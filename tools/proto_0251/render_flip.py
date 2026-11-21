"""Prototype 0251: render the baked Mantaflow scene from its own saved file (the cache is valid only there).

    blender -b /tmp/p251/flip96/flip_s.blend --python tools/proto_0251/render_flip.py -- <out dir> <frames>
"""
import json
import os
import sys
import time

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bl  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
out, n = argv[0], int(argv[1])
sc = bpy.context.scene
dom = bpy.data.objects["Liquid domain"]
d = dom.modifiers["Fluid"].domain_settings
print("baked:", d.has_cache_baked_data, d.has_cache_baked_mesh, list(d.domain_resolution))
bl.engine("CYCLES", 24)
ups = []
for f in range(min(n, 30)):
    a = time.perf_counter()
    sc.frame_set(f)
    bpy.context.evaluated_depsgraph_get()
    ups.append(time.perf_counter() - a)
times = bl.render_frames(range(n), out, lambda f: None)
res = dict(method="flip", engine="CYCLES", frames=n, render_s_per_frame=float(np.median(times)),
           update_ms=1000 * float(np.median(ups)), cells=list(d.domain_resolution))
res["mp4_bytes"] = bl.mp4(out, os.path.join(out, "s_flip_cycles.mp4"))
json.dump(res, open(os.path.join(out, "times.json"), "w"), indent=1)
print(json.dumps(res))
