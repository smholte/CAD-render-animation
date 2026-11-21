"""Task 0142, no Blender: the maths of moving cables on the web page (``core/web3d_tubes.py``) and its JavaScript
twin (``fresing_render/web/fr_tubes.js``, run by node when it is installed)."""

import json
import math
import os
import shutil
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_env as env, web3d_tubes as T

NODE = shutil.which("node")
TUBES_JS = os.path.join(web3d.WEB_DIR, env.TUBES_FILE)


def helix(n=60, r=0.5, pitch=0.3, turns=1.5):
    t = np.linspace(0.0, 2 * math.pi * turns, n)
    return np.c_[r * np.cos(t), r * np.sin(t), pitch * t / (2 * math.pi)]


def tube_points(line, radius, sides, n0):
    """Rings as Blender's Curve to Mesh writes them: ring after ring, point j at angle 2πj/sides."""
    tg = T.tangents(line)
    nr = T.transport(tg, n0)
    b = np.cross(tg, nr)
    ph = 2 * math.pi * np.arange(sides) / sides
    return (line[:, None] + radius * (np.cos(ph)[None, :, None] * nr[:, None] + np.sin(ph)[None, :, None] * b[:, None]))


def test_rings_are_read_back():
    line = helix()
    pts = tube_points(line, 0.02, 12, (0.0, 0.0, 1.0))
    got = T.find_rings(pts.reshape(-1, 3))
    assert got is not None
    c, first, rad, sides = got
    assert sides == 12 and rad == pytest.approx(0.02, rel=1e-6)
    assert np.abs(c - line).max() < 1e-9
    # two rings of 6 taken for one of 12 would be round about their middle, but not flat: refused
    assert T.find_rings(pts.reshape(-1, 3), sides=24) is None
    assert T.find_rings(np.random.default_rng(1).normal(size=(120, 3))) is None


def test_transport_matches_the_rings_and_tangent_rule():
    line = helix(80)
    pts = tube_points(line, 0.03, 16, (0.0, 0.0, 1.0))
    c, first, rad, sides = T.find_rings(pts.reshape(-1, 3))
    carried = T.transport(T.tangents(c), first[0])
    assert np.abs(carried - first).max() < 1e-9
    many = T.transport_many(T.tangents(c)[None].repeat(3, axis=0), first[[0, 0, 0]])
    assert np.abs(many - first[None]).max() < 1e-9


def test_tangents_look_past_tiny_pieces():
    """16-bit points: a piece 0.2 mm long has a noisy direction; with ``min_len`` the neighbours further away count."""
    line = np.c_[np.linspace(0, 1, 21), np.zeros(21), np.zeros(21)]
    noisy = line.copy()
    noisy = np.insert(noisy, 11, noisy[10] + [0.0002, 0.00015, 0.0], axis=0)      # a crooked tiny piece
    plain = T.tangents(noisy)
    far = T.tangents(noisy, min_len=0.01)
    assert np.degrees(np.arccos(np.clip(plain[10, 0], -1, 1))) > 10
    assert np.abs(far - [1.0, 0.0, 0.0]).max() < 0.02


def test_chords_and_trim_like_the_spool_tree():
    p = np.c_[np.arange(6.0), np.zeros(6), np.zeros(6)]
    s = T.chords(p)
    assert list(s) == [0, 1, 2, 3, 4, 5]
    pts, ss = T.trimmed(p, s, 1.5, 3.25)
    # from the first point at or past 1.5 (no cut there), the first point past 3.25 moved back onto 3.25
    assert list(ss) == [2.0, 3.0, 3.25] and pts[-1, 0] == pytest.approx(3.25)
    pts, ss = T.trimmed(p, s, 2.0, 4.0)                  # ends on a point: the next one is moved onto it too
    assert list(ss) == [2.0, 3.0, 4.0, 4.0]


def test_fit_rigid_and_spread():
    rng = np.random.default_rng(3)
    pts = rng.normal(size=(200, 3))
    ang = 0.7
    r = np.array([[math.cos(ang), -math.sin(ang), 0], [math.sin(ang), math.cos(ang), 0], [0, 0, 1]])
    moved = pts @ r.T + [1.0, 2.0, 3.0]
    idx = T.spread(pts)
    assert len(idx) == 4
    m, left = T.fit_rigid(pts[idx], moved[idx])
    assert left < 1e-12 and np.abs(pts @ m[:3, :3].T + m[:3, 3] - moved).max() < 1e-12


def test_thin_keeps_only_what_a_blend_cannot_give():
    f = np.arange(100.0)
    x = np.stack([np.c_[f * 0.01, np.zeros(100), np.zeros(100)]] * 3, axis=1)   # a straight move: 2 moments
    assert list(T.thin_frames(x, 0.001)) == [0, 99]
    y = x.copy()
    y[50:] = y[50]                                       # stops half way: 3
    assert list(T.thin_frames(y, 0.001)) == [0, 50, 99]
    z = np.sin(f / 10.0)[:, None, None] * np.ones((100, 4, 3))     # a curve: kept moments blend within 1 mm
    k = T.thin_frames(z, 0.001)
    back = np.array([T.blend_at(k.astype(float), z[k], t) for t in f])
    assert 5 < len(k) < 100 and np.abs(back - z).max() <= 0.001 + 1e-9


def test_thin_node_turning_part():
    """A part turning at a steady speed: the short-way slerp gives it exactly between kept moments, but never across
    half a turn; one that stops is kept where it stops."""
    f = np.arange(200)
    ang = np.minimum(f, 150) * 0.1                       # 0.1 rad a frame, stops at frame 150
    q = np.c_[np.zeros(200), np.zeros(200), np.sin(ang / 2), np.cos(ang / 2)]
    t = np.zeros((200, 3))
    k = T.thin_node(t, q, reach=0.5)
    assert 150 in k and len(k) < 40
    # what a viewer plays between kept moments stays within 1 mm at 0.5 m from the axis
    for a, b in zip(k[:-1], k[1:]):
        w = (f[a:b + 1] - a) / max(b - a, 1)
        qq = T.slerp(q[a], q[b], w)
        err = 2 * np.arccos(np.clip(np.abs((qq * q[a:b + 1]).sum(axis=1)), -1, 1)) * 0.5
        assert err.max() <= 0.001 + 1e-9


def test_pack_and_octahedral():
    rng = np.random.default_rng(7)
    p = rng.normal(size=(5, 30, 3)) * 0.01 + np.linspace(0, 20, 30)[None, :, None]
    sa = np.linspace(0, 300, 30)[None] + rng.normal(size=(5, 30)) * 0.01
    lo, step, slo, sstep, q = T.pack(p, sa)
    assert q.shape == (5, 30, 4) and q.dtype == np.uint16             # moment after moment, x y z s
    back = T.unpack(lo, step, q, 5)
    assert np.abs(back - p).max() <= step.max() * 0.51 + 4e-6          # (lo is float32: 2e-6 at 20 m)
    assert np.abs(T.unpack_s(slo, sstep, q, 5) - sa).max() <= sstep.max() * 0.51 + 4e-5
    lo1, step1, _sl, _ss, q1 = T.pack(p[:1])
    assert q1 is None and np.abs(T.unpack(lo1, step1, q1, 1) - p[:1]).max() < 1e-5
    n = rng.normal(size=(500, 3))
    n /= np.linalg.norm(n, axis=1)[:, None]
    assert np.degrees(np.arccos(np.clip((T.oct_decode(T.oct_encode(n)) * n).sum(1), -1, 1))).max() < 0.01


def _spec_and_arrays():
    """A small moving tube in the file's form (two kept moments, its own lengths, paid out metres)."""
    a = helix(30)
    b = helix(30, r=0.6)
    lo, step, _slo, _sstep, q = T.pack(np.stack([a, b]))
    spec = {"v": 1, "n": 30, "k": 2, "sides": 8, "r": 0.02, "unit": 1.0}
    arrays = {"times": np.array([0.0, 2.0]), "lo": lo, "step": step, "q": q.reshape(-1, 4),
              "n0": np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]]), "s0": np.array([0.0, 0.5]),
              "pay_t": np.array([0.0, 2.0]), "pay": np.array([0.0, 4.0])}
    return spec, arrays


def test_at_blends_moments():
    spec, arrays = _spec_and_arrays()
    mid = T.at(spec, arrays, 1.0)
    want = 0.5 * (helix(30) + helix(30, r=0.6))
    assert np.abs(mid["points"] - want).max() < 1e-4
    assert mid["pay"] == pytest.approx(2.0) and mid["s"][0] == pytest.approx(0.25)
    assert np.abs((mid["normals"] * mid["tangents"]).sum(1)).max() < 1e-9


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_javascript_twin_gives_the_same():
    """fr_tubes.js (the page) and core.web3d_tubes.at (the tests' reference) agree; also with a spool's cut."""
    spec, arrays = _spec_and_arrays()
    p = helix(40)
    spool = {"v": 1, "n": 40, "k": 1, "sides": 8, "r": 0.01, "unit": 1.0, "spool": True, "pay": 0.0}
    s = T.chords(p) - 3.0
    sarr = {"lo": p, "s": s, "n0": np.array([[0.0, 0.0, 1.0]]), "s0": s[:1], "trim_t": np.array([0.0, 2.0]),
            "trim": np.array([[s[5], s[30]], [s[12], s[20] + 0.01]]),
            "trim_n0": np.array([[0.0, 0.0, 1.0], [0.0, 0.0, 1.0]])}
    # its own lengths in the 4th slot, the app's ring turns per point (nq), short pieces looked past (tmin)
    own = dict(spec, tmin=0.05)
    lo, step, slo, sstep, q = T.pack(np.stack([helix(30), helix(30, r=0.6)]), np.stack([np.linspace(0, 3, 30),
                                                                                       np.linspace(1, 5, 30)]))
    tg = np.stack([T.tangents(helix(30)), T.tangents(helix(30, r=0.6))])
    nq = T.oct_encode(T.transport_many(tg, np.array([[1.0, 0, 0], [0, 1.0, 0]])))
    oarr = dict(arrays, lo=lo, step=step, q=q.reshape(-1, 4), slo=slo, sstep=sstep, nq=nq.reshape(-1, 2))
    jobs = [(spec, arrays), (spool, sarr), (own, oarr)]
    times = [0.0, 0.3, 1.0, 1.7, 2.0, 3.0]
    payload = {"jobs": [[sp, {k: np.asarray(v, float).ravel().tolist() for k, v in ar.items()}] for sp, ar in jobs],
               "ts": times}
    code = ("const F=require(%s);const J=JSON.parse(require('fs').readFileSync(0,'utf8'));const out=[];"
            "for(const [spec,arr] of J.jobs){const a={};for(const k in arr)a[k]=Float64Array.from(arr[k]);"
            "const tb=F.make(spec,a);for(const t of J.ts){tb.at(t);out.push({count:tb.count,"
            "p:Array.from(tb.cp.slice(0,tb.count*3)),n:Array.from(tb.nr.slice(0,tb.count*3)),"
            "s:Array.from(tb.cs.slice(0,tb.count)),pay:tb.pay});}}console.log(JSON.stringify(out));") % json.dumps(
        TUBES_JS)
    res = subprocess.run([NODE, "-e", code], input=json.dumps(payload), capture_output=True, text=True, check=True)
    out = json.loads(res.stdout)
    k = 0
    for sp, ar in jobs:
        a2 = {key: np.asarray(v, float) for key, v in ar.items()}
        for key in ("lo", "n0", "trim_n0"):
            if key in a2:
                a2[key] = a2[key].reshape(-1, 3)
        if "trim" in a2:
            a2["trim"] = a2["trim"].reshape(-1, 2)
        for t in times:
            py = T.at(sp, a2, t)
            js = out[k]
            k += 1
            assert js["count"] == len(py["points"]), (sp.get("spool"), t)
            assert np.abs(np.array(js["p"]).reshape(-1, 3) - py["points"]).max() < 1e-9
            assert np.abs(np.array(js["n"]).reshape(-1, 3) - py["normals"]).max() < 1e-9
            assert np.abs(np.array(js["s"]) - py["s"]).max() < 1e-9
            assert js["pay"] == pytest.approx(py["pay"])


def test_page_carries_the_tubes_script():
    text = env.page_html("T", b"glb", env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1]))
    assert "FRTubes" in text and text.index("FRTubes") < text.index("setupTubes")
    if NODE:
        subprocess.run([NODE, "--check", TUBES_JS], check=True)


def test_as_packed_is_what_the_page_unpacks():
    """Task 0248: the export decides whether a cable's own lengths along it go into the file by the chords of the
    points as the page gets them – ``as_packed`` is exactly ``unpack(pack(...))``, 16-bit and 32-bit alike."""
    rng = np.random.default_rng(1)
    for spread in (1.0, 500.0):                              # (500 m: a point travels too far for 16 bits)
        p = (rng.normal(size=(300, 50, 3)) * spread).astype(np.float32)
        lo, step, _slo, _sstep, q = T.pack(p, None, max_step=T.POS_TOL)
        assert np.array_equal(T.as_packed(p, T.POS_TOL, chunk=64), T.unpack(lo, step, q, len(p)))
    one = rng.normal(size=(1, 5, 3)).astype(np.float32)
    assert np.array_equal(T.as_packed(one), T.unpack(*T.pack(one)[:2], None, 1))
