"""Task 0318: carbon fibre without a seam a real part would not have, perlage, the group's Rust slider (one rust look),
spheres with their axis, and the improved looks.

Without Blender: where rust is logical, the weave's frame per face (``core.finishes.weave_frames``) on made-up
meshes – a fold continues, a closed ring keeps its own frame –, spheres (``_sphere``). In Blender (as a Python module):
the Rust slider in a group's material, nothing on stainless, one ambient-occlusion lookup for Wear and Rust, the welds
reading it, the web model's bake keeps the rust colour, glass lets shadows through, the yellow zinc's film."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fresing_render.core import finishes as fc  # noqa: E402
from fresing_render.core import materials_lib  # noqa: E402

# ---------------------------------------------------------------------------------------------------------------
# without Blender
# ---------------------------------------------------------------------------------------------------------------


def test_rust_only_where_it_is_logical():
    rk = materials_lib.rust_kind
    for m in ("steel_raw", "steel_machined", "steel_ground", "steel_turned", "cast_iron", "shot_blasted"):
        assert rk(m) == "BARE", m
    for m in ("paint_satin", "paint_gloss", "powder_coat", "cast_iron_painted", "hammertone", "paint_marine_growth"):
        assert rk(m) == "PAINTED", m
    for m in ("galvanized", "zinc_plated", "spangle", "wire_rope_galv"):
        assert rk(m) == "ZINC", m
    for m in ("chrome", "chrome_rod"):
        assert rk(m) == "PLATED", m
    for m in ("stainless_brushed", "stainless_polished", "aluminium_machined", "aluminium_anodized", "brass", "copper",
              "rubber_black", "glass_clear", "carbon_fibre", "paint_blade_eroded", "from_file", "perlage"):
        assert rk(m) == "", m
        assert materials_lib.no_rust_why(m), m
    assert "Stainless" in materials_lib.no_rust_why("stainless_brushed")
    assert "Aluminium" in materials_lib.no_rust_why("aluminium_machined")
    # a finish's metal decides: a steel knurl rusts, a stainless one does not; sand-cast iron rusts, aluminium not
    assert rk("knurl_diamond", "STEEL") == "BARE" and rk("knurl_diamond", "STAINLESS") == ""
    assert rk("perforated", "GALVANIZED") == "ZINC" and rk("honed", "CAST_IRON") == "BARE"
    assert rk("as_cast", kind="CAST_FE") == "BARE" and rk("as_cast", kind="CAST_AL") == ""
    assert rk("no such material") == ""


def test_rust_mask_grows_with_the_slider_and_in_corners():
    from fresing_render.blender import rust
    for p in (0.3, 0.5, 0.7):
        vals = [rust.mask_value(p, 0.0, a) for a in (0.0, 0.25, 0.5, 0.75, 1.0)]
        assert vals == sorted(vals)
    assert rust.mask_value(0.5, 0.0, 0.0) == 0.0                 # 0: none
    assert rust.mask_value(0.45, 0.8, 0.5) > rust.mask_value(0.45, 0.0, 0.5)     # a corner rusts first
    assert rust.mask_value(0.9, 0.0, 1.0) == 1.0


def _grid(nu, nv, fn):
    """A triangle grid of fn(i/nu, j/nv) -> point."""
    pts = np.array([fn(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)], float)
    tri = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            tri += [[a, a + 1, a + nu + 2], [a, a + nu + 2, a + nu + 1]]
    return pts, np.array(tri)


def _folded_l():
    """A flat floor (z = 0, x < 0), a 90° bend of radius 5 mm round the y axis line at (0, 0, 5 mm), a wall (x = 5 mm,
    z > 5 mm): three CAD faces, outer side up / out."""
    r = 0.005
    floor = _grid(4, 3, lambda u, v: (-0.03 + 0.03 * u, 0.04 * v, 0.0))
    bend = _grid(6, 3, lambda u, v: (r * math.sin(u * math.pi / 2), 0.04 * v, r - r * math.cos(u * math.pi / 2)))
    wall = _grid(4, 3, lambda u, v: (r, 0.04 * v, r + 0.03 * u))
    co, tri, starts = [], [], []
    for pts, t in (floor, bend, wall):
        starts.append(sum(len(x) for x in tri))
        tri.append(t + sum(len(c) for c in co))
        co.append(pts)
    co, tri = np.vstack(co), np.vstack(tri)
    starts.append(len(tri))
    # the bend's axis: along y through (0, 0, r); its outside faces away from the axis (k = 1) – the floor and wall
    # normals point up / out (+z, +x)
    n0 = len(floor[1])
    nb = len(bend[1])
    axes = [0.0, 0.0, r, 0.0, 1.0, 0.0, r]
    return co, tri, axes, [n0, nb, 0], starts


def test_weave_continues_across_a_fold():
    co, tri, axes, axf, starts = _folded_l()
    o, d, r, k = fc.face_frames(co, tri, axes, axf, starts)
    assert set(np.unique(k)) <= {0.0, 1.0, -1.0, 2.0}
    a, b = fc.weave_frames(co, tri, o, d, r, k, starts)
    faces = [(starts[i], starts[i + 1]) for i in range(3)]

    def glob(fi, pts):
        t0 = faces[fi][0]
        kind = int(round(k[t0]))
        th0 = b[t0, 2]
        n = fc._native(kind, pts, o[t0], d[t0], r[t0], th0)
        c, s, det = a[t0]
        n[:, 1] *= det
        return np.stack([c * n[:, 0] - s * n[:, 1], s * n[:, 0] + c * n[:, 1]], 1) + b[t0, :2]

    # the shared edges: floor | bend at x = 0, z = 0; bend | wall at x = r, z = r
    e1 = np.array([(0.0, y, 0.0) for y in np.linspace(0, 0.04, 4)])
    e2 = np.array([(0.005, y, 0.005) for y in np.linspace(0, 0.04, 4)])
    assert np.allclose(glob(0, e1), glob(1, e1), atol=2e-5)
    assert np.allclose(glob(1, e2), glob(2, e2), atol=2e-5)
    # unfolded, the wall lies the bend's arc further on: floor edge to wall edge across is the arc length
    across = np.abs(glob(2, e2) - glob(0, e1))
    arc = 0.005 * math.pi / 2
    assert np.allclose(np.max(across, axis=1), arc, atol=5e-5)


def test_a_closed_ring_and_a_sphere_keep_their_own_frame():
    r = 0.02
    tube = _grid(24, 4, lambda u, v: (r * math.cos(2 * math.pi * u * 0.9999), r * math.sin(2 * math.pi * u * 0.9999),
                                      0.05 * v))
    co, tri = tube
    o, d, rr, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 1, r], [0, len(tri), 0], [0, len(tri)])
    a, b = fc.weave_frames(co, tri, o, d, rr, k, [0, len(tri)])
    assert (k == 1).all() and (b[:, 2] == -1.0).all() and np.allclose(a, (1.0, 0.0, 1.0))
    # half a tube (a bend): open, its theta0 in the middle of its gap
    half = _grid(12, 4, lambda u, v: (r * math.cos(math.pi * u), r * math.sin(math.pi * u), 0.05 * v))
    co, tri = half
    o, d, rr, k = fc.face_frames(co, tri, [0, 0, 0, 0, 0, 1, r], [0, len(tri), 0], [0, len(tri)])
    a, b = fc.weave_frames(co, tri, o, d, rr, k, [0, len(tri)])
    th = fc._theta(co - o[0], d[0])
    assert 0.0 <= b[0, 2] < 2 * math.pi and not np.any(np.abs(np.mod(th - b[0, 2], 2 * math.pi)) < 1e-6)


def test_sphere_or_not():
    o, d = np.zeros(3), np.array([0.0, 0.0, 1.0])
    ring = np.array([(0.03 * math.cos(t), 0.03 * math.sin(t), z) for t in np.linspace(0, 6, 30) for z in (-0.002, 0, 0.002)])
    assert fc._sphere(ring, o, d) is None                         # a short band of a cylinder
    R, c = 0.1, np.array([0, 0, -0.09])
    dome = np.array([c + R * np.array([math.sin(p) * math.cos(t), math.sin(p) * math.sin(t), math.cos(p)])
                     for p in np.linspace(0, 0.25, 6) for t in np.linspace(0, 6, 12)])
    got = fc._sphere(dome, o, d)
    assert got is not None and np.allclose(got[0], c, atol=1e-9) and got[1] == pytest.approx(R)
    cone = np.array([((0.02 + 0.5 * z) * math.cos(t), (0.02 + 0.5 * z) * math.sin(t), z)
                     for z in np.linspace(0, 0.02, 5) for t in np.linspace(0, 6, 12)])
    assert fc._sphere(cone, o, d) is None


def test_carbon_and_perlage_settings():
    assert fc.settings_of("carbon_fibre") == ["kind", "size", "amount"]
    assert fc.pattern("carbon_fibre", {"kind": "PLAIN"})["twill"] == 0.0
    assert fc.pattern("carbon_fibre")["twill"] == 1.0 and fc.pattern("carbon_fibre")["gloss"] == 1.0
    assert fc.key("carbon_fibre", size=0.003, amount=0.0, kind="PLAIN") == "size=3;amount=0;kind=PLAIN"
    assert fc.needs_faces("carbon_fibre") and fc.needs_faces("perlage")
    assert fc.FINISHES["perlage"]["bases"][0] == "STAINLESS"
    assert materials_lib.UIDS["carbon_fibre"] == 85 and materials_lib.UIDS["perlage"] == 86


# ---------------------------------------------------------------------------------------------------------------
# in Blender
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def blender():
    bpy = pytest.importorskip("bpy")
    import addon_utils

    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def _mat(bpy, name, mid, colour="", wear=0.0, rust=0.0, finish=""):
    from fresing_render.blender import materials
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    materials.build_nodes(m, mid, colour, wear, finish=finish, rust=rust)
    return m


def _count(m, kind):
    return sum(1 for n in m.node_tree.nodes if n.type == kind)


def test_rust_in_the_material_only_where_logical(blender):
    bpy = blender
    from fresing_render.blender import materials, rust
    m = _mat(bpy, "r steel", "steel_raw", rust=0.6)
    assert m.node_tree.nodes.get(rust.NODE_MASK) is not None and m[rust.PROP] == pytest.approx(0.6)
    assert _count(m, "VALTORGB") == 1                             # the one rust colour ramp
    m = _mat(bpy, "r stainless", "stainless_brushed", rust=0.6)
    assert m.node_tree.nodes.get(rust.NODE_MASK) is None and m[rust.PROP] == 0.0
    m = _mat(bpy, "r zero", "steel_raw", rust=0.0)
    assert m.node_tree.nodes.get(rust.NODE_MASK) is None
    # Wear and Rust share one ambient-occlusion lookup
    m = _mat(bpy, "r both", "cast_iron", wear=0.5, rust=0.5)
    assert _count(m, "AMBIENT_OCCLUSION") == 1
    m = _mat(bpy, "r paint", "paint_satin", "RAL 5010", wear=0.0, rust=0.6)
    assert m.node_tree.nodes.get(rust.NODE_MASK) is not None and _count(m, "BEVEL") == 1    # rust needs worn edges
    m = _mat(bpy, "r galv", "galvanized", wear=0.3, rust=0.6)
    assert m.node_tree.nodes.get(rust.NODE_MASK) is not None
    # a steel knurl rusts, a stainless one not
    m = _mat(bpy, "r knurl", "knurl_diamond", rust=0.5, finish=fc.key("knurl_diamond", base="STEEL"))
    assert m[rust.PROP] == pytest.approx(0.5)
    m = _mat(bpy, "r knurl ss", "knurl_diamond", rust=0.5, finish=fc.key("knurl_diamond", base="STAINLESS"))
    assert m[rust.PROP] == 0.0
    # the rust value is part of what makes a material current
    m = _mat(bpy, "r cur", "steel_raw", rust=0.3)
    assert materials.is_current(m, "steel_raw", "", 0.0, "", 0.3)
    assert not materials.is_current(m, "steel_raw", "", 0.0, "", 0.5)
    assert materials.is_current(_mat(bpy, "r cur ss", "stainless_brushed"), "stainless_brushed", "", 0.0, "", 0.9)


def test_the_group_slider(blender):
    bpy = blender
    from fresing_render.blender import logic, materials, rust
    sc = bpy.data.scenes.new("rust group test")
    s = sc.fresing
    g = logic.ensure_group(s, "Rusty frame")
    g.material = "steel_raw"
    g.rust = 0.4
    mat = bpy.data.materials[materials.material_name(g.name)]
    assert mat[rust.PROP] == pytest.approx(0.4) and materials.group_rust_kind(g) == "BARE"
    g.material = "stainless_brushed"
    assert materials.group_rust_kind(g) == "" and "stainless" in materials.group_no_rust_why(g).lower()
    assert bpy.data.materials[materials.material_name(g.name)][rust.PROP] == 0.0
    g.material = "knurl_diamond"
    g.fin_base = "STEEL"
    assert materials.group_rust_kind(g) == "BARE"
    g.fin_base = "STAINLESS"
    assert materials.group_rust_kind(g) == ""
    bpy.data.scenes.remove(sc)


def test_marine_streaks_and_welds_use_the_one_rust(blender):
    bpy = blender
    from fresing_render.blender import rust, weld_looks
    m = _mat(bpy, "r marine", "paint_marine_streaks", "RAL 1023")
    ramps = [n for n in m.node_tree.nodes if n.type == "VALTORGB"]
    want = [rust._lin(c)[:3] for _p, c in rust.STOPS]
    assert any(len(r.color_ramp.elements) == len(want) and all(
        tuple(e.color)[:3] == pytest.approx(w, abs=1e-4) for e, w in zip(r.color_ramp.elements, want)) for r in ramps)
    wm = weld_looks.bead_material(weld_looks.bead_look("STEEL", "MAG", "AS_WELDED", False, False, {"bead": 0.6}))
    ramps = [n for n in wm.node_tree.nodes if n.type == "VALTORGB" and len(n.color_ramp.elements) == len(want)]
    assert any(tuple(r.color_ramp.elements[0].color)[:3] == pytest.approx(want[0], abs=1e-4) for r in ramps)


def test_glass_lets_shadows_through_and_zinc_has_its_film(blender):
    bpy = blender
    m = _mat(bpy, "g glass", "glass_clear")
    lp = [n for n in m.node_tree.nodes if n.type == "LIGHT_PATH"]
    assert lp and lp[0].outputs["Is Shadow Ray"].is_linked
    out = next(n for n in m.node_tree.nodes if n.type == "OUTPUT_MATERIAL" and n.target == "CYCLES")
    assert out.inputs["Surface"].links[0].from_node.type == "MIX_SHADER"
    z = _mat(bpy, "g zinc", "zinc_yellow")
    bsdf = next(n for n in z.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    assert bsdf.inputs["Thin Film Thickness"].default_value == pytest.approx(300.0)
    assert materials_lib.MATERIALS["chrome"]["base_color"] != materials_lib.MATERIALS["stainless_polished"][
        "base_color"]


def test_carbon_and_perlage_build(blender):
    bpy = blender
    from fresing_render.blender import finishes
    for kind in ("TWILL", "PLAIN"):
        for gloss in (1.0, 0.0):
            m = _mat(bpy, f"c {kind} {gloss}", "carbon_fibre", finish=fc.key("carbon_fibre", kind=kind, amount=gloss))
            bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
            assert bsdf.inputs["Coat Roughness"].default_value == pytest.approx(0.03 + (1 - gloss) * 0.32)
            assert not bsdf.inputs["Coat Normal"].is_linked          # the clear coat lies smooth over the weave
            assert bsdf.inputs["Tangent"].is_linked and bsdf.inputs["Normal"].is_linked
            names = {n.attribute_name for n in m.node_tree.nodes if n.type == "ATTRIBUTE"}
            assert {"fr_cw_a", "fr_cw_b", "fr_fx_k"} <= names
    m = _mat(bpy, "p perlage", "perlage", finish=fc.key("perlage", base="BRASS"))
    assert finishes.web_numbers(m)["mode"] == "average"


def test_web_model_bake_keeps_the_rust_colour(blender):
    """The web 3D model bakes a rusty bare steel as a 0.2 m tile (corners flattened): its colour is rust, not grey."""
    bpy = blender
    from fresing_render.blender import web3d
    sc = bpy.data.scenes.new("web rust bake")
    sc.render.engine = "CYCLES"
    m = _mat(bpy, "web rust", "steel_raw", rust=0.8)
    lk = web3d.Look(m)
    baker = web3d.Baker(sc)
    try:
        jobs = [(key, m, sock, web3d.KIND[ch]) for key, (ch, sock) in lk.sockets().items() if ch == "color"]
        assert jobs
        tile = baker.tiles(jobs, 48)[jobs[0][0]]
        rgb = tile[..., :3].reshape(-1, 3).mean(0)
        assert rgb[0] > rgb[1] * 1.3 > 0 and rgb[1] > rgb[2]          # red-brown
    finally:
        baker.close()
