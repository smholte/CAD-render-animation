"""Task 0231: the Lifting tour sets – the load, its CoG and the hook are in every picture, and the new check
('the CoG is not hidden') really fails when something stands between the camera and the CoG (it failed on the old set:
the crane's own carrier deck was in the way at all three stops)."""
import os

import pytest

from fresing_render.blender import tour

LIFTING_STOPS = ("lifting_place", "lifting_cog", "lifting_hook", "lifting_rig")
RIG_STOPS = ("lifting_spreader",)       # task 0232 (lifting_rig is in LIFTING_STOPS: its CoG is the skid's)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("tourlift") / "Tour é")
    out = tour.build_all(folder, "9.9.9", only=("lifting", "lifting_make", "crane_setup"))
    yield bpy, folder, out
    fresing_render.unregister()


def test_the_sets_build_on_the_yard(built):
    bpy, folder, out = built
    assert out["errors"] == {}
    for set_id in ("lifting", "lifting_make", "crane_setup"):
        tour.open_set(folder, "9.9.9", set_id)
        sc = bpy.context.scene
        assert sc.fresing.background == "QUAY", set_id
    tour.open_set(folder, "9.9.9", "lifting")
    mats = [o for o in bpy.context.scene.objects if o.name.startswith("Tour crane mat")]
    assert len(mats) == 4


@pytest.mark.parametrize("stop_id", LIFTING_STOPS + RIG_STOPS + ("lifting_make", "crane_setup"))
def test_each_lifting_stop_passes_its_check(built, stop_id):
    bpy, folder, _out = built
    st = tour.find(stop_id)
    tour.open_set(folder, "9.9.9", st.set)
    assert tour.apply(st, bpy.context.scene) == []
    assert st.check(bpy.context.scene)


def test_the_load_is_real_size_and_the_cog_is_off_the_middle(built):
    bpy, folder, _out = built
    from fresing_render.blender import lifting
    tour.open_set(folder, "9.9.9", "lifting")
    sc = bpy.context.scene
    ld = lifting.plan(sc).loads[0]
    assert lifting.load_mass(sc, ld)[0] == pytest.approx(6000.0)
    xs = [lifting.cog_world(ld)[1]]
    assert xs[0] > 0.1                          # the pump and the motor are on the +y side of the frame


@pytest.mark.parametrize("stop_id", LIFTING_STOPS)
def test_a_part_between_camera_and_cog_is_found(built, stop_id):
    bpy, folder, _out = built
    from mathutils import Vector

    from fresing_render.blender import lifting
    st = tour.find(stop_id)
    tour.open_set(folder, "9.9.9", "lifting")
    sc = bpy.context.scene
    tour.apply(st, sc)
    cog = Vector(tuple(lifting.cog_world(lifting.plan(sc).loads[0])))
    eye = sc.camera.matrix_world.translation
    mid = eye.lerp(cog, 0.6)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=mid)
    wall = bpy.context.object
    wall.scale = (1.5, 1.5, 1.5)
    bpy.context.view_layer.update()
    with pytest.raises(ValueError, match="between the camera and the CoG"):
        st.check(sc)
    bpy.data.objects.remove(wall)
