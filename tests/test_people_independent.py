"""Independent tests of task 0157 (people: paths, gaits, actions, carried items, meetings) – no Blender.

Written from the brief by an agent that did not write the code: they try to break ``core/people.py`` and
``core/person_rig.py``. Conventions (from ``core/people.py``): the figure faces -y in its own space, a root is
(x, y, z, heading) and the heading turns the figure about z (``people._to_fig`` is the inverse of ``_world`` below).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from fresing_render.core import people as C
from fresing_render.core import person_rig as R
from fresing_render.core import props_detail as P
from fresing_render.core import surroundings as S

A = C.Action
PS = C.PersonSpec


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _world(root, v):
    """A figure-space point into the world (the inverse of ``people._to_fig``)."""
    x, y, z, h = root
    c, s = math.cos(h), math.sin(h)
    return np.array((c * v[0] - s * v[1] + x, s * v[0] + c * v[1] + y, v[2] + z))


def _root4(root):
    x, y, z, h = root
    return C.m4(R.rz(h), (x, y, z))


def _soles(fig, root, pose, side):
    return {k: _world(root, v) for k, v in fig.sole_points(pose, side).items()}


def _flat(x, y, z=None):
    return 0.0


def _feet_report(pl, fps=30.0, ground=_flat):
    """(worst slide of the point a standing foot rests on, worst depth of a sole point below the ground, worst gap
    between the ankle the legs reach and the ankle the feet plan wants, where the worst slide happened)."""
    slide, below, reach, where = 0.0, 0.0, 0.0, None
    for name, per in pl.people.items():
        fig = per.fig
        k = fig.k
        n = int(pl.length * fps) + 1
        for i in range(n):
            t = i / fps
            root, pose = pl.pose_at(name, t)
            fk = fig.fk(pose)
            for side in ("l", "r"):
                ft = per.feet[side]
                ank_plan, _yaw, _pitch = ft.state(t, k)
                reach = max(reach, float(np.linalg.norm(_world(root, fk[f"{side}_foot"][0]) - ank_plan)))
                sp = _soles(fig, root, pose, side)
                for v in sp.values():
                    below = max(below, float(ground(v[0], v[1], v[2])) - float(v[2]))
                p = ft.on_floor(t)
                if p is None:
                    continue
                F0 = np.array((math.sin(p.yaw), -math.cos(p.yaw), 0.0))
                sl = getattr(p, "slope", 0.0)                           # the sole lies on a tilted floor
                F = F0 * math.cos(sl) + np.array((0.0, 0.0, math.sin(sl)))
                U = np.array((0.0, 0.0, math.cos(sl))) - F0 * math.sin(sl)
                base = p.pos - U * (P.ANKLE_H * k)
                heel, toe = base + F * C.HEEL_AT * k, base + F * C.TOE_AT * k
                if p.roll_in > 0 and t < p.down + p.roll_in:            # heel roll: the heel stays
                    d = np.linalg.norm(sp["heel"] - heel)
                elif p.roll_out > 0 and t > p.up - p.roll_out:          # toe roll: the toe tip stays
                    d = np.linalg.norm(sp["toe"] - toe)
                else:                                                   # flat: the whole sole stays
                    d = max(np.linalg.norm(sp["heel"] - heel), np.linalg.norm(sp["toe"] - toe))
                if d > slide:
                    slide, where = float(d), (name, side, round(t, 3))
    return slide, below, reach, where


def _walk_seg(pl, name="A"):
    return next(s for s in pl.people[name].segs if s.kind == "WALK")


def _item_world_in_hand(pl, st, t):
    """Where a HELD item is at ``t``: the hand bone's frame (figure space -> world) times its grip."""
    per = pl.people[st.person]
    root, pose = pl.pose_at(st.person, t)
    head, Rh = per.fig.frame(pose, f"{st.side}_hand")
    return _root4(root) @ C.m4(Rh, head) @ st.grip


def _grip_point_world(pl, name, t, side="r"):
    """The point a closed hand holds (``people._grip_local`` in the hand bone's frame), world."""
    per = pl.people[name]
    root, pose = pl.pose_at(name, t)
    head, Rh = per.fig.frame(pose, f"{side}_hand")
    return _world(root, head + Rh @ C._grip_local(side, per.fig.k))


def _example(order=("Anna", "Ben"), x0=3.0):
    """The owner's example in pure Python (as ``blender/people.set_up_example`` sets it up)."""
    ben = PS("Ben", height=1.85, place=(x0 + 0.8, -0.4, 0.0), heading=math.radians(90),
             actions=(A("IDLE", duration=1.5), A("GREET", other="Anna"), A("TALK", other="Anna", duration=6.0)))
    anna = PS("Anna", height=1.65, place=(x0 + 0.3, 5.0, 0.0), heading=0.0,
              path=((x0 + 0.3, 2.2, 0.0), (x0, -0.4, 0.0)),
              actions=(A("WALK", place="END"), A("PUT_DOWN"), A("GREET", other="Ben"),
                       A("TALK", other="Ben", duration=6.0)), carry="box")
    box = C.ItemSpec("box", "TOOLBOX", (x0 + 1.6, 5.0, 0.0))
    people = {"Anna": anna, "Ben": ben}
    return C.plan([people[n] for n in order], [box])


# ---------------------------------------------------------------------------
# the path
# ---------------------------------------------------------------------------

POLYLINES = [
    [(0, 0), (4, 0)],
    [(0, 0), (3, 0), (3, 3)],
    [(0, 0), (2, -2), (0, -4), (2, -6), (-1, -6)],
    [(0, 0), (1, 0), (1.1, 0.05), (5, 0)],                    # a nearly straight kink
    [(0, 0), (5, 0), (0.2, 0.6)],                             # a sharp hairpin (not quite back the same way)
    [(math.cos(i) * (2 + 0.3 * i), math.sin(i) * (2 + 0.3 * i)) for i in range(20)],   # 20 points
]


@pytest.mark.parametrize("pts", POLYLINES)
def test_path_runs_through_its_ends_and_rounding_never_lengthens_it(pts):
    poly = np.asarray(pts, float)
    poly_len = float(np.linalg.norm(np.diff(poly, axis=0), axis=1).sum())
    for radius in (0.0001, 0.3, 0.6, 5.0):
        p = C.Path(pts, radius)
        assert np.allclose(p.at(0.0), poly[0], atol=1e-9), "the path starts on its first point"
        assert np.allclose(p.at(p.length), poly[-1], atol=1e-9), "the path ends on its last point"
        assert p.length <= poly_len + 1e-9, f"rounded corners are never longer ({p.length} > {poly_len})"
        assert p.length > 0.5 * poly_len
        # s runs from 0 to length and is increasing; at() past the ends stays on the ends
        assert p.s[0] == 0.0 and np.all(np.diff(p.s) >= 0)
        assert np.allclose(p.at(-3.0), poly[0]) and np.allclose(p.at(p.length + 3.0), poly[-1])
        # the rounded path stays near the polyline (no farther than the radius asked for, or half a leg)
        for s in np.linspace(0, p.length, 50):
            q = p.at(s)
            d = min(_seg_dist(q, poly[i], poly[i + 1]) for i in range(len(poly) - 1))
            assert d <= radius + 1e-6 or d <= 0.5 * poly_len, (s, d)


def _seg_dist(q, a, b):
    ab = b - a
    u = float(np.clip(np.dot(q - a, ab) / max(1e-12, np.dot(ab, ab)), 0.0, 1.0))
    return float(np.linalg.norm(q - (a + ab * u)))


def test_path_with_duplicate_points_and_a_single_point():
    p = C.Path([(1, 1), (1, 1), (1, 1)])
    assert p.length == 0.0 and np.allclose(p.at(0.3), (1, 1))
    t = p.tangent(0.0)
    assert np.isfinite(t).all() and abs(np.linalg.norm(t) - 1) < 1e-9
    p = C.Path([(0, 0), (0, 0), (2, 0), (2, 0), (2, 2), (2, 2)])
    assert np.allclose(p.at(0), (0, 0)) and np.allclose(p.at(p.length), (2, 2))
    assert 2.5 < p.length <= 4.0


def test_path_that_turns_straight_back_does_not_crash():
    """The person walks 4 m and comes back the same way: a corner of 180° (the owner can click that)."""
    p = C.Path([(0, 0), (0, -4), (0, 0)])                     # raised ZeroDivisionError in rounded_path
    assert np.allclose(p.at(p.length), (0, 0))
    assert 7.0 < p.length <= 8.0 + 1e-9


def test_plan_with_a_path_back_the_same_way_warns_or_walks_never_raises():
    sp = PS("A", path=((0, -4, 0), (0, 0, 0)), actions=(A("WALK", place="END"),))
    pl = C.plan([sp])                                          # raised ZeroDivisionError
    assert pl.length > 4.0
    slide, below, _reach, where = _feet_report(pl)
    assert slide < 0.002 and below < 0.003, (slide, below, where)


# ---------------------------------------------------------------------------
# gaits: speed, step length, cadence
# ---------------------------------------------------------------------------

def test_gait_table_is_sane():
    speeds = [C.GAITS[g].speed for g in ("STROLL", "WALK", "BRISK", "RUN")]
    assert speeds == sorted(speeds), "stroll < walk < brisk < run"
    for gid, g in C.GAITS.items():
        f = g.speed / g.step
        assert 1.2 < f < 3.5, f"{gid}: {f:.2f} steps per second is not a human cadence"
        assert (g.duty < 0.5) == (gid == "RUN"), "only the run has a flight phase"
    assert C.GAITS["CARRY"].speed < C.GAITS["WALK"].speed
    assert {g[0] for g in C.GAIT_ITEMS} == set(C.GAITS)


@pytest.mark.parametrize("gait", sorted(C.GAITS))
@pytest.mark.parametrize("height", (1.65, 1.75, 1.85))
@pytest.mark.parametrize("dist", (1.2, 4.0, 25.0))
def test_walk_speed_step_length_and_cadence(gait, height, dist):
    g = C.GAITS[gait]
    k = height / P.REST_HEIGHT
    sp = PS("A", height=height, path=((0.0, -dist, 0.0),), actions=(A("WALK", place="END", gait=gait),))
    pl = C.plan([sp])
    assert not pl.warnings
    seg = _walk_seg(pl)
    m, f = seg.data["m"], seg.data["f"]
    Ls = dist / m
    assert 0.5 * g.step * k <= Ls <= 1.5 * g.step * k, f"step {Ls:.2f} m vs the gait's {g.step * k:.2f} m"
    assert Ls * f == pytest.approx(g.speed, rel=1e-6), "speed = step length x steps per second"
    # the root moves at the gait's speed once under way (between the second step and the second last)
    per = pl.people["A"]
    if m >= 4:
        t0, t1 = seg.t0 + 2.0 / f, seg.t1 - 2.0 / f
        a, b = per.root(t0), per.root(t1)
        v = math.hypot(b[0] - a[0], b[1] - a[1]) / (t1 - t0)
        assert v == pytest.approx(g.speed, rel=0.01)
    if dist >= 20:
        mean = dist / (seg.t1 - seg.t0)
        assert mean == pytest.approx(g.speed, rel=0.05), "a long walk keeps the gait's speed on average"
    # the walk ends exactly on its point, standing on both feet beside it
    end = per.root(pl.length + 1.0)
    assert end[0] == pytest.approx(0.0, abs=1e-9) and end[1] == pytest.approx(-dist, abs=1e-9)
    for side in ("l", "r"):
        last = per.feet[side].last
        assert abs(math.hypot(last.pos[0], last.pos[1] + dist) - 0.095 * k) < 0.01, "feet end beside the point"


@pytest.mark.parametrize("gait", sorted(C.GAITS))
def test_feet_never_slide_or_sink_on_a_straight_walk(gait):
    sp = PS("A", path=((0.0, -6.0, 0.0),), actions=(A("WALK", place="END", gait=gait),))
    slide, below, reach, where = _feet_report(C.plan([sp]))
    assert slide < 0.002, f"a standing foot slides {slide * 1000:.1f} mm at {where}"
    assert below < 0.003, f"a sole goes {below * 1000:.1f} mm below the floor"


FEET_CASES = {
    "zigzag": [PS("A", path=((2, -2, 0), (0, -4, 0), (2, -6, 0), (-1, -6, 0)), actions=(A("WALK", place="END"),))],
    "point by point and back": [PS("A", path=((0, -4, 0), (3, -4, 0), (0, 0, 0)),
                                   actions=(A("WALK", place="POINT", point=2), A("WALK", place="POINT", point=1),
                                            A("WALK", place="POINT", point=0)))],
    "turns on the spot": [PS("A", path=((0, -1.5, 0),),
                             actions=(A("WALK", place="END"), A("TURN", target=(3, -1.5, 0)),
                                      A("TURN", target=(0, 5, 0)), A("TURN", target=(0.1, -9, 0)),
                                      A("TURN", target=(-3, -1.4, 0))))],
    "short 1.65 brisk": [PS("A", height=1.65, path=((0.4, -0.5, 0),), actions=(A("WALK", place="END", gait="BRISK"),))],
    "1.85 runs a curve": [PS("A", height=1.85, path=((3, -3, 0), (6, -3, 0), (6, 2, 0)),
                             actions=(A("WALK", place="END", gait="RUN"),))],
    "20 points one by one": [PS("A", path=tuple((math.cos(i) * (3 + i * 0.2), math.sin(i) * (3 + i * 0.2), 0)
                                               for i in range(20)), actions=tuple(A("WALK") for _ in range(20)))],
    "acts": [PS("A", path=((0, -2, 0),), carry="crate",
                actions=(A("WALK", place="END"), A("PUT_DOWN"), A("PICK_UP", item="crate"), A("WAVE"),
                         A("POINT", target=(3, -3, 2)), A("LOOK", target=(-2, 0, 1)), A("IDLE", duration=2),
                         A("OPERATE", target=(0.0, -2.5, 1.0)), A("STOP")))],
}


@pytest.mark.parametrize("case", sorted(FEET_CASES))
def test_feet_never_slide_or_sink(case):
    items = [C.ItemSpec("crate", "CRATE", (5, 5, 0))]
    pl = C.plan(FEET_CASES[case], items)
    slide, below, reach, where = _feet_report(pl)
    assert slide < 0.002, f"a standing foot slides {slide * 1000:.1f} mm at {where}"
    assert below < 0.003, f"a sole goes {below * 1000:.1f} mm below the floor"


def test_feet_of_the_example_never_slide_or_sink():
    slide, below, _reach, where = _feet_report(_example(), fps=25.0)
    assert slide < 0.002 and below < 0.003, (slide, below, where)


@pytest.mark.parametrize("gait", sorted(C.GAITS))
def test_swinging_foot_follows_its_arc_and_lands_without_a_snap(gait):
    """While a foot swings the leg must reach the ankle the feet plan wants; else the foot is pulled up towards
    the hip and snaps down onto the floor in the instant it lands."""
    pl = C.plan([PS("A", path=((0.0, -6.0, 0.0),), actions=(A("WALK", place="END", gait=gait),))])
    per = pl.people["A"]
    fig = per.fig
    _slide, _below, reach, _w = _feet_report(pl, fps=50.0)
    snap = 0.0
    for side in ("l", "r"):
        for p in per.feet[side].plants[1:]:
            if not (0.0 < p.down < pl.length):
                continue
            got = []
            for t in (p.down - 0.002, p.down + 0.002):
                root, pose = pl.pose_at("A", t)
                got.append(_world(root, fig.fk(pose)[f"{side}_foot"][0]))
            snap = max(snap, float(np.linalg.norm(got[1] - got[0])))
    assert snap < 0.008, f"the ankle jumps {snap * 1000:.0f} mm in 4 ms as the foot lands"
    assert reach < 0.01, f"the swinging foot misses its planned arc by {reach * 1000:.0f} mm"


@pytest.mark.parametrize("uphill", (True, False))
def test_feet_stay_on_a_gentle_slope(uphill):
    """A ramp of 1 in 10 (the code warns only above 1 in 6): no sole point may go into the ramp."""
    ramp = lambda x, y, z=None: 0.1 * (-y)                      # noqa: E731  rises towards -y
    if uphill:
        sp = PS("A", place=(0, 0, 0), path=((0, -6, 0.6),), actions=(A("WALK", place="END"),))
    else:
        sp = PS("A", place=(0, -6, 0.6), heading=math.pi, path=((0, 0, 0),), actions=(A("WALK", place="END"),))
    pl = C.plan([sp], ground=ramp)
    assert not pl.warnings
    slide, below, _reach, where = _feet_report(pl, ground=ramp)
    assert slide < 0.002, (slide, where)
    assert below < 0.003, f"a sole goes {below * 1000:.1f} mm into a 1:10 ramp (feet are kept level)"


def test_a_steep_or_stepped_ground_is_warned_about():
    steep = lambda x, y, z=None: 0.3 * (-y)                     # noqa: E731
    pl = C.plan([PS("A", path=((0, -4, 1.2),), actions=(A("WALK", place="END"),))], ground=steep)
    assert any("steep" in w for w in pl.warnings), pl.warnings
    step = lambda x, y, z=None: 0.5 if y < -2 else 0.0         # noqa: E731
    pl = C.plan([PS("A", path=((0, -4, 0.5),), actions=(A("WALK", place="END"),))], ground=step)
    assert any("jumps" in w for w in pl.warnings), pl.warnings


def test_a_raised_floor_carries_the_person():
    deck = lambda x, y, z=None: 2.5                            # noqa: E731
    sp = PS("A", place=(0, 0, 2.5), path=((0, -3, 2.5),), actions=(A("WALK", place="END"),))
    pl = C.plan([sp], ground=deck)
    slide, below, _reach, _w = _feet_report(pl, ground=deck)
    assert slide < 0.002 and below < 0.003
    lowest = min(min(v[2] for s in "lr" for v in _soles(pl.people["A"].fig, *pl.pose_at("A", t), s).values())
                 for t in np.linspace(0, pl.length, 30))
    assert lowest == pytest.approx(2.5, abs=0.003), "standing on the deck, not floating above it"


def test_sample_gives_one_frame_per_frame_and_matches_pose_at():
    pl = _example()
    rows = pl.sample(24)
    n = int(math.floor(pl.length * 24 + 1e-6)) + 1
    assert set(rows) == {"Anna", "Ben"} and all(len(r) == n for r in rows.values())
    for f in (0, n // 3, n - 1):
        root, pose = rows["Anna"][f]
        r2, p2 = pl.pose_at("Anna", f / 24)
        assert np.allclose(root, r2)
        assert np.allclose(pose.pelvis, p2.pelvis, atol=0.003)    # the pelvis height is smoothed over frames
    rows = pl.sample(25, t_end=pl.length + 3.0)
    assert len(rows["Ben"]) == int(math.floor((pl.length + 3.0) * 25 + 1e-6)) + 1


def test_plan_is_deterministic_and_does_not_depend_on_the_order_of_people():
    a, b = _example(("Anna", "Ben")), _example(("Ben", "Anna"))
    for name in ("Anna", "Ben"):
        sa = [(s.kind, round(s.t0, 6), round(s.t1, 6)) for s in a.people[name].segs]
        sb = [(s.kind, round(s.t0, 6), round(s.t1, 6)) for s in b.people[name].segs]
        assert sa == sb, name
    assert a.length == pytest.approx(b.length)


# ---------------------------------------------------------------------------
# waits between people
# ---------------------------------------------------------------------------

def test_wait_for_another_persons_step():
    a = PS("A", place=(0, 0, 0), path=((0, -6, 0),), actions=(A("WALK", place="END"), A("WAVE")))
    b = PS("B", place=(4, 0, 0), path=((4, -2, 0),),
           actions=(A("STOP", duration=0.5), A("WALK", place="END", wait_person="A", wait_step=2)))
    for order in ((a, b), (b, a)):
        pl = C.plan(list(order))
        assert not pl.warnings
        a_end = pl.people["A"].step_times[1][1]
        b_walk = next(s for s in pl.people["B"].segs if s.kind == "WALK")
        assert b_walk.t0 >= a_end - 1e-9, "B walks only once A has waved"
        assert b_walk.t0 == pytest.approx(a_end, abs=1e-6), "and not later"
        assert any(s.kind == "WAIT" for s in pl.people["B"].segs)


def test_a_circle_of_waits_warns_and_stays_short():
    a = PS("A", place=(0, 0, 0), path=((0, -3, 0),), actions=(A("WALK", place="END", wait_person="B", wait_step=1),))
    b = PS("B", place=(5, 0, 0), path=((5, -3, 0),), actions=(A("WALK", place="END", wait_person="A", wait_step=1),))
    pl = C.plan([a, b])
    assert any("circle" in w for w in pl.warnings)
    # broken, not pumped up: both walks take ~2.8 s each, so the people's time stays well under a minute
    assert pl.length < 15.0, f"the circle stretched the people's time to {pl.length:.0f} s"


def test_waiting_for_a_step_the_other_does_not_have_warns():
    a = PS("A", actions=(A("STOP", wait_person="B", wait_step=9),))
    b = PS("B", place=(5, 0, 0), actions=(A("IDLE", duration=3),))
    pl = C.plan([a, b])
    assert any("B" in w and "9" in w for w in pl.warnings), pl.warnings


def test_references_to_unknown_people_points_and_items_warn_never_raise():
    it = C.ItemSpec("box", "TOOLBOX", (5, 5, 0))
    acts = (A("WALK"), A("WALK", place="POINT", point=7), A("WALK", place="END"), A("WALK", place="POINT", point=-1),
            A("GREET", other="Nobody"), A("TALK", other="Nobody"), A("TURN", other="Nobody"), A("TURN"),
            A("LOOK"), A("POINT"), A("OPERATE"), A("PICK_UP"), A("PICK_UP", item="ghost"), A("PUT_DOWN"),
            A("STOP", wait_person="Zed", wait_step=1), A("FLY"), A("WALK", gait="SKIP", place="END"))
    pl = C.plan([PS("A", actions=acts, carry="ghost")], [it])
    assert len(pl.warnings) >= 14, pl.warnings
    assert all(isinstance(w, str) and w for w in pl.warnings)
    pl.sample(25)                                                   # and the frames still come out


def test_greeting_or_talking_to_yourself_warns():
    pl = C.plan([PS("A", actions=(A("GREET", other="A"), A("TALK", other="A")))])
    assert len(pl.warnings) >= 2, pl.warnings


def test_empty_scene_and_people_without_actions():
    pl = C.plan([])
    assert pl.length == 0.0 and pl.people == {} and pl.sample(25) == {}
    pl = C.plan([PS("A"), PS("B", place=(2, 0, 0))])
    assert pl.length == 0.0 and not pl.warnings
    rows = pl.sample(25)
    assert len(rows["A"]) == 1 and rows["A"][0][0][:2] == (0.0, 0.0)


def test_start_delay():
    pl = C.plan([PS("A", start=2.0, path=((0, -3, 0),), actions=(A("WALK", place="END"),))])
    w = _walk_seg(pl)
    assert w.t0 == pytest.approx(2.0)
    assert pl.people["A"].root(1.0)[:2] == (0.0, 0.0)


# ---------------------------------------------------------------------------
# greet and talk: both start together
# ---------------------------------------------------------------------------

def _greet_pair(a_from, a_gait, b_from, b_gait, ha=1.75, hb=1.75):
    a = PS("A", height=ha, place=a_from, path=((0, 0.4, 0),),
           actions=(A("WALK", place="END", gait=a_gait), A("GREET", other="B"), A("TALK", other="B", duration=4)))
    b = PS("B", height=hb, place=b_from, path=((0, -0.4, 0),),
           actions=(A("WALK", place="END", gait=b_gait), A("GREET", other="A"), A("TALK", other="A", duration=4)))
    return a, b


@pytest.mark.parametrize("setup", [
    ((0, 10, 0), "RUN", (-20, -0.4, 0), "STROLL"),
    ((0, 30, 0), "STROLL", (0.5, -1.4, 0), "RUN"),
    ((0, 1.0, 0), "WALK", (0, -1.0, 0), "WALK"),
])
def test_greet_and_talk_start_together_whatever_the_walks(setup):
    for order in (0, 1):
        a, b = _greet_pair(*setup)
        pl = C.plan([a, b] if order == 0 else [b, a])
        assert not pl.warnings, pl.warnings
        hs = {n: next(s for s in pl.people[n].segs if s.kind == "HANDSHAKE") for n in ("A", "B")}
        assert hs["A"].t0 == pytest.approx(hs["B"].t0, abs=1e-6) and hs["A"].t1 == pytest.approx(hs["B"].t1, abs=1e-6)
        walks = {n: _walk_seg(pl, n) for n in ("A", "B")}
        assert hs["A"].t0 >= max(w.t1 for w in walks.values()) - 1e-9, "nobody shakes hands while still walking"
        tk = {n: next(s for s in pl.people[n].segs if s.kind == "TALK") for n in ("A", "B")}
        assert tk["A"].t0 == pytest.approx(tk["B"].t0, abs=1e-6)
        assert tk["A"].data["first"] != tk["B"].data["first"], "they take turns: one speaks first"
        # at the handshake they face each other
        for n, o in (("A", "B"), ("B", "A")):
            r, ro = pl.people[n].root(hs[n].t0 + 1.0), pl.people[o].root(hs[n].t0 + 1.0)
            want = C.heading_of((ro[0] - r[0], ro[1] - r[1]))
            assert abs(C.wrap(r[3] - want)) < math.radians(5), f"{n} faces {o}"


@pytest.mark.parametrize("heights", ((1.75, 1.75), (1.65, 1.85)))
def test_handshake_hands_meet(heights):
    """'Both reach, hands meet': the two right hands hold the same point while they shake."""
    a, b = _greet_pair((0, 3, 0), "WALK", (0, -3, 0), "WALK", *heights)
    pl = C.plan([a, b])
    hs = next(s for s in pl.people["A"].segs if s.kind == "HANDSHAKE")
    worst = 0.0
    for t in np.linspace(hs.t0 + 0.7, hs.t1 - 0.7, 9):
        worst = max(worst, float(np.linalg.norm(_grip_point_world(pl, "A", t) - _grip_point_world(pl, "B", t))))
    assert worst < 0.03, f"the hands are {worst * 1000:.0f} mm apart while shaking (heights {heights})"


def test_greet_without_an_answer_is_a_wave():
    a = PS("A", place=(0, 0, 0), actions=(A("GREET", other="B"),))
    b = PS("B", place=(0.8, 0, 0), actions=(A("IDLE"),))
    pl = C.plan([a, b])
    kinds = [s.kind for s in pl.people["A"].segs]
    assert "WAVE" in kinds and "HANDSHAKE" not in kinds
    assert not any(s.kind == "WAIT" for s in pl.people["A"].segs), "nobody waits for a greeting that never comes"
    # a greeting back to somebody else does not count either
    b = PS("B", place=(0.8, 0, 0), actions=(A("GREET", other="C"),))
    c = PS("C", place=(-2, 0, 0), actions=(A("GREET", other="B"),))
    pl = C.plan([a, b, c])
    assert "HANDSHAKE" not in [s.kind for s in pl.people["A"].segs]
    assert "HANDSHAKE" in [s.kind for s in pl.people["B"].segs]


def test_two_greetings_pair_in_order():
    a = PS("A", place=(0, 0.4, 0), heading=math.pi,
           actions=(A("GREET", other="B"), A("STOP", duration=3), A("GREET", other="B")))
    b = PS("B", place=(0, -0.4, 0),
           actions=(A("IDLE", duration=6), A("GREET", other="A"), A("GREET", other="A")))
    pl = C.plan([a, b])
    ha = [s.t0 for s in pl.people["A"].segs if s.kind == "HANDSHAKE"]
    hb = [s.t0 for s in pl.people["B"].segs if s.kind == "HANDSHAKE"]
    assert len(ha) == len(hb) == 2 and np.allclose(ha, hb, atol=1e-6), (ha, hb)


def test_example_order_and_meeting():
    pl = _example()
    order = [s.kind for s in pl.people["Anna"].segs if s.kind in ("WALK", "PUT_DOWN", "HANDSHAKE", "TALK")]
    assert order == ["WALK", "PUT_DOWN", "HANDSHAKE", "TALK"]
    ha = next(s for s in pl.people["Anna"].segs if s.kind == "HANDSHAKE")
    hb = next(s for s in pl.people["Ben"].segs if s.kind == "HANDSHAKE")
    assert ha.t0 == pytest.approx(hb.t0, abs=1e-6)
    ra, rb = pl.people["Anna"].root(ha.t0), pl.people["Ben"].root(ha.t0)
    assert 0.55 <= math.hypot(ra[0] - rb[0], ra[1] - rb[1]) <= 1.25
    assert not pl.warnings


# ---------------------------------------------------------------------------
# carried items
# ---------------------------------------------------------------------------

def test_pick_up_too_far_and_put_down_nothing_warn():
    it = C.ItemSpec("box", "TOOLBOX", (5, 5, 0))
    pl = C.plan([PS("A", actions=(A("PICK_UP", item="box"),))], [it])
    assert any("too far" in w for w in pl.warnings)
    pl = C.plan([PS("A", actions=(A("PUT_DOWN"),))], [it])
    assert any("nothing" in w for w in pl.warnings)
    assert [s.state for s in pl.item_states["box"]] == ["PLACED"], "the box stays where it lies"


@pytest.mark.parametrize("kind", sorted(C.ITEMS))
def test_put_down_lies_on_the_ground_in_front_of_the_person(kind):
    for floor in (0.0, 1.3):
        g = lambda x, y, z=None, f=floor: f                     # noqa: E731
        it = C.ItemSpec("it", kind, (9, 9, floor))
        sp = PS("A", place=(0, 0, floor), path=((2, -2, floor),), carry="it",
                actions=(A("WALK", place="END"), A("PUT_DOWN"), A("STOP")))
        pl = C.plan([sp], [it], ground=g)
        assert not pl.warnings
        last = pl.item_states["it"][-1]
        assert last.state == "PLACED"
        M = last.world
        assert M[2, 3] == pytest.approx(floor, abs=1e-9), "the item's base on the floor"
        assert np.allclose(M[:3, 2], (0, 0, 1)), "standing upright"
        r = pl.people["A"].root(pl.length)
        d = M[:2, 3] - np.array(r[:2])
        ahead = float(np.dot(d, C.facing(r[3])))
        assert 0.25 < ahead < 0.9, f"{ahead:.2f} m in front"
        assert abs(float(np.dot(d, C.left_of(r[3])))) < 0.3
        # the item does not lie under the person's feet
        L, W, _H = C.ITEMS[kind].size
        for side in ("l", "r"):
            q = C.inv4(M) @ np.r_[pl.people["A"].feet[side].last.pos[:2], floor, 1.0]
            assert abs(q[0]) > L / 2 + 0.05 or abs(q[1]) > W / 2 + 0.05, f"{kind} lies on the {side} foot"


@pytest.mark.parametrize("kind", sorted(C.ITEMS))
def test_item_does_not_jump_when_picked_up_or_put_down(kind):
    """At the moment of the grab the hand is on the item: it neither jumps into the hand nor out of it."""
    it = C.ItemSpec("it", kind, (0.0, -0.6, 0.0), 0.0)
    sp = PS("A", place=(0, 0, 0), path=((0, -0.2, 0), (3, -3, 0)),
            actions=(A("PICK_UP", item="it"), A("WALK", place="END"), A("PUT_DOWN"), A("STOP")))
    pl = C.plan([sp], [it])
    assert not pl.warnings, pl.warnings
    states = pl.item_states["it"]
    assert [s.state for s in states] == ["PLACED", "HELD", "PLACED"]
    for prev, nxt in zip(states, states[1:]):
        t = nxt.t
        before = _item_world_in_hand(pl, prev, t - 1e-6) if prev.state == "HELD" else prev.world
        after = _item_world_in_hand(pl, nxt, t + 1e-6) if nxt.state == "HELD" else nxt.world
        jump = float(np.linalg.norm(before[:3, 3] - after[:3, 3]))
        turn = math.degrees(R.angle_between(before[:3, :3], after[:3, :3]))
        assert jump < 0.03 and turn < 10, \
            f"{kind}: {prev.state} -> {nxt.state} at {t:.2f} s jumps {jump * 1000:.0f} mm, {turn:.0f}°"


def test_example_toolbox_is_released_where_the_hand_puts_it():
    pl = _example()
    states = pl.item_states["box"]
    held = next(s for s in states if s.state == "HELD")
    placed = states[-1]
    assert placed.state == "PLACED" and placed.t > 1.0
    before = _item_world_in_hand(pl, held, placed.t - 1e-6)
    jump = float(np.linalg.norm(before[:3, 3] - placed.world[:3, 3]))
    assert jump < 0.03, f"the toolbox jumps {jump * 1000:.0f} mm from Anna's hand to the floor"


def test_item_handed_on_from_one_person_to_another():
    it = C.ItemSpec("box", "TOOLBOX", (9, 9, 0))
    a = PS("A", place=(0, 0, 0), path=((0, -2, 0), (0, -5, 0)), carry="box",
           actions=(A("WALK", place="POINT", point=1), A("PUT_DOWN"), A("WALK", place="END")))
    b = PS("B", place=(0.25, -2.75, 0), heading=math.radians(180),
           actions=(A("PICK_UP", item="box", wait_person="A", wait_step=2), A("STOP")))
    for order in ((a, b), (b, a)):
        pl = C.plan(list(order), [it])
        states = pl.item_states["box"]
        seq = [(s.state, s.person) for s in states]
        assert seq[-3:] == [("HELD", "A"), ("PLACED", ""), ("HELD", "B")], seq
        put = next(s for s in pl.people["A"].segs if s.kind == "PUT_DOWN")
        pick = next(s for s in pl.people["B"].segs if s.kind == "PICK_UP")
        assert pick.t0 >= put.t1 - 1e-9
        assert np.allclose(pick.data["world"], states[-2].world), "B picks it up where A put it"
        assert pl.people["B"].holding(pl.length) == "box" and pl.people["A"].holding(pl.length) == ""


def test_picking_up_what_someone_else_holds_is_refused():
    it = C.ItemSpec("box", "TOOLBOX", (0.3, -0.6, 0))
    a = PS("A", place=(5, 0, 0), path=((5, -6, 0),), carry="box", actions=(A("WALK", place="END"), A("PUT_DOWN")))
    b = PS("B", place=(0, 0, 0), actions=(A("PICK_UP", item="box"),))
    pl = C.plan([a, b], [it])
    holders = [s.person for s in pl.item_states["box"] if s.state == "HELD"]
    assert holders == ["A"] and pl.warnings, (holders, pl.warnings)


def test_two_people_cannot_both_hold_one_item_at_the_start():
    it = C.ItemSpec("box", "TOOLBOX", (9, 9, 0))
    a = PS("A", carry="box", actions=(A("STOP"),))
    b = PS("B", place=(3, 0, 0), carry="box", actions=(A("STOP"),))
    pl = C.plan([a, b], [it])
    holders = [s.person for s in pl.item_states["box"] if s.state == "HELD"]
    assert len(holders) == 1 and pl.warnings, (holders, pl.warnings)


def test_carry_gait_with_heavy_items():
    for kind, want in (("CRATE", "CARRY"), ("CABLE_DRUM", "CARRY"), ("TOOLBOX", "WALK"), ("CLIPBOARD", "WALK")):
        it = C.ItemSpec("it", kind, (9, 9, 0))
        pl = C.plan([PS("A", path=((0, -4, 0),), carry="it", actions=(A("WALK", place="END", gait="WALK"),))], [it])
        assert _walk_seg(pl).data["gait"] == want, kind
    it = C.ItemSpec("it", "CRATE", (9, 9, 0))
    pl = C.plan([PS("A", path=((0, -4, 0),), carry="it", actions=(A("WALK", place="END", gait="RUN"),))], [it])
    assert _walk_seg(pl).data["gait"] == "RUN", "a gait the owner picked on purpose stays"


def test_carried_toolbox_hangs_clear_of_the_leg():
    """The toolbox is carried at the side: its body must not pass through the thigh or the shin."""
    for height in (1.65, 1.85):
        it = C.ItemSpec("it", "TOOLBOX", (9, 9, 0))
        sp = PS("A", height=height, path=((0, -6, 0),), carry="it", actions=(A("WALK", place="END", gait="WALK"),))
        pl = C.plan([sp], [it])
        per, st = pl.people["A"], pl.item_states["it"][-1]
        fig = per.fig
        L, W, H = C.ITEMS["TOOLBOX"].size
        body_h = H - 0.06                                     # the box without its handle
        worst = 0.0
        for t in np.linspace(0.3, pl.length - 0.3, 40):
            _root, pose = pl.pose_at("A", t)
            fk = fig.fk(pose)
            inv = C.inv4(C.m4(fk["r_hand"][1], fk["r_hand"][0]) @ st.grip)
            for bone, rad in (("r_thigh", 0.065), ("r_shin", 0.045), ("l_thigh", 0.065), ("l_shin", 0.045)):
                h0, _Rb, t1 = fk[bone]
                for u in np.linspace(0, 1, 11):
                    q = (inv @ np.r_[h0 + (t1 - h0) * u, 1.0])[:3]
                    r = rad * fig.k
                    depth = min(L / 2 + r - abs(q[0]), W / 2 + r - abs(q[1]), q[2] + r, body_h + r - q[2])
                    worst = max(worst, depth)
        assert worst < 0.01, f"the toolbox goes {worst * 1000:.0f} mm into the leg ({height} m)"


def test_operate_too_far_warns():
    pl = C.plan([PS("A", actions=(A("OPERATE", target=(0, -3, 1)),))])
    assert any("too far" in w for w in pl.warnings)
    pl = C.plan([PS("A", actions=(A("OPERATE", target=(0, -0.5, 1.0)),))])
    assert not pl.warnings


# ---------------------------------------------------------------------------
# the rig: kinematics, Blender numbers, weights
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("height", (1.65, 1.75, 1.85))
def test_rest_pose_stands_on_the_floor_at_its_height(height):
    fig = R.Figure(height)
    pose = fig.rest()
    for side in ("l", "r"):
        sp = fig.sole_points(pose, side)
        assert sp["heel"][2] == pytest.approx(0.0, abs=0.004) and sp["toe"][2] == pytest.approx(0.0, abs=0.004)
    shapes = P.person(height, "STANDING", helmet=False, lod=P.DETAILED)
    zs = np.array([p[2] for sh in shapes if isinstance(sh, S.Loft) for r in sh.rings for p in r])
    assert zs.min() == pytest.approx(0.0, abs=1e-9)
    assert zs.max() == pytest.approx(height, abs=0.02)
    assert np.allclose(fig.from_angles("STANDING").pelvis, pose.pelvis)


@pytest.mark.parametrize("height", (1.65, 1.85))
def test_blender_quaternion_of_the_rest_pose_is_identity(height):
    fig = R.Figure(height)
    for pose in (fig.rest(), fig.from_angles("STANDING")):
        for b in R.BONES:
            assert np.allclose(fig.blender_quaternion(pose, b), (1, 0, 0, 0), atol=1e-9), b
        assert np.allclose(fig.blender_location(pose), (0, 0, 0), atol=1e-9)
    for b in R.BONES:                                         # the rest bone frames are proper rotations
        _h, B, ln = fig.rest_matrix(b)
        assert np.allclose(B.T @ B, np.eye(3), atol=1e-9) and np.linalg.det(B) == pytest.approx(1.0)
        assert ln > 0


def _blender_chain(fig, pose):
    """What Blender makes of the quaternions and the pelvis location: each pose bone's (head, frame) in armature
    space, walked the way Blender walks a bone chain (parent pose @ rest offset @ basis)."""
    rest = {b: fig.rest_matrix(b) for b in R.BONES}
    out = {}
    for b in R.BONES:
        h, B, _ln = rest[b]
        Q = R.matrix(fig.blender_quaternion(pose, b))
        par = R.PARENT[b]
        if par is None:
            loc = np.asarray(fig.blender_location(pose))
            out[b] = (h + B @ loc, B @ Q)
        else:
            ph, PB, _l = rest[par]
            qh, QB = out[par]
            rel_R = PB.T @ B
            rel_t = PB.T @ (h - ph)
            out[b] = (qh + QB @ rel_t, QB @ rel_R @ Q)
    return out


@pytest.mark.parametrize("pose_id", sorted(P.POSES))
def test_blender_bones_follow_the_pose(pose_id):
    fig = R.Figure(1.75)
    pose = fig.from_angles(pose_id)
    fig.arm_ik(pose, "l", fig.shoulder(pose, "l") + np.array((0.1, -0.3, -0.25)), hand_R=R.rx(-0.6))
    fig.leg_ik(pose, "r", fig.hip(pose, "r") + np.array((-0.05, -0.25, -0.7)), foot_R=R.rz(0.3))
    fig.look(pose, (1.0, -1.0, 0.3))
    pose.pelvis = pose.pelvis + np.array((0.03, -0.02, -0.06))
    fk, bl = fig.fk(pose), _blender_chain(fig, pose)
    for b in R.BONES:
        assert np.allclose(bl[b][0], fk[b][0], atol=1e-9), b
        assert np.allclose(bl[b][1], fk[b][1] @ R.C[b], atol=1e-9), b


def test_leg_and_arm_ik_reach_or_say_how_far_they_miss():
    fig = R.Figure(1.75)
    pose = fig.rest()
    hip = fig.hip(pose, "l")
    for off in ((0.05, -0.2, -0.6), (0.0, 0.1, -0.5), (0.1, -0.4, -0.3)):
        tgt = hip + np.array(off)
        foot_R = R.rz(0.2) @ R.rx(0.3)
        assert fig.leg_ik(pose, "l", tgt, foot_R) == pytest.approx(0.0, abs=1e-9)
        fk = fig.fk(pose)
        assert np.allclose(fk["l_foot"][0], tgt, atol=1e-9) and np.allclose(fk["l_foot"][1], foot_R, atol=1e-9)
    far = hip + np.array((0.0, 0.0, -1.2))
    miss = fig.leg_ik(pose, "l", far)
    assert miss == pytest.approx(np.linalg.norm(fig.fk(pose)["l_foot"][0] - far), abs=1e-6) and miss > 0.3
    sh = fig.shoulder(pose, "r")
    for off in ((-0.1, -0.3, -0.2), (0.1, -0.35, 0.1), (-0.2, 0.1, -0.4)):
        tgt = sh + np.array(off)
        hand_R = R.rx(-1.0) @ R.rz(0.4)
        assert fig.arm_ik(pose, "r", tgt, hand_R=hand_R) == pytest.approx(0.0, abs=1e-9)
        fk = fig.fk(pose)
        assert np.allclose(fk["r_hand"][0], tgt, atol=1e-9)
        assert R.angle_between(fk["r_hand"][1], hand_R) < 1e-6
    # elbows and knees stay their own bone lengths
    fk = fig.fk(pose)
    for b in ("l_thigh", "l_shin", "r_arm", "r_forearm"):
        h, _Rb, t = fk[b]
        assert np.linalg.norm(t - h) == pytest.approx(np.linalg.norm(R.VEC[b]) * fig.k)


def test_look_turns_the_face_towards_the_target_and_amount_zero_does_nothing():
    fig = R.Figure(1.75)
    pose = fig.rest()
    before = {b: np.array(m) for b, m in pose.local.items()}
    fig.look(pose, (1.0, -1.0, 0.0), amount=0.0)
    assert all(np.allclose(pose.local[b], before[b]) for b in R.BONES)
    face0 = -fig.fk(pose)["head"][1][:, 1]                    # the head's front (-y of its frame)
    fig.look(pose, (1.0, -1.0, 0.0))
    face1 = -fig.fk(pose)["head"][1][:, 1]
    want = R.unit(np.array((1.0, -1.0, 0.0)))
    assert float(np.dot(face1, want)) > float(np.dot(face0, want)) + 0.2
    assert float(np.dot(face1, want)) > 0.95


def test_quaternion_round_trip():
    rng = np.random.default_rng(7)
    for _ in range(200):
        a, b, c = rng.uniform(-math.pi, math.pi, 3)
        M = R.rz(a) @ R.rx(b) @ R.ry(c)
        q = R.quat(M)
        assert q[0] >= 0 and abs(np.linalg.norm(q) - 1) < 1e-12
        assert np.allclose(R.matrix(q), M, atol=1e-9)
    assert np.allclose(R.slerp(R.rz(0.0), R.rz(1.0), 0.5), R.rz(0.5), atol=1e-9)


def _rest_mesh(height):
    shapes = P.person(height, "STANDING", lod=P.DETAILED)
    pts, anchors, groups = [], [], []
    for g, sh in enumerate(shapes):
        if not isinstance(sh, S.Loft):
            continue
        rings = np.asarray(sh.rings, float)
        pts.append(rings.reshape(-1, 3))
        anchors.append(np.repeat(rings.mean(axis=1), rings.shape[1], axis=0))
        groups += [g] * (rings.shape[0] * rings.shape[1])
    return np.concatenate(pts), np.concatenate(anchors), np.asarray(groups)


@pytest.mark.parametrize("height", (1.65, 1.85))
def test_bind_weights(height):
    fig = R.Figure(height)
    pts, anchors, groups = _rest_mesh(height)
    W = R.bind(fig, anchors, groups)
    assert W.shape == (len(pts), len(R.BONES))
    assert np.allclose(W.sum(axis=1), 1.0) and W.min() >= -1e-12
    dist, _along = R._segment_params(fig, anchors)
    best = W.argmax(axis=1)
    d_best = dist[np.arange(len(anchors)), best]
    assert d_best.max() < 0.2 * fig.k, f"a ring is weighted mostly to a bone {d_best.max():.2f} m away"
    # each point shares at most two neighbours on one chain
    assert (np.count_nonzero(W > 1e-9, axis=1) <= 3).all()
    # hands, feet and head go with their own bone
    for b in ("l_hand", "r_hand", "head", "l_foot", "r_foot"):
        j = R.BONES.index(b)
        others = np.delete(dist, j, axis=1).min(axis=1)
        close = (dist[:, j] < 0.05 * fig.k) & (dist[:, j] + 0.03 * fig.k < others)    # clearly this bone's own
        assert close.sum() >= 3, b
        assert (W[close, j] > 0.45).mean() > 0.9, b
    assert R.bind(fig, np.zeros((0, 3))).shape == (0, len(R.BONES))


@pytest.mark.parametrize("height", (1.65, 1.85))
def test_skin_rest_is_unchanged_and_a_pose_moves_the_right_parts(height):
    fig = R.Figure(height)
    pts, anchors, groups = _rest_mesh(height)
    W = R.bind(fig, anchors, groups)
    assert np.allclose(R.skin(fig, pts, W, fig.rest()), pts, atol=1e-12)
    # moving only the whole figure: every point moves the same
    pose = fig.rest()
    pose.pelvis = pose.pelvis + np.array((0.2, -0.1, 0.05))
    assert np.allclose(R.skin(fig, pts, W, pose) - pts, (0.2, -0.1, 0.05), atol=1e-12)
    # raising the right arm moves the right hand's points with the hand and leaves the left leg alone
    pose = fig.rest()
    fig.arm_ik(pose, "r", fig.shoulder(pose, "r") + np.array((-0.1, -0.5, 0.1)))
    out = R.skin(fig, pts, W, pose)
    jh, jl = R.BONES.index("r_hand"), R.BONES.index("l_shin")
    hand = W[:, jh] > 0.999
    leg = W[:, jl] > 0.999
    assert hand.any() and leg.any()
    assert np.allclose(out[leg], pts[leg], atol=1e-12)
    h0, R0, _t = fig.rest_fk["r_hand"]
    h1, R1, _t = fig.fk(pose)["r_hand"]
    want = (pts[hand] - h0) @ (R1 @ R0.T).T + h1
    assert np.allclose(out[hand], want, atol=1e-9)
    assert np.linalg.norm(out[hand] - pts[hand], axis=1).min() > 0.2
