"""The sources of the site's moving models, cloned at pinned commits (task 0112). Only the folders needed are
checked out (Thor: freecad-src, 118 MB; the press: its CAD folder). Kept in ``cache`` between runs."""

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


def default_cache() -> str:
    return os.environ.get("FRESING_SITE_SOURCES") or os.path.join(os.path.expanduser("~"), ".cache",
                                                                   "fresing_site_sources")


def _git(*args, cwd=None) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def fetch(model: str, cache: str = "") -> str:
    """The source folder of ``model`` (cloned once, at the pinned commit). Returns the folder with the files."""
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
