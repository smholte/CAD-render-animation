"""Make the compatibility test project of the running app version (task 0352).

    ~/venv/bin/python tools/make_compat_project.py <out folder>            # Blender as a Python module
    blender -b --factory-startup --python tools/make_compat_project.py -- <out folder>

Writes ``<out>/format_<FORMAT>/``: one small project per test-tour set in ``COMPAT_SETS`` (``<set>.blend``, saved
compressed, no packed pictures, no bakes – a tour project opens unbuilt), ``summary.json`` (each project's stored
choices: ``blender/compat.summary``, the saved-data list of the task's step 1) and ``<set>.png`` (a tiny Cycles
picture on the processor). Together they use every function family that stores data (``core/compat.FAMILY_DATA``):
the sets are the test tour's own builds, kept working by the tour's tests.

Before the baseline nothing is kept: CI makes the project in the current version and opens it again
(``tests/test_compat_projects.py``). From the baseline on, a release that raises ``FORMAT`` runs this and commits the
folder into ``tests/data/compat/`` (CLAUDE.md section 7); the precheck fails a raised ``FORMAT`` without it.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# test-tour sets (fresing_render/blender/tour.py) whose functions cover every family that stores data:
# crane = looks, motion, scene, animation, video, queue, web, panel; copies = import (copies of a model); mill = milling;
# tools = cnc (the tool library); cylinder = machines; cables = offshore; house = house; lifting = lifting.
# tests/test_compat_projects.py works the coverage out again from core/functions.py and the tour's stops, and fails
# when a family that stores data is missing.
COMPAT_SETS = ("crane", "copies", "mill", "tools", "cylinder", "cables", "house", "lifting")


def covered_families(sets=COMPAT_SETS) -> set:
    """The function families shown by the tour stops of ``sets`` (core/functions.py: each function names its stops)."""
    from fresing_render.blender import tour
    from fresing_render.core import functions
    stop_set = {s.id: s.set for s in tour.STOPS}
    return {f.family for f in functions.FUNCTIONS.values() if any(stop_set.get(st) in sets for st in f.tour)}


def folder_of(out: str, fmt: int | None = None) -> str:
    from fresing_render.core import compat as core
    return os.path.join(out, f"format_{core.FORMAT if fmt is None else fmt}")


def make(out: str, sets=COMPAT_SETS, *, log=print) -> dict:
    """Build the projects into ``folder_of(out)``. Returns {"folder", "files": {set: path}, "errors": {set: text},
    "seconds"}."""
    import bpy

    from fresing_render import __version__
    from fresing_render.blender import compat, tour
    from fresing_render.core import compat as core
    dest = folder_of(out)
    os.makedirs(dest, exist_ok=True)
    t0 = time.time()
    work = tempfile.mkdtemp(prefix="fr_compat_")
    result = {"folder": dest, "files": {}, "errors": {}, "seconds": 0.0}
    summaries = {"format": core.FORMAT, "app": __version__, "projects": {}}
    try:
        built = tour.build_all(work, __version__, only=tuple(sets))
        result["errors"].update(built["errors"])
        for set_id in sets:
            src = built["files"].get(set_id)
            if not src:
                continue
            bpy.ops.wm.open_mainfile(filepath=src)
            path = os.path.join(dest, f"{set_id}.blend")
            bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=True, relative_remap=True)
            summaries["projects"][set_id] = compat.summary()
            pic = os.path.join(dest, f"{set_id}.png")
            if not compat.picture(bpy.context.scene, pic):
                log(f"compat project {set_id}: no camera, no picture")
            result["files"][set_id] = path
            log(f"compat project {set_id}: {os.path.getsize(path) // 1024} KB")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    with open(os.path.join(dest, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summaries, fh, indent=1, sort_keys=True)
    result["seconds"] = round(time.time() - t0, 1)
    return result


def _start_module() -> None:
    """Blender as a Python module: register the app as the tests do."""
    import addon_utils
    import bpy

    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if not argv:
        print(__doc__)
        return 2
    os.environ.setdefault("FRESING_WORKSPACE_START", "All functions")
    import bpy
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    if not hasattr(bpy.types.Scene, "fresing"):
        _start_module()
    res = make(os.path.abspath(argv[0]))
    print(json.dumps({k: v for k, v in res.items()}, indent=1))
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
