"""0131 row 6 repeated: open the made demo, Build with the frames given shown (-1: the last), compare with what Make
demo saved; logs every new touch-down (paths_sea.anchor) with who asked for it.

    python row6.py "<folder>/9.9.9/Demo cable-lay vessel 9.9.9.blend" 1 1803 -1
    FRAME1=1 ...    the fix plan's step 1 tried (Build shows frame 1 first)
    NOANCHOR=1 ...  no new touch-down while a Build runs (what else is left)"""
import sys, os, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, addon_utils, fresing_render
import snap
path, frames = sys.argv[1], [int(f) for f in sys.argv[2:]]
import traceback
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import animation, paths, paths_sea
CALLS = []
real = paths_sea.anchor
def anchor(scene, item):
    before = (tuple(item.sea_start), float(item.sea_mark))
    out = real(scene, item)
    item = paths.find(scene, item.name) or item
    CALLS.append((item.name, scene.frame_current, before, (tuple(item.sea_start), float(item.sea_mark)),
                  [f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-9:-1]]))
    return out
paths_sea.anchor = anchor
import os
if os.environ.get("NOANCHOR"):          # the touch-down is kept while a Build runs (to see what else is left)
    _bake0, _changed0 = animation.bake, paths_sea.water_changed
    _busy = [0]
    def _bake_na(scene, anim):
        _busy[0] += 1
        try:
            return _bake0(scene, anim)
        finally:
            _busy[0] -= 1
    def _water_changed(scene):
        if _busy[0]:
            paths_sea.sync_bed(scene)
            return
        return _changed0(scene)
    animation.bake, paths_sea.water_changed = _bake_na, _water_changed
if os.environ.get("FRAME1"):            # the fix plan's step 1, tried: Build shows the first frame before anything else
    real_bake = animation.bake
    def bake(scene, anim):
        if scene.frame_current != 1 or scene.frame_subframe:
            scene.frame_set(1)
        return real_bake(scene, anim)
    animation.bake = bake
for f in frames:
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = sc.fresing
    made = snap.snapshot(sc)
    print("frame_end", sc.frame_end, "anim", s.anim_baked, flush=True)
    sc.frame_set(f)
    t = time.time()
    f = sc.frame_end if f < 0 else f
    sc.frame_set(f)
    del CALLS[:]
    out = animation.bake(sc, s.animations[s.anim_baked])
    for c in CALLS:
        print("   ANCHOR", c[0], "frame shown", c[1], "\n      before", c[2], "\n      after ", c[3], "\n      ", " < ".join(reversed(c[4])))
    print(f"== Build at frame {f}: {time.time() - t:.0f} s, warnings:", flush=True)
    for w in out["warnings"]:
        print("   W", w)
    snap.diff(made, snap.snapshot(sc))
    sys.stdout.flush()
