"""How the automatic tests are split over parallel jobs on GitHub (task 0036).

    python tools/ci_groups.py                 # the pytest groups and the real-app groups, with expected minutes

pytest: every `tests/test_*.py` file goes into one of PYTEST_GROUPS groups, balanced by the seconds recorded
for it in `tools/ci_times.json` (the slowest of the last three runs, `ci_status.py --record`) (longest first, each into the lightest group). A new file without a
recorded time counts NEW_FILE_SECS until its time is recorded (`python3 tools/ci_status.py --record`), so
no file is ever left out. The packaged self-test (built zip installed into Blender, ~100 s) is placed the
same way, as one more item; it runs after the group's tests.

Real app: the groups are the list `GROUPS` in `tools/ci_real_app.py` (kept by hand, next to MIN_CHECKS).
"""

from __future__ import annotations

import glob
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMES = os.path.join(ROOT, "tools", "ci_times.json")
PYTEST_GROUPS = 8                                  # task 0063: 4 groups took 8-14 min; task 0108: 7 groups took 7-14 min, 8 plan ~11 (slowest of 3 runs)
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


def pytest_groups(files: list[str], secs: dict[str, float], n: int = PYTEST_GROUPS,
                  selftest_secs: float | None = None) -> list[dict]:
    """[{"name": "1", "files": [...], "selftest": bool, "secs": float}], n groups, every file in exactly one.

    Longest-first into the lightest group; ties broken by name so the split is the same on every machine."""
    groups = [{"name": str(i + 1), "files": [], "selftest": False, "secs": 0.0} for i in range(n)]
    cost = dict(secs)
    if selftest_secs is not None:
        cost[SELFTEST] = selftest_secs
    cost.setdefault(SELFTEST, 100.0)
    items = sorted(list(files) + [SELFTEST], key=lambda f: (-float(cost.get(f, NEW_FILE_SECS)), f))
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
    times = load_times() if times is None else times
    secs = times.get("pytest_files", {})
    return [{"name": g["name"], "files": " ".join(g["files"]), "selftest": g["selftest"],
             "minutes": round(g["secs"] / 60, 1)} for g in pytest_groups(test_files(root), secs)]


def matrix_real_app() -> list[dict]:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ci_real_app
    return [{"name": k, "tests": ",".join(v)} for k, v in ci_real_app.GROUPS.items()]


def main() -> int:
    for g in matrix_pytest():
        print(f"pytest {g['name']}: ~{g['minutes']} min{' + packaged self-test' if g['selftest'] else ''}: {g['files']}")
    for g in matrix_real_app():
        print(f"real app {g['name']}: {g['tests']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
