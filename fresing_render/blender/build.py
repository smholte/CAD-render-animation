"""Turn a render cache (tree.json + meshes.npz) into Blender objects.

* every unique part becomes one mesh datablock, shared by all its copies
* every assembly becomes an empty; parts are parented to it
* every object carries a stable ID (``fr_uid``) for re-import and rules: the path of names in the CAD file.
  The same STEP imported twice (task 0056) would give both copies the same IDs, so a copy whose IDs are taken
  gets a scope in front of all of them (``~2/TEST.CRANE#1/COVER#1``), kept on its root (``fr_uid_scope``) and
  through model updates. The first copy, and every project with one copy per model, keep their IDs.
"""

from __future__ import annotations

import json
import os
import re

import bpy
import numpy as np
from mathutils import Matrix

from ..core import ral

PROP_UID = "fr_uid"
PROP_NAME = "fr_name"
PROP_KIND = "fr_kind"          # "assembly" | "part"
PROP_COLOR = "fr_color"        # '#RRGGBB' from CAD or ''
PROP_CAD_MATERIAL = "fr_cad_material"  # material/appearance name from the CAD file or ''
PROP_GROUP = "fr_group"        # material group name
PROP_ROOT = "fr_root"          # set on the model root empty
PROP_SOURCE = "fr_source"      # STEP path on the root
PROP_LOCKED = "fr_locked"      # subassembly locked (moves with parent only)
PROP_EXCLUDED = "fr_excluded"  # hidden for good (clean-up)
PROP_INSTANCE = "fr_instance"  # occurrence name in the CAD file (e.g. "Frame:1"), may be ''
PROP_CAD_BASIS = "fr_cad_basis"    # local matrix from the CAD file (16 floats)
PROP_REST_BASIS = "fr_rest_basis"  # local matrix with no free move applied (changes when a joint carries it)
PROP_CAD_PARENT = "fr_cad_parent"  # CAD parent, set while a joint carries the object
PROP_UID_SCOPE = "fr_uid_scope"    # on a model root: the scope in front of its part IDs ('' = none, task 0056)
_SCOPE_RE = re.compile(r"^(~\d+/)+")  # never "@": joints.PartLookup

MODEL_KINDS = ("assembly", "part")
# a cylinder's empties (task 0013): frame on the barrel pin, barrel (aims), rod (slides), rod pin, telescopic stage
CYLINDER_KINDS = ("cyl_frame", "cyl_barrel", "cyl_rod", "cyl_pin", "cyl_stage")
# a mechanism's empties (task 0014): its frame on the input pin, one per link it moves
LINKAGE_KINDS = ("mech_frame", "mech_link")
# empties the app inserts: not part of the CAD structure
JOINT_KINDS = ("joint_frame", "joint") + CYLINDER_KINDS + LINKAGE_KINDS


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


def scoped(uid: str, scope: str) -> str:
    """A part ID with a model's scope in front (``scope`` '' leaves it as it is)."""
    return f"{scope}{uid}" if scope else uid


def unscoped(uid: str) -> str:
    """A part ID without its model's scope: the path of names in the CAD file."""
    return _SCOPE_RE.sub("", uid or "", count=1)


def uid_scope(root) -> str:
    """The scope in front of the part IDs of the model under ``root`` ('' for the first copy and old projects)."""
    return str(root.get(PROP_UID_SCOPE, "") or "") if root is not None else ""


def used_uids(objs=None, but=None) -> set:
    """Part IDs in use by models in the project (every scene); ``but``: leave out the model under this root."""
    objs = bpy.data.objects if objs is None else objs
    memo: dict = {}
    return {ob.get(PROP_UID) for ob in objs if ob.get(PROP_KIND) in MODEL_KINDS and ob.get(PROP_UID)
            and (but is None or model_root_of(ob, memo) != but)}


def free_scope(uids, used: set) -> str:
    """'' when none of ``uids`` is in ``used``, else the first scope ``~N/`` (N = 2, 3, ...) that makes them all
    free: the same STEP imported a second time gets its own part IDs (task 0056)."""
    uids = list(uids)
    if not used.isdisjoint(uids):
        n = 2
        while True:
            scope = f"~{n}/"
            if not any(scoped(u, scope) in used for u in uids):
                return scope
            n += 1
    return ""


def build(cache_dir: str, collection: bpy.types.Collection | None = None, progress=None,
          scope: str | None = None, taken: set | None = None) -> bpy.types.Object:
    """Create objects for a cache. Returns the root empty of the model.

    Part IDs get a scope in front when they are taken by a model already in the project (task 0056; ``taken``:
    the IDs in use, default every model's). ``scope``: the one to keep when its IDs are free (a model update gives
    the new revision the old one's); ``None`` = a new import: '' unless taken."""
    info, arrays = load_cache(cache_dir)
    nodes = info["nodes"]
    meshes_meta = info["meshes"]
    src_name = os.path.splitext(os.path.basename(info.get("source", "Model")))[0]
    n_roots = sum(1 for n in nodes if n["parent"] < 0)
    ids = [n["uid"] for n in nodes] + ([src_name] if n_roots > 1 else [])
    taken = used_uids() if taken is None else taken
    if scope is None or any(scoped(u, scope) in taken for u in ids):
        scope = free_scope(ids, taken)

    if collection is None:
        collection = bpy.data.collections.new(src_name)
        bpy.context.scene.collection.children.link(collection)

    # ---- meshes (one per unique part) ------------------------------------------
    from . import faces
    mesh_blocks: dict[int, bpy.types.Mesh] = {}
    used = {n["mesh"] for n in nodes if n["kind"] == "part" and n["mesh"] >= 0}
    part_colours: dict[int, dict] = {}          # colours of the copies of each part: faces in it need no set
    for n in nodes:
        if n["kind"] == "part" and n.get("color"):
            c = part_colours.setdefault(n["mesh"], {})
            c[tuple(n["color"])] = c.get(tuple(n["color"]), 0) + 1
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
        if f"f{mid}" in arrays:
            # CAD faces (for picking whole faces) and faces painted in the CAD file
            cols = part_colours.get(mid)
            faces.cad_sets(me, arrays[f"f{mid}"], arrays[f"c{mid}"] if f"c{mid}" in arrays else None,
                           meta.get("palette") or [], meta.get("palette_names") or [],
                           max(cols, key=cols.get) if cols else None)
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
                faces.link_slots(ob)
        else:
            ob = bpy.data.objects.new(n["name"], None)
            ob.empty_display_type = "PLAIN_AXES"
            ob.empty_display_size = 0.02
            ob[PROP_LOCKED] = True
        ob[PROP_UID] = scoped(n["uid"], scope)
        ob[PROP_NAME] = n["name"]
        ob[PROP_KIND] = n["kind"]
        ob[PROP_COLOR] = ral.rgb_to_hex(n["color"]) if n.get("color") else ""
        ob[PROP_CAD_MATERIAL] = n.get("material") or ""
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
        root_obj[PROP_UID] = scoped(src_name, scope)
        root_obj[PROP_NAME] = src_name
    if root_obj is not None:
        root_obj[PROP_ROOT] = True
        root_obj[PROP_UID_SCOPE] = scope
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
    """The part's path of names in the CAD file (rules match on it): the same for every copy of a model."""
    return unscoped(ob.get(PROP_UID, ob.name))


def model_root_of(ob, memo: dict | None = None):
    """The model root above ``ob`` in the CAD structure (``None`` when it has none)."""
    chain = []
    p = ob
    while p is not None:
        if memo is not None and p.name in memo:
            root = memo[p.name]
            break
        chain.append(p)
        if p.get(PROP_ROOT):
            root = p
            break
        p = logical_parent(p)
    else:
        root = None
    if memo is not None:
        for c in chain:
            memo[c.name] = root
    return root


def repair_uids(scene) -> int:
    """Projects made before task 0056 with the same STEP imported twice: the copies share their part IDs. Every
    copy after the first gets its own scope (the first keeps its IDs, so what was saved still points where it
    did). Returns the number of models changed; 0 at once when every ID is unique (the usual case)."""
    objs = [ob for ob in scene.objects if ob.get(PROP_KIND) in MODEL_KINDS]
    uids = [ob.get(PROP_UID, "") for ob in objs]
    if len(set(uids)) == len(uids):
        return 0
    memo: dict = {}
    by_root: dict = {}
    for ob in objs:
        root = model_root_of(ob, memo)
        if root is not None:
            by_root.setdefault(root.name, (root, []))[1].append(ob)
    used: set = set()
    every = set(uids)
    changed = 0
    for root, members in by_root.values():              # scene order: the copy that won lookups so far stays
        ids = [ob.get(PROP_UID, "") for ob in members]
        scope = free_scope(ids, used | every) if not used.isdisjoint(ids) else ""
        if scope:
            for ob in members:
                ob[PROP_UID] = scoped(ob.get(PROP_UID, ""), scope)
            root[PROP_UID_SCOPE] = scope + uid_scope(root)
            changed += 1
        used.update(ob.get(PROP_UID, "") for ob in members)
    if changed:
        _uid_strings_again(scene)
    return changed


def _uid_strings_again(scene) -> None:
    """After ``repair_uids``: the part IDs the CNC machine, its tools and pockets, the air nozzle, the coolant nozzles
    and milling keep as text are taken again from the objects they point at (task 0071, bug hunt 0068 row 15: a CNC
    set up on copy 2 jumped to copy 1 at the next model update)."""
    s = scene.fresing
    pairs = []
    cnc = getattr(s, "cnc", None)
    if cnc is not None:
        pairs += [(cnc, "tool", "tool_uid"), (cnc, "workpiece", "workpiece_uid"), (cnc, "air_nozzle", "air_nozzle_uid")]
        pairs += [(t, "obj", "uid") for t in getattr(cnc, "tools", ())]
        pairs += [(p, "obj", "uid") for p in getattr(cnc, "pockets", ())]
    mill = getattr(s, "milling", None)
    if mill is not None:
        pairs += [(mill, "workpiece", "workpiece_uid"), (mill, "finished", "finished_uid")]
        pairs += [(b, "obj", "uid") for b in getattr(mill, "bits", ())]
    cool = getattr(s, "coolant", None)
    if cool is not None:
        pairs += [(n, "obj", "uid") for n in getattr(cool, "nozzles", ())]
    for owner, ptr, key in pairs:
        ob = getattr(owner, ptr, None)
        if ob is None or not hasattr(owner, key):
            continue
        uid = ob.get(PROP_UID, "")
        if uid and getattr(owner, key) != uid:
            owner["_busy"] = True
            try:
                setattr(owner, key, uid)
            finally:
                del owner["_busy"]


BOUNDS_CAD = "fr_bounds_cad"           # on a part: the model's size counts its CAD shape, not what is drawn (0081)


def world_bounds(objs) -> tuple:
    """(min, max) world-space corners of the given mesh objects (fast, uses bound boxes)."""
    mins = np.array([np.inf] * 3)
    maxs = np.array([-np.inf] * 3)
    for ob in objs:
        if ob.type != "MESH" or ob.data is None:
            continue
        mw = np.array(ob.matrix_world)
        if ob.get(BOUNDS_CAD) and len(ob.data.vertices):
            # drawn somewhere else than its CAD shape and changing per frame (a cable into the sea, a CPS set riding
            # on it, task 0081): the model's size is measured by the CAD shape
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
