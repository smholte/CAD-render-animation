"""Measure in the 3D view (task 0322): the maths (the same as the 3D page's), snapping, the crane's known sizes, a
slice's cut face, parts that move, saving (Keep measurements, the Client view), units, copy, the keys, renders."""

import json
import math
import os
import shutil
import subprocess
import sys

import pytest

from fresing_render.core import measure as core

HERE = os.path.dirname(__file__)
MEASURE_JS = os.path.join(HERE, "..", "fresing_render", "web", "fr_measure.js")
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
NODE = shutil.which("node")


# ---------------------------------------------------------------------------
# the maths, no Blender
# ---------------------------------------------------------------------------

def _js(p: core.Pick) -> dict:
    d = {"kind": p.kind, "p": list(p.p)}
    if p.kind == "flat":
        d["n"] = list(p.n)
    if p.kind in ("round", "axis", "line", "circle"):
        d.update(o=list(p.o), d=list(p.d), r=p.r)
    if p.kind == "line":
        d.update(a=list(p.a), b=list(p.b), len=p.length)
    if p.kind == "circle":
        d.update(c=list(p.o), s=list(p.s), sweep=p.sweep)
    return d


CASES = [
    (core.flat((0.1, 0.1, 0.1), (0, 0, 1)), core.flat((0.6, 0.1, 0.15), (0, 0, -1))),
    (core.flat((0.1, 0.1, 0.1), (0, 0, 1)), core.flat((0.6, 0.1, 0.15), (0, math.sin(0.5 * math.pi / 180),
                                                                         math.cos(0.5 * math.pi / 180)))),
    (core.flat((0.1, 0.1, 0.1), (0, 0, 1)), core.flat((0.2, 0, 0.05), (0, -1, 0))),
    (core.round_face((0.6, 0.08, 0.07), (0.6, 0.1, 0), (0, 0, 1), 0.02),
     core.round_face((0.8, 0.085, 0.03), (0.8, 0.1, 0), (0, 0, -1), 0.015)),
    (core.round_face((0.6, 0.08, 0.07), (0.6, 0.1, 0), (0, 0, 1), 0.02),
     core.round_face((0, 0, 0.3), (0, 0, 0.3), (1, 0, 0), 0.01)),
    (core.flat((0.4, 0.03, 0.05), (1, 0, 0)), core.round_face((0.6, 0.08, 0.07), (0.6, 0.1, 0), (0, 0, 1), 0.02)),
    (core.round_face((0.6, 0.08, 0.07), (0.6, 0.1, 0), (0, 0, 1), 0.02), core.flat((0.4, 0.03, 0.05), (1, 0, 0))),
    (core.point((0, 0, 0)), core.point((0.3, 0.4, 0.12))),
    (core.line((0.1, 0, 0), (0, 0, 0), (0.5, 0, 0)), core.line((0.2, 0.1, 0.02), (0, 0.1, 0.02), (0.4, 0.1, 0.02))),
    (core.line((0.1, 0, 0), (0, 0, 0), (0.5, 0, 0)), core.point((0.2, 0.3, 0.4))),
    (core.point((0.2, 0.3, 0.4)), core.line((0.1, 0, 0), (0, 0, 0), (0.5, 0, 0))),
    (core.circle((0, 0, 0), (0.1, 0.1, 0), (0.12, 0.1, 0), (0, 0, 1), 2 * math.pi),
     core.circle((0, 0, 0), (0.3, 0.1, 0.05), (0.32, 0.1, 0.05), (0, 0, 1), 2 * math.pi)),
    (core.circle((0, 0, 0), (0.1, 0.1, 0), (0.12, 0.1, 0), (0, 0, 1), 2 * math.pi), core.flat((0, 0, 0.3), (0, 0, 1))),
    (core.flat((0, 0, 0.3), (0, 0, 1)), core.circle((0, 0, 0), (0.1, 0.1, 0), (0.12, 0.1, 0), (0, 0, 1), math.pi)),
    (core.flat((0, 0, 0.3), (0, 0, 1)), core.line((0.1, 0, 0), (0, 0, 0), (0.5, 0, 0.2))),
]


@pytest.mark.skipif(NODE is None, reason="no node")
def test_the_same_numbers_as_the_3d_page():
    """Every pair as the page's measure(a, b, 'faces') gives it: type, distance, angle, the line drawn."""
    expr = "[" + ", ".join(f"M.measure({json.dumps(_js(a))}, {json.dumps(_js(b))}, 'faces')" for a, b in CASES) + "]"
    code = f"const M = require({json.dumps(MEASURE_JS)}); console.log(JSON.stringify({expr}));"
    out = json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)
    for (a, b), js in zip(CASES, out):
        py = core.pair(a, b)
        assert py.type == js["type"], (py.type, js["type"])
        assert abs((py.dist or 0.0) - (js.get("dist") or 0.0)) < 1e-12, (py.type, py.dist, js.get("dist"))
        if js.get("angle") is not None:
            assert abs(py.angle - js["angle"]) < 1e-9
        for k_py, k_js in (("frm", "from"), ("to", "to")):
            got, want = getattr(py, k_py), js.get(k_js)
            assert want is None or all(abs(x - y) < 1e-12 for x, y in zip(got, want)), (py.type, k_py, got, want)
    singles = [core.round_face((0, 0, 0), (0, 0, 0), (0, 0, 1), 0.0165), CASES[8][0], CASES[11][0], CASES[13][1]]
    expr = "[" + ", ".join(f"M.single({json.dumps(_js(a))})" for a in singles) + "]"
    code = f"const M = require({json.dumps(MEASURE_JS)}); console.log(JSON.stringify({expr}));"
    out = json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)
    for a, js in zip(singles, out):
        py = core.single(a)
        assert py.type == js["type"] and abs((py.dist or 0) - (js.get("dist") or 0)) < 1e-12


def test_units_words_and_parts():
    assert core.fmt(0.5) == "500.00 mm"
    assert core.fmt(4.5) == "4 500.00 mm"
    assert core.fmt(0.5, "M") == "0.5000 m"
    assert core.fmt(0.0254, "INCH") == "1.000 in"
    assert core.fmt(-0.0025) == "−2.50 mm" and core.fmt(-1e-9) == "0.00 mm"
    r = core.measure("DISTANCE", [core.point((0, 0, 0)), core.point((0.01, -0.0025, 1.2345))])
    assert r.lines == ["Distance 1 234.54 mm", "X 10.00 · Y −2.50 · Z 1 234.50 mm"]
    assert r.value_text("MM") == "1234.54 mm" and r.value_text("INCH") == "48.604 in"
    assert [(q["axis"], round(q["value"], 9)) for q in core.parts((0, 0, 0), (0.3, -0.4, 0.0))] == [("X", 0.3),
                                                                                                   ("Y", -0.4)]
    a = core.measure("ANGLE", [core.point((1, 0, 0)), core.point((0, 0, 0)), core.point((0, 1, 1))])
    assert abs(a.angle - 90.0) < 1e-9 and a.value_text() == "90.00°"
    two = core.measure("ANGLE", [core.flat((0, 0, 0), (0, 0, 1)), core.flat((1, 0, 0), (0, math.sin(0.5), math.cos(0.5)))])
    assert abs(two.angle - math.degrees(0.5)) < 1e-9 and "(or " in two.lines[1]


def test_kinds_ask_for_the_right_clicks():
    pt, fl = core.point((0, 0, 0)), core.flat((0, 0, 0), (0, 0, 1))
    rd = core.round_face((0, 0, 0), (0, 0, 0), (0, 0, 1), 0.01)
    cone = core.round_face((0, 0, 0), (0, 0, 0), (0, 0, 1), 0.0)
    ln = core.line((0, 0, 0), (0, 0, 0), (1, 0, 0))
    assert core.needs("EDGE", []) == 1 and core.needs("RADIUS", []) == 1 and core.needs("DISTANCE", []) == 2
    assert core.needs("ANGLE", [pt]) == 3 and core.needs("ANGLE", [fl]) == 2
    assert core.refuse("FACES", 0, [], rd) == "Click a flat face" and core.refuse("FACES", 0, [], fl) == ""
    assert core.refuse("RADIUS", 0, [], rd) == "" and "no single diameter" in core.refuse("RADIUS", 0, [], cone)
    assert core.refuse("EDGE", 0, [], fl).startswith("Click an edge") and core.refuse("EDGE", 0, [], ln) == ""
    assert core.refuse("AXIS", 1, [pt], fl).startswith("Click a hole") and core.refuse("AXIS", 1, [pt], ln) == ""
    assert core.measure("AXIS", [ln, core.point((0.5, 0.3, 0.4))]).dist == pytest.approx(0.5)
    assert core.measure("RADIUS", [rd]).lines[0].startswith("Ø 20.00 mm")
    assert core.measure("DISTANCE", [pt]) is None                     # a click still to come


def test_snapping_takes_points_then_edges_then_the_face():
    face = core.Candidate("face", core.flat((0, 0, 0), (0, 0, 1)))
    corner = core.Candidate("corner", core.point((1, 1, 0), "corner"), screen=(110, 100))
    edge = core.Candidate("edge", core.line((0, 0, 0), (0, 0, 0), (1, 0, 0)), segs=[((0, 50), (200, 50))],
                          world_segs=[((0, 0, 0), (1, 0, 0))])
    cands = [face, corner, edge]
    assert core.choose(cands, (100, 100))[0] is corner                       # 10 px: within SNAP_PX
    assert core.choose(cands, (100, 58))[0] is edge                          # 8 px from the edge
    c, at = core.choose(cands, (50, 58))
    assert c is edge and at == pytest.approx((0.25, 0.0, 0.0))               # the point on the edge under the mouse
    assert core.choose(cands, (100, 80))[0] is face                          # nothing near: the face
    assert core.choose(cands, (100, 100), no_snap=True)[0] is face           # Shift
    assert core.choose(cands, (100, 80), offer="edges")[0] is edge           # Edge length: the face's nearest edge
    assert core.choose(cands, (100, 100), offer="faces")[0] is face          # Face to face: faces only
    pts = core.circle_points((0, 0, 0), (1, 0, 0), (0, 0, 2 * math.pi), 8)
    assert len(pts) == 9 and pts[2] == pytest.approx((0.0, 1.0, 0.0), abs=1e-12)


# ---------------------------------------------------------------------------
# in Blender (as a Python module)
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Euler, Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, lock, measure, ops_measure, section  # noqa: E402

S = 200.0                                      # px per metre of the test's top view


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def scene(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("measure"))
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    bpy.context.view_layer.update()
    return sc


def base(sc):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == "BASE")


def look(sc, x, y, kind="SMART", picks=None, up=False, no_snap=False):
    """The mouse at (x, y) m in a view straight down (``up``: straight up, from under the crane)."""
    o, d = (Vector((x, y, -2.0)), Vector((0, 0, 1))) if up else (Vector((x, y, 9.0)), Vector((0, 0, -1)))
    return measure.look(sc, bpy.context.evaluated_depsgraph_get(), o, d, (x * S, y * S),
                        lambda p: (p[0] * S, p[1] * S), kind, picks or [], no_snap=no_snap)


def test_the_base_measures_its_known_sizes(scene):
    a = look(scene, 1.0, 1.2, "FACES")
    b = look(scene, 1.0, 1.2, "FACES", [(a.part, a.pick)], up=True)
    assert a.part == b.part == base(scene).name and not a.refused and not b.refused
    r = core.measure("FACES", [a.pick, b.pick])
    assert r.type == "planes" and abs(r.dist - 0.5) < 1e-5 and r.lines[0] == "Between the planes 500.00 mm"
    # a bolt hole from below: its rim (a round edge) is Ø33
    h = look(scene, 0.25 + 0.019, 0.25, "RADIUS", up=True)
    assert h.cand.kind == "edge" and h.pick.kind == "circle" and abs(2 * h.pick.r - 0.033) < 1e-5
    assert core.measure("RADIUS", [h.pick]).lines[0] == "Ø 33.00 mm  (radius 16.50 mm)"
    # snapping: 20 mm from a hole's centre (4 px) takes the centre; two holes 4500 mm apart
    p1 = look(scene, 0.25 + 0.02, 0.25, "DISTANCE", up=True)
    p2 = look(scene, 4.75 + 0.02, 0.25, "DISTANCE", [(p1.part, p1.pick)], up=True)
    assert p1.cand.kind == p2.cand.kind == "centre"
    r = core.measure("DISTANCE", [p1.pick, p2.pick])
    assert abs(r.dist - 4.5) < 1e-5 and r.lines[1].startswith("X 4 500.00 · Y 0.00 · Z 0.00")
    # Shift: no snap – the spot under the mouse
    ns = look(scene, 0.25 + 0.02, 0.25, "DISTANCE", up=True, no_snap=True)
    assert ns.pick.p == pytest.approx((0.27, 0.25, 0.0), abs=1e-6)
    # point to axis: a hole's centre to the other hole's axis
    ax = look(scene, 4.75 + 0.019, 0.25, "AXIS", [(p1.part, p1.pick)], up=True)
    assert ax.pick.is_axis_like() and abs(core.measure("AXIS", [p1.pick, ax.pick]).dist - 4.5) < 1e-5
    # an edge: the base's long top edge (5000 mm, less its chamfered corners)
    e = look(scene, 2.5, 0.03, "EDGE")
    assert e.pick.kind == "line" and 4.7 < e.pick.length < 5.0
    # a refused click says why
    f = look(scene, 1.0, 1.2, "RADIUS")
    assert f.refused.startswith("Click a round face")


def test_a_measurement_follows_its_part_and_is_kept(scene, tmp_path):
    ob = base(scene)
    st = measure.settings(scene)
    st.items.clear()
    a = look(scene, 0.25 + 0.02, 0.25, "DISTANCE", up=True)
    b = look(scene, 4.75 + 0.02, 0.25, "DISTANCE", [(a.part, a.pick)], up=True)
    item = measure.add(scene, "DISTANCE", [(ob, measure.to_local(ob, a.pick)), (ob, measure.to_local(ob, b.pick))])
    before = measure.result(scene, item)
    try:
        ob.rotation_euler = (0.0, 0.0, 0.5)
        ob.location = (1.0, 2.0, 0.3)
        bpy.context.view_layer.update()
        moved = measure.result(scene, item)
        assert abs(moved.dist - before.dist) < 1e-5
        assert moved.vec[0] == pytest.approx(4.5 * math.cos(0.5), abs=1e-5)       # the world's X part changed
    finally:
        ob.rotation_euler = (0.0, 0.0, 0.0)
        ob.location = (0.0, 0.0, 0.0)
        bpy.context.view_layer.update()
    # saved with the project, and left out with Keep measurements off
    path = str(tmp_path / "kept.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    assert len(st.items) == 1
    st.keep = False
    path2 = str(tmp_path / "not kept.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path2, copy=True)
    assert len(st.items) == 1 and measure.result(scene, st.items[0]).dist == pytest.approx(4.5, abs=1e-5)
    st.keep = True
    got = {}
    for p, key in ((path, "kept"), (path2, "not")):
        out = subprocess.run([sys.executable, "-c",
                              "import bpy, sys; sys.path.insert(0, %r); import addon_utils, fresing_render;"
                              "fresing_render.register(); bpy.ops.wm.open_mainfile(filepath=%r);"
                              "print('N=', len(bpy.context.scene.fresing_measure.items))"
                              % (os.path.dirname(HERE), p)], capture_output=True, text=True, timeout=240)
        got[key] = [ln for ln in out.stdout.splitlines() if ln.startswith("N=")]
    assert got == {"kept": ["N= 1"], "not": ["N= 0"]}, got


def test_the_client_view_measures_but_never_saves(scene, monkeypatch):
    assert lock.allowed("fresing.measure") and lock.allowed("fresing.measure_copy")
    assert lock.allowed("fresing.measure_clear") and lock.allowed("fresing.measure_key")
    from fresing_render.blender import workspaces
    monkeypatch.setattr(workspaces, "locked", lambda _sc: True)
    assert measure.leave_out_of_save(scene)
    monkeypatch.setattr(workspaces, "locked", lambda _sc: False)
    assert not measure.leave_out_of_save(scene)


def test_a_slice_is_measured_on_its_cut_face(scene):
    ob = base(scene)
    cut = section.add(scene, [("PART", ob, "")], "PLANE")
    try:
        # the plane at y = 1.5 m, its arrow to the front (-Y): the front half of the base goes
        section.set_world(scene, cut, Matrix.Translation((2.5, 1.5, 0.25)) @ Euler((math.pi / 2, 0, 0)).to_matrix().to_4x4())
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        hit = measure.cast(scene, dg, Vector((2.3, -5.0, 0.25)), Vector((0, 1, 0)))
        assert hit is not None and hit.cut == cut.name and hit.location.y == pytest.approx(1.5, abs=1e-6)
        assert hit.normal.y == pytest.approx(-1.0, abs=1e-6)
        a = measure.look(scene, dg, Vector((2.3, -5.0, 0.25)), Vector((0, 1, 0)), (0, 0), lambda p: None, "FACES")
        b = measure.look(scene, dg, Vector((2.3, 8.0, 0.25)), Vector((0, -1, 0)), (0, 0), lambda p: None, "FACES",
                         [(a.part, a.pick)])
        assert a.text.startswith("cut face of") and core.measure("FACES", [a.pick, b.pick]).dist == pytest.approx(1.5, abs=1e-5)
        cut.enabled = False                   # off: the ray meets the base's own front face again
        bpy.context.view_layer.update()
        hit = measure.cast(scene, bpy.context.evaluated_depsgraph_get(), Vector((2.3, -5.0, 0.25)), Vector((0, 1, 0)))
        assert hit.cut == "" and hit.location.y == pytest.approx(0.0, abs=1e-6)
    finally:
        section.remove(scene, cut)
        bpy.context.view_layer.update()


def test_units_copy_remove_clear(scene):
    st = measure.settings(scene)
    st.items.clear()
    a = look(scene, 1.0, 1.2, "FACES")
    b = look(scene, 1.0, 1.2, "FACES", [(a.part, a.pick)], up=True)
    ob = base(scene)
    measure.add(scene, "FACES", [(ob, measure.to_local(ob, a.pick)), (ob, measure.to_local(ob, b.pick))])
    st.units = "INCH"
    assert measure.result(scene, st.items[0]).lines[0] == "Between the planes 19.685 in"
    assert bpy.ops.fresing.measure_copy(index=0) == {"FINISHED"}
    assert ops_measure.COPIED[0] == "19.685 in"
    st.units = "MM"
    assert bpy.ops.fresing.measure_copy(index=0) == {"FINISHED"}
    assert ops_measure.COPIED[0] == "500.00 mm"
    measure.add(scene, "FACES", [(ob, measure.to_local(ob, a.pick)), (ob, measure.to_local(ob, b.pick))])
    assert bpy.ops.fresing.measure_remove(index=0) == {"FINISHED"} and len(st.items) == 1
    assert bpy.ops.fresing.measure_clear() == {"FINISHED"} and len(st.items) == 0


def test_never_in_renders_unless_ticked(scene):
    st = measure.settings(scene)
    st.items.clear()
    a = look(scene, 0.25 + 0.02, 0.25, "DISTANCE", up=True)
    b = look(scene, 4.75 + 0.02, 0.25, "DISTANCE", [(a.part, a.pick)], up=True)
    ob = base(scene)
    measure.add(scene, "DISTANCE", [(ob, measure.to_local(ob, a.pick)), (ob, measure.to_local(ob, b.pick))])
    assert bpy.data.collections.get(measure.COLLECTION) is None          # drawn in the view only
    st.in_renders = True
    col = bpy.data.collections.get(measure.COLLECTION)
    assert col is not None and len(col.objects) == 3                     # the lines, one label and its box
    text = next(o for o in col.objects if o.type == "FONT")
    assert text.data.body.startswith("Distance 4 500.00 mm")
    assert all(o.get(build.PROP_KIND) == measure.KIND and not o.hide_render for o in col.objects)
    st.in_renders = False
    assert bpy.data.collections.get(measure.COLLECTION) is None
    st.items.clear()


def test_the_keys_and_the_top_bar():
    app = {(km, k, tuple(sorted(m.items()))): op for km, _sp, k, m, op, _p in lock.APP_KEYS}
    assert app[("Object Mode", "M", ())] == "fresing.measure_key"
    assert app[("Object Mode", "M", (("alt", True),))] == "fresing.measure"
    assert not any(k == "M" and not m for _km, _sp, k, m, _w in lock.BLENDER_KEYS)   # M is no longer swallowed
    from fresing_render.blender import ui_topbar
    assert ui_topbar._draw_in_editor_menus in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize()
    assert hasattr(bpy.types, "TOPBAR_PT_fresing_measure")
    for k in core.KINDS:
        assert k in core.TITLES and k in core.HELP and k in core.ICONS
