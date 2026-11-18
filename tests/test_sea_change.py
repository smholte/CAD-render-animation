"""A sea-state change keeps the sea's water material and node groups and only sets their numbers (task 0202, study 0195
A4: making the ~700 nodes again took ~4 s of a ~6 s change on the demo).

The kept material / groups must be exactly what a fresh build gives: compared node for node (kinds, settings, every
input's value, every link) and as a Cycles picture. A build whose nodes differ (another number of waves drawn, white
caps with a meander from about Beaufort 7) makes them new, as before.
"""

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from test_sea_cutaway import _apply, _camera, _env, _render, addon, scene  # noqa: E402,F401
from fresing_render.blender import surroundings  # noqa: E402

SKIP = {"name", "label", "select", "show_options", "show_preview", "hide", "mute", "show_texture",
        "use_custom_color", "location", "width", "height"}


def _value(v):
    if isinstance(v, bpy.types.ID):
        return v.name
    try:
        return tuple(float(np.float32(x)) for x in v)
    except TypeError:
        return float(np.float32(v)) if isinstance(v, float) else v


def _structure(nt):
    """The tree as plain data, without node names or places: kinds, settings, unlinked input values, links."""
    nodes = []
    for n in nt.nodes:
        props = tuple((p.identifier, getattr(n, p.identifier)) for p in n.bl_rna.properties
                      if p.type in ("ENUM", "BOOLEAN", "STRING", "INT") and not p.is_readonly
                      and p.identifier not in SKIP)
        ins = tuple((sk.identifier, _value(sk.default_value)) for sk in n.inputs
                    if hasattr(sk, "default_value") and not sk.is_linked)
        links = tuple(sorted((lk.to_socket.identifier, lk.from_node.bl_idname, lk.from_socket.identifier)
                             for lk in nt.links if lk.to_node == n))
        nodes.append(repr((n.bl_idname, props, ins, links)))
    return sorted(nodes)


def _sea_trees():
    sea = _env("sea")[0]
    trees = {"water": sea.data.materials[0].node_tree}
    if sea.modifiers.get("Waves"):
        trees["waves"] = sea.modifiers["Waves"].node_group
    foam = _env("hull_foam")
    if foam:
        trees["hull foam"] = foam[0].modifiers["On the water"].node_group
    return trees


def _fresh(scene):
    """Build the sea again from nothing: no water material, no waves / hull foam group of before."""
    for mat in [m for m in bpy.data.materials if m.get("fr_env") == "water"]:
        bpy.data.materials.remove(mat)
    for ng in [g for g in bpy.data.node_groups if g.get("fr_env") in ("waves", "hull_foam")]:
        bpy.data.node_groups.remove(ng)
    surroundings.root_object()["fr_key"] = ""                 # (made again at the next apply)
    _apply(scene)


@pytest.mark.parametrize("detailed", [False, True])
def test_a_new_sea_state_keeps_the_nodes_and_equals_a_fresh_build(scene, detailed):
    s = scene.fresing
    s.env_detail = "DETAILED" if detailed else "SIMPLE"
    s.sea_foam = True
    s.sea_moving = True
    s.sea_cutaway = True
    s.sea_state = "CALM"
    _apply(scene)
    calm_mat = _env("sea")[0].data.materials[0]
    n_mats = len(bpy.data.materials)
    for state in ("ROUGH", "CALM", "ROUGH"):
        s.sea_state = state
        _apply(scene)
        mat = _env("sea")[0].data.materials[0]
        assert state.lower() in mat.name
        assert len(bpy.data.materials) <= n_mats + 1          # kept, not one more material per change
    mat = _env("sea")[0].data.materials[0]
    assert mat == calm_mat and mat.get("fr_replayed")         # the same material, its nodes kept
    kept = {k: _structure(t) for k, t in _sea_trees().items()}
    _fresh(scene)
    made = {k: _structure(t) for k, t in _sea_trees().items()}
    assert set(kept) == set(made)
    for k in kept:
        assert kept[k] == made[k], k


def test_other_kinds_of_nodes_are_made_new(scene):
    """A Wind sea from Beaufort 3 to 9: the white caps get a meander, so the material's nodes differ – made new."""
    s = scene.fresing
    s.sea_state = "WIND"
    s.weather.enabled = True
    s.weather.wind = 3.0
    _apply(scene)
    first = _env("sea")[0].data.materials[0]
    s.weather.wind = 9.0
    _apply(scene)
    second = _env("sea")[0].data.materials[0]
    assert second != first and not second.get("fr_replayed")
    kept = _structure(second.node_tree)
    _fresh(scene)
    assert _structure(_env("sea")[0].data.materials[0].node_tree) == kept


def test_kept_nodes_render_like_a_fresh_build(scene, tmp_path):
    """Calm -> Rough with the kept material and groups, and Rough made from nothing: the same picture, to the last
    digit (Cycles, fixed seed): across the waves with white caps, and down into the cut-away box."""
    s = scene.fresing
    s.env_detail = "DETAILED"
    s.sea_foam = True
    s.sea_moving = True
    s.sea_cutaway = True
    s.sea_state = "CALM"
    _apply(scene)
    s.sea_state = "ROUGH"
    _apply(scene)
    assert _env("sea")[0].data.materials[0].get("fr_replayed")
    scene.frame_set(12)
    water = surroundings.waterline(scene)
    shots = (((-60.0, -40.0, water + 12.0), (20.0, 0.0, water)), ((-30.0, 0.0, water + 50.0), (-30.0, 0.01, water)))

    def pictures(tag):
        out = []
        for n, (eye, at) in enumerate(shots):
            _camera(scene, eye, at, lens=35.0)
            out.append(_render(scene, tmp_path / f"{tag}{n}.exr", size=(80, 48), samples=4))
        return out
    kept = pictures("kept")
    _fresh(scene)
    scene.frame_set(12)
    made = pictures("made")
    for n, (a, b) in enumerate(zip(kept, made)):
        assert np.array_equal(a, b), n


def _mesh_data(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    lp = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lp)
    st = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", st)
    sm = np.empty(len(me.polygons), bool)
    me.polygons.foreach_get("use_smooth", sm)
    return co, lp, st, sm


def test_meshes_made_from_arrays_are_the_same(scene):
    """Task 0202 builds the big meshes (sea, hull foam, seabed patch) from NumPy blocks of faces: the same mesh, point
    for point and corner for corner, as from the faces one by one."""
    rng = np.random.default_rng(3)
    pts = rng.random((40, 3))
    quads = np.stack([np.arange(9), np.arange(9) + 1, np.arange(9) + 11, np.arange(9) + 10], axis=1)
    a, b = surroundings._Mesh(), surroundings._Mesh()
    a._add(pts[:4], [(0, 1, 2)], 0)
    a._add(pts, [tuple(int(i) for i in q) for q in quads], 1, smooth=True)
    a._add(pts[:5], [(0, 1, 2, 3, 4)], 0)
    b._add(pts[:4], [(0, 1, 2)], 0)
    b._add(pts, quads, 1, smooth=True)
    b._add(pts[:5], [(0, 1, 2, 3, 4)], 0)
    for x, y in zip(_mesh_data(a.to_mesh("a")), _mesh_data(b.to_mesh("b"))):
        assert np.array_equal(x, y)
    # the sea's own mesh: its fan and rings as before (count of faces, the centre fan first)
    me = surroundings._sea_mesh("sea test", True, 300.0)
    n, rings = surroundings._sea_rings(True, 300.0)
    assert len(me.polygons) == n + n * (len(rings) - 1) and len(me.vertices) == 1 + n * len(rings)
    assert all(len(me.polygons[i].vertices) == 3 for i in range(n)) and len(me.polygons[n].vertices) == 4
