"""The 3D views see the whole scene (task 0193)."""
import bpy
import pytest

from fresing_render.blender import surroundings


def _views():
    return [sp for sc in bpy.data.screens for a in sc.areas if a.type == "VIEW_3D" for sp in a.spaces
            if sp.type == "VIEW_3D"]


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=False)
    return bpy.context.scene


def _far_object(scene, dist):
    ob = bpy.data.objects.new("far turbine", None)
    scene.collection.objects.link(ob)
    ob.location = (dist, 0, 0)
    bpy.context.view_layer.update()
    return ob


def test_views_reach_far_objects(scene):
    assert _views()
    for sp in _views():
        sp.clip_end = 1000.0                      # an old project's view
    _far_object(scene, 6000.0)
    surroundings.fix_view_clip(scene)
    assert all(sp.clip_end >= 6000.0 for sp in _views())


def test_larger_user_value_kept(scene):
    for sp in _views():
        sp.clip_end = 90000.0
    _far_object(scene, 6000.0)
    surroundings.fix_view_clip(scene)
    assert all(sp.clip_end == pytest.approx(90000.0) for sp in _views())


def test_small_scene_keeps_small_start(scene):
    for sp in _views():
        sp.clip_start = 0.01
    surroundings.fix_view_clip(scene)
    assert all(sp.clip_start == pytest.approx(0.01) for sp in _views())


def test_big_scene_raises_start_and_cameras_count(scene):
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
    scene.collection.objects.link(cam)
    cam.data.clip_end = 20000.0
    surroundings.fix_view_clip(scene)
    for sp in _views():
        assert sp.clip_end >= 20000.0
        assert sp.clip_start >= 0.05
        assert sp.clip_end / sp.clip_start <= 5e5


def test_fix_clip_also_sets_views(scene):
    for sp in _views():
        sp.clip_end = 1000.0
    cam = bpy.data.objects.new("c", bpy.data.cameras.new("c"))
    scene.collection.objects.link(cam)
    _far_object(scene, 8000.0)
    surroundings.fix_clip(scene, 5000.0)
    assert all(sp.clip_end >= 8000.0 for sp in _views())
