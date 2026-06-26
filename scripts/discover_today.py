"""
discover_today.py — Find the "hottest reference country" for any given date.

For each candidate country, computes:
  - country_max_c : highest grid-cell temperature (°C) today
  - planet_frac   : cos-lat area-weighted % of the globe strictly hotter

Prints a ranked table (hottest countries first) and flags the "editorial
winner" — the country with the lowest threshold that still falls below the
target fraction. That is: the most relatable extreme where the comparison
map still looks dramatic (few places hotter).

Usage:
  python scripts/discover_today.py             # today, target < 0.8%
  python scripts/discover_today.py 2026-06-25  # specific date
  python scripts/discover_today.py 2026-06-25 --target 1.2
"""
from __future__ import annotations

import sys
import argparse
from pathlib import Path
from datetime import date as _date

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.loaders.ecmwf_opendata import load_daily_tmax
from src.core.france import metropolitan_france_mask
from src.core.country import country_mask
from src.core.threshold import planet_fraction_hotter

# ---------------------------------------------------------------------------
# Candidate list: (display_label, iso3, bbox_or_None, special_or_None)
# bbox   = (lon_min, lat_min, lon_max, lat_max) — clips overseas territories
# special= 'france' uses the dedicated metropolitan_france_mask (more precise)
# ---------------------------------------------------------------------------
CANDIDATES = [
    # Europe west / south
    ('France',        'FRA', None,              'france'),  # metropolitan mask
    ('Spain',         'ESP', (-10, 35,  5, 45), None),      # excl. Canary Islands
    ('Portugal',      'PRT', (-10, 36, -6, 42), None),      # excl. Azores + Madeira
    ('Italy',         'ITA', (  6, 36, 19, 48), None),      # incl. Sicily/Sardinia
    ('Greece',        'GRC', ( 19, 34, 30, 42), None),
    # Europe central / north
    ('Germany',       'DEU', None,              None),
    ('Austria',       'AUT', None,              None),
    ('Switzerland',   'CHE', None,              None),
    ('Hungary',       'HUN', None,              None),
    ('Romania',       'ROU', None,              None),
    ('UK',            'GBR', ( -8, 49,  2, 62), None),      # excl. Gibraltar
    # Balkans / eastern Med
    ('Turkey',        'TUR', ( 25, 35, 45, 43), None),
    ('Bulgaria',      'BGR', None,              None),
    ('Serbia',        'SRB', None,              None),
    # North Africa
    ('Morocco',       'MAR', None,              None),
    ('Algeria',       'DZA', None,              None),
    ('Tunisia',       'TUN', None,              None),
    ('Libya',         'LBY', None,              None),
    ('Egypt',         'EGY', None,              None),
    # Middle East
    ('Israel',        'ISR', None,              None),
    ('Jordan',        'JOR', None,              None),
    ('Saudi Arabia',  'SAU', None,              None),
]


def _build_mask(da, iso3, bbox, special):
    if special == 'france':
        return metropolitan_france_mask(da, verbose=False)
    return country_mask(da, iso3, bbox)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('date', nargs='?', default=str(_date.today()),
                        help='Date YYYY-MM-DD (default: today)')
    parser.add_argument('--target', type=float, default=0.8,
                        help='Planet-fraction target %% (default: 0.8)')
    args = parser.parse_args()

    date_str   = args.date
    target_pct = args.target
    target_frac = target_pct / 100.0

    print('=' * 72)
    print(f'Hotter-Than-[Country] discovery  |  date: {date_str}')
    print(f'Target: planet fraction strictly hotter < {target_pct:.1f}%')
    print(f'Candidates: {len(CANDIDATES)}')
    print('=' * 72)

    print(f'\n[load] Fetching IFS grid for {date_str} ...')
    da = load_daily_tmax(date_str)
    print(f'[load] Grid: {dict(da.sizes)}\n')

    results = []

    for label, iso3, bbox, special in CANDIDATES:
        try:
            mask = _build_mask(da, iso3, bbox, special)
            n_cells = int(mask.values.sum())
            if n_cells == 0:
                print(f'  [!] {label:<16} SKIP — 0 cells in mask')
                continue

            country_max_c = float(da.where(mask).max().values)
            # planet_fraction_hotter already returns %, do NOT multiply again
            frac_pct = planet_fraction_hotter(da, country_max_c)

            passes = frac_pct < target_pct
            results.append({
                'label':    label,
                'iso3':     iso3,
                'max_c':    country_max_c,
                'frac_pct': frac_pct,
                'n_cells':  n_cells,
                'passes':   passes,
            })
            tick = '✓' if passes else ' '
            print(f'  [{tick}] {label:<16} max={country_max_c:>5.2f} °C  '
                  f'hotter={frac_pct:>6.3f}%  cells={n_cells}')
        except Exception as e:
            print(f'  [!] {label:<16} ERROR: {e}')

    if not results:
        print('\nNo results — check GRIB download and shapefile cache.')
        return [], None

    # Sort ascending by planet fraction (hottest → smallest fraction)
    results.sort(key=lambda r: r['frac_pct'])

    print(f'\n{"=" * 72}')
    print('RANKED TABLE  (ascending fraction = hottest reference countries first)')
    print(f'{"─" * 72}')
    hdr = f'  {"":1} {"Country":<16} {"Max °C":>7}  {"Hotter %":>9}  {"Passes?":>8}  {"Cells":>6}'
    print(hdr)
    print(f'  {"─"*16}  {"─"*7}  {"─"*9}  {"─"*8}  {"─"*6}')

    passing = [r for r in results if r['passes']]
    # "extreme"   = hottest (smallest fraction, first in sorted list)
    # "editorial" = most relatable (largest fraction still below target = last passing)
    extreme   = passing[0]  if passing else None
    editorial = passing[-1] if passing else None

    for r in results:
        flag = ''
        if r is editorial and r is extreme:
            flag = '← WINNER'
        elif r is editorial:
            flag = '← EDITORIAL'
        elif r is extreme:
            flag = '← EXTREME'
        tick = '✓' if r['passes'] else ' '
        print(
            f'  [{tick}] {r["label"]:<16} {r["max_c"]:>7.2f}  {r["frac_pct"]:>8.3f}%'
            f'  {"yes" if r["passes"] else "no":>8}  {r["n_cells"]:>6}  {flag}'
        )

    print(f'{"─" * 72}')

    if passing:
        print(f'\n  {len(passing)} candidate(s) pass the < {target_pct:.1f}% filter.')
        if editorial is not extreme:
            print(f'\nExtreme   →  {extreme["label"]} ({extreme["iso3"]})')
            print(f'  Max: {extreme["max_c"]:.2f} °C  |  Planet hotter: {extreme["frac_pct"]:.3f}%')
            print(f'  (hottest of all candidates — least of the planet beats it)')
            print(f'\nEditorial →  {editorial["label"]} ({editorial["iso3"]})')
            print(f'  Max: {editorial["max_c"]:.2f} °C  |  Planet hotter: {editorial["frac_pct"]:.3f}%')
            print(f'  (most relatable country still below the {target_pct:.1f}% threshold)')
            print(f'  → "{editorial["frac_pct"]:.2f}% of the globe is strictly hotter '
                  f'than {editorial["label"]}\'s hottest point today."')
        else:
            print(f'\nWinner  →  {editorial["label"]} ({editorial["iso3"]})')
            print(f'  Max: {editorial["max_c"]:.2f} °C  |  Planet hotter: {editorial["frac_pct"]:.3f}%')
    else:
        closest = results[0]
        print(f'\n  No candidate passes < {target_pct:.1f}% today.')
        print(f'  Closest: {closest["label"]} at {closest["frac_pct"]:.3f}%.')
        print(f'  Try --target {closest["frac_pct"]:.2f} to capture it.')

    print(f'\n{"=" * 72}')
    return results, editorial


if __name__ == '__main__':
    results, editorial = main()
    sys.exit(0)
