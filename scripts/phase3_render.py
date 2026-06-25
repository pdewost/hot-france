"""
phase3_render.py — Phase 3: render WaPo-style world maps for Hotter-Than-France.

Produces 6 PNG files (3 dates × 2 themes) in two locations each:
  outputs/hotter_than_france_<date>_<theme>.png
  site/assets/maps/hotter_than_france_<date>_<theme>.png

Sanity checks:
  - 6 files produced
  - Each image ~1600×900 (16:9)
  - Hot overlay non-empty, single-digit % of total pixels
  - Dark/light differ in background

Usage:
  python scripts/phase3_render.py
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.render.wapo_map import render_map

DATES = ['2026-06-22', '2026-06-23', '2026-06-24']
THEMES = ['dark', 'light']

_OUTPUTS_DIR = _PROJECT_ROOT / 'outputs'
_SITE_MAPS_DIR = _PROJECT_ROOT / 'site' / 'assets' / 'maps'


def _filename(date_str: str, theme: str) -> str:
    return f"hotter_than_france_{date_str}_{theme}.png"


def main():
    print('=' * 72)
    print('Hotter-Than-France — Phase 3 Render')
    print(f'Dates: {", ".join(DATES)}')
    print(f'Themes: {", ".join(THEMES)}')
    print('=' * 72)

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    issues = []

    for date in DATES:
        for theme in THEMES:
            fname = _filename(date, theme)
            out1 = _OUTPUTS_DIR / fname
            out2 = _SITE_MAPS_DIR / fname

            print(f'\n[render] {date} / {theme} ...')
            info = render_map(date, theme, out1)

            # Copy to site/assets/maps/
            import shutil
            shutil.copy2(str(out1), str(out2))

            print(f'  → {out1}')
            print(f'  → {out2}')
            print(f'  threshold : {info["threshold_c"]:.2f} °C')
            print(f'  size      : {info["width"]} × {info["height"]} px')
            print(f'  hot cell %: {info["hot_cell_pct"]:.3f}%  (unweighted grid-cell proxy)')

            results.append({
                'date': date,
                'theme': theme,
                'path_outputs': str(out1),
                'path_site': str(out2),
                **info,
            })

    # ------------------------------------------------------------------
    # Sanity checks
    # ------------------------------------------------------------------
    print(f'\n{"=" * 72}')
    print('SANITY CHECKS')
    print(f'{"─" * 72}')

    # 1. File count
    if len(results) == 6:
        print(f'[PASS] 6 files produced')
    else:
        msg = f'[FAIL] Expected 6 files, got {len(results)}'
        print(msg)
        issues.append(msg)

    for r in results:
        label = f'{r["date"]} / {r["theme"]}'

        # 2. Dimensions ~1600×900
        w, h = r['width'], r['height']
        if 1550 <= w <= 1650 and 870 <= h <= 930:
            print(f'[PASS] {label}: {w}×{h} (expected ~1600×900)')
        else:
            msg = f'[FAIL] {label}: unexpected size {w}×{h}'
            print(msg)
            issues.append(msg)

        # 3. Hot overlay non-empty
        pct = r['hot_cell_pct']
        if pct == 0.0:
            msg = f'[FAIL] {label}: hot overlay is EMPTY (0% hot pixels) — check threshold logic'
            print(msg)
            issues.append(msg)
        elif pct > 15.0:
            msg = f'[FAIL] {label}: hot overlay covers {pct:.2f}% — unexpectedly large (>15%)'
            print(msg)
            issues.append(msg)
        else:
            print(f'[PASS] {label}: hot overlay {pct:.3f}% (sanity: 0<x<15)')

    # 4. Dark vs light differ
    from PIL import Image
    dark_res = next((r for r in results if r['theme'] == 'dark' and r['date'] == DATES[0]), None)
    light_res = next((r for r in results if r['theme'] == 'light' and r['date'] == DATES[0]), None)
    if dark_res and light_res:
        import numpy as np
        d_img = np.array(Image.open(dark_res['path_outputs']).convert('RGB'))
        l_img = np.array(Image.open(light_res['path_outputs']).convert('RGB'))
        mean_diff = float(np.abs(d_img.astype(int) - l_img.astype(int)).mean())
        if mean_diff > 20:
            print(f'[PASS] dark vs light differ meaningfully (mean pixel diff {mean_diff:.1f})')
        else:
            msg = f'[FAIL] dark vs light barely differ (mean pixel diff {mean_diff:.1f} — check theme application)'
            print(msg)
            issues.append(msg)

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    print(f'\n{"=" * 72}')
    print('SUMMARY')
    print(f'{"─" * 72}')
    hdr = f'{"Date":<12} {"Theme":<7} {"Threshold °C":>13} {"Size":>12} {"Hot %":>8}'
    print(hdr)
    print(f'{"─" * 72}')
    for r in results:
        print(
            f'{r["date"]:<12} {r["theme"]:<7} {r["threshold_c"]:>13.2f} '
            f'{r["width"]}×{r["height"]:>4} {r["hot_cell_pct"]:>8.3f}%'
        )
    print(f'{"─" * 72}')

    if issues:
        print(f'\n⚠  {len(issues)} issue(s) detected:')
        for iss in issues:
            print(f'   • {iss}')
    else:
        print('\nAll sanity checks passed.')

    print(f'\n{"=" * 72}')
    return results, issues


if __name__ == '__main__':
    results, issues = main()
    if issues:
        sys.exit(1)
