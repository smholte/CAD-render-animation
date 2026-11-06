"""Helpers for the release job on GitHub (.github/workflows/tests.yml, job "Publish the release").

    python tools/release_tools.py plan --ref refs/heads/main --run 123
        -> prints version=…, tag=…, prerelease=…, publish=true|false (for $GITHUB_OUTPUT)
    python tools/release_tools.py prepare --repo-dir <update-repo> --out <dir> --tag v0.2.16 --repository owner/name
        -> <dir>/index.json (full download addresses), changelog.json, notes.md (release text)
    python tools/release_tools.py verify-run --run 123 --tree <git tree hash>
        -> exit 1 unless run 123 is green (all required jobs) and was made from this exact git tree
           (mode "reuse", task 0036: the release uses the installer files of that run)

plan: on main the tag is v<version>; when that release exists already nothing is published (a version is
published once; the next version bump publishes the next). On a branch whose newest commit message holds
"[release rehearsal]" the tag is v<version>-rehearsal.<run> and it is a pre-release (the job deletes it
again after the check), to try the whole path before merging.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from fresing_render.core import updates  # noqa: E402


def manifest_version() -> str:
    text = open(os.path.join(ROOT, "fresing_render", "blender_manifest.toml"), encoding="utf-8").read()
    return re.search(r'(?m)^version\s*=\s*"([^"]+)"', text).group(1)


def release_exists(tag: str) -> bool:
    """Asks GitHub (gh CLI with the job's token)."""
    p = subprocess.run(["gh", "release", "view", tag, "--json", "tagName"], capture_output=True, text=True)
    if p.returncode == 0:
        return True
    if "release not found" in (p.stderr or "").lower() or "not found" in (p.stderr or "").lower():
        return False
    raise SystemExit(f"could not ask GitHub about release {tag}: {p.stderr.strip()}")


def plan(ref: str, run_id: str, rehearsal: bool, exists=release_exists) -> dict:
    version = manifest_version()
    if ref == "refs/heads/main":
        tag = f"v{version}"
        return {"version": version, "tag": tag, "prerelease": "false", "publish": "false" if exists(tag) else "true"}
    if rehearsal:
        return {"version": version, "tag": f"v{version}-rehearsal.{run_id}", "prerelease": "true", "publish": "true"}
    return {"version": version, "tag": "", "prerelease": "false", "publish": "false"}


def notes(version: str, repository: str, tag: str) -> str:
    """The release text: how to get it, then what changed (the CHANGELOG section)."""
    entries = updates.parse_changelog(open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read())
    entry = next((e for e in entries if e["version"] == version), None)
    if entry is None:
        raise SystemExit(f"CHANGELOG.md has no section for {version}")
    head = [
        "**How to get it**",
        "",
        f"- Fresing Render {updates.SELF_UPDATING_SINCE} or newer is installed: the app offers this version by itself – "
        "\"Update available\" at the top of the Fresing tab, then **Update now**.",
        f"- New PC, or an older version: download **FresingRender-{version}-windows.zip** below, unzip it, "
        "double-click **Install.bat**.",
        "",
        "**What's new**" + (f" – {entry['title']}" if entry.get("title") else ""),
        "",
    ]
    return "\n".join(head) + entry["text"].strip() + "\n"


def prepare(repo_dir: str, out: str, tag: str, repository: str) -> list[str]:
    """Release files: the extension zip, index.json with full download addresses, changelog.json, notes.md."""
    os.makedirs(out, exist_ok=True)
    base = f"https://github.com/{repository}/releases/download/{tag}"
    index = json.load(open(os.path.join(repo_dir, "index.json"), encoding="utf-8"))
    files = []
    for item in index.get("data", []):
        url = item.get("archive_url", "")
        name = url[2:] if url.startswith("./") else url.rsplit("/", 1)[-1]
        item["archive_url"] = f"{base}/{name}"
        shutil.copy2(os.path.join(repo_dir, name), os.path.join(out, name))
        files.append(name)
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
    shutil.copy2(os.path.join(repo_dir, "changelog.json"), os.path.join(out, "changelog.json"))
    version = tag[1:].split("-rehearsal", 1)[0]
    with open(os.path.join(out, "notes.md"), "w", encoding="utf-8") as fh:
        fh.write(notes(version, repository, tag))
    return files + ["index.json", "changelog.json"]


def verify_run(run_id: str, tree: str, api=None) -> tuple[bool, str]:
    """The run whose installer files a reuse release takes: green, all required jobs green, the same git tree."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import ci_precheck
    api = api or ci_precheck.gh_api
    repo = os.environ.get("GITHUB_REPOSITORY", ci_precheck.REPO)
    run = api(f"repos/{repo}/actions/runs/{run_id}")
    got = (run.get("head_commit") or {}).get("tree_id", "")
    if got != tree:
        return False, f"run {run_id} tested tree {got[:7] or '?'}, this commit has tree {tree[:7]}"
    jobs = api(f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100")["jobs"]
    return ci_precheck.run_is_proven(run, jobs)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--ref", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--rehearsal", action="store_true")
    q = sub.add_parser("prepare")
    q.add_argument("--repo-dir", required=True)
    q.add_argument("--out", required=True)
    q.add_argument("--tag", required=True)
    q.add_argument("--repository", required=True)
    w = sub.add_parser("verify-run")
    w.add_argument("--run", required=True)
    w.add_argument("--tree", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "verify-run":
        ok, why = verify_run(args.run, args.tree)
        print(("OK: " if ok else "NOT PROVEN: ") + why)
        return 0 if ok else 1
    if args.cmd == "plan":
        for k, v in plan(args.ref, args.run, args.rehearsal).items():
            print(f"{k}={v}")
    else:
        print("\n".join(prepare(args.repo_dir, args.out, args.tag, args.repository)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
