"""Tool changes (task 0041): manual changes with an optional hand, and an automatic tool changer with pockets.

Set-up (4 Motion > CNC machine > Tool changes, ``scene.fresing.cnc``):

    changer       MANUAL or ATC
    change_mode   where a manual change happens: where the head is, Z up only, or the change position
    pockets       rows: a number, the part the pocket is on (it follows the part, so a turning carousel takes its
                  pockets round), the point where a tool's gauge line sits and the way the tool points (both in the
                  part's own space). Shown as small arrows "FR pocket N" (children of the part).
    carousel      the rotate joint of the carousel (empty: a rack, the head goes to each pocket); ``station`` is
                  the pocket at the spindle when the carousel is as in CAD.

Which tool stands in which pocket: its tool list row's Pocket, else the pocket nearest to the row's part (a tool of
the CAD model standing in the carousel), else the pocket with its T number. Place 'Bench' tools have none.

The bake (``tool_keys``): the tool in the spindle is the spindle part or a copy of the tool (gcode.tool_objects); a
tool in a pocket is its CAD part, or a copy hanging on the pocket's part ("FR tool Tn pocket"), visible from the first
frame. At each change the old tool leaves the spindle at the drop moment (into its pocket) and the new one is in at
the swap moment; the carousel's joint gets keys for every turn. The hand ("FR hand", a gloved hand made by the app)
is a child of the spindle's carrier; it carries a copy of the tool it holds.

Stations (core/toolchange.py): where the reference tool's tip is (machine mm) when the spindle's gauge line sits in a
pocket, worked out from the pocket's point now and the axes that move the tool.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import toolchange as TC
from . import build, gcode, joints

MM = 0.001
POCKET_TAG = "pocket"
HAND_NAME = "FR hand"
GRIP_BELOW_GAUGE = 0.03          # m: the hand holds the holder this far below the gauge line
PULL = 0.07                      # m: the hand pulls the tool this far down out of the spindle
OUT = (0.0, -0.28, -0.08)        # m: where the hand waits, from its grip (towards the front, a little lower)
NEAR_POCKET = 0.06               # m: a CAD tool this close to a pocket stands in it


def settings(scene):
    return scene.fresing.cnc


# ---------------------------------------------------------------------------
# pockets
# ---------------------------------------------------------------------------

def carousel(scene):
    """The carousel's rotate joint, or None."""
    c = settings(scene)
    j = scene.fresing.joints.get(c.carousel_joint) if c.carousel_joint else None
    if j is None or j.kind != "ROTATE" or not joints.is_valid(j):
        return None
    return j


def pocket_world(p) -> tuple[Vector, Vector] | None:
    """(gauge point, direction from tip into holder) of a pocket in the world now, or None (its part is gone)."""
    ob = p.obj
    if ob is None or ob.name not in bpy.data.objects:
        return None
    mw = ob.matrix_world
    d = mw.to_3x3() @ Vector(p.dir)
    if d.length < 1e-9:
        d = Vector((0, 0, 1))
    return mw @ Vector(p.loc), d.normalized()


def pocket_frame(p) -> Matrix | None:
    """The pocket's frame in the world: origin at the gauge point, Z from the tool's tip into its holder."""
    w = pocket_world(p)
    if w is None:
        return None
    pt, d = w
    return Matrix.Translation(pt) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()


def spindle_axis(scene) -> Vector:
    """The spindle tool's direction from its tip into the spindle (world), +Z when not set up."""
    c = settings(scene)
    if c.tool is None:
        return Vector((0, 0, 1))
    try:
        _tip, axis, _t = gcode._rest_tip(c.tool)
    except Exception:
        return Vector((0, 0, 1))
    return (c.tool.matrix_world.to_3x3() @ axis).normalized()


def add_pocket(scene, ob, world: Vector, number: int = 0):
    """A pocket on part ``ob`` at ``world``; the tool points like the spindle's tool. Returns the row."""
    c = settings(scene)
    inv = ob.matrix_world.inverted()
    p = c.pockets.add()
    p["_busy"] = True
    p.number = number or (max((x.number for x in c.pockets if x != p), default=0) + 1)
    p.obj = ob
    p.uid = ob.get(build.PROP_UID, "")
    p.loc = inv @ world
    d = inv.to_3x3() @ spindle_axis(scene)
    p.dir = d.normalized() if d.length > 1e-9 else Vector((0, 0, 1))
    del p["_busy"]
    c.pockets_index = len(c.pockets) - 1
    pockets_changed(scene)
    return p


def fill_carousel(scene) -> str:
    """Pockets evenly round the carousel's axis, from pocket 1 (or the first pocket): '' or why not."""
    c = settings(scene)
    j = carousel(scene)
    if j is None:
        return "Pick the carousel's rotate joint first"
    if not c.pockets:
        return "Click pocket 1 on the carousel first"
    first = next((p for p in c.pockets if p.number == 1), c.pockets[0])
    w = pocket_world(first)
    if w is None:
        return "Pocket 1's part is gone: click it again"
    if not gcode._carries(j, first.obj):
        return f"Pocket {first.number} is not on a part the joint '{j.name}' turns: click it on the carousel"
    origin, axis = joints.axis_world(j)
    pt, d = w
    n = max(2, int(c.pocket_count))
    sign = -1.0 if c.pockets_reverse else 1.0
    ob, uid, num0 = first.obj, first.uid, first.number
    c.pockets.clear()
    inv = ob.matrix_world.inverted()
    for k in range(n):
        rot = Matrix.Rotation(sign * TC.TURN * k / n, 4, axis)
        at = origin + rot.to_3x3() @ (pt - origin)
        dd = rot.to_3x3() @ d
        p = c.pockets.add()
        p["_busy"] = True
        p.number = num0 + k
        p.obj, p.uid = ob, uid
        p.loc = inv @ at
        p.dir = (inv.to_3x3() @ dd).normalized()
        del p["_busy"]
    c.pockets_index = 0
    pockets_changed(scene)
    return ""


def remove_markers() -> None:
    for o in [o for o in bpy.data.objects if o.get(gcode.TAG) == POCKET_TAG]:
        bpy.data.objects.remove(o)


def show_markers(scene) -> None:
    """Small arrows "FR pocket N" at the pockets (children of their parts; not in renders)."""
    remove_markers()
    c = settings(scene)
    if not c.pockets:
        return
    col = gcode._collection(scene)
    for p in c.pockets:
        fr = pocket_frame(p)
        if fr is None:
            continue
        ob = bpy.data.objects.new(f"FR pocket {p.number}", None)
        ob.empty_display_type = "SINGLE_ARROW"
        ob.empty_display_size = 30 * MM
        ob.show_name = True
        ob.hide_render = True
        ob.hide_select = True
        ob[gcode.TAG] = POCKET_TAG
        ob[build.PROP_KIND] = "cnc"
        col.objects.link(ob)
        gcode._place(ob, p.obj, fr)


def pockets_changed(scene) -> None:
    try:
        show_markers(scene)
    except Exception as exc:                           # never break a click over the markers
        print("Fresing Render: pocket markers:", exc)
    gcode.setup_changed(scene)


def problems(scene) -> list[str]:
    """What is wrong with the changer's set-up, in plain words."""
    c = settings(scene)
    out = []
    if c.changer != "ATC":
        return out
    if c.carousel_joint and carousel(scene) is None:
        out.append(f"'{c.carousel_joint}' is not a rotate joint: pick the carousel's rotate joint")
    nums = [p.number for p in c.pockets]
    dup = sorted({n for n in nums if nums.count(n) > 1})
    if dup:
        out.append("Two pockets have the number " + ", ".join(str(n) for n in dup))
    gone = [p.number for p in c.pockets if pocket_world(p) is None]
    if gone:
        out.append("The part of pocket " + ", ".join(str(n) for n in gone) + " is gone: click it again")
    j = carousel(scene)
    if j is not None:
        loose = [p.number for p in c.pockets if p.obj is not None and not gcode._carries(j, p.obj)]
        if loose:
            out.append("Pocket " + ", ".join(str(n) for n in loose[:6]) + f" is not on a part '{j.name}' turns")
        if c.pockets and c.station not in nums:
            out.append(f"The change station is pocket {c.station}, which does not exist")
    if c.pockets and c.tools:
        where = tool_pockets(scene, [t.number for t in c.tools])
        for pk in sorted(set(where.values())):
            ts = sorted(n for n, x in where.items() if x == pk)
            if len(ts) > 1:
                out.append(" and ".join(f"T{n}" for n in ts) + f" all stand in pocket {pk}: give them their own "
                           "Pocket in Tools (fold 'Shank, holder sizes, place')")
    return out


# ---------------------------------------------------------------------------
# which tool stands where, and the stations
# ---------------------------------------------------------------------------

def _row(scene, n):
    return gcode.tool_entry(scene, n)


def start_tool(scene) -> int:
    """The tool in the spindle when a program starts: the row of the spindle's part, else a row placed 'Spindle'."""
    c = settings(scene)
    row = next((t for t in c.tools if t.obj is not None and t.obj is c.tool), None)
    if row is None:
        row = next((t for t in c.tools if t.place == "SPINDLE"), None)
    return row.number if row is not None else 0


def _part_segment(ob):
    tip, axis, _t = gcode._rest_tip(ob)
    mw = ob.matrix_world
    a = mw @ tip
    d = (mw.to_3x3() @ axis).normalized()
    co = gcode._world_points(ob)
    proj = (co - np.array(a)) @ np.array(d)
    return a, d, float(proj.max()) if len(proj) else 0.0


def tool_pockets(scene, numbers) -> dict:
    """{T: pocket number} of the tools that stand in a pocket that exists."""
    c = settings(scene)
    have = {p.number: p for p in c.pockets if pocket_world(p) is not None}
    out = {}
    for n in numbers:
        row = _row(scene, n)
        if row is not None and row.place == "BENCH":
            continue
        if row is not None and row.pocket > 0:
            if row.pocket in have:
                out[n] = row.pocket
            continue
        if row is not None and row.obj is not None and row.obj is not c.tool and have:
            try:
                a, d, length = _part_segment(row.obj)
            except Exception:
                a = None
            if a is not None:
                best, dist = None, None
                for num, p in have.items():
                    pt = pocket_world(p)[0]
                    s = min(max((pt - a).dot(d), 0.0), length)
                    dd = (pt - (a + d * s)).length
                    if dist is None or dd < dist:
                        best, dist = num, dd
                if best is not None and dist < NEAR_POCKET:
                    out[n] = best
                    continue
        if n in have:
            out[n] = n
    return out


def ref_gauge(scene, mach) -> float:
    """From the spindle tool's tip to the spindle's gauge line (m): its row's gauge length, else the part's length."""
    from ..core import tools as tcore
    from . import tools
    c = settings(scene)
    row = next((t for t in c.tools if t.obj is not None and t.obj is mach.tool), None)
    if row is not None:
        return tcore.gauge_length(tools.spec_of(row))
    try:
        return _part_segment(mach.tool)[2]
    except Exception:
        return 0.05


def stations(scene, mach) -> tuple[dict, dict, list]:
    """({pocket: (x, y, z) machine mm, None for an axis that moves the workpiece}, {pocket: carousel value that brings
    it to the station}, notes)."""
    c = settings(scene)
    notes = []
    pockets = {p.number: pocket_world(p) for p in c.pockets}
    pockets = {n: w for n, w in pockets.items() if w is not None}
    if not pockets:
        return {}, {}, notes
    tip_l, axis_l, _t = gcode._rest_tip(mach.tool)
    mw = mach.tool.matrix_world
    tip = mw @ tip_l
    axis = (mw.to_3x3() @ axis_l).normalized()
    gauge_now = tip + axis * ref_gauge(scene, mach)
    m_now = mach.machine_of(mach.values)
    rot_t = mach.rot.transposed()

    def station_of(world: Vector, n: int):
        d = rot_t @ (world - gauge_now)
        out = []
        for i in range(3):
            if mach.moves_tool[i]:
                out.append(m_now[i] + d[i] / MM)
            else:
                out.append(None)
                if abs(d[i]) > 1 * MM:
                    notes.append(f"Pocket {n}: the axis {'XYZ'[i]} moves the workpiece, so the spindle cannot "
                                 "reach the pocket exactly")
        return tuple(out)

    j = carousel(scene)
    if j is None:
        return {n: station_of(w[0], n) for n, w in pockets.items()}, {}, notes
    st = c.station if c.station in pockets else min(pockets)
    origin, d = joints.axis_world(j)
    v_now = joints.get_value(j)
    s_now = pockets[st][0]
    s0 = origin + Matrix.Rotation(-v_now, 3, d) @ (s_now - origin)        # the station: pocket st at value 0
    ref = s0 - origin
    ref = ref - d * ref.dot(d)
    st_mm = station_of(s0, st)
    values = {}
    for n, (pt, _dir) in pockets.items():
        v = pt - origin
        v = v - d * v.dot(d)
        if ref.length < 1e-9 or v.length < 1e-9:
            values[n] = v_now
            continue
        ang = math.atan2(ref.cross(v).dot(d), ref.dot(v))               # where it is now, from the station
        values[n] = v_now - ang
    return {n: st_mm for n in pockets}, values, notes


def changer(scene, anim, b, mach=None) -> TC.Changer:
    """The step's tool changes as the core plans them."""
    c = settings(scene)
    atc = c.changer == "ATC"
    ch = TC.Changer(atc=atc, pause=min(TC.PAUSE_MAX, max(0.0, float(b.gcode_tc_time))), hand=bool(b.gcode_hand),
                    speed=float(b.gcode_changer_speed), turn_time=float(c.pocket_time),
                    approach=float(c.atc_lift) / MM, start_tool=start_tool(scene))
    if c.change_mode == "Z":
        ch.position = (None, None, c.change_pos[2] / MM)
    elif c.change_mode == "XYZ":
        ch.position = tuple(x / MM for x in c.change_pos)
    if atc:
        a, _w = gcode.atc_animation(scene, anim, b)
        if a is not None:
            ch.seq = gcode._atc_length(a)
            ch.seq_swap = min(max(0.0, float(b.gcode_atc_swap)), ch.seq)
    if mach is None:
        try:
            mach = gcode.Machine(scene)
        except gcode.SetupError:
            mach = None
    if mach is not None:
        ch.rapid = tuple(mach.rapid)
    if atc and mach is not None and c.pockets:
        try:
            ch.stations, ch.carousel, _notes = stations(scene, mach)
        except Exception as exc:
            print("Fresing Render: tool changer stations:", exc)
            ch.stations, ch.carousel = {}, {}
        numbers = {t.number for t in c.tools}
        try:
            prog = gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0]
            numbers |= set(prog.tool_numbers())
        except Exception:
            pass
        numbers.add(ch.start_tool)
        ch.pockets = tool_pockets(scene, sorted(x for x in numbers if x))
        j = carousel(scene)
        if j is not None:
            ch.carousel_start = gcode._first_value(j)
            ch.pitch = TC.TURN / max(1, len(c.pockets))
            ch.carousel_limits = None if joints.is_motor(j) else joints.limits(j)
    return ch


def notes(scene, sch) -> list[str]:
    """Lines for the step's summary: the hand's minimum, tools without a pocket."""
    out = []
    ch = sch.timing.changer
    if ch is None:
        return out
    if ch.hand and any(c.hand for c in sch.changes) and ch.pause < TC.HAND_MIN - 1e-9:
        out.append(f"Tool change pause: {TC.HAND_MIN:.1f} s, not {ch.pause:.1f} s – the hand needs "
                   f"{TC.HAND_MIN:.1f} s")
    seen = set()
    for c in sch.changes:
        if c.note and c.note not in seen:
            seen.add(c.note)
            out.append(c.note)
    if sch.change_scale < 1.0 - 1e-6:
        out.append(f"'Fit into': tool changes shortened to {sch.change_scale * 100:.0f} % (they may take half of "
                   "the seconds)")
    return out


# ---------------------------------------------------------------------------
# the hand
# ---------------------------------------------------------------------------

def _tube(pts, radii, ring: int = 10) -> tuple[list, list]:
    """A closed tube along ``pts`` (rounded ends): (verts, faces)."""
    pts = [Vector(p) for p in pts]
    verts, faces = [], []
    n = len(pts)
    prev_x = None
    rings = []
    for k, (p, r) in enumerate(zip(pts, radii)):
        t = (pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized()
        x = prev_x if prev_x is not None else (t.orthogonal()).normalized()
        x = (x - t * x.dot(t)).normalized()
        y = t.cross(x)
        prev_x = x
        idx = []
        for i in range(ring):
            a = TC.TURN * i / ring
            verts.append(p + (x * math.cos(a) + y * math.sin(a)) * r)
            idx.append(len(verts) - 1)
        rings.append(idx)
    for a, b in zip(rings, rings[1:]):
        for i in range(ring):
            faces.append((a[i], a[(i + 1) % ring], b[(i + 1) % ring], b[i]))
    for end, sign in ((0, -1), (n - 1, 1)):
        t = (pts[min(end + 1, n - 1)] - pts[max(end - 1, 0)]).normalized() * sign
        verts.append(pts[end] + t * radii[end] * 0.9)
        c = len(verts) - 1
        r = rings[end]
        for i in range(ring):
            if sign > 0:
                faces.append((r[i], r[(i + 1) % ring], c))
            else:
                faces.append((r[(i + 1) % ring], r[i], c))
    return verts, faces


def _blob(centre, size, ring: int = 12, rows: int = 8) -> tuple[list, list]:
    """An ellipsoid: (verts, faces)."""
    cx, cy, cz = centre
    sx, sy, sz = size
    verts = [Vector((cx, cy, cz - sz))]
    for r in range(1, rows):
        phi = math.pi * r / rows - math.pi / 2
        for i in range(ring):
            a = TC.TURN * i / ring
            verts.append(Vector((cx + sx * math.cos(phi) * math.cos(a), cy + sy * math.cos(phi) * math.sin(a),
                                 cz + sz * math.sin(phi))))
    verts.append(Vector((cx, cy, cz + sz)))
    top = len(verts) - 1
    faces = []
    for i in range(ring):
        faces.append((0, 1 + (i + 1) % ring, 1 + i))
    for r in range(rows - 2):
        a0, b0 = 1 + r * ring, 1 + (r + 1) * ring
        for i in range(ring):
            faces.append((a0 + i, a0 + (i + 1) % ring, b0 + (i + 1) % ring, b0 + i))
    last = 1 + (rows - 2) * ring
    for i in range(ring):
        faces.append((last + i, last + (i + 1) % ring, top))
    return verts, faces


def hand_shapes(holder_r: float = 0.025) -> list:
    """The gloved hand's pieces in its own space (m): the grip centre at the origin on the tool's axis (Z along the
    tool, into the spindle); the palm on the -Y side (towards the operator), fingers wrapped round the holder."""
    r = holder_r
    parts = []
    # palm: a flattened blob in front of the holder
    parts.append(_blob((0.0, -(r + 0.016), -0.004), (0.045, 0.016, 0.048)))
    # four fingers round the holder (right hand: from the palm's +X edge round the back), one above the other
    for k, (z, length) in enumerate(((0.030, 0.076), (0.010, 0.084), (-0.010, 0.080), (-0.029, 0.066))):
        rad = r + 0.010
        a0 = math.radians(-60)
        sweep = length / rad
        pts = [(rad * math.cos(a0 + sweep * u), rad * math.sin(a0 + sweep * u), z - 0.004 * u)
               for u in (i / 7 for i in range(8))]
        pts = [(0.034, -(r + 0.016), z)] + pts
        parts.append(_tube(pts, [0.0095] + [0.0092 - 0.0012 * (i / 7) for i in range(8)]))
    # thumb round the other side, a little lower
    rad = r + 0.011
    pts = [(-0.036, -(r + 0.020), -0.035)] + [(rad * math.cos(a), rad * math.sin(a), -0.024 + 0.006 * i / 5)
                                              for i, a in enumerate(math.radians(x) for x in
                                                                    (-125, -145, -165, -185, -200, -212))]
    parts.append(_tube(pts, [0.012, 0.0115, 0.011, 0.0105, 0.010, 0.0095, 0.009]))
    # wrist and cuff, back towards the operator
    parts.append(_tube([(0.0, -(r + 0.030), -0.010), (0.0, -(r + 0.090), -0.022), (0.0, -(r + 0.150), -0.034)],
                       [0.030, 0.032, 0.036], ring=14))
    return parts


def glove_material() -> bpy.types.Material:
    mat = bpy.data.materials.get("FR glove")
    if mat is None:
        mat = bpy.data.materials.new("FR glove")
        mat[gcode.TAG] = "glove"
        rgb = (0.05, 0.22, 0.62, 1.0)                  # blue nitrile
        mat.diffuse_color = rgb
        mat.roughness = 0.5
        try:
            bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
            if bsdf is not None:
                bsdf.inputs["Base Color"].default_value = rgb
                bsdf.inputs["Roughness"].default_value = 0.5
                bsdf.inputs["Coat Weight"].default_value = 0.15
        except Exception:
            pass
    return mat


def hand_mesh(holder_r: float = 0.025) -> bpy.types.Mesh:
    verts, faces = [], []
    for v, f in hand_shapes(holder_r):
        base = len(verts)
        verts += [tuple(x) for x in v]
        faces += [tuple(i + base for i in face) for face in f]
    me = bpy.data.meshes.new(HAND_NAME)
    me.from_pydata(verts, [], faces)
    me.shade_smooth()
    me.materials.append(glove_material())
    me[gcode.TAG] = "tool"
    me.update()
    return me


def hand_frame(scene, mach, offsets: dict, n: int) -> Matrix:
    """The hand's grip pose in the world for tool ``n`` in the spindle (bake time pose)."""
    spindle = mach.tool
    w = spindle.matrix_world @ gcode.tool_frame(spindle)
    z = (w.to_3x3() @ Vector((0, 0, 1))).normalized()
    y = Vector((0, 1, 0))
    y = y - z * y.dot(z)
    if y.length < 0.2:
        y = Vector((1, 0, 0)) - z * z.x
    y.normalize()
    x = y.cross(z)
    h = max(0.02, ref_gauge(scene, mach) - GRIP_BELOW_GAUGE)
    origin = w.translation + z * h
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return m


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

def _copy(name, data, parent, world, col, tag_key: str, n: int):
    """A tool copy (removed with the others by 'Clear keys'); not one milling cuts with (no fr_cnc_t)."""
    ob = bpy.data.objects.new(name, data)
    ob[gcode.TAG] = "tool"
    ob[tag_key] = n
    ob[build.PROP_KIND] = "cnc"
    ob.hide_select = True
    col.objects.link(ob)
    gcode._place(ob, parent, world)
    return ob


def _frame_of(ob, spindle) -> Matrix:
    """A tool object's tip frame in its own space (from the copy's stored tip, or read from its part)."""
    if ob is spindle or "fr_tip" not in ob:
        return gcode.tool_frame(ob)
    axis = Vector(ob["fr_axis"])
    axis = axis.normalized() if axis.length > 1e-9 else Vector((0, 0, 1))
    return Matrix.Translation(Vector(ob["fr_tip"])) @ axis.to_track_quat("Z", "Y").to_matrix().to_4x4()


def gauge_of(scene, prog, n: int) -> float:
    from ..core import tools as tcore
    return tcore.gauge_length(gcode.tool_spec(scene, prog, n))


def tool_keys(scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until, warnings, merge, name,
              offsets=None) -> None:
    """Visibility keys of the tools (spindle, pockets, hand) and the carousel's turns, for one step."""
    from . import animation
    ch = sch.timing.changer
    start = sch.first_tool or (ch.start_tool if ch is not None else 0)
    numbers = sorted({c.tool for c in sch.changes if c.tool} | {n for _s, n, _t, _d in sch.tool_events if n}
                     | ({start} if start else set()))
    if not numbers:
        return
    show, away, w = gcode.tool_objects(scene, mach, prog, numbers, offsets)
    warnings += [f"'{name}': {x}" for x in w]
    spindle = mach.tool
    col = gcode._collection(scene)

    def key(ob, f, hidden):
        keys = vkeys.setdefault(ob.name, [(1, bool(ob.hide_render), "CONSTANT", "AUTO")])
        merge(keys, f, hidden, "CONSTANT")

    # tools standing in pockets: their CAD part, or a copy on the pocket's part
    pockets = ch.pockets if ch is not None and ch.atc else {}
    rows = {p.number: p for p in settings(scene).pockets}
    in_pocket = {}
    for n in numbers:
        if n in away:
            in_pocket[n] = away[n]
            continue
        pk = pockets.get(n)
        p = rows.get(pk) if pk is not None else None
        fr = pocket_frame(p) if p is not None else None
        ob = show.get(n)
        if fr is None or ob is None:
            continue
        same = next((o for o in bpy.data.objects if o.get("fr_cnc_pocket") == n and o.parent is p.obj), None)
        if same is not None:                           # an earlier step of this build made it: one per tool
            in_pocket[n] = same
            continue
        world = fr @ Matrix.Translation((0.0, 0.0, -gauge_of(scene, prog, n))) @ _frame_of(ob, spindle).inverted()
        cp = _copy(f"FR tool T{n} pocket", ob.data, p.obj, world, col, "fr_cnc_pocket", n)
        if ob is spindle:
            for i, slot in enumerate(ob.material_slots):
                if slot.link == "OBJECT" and i < len(cp.material_slots):
                    cp.material_slots[i].link = "OBJECT"
                    cp.material_slots[i].material = slot.material
        cp.hide_render = cp.hide_viewport = False
        in_pocket[n] = cp

    def in_spindle(n):
        return show.get(n, spindle) if n else spindle

    # the start: the start tool in the spindle, every other tool in its pocket
    for n, ob in show.items():
        if ob is not spindle:
            key(ob, f0, n != start)
    key(spindle, f0, start in show and show[start] is not spindle)
    for n, ob in in_pocket.items():
        key(ob, f0, n == start)

    rig = None
    cur = start
    for c in sch.changes:
        if c.length <= 0 and c.old == c.tool:
            continue
        old = c.old if c.old else cur
        fd, fs = f0 + c.drop * fps, f0 + c.swap * fps
        if c.hand is not None:
            if rig is None:
                rig = _Hand(scene, mach, col)
            for n in (old, c.tool):
                rig.carry_copy(n, in_spindle(n), col)
            rig.change(old, c, f0, fps, key)
        key(in_spindle(old), fd, True)
        if old in in_pocket:
            key(in_pocket[old], fd, False)
        if c.tool in in_pocket:
            key(in_pocket[c.tool], fs, True)
        key(in_spindle(c.tool), fs, False)
        cur = c.tool
    if rig is not None:
        rig.write()
    # the carousel
    j = carousel(scene)
    turns = [x for c in sch.changes for x in c.turns()]
    if j is not None and turns:
        if j.follows:
            warnings.append(f"'{name}': the carousel joint '{j.name}' follows another joint: it does not turn")
        else:
            keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
            interp, ez = animation.EASING["SMOOTH"]
            for t0, t1, v0, v1 in turns:
                merge(keys, f0 + t0 * fps, v0, interp, ez)
                merge(keys, f0 + t1 * fps, v1, "CONSTANT")
            jstate[j.name] = turns[-1][3]
            busy_until[j.name] = max(busy_until.get(j.name, 0), int(math.ceil(f0 + turns[-1][1] * fps)))
    # which tool is in the spindle from which frame on, for milling (task 0040)
    rec = [(f0, start if start in show else 0)]
    rec += [(f0 + swap * fps, n) for swap, n, _t, _d in sch.tool_events]
    gcode._record_schedule(scene, rec)


class _Hand:
    """The hand of one step while it is baked: its object, the copies of the tools it carries, its keys."""

    def __init__(self, scene, mach, col):
        self.grip = hand_frame(scene, mach, {}, 0)
        ob = bpy.data.objects.new(HAND_NAME, hand_mesh())
        ob[gcode.TAG] = "tool"
        ob[build.PROP_KIND] = "cnc"
        ob.hide_select = True
        col.objects.link(ob)
        gcode._place(ob, mach.tool.parent, self.grip)
        ob.hide_render = ob.hide_viewport = True
        self.ob = ob
        self.basis = ob.matrix_basis.copy()
        self.carry = {}
        self.keys = []                  # (frame, location)
        self.vis = []                   # (frame, hidden)

    def carry_copy(self, n, src, col) -> None:
        """A copy of tool ``n`` in the hand, placed as it sits in the spindle when the hand grips it."""
        if n in self.carry:
            return
        if src.parent is not None:
            world = src.parent.matrix_world @ src.matrix_parent_inverse @ src.matrix_basis
        else:
            world = src.matrix_basis.copy()
        cp = bpy.data.objects.new(f"FR tool T{n} in hand", src.data)
        cp[gcode.TAG] = "tool"
        cp["fr_cnc_carry"] = n
        cp[build.PROP_KIND] = "cnc"
        cp.hide_select = True
        col.objects.link(cp)
        for i, slot in enumerate(src.material_slots):
            if slot.link == "OBJECT" and i < len(cp.material_slots):
                cp.material_slots[i].link = "OBJECT"
                cp.material_slots[i].material = slot.material
        cp.parent = self.ob
        cp.matrix_parent_inverse = Matrix.Identity(4)
        cp.matrix_basis = self.grip.inverted() @ world
        cp.hide_render = cp.hide_viewport = True
        self.carry[n] = cp

    def change(self, old, c, f0, fps, key) -> None:
        """The hand's poses for one change, and what it carries when."""
        t0, length = c.hand
        poses = TC.hand_keys(t0, length)
        rot = self.basis.to_3x3()
        offs = {"grip": Vector((0, 0, 0)), "below": Vector((0, 0, -PULL)), "out": Vector(OUT)}
        for t, pose in poses:
            self.keys.append((f0 + t * fps, self.basis.translation + rot @ offs[pose]))
        self.vis += [(f0 + poses[0][0] * fps, False), (f0 + poses[-1][0] * fps, True)]
        grips = [t for t, p in poses if p == "grip"]
        outs = [t for t, p in poses if p == "out"]
        away_t = next(t for t in outs if t > grips[0])            # back outside with the old tool
        fetch = next(t for t in reversed(outs) if t < grips[1])     # outside again, with the new one
        co, cn = self.carry.get(old), self.carry.get(c.tool)
        if co is not None:
            key(co, f0 + grips[0] * fps, False)
            key(co, f0 + away_t * fps, True)
        if cn is not None:
            key(cn, f0 + fetch * fps, False)
            key(cn, f0 + grips[1] * fps, True)

    def write(self) -> None:
        from . import animation
        ob = self.ob
        cb = animation._channelbag(ob, "OBJECT")
        keys = sorted(self.keys, key=lambda k: k[0])
        interp, ez = animation.EASING["SMOOTH"]
        for i in range(3):
            animation._write(cb, "location", i, [(f, loc[i], interp, ez) for f, loc in keys])
        rows = [(1.0, 1.0, "CONSTANT", "AUTO")]
        for f, hidden in sorted(self.vis, key=lambda v: v[0]):
            r = (f, 1.0 if hidden else 0.0, "CONSTANT", "AUTO")
            if abs(rows[-1][0] - f) < 1e-9:
                rows[-1] = r
            else:
                rows.append(r)
        animation._write(cb, "hide_viewport", 0, rows)
        animation._write(cb, "hide_render", 0, rows)
        ob.hide_render = ob.hide_viewport = False


def remove_hand() -> None:
    for o in [o for o in bpy.data.objects if o.name.startswith(HAND_NAME) and o.get(gcode.TAG) == "tool"]:
        me = o.data
        bpy.data.objects.remove(o)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


# ---------------------------------------------------------------------------
# captions, model updates, old projects
# ---------------------------------------------------------------------------

def caption_text(scene, prog, n: int) -> str:
    from ..core import tools as tcore
    row = _row(scene, n)
    s = tcore.resolved(gcode.tool_spec(scene, prog, n))
    kind = tcore.type_name(s.kind).lower()
    text = f"Tool change: T{n} Ø{s.diameter * 1000:.2f}".rstrip("0").rstrip(".") + f" {kind}"
    name = row.name.strip() if row is not None else ""
    letters = "".join(ch for ch in name.lower() if ch.isalnum())
    if letters and letters not in "".join(ch for ch in kind if ch.isalnum()):
        text += f" ({name})"
    return text


def captions(scene, anim) -> list[tuple[str, float, float]]:
    """(text, start, end) seconds of the tool-change captions of an animation's G-code steps that ask for them."""
    out = []
    for b in anim.blocks:
        if not b.enabled or b.kind != "GCODE" or not b.gcode_tc_caption or not b.gcode_file:
            continue
        try:
            mach = gcode.Machine(scene)
        except gcode.SetupError:
            mach = None
        try:
            prog, _n = gcode.read_program(scene, b, mach, start=gcode.start_point(mach))
        except Exception:
            continue
        from ..core import gcode as core
        sch = core.Schedule(prog, gcode.timing(scene, anim, b))
        for c in sch.changes:
            if c.length > 0 and c.tool:
                out.append((caption_text(scene, prog, c.tool), b.start + c.start, b.start + c.start + c.length))
    return out


def before_model_update(scene) -> None:
    remove_markers()
    remove_hand()


def after_model_update(scene, new) -> list[str]:
    c = settings(scene)
    notes = []
    for p in c.pockets:
        if not p.uid:
            continue
        ob = new(p.uid)
        p.obj = ob
        if ob is None:
            notes.append(f"CNC machine: the part of pocket {p.number} is gone in the new revision (click the pocket "
                         "again in 4 Motion > CNC machine > Tool changes)")
        else:
            p.uid = ob.get(build.PROP_UID, "")
    try:
        show_markers(scene)
    except Exception:
        pass
    return notes


def upgrade(scene) -> None:
    """Projects from before 0.2.45: a step with a tool-changer animation means the machine has a tool changer, so it
    plays as before (0.2.45 asks for the machine's kind)."""
    c = settings(scene)
    if c.get("changer") is not None:
        return
    if any(b.kind == "GCODE" and b.gcode_atc for a in scene.fresing.animations for b in a.blocks):
        c["_busy"] = True
        c.changer = "ATC"
        del c["_busy"]
