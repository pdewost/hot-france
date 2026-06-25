# Hotter-Than-France — Status
*Last updated: 2026-06-25*

## What this project is
Reproduce — and be able to regenerate — Ben Noll's WaPo "ECMWF-based" world map that shades
**only the places on Earth hotter than France's hottest place** during the June 2026 heatwave
(target days: Mon 22, Tue 23, Wed 24 Jun). Output: a small reproducible Python pipeline + WaPo-style
maps, calibrated against Noll's quoted planet-fraction figures (~1.2% / 0.93%).

## Current phase
**Phase 1 COMPLETE** — 2026-06-25. ECMWF IFS loader built + triple-verified (build agent, adversarial
verifier, founder re-run). Sanity for 22 Jun: global max **50.23 °C @ 31.25 N,47.25 E** (Iraq/Kuwait
desert ✅), France-bbox max **41.91 °C** ✅, grid 721×1440, lon −180..179.75, °C, 0 NaN, 8 steps.
Next: **Phase 2** (metropolitan France mask + single-cell threshold + planet-fraction calibration).

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
1. **Phase 2** — `src/core/france.py` (metropolitan mask, excl. DOM: bbox lat 41.3..51.3/lon −5.5..9.9
   or NE map_units GEOUNIT='France') + `src/core/threshold.py` (single-cell France max [faithful] +
   percentile variant) + planet-fraction calc (cos-lat area-weighted). **Calibration gate:** fraction
   hotter than France ≈ Noll's ~1.2% (Mon 22) / 0.93% / 0.98%.
2. Phase 3 — vectorized `where(t >= france_max)` mask + WaPo-style render (Cartopy) with honest caption.
3. Phase 4 — run all 3 days + `outputs/CALIBRATION.md`; keep Monday baseline snapshot.
4. Phase 5 (optional, ~29 Jun+) — ERA5 backfill via corrected CDS; forecast-vs-reanalysis diff.

✅ Done 2026-06-25: project scaffold; source-workflow challenge (verified); Phase 0 probe (ECMWF IFS
primary, param mx2t3); **Phase 1 loader** (`src/loaders/ecmwf_opendata.py` + `src/core/normalize.py`,
venv + GRIB stack, sanity green).

## Pointers
- Source proposal (as pasted): `../GUIDELINES_source_workflow.md`
- Adversarial review (verified): `../CHALLENGE_extracted_workflow.md`
- Active plan: `PLAN_reproduction_2026-06-25.md`
- Brief: `../PROJECT_BRIEF.md`
- Cold-start read order: MANIFEST.json → STATUS.md → active plans
- Smoke test: `.venv/bin/python scripts/phase1_sanity.py` (fetches/caches 22 Jun IFS, prints sanity grid)
- Loader API: `from src.loaders.ecmwf_opendata import load_daily_tmax` → normalized °C global grid (lat/lon)
