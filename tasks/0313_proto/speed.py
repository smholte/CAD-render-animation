"""Task 0313 (study, prototype – not app code), point D: is placing and previewing a move instant on big models?

    ~/venv/bin/python tasks/0313_proto/speed.py [test_crane_a | heavy] ...

``heavy`` writes the PC check's invented Heavy machine (``pccheck/heavy_scene.py``, ~3,000 placed / 600 unique parts)
into the scratch folder and imports it (draft quality). Measured per model, Blender as a Python module, no graphics
card (so no viewport frame rate – what a frame costs Blender besides drawing):

  points     the model's corner points (``cameras._points``: one box per visible part) – what every move is fitted to
  place      making a move round the model and sampling 5 s at 25 fps (moves.py)
  key        writing those 125 frames as keys on a camera (place, turn, lens, focus)
  frame      one frame step with only the camera keyed (``frame_set``: what playing the preview costs besides drawing)
  build      today's route: an animation with one "Fly a path" Camera step, Build (``animation.bake``)

Env: SPEED_OUT (default /tmp/speed0313).
"""
import json
import os
import sys
import time

import bpy  # noqa: I001
import addon_utils
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)
import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, cameras  # noqa: E402

import moves as M  # noqa: E402
from clips import key_camera  # noqa: E402

OUT = os.environ.get("SPEED_OUT", "/tmp/speed0313")
os.makedirs(OUT, exist_ok=True)


def ms(fn, reps=5):
    best = 1e9
    out = None
    for _ in range(reps):
        t = time.perf_counter()
        out = fn()
        best = min(best, (time.perf_counter() - t) * 1000)
    return best, out


def model_path(name):
    if name != "heavy":
        return os.path.join(ROOT, "fresing_render", "data", name + ".step")
    p = os.path.join(OUT, "heavy.step")
    if not os.path.exists(p):
        from fresing_render.pccheck import heavy_scene
        t = time.perf_counter()
        info = heavy_scene.build(p)
        print("[SPEED] heavy written", round(time.perf_counter() - t, 1), "s", info, flush=True)
    return p


def run(name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = os.path.join(OUT, "cache")
    r = {}
    t = time.perf_counter()
    assert bpy.ops.fresing.import_step(filepath=model_path(name), quality="draft") == {"FINISHED"}
    r["import_s"] = round(time.perf_counter() - t, 1)
    parts = [o for o in build.iter_parts(sc) if o.type == "MESH"]
    r["parts"] = len(parts)
    r["triangles"] = int(sum(len(o.data.loop_triangles) if o.data.loop_triangles else 0 for o in parts))
    r["points_ms"], pts = ms(lambda: cameras._points(sc))
    S = M.Subject(pts)
    r["size_m"] = [round(float(x), 2) for x in S.size]
    big = max(parts, key=lambda o: o.dimensions.length)
    place = {}
    for nm, fn in (("orbit", lambda: M.orbit(S, turn=360)), ("crane", lambda: M.crane(S)),
                   ("hero", lambda: M.hero(S)), ("top_down", lambda: M.top_down(S)),
                   ("fly_over", lambda: M.fly_over(S)), ("slide", lambda: M.slide(S))):
        place[nm] = round(ms(lambda: fn().sample(125))[0], 2)
    r["place_ms"] = place
    cd = bpy.data.cameras.new("Operator")
    cam = bpy.data.objects.new("Operator", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sampled = M.orbit(S, turn=360).sample(125)
    r["key_ms"] = round(min(key_camera(cam, sampled) for _ in range(3)), 2)
    sc.frame_start, sc.frame_end = 1, 125
    sc.frame_set(1)
    t = time.perf_counter()
    for f in range(2, 52):
        sc.frame_set(f)
    r["frame_ms"] = round((time.perf_counter() - t) * 1000 / 50, 3)
    # today's route: one Fly a path step, Build
    cam.animation_data_clear()
    cd.animation_data_clear()
    start = cameras.add_camera(sc, "ISO", 50.0, "Start")
    sc.camera = start
    a = sc.fresing.animations.add()
    a.name, a.fps = "Speed", "25"
    b = a.blocks.add()
    b.kind, b.camera_mode, b.start, b.duration, b.path_look = "CAMERA", "PATH", 0.0, 5.0, "MODEL"
    for p in M.orbit(S, turn=180).handles:
        b.path_points.add().co = tuple(p)
    t = time.perf_counter()
    res = animation.bake(sc, a)
    r["build_s"] = round(time.perf_counter() - t, 2)
    r["build_warnings"] = res["warnings"][:2]
    # a picked part (the biggest) as the subject: its corners only
    r["part_points_ms"], _ = ms(lambda: np.array([list(big.matrix_world @ __import__("mathutils").Vector(c))
                                                  for c in big.bound_box]))
    print("[SPEED]", name, json.dumps(r), flush=True)
    return r


def main():
    fresing_render.register()
    out = {}
    for name in sys.argv[1:] or ["test_crane_a", "test_mill", "heavy"]:
        out[name] = run(name)
    with open(os.path.join(OUT, "speed.json"), "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
