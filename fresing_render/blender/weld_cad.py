"""Welds from the CAD file (task 0323): the beads ``core/weld_cad.py`` finds in an imported model become welds.

At an import (``after_import``, called by ``ops_import.finish_import``) and with *Find welds in the CAD file* (3 Looks >
Welds), every part named like welds (``core.weld_cad.weld_name``) and every thin part that may be a bead
(``maybe_bead``) is looked at; what is a bead becomes an ``FRWeld`` with ``from_cad`` on:

* its parts (``part_a`` = the bigger one: the bead moves with it), seams (``seam_data`` + ``seams``, in part A's own
  coordinates – 0319's code builds the heat zone and, with *Use the app's bead instead*, the bead from them), size
  (a / cap width), intermittent pieces and pitch, metal (the CAD material's, else AUTO = from the parts) and finish
  (0319's rule: painted when a part is painted);
* ``cad_mesh``: the CAD bead's own shape (a mesh datablock in part A's coordinates with the UV map ``fr_weld``: u
  along the seam, v across) – ``rebuild`` uses it for the bead while ``cad_shape`` is on;
* the source part (the welds body) is left out for good (``build.PROP_EXCLUDED`` + ``SOURCE``): its beads are the welds
  now. *Back to the CAD part* (``put_back``) removes the CAD welds of a model and shows the part again.

A model update (``carry_over``, from ``reimport``): the new model's beads are found; a bead in the same place as a weld
(same two parts, its line along the old one) gives that weld its new shape and size and keeps the user's settings; a
weld whose bead is gone is listed ("Weld lost in the new model"), a new bead becomes a new weld and is said.
"""

from __future__ import annotations

import json
import time

import bpy
import numpy as np

from ..core import weld_cad as cad
from ..core import welds as core
from ..core.words import plural
from . import build, welds

SOURCE = "fr_weld_source"          # on a part whose bodies became welds (it is left out: excluded)
LAST: dict = {}                    # the last run's numbers: welds, by_shape, seconds (tests, the PC check, the report)
_NOTICE = [""]


def take_notice() -> str:
    """What the last import found ('' when nothing): for the import's message."""
    t, _NOTICE[0] = _NOTICE[0], ""
    return t


def _np(m) -> np.ndarray:
    return np.array([list(r) for r in m], np.float64)


def meshes_of(objs, tables: dict | None = None) -> list:
    """``core.weld_cad.Mesh`` of each part (world metres), key = the object's name. ``tables``: the mesh tables read
    so far, by mesh (copies of a part share one)."""
    out = []
    tables = {} if tables is None else tables
    for ob in objs:
        if ob.type != "MESH" or ob.data is None or not len(ob.data.polygons):
            continue
        if ob.data.name not in tables:
            tables[ob.data.name] = welds.mesh_tables(ob.data)
        p, t, f = tables[ob.data.name]
        M = _np(ob.matrix_world)
        if np.linalg.det(M[:3, :3]) < 0:
            t = t[:, ::-1]
        out.append(cad.Mesh(ob.name, ob.get(build.PROP_NAME, ob.name), p @ M[:3, :3].T + M[:3, 3], t, f,
                            ob.get(build.PROP_CAD_MATERIAL, "") or ""))
    return out


def _may_be(ob) -> bool:
    """Before reading its mesh: a part that may be a bead by its shape (not a known part, not a big mesh)."""
    if ob.type != "MESH" or ob.data is None or not len(ob.data.polygons) or len(ob.data.polygons) > 20000:
        return False
    return not cad.known_part(ob.get(build.PROP_NAME, ob.name))


def _parts_of(root, include=()) -> list:
    """The parts of a model a bead may be or lie on: not those left out for good (``include``: unless named here –
    the new revision of a welds body, which a model update left out as the old one was)."""
    if root is None:
        return []
    out = []
    stack = [root]
    while stack:
        o = stack.pop()
        if o.get(build.PROP_KIND) == "part" and o.type == "MESH" and (not o.get(build.PROP_EXCLUDED)
                                                                        or o.name in include):
            out.append(o)
        stack.extend(o.children)
    return out


def _cad_welds_of(scene, root) -> list:
    out = []
    for it in welds.items(scene):
        if it.from_cad and it.cad_source is not None and build.model_root_of(it.cad_source) == root:
            out.append(it)
    return out


def detect(scene, root, progress=None, include=(), budget=cad.SHAPE_BUDGET) -> tuple:
    """(found, {key: object}, named keys, meshes) of one model (``budget``: seconds for the search by shape). The other
    parts' meshes are read only when there is a body to look at (an import without welds costs next to nothing)."""
    objs = _parts_of(root, include)
    obs = {o.name: o for o in objs}
    done = {it.cad_source.name for it in _cad_welds_of(scene, root) if it.cad_source is not None}
    tables: dict = {}
    named_obs = [o for o in objs if o.name not in done and cad.weld_name(o.get(build.PROP_NAME, o.name))]
    named = {o.name for o in named_obs}
    maybe = meshes_of([o for o in objs if o.name not in done and o.name not in named and _may_be(o)], tables)
    bodies = meshes_of(named_obs, tables) + [m for m in maybe if cad.maybe_bead(m)]
    if not bodies:
        return [], obs, named, bodies
    ms = meshes_of([o for o in objs if o.name not in done], tables)
    by = {m.key: m for m in ms}
    bodies = [by[b.key] for b in bodies]
    parts = [m for m in ms if m.key not in named]
    return cad.find(bodies, parts, named, progress=progress, budget=budget), obs, named, ms


def after_import(scene, root) -> str:
    """Find the welds in a model just imported and make them. Returns the words for the import's message."""
    if root is None:
        return ""
    t0 = time.perf_counter()
    try:
        bpy.context.view_layer.update()        # new parts have no world place until the next update (CLAUDE.md 8)
        made, by_shape = make_all(scene, root)
    except Exception as exc:  # noqa: BLE001 - finding welds must never break an import
        print("Fresing Render: welds from the CAD file not read:", exc)
        LAST.update(welds=0, by_shape=0, seconds=time.perf_counter() - t0, error=str(exc))
        return ""
    LAST.update(welds=len(made), by_shape=by_shape, seconds=time.perf_counter() - t0, error="",
                stopped=cad.STOPPED[0])
    if cad.STOPPED[0]:
        _NOTICE[0] = (f"{plural(len(made), 'weld')} from the CAD file; the search for unnamed weld beads stopped "
                      f"after {cad.SHAPE_BUDGET:.0f} s – 3 Looks > Welds > Find in CAD file looks further")
        return _NOTICE[0]
    if not made:
        return ""
    text = f"{plural(len(made), 'weld')} from the CAD file (3 Looks > Welds)"
    if by_shape:
        text += f"; found {plural(by_shape, 'weld')} by {'its' if by_shape == 1 else 'their'} shape – check them"
    _NOTICE[0] = text
    return text


def make_all(scene, root, budget=cad.SHAPE_BUDGET) -> tuple:
    """The welds of one model: (new weld keys, how many of them by shape)."""
    found, obs, _named, ms = detect(scene, root, budget=budget)
    by_key = {m.key: m for m in ms}
    keys = []
    by_shape = 0
    sources = set()
    for f in found:
        it = make(scene, f, obs, by_key)
        if it is None:
            continue
        keys.append(it.key)
        sources.add(f.body)
        if f.how == "shape":
            by_shape += 1
    from . import logic
    srcs = [obs[k] for k in sources if k in obs]
    for ob in srcs:
        ob[SOURCE] = True
    if srcs:
        logic.exclude(srcs, True)
    welds.count(scene)
    return keys, by_shape


def _source_triangles(mesh: cad.Mesh, f: cad.Found):
    return mesh.points, mesh.tris[f.tris]


def _store_mesh(item, pts_local: np.ndarray, tris: np.ndarray, uv: np.ndarray):
    """The CAD bead's shape in part A's coordinates, as a mesh datablock the weld keeps (``cad_mesh``)."""
    used, inv = np.unique(tris.ravel(), return_inverse=True)
    v = pts_local[used]
    t = inv.reshape(-1, 3)
    name = f"FR weld CAD {item.key}"
    old = item.cad_mesh
    me = welds._write_mesh(name, v, [tuple(x) for x in t.tolist()], uv.reshape(-1, 2).tolist(), smooth=True)
    me["fr_weld_cad"] = True
    item.cad_mesh = me
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    return me


def _set_from_found(item, f: cad.Found, obs: dict, by_key: dict, keep_settings: bool) -> None:
    """Shape, seams and sizes from what was found; the settings (finish, process …) only when new."""
    a, b = obs[f.part_a], obs.get(f.part_b) if f.part_b else None
    if b is None:
        b = a
    src = obs[f.body]
    body = by_key[f.body]
    Ainv = np.linalg.inv(_np(a.matrix_world))
    seams = cad.transform(f.seams, Ainv) if f.seams else [_line_of(body, f, Ainv)]
    welds._BUSY[0] = True
    try:
        item.from_cad = True
        item.part_a, item.part_b = a, b
        item.cad_source = src
        item.whole = True
        item.faces_a = item.faces_b = "[]"
        item.prints_a = item.prints_b = "{}"
        item.cad_how = f.how
        item.cad_kind = f.kind
        item.cad_note = f.note
        item.cad_closed = bool(f.closed)
        item.cad_parts = f.joins
        item.cad_legs = tuple(float(x) for x in f.legs)
        item.cad_length = float(f.length)
        item.cad_metal = f.metal
        if f.kind == "BUTT":
            item.kind = "BUTT"
            item.butt_width = max(0.002, f.size)
        elif f.kind == "FILLET":
            item.kind = "FILLET"
            item.size = max(0.001, f.size)
        else:
            item.kind = "AUTO"
        if f.intermittent:
            n, piece, pitch = f.intermittent
            item.intermittent, item.length, item.pitch = True, max(0.005, piece), max(0.01, pitch)
        else:
            item.intermittent = False
        item.lost = False
        item.note = ""
        welds.store_seams(item.seams, seams)
        if not keep_settings:
            ka, kb = welds.metal_kind(a), welds.metal_kind(b)
            d = core.defaults(ka, kb, 0.0)
            item.metal = f.metal if f.metal else "AUTO"
            item.finish = d["finish"]
            item.paint_from = d["paint_from"]
            item.found_metal = f.metal or d["metal"]
    finally:
        welds._BUSY[0] = False
    welds._keep(item, seams, _np(a.matrix_world.inverted() @ b.matrix_world))
    pts = body.points @ Ainv[:3, :3].T + Ainv[:3, 3]
    tris = body.tris[f.tris]
    uv = cad.uvs(pts, tris, seams, f.kind, f.size)
    _store_mesh(item, pts, tris, uv)


def _line_of(body: cad.Mesh, f: cad.Found, Ainv) -> core.Seam:
    """A bead whose line was not found (OTHER): a straight line along it, for its length and where its symbol points."""
    pts = body.points[np.unique(body.tris[f.tris])]
    c = pts.mean(0)
    _u, _s, vt = np.linalg.svd(pts - c, full_matrices=False)
    x = (pts - c) @ vt[0]
    p0, p1 = c + vt[0] * x.min(), c + vt[0] * x.max()
    t = core.unit(p1 - p0)
    n = core.unit(np.cross(t, vt[1]))
    d = core.unit(np.cross(n, t))
    corner = core.Corner("FILLET", 90.0, c, d, n, 0, c, n, -d, 0)
    s = core.Seam(np.array([p0, p1]), [corner, corner], False, "FILLET")
    return cad.transform([s], Ainv)[0]


def make(scene, f: cad.Found, obs: dict, by_key: dict):
    """A new weld from a found bead (None when its part is not there)."""
    if f.part_a not in obs or f.body not in obs:
        return None
    s = welds.settings(scene)
    a = obs[f.part_a]
    b = obs.get(f.part_b) if f.part_b else None
    item = s.items.add()
    key = welds._new_key(scene)
    welds._BUSY[0] = True
    try:
        item.key = key
        base = f"{welds.part_name(a)} – {welds.part_name(b)}" if b is not None else welds.part_name(a)
        item.name = welds._unique_name(scene, base)
    finally:
        welds._BUSY[0] = False
    item = welds.find_item(scene, key)
    _set_from_found(item, f, obs, by_key, keep_settings=False)
    item = welds.find_item(scene, key)
    welds.rebuild(item)
    return welds.find_item(scene, key)


# ---------------------------------------------------------------------------
# the bead from the CAD shape (rebuild asks), switches
# ---------------------------------------------------------------------------

def bead_geometry(item):
    """(verts, faces, uvs per corner) of the CAD bead in part A's coordinates, or None (the app's bead is wanted, or
    the shape is not there)."""
    if not item.from_cad or not item.cad_shape:
        return None
    me = item.cad_mesh
    if me is None or not len(me.polygons):
        return None
    n = len(me.vertices)
    co = np.zeros(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    loops = np.zeros(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loops)
    starts = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_start", starts)
    totals = np.zeros(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", totals)
    uvl = me.uv_layers.get("fr_weld")
    uv = np.zeros(len(me.loops) * 2, np.float32)
    if uvl is not None:
        uvl.data.foreach_get("uv", uv)
    faces = [tuple(loops[s:s + k].tolist()) for s, k in zip(starts, totals)]
    return co.reshape(-1, 3).astype(np.float64), faces, uv.reshape(-1, 2).tolist()


def set_shape(scene, item, cad_shape: bool) -> None:
    item.cad_shape = cad_shape           # (its update rebuilds)


def set_all(scene, **values) -> int:
    """The same setting on every weld from the CAD file (``cad_shape``, ``finish``): how many changed."""
    n = 0
    keys = [it.key for it in welds.items(scene) if it.from_cad and not it.lost]
    for k in keys:
        it = welds.find_item(scene, k)
        changed = False
        welds._BUSY[0] = True
        try:
            for name, v in values.items():
                if name == "finish" and v == "PAINTED" and not _paint_side(it):
                    continue                     # neither part is painted: stays bare
                if getattr(it, name) != v:
                    setattr(it, name, v)
                    changed = True
            if values.get("finish") == "PAINTED" and changed:
                it.paint_from = _paint_side(it) or "A"
        finally:
            welds._BUSY[0] = False
        if changed:
            welds.rebuild(welds.find_item(scene, k))
            n += 1
    return n


def _paint_side(item) -> str:
    if welds.metal_kind(item.part_a) == "PAINTED":
        return "A"
    if item.part_b is not None and welds.metal_kind(item.part_b) == "PAINTED":
        return "B"
    return ""


def count(scene) -> int:
    return sum(1 for it in welds.items(scene) if it.from_cad)


def describe(item) -> str:
    """'From the CAD file (by its name) · fillet a5 · legs 10 × 6 mm' for the panel."""
    how = "by its name" if item.cad_how == "name" else "by its shape – check it"
    if item.cad_kind == "BUTT":
        size = f"groove, cap {cad._mm(item.butt_width)} mm"
    elif item.cad_kind == "FILLET":
        size = f"fillet a{cad._mm(item.size)}"
    else:
        size = "own shape"
    text = f"From the CAD file ({how}) · {size}"
    if item.intermittent:
        text += f" · {round(item.cad_length / max(item.length, 1e-6))} × {item.length * 1000:.0f} ({item.pitch * 1000:.0f})"
    if item.cad_note:
        text += f" · {item.cad_note}"
    return text


def put_back(scene, root=None) -> int:
    """Remove the welds from the CAD file (of one model, or all) and show their CAD parts again. Returns how many."""
    from . import logic
    its = [it for it in welds.items(scene) if it.from_cad and (root is None or (
        it.cad_source is not None and build.model_root_of(it.cad_source) == root))]
    srcs = {it.cad_source.name for it in its if it.cad_source is not None}
    keys = [it.key for it in its]
    for k in keys:
        it = welds.find_item(scene, k)
        if it is not None:
            remove_mesh(it)
            welds.remove(scene, it)
    obs = [bpy.data.objects[n] for n in srcs if n in bpy.data.objects]
    for ob in obs:
        if SOURCE in ob:
            del ob[SOURCE]
    if obs:
        logic.exclude(obs, False)
    return len(keys)


def remove_mesh(item) -> None:
    me = item.cad_mesh
    if me is None:
        return
    welds._BUSY[0] = True
    try:
        item.cad_mesh = None
    finally:
        welds._BUSY[0] = False
    if me.users == 0:
        bpy.data.meshes.remove(me)


def find_again(scene) -> tuple:
    """*Find welds in the CAD file*: every model looked at again (beads already made are skipped)."""
    made, by_shape = [], 0
    bpy.context.view_layer.update()
    for root in build.model_roots(scene):
        m, s = make_all(scene, root, budget=None)        # asked for: no time limit
        made += m
        by_shape += s
    return made, by_shape


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def carry_over(scene, pairs, new_root) -> tuple:
    """After a model update: the CAD welds of the updated model follow its new beads (see the module text). Returns
    (report lines, undo)."""
    by_name = {o.name: n for o, n in pairs}
    old_items = [it for it in welds.items(scene) if it.from_cad and it.cad_source is not None
                 and it.cad_source.name in by_name]
    # also the welds whose source is gone from the new model (its part was renamed or deleted in the CAD)
    olds = {it.key for it in old_items}
    for it in welds.items(scene):
        if it.from_cad and it.key not in olds and it.part_a is not None and it.part_a.name in by_name:
            old_items.append(it)
            olds.add(it.key)
    saved = []
    for it in old_items:
        saved.append({k: it.get(k) for k in it.keys() if k not in ("seams",)} | {
            "_key": it.key, "_a": it.part_a, "_b": it.part_b, "_src": it.cad_source, "_mesh": it.cad_mesh,
            "_seams": [(s.length, s.kind, s.closed, s.angle, tuple(s.mid), s.enabled) for s in it.seams]})
    for it in old_items:                                  # the old beads go with the old model
        for ob in welds.objects_of(it):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        welds._CACHE.pop(it.key, None)
    notes = []
    bpy.context.view_layer.update()                       # the new parts' places
    include = {n.name for o, n in pairs if o.get(SOURCE)}
    found, obs, _named, ms = detect(scene, new_root, include=include)
    by_key = {m.key: m for m in ms}
    # the old welds' lines in the new part A's coordinates
    old_rows, keys = [], []
    for it in old_items:
        na = by_name.get(it.part_a.name) if it.part_a is not None else None
        nb = by_name.get(it.part_b.name) if it.part_b is not None else None
        try:
            seams = core.unpack_seams(it.seam_data) if it.seam_data else []
        except Exception:  # noqa: BLE001
            seams = []
        M = _np(na.matrix_world) if na is not None else np.eye(4)
        pts = cad.line_points(cad.transform(seams, M)) if seams else np.zeros((0, 3))
        old_rows.append((na.name if na is not None else "?a", nb.name if nb is not None else "?b", pts))
        keys.append(it.key)
    new_rows = [(f.part_a, f.part_b or f.part_a, cad.line_points(f.seams) if f.seams else np.zeros((0, 3)))
                for f in found]
    pairs_m = cad.match(old_rows, new_rows)
    used = set()
    new_keys = []
    for i, j in pairs_m:
        it = welds.find_item(scene, keys[i])
        if j is None:
            welds._BUSY[0] = True
            try:
                it.lost = True
                it.note = "Weld lost in the new model – its bead is not in the CAD file any more"
            finally:
                welds._BUSY[0] = False
            notes.append(f"Weld '{it.name}': lost in the new model (its bead is not in the CAD file any more)")
            continue
        used.add(j)
        f = found[j]
        before = (round(it.size, 5), round(it.butt_width, 5), round(it.cad_length, 4), it.intermittent)
        _set_from_found(it, f, obs, by_key, keep_settings=True)
        it = welds.find_item(scene, keys[i])
        welds.rebuild(it)
        after = (round(it.size, 5), round(it.butt_width, 5), round(it.cad_length, 4), it.intermittent)
        if before != after:
            notes.append(f"Weld '{it.name}': changed in the new model ({cad.describe(f)})")
    for j, f in enumerate(found):
        if j in used:
            continue
        it = make(scene, f, obs, by_key)
        if it is not None:
            new_keys.append(it.key)
            notes.append(f"New weld from the CAD file: '{it.name}' ({cad.describe(f)})")
    from . import logic
    srcs = [obs[f.body] for f in found if f.body in obs]
    for ob in srcs:
        ob[SOURCE] = True
    if srcs:
        logic.exclude(srcs, True)
    welds.count(scene)

    def undo():
        for k in new_keys:
            it = welds.find_item(scene, k)
            if it is not None:
                remove_mesh(it)
                welds.remove(scene, it)
        for d in saved:
            it = welds.find_item(scene, d["_key"])
            if it is None:
                continue
            welds._BUSY[0] = True
            try:
                for k, v in d.items():
                    if k.startswith("_"):
                        continue
                    try:
                        it[k] = v
                    except (TypeError, ValueError):
                        pass
                it.part_a, it.part_b, it.cad_source, it.cad_mesh = d["_a"], d["_b"], d["_src"], d["_mesh"]
                it.seams.clear()
                for length, kind, closed, angle, mid, enabled in d["_seams"]:
                    x = it.seams.add()
                    x.length, x.kind, x.closed, x.angle, x.mid, x.enabled = length, kind, closed, angle, mid, enabled
            except ReferenceError:
                continue
            finally:
                welds._BUSY[0] = False
            welds._CACHE.pop(it.key, None)
            if not it.lost:
                welds.rebuild(it)
    return notes, undo


def stats(scene) -> dict:
    its = [it for it in welds.items(scene) if it.from_cad]
    return {"welds": len(its), "by_shape": sum(1 for it in its if it.cad_how == "shape"),
            "cad_shape": sum(1 for it in its if it.cad_shape), "lost": sum(1 for it in its if it.lost),
            "sources": sorted({it.cad_source.get(build.PROP_NAME, "") for it in its if it.cad_source is not None})}


def table(scene) -> list:
    """[(name, kind, size mm, length mm, closed, intermittent (n, l, e) mm or None)] of the CAD welds (tests, the PC
    check)."""
    out = []
    for it in welds.items(scene):
        if not it.from_cad:
            continue
        size = it.butt_width if it.cad_kind == "BUTT" else it.size
        inter = None
        if it.intermittent:
            inter = (round(it.cad_length / max(it.length, 1e-6)), round(it.length * 1000, 1), round(it.pitch * 1000, 1))
        out.append((it.name, it.cad_kind, round(size * 1000, 1), round(it.cad_length * 1000, 1), it.cad_closed, inter))
    return out


def json_table(scene) -> str:
    return json.dumps(table(scene))
