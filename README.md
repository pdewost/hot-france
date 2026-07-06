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
```

### Primary: windowed update (`run_window.py`)

`run_window.py` processes a sliding window of days in one pass — it refreshes the last few
**actual** days *and* publishes a few **forecast** days ahead — then injects every resulting
entry straight into `index.html` (no manual copy-paste), behind a `node` parse-check safety net.

```bash
# Default window: 2 days back … 3 days ahead of today (UTC)
.venv/bin/python scripts/run_window.py

# Wider backfill: 8 days back, 3 ahead, anchored on a specific day
.venv/bin/python scripts/run_window.py --back 8 --ahead 3 --date 2026-07-06

# See the plan without touching anything
.venv/bin/python scripts/run_window.py --dry-run --back 8 --ahead 3

# Only fill dates missing from DATA (don't re-render days already present)
.venv/bin/python scripts/run_window.py --skip-existing
```

Flags: `--back N` (default 2), `--ahead M` (default 3), `--date YYYY-MM-DD` (anchor, default
today UTC), `--dry-run`, `--skip-existing`.

**Forecast days.** Any date beyond today's model run is fetched from the correct forecast
horizon of an earlier run (offset steps), and its DATA entry is tagged `fcst:1`. On the page,
forecast days show a small **"forecast" / "prévision"** badge and appear only in the day grid —
they never drive the page title, hero line, or featured map (those always use the latest
**actual** day). ECMWF's `mx2t3` reaches 5 days out, so `--ahead` is clamped to a 5-day horizon
(a warning is printed; the run never crashes). When you re-run the window after a forecast date
has passed, that day is regenerated from the analysed run and the `fcst` flag drops automatically
— the line upgrades itself from forecast to actual in place.

Injection is **idempotent** (re-running with the same inputs yields an identical file) and writes
`index.html.bak` first; if the post-write `node` parse-check fails, the backup is restored and the
command exits non-zero. Per-day fetch failures (e.g. an old date no longer on the open-data mirror)
are logged and skipped, with an `OK / SKIPPED / FAILED` summary at the end — one bad day never
aborts the whole window.

```bash
# After a run, commit the page + the new maps (maps are gitignored by default; force-add if needed):
git add index.html assets/maps/hotter_than_*_2026-07-*.png
git commit -m "data(window): refresh 2026-07-04 … 2026-07-09 (+forecasts)"
git push
```

### Single day (`run_daily.py`)

`run_daily.py` remains the one-day tool. It downloads the GRIB, discovers the EU reference,
renders the 4 maps, and **prints** a ready-to-paste DATA entry (it does not modify `index.html`).

```bash
.venv/bin/python scripts/run_daily.py 2026-06-28
# → paste the printed DATA entry into index.html, then commit + push (as above).
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
