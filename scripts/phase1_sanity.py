"""
phase1_sanity.py — Phase 1 sanity check for the Hotter-Than-France project.

Fetches the ECMWF IFS HRES daily max 2m temperature for 2026-06-22 (00z run),
normalizes it, and prints key diagnostics.

Run from project root:
    .venv/bin/python scripts/phase1_sanity.py
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'src' package resolves
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import numpy as np
from src.loaders.ecmwf_opendata import load_daily_tmax

DATE = "2026-06-22"
RUN = "00"

print(f"=== Phase 1 Sanity Check — {DATE} run {RUN}z ===\n")

da = load_daily_tmax(DATE, run=RUN)

# --- Shape ---
shape_str = f"({da.sizes['lat']}, {da.sizes['lon']})"
print(f"shape (lat, lon)       : {shape_str}")

# --- Coordinate ranges ---
lon_min = float(da.lon.min())
lon_max = float(da.lon.max())
lat_min = float(da.lat.min())
lat_max = float(da.lat.max())
print(f"lon range              : {lon_min:.2f} .. {lon_max:.2f}")
print(f"lat range              : {lat_min:.2f} .. {lat_max:.2f}")

# --- Units ---
units = da.attrs.get("units", "NOT SET")
print(f"units                  : {units}")

# --- Global max ---
values = da.values
global_max = float(np.nanmax(values))
# Find (lat, lon) of global max
idx_flat = int(np.nanargmax(values))
i_lat, i_lon = np.unravel_index(idx_flat, values.shape)
max_lat = float(da.lat.values[i_lat])
max_lon = float(da.lon.values[i_lon])
print(f"global max             : {global_max:.2f} degC at (lat={max_lat:.2f}, lon={max_lon:.2f})")

# --- France bounding box max ---
# lat 41.3..51.3, lon -5.5..9.9
france = da.sel(
    lat=slice(41.3, 51.3),
    lon=slice(-5.5, 9.9),
)
france_max = float(np.nanmax(france.values))
print(f"France-bbox max        : {france_max:.2f} degC  (lat 41.3..51.3, lon -5.5..9.9)")

# --- NaN count ---
nan_count = int(np.sum(np.isnan(values)))
print(f"NaN count              : {nan_count}")

# --- Steps used ---
n_steps = da.attrs.get("n_steps_used", "unknown")
print(f"steps used             : {n_steps}")

print("\n=== Done ===")
