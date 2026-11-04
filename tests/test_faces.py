"""Painted faces (task 0010): faces painted in CAD come in painted, painting faces by hand,
copies, rules, model update, save + reopen, background render."""

import json
import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
FACES_A = os.path.join(HERE, "data", "test_faces_a.step")
FACES_B = os.path.join(HERE, "data", "test_faces_b.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, faces, logic, ops_panels, queue  # noqa: E402
from fresing_render.core import rules as R  # noqa: E402

# face numbers of a box in OpenCascade's order: 0 -X, 1 +X, 2 -Y, 3 +Y, 4 -Z, 5 +Z (two triangles each)
TOP, FRONT, END = 5, 2, 1


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=FACES_A, quality="draft") == {"FINISHED"}
    return sc


def part(sc, name, n=0):
    hits = sorted((o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name), key=lambda o: o[build.PROP_UID])
    return hits[n]


def indices(ob):
    idx = np.empty(len(ob.data.polygons), dtype=np.int32)
    ob.data.polygons.foreach_get("material_index", idx)
    return idx.tolist()


def slot_names(ob):
    return [s.material.name if s.material else None for s in ob.material_slots]


def test_faces_painted_in_cad_come_in_painted(scene):
    s = scene.fresing
    housing = part(scene, "HOUSING")
    sets = faces.get_sets(housing.data)
    assert [(st["key"], st["faces"]) for st in sets] == [("cad:#3355CC", [FRONT]), ("cad:#CC1A1A", [TOP])]
    assert sets[0]["look"] == "Aluminum - Anodized Glossy (Blue)"       # the face's appearance name
    # whole CAD faces: the two triangles of each face are in the set, the rest is the part
    assert indices(housing) == [0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 2, 2]
    assert faces.groups_on(housing) == ["Aluminum - Anodized Glossy (Blue) #3355CC", "Colour #CC1A1A"]
    assert slot_names(housing) == ["FR " + housing[build.PROP_GROUP], "FR Aluminum - Anodized Glossy (Blue) #3355CC",
                                   "FR Colour #CC1A1A"]
    assert all(sl.link == "OBJECT" for sl in housing.material_slots)
    # the appearance decides the material, the CAD colour paints a plain colour
    assert s.groups["Aluminum - Anodized Glossy (Blue) #3355CC"].material == "aluminium_anodized_color"
    assert (s.groups["Colour #CC1A1A"].material, s.groups["Colour #CC1A1A"].color) == ("paint_satin", "#CC1A1A")
    assert s.groups["Colour #CC1A1A"].faces == 1 and s.groups["Colour #CC1A1A"].count == 0
    assert s.groups["Colour #FF8000"].faces == 2                    # both copies of the bracket
    # parts without painted faces, and a part whose faces all carry the part colour: no sets
    for name in ("COVER", "BLOCK", "EVERY FACE"):
        ob = part(scene, name)
        assert faces.get_sets(ob.data) == [] and len(ob.material_slots) == 1, name
    # every part knows its CAD faces (for picking whole faces with a click)
    assert list(part(scene, "COVER").data[faces.PROP_STARTS]) == [0, 2, 4, 6, 8, 10, 12]


def test_a_rule_turns_a_face_colour_into_another_material(scene):
    s = scene.fresing
    rules = logic.rules_from_scene(s)
    rules.insert(0, R.Rule("Anodised red", "color", "equals", "#CC1A1A"))
    rules.insert(0, R.Rule("Housings", "name", "contains", "HOUSING"))     # name rules sort parts, never faces
    logic.load_rules_into_scene(s, rules)
    logic.apply_rules(scene)
    s.groups["Anodised red"].material = "aluminium_anodized_color"
    s.groups["Anodised red"].color = "#CC1A1A"
    logic.refresh_group_materials(scene)
    housing = part(scene, "HOUSING")
    assert housing[build.PROP_GROUP] == "Housings"
    assert faces.groups_on(housing)[1] == "Anodised red"
    mat = housing.material_slots[2].material
    assert mat.name == "FR Anodised red" and mat["fr_material"] == "aluminium_anodized_color"
    assert s.rules[1].count == 1                                    # the face set counts as a match
    # the rest of the part keeps the part's material
    assert housing.material_slots[0].material.name == "FR Housings"


def test_paint_whole_faces_by_hand(scene):
    s = scene.fresing
    cover = part(scene, "COVER")
    logic.ensure_group(s, "Red paint")
    assert faces.face_of_polygon(cover.data, 3) == 1 and faces.face_of_polygon(cover.data, 11) == 5
    s.face_group = "Red paint"
    bpy.context.view_layer.objects.active = cover
    ops_panels.paint_click(bpy.context, cover, faces.face_of_polygon(cover.data, 11))      # a click on the top
    ops_panels.paint_click(bpy.context, cover, 1)
    assert indices(cover) == [0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1]
    assert faces.groups_on(cover) == ["Red paint"] and slot_names(cover)[1] == "FR Red paint"
    assert s.groups["Red paint"].faces == 1
    # Shift+click: back to the look of the part; another group makes a second set
    ops_panels.paint_click(bpy.context, cover, 1, remove=True)
    logic.ensure_group(s, "Blue paint")
    s.face_group = "Blue paint"
    ops_panels.paint_click(bpy.context, cover, 5)                  # moves the top face to the blue set
    ops_panels.paint_click(bpy.context, cover, 0)
    sets = faces.get_sets(cover.data)
    assert [(st["group"], st["faces"]) for st in sets] == [("Blue paint", [0, 5])]   # the empty red set is gone
    assert indices(cover) == [1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1] and len(cover.material_slots) == 2
    # choose another group for the set, then back to the whole part
    assert bpy.ops.fresing.face_set_group(key=sets[0]["key"], group="Red paint") == {"FINISHED"}
    assert faces.groups_on(cover) == ["Red paint"]
    assert bpy.ops.fresing.face_set_remove(key=sets[0]["key"]) == {"FINISHED"}
    assert faces.get_sets(cover.data) == [] and set(indices(cover)) == {0} and len(cover.material_slots) == 1
    assert s.groups["Red paint"].faces == 0


def test_copies_share_face_sets_but_can_differ(scene):
    s = scene.fresing
    a, b = part(scene, "BRACKET", 0), part(scene, "BRACKET", 1)
    assert a.data is b.data
    logic.ensure_group(s, "Black")
    # only this copy: a's orange end turns black, b keeps the CAD colour
    faces.set_group(a, "cad:#FF8000", "Black", only_this_copy=True)
    logic.apply_rules(scene)
    assert faces.groups_on(a) == ["Black"] and faces.groups_on(b) == ["Colour #FF8000"]
    assert slot_names(a)[1] == "FR Black" and slot_names(b)[1] == "FR Colour #FF8000"
    # faces painted on one copy only: the other copy shows them like its part
    s.face_only_copy = True
    s.face_group = "Black"
    ops_panels.paint_click(bpy.context, b, TOP)
    assert indices(a) == indices(b)                                 # one mesh
    assert faces.groups_on(b)[1] == "Black" and faces.groups_on(a)[1] == a[build.PROP_GROUP]
    # back to the whole part on copy a only; then for every copy
    faces.remove(a, "cad:#FF8000", only_this_copy=True)
    logic.apply_rules(scene)
    assert faces.groups_on(a)[0] == a[build.PROP_GROUP] and faces.groups_on(b)[0] == "Colour #FF8000"
    faces.set_group(a, "cad:#FF8000", "Black")                      # every copy: the copy choices go
    logic.apply_rules(scene)
    assert faces.groups_on(a)[0] == faces.groups_on(b)[0] == "Black"
    assert "cad:#FF8000" not in faces.get_copy(a)


def test_renamed_and_removed_groups(scene):
    s = scene.fresing
    cover = part(scene, "COVER")
    logic.ensure_group(s, "Red paint")
    faces.paint(cover, [TOP], "Red paint")
    logic.apply_rules(scene)
    s.groups["Red paint"].name = "Signal red"
    assert faces.get_sets(cover.data)[0]["group"] == "Signal red"
    logic.apply_rules(scene)
    assert faces.groups_on(cover) == ["Signal red"]
    s.groups_index = next(i for i, g in enumerate(s.groups) if g.name == "Signal red")
    assert bpy.ops.fresing.group_remove() == {"FINISHED"}
    assert faces.groups_on(cover) == [cover[build.PROP_GROUP]]    # painted faces look like the part again
    assert s.groups.get("Signal red") is None


def test_save_and_reopen(scene, tmp_path):
    cover = part(scene, "COVER")
    logic.ensure_group(scene.fresing, "Red paint")
    faces.paint(cover, [TOP], "Red paint")
    faces.set_group(part(scene, "BRACKET", 1), "cad:#FF8000", "Red paint", only_this_copy=True)
    logic.apply_rules(scene)
    path = str(tmp_path / "faces.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    cover = part(sc, "COVER")
    assert indices(cover) == [0] * 10 + [1, 1] and slot_names(cover)[1] == "FR Red paint"
    assert slot_names(part(sc, "BRACKET", 1))[1] == "FR Red paint"
    assert slot_names(part(sc, "BRACKET", 0))[1] == "FR Colour #FF8000"
    logic.apply_rules(sc)                                           # sorting again changes nothing
    assert slot_names(cover)[1] == "FR Red paint" and slot_names(part(sc, "BRACKET", 1))[1] == "FR Red paint"


def test_model_update_keeps_painted_faces_of_unchanged_parts(scene):
    s = scene.fresing
    logic.ensure_group(s, "Red paint")
    faces.paint(part(scene, "COVER"), [TOP], "Red paint")
    faces.paint(part(scene, "BLOCK"), [TOP], "Red paint")
    housing = part(scene, "HOUSING")
    logic.ensure_group(s, "Anodised red")
    faces.set_group(housing, "cad:#CC1A1A", "Anodised red")
    faces.set_group(part(scene, "BRACKET", 1), "cad:#FF8000", "Red paint", only_this_copy=True)
    logic.apply_rules(scene)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=FACES_B, quality="draft", update_root=root.name) == {"FINISHED"}
    cover = part(scene, "COVER")
    assert faces.groups_on(cover) == ["Red paint"] and indices(cover)[10:] == [1, 1]
    assert faces.groups_on(part(scene, "HOUSING"))[1] == "Anodised red"         # choice for a CAD face set kept
    assert faces.groups_on(part(scene, "BRACKET", 1)) == ["Red paint"]           # and the one for one copy
    assert faces.groups_on(part(scene, "BRACKET", 0)) == ["Colour #FF8000"]
    block = part(scene, "BLOCK")                                   # a cylinder now: its faces changed
    assert faces.get_sets(block.data) == []
    notes = [n.text for n in s.report_notes]
    assert any(n.startswith("BLOCK:") and "painted" in n for n in notes), notes
    assert not any(n.startswith("COVER") for n in notes)


def test_meshes_of_old_projects_find_their_faces(scene):
    """Projects imported before 0.2.9 have no face list: the faces are found from the triangles."""
    for name in ("COVER", "HOUSING"):
        me = part(scene, name).data
        stored = list(me[faces.PROP_STARTS])
        del me[faces.PROP_STARTS]
        assert faces.face_starts(me).tolist() == stored
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from fresing_render.importer import step_reader
    occ = step_reader._occ()
    starts: list = []
    pos, nrm, tri, _c, _p = step_reader._mesh_shape(occ, BRepPrimAPI_MakeCylinder(30.0, 80.0).Shape(),
                                                    *step_reader.QUALITY["normal"], face_starts=starts)
    me = build._new_mesh("cyl", pos, nrm, tri)
    assert faces.face_starts(me).tolist() == starts                 # a round face with many triangles too


def test_faces_with_their_own_look_in_a_background_render(scene, tmp_path):
    """The queue renders a saved copy of the project: painted faces must show there too."""
    s = scene.fresing
    cover = part(scene, "COVER")
    for ob in build.iter_parts(scene):
        if ob is not cover:
            ob.hide_render = True
    logic.ensure_group(s, "Bright red")
    g = s.groups["Bright red"]
    g.material, g.color = "paint_satin", "#FF0000"
    faces.paint(cover, [TOP], "Bright red")
    logic.apply_rules(scene)
    cam_data = bpy.data.cameras.new("Top")
    cam = bpy.data.objects.new("Top", cam_data)
    scene.collection.objects.link(cam)
    bpy.context.view_layer.update()
    lo, hi = build.world_bounds([cover])
    cam.location = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, hi[2] + 1.0)      # straight down on the top face
    cam_data.type, cam_data.ortho_scale = "ORTHO", 0.2
    scene.camera = cam
    from fresing_render.blender import states
    s.out_resolution = "preview"
    s.quality = "draft"
    s.use_gpu = False
    states.save_shot(scene, "Top")
    queue.add_job(scene, "STILL", shot="Top")
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "q.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 300:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 30))
    img = bpy.data.images.load(job.output)
    px = np.array(img.pixels[:]).reshape(img.size[1], img.size[0], 4)
    mid = px[img.size[1] // 4: 3 * img.size[1] // 4, img.size[0] // 4: 3 * img.size[0] // 4, :3]
    red = mid[..., 0] - np.maximum(mid[..., 1], mid[..., 2]) > 0.3      # the rest of the part is light grey
    assert red.mean() > 0.5, mid.mean(axis=(0, 1))


def test_paint_panel_draws(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui
    s = scene.fresing
    errors = []
    for active in ("HOUSING", "COVER"):
        bpy.context.view_layer.objects.active = part(scene, active)
        for painting in (False, True):
            s.face_painting = painting
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            ui.FRESING_PT_faces.draw(fake, bpy.context)
            ui.FRESING_PT_faces.draw_header_preset(fake, bpy.context)
    s.face_painting = False
    assert not errors, errors


def test_face_sets_data_is_plain_json(scene):
    """What the .blend keeps is readable and complete (key, kind, colour, look, group, faces)."""
    data = json.loads(part(scene, "HOUSING").data[faces.PROP_SETS])
    assert set(data[0]) == {"key", "kind", "color", "look", "group", "faces"}
