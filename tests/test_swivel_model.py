"""Task 0172: the swivel test model (tools/make_test_swivel.py -> tests/data/test_swivel.step, copy in the extension)
and its set-up (``paths_swivel.set_up_test_model``): a deck davit slews ±45° while its wire runs from a fixed fairlead
over a sheave on a swivel head and straight down the swivel's axis into a hook block.

The maker checks itself and its numbers; the importer reads the names, colours and tree. In Blender (as a Python
module, draft detail): the set-up reads the wire, the animation "Davit slews" is built, and at EVERY frame the wire
comes into the sheave in its plane (within 1°), the swivel stands where the maker's numbers say, the wire's ends sit
on the fairlead and in the hook block and the cable has a path and no problem; the swivel turns 45° over the
animation; the clash check finds nothing; 'Clear keys' lets the swivel follow live again.
"""
import math
import os
import sys

import numpy as np
import pytest

pytest.importorskip("OCP")
bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_swivel as maker  # noqa: E402
import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, clash, joints, paths, paths_swivel  # noqa: E402
from fresing_render.core import clash as core_clash  # noqa: E402
from fresing_render.importer import step_reader  # noqa: E402

STEP = os.path.join(HERE, "data", "test_swivel.step")
N = maker.NUMBERS
TOL_DEG = 1.0                   # the wire comes into the sheave this near its plane
MM = 0.001


# ---------------------------------------------------------------------------
# the maker and the file
# ---------------------------------------------------------------------------

def test_the_shipped_copy_is_the_test_data():
    with open(os.path.join(ROOT, "fresing_render", "data", "test_swivel.step"), "rb") as a, open(STEP, "rb") as b:
        assert a.read() == b.read(), "copy tests/data/test_swivel.step to fresing_render/data/"
    assert os.path.getsize(STEP) < 400 * 1024


def test_the_maker_checks_itself():
    root = maker.model()
    maker.check(root, say=lambda *_: None)
    assert maker.count_parts(root) == len(maker.PARTS) == 9


def test_the_numbers():
    # the fairlead is as far from the slew axis as the tip: the swivel turns half the slew the other way
    assert math.hypot(*maker.FAIRLEAD_AT) == pytest.approx(math.hypot(*maker.TIP))
    for slew in (-45.0, -20.0, 0.0, 10.0, 45.0):
        assert maker.swivel_angle(slew) == pytest.approx(-slew / 2.0, abs=1e-9)
    assert N["swivel_drawn"] == pytest.approx(-135.0)
    c = np.array(N["sheave_centre"])
    assert math.hypot(c[0] - maker.TIP[0], c[1] - maker.TIP[1]) == pytest.approx(maker.SHEAVE_R)
    # the wire: a straight from the fairlead, round the sheave, straight down the swivel axis; no kinks
    r = maker.wire_route()
    assert len(r.segments) == 3 and r.segments[1].kind == "arc"
    u_f = math.hypot(maker.FAIRLEAD_AT[0] - maker.TIP[0], maker.FAIRLEAD_AT[1] - maker.TIP[1])
    assert np.allclose(r.start, (u_f, maker.FAIRLEAD_TOP)) and np.allclose(r.end, (0.0, maker.WIRE_END))
    assert np.allclose(r.segments[1].end, (0.0, maker.SHEAVE_Z)) and np.allclose(r.segments[2].start_tangent, (0, -1))
    assert r.length == pytest.approx(sum(s.length for s in r.segments))
    # the straight run gets longer as the davit slews towards +: the winch keeps the wire tight
    assert maker.free_run(-45.0) < maker.free_run(0.0) - 1000.0 < maker.free_run(45.0) - 2000.0


@pytest.fixture(scope="module")
def info(tmp_path_factory):
    return step_reader.read_step(STEP, str(tmp_path_factory.mktemp("swivel_info")), "draft")


def test_the_importer_reads_the_names_colours_and_tree(info):
    nodes = info["nodes"]
    parts = [n for n in nodes if n["kind"] == "part"]
    assert sorted(n["name"] for n in parts) == sorted(maker.PARTS)
    assert sorted(n["name"] for n in nodes if n["kind"] == "assembly") == sorted(maker.ASSEMBLIES)
    for n in parts:
        assert n["color"] is not None, (n["name"], "has no colour")
        assert np.allclose(n["color"], maker.COLOURS[n["name"]], atol=2e-3), n["name"]
    head = {n["name"] for n in parts if nodes[n["parent"]]["name"] == "SWIVEL HEAD.ASM"}
    assert head == {"SWIVEL HEAD", "SHEAVE PIN", "SHEAVE"}
    davit = {n["name"] for n in parts if nodes[n["parent"]]["name"] == "DAVIT.ASM"}
    assert davit == {"DAVIT", "HOOK BLOCK"}


# ---------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def world(sc, p_mm) -> np.ndarray:
    """A point of the maker (mm, model coordinates) in the scene (m)."""
    m = np.array((build.model_root_of(named(sc, "DAVIT.ASM")) or named(sc, "DAVIT.ASM")).matrix_world)
    return m[:3, :3] @ (np.asarray(p_mm, dtype=float) * MM) + m[:3, 3]


@pytest.fixture(scope="module")
def scene(addon, tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("swivel"))
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    made = paths_swivel.set_up_test_model(sc)
    return sc, made


def wire(sc):
    return paths.find(sc, paths_swivel.TEST_CABLE)


def tilt(sc) -> float:
    """Degrees between the wire's run from the fairlead (the drawn centreline's first piece: a straight run is one
    piece) and the sheave's plane."""
    it = wire(sc)
    pts, s = paths.shape_now(sc, it), paths.lengths_now(sc, it)
    assert s[1] - s[0] > 1.0                     # (the free run from the fairlead)
    run = pts[1] - pts[0]
    run /= np.linalg.norm(run)
    axis = np.asarray(paths.wheels_now(sc, it)[0].axis, dtype=float)
    return math.degrees(math.asin(min(1.0, abs(float(run @ axis)))))


def test_the_set_up(scene):
    sc, made = scene
    assert made["cable"] == paths_swivel.TEST_CABLE and made["swivel"] == paths_swivel.TEST_SWIVEL
    assert made["animation"] == paths_swivel.TEST_ANIMATION and made["contacts"] == ["SHEAVE"]
    assert not any("cannot" in n for n in made["notes"]), made["notes"]
    it = wire(sc)
    assert it.problem == "" and it.keep_tight and it.look == "ROPE"
    assert it.a_kind == "FIXED" and it.a_part == named(sc, "FAIRLEAD")
    assert it.b_kind == "FIXED" and it.b_part == named(sc, "HOOK BLOCK")
    c = it.contacts[0]
    assert c.kind == "SHEAVE" and c.swivel == paths_swivel.TEST_SWIVEL and c.joint
    assert it.diameter == pytest.approx(N["wire_diameter"] * MM, abs=0.2 * MM)
    w = paths.wheels_now(sc, it)[0]
    assert np.allclose(w.centre, world(sc, N["sheave_centre"]), atol=2 * MM)
    assert w.radius == pytest.approx(maker.SHEAVE_R * MM, abs=1 * MM)
    # the joints: the slew about the Z axis, the swivel about the vertical through the tip, riding on the slew
    sw, sl = joints.find(sc, made["swivel"]), joints.find(sc, paths_swivel.TEST_SLEW)
    for j, (p, d) in ((sl, N["slew_axis"]), (sw, N["swivel_axis"])):
        f = np.array(j.frame.matrix_world)
        assert abs(float(f[:3, 2] @ np.array(d)) / np.linalg.norm(f[:3, 2])) == pytest.approx(1.0, abs=1e-6)
        off = f[:3, 3] - world(sc, p)
        assert math.hypot(off[0], off[1]) < 1 * MM, j.name
    assert sw.frame.parent is not None and paths_swivel._under(sw.frame, sl.motion)
    assert paths_swivel._under(c.carrier, sw.motion)


@pytest.fixture(scope="module")
def built(scene):
    sc, made = scene
    r = animation.bake(sc, sc.fresing.animations[made["animation"]])
    return sc, made, r


def test_build_turns_the_swivel_to_its_wire_at_every_frame(built):
    sc, made, r = built
    assert r["warnings"] == [], r["warnings"]
    sw, sl = joints.find(sc, made["swivel"]), joints.find(sc, paths_swivel.TEST_SLEW)
    frames = sc.frame_end - sc.frame_start + 1
    assert frames == 189                                            # 7.5 s at 25 fps: frames 1 … 189
    assert sw.motion[paths_swivel.TAG] == paths_swivel.TEST_CABLE
    fcs = [fc for fc in paths._fcurves(sw.motion) if fc.data_path == joints.COUPLING_PATH]
    assert len(fcs) == 1 and len(fcs[0].keyframe_points) == frames
    start = world(sc, N["wire_start"])
    worst, off, ends, turned = 0.0, 0.0, 0.0, []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        it = wire(sc)
        assert it.problem == "", (f, it.problem)
        pts = paths.shape_now(sc, it)
        assert len(pts) > 2 and np.isfinite(pts).all(), f
        worst = max(worst, tilt(sc))
        slew = math.degrees(joints.get_value(sl))
        v = math.degrees(joints.get_value(sw))
        turned.append(v)
        off = max(off, abs(v - maker.swivel_angle(slew)))
        tip = maker.tip_at(slew)
        end = world(sc, (tip[0], tip[1], maker.WIRE_END))
        ends = max(ends, float(np.linalg.norm(pts[0] - start)), float(np.linalg.norm(pts[-1] - end)))
    assert worst < TOL_DEG, worst
    assert off < 0.05, off                                          # degrees off the maker's numbers
    assert ends < 2 * MM, ends                                      # the wire's ends on the fairlead / in the block
    assert max(turned) - min(turned) > 30.0, (min(turned), max(turned))      # 45° (-22.5° … +22.5°)
    assert max(turned) > 20.0 and min(turned) < -20.0


def test_the_slewing_davit_does_not_clash(built):
    sc, _made, _r = built
    rows = clash.check(sc, store=False).rows
    assert not rows, [core_clash.row_text(r) for r in rows[:5]]


def test_clear_keys_lets_the_swivel_follow_live(built):
    sc, made, _r = built
    animation.clear_keys(sc)
    sw = joints.find(sc, made["swivel"])
    assert paths_swivel.TAG not in sw.motion and not paths._fcurves(sw.motion)
    for slew in (30.0, -40.0):
        joints.set_value(joints.find(sc, paths_swivel.TEST_SLEW), math.radians(slew), use_limits=False)
        for _ in range(2):
            update()
            paths.refresh(sc)               # (the handler does this after a change in the app)
        update()
        assert math.degrees(joints.get_value(joints.find(sc, made["swivel"]))) == pytest.approx(
            maker.swivel_angle(slew), abs=0.05), slew
        assert tilt(sc) < TOL_DEG, slew
