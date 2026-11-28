"""The coolant liquid's six checks in Blender (task 0347 D; study 0251's stand-alone tests, ``core/liquid_lab.py``).

``build(scene, folder)`` puts the six small invented rigs side by side in the scene – a closed pocket, an open slot, a
plate that tilts, a sloped tray with a drain, a box that stops hard, a tank with a thin wall –, each chart as a grey
solid (the tray's drain a dark disc; the moving ones keyed frame by frame), works out the liquid of every case (one
``core.liquid.Liquid`` each) into a bake per case (``core/liquid_cache.py``) in a folder "Liquid lab", and keeps
in the scene (``PROP``, JSON text) where the bakes are and each case's number.

A frame handler of its own draws the liquid from the bakes only (the same frame always gives the same picture): one
sheet per chart ("FR liquid lab <case> <chart>", a child of the chart's solid, made with ``liquid.sheet``) and the
drops of all six (little spheres, as ``liquid.show``). Scene frame ``start + k`` shows frame k of every case (its last
frame once a case has ended). The bakes are found again after the project is saved and opened elsewhere: next to the
project, in its folder "Liquid lab".
"""

from __future__ import annotations

import json
import math
import os
import threading
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix

from ..core import liquid_cache
from ..core import liquid_lab as core

PROP = "fr_liquid_lab"                    # on the scene: the lab (JSON text)
TAG = "fr_liquid_lab"                     # on everything made here (value: its role)
COLLECTION = "FR Liquid lab"
FOLDER = "Liquid lab"
VERSION = 1                               # of the bakes: a change here makes them again
MAT_BED = "FR liquid lab rig"
MAT_DRAIN = "FR liquid lab drain"
OBJ_DROPS = "FR liquid lab drops"
BOTTOM = 0.01                             # m: a rig's solid reaches this far below its lowest bed
RIM = (0.005, 0.015)                      # m: a closed chart's wall stands this far over its highest bed, and at least
                                          # this far over its lowest
MM = 1e-3

_READERS: dict = {}                       # path -> Reader
_CASES: dict = {}                         # case id -> the case at its own place (its beds for the sheets)
_STATE = {"guard": 0}


def bed_name(cid: str, chart: str) -> str:
    return f"FR liquid lab rig {cid} {chart}"


def sheet_name(cid: str, chart: str) -> str:
    return f"FR liquid lab {cid} {chart}"


def fingerprint(cid: str) -> str:
    return f"liquid-lab-{VERSION}-{cid}"


# ---------------------------------------------------------------------------
# the rigs' solids
# ---------------------------------------------------------------------------

def bed_mesh(chart) -> tuple:
    """A chart's surface as a solid in the chart's frame: (verts (n, 3), quads (m, 4), material index per quad).
    Every cell a flat top at its bed height, upright faces where neighbours differ, a bottom ``BOTTOM`` under the
    lowest bed. A chart with walls (``open_edges`` False) gets a wall one cell thick round it (``RIM``) over its
    highest bed. Drain cells' tops have material 1."""
    bed = np.asarray(chart.bed, float)
    cell = float(chart.cell)
    x0, y0 = float(chart.x0), float(chart.y0)
    drain = np.zeros(bed.shape, bool) if chart.drain is None else np.asarray(chart.drain) > 0
    fin = np.isfinite(bed)
    zb = float(bed[fin].min()) - BOTTOM if fin.any() else -BOTTOM
    if not chart.open_edges:
        rim = max(float(bed[fin].max()) + RIM[0], float(bed[fin].min()) + RIM[1]) if fin.any() else RIM[1]
        bed = np.pad(bed, 1, constant_values=rim)
        drain = np.pad(drain, 1)
        x0, y0 = x0 - cell, y0 - cell
        fin = np.isfinite(bed)
    ny, nx = bed.shape
    h = cell / 2
    verts, quads, mats = [], [], []
    n = [0]

    def add(v, m):
        k = len(v)
        if not k:
            return
        verts.append(np.asarray(v, float).reshape(-1, 3))
        quads.append(n[0] + np.arange(4 * k).reshape(k, 4))
        mats.append(np.asarray(m, np.int32).reshape(k))
        n[0] += 4 * k

    jj, ii = np.nonzero(fin)
    cx, cy, cz = x0 + ii * cell, y0 + jj * cell, bed[jj, ii]
    top = np.stack([np.stack([cx - h, cy - h, cz], -1), np.stack([cx + h, cy - h, cz], -1),
                    np.stack([cx + h, cy + h, cz], -1), np.stack([cx - h, cy + h, cz], -1)], 1)
    add(top, drain[jj, ii].astype(np.int32))
    zz = np.full_like(cz, zb)
    bot = np.stack([np.stack([cx - h, cy - h, zz], -1), np.stack([cx - h, cy + h, zz], -1),
                    np.stack([cx + h, cy + h, zz], -1), np.stack([cx + h, cy - h, zz], -1)], 1)
    add(bot, np.zeros(len(cz)))
    H = np.pad(np.where(fin, bed, np.nan), 1, constant_values=np.nan)
    V = np.isfinite(H)
    Hz = np.where(V, H, zb)
    # faces between columns i and i + 1 of the padded grid (x = x0 + (i - 0.5) cell)
    a, b = Hz[:, :-1], Hz[:, 1:]
    use = (V[:, :-1] | V[:, 1:]) & (a != b)
    j, i = np.nonzero(use)
    if len(j):
        x = x0 + (i - 0.5) * cell
        y = y0 + (j - 1) * cell
        lo, hi = np.minimum(a[j, i], b[j, i]), np.maximum(a[j, i], b[j, i])
        plus = a[j, i] > b[j, i]                        # the face looks towards the lower side
        q = np.stack([np.stack([x, y - h, lo], -1), np.stack([x, y + h, lo], -1),
                      np.stack([x, y + h, hi], -1), np.stack([x, y - h, hi], -1)], 1)
        q[~plus] = q[~plus][:, ::-1]
        add(q, np.zeros(len(j)))
    a, b = Hz[:-1, :], Hz[1:, :]
    use = (V[:-1, :] | V[1:, :]) & (a != b)
    j, i = np.nonzero(use)
    if len(j):
        y = y0 + (j - 0.5) * cell
        x = x0 + (i - 1) * cell
        lo, hi = np.minimum(a[j, i], b[j, i]), np.maximum(a[j, i], b[j, i])
        plus = a[j, i] > b[j, i]
        q = np.stack([np.stack([x + h, y, lo], -1), np.stack([x - h, y, lo], -1),
                      np.stack([x - h, y, hi], -1), np.stack([x + h, y, hi], -1)], 1)
        q[~plus] = q[~plus][:, ::-1]
        add(q, np.zeros(len(j)))
    if not verts:
        return np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32), np.zeros(0, np.int32)
    return (np.concatenate(verts).astype(np.float32), np.concatenate(quads).astype(np.int32),
            np.concatenate(mats).astype(np.int32))


def _write_mesh(me, verts, quads, mats) -> None:
    me.clear_geometry()
    if len(verts):
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", np.ascontiguousarray(verts, np.float32).reshape(-1))
        me.loops.add(len(quads) * 4)
        me.loops.foreach_set("vertex_index", np.ascontiguousarray(quads, np.int32).reshape(-1))
        me.polygons.add(len(quads))
        me.polygons.foreach_set("loop_start", np.arange(0, len(quads) * 4, 4, dtype=np.int32))
        me.polygons.foreach_set("material_index", np.ascontiguousarray(mats, np.int32))
    me.update()


def _plain_material(name: str, colour, rough: float, metal: float):
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == "material":
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat[TAG] = "material"
    p = next((nd for nd in mat.node_tree.nodes if nd.bl_idname == "ShaderNodeBsdfPrincipled"), None)
    if p is not None:
        p.inputs["Base Color"].default_value = (*colour, 1.0)
        p.inputs["Roughness"].default_value = rough
        p.inputs["Metallic"].default_value = metal
    mat.diffuse_color = (*colour, 1.0)
    return mat


def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _new_object(scene, name: str, role: str, parent=None):
    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    me[TAG] = role
    ob = bpy.data.objects.new(name, me)
    ob[TAG] = role
    _collection(scene).objects.link(ob)
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob


def _key_matrices(ob, mats, start: int) -> None:
    """Linear keys of location and rotation (XYZ) at frames start + k from the (k, 4, 4) matrices."""
    from bpy_extras import anim_utils
    ob.rotation_mode = "XYZ"
    ad = ob.animation_data or ob.animation_data_create()
    act = bpy.data.actions.new(f"FR liquid lab {ob.name}")
    act[TAG] = "action"
    ad.action = act
    slot = act.slots.new(id_type="OBJECT", name=ob.name)
    ad.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    locs, rots = [], []
    prev = None
    for M in mats:
        m = Matrix([list(r) for r in M])
        e = m.to_euler("XYZ", prev) if prev is not None else m.to_euler("XYZ")
        prev = e
        locs.append(tuple(m.translation))
        rots.append(tuple(e))
    frames = start + np.arange(len(mats), dtype=np.float64)
    linear = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
    for path, vals in (("location", np.array(locs)), ("rotation_euler", np.array(rots))):
        for i in range(3):
            fc = cb.fcurves.new(path, index=i)
            pts = fc.keyframe_points
            pts.add(len(frames))
            pts.foreach_set("co", np.stack([frames, vals[:, i]], -1).astype(np.float32).ravel())
            pts.foreach_set("interpolation", np.full(len(frames), linear, np.int32))
            pts.handles_recalc()
    ob.location, ob.rotation_euler = locs[0], rots[0]


# ---------------------------------------------------------------------------
# the build: rigs, bakes, numbers
# ---------------------------------------------------------------------------

def build(scene, folder: str, helpers: int = 0) -> dict:
    """Make the six rigs in ``scene``, work their liquid out into ``<folder>/Liquid lab`` and keep the numbers.
    Returns {case id: {"result", "value", "ok", "text", "seconds"}}."""
    t_all = time.perf_counter()
    cases = core.lab()
    out_dir = os.path.join(folder, FOLDER)
    os.makedirs(out_dir, exist_ok=True)
    start = int(scene.frame_start)
    scene.render.fps, scene.render.fps_base = core.FPS, 1.0
    rig = _plain_material(MAT_BED, (0.22, 0.24, 0.27), 0.4, 0.5)
    dark = _plain_material(MAT_DRAIN, (0.02, 0.02, 0.02), 0.6, 0.0)
    lab = dict(version=VERSION, start=start, folder=FOLDER, cases={})
    out = {}
    for case in cases:
        for c, ch in enumerate(case.charts):
            ob = _new_object(scene, bed_name(case.id, ch.name), "rig")
            ob.hide_select = True
            v, q, m = bed_mesh(ch)
            _write_mesh(ob.data, v, q, m)
            ob.data.materials.append(rig)
            ob.data.materials.append(dark)
            M = case.mats[c]
            if float(np.abs(M - M[:1]).max()) > 0.0:
                _key_matrices(ob, M[: case.frames + 1], start)
            else:
                ob.matrix_world = Matrix([list(r) for r in M[0]])
            sh = _new_object(scene, sheet_name(case.id, ch.name), "sheet", parent=ob)
            sh.hide_select = True
        t0 = time.perf_counter()
        path = os.path.join(out_dir, f"{case.id}.frliquid")
        names = [(ch.name, ch.shape) for ch in case.charts]
        sim = case.liquid(helpers)
        writer = liquid_cache.Writer(path, fingerprint(case.id), names, core.FPS)
        try:
            writer.add(0, [np.where(d > _show(), d, 0.0) for d in (sim.depth(c) for c in range(len(case.charts)))],
                       np.zeros((0, 3)), np.zeros(0), sim.totals())
            for fr in case.steps(sim):
                writer.add(fr.frame, [np.where(d > _show(), d, 0.0)
                                      for d in (sim.depth(c) for c in range(len(case.charts)))],
                           fr.drops, fr.drop_vol, fr.totals)
            res = case.result(sim)
            writer.close()
        except BaseException:
            writer.abort()
            raise
        finally:
            sim.close()
        value, ok, text = case.number(res)
        res = json.loads(json.dumps(res, default=float))
        row = dict(file=os.path.basename(path), path=os.path.abspath(path), frames=case.frames, best=case.best,
                   charts=[ch.name for ch in case.charts], offset=[float(x) for x in case.offset],
                   box=[[float(x) for x in v] for v in case.box()], title=case.title, limit=case.limit,
                   result=res, value=None if value is None else float(value), ok=bool(ok), text=text,
                   seconds=round(time.perf_counter() - t0, 2))
        lab["cases"][case.id] = row
        out[case.id] = row
    scene[PROP] = json.dumps(lab)
    scene.frame_end = start + max(c.frames for c in cases)
    forget()
    draw(scene)
    out["seconds"] = round(time.perf_counter() - t_all, 2)
    return out


def _show() -> float:
    from . import liquid
    return liquid.SHOW


def data(scene) -> dict:
    """The lab kept in the scene, or {}."""
    try:
        d = json.loads(scene.get(PROP, "") or "{}")
        return d if isinstance(d, dict) else {}
    except (TypeError, ValueError):
        return {}


def case_row(scene, cid: str) -> dict:
    return data(scene).get("cases", {}).get(cid, {})


def case_frame(scene, cid: str) -> int:
    """The scene frame that shows a case best."""
    d = data(scene)
    return int(d.get("start", scene.frame_start)) + int(d.get("cases", {}).get(cid, {}).get("best", 0))


# ---------------------------------------------------------------------------
# drawing (from the bakes only)
# ---------------------------------------------------------------------------

def _path(row: dict) -> str:
    """Where a case's bake is: as written, else next to the open project."""
    p = row.get("path", "")
    if p and os.path.isfile(p):
        return p
    if bpy.data.filepath:
        q = os.path.join(os.path.dirname(bpy.data.filepath), FOLDER, row.get("file", ""))
        if os.path.isfile(q):
            return q
    return ""


def _reader(cid: str, row: dict):
    path = _path(row)
    if not path:
        return None
    rd = _READERS.get(path)
    if rd is None:
        rd = liquid_cache.Reader.open(path, fingerprint(cid))
        if rd is None:
            return None
        _READERS[path] = rd
    return rd


def forget() -> None:
    """Close the open bakes (a project is opened, the add-on goes off)."""
    for rd in _READERS.values():
        try:
            rd.close()
        except Exception:  # noqa: BLE001
            pass
    _READERS.clear()


def _drops_object(scene):
    from . import coolant, liquid
    ob = bpy.data.objects.get(OBJ_DROPS)
    if ob is None or ob.get(TAG) != "drops":
        ob = _new_object(scene, OBJ_DROPS, "drops")
        ob.hide_select = True
    mod = ob.modifiers.get("Drops")
    if mod is None:
        mod = ob.modifiers.new("Drops", "NODES")
    ng = coolant._drops_group()
    if mod.node_group is not ng:
        mod.node_group = ng
    mat = liquid.material(None)
    if not ob.material_slots:
        ob.data.materials.append(None)
    slot = ob.material_slots[0]
    if slot.link != "OBJECT":
        slot.link = "OBJECT"
    if slot.material is not mat:
        slot.material = mat
    return ob


def draw(scene, frame: float | None = None) -> dict:
    """Draw every case's liquid at the scene frame ``frame`` (default: the current one). Returns {case id: (cache
    frame, faces, drops)}; {} when the scene has no lab."""
    from . import coolant, liquid
    d = data(scene)
    if not d.get("cases"):
        return {}
    F = float(scene.frame_current) if frame is None else float(frame)
    k0 = int(math.floor(F + 1e-6)) - int(d.get("start", scene.frame_start))
    mat = liquid.material(None)
    shown = {}
    P, S = [], []
    for cid, row in d["cases"].items():
        rd = _reader(cid, row)
        frames = rd.frames if rd is not None else []
        if not frames:
            depths, drops, vols = None, np.zeros((0, 3)), np.zeros(0)
            k = None
        else:
            k = min(max(k0, int(frames[0])), int(frames[-1]))
            depths, drops, vols, _t = rd.read(k)
        faces = 0
        case = _CASES.get(cid)
        if case is None:
            case = _CASES[cid] = core.CASES[cid]()        # (only its beds are read: the same every time)
        for c, name in enumerate(row.get("charts", [])):
            ob = bpy.data.objects.get(sheet_name(cid, name))
            if ob is None or ob.get(TAG) != "sheet":
                continue
            if depths is None:
                v, q = np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32)
            else:
                ch = case.charts[c]
                v, q = liquid.sheet(depths[c], ch.bed, ch.cell, ch.x0, ch.y0)
            liquid._write_sheet(ob.data, v, q)
            liquid._set_material(ob, mat)
            faces += len(q)
        if len(vols):
            P.append(np.asarray(drops, np.float64))
            S.append(np.cbrt(np.maximum(np.asarray(vols, np.float64), 0.0) * 1e-3 * 3.0 / (4.0 * math.pi)))
        shown[cid] = (k, faces, len(vols))
    dob = _drops_object(scene)
    pos = np.concatenate(P) if P else np.zeros((0, 3))
    size = np.concatenate(S) if S else np.zeros(0)
    coolant._write_points(dob.data, pos, np.maximum(size, 0.1 * MM))
    return shown


def _off_main_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


@persistent
def _on_frame_pre(scene, _depsgraph=None):
    if _STATE["guard"] or scene is None or not scene.get(PROP):
        return
    if not bpy.app.background and _off_main_thread() and not scene.render.use_lock_interface:
        return
    _STATE["guard"] += 1
    try:
        draw(scene)
    except Exception as exc:  # noqa: BLE001 - a frame change never fails over the lab
        print("Fresing Render: liquid lab frame update failed:", exc)
    finally:
        _STATE["guard"] -= 1


@persistent
def _on_load(_dummy=None):
    forget()


def register():
    bpy.app.handlers.frame_change_pre.append(_on_frame_pre)
    bpy.app.handlers.load_post.append(_on_load)


def unregister():
    for lst, fn in ((bpy.app.handlers.frame_change_pre, _on_frame_pre), (bpy.app.handlers.load_post, _on_load)):
        if fn in lst:
            lst.remove(fn)
    forget()
