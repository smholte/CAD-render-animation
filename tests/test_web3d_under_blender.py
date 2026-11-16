"""Web 3D model under the sea (task 0143), with Blender: the page's ``under`` block is read from what the app built –
the cut-away box placed by the cable into the sea, the water's clarity, the seabed under the water, the soil section
of 0148, the seabed's drift while the cable pays out – and is left out where the app has no seabed (Vessel deck,
Surroundings None)."""

import os

import numpy as np
import pytest

from fresing_render.core import sea as sea_core
from fresing_render.core import web3d_env as env

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea, surroundings, web3d, web3d_env  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEA_STEP = os.path.join(HERE, "data", "test_sea.step")


@pytest.fixture(scope="module")
def made():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=SEA_STEP, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    s = scene.fresing
    s.background, s.env_detail, s.sea_state, s.water_level = "SEA", "SIMPLE", "CALM", 2.0
    s.sea_depth = 15.0
    s.sea_clarity = 8.0
    out = paths_sea.set_up_test_model(scene)
    s.sea_cutaway = True
    info = animation.bake(scene, s.animations[out["animation"]])
    assert not info["warnings"], info["warnings"]
    yield scene
    fresing_render.unregister()


def export(scene, tmp_path, name, animated=True, mode="PROJECT"):
    w = scene.fresing.web3d
    w.env_mode = mode
    ch = web3d_env.choice(scene)
    out = web3d.export(scene, str(tmp_path / f"{name}.glb"), size=256, surroundings=ch, animation=animated)
    with open(out["html"], encoding="utf-8") as fh:
        return out, env.page_settings(fh.read())


def test_box_clarity_and_seabed_come_from_the_project(made, tmp_path):
    scene = made
    s = scene.fresing
    out, st = export(scene, tmp_path, "cut")
    u = st["under"]
    box = surroundings.sea_cut_box(scene)
    assert box is not None and s.sea_cut_auto                        # placed by the cable into the sea
    assert u["cut"]["origin"] == pytest.approx(list(box["origin"]), abs=1e-4)
    assert u["cut"]["dir"] == pytest.approx(list(box["dir"]), abs=1e-6)
    assert u["cut"]["length"] == pytest.approx(box["length"], abs=1e-4)
    assert u["cut"]["width"] == pytest.approx(box["width"], abs=1e-4)
    assert u["clarity"] == pytest.approx(8.0) and u["sigma"] == pytest.approx(sea_core.absorption(8.0))
    assert u["bed"] == pytest.approx(surroundings.seabed_z(scene), abs=1e-5)
    assert u["bed"] + u["depth"] == pytest.approx(st["sea"]["level"], abs=1e-5)
    assert u["ground"] is None
    assert "the seabed and the sea cut-away" in out["env_items"]
    # the seabed drifts while the cable pays out (60 m/min for 8 s): 8 m along the lay direction (paths_sea.sync_bed)
    mo = u["motion"]
    assert mo is not None and mo["t"][0] == 0.0
    a, b = np.array(env.bed_offset(u, 0.0)), np.array(env.bed_offset(u, mo["t"][-1] - 1e-6))
    item = paths.find(scene, paths_sea.TEST_CABLE)
    lay = np.array(item.sea_dir[:2], float)
    lay /= np.linalg.norm(lay)
    assert float(np.dot(b - a, lay)) == pytest.approx(8.0, abs=0.15)
    # at the moments the app shows, the page's seabed starts where the app's seabed object is
    fps = scene.render.fps / scene.render.fps_base
    for f in (scene.frame_start, scene.frame_start + 60, scene.frame_end - 1):   # (the page repeats at the end)
        scene.frame_set(f)
        scene.frame_set(f)                                         # (a driven empty: one more update)
        assert env.bed_offset(u, (f - scene.frame_start) / fps) == pytest.approx(list(web3d_env.bed_xy(scene)),
                                                                                  abs=0.02)


def test_ground_and_no_cutaway(made, tmp_path):
    scene = made
    s = scene.fresing
    s.sea_cut_ground = True
    try:
        _out, st = export(scene, tmp_path, "ground", animated=False)
        soil = [o for o in bpy.data.objects if o.get(surroundings.TAG) == "soil"]
        assert len(soil) == 1
        assert st["under"]["ground"]["depth"] == pytest.approx(soil[0]["fr_soil_depth"])
        assert st["under"]["motion"] is None                         # not animated: the seabed of the frame shown
    finally:
        s.sea_cut_ground = False
    s.sea_cutaway = False
    try:
        out, st = export(scene, tmp_path, "nocut", animated=False)
        assert st["under"]["cut"] is None and st["under"]["ground"] is None    # the seabed stays (diving)
        assert "cut-away" not in out["env_items"]
    finally:
        s.sea_cutaway = True


def test_no_seabed_on_the_deck_or_without_surroundings(made, tmp_path):
    scene = made
    s = scene.fresing
    _out, st = export(scene, tmp_path, "plain", animated=False, mode="NONE")
    assert "under" not in st and st["sea"] is None
    s.background = "DECK"
    try:
        _out, st = export(scene, tmp_path, "deck", animated=False)
        assert st["sea"] is not None and "under" not in st
    finally:
        s.background = "SEA"
