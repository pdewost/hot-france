# Hotter-Than-France — Journal
*Quarter: 2026-06 (rotation threshold: 64 KB or quarter boundary)*

---

### 2026-06-25 | Phase 3 COMPLETE — 6 theme-aware Robinson maps; project deliverable shipped

- Delegated render + verify (Sonnet@High, wf wqxycldlf). `src/render/wapo_map.py` (render_map + THEMES) +
  `scripts/phase3_render.py`. 6 PNGs (3 days × light/dark), 1600×900, France blank, hot area 0.80→0.54→0.53%
  (correct shrinking trend), deserts glowing. cartopy coastline SSL pre-fetched via certifi (same as Phase 2).
- **Founder (Opus) review caught two things the render-verifier missed/mis-stated:** (1) the map *read* as
  flat — fixed by giving the ocean (`ax.patch`) a distinct fill vs the figure bg + a faint globe outline, so
  the Robinson projection now reads as a globe (it always WAS Robinson; ocean==bg hid the curvature);
  (2) verifier's `hot_px_pct` was actually a grid-cell fraction → renamed `hot_cell_pct` + docstring fixed.
  Re-rendered; visually confirmed both dark + light variants by reading the PNGs.
- Map bg matches `--bg-card` per theme ⇒ globe floats seamlessly in the cards. object-fit cover on 16:9
  image into 16:9 card = exact fit.
- Wrote `CALIBRATION.md` (validation evidence). Page now complete: panels filled, maps swap with day/night.
- **Deliverable shipped.** Optional remainder: Phase 5 ERA5 backfill (~29 Jun).

### 2026-06-25 | Presentation page built (Apple-50 template adapted)

- Delegated adapt + verify (Sonnet@High, wf w1oxl0p64). Located template at
  `Developpement/HTML single pages/apple-50-years-checklist.html`; reused its design tokens + dark/light +
  i18n (STRINGS/t/toggleLang) + header/footer shell; dropped all checklist machinery.
- `site/index.html` (self-contained): heat-gradient hero, record callout, 3 day panels (from DATA), 4-point
  methodology, footer. Added: localStorage theme+lang persistence + prefers-color-scheme; data-i18n convention.
- Founder edits (Opus): wired real Phase 2 numbers (Mon 41.5 °C/1.15% · Tue 42.1/0.77 · Wed 42.0/0.76);
  added bilingual Tue/Wed model-vs-station-observation footnote (`modelNote`); object-fit contain (don't crop
  world maps); consistent decimals; removed dead vars. Static check: 15/15 i18n parity, tags balanced.
- Maps still pending → cards show graceful "Map pending"/"Carte à venir" until Phase 3 renders PNGs into
  `site/assets/maps/`.

### 2026-06-25 | Phase 2 COMPLETE — calibration VALIDATED (1.145% vs Noll 1.2%)

- Delegated build + independent adversarial verify (Sonnet@High, workflow wsoix6y8x). Verdict PASS, 0 bugs.
- Built `src/core/france.py` (metropolitan mask via NE 10m admin_0_map_units GEOUNIT='France' + shapely.vectorized
  + bbox belt-and-suspenders; 1033 cells, lat 41.5..51.0, lon −4.75..9.5, DOM-leak check PASS),
  `src/core/threshold.py` (`france_threshold` max/percentile; `planet_fraction_hotter` cos-lat area-weighted,
  strictly >), `scripts/phase2_calibration.py`. Installed cartopy/shapely/pyproj/matplotlib/pillow into venv.
- **Calibration:** Mon 22 = **1.145%** planet hotter than France (max 41.53 °C) vs Noll **1.2%** (Δ 0.055 pp).
  Tue 23 = 0.767% (42.10 °C), Wed 24 = 0.764% (42.04 °C). All-surface matches Noll; land-only (3.96%) does not
  ⇒ Noll computed whole-planet. Methodology reproduced.
- **Honest nuance:** our IFS 00z grid daily-max has Tue (42.10) ≈ Wed (42.04) — Tue marginally higher; the
  real-world "Wed broke Tue's record" is a *station-observation* record, not the 0.25° model grid (which ties them).
- Gotcha: cartopy NE auto-download SSL cert failure (Py3.12/macOS) → pre-fetched shapefiles via certifi, cached.

### 2026-06-25 | Phase 1 COMPLETE — ECMWF IFS loader built + triple-verified

- Delegated build to Sonnet@High + independent Sonnet@High adversarial verifier (workflow w3rgycenw).
- Built: `.venv` + GRIB stack (ecmwf-opendata 0.3.30, cfgrib 0.9.15.1, eccodes 2.47.0, ecmwflibs 0.7.0,
  xarray 2026.4.0, numpy 2.5.0; `requirements.txt`); `src/loaders/ecmwf_opendata.py`
  (`fetch_daily_tmax_grib`/`open_daily_tmax`/`load_daily_tmax`); `src/core/normalize.py`; `scripts/phase1_sanity.py`.
- **Sanity (22 Jun 00z):** grid 721×1440, lon −180..179.75, °C, 0 NaN, 8 steps; global max **50.23 °C @
  31.25 N,47.25 E** (Iraq/Kuwait desert — correct), France-bbox max **41.91 °C** (heatwave-plausible).
- **Operational finding:** AWS replica throttles on *downloads* (503 SlowDown) — loader defaults to the
  **Google mirror** (identical GRIB, instant). Recorded in NOTE_phase0.
- Verifier verdict **pass-with-caveats**: confirmed param mx2t3 / type fc / 8 steps / max-over-step /
  lon-fix+sortby / lat-sorted / single K→°C / no scope creep / reproducible. One low bug (docstring said
  default 'aws' while code uses 'google') → **fixed** (kept 'google', corrected docs). Founder re-ran
  sanity post-fix: identical. Next: Phase 2 (France mask + threshold + calibration).

### 2026-06-25 | Phase 0 data probe — ECMWF IFS primary; mx2t3 (not mx2t6)

- Founder chose **Hybrid** goal + "let Phase 0 decide" source. Probed public S3 (no auth).
- **Result:** `s3://ecmwf-forecasts` holds 20260622/23/24 (all cycles, `ifs/0p25/oper/` GRIB2 + `.index`),
  and is a deep archive (partitions back to early 2024) — NOT a 3-day window. GFS `s3://noaa-gfs-bdp-pds`
  also has all three. **Primary = ECMWF IFS `oper`; fallback = GFS.**
- **Correction to research:** IFS oper index has `mx2t3` (3-hourly max) + `2t`, but **no `mx2t6`**.
  Daily max = `max(mx2t3)` over steps 3..24 of the 00z run. Logged in `NOTE_phase0_data_probe_2026-06-25.md`.
- Next: Phase 1 loader build, gated on founder go-ahead for venv + GRIB-stack install (machine stability).

### 2026-06-25 | Source workflow adversarially reviewed — ERA5 approach rejected

- Ran `htf-research-challenge` workflow (5 research + 4 verifier subagents, Sonnet@High; 267 tool
  calls, ~464k tokens). Wrote `../CHALLENGE_extracted_workflow.md` (all claims sourced).
- **Findings (verified):** the map is Ben Noll's (WaPo) ECMWF **IFS forecast** "hotter than France's
  hottest place" genre (repeat of his 2022 UK map), threshold = single hottest France cell, with
  quoted planet-fractions ~1.2% (Mon 22) / 0.93% / 0.98%.
- **Two show-stoppers for the pasted plan:** (A) ERA5/ERA5T has no 22–24 Jun data on 25 Jun (~5-day–
  2-month lag); (B) wrong product (IFS forecast, not reanalysis). Plus stale CDS request, FRA-polygon-
  includes-overseas bug, coord/longitude/vectorization/plotting bugs.
- **Decision pending:** goal + data source (A faithful past-3-days / B reusable forward / C hybrid).
  Plan: `PLAN_reproduction_2026-06-25.md`. No code written yet.

### 2026-06-25 | Project created

- Scaffolded with `project_scaffold` skill (NEOCORTEX_SPEC v1.0); `--domain other` (data-viz/reanalysis).
- PROJECT_BRIEF.md tailored; folders `src/ data/ outputs/ snapshots/` + `.gitignore` added.
- NEOCORTEX/ skeleton created: MANIFEST.json, STATUS.md, JOURNAL.md.

