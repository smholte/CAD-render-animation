"""7 Render queue > Every paint scheme (task 0074): one job per scheme, named after it, the scheme only in the job."""

import math
import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")

import fresing_render  # noqa: E402
from fresing_render.blender import animation, cameras, logic, queue, render  # noqa: E402

YELLOW = "Colour #F9A800"          # the crane's yellow group


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path, monkeypatch):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    monkeypatch.setattr(queue, "_RUNS", {})
    monkeypatch.setattr(queue, "_DELAY", {"when": 0.0, "project": "", "note": ""})
    sc = bpy.context.scene
    s = sc.fresing
    s.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    cameras.add_camera(sc, "FRONT")
    logic.save_scheme(s, "Own")
    for name, colour in (("Red", "#E00000"), ("Blue", "#0030E0"), ("Green", "#00C000")):
        s.groups[YELLOW].color = colour
        logic.save_scheme(s, name)
    logic.apply_scheme(sc, "Own")
    a = s.animations.add()
    a.name, a.fps, a.tail = "Spin", "25", 0.0
    b = a.blocks.add()
    b.kind, b.camera_mode, b.orbit_angle, b.start, b.duration = "CAMERA", "ORBIT", math.radians(30), 0.0, 0.2
    yield sc
    queue.cancel_delay()
    if queue.is_running(sc):
        queue.kill(sc)


def test_animation_in_ticked_or_all_schemes(scene):
    s = scene.fresing
    s.schemes["Own"].queue_on = False
    assert bpy.ops.fresing.queue_schemes(kind="ANIMATION", name="Spin") == {"FINISHED"}
    assert [(j.kind, j.animation, j.scheme) for j in s.queue] == [
        ("ANIMATION", "Spin", "Red"), ("ANIMATION", "Spin", "Blue"), ("ANIMATION", "Spin", "Green")]
    assert s.queue[0].label == "Animation: Spin in Red"
    assert "3 paint schemes" in s.last_message
    assert s.groups[YELLOW].color == "#F9A800"                  # the project keeps its colours
    assert bpy.ops.fresing.queue_schemes(kind="ANIMATION", name="Spin", which="ALL") == {"FINISHED"}
    assert len(s.queue) == 7
    bpy.ops.fresing.queue_schemes_tick(on=False)
    assert not any(sch.queue_on for sch in s.schemes)
    assert bpy.ops.fresing.queue_schemes(kind="ANIMATION", name="Spin") == {"CANCELLED"}
    bpy.ops.fresing.queue_schemes_tick(on=True)
    assert all(sch.queue_on for sch in s.schemes)


def test_current_view_in_every_scheme_shares_one_hidden_scene(scene):
    s = scene.fresing
    assert bpy.ops.fresing.queue_schemes(kind="STILL") == {"FINISHED"}
    assert [j.scheme for j in s.queue] == ["Own", "Red", "Blue", "Green"]
    assert len({j.shot for j in s.queue}) == 1 and s.queue[0].shot
    assert s.shots[s.queue[0].shot].get(queue.QUEUE_ONLY)
    assert s.queue[1].label.endswith("in Red")


def test_each_job_renders_in_its_scheme_and_names_the_file(scene, monkeypatch):
    s = scene.fresing
    seen = []

    def fake_still(sc, settings, quality, watermark=False):
        seen.append(settings.groups[YELLOW].color)
        path = os.path.join(settings.out_folder, "crane_FRONT.png")
        open(path, "wb").close()
        return {"path": path}

    monkeypatch.setattr(render, "render_still", fake_still)
    bpy.ops.fresing.queue_schemes(kind="STILL")
    outs = []
    for j in list(s.queue):
        job = {"kind": "STILL", "shot": j.shot, "camera": j.camera, "quality": "draft", "out_dir": s.out_folder,
               "scheme": j.scheme}
        outs.append(queue.run_job(scene, job, lambda *a: None, lambda: False))
    assert seen == ["#F9A800", "#E00000", "#0030E0", "#00C000"]
    assert [os.path.basename(p) for p in outs] == ["crane_FRONT_Own.png", "crane_FRONT_Red.png",
                                                   "crane_FRONT_Blue.png", "crane_FRONT_Green.png"]
    s.schemes.remove(list(s.schemes).index(s.schemes["Blue"]))
    with pytest.raises(RuntimeError, match="'Blue' was deleted"):
        queue.run_job(scene, {"kind": "STILL", "shot": s.queue[0].shot, "out_dir": s.out_folder, "scheme": "Blue"},
                      lambda *a: None, lambda: False)


def test_animation_job_names_its_video_after_the_scheme(scene, monkeypatch):
    s = scene.fresing
    seen = {}

    def fake_animation(sc, job, progress, should_stop):
        setup = queue._setup_animation(sc, job, progress)
        seen[job["scheme"]] = (sc.fresing.groups[YELLOW].color, setup["name"])
        return setup["name"]

    monkeypatch.setattr(queue, "render_animation", fake_animation)
    for name in ("Red", "Green"):
        queue.run_job(scene, {"kind": "ANIMATION", "animation": "Spin", "quality": "preview", "id": "x",
                              "out_dir": s.out_folder, "scheme": name}, lambda *a: None, lambda: False)
    assert seen["Red"][0] == "#E00000" and seen["Green"][0] == "#00C000"
    assert "_Spin_Red_" in seen["Red"][1] and "_Spin_Green_" in seen["Green"][1]


def test_queue_json_carries_the_scheme_and_start_later_still_works(scene):
    s = scene.fresing
    s.schemes["Own"].queue_on = s.schemes["Green"].queue_on = False
    bpy.ops.fresing.queue_schemes(kind="ANIMATION", name="Spin")
    bpy.ops.fresing.queue_start_later(seconds=0.2)
    assert queue.delay_pending()
    time.sleep(0.3)
    assert queue._delay_tick() is None                  # the time has come: the queue starts
    import json
    with open(os.path.join(s.queue_dir, "queue.json"), encoding="utf-8") as fh:
        jobs = json.load(fh)["jobs"]
    assert [(j["kind"], j["scheme"]) for j in jobs] == [("ANIMATION", "Red"), ("ANIMATION", "Blue")]
    assert s.groups[YELLOW].color == "#F9A800"


def test_real_render_shows_the_schemes_colours(scene, tmp_path):
    """Two tiny Cycles renders: the crane's yellow parts come out red, then blue."""
    s = scene.fresing
    s.out_format, s.out_custom_w, s.out_custom_h = "custom", 96, 64
    s.use_gpu = False
    bpy.ops.fresing.queue_schemes(kind="STILL")
    pics = {}
    for j in list(s.queue):
        if j.scheme not in ("Red", "Blue"):
            continue
        path = queue.run_job(scene, {"kind": "STILL", "shot": j.shot, "quality": "draft", "out_dir": str(tmp_path),
                                     "scheme": j.scheme}, lambda *a: None, lambda: False)
        assert os.path.basename(path).endswith(f"_{j.scheme}.png")
        img = bpy.data.images.load(path)
        pics[j.scheme] = np.array(img.pixels[:]).reshape(-1, 4)[:, :3]
        bpy.data.images.remove(img)
    red, blue = pics["Red"], pics["Blue"]
    changed = np.abs(red - blue).max(axis=1) > 0.1               # the parts of the yellow group
    assert changed.sum() > 20
    r, b = red[changed].mean(axis=0), blue[changed].mean(axis=0)
    assert r[0] > r[2] + 0.1 and b[2] > b[0] + 0.1, (r, b)
    logic.apply_scheme(scene, "Own")
