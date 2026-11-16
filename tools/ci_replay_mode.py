"""Replay the precheck's mode decision for pushes that already ran (task 0170).

    python3 tools/ci_replay_mode.py <run id> [<run id> …]

Reads each run's commit, branch and `before` (from its precheck log), runs today's `ci_precheck.decide()` against
the real git history and the real GitHub runs (read only, no waiting), and prints the mode it would pick now next to
the mode the run got. Runs newer than the replayed one are left out, so the answer is what the precheck would have
seen at that push. Needs `gh` and the history of the commits (`git fetch --unshallow`)."""
from __future__ import annotations

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_precheck as P  # noqa: E402


def log_of(run: str) -> str:
    jobs = P.gh_api(f"repos/{P.REPO}/actions/runs/{run}/jobs?per_page=100")["jobs"]
    pre = [j for j in jobs if j["name"].startswith("Precheck")][0]
    r = subprocess.run(["gh", "api", f"repos/{P.REPO}/actions/jobs/{pre['id']}/logs"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout


def as_of(created: str):
    """An API that hides runs started after `created` and shows runs that were still going then as going."""
    cache = {}

    def api(path):
        if path not in cache:
            cache[path] = P.gh_api(path)
        data = cache[path]
        if "workflow_runs" in data:
            runs = []
            for r in data["workflow_runs"]:
                if r["created_at"] >= created:
                    continue
                if r.get("updated_at", "") > created:
                    r = dict(r, status="in_progress", conclusion=None)
                runs.append(r)
            return dict(data, workflow_runs=runs)
        return data
    return api


def replay(run: str) -> str:
    info = P.gh_api(f"repos/{P.REPO}/actions/runs/{run}")
    log = log_of(run)
    m = re.search(r"BEFORE: ([0-9a-f]{40})", log)
    got = re.search(r"\*\*Mode: (\w+)\*\* – (.*)", log)
    before = m.group(1) if m else ""
    mode, _, why = P.decide("push", "refs/heads/" + info["head_branch"], info["head_sha"], before, run,
                            as_of(info["created_at"]), sleep=lambda s: None)
    return (f"run {run} {info['head_sha'][:7]} \"{info['head_commit']['message'].splitlines()[0][:60]}\"\n"
            f"  then: {got.group(1) if got else '?'} – {got.group(2) if got else ''}\n"
            f"  now:  {mode} – {why}")


if __name__ == "__main__":
    for r in sys.argv[1:]:
        print(replay(r))
