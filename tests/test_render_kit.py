"""The render kit with motion (task 0112): models.ini's new lines, the expected time, starting later, models taken
from the first kit's folder, and one small run end to end (Thor and the press as projects, a product video and a
loop, on the processor) that ends in one zip with pictures, clips, posters and the log."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT = os.path.join(ROOT, "site", "render_kit")


def _kit():
    spec = importlib.util.spec_from_file_location("kit_0112", os.path.join(KIT, "make_site_pictures.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _ini(tmp_path, text):
    p = tmp_path / "m.ini"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_gallery_set_in_models_ini():
    """The owner's set (13 Nov): EVO 2 stills + turntable, FarmBot outdoors in a weather preset, the press and Thor as
    projects with a product video, OpenArm 2 stills; never the Fresing 400."""
    kit = _kit()
    general, models = kit.read_settings(os.path.join(KIT, "models.ini"))
    by = {m["id"]: m for m in models}
    assert set(by) == {"evo_cnc", "openarm", "thor", "farmbot", "ceb_press"}
    assert by["evo_cnc"]["video"] == "turntable" and len(by["evo_cnc"]["views"]) == 2
    assert by["farmbot"]["weather"] == "CLEAR_DAY" and by["farmbot"]["video"] == "none"
    for m in ("thor", "ceb_press"):
        assert by[m]["project"] == m and by[m]["video"] == "product" and len(by[m]["views"]) == 2
    assert by["openarm"]["video"] == "none" and len(by["openarm"]["views"]) == 2
    text = open(os.path.join(KIT, "models.ini"), encoding="utf-8").read().lower()
    assert "fresing 400" not in text and "fresing_400" not in text
    assert general["start_at"] == ""


@pytest.mark.parametrize("lines,reason", [
    ("video = film", "use none, turntable, product, animation"),
    ("video = animation", "needs a 'project"),
    ("project = nothere", "no projects"),
    ("weather = Sunny", "use none or one of"),
    ("weather = Clear day", "needs surroundings outdoors"),
])
def test_new_lines_plain_problems(tmp_path, lines, reason):
    kit = _kit()
    ini = _ini(tmp_path, f"[a]\nfile = a.step\ncredit = c\n{lines}\n")
    with pytest.raises(ValueError, match=reason):
        kit.read_settings(ini)


def test_weather_by_name_or_id_and_start_time(tmp_path):
    kit = _kit()
    ini = _ini(tmp_path, "[settings]\nstart_at = 23.30\n[a]\nfile = a.step\ncredit = c\nsurroundings = SKY\n"
                         "weather = snow at the quay\nproject = thor\nvideo = animation\npose = Grip\n")
    general, (m,) = kit.read_settings(ini)
    assert m["weather"] == "SNOW_QUAY" and m["project"] == "thor" and m["pose"] == "Grip"
    assert kit.parse_clock(general["start_at"]) == (23, 30) and kit.parse_clock("715") == (7, 15)
    for bad in ("25:00", "noon", "7:61"):
        with pytest.raises(ValueError, match="like 23:30"):
            kit.parse_clock(bad)
    now = time.mktime((2026, 11, 13, 22, 0, 0, 0, 0, -1))
    assert kit.seconds_until(23, 30, now) == pytest.approx(5400)
    assert kit.seconds_until(21, 0, now) == pytest.approx(23 * 3600)        # tomorrow
    said, slept = [], []
    kit.seconds_until = lambda h, mn, now=None: 1500.0
    kit.wait_until("23:30", said.append, sleep=slept.append)
    assert sum(slept) == 1500.0 and "Waiting until 23:30" in said[0]


def test_expected_time(tmp_path):
    kit = _kit()
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "a.step").write_bytes(b"x" * 10_000_000)
    ini = _ini(tmp_path, "[a]\nfile = a.step\ncredit = c\nviews = LOW, HIGH\nvideo = turntable\n"
                         "[b]\nfile = b.step\ncredit = c\nviews = LOW\nproject = thor\nvideo = product\n")
    general, models = kit.read_settings(ini)
    est = kit.estimate(models, general, str(tmp_path / "models"))
    assert est["total"] == pytest.approx(est["a"] + est["b"])
    # a 12 s turntable (300 frames) and a 30 s product video (750 frames) at Preview: tens of minutes each on the 3090
    assert 15 * 60 < est["a"] < 60 * 60 and 45 * 60 < est["b"] < 2 * 3600
    assert kit.estimate(models, general, str(tmp_path / "models"), rate=0.04)["total"] > est["total"]
    assert kit.say_time(3 * 3600 + 25 * 60) == "3 h 25 min" and kit.say_time(30) == "1 min"
    assert kit.show_estimate(str(tmp_path / "models"), ini) == 0


def test_models_found_in_the_first_kit(tmp_path):
    """The new kit brings thor.step and ceb_press.step; the others come from the first kit's models folder next to it
    (also when that zip was unzipped into a folder of the same name inside)."""
    kit = _kit()
    new = tmp_path / "Fresing site kit" / "models"
    new.mkdir(parents=True)
    (new / "thor.step").write_text("x")
    old = tmp_path / "Fresing site pictures kit" / "Fresing site pictures kit" / "models"
    old.mkdir(parents=True)
    (old / "evo.step.step").write_text("x")
    assert kit.find_model(str(new), "thor.step") == str(new / "thor.step")
    assert kit.find_model(str(new), "evo.step") == str(old / "evo.step.step")
    assert kit.find_model(str(new), "farmbot.step") == ""


def test_bat_asks_when_to_start():
    bat = open(os.path.join(KIT, "Make site pictures.bat"), "rb").read()
    assert b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b"")
    text = bat.decode("utf-8")
    assert "--estimate-only" in text and "set /p" in text and '"--start-at=%START%"' in text and 'if not "%ERRORLEVEL%"=="0"' in text
    assert "site_pictures_^<date^>.zip" in text
    readme = open(os.path.join(KIT, "README.txt"), encoding="utf-8").read()
    steps = [ln for ln in readme.splitlines() if ln[:2] in {f"{i}." for i in range(1, 10)}]
    assert len(steps) == 6
    assert "fresing_site_kit.zip" in readme and "site_pictures_<date>.zip" in readme and "Save draft" in readme


def test_kit_end_to_end_small(tmp_path):
    """Both moving models through the kit, small (480 px, Draft, processor, clips of half a second): the projects are
    made, the stills taken in a saved pose, Thor's loop and the press's product video (taking the DRAWER apart)
    rendered with posters, everything in site_pictures_<date>.zip with the log."""
    pytest.importorskip("bpy")
    pytest.importorskip("OCP")
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import make_site_projects as msp
    models = tmp_path / "kit" / "models"
    for model in ("thor", "ceb_press"):
        msp.convert(model, str(models))
    ini = _ini(tmp_path, "[thor]\nfile = thor.step\ntitle = Thor\nlook = DARK\nviews = LOW\nproject = thor\n"
                         "pose = Lift and turn\nvideo = animation\ncredit = Thor by AngelLM, CC BY-SA 4.0\n"
                         "[ceb_press]\nfile = ceb_press.step\ntitle = Press\nlook = SUN\nsurroundings = SKY\n"
                         "weather = Clear day\nviews = ISO_LEFT\nproject = ceb_press\nvideo = product\n"
                         "take_apart = DRAWER\ncredit = CEB Press by Open Source Ecology, CC BY-SA 4.0\n")
    out = tmp_path / "kit" / "output"
    res = subprocess.run([sys.executable, os.path.join(KIT, "make_site_pictures.py"), str(models), str(out), ini,
                          "--small"], capture_output=True, text=True, timeout=1500)
    log = (out / "log.txt").read_text(encoding="utf-8")
    assert res.returncode == 0, log[-4000:] + res.stderr[-2000:]
    assert "Expected time on an RTX 3090" in log and "weather: Clear day" in log
    assert "motion: 18 joints" in log and "motion: 2 joints, 2 cylinders" in log
    zips = [f for f in os.listdir(out) if f.startswith("site_pictures_") and f.endswith(".zip")]
    assert zips == [_kit().zip_name()]
    with zipfile.ZipFile(out / zips[0]) as z:
        names = set(z.namelist())
        info = json.loads(z.read("site_pictures.json"))
    assert {"log.txt", "site_pictures.json", "thor_low.jpg", "thor_loop.mp4", "thor_loop_poster.jpg",
            "ceb_press_iso_left.jpg", "ceb_press_product.mp4", "ceb_press_product_poster.jpg"} <= names
    videos = {i["file"]: i for i in info["items"] if i["kind"] == "video"}
    assert videos["thor_loop.mp4"]["loop"] and videos["thor_loop.mp4"]["poster"] == "thor_loop_poster.jpg"
    assert videos["ceb_press_product.mp4"]["video"] == "product"
    assert info["models"]["ceb_press"]["credit"].startswith("CEB Press") and info["app"]
    assert "take-apart" not in log, "the product video left out the take-apart of DRAWER"
