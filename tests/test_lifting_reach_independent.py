"""Independent tests of Hook to here, the chart for a set-up, the readout and the load's solid (task 0201), written from
the brief by a tester who did not write the code. Plain Python, no Blender.

The reference is the maker's own kinematics (``lifting_model/classes.hook_point``) and the equipment files; truths
about the reach are worked out here from the maker's kinematics, never from ``lifting_reach`` itself."""

from __future__ import annotations

import json
import math
import os
import re

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_load as LD, lifting_reach as LR
from fresing_render.lifting_model import classes as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")
FORBIDDEN = re.compile(r"\b(" + "|".join(re.escape(w) for w in lifting.FORBIDDEN_WORDS) + r")\b", re.I)


def data_of(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def charts_of(name):
    return LL.charts_of(LL.read_item(os.path.join(BUILTIN, name)))


def poses_of(data):
    return {p["name"]: dict(p["values"]) for p in data["rig"]["poses"]}


def within_limits(rig, values):
    for n in rig.chain(rig.role["hoist"]):
        lim = rig.by[n].get("limits")
        if lim and not (lim[0] - 1e-3 <= rig.value_of(n, values) <= lim[1] + 1e-3):
            return False
    return True


def amount(reason: str) -> float:
    """The metres in 'Out of reach: (about) 1.23 m …'."""
    m = re.search(r"([0-9]+\.[0-9]+) m ", reason)
    assert m, reason
    return float(m.group(1))


# ---------------------------------------------------------------------------------------------------------------------
# Hook to here: points the crane reaches must be reached

@pytest.mark.parametrize("name", list(C.CLASSES))
def test_hook_to_the_hooks_own_place_in_every_pose(name):
    """Hook to here on the point where the hook already is (every pose of the file, the CAD pose, and the Working
    pose with the rope fully in and fully out) is reachable by definition: the answer must be ok and put the hook there.

    FAULT (CC-100, CC-300): with the rope fully in (Hoist 0) or fully out, the crawler is refused with 'Out of reach:
    0.00 m higher / lower …' – the hoist limit is checked to 1e-6 mm, finer than the solve's own rounding."""
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    cases = {"CAD": {}}
    cases.update(poses_of(d))
    work = poses_of(d).get("Working")
    if work is not None:
        lo, hi = rig.limits(rig.role["hoist"])
        cases["Working, rope in"] = dict(work, **{rig.role["hoist"]: lo})
        cases["Working, rope out"] = dict(work, **{rig.role["hoist"]: hi})
    bad = []
    for label, vals in cases.items():
        target = C.hook_point(L, vals)
        a = LR.hook_to(rig, target, vals, charts, {}, load_kg=1000.0)
        if not a.ok:
            bad.append((label, a.reason))
            continue
        full = dict(vals)
        full.update(a.values)
        err = float(np.linalg.norm(C.hook_point(L, full) - target))
        if err > 5.0 or not within_limits(rig, full):
            bad.append((label, f"{err:.1f} mm off or outside the limits"))
    assert not bad, bad


def test_a_reachable_point_near_the_low_edge_is_reached():
    """AT-40, boom 1° above level, telescope 5 m out, 38 m of rope (of 38.7 m): the maker's kinematics put the hook
    there, so Hook to here must find it.

    FAULT: refused with 'Out of reach: 0.91 m lower than the hoist rope reaches' – the telescope is only tried on a
    grid of 61 values, and the window of telescope lengths that reach this point is a few mm wide."""
    name = "AT-40"
    rig, L = LR.Rig(data_of(name)), C.layout(name)
    vals = {"Luff": 1.0, "Telescope": 5000.0, "Hoist": 38000.0}
    target = C.hook_point(L, vals)
    a = LR.hook_to(rig, target, {}, charts_of(name), {}, load_kg=1000.0)
    assert a.ok, a.reason
    assert np.linalg.norm(C.hook_point(L, a.values) - target) < 5.0


@pytest.mark.parametrize("name", ["AT-40", "AT-500", "CC-300", "CC-1600", "KB-50", "KB-200"])
def test_slew_wraps_to_the_nearest_turn_inside_the_limits(name):
    """A target behind the crane (175° round) from a slew of -170°: the answer is the turn nearest the current one
    inside the slew limits (-185° for a ±200° knuckle-boom crane, +175° for a ±180° crane)."""
    d = data_of(name)
    rig, L = LR.Rig(d), C.layout(name)
    work = poses_of(d)["Working"] if "Working" in poses_of(d) else {}
    vals = dict(work, Slew=175.0)
    target = C.hook_point(L, vals)
    a = LR.hook_to(rig, target, dict(work, Slew=-170.0), charts_of(name))
    assert a.ok, a.reason
    lo, hi = rig.limits("Slew")
    want = -185.0 if lo <= -185.0 else 175.0
    assert a.values["Slew"] == pytest.approx(want, abs=1e-6)
    full = dict(work)
    full.update(a.values)
    assert np.linalg.norm(C.hook_point(L, full) - target) < 5.0


@pytest.mark.parametrize("name", ["CC-100", "CC-750"])
def test_a_crawler_that_has_travelled_keeps_its_travel(name):
    """The crawler travelled 7 m and stands slewed: Hook to here reaches points from where it stands, without moving
    the travel, and the radius is from its slew axis where it stands."""
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    rng = np.random.default_rng(5)
    driven = [j for j in d["rig"]["joints"] if not j.get("follows") and j.get("limits") and j["name"] != "Travel"]
    done = 0
    for _ in range(12):
        vals = {j["name"]: float(rng.uniform(*j["limits"])) for j in driven}
        vals["Travel"] = 7000.0
        target = C.hook_point(L, vals)
        a = LR.hook_to(rig, target, {"Travel": 7000.0, "Slew": 10.0}, charts, {}, load_kg=1000.0)
        assert a.ok, (vals, a.reason)
        assert "Travel" not in a.values
        full = dict(a.values, Travel=7000.0)
        assert np.linalg.norm(C.hook_point(L, full) - target) < 5.0
        assert a.radius == pytest.approx(C.hook_radius_height(L, vals)[0], abs=0.005)
        done += 1
    assert done == 12


def test_no_charts_and_no_load_still_hook():
    """Hook to here needs no chart and no load: the answer is there, without a crane use."""
    name = "AT-100"
    rig, L = LR.Rig(data_of(name)), C.layout(name)
    vals = poses_of(data_of(name))["Working"]
    target = C.hook_point(L, vals)
    a = LR.hook_to(rig, target, {}, (), None, load_kg=0.0)
    assert a.ok and a.use is None and a.chart is None
    assert np.linalg.norm(C.hook_point(L, a.values) - target) < 5.0
    b = LR.hook_to(rig, target, {}, charts_of(name), {}, load_kg=0.0, hook_block_kg=0.0)
    assert b.ok and (b.use is None or b.use == 0.0)


# ---------------------------------------------------------------------------------------------------------------------
# Out of reach: by how much

def _at40_lowest_hook_at(radius_m: float) -> float:
    """AT-40: the lowest hook height (m) at a radius, from the maker's kinematics: boom level (its lower limit), the
    telescope out just far enough for the radius, the rope fully out."""
    name = "AT-40"
    L = C.layout(name)
    lo, hi = 0.0, 7733.3333
    for _ in range(80):
        m = 0.5 * (lo + hi)
        r, _z = C.hook_radius_height(L, {"Luff": 0.0, "Telescope": m})
        lo, hi = (m, hi) if r < radius_m else (lo, m)
    _r, z = C.hook_radius_height(L, {"Luff": 0.0, "Telescope": hi})
    hoist = LR.Rig(data_of(name)).limits("Hoist")[1] / 1000.0
    return z - hoist


@pytest.mark.parametrize("below", [0.5, 2.0])
def test_lower_than_the_rope_reaches_says_the_right_amount(below):
    """AT-40 at 19.91 m radius: the lowest the hook reaches there is with the boom level and the rope fully out. A
    point ``below`` m under that is out of reach by ``below`` m.

    FAULT: 0.5 m below is reported as '2.85 m lower', 2 m below as '4.35 m lower' – the amount comes from the
    telescope grid's nearest value, not the shortest boom that reaches the radius."""
    name = "AT-40"
    rig = LR.Rig(data_of(name))
    R = 19.91
    zmin = _at40_lowest_hook_at(R)
    cx = rig.slew_centre({})[0]
    a = LR.hook_to(rig, (cx + R * 1000.0, 0.0, (zmin - below) * 1000.0), {})
    assert not a.ok and "lower" in a.reason
    assert amount(a.reason) == pytest.approx(below, abs=0.05), a.reason


def _envelope(name, n1=241, n2=61, n3=13):
    """(radius, hook height with the rope in) over a grid of the boom's joints, by the maker's kinematics."""
    rig, L = LR.Rig(data_of(name)), C.layout(name)
    roles = rig.role
    l1 = rig.limits(roles["luff"])
    l2 = rig.limits(roles["second"]) if "second" in roles else None
    le = rig.limits(roles["tele"]) if "tele" in roles else None
    out = []
    for a in np.linspace(*l1, n1):
        for b in (np.linspace(*l2, n2) if l2 else [0.0]):
            for e in (np.linspace(*le, n3) if le else [0.0]):
                v = {roles["luff"]: a}
                if l2:
                    v[roles["second"]] = b
                if le:
                    v[roles["tele"]] = e
                out.append(C.hook_radius_height(L, v))
    return rig, np.array(out)


@pytest.mark.parametrize("name", ["AT-250", "CC-300", "CC-750", "KB-50"])
def test_further_out_and_closer_amounts_match_the_reach(name):
    """A point 1.5 m beyond the longest radius is '1.5 m further out'; a point at 30 % of the shortest radius is
    closer by 70 % of it (the knuckle-boom and jib cranes say 'about': within 3 %)."""
    rig, env = _envelope(name, n1=161, n2=31 if name.startswith(("CC-7", "KB")) else 1, n3=7)
    cx = rig.slew_centre({})[0]
    rmax, rmin = env[:, 0].max(), env[:, 0].min()
    zmid = 0.5 * (env[:, 1].max() + env[:, 1].min())
    a = LR.hook_to(rig, (cx + (rmax + 1.5) * 1000.0, 0.0, zmid * 1000.0), {})
    assert not a.ok and "further out" in a.reason
    assert amount(a.reason) == pytest.approx(1.5, abs=max(0.05, 0.03 * 1.5)), a.reason
    if rmin > 0.5:
        a = LR.hook_to(rig, (cx + 0.3 * rmin * 1000.0, 0.0, env[:, 1].max() * 1000.0 - 500.0), {})
        assert not a.ok and "closer" in a.reason, a.reason
        assert amount(a.reason) == pytest.approx(0.7 * rmin, rel=0.03, abs=0.05), a.reason


@pytest.mark.parametrize("name", ["AT-40", "KB-20"])
def test_out_of_reach_leaves_no_values_and_has_no_forbidden_words(name):
    rig = LR.Rig(data_of(name))
    for t in ((900000.0, 0.0, 0.0), (5000.0, 0.0, 900000.0), (5000.0, 0.0, -900000.0)):
        a = LR.hook_to(rig, t, {}, charts_of(name), {}, load_kg=1000.0)
        assert not a.ok and a.values == {} and a.reason.startswith("Out of reach")
        assert not FORBIDDEN.search(a.reason)


# ---------------------------------------------------------------------------------------------------------------------
# the chart for a set-up

def test_chart_for_values_on_and_off_the_charts():
    charts = charts_of("AT-100")
    # exactly on a chart's values: that chart, no note
    c, why = LR.chart_for(charts, 12.8, {"counterweight": 15000.0, "outriggers": 5.8})
    assert c.config["counterweight"] == 15000.0 and c.config["outriggers"] == 5.8 and "next" not in why.lower()
    # the outrigger spread as float32 stores 5.8 (5.800000190…): still that chart
    import struct
    f32 = struct.unpack("f", struct.pack("f", 5.8))[0]
    c, why = LR.chart_for(charts, 12.8, {"counterweight": 15000.0, "outriggers": f32})
    assert c.config["outriggers"] == 5.8 and "next" not in why.lower()
    # keys left out: the smallest the charts have (the safest)
    c, _ = LR.chart_for(charts, 12.0, {})
    assert c.config["counterweight"] == 0.0 and c.config["outriggers"] == 4.2
    # below every chart: none, and why
    c, why = LR.chart_for(charts, 12.0, {"outriggers": 3.0})
    assert c is None and "No chart" in why and "3 m" in why
    for text in (why,):
        assert not FORBIDDEN.search(text)


def test_chart_for_a_value_above_every_chart_says_so():
    """A counterweight above every chart's (12 t on an AT-40 whose charts have 0, 4 and 8 t) takes the 8 t chart – the
    next safer one. The note must not call 12 t a value 'between the charts' values'.

    FAULT: 'The counterweight 12 t lies between the charts' values: the 8 t chart is the next safer one.'"""
    charts = charts_of("AT-40")
    c, why = LR.chart_for(charts, 10.8, {"counterweight": 12000.0, "outriggers": 6.0})
    assert c is not None and c.config["counterweight"] == 8000.0
    assert "8 t" in why and "12 t" in why
    assert "between" not in why, why


def test_luffing_jib_chart_only_at_its_boom_angle():
    """CC-750's jib charts are for the main boom at 80° (``jib_charts_boom_angle``). With the boom at another angle the
    jib chart's capacity does not hold: the readout and Hook to here must not give a crane use from it without saying
    so (no capacity, or a note naming the boom angle).

    FAULT: at a boom angle of 77.5° (Hook to here) or 70° (posed by hand) the 80° jib chart's capacity is used and the
    crane use shown as if it applied."""
    name = "CC-750"
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    assert d["limits"]["jib_charts_boom_angle"] == 80.0

    def says_angle(text):
        return bool(re.search(r"\b80\s*°|boom angle", text))

    # posed by hand: boom at 70°, the jib turned so the radius lies inside the 42 m jib chart's rows
    chart42 = next(c for c in charts if c.config.get("jib") == 42.0 and c.config["counterweight"] == 160000.0)
    lo, hi = chart42.radius[0], chart42.radius[-1]
    found = None
    for jib in np.linspace(*rig.limits("Jib"), 121):
        vals = {"Luff": 70.0 - rig.th0, "Jib": float(jib), "Hoist": 10000.0}
        r, _z = rig.radius_height(vals)
        if lo + 1.0 < r < hi - 1.0:
            found = vals
            break
    assert found is not None
    ro = LR.readout(rig, found, charts, {"counterweight": 160000.0}, load_kg=10000.0)
    assert abs(ro.boom_angle - 70.0) < 1e-6
    assert ro.capacity is None or says_angle(ro.chart_note + " " + ro.reason), (ro.chart_note, ro.capacity)
    # Hook to here: a point near the boom head that the boom does not reach at 80°
    vals = {"Slew": -82.15822312701653, "Luff": 5.908292899964124, "Jib": 20.568655267474618,
            "Hoist": 5194.967621407288}
    a = LR.hook_to(rig, C.hook_point(L, vals), {}, charts, {"counterweight": 160000.0}, load_kg=10000.0)
    assert a.ok
    if abs(rig.boom_angle(a.values) - 80.0) > 1e-3:
        assert a.use is None or says_angle(a.chart_note), (rig.boom_angle(a.values), a.use, a.chart_note)


# ---------------------------------------------------------------------------------------------------------------------
# the readout

def test_readout_closer_than_the_first_row_is_red_with_the_reason():
    """KB-20 folded in close: the radius is shorter than the chart's first row – no capacity, red, with the reason."""
    name = "KB-20"
    rig, charts = LR.Rig(data_of(name)), charts_of(name)
    vals = {"Main boom": 55.0, "Knuckle": 40.0, "Extension": 0.0, "Hoist": 500.0}
    setup = {"outriggers": 5.2}
    r, _z = rig.radius_height(vals)
    ch, _ = LR.chart_for(charts, rig.boom_length(vals), setup)
    assert ch is not None and r < ch.radius[0]
    ro = LR.readout(rig, vals, charts, setup, load_kg=500.0)
    assert ro.capacity is None and ro.status == lifting.RED and ro.words == lifting.STATUS_WORDS[lifting.RED]
    assert "closer" in ro.reason and not FORBIDDEN.search(ro.reason)


@pytest.mark.parametrize("name", ["AT-500", "CC-1600", "KB-200"])
def test_readout_sums_the_gross_load(name):
    """gross = load x contingency + rigging (0) + hook block (unless the chart includes it) – the same as
    ``lifting.crane_use`` and ``lifting_load.gross``."""
    d = data_of(name)
    rig, charts = LR.Rig(d), charts_of(name)
    vals = poses_of(d)["Working"]
    ro = LR.readout(rig, vals, charts, None, load_kg=4000.0, contingency=1.25, hook_block_kg=900.0)
    if ro.chart is None:          # (KB-200's jib charts are for another boom angle: the readout must say so. Task
        assert ro.reason.startswith("No chart"), ro.reason   # 0238: a skip here filled a CI group's one allowed skip)
        return
    g = LD.gross(4000.0, 1.25, 900.0, ro.chart.includes_hook_block)
    assert ro.gross == pytest.approx(g.total)
    ref = lifting.crane_use(5000.0, ro.radius, ro.chart, hook_block=900.0)
    assert ro.use == ref.use and ro.status == ref.status


# ---------------------------------------------------------------------------------------------------------------------
# the load's solid

def _tube(r, h, n=128, caps=False):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    bot = np.c_[r * np.cos(t), r * np.sin(t), np.zeros(n)]
    top = np.c_[r * np.cos(t), r * np.sin(t), np.full(n, h)]
    P = np.r_[bot, top, [[0, 0, 0], [0, 0, h]]]
    T = []
    for i in range(n):
        j = (i + 1) % n
        T += [(i, j, n + j), (i, n + j, n + i)]
        if caps:
            T += [(2 * n, j, i), (2 * n + 1, n + i, n + j)]
    return P, np.array(T)


def test_an_open_tube_is_not_a_closed_solid():
    """A pipe drawn as a surface without end caps (a duct, a sheet-metal tube) is not a closed solid: the brief says it
    falls back to its box and is named. With the caps it is a closed solid of volume pi r^2 h.

    FAULT: the open tube is called closed (its faces' area vectors add up to nothing, so moving the origin does not
    change the 'volume'), with a volume of 2/3 of the closed one."""
    P, T = _tube(0.5, 2.0, caps=True)
    s = LD.solid(P, T)
    assert s.closed and s.volume == pytest.approx(math.pi * 0.25 * 2.0, rel=1e-3)
    P, T = _tube(0.5, 2.0, caps=False)
    s = LD.solid(P, T)
    assert not s.closed, f"open tube taken for a closed solid of {s.volume:.4f} m³"


def test_a_box_with_two_opposite_faces_missing_is_not_closed():
    """FAULT (same cause): a box with no top and no bottom is taken for a closed solid."""
    lo, hi = np.zeros(3), np.array([2.0, 1.0, 0.5])
    xs = [lo[0], hi[0]]
    ys = [lo[1], hi[1]]
    zs = [lo[2], hi[2]]
    P = np.array([(x, y, z) for z in zs for y in ys for x in xs])
    quads = [(0, 1, 5, 4), (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)]          # the four sides only
    T = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))])
    assert not LD.solid(P, T).closed


def test_a_shifted_scaled_closed_solid():
    """A closed box far from the origin: volume and centroid exact; a box turned inside out gives the same."""
    lo, hi = np.array([100.0, -50.0, 20.0]), np.array([103.0, -49.0, 20.5])
    P = np.array([(x, y, z) for z in (lo[2], hi[2]) for y in (lo[1], hi[1]) for x in (lo[0], hi[0])])
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)]
    T = np.array([t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))])
    for tris in (T, T[:, ::-1]):
        s = LD.solid(P, tris)
        assert s.closed and s.volume == pytest.approx(1.5, rel=1e-9)
        assert np.allclose(s.centroid, 0.5 * (lo + hi), atol=1e-9)


def test_combine_and_gross_sums():
    m, c = LD.combine([(1000.0, (0, 0, 0)), (3000.0, (4, 0, 0))])
    assert m == 4000.0 and np.allclose(c, (3, 0, 0))
    g = LD.gross(2000.0, 1.3, 450.0)
    assert g.factored == pytest.approx(2600.0) and g.total == pytest.approx(3050.0) and g.rigging == 0.0
    g = LD.gross(2000.0, 1.3, 450.0, chart_includes_block=True)
    assert g.hook_block == 0.0 and g.total == pytest.approx(2600.0)
    assert LD.CONTINGENCY == (1.0, 1.3)
