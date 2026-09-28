# CLAUDE.md — Hotter-Than-France

## Cold-start read order (NEOCORTEX_SPEC v1.0, PAICodeConstitution-2026)

`NEOCORTEX/MANIFEST.json` → `NEOCORTEX/STATUS.md` → active plans.
Constitution: `../PAICodeConstitution-2026.md`.
State is untracked: `NEOCORTEX/` is gitignored (since 2026-09-28). This repo HAS a public remote
(`pdewost/hot-france`), so it must stay ignored (Art. 5); backup = Time Machine.
Validator: `python3 governance/adapters/claude-code/neocortex_manifest.py --check <project_dir>`

## Runtime

All scripts require the project venv: `.venv/bin/python scripts/run_daily.py [YYYY-MM-DD]`
Never use bare `python3` — it lacks xarray/cartopy/ecmwf-opendata.
