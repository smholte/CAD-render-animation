"""Task 0159: Build's pass through the frames (``flex.read_places``) lets Blender work out only what it reads.

Everything the read objects' places depend on (parents, constraint targets, the objects their drivers read) stays as it
is; everything else is hidden meanwhile – also where Build keyed it shown, its visibility keys muted for the pass.
The places are exactly those of a pass that works out the whole scene, and afterwards every object's visibility and
every key is as it was.
"""

from __future__ import annotations

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import flex  # noqa: E402

FRAMES = 40


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _empty(name, parent=None):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    return ob


def _mesh(name, parent=None, nodes=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.parent = parent
    if nodes:
        mod = ob.modifiers.new("drawn", "NODES")
        ng = bpy.data.node_groups.new(name + " tree", "GeometryNodeTree")
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
        a, b = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
        ng.links.new(a.outputs[0], b.inputs[0])
        mod.node_group = ng
    return ob


def _scene():
    """A keyed arm, a part on it whose turn a driver reads from a second keyed empty, a part held by a constraint on
    a third, a part driven by a property of a fourth – and things nothing read depends on: a keyed empty, a drawn
    object keyed hidden / shown."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    arm = _empty("arm")
    arm.rotation_euler = (0, 0, 0)
    arm.keyframe_insert("rotation_euler", index=2, frame=1)
    arm.rotation_euler = (0, 0, 1.2)
    arm.keyframe_insert("rotation_euler", index=2, frame=FRAMES)
    knob = _empty("knob")
    knob.location = (0, 0, 0)
    knob.keyframe_insert("location", index=0, frame=1)
    knob.location = (2.0, 0, 0)
    knob.keyframe_insert("location", index=0, frame=FRAMES)
    part = _mesh("part", arm)
    part.location = (1.0, 0.0, 0.0)
    fc = part.driver_add("rotation_euler", 1)
    fc.driver.type = "AVERAGE"
    v = fc.driver.variables.new()
    v.type = "TRANSFORMS"
    v.targets[0].id = knob
    v.targets[0].transform_type = "LOC_X"
    target = _empty("target")
    target.location = (0, 0, 0)
    target.keyframe_insert("location", index=2, frame=1)
    target.location = (0, 0, 3.0)
    target.keyframe_insert("location", index=2, frame=FRAMES)
    held = _mesh("held")
    c = held.constraints.new("COPY_LOCATION")
    c.target = target
    source = _empty("source")
    source["v"] = 0.0
    source.keyframe_insert('["v"]', frame=1)
    source["v"] = 5.0
    source.keyframe_insert('["v"]', frame=FRAMES)
    slid = _mesh("slid")
    fc = slid.driver_add("location", 0)
    fc.driver.type = "AVERAGE"
    v = fc.driver.variables.new()
    v.type = "SINGLE_PROP"
    v.targets[0].id = source
    v.targets[0].data_path = '["v"]'
    other = _empty("other")
    other.location = (0, 0, 0)
    other.keyframe_insert("location", index=1, frame=1)
    other.location = (0, 9, 0)
    other.keyframe_insert("location", index=1, frame=FRAMES)
    drawn = _mesh("drawn", other, nodes=True)
    drawn.hide_viewport = True
    drawn.keyframe_insert("hide_viewport", frame=1)
    drawn.hide_viewport = False
    drawn.keyframe_insert("hide_viewport", frame=FRAMES // 2)
    sc.frame_set(1)
    return sc, [part, held, slid]


def test_depends_on():
    sc, obs = _scene()
    got = flex.depends_on(obs)
    assert got == {"part", "arm", "knob", "held", "target", "slid", "source"}
    assert flex.depends_on([sc.objects["drawn"]]) == {"drawn", "other"}


def test_places_are_those_of_the_whole_scene_and_everything_is_put_back():
    sc, obs = _scene()
    drawn = sc.objects["drawn"]
    flex._STATE["closure"] = False
    try:
        whole = flex.read_places(sc, obs, 1, FRAMES)
    finally:
        flex._STATE["closure"] = True
    seen = []

    def spy(scene):                             # what Blender works out at each frame (the last: back at the start)
        seen.append({o.name for o in bpy.context.evaluated_depsgraph_get().objects})
    bpy.app.handlers.frame_change_post.append(spy)
    try:
        only = flex.read_places(sc, obs, 1, FRAMES)
    finally:
        bpy.app.handlers.frame_change_post.remove(spy)
    assert set(only) == {"part", "held", "slid"}
    for n in only:
        assert np.array_equal(only[n], whole[n]), n
    assert np.abs(only["part"][-1] - only["part"][0]).max() > 0.5         # (they moved: the pass read every frame)
    assert np.abs(only["slid"][-1, 0, 3] - 5.0) < 1e-6
    assert len(seen) == FRAMES + 1
    during = set().union(*seen[:-1])
    assert {"part", "held", "slid", "arm"} <= during and not during & {"drawn", "other"}, during
    # afterwards: the frame, the visibility and its keys as they were
    assert sc.frame_current == 1
    assert drawn.hide_viewport
    fcs = flex._hide_curves(drawn)
    assert len(fcs) == 1 and not fcs[0].mute
    sc.frame_set(FRAMES)
    assert not drawn.hide_viewport                                         # its key still shows it later
    assert not sc.objects["other"].hide_viewport
