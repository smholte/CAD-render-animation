"""The material picker (task 0273): own material files (core), the entries, using one for a group, this project's
short list, own / department / company materials from 0272's Materials folders with their badges, a project that
renders without the material's folder, a Blender material appended, paint schemes and templates keeping them."""

import json
import os
import shutil

import pytest

from fresing_render.core import material_files as F
from fresing_render.core import materials_lib as ML

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")


# ---------------------------------------------------------------------------------------------------------------------
# core: the file

def test_new_material_round_trip(tmp_path):
    d = F.new_material("Our machine blue", "paint_satin", {"color": "RAL 5015", "wear": 0.25, "rust": 0.1},
                       "Satin blue of our frames", "someone", "0.2.300")
    assert d["format"] == F.FORMAT and d["base"] == "paint_satin" and d["tags"]["colour"] == "blue"
    folder = F.save_new(str(tmp_path), d)
    assert os.path.basename(folder) == "Our machine blue"
    e = F.read_folder(folder, "mine", "Mine")
    assert e.ok and e.key == "own:" + d["id"] and e.name == "Our machine blue" and e.badge == "Mine"
    assert e.changes == {"color": "RAL 5015", "wear": 0.25, "rust": 0.1}
    assert not e.takes_colour                                  # it has a colour of its own
    v = F.values_of(e)
    assert v["material"] == "paint_satin" and v["color"] == "RAL 5015" and v["wear"] == 0.25
    assert F.save_new(str(tmp_path), d).endswith("Our machine blue (2)")        # never over another folder


def test_changes_only_what_the_base_uses():
    ch = F.changes_of("steel_machined", "RAL 3020", 0.3, 0.4)
    assert ch == {"wear": 0.3, "rust": 0.4}                    # bare steel takes no colour
    assert "rust" not in F.changes_of("stainless_brushed", "", 0.0, 0.5)        # stainless does not rust
    ch = F.changes_of("knurl_diamond", finish={"size": 0.0012, "angle": 30.0, "amount": 0.8, "base": "STEEL",
                                               "kind": ""})
    assert ch["finish"]["size"] == pytest.approx(0.0012) and ch["finish"]["base"] == "STEEL"
    bad = []
    assert F.clean_changes("paint_satin", {"color": "not a colour", "shine": 3, "wear": "x"}, bad) == {}
    assert len(bad) == 3


@pytest.mark.parametrize("content, problem", [
    (None, "No material.json"),
    ("{not json", "cannot be read"),
    ('{"format": "something else"}', "Not a Fresing material"),
    ('{"format": "fresing-material", "format_version": "2.0", "id": "abcd1234", "name": "X", "base": "chrome"}',
     "newer Fresing Render"),
    ('{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "base": "chrome"}', "no name"),
    ('{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "X", "base": "unobtainium"}',
     "Unknown library material"),
    ('{"format": "fresing-material", "format_version": "1.0", "name": "X", "base": "chrome"}', "no id"),
    ('{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "X", "base": "chrome",'
     ' "blend": {"material": "M"}}', "Blender file"),
    ('[1, 2]', "not a material"),
    ('{"format": "fresing-material", "format_version": "1.0", "id": "abcd1234", "name": "X", "base": "chrome"}'
     + " " * 10, ""),
])
def test_a_broken_folder_is_listed_with_its_problem(tmp_path, content, problem):
    folder = tmp_path / "M"
    folder.mkdir()
    if content is not None:
        (folder / F.JSON_NAME).write_text(content, encoding="utf-8")
    else:
        (folder / F.BLEND_NAME).write_bytes(b"BLENDER")
    found = F.list_folder(str(tmp_path))
    assert len(found) == 1
    e = found[0]
    if problem:
        assert not e.ok and any(problem in p for p in e.problems), e.problems
    else:
        assert e.ok


def test_newer_minor_keeps_what_it_added_and_older_writes_are_refused(tmp_path):
    d = F.new_material("A", "chrome")
    d["format_version"] = "1.7"
    d["glow"] = {"x": 1}
    e = F.entry_from_data(d)
    assert e.ok and any("newer" in n for n in e.notes) and any("glow" in n for n in e.notes)
    d["format_version"] = "3.0"
    with pytest.raises(F.MaterialError):
        F.write_json(str(tmp_path / "x"), d)


def test_folder_names_work_on_windows():
    assert F.folder_name('Blue: "gloss"/old') == "Blue_ _gloss__old"
    assert F.folder_name("con") == "con_" and F.folder_name("COM1.x") == "COM1_.x"
    with pytest.raises(F.MaterialError):
        F.folder_name(" ..")


def test_colour_family_of_ral_colours():
    fam = {c: F.colour_family(F.rgb_of(c)) for c in ("RAL 9010", "RAL 7035", "RAL 9005", "RAL 3020", "RAL 2004",
                                                      "RAL 1003", "RAL 6018", "RAL 5010", "RAL 4005", "RAL 8017")}
    assert fam == {"RAL 9010": "white", "RAL 7035": "grey", "RAL 9005": "black", "RAL 3020": "red",
                   "RAL 2004": "orange", "RAL 1003": "yellow", "RAL 6018": "green", "RAL 5010": "blue",
                   "RAL 4005": "purple", "RAL 8017": "brown"}


def test_builtins_and_filters():
    b = F.builtin_entries()
    keys = [e.key for e in b]
    assert "builtin:blender_material" not in keys and "builtin:paint_satin" in keys
    assert len(keys) == len(set(keys)) == len(ML.MATERIALS) - len(ML.NOT_PICKED) + sum(1 for p in ML.PRESETS if p[3])
    p = F.builtin("preset:paint_5010")
    assert p.changes == {"color": "RAL 5010"} and p.colour == "blue" and not p.takes_colour
    assert F.builtin("builtin:paint_satin").takes_colour
    assert F.builtin_for("paint_satin", "ral 5010").key == "preset:paint_5010"
    assert F.builtin_for("paint_satin", "RAL 4005").key == "builtin:paint_satin"
    knurls = F.filter_entries(b, "knurl")
    assert {e.base for e in knurls} >= {"knurl_diamond", "knurl_straight"}
    assert all(e.kind == "Stainless" for e in F.filter_entries(b, kind="Stainless"))
    assert all("see-through" in e.looks for e in F.filter_entries(b, look="see-through"))
    assert F.filter_entries(b, "blue satin")                    # every word must be found
    assert not F.filter_entries(b, "zzz nothing")
    own = [F.Entry(key="own:a", name="Z", source="mine", badge="Mine"),
           F.Entry(key="own:b", name="A", source="company", badge="ACME")]
    proj = [F.Entry(key="own:a", name="Z", source="project", badge="This project"),
            F.Entry(key="own:c", name="C", source="project", badge="This project")]
    merged = F.merge(b[:2], own, proj)
    assert [e.key for e in merged[2:]] == ["own:b", "own:a", "own:c"]           # the folder's copy wins
    assert [s for s, _src in F.sources(merged)] == ["Built-in", "This project", "ACME", "Mine"]


# ---------------------------------------------------------------------------------------------------------------------
# Blender

bpy = None


@pytest.fixture(scope="module")
def app():
    global bpy
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()


@pytest.fixture()
def loc(app, tmp_path, monkeypatch):
    from fresing_render.blender import locations, material_picker, prefs
    from fresing_render.core import locations as L
    monkeypatch.setenv(locations.ENV, str(tmp_path / "config é" / L.STATE_FILE))
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs ü"))
    prefs.get().library_path = ""
    locations.forget()
    locations.load()
    locations.wait_reach()
    material_picker._S.update(own=[], own_time=-1e9, own_gen=None)
    yield locations
    locations.forget()


def _mine(loc):
    return loc.save_folder("materials")


@pytest.fixture()
def scene(loc):
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    sc.fresing.groups_index = 0
    return sc


def _parts(sc, g):
    from fresing_render.blender import logic
    return logic.parts_in_group(sc, g.name)


def test_use_a_builtin_keeps_the_groups_colour_and_wear(scene):
    from fresing_render.blender import material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    g.color, g.wear = "RAL 2004", 0.4
    assert bpy.ops.fresing.mat_use(key="builtin:paint_gloss") == {"FINISHED"}
    assert (g.material, g.color, round(g.wear, 3), g.mat_key) == ("paint_gloss", "RAL 2004", 0.4, "builtin:paint_gloss")
    mat = bpy.data.materials["FR " + g.name]
    assert mat["fr_material"] == "paint_gloss" and mat["fr_color"] == "RAL 2004"
    assert all(ob.material_slots[0].material == mat for ob in _parts(scene, g))
    assert bpy.ops.fresing.mat_use(key="preset:paint_5010") == {"FINISHED"}            # a ready-made colour
    assert (g.material, g.color) == ("paint_satin", "RAL 5010")
    assert MP.group_key(g) == "preset:paint_5010"
    g.material = "chrome"                                  # the drop-down: the link to the entry ends
    assert g.mat_key == "" and MP.group_key(g) == "builtin:chrome"
    assert bpy.ops.fresing.mat_use(key="builtin:knurl_diamond") == {"FINISHED"}
    g.fin_size = 0.0015
    assert bpy.ops.fresing.mat_use(key="builtin:knurl_diamond") == {"FINISHED"}         # same finish: kept
    assert g.fin_size == pytest.approx(0.0015)


def test_short_list_star_and_off(scene):
    from fresing_render.blender import material_picker as MP
    s = scene.fresing
    assert MP.short_list(scene)[0][1:] == (False, True)        # the group's material shows, marked "in use"
    assert bpy.ops.fresing.mat_star(key="builtin:chrome") == {"FINISHED"}
    assert bpy.ops.fresing.mat_star(key="preset:paint_3020") == {"FINISHED"}
    keys = [e.key for e, listed, _u in MP.short_list(scene) if listed]
    assert keys == ["builtin:chrome", "preset:paint_3020"]
    assert bpy.ops.fresing.mat_star(key="builtin:chrome") == {"FINISHED"}                 # again: off the list
    assert [e.key for e, listed, _u in MP.short_list(scene) if listed] == ["preset:paint_3020"]
    assert bpy.ops.fresing.mat_unlist(key="preset:paint_3020") == {"FINISHED"}
    assert not [1 for _e, listed, _u in MP.short_list(scene) if listed]
    assert len(s.project_materials) == 0


def test_save_as_my_material_and_render_without_its_folder(scene, loc, tmp_path):
    from fresing_render.blender import logic
    from fresing_render.blender import material_picker as MP
    s = scene.fresing
    g = s.groups[0]
    g.material, g.color, g.wear, g.rust = "paint_satin", "RAL 5015", 0.3, 0.2
    root = _mine(loc)
    e = MP.save_from_group(bpy.context, g, "Our blue", "Frames", root)
    assert e.ok and e.source == "mine" and e.badge == "Mine" and g.mat_key == e.key
    assert os.path.isfile(os.path.join(e.folder, F.JSON_NAME))
    MP.wait_pictures(240)
    assert os.path.isfile(os.path.join(e.folder, F.PICTURE_NAME)), "the picture was not made"
    assert e.key in [x.key for x in MP.all_entries(scene)]
    assert s.project_materials.get(e.key).data                 # a copy in the project
    # another group gets it from the list
    g2 = s.groups[1]
    assert bpy.ops.fresing.mat_use(key=e.key, group=g2.name) == {"FINISHED"}
    assert (g2.material, g2.color, round(g2.wear, 3), round(g2.rust, 3)) == ("paint_satin", "RAL 5015", 0.3, 0.2)
    # a paint scheme keeps the entry
    logic.save_scheme(s, "Blue")
    g2.material = "chrome"
    assert g2.mat_key == ""
    logic.apply_scheme(scene, "Blue")
    assert g2.mat_key == e.key and g2.material == "paint_satin"
    # save, take the folder away, open again: the project still knows and renders it
    path = str(tmp_path / "project é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    shutil.rmtree(e.folder)
    MP.refresh_own(force=True, wait=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    g = sc.fresing.groups[0]
    found = MP.find(sc, g.mat_key)
    assert found is not None and found.source == "project" and found.badge == MP.BADGE_PROJECT
    logic.refresh_group_materials(sc)
    mat = bpy.data.materials["FR " + g.name]
    assert mat["fr_color"] == "RAL 5015" and mat.node_tree.nodes
    sc.render.resolution_x = sc.render.resolution_y = 32
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.render.filepath = str(tmp_path / "r.png")
    bpy.ops.render.render(write_still=True)
    assert os.path.isfile(str(tmp_path / "r.png"))


def test_company_and_department_materials_with_badges(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP
    from fresing_render.core import locations as L
    shared = tmp_path / "Server" / "Materials"
    F.save_new(str(shared), F.new_material("ACME green", "paint_gloss", {"color": "RAL 6018"}))
    F.save_new(str(shared), F.new_material("ACME green", "paint_matte", {"color": "RAL 6018"}))     # same name
    (shared / "broken").mkdir()
    (shared / "broken" / F.JSON_NAME).write_text("{", encoding="utf-8")
    s = L.Setup(id="acme", name="ACME", level="company", label="ACME", locations={"materials": [str(shared)]})
    p = str(tmp_path / "acme.frsetup")
    L.write_setup(p, s)
    loc.install(p, "copy")
    loc.wait_reach()
    F.save_new(_mine(loc), F.new_material("My grey", "paint_satin", {"color": "RAL 7001"}))
    MP.refresh_own(force=True, wait=True)
    own = [e for e in MP.all_entries(scene) if e.source != "builtin"]
    names = [(e.name, e.badge, e.ok) for e in own]
    assert ("ACME green", "ACME", True) in names and ("My grey", "Mine", True) in names
    assert sum(1 for n in names if n[0] == "ACME green") == 2                 # both listed, none hidden
    assert any(not e.ok for e in own)                                         # the broken one, with its problem
    from fresing_render.blender import ui_material_picker as UI
    st = UI.state(bpy.context)
    st.source = "ACME"
    assert {e.badge for e in UI.visible(bpy.context)} == {"ACME"}
    st.source = UI.ALL
    bad = next(e for e in own if not e.ok)
    assert bpy.ops.fresing.mat_use(key=bad.key) == {"CANCELLED"} or not bad.key.startswith("own:x")


def test_from_a_blender_material_appended_and_kept(scene, loc, tmp_path):
    from fresing_render.blender import logic, material_picker as MP
    mat = bpy.data.materials.new("Shop red")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.05, 0.03, 1.0)
    assert "Shop red" in [m.name for m in MP.blender_materials()]
    g = scene.fresing.groups[0]
    e = MP.save_from_blender(bpy.context, mat, "Shop red", "", _mine(loc), group=g)
    assert e.ok and e.is_blend and os.path.isfile(e.blend)
    assert g.material == "blender_material" and g.mat_key == e.key
    gm = bpy.data.materials["FR " + g.name]
    assert gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[0] == pytest.approx(0.8)
    src = bpy.data.materials[scene.fresing.project_materials[e.key].blend_mat]
    assert src.use_fake_user and src.library is None                         # appended, not linked
    assert all(ob.material_slots[0].material == gm for ob in _parts(scene, g))
    assert logic.upgrade_looks(scene) == 0                                    # not rebuilt as a library look
    MP.wait_pictures(240)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    shutil.rmtree(e.folder)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    g = sc.fresing.groups[0]
    logic.refresh_group_materials(sc)
    gm = bpy.data.materials["FR " + g.name]
    assert gm.get("fr_material") == "blender_material"
    assert gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value[0] == pytest.approx(0.8)


def test_template_keeps_the_short_list(scene, loc, tmp_path):
    from fresing_render.blender import material_picker as MP, ops_main
    from fresing_render.core.template import Template
    g = scene.fresing.groups[0]
    g.material, g.color = "paint_satin", "RAL 1021"
    e = MP.save_from_group(bpy.context, g, "Yellow", "", _mine(loc))
    MP.add_to_project(scene, e)
    assert bpy.ops.fresing.mat_star(key="builtin:chrome") == {"FINISHED"}
    t = ops_main._template_from_scene(scene)
    path = str(tmp_path / "t.json")
    t.save(path)
    t2 = Template.load(path)
    assert [m["key"] for m in t2.materials] == [e.key, "builtin:chrome"]
    MP.wait_pictures(240)
    shutil.rmtree(e.folder)
    MP.refresh_own(force=True, wait=True)
    bpy.ops.wm.read_homefile(use_empty=True)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    ops_main.apply_template(sc, t2)
    listed = [x.key for x, lst, _u in MP.short_list(sc) if lst]
    assert listed == [e.key, "builtin:chrome"]
    assert MP.find(sc, e.key).changes["color"] == "RAL 1021"              # from the template, no folder


def test_window_draws_quickly_with_every_material(scene):
    """The window's draw (Python side) with every entry: it must stay well under ~20 ms on the 4-core machine."""
    import time

    from fresing_render.blender import ui_material_picker as UI

    class Any:
        def __getattr__(self, name):
            return lambda *a, **k: self

        def __setattr__(self, name, value):
            pass

        def __iter__(self):
            return iter((self, self))

    ctx = bpy.context
    UI.draw_window(Any(), ctx)                       # the first one loads the pictures
    t0 = time.perf_counter()
    for _ in range(5):
        UI.draw_window(Any(), ctx)
    each = (time.perf_counter() - t0) / 5
    assert len(UI.visible(ctx)) >= 100
    assert each < 0.02, f"{each * 1000:.1f} ms a draw"


OLD = os.path.join(HERE, "data", "old_project_0_2_195.blend")


def test_a_project_of_0_2_195_opens_unchanged(app, tmp_path):
    """A project saved by 0.2.195 (made with tools in this task's report: the test machine, four groups given a
    material, colour and wear, a paint scheme): every group keeps its look, nothing is put on its list, the picker
    shows what the groups use, the scheme still switches, it renders."""
    from fresing_render.blender import logic, material_picker as MP
    path = str(tmp_path / "old.blend")
    shutil.copy(OLD, path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = sc.fresing
    want = [("paint_satin", "RAL 5010", 0.3), ("steel_ground", "#13447C", 0.0), ("powder_coat", "RAL 9005", 0.1),
            ("paint_gloss", "RAL 3020", 0.0), ("plastic_gloss", "RAL 9003", 0.0)]
    assert [(g.material, g.color, round(g.wear, 3)) for g in s.groups] == want
    assert all(g.mat_key == "" for g in s.groups) and len(s.project_materials) == 0
    logic.upgrade_looks(sc)
    assert [(g.material, g.color, round(g.wear, 3)) for g in s.groups] == want
    for g in s.groups:
        mat = bpy.data.materials["FR " + g.name]
        assert mat["fr_material"] == g.material and mat["fr_color"] == g.color
    assert MP.group_key(s.groups[0]) == "preset:paint_5010"            # a ready-made colour is found again
    assert MP.group_key(s.groups[1]) == "builtin:steel_ground"
    shown = MP.short_list(sc)
    assert all(not listed and used for _e, listed, used in shown) and len(shown) == 5
    s.groups[0].material = "chrome"
    assert logic.apply_scheme(sc, "Blue") == 5 and s.groups[0].material == "paint_satin"
    sc.render.resolution_x = sc.render.resolution_y = 32
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    sc.render.filepath = str(tmp_path / "old.png")
    bpy.ops.render.render(write_still=True)
    assert os.path.isfile(str(tmp_path / "old.png"))
