"""Function windows (task 0282): a function's form opens in a window of its own that stays open.

What is checked here (Blender as a Python module – no windows, so the window itself is the real-app test
``tools/ui_test_forms.py``):

* the inventory: every dialog of the app is either a window now (``form_window.WINDOWS``: its ``invoke`` calls
  ``form_window.open``) or a popup on purpose (``form_window.POPUPS``) – a new dialog has to choose;
* a form's values are a property group made from the operator's own properties (names, defaults, choices, hidden);
* the operator's own ``draw`` draws them, the layout handed the values where the draw names the operator;
* Make runs the operator with those values (its undo step, its reports), refused ones stay refused and say why;
* opening again keeps what was typed, unless the window is about something else now;
* the sizes and places of the app's windows are kept in the settings file (one preference), the old file moves over.
"""

import ast
import json
import os
import pathlib

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.core import usage as U  # noqa: E402

ROOT = pathlib.Path(fresing_render.__file__).parent


@pytest.fixture(scope="module", autouse=True)
def addon(tmp_path_factory):
    d = tmp_path_factory.mktemp("forms")
    os.environ["FRESING_WORKSPACES_DIR"] = str(d / "Workspaces")
    os.environ["FRESING_USAGE_FILE"] = str(d / U.FILE_NAME)
    fresing_render.register()
    from fresing_render.blender import prefs
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    yield
    fresing_render.unregister()
    for k in ("FRESING_WORKSPACES_DIR", "FRESING_USAGE_FILE"):
        os.environ.pop(k, None)


@pytest.fixture()
def fw():
    from fresing_render.blender import form_window
    return form_window


def _op_cls(idname):
    cat, _, name = idname.partition(".")
    return getattr(bpy.types, f"{cat.upper()}_OT_{name}")


# ---------------------------------------------------------------------------
# the inventory
# ---------------------------------------------------------------------------

def _dialogs():
    """{bl_idname: (file, calls)} of every operator class whose source calls a dialog or form_window.open."""
    out = {}
    for path in sorted(ROOT.rglob("*.py")):
        if path.name == "form_window.py":
            continue
        src = path.read_text(encoding="utf-8")
        if "invoke_props_dialog" not in src and "invoke_popup" not in src and "form_window" not in src:
            continue
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.ClassDef):
                continue
            seg = ast.get_source_segment(src, node) or ""
            idname = next((n.value.value for n in node.body if isinstance(n, ast.Assign)
                           and getattr(n.targets[0], "id", "") == "bl_idname"
                           and isinstance(n.value, ast.Constant)), "")
            calls = {c for c in ("invoke_props_dialog", "invoke_popup", "form_window.open") if c in seg}
            if calls and idname:
                out[idname] = (path.name, calls)
    return out


def test_every_dialog_is_a_window_or_a_popup_on_purpose(fw):
    found = _dialogs()
    assert not set(fw.WINDOWS) & set(fw.POPUPS)
    for idname, (path, calls) in found.items():
        if idname in fw.WINDOWS:
            assert calls == {"form_window.open"}, (idname, path, calls)
        else:
            assert idname in fw.POPUPS, f"{idname} ({path}) opens a dialog: make it a window (form_window.open) " \
                                        "or name it in form_window.POPUPS with the reason"
            assert "form_window.open" not in calls
    assert set(fw.WINDOWS) <= set(found), set(fw.WINDOWS) - set(found)
    assert set(fw.POPUPS) <= set(found), set(fw.POPUPS) - set(found)
    assert len(fw.WINDOWS) >= 23
    assert "fresing.lifting_make" in fw.WINDOWS                   # the owner's example


def test_the_window_buttons_work_in_the_client_view_and_are_not_counted():
    from fresing_render.blender import lock
    for idname in ("fresing.form_ok", "fresing.form_close", "fresing.form_key"):
        assert lock.allowed(idname)
        assert idname in U.NOT_COUNTED
    assert not lock.allowed("fresing.pose_save")                  # refused stays refused (Make runs its poll)


def test_every_window_operator_keeps_its_tooltip(fw):
    for idname in fw.WINDOWS:
        cls = _op_cls(idname)
        cat, _, name = idname.partition(".")
        desc = getattr(getattr(bpy.ops, cat), name).get_rna_type().description
        assert desc and "\n" not in desc, idname


# ---------------------------------------------------------------------------
# the values
# ---------------------------------------------------------------------------

def test_the_values_mirror_the_operators_properties(fw):
    for idname in fw.WINDOWS:
        cls = _op_cls(idname)
        group = fw.make_group(cls)
        d = fw.data(idname)
        assert d is not None and isinstance(d, group), idname
        op_props = {p.identifier: p for p in fw.props_rna(cls).properties if p.identifier != "rna_type"}
        g_props = {p.identifier: p for p in group.bl_rna.properties}
        for name, p in op_props.items():
            assert name in g_props, (idname, name)
            q = g_props[name]
            assert (q.type, q.is_hidden, getattr(q, "default", None)) == (p.type, p.is_hidden,
                                                                           getattr(p, "default", None)), (idname, name)
        assert fw.prop_names(cls) == list(op_props), idname


def test_a_name_property_is_the_forms_own(fw):
    fw.make_group(_op_cls("fresing.pose_save"))
    d = fw.data("fresing.pose_save")
    d.name = "Boom up"
    assert d.name == "Boom up" and fw.values("fresing.pose_save")["name"] == "Boom up"


class Rec:
    """A layout stand-in that records what is drawn."""
    _layout_like = True

    def __init__(self, log=None):
        self.__dict__["log"] = log if log is not None else []

    def __getattr__(self, name):
        def call(*a, **k):
            self.log.append((name, a, k))
            if name == "panel":
                return Rec(self.log), Rec(self.log)
            return Rec(self.log) if name in ("row", "column", "box", "split", "grid_flow", "column_flow") \
                else type("Props", (), {})()
        return call

    def __setattr__(self, name, value):
        self.log.append(("set", name, value))


def seed(fw, idname, title="T", confirm="OK", **vals):
    """What ``open`` does before the window opens: the form's values from the operator."""
    cls = _op_cls(idname)
    fw.make_group(cls)
    d = fw.data(idname)
    for n in fw.prop_names(cls):
        if n in vals:
            setattr(d, n, vals[n])
    fw._FORMS[idname] = {"cls": cls, "title": title, "confirm": confirm, "icon": "WINDOW", "extra": {}, "error": ""}
    return d


def test_the_operators_draw_gets_the_values_not_the_operator(fw):
    bpy.ops.wm.read_homefile(use_empty=True)
    d = seed(fw, "fresing.shot_save", name="Hero")
    rec = Rec()
    assert fw.draw_form(rec, bpy.context, "fresing.shot_save")
    props = [(a[0], a[1]) for name, a, k in rec.log if name == "prop"]
    assert [p[1] for p in props] == ["name", "scheme", "pose", "visibility"]
    assert all(p[0] == d for p in props)                           # the form's values, never the stand-in
    assert any(name == "label" and "Camera: none" in k.get("text", "") for name, a, k in rec.log)


def test_an_operator_without_draw_shows_its_visible_properties(fw):
    d = seed(fw, "fresing.pose_save", name="Up")
    rec = Rec()
    assert fw.draw_form(rec, bpy.context, "fresing.pose_save")
    assert [(a[0], a[1]) for name, a, k in rec.log if name == "prop"] == [(d, "name")]


def test_a_draw_that_uses_what_invoke_found(fw):
    seed(fw, "fresing.learn_window")
    fw._FORMS["fresing.learn_window"]["extra"] = {"_told": []}
    assert fw.draw_form(Rec(), bpy.context, "fresing.learn_window")


@pytest.mark.parametrize("idname", ["fresing.about", "fresing.demo_make", "fresing.tour_make", "fresing.tour_note",
                                    "fresing.workspace_save", "fresing.rule_set_save_as", "fresing.rule_set_new_empty",
                                    "fresing.rule_set_rename", "fresing.usage_export", "fresing.pc_check",
                                    "fresing.learn_lessons", "fresing.backups_window", "fresing.lifting_box",
                                    "fresing.gcode_go_line", "fresing.group_add", "fresing.scheme_save",
                                    "fresing.vis_save", "fresing.gcode_report", "fresing.shot_save",
                                    "fresing.pose_save", "fresing.workspace_rename"])
def test_each_form_draws_in_its_window(fw, idname):
    bpy.ops.wm.read_homefile(use_empty=True)
    from fresing_render.blender import ops_rule_sets
    ops_rule_sets._PREVIEW.update(lines=["a line"], warning="")
    seed(fw, idname)
    assert fw.draw_form(Rec(), bpy.context, idname)


def test_make_a_crane_draws_its_form(fw):
    from fresing_render.blender import lifting
    bpy.ops.wm.read_homefile(use_empty=True)
    was = lifting.understood()
    lifting.set_understood(True)
    try:
        seed(fw, "fresing.lifting_make", confirm="Make")
        rec = Rec()
        assert fw.draw_form(rec, bpy.context, "fresing.lifting_make")
        assert any(name == "prop" for name, a, k in rec.log)
    finally:
        lifting.set_understood(was)


# ---------------------------------------------------------------------------
# Make / OK
# ---------------------------------------------------------------------------

def test_make_runs_the_operator_with_the_windows_values(fw):
    from fresing_render.blender import states
    bpy.ops.wm.read_homefile(use_empty=True)
    seed(fw, "fresing.vis_save", name="Hull only")
    res, why = fw.run("fresing.vis_save")
    assert res == {"FINISHED"} and why == ""
    assert "Hull only" in [v.name for v in bpy.context.scene.fresing.visibility_sets]
    assert states.unique_visibility_name(bpy.context.scene) != "Hull only"


def test_make_refused_by_the_operators_poll_says_why(fw):
    bpy.ops.wm.read_homefile(use_empty=True)
    seed(fw, "fresing.gcode_go_line", line=12)                     # no CNC machine, no step: its poll refuses
    res, why = fw.run("fresing.gcode_go_line")
    assert res == {"CANCELLED"} and why


def test_make_that_fails_keeps_the_window_with_the_reason(fw):
    bpy.ops.wm.read_homefile(use_empty=True)
    seed(fw, "fresing.workspace_rename", name="x")                 # only an own workspace can be renamed
    res, why = fw.run("fresing.workspace_rename")
    assert res == {"CANCELLED"} and "own" in why


def test_ok_closes_only_when_done_and_keeps_the_reason_otherwise(fw):
    bpy.ops.wm.read_homefile(use_empty=True)
    seed(fw, "fresing.gcode_go_line", line=3)
    assert bpy.ops.fresing.form_ok(form="fresing.gcode_go_line") == {"CANCELLED"}
    assert fw._FORMS["fresing.gcode_go_line"]["error"]
    seed(fw, "fresing.pose_save", name="Lowered")
    assert bpy.ops.fresing.form_ok(form="fresing.pose_save") == {"FINISHED"}
    assert "Lowered" in [p.name for p in bpy.context.scene.fresing.poses]
    assert fw._FORMS["fresing.pose_save"]["error"] == ""


def test_a_window_of_a_function_never_opened_says_so(fw):
    res, why = fw.run("fresing.no_such_thing")
    assert res == {"CANCELLED"} and "not there" in why


def test_close_runs_the_operators_cancel(fw):
    from fresing_render.blender import ops_learning
    seed(fw, "fresing.learn_lessons")
    ops_learning.CHOSEN["mode"] = "SHOW"
    fw.close("fresing.learn_lessons")
    assert ops_learning.CHOSEN["mode"] == ""
    ops_learning.CHOSEN["mode"] = "SHOW"
    fw.close("fresing.learn_lessons", done=True)                   # after OK: no cancel
    assert ops_learning.CHOSEN["mode"] == "SHOW"
    ops_learning.CHOSEN["mode"] = ""


# ---------------------------------------------------------------------------
# opening again
# ---------------------------------------------------------------------------

class _Op:
    def __init__(self, cls, **vals):
        from fresing_render.blender import form_window as fw
        self.__class__ = type(cls.__name__, (_Op,), {"bl_idname": cls.bl_idname, "bl_label": cls.bl_label})
        for n, p in ((p.identifier, p) for p in fw.props_rna(cls).properties if p.identifier != "rna_type"):
            setattr(self, n, vals.get(n, p.default))


def test_opening_again_keeps_what_was_typed_unless_it_is_about_something_else(fw):
    cls = _op_cls("fresing.tour_note")
    fw._FORMS.pop("fresing.tour_note", None)
    assert fw.prepare(_Op(cls, stop="looks", note="old"), bpy.context, open_now=False, title="Note")
    d = fw.data("fresing.tour_note")
    assert (d.stop, d.note) == ("looks", "old")
    d.note = "typed"
    assert not fw.prepare(_Op(cls, stop="looks", note="old"), bpy.context, open_now=True, title="Note")
    assert d.note == "typed"                                       # same stop, window open: what was typed stays
    assert fw.prepare(_Op(cls, stop="mill", note=""), bpy.context, open_now=True, title="Note")
    assert (d.stop, d.note) == ("mill", "")                        # another stop: starts again
    assert fw.prepare(_Op(cls, stop="mill", note="x"), bpy.context, open_now=False, title="Note")
    assert d.note == "x"                                           # a closed window starts from invoke's values


def test_open_in_a_background_run_does_what_the_dialog_did(fw):
    assert bpy.app.background
    assert bpy.ops.fresing.pose_save("INVOKE_DEFAULT") in ({"RUNNING_MODAL"}, {"CANCELLED"}, {"FINISHED"})


# ---------------------------------------------------------------------------
# sizes and places in the settings file
# ---------------------------------------------------------------------------

class _Screen(dict):
    pass


class _Win:
    def __init__(self, marks, w, h):
        self.screen = _Screen(marks)
        self.width, self.height = w, h


def test_sizes_and_places_are_one_preference_in_the_settings_file(tmp_path, monkeypatch):
    from fresing_render.blender import ops_make, prefs, settings_store
    p = prefs.get()
    p.window_places = ""
    old = tmp_path / ops_make.PLACES_FILE
    old.write_text(json.dumps({"settings": [10, 20, 450, 700], "still": [1, 2, 3]}), encoding="utf-8")
    monkeypatch.setattr(ops_make, "places_path", lambda: str(old))
    ops_make.forget_places()
    assert ops_make.kept_place("settings") == [10, 20, 450, 700]  # the old file moved over (a bad row left out)
    assert ops_make.kept_place("still") is None
    scale = bpy.context.preferences.system.ui_scale or 1.0
    win = _Win({"fr_form": "fresing.lifting_make"}, int(600 * scale), int(820 * scale))
    assert ops_make.place_key(win) == "form:fresing.lifting_make"
    ops_make.remember(win)
    assert ops_make.kept_size("form:fresing.lifting_make") == (600, 820)
    places, sizes = ops_make.parse(p.window_places)
    assert places["settings"] == [10, 20, 450, 700] and sizes["form:fresing.lifting_make"] == [600, 820]
    ops_make.forget_places()                                       # read again: from the preference now
    old.unlink()
    assert ops_make.kept_size("form:fresing.lifting_make") == (600, 820)
    assert "window_places" in settings_store.spec()                # so the settings file keeps it over a restart
    ops_make.remember(_Win({"fr_form": "fresing.pose_save"}, 20, 20))      # too small to be real: not kept
    assert ops_make.kept_size("form:fresing.pose_save") is None
    p.window_places = ""
    ops_make.forget_places()


def test_a_damaged_preference_gives_nothing():
    from fresing_render.blender import ops_make
    assert ops_make.parse("") == ({}, {})
    assert ops_make.parse("not json") == ({}, {})
    assert ops_make.parse(json.dumps([1])) == ({}, {})
    assert ops_make.parse(json.dumps({"places": {"a": [1, 2, 3, True]}, "sizes": {"b": [5, 6]}})) == ({}, {"b": [5, 6]})
    text = ops_make.dump({"a": [1, 2, 3, 4]}, {"b": [5, 6]})
    assert ops_make.parse(text) == ({"a": [1, 2, 3, 4]}, {"b": [5, 6]})


def test_the_page_windows_are_side_windows():
    from fresing_render.blender import ops_setup, panels
    assert "fr_form" in panels.SIDE_MARKS and ops_setup.FORM_MARK in ops_setup.PAGE_MARKS
    win = _Win({"fr_form": "fresing.pose_save"}, 400, 200)
    assert ops_setup.is_page_window(win) and ops_setup.tab_of(win) == ops_setup.FORM_TAB
    assert panels.side_window(win)
    assert not ops_setup.is_page_window(_Win({"fr_output": "still"}, 400, 200))
