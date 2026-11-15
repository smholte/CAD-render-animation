"""One-click product video (task 0101): the animation it builds, on the sequence test model (a 12-part spindle unit
on a base plate) with and without joints / a subassembly."""

from __future__ import annotations

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils                       # noqa: E402
from mathutils import Vector            # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, product_video as pv  # noqa: E402

MODEL = os.path.join(os.path.dirname(__file__), "data", "test_sequence.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def sc(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    return sc


def unit(sc):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == "SPINDLE.UNIT")


def add_joint(sc, limits=(-0.5, 0.5)):
    j = joints.create(sc, "ROTATE", [unit(sc)], Vector((0.3, 0, 0)), Vector((0, 0, 1)), name="Turn unit")
    j.use_limits, j.rot_min, j.rot_max = True, limits[0], limits[1]
    return j


def kinds(a):
    return [b.kind for b in a.blocks]


def test_with_a_joint_and_a_subassembly(sc):
    add_joint(sc)
    info = pv.make(sc)
    a = info["animation"]
    assert a.get(pv.TAG) and a.fin_title_on and a.fin_end_on
    ks = kinds(a)
    assert ks[0] == "CAMERA" and a.blocks[0].camera_mode == "ORBIT"
    assert ks.count("JOINT") == 2 and ks.count("SEQUENCE") == 2
    assert [b.seq_mode for b in a.blocks if b.kind == "SEQUENCE"] == ["APART", "TOGETHER"]
    assert any(b.kind == "CAMERA" and b.camera_mode == "AIM" for b in a.blocks)
    assert info["left_out"] == [] or all("close-ups" in x for x in info["left_out"])
    assert 50 <= info["seconds"] <= 70                                  # the 60 s option, cards included
    res = animation.bake(sc, a)
    assert res["warnings"] == [], res["warnings"]
    ends = [animation.block_end(b) for b in a.blocks if b.enabled]
    assert max(ends) <= animation.length_seconds(a) + 1e-6


def test_build_twice_is_the_same(sc):
    add_joint(sc)
    a = pv.make(sc)["animation"]
    first = pv._sig(a)
    n_cams = len(pv.cameras.fr_cameras(sc))
    b = pv.make(sc)["animation"]
    assert b == a and pv._sig(b) == first
    assert len(sc.fresing.animations) == 1 and len(pv.cameras.fr_cameras(sc)) == n_cams


def test_without_joints_and_without_a_subassembly(sc):
    sc.fresing.pv_sub = "NONE"
    info = pv.make(sc)
    a = info["animation"]
    assert set(kinds(a)) == {"CAMERA"} and a.blocks[0].camera_mode == "ORBIT"
    assert any("motions" in x for x in info["left_out"]) and any("take-apart" in x for x in info["left_out"])
    res = animation.bake(sc, a)
    assert res["warnings"] == []


def test_the_owners_edits_are_noticed_and_other_animations_untouched(sc):
    add_joint(sc)
    other = sc.fresing.animations.add()
    other.name = "Mine"
    st = other.blocks.add()
    st.kind, st.duration = "POSE", 2.0
    mine = pv._sig(other)
    a = pv.make(sc)["animation"]
    assert not pv.changed(sc)
    a.blocks[0].duration += 1.0
    assert pv.changed(sc)
    pv.make(sc)
    assert not pv.changed(sc) and pv._sig(sc.fresing.animations["Mine"]) == mine


def test_operator_and_length_options(sc):
    add_joint(sc)
    sc.fresing.pv_seconds = "30"
    assert bpy.ops.fresing.product_video() == {"FINISHED"}
    a = pv.find_animation(sc)
    assert 25 <= animation.length_seconds(a) + 6 <= 38
    sc.fresing.pv_seconds = "90"
    sc.fresing.pv_title_on = False
    assert bpy.ops.fresing.product_video() == {"FINISHED"}
    assert not a.fin_title_on and a.fin_end_on


# ---------------------------------------------------------------------------
# task 0129: Back to CAD after the poses, close-ups the app picks
# ---------------------------------------------------------------------------

def _in_frame(sc, cam, points) -> float:
    """Share of the 8 box corners + the centre of ``points`` that the camera sees inside its picture."""
    import numpy as np
    from bpy_extras.object_utils import world_to_camera_view
    lo, hi = points.min(axis=0), points.max(axis=0)
    pts = [(lo + hi) / 2] + [np.array((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                             for z in (lo[2], hi[2])]
    inside = 0
    for p in pts:
        v = world_to_camera_view(sc, cam, Vector(tuple(p)))
        inside += 0.0 <= v.x <= 1.0 and 0.0 <= v.y <= 1.0 and v.z > 0.0
    return inside / len(pts)


def check_closeups(sc, info, want: int = 1):
    """The close-ups the app picked: cameras of their own, each framing a part a joint moves (or a decal)."""
    import numpy as np
    a = info["animation"]
    spots = info["spots"]
    assert len(spots) >= want, info["left_out"]
    steps = [b for b in a.blocks if b.kind == "CAMERA" and b.name.startswith("Close-up")]
    assert len(steps) == len(spots)
    for b, sp in zip(steps, spots):
        cam = b.camera
        assert cam is not None and cam.get(pv.CAM_TAG)
        bpy.context.view_layer.update()
        assert _in_frame(sc, cam, sp["points"]) == 1.0, sp["label"]          # the whole spot in the picture
        assert sp["seen"] > 0.0
        moving = [o for o in sp["objects"] if o.type == "MESH"]
        assert moving
        # the spot is not the whole model: it fills much more of the picture than the model would
        mn, mx = pv.logic.update_bounds(sc)
        size = float(np.linalg.norm(sp["points"].max(axis=0) - sp["points"].min(axis=0)))
        assert size < 0.95 * float(np.linalg.norm(np.array(mx) - np.array(mn))) or len(moving) > 3


def test_closeups_frame_a_moving_part_and_back_to_cad_after_the_poses(sc):
    j = add_joint(sc)
    joints.set_value(j, 0.3)
    from fresing_render.blender import states
    states.save_pose(sc, "Turned")
    joints.set_value(j, 0.0)
    bpy.context.view_layer.update()
    info = pv.make(sc)
    a = info["animation"]
    ks = kinds(a)
    assert ks.index("POSE") < ks.index("CAD") < ks.index("SEQUENCE")       # home again before the take-apart
    check_closeups(sc, info)
    names = {o.name for o in info["spots"][0]["objects"]}
    assert names & {o.name for o in pv.moving_parts(sc, j)}
    res = animation.bake(sc, a)
    assert res["warnings"] == [], res["warnings"]
    seq0 = next(b for b in a.blocks if b.kind == "SEQUENCE")
    sc.frame_set(animation.frame_of(a, seq0.start))
    assert joints.get_value(j) == pytest.approx(0.0, abs=1e-6)


def test_saved_cameras_still_win(sc):
    add_joint(sc)
    whole = pv.saved_cameras(sc)
    assert whole and all(pv.shows_whole_model(sc, c) for c in whole)    # the import's view: not a close-up
    cover = next(o for o in sc.objects if o.get(build.PROP_NAME) == "COVER")
    pts = pv._box([cover])
    cam = pv.cameras.add_camera(sc, "FRONT", name="My front", points=pts)
    bpy.context.view_layer.update()
    assert not pv.shows_whole_model(sc, cam)
    info = pv.make(sc)
    assert info["spots"] == []
    assert any(b.kind == "CAMERA" and b.camera is not None and b.camera.name == "My front"
               for b in info["animation"].blocks)


def test_closeups_on_the_crane(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    crane = os.path.join(os.path.dirname(__file__), "data", "test_crane_a.step")
    assert bpy.ops.fresing.import_step(filepath=crane, quality="draft") == {"FINISHED"}
    from fresing_render.blender import tour
    boom = tour._boom_joint(sc)
    boom.use_limits, boom.rot_min, boom.rot_max = True, 0.0, math.radians(40)
    info = pv.make(sc)
    check_closeups(sc, info)
    assert info["spots"][0]["label"] == boom.name
    spot = info["spots"][0]
    pin = next(o for o in sc.objects if o.get(build.PROP_NAME) == "BOOM.PIN")
    origin = boom.frame.matrix_world.translation
    lo, hi = spot["points"].min(axis=0), spot["points"].max(axis=0)
    assert all(lo[k] - 1e-6 <= origin[k] <= hi[k] + 1e-6 for k in range(3))        # framed at its hinge
    assert pin is not None
