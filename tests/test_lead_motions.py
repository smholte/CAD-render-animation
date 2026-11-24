"""Task 0309: lead motions in the app – the slider moves exactly its joints (followers along), the three ways of making
one (two poses, Record, picking a joint), stages, "moved by …", ▶ / Test / Back to start, the Lead motion step (Build
gives the slider's values, overlap warned), + Add to animation, Show every function, and what is kept: save and reopen,
a model update, a renamed or removed joint, backups; the Client view moves the sliders but cannot edit.

Test crane (tests/data), Blender as a Python module.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, joints, lead_motions, states, tour  # noqa: E402
from fresing_render.blender.lessons import crane  # noqa: E402
from fresing_render.core import lead_motions as core  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")
DEG = math.radians


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    tour._boom_joint(sc)                       # Boom (rotate; the luffing cylinder follows it)
    crane._trolley(sc)                         # Trolley (slide, stacked on the boom)
    return sc


def val(sc, name):
    return joints.get_value(joints.find(sc, name))


def boom_and_trolley(sc):
    return lead_motions.add(sc, "Boom and trolley", [core.Row("Boom", 0.0, DEG(30), 0, 60),
                                                     core.Row("Trolley", 0.0, 1.5, 40, 100, "LINEAR")])


def test_the_slider_moves_its_joints_and_only_those(scene):
    sc = scene
    lm = lead_motions.add(sc, "Boom up", [core.Row("Boom", 0.0, DEG(35))])
    joints.set_value(joints.find(sc, "Trolley"), 0.4)
    for pct in (0.0, 25.0, 50.0, 100.0):
        lm.position = pct
        assert val(sc, "Boom") == pytest.approx(core.values(lead_motions.to_core(lm), pct)["Boom"], abs=1e-6)
        assert val(sc, "Trolley") == pytest.approx(0.4, abs=1e-7)       # not in this lead motion: untouched
    assert val(sc, "Boom") == pytest.approx(DEG(35), abs=1e-6)
    assert lead_motions.status(sc, lm) == ""


def test_windows_order_the_joints(scene):
    sc = scene
    lm = boom_and_trolley(sc)
    lm.position = 25.0
    assert val(sc, "Trolley") == pytest.approx(0.0, abs=1e-7)            # its window starts at 40 %
    assert 0.0 < val(sc, "Boom") < DEG(30)
    lm.position = 50.0
    want = core.values(lead_motions.to_core(lm), 50.0)
    assert val(sc, "Boom") == pytest.approx(want["Boom"], abs=1e-6)
    assert val(sc, "Trolley") == pytest.approx(1.5 * 10 / 60, abs=1e-6)
    lm.position = 100.0
    assert val(sc, "Boom") == pytest.approx(DEG(30), abs=1e-6) and val(sc, "Trolley") == pytest.approx(1.5, abs=1e-6)


def test_a_follower_moves_along_and_is_never_listed(scene):
    from fresing_render.blender import cylinders
    sc = scene
    c = cylinders.find(sc, tour.LUFF)
    assert c is not None
    lm = lead_motions.add(sc, "Boom up", [core.Row("Boom", 0.0, DEG(30))])
    s0 = cylinders.stroke_now(sc, c)
    lm.position = 100.0
    bpy.context.view_layer.update()
    assert cylinders.stroke_now(sc, c) != pytest.approx(s0, abs=1e-4)       # the luffing cylinder followed the boom
    names = {j.name for j in lead_motions.free_joints(sc)}
    assert names == {j.name for j in sc.fresing.joints if not j.follows}


def test_from_two_poses(scene):
    sc = scene
    states.save_pose(sc, "Stowed")
    joints.set_value(joints.find(sc, "Boom"), DEG(20))
    joints.set_value(joints.find(sc, "Trolley"), 0.8)
    states.save_pose(sc, "Working")
    sc.fresing.lead_pose_a, sc.fresing.lead_pose_b = "Stowed", "Working"
    assert bpy.ops.fresing.lead_from_poses() == {"FINISHED"}
    lm = sc.fresing.lead_motions[0]
    assert [(r.joint, round(r.v0, 6), round(r.v1, 6)) for r in lm.rows] == [("Boom", 0.0, round(DEG(20), 6)),
                                                                            ("Trolley", 0.0, 0.8)]
    assert lm.position == 0.0 and val(sc, "Boom") == pytest.approx(0.0, abs=1e-7)   # the model went to the start pose
    lm.position = 100.0
    assert val(sc, "Trolley") == pytest.approx(0.8, abs=1e-6)
    sc.fresing.lead_pose_b = "Stowed"
    assert bpy.ops.fresing.lead_from_poses() == {"CANCELLED"}              # the same pose twice: refused


def test_record_start_and_end(scene):
    sc = scene
    assert not lead_motions.recording(sc)
    assert bpy.ops.fresing.lead_record_start() == {"FINISHED"}
    assert lead_motions.recording(sc)
    with pytest.raises(RuntimeError):                    # nothing moved yet
        lead_motions.record_end(sc, lead_motions.add(sc, "Nothing"))
    joints.set_value(joints.find(sc, "Trolley"), 1.2)
    sc.fresing.lead_index = -1                           # none picked: Set end makes a new one
    assert bpy.ops.fresing.lead_record_end() == {"FINISHED"}
    lm = sc.fresing.lead_motions[-1]
    assert [(r.joint, r.v0, round(r.v1, 6)) for r in lm.rows] == [("Trolley", 0.0, 1.2)]
    assert lm.position == 100.0 and lead_motions.status(sc, lm) == ""   # the slider stands where the model is
    assert not lead_motions.recording(sc)


def test_pick_a_joint_type_values_and_order_by_stages(scene):
    sc = scene
    assert bpy.ops.fresing.lead_new() == {"FINISHED"}
    lm = lead_motions.active(sc)
    for name in ("Boom", "Trolley"):
        sc.fresing.lead_pick = name
        assert bpy.ops.fresing.lead_row_add() == {"FINISHED"}
    boom, trolley = lm.rows
    boom.v1_angle = DEG(25)
    trolley.v1_dist = 1.0
    boom.stage, trolley.stage = 1, 2
    sc.fresing.lead_overlap = 0.0
    assert bpy.ops.fresing.lead_stages() == {"FINISHED"}
    assert (boom.start, boom.end, trolley.start, trolley.end) == (0.0, 50.0, 50.0, 100.0)
    lm.position = 50.0
    assert val(sc, "Boom") == pytest.approx(DEG(25), abs=1e-6) and val(sc, "Trolley") == pytest.approx(0.0, abs=1e-7)
    # a follower cannot be a row
    sc.fresing.lead_pick = next(j.name for j in sc.fresing.joints if j.follows) if any(
        j.follows for j in sc.fresing.joints) else ""
    if sc.fresing.lead_pick:
        assert bpy.ops.fresing.lead_row_add() == {"CANCELLED"}


def test_editing_a_row_moves_the_model_where_the_slider_stands(scene):
    sc = scene
    lm = lead_motions.add(sc, "Boom up", [core.Row("Boom", 0.0, DEG(30))])
    lm.position = 100.0
    lm.rows[0].v1_angle = DEG(10)
    assert val(sc, "Boom") == pytest.approx(DEG(10), abs=1e-6)


def test_two_lead_motions_on_one_joint_the_last_moved_wins(scene):
    sc = scene
    a = boom_and_trolley(sc)
    b = lead_motions.add(sc, "Boom up", [core.Row("Boom", 0.0, DEG(35))])
    a.position = 100.0
    b.position = 50.0
    assert val(sc, "Boom") == pytest.approx(DEG(17.5), abs=1e-6)
    assert lead_motions.status(sc, a) == "moved by Boom up" and lead_motions.status(sc, b) == ""
    a.position = 100.0                                    # moved again: it wins again
    assert lead_motions.status(sc, b) == "moved by Boom and trolley"
    joints.set_value(joints.find(sc, "Trolley"), 0.2)
    assert lead_motions.status(sc, a) == "moved by Boom up" or lead_motions.status(sc, a) == "moved by hand"


def test_play_test_and_back_to_start(scene):
    sc = scene
    a = boom_and_trolley(sc)
    b = lead_motions.add(sc, "Trolley out", [core.Row("Trolley", 0.0, 1.0)])
    assert bpy.ops.fresing.lead_play(index=0) == {"FINISHED"}         # no window: straight to the end
    assert a.position == 100.0 and val(sc, "Trolley") == pytest.approx(1.5, abs=1e-6)
    assert bpy.ops.fresing.lead_play(index=0) == {"FINISHED"}         # again at 100 %: back to 0 %
    assert a.position == 0.0
    assert bpy.ops.fresing.lead_test(index=1) == {"FINISHED"}         # there and back
    assert b.position == 0.0
    a.position, b.position = 100.0, 100.0
    assert bpy.ops.fresing.lead_back_to_start() == {"FINISHED"}
    assert a.position == b.position == 0.0
    assert val(sc, "Boom") == pytest.approx(0.0, abs=1e-7) and val(sc, "Trolley") == pytest.approx(0.0, abs=1e-7)


def _anim(sc):
    assert bpy.ops.fresing.anim_add() == {"FINISHED"}
    a = sc.fresing.animations[sc.fresing.animations_index]
    a.fps = "25"
    return a


def _step_frames(a, b):
    return animation.frame_of(a, b.start), animation.frame_of(a, b.start + b.duration)


def test_build_gives_the_slider_values(scene):
    sc = scene
    lm = boom_and_trolley(sc)
    a = _anim(sc)
    assert bpy.ops.fresing.block_add(kind="LEAD") == {"FINISHED"}
    b = a.blocks[-1]
    assert b.lead == lm.name and b.duration == pytest.approx(lm.seconds)
    assert animation.block_label(b) == "Boom and trolley: where it is → 100 %"
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    f0, f1 = _step_frames(a, b)
    c = lead_motions.to_core(lm)
    for f in (f0, (f0 + f1) // 2, f0 + (f1 - f0) // 4, f1):
        sc.frame_set(f)
        p = core.step_position(0.0, 100.0, b.easing, (f - f0) / (f1 - f0))
        want = core.values(c, p)
        assert val(sc, "Boom") == pytest.approx(want["Boom"], abs=1e-5), f
        assert val(sc, "Trolley") == pytest.approx(want["Trolley"], abs=1e-5), f
    sc.frame_set((f0 + f1) // 2)
    assert (f0 + f1) % 2 == 0                               # a frame exactly in the middle: the slider at 50 %
    want = core.values(c, 50.0)
    assert val(sc, "Boom") == pytest.approx(want["Boom"], abs=1e-5)


def test_a_step_from_where_it_is_and_the_jump_and_overlap_warnings(scene):
    sc = scene
    lm = boom_and_trolley(sc)
    a = _anim(sc)
    b1 = lead_motions.add_step(sc, a, lm, 0.0, 50.0, start=0.0, seconds=2.0, use_from=True)
    b2 = lead_motions.add_step(sc, a, lm, 0.0, 100.0, start=2.0, seconds=2.0, use_from=True)
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    f0, f1 = _step_frames(a, b2)
    sc.frame_set(f0)
    assert val(sc, "Trolley") == pytest.approx(core.values(lead_motions.to_core(lm), 50.0)["Trolley"], abs=1e-5)
    assert "at the same time" not in sc.fresing.last_message and "jumps" not in sc.fresing.last_message
    # From 0 % while it stands at 50 %: it jumps (warned); a joint step on the boom meanwhile: the later one wins
    b2.lead_use_from = False
    j = a.blocks.add()
    j.kind, j.joint, j.start, j.duration, j.to_angle = "JOINT", "Boom", 3.0, 1.0, DEG(5)
    res = animation.bake(sc, a)
    text = " ".join(res.get("warnings", [])) if isinstance(res, dict) else str(res)
    assert "jumps there" in text and "Two steps move 'Boom' at the same time" in text
    from fresing_render.blender.ui_lead_motions import _same_joint_steps
    assert _same_joint_steps(a, b2, {"Boom", "Trolley"}) == [animation.block_label(j)]


def test_add_to_animation_and_show_every_function(scene):
    sc = scene
    boom_and_trolley(sc)
    lead_motions.add(sc, "Trolley out", [core.Row("Trolley", 0.0, 1.0)], seconds=2.0)
    a = _anim(sc)
    a.fin_captions = True
    assert bpy.ops.fresing.lead_add_step(index=1) == {"FINISHED"}
    assert [(b.kind, b.lead, b.lead_from, b.lead_to) for b in a.blocks] == [("LEAD", "Trolley out", 0.0, 100.0)]
    assert bpy.ops.fresing.lead_show_all() == {"FINISHED"}
    steps = [(b.lead, b.lead_from, b.lead_to, round(b.start, 2), b.name) for b in a.blocks][1:]
    assert steps == [("Boom and trolley", 0.0, 100.0, 2.0, "Boom and trolley"), ("Boom and trolley", 100.0, 0.0, 6.0, ""),
                     ("Trolley out", 0.0, 100.0, 10.5, "Trolley out"), ("Trolley out", 100.0, 0.0, 12.5, "")]
    assert bpy.ops.fresing.anim_build() == {"FINISHED"}
    sc.frame_set(sc.frame_end)
    assert val(sc, "Trolley") == pytest.approx(0.0, abs=1e-6)


def test_renaming_kept_through_save_reopen_and_a_model_update(scene, tmp_path):
    sc = scene
    lm = boom_and_trolley(sc)
    a = _anim(sc)
    lead_motions.add_step(sc, a, lm)
    lm.name = "Luff and run"                                 # the step follows the lead motion's new name
    assert a.blocks[0].lead == "Luff and run"
    joints.find(sc, "Trolley").name = "Carriage"             # the row follows the joint's new name
    assert [r.joint for r in lm.rows] == ["Boom", "Carriage"]
    lm.position = 50.0
    path = str(tmp_path / "lead.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    lm = sc.fresing.lead_motions["Luff and run"]
    assert [(r.joint, r.start, r.end) for r in lm.rows] == [("Boom", 0.0, 60.0), ("Carriage", 40.0, 100.0)]
    assert lm.position == 50.0 and lead_motions.status(sc, lm) == ""
    root = __import__("fresing_render.blender.build", fromlist=["x"]).model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name) == {"FINISHED"}
    lm = sc.fresing.lead_motions["Luff and run"]
    assert [r.joint for r in lm.rows] == ["Boom", "Carriage"]
    assert not any(lead_motions.row_problem(sc, r) for r in lm.rows)
    lm.position = 100.0
    assert val(sc, "Carriage") == pytest.approx(1.5, abs=1e-6)


def test_a_removed_joint_marks_its_row_and_the_rest_still_works(scene):
    sc = scene
    lm = boom_and_trolley(sc)
    a = _anim(sc)
    lead_motions.add_step(sc, a, lm, 0.0, 100.0, use_from=False)
    joints.remove(sc, joints.find(sc, "Trolley"))
    lm = sc.fresing.lead_motions["Boom and trolley"]
    assert [lead_motions.row_problem(sc, r) for r in lm.rows] == ["", "missing"]
    lm.position = 100.0
    assert val(sc, "Boom") == pytest.approx(DEG(30), abs=1e-6)
    res = animation.bake(sc, a)
    assert any("'Trolley'" in w and "missing" in w for w in res.get("warnings", []))


def test_a_backup_carries_them(scene, tmp_path):
    from fresing_render.blender import backups
    sc = scene
    boom_and_trolley(sc)
    path = str(tmp_path / "proj.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc.fresing.lead_motions[0].position = 70.0              # a change, so a backup is made
    made = backups.make(sc, force=True, note=False)
    assert made and os.path.isfile(made)
    bpy.ops.wm.open_mainfile(filepath=made)
    lm = bpy.context.scene.fresing.lead_motions["Boom and trolley"]
    assert lm.position == 70.0 and len(lm.rows) == 2


def test_client_view_moves_the_sliders_but_cannot_edit(scene):
    from fresing_render.blender import lock, workspaces
    sc = scene
    lm = boom_and_trolley(sc)
    workspaces.switch(sc, "Client view")
    try:
        assert lock.ON[0]
        assert bpy.ops.fresing.lead_play.poll() and bpy.ops.fresing.lead_back_to_start.poll()
        assert not bpy.ops.fresing.lead_edit.poll() and not bpy.ops.fresing.lead_add_step.poll()
        assert not bpy.ops.fresing.lead_show_all.poll()
        lm.position = 100.0
        assert val(sc, "Trolley") == pytest.approx(1.5, abs=1e-6)
        assert bpy.ops.fresing.lead_back_to_start() == {"FINISHED"}
        assert val(sc, "Trolley") == pytest.approx(0.0, abs=1e-7)
    finally:
        workspaces.switch(sc, "All functions")


def test_the_top_bar_shows_the_button_in_every_workspace(scene):
    from fresing_render.blender import ui_topbar
    from fresing_render.core import functions as F
    funcs = bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    assert ui_topbar._draw_in_editor_menus in funcs
    f = F.FUNCTIONS["motion.lead_motions"]
    assert all(f.shown_in(k) for k in F.WORKSPACE_KEYS)
