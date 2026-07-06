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

Shared entry point
------------------
``process_day(date_str)`` runs steps 1–3 and returns a plain ``entry`` dict; the
windowed driver (scripts/run_window.py) reuses it so both scripts share ONE code path.
``format_entry(entry)`` renders that dict into the exact ``var DATA=[...]`` line
convention used in index.html.
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

from src.loaders.ecmwf_opendata import load_daily_tmax, today_utc
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


# ---------------------------------------------------------------------------
# Number formatting — mirror the hand-maintained DATA lines EXACTLY
# ---------------------------------------------------------------------------
def _num(x) -> str:
    """Format a float the way the existing DATA lines do: strip a trailing '.0'
    but keep genuine decimals (42.31 → '42.31', 41.5 → '41.5', 42.0 → '42')."""
    s = f"{float(x):.2f}".rstrip('0').rstrip('.')
    return s if s else '0'


def _js_str_double(s: str) -> str:
    """Emit a JS double-quoted string literal, escaping only " and backslash.
    Apostrophes stay literal — matching refFr:"l'Espagne" in index.html."""
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


# ---------------------------------------------------------------------------
# Shared pipeline: one day → entry dict (steps 1–3), and entry dict → DATA line
# ---------------------------------------------------------------------------
def process_day(date_str: str, target_pct: float = 0.8,
                render: bool = True, today=None) -> dict:
    """Run the full per-day pipeline and return a serialisable ``entry`` dict.

    Steps: load grid (future-date aware) → discover EU reference → optionally
    render the 4 maps. The returned dict carries everything ``format_entry`` needs
    plus ``fcst`` (1 when the grid came from an offset>0 forecast fetch).

    Parameters
    ----------
    date_str : str
        Target date 'YYYY-MM-DD'.
    target_pct : float
        Discovery display threshold (kept for parity; ranking is EU-scoped).
    render : bool
        When True (default) render + copy the 4 maps. run_window may pass True.
    today : datetime.date | str | None
        Reference "today" (UTC) forwarded to the loader for forecast offset.

    Returns
    -------
    entry : dict with keys:
        date, enDay, frDay, refIso3, refEn, refFr, iso2, refMaxC, planetPct,
        [fraMaxC, fraPct] (omitted when France is the reference), [fcst] (1 if forecast).
    """
    da = load_daily_tmax(date_str, today=today)
    is_forecast = bool(da.attrs.get('is_forecast', False))

    results, extreme, editorial, europe_ref = discover(da, target_pct, CANDIDATES)
    if not results:
        raise RuntimeError(f"discovery returned no results for {date_str} "
                           f"(check GRIB + shapefiles)")

    ref = europe_ref if europe_ref else results[0]

    # France comparison stats (only when France is not the reference)
    fra_stats = None
    if ref['iso3'] != 'fra':
        fra_stats = next((r for r in results if r['iso3'] == 'fra'), None)

    en_day, fr_day = _day_labels(date_str)

    # threshold_c (rendered map's ref max) — identical across variants. Fall back to the
    # discovery max_c when not rendering so run_window --dry-run / no-render still works.
    threshold_c = ref['max_c']
    render_results = []
    if render:
        _OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        _SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)
        for theme in THEMES:
            for lang in LANGS:
                iso3 = ref['iso3']
                fname = f'hotter_than_{iso3}_{date_str}_{theme}_{lang}.png'
                out1  = _OUTPUTS_DIR   / fname
                out2  = _SITE_MAPS_DIR / fname
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
        threshold_c = render_results[0]['threshold_c']

    entry: dict = {
        'date':      date_str,
        'enDay':     en_day,
        'frDay':     fr_day,
        'refIso3':   ref['iso3'],
        'refEn':     ref['label_en'],
        'refFr':     ref['label_fr'],
        'iso2':      ref['iso2'],
        'refMaxC':   round(float(threshold_c), 2),
        'planetPct': round(float(ref['frac_pct']), 2),
    }
    if fra_stats:
        entry['fraMaxC'] = round(float(fra_stats['max_c']), 2)
        entry['fraPct']  = round(float(fra_stats['frac_pct']), 2)
    if is_forecast:
        entry['fcst'] = 1

    # Stash render side-info (not serialised into the DATA line) for callers/logging.
    entry['_render_results'] = render_results
    entry['_ref'] = ref
    entry['_fra_stats'] = fra_stats
    return entry


def format_entry(entry: dict) -> str:
    """Render an ``entry`` dict as one ``var DATA=[...]`` line, mirroring index.html.

    Conventions (must match the hand-maintained lines):
      - keys unquoted, string values single-quoted EXCEPT refFr which is double-quoted
        so a French apostrophe (l'Espagne) needs no escaping;
      - when France is the reference, fraMaxC/fraPct are omitted;
      - numbers formatted via _num (trailing '.0' stripped, real decimals kept);
      - a forecast entry carries a trailing ``fcst:1``.
    """
    parts = [
        f"date:'{entry['date']}'",
        f"enDay:'{entry['enDay']}'",
        f"frDay:'{entry['frDay']}'",
        f"refIso3:'{entry['refIso3']}'",
        f"refEn:'{entry['refEn']}'",
        f"refFr:{_js_str_double(entry['refFr'])}",
        f"iso2:'{entry['iso2']}'",
        f"refMaxC:{_num(entry['refMaxC'])}",
    ]
    if 'fraMaxC' in entry and 'fraPct' in entry:
        parts.append(f"fraMaxC:{_num(entry['fraMaxC'])}")
        parts.append(f"fraPct:{_num(entry['fraPct'])}")
    parts.append(f"planetPct:{_num(entry['planetPct'])}")
    if entry.get('fcst'):
        parts.append("fcst:1")
    return "{" + ", ".join(parts) + "}"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('date', nargs='?', default=str(today_utc()),
                        help='Date YYYY-MM-DD (default: today UTC — matches the loader reference)')
    parser.add_argument('--target', type=float, default=0.8,
                        help='Planet-fraction target %% for discovery (default: 0.8)')
    args = parser.parse_args()

    date_str   = args.date
    target_pct = args.target

    print('=' * 72)
    print(f'Hotter-Than-[Country] daily pipeline  |  {date_str}')
    print('=' * 72)

    print(f'\n[1-3] Loading grid, discovering EU reference, rendering 4 maps for {date_str} ...')
    entry = process_day(date_str, target_pct, render=True)

    ref = entry['_ref']
    if entry.get('fcst'):
        print(f'  (forecast day — grid from an offset>0 fetch)')
    print(f'  → Europe ref: {ref["label_en"]} ({ref["iso3"].upper()})  '
          f'max={ref["max_c"]:.2f} °C  hotter={ref["frac_pct"]:.3f}%')
    fra_stats = entry.get('_fra_stats')
    if fra_stats:
        print(f'  → France that day: {fra_stats["max_c"]:.2f} °C  '
              f'hotter={fra_stats["frac_pct"]:.3f}%')
    for rr in entry['_render_results']:
        print(f'  [render] {rr["theme"]}/{rr["lang"]} → '
              f'hotter_than_{ref["iso3"]}_{date_str}_{rr["theme"]}_{rr["lang"]}.png  '
              f'thr={rr["threshold_c"]:.2f} °C  hot={rr["hot_cell_pct"]:.3f}%  '
              f'{rr["width"]}×{rr["height"]}')

    print(f'\n{"=" * 72}')
    print('DATA entry to add to index.html:')
    print(f'{"─" * 72}')
    print('  ' + format_entry(entry))
    print(f'{"─" * 72}')
    print(f'\nMaps in assets/maps/ and outputs/ (not pushed).')
    print(f'{"=" * 72}')

    return entry['_render_results'], ref


if __name__ == '__main__':
    main()
