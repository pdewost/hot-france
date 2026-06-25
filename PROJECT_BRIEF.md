# Hotter-Than-France — PROJECT_BRIEF
**Domain**: Other (data viz / climate reanalysis) | **Created**: 2026-06-25

## Goal
Reproduce — and be able to re-generate on demand — the Washington Post "ECMWF-based"
world map that shades **only the places on Earth that are hotter than France** during
the June 2026 European heatwave, for three reference days (a target Monday, "yesterday",
and "day-before-yesterday").

The deliverable is a small, reproducible Python pipeline that:
1. pulls a **global gridded near-surface (2 m) daily-maximum air-temperature** field,
2. computes a **France threshold** (the definition is itself under review — see CHALLENGE),
3. masks the global field to "≥ France threshold", and
4. renders a WaPo-style world map per day, plus a side-by-side check against WaPo's Monday map.

## Scope & non-goals
- **In scope**: data retrieval, France masking, threshold logic, map rendering, a Monday calibration check.
- **Non-goals**: claiming pixel-identical reproduction of WaPo's proprietary graphic; publishing/redistributing WaPo imagery; operationalising a daily auto-run (possible later).

## Tech Stack
- Python 3, `xarray`, `numpy`, `matplotlib`, `cartopy` (or `geopandas`/`regionmask` for masking).
- **Data source: DECISION PENDING** — the pasted proposal uses ERA5 via the Copernicus CDS API.
  This choice is contested on latency grounds; see `CHALLENGE_extracted_workflow.md`. Candidates:
  ECMWF Open Data (IFS), ARCO-ERA5 (GCS zarr), ERA5/ERA5T (CDS), GFS, Open-Meteo.

## Safety / integrity constraints
1. **Provenance honesty.** Every generated map must caption its actual data source, variable,
   day-window (UTC vs local), and threshold definition. Never imply it IS the WaPo graphic.
2. **Reproducibility.** Pin the dataset name, version/run, and request parameters in code; no hidden
   manual steps. Re-running with the same dates must give the same output.
3. **No secrets in tracked files.** CDS / ECMWF API keys live in `~/.cdsapirc` / env vars, never committed.
4. **Snapshot before overwrite.** Downloaded `.nc`/`.grib` and rendered `.png` go to gitignored
   `data/` and `outputs/`; keep the calibration Monday render as a baseline.

## Verification Protocol
- **Calibration gate**: generate the Monday map first and compare visually (and, if possible,
  numerically on a few landmark regions) against the published WaPo Monday map before trusting
  "yesterday"/"day-before".
- **Data sanity**: confirm units (K→°C), coordinate names, longitude convention (−180..180 vs 0..360),
  and that the France mask excludes overseas territories.
- **Threshold sanity**: print the France daily-max value per day and the count of "hotter" grid cells.

## Tier References
- Tier 0: `/Users/pdewost/Documents/Personnel/Developpement/ANTIGRAVITY.md`
- Domain entry: `/Users/pdewost/Documents/Personnel/Developpement/Design Projects/CLAUDE.md`
- Cold-start: `NEOCORTEX/MANIFEST.json` → `NEOCORTEX/STATUS.md` → active plans
- Source proposal (as pasted): `GUIDELINES_source_workflow.md`
- Adversarial review of that proposal: `CHALLENGE_extracted_workflow.md`
