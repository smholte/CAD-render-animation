"""The sources of the site's moving models, cloned at pinned commits (task 0112). Only the folders needed are
checked out (Thor: freecad-src, 118 MB; the press: its CAD folder). Kept in ``cache`` between runs.

The wind turbine (task 0116) comes from the owner's STEP on the draft release ``site-kit`` (the IEA's SolidWorks model
exported in Fusion): ``FRESING_IEA15_STEP`` (a path) wins, then the copy in the cache, else it is downloaded with
``GITHUB_TOKEN`` / ``GH_TOKEN`` (a draft is only seen with push access) or the ``gh`` command."""

from __future__ import annotations

import os
import subprocess

SOURCES = {
    "thor": {"url": "https://github.com/AngelLM/Thor.git", "commit": "286b081fe6f056d87c379b884781ef77ff6a0159",
             "folder": "freecad-src", "licence": "CC BY-SA 4.0"},
    "ceb_press": {"url": "https://github.com/goscommons/CEB-Press.git",
                  "commit": "a5bd76f9be64e0d2b92485dbf433ef3c9d603a1f", "folder": "01_Hardware/CAD",
                  "licence": "CC BY-SA 4.0"},
}
RELEASE = {"repo": "smholte/CAD-render-animation", "tag": "site-kit"}
STEP_ASSETS = {
    "iea15_offshore": {"asset": "15MW.step", "env": "FRESING_IEA15_STEP", "licence": "Apache-2.0",
                       "url": "https://github.com/IEAWindSystems/IEA-15-240-RWT"},
}
STEP_ASSETS["iea15_onshore"] = STEP_ASSETS["iea15_offshore"]


def default_cache() -> str:
    return os.environ.get("FRESING_SITE_SOURCES") or os.path.join(os.path.expanduser("~"), ".cache",
                                                                   "fresing_site_sources")


def _git(*args, cwd=None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _download_asset(name: str, dest: str) -> None:
    import json
    import urllib.request
    repo, tag = RELEASE["repo"], RELEASE["tag"]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    tmp = dest + ".part"
    if token:
        def get(url, accept="application/vnd.github+json"):
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": accept,
                                                       "User-Agent": "fresing-site-kit"})
            return urllib.request.urlopen(req, timeout=600)
        with get(f"https://api.github.com/repos/{repo}/releases?per_page=100") as r:
            rels = json.loads(r.read())
        rel = next((x for x in rels if x.get("tag_name") == tag), None)
        asset = next((a for a in (rel or {}).get("assets", []) if a["name"] == name), None)
        if asset is None:
            raise SystemExit(f"{name} is not on the draft release '{tag}' (or the token cannot see drafts)")
        with get(asset["url"], "application/octet-stream") as r, open(tmp, "wb") as fh:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                fh.write(chunk)
    else:
        try:
            rels = json.loads(subprocess.run(["gh", "api", f"repos/{repo}/releases?per_page=100"], check=True,
                                             capture_output=True, text=True).stdout)
        except (OSError, subprocess.CalledProcessError) as e:
            raise SystemExit(f"{name}: no GITHUB_TOKEN and no working gh command ({e}); set FRESING_IEA15_STEP to "
                             "the file instead") from e
        rel = next((x for x in rels if x.get("tag_name") == tag), None)
        asset = next((a for a in (rel or {}).get("assets", []) if a["name"] == name), None)
        if asset is None:
            raise SystemExit(f"{name} is not on the draft release '{tag}'")
        with open(tmp, "wb") as fh:
            subprocess.run(["gh", "api", "-H", "Accept: application/octet-stream",
                            f"repos/{repo}/releases/assets/{asset['id']}"], check=True, stdout=fh)
    os.replace(tmp, dest)


def fetch_step(model: str, cache: str = "") -> str:
    """The owner's STEP of ``model`` (a path)."""
    src = STEP_ASSETS[model]
    own = os.environ.get(src["env"], "")
    if own:
        if not os.path.isfile(own):
            raise SystemExit(f"{src['env']}={own}: no such file")
        return own
    cache = cache or default_cache()
    dest = os.path.join(cache, "iea15", src["asset"])
    if not os.path.isfile(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        _download_asset(src["asset"], dest)
    return dest


def available(model: str) -> bool:
    """Whether the source of ``model`` can be had here without asking anyone (git sources: always)."""
    if model not in STEP_ASSETS:
        return True
    src = STEP_ASSETS[model]
    return bool(os.environ.get(src["env"])) or os.path.isfile(
        os.path.join(default_cache(), "iea15", src["asset"])) or bool(
        os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))


def fetch(model: str, cache: str = "") -> str:
    """The source folder of ``model`` (cloned once, at the pinned commit). Returns the folder with the files; for a
    model made from the owner's STEP (STEP_ASSETS), the STEP's path."""
    if model in STEP_ASSETS:
        return fetch_step(model, cache)
    src = SOURCES[model]
    cache = cache or default_cache()
    repo = os.path.join(cache, model)
    folder = os.path.join(repo, *src["folder"].split("/"))
    stamp = os.path.join(repo, ".fresing_commit")
    if os.path.isdir(folder) and os.path.isfile(stamp) and open(stamp).read().strip() == src["commit"]:
        return folder
    os.makedirs(cache, exist_ok=True)
    if not os.path.isdir(os.path.join(repo, ".git")):
        _git("clone", "--filter=blob:none", "--no-checkout", "--sparse", src["url"], repo)
    _git("sparse-checkout", "set", src["folder"], cwd=repo)
    try:
        _git("checkout", "--quiet", src["commit"], cwd=repo)
    except subprocess.CalledProcessError:          # a shallow or older clone: get the commit first
        _git("fetch", "--quiet", "origin", src["commit"], cwd=repo)
        _git("checkout", "--quiet", src["commit"], cwd=repo)
    with open(stamp, "w") as fh:
        fh.write(src["commit"])
    return folder
