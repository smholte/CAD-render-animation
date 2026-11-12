"""Write the invented cable-lay vessel spread into a folder (task 0077: the app's Help > Make demo project).

    python make.py <out folder> [--cable-d 200] [--only assembly,quay_loading] [--progress <file.json>]

Runs as its own program (Blender's Python with the bundled OpenCascade, like ``pccheck/heavy_scene.py``), so its
memory does not count for the app and Cancel can stop it at any moment. It loads this folder as a package by its
path: no relative-import surprises when it runs as a script, nothing of ``tools/`` needed. ``--progress`` writes
{"stage": "write", "done": i, "total": n} before each file. The file list and what each holds: ``layout.FILES``
and ``tools/make_demo_cable_lay.py`` (the same command for development).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = "fresing_demo_model"


def package():
    """This folder as a package (whatever name it was imported under)."""
    if __package__:
        return importlib.import_module(__package__)
    if PACKAGE not in sys.modules:
        spec = importlib.util.spec_from_file_location(PACKAGE, os.path.join(HERE, "__init__.py"),
                                                      submodule_search_locations=[HERE])
        mod = importlib.util.module_from_spec(spec)
        sys.modules[PACKAGE] = mod
        spec.loader.exec_module(mod)
    return sys.modules[PACKAGE]


def write_progress(path: str, **data) -> None:
    if not path:
        return
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out", help="folder to write into (made if missing)")
    ap.add_argument("--cable-d", type=float, default=200.0, help="cable Ø in mm (50 … 500)")
    ap.add_argument("--only", default="", help="comma-separated keys of layout.FILES to write (default: all)")
    ap.add_argument("--progress", default="", help="a JSON file the progress is written to")
    a = ap.parse_args(argv)
    pkg = package().__name__
    layout = importlib.import_module(pkg + ".layout")
    params = importlib.import_module(pkg + ".params")
    only = tuple(k.strip() for k in a.only.split(",") if k.strip())
    unknown = [k for k in only if k not in layout.FILES]
    if unknown:
        ap.error("unknown file keys: " + ", ".join(unknown))
    t = time.time()
    write_progress(a.progress, stage="build", done=0, total=1)

    def progress(i, n):
        write_progress(a.progress, stage="write", done=i, total=n)

    S = layout.write(a.out, params.Params(cable_d=a.cable_d), only=only, progress=progress)
    write_progress(a.progress, stage="done", done=1, total=1, seconds=round(time.time() - t, 1))
    print(f"done in {time.time() - t:.0f} s: " + ", ".join(f"{k} {v:.1f} s" for k, v in S.timings.items()), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
