"""Task 0142: cables, ropes, coils, hoses and links that the app draws with modifiers move on the web page as they
do in the app. Blender as a Python module; each test model is imported, set up as its own module does it, built, and
exported. What the page draws at a time (``core.web3d_tubes.at``, the twin of ``fr_tubes.js``; node runs the
JavaScript itself, a headless browser the whole page where one works here) is compared with Blender's evaluated
meshes at the same frame.
"""

import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, flex, paths, spool, tracks, web3d, web3d_drawn  # noqa: E402
from fresing_render.core import web3d as core, web3d_env as env, web3d_tubes as T  # noqa: E402

DATA = os.path.join(HERE, "data")
NODE = shutil.which("node")
TUBES_JS = os.path.join(core.WEB_DIR, env.TUBES_FILE)
KEYS = ("times", "lo", "step", "q", "n0", "s0", "pay_t", "pay", "trim_t", "trim", "trim_n0", "s", "slo", "sstep", "nq")


@pytest.fixture(autouse=True, scope="module")
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(model: str, setup, tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, model), quality="normal") == {"FINISHED"}
    out = setup(sc)
    return sc, out


def build(sc):
    a = sc.fresing.animations[sc.fresing.animations_index]
    animation.bake(sc, a)
    sc.frame_set(sc.frame_start)


def export(sc, tmp_path, name="m.glb", **kw):
    job = web3d.Job(sc, str(tmp_path / name), size=256, hide_names=False, **kw)
    out = job.run()
    data = open(out["path"], "rb").read()
    assert core.problems(data) == []
    doc, binary = core.read_glb(data)
    return job, out, doc, binary


def arrays(doc, binary, spec) -> dict:
    a = {}
    for k in KEYS:
        v = spec.get(k)
        if isinstance(v, int) and not isinstance(v, bool):
            a[k] = core.accessor_array(doc, binary, v)
    for k in ("times", "step", "s0", "pay_t", "pay", "trim_t", "s", "slo", "sstep"):
        if k in a:
            a[k] = a[k].reshape(-1)
    return a


def tubes_of(job, doc):
    node_ob = {node: ob for ob, node in job._nodes}
    return {node_ob[k].name: nd["extras"]["fr_tube"] for k, nd in enumerate(doc["nodes"])
            if (nd.get("extras") or {}).get("fr_tube")}


def evaluated(ob) -> np.ndarray:
    me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64)


def compare_tubes(sc, job, doc, binary, frames) -> dict:
    """Worst differences (m) between the page (the Python twin) and the app over ``frames``: ring centres, ring
    points (where no piece is shorter than the page looks past), the cable look's s, paid out."""
    fps = sc.render.fps / sc.render.fps_base
    specs = tubes_of(job, doc)
    worst = {"centre": 0.0, "ring": 0.0, "s": 0.0, "pay": 0.0, "tubes": len(specs)}
    for f in frames:
        sc.frame_set(f)
        for name, spec in specs.items():
            ob = bpy.data.objects[name]
            co = evaluated(ob)
            S = spec["sides"]
            page = T.at(spec, arrays(doc, binary, spec), (f - sc.frame_start) / fps)
            P = page["points"]
            assert len(P) * S == len(co), (name, f, len(P), len(co) // S)
            ring = co.reshape(-1, S, 3)
            worst["centre"] = max(worst["centre"], float(np.linalg.norm(ring.mean(1) - P, axis=1).max()))
            seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
            ok = np.ones(len(P), bool)
            short = np.where(seg < max(float(spec.get("tmin", 0.0)), 1e-9))[0]
            ok[short] = ok[np.minimum(short + 1, len(P) - 1)] = False
            B = np.cross(page["tangents"], page["normals"])
            ph = 2 * math.pi * np.arange(S) / S
            mine = P[:, None] + spec["r"] * (np.cos(ph)[None, :, None] * page["normals"][:, None]
                                            + np.sin(ph)[None, :, None] * B[:, None])
            worst["ring"] = max(worst["ring"], float(np.linalg.norm(mine - ring, axis=2)[ok].max()))
            me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
            cab = me.attributes.get("fr_cable")
            if cab is not None:
                a = np.empty(len(me.vertices) * 3, np.float32)
                cab.data.foreach_get("vector", a)
                worst["s"] = max(worst["s"], float(np.abs(a.reshape(-1, S, 3)[:, 0, 2] - page["s"]).max()))
            pay = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).get("fr_cable_pay")
            if pay is not None:
                worst["pay"] = max(worst["pay"], abs(float(pay) - 2.0 - page["pay"]))
    return worst


def _sample(times, vals, t, rot=False):
    times = np.asarray(times).reshape(-1)
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    k = int(np.searchsorted(times, t, side="right")) - 1
    w = (t - times[k]) / (times[k + 1] - times[k])
    return T.slerp(vals[k], vals[k + 1], np.array([w]))[0] if rot else vals[k] * (1 - w) + vals[k + 1] * w


def compare_rigid(sc, job, doc, binary, frames) -> tuple[int, float]:
    """Parts moved by their modifier (links, pads, riders): the node's place as a viewer plays it, on the part's own
    mesh, against the app's evaluated mesh (world). (count, worst m)."""
    fps = sc.render.fps / sc.render.fps_base
    anim = (doc.get("animations") or [{}])[0]
    chan: dict = {}
    for c in anim.get("channels", []):
        smp = anim["samplers"][c["sampler"]]
        chan.setdefault(c["target"]["node"], {})[c["target"]["path"]] = (
            core.accessor_array(doc, binary, smp["input"]), core.accessor_array(doc, binary, smp["output"]))
    rigid = [(ob, node) for ob, node in job._nodes if job._drawn.kind(ob) == web3d_drawn.RIGID]
    worst = 0.0
    for f in frames:
        sc.frame_set(f)
        t = (f - sc.frame_start) / fps
        for ob, node in rigid:
            nd, ch = doc["nodes"][node], chan.get(node, {})
            if "matrix" in nd:
                m = np.array(nd["matrix"]).reshape(4, 4).T
            else:
                tr = _sample(*ch["translation"], t) if "translation" in ch else np.array(nd.get("translation", [0, 0, 0]))
                q = _sample(*ch["rotation"], t, rot=True) if "rotation" in ch else np.array(nd.get("rotation", [0, 0, 0, 1]))
                m = np.eye(4)
                m[:3, :3] = core.quat_to_matrix(q)[:3, :3]
                m[:3, 3] = tr
            w = np.array(ob.matrix_world)
            app = evaluated(ob) @ w[:3, :3].T + w[:3, 3]
            own = np.empty(len(ob.data.vertices) * 3, np.float32)
            ob.data.vertices.foreach_get("co", own)
            page = own.reshape(-1, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]
            worst = max(worst, float(np.linalg.norm(page - app, axis=1).max()))
    return len(rigid), worst


def node_twin(doc, binary, specs: dict, times) -> list:
    """fr_tubes.js run by node on the file's own arrays at ``times``: [{name, t, points, s, pay}]."""
    payload = {"jobs": [[name, spec, {k: v.ravel().tolist() for k, v in arrays(doc, binary, spec).items()}]
                        for name, spec in specs.items()], "ts": list(times)}
    code = ("const F=require(%s);const J=JSON.parse(require('fs').readFileSync(0,'utf8'));const out=[];"
            "for(const [name,spec,arr] of J.jobs){const a={};for(const k in arr)a[k]=Float64Array.from(arr[k]);"
            "const tb=F.make(spec,a);for(const t of J.ts){tb.at(t);out.push({name,t,"
            "p:Array.from(tb.cp.slice(0,tb.count*3)),s:Array.from(tb.cs.slice(0,tb.count)),pay:tb.pay});}}"
            "console.log(JSON.stringify(out));") % json.dumps(TUBES_JS)
    res = subprocess.run([NODE, "-e", code], input=json.dumps(payload), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


# ---------------------------------------------------------------------------
# the models
# ---------------------------------------------------------------------------

def test_spool_ropes_cables_and_their_looks(tmp_path):
    """test_spool.step: the drum's wire rope and the carousel's coil wind off, the free wire and power cable run;
    the CAD coils the spools hide are left out; the looks go to the page."""
    sc, _out = fresh("test_spool.step", spool.set_up_test_model, tmp_path)
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    assert out["animated"]
    assert out["drawn"] == {"HIDDEN": 2, "TUBE": 2, "SPOOL": 2}
    names = {ob.get("fr_name") or ob.name for ob, _n in job._nodes}
    assert "WIRE ON DRUM" not in names and "CABLE COIL" not in names          # hidden by the spools
    specs = tubes_of(job, doc)
    kinds = {name: spec["look"]["kind"] for name, spec in specs.items()}
    assert kinds == {"WIRE ROPE": "ROPE", "POWER CABLE": "POWER", "FR spool Drum": "ROPE",
                     "FR spool Carousel": "POWER"}
    assert all("trim_t" in specs[n] and specs[n].get("spool") for n in ("FR spool Drum", "FR spool Carousel"))
    assert "pay_t" in specs["POWER CABLE"]
    w = compare_tubes(sc, job, doc, binary, [1, 57, 101, 160, 201])
    assert w["centre"] < 0.002 and w["ring"] < 0.003 and w["s"] < 0.002 and w["pay"] < 0.002, w
    # a compressed file (meshopt, as big models are): the same shapes
    jobc, outc, docc, binc = export(sc, tmp_path, "packed.glb", animation=True, compress=True)
    assert outc["compressed"] and outc["size"] < out["size"]
    w = compare_tubes(sc, jobc, docc, binc, [57, 160])
    assert w["centre"] < 0.002 and w["ring"] < 0.003, w
    if NODE:
        twin = node_twin(doc, binary, specs, [0.0, 2.3, 4.0, 8.0])
        for r in twin:
            spec = specs[r["name"]]
            py = T.at(spec, arrays(doc, binary, spec), r["t"])
            assert np.abs(np.array(r["p"]).reshape(-1, 3) - py["points"]).max() < 1e-7, r["name"]
            assert np.abs(np.array(r["s"]) - py["s"]).max() < 1e-7 and abs(r["pay"] - py["pay"]) < 1e-9
    # without the animation: the frame shown, still with its looks (one moment each)
    sc.frame_set(101)
    job2, out2, doc2, bin2 = export(sc, tmp_path, "still.glb", animation=False)
    still = tubes_of(job2, doc2)
    assert set(still) == set(specs) and all(s.get("k", 1) == 1 and "times" not in s for s in still.values())
    w = compare_tubes(sc, job2, doc2, bin2, [101])
    assert w["centre"] < 0.002 and w["ring"] < 0.003, w


def test_tracks_links_and_pads_move(tmp_path):
    """test_tracks.step: the links and pads of both tracks and the belt run round their wheels on the page; their
    motion is plain node animation, thinned to what a blend cannot give."""
    sc, _out = fresh("test_tracks.step", tracks.set_up_test_model, tmp_path)
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    assert out["drawn"].get("RIGID", 0) == 146 and out["animated"]
    kept, full = out["motion_keys"]
    assert kept < full / 2, out["motion_keys"]
    count, worst = compare_rigid(sc, job, doc, binary, [1, 40, 77, 133, 201])
    assert count == 146 and worst < 0.003, worst
    w = compare_tubes(sc, job, doc, binary, [1, 100, 201])
    assert w["tubes"] == 1 and w["centre"] < 0.002, w                  # the cable between the tracks


def test_cable_into_the_sea_and_lift_wire(tmp_path):
    """test_moving.step: the cable is let go and settles on the seabed (its own lengths along it differ from the
    chords there: kept in the file), the lift wire is kept tight by its winch."""
    sc, _out = fresh("test_moving.step", paths.set_up_moving_model, tmp_path)
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert set(specs) == {"CABLE", "LIFT WIRE"} and "slo" in specs["CABLE"]
    w = compare_tubes(sc, job, doc, binary, [1, 120, 231, 260, 289])
    assert w["centre"] < 0.002 and w["ring"] < 0.004 and w["s"] < 0.002 and w["pay"] < 0.002, w


def _hoses(sc):
    out = flex.set_up_test_hoses(sc)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Luff", 0.0, "25"
    for start, to in ((0.0, 25.0), (2.0, -10.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Luff", start, 2.0, "SMOOTH"
        b.use_from = True
        b.to_angle = math.radians(to)
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return out


def test_hoses_follow_the_arm(tmp_path):
    """test_flex_hoses_a.step: the hoses bend as the arm luffs. Not animated, a plain hose is its drawn shape at the
    frame shown and nothing more (no cost)."""
    sc, _out = fresh("test_flex_hoses_a.step", _hoses, tmp_path)
    job0, out0, doc0, _b0 = export(sc, tmp_path, "plain.glb", animation=False)
    assert tubes_of(job0, doc0) == {} and out0["drawn"] == {"TUBE": 4}
    meshes = {m["name"] for m in doc0["meshes"]}
    assert sum(name.startswith(web3d_drawn.COPY) for name in meshes) == 4      # the app's tubes, not the CAD hoses
    assert not [m for m in bpy.data.meshes if m.name.startswith(web3d_drawn.COPY)]    # the copies are gone again
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert len(specs) == 4 and all("look" not in s and s["k"] > 2 for s in specs.values())
    w = compare_tubes(sc, job, doc, binary, [1, 30, 50, 75, 101])
    assert w["centre"] < 0.002 and w["ring"] < 0.003, w


def _chains(sc):
    out = flex.set_up_test_chains(sc)
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Gantry", 0.0, "25"
    for joint, to in (("X", 0.3), ("Y", 0.2)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", joint, 0.0, 3.0, "SMOOTH"
        b.use_from = True
        b.to_dist = to
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return out


def test_drag_chain_links_follow(tmp_path):
    sc, _out = fresh("test_flex_chains_a.step", _chains, tmp_path)
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    count, worst = compare_rigid(sc, job, doc, binary, [1, 20, 40, 76])
    assert count >= 40 and worst < 0.003, (count, worst)


def test_page_draws_the_moving_cables(tmp_path):
    """The whole page in a headless browser (where one works here): no error, the drawn tubes' centre lines
    (``?tubes=1``) where the app has them at three moments. Elsewhere: the page's scripts parse (node)."""
    sc, _out = fresh("test_spool.step", spool.set_up_test_model, tmp_path)
    build(sc)
    job, out, doc, binary = export(sc, tmp_path, "page.glb", animation=True, page=True)
    html = open(out["html"], encoding="utf-8").read()
    assert "FRTubes" in html and "setupTubes" in html
    browser = env.find_browser()
    works = False
    if browser:
        try:
            first = env.read_page(out["html"], browser, "auto=0&frames=2&t=0&tubes=1", seconds=180)
            works = first["state"].startswith("ready")
        except RuntimeError:
            works = False
    if not works:
        if NODE:
            for name in (env.TUBES_FILE, env.PAGE_FILE):
                subprocess.run([NODE, "--check", os.path.join(core.WEB_DIR, name)], check=True)
        return
    fps = sc.render.fps / sc.render.fps_base
    for f in (1, 101, 200):          # (the page repeats the animation: its very end shows its start)
        got = env.read_page(out["html"], browser, f"auto=0&frames=2&t={(f - 1) / fps}&tubes=1", seconds=180)
        assert got["state"].startswith("ready"), got["state"]
        assert got["tubes"] and len(got["tubes"]) == 4
        sc.frame_set(f)
        for tb in got["tubes"]:
            name = next(n for n in ("WIRE ROPE", "POWER CABLE", "FR spool Drum", "FR spool Carousel")
                        if n.replace(" ", "_") == tb["name"] or n == tb["name"])
            ob = bpy.data.objects[name]
            co = evaluated(ob)
            spec = tubes_of(job, doc)[name]
            cen = co.reshape(-1, spec["sides"], 3).mean(1)
            w = np.array(ob.matrix_world)
            cen = cen @ w[:3, :3].T + w[:3, 3]
            assert tb["count"] == len(cen), (name, f)
            pts = np.array(tb["points"])
            d = np.linalg.norm(pts[:, None] - cen[None], axis=2).min(axis=1)
            assert d.max() < 0.003, (name, f, d.max())


def test_served_cable_look_on_the_page(tmp_path):
    """Task 0158: the power cable and its carousel coil with the served look: the page gets the yarn and the bands
    (the app's numbers), and the page draws them (its shader compiles: the state is "ready", no error)."""
    from fresing_render.blender import cable_looks
    sc, _out = fresh("test_spool.step", spool.set_up_test_model, tmp_path)
    it = next(i for i in paths.items(sc) if i.part.get("fr_name") == "POWER CABLE")
    it.look = "SERVED"
    it = next(i for i in paths.items(sc) if i.part.get("fr_name") == "POWER CABLE")
    it.wear, it.band_count = 0.6, "SINGLE"
    sc.frame_set(sc.frame_start)
    job, out, doc, binary = export(sc, tmp_path, "page.glb", animation=False, page=True)
    specs = tubes_of(job, doc)
    want = cable_looks._served(*(list(it.part[k]) for k in (cable_looks.LOOK, cable_looks.YARN, cable_looks.BAND)))
    for name in ("POWER CABLE", "FR spool Carousel"):
        lk = specs[name]["look"]
        assert lk["kind"] == "SERVED", name
        assert lk["yarn_starts"] == want["starts"] and lk["count"] == 1 and lk["wear"] == pytest.approx(0.6), name
        assert lk["pitch"] == pytest.approx(want["distance"]) and lk["width"] == pytest.approx(want["width"])
        assert lk["yarn_pitch"] == pytest.approx(want["yarn_pitch"]) and lk["radius"] == pytest.approx(want["radius"])
        assert lk["yarn"] == pytest.approx(list(it.yarn_color), abs=1e-6) and len(lk["band"]) == 3
    assert specs["WIRE ROPE"]["look"]["kind"] == "ROPE"
    browser = env.find_browser()
    if not browser:
        if NODE:
            subprocess.run([NODE, "--check", os.path.join(core.WEB_DIR, env.PAGE_FILE)], check=True)
        return
    got = env.read_page(out["html"], browser, "auto=0&frames=2&t=0&tubes=1", seconds=180)
    assert got["state"].startswith("ready"), got["state"]
    assert got["tubes"] and len(got["tubes"]) == 4
