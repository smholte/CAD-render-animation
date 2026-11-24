"""Task 0291: project names in the app – the first model's name, Save as "(1)", the setting, unsaved backups, the
File menu and the keys (Blender as a Python module)."""

from __future__ import annotations

import os
import time

import pytest

bpy = pytest.importorskip("bpy")
import fresing_render  # noqa: E402
from fresing_render.blender import backups, build, project_name  # noqa: E402
from fresing_render.core import backups as core_b  # noqa: E402
from fresing_render.core import project_name as core  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def fresh(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    yield tmp_path


def _root(name: str, source: str, when: float, cad_name: str | None = None):
    ob = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(ob)
    ob[build.PROP_ROOT] = True
    ob[build.PROP_SOURCE] = source
    ob[build.PROP_IMPORTED] = when
    if cad_name is not None:
        ob[build.PROP_NAME] = cad_name
    return ob


def test_nothing_imported_is_an_untitled_project(fresh):
    assert project_name.model_name() == ""
    assert project_name.proposal() == "Untitled project"
    assert backups.unsaved_name() == core_b.UNSAVED_NAME


def test_the_first_model_names_the_project(fresh):
    folder = fresh / "models é"
    folder.mkdir()
    second = _root("Gearbox", str(folder / "gearbox.stp"), time.time())
    _root("Crane v8.iam", str(folder / "crane.stp"), time.time() - 60, cad_name="Test crane v8")
    assert project_name.first_model().name != second.name
    assert project_name.model_name() == "Test crane"
    assert project_name.proposal() == "Test crane"
    path = project_name.proposed_path()
    assert path == os.path.join(str(folder), "Test crane.blend")
    assert project_name.folder()[1] == "the first model's folder"
    assert backups.unsaved_name() == "Test crane"             # its backups carry the name too


def test_older_projects_without_an_import_time_take_the_name_order(fresh):
    a = _root("B model", "", 0.0)
    b = _root("A model", "", 0.0)
    del a[build.PROP_IMPORTED], b[build.PROP_IMPORTED]
    assert project_name.model_name() == "A model"
    d, where = project_name.folder()                          # no STEP folder: Documents (or Blender's last folder)
    assert where in ("Documents", "Blender's last folder") and (d != "") == (where == "Documents")


def test_the_setting_leave_empty(fresh, monkeypatch):
    from fresing_render.blender import prefs
    folder = fresh / "m"
    folder.mkdir()
    _root("Crane", str(folder / "crane.stp"), 1.0)
    monkeypatch.setattr(prefs, "get", lambda: type("P", (), {"new_project_name": "empty"})())
    assert project_name.mode() == "empty"
    assert project_name.proposal() == ""
    assert project_name.proposed_path() == str(folder) + os.sep
    assert backups.unsaved_name() == "Crane"                  # a backup always has a name
    monkeypatch.setattr(prefs, "get", lambda: type("P", (), {"new_project_name": "model"})())
    assert project_name.proposal() == "Crane"
    monkeypatch.setattr(prefs, "get", lambda: None)           # no preferences (a background run): the default
    assert project_name.mode() == "model"
    assert prefs.FRESING_AP_prefs.bl_rna.properties["new_project_name"].default == "model"


def test_an_unsaved_projects_backup_is_named_and_offered(fresh, monkeypatch):
    docs = fresh / "Documents"
    docs.mkdir()
    monkeypatch.setattr(backups, "documents", lambda: str(docs))
    monkeypatch.setattr(backups, "state_path", lambda: str(fresh / "config" / core_b.STATE_FILE))
    _root("Crane", "", 1.0, cad_name="Test crane v2")
    backups._S["changes"] += 1
    path = backups.make(force=True)
    assert os.path.basename(path).startswith("Test crane backup ")
    assert os.path.dirname(path) == core_b.unsaved_folder(str(docs))
    b, mt = backups.offer()
    assert b is not None and b.path == path and mt is None


def test_save_as_proposes_the_next_number_and_never_overwrites(fresh):
    folder = fresh / "job é"
    folder.mkdir()
    path = str(folder / "Test crane.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    assert project_name.save_as_proposal() == "Test crane (1)"
    (folder / "Test crane (1).blend").write_bytes(b"x")
    assert project_name.save_as_proposal() == "Test crane (2)"
    # the box's Save: a new file, the project goes on under the new name; the old file stays
    assert bpy.ops.fresing.save_as("EXEC_DEFAULT", name="Test crane (2)") == {"FINISHED"}
    assert bpy.data.filepath == str(folder / "Test crane (2).blend")
    assert os.path.isfile(path)
    assert project_name.save_as_proposal() == "Test crane (3)"
    # a name that is there already is not overwritten
    before = os.path.getsize(folder / "Test crane (1).blend")
    try:
        bpy.ops.fresing.save_as("EXEC_DEFAULT", name="Test crane (1)")
    except RuntimeError:
        pass                                                 # (no file browser in a background Blender)
    assert os.path.getsize(folder / "Test crane (1).blend") == before
    assert bpy.data.filepath == str(folder / "Test crane (2).blend")
    with pytest.raises(RuntimeError):
        bpy.ops.fresing.save_as("EXEC_DEFAULT", name="a/b")      # refused with the reason


def test_save_keeps_a_saved_projects_name(fresh):
    path = str(fresh / "Mill.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    _root("Crane", "", 1.0)
    bpy.context.scene["x"] = 1
    assert bpy.ops.fresing.save("EXEC_DEFAULT") == {"FINISHED"}
    assert bpy.data.filepath == path and not bpy.data.is_dirty


def test_client_view_and_inventory():
    from fresing_render.blender import form_window, lock
    assert lock.allowed("fresing.save")
    assert not lock.allowed("fresing.save_as")
    assert "fresing.save_as" in form_window.POPUPS


def test_the_file_menu_hands_save_and_save_as_to_the_app():
    """The stand-in layout: the first Save and Save As go to the app's operators, Save Copy and the rest stay."""
    calls = []

    class Real:
        operator_context = "x"

        def operator(self, idname, **kw):
            calls.append(idname)
            return type("Props", (), {})()

        def separator(self):
            calls.append("-")

    lay = project_name._Layout(Real())
    lay.operator_context = "INVOKE_AREA"
    lay.operator("wm.open_mainfile")
    lay.operator("wm.save_mainfile", text="Save").show_save_modified_images_dialog = True
    lay.operator("wm.save_as_mainfile", text="Save As...")
    lay.operator("wm.save_as_mainfile", text="Save Copy...").copy = True
    lay.separator()
    assert calls == ["wm.open_mainfile", "fresing.save", "fresing.save_as", "wm.save_as_mainfile", "-"]
    assert lay._real.operator_context == "INVOKE_AREA"
