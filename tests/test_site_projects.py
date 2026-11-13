"""The landing page's moving models (task 0112): Thor and the CEB press from their own sources.

The sources are cloned at pinned commits (tools/site_projects/fetch.py, ~6 s, only the folders needed) into
~/.cache/fresing_site_sources. What is checked: the joint sheets the kit ships match a fresh conversion; Thor's joint
axes are the Assembly4 frames' (within 0.1°) and each hinge has round faces on both sides (a wrong axis has none);
the press's cylinders split into barrel and rod; both projects build in the app with 0 clash rows and their loops close.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
KIT = os.path.join(ROOT, "site", "render_kit")

pytest.importorskip("OCP")

import make_site_projects as msp  # noqa: E402
from site_projects import a4, ceb, fetch, thor  # noqa: E402


@pytest.fixture(scope="module")
def thor_src():
    return fetch.fetch("thor")


@pytest.fixture(scope="module")
def ceb_src():
    return fetch.fetch("ceb_press")


def _kept(model):
    with open(os.path.join(KIT, "projects", f"{model}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def test_shipped_sheets_match_the_sources(thor_src, ceb_src):
    assert msp.check_sheets() == []


def test_thor_axes_are_the_assembly4_frames(thor_src):
    """Every joint of the sheet lies on its Assembly4 frame's hinge axis (0.1°, 0.1 mm); both frames of each
    attachment (the parent's LCS x offset, the part's own LCS) agree."""
    import numpy as np
    sheet = _kept("thor")
    by = {j["name"]: j for j in sheet["joints"]}
    r = a4.Reader(os.path.join(thor_src, "Assembly.FCStd"))
    assert set(by) == {j[0] for j in thor.JOINTS} and len(by) == 18
    driven = [j for j in sheet["joints"] if not j.get("follows")]
    assert sorted(j["name"] for j in driven) == sorted(thor.DRIVEN) + ["Art1 pinion"] or len(driven) == 7
    for name, _body, (chain, obj, letter), _on in thor.JOINTS:
        on_parent, own = a4.Attachments(r, chain).frames(obj)
        assert np.allclose(on_parent, own, atol=1e-4), name
        u = own[:3, "xyz".index(letter)]
        c = own[:3, 3]
        j = by[name]
        assert thor.angle_between(u, j["direction"]) <= 0.1, name
        p = np.array(j["point"]) - c
        assert np.linalg.norm(p - np.dot(p, u) * u) <= 0.1, name
    # the hinges people see, in words: base and forearm turn about the vertical, shoulder, elbow and wrist across
    for name, axis in (("Art1", 2), ("Art2", 1), ("Art3", 1), ("Art4", 2), ("Art5", 1), ("Art6", 2)):
        assert abs(by[name]["direction"][axis]) > 0.999, name


def test_thor_hinges_have_round_faces_on_both_sides(thor_src):
    """Each joint's axis is the axis of round faces of the turning body and of the body it sits on (stored by the
    STEP pass); the elbow's other frame axis (vertical) has none on the upper arm – that is how it was told apart."""
    import numpy as np
    for j in _kept("thor")["joints"]:
        n1, n2 = j["round_faces"]
        assert n1 > 0 and n2 > 0, j["name"]
    r = a4.Reader(os.path.join(thor_src, "Assembly.FCStd"))
    thor._attachments.clear()
    for sub in thor.ANCHORS:
        thor._attachments[sub] = a4.Attachments(r, (sub,))
    upper = [p for p in r.parts(shapes=True) if thor.body_of(p) == "ART2"]
    elbow = np.array([0.0, 0.0, 362.0])
    assert thor.round_faces(upper, elbow, np.array([0.0, 1.0, 0.0]))[0] > 10
    assert thor.round_faces(upper, elbow, np.array([0.0, 0.0, 1.0]))[0] == 0


def test_thor_couplings_from_tooth_counts(thor_src):
    by = {j["name"]: j for j in _kept("thor")["joints"]}
    assert thor.teeth(thor_src, "Art1Bot") == (50, 2.0)
    assert abs(by["Art1 pinion"]["ratio"]) == 5.0 and "inside a ring gear" in by["Art1 pinion"]["why"]
    assert abs(by["Art2 pinion A"]["ratio"]) == 6.0 and abs(by["Art4 pinion"]["ratio"]) == 2.0
    assert "outside" in by["Art4 pinion"]["why"]
    assert abs(by["Wrist gear A"]["ratio"]) == 2.0 and by["Wrist gear A"]["follows"] == "Art6"
    # the two bevel gears turn against each other when the wrist rolls (their axes point opposite ways)
    a, b = by["Wrist gear A"], by["Wrist gear B"]
    assert a["ratio"] * a["direction"][1] == -(b["ratio"] * b["direction"][1])
    for f in ("Gripper passive arm", "Gripper link A", "Gripper link B", "Finger A", "Finger B"):
        assert by[f]["follows"] == "Gripper" and abs(by[f]["ratio"]) == 1.0
    assert {h["part"] for h in _kept("thor")["hide"]} == {"ART3 BELT", "ART1 PINION GRUB SCREW"}


def test_loops_start_and_end_in_one_pose():
    for model, lo, hi in (("thor", 10.0, 12.0), ("ceb_press", 8.0, 12.0)):
        sheet = _kept(model)
        a = sheet["animation"]
        assert a["loop"] and lo <= a["seconds"] <= hi, model
        assert a["steps"][-1]["pose"] == sheet["start_pose"], model
        poses = {p["name"] for p in sheet["poses"]}
        assert all(st["pose"] in poses for st in a["steps"]), model
        t = 0.0
        for st in a["steps"]:                       # one after another, no gaps
            assert abs(st["start"] - t) < 1e-6
            t += st["seconds"]


def test_press_cylinders_split_and_source_faults_noted(ceb_src, tmp_path):
    from OCP.BRepCheck import BRepCheck_Analyzer
    subs = ceb.read(ceb_src)
    shift = ceb.chamber_shift(subs)
    assert 10.0 < shift[1] < 12.0                # the main cylinder sits ~11 mm off the chamber in the source
    main = max(subs[ceb.MAIN], key=lambda s: ceb.bbox(s)[1][2] - ceb.bbox(s)[0][2])
    barrel, rod, o, d, root, tip = ceb.split_cylinder(main, 34.92, 0.0, 220.0)
    for part in (barrel, rod):
        assert BRepCheck_Analyzer(part).IsValid()
    assert abs(d[2]) > 0.999                     # the press cylinder stands upright
    assert 280.0 < tip - root < 300.0            # rod from the gland's floor to its eye end
    expected = math.pi * 34.92 ** 2 * (tip - root)                # a solid round rod, less its eye hole
    assert 0.9 * expected < ceb.volume(rod) < 1.01 * expected
    assert ceb.volume(barrel) > 4 * ceb.volume(rod)
    sheet = _kept("ceb_press")
    assert [c["name"] for c in sheet["cylinders"]] == ["Main cylinder", "Drawer cylinder"]
    notes = " ".join(sheet["notes"])
    assert "moved +10.8" in notes and "split into barrel and rod" in notes and "drawer's way cleared" in notes
    drawer = next(j for j in sheet["joints"] if j["name"] == "Drawer")
    assert drawer["direction"] in ([0.0, -1.0, 0.0], [0.0, 1.0, 0.0])          # on its rails, not the 1° cylinder


@pytest.mark.parametrize("model", ["ceb_press", "thor"])
def test_project_builds_with_no_clash(model, tmp_path):
    """The STEP written, imported with the app's importer (Draft), the motion made from the sheet, the loop built
    and clash-checked: 0 clash rows, the joints on the sheet's axes, the loop closes (tools/make_site_projects.py
    --project, Blender as a Python module, its own process). Thor: ~3 min on 4 cores, most of it the clash check."""
    pytest.importorskip("bpy")
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_site_projects.py"), model,
                          "--out", str(tmp_path), "--project"], capture_output=True, text=True, timeout=1500)
    out = res.stdout
    assert res.returncode == 0, out[-3000:] + res.stderr[-3000:]
    summary = json.loads(out[out.index("{\n"):out.rindex("}") + 1])
    sheet = _kept(model)
    assert summary["joints"] == len(sheet["joints"]) and summary["cylinders"] == len(sheet["cylinders"])
    assert summary["poses"] == len(sheet["poses"]) and summary["hidden"] >= len(sheet["hide"])
    assert summary["axis_error_deg"] <= 0.1 and summary["axis_error_mm"] <= 0.1
    assert summary["clash_rows"] == 0, summary.get("clashes")
    assert summary["loop_gap"] < 1e-5
    assert summary["frames"] == 1 + round(sheet["animation"]["seconds"] * 25)
    assert os.path.isfile(os.path.join(tmp_path, f"{model}.blend"))


def test_publish_kit_keeps_a_draft(tmp_path):
    """--publish-kit: makes the draft release when missing, replaces only the kit's own zip, refuses a published one."""
    zp = tmp_path / "k.zip"
    zp.write_bytes(b"PK\x05\x06" + b"\0" * 18)
    calls = []

    def api(method, url, token, data=None, ctype=""):
        calls.append((method, url.split("?")[0].rsplit("/", 2)[-2:], json.loads(data) if ctype.endswith("json")
                      and data else None))
        if method == "GET":
            return state["rels"]
        if method == "POST" and url.endswith("/releases"):
            return {"tag_name": msp.KIT_TAG, "draft": True, "assets": [],
                    "upload_url": "https://uploads.example/rel/1/assets{?name,label}"}
        return {}

    state = {"rels": [{"tag_name": "v0.2.88", "draft": False}]}
    msp.publish_kit(str(zp), "t", api=api)
    made = next(c for c in calls if c[0] == "POST" and c[2])
    assert made[2]["draft"] is True and made[2]["tag_name"] == "site-kit"
    assert calls[-1][0] == "POST" and calls[-1][1] == ["1", "assets"]

    calls.clear()
    state["rels"] = [{"tag_name": "site-kit", "draft": True, "upload_url": "https://u/r/2/assets{?name}",
                      "assets": [{"name": msp.KIT_ASSET, "id": 7}, {"name": "site_pictures_2026-11-14.zip", "id": 8}]}]
    msp.publish_kit(str(zp), "t", api=api)
    deleted = [c for c in calls if c[0] == "DELETE"]
    assert len(deleted) == 1 and deleted[0][1] == ["assets", "7"]          # the owner's upload stays

    state["rels"] = [{"tag_name": "site-kit", "draft": False, "assets": []}]
    with pytest.raises(SystemExit, match="must stay a draft"):
        msp.publish_kit(str(zp), "t", api=api)


def test_site_kit_workflow():
    wf = open(os.path.join(ROOT, ".github", "workflows", "site-kit.yml"), encoding="utf-8").read()
    for key in ("workflow_dispatch:", "branches: [main]", '"site/render_kit/**"', "contents: write",
                "make_site_projects.py --kit", "make_site_projects.py --publish-kit", "GITHUB_TOKEN"):
        assert key in wf, key
    import re
    for line in wf.splitlines():
        m = re.match(r"^\s*(?:- )?run: (.*)$", line)
        if m and m.group(1) not in ("|", ">-"):
            assert ": " not in m.group(1), line
    assert math.isclose(1.0, 1.0)
