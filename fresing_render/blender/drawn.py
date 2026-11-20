"""Hoses, cables and drag chains drawn in the app by clicking points (task 0240).

Most CAD models have no hoses or cables, and a drag chain that is there is often one simplified block. Here the user
clicks where a hose, cable or chain goes; ``flex.draw_hose`` / ``flex.draw_chain`` / ``paths.draw_cable`` make a
normal item of it. This file has what the three share:

* **The drawn object.** A drawn item has no CAD part, so the app makes one: a mesh part (``fr_kind`` "part", so a
  group's look from 3 Looks, the web 3D export and the render queue treat it as any other part), with no parent and
  the identity matrix, in its own collection ``COLLECTION`` (a model update sets aside only the collections of the
  model it replaces), tagged ``TAG`` = "HOSE" / "CHAIN" / "CABLE". Its own mesh is a tube along the line drawn
  (``set_tube``): what shows when the item is off or one of its parts is gone – the item keeps its last place.
* **A click -> a spot** (``spot``): where on the clicked part the line starts or passes, and which way it runs there,
  both in the part's own coordinates (they move with it). A round face (a fitting's stub, a gland, a clip's bore):
  the point on its axis at the end of the round face nearer the click, the direction along the axis out of that end.
  A flat face: its middle when it is small (a fitting's end face, a bracket's tab; ``SNAP``), else the point clicked;
  the direction is the face's normal.
* **Replacing a CAD part** (``replace`` / ``unreplace``): a simplified CAD hose or chain is excluded ("hidden for
  good": not in the view, not in renders, left out of the clash check and the web export) while the drawn item that
  replaces it is in the list; it shows again when the item is removed. A chain link takes its whole row with it.

Units: metres, world coordinates unless said otherwise.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix

from . import build

TAG = "fr_drawn"                        # on a drawn object: "HOSE" / "CHAIN" / "CABLE"
OWNER = "fr_drawn_owner"                # on a drawn object: the name of the item it draws (a hint; the item points at it)
REPLACED = "fr_replaced_by"             # on a replaced CAD part: the name of the drawn item that replaces it
WAS_EXCLUDED = "fr_replaced_was_excluded"   # … it was excluded already before (it stays so when the item goes)
COLLECTION = "Drawn hoses and cables"
SIDES = 16                              # of a drawn object's own tube
SNAP = 0.1                              # m: a flat face up to this size is clicked at its middle
GROUPS = {"HOSE": "Hoses & tubing", "CABLE": "Cables", "CHAIN": "Cable chains"}
NAMES = {"HOSE": "Hose", "CABLE": "Cable", "CHAIN": "Drag chain"}


class DrawError(RuntimeError):
    """A click or a drawing that cannot be used; the text says why, in plain words."""


# ---------------------------------------------------------------------------
# the drawn object
# ---------------------------------------------------------------------------

def is_drawn(ob) -> bool:
    try:
        return ob is not None and bool(ob.get(TAG))
    except ReferenceError:
        return False


def drawn_objects(scene) -> list:
    return [ob for ob in scene.objects if is_drawn(ob)]


def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _uid(scene, kind: str) -> str:
    taken = {ob.get(build.PROP_UID) for ob in scene.objects if is_drawn(ob)}
    n = 1
    while f"fr-drawn/{kind.lower()}/{n}" in taken:
        n += 1
    return f"fr-drawn/{kind.lower()}/{n}"


def make_object(scene, kind: str, name: str, points=None, radius: float = 0.005):
    """A new drawn object for an item of ``kind`` called ``name``; its own mesh a tube along ``points``."""
    me = bpy.data.meshes.new(f"FR drawn {name}")
    ob = bpy.data.objects.new(name, me)
    _collection(scene).objects.link(ob)
    ob[TAG] = kind
    ob[OWNER] = name
    ob[build.PROP_KIND] = "part"
    ob[build.PROP_NAME] = name
    ob[build.PROP_UID] = _uid(scene, kind)
    ob[build.PROP_COLOR] = ""
    ob[build.PROP_CAD_MATERIAL] = ""
    ob.matrix_world = Matrix.Identity(4)
    build.set_mat(ob, build.PROP_CAD_BASIS, Matrix.Identity(4))
    ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
    if points is not None:
        set_tube(ob, points, radius)
    look(scene, ob, GROUPS.get(kind, "Hoses & tubing"))
    return ob


def rename(ob, name: str) -> None:
    if not is_drawn(ob):
        return
    ob[OWNER] = name
    ob[build.PROP_NAME] = name
    if ob.name != name:
        ob.name = name


def look(scene, ob, group: str) -> None:
    """The object goes into the material group ``group`` (made with its usual look when it is new), as "Assign
    selected" in 3 Looks does: the group's look is its look, and changes with it."""
    from . import logic, materials
    s = scene.fresing
    g = logic.ensure_group(s, group)
    ob["fr_group_manual"] = group
    ob[build.PROP_GROUP] = group
    materials.assign(ob, materials.ensure_material(g.name, g.material, g.color, g.wear))


def delete_object(ob) -> None:
    """Remove a drawn object and its mesh (never a CAD part)."""
    if not is_drawn(ob):
        return
    me = ob.data
    bpy.data.objects.remove(ob, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def _frames(pts: np.ndarray) -> tuple:
    """Two unit vectors square to the line at each point, turning as little as possible along it."""
    t = np.gradient(pts, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-12)
    n = len(pts)
    u, v = np.empty((n, 3)), np.empty((n, 3))
    a = np.array((0.0, 0.0, 1.0)) if abs(t[0][2]) < 0.9 else np.array((1.0, 0.0, 0.0))
    u[0] = np.cross(t[0], a)
    u[0] /= np.linalg.norm(u[0])
    for k in range(1, n):
        w = u[k - 1] - t[k] * float(u[k - 1] @ t[k])
        ln = float(np.linalg.norm(w))
        if ln < 1e-9:
            w = np.cross(t[k], a)
            ln = float(np.linalg.norm(w)) or 1.0
        u[k] = w / ln
    v[:] = np.cross(t, u)
    return u, v


def tube_arrays(points, radius: float, sides: int = SIDES) -> tuple:
    """(points (V, 3), triangles (T, 3)) of a closed tube of ``radius`` along the line ``points`` (n, 3)."""
    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    keep = np.concatenate([[True], np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-9])
    pts = pts[keep]
    if len(pts) < 2:
        raise DrawError("The line has no length.")
    u, v = _frames(pts)
    ang = np.linspace(0.0, 2.0 * math.pi, sides, endpoint=False)
    ring = (np.cos(ang)[None, :, None] * u[:, None] + np.sin(ang)[None, :, None] * v[:, None]) * radius
    co = (pts[:, None] + ring).reshape(-1, 3)
    n = len(pts)
    i = np.arange(n - 1)[:, None] * sides
    j = np.arange(sides)[None, :]
    a, b = i + j, i + (j + 1) % sides
    c, d = a + sides, b + sides
    tris = np.concatenate([np.stack([a, b, d], -1).reshape(-1, 3), np.stack([a, d, c], -1).reshape(-1, 3)])
    first, last = len(co), len(co) + 1                     # the two end caps: a fan round each end's centre
    co = np.concatenate([co, pts[:1], pts[-1:]])
    k = np.arange(sides)
    cap0 = np.stack([np.full(sides, first), (k + 1) % sides, k], -1)
    cap1 = np.stack([np.full(sides, last), (n - 1) * sides + k, (n - 1) * sides + (k + 1) % sides], -1)
    return co, np.concatenate([tris, cap0, cap1]).astype(np.int64)


def set_tube(ob, points, radius: float) -> None:
    """The object's own mesh becomes a tube along ``points`` (world; the object sits at the identity)."""
    co, tris = tube_arrays(points, max(float(radius), 1e-5))
    me = ob.data
    me.clear_geometry()
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.astype(np.float32).reshape(-1))
    me.loops.add(len(tris) * 3)
    me.loops.foreach_set("vertex_index", tris.astype(np.int32).reshape(-1))
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tris) * 3, 3, dtype=np.int32))
    me.update()
    for poly in me.polygons:
        poly.use_smooth = True
    me.update()


# ---------------------------------------------------------------------------
# a click
# ---------------------------------------------------------------------------

def _np(m) -> np.ndarray:
    return np.array(m, dtype=float)


def spot(ob, polygon: int, location, normal) -> dict:
    """What a click on ``ob`` at ``polygon`` / ``location`` (world) means for a line that starts or passes there:
    {"part", "point", "dir" (world, unit), "round" (a round face was clicked), "diameter" (of that round face, m;
    0 for a flat one), "hit" (the point clicked), "local_point", "local_dir" (in the part's own coordinates)}.
    Raises DrawError."""
    from . import hover, joints
    if ob is None or ob.type != "MESH" or ob.data is None or ob.get(build.PROP_KIND) != "part":
        raise DrawError("Click a part of the model.")
    if is_drawn(ob):
        raise DrawError(f"'{ob.get(build.PROP_NAME, ob.name)}' is a drawn hose, cable or chain itself: click the "
                        "part it is fixed to.")
    w = _np(ob.matrix_world)
    loc = np.asarray(location, dtype=float)
    o, d, desc = joints.axis_from_hit(ob, polygon, location, normal)
    o, d = np.asarray(o, dtype=float), np.asarray(d, dtype=float)
    d = d / (np.linalg.norm(d) or 1.0)
    n, starts, tris, co = hover._mesh(ob.data)
    face = int(np.searchsorted(starts, polygon, side="right") - 1) if 0 <= polygon < n else -1
    pts = co[tris[int(starts[face]):int(starts[face + 1])].reshape(-1)] if face >= 0 else np.zeros((0, 3))
    pts = pts.astype(float) @ w[:3, :3].T + w[:3, 3]
    out = {"part": ob, "round": desc.startswith("round"), "diameter": 0.0, "hit": loc}
    if out["round"]:
        m = desc.split("Ø")
        try:
            out["diameter"] = float(m[1].split()[0]) / 1000.0 if len(m) > 1 else 0.0
        except ValueError:
            out["diameter"] = 0.0
        t = (pts - o) @ d if len(pts) else np.array([0.0])
        lo, hi = float(t.min()), float(t.max())
        here = float((loc - o) @ d)
        end = hi if abs(hi - here) <= abs(here - lo) else lo
        sign = 1.0 if end >= 0.5 * (lo + hi) else -1.0
        if hi - lo < 1e-6:                                 # a ring of no width: out of the side the click came from
            sign = 1.0
        out["point"], out["dir"] = o + d * end, d * sign
    else:
        size = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 0.0
        if len(pts) and size <= SNAP:
            corners = pts.reshape(-1, 3, 3) if len(pts) % 3 == 0 else None
            if corners is not None:                         # the middle of the face, by area
                cr = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
                area = np.linalg.norm(cr, axis=1)
                mid = (corners.mean(axis=1) * area[:, None]).sum(axis=0) / max(float(area.sum()), 1e-18)
            else:
                mid = pts.mean(axis=0)
            out["point"] = mid - d * float((mid - loc) @ d)    # in the face's plane
        else:
            out["point"] = loc
        out["dir"] = d
    inv = np.linalg.inv(w)
    out["local_point"] = inv[:3, :3] @ out["point"] + inv[:3, 3]
    ld = inv[:3, :3] @ out["dir"]
    out["local_dir"] = ld / (np.linalg.norm(ld) or 1.0)
    return out


def spot_words(sp: dict, what: str) -> str:
    """'End A: the end of the round face Ø22 mm, along its axis' – what the click takes, for the status line."""
    name = sp["part"].get(build.PROP_NAME, sp["part"].name)
    if sp["round"]:
        dia = f" Ø{sp['diameter'] * 1000.0:.0f} mm" if sp["diameter"] else ""
        return f"{what} on '{name}': the end of the round face{dia}, along its axis"
    return f"{what} on '{name}': this flat face, at right angles to it"


def world_spot(part, point, direction) -> tuple:
    """A spot kept in ``part``'s own coordinates, in the world now: (point, unit direction)."""
    w = _np(part.matrix_world)
    p = w[:3, :3] @ np.asarray(point, dtype=float) + w[:3, 3]
    d = w[:3, :3] @ np.asarray(direction, dtype=float)
    return p, d / (np.linalg.norm(d) or 1.0)


# ---------------------------------------------------------------------------
# replacing a simplified CAD part
# ---------------------------------------------------------------------------

def replace_targets(scene, ob) -> list:
    """What "Replaces CAD part" hides for the clicked ``ob``: a chain link -> its whole row of links; else ``ob``."""
    if ob is None or ob.get(build.PROP_KIND) != "part" or is_drawn(ob):
        return []
    from . import ops_flex
    row = ops_flex.row_of(scene, ob)
    return row if row else [ob]


def replace(scene, item, ob) -> list:
    """The drawn ``item`` (a hose, chain or cable of the lists) replaces the CAD part ``ob`` (its row of links):
    those are excluded – hidden in the view and in renders, left out of the clash check and the web export – until
    the item is removed. Returns the parts. Raises DrawError."""
    from . import logic
    parts = replace_targets(scene, ob)
    if not parts:
        raise DrawError("Click the simplified CAD hose, cable or chain in the 3D view first.")
    for p in parts:
        other = p.get(REPLACED)
        if other and other != item.name:
            raise DrawError(f"'{p.get(build.PROP_NAME, p.name)}' is replaced by '{other}' already.")
    have = {r.obj.name for r in item.replaces if r.obj is not None}
    new = [p for p in parts if p.name not in have]
    for p in new:
        p[WAS_EXCLUDED] = bool(p.get(build.PROP_EXCLUDED))
        p[REPLACED] = item.name
        item.replaces.add().obj = p
    logic.exclude([p for p in new if not p.get(build.PROP_EXCLUDED)], True)
    item.replace_uids = "\n".join(r.obj.get(build.PROP_UID, "") for r in item.replaces if r.obj is not None)
    return parts


def unreplace(scene, item) -> int:
    """The CAD parts the item replaced show again (those the app excluded; one excluded before stays so)."""
    from . import logic
    back = []
    for r in item.replaces:
        p = r.obj
        try:
            if p is None or not p.name:
                continue
        except ReferenceError:
            continue
        if not p.get(WAS_EXCLUDED):
            back.append(p)
        for key in (REPLACED, WAS_EXCLUDED):
            if key in p:
                del p[key]
    if back:
        logic.exclude(back, False)
    item.replaces.clear()
    item.replace_uids = ""
    return len(back)


def replaced_names(item) -> list:
    return [r.obj.get(build.PROP_NAME, r.obj.name) for r in item.replaces if r.obj is not None]


def renamed(item, old: str) -> None:
    """The item was renamed: its replaced parts and its object name it."""
    for r in item.replaces:
        if r.obj is not None and r.obj.get(REPLACED) == old:
            r.obj[REPLACED] = item.name
    if is_drawn(item.part):
        rename(item.part, item.name)


def after_model_update(scene, item, by_uid: dict, mapping: dict) -> None:
    """The replaced parts go to the new revision's parts (by part ID) and stay excluded there."""
    from . import logic
    uids = [u for u in item.replace_uids.split("\n") if u]
    if not uids:
        return
    item.replaces.clear()
    found = []
    for u in uids:
        ob = by_uid.get(u) or by_uid.get(mapping.get(u, u))
        if ob is None:
            new = mapping.get(u, u)
            ob = next((o for o in scene.objects if o.get(build.PROP_UID) == new), None)
        if ob is not None:
            found.append(ob)
            item.replaces.add().obj = ob
            ob[REPLACED] = item.name
            if WAS_EXCLUDED not in ob:
                ob[WAS_EXCLUDED] = False
    logic.exclude([o for o in found if not o.get(build.PROP_EXCLUDED)], True)
    item.replace_uids = "\n".join(o.get(build.PROP_UID, "") for o in found)
