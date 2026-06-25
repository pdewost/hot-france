# Hotter-Than-France — Status
*Last updated: 2026-06-25*

## What this project is
Reproduce — and be able to regenerate — Ben Noll's WaPo "ECMWF-based" world map that shades
**only the places on Earth hotter than France's hottest place** during the June 2026 heatwave
(target days: Mon 22, Tue 23, Wed 24 Jun). Output: a small reproducible Python pipeline + WaPo-style
maps, calibrated against Noll's quoted planet-fraction figures (~1.2% / 0.93%).

## Current phase
**Phase 2 COMPLETE — CALIBRATION VALIDATED** — 2026-06-25. Metropolitan-France mask (1033 cells, DOM-leak
check PASS) + single-cell threshold + cos-lat planet-fraction, built + independently verified (PASS, 0 bugs).
**Mon 22: 1.145% planet hotter vs Noll's 1.2% (Δ 0.055 pp) → methodology reproduced.** All-surface matches
Noll far better than land-only (3.96%) ⇒ Noll computed over the whole planet.
Per-day: Mon 41.53 °C/1.145% · Tue 42.10 °C/0.767% · Wed 42.04 °C/0.764%.
Next: **Phase 3** (render WaPo-style maps) → **Phase 4** (wire real numbers + maps into `site/` page).

## Invariants
1. **Data source = ECMWF IFS forecast (`oper`, param `mx2t3`), NOT ERA5** for these dates. ERA5/ERA5T
   lags ~5 days–2 months (no 22–24 Jun on 25 Jun) and the WaPo map is IFS forecast, not reanalysis.
   ECMWF AWS replica confirmed to hold all 3 dates. (CHALLENGE §2–§3 + NOTE_phase0, verified)
2. **France = metropolitan only** (incl. Corsica). Natural Earth `FRA` includes tropical overseas
   départements and corrupts the max threshold. (CHALLENGE §6, verified)
3. **Provenance honesty.** Every map captions its real source/variable/window/threshold; never imply it IS WaPo's graphic. (PROJECT_BRIEF safety #1)
4. **Calibration is quantitative**, not pixel-diff (original image is paywalled): reproduce Noll's ~1.2%/0.93% within tolerance.
5. **Faithful threshold = single hottest France cell** (matches "France's hottest place"); percentile is a labelled sensitivity variant only.

## Next actions
1. **Phase 3** — `src/render/wapo_map.py`: vectorized `where(t > france_max)` mask + WaPo-style world map
   (Cartopy Robinson, set_bad lightgray, fixed vmin/vmax, add_cyclic_point) per day → `outputs/*.png`.
   Honest caption (source/variable/threshold/window). Reuse `metropolitan_france_mask` + `france_threshold`.
2. **Phase 4** — copy chosen maps → `site/assets/maps/hotter_than_france_<date>.png`; wire the real numbers
   into the page DATA (Mon 41.53 °C/1.145% · Tue 42.10/0.767% · Wed 42.04/0.764%); write `outputs/CALIBRATION.md`.
3. **Page** — `site/index.html` (Apple-50 template adapted, FR/EN + dark/light) building now (wf w1oxl0p64).
4. Phase 5 (optional, ~29 Jun+) — ERA5 backfill via corrected CDS; forecast-vs-reanalysis diff.

✅ Done 2026-06-25: scaffold; source-workflow challenge (verified); Phase 0 probe (ECMWF IFS, mx2t3);
**Phase 1 loader**; **Phase 2 mask+threshold+calibration (1.145% vs 1.2% ✅)**; nested git repo.

## Pointers
- Source proposal (as pasted): `../GUIDELINES_source_workflow.md`
- Adversarial review (verified): `../CHALLENGE_extracted_workflow.md`
- Active plan: `PLAN_reproduction_2026-06-25.md`
- Brief: `../PROJECT_BRIEF.md`
- Cold-start read order: MANIFEST.json → STATUS.md → active plans
- Smoke test: `.venv/bin/python scripts/phase1_sanity.py` · Calibration: `.venv/bin/python scripts/phase2_calibration.py`
- Loader API: `from src.loaders.ecmwf_opendata import load_daily_tmax` → normalized °C global grid (lat/lon)
- Phase 2 API: `from src.core.france import metropolitan_france_mask` · `from src.core.threshold import france_threshold, planet_fraction_hotter`
- ⚠️ Gotcha: cartopy's Natural Earth auto-downloader hit an SSL cert error (Py3.12/macOS); shapefiles
  pre-fetched via certifi → cached at `~/.local/share/cartopy/shapefiles/natural_earth/` (no re-download needed).
  Data source default = `source='google'` (AWS replica throttles downloads).
