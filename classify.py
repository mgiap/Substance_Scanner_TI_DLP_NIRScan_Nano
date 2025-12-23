#!/usr/bin/env python3
import os
from pathlib import Path
import time
import subprocess
import sys
import numpy as np
import tflite_runtime.interpreter as tflite

MODEL_PATH = "/home/long0/model/model.tflite"
SCANS_DIR = str(Path.home() / "Scans")
CLASS_NAMES = ["MSG", "Salt", "Sugar"]
UNDETECTED_LABEL = "Undetected"
CONF_THRESHOLD = 0.8  # adjust as you like
POLL_INTERVAL_SEC = 1.0  # how often to check for a newer file
USE_STATIC_TEST_FIRST = True  # run one classification with static test array before realtime loop


def get_nir_from_device(raw_data) -> np.ndarray:
    """
    Convert absorbance values to float32 numpy array (dummy device feed).
    """
    dummy = np.array(raw_data, dtype=np.float32)
    return dummy


def find_latest_csv_without_prefix(scans_dir: str) -> Path | None:
    """Find the latest CSV file in scans_dir with no prefix (digits only name)."""
    p = Path(scans_dir).expanduser()
    if not p.exists():
        return None
    candidates = []
    for f in p.glob("*.csv"):
        name = f.name
        # Accept files that do NOT start with known prefixes and are digit-only before .csv
        stem = f.stem
        if stem.isdigit():
            candidates.append(f)
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_mtime)


def read_absorbance_column(csv_path: Path) -> np.ndarray:
    """Read 'absorbance' column from CSV and return as float32 numpy array."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    # Normalize columns
    cols = [c.strip().lower() for c in df.columns]
    df.columns = cols
    if "absorbance" not in df.columns:
        raise ValueError(f"'absorbance' column not found in {csv_path}")
    values = df["absorbance"].astype(np.float32).to_numpy()
    return values


def load_model():
    interpreter = tflite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()
    return interpreter


def run_scan_substance():
    """Invoke the scanner to capture a new scan and save CSV."""
    script_path = Path.home() / "NIRScanner-Python" / "scan_substance.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Scanner script not found: {script_path}")
    print(f"Starting scan via: {script_path} --save-csv")
    # Use current Python interpreter to ensure environment consistency
    result = subprocess.run([sys.executable, str(script_path), "--save-csv"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Scan script stderr:\n" + (result.stderr or "<none>"))
        print("Scan script stdout:\n" + (result.stdout or "<none>"))
        raise RuntimeError(f"Scan script failed with exit code {result.returncode}")
    print("Scan completed successfully.")


def run_model(interpreter, spectrum_1d_float: np.ndarray):
    if spectrum_1d_float is None:
        raise ValueError("spectrum_1d_float is None.")

    input_details = interpreter.get_input_details()[0]
    output_details = interpreter.get_output_details()[0]

    print("Input details:", input_details)
    print("Output details:", output_details)
    print("Float spectrum shape:", spectrum_1d_float.shape)

    input_index = input_details["index"]
    input_shape = input_details["shape"]
    input_dtype = input_details["dtype"]

    # Ensure length matches model expectation (account for diff length = N-1)
    expected_len = input_shape[1] if len(input_shape) >= 2 else spectrum_1d_float.shape[0]
    current_len = spectrum_1d_float.shape[0]
    if current_len != expected_len:
        # Simple padding/truncation strategy: if one short (e.g., 227 vs 228), pad last value
        if current_len < expected_len:
            pad_count = expected_len - current_len
            pad_value = spectrum_1d_float[-1] if current_len > 0 else 0.0
            spectrum_1d_float = np.concatenate([spectrum_1d_float, np.full(pad_count, pad_value, dtype=np.float32)])
        else:
            spectrum_1d_float = spectrum_1d_float[:expected_len]

    # reshape float data to [1, expected_len, 1]
    if len(input_shape) == 3 and input_shape[0] == 1 and input_shape[2] == 1:
        float_reshaped = spectrum_1d_float.reshape((1, expected_len, 1))
    elif len(input_shape) == 2 and input_shape[0] == 1:
        float_reshaped = spectrum_1d_float.reshape((1, expected_len))
    else:
        raise RuntimeError(f"Unsupported input shape {input_shape} for prepared length {expected_len}")

    # For 32-bit float models, feed raw float32 directly
    if input_dtype == np.float32:
        x = float_reshaped.astype(np.float32)
    else:
        # Fallback: cast to model's dtype (no manual quantization here)
        x = float_reshaped.astype(input_dtype)

    interpreter.set_tensor(input_index, x)
    interpreter.invoke()

    output_index = output_details["index"]
    raw_output = interpreter.get_tensor(output_index).squeeze()
    # If output is float32 (typical for 32-bit model), return directly
    if raw_output.dtype == np.float32:
        return raw_output
    # Else cast to float32 for downstream processing
    return raw_output.astype(np.float32)


def softmax(z: np.ndarray) -> np.ndarray:
    e = np.exp(z - np.max(z))
    return e / np.sum(e)


def classify(output: np.ndarray):
    probs = output

    idx = int(np.argmax(probs))
    conf = float(probs[idx])

    if conf < CONF_THRESHOLD:
        return UNDETECTED_LABEL, conf, probs
    
    return CLASS_NAMES[idx], conf, probs


def main():
    print("Loading TFLite model...")
    interpreter = load_model()
    print(f"Watching for latest CSV in {SCANS_DIR} (no-prefix names like 20251210152633.csv)...")

    # Record current latest file mtime (if any) before triggering a new scan
    pre_latest = find_latest_csv_without_prefix(SCANS_DIR)
    last_processed_mtime = pre_latest.stat().st_mtime if pre_latest else None

    # Trigger scan to generate a fresh CSV
    try:
        run_scan_substance()
    except Exception as e:
        print(f"Failed to run scanner: {e}")
        return

    
    latest = find_latest_csv_without_prefix(SCANS_DIR)
    if latest is None:
        print("No digit-only CSV found after scan.")
        return

    mtime = latest.stat().st_mtime
    if last_processed_mtime is not None and mtime <= last_processed_mtime:
        # No new file generated by the scan
        print("No new CSV detected compared to pre-scan state.")
        return

    try:
        label = ""
        conf = 0.0
        err = ""
        print(f"Reading absorbance from: {latest}")
        absorbance_vals = read_absorbance_column(latest)
        # Validate data: no NaNs and enough points to compute differences
        if np.isnan(absorbance_vals).any() or absorbance_vals.shape[0] < 228:
            err = "Not enough valid absorbance points to compute differences. Please scan again!"
            return label, conf, err
            
        delta_vals = np.diff(absorbance_vals).astype(np.float32)
        print("Using delta input, len =", len(delta_vals))
        x_float = get_nir_from_device(delta_vals)
        print("Running inference...")
        output = run_model(interpreter, x_float)
        label, conf, probs = classify(output)

        print("\n=== CLASSIFICATION RESULT ===")
        print("File       :", latest.name)
        print("Label      :", label)
        print("Confidence :", f"{conf:.4f}")
        print("Prob vector:", probs)
        return label, conf, err
    except Exception as e:
        print(f"Error processing {latest}: {e}")



if __name__ == "__main__":
    main()

