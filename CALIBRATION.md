# Calibration — did we reproduce Ben Noll's "hotter than France" figure?
*2026-06-25*

**Yes.** Our independent pipeline reproduces Ben Noll's (WaPo) quoted planet-fraction for Monday 22 June.

## Result
| Date | France's hottest cell | % of planet strictly hotter (all-surface, cos-lat area-weighted) | Noll (WaPo) |
|------|----------------------:|-----------------------------------------------------------------:|------------:|
| Mon 22 Jun | 41.53 °C | **1.145 %** | **~1.2 %** |
| Tue 23 Jun | 42.10 °C | 0.767 % | — |
| Wed 24 Jun | 42.04 °C | 0.764 % | — |

Monday delta vs Noll: **0.055 percentage points (~4.6 % relative)** — a tight match given journalist
rounding + model/threshold differences.

## What this tells us about Noll's method
- **All-surface, not land-only.** Our all-surface figure (1.145 %) matches Noll's 1.2 %; the land-only
  figure (3.96 %) does not. So Noll's "% of the planet" is over the whole globe (land + ocean), area-weighted.
- **Threshold = France's single hottest grid cell** ("France's hottest place"), strictly-greater comparison.
- The fraction shrinks Mon→Wed because France itself got hotter (higher threshold ⇒ fewer places exceed it).

## Method (this reconstruction)
1. **Data**: ECMWF IFS operational forecast (`oper`, 00 UTC run), param `mx2t3` (3-hourly max 2 m T),
   steps 3…24 → daily max; 0.25°; via the ECMWF Open Data Google mirror. Same model family WaPo credits.
2. **France**: metropolitan-only mask (Natural Earth `map_units` GEOUNIT=France + metropolitan bbox guard,
   excludes overseas départements). Threshold = `max` over those cells.
3. **Fraction**: cos-latitude area-weighted share of global cells with daily-max **strictly >** threshold.

## Caveats (honest)
- **Model grid, not station records.** Our per-day France max is the hottest 0.25° model cell (a forecast),
  which puts Tue 23 (42.10 °C) marginally above Wed 24 (42.04 °C) — effectively tied. The real-world
  "Tuesday hottest ever, broken again Wednesday" refers to Météo-France **station observations**, a
  separate measure not captured by a 0.25° forecast grid.
- **Exact IFS sub-product** Noll used (HRES / ENS / AIFS) is unconfirmed; we use deterministic `oper`.
- This is an **independent reconstruction**, not the original WaPo/Noll graphic.

## Reproduce
```
.venv/bin/python scripts/phase2_calibration.py   # the table above
.venv/bin/python scripts/phase3_render.py         # the 6 maps
```
