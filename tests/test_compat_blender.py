"""Task 0352: the compatibility kit in Blender – the stamp on every save, the chain first on load, a project from a
newer app never damaged (Save, Blender's own save, Save As, backups, the render queue, a model update)."""

import os
import shutil

import pytest

bpy = pytest.importorskip("bpy")


@pytest.fixture(scope="module")
def app():
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
def fresh(app):
    from fresing_render.blender import compat
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    yield compat
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()


def _save_newer(path, fmt=None, by="9.8.7", second_scene=False):
    """A project as a newer app would save it (its stamp above this app's FORMAT)."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    if second_scene:
        bpy.data.scenes.new("Second")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc = bpy.context.scene
    sc[core.STAMP] = core.FORMAT + 1 if fmt is None else fmt
    sc[core.STAMP_APP] = by
    bpy.app.handlers.save_pre.remove(compat._before_save)      # the stamp as written by "the newer app"
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    finally:
        bpy.app.handlers.save_pre.insert(0, compat._before_save)
    with open(path, "rb") as fh:
        return fh.read()


def test_every_save_is_stamped_also_copies_and_backups(fresh, tmp_path):
    from fresing_render import __version__
    from fresing_render.blender import backups
    from fresing_render.core import compat as core
    bpy.data.scenes.new("Second")
    p = str(tmp_path / "Project é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    backups.write_copy(str(tmp_path / "backup.blend"))
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "queue copy.blend"), copy=True)
    for f in ("Project é.blend", "backup.blend", "queue copy.blend"):
        bpy.ops.wm.open_mainfile(filepath=str(tmp_path / f))
        assert len(bpy.data.scenes) == 2
        for sc in bpy.data.scenes:
            assert sc[core.STAMP] == core.FORMAT and sc[core.STAMP_APP] == __version__, f
        assert fresh.project_format() == (core.FORMAT, __version__)
        assert fresh.newer() is None


def test_a_project_without_a_stamp_is_left_alone(fresh, tmp_path):
    from fresing_render.core import compat as core
    p = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    sc = bpy.context.scene
    del sc[core.STAMP]
    bpy.app.handlers.save_pre.remove(fresh._before_save)       # as an app before the kit saved it
    try:
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "plain.blend"), copy=True)
    finally:
        bpy.app.handlers.save_pre.insert(0, fresh._before_save)
    fresh.STATE["ran"] = ["x"]
    bpy.ops.wm.open_mainfile(filepath=str(tmp_path / "plain.blend"))
    assert core.STAMP not in bpy.context.scene        # nothing stamped in memory: made before the kit
    assert fresh.project_format() == (None, "")
    assert fresh.newer() is None and fresh.STATE["ran"] == [] and fresh.blocked() == ""


def test_our_handlers_run_first(fresh, tmp_path):
    from fresing_render.blender import compat
    seen = []

    @bpy.app.handlers.persistent
    def other(*_a):
        seen.append(bpy.app.handlers.load_post.index(compat._on_load))

    bpy.app.handlers.load_post.insert(0, other)       # a later add-on that also wants to be first
    bpy.app.handlers.save_pre.insert(0, other)
    try:
        p = str(tmp_path / "a.blend")
        bpy.ops.wm.save_as_mainfile(filepath=p)
        bpy.ops.wm.open_mainfile(filepath=p)
        assert bpy.app.handlers.load_post[0] is compat._on_load
        assert bpy.app.handlers.save_pre[0] is compat._before_save
        assert seen and seen[-1] == 0
    finally:
        for lst in (bpy.app.handlers.load_post, bpy.app.handlers.save_pre):
            while other in lst:
                lst.remove(other)


def _two_scene_file(tmp_path, compat, core):
    """A file whose scenes were saved at formats 1 ("Scene") and 3 ("Second"), sharing one object."""
    bpy.data.scenes.new("Second")
    shared = bpy.data.objects.new("Shared", None)
    for sc in bpy.data.scenes:
        sc.collection.objects.link(shared)
    p = str(tmp_path / "f1.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    bpy.ops.wm.open_mainfile(filepath=p)
    bpy.data.scenes["Scene"][core.STAMP] = 1
    bpy.data.scenes["Second"][core.STAMP] = 3
    bpy.app.handlers.save_pre.remove(compat._before_save)      # as older versions saved them
    try:
        bpy.ops.wm.save_as_mainfile(filepath=p, copy=True)
    finally:
        bpy.app.handlers.save_pre.insert(0, compat._before_save)
    return p


def _chain(monkeypatch, compat, core, funcs):
    chain = (core.Step(1, 2, "s1", "t:s1"), core.Step(2, 3, "s2", "t:s2"), core.Step(3, 4, "s3", "t:s3"))
    monkeypatch.setattr(core, "STEPS", chain)
    monkeypatch.setattr(core, "FORMAT", 4)
    monkeypatch.setattr(core, "BASELINE_FORMAT", 1)
    monkeypatch.setattr(compat, "_resolve", lambda s: funcs[s.function])


def test_the_chain_runs_first_in_order_and_once_per_file(fresh, tmp_path, monkeypatch):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    calls = []

    def ok(name):
        def f(scenes):
            calls.append((name, sorted(sc.name for sc in scenes), [sc.get(core.STAMP) for sc in scenes]))
            for ob in {ob for sc in scenes for ob in sc.objects}:      # shared data: once
                ob["fr_steps"] = ob.get("fr_steps", 0) + 1
        return f
    p = _two_scene_file(tmp_path, compat, core)
    _chain(monkeypatch, compat, core, {"t:s1": ok("s1"), "t:s2": ok("s2"), "t:s3": ok("s3")})
    seen_by_others = []

    @bpy.app.handlers.persistent
    def later(*_a):                                             # an ordinary Fresing load handler, after ours
        seen_by_others.append({sc.name: sc.get(core.STAMP) for sc in bpy.data.scenes})
    bpy.app.handlers.load_post.append(later)
    try:
        bpy.ops.wm.open_mainfile(filepath=p)
    finally:
        bpy.app.handlers.load_post.remove(later)
    assert calls == [("s1", ["Scene"], [1]), ("s2", ["Scene"], [1]), ("s3", ["Scene", "Second"], [1, 3])]
    assert bpy.data.objects["Shared"]["fr_steps"] == 3          # three steps, each once
    assert seen_by_others[-1] == {"Scene": 4, "Second": 4}      # stamped before the others ran
    assert compat.STATE["ran"] == ["s1", "s2", "s3"] and compat.STATE["failed"] == []
    calls.clear()
    assert compat.run_chain() == ([], []) and calls == []      # it runs once


def test_a_failing_step_stops_the_chain_and_the_project_keeps_the_format_it_reached(fresh, tmp_path, monkeypatch):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    calls = []

    def ok(name):
        def f(scenes):
            calls.append(name)
        return f

    def broken(scenes):
        calls.append("s2")
        raise RuntimeError("step two broke")
    p = _two_scene_file(tmp_path, compat, core)
    _chain(monkeypatch, compat, core, {"t:s1": ok("s1"), "t:s2": broken, "t:s3": ok("s3")})
    bpy.ops.wm.open_mainfile(filepath=p)                       # the project opens
    assert calls == ["s1", "s2"]                               # s3 builds on s2: it waits
    assert compat.STATE["failed"] == ["s2"]
    assert bpy.data.scenes["Scene"][core.STAMP] == 2 and bpy.data.scenes["Second"][core.STAMP] == 3
    q = str(tmp_path / "saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=q)                    # a save keeps what was reached
    calls.clear()
    bpy.ops.wm.open_mainfile(filepath=q)                       # a fixed version would try again from there
    assert calls == ["s2"]


def test_a_newer_project_is_never_saved_over_itself(fresh, tmp_path):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    p = str(tmp_path / "From the future.blend")
    original = _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p)
    note = compat.blocked()
    assert note == core.newer_note("9.8.7", __import__("fresing_render").__version__)
    assert compat.newer()["format"] == core.FORMAT + 1
    assert bpy.context.scene.fresing.last_message == note
    # the app's Save (Ctrl+S, File > Save) is refused
    assert bpy.ops.fresing.save("EXEC_DEFAULT") == {"CANCELLED"}
    assert open(p, "rb").read() == original
    # Blender's own save (the "Save changes?" question, Update now): the newer file is kept aside first
    bpy.ops.wm.save_mainfile()
    aside = str(tmp_path / "From the future (Fresing Render 9.8.7).blend")
    assert os.path.isfile(aside) and open(aside, "rb").read() == original
    bpy.ops.wm.save_mainfile()                                   # a second save keeps the first copy
    assert not os.path.exists(str(tmp_path / "From the future (Fresing Render 9.8.7) (2).blend"))
    assert open(aside, "rb").read() == original
    # what this app wrote keeps the newer stamp: it opens look-only again
    bpy.ops.wm.open_mainfile(filepath=p)
    assert compat.newer() is not None and bpy.context.scene[core.STAMP] == core.FORMAT + 1


def test_save_as_of_a_newer_project_makes_a_copy_that_stays_look_only(fresh, tmp_path):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    p = str(tmp_path / "new.blend")
    original = _save_newer(p, by="0.3.0")
    bpy.ops.wm.open_mainfile(filepath=p)
    q = str(tmp_path / "copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=q)
    assert open(p, "rb").read() == original
    assert not any(f.startswith("new (") for f in os.listdir(tmp_path))      # nothing written over: no copy aside
    assert compat.blocked()                                     # still the newer data in memory
    assert bpy.ops.fresing.save("EXEC_DEFAULT") == {"CANCELLED"}
    bpy.ops.wm.open_mainfile(filepath=q)
    assert compat.newer()["saved_by"] == "0.3.0" and bpy.context.scene[core.STAMP] == core.FORMAT + 1


def test_backups_queue_and_model_update_keep_out(fresh, tmp_path):
    from fresing_render.blender import backups, compat, queue, reimport
    p = str(tmp_path / "newer.blend")
    original = _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p)
    sc = bpy.context.scene
    assert backups.wait_reason(sc) == "a project from a newer Fresing Render"
    assert backups.make(sc, force=True) == ""
    with pytest.raises(RuntimeError, match="newer than this one"):
        queue.start(bpy.context)
    root = bpy.data.objects.new("Model", None)
    sc.collection.objects.link(root)
    with pytest.raises(reimport.UpdateFailed, match="newer than this one"):
        reimport.update_model(bpy.context, root, str(tmp_path))
    assert open(p, "rb").read() == original
    bpy.ops.wm.read_homefile(use_empty=True)                    # another project: back to normal
    assert compat.newer() is None and compat.blocked() == ""
    assert backups.wait_reason(bpy.context.scene) != "a project from a newer Fresing Render"


def test_two_scenes_the_newest_counts_and_a_linked_scene_is_not_ours(fresh, tmp_path):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    lib = str(tmp_path / "library.blend")
    _save_newer(lib)                                             # a newer file, linked into ours
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    with bpy.data.libraries.load(lib, link=True) as (src, dst):
        dst.scenes = list(src.scenes)
    linked = [sc.name for sc in bpy.data.scenes if sc.library is not None]
    assert linked == ["Scene"]
    assert [sc.get(core.STAMP) for sc in bpy.data.scenes if sc.library is not None] == [core.FORMAT + 1]
    p = str(tmp_path / "ours.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    bpy.ops.wm.open_mainfile(filepath=p)
    assert compat.newer() is None                                # a linked scene's stamp is the library's
    assert compat.project_format()[0] == core.FORMAT
    assert [sc.name for sc in bpy.data.scenes if sc.library is not None] == linked   # still linked, not ours
    # two scenes of our own: one newer makes the whole file look-only
    q = str(tmp_path / "two.blend")
    _save_newer(q, second_scene=True)
    bpy.ops.wm.open_mainfile(filepath=q)
    assert {sc.get(core.STAMP) for sc in bpy.data.scenes} == {core.FORMAT, core.FORMAT + 1}
    assert compat.newer() is not None


def test_summary_reads_the_choices_and_leaves_out_derived_data(fresh):
    from fresing_render.blender import compat
    sc = bpy.context.scene
    sc.fresing.last_message = "anything"
    sc.fresing.out_folder = "C:/renders"
    s = compat.summary()
    settings = s["scenes"][sc.name]["settings"]["fresing"]
    assert "last_message" not in settings and "tree" not in settings and "model_count" not in settings
    assert settings["out_folder"] == "C:/renders"
    assert "fresing_measure" in s["scenes"][sc.name]["settings"]


def test_no_format_line_while_blender_data_cannot_be_read(app, capsys, monkeypatch):
    """Task 0371: switched on at start (Blender's data restricted: a ``_RestrictData`` without ``filepath``) the format
    check printed "the project's format could not be read" twice at every start. Now it waits for the load; a format
    that really cannot be read still prints."""
    import types

    from fresing_render.blender import compat

    class _RestrictData:                               # what bpy.data is while add-ons are switched on
        pass

    restricted = types.SimpleNamespace(data=_RestrictData(), types=bpy.types, app=bpy.app)
    called = []
    monkeypatch.setattr(compat, "check_open", lambda *a: called.append(a))
    monkeypatch.setattr(compat, "bpy", restricted)
    assert not compat.data_readable()
    compat.register()
    compat._on_load("")
    assert called == []
    assert "could not be read" not in capsys.readouterr().out
    monkeypatch.setattr(compat, "bpy", bpy)
    assert compat.data_readable()

    def broken(*_a):
        raise ValueError("the stamp is not a number")
    monkeypatch.setattr(compat, "check_open", broken)
    compat.register()
    compat._on_load("")
    out = capsys.readouterr().out
    assert out.count("the project's format could not be read: the stamp is not a number") == 2
