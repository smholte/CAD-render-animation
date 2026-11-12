"""Pictures of the demo cable-lay spread (tasks 0076, 0084) with the app's own importer, surroundings and Cycles.

    ~/venv/bin/python tools/demo_cable_lay_pictures.py <demo_cable_lay.step> <out folder> [--width 960] [--quality draft]
                      [--only overview,stern,tensioners,arch,cps,quadrant,quay] [--also demo_quay_loading.step]
                      [--prefix 0084]

Blender as a Python module (bpy), processor only. Imports the STEP(s) at Normal detail with the built-in sorting
rules, light look "Sun", surroundings "Open sea", then renders each view to <out>/<prefix>-<view>.png.
"""

from __future__ import annotations

import argparse
import importlib
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# camera (m) -> target (m), lens (mm): model coordinates (x to the bow, transom at 0, y to port, z up)
VIEWS = {
    "overview": ((-30.0, -52.0, 42.0), (36.0, 0.0, 3.0), 30.0),
    "stern": ((-13.0, -21.0, 13.0), (6.0, 0.0, 4.0), 28.0),
    "tensioners": ((17.0, -17.0, 11.0), (28.0, 0.0, 5.0), 28.0),
    "arch": ((40.0, -36.0, 24.0), (60.0, -4.0, 8.0), 30.0),
    "cps": ((26.0, 22.0, 13.0), (16.0, 7.0, 5.0), 26.0),
    "quadrant": ((34.0, 14.0, 11.0), (44.0, 0.0, 5.0), 28.0),
    "quay": ((-36.0, -62.0, 36.0), (8.0, -18.0, 4.0), 30.0),
}


def load_app():
    import bpy
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    pkg = importlib.import_module("fresing_render")
    if not hasattr(bpy.types.Scene, "fresing"):
        pkg.register()
    return pkg


def look_at(ob, loc, target):
    from mathutils import Vector
    ob.location = Vector(loc)
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--quality", default="draft")
    ap.add_argument("--only", default="")
    ap.add_argument("--also", default="", help="more STEP files to import into the same scene (comma separated)")
    ap.add_argument("--prefix", default="0084")
    a = ap.parse_args(argv)
    import bpy
    pkg = load_app()
    render = importlib.import_module(pkg.__name__ + ".blender.render")
    os.makedirs(a.out, exist_ok=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    s = scene.fresing
    s.out_folder = a.out
    t0 = time.time()
    res = bpy.ops.fresing.import_step(filepath=os.path.abspath(a.step), quality="normal")
    if res != {"FINISHED"}:
        raise SystemExit(f"import: {res} {s.last_message}")
    for extra in [x for x in a.also.split(",") if x]:
        res = bpy.ops.fresing.import_step(filepath=os.path.abspath(extra), quality="normal")
        if res != {"FINISHED"}:
            raise SystemExit(f"import {extra}: {res} {s.last_message}")
    print(f"imported in {time.time() - t0:.0f} s")
    bpy.ops.fresing.light_look(look="SUN")
    s.env_detail = "DETAILED"
    s.background = "SEA"
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = a.width, round(a.width * 9 / 16)
    s.use_gpu = False
    views = [v for v in VIEWS if not a.only or v in a.only.split(",")]
    for v in views:
        loc, target, lens = VIEWS[v]
        cam = bpy.data.cameras.new(f"Demo {v}")
        cam.lens = lens
        cam.clip_start, cam.clip_end = 0.1, 5000.0
        ob = bpy.data.objects.new(f"Demo {v}", cam)
        scene.collection.objects.link(ob)
        look_at(ob, loc, target)
        scene.camera = ob
        t1 = time.time()
        info = render.render_still(scene, s, a.quality, filepath=os.path.join(os.path.abspath(a.out), f"{a.prefix}-{v}.png"))
        print(f"{v}: {info['size']} in {time.time() - t1:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
