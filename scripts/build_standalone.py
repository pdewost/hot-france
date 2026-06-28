#!/usr/bin/env python3
"""build_standalone.py — produce a single self-contained HTML page.

Reads index.html + every assets/maps/hotter_than_*.png, base64-inlines
the maps into a `window.MAP_B64` lookup injected before </head>, and writes
hot-france-standalone.html — one portable file (open it anywhere, no server, no assets folder).

The page's renderDays() prefers window.MAP_B64[<key>] when present, and falls
back to the assets/maps/ path otherwise — so the same index.html works both served and standalone.

Key format: {iso3}_{date}_{theme}_{lang}   e.g. deu_2026-06-27_dark_en

Usage: python3 scripts/build_standalone.py
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / "assets" / "maps"
SRC = ROOT / "index.html"
DEST = ROOT / "hot-france-standalone.html"


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found", file=sys.stderr)
        return 1
    pngs = sorted(MAPS.glob("hotter_than_*.png"))
    if not pngs:
        print(f"ERROR: no map PNGs in {MAPS}", file=sys.stderr)
        return 1

    html = SRC.read_text(encoding="utf-8")

    entries = []
    for p in pngs:
        key = p.stem.replace("hotter_than_", "")  # {iso3}_{date}_{theme}_{lang}
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        entries.append('"%s":"data:image/png;base64,%s"' % (key, b64))
    inject = "<script>window.MAP_B64={" + ",".join(entries) + "};</script>"

    if "</head>" not in html:
        print("ERROR: no </head> in index.html to inject before", file=sys.stderr)
        return 1
    out = html.replace("</head>", inject + "\n</head>", 1)

    DEST.write_text(out, encoding="utf-8")
    mb = DEST.stat().st_size / 1e6
    print(f"Wrote {DEST}")
    print(f"  {len(entries)} maps inlined · {mb:.1f} MB self-contained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
