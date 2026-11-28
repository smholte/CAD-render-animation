"""How the automatic tests are split over parallel jobs on GitHub (task 0036).

    python tools/ci_groups.py                 # the pytest groups and the real-app groups, with expected minutes

pytest: every `tests/test_*.py` file goes into one of PYTEST_GROUPS groups, balanced by the seconds recorded
for it in `tools/ci_times.json` (the slowest of the last three runs, `ci_status.py --record`) (longest first, each into the lightest group). A new file without a
recorded time counts NEW_FILE_SECS until its time is recorded (`python3 tools/ci_status.py --record`), so
no file is ever left out. The packaged self-test (built zip installed into Blender, ~100 s) is placed the
same way, as one more item; it runs after the group's tests.

Demo (task 0145): the test files that check the made demo project (they import `tests/demo_made.py`) go into
DEMO_GROUPS groups of their own, "demo 1" …, balanced the same way. On GitHub each such job makes the demo project
first (~1.5 min) and then runs its files (task 0383: the separate make job was one more job for one group).

Order (task 0383): GitHub hands its runners to the jobs that wait in about the order they were queued, so every matrix
lists its slowest group first (`slowest_first`): the run's longest jobs start first when runners are short.

Real app: the groups are the list `GROUPS` in `tools/ci_real_app.py` (kept by hand, next to MIN_CHECKS).

Windows (task 0171): the Windows install test runs as WINDOWS_PARTS, two jobs at once after the build (each installs
what it needs; `tools/ci_windows_install.ps1 -Part a|b`).

Lane runs (task 0171): a branch push whose version is not raised yet (the task is still being built) runs only the
jobs its changed files need: `lane_plan(files)` (`python tools/ci_groups.py --lane <file> …` prints it). A test file
or real-app test is picked when it names a changed module (its file name as a word: `web3d` for `blender/web3d.py`,
`ops_web3d.py`, `core/web3d.py`); shared files (`FULL_FILES`, `FULL_PREFIXES`) and a file that no test names give a
full run instead ("when in doubt, everything"). The PC check and the test tour are never part of a lane run (they
cover every module); they run in the full run that comes with the version raise.
"""

from __future__ import annotations

import glob
import json
import math
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMES = os.path.join(ROOT, "tools", "ci_times.json")
PYTEST_GROUPS = 8                                  # task 0063: 4 groups took 8-14 min; task 0108: 7 groups 7-14 min, 9 plan ~10
                                                   # (slowest of 3 runs); task 0383: 8 – one full run fits GitHub Free's 20
                                                   # jobs at once (8 pytest + 1 demo + the real-app groups + build)
DEMO_GROUPS = 1                                    # task 0145: the demo's checks after one make (task 0247: ~5 min)
DEMO_MARK = "demo_made"                            # a test file that opens the shared made demo imports this module
NEW_FILE_SECS = 30.0
SELFTEST = "packaged self-test"
# Task 0248: test files that skip one test on GitHub's runners by design (each pytest group allows ONE skip,
# ``ci_pytest_summary.py --max-skipped 1``): Blender's meshopt bridge is not there; a crane class without a chart at
# its working pose. Never two of them in one group (a new test file shifted the split and put both in group 2).
SKIPS_ON_GITHUB = {"tests/test_web3d_keys.py", "tests/test_lifting_reach_independent.py",
                   "tests/test_web3d_film_blender.py",    # task 0279: no browser on the Linux runners
                   "tests/test_flex_avoid_independent.py",   # task 0298: one xfail (the summary counts it as a skip)
                   "tests/test_web3d_lead_blender.py",       # task 0310: no browser on GitHub's Linux (found by 0322)
                   "tests/test_web_tools.py",                # no node on GitHub's Linux (task 0368 met it beside 0298's)
                   "tests/test_compat_projects.py"}          # task 0352: no kept test project yet (found by 0354)


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
        pool = groups
        if f in SKIPS_ON_GITHUB:                # (into a group without another one, while there is one)
            pool = [g for g in groups if not SKIPS_ON_GITHUB.intersection(g["files"])] or groups
        g = min(pool, key=lambda g: (g["secs"], g["name"]))
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
    return slowest_first([{"name": g["name"], "files": " ".join(g["files"]), "selftest": g["selftest"],
                           "minutes": round(g["secs"] / 60, 1)}
                          for g in pytest_groups([f for f in files if f not in demo], secs)])


def slowest_first(groups: list[dict]) -> list[dict]:
    """The groups with the most minutes first (task 0383); ties keep their order."""
    return sorted(groups, key=lambda g: -float(g.get("minutes") or 0.0))


def matrix_demo(times: dict | None = None, root: str = ROOT) -> list[dict]:
    """The demo groups (task 0145): the files that check the made demo project, after the job that makes it."""
    times = load_times() if times is None else times
    secs = times.get("pytest_files", {})
    return [{"name": g["name"], "files": " ".join(g["files"]), "selftest": False, "minutes": round(g["secs"] / 60, 1)}
            for g in pytest_groups(demo_files(test_files(root), root), secs, n=DEMO_GROUPS, selftest=False,
                                   prefix="demo ")]


REAL_APP_JOB = "Linux - real app "


def matrix_real_app(times: dict | None = None) -> list[dict]:
    """GROUPS of tools/ci_real_app.py, the group whose recorded job took longest first (task 0383)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ci_real_app
    jobs = (load_times() if times is None else times).get("jobs", {})
    return slowest_first([{"name": k, "tests": ",".join(v), "minutes": jobs.get(REAL_APP_JOB + k, 0.0)}
                          for k, v in ci_real_app.GROUPS.items()])


# ---------------------------------------------------------------------------------------------- Windows parts

WINDOWS_PARTS = [
    {"name": "A", "part": "a", "what": "update, install, icons, self-test, PC check Full, uninstall"},
    {"name": "B", "part": "b", "what": "install, PC check Heavy (scaled down)"},
]


def matrix_windows(parts=("a", "b")) -> list[dict]:
    return [p for p in WINDOWS_PARTS if p["part"] in parts]


# ---------------------------------------------------------------------------------------------- lane runs (task 0171)

# A change in one of these files touches every lane: the run is full.
FULL_FILES = {
    "fresing_render/__init__.py", "fresing_render/blender_manifest.toml", "fresing_render/blender/__init__.py",
    "fresing_render/core/__init__.py", "fresing_render/blender/props.py", "fresing_render/blender/ui.py",
    "fresing_render/blender/reimport.py", "fresing_render/blender/animation.py", "fresing_render/blender/handlers.py",
    "fresing_render/blender/tour.py", "fresing_render/blender/build.py", "fresing_render/blender/ops_tour.py",
    "fresing_render/blender/ui_tour.py", "fresing_render/core/functions.py",
    "tools/build_release.py", "tools/release_tools.py", "tools/requirements-dev.txt", "tools/web_setup.sh",
    "tests/conftest.py",
}
FULL_PREFIXES = ("fresing_render/pccheck/", "fresing_render/importer/", "installer/", "app_template/", ".github/",
                 "tools/ci_")
# Documents: no tests of their own, except these (the docs-mode checks)
DOC_TESTS = {"docs/": "tests/test_user_guide.py", "site/": "tests/test_site.py", "tools/build_site.py": "tests/test_site.py",
             "CHANGELOG.md": "tests/test_updates.py"}
NO_TESTS = ("TASKS.md", "tasks/", "CLAUDE.md", "README.md")
# Windows-only code: the lane run also builds the installer and runs Windows part A
WINDOWS_FILES = {"fresing_render/update_helper.py", "fresing_render/selftest.py", "fresing_render/core/updates.py",
                 "fresing_render/appicon.py", "fresing_render/winexe.py", "fresing_render/queue_runner.py",
                 "fresing_render/blender/files.py", "fresing_render/blender/updates.py",
                 "fresing_render/blender/project_lock.py", "tools/update_test_blender.py", "tools/appicon_test.py"}
WINDOWS_MARK = re.compile(r"""os\.name\s*==\s*["']nt|sys\.platform|ctypes|CREATE_NO_WINDOW|winreg|creationflags""")
# Task 0356: the code the real assets pack's job checks (tests.yml "Linux - real assets pack"): a lane run that changes
# it runs that job too (once the pin exists – ci_precheck.real_pack_wanted)
REALPACK_FILES = {"fresing_render/core/assets_pack.py", "fresing_render/core/assets_registry.py", "tools/assets_check.py"}
REALPACK_TESTS = "tests/real_pack/"                        # the with-pack tests: only that job runs them
SELFTEST_FILES = {"fresing_render/selftest.py"}            # the packaged self-test runs in the lane run too
LANE_GROUP_SECS = 600.0                                    # a lane run's pytest groups: about 10 minutes each
LANE_SKIP_REALAPP = {"pccheck", "pccheck2", "pccheckheavy", "tour", "tour2"}   # cover everything: full run only


def _keys(path: str) -> set[str]:
    """The words a test uses for this file: its name, its stem, and for ops_x / ui_x also x."""
    base = os.path.basename(path)
    stem = base.rsplit(".", 1)[0]
    keys = {base, stem}
    for pre in ("ops_", "ui_"):
        if stem.startswith(pre) and len(stem) > len(pre):
            keys.add(stem[len(pre):])
    return {k for k in keys if len(k) >= 3}


def _names(text: str, keys: set[str]) -> bool:
    return any(re.search(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", text) for k in keys)


def _read(root: str, rel: str) -> str:
    try:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def lane_plan(files: list[str], root: str = ROOT, times: dict | None = None, extra: list[str] = (),
              catchup: bool = False) -> dict:
    """What a lane run of these changed files needs.

    {"full": True, "why": [...]} when a shared file changed or a file is named by no test; else {"full": False,
    "why": [...], "pytest": matrix, "demo": matrix, "realapp": matrix, "windows": matrix, "build": bool}.

    ``extra`` (task 0383, the catch-up): the branch's own changed files; of them only the test files and real-app test
    scripts are added (they ran green in the branch's full run, on the main it left). They never make the run full. ``catchup``: the plan
    always builds (the release takes the run's installer), and a plan with no test at all is still a plan (only the
    build and its documentation checks), not a full run."""
    times = load_times() if times is None else times
    secs = times.get("pytest_files", {})
    tests = test_files(root)
    texts = {f: _read(root, f) for f in tests}
    sys.path.insert(0, os.path.join(root, "tools"))
    import ci_real_app
    scripts = {k: v[1] for k, v in ci_real_app.TESTS.items() if v[1] and k not in LANE_SKIP_REALAPP}
    script_text = {k: _read(root, os.path.join("tools", s)) for k, s in scripts.items()}
    picked: set[str] = set()
    real: set[str] = set()
    why: list[str] = []
    full: list[str] = []
    windows = selftest = realpack = False
    for f in sorted(set(files)):
        realpack = realpack or f in REALPACK_FILES or f.startswith(REALPACK_TESTS)
        if f.startswith(REALPACK_TESTS):
            why.append(f"{f}: the real assets pack's job")
            continue
        if f in FULL_FILES or f.startswith(FULL_PREFIXES):
            full.append(f"{f} is shared by every lane")
            continue
        if f in NO_TESTS or f.startswith(NO_TESTS):
            continue
        doc = next((t for k, t in DOC_TESTS.items() if f == k or (k.endswith("/") and f.startswith(k))), None)
        if f.endswith((".ps1", ".bat")) or f in WINDOWS_FILES or \
                (f.endswith(".py") and f.startswith(("fresing_render/", "tools/")) and WINDOWS_MARK.search(_read(root, f))):
            windows = True
            why.append(f"{f}: Windows code → build + Windows part A")
        selftest = selftest or f in SELFTEST_FILES
        if f in texts:                                     # a test file itself
            picked.add(f)
            why.append(f"{f}: itself")
            continue
        keys = _keys(f)
        hit = {t for t, txt in texts.items() if _names(txt, keys)}
        hit_real = {k for k, txt in script_text.items() if _names(txt, keys) or os.path.basename(f) == scripts[k]}
        if doc:
            hit.add(doc)
        if not hit and not hit_real:
            if doc or (windows and f.endswith((".ps1", ".bat"))):
                continue
            full.append(f"{f} is named by no test")
            continue
        picked |= hit
        real |= hit_real
        why.append(f"{f}: {len(hit)} test file{'s' if len(hit) != 1 else ''}"
                   + (f", real app {', '.join(sorted(hit_real))}" if hit_real else ""))
    if full:
        return {"full": True, "why": full}
    for f in sorted(set(extra) - set(files)):             # the branch's own tests (catch-up): run them, nothing more
        hit = {f} if f in texts else set()
        hit_real = {k for k, s in scripts.items() if os.path.basename(f) == s and f == f"tools/{s}"}
        new, new_real = hit - picked, hit_real - real
        if new or new_real:
            picked |= new
            real |= new_real
            why.append(f"{f}: changed on this branch" + (f" (real app {', '.join(sorted(new_real))})" if new_real else ""))
    demo_set = set(demo_files(sorted(picked), root))
    plain = sorted(picked - demo_set)

    def regroup(fs, n_max, selftest_on, prefix):
        if not fs and not selftest_on:
            return []
        total = sum(float(secs.get(f, NEW_FILE_SECS)) for f in fs) + (100.0 if selftest_on else 0.0)
        n = max(1, min(n_max, math.ceil(total / LANE_GROUP_SECS)))
        return [{"name": g["name"], "files": " ".join(g["files"]), "selftest": g["selftest"],
                 "minutes": round(g["secs"] / 60, 1)}
                for g in pytest_groups(fs, secs, n=n, selftest=selftest_on, prefix=prefix)]

    groups = {k: v for k, v in ci_real_app.GROUPS.items()}
    realapp = [{"name": g, "tests": ",".join(ts)} for g, ts in groups.items() if real & set(ts)]
    plan = {"full": False, "why": why,
            "pytest": regroup(plain, PYTEST_GROUPS, selftest, ""),
            "demo": regroup(sorted(demo_set), DEMO_GROUPS, False, "demo "),
            "realapp": realapp,
            "windows": matrix_windows(("a",)) if windows else [],
            "build": windows or catchup,
            "realpack": realpack}
    if catchup:
        for k in ("pytest", "demo", "realapp"):
            plan[k] = slowest_first(plan[k]) if k != "realapp" else plan[k]
        if not (plan["pytest"] or plan["demo"] or plan["realapp"] or plan["windows"]):
            plan["why"].append("no test file names what main brought: the build and its documentation checks only")
        return plan
    if not (plan["pytest"] or plan["demo"] or plan["realapp"] or plan["windows"] or plan["realpack"]):
        return {"full": True, "why": ["no test is named by the changed files: everything"]}
    return plan


def catchup_plan(main_files: list[str], branch_files: list[str], root: str = ROOT, times: dict | None = None) -> dict:
    """Task 0383: the catch-up run of a branch whose full run went green at G and which then merged main (and raised
    its version). What is new is only where main's changes meet the branch's: the tests that name a file main brought
    (as a lane run of those files – a shared one makes it full), plus every test file and real-app test the branch
    itself changed or added (``extra``), plus the build (the release takes this run's installer)."""
    return lane_plan(main_files, root, times, extra=branch_files, catchup=True)


def describe(plan: dict) -> list[str]:
    """Lines for the precheck's summary (a lane or a catch-up plan)."""
    if plan.get("full"):
        return [f"full: {w}" for w in plan["why"]]
    out = [f"why: {w}" for w in plan["why"]]
    out += [f"pytest group {g['name']}: ~{g['minutes']} min{' + packaged self-test' if g['selftest'] else ''}: "
            f"{g['files']}" for g in plan["pytest"]]
    out += [f"pytest group {g['name']} (after the demo is made): ~{g['minutes']} min: {g['files']}" for g in plan["demo"]]
    out += [f"real-app group {g['name']}: {g['tests']}" for g in plan["realapp"]]
    out += [f"Windows part {p['name']}: {p['what']}" for p in plan["windows"]]
    if not plan["windows"]:
        out.append("the installer is built (the release takes it), no Windows job (no Windows code changed)"
                   if plan.get("build") else "no installer build, no Windows job (no Windows code changed)")
    if plan.get("realpack"):
        out.append("the assets pack code changed: the real assets pack's job runs (once a pin exists)")
    return out


def main() -> int:
    if sys.argv[1:2] == ["--lane"]:
        for line in describe(lane_plan(sys.argv[2:])):
            print(line)
        return 0
    for g in matrix_pytest():
        print(f"pytest {g['name']}: ~{g['minutes']} min{' + packaged self-test' if g['selftest'] else ''}: {g['files']}")
    for g in matrix_demo():
        print(f"pytest {g['name']} (after the demo is made): ~{g['minutes']} min: {g['files']}")
    for g in matrix_real_app():
        print(f"real app {g['name']}: {g['tests']}")
    for p in matrix_windows():
        print(f"Windows part {p['name']}: {p['what']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
