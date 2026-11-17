"""Workspaces, function families, own-workspace files, the app's own panel headers and the Client view's lock
(task 0062)."""

import json
import os

import pytest

from fresing_render.core import functions as F
from fresing_render.core import workspaces as W

# ---------------------------------------------------------------------------------------------------------------
# core: what shows
# ---------------------------------------------------------------------------------------------------------------


def test_every_family_has_a_workspace_row_and_every_key_is_known():
    assert set(F.FAMILY_WORKSPACES) == set(F.FAMILIES)
    for fam, keys in F.FAMILY_WORKSPACES.items():
        assert set(keys) <= set(F.WORKSPACE_KEYS), fam
    for fn in F.FUNCTIONS.values():
        assert fn.family in F.FAMILIES
    assert set(W.BUILTIN) == set(F.WORKSPACE_KEYS)
    assert set(F.ALWAYS) <= set(F.FAMILIES)


def test_all_functions_and_full_access_show_everything():
    for key in ("all", "full"):
        ws = W.builtin(key)
        assert W.shown_functions(ws) == frozenset(F.FUNCTIONS)
        assert W.hidden_panels(ws) == frozenset()
    assert W.builtin("full").blender_ui and not W.builtin("all").blender_ui
    assert W.DEFAULT == W.NAMES["all"]


def test_cnc_hides_the_sea_offshore_hides_milling_product_hides_both():
    cnc, off, prod = (W.hidden_panels(W.builtin(k)) for k in ("cnc", "offshore", "product"))
    assert {"FRESING_PT_cables", "FRESING_PT_spools", "FRESING_PT_vessel_motion", "FRESING_PT_weather"} <= cnc
    assert "FRESING_PT_cnc" not in cnc and "FRESING_PT_milling" not in cnc and "FRESING_PT_waycover" not in cnc
    assert {"FRESING_PT_cnc", "FRESING_PT_cnc_tools", "FRESING_PT_milling", "FRESING_PT_waycover"} <= off
    assert "FRESING_PT_cables" not in off and "FRESING_PT_cylinders" not in off
    assert {"FRESING_PT_cnc", "FRESING_PT_milling", "FRESING_PT_cables", "FRESING_PT_spools"} <= prod
    for hidden in (cnc, off, prod):                     # what every project needs is never hidden
        assert not {"FRESING_PT_import", "FRESING_PT_looks", "FRESING_PT_scene", "FRESING_PT_output",
                    "FRESING_PT_camera", "FRESING_PT_animation", "FRESING_PT_queue", "FRESING_PT_motion"} & hidden
    assert "poses.explode" not in W.shown_functions(W.builtin("cnc"))       # the owner's list: CNC hides exploded views
    assert "poses.explode" in W.shown_functions(W.builtin("product"))


def test_client_view_shows_only_looking_and_rendering_and_locks():
    ws = W.builtin("client")
    assert ws.lock and not ws.blender_ui
    hidden = W.hidden_panels(ws)
    for shown in ("import", "scene", "camera", "shots", "turntable", "output", "queue"):
        assert "FRESING_PT_" + shown not in hidden, shown
    for gone in ("structure", "looks", "motion", "animation", "cnc", "cables", "web3d", "props", "labels"):
        assert "FRESING_PT_" + gone in hidden, gone
    assert not any(w.lock for w in W.builtins() if w.key != "client")


def test_ticks_go_on_top_of_the_workspace():
    ws = W.builtin("offshore")
    assert not W.effective_families(ws)["cnc"]
    fam = W.effective_families(ws, {"cnc": True, "offshore": False})
    assert fam["cnc"] and not fam["offshore"] and fam["import"]
    shown = W.shown_functions(ws, {"cnc": True})
    assert "cnc.machine" in shown and "cnc.tools" in shown                  # a family ticked on shows all of it
    hidden = W.hidden_panels(ws, {"offshore": False})
    assert "FRESING_PT_cables" in hidden and "FRESING_PT_spools" in hidden
    assert W.parse_ticks("not json") == {} and W.parse_ticks('{"import": false, "cnc": 0, "x": 1}') == {"cnc": False}
    assert W.ticks_json({}) == "" and json.loads(W.ticks_json({"cnc": True})) == {"cnc": True}
    # an always-on family cannot be ticked off
    assert W.effective_families(ws, {"import": False})["import"]


def test_a_panel_no_function_names_always_shows():
    assert "FRESING_PT_workspace" not in W.hidden_panels(W.builtin("client"))
    assert "FRESING_PT_tour" not in W.hidden_panels(W.builtin("client"))


def test_a_function_added_later_adds_itself():
    funcs = dict(F.FUNCTIONS)
    funcs["lifting.plan"] = F.Function(id="lifting.plan", title="Lifting plan", family="motion",
                                       panel="FRESING_PT_lifting", button="fresing.x", workspaces=("offshore",))
    assert "lifting.plan" in W.shown_functions(W.builtin("offshore", funcs), funcs=funcs)
    assert "lifting.plan" not in W.shown_functions(W.builtin("cnc", funcs), funcs=funcs)
    assert "FRESING_PT_lifting" in W.hidden_panels(W.builtin("cnc", funcs), funcs=funcs)
    assert "lifting.plan" in W.shown_functions(W.builtin("all", funcs), funcs=funcs)


def test_hide_warning_names_what_is_set_up():
    text = W.hide_warning("cnc", ["a CNC machine", "3 tools", "a G-code step"])
    assert text.startswith("This project has a CNC machine, 3 tools and a G-code step. They stay in the project")
    assert "only the panels are hidden" in text
    assert W.hide_warning("offshore", ["a cable"]).startswith("This project has a cable. It stays in the project and "
                                                               "keeps working")
    assert W.hide_warning("cnc", []) == ""


# ---------------------------------------------------------------------------------------------------------------
# core: own workspaces as files
# ---------------------------------------------------------------------------------------------------------------


def test_own_workspace_round_trip_rename_delete(tmp_path):
    folder = str(tmp_path / "Workspaces")
    ws = W.make_own("Offshore cranes", W.builtin("offshore"), {"cnc": True, "web": False}, "for the crane jobs")
    assert ws.own and ws.families["cnc"] and not ws.families["web"] and ws.based_on == "offshore"
    path = W.save_in(folder, ws)
    assert os.path.basename(path) == "Offshore cranes.json"
    found = W.scan(folder)
    assert list(found) == ["Offshore cranes"]
    back = found["Offshore cranes"][1]
    assert back.families == ws.families and back.hide == ws.hide and back.note == "for the crane jobs"
    assert W.shown_functions(back) == W.shown_functions(W.builtin("offshore"), {"cnc": True, "web": False})
    W.save_in(folder, ws)                                           # saving again replaces its own file
    assert len(os.listdir(folder)) == 1
    W.rename_in(folder, "Offshore cranes", "Mill demos")
    assert list(W.scan(folder)) == ["Mill demos"] and os.listdir(folder) == ["Mill demos.json"]
    with pytest.raises(ValueError):
        W.rename_in(folder, "Mill demos", "  ")
    W.delete_in(folder, "Mill demos")
    assert W.scan(folder) == {}
    with pytest.raises(FileNotFoundError):
        W.delete_in(folder, "Mill demos")


def test_a_copied_file_shows_up_and_bad_files_are_skipped(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    W.save_in(a, W.make_own("Mill demos", W.builtin("cnc")))
    os.makedirs(b)
    with open(os.path.join(a, "Mill demos.json"), "rb") as src, open(os.path.join(b, "from colleague.json"), "wb") as dst:
        dst.write(src.read())                                       # a colleague's copy, under another file name
    with open(os.path.join(b, "broken.json"), "w") as fh:
        fh.write("{ not json")
    with open(os.path.join(b, "other.json"), "w") as fh:
        json.dump({"something": "else"}, fh)
    assert list(W.scan(b)) == ["Mill demos"]


def test_a_file_from_a_newer_version_opens(tmp_path):
    d = {W.MARKER: 99, "name": "From the future", "based_on": "offshore",
         "families": {"cnc": True, "teleportation": True, "import": False}, "hide": ["no.such_function", "poses.explode"],
         "lock": False, "new_field": [1, 2, 3]}
    ws = W.from_dict(d)
    assert ws.families["cnc"] and ws.families["import"]             # always-on stays on; unknown family ignored
    assert "teleportation" not in ws.families and ws.hide == ("poses.explode",)
    assert ws.families["offshore"] and not ws.families["milling"]   # not named in the file: as its base workspace
    with pytest.raises(ValueError):
        W.from_dict({"name": "no marker"})


def test_names(tmp_path):
    assert W.name_problem("") and W.name_problem("???")
    assert W.name_problem("Mill demos", ["mill DEMOS"])
    assert W.name_problem("CNC & machining") == ""                 # an own one may take a built-in's name: it wins
    assert W.file_name('a/b:c') == "a_b_c.json" and W.file_name("CON") == "_CON.json"
    assert W.key_of("Full access") == "full" and W.key_of("cnc") == "cnc" and W.key_of("nope") == ""
    own = {"CNC & machining": ("x.json", W.make_own("CNC & machining", W.builtin("all")))}
    assert W.shadows("CNC & machining", own) and not W.shadows("Mill demos", own)
    assert W.find("CNC & machining", own).own and not W.find("CNC & machining").own


# ---------------------------------------------------------------------------------------------------------------
# in Blender: a project's state, what it uses, the headers, the lock
# ---------------------------------------------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")
GANTRY = os.path.join(HERE, "data", "test_gantry.step")


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    addon_utils.enable("cycles", default_set=True)
    os.environ["FRESING_WORKSPACES_DIR"] = str(tmp_path_factory.mktemp("lib") / "Workspaces")
    fresing_render.register()
    yield
    fresing_render.unregister()
    os.environ.pop("FRESING_WORKSPACES_DIR", None)


def _mods():
    from fresing_render.blender import lock, panels, workspaces
    return workspaces, panels, lock


def _new(path=None):
    bpy.ops.wm.read_homefile(use_empty=True)
    if path:
        assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def _polls(name):
    return getattr(bpy.types, name).poll(bpy.context)


def test_a_new_project_starts_in_the_default_workspace_with_sections_folded():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    assert sc.fresing.ws_name == "All functions" and not lock.ON[0]
    for sec in panels.SECTIONS:
        assert not panels.is_open(sec), sec
    assert panels.is_open("FRESING_PT_camera") and not panels.is_open("FRESING_PT_cutaway")
    assert _polls("FRESING_PT_looks") and _polls("FRESING_PT_motion")
    assert not _polls("FRESING_PT_cutaway")                      # its section is folded: nothing under it shows
    panels.open_to("FRESING_PT_cnc_tools")
    assert panels.is_open("FRESING_PT_motion") and panels.is_open("FRESING_PT_cnc")
    assert _polls("FRESING_PT_cnc")


def test_every_fresing_panel_draws_its_own_header():
    workspaces, panels, lock = _mods()
    for name in dir(bpy.types):
        if not name.startswith("FRESING_PT_"):
            continue
        cls = getattr(bpy.types, name)
        if cls.bl_region_type == "UI" and getattr(cls, "bl_category", "") == "Fresing":
            assert "HIDE_HEADER" in cls.bl_options and "DEFAULT_CLOSED" not in cls.bl_options, name
            assert name in panels.PARENT


def test_switching_and_ticking_hides_panels_and_keeps_the_work():
    workspaces, panels, lock = _mods()
    sc = _new(GANTRY)
    from fresing_render.blender import gcode
    gcode.set_up_test_model(sc) if hasattr(gcode, "set_up_test_model") else None
    panels.open_all()
    cnc = sc.fresing.cnc
    cnc.x_joint = cnc.x_joint or "X"                             # a CNC machine is set up
    before = (cnc.x_joint, len(sc.fresing.joints), len(sc.objects))
    assert "cnc" in workspaces.in_use(sc)
    workspaces.switch(sc, "Offshore & cable laying")
    assert sc.fresing.ws_name == "Offshore & cable laying"
    assert not _polls("FRESING_PT_cnc") and not _polls("FRESING_PT_milling") and _polls("FRESING_PT_cylinders")
    assert workspaces.hidden_in_use(sc) == ["cnc"] or "cnc" in workspaces.hidden_in_use(sc)
    assert (cnc.x_joint, len(sc.fresing.joints), len(sc.objects)) == before      # hiding changes nothing
    assert workspaces.show_used(sc) and _polls("FRESING_PT_cnc")
    workspaces.set_tick(sc, "cnc", False)
    assert not _polls("FRESING_PT_cnc") and sc.fresing.ws_ticks == ""       # as the workspace says: no tick kept
    workspaces.set_tick(sc, "cnc", True)
    assert _polls("FRESING_PT_cnc")
    workspaces.set_tick(sc, "offshore", False)
    assert json.loads(sc.fresing.ws_ticks)["offshore"] is False and not _polls("FRESING_PT_cables")
    workspaces.set_tick(sc, "offshore", True)                    # back to what the workspace says: no tick kept
    assert "offshore" not in json.loads(sc.fresing.ws_ticks or "{}")
    workspaces.switch(sc, "All functions")
    assert sc.fresing.ws_ticks == "" and _polls("FRESING_PT_cables")


def test_family_toggle_asks_before_hiding_what_is_used():
    workspaces, panels, lock = _mods()
    sc = _new(GANTRY)
    sc.fresing.cnc.x_joint = "X"
    assert bpy.ops.fresing.family_toggle(family="web") == {"FINISHED"}        # not in use: no question
    assert not workspaces.family_on(sc, "web")
    uses = workspaces.in_use(sc)["cnc"]
    assert "CNC machine" in W.hide_warning("cnc", uses)
    assert bpy.ops.fresing.family_toggle(family="cnc") == {"FINISHED"}        # EXEC = the user pressed Hide anyway
    assert not workspaces.family_on(sc, "cnc") and sc.fresing.cnc.x_joint == "X"
    assert bpy.ops.fresing.workspace_show_used() == {"FINISHED"} and workspaces.family_on(sc, "cnc")
    assert bpy.ops.fresing.family_toggle(family="import") == {"CANCELLED"}    # always shown


def test_an_old_project_opens_with_everything_it_uses(tmp_path):
    workspaces, panels, lock = _mods()
    from fresing_render.blender import prefs
    sc = _new(GANTRY)
    sc.fresing.cnc.x_joint = "X"
    sc.fresing.ws_name = ""                                      # as saved by a version before workspaces
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    p = prefs.get()
    old_default = p.default_workspace if p is not None else None
    try:
        if p is not None:
            p.default_workspace = "Offshore & cable laying"
            bpy.ops.wm.open_mainfile(filepath=path)
            sc = bpy.context.scene
            assert sc.fresing.ws_name == "Offshore & cable laying"
            assert workspaces.family_on(sc, "cnc") and workspaces.hidden_in_use(sc) == []
        else:                                                    # no preferences in this run: the built-in default
            bpy.ops.wm.open_mainfile(filepath=path)
            assert bpy.context.scene.fresing.ws_name == "All functions"
    finally:
        if p is not None:
            p.default_workspace = old_default
    # a family the user hid himself stays hidden at the next open
    sc = bpy.context.scene
    workspaces.set_tick(sc, "cnc", False)
    bpy.ops.wm.save_mainfile()
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not workspaces.family_on(bpy.context.scene, "cnc")


def test_own_workspace_save_use_rename_delete_and_a_second_folder(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "CNC & machining")
    workspaces.set_tick(sc, "web", False)
    assert bpy.ops.fresing.workspace_save(name="Mill demos", note="demo days") == {"FINISHED"}
    assert sc.fresing.ws_name == "Mill demos" and sc.fresing.ws_ticks == "" and sc.fresing.ws_data
    folder = workspaces.folder()[0]
    assert os.listdir(folder) == ["Mill demos.json"]
    assert ("Mill demos", "demo days", True) in workspaces.names()
    assert not workspaces.family_on(sc, "web") and not workspaces.family_on(sc, "offshore")
    # the project keeps showing the same on a PC without the file
    other = str(tmp_path / "second" / "Workspaces")
    os.environ["FRESING_WORKSPACES_DIR"] = other
    try:
        workspaces.forget_scan()
        assert workspaces.library(force=True) == {}
        assert not workspaces.family_on(sc, "web") and workspaces.current(sc).name == "Mill demos"
        assert not workspaces.is_own("Mill demos")
        # a colleague copies the file into his folder and presses Refresh
        os.makedirs(other)
        with open(os.path.join(folder, "Mill demos.json"), "rb") as src, \
                open(os.path.join(other, "Mill demos.json"), "wb") as dst:
            dst.write(src.read())
        assert bpy.ops.fresing.workspace_refresh() == {"FINISHED"}
        assert workspaces.is_own("Mill demos")
        sc2 = _new(CRANE)
        assert bpy.ops.fresing.workspace_pick(name="Mill demos") == {"FINISHED"}
        assert not workspaces.family_on(sc2, "web") and not _polls("FRESING_PT_cables")
    finally:
        os.environ["FRESING_WORKSPACES_DIR"] = folder
        workspaces.forget_scan()
    sc = bpy.context.scene
    workspaces.switch(sc, "Mill demos")
    assert bpy.ops.fresing.workspace_rename(name="Mill demo days") == {"FINISHED"}
    assert sc.fresing.ws_name == "Mill demo days" and os.listdir(folder) == ["Mill demo days.json"]
    assert bpy.ops.fresing.workspace_delete() == {"FINISHED"}
    assert os.listdir(folder) == [] and sc.fresing.ws_name == "Mill demo days"     # the project keeps its copy
    assert not workspaces.family_on(sc, "web")
    assert bpy.ops.fresing.workspace_rename.poll() is False                        # no longer an own file
    assert bpy.ops.fresing.workspace_all() == {"FINISHED"} and workspaces.family_on(sc, "web")


def test_an_own_workspace_with_a_built_in_name_wins():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "All functions")
    workspaces.set_tick(sc, "milling", False)
    workspaces.save_own(sc, "CNC & machining")
    try:
        names = [n for n, _note, _own in workspaces.names()]
        assert names.count("CNC & machining") == 1
        sc2 = _new(CRANE)
        workspaces.switch(sc2, "CNC & machining")
        assert workspaces.current(sc2).own and not workspaces.family_on(sc2, "milling")
        assert workspaces.family_on(sc2, "offshore")             # the built-in one would hide it
    finally:
        workspaces.delete_own(bpy.context.scene, "CNC & machining")


def test_section_tabs_show_one_section_opened():
    workspaces, panels, lock = _mods()
    _new(CRANE)
    wm = bpy.context.window_manager
    wm.fresing_tab = "3"
    try:
        assert panels.tab_section() == "FRESING_PT_looks" and panels.is_open("FRESING_PT_looks")
        assert _polls("FRESING_PT_looks") and _polls("FRESING_PT_find")
        assert not _polls("FRESING_PT_motion") and not _polls("FRESING_PT_scene") and not _polls("FRESING_PT_camera")
        assert _polls("FRESING_PT_workspace") and _polls("FRESING_PT_tabs")       # the top of the tab always shows
    finally:
        wm.fresing_tab = "ALL"
    assert _polls("FRESING_PT_motion") and not panels.is_open("FRESING_PT_looks")


def test_ctrl_click_keeps_only_that_one_open_and_a_load_folds_again():
    workspaces, panels, lock = _mods()
    _new(CRANE)
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_looks") == {"FINISHED"}
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_motion") == {"FINISHED"}
    assert panels.is_open("FRESING_PT_looks") and panels.is_open("FRESING_PT_motion")
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_scene", only=True) == {"FINISHED"}
    assert panels.is_open("FRESING_PT_scene")
    assert not panels.is_open("FRESING_PT_looks") and not panels.is_open("FRESING_PT_motion")
    assert panels.is_open("FRESING_PT_camera")                   # sub-panels of other sections are left alone
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_scene") == {"FINISHED"}
    assert not panels.is_open("FRESING_PT_scene")
    panels.open_all()
    _new(CRANE)
    assert not any(panels.is_open(s) for s in panels.SECTIONS)


def test_keep_sections_as_i_left_them(tmp_path):
    workspaces, panels, lock = _mods()
    from fresing_render.blender import prefs
    p = prefs.get()
    if p is None:
        pytest.skip("no add-on preferences in this run")
    _new(CRANE)
    path = str(tmp_path / "kept.blend")
    p.keep_sections = True
    try:
        panels.open_to("FRESING_PT_cutaway")
        bpy.ops.wm.save_as_mainfile(filepath=path)
        _new()
        assert not panels.is_open("FRESING_PT_looks")
        bpy.ops.wm.open_mainfile(filepath=path)
        assert panels.is_open("FRESING_PT_looks") and panels.is_open("FRESING_PT_cutaway")
        p.keep_sections = False
        bpy.ops.wm.open_mainfile(filepath=path)
        assert not panels.is_open("FRESING_PT_looks")
    finally:
        p.keep_sections = False


def test_client_view_locks_and_full_access_unlocks(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    from fresing_render.blender import build
    parts = list(build.iter_parts(sc))
    unclickable = sum(1 for o in sc.objects if o.hide_select)   # the floor, as the app makes it
    free = parts[0]
    free.lock_location = (False, True, False)                   # something the lock must put back exactly
    free_name, rot_before = free.name, tuple(free.lock_rotation)
    excluded = parts[1]
    excluded.hide_select = True                                  # as the app's Clean-up leaves a removed part
    free.select_set(True)
    bpy.context.view_layer.objects.active = free
    assert bpy.ops.fresing.workspace_pick(name="Client view") == {"FINISHED"}
    assert lock.ON[0] and workspaces.locked(sc)
    assert all(o.hide_select and all(o.lock_location) and all(o.lock_rotation) and all(o.lock_scale)
               for o in sc.objects)
    assert not bpy.context.selected_objects and bpy.context.view_layer.objects.active is None
    # editing operators are refused, with a reason; looking and rendering still work
    assert bpy.ops.fresing.group_add.poll() is False
    assert bpy.ops.fresing.exclude_selected.poll() is False
    with pytest.raises(RuntimeError, match="Full access"):
        bpy.ops.fresing.group_add()
    assert bpy.ops.fresing.light_look.poll() and bpy.ops.fresing.workspace_pick.poll()
    assert bpy.ops.fresing.client_locked.poll()
    assert not _polls("FRESING_PT_looks") and _polls("FRESING_PT_scene")
    # a part made while locked is locked too
    bpy.ops.mesh.primitive_cube_add()
    bpy.context.view_layer.update()
    lock._after_change()
    assert all(o.hide_select for o in sc.objects)
    # saved and opened again: still locked
    path = str(tmp_path / "client.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    _new()
    assert not lock.ON[0]
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert lock.ON[0] and all(o.hide_select for o in sc.objects)
    # Full access undoes all of it, exactly
    assert bpy.ops.fresing.workspace_pick(name="Full access") == {"FINISHED"}
    assert not lock.ON[0] and lock.marked() == 0
    free = sc.objects[free_name]
    assert not free.hide_select and tuple(free.lock_location) == (False, True, False)
    assert tuple(free.lock_rotation) == rot_before
    assert sum(1 for o in sc.objects if o.hide_select) == unclickable + 1            # + the part made unclickable
    assert not bpy.ops.fresing.client_locked.poll()
    assert workspaces.blender_ui(sc) and not lock.tabs_hidden()
    assert bpy.ops.fresing.workspace_pick(name="All functions") == {"FINISHED"}
    assert lock.tabs_hidden()


def test_lock_allow_list_names_real_operators():
    workspaces, panels, lock = _mods()
    ids = {getattr(c, "bl_idname", "") for c in fresing_render._all_classes()}
    missing = sorted(i for i in lock.ALLOWED if i not in ids and i not in ("fresing.user_guide", "fresing.show_panel", "fresing.pc_check",
                                                 "fresing.pc_check_cancel"))    # registered by the template / PC check
    assert not missing, missing
    assert lock.allowed("fresing.workspace_pick") and lock.allowed("fresing.panel_toggle")
    assert not lock.allowed("fresing.joint_pick_axis") and not lock.allowed("fresing.group_remove")


def test_what_a_project_uses():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    assert workspaces.in_use(sc) == {} or "cnc" not in workspaces.in_use(sc)
    s = sc.fresing
    s.cnc.x_joint = "X"
    s.cnc.tools.add()
    a = s.animations.add()
    a.name = "Demo"
    b = a.blocks.add()
    b.kind = "GCODE"
    uses = workspaces.in_use(sc)
    assert uses["cnc"] == ["a CNC machine", "a tool", "a G-code step"]
    assert uses["animation"] == ["an animation"]
    s.cnc.tools.add()
    assert "2 tools" in workspaces.in_use(sc)["cnc"]
