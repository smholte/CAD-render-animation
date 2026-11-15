"""Task 0141 – the smallest repeat case of bug hunt 0131 row 6 (for task 0138's failing test).

    ~/venv/bin/python repeat.py            (Blender as a Python module, about 25 s)

The moving-part test model (tests/data/test_moving.step, set up by ``paths.set_up_moving_model``) plus ONE thing:
a saved scene as the animation's start scene. Build with frame 1 shown, then with the last frame shown: the sea
cable's touch-down (``sea_start`` / ``sea_mark``) and its shapes must be the same. Variants show the two things
that make "the pose shown" depend on the frame: the seabed that moves with the clock, and let go."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import bpy  # noqa: I001  (bpy first: addon_utils comes with it)
import addon_utils
import numpy as np

import fresing_render
from fresing_render.blender import animation, paths, states

MODEL = os.path.join(ROOT, "tests", "data", "test_moving.step")


def load(folder):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    return sc


def shapes(sc, item):
    sh = paths._shapes(sc, item)
    frames, per, _first = paths._layout_of(sh)
    co = np.empty(len(sh.data.vertices) * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    return co.reshape(frames, per, 3).astype(float)


def case(folder, title, let_go=True, clock=True, start_scene=True, go_to_scene=False):
    sc = load(folder)
    paths.set_up_moving_model(sc, with_let_go=let_go)
    s = sc.fresing
    if not clock:                               # the seabed moves with the payout (nothing is paid out): it stands still
        s.weather.enabled = False
        s.weather.vessel_speed = 0.0
        paths.find(sc, paths.MOVING_CABLE).sea_speed = "LAY"
        from fresing_render.blender import paths_sea
        paths_sea.changed(sc, paths.find(sc, paths.MOVING_CABLE))
    a = s.animations[paths.MOVING_ANIMATION]
    states.save_shot(sc, "Start")
    if start_scene:
        a.start_shot = "Start"                  # <- the one thing added to the test model's own set-up
    out = animation.bake(sc, a)                 # frame 1 shown
    it = paths.find(sc, paths.MOVING_CABLE)
    ref = (np.array(it.sea_start), float(it.sea_mark), shapes(sc, it), list(out["warnings"]))
    sc.frame_set(sc.frame_end)                  # the owner scrubs to the end ...
    if go_to_scene:
        states.apply_shot(sc, "Start")          # ... clicks the saved scene (5 Scene & Render) ...
        sc.frame_set(sc.frame_end)
    out = animation.bake(sc, a)                 # ... and presses Build
    it = paths.find(sc, paths.MOVING_CABLE)
    now = shapes(sc, it)
    d_start = float(np.linalg.norm(np.array(it.sea_start) - ref[0]))
    d_shape = float(np.abs(now - ref[2]).max()) if now.shape == ref[2].shape else float("nan")
    new = [w for w in out["warnings"] if w not in ref[3]]
    same = d_start < 1e-6 and abs(float(it.sea_mark) - ref[1]) < 1e-6 and d_shape < 1e-5
    print(f"{'SAME     ' if same else 'DIFFERENT'} {title}: touch-down moved {d_start:.3f} m, mark {ref[1]:.3f} -> "
          f"{float(it.sea_mark):.3f}, shapes differ by {d_shape:.3f} m" + (f"; new warning: {new[0]}" if new else ""),
          flush=True)
    if not same:                                # does a Build with frame 1 shown put it right again?
        sc.frame_set(1)
        animation.bake(sc, a)
        it = paths.find(sc, paths.MOVING_CABLE)
        d = float(np.linalg.norm(np.array(it.sea_start) - ref[0]))
        print(f"             then Build with frame 1 shown: touch-down {d:.3f} m off -> "
              f"{'put right' if d < 1e-6 else 'STAYS WRONG'}", flush=True)
    return same


if __name__ == "__main__":
    import tempfile
    folder = tempfile.mkdtemp()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    case(folder, "A  as the test model is set up + a start scene (clock seabed + let go)")
    case(folder, "B  let go only (seabed stands still)", clock=False)
    case(folder, "C  clock seabed only (nothing let go)", let_go=False)
    case(folder, "D  neither", let_go=False, clock=False)
    case(folder, "E  no start scene (what bug hunt 0131 tried)", start_scene=False)
    case(folder, "F  no start scene, but 'Go to scene' clicked at the last frame before Build", start_scene=False,
         go_to_scene=True)
