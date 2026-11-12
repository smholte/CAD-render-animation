"""The user guide's picture of tool marks (docs/img/milling_marks.jpg, task 0061): builds the test tour's set "marks"
alone, runs its stop's Go and check and renders the stop's shot with Cycles on the processor (bpy as a module).

    ~/venv/bin/python tools/guide_marks_picture.py <out dir> 1100x660 preview marks
    convert <out dir>/marks.png -quality 88 docs/img/milling_marks.jpg
"""
import os
import sys
import time

sys.path.insert(0, os.getcwd())
import bpy  # noqa: E402, I001
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import machining, render, tour  # noqa: E402

out_dir = sys.argv[1]
do_render = sys.argv[2] if len(sys.argv) > 2 else ""
bpy.ops.wm.read_factory_settings(use_empty=True)
addon_utils.enable("cycles", default_set=True)
fresing_render.register()
folder = os.path.join(out_dir, "tour")
out = tour.build_all(folder, "9.9.9", only=("marks",))
print("BUILD", out["seconds"], out["errors"], flush=True)
st = tour.find("marks")
tour.open_set(folder, "9.9.9", "marks")
sc = bpy.context.scene
t0 = time.time()
print("APPLY", tour.apply(st, sc), round(time.time() - t0, 1), "s", flush=True)
t0 = time.time()
print("CHECK", st.check(sc), round(time.time() - t0, 1), "s", flush=True)
print("FRAMES", sc.frame_start, sc.frame_end, "source:", machining.marks_source(sc))
print("STATUS", machining.status(sc))
if do_render:
    s = sc.fresing
    s.use_gpu = False
    s.out_format = "custom"
    w, h = (int(x) for x in do_render.split("x"))
    s.out_custom_w, s.out_custom_h = w, h
    q = sys.argv[3] if len(sys.argv) > 3 else "draft"
    name = sys.argv[4] if len(sys.argv) > 4 else "marks"
    t0 = time.time()
    info = render.render_still(sc, s, q, filepath=os.path.join(out_dir, name + ".png"))
    print("RENDER", info, round(time.time() - t0, 1), "s")
