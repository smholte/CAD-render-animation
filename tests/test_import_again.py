"""Task 0289: a dropped file comes in like Import STEP…, the Imported models fold (Import again, Remove from cache), and
a model's Up axis changed after its import (joints, poses, Build, save + reopen, model update keep working)."""

import math
import os
import shutil
import time

import pytest

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, logic, ops_import, panels, states  # noqa: E402
from fresing_render.core import import_cache  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CRANE_A = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
PIVOT = Vector((0.1, 0.3, 0.4))
TOL = 1e-4


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    ops_import.use_cache_root(None)
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    ops_import.use_cache_root(str(tmp_path / "cache"))
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    return sc


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def copy_of(tmp_path, src=CRANE_A, name="crane.step"):
    d = tmp_path / "models"
    d.mkdir(exist_ok=True)
    dst = str(d / name)
    shutil.copy(src, dst)
    return dst


# ---------------------------------------------------------------------------------------------------------
# 1. drop = button
# ---------------------------------------------------------------------------------------------------------

class _Dropped:
    """Stands in for the operator a FileHandler calls (Blender as a module never calls ``invoke``; the real-app test
    ``tools/ui_test_import_again.py`` drops through the real invoke): what ``invoke`` hands to ``_dropped``."""

    def __init__(self, directory, names, scene):
        self.files = [type("F", (), {"name": n})() for n in names]
        self.directory = directory
        self.reports = []
        s = scene.fresing
        self.quality, self.up_axis = s.import_quality, s.import_up_axis    # as invoke takes them

    def execute(self, context):
        path = os.path.join(self.directory, self.files[0].name)
        return bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=path, quality=self.quality, up_axis=self.up_axis)

    def report(self, kind, text):
        self.reports.append((kind, text))


def test_a_drop_takes_the_panels_choices_and_opens_1_import(scene, tmp_path):
    s = scene.fresing
    s.import_quality, s.import_up_axis = "draft", "Y"
    panels.OPEN.discard(ops_import.PANEL)
    panels._TAB["v"] = "3"                                   # another section's tab was chosen
    path = copy_of(tmp_path)
    op = _Dropped(os.path.dirname(path), [os.path.basename(path)], scene)
    assert ops_import._dropped(op, bpy.context) == {"FINISHED"}
    assert panels.is_open(ops_import.PANEL) and panels.tab() == "ALL"
    root = build.model_roots(scene)[0]
    assert root["fr_quality"] == "draft"                     # the panel's Detail …
    assert logic.up_axis_of(root) == "Y"                     # … and Up axis, as the button
    assert s.last_message == "Imported crane.step" and not op.reports
    fh = bpy.types.FRESING_FH_step
    assert fh.bl_import_operator == "fresing.import_step" and ".step" in fh.bl_file_extensions


def test_several_files_dropped_import_the_first_and_say_so(scene, tmp_path):
    a = copy_of(tmp_path, name="a.step")
    copy_of(tmp_path, CRANE_B, name="b.step")
    op = _Dropped(os.path.dirname(a), ["a.step", "b.step"], scene)
    assert ops_import._dropped(op, bpy.context) == {"FINISHED"}
    assert len(build.model_roots(scene)) == 1
    msg = scene.fresing.last_message
    assert msg.startswith("Imported a.step") and "2 files dropped: a.step is imported" in msg
    assert op.reports and op.reports[0][0] == {"WARNING"}


def test_show_import_panel_leaves_its_own_tab(scene):
    panels._TAB["v"] = "1"
    ops_import.show_import_panel(bpy.context)
    assert panels.tab() == "1" and panels.is_open(ops_import.PANEL)
    panels._TAB["v"] = "ALL"


# ---------------------------------------------------------------------------------------------------------
# 2. Imported models: Import again, Remove from cache
# ---------------------------------------------------------------------------------------------------------

def _entries():
    return import_cache.entries(ops_import.cache_root())


def test_the_cache_lists_what_was_imported_newest_first(scene, tmp_path):
    a = copy_of(tmp_path, name="first.step")
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    time.sleep(0.05)
    b = copy_of(tmp_path, CRANE_B, name="second.step")
    assert bpy.ops.fresing.import_step(filepath=b, quality="draft") == {"FINISHED"}
    items = _entries()
    assert [e.name for e in items] == ["second", "first"]
    e = items[1]
    assert e.source == os.path.abspath(a) and e.quality == "draft" and e.kind == "step"
    assert e.parts > 10 and e.size > 10_000 and e.state == import_cache.OK
    assert import_cache.size_text(e.size).endswith(("KB", "MB"))
    assert import_cache.date_text(e.stored).startswith("today ")
    assert import_cache.matches(e, "FIRST") and not import_cache.matches(e, "second")


def test_import_again_of_an_unchanged_file_reads_nothing(scene, tmp_path, monkeypatch):
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    e = _entries()[0]

    def no_reading(*_a, **_k):
        raise AssertionError("the file was read again")
    monkeypatch.setattr(ops_import.ImportJob, "start", no_reading)
    assert bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id) == {"FINISHED"}
    roots = build.model_roots(scene)
    assert len(roots) == 2 and roots[1]["fr_quality"] == "draft"
    assert scene.fresing.last_message == "Imported crane.step (from cache: file unchanged since last import)"
    assert len(_entries()) == 1


def test_import_again_of_a_changed_file_reads_it_again(scene, tmp_path):
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    shutil.copy(CRANE_B, a)                                   # a new revision under the same name
    st = os.stat(a)
    os.utime(a, (st.st_atime, st.st_mtime + 5))
    e = _entries()[0]
    assert e.state == import_cache.CHANGED
    assert bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id) == {"FINISHED"}
    assert scene.fresing.last_message.endswith("(the file had changed since it was stored: read again)")
    items = _entries()                                         # the new copy replaced the old one of the same file
    assert len(items) == 1 and items[0].state == import_cache.OK and items[0].id != e.id


def test_import_again_of_a_moved_file_takes_the_stored_copy(scene, tmp_path):
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    n_parts = len(list(build.iter_parts(scene)))
    os.rename(a, a + ".moved")
    e = _entries()[0]
    assert e.state == import_cache.MOVED and import_cache.state_text(e) == "file moved"
    assert bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id) == {"FINISHED"}
    assert len(build.model_roots(scene)) == 2 and len(list(build.iter_parts(scene))) == 2 * n_parts
    assert "the file was moved" in scene.fresing.last_message


def test_remove_from_cache_frees_the_folder_and_keeps_the_model(scene, tmp_path):
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    e = _entries()[0]
    assert bpy.ops.fresing.cache_remove("EXEC_DEFAULT", entry=e.id) == {"FINISHED"}
    assert not os.path.exists(e.folder) and not _entries()
    assert "freed" in scene.fresing.last_message and len(build.model_roots(scene)) == 1
    assert bpy.ops.fresing.cache_remove("EXEC_DEFAULT", entry=e.id) == {"CANCELLED"}
    assert bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id) == {"CANCELLED"}       # said as a warning


def test_remove_never_leaves_the_cache_folder(tmp_path):
    outside = tmp_path / "x"
    outside.mkdir()
    e = import_cache.Entry(folder=str(outside), name="x", source="")
    assert not import_cache.remove(e, str(tmp_path / "cache")) and outside.exists()


# ---------------------------------------------------------------------------------------------------------
# 3. Up axis after the import
# ---------------------------------------------------------------------------------------------------------

def _set_up(sc, tmp_path):
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    root = build.model_roots(sc)[0]
    j = joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], PIVOT, Vector((0.0, 0.0, 1.0)), ref=ob(sc, "BOOM.PIN"))
    joints.set_value(j, math.radians(35))
    pose = sc.fresing.poses.add()
    pose.name = "Turned"
    states.capture_pose(sc, pose)
    joints.set_value(j, 0.0)
    an = sc.fresing.animations.add()
    an.name = "Turn"
    b = an.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j.name, 0.0, 2.0, "LINEAR"
    b.use_from, b.to_angle = True, math.radians(80)
    return root, j, an


def _tip(sc):
    """A point on the boom's far end, in the world."""
    p = ob(sc, "BOOM.ASM")
    bpy.context.view_layer.update()
    return p.matrix_world @ Vector((1.0, 0.0, 0.0))


def _at_frames(sc, an, frames=(1, 20, 40)):
    animation.bake(sc, an)
    out = []
    for f in frames:
        sc.frame_set(f)
        out.append(_tip(sc))
    sc.frame_set(1)
    return out


TURN_Y = Matrix.Rotation(math.radians(90), 4, "X")


def test_up_axis_turns_the_model_and_keeps_joints_poses_and_build(scene, tmp_path):
    sc = scene
    root, j, an = _set_up(sc, tmp_path)
    jname = j.name
    assert logic.up_axis_of(root) == "Z"
    before = _at_frames(sc, an)
    states.apply_pose(sc, "Turned")
    posed = _tip(sc)
    joints.set_value(joints.find(sc, jname), 0.0)
    animation.bake(sc, an)
    assert animation.has_keys(sc)

    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Y") == {"FINISHED"}
    assert logic.up_axis_of(root) == "Y"
    assert not animation.has_keys(sc)                         # the Build was taken off …
    assert sc.fresing.last_message.endswith("Build again")    # … and the panel says so
    after = _at_frames(sc, an)                               # Build again: the same motion, turned
    for p0, p1 in zip(before, after):
        assert (TURN_Y @ p0 - p1).length < TOL
    animation.clear_keys(sc)
    states.apply_pose(sc, "Turned")
    assert (TURN_Y @ posed - _tip(sc)).length < TOL
    joints.set_value(joints.find(sc, jname), 0.0)            # as before the first Build
    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Y") == {"CANCELLED"}   # already

    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Z") == {"FINISHED"}
    again = _at_frames(sc, an)
    for p0, p1 in zip(before, again):
        assert (p0 - p1).length < TOL


def test_one_undo_step(scene, tmp_path):
    op = bpy.types.FRESING_OT_model_up_axis
    assert "UNDO" in op.bl_options


def test_free_cameras_turn_with_a_lone_model(scene, tmp_path):
    sc = scene
    a = copy_of(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=a, quality="draft") == {"FINISHED"}
    root = build.model_roots(sc)[0]
    cam = sc.camera
    m0 = cam.matrix_world.copy()
    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Y") == {"FINISHED"}
    assert ((TURN_Y @ m0).translation - cam.matrix_world.translation).length < TOL


def test_the_axis_stays_through_save_reopen_and_a_model_update(scene, tmp_path):
    sc = scene
    root, j, an = _set_up(sc, tmp_path)
    jname = j.name                                            # items go stale when the collection changes
    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Y") == {"FINISHED"}
    tip = _tip(sc)
    path = str(tmp_path / "up.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    root = build.model_roots(sc)[0]
    assert logic.up_axis_of(root) == "Y"
    assert (_tip(sc) - tip).length < TOL
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    root = build.model_roots(sc)[0]
    assert logic.up_axis_of(root) == "Y"                      # the new revision keeps the chosen axis
    assert joints.find(sc, jname) is not None
    assert sc.fresing.import_up_axis == "Z"                   # the panel's own choice is the next import's default


def test_import_again_of_a_mesh_model(scene, tmp_path, monkeypatch):
    a = copy_of(tmp_path, os.path.join(DATA, "test_mesh_crane.glb"), name="mesh crane.glb")
    assert bpy.ops.fresing.import_mesh(filepath=a) == {"FINISHED"}
    e = _entries()[0]
    assert e.kind == "mesh" and e.quality == "mesh"

    def no_reading(*_a, **_k):
        raise AssertionError("the file was read again")
    monkeypatch.setattr(ops_import.ImportJob, "start", no_reading)
    assert bpy.ops.fresing.import_mesh("EXEC_DEFAULT", again=e.id) == {"FINISHED"}
    roots = build.model_roots(scene)
    assert len(roots) == 2 and all(r["fr_quality"] == "mesh" for r in roots)
    assert bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=roots[1].name, axis="Y") == {"FINISHED"}
    assert logic.up_axis_of(roots[1]) == "Y" and logic.up_axis_of(roots[0]) == "Z"
