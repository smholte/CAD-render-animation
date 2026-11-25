"""Task 0324: a model update keeps unchanged parts' meshes – and gives the same result as reading every part again.

The oracle: every revision pair of the test-model makers is updated twice from the same project with the same work on
it (painted faces, a hidden part, a decal, a joint, the maker's own set-up: hoses, cables, welds …) – once the full way
(``FRESING_UPDATE_FULL=1``: every part read, meshed and built again, as before this task) and once the fast way (the
old cache's meshes and the old Blender meshes of unchanged parts) – and both projects must be the same: per object
its mesh (counts, bounds, a hash of its points, triangles and normals), the tree, names, looks and groups, painted
faces, decals, joints, poses, animation steps, hoses, cables, welds, hidden states, and the clash check's rows. Each
import gets a cache folder of its own, so the fast way really reads the new revision with the old cache beside it.
"""
import hashlib
import json
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, decals, faces, joints, logic, ops_import  # noqa: E402
from fresing_render.importer import runner  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "data")


def _p(name):
    return os.path.join(DATA, name)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    ops_import.use_cache_root(None)
    os.environ.pop(runner.FULL_ENV, None)
    fresing_render.unregister()


def _named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def _set_up_flex(sc):
    from fresing_render.blender import flex
    flex.set_up_test_hoses(sc)


def _set_up_avoid(sc):
    from fresing_render.blender import flex
    flex.set_up_test_avoid(sc)


def _set_up_paths(sc):
    from fresing_render.blender import paths
    paths.set_up_test_model(sc)


def _set_up_welds(sc):
    from fresing_render.blender import welds
    welds.set_up_test_model(sc)


# (revision A, revision B, the maker's own set-up or None); every one also gets the generic work below
CASES = {
    "crane": ("test_crane_a.step", "test_crane_b.step", None),
    "cylinder": ("test_cylinder_a.step", "test_cylinder_b.step", None),
    "linkage": ("test_linkage_a.step", "test_linkage_b.step", None),
    "flex_hoses": ("test_flex_hoses_a.step", "test_flex_hoses_b.step", _set_up_flex),
    "flex_avoid": ("test_flex_avoid_a.step", "test_flex_avoid_b.step", _set_up_avoid),
    "paths": ("test_paths_a.step", "test_paths_b.step", _set_up_paths),
    "faces": ("test_faces_a.step", "test_faces_b.step", None),
    "decals": ("test_decals_a.step", "test_decals_b.step", None),
    "weldment": ("test_weldment.step", "test_weldment_b.step", _set_up_welds),
    "mesh": ("test_mesh_crane.glb", "test_mesh_crane_b.glb", None),
}


def _import(path, root=None):
    if runner.is_mesh(path):
        kw = {"update_root": root.name} if root is not None else {}
        return bpy.ops.fresing.import_mesh(filepath=path, **kw)
    kw = {"update_root": root.name} if root is not None else {}
    return bpy.ops.fresing.import_step(filepath=path, quality="draft", **kw)


def _parts(sc):
    return sorted((o for o in build.iter_parts(sc)), key=lambda o: o.get(build.PROP_UID, ""))


def _generic_work(sc):
    """Painted faces on the first part with two CAD faces or more, a hidden part, a text decal, a joint."""
    parts = _parts(sc)
    painted = next((o for o in parts if len(faces.face_starts(o.data)) > 2), None)
    if painted is not None:
        faces.paint(painted, [0], "Paint test")
    rest = [o for o in parts if o is not painted]
    if rest:
        logic.set_hidden(rest[0], True)
    if len(rest) > 1:
        part = rest[1]
        starts = faces.face_starts(part.data)
        tri = np.empty(len(part.data.loops), np.int32)
        part.data.loops.foreach_get("vertex_index", tri)
        co = np.empty(len(part.data.vertices) * 3, np.float32)
        part.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        t = tri.reshape(-1, 3)[int(starts[0])]
        a, b, c = (Vector(co[i]) for i in t)
        n = (b - a).cross(c - a)
        if n.length > 0:
            decals.add(part, 0, (a + b + c) / 3.0, n.normalized(), "TEXT", text="ORACLE")
    if not len(sc.fresing.joints) and len(rest) > 2:
        ob = rest[2]
        joints.create(sc, "ROTATE", [ob], ob.matrix_world.translation.copy(), Vector((0.0, 0.0, 1.0)), name="Oracle")
        j = joints.find(sc, "Oracle")
        joints.set_value(j, 0.2)
    bpy.context.view_layer.update()


def _arr_hash(*arrays) -> str:
    h = hashlib.blake2b(digest_size=12)
    for a in arrays:
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()


def _mesh_sig(me) -> dict:
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    vi = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", vi)
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    nrm = np.zeros(0, np.float32)
    attr = me.attributes.get("custom_normal")
    if attr is not None:
        nrm = np.empty(len(attr.data) * 3, np.float32)
        attr.data.foreach_get("vector", nrm)
    co3 = co.reshape(-1, 3)
    props = {k: me[k] for k in me.keys() if k not in (build.MESH_KEY, build.MESH_OF)}
    props = json.loads(json.dumps(props, default=lambda v: list(v) if hasattr(v, "__len__") else str(v)))
    return {
        "counts": (len(me.vertices), len(me.polygons), len(me.edges)),
        "bounds": (np.round(co3.min(0), 6).tolist(), np.round(co3.max(0), 6).tolist()) if len(co3) else None,
        "geometry": _arr_hash(co, vi, nrm),
        "material_index": _arr_hash(mi),
        "slots": len(me.materials),
        "props": props,
        "decals": sorted((d.name, d.kind, d.face, d.lost, d.text) for d in me.fresing_decals),
        "uv": [uv.name for uv in me.uv_layers],
    }


def _round(m) -> list:
    return [round(float(v), 5) for row in m for v in row]


def snapshot(sc) -> dict:
    """Everything the two ways must agree on, keyed by part ID (object and mesh names may differ: '.001')."""
    s = sc.fresing
    objs = {}
    root = build.model_roots(sc)[0]
    for o in [root] + list(logic.Tree(sc).descendants(root)):
        if o.get(build.PROP_KIND) not in build.MODEL_KINDS:
            continue
        p = build.logical_parent(o)
        d = {
            "name": o.get(build.PROP_NAME), "kind": o.get(build.PROP_KIND), "type": o.type,
            "parent": p.get(build.PROP_UID) if p is not None else None,
            "world": _round(o.matrix_world),
            "colour": o.get(build.PROP_COLOR), "cad_material": o.get(build.PROP_CAD_MATERIAL),
            "instance": o.get(build.PROP_INSTANCE), "group": o.get(build.PROP_GROUP),
            "group_manual": o.get("fr_group_manual"), "hidden": logic.is_hidden(o),
            "excluded": bool(o.get(build.PROP_EXCLUDED)), "hide_render": o.hide_render,
            "face_copy": o.get(faces.PROP_COPY), "face_groups": o.get(faces.PROP_GROUPS),
            "materials": [sl.material.name if sl.material else None for sl in o.material_slots],
            "modifiers": [(m.name, m.type) for m in o.modifiers],
            "decals": sorted((d.name, d.kind, d.face, d.lost) for d in o.fresing_decals),
        }
        if o.type == "MESH" and o.data is not None:
            d["mesh"] = _mesh_sig(o.data)
        objs[o.get(build.PROP_UID)] = d
    shared = {}                                     # which parts share one mesh (copies of a part)
    for o in build.iter_parts(sc):
        shared.setdefault(o.data.as_pointer(), []).append(o.get(build.PROP_UID))
    out = {
        "objects": objs,
        "sharing": sorted(sorted(v) for v in shared.values()),
        "joints": sorted((j.name, j.kind, round(joints.get_value(j), 5),
                          sorted(m.get(build.PROP_UID, "") for m in joints.members(j)) if hasattr(joints, "members")
                          else None) for j in s.joints),
        "states": sorted(st.name for st in getattr(s, "states", [])),
        "animations": [(a.name, len(a.blocks)) for a in s.animations],
        "report": (s.report_title, sorted(x.text for x in s.report_new), sorted(x.text for x in s.report_missing),
                   sorted(x.text for x in s.report_notes)),
        "decal objects": sorted((o.parent.get(build.PROP_UID, "") if o.parent else "", len(o.data.polygons))
                                for o in sc.objects if decals.is_decal(o)),
    }
    for attr in ("flex_items", "cables", "welds"):
        coll = getattr(s, attr, None)
        if coll is not None:
            rows = []
            for it in coll:
                row = {}
                for k in ("name", "lost", "note", "faces_a", "faces_b"):
                    if hasattr(it, k):
                        row[k] = getattr(it, k)
                for k in ("part", "part_a", "part_b", "obj"):
                    v = getattr(it, k, None)
                    if isinstance(v, bpy.types.Object):
                        row[k] = v.get(build.PROP_UID, v.name)
                rows.append(row)
            out[attr] = rows
    if s.animations:
        from fresing_render.blender import animation, clash
        animation.bake(sc, s.animations[0])
        out["clash"] = sorted((r.a, r.b, round(r.depth * 1000.0, 1)) for r in clash.check(sc, store=False).rows)
    return out


def _run(tmp_path, case, full: bool, paths=None) -> dict:
    a, b, set_up = paths or CASES[case]
    a, b = (x if os.path.isabs(x) else _p(x) for x in (a, b))
    if full:
        os.environ[runner.FULL_ENV] = "1"
    else:
        os.environ.pop(runner.FULL_ENV, None)
    ops_import.use_cache_root(str(tmp_path / ("cache_full" if full else "cache_fast")))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert _import(a) == {"FINISHED"}
    if set_up is not None:
        set_up(sc)
    _generic_work(sc)
    root = build.model_roots(sc)[0]
    build.LAST_TIMES.clear()
    snap_meshes = {o.get(build.PROP_NAME): o.data.as_pointer() for o in build.iter_parts(sc)}
    assert _import(b, root) == {"FINISHED"}, sc.fresing.last_message
    bpy.context.view_layer.update()
    reused = dict(build.LAST_TIMES)
    snap = snapshot(sc)
    root = build.model_roots(sc)[0]
    with open(os.path.join(root["fr_cache"], "tree.json"), encoding="utf-8") as fh:
        snap["_reader"] = json.load(fh)["stats"].get("parts_reused", 0)
    snap["_reused"] = reused.get("reused", 0)
    snap["_kept_mesh"] = sorted(o.get(build.PROP_NAME) for o in build.iter_parts(sc)
                                if snap_meshes.get(o.get(build.PROP_NAME)) == o.data.as_pointer())
    os.environ.pop(runner.FULL_ENV, None)
    return snap


def _diff(a, b, path="") -> list:
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: only in {'full' if k in a else 'fast'}")
            else:
                out += _diff(a[k], b[k], f"{path}/{k}")
        return out
    return [] if a == b else [f"{path}: full {a!r} != fast {b!r}"]


@pytest.mark.parametrize("case", list(CASES))
def test_fast_update_is_the_full_update(case, tmp_path):
    full = _run(tmp_path, case, True)
    fast = _run(tmp_path, case, False)
    assert full.pop("_reader") == 0 and full.pop("_reused") == 0, "the full way took something from the old revision"
    reader, reused = fast.pop("_reader"), fast.pop("_reused")
    assert not full.pop("_kept_mesh")
    fast.pop("_kept_mesh")
    diffs = _diff(full, fast)
    assert not diffs, f"{case}: {len(diffs)} differences: " + "\n".join(diffs[:15])
    if case != "mesh":                               # a mesh file has no mesh keys: nothing is taken (as before)
        assert reader > 0 and reused > 0, (case, reader, reused)
    else:
        assert reader == 0 and reused == 0


# ---------------------------------------------------------------------------
# a changed part is never kept (task 0324 step 6): small models written at test time
# ---------------------------------------------------------------------------

def _write_model(path, block_h=20.0, swap=False, bracket=(0.5, 0.5, 0.5)):
    """BLOCK (100 x 50 x block_h mm), PIN, PLATE A and PLATE B (the same shape), BRACKET (its colour)."""
    from fresing_render.demo_model import geom as G
    root = G.Asm("TEST.REUSE")
    root.add(G.Part("BLOCK", G.box(0, 0, 0, 100, 50, block_h), (0.8, 0.2, 0.2)), instance="BLOCK:1")
    root.add(G.Part("PIN", G.cyl(10, 40), (0.3, 0.3, 0.3)), G.T(200, 0, 0), instance="PIN:1")
    pa, pb = G.T(0, 200, 0), G.T(0, 300, 40)
    if swap:
        pa, pb = pb, pa
    root.add(G.Part("PLATE A", G.box(0, 0, 0, 60, 60, 5), (0.2, 0.6, 0.2)), pa, instance="PLATE A:1")
    root.add(G.Part("PLATE B", G.box(0, 0, 0, 60, 60, 5), (0.2, 0.6, 0.2)), pb, instance="PLATE B:1")
    root.add(G.Part("BRACKET", G.box(0, 0, 0, 30, 30, 30), bracket), G.T(300, 300, 0), instance="BRACKET:1")
    G.write_step(root, str(path))
    return str(path)


@pytest.fixture(scope="module")
def small_models(tmp_path_factory):
    d = tmp_path_factory.mktemp("reuse_models")
    return {
        "base": _write_model(d / "reuse_base.step"),
        "face": _write_model(d / "reuse_face.step", block_h=20.1),          # one face 0.1 mm higher
        "swap": _write_model(d / "reuse_swap.step", swap=True),             # two identical parts change places
        "colour": _write_model(d / "reuse_colour.step", bracket=(0.1, 0.2, 0.9)),   # only a colour
    }


def _read(path, out, reuse=None):
    from fresing_render.importer import step_reader
    return step_reader.read_step(path, str(out), "draft", workers=0, reuse_dir=str(reuse) if reuse else None)


def test_reader_meshes_a_part_whose_face_moved(small_models, tmp_path):
    base = _read(small_models["base"], tmp_path / "a")
    new = _read(small_models["face"], tmp_path / "b", tmp_path / "a")
    full = _read(small_models["face"], tmp_path / "c")
    by_name = {m["name"]: m for m in new["meshes"]}
    old_keys = {m["key"] for m in base["meshes"]}
    assert by_name["BLOCK"]["key"] not in old_keys
    assert abs(by_name["BLOCK"]["bbox"][1][2] - 0.0201) < 1e-6
    assert new["stats"]["parts_reused"] == len(new["meshes"]) - 1
    assert [m["key"] for m in new["meshes"]] == [m["key"] for m in full["meshes"]]
    a, c = np.load(tmp_path / "b" / "meshes.npz"), np.load(tmp_path / "c" / "meshes.npz")
    assert sorted(a.files) == sorted(c.files)
    for k in a.files:
        assert np.array_equal(a[k], c[k]), k


def test_reader_old_cache_without_keys_reads_everything(small_models, tmp_path):
    _read(small_models["base"], tmp_path / "a")
    tree = tmp_path / "a" / "tree.json"
    head = json.loads(tree.read_text(encoding="utf-8"))
    for m in head["meshes"]:
        m.pop("key", None)                         # a cache written before task 0324
    tree.write_text(json.dumps(head), encoding="utf-8")
    assert _read(small_models["face"], tmp_path / "b", tmp_path / "a")["stats"]["parts_reused"] == 0
    head["version"] = 7
    tree.write_text(json.dumps(head), encoding="utf-8")
    assert runner.reuse_dir_for(str(tmp_path / "a"), "draft") is None      # another cache version: not offered


def test_reader_quality_change_meshes_everything(small_models, tmp_path):
    from fresing_render.importer import step_reader
    _read(small_models["base"], tmp_path / "a")
    out = step_reader.read_step(small_models["base"], str(tmp_path / "b"), "normal", workers=0,
                                reuse_dir=str(tmp_path / "a"))
    assert out["stats"]["parts_reused"] == 0
    assert runner.reuse_dir_for(str(tmp_path / "a"), "normal") is None
    assert runner.reuse_dir_for(str(tmp_path / "a"), "draft") == str(tmp_path / "a")
    os.environ[runner.FULL_ENV] = "1"
    try:
        assert runner.reuse_dir_for(str(tmp_path / "a"), "draft") is None
    finally:
        os.environ.pop(runner.FULL_ENV, None)


@pytest.mark.parametrize("change", ["face", "swap", "colour"])
def test_changed_part_is_never_kept(change, small_models, tmp_path):
    pair = (small_models["base"], small_models[change], None)
    full = _run(tmp_path, change, True, pair)
    fast = _run(tmp_path, change, False, pair)
    full.pop("_reader"), full.pop("_reused"), full.pop("_kept_mesh")
    kept = fast.pop("_kept_mesh")
    reader, reused = fast.pop("_reader"), fast.pop("_reused")
    diffs = _diff(full, fast)
    assert not diffs, "\n".join(diffs[:15])
    objs = {d["name"]: d for d in fast["objects"].values()}
    if change == "face":
        assert "BLOCK" not in kept and {"PIN", "PLATE A", "PLATE B", "BRACKET"} <= set(kept)
        assert abs(objs["BLOCK"]["mesh"]["bounds"][1][2] - 0.0201) < 1e-6
        assert reader == 4 and reused == 4
    elif change == "swap":
        assert {"BLOCK", "PIN", "PLATE A", "PLATE B", "BRACKET"} <= set(kept)
        assert abs(objs["PLATE A"]["world"][11] - 0.04) < 1e-6 and abs(objs["PLATE B"]["world"][11]) < 1e-6
    else:
        assert "BRACKET" in kept and reused == 5
        assert objs["BRACKET"]["colour"] == "#1A33E6" or objs["BRACKET"]["colour"].upper() != "#808080"


def test_old_project_first_update_reads_everything_then_reuses(small_models, tmp_path):
    """A project imported before task 0324 (meshes without keys, a cache of version 7): its first update reads and
    builds every part; the update after that keeps the unchanged ones."""
    os.environ.pop(runner.FULL_ENV, None)
    ops_import.use_cache_root(str(tmp_path / "cache"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert _import(small_models["base"]) == {"FINISHED"}
    root = build.model_roots(sc)[0]
    for me in {o.data for o in build.iter_parts(sc)}:          # as an old project has them
        for k in (build.MESH_KEY, build.MESH_OF):
            if k in me:
                del me[k]
    tree = os.path.join(root["fr_cache"], "tree.json")
    with open(tree, encoding="utf-8") as fh:
        head = json.load(fh)
    head["version"] = 7
    with open(tree, "w", encoding="utf-8") as fh:
        json.dump(head, fh)
    assert _import(small_models["face"], root) == {"FINISHED"}, sc.fresing.last_message
    root = build.model_roots(sc)[0]
    with open(os.path.join(root["fr_cache"], "tree.json"), encoding="utf-8") as fh:
        assert json.load(fh)["stats"]["parts_reused"] == 0
    assert build.LAST_TIMES["reused"] == 0
    assert sc.fresing.report_title.startswith("Model updated: 5 parts kept")
    assert _import(small_models["colour"], root) == {"FINISHED"}, sc.fresing.last_message
    root = build.model_roots(sc)[0]
    with open(os.path.join(root["fr_cache"], "tree.json"), encoding="utf-8") as fh:
        assert json.load(fh)["stats"]["parts_reused"] == 4          # BLOCK changed back to 20 mm
    assert build.LAST_TIMES["reused"] == 4
