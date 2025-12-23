# NIRScanner-Python — Minimal for Raspberry Pi 3B (Python 3.11.2)

This repository has been trimmed to the essentials required to acquire a single scan from a DLP NIRScan Nano and save the result as a CSV using Python 3.11.2 on a Raspberry Pi 3B.

Files you will use:
- `NIRS.py` — Python wrapper around the native `_NIRScanner.so` extension.
- `scan_substance.py` — acquisition script (per-scan 1D NumPy intensity array; optional CSV save to `Data/`).
- `build_native_pi.sh` — helper to build the native shared object with a chosen Python executable.
- `requirements.txt` — Python packages required by the acquisition script.
- `prune_unused.sh` — optional script to remove demo/test files locally on the Pi to minimize repo footprint.
- `systemd/nirscan.service` — example `systemd` unit (edit paths to your venv/project).

Quick minimal setup (assumes you already have a tflite venv and want to reuse it)

1) Copy or clone this repo to your Pi and change to the project directory.

2) Ensure a matching `_NIRScanner.so` is available in project root. To build it with your venv Python:

```bash
# run the build helper and give it the venv python executable
./build_native_pi.sh /path/to/venv/bin/python
```

3) Activate your existing venv and install dependencies:

```bash
source /path/to/venv/bin/activate
pip install -r requirements.txt
```

4) (Optional) Minimize repository on the Pi by removing demo/test files. Run this from the project root:

```bash
chmod +x prune_unused.sh
./prune_unused.sh
```

5) Run a scan and save CSV (use the venv python directly):

```bash
/path/to/venv/bin/python scan_substance.py --save-csv
```

6) To run at boot, adapt the example in `systemd/nirscan.service` (edit `ExecStart` and `WorkingDirectory` to match your venv and project paths), then copy it to `/etc/systemd/system/` and enable it:

```bash
sudo cp systemd/nirscan.service /etc/systemd/system/nirscan.service
sudo systemctl daemon-reload
sudo systemctl enable --now nirscan.service
sudo journalctl -u nirscan.service -f
```

Notes
- Keep `lib/` and `src/` if you want to try prebuilt binaries or rebuild the native extension locally — `build_native_pi.sh` will compile against the provided Python executable.
- `prune_unused.sh` will prompt before deleting demo files; I left deletion under your control so you can verify everything on the Pi first.
- If `_NIRScanner.so` is not compatible with the venv Python (ABI mismatch), build with the venv python as shown above.

If you want I can now:
- (A) adapt `systemd/nirscan.service` with your exact venv path and add an install script that registers it automatically, or
- (B) add a small preprocessing helper (SNV/MSC/Savitzky–Golay) to `scan_substance.py` and optionally save both raw and preprocessed spectra.

Tell me which and I will implement it.

Quick setup
1. Ensure the compiled Python extension (`_NIRScanner.so`) matching your Python version is available in the project root or on `PYTHONPATH`. The `lib/` folder contains prebuilt binaries for some platforms.

2. Install OS packages (Debian/Ubuntu/Raspbian):

```bash
sudo apt-get update
sudo apt-get install -y libudev-dev libusb-1.0-0-dev python3-dev python3-pip
```

3. (Optional) Create a virtualenv and install Python deps used by examples:

```bash
python3 -m venv .venv
.\\.venv\\Scripts\\activate    # Windows (if testing on Windows)
source .venv/bin/activate    # Linux / Raspberry Pi
pip install numpy pandas scipy pillow requests
```

If you are using Python 3.11.2 (Raspberry Pi 3B):

- Run the `check_python_version.py` script to verify your Python ABI information before using prebuilt binaries:

```bash
python3 check_python_version.py
```

- If there is no `_NIRScanner.so` matching your Python ABI in `lib/`, build the native extension using the included helper script:

```bash
# example: explicitly provide python executable
./build_native_pi.sh /usr/bin/python3.11
# or use default python3 on the Pi
./build_native_pi.sh
```

The build script will run CMake and Make in the `src/` folder and copy the resulting shared object to the project root as `_NIRScanner.so`.

Install Python dependencies into your venv (use the provided `requirements.txt`):

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Running a substance scan (example)
- `scan_substance.py` is an example script that:
  - Instantiates the `NIRS` wrapper
  - Configures the device
  - Performs a scan
  - Returns a 1D NumPy array of intensities and saves a timestamped CSV to `Data/`

Example command (on the Pi):

```bash
python3 scan_substance.py --save-csv
```

Output:
- The script prints a summary and saves `Data/<timestamp>.csv` containing two columns: wavelength (nm) and intensity (AU). If the device or native library isn't available, the script will fall back to a simulated spectrum (useful for testing).

Integrating substance analysis
- Each scan returns a 1D intensity array; this is the raw spectral data. For substance scanning you typically:
  - Convert intensity -> reflectance (divide by reference)
  - Apply preprocessing (SNV, MSC, derivatives, smoothing)
  - Run classification/regression models (PLS, SVM, neural nets)

- Keep your substance-specific models separate from the scanner wrapper. Use `scan_substance.py` as the acquisition step and then pipe the returned 1D array into your analysis pipeline.

Next steps you might want me to do
- Add a CLI flag to `scan_substance.py` to run multiple repeats or different scan types (hadamard vs column).
- Integrate an example PLS classification/regression pipeline for your substance dataset.
- Clean up remaining demo scripts (`testAll.py`, `testNIR.py`) to remove fruit-specific code.

License & Notes
- This repo wraps vendor-provided binaries and code; check the original project and vendor licenses for redistribution constraints.
