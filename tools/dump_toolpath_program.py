"""The toolpath test model's milling inputs as a file, for ``tools/bench_milling_dense.py --only toolpath`` (task 0167).

    ~/venv/bin/python tools/dump_toolpath_program.py <out.npz>

Runs Blender as a Python module: imports tests/data/test_toolpath.step, sets the model up as the owner would
(``blender.toolpath.set_up_test_model``), makes the toolpath, builds its animation and writes what the milling
timeline is made from: the stock and finished part (triangles, metres, the block's frame), the bits and the paths.
"""

from __future__ import annotations

import os
import sys
import tempfile

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def main(out: str) -> None:
    import bpy  # noqa: F401  (first: it brings addon_utils)
    import addon_utils

    import fresing_render
    from fresing_render.blender import animation, gcode, machining, toolpath

    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    d = tempfile.mkdtemp()
    sc = bpy.context.scene
    sc.fresing.out_folder = d
    assert bpy.ops.fresing.import_step(filepath=os.path.join(ROOT, "tests", "data", "test_toolpath.step"),
                                       quality="normal") == {"FINISHED"}
    toolpath.set_up_test_model(sc)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(d, "part.blend"))
    sc = bpy.context.scene
    assert bpy.ops.fresing.toolpath_make() == {"FINISHED"}
    a, _b = toolpath.step(sc)
    animation.bake(sc, a)
    machining.update_if_needed(sc)
    tl = machining._timeline(sc)
    wp = tl.wp
    data = {}
    m = wp.stock.to_mesh()
    data["stock_v"], data["stock_t"] = np.array(m.vert_properties[:, :3]), np.array(m.tri_verts)
    if wp.first[0].keep is not None:
        k = wp.first[0].keep.to_mesh()
        data["keep_v"], data["keep_t"] = np.array(k.vert_properties[:, :3]), np.array(k.tri_verts)
    for i, c in enumerate(tl.cutters):
        t = c.tool
        data[f"tool{i}"] = np.array([t.radius, t.length, t.corner, t.angle])
        data[f"kind{i}"] = np.array(t.kind)
    for i, p in enumerate(tl.paths):
        data[f"path{i}_t"], data[f"path{i}_o"], data[f"path{i}_d"] = p.t, p.o, p.d
    data["detail"] = np.array(machining.settings(sc).detail)
    np.savez_compressed(out, **data)
    print(f"{out}: {len(tl.cutters)} bits, {len(tl.paths)} paths, {len(tl.segs)} moves")
    fresing_render.unregister()


if __name__ == "__main__":
    main(sys.argv[1])
