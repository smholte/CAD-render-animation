"""First job of the automatic tests (task 0036): cheap checks that fail in about a minute, and the plan for the run.

    python tools/ci_precheck.py                 # on a chat machine: the checks only (asks GitHub with `gh`)
    python tools/ci_precheck.py --github        # in the workflow: also decides the mode, writes $GITHUB_OUTPUT

Checks (each problem is printed with what to do; any problem fails the job and the rest of the run is skipped):
  - the version in fresing_render/__init__.py and blender_manifest.toml agree;
  - a branch / pull request that raised the version: it is newer than the version on `main` and every release,
    and CHANGELOG.md has its heading ("someone took your version number: merge main and renumber to …");
    on `main`: a version without a release has its CHANGELOG heading;
  - MIN_CHECKS (tools/ci_real_app.py) names every real-app test, MIN_LINES_FULL / MIN_LINES_HEAVY
    (tools/ci_check_pccheck.py) are not lower than the number of Full / Heavy lines of the PC check;
  - every real-app test is in exactly one group, every tests/test_*.py file in exactly one pytest group;
  - TASKS.md parses (every table row has its columns, no task number twice in the open list).

Mode of the run (output `mode`):
  reuse  a push to main whose git tree already has a green run (typically: the branch was fast-forwarded to
         `main` after its run went green): no tests; the release jobs use that run's installer files.
  docs   the push changes only documentation (docs/, CHANGELOG.md, CLAUDE.md, README.md, TASKS.md, tasks/) and at
         most the version line of the two version files, compared with a commit whose run is green: the build job with
         the tooltip check, the guide and their tests; no full suite, no real app, no Windows install.
  lane   (task 0171) a branch push whose version is not raised yet (the task is still being built; CLAUDE.md: the
         version is taken last) and whose changed files (against where it left main) are named by tests: only those
         tests' jobs (`ci_groups.lane_plan`), plus the build and Windows part A when Windows code changed. A shared
         file, a file no test names, a raised version, `main`, a pull request, "[full run]" or "[release rehearsal]"
         in the commit message → full. A lane run proves nothing (its verdict job says "lane run"): never the basis of
         a docs or reuse run.
  full   everything else: all tests.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import time
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

REPO = os.environ.get("GITHUB_REPOSITORY", "smholte/cad-render-animation")
WORKFLOW = "tests.yml"
INIT = "fresing_render/__init__.py"
MANIFEST = "fresing_render/blender_manifest.toml"
VERSION_FILES = (INIT, MANIFEST)
DOC_PREFIXES = ("docs/", "tasks/", "site/")       # site/: the landing page (task 0047)
DOC_FILES = ("CHANGELOG.md", "CLAUDE.md", "README.md", "TASKS.md", "tools/build_site.py", "tests/test_site.py")
TASK_LIST_ONLY = ("TASKS.md", "tasks/")
# Jobs that must all be green in a run before its tree counts as proven (new and old workflow names).
BUILD_JOB = "Build the Windows installer zip"
VERDICT_JOB = "Tests - verdict"
OLD_FULL_JOBS = ("Linux - test suite", "Linux - real app", "Windows - install")
ARTIFACTS = ("windows-installer", "windows-installer-old", "update-listing")
ZERO = "0" * 40


# ---------------------------------------------------------------------------------------------- helpers

def git(*args, check: bool = False) -> str:
    r = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout.strip() if r.returncode == 0 else ""


def gh_api(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip() or r.stdout.strip()}")
    return json.loads(r.stdout)


def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v.split("-", 1)[0])[:3])


def next_version(v: str) -> str:
    a = list(vtuple(v)) + [0, 0, 0]
    return f"{a[0]}.{a[1]}.{a[2] + 1}"


def init_version(text: str) -> str:
    m = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def manifest_version(text: str) -> str:
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else ""


def changelog_versions(text: str) -> list[str]:
    from fresing_render.core import updates
    return [e["version"] for e in updates.parse_changelog(text)]


def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def version_at(commit: str) -> str:
    """The manifest version at a commit ('' when it cannot be read)."""
    return manifest_version(git("show", f"{commit}:{MANIFEST}")) if commit else ""


# ---------------------------------------------------------------------------------------------- checks

def check_versions(init_v: str, manifest_v: str, changelog: list[str], *, on_main: bool, main_v: str,
                   base_v: str, released: set[str]) -> tuple[list[str], list[str]]:
    """Returns (problems, notes). base_v: the version where this branch left main (merge-base)."""
    problems, notes = [], []
    if not init_v or not manifest_v:
        return [f"cannot read the version from {INIT} or {MANIFEST}"], notes
    if init_v != manifest_v:
        problems.append(f"version clash inside this commit: {INIT} says {init_v}, {MANIFEST} says {manifest_v} – "
                        "set both to the same number")
        return problems, notes
    v = manifest_v
    newest = max([main_v] + sorted(released, key=vtuple), key=lambda x: vtuple(x) if x else ())
    if on_main:
        if v in released:
            notes.append(f"version {v} is released already: nothing new to publish")
        elif v not in changelog:
            problems.append(f"CHANGELOG.md has no heading for {v}: add '## {v} – <date> – <title>' at the top")
        return problems, notes
    if base_v and v == base_v:
        notes.append(f"version {v} not raised on this branch (fine until the branch is finished)")
        return problems, notes
    if vtuple(v) <= vtuple(newest) or v in released:
        problems.append(f"someone took your version number: {v} is not newer than {newest} "
                        f"(on main or released). Merge main and renumber to {next_version(newest)} "
                        "(both version files and the CHANGELOG heading)")
    elif v not in changelog:
        problems.append(f"CHANGELOG.md has no heading for {v}: add '## {v} – <date> – <title>' at the top")
    else:
        notes.append(f"version {v} (main has {main_v or '?'}, newest release {newest})")
    return problems, notes


def full_pccheck_lines(src: str, mode: str = "F") -> int:
    """Number of PC check lines that run in a mode ("F" Full, "H" Heavy; the default is modes=(F,))."""
    count = 0
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if not (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "line"):
                continue
            modes = d.args[3] if len(d.args) >= 4 else None
            for k in d.keywords:
                if k.arg == "modes":
                    modes = k.value
            names = {n.id for n in ast.walk(modes) if isinstance(n, ast.Name)} if modes is not None else {"F"}
            count += mode in names
    return count


def check_counts() -> list[str]:
    import ci_check_pccheck
    import ci_real_app
    problems = []
    missing = sorted(set(ci_real_app.TESTS) - set(ci_real_app.MIN_CHECKS))
    extra = sorted(set(ci_real_app.MIN_CHECKS) - set(ci_real_app.TESTS))
    if missing:
        problems.append(f"MIN_CHECKS in tools/ci_real_app.py has no entry for {', '.join(missing)}: add the number "
                        "of checks each test reports")
    if extra:
        problems.append(f"MIN_CHECKS in tools/ci_real_app.py names tests that do not exist: {', '.join(extra)}")
    srcs = [read(f"fresing_render/pccheck/{f}") for f in ("checks.py", "heavy.py")
            if os.path.isfile(os.path.join(ROOT, "fresing_render", "pccheck", f))]
    for mode, name in (("F", "MIN_LINES_FULL"), ("H", "MIN_LINES_HEAVY")):
        n = sum(full_pccheck_lines(src, mode) for src in srcs)
        have = getattr(ci_check_pccheck, name, None)
        if have is not None and have < n:
            problems.append(f"{name} in tools/ci_check_pccheck.py is {have}, but the PC check has {n} "
                            f"{'Full' if mode == 'F' else 'Heavy'} lines: raise it to {n}")
    tour = os.path.join(ROOT, "fresing_render", "blender", "tour.py")
    if os.path.isfile(tour):                     # the test tour (task 0059): Make test tour project + one per stop
        n = 1 + len(re.findall(r"^stop\(", read("fresing_render/blender/tour.py"), re.M))
        have = getattr(ci_check_pccheck, "MIN_LINES_TOUR", None)
        if have is not None and have < n:
            problems.append(f"MIN_LINES_TOUR in tools/ci_check_pccheck.py is {have}, but the test tour has {n} "
                            f"lines (Make test tour project + {n - 1} stops): raise it to {n}")
        if ci_real_app.MIN_CHECKS.get("tour", n) < n:
            problems.append(f"MIN_CHECKS['tour'] in tools/ci_real_app.py is below the {n} lines of the test tour")
    return problems


def check_groups() -> list[str]:
    import ci_groups
    import ci_real_app
    problems = []
    seen: dict[str, str] = {}
    for g, keys in ci_real_app.GROUPS.items():
        for k in keys:
            if k in seen:
                problems.append(f"real-app test '{k}' is in two groups ({seen[k]}, {g}) in tools/ci_real_app.py GROUPS")
            seen[k] = g
            if k not in ci_real_app.TESTS:
                problems.append(f"GROUPS in tools/ci_real_app.py names '{k}', which is not in TESTS")
    for k in ci_real_app.TESTS:
        if k not in seen:
            problems.append(f"real-app test '{k}' is in no group: add it to the group with the fewest minutes in "
                            "GROUPS (tools/ci_real_app.py)")
    import ci_pccheck_lines                      # the PC check (Full): Linux halves add up to every line (task 0063)
    problems += [f"tools/ci_pccheck_lines.py: {p}" for p in ci_pccheck_lines.problems()]
    files = ci_groups.test_files()
    grouped = [f for g in ci_groups.matrix_pytest() + ci_groups.matrix_demo() for f in g["files"].split()]
    if sorted(grouped) != files:
        problems.append("the pytest groups do not hold every tests/test_*.py file exactly once (tools/ci_groups.py)")
    return problems


def check_functions() -> list[str]:
    """The function list (task 0124): every tour stop, Full PC-check line and guide section named, every entry linked."""
    from fresing_render.core import functions
    return [f"function list: {p}" for p in functions.problems(**functions.read_repo(ROOT))]


def check_tour_versions(version: str, *, raised: bool, main_ref: str = "origin/main") -> tuple[list[str], list[str]]:
    """Task 0199: a test tour set that changed on this branch has its changed= (added= when new) raised to the
    branch's version, every stop has since=, tests/data/tour_versions.json matches (tools/tour_versions.py)."""
    import tour_versions
    main_text = git("show", f"{main_ref}:{tour_versions.RECORD}")
    main_record = tour_versions.read_record(main_text) if main_text.strip() else None
    try:
        with open(os.path.join(ROOT, tour_versions.RECORD), encoding="utf-8") as fh:
            record = tour_versions.read_record(fh.read())
    except OSError:
        record = {}
    return tour_versions.check(tour_versions.current(ROOT), record, main_record, version=version, raised=raised)


def check_tasks(text: str) -> list[str]:
    """TASKS.md: every table has rows with as many cells as its header; no task number twice in a table."""
    problems = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and re.match(r"^\|\s*-", lines[i + 1]):
            ncol = len(_cells(lines[i]))
            seen = set()
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                cells = _cells(lines[j])
                if len(cells) != ncol:
                    problems.append(f"TASKS.md line {j + 1}: {len(cells)} cells, the table has {ncol} – "
                                    "a '|' too many or too few")
                num = cells[0].strip() if cells else ""
                if re.fullmatch(r"\d{4}", num):
                    if num in seen:
                        problems.append(f"TASKS.md line {j + 1}: task {num} appears twice in the same table")
                    seen.add(num)
                j += 1
            i = j
        else:
            i += 1
    return problems


def _cells(row: str) -> list[str]:
    row = row.strip()
    row = row[1:] if row.startswith("|") else row
    row = row[:-1] if row.endswith("|") else row
    return re.split(r"(?<!\\)\|", row)


# ---------------------------------------------------------------------------------------------- the mode

def is_doc_path(path: str) -> bool:
    return path in DOC_FILES or path.startswith(DOC_PREFIXES)


def only_version_line(diff: str) -> bool:
    """A -U0 diff of a version file changes only the version line."""
    changed = [ln for ln in diff.splitlines()
               if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return bool(changed) and all(re.match(r'^[+-]\s*(__version__|version)\s*=\s*"[^"]*"\s*$', ln) for ln in changed)


def docs_only(files: list[str], diff_of) -> bool:
    """True when every changed file is documentation, or a version file with only its version line changed."""
    if not files:
        return False
    for f in files:
        if is_doc_path(f):
            continue
        if f in VERSION_FILES and only_version_line(diff_of(f)):
            continue
        return False
    return True


def run_is_proven(run: dict, jobs: list[dict]) -> tuple[bool, str]:
    """A finished run whose tests all passed: the new workflow's verdict job and build, or the old workflow's jobs."""
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        return False, f"run {run.get('id')} is not green"
    by_name = {}
    for j in jobs:
        by_name.setdefault(j["name"], []).append(j)
    ok = lambda name: [j for n, js in by_name.items() if n.startswith(name) for j in js]  # noqa: E731
    build = ok(BUILD_JOB)
    if not build or any(j["conclusion"] != "success" for j in build):
        return False, f"run {run.get('id')}: the build job did not run green"
    verdict = ok(VERDICT_JOB)
    if any(LANE_MARK in j["name"] for j in verdict):
        return False, f"run {run.get('id')} was a lane run (only some tests): it proves nothing"
    if verdict:
        if any(j["conclusion"] != "success" for j in verdict):
            return False, f"run {run.get('id')}: the verdict job is not green"
        return True, f"run {run.get('id')} green"
    for name in OLD_FULL_JOBS:
        js = ok(name)
        if not js or any(j["conclusion"] != "success" for j in js):
            return False, f"run {run.get('id')}: '{name}' not green"
    return True, f"run {run.get('id')} green (workflow before task 0036)"


def find_proven_run(tree: str, own_run: str, api=gh_api) -> tuple[dict | None, str]:
    """The newest green run (any branch) of a commit with this git tree, with its installer files still kept."""
    runs = api(f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?status=success&per_page=100")["workflow_runs"]
    why = "no green run with this tree"
    for run in sorted(runs, key=lambda r: r["created_at"], reverse=True):
        if str(run["id"]) == str(own_run) or (run.get("head_commit") or {}).get("tree_id") != tree:
            continue
        jobs = api(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
        ok, why = run_is_proven(run, jobs)
        if not ok:
            continue
        arts = api(f"repos/{REPO}/actions/runs/{run['id']}/artifacts?per_page=100")["artifacts"]
        have = {a["name"] for a in arts if not a.get("expired")}
        if not set(ARTIFACTS) <= have:
            why = f"run {run['id']} is green but its installer files are gone (kept 7 days)"
            continue
        return run, why
    return None, why


def runs_of(sha: str, api=gh_api) -> list[dict]:
    """Every run of this workflow on exactly this commit (any branch, any state)."""
    runs = api(f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?head_sha={sha}&per_page=20")
    return [r for r in runs["workflow_runs"] if r["head_sha"] == sha]


# Task 0170: the commits whose green run may stand for this push. A task's last push to main is often "merge main
# + report" on top of a branch commit that already ran green, while main moved only by task-list pushes. The old
# rule walked main's first parents only and found main's green commit from before the task: "code changed".
CANDIDATES = 40            # newest commits of the push (every parent) that are looked at
API_CHECKS = 12            # at most this many candidates (with a documents-only diff) asked about their runs
WAIT_LIMIT = 6 * 60        # s: a candidate's docs run that is still going is waited for this long (a docs run: ~3 min)
WAIT_STEP = 30
TEST_JOBS = ("Linux - test suite", "Linux - real app", "Windows - install", "Linux - make the demo")
LANE_MARK = "lane run"     # in the verdict job's name of a lane run: such a run proves nothing (task 0171)
FULL_WORDS = ("[full run]", "[release rehearsal]")


def candidates(sha: str, before: str, base: str, depth: int = 10) -> list[str]:
    """Commits that may have run green, nearest first: those the push brings (every parent, newest first),
    then base and its first parents. sha itself is left out (its run is this one)."""
    out = []
    if before:
        out += git("rev-list", "--topo-order", f"--max-count={CANDIDATES}", sha, f"^{before}").split()
    c = base
    for _ in range(depth):
        if not c:
            break
        out.append(c)
        c = git("rev-parse", "--verify", "-q", f"{c}^")
    seen, res = {sha}, []
    for c in out:
        if c and c not in seen:
            seen.add(c)
            res.append(c)
    return res


def changed_files(a: str, b: str) -> list[str]:
    return git("diff", "--name-only", a, b).splitlines()


def is_docs_run(jobs: list[dict]) -> bool:
    """A run still going whose precheck chose docs: its test jobs are skipped (or not made), its build is not."""
    pre = [j for j in jobs if j["name"].startswith("Precheck")]
    if not pre or pre[0].get("conclusion") != "success":
        return False
    tests = [j for j in jobs if j["name"].startswith(TEST_JOBS)]
    build = [j for j in jobs if j["name"].startswith(BUILD_JOB)]
    return bool(build) and all(j.get("conclusion") == "skipped" for j in tests) \
        and all(j.get("conclusion") != "skipped" for j in build)


def proven_state(sha: str, api=gh_api) -> tuple[str, str]:
    """('proven' | 'running' | 'no', why) for the runs of one commit. Only a finished run with build + verdict green
    proves it (a reuse run has no build: it counts through the commit whose run it reused). 'running' only for a
    docs run still going (worth a short wait); a full run still going is not waited for."""
    runs = runs_of(sha, api)
    if not runs:
        return "no", "no run"
    why, running = "", False
    for run in sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True):
        jobs = api(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
        if run.get("status") == "completed":
            ok, w = run_is_proven(run, jobs)
            if ok:
                return "proven", w
            why = why or (f"run {run['id']} {run.get('conclusion')}" if run.get("conclusion") != "success" else w)
        elif is_docs_run(jobs):
            running = True
            why = f"run {run['id']} (docs) still going"
        else:
            why = why or f"run {run['id']} still going (not a short docs run: not waited for)"
    return ("running" if running else "no"), why


def docs_basis(sha: str, cands: list[str], api=gh_api, sleep=time.sleep, wait: float = WAIT_LIMIT) \
        -> tuple[str, list[str], list[str]]:
    """The nearest candidate with a proven green run and only documentation/version lines changed from it to sha:
    (commit, its changed files, notes). ('', [], notes) when none."""
    notes, pending, asked = [], [], 0
    for c in cands:
        files = changed_files(c, sha)
        if not docs_only(files, lambda f, c=c: git("diff", "-U0", c, sha, "--", f)):
            continue
        if asked >= API_CHECKS:
            notes.append(f"stopped after {API_CHECKS} commits with a documents-only difference")
            break
        asked += 1
        state, why = proven_state(c, api)
        if state == "proven":
            return c, files, notes
        notes.append(f"{c[:7]}: {why}")
        if state == "running":
            pending.append((c, files))
    waited = 0.0
    while pending and waited < wait:
        sleep(WAIT_STEP)
        waited += WAIT_STEP
        still = []
        for c, files in pending:
            state, why = proven_state(c, api)
            if state == "proven":
                notes.append(f"waited {waited:.0f} s for {c[:7]}'s run")
                return c, files, notes
            if state == "running":
                still.append((c, files))
            else:
                notes.append(f"{c[:7]} after waiting: {why}")
        pending = still
    if pending:
        notes.append(f"stopped waiting after {wait:.0f} s")
    return "", [], notes


def lane_base(sha: str) -> str:
    """Where the branch left main (merge-base with origin/main, or a local main)."""
    for ref in ("origin/main", "main"):
        if git("rev-parse", "--verify", "-q", ref):
            mb = git("merge-base", sha, ref)
            if mb:
                return mb
    return ""


def lane_decision(event: str, ref: str, sha: str, message: str | None = None) -> tuple[dict | None, str]:
    """(plan, why) for a lane run (task 0171), or (None, why not)."""
    if event != "push" or ref == "refs/heads/main":
        return None, "main or a pull request"
    message = git("log", "-1", "--format=%B", sha) if message is None else message
    word = next((w for w in FULL_WORDS if w in message), "")
    if word:
        return None, f"'{word}' in the commit message"
    mb = lane_base(sha)
    if not mb or mb == sha:
        return None, "no commit of main to compare with"
    v_here, v_base = version_at(sha), version_at(mb)
    if not v_here or v_here != v_base:
        return None, f"version raised ({v_base or '?'} → {v_here or '?'}): the full run that comes with the version"
    import ci_groups
    files = changed_files(mb, sha)
    plan = ci_groups.lane_plan(files, ROOT)
    if plan["full"]:
        return None, "; ".join(plan["why"][:4]) + (" …" if len(plan["why"]) > 4 else "")
    return plan, (f"version {v_here} not raised yet (a task still being built): only the tests of the "
                  f"{len(files)} changed files since {mb[:7]} on main")


def decide(event: str, ref: str, sha: str, before: str, run_id: str, api=gh_api,
           sleep=time.sleep) -> tuple[str, str, str]:
    """(mode, artifacts run id, why)."""
    return decide_plan(event, ref, sha, before, run_id, api, sleep)[:3]


def decide_plan(event: str, ref: str, sha: str, before: str, run_id: str, api=gh_api, sleep=time.sleep,
                message: str | None = None) -> tuple[str, str, str, dict | None]:
    """(mode, artifacts run id, why, lane plan or None)."""
    mode, art, why = _decide(event, ref, sha, before, run_id, api, sleep)
    if mode != "full":
        return mode, art, why, None
    plan, lane_why = lane_decision(event, ref, sha, message)
    if plan:
        return "lane", run_id, lane_why, plan
    return mode, art, f"{why} – not a lane run: {lane_why}", None


def _decide(event: str, ref: str, sha: str, before: str, run_id: str, api=gh_api,
            sleep=time.sleep) -> tuple[str, str, str]:
    if event == "workflow_dispatch":
        return "full", run_id, "started by hand: everything"
    on_main = ref == "refs/heads/main"
    if on_main and event == "push":
        tree = git("rev-parse", f"{sha}^{{tree}}")
        run, why = find_proven_run(tree, run_id, api)
        if run:
            return "reuse", str(run["id"]), (f"this tree ({tree[:7]}) already ran green in run {run['id']} on "
                                             f"{run['head_branch']} @ {run['head_sha'][:7]}: no tests again")
    before = before if event == "push" and before and before != ZERO and git("cat-file", "-t", before) else ""
    base = before or git("merge-base", sha, "origin/main")
    if not base or base == sha:
        return "full", run_id, "no earlier commit to compare with: everything"
    gb, files, notes = docs_basis(sha, candidates(sha, before, base), api, sleep)
    if gb:
        return "docs", run_id, (f"only documentation/version lines changed since {gb[:7]} (proven green): "
                                f"{', '.join(files[:8])}{' …' if len(files) > 8 else ''}")
    extra = f" ({'; '.join(notes[:4])})" if notes else ""
    return "full", run_id, (f"code changed since every green commit of this push and the 9 before {base[:7]}: "
                            f"everything{extra}")


# ---------------------------------------------------------------------------------------------- main

def released_versions(api=gh_api) -> set[str]:
    rels = api(f"repos/{REPO}/releases?per_page=100")
    return {r["tag_name"][1:] for r in rels if r["tag_name"].startswith("v") and "rehearsal" not in r["tag_name"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--github", action="store_true", help="in the workflow: decide the mode, write $GITHUB_OUTPUT")
    ap.add_argument("--event", default=os.environ.get("GITHUB_EVENT_NAME", "push"))
    ap.add_argument("--ref", default=os.environ.get("GITHUB_REF", ""))
    ap.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    ap.add_argument("--before", default="")
    ap.add_argument("--run", default=os.environ.get("GITHUB_RUN_ID", "0"))
    args = ap.parse_args(argv)
    sha = args.sha or git("rev-parse", "HEAD")
    ref = args.ref or ("refs/heads/" + git("rev-parse", "--abbrev-ref", "HEAD"))
    on_main = ref == "refs/heads/main"

    problems, notes = [], []
    try:
        released = released_versions()
    except RuntimeError as exc:
        released = set()
        notes.append(f"could not list the releases ({exc}); version compared with main only")
    main_v = version_at("origin/main")
    base = git("merge-base", sha, "origin/main") if not on_main else sha
    p, n = check_versions(init_version(read(INIT)), manifest_version(read(MANIFEST)),
                          changelog_versions(read("CHANGELOG.md")), on_main=on_main, main_v=main_v,
                          base_v=version_at(base) if base else main_v, released=released)
    problems += p
    notes += n
    problems += check_counts()
    problems += check_groups()
    problems += check_functions()
    version = init_version(read(INIT))
    p, n = check_tour_versions(version, raised=on_main or version != (version_at(base) if base else main_v))
    problems += p
    notes += n
    problems += check_tasks(read("TASKS.md"))

    import ci_groups
    pytest_m, real_m, demo_m = ci_groups.matrix_pytest(), ci_groups.matrix_real_app(), ci_groups.matrix_demo()
    win_m, build = ci_groups.matrix_windows(), True
    mode, art_run, why, plan = ("failed" if problems else "full"), args.run, "checks only", None
    if args.github and not problems:
        mode, art_run, why, plan = decide_plan(args.event, ref, sha, args.before, args.run)
    if plan:
        pytest_m, real_m, demo_m, win_m, build = plan["pytest"], plan["realapp"], plan["demo"], plan["windows"], plan["build"]

    out = ["### Precheck: " + ("FAILED" if problems else "passed"), ""]
    out += [f"- ❌ {p}" for p in problems] + [f"- {n}" for n in notes]
    if not problems:
        out += [f"- **Mode: {mode}** – {why}", ""]
        if mode == "full":
            out += [f"- pytest group {g['name']}: ~{g['minutes']} min" + (" + packaged self-test" if g["selftest"] else "")
                    for g in pytest_m]
            out += [f"- pytest group {g['name']} (after the demo is made once): ~{g['minutes']} min" for g in demo_m]
            out += [f"- real-app group {g['name']}: {g['tests']}" for g in real_m]
            out += [f"- Windows part {p['name']}: {p['what']}" for p in win_m]
        if mode == "lane":
            out += ["- **lane run – not a release check**: the full run comes with the version raise "
                    "(or put [full run] in the commit message)"]
            out += [f"- {line}" for line in ci_groups.describe(plan)]
    text = "\n".join(out) + "\n"
    print(text)
    print(f"MODE: {mode} {art_run if mode == 'reuse' else ''}".rstrip())     # read by tools/ci_status.py
    for p in problems:
        print(f"::error title=Precheck::{p}")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(text)
    if args.github and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"mode={mode}\nartifacts_run={art_run}\n")
            fh.write(f"pytest={json.dumps(pytest_m)}\nrealapp={json.dumps(real_m)}\ndemo={json.dumps(demo_m)}\n")
            fh.write(f"windows={json.dumps(win_m)}\nbuild={'true' if build else 'false'}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
