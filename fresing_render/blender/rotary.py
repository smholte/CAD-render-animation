"""Rotary axes A, B, C of the CNC machine (task 0066): the 4th and 5th axis.

Set-up (4 Motion > CNC machine > Rotary axes, ``scene.fresing.cnc``): a rotate joint for each of A, B, C (any can be
empty), Reverse, rapid in degrees per minute, Wrapped, and the kinematics:

    Plain   A, B, C are just the joints' angles: the CAM post worked out X, Y and Z for the turned part (LinuxCNC
            ``trivkins``). Joint value = home + sign * angle.
    TCP     "Tool follows the part": the program is written for the part as it lies at A0 B0 C0; X, Y and Z get the
            values that put the tool tip on that point of the turned part. Only rotary axes that turn the part
            (a rotary table, a trunnion); a turning head stays Plain.

The maths, in machine coordinates (mm, the program's axes; ``Machine`` in gcode.py): every rotary axis that turns the
workpiece has a centre K (the machine position at which the tool tip lies on its axis) and a direction u, both as
they are with every rotary axis at 0. Turning the axes by their program angles moves a point p of the part to

    T(p) = K_outer + R_outer (K_inner + R_inner (p - K_inner) - K_outer)         (the inner axis first)

TCP: X/Y/Z = T(programmed point). Plain: the point of the part under the tool is T⁻¹(X/Y/Z) – that is where the
toolpath is drawn (on the part, so it turns with it).

The direction of +A (+B, +C): the tool goes round the part right-handed about +X (+Y, +Z), like X/Y/Z where + is the
tool's move relative to the part; a table turns the other way. Reverse turns it round.

The machine is set up in whatever pose the model is in: ``Machine`` turns everything back to A0 B0 C0 first
(``unturn``), so the work zero, G54 and the centres are the same at every pose.
"""

from __future__ import annotations

import math

from mathutils import Matrix, Vector

from . import joints

MM = 0.001
LETTERS = "ABC"
TCP_TOL = 0.002                  # mm: the tool tip may stray this much between two keys (TCP)
PROG_AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))


def joint_names(c) -> tuple:
    return (c.a_joint, c.b_joint, c.c_joint)


def _turn_about(o: Vector, d: Vector, angle: float) -> Matrix:
    """World transform: a turn by ``angle`` (rad) about the line through ``o`` along ``d``."""
    return Matrix.Translation(o) @ Matrix.Rotation(angle, 4, d) @ Matrix.Translation(-o)


class Axis:
    """One rotary axis of the machine."""

    def __init__(self, index: int, j, sign: float, home: float, part: bool, rapid: float, wrapped: bool):
        self.index = index
        self.letter = LETTERS[index]
        self.joint = j
        self.sign = sign
        self.home = home                    # joint value (rad) at program 0
        self.part = part                    # turns the workpiece (else the tool)
        self.rapid = rapid
        self.wrapped = wrapped
        self.centre = (0.0, 0.0, 0.0)       # K, machine mm (part side)
        self.u = Vector((1, 0, 0))          # direction in the program's axes (the joint's +)
        self.auto = 1.0
        self.back = Matrix.Identity(4)      # world: undoes its turn as it is now (set by build)

    def value(self, deg: float) -> float:
        return self.home + self.sign * math.radians(deg)

    def angle_of(self, value: float) -> float:
        return math.degrees((value - self.home) * self.sign)


def build(mach, c, s, carries, xyz_names) -> None:
    """Add the rotary axes to ``mach`` (a gcode.Machine being made): ``mach.axes`` (index -> Axis), ``unturn_part``
    / ``unturn_tool`` (world transforms back to A0 B0 C0). Raises gcode.SetupError when a pick is wrong."""
    from .gcode import SetupError
    mach.axes = {}
    mach.axis_order = []
    mach.unturn_part = Matrix.Identity(4)
    mach.unturn_tool = Matrix.Identity(4)
    mach.kinematics = c.kinematics
    names = joint_names(c)
    if not any(names):
        return
    home_rot = list(c.home_rot) if c.home_set else [0.0, 0.0, 0.0]
    used = set(xyz_names) | ({c.spindle_joint} if c.spindle_joint else set())
    picked = []
    for k, name in enumerate(names):
        if not name:
            continue
        letter = LETTERS[k]
        j = s.joints.get(name)
        if j is None:
            raise SetupError(f"The {letter} joint '{name}' is gone: pick it again")
        if j.kind != "ROTATE":
            raise SetupError(f"'{j.name}' slides: the {letter} axis needs a rotate joint")
        if j.follows:
            raise SetupError(f"'{j.name}' follows another joint: the {letter} axis needs a joint that moves by itself")
        if not joints.is_valid(j):
            raise SetupError(f"The {letter} joint '{j.name}' is broken")
        if j.name in used:
            raise SetupError(f"'{j.name}' is already X, Y, Z, the spindle or another rotary axis: pick another joint "
                             f"for {letter}")
        used.add(j.name)
        t, w = carries(j, mach.tool), carries(j, mach.workpiece)
        if t == w:
            raise SetupError(f"'{j.name}' ({letter}) turns {'both the tool and' if t else 'neither the tool nor'} the "
                             "workpiece")
        picked.append((k, j, w))
    # inner first: an axis carried by more of the others comes first (keys worked out before sorting: the list is
    # empty while Python sorts it)
    depth = {j.name: sum(1 for _k2, j2, _w2 in picked if j2.name != j.name and carries(j2, j.frame))
             for _k, j, _w in picked}
    picked.sort(key=lambda item: -depth[item[1].name])
    rev = (c.a_reverse, c.b_reverse, c.c_reverse)
    rapid = (c.rapid_a, c.rapid_b, c.rapid_c)
    wrapped = (c.a_wrapped, c.b_wrapped, c.c_wrapped)
    for k, j, w in picked:
        mach.axes[k] = Axis(k, j, 1.0, home_rot[k], w, rapid[k], wrapped[k])
    mach.axis_order = [k for k, _j, _w in picked]               # inner first
    # back to A0 B0 C0: undo each axis' turn, the inner one first (its axis as it is now)
    for k in mach.axis_order:
        ax = mach.axes[k]
        o, d = joints.axis_world(ax.joint)
        ax.back = _turn_about(o, d, -(joints.get_value(ax.joint) - ax.home))
        if ax.part:
            mach.unturn_part = ax.back @ mach.unturn_part
        else:
            mach.unturn_tool = ax.back @ mach.unturn_tool
    # which way + turns: from the axis as it lies at A0 B0 C0 (the outer axes turned back, as ``finish`` does), not
    # as it lies now – C on a trunnion at A >= 90° pointed the other way (task 0071, bug hunt 0068 row 10)
    for n, k in enumerate(mach.axis_order):
        ax = mach.axes[k]
        _o, d = joints.axis_world(ax.joint)
        for k2 in mach.axis_order[n + 1:]:
            if mach.axes[k2].part == ax.part:
                d = mach.axes[k2].back.to_3x3() @ d
        rel = -d if ax.part else d                               # the tool's turn relative to the part
        e = mach.rot @ PROG_AXES[k]
        ax.auto = 1.0 if rel.dot(e) >= 0 else -1.0
        ax.sign = ax.auto * (-1.0 if rev[k] else 1.0)


def finish(mach) -> None:
    """Centres and directions in machine coordinates (needs ``mach.zero`` and ``mach.g54``)."""
    rt = mach.rot.transposed()
    for n, k in enumerate(mach.axis_order):
        ax = mach.axes[k]
        o, d = joints.axis_world(ax.joint)
        un = Matrix.Identity(4)                     # only the axes that carry this one move its axis
        for k2 in mach.axis_order[n + 1:]:
            if mach.axes[k2].part == ax.part:
                un = mach.axes[k2].back @ un
        o_h = un @ o
        d_h = (un.to_3x3() @ d).normalized()
        c_rel = rt @ (o_h - mach.zero) / MM
        ax.centre = tuple(g + x for g, x in zip(mach.g54, c_rel))
        ax.u = (rt @ d_h).normalized()


def part_axes(mach) -> list:
    """The axes that turn the workpiece, inner first."""
    return [mach.axes[k] for k in getattr(mach, "axis_order", []) if mach.axes[k].part]


def turn_point(mach, p, rot, inverse: bool = False) -> tuple:
    """A point of the part (machine mm, as at A0 B0 C0) moved by the part's turn at ``rot`` (A, B, C degrees); with
    ``inverse`` the other way (the point of the part at A0 B0 C0 that is at ``p`` now)."""
    axes = part_axes(mach)
    if not axes:
        return tuple(p)
    v = Vector(p)
    seq = list(reversed(axes)) if inverse else axes
    for ax in seq:
        ang = ax.sign * math.radians(rot[ax.index])
        if inverse:
            ang = -ang
        k = Vector(ax.centre)
        v = k + Matrix.Rotation(ang, 3, ax.u) @ (v - k)
    return (v.x, v.y, v.z)


def tcp(mach) -> bool:
    return getattr(mach, "kinematics", "PLAIN") == "TCP" and bool(part_axes(mach))


def machine_point(mach, p, rot) -> tuple:
    """X/Y/Z (machine mm) for the program's point ``p`` at ``rot``: TCP turns it with the part, Plain leaves it."""
    return turn_point(mach, p, rot) if tcp(mach) else tuple(p)


def program_point(mach, m, rot) -> tuple:
    """The program's point for X/Y/Z ``m`` (machine mm) at ``rot`` (the other way round)."""
    return turn_point(mach, m, rot, inverse=True) if tcp(mach) else tuple(m)


def on_part(mach, m, rot) -> tuple:
    """Where X/Y/Z ``m`` at ``rot`` touches the part, in machine mm as the part lies at A0 B0 C0 (the toolpath)."""
    return turn_point(mach, m, rot, inverse=True)


def values_for(mach, rot) -> list:
    """[(joint, value)] of the rotary axes for A, B, C ``rot`` (degrees)."""
    return [(ax.joint, ax.value(rot[k])) for k, ax in sorted(mach.axes.items())]


def rot_of(mach, values: dict | None = None) -> tuple:
    """A, B, C (degrees) of the rotary joints' values (``values``: {joint name: value}, else now)."""
    out = [0.0, 0.0, 0.0]
    for k, ax in mach.axes.items():
        v = values.get(ax.joint.name) if values is not None else None
        out[k] = ax.angle_of(joints.get_value(ax.joint) if v is None else v)
    return tuple(out)


def first_rot(mach) -> tuple:
    """A, B, C at frame 1 (their keys there once an animation is built)."""
    from .gcode import _first_value
    return rot_of(mach, {ax.joint.name: _first_value(ax.joint) for ax in mach.axes.values()})


def radius(mach, prog) -> float:
    """The furthest the program's points come from a part-side axis (mm)."""
    box = prog.bounds()
    if box is None:
        return 0.0
    lo, hi = box
    pts = [Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    r = 0.0
    for ax in part_axes(mach):
        k = Vector(ax.centre)
        for p in pts:
            q = p - k
            r = max(r, (q - ax.u * q.dot(ax.u)).length)
    return r


def turn_step(mach, prog, tol: float = TCP_TOL) -> float:
    """Degrees between keys so that a point ``radius`` away strays less than ``tol`` between them (TCP); 0 off."""
    if not tcp(mach):
        return 0.0
    r = max(radius(mach, prog), 1.0)
    step = math.degrees(2 * math.acos(max(-1.0, 1 - tol / r))) if tol < r else 5.0
    return min(5.0, max(0.05, step))


def describe(mach) -> list:
    """Lines for the panel: which joint is which axis and what it turns."""
    out = []
    for k, ax in sorted(mach.axes.items()):
        e = PROG_AXES[k]
        dev = math.degrees(ax.u.angle(e if ax.u.dot(e) >= 0 else -e)) if ax.u.length > 0 else 90.0
        about = "XYZ"[k]
        side = "the workpiece" if ax.part else "the tool (head)"
        note = "" if dev < 1.0 else f" – its axis is {dev:.0f}° off the machine's {about}"
        out.append(f"{ax.letter}: '{ax.joint.name}' turns {side}{note}")
    if mach.kinematics == "TCP":
        if part_axes(mach):
            heads = [ax.letter for ax in mach.axes.values() if not ax.part]
            out.append("Tool follows the part (TCP)" + (f"; {', '.join(heads)} turn(s) the head: Plain"
                                                        if heads else ""))
        else:
            out.append("TCP only works for axes that turn the workpiece: Plain is used")
    return out


# ---------------------------------------------------------------------------
# Check: turn each axis through its range, report direction, centre and (TCP) how far the tip strays
# ---------------------------------------------------------------------------

LAST_CHECK: list = []                # [(ok, line)] of the last Check, for the panel


def check_angles(ax, n: int = 8) -> list:
    """Angles (degrees) the Check turns ``ax`` through: its limits, else a whole turn."""
    j = ax.joint
    if j.use_limits and not joints.is_motor(j):
        lo, hi = sorted((ax.angle_of(j.rot_min), ax.angle_of(j.rot_max)))
        lo, hi = max(lo, -360.0), min(hi, 360.0)
    else:
        lo, hi = -180.0, 180.0
    return [lo + (hi - lo) * i / n for i in range(n + 1)]


def check(scene) -> list:
    """Check the rotary axes on the model (``LAST_CHECK``): for each axis the direction it turns, its centre from the
    work zero, and how far a point of the part under the tool tip strays from the tip when the axis turns with TCP
    (Plain: how far the work zero swings). Puts every joint back. Returns [(ok, line)]."""
    from . import gcode
    out = []
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError as exc:
        out.append((False, str(exc)))
        LAST_CHECK[:] = out
        return out
    if not mach.axes:
        out.append((False, "Pick a rotate joint for A, B or C first"))
        LAST_CHECK[:] = out
        return out
    keep = {j.name: joints.get_value(j) for j in mach.joints + [ax.joint for ax in mach.axes.values()]}
    try:
        for k, ax in sorted(mach.axes.items()):
            e = PROG_AXES[k]
            dev = math.degrees(ax.u.angle(e if ax.u.dot(e) >= 0 else -e))
            sign_word = "+" if (ax.u.dot(e) >= 0) == (ax.sign > 0) else "-"
            what = "workpiece" if ax.part else "head"
            out.append((dev < 1.0, f"{ax.letter}: '{ax.joint.name}' turns the {what} about the machine's "
                                   f"{sign_word}{'XYZ'[k]}" + (f" ({dev:.1f}° off)" if dev >= 0.05 else "")))
            if ax.part:
                cen = Vector(ax.centre) - Vector(mach.g54)
                parts = [f"{'XYZ'[i]} {cen[i] + 0.0:.2f}".replace("-0.00", "0.00") for i in range(3) if i != k]
                out.append((True, f"{ax.letter} centre from the work zero: " + ", ".join(parts) + " mm"))
            stray = _stray(scene, mach, ax, keep)
            if ax.part and tcp(mach):
                out.append((stray < 0.01, f"{ax.letter} with TCP: the tool tip strays {stray:.4f} mm from its point "
                                          "on the part" + ("" if stray < 0.01 else " – the joint or its axis is wrong")))
            elif ax.part:
                swing = max(_zero_swing(mach, ax, a) for a in check_angles(ax))
                out.append((True, f"{ax.letter} turns the work zero round by up to {swing:.1f} mm (Plain: the CAM "
                                  "post must know this centre)"))
    finally:
        for name, v in keep.items():
            j = scene.fresing.joints.get(name)
            if j is not None:
                joints.set_value(j, v, use_limits=False)
        joints._update(scene)
    LAST_CHECK[:] = out
    return out


def _zero_swing(mach, ax, angle: float) -> float:
    rot = [0.0, 0.0, 0.0]
    rot[ax.index] = angle
    g = mach.g54
    q = turn_point(mach, g, rot)
    return math.dist(q, g)


def _stray(scene, mach, ax, keep: dict) -> float:
    """Turn ``ax`` through its range in the model (the X/Y/Z joints follow with TCP). Returns the largest distance (mm)
    between the tool tip and the point of the part that was under it at the first angle (0 for Plain)."""
    from . import gcode
    tip_l, _a, _t = gcode._rest_tip(mach.tool)
    rot0 = rot_of(mach)
    p = program_point(mach, mach.machine_of([keep[j.name] for j in mach.joints]), rot0)
    wp = mach.workpiece
    out = 0.0
    local = None
    for a in check_angles(ax):
        rot = list(rot0)
        rot[ax.index] = a
        for j, v in values_for(mach, rot):
            joints.set_value(j, v, use_limits=False)
        if tcp(mach):
            for j, v in zip(mach.joints, mach.values_for(machine_point(mach, p, rot))):
                joints.set_value(j, v, use_limits=False)
        joints._update(scene)
        if not tcp(mach):
            continue
        tip = mach.tool.matrix_world @ tip_l
        if local is None:
            local = wp.matrix_world.inverted() @ tip
            continue
        out = max(out, ((wp.matrix_world @ local) - tip).length / MM)
    return out


# ---------------------------------------------------------------------------
# the two test models (tools/make_test_4axis.py, make_test_5axis.py): programs and set-up
# ---------------------------------------------------------------------------

def _flat(y_from: float, y_to: float, x0: float, x1: float, depth: float, step: float) -> list:
    """Passes back and forth along X, ``step`` apart in Y, at ``depth``: a flat."""
    out, y, k = [], y_from, 0
    out.append(f"G0 X{x0:g} Y{y:g}")
    out.append(f"G1 Z{depth:g} F300")
    while True:
        out.append(f"G1 X{(x1 if k % 2 == 0 else x0):g} F600")
        k += 1
        if y + step > y_to + 1e-9:
            break
        y += step
        out.append(f"G1 Y{y:g}")
    out.append("G0 Z10")
    return out


#: test_4axis.step, Plain kinematics, work zero on top of the bar in its middle (the A axis at Y0 Z-25): a slot
#: wrapped once round the bar (X -90 .. -10 while A turns 0 .. 360, 2 deep) and a flat 3 deep at A0 and at A180
TEST_PROGRAM_4AXIS = "\n".join([
    "(4-AXIS TEST: WRAPPED SLOT AND TWO FLATS)",
    "(T1 D=6 CR=0 - ZMIN=-3 - flat end mill)",
    "G21 G90 G94 G17 G54",
    "T1 M6",
    "S10000 M3",
    "G0 Z10",
    "G0 X-90 Y0 A0",
    "G1 Z-2 F300",
    "G1 X-10 A360 F400",
    "G0 Z10",
    "G0 A0",
    *_flat(-13, 12, 20, 50, -3, 5),
    "G0 A180",
    *_flat(-13, 12, 20, 50, -3, 5),
    "G0 A0",
    "M5",
    "M30",
]) + "\n"

POCKET_A = 30.0                  # 5-axis test: the pockets' tilt
POCKET_Y = 18.0                  # their centre on the block's top, from its middle
POCKET_DEPTH = 3.0
POCKET_HALF = 4.0                # the tool's centre goes round a square this far from the pocket's middle


def _pocket(c_deg: float) -> list:
    """A square pocket on the block (TCP: program in the block's own coordinates) with the tool tilted by A30 at
    C ``c_deg``: down along the tool's axis, round the square, back up."""
    import math as m
    a, c = m.radians(POCKET_A), m.radians(c_deg)
    # the tool's axis in the block's coordinates at A30, C c (+A: the tool goes round right-handed about +X)
    def rz(v):
        return (v[0] * m.cos(c) - v[1] * m.sin(c), v[0] * m.sin(c) + v[1] * m.cos(c), v[2])
    n = rz((0.0, -m.sin(a), m.cos(a)))
    e1 = rz((1.0, 0.0, 0.0))
    e2 = rz((0.0, m.cos(a), m.sin(a)))
    cen = rz((0.0, -POCKET_Y, 0.0))
    floor = [cen[i] - POCKET_DEPTH * n[i] for i in range(3)]
    clear = [cen[i] + 15.0 * n[i] for i in range(3)]

    def at(p):
        return f"X{p[0]:.4f} Y{p[1]:.4f} Z{p[2]:.4f}"
    out = [f"G0 A{POCKET_A:g} C{c_deg:g}", f"G0 {at(clear)}", f"G1 {at(floor)} F200"]
    h = POCKET_HALF
    for u, v in ((h, -h), (h, h), (-h, h), (-h, -h), (h, -h)):
        out.append(f"G1 {at([floor[i] + u * e1[i] + v * e2[i] for i in range(3)])} F400")
    out += [f"G1 {at(floor)}", f"G0 {at(clear)}"]
    return out


#: test_5axis.step, Tool follows the part (TCP), work zero on top of the block in its middle (the A axis at Y0 Z-40,
#: C through X0 Y0): a 3+2 pocket on each side tilted by A30 (C0 and C180), and a straight groove 1 deep along
#: Y20 cut while C turns 90° (simultaneous)
TEST_PROGRAM_5AXIS = "\n".join([
    "(5-AXIS TEST: TWO TILTED POCKETS AND A GROOVE WHILE C TURNS)",
    "(T1 D=6 CR=0 - ZMIN=-3 - flat end mill)",
    "G21 G90 G94 G17 G54",
    "T1 M6",
    "S10000 M3",
    "G0 Z20",
    *_pocket(0.0),
    "G0 Z40",
    *_pocket(180.0),
    "G0 Z40",
    "G0 A0 C0",
    "G0 X-20 Y20 Z5",
    "G1 Z-1 F200",
    "G1 X20 C90 F300",
    "G0 Z20",
    "G0 C0",
    "M5",
    "M30",
]) + "\n"


def _named(scene, name):
    from . import build as b_
    ob = next((o for o in scene.objects if o.get(b_.PROP_NAME) == name), None)
    if ob is None:
        raise RuntimeError(f"'{name}' is not in the model")
    return ob


def set_up_test_model(scene, b, five: bool = False, milling: bool = True) -> None:
    """The imported test_4axis.step (``five``: test_5axis.step) as a CNC machine, step ``b`` running its program:
    X/Y/Z on the moving column, the spindle (a motor), A (and C) on the rotary table, the tool list (T1 the part in
    the spindle), the work zero on top of the workpiece in its middle; 4 axes Plain, 5 axes TCP. ``milling``: the
    tool cuts the workpiece."""
    from . import gcode, machining, tools
    for name, asm, d in (("X", "X.ASM", (1, 0, 0)), ("Y", "Y.ASM", (0, 1, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _named(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    tool = _named(scene, "TOOL T1 FLAT D6")
    j = joints.create(scene, "ROTATE", [tool], Vector((0, 0, 0.25 if five else 0.21)), Vector((0, 0, 1)),
                      name="Spindle")
    joints.set_motor(scene, j, True)
    if five:
        joints.create(scene, "ROTATE", [_named(scene, "A.ASM")], Vector((0, 0, 0.14)), Vector((1, 0, 0)),
                      name="Trunnion A")
        joints.create(scene, "ROTATE", [_named(scene, "C.ASM")], Vector((0, 0, 0.14)), Vector((0, 0, 1)),
                      name="Table C")
        wp = _named(scene, "BLOCK 60x60x40")
    else:
        joints.create(scene, "ROTATE", [_named(scene, "A.ASM")], Vector((0, 0, 0.15)), Vector((1, 0, 0)),
                      name="Rotary A")
        wp = _named(scene, "BAR D50x240")
    for jn in ("Trunnion A", "Table C", "Rotary A"):
        jj = scene.fresing.joints.get(jn)
        if jj is not None:
            jj.use_limits = False
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, wp)
    gcode.find_axes(scene)
    c = gcode.settings(scene)
    c["_busy"] = True
    c.spindle_joint = "Spindle"
    if five:
        c.a_joint, c.c_joint = "Trunnion A", "Table C"
        c.kinematics = "TCP"
    else:
        c.a_joint = "Rotary A"
    c.zero_mode = "TOP_CENTRE"
    del c["_busy"]
    gcode.setup_changed(scene)
    why = gcode.problem(scene)
    if why:
        raise RuntimeError(why)
    gcode.tools_from_program(scene, b)
    row = tools.row_of(scene, 1)
    if row is None:
        raise RuntimeError("Tools from the program did not add T1")
    tools.use_part(scene, row, tool)
    if milling:
        machining.settings(scene).enabled = True
        machining.add_bit(scene, tool)
        machining.set_workpiece(scene, wp)
    gcode.step_changed(scene, b)


def start_check(scene) -> list:
    """Before Check plays in the view: the animation's keys go first (bug hunt 0068 row 11: read before them, the
    pose of the frame shown was put back afterwards and the next Build started from there). Returns the poses."""
    from . import animation
    animation.clear_keys(scene)
    return check_poses(scene)


def check_poses(scene, seconds: float = 1.6) -> list:
    """[(seconds, {joint name: value})] for Check to play in the view: each axis in turn through its range and back
    to where it was (with TCP the X/Y/Z joints follow, so the tool tip stays on its point of the part)."""
    from . import gcode
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError:
        return []
    if not mach.axes:
        return []
    names = [j.name for j in mach.joints] + [ax.joint.name for ax in mach.axes.values()]
    keep = {n: joints.get_value(scene.fresing.joints[n]) for n in names}
    rot0 = rot_of(mach)
    p = program_point(mach, mach.machine_of([keep[j.name] for j in mach.joints]), rot0)
    out = [(0.0, dict(keep))]
    t = 0.0
    for k, ax in sorted(mach.axes.items()):
        angles = check_angles(ax, 24)
        seq = [rot0[k]] + angles + [rot0[k]]
        for n, a in enumerate(seq[1:], 1):
            rot = list(rot0)
            rot[k] = a
            v = dict(keep)
            for j, val in values_for(mach, rot):
                v[j.name] = val
            if tcp(mach):
                for j, val in zip(mach.joints, mach.values_for(machine_point(mach, p, rot))):
                    v[j.name] = val
            dt = seconds / len(angles) if 1 < n < len(seq) - 1 else seconds / 4
            t += dt
            out.append((t, v))
    return out
