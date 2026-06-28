# Hotter than … (EU heatwave maps) 🌡️

A bilingual (FR/EN), dark/light web page reconstructing the viral *"only the places on Earth hotter
than [country]"* maps for the **June 2026 European heatwave** — and an open, reproducible pipeline behind it.

> **Live page:** https://pdewost.github.io/hot-france/
> **Single-file version:** `hot-france-standalone.html` (everything inlined — open it anywhere, no server).

## What it shows

Each day we find the **hottest point in Continental Europe** and shade every place on Earth strictly
hotter than it. France is always shown as a secondary overlay for reference.
During the heatwave, only **0.3 – 2.3 %** of the planet's surface was hotter than the European peak.

| Date | Reference country | Peak °C | % of planet hotter |
|------|-------------------|--------:|-------------------:|
| Mon 22 Jun | Spain   | 42.31 | 0.84 % |
| Tue 23 Jun | Spain   | 43.85 | 0.34 % |
| Wed 24 Jun | France  | 42.04 | 0.76 % |
| Thu 25 Jun | France  | 40.15 | 1.70 % |
| Fri 26 Jun | Germany | 38.86 | 2.26 % |
| Sat 27 Jun | Germany | 39.87 | 1.82 % |

## Method (and how it was validated)

- **Data:** ECMWF **IFS** operational forecast (`oper`, 00 UTC run), 3-hourly max 2 m temperature (`mx2t3`)
  reduced to a daily max, 0.25° — via [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data).
- **Reference country:** the Continental European country with the highest single 0.25° grid cell that day
  (EU-scoped; no threshold). France is overlaid on every map regardless.
- **"% of planet hotter":** cosine-latitude **area-weighted** share of the globe strictly above the reference peak.
- **Calibration:** our Monday figure is **1.145 %** vs the **~1.2 %** quoted by Ben Noll (The Washington Post)
  for a France-as-reference framing — see [`CALIBRATION.md`](CALIBRATION.md).

## Honest disclaimer

This is an **independent reconstruction**, inspired by Ben Noll / The Washington Post — **not** the original
graphic and **not affiliated** with them. Per-day values are the hottest **model-forecast** grid cell;
the "record broken" headlines refer to **station observations**, a separate measure.

## Run the daily update

```bash
# First-time setup
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Add a new day (downloads GRIB, discovers EU ref, renders 4 maps, prints DATA entry)
.venv/bin/python scripts/run_daily.py 2026-06-28

# Paste the printed DATA entry into index.html, then commit and push:
git add index.html assets/maps/hotter_than_*_2026-06-28_*.png
git commit -m "data(2026-06-28): ..."
git push
```

## Build the standalone file

```bash
python3 scripts/build_standalone.py   # inlines all maps → hot-france-standalone.html
```

## Legacy calibration scripts

```bash
.venv/bin/python scripts/phase2_calibration.py   # France-as-reference % table (3 days)
.venv/bin/python scripts/phase3_render.py         # France-as-reference maps (12 variants)
```

## Credits & licence

- Maps derived from **ECMWF Open Data**, licensed **CC-BY-4.0** — attribute ECMWF if you reuse them.
- Code in this repo: **MIT** (see [`LICENSE`](LICENSE)).
- Concept: Ben Noll / The Washington Post (reconstruction only).
