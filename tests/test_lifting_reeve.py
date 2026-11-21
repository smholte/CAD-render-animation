"""Task 0232: the reeved hoist rope (core/lifting_reeve.py), check C10, the rigging gear (core/lifting_gear.py) and
the cranes' reeving tables."""

import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import lifting as L
from fresing_render.core import lifting_gear as G
from fresing_render.core import lifting_library as LL
from fresing_render.core import lifting_reeve as R

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fresing_render", "data", "lifting")


@pytest.mark.parametrize("falls,head,block,dead", [(1, 1, 0, "block"), (2, 1, 1, "head"), (3, 2, 1, "block"),
                                                    (7, 4, 3, "block"), (8, 4, 4, "head"), (28, 14, 14, "head")])
def test_sheaves_and_the_dead_end(falls, head, block, dead):
    assert R.sheaves_for(falls) == (head, block, dead)
    rv = R.Reeving(falls, 0.3, 0.25, 0.06, 0.06, 0.018)
    pts = R.path(rv, (-10, 0, -5), (10, 0, 5))
    assert R.falls_of(pts) == falls
    assert pts[0][0] == "drum" and pts[-1][0] == dead
    # every head point lies on a head sheave's rope circle or is the dead end
    ys = set(np.round(R.ys(rv.head, rv.head_pitch), 9))
    for fr, p in pts:
        if fr == "head" and round(p[1], 9) in ys:
            assert math.hypot(p[0], p[2]) == pytest.approx(0.3, abs=1e-9)


def test_lead_comes_onto_the_lead_sheave_at_a_tangent():
    rv = R.Reeving(4, 0.3, 0.25, 0.06, 0.06, 0.018, drum_r=0.4)
    drum = np.array([-12.0, 0.0, -6.0])
    pts = R.path(rv, drum, -drum)
    d0 = pts[0][1] + np.array([drum[0], 0, drum[2]])                # the drum point in the head frame
    h0 = pts[1][1]
    radius = np.array([h0[0], 0, h0[2]])
    lead = h0 - d0
    assert abs(float(lead @ radius)) / (np.linalg.norm(lead) * 0.3) < 1e-6        # square to the radius


def test_payout_and_the_drum():
    assert R.payout(8, 1.0) == 8.0
    rv = R.Reeving(8, 0.22, 0.19, 0.06, 0.06, 0.020, drum_r=0.373, drum_w=0.87)
    dt = R.drum_table(rv, 40.0)
    assert dt.layers >= 2 and np.all(np.diff(dt.hoist) > 0) and np.all(np.diff(dt.angle) >= -1e-12)
    # hook 1 m up = 8 m wound: the drum turns 8 m / its rope radius, within a layer step
    a = np.interp([10.0, 11.0], dt.hoist, dt.angle)
    r_lo, r_hi = rv.drum_r + rv.rope_d / 2, dt.outside.max()
    turned = a[1] - a[0]
    assert 8.0 / r_hi - 1e-6 <= turned <= 8.0 / r_lo + 1e-6
    assert dt.outside[0] >= dt.outside[-1]                         # hook up = more rope on the drum


def test_c10_hand_case():
    """10 t on 8 falls, K 1.04: E = (1.04^8 − 1)/(1.04^8 · 8 · 0.04) = 84.16 %, line pull 1.485 t, 22.85 % of 6.5 t."""
    e = L.reeving_efficiency(8)
    assert e == pytest.approx(0.36856905 / (1.36856905 * 0.32), rel=1e-6)
    assert e == pytest.approx(0.8416, abs=1e-4)
    r = L.hoist_line_pull(10000.0, 8, 6500.0)
    assert r.check == "C10" and r.value / 1000 == pytest.approx(1.4853, abs=1e-4)
    assert r.use == pytest.approx(0.2285, abs=1e-4) and r.status == L.OK
    assert L.hoist_line_pull(10000.0, 1, 6500.0).status == L.RED           # 10.4 t on one fall
    assert L.hoist_line_pull(10000.0, 8).status == L.NOT_CHECKED
    assert R.line_pull(10000.0, 8) == pytest.approx(r.value)
    assert L.reeving_efficiency(1, k=1.0) == 1.0
    assert "API RP 9B" in L.REEVING_SOURCE and L.LEAVES_OUT["C10"]
    assert not any(w.lower() in r.message.lower() for w in L.FORBIDDEN_WORDS)


def test_built_in_gear_reads_without_problems():
    items = G.builtins()
    kinds = {it.kind for it in items}
    assert kinds == {"sling", "shackle", "spreader_beam", "lifting_frame"}
    for it in items:
        assert it.ok and it.sample and it.path.startswith("builtin:"), it.problems
        g = G.gear_of(it)
        assert not g.problems and g.wll > 0, (it.name, g.problems)
    lf = G.gear_of(G.find("builtin:LF-20"))
    assert len(lf.bottom) == 4 and len(lf.top) == 2
    assert G.gear_of(G.find("builtin:SH-8.5")).wll == pytest.approx(8500.0)
    assert G.shackle_for(7000.0).path == "builtin:SH-8.5"
    assert G.sling_for(7000.0, 4).path == "builtin:CH8-4L-16"
    ch = G.gear_of(G.find("builtin:CH8-2L-16"))
    assert ch.sling_mass([3.0, 3.0]) == pytest.approx(6 * 5.7 + ch.master_link)


def test_own_gear_file_is_checked():
    d = LL.new_item("sling", "X", "My sling", "t", "m", wll=5.0, rigging={"material": "rope", "legs": 5})
    g = G.gear_of(LL.from_data(d))
    assert any("material" in p for p in g.problems) and any("legs" in p for p in g.problems)
    d = LL.new_item("spreader_beam", "S", "My beam", "t", "m", wll=5.0, rigging={"top": [[0, 0]], "bottom": []})
    assert G.gear_of(LL.from_data(d)).problems


@pytest.mark.parametrize("name", ["AT-40", "AT-100", "CC-1600", "KB-20"])
def test_cranes_carry_their_reeving(name):
    with open(os.path.join(DATA, name, f"{name}.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    rv = d["reeving"]
    falls = d["hook_blocks"][0]["falls"]
    r = R.from_data(rv, falls)
    assert 0 < r.block_r <= r.head_r and r.rope_d > 0 and rv["drum"]["joint"] == "Slew"
    assert r.head * r.head_pitch < 3.0
    if name == "AT-100":
        assert (r.falls, r.head, r.block) == (8, 4, 4)
