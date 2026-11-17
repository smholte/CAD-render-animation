"""Write the built-in crane classes (task 0191): ``<out>/<class>/<class>.step`` + ``<class>.json``.

    python -m fresing_render.lifting_model.make <out folder> [--only AT-40,CC-100]

The pictures are made separately with Blender (``tools/make_lifting_cranes.py --pictures``). The JSON is written
with sorted keys and two-space indents so a rebuild changes only what changed (the STEP writer is not byte-stable).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import classes as C
from . import equipment as E

BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "lifting")


def builder(kind: str):
    if kind == "AT":
        from . import mobile
        return mobile.build
    if kind == "CC":
        from . import crawler
        return crawler.build
    from . import knuckle
    return knuckle.build


def model(name: str):
    """(root Asm, layout) of a class."""
    c = C.CLASSES[name]
    return builder(c.kind)(c)


def json_text(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def write_class(name: str, out: str, step: bool = True) -> dict:
    """One class's folder. Returns a summary (parts, seconds, sizes)."""
    from . import common
    t0 = time.time()
    root, _L = model(name)
    cogs = common.group_cogs(root, E.groups(name))
    data = E.data(name, cogs)
    folder = os.path.join(out, name)
    os.makedirs(folder, exist_ok=True)
    js = os.path.join(folder, f"{name}.json")
    with open(js, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json_text(data))
    st = os.path.join(folder, f"{name}.step")
    if step:
        common.write_step(root, st)
    return {"class": name, "parts": common.count_parts(root), "seconds": round(time.time() - t0, 1),
            "json_kb": round(os.path.getsize(js) / 1024, 1),
            "step_kb": round(os.path.getsize(st) / 1024, 1) if os.path.isfile(st) else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", nargs="?", default=BUILTIN_DIR, help="folder to write into (default: the built-ins)")
    ap.add_argument("--only", default="", help="comma-separated classes (default: all 12)")
    ap.add_argument("--json-only", action="store_true", help="write only the JSON (keeps the STEP files)")
    a = ap.parse_args(argv)
    only = [x.strip() for x in a.only.split(",") if x.strip()] or list(C.CLASSES)
    bad = [x for x in only if x not in C.CLASSES]
    if bad:
        ap.error("unknown classes: " + ", ".join(bad))
    for name in only:
        print(json.dumps(write_class(name, a.out, step=not a.json_only)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
