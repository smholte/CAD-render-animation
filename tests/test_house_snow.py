"""Snow layers for a House Planner bake (task 0114, ``fresing_render/core/house_snow.py``; FORMAT.md 8.6 of
house-scene-format v1.0). No Blender: the sample house's winter season, small made-up glb files, and the pinned
format checker (``tests/data/house/hsf-v1.0``) reading the layers' ``snow/winter.glb``."""

import json
import os
import re
import sys
import time
import zipfile

import numpy as np
import pytest

from fresing_render.core import house_snow as hs

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
PIN = os.path.join(HERE, "data", "house", "hsf-v1.0")
SAMPLE = os.path.join(PIN, "samples", "sample-house.hpscene")

sys.dont_write_bytecode = True        # the pinned copy stays exactly the tag (test_house_pinned.py)
if PIN not in sys.path:
    sys.path.insert(0, PIN)


def _checker():
    from hsf import check as C
    from hsf.glb import Glb, GlbWriter
    from hsf.package import Package
    return C, Glb, GlbWriter, Package


@pytest.fixture(scope="module")
def sample():
    with zipfile.ZipFile(SAMPLE) as z:
        doc = json.loads(z.read("scene.json"))
        glb = z.read("house.glb")
    winter = next(s for s in doc["recipe"]["seasons"] if s["id"] == "winter")
    sources, blockers = hs.sources_from_glb(glb, winter["foliage"])
    layers = hs.build_layers(sources, winter["snow_cover"], blockers)
    return {"doc": doc, "glb": glb, "winter": winter, "sources": {s["id"]: s for s in sources},
            "blockers": blockers, "layers": {lay.id: lay for lay in layers}}


def _box(points):
    p = np.asarray(points)
    return p.min(0), p.max(0)


# ---------------------------------------------------------------------------
# 0109's rule
# ---------------------------------------------------------------------------

def test_rule_is_0109s():
    """min_up is the middle of 0109's ramp and SKY_DISTANCE its value: read from weather_look.py's text (it needs
    Blender), so a change there shows here."""
    text = open(os.path.join(ROOT, "fresing_render", "blender", "weather_look.py"), encoding="utf-8").read()
    assert float(re.search(r"^SKY_DISTANCE = ([\d.]+)", text, re.M).group(1)) == hs.SKY_DISTANCE
    assert re.search(r'"MULTIPLY_ADD", cover, -0\.45, 0\.85', text)          # lo = 0.85 - 0.45 cover
    assert re.search(r'"ADD", lo, 0\.12', text)                               # hi = lo + 0.12
    for cover in (0.0, 0.3, 0.6, 1.0):
        lo = 0.85 - 0.45 * cover
        assert hs.min_up(cover) == pytest.approx(lo + 0.06)
    assert hs.THICKNESS_PER_COVER == 0.10 and hs.PIECE == 0.5


# ---------------------------------------------------------------------------
# the sample house in winter
# ---------------------------------------------------------------------------

def test_sample_snow_lies_on_roof_and_plot_only(sample):
    ids = set(sample["layers"])
    assert {"snow:roof:st_first:0", "snow:ground:plot", "snow:garden:ga_terrace"} == ids
    for lay in sample["layers"].values():
        src = sample["sources"][lay.on]
        assert lay.id == "snow:" + lay.on
        assert (lay.storey, lay.group) == (src["storey"], src["group"])
    # nothing that lies under the roof: floors, ceilings, the stair, the table, the window, the lamp
    for sid in sample["sources"]:
        if sid.split(":")[0] in ("floor", "ceiling", "stair", "furniture", "opening", "slab-edge", "wall"):
            assert "snow:" + sid not in ids, sid


def test_sample_no_snow_above_anything_under_the_roof(sample):
    """By geometry: over every surface under the roof (floors, the stair, the table …) the only snow is the roof's,
    on top of the roof."""
    roof_lo, roof_hi = _box(sample["sources"]["roof:st_first:0"]["points"])
    under = [sid for sid, s in sample["sources"].items()
             if sid.split(":")[0] in ("floor", "ceiling", "stair", "furniture", "slab-edge")]
    assert len(under) >= 10
    for sid in under:
        lo, hi = _box(sample["sources"][sid]["points"])
        assert lo[0] >= roof_lo[0] - 1e-6 and hi[0] <= roof_hi[0] + 1e-6 and hi[1] < roof_hi[1], sid
        for lay in sample["layers"].values():
            p = lay.positions
            over = ((p[:, 0] > lo[0] + 1e-3) & (p[:, 0] < hi[0] - 1e-3)
                    & (p[:, 2] > lo[2] + 1e-3) & (p[:, 2] < hi[2] - 1e-3))
            if lay.on == "roof:st_first:0":
                assert (p[over, 1] >= roof_hi[1] - 1e-4).all()
            else:
                assert not over.any(), f"{lay.id} has snow over {sid}"


def test_sample_plot_layer_has_a_hole_where_the_house_stands(sample):
    plot = sample["layers"]["snow:ground:plot"]
    roof_lo, roof_hi = _box(sample["sources"]["roof:st_first:0"]["points"])
    p = plot.positions
    inside = ((p[:, 0] > roof_lo[0] + 1e-3) & (p[:, 0] < roof_hi[0] - 1e-3)
              & (p[:, 2] > roof_lo[2] + 1e-3) & (p[:, 2] < roof_hi[2] - 1e-3))
    assert not inside.any()
    # … and covers the whole plot round it (nothing above the plot outside the house)
    src = sample["sources"]["ground:plot"]
    assert _top_area(plot) == pytest.approx(_area(src["points"], src["tris"]), rel=1e-4)
    # the plot is four quads round the house whose long edges meet short ones (T-junctions): the layer is still one
    # welded piece – its outline is the plot's outer edge and the hole, nothing inside
    top = plot.indices.reshape(-1, 3)[:plot.top]
    e = np.sort(np.stack([top, np.roll(top, -1, axis=1)], 2).reshape(-1, 2), axis=1)
    keys, cnt = np.unique(e, axis=0, return_counts=True)
    ring = keys[cnt == 1]
    q = plot.positions.astype(np.float64)
    assert np.linalg.norm(q[ring[:, 0]] - q[ring[:, 1]], axis=1).sum() == pytest.approx(2 * (15 + 23) + 2 * (7 + 12))


def _area(points, tris):
    p = np.asarray(points, np.float64)[np.asarray(tris)]
    return 0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum()


def _top_area(lay):
    return _area(lay.positions.astype(np.float64), lay.indices.reshape(-1, 3)[:lay.top])


def _check_layer(lay, cover):
    """The rules every layer keeps: triangles, every vertex used, top faces up enough, short edges, unit normals."""
    n = len(lay.positions)
    assert lay.positions.dtype == np.float32 and lay.normals.dtype == np.float32
    assert lay.indices.dtype == np.uint32 and len(lay.indices) % 3 == 0
    assert lay.indices.max() < n and len(np.unique(lay.indices)) == n         # every vertex used
    assert np.allclose(np.linalg.norm(lay.normals, axis=1), 1.0, atol=1e-5)
    tri = lay.indices.reshape(-1, 3)
    p = lay.positions.astype(np.float64)
    top = tri[:lay.top]
    c = np.cross(p[top[:, 1]] - p[top[:, 0]], p[top[:, 2]] - p[top[:, 0]])
    up = c[:, 1] / np.linalg.norm(c, axis=1)
    assert (up >= hs.min_up(cover) - 1e-4).all(), up.min()
    edges = np.linalg.norm(p[top] - p[np.roll(top, -1, axis=1)], axis=2)
    assert edges.max() <= hs.PIECE * 1.02 + 1e-4, edges.max()
    assert lay.top > 0 and len(tri) > lay.top                                  # a top and a skirt
    # every triangle (top and skirt) turns the way its stored normals point: outwards
    g = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
    stored = lay.normals[tri].astype(np.float64).sum(1)
    assert (np.einsum("ij,ij->i", g, stored) > 0).all()
    # each skirt face stands on the outline only (no skirt inside the snow, also with T-junctions in the source)
    # and points away from the snow: 1 cm behind it (1 m down) the top is overhead; in front of it, past the top's
    # overhang on a slope (at most the thickness), not – also round a hole
    sn = g[lay.top:] * [1, 0, 1]
    sn /= np.linalg.norm(sn, axis=1)[:, None]
    sc = p[tri[lay.top:]].mean(1) - [0, 1.0, 0]
    top = p[tri[:lay.top]]
    assert not hs.open_sky(sc - 0.01 * sn, top, distance=5.0).any()
    assert hs.open_sky(sc + (0.01 + 0.1 * cover) * sn, top, distance=5.0).all()
    return p, tri


def test_sample_layer_geometry(sample):
    cover = sample["winter"]["snow_cover"]
    thick = 0.1 * cover
    for lay in sample["layers"].values():
        p, tri = _check_layer(lay, cover)
        src = sample["sources"][lay.on]
        sp = np.asarray(src["points"])[np.asarray(src["tris"])]
        sn = np.cross(sp[:, 1] - sp[:, 0], sp[:, 2] - sp[:, 0])
        flat_y = sp[sn[:, 1] > 0.99 * np.linalg.norm(sn, axis=1), 0, 1]
        assert np.ptp(flat_y) < 1e-6, "the sample's snow surfaces are flat"   # one source plane per layer
        top_pts = np.unique(tri[:lay.top])
        # the top lies `thick` above the source plane …
        assert np.allclose(p[top_pts, 1] - flat_y[0], thick, atol=2e-5), lay.id
        # … and the skirt reaches down to it
        assert p[:, 1].min() == pytest.approx(flat_y[0], abs=2e-5)


def test_sample_layers_glb_passes_the_pinned_checker(sample):
    C, Glb, _, Package = _checker()
    layers = list(sample["layers"].values())
    data = hs.layers_glb(layers)
    glb = Glb.parse(data)
    doc = glb.json
    assert "extensionsUsed" not in doc and "extensionsRequired" not in doc
    for mesh in doc["meshes"]:
        attrs = mesh["primitives"][0]["attributes"]
        for name in ("POSITION", "NORMAL"):
            assert doc["accessors"][attrs[name]]["componentType"] == 5126
        assert "min" in doc["accessors"][attrs["POSITION"]]
        assert doc["accessors"][mesh["primitives"][0]["indices"]]["componentType"] == 5125
    rep = C.Report("snow")
    found = C.read_surfaces(glb, rep, "snow/winter.glb", False, snow=True)
    assert rep.items == [], rep.text()
    assert set(found.by_id) == {lay.id for lay in layers}
    for lay in layers:
        hp = found.by_id[lay.id]["hp"]
        assert hp["kind"] == "snow" and hp["bake"] == "VERTEX" and hp["on"] == lay.on
        assert hp["hash"] == lay.hash                                            # the checker recomputed it
        assert found.by_id[lay.id]["verts"] == len(lay.positions)
    # against the scene: every `on` exists, storey and group are those of `on`
    pkg = Package.open(SAMPLE)
    srep = C.Report("scene")
    scene = C.check_scene(pkg, srep)
    assert srep.ok, srep.text()
    for info in found.by_id.values():
        info["season"] = "winter"
    bake = {"scene": {"id": scene["doc"]["id"], "scene_hash": scene["doc"]["scene_hash"]},
            "light": scene["doc"]["recipe"]["light"], "moments": [], "pages": [], "surfaces": {}, "photos": [],
            "videos": [], "snow": [{"season": "winter", "file": "snow/winter.glb"}]}
    rep = C.Report("against")
    C._against_scene(bake, scene, found.by_id, rep)
    assert rep.errors == [], rep.text()
    assert not [w for w in rep.warnings if "snow" in w], rep.text()


def test_sample_summer_and_cover_zero_give_no_layers(sample):
    summer = next(s for s in sample["doc"]["recipe"]["seasons"] if s["id"] == "summer")
    sources, blockers = hs.sources_from_glb(sample["glb"], summer["foliage"])
    assert hs.build_layers(sources, summer["snow_cover"], blockers) == []
    assert hs.build_layers(sources, 0.0, blockers) == []
    assert hs.build_layers(sources, -0.2, blockers) == []


def test_sources_skip_glass_lamps_and_no_bake(sample):
    ids = set(sample["sources"])
    assert "glass:o_g_win1" not in ids and "lamp:p_living_1" not in ids
    assert "roof:st_first:0" in ids and "furniture:f_table:0" in ids
    # the table is placed by a matrix: its points are in the world
    lo, hi = _box(sample["sources"]["furniture:f_table:0"]["points"])
    assert 2.5 < lo[0] < 3.5 < hi[0] < 4.5 and hi[1] == pytest.approx(0.76, abs=1e-5)
    # every mesh node blocks, glass (2 triangles) and the lamp (10) included
    assert len(sample["blockers"][1]) == sum(len(s["tris"]) for s in sample["sources"].values()) + 2 + 10


# ---------------------------------------------------------------------------
# open sky
# ---------------------------------------------------------------------------

def _quad(x0, x1, z0, z1, y):
    """A horizontal square facing up (counter-clockwise seen from +Y), as (points, tris)."""
    p = np.array([[x0, y, z0], [x0, y, z1], [x1, y, z1], [x1, y, z0]], float)
    return p, np.array([[0, 1, 2], [0, 2, 3]])


def test_open_sky_under_a_roof_beside_it_and_far_below():
    roof = _quad(0, 4, 0, 4, 2.0)
    high = _quad(10, 14, 0, 4, 30.0)
    pts = np.array([[2, 0, 2],        # under the 2 m roof: blocked
                    [6, 0, 2],        # beside it: open
                    [12, 0, 2],       # under something 30 m up: beyond 25 m, open
                    [12, 5.5, 2],     # 24.5 m below it: blocked
                    [2, 2.0, 2],      # on the roof itself: its own face does not block it
                    [2, 2.5, 2]])     # above the roof: open
    corners = np.concatenate([roof[0][roof[1]], high[0][high[1]]])
    assert hs.open_sky(pts, corners).tolist() == [False, True, True, False, True, True]
    # the (points, tris) form gives the same; an upright wall never blocks a ray straight up
    wall = (np.array([[5, 0, 0], [5, 3, 0], [5, 3, 4]], float), np.array([[0, 1, 2]]))
    assert hs.open_sky(pts[:2], wall).tolist() == [True, True]
    assert hs.open_sky(pts, (np.zeros((0, 3)), np.zeros((0, 3), int))).all()
    assert hs.open_sky(pts, corners, distance=40.0).tolist()[2] is False


def test_open_sky_is_fast_and_right():
    """100 k blocker triangles x 10 k points (the size of a big house with its neighbourhood) in well under a few
    seconds; 200 points compared with a plain loop."""
    rng = np.random.default_rng(7)
    corners = rng.uniform([0, 0, 0], [100, 20, 100], (100_000, 1, 3)) + rng.normal(0, 0.3, (100_000, 3, 3))
    corners = np.concatenate([corners, np.array([[[-10, 3, -10], [-10, 3, 110], [110, 3, 110]]])])  # a big one
    pts = rng.uniform([0, -1, 0], [100, 10, 100], (10_000, 3))
    t = time.perf_counter()
    got = hs.open_sky(pts, corners)
    seconds = time.perf_counter() - t
    print(f"open_sky: 100,001 triangles x 10,000 points in {seconds:.3f} s")
    assert seconds < 5.0
    assert 0.05 < got.mean() < 0.95
    x, y, z = corners[:, :, 0], corners[:, :, 1], corners[:, :, 2]
    det = (x[:, 1] - x[:, 0]) * (z[:, 2] - z[:, 0]) - (x[:, 2] - x[:, 0]) * (z[:, 1] - z[:, 0])
    for i in range(200):
        px, py, pz = pts[i]
        l1 = ((px - x[:, 0]) * (z[:, 2] - z[:, 0]) - (x[:, 2] - x[:, 0]) * (pz - z[:, 0])) / det
        l2 = ((x[:, 1] - x[:, 0]) * (pz - z[:, 0]) - (px - x[:, 0]) * (z[:, 1] - z[:, 0])) / det
        l0 = 1 - l1 - l2
        ty = l0 * y[:, 0] + l1 * y[:, 1] + l2 * y[:, 2]
        hit = (l0 >= 0) & (l1 >= 0) & (l2 >= 0) & (ty > py + hs.LIFT) & (ty <= py + hs.SKY_DISTANCE)
        assert got[i] == (not hit.any()), i


# ---------------------------------------------------------------------------
# made-up surfaces
# ---------------------------------------------------------------------------

def test_cut_is_closed_and_short():
    p, t = _quad(0, 3, 0, 7.3, 0.0)
    P, T = hs.cut(p, t, 0.5)
    e = np.sort(np.stack([T, np.roll(T, -1, axis=1)], 2).reshape(-1, 2), axis=1)
    keys, cnt = np.unique(e, axis=0, return_counts=True)
    assert set(cnt.tolist()) <= {1, 2}                    # no T-junctions: every inner edge has both its triangles
    edges = np.linalg.norm(P[T] - P[np.roll(T, -1, axis=1)], axis=2)
    assert edges.max() <= 0.5
    assert _area(P, T) == pytest.approx(3 * 7.3)
    # the outline is still the square's: its edges (used once) add up to the perimeter
    ring = keys[cnt == 1]
    assert np.linalg.norm(P[ring[:, 0]] - P[ring[:, 1]], axis=1).sum() == pytest.approx(2 * (3 + 7.3))


def test_ground_round_a_house_and_a_pitched_roof():
    """A 20 m ground under a house box with a pitched roof (30°, ridge along z): the ground's snow has a hole under
    the house; the roof holds snow on both sides, welded at the ridge, at least the thickness above each side; a
    60° roof holds snow only at cover 1."""
    ground = _quad(-10, 10, -10, 10, 0.0)
    s30 = np.tan(np.radians(30)) * 3.0
    roof_p = np.array([[-3, 3, -4], [-3, 3, 4], [0, 3 + s30, 4], [0, 3 + s30, -4],
                       [3, 3, -4], [0, 3 + s30, -4], [0, 3 + s30, 4], [3, 3, 4]], float)
    roof_t = np.array([[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]])
    steep_p, steep_t = roof_p.copy(), roof_t
    steep_p[[2, 3, 5, 6], 1] = 3 + np.tan(np.radians(60)) * 3.0
    blockers = (np.concatenate([ground[0], roof_p]), np.concatenate([ground[1], roof_t + 4]))
    sources = [{"id": "ground:g", "storey": None, "group": "garden", "points": ground[0], "tris": ground[1]},
               {"id": "roof:r", "storey": "st", "group": "house", "points": roof_p, "tris": roof_t},
               {"id": "roof:steep", "storey": "st", "group": "house", "points": steep_p + [20, 0, 0],
                "tris": steep_t}]
    cover = 0.6
    layers = {lay.id: lay for lay in hs.build_layers(sources, cover, blockers)}
    assert set(layers) == {"snow:ground:g", "snow:roof:r"}           # 60° is too steep at 0.6
    g = layers["snow:ground:g"]
    _check_layer(g, cover)
    p = g.positions
    assert not ((np.abs(p[:, 0]) < 3 - hs.PIECE) & (np.abs(p[:, 2]) < 4 - hs.PIECE)).any()   # the hole
    assert 400 - 48 - 28 * hs.PIECE < _top_area(g) < 400 - 48 + 28 * hs.PIECE          # less the 6 x 8 m house
    r = layers["snow:roof:r"]
    rp, rt = _check_layer(r, cover)
    top = rt[:r.top]
    side = np.sign(rp[top].mean(1)[:, 0])
    assert (side < 0).any() and (side > 0).any()                      # both sides
    shared = np.intersect1d(np.unique(top[side < 0]), np.unique(top[side > 0]))
    assert len(shared) >= 8                                            # welded along the ridge
    thick = 0.1 * cover
    n_l = np.array([-np.sin(np.radians(30)), np.cos(np.radians(30)), 0])   # the two sides' normals
    n_r = np.array([np.sin(np.radians(30)), np.cos(np.radians(30)), 0])
    for idx, n, o in ((np.unique(top[side < 0]), n_l, roof_p[0]), (np.unique(top[side > 0]), n_r, roof_p[4])):
        d = (rp[idx] - o) @ n
        assert (d >= thick - 1e-5).all()
        inner = np.setdiff1d(idx, shared)
        assert np.allclose((rp[inner] - o) @ n, thick, atol=1e-5)
        assert d.max() <= 3 * thick
    assert "snow:roof:steep" in {lay.id for lay in hs.build_layers(sources, 1.0, blockers)}


def _glb(nodes_spec):
    """A small house.glb: nodes_spec = [(hp or None, (points, tris) or None, node extras like translation /
    children)]; the scene's roots are the nodes no other node names as a child."""
    _, _, GlbWriter, _ = _checker()
    w = GlbWriter("test")
    meshes, nodes, children = [], [], set()
    for hp, mesh, extra in nodes_spec:
        node = dict(extra)
        children.update(node.get("children", []))
        if mesh is not None:
            p, t = mesh
            prim = {"attributes": {"POSITION": w.accessor([tuple(map(float, v)) for v in p], "VEC3", minmax=True),
                                   "NORMAL": w.accessor([(0.0, 1.0, 0.0)] * len(p), "VEC3")},
                    "indices": w.accessor([int(i) for i in np.ravel(t)], "SCALAR", 5125, target=34963)}
            meshes.append({"primitives": [prim]})
            node["mesh"] = len(meshes) - 1
        if hp is not None:
            node["name"] = hp["id"]
            node["extras"] = {"hp": hp}
        nodes.append(node)
    w.doc.update(scene=0, scenes=[{"nodes": [i for i in range(len(nodes)) if i not in children]}], nodes=nodes,
                 meshes=meshes)
    return w.to_bytes()


def test_foliage_bare_or_full_and_placed_nodes():
    """A tree's leaves (kind foliage) 5 m over the ground, placed by a parent node: with foliage "full" they keep
    the snow off the ground under them and hold snow themselves; "bare" hides them. A mirrored node's up-facing
    plane keeps facing up. Glass never holds snow."""
    def hp(sid, kind, bake="MAP", group="garden"):
        return {"id": sid, "kind": kind, "storey": None, "group": group, "bake": bake}
    ground = _quad(-5, 5, -5, 5, 0.0)
    leaves = _quad(-1, 1, -1, 1, 0.0)
    mirrored = _quad(0, 2, 0, 2, 0.0)
    data = _glb([
        (hp("ground:plot", "ground"), ground, {}),
        (None, None, {"translation": [0.0, 5.0, 0.0], "children": [2]}),          # the tree, a group node
        (hp("foliage:tree", "foliage", "VERTEX"), leaves, {"rotation": [0.0, 0.3826834, 0.0, 0.9238795]}),
        (hp("garden:mirror", "garden"), mirrored, {"translation": [20.0, 0.0, 0.0], "scale": [-1.0, 1.0, 1.0]}),
        (hp("glass:pane", "glass", "NO", "house"), _quad(30, 31, 0, 1, 1.0), {}),
    ])
    full_src, full_bl = hs.sources_from_glb(data, "full")
    bare_src, bare_bl = hs.sources_from_glb(data, "bare")
    assert {s["id"] for s in full_src} == {"ground:plot", "foliage:tree", "garden:mirror"}
    assert {s["id"] for s in bare_src} == {"ground:plot", "garden:mirror"}
    assert len(full_bl[1]) == len(bare_bl[1]) + 2
    tree = next(s for s in full_src if s["id"] == "foliage:tree")
    assert np.allclose(tree["points"][:, 1], 5.0)
    assert np.abs(tree["points"][:, [0, 2]]).max() == pytest.approx(np.sqrt(2), abs=1e-5)   # turned 45°
    mirror = next(s for s in full_src if s["id"] == "garden:mirror")
    assert mirror["points"][:, 0].min() == pytest.approx(18.0)
    full = {lay.id: lay for lay in hs.build_layers(full_src, 0.5, full_bl)}
    bare = {lay.id: lay for lay in hs.build_layers(bare_src, 0.5, bare_bl)}
    assert set(full) == {"snow:ground:plot", "snow:foliage:tree", "snow:garden:mirror"}
    assert set(bare) == {"snow:ground:plot", "snow:garden:mirror"}
    for lay in list(full.values()) + list(bare.values()):
        _check_layer(lay, 0.5)

    def under_tree(lay):
        p = lay.positions
        return ((np.abs(p[:, 0]) < 0.5) & (np.abs(p[:, 2]) < 0.5) & (p[:, 1] < 1)).sum()
    assert under_tree(full["snow:ground:plot"]) == 0
    assert under_tree(bare["snow:ground:plot"]) > 0
    assert _top_area(bare["snow:ground:plot"]) == pytest.approx(100.0)
    assert 100 - 2 - 4 < _top_area(full["snow:ground:plot"]) < 100 - 2 + 0.1
    # the layers go into one file the checker reads without a word
    C, Glb, _, _ = _checker()
    rep = C.Report("snow")
    found = C.read_surfaces(Glb.parse(hs.layers_glb(list(full.values()))), rep, "snow/x.glb", False, snow=True)
    assert rep.items == [], rep.text()
    assert {k: v["hp"]["hash"] for k, v in found.by_id.items()} == {k: v.hash for k, v in full.items()}


def test_empty_season_file_is_a_valid_glb():
    C, Glb, _, _ = _checker()
    glb = Glb.parse(hs.layers_glb([]))
    rep = C.Report("snow")
    assert not C.read_surfaces(glb, rep, "snow/x.glb", False, snow=True).by_id
    assert rep.items == []
