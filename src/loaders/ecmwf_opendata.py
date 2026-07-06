"""
ecmwf_opendata.py — fetch and load ECMWF IFS HRES daily maximum 2m temperature.

Data source: ECMWF Open Data (IFS HRES "oper", type=fc, 0.25 deg). Default mirror is the
            Google bucket (storage.googleapis.com/ecmwf-open-data) because the AWS S3 replica
            (s3://ecmwf-forecasts) throttles aggressively on downloads with 503 "Slow Down"
            (Phase 0 + Phase 1, 2026-06-25). AWS is fine for *listing* but unreliable for *fetching*.
            Both mirrors and source='ecmwf' serve byte-identical GRIB. Override via source=.
Parameter:  mx2t3 — 3-hourly maximum 2m temperature (NOT mx2t6, which does not exist in this stream).
Daily max:  max over steps [3, 6, 9, 12, 15, 18, 21, 24] of the 00z run.

Forecast (future-date) support:
  For a target date D and a reference "today" T (UTC), the run used is run_date = min(D, T).
  The daily window is shifted by offset_h = 24 * (D - run_date).days:
    steps = [3 + offset_h, 6 + offset_h, ..., 24 + offset_h].
  Offset 0 (D <= T) is the historical/nowcast path and keeps the ORIGINAL cache filename
  scheme (mx2t3_YYYYMMDD_00z.grib2). Offset > 0 (D > T, a forecast) encodes BOTH the run and
  the target in the cache name (mx2t3_tgt{YYYYMMDD}_run{YYYYMMDD}_00z.grib2) so that a later
  re-run of the same target as an actual day does NOT collide with the stale forecast cache.
  mx2t3 exists 3-hourly only up to step 144, so the maximum supported forecast offset is 5 days
  (24 + 120 = 144). A larger offset raises ValueError (the window driver clamps before calling).

Coordinate conventions after normalize():
  - dims: lat (S->N ascending), lon (-180..180 ascending)
  - units: degC
"""
from __future__ import annotations

import os
import sys
from datetime import (
    date as _date,
    datetime as _datetime,
    timedelta as _timedelta,
    timezone as _timezone,
)
from pathlib import Path

import xarray as xr

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_STEPS = [3, 6, 9, 12, 15, 18, 21, 24]

# mx2t3 is published 3-hourly out to step 144. The daily window is 8 steps ending at 24h,
# so the last usable offset pushes the final step to 144 → offset_h = 120h = 5 days.
MAX_STEP_HOURS = 144
_WINDOW_END_STEP = DEFAULT_STEPS[-1]          # 24
MAX_OFFSET_DAYS = (MAX_STEP_HOURS - _WINDOW_END_STEP) // 24  # 5

# Sentinel: distinguishes "caller did not pass run/steps" (auto-derive) from an explicit override.
_AUTO = None

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
# Date / offset helpers
# ---------------------------------------------------------------------------
def _to_date(value) -> _date:
    """Coerce 'YYYY-MM-DD' / 'YYYYMMDD' / datetime.date to a datetime.date."""
    if isinstance(value, _date):
        return value
    s = str(value).strip()
    if "-" in s:
        return _date.fromisoformat(s)
    return _date(int(s[0:4]), int(s[4:6]), int(s[6:8]))


def today_utc() -> _date:
    """Current UTC calendar date (the latest run that could plausibly exist)."""
    return _datetime.now(_timezone.utc).date()


def resolve_run_and_steps(target, today=None):
    """Compute the run date and forecast steps for a target date.

    run_date = min(target, today); offset_h = 24 * (target - run_date).days;
    steps    = [s + offset_h for s in DEFAULT_STEPS].

    Parameters
    ----------
    target : str | datetime.date
        The day we want the daily-max field for.
    today : str | datetime.date | None
        Reference "today" (UTC). Defaults to today_utc(). Passing this lets tests and
        the window driver pin the run selection deterministically.

    Returns
    -------
    (run_date, steps, offset_h) : (datetime.date, list[int], int)

    Raises
    ------
    ValueError
        If the required offset exceeds MAX_OFFSET_DAYS (mx2t3 stops at step 144).
    """
    target_d = _to_date(target)
    today_d = _to_date(today) if today is not None else today_utc()

    run_date = min(target_d, today_d)
    offset_days = (target_d - run_date).days
    if offset_days > MAX_OFFSET_DAYS:
        raise ValueError(
            f"target {target_d.isoformat()} is {offset_days} days beyond run {run_date.isoformat()}; "
            f"mx2t3 only supports up to {MAX_OFFSET_DAYS} days ahead (final step "
            f"{_WINDOW_END_STEP + offset_days * 24}h > {MAX_STEP_HOURS}h). "
            f"Clamp the requested horizon."
        )
    offset_h = 24 * offset_days
    steps = [s + offset_h for s in DEFAULT_STEPS]
    return run_date, steps, offset_h


def _cache_path(data_dir: Path, target_d: _date, run_d: _date, offset_h: int, run: str) -> Path:
    """Cache filename. Offset 0 keeps the legacy scheme; offset>0 encodes target AND run."""
    if offset_h == 0:
        return data_dir / f"mx2t3_{target_d.strftime('%Y%m%d')}_{run}z.grib2"
    return data_dir / (
        f"mx2t3_tgt{target_d.strftime('%Y%m%d')}_run{run_d.strftime('%Y%m%d')}_{run}z.grib2"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_daily_tmax_grib(
    date_str: str,
    run: str = "00",
    steps: list[int] | None = _AUTO,
    source: str = "google",
    data_dir: Path | str | None = None,
    today=None,
    run_date=None,
    return_offset: bool = False,
):
    """Download the mx2t3 GRIB2 file for a given target date from ECMWF Open Data.

    Behaviour
    ---------
    * If ``steps`` and ``run_date`` are both left at their defaults, the run date and
      forecast steps are auto-derived from ``date_str`` and ``today`` (see
      ``resolve_run_and_steps``). This transparently supports FUTURE target dates by
      shifting the daily window into the correct forecast horizon of an earlier run.
    * If the auto-selected run is TODAY's run and that run is not yet published (the
      download fails early in the day), we fall back to ``run_date - 1 day`` (re-shifting
      the steps by +24h) and retry ONCE.
    * Passing ``steps`` (and/or ``run_date``) explicitly bypasses auto-derivation entirely
      — this preserves the legacy call signature used by phase1_sanity / phase2 scripts.

    Parameters
    ----------
    date_str : str
        Target date in 'YYYY-MM-DD' or 'YYYYMMDD' format, e.g. '2026-06-22'.
    run : str
        Model run hour, e.g. '00'.
    steps : list[int] or None
        Forecast steps to request. ``None`` (default) → auto-derive from the target/today
        offset. An explicit list is used verbatim (legacy path, no offset logic).
    source : str
        ecmwf-opendata source keyword. Default 'google' (reliable for downloads);
        'aws' throttles with 503 Slow Down; 'ecmwf' is the origin (3-day window only).
    data_dir : Path or str, optional
        Directory to store downloaded files. Defaults to <project_root>/data.
    today : str | datetime.date | None
        Reference "today" (UTC) for auto-derivation. Defaults to today_utc().
    run_date : str | datetime.date | None
        Explicit run date override (also disables auto-derivation). Rarely needed.
    return_offset : bool
        When True, return ``(path, effective_offset_h)`` where ``effective_offset_h``
        is the offset of the run ACTUALLY fetched — this differs from the pre-fetch
        offset when the today's-run-unavailable fallback re-shifts to yesterday's run
        (offset += 24). ``load_daily_tmax`` uses this so its ``is_forecast`` annotation
        reflects the grid it actually loaded, not the pre-fallback intent.

    Returns
    -------
    Path
        Path to the downloaded (or pre-existing) GRIB2 file
        (or ``(Path, effective_offset_h)`` when ``return_offset=True``).
    """
    from ecmwf.opendata import Client

    if data_dir is None:
        data_dir = _DEFAULT_DATA_DIR
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    target_d = _to_date(date_str)

    # Every return site reports the EFFECTIVE offset of the run actually fetched, so
    # load_daily_tmax can annotate is_forecast from the real grid (post-fallback), not
    # from the pre-fetch intent. Legacy callers (return_offset=False) still get a bare Path.
    def _ret(path: Path, effective_offset_h: int):
        return (path, int(effective_offset_h)) if return_offset else path

    # -- Auto-derivation vs. explicit override -------------------------------
    explicit = (steps is not _AUTO) or (run_date is not None)
    if explicit:
        # Legacy path: honour caller-provided steps/run_date exactly; no fallback retry.
        eff_steps = list(steps) if steps is not _AUTO else list(DEFAULT_STEPS)
        run_d = _to_date(run_date) if run_date is not None else target_d
        offset_h = 24 * (target_d - run_d).days if run_d <= target_d else 0
        _do_fetch(
            Client, source, run, run_d, eff_steps,
            _cache_path(data_dir, target_d, run_d, offset_h, run),
            date_str,
        )
        return _ret(_cache_path(data_dir, target_d, run_d, offset_h, run), offset_h)

    # -- Auto path -----------------------------------------------------------
    run_d, eff_steps, offset_h = resolve_run_and_steps(target_d, today)
    target_path = _cache_path(data_dir, target_d, run_d, offset_h, run)
    if target_path.exists():
        print(f"[fetch] Cache hit: {target_path}")
        return _ret(target_path, offset_h)

    try:
        _do_fetch(Client, source, run, run_d, eff_steps, target_path, date_str)
        return _ret(target_path, offset_h)
    except Exception as first_err:
        # Only retry-with-fallback when the primary run was TODAY's run (may not be
        # published yet this early in the day). For any offset>0 forecast, that means the
        # run WAS today's run (run_date == today). For offset 0 targets in the past there
        # is nothing to fall back to that would help, so re-raise.
        today_d = _to_date(today) if today is not None else today_utc()
        if run_d != today_d:
            raise
        fb_run = run_d - _timedelta(days=1)
        fb_offset_h = offset_h + 24
        fb_steps = [s + 24 for s in eff_steps]
        if (target_d - fb_run).days > MAX_OFFSET_DAYS:
            # Falling back would exceed the mx2t3 horizon → surface the original error.
            raise
        fb_path = _cache_path(data_dir, target_d, fb_run, fb_offset_h, run)
        # The fallback grid is a +24h forecast of yesterday's run → genuinely a forecast,
        # even when the pre-fetch offset_h was 0 (target == today). Report fb_offset_h.
        if fb_path.exists():
            print(f"[fetch] Cache hit (fallback run): {fb_path}")
            return _ret(fb_path, fb_offset_h)
        print(f"[fetch] Today's run {run_d.isoformat()} unavailable "
              f"({type(first_err).__name__}); falling back to {fb_run.isoformat()} run, "
              f"steps {fb_steps} ...")
        _do_fetch(Client, source, run, fb_run, fb_steps, fb_path, date_str)
        return _ret(fb_path, fb_offset_h)


def _do_fetch(Client, source, run, run_d, steps, target_path, target_label):
    """Perform one retrieve() into target_path (cache hit short-circuits)."""
    if Path(target_path).exists():
        print(f"[fetch] Cache hit: {target_path}")
        return
    print(f"[fetch] Downloading mx2t3 target={target_label} run={run_d.isoformat()} {run}z "
          f"steps {steps} from {source} ...")
    client = Client(source=source)
    client.retrieve(
        date=run_d.strftime("%Y-%m-%d"),
        time=int(run),
        stream="oper",
        type="fc",
        param="mx2t3",
        step=list(steps),
        target=str(target_path),
    )
    print(f"[fetch] Saved to {target_path} ({Path(target_path).stat().st_size / 1e6:.1f} MB)")


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
    steps: list[int] | None = _AUTO,
    source: str = "google",
    data_dir: Path | str | None = None,
    today=None,
    run_date=None,
) -> xr.DataArray:
    """Fetch, open, and normalize the daily maximum 2m temperature.

    Composes fetch_daily_tmax_grib() + open_daily_tmax() + normalize().
    Returns a DataArray with:
      - dims: lat (S->N), lon (-180..180 ascending)
      - units: degC
      - attrs['forecast_offset_h'] : int  — 0 for actual/nowcast days, >0 for forecasts
      - attrs['is_forecast']       : bool — True iff forecast_offset_h > 0

    Future target dates are supported transparently: see fetch_daily_tmax_grib and
    resolve_run_and_steps. Legacy callers passing steps=/run= keep offset 0 behaviour.

    Parameters
    ----------
    date_str : str
        Target date in 'YYYY-MM-DD' or 'YYYYMMDD' format.
    run : str
        Model run hour (default '00').
    steps : list[int] or None
        Forecast steps. None → auto-derive from target/today offset (default).
    source : str
        ecmwf-opendata source (default 'google'; 'aws' throttles on downloads).
    data_dir : Path or str, optional
        Directory for cached GRIB files.
    today : str | datetime.date | None
        Reference "today" (UTC) for auto-derivation. Defaults to today_utc().
    run_date : str | datetime.date | None
        Explicit run date override (disables auto-derivation).

    Returns
    -------
    xr.DataArray
        Normalized daily max 2m temperature in degC (see attrs above).
    """
    normalize = _get_normalize()

    # Annotate is_forecast from the run ACTUALLY fetched. fetch_daily_tmax_grib returns the
    # EFFECTIVE offset — which differs from the pre-fetch resolve when today's run is missing
    # and the loader falls back to yesterday's +24h grid (a genuine forecast even for a
    # "today" target that resolves to offset 0). Using the pre-fetch offset would mislabel
    # such a fallback grid as an actual day (no fcst flag). See fetch_daily_tmax_grib.
    grib_path, offset_h = fetch_daily_tmax_grib(
        date_str=date_str,
        run=run,
        steps=steps,
        source=source,
        data_dir=data_dir,
        today=today,
        run_date=run_date,
        return_offset=True,
    )
    da_kelvin = open_daily_tmax(grib_path)
    da_degc = normalize(da_kelvin)
    da_degc.attrs["forecast_offset_h"] = int(offset_h)
    da_degc.attrs["is_forecast"] = bool(offset_h > 0)
    return da_degc
