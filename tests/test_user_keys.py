"""Task 0330 (bug hunt 0328 rows 2, 3, 4, 8, 35): Build keeps the user's own keys and steps.

Row 2: a key of a built joint changed in the Graph Editor survives the next Build (also the queue's Build), while the
steps that made it stay the same; changed steps replace it, and both are said. Row 3: a faded part with keys of its own
keeps them (they play while built and are back after Stop and a save). Row 4: Turntable again replaces only its own
orbit step. Row 8: a lead slider on a built animation takes the Build off and says so. Row 35: the timeline fit is
asked for after a Build in the app (a timer; nothing in a background run).

Test crane (tests/data), Blender as a Python module.
"""

import math
import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, lead_motions, tour, turntable  # noqa: E402
from fresing_render.core import lead_motions as core  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
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
    tour._boom_joint(sc)
    return sc


def part(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def boom_up(sc, angle=30.0):
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Boom up", "25", 0.0
    tour._joint_step(a, "Boom", 0.0, 2.0, DEG(angle))
    return a


def value_curve(sc):
    j = joints.find(sc, "Boom")
    cb = animation._bag(j.motion)
    return cb.fcurves.find(f'["{joints.VALUE}"]', index=0)


def boom_at(sc, f):
    sc.frame_set(f)
    return joints.get_value(joints.find(sc, "Boom"))


# ---------------------------------------------------------------------------
# row 2: a key changed by hand
# ---------------------------------------------------------------------------

def test_a_changed_key_survives_the_next_build(scene):
    sc = scene
    a = boom_up(sc)
    r = animation.bake(sc, a)
    assert not r["warnings"], r
    fc = value_curve(sc)
    last = fc.keyframe_points[-1]
    f_last = int(round(last.co[0]))
    assert last.co[1] == pytest.approx(DEG(30), abs=1e-4)
    last.co[1] = 0.444                                   # what the owner did in the Graph Editor
    last.handle_left[1] = last.handle_right[1] = 0.444
    assert "joint 'Boom'" in animation.edited_text(sc)
    r = animation.bake(sc, a)                            # Build again (the queue and Ctrl+F12 do the same)
    assert any("Kept your own change" in w and "'Boom'" in w for w in r["warnings"]), r
    assert value_curve(sc).keyframe_points[-1].co[1] == pytest.approx(0.444, abs=1e-5)
    assert boom_at(sc, f_last) == pytest.approx(0.444, abs=1e-4)
    # a third Build keeps it too (the print is of what the steps make, not of the edit)
    r = animation.bake(sc, a)
    assert value_curve(sc).keyframe_points[-1].co[1] == pytest.approx(0.444, abs=1e-5)
    # Stop, then Build: back to the steps' keys, nothing to say
    animation.clear_keys(sc)
    assert animation.PRINT not in sc
    r = animation.bake(sc, a)
    assert not r["warnings"], r
    assert value_curve(sc).keyframe_points[-1].co[1] == pytest.approx(DEG(30), abs=1e-4)


def test_a_changed_key_is_replaced_and_said_when_its_steps_changed(scene):
    sc = scene
    a = boom_up(sc)
    animation.bake(sc, a)
    value_curve(sc).keyframe_points[-1].co[1] = 0.444
    a.blocks[0].to_angle = DEG(20)                       # the step itself changed
    r = animation.bake(sc, a)
    assert any("Build replaced your own change" in w and "'Boom'" in w for w in r["warnings"]), r
    assert value_curve(sc).keyframe_points[-1].co[1] == pytest.approx(DEG(20), abs=1e-4)


def test_two_builds_without_an_edit_say_nothing(scene):
    sc = scene
    a = boom_up(sc)
    animation.bake(sc, a)
    assert animation.edited_text(sc) == ""
    r = animation.bake(sc, a)
    assert not r["warnings"], r


def test_the_queue_says_and_keeps_a_changed_key_from_the_saved_file(scene, tmp_path):
    sc = scene
    a = boom_up(sc)
    animation.bake(sc, a)
    value_curve(sc).keyframe_points[-1].co[1] = 0.444
    path = str(tmp_path / "edited.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)              # what the queue's background copy does
    sc = bpy.context.scene
    assert "joint 'Boom'" in animation.edited_text(sc)
    r = animation.bake(sc, sc.fresing.animations["Boom up"])
    assert any("Kept your own change" in w for w in r["warnings"]), r
    assert value_curve(sc).keyframe_points[-1].co[1] == pytest.approx(0.444, abs=1e-5)


def test_own_keys_on_a_channel_build_keys_are_named(scene):
    sc = scene
    j = joints.find(sc, "Boom")
    j.motion[joints.VALUE] = 0.2
    j.motion.keyframe_insert(f'["{joints.VALUE}"]', frame=10)          # a hand key on the joint
    own = j.motion.animation_data.action
    a = boom_up(sc)
    r = animation.bake(sc, a)
    assert any("joint 'Boom' has keys of your own" in w for w in r["warnings"]), r
    animation.clear_keys(sc)
    assert j.motion.animation_data.action == own                       # back after Stop


# ---------------------------------------------------------------------------
# row 3: a faded part with keys of its own
# ---------------------------------------------------------------------------

def test_a_faded_part_keeps_its_own_keys(scene, tmp_path):
    sc = scene
    cover = part(sc, "COVER")
    z0 = cover.location.z
    cover.keyframe_insert("location", index=2, frame=1)
    cover.location.z = z0 + 0.5
    cover.keyframe_insert("location", index=2, frame=40)
    own = cover.animation_data.action
    own_name = own.name
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Fade and trail", "25", 0.0
    b = a.blocks.add()
    b.kind, b.start, b.duration = "FADE_OUT", 0.5, 1.0
    b.target_uid, b.target_name = cover[build.PROP_UID], "COVER"
    r = animation.bake(sc, a)
    assert not any("own" in w for w in r["warnings"]), r
    assert cover.animation_data.action != own                         # the built keys while built …
    sc.frame_set(40)
    assert cover.location.z == pytest.approx(z0 + 0.5, abs=1e-5)       # … and the hand motion plays along
    sc.frame_set(1)
    assert cover.location.z == pytest.approx(z0, abs=1e-5)
    animation.clear_keys(sc)
    assert cover.animation_data.action == own                         # back after Stop
    path = str(tmp_path / "fade.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert own_name in bpy.data.actions                               # kept over a save
    cov = next(o for o in bpy.context.scene.objects if o.get(build.PROP_NAME) == "COVER")
    assert cov.animation_data.action.name == own_name


# ---------------------------------------------------------------------------
# row 4: Turntable again
# ---------------------------------------------------------------------------

def test_turntable_again_keeps_the_users_steps(scene):
    sc = scene
    s = sc.fresing
    other = s.animations.add()
    other.name = "Mine"
    s.turntable_seconds = 4.0
    a = turntable.make(sc)["animation"]
    s.animations_index = list(s.animations).index(other)
    tour._joint_step(a, "Boom", 1.0, 1.0, DEG(20), label="My step")
    s.turntable_seconds = 6.0
    a2 = turntable.make(sc)["animation"]
    assert a2 == a and len(a.blocks) == 2
    names = [b.name for b in a.blocks]
    assert "My step" in names and "Once round the machine" in names
    orbit = turntable.orbit_block(a)
    assert orbit.duration > 5.0
    assert s.animations[s.animations_index].name == "Mine"           # the picked animation stays picked


def test_turntable_of_an_older_project_finds_its_orbit_by_name(scene):
    sc = scene
    a = turntable.make(sc)["animation"]
    del a.blocks[0][turntable.TAG]                                    # as made before 0.2.247
    turntable.make(sc)
    assert len(a.blocks) == 1 and a.blocks[0].get(turntable.TAG)


# ---------------------------------------------------------------------------
# row 8: a lead slider on a built animation
# ---------------------------------------------------------------------------

def test_a_lead_slider_takes_the_build_off(scene):
    sc = scene
    a = boom_up(sc)
    animation.bake(sc, a)
    lm = lead_motions.add(sc, "Boom up and out", [core.Row("Boom", 0.0, DEG(25))])
    assert animation.has_keys(sc)
    lead_motions.set_position(lm, 100.0)
    assert not animation.has_keys(sc)
    assert sc.fresing.last_message == lead_motions.BUILT_OFF
    sc.frame_set(10)
    sc.frame_set(1)                                   # a frame change no longer snaps it back
    assert joints.get_value(joints.find(sc, "Boom")) == pytest.approx(DEG(25), abs=1e-4)


def test_a_lead_slider_on_a_plain_model_says_nothing(scene):
    sc = scene
    sc.fresing.last_message = ""
    lm = lead_motions.add(sc, "Boom up", [core.Row("Boom", 0.0, DEG(25))])
    lead_motions.set_position(lm, 50.0)
    assert sc.fresing.last_message == ""


# ---------------------------------------------------------------------------
# row 35: the timeline fits a new Build
# ---------------------------------------------------------------------------

def test_the_timeline_fit_runs_only_in_the_app(scene, monkeypatch):
    calls = []
    monkeypatch.setattr(bpy.app.timers, "register", lambda f, **kw: calls.append(f))
    animation.fit_timeline(scene)
    assert calls == []                                # Blender as a module = a background run: no view to fit
