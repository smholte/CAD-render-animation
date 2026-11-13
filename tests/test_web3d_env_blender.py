"""Web 3D model with surroundings (task 0106), with Blender: the panel's choice, the page's sea and vessel numbers
against the app's own sea mesh and vessel rig, the export with surroundings, and the page in headless Chromium when
the session has one (else its scripts are parsed by node)."""

import json
import math
import os
import shutil
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d_env as env

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import vessel_motion, web3d, web3d_env, world  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CRANE = os.path.join(HERE, "data", "test_crane_a.step")
SHOT = os.path.join(ROOT, "tools", "web3d_env_shot.js")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def at_sea(state="CALM", vessel=True, kind="SEA"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    s = sc.fresing
    s.background = kind
    s.sea_state = state
    s.env_detail = "DETAILED"
    s.vessel.enabled = vessel
    world.apply(sc, s)
    sc.frame_set(1)
    return sc


def test_surroundings_start_from_the_project_and_never_change_it():
    sc = at_sea("ROUGH")
    s = sc.fresing
    w = s.web3d
    assert web3d_env.choice(sc) is None                       # None: today's page
    before = (s.background, s.sea_state, s.vessel.enabled, s.sun_elevation)
    w.env_mode = "PROJECT"                                    # the update fills the ticks from the project
    ch = web3d_env.choice(sc)
    assert ch["sea"] and ch["sea_state"] == "ROUGH" and ch["vessel"] and ch["sky_source"] == "PROJECT"
    assert ch["sun_height"] == pytest.approx(s.sun_elevation)
    w.env_sea_state = "CALM"
    w.env_sea = False
    ch = web3d_env.choice(sc)
    assert ch["sea_state"] == "CALM" and not ch["sea"] and not ch["vessel"]     # no vessel motion without a sea
    assert (s.background, s.sea_state, s.vessel.enabled, s.sun_elevation) == before
    assert bpy.ops.fresing.web3d_env_from_project() == {"FINISHED"}
    assert web3d_env.choice(sc)["sea"] and web3d_env.choice(sc)["sea_state"] == "ROUGH"
    s.sky_weather = "OVERCAST"
    assert web3d_env.from_project(sc)["clouds"] == "OVERCAST"
    s.vessel.enabled = False
    w.env_vessel = True
    assert web3d_env.choice(sc)["vessel"] is False            # only when the project has vessel motion on


@pytest.mark.parametrize("state", ["CALM", "ROUGH"])
def test_page_sea_is_the_app_sea(state):
    """The sea block's numbers in the page's formula give the heights of the app's own sea mesh (geometry nodes,
    vessel swell included) at several frames."""
    sc = at_sea(state)
    sc.fresing.web3d.env_mode = "PROJECT"
    ch = web3d_env.choice(sc)
    mn, mx = (np.array(v) for v in web3d.build.world_bounds(web3d.objects(sc)[0]))
    block = web3d_env.sea_block(sc, ch, mn, mx)
    assert block["state"] == state and len(block["waves"]) > block["own"]          # vessel swell is in
    sea = vessel_motion._sea_object()
    fps = sc.render.fps / sc.render.fps_base
    for frame in (1, 37, 140):
        sc.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = sea.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        co = co.reshape(-1, 3)
        r = np.hypot(co[:, 0], co[:, 1])
        pick = np.nonzero((r > 0.3) & (r < 1.7 * block["near"]))[0][::97][:200]
        world_z = co[pick, 2] + sea.matrix_world.translation.z
        x = co[pick, 0] + sea.matrix_world.translation.x - block["origin"][0]
        y = co[pick, 1] + sea.matrix_world.translation.y - block["origin"][1]
        want = block["level"] + env.sea_height(block, x, y, frame / fps)
        assert np.abs(world_z - want).max() < 2e-4, frame


def test_page_vessel_is_the_app_rig():
    """The vessel block played by the page's formula puts the vessel where the app's rig does, at several frames."""
    sc = at_sea("ROUGH")
    sc.fresing.web3d.env_mode = "PROJECT"
    ch = web3d_env.choice(sc)
    mn, mx = (np.array(v) for v in web3d.build.world_bounds(web3d.objects(sc)[0]))
    sea = web3d_env.sea_block(sc, ch, mn, mx)
    v = web3d_env.vessel_block(sc, ch, sea)
    assert v is not None and v["roll"][1] and v["ends"][0][0] < v["pivot"][0] < v["ends"][1][0]
    rig = vessel_motion.rig("pivot")
    fps = sc.render.fps / sc.render.fps_base
    for frame in (1, 50, 233):
        sc.frame_set(frame)
        app = np.array(rig.matrix_world)
        page = env.vessel_matrix(v, frame / fps)
        assert np.abs(app[:3, :3] - page[:3, :3]).max() < 1e-5, frame
        assert np.abs(app[:3, 3] - page[:3, 3]).max() < 1e-4, frame
    # Calm on the page (the project is Rough): smaller motion, the app's Calm numbers
    calm = web3d_env.vessel_block(sc, dict(ch, sea_state="CALM"), dict(sea, state="CALM"))
    t = np.arange(0, 120, 0.1)
    assert np.abs(env.channel(calm["roll"], t)).max() < np.abs(env.channel(v["roll"], t)).max()


def test_export_with_surroundings(tmp_path):
    sc = at_sea("ROUGH", kind="DECK")
    s = sc.fresing
    w = s.web3d
    w.env_mode = "PROJECT"
    w.env_rain = True
    w.env_haze = True
    part = web3d.objects(sc)[0][0]
    vessel_motion.add_marks(sc, [part], "STILL")
    vessel_motion.sync(sc)
    before = part.matrix_world.copy()
    muted = [c.mute for _o, c in vessel_motion._constraints(sc)]
    out = web3d.export(sc, str(tmp_path / "Crane é.glb"), size=512, surroundings=web3d_env.choice(sc))
    assert [c.mute for _o, c in vessel_motion._constraints(sc)] == muted              # the motion is back on
    assert np.allclose(np.array(part.matrix_world), np.array(before))
    page = open(out["html"], encoding="utf-8").read()
    st = env.page_settings(page)
    assert st["sea"]["state"] == "ROUGH" and st["vessel"] and st["haze"] and st["rain"]["spray"]
    assert st["sky"]["kind"] == "SKY" and st["shadows"]
    assert "surroundings" in out["text"] and out["env_items"].startswith("sea (rough), vessel motion")
    doc, _bin = web3d.core.read_glb(open(out["path"], "rb").read())
    still = [n for n in doc["nodes"] if n.get("extras", {}).get("fr_vm") == "STILL"]
    assert len(still) >= 1
    deck = len(web3d_env.deck_objects(sc, web3d_env.choice(sc)))
    assert deck >= 1 and out["parts"] == len(web3d.objects(sc)[0]) + deck              # the deck goes on the page
    # the parts are written where they stand on a still sea, whatever frame the project shows
    sc.frame_set(77)
    out2 = web3d.export(sc, str(tmp_path / "Crane 2.glb"), size=512, surroundings=web3d_env.choice(sc))
    assert open(out2["path"], "rb").read() == open(out["path"], "rb").read()
    # Surroundings None: today's model-viewer page
    w.env_mode = "NONE"
    out3 = web3d.export(sc, str(tmp_path / "Crane 3.glb"), size=512, surroundings=web3d_env.choice(sc))
    plain = open(out3["html"], encoding="utf-8").read()
    assert "<model-viewer" in plain and "FRTHREE" not in plain and "surroundings" not in out3["text"]


def _browser() -> bool:
    if not shutil.which("node"):
        return False
    try:
        subprocess.run(["node", "-e", "try{require('playwright')}catch(e){require('/opt/node-tools/node_modules/playwright')}"],
                       check=True, capture_output=True, timeout=60)
        return True
    except Exception:  # noqa: BLE001
        return False


def test_page_opens_in_a_browser(tmp_path):
    """Headless Chromium (software GL) when the session has one: every item on, each quality, no error. Without a
    browser (GitHub's runners) the page's own scripts are checked by node instead."""
    sc = at_sea("ROUGH")
    w = sc.fresing.web3d
    w.env_mode = "PROJECT"
    w.env_rain = w.env_haze = True
    w.env_clouds = "SOME"
    out = web3d.export(sc, str(tmp_path / "page.glb"), size=512, surroundings=web3d_env.choice(sc))
    if not _browser():
        page = open(out["html"], encoding="utf-8").read()
        for name in ("fr_math.js", "fr_page.js"):
            assert open(os.path.join(web3d.core.WEB_DIR, name), encoding="utf-8").read() in page
        if shutil.which("node"):
            for name in ("fr_math.js", "fr_page.js"):
                subprocess.run(["node", "--check", os.path.join(web3d.core.WEB_DIR, name)], check=True)
        return
    levels = {}
    for q in env.LEVELS:
        r = subprocess.run(["node", SHOT, out["html"], str(tmp_path / f"{q}.png"), "480", "320",
                            f"--query=quality={q}&auto=0&t=8", "--wait=300"], capture_output=True, text=True,
                           timeout=300)
        info = json.loads(r.stdout.strip().splitlines()[-1])
        assert info["ok"], info
        levels[q] = info
    assert levels["PHONE"]["info"]["seaPoints"] < levels["BALANCED"]["info"]["seaPoints"] < \
        levels["BEST"]["info"]["seaPoints"]
    assert levels["PHONE"]["info"]["rain"] < levels["BEST"]["info"]["rain"]
    assert math.isfinite(levels["BEST"]["load_ms"])
    # Auto: software drawing at Best cannot keep 30 pictures a second, so the page steps down by itself
    r = subprocess.run(["node", SHOT, out["html"], "-", "900", "600", "--query=quality=BEST&t=8", "--wait=7000"],
                       capture_output=True, text=True, timeout=300)
    info = json.loads(r.stdout.strip().splitlines()[-1])
    assert info["ok"] and info["lowered"] >= 1 and info["level"] != "BEST", info
    # the headless state the PC check reads; a broken model is an error, never a page stuck on "Loading"
    assert env.open_headless(out["html"]).startswith("ready")
    st = env.page_settings(open(out["html"], encoding="utf-8").read())
    st.pop("animated", None)
    broken = tmp_path / "broken.html"
    broken.write_text(env.page_html("Broken", b"not a model", st), encoding="utf-8")
    assert env.open_headless(str(broken)).startswith("error"), "a broken model must show as an error"
