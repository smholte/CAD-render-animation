"""Task 0092: the clash check with parts that turn in place (rollers, sheaves, drums, a coil).

A part that turns about its own round axis fills the same room at every angle: the check holds it at its place and
lets it ride along with its carrier only (``Check._hold_still``), so it is not worked out again at every moment. A part
that turns but is not round (a flat cut, teeth) keeps the full check. Small scenes made here (no STEP file): a roller
beside a fixed frame, the same roller with a flat, a roller on a moving carriage, a sprocket with teeth. The parts
without Blender (the turn stretches, the roundness test) are in ``tests/test_clash_core.py``.
"""

import math

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, clash  # noqa: E402
from fresing_render.core import clash as core  # noqa: E402

MM = 1e-3
FRAMES = 40


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def sc():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.frame_start, s.frame_end = 1, FRAMES
    return s


# ---------------------------------------------------------------------------
# shapes (m): prisms along X from a cross-section in the YZ plane
# ---------------------------------------------------------------------------

def prism(section, x0, x1):
    """A closed prism along X: ``section`` a list of (y, z) round the origin (star-shaped about it), caps as fans."""
    n = len(section)
    v = [(x0, y, z) for y, z in section] + [(x1, y, z) for y, z in section] + [(x0, 0.0, 0.0), (x1, 0.0, 0.0)]
    t = []
    for i in range(n):
        j = (i + 1) % n
        t += [(i, j, n + j), (i, n + j, n + i), (2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return v, t


def roller(r=50 * MM, n=64, flat=None):
    """A round roller's cross-section; ``flat``: cut flat at that height (z) on top."""
    out = []
    for k in range(n):
        a = 2 * math.pi * k / n
        y, z = r * math.cos(a), r * math.sin(a)
        out.append((y, min(z, flat) if flat is not None else z))
    return out


def sprocket(teeth=12, r=50 * MM, depth=8 * MM, n=240):
    """Teeth (flat tops at ``r``, flat roots ``depth`` lower); a gap between two teeth is centred on top (+Z)."""
    out = []
    for k in range(n):
        a = 2 * math.pi * (k + 0.5) / n
        rr = r - depth if math.cos(teeth * (a - math.pi / 2)) > 0 else r
        out.append((rr * math.cos(a), rr * math.sin(a)))
    return out


def box(lo, hi):
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    v = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    return v, t


def part(scene, name, shape, parent=None):
    v, t = shape
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], t)
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    ob[build.PROP_KIND] = "part"
    ob[build.PROP_NAME] = name
    if parent is not None:
        ob.parent = parent
    return ob


def keys(ob, path, values, frames=(1, FRAMES)):
    """Linear keys of ``path`` (e.g. rotation_euler) at the first and last frame."""
    for f, val in zip(frames, values):
        setattr(ob, path, val)
        ob.keyframe_insert(path, frame=f)
    _linear(ob)


def _linear(ob):
    act = ob.animation_data.action
    curves = []
    if hasattr(act, "fcurves"):
        curves = list(act.fcurves)
    else:                                                        # layered actions (Blender 4.4+)
        for layer in act.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves += list(bag.fcurves)
    for fc in curves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def built(scene):
    scene.fresing.anim_baked = "Test"
    scene.frame_set(1)
    return scene


def run(scene, **kw):
    return clash.check(scene, store=False, **kw)


def never_held(monkeypatch):
    """The check as it was before task 0092: no part is held still."""
    monkeypatch.setattr(core, "SPIN_MIN", 1e9)


# ---------------------------------------------------------------------------
# the four cases
# ---------------------------------------------------------------------------

def test_a_round_roller_turning_beside_a_fixed_frame(sc, monkeypatch):
    """Two turns of a round roller (Ø100, 64 facets) 1 mm from a frame, its shaft in two bearing blocks (touching):
    0 rows, held still, so not one pair is worked out after the start."""
    rol = part(sc, "ROLLER", prism(roller(), -0.1, 0.1))
    shaft = part(sc, "SHAFT", prism(roller(10 * MM, 32), -0.16, 0.16), parent=rol)
    part(sc, "FRAME", box((-0.12, -0.1, -0.08), (0.12, 0.1, -0.051)))
    part(sc, "BEARING L", box((-0.16, -0.02, -0.05), (-0.12, 0.02, -0.0099)))
    part(sc, "BEARING R", box((0.12, -0.02, -0.05), (0.16, 0.02, -0.0099)))
    keys(rol, "rotation_euler", [(0, 0, 0), (4 * math.pi, 0, 0)])
    del shaft
    r = run(built(sc))
    assert not r.rows, [core.row_text(x) for x in r.rows]
    assert r.stats["held"] == 2                                 # the roller and its shaft
    assert r.stats["bodies"] == 1 and r.stats["narrow"] == 0 and r.stats["between"] == 0
    # before task 0092: every moment and many moments between frames (the box corners move fast)
    never_held(monkeypatch)
    old = run(sc)
    assert not old.rows and old.stats["held"] == 0
    assert old.stats["narrow"] > 20 and old.stats["between"] > 50


def test_the_same_roller_with_a_flat_is_checked_in_full(sc):
    """A flat 5 mm deep on top, a block 1 mm above the flat: a quarter turn swings the round part through the block
    (up to 4 mm deep). Not round: not held, the clash is found."""
    rol = part(sc, "ROLLER FLAT", prism(roller(flat=45 * MM), -0.1, 0.1))
    part(sc, "BLOCK", box((-0.05, -0.01, 0.046), (0.05, 0.01, 0.07)))
    keys(rol, "rotation_euler", [(0, 0, 0), (math.pi / 2, 0, 0)])
    r = run(built(sc))
    assert r.stats["held"] == 0
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert len(rows) == 1 and {rows[0].a, rows[0].b} == {"ROLLER FLAT", "BLOCK"}, [core.row_text(x) for x in r.rows]
    assert 3.0 * MM < rows[0].depth < 4.2 * MM


def test_a_roller_on_a_moving_carriage_rides_with_it(sc):
    """A carriage slides 0.5 m along Y while its roller turns 3 times; the roller's shaft touches the carriage's
    bearing blocks all the time. The roller is held on the carriage (one body with it, never compared with it); the
    roller still runs into a fixed beam over the carriage's path (found)."""
    car = part(sc, "CARRIAGE", box((-0.12, -0.08, -0.09), (0.12, 0.08, -0.06)))
    part(sc, "CAR BEARING L", box((-0.16, -0.02, -0.07), (-0.12, 0.02, -0.0099)), parent=car)
    part(sc, "CAR BEARING R", box((0.12, -0.02, -0.07), (0.16, 0.02, -0.0099)), parent=car)
    rol = part(sc, "CAR ROLLER", prism(roller(), -0.1, 0.1), parent=car)
    part(sc, "CAR SHAFT", prism(roller(10 * MM, 32), -0.16, 0.16), parent=rol)
    part(sc, "BEAM", box((-0.05, 0.36, 0.047), (0.05, 0.4, 0.1)))     # 3 mm into the roller's top
    keys(car, "location", [(0, 0, 0), (0, 0.5, 0)])
    keys(rol, "rotation_euler", [(0, 0, 0), (6 * math.pi, 0, 0)])
    r = run(built(sc))
    assert r.stats["held"] == 2
    assert r.stats["bodies"] == 2                               # the fixed parts; the carriage with all it carries
    rows = [x for x in r.rows if x.kind == "CLASH"]
    pairs = {frozenset((x.a, x.b)) for x in rows}
    assert pairs == {frozenset(("CAR ROLLER", "BEAM"))}, [core.row_text(x) for x in r.rows]
    assert abs(rows[0].depth - 3.0 * MM) < 0.3 * MM


def test_a_sprocket_with_teeth_is_checked_in_full(sc):
    """A 12-tooth sprocket turns 60° under a chain link lying in the gap between two teeth (clear of them at the
    start): its teeth go through the link. Not round: not held, found."""
    spr = part(sc, "SPROCKET", prism(sprocket(), -0.01, 0.01))
    part(sc, "CHAIN LINK", box((-0.02, -0.003, 0.0425), (0.02, 0.003, 0.049)))
    keys(spr, "rotation_euler", [(0, 0, 0), (math.pi / 3, 0, 0)])
    r = run(built(sc))
    assert r.stats["held"] == 0
    rows = [x for x in r.rows if x.kind == "CLASH"]
    assert len(rows) == 2, [core.row_text(x) for x in r.rows]                  # two teeth pass through it
    assert all({x.a, x.b} == {"SPROCKET", "CHAIN LINK"} and x.depth > 2 * MM for x in rows)


def test_a_round_roller_turning_off_its_round_centre_is_checked_in_full(sc):
    """A wheel whose turning axis is 2 mm off its round centre (0077's rail wheels) wobbles: not held."""
    whl = part(sc, "WHEEL", prism([(y + 2 * MM, z) for y, z in roller()], -0.02, 0.02))
    part(sc, "RAIL", box((-0.05, -0.1, -0.08), (0.05, 0.1, -0.0505)))
    keys(whl, "rotation_euler", [(0, 0, 0), (2 * math.pi, 0, 0)])
    r = run(built(sc))
    assert r.stats["held"] == 0
    assert any({x.a, x.b} == {"WHEEL", "RAIL"} for x in r.rows if x.kind == "CLASH")


# ---------------------------------------------------------------------------
# the distance bound that lets far pairs skip the narrow test (task 0092)
# ---------------------------------------------------------------------------

def _mesh(shape):
    v, t = shape
    return clash.Mesh(np.array(v, dtype=float), np.array(t))


def test_separation_is_a_lower_bound_and_sees_a_part_inside_another():
    ring = _mesh(prism(roller(r=1.0, n=128), -0.05, 0.05))           # a disc 2 m across, 10 cm thick
    pin = _mesh(box((-0.01, -0.01, -0.01), (0.01, 0.01, 0.01)))
    move = np.eye(4)
    for x, want in ((0.2, 0.04), (0.06, 0.0), (0.0, 0.0)):
        move[:3, 3] = (x, 0.0, 0.0)
        sep = clash.separation(ring, pin, move)
        assert sep <= max(0.0, x - 0.06) + 1e-9                        # never more than the true gap
        if want:
            assert sep >= want * 0.9
    # the pin wholly inside the disc: surfaces apart, but not apart
    move[:3, 3] = (0.0, 0.3, 0.0)
    assert clash.separation(ring, pin, move) == 0.0 and clash.narrow(ring, pin, move)[0] > 0.0


def _fence(half):
    """Four bars round the middle, ``half`` m out: one part whose box holds everything inside it."""
    v, t = [], []
    for lo, hi in (((-half, -half, -0.1), (half, -half + 0.05, 0.1)), ((-half, half - 0.05, -0.1), (half, half, 0.1)),
                   ((-half, -half, -0.1), (-half + 0.05, half, 0.1)), ((half - 0.05, -half, -0.1), (half, half, 0.1))):
        bv, bt = box(lo, hi)
        t += [(a + len(v), b + len(v), c + len(v)) for a, b, c in bt]
        v += bv
    return v, t


def test_far_pairs_need_no_moments_between_frames(sc, monkeypatch):
    """A fast-turning arm (2 turns in 40 frames) inside a fence well clear of it: the boxes meet, the surfaces are
    far apart: no extra moments, and (looking for a gap first, as for big parts) no narrow test. A fence the arm
    reaches is found."""
    monkeypatch.setattr(clash, "SEP_TRIS", 0)
    arm = part(sc, "ARM", box((0.0, -0.02, -0.02), (0.6, 0.02, 0.02)))
    fence = part(sc, "FENCE", _fence(1.0))
    keys(arm, "rotation_euler", [(0, 0, math.pi / 4), (0, 0, 4.25 * math.pi)])     # starts along the diagonal
    r = run(built(sc))
    assert not r.rows and r.stats["between"] == 0 and r.stats["narrow"] == 0 and r.stats["apart"] > 0
    fence.data = bpy.data.meshes.new("FENCE small")
    v, t = _fence(0.55)                                                # the arm's tip reaches 0.6
    fence.data.from_pydata(v, [], t)
    r = run(built(sc))
    assert any({x.a, x.b} == {"ARM", "FENCE"} for x in r.rows)
    assert r.stats["between"] > 0


# ---------------------------------------------------------------------------
# a turning part that is not round, and a part resting against it (task 0092)
# ---------------------------------------------------------------------------

def _sheave():
    """A sheave turning about Z: a rim ring (r 0.30 … 0.40 m, 60 mm wide) on four spokes – not round."""
    n = 96
    v, t = [], []
    for r in (0.3, 0.4):
        for z in (-0.03, 0.03):
            v += [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n), z) for i in range(n)]

    def ix(k, i):
        return k * n + i % n
    for i in range(n):
        for k0, k1 in ((0, 1), (1, 3), (3, 2), (2, 0)):
            t += [(ix(k0, i), ix(k0, i + 1), ix(k1, i + 1)), (ix(k0, i), ix(k1, i + 1), ix(k1, i))]
    for k in range(4):
        a = k * math.pi / 2
        bv, bt = box((0.05, -0.02, -0.02), (0.31, 0.02, 0.02))
        rot = [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z) for x, y, z in bv]
        t += [(i + len(v), j + len(v), l + len(v)) for i, j, l in bt]
        v += rot
    return v, t


def test_a_spoked_sheave_and_its_rope_are_checked_once_per_turn(sc):
    """The sheave turns twice; a rope rests in its groove (0.2 mm into the rim) and a pin stands beside the spokes.
    Not round: the sheave keeps turning. The rope stays out of the room the spokes sweep: checked at the start of the
    turn only, no row. The spokes run through the pin: found."""
    shv = part(sc, "SHEAVE", _sheave())
    part(sc, "ROPE", box((0.3998, -0.3, -0.01), (0.43, 0.3, 0.01)))
    part(sc, "PIN", box((-0.02, 0.15, 0.015), (0.02, 0.19, 0.05)))      # 5 mm into the spokes' path (z 0.02)
    keys(shv, "rotation_euler", [(0, 0, 0.3), (0, 0, 0.3 + 4 * math.pi)])
    r = run(built(sc))
    assert r.stats["held"] == 0 and r.stats["still_pairs"] == 1
    pairs = {frozenset((x.a, x.b)) for x in r.rows if x.kind == "CLASH"}
    assert pairs == {frozenset(("SHEAVE", "PIN"))}, [core.row_text(x) for x in r.rows]


def test_a_gap_in_a_big_mesh_does_not_make_a_far_point_inside(monkeypatch):
    """A closed box plus a stray open sheet (a face left over where a CAD mesh has a gap): from a point 1 m from any
    face, two of the three usual rays cross the sheet once (odd: "inside"). More rays disagree: outside (task 0092: a
    gearbox's corner read 0.58 m inside a thin rim fence)."""
    bv, bt = box((2.0, 2.0, 2.0), (3.0, 3.0, 3.0))
    sheet_v = [(-2.0, 1.0, -2.0), (2.0, 1.0, -2.0), (2.0, 1.0, 2.0), (-2.0, 1.0, 2.0)]
    v = list(bv) + sheet_v
    t = list(bt) + [(8, 9, 10), (8, 10, 11)]
    m = _mesh((v, t))
    p = (np.zeros(3) - m.c).tolist()                                   # (the rays work round the mesh's centre)
    assert not m._inside_by_rays(p, dist=1.0)
    assert m._inside_by_rays(p, dist=0.001 * MM)                       # near a face: the three rays decide
    monkeypatch.setattr(clash, "RAY_CONFIRM", math.inf)             # only the three rays (before task 0092)
    assert m._inside_by_rays(p, dist=1.0)
