"""
phase2_calibration.py — Phase 2 calibration against Ben Noll's (WaPo) ~1.2% figure.

For each date in [2026-06-22, 2026-06-23, 2026-06-24] (00z run):
  1. Load normalized daily-max 2m temperature (degC, IFS HRES 0.25° via ECMWF Open Data).
  2. Build metropolitan France mask (once — grid is constant across dates).
  3. Compute:
       - france_max  : hottest single grid cell in metropolitan France (degC)
       - france_p95  : 95th-percentile temperature in France (degC)
       - frac_all    : cos-lat area-weighted % of planet strictly > france_max
       - frac_land   : same, land only (Natural Earth 110m; -1 if unavailable)
  4. Print a formatted table with the Noll target for 22 Jun 2026 (1.2%).

CALIBRATION NOTE: Noll's quoted figure (~1.2% of Earth's surface hotter than
France) used 'France's hottest place' as the threshold — i.e., France's
maximum grid cell (method='max'). This script uses that same threshold as the
primary (faithful) method.

Usage:
  python scripts/phase2_calibration.py [--source google|aws|ecmwf]
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path for package imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.loaders.ecmwf_opendata import load_daily_tmax
from src.core.france import metropolitan_france_mask
from src.core.threshold import france_threshold, planet_fraction_hotter, build_land_mask

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DATES = ['2026-06-22', '2026-06-23', '2026-06-24']
NOLL_DATE = '2026-06-22'
NOLL_TARGET_PCT = 1.2
SOURCE = 'google'  # override via --source CLI arg


def parse_args():
    source = SOURCE
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--source' and i + 1 < len(sys.argv) - 1:
            source = sys.argv[i + 2]
    return source


def main():
    source = parse_args()
    print("=" * 72)
    print("Hotter-Than-France — Phase 2 Calibration")
    print(f"Dates: {', '.join(DATES)}  |  Source: {source}")
    print(f"Noll target (22 Jun 2026): {NOLL_TARGET_PCT}% (WaPo)")
    print("=" * 72)

    # ------------------------------------------------------------------
    # Load first date to build masks (grid is constant)
    # ------------------------------------------------------------------
    print(f"\n[step 1] Loading {DATES[0]} to build France mask and land mask...")
    da0 = load_daily_tmax(DATES[0], source=source)
    print(f"  Grid: {da0.sizes['lat']} lat x {da0.sizes['lon']} lon")
    print(f"  Lat: {float(da0.lat.min()):.2f} .. {float(da0.lat.max()):.2f}")
    print(f"  Lon: {float(da0.lon.min()):.2f} .. {float(da0.lon.max()):.2f}")
    print(f"  NaN cells: {int(da0.isnull().sum())}")

    print("\n[step 2] Building metropolitan France mask...")
    france_mask = metropolitan_france_mask(da0, verbose=True)
    n_france_cells = int(france_mask.sum())

    print("\n[step 3] Building land mask (110m Natural Earth, optional)...")
    land_mask = build_land_mask(da0)
    if land_mask is not None:
        n_land = int(land_mask.sum())
        n_total = land_mask.size
        print(f"  Land cells: {n_land} / {n_total} ({100.*n_land/n_total:.1f}%)")
    else:
        print("  Land mask unavailable — frac_land will be -1")

    # ------------------------------------------------------------------
    # Per-date computation
    # ------------------------------------------------------------------
    results = []

    for date in DATES:
        print(f"\n{'─'*60}")
        print(f"[date] {date}")
        if date == DATES[0]:
            da = da0
        else:
            print(f"  Loading data...")
            da = load_daily_tmax(date, source=source)

        f_max = france_threshold(da, france_mask, method='max')
        f_p95 = france_threshold(da, france_mask, method='percentile', q=0.95)
        frac_all = planet_fraction_hotter(da, threshold=f_max, domain='all')
        frac_land = planet_fraction_hotter(da, threshold=f_max, domain='land',
                                           land_mask=land_mask)

        noll_target = NOLL_TARGET_PCT if date == NOLL_DATE else -1.0

        results.append({
            'date': date,
            'france_max_c': f_max,
            'france_p95_c': f_p95,
            'frac_all_pct': frac_all,
            'frac_land_pct': frac_land,
            'noll_target_pct': noll_target,
        })

        print(f"  France max (hottest cell) : {f_max:.2f} °C")
        print(f"  France p95                : {f_p95:.2f} °C")
        print(f"  % planet hotter (all)     : {frac_all:.3f}%")
        if frac_land >= 0:
            print(f"  % planet hotter (land)    : {frac_land:.3f}%")
        else:
            print(f"  % planet hotter (land)    : n/a")
        if date == NOLL_DATE:
            print(f"  Noll target (22 Jun)      : {NOLL_TARGET_PCT}%  "
                  f"[{'WITHIN RANGE' if 0.5 <= frac_all <= 2.5 else 'OUT OF RANGE'}]")

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    print(f"\n{'='*72}")
    print("SUMMARY TABLE")
    print(f"{'─'*72}")
    hdr = f"{'Date':<12} {'FR max (°C)':>12} {'FR p95 (°C)':>12} {'Frac all %':>12} {'Frac land %':>12} {'Noll %':>8}"
    print(hdr)
    print(f"{'─'*72}")
    for r in results:
        noll_str = f"{r['noll_target_pct']:.1f}" if r['noll_target_pct'] >= 0 else "  n/a"
        land_str = f"{r['frac_land_pct']:.3f}" if r['frac_land_pct'] >= 0 else "   n/a"
        print(f"{r['date']:<12} {r['france_max_c']:>12.2f} {r['france_p95_c']:>12.2f} "
              f"{r['frac_all_pct']:>12.3f} {land_str:>12} {noll_str:>8}")
    print(f"{'─'*72}")
    print(f"Note: threshold = France's hottest single 0.25° grid cell (method='max').")
    print(f"      Fraction = cos-lat area-weighted % of globe STRICTLY > threshold.")
    print(f"      Noll target = ~1.2% of Earth hotter than France's hottest place,")
    print(f"                    quoted by Ben Noll (WaPo) for 22 Jun 2026.")
    print(f"{'='*72}")

    return results


if __name__ == '__main__':
    main()
