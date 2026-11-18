#!/usr/bin/env python3
"""Check what the toolbox format describes.

    python3 check.py samples/Toolbox                 # a whole Toolbox folder: every manifest and every job in it
    python3 check.py path/to/toolbox.json            # one tool's manifest
    python3 check.py path/to/inbox/<job id>          # one job folder
    python3 check.py types.json                      # the built-in list of file types
    python3 check.py --type part.step house.hpscene  # which file type each file is

Prints the problems (ERROR: a reader must refuse it; WARNING: readable, but look at it). Exit code 1 when anything
has an error. Needs Python 3.10+ and `jsonschema` (pip install -r requirements.txt).
"""
from __future__ import annotations

import argparse
import sys

from tbf.check import check
from tbf.detect import detect, load_types


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("paths", nargs="+", help="Toolbox folders, job folders, toolbox.json or types.json files")
    ap.add_argument("--type", action="store_true", help="say which file type each file is, instead of checking")
    ap.add_argument("-q", "--quiet", action="store_true", help="print only what has problems")
    a = ap.parse_args(argv)
    if a.type:
        types, bad = load_types(), 0
        for p in a.paths:
            try:
                found, note = detect(p, types)
                print(f"{p}: {found}" + (f"  ({note})" if note else ""))
            except OSError as e:
                bad = 1
                print(f"{p}: cannot be read ({e.strerror or e})")
        return bad
    bad = 0
    for p in a.paths:
        rep = check(p)
        bad += not rep.ok
        if rep.items or not a.quiet:
            print(rep.text())
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
