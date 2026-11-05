"""Judge a self-test report for the automatic tests on GitHub (and print it readably).

    python tools/ci_check_selftest.py <report.txt> [--title "Windows self-test"] [--strict]

Passes (exit code 0) when:
  - every check line is "[ OK ]", except graphics-card checks, which may be
    "[SKIP] ...: skipped: no graphics card" (GitHub's runners have no graphics card; the
    self-test only skips them when FRESING_SELFTEST_NO_GPU=1 is set);
  - the report ends with "RESULT: ALL OK" (no RESULT line = the self-test crashed half-way);
  - there are at least MIN_CHECKS checks (a check that silently disappears fails);
  - with --strict (the real Windows install) no OK line may say "skipped" either: there the
    "App start" check must really start the app.

The verdict is printed as a table, written to the GitHub job summary ($GITHUB_STEP_SUMMARY)
and every problem becomes an error annotation on the run page.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

MIN_CHECKS = 13          # raise it when the self-test gets new lines
LINE = re.compile(r"^\[(?P<tag> OK |FAIL|SKIP)\] (?P<rest>.*)$")
OK_REST = re.compile(r"^(?P<name>.*?) \((?P<secs>[\d.]+) s\)(?:: (?P<detail>.*))?$")
ALLOWED_SKIP = re.compile(r"graphics card", re.I)
SKIP_TEXT = "skipped: no graphics card"


def judge(text: str, strict: bool = False) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return (rows, problems). Rows are (state, check name, detail)."""
    rows: list[tuple[str, str, str]] = []
    problems: list[str] = []
    result = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("RESULT:"):
            result = line[len("RESULT:"):].strip()
            continue
        m = LINE.match(line)
        if not m:
            continue
        tag, rest = m.group("tag"), m.group("rest")
        if tag == " OK ":
            ok = OK_REST.match(rest)
            if ok:
                rows.append(("OK", ok.group("name"), f"{ok.group('secs')} s" +
                             (f": {ok.group('detail')}" if ok.group("detail") else "")))
                if strict and (ok.group("detail") or "").startswith("skipped"):
                    problems.append(f"{ok.group('name')}: {ok.group('detail')} (must really run here)")
            else:
                rows.append(("OK", rest, ""))
        elif tag == "SKIP":
            name, _, detail = rest.partition(": ")
            if ALLOWED_SKIP.search(name) and SKIP_TEXT in detail:
                rows.append(("skipped", name, detail))
            else:
                rows.append(("SKIP not allowed", name, detail))
                problems.append(f"{name}: skipped, but only the graphics-card checks may be skipped ({detail})")
        else:
            name, _, detail = rest.partition(": ")
            rows.append(("FAIL", name, detail))
            problems.append(f"{name}: {detail}")
    if result is None:
        problems.append("no RESULT line: the self-test stopped half-way (crash or timeout); see the log")
    elif not result.startswith("ALL OK"):
        if not any(r[0] == "FAIL" for r in rows):
            problems.append(f"RESULT says: {result}")
    if len(rows) < MIN_CHECKS:
        problems.append(f"only {len(rows)} checks ran (expected at least {MIN_CHECKS})")
    return rows, problems


def _summary(title: str, rows, problems) -> str:
    out = [f"### {title}: {'passed' if not problems else 'FAILED'}", "",
           "| Check | Result | Detail |", "| --- | --- | --- |"]
    for state, name, detail in rows:
        mark = {"OK": "✅ OK", "skipped": "⏭️ skipped", "FAIL": "❌ FAIL"}.get(state, "❌ " + state)
        detail = detail.replace("|", "\\|")
        if len(detail) > 160:
            detail = detail[:157] + "..."
        out.append(f"| {name} | {mark} | {detail} |")
    if problems:
        out += ["", "**Problems:**", ""] + [f"- {p}" for p in problems]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--title", default="Self-test")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.isfile(args.report):
        msg = f"report not found: {args.report} (the self-test did not start or could not write it)"
        print(f"::error title={args.title}::{msg}")
        _write_summary(f"### {args.title}: FAILED\n\n{msg}\n")
        return 1
    with open(args.report, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    print(f"----- {args.report} -----")
    print(text)
    print("-" * 40)
    rows, problems = judge(text, strict=args.strict)
    summary = _summary(args.title, rows, problems)
    print(summary)
    _write_summary(summary)
    for p in problems:
        print(f"::error title={args.title}::{p}")
    return 1 if problems else 0


def _write_summary(text: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    sys.exit(main())
