"""Task 0145: the demo project "Cable-lay vessel" made ONCE and shared by every test file that checks it.

    python tests/demo_made.py <folder>          # make it there (GitHub: the job "Linux - make the demo project")

The demo's tests (``tests/test_demo_project*.py``, ``tests/test_demo_clash.py``) were one file of ~35 min on GitHub
(task 0134: one job near GitHub's 40-minute limit), and the clash check made the same project again. Now:

- The project is made once, in its scaled-down form (``demo.build_project(..., small=True)``, as before), by this
  script as a program of its own. Next to it: ``made.json`` (the build's result, the status lines it showed) and
  ``models/`` (a copy of the model files, for the Cancel test).
- On GitHub one job makes it and hands the folder to the demo test jobs as a run artifact; each job unpacks it at the
  same place (``$RUNNER_TEMP/demo-made``) and points ``FRESING_DEMO_MADE`` at it. Why an artifact between jobs, not
  GitHub's cache: the cache would have to be keyed on all the app's code, which nearly every task changes, so it would
  miss nearly always – and on a miss every job would make it again at the same time.
- Without ``FRESING_DEMO_MADE`` (a chat machine) the first demo test file of a pytest session makes it in the session's
  temp folder (a lock file: one maker) and the others reuse it.
- Each test file opens the saved project itself (``made`` fixture below, scope "module"), with the add-on registered
  as the old single file did: every file starts from exactly the saved project.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VERSION = "9.9.9"
ENV = "FRESING_DEMO_MADE"
INFO = "made.json"


def make(dest: str) -> dict:
    """Make the demo project in ``dest`` (Blender as a Python module, this process). Returns what ``made.json`` holds."""
    sys.path.insert(0, ROOT)
    import bpy  # noqa: I001 - bpy first: it makes addon_utils importable
    import addon_utils

    import fresing_render
    from fresing_render.blender import demo
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    os.makedirs(dest, exist_ok=True)
    folder = os.path.join(dest, "Demo é")
    seen = []
    t0 = time.time()
    out = demo.build_project(folder, VERSION, small=True,
                             progress=lambda st, text, done, total: seen.append((st, text)))
    models = os.path.join(dest, "models")
    os.makedirs(models, exist_ok=True)
    for f in os.listdir(demo.model_dir(folder, VERSION)):
        shutil.copy(os.path.join(demo.model_dir(folder, VERSION), f), models)
    info = {"folder": folder, "out": out, "seen": seen, "models": models, "make_seconds": round(time.time() - t0, 1)}
    with open(os.path.join(dest, INFO + ".part"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)
    os.replace(os.path.join(dest, INFO + ".part"), os.path.join(dest, INFO))
    fresing_render.unregister()
    return info


def read(dest: str) -> dict:
    """The made project in ``dest``: made.json + the joint sheet, checked to be there where it was made."""
    with open(os.path.join(dest, INFO), encoding="utf-8") as fh:
        info = json.load(fh)
    path = info["out"]["path"]
    if not os.path.isfile(path):
        raise RuntimeError(f"the made demo project is not at {path}: unpack it where it was made "
                           f"({ENV}={dest}; on GitHub $RUNNER_TEMP/demo-made)")
    with open(os.path.join(info["models"], "demo_joints.json"), encoding="utf-8") as fh:
        info["sheet"] = json.load(fh)
    info["seen"] = [tuple(x) for x in info["seen"]]
    return info


def ensure(base_temp: str) -> str:
    """The folder of the made project: ``FRESING_DEMO_MADE``, or made once per pytest session under ``base_temp``."""
    given = os.environ.get(ENV)
    if given:
        if not os.path.isfile(os.path.join(given, INFO)):
            raise RuntimeError(f"{ENV}={given} holds no made demo project ({INFO})")
        return given
    dest = os.path.join(base_temp, "demo-made")
    os.makedirs(dest, exist_ok=True)
    lock = os.path.join(dest, "making.lock")
    while not os.path.isfile(os.path.join(dest, INFO)):
        try:
            os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:                           # another file of this session makes it
            time.sleep(2.0)
            continue
        try:
            if not os.path.isfile(os.path.join(dest, INFO)):
                r = subprocess.run([sys.executable, os.path.abspath(__file__), dest], cwd=ROOT)
                if r.returncode != 0:
                    raise RuntimeError(f"making the demo project failed ({r.returncode}): see the output above")
        finally:
            os.remove(lock)
    return dest


def open_made(tmp_path_factory) -> dict:
    """Register the add-on, open the made project; the dict the tests read (folder, out, seen, models, sheet)."""
    import bpy  # noqa: I001
    import addon_utils

    import fresing_render
    info = read(ensure(str(tmp_path_factory.getbasetemp())))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    bpy.ops.wm.open_mainfile(filepath=info["out"]["path"])
    return info


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    """The made demo project, opened for one test file (the add-on registered, as the single file had it)."""
    import fresing_render
    info = open_made(tmp_path_factory)
    yield info
    fresing_render.unregister()


# ------------------------------------------------------------------- helpers the demo's test files share (moved here)

def _scene():
    import bpy
    return bpy.context.scene


def _keys(sc):
    """Every key the Build wrote (layered actions: the channel bag of each object's slot)."""
    from bpy_extras import anim_utils
    out = {}
    for ob in sc.objects:
        ad = ob.animation_data
        if ad is None or ad.action is None or ad.action_slot is None:
            continue
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        for fc in cb.fcurves if cb is not None else []:
            pts = np.array([tuple(k.co) for k in fc.keyframe_points])
            out[(ob.name, fc.data_path, fc.array_index)] = pts
    return out


def _t9(a) -> float:
    """Where shot 9 starts: the second end is shown (task 0126: the lay cable is hidden earlier, in shot 8b)."""
    return next(b.start for b in a.blocks if b.kind == "SHOW" and b.target_name == "CABLE END")


def _first_steps(a) -> dict:
    """The first Move step of each joint in shot 9 and later (the quadrant operation)."""
    t9 = _t9(a)
    out = {}
    for b in sorted((b for b in a.blocks if b.kind == "JOINT" and b.start >= t9 - 1e-6), key=lambda b: b.start):
        out.setdefault(b.joint, b)
    return out


def _cps_shot(sc, a) -> tuple:
    """(first, last frame) of shot 8b (task 0126): from its cut to the second end's Show step."""
    from fresing_render.blender import demo
    t0 = next(b.start for b in a.blocks if b.kind == "CAMERA" and b.camera_mode == "CUT" and b.camera is not None
              and b.camera.name == demo.CPS_RACK)
    return animation_frame(a, t0), animation_frame(a, _t9(a))


def animation_frame(a, t: float) -> int:
    from fresing_render.blender import animation
    return animation.frame_of(a, t)


def paths_riders_parts(asm) -> list:
    from fresing_render.blender import paths_riders
    return paths_riders.parts_from([asm])


def _solved(sc, item):
    """The cable solved over the built frames as Build solved it: (result, first frame)."""
    from fresing_render.blender import paths
    _w, slots, *_ = paths._inputs_of(item)
    rel, first = paths._stored_places(sc, item, slots)[:2]
    return paths._solve_item(sc, item, rel, first=first), first


def _dense(P, step=0.25):
    out = [P[:1]]
    for a_, b_ in zip(P[:-1], P[1:]):
        n = max(1, int(math.ceil(np.linalg.norm(b_ - a_) / step)))
        out.append(a_ + (b_ - a_) * (np.arange(1, n + 1) / n)[:, None])
    return np.concatenate(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    got = make(os.path.abspath(sys.argv[1]))
    print(f"demo project made in {got['make_seconds']:.0f} s: {got['out']['path']}")
    sys.exit(0)
