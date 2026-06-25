# NOTE — Phase 0 data-availability probe (RESOLVED)
*2026-06-25 · empirical probe of public S3 buckets (no auth, read-only listings)*

Resolves the PLAN §1 open decision on data source. Founder chose Hybrid + "let Phase 0 decide".

## Verdict
**Primary loader = ECMWF Open Data, IFS `oper` (deterministic HRES), 0.25°, via the AWS replica
`s3://ecmwf-forecasts`.** GFS (`s3://noaa-gfs-bdp-pds`) confirmed as fallback. Both cover all three
target dates *today*.

## Evidence (probed 2026-06-25 07:45 UTC)
- `s3://ecmwf-forecasts/20260622/`, `/20260623/`, `/20260624/` all exist with cycles 00/06/12/18z.
- Tree: `<date>/<cycle>z/ifs/0p25/oper/` holds `…-{step}h-oper-fc.grib2` + `.index` sidecars
  (also `aifs-single/`, `aifs-ens/` AI-model streams). `.index` files enable **byte-range fetch of a
  single param** — no full-GRIB downloads.
- The replica is a **deep archive** (date partitions listed back to early 2024), NOT the ~3-day rolling
  window documented for the origin server. So aged dates remain retrievable here.
- `s3://noaa-gfs-bdp-pds/gfs.20260622/` (and 23, 24) present with cycles 00/06/12/18.

## ⚠️ Correction to research finding (params)
The research bundle (`../CHALLENGE_extracted_workflow.md` §4) said to use **`mx2t6`** (6-hourly max).
The **actual IFS `oper` index** (20260622/00z, step 6h, 184 records) contains:
- `2t` (instantaneous 2 m temperature) ✅
- `mx2t3` (3-hourly max 2 m temperature) ✅  ← **use this**
- `mn2t3` (3-hourly min 2 m temperature)
- **No `mx2t6`.**

**Daily-max recipe (corrected):** from the **00z run**, fetch `mx2t3` at steps **3,6,9,12,15,18,21,24**
(eight 3-hour windows covering hours 0–24 UTC) and take `.max('step')`. Each `mx2t3` at step S is the
model's true max over (S−3, S], so this is exact, not a resampling approximation. (`2t` remains a
sanity cross-check.) For French civil-day alignment, optionally shift the step window to cover
02→26 h ≈ CEST midnight-to-midnight, but the effect on Tmax is <0.5 °C.

## ⚠️ Update (Phase 1 build): AWS replica throttles on *downloads*
The AWS replica is great for *listings* (used above) but **throttles actual file downloads** with
`503 SlowDown` (hit in both Phase 0 index-fetch and Phase 1 build). The loader therefore defaults to
**`source='google'`** (`storage.googleapis.com/ecmwf-open-data`) — byte-identical GRIB, instant. AWS
remains usable for listings / as an override. (`source='ecmwf'` = origin, ~3-day window only.)

## Consequence for the plan
- PLAN §1 decision: **resolved → ECMWF IFS primary, GFS fallback.**
- PLAN §2 loader: `ecmwf_opendata.py` targets `stream=oper, type=fc, param=mx2t3, step=[3..24 by 3]`,
  `source=aws`; `.max('step')` → daily-max grid. (NOT mx2t6.)
- Still applies: longitude 0–360 → −180..180 fix; metropolitan-France mask; single-cell threshold +
  percentile variant; calibrate vs Noll's ~1.2% / 0.93% planet-fraction.
