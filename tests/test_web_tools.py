"""The web 3D player's part tools (task 0135), no Blender: part info, measure (points, planes, diameter, centre to
centre, face to centre, X/Y/Z parts), cutaway, fade the rest – on a made-up model of known sizes, driven in headless
Chromium by ``tools/web_player_probe.js``; the measuring maths (``fr_measure.js``) by node; the face data
(``core/web3d_faces.py``) on its own.

The model (Blender's world, metres): a block 400 x 200 x 100 mm from the origin; a shaft Ø40 x 150 standing at
(600, 100); a pin Ø30 x 120 at (800, 100). Each is a part of its own, placed by its node, with 16-bit points.

GitHub's Linux runner cannot start Chromium (task 0106): the browser tests check the scripts with node there instead
(each pytest group on GitHub allows only one skipped test); the maths and face-data tests run everywhere.
"""

import functools
import json
import os
import shutil
import subprocess

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_env as env, web3d_faces as wf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "tools", "web_player_probe.js")
MEASURE_JS = os.path.join(web3d.WEB_DIR, env.MEASURE_FILE)
NODE = shutil.which("node")


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------

def box(x0, y0, z0, x1, y1, z1):
    """Points, normals, triangles and face starts of a box (one CAD face per side)."""
    pts, nrm, tri, starts = [], [], [], []
    sides = [((0, 1, 2), 2, z1, (0, 0, 1)), ((0, 1, 2), 2, z0, (0, 0, -1)), ((1, 2, 0), 0, x1, (1, 0, 0)),
             ((1, 2, 0), 0, x0, (-1, 0, 0)), ((2, 0, 1), 1, y1, (0, 1, 0)), ((2, 0, 1), 1, y0, (0, -1, 0))]
    lo, hi = (x0, y0, z0), (x1, y1, z1)
    for (a, b, c), axis, at, n in sides:
        k = len(pts)
        for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
            p = [0.0, 0.0, 0.0]
            p[a] = lo[a] if not u else hi[a]
            p[b] = lo[b] if not v else hi[b]
            p[c] = at
            pts.append(p)
            nrm.append(n)
        starts.append(len(tri))
        quad = [[k, k + 1, k + 2], [k, k + 2, k + 3]]
        if np.dot(np.cross(np.subtract(pts[k + 1], pts[k]), np.subtract(pts[k + 2], pts[k])), n) < 0:
            quad = [[k, k + 2, k + 1], [k, k + 3, k + 2]]
        tri += quad
    starts.append(len(tri))
    return np.array(pts), np.array(nrm, float), np.array(tri), starts, [], []


def cylinder(r, h, n=48):
    """A cylinder about z from z 0 to h: side (one round face), top, bottom; axis data as the importer writes it."""
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(a), np.sin(a)
    pts, nrm, tri = [], [], []
    for z in (0.0, h):                                   # side
        for i in range(n):
            pts.append([r * c[i], r * s[i], z]); nrm.append([c[i], s[i], 0.0])
    for i in range(n):
        j = (i + 1) % n
        tri += [[i, j, n + j], [i, n + j, n + i]]
    starts = [0]
    for z, sign in ((h, 1.0), (0.0, -1.0)):              # top, bottom
        starts.append(len(tri))
        k = len(pts)
        pts.append([0.0, 0.0, z]); nrm.append([0, 0, sign])
        for i in range(n):
            pts.append([r * c[i], r * s[i], z]); nrm.append([0, 0, sign])
        for i in range(n):
            j = (i + 1) % n
            tri.append([k, k + 1 + i, k + 1 + j] if sign > 0 else [k, k + 1 + j, k + 1 + i])
    starts.append(len(tri))
    axes = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, r]
    return np.array(pts), np.array(nrm, float), np.array(tri), starts, axes, [0, 2 * n, 0]


PARTS = [("Block", "Steel", (0.0, 0.0, 0.0), box(0, 0, 0, 0.4, 0.2, 0.1)),
         ("Shaft", "Steel", (0.6, 0.1, 0.0), cylinder(0.02, 0.15)),
         ("Pin", "Bolts", (0.8, 0.1, 0.0), cylinder(0.015, 0.12))]


def model(hide_names=False, faces=True) -> bytes:
    g = web3d.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.62, 0.65, 1.0], "metallicFactor": 0.0,
                                                "roughnessFactor": 0.7}, "doubleSided": True})
    root = g.node({"name": "Model", "rotation": list(web3d.Z_UP_TO_Y_UP)})
    data = {}
    for k, (name, group, at, (pts, nrm, tri, starts, axes, af)) in enumerate(PARTS):
        mesh = g.mesh(f"Mesh {k + 1}", pts, web3d.quantize_normals(nrm), None, [(look, tri)], max_step=0.001)
        rows = wf.classify(pts, tri, wf.face_of_triangles(len(tri), starts), axes, af)
        dq = g.dequantize[mesh]
        data[mesh] = wf.pack([wf.face_of_triangles(len(tri), starts)], wf.to_written(rows, *(dq or (None, None))))
        node = {"name": f"Part {k + 1}" if hide_names else name, "translation": list(at),
                "extras": {"fr_card": group if hide_names else name}}
        g.place_mesh(node, mesh, root)
    if faces:
        wf.write(g, data)
    return g.glb()


def write(path, hide_names=False, faces=True, title="Tools test", shadows=False):
    st = env.settings(dict(env.default_choice(), shadows=shadows, auto=False, quality="BALANCED"), [0.0, 0.0, 0.0],
                      [0.83, 0.2, 0.15], sky={"kind": "SKY", "sun": env.sun_vector(40, 30)}, plain=True)
    glb = model(hide_names, faces)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html(title, glb, st, note="Made with Fresing Render"))
    return str(path), glb


# ---------------------------------------------------------------------------
# the face data (no browser)
# ---------------------------------------------------------------------------

def test_faces_are_classified_and_packed():
    pts, _n, tri, starts, axes, af = cylinder(0.02, 0.15)
    face = wf.face_of_triangles(len(tri), starts)
    rows = wf.classify(pts, tri, face, axes, af)
    assert set(rows) == {0, 1, 2}
    assert rows[0][0] == wf.ROUND and abs(rows[0][7] - 0.02) < 1e-9               # the face's own radius
    assert rows[1][0] == wf.FLAT and np.allclose(rows[1][1:4], [0, 0, 1]) and abs(rows[1][4] - 0.15) < 1e-9
    runs, table = wf.pack([face], rows)
    assert runs.tolist() == [[0, 0], [96, 1], [144, 2]] and table.shape == (3, wf.ROW)
    assert wf.row_at(runs, table, 100)[0] == wf.FLAT and wf.row_at(runs, table, 5)[0] == wf.ROUND
    # in the written 16-bit coordinates: (x - centre) / step
    w = wf.to_written(rows, [0.0, 0.0, 0.075], 0.001)
    assert abs(w[0][7] - 20.0) < 1e-6 and abs(w[1][4] - 75.0) < 1e-6 and abs(w[0][3] + 75.0) < 1e-6


def test_one_axis_line_keeps_each_faces_own_radius():
    """0122: faces on one axis line share ONE axis carrying the largest radius – the clicked face keeps its own."""
    p1, _n1, t1, s1, _a, _f = cylinder(0.02, 0.05)
    p2, _n2, t2, s2, _a2, _f2 = cylinder(0.04, 0.02)
    p2 = p2 + [0, 0, 0.05]
    pts = np.vstack([p1, p2])
    tri = np.vstack([t1, t2 + len(p1)])
    starts = s1[:-1] + [s + s1[-1] for s in s2]
    axes = [0, 0, 0, 0, 0, 1, 0.04]                         # the importer: one axis, the largest radius
    af = [0, 96, 0, s1[-1], 96, 0]
    rows = wf.classify(pts, tri, wf.face_of_triangles(len(tri), starts), axes, af)
    assert abs(rows[0][7] - 0.02) < 1e-9 and abs(rows[3][7] - 0.04) < 1e-9


def test_a_cone_has_an_axis_but_no_diameter():
    a = np.linspace(0, 2 * np.pi, 32, endpoint=False)
    pts = np.array([[0.02 * np.cos(x), 0.02 * np.sin(x), 0.0] for x in a] + [[0.01 * np.cos(x), 0.01 * np.sin(x), 0.02]
                                                                               for x in a])
    tri = np.array([[i, (i + 1) % 32, 32 + (i + 1) % 32] for i in range(32)] + [[i, 32 + (i + 1) % 32, 32 + i]
                                                                                for i in range(32)])
    rows = wf.classify(pts, tri, np.zeros(64, int), [0, 0, 0, 0, 0, 1, 0.02], [0, 64, 0])
    assert rows[0][0] == wf.AXIS and rows[0][7] == 0.0


def test_a_curved_face_without_an_axis_gets_no_row():
    pts, _n, tri, _s, _a, _f = cylinder(0.02, 0.15)
    rows = wf.classify(pts, tri[:96], np.zeros(96, int))     # the side, but no axis given: not flat either
    assert rows == {}


def test_the_file_carries_the_face_data_and_the_cards():
    data = model()
    got = wf.read(data)
    assert len(got) == 3 and all(r.dtype == np.uint32 and t.shape[1] == wf.ROW for r, t in got.values())
    assert web3d.problems(data) == []
    doc, _ = web3d.read_glb(data)
    assert [n["extras"]["fr_card"] for n in doc["nodes"] if "extras" in n] == ["Block", "Shaft", "Pin"]
    hidden = model(hide_names=True)
    assert b"Block" not in hidden and b"Shaft" not in hidden and b"Pin\"" not in hidden


# ---------------------------------------------------------------------------
# the maths (node)
# ---------------------------------------------------------------------------

def run_measure(expr: str):
    if not NODE:
        pytest.skip("no node")
    code = f"const M = require({json.dumps(MEASURE_JS)}); console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def test_measure_maths():
    flat_a = "{kind: 'flat', p: [0.1, 0.1, 0.1], n: [0, 0, 1]}"
    flat_b = "{kind: 'flat', p: [0.6, 0.1, 0.15], n: [0, 0, -1]}"
    tilted = "{kind: 'flat', p: [0.6, 0.1, 0.15], n: [0, Math.sin(0.5 * Math.PI / 180), Math.cos(0.5 * Math.PI / 180)]}"
    wall = "{kind: 'flat', p: [0.2, 0, 0.05], n: [0, -1, 0]}"
    rd = "{kind: 'round', p: [0.6, 0.08, 0.07], o: [0.6, 0.1, 0], d: [0, 0, 1], r: 0.02}"
    rd2 = "{kind: 'round', p: [0.8, 0.085, 0.03], o: [0.8, 0.1, 0], d: [0, 0, -1], r: 0.015}"
    skew = "{kind: 'round', p: [0, 0, 0.3], o: [0, 0, 0.3], d: [1, 0, 0], r: 0.01}"
    side = "{kind: 'flat', p: [0.4, 0.03, 0.05], n: [1, 0, 0]}"
    pts = "{kind: 'point', p: [0, 0, 0]}, {kind: 'point', p: [0.3, 0.4, 0.12]}"
    o = run_measure(f"[M.measure({flat_a}, {flat_b}), M.measure({flat_a}, {tilted}), M.measure({flat_a}, {wall}),"
                    f" M.single({rd}), M.measure({rd}, {rd2}), M.measure({rd}, {skew}), M.measure({side}, {rd}),"
                    f" M.measure({rd}, {side}), M.measure({pts}), M.parts([0, 0, 0], [0.3, -0.4, 0.12]),"
                    f" M.measure({flat_a}, {flat_b}, 'points'), M.mm(12.345678), M.mm(0.0042), M.mm(-0.2)]")
    assert o[0]["type"] == "planes" and abs(o[0]["dist"] - 0.05) < 1e-12 and o[0]["lines"][0] == "Between the planes 50.0 mm"
    assert o[1]["type"] == "planes" and abs(o[1]["angle"] - 0.5) < 1e-6                      # parallel within 1°
    assert o[2]["type"] == "angle" and abs(o[2]["angle"] - 90) < 1e-9 and "90.0°" in o[2]["lines"][0]
    assert o[3]["type"] == "diameter" and abs(o[3]["dist"] - 0.04) < 1e-12 and o[3]["lines"][0].startswith("Ø 40.0 mm")
    assert o[4]["type"] == "axes" and abs(o[4]["dist"] - 0.2) < 1e-12 and np.allclose(o[4]["vec"], [0.2, 0, 0])
    assert abs(o[5]["dist"] - 0.1) < 1e-12 and abs(o[5]["angle"] - 90) < 1e-9                  # skew axes (y 0.1 apart)
    assert o[6]["type"] == "face-axis" and abs(o[6]["dist"] - 0.2) < 1e-12 and np.allclose(o[6]["vec"], [0.2, 0, 0])
    assert np.allclose(o[7]["vec"], [-0.2, 0, 0])                                                # the other way round
    assert abs(o[8]["dist"] - np.linalg.norm([0.3, 0.4, 0.12])) < 1e-12
    assert [(q["axis"], round(q["value"], 9)) for q in o[9]] == [("X", 0.3), ("Y", -0.4), ("Z", 0.12)]
    assert o[9][0]["text"] == "X 300.0 mm" and o[9][1]["text"] == "Y −400.0 mm"
    assert o[10]["type"] == "points"
    assert o[11] == "12 345.7 mm" and o[12] == "4.20 mm" and o[13] == "−200.0 mm"


def test_a_row_is_turned_into_the_models_coordinates():
    """fromRow: a stretched, moved part – the radius across its axis, the plane's normal by the inverse transpose."""
    # written coordinates -> model: scale x 2, y 1, z 0.5, then moved by (1, 2, 3); column-major
    m = "[2,0,0,0, 0,1,0,0, 0,0,0.5,0, 1,2,3,1]"
    o = run_measure(f"[M.fromRow([2, 0, 0, 0, 0, 0, 1, 0.01], {m}, [1.03, 2, 3.2]),"
                    f" M.fromRow([1, 0.6, 0, 0.8, 0.4, 0, 0, 0], {m}, [1.2, 2, 3.1]), M.fromRow(null, {m}, [1, 1, 1])]")
    assert o[0]["kind"] == "round" and abs(o[0]["r"] - 0.015) < 1e-12 and np.allclose(o[0]["o"], [1, 2, 3])
    assert np.allclose(o[0]["p"], [1.015, 2, 3.2])                       # the click put on the round face
    n = np.array([0.6 / 2, 0, 0.8 / 0.5])
    assert o[1]["kind"] == "flat" and np.allclose(o[1]["n"], n / np.linalg.norm(n))
    assert o[2] == {"kind": "point", "p": [1, 1, 1]}


# ---------------------------------------------------------------------------
# the page (headless Chromium)
# ---------------------------------------------------------------------------

_WORKS: dict = {}


def probe(path, steps, query="soft=0", size="900x600", mobile=False, timeout=240):
    args = [NODE, PROBE, path, json.dumps(steps), f"--size={size}"] + ([f"--query={query}"] if query else [])
    if mobile:
        args.append("--mobile")
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert "error" not in out, out
    return out


def browser_test(fn):
    @functools.wraps(fn)
    def run(tmp_path):
        if "ok" not in _WORKS:
            ok = False
            if NODE:
                try:
                    path, _g = write(os.path.join(str(tmp_path), "works.html"))
                    ok = probe(path, [])["ok"]
                except Exception:  # noqa: BLE001 - no Playwright, no Chromium: the scripts are checked by node
                    ok = False
            _WORKS["ok"] = ok
        if _WORKS["ok"]:
            return fn(tmp_path)
        page = env.page_html("x", b"x", env.settings(env.default_choice(), [0, 0, 0], [1, 1, 1]))
        for name in (env.MEASURE_FILE, env.TOOLS_FILE):
            assert env._inline(env._read(name)) in page
            if NODE:
                subprocess.run([NODE, "--check", os.path.join(web3d.WEB_DIR, name)], check=True)
    return run


# the camera: Blender (1.1, -1.0, 0.8) looking at (0.42, 0.1, 0.06); three = (x, z, -y)
CAM = "frPage.setCamera([1.1, 0.8, 1.0], [0.42, 0.06, -0.1])"
P = {"block_top": [0.2, 0.1, 0.1], "block_front": [0.2, 0.0, 0.05], "block_side": [0.4, 0.03, 0.05],
     "shaft_top": [0.6, 0.1, 0.15], "shaft_side": [0.6 + 0.02 * np.cos(-1.2), 0.1 + 0.02 * np.sin(-1.2), 0.07],
     "pin_side": [0.8 + 0.015 * np.cos(-1.0), 0.1 + 0.015 * np.sin(-1.0), 0.06]}


def at(name):
    return f"(function () {{ var s = frPage.partTools.screenOf({json.dumps(list(map(float, P[name])))});" \
           f" return [s.x, s.y]; }})()"


def clicks(*names):
    """eval steps: click the named points one after the other through the tool's own click (exact pixels)."""
    return [{"eval": f"(function () {{ var s = frPage.partTools.screenOf({json.dumps(list(map(float, P[n])))});"
                     f" return frPage.partTools.click(s.x, s.y); }})()"} for n in names]


@browser_test
def test_measurements_on_known_sizes(tmp_path):
    path, _g = write(tmp_path / "tools.html")
    steps = [{"eval": CAM}, {"wait": 300}, {"key": "d"}, {"eval": "frPage.partTools.state()"}]
    steps += clicks("block_top", "shaft_top")                 # 4, 5: between planes
    steps += clicks("shaft_side")                             # 6: a new measurement: the diameter
    steps += clicks("pin_side")                               # 7: centre to centre
    steps += [{"key": "x"}, {"eval": "frPage.partTools.state()"}]      # 8, 9: X / Y / Z parts
    steps += clicks("block_side", "shaft_side")               # 10, 11: face to centre
    steps += clicks("block_top", "block_front")               # 12, 13: angle
    steps += [{"click": "#fr-tpanel [data-mode=points]"}]     # 14
    steps += clicks("block_top", "shaft_top")                 # 15, 16: points
    steps += [{"key": "Escape"}, {"eval": "frPage.partTools.state()"}]  # 17, 18
    out = probe(path, steps)
    assert out["ok"], out
    o = out["out"]
    assert o[3]["tool"] == "measure" and o[3]["faces"] is True
    r = o[5]["result"]
    assert r["type"] == "planes" and abs(r["dist"] - 0.05) < 1e-6 and r["lines"][0] == "Between the planes 50.0 mm"
    r = o[6]["result"]
    assert r["type"] == "diameter" and abs(r["dist"] - 0.04) < 1e-6, r
    r = o[7]["result"]
    assert r["type"] == "axes" and abs(r["dist"] - 0.2) < 1e-6, r
    r = o[9]["result"]
    assert r["parts"][0][0] == "X" and abs(r["parts"][0][1] - 0.2) < 1e-6 and len(r["parts"]) == 1
    assert o[9]["lines"] and o[9]["labels"] == ["200.0 mm"]           # one part only: no second number on it
    r = o[11]["result"]
    assert r["type"] == "face-axis" and abs(r["dist"] - 0.2) < 1e-6, r
    r = o[13]["result"]
    assert r["type"] == "angle" and abs(r["angle"] - 90) < 1e-3, r
    r = o[16]["result"]
    a, b = np.array(r["picks"][0]["p"]), np.array(r["picks"][1]["p"])
    assert r["type"] == "points" and abs(r["dist"] - np.linalg.norm(b - a)) < 1e-9
    assert np.allclose(a, P["block_top"], atol=2e-3) and np.allclose(b, P["shaft_top"], atol=2e-3)
    assert abs(a[2] - 0.1) < 2e-4 and abs(b[2] - 0.15) < 2e-4              # on the faces (16-bit points: 1 mm steps)
    assert o[18]["picks"] == 0 and o[18]["result"] is None


@browser_test
def test_a_real_click_info_card_fade_and_cut(tmp_path):
    path, _g = write(tmp_path / "tools.html")
    shaft, block = at("shaft_side"), at("block_top")
    steps = [{"eval": CAM}, {"wait": 300}, {"key": "i"}, {"eval": shaft}]
    out = probe(path, steps)
    x, y = out["out"][3]
    steps += [{"tap": [x, y]}, {"eval": "frPage.partTools.state().card"},                       # 4, 5
              {"drag": [x, y, x + 80, y + 10]}, {"eval": "frPage.partTools.state().card"},       # 6, 7: a drag keeps it
              {"key": "t"}, {"eval": block}]                                                    # 8, 9
    out = probe(path, steps)
    bx, by = out["out"][9]
    steps += [{"tap": [bx, by]}, {"eval": "frPage.partTools.state()"},                          # 10, 11
              {"tap": [5, 590]}, {"eval": "frPage.partTools.state()"},                          # 12, 13: empty space
              {"eval": "frPage.partTools.setCut(true, 'X', 0.5)"}, {"eval": "frPage.partTools.state()"},   # 14, 15
              {"eval": f"frPage.partTools.pickAt.apply(null, {shaft})"},                        # 16: cut away
              {"eval": "frPage.partTools.setCut(true, 'X', 0.5, true)"},
              {"eval": f"frPage.partTools.pickAt.apply(null, {shaft})"},                        # 18: Flip keeps it
              {"key": "c"}, {"eval": "frPage.partTools.state()"}]                               # 19, 20
    out = probe(path, steps)
    assert out["ok"], out
    o = out["out"]
    assert o[5]["text"] == "Shaft" and "Ø 40.0 mm" in o[5]["face"] and o[5]["shown"], o[5]
    assert o[7] is not None and o[7]["text"] == "Shaft"
    assert o[11]["fade"] == "Block" and o[11]["faded"] == 2 and o[11]["tool"] == "fade"
    assert o[13]["fade"] is None and o[13]["faded"] == 0
    assert o[15]["cut"]["on"] and o[15]["clipped"] >= 1
    assert o[16] is None or o[16]["card"] != "Shaft"           # x > 415 mm is cut away: the shaft is gone
    assert o[18] is not None and o[18]["card"] == "Shaft"
    assert o[20]["cut"]["on"] is False and o[20]["clipped"] == 0


@browser_test
def test_hide_names_long_press_and_hover(tmp_path):
    path, glb = write(tmp_path / "hidden.html", hide_names=True)
    for name in (b"Block", b"Shaft", b"Pin"):
        assert name not in glb, name                        # no part name anywhere in the model
    steps = [{"eval": CAM}, {"wait": 300}, {"eval": at("shaft_side")}]
    out = probe(path, steps, size="480x640", mobile=True)
    x, y = out["out"][2]
    steps += [{"touch": [x, y, 900]}, {"eval": "frPage.partTools.state().card"},               # 3, 4: long press
              {"key": "Escape"}, {"key": "i"}, {"touch": [x, y, 80]},                         # 5-7: a tap with Info
              {"eval": "frPage.partTools.state().card"}]                                       # 8
    out = probe(path, steps, size="480x640", mobile=True)
    assert out["ok"], out
    o = out["out"]
    assert o[4]["text"] == "Steel" and "Ø 40.0 mm" in o[4]["face"]              # the group, never the part name
    assert o[8] and o[8]["text"] == "Steel"
    # mouse: a press held long is a click (no card); hovering while measuring lights a face
    out = probe(path, [{"eval": CAM}, {"wait": 300}, {"eval": at("shaft_side")}])
    x, y = out["out"][2]
    out = probe(path, [{"eval": CAM}, {"wait": 300}, {"press": [x, y, 900]}, {"eval": "frPage.partTools.state().card"},
                       {"key": "d"}, {"move": [x, y]}, {"eval": "frPage.partTools.state().hover"}])
    assert out["out"][3] is None
    assert ":" in out["out"][6]                                                   # a face is lit (mesh:first triangle)


@browser_test
def test_a_page_without_face_data_measures_points(tmp_path):
    path, _g = write(tmp_path / "nofaces.html", faces=False)
    steps = [{"eval": CAM}, {"wait": 300}, {"key": "d"}] + clicks("block_top", "shaft_top") + \
            [{"eval": "document.getElementById('fr-hint').textContent"}]
    out = probe(path, steps)
    assert out["ok"], out
    r = out["out"][4]["result"]
    assert out["out"][4]["faces"] is False and r["type"] == "points" and r["picks"][0]["kind"] == "point"
    assert "no face data" in out["out"][5]


@browser_test
def test_selftest_and_keys_help(tmp_path):
    path, _g = write(tmp_path / "tools.html")
    st = env.read_page(path, query="selftest=1&soft=0")
    assert st["tools"] and st["tools"]["ok"], st["tools"]
    out = probe(path, [{"key": "?"}, {"eval": "document.getElementById('fr-help').textContent"}])
    assert "measure" in out["out"][1] and "cutaway" in out["out"][1] and "fade the rest" in out["out"][1]


@browser_test
def test_phone_layout_and_remembered_settings(tmp_path):
    """0147 row 21e: portrait – the help is a bottom sheet (no longer over the tool column); landscape 844 x 390 –
    the menu leaves the tool buttons free, the tools fit in one column; the touch hint; row 16: a remembered field of
    the wrong type no longer stops the page."""
    path, _g = write(tmp_path / "phone.html", title="Plåt – test")
    rect = "(function (s) { var r = document.querySelector(s).getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })"
    out = probe(path, [{"key": "?"}, {"eval": rect + "('#fr-help')"}, {"eval": rect + "('#fr-tools')"},
                       {"eval": "document.querySelector('header .hint').textContent"}],
                size="390x844", mobile=True)
    assert out["ok"], out
    help_, tools = out["out"][1], out["out"][2]
    assert help_[1] > tools[3] or help_[2] <= tools[0], (help_, tools)          # below the tool column
    assert "pinch" in out["out"][3] and "? for keys" not in out["out"][3] and "right-drag" not in out["out"][3]
    out = probe(path, [{"key": "m"}, {"eval": rect + "('#fr-menu')"},
                       {"eval": "[...document.querySelectorAll('#fr-tools button')].filter(b => b.offsetParent).map(b => { var r = b.getBoundingClientRect(); return [r.left, r.right]; })"},
                       {"eval": "frPage.fileName(document.title)"}], size="844x390")
    menu, btns = out["out"][1], out["out"][2]
    assert len({round(b[0]) for b in btns}) == 1, btns                          # one column
    assert all(menu[2] <= b[0] + 0.5 for b in btns), (menu, btns)               # the menu leaves them free
    assert out["out"][3] == "Plat - test"                                       # 21f: a plain-letter file name
    # row 16: "off" not a list, "turn" a number, … – the page starts and the bad fields are dropped
    key = "fresing-player:" + "/" + str(path).lstrip("/").replace("\\", "/")
    bad = json.dumps({"off": "sea", "turn": 3, "quality": 7, "speed": "fast", "tools": [1]})
    out = probe(path, [{"eval": f"localStorage.setItem(location.pathname ? 'fresing-player:' + location.pathname : {json.dumps(key)}, {json.dumps(bad)})"},
                       {"reload": True}, {"eval": "[frPage.ready, frPage.errors.length, frPage.turn]"}])
    assert out["ok"], out
    assert out["out"][2] == [True, 0, False]


@browser_test
def test_the_link_leaves_out_what_the_page_switched_off(tmp_path):
    """0147 row 21d: a software-drawing browser switches shadows off itself; its link no longer says off=shadows."""
    path, _g = write(tmp_path / "soft.html", shadows=True)
    out = probe(path, [{"eval": "[frPage.warned, frPage.on.shadows]"}, {"eval": "frPage.viewLink()"},
                       {"eval": "frPage.setItem('shadows', true), frPage.setItem('shadows', false), frPage.viewLink()"}],
                query="")
    assert out["out"][0] == ["software", False]
    assert "off=" not in out["out"][1]
    assert "off=shadows" in out["out"][2]                   # the visitor's own choice is in the link


# ---------------------------------------------------------------------------
# what the independent tester found (task 0135): each a test that failed before the fix
# ---------------------------------------------------------------------------

def test_shallow_cones_and_small_fillets_are_not_cylinders():
    """A cone from Ø2000 to Ø1996.8 read as "Ø 1998.4 mm", an R0.35 fillet on a Ø400 edge as "Ø 400.60 mm"."""
    a = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    for r0, r1 in ((1.0, 0.9984), (0.2, 0.20035)):
        pts = np.array([[r0 * np.cos(x), r0 * np.sin(x), 0.0] for x in a] + [[r1 * np.cos(x), r1 * np.sin(x), 0.05]
                                                                             for x in a])
        tri = np.array([[i, (i + 1) % 64, 64 + (i + 1) % 64] for i in range(64)] +
                       [[i, 64 + (i + 1) % 64, 64 + i] for i in range(64)])
        rows = wf.classify(pts, tri, np.zeros(128, int), [0, 0, 0, 0, 0, 1, r0], [0, 128, 0])
        assert rows[0][0] == wf.AXIS, (r0, r1)
    # a true cylinder far from its part's origin (32-bit points) stays round
    pts, _n, tri, starts, axes, af = cylinder(1.0, 0.5)
    pts = (pts + [20.0, 0, 0]).astype(np.float32).astype(np.float64)
    axes = [20.0, 0, 0, 0, 0, 1, 1.0]
    rows = wf.classify(pts, tri, wf.face_of_triangles(len(tri), starts), axes, af)
    assert rows[0][0] == wf.ROUND and abs(rows[0][7] - 1.0) < 1e-5


def tube_model() -> bytes:
    """A block, a red cable drawn by the page (task 0142) in front of it, and a sticker (decal) on the block's top."""
    from fresing_render.core import web3d_tubes as TT
    g = web3d.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.62, 0.65, 1], "metallicFactor": 0},
                       "doubleSided": True})
    red = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.9, 0.05, 0.05, 1], "metallicFactor": 0},
                      "doubleSided": True})
    root = g.node({"name": "Model", "rotation": list(web3d.Z_UP_TO_Y_UP)})
    pts, nrm, tri, starts, _a, _f = box(0, 0, 0, 0.4, 0.2, 0.1)
    m = g.mesh("Block", pts, web3d.quantize_normals(nrm), None, [(look, tri)])
    g.place_mesh({"name": "Block", "extras": {"fr_card": "Block"}}, m, root)
    sp, sn, st_, _s, _a, _f = box(0.15, 0.05, 0.1, 0.25, 0.15, 0.1002)
    ms = g.mesh("Sticker", sp, web3d.quantize_normals(sn), None, [(red, st_)])
    g.place_mesh({"name": "Decal 3", "extras": {"fr_decal": 1}}, ms, root)
    line = np.array([[x, -0.15, 0.05] for x in np.linspace(-0.1, 0.5, 13)])
    tp, tn, tt, _s, _a, _f = box(0, -0.16, 0.04, 0.02, -0.14, 0.06)
    mc = g.mesh("Cable", tp, web3d.quantize_normals(tn), None, [(red, tt)])
    spec = {"v": TT.VERSION, "sides": 12, "r": 0.02, "unit": 1.0, "n": len(line), "k": 1,
            "lo": g.accessor(line.astype(np.float32), "VEC3"),
            "n0": g.accessor(np.array([[0, 0, 1.0]], np.float32), "VEC3"),
            "s0": g.accessor(np.array([0.0], np.float32), "SCALAR")}
    g.place_mesh({"name": "Cable", "extras": {"fr_card": "Cable", "fr_tube": spec}}, mc, root)
    return g.glb()


def screen_eval(p, then="return [s.x, s.y];"):
    return f"(function () {{ var s = frPage.partTools.screenOf({json.dumps(p)}); {then} }})()"


@browser_test
def test_cables_drawn_by_the_page_stickers_cut_faces_and_fade(tmp_path):
    st = env.settings(dict(env.default_choice(), shadows=False, auto=False), [-0.1, -0.2, 0.0], [0.5, 0.2, 0.1],
                      sky={"kind": "SKY", "sun": env.sun_vector(40, 30)}, plain=True)
    path = str(tmp_path / "tube.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(env.page_html("Tubes", tube_model(), st))
    pick = "return frPage.partTools.pickAt(s.x, s.y);"
    steps = [{"eval": "frPage.setCamera([0.2, 0.15, 0.9], [0.2, 0.05, 0.0])"}, {"wait": 300},
             {"eval": screen_eval([0.3, -0.15, 0.05], pick)},                       # 2: the cable, not the block
             {"eval": screen_eval([0.2, 0.1, 0.1002], pick)},                        # 3: the sticker: its part
             {"key": "t"}, {"eval": screen_eval([0.05, 0.1, 0.1], "return frPage.partTools.click(s.x, s.y).fade;")},
             {"eval": "(function () { var t = null; frPage.three.top.traverse(function (o) { if (o.userData.frTube) t = o; });"
                      " return [t.material.transparent, !!t.material.onBeforeCompile && t.material.onBeforeCompile.toString().length > 50]; })()"},
             {"key": "Escape"},                                                       # 7
             {"eval": "frPage.partTools.setCut(true, 'X', 0.5)"},                     # 8: cut, then fade, then move
             {"eval": screen_eval([0.05, 0.1, 0.1], "return frPage.partTools.click(s.x, s.y).fade;")},
             {"eval": "frPage.partTools.setCut(true, 'X', 0.9)"}, {"eval": "frPage.partTools.state()"},   # 10, 11
             {"key": "Escape"}, {"key": "t"}, {"key": "d"},                           # 12-14
             {"eval": "frPage.partTools.setCut(true, 'X', 0.4, true)"},              # 15: keep x > 0.14
             {"eval": "frPage.setCamera([-0.6, 0.3, 0.3], [0.2, 0.05, -0.1])"}, {"wait": 300},
             {"eval": screen_eval([0.14, 0.1, 0.05], "return frPage.partTools.click(s.x, s.y).result;")},   # 18
             ]
    out = probe(path, steps)
    assert out["ok"], out
    o = out["out"]
    assert o[2] and o[2]["card"] == "Cable", o[2]
    assert o[3] and o[3]["card"] == "Block", o[3]
    assert o[5] == "Block" and o[6] == [True, True]          # the faded cable is still drawn, see-through
    assert o[11]["fade"] == "Block" and o[11]["stale"] == 0 and o[11]["clipped"] >= 3
    r = o[18]
    assert r["picks"][0]["kind"] == "flat" and abs(r["picks"][0]["p"][0] - 0.14) < 1e-6, r   # on the red cut face


@browser_test
def test_a_slow_mouse_click_measures_and_esc_closes_the_help_first(tmp_path):
    path, _g = write(tmp_path / "slow.html")
    out = probe(path, [{"eval": CAM}, {"wait": 300}, {"key": "d"}, {"eval": at("shaft_side")}])
    x, y = out["out"][3]
    out = probe(path, [{"eval": CAM}, {"wait": 300}, {"key": "d"}, {"press": [x, y, 1200]},
                       {"eval": "frPage.partTools.state()"},                                       # 4
                       {"key": "?"}, {"key": "Escape"}, {"eval": "[frPage.helpOpen, frPage.partTools.state().picks]"},
                       {"eval": "frPage.fileName('Kabelføring Größe – Ø 40 Æble')"}])
    assert out["ok"], out
    o = out["out"]
    assert o[4]["picks"] == 1 and o[4]["card"] is None
    assert o[7] == [False, 1]
    assert o[8] == "Kabelforing Grosse - O 40 AEble"
