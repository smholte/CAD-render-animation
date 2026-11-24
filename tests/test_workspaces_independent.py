"""Task 0062, independent tests (subagent S6): workspaces, function families, own-workspace files, the Client view's
lock, the open set and the section tabs – written from the brief (``tasks/0062-ui-clean-up.md``) by an agent that
wrote none of the code, with the job of breaking it.

A test that passes = a promise of the brief that holds. A fault = a test marked
``@FINDING(reason="FINDING n: …")``: it FAILS today and shows the fault; the file passes as a
whole while the fault is open. Fix the fault, then remove the mark (a strict xfail that starts passing fails the run).

Not testable here (Blender as a Python module has no window events): the keys the lock swallows (Delete, X, Tab,
Ctrl+Shift+S), the Outliner replaced by the Info editor, the File menu as drawn, the warning popup's two buttons,
real Ctrl+Z.
"""

import hashlib
import json
import os
import random
import shutil

import numpy as np
import pytest


def FINDING(reason):
    """A fault the independent tester found in task 0062 (these tests failed then, as strict xfails). All were
    fixed by the worker in the same task; the mark stays as the record of what each test caught."""
    return lambda fn: fn


from fresing_render.core import functions as F
from fresing_render.core import places
from fresing_render.core import workspaces as W

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
GANTRY = os.path.join(DATA, "test_gantry.step")
PATHS = os.path.join(DATA, "test_paths_a.step")

BUILT_IN = ("Essentials", "All functions", "CNC & machining", "Offshore & cable laying", "Product design & R&D",
            "Client view", "Education & training", "Lifting plans", "Sales", "Quick render", "Animator", "Reviewer",
            "Full access")      # Lifting plans: task 0201; Essentials and the task workspaces: task 0294
_BEFORE: dict = {}           # Blender as it was before the extension was registered (handlers, the patched draws)


def _handler_counts() -> dict:
    return {n: len(getattr(bpy.app.handlers, n)) for n in dir(bpy.app.handlers)
            if isinstance(getattr(bpy.app.handlers, n), list)}


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    addon_utils.enable("cycles", default_set=True)
    os.environ["FRESING_WORKSPACES_DIR"] = str(tmp_path_factory.mktemp("lib") / "Workspaces")
    _BEFORE["handlers"] = _handler_counts()
    _BEFORE["draw_left"] = bpy.types.TOPBAR_HT_upper_bar.__dict__.get("draw_left")
    _BEFORE["file_draw"] = bpy.types.TOPBAR_MT_file.__dict__.get("draw")
    fresing_render.register()
    from fresing_render.blender import prefs
    entry = None
    if prefs.get() is None:                  # the extension's preferences exist only for an enabled add-on: make its
        entry = bpy.context.preferences.addons.new()       # entry, so "default workspace", "keep sections" and the
        entry.module = prefs.ADDON_ID                      # library path can be tested as the user sets them
    yield
    try:
        _calm()
    finally:
        fresing_render.unregister()
        if entry is not None:
            try:
                bpy.context.preferences.addons.remove(entry)
            except Exception:  # noqa: BLE001
                pass
        os.environ.pop("FRESING_WORKSPACES_DIR", None)


def _mods():
    from fresing_render.blender import lock, panels, workspaces
    return workspaces, panels, lock


def _prefs():
    from fresing_render.blender import prefs
    p = prefs.get()
    assert p is not None, "the extension's preferences are not available in this run"
    return p


def _calm():
    """Back to a plain state, whatever a test (or an open fault) left behind."""
    workspaces, panels, lock = _mods()
    p = _prefs()
    p.default_workspace = ""
    p.keep_sections = False
    p.library_path = ""
    folder = os.environ["FRESING_WORKSPACES_DIR"]
    shutil.rmtree(folder, ignore_errors=True)
    workspaces.forget_scan()
    panels.show_only()
    sc = bpy.context.scene
    if sc is not None and getattr(sc, "fresing", None) is not None:
        sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks = "All functions", "", ""
        workspaces.apply(sc)
    lock.apply(sc, False)
    wm = bpy.context.window_manager
    if wm is not None and getattr(wm, "fresing_tab", "ALL") != "ALL":
        wm.fresing_tab = "ALL"


@pytest.fixture(autouse=True)
def calm():
    _calm()
    yield
    _calm()


def _new(path=None):
    bpy.ops.wm.read_homefile(use_empty=True)
    if path:
        assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


def _polls(name) -> bool:
    """Would the panel show in the app's window? Without a window (these tests) a class's own ``poll`` leaves the
    tab and the folds out – nothing is folded in a script – so ``panels.visible`` is asked with them (the worker
    made that rule after these tests were written)."""
    from fresing_render.blender import panels
    return bool(getattr(bpy.types, name).poll(bpy.context)) and panels.visible(name, bpy.context, folds=True)


def _drawn(name) -> bool:
    """Does Blender draw this panel: it shows, and so does every panel above it (Blender asks a sub-panel only
    when its parent shows; ``panels.visible`` alone says True for a sub-panel of a section the workspace hides)."""
    workspaces, panels, lock = _mods()
    while name:
        if not _polls(name):
            return False
        name = panels.PARENT.get(name, "")
    return True


def _reach(name) -> bool:
    """Can the user get to this panel: opened, it and every panel above it show?"""
    workspaces, panels, lock = _mods()
    panels.open_to(name)
    while name:
        if not _polls(name):
            return False
        name = panels.PARENT.get(name, "")
    return True


def _tab_panels() -> list:
    return sorted(n for n in dir(bpy.types) if n.startswith("FRESING_PT_")
                  and ((getattr(getattr(bpy.types, n), "bl_region_type", "") == "UI"
                        and getattr(getattr(bpy.types, n), "bl_category", "") == "Fresing")
                       or getattr(getattr(bpy.types, n), "_fr_left", False)))     # task 0260: the left panel too


def _operators() -> dict:
    return {getattr(bpy.types, n).bl_idname: n for n in dir(bpy.types) if n.startswith("FRESING_OT_")}


def _op(idname):
    mod, name = idname.split(".")
    return getattr(getattr(bpy.ops, mod), name)


def _locks() -> dict:
    """What the lock touches, per object."""
    return {o.name: (bool(o.hide_select), tuple(o.lock_location), tuple(o.lock_rotation), tuple(o.lock_scale))
            for o in bpy.data.objects}


def _project(sc) -> tuple:
    """A fingerprint of the project's work: nothing a workspace or a tick does may change it."""
    s = sc.fresing
    obs = tuple(sorted((o.name, tuple(round(v, 5) for row in o.matrix_world for v in row), bool(o.hide_render),
                        bool(o.hide_viewport)) for o in bpy.data.objects))
    return (len(s.joints), len(s.poses), len(s.groups), tuple(g.material for g in s.groups), s.cnc.x_joint,
            len(s.animations), len(s.queue), len(s.shots), obs)


def _parts(sc) -> list:
    from fresing_render.blender import build
    return sorted(str(o.get(build.PROP_NAME)) for o in build.iter_parts(sc))


def _root(sc):
    from fresing_render.blender import build
    return next(o for o in sc.objects if o.get(build.PROP_SOURCE))


# ===================================================================================================================
# own-workspace files (no project needed)
# ===================================================================================================================

def _write(folder, file, content):
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, file)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content if isinstance(content, str) else json.dumps(content))
    return path


def test_a_file_from_a_newer_version_opens_without_errors(tmp_path):
    """"A set file from a newer version opens in an older one without errors (unknown families ignored)." """
    folder = str(tmp_path)
    _write(folder, "Future.json", {
        W.MARKER: 99, "name": "Future", "note": "made by 0.9", "based_on": "robotics", "lock": False,
        "families": {"cnc": False, "robotics": True, "lifting": False, 7: True},
        "hide": ["robots.gripper", "poses.explode", {"id": "x"}, 5, None],
        "favourites": ["a", "b"], "usage": {"clicks": 12}, "blender_ui": False, "version_note": [1, 2]})
    found = W.scan(folder)
    assert list(found) == ["Future"]
    ws = found["Future"][1]
    assert ws.own and ws.families["cnc"] is False
    assert set(ws.families) == set(F.FAMILIES)               # no family of the future, none of today missing
    assert ws.hide == ("poses.explode",)                     # what this version does not know is left out
    assert ws.families["offshore"] is True                   # unknown base: a family the file does not name shows
    assert "FRESING_PT_cnc" in W.hidden_panels(ws)
    assert W.from_json(ws.to_json()).families == ws.families     # and it can be kept in a project


def test_a_file_from_an_older_version_follows_the_workspace_it_was_based_on(tmp_path):
    folder = str(tmp_path)
    _write(folder, "Old.json", {W.MARKER: 1, "name": "Old", "based_on": "offshore", "families": {"web": False}})
    ws = W.scan(folder)["Old"][1]
    base = W.builtin("offshore")
    assert ws.families["web"] is False
    for fam in W.tickable():
        if fam != "web":
            assert ws.families[fam] == base.families[fam], fam
    for fam in F.ALWAYS:
        assert ws.families[fam] is True


def test_damaged_and_foreign_files_never_stop_the_others(tmp_path):
    folder = str(tmp_path)
    _write(folder, "Good.json", {W.MARKER: 1, "name": "Good", "families": {}})
    _write(folder, "list.json", [1, 2, 3])
    _write(folder, "number.json", "5")
    _write(folder, "empty.json", "")
    _write(folder, "cut.json", '{"fresing_render_workspace": 1, "name": "Cut", "fam')
    _write(folder, "other.json", {"name": "A rule set", "rules": []})
    _write(folder, "noname.json", {W.MARKER: 1})
    _write(folder, "oddhide.json", {W.MARKER: 1, "name": "Odd", "hide": 5})
    _write(folder, "oddfam.json", {W.MARKER: 1, "name": "Odd families", "families": [1, 2]})
    with open(os.path.join(folder, "binary.json"), "wb") as fh:
        fh.write(bytes(range(256)) * 4)
    os.makedirs(os.path.join(folder, "folder.json"))
    _write(folder, "notes.txt", "hello")
    found = W.scan(folder)
    assert "Good" in found and "Cut" not in found
    assert set(found) <= {"Good", "Odd", "Odd families"}
    assert W.scan(os.path.join(folder, "does not exist")) == {} and W.scan("") == {}


def test_file_names_work_on_windows():
    bad = '<>:"/\\|?*'
    for name in ('Mill: "demos" <2026>?', "a/b\\c|d*e", "trailing dots...", "trailing space ", "CON", "nul", "com1",
                 "LPT9", "tab\tname", "new\nline", "Ünïcödé – ok", "x" * 300, "."):
        f = W.file_name(name)
        assert f.endswith(".json") and len(f) <= 70, (name, f)
        stem = f[:-5]
        assert stem and not any(ch in bad for ch in stem) and not any(ord(ch) < 32 for ch in stem), (name, f)
        assert stem == stem.rstrip(". "), (name, f)
        assert stem.upper() not in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT9"}, (name, f)
    assert W.name_problem("") and W.name_problem("   ") and W.name_problem("...")
    assert not W.name_problem("Offshore cranes")
    assert W.name_problem("offshore CRANES", existing=["Offshore cranes"])       # Windows: one file name


def test_names_windows_forbids_are_saved_under_a_safe_file_name_and_keep_their_name(tmp_path):
    folder = str(tmp_path)
    for name in ('Mill: "demos" <2026>?', "CON", "a/b"):
        ws = W.make_own(name, W.builtin("cnc"))
        path = W.save_in(folder, ws)
        assert os.path.dirname(path) == folder and os.path.isfile(path)
    found = W.scan(folder)
    assert set(found) == {'Mill: "demos" <2026>?', "CON", "a/b"}
    assert len(os.listdir(folder)) == 3                      # no stray folders, no temporary files left


def test_two_files_with_the_same_name_inside_and_a_file_named_differently(tmp_path):
    folder = str(tmp_path)
    _write(folder, "Zebra.json", {W.MARKER: 1, "name": "Cranes", "families": {"cnc": False}})
    assert list(W.scan(folder)) == ["Cranes"]                # the name inside counts, not the file's
    _write(folder, "Cranes.json", {W.MARKER: 1, "name": "Cranes", "families": {"cnc": True}})
    _write(folder, "Cranes - copy.json", {W.MARKER: 1, "name": "Cranes", "families": {"cnc": False}})
    found = W.scan(folder)
    assert list(found) == ["Cranes"] and os.path.basename(found["Cranes"][0]) == "Cranes.json"
    assert found["Cranes"][1].families["cnc"] is True        # the file whose name belongs to the name counts
    # saving it again writes its own file, never one of the copies; deleting removes only that file
    ws = found["Cranes"][1]
    ws.families["web"] = False
    assert os.path.basename(W.save_in(folder, ws)) == "Cranes.json"
    assert sorted(os.listdir(folder)) == ["Cranes - copy.json", "Cranes.json", "Zebra.json"]
    W.delete_in(folder, "Cranes")
    assert sorted(os.listdir(folder)) == ["Cranes - copy.json", "Zebra.json"]


def test_rename_never_takes_another_workspaces_name_or_file(tmp_path):
    folder = str(tmp_path)
    W.save_in(folder, W.make_own("One", W.builtin("cnc")))
    W.save_in(folder, W.make_own("Two", W.builtin("offshore")))
    with pytest.raises(ValueError):
        W.rename_in(folder, "One", "two")                    # Windows: the same file name
    with pytest.raises(ValueError):
        W.rename_in(folder, "One", "  ")
    with pytest.raises(FileNotFoundError):
        W.rename_in(folder, "Three", "Four")
    _write(folder, "Four.json", "not a workspace: somebody else's file")
    path = W.rename_in(folder, "One", "Four")                # a foreign file of that name is not overwritten
    assert os.path.basename(path) != "Four.json"
    with open(os.path.join(folder, "Four.json"), encoding="utf-8") as fh:
        assert fh.read().startswith("not a workspace")
    found = W.scan(folder)
    assert set(found) == {"Four", "Two"} and found["Four"][1].families == W.builtin("cnc").families
    assert W.rename_in(folder, "Four", "four") and set(W.scan(folder)) == {"four", "Two"}    # only the case


def test_built_in_workspaces_cannot_be_overwritten(tmp_path):
    """"Ready-made sets are built in and cannot be overwritten; an own set with the same name wins and says so." """
    folder = str(tmp_path)
    before = {k: (W.builtin(k).families, W.builtin(k).hide, W.builtin(k).lock) for k in W.BUILTIN}
    own = W.make_own("CNC & machining", W.builtin("all"), {"milling": False})
    W.save_in(folder, own)
    found = W.scan(folder)
    assert W.shadows("CNC & machining", found) and W.find("cnc & MACHINING", found).own
    assert not W.find("CNC & machining").own                 # without the file: the built-in one, untouched
    assert before == {k: (W.builtin(k).families, W.builtin(k).hide, W.builtin(k).lock) for k in W.BUILTIN}
    W.delete_in(folder, "CNC & machining")
    assert not W.find("CNC & machining", W.scan(folder)).own


def test_an_own_workspace_shows_exactly_what_showed_when_it_was_saved():
    rnd = random.Random(62)
    for key in W.BUILTIN:
        base = W.builtin(key)
        for _ in range(6):
            ticks = {f: rnd.random() < 0.5 for f in rnd.sample(W.tickable(), rnd.randint(0, 5))}
            own = W.make_own("Mine", base, ticks)
            assert W.hidden_panels(own) == W.hidden_panels(base, ticks), (key, ticks)
            back = W.from_json(own.to_json())
            assert W.hidden_panels(back) == W.hidden_panels(base, ticks), (key, ticks)
            assert back.lock == base.lock and back.blender_ui == base.blender_ui


@FINDING(reason="FINDING 13: a name longer than 60 characters whose 60th character is a space "
                                       "is cut to a name ending in a space; read back from the file it has none "
                                       "(core/workspaces.clean_name cuts after joining the words)")
def test_a_cleaned_name_stays_the_same_when_cleaned_again():
    name = "x" * 59 + " " + "y" * 20
    once = W.clean_name(name)
    assert W.clean_name(once) == once


@FINDING(reason="FINDING 15: a workspace called 'NUL.old' or 'con.cranes' gets the file "
                                       "'NUL.old.json': on Windows a reserved device name followed by an extension "
                                       "is still the device (core/workspaces.file_name tests the whole stem only)")
def test_a_reserved_windows_name_with_an_extension_gets_a_safe_file_name():
    for name in ("NUL.old", "con.cranes", "COM1.backup"):
        assert W.file_name(name).split(".")[0].upper() not in {"NUL", "CON", "COM1"}, W.file_name(name)


@FINDING(reason="FINDING 16: a workspace file saved by a Windows editor as 'UTF-8 with BOM' "
                                       "is skipped without a word (core/workspaces.load opens with utf-8, not "
                                       "utf-8-sig)")
def test_a_workspace_file_with_a_byte_order_mark_shows_up(tmp_path):
    folder = str(tmp_path)
    with open(os.path.join(folder, "Edited.json"), "w", encoding="utf-8-sig") as fh:
        json.dump({W.MARKER: 1, "name": "Edited", "families": {"cnc": False}}, fh)
    assert "Edited" in W.scan(folder)


@FINDING(reason="FINDING 14: a function whose workspaces= names a key that does not exist "
                                       "(a typing mistake) is silently hidden in that workspace: "
                                       "core/functions.problems() does not check the keys")
def test_the_precheck_names_a_misspelt_workspace_key():
    bad = F.Function(id="x.typo", title="A later lane's function", family="offshore", panel="FRESING_PT_cables",
                     workspaces=("ofshore", "education"))
    assert any("ofshore" in p for p in F.problems([bad]))


# ===================================================================================================================
# what shows: places, functions, panels, tabs
# ===================================================================================================================

def test_every_panel_of_the_tab_has_a_place_and_every_function_a_panel():
    workspaces, panels, lock = _mods()
    tab = _tab_panels()
    known = set(places.SECTIONS) | set(places.PLACES) | set(places.OTHER)
    assert [n for n in tab if n not in known] == []
    assert [n for n in list(places.SECTIONS) + list(places.PLACES) if n not in tab] == []
    assert sorted(panels.PARENT) == tab
    for name in tab:                                         # the parent the table says is the parent Blender has
        parent = getattr(getattr(bpy.types, name), "bl_parent_id", "") or ""
        assert parent == (places.PLACES[name][0] if name in places.PLACES else ""), name
    named = W.panel_families()
    assert [p for p in named if not hasattr(bpy.types, p)] == []
    # a panel no function names can never be hidden: only the notices on top may be like that (task 0230: + the Lesson
    # panel, shown only while a lesson runs or a project offers to go on with one)
    assert sorted(n for n in tab if n not in named) == ["FRESING_PT_lesson", "FRESING_PT_tour", "FRESING_PT_update"]


def test_where_gives_a_text_for_every_panel():
    for name in list(places.SECTIONS) + list(places.PLACES) + list(places.OTHER):
        text = places.where(name)
        assert text and text == places.where(name[len("FRESING_PT_"):])
        if name in places.PLACES:
            sec = places.section_of(name)
            assert text.startswith(places.SECTIONS[sec] + " > ") and text.endswith(places.PLACES[name][1])
            assert places.number_of(name) == list(places.SECTIONS).index(sec) + 1
    assert places.where("labels") == "6 Animation > Labels" and places.where("brand").startswith("6 Animation")
    assert places.where("cnc_tools", "Library") == "4 Motion > CNC machine > Tools > Library"
    with pytest.raises(KeyError):
        places.where("no_such_panel")


def test_the_built_in_workspaces_show_and_hide_what_the_brief_says():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    want = {
        "CNC & machining": (["cnc", "cnc_tools", "milling", "milling_toolpath", "clash", "waycover"],
                            ["cables", "spools", "vessel_motion"]),
        "Offshore & cable laying": (["cables", "spools", "vessel_motion", "cylinders", "weather"],
                                    ["cnc", "cnc_tools", "milling", "milling_toolpath"]),
        "Product design & R&D": (["faces", "schemes", "poses", "cutaway", "turntable", "web3d"],
                                 ["cnc", "milling", "cables", "spools", "vessel_motion"]),
        "Client view": (["import", "scene", "camera", "shots", "turntable", "output", "queue"],
                        ["structure", "cleanup", "looks", "faces", "motion", "cnc", "cables", "animation", "labels",
                         "props", "web3d"]),
        "Education & training": (["motion", "cnc", "milling", "cables", "animation", "camera"], []),
        "Lifting plans": (["lifting", "lifting_equipment", "lifting_load", "lifting_hook", "import", "structure",
                           "looks", "scene", "animation", "queue"],
                          ["cnc", "milling", "cables", "spools", "vessel_motion", "cylinders"]),    # task 0201
        "All functions": ([n[len("FRESING_PT_"):] for n in places.SECTIONS], []),
        "Full access": ([n[len("FRESING_PT_"):] for n in places.SECTIONS], []),
    }
    for name, (shown, hidden) in want.items():
        assert bpy.ops.fresing.workspace_pick(name=name) == {"FINISHED"}
        if name in ("All functions", "Full access"):         # every family plus …: nothing at all is hidden
            assert not any(workspaces.panel_hidden(sc, n) for n in panels.PARENT)
        for p in shown:
            assert _reach("FRESING_PT_" + p), (name, p)
        panels.open_all()
        for p in hidden:
            assert not _polls("FRESING_PT_" + p), (name, p)
        assert lock.ON[0] == (name == "Client view")
        assert lock.tabs_hidden() == (name != "Full access")          # Blender's own tabs: only in Full access
        patched = bpy.types.TOPBAR_HT_upper_bar.__dict__.get("draw_left") is not _BEFORE["draw_left"]
        assert patched == (name != "Full access")
    assert _project(sc)


def test_what_shows_is_what_the_workspace_and_the_tab_say_for_every_panel():
    """Under every built-in workspace and every tab: a panel shows exactly when the workspace does not hide it or
    a panel above it, and it belongs to the tab's section (the top of the tab always shows)."""
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    wm = bpy.context.window_manager
    panels.open_all()
    base = {n for n in panels.PARENT if _drawn(n)}           # with everything shown: what this project shows
    assert set(places.SECTIONS) <= base
    for name in BUILT_IN:
        workspaces.switch(sc, name)
        hidden = W.hidden_panels(workspaces.current(sc), workspaces.ticks(sc))
        for tab in ("ALL", "1", "2", "3", "4", "5", "6", "7"):
            wm.fresing_tab = tab
            panels.open_all()
            sec = list(places.SECTIONS)[int(tab) - 1] if tab != "ALL" else ""
            for n in panels.PARENT:
                above, p = [n], panels.PARENT.get(n, "")
                while p:
                    above.append(p)
                    p = panels.PARENT.get(p, "")
                expect = n in base and not any(a in hidden for a in above)
                if sec and places.section_of(n) and places.section_of(n) != sec:
                    expect = False
                if n == "FRESING_PT_next":                   # the card has its own rule: not in the Client view
                    expect = expect and not lock.ON[0]
                assert _drawn(n) == expect, (name, tab, n)
        wm.fresing_tab = "ALL"


def test_a_tab_opens_its_section_and_all_puts_the_open_set_back():
    workspaces, panels, lock = _mods()
    _new(CRANE)
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_scene") == {"FINISHED"}
    was = set(panels.OPEN)
    for i, sec in enumerate(places.SECTIONS, 1):
        assert bpy.ops.fresing.panel_tab(tab=str(i)) == {"FINISHED"}
        assert panels.tab() == str(i) and panels.is_open(sec) and _polls(sec)
        assert [s for s in places.SECTIONS if _polls(s)] == [sec]
        for top in ("FRESING_PT_workspace", "FRESING_PT_tabs", "FRESING_PT_make"):
            assert _polls(top), (i, top)
    assert bpy.ops.fresing.panel_tab(tab="nonsense") == {"FINISHED"} and panels.tab() == "ALL"
    assert set(panels.OPEN) == was and panels.is_open("FRESING_PT_scene") and not panels.is_open("FRESING_PT_looks")
    assert bpy.ops.fresing.panel_tab(tab="4") == {"FINISHED"}
    _new()                                                   # a new project starts at All again
    assert panels.tab() == "ALL" and bpy.context.window_manager.fresing_tab == "ALL"


def test_ctrl_click_works_on_every_level():
    workspaces, panels, lock = _mods()
    _new(CRANE)
    panels.open_all()
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_cnc", only=True) == {"FINISHED"}
    for sib in places.children("FRESING_PT_motion"):         # its neighbours fold, it stays open
        assert panels.is_open(sib) == (sib == "FRESING_PT_cnc"), sib
    assert all(panels.is_open(c) for c in places.children("FRESING_PT_cnc"))          # what is under it is left alone
    assert all(panels.is_open(s) for s in places.SECTIONS)                            # and the level above
    assert panels.is_open("FRESING_PT_camera") and panels.is_open("FRESING_PT_faces")  # and other sections' panels
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_cnc_tools", only=True) == {"FINISHED"}
    assert [c for c in places.children("FRESING_PT_cnc") if panels.is_open(c)] == ["FRESING_PT_cnc_tools"]
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_scene", only=True) == {"FINISHED"}
    assert [s for s in places.SECTIONS if panels.is_open(s)] == ["FRESING_PT_scene"]
    assert panels.is_open("FRESING_PT_make") and panels.is_open("FRESING_PT_cnc")     # the top and sub-panels stay
    assert bpy.ops.fresing.panel_toggle(name="FRESING_PT_no_such_panel") == {"CANCELLED"}
    assert bpy.ops.fresing.panel_toggle(name="") == {"CANCELLED"}


def test_sections_are_folded_after_every_load_and_sub_panels_as_their_class_says(tmp_path):
    workspaces, panels, lock = _mods()
    _new(CRANE)
    start = set(panels.OPEN)
    assert not any(panels.is_open(s) for s in places.SECTIONS)
    path = str(tmp_path / "p.blend")
    panels.open_all()
    bpy.ops.wm.save_as_mainfile(filepath=path)
    assert bpy.context.scene.fresing.panels_open == ""       # without the preference nothing is kept in the project
    for load in (lambda: bpy.ops.wm.open_mainfile(filepath=path), lambda: _new(), lambda: _new(CRANE)):
        panels.open_all()
        load()
        assert set(panels.OPEN) == start
        assert not any(panels.is_open(s) for s in places.SECTIONS)


def test_keep_sections_as_i_left_them_on_and_off(tmp_path):
    workspaces, panels, lock = _mods()
    p = _prefs()
    _new(CRANE)
    path = str(tmp_path / "kept.blend")
    p.keep_sections = True
    panels.open_to("FRESING_PT_cnc_tools")
    panels.set_open("FRESING_PT_camera", False)
    left = set(panels.OPEN)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    _new()
    assert not panels.is_open("FRESING_PT_motion")
    bpy.ops.wm.open_mainfile(filepath=path)
    assert set(panels.OPEN) == left and panels.is_open("FRESING_PT_cnc_tools")
    assert not panels.is_open("FRESING_PT_camera")
    # a saved set that names a panel this version does not have (a newer version, a removed panel)
    sc = bpy.context.scene
    sc.fresing.panels_open = "FRESING_PT_from_the_future,FRESING_PT_looks,,  ,FRESING_PT_cutaway"
    panels.on_load(sc)
    assert set(panels.OPEN) == {"FRESING_PT_looks", "FRESING_PT_cutaway"}
    # the preference off again: folded at the next open, and the next save keeps nothing
    p.keep_sections = False
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not any(panels.is_open(s) for s in places.SECTIONS)
    bpy.ops.wm.save_mainfile()
    assert bpy.context.scene.fresing.panels_open == ""


@FINDING(reason="FINDING 17: with 'Keep sections as I left them' a project saved with "
                                       "everything folded opens with the default sub-panels and Make open again "
                                       "(an empty saved set reads as 'nothing saved': panels.on_load / on_save)")
def test_keep_sections_also_keeps_everything_folded(tmp_path):
    workspaces, panels, lock = _mods()
    p = _prefs()
    _new(CRANE)
    p.keep_sections = True
    for name in list(panels.OPEN):
        assert bpy.ops.fresing.panel_toggle(name=name) == {"FINISHED"}
    assert not panels.OPEN
    path = str(tmp_path / "folded.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    _new()
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not panels.is_open("FRESING_PT_make") and not panels.OPEN


def test_make_lists_only_outputs_whose_settings_can_be_shown():
    """A Make button opens the output's own settings panel as a popover: never one for an output the workspace
    hides, and every listed popover exists whatever is folded."""
    workspaces, panels, lock = _mods()
    from fresing_render.blender import ui_top
    sc = _new(CRANE)
    family = {"still": "scene", "turn": "scene", "queue": "queue", "web": "web", "anim": "animation",
              "product": "animation"}
    for name in BUILT_IN:
        workspaces.switch(sc, name)
        if W.key_of(name) in F.TASK_WORKSPACES:      # task 0294: a list of functions – an output shows when its
            listed = {o[0] for o in ui_top._outputs(sc)}         # function is on the list, whatever its family
            for key, _text, _icon, _popover, fid, _op_id, _t in ui_top.OUTPUTS:
                assert (key in listed) == (fid in F.TASK_WORKSPACES[W.key_of(name)]), (name, key)
            continue
        for fam in [None] + W.tickable():
            if fam is not None:
                workspaces.set_tick(sc, fam, not workspaces.family_on(sc, fam))
            listed = {o[0] for o in ui_top._outputs(sc)}
            for key, _text, _icon, popover, _fid, _op_id, _t in ui_top.OUTPUTS:
                assert hasattr(bpy.types, popover)
                assert (key in listed) == workspaces.family_on(sc, family[key]), (name, fam, key)
            if fam is not None:
                workspaces.set_tick(sc, fam, not workspaces.family_on(sc, fam))
    workspaces.switch(sc, "Client view")                     # what the Client view lists still works under its lock
    for o in ui_top._outputs(sc):
        if o[5]:
            assert lock.allowed(o[5]), o[5]
    # folded or not: a popover's panel is always there to be drawn
    panels.fold_sections()
    for cls in ui_top.POPOVERS:
        poll = getattr(cls, "poll", None)
        assert poll is None or poll(bpy.context), cls.__name__


@FINDING(reason="FINDING 6: with 'Motion' ticked off the whole section 4 Motion goes, and with "
                                       "it CNC machine, Milling, Cylinders, Cables … although their families are "
                                       "ticked on and in use; no 'in use but hidden' note (a sub-panel cannot show "
                                       "without its parent: core/workspaces.hidden_panels looks at each panel alone)")
def test_a_ticked_family_can_be_reached_when_the_family_of_its_section_is_off():
    workspaces, panels, lock = _mods()
    sc = _new(GANTRY)
    sc.fresing.cnc.x_joint = "X"                             # a CNC machine is set up
    workspaces.set_tick(sc, "motion", False)
    assert workspaces.family_on(sc, "cnc") and workspaces.family_on(sc, "machines")
    assert _reach("FRESING_PT_cnc") and _reach("FRESING_PT_cylinders")


@FINDING(reason="FINDING 10: in the Client view the tabs 2, 3, 4 and 6 lead to an empty side "
                                       "panel: the tab row offers a section the workspace hides (ui_top."
                                       "FRESING_PT_tabs draws all eight; panels.FRESING_OT_panel_tab takes any)")
def test_no_tab_leads_to_an_empty_panel():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "Client view")
    for i in range(1, 8):
        bpy.ops.fresing.panel_tab(tab=str(i))
        assert panels.tab() != str(i) or any(_polls(s) for s in places.SECTIONS), f"tab {i} shows no section"


# ===================================================================================================================
# hiding never deletes or switches off anything
# ===================================================================================================================

def _hide_a_lot(sc):
    workspaces, panels, lock = _mods()
    workspaces.switch(sc, "Product design & R&D")            # hides cables, drums, the sea, CNC, milling
    for fam in ("motion", "animation", "machines", "video", "queue", "web"):
        workspaces.set_tick(sc, fam, False)


def _client(sc):
    _mods()[0].switch(sc, "Client view")


def _bake_fingerprint(prep) -> str:
    from fresing_render.blender import animation, paths
    sc = _new(PATHS)
    made = paths.set_up_test_model(sc)                       # a luffing A-frame, a wire rope over sheaves, a video
    prep(sc)
    animation.bake(sc, sc.fresing.animations[made["animation"]])
    h = hashlib.sha1()
    dg = bpy.context.evaluated_depsgraph_get()
    for frame in (sc.frame_start, (sc.frame_start + sc.frame_end) // 2, sc.frame_end):
        sc.frame_set(frame)
        bpy.context.view_layer.update()
        for ob in sorted(sc.objects, key=lambda o: o.name):
            h.update(ob.name.encode())
            h.update(np.array(ob.matrix_world, np.float32).round(5).tobytes())
            h.update(bytes((ob.hide_render, ob.hide_viewport)))
            if ob.type == "MESH" and ob.modifiers:           # the cable's drawn tube
                me = ob.evaluated_get(dg).to_mesh()
                co = np.empty(len(me.vertices) * 3, np.float32)
                me.vertices.foreach_get("co", co)
                h.update(co.round(5).tobytes())
                ob.evaluated_get(dg).to_mesh_clear()
    assert sc.fresing.anim_baked == made["animation"] and len(sc.fresing.cables) == 1
    return h.hexdigest()


def test_build_gives_the_same_animation_with_its_families_hidden_and_in_the_client_view():
    shown = _bake_fingerprint(lambda sc: None)
    assert _bake_fingerprint(lambda sc: None) == shown       # the measure itself is stable
    assert _bake_fingerprint(_hide_a_lot) == shown
    assert _bake_fingerprint(_client) == shown


def _picture(prep, path) -> np.ndarray:
    from fresing_render.blender import cameras, joints, render
    from mathutils import Vector
    sc = _new(CRANE)
    s = sc.fresing
    boom = next(o for o in sc.objects if "BOOM" in o.name and o.type == "MESH")
    j = joints.create(sc, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)), name="Boom")
    joints.set_value(j, 0.3)
    s.background = "QUAY" if "QUAY" in [i.identifier for i in s.bl_rna.properties["background"].enum_items] else "SKY"
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 64, 36
    s.use_gpu = False
    cameras.add_camera(sc)
    prep(sc)
    render.render_still(sc, s, "draft", filepath=path)
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px


def test_a_render_is_the_same_with_families_hidden_and_in_the_client_view(tmp_path):
    shown = _picture(lambda sc: None, str(tmp_path / "shown.png"))
    assert shown.std() > 0.01
    assert np.array_equal(_picture(_hide_a_lot, str(tmp_path / "hidden.png")), shown)
    assert np.array_equal(_picture(_client, str(tmp_path / "client.png")), shown)


def _updated(prep) -> tuple:
    from fresing_render.blender import joints, states
    from mathutils import Vector
    sc = _new(CRANE)
    boom = next(o for o in sc.objects if "BOOM" in o.name and o.type == "MESH")
    j = joints.create(sc, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)), name="Boom")
    joints.set_value(j, 0.25)
    states.save_pose(sc, "Up")
    prep(sc)
    root = _root(sc).name
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root) == {"FINISHED"}
    bpy.context.view_layer.update()
    s = sc.fresing
    return (_parts(sc), [(x.name, x.kind) for x in s.joints], [p.name for p in s.poses], s.report_title,
            len(s.report_new), len(s.report_missing), [g.name for g in s.groups],
            sorted((o.name, tuple(round(v, 5) for row in o.matrix_world for v in row)) for o in sc.objects))


def test_a_model_update_gives_the_same_result_with_its_families_hidden():
    def hide(sc):
        workspaces = _mods()[0]
        workspaces.switch(sc, "CNC & machining")
        for fam in ("motion", "machines", "animation"):
            workspaces.set_tick(sc, fam, False)
    shown = _updated(lambda sc: None)
    assert shown[1] == [("Boom", "ROTATE")] and shown[2] == ["Up"]
    assert _updated(hide) == shown


def test_the_queue_gets_the_same_job_with_families_hidden_and_in_the_client_view():
    from fresing_render.blender import cameras

    def job(prep):
        sc = _new(CRANE)
        cameras.add_camera(sc)
        prep(sc)
        assert bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}
        s = sc.fresing
        assert len(s.queue) == 1
        j = s.queue[0]
        return (j.kind, j.quality, j.status, j.watermark, j.scheme, len(s.shots), sc.camera.name)
    shown = job(lambda sc: None)
    assert job(_hide_a_lot) == shown                         # also with the Render queue's own family ticked off
    assert job(_client) == shown


def test_poses_and_saved_scenes_work_the_same_with_motion_hidden_and_in_the_client_view():
    from fresing_render.blender import joints, states
    from mathutils import Vector

    def run(prep):
        sc = _new(CRANE)
        boom = next(o for o in sc.objects if "BOOM" in o.name and o.type == "MESH")
        j = joints.create(sc, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)),
                          name="Boom")
        joints.set_value(j, 0.4)
        states.save_pose(sc, "Up")
        states.save_shot(sc, "Boom up", pose="Up")
        joints.set_value(joints.find(sc, "Boom"), 0.0)
        prep(sc)
        assert bpy.ops.fresing.shot_apply(name="Boom up") == {"FINISHED"}      # a saved scene: also in the Client view
        bpy.context.view_layer.update()
        bpy.context.view_layer.update()
        return (round(joints.get_value(joints.find(sc, "Boom")), 5),
                tuple(round(v, 4) for row in boom.matrix_world for v in row))
    shown = run(lambda sc: None)
    assert shown[0] == 0.4
    assert run(_hide_a_lot) == shown
    assert run(_client) == shown


# ===================================================================================================================
# switching, ticking, own workspaces: at any time, as often as the user likes
# ===================================================================================================================

def test_random_switching_ticking_saving_never_changes_the_project_and_the_panel_follows(tmp_path):
    workspaces, panels, lock = _mods()
    from fresing_render.blender import joints, states
    from mathutils import Vector
    sc = _new(CRANE)
    boom = next(o for o in sc.objects if "BOOM" in o.name and o.type == "MESH")
    joints.create(sc, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0.0, 1.0, 0.0)), name="Boom")
    states.save_pose(sc, "Rest")
    sc.fresing.cnc.x_joint = "Boom"
    a_part = next(o for o in sc.objects if o.type == "MESH" and o is not boom)
    a_part.lock_location = (False, True, False)              # something only the user set: must come back exactly
    a_part_name = a_part.name
    bpy.context.view_layer.update()
    path = str(tmp_path / "random.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc = bpy.context.scene
    panels.open_all()
    base = {n for n in panels.PARENT if _drawn(n)}
    project, locks = _project(sc), _locks()
    rnd = random.Random(2026)
    own_names = ["Offshore cranes", "Mill demos", "Sales – Ünïcode", "x" * 80]
    log = []

    def check():
        sc = bpy.context.scene
        ws = workspaces.current(sc)
        ticks = workspaces.ticks(sc)
        hidden = W.hidden_panels(ws, ticks)
        panels.open_all()
        for n in panels.PARENT:
            above, p = [n], panels.PARENT.get(n, "")
            while p:
                above.append(p)
                p = panels.PARENT.get(p, "")
            expect = n in base and not any(x in hidden for x in above)
            if n == "FRESING_PT_next":
                expect = expect and not ws.lock
            assert _drawn(n) == expect, (log[-6:], n)
        for fam in W.tickable():
            assert workspaces.family_on(sc, fam) == W.effective_families(ws, ticks)[fam], (log[-6:], fam)
        assert lock.ON[0] == bool(ws.lock) == workspaces.locked(sc), log[-6:]
        assert lock.marked() == (len(bpy.data.objects) if ws.lock else 0), log[-6:]
        assert lock.tabs_hidden() == (not ws.blender_ui), log[-6:]
        assert bpy.ops.fresing.workspace_pick.poll() and bpy.ops.fresing.family_toggle.poll()
        if ws.lock:
            assert all(o.hide_select and all(o.lock_location) for o in bpy.data.objects), log[-6:]
            assert not bpy.ops.fresing.pose_save.poll(), log[-6:]
        else:
            assert _locks() == locks, log[-6:]
        assert _project(sc) == project, log[-6:]

    for step in range(90):
        sc = bpy.context.scene
        kind = rnd.choice(["pick", "pick", "tick", "tick", "tick", "save", "rename", "delete", "used", "all", "undo",
                           "file", "refresh"])
        if kind == "pick":
            name = rnd.choice([n for n, _note, _own in workspaces.names()])
            assert bpy.ops.fresing.workspace_pick(name=name) == {"FINISHED"}
            assert sc.fresing.ws_name == name and sc.fresing.ws_ticks == ""
            log.append(("pick", name))
        elif kind == "tick":
            fam = rnd.choice(W.tickable())
            was = workspaces.family_on(sc, fam)
            assert bpy.ops.fresing.family_toggle(family=fam) == {"FINISHED"}       # EXEC = "Hide anyway"
            assert workspaces.family_on(sc, fam) != was
            log.append(("tick", fam))
        elif kind == "save":
            name = rnd.choice(own_names)
            assert bpy.ops.fresing.workspace_save(name=name, note="random") == {"FINISHED"}
            assert sc.fresing.ws_name == W.clean_name(name) and workspaces.is_own(sc.fresing.ws_name)
            log.append(("save", name[:20]))
        elif kind == "rename" and bpy.ops.fresing.workspace_rename.poll():
            new = rnd.choice(["Renamed", "Renamed again", "Third name"])
            if not workspaces.is_own(new):
                old_file = workspaces.library(force=True)[sc.fresing.ws_name][0]
                assert bpy.ops.fresing.workspace_rename(name=new) == {"FINISHED"}
                assert sc.fresing.ws_name == new and workspaces.is_own(new) and not os.path.exists(old_file)
                log.append(("rename", new))
        elif kind == "delete" and bpy.ops.fresing.workspace_delete.poll():
            name = sc.fresing.ws_name
            assert bpy.ops.fresing.workspace_delete() == {"FINISHED"}
            assert not workspaces.is_own(name) and sc.fresing.ws_name == name      # the project keeps its copy
            log.append(("delete", name[:20]))
        elif kind == "used":
            assert bpy.ops.fresing.workspace_show_used() == {"FINISHED"}
            assert workspaces.hidden_in_use(sc) == []
            log.append(("used",))
        elif kind == "all":
            assert bpy.ops.fresing.workspace_all() == {"FINISHED"}
            assert sc.fresing.ws_name == "All functions" and not W.hidden_panels(workspaces.current(sc))
            log.append(("all",))
        elif kind == "undo":
            workspaces._after_undo()                         # nothing to put right: nothing may change
            log.append(("undo",))
        elif kind == "file":
            bpy.ops.wm.save_mainfile()
            if rnd.random() < 0.5:
                _new()                                       # another project in between: unlocked, all shown
                assert not lock.ON[0] and lock.marked() == 0
            bpy.ops.wm.open_mainfile(filepath=path)
            assert not any(panels.is_open(s) for s in places.SECTIONS)
            log.append(("file",))
        elif kind == "refresh":
            assert bpy.ops.fresing.workspace_refresh() == {"FINISHED"}
            log.append(("refresh",))
        check()
    assert len({entry[0] for entry in log}) >= 9             # the run did try every kind of thing
    assert bpy.ops.fresing.workspace_pick(name="Full access") == {"FINISHED"}
    assert _locks() == locks and lock.marked() == 0
    assert all("fr_cv" not in o for o in bpy.data.objects)
    assert tuple(bpy.data.objects[a_part_name].lock_location) == (False, True, False)


def test_a_family_the_user_hid_stays_hidden_and_one_click_shows_everything(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(GANTRY)
    sc.fresing.cnc.x_joint = "X"
    assert "cnc" in workspaces.in_use(sc)
    text = W.hide_warning("cnc", workspaces.in_use(sc)["cnc"])
    assert "a CNC machine" in text and "stay" in text and "only the panels are hidden" in text
    assert bpy.ops.fresing.family_toggle(family="cnc") == {"FINISHED"}             # Hide anyway
    assert workspaces.hidden_in_use(sc) == ["cnc"] and sc.fresing.cnc.x_joint == "X"
    path = str(tmp_path / "hid.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    _new()
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert not workspaces.family_on(sc, "cnc") and not _reach("FRESING_PT_cnc")    # his choice: still hidden
    assert workspaces.hidden_in_use(sc) == ["cnc"]                                 # … and the panel can say so
    assert bpy.ops.fresing.workspace_all() == {"FINISHED"}                         # one click shows everything
    assert _reach("FRESING_PT_cnc") and sc.fresing.cnc.x_joint == "X" and sc.fresing.ws_ticks == ""
    for fam in ("import", "looks", "scene", "help", "panel", "no such family", ""):
        assert bpy.ops.fresing.family_toggle(family=fam) == {"CANCELLED"}
        assert sc.fresing.ws_ticks == ""


def test_an_old_project_opens_in_the_default_workspace_with_every_family_it_uses(tmp_path):
    workspaces, panels, lock = _mods()
    p = _prefs()
    sc = _new(GANTRY)
    s = sc.fresing
    s.cnc.x_joint = "X"
    s.cables.add()
    s.callouts.add()
    s.ws_name = ""                                           # as saved by a version before workspaces
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    for default in ("Product design & R&D", "Offshore & cable laying", "CNC & machining"):
        p.default_workspace = default
        bpy.ops.wm.open_mainfile(filepath=path)
        sc = bpy.context.scene
        assert sc.fresing.ws_name == default
        assert workspaces.hidden_in_use(sc) == []
        for panel in ("FRESING_PT_cnc", "FRESING_PT_cables", "FRESING_PT_labels"):
            assert _reach(panel), (default, panel)
    p.default_workspace = "A workspace that is gone"         # the default was deleted: the built-in default
    bpy.ops.wm.open_mainfile(filepath=path)
    assert bpy.context.scene.fresing.ws_name == "All functions"
    # a new project starts in the default workspace too, with nothing ticked
    p.default_workspace = "Offshore & cable laying"
    sc = _new(CRANE)
    assert sc.fresing.ws_name == "Offshore & cable laying" and sc.fresing.ws_ticks == ""
    assert not _reach("FRESING_PT_cnc") and _reach("FRESING_PT_cables")


@FINDING(reason="FINDING 5: an old project that uses way covers opens in 'Offshore & cable "
                                       "laying' (or Product design) without its Way covers panel, and no 'in use but "
                                       "hidden' note or Show button brings it: the workspace hides the function "
                                       "inside a family that shows (blender/workspaces.hidden_in_use and show_used "
                                       "look at whole families only)")
def test_an_old_project_shows_a_function_it_uses_that_its_workspace_hides_inside_a_shown_family(tmp_path):
    workspaces, panels, lock = _mods()
    p = _prefs()
    sc = _new(GANTRY)
    sc.fresing.waycovers.add()
    assert "machines" in workspaces.in_use(sc)
    sc.fresing.ws_name = ""
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    p.default_workspace = "Offshore & cable laying"
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    if not _reach("FRESING_PT_waycover"):
        workspaces.show_used(sc)                             # "Show what the project uses"
    assert _reach("FRESING_PT_waycover")


@FINDING(reason="FINDING 5: an old project with weather switched on opens in 'CNC & "
                                       "machining' (or Product design) without 5 Scene & Render > Weather & time: "
                                       "its weather shows in every render and the panel that changes it cannot be "
                                       "shown by any tick (blender/workspaces.in_use does not know the weather; the family "
                                       "'scene' has no tick)")
def test_an_old_project_with_weather_shows_the_weather_panel(tmp_path):
    workspaces, panels, lock = _mods()
    p = _prefs()
    sc = _new(CRANE)
    sc.fresing.weather.enabled = True
    sc.fresing.ws_name = ""
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    p.default_workspace = "CNC & machining"
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.fresing.weather.enabled
    if not _reach("FRESING_PT_weather"):
        workspaces.show_used(sc)
    assert _reach("FRESING_PT_weather")


@FINDING(reason="FINDING 3: the user's 'workspace for new projects' leaks into the projects "
                                       "the app makes itself: with 'Offshore & cable laying' as default the test "
                                       "tour's milling project is saved in it, 4 Motion > Milling hidden – the stop "
                                       "points at a panel that is not there (tour._fresh sets the default template "
                                       "aside but not the default workspace; workspaces.ensure runs on the empty "
                                       "project, before the set-up; the demo, the self-test and the PC check start "
                                       "the same way)")
def test_a_test_tour_project_shows_what_it_teaches_whatever_the_default_workspace(tmp_path):
    workspaces, panels, lock = _mods()
    from fresing_render.blender import tour
    _prefs().default_workspace = "Offshore & cable laying"
    res = tour.build_all(str(tmp_path / "tour"), only=("mill",))
    assert not res["errors"]
    bpy.ops.wm.open_mainfile(filepath=res["files"]["mill"])
    sc = bpy.context.scene
    assert "milling" in workspaces.in_use(sc)
    assert workspaces.hidden_in_use(sc) == [] and _reach("FRESING_PT_milling")


@FINDING(reason="FINDING 3: with the Client view as 'workspace for new projects' the PC "
                                       "check's own new projects are locked: its lines call fresing.camera_add, "
                                       "block_add, mill_add_bit, product_video, queue_schemes … and each is refused "
                                       "('Client view: the project is locked'); the tour and demo projects are made "
                                       "and saved locked (pccheck/runner.Context.fresh, tour._fresh, demo.py)")
def test_the_pc_checks_own_projects_are_not_locked_by_the_default_workspace(tmp_path):
    workspaces, panels, lock = _mods()
    from fresing_render.pccheck import runner
    _prefs().default_workspace = "Client view"
    ctx = runner.Context(str(tmp_path / "work"), str(tmp_path / "hist"), None)
    sc = ctx.fresh(CRANE)
    assert sc.fresing.model_count == 1
    assert not lock.ON[0] and bpy.ops.fresing.camera_add.poll()


@FINDING(reason="FINDING 8: a template does not carry the workspace or the family ticks "
                                       "(the brief, point 1: 'Saved with the project and in templates'): "
                                       "ops_main._template_from_scene / apply_template know nothing of them")
def test_a_template_carries_the_workspace_and_the_ticks(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "Offshore & cable laying")
    workspaces.set_tick(sc, "web", False)
    path = str(tmp_path / "offshore template.json")
    assert bpy.ops.fresing.template_export(filepath=path) == {"FINISHED"}
    sc = _new(CRANE)
    assert sc.fresing.ws_name == "All functions"
    assert bpy.ops.fresing.template_import(filepath=path) == {"FINISHED"}
    assert sc.fresing.ws_name == "Offshore & cable laying" and not workspaces.family_on(sc, "web")


def test_a_template_changes_nothing_of_what_shows_and_loads_the_same_with_looks_out_of_sight(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    s = sc.fresing
    s.background = "SKY"
    path = str(tmp_path / "t.json")
    assert bpy.ops.fresing.template_export(filepath=path) == {"FINISHED"}
    with open(path, encoding="utf-8") as fh:                 # a template from before workspaces (finding 8 made
        d = json.load(fh)                                    # templates carry the workspace: such a one is applied)
    d.pop("workspace", None)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(d, fh)

    def load(prep):
        sc = _new(CRANE)
        prep(sc)
        was = (sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks)
        assert bpy.ops.fresing.template_import(filepath=path) == {"FINISHED"}
        assert (sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks) == was
        return (sc.fresing.background, [(g.name, g.material) for g in sc.fresing.groups], sc.fresing.rule_set)
    shown = load(lambda sc: None)
    assert shown[0] == "SKY"
    assert load(_hide_a_lot) == shown
    sc = _new(CRANE)
    workspaces.switch(sc, "Client view")                     # loading a template is an edit: not in the Client view
    assert not bpy.ops.fresing.template_import.poll()


def test_own_workspaces_through_the_buttons_with_awkward_names(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    folder = workspaces.folder()[0]
    assert not os.path.isdir(folder) and workspaces.library(force=True) == {}      # a folder that does not exist yet
    workspaces.switch(sc, "CNC & machining")
    workspaces.set_tick(sc, "web", False)
    awkward = 'Mill: "demos" <2026>?'
    assert bpy.ops.fresing.workspace_save(name=awkward) == {"FINISHED"}
    assert sc.fresing.ws_name == awkward and workspaces.is_own(awkward) and not workspaces.changed(sc)
    assert len(os.listdir(folder)) == 1
    hidden = W.hidden_panels(workspaces.current(sc))
    assert "FRESING_PT_web3d" in hidden and "FRESING_PT_cables" in hidden
    with pytest.raises(RuntimeError):                        # no name: refused, with a reason
        bpy.ops.fresing.workspace_save(name="   ")
    long = "A very long name " * 20
    assert bpy.ops.fresing.workspace_save(name=long) == {"FINISHED"}
    assert sc.fresing.ws_name == W.clean_name(long) and len(sc.fresing.ws_name) <= 60
    assert workspaces.is_own(sc.fresing.ws_name) and len(os.listdir(folder)) == 2
    assert bpy.ops.fresing.workspace_save(name=long) == {"FINISHED"}               # again: replaces, no second file
    assert len(os.listdir(folder)) == 2
    with pytest.raises(RuntimeError):                        # renaming to a name that exists: refused
        bpy.ops.fresing.workspace_rename(name=awkward)
    assert sc.fresing.ws_name == W.clean_name(long) and len(os.listdir(folder)) == 2
    assert bpy.ops.fresing.workspace_rename(name="Short") == {"FINISHED"}
    assert sc.fresing.ws_name == "Short" and sorted(workspaces.library(force=True)) == [awkward, "Short"]
    assert W.hidden_panels(workspaces.current(sc)) == hidden                       # still shows the same
    assert [n for n, _note, own in workspaces.names() if own] == [awkward, "Short"]
    assert [n for n, _note, own in workspaces.names() if not own] == list(BUILT_IN)


def test_a_folder_that_cannot_be_written_says_so_and_changes_nothing(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    blocker = tmp_path / "a file, not a folder"
    blocker.write_text("x")
    was_env = os.environ["FRESING_WORKSPACES_DIR"]
    os.environ["FRESING_WORKSPACES_DIR"] = str(blocker / "Workspaces")
    try:
        workspaces.forget_scan()
        workspaces.set_tick(sc, "web", False)
        was = (sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks)
        with pytest.raises(RuntimeError, match="Not a directory|cannot|denied|exists"):
            bpy.ops.fresing.workspace_save(name="Nope")
        assert (sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks) == was
        assert workspaces.library(force=True) == {} and len(workspaces.names()) == len(BUILT_IN)
        assert bpy.ops.fresing.workspace_refresh() == {"FINISHED"}
        assert not bpy.ops.fresing.workspace_rename.poll() and not bpy.ops.fresing.workspace_delete.poll()
        assert _reach("FRESING_PT_cnc")                      # the panel still draws and shows
    finally:
        os.environ["FRESING_WORKSPACES_DIR"] = was_env
        workspaces.forget_scan()


def test_the_shared_library_of_the_preferences_and_the_test_folder(tmp_path, monkeypatch):
    """Task 0272: the Workspaces folders come from Fresing Settings > Locations – a fresh user's ready-made folder
    under Documents\\Fresing Render\\Library; a folder on a dead share is never saved into (nothing made there);
    once it is back it is used; the test folder wins over all of it."""
    from fresing_render.blender import locations
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    env = os.environ.pop("FRESING_WORKSPACES_DIR")
    monkeypatch.setenv(locations.ENV, str(tmp_path / "loc" / "fresing_locations.json"))
    monkeypatch.setattr(locations, "documents", lambda: str(tmp_path / "Docs"))
    locations.forget()
    try:
        workspaces.forget_scan()
        path, shared, problem = workspaces.folder(fresh=True)
        assert not shared and not problem and path.endswith(os.path.join("Fresing Render", "Library", "Workspaces"))
        lib = tmp_path / "shared library"
        locations.set_mine_root(str(lib / "deeper"))
        locations.wait_reach()
        path, shared, problem = workspaces.folder(fresh=True)
        assert path == "" and "No folder for workspaces" in problem
        assert workspaces.library(force=True) == {} and len(workspaces.names()) == len(BUILT_IN)
        with pytest.raises(RuntimeError, match="No folder for workspaces"):
            bpy.ops.fresing.workspace_save(name="Lib one")
        assert not lib.exists() and sc.fresing.ws_name == "All functions"          # nothing made on a dead share
        (lib / "deeper").mkdir(parents=True)
        locations.REACH.forget()
        locations._WRITABLE.clear()
        locations.wait_reach()
        assert workspaces.folder(fresh=True) == (str(lib / "deeper" / "Workspaces"), False, "")
        assert bpy.ops.fresing.workspace_save(name="Lib one") == {"FINISHED"}
        assert os.listdir(lib / "deeper" / "Workspaces") == ["Lib one.json"] and workspaces.is_own("Lib one")
        os.environ["FRESING_WORKSPACES_DIR"] = env           # the test folder wins over the locations
        workspaces.forget_scan()
        assert workspaces.folder()[0] == env and not workspaces.is_own("Lib one")
        assert workspaces.current(sc).name == "Lib one"      # the project keeps its copy without the file
    finally:
        os.environ["FRESING_WORKSPACES_DIR"] = env
        locations.forget()
        workspaces.forget_scan()


def test_a_deleted_workspace_stays_in_the_projects_that_use_it(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "Offshore & cable laying")
    workspaces.set_tick(sc, "web", False)
    workspaces.save_own(sc, "Cranes")
    hidden = W.hidden_panels(workspaces.current(sc))
    path = str(tmp_path / "uses.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    assert bpy.ops.fresing.workspace_delete() == {"FINISHED"}
    assert not bpy.ops.fresing.workspace_delete.poll()       # a second Delete has nothing to delete
    _new()
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.fresing.ws_name == "Cranes" and W.hidden_panels(workspaces.current(sc)) == hidden
    assert not workspaces.is_own("Cranes") and "Cranes" not in [n for n, _n, _o in workspaces.names()]
    assert not _reach("FRESING_PT_web3d") and _reach("FRESING_PT_cables")
    # a file changed by another project: this project keeps what it had until the workspace is picked again
    workspaces.save_own(sc, "Cranes")
    sc2 = _new(CRANE)
    workspaces.switch(sc2, "Cranes")
    workspaces.set_tick(sc2, "offshore", False)
    workspaces.save_own(sc2, "Cranes")
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert workspaces.family_on(sc, "offshore")              # its own copy (as the Rename tooltip says)
    assert bpy.ops.fresing.workspace_pick(name="Cranes") == {"FINISHED"}
    assert not workspaces.family_on(sc, "offshore")          # picked again: the file as it is now


@FINDING(reason="FINDING 13: renaming an own workspace to a long name whose 60th character "
                                       "is a space leaves the project with a name ending in a space that is not "
                                       "the file's: Rename and Delete go grey for it (blender/workspaces.rename_own "
                                       "+ core clean_name)")
def test_rename_to_a_long_name_keeps_the_project_on_its_workspace():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.save_own(sc, "Short")
    assert bpy.ops.fresing.workspace_rename(name="x" * 59 + " " + "y" * 20) == {"FINISHED"}
    assert workspaces.is_own(sc.fresing.ws_name) and bpy.ops.fresing.workspace_rename.poll()


@FINDING(reason="FINDING 4: an own workspace may be called 'All functions' – then 'Show "
                                       "everything' (and the fall-back for new projects) uses it instead of the "
                                       "built-in one and no longer shows everything (ops_workspace.workspace_all and "
                                       "workspaces.default_name find the own one first)")
def test_show_everything_shows_everything_also_with_an_own_workspace_called_all_functions():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "Offshore & cable laying")
    with pytest.raises(RuntimeError, match="app's own workspace"):                 # the fix: the name is the app's
        bpy.ops.fresing.workspace_save(name="All functions")
    folder = workspaces.folder()[0]                                                # … and a file a colleague sent
    os.makedirs(folder, exist_ok=True)                                             # under that name changes nothing
    own = W.make_own("Somebody's", workspaces.current(sc))
    own.name = "All functions"
    with open(os.path.join(folder, "All functions.json"), "w", encoding="utf-8") as fh:
        json.dump(own.to_dict(), fh)
    try:
        workspaces.library(force=True)
        assert bpy.ops.fresing.workspace_all() == {"FINISHED"}                     # "one click shows everything"
        assert _reach("FRESING_PT_milling") and _reach("FRESING_PT_cnc")
        assert [n for n, _note, own_ in workspaces.names() if n == "All functions"] == ["All functions"]
        assert not workspaces.is_own("All functions")
    finally:
        os.remove(os.path.join(folder, "All functions.json"))
        workspaces.forget_scan()


@FINDING(reason="FINDING 4: 'Save as my own…' in the Client view under the name 'Full "
                                       "access' makes a locked workspace that takes the built-in one's place in the "
                                       "list: picking Full access no longer unlocks, though every message says it "
                                       "does (core make_own keeps the lock; names() drops the shadowed built-in)")
def test_full_access_always_unlocks():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    assert bpy.ops.fresing.workspace_pick(name="Client view") == {"FINISHED"}
    try:
        bpy.ops.fresing.workspace_save(name="Full access")
    except RuntimeError:
        pass                                                 # refusing that name would be a fine answer too
    assert "Full access" in [n for n, _note, _own in workspaces.names()]
    assert bpy.ops.fresing.workspace_pick(name="Full access") == {"FINISHED"}
    assert not lock.ON[0] and lock.marked() == 0 and not lock.tabs_hidden()


# ===================================================================================================================
# the Client view's lock
# ===================================================================================================================

def test_every_fresing_operator_is_refused_in_the_client_view_except_the_allow_list():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    from fresing_render.blender import cameras
    cameras.add_camera(sc)
    ops = _operators()
    assert len(ops) > 300 and all(i.startswith("fresing.") for i in ops)
    free = {i: bool(_op(i).poll()) for i in ops}
    workspaces.switch(sc, "Client view")
    for i in ops:
        if lock.allowed(i):
            if i != "fresing.client_locked":                 # what still works, works as before
                assert bool(_op(i).poll()) == free[i], i
        else:
            assert not _op(i).poll(), i
    with pytest.raises(RuntimeError, match="Full access"):   # … and says why, and how to get out
        bpy.ops.fresing.pose_save()
    workspaces.switch(sc, "Education & training")            # any workspace without the lock undoes it
    assert {i: bool(_op(i).poll()) for i in ops if i != "fresing.client_locked"} == \
        {i: v for i, v in free.items() if i != "fresing.client_locked"}
    # every fresing operator goes through the lock: only the PC check's two are registered apart, and are allowed
    inside = {c.__name__ for c in fresing_render._all_classes()}
    outside = sorted(i for i, n in ops.items() if n not in inside)
    assert outside == ["fresing.pc_check", "fresing.pc_check_cancel"] and all(lock.allowed(i) for i in outside)


def test_nothing_on_the_allow_list_edits_the_model_by_its_name():
    """The allow-list is short and holds no operator of the editing kind (the brief: import, surroundings picker,
    saved views, turntable, render; plus help, updates, the panel itself)."""
    workspaces, panels, lock = _mods()
    allowed = sorted(i for i in _operators() if lock.allowed(i))
    assert len(allowed) < 138         # task 0309: + the lead motions' ▶, Test, Back to start and Keep open (4: they move joints the way the Client view's sliders do, nothing else); task 0294: + the workspace's star (a setting of the user, not of the model) (1); task 0308: + Render this view and the outputs strip's switch (2); task 0296: + the graphics-card notice, Show me how, Windows' Graphics settings and Use the graphics card (4; Windows' preference, never the model); task 0316: + Update now's box Cancel (1); task 0282: + a function window's OK, Close and Esc / Return (3; OK runs the function's own poll, refused stays refused); task 0275: + hub_show (1); task 0281: + tour_chapter (1); task 0253: + a swallowed Blender key, F12, the right-click menu and its 5 viewing entries (hide in the view only) (8); task 0271: + Fresing Settings open / tab / close and the presence mark (4); task 0260: + fold the left panel, the Learning hub's switch, What's next's fold, the output windows' open / close / Make's fold (6); task 0230: + Learn…, its View / Show me / Build (a new project, never the locked one) and the lesson's Stop, More, mode (6); task 0217: + the Toolbox status line and Not now (2); task 0213: + camera, saved scene, paint schemes (4); task 0208: + the learning buttons (8); task 0181: + the usage tracker's 9 buttons (they change nothing in the model)
    edits = ("_add", "_remove", "_delete", "_clear", "_save", "_set", "_move", "_assign", "_apply_", "explode",
             "exclude", "hide_", "joint", "pose", "group", "rule", "scheme", "decal", "bake", "build")
    ok = {"fresing.queue_add", "fresing.queue_remove", "fresing.report_clear", "fresing.workspace_save",
          "fresing.workspace_delete", "fresing.next_hide", "fresing.workspace_default",
          "fresing.usage_clear",           # task 0181: clears the usage file on this PC, not the model
          # task 0208: they change the user's own learning list in the usage file, never the model
          "fresing.learn_add", "fresing.learn_add_new", "fresing.learn_remove",
          # the job that works the cables out again after a sea change the Client view may make (the tester's own
          # suspicion: refused, the cables would stay stale) – it follows the project, it edits nothing by hand
          "fresing.rebake", "fresing.rebake_cancel",
          # task 0213 (bug hunt 0209 row 24): the Client view shows camera views, saved scenes and every paint scheme
          # – a new camera is locked like the rest, a saved scene and the queue's jobs change no part
          "fresing.camera_add", "fresing.shot_save", "fresing.queue_schemes", "fresing.queue_schemes_tick"}
    assert [i for i in allowed if any(w in i for w in edits) and i not in ok] == []
    for i in ("fresing.import_step", "fresing.render", "fresing.turntable", "fresing.shot_apply",
              "fresing.camera_activate", "fresing.light_look", "fresing.queue_start", "fresing.workspace_pick"):
        assert i in allowed, i


@FINDING(reason="FINDING 1: in the Client view '1 Import > Update to new revision…' still "
                                       "works: the whole model is replaced by another revision (parts added and "
                                       "removed) while 'locked against changes' – fresing.import_step is on the "
                                       "allow-list with its update_root option (lock.ALLOWED; same for import_mesh)")
def test_the_client_view_refuses_a_model_update():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    parts = _parts(sc)
    root = _root(sc).name
    workspaces.switch(sc, "Client view")
    try:
        res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root)
    except RuntimeError:
        res = {"CANCELLED"}
    assert res != {"FINISHED"} and _parts(sc) == parts


@FINDING(reason="FINDING 2: after a model update in the Client view and Full access, no part "
                                       "is 'Locked in place' any more (24 of 26 objects on the test crane): every "
                                       "part can be dragged by mistake. The lock notes 'was free' for the new parts "
                                       "before the update locks them in place, and frees them when it goes "
                                       "(lock._after_change runs between build and reimport's own locking)")
def test_parts_are_locked_in_place_as_the_app_leaves_them_after_the_client_view():
    workspaces, panels, lock = _mods()
    from fresing_render.blender import build
    sc = _new(CRANE)
    assert all(all(o.lock_location) and all(o.lock_rotation) for o in build.iter_parts(sc))    # the app's default
    root = _root(sc).name
    workspaces.switch(sc, "Client view")
    try:
        bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root)
    except RuntimeError:
        pass
    bpy.context.view_layer.update()
    workspaces.switch(sc, "Full access")
    loose = [o.name for o in build.iter_parts(sc) if not (all(o.lock_location) and all(o.lock_rotation))]
    assert loose == []


def test_what_is_made_in_the_client_view_is_locked_and_exactly_as_without_it_afterwards():
    """Import, surroundings, a turntable – the things the Client view is for – made with the lock on: locked while
    it is on, and after Full access exactly what the same clicks give without the lock."""
    workspaces, panels, lock = _mods()
    from fresing_render.blender import turntable
    from fresing_render.core import surroundings as env

    def clicks(sc):
        assert bpy.ops.fresing.import_step(filepath=GANTRY, quality="draft") == {"FINISHED"}
        assert bpy.ops.fresing.import_mesh(filepath=os.path.join(DATA, "test_mesh_crane.glb")) == {"FINISHED"}
        for bg in env.BUILT:
            sc.fresing.background = bg
            bpy.context.view_layer.update()
        turntable.make(sc)
        assert bpy.ops.fresing.light_look(look="PRODUCT") == {"FINISHED"}
        bpy.context.view_layer.update()

    sc = _new(CRANE)
    clicks(sc)
    plain, plain_project = _locks(), _project(sc)
    sc = _new(CRANE)
    workspaces.switch(sc, "Client view")
    clicks(sc)
    assert lock.ON[0] and lock.marked() == len(bpy.data.objects) == len(plain)
    assert all(o.hide_select and all(o.lock_location) and all(o.lock_rotation) and all(o.lock_scale)
               for o in bpy.data.objects)
    assert not bpy.context.selected_objects
    workspaces.switch(sc, "Full access")
    assert _locks() == plain and _project(sc) == plain_project
    assert lock.marked() == 0 and all("fr_cv" not in o for o in bpy.data.objects)
    assert all("fr_cv_areas" not in scr for scr in bpy.data.screens)


def test_the_apps_own_locked_in_place_and_removed_parts_come_back_exactly():
    workspaces, panels, lock = _mods()
    from fresing_render.blender import build, logic
    sc = _new(CRANE)
    parts = list(build.iter_parts(sc))
    logic.set_locked(parts[0], False)                        # the user freed one part ("Locked in place" off)
    logic.exclude([parts[1]])                                # Clean-up removed one: unclickable, hidden
    parts[2].lock_rotation = (True, False, True)
    orphan = bpy.data.objects.new("In no scene", None)       # an object in no scene (a kept copy)
    orphan.lock_scale = (False, True, False)
    before = _locks()
    hidden_before = {o.name: (o.hide_render, o.hide_viewport, o.hide_get()) for o in sc.objects}
    for name in ("Client view", "Client view"):              # switching to it twice is no problem either
        workspaces.switch(sc, name)
        assert all(o.hide_select and all(o.lock_location) and all(o.lock_rotation) and all(o.lock_scale)
                   for o in bpy.data.objects)                # every object, also the one in no scene
        assert {o.name: (o.hide_render, o.hide_viewport, o.hide_get()) for o in sc.objects} == hidden_before
    for back in ("All functions", "Full access", "Education & training"):
        workspaces.switch(sc, "Client view")
        workspaces.switch(sc, back)                          # Full access – or any workspace without the lock
        assert _locks() == before, back
        assert lock.marked() == 0 and not lock.ON[0]
    assert parts[1].get(build.PROP_EXCLUDED) and parts[1].hide_select
    bpy.data.objects.remove(orphan)


def test_a_linked_object_does_not_stop_the_lock(tmp_path):
    workspaces, panels, lock = _mods()
    _new(CRANE)
    lib = str(tmp_path / "library.blend")
    bpy.ops.wm.save_as_mainfile(filepath=lib)
    sc = _new(CRANE)
    with bpy.data.libraries.load(lib, link=True) as (src, dst):
        dst.objects = [src.objects[0]]
    linked = dst.objects[0]
    sc.collection.objects.link(linked)
    assert linked.library is not None
    before = {k: v for k, v in _locks().items()}
    workspaces.switch(sc, "Client view")
    assert lock.ON[0] and all(o.hide_select for o in bpy.data.objects if o.library is None)
    workspaces.switch(sc, "Full access")
    assert not lock.ON[0] and lock.marked() == 0 and _locks() == before


def test_the_lock_follows_the_project_that_is_open(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    plain = str(tmp_path / "plain.blend")
    bpy.ops.wm.save_as_mainfile(filepath=plain)
    before = _locks()
    workspaces.switch(sc, "Client view")
    locked = str(tmp_path / "locked.blend")
    bpy.ops.wm.save_as_mainfile(filepath=locked)

    def file_menu_locked():
        return bpy.types.TOPBAR_MT_file.__dict__.get("draw") is not _BEFORE["file_draw"]
    assert lock.ON[0] and file_menu_locked()
    bpy.ops.wm.open_mainfile(filepath=plain)                 # another project: not locked, nothing left behind
    assert not lock.ON[0] and lock.marked() == 0 and _locks() == before and not file_menu_locked()
    assert bpy.ops.fresing.pose_save.poll() is not None and not bpy.ops.fresing.client_locked.poll()
    bpy.ops.wm.open_mainfile(filepath=locked)                # opened in a session where the lock was off: locked
    sc = bpy.context.scene
    assert lock.ON[0] and lock.marked() == len(bpy.data.objects) and file_menu_locked()
    assert all(o.hide_select for o in bpy.data.objects) and bpy.ops.fresing.client_locked.poll()
    _new()                                                   # File > New: free again
    assert not lock.ON[0] and not file_menu_locked() and not bpy.ops.fresing.client_locked.poll()
    bpy.ops.wm.open_mainfile(filepath=locked)
    sc = bpy.context.scene
    workspaces.switch(sc, "Full access")
    assert _locks() == before and all("fr_cv" not in o for o in bpy.data.objects)
    bpy.ops.wm.save_mainfile()                               # saved unlocked: opens unlocked, as it was
    bpy.ops.wm.open_mainfile(filepath=locked)
    assert not lock.ON[0] and _locks() == before


def test_undo_and_redo_put_the_lock_where_the_workspace_is():
    """Real Ctrl+Z is not available here: the handler behind it, on the states an undo leaves."""
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    before = _locks()
    workspaces.switch(sc, "Client view")
    lock._unlock_all()                                       # an undo of the pick: the workspace and the objects
    sc.fresing.ws_name = "All functions"                     # are as before it, the session still thinks "locked"
    workspaces._after_undo()
    assert not lock.ON[0] and lock.marked() == 0 and _locks() == before
    sc.fresing.ws_name = "Client view"                       # the redo: the workspace says locked, objects are free
    workspaces._after_undo()
    assert lock.ON[0] and lock.marked() == len(bpy.data.objects) and all(o.hide_select for o in bpy.data.objects)
    sc.fresing.ws_name = "Full access"                       # undo of "Full access → another": Blender's tabs back
    workspaces._after_undo()
    assert not lock.ON[0] and _locks() == before and not lock.tabs_hidden()
    sc.fresing.ws_name = "All functions"
    workspaces._after_undo()
    assert lock.tabs_hidden()
    workspaces._after_undo()                                 # nothing to put right: nothing changes
    assert not lock.ON[0] and _locks() == before and lock.tabs_hidden()


@FINDING(reason="FINDING 7: a new project while the default workspace is the Client view "
                                       "(Workspace > Use for new projects on a sales PC): the lock fails half-way "
                                       "with 'workspace not set: NoneType has no attribute select_get' – Blender's "
                                       "tabs and the File menu stay as they were (lock._lock_all meets an empty "
                                       "entry in the view layer inside the load handler; seen with Blender as a "
                                       "module, not checked in the real app)")
def test_a_new_project_in_a_locked_default_workspace_is_locked_all_the_way(capfd):
    workspaces, panels, lock = _mods()
    p = _prefs()
    sc = _new(CRANE)
    workspaces.switch(sc, "Full access")                     # Blender's tabs shown, the File menu whole
    p.default_workspace = "Client view"
    capfd.readouterr()
    sc = _new()
    out = capfd.readouterr().out
    assert sc.fresing.ws_name == "Client view" and lock.ON[0]
    assert "workspace not set" not in out
    assert lock.tabs_hidden()
    assert bpy.types.TOPBAR_MT_file.__dict__.get("draw") is not _BEFORE["file_draw"]


@FINDING(reason="FINDING 11: the workspace is kept per scene, the lock per file: with a "
                                       "second scene in the project, showing it leaves the lock on although that "
                                       "scene's workspace is 'All functions' (every button refused, the panel says "
                                       "nothing) – and the other way round (nothing follows a change of scene)")
def test_with_two_scenes_the_lock_follows_the_scene_that_is_shown():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    second = bpy.data.scenes.new("Second")
    workspaces.switch(sc, "Client view")
    assert lock.ON[0]
    bpy.context.window.scene = second
    bpy.context.view_layer.update()
    assert bpy.context.scene is second and not workspaces.locked(second)
    lock._after_change()                 # what the app's update handler does at the scene's next update (a script
    assert lock.ON[0] == workspaces.locked(bpy.context.scene)      # without a window gets no such update by itself)
    bpy.context.window.scene = sc
    lock._after_change()
    assert lock.ON[0] and all(o.hide_select for o in sc.objects)


def test_whats_next_goes_per_project_after_a_render_and_in_the_client_view(tmp_path):
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    assert _polls("FRESING_PT_next")
    workspaces.switch(sc, "Client view")
    assert not _polls("FRESING_PT_next") and bpy.ops.fresing.next_hide.poll()
    workspaces.switch(sc, "All functions")
    assert bpy.ops.fresing.next_hide() == {"FINISHED"} and not _polls("FRESING_PT_next")
    path = str(tmp_path / "next.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc = _new(CRANE)
    assert _polls("FRESING_PT_next")                         # another project has its card
    sc.fresing.rendered_once = True                          # a picture was made: the card is done
    assert not _polls("FRESING_PT_next")
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not _polls("FRESING_PT_next")                     # remembered in the project
    sc = _new()
    assert _polls("FRESING_PT_next") and not _polls("FRESING_PT_make")             # no model yet: nothing to make


@FINDING(reason="FINDING 12: 'What's next' is 'gone after the first render' – but a first "
                                       "turntable video leaves it there (only Render image and Add to queue note "
                                       "the render: ops_scene.FRESING_OT_turntable does not set rendered_once)")
def test_a_turntable_video_counts_as_the_first_render(monkeypatch):
    workspaces, panels, lock = _mods()
    from fresing_render.blender import queue
    sc = _new(CRANE)
    monkeypatch.setattr(queue, "start", lambda *a, **k: "")  # no background render in a test
    assert _polls("FRESING_PT_next")
    assert bpy.ops.fresing.turntable() == {"FINISHED"} and len(sc.fresing.queue) == 1
    assert not _polls("FRESING_PT_next")


# ===================================================================================================================
# robustness
# ===================================================================================================================

def test_asking_about_a_scene_without_settings_never_raises():
    workspaces, panels, lock = _mods()

    class Bare:
        pass
    for scene in (None, Bare()):
        assert workspaces.name_of(scene) == "All functions"
        assert workspaces.current(scene).name == "All functions"
        assert workspaces.ticks(scene) == {} and workspaces.in_use(scene) == {}
        assert not workspaces.locked(scene) and not workspaces.blender_ui(scene)
        assert not workspaces.panel_hidden(scene, "FRESING_PT_cnc") and workspaces.shows(scene, "cnc.machine")
        assert workspaces.family_on(scene, "cnc") and workspaces.hidden_in_use(scene) == []
        assert workspaces.show_used(scene) == [] and workspaces.ensure(scene) is False
        workspaces.on_load(scene)
        panels.on_load(scene)
        panels.on_save(scene)
        lock.apply(scene, False)
    assert panels.visible("FRESING_PT_cnc", None) in (True, False)
    assert not lock.allowed("") and not lock.allowed("object.delete") and lock.allowed("fresing.workspace_pick")
    # a project whose stored texts are damaged (a newer version, a hand edit) still draws
    sc = _new(CRANE)
    for data, ticks in (("{not json", "[1, 2"), ("[1, 2, 3]", "5"), ('{"name": "x"}', '{"cnc": "no", "robots": 1}'),
                        (json.dumps({W.MARKER: 5, "name": "Later", "families": "all", "hide": None}), "null")):
        sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks = "Later", data, ticks
        assert isinstance(workspaces.current(sc), W.Workspace)
        assert _polls("FRESING_PT_workspace") and _polls("FRESING_PT_import")
        workspaces.apply(sc)
        workspaces.on_load(sc)
    sc.fresing.ws_name, sc.fresing.ws_data, sc.fresing.ws_ticks = "A name nobody has", "", ""
    assert _reach("FRESING_PT_cnc") and not lock.ON[0]       # an unknown workspace hides nothing, locks nothing
    with pytest.raises((RuntimeError, TypeError)):           # and picking a workspace that is not there says so
        bpy.ops.fresing.workspace_pick(name="A name nobody has")


# ===================================================================================================================
# the extension switched off and on (these run last: they unregister it)
# ===================================================================================================================

def test_zz_switching_the_extension_off_leaves_blender_as_it_was():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "All functions")                   # Blender's top bar drawn without its tabs
    assert bpy.types.TOPBAR_HT_upper_bar.__dict__.get("draw_left") is not _BEFORE["draw_left"]
    fresing_render.unregister()
    try:
        assert _handler_counts() == _BEFORE["handlers"]
        assert bpy.types.TOPBAR_HT_upper_bar.__dict__.get("draw_left") is _BEFORE["draw_left"]
        assert bpy.types.TOPBAR_MT_file.__dict__.get("draw") is _BEFORE["file_draw"]
        assert not hasattr(bpy.types.WindowManager, "fresing_tab")
        assert [n for n in dir(bpy.types) if n.startswith(("FRESING_PT_", "FRESING_OT_"))
                and n not in ("FRESING_OT_user_guide", "FRESING_OT_show_panel")] == []
        assert not lock.ON[0]
    finally:
        fresing_render.register()
    assert not any(panels.is_open(s) for s in places.SECTIONS)                     # at register: sections folded
    assert panels.tab() == "ALL" and len(_operators()) > 300
    assert _handler_counts() != _BEFORE["handlers"]


@FINDING(reason="FINDING 9: switching the extension off while the Client view is on leaves "
                                       "every object unclickable and locked, with the lock's marks on them – and "
                                       "nothing left to undo it (lock.unregister only clears its flag)")
def test_zz_switching_the_extension_off_in_the_client_view_gives_the_parts_back():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    before = _locks()
    workspaces.switch(sc, "Client view")
    fresing_render.unregister()
    try:
        assert _locks() == before and all("fr_cv" not in o for o in bpy.data.objects)
    finally:
        fresing_render.register()


@FINDING(reason="FINDING 9: switched on again with a Client view project open, the panel says "
                                       "'locked' but nothing is: every editing operator works until the next load "
                                       "(fresing_render.register never applies the open project's workspace; the "
                                       "same after a first enabling with a project open: Blender's tabs stay)")
def test_zz_switching_the_extension_on_applies_the_open_projects_workspace():
    workspaces, panels, lock = _mods()
    sc = _new(CRANE)
    workspaces.switch(sc, "Client view")
    fresing_render.unregister()
    fresing_render.register()
    sc = bpy.context.scene
    assert workspaces.locked(sc)
    assert lock.ON[0] and not bpy.ops.fresing.pose_save.poll() and lock.tabs_hidden()
