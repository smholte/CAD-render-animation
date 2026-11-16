#!/usr/bin/env python3
"""Check house scene format packages.

    python3 check.py house.hpscene                 # one package
    python3 check.py house.hpbake --scene house.hpscene   # a bake, and whether it fits the scene it was made from
    python3 check.py samples/*                     # several; a .hpbake is checked against the .hpscene whose id it names

Prints the problems (ERROR: a reader must refuse it; WARNING: readable, but look at it). Exit code 1 when any package
has an error. Needs Python 3.10+ and `jsonschema` (pip install -r requirements.txt).
"""
from __future__ import annotations

import argparse
import sys

from hsf.check import check
from hsf.package import Package, PackageError


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("packages", nargs="+", help=".hpscene / .hpbake files")
    ap.add_argument("--scene", help="the .hpscene the bake(s) were made from")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only packages with problems")
    a = ap.parse_args(argv)
    scenes = {}
    for p in a.packages:
        try:
            pkg = Package.open(p)
        except (PackageError, OSError):
            continue
        if pkg.kind == "house-scene" and isinstance(pkg.doc.get("id"), str):
            scenes[pkg.doc["id"]] = p
    bad = 0
    for p in a.packages:
        scene = a.scene
        if scene is None and p.endswith(".hpbake"):
            try:
                sid = (Package.open(p).doc.get("scene") or {}).get("id")
                scene = scenes.get(sid)
            except (PackageError, OSError, AttributeError):
                scene = None
        rep = check(p, scene=scene)
        if scene and p.endswith(".hpbake"):
            rep.name += f" (against {scene})"
        bad += not rep.ok
        if rep.items or not a.quiet:
            print(rep.text())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
