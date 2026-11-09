"""The tool library in Blender (task 0040): the rows of 4 Motion > CNC machine > Tools (``scene.fresing.cnc.tools``).

A row has a T number, a type and its sizes (``core/tools.Spec``); its **shape** is one of three:

* drawn from the sizes (a generated mesh: flutes, inserts, teeth, and a holder if one is picked),
* a manufacturer's **STEP** model of the tool (or tool + holder), read with the app's own STEP reader into a mesh
  kept in the project (``row.step_mesh``), its tip and axis found from its shape (``row.tip``, ``row.axis``),
* a **part of the model** (``row.obj``, e.g. a tool standing in the carousel).

Whatever the shape, the tool **cuts with its sizes**: a part or STEP model only fills the sizes in as a first
guess (outer diameter over the flutes), and the owner can correct them. The copies shown in the spindle at a tool
change are made by ``gcode.tool_objects``; each carries its sizes (``fr_spec``), and milling cuts with the tool that
is in the spindle at each frame (``machining.cut_items``).
"""

from __future__ import annotations

import json
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

from ..core import tools as core
from . import build

MM = 0.001
TAG = "fr_cnc"
STEP_PREFIX = "FR tool STEP "
_FIELDS = core.spec_fields()


def settings(scene):
    return scene.fresing.cnc


def rows(scene) -> list:
    return list(settings(scene).tools)


def row_of(scene, number: int):
    return next((t for t in settings(scene).tools if t.number == number), None)


def label(row) -> str:
    return f"T{row.number} {row.name or core.describe(spec_of(row))}"


# ---------------------------------------------------------------------------
# rows <-> sizes
# ---------------------------------------------------------------------------

def spec_of(row) -> core.Spec:
    """The row's sizes (metres, degrees); sizes left at 0 are filled in from the type."""
    s = core.Spec(number=row.number, name=row.name, kind=row.kind, diameter=row.diameter, corner=row.corner,
                  angle=math.degrees(row.angle), flute_length=row.flute_length, flutes=row.flutes,
                  inserts=row.inserts, insert_size=row.insert_size, lead_angle=math.degrees(row.lead_angle),
                  pitch=row.pitch, width=row.width, neck=row.neck, shank=row.shank, stick_out=row.length,
                  holder=row.holder, holder_diameter=row.holder_diameter, holder_length=row.holder_length,
                  gauge=row.gauge_length, pocket=row.pocket, note=row.note, source=row.source)
    return core.resolved(s)


def fill(row, spec: core.Spec, number: bool = False, name: bool = True, new_shape: bool = False) -> None:
    """Put a Spec's sizes into a row (without starting an update for every field). ``new_shape``: the row got
    another part or STEP model, so a gauge length typed for the old one goes too."""
    s = core.resolved(spec)
    row["_busy"] = True
    try:
        if number:
            row.number = s.number
        if name and s.name:
            row.name = s.name
        row.kind = s.kind
        row.diameter = max(s.diameter, 1e-5)
        row.length = max(s.stick_out, 1e-4)
        row.corner = s.corner if s.kind == "BULL" else row.corner
        if s.kind in ("VEE", "DRILL"):
            row.angle = math.radians(min(max(s.angle, 10.0), 175.0))
        row.flute_length = s.flute_length
        row.flutes = s.flutes
        row.inserts = s.inserts if s.kind == "FACE" else 0
        row.insert_size = s.insert_size if s.kind == "FACE" else 0.0
        row.lead_angle = math.radians(min(max(s.lead_angle or 90.0, 10.0), 90.0))
        row.pitch = s.pitch if s.kind == "THREAD" else 0.0
        row.width = s.width if s.kind == "SLOT" else 0.0
        row.neck = s.neck if s.kind == "SLOT" else 0.0
        row.shank = s.shank
        row.holder = s.holder
        row.holder_diameter = s.holder_diameter if s.holder != "NONE" else 0.0
        row.holder_length = s.holder_length if s.holder != "NONE" else 0.0
        if s.gauge > 0 or new_shape:
            row.gauge_length = s.gauge
        if s.pocket:
            row.pocket = s.pocket
        row.note = s.note
        row.source = s.source or row.source
    finally:
        del row["_busy"]


def row_changed(scene, row=None) -> None:
    """Sizes or the type of a row changed: the cut follows (a built animation shows the new shape at its next
    build; the copies already there are made again now)."""
    if row is not None and row.get("_busy"):
        return
    if row is not None and not row.get("_kind_seen") == row.kind:
        _type_changed(row)
    try:
        refresh_copies(scene)
    except Exception as exc:                       # never break the panel over a preview
        print("Fresing Render: tool copies could not be updated:", exc)
    from . import machining
    if machining.is_active(scene):
        machining.tool_changed(scene)
    from . import gcode
    if gcode.settings(scene).changer == "ATC":        # pockets and lengths set how long the changes take (0041)
        gcode.setup_changed(scene)


def _type_changed(row) -> None:
    """A new type: the sizes only that type has start from what that type usually has."""
    old = row.get("_kind_seen")
    row["_kind_seen"] = row.kind
    if old is None or old == row.kind:
        return
    d = core.default(row.kind, row.number)
    row["_busy"] = True
    try:
        if row.kind in ("VEE", "DRILL"):
            row.angle = math.radians(d.angle)
        row.flute_length = 0.0
        row.flutes = 0
        if row.kind == "FACE":
            row.lead_angle = math.radians(d.lead_angle)
    finally:
        del row["_busy"]


# ---------------------------------------------------------------------------
# list operations
# ---------------------------------------------------------------------------

def next_number(scene) -> int:
    used = {t.number for t in settings(scene).tools}
    n = 1
    while n in used:
        n += 1
    return n


def add_row(scene, kind: str = "FLAT", number: int | None = None, spec: core.Spec | None = None):
    c = settings(scene)
    n = next_number(scene) if number is None else number
    row = c.tools.add()
    row["_busy"] = True
    row.number = n
    row.source = "typed"
    del row["_busy"]
    fill(row, spec or core.default(kind, n))
    row["_kind_seen"] = row.kind
    c.tools_index = len(c.tools) - 1
    row_changed(scene)
    return row


def copy_row(scene, index: int):
    c = settings(scene)
    if not 0 <= index < len(c.tools):
        return None
    src = c.tools[index]
    spec = spec_of(src)
    keep = {"obj": src.obj, "uid": src.uid, "step_file": src.step_file, "step_mesh": src.step_mesh,
            "tip": tuple(src.tip), "axis": tuple(src.axis), "place": src.place}
    row = add_row(scene, spec.kind, next_number(scene), spec)
    row["_busy"] = True
    for k, v in keep.items():
        if k != "obj" or v is None:
            setattr(row, k, v)
    del row["_busy"]
    row.name = src.name + " (copy)" if src.name else ""
    return row


def remove_row(scene, index: int) -> None:
    c = settings(scene)
    if 0 <= index < len(c.tools):
        c.tools.remove(index)
        c.tools_index = max(0, min(c.tools_index, len(c.tools) - 1))
    row_changed(scene)


def sort_rows(scene) -> None:
    """Sort the list by T number."""
    c = settings(scene)
    cur = c.tools[c.tools_index].number if 0 <= c.tools_index < len(c.tools) else None
    for i in range(len(c.tools)):
        best = min(range(i, len(c.tools)), key=lambda k: (c.tools[k].number, k))
        if best != i:
            c.tools.move(best, i)
    if cur is not None:
        c.tools_index = next((i for i, t in enumerate(c.tools) if t.number == cur), 0)


def merge_specs(scene, specs: list) -> tuple[int, int]:
    """Rows for tools read from a file: new T numbers are added, rows with the same T number get the sizes (their
    part or STEP model stays). Returns (added, updated)."""
    added = updated = 0
    for s in specs:
        row = row_of(scene, s.number)
        if row is None:
            row = add_row(scene, s.kind, s.number, s)
            row["_busy"] = True
            row.source = s.source or "file"
            del row["_busy"]
            added += 1
        else:
            fill(row, s)
            row["_kind_seen"] = row.kind
            updated += 1
    sort_rows(scene)
    row_changed(scene)
    return added, updated


def read_file(scene, path: str) -> dict:
    """Read a Fusion tool library (.json, .tools) or a LinuxCNC tool table (.tbl) into the list."""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as fh:
        data = fh.read()
    if ext == ".tbl" or (not data.lstrip().startswith((b"{", b"[", b"PK")) and b"T" in data[:200]):
        res = core.read_linuxcnc(data.decode("utf-8", errors="replace"))
        what = "LinuxCNC tool table"
    else:
        res = core.read_fusion(data)
        what = "Fusion tool library"
    added, updated = merge_specs(scene, res.tools)
    return {"what": what, "added": added, "updated": updated, "notes": res.notes,
            "read": len(res.tools)}


def from_program(scene, prog) -> int:
    """A row for every T number the program uses (or names in a tool comment) that has none. Returns how many."""
    added = 0
    for n in sorted(set(prog.tool_numbers()) | set(prog.tools)):
        if n <= 0 or row_of(scene, n) is not None:
            continue
        info = prog.tools.get(n)
        if info is not None:
            spec = core.from_info(info)
        else:
            spec = core.default("FLAT", n)
            spec.note = "the program gives no size: check the type and the sizes"
        spec.number = n
        row = add_row(scene, spec.kind, n, spec)
        row["_busy"] = True
        row.source = spec.source or "program"
        del row["_busy"]
        added += 1
    sort_rows(scene)
    return added


def missing(scene, prog) -> list:
    """[(T number, first line)] of tools the program puts in the spindle that are not in the list. Nothing when
    the list is empty and the program uses one tool only (the part in the spindle is that tool)."""
    used = {}
    for m in prog.moves:
        if m.kind == "TOOL" and m.tool and m.tool not in used:
            used[m.tool] = m.line
    if not used or (not settings(scene).tools and len(used) <= 1):
        return []
    return [(n, used[n]) for n in sorted(used) if row_of(scene, n) is None]


def checks(scene) -> list:
    """Warnings about the list: sizes that look wrong, two rows with one T number."""
    out = []
    seen = set()
    travel = machine_travel(scene)
    for row in settings(scene).tools:
        if row.number in seen:
            out.append(f"T{row.number} is in the list twice: the first row is used")
        seen.add(row.number)
        out += core.checks(spec_of(row), travel)
    return out


def machine_travel(scene):
    """(X, Y, Z) travel in metres from the axis joints' limits, None for an axis without limits."""
    c = settings(scene)
    js = scene.fresing.joints
    out = []
    for name in (c.x_joint, c.y_joint, c.z_joint):
        j = js.get(name) if name else None
        if j is None or not getattr(j, "use_limits", False) or j.kind != "SLIDE":
            out.append(None)
            continue
        out.append(abs(float(j.slide_max) - float(j.slide_min)))
    return out if any(out) else None


# ---------------------------------------------------------------------------
# shapes: a part of the model, a STEP model, or drawn from the sizes
# ---------------------------------------------------------------------------

def use_part(scene, row, ob, fill_sizes: bool = True) -> None:
    """The row is shown by a part of the model; its sizes are read from the part's shape as a first guess."""
    from . import gcode
    tip, axis, _tool = gcode._rest_tip(ob)           # raises RuntimeError when it has no shape
    row["_busy"] = True
    row.obj = ob
    row.uid = ob.get(build.PROP_UID, "")
    del row["_busy"]
    if fill_sizes:
        guess = guess_from(ob.data, tip, axis)
        guess.number = row.number
        guess.source = "part"
        fill(row, guess, name=not row.name, new_shape=True)
        row["_kind_seen"] = row.kind
    row_changed(scene, None)


def guess_from(me, tip, axis) -> core.Spec:
    """A row's sizes from a tool's mesh, its tip and axis (in the mesh's space)."""
    from ..core import machining as mcore
    pts = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", pts)
    pts = pts.reshape(-1, 3)
    me.calc_loop_triangles()
    tris = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", tris)
    prof, _z0, _z1 = mcore.profile_from_points(pts, np.array(tip), np.array(axis), tris.reshape(-1, 3))
    return core.from_outline(prof)


def import_step(scene, row, path: str, timeout: float = 120.0) -> core.Spec:
    """Read a tool's STEP model with the app's STEP reader into a mesh kept in the project; find its axis and tip
    (the narrower end, or the end with the flutes); fill the row's sizes from it. Returns the guessed sizes."""
    from ..importer.runner import ImportJob
    from .ops_import import cache_root
    path = bpy.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    job = ImportJob(path, "normal", cache_root())
    if not job.cached:
        job.start()
        t0 = time.time()
        while not job.poll():
            if time.time() - t0 > timeout:
                job.cancel()
                raise RuntimeError("Reading the STEP file took too long")
            time.sleep(0.05)
        if job.error:
            raise RuntimeError(job.error)
    info, arrays = build.load_cache(job.cache_dir)
    verts, tris, axes, axis_faces = combine_cache(info, arrays)
    if len(tris) == 0:
        raise RuntimeError("The STEP file holds no shape")
    me = bpy.data.meshes.new(STEP_PREFIX + os.path.splitext(os.path.basename(path))[0])
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).reshape(-1))
    me.loops.add(len(tris) * 3)
    me.loops.foreach_set("vertex_index", tris.astype(np.int32).reshape(-1))
    me.polygons.add(len(tris))
    me.polygons.foreach_set("loop_start", np.arange(0, len(tris) * 3, 3, dtype=np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(30))
    if axes:
        me["fr_axes"] = [v for a in axes for v in a]
        me["fr_axis_faces"] = axis_faces
    me[TAG] = "tool_step"
    tip, axis = tip_and_axis(me)
    old = row.step_mesh
    row["_busy"] = True
    row.step_file = path
    row.step_mesh = me
    row.tip = tip
    row.axis = axis
    row.obj = None
    row.uid = ""
    del row["_busy"]
    if old is not None and old is not me and old.users == 0:
        bpy.data.meshes.remove(old)
    guess = guess_from(me, tip, axis)
    guess.number = row.number
    guess.source = "STEP"
    fill(row, guess, name=False, new_shape=True)
    if not row.name:
        row.name = os.path.splitext(os.path.basename(path))[0][:60]
    row["_kind_seen"] = row.kind
    row_changed(scene, None)
    return guess


def combine_cache(info: dict, arrays) -> tuple:
    """Every part of a read STEP file in one mesh (the file's own coordinates, metres): (verts, tris, axes,
    axis_faces). ``axes`` are the round faces' axes (origin, direction, radius) moved along."""
    nodes = info["nodes"]
    mats = []
    for n in nodes:
        m = np.array(n.get("matrix") or np.eye(4).tolist(), dtype=np.float64)
        if n["parent"] >= 0:
            m = mats[n["parent"]] @ m
        mats.append(m)
    vs, ts, axes, faces = [], [], [], []
    off = toff = 0
    for n, m in zip(nodes, mats):
        if n["kind"] != "part" or n.get("mesh", -1) < 0 or f"p{n['mesh']}" not in arrays:
            continue
        mid = n["mesh"]
        p = np.asarray(arrays[f"p{mid}"], dtype=np.float64).reshape(-1, 3)
        t = np.asarray(arrays[f"t{mid}"], dtype=np.int64).reshape(-1, 3)
        vs.append(p @ m[:3, :3].T + m[:3, 3])
        meta = info["meshes"][mid]
        for a in meta.get("axes") or []:
            o = np.array(a[:3]) @ m[:3, :3].T + m[:3, 3]
            d = np.array(a[3:6]) @ m[:3, :3].T
            axes.append(list(o) + list(d) + [a[6] if len(a) > 6 else 0.0])
        af = meta.get("axis_faces") or []
        base = len(axes) - len(meta.get("axes") or [])
        for k in range(0, len(af) - 2, 3):          # (first triangle, count, axis) of each round face
            faces += [af[k] + toff, af[k + 1], af[k + 2] + base]
        ts.append(t + off)
        off += len(p)
        toff += len(t)
    if not vs:
        return np.zeros((0, 3)), np.zeros((0, 3), np.int64), [], []
    return np.concatenate(vs), np.concatenate(ts), axes, faces


def tip_and_axis(me) -> tuple:
    """Tip and axis (from the tip into the holder) of a tool's mesh in its own space, along its main axis.

    * A model along X with the file's origin on its axis (ToolsUnited / Hoffmann layout: the gauge line or the
      shank's end at the origin, task 0049): the tip is on the side of the origin the tool reaches out to – the
      only side, or, when the origin lies inside (a holder: taper on one side, flange and nose on the other), the
      side with the flange right next to the origin.
    * Else the end on the file's origin (where other manufacturers put the tip), else the narrower end, else (both
      ends as wide) the end with the flutes (more detail)."""
    from . import machining
    ob = bpy.data.objects.new("FR tool probe", me)
    try:
        a = machining.detect(ob, toward=None, flip=False)
        b = machining.detect(ob, toward=None, flip=True)
    finally:
        bpy.data.objects.remove(ob)
    pts = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", pts)
    pts = pts.reshape(-1, 3)

    def end_width(info):
        prof = info["profile"]
        L = prof[-1][0] if prof else 0.0
        return max((r for z, r in prof if z <= 0.15 * L + 1e-9), default=0.0)

    wa, wb = end_width(a), end_width(b)
    oa, ob_ = np.linalg.norm(np.array(a["tip"])), np.linalg.norm(np.array(b["tip"]))
    gauge = _gauge_side(pts, a)
    if gauge is not None:
        pick = a if gauge else b
    elif min(oa, ob_) < 1 * MM <= max(oa, ob_):
        pick = a if oa < ob_ else b                  # manufacturers put the tip on the file's origin
    elif abs(wa - wb) > 0.2 * max(wa, wb):
        pick = a if wa < wb else b
    else:
        centre = pts.mean(axis=0)                   # the flutes hold most of the vertices
        da = np.linalg.norm(np.array(a["tip"]) - centre)
        db = np.linalg.norm(np.array(b["tip"]) - centre)
        pick = a if da <= db else b
    return tuple(pick["tip"]), tuple(pick["axis"])


def _gauge_side(pts, info):
    """For a model along X with the origin on its axis (the gauge line at the origin): True when ``info``'s tip
    is the tip, False when the other end is; None when the model is not laid out like that."""
    axis = np.array(info["axis"], dtype=float)
    axis /= np.linalg.norm(axis) or 1.0
    if abs(axis[0]) < 0.999:
        return None
    tip = np.array(info["tip"], dtype=float)
    z = (pts - tip) @ axis                          # 0 at this tip, growing towards the other end
    z0 = float(-tip @ axis)                        # the origin along the axis
    radial = -tip - axis * z0                      # the origin's distance from the axis
    length = float(z.max())
    if np.linalg.norm(radial) > 1 * MM or not -1 * MM <= z0 <= length + 1 * MM:
        return None
    prof = np.array(info["profile"], dtype=float).reshape(-1, 2)    # (z from this tip, widest r): between vertices
    reach_tip, reach_far = z0, length - z0
    if reach_far < 1 * MM:                          # the origin at the other end (a shank's end): this is the tip
        return True
    if reach_tip < 1 * MM:
        return False
    def width(lo, hi):                              # widest outline between two heights
        out = 0.0
        for (za, ra), (zb, rb) in zip(prof[:-1], prof[1:]):
            if zb <= za or zb < lo or za > hi:
                continue
            for zq in (max(za, lo), min(zb, hi)):
                out = max(out, ra + (rb - ra) * (zq - za) / (zb - za))
        return out

    wt = width(z0 - 8 * MM, z0 - 0.5 * MM)          # between the origin and this tip
    wf = width(z0 + 0.5 * MM, z0 + 8 * MM)
    if abs(wt - wf) > 1 * MM:                       # the flange is next to the gauge line, on the tool's side
        return wt > wf
    return reach_tip >= reach_far                   # else the side it reaches further out to


def flip_step(scene, row) -> None:
    """The STEP model's tip is at the other end."""
    if row.step_mesh is None:
        return
    pts = np.empty(len(row.step_mesh.vertices) * 3, dtype=np.float64)
    row.step_mesh.vertices.foreach_get("co", pts)
    pts = pts.reshape(-1, 3)
    d = np.array(row.axis, dtype=float)
    d /= np.linalg.norm(d) or 1.0
    z = (pts - np.array(row.tip)) @ d
    new_tip = np.array(row.tip) + d * float(z.max())
    row["_busy"] = True
    row.tip = tuple(new_tip.tolist())
    row.axis = tuple((-d).tolist())
    del row["_busy"]
    guess = guess_from(row.step_mesh, row.tip, row.axis)
    guess.number = row.number
    guess.source = "STEP"
    fill(row, guess, name=False)
    row["_kind_seen"] = row.kind
    row_changed(scene, None)


def clear_shape(scene, row) -> None:
    """Back to the shape drawn from the sizes."""
    old = row.step_mesh
    row["_busy"] = True
    row.obj = None
    row.uid = ""
    row.step_mesh = None
    row.step_file = ""
    del row["_busy"]
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    row_changed(scene, None)


def shape_text(row) -> str:
    if row.obj is not None:
        return f"part '{row.obj.get(build.PROP_NAME, row.obj.name)}'"
    if row.step_mesh is not None:
        return f"STEP model {os.path.basename(row.step_file) or row.step_mesh.name}"
    return "drawn from the sizes" + ("" if row.holder == "NONE" else f", {core.HOLDERS[row.holder]} holder")


def drawn_mesh(spec: core.Spec, name: str) -> bpy.types.Mesh:
    """A new mesh of a tool drawn from its sizes (tip at the origin, along +Z); faces of the holder use the second
    material slot."""
    v, t, part = core.tool_mesh(spec)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.astype(np.float32).reshape(-1))
    me.loops.add(len(t) * 3)
    me.loops.foreach_set("vertex_index", t.astype(np.int32).reshape(-1))
    me.polygons.add(len(t))
    me.polygons.foreach_set("loop_start", np.arange(0, len(t) * 3, 3, dtype=np.int32))
    me.polygons.foreach_set("material_index", part.astype(np.int32))
    me.update(calc_edges=True)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(35))
    me[TAG] = "tool"
    me["fr_spec"] = spec_json(spec)
    return me


def spec_json(spec: core.Spec) -> str:
    return json.dumps({k: getattr(spec, k) for k in _FIELDS})


def spec_from_json(text: str) -> core.Spec | None:
    try:
        d = json.loads(text)
    except (TypeError, ValueError):
        return None
    return core.resolved(core.Spec(**{k: v for k, v in d.items() if k in _FIELDS}))


def tool_materials(scene, spindle) -> tuple:
    """(tool material, holder material): the spindle tool's own, and a darker steel for holders."""
    tool_mat = spindle.active_material if spindle is not None else None
    holder = bpy.data.materials.get("FR tool holder")
    if holder is None:
        holder = bpy.data.materials.new("FR tool holder")
        holder[TAG] = "holder"
        holder.diffuse_color = (0.18, 0.19, 0.2, 1.0)
        holder.metallic = 1.0
        holder.roughness = 0.35
        try:
            bsdf = holder.node_tree.nodes.get("Principled BSDF") if holder.node_tree else None
            if bsdf is not None:
                bsdf.inputs["Base Color"].default_value = (0.18, 0.19, 0.2, 1.0)
                bsdf.inputs["Metallic"].default_value = 1.0
                bsdf.inputs["Roughness"].default_value = 0.35
        except Exception:
            pass
    if tool_mat is None:
        tool_mat = bpy.data.materials.get("FR tool steel")
        if tool_mat is None:
            tool_mat = bpy.data.materials.new("FR tool steel")
            tool_mat[TAG] = "steel"
            tool_mat.diffuse_color = (0.75, 0.76, 0.78, 1.0)
            tool_mat.metallic = 1.0
            tool_mat.roughness = 0.25
    return tool_mat, holder


def refresh_copies(scene) -> None:
    """Copies already in the scene (a built animation) get the shape of their row's sizes now."""
    for ob in [o for o in bpy.data.objects if o.get(TAG) == "tool" and "fr_cnc_t" in o]:
        row = row_of(scene, int(ob["fr_cnc_t"]))
        if row is None:
            continue
        spec = spec_of(row)
        ob["fr_spec"] = spec_json(spec)
        me = ob.data
        if me is None or me.get(TAG) != "tool" or row.obj is not None or row.step_mesh is not None:
            continue
        if me.get("fr_spec") == spec_json(spec):
            continue
        new = drawn_mesh(spec, me.name)
        for m in me.materials:
            new.materials.append(m)
        ob.data = new
        if me.users == 0:
            bpy.data.meshes.remove(me)


def world_tip(ob) -> Vector:
    from . import gcode
    return ob.matrix_world @ gcode._rest_tip(ob)[0]
