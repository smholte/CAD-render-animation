"""Judge a PC check run for the automatic tests on GitHub (task 0032).

    python tools/ci_check_pccheck.py <last_run.txt> [--title "Windows PC check"] [--min-lines 27]

Reads the text block the PC check writes next to its history (<settings>/config/fresing_pccheck/
last_run.txt, the same text the owner copies into the lead chat). Passes (exit code 0) when:
  - the run finished (no "DID NOT FINISH"),
  - no line FAILED,
  - every skipped line says "no graphics card" (GitHub's runners have none) - a line skipped because
    the line it needs failed, or for any other reason, is a problem,
  - there are at least --min-lines lines (a line that silently disappears fails).
The verdict goes to the console, the GitHub job summary and error annotations.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

ROW = re.compile(r"^(?:NEW )?\[(?P<tag> OK |FAIL|SKIP)\] (?P<id>[\w.]+) (?P<secs>[\d.]+) s(?P<rest>.*)$")
ALLOWED_SKIP = "no graphics card"
MIN_LINES_FULL = 48          # raise it when the check gets new lines
MIN_LINES_HEAVY = 11         # the Heavy lines (task 0033)
MIN_LINES_TOUR = 32          # the test tour: Make test tour project + one line per stop (task 0059)


def judge(text: str, min_lines: int = MIN_LINES_FULL) -> tuple[list[tuple[str, str, str, str]], list[str]]:
    """Return (rows, problems). Rows: (state, line id, seconds, detail)."""
    rows, problems = [], []
    lines = text.splitlines()
    if not lines or not lines[0].startswith("Fresing Render PC check"):
        return rows, ["no PC check text block (the check did not run or did not finish)"]
    if "DID NOT FINISH" in lines[0]:
        problems.append("the PC check did not finish")
    for ln in lines:
        m = ROW.match(ln)
        if not m:
            continue
        tag, lid, secs, rest = m.group("tag"), m.group("id"), m.group("secs"), m.group("rest")
        detail = rest.split("|", 1)[1].strip() if "|" in rest else ""
        if tag == "FAIL":
            rows.append(("FAILED", lid, secs, detail))
            problems.append(f"{lid}: {detail}")
        elif tag == "SKIP":
            ok = ALLOWED_SKIP in detail
            rows.append(("skipped" if ok else "SKIP not allowed", lid, secs, detail))
            if not ok:
                problems.append(f"{lid} skipped: {detail}")
        else:
            rows.append(("OK", lid, secs, detail))
    if len(rows) < min_lines:
        problems.append(f"only {len(rows)} lines, at least {min_lines} expected")
    return rows, problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("block")
    ap.add_argument("--title", default="PC check")
    ap.add_argument("--min-lines", type=int, default=MIN_LINES_FULL)
    args = ap.parse_args(argv)
    try:
        with open(args.block, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        text = ""
        print(f"cannot read {args.block}: {exc}")
    rows, problems = judge(text, args.min_lines)
    out = [f"### {args.title}: {'FAILED' if problems else 'passed'}", "", "| Line | Result | Time | Detail |",
           "| --- | --- | --- | --- |"]
    for state, lid, secs, detail in rows:
        mark = "✅" if state == "OK" else ("⏭️" if state == "skipped" else "❌")
        out.append(f"| {lid} | {mark} {state} | {secs} s | {detail.replace('|', '/')[:150]} |")
    if problems:
        out += ["", "**Problems:**", ""] + [f"- {p}" for p in problems]
    summary = "\n".join(out) + "\n"
    print(text)
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    for p in problems:
        print(f"::error title={args.title}::{p}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
