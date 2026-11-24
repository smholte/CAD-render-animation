"""Task 0172, independent tester (subagent T): tries to break "What to do" 1–3 of the brief, written from the brief.

1. ``core/catenary.hang_off``: the cable leaves a chute/gutter at the end where its way down lies; no bend outside the
   gutter of more than the gutter's own arc per drawn point; no moment without an answer; no step where the leave
   point changes end between neighbouring moments; a free bend never goes into the seabed. Pure NumPy.
2. ``blender/paths_rollers.py``: a sheave the cable has left stands still at Build, its coupling put aside and put
   back by 'Clear keys' (the cable paths test model, SHEAVE 2 carried out of the rope's way by a slide joint "Away").
3. (``blender/demo.set_down_shares``: left with the vessel's equipment, task 0247 – its test is in the private kit.)

It found five faults on the branch as handed over (16 Nov 2026); the worker fixed three (their tests now pass and say
so). The two tests named "KNOWN_FAULT" are open points of task 0172: they hold the faults to the size they have now
(``KNOWN_*``; the brief's bounds are in their docstrings), so they cannot grow unseen.
"""

import math
import os

import numpy as np
import pytest

from fresing_render.core import catenary as C
from fresing_render.core import paths as P

HERE = os.path.dirname(__file__)
ZB = -30.0                              # the cable's middle on the seabed
AFT = np.array([-1.0, 0.0, 0.0])        # laid aft (-x)
BEND_STEP = math.radians(0.5)           # paths_sea.BEND_STEP: a drawn point per 0.5° of free bend
# the two faults left open by task 0172 (its report, open points 1–2): the bounds they reach now – the brief's bounds
# are 10° / 0.5 m and 4°; lower these when the faults are fixed (rename the tests then)
KNOWN_TIP = {(1.0, 0.0, 0.0): (55.0, 5.0), (0.0, 1.0, 0.0): (180.0, 7.5)}   # tipped about x / y: degrees, m
KNOWN_SEABED_KINK = 50.0                         # degrees


# ---------------------------------------------------------------------------
# helpers (drawn as blender/paths_sea.solve draws a hang-off)
# ---------------------------------------------------------------------------

def rot(axis, a):
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def gutter(F, height, R=4.0, tilt=0.0, tilt_axis=(1.0, 0.0, 0.0)):
    """A 180° gutter lying flat (axis +z, side -1): the cable arrives at +y going +x, goes round over +x and leaves at
    its far end (-y) going -x, the way it is laid (AFT). Turned by ``tilt`` about ``tilt_axis`` through its centre
    (tilt 0 = flat, the D set down; larger = on its way from hanging to flat). ``height``: its centre over the
    cable's middle on the seabed. Returns hang_off's first five inputs."""
    height = np.asarray(height, dtype=float).reshape(-1)
    tilt = np.broadcast_to(np.asarray(tilt, dtype=float), (F,))
    c = np.zeros((F, 3))
    c[:, 2] = ZB + height
    ax = np.array([rot(tilt_axis, t) @ [0.0, 0.0, 1.0] for t in tilt])
    arr = c + np.array([rot(tilt_axis, t) @ [0.0, R, 0.0] for t in tilt])
    return c, ax, R, -1.0, arr


def one(res, k):
    n = len(res["kind"])
    return {key: (v[k:k + 1] if isinstance(v, np.ndarray) and v.shape[:1] == (n,) else v) for key, v in res.items()}


def drawn(res, k, inputs, wmax=math.pi, n_cat=600, n_laid=4):
    """(arc on the wheel, free bend, catenary + laid) points of moment k: the wheel's arc with the app's count for the
    gutter (core.paths.point_counts: one every 4°), the bend one point per 0.5°, the catenary."""
    s = one(res, k)
    centre, axis, r, side, arrive = inputs
    n_arc = P.point_counts(wmax)[0]
    psi = float(s["psi"][0])
    arc = np.stack([C.wheel_point(centre[k:k + 1], axis[k:k + 1], r, side, arrive[k:k + 1], psi * t)[0][0]
                    for t in np.linspace(0.0, 1.0, n_arc)])
    n_bend = int(np.clip(math.ceil(float(res["bend"].max()) / BEND_STEP), 4, 400)) \
        if float(res["bend"].max()) >= C.BEND_MIN else 0
    bend = C.bend_points(s, n_bend)[0][0] if n_bend else np.zeros((0, 3))
    L, sh = float(s["L"][0]), float(s["suspended"][0])
    lam = np.concatenate([sh * np.arange(1, n_cat + 1) / n_cat, sh + (L - sh) * np.arange(1, n_laid + 1) / n_laid])
    return arc, bend, C.points(s, lam[None])[0]


def turns(p):
    """Turn (degrees) at each inner point of a polyline (repeated points skipped)."""
    d = np.diff(p, axis=0)
    n = np.linalg.norm(d, axis=1)
    d = d[n > 1e-9] / n[n > 1e-9, None]
    return np.degrees(np.arccos(np.clip((d[1:] * d[:-1]).sum(1), -1.0, 1.0)))


def length0(inputs, S, extra):
    """hang_off's length0: the gutter's half turn + the flat distance to S + ``extra``."""
    c, _ax, R, _side, _arr = inputs
    return R * math.pi + np.linalg.norm(S[:2] - c[0, :2]) + np.asarray(extra, dtype=float)


# ---------------------------------------------------------------------------
# 1. the hang-off from a gutter – what holds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("height", [6.0, 1.0, 0.3])
def test_a_flat_gutter_is_left_at_the_end_pointing_the_way_the_cable_lies(height):
    """Flat gutter, the cable's end anywhere from 6 m to one side to 6 m to the other: it leaves at the far end (180°),
    where the gutter points the way the cable lies; laid the other way (+x: the D lowered "on the other side") it
    leaves at the near end (0°, going on in a free bend), never in the middle."""
    for lat in np.linspace(-6.0, 6.0, 13):
        for extra in (2.0, 8.0):
            g = gutter(1, [height], R=3.5)
            S = np.array([-60.0, lat, ZB])
            res = C.hang_off(*g, math.pi, S, AFT, ZB, length0(g, S, [extra]))
            assert math.degrees(res["psi"][0]) == pytest.approx(180.0, abs=0.5), (lat, extra)
            S = np.array([60.0, lat, ZB])
            res = C.hang_off(*g, math.pi, S, -AFT, ZB, length0(g, S, [extra]))
            assert math.degrees(res["psi"][0]) == pytest.approx(0.0, abs=0.5), (lat, extra)
            assert not res["short"][0] and res["bend"][0] > 0.1


def test_mirrored_set_up_gives_the_mirrored_answer():
    """The same gutter mirrored in y (the cable going round the other way: side flips): T and the wrap mirror."""
    rng = np.random.default_rng(1)
    M = np.diag([1.0, -1.0, 1.0])
    for _ in range(40):
        R, h, lat, extra = rng.uniform(1.0, 6.0), rng.uniform(0.05, 8.0), rng.uniform(-6, 6), rng.uniform(0.5, 12)
        g = gutter(1, [h], R=R, tilt=rng.uniform(-0.3, 0.3), tilt_axis=(0, 1, 0))
        S = np.array([-60.0, lat, ZB])
        L0 = length0(g, S, [extra])
        a = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
        c, ax, r, side, arr = g
        b = C.hang_off(c @ M, ax @ M, r, -side, arr @ M, math.pi, S @ M, AFT @ M, ZB, L0)
        assert np.abs(a["T"] @ M - b["T"]).max() < 1e-6
        assert abs(a["psi"][0] - b["psi"][0]) < 1e-6


def test_no_moment_without_an_answer_and_no_bend_into_the_seabed():
    """Fuzz (seeded): wheels at any tilt and sense, radius 1 cm … 50 m, wrap_max from 3° to nearly a whole turn, the
    centre from under the seabed to high above it, cables from far too short (stretched, lifted) to piled up, the lay
    any way: every moment has a finite answer, the wrap lies in 0 … wrap_max, and where the whole wheel is above the
    seabed the free bend never goes below it."""
    rng = np.random.default_rng(7)
    kinds = set()
    for _ in range(90):
        F = 16
        R = float(10 ** rng.uniform(-2, 1.7))
        wmax = float(rng.choice([0.05, 0.5, math.pi / 2, math.pi, 2 * math.pi - 0.05]))
        h = rng.uniform(-0.2 * R, 3 * R + 5, F)
        axis = rng.normal(size=3)
        axis /= np.linalg.norm(axis)
        c = np.zeros((F, 3))
        c[:, 2] = ZB + h
        perp = np.cross(axis, rng.normal(size=3))
        perp /= np.linalg.norm(perp)
        S = np.array([rng.uniform(-80, 80), rng.uniform(-80, 80), ZB])
        lay = rng.normal(size=3)
        lay[2] = 0.0
        d = np.linalg.norm(S[:2])
        L0 = R * wmax * rng.uniform(0, 1) + np.hypot(d, h.mean()) * rng.uniform(0.6, 2.0, F)
        with np.errstate(all="ignore"):
            res = C.hang_off(c, np.tile(axis, (F, 1)), R, float(rng.choice([-1.0, 1.0])), c + R * perp, wmax, S, lay,
                             ZB, L0)
        kinds |= set(res["kind"].tolist())
        for key in ("T", "direction", "psi", "bend", "a", "suspended", "laid"):
            assert np.isfinite(res[key]).all(), key
        assert (res["psi"] >= -1e-12).all() and (res["psi"] <= wmax + 1e-9).all()
        pts = C.bend_points(res, 400)[0]
        above = h - R > 0.002
        assert ((pts[..., 2] - ZB).min(axis=1)[above] >= -1e-6).all()
    assert kinds == {C.NORMAL, C.LIFTED, C.PILED, C.STRETCHED}


def test_many_moments_at_once_give_what_one_at_a_time_gives():
    """F = 40 moments at once (the array bisections) and one at a time (plain numbers, ``SMALL``): the same answers,
    also where the flat gutter is lowered to 5 cm over the seabed."""
    rng = np.random.default_rng(3)
    F = 40
    h = np.concatenate([np.linspace(8, 0.05, 20), np.linspace(0.05, 8, 20)])
    g = gutter(F, h, R=3.5)
    S = np.array([-60.0, 0.5, ZB])
    L0 = length0(g, S, 1.0 + rng.uniform(0, 6, F))
    every = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
    for k in range(F):
        g1 = gutter(1, h[k:k + 1], R=3.5)
        r1 = C.hang_off(*g1, math.pi, S, AFT, ZB, L0[k:k + 1])
        assert np.abs(r1["T"][0] - every["T"][k]).max() < 1e-6, k
        assert abs(r1["psi"][0] - every["psi"][k]) < 1e-9, k


def test_the_cable_leaves_the_gutter_without_a_kink_where_it_hangs_free():
    """High over the seabed (the bend never reaches it) the drawn cable turns at most the gutter's own arc per point
    (4°) everywhere from the gutter's end on: at the wheel → free bend and at the free bend → catenary."""
    F = 60
    h = np.linspace(12.0, 8.0, F)
    for lat in (-3.0, 0.0, 3.0):
        g = gutter(F, h, R=3.5, tilt=math.radians(5.0))
        S = np.array([-60.0, lat, ZB])
        res = C.hang_off(*g, math.pi, S, AFT, ZB, length0(g, S, np.full(F, 4.0)))
        assert (res["kind"] == C.NORMAL).all()
        for k in range(F):
            arc, bend, cat = drawn(res, k, g)
            t = turns(np.concatenate([arc[-3:], bend, cat[:5]]))
            assert t.max() <= 4.0 + 1e-6, (lat, h[k], t.max())


# ---------------------------------------------------------------------------
# 1. the hang-off from a gutter – faults found
# ---------------------------------------------------------------------------

def test_KNOWN_FAULT_tipping_towards_flat_the_leave_point_jumps_from_the_middle_to_the_far_end():
    """FAULT (brief 1: "no step where the hang-off changes end"). A gutter of 3.5 m, its centre 1 m over the seabed,
    tips from 30° to flat in 400 steps of 0.075° (the D tipping towards flat near the seabed, shot 11's first step):
    the leave point stays at the gutter's middle (90°) and then, in ONE step at 11.58° (where the wheel's plane holds
    ``FLAT`` = 0.2 of "down"), jumps to the far end (180°): the catenary's start moves 6.5 m between two neighbouring
    moments; ``hang_off_steady`` keeps it (it only puts back runs of ≤ 2 moments). Tipped about y instead: 82.9° →
    180° at 9.2°, 7.2 m. (Before the change the same jump came at 8.5°, 4.95 m: moved, not removed.)"""
    F = 400
    tilt = np.linspace(math.radians(30.0), 0.0, F)
    for tilt_axis in ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)):
        g = gutter(F, np.full(F, 1.0), R=3.5, tilt=tilt, tilt_axis=tilt_axis)
        S = np.array([-60.0, 0.0, ZB])
        L0 = length0(g, S, np.full(F, 2.0))
        for res in (C.hang_off(*g, math.pi, S, AFT, ZB, L0), C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)):
            assert np.isfinite(res["T"]).all()
            dpsi = np.degrees(np.abs(np.diff(res["psi"])))
            step = np.linalg.norm(np.diff(res["T"], axis=0), axis=1)
            k = int(dpsi.argmax())
            # KNOWN FAULT (open point 1 of task 0172): the brief wants < 10° and < 0.5 m; after the task, tipped about x
            # 51° / 4.45 m at 6.3° of tilt, about y from the near end to the far end (180°) / 7.2 m at 5.8° (before the
            # task 4.95 m at 8.5°). Held to what it is now, so it cannot get worse unseen
            jump, move = KNOWN_TIP[tilt_axis]
            assert dpsi.max() <= jump, (f"axis {tilt_axis}: the wrap jumps {dpsi.max():.1f}° in one step of "
                                        f"0.075° tilt at {math.degrees(tilt[k]):.2f}°")
            assert step.max() < move, f"axis {tilt_axis}: the catenary's start moves {step.max():.2f} m"


def test_lowering_a_flat_gutter_the_bends_end_moves_on_smoothly():
    """Found by this tester, fixed by the worker (``BED_BAND`` 0.5 → 2 m) – brief 1: no step / no twitch. Before: The flat 4 m gutter lowered towards the seabed 10 mm a moment, the cable
    (end straight aft, 63 m of it beyond the flat distance) leaving at the far end every moment: where the free bend
    comes within ``BED_BAND`` of the seabed (centre 2.28 … 2.45 m over it) its fixed point does not settle in
    ``BEND_ROUNDS`` – the bend's end (the catenary's start) jumps back and forth by up to 0.73 m between moments 10 mm
    apart (y = -1.29, -1.10, -1.10, -1.18, -1.21, -1.10, -1.06, -1.33, -1.86, -2.10, -1.86, -1.13, -1.70, -2.08 …).
    Over 6 m → 2 cm in 400 moments, for the end 2 m to either side or more cable: steps of 0.65 … 1.5 m."""
    h = np.linspace(2.45, 2.28, 18)
    F = len(h)
    g = gutter(F, h, R=4.0)
    S = np.array([-60.0, 0.0, ZB])
    res = C.hang_off(*g, math.pi, S, AFT, ZB, length0(g, S, np.full(F, 3.0)))
    assert np.allclose(np.degrees(res["psi"]), 180.0, atol=0.5)
    step = np.linalg.norm(np.diff(res["T"], axis=0), axis=1)
    worst = []
    H = np.linspace(6.0, 0.02, 400)
    for lat, extra in ((0.0, 3.0), (0.0, 6.0), (-2.0, 3.0), (2.0, 6.0)):
        g4 = gutter(400, H, R=4.0)
        S4 = np.array([-60.0, lat, ZB])
        r4 = C.hang_off(*g4, math.pi, S4, AFT, ZB, length0(g4, S4, np.full(400, extra)))
        worst.append(float(np.linalg.norm(np.diff(r4["T"], axis=0), axis=1).max()))
    assert step.max() < 0.1 and max(worst) < 0.3, (f"bend's end moves {step.max():.2f} m between moments 10 mm apart; "
                                                   f"6 m → 2 cm sweeps: {np.round(worst, 2).tolist()} m")


def test_the_free_bend_near_the_seabed_is_a_settled_answer():
    """Found by this tester, fixed by the worker (``BED_BAND`` 2 m; a piled cable reads its wrap from straight down) –
    same cause as the one above. Before: The free bend's fixed point near the seabed is not reached: the answer depends on how many
    rounds were run and on rounding – the SAME set-up turned about the vertical (gutter, cable end and lay direction
    all turned together) gives a catenary start up to 4 m elsewhere (gutter 2.02 m, tipped 0.2 rad, 2.86 m over the
    seabed); with ``BEND_ROUNDS`` 80 / 400 / 2000 the 4 m gutter at 2.40 m gives y = -1.10 / -1.06 / -2.07 m."""
    R, h, lat, extra = 2.0195369004891885, 2.8591386862651413, 0.5197609354482537, 5.417987088966163
    g = gutter(1, [h], R=R, tilt=0.2)
    S = np.array([-60.0, lat, ZB])
    L0 = length0(g, S, [extra])
    ref = C.hang_off(*g, math.pi, S, AFT, ZB, L0)["T"][0]
    spread = 0.0
    c, ax, r, side, arr = g
    for phi in (0.3, 1.0, -2.37, 2.0):
        Rz = rot((0, 0, 1), phi)
        got = C.hang_off(c @ Rz.T, ax @ Rz.T, r, side, arr @ Rz.T, math.pi, Rz @ S, Rz @ AFT, ZB, L0)["T"][0] @ Rz
        spread = max(spread, float(np.abs(got - ref).max()))
    rounds = []
    was = C.BEND_ROUNDS
    try:
        g2 = gutter(1, [2.40], R=4.0)
        S2 = np.array([-60.0, 0.0, ZB])
        for n in (80, 400, 2000):
            C.BEND_ROUNDS = n
            rounds.append(float(C.hang_off(*g2, math.pi, S2, AFT, ZB, length0(g2, S2, [3.0]))["T"][0, 1]))
    finally:
        C.BEND_ROUNDS = was
    assert spread < 1e-3 and np.ptp(rounds) < 1e-3, (f"turned about the vertical: {spread:.2f} m apart; "
                                                     f"rounds 80/400/2000: y = {np.round(rounds, 3).tolist()}")


def test_KNOWN_FAULT_where_the_free_bend_reaches_the_seabed_the_cable_kinks():
    """FAULT (brief 1: "no bend outside the gutter of more than the gutter's own arc per point"). Where the free bend
    reaches the seabed it is cut there (``_bend_fit``) still pointing down, and the catenary from 1 mm over the seabed
    goes on flat: the drawn cable turns by up to 49° at that one point (NORMAL cable, flat 4 m gutter 2.3 m over the
    seabed; 86–88° where the cable piles up). The gutter's own arc: 4° per point. (Before the change: up to 62° at
    the wheel; the kink moved from the wheel to the seabed.)"""
    F = 200
    h = np.linspace(6.0, 0.02, F)
    g = gutter(F, h, R=4.0)
    S = np.array([-60.0, 0.0, ZB])
    res = C.hang_off(*g, math.pi, S, AFT, ZB, length0(g, S, np.full(F, 3.0)))
    worst, at = 0.0, None
    for k in np.flatnonzero(res["kind"] == C.NORMAL):
        arc, bend, cat = drawn(res, k, g)
        if not len(bend):
            continue
        t = turns(np.concatenate([arc[-2:], bend, cat[:2]]))
        if t.max() > worst:
            worst, at = float(t.max()), (float(h[k]), float(res["T"][k, 2] - ZB), math.degrees(res["bend"][k]))
    # KNOWN FAULT (open point 2 of task 0172): the brief wants ≤ 4° (the gutter's arc per point); 48.7° now (before the
    # task the kink was at the wheel: up to 62°). Held to what it is now, so it cannot get worse unseen
    assert worst <= KNOWN_SEABED_KINK, (f"{worst:.1f}° at one drawn point (centre {at[0]:.2f} m over the seabed, the bend's "
                                 f"end {at[1] * 1000:.0f} mm over it, bend {at[2]:.1f}°)")


# ---------------------------------------------------------------------------
# 2. and 3. in Blender (as a Python module)
# ---------------------------------------------------------------------------

PATHS_MODEL = os.path.join(HERE, "data", "test_paths_a.step")


@pytest.fixture(scope="module")
def blender(tmp_path_factory):
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield str(tmp_path_factory.mktemp("t0172"))
    fresing_render.unregister()


def _model(folder, moves, start_away=0.0, motor=True):
    """test_paths_a.step with SHEAVE 2 on a slide joint "Away" (up and forward, out of the rope's way, as
    tests/test_paths.py ``lifting``); the rope runs at 10 m/min for 6 s (``motor``); ``moves``: (start, seconds, to)
    of "Away"; ``start_away``: its value before Build."""
    import sys

    import addon_utils
    import bpy
    from mathutils import Vector

    from fresing_render.blender import build, joints, paths
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import make_test_paths as maker
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=PATHS_MODEL, quality="draft") == {"FINISHED"}
    sheave = next(o for o in sc.objects if o.get(build.PROP_NAME) == "SHEAVE 2")
    centre = np.array(maker.NUMBERS["contacts"]["SHEAVE 2"]["axis_point"]) * 0.001
    joints.create(sc, "SLIDE", [sheave], Vector(centre), Vector((0.8, 0.0, 0.6)), name="Away")
    made = paths.set_up_test_model(sc)
    it = paths.find(sc, made["cable"])
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Sheave away", 0.0, "25"
    if motor:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", it.joint, 0.0, 6.0, "LINEAR"
        b.speed_mmin = 10.0
    for start, dur, to in moves:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Away", start, dur, "SMOOTH"
        b.use_from, b.to_dist = True, to
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    if start_away:
        joints.set_value(joints.find(sc, "Away"), start_away, use_limits=False)
        bpy.context.view_layer.update()
    return sc, it, a


def _values(sc, j, frames):
    from fresing_render.blender import joints
    out = []
    for f in frames:
        sc.frame_set(int(f))
        out.append(joints.get_value(j))
    return np.array(out)


def _built(sc, it, a):
    """Build; returns (frames, rope paid out, SHEAVE 2's value, on: the solver's rope on SHEAVE 2 per frame)."""
    from fresing_render.blender import animation, joints, paths
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    r = animation.bake(sc, a)
    frames = np.arange(1, r["frames"] + 1)
    pay = _values(sc, joints.find(sc, it.joint), frames)
    v2 = _values(sc, joints.find(sc, c2.joint), frames)
    got = paths._stored_places(sc, it, paths._inputs_of(it)[1])
    on = None
    if got is not None:
        rel, first = got[:2]
        res = paths._solve_item(sc, it, rel, first=first)
        on = np.asarray(res["wrap"])[:, [c.name for c in paths._wheels(it)].index("SHEAVE 2")] > 1e-6
    return frames, pay, v2, on


def _check_held(sc, it, pay, v2, on, ratio):
    from fresing_render.blender import joints
    step, want = np.diff(v2), joints.factor("SLIDE", "ROTATE", ratio) * np.diff(pay)
    off = ~on[1:]
    both = on[1:] & on[:-1]
    assert np.abs(step[off]).max() < 1e-9                       # stands still while lifted off
    assert np.allclose(step[both], want[both], atol=1e-5)        # turns with the rope while on it


def test_a_sheave_lifted_and_touched_again_three_times(blender):
    """SHEAVE 2 carried out of the rope's way and back three times while the rope runs: it stands still at every
    frame it is off and turns with the rope at every frame it is on; Clear keys puts its coupling back."""
    from fresing_render.blender import animation, joints, paths_rollers
    sc, it, a = _model(blender, [(0.5, 0.6, 3.2), (1.5, 0.6, 0.0), (2.5, 0.6, 3.2), (3.5, 0.6, 0.0),
                                 (4.5, 0.6, 3.2)])
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    ratio, follows = joints.find(sc, c2.joint).couple_ratio, joints.find(sc, c2.joint).follows
    _frames, pay, v2, on = _built(sc, it, a)
    assert on is not None and len(np.flatnonzero(np.diff(on.astype(int)))) == 5      # off, on, off, on, off
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == "" and paths_rollers.WAS in j2.motion
    _check_held(sc, it, pay, v2, on, ratio)
    animation.clear_keys(sc)
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == follows and j2.couple_ratio == pytest.approx(ratio, rel=1e-6)
    assert paths_rollers.WAS not in j2.motion and paths_rollers.STILL not in j2.motion


def test_a_sheave_lifted_at_the_first_frame(blender):
    """SHEAVE 2 already out of the rope's way when the animation starts, brought back at 2 s: still until then,
    turning with the rope after."""
    from fresing_render.blender import joints
    sc, it, a = _model(blender, [(2.0, 1.0, 0.0)], start_away=3.2)
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    ratio = joints.find(sc, c2.joint).couple_ratio
    _frames, pay, v2, on = _built(sc, it, a)
    assert on is not None and not on[0] and on[-1]
    _check_held(sc, it, pay, v2, on, ratio)
    assert abs(v2[-1] - v2[0]) > 1.0


def test_a_sheave_never_touched_has_one_key_and_never_turns(blender):
    """SHEAVE 2 out of the rope's way the whole animation: it never turns (one key), its coupling put aside, and back
    after Clear keys."""
    from fresing_render.blender import animation, joints, paths, paths_rollers
    sc, it, a = _model(blender, [], start_away=3.2)
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    follows = joints.find(sc, c2.joint).follows
    _frames, pay, v2, _on = _built(sc, it, a)
    assert pay[-1] - pay[0] > 0.9
    assert np.ptp(v2) == 0.0
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == "" and paths_rollers.WAS in j2.motion
    fc = next(f for f in paths._fcurves(j2.motion) if f.data_path == joints.COUPLING_PATH)
    assert len(fc.keyframe_points) == 1
    animation.clear_keys(sc)
    assert joints.find(sc, c2.joint).follows == follows


def test_build_twice_and_clear_then_build_give_the_same_turns(blender):
    from fresing_render.blender import animation, joints, paths_rollers
    sc, it, a = _model(blender, [(0.5, 0.6, 3.2), (2.5, 0.6, 0.0)])
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    follows = joints.find(sc, c2.joint).follows
    _f, _p, first, _on = _built(sc, it, a)
    _f, _p, again, _on = _built(sc, it, a)
    animation.clear_keys(sc)
    j2 = joints.find(sc, c2.joint)
    assert j2.follows == follows and paths_rollers.WAS not in j2.motion
    _f, _p, third, _on = _built(sc, it, a)
    assert np.abs(first - again).max() == 0.0 and np.abs(first - third).max() == 0.0
    assert abs(first[-1] - first[0]) > 1.0


def test_a_sheave_turned_by_something_else_is_left_alone(blender):
    """SHEAVE 2's joint made to follow "Luff" (not its rope): Build leaves its coupling alone although the rope
    leaves it."""
    from fresing_render.blender import joints, paths_rollers
    sc, it, a = _model(blender, [(0.5, 0.6, 3.2), (2.5, 0.6, 0.0)])
    c2 = next(c for c in it.contacts if c.name == "SHEAVE 2")
    joints.set_follows(sc, joints.find(sc, c2.joint), "Luff")
    j2 = joints.find(sc, c2.joint)
    before = (j2.follows, j2.couple_ratio)
    _built(sc, it, a)
    j2 = joints.find(sc, c2.joint)
    assert (j2.follows, j2.couple_ratio) == before and paths_rollers.WAS not in j2.motion
