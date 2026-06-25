# Hotter than France 🌡️

A bilingual (FR/EN), dark/light web page reconstructing the viral *"only the places on Earth hotter
than France"* map for the **June 2026 European heatwave** — and an open, reproducible pipeline behind it.

> **Live page:** https://pdewost.github.io/hot-france/
> **Single-file version:** `hot-france-standalone.html` (everything inlined — open it anywhere, no server).

During the heatwave, only about **1 %** of the planet was hotter than France's hottest place. This project
reproduces that figure from scratch and renders the maps.

## What it shows
For three days (Mon 22 / Tue 23 / Wed 24 June 2026), each map highlights every place on Earth **strictly
hotter than France's hottest grid cell** that day, with France itself temperature-coloured and a crosshair
on its hottest point:

| Day | France's hottest | % of planet hotter |
|-----|-----------------:|-------------------:|
| Mon 22 Jun | 41.5 °C | 1.15 % |
| Tue 23 Jun | 42.1 °C | 0.77 % |
| Wed 24 Jun | 42.0 °C | 0.76 % |

## Method (and how it was validated)
- **Data:** ECMWF **IFS** operational forecast (`oper`, 00 UTC run), 3-hourly max 2 m temperature (`mx2t3`)
  reduced to a daily max, 0.25° — via [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data).
- **Threshold:** the single hottest 0.25° grid cell inside **metropolitan France** (Corsica included, overseas
  *départements* excluded).
- **"% of planet hotter":** cosine-latitude **area-weighted** share of the globe strictly above that threshold.
- **Calibration:** our Monday figure is **1.145 %** vs the **~1.2 %** quoted by Ben Noll (The Washington Post) —
  see [`CALIBRATION.md`](CALIBRATION.md). The all-surface figure matches; land-only (3.96 %) does not, which is
  how we know the original was computed over the whole planet.

## Honest disclaimer
This is an **independent reconstruction**, inspired by Ben Noll / The Washington Post — **not** the original
graphic and **not affiliated** with them. Per-day values are the hottest **model-forecast** grid cell, so
Tuesday and Wednesday come out effectively tied (~42 °C); the real-world "hottest day ever, then broken again"
records are **station observations**, a separate measure.

## Reproduce
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/phase2_calibration.py   # the % table
.venv/bin/python scripts/phase3_render.py         # the maps (12 variants: 3 days × light/dark × EN/FR)
python3 scripts/build_standalone.py               # the single-file page
```

## Credits & licence
- Maps derived from **ECMWF Open Data**, licensed **CC-BY-4.0** — attribute ECMWF if you reuse them.
- Code in this repo: **MIT** (see [`LICENSE`](LICENSE)).
- Concept: Ben Noll / The Washington Post (reconstruction only).
