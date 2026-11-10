"""Which PC-check lines (Full) run where on GitHub (task 0063).

The PC check (Full) takes about 10 minutes (the video and queue lines render for minutes). It runs in full on
Linux, as two parallel real-app jobs (`pccheck`, `pccheck2`); the Windows job runs the same lines minus the
slow ones that only test the app itself (same code as on Linux, nothing Windows-specific), because the
Windows job started after the build and was the longest of all.

    python tools/ci_pccheck_lines.py linux1      # comma-separated line ids of Linux job `pccheck`
    python tools/ci_pccheck_lines.py linux2      # ... of `pccheck2`
    python tools/ci_pccheck_lines.py windows     # ... of the Windows job (all Full lines minus WINDOWS_SKIPS)
    python tools/ci_pccheck_lines.py count windows
    python tools/ci_pccheck_lines.py             # a table

The ids are read from `fresing_render/pccheck/checks.py` without importing it (no Blender needed). The precheck
(tools/ci_precheck.py) fails when the two Linux halves do not add up to every Full line, or when a name here
is no line any more: a line can never silently stop running everywhere.
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHECKS = os.path.join(ROOT, "fresing_render", "pccheck", "checks.py")

# Linux job `pccheck2`: the two longest lines (video with labels ~3 min on Windows' CPU, the queue's time test).
LINUX2 = ("video.labels", "queue.time_test")
# Not run on Windows (they run on Linux, in `pccheck` / `pccheck2`): long renders of the app's own code. The
# Windows-specific parts stay: install, start, import, a CPU render, the queue's background Blender (queue.frame_shown),
# the update check, the launch from the Start-menu shortcut and the report.
WINDOWS_SKIPS = ("video.labels", "queue.time_test", "queue.video", "scene.turntable", "tour.make",
                 "looks.materials", "milling.coolant")


def full_ids(path: str = CHECKS) -> list[str]:
    """Ids of the lines that are in mode Full (`F`), in file order."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = {"Q": "quick", "F": "full", "OWN": "own", "H": "heavy"}
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for dec in node.decorator_list:
            if not (isinstance(dec, ast.Call) and getattr(dec.func, "id", "") == "line" and dec.args
                    and isinstance(dec.args[0], ast.Constant)):
                continue
            modes = ["full"]                          # the default of @line
            node_modes = dec.args[3] if len(dec.args) > 3 else next((k.value for k in dec.keywords if k.arg == "modes"), None)
            if node_modes is not None:
                modes = [names.get(getattr(e, "id", ""), "") for e in getattr(node_modes, "elts", [])]
            if "full" in modes:
                out.append((dec.lineno, dec.args[0].value))
    return [i for _n, i in sorted(out)]


def ids_for(job: str, full: list[str] | None = None) -> list[str]:
    full = full_ids() if full is None else full
    if job == "linux2":
        return [i for i in full if i in LINUX2]
    if job == "linux1":
        return [i for i in full if i not in LINUX2]
    if job == "windows":
        return [i for i in full if i not in WINDOWS_SKIPS]
    raise SystemExit(f"unknown job {job!r} (linux1, linux2, windows)")


def problems(full: list[str] | None = None) -> list[str]:
    full = full_ids() if full is None else full
    out = []
    for name, group in (("LINUX2", LINUX2), ("WINDOWS_SKIPS", WINDOWS_SKIPS)):
        gone = [i for i in group if i not in full]
        if gone:
            out.append(f"{name} in tools/ci_pccheck_lines.py names {', '.join(gone)}, which is no PC-check line (Full) any more")
    if not set(ids_for("linux1", full)) | set(ids_for("linux2", full)) == set(full):
        out.append("the Linux PC-check jobs do not add up to every Full line")
    if not set(WINDOWS_SKIPS) <= set(LINUX2) | set(ids_for("linux1", full)):
        out.append("a line skipped on Windows does not run on Linux")
    return out


def main(argv: list[str]) -> int:
    full = full_ids()
    if argv[:1] == ["count"] and len(argv) == 2:
        print(len(ids_for(argv[1], full)))
    elif len(argv) == 1:
        print(",".join(ids_for(argv[0], full)))
    else:
        for job in ("linux1", "linux2", "windows"):
            print(f"{job}: {len(ids_for(job, full))} lines")
        print("skipped on Windows:", ", ".join(WINDOWS_SKIPS))
        for p in problems(full):
            print("PROBLEM:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
