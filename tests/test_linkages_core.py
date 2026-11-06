"""Planar linkage solver (task 0014, ``core/linkages.py``): checked against formulas worked out by hand."""

import math

import pytest

from fresing_render.core import linkages as K


def deg(x):
    return math.radians(x)


# ---------------------------------------------------------------------------
# four-bar (crank-rocker): Freudenstein's closed form (Norton, Design of Machinery, eq. 4.10)
# ---------------------------------------------------------------------------

A_, B_, C_, D_ = 0.12, 0.35, 0.25, 0.40       # crank, coupler, rocker, ground (m)
TH0 = deg(60)


def freudenstein(th2, branch):
    k1, k2, k3 = D_ / A_, D_ / C_, (A_ ** 2 - B_ ** 2 + C_ ** 2 + D_ ** 2) / (2 * A_ * C_)
    a = math.cos(th2) - k1 - k2 * math.cos(th2) + k3
    b = -2 * math.sin(th2)
    c = k1 - (k2 + 1) * math.cos(th2) + k3
    return 2 * math.atan((-b + branch * math.sqrt(b * b - 4 * a * c)) / (2 * a))


def four_bar(input_pin=0):
    b = (A_ * math.cos(TH0), A_ * math.sin(TH0))
    th4 = freudenstein(TH0, -1)                        # the open branch: rocker pointing up
    c = (D_ + C_ * math.cos(th4), C_ * math.sin(th4))
    lk = K.Linkage(["base", "crank", "coupler", "rocker"],
                   [K.Pin(0, 1, (0, 0)), K.Pin(1, 2, b), K.Pin(2, 3, c), K.Pin(3, 0, (D_, 0))],
                   input=("pin", input_pin))
    return lk, b, c, th4


def test_four_bar_matches_freudenstein_over_two_turns_both_ways():
    lk, b, c, th4_0 = four_bar()
    s = K.Solver(lk)
    assert [st.kind for st in s.steps] == ["dyad_pp"] and not s.newton
    worst = 0.0
    for d in list(range(0, 721, 5)) + list(range(720, -721, -11)):
        th2 = TH0 + deg(d)
        p = s.solve(deg(d))
        cn = K.place(p[3], c)
        th4 = math.atan2(cn[1], cn[0] - D_)
        worst = max(worst, abs(math.remainder(th4 - freudenstein(th2, -1), 2 * math.pi)))
        bn = K.place(p[1], b)
        assert math.hypot(cn[0] - bn[0], cn[1] - bn[1]) == pytest.approx(B_, abs=1e-12)
    assert worst < 1e-9


def test_four_bar_big_jump_lands_on_the_same_branch():
    lk, b, c, _ = four_bar()
    s = K.Solver(lk)
    p = s.solve(10 * 2 * math.pi + deg(100))           # ten turns in one go
    cn = K.place(p[3], c)
    assert math.atan2(cn[1], cn[0] - D_) == pytest.approx(freudenstein(TH0 + deg(100), -1), abs=1e-9)
    assert s.limits() == (-math.inf, math.inf)             # a Grashof crank turns without end


def test_rocker_as_input_stops_where_crank_and_coupler_are_in_line():
    lk, b, c, th4_0 = four_bar(input_pin=3)
    s = K.Solver(lk)
    lo, hi = s.limits()
    # extremes of the rocker: |AC| = b + a and b - a; the angle at D from the law of cosines
    def rocker_at(ac):
        cos_d = (C_ ** 2 + D_ ** 2 - ac ** 2) / (2 * C_ * D_)
        return math.pi - math.acos(cos_d)                  # angle of DC from the +x axis (C above the ground)
    ends = sorted([rocker_at(B_ + A_) - th4_0, rocker_at(B_ - A_) - th4_0])
    assert lo == pytest.approx(ends[0], abs=1e-6)
    assert hi == pytest.approx(ends[1], abs=1e-6)
    s.solve(hi - 1e-4)
    with pytest.raises(K.Unreachable, match="cannot meet"):
        s.solve(hi + deg(5))
    assert s.value <= hi                                   # it stays at its last good position
    assert s.value > hi - deg(1.01)


# ---------------------------------------------------------------------------
# slider-crank with an offset
# ---------------------------------------------------------------------------

def test_slider_crank_matches_the_formula():
    r, l, e = 0.1, 0.3, 0.02
    th0 = deg(30)
    b = (r * math.cos(th0), r * math.sin(th0))
    p0 = (b[0] + math.sqrt(l * l - (b[1] - e) ** 2), e)
    lk = K.Linkage(["base", "crank", "rod", "slider"], [K.Pin(0, 1, (0, 0)), K.Pin(1, 2, b), K.Pin(2, 3, p0)],
                   slides=[K.Slide(3, 0, p0, (1, 0))])
    s = K.Solver(lk)
    for d in range(0, 721, 7):
        t = th0 + deg(d)
        poses = s.solve(deg(d))
        x = K.place(poses[3], p0)
        assert x[0] == pytest.approx(r * math.cos(t) + math.sqrt(l * l - (r * math.sin(t) - e) ** 2), abs=1e-12)
        assert x[1] == pytest.approx(e, abs=1e-12)
        assert poses[3][0] == pytest.approx(0.0, abs=1e-12)        # the slider never turns


# ---------------------------------------------------------------------------
# scissor lift, 3 stages
# ---------------------------------------------------------------------------

L, N, PHI0 = 1.0, 3, deg(15)


def scissor_mech():
    c, s = L * math.cos(PHI0), L * math.sin(PHI0)
    names = ["base", "A1", "B1", "A2", "B2", "A3", "B3", "platform"]
    A = lambda i: 1 + 2 * i              # noqa: E731
    B = lambda i: 2 + 2 * i              # noqa: E731
    pins = [K.Pin(0, A(0), (0, 0))]
    for i in range(N):
        z = i * s
        pins.append(K.Pin(A(i), B(i), (c / 2, z + s / 2)))
        if i < N - 1:
            pins += [K.Pin(B(i), A(i + 1), (0, z + s)), K.Pin(A(i), B(i + 1), (c, z + s))]
    pins.append(K.Pin(B(N - 1), 7, (0, N * s)))
    slots = [K.Slot(B(0), 0, (c, 0), (1, 0)), K.Slot(A(N - 1), 7, (c, N * s), (1, 0))]
    return K.Linkage(names, pins, slots), K.Height(7, (0, N * s), (0, 0), (0, 1))


def test_scissor_height_roller_and_platform_by_hand():
    lk, h = scissor_mech()
    s = K.Solver(lk)
    assert not s.newton
    for d in (15, 30, 45, 60, 80, 5, 1):
        phi = deg(d)
        p = s.solve(phi - PHI0)
        assert h.of(p) == pytest.approx(N * L * math.sin(phi), abs=1e-12)          # h = n L sin(phi)
        roller = K.place(p[2], (L * math.cos(PHI0), 0))
        assert roller == pytest.approx((L * math.cos(phi), 0.0), abs=1e-12)          # x = L cos(phi)
        assert p[7][0] == pytest.approx(0.0, abs=1e-12)                              # platform stays level
        top = K.place(p[5], (L * math.cos(PHI0), N * L * math.sin(PHI0)))          # A3's roller under it
        assert top == pytest.approx((L * math.cos(phi), N * L * math.sin(phi)), abs=1e-12)


def test_scissor_height_input():
    lk, h = scissor_mech()
    s = K.Solver(lk)
    v = s.value_for(h, 1.5)
    assert v + PHI0 == pytest.approx(math.asin(0.5), abs=1e-9)
    assert h.of(s.poses) == pytest.approx(1.5, abs=1e-9)
    v = s.value_for(h, 0.3)                                      # and down again
    assert math.sin(v + PHI0) * N * L == pytest.approx(0.3, abs=1e-9)
    with pytest.raises(K.Unreachable):
        s.value_for(h, 3.5)                                      # higher than 3 arms standing straight up


# ---------------------------------------------------------------------------
# parallelogram arm: through the position where its four pins are in one line
# ---------------------------------------------------------------------------

def test_parallelogram_never_crosses_over():
    t0 = deg(30)
    b = (0.5 * math.cos(t0), 0.5 * math.sin(t0))
    c = (b[0], b[1] + 0.3)
    lk = K.Linkage(["base", "lower arm", "coupler", "upper arm"],
                   [K.Pin(0, 1, (0, 0)), K.Pin(1, 2, b), K.Pin(2, 3, c), K.Pin(3, 0, (0, 0.3))])
    s = K.Solver(lk)
    for d in list(range(30, 200, 3)) + list(range(200, -200, -4)) + [90, 270, -90]:
        p = s.solve(deg(d) - t0)
        assert math.remainder(p[3][0] - p[1][0], 2 * math.pi) == pytest.approx(0.0, abs=1e-9)    # arms parallel
        assert p[2][0] == pytest.approx(0.0, abs=1e-9)         # the coupler never turns


# ---------------------------------------------------------------------------
# what the exact steps cannot split up: Newton
# ---------------------------------------------------------------------------

def triad():
    pts = dict(O=(0, 0), B=(0.1, 0), P1=(0.35, 0.2), P2=(0.55, 0.25), P3=(0.45, 0.4), G2=(0.7, 0.0), G3=(0.3, 0.7))
    lk = K.Linkage(["base", "crank", "b1", "T", "b2", "b3"],
                   [K.Pin(0, 1, pts["O"]), K.Pin(1, 2, pts["B"]), K.Pin(2, 3, pts["P1"]), K.Pin(3, 4, pts["P2"]),
                    K.Pin(4, 0, pts["G2"]), K.Pin(3, 5, pts["P3"]), K.Pin(5, 0, pts["G3"])])
    return lk


def test_triad_is_solved_by_newton_and_closes():
    lk = triad()
    s = K.Solver(lk)
    assert s.newton == [2, 3, 4, 5]
    for d in range(0, 41, 4):
        p = s.solve(deg(d))
        for c in lk.pins:
            assert max(abs(v) for v in K.residual(c, p)) < 1e-10
    # walking there in small steps and jumping there give the same answer (the same assembly mode)
    s2 = K.Solver(lk)
    p2 = s2.solve(deg(40))
    assert all(a == pytest.approx(b, abs=1e-9) for x, y in zip(p, p2) for a, b in zip(x, y))


# ---------------------------------------------------------------------------
# cylinder length as the input
# ---------------------------------------------------------------------------

def test_cylinder_length_drives_the_crank_by_law_of_cosines():
    lk, b, c, _ = four_bar()
    s = K.Solver(lk)
    # a cylinder from the base point G to the crank point b: |G b(theta)| = length
    g = (0.0, -0.3)
    m = K.Distance(0, g, 1, b)
    target = 0.35
    v = s.value_for(m, target)
    # law of cosines in the triangle O, G, B: target^2 = 0.3^2 + a^2 - 2 * 0.3 * a * cos(angle GOB)
    ang = math.acos((0.3 ** 2 + A_ ** 2 - target ** 2) / (2 * 0.3 * A_))
    th = -math.pi / 2 + ang                              # B on the side the CAD crank is on (counter-clockwise)
    assert v + TH0 == pytest.approx(th, abs=1e-9)


# ---------------------------------------------------------------------------
# state, set-up checks, pins from round faces
# ---------------------------------------------------------------------------

def test_state_round_trip():
    lk, _h = scissor_mech()
    s = K.Solver(lk)
    s.solve(deg(20))
    s2 = K.Solver(lk)
    s2.set_state(*s.state())
    assert all(a == pytest.approx(b, abs=1e-12) for x, y in zip(s.poses, s2.poses) for a, b in zip(x, y))


def test_setup_errors():
    with pytest.raises(K.SetupError, match="Not enough"):
        K.Linkage(["base", "a", "b"], [K.Pin(0, 1, (0, 0)), K.Pin(1, 2, (1, 0))])
    with pytest.raises(K.SetupError, match="Not connected"):
        K.Linkage(["base", "a", "b", "c"], [K.Pin(0, 1, (0, 0)), K.Pin(2, 3, (1, 0)), K.Pin(2, 3, (2, 0))])
    with pytest.raises(K.SetupError, match="sit on the base"):
        K.Linkage(["base", "a", "b"], [K.Pin(0, 1, (0, 0)), K.Pin(1, 2, (1, 0))], input=("pin", 1))
    # a four-bar with a fifth link from the coupler to the base: locked
    lk, b, c, _ = four_bar()
    extra = K.Linkage(lk.names + ["strut"], lk.pins + [K.Pin(2, 4, (0.25, 0.2)), K.Pin(4, 0, (0.1, 0.4))])
    with pytest.raises(K.SetupError, match="cannot move"):
        K.Solver(extra)


def test_find_pins_rigid_groups_and_merge():
    pts = [[(0, 0)], [(0, 0), (1, 0), (0.5, 0.5)], [(1, 0), (2, 0)], [(2, 0), (3, 3)], [(1, 0), (2, 0)]]
    pins = K.find_pins(pts, 1e-6)
    assert {(p.a, p.b) for p in pins} == {(0, 1), (1, 2), (2, 4), (2, 3), (3, 4)}      # chains on shared points
    allp = K.find_pins(pts, 1e-6, chain=False)
    # links 2 and 4 share two points: one rigid body
    groups = K.rigid_groups(5, allp, 1e-6)
    assert groups[0] == 0 and groups[2] == groups[4] and len(set(groups)) == 4
    names, merged = K.merge(["base", "a", "b", "c", "d"], allp, groups, 1e-6)
    assert names[groups[2]] == "b + d"
    assert not any(p.a == p.b for p in merged)
    assert len(merged) == 3            # base-a, a-(b+d), (b+d)-c


def test_scissor_layout_from_round_faces():
    c, s = L * math.cos(PHI0), L * math.sin(PHI0)
    # base: fixed pin; A1: base pin, centre, top; B1: roller, centre, top; ... platform: pin
    pts = [[(0, 0)]]
    for i in range(N):
        z = i * s
        pts.append([(0, z), (c / 2, z + s / 2), (c, z + s)])          # A arms
        pts.append([(c, z), (c / 2, z + s / 2), (0, z + s)])          # B arms (bottom end: roller axle)
    pts.append([(0, N * s), (0.3, N * s + 0.05)])                     # platform: pin + a hole elsewhere
    pins = K.find_pins(pts, 1e-6)
    lay = K.scissor(len(pts), pins, pts, platform=7, tol=1e-6)
    assert lay.stages == [(1, 2), (3, 4), (5, 6)]
    assert sorted((sl.link, sl.guide) for sl in lay.slots) == [(2, 0), (5, 7)]
    lk = K.Linkage(["base", "A1", "B1", "A2", "B2", "A3", "B3", "platform"], pins, lay.slots,
                   input=("pin", lay.input_pin))
    sol = K.Solver(lk)
    sol.solve(deg(30) - PHI0)
    assert lay.height.of(sol.poses) == pytest.approx(N * L * math.sin(deg(30)), abs=1e-12)


def test_scissor_turning_back_near_flat_keeps_every_stage():
    """Regression: down to 2° (arms nearly flat), then up again – a stage folded back (one step of history
    picked the answer nearest the last position; near-flat arms move further per step than the two answers
    lie apart)."""
    lk, h = scissor_mech()
    s = K.Solver(lk)
    for d in (15, 30, 5, 2, 60, 3, 75):
        s.solve(deg(d) - PHI0)
        assert h.of(s.poses) == pytest.approx(N * L * math.sin(deg(d)), abs=1e-9)


def test_scissor_random_walk_never_folds():
    import random
    rnd = random.Random(14)
    lk, h = scissor_mech()
    s = K.Solver(lk)
    for _ in range(300):
        d = rnd.uniform(1.5, 88.0)
        s.solve(deg(d) - PHI0)
        assert h.of(s.poses) == pytest.approx(N * L * math.sin(deg(d)), abs=1e-9)
