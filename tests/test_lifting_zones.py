"""Task 0349 (Lifting L6b) in plain Python: clearance as a distance (boxes a known gap apart, moved by a joint), the
reach of a chart, the exclusion zone's outline, the ground footprint (pads and tracks against the hand formulas) and
the plan sheet's drawings."""

from __future__ import annotations

import math
import os
import xml.dom.minidom

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_path as P, lifting_reach as LR
from fresing_render.core import lifting_zones as Z

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "fresing_render", "data", "lifting")


def _box(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    v = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    t = [(0, 1, 3), (0, 3, 2), (4, 6, 7), (4, 7, 5), (0, 4, 5), (0, 5, 1), (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4),
         (1, 5, 7), (1, 7, 3)]
    return v, np.array(t)


def _body(name, lo, hi, kind="crane", joint="J"):
    tree, a, b = Z.tree_of(*_box(lo, hi))
    return Z.Body(name, kind, joint, tree, a, b)


def _obst(name, lo, hi):
    tree, a, b = Z.tree_of(*_box(lo, hi))
    return Z.Obstacle(name, tree, a, b)


def _slide(joint, values):
    M = np.eye(4)
    M[0, 3] = values.get(joint, 0.0)
    return M


def test_clearance_is_the_gap_and_follows_the_joint():
    c = Z.Clearance([_body("BOOM", (0, 0, 0), (1, 1, 1))], [_obst("WALL", (3, 0, 0), (4, 1, 1))], _slide,
                    required=1.0)
    assert c.nearest({"J": 0.0}).distance == pytest.approx(2.0, abs=0.02)
    assert c.nearest({"J": 1.5}).distance == pytest.approx(0.5, abs=0.02)
    assert c.nearest({"J": -10.0}).distance >= Z.FAR / 2                   # beyond the search: nothing near
    r = c.row({"J": 0.0})
    assert r.id == "CLR" and r.status == lifting.OK and r.use == pytest.approx(0.5, rel=0.02)
    assert "BOOM" in r.words and "WALL" in r.words and "1.00 m needed" in r.words
    assert c.row({"J": 1.5}).status == lifting.RED
    far = c.row({"J": -10.0})
    assert far.status == lifting.OK and "more than" in far.value
    # never more than the truth (a lower bound)
    for x in np.linspace(-1.0, 1.9, 13):
        assert c.nearest({"J": float(x)}).distance <= (2.0 - x) + 1e-9


def test_amber_from_the_crane_limit():
    c = Z.Clearance([_body("BOOM", (0, 0, 0), (1, 1, 1))], [_obst("WALL", (3, 0, 0), (4, 1, 1))], _slide,
                    required=1.0)
    # use = 1 / d: amber from 75 % (d ≤ 1.33 m), red above 100 % (d < 1 m)
    assert c.row({"J": 2.0 - 1.5}).status == lifting.OK
    assert c.row({"J": 2.0 - 1.2}).status == lifting.AMBER
    assert c.row({"J": 2.0 - 0.9}).status == lifting.RED


def test_what_the_load_stands_on_does_not_count_for_it():
    floor = _obst("FLOOR", (-5, -5, -1), (5, 5, 0))
    load = _body("SKID", (0, 0, 0.0), (1, 1, 1), kind="load")
    boom = _body("BOOM", (0, 0, 0.0), (1, 1, 1), kind="crane", joint="K")
    c = Z.Clearance([load, boom], [floor], lambda j, v: _slide("J" if j == "J" else "K", v), required=1.0)
    c.leave_out_touching([{"J": 0.0, "K": 5.0}])
    assert c.ignore == {"SKID": {"FLOOR"}}                       # the boom does not stand on it: it still counts
    assert c.nearest({"J": 0.0, "K": 5.0}).body == "BOOM"


def test_reach_of_a_chart():
    ch = lifting.Chart(radius=[3.0, 5.0, 8.0, 12.0], capacity=[20000.0, 12000.0, 7000.0, 4000.0], config={})
    r = Z.reach(ch, 6000.0)
    assert r.full == 8.0 and r.amber == 5.0 and r.longest == 12.0        # 7 t × 0.75 = 5.25 < 6 t
    assert Z.reach(ch, 25000.0).full is None and "shortest" in Z.reach(ch, 25000.0).words
    assert Z.reach(None, 1.0).full is None


def test_hull_and_zone():
    h = Z.hull([(0, 0), (2, 0), (2, 2), (0, 2), (1, 1)])
    assert len(h) == 4 and Z.polygon_area(h) == pytest.approx(4.0)
    z = Z.exclusion_zone((0.0, 0.0), 3.0, [(-2, -2), (2, -2), (2, 2), (-2, 2)], [(10.0, 0.0)], load_r=1.0, margin=1.0)
    assert Z.polygon_area(z) > 0                                          # counter-clockwise
    assert Z.inside(z, (0.0, 0.0)) and Z.inside(z, (11.9, 0.0)) and not Z.inside(z, (12.2, 0.0))
    assert Z.inside(z, (0.0, 3.9)) and not Z.inside(z, (0.0, 4.2))        # the tail swing (3 m) + 1 m
    assert Z.inside(z, (-2.6, -2.6)) and not Z.inside(z, (-3.0, -3.0))     # an outrigger's corner + 1 m


def _crane(name):
    it = LL.read_item(os.path.join(LIB, name))
    poses = {p["name"]: dict(p["values"]) for p in it.data["rig"]["poses"]}
    return it.data, LL.charts_of(it), poses


def test_pads_carry_the_crane_and_its_load_as_c5():
    data, charts, poses = _crane("AT-100")
    v = dict(poses["Working"], Slew=30.0)
    plan = P.Plan(load_kg=8000.0, hook_block_kg=1000.0, allowable_pa=200e3, mat=(1.5, 1.5))
    ck = P.Checks(data, charts, plan)
    pads = Z.footprint(ck, v)
    assert [p.name for p in pads] == list(Z.PAD_NAMES)
    total = sum(m for m, _x, _y in ck.sup.items(v, ck.cw, ck.hanging_kg())) * lifting.G
    assert sum(p.force for p in pads) == pytest.approx(total, rel=1e-9)
    c5 = {r.id: r for r in ck.at(v)}["C5"]
    worst = max(pads, key=lambda p: p.force)
    assert lifting.force_t(worst.force) == pytest.approx(c5.measure, rel=1e-9)
    assert worst.use == pytest.approx(c5.use, rel=1e-9) and worst.status == c5.status
    for p in pads:
        xs = [c[0] for c in p.corners]
        assert max(xs) - min(xs) == pytest.approx(1.5)
    # no allowable: grey, the forces still there
    grey = Z.footprint(P.Checks(data, charts, P.Plan(load_kg=8000.0)), v)
    assert all(p.status == lifting.NOT_CHECKED and p.force > 0 for p in grey)


def test_tracks_in_pieces_follow_the_c6_pressure_and_the_travel():
    data, charts, poses = _crane("CC-300")
    plan = P.Plan(load_kg=10000.0, hook_block_kg=3200.0, counterweight_kg=100000.0, allowable_pa=300e3)
    ck = P.Checks(data, charts, plan)
    v = poses["Working"]
    tr = Z.footprint(ck, v, pieces=8)
    assert len(tr) == 16 and {p.kind for p in tr} == {"track"}
    c6 = {r.id: r for r in ck.at(v)}["C6"]
    top = max(p.pressure for p in tr)
    assert lifting.kPa(top) <= c6.measure + 1e-6 and lifting.kPa(top) > 0.8 * c6.measure    # pieces' middles
    moved = Z.footprint(ck, dict(v, Travel=5000.0), pieces=8)
    dx = [b.corners[0][0] - a.corners[0][0] for a, b in zip(tr, moved)]
    assert all(d == pytest.approx(5.0) for d in dx)


def test_range_curve_and_drawings():
    data, charts, poses = _crane("AT-40")
    rig = LR.Rig(data)
    v = poses["Working"]
    curve = Z.range_curve(rig, v)
    assert len(curve) > 10
    rs = [r for r, _z in curve]
    assert max(rs) > 5.0 and min(z for _r, z in curve) > 0.0
    ro = LR.readout(rig, v, charts, {"counterweight": 8000.0, "outriggers": 6.0}, load_kg=3000.0)
    re = Z.reach(ro.chart, ro.gross)
    svg = Z.range_svg(curve, list(zip(ro.chart.radius, ro.chart.capacity)), re.full, re.amber,
                      hook=(ro.radius, ro.height))
    xml.dom.minidom.parseString(svg)
    ck = P.Checks(data, charts, P.Plan(load_kg=3000.0, allowable_pa=200e3))
    view = {"slew": (0.0, 0.0), "zone": Z.exclusion_zone((0.0, 0.0), 4.0, [], [(8.0, 0.0), (0.0, 8.0)], 1.0),
            "rings": [(re.full, lifting.RED), (re.amber, lifting.AMBER)],
            "patches": [p.to_dict() for p in Z.footprint(ck, v)], "path": [(8.0, 0.0), (0.0, 8.0)],
            "obstacles": [("SHED", [(10, 10), (12, 10), (12, 12), (10, 12)])]}
    plan = Z.plan_svg(view)
    xml.dom.minidom.parseString(plan)
    page = Z.sheet_html("Lift plan <test>", [("Crane", "AT-40")], plan, svg, ck.at(v), ["SAMPLE chart"])
    assert page.startswith("<!doctype html>") and "&lt;test&gt;" in page and "Exclusion zone" in page
    for w in lifting.FORBIDDEN_WORDS:
        assert w not in page.lower()


def test_clearance_row_joins_the_checks():
    data, charts, poses = _crane("AT-40")
    seen = []

    def clr(values):
        seen.append(values)
        return P.Row("CLR", "Clearance", lifting.RED, 1.5, value="0.80 m")
    rows = {r.id: r for r in P.Checks(data, charts, P.Plan(load_kg=1000.0, clearance=clr)).at(poses["Working"])}
    assert rows["CLR"].status == lifting.RED and seen
    rows = {r.id: r for r in P.Checks(data, charts, P.Plan(load_kg=1000.0, clearance=lambda v: 1 / 0)).at(
        poses["Working"])}
    assert rows["CLR"].status == lifting.NOT_CHECKED and "division" in rows["CLR"].words
    assert P.ORDER.index("CLR") > P.ORDER.index("BACK")
    assert math.isfinite(Z.REQUIRED_DEFAULT) and "1926.1408" in Z.REQUIRED_SOURCE
