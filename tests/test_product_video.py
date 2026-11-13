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
