"""The general Hook to here (task 0203): one solver for any crane rigged with roles, measured from the 3-D kinematics –
plain Python, no Blender.

The reference is 0201's class solver (``tests/lifting_reach_class.py``, kept for the tests only) and the makers' own
kinematics (``lifting_model/classes.hook_point``). On all 12 built-in cranes the general solver gives the class
solver's answer: the hook within 5 mm, the same chart, the same crane use, the same boom length; the same rig drawn
turned about up, with up along Y, shifted, with axes picked from CAD faces (1e-6 noise) or rigged as an "other crane"
with its own joint names and roles gives the same joint values.

Joint values: on the mobile and crawler cranes they agree to 1e-3° / 0.05 mm. On the knuckle-boom cranes the answer is
often the shortest extension that reaches, where the reach is a window narrower than the step of the 401 hoist values
both solvers try (36 mm on KB-50): there "reaches" turns on and off within the last hundredths of a mm of extension,
and the two solvers (whose planes differ in the last decimals: the general one measures it) stop at different points
of it. Both are equally good there – the same boom to 0.1 mm, the same chart and crane use, the hook on the point – the
lowest rope differs by up to ~35 mm and the knuckle by up to ~0.6° (measured 18 Nov 2026 on the web machine)."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import statistics
import time

import numpy as np
import pytest

from fresing_render.core import lifting_library as LL, lifting_reach as LR
from fresing_render.lifting_model import classes as C

import lifting_reach_class as K

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")


def data_of(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


_CHARTS: dict = {}


def charts_of(name):
    if name not in _CHARTS:
        _CHARTS[name] = LL.charts_of(LL.read_item(os.path.join(BUILTIN, name)))
    return _CHARTS[name]


def driven(data):
    return [j for j in data["rig"]["joints"] if not j.get("follows") and j.get("limits")]


def targets(data, n, seed):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        out.append({j["name"]: float(rng.uniform(*j["limits"])) for j in driven(data)})
    return out


def within_limits(rig, values):
    for n in rig.chain(rig.role["hoist"]):
        lim = rig.by[n].get("limits")
        if lim and not (lim[0] - 1e-3 <= float(rig.value_of(n, values)) <= lim[1] + 1e-3):
            return False
    return True


def amount(reason: str) -> float:
    m = re.search(r"([0-9]+\.[0-9]+) m ", reason)
    assert m, reason
    return float(m.group(1))


def same_chart(a, b):
    if a is None or b is None:
        return a is b
    return a.name == b.name and a.config == b.config


# ---------------------------------------------------------------------------------------------------------------------
# the 12 built-in cranes: the class solver's answers

@pytest.mark.parametrize("name", list(C.CLASSES))
def test_general_gives_the_class_solvers_answer(name):
    d = data_of(name)
    rig, L, charts = LR.Rig(d), C.layout(name), charts_of(name)
    knuckle = name.startswith("KB")
    deg_tol, mm_tol = (1.0, 50.0) if knuckle else (1e-3, 0.05)
    n, times, worst = 0, [], {}
    for vals in targets(d, 50, 11):
        T = C.hook_point(L, vals)
        start = {"Travel": vals["Travel"]} if "Travel" in vals else {}
        t0 = time.perf_counter()
        a = LR.hook_to(rig, T, start, charts, {}, load_kg=1000.0, hook_block_kg=500.0)
        times.append(time.perf_counter() - t0)
        b = K.class_hook_to(d, T, start, charts, {}, load_kg=1000.0, hook_block_kg=500.0)
        assert a.ok and b.ok, (vals, a.reason, b.reason)
        full = dict(start, **a.values)
        assert np.linalg.norm(C.hook_point(L, full) - T) < 5.0
        assert within_limits(rig, full)
        assert same_chart(a.chart, b.chart), (a.chart_note, b.chart_note)
        assert (a.use is None) == (b.use is None)
        if a.use is not None:
            assert abs(a.use - b.use) <= 1e-6
        assert abs(a.boom - b.boom) * 1000.0 <= 1.0
        assert set(a.values) == set(b.values)
        for k, v in b.values.items():
            tol = deg_tol if rig.by[k]["kind"] == "ROTATE" else mm_tol
            worst[k] = max(worst.get(k, 0.0), abs(a.values[k] - v))
            assert abs(a.values[k] - v) <= tol, (k, a.values[k], v)
        n += 1
    assert n >= 50
    # one Hook to here stays quick (the web machine: median 1–37 ms; a loose bound against a 10x slip)
    assert statistics.median(times) < 0.25


def test_the_roles_of_the_built_ins_come_from_their_names():
    for name in C.CLASSES:
        rig = LR.Rig(data_of(name))
        kind = C.kind_of(name)
        assert rig.role["slew"] == "Slew" and rig.role["hoist"] == "Hoist"
        if kind == "AT":
            assert rig.mode == "luff" and rig.role["luff"] == "Luff" and rig.role["tele"] == "Telescope"
        elif kind == "CC":
            assert rig.role["luff"] == "Luff"
            assert rig.mode == ("jib" if C.CLASSES[name].jib_cad else "luff")
        else:
            assert rig.mode == "knuckle" and rig.role["luff"] == "Main boom" and rig.role["second"] == "Knuckle"
            assert rig.role["tele"] == "Extension"
    names = {"Slew": "slew", "Luff": "luff", "Main boom": "luff", "Telescope 3": "telescope", "Jib": "jib",
             "Knuckle": "knuckle", "Extension 4": "extension", "Hoist": "hoist", "Hook swing 2": "swing",
             "Outriggers": "outrigger", "Stabiliser RL 2": "outrigger", "Jacks": "jack", "Jack FR": "jack",
             "Legs": "jack", "Leg RR": "jack", "Travel": "travel", "Track L": "track", "Counterweight": None}
    for n, r in names.items():
        assert LR.role_of({"name": n}) == r, n
    assert LR.role_of({"name": "Anything", "role": "Luff"}) == "luff"
    assert LR.role_of({"name": "Luff", "role": "none"}) is None       # an explicit role wins over the name
    assert LR.role_of({"name": "Luff", "role": ""}) == "luff"
    assert set(LR.ROLE_KEYS) == {"slew", "luff", "telescope", "jib", "knuckle", "extension", "hoist", "swing",
                                 "outrigger", "jack", "track", "travel"}


# ---------------------------------------------------------------------------------------------------------------------
# an "other crane": own names, roles given by hand

def other_from(name, drop_limits=True):
    """The built-in rigged as an "other crane": every joint renamed J00, J01 …, its role written on it."""
    d = data_of(name)
    o = copy.deepcopy(d)
    o["kind"] = "other_crane"
    ren = {j["name"]: f"J{i:02d}" for i, j in enumerate(o["rig"]["joints"])}
    for j in o["rig"]["joints"]:
        j["role"] = LR.role_of(j) or ""
        j["name"] = ren[j["name"]]
        for k in ("rides_on", "follows"):
            if j.get(k):
                j[k] = ren[j[k]]
    o["rig"]["hook"]["joint"] = ren[o["rig"]["hook"]["joint"]]
    for p in o["rig"]["poses"]:
        p["values"] = {ren[k]: v for k, v in p["values"].items()}
    if drop_limits:
        o.pop("limits")
    return d, o, ren


@pytest.mark.parametrize("name", ["KB-50", "AT-100"])
def test_an_other_crane_with_hand_roles_solves_like_the_built_in(name):
    d, o, ren = other_from(name)
    base, rig, charts = LR.Rig(d), LR.Rig(o), charts_of(name)
    assert rig.kind == "other_crane" and rig.mode == base.mode
    assert {k: ren[v] for k, v in base.role.items()} == rig.role
    # no "limits" block: the boom's angles come from the geometry
    assert rig.th0 == pytest.approx(base.th0, abs=1e-4)
    if base.second_angle({}) is not None:
        assert rig.second_angle({}) == pytest.approx(base.second_angle({}), abs=1e-4)
    for vals in targets(d, 25, 9):
        T = base.hook(vals)
        a0 = LR.hook_to(base, T, {}, charts, {}, load_kg=1000.0)
        a = LR.hook_to(rig, T, {}, charts, {}, load_kg=1000.0)
        assert a.ok == a0.ok and a.ok, (a.reason, a0.reason)
        assert {ren[k]: v for k, v in a0.values.items()} == pytest.approx(a.values, abs=1e-9)
        assert a.use == a0.use and a.boom == a0.boom


def test_an_other_crane_with_a_jib_and_no_telescope_luffs_its_jib():
    """CC-750 rigged as an "other crane": a jib and no telescope – the luffing jib's way (boom at the charts' angle)."""
    d, o, ren = other_from("CC-750", drop_limits=False)
    rig, base, charts = LR.Rig(o), LR.Rig(d), charts_of("CC-750")
    assert rig.mode == "jib" and rig.role["second"] == ren["Jib"]
    for vals in targets(d, 15, 4):
        T = base.hook(vals)
        a0 = LR.hook_to(base, T, {"Travel": vals["Travel"]}, charts, {})
        a = LR.hook_to(rig, T, {ren["Travel"]: vals["Travel"]}, charts, {})
        assert a.ok and a0.ok
        assert {ren[k]: v for k, v in a0.values.items()} == pytest.approx(a.values, abs=1e-9)


def test_a_mobile_crane_keeps_its_fly_jib():
    """A fly jib on a mobile crane is not solved: it stays at its value, the boom reaches round it."""
    d = data_of("AT-40")
    jn = d["rig"]["joints"]
    head = next(j for j in jn if j["name"] == "Hook swing")
    jn.append({"name": "Fly jib", "kind": "ROTATE", "parts": [], "point": list(head["point"]),
               "direction": [0.0, -1.0, 0.0], "rides_on": "Telescope 4", "limits": [-30.0, 0.0]})
    head["rides_on"] = "Fly jib"
    rig = LR.Rig(d)
    assert rig.mode == "luff" and rig.fly == "Fly jib" and "second" not in rig.role
    vals = {"Luff": 50.0, "Telescope": 3000.0, "Hoist": 8000.0, "Fly jib": -10.0, "Slew": 20.0}
    T = rig.hook(vals)
    a = LR.hook_to(rig, T, {"Fly jib": -10.0}, charts_of("AT-40"), {})
    assert a.ok and "Fly jib" not in a.values
    assert np.linalg.norm(rig.hook(dict(a.values, **{"Fly jib": -10.0})) - T) < 1.0


# ---------------------------------------------------------------------------------------------------------------------
# the same crane drawn another way

def moved(d, Q, t, up=None, noise=0.0, seed=0):
    d = copy.deepcopy(d)
    rng = np.random.default_rng(seed)
    for j in d["rig"]["joints"]:
        j["point"] = (Q @ np.array(j["point"]) + t).tolist()
        dd = Q @ np.array(j["direction"])
        if noise:
            dd = dd + rng.normal(0.0, noise, 3)
        j["direction"] = dd.tolist()
    d["rig"]["hook"]["point"] = (Q @ np.array(d["rig"]["hook"]["point"]) + t).tolist()
    if up:
        d["rig"]["up_axis"] = up
    return d


def rz(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


Z_TO_Y = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])      # model z -> y (up along Y)
DRAWN = {"turned 37°": (rz(37.0), np.array([1234.0, -567.0, 0.0]), None, 0.0),
         "up along Y": (Z_TO_Y @ rz(-20.0), np.array([500.0, 0.0, 800.0]), "Y", 0.0),
         "shifted": (np.eye(3), np.array([-25000.0, 4000.0, 0.0]), None, 0.0),
         "axes from CAD faces": (rz(37.0), np.zeros(3), None, 1e-6)}


@pytest.mark.parametrize("name", ["AT-40", "CC-750", "KB-50"])
@pytest.mark.parametrize("how", list(DRAWN))
def test_the_same_crane_drawn_another_way_gives_the_same_answers(name, how):
    Q, t, up, noise = DRAWN[how]
    d = data_of(name)
    base, rig, charts = LR.Rig(d), LR.Rig(moved(d, Q, t, up, noise)), charts_of(name)
    tol = (0.02, 2.0) if noise else (1e-6, 1e-5)                 # deg, mm
    for vals in targets(d, 12, 3):
        T0 = base.hook(vals)
        start = {"Travel": vals["Travel"]} if "Travel" in vals else {}
        a0 = LR.hook_to(base, T0, start, charts, {}, load_kg=1000.0)
        a = LR.hook_to(rig, Q @ T0 + t, start, charts, {}, load_kg=1000.0)
        assert a.ok and a0.ok, a.reason
        for k, v in a0.values.items():
            assert abs(a.values[k] - v) <= tol[0 if rig.by[k]["kind"] == "ROTATE" else 1], (k, a.values[k], v)
        assert a.boom == pytest.approx(a0.boom, abs=1e-3) and a.use == pytest.approx(a0.use, abs=1e-9)
        assert a.radius == pytest.approx(a0.radius, abs=1e-4 if noise else 1e-6)
        r, _z = rig.radius_height(dict(start, **a.values))
        assert r == pytest.approx(a.radius, abs=1e-3)
    # the readout's height is along the rig's up axis
    work = {p["name"]: p["values"] for p in d["rig"]["poses"]}.get("Working", {})
    r0, z0 = base.radius_height(work)
    r1, z1 = rig.radius_height(work)
    assert r1 == pytest.approx(r0, abs=1e-4 if noise else 1e-5)
    assert z1 == pytest.approx(z0 + float(t @ rig.up) / 1000.0, abs=1e-4 if noise else 1e-5)


@pytest.mark.parametrize("name", ["AT-40", "CC-750", "KB-50"])
def test_a_boom_beside_the_slew_axis(name):
    """The boom's plane 300 mm beside the slew axis (a pedestal or a side-mounted boom): every point the crane's own
    kinematics put the hook on is reached, and the slew turns the offset boom onto it."""
    d = data_of(name)
    k = LR.Kinematics(d)
    for j in d["rig"]["joints"]:
        if "Slew" in k.chain(j["name"]) and j["name"] != "Slew":
            j["point"][1] += 300.0
    d["rig"]["hook"]["point"][1] += 300.0
    rig, charts = LR.Rig(d), charts_of(name)
    assert abs(rig.plane({}).y) == pytest.approx(300.0)
    for vals in targets(d, 25, 5):
        T = rig.hook(vals)
        start = {"Travel": vals["Travel"]} if "Travel" in vals else {}
        a = LR.hook_to(rig, T, start, charts, {}, load_kg=1000.0)
        assert a.ok, (vals, a.reason)
        assert np.linalg.norm(rig.hook(dict(start, **a.values)) - T) <= 1.0
        assert within_limits(rig, dict(start, **a.values))
    # out of reach: the radius the offset boom cannot reach, in metres of radius
    lo_t, hi_t = rig.limits("Telescope") if "Telescope" in rig.by else (0.0, 0.0)
    if name == "AT-40":
        flat = rig.hook({"Telescope": hi_t, "Luff": 0.0})
        c = rig.slew_centre({})
        r_max = math.hypot(flat[0] - c[0], flat[1] - c[1])
        a = LR.hook_to(rig, (c[0] + r_max + 2000.0, c[1], flat[2] - 1000.0), {})
        assert not a.ok and "further out" in a.reason and amount(a.reason) == pytest.approx(2.0, abs=0.01)


# ---------------------------------------------------------------------------------------------------------------------
# out of reach: refused, and by how much

@pytest.mark.parametrize("how", ["as drawn", "turned 37°", "up along Y"])
def test_out_of_reach_reasons_survive_how_the_crane_is_drawn(how):
    d = data_of("AT-40")
    Q, t, up, _n = DRAWN.get(how, (np.eye(3), np.zeros(3), None, 0.0))
    rig = LR.Rig(moved(d, Q, t, up))
    L = C.layout("AT-40")
    tele = rig.limits("Telescope")[1]
    flat = C.hook_point(L, {"Telescope": tele, "Luff": 0.0})
    r_max = math.hypot(flat[0], flat[1])

    def at(p):
        return Q @ np.asarray(p, float) + t

    far = LR.hook_to(rig, at((r_max + 2000.0, 0.0, flat[2] - 1000.0)), {})
    assert not far.ok and far.values == {} and "further out" in far.reason
    assert amount(far.reason) == pytest.approx(2.0, abs=0.01)
    high = LR.hook_to(rig, at((8000.0, 0.0, 400000.0)), {})
    assert not high.ok and "higher" in high.reason and amount(high.reason) > 300.0
    low = LR.hook_to(rig, at((8000.0, 0.0, -400000.0)), {})
    assert not low.ok and "lower" in low.reason and amount(low.reason) > 300.0
    close = LR.hook_to(rig, at((300.0, 0.0, 30000.0)), {})
    assert not close.ok and close.reason.startswith("Out of reach")


@pytest.mark.parametrize("name", ["CC-750", "KB-50"])
def test_out_of_reach_on_two_turning_joints_says_about_how_much(name):
    rig = LR.Rig(data_of(name))
    a = LR.hook_to(rig, (400000.0, 0.0, 5000.0), {})
    assert not a.ok and "about" in a.reason and "further out" in a.reason and amount(a.reason) > 100.0


# ---------------------------------------------------------------------------------------------------------------------
# refusals in plain words

def _joint(d, name):
    return next(j for j in d["rig"]["joints"] if j["name"] == name)


def test_refusals_say_what_is_wrong_and_which_step_mends_it():
    d = data_of("AT-40")
    d["rig"]["joints"] = [j for j in d["rig"]["joints"] if j["name"] != "Luff"]
    for j in d["rig"]["joints"]:
        if j.get("rides_on") == "Luff":
            j["rides_on"] = "Slew"
        if j.get("follows") == "Luff":
            j["follows"] = "Slew"
    with pytest.raises(LR.ReachError, match="Luff") as e:
        LR.Rig(d)
    assert e.value.step == "luff"
    d = data_of("AT-40")
    _joint(d, "Hoist")["role"] = "none"
    with pytest.raises(LR.ReachError, match="hoist") as e:
        LR.Rig(d)
    assert e.value.step == "hoist"
    d = data_of("AT-40")
    _joint(d, "Slew")["direction"] = [0.0, math.sin(math.radians(5)), math.cos(math.radians(5))]
    with pytest.raises(LR.ReachError, match="up axis") as e:
        LR.Rig(d)
    assert e.value.step == "slew"
    d = data_of("AT-40")
    _joint(d, "Luff")["direction"] = [0.0, -math.cos(math.radians(10)), math.sin(math.radians(10))]
    with pytest.raises(LR.ReachError, match="level axis") as e:
        LR.Rig(d)
    d = data_of("KB-50")
    _joint(d, "Knuckle")["direction"] = [math.sin(math.radians(3)), -math.cos(math.radians(3)), 0.0]
    with pytest.raises(LR.ReachError, match="parallel") as e:
        LR.Rig(d)
    assert e.value.step == "knuckle"
    d = data_of("AT-40")
    _joint(d, "Telescope 3")["direction"] = [0.9, 0.0, 0.43]     # another straight line: fine
    LR.Rig(d)
    d = data_of("AT-40")
    t4 = _joint(d, "Telescope 4")                                 # a section that turns as it runs out: an arc
    t4.update(kind="ROTATE", direction=[0.0, -1.0, 0.0], ratio=0.002)
    with pytest.raises(LR.ReachError, match="straight line") as e:
        LR.Rig(d)
    assert e.value.step == "telescope"
    d = data_of("AT-40")
    d["rig"]["hook"].pop("point")
    with pytest.raises(LR.ReachError, match="hook") as e:
        LR.Rig(d)
    assert e.value.step == "hook_block"
    d = data_of("AT-40")
    _joint(d, "Telescope")["rides_on"] = "Nothing"
    with pytest.raises(LR.ReachError, match="Nothing"):
        LR.Rig(d)
    d = data_of("AT-40")
    _joint(d, "Slew")["rides_on"] = "Hoist"
    with pytest.raises(LR.ReachError, match="circle"):
        LR.Rig(d)
    d = data_of("AT-40")
    d["rig"]["up_axis"] = "X"
    with pytest.raises(LR.ReachError, match="up axis"):
        LR.Rig(d)
    for kind in ("forklift", "sling"):
        d = data_of("AT-40")
        d["kind"] = kind
        with pytest.raises(LR.ReachError, match="cranes"):
            LR.Rig(d)
    for word in ("safe", "approved", "certified"):
        for msg in ("The luff joint 'X' does not turn about a level axis",):
            assert word not in msg.lower()


def test_a_hook_swing_that_moves_nothing_and_falls_on_the_hook():
    """Own-crane files: a hook swing with no parts that only carries the hoist, a hook with its falls, limits with only
    some keys – Hook to here works the same."""
    d = data_of("AT-40")
    _joint(d, "Hook swing")["parts"] = []
    d["rig"]["hook"]["falls"] = 4
    d["limits"] = {"slew": [-180.0, 180.0]}
    rig = LR.Rig(d)
    L = C.layout("AT-40")
    for vals in targets(data_of("AT-40"), 10, 2):
        T = C.hook_point(L, vals)
        a = LR.hook_to(rig, T, {}, charts_of("AT-40"), {})
        assert a.ok and np.linalg.norm(C.hook_point(L, a.values) - T) < 5.0


# ---------------------------------------------------------------------------------------------------------------------
# the kinematics, many poses at once

@pytest.mark.parametrize("name", ["AT-500", "CC-1600", "KB-200"])
def test_batched_transforms_are_the_single_ones(name):
    d = data_of(name)
    k = LR.Kinematics(d)
    vs = targets(d, 20, 1)
    batch = {n: np.array([v[n] for v in vs]) for n in vs[0]}
    R, t = k.transforms("Hoist", batch)
    for i, v in enumerate(vs):
        M = k.motion("Hoist", v)
        assert np.allclose(R[i], M[:3, :3], atol=1e-12) and np.allclose(t[i], M[:3, 3], atol=1e-7)
    hooks = k.moved("Hoist", d["rig"]["hook"]["point"], batch)
    L = C.layout(name)
    for i, v in enumerate(vs):
        assert np.linalg.norm(hooks[i] - C.hook_point(L, v)) < 0.01      # the file keeps 4 decimals
