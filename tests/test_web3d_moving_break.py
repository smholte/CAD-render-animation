"""Task 0142, independent tester: trying to break the moving cables on the web page.

Part 1 (no Blender): ``core/web3d_tubes.py`` and its JavaScript twin ``fresing_render/web/fr_tubes.js`` on edge
cases. Part 2 (Blender as a module): the export of the small test models compared with Blender's own evaluated
meshes, in world coordinates (the node's animation as a viewer plays it, times the page's tube), and exports with
other options.
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

from fresing_render.core import web3d as core, web3d_env as env, web3d_tubes as T  # noqa: E402

NODE = shutil.which("node") or ("/opt/node22/bin/node" if os.path.exists("/opt/node22/bin/node") else None)
TUBES_JS = os.path.join(core.WEB_DIR, env.TUBES_FILE)


# ---------------------------------------------------------------------------
# helpers: the JavaScript twin
# ---------------------------------------------------------------------------

def js_run(jobs, times):
    """fr_tubes.js on [(spec, arrays)] at ``times``: [{count, p, n, t, s, pay, fill}] per job and time."""
    payload = {"jobs": [[sp, {k: np.asarray(v, float).ravel().tolist() for k, v in ar.items()}] for sp, ar in jobs],
               "ts": list(times)}
    code = ("const F=require(%s);const J=JSON.parse(require('fs').readFileSync(0,'utf8'));const out=[];"
            "for(const [spec,arr] of J.jobs){const a={};for(const k in arr)a[k]=Float64Array.from(arr[k]);"
            "const tb=F.make(spec,a);for(const t of J.ts){tb.at(t);const d=tb.fill();out.push({count:tb.count,"
            "p:Array.from(tb.cp.slice(0,tb.count*3)),n:Array.from(tb.nr.slice(0,tb.count*3)),"
            "t:Array.from(tb.tg.slice(0,tb.count*3)),s:Array.from(tb.cs.slice(0,tb.count)),pay:tb.pay,"
            "empty:!!tb.empty,finite:Array.from(d).every(Number.isFinite)});}}console.log(JSON.stringify(out));"
            ) % json.dumps(TUBES_JS)
    res = subprocess.run([NODE, "-e", code], input=json.dumps(payload), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def py_arrays(ar):
    a2 = {key: np.asarray(v, float) for key, v in ar.items()}
    for key in ("lo", "n0", "trim_n0"):
        if key in a2:
            a2[key] = a2[key].reshape(-1, 3)
    if "trim" in a2:
        a2["trim"] = a2["trim"].reshape(-1, 2)
    return a2


def still_spec(p, n0=(0.0, 0.0, 1.0), **kw):
    spec = {"v": 1, "n": len(p), "k": 1, "sides": 8, "r": 0.01, "unit": 1.0}
    spec.update(kw)
    s = T.chords(p)
    return spec, {"lo": np.asarray(p, float), "n0": np.array([n0], float), "s0": s[:1]}


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


# ---------------------------------------------------------------------------
# Part 1: the maths, no Blender
# ---------------------------------------------------------------------------

def test_find_rings_degenerate_inputs_do_not_crash():
    """All points equal, a single ring, too few points, NaN-free: None, never an exception."""
    assert T.find_rings(np.zeros((48, 3))) is None
    assert T.find_rings(np.zeros((0, 3))) is None
    assert T.find_rings(np.zeros((5, 3))) is None
    ph = 2 * math.pi * np.arange(8) / 8
    one = np.c_[np.cos(ph), np.sin(ph), np.zeros(8)] * 0.01
    assert T.find_rings(one) is None                       # one ring is no tube (needs 2)
    two = np.concatenate([one, one + [0, 0, 1.0]])
    got = T.find_rings(two)
    assert got is not None and got[3] == 8 and np.isfinite(got[0]).all()


def test_tangents_and_transport_on_a_180_degree_fold_are_finite():
    p = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [1, 0, 0], [0, 0, 0]], float)
    tg = T.tangents(p)
    nr = T.transport(tg, (0, 0, 1))
    assert np.isfinite(tg).all() and np.isfinite(nr).all()
    assert np.allclose(np.linalg.norm(nr, axis=1), 1.0)
    out = T.at(*still_spec(p), 0.0)
    assert all(np.isfinite(np.asarray(v, float)).all() for v in out.values())


def test_two_point_line_and_all_points_equal():
    for p in (np.array([[0, 0, 0], [0, 0, 1.0]]), np.zeros((6, 3))):
        out = T.at(*still_spec(p, n0=(1.0, 0.0, 0.0)), 0.0)
        assert np.isfinite(out["normals"]).all() and np.isfinite(out["tangents"]).all()
        assert np.allclose(np.linalg.norm(out["normals"], axis=1), 1.0)


@needs_node
def test_js_twin_on_degenerate_lines():
    """The page and the Python twin agree on a 180° fold, a 2-point line and all points equal."""
    lines = [np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [1, 0, 0], [0, 0, 0]], float),
             np.array([[0, 0, 0], [0, 0, 1.0]]), np.zeros((6, 3))]
    jobs = [still_spec(p, n0=(0.0, 1.0, 0.0)) for p in lines[:1]] + [still_spec(p, n0=(1.0, 0.0, 0.0))
                                                                       for p in lines[1:]]
    out = js_run(jobs, [0.0])
    for (sp, ar), js in zip(jobs, out):
        py = T.at(sp, py_arrays(ar), 0.0)
        assert js["finite"]
        assert np.abs(np.array(js["t"]).reshape(-1, 3) - py["tangents"]).max() < 1e-9
        assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-9


@needs_node
def test_js_twin_tangent_on_a_run_of_equal_points():
    """Finding 4 (fixed): a run of equal points (pieces of length 0) leaves points whose tangent is 0. Python
    (``_unit_or_near``) took the next good one ahead, the page the nearest: the twins disagreed there and about every
    ring turn carried past it. Now both take the first good one ahead, else the last good one."""
    a, b, c = np.array([0, 0, 0.0]), np.array([1, 0, 0.0]), np.array([1, 1, 0.0])
    p = np.array([a, b, b, b, b, c])           # pieces: ab, 0, 0, 0, bc -> point 2 has tangent 0; nearest good is 1
    sp, ar = still_spec(p)
    js = js_run([(sp, ar)], [0.0])[0]
    py = T.at(sp, py_arrays(ar), 0.0)
    jt = np.array(js["t"]).reshape(-1, 3)
    assert np.abs(jt - py["tangents"]).max() < 1e-9, (jt[2], py["tangents"][2])
    assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-9
    # a run at the very end (no good one ahead): the last good one, in both
    p2 = np.array([a, b, c, c, c, c])
    sp2, ar2 = still_spec(p2)
    js2 = js_run([(sp2, ar2)], [0.0])[0]
    py2 = T.at(sp2, py_arrays(ar2), 0.0)
    assert np.abs(np.array(js2["t"]).reshape(-1, 3) - py2["tangents"]).max() < 1e-9
    assert np.isfinite(py2["normals"]).all() and js2["finite"]


@needs_node
def test_js_twin_spool_cut_inside_one_piece():
    """Finding 3 (fixed): a spool's cut inside one piece of the wound path (start and end between two points). Python
    invented 2 points, the page kept 1, the app's spool tree keeps 1 (and draws nothing). Now Python keeps 1 like
    the app, and the page hides the tube (``empty``) with a finite texture."""
    p = np.c_[np.arange(6.0), np.zeros(6), np.zeros(6)]
    s = T.chords(p)
    spec = {"v": 1, "n": 6, "k": 1, "sides": 8, "r": 0.01, "unit": 1.0, "spool": True, "pay": 0.0}
    ar = {"lo": p, "s": s, "n0": np.array([[0.0, 0.0, 1.0]]), "s0": s[:1], "trim": np.array([[2.2, 2.6]]),
          "trim_n0": np.array([[0.0, 0.0, 1.0]])}
    js = js_run([(spec, ar)], [0.0])[0]
    py = T.at(spec, py_arrays(ar), 0.0)
    assert js["finite"], "page texture gets NaN"
    assert js["count"] == len(py["points"]) == 1, (js["count"], len(py["points"]))
    assert np.abs(np.array(js["p"]).reshape(-1, 3) - py["points"]).max() < 1e-12
    assert js["empty"]


@needs_node
def test_js_twin_spool_cut_past_the_whole_path_is_finite():
    """Finding 2 (fixed): a cut that keeps no point at all (start past the wound path's end: everything paid out).
    The page's ``fill`` read point -1 and wrote NaN into the tube texture. Now: no point in either twin, the page
    hides the tube, nothing NaN. A moving cut that empties and fills again comes back drawn."""
    p = np.c_[np.arange(6.0), np.zeros(6), np.zeros(6)]
    s = T.chords(p)
    spec = {"v": 1, "n": 6, "k": 1, "sides": 8, "r": 0.01, "unit": 1.0, "spool": True, "pay": 0.0}
    ar = {"lo": p, "s": s, "n0": np.array([[0.0, 0.0, 1.0]]), "s0": s[:1], "trim": np.array([[7.0, 7.0]]),
          "trim_n0": np.array([[0.0, 0.0, 1.0]])}
    js = js_run([(spec, ar)], [0.0])[0]
    assert js["finite"], "NaN in the tube texture when nothing is left on the spool"
    assert js["empty"] and js["count"] == 0
    py = T.at(spec, py_arrays(ar), 0.0)
    assert len(py["points"]) == 0 and py["normals"].shape == (0, 3)
    # wound, empty, wound again
    ar2 = dict(ar, trim_t=np.array([0.0, 1.0, 2.0]), trim=np.array([[0.5, 4.5], [7.0, 7.0], [1.0, 3.5]]),
               trim_n0=np.array([[0.0, 0.0, 1.0]] * 3))
    ts = [0.0, 0.5, 0.99, 1.0, 1.01, 1.5, 2.0]
    res = js_run([(spec, ar2)], ts)
    for t, r in zip(ts, res):
        py = T.at(spec, py_arrays(ar2), t)
        assert r["finite"] and r["count"] == len(py["points"]) and r["empty"] == (len(py["points"]) < 2), t
        if len(py["points"]):
            assert np.abs(np.array(r["p"]).reshape(-1, 3) - py["points"]).max() < 1e-9
    assert not res[0]["empty"] and res[3]["empty"] and not res[-1]["empty"]


@needs_node
def test_js_twin_random_specs():
    """Random moving tubes with every optional array (tmin, nq, slo/sq, pay_t, times not starting at 0): the page's
    JavaScript and the Python twin agree."""
    rng = np.random.default_rng(42)
    jobs, times_all = [], np.linspace(-0.5, 7.0, 23)
    for case in range(6):
        n = int(rng.integers(5, 40))
        k = int(rng.integers(2, 6))
        base = np.cumsum(rng.normal(size=(n, 3)) * 0.3, axis=0)
        pts = np.stack([base + rng.normal(size=(n, 3)) * 0.05 * j for j in range(k)])
        if case == 5:
            pts[:, :] += np.linspace(0.0, 200.0, k)[:, None, None]        # a long travel: 32-bit fallback
        sa = np.cumsum(rng.uniform(0.1, 0.5, (k, n)), axis=1) if case % 3 == 2 else None
        lo, step, slo, sstep, q = T.pack(pts, s=sa, max_step=T.POS_TOL if case >= 4 else None)
        tm = np.sort(rng.uniform(0.5, 6.0, k))
        tm[0] = 0.5 + case * 0.1                                  # not starting at 0
        spec = {"v": 1, "n": n, "k": k, "sides": 8, "r": 0.02, "unit": 1.0}
        if case % 2 and q.dtype == np.uint16:
            spec["tmin"] = float(32 * step.max())
        ar = {"times": tm, "lo": lo, "step": step, "q": q.reshape(-1, 4), "n0": rng.normal(size=(k, 3)),
              "s0": rng.uniform(0, 3, k), "pay_t": tm, "pay": rng.uniform(0, 5, k)}
        if case % 3 == 1:
            nr = rng.normal(size=(k, n, 3))
            ar["nq"] = T.oct_encode(nr / np.linalg.norm(nr, axis=2, keepdims=True)).reshape(-1, 2)   # key-major
        if sa is not None:
            ar.update(slo=slo, sstep=sstep)
        jobs.append((spec, ar))
    assert jobs[5][1]["q"].dtype == np.float32                    # the long travel took the 32-bit fallback
    out = js_run(jobs, times_all)
    i = 0
    for sp, ar in jobs:
        a2 = py_arrays(ar)
        for t in times_all:
            py = T.at(sp, a2, float(t))
            js = out[i]
            i += 1
            assert js["finite"]
            assert np.abs(np.array(js["p"]).reshape(-1, 3) - py["points"]).max() < 1e-7
            assert np.abs(np.array(js["s"]) - py["s"]).max() < 1e-7
            assert np.abs(np.array(js["t"]).reshape(-1, 3) - py["tangents"]).max() < 1e-6, (sp, t)
            assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-6, (sp, t)
            assert js["pay"] == pytest.approx(py["pay"], abs=1e-9)


def test_thin_one_and_two_frames_and_late_times():
    x1 = np.zeros((1, 3, 3))
    assert list(T.thin_frames(x1, 0.001)) == [0]
    x2 = np.zeros((2, 3, 3))
    x2[1] += 1
    assert list(T.thin_frames(x2, 0.001)) == [0, 1]
    f = np.arange(50.0)
    z = np.sin(f / 5.0)[:, None, None] * np.ones((50, 2, 3))
    tm = 100.0 + f / 25.0                                      # times not starting at 0
    k = T.thin_frames(z, 0.001, tm)
    back = np.array([T.blend_at(tm[k], z[k], t) for t in tm])
    assert np.abs(back - z).max() <= 0.001 + 1e-6
    # thin_node with one and two moments
    assert list(T.thin_node(np.zeros((1, 3)), np.array([[0, 0, 0, 1.0]]))) == [0]
    assert list(T.thin_node(np.zeros((2, 3)), np.array([[0, 0, 0, 1.0]] * 2))) == [0, 1]


def test_thin_node_quaternion_sign_flips():
    """Every other moment's quaternion with the other sign (the same turn): the thinning must not see a turn there
    and the kept moments must play back within 1 mm (three.js slerps the short way)."""
    f = np.arange(120)
    ang = f * 0.02
    q = np.c_[np.zeros(120), np.zeros(120), np.sin(ang / 2), np.cos(ang / 2)]
    q[1::2] *= -1
    t = np.c_[f * 0.01, np.zeros(120), np.zeros(120)]
    k = T.thin_node(t, q, reach=1.0)
    assert len(k) < 30
    for a, b in zip(k[:-1], k[1:]):
        w = (f[a:b + 1] - a) / max(b - a, 1)
        qq = T.slerp(q[a], q[b], w)
        err = 2 * np.arccos(np.clip(np.abs((qq * q[a:b + 1]).sum(axis=1)), -1, 1)) * 1.0
        assert err.max() <= 0.001 + 1e-6


def test_thin_node_half_turn_between_frames_is_kept():
    """A part that turns 170° per frame: no two moments may be dropped so that the short way goes the wrong way."""
    f = np.arange(20)
    ang = f * math.radians(170)
    q = np.c_[np.zeros(20), np.zeros(20), np.sin(ang / 2), np.cos(ang / 2)]
    k = T.thin_node(np.zeros((20, 3)), q, reach=1.0)
    assert len(k) == 20


def test_pack_keeps_a_long_travel_within_the_tolerance():
    """Finding 5 (fixed): ``pack`` stored each point as 16 bits over its own range over time: a point travelling
    300 m got 4.6 mm steps and was up to 2.4 mm off (POS_TOL 1 mm). With ``max_step`` (the export passes
    POS_TOL / unit) a range too big for 16 bits goes in as 32-bit numbers; a small one stays 16-bit."""
    f = np.linspace(0.0, 1.0, 5)
    line = np.c_[np.linspace(0, 10, 20), np.zeros(20), np.zeros(20)]
    pts = np.stack([line + [300.0 * w + 0.000123 * (i + 1), 0.000371 * i, 0.0] for i, w in enumerate(f)])
    sa = T.chords(line)[None] + 300.0 * f[:, None]
    lo, step, slo, sstep, q = T.pack(pts, s=sa, max_step=T.POS_TOL)
    assert q.dtype == np.float32 and q.shape == (5, 20, 4)
    back = T.unpack(lo, step, q, len(pts))
    err = float(np.linalg.norm(back - pts, axis=2).max())
    assert err <= T.POS_TOL, f"points off by {err * 1000:.2f} mm"
    assert np.abs(T.unpack_s(slo, sstep, q, len(pts)) - sa).max() <= T.S_TOL
    # a 10 m travel stays 16-bit and within the tolerance
    small = pts.copy()
    small[..., 0] = line[None, :, 0] + 10.0 * f[:, None]
    lo, step, slo, sstep, q = T.pack(small, max_step=T.POS_TOL)
    assert q.dtype == np.uint16 and slo is None
    assert float(np.linalg.norm(T.unpack(lo, step, q, 5) - small, axis=2).max()) <= T.POS_TOL


def test_pack_far_from_origin():
    """A cable part whose own coordinates lie far from its origin (CAD assemblies are often drawn metres from 0):
    lo is float32, so at 5 km a point is off by 0.5 mm already, at 20 km by 2 mm."""
    pts = np.stack([np.c_[np.linspace(0, 1, 10), np.zeros(10), np.zeros(10)] + [5000.0, 0, 0]] * 1)
    lo, step, _slo, _sstep, q = T.pack(pts)
    back = T.unpack(lo, step, q, 1)
    assert np.abs(back - pts).max() <= T.POS_TOL


def test_trimmed_matches_the_spool_tree_on_the_ends():
    """The cut at the wound path's very ends: lo before the first point, hi past the last."""
    p = np.c_[np.arange(6.0), np.zeros(6), np.zeros(6)]
    s = T.chords(p)
    pts, ss = T.trimmed(p, s, -1.0, 9.0)
    assert len(pts) == 6 and list(ss) == list(s)
    pts, ss = T.trimmed(p, s, 0.0, 0.0)                       # empty rope at the start: point 0 and point 1 onto it
    assert np.isfinite(pts).all() and len(pts) >= 2


# ---------------------------------------------------------------------------
# Part 2: Blender as a module – the page against the app, in world coordinates
# ---------------------------------------------------------------------------

KEYS = ("times", "lo", "step", "q", "n0", "s0", "pay_t", "pay", "trim_t", "trim", "trim_n0", "s", "slo", "sstep",
        "nq")
DATA = os.path.join(HERE, "data")


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    pytest.importorskip("OCP")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def fresh(bpy, model, setup, tmp_path):
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, model), quality="normal") == {"FINISHED"}
    setup(sc)
    return sc


def build_anim(sc):
    from fresing_render.blender import animation
    a = sc.fresing.animations[sc.fresing.animations_index]
    animation.bake(sc, a)
    sc.frame_set(sc.frame_start)


def export(sc, tmp_path, name="m.glb", **kw):
    from fresing_render.blender import web3d
    kw.setdefault("hide_names", False)
    job = web3d.Job(sc, str(tmp_path / name), size=256, **kw)
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
    for k in ("times", "step", "s0", "pay_t", "pay", "trim_t", "s", "slo", "sstep", "sq"):
        if k in a:
            a[k] = a[k].reshape(-1)
    return a


def tubes_of(job, doc):
    node_ob = {node: ob for ob, node in job._nodes}
    return {node_ob[k].name: (k, nd["extras"]["fr_tube"]) for k, nd in enumerate(doc["nodes"])
            if (nd.get("extras") or {}).get("fr_tube") and k in node_ob}


def channels(doc, binary) -> dict:
    out: dict = {}
    for anim in doc.get("animations", []):
        for c in anim["channels"]:
            smp = anim["samplers"][c["sampler"]]
            out.setdefault(c["target"]["node"], {})[c["target"]["path"]] = (
                core.accessor_array(doc, binary, smp["input"]).reshape(-1),
                core.accessor_array(doc, binary, smp["output"]), smp.get("interpolation", "LINEAR"))
    return out


def _sample(times, vals, interp, t, rot=False):
    if t <= times[0]:
        return vals[0]
    if t >= times[-1]:
        return vals[-1]
    k = int(np.searchsorted(times, t, side="right")) - 1
    if interp == "STEP":
        return vals[k]
    w = (t - times[k]) / (times[k + 1] - times[k])
    return T.slerp(vals[k], vals[k + 1], np.array([w]))[0] if rot else vals[k] * (1 - w) + vals[k + 1] * w


def node_matrix(doc, chans, node, t) -> np.ndarray:
    """The node's place (Blender coordinates, under the model's Y-up root) as a viewer plays it at ``t``."""
    nd, ch = doc["nodes"][node], chans.get(node, {})
    if "matrix" in nd and not ch:
        return np.array(nd["matrix"]).reshape(4, 4).T
    tr = _sample(*ch["translation"], t) if "translation" in ch else np.array(nd.get("translation", [0, 0, 0]))
    q = _sample(*ch["rotation"], t, rot=True) if "rotation" in ch else np.array(nd.get("rotation", [0, 0, 0, 1]))
    s = _sample(*ch["scale"], t) if "scale" in ch else np.array(nd.get("scale", [1, 1, 1]))
    m = np.eye(4)
    m[:3, :3] = core.quat_to_matrix(q)[:3, :3] @ np.diag(s)
    m[:3, 3] = tr
    return m


def evaluated(bpy, ob):
    me = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).astype(np.float64), me


def prim_of(doc, node):
    """The first primitive a part's node shows (its own mesh, or the child that turns 16-bit points back)."""
    nd = doc["nodes"][node]
    mesh = nd["mesh"] if "mesh" in nd else doc["nodes"][nd["children"][0]]["mesh"]
    return doc["meshes"][mesh]["primitives"][0]


def world(m, p):
    m = np.asarray(m, np.float64)
    return p @ m[:3, :3].T + m[:3, 3]


def compare_world(bpy, sc, job, doc, binary, frames, names=None) -> dict:
    """Worst differences (m) between the page (node place as played x the tube's ``at``) and the app's evaluated
    rings in world coordinates; also s and pay where the app has them; ``count`` mismatches listed."""
    fps = sc.render.fps / sc.render.fps_base
    specs = tubes_of(job, doc)
    chans = channels(doc, binary)
    worst = {"centre": 0.0, "s": 0.0, "pay": 0.0, "count": [], "where": None}
    for f in frames:
        sc.frame_set(int(f), subframe=float(f) - int(f))
        t = (f - sc.frame_start) / fps
        for name, (node, spec) in specs.items():
            if names is not None and name not in names:
                continue
            ob = bpy.data.objects[name]
            co, me = evaluated(bpy, ob)
            S = spec["sides"]
            page = T.at(spec, arrays(doc, binary, spec), t)
            P = world(node_matrix(doc, chans, node, t), page["points"])
            if len(co) != len(P) * S:
                worst["count"].append((name, f, len(P), len(co) / S))
                continue
            app = world(np.array(ob.matrix_world), co.reshape(-1, S, 3).mean(1))
            d = float(np.linalg.norm(app - P, axis=1).max())
            if d > worst["centre"]:
                worst["centre"], worst["where"] = d, (name, f)
            cab = me.attributes.get("fr_cable")
            if cab is not None and spec.get("look") is not None:
                a = np.empty(len(me.vertices) * 3, np.float32)
                cab.data.foreach_get("vector", a)
                worst["s"] = max(worst["s"], float(np.abs(a.reshape(-1, S, 3)[:, 0, 2] - page["s"]).max()))
            pay = ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).get("fr_cable_pay")
            if pay is not None and spec.get("look") is not None:
                worst["pay"] = max(worst["pay"], abs(float(pay) - 2.0 - page["pay"]))
    return worst


def spool_model(sc):
    from fresing_render.blender import spool
    return spool.set_up_test_model(sc)


def _part(bpy, name):
    from fresing_render.blender import build
    for ob in bpy.context.scene.objects:
        if ob.get(build.PROP_NAME) == name:
            return ob
    raise KeyError(name)


def test_spool_world_names_hidden_compressed(blender, tmp_path):
    """test_spool.step exported with names hidden and compressed: the file reads back, every tube is there, the page
    (node place as played x tube) matches the app in world coordinates, and the page itself runs (headless)."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    build_anim(sc)
    job, out, doc, binary = export(sc, tmp_path, "hidden.glb", animation=True, hide_names=True, compress=True,
                                   page=True)
    assert out["compressed"]
    specs = tubes_of(job, doc)
    assert set(specs) == {"WIRE ROPE", "POWER CABLE", "FR spool Drum", "FR spool Carousel"}
    assert not any("WIRE" in (nd.get("name") or "") or "CABLE" in (nd.get("name") or "") for nd in doc["nodes"])
    w = compare_world(bpy, sc, job, doc, binary, [1, 37, 50.5, 101, 150.5, 163, 200])    # also between frames
    assert not w["count"], w
    assert w["centre"] < 0.003 and w["s"] < 0.003 and w["pay"] < 0.003, w
    browser = env.find_browser()
    if not browser:
        return
    fps = sc.render.fps / sc.render.fps_base
    f = 101
    try:
        got = env.read_page(out["html"], browser, f"auto=0&frames=2&t={(f - 1) / fps}&tubes=1", seconds=120)
    except RuntimeError:
        return
    assert got["state"].startswith("ready"), got["state"]
    assert got["tubes"] and len(got["tubes"]) == 4
    sc.frame_set(f)
    apps = []
    for name, (node, spec) in specs.items():
        ob = bpy.data.objects[name]
        co, _me = evaluated(bpy, ob)
        apps.append(world(np.array(ob.matrix_world), co.reshape(-1, spec["sides"], 3).mean(1)))
    for tb in got["tubes"]:
        pts = np.array(tb["points"])
        best = min(float(np.linalg.norm(pts[:, None] - a[None], axis=2).min(axis=1).max()) for a in apps)
        assert best < 0.003, (tb["name"], best)


def test_spool_rope_empty_at_the_frame_shown(blender, tmp_path):
    """Finding 1 (fixed): a winch that hauls a rope in from fully paid out. At the frame shown (the animation's start)
    the drum holds no rope, so its evaluated rope is empty; it was sorted HIDDEN and left out of the web model for the
    whole animation, while the app winds 72 m onto the drum. Now it is sorted where it is first drawn; the page
    draws nothing while the drum is empty and the app's rope once it holds some."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    sm = bpy.data.objects["FR spool shapes Drum"].data
    L = np.empty(len(sm.vertices), np.float32)
    sm.attributes["fr_L"].data.foreach_get("value", L)
    a = sc.fresing.animations[sc.fresing.animations_index]
    b = a.blocks[0]                                       # the wire: from all paid out back onto the drum
    b.use_from = False
    b.from_dist = float(L.max()) + 1.0
    b.to_dist = 0.0
    build_anim(sc)
    rope = bpy.data.objects["FR spool Drum"]
    assert len(evaluated(bpy, rope)[0]) == 0               # empty at the frame shown
    sc.frame_set(201)
    assert len(evaluated(bpy, rope)[0]) > 1000             # the app draws it wound later
    sc.frame_set(1)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert "FR spool Drum" in specs, ("the drum's rope is not in the web model", out["drawn"])
    node, spec = specs["FR spool Drum"]
    assert len(T.at(spec, arrays(doc, binary, spec), 0.0)["points"]) < 2      # empty at the start: not drawn
    if NODE:
        js = js_run([(spec, arrays(doc, binary, spec))], [0.0, 4.0])
        assert js[0]["empty"] and js[0]["finite"] and not js[1]["empty"]
    # (frames 67, 75, 98 show the start-ring finding of test_spool_rope_keeps_its_first_ring_every_frame)
    w = compare_world(bpy, sc, job, doc, binary, [101, 150, 201], names={"FR spool Drum"})
    assert not w["count"] and w["centre"] < 0.003 and w["s"] < 0.003, w
    sc.frame_set(1)                                        # without the animation at the empty frame: left out
    job2, out2, doc2, _b2 = export(sc, tmp_path, "still.glb", animation=False)
    assert "FR spool Drum" not in tubes_of(job2, doc2)


def test_spool_rope_keeps_its_first_ring_every_frame(blender, tmp_path):
    """FINDING (new, after the fixes; also on the unchanged test model): the spool rope's cut starts exactly at a
    point of the wound path (the anchor: Start = that point's s, the same at every moment). The page blends the cut
    between its kept moments, ``lo * (1 - w) + lo * w``, which in float64 lands a hair past the float32 ``s`` of
    that point (-27.145019531249996 > -27.14501953125), so ``s < lo`` drops it: on about one frame in 15 the page's
    rope has one ring fewer at its start than the app (carousel: 7 of 201 frames, the rope's end jumps 69 mm; drum:
    8 frames, 2.9 mm). The JavaScript twin does the same."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    build_anim(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    fps = sc.render.fps / sc.render.fps_base
    frames = list(range(1, 202))
    bad = []
    js_counts = {}
    for name in ("FR spool Drum", "FR spool Carousel"):
        node, spec = specs[name]
        ar = arrays(doc, binary, spec)
        if NODE:
            js_counts[name] = [r["count"] for r in js_run([(spec, ar)], [(f - 1) / fps for f in frames])]
        for i, f in enumerate(frames):
            sc.frame_set(f)
            co, _me = evaluated(bpy, bpy.data.objects[name])
            n_app = len(co) // spec["sides"]
            n_py = len(T.at(spec, ar, (f - 1) / fps)["points"])
            n_js = js_counts[name][i] if name in js_counts else n_py
            if not n_app == n_py == n_js:
                bad.append((name, f, n_app, n_py, n_js))
    assert not bad, f"{len(bad)} frames with another ring count (name, frame, app, python, page): {bad[:6]}"


def test_cable_shown_later_by_a_show_step(blender, tmp_path):
    """The power cable hidden at the start (a Hide step at 0 s) and shown by a Show step at 3 s: exported at the
    first frame, it must still move on the page once shown."""
    from fresing_render.blender import build
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    cable = _part(bpy, "POWER CABLE")
    a = sc.fresing.animations[sc.fresing.animations_index]
    for kind, start in (("HIDE", 0.0), ("SHOW", 3.0)):
        blk = a.blocks.add()
        blk.kind, blk.start, blk.duration = kind, start, 0.1
        blk.target_name, blk.target_uid = cable.name, cable.get(build.PROP_UID, "")
    build_anim(sc)
    assert not cable.visible_get() or cable.hide_render
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert "POWER CABLE" in specs, out["drawn"]
    w = compare_world(bpy, sc, job, doc, binary, [101, 160, 200], names={"POWER CABLE"})
    assert not w["count"] and w["centre"] < 0.003 and w["s"] < 0.003 and w["pay"] < 0.003, w


def test_scaled_model_root(blender, tmp_path):
    """The whole model under its root scaled by 0.5 (unit != 1 for every drawn part): the page still matches the app
    in world coordinates, the look's s and the metres paid out."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    root = bpy.data.objects["TEST.SPOOL"]
    root.scale = (0.5, 0.5, 0.5)
    bpy.context.view_layer.update()
    build_anim(sc)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert len(specs) == 4, out["drawn"]
    assert all(abs(spec["unit"] - 0.5) < 1e-6 for _n, spec in specs.values())
    w = compare_world(bpy, sc, job, doc, binary, [1, 101, 200])
    assert not w["count"], w
    assert w["centre"] < 0.003 and w["s"] < 0.003 and w["pay"] < 0.003, w


def test_cable_switched_off_and_rebuilt(blender, tmp_path):
    """The power cable switched off (its modifier off: the app shows the CAD cable), the animation built again: no
    fr_tube for it, its node shows the CAD mesh, the other tubes still match."""
    from fresing_render.blender import paths
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    paths.find(sc, "Power cable").enabled = False
    build_anim(sc)
    cable = _part(bpy, "POWER CABLE")
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    specs = tubes_of(job, doc)
    assert "POWER CABLE" not in specs
    node = next(n for ob, n in job._nodes if ob == cable)
    prim = prim_of(doc, node)
    assert doc["accessors"][prim["attributes"]["POSITION"]]["count"] <= len(evaluated(bpy, cable)[0]) * 1.01 + 10
    w = compare_world(bpy, sc, job, doc, binary, [1, 120, 200])
    assert not w["count"] and w["centre"] < 0.003, w


def _gn_tree(bpy, name, mode):
    """A Geometry Nodes tree that moves (``move``: 0.1 m/s along x) or grows (``grow``: scale 1 + 0.1/s) its
    geometry with the scene time."""
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gi, go = ng.nodes.new("NodeGroupInput"), ng.nodes.new("NodeGroupOutput")
    tr = ng.nodes.new("GeometryNodeTransform")
    st = ng.nodes.new("GeometryNodeInputSceneTime")
    if mode == "move":
        vm = ng.nodes.new("ShaderNodeVectorMath")
        vm.operation = "SCALE"
        vm.inputs[0].default_value = (0.1, 0.0, 0.0)
        ng.links.new(st.outputs["Seconds"], vm.inputs["Scale"])
        ng.links.new(vm.outputs[0], tr.inputs["Translation"])
    else:
        m = ng.nodes.new("ShaderNodeMath")
        m.operation = "MULTIPLY_ADD"
        m.inputs[1].default_value = 0.1
        m.inputs[2].default_value = 1.0 - 0.1 / 25.0          # exactly 1 at frame 1 (scene time 0.04 s at 25 fps)
        ng.links.new(st.outputs["Seconds"], m.inputs[0])
        cx = ng.nodes.new("ShaderNodeCombineXYZ")
        for k in range(3):
            ng.links.new(m.outputs[0], cx.inputs[k])
        ng.links.new(cx.outputs[0], tr.inputs["Scale"])
    ng.links.new(gi.outputs[0], tr.inputs["Geometry"])
    ng.links.new(tr.outputs["Geometry"], go.inputs[0])
    return ng


def _plain_parts(bpy, sc, k):
    from fresing_render.blender import build
    out = [ob for ob in build.iter_parts(sc) if ob.type == "MESH" and not len(ob.modifiers) and ob.data
           and len(ob.data.polygons) > 20 and ob.data.users == 1 and ob.visible_get()]
    out.sort(key=lambda o: o.name)
    assert len(out) >= k
    return out[:k]


def _rigid_world(bpy, sc, doc, binary, job, ob, frames):
    fps = sc.render.fps / sc.render.fps_base
    chans = channels(doc, binary)
    node = next(n for o, n in job._nodes if o == ob)
    own = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get("co", own)
    own = own.reshape(-1, 3).astype(np.float64)
    worst = 0.0
    for f in frames:
        sc.frame_set(f)
        co, _me = evaluated(bpy, ob)
        app = world(np.array(ob.matrix_world), co)
        page = world(node_matrix(doc, chans, node, (f - sc.frame_start) / fps), own)
        worst = max(worst, float(np.linalg.norm(page - app, axis=1).max()))
    return worst


def test_part_with_other_modifiers(blender, tmp_path):
    """A Subdivision modifier on one CAD part (SHAPE: its evaluated mesh), a Geometry Nodes modifier that moves
    another part with the scene time (RIGID: node animation): no crash, the shapes and moves the app draws."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    build_anim(sc)
    sub, mov = _plain_parts(bpy, sc, 2)
    m = sub.modifiers.new("Sub", "SUBSURF")
    m.levels = m.render_levels = 1
    g = mov.modifiers.new("Move", "NODES")
    g.node_group = _gn_tree(bpy, "move", "move")
    sc.frame_set(1)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    assert job._drawn.kind(sub) == "SHAPE" and job._drawn.kind(mov) == "RIGID", out["drawn"]
    node = next(n for o, n in job._nodes if o == sub)
    prim = prim_of(doc, node)
    tri = sum(len(p.vertices) - 2 for p in sub.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.polygons)
    assert doc["accessors"][prim["indices"]]["count"] == 3 * tri
    assert _rigid_world(bpy, sc, doc, binary, job, mov, [1, 60, 133, 200]) < 0.003


def test_part_grown_by_its_modifier_is_not_taken_for_rigid(blender, tmp_path):
    """Finding 6 (fixed, contrived input): a part whose modifier grows it with the scene time, exactly x1 at the frame
    shown, is sorted RIGID there; every later frame was fitted as a rigid move from 4 points and the page ended
    0.56 m off. Now the fit is checked per frame: the part keeps its frame-shown move (its own motion still plays),
    and the result says so (``drawn_still`` + a line in the result text)."""
    bpy = blender
    sc = fresh(bpy, "test_spool.step", spool_model, tmp_path)
    build_anim(sc)
    (grow,) = _plain_parts(bpy, sc, 1)
    g = grow.modifiers.new("Grow", "NODES")
    g.node_group = _gn_tree(bpy, "grow", "grow")
    sc.frame_set(1)
    job, out, doc, binary = export(sc, tmp_path, animation=True)
    assert job._drawn.kind(grow) == "RIGID"
    assert grow.name in out.get("drawn_still", []), out.get("drawn_still")
    assert "stay as at the frame shown" in out["text"], out["text"]
    assert _rigid_world(bpy, sc, doc, binary, job, grow, [1]) < 0.001       # the frame shown: as the app
    # later: the part's own place as played, with its shape of the frame shown (not a made-up rigid fit)
    fps = sc.render.fps / sc.render.fps_base
    chans = channels(doc, binary)
    node = next(n for o, n in job._nodes if o == grow)
    own = np.empty(len(grow.data.vertices) * 3, np.float32)
    grow.data.vertices.foreach_get("co", own)
    own = own.reshape(-1, 3).astype(np.float64)
    for f in (101, 200):
        sc.frame_set(f)
        page = world(node_matrix(doc, chans, node, (f - 1) / fps), own)
        assert np.linalg.norm(page - world(np.array(grow.matrix_world), own), axis=1).max() < 0.003, f


def test_tracks_static_export_at_a_middle_frame(blender, tmp_path):
    """test_tracks.step without the animation, shown at frame 77: every link and pad where the app draws it."""
    from fresing_render.blender import tracks, web3d_drawn
    bpy = blender
    sc = fresh(bpy, "test_tracks.step", tracks.set_up_test_model, tmp_path)
    build_anim(sc)
    sc.frame_set(77)
    job, out, doc, binary = export(sc, tmp_path, animation=False)
    rigid = [(ob, n) for ob, n in job._nodes if job._drawn.kind(ob) == web3d_drawn.RIGID]
    assert len(rigid) == 146 and "animations" not in doc
    worst = 0.0
    for ob, node in rigid:
        co, _me = evaluated(bpy, ob)
        app = world(np.array(ob.matrix_world), co)
        own = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get("co", own)
        page = world(node_matrix(doc, {}, node, 0.0), own.reshape(-1, 3).astype(np.float64))
        worst = max(worst, float(np.linalg.norm(page - app, axis=1).max()))
    assert worst < 0.001, worst


def test_seabed_cable_static(blender, tmp_path):
    """test_moving.step without the animation at a frame where the cable lies on the seabed (own lengths, ``slo``
    without moments): page = app, and the page's JavaScript twin = the Python twin on the same file."""
    from fresing_render.blender import paths
    bpy = blender
    sc = fresh(bpy, "test_moving.step", paths.set_up_moving_model, tmp_path)
    build_anim(sc)
    sc.frame_set(260)
    job, out, doc, binary = export(sc, tmp_path, "still.glb", animation=False)
    specs = tubes_of(job, doc)
    assert set(specs) == {"CABLE", "LIFT WIRE"}
    w = compare_world(bpy, sc, job, doc, binary, [260])
    assert not w["count"] and w["centre"] < 0.002 and w["s"] < 0.002 and w["pay"] < 0.002, w
    if NODE:
        for name, (node, spec) in specs.items():
            ar = arrays(doc, binary, spec)
            js = js_run([(spec, ar)], [0.0])[0]
            py = T.at(spec, ar, 0.0)
            assert js["finite"] and js["count"] == len(py["points"])
            assert np.abs(np.array(js["s"]) - py["s"]).max() < 1e-6
            assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-5
    # animated: the page's JavaScript on the real file (own lengths, maybe the app's own ring turns) = Python twin,
    # and the page in world coordinates = the app, also between frames
    sc.frame_set(1)
    job, out, doc, binary = export(sc, tmp_path, "moving.glb", animation=True)
    specs = tubes_of(job, doc)
    w = compare_world(bpy, sc, job, doc, binary, [1, 60, 120, 200, 231, 260, 289])
    assert not w["count"] and w["centre"] < 0.003 and w["s"] < 0.003 and w["pay"] < 0.003, w
    # (16-bit steps here: 0.31 mm CABLE, 0.24 mm LIFT WIRE; see test_pack_keeps_a_long_travel_within_the_tolerance)
    # (between frames the app's cable picks a whole frame's shape – Scene Time -> Sample Index – while the page
    # blends: up to 0.1 m apart at frame 60.5 here; that is the page being smoother, not wrong)
    if NODE:
        ts = list(np.linspace(0.0, 289 / 25.0, 17))
        for name, (node, spec) in specs.items():
            ar = arrays(doc, binary, spec)
            res = js_run([(spec, ar)], ts)
            for t, js in zip(ts, res):
                py = T.at(spec, ar, float(t))
                assert js["finite"] and js["count"] == len(py["points"]), (name, t)
                assert np.abs(np.array(js["p"]).reshape(-1, 3) - py["points"]).max() < 1e-6, (name, t)
                assert np.abs(np.array(js["s"]) - py["s"]).max() < 1e-5, (name, t)
                assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-4, (name, t)
