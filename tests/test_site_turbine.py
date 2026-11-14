"""The IEA 15 MW wind turbine on the landing page (task 0116): onshore and offshore, from the owner's STEP.

The STEP (``15MW.step``, the IEA's SolidWorks model exported in Fusion) lies on the draft release ``site-kit``; the
repository's test machines cannot see drafts, so most checks here read the sheets the kit ships
(``site/render_kit/projects/iea15_*.json``, written by ``tools/make_site_projects.py`` from that STEP) and the kit's
settings. Where the STEP is on this machine (``FRESING_IEA15_STEP`` or the sources cache) the shipped sheets are also
compared with a fresh conversion – on GitHub that runs in the site-kit workflow, which refuses a kit whose sheets
differ. The converter itself is tested on a small stand-in model in ``tests/test_site_turbine_standin.py``.
"""

from __future__ import annotations

import json
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
KIT = os.path.join(ROOT, "site", "render_kit")
MODELS = ("iea15_offshore", "iea15_onshore")


def _sheet(model):
    with open(os.path.join(KIT, "projects", f"{model}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _m(sheet, key):
    return sheet["measured"][key]["value"]


def _iea(sheet, key):
    return sheet["iea"][key]["value"]


@pytest.mark.parametrize("model", MODELS)
def test_sizes_match_the_iea_report(model):
    """Hub height and rotor diameter within 1 % of the IEA's v1.0 numbers, every number with its source."""
    s = _sheet(model)
    assert s["iea_commit"].startswith("630f7cb")                  # IEA-15-240-RWT v1.0
    for k, v in s["iea"].items():
        assert v["source"] and ("IEA-15-240-RWT" in v["source"] or "v1.0" in v["source"]), k
    above = 0.0 if model == "iea15_offshore" else 14.0              # on land the tower stands 14 m lower
    assert abs(_m(s, "hub_height_m") + above - _iea(s, "hub_height_m")) <= 0.01 * _iea(s, "hub_height_m")
    assert abs(_m(s, "rotor_diameter_m") - _iea(s, "rotor_diameter_m")) <= 0.01 * _iea(s, "rotor_diameter_m")
    assert abs(_m(s, "shaft_tilt_deg") - _iea(s, "shaft_tilt_deg")) < 0.01
    assert abs(_m(s, "tower_top_m") - _iea(s, "tower_top_m")) <= 0.005 * _iea(s, "tower_top_m")
    assert abs(_m(s, "blade_length_m") - _iea(s, "blade_length_m")) < 0.05
    assert abs(_m(s, "prebend_m") - _iea(s, "prebend_m")) < 0.05
    assert _m(s, "precone_deg") < 0.01                              # the CAD has no precone: said in the sheet
    assert "IEA 4°" in s["measured"]["precone_deg"]["source"]


@pytest.mark.parametrize("model", MODELS)
def test_joints_on_their_axes(model):
    s = _sheet(model)
    by = {j["name"]: j for j in s["joints"]}
    want = {"Yaw", "Rotor", "Pitch 1", "Pitch 2", "Pitch 3", "Door"} | ({"Davit"} if model == "iea15_offshore"
                                                                         else set())
    assert set(by) == want
    assert by["Yaw"]["direction"] == [0.0, 0.0, 1.0] and by["Yaw"]["point"][:2] == [0.0, 0.0]
    assert by["Rotor"]["rides_on"] == "Yaw"
    d = by["Rotor"]["direction"]
    assert d[0] == 0.0 and d[1] > 0.99 and abs(math.degrees(math.asin(-d[2])) - 6.0) < 0.01   # downwind, 6° tilt
    for i in (1, 2, 3):
        p = by[f"Pitch {i}"]
        assert p["rides_on"] == "Rotor" and p["limits"] == [-5.0, 95.0]
        # a pitch axis is square to the rotor (no precone) and passes 3 m from the hub's centre
        dot = sum(a * b for a, b in zip(p["direction"], d))
        assert abs(dot) < 1e-4
        rel = [a - b for a, b in zip(p["point"], by["Rotor"]["point"])]
        assert abs(math.sqrt(sum(x * x for x in rel)) - 3000.0) < 1.0
        assert "ring face is centred on it (0.000 mm" in p["source"]
    for j in s["joints"]:
        assert j["source"], j["name"]
    assert by["Door"]["limits"][1] >= 80.0


@pytest.mark.parametrize("model", MODELS)
def test_loop_turns_a_whole_number_of_thirds_at_rated_speed(model):
    s = _sheet(model)
    a = s["animation"]
    assert a["loop"] and a["periods"] == {"Rotor": 120.0}
    rotor = next(st for st in a["steps"] if st["joint"] == "Rotor")
    start = next(p for p in s["poses"] if p["name"] == s["start_pose"])["values"]["Rotor"]
    turn = rotor["to"] - start
    assert abs(turn / 120.0 - round(turn / 120.0)) < 1e-9 and turn > 0
    assert rotor["easing"] == "LINEAR" and rotor["start"] == 0.0 and rotor["seconds"] == a["seconds"]
    rpm = turn / 360.0 / (a["seconds"] / 60.0)
    assert abs(rpm - 7.56) < 0.001                                   # the IEA's rated rotor speed
    yaw = [st for st in a["steps"] if st["joint"] == "Yaw"]
    assert yaw[-1]["to"] == 0.0 and abs(yaw[-1]["start"] + yaw[-1]["seconds"] - a["seconds"]) < 1e-6
    assert {p["name"] for p in s["poses"]} >= {"Running", "Feathered", "Door open"}
    feathered = next(p for p in s["poses"] if p["name"] == "Feathered")["values"]
    assert all(feathered[f"Pitch {i}"] == 90.0 for i in (1, 2, 3))
    assert a["camera"] in {c["name"] for c in s["cameras"]}


@pytest.mark.parametrize("model", MODELS)
def test_decals_cameras_scene_and_hidden_parts(model):
    s = _sheet(model)
    texts = {d.get("text") for d in s["decals"]}
    assert "WTG A07" in texts
    stickers = {d.get("sticker") for d in s["decals"] if d["kind"] == "STICKER"}
    assert "WARN_GENERAL" in stickers
    if model == "iea15_offshore":
        assert {"N 0°", "E 90°", "S 180°", "W 270°"} <= texts and "WARN_LOAD" in stickers
        assert s["scene"]["water_level_m"] == 30.0                    # the sea at z 0: 30 m above the cut pile
        assert "Work boat" in {c["name"] for c in s["cameras"]}
        assert any(h["part"] == "MONOPILE BELOW SEABED" for h in s["hide"])
    for d in s["decals"]:
        assert d["kind"] in ("TEXT", "STICKER") and d["part"] and len(d["point"]) == 3
        n = d["normal"]
        assert abs(math.sqrt(sum(x * x for x in n)) - 1.0) < 1e-6
    hidden = {h["part"] for h in s["hide"]}
    assert {"MAIN BEARING SRB", "MAIN BEARING TDO", "BLADE 1 ROOT DISC"} <= hidden
    for h in s["hide"]:
        assert h["why"]
    # no maker's names or logos on the model (owner's choice): only an invented turbine id and plain signs
    words = " ".join(str(d.get("text", "")) for d in s["decals"]).lower()
    for brand in ("siemens", "vestas", "gamesa", "ge ", "nordex", "enercon", "orsted", "ørsted", "iea"):
        assert brand not in words


def test_kit_settings_and_credits():
    import make_site_pictures as kit  # noqa: F401  (KIT on the path below)
    general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    by = {m["id"]: m for m in models}
    lib = _materials()
    for model in MODELS:
        m = by[model]
        assert m["project"] == model and m["file"] == f"{model}.step"
        assert m["credit"].startswith("IEA 15 MW Reference Wind Turbine") and "Apache-2.0" in m["credit"]
        assert "added by Fresing" in m["credit"]
        for _pat, mat, _col in m["colours"]:
            assert mat in lib, mat
        cams = {c["name"].upper() for c in _sheet(model)["cameras"]}
        assert all(v in kit.VIEW_NAMES or v in cams for v in m["views"])
    assert by["iea15_offshore"]["surroundings"] == "SEA" and by["iea15_offshore"]["video"] == "animation"
    credits = open(os.path.join(ROOT, "site", "CREDITS.md"), encoding="utf-8").read()
    media = json.load(open(os.path.join(ROOT, "site", "media", "media.json"), encoding="utf-8"))
    for model in MODELS:
        assert media["models"][model]["credit"] == by[model]["credit"]
        assert by[model]["credit"] in credits
    assert "what Fresing changed" in credits


def _materials():
    sys.path.insert(0, ROOT)
    from fresing_render.core import materials_lib
    return materials_lib.MATERIALS


sys.path.insert(0, KIT)


@pytest.fixture(scope="module")
def owner_step():
    from site_projects import fetch
    return fetch.fetch_step("iea15_offshore") if fetch.available("iea15_offshore") else None


def test_shipped_sheets_match_a_fresh_conversion(owner_step):
    """With the owner's STEP on this machine: the kit's sheets are what the converter makes from it (on GitHub the
    site-kit workflow checks the same before it packs the kit)."""
    import make_site_projects as msp
    if owner_step is None:
        # no STEP here (GitHub's test machines cannot see the draft): the sheets must at least name what made them
        for model in MODELS:
            s = _sheet(model)
            assert s["step"] == f"{model}.step" and s["source"].startswith("IEA Wind TCP Task 37")
            assert s["unique_parts"] > 0 and s["parts"] >= s["unique_parts"]
        return
    assert msp.check_sheets(models=MODELS) == []
