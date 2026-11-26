"""Task 0366: the faster model build gives exactly the model of the build before it.

The build before 0366 is kept here as the reference: ``_old_new_mesh`` (points and corners through
``vertices.foreach_set("co")`` / ``loops.foreach_set("vertex_index")``), ``_old_world_bounds`` (every part's 8 corners
turned one by one) and a group's look given to its parts at each change (no ``props.held_looks``). Each model is built
both ways from the same cache, and everything the build writes is compared: points, corners, loop starts, edges,
custom normals, UV layers, every attribute, the meshes' own properties (CAD faces, axes, keys), each part's group,
materials and face materials, the groups and the bounds. Models: the PC check's Heavy machine (scaled down, made at
test time), the test tour's crane, painted faces, and a mesh model with UVs.
"""
import contextlib
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, logic, ops_import, props  # noqa: E402
from fresing_render.importer import mesh_reader, step_reader  # noqa: E402

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


# ---- the build before task 0366 ---------------------------------------------------------------------------------

def _old_new_mesh(name, pos, nrm, tri):
    me = bpy.data.meshes.new(name)
    n_v = len(pos)
    n_t = len(tri)
    me.vertices.add(n_v)
    me.vertices.foreach_set("co", pos.reshape(-1))
    me.loops.add(n_t * 3)
    me.loops.foreach_set("vertex_index", tri.reshape(-1))
    me.polygons.add(n_t)
    me.polygons.foreach_set("loop_start", np.arange(0, n_t * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    if nrm is not None and len(nrm) == n_v:
        attr = me.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")
        attr.data.foreach_set("vector", nrm.reshape(-1))
    me.materials.append(None)
    return me


def _old_world_bounds(objs):
    objs = build.without_scenery(objs)
    mins = np.array([np.inf] * 3)
    maxs = np.array([-np.inf] * 3)
    for ob in objs:
        if ob.type != "MESH" or ob.data is None:
            continue
        mw = np.array(ob.matrix_world)
        if ob.get(build.BOUNDS_CAD) and len(ob.data.vertices):
            co = np.empty(len(ob.data.vertices) * 3)
            ob.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            lo, hi = co.min(axis=0), co.max(axis=0)
            bb = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        else:
            bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        w = (mw @ bb.T).T[:, :3]
        mins = np.minimum(mins, w.min(axis=0))
        maxs = np.maximum(maxs, w.max(axis=0))
    if not np.isfinite(mins).all():
        return np.zeros(3), np.ones(3)
    return mins, maxs


@contextlib.contextmanager
def _old_build(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(build, "_new_mesh", _old_new_mesh)
        m.setattr(build, "world_bounds", _old_world_bounds)
        m.setattr(props, "held_looks", contextlib.nullcontext)       # a walk over the parts at every change
        yield


# ---- what a build writes ---------------------------------------------------------------------------------------

def _attr_array(a, n):
    kind = {"FLOAT": ("value", 1, np.float32), "INT": ("value", 1, np.int32), "BOOLEAN": ("value", 1, bool),
            "FLOAT_VECTOR": ("vector", 3, np.float32), "FLOAT2": ("vector", 2, np.float32),
            "FLOAT_COLOR": ("color", 4, np.float32), "BYTE_COLOR": ("color", 4, np.float32),
            "INT32_2D": ("value", 2, np.int32), "INT8": ("value", 1, np.int32),
            "QUATERNION": ("value", 4, np.float32), "FLOAT4X4": ("value", 16, np.float32)}.get(a.data_type)
    if kind is None:
        return a.data_type
    prop, width, dt = kind
    out = np.empty(n * width, dtype=dt)
    a.data.foreach_get(prop, out)
    return out


def _idprops(idb) -> dict:
    out = {}
    for k in idb.keys():
        v = idb[k]
        out[k] = v.to_list() if hasattr(v, "to_list") else (v.to_dict() if hasattr(v, "to_dict") else v)
    return out


def _mesh_state(me) -> dict:
    n = {"POINT": len(me.vertices), "EDGE": len(me.edges), "FACE": len(me.polygons), "CORNER": len(me.loops)}
    ls = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("loop_start", ls)
    mi = np.empty(len(me.polygons), dtype=np.int32)
    me.polygons.foreach_get("material_index", mi)
    attrs = {}
    for a in me.attributes:
        if a.domain in n:
            attrs[(a.name, a.domain, a.data_type)] = _attr_array(a, n[a.domain])
    uvs = {}
    for layer in me.uv_layers:
        uv = np.empty(len(me.loops) * 2, dtype=np.float32)
        layer.data.foreach_get("uv", uv)
        uvs[layer.name] = uv
    return {"counts": n, "loop_start": ls, "material_index": mi, "attrs": attrs, "uvs": uvs,
            "props": _idprops(me), "materials": [m.name if m else None for m in me.materials],
            "has_custom_normals": me.has_custom_normals}


def _state(scene) -> dict:
    parts = {}
    meshes = {}
    for ob in sorted(build.iter_parts(scene), key=lambda o: o[build.PROP_UID]):
        parts[ob[build.PROP_UID]] = {
            "group": ob.get(build.PROP_GROUP), "mesh": ob.data.name,
            "slots": [(s.link, s.material.name if s.material else None) for s in ob.material_slots],
            "props": {k: v for k, v in _idprops(ob).items() if k != build.PROP_IMPORTED},
            "matrix": np.array(ob.matrix_world)}
        if ob.data.name not in meshes:
            meshes[ob.data.name] = _mesh_state(ob.data)
    s = scene.fresing
    groups = [(g.name, g.material, g.color, g.count, g.faces, g.by_rules) for g in s.groups]
    return {"parts": parts, "meshes": meshes, "groups": groups,
            "bounds": (np.array(s.bounds_min), np.array(s.bounds_max), s.bounds_valid),
            "materials": sorted(m.name for m in bpy.data.materials)}


def _same(a, b, where=""):
    if isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), f"{where}: keys {sorted(set(a) ^ set(b))[:5]}"
        for k in a:
            _same(a[k], b[k], f"{where}/{k}")
    elif isinstance(a, (list, tuple)):
        assert len(a) == len(b), f"{where}: {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{where}[{i}]")
    elif isinstance(a, np.ndarray):
        assert np.array_equal(a, b), f"{where}: arrays differ"
    else:
        assert a == b, f"{where}: {a!r} != {b!r}"


def _built(cache, tmp_path, monkeypatch, old: bool) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    bpy.context.scene.fresing.out_folder = str(tmp_path / "renders")
    with (_old_build(monkeypatch) if old else contextlib.nullcontext()):
        ops_import.finish_import(bpy.context, cache)
    return _state(bpy.context.scene)


def _compare(cache, tmp_path, monkeypatch):
    old = _built(cache, tmp_path, monkeypatch, old=True)
    new = _built(cache, tmp_path, monkeypatch, old=False)
    lo_old, hi_old, valid_old = old.pop("bounds")
    lo_new, hi_new, valid_new = new.pop("bounds")
    assert valid_old and valid_new
    size = float(np.max(hi_old - lo_old))                # same box (float32 matrices: rounding only)
    assert np.allclose(lo_old, lo_new, rtol=0, atol=1e-6 * max(1.0, size))
    assert np.allclose(hi_old, hi_new, rtol=0, atol=1e-6 * max(1.0, size))
    _same(old, new)
    return new


# ---- the models -------------------------------------------------------------------------------------------------

def test_the_tour_crane_is_built_the_same(tmp_path, monkeypatch):
    cache = str(tmp_path / "crane")
    step_reader.read_step(os.path.join(DATA, "test_crane_a.step"), cache, "draft", workers=0)
    st = _compare(cache, tmp_path, monkeypatch)
    assert len(st["parts"]) > 10 and len(st["groups"]) > 2


def test_painted_faces_are_built_the_same(tmp_path, monkeypatch):
    cache = str(tmp_path / "faces")
    step_reader.read_step(os.path.join(DATA, "test_faces_a.step"), cache, "draft", workers=0)
    st = _compare(cache, tmp_path, monkeypatch)
    assert any(any(k[0] == "custom_normal" for k in m["attrs"]) for m in st["meshes"].values())
    assert any(len(m["materials"]) > 1 or "fr_face_sets" in m["props"] for m in st["meshes"].values())


def test_a_mesh_model_with_uvs_is_built_the_same(tmp_path, monkeypatch):
    cache = str(tmp_path / "obj")
    mesh_reader.read_mesh(os.path.join(DATA, "test_mesh_parts.obj"), cache)
    st = _compare(cache, tmp_path, monkeypatch)
    assert any(m["uvs"] for m in st["meshes"].values())


def test_the_heavy_machine_is_built_the_same(tmp_path, monkeypatch):
    pytest.importorskip("OCP")
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(fresing_render.__file__), "pccheck"))
    import heavy_scene
    step = str(tmp_path / "heavy.step")
    heavy_scene.build(step, 60, 300)
    cache = str(tmp_path / "heavy")
    info = step_reader.read_step(step, cache, "normal", workers=2)
    st = _compare(cache, tmp_path, monkeypatch)
    assert len(st["parts"]) >= 250 and len(st["groups"]) >= 3
    stats = info["stats"]                               # the reader's stage seconds (task 0366)
    for k in ("seconds_parse", "seconds_transfer", "seconds_tree", "seconds_part_total", "seconds_biggest_part",
              "seconds_write"):
        assert k in stats and stats[k] >= 0, k
    assert stats["seconds_parse"] + stats["seconds_transfer"] == pytest.approx(stats["seconds_read"], abs=0.11)
    assert 0 < stats["seconds_biggest_part"] <= stats["seconds_part_total"]


def test_new_mesh_handles_an_empty_part():
    me = build._new_mesh("empty", np.zeros((0, 3), np.float32), np.zeros((0, 3), np.float32),
                         np.zeros((0, 3), np.int32))
    assert len(me.vertices) == 0 and len(me.polygons) == 0
    bpy.data.meshes.remove(me)


def test_world_bounds_matches_the_corners_with_turned_scaled_and_modified_parts():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from mathutils import Euler, Matrix
    me = build._new_mesh("box", np.array([[x, y, z] for x in (0, 1) for y in (0, 2) for z in (0, 3)], np.float32),
                         None, np.array([[0, 1, 2], [5, 6, 7], [1, 3, 7]], np.int32))
    obs = []
    rng = np.random.default_rng(3)
    for i in range(12):
        ob = bpy.data.objects.new(f"b{i}", me)
        bpy.context.scene.collection.objects.link(ob)
        ob.matrix_world = Matrix.LocRotScale(rng.normal(size=3) * 5, Euler(rng.normal(size=3)),
                                             np.abs(rng.normal(size=3)) + 0.2)
        obs.append(ob)
    obs[3].modifiers.new("d", "DISPLACE").strength = 4.0       # its own (evaluated) box, not the shared mesh's
    obs[5][build.BOUNDS_CAD] = True
    bpy.context.view_layer.update()
    lo, hi = build.world_bounds(obs)
    lo0, hi0 = _old_world_bounds(obs)
    assert np.allclose(lo, lo0, atol=1e-5) and np.allclose(hi, hi0, atol=1e-5)
    lo, hi = build.world_bounds([])
    assert list(lo) == [0, 0, 0] and list(hi) == [1, 1, 1]


def test_held_looks_gives_each_part_its_group_material_in_one_walk(tmp_path, monkeypatch):
    cache = str(tmp_path / "crane")
    step_reader.read_step(os.path.join(DATA, "test_crane_a.step"), cache, "draft", workers=0)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    ops_import.finish_import(bpy.context, cache)
    scene = bpy.context.scene
    walks = []
    real = props._looks_to_parts
    monkeypatch.setattr(props, "_looks_to_parts", lambda sc, mats: (walks.append(sorted(mats)), real(sc, mats)))
    groups = [g for g in scene.fresing.groups if g.count]
    with props.held_looks():
        with props.held_looks():                             # nested: only the outer one walks
            for g in groups:
                g.color = "#123456"
                g.wear = 0.3
        assert walks == []
    assert walks == [sorted(g.name for g in groups)]
    from fresing_render.blender import materials
    for ob in build.iter_parts(scene):
        g = scene.fresing.groups.get(ob.get(build.PROP_GROUP))
        if g is not None and g.count:
            assert ob.material_slots[0].material == materials.group_material(g)
    walks.clear()
    groups[0].color = "#654321"                              # outside: at once, as before
    assert walks == [[groups[0].name]]
    logic.apply_rules(scene)
