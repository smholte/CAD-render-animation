"""Task 0082: a cable on a moving part, in Blender (as a Python module). Model: tests/data/test_moving.step
(tools/make_test_moving.py), set up by ``paths.set_up_moving_model``: a trolley travels aft along a gantry, its
hanger tilts, the block under it lowers; the cable "Cable end" is clamped on the block, goes round its sheave and
over the stern horn into the sea (the vessel sails at 3 kn) and is let go at 9.2 s; the lift wire runs from a
fairlead over the trolley's head sheave down to the block, its winch keeping it tight. And the spooling model
(test_spool.step): a winch drum turns with what keeping its wire tight pays out.

A1 the winch keeps it tight, A2 the hang-off moves to the last wheel the cable still bends round, A3 let go.
"""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
MODEL = os.path.join(HERE, "data", "test_moving.step")
SPOOL = os.path.join(HERE, "data", "test_spool.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, paths_sea, spool  # noqa: E402

MM = 0.001


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("moving"))


def load(folder, model=MODEL):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture()
def moving(folder):
    sc = load(folder)
    made = paths.set_up_moving_model(sc)
    assert made["cable"] == paths.MOVING_CABLE and made["wire"] == paths.MOVING_WIRE
    return sc


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def cable(sc):
    return paths.find(sc, paths.MOVING_CABLE)


def wire(sc):
    return paths.find(sc, paths.MOVING_WIRE)


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def build_it(sc):
    r = animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    return r["warnings"]


def bed_inv(sc):
    return np.linalg.inv(np.array(paths_sea.bed(sc).matrix_world))


def at(m, p):
    return m[:3, :3] @ np.asarray(p, dtype=float) + m[:3, 3]


def let_go_frame(sc):
    return int(round(paths.MOVING_LET_GO * 25)) + 1


# ---------------------------------------------------------------------------
# the set-up
# ---------------------------------------------------------------------------

def test_the_set_up_reads_both_ropes(moving):
    sc = moving
    it, w = cable(sc), wire(sc)
    assert [(c.name, c.kind) for c in it.contacts] == [("SHEAVE", "SHEAVE"), ("HORN", "CHUTE")]
    assert it.a_kind == "FIXED" and it.a_part.get(build.PROP_NAME) == "CLAMP" and it.b_kind == "SEA"
    assert [(c.name, c.kind) for c in w.contacts] == [("HEAD SHEAVE", "SHEAVE")]
    assert {w.a_part.get(build.PROP_NAME), w.b_part.get(build.PROP_NAME)} == {"BLOCK", "FAIRLEAD"}
    assert w.keep_tight and not it.keep_tight
    assert it.a_let_go_frame == let_go_frame(sc) and it.contacts[0].let_go_frame == let_go_frame(sc)
    assert it.contacts[1].let_go_frame == -1 and it.b_let_go_frame == -1
    assert paths._stored_let_go(it) == {}                   # (a frame not built yet: its place is read at Build)
    for x in (it, w):
        assert paths.status(sc, x)[1] == "OK", paths.status(sc, x)
    assert "winch pays out 0.00 m" in paths.status(sc, w)[0]
    assert paths_sea.numbers(sc, it)["hang_off"] == "HORN" and "left" not in paths_sea.numbers(sc, it)
    # the free length: the drawn path from its start to its end, or (into the sea) to where it arrives on the horn
    assert paths.free_length(sc, w) == pytest.approx(paths.free_length(sc, w, cad=True), abs=1e-5)
    assert paths.free_length(sc, it, cad=True) == pytest.approx(10.453, abs=0.01)


# ---------------------------------------------------------------------------
# A1: the winch keeps it tight
# ---------------------------------------------------------------------------

def test_keep_tight_live_pays_out_what_travel_and_lowering_need(moving):
    sc = moving
    w = wire(sc)
    j = joints.find(sc, w.joint)
    free0 = paths.free_length(sc, w, cad=True)
    for jname, value, want in (("Travel", 3.0, 3.0), ("Lower", 2.0, 5.0)):
        joints.set_value(joints.find(sc, jname), value)
        update()
        paths.refresh(sc)                                   # (what the handler does after the change)
        update()
        w = wire(sc)
        # the run fairlead -> head sheave grows by the travel, the run down to the block by the lowering
        assert joints.get_value(j) == pytest.approx(want, abs=paths.TIGHT_TOL), jname
        assert paths.tight_payout(sc, w) == pytest.approx(want, abs=paths.TIGHT_TOL)
        assert paths.free_length(sc, w) - paths.tight_payout(sc, w) == pytest.approx(free0, abs=paths.TIGHT_TOL)
    # the head sheave turns with it (it follows the wire's speed)
    c = w.contacts[0]
    sheave = joints.find(sc, c.joint)
    assert abs(joints.get_value(sheave)) == pytest.approx(5.0 / (paths.radius_of(w, c)), rel=1e-3)
    # a value set again for the same pose does not change it (no update loop): within the tolerance it stays
    before = joints.get_value(j)
    paths.refresh(sc)
    assert joints.get_value(j) == before
    # off: the speed goes back to 0 (nothing else moves it) and no longer follows
    paths.set_keep_tight(sc, wire(sc), False)
    joints.set_value(joints.find(sc, "Lower"), 4.0)
    update()
    paths.refresh(sc)
    assert joints.get_value(joints.find(sc, wire(sc).joint)) == 0.0 and before > 4.0
    assert "winch" not in paths.status(sc, wire(sc))[0]


def test_keep_tight_at_build_keys_every_frame(moving):
    sc = moving
    warnings = build_it(sc)
    assert not warnings, warnings
    w = wire(sc)
    j = joints.find(sc, w.joint)
    assert j.motion.get(paths.TIGHT) == w.name
    keys = paths._fcurves(j.motion)
    assert [f.data_path for f in keys] == [joints.COUPLING_PATH]
    assert len(keys[0].keyframe_points) == sc.frame_end - sc.frame_start + 1          # one key per frame
    free0 = paths.free_length(sc, w, cad=True)
    worst, pays = 0.0, []
    for f in range(sc.frame_start, sc.frame_end + 1, 3):
        sc.frame_set(f)
        w = wire(sc)
        pays.append(paths.tight_payout(sc, w))
        worst = max(worst, abs(paths.free_length(sc, w) - pays[-1] - free0))
    assert worst < paths.TIGHT_TOL, worst                                             # 0.5 mm
    assert max(pays) > 18.0 and pays[0] == pytest.approx(0.0, abs=1e-5)               # 10.5 m travel + 9 m lowered
    assert "winch pays out" in paths.status(sc, w)[0]
    # what Build drew is what was solved for those places: the drawn line's length is the free length
    sc.frame_set(200)
    line = paths.shape_now(sc, wire(sc))
    assert np.linalg.norm(np.diff(line, axis=0), axis=1).sum() == pytest.approx(paths.free_length(sc, wire(sc)),
                                                                              abs=2e-3)
    # Clear keys takes the winch's keys with the others, and the tag
    animation.clear_keys(sc)
    j = joints.find(sc, wire(sc).joint)
    assert paths.TIGHT not in j.motion and not paths._fcurves(j.motion)


def test_keep_tight_is_skipped_when_a_step_moves_the_speed(moving):
    sc = moving
    w = wire(sc)
    a = sc.fresing.animations[paths.MOVING_ANIMATION]
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", w.joint, 0.0, 2.0, "LINEAR"
    b.speed_mmin = 6.0
    warnings = build_it(sc)
    assert any("does not keep it tight" in t for t in warnings), warnings
    j = joints.find(sc, wire(sc).joint)
    assert paths.TIGHT not in j.motion
    assert paths.status(sc, wire(sc))[1] == "WARN" and "not kept tight" in paths.status(sc, wire(sc))[0]


def test_keep_tight_skipped_is_said_in_the_panel_and_off_puts_the_speed_back(moving):
    from test_paths_panel import draw_panel
    sc = moving
    s = sc.fresing
    s.cables_index = paths.index_of(sc, wire(sc))
    joints.set_value(joints.find(sc, "Travel"), 3.0)
    update()
    paths.refresh(sc)
    assert paths.tight_payout(sc, wire(sc)) == pytest.approx(3.0, abs=paths.TIGHT_TOL)
    a = s.animations[paths.MOVING_ANIMATION]
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", wire(sc).joint, 0.0, 2.0, "LINEAR"
    b.speed_mmin = 6.0
    assert "a step in 6 Animation moves its speed" in paths.tight_skipped(sc, wire(sc))
    texts = " ".join(draw_panel()[0])
    assert "Not kept tight" in texts and "Add a Run motor step" in texts, texts
    a.blocks.remove(len(a.blocks) - 1)
    assert paths.tight_skipped(sc, wire(sc)) == ""
    texts = " ".join(draw_panel()[0])
    assert "Not kept tight" not in texts and "Add a Run motor step" not in texts
    # off: nothing else moves the speed, so it goes back to 0
    paths.set_keep_tight(sc, wire(sc), False)
    assert joints.get_value(joints.find(sc, wire(sc).joint)) == 0.0


def test_keep_tight_needs_a_joint_of_its_own(moving):
    sc = moving
    w = wire(sc)
    j = joints.find(sc, w.joint)
    j.follows = "Travel"                                    # (its speed follows another joint now)
    notes = paths.set_keep_tight(sc, wire(sc), True)
    assert notes and "cannot be kept tight" in notes[0] and "follows 'Travel'" in notes[0]
    assert paths.status(sc, wire(sc))[1] == "WARN"


def test_a_spool_drum_turns_with_the_keep_tight_payout(folder):
    sc = load(folder, SPOOL)
    spool.set_up_test_model(sc)
    sc.fresing.animations.remove(sc.fresing.animations.find(spool.TEST_ANIMATION))
    weight = named(sc, "WEIGHT")
    root = build.model_root_of(weight)
    m = root.matrix_world
    from mathutils import Vector
    joints.create(sc, "SLIDE", [weight], m @ Vector((0.9, 0.0, 0.2)), (m.to_3x3() @ Vector((0, 0, -1))).normalized(),
                  name="Weight down")
    update()
    w = paths.find(sc, "Wire")
    assert w.a_kind == "SPOOL"
    assert not paths.set_keep_tight(sc, w, True)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Lower the weight", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Weight down", 0.0, 2.0, "LINEAR"
    b.use_from = True
    b.to_dist = 0.3
    r = animation.bake(sc, a)
    assert not [t for t in r["warnings"] if "Wire" in t], r["warnings"]
    w = paths.find(sc, "Wire")
    sp = spool.of_cable(sc, w)
    drum = joints.find(sc, sp.joint)
    top, f_map = joints.chain_map(sc, drum)
    assert top.name == w.joint
    free0 = paths.free_length(sc, w, cad=True)
    for f in (sc.frame_start, 20, sc.frame_end):
        sc.frame_set(f)
        update()
        w = paths.find(sc, "Wire")
        pay = paths.tight_payout(sc, w)
        assert paths.free_length(sc, w) - pay == pytest.approx(free0, abs=paths.TIGHT_TOL), f
        assert joints.get_value(drum) == pytest.approx(float(f_map(joints.get_value(joints.find(sc, w.joint)))),
                                                       abs=1e-5)
    assert pay == pytest.approx(0.3, abs=0.01)              # (the weight hangs straight under the fairlead sheave)
    assert abs(joints.get_value(drum)) > 0.2                 # 0.3 m off a drum of r ≈ 0.19 m: about a quarter turn


# ---------------------------------------------------------------------------
# A2: the hang-off moves to the last wheel the cable still bends round
# ---------------------------------------------------------------------------

def test_the_hang_off_moves_to_the_sheave_carried_past_the_horn(moving):
    sc = moving
    for c in (cable(sc),):                                  # (no let-go: only the hang-off is looked at here)
        paths.hold(sc, c, "a")
        paths.hold(sc, cable(sc), "0")
    warnings = build_it(sc)
    assert not [t for t in warnings if paths.MOVING_CABLE in t], warnings
    it = cable(sc)
    frames, per, first = paths._layout_of(it.shapes)
    assert frames == sc.frame_end - sc.frame_start + 1                                 # one point count …
    total, hangs = [], []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        it = cable(sc)
        s = paths.lengths_now(sc, it)
        assert len(s) == per                                                           # … for every frame
        total.append(float(s[-1]))
        hangs.append(paths_sea.numbers(sc, it)["hang_off"])
    assert max(total) - min(total) < 1e-3, (min(total), max(total))                   # start -> seabed end: kept
    k = hangs.index("SHEAVE")
    assert set(hangs[:k]) == {"HORN"} and set(hangs[k:]) == {"SHEAVE"}                # once left, the horn stays left
    sc.frame_set(sc.frame_end)
    n = paths_sea.numbers(sc, cable(sc))
    assert n["left"] == "HORN" and n["left_frame"] == sc.frame_start + k
    # it is information, not a problem: the cable's status stays OK
    assert cable(sc).problem == "" and paths.status(sc, cable(sc))[1] == "OK"
    # when it leaves the horn the sheave has gone past the horn's top (a sheave carried over the stern)
    sc.frame_set(sc.frame_start + k)
    sheave = np.array(named(sc, "SHEAVE").matrix_world)[:3, 3]
    horn_top = np.array(named(sc, "HORN").matrix_world) @ np.array([0.5, 0.0, 3.2, 1.0])
    assert sheave[0] < horn_top[0] - 1.0
    # the drawn line: the horn's points lie on the catenary now (closer than 2 m apart until the seabed, where
    # the cable lies straight), and its length is the length kept
    line = paths.shape_now(sc, cable(sc))
    seg = np.linalg.norm(np.diff(line, axis=0), axis=1)
    assert seg[:-paths_sea.N_LAID].max() < 2.0 and np.isfinite(line).all()
    assert seg.sum() == pytest.approx(total[k], abs=5e-3)


def test_one_moment_alone_hangs_from_where_the_moment_says(moving):
    """Live (a pose set by hand): the sheave past the horn and lowered – the cable hangs from the sheave."""
    sc = moving
    for jname, v in (("Travel", 10.5), ("Tilt", math.radians(30.0)), ("Lower", 5.0)):
        joints.set_value(joints.find(sc, jname), v)
    update()
    paths.refresh(sc)
    n = paths_sea.numbers(sc, cable(sc))
    assert n["hang_off"] == "SHEAVE" and n["left"] == "HORN" and n["left_frame"] is None
    text = paths.status(sc, cable(sc))[0]                   # (the vessel stands still: the cable piles up there)
    assert "HORN" not in text and "no longer touches" not in text, text
    for jname in ("Lower", "Tilt", "Travel"):
        joints.set_value(joints.find(sc, jname), 0.0)
    update()
    paths.refresh(sc)
    assert paths_sea.numbers(sc, cable(sc))["hang_off"] == "HORN"


# ---------------------------------------------------------------------------
# A3: let go
# ---------------------------------------------------------------------------

def test_let_go_stays_on_the_seabed_while_its_carrier_moves_away(moving):
    sc = moving
    warnings = build_it(sc)
    assert not [t for t in warnings if paths.MOVING_CABLE in t], warnings
    it = cable(sc)
    f0 = let_go_frame(sc)
    stored = paths._stored_places(sc, it, paths._inputs_of(it)[1])
    assert stored is not None
    rel, first = stored
    res = paths._solve_item(sc, it, rel, first=first)                                  # (what Build drew)
    lo, n = int(res["first"][0]), int(res["counts"][0])                                # the sheave's arc
    starts, sheave, totals, carried = [], [], [], []
    for f in range(f0, sc.frame_end + 1, 4):
        sc.frame_set(f)
        it = cable(sc)
        inv = bed_inv(sc)
        line = paths.shape_now(sc, it)
        assert np.abs(paths._at(paths._world(it.part), res["points"][f - first]) - line).max() < 1e-3
        arc = line[lo:lo + n]
        starts.append(at(inv, line[0]))
        sheave.append(np.array([at(inv, p) for p in arc]))
        totals.append(float(paths.lengths_now(sc, it)[-1]))
        carried.append(at(inv, np.array(named(sc, "SHEAVE").matrix_world)[:3, 3]))
    drift = max(np.linalg.norm(p - starts[0]) for p in starts)
    arc_drift = max(np.abs(a - sheave[0]).max() for a in sheave)
    assert drift < 1e-3 and arc_drift < 1e-3, (drift, arc_drift)                       # still on the seabed …
    assert max(np.linalg.norm(c - carried[0]) for c in carried) > 4.0                 # … while the block went on
    assert max(totals) - min(totals) < 1e-3                                            # its length kept
    # the seabed itself moved aft meanwhile (the vessel sails on): in the world the let-go points moved with it
    sc.frame_set(f0)
    p0 = paths.shape_now(sc, cable(sc))[0]
    sc.frame_set(sc.frame_end)
    p1 = paths.shape_now(sc, cable(sc))[0]
    sailed = 3.0 * 0.514444 * (sc.frame_end - f0) / 25.0
    assert np.linalg.norm(p1 - p0) == pytest.approx(sailed, abs=0.01)
    # before the let-go frame the start went with the clamp
    sc.frame_set(f0 - 40)
    clamp = named(sc, "CLAMP")
    assert np.linalg.norm(paths.shape_now(sc, cable(sc))[0] - paths._at(paths._world(clamp),
                                                                       np.array(cable(sc).a_point))) < 1e-3


def test_let_go_and_hold_in_the_pose_shown(moving):
    sc = moving
    it = cable(sc)
    paths.hold(sc, it, "a")
    paths.hold(sc, cable(sc), "0")
    assert cable(sc).a_let_go_frame == -1 and cable(sc).contacts[0].let_go_frame == -1
    for jname, v in (("Travel", 10.5), ("Tilt", math.radians(30.0)), ("Lower", 5.0)):
        joints.set_value(joints.find(sc, jname), v)
    update()
    paths.refresh(sc)
    sc.frame_set(10)
    sc.fresing.cables_index = 0
    assert bpy.ops.fresing.cable_let_go(which="A") == {"FINISHED"}                   # (the chosen cable)
    it = cable(sc)
    assert it.a_let_go_frame == 10 and paths.LET_GO in it
    start = paths.shape_now(sc, it)[0].copy()
    joints.set_value(joints.find(sc, "Lower"), 8.0)                                    # the block goes on down
    update()
    paths.refresh(sc)
    assert np.linalg.norm(paths.shape_now(sc, cable(sc))[0] - start) < 1e-3           # the start stays
    sc.frame_set(5)                                                                    # before the let-go frame …
    paths.refresh(sc, force=True)
    assert np.linalg.norm(paths.shape_now(sc, cable(sc))[0] - start) > 1.0            # … it goes with the clamp
    sc.frame_set(10)
    paths.refresh(sc, force=True)
    assert bpy.ops.fresing.cable_let_go(which="A", hold=True) == {"FINISHED"}
    it = cable(sc)
    assert it.a_let_go_frame == -1
    clamp = named(sc, "CLAMP")
    assert np.linalg.norm(paths.shape_now(sc, it)[0] - paths._at(paths._world(clamp), np.array(it.a_point))) < 1e-3
    # a contact: the one chosen in the list
    it.contacts_index = 0
    assert bpy.ops.fresing.cable_let_go(which="") == {"FINISHED"}
    assert cable(sc).contacts[0].let_go_frame == 10


def test_let_go_refuses_what_cannot_go(moving, folder):
    sc = moving
    with pytest.raises(paths.PathError, match="seabed already"):
        paths.let_go(sc, cable(sc), "b")
    with pytest.raises(paths.PathError):
        paths.let_go(sc, cable(sc), "7")
    sc2 = load(folder, SPOOL)
    spool.set_up_test_model(sc2)
    w = paths.find(sc2, "Wire")
    with pytest.raises(paths.PathError, match="drum or carousel"):
        paths.let_go(sc2, w, "a")
    rollers = [i for i, c in enumerate(w.contacts) if c.kind == "ROLLER"]
    for i in rollers[:1]:
        with pytest.raises(paths.PathError, match="roller"):
            paths.let_go(sc2, w, str(i))


def test_let_go_survives_a_reopened_project(moving, tmp_path):
    sc = moving
    build_it(sc)
    path = str(tmp_path / "moving.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    sc.frame_set(sc.frame_end)
    want = paths.shape_now(sc, cable(sc))[0].copy()
    bpy.ops.wm.open_mainfile(filepath=path)
    paths.forget()
    sc = bpy.context.scene
    sc.frame_set(sc.frame_end)
    assert np.linalg.norm(paths.shape_now(sc, cable(sc))[0] - want) < 1e-3
    assert cable(sc).a_let_go_frame == let_go_frame(sc)
    assert paths.LET_GO in cable(sc)
