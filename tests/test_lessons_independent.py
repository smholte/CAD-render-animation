"""Task 0230, the independent tester: trying to break the lessons (bpy module).

Each test says what a user does, what should happen and checks it. Tests marked ``xfail(strict=True)`` show a fault
found in the code as it was handed over (they fail = the fault is still there; a fix turns them into a pass, and the
strict xfail then asks for the mark to go).
"""

import os
import time

import pytest

bpy = pytest.importorskip("bpy")

HERE = os.path.join(os.path.dirname(__file__), "data")
CRANE_A = os.path.join(HERE, "test_crane_a.step")
CRANE_B = os.path.join(HERE, "test_crane_b.step")


@pytest.fixture(scope="module")
def blender():
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    from fresing_render.blender import lesson
    lesson.stop(forget=True)
    fresing_render.unregister()


@pytest.fixture
def les(blender):
    from fresing_render.blender import highlight, lesson
    yield lesson
    lesson.stop(forget=True)
    lesson._remove_handlers()
    highlight.clear()


def cameras(sc):
    return sum(1 for o in sc.objects if o.get("fr_camera"))


# ---------------------------------------------------------------------------
# 1. Show me does a step again that the user already did
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Show me's 'point' phase never looks at done(): a step the user did while the "
                                       "button glowed is done a second time (a third camera)")
def test_show_me_does_not_do_again_what_the_user_did_while_it_pointed(les):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=4)                     # step 5: "A camera view of your own"
    assert lesson.state()["step"] == 4 and lesson.state()["phase"] == "point"
    assert cameras(sc) == 1
    # the user does not wait the 1.6 s: they click the glowing camera button themselves
    assert bpy.ops.fresing.camera_add(view="HIGH") == {"FINISHED"}
    assert cameras(sc) == 2
    lesson.tick(sc, now=time.time() + lesson.SHOW_LATEST + 0.1)
    assert lesson.state()["phase"] == "done"
    assert cameras(sc) == 2, f"Show me added another camera: {cameras(sc)} cameras"


@pytest.mark.xfail(strict=True, reason="the Next button in Show me's 'point' phase runs do() without asking done(): "
                                       "the joint the user made is made a second time")
def test_next_in_show_me_after_the_user_did_the_step(les):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=4)
    assert bpy.ops.fresing.camera_add(view="FRONT") == {"FINISHED"}
    assert bpy.ops.fresing.lesson_next() == {"FINISHED"}
    assert cameras(sc) == 2, f"{cameras(sc)} cameras after Next"


# ---------------------------------------------------------------------------
# 2. a later change to what an earlier step set sends the lesson back
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="where the lesson is = the first step not done: trying another light look "
                                       "later sends the lesson back to step 2, and Show me then puts Product back")
def test_trying_another_light_look_later_does_not_send_the_lesson_back(les):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=4)                    # light look, joints done; at the camera
    assert lesson.state()["step"] == 4
    assert bpy.ops.fresing.light_look(look="WHITE") == {"FINISHED"}   # the user tries White on the way
    assert lesson.do_step(sc)                                   # Do it for me: the camera
    lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    assert lesson.state()["step"] == 5, f"the lesson went to step {lesson.state()['step'] + 1}"


@pytest.mark.xfail(strict=True, reason="the mill's chips step accepts any setting but None: putting the chips back "
                                       "to None later (they slow the view) sends the lesson back to 'Chips'")
def test_mill_chips_off_later_does_not_send_the_lesson_back(les):
    lesson = les
    from fresing_render.blender import machining
    sc = lesson.new_project("mill")
    lesson.start(sc, "mill", "BUILD", at=9)
    assert lesson.state()["step"] == 9
    machining.settings(sc).chips = "NONE"
    assert lesson.do_step(sc)
    lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    assert lesson.state()["step"] == 10, f"the lesson went to step {lesson.state()['step'] + 1}"


# ---------------------------------------------------------------------------
# 3. a step done another way, then "Do it for me" on a later step
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="mill step 11's do finds the axes by the names 'Z' and 'X': with the user's own "
                                       "names its steps point at joints that do not exist, yet done() is true")
def test_mill_axes_with_the_users_own_names_then_do_it_for_me(les):
    lesson = les
    from mathutils import Vector

    from fresing_render.blender import joints, tour
    from fresing_render.blender.lessons import mill
    sc = lesson.new_project("mill")
    lesson.start(sc, "mill", "BUILD", at=2)
    assert lesson.state()["step"] == 2
    for name, (_n, part, d) in zip(("Table", "Carriage", "Head"), mill.AXES):   # made another way, own names
        o = tour._ob(sc, part)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    lesson.tick(sc)
    lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    assert lesson.state()["step"] == 3
    while lesson.step() is not None and lesson.step().function != "animation.joint_step":
        assert lesson.do_step(sc), lesson.state()
        lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    ok = lesson.do_step(sc)
    names = {j.name for j in sc.fresing.joints}
    blocks = [b.joint for a in sc.fresing.animations for b in a.blocks if b.kind == "JOINT"]
    assert ok and blocks and all(b in names for b in blocks), f"the cut's steps move {blocks}; joints {sorted(names)}"


# ---------------------------------------------------------------------------
# 4. the Client view
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="fresing.lesson_* are not in lock.ALLOWED: in the Client view the Lesson "
                                       "panel's Stop / Next / Back are refused while Show me goes on")
def test_client_view_the_lesson_can_still_be_stopped(les):
    lesson = les
    from fresing_render.blender import lock, workspaces
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=2)
    try:
        workspaces.switch(sc, "Client view")
        assert lock.ON[0]
        assert bpy.ops.fresing.lesson_stop.poll(), "Stop the lesson is refused in the Client view"
    finally:
        workspaces.switch(sc, "All functions")


@pytest.mark.xfail(strict=True, reason="Show me's timer goes on editing a project that was switched to the Client "
                                       "view (the boom's joint is made in a locked project)")
def test_client_view_show_me_does_not_edit_the_locked_project(les):
    lesson = les
    from fresing_render.blender import lock, workspaces
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=2)                     # points at "Rotate joint"
    n = len(sc.fresing.joints)
    try:
        workspaces.switch(sc, "Client view")
        assert lock.ON[0]
        lesson.tick(sc, now=time.time() + lesson.SHOW_LATEST + 0.1)
        assert len(sc.fresing.joints) == n, "Show me made a joint in the Client view"
    finally:
        workspaces.switch(sc, "All functions")


def test_client_view_resume_is_refused_not_broken(les):
    """A project saved half-way, opened in the Client view: Go on is refused by the lock (no traceback); after Full
    access it goes on at the right step."""
    lesson = les
    from fresing_render.blender import lock, workspaces
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=3)
    lesson.stop()
    assert sc.get(lesson.KEY) == "crane"
    workspaces.switch(sc, "Client view")
    try:
        assert lock.ON[0]
        assert not bpy.ops.fresing.lesson_resume.poll()
    finally:
        workspaces.switch(sc, "All functions")
    assert bpy.ops.fresing.lesson_resume(mode="BUILD") == {"FINISHED"}
    assert lesson.state()["step"] == 3


# ---------------------------------------------------------------------------
# 5. the Learn window throws away unsaved work
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="Learn > Show me / Build it yourself / a learning list's lesson start a new "
                                       "project (read_homefile) without asking: unsaved work is lost (the test "
                                       "tour's Open asks first, ops_tour.py)")
def test_starting_a_lesson_asks_before_unsaved_work_is_lost(les):
    from fresing_render.blender import ops_learning
    for cls in (ops_learning.FRESING_OT_learn_start, ops_learning.FRESING_OT_learn_lesson):
        assert hasattr(cls, "invoke"), f"{cls.bl_idname} has no invoke: no question before the project is replaced"


# ---------------------------------------------------------------------------
# 6. a model update half-way
# ---------------------------------------------------------------------------

def _root(sc, name="TEST.CRANE"):
    from fresing_render.blender import build
    return next(r for r in build.model_roots(sc))


def test_model_update_half_way_the_lesson_goes_on(les):
    """Build it yourself at the camera step, the model updated to revision B: the done checks still read the project
    (the boom's and the trolley's joints kept) and Do it for me finishes the lesson."""
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=4)
    assert lesson.state()["step"] == 4
    try:
        res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=_root(sc).name)
    except RuntimeError as exc:
        pytest.fail(f"the model update failed: {exc}")
    assert res == {"FINISHED"}
    bpy.context.view_layer.update()
    sc = bpy.context.scene
    from fresing_render.blender import lesson as L
    assert L.first_not_done(sc, L.LESSONS["crane"]) == 4, L.first_not_done(sc, L.LESSONS["crane"])
    lesson.tick(sc)
    assert lesson.state()["step"] == 4 and lesson.state()["phase"] == "wait"
    guard = 0
    while lesson.step() is not None:
        guard += 1
        assert guard < 20
        assert lesson.do_step(sc), lesson.state()
        lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    assert lesson.step() is None


def test_a_removed_part_shows_on_the_card_not_as_a_traceback(les):
    """The boom's part gone from the model: pointing, the card's lines and the panel's text still work; Do it for me
    says why it did not work."""
    lesson = les
    from fresing_render.blender import tour
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=2)
    tour._ob(sc, "BOOM.ASM")["fr_name"] = "GONE"
    lesson._after_undo()                                        # pointing again (as after an undo)
    assert lesson.state()["step"] == 2
    lines = lesson.card_lines(lesson.step(), False, "wait", "BUILD", 3, 11)
    assert lines and lines[0][1] == "title"
    assert not lesson.do_step(sc)
    assert lesson.state()["failed"]
    lines = lesson.card_lines(lesson.step(), False, "wait", "BUILD", 3, 11, lesson.state()["failed"])
    assert any(k == "problem" for _t, k in lines)


# ---------------------------------------------------------------------------
# 7. another project opened while a lesson runs
# ---------------------------------------------------------------------------

def test_opening_another_project_ends_the_lesson_and_leaves_nothing(les, tmp_path):
    lesson = les
    from fresing_render.blender import highlight
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=2)
    assert lesson.running() and highlight.handlers_left()
    path = str(tmp_path / "other.blend")
    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert not lesson.running()
    # the timers that take the load handlers off (they do not run in Blender as a module)
    lesson._remove_handlers()
    highlight._drop_load_handler()
    assert lesson.handlers_left() == [], lesson.handlers_left()
    assert highlight.handlers_left() == [], highlight.handlers_left()
    assert bpy.context.scene.get(lesson.KEY) is None


def test_saved_while_running_reopened_goes_on_in_both_modes(les, tmp_path):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "SHOW", at=5)
    path = str(tmp_path / "half way é.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert not lesson.running() and sc.get(lesson.KEY) == "crane"
    for mode in ("SHOW", "BUILD"):
        assert bpy.ops.fresing.lesson_resume(mode=mode) == {"FINISHED"}
        assert lesson.state()["step"] == 5 and lesson.state()["mode"] == mode
        lesson.stop()


# ---------------------------------------------------------------------------
# 8. done checks on the plain import, and the end state
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lesson_id", ["crane", "mill"])
def test_a_finished_lesson_stays_finished(les, lesson_id):
    """After the last step every step is still done (no later step undid an earlier one: an Explode that takes the
    Build off would send the lesson back)."""
    lesson = les
    sc = lesson.new_project(lesson_id)
    lesson.run(sc, lesson_id)
    L = lesson.LESSONS[lesson_id]
    bad = [f"{i + 1} {st.title}" for i, st in enumerate(L.steps) if not lesson.is_done(sc, st)]
    assert bad == [], bad


def test_crane_saved_scene_alone_does_not_pass_the_explode_step(les):
    """Build it yourself: a scene saved with the boom up (a joint pose, not exploded) must not count as the exploded
    view."""
    lesson = les
    import math

    from fresing_render.blender import joints, states
    from fresing_render.blender.lessons import crane
    sc = lesson.new_project("crane")
    lesson.run(sc, "crane", until=9)
    j = crane.joint_on(sc, "BOOM.ASM", "ROTATE")
    joints.set_value(j, math.radians(20))
    t = crane.joint_on(sc, "TROLLEY.ASM", "SLIDE")
    joints.set_value(t, 0.2)
    bpy.context.view_layer.update()
    states.save_shot(sc, "Boom up a bit")
    assert not lesson.is_done(sc, lesson.LESSONS["crane"].steps[9])


def test_play_on_goes_on_by_itself_and_off_waits(les):
    lesson = les
    from fresing_render.blender import prefs
    p = prefs.get()
    if p is None:
        pytest.skip("no add-on preferences in Blender as a module")
    was = p.lesson_play_on
    try:
        sc = lesson.new_project("crane")
        p.lesson_play_on = True
        lesson.start(sc, "crane", "SHOW", at=1)
        now = time.time()
        lesson.tick(sc, now=now + lesson.SHOW_LATEST + 0.1)
        assert lesson.state()["phase"] == "done"
        lesson.tick(sc, now=time.time() + lesson.PLAY_PAUSE + 0.1)
        assert lesson.state()["step"] == 2
    finally:
        p.lesson_play_on = was


def test_back_at_the_first_step_and_at_the_end_do_not_break(les):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD")
    assert bpy.ops.fresing.lesson_back() == {"FINISHED"}        # nothing to undo in a module: a note, no traceback
    assert lesson.running()
    lesson.stop(forget=True)
    sc = lesson.new_project("crane")
    lesson.run(sc, "crane")
    lesson.start(sc, "crane", "BUILD")
    assert lesson.step() is None and lesson.state()["phase"] == "end"
    assert not bpy.ops.fresing.lesson_do.poll()
    assert bpy.ops.fresing.lesson_next() == {"FINISHED"}
    lesson.tick(sc)


def test_switching_mode_in_the_middle(les):
    lesson = les
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=2)
    n = len(sc.fresing.joints)
    assert bpy.ops.fresing.lesson_mode(mode="SHOW") == {"FINISHED"}
    assert lesson.state()["phase"] == "point"
    lesson.tick(sc, now=time.time() + lesson.SHOW_LATEST + 0.1)
    assert lesson.state()["phase"] == "done" and len(sc.fresing.joints) == n + 1
    assert bpy.ops.fresing.lesson_mode(mode="BUILD") == {"FINISHED"}
    lesson.tick(sc, now=time.time() + lesson.DONE_PAUSE + 0.1)
    assert lesson.state()["step"] == 3 and lesson.state()["phase"] == "wait"


# ---------------------------------------------------------------------------
# 9. undone past the import (many Ctrl+Z): step 1 has no do
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="step 1 (Import) has do=None: Show me / Next / Do it for me 'do' nothing and "
                                       "the card says 'The step was done, but the project does not show it yet'; "
                                       "Next is refused – the lesson is stuck")
@pytest.mark.parametrize("mode", ["SHOW", "BUILD"])
def test_undone_past_the_import_the_lesson_is_not_stuck(les, mode):
    lesson = les
    bpy.ops.wm.read_homefile(use_empty=True)                    # (what undoing the import leaves: no model)
    sc = bpy.context.scene
    lesson.start(sc, "crane", mode)
    assert lesson.state()["step"] == 0
    if mode == "SHOW":
        lesson.tick(sc, now=time.time() + lesson.SHOW_LATEST + 0.1)
        ok = sc.fresing.model_count > 0 or bpy.ops.fresing.lesson_next() == {"FINISHED"}
    else:
        ok = bpy.ops.fresing.lesson_do() == {"FINISHED"}
    misleading = "does not show it yet" in lesson.state()["failed"]
    assert ok and not misleading, lesson.state()


def test_two_quick_starts_of_a_lesson(les):
    """Show me pressed twice (two new projects one after the other): one lesson runs, at step 2, one model."""
    lesson = les
    lesson.open_lesson("crane", "SHOW")
    lesson.open_lesson("crane", "BUILD")
    sc = bpy.context.scene
    assert lesson.running() and lesson.state()["mode"] == "BUILD" and lesson.state()["step"] == 1
    assert sc.fresing.model_count == 1
