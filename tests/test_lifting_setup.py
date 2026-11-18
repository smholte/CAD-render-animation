"""The Check step of "Set up a crane" (task 0203): ``core/lifting_setup`` – plain Python, no Blender.

The 12 built-in cranes pass every check; each check finds a fault planted in a copy of a built-in and names the step
that mends it."""

from __future__ import annotations

import copy
import json
import os

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_reach as LR, lifting_setup as S
from fresing_render.lifting_model import classes as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")


def data_of(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def joint(d, name):
    return next(j for j in d["rig"]["joints"] if j["name"] == name)


def red(problems):
    return [p for p in problems if p.severity == lifting.RED]


def steps(problems):
    return {p.step for p in problems}


@pytest.mark.parametrize("name", list(C.CLASSES))
def test_the_built_in_cranes_pass(name):
    ps = S.check(data_of(name))
    assert not red(ps), [(p.step, p.text) for p in ps]
    assert not ps, [(p.step, p.text) for p in ps]


def test_needed_roles_per_kind():
    assert S.needed_roles("mobile_crane") == ("slew", "luff", "telescope", "hoist")
    assert S.needed_roles("crawler_crane") == ("slew", "luff", "hoist")
    assert S.needed_roles("knuckle_boom_crane") == ("slew", "luff", "knuckle", "hoist")
    assert S.needed_roles("other_crane") == ("slew", "luff", "hoist")


# ---------------------------------------------------------------------------------------------------------------------
# planted faults

def test_a_missing_role_is_found_with_its_step():
    d = data_of("AT-40")
    for j in d["rig"]["joints"]:
        if j["name"].startswith("Telescope"):
            j["role"] = "none" if j["name"] == "Telescope" else j.get("role", "")
    ps = S.check(d)
    assert "telescope" in steps(red(ps)) and any("telescope" in p.text.lower() for p in ps)
    d = data_of("KB-50")
    joint(d, "Knuckle")["name"] = "Elbow"
    for j in d["rig"]["joints"]:
        for k in ("rides_on", "follows"):
            if j.get(k) == "Knuckle":
                j[k] = "Elbow"
    ps = S.missing_roles(d)
    assert [p.step for p in ps] == ["knuckle"]
    joint(d, "Elbow")["role"] = "knuckle"                         # given by hand: found again
    assert S.missing_roles(d) == []
    assert not red(S.check(d))
    d = data_of("CC-100")
    d["rig"]["hook"] = {"assembly": "HOOK BLOCK.ASM", "joint": "Hoist"}
    ps = S.check(d)
    assert "hook_block" in steps(red(ps))


def test_a_follower_past_its_limit_at_the_leaders_max():
    d = data_of("AT-40")
    joint(d, "Telescope 3")["limits"] = [0.0, 5000.0]
    ps = S.sweep(d)
    assert len(ps) == 1 and ps[0].step == "telescope" and ps[0].severity == lifting.RED
    assert "'Telescope 3'" in ps[0].text and "'Telescope'" in ps[0].text and "5000" in ps[0].text
    d = data_of("KB-50")
    joint(d, "Leg FR")["ratio"] = 1.5
    ps = S.check(d)
    assert {p.step for p in red(ps)} == {"jack", "poses"} and "'Leg FR'" in ps[0].text   # the poses put it there too


@pytest.mark.parametrize("name, swing, leader", [("KB-50", "Hook swing", "Main boom"),
                                                  ("KB-50", "Hook swing 2", "Knuckle"),
                                                  ("AT-100", "Hook swing", "Luff"),
                                                  ("CC-750", "Hook swing 2", "Jib")])
def test_a_hook_that_does_not_hang_plumb(name, swing, leader):
    d = data_of(name)
    joint(d, swing)["ratio"] = -0.5
    ps = [p for p in S.check(d) if p.step == "hook_block"]
    assert ps and all(p.severity == lifting.RED for p in ps)
    assert any(f"'{leader}'" in p.text and "plumb" in p.text for p in ps)


def test_a_pose_past_a_limit():
    d = data_of("AT-40")
    pose = next(p for p in d["rig"]["poses"] if p["name"] == "Working")
    pose["values"]["Luff"] = 95.0
    ps = S.pose_problems(d)
    assert [p.step for p in ps] == ["poses"] and "'Working'" in ps[0].text and "'Luff'" in ps[0].text
    d = data_of("AT-40")
    pose = next(p for p in d["rig"]["poses"] if p["name"] == "Set up")
    pose["values"]["Outriggers"] = 900.0                         # the followers too: every beam past its 772.5 mm
    ps = S.pose_problems(d)
    assert len(ps) == 8 and all(p.step == "poses" for p in ps)
    d = data_of("AT-40")
    d["rig"]["start_pose"] = "Parked"
    d["rig"]["poses"][0]["values"]["Winch"] = 3.0
    ps = S.pose_problems(d)
    assert {p.severity for p in ps} == {lifting.AMBER} and len(ps) == 2


def test_a_missing_mass_or_cog():
    d = data_of("AT-40")
    d["mass"].pop("boom")
    ps = S.check(d)
    assert [p.step for p in red(ps)] == ["masses"] and "'boom'" in ps[0].text
    d = data_of("CC-750")
    d["cog"].pop("jib")
    ps = S.mass_problems(d)
    assert len(ps) == 1 and "'jib'" in ps[0].text and "centre of gravity" in ps[0].text
    d = data_of("KB-20")
    d["mass"]["truck"] = 0.0
    assert [p.step for p in S.mass_problems(d)] == ["masses"]
    d = data_of("KB-20")
    d.pop("mass")
    ps = S.check(d)
    assert [p.step for p in red(ps)] == ["masses"] and "No masses" in ps[0].text
    # a group without parts needs no mass
    d = data_of("AT-40")
    d["rig"]["groups"]["empty"] = {"parts": [], "moves_with": None}
    assert S.mass_problems(d) == []


def test_the_centre_of_gravity_outside_the_support():
    d = data_of("AT-40")
    d["cog"]["counterweight"] = [-40.0, 0.0, 2.0]
    ps = S.check(d)
    assert [p.step for p in red(ps)] == ["masses"] and "outside its support" in ps[0].text
    assert "'Travel'" in ps[0].text and " m outside" in ps[0].text
    # a crawler: the tracks' centre lines
    d = data_of("CC-300")
    d["cog"]["counterweight"] = [-30.0, 0.0, 3.0]
    assert [p.step for p in red(S.cog_problems(d))] == ["masses"]


def test_a_refused_chart_and_no_chart():
    d = data_of("AT-40")
    d["charts"][0]["capacity"][3] = d["charts"][0]["capacity"][2] + 5.0      # rises with the radius
    ps = S.check(d)
    assert [p.step for p in red(ps)] == ["chart"] and "rises" in ps[0].text
    d = data_of("AT-40")
    d["charts"] = []
    ps = S.check(d)
    assert not red(ps)
    assert [(p.step, p.severity) for p in ps] == [("chart", lifting.AMBER)] and "Not checked" in ps[0].text
    d = data_of("KB-50")
    d["charts"][0]["radius"] = "far"
    assert [p.step for p in red(S.chart_problems(d))] == ["chart"]


def test_joints_hook_to_here_cannot_use():
    d = data_of("AT-40")
    joint(d, "Slew")["direction"] = [0.0, 0.2, 0.98]
    ps = S.check(d)
    assert any(p.step == "slew" and "up axis" in p.text for p in red(ps))
    d = data_of("AT-40")
    joint(d, "Hoist")["rides_on"] = "Gone"
    ps = S.check(d)
    assert any("'Gone'" in p.text for p in red(ps))


# ---------------------------------------------------------------------------------------------------------------------
# masses, centre of gravity, support

def test_the_cog_moves_with_its_joint():
    d = data_of("AT-40")
    m0, c0 = S.total_cog(d, {})
    assert m0 == pytest.approx(sum(d["mass"].values()))
    k = LR.Kinematics(d)
    vals = {"Slew": 90.0, "Luff": 60.0}
    m1, c1 = S.total_cog(d, vals)
    boom0 = np.array(d["cog"]["boom"])
    boom1 = k.moved("Luff", boom0 * 1000.0, vals) / 1000.0
    carrier = np.array(d["cog"]["carrier"])
    want = (c0 * m0 - boom0 * d["mass"]["boom"] + boom1 * d["mass"]["boom"]) / m0
    # the superstructure and counterweight turn with the slew too
    for g in ("superstructure", "counterweight", "hook_block"):
        p0 = np.array(d["cog"][g])
        mw = d["rig"]["groups"][g]["moves_with"]
        want += (k.moved(mw, p0 * 1000.0, vals) / 1000.0 - p0) * d["mass"][g] / m0
    assert np.allclose(c1, want, atol=1e-9)
    assert carrier[0] != c1[0]
    # file in kg and mm: the same centre of gravity in mm
    d2 = copy.deepcopy(d)
    d2["units"] = {"mass": "kg", "length": "mm"}
    d2["mass"] = {g: v * 1000.0 for g, v in d["mass"].items()}
    d2["cog"] = {g: [x * 1000.0 for x in v] for g, v in d["cog"].items()}
    m2, c2 = S.total_cog(d2, vals)
    assert m2 == pytest.approx(m0 * 1000.0) and np.allclose(c2, c1 * 1000.0, atol=1e-6)


def test_footprints():
    d = data_of("AT-40")
    o = d["outriggers"]
    fp = S.footprint(d, {"Outriggers": 500.0})
    xs, ys = [p[0] for p in fp], [p[1] for p in fp]
    assert max(xs) == pytest.approx(o["a"]) and max(ys) == pytest.approx(o["b_in"] + 2 * 0.5)
    d = data_of("CC-750")
    fp0 = S.footprint(d, {})
    fp1 = S.footprint(d, {"Travel": 4000.0})                      # the tracks move with the travel
    assert fp1[0][0] == pytest.approx(fp0[0][0] + 4.0) and fp1[0][1] == pytest.approx(fp0[0][1])
    assert max(p[1] for p in fp0) == pytest.approx(d["tracks"]["gauge"] / 2)
    # an own crane without outriggers or tracks: the footprint the set-up writes (m, model frame, counter-clockwise)
    d = data_of("KB-50")
    d.pop("outriggers")
    assert S.footprint(d) is None
    assert [(p.step, p.severity) for p in S.cog_problems(d)] == [("masses", lifting.AMBER)]
    d["footprint"] = [[-1.0, -1.3], [6.0, -1.3], [6.0, 1.3], [-1.0, 1.3]]
    assert S.footprint(d) == [(-1.0, -1.3), (6.0, -1.3), (6.0, 1.3), (-1.0, 1.3)]
    assert S.cog_problems(d) == []
    d["footprint"] = [[2.0, -1.3], [6.0, -1.3], [6.0, 1.3], [2.0, 1.3]]
    assert [p.severity for p in S.cog_problems(d)] == [lifting.RED]


def test_inside():
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 1.0), (0.0, 1.0)]
    assert S.inside((1.0, 0.5), sq) and S.inside((0.0, 0.5), sq) and S.inside((2.0, 1.0), sq)
    assert not S.inside((2.01, 0.5), sq) and not S.inside((1.0, -0.001), sq)
    ell = [(0.0, 0.0), (3.0, 0.0), (3.0, 1.0), (1.0, 1.0), (1.0, 3.0), (0.0, 3.0)]
    assert S.inside((0.5, 2.5), ell) and not S.inside((2.0, 2.0), ell)


def test_a_y_up_crane():
    """A file drawn with Y up: the centre of gravity and the plumb hook are judged along Y."""
    d = data_of("AT-40")
    Q = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]])
    for j in d["rig"]["joints"]:
        j["point"] = (Q @ np.array(j["point"])).tolist()
        j["direction"] = (Q @ np.array(j["direction"])).tolist()
    d["rig"]["hook"]["point"] = (Q @ np.array(d["rig"]["hook"]["point"])).tolist()
    d["rig"]["up_axis"] = "Y"
    d["cog"] = {g: (Q @ np.array(v)).tolist() for g, v in d["cog"].items()}
    d["outriggers"]["centre"] = [0.0, 0.0]
    assert S.sweep(d) == [] and not red(S.check(d))
    joint(d, "Hook swing")["ratio"] = -0.5
    assert "hook_block" in steps(S.sweep(d))
