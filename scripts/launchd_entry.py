#!/usr/bin/env python3
"""launchd entry for com.hotfrance.daily.

python3.12 (Full Disk Access) reads daily_update.sh; bash receives the text via -c and never
opens a pre-existing ~/Documents file itself (bash EPERM 07-07..07-09). $0 is passed as the real
script path so the script's ROOT= line still resolves. The plist declares no Standard*Path —
launchd reopening its own fixed logs is what caused exit 78 from 07-10 on.
See NEOCORTEX/INCIDENT_launchd_daily_dead_2026-09-28.md.
"""
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path(__file__).resolve().parent / "daily_update.sh"
sys.exit(subprocess.run(["/bin/bash", "-c", SCRIPT.read_text(), str(SCRIPT)],
                        cwd=SCRIPT.parent.parent).returncode)
