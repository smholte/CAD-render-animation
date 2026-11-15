"""0141: what in 'the pose shown' moves the touch-down when Build's start scene sets it again at a late frame?
Open the made demo, show frame f, do what Build does up to the start scene, and read the new touch-down under
variants: as it is / vessel motion at rest / let-go ignored / both."""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, addon_utils, fresing_render
import numpy as np
path, frames = sys.argv[1], [int(f) for f in sys.argv[2:]]
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
from fresing_render.blender import animation, paths, paths_sea, states, vessel_motion, joints
for f in frames:
    for variant in ("as it is", "vessel at rest", "let go ignored", "both"):
        bpy.ops.wm.open_mainfile(filepath=path)
        sc = bpy.context.scene
        s = sc.fresing
        f = sc.frame_end if f < 0 else f
        anim = s.animations[s.anim_baked]
        was = {it.name: (tuple(it.sea_start), float(it.sea_mark)) for it in s.cables if it.b_kind == "SEA"}
        lg = {it.name: paths._let_goes(it) for it in s.cables if paths._let_goes(it)}
        sc.frame_set(f)
        real_lg = paths._let_goes
        if variant in ("let go ignored", "both"):
            paths._let_goes = lambda item: []
        try:
            animation.clear_keys(sc)
            ctx = vessel_motion.at_rest(sc) if variant in ("vessel at rest", "both") else None
            if ctx is not None:
                ctx.__enter__()
            try:
                states.apply_shot(sc, anim.start_shot)
            finally:
                if ctx is not None:
                    ctx.__exit__(None, None, None)
        finally:
            paths._let_goes = real_lg
        print(f"FRAME {f} [{variant}]", flush=True)
        for it in s.cables:
            if it.b_kind == "SEA":
                a, b = was[it.name], (tuple(it.sea_start), float(it.sea_mark))
                print(f"   {it.name}: start moved {np.linalg.norm(np.array(a[0]) - b[0]):.4f} m, mark {a[1]:.3f} -> {b[1]:.3f} ({b[1] - a[1]:+.3f} m)")
        if variant == "as it is":
            print("   let go:", lg, " vessel motion on:", bool(getattr(s, "vessel", None) and getattr(s.vessel, "enabled", False)),
                  " cable travel now:", round(joints.get_value(joints.find(sc, "Cable travel")), 3))
