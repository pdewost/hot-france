"""
render_date.py — Fetch IFS data and render maps for a single date.

Usage:
  python scripts/render_date.py 2026-06-25

Outputs (4 PNGs, no HTML changes, no git push):
  outputs/hotter_than_france_<date>_<theme>_<lang>.png
  site/assets/maps/hotter_than_france_<date>_<theme>_<lang>.png
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.render.wapo_map import render_map

THEMES = ['dark', 'light']
LANGS  = ['en', 'fr']

_OUTPUTS_DIR   = _PROJECT_ROOT / 'outputs'
_SITE_MAPS_DIR = _PROJECT_ROOT / 'assets' / 'maps'


def main(date_str: str):
    print('=' * 72)
    print(f'Hotter-Than-France — single-date render: {date_str}')
    print(f'Variants: {len(THEMES) * len(LANGS)} (themes × langs)')
    print('=' * 72)

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)

    results = []

    for theme in THEMES:
        for lang in LANGS:
            fname = f'hotter_than_france_{date_str}_{theme}_{lang}.png'
            out1  = _OUTPUTS_DIR   / fname
            out2  = _SITE_MAPS_DIR / fname

            print(f'\n[render] {date_str} / {theme} / {lang} ...')
            info = render_map(date_str, theme, lang, out1)
            shutil.copy2(str(out1), str(out2))

            print(f'  → {out1.name}')
            print(f'  threshold  : {info["threshold_c"]:.2f} °C')
            print(f'  france_min : {info["france_min_c"]:.2f} °C')
            print(f'  crosshair  : {info["crosshair_lat"]:.4f} N, {info["crosshair_lon"]:.4f} E')
            print(f'  hot cell % : {info["hot_cell_pct"]:.3f}%')
            print(f'  size       : {info["width"]} × {info["height"]} px')

            results.append({'date': date_str, 'theme': theme, 'lang': lang, **info})

    print(f'\n{"=" * 72}')
    print('SUMMARY')
    print(f'{"─" * 72}')
    for r in results:
        print(
            f'{r["date"]} {r["theme"]:<6} {r["lang"]}  '
            f'thr={r["threshold_c"]:.2f} °C  '
            f'hot={r["hot_cell_pct"]:.3f}%'
        )
    print(f'{"─" * 72}')
    print(f'\nDone — {len(results)} files written (not pushed).')
    return results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: python scripts/render_date.py YYYY-MM-DD', file=sys.stderr)
        sys.exit(1)
    main(sys.argv[1])
