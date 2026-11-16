"""Detailed props for scale and the person (task 0155).

Pure Python: the person's heights, every pose keeps its feet (or a kneeling knee) on the floor, every pose x outfit x
level builds, the prop list of older projects is unchanged. In Blender (bpy module): one mesh holds both levels, the
detail switch by camera distance and by the scene's setting, a person's settings rebuild it in place, and props of an
older project get the new look when it opens without moving or changing name or count.
"""

import math

import numpy as np
import pytest

from fresing_render.core import props_detail as P
from fresing_render.core import surroundings as S


def _pts(shapes):
    return np.array([p for sh in shapes for p in P._points(sh)])


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("height", P.HEIGHTS)
def test_person_has_its_height(height):
    top = _pts(P.person(height=height, helmet=False))[:, 2].max()
    assert abs(top - height) < 0.01
    with_helmet = _pts(P.person(height=height, helmet=True))[:, 2].max()
    assert 0.015 < with_helmet - top < 0.06, "the helmet sits on the head"


@pytest.mark.parametrize("pose", P.POSES_IDS)
def test_poses_keep_the_feet_on_the_floor(pose):
    lv = P.feet_levels(pose=pose)
    low = _pts(P.person(pose=pose))[:, 2].min()
    assert abs(low) < 1e-9, "the lowest point is on the floor"
    if pose == "KNEELING":
        assert lv["r_knee"] < 0.015, "the right knee rests on the floor"
        assert lv["l_sole"] < 0.01, "the front foot stands flat"
        assert lv["r_sole"] < 0.04, "the toes of the kneeling leg touch the floor"
    elif pose == "WALKING":
        assert min(lv["l_sole"], lv["r_sole"]) < 0.01 and max(lv["l_sole"], lv["r_sole"]) < 0.04
    else:
        assert lv["l_sole"] < 0.01 and lv["r_sole"] < 0.01, "both feet stand on the floor"


def test_kneeling_is_lower_and_pointing_reaches_forward():
    h = {pose: _pts(P.person(pose=pose, helmet=False))[:, 2].max() for pose in P.POSES_IDS}
    assert h["KNEELING"] < 0.8 * h["STANDING"]
    front = {pose: _pts(P.person(pose=pose))[:, 1].min() for pose in P.POSES_IDS}
    assert front["POINTING"] < front["STANDING"] - 0.4, "the arm points forward (-y, towards a front view)"
    assert front["PANEL"] < front["STANDING"] - 0.15


@pytest.mark.parametrize("outfit", P.OUTFITS)
@pytest.mark.parametrize("lod", P.LODS)
def test_every_pose_outfit_and_level_builds(outfit, lod):
    for pose in P.POSES_IDS:
        for gloves in (False, True):
            shapes = P.person(pose=pose, outfit=outfit, gloves=gloves, look=3, lod=lod)
            pts = _pts(shapes)
            assert np.isfinite(pts).all() and abs(pts[:, 2].min()) < 1e-9
            mats = {sh.mat for sh in shapes}
            assert any(m.startswith("skin_") for m in mats)
            assert ("glove_grey" in mats or "glove_orange" in mats) == gloves


def test_outfits_and_looks_differ():
    mats = {o: {sh.mat for sh in P.person(outfit=o)} for o in P.OUTFITS}
    assert "cloth_orange" in mats["OFFSHORE"] and "reflective" in mats["OFFSHORE"]
    assert "hivis_yellow" in mats["OFFICE"] and "cloth_shirt" in mats["OFFICE"]
    assert "cloth_navy" in mats["WORKSHOP"]
    skins = {next(sh.mat for sh in P.person(look=k) if sh.mat.startswith("skin_")) for k in range(4)}
    assert len(skins) == 4


def test_prop_list_of_older_projects_is_unchanged():
    """Projects store a prop's kind (fr_prop) and its object is named after the label: both must stay."""
    old = {"PERSON": "Person", "CONTAINER": "20 ft container", "PALLET": "Euro pallet", "BARRIER": "Safety barrier"}
    assert list(S.PROPS)[:4] == list(old)
    assert all(S.PROPS[k][0] == v for k, v in old.items())
    assert {"IBC", "GAS_RACK", "TOOL_TROLLEY"} <= set(S.PROPS)


@pytest.mark.parametrize("kind", list(S.PROPS))
def test_both_levels_have_the_same_size(kind):
    """Switching the level must not make the prop jump: the light version fills about the same box."""
    a = _pts(S.prop_shapes(kind, P.DETAILED))
    b = _pts(S.prop_shapes(kind, P.LIGHT))
    assert np.isfinite(a).all() and np.isfinite(b).all()
    size_a, size_b = a.max(0) - a.min(0), b.max(0) - b.min(0)
    assert abs(a[:, 2].min()) < 1e-6 and abs(b[:, 2].min()) < 1e-6, "both stand on the floor"
    assert np.all(np.abs(size_a - size_b) < np.maximum(0.15, 0.1 * size_a)), (size_a, size_b)


def test_rounded_box_and_sweep():
    lo = P.rbox("x", 1.0, 2.0, 0.5, 0.4, 0.2, 0.3, 0.02, 3)
    pts = _pts([lo])
    assert np.allclose(pts.min(0), (0.8, 1.9, 0.5), atol=1e-9) and np.allclose(pts.max(0), (1.2, 2.1, 0.8), atol=1e-9)
    path = P.rounded_path([(0, 0, 0), (1, 0, 0), (1, 1, 0)], 0.2, 4)
    assert len(path) == 2 + 5
    assert all(np.linalg.norm(np.asarray(p) - (1, 0, 0)) > 0.05 for p in path), "the corner is rounded"
    sw = P.sweep("x", path, 0.03, 8)
    assert len(sw.rings) == len(path) and len(sw.rings[0]) == 8


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.location = (0.0, -4.0, 1.5)
    return sc


def _level(ob):
    from fresing_render.blender import props_scale
    bpy.context.view_layer.update()
    return props_scale.visible_level(ob)


def test_one_mesh_holds_both_levels(scene):
    from fresing_render.blender import props_scale, surroundings
    for kind in S.PROPS:
        ob = surroundings.add_prop(scene, kind)
        att = ob.data.attributes.get(props_scale.LOD_ATTR)
        assert att is not None and att.domain == "FACE"
        vals = np.zeros(len(att.data), dtype=np.int32)
        att.data.foreach_get("value", vals)
        assert set(vals) == {1, 2}
        assert ob.modifiers.get(props_scale.MODIFIER) is not None
        assert ob[props_scale.VER_KEY] == props_scale.VERSION
        det, light = props_scale.triangles(kind, P.DETAILED), props_scale.triangles(kind, P.LIGHT)
        assert light < det / 2.5, f"{kind}: the light version is much lighter ({light} vs {det})"
        assert det < 12000, "props stay light enough for many copies"
        assert all(m is not None for m in ob.data.materials)


def test_detail_follows_the_camera_and_the_setting(scene):
    from fresing_render.blender import surroundings
    ob = surroundings.add_prop(scene, "PALLET")
    ob.location = (0.0, 0.0, 0.0)
    s = scene.fresing
    assert s.props_detail == "AUTO"
    assert _level(ob) == P.DETAILED
    scene.camera.location = (0.0, -s.props_far - 5.0, 1.5)
    assert _level(ob) == P.LIGHT
    s.props_detail = "DETAILED"
    assert _level(ob) == P.DETAILED
    s.props_detail = "LIGHT"
    scene.camera.location = (0.0, -2.0, 1.0)
    assert _level(ob) == P.LIGHT
    s.props_detail = "AUTO"
    s.props_far = 1.0
    assert _level(ob) == P.LIGHT, "a shorter distance: light sooner"
    s.props_far = 30.0
    assert _level(ob) == P.DETAILED


def test_person_settings_rebuild_in_place(scene):
    from fresing_render.blender import surroundings
    ob = surroundings.add_prop(scene, "PERSON")
    ob.location = (3.0, 1.0, 0.25)
    ob.rotation_euler.z = 0.7
    name, mesh_name = ob.name, ob.data.name
    tall = ob.dimensions.z
    ps = ob.fresing_person
    ps.pose = "KNEELING"
    bpy.context.view_layer.update()
    assert ob.dimensions.z < 0.8 * tall
    assert ob.name == name and ob.data.name == mesh_name and tuple(ob.location) == pytest.approx((3.0, 1.0, 0.25))
    assert ob.rotation_euler.z == pytest.approx(0.7)
    ps.pose = "STANDING"
    ps.helmet = False
    ps.height_choice = "1.65"
    bpy.context.view_layer.update()
    assert ob.dimensions.z == pytest.approx(1.65, abs=0.01)
    ps.height_choice = "1.85"
    bpy.context.view_layer.update()
    assert ob.dimensions.z == pytest.approx(1.85, abs=0.01)
    ps.outfit = "OFFSHORE"
    assert any(m.name.endswith("cloth_orange") for m in ob.data.materials)
    assert len([m for m in bpy.data.meshes if m.name.startswith(mesh_name)]) == 1, "old meshes are removed"


def test_old_projects_get_the_new_look_in_place(scene, tmp_path):
    """A project saved before task 0155: props without fr_prop_ver, plain meshes, no modifier."""
    from fresing_render.blender import props_scale, surroundings
    old = []
    for i, kind in enumerate(("PERSON", "CONTAINER", "PALLET", "BARRIER")):
        m = surroundings._Mesh()
        for sh in S.plain_prop_shapes(kind):
            m.shape(sh, 0)
        me = m.to_mesh(S.PROPS[kind][0])
        ob = bpy.data.objects.new(S.PROPS[kind][0], me)
        surroundings._collection(scene, surroundings.PROPS_COLLECTION).objects.link(ob)
        ob[surroundings.PROP_TAG] = kind
        ob.location = (i * 3.0, 2.0, 0.1)
        ob.rotation_euler.z = 0.3 * i
        old.append((ob.name, kind, tuple(ob.location), ob.rotation_euler.z, len(me.polygons)))
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    props = surroundings.props(sc)
    assert len(props) == len(old)
    for (name, kind, loc, rot, polys), ob in zip(old, sorted(props, key=lambda o: o.location.x)):
        assert ob.name == name and ob[surroundings.PROP_TAG] == kind
        assert tuple(ob.location) == pytest.approx(loc) and ob.rotation_euler.z == pytest.approx(rot)
        assert ob[props_scale.VER_KEY] == props_scale.VERSION and ob.modifiers.get(props_scale.MODIFIER)
        assert len(ob.data.polygons) > polys, f"{kind} got the detailed mesh"
    assert props_scale.upgrade(sc) == 0, "a project opened again is not rebuilt again"


def test_panel_shows_the_selected_person(scene):
    from fresing_render.blender import surroundings, ui
    ob = surroundings.add_prop(scene, "PERSON")
    bpy.context.view_layer.objects.active = ob
    drawn = []

    class _Fake:
        def __getattr__(self, name):
            def f(*a, **k):
                if name == "prop" and len(a) > 1:
                    drawn.append(a[1])
                if name == "panel":
                    return _Fake(), _Fake()
                return _Fake()
            return f

    class _Self:
        layout = _Fake()
    ui.FRESING_PT_props.draw(_Self(), bpy.context)
    assert {"pose", "height_choice", "outfit", "helmet", "gloves", "look"} <= set(drawn)
    assert "props_detail" in drawn


def test_tooltips_of_the_new_settings():
    rna = bpy.types.Object.bl_rna.properties["fresing_person"].fixed_type
    for name in ("pose", "height_choice", "outfit", "helmet", "gloves", "look"):
        desc = rna.properties[name].description
        assert len(desc) > 30 and "\n" not in desc, name
    srna = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type
    for name in ("props_detail", "props_far"):
        assert len(srna.properties[name].description) > 30
    assert math.isclose(srna.properties["props_far"].default, 30.0)
