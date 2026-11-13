"""Vessel motion at sea (task 0085).

The maths (``core/vessel_motion.py``) is checked without Blender: the sea states' numbers, headings, long and short
waves, the roll period, Strength. Inside Blender (as a Python module): the rig matches the maths, every part moves
with its root, the sea and the camera stay, amplitudes and periods measured from the evaluated scene over 120 s,
off = exactly as before, save/reopen, model update, the queue's background copy, stays still / level.
(Scripts off is proved in the real program: ``tools/ui_test_vessel.py``.)
"""

import json
import math
import os
import subprocess
import sys

import numpy as np
import pytest

from fresing_render.core import vessel_motion as V

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
CRANE_B = os.path.join(HERE, "data", "test_crane_b.step")

# the sea's own waves, as blender/surroundings.py makes them (checked against it in a Blender test below): since
# task 0109 a wind-wave spectrum (core/sea.py), Calm = Beaufort 3, Rough = Beaufort 6
def sea_waves(state):
    from fresing_render.core import sea
    return V.waves_from_tuples(sea.of_state(state))


def motion(state="CALM", heading="BOW", size=V.REFERENCE_SIZE, **kw):
    return V.motion(V.Settings(state=state, heading=heading, length=size[0], beam=size[1], **kw), sea_waves(state))


# ---------------------------------------------------------------------------
# the maths (no Blender)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["CALM", "ROUGH"])
@pytest.mark.parametrize("size", [V.REFERENCE_SIZE, (64.0, 18.3)])
def test_sea_state_matches_its_table(state, size):
    """Bow quarter (the default heading): peaks and mean periods of every 120 s stretch of the first 10 minutes lie
    in the table (Calm = the reference study 0083: roll 1-1.5° at 10-12 s, pitch 0.3-0.6° at 6-8 s, heave
    0.2-0.4 m at 7-9 s)."""
    m = motion(state, "BOW", size)
    table = V.TABLE[state]
    for start in (0.0, 120.0, 240.0, 360.0, 480.0):
        r = V.measure(m, 120.0, 0.04, start)
        for k, (lo, hi) in table.items():
            assert lo <= r[k] <= hi, (state, size, start, k, round(r[k], 3), (lo, hi))


def test_heading_shares_the_motion():
    """A beam sea rolls the most, head and following seas the least; a head sea pitches at least as much as a beam
    sea. Calm in a beam sea stays gentle (at most 2°, the old pipelay limit)."""
    roll = {h: V.measure(motion("CALM", h), 600.0, 0.05)["roll"] for h in V.HEADINGS}
    pitch = {h: V.measure(motion("CALM", h), 600.0, 0.05)["pitch"] for h in V.HEADINGS}
    assert roll["BEAM"] > roll["BOW"] > roll["HEAD"] and roll["BEAM"] > roll["FOLLOWING"]
    assert roll["BEAM"] <= 2.0, roll
    assert roll["HEAD"] < 0.5 * roll["BOW"] and roll["FOLLOWING"] < 0.5 * roll["BOW"]
    assert pitch["HEAD"] >= 0.9 * pitch["BEAM"], pitch


def test_long_waves_move_the_vessel_short_ones_do_not():
    """A 124 m vessel ignores 13 m ripples and rides a 400 m swell."""
    short = V.Wave(0.3, 1.0, 0.0, 2 * math.pi / 13.0, 0.0)
    long_ = V.Wave(0.3, 1.0, 0.0, 2 * math.pi / 400.0, 0.0)
    rs = V.raw([short], 124.0, 28.0)
    rl = V.raw([long_], 124.0, 28.0)
    assert abs(rs.heave.terms[0][0]) < 0.05 * 0.3 and abs(rl.heave.terms[0][0]) > 0.8 * 0.3
    assert abs(rs.pitch.terms[0][0]) < 0.05 * abs(rl.pitch.terms[0][0])


@pytest.mark.parametrize("heading", list(V.HEADINGS))
def test_rises_when_a_crest_passes(heading):
    """Heave follows the long swell the sea shows under the hull's middle (same waves, same phases): a crest under
    the vessel lifts it (the Vessel deck's 64 m hull; a 124 m hull averages waves shorter than itself)."""
    m = motion("CALM", heading, (64.0, 18.3))
    t = np.arange(0, 600, 0.1)
    sea = sum(w.amp * np.sin(w.phase - w.omega * t) for w in V.swell("CALM", heading))
    assert np.corrcoef(sea, m.heave.value(t))[0, 1] > 0.9


def test_roll_period_follows_the_setting():
    for period in (8.0, 11.0, 14.0):
        r = V.measure(motion("CALM", "BEAM", roll_period=period), 600.0, 0.04)
        assert abs(r["roll_s"] - period) < 0.12 * period, (period, r["roll_s"])


def test_strength():
    still = motion(strength=0.0)
    assert all(V.measure(still, 120.0)[k] == 0.0 for k in ("roll", "pitch", "heave"))
    one, two = V.measure(motion(strength=1.0), 120.0), V.measure(motion(strength=2.0), 120.0)
    for k in ("roll", "pitch", "heave"):
        assert abs(two[k] - 2 * one[k]) < 1e-6 * max(1.0, one[k])


def test_mixed_and_not_repeating():
    """Several waves of unrelated periods: two stretches of the motion are never the same."""
    m = motion("CALM", "BOW")
    assert len(m.roll.terms) >= 5 and len(m.heave.terms) >= 5
    t = np.arange(0, 120, 0.1)
    a, b = m.roll.value(t), m.roll.value(t + 300.0)
    assert np.max(np.abs(a - b)) > 0.3 * np.max(np.abs(a))


def test_header_words():
    assert V.summary("CALM", 1.0, 1.24) == "Calm · roll ±1.2°"
    assert V.summary("ROUGH", 0.0, 0.0) == "Rough · still"


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, surroundings, vessel_motion as VM  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update():
    bpy.context.view_layer.update()


def fresh(background="DECK", detail="DETAILED", heading="BOW", on=True, path=CRANE_A):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    s.env_detail = detail
    s.background = background
    s.vessel.heading = heading
    s.vessel.enabled = on
    update()
    return sc


def ob(sc, name, n=0):
    hits = sorted((o for o in sc.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    return hits[n]


def at(sc, frame):
    sc.frame_set(frame)
    update()


def expected_matrix(sc, frame) -> Matrix:
    """The vessel's motion at ``frame`` worked out from the maths: T(p + heave) R(pitch) R(roll) T(-p)."""
    m = VM.motion(sc)
    p = VM.pivot(sc)
    t = frame * sc.render.fps_base / sc.render.fps
    h, r, q = float(m.heave.value(t)), float(m.roll.value(t)), float(m.pitch.value(t))
    rot = Matrix.Rotation(q, 4, "Y") @ Matrix.Rotation(r, 4, "X")
    return Matrix.Translation(p + Vector((0, 0, h))) @ rot @ Matrix.Translation(-p)


def rest_worlds(sc, objs):
    with VM.at_rest(sc):
        return {o.name: o.matrix_world.copy() for o in objs}


def test_sea_waves_are_the_ones_the_maths_uses():
    for state in ("CALM", "ROUGH"):
        got = surroundings._waves(state)
        want = [w.as_tuple() for w in sea_waves(state)]
        assert np.allclose(np.array(got), np.array(want))


def test_rig_matches_the_maths_and_every_part_moves_with_its_root():
    sc = fresh()
    parts = list(build.iter_parts(sc))
    assert parts and VM.rig("vessel") is not None
    rest = rest_worlds(sc, parts)
    root = build.model_roots(sc)[0]
    assert root.constraints.get(VM.CON) is not None
    piv = VM.rig("pivot")
    for f in (1, 37, 160, 611, 1500, 2999):
        at(sc, f)
        want = expected_matrix(sc, f)
        got = piv.matrix_world
        for i in range(4):
            for j in range(4):
                assert abs(got[i][j] - want[i][j]) < 2e-5, (f, i, j, got[i][j], want[i][j])
        for p in parts[::3]:
            for corner in ((0, 0, 0), (1, 1, 1), (-1, 0.5, 2)):
                c = Vector(corner)
                d = (p.matrix_world @ c - got @ rest[p.name] @ c).length
                assert d < 1e-5, (f, p.name, d)          # < 0.01 mm


def test_measured_in_blender_over_two_minutes_matches_the_table():
    """Amplitudes and periods measured from the evaluated scene (the boom's tip and the rig) over 120 s at 25 fps,
    every 2nd frame: Calm, bow quarter, the test crane on the Vessel deck (a 64 m hull)."""
    sc = fresh()
    sc.render.fps, sc.render.fps_base = 25, 1.0
    piv = VM.rig("pivot")
    roll, pitch, heave = [], [], []
    p = VM.pivot(sc)
    for f in range(0, 3000, 2):
        at(sc, f)
        mw = piv.matrix_world
        e = (mw.to_3x3()).to_euler("XYZ")
        roll.append(e.x)
        pitch.append(e.y)
        heave.append((mw @ p).z - p.z)
    dt = 2 / 25
    r = {"roll": math.degrees(V.peak(roll)), "pitch": math.degrees(V.peak(pitch)), "heave": V.peak(heave),
         "roll_s": V.mean_period(roll, dt), "pitch_s": V.mean_period(pitch, dt), "heave_s": V.mean_period(heave, dt)}
    print("measured in Blender:", {k: round(v, 3) for k, v in r.items()})
    for k, (lo, hi) in V.TABLE["CALM"].items():
        assert lo <= r[k] <= hi, (k, r[k])


def test_sea_and_camera_stay():
    sc = fresh()
    assert bpy.ops.fresing.camera_add(view="ISOMETRIC") == {"FINISHED"}
    cam = sc.camera
    sea = next(o for o in bpy.data.objects if o.get(surroundings.TAG) == "sea")
    root = surroundings.root_object()
    still = [o for o in (cam, sea, root) if o is not None]
    first = {o.name: o.matrix_world.copy() for o in still}
    tip = ob(sc, "BOOM")
    moved = 0.0
    tip0 = tip.matrix_world.translation.copy()
    for f in (10, 55, 140, 400):
        at(sc, f)
        for o in still:
            assert o.matrix_world == first[o.name], o.name
        moved = max(moved, (tip.matrix_world.translation - tip0).length)
        assert not sea.constraints and not cam.constraints
    assert moved > 0.05                                   # the crane does move


def test_strength_zero_holds_it_still():
    sc = fresh()
    sc.fresing.vessel.strength = 0.0
    parts = list(build.iter_parts(sc))[:5]
    rest = rest_worlds(sc, parts)
    for f in (20, 90, 333):
        at(sc, f)
        for p in parts:
            assert (p.matrix_world.translation - rest[p.name].translation).length < 1e-7
    assert VM.header(sc) == "Calm · still"


def _sea_state(sc):
    sea = next(o for o in bpy.data.objects if o.get(surroundings.TAG) == "sea")
    dg = bpy.context.evaluated_depsgraph_get()
    me = sea.evaluated_get(dg).to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    sea.evaluated_get(dg).to_mesh_clear()
    return co, sea.active_material.name, [m.node_group.name for m in sea.modifiers]


def test_off_and_old_projects_are_exactly_as_before():
    """A project that never had vessel motion, and one where it was switched on and off again: the same sea mesh
    and material, no rig, no constraints, nothing in the deck."""
    sc = fresh(on=False)
    at(sc, 47)
    before = _sea_state(sc)
    assert VM.rig("vessel") is None and not list(VM._constraints(sc))
    sc.fresing.vessel.enabled = True
    at(sc, 47)
    on = _sea_state(sc)
    assert not np.allclose(on[0], before[0])               # the swell is in the sea
    sc.fresing.vessel.enabled = False
    at(sc, 47)
    after = _sea_state(sc)
    assert np.array_equal(after[0], before[0]) and after[1:] == before[1:]
    assert VM.rig("vessel") is None and not list(VM._constraints(sc))
    assert bpy.data.collections.get(VM.COLLECTION) is None


def test_other_surroundings_and_switching():
    sc = fresh()
    s = sc.fresing
    assert VM.effective(sc)
    s.background = "FACTORY"
    update()
    assert not VM.effective(sc) and VM.rig("vessel") is None and not list(VM._constraints(sc))
    s.background = "SEA"
    update()
    assert VM.rig("vessel") is not None
    names = {o.name for o, _c in VM._constraints(sc)}
    foam = {o.name for o in bpy.data.objects if o.get(surroundings.TAG) == "hull_foam"}
    assert foam                                              # task 0109: the foam where the hull meets the water
    assert names == {build.model_roots(sc)[0].name} | foam   # the open sea: only the model (and its hull foam) moves
    assert VM.header(sc).startswith("Calm · roll ±")


def test_save_reopen_and_saved_scenes(tmp_path):
    from fresing_render.blender import states
    sc = fresh()
    states.save_shot(sc, "Deck")
    tip = ob(sc, "BOOM")
    at(sc, 123)
    want = tip.matrix_world.copy()
    path = str(tmp_path / "vessel.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    at(sc, 1)
    at(sc, 123)
    assert (ob(sc, "BOOM").matrix_world.translation - want.translation).length < 1e-6
    assert states.apply_shot(sc, "Deck") is not None          # rebuilds the surroundings: still moving
    at(sc, 123)
    assert (ob(sc, "BOOM").matrix_world.translation - want.translation).length < 1e-6
    deck = [o for o in sc.objects if o.get(surroundings.TAG) == "floor"]
    assert deck and all(o.constraints.get(VM.CON) is not None for o in deck)


def test_props_move_with_the_deck():
    sc = fresh()
    prop = surroundings.add_prop(sc, "PERSON")
    VM.sync(sc)
    assert prop.constraints.get(VM.CON) is not None


def test_still_and_level_parts():
    """'Still' keeps the trolley where it is in the world while the rest moves; 'Level' takes out roll and pitch,
    keeps heave. The boom's joint still turns the boom on a still vessel."""
    from fresing_render.blender import joints
    sc = fresh(heading="BEAM")
    trolley = ob(sc, "TROLLEY.ASM")
    assert VM.add_marks(sc, [trolley], "STILL") == 1
    parts = [p for p in build.iter_parts(sc)]
    t_parts = [p for p in parts if build.model_root_of(p) is not None and _under(p, trolley)]
    others = [p for p in parts if p not in t_parts]
    assert t_parts and others
    rest = rest_worlds(sc, parts)
    for f in (30, 140, 251):
        at(sc, f)
        for p in t_parts:
            assert (p.matrix_world.translation - rest[p.name].translation).length < 1e-5, p.name
        assert max((p.matrix_world.translation - rest[p.name].translation).length for p in others) > 1e-3
    # level: no turn, the vessel's heave at the pivot
    sc.fresing.vessel.still[0].mode = "LEVEL"
    piv = VM.pivot(sc)
    for f in (30, 140):
        at(sc, f)
        h = (VM.rig("pivot").matrix_world @ piv).z - piv.z
        for p in t_parts[:3]:
            d = p.matrix_world.translation - rest[p.name].translation
            assert abs(d.x) < 1e-5 and abs(d.y) < 1e-5 and abs(d.z - h) < 1e-5
            q = p.matrix_world.to_quaternion().rotation_difference(rest[p.name].to_quaternion())
            assert q.angle < 1e-5
    # a joint on a still part still moves it: the boom (with the trolley on it) turns while the vessel moves
    sc.fresing.vessel.still[0].mode = "STILL"
    boom = ob(sc, "BOOM.ASM")
    VM.add_marks(sc, [boom], "STILL")
    pin = ob(sc, "BOOM.PIN")
    j = joints.create(sc, "ROTATE", [boom], pin.matrix_world.translation, Vector((0, 1, 0)), name="Boom")
    VM.sync(sc)
    tip = ob(sc, "BOOM")
    at(sc, 80)
    a = tip.matrix_world @ Vector((1.5, 0, 0))
    joints.set_value(j, math.radians(20), use_limits=False)
    update()
    b = tip.matrix_world @ Vector((1.5, 0, 0))
    joints.set_value(j, 0.0, use_limits=False)
    update()
    c = tip.matrix_world @ Vector((1.5, 0, 0))
    assert (a - b).length > 0.05 and (a - c).length < 1e-5
    with VM.at_rest(sc):
        r = tip.matrix_world @ Vector((1.5, 0, 0))
    assert (r - c).length < 1e-5                       # on a still vessel: where it would be
    # removing the marks: it moves with the vessel again
    v = sc.fresing.vessel
    while len(v.still):
        v.still_index = 0
        assert bpy.ops.fresing.vessel_still_remove() == {"FINISHED"}
    assert not [c for _o, c in VM._constraints(sc) if c.name != VM.CON]
    assert VM.rig("still") is None and VM.rig("level") is None


def _under(ob_, top):
    p = ob_
    while p is not None:
        if p == top:
            return True
        p = build.logical_parent(p)
    return False


def test_model_update_keeps_it():
    sc = fresh(heading="BEAM")
    root = build.model_roots(sc)[0]
    VM.add_marks(sc, [ob(sc, "TROLLEY.ASM")], "LEVEL")
    at(sc, 77)                     # mid-motion: the update must not take the motion into the model
    res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name)
    assert res == {"FINISHED"}
    update()
    new_root = build.model_roots(sc)[0]
    assert new_root.constraints.get(VM.CON) is not None
    assert len(sc.fresing.vessel.still) == 1 and sc.fresing.vessel.still[0].mode == "LEVEL"
    assert any(c.name == VM.CON_LEVEL for _o, c in VM._constraints(sc))
    with VM.at_rest(sc):
        assert abs(new_root.matrix_world.translation.z - root_rest_z(sc)) < 1e-6


def root_rest_z(sc):
    return build.model_roots(sc)[0].matrix_basis.translation.z


def test_pivot_pick_and_auto():
    sc = fresh()
    v = sc.fresing.vessel
    auto = VM.pivot(sc)
    h = VM.hull(sc)
    assert abs(auto.z - h["water"]) < 1e-6 and abs(auto.x - h["middle"][0]) < 1e-6
    assert bpy.ops.fresing.vessel_pivot_pick() == {"FINISHED"}         # scripts: the automatic point, as picked
    assert v.pivot_mode == "PICK" and (Vector(v.pivot) - auto).length < 1e-6
    v.pivot = (auto.x + 10.0, auto.y, auto.z)
    assert abs(VM.rig("vessel").location.x - (auto.x + 10.0)) < 1e-6
    # a point clicked on the moving deck is taken back to where it is on a still sea
    at(sc, 90)
    p_world = VM.rig("pivot").matrix_world @ Vector((1.0, 2.0, 3.0))
    assert (VM.to_rest(sc, p_world) - Vector((1.0, 2.0, 3.0))).length < 1e-5


def test_frame_rate_changes_keep_the_vessel_on_the_waves():
    """The drivers read the time in seconds: at 50 fps frame 200 is the same moment as frame 100 at 25 fps."""
    sc = fresh()
    sc.render.fps = 25
    at(sc, 100)
    a = VM.rig("pivot").matrix_world.copy()
    sc.render.fps = 50
    at(sc, 200)
    b = VM.rig("pivot").matrix_world.copy()
    assert all(abs(a[i][j] - b[i][j]) < 1e-6 for i in range(4) for j in range(4))


QUEUE_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[-3])
import bpy, addon_utils
bpy.ops.wm.open_mainfile(filepath=sys.argv[-2])
addon_utils.enable("cycles", default_set=True)
import fresing_render
fresing_render.register()
from fresing_render.blender import animation
sc = bpy.context.scene
a = sc.fresing.animations[0]
animation.bake(sc, a)                       # the queue builds the animation again before it renders
out = {}
for f in json.loads(sys.argv[-1]):
    sc.frame_set(f)
    bpy.context.view_layer.update()
    out[str(f)] = [list(r) for r in bpy.data.objects["TIP"].matrix_world]
print("QUEUE", json.dumps(out))
"""


def test_queue_copy_shows_the_same_frames(tmp_path):
    """The render queue's background copy opens the saved project and builds the animation again: every frame
    shows the vessel where the view shows it."""
    from fresing_render.blender import animation, joints
    sc = fresh()
    pin = ob(sc, "BOOM.PIN")
    joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], pin.matrix_world.translation, Vector((0, -1, 0)), name="Boom")
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "Roll", "25", 0.0
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.to_angle = "JOINT", "Boom", 0.0, 6.0, math.radians(10)
    animation.bake(sc, a)
    tip = ob(sc, "BOOM")
    tip.name = "TIP"
    frames = [3, 61, 140]
    view = {}
    for f in frames:
        at(sc, f)
        view[str(f)] = [list(r) for r in tip.matrix_world]
    path = str(tmp_path / "queue.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    script = str(tmp_path / "q.py")
    with open(script, "w") as fh:
        fh.write(QUEUE_SCRIPT)
    root = os.path.dirname(HERE)
    res = subprocess.run([sys.executable, script, root, path, json.dumps(frames)], capture_output=True, text=True,
                         timeout=300)
    line = next((ln for ln in res.stdout.splitlines() if ln.startswith("QUEUE ")), None)
    assert line, res.stdout[-2000:] + res.stderr[-2000:]
    got = json.loads(line[6:])
    for f in frames:
        assert np.allclose(np.array(got[str(f)]), np.array(view[str(f)]), atol=1e-6), f


def test_camera_rides_on_the_vessel():
    """Camera on board (with task 0087's Ride along): a Ride along step on the model's root rides the vessel – the
    camera keeps its place and view on the deck while the vessel rolls; with Keep level it stays upright."""
    from fresing_render.blender import animation, cameras, camera_path
    sc = fresh(heading="BEAM")
    cam = cameras.add_camera(sc, "ISO", name="On board")
    sc.camera = cam
    update()
    root = build.model_roots(sc)[0]
    a = sc.fresing.animations.add()
    a.name, a.fps, a.tail = "On board", "25", 0.0
    b = a.blocks.add()
    b.kind, b.camera_mode, b.start, b.duration, b.cam_blend = "CAMERA", "RIDE", 0.0, 8.0, 0.0
    b.target_uid, b.target_name = root.get(build.PROP_UID), root.get(build.PROP_NAME)
    info = animation.bake(sc, a)                         # (sets the animation's 25 fps: the seat is read after it)
    assert not info["warnings"], info
    at(sc, 1)
    c0 = sc.camera.matrix_world.copy()
    offset = root.matrix_world.inverted() @ c0
    worst_mm = worst_deg = tilt = 0.0
    for f in range(1, info["frames"] + 1, 7):
        at(sc, f)
        want = root.matrix_world @ offset
        worst_mm = max(worst_mm, (sc.camera.matrix_world.translation - want.translation).length * 1000)
        worst_deg = max(worst_deg, camera_path.angle_between(sc.camera.matrix_world, want))
        tilt = max(tilt, camera_path.angle_between(sc.camera.matrix_world, c0))
    assert worst_mm < 0.01 and worst_deg < 0.01, (worst_mm, worst_deg)
    assert tilt > 0.3                                    # it rolls with the vessel (calm beam sea: about 1.5°)
    # Keep level: the horizon stays put (no roll or pitch), the camera still rides along
    b.ride_level = True
    animation.bake(sc, a)
    up0 = c0.to_3x3() @ Vector((0, 1, 0))
    for f in range(1, info["frames"] + 1, 7):
        at(sc, f)
        up = sc.camera.matrix_world.to_3x3() @ Vector((0, 1, 0))
        assert abs(math.degrees(up.angle(Vector((0, 0, 1)))) - math.degrees(up0.angle(Vector((0, 0, 1))))) < 0.01
        want = (root.matrix_world @ offset).translation
        assert (sc.camera.matrix_world.translation - want).length < 1e-5
