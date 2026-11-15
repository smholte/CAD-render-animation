"""0141: for tour sets, Build each animation with frame 1 shown and with a later frame shown; compare.
usage: tourset.py <folder> [--patch NAME] set ...   (patches: see PATCHES)"""
import sys, os, time, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, addon_utils, fresing_render
import snap
args = sys.argv[1:]
folder = args.pop(0)
patch = ""
if args and args[0] == "--patch":
    args.pop(0); patch = args.pop(0)
sids = args
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import animation, tour, paths, paths_sea

CALLS = []
if patch == "log":                      # who sets the touch-down again during a Build?
    real = paths_sea.anchor
    def anchor(scene, item):
        before = (tuple(item.sea_start), float(item.sea_mark))
        out = real(scene, item)
        item = paths.find(scene, item.name) or item
        CALLS.append((item.name, scene.frame_current, before, (tuple(item.sea_start), float(item.sea_mark)),
                      [f"{f.name}:{f.lineno}" for f in traceback.extract_stack()[-9:-1]]))
        return out
    paths_sea.anchor = anchor
elif patch == "frame1":                 # the fix plan's step 1, tried
    real_bake = animation.bake
    def bake(scene, anim):
        if scene.frame_current != 1 or scene.frame_subframe:
            scene.frame_set(1)
        return real_bake(scene, anim)
    animation.bake = bake
elif patch == "noanchor":               # the candidate fix, crudely: no new touch-down while a Build runs
    real_bake, real_changed = animation.bake, paths_sea.water_changed
    busy = [0]
    def bake(scene, anim):
        busy[0] += 1
        try:
            return real_bake(scene, anim)
        finally:
            busy[0] -= 1
    def water_changed(scene):
        if busy[0]:
            paths_sea.sync_bed(scene)
            return
        return real_changed(scene)
    animation.bake, paths_sea.water_changed = bake, water_changed

for sid in sids:
    path = tour.set_path(folder, "9.9.9", sid)
    if not os.path.isfile(path):
        out = tour.build_all(folder, "9.9.9", only=(sid,))
        if out["errors"]:
            print("SET", sid, "ERROR", out["errors"]); continue
    bpy.ops.wm.open_mainfile(filepath=path)
    names = [a.name for a in bpy.context.scene.fresing.animations]
    for an in names:
        ref, end = None, 0
        for where in ("first", "mid", "last"):
            bpy.ops.wm.open_mainfile(filepath=path)
            sc = bpy.context.scene
            s = sc.fresing
            a = s.animations[an]
            f = 1 if where == "first" else end if where == "last" else max(2, int(end * 0.8))
            if where != "first" and not s.anim_baked:
                animation.bake(sc, a)           # (a set saved without a built animation: built first, as the owner has it)
            sc.frame_set(f)
            del CALLS[:]
            t = time.time()
            out = animation.bake(sc, a)
            took = time.time() - t
            for c in CALLS:
                print("   ANCHOR", c[0], "frame shown", c[1], "\n      before", c[2], "\n      after ", c[3], "\n      ", " < ".join(reversed(c[4])))
            if where == "first":
                ref, end = (snap.snapshot(sc), list(out["warnings"])), sc.frame_end
                print(f"== {sid} / {an}: {end} frames, Build {took:.1f} s, warnings {len(out['warnings'])}", flush=True)
                continue
            print(f"== {sid} / {an}: Build with frame {f} of {end} shown", flush=True)
            rows = snap.diff(ref[0], snap.snapshot(sc), show=14)
            if out["warnings"] != ref[1]:
                print("   WARNINGS differ:", [w for w in out["warnings"] if w not in ref[1]][:4])
            print(f"RESULT {sid} / {an} @{where} {f}/{end}: {'SAME' if not rows and out['warnings'] == ref[1] else 'DIFFERENT'}", flush=True)
