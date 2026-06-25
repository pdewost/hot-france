# Source Workflow — extracted guidelines (as proposed, UNVERIFIED)
*Extracted 2026-06-25 from the conversation that seeded this project.*

> ⚠️ This file faithfully captures the workflow **as proposed**. It is the input to the
> adversarial review in `CHALLENGE_extracted_workflow.md`. Several steps are believed to
> contain factual/latency/API errors — do **not** implement from this file directly; use
> the corrected plan once the challenge is resolved.

## Objective (as stated)
Get "very close" to WaPo's ECMWF-based "only places hotter than France" map for Monday,
yesterday, and the day before, using ERA5 daily aggregates + xarray post-processing to apply
a "France max threshold" filter.

## Step 1 — Data choice & variables
- Use **ERA5 Daily Aggregates** (global, single-level) for daily min/max/mean at 2 m.
- Or use ERA5 hourly single levels and compute daily max yourself.
- Variable of interest: `maximum_2m_air_temperature_since_previous_post_processing`
  (exposed as `maximum_2m_temperature` or similar in API wrappers).
- Rationale: WaPo's map visually matches a daily (24 h) maximum near-surface temperature field.

## Step 2 — Get data via Copernicus CDS API
- `pip install cdsapi xarray netCDF4 numpy cartopy matplotlib`
- Configure `~/.cdsapirc` with a CDS key.
- Request (as proposed): dataset `reanalysis-era5-single-levels-daily-statistics`, product_type
  `reanalysis`, variable `maximum_2m_air_temperature_since_previous_post_processing`,
  year/month/day lists from the three dates, `time: '00:00'`, `format: 'netcdf'`.
- Dates as written: **D0 = Mon 2026-06-22**, **D1 = 2026-06-24 (yesterday)**, **D2 = 2026-06-23 (day before)**.
- Fallback noted: ERA5 daily aggregates from Earth Engine, or ERA5-Land daily.

## Step 3 — Load with xarray
- `ds = xr.open_dataset(...)`; inspect `ds.data_vars`; take first var as `tmax` (dims time, lat, lon).
- Convert Kelvin → Celsius: `tmax_c = tmax - 273.15`.

## Step 4 — Define France mask
- **Quick**: bbox metropolitan France `lat 41.0..51.5`, `lon -5.5..9.5`.
- **Precise**: Natural Earth `admin_0_countries`, select `ADM0_A3 == 'FRA'`, build boolean
  point-in-polygon mask over the lat/lon grid.

## Step 5 — Compute France max per day
- Broadcast mask over time; `tmax_france_only = tmax_c.where(france_mask_time)`;
  `tmax_france_daily = tmax_france_only.max(dim=('lat','lon'))` → one value/day (hottest grid cell in France).

## Step 6 — Build "hotter than France" global masks
- For each day, keep cells where `tmax_c >= threshold`, else NaN (per-timestep loop with `.loc[dict(time=t)]`).
- Optional split: `hotter_outside_france` vs `hotter_inside_france`.

## Step 7 — Plot WaPo-style maps per day
- Cartopy, Robinson/PlateCarree, `set_global()`, coastlines, gridlines.
- `t.plot(transform=PlateCarree(), cmap='inferno', vmin=25, vmax=50, add_colorbar=True)`.
- Save `hotter_than_france_<label>.png` at 300 dpi.
- Aesthetic notes: dark background, bright reds/yellows, optional grey/blue mask over non-hot areas,
  caption stating ERA5 daily max 2 m temp with France max grid cell as threshold.

## Step 8 — Align Monday with the WaPo map
- Match the Monday date to the date WaPo actually used (from their caption/article).
- Use same UTC day definition (ERA5 daily stats ≈ 00:00–24:00 UTC); note local-day shift.
- Once Monday matches WaPo, trust the pipeline for the other two days.

## Open dependency (as stated)
Author offered to refine for the exact Monday date once confirmed, and to suggest a colormap /
projection combo for best side-by-side match.
