"""Task 0156, independent tests (written from the brief and the Design by an agent that did not write the code): the
operator who changes the tool, without Blender.

* timing: ``core/toolchange.person_keys`` / ``person_events`` / ``person_min`` and ``place()`` with a person;
* ``core/tc_person``: the floor map, the stand and trolley spots, the tools on the trolley, the door, the hands;
* ``Operator`` on a made-up machine (a table with a column and a head, the holder about 1.1 m up): where it walks,
  what its hands hold, the tools it carries, its feet, no jumps, heights, a door, several changes.

Tests marked ``xfail(strict=True)`` show a fault found in the code (their reason says what).
"""

import functools
import math

import numpy as np
import pytest

from fresing_render.core import people as PL
from fresing_render.core import person_rig as R
from fresing_render.core import tc_person as T
from fresing_render.core import toolchange as TC

FPS = 25.0
MM = 1e-3


# ---------------------------------------------------------------------------
# timing (core/toolchange.py)
# ---------------------------------------------------------------------------

def _names(door):
    return [n for n, _d in TC.person_moves(door)]


@pytest.mark.parametrize("door", [0.0, 1.2])
@pytest.mark.parametrize("extra", [0.0, 2.5, -0.5])
def test_moves_in_order_without_gaps(door, extra):
    need = TC.person_min(door)
    length = need * (1 + extra) if extra < 0 else need + extra
    t0 = 3.7
    keys = TC.person_keys(t0, length, door)
    names = [n for _a, _b, n in keys]
    want = _names(door)
    if extra > 0:
        want = want[:want.index("take")] + ["wait"] + want[want.index("take"):]
    assert names == want
    assert keys[0][0] == pytest.approx(t0)
    assert keys[-1][1] == pytest.approx(t0 + length)
    for (a0, b0, _n0), (a1, b1, _n1) in zip(keys, keys[1:]):
        assert a1 == pytest.approx(b0, abs=1e-9), "a gap or an overlap between two moves"
    assert all(b >= a for a, b, _n in keys)


def test_person_min_is_the_sum_of_the_moves():
    assert TC.person_min(0.0) == pytest.approx(sum(d for _n, d in TC.PERSON_MOVES))
    d = 1.3
    extra = 2 * (TC.DOOR_REACH + d + TC.DOOR_LET_GO)
    assert TC.person_min(d) == pytest.approx(TC.person_min(0.0) + extra)
    # a very quick door still takes DOOR_MIN each way
    assert TC.person_min(0.05) == pytest.approx(TC.person_min(0.0) + 2 * (TC.DOOR_REACH + TC.DOOR_MIN +
                                                                           TC.DOOR_LET_GO))


def test_the_pause_grows_to_what_the_person_needs():
    for door in (0.0, 1.0):
        ch = TC.Changer(pause=1.0, person=True, door=door)
        assert ch.pause_length() == pytest.approx(TC.person_min(door))
        assert ch.operator_min() == pytest.approx(TC.person_min(door))
        ch = TC.Changer(pause=TC.person_min(door) + 2.0, person=True, door=door)
        assert ch.pause_length() == pytest.approx(TC.person_min(door) + 2.0)
    assert TC.Changer(pause=1.0).pause_length() == pytest.approx(1.0)
    assert TC.Changer(pause=1.0, hand=True).pause_length() == pytest.approx(TC.HAND_MIN)


def test_a_longer_pause_is_a_wait_before_take():
    need = TC.person_min(0.0)
    keys = TC.person_keys(0.0, need + 3.0, 0.0)
    own = dict(TC.PERSON_MOVES)
    for a, b, n in keys:
        if n == "wait":
            assert b - a == pytest.approx(3.0)
        else:
            assert b - a == pytest.approx(own[n]), n
    names = [n for _a, _b, n in keys]
    assert names.index("wait") == names.index("take") - 1
    assert names.index("wait") > names.index("set")


def test_a_shorter_pause_plays_every_move_faster():
    need = TC.person_min(0.0)
    keys = TC.person_keys(10.0, need / 2, 0.0)
    own = dict(TC.PERSON_MOVES)
    assert "wait" not in [n for _a, _b, n in keys]
    for a, b, n in keys:
        assert b - a == pytest.approx(own[n] / 2)
    out_t, in_t = TC.person_events(10.0, need / 2, 0.0)
    assert 10.0 < out_t < in_t <= 10.0 + need / 2 + 1e-9


@pytest.mark.parametrize("door", [0.0, 0.9])
def test_events_are_the_ends_of_release_and_clamp(door):
    length = TC.person_min(door) + 1.0
    keys = TC.person_keys(2.0, length, door)
    end = {n: b for _a, b, n in keys}
    out_t, in_t = TC.person_events(2.0, length, door)
    assert out_t == pytest.approx(end["release"])
    assert in_t == pytest.approx(end["clamp"])
    assert out_t < end["set"] <= end["take"] < in_t


def test_door_moves_only_with_a_door():
    plain = _names(0.0)
    assert not set(plain) & {"open", "close", "to_door", "to_close", "let_go", "let_go2"}
    with_door = _names(1.0)
    assert with_door.index("open") < with_door.index("reach")
    assert with_door.index("close") > with_door.index("leave")
    assert [n for n in with_door if n in plain] == plain


def _manual(person=True, door=0.0, position=None, pause=1.0, hand=False):
    ch = TC.Changer(position=position, pause=pause, person=person, door=door, hand=hand)
    c = TC.plan(1, 2, (10.0, 20.0, 30.0), ch, 0.0)
    return ch, c


@pytest.mark.parametrize("door", [0.0, 1.1])
@pytest.mark.parametrize("position", [None, (0.0, 0.0, 300.0)])
def test_place_gives_the_person_and_its_moments(door, position):
    ch, c = _manual(door=door, position=position)
    TC.place(c, 5.0)
    assert c.person is True
    assert c.door == pytest.approx(door)
    assert c.hand is not None
    t, length = c.hand
    assert length == pytest.approx(TC.person_min(door))
    assert (c.drop, c.swap) == pytest.approx(TC.person_events(t, length, door))
    assert 5.0 <= t and t + length <= c.start + c.length + 1e-9


def test_place_squeezed_keeps_the_person_s_time():
    _ch, c = _manual(door=0.8, pause=4.0, position=(0.0, 0.0, 300.0))
    TC.place(c, 0.0, scale=0.2)
    assert c.hand[1] == pytest.approx(TC.person_min(0.8))


def test_a_hand_is_not_a_person():
    _ch, c = _manual(person=False, hand=True)
    TC.place(c, 0.0)
    assert not c.person
    assert c.hand[1] == pytest.approx(TC.HAND_MIN)
    _ch, c = _manual(person=False, hand=False)
    TC.place(c, 0.0)
    assert not c.person and c.hand is None


# ---------------------------------------------------------------------------
# the floor
# ---------------------------------------------------------------------------

def test_a_box_takes_its_cells_and_free_keeps_a_body_off():
    fl = T.Floor((-2, -2), (2, 2), z=0.0, cell=0.05)
    fl.add_box((-0.2, -0.2, 0.0), (0.2, 0.2, 1.0))
    assert not fl.is_free((0.0, 0.0), 0.0)
    assert fl.is_free((1.0, 1.0), 0.27)
    assert not fl.is_free((0.0, 0.4), 0.27)           # 0.2 from the box's side
    assert fl.is_free((0.0, 0.55), 0.27)              # 0.35 from it
    assert fl.is_free((10.0, 10.0), 0.27)             # outside the map counts as free
    f = fl.free(0.27)
    ii, jj = np.nonzero(f)
    for i, j in list(zip(ii, jj))[::37]:
        assert fl.clearance(fl.xy(i, j)) >= 0.27 - 1e-9


def test_a_box_below_the_knee_or_above_the_head_is_not_in_the_way():
    fl = T.Floor((-2, -2), (2, 2), z=0.5, cell=0.05)
    fl.add_box((-0.3, -0.3, 0.5), (0.3, 0.3, 0.55))        # a mat on the floor (floor at 0.5)
    fl.add_box((1.0, -0.3, 2.6), (1.4, 0.3, 2.9))          # a beam above the head
    assert fl.is_free((0.0, 0.0), 0.27)
    assert fl.is_free((1.2, 0.0), 0.27)


def test_clear_at_looks_at_the_height():
    fl = T.Floor((-2, -2), (2, 2), z=0.0, cell=0.04)
    fl.add_box((-0.2, -0.2, 1.5), (0.2, 0.2, 1.8))         # a hood at head height
    assert fl.clear_at((0.0, 0.0, 0.9), 0.15, 0.1)
    assert not fl.clear_at((0.0, 0.0, 1.6), 0.15, 0.1)
    assert not fl.clear_at((0.0, 0.3, 1.6), 0.15, 0.1)     # 0.1 beside it
    assert fl.clear_at((0.0, 0.6, 1.6), 0.15, 0.1)         # 0.4 beside it
    assert fl.clear_at((0.0, 0.0, 1.6), 0.15, 0.1) is False


def _wall_floor():
    fl = T.Floor((-3, -3), (3, 3), z=0.0, cell=0.04)
    fl.add_box((-1.0, -0.05, 0.0), (1.0, 0.05, 1.5))
    return fl


def test_the_way_goes_round_an_obstacle_and_stays_clear():
    fl = _wall_floor()
    a, b = (0.0, -1.5), (0.0, 1.5)
    w = fl.way(a, b, T.BODY)
    assert w is not None
    assert np.allclose(w[0], a) and np.allclose(w[-1], b)
    assert len(w) >= 3
    for p, q in zip(w, w[1:]):
        assert fl.line_free(p, q, T.BODY)
        for u in np.linspace(0, 1, 30):
            x = np.asarray(p) + (np.asarray(q) - np.asarray(p)) * u
            assert fl.clearance(x) >= T.BODY - fl.cell, x
    length = sum(np.linalg.norm(np.asarray(q) - np.asarray(p)) for p, q in zip(w, w[1:]))
    assert 3.0 < length < 6.0


def test_way_to_keeps_the_margin_and_reaches_the_goal():
    fl = _wall_floor()
    w = T.way_to(fl, (0.0, -1.5), (0.0, 1.5))
    assert w is not None and np.allclose(w[-1], (0.0, 1.5))
    for p, q in zip(w, w[1:]):
        assert fl.line_free(p, q, T.BODY)


def test_no_way_when_the_goal_is_walled_in():
    fl = T.Floor((-3, -3), (3, 3), z=0.0, cell=0.04)
    for lo, hi in (((-1.0, -1.0, 0), (1.0, -0.9, 1.5)), ((-1.0, 0.9, 0), (1.0, 1.0, 1.5)),
                   ((-1.0, -1.0, 0), (-0.9, 1.0, 1.5)), ((0.9, -1.0, 0), (1.0, 1.0, 1.5))):
        fl.add_box(lo, hi)
    assert fl.way((0.0, -2.5), (0.0, 0.0), T.BODY) is None
    assert T.way_to(fl, (0.0, -2.5), (0.0, 0.0)) is None


def test_the_grid_of_a_huge_area_is_capped():
    fl = T.Floor((-500, -500), (500, 500), cell=0.05, max_cells=320)
    assert fl.cell >= 1000 / 320 - 1e-9
    assert max(fl.shape) <= 322
    fl.add_box((-1, -1, 0), (1, 1, 1))
    assert not fl.is_free((0, 0), 0.0)


@pytest.mark.xfail(reason="fault: Floor.way returns None when the start (or goal) lies outside the floor map although "
                          "is_free counts outside as free – a start spot the owner moves further than tc_person.AREA "
                          "(4 m) from the spindle, with the straight line blocked, gives 'no clear way' and the "
                          "operator stands at the machine from the start", strict=True)
def test_a_start_outside_the_map_still_finds_its_way():
    fl = _wall_floor()
    w = T.way_to(fl, (0.0, -5.0), (0.0, 1.5))
    assert w is not None


# ---------------------------------------------------------------------------
# the stand spot, the trolley, the tools on it
# ---------------------------------------------------------------------------

def _machine_floor(door: float = 0.0, door_dir: float = 1.0):
    fl = T.Floor((-3, -3), (3, 3), z=0.0, cell=0.04)
    for lo, hi in MACHINE:
        fl.add_box(lo, hi)
    if door:
        fl.add_box(*DOOR_BOX)
        fl.add_box(DOOR_BOX[0] + np.array((door * door_dir, 0, 0)), DOOR_BOX[1] + np.array((door * door_dir, 0, 0)))
    return fl


MACHINE = (((-0.4, 0.0, 0.0), (0.4, 0.8, 0.95)),        # the base with the table
           ((-0.25, 0.5, 0.0), (0.25, 0.8, 2.0)),        # the column
           ((-0.12, 0.12, 1.2), (0.12, 0.5, 1.6)))       # the head above the holder
DOOR_BOX = (np.array((-0.45, -0.03, 0.95)), np.array((0.05, -0.01, 1.9)))
HOLDER = np.array((0.0, 0.2, 1.1))
BUTTON = (np.array((-0.13, 0.12, 1.3)), np.array((0.0, -1.0, 0.0)))


def _in_box_xy(p, lo, hi, grow=0.0):
    return lo[0] - grow <= p[0] <= hi[0] + grow and lo[1] - grow <= p[1] <= hi[1] + grow


def test_the_stand_spot_is_free_and_in_front():
    fl = _machine_floor()
    s = T.stand_spot(fl, HOLDER[:2], (0.0, -1.0))
    assert s is not None
    assert fl.is_free(s, T.WORK_ROOM)
    assert s[1] < 0.0                                   # in front of the machine (its front faces -y)
    assert abs(s[0] - HOLDER[0]) < 0.2
    assert 0.3 <= np.linalg.norm(s - HOLDER[:2]) <= 0.8
    # facing the other way round: the spot is on that side
    s2 = T.stand_spot(fl, (0.0, 0.7), (0.0, 1.0))
    assert s2 is not None and s2[1] > 0.8


def test_no_stand_spot_when_everything_is_taken():
    fl = T.Floor((-1, -1), (1, 1), z=0.0, cell=0.05)
    fl.add_box((-1, -1, 0), (1, 1, 1.5))
    assert T.stand_spot(fl, (0, 0), (0, -1), far=0.9) is None


@pytest.mark.parametrize("right", [True, False])
def test_the_trolley_stands_free_on_the_asked_side(right):
    fl = _machine_floor()
    s = T.stand_spot(fl, HOLDER[:2], (0.0, -1.0))
    h = PL.heading_of(HOLDER[:2] - s)
    out = T.trolley_spot(fl, s, h, right=right)
    assert out is not None
    c, th = out
    assert fl.is_free(c, T.TROLLEY_BODY)
    assert fl.clearance(c) >= T.TROLLEY_BODY - 1e-9
    side = float(np.dot(c - s, PL.left_of(h)))
    assert (side < -0.4) if right else (side > 0.4)
    assert np.linalg.norm(c - s) >= 0.5                # not where the person stands
    assert th == pytest.approx(h)


def _trolley(n_tools=2, r=0.03, heading=math.pi):
    tr = T.Trolley(np.array((0.5, -0.4)), heading, 0.96)
    grips = {}
    for n in range(1, n_tools + 1):
        W = T.m4(np.eye(3), (0, 0, 0)) @ T.m4(np.eye(3), (0, 0, -0.12))
        grips[n] = (PL.inv4(W), r)      # the grip frame 0.12 above the tool's own origin (its tip), along its z
    T.place_tools(tr, list(range(1, n_tools + 1)), grips, heading)
    return tr, grips


def _tool_axis(tr, grips, n):
    """(grip point, unit axis) of tool n lying on the trolley."""
    G = tr.slots[n] @ grips[n][0]
    return G[:3, 3], G[:3, 2]


@pytest.mark.parametrize("count", [1, 2, 3, 6])
def test_tools_lie_across_the_trolley_s_top_apart(count):
    r = 0.03
    tr, grips = _trolley(count, r)
    f = np.array((*PL.facing(tr.heading), 0.0))
    left = np.array((*PL.left_of(tr.heading), 0.0))
    L, W, _H = T.TROLLEY_SIZE
    pts = []
    for n in range(1, count + 1):
        p, ax = _tool_axis(tr, grips, n)
        assert abs(ax[2]) < 1e-9                                  # lying
        assert abs(np.dot(ax, f)) < 1e-9                          # across: its axis to the person's left / right
        assert abs(np.dot(ax, left)) == pytest.approx(1.0)
        assert p[2] - r == pytest.approx(tr.top, abs=0.005)      # on the top, not in it, not above it
        rel = p[:2] - tr.centre
        assert abs(np.dot(rel, f[:2])) + r <= L / 2 + 1e-9
        assert abs(np.dot(rel, left[:2])) + r <= W / 2 + 1e-9
        pts.append(p)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            assert np.linalg.norm(pts[i] - pts[j]) >= 2 * r, "two tools lie in each other"


@pytest.mark.xfail(reason="fault: place_tools squeezes the row into the trolley's length without a check: with "
                          "more than about 10 tools of Ø60 they lie in each other (12 tools: 51 mm apart)",
                   strict=True)
def test_many_tools_do_not_lie_in_each_other():
    r = 0.03
    tr, grips = _trolley(12, r)
    pts = [_tool_axis(tr, grips, n)[0] for n in range(1, 13)]
    d = min(np.linalg.norm(a - b) for i, a in enumerate(pts) for b in pts[i + 1:])
    assert d >= 2 * r


# ---------------------------------------------------------------------------
# the door
# ---------------------------------------------------------------------------

def test_a_sliding_door_moves_along_its_direction():
    d = T.Door("SLIDE", np.zeros(3), np.array((2.0, 0.0, 0.0)), 0.0, 0.5, np.array((0.1, -0.04, 1.1)),
               np.array((0.0, -1.0, 0.0)))
    assert np.allclose(d.move(0.0), np.eye(4))
    assert np.allclose(d.at(0.5, d.handle), d.handle + (0.5, 0, 0))
    assert np.allclose(d.at(0.2, (1.0, 2.0, 3.0)), (1.2, 2.0, 3.0))
    assert d.travel_time() == pytest.approx(max(TC.DOOR_MIN, 0.5 / 0.7))
    d2 = T.Door("SLIDE", np.zeros(3), np.array((1.0, 0.0, 0.0)), 0.1, -0.4, np.zeros(3), np.array((0, -1.0, 0)))
    assert np.allclose(d2.at(-0.4, (0, 0, 0)), (-0.5, 0, 0))
    assert d2.travel_time() == pytest.approx(max(TC.DOOR_MIN, 0.5 / 0.7))


def test_a_hinged_door_turns_about_its_axis():
    o = np.array((1.0, -0.2, 0.0))
    d = T.Door("ROTATE", o, np.array((0.0, 0.0, 1.0)), 0.0, math.radians(90), np.array((0.4, -0.2, 1.1)),
               np.array((0.0, -1.0, 0.0)))
    assert np.allclose(d.move(0.0), np.eye(4))
    p = d.at(math.radians(90), d.handle)
    assert np.allclose(p, (1.0, -0.8, 1.1), atol=1e-9)      # +90° about +z: -x becomes -y
    for v in np.linspace(0, math.radians(90), 7):
        q = d.at(v, d.handle)
        assert np.linalg.norm(q[:2] - o[:2]) == pytest.approx(0.6)
        assert q[2] == pytest.approx(1.1)
    M = d.move(0.7)
    assert np.allclose(M[:3, :3] @ M[:3, :3].T, np.eye(3))
    assert np.allclose(d.at(0.7, o), o)                       # the hinge stays
    assert d.travel_time() == pytest.approx(max(TC.DOOR_MIN, math.radians(90) / math.radians(110)))


# ---------------------------------------------------------------------------
# hands
# ---------------------------------------------------------------------------

PALM_HALF = 0.016           # m: half the palm's thickness (props_detail._hand: the palm limb's 0.016–0.018)


def _holder_frame(right_way=(1.0, 0.0, 0.0)):
    H = T.m4(T.frame_of((0, 0, 1), (0, 1, 0)), HOLDER)
    return H, np.asarray(right_way, float)


@pytest.mark.parametrize("r", [0.012, 0.025, 0.04])
def test_grip_hand_palm_faces_the_holder_and_thumb_along_it(r):
    k = 1.0
    H, rw = _holder_frame()
    M = T.grip_hand(H, k, r, rw)
    X, Y, Z = M[:3, 0], M[:3, 1], M[:3, 2]
    assert np.allclose(M[:3, :3].T @ M[:3, :3], np.eye(3), atol=1e-9)
    assert np.linalg.det(M[:3, :3]) == pytest.approx(1.0)
    assert np.dot(X, -rw) > 0.9                     # the palm (x, right hand) faces the holder
    thumb = -Y
    assert math.degrees(math.acos(np.clip(np.dot(thumb, H[:3, 2]), -1, 1))) == pytest.approx(T.THUMB_TILT, abs=1)
    # the hand is on the right_way side of the holder
    assert np.dot(M[:3, 3] - HOLDER, rw) > 0


@pytest.mark.parametrize("r", [0.02, 0.025, 0.032])
@pytest.mark.xfail(reason="fault: grip_hand puts the holder's axis 13-15 mm from the hand bone (props_detail's palm "
                          "is ±16 mm thick): a Ø50 holder goes through the palm and out of the back of the hand. "
                          "The holder-radius correction in grip_hand moves the axis towards the palm instead of "
                          "away from it (sign of -(holder_r + GRIP_GAP - 0.016))", strict=True)
def test_the_holder_lies_in_the_fist_not_in_the_palm(r):
    """The holder's axis must be on the palm side of the hand bone, at least the palm's half thickness plus the
    holder's radius away (a few mm of glove allowed), and the closed fist round it (the people module's grip point
    lies between the palm and the axis)."""
    k = 1.0
    H, rw = _holder_frame()
    M = T.grip_hand(H, k, r, rw)
    # the hand bone from the wrist to the knuckles (props_detail: palm 0.095 long, along -z)
    for along in (0.04, 0.07, 0.09):
        p = M[:3, 3] + M[:3, :3] @ np.array((0.0, 0.0, -along * k))
        rel = p - HOLDER
        rel -= H[:3, 2] * np.dot(rel, H[:3, 2])
        assert np.linalg.norm(rel) >= r + PALM_HALF - 0.004, f"{along}: the bone {np.linalg.norm(rel) / MM:.0f} mm off"
    g = M @ np.r_[PL._grip_local("r", k), 1.0]
    rel = g[:3] - HOLDER
    rel -= H[:3, 2] * np.dot(rel, H[:3, 2])
    assert np.linalg.norm(rel) <= r + 0.006


def test_grip_hand_open_by_moves_the_palm_off():
    H, rw = _holder_frame()
    a = T.grip_hand(H, 1.0, 0.025, rw)
    b = T.grip_hand(H, 1.0, 0.025, rw, open_by=0.035)
    assert np.allclose(a[:3, :3], b[:3, :3])
    assert np.allclose(b[:3, 3] - a[:3, 3], rw * 0.035)


@pytest.mark.parametrize("face", [(0.0, -1.0, 0.0), (0.6, -0.8, 0.0), (0.0, -0.8, 0.6)])
@pytest.mark.parametrize("side", ["l", "r"])
def test_press_hand_puts_the_index_tip_on_the_button(face, side):
    k = 1.05
    p = np.array((0.3, 0.1, 1.3))
    n = np.asarray(face) / np.linalg.norm(face)
    for press in (0.0, T.PRESS):
        M = T.press_hand(p, n, k, side=side, press=press)
        tip = M @ np.r_[np.asarray(T.INDEX_TIP) * k, 1.0]
        off = float(np.dot(tip[:3] - p, n))
        assert -press - 1e-9 <= off <= 0.006           # on the button, pushed in by ``press``
        assert np.linalg.norm((tip[:3] - p) - n * off) < 1e-6
        fingers = -M[:3, 2]
        assert np.dot(fingers, -n) > 0.99               # the finger points into the face
        assert np.allclose(M[:3, :3].T @ M[:3, :3], np.eye(3), atol=1e-9)
        assert np.linalg.det(M[:3, :3]) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# the operator on a made-up machine
# ---------------------------------------------------------------------------

class Setup:
    """A made-up machine (``MACHINE``), the holder at ``HOLDER`` (z up into the spindle), tools T1–T3, a trolley, a
    way in from 2.5 m in front and to the right, changes at ``t0s`` (old → new: 1→2, 2→3, 3→1)."""

    def __init__(self, height=1.75, t0s=(8.0,), door=0.0, door_dir=1.0, side="RIGHT", extra=0.0, button=True):
        self.fl = fl = _machine_floor(door, door_dir)
        self.door = None
        if door:
            handle = np.array((-0.4, -0.041, 1.1)) if door_dir > 0 else np.array((0.0, -0.041, 1.1))
            self.door = T.Door("SLIDE", np.zeros(3), np.array((door_dir, 0.0, 0.0)), 0.0, door, handle,
                               np.array((0.0, -1.0, 0.0)))
        self.stand = T.stand_spot(fl, HOLDER[:2], (0.0, -1.0))
        self.heading = PL.heading_of(HOLDER[:2] - self.stand)
        right = side == "RIGHT"
        tr = T.trolley_spot(fl, self.stand, self.heading, right=right)
        self.trolley_side = side
        if tr is None:
            tr = T.trolley_spot(fl, self.stand, self.heading, right=not right)
            self.trolley_side = "LEFT" if right else "RIGHT"
        assert tr is not None
        self.trolley = T.Trolley(tr[0], tr[1], 0.96)
        rw = -np.array((*PL.left_of(self.heading), 0.0))
        self.H = T.m4(T.frame_of((0, 0, 1), rw), HOLDER)
        self.W = {n: self.H @ T.m4(np.eye(3), (0.0, 0.0, -0.11 - 0.01 * n)) for n in (1, 2, 3)}
        self.grips = {n: (PL.inv4(self.W[n]) @ self.H, 0.03) for n in self.W}
        T.place_tools(self.trolley, [1, 2, 3], self.grips, self.heading)
        self.start = self.stand + np.array((1.2, -2.5))
        self.way = T.way_to(fl, self.start, self.stand)
        assert self.way is not None
        self.door_s = self.door.travel_time() if self.door is not None else 0.0
        self.length = TC.person_min(self.door_s) + extra
        seq = [(1, 2), (2, 3), (3, 1)]
        self.stations = []
        for i, t0 in enumerate(t0s):
            o, n = seq[i % 3]
            self.stations.append(T.Station(o, n, t0, self.length, self.H, {o: self.W[o], n: self.W[n]}, self.grips,
                                           button=BUTTON if button else None, door=self.door_s))
        self.op = T.Operator(height, self.way[0], self.stand, self.way, self.stations, self.trolley, 0.0,
                             door=self.door, floor=fl)
        self.op.plan()
        last = self.stations[-1]
        self.times = [i / FPS for i in range(int(FPS * (last.t0 + last.length + 7.0)))]
        self.rows = self.op.sample(self.times)
        self.fig = self.op.fig

    def keys(self, s):
        return TC.person_keys(s.t0, s.length, s.door)

    def end_of(self, s, name):
        return next(b for _a, b, n in self.keys(s) if n == name)

    def at(self, t):
        """One exact moment: (root, pose, tools, door value)."""
        return self.op.sample([t])[0]

    def bone(self, row, bone):
        root, pose = row[0], row[1]
        h, Rb, _t = self.fig.fk(pose)[bone]
        return T.to_world(root, T.m4(Rb, h))

    def windows(self):
        return [(self.keys(s)[0][0], self.keys(s)[-1][1]) for s in self.stations]


@functools.lru_cache(maxsize=None)
def setup(**kw):
    return Setup(**kw)


def _setup(**kw):
    return setup(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in kw.items()})


def test_the_root_never_stands_in_the_machine():
    s = _setup()
    for t, row in zip(s.times, s.rows):
        root = row[0]
        for lo, hi in MACHINE:
            assert not _in_box_xy(root, lo, hi, grow=0.15), f"{t:.2f} s: the person stands in the machine"
        assert s.fl.clearance(root[:2]) >= T.WORK_ROOM - s.fl.cell, t


def test_it_walks_in_stands_and_walks_out():
    s = _setup()
    st = s.stations[0]
    roots = np.array([r[0] for r in s.rows])
    t = np.array(s.times)
    assert np.allclose(roots[0, :2], s.way[0], atol=0.02)               # it starts at the start spot
    at_machine = (t >= st.t0 - T.ARRIVE + 0.02) & (t <= st.t0 + st.length)
    assert np.allclose(roots[at_machine, :2], s.stand, atol=0.02)       # it stands at the spot through the change
    assert np.linalg.norm(roots[-1, :2] - s.stand) > 1.5                 # and walks away afterwards
    assert not s.op.at_start
    # it faces the machine while it works
    h = roots[at_machine, 3]
    assert np.allclose(np.cos(h - s.heading), 1.0, atol=2e-3)


def test_the_hand_reaches_the_holder_at_the_grip():
    s = _setup()
    st = s.stations[0]
    aim = T.grip_hand(st.spindle, s.op.k, st.holder_r, s.op._right_way(s.at(st.t0)[0]))
    for name in ("grip", "release", "insert", "clamp"):
        row = s.at(s.end_of(st, name))
        hand = s.bone(row, "r_hand")
        assert np.linalg.norm(hand[:3, 3] - aim[:3, 3]) < 4 * MM, name
        assert R.angle_between(hand[:3, :3], aim[:3, :3]) < math.radians(3), name
    big = [m for m in s.op.misses if m[2] > 0.004]
    assert not big, big[:5]


def test_the_left_hand_presses_the_button_while_the_tool_comes_out():
    s = _setup()
    st = s.stations[0]
    for name in ("release", "insert"):
        row = s.at(s.end_of(st, name))
        hand = s.bone(row, "l_hand")
        tip = hand @ np.r_[np.asarray(T.INDEX_TIP) * s.op.k, 1.0]
        assert np.linalg.norm(tip[:3] - BUTTON[0]) < 6 * MM, name
        assert row[1].point["l"] > 0.9


def test_no_button_leaves_the_left_hand_down():
    s = _setup(button=False)
    st = s.stations[0]
    row = s.at(s.end_of(st, "release"))
    hand = s.bone(row, "l_hand")
    assert hand[2, 3] < 1.0                      # hanging at the side


def test_the_carried_tool_follows_the_hand_from_spindle_to_trolley_and_back():
    s = _setup()
    st = s.stations[0]
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    set_end, take_end = s.end_of(st, "set"), s.end_of(st, "take")
    row = s.at(out_t)
    assert set(row[2]) == {st.old}
    assert np.allclose(row[2][st.old], s.W[st.old], atol=3 * MM)      # out of the spindle where it sat
    row = s.at(set_end)
    assert np.allclose(row[2][st.old], s.trolley.slots[st.old], atol=3 * MM)   # laid where its trolley copy lies
    row = s.at(take_end)
    assert set(row[2]) == {st.new}
    assert np.allclose(row[2][st.new], s.trolley.slots[st.new], atol=3 * MM)
    row = s.at(in_t)
    assert np.allclose(row[2][st.new], s.W[st.new], atol=3 * MM)      # in the spindle where it will sit
    # nothing is carried before the old tool is out, between "set" and "take", or after the new one is in
    for t in (out_t - 0.05, (set_end + take_end) / 2 if take_end - set_end > 0.1 else None, in_t + 0.05):
        if t is not None:
            assert s.at(t)[2] == {}, t
    # while carried, the tool keeps its place in the hand
    for t in np.linspace(out_t, set_end, 9):
        row = s.at(float(t))
        hand = s.bone(row, "r_hand")
        rel = PL.inv4(hand) @ row[2][st.old]
        rel0 = PL.inv4(s.bone(s.at(out_t), "r_hand")) @ s.at(out_t)[2][st.old]
        assert np.allclose(rel, rel0, atol=1e-6)


def test_the_pulled_tool_comes_straight_down_out_of_the_spindle():
    s = _setup()
    st = s.stations[0]
    out_t = TC.person_events(st.t0, st.length, st.door)[0]
    pull_end = s.end_of(st, "pull")
    ax = st.spindle[:3, 2]
    for t in np.linspace(out_t, pull_end, 6):
        M = s.at(float(t))[2][st.old]
        d = M[:3, 3] - s.W[st.old][:3, 3]
        side = d - ax * np.dot(d, ax)
        assert np.linalg.norm(side) < 4 * MM, t          # not through the spindle's side
        assert np.dot(d, ax) <= 1e-3                     # down, not up into the spindle


def _planted_slides(s, z_max=0.003):
    worst = 0.0
    for side in R.SIDES:
        prev = None
        for row in s.rows:
            root, pose = row[0], row[1]
            pts = np.array([T.to_world(root, T.m4(np.eye(3), p))[:3, 3]
                            for p in s.fig.sole_points(pose, side).values()])
            if prev is not None:
                for a, b in zip(pts, prev):
                    if a[2] < z_max and b[2] < z_max:
                        worst = max(worst, float(np.linalg.norm(a[:2] - b[:2])))
            prev = pts
    return worst


def test_the_feet_stay_planted_while_it_walks():
    s = _setup()
    assert _planted_slides(s) < 0.01                      # m per frame of a sole point on the floor
    lows = []
    for row in s.rows:
        root, pose = row[0], row[1]
        lows.append(min(T.to_world(root, T.m4(np.eye(3), p))[2, 3] for sd in R.SIDES
                        for p in s.fig.sole_points(pose, sd).values()))
    assert min(lows) > -0.015 and max(lows) < 0.02        # always a foot on the floor, never in it


def _worst_jump(s, margin=0.3):
    worst = (0.0, None)
    prev = None
    for t, row in zip(s.times, s.rows):
        root, pose = row[0], row[1]
        fk = s.fig.fk(pose)
        pts = [T.to_world(root, T.m4(np.eye(3), fk[b][0]))[:3, 3] for b in ("r_hand", "l_hand", "head")]
        if prev is not None and any(a - margin <= t <= b + margin for a, b in s.windows()):
            d = max(float(np.linalg.norm(p - q)) for p, q in zip(pts, prev))
            if d > worst[0]:
                worst = (d, t)
        prev = pts
    return worst


def test_no_jumps_at_the_machine():
    s = _setup()
    d, t = _worst_jump(s)
    assert d < 0.1, f"{d:.3f} m in 1/25 s at {t:.2f} s"


@pytest.mark.parametrize("height", [1.65, 1.85])
def test_other_heights_reach_and_carry(height):
    s = _setup(height=height)
    st = s.stations[0]
    assert s.op.fig.height == pytest.approx(height)
    big = [m for m in s.op.misses if m[2] > 0.004]
    assert not big, big[:5]
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM)
    assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM)
    assert np.allclose(s.at(s.end_of(st, "set"))[2][st.old], s.trolley.slots[st.old], atol=3 * MM)
    assert _worst_jump(s)[0] < 0.1


def test_the_door_opens_and_closes_in_its_moves():
    s = _setup(door=0.53)
    st = s.stations[0]
    keys = {n: (a, b) for a, b, n in s.keys(st)}
    assert s.at(st.t0 - 1.0)[3] == pytest.approx(0.0)
    assert s.at(keys["open"][1])[3] == pytest.approx(0.53)
    assert s.at(keys["reach"][0])[3] == pytest.approx(0.53)
    assert s.at(keys["clamp"][1])[3] == pytest.approx(0.53)
    assert s.at(keys["close"][1])[3] == pytest.approx(0.0)
    assert s.at(st.t0 + st.length + 2.0)[3] == pytest.approx(0.0)
    vals = [s.at(t)[3] for t in np.linspace(*keys["open"], 9)]
    assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:]))      # it opens steadily
    # the hand holds the handle while it pulls the door open
    for t in np.linspace(*keys["open"], 5):
        row = s.at(float(t))
        hand = s.bone(row, "r_hand")
        g = hand @ np.r_[PL._grip_local("r", s.op.k), 1.0]
        assert np.linalg.norm(g[:3] - s.door.at(row[3], s.door.handle)) < 0.03, t
    # and it still changes the tool
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM)
    assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM)
    assert _worst_jump(s)[0] < 0.1


@pytest.mark.xfail(reason="fault: a 1.85 m person at a machine with a door (stand spot 0.3 m off) misses its aims by "
                          "up to 25 mm in to_door / pull / away / fetch / insert / let_go2 – more than the 20 mm at "
                          "which bake() warns 'the operator's hand stays 3 cm short of the tool' (also in let_go2, "
                          "where it holds no tool)", strict=True)
def test_a_tall_person_with_a_door_reaches_everything():
    s = _setup(height=1.85, door=0.53, t0s=(9.0,))
    big = [m for m in s.op.misses if m[2] > 0.02]
    assert not big, [(round(m[0], 2), m[3], round(m[2], 3)) for m in big[:5]]


@pytest.mark.xfail(reason="fault: a door that slides 1.5 m (out of reach): _door_aim thinks the hand can follow the "
                          "handle until 10.24 s (_reachable assumes the full lean) but pose() leans only part of the "
                          "way mid-move: the hand stays up to 25 cm off its aim in open / to_close / close, and the "
                          "hands / head jump 0.15 m in one frame (10.44 s)", strict=True)
def test_a_door_that_slides_out_of_reach():
    s = _setup(door=1.5, door_dir=-1.0, t0s=(9.0,))
    assert s.trolley_side == "RIGHT"
    st = s.stations[0]
    keys = {n: (a, b) for a, b, n in s.keys(st)}
    assert s.at(keys["open"][1])[3] == pytest.approx(1.5)
    assert s.at(keys["close"][1])[3] == pytest.approx(0.0)
    big = [m for m in s.op.misses if m[2] > 0.02]
    assert not big, [(round(m[0], 2), m[3], round(m[2], 3)) for m in big[:5]]
    assert _worst_jump(s)[0] < 0.1


def test_a_door_that_slides_out_of_reach_still_works():
    """The part of the case above that works: the door opens all the way and closes, the tools are changed."""
    s = _setup(door=1.5, door_dir=-1.0, t0s=(9.0,))
    st = s.stations[0]
    keys = {n: (a, b) for a, b, n in s.keys(st)}
    assert s.at(keys["open"][1])[3] == pytest.approx(1.5)
    assert s.at(keys["close"][1])[3] == pytest.approx(0.0)
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM)
    assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM)
    # it takes the handle at the start of the door's move
    row = s.at(keys["open"][0] + 0.02)
    g = s.bone(row, "r_hand") @ np.r_[PL._grip_local("r", s.op.k), 1.0]
    assert np.linalg.norm(g[:3] - s.door.at(row[3], s.door.handle)) < 0.03


@pytest.mark.xfail(reason="fault: with the trolley on the operator's LEFT (op_trolley_side, or the fallback when the "
                          "right side has no room) the right hand still lays the tool down and takes the new one: it "
                          "stays up to 16 cm short of the trolley, so the carried tool vanishes 14 cm from where its "
                          "trolley copy appears, and bake() warns", strict=True)
def test_the_trolley_on_the_left():
    s = _setup(side="LEFT")
    assert s.trolley_side == "LEFT"
    st = s.stations[0]
    assert np.allclose(s.at(s.end_of(st, "set"))[2][st.old], s.trolley.slots[st.old], atol=5 * MM)
    assert np.allclose(s.at(s.end_of(st, "take"))[2][st.new], s.trolley.slots[st.new], atol=5 * MM)
    big = [m for m in s.op.misses if m[2] > 0.02]
    assert not big, [(round(m[0], 2), m[3], round(m[2], 3)) for m in big[:5]]


def test_a_longer_pause_waits_by_the_trolley_and_still_changes():
    s = _setup(extra=3.0)
    st = s.stations[0]
    names = [n for _a, _b, n in s.keys(st)]
    assert "wait" in names
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM)
    assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM)
    assert _worst_jump(s)[0] < 0.1


def test_a_change_too_early_to_walk_in_stands_there_from_the_start():
    s = _setup(t0s=(1.0,))
    assert s.op.at_start
    assert any("too early" in n for n in s.op.notes)
    st = s.stations[0]
    for t, row in zip(s.times, s.rows):
        if t <= st.t0 + st.length:
            assert np.allclose(row[0][:2], s.stand, atol=0.02), t
    out_t, in_t = TC.person_events(st.t0, st.length, st.door)
    assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM)
    assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM)
    assert np.linalg.norm(s.rows[-1][0][:2] - s.stand) > 1.0          # it walks away afterwards


def test_several_changes_in_a_row():
    s = _setup(t0s=(8.0, 17.0, 26.0))
    assert len(s.op.change_times()) == 3
    for st in s.stations:
        out_t, in_t = TC.person_events(st.t0, st.length, st.door)
        assert np.allclose(s.at(out_t)[2][st.old], s.W[st.old], atol=3 * MM), st.t0
        assert np.allclose(s.at(in_t)[2][st.new], s.W[st.new], atol=3 * MM), st.t0
        assert np.allclose(s.at(s.end_of(st, "set"))[2][st.old], s.trolley.slots[st.old], atol=3 * MM)
        assert np.allclose(s.at(s.end_of(st, "take"))[2][st.new], s.trolley.slots[st.new], atol=3 * MM)
    # it stays at the machine between the changes (no walking off and back)
    first, last = s.stations[0], s.stations[-1]
    for t, row in zip(s.times, s.rows):
        if first.t0 <= t <= last.t0 + last.length:
            assert np.allclose(row[0][:2], s.stand, atol=0.02), t
        if not any(a - 0.1 <= t <= b + 0.1 for a, b in s.windows()):
            assert row[2] == {}, t
    assert _worst_jump(s)[0] < 0.1
    assert not [m for m in s.op.misses if m[2] > 0.004]
    rows = s.op.change_times()
    assert all(r[2] == pytest.approx(s.length) for r in rows)


def test_no_changes_is_an_error_not_a_silent_person():
    fl = _machine_floor()
    op = T.Operator(1.75, (0, -2), (0, -0.3), [(0, -2), (0, -0.3)], [], None, 0.0, floor=fl)
    with pytest.raises(ValueError):
        op.plan()
