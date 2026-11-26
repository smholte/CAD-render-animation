"""Independent tests of core/lifting_path.py (task 0348), written from the brief and the docstrings by an agent that
did not write the module. Hand-worked numbers for C5 / C6 / backward stability, the worst-moment search against the
frame-by-frame reference, the proposed steps on every built-in crane."""

import math
import os
import re
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fresing_render.core import lifting  # noqa: E402
from fresing_render.core import lifting_library as LL  # noqa: E402
from fresing_render.core import lifting_path as P  # noqa: E402
from fresing_render.core import lifting_reach as LR  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "fresing_render", "data", "lifting")
CRANES = sorted(os.listdir(ROOT))
FORBIDDEN = re.compile(r"\b(" + "|".join(re.escape(w) for w in lifting.FORBIDDEN_WORDS) + r")\b", re.I)
G = 9.80665


def crane(name):
    it = LL.read_item(os.path.join(ROOT, name))
    return it.data, LL.charts_of(it)


def poses(data):
    return {p["name"]: dict(p["values"]) for p in data["rig"]["poses"]}


def urow(cid, u, amber=0.75):
    return P.Row(cid, cid, lifting.status_of(u, amber), u)


def single(f, amber=0.75):
    count = [0]

    def at(t):
        count[0] += 1
        return [urow("C1", f(t), amber)]
    return at, count


def frames(t0, t1, step=0.01):
    return np.arange(t0, t1 + step / 2, step)


# =====================================================================================================================
# 1. search against every

SYNTH = {
    "smooth peak between keys": (lambda t: 0.5 + 0.4 * math.exp(-((t - 37.3) / 6) ** 2), [0, 25, 50, 75, 100]),
    "two peaks, higher one in another gap": (
        lambda t: 0.3 + 0.5 * math.exp(-((t - 12.7) / 3) ** 2) + 0.65 * math.exp(-((t - 81.1) / 3) ** 2),
        [0, 25, 50, 75, 100]),
    "narrow smooth red": (lambda t: 0.5 + 0.6 * math.exp(-((t - 61.7) / 1.0) ** 2), [0, 25, 50, 75, 100]),
    "sine": (lambda t: 0.5 + 0.3 * math.sin(t / 3.0), [0, 50, 100]),
    "slew past a corner": (lambda t: 0.5 + 0.45 * math.sin(math.radians(t * 3.6)) ** 2, [0, 100]),
    "peak mid-gap, both keys lower": (lambda t: 0.5 + 0.4 * math.exp(-((t - 12.5) / 2) ** 2), [0, 25]),
}


@pytest.mark.parametrize("name", list(SYNTH))
def test_search_finds_the_same_worst_as_every_frame(name):
    f, keys = SYNTH[name]
    at, n = single(f)
    fd = P.search(at, 0.0, 100.0, keys, step=0.01)
    ref = P.every(single(f)[0], frames(0, 100))
    w, r = fd.worst["C1"], ref.worst["C1"]
    assert w.status == r.status
    assert w.use == pytest.approx(r.use, abs=2e-3)
    assert abs(w.t - r.t) < 0.5
    assert fd.evaluations == n[0] <= 80              # against 10,001 frames


def test_search_peak_between_two_lower_keys():
    f = lambda t: 0.6 + 0.5 * math.exp(-((t - 31.0) / 4) ** 2)         # noqa: E731 - keys at 20, 40 are green
    at, _n = single(f)
    fd = P.search(at, 20.0, 40.0, [20, 40], step=0.01)
    assert f(20) < 0.75 and f(40) < 0.75
    assert fd.worst["C1"].status == lifting.RED
    assert fd.worst["C1"].t == pytest.approx(31.0, abs=0.05)


def test_step_function_reaches_the_high_value():
    at, _n = single(lambda t: 0.4 if t < 43.2 else 0.8)
    fd = P.search(at, 0, 100, [0, 25, 50, 75, 100], step=0.01)
    assert fd.worst["C1"].status == lifting.AMBER and fd.worst["C1"].use == pytest.approx(0.8)
    assert fd.worst["C1"].t >= 43.2


def test_constant_check_needs_no_search():
    at, n = single(lambda t: 0.6)
    fd = P.search(at, 0, 100, [0, 25, 50, 75, 100])
    assert fd.worst["C1"].use == pytest.approx(0.6)
    assert n[0] == 17                                  # 4 gaps x (3 inner + key) + end, nothing more
    assert 0 <= fd.worst["C1"].t <= 100


def test_red_band_between_grid_points_is_found():
    """A red band lasting a fifth of a step (between the grid's points) – the check is green everywhere else.
    The grid is flat there, so ``search`` does no golden search at all and reports green."""
    f = lambda t: 1.05 if 57.5 <= t <= 61.5 else 0.5   # noqa: E731
    # (worker) the app's grid has a point at least every 0.2 s (5 frames at 25 fps): ``spacing``
    fd = P.search(single(f)[0], 0, 100, [0, 25, 50, 75, 100], step=0.01, spacing=2.0)
    ref = P.every(single(f)[0], frames(0, 100))
    assert ref.worst["C1"].status == lifting.RED
    assert fd.worst["C1"].status == lifting.RED, f"search reports {fd.worst['C1'].status} at t={fd.worst['C1'].t}"


def test_rank_beats_use_and_grey_beats_green():
    def at(t):
        if 20 < t < 30:
            return [P.Row("C6", "x", lifting.NOT_CHECKED, None)]
        return [urow("C6", 0.7)]
    fd = P.search(at, 0, 100, [0, 25, 50, 100], step=0.01)
    assert fd.worst["C6"].status == lifting.NOT_CHECKED
    assert 20 < fd.worst["C6"].t < 30

    def at2(t):                     # amber at a low use beats green at a higher one (another amber_at)
        return [P.Row("C1", "x", lifting.AMBER if t > 80 else lifting.OK, 0.5 if t > 80 else 0.7)]
    assert P.search(at2, 0, 100, [0, 50, 100], step=0.01).worst["C1"].status == lifting.AMBER


def test_measure_decides_without_a_use():
    def at(t):
        r = P.Row("C5", "x", lifting.NOT_CHECKED, None)
        r.measure = 10 + 5 * math.exp(-((t - 33.3) / 4) ** 2)
        return [r]
    w = P.search(at, 0, 100, [0, 50, 100], step=0.01).worst["C5"]
    assert w.t == pytest.approx(33.3, abs=0.05) and w.measure == pytest.approx(15.0, abs=1e-3)


def test_check_present_only_at_some_moments():
    def at(t):
        out = [urow("C1", 0.5)]
        if 40 < t < 60:
            out.append(urow("C5", 0.5 + 0.4 * math.exp(-((t - 52.3) / 3) ** 2)))
        return out
    fd = P.search(at, 0, 100, [0, 50, 100], step=0.01)
    assert set(fd.worst) == {"C1", "C5"}
    assert fd.worst["C5"].t == pytest.approx(52.3, abs=0.05)
    assert fd.worst["C5"].use == pytest.approx(0.9, abs=1e-4)


def test_t0_equal_t1_and_keys_outside_and_unsorted():
    calls = []

    def at(t):
        calls.append(t)
        return [urow("C1", 0.5)]
    fd = P.search(at, 5.0, 5.0, [9, 1, 5])
    assert fd.worst["C1"].t == 5.0 and fd.evaluations == 1 and set(calls) == {5.0}
    calls.clear()
    f = lambda t: 0.5 + 0.01 * t                       # noqa: E731
    fd = P.search(lambda t: (calls.append(t), [urow("C1", f(t))])[1], 0.0, 10.0, [30, -5, 7, 3, 7])
    assert all(0.0 <= t <= 10.0 for t in calls)
    assert fd.worst["C1"].t == pytest.approx(10.0)
    assert [t for t, _s in fd.moments] == sorted(t for t, _s in fd.moments)


def test_step_rounding_and_moments():
    at, _ = single(lambda t: 0.5 + 0.4 * math.exp(-((t - 37.33) / 6) ** 2))
    fd = P.search(at, 0, 100, [0, 50, 100], step=1.0)
    assert all(float(t).is_integer() for t, _s in fd.moments)
    assert float(fd.worst["C1"].t).is_integer()
    assert fd.worst["C1"].t in (37.0, 38.0)


# =====================================================================================================================
# 2. worst_so_far, ordered, Row round trip

def test_worst_so_far():
    m = [(0.0, lifting.OK), (10.0, lifting.AMBER), (20.0, lifting.RED), (30.0, lifting.OK)]
    assert P.worst_so_far(m, 9.99) == lifting.OK
    assert P.worst_so_far(m, 10.0) == lifting.AMBER
    assert P.worst_so_far(m, 25.0) == lifting.RED
    assert P.worst_so_far(m, 100.0) == lifting.RED
    assert P.worst_so_far(list(reversed(m)), 15.0) == lifting.AMBER
    assert P.worst_so_far([], 5.0) == lifting.NOT_CHECKED


def test_ordered_follows_the_table():
    rows = {i: P.Row(i, i) for i in ("C4", "ZZ", "C1", "BACK", "C5", "SETUP", "C10", "AA")}
    ids = [r.id for r in P.ordered(rows)]
    assert ids == ["C1", "C10", "SETUP", "C5", "BACK", "C4", "AA", "ZZ"]


def test_row_round_trip():
    r = P.Row("C5", "Outriggers and mats", lifting.AMBER, 0.93, "186 kPa (19.0 t)", "200 kPa entered", "words",
              0.9, 12.25, 19.0)
    import json
    back = P.Row.from_dict(json.loads(json.dumps(r.to_dict())))
    assert back == r and back.key == r.key
    g = P.grey("C2", "why")
    assert P.Row.from_dict(g.to_dict()) == g


# =====================================================================================================================
# 3. Checks.at on the built-in cranes

def rot(xy, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return xy[0] * c - xy[1] * s, xy[0] * s + xy[1] * c


def by_id(rows):
    out = {}
    for r in rows:
        assert r.id not in out, f"two rows {r.id}"
        out[r.id] = r
    return out


AT100_SET = {"Outriggers": 1122.5, "Jacks": 427.8, "Luff": 0.0, "Telescope": 0.0, "Hoist": 0.0}


def test_c5_by_hand_on_the_at100():
    data, charts = crane("AT-100")
    slew, load = 30.0, 5000.0
    v = dict(AT100_SET, Slew=slew)
    plan = P.Plan(load_kg=load, hook_block_kg=1000.0, allowable_pa=200e3, mat=(1.5, 1.5))
    rows = by_id(P.Checks(data, charts, plan).at(v))
    # by hand: the file's groups (t, m), all but the carrier turned by the slew; the load under the hook (11.84, 0)
    items = []
    for g, m in data["mass"].items():
        x, y = data["cog"][g][:2]
        if g != "carrier":
            x, y = rot((x, y), slew)
        items.append((m * 1000.0, x, y))
    items.append((load,) + rot((11.84, 0.0), slew))
    p = sum(m for m, _, _ in items)
    xb = sum(m * x for m, x, _ in items) / p
    yb = sum(m * y for m, _, y in items) / p
    a, b = 3.6, 1.555 + 2 * 1.1225
    rs = [p / 4 * (1 + sx * xb / a + sy * yb / b) for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1))]
    assert min(rs) > 0
    rmax = max(rs)
    kpa = rmax * G / 2.25 / 1000.0
    c5 = rows["C5"]
    assert c5.measure == pytest.approx(rmax / 1000.0, rel=1e-3)
    assert c5.use == pytest.approx(kpa / 200.0, rel=1e-3)
    assert c5.status == lifting.status_of(kpa / 200.0, 0.90)
    assert f"{kpa:.0f} kPa" in c5.words and "front left" in c5.words      # +x front, +y left: (+a, +b)
    assert rows["SETUP"].status == lifting.OK


def test_c5_without_allowable_and_with_pad():
    data, charts = crane("AT-100")
    v = dict(AT100_SET, Slew=10.0)
    c5 = by_id(P.Checks(data, charts, P.Plan(load_kg=3000.0)).at(v))["C5"]
    assert c5.status == lifting.NOT_CHECKED and c5.use is None and c5.measure > 0
    assert "allowable" in c5.words
    c5 = by_id(P.Checks(data, charts, P.Plan(load_kg=3000.0, allowable_pa=150e3)).at(v))["C5"]
    assert "0.6 × 0.6 m pad" in c5.words and c5.use is not None


def test_c6_by_hand_on_the_cc300_and_travel_does_not_matter():
    data, charts = crane("CC-300")
    slew, load = 25.0, 20000.0
    plan = P.Plan(load_kg=load, allowable_pa=400e3)
    hook_xy = (28.382, 0.0)
    items = []
    for g, m in data["mass"].items():
        x, y = data["cog"][g][:2]
        if g != "lower":
            x, y = rot((x, y), slew)
        items.append((m * 1000.0, x, y))
    items.append((load,) + rot(hook_xy, slew))
    p = sum(m for m, _, _ in items)
    x = sum(m * xx for m, xx, _ in items) / p
    y = sum(m * yy for m, _, yy in items) / p
    gauge, L, w = 5.9, 7.5, 1.0
    shares = [p * (gauge / 2 + y) / gauge, p * (gauge / 2 - y) / gauge]
    e = abs(x)
    if e <= L / 6:
        pmax = max(s / (w * L) * (1 + 6 * e / L) for s in shares)
    else:
        pmax = max(2 * s / (3 * w * (L / 2 - e)) for s in shares)
    kpa = pmax * G / 1000.0
    for travel in (0.0, 4000.0, -12000.0):
        v = {"Slew": slew, "Luff": 0.0, "Hoist": 22432.8, "Travel": travel}
        c6 = by_id(P.Checks(data, charts, plan).at(v))["C6"]
        assert c6.measure == pytest.approx(kpa, rel=1e-3), travel
        assert c6.use == pytest.approx(kpa / 400.0, rel=1e-3)
        assert f"{kpa:.0f} kPa" in c6.words


def test_c1_words_and_number():
    data, charts = crane("AT-100")
    v = dict(AT100_SET, Slew=0.0, Luff=30.0)
    plan = P.Plan(load_kg=4000.0, hook_block_kg=1000.0, counterweight_kg=30000.0)
    c1 = by_id(P.Checks(data, charts, plan).at(v))["C1"]
    rig = LR.Rig(data)
    ro = LR.readout(rig, v, charts, {"counterweight": 30000.0, "outriggers": 7.6}, load_kg=4000.0,
                    hook_block_kg=1000.0)
    m = re.fullmatch(r"Crane at (\d+) % of its chart at (\d+\.\d) m – (green|amber|red), your limit is 75 %\.",
                     c1.words)
    assert m, c1.words
    assert int(m.group(1)) == round(ro.use * 100) and float(m.group(2)) == pytest.approx(ro.radius, abs=0.05)
    assert c1.use == pytest.approx(ro.use) and m.group(3) == P.COLOUR[ro.status]
    # 5,000 kg gross at 11.84 m (next longer row) – the use from the chart by hand
    chart, _n = LR.chart_for(charts, 12.8, {"counterweight": 30000.0, "outriggers": 7.6})
    i = min(k for k, r in enumerate(chart.radius) if r >= ro.radius - 1e-9)
    assert c1.use == pytest.approx(5000.0 / chart.capacity[i], rel=1e-6)
    assert f"{chart.radius[i]:g} m" in c1.limit


def test_set_up_jacks_up_and_beams_in():
    data, charts = crane("AT-100")
    plan = P.Plan(load_kg=2000.0)
    jk = data["outriggers"]["jack_joint"]
    for jack, want in ((427.8, lifting.OK), (427.8 - 4.0, lifting.OK), (0.0, lifting.RED), (300.0, lifting.RED)):
        s = by_id(P.Checks(data, charts, plan).at(dict(AT100_SET, Slew=0.0, **{jk: jack})))["SETUP"]
        assert s.status == want, (jack, s.words)
        if want == lifting.RED:
            assert "jacks are up" in s.words
    # beams half out while the plan says the full spread
    plan = P.Plan(load_kg=2000.0, spread=7.6)
    s = by_id(P.Checks(data, charts, plan).at(dict(AT100_SET, Slew=0.0, Outriggers=561.0)))["SETUP"]
    assert s.status == lifting.RED and "beams" in s.words
    # beams out to the typed spread: fine
    s = by_id(P.Checks(data, charts, plan).at(dict(AT100_SET, Slew=0.0)))["SETUP"]
    assert s.status == lifting.OK


def test_crawler_has_no_set_up_row_and_c6_not_c5():
    data, charts = crane("CC-300")
    ids = [r.id for r in P.Checks(data, charts, P.Plan(load_kg=1000.0)).at({"Hoist": 22432.8})]
    assert "SETUP" not in ids and "C5" not in ids and "C6" in ids


def test_backward_stability_grey_unless_more_counterweight():
    data, charts = crane("AT-100")
    v = dict(AT100_SET, Slew=180.0)
    for cw in (None, 0.0, 15000.0, 30000.0):
        b = by_id(P.Checks(data, charts, P.Plan(load_kg=2000.0, counterweight_kg=cw)).at(v))["BACK"]
        assert b.status == lifting.NOT_CHECKED, cw
    cw = 40000.0
    rows = by_id(P.Checks(data, charts, P.Plan(load_kg=2000.0, counterweight_kg=cw)).at(v))
    b = rows["BACK"]
    assert b.status != lifting.NOT_CHECKED
    # by hand: the crane without its load, 40 t of counterweight, slewed 180°
    items = []
    for g, m in data["mass"].items():
        x, y = data["cog"][g][:2]
        kg = cw if g == "counterweight" else m * 1000.0
        if g != "carrier":
            x, y = rot((x, y), 180.0)
        items.append((kg, x, y))
    p = sum(m for m, _, _ in items)
    x = sum(m * xx for m, xx, _ in items) / p
    y = sum(m * yy for m, _, yy in items) / p
    margin = min(1 - abs(x) / 3.6, 1 - abs(y) / 3.8)
    use = (1 - margin) / (1 - 0.15)
    assert b.use == pytest.approx(use, rel=1e-6)
    assert b.status == lifting.status_of(use, 0.75)
    assert "40.00 t" in b.words and "30.00 t" in b.words
    assert "Backward stability" in rows["C1"].words


def test_backward_stability_tips_when_the_counterweight_is_huge():
    data, charts = crane("AT-100")
    v = dict(AT100_SET, Slew=0.0)
    b = by_id(P.Checks(data, charts, P.Plan(counterweight_kg=4.0e6)).at(v))["BACK"]
    assert b.status == lifting.RED and b.use > 1.0 and "red" in b.words


def rig_check(cid, title, status, use, parts=()):
    return {"check": cid, "title": title, "status": status, "use": use, "message": "", "words": "",
            "parts": [{"title": t, "status": s, "use": u, "message": ""} for t, s, u in parts]}


def test_rigging_rows_one_per_check_the_worst():
    data, charts = crane("AT-100")
    checks = [
        rig_check("C4", "Shackles", lifting.AMBER, 0.95,
                  [("Shackle A", lifting.OK, 0.5), ("Shackle B", lifting.AMBER, 0.95)]),
        rig_check("C4", "Sling", lifting.RED, 1.2),
        rig_check("C2", "Legs", lifting.OK, 0.4),
        rig_check("C2", "Legs again", lifting.AMBER, 0.92),
    ]
    rows = P.Checks(data, charts, P.Plan(load_kg=2000.0, hung=True, rig_checks=checks)).at(dict(AT100_SET, Slew=0.0))
    r = by_id(rows)
    assert r["C4"].status == lifting.RED and r["C4"].use == pytest.approx(1.2) and "Sling" in r["C4"].words
    assert r["C2"].status == lifting.AMBER and r["C2"].use == pytest.approx(0.92)
    assert by_id(P.Checks(data, charts, P.Plan(hung=False)).at(AT100_SET))["C2"].status == lifting.NOT_CHECKED


def test_line_pull_row():
    data, charts = crane("AT-100")
    plan = P.Plan(load_kg=10000.0, line_pull=lambda g: lifting.hoist_line_pull(g, 4, 6500.0))
    c10 = by_id(P.Checks(data, charts, plan).at(dict(AT100_SET, Slew=0.0)))["C10"]
    want = lifting.hoist_line_pull(10000.0, 4, 6500.0)          # gross = the load (no hook block in the plan)
    assert c10.use is not None and c10.status != lifting.NOT_CHECKED
    assert "4 falls" in c10.words
    assert c10.use == pytest.approx(want.use, rel=1e-9)


def _all_rows():
    for n in CRANES:
        data, charts = crane(n)
        for pname, v in poses(data).items():
            for load in (0.0, 8000.0):
                for allow in (None, 180e3):
                    for mat in (None, (1.2, 1.5)):
                        plan = P.Plan(load_kg=load, allowable_pa=allow, mat=mat, hook_block_kg=500.0)
                        yield n, pname, P.Checks(data, charts, plan).at(v)


def test_every_pose_of_every_crane_gives_rows_in_plain_words():
    count = 0
    for n, pname, rows in _all_rows():
        ids = [r.id for r in rows]
        assert len(ids) == len(set(ids)), (n, pname, ids)
        assert "C1" in ids
        for r in rows:
            count += 1
            assert r.status in P.RANK, (n, r)
            assert r.words, (n, pname, r.id)
            assert not FORBIDDEN.search(r.words), (n, pname, r.words)
            assert "safe" not in r.words.lower(), (n, pname, r.words)
            assert not FORBIDDEN.search(r.value or "") and not FORBIDDEN.search(r.limit or "")
            if r.use is not None:
                assert math.isfinite(r.use)
    assert count > 500


# =====================================================================================================================
# 4. propose

def walk(rig, start, steps, n=40):
    """The hook along the steps, the joints moving linearly between a step's start and end (as keys do)."""
    now = dict(start)
    out = []
    for s in steps:
        before = dict(now)
        for i in range(n + 1):
            f = i / n
            v = dict(before)
            for k, x in s.values.items():
                v[k] = before.get(k, 0.0) + (x - before.get(k, 0.0)) * f
            out.append((s.kind, i, rig.hook(v)))
        now.update(s.values)
    return now, out


def working(name):
    data, charts = crane(name)
    p = poses(data)
    return data, charts, LR.Rig(data), dict(p.get("Working") or {})


def targets(rig, start):
    h = rig.hook(start)
    c = rig.slew_centre(start)
    r = rig.radius_height(start)[0] * 1000.0
    slewed = c + np.array([0.0, 0.9 * r, 0.0])
    slewed[2] = h[2] - 500.0
    d = h - c
    d[2] = 0.0
    closer = c + 0.7 * d
    closer[2] = h[2]
    return {"slewed": slewed, "closer": closer}


@pytest.mark.parametrize("name", CRANES)
def test_propose_ends_on_the_target(name):
    data, charts, rig, start = working(name)
    for what, tgt in targets(rig, start).items():
        pr = P.propose(rig, data, start, tgt, 2000.0, charts, None, 5000.0, 0.0)
        assert pr.ok, (what, pr.reason)
        end, _pts = walk(rig, start, pr.steps)
        assert np.linalg.norm(rig.hook(end) - tgt) < 50.0, what
        assert np.linalg.norm(rig.hook(pr.end) - tgt) < 50.0
        for s in pr.steps:
            if s.kind != "luff":               # (worker) the luff move comes in SUB pieces: their sum below
                assert P.MIN_S <= s.seconds <= P.MAX_S
            assert s.kind in ("hoist", "slew", "luff", "travel", "lower")
        luff = sum(s.seconds for s in pr.steps if s.kind == "luff")
        assert luff == 0 or P.MIN_S - 0.05 <= luff <= P.MAX_S + 0.05
        assert not FORBIDDEN.search(" ".join(pr.notes) + pr.reason)


@pytest.mark.parametrize("name", CRANES)
def test_propose_keeps_the_clearance_at_the_keys(name):
    """At the end of the hoist-clear, slew, luff and travel steps the hook is at least the clearance above the
    higher of pick and set-down point."""
    data, charts, rig, start = working(name)
    h0 = rig.hook(start)[2]
    for what, tgt in targets(rig, start).items():
        pr = P.propose(rig, data, start, tgt, 2000.0, charts, None, 5000.0, 0.0)
        assert pr.ok
        need = max(h0, tgt[2]) + 2000.0
        now = dict(start)
        for s in pr.steps:
            now.update(s.values)
            if s.kind in ("slew", "luff", "travel"):
                assert rig.hook(now)[2] >= need - 20.0, (what, s.kind, rig.hook(now)[2] - need, pr.notes)


@pytest.mark.parametrize("name", CRANES)
def test_propose_keeps_the_clearance_during_the_moves(name):
    """While the crane slews / luffs / telescopes / travels (joints moving between their keys) the hook stays at the
    clearance height – within 100 mm."""
    data, charts, rig, start = working(name)
    h0 = rig.hook(start)[2]
    for what, tgt in targets(rig, start).items():
        pr = P.propose(rig, data, start, tgt, 2000.0, charts, None, 5000.0, 0.0)
        need = max(h0, tgt[2]) + 2000.0
        _end, pts = walk(rig, start, pr.steps)
        low = min((p[2] - need for kind, _i, p in pts if kind in ("slew", "luff", "travel")), default=0.0)
        assert low >= -100.0, (what, f"the hook dips {-low:.0f} mm below the clearance height mid-step")


@pytest.mark.parametrize("name", CRANES)
def test_target_straight_below_only_hoists(name):
    data, charts, rig, start = working(name)
    tgt = rig.hook(start) - np.array([0.0, 0.0, 1000.0])
    pr = P.propose(rig, data, start, tgt, 2000.0, charts, None, 5000.0, 0.0)
    assert pr.ok, pr.reason
    assert [s.kind for s in pr.steps if s.kind not in ("hoist", "lower")] == [], \
        [(s.kind, s.values) for s in pr.steps]
    assert np.linalg.norm(rig.hook(pr.end) - tgt) < 50.0


@pytest.mark.parametrize("name", ["AT-100", "CC-300", "KB-50"])
def test_target_higher_than_the_pick(name):
    data, charts, rig, start = working(name)
    h = rig.hook(start)
    c = rig.slew_centre(start)
    d = h - c
    d[2] = 0.0
    tgt = c + 0.85 * d
    tgt[2] = h[2] + 1500.0
    pr = P.propose(rig, data, start, tgt, 1000.0, charts, None, 1000.0, 0.0)
    assert pr.ok, pr.reason
    assert np.linalg.norm(rig.hook(pr.end) - tgt) < 50.0
    assert pr.steps[-1].kind == "lower"                 # it comes down onto it from the clearance height


@pytest.mark.parametrize("name", ["AT-40", "CC-100", "KB-20"])
def test_out_of_reach_in_words(name):
    data, charts, rig, start = working(name)
    tgt = rig.slew_centre(start) + np.array([0.0, 400000.0, 0.0])
    pr = P.propose(rig, data, start, tgt, 2000.0, charts, None, 1000.0, 0.0)
    assert not pr.ok and pr.steps == [] and len(pr.reason) > 10
    assert re.search(r"\d+(\.\d+)? m", pr.reason)
    assert not FORBIDDEN.search(pr.reason)


def test_crawler_travels_only_when_needed():
    data, charts, rig, start = working("CC-300")
    h = rig.hook(start)
    near = np.array([40000.0, 0.0, h[2] - 3000.0])
    pr = P.propose(rig, data, start, near, 2000.0, charts, None, 5000.0, 0.0)
    assert pr.ok and "travel" not in [s.kind for s in pr.steps]
    far = np.array([65000.0, 0.0, h[2] - 3000.0])
    pr = P.propose(rig, data, start, far, 2000.0, charts, None, 5000.0, 0.0)
    assert pr.ok, pr.reason
    kinds = [s.kind for s in pr.steps]
    assert kinds.count("travel") == 1 and kinds[-1] == "lower"
    assert np.linalg.norm(rig.hook(pr.end) - far) < 50.0
    lo, hi = rig.limits("Travel")
    assert lo <= pr.end["Travel"] <= hi
    assert any("travels" in n for n in pr.notes)
    # past travel + reach: out of reach, no steps
    pr = P.propose(rig, data, start, np.array([140000.0, 0.0, h[2]]), 2000.0, charts, None, 5000.0, 0.0)
    assert not pr.ok and pr.steps == []


def test_mobile_crane_never_travels():
    data, charts, rig, start = working("AT-100")
    pr = P.propose(rig, data, start, rig.slew_centre(start) + np.array([80000.0, 0, 0]), 2000.0, charts)
    assert not pr.ok and not any(s.kind == "travel" for s in pr.steps)


# =====================================================================================================================
# the search on a real path: C5 along a proposed slew

def test_search_on_a_real_slew_matches_every_frame():
    data, charts, rig, start = working("AT-100")
    start = dict(start, Slew=-60.0)
    c = rig.slew_centre(start)
    r = rig.radius_height(start)[0] * 1000.0
    tgt = c + np.array([r * math.cos(math.radians(100)), r * math.sin(math.radians(100)), 0.0])
    tgt[2] = rig.hook(start)[2] - 1000.0
    pr = P.propose(rig, data, start, tgt, 1500.0, charts, None, 8000.0, 0.0)
    assert pr.ok
    keys, t, states = [0.0], 0.0, [dict(start)]
    for s in pr.steps:
        t += s.seconds * 25.0
        keys.append(t)
        states.append(dict(states[-1], **s.values))
    checks = P.Checks(data, charts, P.Plan(load_kg=8000.0, hook_block_kg=1000.0, allowable_pa=250e3,
                                           counterweight_kg=30000.0))

    def at(f):
        i = max(k for k in range(len(keys) - 1) if keys[k] <= f) if f < keys[-1] else len(keys) - 2
        a, b = states[i], states[i + 1]
        w = (f - keys[i]) / (keys[i + 1] - keys[i])
        v = {n: a.get(n, 0.0) + (b.get(n, 0.0) - a.get(n, 0.0)) * w for n in set(a) | set(b)}
        return checks.at(v)
    fd = P.search(at, 0.0, keys[-1], keys, step=0.01)
    ref = P.every(at, np.arange(0.0, keys[-1] + 0.5, 1.0))
    for cid in ("C1", "C5"):
        assert fd.worst[cid].status == ref.worst[cid].status, cid
        if ref.worst[cid].use is not None:
            assert fd.worst[cid].use >= ref.worst[cid].use - 0.005, cid
        if ref.worst[cid].measure is not None:
            assert fd.worst[cid].measure >= ref.worst[cid].measure * 0.995, cid
    assert fd.evaluations < len(ref.moments) / 5
