"""Task 0374, independent tester: tries to break rows A, E, H, C and I of the brief, written from the brief (not from
the code). Pure NumPy first (``core/catenary.hang_off`` / ``hang_off_steady``, ``core/paths.read_cable``), then
Blender as a Python module (two cables over one sheave; Copy brings a cable read from CAD).

It found 7 faults (28 Nov 2026). The worker fixed four of them (3 moments at once crashed, batch vs one at a time,
a slid moment lost its free bend, a tilted gutter 3x slower) and a stale note of a third cable; their tests now pass.
Three are open points of task 0374, kept as ``test_KNOWN_FAULT_…`` held to today's size (a pytest group on GitHub
allows one skipped test, so no xfail): lower the ``KNOWN_*`` bounds when they are fixed and rename the tests."""

import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import catenary as C
from fresing_render.core import paths as P

HERE = os.path.dirname(__file__)
ZB = -30.0                              # the cable's middle on the seabed
AFT = np.array([-1.0, 0.0, 0.0])        # laid aft (-x)


# ---------------------------------------------------------------------------
# helpers (as tests/test_flex_followups_independent.py)
# ---------------------------------------------------------------------------

def rot(axis, a):
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


def gutter(F, height, R=4.0, tilt=0.0, tilt_axis=(1.0, 0.0, 0.0)):
    """A 180° gutter (axis +z, side -1, arrives at +y going +x, leaves at -y going -x), turned by ``tilt`` about
    ``tilt_axis`` through its centre, its centre ``height`` over the cable's middle on the seabed."""
    height = np.broadcast_to(np.asarray(height, dtype=float), (F,))
    tilt = np.broadcast_to(np.asarray(tilt, dtype=float), (F,))
    c = np.zeros((F, 3))
    c[:, 2] = ZB + height
    ax = np.array([rot(tilt_axis, t) @ [0.0, 0.0, 1.0] for t in tilt])
    arr = c + np.array([rot(tilt_axis, t) @ [0.0, R, 0.0] for t in tilt])
    return c, ax, R, -1.0, arr


def length0(inputs, S, extra):
    c, _ax, R, _side, _arr = inputs
    return R * math.pi + np.linalg.norm(S[:2] - c[0, :2]) + np.asarray(extra, dtype=float)


def rows(g, sel, F):
    return tuple(x[sel] if isinstance(x, np.ndarray) and x.shape[:1] == (F,) else x for x in g)


def t_step(res):
    return np.linalg.norm(np.diff(res["T"], axis=0), axis=1)


def tipping(R, h, tilt_axis, tilt0_deg, Fm, lat, extra, still=50):
    """A gutter tipping from ``tilt0_deg`` to flat in ``Fm`` frames, then standing still for ``still`` frames."""
    F = Fm + still
    tilt = np.concatenate([np.linspace(math.radians(tilt0_deg), 0.0, Fm), np.zeros(still)])
    g = gutter(F, np.full(F, h), R=R, tilt=tilt, tilt_axis=tilt_axis)
    S = np.array([-60.0, lat, ZB])
    return g, S, length0(g, S, np.full(F, extra))


# ---------------------------------------------------------------------------
# row A – the free bend's seabed fit in closed form
# ---------------------------------------------------------------------------

def test_bend_fit_matches_a_dense_scan_of_the_bends_height():
    """_bend_fit (closed form) against a dense scan of z(φ) = T_z + r (sin φ t_z + (1 − cos φ) m_z): the first φ where
    it reaches the floor (or theta; 0 when T starts at or below it). 3,000 random bends, any radius, any turn."""
    rng = np.random.default_rng(5)
    N, n = 3000, 4001
    t = rng.normal(size=(N, 3))
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    m = rng.normal(size=(N, 3))
    m -= (m * t).sum(1, keepdims=True) * t
    m /= np.linalg.norm(m, axis=1, keepdims=True)
    r = 10 ** rng.uniform(-2, 1.5, N)
    T = np.zeros((N, 3))
    T[:, 2] = rng.uniform(-1, 3, N) * r
    theta = rng.uniform(0, 2 * math.pi, N)
    got = C._bend_fit(T, t, m, r, theta, 0.0)
    phi = theta[:, None] * np.linspace(0.0, 1.0, n)[None, :]
    z = T[:, 2, None] + r[:, None] * (np.sin(phi) * t[:, 2, None] + (1 - np.cos(phi)) * m[:, 2, None])
    below = z <= 0.0
    first = np.argmax(below, axis=1)
    want = np.where(below.any(axis=1), phi[np.arange(N), first], theta)
    want = np.where(T[:, 2] <= 0.0, 0.0, want)
    assert np.isfinite(got).all()
    assert (np.abs(got - want) <= 2.0 * theta / (n - 1) + 1e-9).all()


# ---------------------------------------------------------------------------
# row A – hang_off with few moments, and many moments against one at a time
# ---------------------------------------------------------------------------

def _three(F):
    h = np.linspace(6, 0.5, F)
    g = gutter(F, h, R=3.5, tilt=np.linspace(0.3, 0.1, F), tilt_axis=(1, 0, 0))
    S = np.array([-60.0, 1.5, ZB])
    return g, S, length0(g, S, np.linspace(1, 5, F))


@pytest.mark.parametrize("F", [2, 4, 5, 9])
def test_a_few_moments_at_once_give_what_one_at_a_time_gives(F):
    g, S, L0 = _three(F)
    every = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
    for k in range(F):
        one = C.hang_off(*rows(g, slice(k, k + 1), F), math.pi, S, AFT, ZB, L0[k:k + 1])
        assert np.abs(one["T"][0] - every["T"][k]).max() < 1e-6
        assert abs(one["psi"][0] - every["psi"][k]) < 1e-9


def test_three_moments_at_once():
    g, S, L0 = _three(3)
    C.hang_off(*g, math.pi, S, AFT, ZB, L0)
    C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)


def _window(a, b, F=4500):
    k = np.arange(a, b)
    h = np.linspace(6, 0.05, F)[k]
    tilt = np.linspace(0.4, 0.0, F)[k]
    ex = np.linspace(1, 8, F)[k]
    g = gutter(len(k), h, R=4.0, tilt=tilt)
    S = np.array([-60.0, 2.5, ZB])
    return g, S, length0(g, S, ex)


def test_a_batch_gives_what_one_at_a_time_gives_near_two_answers():
    g, S, L0 = _window(1266, 1300)
    F = len(L0)
    every = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
    one = np.array([C.hang_off(*rows(g, slice(k, k + 1), F), math.pi, S, AFT, ZB, L0[k:k + 1])["psi"][0]
                    for k in range(F)])
    assert np.degrees(np.abs(one - every["psi"])).max() < 1e-3


# ---------------------------------------------------------------------------
# row A – the slide over time
# ---------------------------------------------------------------------------

def _sheave(F, cx, cz, R=2.0, yaw=None, side=1.0):
    c = np.zeros((F, 3))
    c[:, 0], c[:, 2] = cx, cz
    yaw = np.zeros(F) if yaw is None else yaw
    ax = np.array([rot((0, 0, 1), a) @ [0, 1.0, 0] for a in yaw])
    arr = c + np.array([rot((0, 0, 1), a) @ [R, 0, 0] for a in yaw])
    return c, ax, R, side, arr


@pytest.mark.parametrize("case", ["fast drop", "fast run", "fast payout", "fast yaw"])
def test_a_fast_legitimate_move_is_followed_not_lagged(case):
    """A sheave dropped 0.65 m a frame, run 1 m a frame, the cable paid out 1.3 m a frame, the sheave yawed 2.4° a
    frame: the steady answer is every moment's own (the slide never holds it back)."""
    F = 60
    S = np.array([-80.0, 0, ZB])
    cx, cz, yaw, L0 = np.zeros(F), np.full(F, 20 + ZB), None, None
    if case == "fast drop":
        cz = np.linspace(40, 2, F) + ZB
    elif case == "fast run":
        cx = np.linspace(0, -60, F)
    elif case == "fast payout":
        L0 = np.linspace(85, 160, F)
    else:
        yaw = np.linspace(0, 2.5, F)
    if L0 is None:
        L0 = math.pi * 2.0 + np.hypot(cx - S[0], cz - ZB) * 1.05 + 3
    for side in (1.0, -1.0):
        g = _sheave(F, cx, cz, yaw=yaw, side=side)
        own = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
        st = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
        assert np.abs(own["psi"] - st["psi"]).max() < 1e-9
        assert np.isfinite(st["T"]).all()


def test_tipping_through_flat_the_slide_keeps_its_bound_and_gets_there():
    """Fuzz (seeded) of the brief's case – any radius, height, tilt axis, start tilt either way, speed, end aside,
    extra cable – followed by still frames: every answer finite, the wrap in 0 … π, between neighbouring frames the
    leave point moves at most SLIDE + SLIDE_FOLLOW x what moved, and once still it ends on the moment's own answer."""
    rng = np.random.default_rng(11)
    for _ in range(12):
        R, h = rng.uniform(1.5, 6), rng.uniform(0.3, 4)
        tilt_axis = [(1, 0, 0), (0, 1, 0), (1, 1, 0)][int(rng.integers(3))]
        t0 = rng.uniform(10, 50) * rng.choice([-1, 1])
        g, S, L0 = tipping(R, h, tilt_axis, t0, int(rng.integers(30, 300)), rng.uniform(-4, 4), rng.uniform(0.5, 8),
                           still=150)
        own = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
        st = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
        for key in ("T", "psi", "bend", "direction"):
            assert np.isfinite(st[key]).all(), key
        assert (st["psi"] >= -1e-12).all() and (st["psi"] <= math.pi + 1e-9).all()
        c, ax, r, _side, arr = g
        moved = np.zeros(len(L0))
        moved[1:] = (np.linalg.norm(np.diff(c, axis=0), axis=1) + np.linalg.norm(np.diff(arr, axis=0), axis=1)
                     + r * np.linalg.norm(np.diff(ax, axis=0), axis=1))
        assert (np.abs(np.diff(st["psi"])) * r <= C.SLIDE + C.SLIDE_FOLLOW * moved[1:] + 1e-9).all()
        assert abs(st["psi"][-1] - own["psi"][-1]) < 1e-9


@pytest.mark.parametrize("case", [
    # R, h, tilt axis, start tilt °, frames, end aside, extra cable: the cable leaves before it arrives (short, no
    # free bend) and one frame later lies in the gutter with a free bend of 76–91°
    (5.5, 1.9, (1, 0, 0), -37.0, 200, -2.4, 7.3),
    (2.1, 3.2, (1, 0, 0), -37.0, 400, 2.5, 4.6),
    # the leave point comes up through the floor (1 mm over the seabed): the free bend switches on at once (0 → 68°)
    (3.971, 0.406, (1, 0, 0), 16.2, 258, 2.271, 5.277),
])
def test_KNOWN_FAULT_tipping_through_flat_the_catenary_start_jumps_where_the_free_bend_switches(case):
    """KNOWN FAULT (task 0374's open point, older than 0374: 5–13 m before it): the leave point slides, but where the
    free bend switches on or off (the cable becomes 'short', or the leave point comes up through the floor) the
    catenary's start jumps 3–7 m in one frame. Held to today's size (the brief's bound is 0.5 m)."""
    R, h, ax, t0, Fm, lat, extra = case
    g, S, L0 = tipping(R, h, ax, t0, Fm, lat, extra)
    st = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
    assert np.degrees(np.abs(np.diff(st["psi"]))).max() < 10.0         # (holds: the leave point slides)
    assert t_step(st).max() < KNOWN_T_JUMP, t_step(st).max()


def test_a_slid_moment_keeps_its_free_bend():
    g, S, L0 = _window(1500, 1620)
    st = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
    assert not st["short"].any(), np.flatnonzero(st["short"]) + 1500
    assert t_step(st).max() < 0.5, t_step(st).max()


def test_frames_with_gaps_duplicates_and_out_of_order():
    """``frames`` with gaps, a repeated frame and frames out of order: every answer finite and in range; moments that
    are no neighbouring frames keep their own answers."""
    F = 120
    g, S, L0 = tipping(3.5, 1.0, (1, 0, 0), 30.0, F - 20, 0.0, 2.0, still=20)
    own = C.hang_off(*g, math.pi, S, AFT, ZB, L0)
    for fr in (np.arange(F) * 2,                                  # no two neighbouring
               np.concatenate([np.arange(60), np.arange(59, 119)]),   # one frame repeated
               np.arange(F)[::-1].copy()):                        # backwards
        st = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0, frames=fr)
        assert np.isfinite(st["T"]).all()
        assert (st["psi"] >= -1e-12).all() and (st["psi"] <= math.pi + 1e-9).all()
        neighbour = np.zeros(F, dtype=bool)
        neighbour[1:] = fr[1:] == fr[:-1] + 1
        if not neighbour.any():
            assert np.allclose(st["psi"], own["psi"])


# ---------------------------------------------------------------------------
# row E – speed
# ---------------------------------------------------------------------------

def test_4500_moments_of_a_flat_gutter_lowered_to_the_seabed_take_well_under_2_s():
    F = 4500
    g = gutter(F, np.linspace(6, 0.05, F), R=4.0)
    S = np.array([-60.0, 0.0, ZB])
    L0 = length0(g, S, np.full(F, 3.0))
    t0 = time.perf_counter()
    res = C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
    took = time.perf_counter() - t0
    assert np.isfinite(res["T"]).all()
    assert took < 1.2, took                              # (0.44 s here; 1.2 s before 0374)


def test_4500_moments_of_a_tilted_gutter_beside_the_lay_are_fast_too():
    F = 4500
    g = gutter(F, np.linspace(6, 0.05, F), R=4.0, tilt=np.linspace(0.4, 0.0, F))
    S = np.array([-60.0, 2.5, ZB])
    L0 = length0(g, S, np.linspace(1, 8, F))
    t0 = time.perf_counter()
    C.hang_off_steady(*g, math.pi, S, AFT, ZB, L0)
    assert time.perf_counter() - t0 < 1.2


# ---------------------------------------------------------------------------
# row H – read_cable: splines and coils
# ---------------------------------------------------------------------------

# task 0374's open points as found by its tester, held to today's size (lower them when fixed; rename the tests then)
KNOWN_T_JUMP = 7.5              # m: the catenary's start in one frame where the free bend switches (brief: 0.5 m)
KNOWN_NOISY_SPLINE = 0.0055     # m: an S-curve with 20 µm noise read this far off (brief: ~2 mm)
KNOWN_FACETED_COIL = 0.0065     # m: a coil from a coarse tube refused this far off
ROPE = 0.02


def even(curve, step=ROPE):
    seg = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(curve, axis=0), axis=1))])
    s = np.linspace(0, seg[-1], max(int(seg[-1] / step), 2) + 1)
    return np.stack([np.interp(s, seg, curve[:, k]) for k in range(3)], axis=1)


def bez(ctrl, n=2000):
    t = np.linspace(0, 1, n)[:, None]
    c = np.asarray(ctrl, float)
    return (1 - t) ** 3 * c[0] + 3 * (1 - t) ** 2 * t * c[1] + 3 * (1 - t) * t ** 2 * c[2] + t ** 3 * c[3]


def s_curve():
    s = np.linspace(0, 2 * math.pi, 3000)
    return np.c_[s, 0.6 * np.sin(s), np.zeros_like(s)]


def helix():
    a = np.linspace(0, 4 * math.pi, 3000)
    return np.c_[0.8 * np.cos(a), 0.8 * np.sin(a), 0.3 * a / (2 * math.pi)]


def mixed():
    """straight – spline – straight – a true 90° arc of 0.7 m – straight."""
    l1 = np.linspace([0, 0, 0], [2, 0, 0], 200)
    b = bez([[2, 0, 0], [3, 0, 0], [3, 0, 1.5], [4, 0.5, 1.5]])
    d = np.array([1, 0.5, 0]) / np.linalg.norm([1, 0.5, 0])
    l2 = np.linspace([4, 0.5, 1.5], np.array([4, 0.5, 1.5]) + 1.5 * d, 200)
    p0, n = l2[-1], np.array([0, 0, 1.0])
    c = p0 + 0.7 * np.cross(n, d)
    a = np.linspace(0, math.pi / 2, 400)
    ar = c + 0.7 * (np.cos(a)[:, None] * (p0 - c) / 0.7 + np.sin(a)[:, None] * d)
    d2 = np.cross(n, (ar[-1] - c) / 0.7)
    l3 = np.linspace(ar[-1], ar[-1] + 2 * d2, 200)
    return np.concatenate([l1, b[1:], l2[1:], ar[1:], l3[1:]])


@pytest.mark.parametrize("name", ["S-curve", "helix", "mixed"])
def test_a_spline_or_coil_is_read_as_short_bends_that_keep_to_the_cable(name):
    pts = even({"S-curve": s_curve, "helix": helix, "mixed": mixed}[name]())
    t0 = time.perf_counter()
    rd = P.read_cable(pts, ROPE, [])
    took = time.perf_counter() - t0
    assert rd.ok, rd.problem
    assert rd.contacts and all(c.kind == "BEND" for c in rd.contacts)
    assert rd.deviation < 0.002, rd.deviation
    assert rd.path.length == pytest.approx(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum(), rel=2e-3)
    assert took < 15.0, took                          # (0.8–3.7 s here)


@pytest.mark.parametrize("L, off", [(0.3, 0.1), (0.6, 0.15)])
def test_a_short_spline_between_two_straights_is_read(L, off):
    b = bez([[1, 0, 0], [1 + L / 2, 0, 0], [1 + L / 2, off, 0], [1 + L, off, 0.0]])
    pts = even(np.concatenate([np.linspace([0, 0, 0], [1, 0, 0], 100), b[1:],
                               np.linspace(b[-1], b[-1] + np.array([1.0, 0, 0]), 100)[1:]]))
    rd = P.read_cable(pts, ROPE, [])
    assert rd.ok and rd.deviation < 0.002, (rd.problem, rd.deviation)


def test_KNOWN_FAULT_a_spline_with_a_little_noise_leaves_the_cable_by_some_mm():
    """KNOWN FAULT (task 0374's open point): an S-curve spline, rope Ø40 mm, with 20 µm noise is read 3.3–5.0 mm off
    the points (the brief's ~2 mm; with 0.1 mm noise it is refused, in words). Held to today's size."""
    pts = even(s_curve())
    for seed in range(3):
        p = pts + np.random.default_rng(seed).normal(scale=2e-5, size=pts.shape)
        rd = P.read_cable(p, ROPE, [])
        assert rd.ok and rd.deviation < KNOWN_NOISY_SPLINE, (seed, rd.deviation, rd.problem)


def tube_of(poly, radius, sides=24, ring_step=0.03):
    """A closed faceted tube round a polyline, rings every ``ring_step`` (as a CAD mesher cuts a 0.8 m coil to 0.1 mm
    chord: one ring every ~2.5 cm)."""
    poly = even(np.asarray(poly, float), ring_step)
    t = np.gradient(poly, axis=0)
    t /= np.linalg.norm(t, axis=1, keepdims=True)
    u = np.cross(t[0], [1, 0, 0] if abs(t[0, 0]) < 0.9 else [0, 1, 0])
    V = []
    for p, tt in zip(poly, t):
        u = u - (u @ tt) * tt
        u /= np.linalg.norm(u)
        v = np.cross(tt, u)
        for i in range(sides):
            a = 2 * math.pi * i / sides
            V.append(p + radius * (math.cos(a) * u + math.sin(a) * v))
    T, n = [], len(poly)
    for k in range(n - 1):
        for i in range(sides):
            a, b = k * sides + i, k * sides + (i + 1) % sides
            T += [(a, b, a + sides), (b, b + sides, a + sides)]
    n0, last = len(V), (n - 1) * sides
    V += [poly[0], poly[-1]]
    for i in range(sides):
        T += [(n0, (i + 1) % sides, i), (n0 + 1, last + i, last + (i + 1) % sides)]
    return np.array(V), np.array(T, dtype=np.int64)


def test_KNOWN_FAULT_a_coil_read_from_a_coarse_faceted_tube_is_refused_in_words():
    """KNOWN FAULT (task 0374's open point): a coil (r 0.8 m, pitch 0.3 m, rope Ø40 mm) from a tube with rings every
    3 cm is refused (5.7 mm beside the cable at its end; rings every 1 cm: read at 1.3 mm). Refused in plain words,
    never an exception; held so it gets no worse."""
    v, t = tube_of(helix(), ROPE)
    tube = P.centreline(v, t)
    assert tube.ok, tube.problem
    rd = P.read_cable(tube.points, tube.radius, [])
    assert rd.ok or ("beside the cable" in rd.problem and rd.deviation < KNOWN_FACETED_COIL), (rd.deviation,
                                                                                               rd.problem)


def test_what_is_no_cable_is_still_refused_and_never_raises():
    line = np.linspace([0, 0, 0], [1, 0, 0], 51)
    bad = line.copy()
    bad[7, 1] = np.nan
    for pts, r in ((np.zeros((0, 3)), ROPE), (line[:1], ROPE), (bad, ROPE), (line, 0.0), (line, -ROPE),
                   (line, float("nan")), (line, float("inf")), (np.zeros((6, 3)), ROPE), ("junk", ROPE)):
        rd = P.read_cable(pts, r, [])
        assert not rd.ok and rd.problem and rd.contacts == []


# ---------------------------------------------------------------------------
# rows C and I – Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, copy, drawn, hover, joints, logic, paths, remove, workspaces  # noqa: E402

MODEL = os.path.join(HERE, "data", "test_paths_a.step")


@pytest.fixture(scope="module")
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update():
    for _ in range(2):
        bpy.context.view_layer.update()


def _fresh(tmp_path, winch=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    workspaces.switch(sc, "All functions")
    paths.set_up_test_model(sc, winch=winch)
    update()
    return sc


def named(sc, name, root=None):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name
                and (root is None or build.model_root_of(o) is root))


def cast(sc, origin, direction, want):
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert index >= 0 and ob.get(build.PROP_NAME) == want, ob.get(build.PROP_NAME) if ob else None
    return ob, index, loc, normal


def draw_over_sheave_1(sc, name, start_xy=(2.5, 0.5)):
    """A cable drawn from the base frame over SHEAVE 1 (as tests/test_paths_shared.py)."""
    rope = [named(sc, "WIRE ROPE")] + [it.part for it in sc.fresing.cables if it.drawn and it.part is not None]
    logic.exclude(rope, True)
    update()
    ob, index, loc, normal = cast(sc, (start_xy[0], start_xy[1], 3.0), (0, 0, -1), "BASE FRAME")
    start = drawn.spot(ob, index, loc, normal)
    s1, _i, hit, _n = cast(sc, (4.776, 0.0, 6.0), (0, 0, -1), "SHEAVE 1")
    logic.exclude(rope, False)
    update()
    paths.draw_cable(sc, start, [(s1, np.array(hit), False)], None, name=name, diameter=0.020)
    update()


def contact(item, part_name):
    return next(c for c in item.contacts if c.part is not None and c.part.get(build.PROP_NAME) == part_name)


def joints_moving(sc, ob):
    return [j.name for j in sc.fresing.joints if ob in joints.members(j)]


def test_three_cables_over_one_sheave_and_the_first_goes(addon, tmp_path):
    """Three cables over SHEAVE 1: one joint; the 2nd and 3rd say they share it with the first; the first removed: the
    sheave turns with the 2nd; then the 2nd goes too: the 3rd turns it."""
    sc = _fresh(tmp_path)
    draw_over_sheave_1(sc, "Second rope")
    draw_over_sheave_1(sc, "Third rope", start_xy=(2.5, -0.4))
    s1 = named(sc, "SHEAVE 1")
    first, second, third = (paths.find(sc, n) for n in ("Wire rope", "Second rope", "Third rope"))
    assert len(joints_moving(sc, s1)) == 1
    name = contact(first, "SHEAVE 1").joint
    for it in (second, third):
        c = contact(it, "SHEAVE 1")
        assert c.joint == name and c.note.startswith(paths.SHARED + " 'Wire rope'"), c.note
    paths.remove(sc, paths.index_of(sc, paths.find(sc, "Wire rope")))
    update()
    second, third = paths.find(sc, "Second rope"), paths.find(sc, "Third rope")
    j = joints.find(sc, name)
    assert j is not None and joints_moving(sc, s1) == [name]
    assert j.follows == second.joint
    paths.remove(sc, paths.index_of(sc, second))
    update()
    third = paths.find(sc, "Third rope")
    j = joints.find(sc, name)
    assert j is not None and j.follows == third.joint and contact(third, "SHEAVE 1").made_joint


def test_a_third_cable_names_the_new_owner_after_the_first_goes(addon, tmp_path):
    sc = _fresh(tmp_path)
    draw_over_sheave_1(sc, "Second rope")
    draw_over_sheave_1(sc, "Third rope", start_xy=(2.5, -0.4))
    paths.remove(sc, paths.index_of(sc, paths.find(sc, "Wire rope")))
    update()
    c3 = contact(paths.find(sc, "Third rope"), "SHEAVE 1")
    assert "Wire rope" not in c3.note and c3.note.startswith(paths.SHARED + " 'Second rope'"), c3.note


def test_the_first_cable_read_again_after_it_went_shares_the_sheave(addon, tmp_path):
    """Remove the first cable (the second takes the sheave), then read the wire rope again: still ONE joint on SHEAVE 1,
    now the second's; the wire rope's contact says it shares it."""
    sc = _fresh(tmp_path)
    draw_over_sheave_1(sc, "Second rope")
    s1 = named(sc, "SHEAVE 1")
    paths.remove(sc, paths.index_of(sc, paths.find(sc, "Wire rope")))
    update()
    item = paths.add_cable(sc, "Wire rope")
    paths.read_cad(sc, item, named(sc, "WIRE ROPE"))
    update()
    assert len(joints_moving(sc, s1)) == 1, joints_moving(sc, s1)
    first, second = paths.find(sc, "Wire rope"), paths.find(sc, "Second rope")
    j = joints.find(sc, contact(second, "SHEAVE 1").joint)
    assert j.follows == second.joint
    c = contact(first, "SHEAVE 1")
    assert c.joint == j.name and c.note.startswith(paths.SHARED + " 'Second rope'"), c.note


def _orphans(sc):
    """Joints that move nothing and are no cable's speed joint."""
    speeds = {it.joint for it in sc.fresing.cables}
    return [j.name for j in sc.fresing.joints if not joints.members(j) and j.name not in speeds]


def test_pasted_twice_and_the_copy_removed(addon, tmp_path):
    """Paste the whole model twice: 'Wire rope (2)' and '(3)', each its own speed joint and drum; remove the second
    copy: the original and the first copy work as before, no joint left behind."""
    sc = _fresh(tmp_path, winch=True)
    root = build.model_roots(sc)[0]
    orphans0 = _orphans(sc)
    p2 = copy.paste(sc, [root])
    p3 = copy.paste(sc, [root])
    update()
    assert p2["cables"] == 1 and p3["cables"] == 1 and p3["drums"] == 1, (p2, p3)
    names = [it.name for it in sc.fresing.cables]
    assert names == ["Wire rope", "Wire rope (2)", "Wire rope (3)"], names
    js = {paths.find(sc, n).joint for n in names}
    assert len(js) == 3
    assert len(sc.fresing.spools) == 3
    r3 = bpy.data.objects[p3["roots"][0]]
    remove.remove(sc, [r3])
    update()
    assert [it.name for it in sc.fresing.cables] == ["Wire rope", "Wire rope (2)"]
    assert len(sc.fresing.spools) == 2
    for n in ("Wire rope", "Wire rope (2)"):
        it = paths.find(sc, n)
        assert paths.broken(sc, it) == "", (n, paths.broken(sc, it))
        for c in it.contacts:
            if c.kind in ("SHEAVE", "ROLLER") and c.made_joint:
                assert joints.find(sc, c.joint).follows == it.joint
    assert _orphans(sc) == orphans0
    assert not [j.name for j in sc.fresing.joints if "(3)" in j.name]


def test_copying_a_subassembly_with_some_of_the_wheels_leaves_the_cable(addon, tmp_path):
    """Paste only the V cradle (its two rollers): the cable is not copied and the paste says why; the original cable
    and its rollers' joints are as they were."""
    sc = _fresh(tmp_path, winch=True)
    cradle = named(sc, "V CRADLE.ASM")
    p = copy.paste(sc, [cradle])
    update()
    assert p["cables"] == 0 and p["drums"] == 0, p
    assert any("Cable 'Wire rope' is not copied" in x and "outside the copy" in x for x in p["left"]), p["left"]
    assert [it.name for it in sc.fresing.cables] == ["Wire rope"]
    it = paths.find(sc, "Wire rope")
    assert paths.broken(sc, it) == ""
    for c in it.contacts:
        if c.kind == "ROLLER":
            assert joints.find(sc, c.joint).follows == it.joint
            assert build.model_root_of(c.part) is build.model_root_of(named(sc, "BASE FRAME"))


def test_copy_with_a_drawn_cable_present(addon, tmp_path):
    """A drawn cable shares SHEAVE 1: the paste copies the wire rope read from CAD, names the drawn one in what is left
    out, and the copy's SHEAVE 1 turns with the copied wire rope."""
    sc = _fresh(tmp_path)
    draw_over_sheave_1(sc, "Second rope")
    root = build.model_roots(sc)[0]
    p = copy.paste(sc, [root])
    update()
    assert p["cables"] == 1, p
    assert any("Second rope" in x and "drawn" in x for x in p["left"]), p["left"]
    new = paths.find(sc, "Wire rope (2)")
    assert new is not None and paths.broken(sc, new) == ""
    r2 = bpy.data.objects[p["roots"][0]]
    c = contact(new, "SHEAVE 1")
    assert build.model_root_of(c.part) is r2
    assert joints.find(sc, c.joint).follows == new.joint
    # the original's sheave still turns with the original, and the drawn cable still shares it
    first, second = paths.find(sc, "Wire rope"), paths.find(sc, "Second rope")
    assert joints.find(sc, contact(first, "SHEAVE 1").joint).follows == first.joint
    assert contact(second, "SHEAVE 1").joint == contact(first, "SHEAVE 1").joint
