"""About Fresing Render (task 0206): where the licence files are and the words of the About window. No Blender.

The licence files ship inside the extension (``licenses/``: ``LICENSE``, ``THIRD-PARTY-NOTICES.md``, ``COMPANY-USE.md``
and the folder ``third-party/`` with the texts of the libraries), so every install and every update brings them, offline.
A checkout of the repository has the same files at its root; they are found there when the package folder has none.
"""

from __future__ import annotations

import os

FOLDER = "licenses"
LICENCE = "LICENSE"
NOTICES = "THIRD-PARTY-NOTICES.md"
COMPANY = "COMPANY-USE.md"
THIRD_PARTY = "third-party"
COMPANY_URL = "https://github.com/smholte/CAD-render-animation/blob/main/docs/COMPANY-USE.md"
HOLDER = "Fresing"
YEAR = "2026"

# the text files an install must carry (the PC-check line and the tests look for exactly these)
REQUIRED = (LICENCE, NOTICES, COMPANY, f"{THIRD_PARTY}/SOURCES.txt")


def folder(package_dir: str) -> str:
    """The licence folder of the installed extension, else the repository's root (a checkout)."""
    inside = os.path.join(package_dir, FOLDER)
    if os.path.isfile(os.path.join(inside, LICENCE)):
        return inside
    root = os.path.dirname(package_dir)
    if os.path.isfile(os.path.join(root, LICENCE)):
        return root
    return inside


def find(package_dir: str, name: str) -> str:
    """The path of one licence file, or "" when this install does not have it."""
    path = os.path.join(folder(package_dir), name)
    if os.path.isfile(path):
        return path
    if name == COMPANY:                              # a checkout keeps it under docs/
        alt = os.path.join(os.path.dirname(package_dir), "docs", COMPANY)
        if os.path.isfile(alt):
            return alt
    return ""


def missing(package_dir: str) -> list[str]:
    """Which of the required files this install lacks (empty = all there)."""
    return [name for name in REQUIRED if not find(package_dir, name)]


def lines(version: str, blender_version: str) -> list[str]:
    """The words of the About window (plain, one idea per line)."""
    return [
        f"Version {version}, running on Blender {blender_version}.",
        f"© {YEAR} {HOLDER}. Free software under the GPL-3.0-or-later licence, with no warranty.",
        "You may use it, also at work and for commercial jobs. The licence file has the details.",
        "Everything here works offline: the files are inside this install.",
    ]
