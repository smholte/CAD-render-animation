"""Lessons (task 0230): Show me and Build it yourself on the crane and the mill.

* without Blender: the lessons are read from their files (the precheck's way) and every link of the function list
  points at the step that teaches it; a broken link is refused; the card never covers the part;
* in Blender: every step's ``done`` is false before its ``do`` and true after; View (the tour's recipe), Show me and
  Build it yourself make the same project for each set; a step done another way counts; where the lesson is follows
  the scene; a function's lesson opens at its step; nothing runs without a lesson.
"""

import os

import pytest

from fresing_render.core import functions

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LESSONS = os.path.join(ROOT, "fresing_render", "blender", "lessons")


# ---------------------------------------------------------------------------
# without Blender
# ---------------------------------------------------------------------------

def test_the_lessons_are_read_without_blender_and_every_link_is_right():
    steps = functions.read_lessons(LESSONS)
    assert set(steps) == {"crane", "mill"}
    assert len(steps["crane"]) == 11 and 10 <= len(steps["mill"]) <= 13
    assert steps["crane"][0] == steps["mill"][0] == "import.step"
    linked = {f.id: f.lesson for f in functions.FUNCTIONS.values() if f.lesson}
    for fid, link in linked.items():
        name, _, k = link.partition(":")
        assert steps[name][int(k) - 1] == fid, (fid, link)
    # every function a step teaches is linked to one of its steps (the learning list's Show me opens it)
    for name, fids in steps.items():
        for fid in fids:
            assert fid in functions.FUNCTIONS and functions.FUNCTIONS[fid].lesson, (name, fid)
    found = functions.problems(lessons={k: len(v) for k, v in steps.items()}, lesson_steps=steps)
    assert [p for p in found if "lesson" in p] == []


def test_a_broken_lesson_link_is_refused():
    steps = {"crane": ["import.step", "looks.light_look", "no.such"]}
    f = functions.Function(id="joints.rotate", title="Rotate joint", family="motion", panel="FRESING_PT_motion",
                           button="fresing.joint_pick_axis", since="0.2.0", lesson="crane:2")
    g = functions.Function(id="looks.light_look", title="Light look", family="scene", panel="FRESING_PT_scene",
                           button="fresing.light_look", since="0.2.0", lesson="crane:9")
    text = " | ".join(functions.problems([f, g], lessons={"crane": 3}, lesson_steps=steps, duplicates=[]))
    assert "joints.rotate: lesson step 'crane:2' teaches 'looks.light_look', not this function" in text
    assert "looks.light_look: lesson step 'crane:9' does not exist" in text
    assert "lesson 'crane' step 3: the function 'no.such' is not in" in text


def test_the_precheck_reads_the_lessons():
    got = functions.read_repo(ROOT)
    assert got["lessons"] == {"crane": 11, "mill": len(got["lesson_steps"]["mill"])}
    assert functions.problems(**got) == []


def test_claude_md_has_the_lesson_rule():
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as fh:
        text = fh.read()
    assert "Lesson step" in text and "blender/lessons/" in text


# ---------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def test_the_card_never_covers_the_part(blender):
    from itertools import product

    from fresing_render.blender import lesson
    region, size = (1200, 800), (320, 120)
    for x0, y0, w, h in product((0, 100, 500, 900, 1100), (0, 300, 700), (50, 400, 1150), (40, 500, 790)):
        box = (x0, y0, min(1200, x0 + w), min(800, y0 + h))
        cx, cy = lesson.place_card(box, size, region)
        overlap = cx < box[2] and cx + size[0] > box[0] and cy < box[3] and cy + size[1] > box[1]
        fits = box[2] - box[0] < region[0] - size[0] - 100 or box[3] - box[1] < region[1] - size[1] - 100
        assert not overlap or not fits, (box, (cx, cy))
        assert 0 <= cx and cx + size[0] <= region[0]               # never under the side panel (region = free view)


def fingerprint(scene) -> dict:
    """What a lesson makes, in plain values: the same for View, Show me and Build it yourself."""
    from fresing_render.blender import machining
    from fresing_render.core import studio
    s = scene.fresing
    joints = sorted((j.name, j.kind, tuple(sorted(m.obj.get("fr_name", "") for m in j.members if m.obj)))
                    for j in s.joints)
    anims = [(a.name, a.start_shot, [(b.kind, b.joint, round(b.start, 3), round(b.duration, 3),
                                      round(b.to_angle, 4), round(b.to_dist, 5)) for b in a.blocks])
             for a in s.animations]
    m = machining.settings(scene)
    return {"joints": joints, "shots": sorted(sh.name for sh in s.shots), "anims": anims,
            "cameras": sorted(o.name for o in scene.objects if o.get("fr_camera")),
            "queue": sorted(j.kind for j in s.queue), "product": studio.look_matches("PRODUCT", s),
            "baked": s.anim_baked, "bits": sorted(ob.name for _it, ob in machining.bits(scene)),
            "workpiece": m.workpiece.name if m.workpiece else "", "chips": m.chips,
            "materials": sorted((g.name, g.material) for g in s.groups)}


def _show_me_to_the_end(bpy, scene, lesson):
    """Show me as the timer runs it: point, the target 'seen' late (no window here), do, wait, Next."""
    import time
    guard = 0
    while lesson.step() is not None:
        guard += 1
        assert guard < 40
        st = lesson.step()
        assert lesson.state()["phase"] == "point"
        now = time.time()
        lesson.tick(scene, now=now + lesson.SHOW_LATEST + 0.1)
        assert lesson.state()["phase"] == "done", (st.title, lesson.state())
        lesson.tick(scene, now=now + 30)                       # no Play on: it waits
        assert lesson.state()["phase"] == "done"
        assert bpy.ops.fresing.lesson_next() == {"FINISHED"}


def _build_to_the_end(scene, lesson):
    import time
    guard = 0
    while lesson.step() is not None:
        guard += 1
        assert guard < 40
        k = lesson.state()["step"]
        lesson.tick(scene, now=time.time() + 30)               # not done yet: it waits
        assert lesson.state()["step"] == k and lesson.state()["phase"] == "wait"
        assert lesson.do_step(scene), lesson.state()           # Do it for me
        lesson.tick(scene, now=time.time() + lesson.DONE_PAUSE + 0.1)
        assert lesson.state()["step"] > k or lesson.step() is None


@pytest.mark.parametrize("lesson_id", ["crane", "mill"])
def test_view_show_me_and_build_it_yourself_make_the_same_project(blender, lesson_id):
    bpy = blender
    from fresing_render.blender import highlight, lesson
    les = lesson.LESSONS[lesson_id]
    assert lesson.handlers_left() == [] and highlight.handlers_left() == []
    # View: the tour's recipe; every step's done is false before its do and true after
    sc = lesson.new_project(lesson_id)
    assert lesson.first_not_done(sc, les) == 1
    for k, st in enumerate(les.steps[1:], 1):
        assert not lesson.is_done(sc, st), f"step {k + 1} '{st.title}' counts as done before it was done"
        lesson.do(sc, st)
        assert lesson.is_done(sc, st), f"step {k + 1} '{st.title}': done() is false after do()"
        assert lesson.first_not_done(sc, les) == k + 1
    view = fingerprint(sc)
    # Show me
    sc = lesson.new_project(lesson_id)
    lesson.start(sc, lesson_id, "SHOW")
    assert lesson.state()["step"] == 1 and lesson.handlers_left() != []
    _show_me_to_the_end(bpy, sc, lesson)
    show = fingerprint(sc)
    lesson.stop(forget=True)
    # Build it yourself with Do it for me
    sc = lesson.new_project(lesson_id)
    lesson.start(sc, lesson_id, "BUILD")
    _build_to_the_end(sc, lesson)
    build = fingerprint(sc)
    lesson.stop(forget=True)
    assert view == show == build
    assert lesson.handlers_left() == [] and highlight.handlers_left() == []
    assert lesson.KEY not in bpy.context.scene


def test_a_step_done_another_way_counts_and_the_lesson_follows_the_scene(blender):
    import time

    from mathutils import Vector

    from fresing_render.blender import joints, lesson, states, tour
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD")
    lesson.do_step(sc)                                       # the light look
    lesson.tick(sc, now=time.time() + 5)
    assert lesson.state()["step"] == 2
    # the boom's joint made another way: an axis along Y through the boom's origin, not the pin's click
    boom = tour._ob(sc, "BOOM.ASM")
    joints.create(sc, "ROTATE", [boom], boom.matrix_world.translation.copy(), Vector((0, 1, 0)), name="My boom")
    lesson.tick(sc)
    assert lesson.state()["phase"] == "done"
    lesson.tick(sc, now=time.time() + 5)
    assert lesson.state()["step"] == 3
    lesson.do_step(sc)                                       # trolley
    lesson.tick(sc, now=time.time() + 5)
    # a camera from another view (Front) and a scene saved under the user's own name count too
    assert bpy_ops().fresing.camera_add(view="FRONT") == {"FINISHED"}
    lesson.tick(sc)
    lesson.tick(sc, now=time.time() + 5)
    states.save_shot(sc, "Mine")
    lesson.tick(sc)
    lesson.tick(sc, now=time.time() + 5)
    assert lesson.state()["step"] == 6
    # taking something away in the scene (as undo does) moves the lesson back to that step
    sc.fresing.shots.remove(0)
    lesson._after_undo()
    assert lesson.state()["step"] == 5 and lesson.state()["phase"] == "wait"
    lesson.stop(forget=True)


def bpy_ops():
    import bpy
    return bpy.ops


def test_a_function_opens_its_lesson_at_its_step(blender):
    bpy = blender
    from fresing_render.blender import lesson
    les, k = lesson.of_function("animation.joint_step")
    assert les.id == "crane" and les.steps[k].function == "animation.joint_step" and k == 7
    assert lesson.of_function("looks.decals") == (None, -1)
    lesson.open_lesson("crane", "SHOW", at=k)
    sc = bpy.context.scene
    assert lesson.state()["step"] == k and lesson.state()["phase"] == "point"
    assert lesson.first_not_done(sc, les) == k
    assert sc[lesson.KEY] == "crane"
    lesson.stop()
    # the project remembers the lesson (saved half-way and opened again: its panel offers to go on)
    assert sc.get(lesson.KEY) == "crane"
    assert bpy.ops.fresing.lesson_resume(mode="BUILD") == {"FINISHED"}
    assert lesson.state()["step"] == k and lesson.state()["mode"] == "BUILD"
    assert bpy.ops.fresing.lesson_stop() == {"FINISHED"}
    assert lesson.KEY not in sc and lesson.handlers_left() == []


def test_a_step_that_fails_says_why_and_stays(blender):
    from fresing_render.blender import lesson, tour
    sc = lesson.new_project("crane")
    lesson.start(sc, "crane", "BUILD", at=2)
    pin = tour._ob(sc, "BOOM.ASM")
    pin["fr_name"] = "SOMETHING ELSE"                        # the part the step needs is gone (a model update)
    assert not lesson.do_step(sc)
    assert lesson.state()["step"] == 2 and "BOOM.ASM" in lesson.state()["failed"]
    lesson.stop(forget=True)
