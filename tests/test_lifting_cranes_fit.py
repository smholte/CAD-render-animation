"""Task 0349 (Lifting makers): the built-in mobile and knuckle-boom cranes' masses fit their SAMPLE charts.

0348 found AT-40's carrier centre of gravity 4.2 m forward of the slew axis, past its front outrigger pads (the pads
stood symmetric round the slew axis, the charts' tipping assumed the carrier on it): C5 said "outside the outriggers"
at 96 % of the chart and an outrigger lifted at 6 t. Now the outriggers stand at the carrier's ends, a cab counts as
mostly air, and the charts' tipping uses the file's own centres of gravity over the real base – so a load the chart
allows never puts the crane's centre of gravity outside its outriggers, at any slew angle.
"""

from __future__ import annotations

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_path as P, lifting_reach as LR
from fresing_render.lifting_model import charts as K, classes as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, "fresing_render", "data", "lifting")
NAMES = [n for n, c in C.CLASSES.items() if c.kind in ("AT", "KB")]


def _crane(name):
    it = LL.read_item(os.path.join(LIB, name))
    poses = {p["name"]: dict(p["values"]) for p in it.data["rig"]["poses"]}
    return it, LL.charts_of(it), poses


@pytest.mark.parametrize("name", NAMES)
def test_carrier_and_slew_axis_inside_the_base(name):
    d = json.load(open(os.path.join(LIB, name, f"{name}.json"), encoding="utf-8"))
    o = d["outriggers"]
    cx, a = o["centre"][0], o["a"]
    own = "carrier" if "carrier" in d["cog"] else "truck"
    assert abs(d["cog"][own][0] - cx) < 0.8 * a, (name, d["cog"][own], o)          # well inside, not on the edge
    assert abs(0.0 - cx) < 0.8 * a, (name, o)                                       # the slew axis too


@pytest.mark.parametrize("name", NAMES)
def test_a_charted_load_keeps_the_crane_on_its_outriggers(name):
    """At 100 % of the chart, every 30° of slew and four radii: C5 never 'outside the outriggers'; at 50 % no
    outrigger of a mobile crane lifts."""
    it, charts, poses = _crane(name)
    d, rig = it.data, LR.Rig(it.data)
    pose = poses["Working"]
    cw = next((kg for n, kg, _c, _m in P.Supports(rig, d).groups if n == "counterweight"), None)
    st = {"outriggers": LR.outrigger_spread(d, pose)}
    if cw:
        st["counterweight"] = cw
    hb = LL.hook_blocks_of(it)[0][1]
    slew = rig.role["slew"]
    tried = 0
    for s in range(0, 360, 30):
        base = dict(pose, **{slew: float(s)})
        c = rig.slew_centre(base)
        v = rig.hook(base) - c
        v[2] = 0.0
        v /= np.linalg.norm(v)
        for r in (4.0, 8.0, 14.0, 20.0):
            tgt = c + v * r * 1000.0
            tgt[2] = 2500.0
            a = LR.hook_to(rig, tgt, base, charts, st)
            if not a.ok:
                continue
            vals = dict(base, **a.values)
            ro = LR.readout(rig, vals, charts, st, hook_block_kg=hb)
            if ro.capacity is None:
                continue
            for share in (0.5, 1.0):
                load = share * ro.capacity - (0.0 if ro.chart.includes_hook_block else hb)
                rows = {x.id: x for x in P.Checks(d, charts, P.Plan(load_kg=load, hook_block_kg=hb,
                                                                     counterweight_kg=cw)).at(vals)}
                c5 = rows["C5"]
                assert c5.status != lifting.RED and "outside" not in c5.value, (name, s, r, share, c5.words)
                if share == 0.5 and C.CLASSES[name].kind == "AT":
                    assert "lifts" not in c5.words, (name, s, r, c5.words)
                tried += 1
    assert tried >= 30


def test_tip_load_by_hand():
    """A 10 t crane, its centre of gravity on the slew axis in the middle of a 4 × 4 m base, the load 5 m out: the
    resultant reaches the side edge (2 m) when P · 5 = (10 + P) · 2 → P = 6.67 t; along the diagonal the corner is
    further, so the side is the weakest."""
    got = K.tip_load([(10.0, 0.0, 0.0)], [], 5.0, (0.0, 2.0, 2.0))
    assert got == pytest.approx(20.0 / 3.0, rel=1e-9)
    # the base's centre ahead of the slew axis: the rear edge is 1 m behind it, P · 5 = (10 + P) · 1 → 2.5 t
    assert K.tip_load([(10.0, 0.0, 0.0)], [], 5.0, (1.0, 2.0, 3.0)) == pytest.approx(2.5, rel=1e-9)
    # the crane alone outside its base: 0
    assert K.tip_load([(10.0, 3.0, 0.0)], [], 5.0, (0.0, 2.0, 2.0)) == 0.0


def test_a_cab_counts_as_mostly_air():
    from fresing_render.lifting_model import common
    assert common._weight("CARRIER CAB") == common.HOLLOW_SHARE
    assert common._weight("OPERATOR CAB WINDOW") == common.HOLLOW_SHARE
    assert common._weight("ENGINE BONNET") == common.HOLLOW_SHARE
    assert common._weight("CABLE GUIDE") == 1.0 and common._weight("CHASSIS FRAME") == 1.0
