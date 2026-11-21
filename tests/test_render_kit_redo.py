"""Task 0268: the render kit's "Redo 21 Nov" – a run choice that makes only Thor's side picture (stored camera, crop,
own file name, Thor's credit), the offshore turbine's "Whole turbine" still and its video; the onshore turbine and the
seabed view left out; a run being continued keeps what it had; the start window ticks the run choice alone."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")


def _kit():
    spec = importlib.util.spec_from_file_location("kit_0268", os.path.join(KIT, "make_site_pictures.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ini(tmp_path, text):
    p = tmp_path / "m.ini"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_redo_21_nov_in_models_ini():
    kit = _kit()
    general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    by = {m["id"]: m for m in models}
    (redo,) = general["runs"]
    assert redo["id"] == "Redo 21 Nov" and redo["ticked"] and redo["title"].startswith("Redo 21 Nov")
    chosen, unknown = kit.pick(models, general)                 # what the window ticks and the console route makes
    assert not unknown
    assert [(m["id"], m["views"], m["video"]) for m in chosen] == [
        ("thor_side", ["LOW"], "none"), ("iea15_offshore", ["WHOLE TURBINE"], "animation")]
    assert [kit.kit_run.units_of(m) for m in chosen] == [["still:low"], ["still:whole turbine", "video"]]
    side, turbine = chosen
    assert kit.still_name(side, 0) == "thor_side" and side["credit_of"] == "thor"
    assert side["captions"].startswith("Thor robot arm in the dark studio")
    assert turbine["captions"].startswith("A 15 MW wind turbine on its monopile")     # the Whole turbine's own caption
    # the first run's camera (8 Nov, the LOW view the app worked out for the first model), stored
    assert side["camera"] == {"at": [0.98078, -1.65913, 0.59383], "turn": [82.4523, 0.0, 32.0054]}
    assert side["lens"] == "50" and side["look"] == "DARK" and side["surroundings"] == "COLOR"
    assert not side["project"] and not side.get("pose")       # the arm as drawn, as in the first run
    assert side["colours"] == by["thor"]["colours"]           # the colours of Thor's other pictures (owner 21 Nov)
    assert side["crop"] == pytest.approx((780 / 2400, 0.0, 1780 / 2400, 1.0))
    assert (general["width"], general["height"]) == ("2400", "1350")     # 1000 x 1350 px, as site/media/thor_side.jpg
    # the dropped views: no Seabed, no onshore stills; the onshore model stays in the kit, out of every run
    assert by["iea15_offshore"]["views"] == ["WORK BOAT", "WHOLE TURBINE"]
    assert by["iea15_onshore"]["views"] == [] and by["iea15_onshore"]["video"] == "none"
    everything, _ = kit.pick(models, general, [m["id"] for m in models])
    assert "iea15_onshore" not in {m["id"] for m in everything} and len(everything) == len(models) - 1
    sheet = json.load(open(os.path.join(KIT, "projects", "iea15_offshore.json"), encoding="utf-8"))
    assert "cutaway" not in sheet["scene"] and "Seabed" not in {c["name"] for c in sheet["cameras"]}
    assert sheet["animation"]["camera"] == "Whole turbine"


def test_run_choices_and_rows(tmp_path):
    kit = _kit()
    ini = _ini(tmp_path, "[Quick]\njobs = a: High, b: video\n"
                         "[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\ncaptions = one | two\nnames = a1, a2\n"
                         "video = turntable\n"
                         "[b]\nfile = b.step\ncredit = c\nviews = LOW\nvideo = turntable\n"
                         "[c]\nfile = c.step\ncredit = c\nviews = none\n")
    general, models = kit.read_settings(ini)
    assert [m["id"] for m in models] == ["a", "b", "c"] and not general["runs"][0]["ticked"]
    # nothing ticked by the file: every model (c has nothing to make and is left out)
    chosen, _ = kit.pick(models, general)
    assert [m["id"] for m in chosen] == ["a", "b"] and chosen[0]["views"] == ["LOW", "HIGH"]
    chosen, _ = kit.pick(models, general, ["Quick"])
    a, b = chosen
    assert a["views"] == ["HIGH"] and a["video"] == "none" and a["names"] == ["a2"] and a["captions"] == "two"
    assert b["views"] == [] and b["video"] == "turntable"
    chosen, unknown = kit.pick(models, general, ["Quick", "a", "gone"])      # a row and a model: both, once
    assert [(m["id"], m["views"], m["video"]) for m in chosen] == [("a", ["LOW", "HIGH"], "turntable"),
                                                                     ("b", [], "turntable")]
    assert unknown == ["gone"]
    assert kit.narrow(models[1], ["still:high"]) is None


@pytest.mark.parametrize("text,reason", [
    ("[R]\njobs = x\n", "x is not a model"),
    ("[R]\njobs = a: TOP\n", "has no view 'TOP'"),
    ("[R]\njobs = a: video\n", "has no video"),
    ("[R]\njobs = ,\n", "names nothing"),
    ("[R]\njobs = a\n[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\ncamera_at = 1, 2, 3\ncamera_turn = 0, 0, 0\n",
     "for one picture"),
    ("[R]\njobs = a\n[a]\nfile = a.step\ncredit = c\nviews = LOW\ncamera_at = 1, 2\ncamera_turn = 0, 0, 0\n",
     "needs 3 numbers"),
    ("[R]\njobs = a\n[a]\nfile = a.step\ncredit = c\ncrop = 2000, 0, 1000, 1350\n", "inside the picture"),
    ("[R]\njobs = a\n[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\nnames = one\n", "one file name per view"),
    ("[R]\njobs = a\n[a]\nfile = a.step\ncredit = c\nnames = x/y\nviews = LOW\n", "one file name per view"),
])
def test_plain_problems(tmp_path, text, reason):
    kit = _kit()
    if "[a]" not in text:
        text += "[a]\nfile = a.step\ncredit = c\nviews = LOW\n"
    with pytest.raises(ValueError, match=reason):
        kit.read_settings(_ini(tmp_path, text))


def test_window_rows_and_a_continued_run(tmp_path, monkeypatch):
    """The estimate for the start window: the run choice first and alone ticked, the model rows unticked, a model with
    nothing to make not listed; a stopped run is continued with only what it had."""
    kit = _kit()
    monkeypatch.setenv("FRESING_KIT_STANDARD", str(tmp_path / "std" / "site_kit.json"))
    (tmp_path / "models").mkdir()
    for f in ("a.step", "b.step"):
        (tmp_path / "models" / f).write_bytes(b"x" * 1_000_000)
    ini = _ini(tmp_path, "[Redo]\ntitle = Redo - only two\njobs = a: High, b: video\nticked = yes\n"
                         "[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\nvideo = turntable\n"
                         "[b]\nfile = b.step\ncredit = c\nviews = LOW\nvideo = turntable\n"
                         "[c]\nfile = c.step\ncredit = c\nviews = none\n")
    js = tmp_path / "est.json"
    out = tmp_path / "output"
    assert kit.main(["x", str(tmp_path / "models"), str(out), ini, f"--estimate-json={js}"]) == 0
    rows = json.loads(js.read_bytes())["models"]
    assert [(r["id"], r["ticked"], r["found"]) for r in rows] == [("Redo", True, True), ("a", False, True),
                                                                   ("b", False, True)]
    assert rows[0]["title"] == "Redo - only two"
    general, models = kit.read_settings(ini)
    a_parts = kit.estimate_parts(kit.narrow(models[0], ["still:high"]), general, str(tmp_path / "models"))
    b_parts = kit.estimate_parts(kit.narrow(models[1], ["video"]), general, str(tmp_path / "models"))
    assert rows[0]["gpu"] == pytest.approx(a_parts["gpu"] + b_parts["gpu"], abs=0.2)
    assert rows[0]["gpu"] < rows[1]["gpu"] + rows[2]["gpu"]
    chosen, _ = kit.pick(models, general)
    st = kit.kit_run.RunState.new(str(out), chosen, {})
    assert st.counts() == (0, 2)
    again = kit.resumed(models, st)
    assert [(m["id"], m["views"], m["video"]) for m in again] == [("a", ["HIGH"], "none"), ("b", [], "turntable")]


def test_start_window_takes_the_tick_from_the_estimate():
    ps = open(os.path.join(KIT, "kit_window.ps1"), "rb").read().decode("ascii")
    assert '-contains "ticked") { $tick = [bool]$m.ticked }' in ps
    assert "$item.Checked = ([bool]$m.found -and $tick)" in ps


def test_stored_camera_crop_and_name_small(tmp_path):
    """A model with a stored camera, a crop and its own file name, through the kit (small, processor): the picture is
    the crop's share of the frame, named as asked, credited as the other model; the camera sits where it was stored."""
    pytest.importorskip("bpy")
    pytest.importorskip("OCP")
    models = tmp_path / "models"
    models.mkdir()
    step = os.path.join(ROOT, "tests", "data", "test_machine.step")
    os.symlink(step, models / "m.step")
    ini = _ini(tmp_path, "[Only side]\njobs = side\nticked = yes\n"
                         "[mach]\nfile = m.step\ncredit = Mach credit\nviews = LOW\n"
                         "[side]\nfile = m.step\nmodel = mach\ncredit = Mach credit\nlook = DARK\nviews = LOW\n"
                         "names = mach_side\ncamera_at = 2.5, -3.0, 1.2\ncamera_turn = 75, 0, 40\nlens = 50\n"
                         "crop = 780, 0, 1000, 1350\ncaptions = The side\n")
    out = tmp_path / "output"
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys, runpy, json\n"
        f"sys.argv = ['make_site_pictures.py', {str(models)!r}, {str(out)!r}, {ini!r}, '--small']\n"
        "kit = runpy.run_path(" + repr(os.path.join(KIT, "make_site_pictures.py")) + ", run_name='kit')\n"
        "code = kit['main'](sys.argv)\n"
        "import bpy\n"
        "cam = bpy.data.objects['Site LOW']\n"
        "r = bpy.context.scene.render\n"
        "json.dump({'code': code, 'at': list(cam.matrix_world.translation), 'turn': [a for a in cam.matrix_world"
        ".to_euler('XYZ')], 'lens': cam.data.lens, 'border': r.use_border}, open(sys.argv[2] + '/probe.json', 'w'))\n",
        encoding="utf-8")
    res = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True, timeout=900)
    log = (out / "log.txt").read_text(encoding="utf-8") if (out / "log.txt").exists() else ""
    p = json.loads((out / "probe.json").read_text())
    assert p["code"] == 0, log[-3000:] + res.stderr[-2000:]
    assert "Run: Only side" in log and "Model 1 of 1: side" in log
    assert sorted(os.listdir(out / "send")) == ["mach_side.jpg", "site_pictures.json"]
    info = json.loads((out / "send" / "site_pictures.json").read_text(encoding="utf-8"))
    (item,) = info["items"]
    assert item["model"] == "mach" and item["caption"] == "The side" and info["models"]["mach"]["credit"] == "Mach credit"
    size = subprocess.run(["identify", "-format", "%w %h", str(out / "full" / "mach_side.png")],
                          capture_output=True, text=True).stdout.split()
    assert [int(v) for v in size] == [100, 135]          # small: 480 x 270 at Draft (50 %), 1000/2400 of it across
    import math
    assert p["at"] == pytest.approx([2.5, -3.0, 1.2], abs=1e-5)
    assert [math.degrees(a) for a in p["turn"]] == pytest.approx([75.0, 0.0, 40.0], abs=1e-3)
    assert p["lens"] == 50.0 and p["border"] is False   # the crop is taken off again after the picture
