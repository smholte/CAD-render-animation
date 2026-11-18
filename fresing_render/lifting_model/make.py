"""Write the built-in crane classes (task 0191): ``<out>/<class>/<class>.step`` + ``<class>.json``.

    python -m fresing_render.lifting_model.make <out folder> [--only AT-40,CC-100]
    python make.py <out folder> --params <crane.json> [--progress <progress.json>]     (task 0204: a made crane)

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


# ---------------------------------------------------------------------------------------------------------------------
# A crane made from numbers (task 0204, 8 Lifting plan > Equipment > Make a crane…)

SPEC_FORMAT = "fresing-crane-numbers"


def _progress(path: str | None, stage: str, share: float) -> None:
    if not path:
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"stage": stage, "share": round(share, 3)}, fh)
    for _k in range(3):                  # Windows: the app may be reading it this very moment (only cosmetic)
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.02)


def made_data(c, cogs: dict, spec: dict, stem: str) -> dict:
    """The equipment file of a made crane: ``equipment.data`` for its own dataclass, SAMPLE, ``derived_from`` = its
    own chart hash (L2's rule: the mark comes off only once a real chart replaced these), ``made_from`` = the class it
    started from and every number."""
    from ..core import lifting_library as LL
    from . import params as P
    kind = spec["kind"]
    d = E.data(c, cogs, step=f"{stem}.step", cls_word=P.class_word(kind, spec["values"]))
    d["source"] = f"made in Fresing Render from numbers (Make a crane…), started from the class {spec['start']}"
    d["derived_from"] = LL.chart_hash(d)
    d["made_from"] = {"class": spec["start"], "kind": kind, "app": spec.get("app", ""),
                      "values": {k: (list(v) if isinstance(v, (tuple, list)) else v)
                                 for k, v in sorted(spec["values"].items())}}
    return d


def make_crane(spec: dict, out: str, progress: str | None = None, picture: bool = True) -> dict:
    """``<out>/<stem>.step``, ``<stem>.json``, ``<stem>.png`` of a crane from its numbers (``spec``: kind, name,
    start, values). ValueError naming every rule the numbers break (nothing written)."""
    from ..core import lifting_library as LL
    from . import common
    from . import params as P
    t0 = time.time()
    kind, name = spec["kind"], str(spec["name"]).strip()
    values = {k: (tuple(v) if isinstance(v, list) else v) for k, v in spec["values"].items()}
    spec = dict(spec, values=values)
    problems = P.validate(kind, values)
    if problems:
        raise ValueError(" ".join(p.text for p in problems))
    stem = LL.folder_name(name)
    c = P.to_class(kind, values, name)
    _progress(progress, "shapes", 0.05)
    root, _L = builder(kind)(c)
    _progress(progress, "masses", 0.45)
    cogs = common.group_cogs(root, E.groups(c))
    data = made_data(c, cogs, spec, stem)
    os.makedirs(out, exist_ok=True)
    _progress(progress, "step", 0.55)
    common.write_step(root, os.path.join(out, f"{stem}.step"))
    if picture:
        _progress(progress, "picture", 0.8)
        from . import picture as PI
        PI.picture(root, os.path.join(out, f"{stem}.png"))
    with open(os.path.join(out, f"{stem}.json"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json_text(data))
    _progress(progress, "done", 1.0)
    return {"name": name, "stem": stem, "parts": common.count_parts(root), "seconds": round(time.time() - t0, 2)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", nargs="?", default=BUILTIN_DIR, help="folder to write into (default: the built-ins)")
    ap.add_argument("--only", default="", help="comma-separated classes (default: all 12)")
    ap.add_argument("--json-only", action="store_true", help="write only the JSON (keeps the STEP files)")
    ap.add_argument("--params", default="", help="a made crane's numbers (JSON: kind, name, start, values)")
    ap.add_argument("--progress", default="", help="with --params: a JSON file the maker writes its stage into")
    a = ap.parse_args(argv)
    if a.params:
        with open(a.params, encoding="utf-8") as fh:
            spec = json.load(fh)
        try:
            print(json.dumps(make_crane(spec, a.out, a.progress or None)), flush=True)
        except ValueError as exc:
            print(f"NOT MADE: {exc}", flush=True)
            return 2
        return 0
    only = [x.strip() for x in a.only.split(",") if x.strip()] or list(C.CLASSES)
    bad = [x for x in only if x not in C.CLASSES]
    if bad:
        ap.error("unknown classes: " + ", ".join(bad))
    for name in only:
        print(json.dumps(write_class(name, a.out, step=not a.json_only)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
