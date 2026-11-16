"""How the automatic tests are split over parallel jobs on GitHub (task 0036).

    python tools/ci_groups.py                 # the pytest groups and the real-app groups, with expected minutes

pytest: every `tests/test_*.py` file goes into one of PYTEST_GROUPS groups, balanced by the seconds recorded
for it in `tools/ci_times.json` (the slowest of the last three runs, `ci_status.py --record`) (longest first, each into the lightest group). A new file without a
recorded time counts NEW_FILE_SECS until its time is recorded (`python3 tools/ci_status.py --record`), so
no file is ever left out. The packaged self-test (built zip installed into Blender, ~100 s) is placed the
same way, as one more item; it runs after the group's tests.

Demo (task 0145): the test files that check the made demo project (they import `tests/demo_made.py`) go into
DEMO_GROUPS groups of their own, "demo 1" …, balanced the same way. On GitHub one job makes the demo project once
("Linux - make the demo project") and these groups' jobs take it from there (`.github/workflows/tests.yml`).

Real app: the groups are the list `GROUPS` in `tools/ci_real_app.py` (kept by hand, next to MIN_CHECKS).
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMES = os.path.join(ROOT, "tools", "ci_times.json")
PYTEST_GROUPS = 9                                  # task 0063: 4 groups took 8-14 min; task 0108: 7 groups 7-14 min, 9 plan ~10 (slowest of 3 runs)
DEMO_GROUPS = 4                                    # task 0145: the demo's checks (~35 + ~20 min) after one make
DEMO_MARK = "demo_made"                            # a test file that opens the shared made demo imports this module
NEW_FILE_SECS = 30.0
SELFTEST = "packaged self-test"


def load_times(path: str = TIMES) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def test_files(root: str = ROOT) -> list[str]:
    """Every pytest file, as 'tests/test_x.py'."""
    return sorted(os.path.relpath(p, root).replace(os.sep, "/") for p in glob.glob(os.path.join(root, "tests", "test_*.py")))


def demo_files(files: list[str], root: str = ROOT) -> list[str]:
    """The files among ``files`` that check the shared made demo project (``import demo_made`` / ``from demo_made``)."""
    out = []
    for f in files:
        try:
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        if f"import {DEMO_MARK}" in text or f"from {DEMO_MARK} import" in text:
            out.append(f)
    return out


def pytest_groups(files: list[str], secs: dict[str, float], n: int = PYTEST_GROUPS,
                  selftest_secs: float | None = None, selftest: bool = True, prefix: str = "") -> list[dict]:
    """[{"name": "1", "files": [...], "selftest": bool, "secs": float}], n groups, every file in exactly one.

    Longest-first into the lightest group; ties broken by name so the split is the same on every machine."""
    groups = [{"name": prefix + str(i + 1), "files": [], "selftest": False, "secs": 0.0} for i in range(n)]
    cost = dict(secs)
    if selftest_secs is not None:
        cost[SELFTEST] = selftest_secs
    cost.setdefault(SELFTEST, 100.0)
    items = sorted(list(files) + ([SELFTEST] if selftest else []), key=lambda f: (-float(cost.get(f, NEW_FILE_SECS)), f))
    for f in items:
        g = min(groups, key=lambda g: (g["secs"], g["name"]))
        if f == SELFTEST:
            g["selftest"] = True
        else:
            g["files"].append(f)
        g["secs"] += float(cost.get(f, NEW_FILE_SECS))
    for g in groups:
        g["files"].sort()
    return [g for g in groups if g["files"] or g["selftest"]]


def matrix_pytest(times: dict | None = None, root: str = ROOT) -> list[dict]:
    """The plain pytest groups: every test file except the demo's (``matrix_demo``)."""
    times = load_times() if times is None else times
    secs = times.get("pytest_files", {})
    files = test_files(root)
    demo = set(demo_files(files, root))
    return [{"name": g["name"], "files": " ".join(g["files"]), "selftest": g["selftest"],
             "minutes": round(g["secs"] / 60, 1)} for g in pytest_groups([f for f in files if f not in demo], secs)]


def matrix_demo(times: dict | None = None, root: str = ROOT) -> list[dict]:
    """The demo groups (task 0145): the files that check the made demo project, after the job that makes it."""
    times = load_times() if times is None else times
    secs = times.get("pytest_files", {})
    return [{"name": g["name"], "files": " ".join(g["files"]), "selftest": False, "minutes": round(g["secs"] / 60, 1)}
            for g in pytest_groups(demo_files(test_files(root), root), secs, n=DEMO_GROUPS, selftest=False,
                                   prefix="demo ")]


def matrix_real_app() -> list[dict]:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ci_real_app
    return [{"name": k, "tests": ",".join(v)} for k, v in ci_real_app.GROUPS.items()]


def main() -> int:
    for g in matrix_pytest():
        print(f"pytest {g['name']}: ~{g['minutes']} min{' + packaged self-test' if g['selftest'] else ''}: {g['files']}")
    for g in matrix_demo():
        print(f"pytest {g['name']} (after the demo is made): ~{g['minutes']} min: {g['files']}")
    for g in matrix_real_app():
        print(f"real app {g['name']}: {g['tests']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
