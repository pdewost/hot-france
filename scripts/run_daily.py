"""
run_daily.py — Daily pipeline: discover editorial reference country, render 4 maps.

Combines discover_today + render_date into a single command.

Usage:
  python scripts/run_daily.py              # today
  python scripts/run_daily.py 2026-06-26  # specific date
  python scripts/run_daily.py 2026-06-26 --target 1.0

Steps:
  1. Fetch (or cache-hit) IFS grid for the date
  2. Discover editorial reference country (coolest candidate below target %)
  3. Render 4 maps (dark/light × EN/FR) into outputs/ and assets/maps/
  4. Print the DATA entry to paste into site/index.html

Maps are named: hotter_than_{iso3}_{date}_{theme}_{lang}.png
"""
from __future__ import annotations

import sys
import shutil
import argparse
from pathlib import Path
from datetime import date as _date

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.loaders.ecmwf_opendata import load_daily_tmax
from src.render.wapo_map import render_map
from scripts.discover_today import discover, CANDIDATES  # noqa: E402

_OUTPUTS_DIR   = _PROJECT_ROOT / 'outputs'
_SITE_MAPS_DIR = _PROJECT_ROOT / 'assets' / 'maps'

def _flag_emoji(iso2: str) -> str:
    if not iso2: return ''
    return ''.join(chr(ord(c) + 127397) for c in iso2.upper())

THEMES = ['dark', 'light']
LANGS  = ['en', 'fr']

# Day-of-week labels for the DATA entry
_DAYS_EN   = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
_MONTHS_EN = ['June','July','August','September','October','November','December',
               'January','February','March','April','May']  # unused, kept for clarity
_DAYS_FR   = ['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche']
_MONTHS_FR = ['janvier','février','mars','avril','mai','juin','juillet',
               'août','septembre','octobre','novembre','décembre']
_MONTHS_LONG_EN = ['January','February','March','April','May','June','July',
                   'August','September','October','November','December']


def _day_labels(date_str: str):
    d = _date.fromisoformat(date_str)
    en = f"{_DAYS_EN[d.weekday()]} {d.day} {_MONTHS_LONG_EN[d.month-1]}"
    fr = f"{_DAYS_FR[d.weekday()]} {d.day} {_MONTHS_FR[d.month-1]}"
    return en, fr


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('date', nargs='?', default=str(_date.today()),
                        help='Date YYYY-MM-DD (default: today)')
    parser.add_argument('--target', type=float, default=0.8,
                        help='Planet-fraction target %% for discovery (default: 0.8)')
    args = parser.parse_args()

    date_str   = args.date
    target_pct = args.target

    print('=' * 72)
    print(f'Hotter-Than-[Country] daily pipeline  |  {date_str}')
    print('=' * 72)

    # ------------------------------------------------------------------
    # 1. Load grid
    # ------------------------------------------------------------------
    print(f'\n[1/3] Loading IFS grid for {date_str} ...')
    da = load_daily_tmax(date_str)
    print(f'      Grid: {dict(da.sizes)}')

    # ------------------------------------------------------------------
    # 2. Discover editorial country
    # ------------------------------------------------------------------
    print(f'\n[2/3] Discovering reference country (target < {target_pct:.1f}%) ...')
    results, extreme, editorial = discover(da, target_pct, CANDIDATES)

    if not results:
        print('  ERROR: discovery returned no results. Check GRIB + shapefiles.')
        sys.exit(1)

    passing = [r for r in results if r['passes']]
    print(f'  {len(passing)} candidate(s) pass < {target_pct:.1f}%')

    if editorial:
        ref = editorial
        print(f'  → Editorial: {ref["label_en"]} ({ref["iso3"].upper()})  '
              f'max={ref["max_c"]:.2f} °C  hotter={ref["frac_pct"]:.3f}%')
    else:
        # Fallback: use the closest candidate
        ref = results[0]
        print(f'  ⚠ No candidate passes {target_pct:.1f}%. Using closest: '
              f'{ref["label_en"]} ({ref["frac_pct"]:.3f}%)')
        print(f'  Consider --target {ref["frac_pct"] + 0.05:.2f} to include it.')

    # France comparison stats (always computed when France is not the editorial pick)
    fra_stats = None
    if ref['iso3'] != 'fra':
        fra_stats = next((r for r in results if r['iso3'] == 'fra'), None)
        if fra_stats:
            print(f'  → France that day: {fra_stats["max_c"]:.2f} °C  '
                  f'hotter={fra_stats["frac_pct"]:.3f}%')

    # ------------------------------------------------------------------
    # 3. Render 4 maps
    # ------------------------------------------------------------------
    print(f'\n[3/3] Rendering 4 maps for {ref["label_en"]} ...')
    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)

    render_results = []
    for theme in THEMES:
        for lang in LANGS:
            iso3 = ref['iso3']  # already lowercased
            fname = f'hotter_than_{iso3}_{date_str}_{theme}_{lang}.png'
            out1  = _OUTPUTS_DIR   / fname
            out2  = _SITE_MAPS_DIR / fname

            print(f'  [render] {theme}/{lang} → {fname}')
            info = render_map(
                date_str, theme, lang, out1,
                ref_iso3=ref['iso3'].upper(),
                ref_bbox=ref['bbox'],
                ref_label_en=ref['label_en'],
                ref_label_fr=ref['label_fr'],
                ref_flag=_flag_emoji(ref.get('iso2', '')),
            )
            shutil.copy2(str(out1), str(out2))
            render_results.append({**ref, **info, 'theme': theme, 'lang': lang})
            print(f'         thr={info["threshold_c"]:.2f} °C  '
                  f'hot={info["hot_cell_pct"]:.3f}%  '
                  f'{info["width"]}×{info["height"]}')

    # ------------------------------------------------------------------
    # Summary + DATA entry for index.html
    # ------------------------------------------------------------------
    en_day, fr_day = _day_labels(date_str)
    r0 = render_results[0]  # any variant — stats are the same

    print(f'\n{"=" * 72}')
    print('DATA entry to add to index.html:')
    print(f'{"─" * 72}')
    fra_part = (
        f" fraMaxC:{fra_stats['max_c']:.1f}, fraPct:{fra_stats['frac_pct']:.2f},"
        if fra_stats else ''
    )
    label_fr_js = ref['label_fr'].replace("'", "\\'")
    print(
        f"  {{date:'{date_str}', "
        f"enDay:'{en_day}', frDay:'{fr_day}', "
        f"refIso3:'{ref['iso3']}', "
        f"refEn:'{ref['label_en']}', refFr:'{label_fr_js}', "
        f"iso2:'{ref['iso2']}', "
        f"refMaxC:{r0['threshold_c']},{fra_part} "
        f"planetPct:{round(ref['frac_pct'], 2)}}}"
    )
    print(f'{"─" * 72}')
    print(f'\nMaps in assets/maps/ and outputs/ (not pushed).')
    print(f'{"=" * 72}')

    return render_results, ref


if __name__ == '__main__':
    main()
