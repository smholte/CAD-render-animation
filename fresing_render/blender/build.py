"""Turn a render cache (tree.json + meshes.npz) into Blender objects.

* every unique part becomes one mesh datablock, shared by all its copies
* every assembly becomes an empty; parts are parented to it
* every object carries a stable ID (``fr_uid``) for re-import and rules
"""

from __future__ import annotations

import json
import os

import bpy
import numpy as np
from mathutils import Matrix

from ..core import ral

PROP_UID = "fr_uid"
PROP_NAME = "fr_name"
PROP_KIND = "fr_kind"          # "assembly" | "part"
PROP_COLOR = "fr_color"        # '#RRGGBB' from CAD or ''
PROP_GROUP = "fr_group"        # material group name
PROP_ROOT = "fr_root"          # set on the model root empty
PROP_SOURCE = "fr_source"      # STEP path on the root
PROP_LOCKED = "fr_locked"      # subassembly locked (moves with parent only)
PROP_EXCLUDED = "fr_excluded"  # hidden for good (clean-up)
PROP_INSTANCE = "fr_instance"  # occurrence name in the CAD file (e.g. "Frame:1"), may be ''
PROP_CAD_BASIS = "fr_cad_basis"    # local matrix from the CAD file (16 floats)
PROP_REST_BASIS = "fr_rest_basis"  # local matrix with no free move applied (changes when a joint carries it)
PROP_CAD_PARENT = "fr_cad_parent"  # CAD parent, set while a joint carries the object

MODEL_KINDS = ("assembly", "part")
JOINT_KINDS = ("joint_frame", "joint")


def mat_to_list(m) -> list[float]:
    return [float(m[r][c]) for r in range(4) for c in range(4)]


def list_to_mat(values) -> Matrix:
    v = list(values)
    return Matrix([v[0:4], v[4:8], v[8:12], v[12:16]])


def get_mat(ob, key: str, default=None) -> Matrix | None:
    v = ob.get(key)
    if v is None or len(v) != 16:
        return default
    return list_to_mat(v)


def set_mat(ob, key: str, m) -> None:
    ob[key] = mat_to_list(m)


def cad_basis(ob) -> Matrix:
    m = get_mat(ob, PROP_CAD_BASIS)
    return m if m is not None else ob.matrix_basis.copy()


def rest_basis(ob) -> Matrix:
    m = get_mat(ob, PROP_REST_BASIS)
    return m if m is not None else cad_basis(ob)


def ensure_bases(scene) -> int:
    """Projects made before version 0.2 have no stored CAD matrices: store the current ones.

    Only for objects that are still in their CAD parent (no joint was ever added)."""
    n = 0
    for ob in scene.objects:
        if ob.get(PROP_KIND) in MODEL_KINDS and PROP_CAD_BASIS not in ob and PROP_CAD_PARENT not in ob:
            set_mat(ob, PROP_CAD_BASIS, ob.matrix_basis)
            set_mat(ob, PROP_REST_BASIS, ob.matrix_basis)
            n += 1
    return n


def logical_parent(ob):
    """Parent in the CAD structure (skips the empties a joint inserts)."""
    p = ob.get(PROP_CAD_PARENT)
    if isinstance(p, bpy.types.Object):
        return p
    p = ob.parent
    while p is not None and p.get(PROP_KIND) in JOINT_KINDS:
        p = p.parent
    return p


def _new_mesh(name: str, pos: np.ndarray, nrm: np.ndarray, tri: np.ndarray) -> bpy.types.Mesh:
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
        try:
            attr = me.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")
            attr.data.foreach_set("vector", nrm.reshape(-1))
        except Exception:
            # older Blender: classic custom split normals
            me.normals_split_custom_set_from_vertices([tuple(v) for v in nrm])
    me.materials.append(None)
    return me


def _matrix(rows) -> Matrix:
    return Matrix(rows) if rows else Matrix.Identity(4)


def load_cache(cache_dir: str):
    with open(os.path.join(cache_dir, "tree.json"), encoding="utf-8") as fh:
        info = json.load(fh)
    arrays = np.load(os.path.join(cache_dir, "meshes.npz"))
    return info, arrays


def build(cache_dir: str, collection: bpy.types.Collection | None = None, progress=None) -> bpy.types.Object:
    """Create objects for a cache. Returns the root empty of the model."""
    info, arrays = load_cache(cache_dir)
    nodes = info["nodes"]
    meshes_meta = info["meshes"]
    src_name = os.path.splitext(os.path.basename(info.get("source", "Model")))[0]

    if collection is None:
        collection = bpy.data.collections.new(src_name)
        bpy.context.scene.collection.children.link(collection)

    # ---- meshes (one per unique part) ------------------------------------------
    mesh_blocks: dict[int, bpy.types.Mesh] = {}
    used = {n["mesh"] for n in nodes if n["kind"] == "part" and n["mesh"] >= 0}
    total = max(1, len(used))
    for k, mid in enumerate(sorted(used)):
        key = f"p{mid}"
        if key not in arrays:
            continue
        me = _new_mesh(meshes_meta[mid]["name"] or f"Part {mid}", arrays[key], arrays[f"n{mid}"], arrays[f"t{mid}"])
        meta = meshes_meta[mid]
        if meta.get("axes"):
            # round faces of the part, for picking joint axes with a click
            me["fr_axes"] = [v for ax in meta["axes"] for v in ax]
            me["fr_axis_faces"] = meta.get("axis_faces", [])
        mesh_blocks[mid] = me
        if progress and k % 25 == 0:
            progress(k / total * 0.7, f"Creating part {k + 1} of {total}")

    # ---- objects ----------------------------------------------------------------
    objects: list[bpy.types.Object] = []
    root_obj = None
    for i, n in enumerate(nodes):
        if n["kind"] == "part":
            data = mesh_blocks.get(n["mesh"])
            ob = bpy.data.objects.new(n["name"], data)
            if data is not None:
                ob.material_slots[0].link = "OBJECT"
        else:
            ob = bpy.data.objects.new(n["name"], None)
            ob.empty_display_type = "PLAIN_AXES"
            ob.empty_display_size = 0.02
            ob[PROP_LOCKED] = True
        ob[PROP_UID] = n["uid"]
        ob[PROP_NAME] = n["name"]
        ob[PROP_KIND] = n["kind"]
        ob[PROP_COLOR] = ral.rgb_to_hex(n["color"]) if n.get("color") else ""
        ob[PROP_INSTANCE] = n.get("instance", "") or ""
        if n["parent"] >= 0:
            ob.parent = objects[n["parent"]]
        ob.matrix_basis = _matrix(n.get("matrix"))
        set_mat(ob, PROP_CAD_BASIS, ob.matrix_basis)
        set_mat(ob, PROP_REST_BASIS, ob.matrix_basis)
        collection.objects.link(ob)
        objects.append(ob)
        if root_obj is None and n["parent"] < 0:
            root_obj = ob
        if progress and i % 200 == 0:
            progress(0.7 + 0.3 * i / max(1, len(nodes)), "Placing parts")

    roots = [ob for ob, n in zip(objects, nodes) if n["parent"] < 0]
    if len(roots) > 1:
        # several top-level shapes: put them under one model empty
        root_obj = bpy.data.objects.new(src_name, None)
        root_obj.empty_display_size = 0.05
        collection.objects.link(root_obj)
        for ob in roots:
            ob.parent = root_obj
        set_mat(root_obj, PROP_CAD_BASIS, root_obj.matrix_basis)
        set_mat(root_obj, PROP_REST_BASIS, root_obj.matrix_basis)
        root_obj[PROP_INSTANCE] = ""
        root_obj[PROP_KIND] = "assembly"
        root_obj[PROP_UID] = src_name
        root_obj[PROP_NAME] = src_name
    if root_obj is not None:
        root_obj[PROP_ROOT] = True
        root_obj[PROP_SOURCE] = info.get("source", "")
        root_obj["fr_cache"] = cache_dir
        root_obj["fr_stats"] = json.dumps(info.get("stats", {}))
        root_obj[PROP_LOCKED] = True
    return root_obj


def model_roots(scene=None) -> list[bpy.types.Object]:
    scene = scene or bpy.context.scene
    return [ob for ob in scene.objects if ob.get(PROP_ROOT)]


def iter_parts(scene=None):
    scene = scene or bpy.context.scene
    for ob in scene.objects:
        if ob.get(PROP_KIND) == "part" and ob.type == "MESH":
            yield ob


def parent_assembly(ob) -> bpy.types.Object | None:
    p = logical_parent(ob)
    while p is not None and p.get(PROP_KIND) != "assembly":
        p = logical_parent(p)
    return p


def path_of(ob) -> str:
    return ob.get(PROP_UID, ob.name)


def world_bounds(objs) -> tuple:
    """(min, max) world-space corners of the given mesh objects (fast, uses bound boxes)."""
    mins = np.array([np.inf] * 3)
    maxs = np.array([-np.inf] * 3)
    for ob in objs:
        if ob.type != "MESH" or ob.data is None:
            continue
        mw = np.array(ob.matrix_world)
        bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        w = (mw @ bb.T).T[:, :3]
        mins = np.minimum(mins, w.min(axis=0))
        maxs = np.maximum(maxs, w.max(axis=0))
    if not np.isfinite(mins).all():
        return np.zeros(3), np.ones(3)
    return mins, maxs
