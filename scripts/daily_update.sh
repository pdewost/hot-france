#!/usr/bin/env bash
# daily_update.sh — unattended daily routine for Hotter-Than-France.
#
# Run by launchd (com.hotfrance.daily) every day at 10:30 Europe/Paris —
# late enough that ECMWF's 00z run is published (~07-08 UTC); if it isn't,
# the loader falls back to yesterday's run and tags the day fcst:1.
# launchd never runs this file directly: it goes through scripts/launchd_entry.py
# (python3.12 reads it, bash gets the text) — bash reading it itself gets EPERM.
#
# Steps: run_window.py (defaults: back 2 / ahead 3) → commit+push if changed
# → post-push audit (tested scripts, per workspace domain rule #4) → iMessage
# ping (handle from workspace .notify.yaml — NEVER hardcoded here, §16).
#
# Deliberately NOT rebuilt daily: hot-france-standalone.html (~17 MB — daily
# commits would bloat git history; rebuild manually when sharing the file).
#
# Manual run: bash scripts/daily_update.sh
# Logs: logs/daily_update_YYYYMMDD.log (gitignored)

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

LOGDIR="${ROOT}/logs"
mkdir -p "${LOGDIR}"
LOG="${LOGDIR}/daily_update_$(date +%Y%m%d).log"
exec >>"${LOG}" 2>&1

echo "======================================================================"
echo "daily_update $(date '+%Y-%m-%d %H:%M:%S %Z')"

# ── Overlap guard (launchd retries, manual runs) ──────────────────────────
LOCKDIR="${ROOT}/.daily_update.lock"
if ! mkdir "${LOCKDIR}" 2>/dev/null; then
  echo "Another run holds ${LOCKDIR} — exiting."
  exit 0
fi
trap 'rmdir "${LOCKDIR}" 2>/dev/null' EXIT

# ── Notification helper (workspace pattern: handle from .notify.yaml) ─────
NOTIFY_YAML="${ROOT}/../../.notify.yaml"
notify() {
  local msg="HotFrance — $1"
  [[ -f "${NOTIFY_YAML}" ]] || { echo "notify skipped (no .notify.yaml): ${msg}"; return 0; }
  local handle
  handle="$(python3 - <<PYEOF
import re, sys
with open("${NOTIFY_YAML}") as f:
    for line in f:
        m = re.match(r'\s*handle:\s*["\x27]?([^\s"]+)["\x27]?', line)
        if m and m.group(1):
            print(m.group(1)); sys.exit(0)
PYEOF
)"
  [[ -n "${handle}" ]] || { echo "notify skipped (empty handle): ${msg}"; return 0; }
  osascript - "${handle}" "${msg}" <<'ASEOF' || echo "notify FAILED to send"
on run {targetHandle, msgBody}
  tell application "Messages"
    set destService to 1st service whose service type = iMessage
    set destBuddy to buddy targetHandle of destService
    send msgBody to destBuddy
  end tell
end run
ASEOF
}

# ── 1. Windowed update (venv python ONLY — never bare python3) ────────────
"${ROOT}/.venv/bin/python" "${ROOT}/scripts/run_window.py"
WINDOW_RC=$?
SUMMARY="$(grep -E '^\s+(OK|SKIPPED|FAILED)\s+\(' "${LOG}" | tail -3 | tr -s ' ' | tr '\n' ' ')"

if [[ ${WINDOW_RC} -ne 0 ]]; then
  echo "run_window exited ${WINDOW_RC}"
  notify "daily window FAILED (exit ${WINDOW_RC}). ${SUMMARY} Log: ${LOG}"
  exit "${WINDOW_RC}"
fi

# ── 2. Commit + push only if the update changed anything ──────────────────
git add index.html assets/maps assets/flags
if git diff --cached --quiet; then
  echo "No changes to commit — site already current."
  notify "daily window OK, no changes (already current). ${SUMMARY}"
  exit 0
fi

git commit -m "data(auto): daily window $(date +%Y-%m-%d)

Automated run_window.py refresh (back 2 / ahead 3) via com.hotfrance.daily.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
if ! git push origin main; then
  echo "git push FAILED"
  notify "daily window rendered OK but git push FAILED. Log: ${LOG}"
  exit 1
fi

# ── 3. Post-push audit (workspace domain rule #4; tested scripts) ─────────
AUDIT_SCRIPT="${ROOT}/../../_skills/github_commit_audit/scripts/post_audit.py"
AUDIT_FAILS=""
if [[ -f "${AUDIT_SCRIPT}" ]] && command -v python3.12 >/dev/null; then
  AUDIT_FAILS="$(python3.12 "${AUDIT_SCRIPT}" --repo-path "${ROOT}" --repo-name hot-france 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); print(', '.join(c['name'] for c in d['checks'] if c['status']=='fail'))" 2>/dev/null)"
  # Known false-positive warns (basename lookup) are ignored; only status=fail alerts.
else
  echo "audit script unavailable — skipped (flagging in notify)"
  AUDIT_FAILS="(audit script unavailable)"
fi

# ── 4. Ping ────────────────────────────────────────────────────────────────
if [[ -n "${AUDIT_FAILS}" ]]; then
  notify "daily window pushed, but audit flags: ${AUDIT_FAILS}. ${SUMMARY}"
else
  notify "daily window pushed ✓ ${SUMMARY}"
fi
echo "daily_update done $(date '+%H:%M:%S')"
