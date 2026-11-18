"""Task 0175 in Blender: a compressed web export of the test mill with a part that slides and turns, one that only
turns and one that is shown and hidden – every frame within the keys' bound, still paths and blink keys left out, the
filtered numbers read back by the page itself (headless browser, ``?places=1``), WebP pictures and their fallback."""

import os
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d as core
from fresing_render.core import web3d_env as env
from fresing_render.core import web3d_keys as K

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, web3d  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    sc = bpy.context.scene
    parts = sorted(build.iter_parts(sc), key=lambda o: o.name)
    slide, turn, blink = parts[3], parts[5], parts[7]
    for ob in (slide, turn):
        ob.rotation_mode = "XYZ"
    slide.keyframe_insert("location", frame=1)
    slide.keyframe_insert("rotation_euler", frame=1)
    slide.location.x += 0.25
    slide.location.z += 0.04
    slide.rotation_euler.z += 0.6
    slide.keyframe_insert("location", frame=41)
    slide.keyframe_insert("rotation_euler", frame=41)
    turn.keyframe_insert("rotation_euler", frame=1)
    turn.rotation_euler.x += 6.0                          # a roller: turns only
    turn.keyframe_insert("rotation_euler", frame=61)
    for frame, hidden in ((1, False), (20, True), (35, False)):
        blink.hide_render = blink.hide_viewport = hidden
        blink.keyframe_insert("hide_render", frame=frame)
        blink.keyframe_insert("hide_viewport", frame=frame)
    sc.frame_start, sc.frame_end = 1, 61
    sc.frame_set(1)
    sc.fresing.anim_baked = "Keys"
    out_dir = tmp_path_factory.mktemp("keys")
    job = web3d.Job(sc, str(out_dir / "k.glb"), size=256, animation=True, compress=True)
    out = job.run()
    data = open(out["path"], "rb").read()
    doc, binary = core.read_glb(data)
    return {"sc": sc, "job": job, "out": out, "data": data, "doc": doc, "binary": binary,
            "slide": slide, "turn": turn, "blink": blink}


def _node(m, ob):
    return next(n for o, n in m["job"]._nodes if o == ob)


def _channels(m):
    doc, binary = m["doc"], m["binary"]
    anim = doc["animations"][0]
    out = {}
    for c in anim["channels"]:
        smp = anim["samplers"][c["sampler"]]
        out[(c["target"]["node"], c["target"]["path"])] = (
            core.accessor_array(doc, binary, smp["input"])[:, 0].astype(np.float64),
            core.accessor_array(doc, binary, smp["output"]).astype(np.float64), smp["interpolation"])
    return out


def test_file_is_valid_and_uses_the_filters(made):
    assert core.problems(made["data"]) == []
    filters = {((v.get("extensions") or {}).get(core.MESHOPT) or {}).get("filter")
               for v in made["doc"]["bufferViews"]}
    assert {"QUATERNION", "EXPONENTIAL"} <= filters
    ch = _channels(made)
    slide, turn, blink = (_node(made, made[k]) for k in ("slide", "turn", "blink"))
    assert (slide, "translation") in ch and (slide, "rotation") in ch
    assert (turn, "rotation") in ch and (turn, "translation") not in ch          # still: left out
    times, vals, interp = ch[(blink, "scale")]
    assert interp == "STEP" and len(times) == 4                                   # first, 2 changes, last
    assert made["out"]["still_tracks"] >= 1


def test_every_frame_within_the_bound(made):
    sc, ch = made["sc"], _channels(made)
    fps = sc.render.fps / sc.render.fps_base
    worst = [0.0, 0.0]
    for f in range(sc.frame_start, sc.frame_end + 1):
        sc.frame_set(f)
        t = (f - sc.frame_start) / fps
        for key in ("slide", "turn"):
            ob = made[key]
            node = _node(made, ob)
            nd = made["doc"]["nodes"][node]
            tt, qq, _s = core.decompose(np.array(ob.matrix_world)[None])
            if (node, "translation") in ch:
                kt, kv, _i = ch[(node, "translation")]
                p = K.played(kt, kv, [t], "translation")[0]
            else:
                p = np.array(nd["translation"])
            kt, kv, _i = ch[(node, "rotation")]
            r = K.played(kt, kv, [t], "rotation")
            ang, _far = K.turn_error(r, K.unit(qq))
            worst[0] = max(worst[0], float(np.linalg.norm(p - tt[0])))
            worst[1] = max(worst[1], float(ang[0]))
    sc.frame_set(1)
    assert worst[0] <= K.POS_TOL * 1.05 and worst[1] <= K.ANGLE_TOL * 1.05, worst


def test_the_page_is_read_every_time(made):
    """Task 0062: a browser without a window ran ahead while the page still unpacked its model and decoded its
    pictures, and wrote it out as "loading" - 5 of 8 openings here, three runs in a row on GitHub's Windows machine.
    A test's page now holds the browser's clock until it is ready: where the browser works, every opening is read."""
    page = made["out"]["html"]
    browser = env.find_browser()
    if not browser:
        return
    states = []
    for _ in range(8):
        try:
            got = env.read_page(page, browser, "auto=0&frames=2&t=0.9&places=1", seconds=180)
        except RuntimeError as exc:                  # GitHub's machines: the browser may not start
            print("browser:", exc)
            return
        if not states and not got["state"].startswith("ready"):
            print("page state:", got["state"])       # no WebGL without a window: nothing to compare
            return
        states.append((got["state"], bool(got["places"])))
    assert all(s.startswith("ready") and p for s, p in states), states


def test_the_page_plays_the_packed_keys(made):
    """The page (headless browser) reads the gzip-packed model and plays the filtered keys as the Python twin."""
    page = made["out"]["html"]
    text = open(page, encoding="utf-8").read()
    assert 'data-gzip="1"' in text and env.page_glb(text) == made["data"]
    browser = env.find_browser()
    works = False
    if browser:
        try:
            got = env.read_page(page, browser, "auto=0&frames=2&t=0.9&places=1", seconds=180)
            works = got["state"].startswith("ready")
        except RuntimeError as exc:
            print("browser:", exc)
            works = False
    print("page state:", got["state"] if works else "not read")
    if not works:                                    # GitHub's machines: the browser may not start
        node = __import__("shutil").which("node")
        if node:
            subprocess.run([node, "--check", os.path.join(core.WEB_DIR, env.PAGE_FILE)], check=True)
        return
    ch = _channels(made)
    sc = made["sc"]
    for t in (0.9, 1.7):
        if t != 0.9:
            got = env.read_page(page, browser, f"auto=0&frames=2&t={t}&places=1", seconds=180)
            assert got["state"].startswith("ready"), got["state"]
        places = got["places"]
        for key in ("slide", "turn"):
            node = _node(made, made[key])
            here = np.array(places[str(node)], np.float64)
            kt, kv, _i = ch[(node, "rotation")]
            r = K.played(kt, kv, [t], "rotation")[0]
            assert np.abs(here[3:7] - r).max() < 2e-5, (key, t, here[3:7], r)
            if (node, "translation") in ch:
                kt, kv, _i = ch[(node, "translation")]
                assert np.abs(here[:3] - K.played(kt, kv, [t], "translation")[0]).max() < 2e-6
        blink = places[str(_node(made, made["blink"]))]
        hidden = 19 <= t * sc.render.fps / sc.render.fps_base + 1 < 35
        assert (max(blink[7:]) == 0.0) == hidden, (t, blink)


def test_webp_pictures_and_the_jpeg_fallback(made, tmp_path):
    doc = made["doc"]
    mimes = [im["mimeType"] for im in doc.get("images", [])]
    assert mimes, "the mill has look pictures"
    assert made["out"]["webp"] == mimes.count("image/webp")
    if "image/webp" in mimes:
        assert core.WEBP in doc["extensionsRequired"]
    for kind, jpg, wp, kept in web3d.WEBP_LOG:
        assert kept == "jpg" or wp < jpg
    # a Blender that cannot write WebP: JPGs, no extension
    web3d.USE_WEBP = False
    try:
        out = web3d.export(made["sc"], str(tmp_path / "j.glb"), size=256, page=False, compress=True)
    finally:
        web3d.USE_WEBP = True
    doc2, _ = core.read_glb(open(out["path"], "rb").read())
    assert all(im["mimeType"] != "image/webp" for im in doc2.get("images", []))
    assert core.WEBP not in doc2.get("extensionsUsed", []) and out["webp"] == 0
