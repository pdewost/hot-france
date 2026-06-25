# Adversarial review of the source workflow — VERIFIED
*2026-06-25 · Opus@Ultracode orchestration · 5 research + 4 verifier subagents (Sonnet@High), 267 tool calls, ~464k tokens. Every claim below is sourced.*

> Reviews `GUIDELINES_source_workflow.md`. **Verdict: the proposed pipeline is the wrong
> instrument for the stated goal, and is also infeasible for the requested dates.** Two
> independent show-stoppers + one wrong premise + several real bugs. It is salvageable, but
> the data source must change.

---

## 0. TL;DR

| # | Issue | Verdict | Severity |
|---|-------|---------|----------|
| A | ERA5/ERA5T has **no data for 22–24 Jun 2026** on 25 Jun (5-day to 2-month lag) | ✅ confirmed | **show-stopper** |
| B | WaPo's map is **ECMWF IFS forecast**, not ERA5 reanalysis → wrong source | ✅ confirmed | **show-stopper** |
| C | The CDS request (dataset name, variable, keys, endpoint) is **stale/invalid** | ◑ partially-correct | high (moot for A) |
| D | Natural Earth `FRA` polygon **includes tropical overseas départements** | ✅ confirmed | high |
| E | Coordinate names, longitude 0–360, per-step loop, plotting NaN/antimeridian | (code) | medium |
| F | Threshold = single hottest cell — **actually matches WaPo's intent**, but is fragile | (nuance) | note |

---

## 1. What the map actually is (this changes everything)

The "WaPo ECMWF-based" map is by **Ben Noll**, a Washington Post meteorologist (@BenNollWeather).
It is a recurring genre he originated in the **July 2022 UK heatwave** ("hotter than the UK"),
repeated for France in June 2026. Key verified facts:

- **Source: ECMWF operational IFS *forecast*** (graphic credited *"Ben Noll/The Washington Post and ECMWF"*). Noll's own site separates his monthly **ERA5** climate graphics from his real-time **ECMWF forecast** graphics — heatwave maps are the latter. The language is future tense ("*will be* hotter"). [conf: high]
- **Threshold: "hotter than France's *hottest place*"** — i.e. the single hottest grid point's daily-max 2 m temperature, compared globally. NOT an average, NOT a percentile, NOT an anomaly. [conf: high]
- **Quantitative targets we can calibrate against** (his own quoted numbers):
  - **Mon 22 Jun**: "only **1.2%** of the planet will be hotter than France's hottest place"
  - a later day: "only **0.93%** … hotter"
  - "France hotter than **99.02%** of the planet" (≈ 0.98% hotter; attributed to "Tuesday")
- **No published methodology box.** WaPo articles are paywalled (403); the X posts holding the actual map image are behind X's login. We could not pull the original raster. [conf: high]

**Implication:** the right way to *faithfully* reproduce this is ECMWF IFS forecast 2 m daily-max,
single-cell France threshold — and the best **calibration gate is reproducing the ~1.2% / 0.93%
figures**, not pixel-diffing an image we can't obtain.

Source: Noll tweets `status/2069027873445310756`, `status/2069737306349568493`; WaPo `2026/06/21/another-major-heat-dome-will-bake-swaths-europe`; Futura-Sciences `canicule-...-9902-planete`; The London Economic 2022 UK precedent; climate.copernicus.eu heatwave monitoring.

---

## 2. Show-stopper A — ERA5 latency (✅ confirmed, high)

Today is **2026-06-25**. Requested days: 22, 23, 24 June.

- **ERA5 final**: ~2 months behind → most recent data ≈ **April 2026**. June is nowhere close.
- **ERA5T (preliminary, near-real-time)**: **~5 days** behind, "D-5 typically by 12 UTC, not guaranteed." On 25 Jun the newest ERA5T ≈ **20 Jun**. June 22 (D-3), 23 (D-2), 24 (D-1) are **all inside the unavailable window.**

> The pasted ERA5 pipeline **physically cannot return these three days today.** It would error or return empty for all of them.

*Sources:* ECMWF Confluence ERA5 (pageId=76414402); Copernicus "data five days behind real-time"; ECMWF forum ERA5T availability.

**Silver lining (timing):** ERA5T will cover 22–24 Jun around **~27–29 Jun**. If retrospective ERA5-quality maps are acceptable a few days late, the *corrected* CDS pipeline becomes viable then.

---

## 3. Show-stopper B — wrong data source (✅ confirmed, high)

Even if ERA5 were available, it's the wrong product. Noll's map is a **real-time IFS forecast**;
ERA5 is a retrospective reanalysis. The WaPo piece was published **23 Jun** about temperatures on
22–23 Jun — a date for which ERA5/ERA5T did not yet exist at publication. So reproducing with ERA5
is a mismatch on **both** latency and product type.

**To match WaPo, use ECMWF IFS open data.** (The exact IFS sub-product — HRES vs ENS vs AIFS — is
unverifiable without paywall/author contact; HRES deterministic is the safe default.)

*Sources:* graphic credit "Ben Noll/ECMWF"; ECMWF Open Data page (CC-BY-4.0, IFS+AIFS, 0.25°); ECMWF opened full real-time catalogue Oct 2025.

---

## 4. Recommended data sources (ranked, for *this* goal)

| Path | Provenance | Covers 22–24 Jun *today*? | Auth | Effort | Notes |
|------|-----------|---------------------------|------|--------|-------|
| **ECMWF Open Data** (`ecmwf-opendata`) | **ECMWF IFS** ✅ matches WaPo | ⚠️ only ~last 12 runs (~2–3 d) on origin; AWS replica `s3://ecmwf-forecasts` *may* retain more — **must probe** | none | ~15 LOC | param `mx2t6` (6-h max 2 m) steps 6/12/18/24 → `.max('step')`. GRIB2, 0.25°. **Best match.** |
| **NOAA GFS** via `Herbie` | GFS (American model) ✗ not ECMWF | ✅ 30-day AWS archive `s3://noaa-gfs-bdp-pds` (reliable) | none | ~15 LOC | Great fallback for *availability*; map will differ visually from ECMWF in detail. |
| **ERA5 (corrected CDS)** | ERA5 reanalysis (≠ IFS forecast) | ❌ not until ~29 Jun | CDS token | ~20 LOC | Use only for retrospective maps ≥5 days old. Clean & reproducible then. |
| ARCO-ERA5 (GCS zarr) | ERA5 | ❌ ~1 wk–3 mo lag | none | ~5 LOC | Easiest *for historical*; no near-real-time. |
| Open-Meteo | mixed | n/a | none | — | **Point API only — cannot produce a global grid. Excluded.** |
| Google Earth Engine ERA5 | ERA5 | ❌ ~3 mo lag | account | — | Overkill + latency. |

---

## 5. Issue C — the CDS request (◑ partially-correct)

If/when ERA5 is used (retrospective path), the pasted request is broken on every line. Corrected:

```python
import cdsapi
c = cdsapi.Client()  # .cdsapirc -> url: https://cds.climate.copernicus.eu/api  + Personal Access Token
c.retrieve(
    "derived-era5-single-levels-daily-statistics",   # NOT reanalysis-...; legacy app killed 2024-09-26
    {
        "product_type": "reanalysis",
        "variable": ["2m_temperature"],              # NOT maximum_2m_air_temperature_since_previous_post_processing
        "year": "2026", "month": ["06"], "day": ["22", "23", "24"],
        "daily_statistic": "daily_maximum",          # the max is requested here, not via the variable
        "time_zone": "utc+02:00",                    # CEST for French civil-day Tmax (small effect)
        "frequency": "1_hourly",
        "data_format": "netcdf",                     # NOT format=
    },
).download("era5_daily_tmax.zip")                     # output is a ZIP containing the .nc
```

Corrections vs. the original: dataset renamed; variable replaced (the long `…since_previous_post_processing`
name is forecast-only, has a *known +1 h time-shift bug* in the derived dataset, and the "air" spelling
doesn't exist at all); added `daily_statistic`/`time_zone`/`frequency`; `format`→`data_format`; dropped the
hourly `time` key; new API endpoint + Personal Access Token (old `…/api/v2` + UID:key decommissioned 2024-09-26).
*(One residual ambiguity: `daily_maximum` vs `daily_max` spelling — verify against the live CDS form.)*

*Sources:* CDS catalogue `derived-era5-single-levels-daily-statistics`; ECMWF forum dataset announcement + param-issue thread; PyAPS migration notes.

---

## 6. Issue D — France polygon includes overseas (✅ confirmed)

Natural Earth `admin_0_countries` stores France as one MultiPolygon (`ADM0_A3='FRA'`) that **includes
Guyane, Martinique, Guadeloupe, Réunion, Mayotte** — tropical, 28–35 °C year-round. Taking `.max()` over
that geometry sets the "France max" to a *tropical* cell, silently destroying the comparison. Fixes:

- **bbox** (after longitude fix): `lat 41.3..51.3, lon -5.5..9.9` (metropolitan + Corsica) — simplest, reliable; **or**
- Natural Earth **`ne_10m_admin_0_map_units`**, filter `GEOUNIT == 'France'` (separates DOM).

*Sources:* naturalearthdata.com admin-0 docs; rnaturalearth "what is a country" vignette; natural-earth-vector issue #196.

---

## 7. Issue E — code bugs (all real)

| Bug | Fix |
|-----|-----|
| Coords assumed `time/lat/lon`; CDS netCDF uses **`valid_time/latitude/longitude`** | rename defensively after load |
| **Longitude 0–360** (ERA5 *and* ECMWF GRIB) → France bbox `-5.5..9.5` selects nothing | `ds.assign_coords(lon=((ds.lon+180)%360-180)).sortby('lon')` |
| Per-timestep `for`-loop with `.loc[dict(time=t)]` — slow, needless | single vectorized `tmax_c.where(tmax_c >= france_daily_max)` (broadcasts on the `time` dim) |
| `inferno` renders **NaN as black** = merges with hot end; no fixed `vmin/vmax` across days | `cmap.set_bad('lightgray')`, fix `vmin/vmax` (e.g. 20–50 °C) |
| Antimeridian streak in Cartopy `pcolormesh` | `cartopy.util.add_cyclic_point` before plotting |
| Open-Meteo as a drop-in | impossible (point API, no grid) — excluded |

*Sources:* MediTwin CDS tutorial (valid_time/latitude/longitude); ECMWF spatial-reference (0–360); xarray broadcasting docs; Cartopy issue #1654.

---

## 8. Issue F — threshold nuance (deliberate choice, not a bug)

The pasted "single hottest France cell" is **faithful to Noll's stated method** ("France's hottest place")
— so for *reproduction* we keep it. BUT in a record heatwave the single max can sit near France's all-time
record (~45–46 °C), which can push the global "hotter" area toward zero and be outlier-sensitive (one
0.25° cell). **Plan:** use single-cell max as the primary (faithful) threshold, **and** emit a 95th/99th
-percentile variant as a labelled sensitivity check. Validate the primary against Noll's quoted **1.2% /
0.93%** planet-fraction figures (cos-latitude area-weighted) — that's our objective calibration gate.

---

## 9. Net recommendation

1. **Drop ERA5 for the near-real-time goal.** Use **ECMWF Open Data (IFS)** to match WaPo; keep **GFS/Herbie** as an availability fallback; keep the **corrected ERA5 CDS** path for retrospective (≥5-day-old) maps.
2. **Probe data availability first** (Phase 0) — confirm whether 22–24 Jun IFS runs are still retrievable today before committing to ECMWF-vs-GFS.
3. **Keep the single-cell threshold** (faithful) + percentile sensitivity; **calibrate on the % figures**.
4. Fix the polygon (metropolitan only), coords, longitude, vectorization, and plotting as above.
5. **Decide the goal** with the founder: (A) best-effort faithful repro of the *past 3 days*, vs (B) a reusable pipeline that runs cleanly *going forward* (+ ERA5 backfill after ~29 Jun). See `NEOCORTEX/PLAN_reproduction_2026-06-25.md`.
