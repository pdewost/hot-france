# Hotter-Than-France — Status
*Last updated: 2026-06-25*

## What this project is
Reproduce — and be able to regenerate — Ben Noll's WaPo "ECMWF-based" world map that shades
**only the places on Earth hotter than France's hottest place** during the June 2026 heatwave
(target days: Mon 22, Tue 23, Wed 24 Jun). Output: a small reproducible Python pipeline + WaPo-style
maps, calibrated against Noll's quoted planet-fraction figures (~1.2% / 0.93%).

## Current phase
**Phases 1–3 COMPLETE + page shipped** — 2026-06-25. End-to-end works: loader → France mask → threshold →
calibration (Mon 1.145% vs Noll 1.2% ✅) → 6 theme-aware Robinson maps → bilingual dark/light `site/index.html`
with maps wired in. All stages independently verified; maps visually confirmed (deserts glow, France blank,
hot area shrinks Mon→Wed). `CALIBRATION.md` written. Nested git repo committed.
Remaining (optional): Phase 5 — ERA5 backfill (~29 Jun, when ERA5T covers 22–24 Jun) for a reanalysis cross-check.

## Invariants
1. **Data source = ECMWF IFS forecast (`oper`, param `mx2t3`), NOT ERA5** for these dates. ERA5/ERA5T
   lags ~5 days–2 months (no 22–24 Jun on 25 Jun) and the WaPo map is IFS forecast, not reanalysis.
   ECMWF AWS replica confirmed to hold all 3 dates. (CHALLENGE §2–§3 + NOTE_phase0, verified)
2. **France = metropolitan only** (incl. Corsica). Natural Earth `FRA` includes tropical overseas
   départements and corrupts the max threshold. (CHALLENGE §6, verified)
3. **Provenance honesty.** Every map captions its real source/variable/window/threshold; never imply it IS WaPo's graphic. (PROJECT_BRIEF safety #1)
4. **Calibration is quantitative**, not pixel-diff (original image is paywalled): reproduce Noll's ~1.2%/0.93% within tolerance.
5. **Faithful threshold = single hottest France cell** (matches "France's hottest place"); percentile is a labelled sensitivity variant only.

## Next actions (all optional — core deliverable shipped)
1. Phase 5 (~29 Jun+) — ERA5 backfill via corrected CDS once ERA5T covers 22–24 Jun; forecast-vs-reanalysis diff.
2. If desired: serve/share the page (any static server over `site/`), or add more days as the heatwave evolves.
3. If desired: confirm Noll's exact IFS sub-product (HRES/ENS/AIFS) by emailing him; we used deterministic `oper`.

✅ Done 2026-06-25: scaffold; source-workflow challenge (verified); Phase 0 probe (ECMWF IFS, mx2t3);
**Phase 1 loader**; **Phase 2 mask+threshold+calibration (1.145% vs 1.2% ✅)**; **Phase 3 render — 6
theme-aware Robinson maps** (visually confirmed); **bilingual dark/light page** (`site/index.html`, maps wired,
Tue/Wed footnote, 19/19 i18n parity); `CALIBRATION.md`; nested git repo (3 commits).

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
