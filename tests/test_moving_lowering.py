"""Task 0229, stand-in (study 0226): a block lowered on a wire past a part it must clear – the clash check finds no
clash when it clears it by a few cm, and finds it when the part stands 5 cm into its way.

Until now only the private demo vessel proved a lowering past equipment clash-free. Here: the moving-part test model
(tests/data/test_moving.step, ``paths.set_up_moving_model``, its let-go left out): the trolley travels aft, the
hanger tilts 30° and the block is lowered 9 m on the lift wire (its winch keeping it tight) over the stern, then
lifted 4 m again. The part to clear is made in the test: a guide slot of two walls, one either side of the block's
way below the gantry, placed from the block's own swept box (its sheave and clamp included) with ``GAP`` clearance on
each side. It is a part like an imported one (``fr_kind`` "part", still), so the check compares it with everything.

- Build + clash check: 0 rows;
- the slot moved 5 cm sideways (one wall 2 cm into the block's way): the check finds the block (or its sheave)
  against the slot.
"""

import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(HERE, "data", "test_moving.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, flex, paths  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

GAP = 0.03                      # m: the slot's clearance either side of the block's way
SHIFT = 0.05                    # m: the control moves the slot this far sideways
WALL = 0.10                     # m: each wall's thickness
LOWERED = ("BLOCK", "SHEAVE", "CLAMP")
SLOT = "GUIDE SLOT"


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _boxes(lohi):
    """One mesh of several boxes: (corners, triangles) for [(lo, hi), …]."""
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    vs, ts = [], []
    for lo, hi in lohi:
        k = len(vs)
        vs += [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        ts += [(a + k, b + k, c + k) for a, b, c in t]
    return np.array(vs, np.float32), np.array(ts, np.int32)


def _make_slot(sc, lohi):
    """The part to clear, made as an imported part would be: a mesh object tagged as a part, at the world origin."""
    v, t = _boxes(lohi)
    n = v - v.mean(axis=0)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    me = build._new_mesh(SLOT, v, n.astype(np.float32), t)
    ob = bpy.data.objects.new(SLOT, me)
    sc.collection.objects.link(ob)
    ob[build.PROP_KIND] = "part"
    ob[build.PROP_NAME] = SLOT
    ob.matrix_world = Matrix.Identity(4)
    return ob


def _swept(sc, frames):
    """World box (lo, hi) of the lowered parts over the frames, and the lowest frame's box."""
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    obs = [named(sc, n) for n in LOWERED]
    for f in frames:
        sc.frame_set(f)
        for ob in obs:
            m = np.array(ob.matrix_world)
            c = np.array(ob.bound_box, dtype=float) @ m[:3, :3].T + m[:3, 3]
            lo, hi = np.minimum(lo, c.min(0)), np.maximum(hi, c.max(0))
    return lo, hi


@pytest.fixture(scope="module")
def lowered(tmp_path_factory):
    t0 = time.perf_counter()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("lowering"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    made = paths.set_up_moving_model(sc, with_let_go=False)
    r = animation.bake(sc, sc.fresing.animations[made["animation"]])
    assert r["warnings"] == [], r["warnings"]
    for name in (made["cable"], made["wire"]):
        assert paths.status(sc, paths.find(sc, name))[1] == "OK", name
    # the block's way: x and z of the whole lowering (frames after the tilt), y (across) of every frame
    lo, hi = _swept(sc, range(sc.frame_start, sc.frame_end + 1, 2))
    gantry = np.array(named(sc, "GANTRY").matrix_world)
    g = np.array(named(sc, "GANTRY").bound_box, dtype=float) @ gantry[:3, :3].T + gantry[:3, 3]
    horn = np.array(named(sc, "HORN").matrix_world)
    h = np.array(named(sc, "HORN").bound_box, dtype=float) @ horn[:3, :3].T + horn[:3, 3]
    # the slot's walls: beside the way, below the gantry, aft of the horn, down to below the lowest point
    x0, x1 = lo[0] - 0.5, min(h.min(0)[0] - 0.05, hi[0])
    z0, z1 = lo[2] - 0.5, g.min(0)[2] - 0.1
    assert x1 - x0 > 5.0 and z1 - z0 > 5.0, (x0, x1, z0, z1)          # (walls metres long beside the way)
    assert lo[2] < z1 - 4.0                                           # (the block goes down metres between them)
    walls = [((x0, hi[1] + GAP, z0), (x1, hi[1] + GAP + WALL, z1)),
             ((x0, lo[1] - GAP - WALL, z0), (x1, lo[1] - GAP, z1))]
    slot = _make_slot(sc, walls)
    return sc, slot, (lo, hi), time.perf_counter() - t0


def _rows_with_slot(rows):
    return [r for r in rows if SLOT in (r.a, r.b)]


def test_the_block_lowered_through_the_slot_clears_it(lowered):
    sc, slot, (lo, hi), _took = lowered
    slot.location = (0.0, 0.0, 0.0)
    bpy.context.view_layer.update()
    assert slot in clash.objects(sc)
    t0 = time.perf_counter()
    rows = clash.check(sc, store=False).rows
    assert not rows, [core.row_text(r) for r in rows[:5]]
    assert time.perf_counter() - t0 < 60.0


def test_the_slot_moved_5_cm_into_the_way_is_found(lowered):
    sc, slot, (lo, hi), _took = lowered
    slot.location = (0.0, -SHIFT, 0.0)                # the +y wall 2 cm into the block's way
    bpy.context.view_layer.update()
    try:
        rows = clash.check(sc, store=False).rows
    finally:
        slot.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
    hits = _rows_with_slot(rows)
    assert hits, [core.row_text(r) for r in rows[:5]]
    assert {(set((r.a, r.b)) - {SLOT}).pop() for r in hits} <= set(LOWERED), [core.row_text(r) for r in hits[:5]]
    assert all(r.kind == "CLASH" for r in hits)
    deepest = max(r.depth for r in hits)
    assert SHIFT - GAP - 0.005 < deepest < SHIFT - GAP + 0.01, deepest       # 2 cm into its way
    assert not [r for r in rows if SLOT not in (r.a, r.b)], [core.row_text(r) for r in rows[:5]]
