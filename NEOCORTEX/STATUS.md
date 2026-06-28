# Hotter-Than-France — Status
*Last updated: 2026-06-27*

## What this project is
Reproduce Ben Noll's WaPo "ECMWF-based" world map shading **only the places on Earth hotter than the hottest point in Continental Europe** during the June 2026 heatwave. Output: a reproducible Python pipeline + WaPo-style maps + a live bilingual web page updated daily.

## Current phase
**DELIVERED + PUBLISHED + ACTIVELY UPDATED** — first shipped 2026-06-25.

Live at **pdewost.github.io/hot-france** (GitHub Pages, branch `main`, repo root).

Data coverage: **Mon 22 Jun → Sat 27 Jun 2026** (6 days, 24 maps).

| Date | Ref country | Max °C | Planet % hotter |
|------|-------------|--------|-----------------|
| Mon 22 | Spain  | 42.31 | 0.84% |
| Tue 23 | Spain  | 43.85 | 0.34% |
| Wed 24 | France | 42.04 | 0.76% |
| Thu 25 | France | 40.15 | 1.70% |
| Fri 26 | Germany | 38.86 | 2.26% |
| Sat 27 | Germany | 39.87 | 1.82% |

## Architecture

- **Pipeline:** `.venv/bin/python scripts/run_daily.py YYYY-MM-DD`
  Downloads GRIB2 (ECMWF IFS `oper`, param `mx2t3`, steps 3–24, google mirror) → discovers EU reference country → renders 4 maps (dark/light × EN/FR). Prints a ready-to-paste DATA entry for `index.html`.
- **EU-scope framing:** Reference = hottest Continental European country each day (no threshold). Non-EU countries appear as heat cells but are never the reference. France always shown as secondary overlay when not hottest.
- **Page:** `index.html` at repo root (no `site/` subdirectory). `var DATA=[...]` inline array drives the displayed day, title, stats. `var STRINGS={en:{...}, fr:{...}}` for i18n. Theme+lang toggles persist in localStorage.
- **Maps:** `assets/maps/hotter_than_{iso3}_{date}_{theme}_{lang}.png`
- **Flags:** Twemoji PNGs in `assets/flags/`, composited at NW corner of country polygon (outside, upper-left) with white semi-transparent card backing.
- **Favicon:** thermometer icon, `favicon-32.png` + `favicon-16.png` + `favicon.ico`; HTML uses `?v=4` cache-buster.
- **Preview server:** `.claude/launch.json` at Design Projects level, port 8051, serves project root.

## Invariants
1. **Data = ECMWF IFS forecast (`oper`, `mx2t3`)** — NOT ERA5 (lags 5 days+, wrong product).
2. **France = metropolitan only** (Natural Earth `FRA` includes overseas DOM → corrupts threshold).
3. **Provenance honesty** — page captions source/variable/threshold; never claims to be the WaPo original.
4. **Calibration:** Mon 22 = 1.145% planet hotter vs Noll's ~1.2% ✅.
5. **JS safety:** straight double quotes only in `<script>` blocks; inner `"` must be `\"`. Smart/curly quotes (U+201C/U+201D) are invalid JS tokens — caused a full-page outage 2026-06-27.
6. **`~/.cdsapirc` never committed.**
7. **`source='google'`** (AWS mirror throttles downloads).

## Next actions (all optional)
1. **Daily update:** run `.venv/bin/python scripts/run_daily.py YYYY-MM-DD`, paste DATA entry into `index.html`, commit+push maps and page.
2. **Phase 5 (~29 Jun+):** ERA5 backfill via CDS once ERA5T covers 22–24 Jun; forecast-vs-reanalysis diff.
3. **IFS sub-product:** used `oper`; confirm HRES/ENS/AIFS with Ben Noll (@BenNollWeather) if desired.

## Done log
- 2026-06-25: scaffold; adversarial source-workflow challenge (verified); Phase 0 probe; Phase 1 loader; Phase 2 mask+threshold+calibration (1.145% ✅); Phase 3 render (6 maps); bilingual dark/light page (`site/index.html`); CALIBRATION.md; published to GitHub Pages.
- 2026-06-27: EU-scoped reference refactor; country flags on maps; methodology text updated (EN+FR); 3 JS parse errors fixed (smart quotes + unescaped inner quotes); favicon cache-buster ?v=4; Design Projects launch.json `site/` bug fixed; Jun 26 + Jun 27 data added; page moved from `site/` to repo root.

## Pointers
- Brief: `PROJECT_BRIEF.md`
- Calibration record: `CALIBRATION.md`
- Plan (partially stale — core delivered): `PLAN_reproduction_2026-06-25.md`
- Loader API: `from src.loaders.ecmwf_opendata import load_daily_tmax`
- Render API: `from src.render.wapo_map import render_wapo_map`
- Gotcha: cartopy NE shapefiles pre-fetched via certifi → `~/.local/share/cartopy/` (no re-download needed)
