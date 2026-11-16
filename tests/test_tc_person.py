"""Task 0156: the operator who changes the tool (core/tc_person.py, core/toolchange.py's person moves) and the gloved
hand (core/glove.py) – without Blender."""

import math

import numpy as np
import pytest

from fresing_render.core import glove
from fresing_render.core import people as PL
from fresing_render.core import person_rig as R
from fresing_render.core import tc_person as T
from fresing_render.core import toolchange as TC

FPS = 25


# ---------------------------------------------------------------------------
# timing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("door", [0.0, 0.8])
def test_person_moves_in_order_without_gaps(door):
    need = TC.person_min(door)
    for length in (need, need + 2.5, need * 0.6):
        keys = TC.person_keys(10.0, length, door)
        assert keys[0][0] == pytest.approx(10.0)
        assert keys[-1][1] == pytest.approx(10.0 + length)
        for (a0, b0, _n0), (a1, _b1, _n1) in zip(keys, keys[1:]):
            assert b0 == pytest.approx(a1)
        names = [n for _a, _b, n in keys if n != "wait"]
        assert names == [n for n, _d in TC.person_moves(door)]
        out_t, in_t = TC.person_events(10.0, length, door)
        assert 10.0 < out_t < in_t <= 10.0 + length
        waits = [b - a for a, b, n in keys if n == "wait"]
        if length > need:
            assert waits == [pytest.approx(length - need)]
            assert [n for _a, _b, n in keys].index("wait") == [n for _a, _b, n in keys].index("take") - 1
        else:
            assert not waits
    assert TC.person_min(door) > TC.HAND_MIN
    if door:
        assert TC.person_min(door) > TC.person_min(0.0) + 2 * door


def test_the_pause_grows_to_what_the_person_needs():
    ch = TC.Changer(pause=1.0, person=True, door=0.7)
    assert ch.pause_length() == pytest.approx(TC.person_min(0.7))
    assert TC.Changer(pause=1.0, hand=True).pause_length() == pytest.approx(TC.HAND_MIN)
    assert TC.Changer(pause=1.0).pause_length() == pytest.approx(1.0)
    c = TC.plan(1, 2, (0.0, 0.0, 50.0), ch, 0.0)
    TC.place(c, 3.0)
    assert c.person and c.door == pytest.approx(0.7)
    assert c.hand[1] == pytest.approx(TC.person_min(0.7))
    out_t, in_t = TC.person_events(*c.hand, c.door)
    assert (c.drop, c.swap) == (pytest.approx(out_t), pytest.approx(in_t))
    # "Fit into" never squeezes the person's pause below what it needs
    assert TC.place(TC.plan(1, 2, (0.0, 0.0, 50.0), ch, 0.0), 0.0, scale=0.1).hand[1] == \
        pytest.approx(TC.person_min(0.7))


# ---------------------------------------------------------------------------
# the floor
# ---------------------------------------------------------------------------

def machine_floor():
    fl = T.Floor((-3.0, -4.0), (3.0, 2.0), z=0.0)
    fl.add_box((-0.45, -0.28, 0.0), (0.45, 0.5, 1.45))        # cabinet and enclosure
    fl.add_box((-1.6, -1.6, 0.0), (-1.2, -0.9, 1.0))          # a table to walk round
    return fl


def test_a_clear_way_round_things():
    fl = machine_floor()
    spot = T.stand_spot(fl, (0.0, 0.0), (0.0, -1.0))
    assert spot is not None and spot[1] < -0.28 - T.WORK_ROOM + 0.03
    assert fl.is_free(spot, T.WORK_ROOM)
    way = T.way_to(fl, (-2.2, -1.2), spot)
    assert way is not None and np.allclose(way[-1], spot)
    path = PL.Path(T.walkable(way))
    for s in np.linspace(0.0, path.length, 200):
        p = path.at(s)
        if np.linalg.norm(p - spot) > 0.1:
            assert fl.is_free(p, T.BODY - 0.02), p
    walled = T.Floor((-1.0, -1.0), (1.0, 1.0))
    walled.add_box((-0.8, -0.8, 0.0), (0.8, -0.7, 2.0))
    walled.add_box((-0.8, 0.7, 0.0), (0.8, 0.8, 2.0))
    walled.add_box((-0.8, -0.8, 0.0), (-0.7, 0.8, 2.0))
    walled.add_box((0.7, -0.8, 0.0), (0.8, 0.8, 2.0))
    assert walled.way((0.0, 0.0), (0.95, 0.95), 0.2) is None


def test_heights_are_kept_apart():
    fl = T.Floor((-1.0, -1.0), (1.0, 1.0), z=0.0)
    fl.add_box((-0.2, -0.2, 0.0), (0.2, 0.2, 0.9))             # a low table
    assert not fl.clear_at(np.array((0.0, -0.25, 0.85)), 0.1, 0.05)
    assert fl.clear_at(np.array((0.0, -0.25, 1.5)), 0.1, 0.1)   # a head above it
    big = T.Floor((-200.0, -200.0), (200.0, 200.0))
    assert max(big.shape) <= 325                               # the grid stays small on a huge area


def test_tools_lie_on_the_trolley_without_touching():
    tr = T.Trolley(np.array((0.6, -0.8)), math.pi, 0.96)
    L = np.eye(4)
    L[2, 3] = 0.04
    grips = {n: (L, 0.032) for n in (1, 2, 3, 4)}
    T.place_tools(tr, [1, 2, 3, 4], grips, math.pi)
    pts = np.array([tr.slots[n] @ L for n in (1, 2, 3, 4)])
    assert np.allclose(pts[:, 2, 3], 0.96 + 0.032 + 0.002)                  # the axis a radius above the top
    assert np.allclose(np.abs(pts[:, :3, 2] @ np.array((1.0, 0.0, 0.0))), 1.0, atol=1e-6)   # lying across
    d = np.linalg.norm(np.diff(pts[:, :2, 3], axis=0), axis=1)
    assert d.min() >= 2 * 0.032 + 0.02
    assert np.all(np.abs(pts[:, 1, 3] - (-0.8)) < 0.68 / 2)


def test_doors():
    d = T.Door("SLIDE", np.zeros(3), np.array((1.0, 0.0, 0.0)), 0.0, 0.5, np.array((-0.2, -0.3, 1.1)),
               np.array((0.0, -1.0, 0.0)))
    assert np.allclose(d.at(0.5, d.handle), (0.3, -0.3, 1.1))
    r = T.Door("ROTATE", np.array((0.3, -0.3, 0.0)), np.array((0.0, 0.0, 1.0)), 0.0, math.pi / 2,
               np.array((-0.2, -0.3, 1.1)), np.array((0.0, -1.0, 0.0)))
    assert np.allclose(r.at(math.pi / 2, r.handle), (0.3, -0.8, 1.1), atol=1e-9)
    assert r.travel_time() >= TC.DOOR_MIN


# ---------------------------------------------------------------------------
# hands
# ---------------------------------------------------------------------------

def test_the_fist_is_round_the_holder():
    k = R.Figure(1.75).k
    H = T.m4(T.frame_of((0.0, 0.0, 1.0), (1.0, -0.3, 0.0)), (0.1, 0.2, 1.1))
    for r in (0.016, 0.025, 0.035):
        M = T.grip_hand(H, k, r, np.array((1.0, -0.35, 0.0)))
        centre = M[:3, :3] @ PL._grip_local("r", k) + M[:3, 3]
        off = centre - H[:3, 3]
        axial = float(np.dot(off, H[:3, 2]))
        radial = np.linalg.norm(off - H[:3, 2] * axial)
        assert abs(axial) < 1e-9
        assert radial == pytest.approx(r + T.GRIP_GAP - 0.016, abs=1e-6)       # the fist wraps the holder
        thumb = -M[:3, 1]
        assert float(np.dot(thumb, H[:3, 2])) == pytest.approx(math.cos(math.radians(T.THUMB_TILT)), abs=1e-6)


def test_the_index_finger_presses_the_button():
    k = R.Figure(1.65).k
    face = np.array((0.0, -1.0, 0.0))
    M = T.press_hand(np.array((0.0, 0.0, 1.3)), face, k, press=0.003)
    tip = M[:3, :3] @ (np.asarray(T.INDEX_TIP) * k) + M[:3, 3]
    assert np.allclose(tip, (0.0, -0.001, 1.3), atol=1e-9)
    assert float(np.dot(-M[:3, 2], -face)) == pytest.approx(1.0)               # the finger points into the face


# ---------------------------------------------------------------------------
# the operator on a made-up machine
# ---------------------------------------------------------------------------

def made_up(height=1.75, t0=12.0, extra=1.0, changes=1, door=None):
    fl = T.Floor((-3.0, -4.0), (3.0, 2.0), z=0.0)
    fl.add_box((-0.45, -0.28, 0.0), (0.45, 0.5, 0.95))            # cabinet: the person reaches over it
    fl.add_box((-0.45, 0.25, 0.95), (0.45, 0.5, 1.5))             # the column behind the spindle
    heading = math.pi
    spot = T.stand_spot(fl, (0.0, 0.0), (0.0, -1.0))
    tr_c, tr_h = T.trolley_spot(fl, spot, heading)
    fl.add_box((tr_c[0] - 0.23, tr_c[1] - 0.34, 0.0), (tr_c[0] + 0.23, tr_c[1] + 0.34, 0.96))
    start = fl.nearest_free(spot + np.array((-1.5, -2.5)), T.BODY + T.WALK_MARGIN)
    way = T.way_to(fl, start, spot)
    rw = -np.array((*PL.left_of(heading), 0.0)) - np.array((*PL.facing(heading), 0.0)) * 0.35
    H = T.m4(T.frame_of((0.0, 0.0, 1.0), rw), (0.0, 0.0, 1.12))
    tool = H @ T.m4(np.eye(3), (0.0, 0.0, -0.05))
    grips = {n: (np.linalg.inv(tool) @ H, 0.03) for n in range(1, changes + 2)}
    trol = T.Trolley(tr_c, tr_h, 0.96)
    T.place_tools(trol, list(range(1, changes + 2)), grips, heading)
    need = TC.person_min(door.travel_time() if door else 0.0)
    stations = []
    for i in range(changes):
        stations.append(T.Station(i + 1, i + 2, t0 + i * (need + extra + 4.0), need + extra, H,
                                  {n: tool for n in range(1, changes + 2)}, grips,
                                  button=(np.array((-0.11, -0.04, 1.3)), np.array((0.0, -1.0, 0.0))),
                                  door=door.travel_time() if door else 0.0))
    op = T.Operator(height, start, spot, way, stations, trol, 0.0, door=door, floor=fl)
    op.plan()
    return op, fl, H, tool, trol


def sample(op, t_end):
    times = [i / FPS for i in range(int(t_end * FPS) + 1)]
    return times, op.sample(times)


def world_of(root, fk, bone):
    return T.to_world(root, T.m4(np.eye(3), fk[bone][2]))[:3, 3]


@pytest.mark.parametrize("height", [1.65, 1.85])
def test_the_operator_swaps_the_tool(height):
    op, fl, H, tool, trol = made_up(height)
    s = op.stations[0]
    times, rows = sample(op, s.t0 + s.length + 4.0)
    fig = op.fig
    # the hand reaches every aim; on the way between (through the machine's opening) it may stay a little short
    assert not [m for m in op.misses if m[2] > 0.015], op.misses[:3]
    ends = {round(b, 2) for a, b, n in TC.person_keys(s.t0, s.length, s.door)
            if n in ("grip", "release", "set", "take", "insert", "clamp")}
    assert not [m for m in op.misses if round(m[0], 2) in ends and m[2] > 0.004]
    keys = TC.person_keys(s.t0, s.length, s.door)
    span = {n: (a, b) for a, b, n in keys}
    out_t, in_t = TC.person_events(s.t0, s.length, s.door)
    # the hand round the holder at the grip, the tool out of the spindle into the hand, onto the trolley, back
    i_grip = int(round(span["grip"][1] * FPS))
    root, pose, tools, _dv = rows[i_grip]
    fk = fig.fk(pose)
    hand = T.to_world(root, T.m4(fk["r_hand"][1], fk["r_hand"][0]))
    centre = hand[:3, :3] @ PL._grip_local("r", fig.k) + hand[:3, 3]
    off = centre - H[:3, 3]
    assert np.linalg.norm(off - H[:3, 2] * np.dot(off, H[:3, 2])) < 0.03 and abs(np.dot(off, H[:3, 2])) < 0.004
    for t, want in ((out_t, tool), (span["set"][1], trol.slots[1])):
        _r, _p, tools, _d = op.sample([t])[0]
        assert np.allclose(tools[1], want, atol=2e-3), t
    _r, _p, tools, _d = op.sample([in_t])[0]
    assert np.allclose(tools[2], tool, atol=2e-3)
    # never walks or stands in the machine; turns to face it
    for t, (root, _p, _t, _d) in zip(times, rows):
        assert fl.is_free(root[:2], T.WORK_ROOM - 0.02), (t, root)
    assert op.person.root(s.t0)[3] == pytest.approx(math.pi, abs=0.05)
    # the person walks in before the pause and stands still during it
    r0, r1 = op.person.root(s.t0 - T.ARRIVE + 0.01), op.person.root(s.t0 + s.length)
    assert np.allclose(r0[:2], r1[:2], atol=1e-6)
    assert np.linalg.norm(np.array(op.person.root(0.0)[:2]) - op.stand) > 1.5


def test_no_jumps_at_the_machine():
    op, *_ = made_up()
    s = op.stations[0]
    times, rows = sample(op, s.t0 + s.length + 0.5)
    fig = op.fig
    prev = None
    for t, (root, pose, _tools, _d) in zip(times, rows):
        if t < s.t0 - 0.2:
            continue
        fk = fig.fk(pose)
        cur = {b: world_of(root, fk, b) for b in ("r_hand", "l_hand", "head")}
        if prev is not None:
            for b in cur:
                assert np.linalg.norm(cur[b] - prev[b]) < 0.1, (t, b)       # under 2.5 m/s
        prev = cur


def test_the_head_stays_out_of_things_when_leaning():
    op, fl, *_ = made_up()
    s = op.stations[0]
    times, rows = sample(op, s.t0 + s.length)
    fig = op.fig
    for t, (root, pose, _tools, _d) in zip(times, rows):
        if t < s.t0:
            continue
        fk = fig.fk(pose)
        hh, _R, ht = fk["head"]
        head = T.to_world(root, T.m4(np.eye(3), hh + (ht - hh) * 0.45))[:3, 3]
        assert fl.clear_at(head, T.HEAD_R * fig.k * 0.9, 0.1 * fig.k), t


def test_several_changes_and_a_door():
    door = T.Door("SLIDE", np.zeros(3), np.array((1.0, 0.0, 0.0)), 0.0, 0.5, np.array((-0.2, -0.33, 1.1)),
                  np.array((0.0, -1.0, 0.0)))
    op, *_ = made_up(changes=3, door=door)
    assert len(op.change_times()) == 3
    last = op.stations[-1]
    times, rows = sample(op, last.t0 + last.length + 3.0)
    vals = [d for _r, _p, _t, d in rows]
    assert max(vals) == pytest.approx(0.5) and vals[0] == pytest.approx(0.0) and vals[-1] == pytest.approx(0.0)
    for s in op.stations:                                  # the door is open for the whole change of the tool
        keys = TC.person_keys(s.t0, s.length, s.door)
        a = next(x for x in keys if x[2] == "reach")[0]
        b = next(x for x in keys if x[2] == "leave")[1]
        assert op.door_value(a) == pytest.approx(0.5) and op.door_value(b) == pytest.approx(0.5)
    big = [m for m in op.misses if m[2] > 0.02]
    assert not big, big[:3]


def test_too_early_a_change_stands_at_the_machine_from_the_start():
    op, *_ = made_up(t0=0.5)
    assert op.at_start
    assert np.allclose(op.person.root(0.0)[:2], op.stand, atol=1e-6)
    assert op.notes


# ---------------------------------------------------------------------------
# the glove
# ---------------------------------------------------------------------------

def test_the_glove_closes_round_the_holder():
    for r in (0.018, 0.025, 0.032):
        v1, f1 = glove.glove(r, 1.0)
        v0, f0 = glove.glove(r, 0.0)
        assert v1.shape == v0.shape and f1 == f0                    # the open hand is a shape key of the closed one
        assert sum(len(f) - 2 for f in f1) < 4000                   # light
        tips = glove.fingertips(r)
        rad = np.hypot(tips[:, 0], tips[:, 1])
        assert np.all(rad > r) and np.all(rad < r + 0.015)          # round the holder, not in it
        ang = np.degrees(np.arctan2(tips[:, 1], tips[:, 0]))
        assert np.all(ang > 25) and ang.mean() > 45                 # wrapped round to the holder's back
        near = v1[np.abs(v1[:, 2]) < 0.035]                         # the fingers' height
        assert np.hypot(near[:, 0], near[:, 1]).min() > r - 0.003   # nothing deep in the holder
    _v, f = glove.tube([(0, 0, 0), (0, 0, 0.05), (0, 0, 0.1)], [0.01, 0.01, 0.01])
    v = _v
    for face in f:                                                  # faces look out (smooth shading stays clean)
        p = v[list(face)]
        assert np.dot(np.cross(p[1] - p[0], p[2] - p[0]), p.mean(axis=0) - (0, 0, 0.05)) >= 0
