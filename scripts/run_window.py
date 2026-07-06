"""
run_window.py — windowed daily driver for Hotter-Than-France.

Processes a sliding window of dates [anchor-back .. anchor+ahead] in one pass:
refresh recent actual days AND publish a few forecast days ahead, then inject every
resulting entry into index.html's ``var DATA=[...]`` array (replace-or-insert by date),
behind a node parse-check safety harness.

It shares ONE code path with run_daily.py via ``process_day`` / ``format_entry`` — there
is no duplicated formatting logic here.

Usage
-----
  .venv/bin/python scripts/run_window.py                       # back 2, ahead 3, anchor today
  .venv/bin/python scripts/run_window.py --back 8 --ahead 3    # backfill
  .venv/bin/python scripts/run_window.py --date 2026-07-06     # pin the anchor
  .venv/bin/python scripts/run_window.py --dry-run             # plan only, no fetch/render/write
  .venv/bin/python scripts/run_window.py --skip-existing       # only dates absent from DATA

Forecast days
-------------
Any date beyond the anchor's model run is fetched via the loader's forecast-offset path and
its DATA entry gets ``fcst:1``. Because injection replaces WHOLE lines keyed by date, re-running
the window after that date has passed silently upgrades the forecast line to an actual entry
(the new grid has offset 0, so no ``fcst`` flag is emitted).
"""
from __future__ import annotations

import re
import sys
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import date as _date, timedelta as _timedelta

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.loaders.ecmwf_opendata import MAX_OFFSET_DAYS, today_utc
from scripts.run_daily import process_day, format_entry

_INDEX_HTML = _PROJECT_ROOT / 'index.html'
_NODE = Path('/opt/homebrew/bin/node')

# Match the opening of the DATA array and the first "];" that closes it.
_DATA_OPEN_RE  = re.compile(r'(^[ \t]*var\s+DATA\s*=\s*\[[ \t]*)$', re.MULTILINE)
_DATE_KEY_RE   = re.compile(r"date:\s*'(\d{4}-\d{2}-\d{2})'")


# ---------------------------------------------------------------------------
# DATA-block injection (pure string surgery — no fetch, fully unit-testable)
# ---------------------------------------------------------------------------
class DataBlockError(RuntimeError):
    pass


def _split_data_block(html: str):
    """Return (prefix, open_line, body_lines, close_line, suffix) for the DATA array.

    prefix / suffix   : text before the opening line / after the closing line (byte-preserved)
    open_line         : the 'var DATA = [' line (without its trailing newline)
    body_lines        : list of raw entry lines between open and close (no trailing newlines)
    close_line        : the '];' line (without its trailing newline)

    Only the DATA array is touched; everything else in the file is preserved byte-for-byte.
    """
    m = _DATA_OPEN_RE.search(html)
    if not m:
        raise DataBlockError("could not locate 'var DATA = [' opening line")
    open_start = m.start()
    open_end   = m.end()  # end of the open-bracket line content (before newline)

    # Find the closing '];' at the start of a line after the open.
    close_re = re.compile(r'^[ \t]*\];', re.MULTILINE)
    cm = close_re.search(html, open_end)
    if not cm:
        raise DataBlockError("could not locate closing '];' for the DATA array")

    prefix    = html[:open_start]
    open_line = html[open_start:open_end]
    between   = html[open_end:cm.start()]     # includes leading newline after '['
    close_ln  = html[cm.start():cm.end()]
    suffix    = html[cm.end():]

    # body: strip the leading newline that follows the '[' line, then split on newlines.
    if between.startswith('\r\n'):
        between = between[2:]
    elif between.startswith('\n'):
        between = between[1:]
    # Drop a single trailing newline right before '];' so we don't create a phantom blank entry.
    body = between.rstrip('\n')
    body_lines = body.split('\n') if body else []
    # Keep only non-empty entry lines (an all-whitespace line is not an entry).
    body_lines = [ln for ln in body_lines if ln.strip()]
    return prefix, open_line, body_lines, close_ln, suffix


def _entry_indent(body_lines):
    """Infer the per-entry indentation from existing lines (default 2 spaces)."""
    for ln in body_lines:
        stripped = ln.lstrip(' \t')
        if stripped.startswith('{'):
            return ln[:len(ln) - len(stripped)]
    return '  '


def inject_entries(html: str, entries: list[dict]) -> str:
    """Replace-or-insert each entry (keyed by date) into the DATA array.

    - Existing entry lines whose date is NOT in ``entries`` are preserved BYTE-FOR-BYTE
      (only trailing-comma normalisation applies, which is a no-op for a well-formed array).
    - A date already present is replaced by the freshly formatted line.
    - A new date is inserted so the array stays in ascending date order.
    - Idempotent: injecting the same entries twice yields an identical string.

    Raises DataBlockError if the array contains a non-entry line (no ``date:'...'`` key),
    which would make byte-preservation ambiguous — this file format never has one.
    """
    prefix, open_line, body_lines, close_line, suffix = _split_data_block(html)
    indent = _entry_indent(body_lines)

    # date -> raw existing line. Every line in this array MUST be a dated entry.
    by_date: dict[str, str] = {}
    for ln in body_lines:
        dm = _DATE_KEY_RE.search(ln)
        if not dm:
            raise DataBlockError(
                f"unexpected non-entry line inside DATA array: {ln.strip()!r}")
        by_date[dm.group(1)] = ln.rstrip().rstrip(',').rstrip()

    # Replace-or-insert the new entries (keyed by date).
    for e in entries:
        by_date[e['date']] = indent + format_entry(e)

    # Emit in ascending date order; comma on all but the last.
    ordered = sorted(by_date)
    lines_out = []
    for i, d in enumerate(ordered):
        core = by_date[d].rstrip().rstrip(',').rstrip()
        lines_out.append(core + (',' if i < len(ordered) - 1 else ''))

    body_text = '\n'.join(lines_out)
    return f"{prefix}{open_line}\n{body_text}\n{close_line}{suffix}"


# ---------------------------------------------------------------------------
# Safety harness: extract the <script> block and node-parse it
# ---------------------------------------------------------------------------
def _extract_script_block(html: str) -> str:
    """Return the content of the LAST <script>...</script> block (the DATA/i18n one)."""
    blocks = re.findall(r'<script\b[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    if not blocks:
        raise DataBlockError("no <script> block found for parse-check")
    return blocks[-1]


def node_parse_check(html: str) -> tuple[bool, str]:
    """Parse-check the page's <script> block with node (new Function(...)).

    Returns (ok, message). Uses new Function so top-level `return`-free code compiles
    without executing DOM calls.
    """
    if not _NODE.exists():
        return False, f"node not found at {_NODE}"
    script = _extract_script_block(html)
    # Feed the script to node on stdin; compile via new Function to catch syntax errors
    # (incl. smart-quote delimiters) WITHOUT running the browser-only code.
    harness = (
        "let s='';process.stdin.setEncoding('utf8');"
        "process.stdin.on('data',d=>s+=d);"
        "process.stdin.on('end',()=>{try{new Function(s);"
        "console.log('PARSE_OK');}catch(e){"
        "console.error('PARSE_FAIL: '+e.message);process.exit(3);}});"
    )
    try:
        r = subprocess.run(
            [str(_NODE), '-e', harness],
            input=script, capture_output=True, text=True, timeout=30,
        )
    except Exception as ex:
        return False, f"node invocation failed: {ex}"
    out = (r.stdout or '') + (r.stderr or '')
    return (r.returncode == 0 and 'PARSE_OK' in r.stdout), out.strip()


def _safe_write_index(new_html: str) -> None:
    """Write index.html behind a .bak + node parse-check harness.

    On parse failure: restore the backup, print a loud error, raise SystemExit(1).
    On success: delete the .bak.
    """
    bak = _INDEX_HTML.with_suffix('.html.bak')
    # 1. backup current file
    shutil.copy2(str(_INDEX_HTML), str(bak))
    try:
        # 2. write new content
        _INDEX_HTML.write_text(new_html, encoding='utf-8')
        # 3. parse-check what we just wrote (read it back from disk)
        on_disk = _INDEX_HTML.read_text(encoding='utf-8')
        ok, msg = node_parse_check(on_disk)
        if not ok:
            # restore
            shutil.copy2(str(bak), str(_INDEX_HTML))
            print('\n' + '!' * 72)
            print('INJECTION ABORTED — node parse-check FAILED. index.html RESTORED from backup.')
            print('!' * 72)
            print(msg)
            raise SystemExit(1)
    finally:
        # delete backup on success (on failure we already restored; still remove the .bak)
        if bak.exists():
            try:
                bak.unlink()
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Window planning
# ---------------------------------------------------------------------------
def existing_dates(html: str) -> set[str]:
    _, _, body_lines, _, _ = _split_data_block(html)
    dates = set()
    for ln in body_lines:
        dm = _DATE_KEY_RE.search(ln)
        if dm:
            dates.add(dm.group(1))
    return dates


def plan_window(anchor: _date, back: int, ahead: int, today: _date):
    """Return (dates, clamped_ahead, warning_or_None).

    ahead is clamped so no date exceeds ``today + MAX_OFFSET_DAYS`` (the mx2t3 horizon).
    The clamp is computed relative to TODAY (the newest run), not the anchor.
    """
    warning = None
    max_ahead_date = today + _timedelta(days=MAX_OFFSET_DAYS)
    requested_end = anchor + _timedelta(days=ahead)
    clamped_ahead = ahead
    if requested_end > max_ahead_date:
        # reduce ahead so anchor+ahead == max_ahead_date (never negative)
        clamped_ahead = max(0, (max_ahead_date - anchor).days)
        warning = (
            f"--ahead {ahead} would reach {requested_end.isoformat()}, beyond the mx2t3 "
            f"forecast horizon {max_ahead_date.isoformat()} (today {today.isoformat()} + "
            f"{MAX_OFFSET_DAYS}d). Clamping ahead to {clamped_ahead} "
            f"(last date {(anchor + _timedelta(days=clamped_ahead)).isoformat()})."
        )
    start = anchor - _timedelta(days=back)
    end = anchor + _timedelta(days=clamped_ahead)
    dates = []
    d = start
    while d <= end:
        dates.append(d)
        d += _timedelta(days=1)
    return dates, clamped_ahead, warning


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--back', type=int, default=2,
                        help='Days before the anchor to (re)process (default 2).')
    parser.add_argument('--ahead', type=int, default=3,
                        help='Days after the anchor to forecast (default 3; clamped to horizon).')
    parser.add_argument('--date', default=None,
                        help='Anchor date YYYY-MM-DD (default: today UTC).')
    parser.add_argument('--dry-run', action='store_true',
                        help='List planned actions; no fetch/render/write.')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Only process dates absent from DATA (default: refresh all in window).')
    parser.add_argument('--target', type=float, default=0.8,
                        help='Discovery display threshold %% (default 0.8).')
    args = parser.parse_args(argv)

    today = today_utc()
    anchor = _date.fromisoformat(args.date) if args.date else today

    dates, clamped_ahead, warning = plan_window(anchor, args.back, args.ahead, today)

    html = _INDEX_HTML.read_text(encoding='utf-8')
    have = existing_dates(html)

    print('=' * 72)
    print(f'Hotter-Than-France — windowed driver')
    print(f'  anchor={anchor.isoformat()}  today(UTC)={today.isoformat()}  '
          f'back={args.back}  ahead={args.ahead}'
          + (f' → clamped {clamped_ahead}' if clamped_ahead != args.ahead else ''))
    print('=' * 72)
    if warning:
        print(f'\n[warn] {warning}\n')

    # Build the plan table.
    plan = []
    for d in dates:
        ds = d.isoformat()
        offset_days = max(0, (d - today).days)
        is_fcst = offset_days > 0
        in_data = ds in have
        action = 'process'
        if args.skip_existing and in_data:
            action = 'skip (in DATA)'
        plan.append((ds, is_fcst, in_data, action))

    print('Planned window:')
    print(f'  {"date":<12} {"kind":<10} {"in DATA":<8} {"action"}')
    print(f'  {"-"*12} {"-"*10} {"-"*8} {"-"*16}')
    for ds, is_fcst, in_data, action in plan:
        print(f'  {ds:<12} {"forecast" if is_fcst else "actual":<10} '
              f'{"yes" if in_data else "no":<8} {action}')

    if args.dry_run:
        print(f'\n[dry-run] {sum(1 for _,_,_,a in plan if a=="process")} day(s) would be processed, '
              f'{sum(1 for _,_,_,a in plan if a!="process")} skipped. No files touched.')
        print('=' * 72)
        return 0

    # -- Execute -------------------------------------------------------------
    ok_days, failed_days, skipped_days = [], [], []
    new_entries = []
    for ds, is_fcst, in_data, action in plan:
        if action != 'process':
            skipped_days.append(ds)
            print(f'\n[skip] {ds} (already in DATA)')
            continue
        print(f'\n[proc] {ds} ({"forecast" if is_fcst else "actual"}) ...')
        try:
            entry = process_day(ds, args.target, render=True, today=today)
            new_entries.append(entry)
            ok_days.append(ds)
            tag = ' [fcst]' if entry.get('fcst') else ''
            print(f'  → {entry["refEn"]} {entry["refMaxC"]}°C  '
                  f'planet {entry["planetPct"]}%{tag}')
        except Exception as ex:
            failed_days.append((ds, f'{type(ex).__name__}: {ex}'))
            print(f'  [FAIL] {ds}: {type(ex).__name__}: {ex}')
            continue

    # -- Inject (only if we produced entries) --------------------------------
    if new_entries:
        print(f'\n[inject] merging {len(new_entries)} entr(y/ies) into index.html ...')
        current = _INDEX_HTML.read_text(encoding='utf-8')
        # Strip internal side-fields before formatting is handled inside format_entry;
        # inject_entries calls format_entry which ignores the _-prefixed keys.
        merged = inject_entries(current, new_entries)
        if merged == current:
            print('  (no change — index.html already up to date; idempotent no-op)')
        else:
            _safe_write_index(merged)
            print('  index.html updated + node parse-check PASSED (.bak removed).')
    else:
        print('\n[inject] nothing to inject.')

    # -- Summary -------------------------------------------------------------
    print(f'\n{"=" * 72}')
    print('WINDOW SUMMARY')
    print(f'  OK      ({len(ok_days)}): {", ".join(ok_days) or "—"}')
    print(f'  SKIPPED ({len(skipped_days)}): {", ".join(skipped_days) or "—"}')
    print(f'  FAILED  ({len(failed_days)}): '
          + (", ".join(f"{d} ({why})" for d, why in failed_days) or "—"))
    print('=' * 72)
    return 0 if not failed_days else 2


if __name__ == '__main__':
    sys.exit(main())
