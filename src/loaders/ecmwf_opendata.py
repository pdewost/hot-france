"""
ecmwf_opendata.py — fetch and load ECMWF IFS HRES daily maximum 2m temperature.

Data source: ECMWF Open Data (IFS HRES "oper", type=fc, 0.25 deg). Default mirror is the
            Google bucket (storage.googleapis.com/ecmwf-open-data) because the AWS S3 replica
            (s3://ecmwf-forecasts) throttles aggressively on downloads with 503 "Slow Down"
            (Phase 0 + Phase 1, 2026-06-25). AWS is fine for *listing* but unreliable for *fetching*.
            Both mirrors and source='ecmwf' serve byte-identical GRIB. Override via source=.
Parameter:  mx2t3 — 3-hourly maximum 2m temperature (NOT mx2t6, which does not exist in this stream).
Daily max:  max over steps [3, 6, 9, 12, 15, 18, 21, 24] of the 00z run.

Coordinate conventions after normalize():
  - dims: lat (S->N ascending), lon (-180..180 ascending)
  - units: degC
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import xarray as xr

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_STEPS = [3, 6, 9, 12, 15, 18, 21, 24]

# Project root is two levels up from this file: src/loaders/ecmwf_opendata.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data"


# ---------------------------------------------------------------------------
# Internal: import normalize (works both as package and as script)
# ---------------------------------------------------------------------------
def _get_normalize():
    """Return the normalize function, supporting both package and script usage."""
    try:
        from ..core.normalize import normalize  # package import
        return normalize
    except ImportError:
        # Fallback: add project root to sys.path and import directly
        root = str(_PROJECT_ROOT)
        if root not in sys.path:
            sys.path.insert(0, root)
        from src.core.normalize import normalize  # type: ignore[import]
        return normalize


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_daily_tmax_grib(
    date_str: str,
    run: str = "00",
    steps: list[int] = DEFAULT_STEPS,
    source: str = "google",
    data_dir: Path | str | None = None,
) -> Path:
    """Download the mx2t3 GRIB2 file for a given date from ECMWF Open Data.

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' or 'YYYYMMDD' format, e.g. '2026-06-22'.
    run : str
        Model run hour, e.g. '00'.
    steps : list[int]
        Forecast steps to request (default: [3,6,...,24] — full daily window).
    source : str
        ecmwf-opendata source keyword. Default 'google' (reliable for downloads);
        'aws' throttles with 503 Slow Down; 'ecmwf' is the origin (3-day window only).
    data_dir : Path or str, optional
        Directory to store downloaded files. Defaults to <project_root>/data.

    Returns
    -------
    Path
        Path to the downloaded (or pre-existing) GRIB2 file.
    """
    from ecmwf.opendata import Client

    if data_dir is None:
        data_dir = _DEFAULT_DATA_DIR
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Normalise date string to YYYYMMDD for the filename
    date_compact = date_str.replace("-", "")
    target_path = data_dir / f"mx2t3_{date_compact}_{run}z.grib2"

    if target_path.exists():
        print(f"[fetch] Cache hit: {target_path}")
        return target_path

    print(f"[fetch] Downloading mx2t3 for {date_str} run {run}z steps {steps} from {source}...")
    client = Client(source=source)
    client.retrieve(
        date=date_str,
        time=int(run),
        stream="oper",
        type="fc",
        param="mx2t3",
        step=steps,
        target=str(target_path),
    )
    print(f"[fetch] Saved to {target_path} ({target_path.stat().st_size / 1e6:.1f} MB)")
    return target_path


def open_daily_tmax(grib_path: Path | str) -> xr.DataArray:
    """Open a mx2t3 GRIB2 file and compute the daily max over all steps.

    Parameters
    ----------
    grib_path : Path or str
        Path to the GRIB2 file produced by fetch_daily_tmax_grib().

    Returns
    -------
    xr.DataArray
        Daily maximum 2m temperature in Kelvin, with dims (latitude, longitude).
        The 'step' dimension is reduced by taking the max over all steps present.
    """
    grib_path = Path(grib_path)

    ds = xr.open_dataset(str(grib_path), engine="cfgrib")

    # Identify the mx2t3 variable
    if "mx2t3" in ds.data_vars:
        da = ds["mx2t3"]
    elif len(ds.data_vars) == 1:
        var_name = list(ds.data_vars)[0]
        print(f"[open] Variable '{var_name}' used (single data_var in dataset)")
        da = ds[var_name]
    else:
        # Pick the first variable and warn
        var_name = list(ds.data_vars)[0]
        print(f"[open] Warning: multiple data_vars {list(ds.data_vars)}, using '{var_name}'")
        da = ds[var_name]

    # Record how many steps are present
    if "step" in da.dims:
        n_steps = da.sizes["step"]
        print(f"[open] {n_steps} steps found: {list(da.step.values)}")
        da = da.max(dim="step")
    else:
        n_steps = 1
        print(f"[open] No 'step' dim — treating as single-step field")

    da.attrs["n_steps_used"] = n_steps
    return da


def load_daily_tmax(
    date_str: str,
    run: str = "00",
    steps: list[int] = DEFAULT_STEPS,
    source: str = "google",
    data_dir: Path | str | None = None,
) -> xr.DataArray:
    """Fetch, open, and normalize the daily maximum 2m temperature.

    Composes fetch_daily_tmax_grib() + open_daily_tmax() + normalize().
    Returns a DataArray with:
      - dims: lat (S->N), lon (-180..180 ascending)
      - units: degC

    Parameters
    ----------
    date_str : str
        Date in 'YYYY-MM-DD' or 'YYYYMMDD' format.
    run : str
        Model run hour (default '00').
    steps : list[int]
        Forecast steps (default DEFAULT_STEPS = [3,6,...,24]).
    source : str
        ecmwf-opendata source (default 'google'; 'aws' throttles on downloads).
    data_dir : Path or str, optional
        Directory for cached GRIB files.

    Returns
    -------
    xr.DataArray
        Normalized daily max 2m temperature in degC.
    """
    normalize = _get_normalize()

    grib_path = fetch_daily_tmax_grib(
        date_str=date_str,
        run=run,
        steps=steps,
        source=source,
        data_dir=data_dir,
    )
    da_kelvin = open_daily_tmax(grib_path)
    da_degc = normalize(da_kelvin)
    return da_degc
