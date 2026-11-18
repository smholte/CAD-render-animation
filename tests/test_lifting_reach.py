"""Hook to here, the chart for a set-up, the readout and the load's mass and CoG (task 0201) – plain Python.

The reference is the maker's own kinematics, ``lifting_model/classes.hook_point``: for every crane class, targets made
from random joint values must be reached (the hook within 5 mm, every joint inside its limits)."""

from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_load as LD, lifting_reach as LR
from fresing_render.lifting_model import classes as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")


def data_of(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def charts_of(name):
    return LL.charts_of(LL.read_item(os.path.join(BUILTIN, name)))


def driven(data):
    return [j for j in data["rig"]["joints"] if not j.get("follows") and j.get("limits")]


def inside(rig, values):
    for n in rig.chain(rig.role["hoist"]):
        lim = rig.by[n].get("limits")
        if lim and not (lim[0] - 1e-3 <= rig.value_of(n, values) <= lim[1] + 1e-3):
            return n
    return ""


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_forward_kinematics_is_the_makers(name):
    d = data_of(name)
    rig, L = LR.Rig(d), C.layout(name)
    rng = np.random.default_rng(7)
    for _ in range(30):
        vals = {j["name"]: float(rng.uniform(*j["limits"])) for j in driven(d)}
        assert np.linalg.norm(rig.hook(vals) - C.hook_point(L, vals)) < 0.01
        r, z = rig.radius_height(vals)
        r2, z2 = C.hook_radius_height(L, vals)
        assert abs(r - r2) < 1e-5 and abs(z - z2) < 1e-5
        assert abs(rig.boom_length(vals) - C.boom_length(L, vals)) < 1e-4


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_hook_to_here_reaches_every_target(name):
    """>= 50 reachable targets per class: the solved joints put the maker's hook within 5 mm, inside the limits."""
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    rng = np.random.default_rng(11)
    n = 0
    for _ in range(55):
        vals = {j["name"]: float(rng.uniform(*j["limits"])) for j in driven(d)}
        target = C.hook_point(L, vals)
        start = {"Travel": vals["Travel"]} if "Travel" in vals else {}
        a = LR.hook_to(rig, target, start, charts, {}, load_kg=1000.0, hook_block_kg=500.0)
        assert a.ok, (vals, a.reason)
        full = dict(start)
        full.update(a.values)
        assert np.linalg.norm(C.hook_point(L, full) - target) < 5.0
        assert inside(rig, full) == ""
        # the hook hangs plumb: straight below the head sheave
        n += 1
    assert n >= 50


@pytest.mark.parametrize("name", ["AT-40", "CC-100", "CC-750", "KB-20"])
def test_out_of_reach_says_by_how_much(name):
    rig, charts = LR.Rig(data_of(name)), charts_of(name)
    far = LR.hook_to(rig, (300000.0, 0.0, 1000.0), {}, charts)
    assert not far.ok and "further out" in far.reason and far.values == {}
    high = LR.hook_to(rig, (12000.0 if name != "CC-750" else 40000.0, 0.0, 400000.0), {}, charts)
    assert not high.ok and ("higher" in high.reason or "closer" in high.reason or "further" in high.reason)
    low = LR.hook_to(rig, (12000.0 if name != "CC-750" else 40000.0, 0.0, -400000.0), {}, charts)
    assert not low.ok and "lower" in low.reason or "closer" in low.reason or "further" in low.reason
    for a in (far, high, low):
        m = float(a.reason.split(":")[1].split()[0 if "about" not in a.reason else 1]) if any(
            w in a.reason for w in ("further", "higher", "lower", "closer")) else 0.0
        assert m > 0


def test_out_of_reach_amounts_are_right_for_a_mobile_crane():
    """AT-40: the longest reach is the full boom flat; a point 2 m beyond it is 2 m out."""
    d = data_of("AT-40")
    rig, L = LR.Rig(d), C.layout("AT-40")
    tele = rig.limits("Telescope")[1]
    flat = C.hook_point(L, {"Telescope": tele, "Luff": 0.0})
    r_max = math.hypot(flat[0], flat[1])
    a = LR.hook_to(rig, (r_max + 2000.0, 0.0, flat[2] - 1000.0), {})
    assert not a.ok and "2.00 m further out" in a.reason
    # high: at a radius the hook reaches, a point 3 m above the highest hook
    best = max(C.hook_point(L, {"Telescope": tele, "Luff": th})[2]
               for th in np.linspace(0, 82, 4000) if abs(math.hypot(*C.hook_point(L, {"Telescope": tele, "Luff": th})[:2])
                                                          - 8000.0) < 3.0)
    a = LR.hook_to(rig, (8000.0, 0.0, best + 3000.0), {})
    assert not a.ok and "higher" in a.reason
    assert abs(float(a.reason.split(":")[1].split()[0]) - 3.0) < 0.02


def test_a_point_outside_the_slew_range_is_refused():
    d = data_of("AT-40")
    for j in d["rig"]["joints"]:
        if j["name"] == "Slew":
            j["limits"] = [-30.0, 30.0]
    a = LR.hook_to(LR.Rig(d), (-8000.0, 0.0, 2000.0), {})
    assert not a.ok and "slew range" in a.reason


def test_slew_is_the_nearest_turn_to_the_current_one():
    rig = LR.Rig(data_of("KB-20"))     # slew -200 … 200: 170° can also be -190°
    t = C.hook_point(C.layout("KB-20"), {"Slew": 170.0, "Main boom": 10.0, "Knuckle": 10.0, "Hoist": 500.0})
    assert abs(LR.hook_to(rig, t, {"Slew": -150.0}).values["Slew"] - (-190.0)) < 1e-6
    assert abs(LR.hook_to(rig, t, {"Slew": 150.0}).values["Slew"] - 170.0) < 1e-6


def test_lowest_use_then_shortest_boom():
    """AT-100 at 10 m radius: every boom that reaches is tried; the answer has the lowest crane use of them, and no
    shorter boom has the same use."""
    name = "AT-100"
    rig, L, charts = LR.Rig(data_of(name)), C.layout(name), charts_of(name)
    setup = {"counterweight": 30000.0, "outriggers": 7.6}
    target = np.array([10000.0, 0.0, 3000.0])
    a = LR.hook_to(rig, target, {}, charts, setup, load_kg=8000.0, hook_block_kg=1000.0)
    assert a.ok and a.use is not None
    lo, hi = rig.limits("Telescope")
    pl = rig.planar()
    for t in np.linspace(lo, hi, 300):
        s = LR._Search(rig, pl.cx + 10000.0, 3000.0)
        if s.at(float(t)):
            ch, _ = LR.chart_for(charts, pl.boom_m(float(t)), setup)
            u = lifting.crane_use(8000.0, 10.0, ch, hook_block=1000.0).use if ch is not None else None
            assert u is None or u >= a.use - 1e-9
            if u is not None and abs(u - a.use) < 1e-12:
                assert pl.boom_m(float(t)) >= a.boom - 1e-3
    # the answer is the shortest boom that reaches (the charts' first boom is too short at that height here)
    assert a.boom < pl.boom_m(hi)


def test_chart_for_takes_the_next_safer_chart_and_says_why():
    charts = charts_of("AT-40")
    c, why = LR.chart_for(charts, 10.8, {"counterweight": 6000.0, "outriggers": 5.0})
    assert c.config == {"boom": 10.8, "counterweight": 4000.0, "outriggers": 4.6}
    assert "next safer" in why and "6 t" in why and "5 m" in why
    c, why = LR.chart_for(charts, 12.0, {"counterweight": 8000.0, "outriggers": 6.0})
    assert c.config["boom"] == pytest.approx(15.44) and "next longer boom" in why
    c, why = LR.chart_for(charts, 10.8, {"counterweight": 8000.0, "outriggers": 6.0})
    assert why.startswith("Chart:") and "next" not in why
    c, why = LR.chart_for(charts, 10.8, {"counterweight": -1.0})
    assert c is None and "No chart" in why
    c, why = LR.chart_for(charts, 99.0, {})
    assert c is None and "boom" in why
    for word in lifting.FORBIDDEN_WORDS:
        assert word.lower() not in why.lower()


def test_chart_for_steps_down_when_the_file_lacks_the_combination():
    charts = charts_of("AT-500")
    have = {(c.config["counterweight"], c.config["outriggers"]) for c in charts}
    assert (165000.0, 5.4) not in have
    c, why = LR.chart_for(charts, 16.5, {"counterweight": 165000.0, "outriggers": 5.4})
    assert c is not None and (c.config["counterweight"], c.config["outriggers"]) in have
    assert c.config["counterweight"] < 165000.0 and "no chart for the set-up as chosen" in why


def test_crawler_jib_charts():
    charts = charts_of("CC-750")
    c, why = LR.chart_for(charts, 72.0, {"counterweight": 240000.0}, jib=42.0)
    assert c is not None and c.config["jib"] == 42.0
    c2, _ = LR.chart_for(charts, 72.0, {"counterweight": 240000.0})
    assert c2 is not None and c2.config.get("jib") is None


def test_jib_crane_keeps_its_boom_at_the_jib_charts_angle():
    name = "CC-750"
    rig, L, charts = LR.Rig(data_of(name)), C.layout(name), charts_of(name)
    vals = {"Luff": 80.0 - rig.th0, "Jib": -10.0, "Hoist": 20000.0, "Slew": 30.0}
    a = LR.hook_to(rig, C.hook_point(L, vals), {}, charts)
    assert a.ok and abs(rig.boom_angle(a.values) - 80.0) < 1e-6


@pytest.mark.parametrize("name", ["AT-250", "CC-300", "KB-100"])
def test_readout_is_crane_use_for_the_same_inputs(name):
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    vals = {p["name"]: p for p in d["rig"]["poses"]}["Working"]["values"]
    setup = {k: v[-1] for k, v in LR.setup_values(charts).items()}
    ro = LR.readout(rig, vals, charts, setup, load_kg=3000.0, contingency=1.1, hook_block_kg=700.0)
    r, z = C.hook_radius_height(L, vals)
    assert ro.radius == pytest.approx(r) and ro.height == pytest.approx(z)
    chart, _ = LR.chart_for(charts, C.boom_length(L, vals), setup, rig.jib_length())
    ref = lifting.crane_use(3000.0 * 1.1, r, chart, hook_block=700.0)
    assert ro.use == pytest.approx(ref.use) and ro.status == ref.status and ro.words == ref.words
    assert ro.capacity == ref.limit and ro.gross == pytest.approx(3300.0 + 700.0)
    assert ro.sample


def test_readout_past_the_last_row_is_red_with_the_reason():
    name = "AT-40"
    rig, charts = LR.Rig(data_of(name)), charts_of(name)
    ro = LR.readout(rig, {"Luff": 0.0}, charts, {}, load_kg=1000.0)     # boom flat: 10.6 m, the chart ends at 9 m
    assert ro.status == lifting.RED and ro.capacity is None and "outside the chart" in ro.reason
    ro = LR.readout(rig, {"Luff": 60.0}, [], {}, load_kg=1000.0)
    assert ro.status == lifting.RED and "no load chart" in ro.reason


def test_outrigger_spread_from_the_pose():
    d = data_of("AT-40")
    setup = {p["name"]: p for p in d["rig"]["poses"]}["Set up"]["values"]
    assert LR.outrigger_spread(d, setup) == pytest.approx(6.0, abs=1e-6)
    assert LR.outrigger_spread(d, {}) == pytest.approx(2 * d["outriggers"]["b_in"])
    assert LR.outrigger_spread(data_of("CC-100"), {}) is None


def test_a_file_without_the_joints_is_refused():
    d = data_of("AT-40")
    d["rig"]["joints"] = [j for j in d["rig"]["joints"] if j["name"] != "Luff"]
    with pytest.raises(LR.ReachError, match="Luff"):
        LR.Rig(d)
    d = data_of("AT-40")
    d["kind"] = "forklift"
    with pytest.raises(LR.ReachError):
        LR.Rig(d)


# ---------------------------------------------------------------------------------------------------------------------
# the load

def _box_mesh(lo, hi, flip=False):
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    P = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    T = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return P, (T[:, ::-1] if flip else T)


def _cylinder(r, h, n=256):
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    ring = np.c_[r * np.cos(a), r * np.sin(a)]
    P = np.vstack([np.c_[ring, np.zeros(n)], np.c_[ring, np.full(n, h)], [[0, 0, 0], [0, 0, h]]])
    T = []
    for i in range(n):
        j = (i + 1) % n
        T += [[i, j, n + j], [i, n + j, n + i], [2 * n, j, i], [2 * n + 1, n + i, n + j]]
    return P, np.array(T)


def test_solid_box_and_cylinder():
    P, T = _box_mesh((1, 2, 3), (3, 3, 7))
    s = LD.solid(P, T)
    assert s.closed and s.volume == pytest.approx(8.0) and np.allclose(s.centroid, (2, 2.5, 5))
    s2 = LD.solid(*_box_mesh((1, 2, 3), (3, 3, 7), flip=True))
    assert s2.volume == pytest.approx(8.0) and np.allclose(s2.centroid, s.centroid)
    P, T = _cylinder(0.5, 2.0)
    s = LD.solid(P, T)
    exact = math.pi * 0.25 * 2.0 * (256 / (2 * math.pi)) * math.sin(2 * math.pi / 256)
    assert s.closed and s.volume == pytest.approx(exact) and np.allclose(s.centroid, (0, 0, 1.0))


def test_an_open_surface_is_not_a_solid():
    P, T = _box_mesh((0, 0, 0), (1, 1, 1))
    s = LD.solid(P, T[:-2])                          # one side missing
    assert not s.closed


def test_combine_and_gross():
    m, c = LD.combine([(1000.0, (0, 0, 0)), (3000.0, (4, 0, 0))])
    assert m == 4000.0 and np.allclose(c, (3, 0, 0))
    g = LD.gross(10000.0, 1.1, hook_block=500.0)
    assert g.factored == pytest.approx(11000.0) and g.total == pytest.approx(11500.0) and g.rigging == 0.0
    g = LD.gross(10000.0, 1.1, hook_block=500.0, chart_includes_block=True)
    assert g.total == pytest.approx(11000.0) and g.hook_block == 0.0
    # the same sum crane_use makes
    ch = lifting.Chart(radius=[5.0, 10.0], capacity=[20000.0, 12000.0])
    r = lifting.crane_use(g.factored, 7.0, ch, hook_block=500.0)
    assert r.value == pytest.approx(LD.gross(10000.0, 1.1, hook_block=500.0).total)


def test_density_guesses():
    assert LD.density_of("paint_gloss") == LD.STEEL
    assert LD.density_of("aluminium_profile") == 2700.0
    assert LD.density_of("") == LD.STEEL
