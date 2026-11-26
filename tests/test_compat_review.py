"""Task 0352, independent review: tests that try to break the compatibility kit (written by an agent that did not
write it). A FAILING test shows a fault; tests marked "DESIGN QUESTION" show a behaviour the author / lead should
decide on (they fail today on purpose). Tests marked "HELD" passed and stay as guards."""

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
    compat.STATE["aside"].clear()
    yield compat
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    compat.STATE["aside"].clear()


def _save_newer(path, fmt=None, by="9.8.7", extra_object=None):
    """A project as a newer app would save it (its stamp above this app's FORMAT), written without our save hook."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    sc = bpy.context.scene
    if extra_object:
        sc.collection.objects.link(bpy.data.objects.new(extra_object, None))
    sc[core.STAMP] = core.FORMAT + 1 if fmt is None else fmt
    sc[core.STAMP_APP] = by
    bpy.app.handlers.save_pre.remove(compat._before_save)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    finally:
        bpy.app.handlers.save_pre.insert(0, compat._before_save)
    with open(path, "rb") as fh:
        return fh.read()


def _stamp_in_file(path):
    """The stamps of a file's scenes, read with this app's own load (the file stays as it is)."""
    from fresing_render.core import compat as core
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        names = list(src.scenes)
    bpy.ops.wm.open_mainfile(filepath=path)
    return {sc.name: sc.get(core.STAMP) for sc in bpy.data.scenes if sc.name in names}


# ---------------------------------------------------------------------------
# 1. a newer project reaching disk
# ---------------------------------------------------------------------------

def test_a_second_newer_file_at_the_same_path_is_kept_aside_too(fresh, tmp_path):
    """BUG: STATE["aside"] outlives the load. A colleague's newer app saves the file again (new content at the same
    path); opened and saved here in the same session, the new content is written over WITHOUT a copy aside, because
    the path is still in STATE["aside"] from the first time."""
    p = str(tmp_path / "Shared.blend")
    _save_newer(p, by="9.8.7")
    bpy.ops.wm.open_mainfile(filepath=p)
    bpy.ops.wm.save_mainfile()                                  # aside #1 made, file now this app's write
    first_aside = str(tmp_path / "Shared (Fresing Render 9.8.7).blend")
    assert os.path.isfile(first_aside)
    second = _save_newer(p, by="9.8.7", extra_object="Made by the colleague")   # the newer app saved it again
    bpy.ops.wm.open_mainfile(filepath=p)
    assert fresh.newer() is not None
    bpy.ops.wm.save_mainfile()
    kept = [f for f in os.listdir(tmp_path) if f.startswith("Shared (")]
    assert any(open(str(tmp_path / f), "rb").read() == second for f in kept), \
        f"the colleague's second newer save was written over with no copy aside (files: {kept})"


def test_a_failed_copy_aside_still_lets_the_save_write_over(fresh, tmp_path, monkeypatch):
    """RISK: when the copy aside fails (disk full, a virus scanner holding the file, a share that refuses the new
    name), save_hook only prints and Blender's save goes on: the newer file is written over and nothing of it is
    kept. Blender cannot cancel a save from save_pre – but the hook could e.g. move the file aside with os.replace,
    or (as a last resort) raise so the user sees it. Today: silent loss."""
    from fresing_render.blender import compat
    p = str(tmp_path / "Newer.blend")
    original = _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p)

    def refuse(*_a, **_k):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(compat.shutil, "copy2", refuse)
    bpy.ops.wm.save_mainfile()          # the "Save changes?" question when closing, Update now
    kept = [f for f in os.listdir(tmp_path) if f != "Newer.blend" and f.endswith(".blend")]
    assert open(p, "rb").read() == original or kept, "the newer file was written over and no copy of it exists"


def test_save_as_from_a_copy_back_onto_the_newer_original_keeps_it_aside(fresh, tmp_path):
    """RISK: the aside copy is made only when the target is the path the newer project was OPENED from. Open the
    newer file, Save As a copy, open the copy (or: Recover last session), then Save As back onto the original
    name (Blender's browser asks "overwrite?" – a user says yes, it is "the same project"): the newer original's
    own bytes are gone and no copy aside is made. A rule that would hold: while look-only, any save onto an
    existing file other than the open one first copies that file aside."""
    p = str(tmp_path / "Original.blend")
    original = _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p)
    q = str(tmp_path / "Working copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=q)
    bpy.ops.wm.open_mainfile(filepath=q)
    assert fresh.newer() is not None                            # the copy is look-only too (held)
    bpy.ops.wm.save_as_mainfile(filepath=p)
    kept = [f for f in os.listdir(tmp_path) if f.startswith("Original (")]
    assert open(p, "rb").read() == original or any(open(str(tmp_path / f), "rb").read() == original for f in kept), \
        "the newer original was written over by Save As from its copy, no copy aside"


def test_reregistering_the_app_keeps_a_newer_project_look_only(fresh, tmp_path):
    """BUG: compat.unregister() clears STATE["newer"], and register() does not read the open file again. After the
    extension is switched off and on (Preferences, an extension update / reload, a script) while a newer project is
    open, nothing is blocked any more AND the next save stamps the newer data with this app's lower FORMAT – the
    file then opens as an ordinary project here and in the newer app, its "newer" mark is lost for good. Two cheap
    fixes: register() runs check_open() on the open file; save_hook never LOWERS a stamp it finds (with or without
    STATE)."""
    import fresing_render
    from fresing_render.blender import compat, prefs
    from fresing_render.core import compat as core
    p = str(tmp_path / "Newer.blend")
    _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p)
    assert compat.blocked()
    fresing_render.unregister()
    fresing_render.register()
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    still_blocked = bool(compat.blocked())
    q = str(tmp_path / "copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=q, copy=True)
    stamps = _stamp_in_file(q)
    assert stamps == {"Scene": core.FORMAT + 1}, f"the newer stamp was lowered by a save: {stamps}"
    assert still_blocked, "after switching the app off and on, backups / queue / model update are no longer kept out"


def test_a_stamp_is_never_lowered_by_a_save(fresh, tmp_path):
    """BUG (same root as above, without re-registering): any way STATE["newer"] is None while a newer stamp is in
    memory – an appended newer scene, a load that did not reach _on_load, the check failing – makes the save write
    this app's FORMAT over the higher number. save_hook should keep a stamp above FORMAT (and then this file is
    look-only on its next open)."""
    from fresing_render.core import compat as core
    sc = bpy.context.scene
    name = sc.name
    sc[core.STAMP] = core.FORMAT + 3
    sc[core.STAMP_APP] = "9.9.9"
    assert fresh.newer() is None
    q = str(tmp_path / "q.blend")
    bpy.ops.wm.save_as_mainfile(filepath=q, copy=True)
    assert _stamp_in_file(q) == {name: core.FORMAT + 3}


def test_an_appended_newer_scene_does_not_pass_as_this_format(fresh, tmp_path):
    """DESIGN QUESTION: a scene APPENDED (File > Append, libraries.load(link=False)) from a newer project becomes a
    local scene with the newer stamp. Nothing re-checks the open project, the save then writes FORMAT over it, and
    the newer app later treats that data as the old format (its chain would run on data that is already newer).
    Either keep the higher stamp (next open = look-only), or refuse / warn when a newer scene is appended."""
    from fresing_render.core import compat as core
    lib = str(tmp_path / "newer lib.blend")
    _save_newer(lib)
    bpy.ops.wm.read_homefile(use_empty=True)
    fresh.check_open()
    with bpy.data.libraries.load(lib, link=False) as (src, dst):
        dst.scenes = list(src.scenes)
    appended = [sc for sc in bpy.data.scenes if sc.get(core.STAMP) == core.FORMAT + 1]
    assert appended and appended[0].library is None
    name = appended[0].name
    p = str(tmp_path / "ours.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    bpy.ops.wm.open_mainfile(filepath=p)
    assert bpy.data.scenes[name].get(core.STAMP) == core.FORMAT + 1 or fresh.newer() is not None, \
        "the appended newer scene was saved as this app's format"


def test_held_revert_open_another_and_back_and_load_ui_false(fresh, tmp_path):
    """HELD: Revert, opening another project and coming back, and open with load_ui=False keep a newer project
    look-only; the original stays as it was after each."""
    p = str(tmp_path / "Newer.blend")
    original = _save_newer(p)
    bpy.ops.wm.open_mainfile(filepath=p, load_ui=False)
    assert fresh.blocked()
    bpy.ops.wm.revert_mainfile()
    assert fresh.blocked()
    other = str(tmp_path / "Other.blend")
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=other)
    assert not fresh.blocked()
    bpy.ops.wm.open_mainfile(filepath=p)
    assert fresh.blocked()
    assert bpy.ops.fresing.save("EXEC_DEFAULT") == {"CANCELLED"}
    assert open(p, "rb").read() == original


def test_held_aside_name_taken_and_read_only_folder(fresh, tmp_path):
    """HELD: the aside name in use gets " (2)"; the first aside is not touched."""
    p = str(tmp_path / "N.blend")
    original = _save_newer(p)
    taken = tmp_path / "N (Fresing Render 9.8.7).blend"
    taken.write_bytes(b"someone else's file")
    bpy.ops.wm.open_mainfile(filepath=p)
    bpy.ops.wm.save_mainfile()
    assert taken.read_bytes() == b"someone else's file"
    assert (tmp_path / "N (Fresing Render 9.8.7) (2).blend").read_bytes() == original


# ---------------------------------------------------------------------------
# 2. the chain
# ---------------------------------------------------------------------------

def _chain_file(tmp_path, scenes=("Scene",), stamp=1, share_object=False):
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    bpy.ops.wm.read_homefile(use_empty=True)
    compat.check_open()
    first = bpy.context.scene
    for n in scenes[1:]:
        bpy.data.scenes.new(n)
    if share_object:
        ob = bpy.data.objects.new("Shared", None)
        ob["fr_count"] = 0
        for sc in bpy.data.scenes:
            sc.collection.objects.link(ob)
    for sc in bpy.data.scenes:
        sc[core.STAMP] = stamp
    p = str(tmp_path / "chain.blend")
    bpy.app.handlers.save_pre.remove(compat._before_save)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=p, copy=True)
    finally:
        bpy.app.handlers.save_pre.insert(0, compat._before_save)
    return p, first.name


def test_a_failed_step_is_not_claimed_as_done(fresh, tmp_path, monkeypatch):
    """DESIGN QUESTION: when a step fails, run_chain still stamps the scene with FORMAT. The next save writes FORMAT
    and the step can never run again (the data is NOT upgraded but says it is). The brief's "one plain line" keeps
    the project opening; but stamping only up to the last step that worked (or not stamping) would let a fixed
    version try again."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core

    def broken(scene):
        raise RuntimeError("broken step")
    chain = (core.Step(1, 2, "broken", "t:broken"),)
    p, _ = _chain_file(tmp_path)
    monkeypatch.setattr(core, "STEPS", chain)
    monkeypatch.setattr(core, "FORMAT", 2)
    monkeypatch.setattr(core, "BASELINE_FORMAT", 1)
    monkeypatch.setattr(compat, "_resolve", lambda s: broken)
    bpy.ops.wm.open_mainfile(filepath=p)
    assert compat.STATE["failed"]
    assert bpy.context.scene.get(core.STAMP) == 1, "the failed step's project is stamped as upgraded"


def test_a_step_on_data_two_scenes_share_runs_once(fresh, tmp_path, monkeypatch):
    """DESIGN QUESTION: the chain runs per SCENE, but objects, meshes, materials, node groups are shared between
    scenes (a "Linked Copy" scene, an object linked into two scenes – the app's saved scenes and turntable
    scenes do this). A step that converts e.g. an object's stored value in its scene's objects runs twice on it.
    Step.__doc__ says a step "changes only that scene's own data", which a step on shared datablocks cannot keep;
    either run the chain once per FILE (data-level steps) or say in Step's doc that a step must be idempotent per
    datablock (and give it a way to tell, e.g. a per-datablock mark)."""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core

    def bump(scenes):                    # DECIDED (author): a step runs once per FILE and gets the scenes below it
        for ob in {ob for sc in scenes for ob in sc.objects}:
            ob["fr_count"] = ob.get("fr_count", 0) + 1       # e.g. "convert mm to m": not idempotent by nature
    p, _ = _chain_file(tmp_path, scenes=("Scene", "Turntable"), share_object=True)
    monkeypatch.setattr(core, "STEPS", (core.Step(1, 2, "bump", "t:bump"),))
    monkeypatch.setattr(core, "FORMAT", 2)
    monkeypatch.setattr(core, "BASELINE_FORMAT", 1)
    monkeypatch.setattr(compat, "_resolve", lambda s: bump)
    bpy.ops.wm.open_mainfile(filepath=p)
    assert bpy.data.objects["Shared"]["fr_count"] == 1, "a step ran twice on an object two scenes share"


def test_held_a_step_that_does_not_resolve_or_raises_base_errors(fresh, tmp_path, monkeypatch):
    """HELD (the rule changed after the review: the chain stops at a failing step – step n+1 expects n+1's data):
    a step whose function does not exist is one plain line, the project opens at the format it reached and the
    next open tries again. (A step that raises
    SystemExit / KeyboardInterrupt is NOT caught – fine: those must stop.)"""
    from fresing_render.blender import compat
    from fresing_render.core import compat as core
    ran = []
    chain = (core.Step(1, 2, "missing", "no_such_module:nothing"), core.Step(2, 3, "ok", "t:ok"))
    p, _ = _chain_file(tmp_path)
    monkeypatch.setattr(core, "STEPS", chain)
    monkeypatch.setattr(core, "FORMAT", 3)
    monkeypatch.setattr(core, "BASELINE_FORMAT", 1)
    real = compat._resolve
    monkeypatch.setattr(compat, "_resolve",
                        lambda s: (lambda scs: ran.extend(sc.name for sc in scs)) if s.name == "ok" else real(s))
    bpy.ops.wm.open_mainfile(filepath=p)
    assert ran == [] and compat.STATE["failed"] == ["missing"]
    assert bpy.context.scene[core.STAMP] == 1
    assert compat.run_chain() == ([], ["missing"])             # not claimed as done: tried again


# ---------------------------------------------------------------------------
# 3. handler order
# ---------------------------------------------------------------------------

def test_held_handlers_first_after_reregister(fresh, tmp_path):
    """HELD: after the app is switched off and on, _on_load / _before_save are first again."""
    import fresing_render
    from fresing_render.blender import compat, prefs
    fresing_render.unregister()
    fresing_render.register()
    if prefs.get() is None:
        entry = bpy.context.preferences.addons.new()
        entry.module = prefs.ADDON_ID
    assert bpy.app.handlers.load_post[0] is compat._on_load
    assert bpy.app.handlers.save_pre[0] is compat._before_save
    assert bpy.app.handlers.load_pre[0] is compat._before_load


def test_enabling_the_app_inside_a_load_post_handler_skips_the_check(fresh, tmp_path):
    """RISK: Blender calls load_post handlers by index. The app template enables the extension from ITS load_post
    handler (`_after_load`) when the template's add-on list does not have it yet. register() then inserts
    compat._on_load at index 0 of the list being walked: the walk is already past 0, so for THAT load the newer
    check never runs (and the template's handler is called a second time). Measured with the real app in this
    review: a normal start with a file argument (double-click) found the extension already on and DID detect the
    newer file; the gap is a start where the template has to enable it (first start of a fresh settings folder
    with a .blend argument). register() could run check_open() itself when a file is open."""
    import fresing_render
    from fresing_render.blender import compat, prefs
    p = str(tmp_path / "Newer.blend")
    _save_newer(p)
    bpy.ops.wm.read_homefile(use_empty=True)
    fresing_render.unregister()
    calls = []

    @bpy.app.handlers.persistent
    def template_after_load(*_a):                 # app_template/fresing_render/__init__.py _after_load
        calls.append(1)
        if not hasattr(bpy.types.Scene, "fresing"):
            fresing_render.register()
            if prefs.get() is None:
                entry = bpy.context.preferences.addons.new()
                entry.module = prefs.ADDON_ID
    bpy.app.handlers.load_post.append(template_after_load)
    try:
        bpy.ops.wm.open_mainfile(filepath=p)
    finally:
        bpy.app.handlers.load_post.remove(template_after_load)
        if not hasattr(bpy.types.Scene, "fresing"):
            fresing_render.register()
    assert compat.newer() is not None, f"the newer project was not seen (template handler ran {len(calls)} x)"


# ---------------------------------------------------------------------------
# 4. the summary: blind spots and false alarms
# ---------------------------------------------------------------------------

def test_the_summary_sees_a_changed_lead_motion_row(fresh):
    """BUG (blind spot): NOT_CHOICES leaves out every property named "rows" in every group. FRLeadMotion.rows ARE
    the lead motion's choices (joint, value at 0 % / 100 %, window, easing, stage), FRCraneChart.rows are a crane's
    load chart. A changed row is not seen by the test projects' comparison. Bare names in NOT_CHOICES should be
    dotted ("<group>.<prop>") or the list checked against every property group."""
    from fresing_render.core import compat as core
    s = bpy.context.scene.fresing
    lm = s.lead_motions.add()
    lm.name = "Boom up"
    row = lm.rows.add()
    row.joint = "Boom"
    row["v1"] = 0.5
    before = fresh.summary()
    row.easing = "LINEAR" if row.easing != "LINEAR" else "SMOOTH"
    row["v1"] = 0.25
    assert core.compare(before, fresh.summary()), "a lead motion's rows changed and the summary did not see it"


def test_no_bare_name_in_not_choices_hides_a_choice_somewhere(app):
    """BUG (blind spot, wider): every bare name in NOT_CHOICES is left out in EVERY property group. A collection or
    pointer of further settings left out that way hides a whole group of choices. Derived ones (clash rows, the
    structure tree, found parts) are fine; the rest are listed."""
    from fresing_render.core import compat as core
    import fresing_render.blender.props as props
    derived = {"FRClashRow", "FRTreeItem", "FRFoundPart", "FRReportLine"}   # the model update's report: derived
    hidden = []
    for cls in vars(props).values():
        if not (isinstance(cls, type) and issubclass(cls, bpy.types.PropertyGroup) and hasattr(cls, "bl_rna")):
            continue
        for prop in cls.bl_rna.properties:
            if prop.identifier in core.NOT_CHOICES and prop.type == "COLLECTION":
                kind = prop.fixed_type.identifier
                if kind not in derived:
                    hidden.append(f"{cls.__name__}.{prop.identifier} ({kind})")
    assert hidden == [], f"collections of choices hidden by a bare NOT_CHOICES name: {hidden}"


def test_the_summary_sees_a_decal_on_a_parts_mesh(fresh):
    """BUG (blind spot): decals on every copy of a part live in Mesh.fresing_decals; the summary reads only Scene
    and Object groups (+ materials' fr_ properties), so a decal's place, size, picture … on a mesh is not compared."""
    from fresing_render.core import compat as core
    me = bpy.data.meshes.new("Part")
    ob = bpy.data.objects.new("Part", me)
    bpy.context.scene.collection.objects.link(ob)
    d = me.fresing_decals.add()
    d.name = "Logo"
    before = fresh.summary()
    d.name = "Warning sign"
    assert core.compare(before, fresh.summary()), "a decal on a part's mesh changed and the summary did not see it"


def test_the_summary_sees_a_camera_lens(fresh):
    """RISK (blind spot): cameras are a 'scene' family choice (views, the turntable camera), but the summary keeps
    only the camera object's place; a changed lens / sensor / clip or depth of field is only seen through the tiny
    picture, within PICTURE_TOLERANCE (a lens change of a few mm may well stay under 0.02 mean difference)."""
    from fresing_render.core import compat as core
    cam = bpy.data.cameras.new("View")
    ob = bpy.data.objects.new("View", cam)
    bpy.context.scene.collection.objects.link(ob)
    before = fresh.summary()
    cam.lens = 85.0
    cam.dof.use_dof = True
    assert core.compare(before, fresh.summary()), "a camera's lens changed and the summary did not see it"


def test_counts_do_not_alarm_on_derived_datablocks(fresh):
    """DESIGN QUESTION (false alarm): ``counts`` compares datablock numbers exactly. A later version that makes one
    more node group / text / image at load (derived data, e.g. a new shared node group for looks, an icon image)
    fails every kept project though nothing the user chose changed. Compare counts only as "not fewer", or leave
    derived kinds (node_groups, images, texts, actions) out."""
    from fresing_render.core import compat as core
    # DECIDED (author): the summary has no datablock counts any more (objects compare by name; more is allowed)
    from fresing_render.blender import compat
    assert "counts" not in compat.summary()


def test_held_compare_basics():
    """HELD: additions allowed, a missing key and a changed value found, float noise of float32 not an alarm."""
    from fresing_render.core import compat as core
    assert core.compare({"a": 1.0000001}, {"a": 1.0, "b": 2}) == []
    assert core.compare({"a": 1}, {}) == ["a: gone"]
    assert core.compare({"a": [1, 2]}, {"a": [1]})
    assert core.compare({"a": 0.1}, {"a": float(__import__("numpy").float32(0.1))}) == []


def test_held_odd_stamps():
    """HELD: odd stamp values read as no stamp, or as a number when they clearly are one."""
    from fresing_render.core import compat as core
    assert core.as_format(True) is None and core.as_format(-1) is None and core.as_format(0) is None
    assert core.as_format("2") == 2 and core.as_format(2.0) == 2 and core.as_format(2.5) is None
    assert core.as_format({"x": 1}) is None and core.as_format(None) is None
    assert core.file_format([None, "x", 3, 2.0]) == 3


# ---------------------------------------------------------------------------
# 5. the precheck
# ---------------------------------------------------------------------------

def test_precheck_wants_the_whole_kept_project_not_only_its_summary(tmp_path, monkeypatch):
    """NIT: check_compat accepts tests/data/compat/format_<n>/ with only summary.json (no .blend, no picture), a
    summary whose "format" is another number, and kept folders ABOVE FORMAT (e.g. FORMAT lowered by a bad merge)."""
    import importlib
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    pre = importlib.import_module("ci_precheck")
    from fresing_render.core import compat as core
    monkeypatch.setattr(core, "BASELINE_FORMAT", 1)
    monkeypatch.setattr(core, "FORMAT", 1)
    d = tmp_path / "tests" / "data" / "compat" / "format_1"
    d.mkdir(parents=True)
    (d / "summary.json").write_text('{"format": 7, "projects": {"crane": {}}}')
    (tmp_path / "tests" / "data" / "compat" / "format_2").mkdir()
    ((tmp_path / "tests" / "data" / "compat" / "format_2") / "summary.json").write_text('{"format": 2}')
    assert pre.check_compat(str(tmp_path)), "an empty kept folder (summary only, wrong number) and one above " \
                                            "FORMAT pass the precheck"
