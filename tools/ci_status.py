"""Show the result of the automatic tests on GitHub, from a chat (or any machine with `gh`).

    python3 tools/ci_status.py                      # newest run of the current commit (or branch)
    python3 tools/ci_status.py --branch main        # newest run on main
    python3 tools/ci_status.py --sha 1a2b3c4        # run of one commit
    python3 tools/ci_status.py --wait               # wait until the run has finished (max 90 min)
    python3 tools/ci_status.py --run 123456789 --log "Windows"   # whole log of the job(s) matching "Windows"

Prints each job with its time and, for a failed job, the failing step, the error annotations and
the last lines of its log. Exit code: 0 = all jobs passed, 1 = something failed, 2 = still running
or no run found. Uses the `gh` command (set up in the chats); only the GitHub API paths for runs,
jobs, job logs and annotations are needed.
"""

from __future__ import annotations

import argparse
import json
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


def find_run(args):
    if args.run:
        return gh(f"repos/{REPO}/actions/runs/{args.run}")
    if args.sha:
        sha = _git("rev-parse", args.sha) or args.sha
        runs = gh(f"repos/{REPO}/actions/runs?head_sha={sha}&per_page=20")["workflow_runs"]
    else:
        branch = args.branch or _git("rev-parse", "--abbrev-ref", "HEAD")
        if not args.branch:
            sha = _git("rev-parse", "HEAD")
            runs = gh(f"repos/{REPO}/actions/runs?head_sha={sha}&per_page=20")["workflow_runs"]
            if runs:
                return _prefer_push(runs)
        runs = gh(f"repos/{REPO}/actions/runs?branch={branch}&per_page=20")["workflow_runs"]
    return _prefer_push(runs) if runs else None


def _prefer_push(runs):
    runs = sorted(runs, key=lambda r: r["created_at"], reverse=True)
    push = [r for r in runs if r["event"] == "push"]
    return (push or runs)[0]


def _secs(job) -> str:
    try:
        a = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
        b = datetime.fromisoformat((job["completed_at"] or "").replace("Z", "+00:00"))
        return f"{(b - a).total_seconds() / 60:.1f} min"
    except (TypeError, ValueError, AttributeError):
        return "running"


def show(run, log_filter: str | None) -> int:
    print(f"Run {run['id']} ({run['event']}) on {run['head_branch']} @ {run['head_sha'][:7]}: "
          f"{run['status']} {run.get('conclusion') or ''}")
    print(f"  {run['html_url']}")
    jobs = gh(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=50")["jobs"]
    bad = False
    for job in jobs:
        state = job["conclusion"] or job["status"]
        mark = {"success": "OK  ", "failure": "FAIL", "cancelled": "STOP", "skipped": "skip"}.get(state, state)
        print(f"  [{mark}] {job['name']} ({_secs(job)})")
        if state in ("failure", "cancelled", "timed_out"):
            bad = True
            for st in job["steps"]:
                if st.get("conclusion") == "failure":
                    print(f"         failed step: {st['name']}")
            try:
                for a in gh(f"repos/{REPO}/check-runs/{job['id']}/annotations"):
                    if a.get("annotation_level") == "failure":
                        print(f"         ! {a.get('title') or ''}: {a.get('message', '')[:300]}")
            except RuntimeError:
                pass
            if not log_filter:
                log = _log(job["id"]).split("\nPost job cleanup.")[0]      # git clean-up noise after it
                tail = [ln for ln in log.splitlines() if ln.strip()][-40:]
                print("         --- last lines of the log ---")
                for ln in tail:
                    print("         " + ln[:240])
        if log_filter and log_filter.lower() in job["name"].lower():
            print(_log(job["id"]))
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch")
    ap.add_argument("--sha")
    ap.add_argument("--run", type=int)
    ap.add_argument("--wait", action="store_true")
    ap.add_argument("--log", metavar="JOB_NAME_PART")
    args = ap.parse_args()
    end = time.time() + 90 * 60
    while True:
        run = find_run(args)
        if run is None:
            if args.wait and time.time() < end:
                time.sleep(15)
                continue
            print("No run found (GitHub starts one a few seconds after a push).")
            return 2
        if args.wait and run["status"] != "completed" and time.time() < end:
            time.sleep(30)
            continue
        return show(run, args.log)


if __name__ == "__main__":
    sys.exit(main())
