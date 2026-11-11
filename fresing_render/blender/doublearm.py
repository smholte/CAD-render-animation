"""Double-arm tool changer (task 0064): the arm grips the tool in the spindle and the one in the tipped pot, pulls them
out, turns 180° and pushes them in; every tool hangs on the spindle, the arm or a pot at every frame.

Set-up (4 Motion > CNC machine > Tool changes, ``scene.fresing.cnc``, changer 'ARM'):

    arm           select the arm (a part or subassembly), click its hub: the app makes two joints on it – a slide
                  along the hub's axis (``arm_slide``, the pull-out stroke) and a rotate joint riding on it
                  (``arm_turn``) – and reads the grip angle from the arm's round claws
    magazine      the carousel joint and the pockets (task 0041): 'Click pockets' + 'Fill the carousel', or with
                  tipping pots 'Click the hinge' on the pot at the change station: the app puts a pocket in every pot
                  and makes one rotate joint per pot ("Pot N tip", its hinge) – the pot at the station tips
    settings      rest / grip angle, pull-out stroke, orient angle, times; 'Check' plays one change in the view and
                  says what does not fit

The head goes to the change position (it must hold the spindle where the arm grips). The bake (``tool_keys``) keys
the arm's two joints, the pots' tip joints, the carousel and the tools' visibility. Every tool is shown by one copy
per holder: the spindle's (gcode.tool_objects), on the arm (children of the arm's turn, "FR tool Tn on arm"), in a
pot (children of the pot's part, "FR tool Tn pot k"); at each hand-over the two copies are in the same place, worked
out from the joints' frames (``world_at``), not read from frames:

    W      the tool in the spindle at the change (head at the change position, spindle at its orient angle)
    A(θ)   the arm's turn at angle θ, stroke 0;  R  half a turn about the arm's axis
    P_k    pot k at the station, tipped

    on the arm at the spindle: A(θ)⁻¹ W     on the arm at the pot: A(θ)⁻¹ R W     in pot k: P_k⁻¹ R W

so a tool taken from the spindle and pushed into a pot (θ -> θ + π) lands exactly on its pot copy, and back.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from ..core import toolchange as TC
from . import build, gcode, joints

MM = 0.001
ARM_TAG = "fr_atc"                       # on the motion empties of the joints this module makes
STROKE_EXTRA = 5 * MM                    # the stroke clears the taper and the pull stud by this much
PARALLEL = math.radians(0.5)
FIT = 0.1 * MM                           # 'Check': grip and pot must be on the spindle's axis within this
LAST_CHECK: list = []                    # the last 'Check' result, (fits?, line), for the panel


def settings(scene):
    return scene.fresing.cnc


def is_on(scene) -> bool:
    return settings(scene).changer == "ARM"


def _joint(scene, name):
    j = scene.fresing.joints.get(name) if name else None
    return j if j is not None and joints.is_valid(j) else None


def arm_joints(scene):
    """(slide, turn) of the arm, or (None, None)."""
    c = settings(scene)
    s, t = _joint(scene, c.arm_slide), _joint(scene, c.arm_turn)
    if s is None or t is None or s.kind != "SLIDE" or t.kind != "ROTATE":
        return None, None
    return s, t


def app_joint(j) -> bool:
    """True for a joint this module made (the arm, the pots): never an axis or the spindle."""
    return j.motion is not None and bool(j.motion.get(ARM_TAG))


# ---------------------------------------------------------------------------
# poses worked out from the joints' frames
# ---------------------------------------------------------------------------

def world_at(scene, ob, values: dict) -> Matrix:
    """``ob``'s world matrix with the joints in ``values`` ({name: value}) at those values, the rest as now."""
    chain = []
    o = ob
    while o is not None:
        chain.append(o)
        o = o.parent
    m = Matrix.Identity(4)
    for o in reversed(chain):
        name = o.get("fr_joint") if o.get(build.PROP_KIND) == "joint" else None
        if name is not None and name in values:
            j = scene.fresing.joints.get(name)
            v = float(values[name])
            basis = (Matrix.Rotation(v, 4, "Z") if j is not None and j.kind == "ROTATE"
                     else Matrix.Translation((0.0, 0.0, v)))
        else:
            basis = o.matrix_basis
        m = m @ o.matrix_parent_inverse @ basis
    return m


def spindle_axis(scene) -> Vector:
    from . import toolchange
    return toolchange.spindle_axis(scene)


def change_values(scene, mach, point=None) -> dict:
    """Joint values with the head at the change position (``point``: machine mm, else the set-up's) and the spindle at
    its orient angle."""
    c = settings(scene)
    vals = {}
    if point is None:
        cur = mach.machine_of([joints.get_value(j) for j in mach.joints])
        if c.change_mode == "XYZ":
            point = tuple(x / MM for x in c.change_pos)
        elif c.change_mode == "Z":
            point = (cur[0], cur[1], c.change_pos[2] / MM)
        else:
            point = cur
    for j, v in zip(mach.joints, mach.values_for(point)):
        vals[j.name] = v
    sp = _joint(scene, c.spindle_joint)
    if sp is not None and sp.kind == "ROTATE":
        vals[sp.name] = float(c.orient_angle)
    return vals


def gauge_frame(scene, mach, values: dict) -> Matrix:
    """The spindle's gauge-line frame (origin on the gauge line, Z into the spindle) for the joint values."""
    from . import toolchange
    spindle = mach.tool
    w = world_at(scene, spindle, values) @ gcode.tool_frame(spindle)
    return w @ Matrix.Translation((0.0, 0.0, toolchange.ref_gauge(scene, mach)))


def arm_frame(scene, turn, slide) -> Matrix:
    """The arm's turn axis frame (stroke 0)."""
    return world_at(scene, turn.frame, {slide.name: 0.0})


def half_turn(frame: Matrix) -> Matrix:
    return frame @ Matrix.Rotation(math.pi, 4, "Z") @ frame.inverted()


def arm_at(scene, turn, slide, theta: float) -> Matrix:
    return world_at(scene, turn.motion, {slide.name: 0.0, turn.name: theta})


def tip_value(scene) -> float:
    c = settings(scene)
    return float(c.pot_tip_sign) * float(c.pot_tip_angle)


def station_values(scene, pocket_row, carousel_value: float | None, tipped: bool) -> dict:
    from . import toolchange
    vals = {}
    j = toolchange.carousel(scene)
    if j is not None and carousel_value is not None:
        vals[j.name] = carousel_value
    tj = _joint(scene, pocket_row.tip_joint) if settings(scene).pot_tip else None
    if tj is not None:
        vals[tj.name] = tip_value(scene) if tipped else 0.0
    return vals


# ---------------------------------------------------------------------------
# set-up: the arm
# ---------------------------------------------------------------------------

def _round_axes(ob):
    """[(origin, direction, radius)] of a part's round faces, world."""
    me = ob.data if ob is not None and ob.type == "MESH" else None
    if me is None or "fr_axes" not in me:
        return []
    a = list(me["fr_axes"])
    mw = ob.matrix_world
    out = []
    for k in range(0, len(a) - 6, 7):
        o = mw @ Vector(a[k:k + 3])
        d = (mw.to_3x3() @ Vector(a[k + 3:k + 6]))
        if d.length < 1e-9:
            continue
        out.append((o, d.normalized(), a[k + 6] * mw.to_scale()[0]))
    return out


def _arm_parts(scene, turn) -> list:
    return [o for o in joints.moved_objects(scene, turn) if o.type == "MESH"] if turn is not None else []


def claws(scene, turn=None, slide=None) -> list[Vector]:
    """The centres of the arm's claws (round faces parallel to its axis, away from its hub), world, now; one point per
    claw (on the plane through the arm's axis point at right angles to it)."""
    if turn is None:
        slide, turn = arm_joints(scene)
    if turn is None:
        return []
    o, d = joints.axis_world(turn)
    out = []
    for part in _arm_parts(scene, turn):
        for po, pd, r in _round_axes(part):
            if abs(pd.dot(d)) < math.cos(PARALLEL * 4) or not 8 * MM <= r <= 80 * MM:
                continue
            p = po - d * (po - o).dot(d)
            if (p - o).length < 40 * MM:
                continue
            if all((p - q).length > 2 * MM for q in out):
                out.append(p)
    return out


def _signed(a: Vector, b: Vector, axis: Vector) -> float:
    return math.atan2(a.cross(b).dot(axis), a.dot(b))


def read_grip(scene, mach) -> tuple[float | None, str]:
    """(the arm's turn from now that puts a claw on the spindle's axis, or None; a note)."""
    slide, turn = arm_joints(scene)
    if turn is None:
        return None, "make the arm first"
    o, d = joints.axis_world(turn)
    g = gauge_frame(scene, mach, change_values(scene, mach)).translation
    s = g - o
    s = s - d * s.dot(d)
    found = claws(scene, turn, slide)
    if not found or s.length < 1e-6:
        return None, "the arm has no round claws the app can read: type the grip angle"
    best = None
    for p in found:
        v = p - o
        ang = _signed(v, s, d)
        if best is None or abs(ang) < abs(best) - 1e-3 or (abs(abs(ang) - abs(best)) <= 1e-3 and ang > best):
            best = ang
    return best, ""


def default_stroke(scene) -> float:
    """The pull-out stroke for the spindle tool's holder: its taper and pull stud and a little more."""
    from ..core import tools as tcore
    from . import tools
    c = settings(scene)
    row = next((t for t in c.tools if t.obj is not None and t.obj is c.tool), None)
    holder = tools.spec_of(row).holder if row is not None else "BT30"
    taper = tcore._TAPERS.get(holder) or tcore._TAPERS["BT30"]
    return round((taper[3] + taper[4] + STROKE_EXTRA) / MM) * MM


def make_arm(scene, objs, origin: Vector, direction: Vector, ref=None) -> str:
    """The arm's two joints on ``objs`` about/along the hub's axis (``origin``, ``direction``: world, now); '' or why
    not. Reads the grip angle and sets the stroke."""
    c = settings(scene)
    objs = [o for o in objs if o is not None]
    if not objs:
        return "Select the arm (its part or subassembly) first"
    d = Vector(direction).normalized()
    up = spindle_axis(scene)
    if d.dot(up) < 0:
        d = -d
    if d.angle(up) > math.radians(5):
        return ("The hub's axis is not parallel with the spindle: click a round face of the hub that turns about the "
                "arm's axis")
    remove_arm(scene)
    slide_name = ""
    try:
        slide = joints.create(scene, "SLIDE", objs, Vector(origin), d, name="Changer arm stroke", ref=ref)
        slide_name = slide.name
        slide.motion[ARM_TAG] = "arm"
        turn = joints.create(scene, "ROTATE", objs, Vector(origin), d, name="Changer arm turn", ref=ref)
        turn.motion[ARM_TAG] = "arm"
        turn_name = turn.name
    except RuntimeError as exc:
        half = scene.fresing.joints.get(slide_name) if slide_name else None
        if half is not None:                           # no half-made arm (bug hunt 0068 row 19a)
            joints.remove(scene, half)
        return str(exc)
    for name in (slide_name, turn_name):
        j = scene.fresing.joints.get(name)
        j.use_limits = False
    c["_busy"] = True
    c.arm_slide, c.arm_turn = slide_name, turn_name
    c.arm_rest = 0.0
    c.arm_stroke = default_stroke(scene)
    del c["_busy"]
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError:
        mach = None
    if mach is not None:
        g, _note = read_grip(scene, mach)
        if g is not None:
            c["_busy"] = True
            c.arm_grip = g
            del c["_busy"]
    gcode.setup_changed(scene)
    return ""


def remove_arm(scene) -> None:
    c = settings(scene)
    for name in (c.arm_turn, c.arm_slide):
        j = scene.fresing.joints.get(name) if name else None
        if j is not None:
            joints.remove(scene, j)
    c["_busy"] = True
    c.arm_slide = c.arm_turn = ""
    del c["_busy"]


# ---------------------------------------------------------------------------
# set-up: the pots
# ---------------------------------------------------------------------------

def _pot_root(ob, carousel) -> object:
    """The pot: ``ob`` or its subassembly when that holds no other part of ``ob``'s shape (one pot), below the
    carousel's moving parts."""
    best = ob
    p = ob.parent
    while p is not None and p.get(build.PROP_KIND) in build.MODEL_KINDS:
        if carousel is not None and any(m.obj is p for m in carousel.members):
            break
        if build.logical_parent(p) is None:
            break
        same = [x for x in p.children_recursive if x is not ob and x.type == "MESH" and x.data is ob.data]
        if same:
            break
        best = p
        p = p.parent
    return best


def remove_pots(scene) -> None:
    """The pots' tip joints go (also those of pockets removed since)."""
    c = settings(scene)
    names = {p.tip_joint for p in c.pockets if p.tip_joint}
    names |= {j.name for j in scene.fresing.joints if j.motion is not None and j.motion.get(ARM_TAG) == "pot"}
    for name in names:
        j = scene.fresing.joints.get(name)
        if j is not None:
            joints.remove(scene, j)
    for p in c.pockets:
        p["_busy"] = True
        p.tip_joint = ""
        del p["_busy"]


def make_pots(scene, pot, origin: Vector, direction: Vector) -> str:
    """Click on the hinge of the pot at the change station: a pocket in every pot round the magazine (``pocket_count``
    of them, numbered from the station pocket) and a joint that tips each pot about its hinge. '' or why not."""
    from . import toolchange
    c = settings(scene)
    car = toolchange.carousel(scene)
    if car is None:
        return "Pick the magazine's rotate joint (Carousel) first"
    slide, turn = arm_joints(scene)
    if turn is None:
        return "Make the arm first (select it, then 'Click the arm's hub')"
    if not gcode._carries(car, pot):
        return f"'{gcode.label(pot)}' is not turned by '{car.name}': click the hinge of a pot on the magazine"
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError as exc:
        return str(exc)
    hinge_o, hinge_d = Vector(origin), Vector(direction).normalized()
    # where the tool's gauge line must be in the tipped pot: under the arm's second grip
    g = gauge_frame(scene, mach, change_values(scene, mach))
    rot = half_turn(arm_frame(scene, turn, slide))
    g_pot = rot @ g.translation
    up = (rot.to_3x3() @ g.to_3x3() @ Vector((0, 0, 1))).normalized()
    # back to the pot as it lies now (not tipped): the tip that leaves the gauge point nearest to the pot's shape
    angle = float(c.pot_tip_angle)
    verts = gcode._world_points(pot)
    best = None
    for sign in (1.0, -1.0):
        r = Matrix.Rotation(-sign * angle, 3, hinge_d)
        pt = hinge_o + r @ (g_pot - hinge_o)
        dist = float(((verts - pt) ** 2).sum(axis=1).min()) if len(verts) else 0.0
        if best is None or dist < best[0]:
            best = (dist, sign, pt, (r @ up).normalized())
    _dist, sign, g0, d0 = best
    data = pot.data
    root = _pot_root(pot, car)
    n = max(2, int(c.pocket_count))
    way = -1.0 if c.pockets_reverse else 1.0
    a_o, a_d = joints.axis_world(car)
    centre = sum((Vector(b) for b in pot.bound_box), Vector()) / 8
    centre = pot.matrix_world @ centre
    others = [o for o in bpy.data.objects if o.type == "MESH" and o.data is data and gcode._carries(car, o)]
    num0 = max(1, int(c.station))
    found = []                                     # every pot first: a wrong click leaves the old pockets as they were
    for k in range(n):                             # (bug hunt 0068 row 19a)
        r = Matrix.Rotation(way * TC.TURN * k / n, 3, a_d)
        want = a_o + r @ (centre - a_o)
        part = min(others, key=lambda o: (o.matrix_world @ (sum((Vector(b) for b in o.bound_box), Vector()) / 8)
                                          - want).length) if others else None
        if part is None or (part.matrix_world @ (sum((Vector(b) for b in part.bound_box), Vector()) / 8)
                            - want).length > 20 * MM:
            return (f"No pot found {k} pockets on from the station: the magazine's pots must be parts of the same "
                    "shape, evenly round its axis (check 'Pockets' and 'Number the other way')")
        others.remove(part)
        found.append((k, r, part))
    remove_pots(scene)
    c.pockets.clear()
    made = []
    for k, r, part in found:
        inv = part.matrix_world.inverted()
        p = c.pockets.add()
        p["_busy"] = True
        p.number = num0 + k
        p.obj = part
        p.uid = part.get(build.PROP_UID, "")
        p.loc = inv @ (a_o + r @ (g0 - a_o))
        p.dir = (inv.to_3x3() @ (r @ d0)).normalized()
        del p["_busy"]
        made.append((p.number, _pot_root(part, car) if part is not pot else root, a_o + r @ (hinge_o - a_o),
                     r @ hinge_d, part))
    names = {}
    try:
        with joints._batch(scene):
            for num, obj, ho, hd, part in made:
                j = joints.create(scene, "ROTATE", [obj], ho, hd, name=f"Pot {num} tip", ref=part)
                j.motion[ARM_TAG] = "pot"
                j.use_limits = False
                names[num] = j.name
    except RuntimeError as exc:
        return str(exc)
    for p in c.pockets:
        p["_busy"] = True
        p.tip_joint = names.get(p.number, "")
        del p["_busy"]
    # which way the joints turn to tip the pot down
    j = scene.fresing.joints.get(names[num0])
    _o, jd = joints.axis_world(j)
    st = c.pockets[0]
    w = toolchange.pocket_world(st)
    c["_busy"] = True
    c.station = num0
    c.pot_tip = True
    if w is not None:
        c.pot_tip_sign = 1.0 if (Matrix.Rotation(angle, 3, jd) @ w[1]).dot(up) >= 0 else -1.0
    del c["_busy"]
    c.pockets_index = 0
    toolchange.pockets_changed(scene)
    return ""


# ---------------------------------------------------------------------------
# problems and the check
# ---------------------------------------------------------------------------

def problems(scene) -> list[str]:
    """What keeps the double-arm changer from working, in plain words."""
    from . import toolchange
    c = settings(scene)
    out = []
    slide, turn = arm_joints(scene)
    if turn is None:
        out.append("Make the arm: select it, then 'Click the arm's hub'")
    if c.change_mode == "STAY":
        out.append("The head must go to the change position for the arm (Change position: 'Z up only' or "
                   "'Change position')")
    elif c.change_mode == "Z":
        try:
            mach = gcode.Machine(scene)
        except gcode.SetupError:
            mach = None
        if mach is not None and any(mach.moves_tool[:2]):
            out.append("X or Y moves the spindle: set 'Head goes' to 'Change position' so the spindle is where the "
                       "arm grips")
    if c.pot_tip and c.pockets and any(not p.tip_joint or _joint(scene, p.tip_joint) is None for p in c.pockets):
        out.append("Some pots have no tip joint: press 'Click the hinge' again")
    if not c.pockets:
        out.append("No pots yet: 'Click the hinge' on the pot at the change station (tipping pots), or 'Click "
                   "pockets'")
    elif toolchange.carousel(scene) is None:
        out.append("Pick the magazine's rotate joint (Carousel)")
    return out


def check(scene) -> list[tuple[bool, str]]:
    """[(fits?, line)]: the arm, the claws, the station pot and the stroke measured in the change pose."""
    from ..core import tools as tcore
    from . import tools, toolchange
    c = settings(scene)
    out = [(False, p) for p in problems(scene)]
    slide, turn = arm_joints(scene)
    try:
        mach = gcode.Machine(scene)
    except gcode.SetupError as exc:
        return out + [(False, str(exc))]
    if turn is None:
        return out
    vals = change_values(scene, mach)
    g = gauge_frame(scene, mach, vals)
    gz = (g.to_3x3() @ Vector((0, 0, 1))).normalized()
    frame = arm_frame(scene, turn, slide)
    az = (frame.to_3x3() @ Vector((0, 0, 1))).normalized()
    ang = az.angle(gz)
    out.append((ang <= PARALLEL, f"Arm's axis to the spindle: {math.degrees(ang):.2f}°"
                + ("" if ang <= PARALLEL else " – it must be parallel")))
    # the claw that grips the spindle's tool, at the grip angle
    found = claws(scene, turn, slide)
    if found:
        now = joints.get_value(turn)
        a_now = arm_at(scene, turn, slide, now)
        a_grip = arm_at(scene, turn, slide, float(c.arm_grip))
        pts = [a_grip @ (a_now.inverted() @ p) for p in found]

        def off(p):
            v = p - g.translation
            return (v - gz * v.dot(gz)).length
        miss = min(off(p) for p in pts)
        out.append((miss <= FIT, f"Claw on the spindle's axis at the grip angle: {miss / MM:.2f} mm off"
                    + ("" if miss <= FIT else " – change the grip angle, or the change position")))
    else:
        out.append((True, "The arm has no round claws to measure: check the grip by eye"))
    # the pot at the station, tipped, under the second grip
    rot = half_turn(frame)
    st = next((p for p in c.pockets if p.number == c.station), None)
    car = toolchange.carousel(scene)
    if st is not None and st.obj is not None:
        values = {}
        if car is not None:
            try:
                _s, carousel_vals, _n = toolchange.stations(scene, mach)
                values = station_values(scene, st, carousel_vals.get(st.number), True)
            except Exception:
                values = station_values(scene, st, None, True)
        else:
            values = station_values(scene, st, None, True)
        pw = world_at(scene, st.obj, values)
        pt = pw @ Vector(st.loc)
        pd = (pw.to_3x3() @ Vector(st.dir)).normalized()
        want = rot @ g.translation
        miss = (pt - want).length
        out.append((miss <= FIT, f"Pot {st.number} at the station under the second grip: {miss / MM:.2f} mm off"
                    + ("" if miss <= FIT else " – check the station, the hinge or the change position")))
        tilt = pd.angle(gz)
        out.append((tilt <= PARALLEL, f"Tool in the station pot to the spindle: {math.degrees(tilt):.2f}°"
                    + ("" if tilt <= PARALLEL else (" – tick 'Pots tip down'" if not c.pot_tip else
                                                    " – check the tip angle"))))
    # the stroke clears the spindle tool's taper
    row = next((t for t in c.tools if t.obj is not None and t.obj is c.tool), None)
    holder = tools.spec_of(row).holder if row is not None else ""
    taper = tcore._TAPERS.get(holder)
    if taper:
        need = taper[3] + taper[4]
        ok = float(c.arm_stroke) >= need
        out.append((ok, f"Pull-out stroke {c.arm_stroke / MM:.0f} mm, the {holder} taper and pull stud "
                        f"{need / MM:.0f} mm" + ("" if ok else " – too short: the tools stay in")))
    return out


def check_poses(scene) -> list[tuple[float, dict]]:
    """[(seconds, joint values)] of one change for 'Check' to play in the view: rest, grip, pull, turn, push, back."""
    c = settings(scene)
    slide, turn = arm_joints(scene)
    if turn is None:
        return []
    rest, grip, s = float(c.arm_rest), float(c.arm_grip), -float(c.arm_stroke)
    out = []
    st = next((p for p in c.pockets if p.number == c.station), None)
    tj = _joint(scene, st.tip_joint) if st is not None and c.pot_tip else None
    tip = tip_value(scene) if tj is not None else None

    def pose(t, a, b, pot=None):
        v = {turn.name: a, slide.name: b}
        if tj is not None:
            v[tj.name] = pot if pot is not None else 0.0
        out.append((t, v))
    pose(0.0, rest, 0.0, 0.0)
    t = 0.0
    if tip is not None:
        t += c.pot_tip_time
        pose(t, rest, 0.0, tip)
    for dt, a, b in ((c.arm_grip_time, grip, 0.0), (c.arm_stroke_time, grip, s), (c.arm_swap_time, grip + math.pi, s),
                     (c.arm_stroke_time, grip + math.pi, 0.0), (c.arm_grip_time, rest + math.pi, 0.0)):
        t += dt
        pose(t, a, b, tip)
    if tip is not None:
        t += c.pot_tip_time
        pose(t, rest + math.pi, 0.0, 0.0)
    return out


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

def _copy(name, src, parent, local, col, tag: str, n: int):
    ob = bpy.data.objects.new(name, src.data)
    ob[gcode.TAG] = "tool"
    ob[tag] = n
    ob[build.PROP_KIND] = "cnc"
    ob.hide_select = True
    for i, slot in enumerate(src.material_slots):
        if slot.link == "OBJECT" and i < len(ob.material_slots):
            ob.material_slots[i].link = "OBJECT"
            ob.material_slots[i].material = slot.material
    col.objects.link(ob)
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = local
    return ob


class _Bake:
    """The double-arm changes of one program step while they are baked."""

    def __init__(self, scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until, warnings, merge, name,
                 offsets):
        from . import toolchange
        self.scene, self.mach, self.sch, self.f0, self.fps = scene, mach, sch, f0, fps
        self.vkeys, self.jkeys, self.jstate, self.busy, self.merge = vkeys, jkeys, jstate, busy_until, merge
        self.warnings, self.name = warnings, name
        self.c = settings(scene)
        self.ch = sch.timing.changer
        self.slide, self.turn = arm_joints(scene)
        self.col = gcode._collection(scene)
        self.rows = {p.number: p for p in self.c.pockets}
        self.car = toolchange.carousel(scene)
        start = sch.first_tool or (self.ch.start_tool if self.ch is not None else 0)
        self.start = start
        numbers = sorted({c.tool for c in sch.changes if c.tool} | {n for _s, n, _t, _d in sch.tool_events if n}
                         | {n for n in sch.pocket_table} | ({start} if start else set()))
        self.later = toolchange.earlier_keys(vkeys)     # a second program step of the build (task 0071)
        self.show, self.away, w = gcode.tool_objects(scene, mach, prog, numbers, offsets)
        warnings += [f"'{name}': {x}" for x in w]
        self.spindle = mach.tool
        self.frame = arm_frame(scene, self.turn, self.slide)
        self.rot = half_turn(self.frame)
        try:
            _st, self.values, _n = toolchange.stations(scene, mach)
        except Exception:
            self.values = {}
        self.pots: dict = {}            # (T, pocket) -> copy in the pot
        self.arms: dict = {}            # (T, 0/1) -> copy on the arm
        self.ws: dict = {}              # T -> W (the tool in the spindle at the change)

    def f(self, t):
        return self.f0 + t * self.fps

    def key(self, ob, t, hidden, frame=None):
        keys = self.vkeys.setdefault(ob.name, [(1, bool(ob.hide_render), "CONSTANT", "AUTO")])
        self.merge(keys, self.f(t) if frame is None else frame, hidden, "CONSTANT")

    def in_spindle(self, n):
        return self.show.get(n, self.spindle) if n else self.spindle

    def w_spindle(self, n, t):
        """The tool's world matrix in the spindle at the change (head where the schedule has it at ``t``; None: at the
        set-up's change position)."""
        if n not in self.ws:
            vals = change_values(self.scene, self.mach, self.sch.point_at(t) if t is not None else None)
            self.ws[n] = world_at(self.scene, self.in_spindle(n), vals)
        return self.ws[n]

    def _made(self, tag: str, n: int, parent, extra: tuple = ()):
        """A copy an earlier program step of this build made (task 0071: one per tool and pot, or arm side)."""
        for o in bpy.data.objects:
            if o.get(gcode.TAG) == "tool" and o.get(tag) == n and o.parent is parent and \
                    all(o.get(k) == v for k, v in extra):
                return o
        return None

    def pot_copy(self, n, pocket, t):
        hit = self.pots.get((n, pocket))
        if hit is not None:
            return hit
        p = self.rows.get(pocket)
        if p is None or p.obj is None:
            return None
        hit = self._made("fr_cnc_pocket", n, p.obj) if self.later else None
        if hit is not None:
            self.pots[(n, pocket)] = hit
            return hit
        pw = world_at(self.scene, p.obj, station_values(self.scene, p, self.values.get(pocket), True))
        local = pw.inverted() @ self.rot @ self.w_spindle(n, t)
        ob = _copy(f"FR tool T{n} pot {pocket}", self.in_spindle(n), p.obj, local, self.col, "fr_cnc_pocket", n)
        ob.hide_render = ob.hide_viewport = True
        self.pots[(n, pocket)] = ob
        return ob

    def arm_copy(self, n, side, theta, t):
        k = (side + int(round((theta - float(self.c.arm_grip)) / math.pi))) % 2
        hit = self.arms.get((n, k))
        if hit is None and self.later:
            hit = self._made("fr_cnc_carry", n, self.turn.motion, (("fr_arm_side", k),))
            if hit is not None:
                self.arms[(n, k)] = hit
        if hit is not None:
            return hit
        w = self.w_spindle(n, t)
        if side == 1:
            w = self.rot @ w
        local = arm_at(self.scene, self.turn, self.slide, theta).inverted() @ w
        ob = _copy(f"FR tool T{n} on arm", self.in_spindle(n), self.turn.motion, local, self.col, "fr_cnc_carry", n)
        ob["fr_arm_side"] = k
        ob.hide_render = ob.hide_viewport = True
        self.arms[(n, k)] = ob
        return ob

    def joint_keys(self, j, rows) -> None:
        """rows: [(t, value, interp)] in time order."""
        from . import animation
        keys = self.jkeys.setdefault(j.name, [(1, self.jstate[j.name], "CONSTANT", "AUTO")])
        interp, ez = animation.EASING["SMOOTH"]
        for t, v, smooth in rows:
            self.merge(keys, self.f(t), v, interp if smooth else "CONSTANT", ez if smooth else "AUTO")
        if rows:
            self.jstate[j.name] = rows[-1][1]
            self.busy[j.name] = max(self.busy.get(j.name, 0), int(math.ceil(self.f(rows[-1][0]))))

    def run(self) -> None:
        from . import toolchange
        sch, c = self.sch, self.c
        # tools of the CAD model away from the spindle: shown by their copies (they move between pots)
        for n, part in self.away.items():
            keys = self.vkeys.setdefault(part.name, [(1, bool(part.hide_render), "CONSTANT", "AUTO")])
            self.merge(keys, 1, True, "CONSTANT")
        start = self.start
        for n, ob in self.show.items():
            if ob is not self.spindle:
                self.key(ob, 0.0, n != start)
        self.key(self.spindle, 0.0, start in self.show and self.show[start] is not self.spindle)
        first = next((x for x in sch.changes if x.kind == "arm"), None)
        t_first = first.arm_times()["grip"][1] if first is not None else None
        for n, pk in sch.pocket_table.items():
            if n == start:
                continue
            cp = self.pot_copy(n, pk, t_first)
            if cp is not None:
                if cp.name not in self.vkeys:          # in its pot from the first frame (a later step's new copy:
                    self.vkeys[cp.name] = [(1, self.later, "CONSTANT", "AUTO")]       # from the step's start)
                self.key(cp, 0.0, False)
        rest = float(c.arm_rest)
        grip = float(c.arm_grip)
        stroke = float(c.arm_stroke)
        turn_rows, slide_rows, tips, car_rows = [], [], {}, []
        cur = start
        hand = None
        for ch in sch.changes:
            if ch.length <= 0 and ch.old == ch.tool:
                continue
            old = ch.old if ch.old else cur
            if ch.kind != "arm":                         # a tool without a pot: by hand
                if ch.hand is not None:
                    if hand is None:
                        hand = toolchange._Hand(self.scene, self.mach, self.col)
                    for n in (old, ch.tool):
                        hand.carry_copy(n, self.in_spindle(n), self.col)
                    hand.change(old, ch, self.f0, self.fps, lambda ob, f, h: self.key(ob, 0, h, frame=f))
                self.key(self.in_spindle(old), ch.drop, True)
                self.key(self.in_spindle(ch.tool), ch.swap, False)
                cur = ch.tool
                continue
            times = ch.arm_times()
            base = rest + (ch.index % 2) * math.pi
            th = base + (grip - rest)
            g0, g1 = times["grip"]
            pu0, pu1 = times["pull"]
            sw0, sw1 = times["swap"]
            ps0, ps1 = times["push"]
            b0, b1 = times["back"]
            turn_rows += [(g0, base, True), (g1, th, False), (sw0, th, True), (sw1, th + math.pi, False),
                          (b0, th + math.pi, True), (b1, base + math.pi, False)]
            slide_rows += [(pu0, 0.0, True), (pu1, -stroke, False), (ps0, -stroke, True), (ps1, 0.0, False)]
            pk = ch.new_pocket
            # hand-overs: spindle -> arm and pot -> arm when the claws close, arm -> spindle and arm -> pot when
            # the arm has pushed them in
            if old:
                a_old = self.arm_copy(old, 0, th, g1)
                self.key(self.in_spindle(old), g1, True)
                self.key(a_old, g1, False)
                self.key(a_old, ps1, True)
                cp = self.pot_copy(old, pk, g1)
                if cp is not None:
                    self.key(cp, ps1, False)
            a_new = self.arm_copy(ch.tool, 1, th, g1)
            cp = self.pot_copy(ch.tool, pk, g1)
            if cp is not None:
                self.key(cp, g1, True)
            self.key(a_new, g1, False)
            self.key(a_new, ps1, True)
            self.key(self.in_spindle(ch.tool), ps1, False)
            for t0, t1, pocket, down in ch.tips():
                tips.setdefault(pocket, []).append((t0, t1, down))
            for t0, t1, v0, v1 in ch.turns():
                car_rows += [(t0, v0, True), (t1, v1, False)]
            cur = ch.tool
        if hand is not None:
            hand.write()
        if self.turn is not None and turn_rows:
            self.joint_keys(self.turn, turn_rows)
            self.joint_keys(self.slide, slide_rows)
        tip = tip_value(self.scene)
        for pocket, rows in tips.items():
            p = self.rows.get(pocket)
            tj = _joint(self.scene, p.tip_joint) if p is not None and c.pot_tip else None
            if tj is None:
                continue
            out = []
            for t0, t1, down in sorted(rows):
                out += [(t0, 0.0 if down else tip, True), (t1, tip if down else 0.0, False)]
            self.joint_keys(tj, out)
        if self.car is not None and car_rows:
            if self.car.follows:
                self.warnings.append(f"'{self.name}': the magazine joint '{self.car.name}' follows another joint: it "
                                     "does not turn")
            else:
                self.joint_keys(self.car, sorted(car_rows, key=lambda r: r[0]))
        rec = [(self.f0, start if start in self.show else 0)]
        rec += [(self.f0 + swap * self.fps, n) for swap, n, _t, _d in sch.tool_events]
        gcode._record_schedule(self.scene, rec)


def tool_keys(scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until, warnings, merge, name,
              offsets=None) -> None:
    """Keys of one program step's double-arm changes: the tools' copies, the arm, the pots, the magazine."""
    slide, turn = arm_joints(scene)
    if turn is None:
        warnings.append(f"'{name}': the double-arm changer has no arm (4 Motion > CNC machine > Tool changes)")
        from . import toolchange
        return toolchange.tool_keys_plain(scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until,
                                          warnings, merge, name, offsets)
    _Bake(scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until, warnings, merge, name, offsets).run()


def spindle_holds(sch) -> list[tuple[float, float, float]]:
    """[(t0, t1, t_end)]: the spindle turns to its orient angle from t0 to t1 and stays there until t_end."""
    out = []
    for c in sch.changes:
        if c.kind != "arm":
            continue
        span = c.orient_span()
        times = c.arm_times()
        if span is None:
            span = (c.start, c.start)
        out.append((span[0], span[1], times["push"][1] if "push" in times else c.start + c.length))
    return out


# ---------------------------------------------------------------------------
# the generic test model (data/test_atc.step, tools/make_test_atc.py): PC check, test tour, guide pictures, tests
# ---------------------------------------------------------------------------

TEST_MODEL = "test_atc.step"
TEST_PROGRAM = """%
(DOUBLE-ARM TEST: THREE BT30 TOOLS, TN BEFORE EVERY M6)
(T1 D=10. CR=0. - flat end mill)
(T2 D=8. CR=4. - ball end mill)
(T3 D=6. CR=0. TAPER=118deg - drill)
G21 G90 G54
T1 M6
T2
S8000 M3
G0 X-40 Y-30 Z5
G1 Z-1 F500
G1 X40 F1200
G0 Z20
M5
T2 M6
T3
S8000 M3
G0 X0 Y0 Z5
G1 Z-1 F300
G1 X30 Y20 F1000
G0 Z20
M5
T3 M6
T1
S6000 M3
G0 X20 Y10 Z5
G1 Z-2 F200
G0 Z20
M5
T1 M6
G0 X0 Y0 Z20
M30
%
"""
TEST_HUB = ((-0.13, 0.0, 0.3), (0.0, 0.0, 1.0))           # the arm's hub: a point on its axis, the axis
TEST_HINGE = ((-0.31, 0.0, 0.35), (0.0, 1.0, 0.0))        # the station pot's hinge


def _named(scene, name):
    hits = sorted((o for o in scene.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    if not hits:
        raise RuntimeError(f"the test model has no part '{name}'")
    return hits[0]


def test_station_pot(scene):
    """The pot towards the arm (the change station) on the test model."""
    pots = [o for o in scene.objects if o.get(build.PROP_NAME) == "POT"]
    return min(pots, key=lambda o: (o.matrix_world @ (sum((Vector(b) for b in o.bound_box), Vector()) / 8)
                                    - Vector((-0.28, 0.0, 0.4))).length)


def set_up_test_model(scene, b, tip: bool = True, spindle: bool = True, arm: bool = True) -> None:
    """The imported test model as a mill with a double-arm changer, step ``b`` running its program: X/Y/Z, the spindle
    (a motor), the magazine, the tool list (T1 in the spindle, T2 in pot 2, T3 drawn in pot 5, BT30), the arm and the
    pots (``tip``: tipping pots, else pockets clicked and filled)."""
    from . import toolchange, tools
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _named(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    t1 = _named(scene, "TOOL T1 BT30 FLAT D10")
    if spindle:
        j = joints.create(scene, "ROTATE", [t1], Vector((0, 0, 0.3)), Vector((0, 0, 1)), name="Spindle")
        joints.set_motor(scene, j, True)
    joints.create(scene, "ROTATE", [_named(scene, "MAGAZINE.ASM")], Vector((-0.46, 0, 0.35)), Vector((0, 0, 1)),
                  name="Magazine")
    gcode.use_tool(scene, t1)
    gcode.use_workpiece(scene, _named(scene, "STOCK 160x120x30"))
    gcode.find_axes(scene)
    c = settings(scene)
    if not spindle:
        c.spindle_joint = ""
    why = gcode.problem(scene)
    if why:
        raise RuntimeError(why)
    c.changer = "ARM"
    c.change_mode = "Z"
    mach = gcode.Machine(scene)
    c.change_pos = tuple(x * MM for x in mach.machine_of(mach.values))
    gcode.tools_from_program(scene, b)
    rows = {n: tools.row_of(scene, n) for n in (1, 2, 3)}
    if not all(rows.values()):
        raise RuntimeError("Tools from the program did not add T1 … T3")
    tools.use_part(scene, rows[1], t1)
    tools.use_part(scene, rows[2], _named(scene, "TOOL T2 BT30 BALL D8"))
    for n, stick in ((1, 40), (2, 35), (3, 50)):
        rows[n].holder = "BT30"
        rows[n].length = stick * MM
    rows[3].pocket = 5
    c.carousel_joint = "Magazine"
    c.pocket_count = 12
    c.station = 1
    if not arm:
        return
    part = _named(scene, "CHANGER ARM")
    why = make_arm(scene, [part], Vector(TEST_HUB[0]), Vector(TEST_HUB[1]), ref=part)
    if why:
        raise RuntimeError(why)
    if tip:
        why = make_pots(scene, test_station_pot(scene), Vector(TEST_HINGE[0]), Vector(TEST_HINGE[1]))
    else:
        toolchange.add_pocket(scene, test_station_pot(scene), Vector((-0.26, 0.0, 0.4)))
        why = toolchange.fill_carousel(scene)
    if why:
        raise RuntimeError(why)
    gcode.step_changed(scene, b)
