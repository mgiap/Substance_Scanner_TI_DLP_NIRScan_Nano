#!/usr/bin/env python3
"""Simple example: perform one scan and return a 1D NumPy array of intensities.

Usage:
    python3 scan_substance.py [--save-csv]

If the native `_NIRScanner` extension or attached device isn't available the script
falls back to a simulated spectrum for testing.
"""
import argparse
import time
import os
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from NIRS import NIRS
    HAS_NIRS = True
except Exception as e:
    # If the wrapper or native lib is unavailable, fall back to simulation
    print("Warning: real NIRS wrapper not available, falling back to simulated data.")
    HAS_NIRS = False


def acquire_spectrum(n_repeats=1, save_csv=False):
    """Return (wavelengths, intensities) as NumPy arrays.

    - wavelengths: 1D array of wavelength (nm) or None if not provided
    - intensities: 1D array of intensity (AU)
    """
    if HAS_NIRS:
        nirs = NIRS()
        # Example config: adjust for your needs
        try:
            nirs.set_config(8, NIRS.TYPES.HADAMARD_TYPE, 228, n_repeats, 900, 1700, 7)
        except Exception:
            # If set_config signature or values differ, ignore and continue
            pass
        # Turn lamp on
        try:
            nirs.set_lamp_on_off(1)
        except Exception:
            pass
        # Wait a bit for lamp to stabilize
        time.sleep(1.0)
        # Perform scan
        nirs.scan(n_repeats)
        results = nirs.get_scan_results()
        # keep the raw results dict for legacy CSV formatting
        results_raw = dict(results)
        # Turn lamp off
        try:
            nirs.set_lamp_on_off(-1)
        except Exception:
            pass

        wavelengths = results.get('wavelength', None)
        intensities = results.get('intensity', None)
        references = results.get('reference', None)
        if intensities is None:
            raise RuntimeError('Device returned no intensity data')
        wavelengths = np.array(wavelengths) if wavelengths is not None else None
        intensities = np.array(intensities)
        references = np.array(references) if references is not None else None
    else:
        # Simulate wavelengths and intensities
        wavelengths = np.linspace(900, 1700, 227)
        intensities = np.abs(np.sin(np.linspace(0, 6.28, 227)) * 5e4 + np.linspace(1e4, 8e4, 227))
        # create a simulated references array to match legacy CSV layout
        references = np.full_like(intensities, np.nan)

    # Compute absorbance if reference available: A = -log10(intensity / reference)
    absorbance = None
    if references is not None:
        # avoid division by zero and invalid values
        with np.errstate(divide='ignore', invalid='ignore'):
            reflectance = np.where(references > 0, intensities.astype(float) / references.astype(float), np.nan)
            absorbance = np.where(reflectance > 0, -np.log10(reflectance), np.nan)

    # Optionally save CSV
    if save_csv:
        # 'prefix' will be provided via outer-scope (main) by design. If missing, default to ''
        prefix = globals().get('__csv_prefix__', '')
        # sanitize prefix: allow alnum, dash, underscore
        if prefix:
            safe_prefix = ''.join(c for c in prefix if (c.isalnum() or c in ('-', '_')))
            safe_prefix = safe_prefix.strip('-_')
        else:
            safe_prefix = ''

        # Save scans under the user's Scans directory (expand ~)
        target_dir = os.path.expanduser('~/Scans')
        os.makedirs(target_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        if safe_prefix:
            filename = os.path.join(target_dir, f'{safe_prefix}-{timestamp}.csv')
        else:
            filename = os.path.join(target_dir, f'{timestamp}.csv')
        # If we have live device results, save in the legacy DataFrame layout
        columns_order = [
            'header_version', 'scan_name', 'scan_time', 'temperature_system',
            'temperature_detector', 'humidity', 'pga', 'wavelength', 'intensity',
            'reference', 'valid_length', 'absorbance'
        ]

        if HAS_NIRS and 'results_raw' in locals():
            # Ensure results_raw contains an 'absorbance' field (fill with NaN if missing)
            length = None
            try:
                length = int(results_raw.get('valid_length', 0))
            except Exception:
                pass
            if length is None or length == 0:
                # fallback to intensity length
                try:
                    length = len(results_raw.get('intensity', []))
                except Exception:
                    length = 0

            if 'absorbance' not in results_raw:
                if absorbance is not None:
                    results_raw['absorbance'] = list(absorbance)
                else:
                    results_raw['absorbance'] = [float('nan')] * length

            # results_raw is expected to be a dict with list-like and scalar entries
            df = pd.DataFrame(results_raw)
            # ensure columns order matches legacy layout (absorbance will be last)
            df = df.reindex(columns=columns_order)
            df.to_csv(filename, index=True)
        else:
            # Simulated or no-NIRS fallback: construct a dict similar to legacy results
            length = len(intensities) if hasattr(intensities, '__len__') else 1
            sim_results = {
                'header_version': 0,
                'scan_name': 'sim',
                'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'temperature_system': np.nan,
                'temperature_detector': np.nan,
                'humidity': np.nan,
                'pga': np.nan,
                'wavelength': list(wavelengths) if wavelengths is not None else [np.nan] * length,
                'intensity': list(intensities) if hasattr(intensities, '__len__') else [intensities],
                'reference': list(references) if references is not None else [np.nan] * length,
                'valid_length': length,
                'absorbance': list(absorbance) if absorbance is not None else [np.nan] * length
            }
            df = pd.DataFrame(sim_results)
            df = df.reindex(columns=columns_order)
            df.to_csv(filename, index=True)

        print(f'Saved scan to {filename}')

    return wavelengths, intensities, references, absorbance


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--save-csv', action='store_true', help='Save a CSV of the scan into Data/')
    parser.add_argument('--prefix', type=str, default='', help='Optional filename prefix for saved CSV (e.g. sugar, salt). If empty, no prefix is added.')
    parser.add_argument('--repeats', type=int, default=1, help='Number of repeats to perform')
    args = parser.parse_args()

    # Make prefix available to acquire_spectrum via module-global variable
    prefix = (args.prefix or '').strip()
    globals()['__csv_prefix__'] = prefix

    wl, ints, refs, absb = acquire_spectrum(n_repeats=args.repeats, save_csv=args.save_csv)
    print('Scan result: intensities shape =', ints.shape)
    # For convenience print first 10 values
    print('First 10 intensity values:', ints[:10].tolist())
    if refs is not None:
        print('Reference shape =', refs.shape)
    if absb is not None:
        print('Absorbance shape =', absb.shape)

    # Return (wavelengths, intensities, references, absorbance)
    return wl, ints, refs, absb


if __name__ == '__main__':
    main()
