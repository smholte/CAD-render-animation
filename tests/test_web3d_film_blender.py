"""Film on the web 3D page (task 0252), Blender as a Python module: the export reads the video's Animation camera.

The test crane's film (``web3d_film.set_up_test``): the camera rides on the boom, flies a path watching the trolley
with a glide-in, cuts to a second camera and keeps the trolley in the middle. The page's film must give Blender's
camera at **every** frame (place ≤ 1 mm per metre of the model, turn and field of view ≤ 0.05°), the cut must jump,
and the three tick boxes must put in only what they name. A project without a built Animation camera, or an export
without its animation, gets no film.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, web3d, web3d_film  # noqa: E402
from fresing_render.core import web3d_env as env  # noqa: E402
from fresing_render.core import web3d_film as F  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def crane(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    """The crane with its film, exported twice: all three tick boxes on, and all off."""
    tmp = tmp_path_factory.mktemp("film")
    sc = crane(tmp)
    web3d_film.set_up_test(sc)
    on = web3d.export(sc, str(tmp / "on.glb"), size=512, animation=True, film_captions=True, film_labels=True,
                      film_cards=True)
    off = web3d.export(sc, str(tmp / "off.glb"), size=512, animation=True)
    cam = web3d_film.camera(sc)
    dg = bpy.context.evaluated_depsgraph_get()
    w, h = sc.render.resolution_x, sc.render.resolution_y
    mats, vfov = [], []
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        ev = cam.evaluated_get(dg)
        mats.append(np.array(ev.matrix_world))
        p = np.array(ev.calc_matrix_camera(dg, x=w, y=h, scale_x=1.0, scale_y=1.0))
        vfov.append(math.degrees(2 * math.atan(1.0 / p[1, 1])))
    sc.frame_set(sc.frame_start)
    st_on = env.page_settings(open(on["html"], encoding="utf-8").read())
    st_off = env.page_settings(open(off["html"], encoding="utf-8").read())
    mn, mx = np.array(st_on["model"]["min"]), np.array(st_on["model"]["max"])
    return {"scene": sc, "on": on, "off": off, "st_on": st_on, "st_off": st_off, "mats": np.array(mats),
            "vfov": np.array(vfov), "size": float(np.linalg.norm(mx - mn)), "cut": web3d_film.cut_frames(sc),
            "frame_start": sc.frame_start}


def test_the_film_is_blenders_camera_at_every_frame(made):
    film = made["st_on"]["films"][0]
    dec = F.decode(film)
    pos, q = F.pose(made["mats"])
    assert dec["n"] == len(pos) and dec["fps"] == 25.0
    ep, ea, ev = F.errors(dec, pos, q, made["vfov"])
    print(f"film: {len(dec['keys'])} of {dec['n']} frames kept, {F.size_bytes(film)} bytes; worst {ep * 1000:.3f} mm, "
          f"{ea:.4f}°, fov {ev:.4f}° (model {made['size']:.2f} m)")
    assert ep <= 1e-3 * max(made["size"], 1.0) and ea <= 0.05 and ev <= 0.05
    # the camera moved (rides, flies, aims): not a still film
    assert np.linalg.norm(pos[0] - pos[-1]) > 0.1 and len(dec["keys"]) > 10


def test_the_cut_jumps(made):
    film = made["st_on"]["films"][0]
    dec = F.decode(film)
    pos, _q = F.pose(made["mats"])
    k = made["cut"][0] - made["frame_start"]                 # the Cut step's frame, counted from the page's first frame
    assert film["cut"] == [k]
    assert np.linalg.norm(pos[k] - pos[k - 1]) > 0.2, "the test's cut is a real jump"
    for frac in (0.25, 0.5, 0.75):                       # held, never halfway
        p, _qq, _v = F.sample(dec, (k - 1 + frac) / dec["fps"])
        assert np.linalg.norm(p[0] - pos[k - 1]) <= 1e-3 * made["size"]


def test_modes_ride_path_aim_and_glide_in_are_in_the_film(made):
    """Each camera step's frames are within the tolerances on their own (the worst of each), so a step the film
    smoothed away would show here."""
    sc = made["scene"]
    a = sc.fresing.animations[web3d_film.TEST_ANIM]
    film = made["st_on"]["films"][0]
    dec = F.decode(film)
    pos, q = F.pose(made["mats"])
    for b in a.blocks:
        if b.kind != "CAMERA" or b.camera_mode == "CUT":
            continue
        f0, f1 = animation.frame_of(a, b.start) - 1, animation.frame_of(a, b.start + b.duration) - 1
        sl = slice(f0, f1 + 1)
        p, qq, v = F.sample(dec, np.arange(f0, f1 + 1) / dec["fps"])
        assert np.linalg.norm(p - pos[sl], axis=1).max() <= 1e-3 * made["size"], b.camera_mode
        ang = np.degrees(2 * np.arccos(np.clip(np.abs((qq * q[sl]).sum(axis=1)), 0, 1))).max()
        assert ang <= 0.05, (b.camera_mode, ang)


def test_tick_boxes_put_in_only_what_they_name(made):
    on, off = made["st_on"]["films"][0], made["st_off"]["films"][0]
    for key in ("captions", "labels", "cards"):
        assert key in on and key not in off, key
    assert [c["text"] for c in on["captions"]][-1] == "The trolley runs back"
    lab = on["labels"]["items"]
    assert len(lab) == 1 and lab[0]["text"] == "Trolley" and lab[0]["w"] == [web3d_film.CUT_AT, web3d_film.END_AT]
    assert on["cards"]["title"]["title"] == "Crane" and on["cards"]["end"]["s"] == 1.0
    assert "Film" in made["on"]["text"] and made["on"]["film_bytes"] < 20_000
    off_text = open(made["off"]["html"], encoding="utf-8").read()
    assert "Test film" not in off_text and "The trolley runs back" not in off_text.split('id="fr-env">')[1][:200000]


def test_the_labels_point_rides_on_its_part(made):
    """The label's point is stored in its part's node: that node's place at a frame times the point is the point
    on the part in Blender at that frame."""
    sc = made["scene"]
    from fresing_render.core import web3d as core
    on = made["on"]
    doc, _bin = core.read_glb(open(on["path"], "rb").read())
    it = made["st_on"]["films"][0]["labels"]["items"][0]
    c = sc.fresing.callouts[0]
    node = doc["nodes"][it["node"]]
    if "matrix" in node:
        m = np.array(node["matrix"]).reshape(4, 4).T
    else:
        m = np.eye(4)
        m[:3, :3] = core.quat_to_matrix(node.get("rotation", [0, 0, 0, 1]))
        m[:3, :3] *= np.array(node.get("scale", [1, 1, 1]))[None, :]
        m[:3, 3] = node.get("translation", [0, 0, 0])
    here = m @ np.array([*it["at"], 1.0])
    want = np.array(c.part.matrix_world) @ np.array([*c.local, 1.0])
    assert np.linalg.norm(here[:3] - want[:3]) < 1e-4


def test_no_film_without_animation_camera_or_motion(tmp_path):
    sc = crane(tmp_path)
    assert web3d_film.camera(sc) is None
    out = web3d.export(sc, str(tmp_path / "still.glb"), size=512, animation=True)
    assert "films" not in env.page_settings(open(out["html"], encoding="utf-8").read())
    web3d_film.set_up_test(sc, extras=False)
    assert web3d_film.camera(sc) is not None
    out = web3d.export(sc, str(tmp_path / "no_motion.glb"), size=512, animation=False)
    assert "films" not in env.page_settings(open(out["html"], encoding="utf-8").read())
    animation.clear_keys(sc)
    assert web3d_film.camera(sc) is None, "Clear keys: the Animation camera is no longer built"


def test_the_page_shows_blenders_camera(made, tmp_path):
    """The exported page in headless Chromium, in the Film at three moments (a ride, the fly, after the cut): its
    camera is Blender's Animation camera at that frame."""
    from test_web_player import NODE, _browser_works, probe
    if not NODE or not _browser_works(tmp_path):
        pytest.skip("no browser (GitHub's Linux runners): the data is checked above")
    dec_fps = 25.0
    frames = [13, 75, made["cut"][0] - made["frame_start"] + 10]
    steps = [{"eval": "frPage.paused = true, frPage.setFilm(true, false), 0"}]
    for k in frames:
        steps += [{"eval": f"frPage.setTime({k / dec_fps}), 0"}, {"wait": 250}, {"eval": "frPage.filmState()"}]
    out = probe(made["on"]["html"], steps, query="soft=0")
    assert out["ok"], out
    pos, q = F.pose(made["mats"])
    for k, st in zip(frames, out["out"][3::3]):
        assert np.linalg.norm(np.array(st["camPos"]) - pos[k]) <= 1e-3 * made["size"], k
        ang = math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(st["camQuat"], q[k]))))))
        assert ang <= 0.05, (k, ang)
        assert abs(st["vfov"] - made["vfov"][k]) <= 0.05
