"""Joints: rotate or slide subassemblies about an axis.

How a joint is built in Blender (all native, so playback and background renders
need no add-on code):

    base (the subassembly it sits on)
     └─ joint frame   empty on the axis, local Z = axis direction, never moves
         └─ joint motion  empty that turns about / slides along its Z
              └─ moving subassemblies (re-parented, CAD parent remembered)

The joint value is a custom property ``fr_value`` on the motion empty (radians
or metres) with min/max from the joint limits; a driver copies it into the
motion's Z rotation or Z location. Animation keys go on ``fr_value``.

Joints whose base is moved by another joint follow it: that gives chains
(a trolley on a luffing boom). Changes to the joint structure are made in the
CAD pose (every joint at 0, no free moves) and the pose is restored after.

Stacks (several joints on one subassembly, the moves add up): a new joint added
to objects that already move with joint A *rides on* A – its frame is parented
to A's motion empty and the chosen objects move to the new joint's motion:

    A frame └─ A motion └─ B frame └─ B motion └─ the subassembly

The newer joint's axis moves with the older one (slew, then luff). Nothing extra
is stored: "B rides on A" is ``B.frame.parent is A.motion``, so projects made
before stacks open unchanged. Removing a joint from a stack puts what it moved
and the joints riding on it down onto what it sat on.

Couplings (task 0012): a joint can *follow* another one (gears, telescopes, jaws,
spindles, racks, rolling wheels). The follower's ``fr_value`` gets a driver
``a * k + c`` reading the leader's ``fr_value``: a *simple expression*, which
Blender evaluates without Python, so files work with "Auto Run Python Scripts" off.
``k`` is the ratio in internal units (rad / m), worked out from what the owner
types (turns per turn, mm per mm, mm per turn, degrees per mm); ``c`` is the
offset. Chains A -> B -> C work (B's value is driven, C reads it); loops are refused.
A follower is never moved by hand, by poses or by animation steps; its limits only
warn. The structure is changed in the CAD pose with the coupling drivers muted.

Motors: a rotate joint marked "Motor" has no limits and turns without end; the
"Run motor" animation step turns it at a speed (rpm) for a while.
"""

from __future__ import annotations

import contextlib
import math

import bpy
from mathutils import Matrix, Vector

from . import build

VALUE = "fr_value"
EPS = 1e-7
# Matrices are stored in single precision by Blender: differences below this are rounding,
# not a move (1e-5 m = 0.01 mm; 1e-5 in a rotation entry = 0.0006 degrees).
MOVE_EPS = 1e-5


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------

def to_display(kind: str, value: float) -> float:
    """Internal value (rad / m) -> what the user reads (degrees / mm)."""
    return math.degrees(value) if kind == "ROTATE" else value * 1000.0


def from_display(kind: str, value: float) -> float:
    return math.radians(value) if kind == "ROTATE" else value / 1000.0


def unit_label(kind: str) -> str:
    return "°" if kind == "ROTATE" else "mm"


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def joints(scene):
    return scene.fresing.joints


def find(scene, name: str):
    return scene.fresing.joints.get(name)


def is_valid(j) -> bool:
    return j.frame is not None and j.motion is not None and j.motion.parent is j.frame


def joint_of_object(scene, ob):
    """The joint that moves ``ob`` directly (ob is one of its members), or None."""
    p = ob.parent
    if p is None or p.get(build.PROP_KIND) != "joint":
        return None
    for j in scene.fresing.joints:
        if j.motion is p:
            return j
    return None


def joint_for_empty(scene, ob):
    for j in scene.fresing.joints:
        if ob is j.frame or ob is j.motion:
            return j
    return None


def members(j) -> list:
    return [m.obj for m in j.members if m.obj is not None]


# ---------------------------------------------------------------------------
# stacks: joints riding on other joints
# ---------------------------------------------------------------------------

def _is_motion(ob) -> bool:
    return ob is not None and ob.get(build.PROP_KIND) == "joint"


def rides_on(scene, j):
    """The joint whose motion carries ``j`` (``j`` sits on top of it in a stack), or None."""
    p = j.frame.parent if j.frame is not None else None
    if not _is_motion(p):
        return None
    for other in scene.fresing.joints:
        if other.motion is p:
            return other
    return None


def riders(scene, j) -> list:
    """Joints riding directly on ``j`` (their frame sits on its motion)."""
    if j.motion is None:
        return []
    return [r for r in scene.fresing.joints if r.frame is not None and r.frame.parent is j.motion]


def depth(scene, j) -> int:
    """How many joints ``j`` rides on (0 for a joint that sits on a part)."""
    d = 0
    seen = {j.name}
    below = rides_on(scene, j)
    while below is not None and below.name not in seen:
        d += 1
        seen.add(below.name)
        below = rides_on(scene, below)
    return d


def all_riders(scene, j) -> list:
    """Every joint above ``j`` in its stack."""
    out, todo, seen = [], riders(scene, j), {j.name}
    while todo:
        r = todo.pop(0)
        if r.name in seen:
            continue
        seen.add(r.name)
        out.append(r)
        todo += riders(scene, r)
    return out


def moved_objects(scene, j) -> list:
    """Everything ``j`` moves directly: its members and, through the joints riding on it, theirs."""
    out = []
    todo, seen = [j], set()
    while todo:
        x = todo.pop(0)
        if x.name in seen:
            continue
        seen.add(x.name)
        out += members(x)
        todo += riders(scene, x)
    return out


def tree_order(scene) -> tuple[list[int], dict[int, int]]:
    """Joint indices in list order with every stack under the joint it rides on, and each one's depth."""
    js = list(scene.fresing.joints)
    by_motion = {j.motion.name: i for i, j in enumerate(js) if j.motion is not None}
    kids: dict[int, list] = {}
    roots = []
    for i, j in enumerate(js):
        p = j.frame.parent if j.frame is not None else None
        below = by_motion.get(p.name) if _is_motion(p) else None
        if below is None or below == i:
            roots.append(i)
        else:
            kids.setdefault(below, []).append(i)
    order: list[int] = []
    depths: dict[int, int] = {}

    def walk(i, d):
        if i in depths:
            return
        order.append(i)
        depths[i] = d
        for k in kids.get(i, []):
            walk(k, d + 1)

    for r in roots:
        walk(r, 0)
    for i in range(len(js)):            # a broken loop (never made by the app): still list everything
        if i not in depths:
            walk(i, 0)
    return order, depths


def stack_info(scene, objs) -> tuple:
    """(joint, reason): the joint a new joint on ``objs`` would ride on (all of them move directly
    with it), or None; reason is non-empty when that cannot be decided (a mixed selection)."""
    owners = [(ob, joint_of_object(scene, ob)) for ob in objs if ob is not None]
    moving = [(ob, o) for ob, o in owners if o is not None]
    if not moving:
        return None, ""
    first_ob, first = moving[0]

    def label(ob):
        return ob.get(build.PROP_NAME, ob.name)

    for ob, o in owners:
        if o is None:
            return None, (f"'{label(first_ob)}' already moves with joint '{first.name}' and '{label(ob)}' "
                          "does not: add the joint to them one at a time")
        if o.name != first.name:                     # (list items are new Python objects each time: no 'is')
            return None, (f"'{label(first_ob)}' moves with joint '{first.name}' and '{label(ob)}' with "
                          f"'{o.name}': add the joint to them one at a time")
    return first, ""


# ---------------------------------------------------------------------------
# values and limits
# ---------------------------------------------------------------------------

TURN = 2.0 * math.pi
# A motor turns without end. Blender keeps animation keys and driver results in single
# precision: 10,000 turns (62,832 rad) is still to 0.004 rad, and 12 rpm for 13 hours.
MOTOR_RANGE = 10000 * TURN
# A follower is never stopped by its limits (they only warn): the value keeps this range.
FOLLOW_RANGE = (10000 * TURN, 100000.0)


def is_motor(j) -> bool:
    return j.kind == "ROTATE" and bool(j.is_motor)


def get_value(j) -> float:
    """The joint's value (rad / m). A follower's is worked out from the joint at the top of its chain:
    the copy Blender's driver writes into the follower is not always up to date (drivers run on
    several threads); its motion is, because that reads the top joint directly."""
    if j.motion is None:
        return 0.0
    if j.follows:
        fc = _coupling_fcurve(j)
        if fc is not None and not fc.mute:
            top, k, c = chain_affine(j.id_data, j)
            if top is not None and top.motion is not None:
                return k * float(top.motion.get(VALUE, 0.0)) + c
    return float(j.motion.get(VALUE, 0.0))


def limits(j) -> tuple[float, float]:
    """The range the joint may be set to (rad / m)."""
    if is_motor(j):
        return (-MOTOR_RANGE, MOTOR_RANGE)
    if not j.use_limits:
        return (-math.radians(3600), math.radians(3600)) if j.kind == "ROTATE" else (-1000.0, 1000.0)
    lo, hi = (j.rot_min, j.rot_max) if j.kind == "ROTATE" else (j.slide_min, j.slide_max)
    return (min(lo, hi), max(lo, hi))


def outside_limits(j, value: float) -> bool:
    """True when ``value`` is beyond the limits the owner set (a little rounding allowed)."""
    if not j.use_limits or is_motor(j):
        return False
    lo, hi = limits(j)
    tol = 1e-6 if j.kind == "ROTATE" else 1e-7
    return value < lo - tol or value > hi + tol


def clamp(j, value: float) -> float:
    lo, hi = limits(j)
    return min(max(value, lo), hi)


def set_value(j, value: float, use_limits: bool = True) -> float:
    if j.motion is None:
        return 0.0
    if j.follows:
        fc = _coupling_fcurve(j)
        if fc is not None and not fc.mute:
            return get_value(j)              # its leader decides (only the CAD pose mutes that and sets 0)
    v = clamp(j, value) if use_limits else value
    j.motion[VALUE] = float(v)
    j.motion.update_tag()
    return v


def apply_limits(j, model_size: float = 10.0, clamp: bool = True) -> None:
    """Push the joint limits into the slider of the value property.

    Blender clamps keyed and driven values to the property's min/max: a motor gets a range
    without a practical end, a follower one its limits never cut (they only warn)."""
    if j.motion is None:
        return
    lo, hi = limits(j)
    following = bool(j.follows)
    if j.kind == "ROTATE":
        soft = (lo, hi) if j.use_limits and not is_motor(j) else (-math.pi, math.pi)
        subtype = "ANGLE"
        if following:
            lo, hi = -FOLLOW_RANGE[0], FOLLOW_RANGE[0]
    else:
        reach = max(0.1, model_size)
        soft = (lo, hi) if j.use_limits else (-reach, reach)
        subtype = "DISTANCE"
        if following:
            lo, hi = -FOLLOW_RANGE[1], FOLLOW_RANGE[1]
    if following:
        desc = "Follows another joint: move that one (this joint's set-up shows which)"
    elif is_motor(j):
        desc = "Motor angle, in degrees (turns without end; 360° is one turn). Drag it, or type a number"
    elif j.kind == "ROTATE":
        desc = "Angle of the joint, in degrees (0 = CAD position). Drag it, or type a number"
    else:
        desc = "Position of the joint, in mm (0 = CAD position). Drag it, or type a number"
    ui = j.motion.id_properties_ui(VALUE)
    ui.update(min=lo, max=hi, soft_min=soft[0], soft_max=soft[1], subtype=subtype,
              step=100 if j.kind == "ROTATE" else 1, precision=1 if j.kind == "ROTATE" else 1,
              description=desc)
    cur = get_value(j)
    if clamp and not following and j.use_limits and (cur < lo or cur > hi):
        set_value(j, cur)


# ---------------------------------------------------------------------------
# couplings: one joint follows another
# ---------------------------------------------------------------------------

# what the owner types as the ratio, per (leader type, follower type)
RATIO_UNITS = {
    ("ROTATE", "ROTATE"): "turns per turn",
    ("SLIDE", "SLIDE"): "mm per mm",
    ("ROTATE", "SLIDE"): "mm per turn",
    ("SLIDE", "ROTATE"): "° per mm",
}
DEFAULT_RATIOS = {
    ("ROTATE", "ROTATE"): 1.0,                     # same speed
    ("SLIDE", "SLIDE"): 1.0,                       # telescope section: as far again
    ("ROTATE", "SLIDE"): 5.0,                      # a 5 mm ball screw
    ("SLIDE", "ROTATE"): 360.0 / (math.pi * 100),  # a wheel of Ø100 mm rolling along
}
COUPLING_PATH = f'["{VALUE}"]'


def leader(scene, j):
    """The joint ``j`` follows, or None (it moves by itself, or the leader is gone)."""
    return scene.fresing.joints.get(j.follows) if j.follows else None


def followers(scene, j) -> list:
    """Joints that follow ``j`` directly."""
    return [x for x in scene.fresing.joints if x.follows and x.follows == j.name]


def all_followers(scene, j) -> list:
    """Every joint ``j`` drives, also through other followers (A drives B drives C)."""
    out, todo, seen = [], followers(scene, j), {j.name}
    while todo:
        x = todo.pop(0)
        if x.name in seen:
            continue
        seen.add(x.name)
        out.append(x)
        todo += followers(scene, x)
    return out


def driver_of(scene, j):
    """The joint at the top of ``j``'s chain of leaders (the one that really moves it): ``j`` itself
    when it moves by itself; None when the chain is broken (a leader gone) or loops."""
    x, seen = j, set()
    while x is not None and x.follows:
        if x.name in seen:
            return None
        seen.add(x.name)
        x = leader(scene, x)
    return x


def ratio_unit(lead_kind: str, kind: str) -> str:
    return RATIO_UNITS[(lead_kind, kind)]


def default_ratio(lead_kind: str, kind: str) -> float:
    return DEFAULT_RATIOS[(lead_kind, kind)]


def factor(lead_kind: str, kind: str, ratio: float) -> float:
    """The ratio as the owner types it -> follower value per leader value in internal units."""
    if lead_kind == kind:
        return float(ratio)
    if lead_kind == "ROTATE":                       # mm per turn -> m per rad
        return float(ratio) / 1000.0 / TURN
    return math.radians(float(ratio)) * 1000.0      # degrees per mm -> rad per m


def offset(j) -> float:
    """The follower's value when its leader is at 0 (rad / m)."""
    return float(j.couple_offset_angle if j.kind == "ROTATE" else j.couple_offset_dist)


def expression(k: float, c: float) -> str:
    """The driver expression: plain arithmetic, so Blender evaluates it without Python."""
    e = f"a * {float(k)!r}"
    if c > 0:
        e += f" + {float(c)!r}"
    elif c < 0:
        e += f" - {-float(c)!r}"
    return e


def follow_check(scene, j, name: str) -> str:
    """'' when ``j`` may follow the joint called ``name`` ('' = by itself), else the reason."""
    if not name:
        return ""
    if name == j.name:
        return "A joint cannot follow itself: pick another joint"
    lead = find(scene, name)
    if lead is None:
        return f"There is no joint called '{name}'"
    if not is_valid(lead):
        return f"'{name}' is broken (its arrow was deleted): remove it first"
    chain = [name]
    x = lead
    while x is not None and x.follows:
        if x.follows == j.name:
            via = " → ".join(f"'{n}'" for n in chain[1:])
            through = f" (through {via})" if via else ""
            return (f"'{name}' already follows '{j.name}'{through}: two joints cannot follow each other. "
                    f"Let one of them move by itself")
        if x.follows in chain:
            break                                   # an old loop further up: not this joint's doing
        chain.append(x.follows)
        x = find(scene, x.follows)
    return ""


def chain_affine(scene, j):
    """(top, K, C): ``j``'s value = K * top's value + C, through its whole chain of leaders (the
    ratios and offsets of a chain combine into one straight line). top is None when a leader is
    gone or the chain loops; ``j`` itself (K 1, C 0) when it moves by itself."""
    k, c = 1.0, 0.0
    x, seen = j, set()
    while x.follows:
        if x.name in seen:
            return None, 1.0, 0.0
        seen.add(x.name)
        lead = leader(scene, x)
        if lead is None:
            return None, 1.0, 0.0
        c += k * offset(x)
        k *= factor(lead.kind, x.kind, x.couple_ratio)
        x = lead
    return x, k, c


def _channel(kind: str) -> tuple[str, int]:
    return ("rotation_euler", 2) if kind == "ROTATE" else ("location", 2)


def _coupling_fcurves(j) -> list:
    """A follower's drivers: on its value (what the panel shows) and on its motion (what moves)."""
    ad = j.motion.animation_data if j.motion is not None else None
    if ad is None:
        return []
    out = [fc for fc in (ad.drivers.find(COUPLING_PATH),) if fc is not None]
    path, index = _channel(j.kind)
    fc = ad.drivers.find(path, index=index)
    if fc is not None and fc.driver.type == "SCRIPTED":
        out.append(fc)
    return out


def _coupling_fcurve(j):
    ad = j.motion.animation_data if j.motion is not None else None
    return ad.drivers.find(COUPLING_PATH) if ad is not None else None


def _remove_coupling_driver(j) -> None:
    if j.motion is None:
        return
    try:
        j.motion.driver_remove(COUPLING_PATH)
    except TypeError:
        pass


def _scripted(fc, source, expr: str) -> None:
    for m in list(fc.modifiers):                    # (Blender may add an identity generator)
        fc.modifiers.remove(m)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for v in list(drv.variables):
        drv.variables.remove(v)
    var = drv.variables.new()
    var.name = "a"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = source
    var.targets[0].data_path = COUPLING_PATH
    drv.expression = expr


def _write_one(scene, j) -> bool:
    """One joint's drivers. A follower's value AND its motion both read the joint at the top of its
    chain (never the follower's own value, nor a leader in between): Blender evaluates drivers on
    several threads and does not always finish a driven value before another driver reads it, which
    showed as a follower one frame behind. Returns False when the chain is broken (no coupling then)."""
    if j.motion is None:
        return True
    _remove_coupling_driver(j)
    top, k, c = chain_affine(scene, j) if j.follows else (j, 1.0, 0.0)
    if not j.follows or top is None or top.motion is None:
        path, index = _channel(j.kind)
        ad = j.motion.animation_data
        fc = ad.drivers.find(path, index=index) if ad is not None else None
        if fc is None or fc.driver.type != "AVERAGE" or not driver_biased(j):
            _add_driver(j.motion, j.kind)               # back to "the motion follows its own value"
        j.motion.update_tag()
        return not j.follows
    expr = expression(k, c)
    _scripted(j.motion.driver_add(COUPLING_PATH), top.motion, expr)
    path, index = _channel(j.kind)
    for p, i in (("rotation_euler", 2), ("location", 2)):
        try:
            j.motion.driver_remove(p, i)
        except TypeError:
            pass
    fc = j.motion.driver_add(path, index)
    _scripted(fc, top.motion, expression(k, c + BIAS))           # never a small number (see BIAS)
    _unbias(fc, 1.0)
    j.motion.update_tag()
    return True


def write_coupling(scene, j) -> bool:
    """Make the drivers of ``j`` and of every joint that follows it (through it) match their settings.
    Returns False when ``j`` follows a joint that is missing (it then moves by its own value)."""
    ok = _write_one(scene, j)
    for x in all_followers(scene, j):
        _write_one(scene, x)
    return ok


def _set_raw(j, **values) -> None:
    """Set joint settings without their update callbacks (no re-check, no driver rebuild)."""
    for k, v in values.items():
        j[k] = v
        if k == "follows":
            j["_old_follows"] = v           # the panel's callback goes back to this one when refused


def _free(scene, j) -> None:
    """``j`` stops following and stays exactly where it is (also beyond its limits)."""
    v = get_value(j)
    _set_raw(j, follows="")
    write_coupling(scene, j)                     # its own drivers, and those of the joints behind it
    set_value(j, v, use_limits=False)
    apply_limits(j, _model_size(scene), clamp=False)


def set_follows(scene, j, name: str, ratio: float | None = None, offset_value: float | None = None) -> None:
    """Make ``j`` follow the joint called ``name``, or move by itself again (``name`` = '').

    A new combination of joint types starts with its usual ratio (1, 5 mm per turn...) and no
    offset; ``ratio`` / ``offset_value`` (as typed: turns per turn, mm per turn, ° per mm...;
    offset in rad / m) set them at once. Raises RuntimeError with the reason when not allowed.
    A built animation is taken off first (as for every change to the joints)."""
    reason = follow_check(scene, j, name)
    if reason:
        raise RuntimeError(reason)
    from . import animation
    if animation.has_keys(scene):
        animation.clear_keys(scene)
    if not name:
        if j.follows:
            _free(scene, j)
        _update(scene)
        return
    old = leader(scene, j)
    lead = find(scene, name)
    if old is None or old.kind != lead.kind:
        _set_raw(j, couple_ratio=default_ratio(lead.kind, j.kind), couple_offset_angle=0.0,
                 couple_offset_dist=0.0)
    if ratio is not None:
        _set_raw(j, couple_ratio=float(ratio))
    if offset_value is not None:
        _set_raw(j, **{"couple_offset_angle" if j.kind == "ROTATE" else "couple_offset_dist": float(offset_value)})
    _set_raw(j, follows=name)
    write_coupling(scene, j)
    apply_limits(j, _model_size(scene))
    _update(scene)


def refresh_couplings(scene) -> list[str]:
    """Rewrite every coupling driver (after a model update, a type change...). A follower whose
    leader is gone (or which would loop) moves by itself from then on; returns those warnings."""
    warnings = []
    size = _model_size(scene)
    for j in scene.fresing.joints:
        if j.follows and follow_check(scene, j, j.follows):
            warnings.append(f"Joint '{j.name}' followed '{j.follows}', which is gone or not possible any more: "
                            "it moves by itself now")
            _set_raw(j, follows="")
    for j in scene.fresing.joints:
        if j.motion is None:
            continue
        _write_one(scene, j)
        if j.follows:
            apply_limits(j, size)
    _update(scene)
    return warnings


def driven_value(scene, j, values: dict | None = None) -> float:
    """The value ``j`` has when the joints that move by themselves are at ``values`` (name -> value;
    a joint not in it: its current value). Works without the scene being updated."""
    values = values or {}
    top, k, c = chain_affine(scene, j)
    if top is None:                                 # a leader is gone: the driver is stale too
        return get_value(j)
    return k * values.get(top.name, get_value(top)) + c


def couplings_simple(scene) -> bool:
    """True when every coupling driver is a simple expression (works with scripts disabled)."""
    for j in scene.fresing.joints:
        for fc in _coupling_fcurves(j):
            if not fc.driver.is_simple_expression:
                return False
    return True


def _mute_couplings(scene, mute: bool, only=None) -> list[str]:
    """Mute (or un-mute) the coupling drivers; returns the motion names whose drivers changed.

    A muted follower's motion goes to its CAD place (its driven channel at 0)."""
    changed = []
    for j in scene.fresing.joints:
        if j.motion is None or (only is not None and j.motion.name not in only):
            continue
        fcs = [fc for fc in _coupling_fcurves(j) if fc.mute != mute]
        if not fcs:
            continue
        for fc in fcs:
            fc.mute = mute
        if mute:
            path, index = _channel(j.kind)
            getattr(j.motion, path)[index] = 0.0
        changed.append(j.motion.name)
        j.motion.update_tag()
    return changed


def set_motor(scene, j, on: bool) -> None:
    """Mark a rotate joint as a motor: no limits, it turns without end."""
    if on and j.kind != "ROTATE":
        raise RuntimeError("Only a rotate joint can be a motor")
    _set_raw(j, is_motor=bool(on))
    if on:
        _set_raw(j, use_limits=False)
    elif j.kind == "ROTATE":
        # no longer a motor: back within ±10 turns, at the same angle (no visible jump)
        v = get_value(j)
        lo, hi = limits(j)
        if not lo <= v <= hi:
            set_value(j, math.remainder(v, TURN), use_limits=False)
    apply_limits(j, _model_size(scene))


# ---------------------------------------------------------------------------
# the CAD pose (all joints at 0, no free moves)
# ---------------------------------------------------------------------------

def model_objects(scene):
    return [ob for ob in scene.objects if ob.get(build.PROP_KIND) in build.MODEL_KINDS]


def _is_identity(m: Matrix) -> bool:
    ident = Matrix.Identity(4)
    return all(abs(m[r][c] - ident[r][c]) < MOVE_EPS for r in range(4) for c in range(4))


def _same(a: Matrix, b: Matrix) -> bool:
    return all(abs(a[r][c] - b[r][c]) < MOVE_EPS for r in range(3) for c in range(4))


def free_moves(scene) -> dict:
    """{object name: delta} for every object moved away from its rest position."""
    out = {}
    for ob in model_objects(scene):
        rest = build.rest_basis(ob)
        basis = ob.matrix_basis
        if _same(basis, rest):              # cheap test first: almost nothing is moved
            continue
        try:
            delta = rest.inverted() @ basis
        except ValueError:
            continue
        if not _is_identity(delta):
            out[ob.name] = delta
    return out


def apply_free_moves(scene, deltas: dict, reset_others: bool = True) -> None:
    for ob in model_objects(scene):
        d = deltas.get(ob.name)
        if d is not None:
            ob.matrix_basis = build.rest_basis(ob) @ d
        elif reset_others:
            rest = build.rest_basis(ob)
            if not _same(ob.matrix_basis, rest):
                ob.matrix_basis = rest


def _update(scene) -> None:
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass


@contextlib.contextmanager
def cad_pose(scene):
    """Temporarily put the model in its CAD pose; restore joint values and free moves after."""
    from . import animation
    animation.clear_keys(scene)            # baked keys would fight the pose; rebuilt on demand
    values = {j.name: get_value(j) for j in scene.fresing.joints if not j.follows}
    deltas = free_moves(scene)
    muted = _mute_couplings(scene, True)     # a follower with an offset is not at 0 when its leader is
    for j in scene.fresing.joints:
        set_value(j, 0.0, use_limits=False)      # through set_value: tags the driver for an update
    apply_free_moves(scene, {}, reset_others=True)
    from . import linkages
    links = linkages.cad_enter(scene)        # mechanisms (task 0014): every link on its CAD place
    _update(scene)
    try:
        yield
    finally:
        linkages.cad_leave(scene, links)
        apply_free_moves(scene, {n: d for n, d in deltas.items() if n in bpy.data.objects}, reset_others=False)
        for j in scene.fresing.joints:
            if j.name in values and j.motion is not None:
                set_value(j, values[j.name], use_limits=False)
        _mute_couplings(scene, False, only=muted)
        _update(scene)


# ---------------------------------------------------------------------------
# building blocks
# ---------------------------------------------------------------------------

def axis_matrix(origin: Vector, direction: Vector) -> Matrix:
    d = Vector(direction).normalized()
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(Vector(origin)) @ rot


def _parent_world(ob) -> Matrix:
    if ob.parent is None:
        return Matrix.Identity(4)
    return ob.parent.matrix_world @ ob.matrix_parent_inverse


def _set_world(ob, world: Matrix, parent_world: Matrix | None = None) -> None:
    pw = _parent_world(ob) if parent_world is None else parent_world
    ob.matrix_basis = pw.inverted() @ world


def _moved_by(ob, motion) -> bool:
    """True when ``motion`` is above ``ob`` in the real (Blender) parent chain."""
    p = ob
    while p is not None:
        if p is motion:
            return True
        p = p.parent
    return False


def _model_size(scene) -> float:
    s = scene.fresing
    if s.bounds_valid:
        return max(0.1, (Vector(s.bounds_max) - Vector(s.bounds_min)).length)
    return 5.0


def _new_empty(name: str, kind: str, collection, size: float, display: str) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = display
    ob.empty_display_size = size
    ob[build.PROP_KIND] = kind
    ob.lock_location = (True,) * 3
    ob.lock_rotation = (True,) * 3
    ob.lock_scale = (True,) * 3
    collection.objects.link(ob)
    return ob


# Blender 5.2.3 writes 0 instead of a driver's result when that result is a small positive number (below
# about 0.0001: 0.1 mm for a slide, found by task 0026 – a joint 0.05 mm from its CAD position sat at it). So
# no motion driver ever gives a small number: it works out ``value + BIAS`` (an average with a constant second
# input, or the expression plus BIAS), and a generator modifier on the driver takes BIAS off again. No Python:
# files keep working with scripts off.
BIAS = 2.0
BIAS_PROP = "fr_bias"


def _unbias(fc, factor: float) -> None:
    """Generator on a motion driver: result = factor * raw - BIAS."""
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    g = fc.modifiers.new("GENERATOR")
    g.mode = "POLYNOMIAL"
    g.poly_order = 1
    g.coefficients = (-BIAS, factor)


def _add_driver(motion, kind: str) -> None:
    path, index = ("rotation_euler", 2) if kind == "ROTATE" else ("location", 2)
    for p, i in (("rotation_euler", 2), ("location", 2)):
        try:
            motion.driver_remove(p, i)
        except TypeError:
            pass
    motion[BIAS_PROP] = BIAS
    fc = motion.driver_add(path, index)
    drv = fc.driver
    drv.type = "AVERAGE"                    # no Python expression: works with scripts disabled
    var = drv.variables.new()
    var.name = "v"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = motion
    var.targets[0].data_path = f'["{VALUE}"]'
    var = drv.variables.new()               # (value + BIAS) / 2 ...
    var.name = "b"
    var.type = "SINGLE_PROP"
    var.targets[0].id_type = "OBJECT"
    var.targets[0].id = motion
    var.targets[0].data_path = f'["{BIAS_PROP}"]'
    _unbias(fc, 2.0)                        # ... * 2 - BIAS = value


def driver_biased(j) -> bool:
    """True when the joint's motion driver has the small-number fix (see BIAS)."""
    ad = j.motion.animation_data if j.motion is not None else None
    path, index = _channel(j.kind)
    fc = ad.drivers.find(path, index=index) if ad is not None else None
    if fc is None:
        return True
    return any(m.type == "GENERATOR" and abs(m.coefficients[0] + BIAS) < 1e-9 for m in fc.modifiers)


def upgrade_drivers(scene) -> int:
    """Projects made before 0.2.30: give every joint's motion driver the small-number fix. Returns how many."""
    n = 0
    for j in scene.fresing.joints:
        if j.motion is None or driver_biased(j):
            continue
        if j.follows:
            _write_one(scene, j)
        else:
            _add_driver(j.motion, j.kind)
            j.motion.update_tag()
        n += 1
    return n


def _attach(ob, motion, motion_world: Matrix) -> None:
    """Make ``ob`` move with ``motion`` (call in the CAD pose)."""
    world = ob.matrix_world.copy()
    if not isinstance(ob.get(build.PROP_CAD_PARENT), bpy.types.Object):
        if ob.parent is None or ob.parent.get(build.PROP_KIND) in build.JOINT_KINDS:
            raise RuntimeError(f"{ob.name} has no CAD parent")
        ob[build.PROP_CAD_PARENT] = ob.parent
    ob.parent = motion
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = motion_world.inverted() @ world
    build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)


def _detach(ob) -> None:
    """Put ``ob`` back under its CAD parent at its CAD place (call in the CAD pose)."""
    cad_parent = ob.get(build.PROP_CAD_PARENT)
    if not isinstance(cad_parent, bpy.types.Object):
        return
    ob.parent = cad_parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = build.cad_basis(ob)
    build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
    del ob[build.PROP_CAD_PARENT]


def unique_name(scene, base: str) -> str:
    names = {j.name for j in scene.fresing.joints}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def check_members(scene, objs, base, joint=None, allow_empty: bool = False) -> str:
    """'' if ``objs`` can be moved by a joint sitting on ``base``, else a reason.

    ``allow_empty``: a joint may move nothing directly (the bottom of a stack moves the joints on it)."""
    if not objs and not allow_empty:
        return "Select the subassemblies that should move"
    from . import cylinders
    for ob in objs:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            return f"{ob.name} is not part of the model"
        cyl = cylinders.cylinder_of_object(scene, ob)
        if cyl is not None:
            return (f"'{ob.get(build.PROP_NAME, ob.name)}' is part of cylinder '{cyl.name}', which moves it. "
                    "Give the arm the joint: the cylinder follows")
    reason = cylinders.joint_conflict(scene, objs, base, joint)
    if reason:
        return reason
    from . import linkages
    reason = linkages.joint_conflict(scene, objs, base, joint)
    if reason:
        return reason
    for ob in objs:
        if build.logical_parent(ob) is None:
            return "The whole model cannot be a moving part; select subassemblies inside it"
        if base is not None and (base is ob or _moved_by(base, ob)):
            return f"'{ob.get(build.PROP_NAME, ob.name)}' cannot move itself: it carries the base of this joint"
    if joint is not None and base is not None and joint.motion is not None and _moved_by(base, joint.motion):
        return "A joint cannot sit on something it moves"
    return ""


def default_base(objs):
    """The CAD parent shared by the moving objects (the first one's parent when they differ)."""
    first = build.logical_parent(objs[0])
    return first


# ---------------------------------------------------------------------------
# public operations
# ---------------------------------------------------------------------------

def create(scene, kind: str, objs, origin, direction, name: str = "", base=None, ref=None,
           stack: bool = True, allow_empty: bool = False, frame_world: Matrix | None = None):
    """New joint moving ``objs`` about/along the axis. Returns the joint item.

    ``origin``/``direction`` are world space in the current pose; they are stored relative
    to ``ref`` (the part that was clicked, default the base), so picking works with other
    joints moved or the model turned.

    ``stack``: when no base is given and the objects already move with joint A, the new joint
    rides on A (its frame on A's motion) and the moves add up. ``allow_empty``: build a joint that
    moves nothing directly (model updates rebuild the bottom of a stack that way).
    ``frame_world``: the exact axis matrix (world, current pose) instead of origin + direction. A
    direction alone leaves the turn of the arrow about its own axis open (unstable for a vertical
    axis); a joint riding on it would turn with it, so model updates pass the whole matrix.
    """
    objs = [ob for ob in objs if ob is not None]
    # members inside other members move with them anyway
    objs = [ob for ob in objs if not any(o is not ob and _is_cad_ancestor(o, ob) for o in objs)]
    if base is None and stack and objs:
        below, reason = stack_info(scene, objs)
        if reason:
            raise RuntimeError(reason)
        if below is not None:
            base = below.motion                 # an Object: stays valid when the joint list grows
    if base is None and objs:
        base = default_base(objs)
    reason = check_members(scene, objs, base, allow_empty=allow_empty)
    if reason:
        raise RuntimeError(reason)
    if not objs and base is None:
        raise RuntimeError("A joint that moves nothing needs something to sit on")
    s = scene.fresing
    build.ensure_bases(scene)
    label = objs[0].get(build.PROP_NAME, objs[0].name) if objs else (name or "Joint")
    name = unique_name(scene, name or f"{label} {'rotate' if kind == 'ROTATE' else 'slide'}")
    size = _model_size(scene) * 0.08
    collection = (base.users_collection[0] if base is not None and base.users_collection
                  else objs[0].users_collection[0])
    ref = ref if ref is not None else base
    if frame_world is not None:
        local = ref.matrix_world.inverted() @ frame_world if ref is not None else frame_world.copy()
    else:
        local = _local_axis(ref, origin, direction)
    with cad_pose(scene):
        for ob in objs:                         # an object is moved directly by one joint only
            other = joint_of_object(scene, ob)
            if other is not None:
                _remove_member(other, ob)
                _detach(ob)
        _update(scene)
        frame = _new_empty(f"Joint {name}", "joint_frame", collection, size, "SINGLE_ARROW")
        motion = _new_empty(f"Joint {name} (motion)", "joint", collection, size * 0.4, "PLAIN_AXES")
        frame.parent = base
        frame.matrix_parent_inverse = Matrix.Identity(4)
        world = _world_axis(ref, local)
        base_world = base.matrix_world.copy() if base is not None else Matrix.Identity(4)
        frame.matrix_basis = base_world.inverted() @ world
        motion.parent = frame
        motion.matrix_parent_inverse = Matrix.Identity(4)
        motion.matrix_basis = Matrix.Identity(4)
        motion.rotation_mode = "XYZ"
        motion[VALUE] = 0.0
        _add_driver(motion, kind)
        try:
            motion.hide_set(True)
        except RuntimeError:
            pass
        j = s.joints.add()
        j["name"] = name                        # no rename callback on creation
        j["_old_name"] = name
        j.kind = kind
        j.frame = frame
        j.motion = motion
        frame["fr_joint"] = name
        motion["fr_joint"] = name
        for ob in objs:
            _attach(ob, motion, world)
            m = j.members.add()
            m.obj = ob
    sync_base(j)
    apply_limits(j, _model_size(scene))
    s.joints_index = len(s.joints) - 1
    return j


def _local_axis(ref, origin, direction) -> Matrix:
    m = axis_matrix(origin, direction)
    return ref.matrix_world.inverted() @ m if ref is not None else m


def _world_axis(ref, local: Matrix) -> Matrix:
    m = ref.matrix_world @ local if ref is not None else local.copy()
    # keep it a clean rigid frame (no scale/shear from the reference)
    loc, rot, _scale = m.decompose()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def _is_cad_ancestor(a, b) -> bool:
    p = build.logical_parent(b)
    while p is not None:
        if p is a:
            return True
        p = build.logical_parent(p)
    return False


def _remove_member(j, ob) -> None:
    for i in reversed(range(len(j.members))):
        if j.members[i].obj is ob or j.members[i].obj is None:
            j.members.remove(i)


def add_members(scene, j, objs) -> int:
    objs = [ob for ob in objs if ob is not None and ob not in members(j)]
    objs = [ob for ob in objs if not any(_is_cad_ancestor(o, ob) for o in members(j) + objs if o is not ob)]
    reason = check_members(scene, objs, j.frame.parent if j.frame else None, j)
    if reason:
        raise RuntimeError(reason)
    above = {x.name for x in all_riders(scene, j)}
    for ob in objs:
        other = joint_of_object(scene, ob)
        if other is not None and other.name in above:
            # it already moves with this joint, through the joint on top: taking it off that one
            # would lose that move
            raise RuntimeError(f"'{ob.get(build.PROP_NAME, ob.name)}' already moves with this joint, through "
                               f"'{other.name}' on top of it")
    with cad_pose(scene):
        for ob in objs:
            other = joint_of_object(scene, ob)
            if other is not None:
                _remove_member(other, ob)
                _detach(ob)
        _update(scene)
        world = j.motion.matrix_world.copy()
        for ob in objs:
            _attach(ob, j.motion, world)
            j.members.add().obj = ob
    return len(objs)


def _release(scene, below, objs) -> None:
    """Objects leave their joint (call in the CAD pose): onto the joint ``below`` it when it rode
    on one (the moves of the stack under it stay), else back to their CAD parent."""
    for ob in objs:
        _detach(ob)
    if below is None or not objs:
        return
    _update(scene)
    world = below.motion.matrix_world.copy()
    for ob in objs:
        _attach(ob, below.motion, world)
        below.members.add().obj = ob


def remove_members(scene, j, objs) -> int:
    objs = [ob for ob in objs if ob in members(j)]
    with cad_pose(scene):
        below = rides_on(scene, j)
        for ob in objs:
            _remove_member(j, ob)
        _release(scene, below, objs)
    return len(objs)


def _true_frame_world(scene, r, seen=None):
    """Where ``r``'s frame belongs in the CAD pose, worked out from a part it moves (needed when
    the joint under it is broken: its own matrices then hang somewhere in the world)."""
    seen = seen or set()
    if r.name in seen:
        return None
    seen.add(r.name)
    for o in members(r):
        cad_parent = build.logical_parent(o)
        if cad_parent is None:
            continue
        cad_world = cad_parent.matrix_world @ build.cad_basis(o)
        return cad_world @ build.rest_basis(o).inverted()      # its motion sits on its frame in the CAD pose
    for up in riders(scene, r):
        w = _true_frame_world(scene, up, seen)
        if w is not None:
            return w @ up.frame.matrix_basis.inverted()
    return None


def _take_out(scene, j) -> None:
    """Everything ``j`` carries goes down onto what it sat on (call in the CAD pose)."""
    if j.frame is not None:
        seat = j.frame.parent
        above = [(r.frame, r.frame.matrix_world.copy()) for r in riders(scene, j)]
    else:
        # broken joint (its arrow was deleted): the joints on it go onto the CAD parent of what they
        # move, at the place their parts say
        moved = moved_objects(scene, j)
        seat = default_base(moved) if moved else None
        above = [(r.frame, _true_frame_world(scene, r) or r.frame.matrix_world.copy()) for r in riders(scene, j)]
    seat_world = seat.matrix_world.copy() if seat is not None else Matrix.Identity(4)
    below = rides_on(scene, j)
    objs = members(j)
    j.members.clear()
    _release(scene, below, objs)
    for frame, world in above:
        frame.parent = seat
        frame.matrix_parent_inverse = Matrix.Identity(4)
        frame.matrix_basis = seat_world.inverted() @ world


def remove(scene, j) -> list[str]:
    """Remove a joint. What it moved goes back to the joint it rode on (or its CAD place);
    joints riding on it move down onto what it sat on; joints that followed it move by themselves
    from now on (they stay where they are). Returns the names of those joints."""
    s = scene.fresing
    from . import animation
    if animation.has_keys(scene):                  # first: the joints go back to where they were before
        animation.clear_keys(scene)
        _update(scene)
    name = j.name
    freed = [x.name for x in followers(scene, j)]
    for fname in freed:                            # before the leader's motion goes: keep their place
        _free(scene, find(scene, fname))
    j = find(scene, name)
    with cad_pose(scene):
        _take_out(scene, j)
        for ob in (j.motion, j.frame):
            if ob is not None:
                bpy.data.objects.remove(ob, do_unlink=True)
        idx = next(i for i, x in enumerate(s.joints) if x == j)
        s.joints.remove(idx)
        for r in s.joints:                         # the joints that rode on it show their new seat
            if r.frame is not None:
                sync_base(r)
    s.joints_index = min(s.joints_index, len(s.joints) - 1)
    refresh_couplings(scene)                       # (nothing should read the removed joint any more)
    return freed


def sync_base(j) -> None:
    """Show the frame's parent in the 'Sits on' field without triggering a move.

    A joint riding on another joint sits on no part: the field stays empty."""
    from . import props
    key = ("base", j.as_pointer())
    props._BUSY.add(key)
    try:
        p = j.frame.parent if j.frame is not None else None
        j.base = None if _is_motion(p) else p
    finally:
        props._BUSY.discard(key)


def set_base(scene, j, base) -> None:
    """Make the joint sit on (move with) another subassembly."""
    reason = check_members(scene, members(j), base, j, allow_empty=True)
    if reason:
        raise RuntimeError(reason)
    with cad_pose(scene):
        world = j.frame.matrix_world.copy()
        j.frame.parent = base
        j.frame.matrix_parent_inverse = Matrix.Identity(4)
        _set_world(j.frame, world, base.matrix_world if base is not None else Matrix.Identity(4))
    sync_base(j)


def axis_world(j) -> tuple[Vector, Vector]:
    m = j.frame.matrix_world
    return m.translation.copy(), (m.to_3x3() @ Vector((0, 0, 1))).normalized()


def set_axis(scene, j, origin, direction, ref=None) -> None:
    """Move the joint axis (world space, current pose); the moving parts stay where they are."""
    ref = ref if ref is not None else j.frame.parent
    local = _local_axis(ref, origin, direction)
    with cad_pose(scene):
        worlds = {ob.name: ob.matrix_world.copy() for ob in members(j)}
        above = [(r.frame, r.frame.matrix_world.copy()) for r in riders(scene, j)]
        new_world = _world_axis(ref, local)
        _set_world(j.frame, new_world)
        for ob in members(j):
            ob.matrix_basis = new_world.inverted() @ worlds[ob.name]
            build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
        for frame, world in above:                  # joints riding on it stay where they are too
            frame.matrix_basis = new_world.inverted() @ world
    from . import cylinders
    _update(scene)
    cylinders.joint_changed(scene, j)              # a cylinder driving it: limits for the new direction


def swap_check(scene, j) -> str:
    """'' if ``j`` can swap places with the joint it rides on, else the reason."""
    below = rides_on(scene, j)
    if below is None:
        return f"'{j.name}' does not ride on another joint"
    if not is_valid(below) or not is_valid(j):
        broken = j.name if not is_valid(j) else below.name
        return f"'{broken}' is broken (its arrow was deleted): remove it first"
    others =[ob.get(build.PROP_NAME, ob.name) for ob in members(below)]
    others += [f"joint '{r.name}'" for r in riders(scene, below) if r.name != j.name]
    if others:
        listed = ", ".join(others[:2]) + (f" +{len(others) - 2}" if len(others) > 2 else "")
        return (f"'{below.name}' also moves {listed}: swapping would make that move with '{j.name}' too. "
                f"Swap works when '{below.name}' moves only what '{j.name}' moves")
    return ""


def swap(scene, j) -> None:
    """Swap ``j`` with the joint it rides on: ``j`` moves to the bottom, the other one rides on it.

    Built in the CAD pose; both keep their axis, type, limits and value. With two slides the
    result is the same; with a rotation it changes (turn-then-slide becomes slide-then-turn)."""
    reason = swap_check(scene, j)
    if reason:
        raise RuntimeError(reason)
    below = rides_on(scene, j)
    with cad_pose(scene):
        seat = below.frame.parent
        seat_world = seat.matrix_world.copy() if seat is not None else Matrix.Identity(4)
        wj = j.frame.matrix_world.copy()           # in the CAD pose a motion sits exactly on its frame
        wb = below.frame.matrix_world.copy()
        objs = [(ob, ob.matrix_world.copy()) for ob in members(j)]
        above = [(r.frame, r.frame.matrix_world.copy()) for r in riders(scene, j)]
        # j goes down onto the seat, the other joint onto j's motion
        j.frame.parent = seat
        j.frame.matrix_parent_inverse = Matrix.Identity(4)
        j.frame.matrix_basis = seat_world.inverted() @ wj
        below.frame.parent = j.motion
        below.frame.matrix_parent_inverse = Matrix.Identity(4)
        below.frame.matrix_basis = wj.inverted() @ wb
        # what j carried now rides on the top joint
        for ob, world in objs:
            ob.parent = below.motion
            ob.matrix_parent_inverse = Matrix.Identity(4)
            ob.matrix_basis = wb.inverted() @ world
            build.set_mat(ob, build.PROP_REST_BASIS, ob.matrix_basis)
            below.members.add().obj = ob
        j.members.clear()
        for frame, world in above:
            frame.parent = below.motion
            frame.matrix_parent_inverse = Matrix.Identity(4)
            frame.matrix_basis = wb.inverted() @ world
    sync_base(j)
    sync_base(below)


def flip(scene, j) -> None:
    o, d = axis_world(j)
    set_axis(scene, j, o, -d)


def set_kind(scene, j, kind: str) -> None:
    """Switch between rotate and slide. Couplings of this joint (as follower or leader) start again
    from the usual ratio of the new combination: the old number meant something else."""
    old_kind = j.kind
    with cad_pose(scene):
        j.kind = kind
        _add_driver(j.motion, kind)
        j.motion.matrix_basis = Matrix.Identity(4)
    if kind != "ROTATE":
        _set_raw(j, is_motor=False)
    set_value(j, 0.0, use_limits=False)
    apply_limits(j, _model_size(scene))
    from . import cylinders
    _update(scene)
    cylinders.joint_changed(scene, j)
    if old_kind != kind:
        touched = ([j] if j.follows else []) + followers(scene, j)
        for x in touched:
            lead = leader(scene, x)
            if lead is not None:
                _set_raw(x, couple_ratio=default_ratio(lead.kind, x.kind), couple_offset_angle=0.0,
                         couple_offset_dist=0.0)
        if touched:
            refresh_couplings(scene)


def rename(scene, j, old: str) -> None:
    for ob in (j.frame, j.motion):
        if ob is not None:
            ob["fr_joint"] = j.name
    if j.frame is not None:
        j.frame.name = f"Joint {j.name}"
    if j.motion is not None:
        j.motion.name = f"Joint {j.name} (motion)"
    for pose in scene.fresing.poses:
        for v in pose.joints:
            if v.joint == old:
                v.joint = j.name
    for anim in scene.fresing.animations:
        for b in anim.blocks:
            if b.joint == old:
                b.joint = j.name
    for x in scene.fresing.joints:                # followers name their leader (the driver needs no change)
        if x.follows and x.follows == old:
            _set_raw(x, follows=j.name)
    from . import gcode
    gcode.renamed_joint(scene, old, j.name)        # the CNC machine's axes (task 0026)
    from . import waycover                        # the way cover keeps following the same joints (task 0034)
    waycover.joint_renamed(scene, old, j.name)


def reset_all(scene) -> None:
    for j in scene.fresing.joints:
        set_value(j, 0.0, use_limits=False)


# ---------------------------------------------------------------------------
# picking an axis on the model
# ---------------------------------------------------------------------------

def axis_from_hit(ob, polygon_index: int, hit: Vector, normal: Vector):
    """Axis under a click: the round face's axis when the click hit a hole/shaft, else the face normal.

    Returns (origin, direction, description); all world space.
    """
    me = ob.data if ob is not None and ob.type == "MESH" else None
    if me is not None and "fr_axes" in me and "fr_axis_faces" in me:
        faces = me["fr_axis_faces"]
        axes = me["fr_axes"]
        for k in range(0, len(faces), 3):
            start, count, idx = faces[k], faces[k + 1], faces[k + 2]
            if start <= polygon_index < start + count:
                a = axes[idx * 7: idx * 7 + 7]
                mw = ob.matrix_world
                o = mw @ Vector(a[0:3])
                d = (mw.to_3x3() @ Vector(a[3:6])).normalized()
                o = o + d * (Vector(hit) - o).dot(d)      # put the axis point where the user clicked
                r = a[6] * mw.to_scale()[0]
                desc = f"round face Ø{r * 2000:.1f} mm" if r > 0 else "round face"
                return o, d, desc
    return Vector(hit), Vector(normal).normalized(), "flat face (axis at right angles to it)"


# ---------------------------------------------------------------------------
# re-import support: joints as plain data
# ---------------------------------------------------------------------------

def to_specs(scene, values: dict | None = None, only=None) -> list[dict]:
    """Joints as plain data (object references by stable part ID). Call in the CAD pose.

    A joint riding on another joint stores that joint's name in ``base_joint`` (and no part)."""
    out = []
    for j in scene.fresing.joints:
        if not is_valid(j) or (only is not None and j.name not in only):
            continue
        base = j.frame.parent
        below = rides_on(scene, j)
        out.append({
            "world": build.mat_to_list(j.frame.matrix_world),
            "name": j.name, "kind": j.kind, "value": (values or {}).get(j.name, get_value(j)),
            "use_limits": j.use_limits, "rot_min": j.rot_min, "rot_max": j.rot_max,
            "slide_min": j.slide_min, "slide_max": j.slide_max,
            "base": base.get(build.PROP_UID) if base is not None and below is None else None,
            "base_joint": below.name if below is not None else None,
            "base_local": build.mat_to_list(j.frame.matrix_basis),
            "members": [ob.get(build.PROP_UID) for ob in members(j)],
            # couplings and motors (task 0012); specs without them come from older versions
            "follows": j.follows, "ratio": j.couple_ratio, "offset_angle": j.couple_offset_angle,
            "offset_dist": j.couple_offset_dist, "motor": bool(j.is_motor),
        })
    return out


def _root(ob):
    while True:
        p = build.logical_parent(ob)
        if p is None:
            return ob
        ob = p


def dissolve_all(scene, root=None) -> list[dict]:
    """Remove the joints (of the model under ``root``, or all) and return them as specs."""
    s = scene.fresing

    def belongs(j) -> bool:
        if root is None:
            return True
        # a bottom joint moves nothing itself: what rides on it tells which model it belongs to
        objs = moved_objects(scene, j) + ([j.frame.parent] if j.frame is not None and j.frame.parent is not None
                                          else [])
        return any(_root(o) is root for o in objs)

    chosen = {j.name for j in s.joints if belongs(j)}
    for name in list(chosen):                 # never split a stack from below: take the joints under it too
        below = rides_on(scene, find(scene, name))
        while below is not None and below.name not in chosen:
            chosen.add(below.name)
            below = rides_on(scene, below)
    values = {j.name: get_value(j) for j in s.joints}
    with cad_pose(scene):
        specs = to_specs(scene, values, only=chosen)
        # top of each stack first: a joint is never removed while another one still rides on it
        _order, depths = tree_order(scene)

        def key(x):                                   # list positions shift on removal; objects do not
            return x.motion or x.frame or x.name

        by_depth = sorted(range(len(s.joints)), key=lambda i: -depths.get(i, 0))
        todo = [key(s.joints[i]) for i in by_depth if s.joints[i].name in chosen]
        for k in todo:
            i = next(n for n, x in enumerate(s.joints) if key(x) == k)
            j = s.joints[i]
            for ob in members(j):
                _detach(ob)
            seat = j.frame.parent if j.frame is not None else None
            for r in riders(scene, j):               # (only when a stack spans two models)
                w = r.frame.matrix_world.copy()
                r.frame.parent = seat
                r.frame.matrix_parent_inverse = Matrix.Identity(4)
                _set_world(r.frame, w, seat.matrix_world if seat is not None else Matrix.Identity(4))
            for ob in (j.motion, j.frame):
                if ob is not None:
                    bpy.data.objects.remove(ob, do_unlink=True)
            s.joints.remove(i)
        s.joints_index = min(s.joints_index, max(0, len(s.joints) - 1))
    return specs


def _stack_order(specs: list[dict]) -> list[dict]:
    """Specs with every joint after the joint it rides on (the order of the list otherwise kept)."""
    names = {sp["name"] for sp in specs}
    out, done, pending = [], set(), list(specs)
    while pending:
        ready = [sp for sp in pending if not sp.get("base_joint") or sp["base_joint"] not in names
                 or sp["base_joint"] in done]
        if not ready:                               # a loop (never made by the app): keep the rest as is
            ready = pending[:]
        for sp in ready:
            out.append(sp)
            done.add(sp["name"])
            pending.remove(sp)
    return out


def _find_last(scene, name: str):
    """The newest joint with this name (a rebuilt joint is added at the end of the list)."""
    for j in reversed(list(scene.fresing.joints)):
        if j.name == name:
            return j
    return None


def rebuild_from_specs(scene, specs: list[dict], by_uid: dict) -> list[str]:
    """Re-create joints on a new model revision (stacks in the right order). Returns warnings."""
    warnings = []
    values: dict[str, float] = {}
    built: list[str] = []
    riders_of: dict[str, list] = {}
    for sp in specs:
        if sp.get("base_joint"):
            riders_of.setdefault(sp["base_joint"], []).append(sp)

    def present(sp) -> list:
        return [o for o in (by_uid.get(u) for u in sp["members"]) if o is not None]

    def stack_objs(sp, seen=None) -> list:
        """What this joint moves, also through the joints riding on it."""
        seen = seen or set()
        if sp["name"] in seen:
            return []
        seen.add(sp["name"])
        out = present(sp)
        for r in riders_of.get(sp["name"], []):
            out += stack_objs(r, seen)
        return out

    for sp in _stack_order(specs):
        objs = present(sp)
        missing = len(sp["members"]) - len(objs)
        carries = bool(stack_objs(sp)) and not objs     # moves nothing itself, but carries other joints
        if not objs and not carries:
            warnings.append(f"Joint '{sp['name']}' removed: its moving parts are no longer in the model")
            continue
        if missing:
            warnings.append(f"Joint '{sp['name']}': {missing} moving part(s) no longer in the model")
        below = _find_last(scene, sp["base_joint"]) if sp.get("base_joint") and sp["base_joint"] in built else None
        base = by_uid.get(sp["base"]) if sp.get("base") else None
        if below is not None:
            base = below.motion
            world = base.matrix_world @ build.list_to_mat(sp["base_local"])
        else:
            if sp.get("base_joint"):
                warnings.append(f"Joint '{sp['name']}': the joint it rode on ('{sp['base_joint']}') is gone; "
                                "it now sits on its CAD parent")
            elif sp.get("base") and base is None:
                warnings.append(f"Joint '{sp['name']}': the part it sat on is gone; it now sits on its CAD parent")
            if base is None:
                base = default_base(objs or stack_objs(sp))
                world = build.list_to_mat(sp["world"])     # where the axis was (the model did not move)
            else:
                world = base.matrix_world @ build.list_to_mat(sp["base_local"])
        origin = world.translation
        direction = world.to_3x3() @ Vector((0, 0, 1))
        try:
            j = create(scene, sp["kind"], objs, origin, direction, name=sp["name"], base=base, stack=False,
                       allow_empty=carries, frame_world=world)
        except RuntimeError as exc:
            warnings.append(f"Joint '{sp['name']}' could not be rebuilt: {exc}")
            continue
        if j.name != sp["name"]:
            j["name"] = sp["name"]
            j["_old_name"] = sp["name"]
            rename(scene, j, sp["name"])
        j.use_limits = sp["use_limits"]
        j.rot_min, j.rot_max = sp["rot_min"], sp["rot_max"]
        j.slide_min, j.slide_max = sp["slide_min"], sp["slide_max"]
        _set_raw(j, is_motor=bool(sp.get("motor", False)) and sp["kind"] == "ROTATE")
        apply_limits(j, _model_size(scene))
        values[j.name] = sp["value"]                # (a follower's driver overrides it while its leader is there)
        built.append(sp["name"])
    s = scene.fresing
    n = len(s.joints)
    rebuilt = [x for x in (sp["name"] for sp in specs) if x in built]
    if len(rebuilt) == len(built) and n >= len(built):
        # the list in the order it had before the update (stacks were built bottom first)
        tail = list(range(n - len(built), n))
        for name in rebuilt:
            i = next(k for k in tail if s.joints[k].name == name)
            s.joints.move(i, n - 1)
    # couplings after every joint is there (a leader may be built after its follower)
    for sp in specs:
        if sp["name"] not in built or not sp.get("follows"):
            continue
        jj = _find_last(scene, sp["name"])
        if jj is None:
            continue
        if find(scene, sp["follows"]) is None:
            warnings.append(f"Joint '{sp['name']}' followed '{sp['follows']}', which is gone: "
                            "it moves by itself now")
            continue
        _set_raw(jj, follows=sp["follows"], couple_ratio=sp.get("ratio", 1.0),
                 couple_offset_angle=sp.get("offset_angle", 0.0), couple_offset_dist=sp.get("offset_dist", 0.0))
    for name, v in values.items():          # values last: every joint was built in the CAD pose
        jj = _find_last(scene, name)
        if jj is not None:
            set_value(jj, v, use_limits=not jj.follows)
    # every coupling driver again: also those of other models whose leader was just rebuilt
    warnings += refresh_couplings(scene)
    return warnings
