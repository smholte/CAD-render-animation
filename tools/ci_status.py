"""Show the result of the automatic tests on GitHub, from a chat (or any machine with `gh`).

    python3 tools/ci_status.py                      # run of the current commit (HEAD)
    python3 tools/ci_status.py --branch main        # run of the newest commit on main (on GitHub)
    python3 tools/ci_status.py --sha 1a2b3c4        # run of one commit
    python3 tools/ci_status.py --wait               # wait until the run has finished (max 90 min)
    python3 tools/ci_status.py --run 123456789 --log "Windows"   # whole log of the job(s) matching "Windows"
    python3 tools/ci_status.py --run 123456789 --record   # copy a green run's times into tools/ci_times.json
    python3 tools/ci_status.py --claimed             # the version claim (tasks/MERGING.md on main) and its age
    python3 tools/ci_status.py --claim               # take the claim: the next version, for this branch's task
    python3 tools/ci_status.py --claim --no-version  # a task that raises no version (tools, docs) takes its turn
    python3 tools/ci_status.py --unclaim             # give the claim back (after the merge, or after a second red run)

The claim (task 0383, CLAUDE.md section 2 "One merge at a time"): one line in tasks/MERGING.md on main. --claim and
--unclaim read it from GitHub's main, write only that file in a checkout of its own (a git worktree of origin/main)
and push only that commit to main – a tasks/-only push starts no test run. --claim refuses while another task holds
the claim and shows who holds it, since when, and when its branch last moved. The task number comes from the branch
name (task/NNNN-…) or --task; --trailer "Co-Authored-By: …" lines end the commit message.

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
from datetime import datetime, timezone

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


TASK_LIST_GRACE = 90                             # s: --wait looks this long for a run before "task list only: no run"
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
            "full": "full - all tests",
            "lane": "lane - only the tests of the changed files (version not raised yet); not a release check: the "
                    "full run comes with the version raise or '[full run]' in the commit message",
            "catchup": "catch-up - the branch's full run was green; only the tests of what main brought (and of the "
                       "branch's files) and the build; proves the tree like a full run",
            "stale": "stale - the branch has moved on to a commit with its own run; this run was cancelled",
            }.get(m.group(1), m.group(1))


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
    if not run_mode(jobs).startswith("full"):
        print(f"Run {run['id']} is not a full run (mode {run_mode(jobs).split(' ')[0] or '?'}): its times are not "
              "recorded (its groups are not the full run's).")
        return 1
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


# ---------------------------------------------------------------------------------------------- the version claim

MERGING = "tasks/MERGING.md"
CLAIM_LINE = re.compile(r"^(?P<version>\d+\.\d+\.\d+|no version) · task (?P<task>\d{4}) · (?P<branch>\S+) · "
                        r"claimed (?P<when>\d{1,2} \w{3} \d{1,2}:\d{2})\s*$")
STALE_CLAIM_MIN = 90                              # CLAUDE.md: older than this with no push on its branch → ask the owner


def read_claim(text: str) -> dict | None:
    """The claim line of tasks/MERGING.md as a dict (version, task, branch, when), None when it is free."""
    for line in text.splitlines():
        m = CLAIM_LINE.match(line.strip())
        if m:
            return m.groupdict()
    return None


def claim_time(when: str, now: datetime) -> datetime | None:
    """'28 Nov 18:38' (UTC) as a datetime in now's year (the year before when that would lie in the future)."""
    try:
        t = datetime.strptime(f"{when} {now.year}", "%d %b %H:%M %Y").replace(tzinfo=now.tzinfo)
    except ValueError:
        return None
    return t.replace(year=now.year - 1) if (t - now).days > 1 else t


def write_claim(text: str, line: str) -> str:
    """tasks/MERGING.md with its claim line replaced by ``line`` ('' empties it); the header lines stay."""
    keep = [ln for ln in text.splitlines() if not CLAIM_LINE.match(ln.strip())]
    while keep and not keep[-1].strip():
        keep.pop()
    return "\n".join(keep + ([line] if line else [])) + "\n"


def next_version(main_version: str, released: set[str]) -> str:
    def vt(v):
        return tuple(int(x) for x in re.findall(r"\d+", v)[:3])
    newest = max([main_version] + list(released), key=vt)
    a = list(vt(newest)) + [0, 0, 0]
    return f"{a[0]}.{a[1]}.{a[2] + 1}"


def _released() -> set[str]:
    rels = gh(f"repos/{REPO}/releases?per_page=100")
    return {r["tag_name"][1:] for r in rels if r["tag_name"].startswith("v") and "rehearsal" not in r["tag_name"]}


def _main_text(path: str) -> str:
    r = subprocess.run(["git", "show", f"origin/main:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _branch_moved(branch: str) -> str:
    try:
        c = gh(f"repos/{REPO}/branches/{branch}")["commit"]["commit"]["committer"]["date"]
    except (RuntimeError, KeyError, TypeError):
        return "?"
    return c


def describe_claim(claim: dict | None, now: datetime, branch_moved=_branch_moved) -> list[str]:
    if not claim:
        return ["The version claim is free (tasks/MERGING.md on main has no claim line)."]
    t = claim_time(claim["when"], now)
    age = (now - t).total_seconds() / 60 if t else None
    out = [f"Claimed: {claim['version']} · task {claim['task']} · {claim['branch']} · since {claim['when']} UTC"
           + (f" ({age:.0f} min ago)" if age is not None else "")]
    moved = branch_moved(claim["branch"])
    mt = None
    try:
        mt = datetime.fromisoformat(moved.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    if mt:
        out.append(f"  its branch last moved {(now - mt).total_seconds() / 60:.0f} min ago")
    if age is not None and age > STALE_CLAIM_MIN and (mt is None or (now - mt).total_seconds() / 60 > STALE_CLAIM_MIN):
        out.append(f"  older than {STALE_CLAIM_MIN} min with no push on its branch: ask the owner whether that session "
                   "stopped (CLAUDE.md section 2) – never take the claim over yourself")
    return out


def _current_task(branch: str) -> str:
    m = re.match(r"task/(\d{4})", branch)
    return m.group(1) if m else ""


def push_claim(new_text: str, message: str) -> tuple[bool, str]:
    """Commit tasks/MERGING.md = new_text on top of origin/main in a worktree of its own and push it to main."""
    import tempfile
    tmp = tempfile.mkdtemp(prefix="fr-claim-")
    wt = os.path.join(tmp, "main")
    try:
        r = subprocess.run(["git", "worktree", "add", "-q", "--detach", wt, "origin/main"], capture_output=True, text=True)
        if r.returncode:
            return False, r.stderr.strip()
        with open(os.path.join(wt, MERGING), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(new_text)
        for cmd in (["git", "-C", wt, "add", MERGING], ["git", "-C", wt, "commit", "-q", "-m", message],
                    ["git", "-C", wt, "push", "-q", "origin", "HEAD:main"]):
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode:
                return False, (r.stderr or r.stdout).strip()
        return True, ""
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", wt], capture_output=True)
        subprocess.run(["git", "worktree", "prune"], capture_output=True)


def claim(args, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    branch = args.claim_branch or _git("rev-parse", "--abbrev-ref", "HEAD")
    task = args.task or _current_task(branch)
    for attempt in range(3):
        if subprocess.run(["git", "fetch", "-q", "origin", "main:refs/remotes/origin/main"]).returncode:
            print("Could not fetch main from GitHub.")
            return 2
        text = _main_text(MERGING)
        held = read_claim(text)
        if args.claimed:
            print("\n".join(describe_claim(held, now)))
            return 0
        mine = bool(held and task and held["task"] == task)
        if args.unclaim:
            if not held:
                print("The claim is free already.")
                return 0
            if not mine and not args.force:
                print("\n".join(describe_claim(held, now)))
                print(f"Not yours (task {task or '?'}): only the task that holds a claim gives it back.")
                return 1
            new = write_claim(text, "")
            msg = f"Version claim: free again (task {held['task']}, {held['version']})"
        else:
            if not task:
                print("No task number: work on a branch task/NNNN-… or give --task NNNN.")
                return 2
            if held and not mine:
                print("\n".join(describe_claim(held, now)))
                print("Held by another task: do not merge main, do not raise the version, do not push code. Finish the "
                      "report and the guide; check again with this command in about 15 minutes.")
                return 1
            if mine:
                print("\n".join(describe_claim(held, now)))
                print("You hold the claim already.")
                return 0
            if args.no_version:
                version = "no version"
            else:
                main_v = re.search(r'(?m)^version\s*=\s*"([^"]+)"', _main_text("fresing_render/blender_manifest.toml"))
                version = next_version(main_v.group(1) if main_v else "0.0.0", _released())
            line = f"{version} · task {task} · {branch} · claimed {now.strftime('%d %b %H:%M').lstrip('0')}"
            new = write_claim(text, line)
            msg = f"Version claim: {version} for task {task}"
        if args.trailer:                           # the session's attribution lines, after a blank line
            msg += "\n\n" + "\n".join(args.trailer)
        ok, err = push_claim(new, msg)
        if ok:
            if args.unclaim:
                print("The claim is free again (tasks/MERGING.md on main).")
            else:
                print(f"Claimed: {line}")
                if version != "no version":
                    print(f"Next: merge main once, raise both version files to {version}, its CHANGELOG heading, the "
                          "tour / function versions, push once (a catch-up run when your [full run] was green). "
                          "Green: fast-forward main, then --unclaim in the report push.")
            return 0
        print(f"The push to main was refused ({err.splitlines()[-1] if err else '?'}): someone pushed first; reading "
              "the claim again.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch")
    ap.add_argument("--sha")
    ap.add_argument("--run", type=int)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--log", metavar="JOB_NAME_PART")
    ap.add_argument("--record", action="store_true", help="copy this green run's times into tools/ci_times.json")
    ap.add_argument("--claim", action="store_true", help="take the version claim (tasks/MERGING.md on main)")
    ap.add_argument("--unclaim", action="store_true", help="give the version claim back")
    ap.add_argument("--claimed", action="store_true", help="show the version claim and its age")
    ap.add_argument("--no-version", action="store_true", help="with --claim: a task that raises no version")
    ap.add_argument("--task", help="the task number for --claim / --unclaim (default: from the branch name)")
    ap.add_argument("--claim-branch", help="the branch named in the claim (default: the current branch)")
    ap.add_argument("--force", action="store_true", help="with --unclaim: also another task's claim (the owner said so)")
    ap.add_argument("--trailer", action="append", help="a line for the end of the claim's commit message")
    args = ap.parse_args()
    if args.claim or args.unclaim or args.claimed:
        return claim(args)
    end = time.time() + 90 * 60
    grace = time.time() + TASK_LIST_GRACE
    while True:
        run = find_run(args)
        # task 0171 (0170's open point): a push of "merge main + report" whose LAST commit touches only tasks/ does get
        # a run (GitHub looks at everything the push brought); it just appears a few seconds after the push
        if run is None and args.wait and not args.run and time.time() < grace:
            time.sleep(15)
            continue
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
