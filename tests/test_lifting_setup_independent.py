"""Set up a crane (task 0203) – the independent tester's cases for the plain-Python half: the Check
(``core/lifting_setup``) and Hook to here on any crane (``core/lifting_reach``), written from the brief.

Hand-made "other crane" rigs (made-up numbers), and copies of the built-in (invented) cranes' files with what an own
crane's file may lack or a hand-edited file may hold: joints without limits, no hook swing, no chart, odd values.
The brief: refusals in plain words, never a traceback; an own crane without its chart is never "within limits" and
shows "Not checked – no chart"."""

from __future__ import annotations

import copy
import json
import math
import os

import numpy as np
import pytest

from fresing_render.core import lifting, lifting_library as LL, lifting_reach as LR, lifting_setup as LS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = os.path.join(ROOT, "fresing_render", "data", "lifting")


def data_of(name):
    with open(os.path.join(BUILTIN, name, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def joint(d, name):
    return next(j for j in d["rig"]["joints"] if j["name"] == name)


def charts(d):
    return LL.charts_of(LL.from_data(d))


def texts(ps):
    return [(p.step, p.severity, p.text) for p in ps]


# ---------------------------------------------------------------------------------------------------------------------
# a hand-made "other crane": names that say nothing, roles by hand (mm, degrees)

def other(**over):
    """A pedestal crane: slew about z at the origin, a boom pivot 3 m up and 1 m out, a 20 m boom drawn level along
    +x, a hook swing at the head that follows the boom (ratio -1), the hoist straight down."""
    joints = [
        {"name": "A", "kind": "ROTATE", "role": "slew", "parts": ["P1"], "point": [0, 0, 0], "direction": [0, 0, 1],
         "limits": [-170, 170]},
        {"name": "B", "kind": "ROTATE", "role": "luff", "parts": ["P2"], "point": [1000, 0, 3000],
         "direction": [0, -1, 0], "rides_on": "A", "limits": [-5, 80]},
        {"name": "C", "kind": "ROTATE", "role": "swing", "parts": [], "point": [21000, 0, 3000],
         "direction": [0, -1, 0], "rides_on": "B", "follows": "B", "ratio": -1.0},
        {"name": "D", "kind": "SLIDE", "role": "hoist", "parts": ["P4"], "point": [21000, 0, 3000],
         "direction": [0, 0, -1], "rides_on": "C", "limits": [0, 40000]},
    ]
    d = {"format": LL.FORMAT, "format_version": "1.0", "kind": "other_crane", "class": "X", "name": "Made up",
         "units": {"mass": "t", "length": "m"}, "sample": False,
         "rig": {"units": "mm", "joints": joints, "hook": {"assembly": "P4", "point": [21000, 0, 2000],
                                                          "joint": "D"},
                 "poses": [{"name": "Rest", "values": {}}], "start_pose": "Rest",
                 "groups": {"base": {"parts": ["P1"], "moves_with": None}}},
         "mass": {"base": 50.0}, "cog": {"base": [0.0, 0.0, 1.0]},
         "footprint": [[-3, -3], [3, -3], [3, 3], [-3, 3]],
         "charts": [{"config": {"boom": 20.0}, "radius": [5, 10, 15, 21], "capacity": [10, 6, 4, 3]}]}
    for k, v in over.items():
        d[k] = v
    return d


def test_a_hand_made_other_crane_reaches_and_refuses_in_words():
    d = other()
    assert [p for p in LS.check(d) if p.severity == lifting.RED] == []
    rig = LR.Rig(d)
    for a1, sl, hv in ((10.0, 0.0, 5000.0), (45.0, 60.0, 12000.0), (70.0, -120.0, 2000.0)):
        t = rig.hook({"A": sl, "B": a1, "D": hv})
        a = LR.hook_to(rig, t, {}, charts(d))
        assert a.ok, a.reason
        assert np.linalg.norm(rig.hook(a.values) - t) < 1.0
        assert a.values["D"] >= -1e-6
    far = LR.hook_to(rig, [60000.0, 0.0, 0.0], {}, charts(d))
    assert not far.ok and "Out of reach" in far.reason and "m" in far.reason
    behind = LR.hook_to(rig, [0.0, 0.0, -1000.0], {}, charts(d))
    assert not behind.ok and behind.reason


@pytest.mark.parametrize("what, change, step", [
    ("no hoist", lambda d: d["rig"]["joints"].pop(), "hoist"),
    ("hoist turns", lambda d: d["rig"]["joints"][3].update(kind="ROTATE"), "hoist"),
    ("slew tilted 10°", lambda d: d["rig"]["joints"][0].update(direction=[0, math.sin(0.1745), math.cos(0.1745)]),
     "slew"),
    ("slew slides", lambda d: d["rig"]["joints"][0].update(kind="SLIDE"), "slew"),
    ("luff upright", lambda d: d["rig"]["joints"][1].update(direction=[0, 0, 1]), "luff"),
    ("luff not on the slew", lambda d: d["rig"]["joints"][1].pop("rides_on"), None),
    ("hoist points up", lambda d: d["rig"]["joints"][3].update(direction=[0, 0, 1]), "hoist"),
    ("no hook point", lambda d: d["rig"]["hook"].pop("point"), "hook_block"),
    ("role none of them", lambda d: [j.update(role="nonsense") for j in d["rig"]["joints"]], None),
])
def test_other_crane_refusals_are_words_with_their_step(what, change, step):
    d = other()
    change(d)
    with pytest.raises(LR.ReachError) as e:
        LR.Rig(d)
    assert len(str(e.value)) > 20
    if step is not None:
        assert e.value.step == step, (what, e.value.step, str(e.value))
    ps = LS.check(d)                                     # the Check says it too, with a step to go to
    assert any(p.severity == lifting.RED for p in ps), (what, texts(ps))


def test_other_crane_without_hook_swing_is_found():
    """The hoist rides straight on the boom (no swing joint): the hook leans as the boom rises. The Check names the
    hook block step; Hook to here never answers with a hook off the point."""
    d = other()
    d["rig"]["joints"].pop(2)
    d["rig"]["joints"][2]["rides_on"] = "B"
    ps = LS.check(d)
    assert any(p.step == "hook_block" and p.severity == lifting.RED for p in ps), texts(ps)
    try:
        rig = LR.Rig(d)
    except LR.ReachError:
        return
    ref = LR.Rig(other())
    t = ref.hook({"B": 40.0, "D": 6000.0})
    a = LR.hook_to(rig, t, {}, charts(d))
    if a.ok:
        assert np.linalg.norm(rig.hook(a.values) - t) < 1.0


# ---------------------------------------------------------------------------------------------------------------------
# joints without limits (the set-up makes the hoist without; Limits is a tick the user may leave off)

def _no_limits(d, *names):
    for n in names:
        joint(d, n).pop("limits", None)
    return d


def test_hook_to_never_pulls_the_hook_up_past_the_sheave():
    """A hoist without limits (made by the set-up and never given any): Hook to here must not answer with the rope
    shorter than nothing – the hook above the head sheave. Refused in words, or the hoist at 0 or more."""
    d = _no_limits(data_of("AT-40"), "Hoist")
    ref = LR.Rig(data_of("AT-40"))
    rig = LR.Rig(d)
    t = ref.hook({"Luff": 50.0, "Telescope": 3000.0, "Hoist": 8000.0, "Slew": 30.0})
    for target in (t, t + np.array([0.0, 0.0, 30000.0])):
        a = LR.hook_to(rig, target, {}, charts(d))
        if a.ok:
            assert a.values["Hoist"] >= -1.0, f"the hook {-a.values['Hoist'] / 1000:.1f} m above the head sheave"


@pytest.mark.parametrize("name", ["Hoist", "Luff", "Telescope"])
def test_the_check_names_a_reach_joint_without_limits(name):
    """Hook to here and the Check's run from Min to Max need the reach joints' limits: a luff, telescope or hoist
    without limits is a problem of its step (else the Check never runs that joint and finds nothing)."""
    d = _no_limits(data_of("AT-40"), name)
    role = LR.role_of(joint(d, name))
    ps = LS.check(d)
    assert any(p.step in (role, "hook_block") for p in ps), (name, texts(ps))


def test_a_hook_not_plumb_is_found_when_the_luff_has_no_limits():
    """No hook swing (the hoist rides on the boom head) and the luff without limits: the hook leans as the boom
    rises – the Check must still find it."""
    d = data_of("AT-40")
    d["rig"]["joints"] = [j for j in d["rig"]["joints"] if j["name"] != "Hook swing"]
    joint(d, "Hoist")["rides_on"] = "Telescope 4"
    _no_limits(d, "Luff")
    ps = LS.check(d)
    assert any(p.step in ("hook_block", "luff") for p in ps), texts(ps)


def test_with_limits_the_same_fault_is_found():
    d = data_of("AT-40")
    d["rig"]["joints"] = [j for j in d["rig"]["joints"] if j["name"] != "Hook swing"]
    joint(d, "Hoist")["rides_on"] = "Telescope 4"
    ps = LS.check(d)
    assert any(p.step == "hook_block" for p in ps), texts(ps)


# ---------------------------------------------------------------------------------------------------------------------
# no chart

def test_no_chart_readout_is_not_checked_grey():
    """The brief: no chart = the crane can be placed and moved, crane use says 'Not checked – no chart' (grey). An own
    crane without the owner's chart is never 'within limits' – and not 'Over entered limit' either: no limit was
    entered."""
    for name in ("AT-40", "KB-50", "CC-750"):
        d = data_of(name)
        rig = LR.Rig(d)
        vals = {p["name"]: p["values"] for p in d["rig"]["poses"]}["Working"]
        ro = LR.readout(rig, vals, (), load_kg=5000.0)
        assert ro.use is None
        assert ro.status == lifting.NOT_CHECKED, (name, ro.status, ro.words, ro.reason)
        assert "no chart" in (ro.words + " " + ro.reason).lower()


def test_no_chart_check_is_amber_not_checked_and_hook_to_still_works():
    d = data_of("KB-50")
    d["charts"] = []
    ps = LS.check(d)
    assert [p for p in ps if p.severity == lifting.RED] == [], texts(ps)
    assert any(p.step == "chart" and p.severity == lifting.AMBER and "Not checked – no chart" in p.text for p in ps)
    assert not any("within" in p.text.lower() for p in ps)
    rig = LR.Rig(d)
    t = rig.hook({"Main boom": 20.0, "Knuckle": 10.0, "Extension": 900.0, "Hoist": 2000.0})
    a = LR.hook_to(rig, t, {}, ())
    assert a.ok, a.reason
    assert a.use is None and a.chart is None


# ---------------------------------------------------------------------------------------------------------------------
# the Check on odd files: words, never a traceback

ODD = {
    "outrigger stages empty": lambda d: d["outriggers"].update(stages=None),
    "outrigger centre in words": lambda d: d["outriggers"].update(centre=["a", "b"]),
    "axles in words": lambda d: (d.pop("outriggers"), d.update(axles={"x": ["a"], "width": 2})),
    "boom angle as one number": lambda d: d["limits"].update(boom_angle=5),
    "boom angle in words": lambda d: d["limits"].update(boom_angle="steep"),
    "model boom in words": lambda d: d["limits"].update(model_boom="long"),
    "rig as a list": lambda d: d.update(rig=[1, 2]),
    "joint not a table": lambda d: d["rig"]["joints"].append(5),
    "masses as a list": lambda d: d.update(mass=[1, 2]),
    "pose without values": lambda d: d["rig"]["poses"].append({"name": "x", "values": None}),
    "pose value in words": lambda d: d["rig"]["poses"].append({"name": "x", "values": {"Luff": "high"}}),
    "groups as a list": lambda d: d["rig"].update(groups=[1]),
    "footprint in words": lambda d: (d.pop("outriggers"), d.pop("axles"), d.update(footprint=[["a", 1], [2, 3],
                                                                                              [4, 5]])),
}


@pytest.mark.parametrize("what", list(ODD))
def test_check_and_hook_to_on_odd_files_answer_in_words(what):
    """A hand-edited file the library reads: the Check gives problems, Rig / Hook to here a ReachError or an answer –
    never another exception (the panel would show a traceback)."""
    d = data_of("AT-40")
    ODD[what](d)
    ps = LS.check(d)
    assert all(isinstance(p.text, str) and p.text for p in ps)
    try:
        rig = LR.Rig(d)
    except LR.ReachError:
        return
    a = LR.hook_to(rig, [12000.0, 0.0, 6000.0], {}, ())
    assert isinstance(a.ok, bool)
    LR.readout(rig, {}, ())


# ---------------------------------------------------------------------------------------------------------------------
# the Check's other checks on own files

def test_a_follower_pushed_past_its_limits_by_its_ratio():
    d = data_of("AT-40")
    joint(d, "Telescope 3")["ratio"] = 1.5
    ps = LS.check(d)
    assert any(p.step == "telescope" and "Telescope 3" in p.text for p in ps), texts(ps)


def test_a_pose_naming_a_joint_the_crane_does_not_have():
    d = data_of("AT-40")
    d["rig"]["poses"][2]["values"]["Luff 2"] = 10.0
    ps = LS.check(d)
    assert any(p.step == "poses" and "Luff 2" in p.text for p in ps), texts(ps)


def test_crawler_cog_far_behind_its_tracks_is_red():
    d = data_of("CC-750")
    k = next(iter(d["cog"]))
    d["cog"]["counterweight" if "counterweight" in d["cog"] else k] = [-40.0, 0.0, 3.0]
    d["mass"]["counterweight" if "counterweight" in d["mass"] else k] = 500.0
    ps = LS.cog_problems(d)
    assert ps and ps[0].severity == lifting.RED and ps[0].step == "masses" and "outside" in ps[0].text


def test_a_y_up_copy_of_a_builtin_checks_and_hooks_as_the_builtin():
    """The AT-40's file turned into a Y-up frame (x, z, -y) – as a crane drawn with Y up is written: the same Check
    (none) and the same Hook to here answers."""
    d0 = data_of("AT-40")
    d = copy.deepcopy(d0)
    Rm = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], float)
    for j in d["rig"]["joints"]:
        j["point"] = (Rm @ np.asarray(j["point"], float)).tolist()
        j["direction"] = (Rm @ np.asarray(j["direction"], float)).tolist()
    d["rig"]["hook"]["point"] = (Rm @ np.asarray(d["rig"]["hook"]["point"], float)).tolist()
    for k in d["cog"]:
        d["cog"][k] = (Rm @ np.asarray(d["cog"][k], float)).tolist()
    d["rig"]["up_axis"] = "Y"
    c = d["outriggers"]["centre"]
    d["outriggers"]["centre"] = [c[0], -c[1]]                    # level (x, z) of the Y-up frame
    assert texts(LS.check(d)) == texts(LS.check(d0))
    r0, r1 = LR.Rig(d0), LR.Rig(d)
    v = {"Luff": 45.0, "Telescope": 2500.0, "Hoist": 7000.0, "Slew": -40.0}
    t0 = r0.hook(v)
    a0 = LR.hook_to(r0, t0, {}, charts(d0))
    a1 = LR.hook_to(r1, Rm @ t0, {}, charts(d))
    assert a0.ok and a1.ok, (a0.reason, a1.reason)
    for k in a0.values:
        assert a1.values[k] == pytest.approx(a0.values[k], abs=0.05), k


def test_role_words_with_case_and_spaces():
    assert LR.role_of({"name": "x", "role": " Luff "}) == "luff"
    assert LR.role_of({"name": "x", "role": "HOIST"}) == "hoist"
    assert LR.role_of({"name": "Hook swing 2"}) == "swing"
    assert LR.role_of({"name": "Slewing ring"}) == "slew"
    assert LR.role_of({"name": "Legend plate"}) is None
    assert LR.role_of({"name": "Hoist", "role": None}) == "hoist"
