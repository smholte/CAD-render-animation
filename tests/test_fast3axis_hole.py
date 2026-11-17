"""Task 0186 (bug hunt 6, row 2): Fast 3-axis left a square hole straight through the block.

The case: the toolpath test model (tools/make_test_toolpath.py) with the toolpath of the tour set "toolpath" at the
toolpath's own default settings (Detail Draft, about 4,500 moves), milling Detail Normal, Fast 3-axis on. At frames
241 and 251 (step fitted to 10 s) one map tile's mesh was not a closed solid: on its border a wall had an extra
vertex at its top and one at its foot at the same place, ``HeightMap._ring_walk`` did not exist and the side was
stitched the wrong way between them; ``_MapSide._below`` (core/machining.py) made an empty solid of it and the whole
column of the block was dropped. Checked here: a ray straight down hits the block everywhere at every frame of the cut
(the exact cut has no such place), and every map tile's mesh (core/heightmap.py ``mesh``) is a closed solid.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, gcode, machining, toolpath  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_toolpath.step")
MM = 0.001


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    d = tmp_path_factory.mktemp("hole")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(d)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    toolpath.set_up_test_model(sc, detail="DRAFT")          # (the tour set's model, the toolpath's other defaults)
    bpy.ops.wm.save_as_mainfile(filepath=str(d / "part.blend"))
    sc = bpy.context.scene
    assert bpy.ops.fresing.toolpath_make() == {"FINISHED"}
    m = machining.settings(sc)
    assert m.fast_map and m.detail == "NORMAL"
    a, blk = toolpath.step(sc)
    blk.gcode_fit = 10.0
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    machining.update_if_needed(sc)
    yield sc
    fresing_render.unregister()


def test_no_column_of_the_block_is_dropped(scene):
    sc = scene
    tl = machining._timeline(sc)
    assert tl.map is not None and tl.stats.extra["map_moves"] > 1000
    hm = tl.map.hm
    wp = machining.settings(sc).workpiece
    lo = np.array(wp.bound_box[0]) / MM
    hi = np.array(wp.bound_box[6]) / MM
    xs = np.arange(lo[0] + 0.25, hi[0] - 0.2, 0.5)
    ys = np.arange(lo[1] + 0.25, hi[1] - 0.2, 0.5)
    bad_tiles, misses = [], []
    for f in range(sc.frame_start, sc.frame_end + 1):
        v, t = tl.mesh_at(float(f))[:2]
        bvh = BVHTree.FromPolygons([Vector(p) for p in np.asarray(v, float) / MM], np.asarray(t).tolist())
        miss = sum(bvh.ray_cast(Vector((x, y, hi[2] + 10.0)), Vector((0, 0, -1)))[0] is None for x in xs for y in ys)
        if miss:
            misses.append((f, miss))
        for J, I in np.argwhere(hm.cut_tiles()):
            _s, tv, tt, _m = hm.mesh(int(J), int(I))
            s = mf.Manifold(mf.Mesh(vert_properties=np.ascontiguousarray(tv, np.float32),
                                    tri_verts=np.ascontiguousarray(tt, np.uint32)))
            if s.status() != mf.Error.NoError or s.is_empty():
                bad_tiles.append((f, int(J), int(I), str(s.status())))
    assert not misses, f"(frame, rays from above that miss the block): {misses[:10]}"
    assert not bad_tiles, f"map tiles that are no closed solid: {bad_tiles[:10]}"
    # (the tiles took their own mesh: no plain fallback, no box)
    assert not tl.stats.extra.get("map_tiles_plain") and not tl.stats.extra.get("map_tiles_box"), tl.stats.extra
