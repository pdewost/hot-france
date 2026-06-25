"""
phase3_render.py — Phase 3: render WaPo-style world maps for Hotter-Than-France.

Produces 12 PNG files (3 dates × 2 themes × 2 langs) in two locations each:
  outputs/hotter_than_france_<date>_<theme>_<lang>.png
  site/assets/maps/hotter_than_france_<date>_<theme>_<lang>.png

Old 6 non-lang files (hotter_than_france_<date>_<theme>.png) are deleted from
both directories if they exist, to eliminate stale orphans.

Sanity checks:
  - 12 files produced
  - Each image ~1600×900 (16:9)
  - Hot overlay non-empty, <15% of grid cells
  - Dark/light differ in background
  - en vs fr of same date+theme are identical in the map region but differ in text bands

Usage:
  python scripts/phase3_render.py
"""
from __future__ import annotations

import sys
import os
import shutil
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.render.wapo_map import render_map

DATES  = ['2026-06-22', '2026-06-23', '2026-06-24']
THEMES = ['dark', 'light']
LANGS  = ['en', 'fr']

_OUTPUTS_DIR  = _PROJECT_ROOT / 'outputs'
_SITE_MAPS_DIR = _PROJECT_ROOT / 'site' / 'assets' / 'maps'


def _filename(date_str: str, theme: str, lang: str) -> str:
    return f"hotter_than_france_{date_str}_{theme}_{lang}.png"


def _old_filename(date_str: str, theme: str) -> str:
    """Filename pattern used before lang dimension was added."""
    return f"hotter_than_france_{date_str}_{theme}.png"


def _delete_old_files():
    """Remove pre-lang orphan files from both output directories."""
    removed = []
    for date in DATES:
        for theme in THEMES:
            fname = _old_filename(date, theme)
            for d in (_OUTPUTS_DIR, _SITE_MAPS_DIR):
                p = d / fname
                if p.exists():
                    p.unlink()
                    removed.append(str(p))
    return removed


def main():
    print('=' * 72)
    print('Hotter-Than-France — Phase 3 Render (with lang dimension)')
    print(f'Dates  : {", ".join(DATES)}')
    print(f'Themes : {", ".join(THEMES)}')
    print(f'Langs  : {", ".join(LANGS)}')
    print(f'Total  : {len(DATES) * len(THEMES) * len(LANGS)} files')
    print('=' * 72)

    _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    _SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Delete stale orphan files (old format, no lang suffix)
    # ------------------------------------------------------------------
    removed = _delete_old_files()
    if removed:
        print(f'\nDeleted {len(removed)} stale pre-lang file(s):')
        for p in removed:
            print(f'  {p}')
    else:
        print('\nNo stale pre-lang files to delete.')

    results = []
    issues  = []

    for date in DATES:
        for theme in THEMES:
            for lang in LANGS:
                fname = _filename(date, theme, lang)
                out1  = _OUTPUTS_DIR  / fname
                out2  = _SITE_MAPS_DIR / fname

                print(f'\n[render] {date} / {theme} / {lang} ...')
                info = render_map(date, theme, lang, out1)

                # Copy to site/assets/maps/
                shutil.copy2(str(out1), str(out2))

                print(f'  → {out1}')
                print(f'  → {out2}')
                print(f'  threshold    : {info["threshold_c"]:.2f} °C')
                print(f'  france_min   : {info["france_min_c"]:.2f} °C')
                print(f'  crosshair    : lat {info["crosshair_lat"]:.4f}, lon {info["crosshair_lon"]:.4f}')
                print(f'  size         : {info["width"]} × {info["height"]} px')
                print(f'  hot cell %   : {info["hot_cell_pct"]:.3f}%  (unweighted grid-cell proxy)')

                results.append({
                    'date': date,
                    'theme': theme,
                    'lang': lang,
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
    if len(results) == 12:
        print('[PASS] 12 files produced')
    else:
        msg = f'[FAIL] Expected 12 files, got {len(results)}'
        print(msg)
        issues.append(msg)

    for r in results:
        label = f'{r["date"]} / {r["theme"]} / {r["lang"]}'

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
    import numpy as np

    dark_res  = next((r for r in results if r['theme'] == 'dark'  and r['date'] == DATES[0] and r['lang'] == 'en'), None)
    light_res = next((r for r in results if r['theme'] == 'light' and r['date'] == DATES[0] and r['lang'] == 'en'), None)
    if dark_res and light_res:
        d_img = np.array(Image.open(dark_res['path_outputs']).convert('RGB'))
        l_img = np.array(Image.open(light_res['path_outputs']).convert('RGB'))
        mean_diff = float(np.abs(d_img.astype(int) - l_img.astype(int)).mean())
        if mean_diff > 20:
            print(f'[PASS] dark vs light differ meaningfully (mean pixel diff {mean_diff:.1f})')
        else:
            msg = f'[FAIL] dark vs light barely differ (mean pixel diff {mean_diff:.1f} — check theme application)'
            print(msg)
            issues.append(msg)

    # 5. en vs fr: identical map area, different text bands
    #    Compare first date+theme pair: en and fr images should differ overall
    #    (text bands differ) but be identical in the central map strip (rows 90..810).
    en_res = next((r for r in results if r['theme'] == 'dark' and r['date'] == DATES[0] and r['lang'] == 'en'), None)
    fr_res = next((r for r in results if r['theme'] == 'dark' and r['date'] == DATES[0] and r['lang'] == 'fr'), None)
    if en_res and fr_res:
        en_img = np.array(Image.open(en_res['path_outputs']).convert('RGB'))
        fr_img = np.array(Image.open(fr_res['path_outputs']).convert('RGB'))
        # Central map strip (axes span rows ~90..810 of 900)
        map_slice  = slice(90, 810)
        text_top   = slice(0, 90)
        text_bot   = slice(810, 900)
        map_diff  = float(np.abs(en_img[map_slice].astype(int) - fr_img[map_slice].astype(int)).mean())
        text_diff = float(np.abs(
            np.concatenate([en_img[text_top], en_img[text_bot]]).astype(int)
            - np.concatenate([fr_img[text_top], fr_img[text_bot]]).astype(int)
        ).mean())
        if map_diff < 1.0:
            print(f'[PASS] en vs fr: map area identical (mean diff {map_diff:.3f} < 1)')
        else:
            msg = f'[FAIL] en vs fr: map area differs (mean diff {map_diff:.3f} — should be identical)'
            print(msg)
            issues.append(msg)
        if text_diff > 2.0:
            print(f'[PASS] en vs fr: text bands differ (mean diff {text_diff:.2f} > 2)')
        else:
            msg = f'[FAIL] en vs fr: text bands look the same (mean diff {text_diff:.2f} — check lang logic)'
            print(msg)
            issues.append(msg)

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    print(f'\n{"=" * 72}')
    print('SUMMARY')
    print(f'{"─" * 72}')
    hdr = f'{"Date":<12} {"Theme":<7} {"Lang":<5} {"Thr °C":>8} {"FrMin °C":>9} {"Size":>12} {"Hot%":>7}'
    print(hdr)
    print(f'{"─" * 72}')
    for r in results:
        print(
            f'{r["date"]:<12} {r["theme"]:<7} {r["lang"]:<5}'
            f'{r["threshold_c"]:>8.2f} {r["france_min_c"]:>9.2f}'
            f'  {r["width"]}×{r["height"]:<4} {r["hot_cell_pct"]:>7.3f}%'
        )
    print(f'{"─" * 72}')

    if issues:
        print(f'\n  {len(issues)} issue(s) detected:')
        for iss in issues:
            print(f'   - {iss}')
    else:
        print('\nAll sanity checks passed.')

    print(f'\n{"=" * 72}')
    return results, issues


if __name__ == '__main__':
    results, issues = main()
    if issues:
        sys.exit(1)
