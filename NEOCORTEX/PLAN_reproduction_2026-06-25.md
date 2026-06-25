# PLAN — Hotter-Than-France reproduction
*Created 2026-06-25 · status: AWAITING FOUNDER DECISION on goal + data source (see §1)*

Grounds the corrected approach from `../CHALLENGE_extracted_workflow.md`. Do not start coding
until §1 is resolved — the data source determines the whole pipeline.

## 1. Decision — RESOLVED 2026-06-25
**Goal = Hybrid (C):** build a reusable, source-agnostic pipeline AND do a best-effort faithful repro of
22–24 Jun. **Data source = ECMWF IFS `oper` 0.25° via `s3://ecmwf-forecasts`** (GFS fallback) — Phase 0
confirmed all three dates are retrievable from the ECMWF AWS replica today (it's a deep archive, not a
3-day window). See `NOTE_phase0_data_probe_2026-06-25.md`. **Param = `mx2t3`** (3-hourly max; mx2t6 does
NOT exist in this stream — research was wrong): daily max = `max(mx2t3)` over steps 3,6,…,24 of the 00z run.

## 2. Target architecture (source-agnostic)
```
src/
  loaders/
    ecmwf_opendata.py   # IFS oper mx2t3 steps 3..24 -> .max('step') daily-max 2m grid (primary, matches WaPo)
    gfs_herbie.py       # GFS analysis/Tmax -> daily-max grid (fallback, always available)
    era5_cds.py         # corrected derived-era5 daily_maximum (retrospective, >=5d old)
  core/
    normalize.py        # -> common xr.DataArray (time, lat[-90..90], lon[-180..180], degC); fix coords+lon
    france.py           # metropolitan-only mask (bbox or map_units GEOUNIT='France')
    threshold.py        # single-cell max (faithful) + percentile variant; planet-fraction (cos-lat weighted)
    mask_hotter.py      # vectorized where(t >= france_max)
  render/
    wapo_map.py         # Cartopy Robinson, set_bad('lightgray'), fixed vmin/vmax, add_cyclic_point, caption
  run.py                # CLI: --date / --source / --threshold / --out
```
All loaders return the SAME normalized DataArray so core/render never know the source.

## 3. Phases
- **Phase 0 — availability probe (½ day).** Before committing: empirically check whether 22/23/24 Jun
  IFS runs are still on `s3://ecmwf-forecasts` (and ECMWF origin), and confirm GFS `s3://noaa-gfs-bdp-pds`
  has them. Output: a one-page note fixing the source choice. **Gate: which loader is primary.**
- **Phase 1 — loader + normalize.** Build the chosen primary loader + `normalize.py`. Sanity: units °C,
  coords renamed, lon in −180..180, global extent, no all-NaN. Snapshot raw download to `data/`.
- **Phase 2 — France + threshold.** Metropolitan mask (verify it excludes DOM by printing the masked
  bbox), single-cell max per day, planet-fraction calc. **Calibration gate:** fraction ≈ Noll's
  **1.2% (Mon 22)** / **0.93%** / **0.98%**; if off by >~0.5 pt, investigate (land-only vs all-surface,
  area weighting, instantaneous vs daily-max, threshold day alignment).
- **Phase 3 — mask + render.** Vectorized hotter-than mask; WaPo-style map per day; honest caption
  (source, variable, UTC/local window, threshold). Save PNGs to `outputs/`.
- **Phase 4 — multi-day + calibration report.** Run all 3 days; write `outputs/CALIBRATION.md` comparing
  computed vs quoted percentages; keep Monday render as the baseline snapshot.
- **Phase 5 (optional) — ERA5 backfill (~29 Jun+).** Add `era5_cds.py`, regenerate 22–24 Jun from ERA5T,
  diff against the forecast-based maps (forecast-vs-reanalysis sensitivity).

## 4. Verification protocol
- **Calibration is quantitative**, not pixel-diff (we cannot obtain the paywalled image): reproduce the
  quoted planet-fraction figures within tolerance.
- Each map self-documents provenance (PROJECT_BRIEF safety rule #1).
- Adversarial-review gate (`adversarial_review` skill, `code` pack) before declaring Phase 3 done.

## 5. Deps / env
`xarray numpy matplotlib cartopy` + per-loader: `ecmwf-opendata cfgrib eccodes` (ECMWF) /
`herbie-data` (GFS) / `cdsapi` (ERA5). Secrets in `~/.cdsapirc` / env only (never tracked).

## 6. Risks
- IFS open-data dates aged out today → fall back to GFS (note the provenance caveat in captions).
- "% of planet" definition ambiguous (land vs all-surface) → calibration phase resolves it empirically.
- Exact IFS sub-product (HRES/ENS/AIFS) unknown → default HRES; optionally email Noll to confirm.
- GRIB stack (`eccodes`) install friction on macOS → `conda`/`mamba` or `brew install eccodes` if pip fails.
