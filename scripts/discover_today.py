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
# Candidate list: (label_en, iso3, bbox_or_None, special_or_None, label_fr)
# bbox   = (lon_min, lat_min, lon_max, lat_max) — clips overseas territories
# special= 'france' uses the dedicated metropolitan_france_mask (more precise)
# label_fr includes the definite article (used in map burnt-in text)
# ---------------------------------------------------------------------------
CANDIDATES = [
    # ── Continental Europe + UK (scope='europe') — eligible as daily map reference ──
    ('France',       'FRA', None,             'france', 'la France',               'europe'),
    ('Spain',        'ESP', (-10,35, 5,45),   None,     "l'Espagne",               'europe'),
    ('Portugal',     'PRT', (-10,36,-6,42),   None,     'le Portugal',             'europe'),
    ('Italy',        'ITA', (  6,36,19,48),   None,     "l'Italie",                'europe'),
    ('Greece',       'GRC', ( 19,34,30,42),   None,     'la Grèce',                'europe'),
    ('Germany',      'DEU', None,             None,     "l'Allemagne",             'europe'),
    ('Austria',      'AUT', None,             None,     "l'Autriche",              'europe'),
    ('Switzerland',  'CHE', None,             None,     'la Suisse',               'europe'),
    ('Hungary',      'HUN', None,             None,     'la Hongrie',              'europe'),
    ('Romania',      'ROU', None,             None,     'la Roumanie',             'europe'),
    ('UK',           'GBR', ( -8,49, 2,62),   None,     'le Royaume-Uni',          'europe'),
    ('Bulgaria',     'BGR', None,             None,     'la Bulgarie',             'europe'),
    ('Serbia',       'SRB', None,             None,     'la Serbie',               'europe'),
    # ── Global context (scope='global') — appear on map as hot cells; never map reference ──
    ('Turkey',       'TUR', ( 25,35,45,43),   None,     'la Turquie',              'global'),
    ('Morocco',      'MAR', None,             None,     'le Maroc',                'global'),
    ('Algeria',      'DZA', None,             None,     "l'Algérie",               'global'),
    ('Tunisia',      'TUN', None,             None,     'la Tunisie',              'global'),
    ('Libya',        'LBY', None,             None,     'la Libye',                'global'),
    ('Egypt',        'EGY', None,             None,     "l'Égypte",                'global'),
    ('Israel',       'ISR', None,             None,     'Israël',                  'global'),
    ('Jordan',       'JOR', None,             None,     'la Jordanie',             'global'),
    ('Saudi Arabia', 'SAU', None,             None,     "l'Arabie Saoudite",       'global'),
    ('Iraq',         'IRQ', (38, 29, 49, 38), None,     "l'Irak",                  'global'),
    ('Kuwait',       'KWT', None,             None,     'le Koweït',               'global'),
    ('UAE',          'ARE', (51, 22, 57, 26), None,     'les Émirats arabes unis', 'global'),
    ('Iran',         'IRN', None,             None,     "l'Iran",                  'global'),
    ('Mauritania',   'MRT', None,             None,     'la Mauritanie',           'global'),
    ('India',        'IND', (68,  6, 97, 36), None,     "l'Inde",                  'global'),
    ('Pakistan',     'PAK', (60, 23, 78, 37), None,     'le Pakistan',             'global'),
]

ISO3_TO_ISO2 = {
    'FRA':'FR','ESP':'ES','PRT':'PT','ITA':'IT','GRC':'GR',
    'DEU':'DE','AUT':'AT','CHE':'CH','HUN':'HU','ROU':'RO',
    'GBR':'GB','TUR':'TR','BGR':'BG','SRB':'RS',
    'MAR':'MA','DZA':'DZ','TUN':'TN','LBY':'LY','EGY':'EG',
    'ISR':'IL','JOR':'JO','SAU':'SA',
    'IRQ':'IQ','KWT':'KW','ARE':'AE','IRN':'IR',
    'MRT':'MR',
    'IND':'IN','PAK':'PK',
}


def _build_mask(da, iso3, bbox, special):
    if special == 'france':
        return metropolitan_france_mask(da, verbose=False)
    return country_mask(da, iso3, bbox)


def discover(da, target_pct: float = 0.8, candidates=None):
    """Run the ranking loop on a preloaded DataArray.

    Parameters
    ----------
    da : xr.DataArray
        Normalized daily-max temperature grid (°C, lat/lon).
    target_pct : float
        Planet-fraction threshold in percent (default 0.8 — kept for display only).
    candidates : list or None
        Override CANDIDATES list; defaults to module-level CANDIDATES.

    Returns
    -------
    results    : list of dicts (sorted ascending by frac_pct)
    extreme    : dict — globally hottest candidate (smallest fraction overall)
    editorial  : dict — most relatable candidate still below target_pct (legacy)
    europe_ref : dict — hottest Continental European country (map reference)
    """
    if candidates is None:
        candidates = CANDIDATES

    results = []
    for label_en, iso3, bbox, special, label_fr, scope in candidates:
        try:
            mask    = _build_mask(da, iso3, bbox, special)
            n_cells = int(mask.values.sum())
            if n_cells == 0:
                continue
            country_max_c = float(da.where(mask).max().values)
            frac_pct      = planet_fraction_hotter(da, country_max_c)
            results.append({
                'label_en': label_en,
                'label_fr': label_fr,
                'iso3':     iso3.lower(),
                'iso2':     ISO3_TO_ISO2.get(iso3, ''),
                'bbox':     bbox,
                'special':  special,
                'scope':    scope,
                'max_c':    country_max_c,
                'frac_pct': frac_pct,
                'n_cells':  n_cells,
                'passes':   frac_pct < target_pct,
            })
        except Exception:
            pass

    results.sort(key=lambda r: r['frac_pct'])
    passing  = [r for r in results if r['passes']]
    extreme  = passing[0]  if passing else None
    editorial = passing[-1] if passing else None

    # EU-scoped reference: hottest European country, no threshold
    eu_results = [r for r in results if r['scope'] == 'europe']
    europe_ref = eu_results[0] if eu_results else None  # already sorted ascending by frac_pct

    return results, extreme, editorial, europe_ref


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

    # Print progress line-by-line while running the ranking
    for label_en, iso3, bbox, special, label_fr, scope in CANDIDATES:
        try:
            mask    = _build_mask(da, iso3, bbox, special)
            n_cells = int(mask.values.sum())
            if n_cells == 0:
                print(f'  [!] {label_en:<16} SKIP — 0 cells in mask')
                continue
            country_max_c = float(da.where(mask).max().values)
            frac_pct      = planet_fraction_hotter(da, country_max_c)
            passes        = frac_pct < target_pct
            tick = '✓' if passes else ' '
            print(f'  [{tick}] {label_en:<16} max={country_max_c:>5.2f} °C  '
                  f'hotter={frac_pct:>6.3f}%  cells={n_cells}')
        except Exception as e:
            print(f'  [!] {label_en:<16} ERROR: {e}')

    # Full structured run via discover()
    results, extreme, editorial, europe_ref = discover(da, target_pct)

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
            f'  [{tick}] {r["label_en"]:<16} {r["max_c"]:>7.2f}  {r["frac_pct"]:>8.3f}%'
            f'  {"yes" if r["passes"] else "no":>8}  {r["n_cells"]:>6}  {flag}'
        )

    print(f'{"─" * 72}')

    if passing:
        print(f'\n  {len(passing)} candidate(s) pass the < {target_pct:.1f}% filter.')
        if editorial is not extreme:
            print(f'\nExtreme (global)  →  {extreme["label_en"]} ({extreme["iso3"].upper()})')
            print(f'  Max: {extreme["max_c"]:.2f} °C  |  Planet hotter: {extreme["frac_pct"]:.3f}%')
            print(f'\nEditorial (legacy)→  {editorial["label_en"]} ({editorial["iso3"].upper()})')
            print(f'  Max: {editorial["max_c"]:.2f} °C  |  Planet hotter: {editorial["frac_pct"]:.3f}%')
        else:
            print(f'\nExtreme (global)  →  {extreme["label_en"]} ({extreme["iso3"].upper()})')
            print(f'  Max: {extreme["max_c"]:.2f} °C  |  Planet hotter: {extreme["frac_pct"]:.3f}%')
    else:
        print(f'\n  No global candidate passes < {target_pct:.1f}% today.')

    if europe_ref:
        print(f'\nEurope ref (MAP)  →  {europe_ref["label_en"]} ({europe_ref["iso3"].upper()})')
        print(f'  Max: {europe_ref["max_c"]:.2f} °C  |  Planet hotter: {europe_ref["frac_pct"]:.3f}%')
        print(f'  → "{europe_ref["frac_pct"]:.2f}% of Earth is strictly hotter than '
              f'{europe_ref["label_en"]}\'s hottest point today."')

    print(f'\n{"=" * 72}')
    return results, europe_ref  # europe_ref = actual map reference


if __name__ == '__main__':
    main()
    sys.exit(0)
