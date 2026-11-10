"""Show the result of the automatic tests on GitHub, from a chat (or any machine with `gh`).

    python3 tools/ci_status.py                      # run of the current commit (HEAD)
    python3 tools/ci_status.py --branch main        # run of the newest commit on main (on GitHub)
    python3 tools/ci_status.py --sha 1a2b3c4        # run of one commit
    python3 tools/ci_status.py --wait               # wait until the run has finished (max 90 min)
    python3 tools/ci_status.py --run 123456789 --log "Windows"   # whole log of the job(s) matching "Windows"
    python3 tools/ci_status.py --run 123456789 --record   # copy a green run's times into tools/ci_times.json

Prints the mode of the run (full / docs / reuse, chosen by the precheck job, task 0036), each job with its
time, the run's total, a flag for a job that took more than 1.5 x its recorded time, and for a failed job
the failing step, the error annotations and the last lines of its log. Exit code: 0 = all jobs passed, 1 = something failed, 2 = still running
or no run found. Uses the `gh` command (set up in the chats); only the GitHub API paths for runs,
jobs, job logs and annotations are needed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

REPO = "smholte/cad-render-animation"


def gh(path: str, raw: bool = False):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip() or r.stdout.strip()}")
    return r.stdout if raw else json.loads(r.stdout)


def _git(*args) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


WORKFLOW = "tests.yml"
SKIPPED_PATHS = ("TASKS.md", "tasks/")          # the workflow's paths-ignore: such commits get no run


def only_task_list(sha: str) -> bool:
    """True when the commit changes only the task list: GitHub starts no test run for it."""
    try:
        commit = gh(f"repos/{REPO}/commits/{sha}")
    except RuntimeError:
        return False
    return commit_only_task_list(commit)


def commit_only_task_list(commit: dict) -> bool:
    """The judgement on one commit's API answer. A merge commit (two parents) is never judged by its diff against
    the first parent: GitHub looks at what the push brought in and runs the tests (task 0060)."""
    if len(commit.get("parents", [])) > 1:
        return False
    files = [f["filename"] for f in commit.get("files", [])]
    return bool(files) and all(f == SKIPPED_PATHS[0] or f.startswith(SKIPPED_PATHS[1]) for f in files)


def commit_of(args) -> str:
    if args.sha:
        return _git("rev-parse", args.sha) or args.sha
    if args.branch:
        return gh(f"repos/{REPO}/commits/{args.branch}")["sha"]
    return _git("rev-parse", "HEAD")


def find_run(args):
    """The run of exactly one commit: --sha, or the newest commit of --branch on GitHub, or HEAD.

    Never an older commit's run: right after a push GitHub needs a few seconds to create the
    run, and an older green run must not stand in for it."""
    if args.run:
        return gh(f"repos/{REPO}/actions/runs/{args.run}")
    if args.sha:
        sha = _git("rev-parse", args.sha) or args.sha
    elif args.branch:
        sha = gh(f"repos/{REPO}/commits/{args.branch}")["sha"]
    else:
        sha = _git("rev-parse", "HEAD")
    runs = gh(f"repos/{REPO}/actions/workflows/{WORKFLOW}/runs?head_sha={sha}&per_page=20")["workflow_runs"]
    runs = [r for r in runs if r["head_sha"] == sha]
    if args.branch:          # a commit pushed to a task branch and to main has a run on each
        runs = [r for r in runs if r["head_branch"] == args.branch]
    return _prefer_push(runs) if runs else None


def _prefer_push(runs):
    runs = sorted(runs, key=lambda r: r["created_at"], reverse=True)
    push = [r for r in runs if r["event"] == "push"]
    return (push or runs)[0]


TIMES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ci_times.json")
SLOW = 1.5                                       # flag a job that takes more than 1.5 x its recorded time


def _minutes(a: str | None, b: str | None) -> float | None:
    try:
        ta = datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = datetime.fromisoformat(b.replace("Z", "+00:00"))
        return (tb - ta).total_seconds() / 60
    except (TypeError, ValueError, AttributeError):
        return None


def _secs(job) -> str:
    m = _minutes(job.get("started_at"), job.get("completed_at"))
    return "running" if m is None else f"{m:.1f} min"


def _recorded() -> dict:
    try:
        with open(TIMES, encoding="utf-8") as fh:
            return json.load(fh).get("jobs", {})
    except (OSError, ValueError):
        return {}


def slow_note(name: str, minutes: float | None, recorded: dict) -> str:
    """' - SLOW: usually 4.0 min' when the job took more than SLOW x its recorded minutes (and over a minute)."""
    usual = recorded.get(name)
    if minutes is None or not usual or minutes <= max(1.0, SLOW * usual):
        return ""
    return f" - SLOW: usually {usual:.1f} min"


def run_mode(jobs) -> str:
    """The precheck job's 'MODE: …' line (task 0036), '' for older runs or while it runs."""
    pre = [j for j in jobs if j["name"].startswith("Precheck") and j.get("conclusion") == "success"]
    if not pre:
        return ""
    m = re.search(r"^MODE: (\w+)(?: (\d+))?\s*$", _log(pre[0]["id"]), re.M)
    if not m:
        return ""
    if m.group(1) == "reuse":
        return f"reuse - no tests: this tree already ran green in run {m.group(2)}"
    return {"docs": "docs - documentation-only change: build, tooltip check, guide",
            "full": "full - all tests"}.get(m.group(1), m.group(1))


def show(run, log_filter: str | None) -> int:
    print(f"Run {run['id']} ({run['event']}) on {run['head_branch']} @ {run['head_sha'][:7]}: "
          f"{run['status']} {run.get('conclusion') or ''}")
    print(f"  {run['html_url']}")
    jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    mode = run_mode(jobs)
    if mode:
        print(f"  Mode: {mode}")
    recorded = _recorded()
    bad = False
    for job in jobs:
        state = job["conclusion"] or job["status"]
        mark = {"success": "OK  ", "failure": "FAIL", "cancelled": "STOP", "skipped": "skip"}.get(state, state)
        mins = _minutes(job.get("started_at"), job.get("completed_at")) if state != "skipped" else None
        print(f"  [{mark}] {job['name']} ({'-' if state == 'skipped' else _secs(job)})"
              f"{slow_note(job['name'], mins, recorded)}")
        if state in ("failure", "cancelled", "timed_out"):
            bad = True
            for st in job["steps"]:
                if st.get("conclusion") == "failure":
                    print(f"         failed step: {st['name']}")
            try:
                for a in gh(f"repos/{REPO}/check-runs/{job['id']}/annotations"):
                    if a.get("annotation_level") == "failure":
                        title = f"{a['title']}: " if a.get("title") else ""
                        print(f"         ! {title}{a.get('message', '')[:300]}")
            except RuntimeError:
                pass
            if not log_filter:
                lines = [ln for ln in _log(job["id"]).splitlines() if ln.strip()]
                errors = [i for i, ln in enumerate(lines) if "##[error]" in ln]
                end = errors[0] + 1 if errors else len(lines)      # the lines that lead to the first error
                tail = lines[max(0, end - 40):end]
                print("         --- the log up to the first error ---")
                for ln in tail:
                    print("         " + ln[:240])
        if log_filter and log_filter.lower() in job["name"].lower():
            print(_log(job["id"]))
    if run["status"] == "completed":
        total = _minutes(run.get("run_started_at") or run.get("created_at"), run.get("updated_at"))
        busy = sum(m for j in jobs if (m := _minutes(j.get("started_at"), j.get("completed_at"))) is not None
                   and j.get("conclusion") != "skipped")
        if total is not None:
            print(f"  Total: {total:.1f} min from start to end ({busy:.0f} job-minutes on {len(jobs)} jobs)")
    if run["status"] != "completed":
        return 2
    return 1 if bad or run.get("conclusion") != "success" else 0


def _log(job_id: int) -> str:
    try:
        text = gh(f"repos/{REPO}/actions/jobs/{job_id}/logs", raw=True)
    except RuntimeError as exc:
        return f"(log not available: {exc})"
    # drop the timestamp GitHub puts before every line
    return "\n".join(ln[29:] if len(ln) > 29 and ln[4] == "-" and ln[10] == "T" else ln for ln in text.splitlines())


HISTORY = 3                                       # runs whose file times are kept; the slowest of them balances the groups


def merge_file_times(times: dict, files: dict) -> None:
    """Add one run's seconds per test file. `pytest_history` keeps the last HISTORY values per file and
    `pytest_files` (what tools/ci_groups.py balances by) is the slowest of them, so one fast run (or a runner that
    happened to be quick) does not unbalance the next split (task 0063)."""
    hist = times.setdefault("pytest_history", {})
    for name, secs in files.items():
        if name not in hist:                       # the first time: the old single value counts as one sample
            old = times.get("pytest_files", {}).get(name)
            hist[name] = [old] if old is not None else []
        hist[name] = (hist[name] + [secs])[-HISTORY:]
    times.setdefault("pytest_files", {})
    for name, values in hist.items():
        if values:
            times["pytest_files"][name] = round(max(values), 1)


def record(run) -> int:
    """Copy a green run's job minutes and pytest file seconds into tools/ci_times.json (balances the groups)."""
    if run.get("conclusion") != "success":
        print(f"Run {run['id']} is not green: its times are not recorded.")
        return 1
    jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100")["jobs"]
    with open(TIMES, encoding="utf-8") as fh:
        times = json.load(fh)
    for j in jobs:
        m = _minutes(j.get("started_at"), j.get("completed_at"))
        if j.get("conclusion") == "success" and m is not None and m > 0.05:
            times.setdefault("jobs", {})[j["name"]] = round(m, 1)
    files = {}
    for j in jobs:
        if j["name"].startswith("Linux - test suite") and j.get("conclusion") == "success":
            for line in _log(j["id"]).splitlines():
                if line.startswith("PYTEST_FILE_SECS "):
                    files.update(json.loads(line[len("PYTEST_FILE_SECS "):]))
            if j["name"].endswith("packaged self-test"):
                steps = [s for s in j["steps"] if s["name"].startswith("Packaged self-test")]
                m = _minutes(steps[0].get("started_at"), steps[0].get("completed_at")) if steps else None
                if m:
                    files["packaged self-test"] = round(m * 60, 1)
    merge_file_times(times, files)
    times["recorded_from"] = f"run {run['id']} ({run['head_branch']} @ {run['head_sha'][:7]}, {run['created_at'][:10]})"
    with open(TIMES, "w", encoding="utf-8") as fh:
        json.dump(times, fh, indent=1)
        fh.write("\n")
    print(f"Recorded {len(jobs)} jobs and {len(files)} test files from run {run['id']} into {TIMES}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch")
    ap.add_argument("--sha")
    ap.add_argument("--run", type=int)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--log", metavar="JOB_NAME_PART")
    ap.add_argument("--record", action="store_true", help="copy this green run's times into tools/ci_times.json")
    args = ap.parse_args()
    end = time.time() + 90 * 60
    while True:
        run = find_run(args)
        if run is None and not args.run and only_task_list(commit_of(args)):
            print("No test run for this commit: it changes only the task list (TASKS.md, tasks/), which the "
                  "tests skip. The run of the commit before it counts.")
            return 0
        if run is None:
            if args.wait and time.time() < end:
                time.sleep(15)
                continue
            print("No run for this commit yet (GitHub starts one a few seconds after a push; "
                  "an unpushed commit has none).")
            return 2
        if args.wait and run["status"] != "completed" and time.time() < end:
            time.sleep(30)
            continue
        code = show(run, args.log)
        return record(run) if args.record and run["status"] == "completed" else code


if __name__ == "__main__":
    sys.exit(main())
