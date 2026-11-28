"""Task 0374 row C (0172's open point 3): two cables over one sheave, in Blender (as a Python module).

Model: tests/data/test_paths_a.step (tools/make_test_paths.py) set up by ``paths.set_up_test_model`` – the cable "Wire
rope" from the winch over SHEAVE 1 (one groove, 70 mm wide), SHEAVE 2, the V rollers and the chute. A second cable is
drawn over SHEAVE 1 (``paths.draw_cable``): it lies in the same groove. What must hold: the sheave keeps one joint and
turns with the first cable; the second cable's panel says so in plain words and says the two lie in one groove; taking
the first cable off hands the sheave to the second (it is not deleted with the first, and turns with the second)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, drawn, hover, joints, logic, paths  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_paths_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update():
    for _ in range(2):
        bpy.context.view_layer.update()


def cast(sc, origin, direction, want):
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert index >= 0 and ob.get(build.PROP_NAME) == want, ob.get(build.PROP_NAME) if ob else None
    return ob, index, loc, normal


@pytest.fixture()
def two(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_test_model(sc)
    rope = next(o for o in sc.objects if o.get(build.PROP_NAME) == "WIRE ROPE")
    logic.exclude([rope], True)                 # (the clicks go through the first cable, as a user's would not)
    update()
    ob, index, loc, normal = cast(sc, (2.5, 0.5, 3.0), (0, 0, -1), "BASE FRAME")
    start = drawn.spot(ob, index, loc, normal)
    s1, _i, hit, _n = cast(sc, (4.776, 0.0, 6.0), (0, 0, -1), "SHEAVE 1")
    logic.exclude([rope], False)
    update()
    item, _notes = paths.draw_cable(sc, start, [(s1, np.array(hit), False)], None, name="Second rope",
                                    diameter=0.020)
    update()
    return sc


def contact(item, part_name):
    return next(c for c in item.contacts if c.part is not None and c.part.get(build.PROP_NAME) == part_name)


def test_the_sheave_keeps_one_joint_and_turns_with_the_first_cable(two):
    sc = two
    first, second = paths.find(sc, "Wire rope"), paths.find(sc, "Second rope")
    a, b = contact(first, "SHEAVE 1"), contact(second, "SHEAVE 1")
    assert a.joint and a.joint == b.joint                   # one joint, not a second one stacked on it
    assert a.made_joint and not b.made_joint and not b.coupled
    j = joints.find(sc, a.joint)
    assert j.follows == first.joint
    # the second cable's panel says it in plain words – and that the two lie in one groove (a fault: red)
    assert b.note.startswith(paths.SHARED + " 'Wire rope'") and "ONE groove" in b.note, b.note
    assert not a.note.startswith(paths.SHARED)


def test_removing_the_first_cable_hands_the_sheave_to_the_second(two):
    sc = two
    first = paths.find(sc, "Wire rope")
    name = contact(first, "SHEAVE 1").joint
    paths.remove(sc, paths.index_of(sc, first))
    update()
    second = paths.find(sc, "Second rope")
    b = contact(second, "SHEAVE 1")
    j = joints.find(sc, name)
    assert j is not None and b.joint == name                # the sheave's joint stayed
    assert b.made_joint and b.coupled
    assert j.follows == second.joint                        # and turns with the second cable now
    assert j.motion.get(paths.TAG) == second.name
    # the first cable's own joints that nobody else uses went with it
    assert joints.find(sc, "SHEAVE 2 rotate") is None
    # taking the second off too takes the sheave's joint (now its own)
    paths.remove(sc, paths.index_of(sc, second))
    assert joints.find(sc, name) is None


def test_removing_the_second_cable_leaves_the_first_as_it_was(two):
    sc = two
    second = paths.find(sc, "Second rope")
    paths.remove(sc, paths.index_of(sc, second))
    first = paths.find(sc, "Wire rope")
    a = contact(first, "SHEAVE 1")
    j = joints.find(sc, a.joint)
    assert j is not None and j.follows == first.joint and a.made_joint
