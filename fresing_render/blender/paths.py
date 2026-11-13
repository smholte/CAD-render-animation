"""Cables and paths: a cable or wire rope laid over rollers, sheaves and chutes, moved by one cable speed (task 0078).

A cable in a CAD model is one stiff solid, drawn along its route. This file makes it a *path*: straight runs and
round bends over the things it touches (``core/paths.py`` has the maths), drawn by the app, with a look whose
pattern runs along the cable, and with every roller and sheave it touches turning at the cable's speed.

**The cable speed is a joint.** Every cable has a slide joint that moves nothing: its value is the metres of cable
paid out. "Add cable" makes it ("Cable <name>") or takes one that is there (the demo's "Cable travel"). The
existing Move joint and Run motor steps animate it; a Run motor step on it shows its speed in m/min.

**Contacts** (``FRCableContact``, in order along the cable): a ``SHEAVE`` (the cable bends round it and turns it),
a ``ROLLER`` (the cable only rests on it or runs past it: it turns, but does not shape the path), a ``CHUTE`` (a
bend on a part that does not turn) and a ``BEND`` (a bend no single part carries). "From CAD cable" reads them:
the CAD cable's centreline, the round parts near it, and ``core.paths.read_cable``. Each contact keeps its centre
and axis in the coordinates of its **carrier**: the arrow of the joint that turns it (it does not turn along), the
part itself for a chute, the cable part's parent for a bend. The two ends are a point on a part, a free end (a
point that stays with the last contact's carrier) or the place on its first wheel where the cable starts (a drum).

**Everything it touches turns.** A sheave or roller that already has a rotate joint on its axis keeps it: the app
makes it follow the cable's joint (or leaves it alone when it follows something already, and says so when its
ratio differs). Else the app makes the joint (tagged ``TAG`` on its motion empty, like the double arm's joints,
so a model update keeps it). The ratio is 360 / (pi x 2 x radius) degrees per mm with its sign
(``core.paths.wheel_ratio``): the cable's middle on a sheave, the cable's skin on a roller.

**The cable is drawn on the part itself.** The CAD cable part gets a Geometry Nodes modifier (``MOD``) that draws a
round tube through the points of the cable's own hidden mesh ("FR cable shapes <name>", in flex's hidden
collection). The points are in the cable part's own coordinates, so moving the whole model (a vessel at sea)
costs nothing. Materials, paint schemes, hiding and fades keep working; item off = modifier off = the CAD shape.
Two node trees: *still* has no Scene Time node and reads the first moment only – a frame change does not work the
tube out again; *moving* picks the frame's slice of ``frames x points``.

* A cable whose carriers all move alike is **still**: solved once, when something about it changes.
* One whose carriers can move against each other (a sheave on a luffing frame) is **moving**: while posing, a
  handler solves it again when a carrier moved against the cable part; ``bake`` (the end of every Build) reads the
  carriers' places at every frame (only when something that moves them is animated), solves all frames at once
  with the same number of points and writes them; playing and rendering then cost no Python. What was read is
  kept, so a setting changed after Build solves again without stepping through the frames.

**The look moves by a driver, not by geometry** (``blender/cable_looks.py`` has the materials). The tube carries a
point attribute ``fr_cable`` = (cos phi, sin phi, s): the angle round the cable and the metres along it. The part
has ``fr_cable_pay`` (metres paid out + 2.0, written by a simple-expression driver on the cable joint) and
``fr_cable_look`` (pitch, starts, width, kind). Look = Power cable / Steel wire rope puts the part into the manual
group "Power cables" / "Wire ropes"; Plain takes it out again.

Units: metres, radians. Module-level caches hold names and numbers only and are dropped at undo, redo and file
load. With no cable in the project nothing here costs time or makes data.
"""

from __future__ import annotations

import json
import math
import re
import threading

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import flex_fit
from ..core import paths as P
from ..core.words import plural
from . import build, cable_looks, flex, idprops, joints

TAG = "fr_cable"                        # on the motion empty of a joint this module made: the cable's name
PART = "fr_cable_part"                  # on a cable part, the shapes objects and meshes, the node trees
MOD = "FR cable"                        # the modifier's name on a cable part
SHAPES = "FR cable shapes"              # + the cable's name: its hidden mesh of points
TREES = {False: "FR cable still", True: "FR cable moving"}
VERSION = 1                             # of the node trees: an older tree is made again
SIDES = 20                              # of the tube's cross-section
S_ATTR = "fr_s"                         # on the shapes mesh's points: the exact length along the cable (m)
GROUPS = {"POWER": "Power cables", "ROPE": "Wire ropes"}
WAS = "fr_cable_group_was"              # on the part: the group it was in by hand before its look put it in one
SHAPING = ("SHEAVE", "CHUTE", "BEND")   # the kinds the cable bends round
TURNING = ("SHEAVE", "ROLLER")          # the kinds that turn with the cable
HAND = -1.0                             # the tube's phi turns right-handed about the way s grows (measured, see
#                                         tests/test_paths.py), and a look's positive angle lets phi fall along a
#                                         strand: a left-hand lay. So the angle goes to the look with this sign:
#                                         the usual right-hand lay (and stripes that climb like a right-hand thread)
SAG = 0.0003                            # an arc's points lie so close that the tube is at most this far inside it
ROPE_LAY = 6.5                          # a wire rope's lay length in diameters, when none was typed
POWER_PITCH = 2.5                       # a power cable's stripe distance in diameters, when none was typed
MOVE_TOL = 5e-6                         # a carrier moved against the cable part when a number differs this much
RATIO_TOL = 0.005                       # an own coupling this far off the app's ratio is reported
GAP_NOTE = 0.001                        # a cable drawn this far off a surface is reported
HUGE = 400_000                          # triangles: a part bigger than this is not looked at as a roller or sheave
ONE_GO = 1000.0                         # a cable up to this many radii long is read in one go (flex_fit), a longer
#                                         one in pieces (core.paths.centreline). A SWITCH UNTIL core.paths.centreline
#                                         IS FIXED: it bends the line after a seam on a cable of 200+ radii that turns
#                                         more than 90° (the test model's rope: 4.3 mm off). Then: 0.0
OFF_PATH = (0.002, 0.25)                # a reading whose path lies further than 2 mm, or a quarter of the cable's
#                                         radius if that is more, beside the CAD cable is refused
WRAP_JUMP = math.pi                     # a wrap that changes by more than this from one frame to the next: the cable
#                                         has lifted off that wheel (the path would loop round it)
UNDER = 0.7                             # a bend lies on a part when this share of it is on that part's surface
USER_CHANGE = 0.002                     # a diameter that differs this much from the CAD one was typed

_FRAMES, _PER, _FIRST = "fr_cable_frames", "fr_cable_per", "fr_cable_first"       # on a shapes object: its layout
_PLACES, _PLACES_OBS, _PLACES_FIRST = "fr_cable_places", "fr_cable_places_obs", "fr_cable_places_first"
_INPUTS = (("Shapes", "NodeSocketObject"), ("First", "NodeSocketInt"), ("Frames", "NodeSocketInt"),
           ("Per frame", "NodeSocketInt"), ("Offset", "NodeSocketInt"), ("Count", "NodeSocketInt"),
           ("Radius", "NodeSocketFloat"))

# runtime only: nothing here outlives undo, redo or a file load, and no Blender object is kept
_STATE = {"busy": 0, "last": {}, "arrays": {}, "inputs": {}, "solves": 0, "steps": 0}


class PathError(RuntimeError):
    """Something about a cable cannot be done; the text says why, in plain words."""


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------

def items(scene):
    return scene.fresing.cables


def active(scene):
    s = scene.fresing
    return s.cables[s.cables_index] if 0 <= s.cables_index < len(s.cables) else None


def find(scene, name: str):
    for it in scene.fresing.cables:
        if it.name == name:
            return it
    return None


def index_of(scene, item) -> int:
    for i, it in enumerate(scene.fresing.cables):
        if it == item:
            return i
    return -1


_part_name = flex._part_name
_quiet = flex._quiet
_alive = flex._alive


def label(item) -> str:
    if item.name:
        return item.name
    if item.part is not None:
        return _part_name(item.part)
    return "Cable"


def _unique(scene, base: str) -> str:
    names = {it.name for it in scene.fresing.cables}
    name, n = base, 2
    while name in names:
        name, n = f"{base} {n}", n + 1
    return name


def parts_of(scene, item) -> list:
    """The model part the item draws (the clash check leaves it out, as it does hoses)."""
    return [item.part] if _alive(scene, item.part) else []


def cable_parts(scene) -> list:
    out = []
    for it in scene.fresing.cables:
        out += parts_of(scene, it)
    return out


def is_cable_joint(scene, j) -> bool:
    """True when ``j`` is the slide joint of a cable (its value = metres paid out)."""
    return j is not None and any(c.joint == j.name for c in scene.fresing.cables)


def cable_of_joint(scene, j):
    """The cable whose speed joint ``j`` is, or None."""
    if j is None:
        return None
    for c in scene.fresing.cables:
        if c.joint == j.name:
            return c
    return None


def _owner(scene, contact):
    """(cable, index) of a contact."""
    for it in scene.fresing.cables:
        for k, c in enumerate(it.contacts):
            if c == contact:
                return it, k
    return None, -1


def _wheels(item) -> list:
    """The contacts the cable bends round, in order."""
    return [c for c in item.contacts if c.kind in SHAPING]


def broken(scene, item) -> str:
    """'' when the cable can be drawn, else what is missing (plain words, for a list row)."""
    if not _alive(scene, item.part):
        return "its part is gone" if item.part_uid else "no path yet: use 'From CAD cable'"
    for c in _wheels(item):
        if not _alive(scene, c.carrier):
            return f"what '{c.name}' sat on is gone: use 'From CAD cable' again"
    if not _alive(scene, item.a_part) or not _alive(scene, item.b_part):
        return "the part an end sat on is gone: use 'From CAD cable' again"
    return ""


def _baked(scene) -> bool:
    return bool(scene.fresing.anim_baked)


def _mm(metres: float) -> str:
    mm = metres * 1000.0
    return f"{mm:.1f}" if abs(mm) < 10.0 else f"{mm:.0f}"


# ---------------------------------------------------------------------------
# places
# ---------------------------------------------------------------------------

_np = flex._np
_at = flex._at


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    return v / n if n > 0.0 else np.array([0.0, 0.0, 1.0])


def _scale(m: np.ndarray) -> float:
    return float(np.cbrt(abs(np.linalg.det(m[:3, :3])))) or 1.0


def _world(ob) -> np.ndarray:
    return _np(flex._world(ob))


def _cad(ob, memo: dict) -> np.ndarray:
    """Where an object is in the CAD pose (4 x 4, world): a model object (``flex._cad_world``), or a joint's arrow
    or motion empty – in the CAD pose every joint is at 0, so a motion empty sits on its arrow and the arrow where
    it was put on what carries it."""
    if ob.get(build.PROP_KIND) in build.MODEL_KINDS:
        return flex._cad_world(ob, memo)
    m = memo.get(ob.name)
    if m is None:
        p = ob.parent
        up = _cad(p, memo) if p is not None else np.eye(4)
        m = up if ob.get(build.PROP_KIND) == "joint" else up @ _np(ob.matrix_parent_inverse) @ _np(ob.matrix_basis)
        memo[ob.name] = m
    return m


def _uid(ob) -> str:
    return ob.get(build.PROP_UID, "") if ob is not None and ob.get(build.PROP_KIND) in build.MODEL_KINDS else ""


def radius_of(item, c) -> float:
    """From a contact's axis to the cable's middle (m): as read, moved by half of what the user made the cable
    thicker or thinner (a bend in the air stays as drawn)."""
    r = float(c.radius)
    if c.kind != "BEND" and item.cad_diameter > 0.0:
        r += 0.5 * (float(item.diameter) - float(item.cad_diameter))
    return max(r, 1e-6)


def _ratio_radius(item, c) -> float:
    """Where the cable's speed is the wheel's rim speed: the cable's middle on a sheave, its skin (as CAD drew
    it) on a roller."""
    if c.kind == "SHEAVE":
        return radius_of(item, c)
    cad = float(item.cad_diameter) if item.cad_diameter > 0.0 else float(item.diameter)
    return max(float(c.radius) - 0.5 * cad, 1e-6)


def _inputs_of(item):
    """(wheels, carriers, slot of each wheel's carrier, slot of end A's part, of end B's): what a solve reads."""
    wheels = _wheels(item)
    obs, slots = [], {}

    def slot(ob):
        if ob.name not in slots:
            slots[ob.name] = len(obs)
            obs.append(ob)
        return slots[ob.name]

    return wheels, obs, [slot(c.carrier) for c in wheels], slot(item.a_part), slot(item.b_part)


def _rel_now(item, obs) -> np.ndarray:
    """(K, 4, 4): where the carriers are now, as the cable part sees them."""
    inv = np.linalg.inv(_world(item.part))
    return np.stack([inv @ _world(ob) for ob in obs]) if obs else np.zeros((0, 4, 4))


def _can_move(item) -> bool:
    """Can the things that shape the cable move against each other or against the cable part? (Not: do they.)"""
    _wheels_, obs, _w, _a, _b = _inputs_of(item)
    return len({flex._movers(ob) for ob in [item.part] + obs}) > 1


def _fcurves(ob) -> list:
    ad = ob.animation_data
    if ad is None or ad.action is None or ad.action_slot is None:
        return []
    from bpy_extras import anim_utils
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    return list(cb.fcurves) if cb is not None else []


_MOVING_PATHS = ("location", "rotation", "scale", "delta_", f'["{joints.VALUE}"]')


def _keys_vary(ob) -> bool:
    for fc in _fcurves(ob):
        if not fc.data_path.startswith(_MOVING_PATHS):
            continue
        n = len(fc.keyframe_points)
        if n < 2:
            continue
        co = np.empty(2 * n, np.float32)
        fc.keyframe_points.foreach_get("co", co)
        if float(np.ptp(co[1::2])) > 1e-9:
            return True
    return False


def _varies(ob, depth: int = 0) -> bool:
    """Is this object moved along the time line: keys on its place or its joint value, a driver that reads
    something with keys, or a constraint?"""
    if len(ob.constraints) or _keys_vary(ob):
        return True
    ad = ob.animation_data
    if ad is None or depth > 3:
        return False
    for fc in ad.drivers:
        if not fc.data_path.startswith(_MOVING_PATHS):
            continue                            # (a driver on a look's number does not move it)
        for var in fc.driver.variables:
            for t in var.targets:
                tid = t.id
                if isinstance(tid, bpy.types.Object) and tid != ob and _varies(tid, depth + 1):
                    return True
    return False


def _animated(item) -> bool:
    """Does anything that can move the cable's carriers against each other move along the time line?"""
    _wheels_, obs, _w, _a, _b = _inputs_of(item)
    chains = []
    for ob in [item.part] + obs:
        chain, p = {}, ob
        while p is not None:
            chain[p.name] = p
            p = p.parent
        chains.append(chain)
    common = set(chains[0])
    for ch in chains[1:]:
        common &= set(ch)
    seen = {}
    for ch in chains:
        for name, ob in ch.items():
            if name not in common:
                seen[name] = ob
    return any(_varies(ob) for ob in seen.values())


# ---------------------------------------------------------------------------
# the cable's joint, and the joints of what it turns
# ---------------------------------------------------------------------------

def _joint_names(scene) -> dict:
    """Motion empty name -> joint name (names: a joint item is not kept across changes of the list)."""
    return {j.motion.name: j.name for j in scene.fresing.joints if j.motion is not None}


def _new_cable_joint(scene, name: str, joint_name: str = ""):
    """The slide joint of a cable: it moves nothing, sits on the first model and counts the metres paid out."""
    roots = build.model_roots(scene)
    if not roots:
        raise PathError("There is no model yet: import one first (1 Import).")
    base = roots[0]
    jname = joint_name or (name if name.lower().startswith("cable") else f"Cable {name}")
    with joints._batch(scene):
        w = joints.world_of(scene, base)
        try:
            j = joints.create(scene, "SLIDE", [], w.translation.copy(),
                              (w.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized(), name=jname, base=base,
                              allow_empty=True)
        except RuntimeError as exc:
            raise PathError(str(exc)) from exc
        j.motion[TAG] = name
        jname = j.name
    j = joints.find(scene, jname)
    if j.use_limits:
        j.use_limits = False
    joints.apply_limits(j, joints._model_size(scene))
    return j


def add_cable(scene, name: str = "", joint: str = ""):
    """A new cable. ``joint``: the slide joint whose value is its metres paid out ('' = the app makes one,
    "Cable <name>"). Raises PathError when that joint is missing or no slide joint, or there is no model."""
    s = scene.fresing
    if joint:
        j = joints.find(scene, joint)
        if j is None:
            raise PathError(f"There is no joint called '{joint}'.")
        if j.kind != "SLIDE":
            raise PathError(f"'{joint}' is a rotate joint: a cable's speed needs a slide joint (its value is the "
                            "metres of cable paid out).")
        other = cable_of_joint(scene, j)
        if other is not None:
            raise PathError(f"'{joint}' is the speed of cable '{label(other)}' already.")
    name = _unique(scene, name or "Cable")
    made = ""
    if not joint:
        made = _new_cable_joint(scene, name).name
    item = s.cables.add()
    with _quiet(item):
        item.name = name
        item.joint = joint or made
        item.made_joint = bool(made)
    s.cables_index = len(s.cables) - 1
    return s.cables[len(s.cables) - 1]


def _own_joint(scene, part, centre, axis, radius: float, memo: dict, names: dict) -> str:
    """The name of the rotate joint that already turns ``part`` about this axis ('' = none): the nearest joint
    above the part, when its arrow lies on the axis."""
    ob = part
    while ob is not None:
        p = ob.parent
        if p is None:
            return ""
        kind = p.get(build.PROP_KIND)
        if kind == "joint":
            j = joints.find(scene, names.get(p.name, ""))
            if j is None or j.kind != "ROTATE" or j.frame is None:
                return ""
            f = _cad(j.frame, memo)
            d = _unit(f[:3, 2])
            if abs(float(d @ axis)) < math.cos(math.radians(1.0)):
                return ""
            off = float(np.linalg.norm(np.cross(np.asarray(centre) - f[:3, 3], d)))
            return j.name if off <= max(0.001, 0.02 * radius) else ""
        if kind in build.JOINT_KINDS:
            return ""                           # a cylinder or a mechanism moves it
        ob = p
    return ""


def _make_joints(scene, item, rows: list, memo: dict) -> None:
    """Every sheave and roller of ``rows`` (dicts, places in the CAD pose) gets the joint that turns it: its own
    when it has one on that axis, else a new one (made together, in one CAD pose). Fills ``joint``, ``made``,
    ``carrier`` and ``note``."""
    names = _joint_names(scene)
    todo, by_part = [], {}
    for d in rows:
        if d["kind"] not in TURNING or d.get("part") is None or d.get("joint"):
            continue
        own = _own_joint(scene, d["part"], d["centre"], d["axis"], d["radius"], memo, names)
        if own:
            d["joint"], d["made"] = own, False
        else:
            todo.append(d)
    if todo:
        with joints._batch(scene):
            for d in todo:
                key = d["part"].name
                if key in by_part:              # the cable passes the same part twice: one joint
                    d["joint"], d["made"] = by_part[key], False
                    continue
                try:
                    j = joints.create(scene, "ROTATE", [d["part"]], Vector(d["centre"]), Vector(d["axis"]))
                except RuntimeError as exc:
                    d["note"] = f"it cannot turn: {exc}"
                    continue
                j.motion[TAG] = item.name
                d["joint"], d["made"], d["coupled"] = j.name, True, True
                by_part[key] = j.name
        memo.clear()                            # (parts under a new joint have a new parent)
    for d in rows:
        j = joints.find(scene, d.get("joint", "")) if d.get("joint") else None
        if j is not None and j.frame is not None:
            d["carrier"] = j.frame


def _joint_axis(c, j, memo: dict) -> tuple:
    """(the contact's axis, the joint's axis), both in the CAD pose (world)."""
    a = _unit(_cad(c.carrier, memo)[:3, :3] @ np.array(c.axis, dtype=float))
    return a, _unit(_cad(j.frame, memo)[:3, 2])


def ratio_of(scene, item, c) -> float:
    """Degrees the contact's joint should turn per mm of cable, with its sign (0.0: it has no joint)."""
    j = joints.find(scene, c.joint) if c.joint else None
    if j is None or j.frame is None or not _alive(scene, c.carrier):
        return 0.0
    a, ja = _joint_axis(c, j, {})
    return P.wheel_ratio(_ratio_radius(item, c), int(c.side), a, ja, bool(item.reverse))


def _own_ratio(scene, item, j):
    """Degrees per mm of the cable's joint that ``j`` turns by its own coupling; None when it does not follow the
    cable's joint (also not through other joints)."""
    top, k, _c = joints.chain_affine(scene, j)
    if top is None or top.name != item.joint or not j.follows:
        return None
    return math.degrees(k) / 1000.0


def _couple(scene, item) -> None:
    """The couplings the app made, as the settings are now: a contact that turns follows the cable's joint at its
    ratio; one switched off (or a cable switched off) moves by itself. Couplings the user made stay."""
    lead = joints.find(scene, item.joint) if item.joint else None
    todo = []
    for c in item.contacts:
        if c.kind not in TURNING or not c.joint:
            continue
        j = joints.find(scene, c.joint)
        if j is None:
            continue
        ratio = ratio_of(scene, item, c)
        if abs(c.ratio - ratio) > 1e-9:
            with _quiet(c):
                c.ratio = ratio
        if not (c.coupled or c.made_joint):
            continue
        want = bool(item.enabled and c.turns and lead is not None and ratio != 0.0)
        if want:
            if j.follows != item.joint or joints.offset(j) != 0.0:
                todo.append((c.joint, item.joint, ratio))
            elif abs(j.couple_ratio - ratio) > 1e-5 * abs(ratio):
                # only its ratio (a thicker cable, the other way round): the driver's number, nothing else – a
                # built animation stays (the follower has no keys of its own)
                joints._set_raw(j, couple_ratio=float(ratio))
                joints.write_coupling(scene, j)
                joints.apply_limits(j, joints._model_size(scene))
        elif j.follows == item.joint:
            todo.append((c.joint, "", None))

    def run():
        for name, follows, ratio in todo:
            j = joints.find(scene, name)
            try:
                if follows:
                    joints.set_follows(scene, j, follows, ratio=ratio, offset_value=0.0)
                else:
                    joints.set_follows(scene, j, "")
            except RuntimeError as exc:
                print("Fresing Render: cable coupling:", exc)

    if not todo:
        return
    _STATE["busy"] += 1
    try:
        if joints.in_batch(scene) or len(todo) <= 2:
            run()
        else:
            with joints._batch(scene):
                run()
    finally:
        _STATE["busy"] -= 1


def _remove_joints(scene, names: list) -> None:
    """Take these joints out together, in one CAD pose (``joints.remove`` one by one takes a CAD pose each)."""
    names = [n for n in names if joints.find(scene, n) is not None]
    if not names:
        return
    if len(names) == 1:
        joints.remove(scene, joints.find(scene, names[0]))
        return
    s = scene.fresing
    with joints._batch(scene):
        for name in names:
            for f in [x.name for x in joints.followers(scene, joints.find(scene, name))]:
                joints._free(scene, joints.find(scene, f))
            j = joints.find(scene, name)
            joints._take_out(scene, j)
            for ob in (j.motion, j.frame):
                if ob is not None:
                    bpy.data.objects.remove(ob, do_unlink=True)
            s.joints.remove(next(i for i, x in enumerate(s.joints) if x.name == name))
        for r in s.joints:
            if r.frame is not None:
                joints.sync_base(r)
    s.joints_index = max(0, min(s.joints_index, len(s.joints) - 1))
    joints.refresh_couplings(scene)


# ---------------------------------------------------------------------------
# reading a CAD cable
# ---------------------------------------------------------------------------

def _check_part(scene, item, part) -> None:
    name = _part_name(part) or "Nothing"
    if part is None or part.type != "MESH" or part.data is None or not len(part.data.vertices):
        raise PathError(f"'{name}' is not a cable: it has no shape to read.")
    if part.get(build.PROP_KIND) != "part":
        raise PathError(f"'{name}' is not a part of the model.")
    for it in scene.fresing.cables:
        if it != item and it.part == part:
            raise PathError(f"'{name}' is cable '{label(it)}' already.")
    if any(ob == part for ob in flex.flex_parts(scene)):
        raise PathError(f"'{name}' follows the motion as a hose already (4 Motion > Hoses and drag chains): "
                        "remove it there first.")


def _rounds(scene, part, pts: np.ndarray, radius: float, memo: dict, skip: set) -> tuple:
    """The round parts near the cable's centreline, as ``core.paths.Round`` (world, CAD pose): every round face
    axis of every part the cable comes close to. Returns (rounds, {object name: object})."""
    reach = max(P.TOUCH_TOL[0], P.TOUCH_TOL[1] * radius)
    margin = radius + reach + 0.002
    parts = [ob for ob in build.iter_parts(scene)
             if ob.name not in skip and not ob.get(build.PROP_EXCLUDED) and ob.data is not None
             and "fr_axes" in ob.data and len(ob.data.vertices)]
    if not parts:
        return [], {}
    world = np.stack([flex._cad_world(ob, memo) for ob in parts])
    box = np.array([[tuple(c) for c in ob.bound_box] for ob in parts], dtype=float).reshape(-1, 8, 3)
    corners = np.einsum("kij,kcj->kci", world[:, :3, :3], box) + world[:, None, :3, 3]
    lo, hi = corners.min(axis=1) - margin, corners.max(axis=1) + margin
    maybe = np.nonzero(((lo <= pts.max(axis=0)) & (hi >= pts.min(axis=0))).all(axis=1))[0]
    meshes, rounds, obs = {}, [], {}
    for k in maybe:
        inside = ((pts >= lo[k]) & (pts <= hi[k])).all(axis=1)
        if not inside.any():
            continue
        ob = parts[k]
        if len(ob.data.loop_triangles) > HUGE or len(ob.data.polygons) > HUGE:
            continue                            # a hull, a deck: no roller
        if ob.data.name not in meshes:
            meshes[ob.data.name] = flex._mesh_arrays(ob.data)
        verts, tris = meshes[ob.data.name]
        vw = _at(world[k], verts)
        near = pts[inside]
        axes = np.array(ob.data["fr_axes"], dtype=float).reshape(-1, 7)
        for i, a in enumerate(axes):
            d = world[k][:3, :3] @ a[3:6]
            n = float(np.linalg.norm(d))
            if n < 1e-9:
                continue
            d = d / n
            o = _at(world[k], a[:3])
            rel = near - o
            rho = np.linalg.norm(rel - np.outer(rel @ d, d), axis=1)
            vrel = vw - o
            far = float(np.linalg.norm(vrel - np.outer(vrel @ d, d), axis=1).max())
            if float(rho.min()) > far + margin:
                continue                        # the cable never comes near anything round about this axis
            rounds.append(P.Round((ob.name, i), o, d, vw, tris))
            obs[ob.name] = ob
    return rounds, obs


def _under(near, pts: np.ndarray, reach: float, but: set):
    """The part a bend lies on: the one whose surface is within ``reach`` of at least ``UNDER`` of the bend's
    points (the most of them, then the smallest part). None when no single part carries it."""
    if not len(near.parts) or not len(pts):
        return None
    lo, hi = pts.min(axis=0) - reach, pts.max(axis=0) + reach
    found = []
    for k in np.nonzero(((near.lo <= hi) & (near.hi >= lo)).all(axis=1))[0]:
        ob = near.parts[k]
        if ob.name in but:
            continue
        if ob.data.name not in near.meshes:
            near.meshes[ob.data.name] = flex._mesh_arrays(ob.data)
        verts, tris = near.meshes[ob.data.name]
        if len(tris) > HUGE:
            continue
        on = _points_on(_at(near.world[k], verts), tris, pts, reach)
        if on >= UNDER * len(pts):
            found.append((-on, float(near.size[k]), ob.name, ob))
    return min(found)[3] if found else None


def _points_on(verts: np.ndarray, tris: np.ndarray, pts: np.ndarray, reach: float) -> int:
    """How many of the points lie within ``reach`` of the mesh's surface."""
    lo, hi = pts.min(axis=0) - reach, pts.max(axis=0) + reach
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    tlo, thi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
    keep = ((tlo <= hi) & (thi >= lo)).all(axis=1)
    if not keep.any():
        return 0
    a, b, c, tlo, thi = a[keep], b[keep], c[keep], tlo[keep], thi[keep]
    on = 0
    for p in pts:
        near_p = ((tlo <= p + reach) & (thi >= p - reach)).all(axis=1)
        if near_p.any() and flex._distance(p[None], a[near_p], b[near_p], c[near_p]) <= reach:
            on += 1
    return on


def _flip_rows(geo: dict) -> None:
    """The same path read from its other end."""
    length = geo["length"]
    geo["rows"].reverse()
    for d in geo["rows"]:
        d["side"] = -d["side"]
        d["s"] = length - d["s"]
    geo["start"], geo["end"] = geo["end"], geo["start"]
    geo["on0"], geo["on1"] = geo["on1"], geo["on0"]
    geo["line"] = geo["line"][::-1]
    geo["flipped"] = not geo.get("flipped", False)


def _centrelines(verts: np.ndarray, tris: np.ndarray):
    """The cable's centreline, a point every radius: read in one go where that is exact (up to ``ONE_GO`` radii:
    ``flex_fit`` cuts a tube 1024 times at most), in pieces for a longer cable; then the other way, for a cable
    the first way's line cannot be read from."""
    rough = flex_fit.tube_centreline(verts, tris, 65)
    if not rough.ok:
        yield rough
        return
    n = int(round(rough.length / rough.radius)) + 1
    short = rough.length <= ONE_GO * rough.radius
    for one_go in ((True, False) if short else (False,)):
        tube = flex_fit.tube_centreline(verts, tris, max(n, 2)) if one_go else P.centreline(verts, tris)
        if tube.ok:
            yield tube


def _end_face(verts: np.ndarray, tris: np.ndarray, point, along, radius: float):
    """The middle of the flat end face of a cable near ``point`` (the centreline's end, which is a little off
    where the cable ends in a bend): the centre of the triangles there that look along the cable. None when
    there is no such face."""
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    near = (np.linalg.norm(a - point, axis=1) < 1.6 * radius) & (np.linalg.norm(b - point, axis=1) < 1.6 * radius) \
        & (np.linalg.norm(c - point, axis=1) < 1.6 * radius)
    if not near.any():
        return None
    a, b, c = a[near], b[near], c[near]
    n = np.cross(b - a, c - a)
    area = np.linalg.norm(n, axis=1)
    flat = (area > 0.0) & (np.abs(n @ np.asarray(along)) > 0.985 * area)
    if not flat.any() or float(area[flat].sum()) < 0.5 * math.pi * radius * radius:
        return None
    centre = ((a[flat] + b[flat] + c[flat]) / 3.0 * area[flat, None]).sum(axis=0) / area[flat].sum()
    return centre if float(np.linalg.norm(centre - point)) < 0.5 * radius else None


def _read(scene, item, part) -> dict:
    """What the CAD cable says: its contacts (rows, places in the CAD pose, world), its two ends, its diameter.
    Raises PathError with a plain reason."""
    _check_part(scene, item, part)
    name = _part_name(part)
    memo: dict = {}
    w = flex._cad_world(part, memo)
    verts, tris = flex._mesh_arrays(part.data)
    vw = _at(w, verts)
    skip = {ob.name for ob in flex.flex_parts(scene)} | {ob.name for ob in cable_parts(scene)} | {part.name}
    rd, tube, obs, why, good = None, None, {}, "", False
    for tube in _centrelines(vw, tris):
        if not tube.ok:
            raise PathError(f"This part is not a cable: {tube.problem}")
        rounds, obs = _rounds(scene, part, tube.points, float(tube.radius), memo, skip)
        for wider in (1.0, 2.0):                # (facets of a coarse mesh: once more, less strict)
            tol = None if wider == 1.0 else wider * max(P.FIT_TOL[0], P.FIT_TOL[1] * float(tube.radius))
            rd = P.read_cable(tube.points, float(tube.radius), rounds, fit_tol=tol)
            if not rd.ok:
                why = why or _named(rd.problem, [_row_name(c, obs) for c in rd.contacts])
                continue
            # a reading may say "ok" with its path well beside the cable: look for ourselves
            limit = max(OFF_PATH[0], OFF_PATH[1] * float(tube.radius))
            if float(rd.deviation) <= limit:
                good = True
                break
            off = _off_path(tube.points, rd.path.points)
            k = int(np.argmax(off))
            run = float(np.linalg.norm(np.diff(tube.points[:k + 1], axis=0), axis=1).sum())
            why = why or (f"{run:.1f} m from its start the cable as drawn lies {_mm(float(off[k]))} mm beside the "
                          "straight runs and round bends the app can lay over its rollers and sheaves (is it drawn "
                          "as a spline there, or does it sag?)")
        if good:
            break
    if tube is None:
        raise PathError("This part is not a cable: it has no shape to read.")
    if not good:
        raise PathError(f"The path of '{name}' cannot be read: {why}")
    pts, radius = tube.points, float(tube.radius)
    for k, along in ((0, tube.t0), (-1, tube.t1)):         # the ends: the middle of the cable's end faces
        face = _end_face(vw, tris, pts[k], along, radius)
        if face is not None:
            if k == 0:
                rd.start = face
            else:
                rd.end = face
    if not rd.contacts:
        raise PathError(f"The cable touches nothing: no roller, sheave or chute lies on the path of '{name}' "
                        "(within a few mm of it). Is it the right part?")
    near = flex._Near(scene, memo)
    reach = radius + max(P.TOUCH_TOL[0], P.TOUCH_TOL[1] * radius)
    path = rd.path
    turning = {c.key[0] for c in rd.contacts if c.kind != "BEND" and c.full}
    rows, wheel, bends = [], 0, 0
    for c in rd.contacts:
        d = {"centre": np.array(c.centre, dtype=float), "axis": _unit(c.axis), "radius": float(c.radius),
             "surface": float(c.surface), "side": 1 if c.side >= 0 else -1, "s": float(c.s), "wrap": float(c.wrap),
             "gap": float(c.gap), "full": bool(c.full), "part": None, "note": ""}
        if c.kind == "BEND":
            lo = int(path.first[wheel])
            arc = path.points[lo:lo + int(path.counts[wheel])]
            take = arc[np.unique(np.linspace(0, len(arc) - 1, min(len(arc), 9)).round().astype(int))]
            on = _under(near, take[1:-1] if len(take) > 4 else take, reach, skip | turning)
            if on is not None:
                d.update(kind="CHUTE", part=on, name=_part_name(on))
            else:
                bends += 1
                d.update(kind="BEND", name=f"Bend {bends}")
        else:
            ob = obs[c.key[0]]
            kind = "ROLLER" if c.kind == "TOUCH" else ("SHEAVE" if c.full else "CHUTE")
            d.update(kind=kind, part=ob, name=_part_name(ob))
        if c.kind != "TOUCH":
            wheel += 1
        rows.append(d)
    geo = {"rows": rows, "start": np.array(rd.start, dtype=float), "end": np.array(rd.end, dtype=float),
           "on0": bool(rd.start_on_wheel), "on1": bool(rd.end_on_wheel), "diameter": 2.0 * radius,
           "length": float(path.length), "deviation": float(rd.deviation), "memo": memo, "line": pts,
           "near": near, "skip": skip, "notes": []}
    return geo


def _off_path(points: np.ndarray, line: np.ndarray) -> np.ndarray:
    """How far every point (P, 3) is from the polyline (L, 3)."""
    if len(line) < 2:
        return np.full(len(points), math.inf)
    a, seg = line[:-1], line[1:] - line[:-1]
    ss = np.maximum(np.einsum("li,li->l", seg, seg), 1e-30)
    out = np.empty(len(points))
    for lo in range(0, len(points), 512):
        p = points[lo:lo + 512, None]
        t = np.clip(np.einsum("pli,li->pl", p - a[None], seg) / ss, 0.0, 1.0)
        out[lo:lo + 512] = np.linalg.norm(p - (a[None] + t[..., None] * seg[None]), axis=2).min(axis=1)
    return out


def _row_name(c, obs: dict) -> str:
    return _part_name(obs[c.key[0]]) if c.key is not None and c.key[0] in obs else "a bend"


def _named(text: str, names: list) -> str:
    """The solver's reason with its "contact 3" replaced by that contact's name."""
    def name(m):
        k = int(m.group(1)) - 1
        return f"'{names[k]}'" if 0 <= k < len(names) else m.group(0)
    out = re.sub(r"[Cc]ontact (\d+)", name, text)
    return out[:1].upper() + out[1:] if out else out


def _direction(scene, item, geo: dict) -> None:
    """Which end is the start. Rollers that already follow the cable's joint know: when most of them turn the
    other way than the path as read would turn them, the path is read from its other end."""
    names = _joint_names(scene)
    votes = 0
    for d in geo["rows"]:
        if d["kind"] not in TURNING or d["part"] is None:
            continue
        own = _own_joint(scene, d["part"], d["centre"], d["axis"], d["radius"], geo["memo"], names)
        j = joints.find(scene, own) if own else None
        mine = _own_ratio(scene, item, j) if j is not None else None
        if not mine:
            continue
        app = P.wheel_ratio(1.0, d["side"], d["axis"], _unit(_cad(j.frame, geo["memo"])[:3, 2]), bool(item.reverse))
        votes += 1 if app * mine > 0.0 else -1
    if votes < 0:
        _flip_rows(geo)


def _ends(scene, item, part, geo: dict, keep_user: bool) -> None:
    """The two ends: on its first / last wheel (a drum), on the part it touches, or a free end that stays with
    the nearest bend's carrier."""
    radius = 0.5 * geo["diameter"]
    near, memo = geo["near"], geo["memo"]
    wheels = [d for d in geo["rows"] if d["kind"] in SHAPING]
    but = geo["skip"] | {d["part"].name for d in geo["rows"] if d["part"] is not None and d["kind"] in TURNING}
    for key, point, on, k in (("a", geo["start"], geo["on0"], 0), ("b", geo["end"], geo["on1"], -1)):
        if keep_user and item.get(key + "_user") and _alive(scene, getattr(item, key + "_part")):
            ob, kind, free = getattr(item, key + "_part"), "FIXED", False
        elif on and wheels:
            ob, kind, free = wheels[k]["carrier"], "WHEEL", False
        else:
            ob, _dist = near.touching(point[None], radius + 0.002, but=but)
            kind, free = "FIXED", ob is None
            if ob is None:
                ob = wheels[k]["carrier"] if wheels else flex._stay_part(part)
        with _quiet(item):
            setattr(item, key + "_kind", kind)
            setattr(item, key + "_part", ob)
            setattr(item, key + "_uid", _uid(ob))
            setattr(item, key + "_point", tuple(_at(np.linalg.inv(_cad(ob, memo)), point)))
            setattr(item, key + "_free_end", free)
        if free and wheels:                     # how far it runs straight on, as drawn: the tangent's length
            rel = point - wheels[k]["centre"]
            flat = rel - wheels[k]["axis"] * float(rel @ wheels[k]["axis"])
            item[key + "_cad_free"] = math.sqrt(max(float(flat @ flat) - wheels[k]["radius"] ** 2, 0.0))
            item[key + "_cad_point"] = [float(v) for v in getattr(item, key + "_point")]
        else:
            for extra in ("_cad_free", "_cad_point"):
                if key + extra in item:
                    del item[key + extra]


_CONTACT_FIELDS = ("name", "kind", "part", "part_uid", "carrier", "carrier_uid", "centre", "axis", "radius", "surface",
                   "side", "wrap", "gap", "s", "full", "turns", "joint", "made_joint", "coupled", "ratio", "user",
                   "note")
_END_FIELDS = tuple(k + f for k in ("a", "b") for f in ("_kind", "_part", "_uid", "_point", "_free_end"))
_ITEM_FIELDS = ("part", "part_uid", "diameter", "cad_diameter", "pitch", "length", "moving", "problem",
                "problem_frame", "contacts_index") + _END_FIELDS
_CUSTOM = ("a_user", "b_user", "a_cad_free", "b_cad_free", "a_cad_point", "b_cad_point", "look_was")


def _values(group, fields) -> dict:
    out = {}
    for f in fields:
        v = getattr(group, f)
        out[f] = tuple(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
    return out


def _snapshot(item) -> dict:
    """The cable's contacts and ends as plain data (to put them back when a change gives no path)."""
    return {"contacts": [_values(c, _CONTACT_FIELDS) for c in item.contacts], "item": _values(item, _ITEM_FIELDS),
            "custom": {k: (list(item[k]) if hasattr(item[k], "__len__") and not isinstance(item[k], str) else item[k])
                       for k in _CUSTOM if k in item}}


def _restore(item, snap: dict) -> None:
    with _quiet(item):
        item.contacts.clear()
        for row in snap["contacts"]:
            c = item.contacts.add()
            with _quiet(c):
                for k, v in row.items():
                    setattr(c, k, v)
        for k, v in snap["item"].items():
            setattr(item, k, v)
        for k in _CUSTOM:
            if k in snap["custom"]:
                item[k] = snap["custom"][k]
            elif k in item:
                del item[k]


def _write_contact(c, d: dict, memo: dict) -> None:
    carrier = d["carrier"]
    inv = np.linalg.inv(_cad(carrier, memo))
    with _quiet(c):
        c.name, c.kind = d["name"], d["kind"]
        c.part = d.get("part")
        c.part_uid = _uid(d.get("part"))
        c.carrier = carrier
        c.carrier_uid = _uid(carrier)
        c.centre = tuple(_at(inv, d["centre"]))
        c.axis = tuple(_unit(inv[:3, :3] @ d["axis"]))
        c.radius, c.surface, c.side = d["radius"], d["surface"], int(d["side"])
        c.wrap, c.gap, c.s, c.full = d["wrap"], d["gap"], d["s"], bool(d["full"])
        c.turns = bool(d.get("turns", True))
        c.joint = d.get("joint", "") or ""
        c.made_joint = bool(d.get("made", False))
        c.coupled = bool(d.get("coupled", False))
        c.user = bool(d.get("user", False))
        c.note = d.get("note", "") or ""


def _row_of(c, memo: dict) -> dict:
    """A stored contact as a row (places in the CAD pose, world)."""
    m = _cad(c.carrier, memo)
    return {"kind": c.kind, "name": c.name, "part": c.part, "carrier": c.carrier,
            "centre": _at(m, np.array(c.centre, dtype=float)), "axis": _unit(m[:3, :3] @ np.array(c.axis, dtype=float)),
            "radius": float(c.radius), "surface": float(c.surface), "side": int(c.side), "s": float(c.s),
            "wrap": float(c.wrap), "gap": float(c.gap), "full": bool(c.full), "turns": bool(c.turns),
            "joint": c.joint, "made": bool(c.made_joint), "coupled": bool(c.coupled), "user": bool(c.user),
            "note": c.note}


def _merge(scene, item, geo: dict) -> list:
    """What the list had that a new reading of the same part must keep: a contact the user added or changed takes
    the place of the reading's contact on the same part (or goes in by its place along the cable); a contact
    switched off stays off; the joint a contact has is found again. Returns the joints the app made that no
    contact needs any more."""
    memo = geo["memo"]
    rows = geo["rows"]
    used = set()

    def match(c, row):
        for k, d in enumerate(rows):
            if k in used:
                continue
            if c.part is not None and d["part"] == c.part:
                return k
            if c.part is None and d["part"] is None and np.linalg.norm(row["centre"] - d["centre"]) < 0.5 * d["radius"]:
                return k
        return -1

    left = []
    for c in item.contacts:
        if not _alive(scene, c.carrier) or (c.part_uid and not _alive(scene, c.part)):
            if c.made_joint and c.joint:
                left.append(c.joint)
            continue
        row = _row_of(c, memo)
        k = match(c, row)
        if c.user:
            if k >= 0:
                rows[k] = row
            else:
                k = next((i for i, d in enumerate(rows) if d["s"] > row["s"]), len(rows))
                rows.insert(k, row)
                used = {u + 1 if u >= k else u for u in used}
            used.add(k)
        elif k >= 0:
            used.add(k)
            d = rows[k]
            d["turns"] = bool(c.turns)
            if c.joint and joints.find(scene, c.joint) is not None and d["kind"] in TURNING:
                d["joint"], d["made"], d["coupled"] = c.joint, bool(c.made_joint), bool(c.coupled)
        elif c.made_joint and c.joint:
            left.append(c.joint)
        elif c.coupled and c.joint:
            j = joints.find(scene, c.joint)
            if j is not None and j.follows == item.joint:
                joints.set_follows(scene, j, "")
    return left


def read_cad(scene, item, part) -> list[str]:
    """"From CAD cable": read the cable ``part`` – its centreline, its diameter, what it touches, its ends –, give
    everything it touches its joint, and draw the cable on its path. Contacts the user added or changed stay.
    Returns notes for the report. Raises PathError (nothing is changed then)."""
    if index_of(scene, item) < 0:
        raise PathError("This cable is not in the list.")
    name = item.name
    _STATE["busy"] += 1
    try:
        geo = _read(scene, item, part)
        item = find(scene, name)
        _direction(scene, item, geo)
        snap = _snapshot(item)
        old_part = item.part if _alive(scene, item.part) else None
        same = old_part == part
        left = _merge(scene, item, geo) if same else [c.joint for c in item.contacts if c.made_joint and c.joint]
        before = {j.name for j in scene.fresing.joints}
        try:
            memo = geo["memo"]
            _make_joints(scene, item, geo["rows"], memo)
            item = find(scene, name)
            for d in geo["rows"]:
                if "carrier" not in d:
                    d["carrier"] = d["part"] if d["part"] is not None else flex._stay_part(part)
            with _quiet(item):
                item.part = part
                item.part_uid = _uid(part)
                typed = item.cad_diameter > 0.0 and \
                    abs(item.diameter - item.cad_diameter) > USER_CHANGE * item.cad_diameter
                fresh = item.cad_diameter <= 0.0
                item.cad_diameter = geo["diameter"]
                if not typed:
                    item.diameter = geo["diameter"]
                if fresh and abs(item.pitch - 0.5) < 1e-9:
                    item.pitch = _default_pitch(item)
                item.contacts.clear()
                for d in geo["rows"]:
                    _write_contact(item.contacts.add(), d, memo)
                item.contacts_index = 0
            item["look_was"] = item.look
            _ends(scene, item, part, geo, keep_user=same)
            _notes_of_joints(scene, item, memo)
            res = _solve_item(scene, item, _cad_rel(item, memo))
            if not res["ok"].all():
                raise PathError(f"The path of '{_part_name(part)}' cannot be drawn: {res['problems'][0]}")
        except Exception:
            item = find(scene, name)
            _remove_joints(scene, [j.name for j in scene.fresing.joints if j.name not in before])
            _restore(find(scene, name), snap)
            raise
        if old_part is not None and not same:
            _strip(scene, item, old_part)
        _remove_joints(scene, [n for n in dict.fromkeys(left) if n not in {c.joint for c in item.contacts}])
        _couple(scene, find(scene, name))
        item = find(scene, name)
        part[PART] = True
        _apply_look(scene, item)
        _pay_driver(scene, item)
        with _quiet(item):
            item.moving = _can_move(item)
        notes = _summary(scene, item, geo)
    finally:
        _STATE["busy"] -= 1
    forget()
    notes += _rebuild(scene, find(scene, name))
    return notes


def _default_pitch(item) -> float:
    d = float(item.diameter)
    return ROPE_LAY * d if item.look == "ROPE" else max(0.1, round(POWER_PITCH * d, 2))


def _cad_rel(item, memo: dict) -> np.ndarray:
    """(1, K, 4, 4): the carriers as the cable part sees them in the CAD pose."""
    _wheels_, obs, _w, _a, _b = _inputs_of(item)
    inv = np.linalg.inv(_cad(item.part, memo))
    return np.stack([inv @ _cad(ob, memo) for ob in obs])[None] if obs else np.zeros((1, 0, 4, 4))


def _notes_of_joints(scene, item, memo: dict) -> None:
    """Each turning contact's note: what its own joint does, when the app left it alone. A joint of its own that
    follows nothing yet is the app's to couple."""
    for c in item.contacts:
        if c.kind not in TURNING:
            continue
        note = c.note
        j = joints.find(scene, c.joint) if c.joint else None
        if j is None:
            if not note:
                note = "it has no joint: it does not turn"
        elif not c.made_joint:
            a, ja = _joint_axis(c, j, memo)
            ratio = P.wheel_ratio(_ratio_radius(item, c), int(c.side), a, ja, bool(item.reverse))
            mine = _own_ratio(scene, item, j)
            if not j.follows:
                with _quiet(c):
                    c.coupled = True            # its own joint, free: the app makes it follow the cable
                note = ""
            elif mine is None:
                top = joints.driver_of(scene, j)
                note = (f"its joint '{j.name}' follows '{top.name if top is not None else j.follows}', not this "
                        "cable: left as it is")
            elif abs(mine - ratio) > RATIO_TOL * abs(ratio):
                if mine * ratio < 0.0 and abs(abs(mine) - abs(ratio)) <= RATIO_TOL * abs(ratio):
                    note = f"its joint '{j.name}' turns the other way than the cable runs over it: left as it is"
                else:
                    note = (f"its joint '{j.name}' turns {abs(mine):.4f}° per mm of cable, the cable's surface "
                            f"gives {abs(ratio):.4f}° ({(abs(mine) / abs(ratio) - 1.0) * 100.0:+.1f} %): left as it is")
            else:
                note = ""
        if abs(c.gap) > max(GAP_NOTE, 0.02 * item.cad_diameter) and c.kind != "BEND":
            gap = f"the CAD cable is drawn {_mm(abs(c.gap))} mm {'off' if c.gap > 0.0 else 'into'} it"
            note = f"{note}; {gap}" if note else gap
        if note != c.note:
            with _quiet(c):
                c.note = note


def _summary(scene, item, geo: dict) -> list[str]:
    kinds = {}
    for c in item.contacts:
        kinds[c.kind] = kinds.get(c.kind, 0) + 1
    words = {"BEND": "bend", "ROLLER": "roller", "SHEAVE": "sheave", "CHUTE": "chute"}
    counts = ", ".join(plural(kinds[k], words[k]) for k in ("SHEAVE", "ROLLER", "CHUTE", "BEND") if kinds.get(k))
    name = label(item)
    notes = [f"Cable '{name}': {counts}; Ø {_mm(item.cad_diameter)} mm, {geo['length']:.2f} m; the path is at most "
             f"{_mm(geo['deviation'])} mm off the cable as drawn in CAD"]
    made = sum(1 for c in item.contacts if c.made_joint)
    own = sum(1 for c in item.contacts if c.kind in TURNING and c.joint and not c.made_joint and not c.coupled)
    took = sum(1 for c in item.contacts if c.coupled and not c.made_joint)
    if made:
        notes.append(f"Cable '{name}': {plural(made, 'new joint')} so that what it touches turns with it")
    if took:
        notes.append(f"Cable '{name}': {plural(took, 'joint')} you had made now {'follows' if took == 1 else 'follow'} "
                     "the cable")
    if own:
        notes.append(f"Cable '{name}': {plural(own, 'part')} already had a joint that follows something: left as "
                     f"{'it is' if own == 1 else 'they are'}")
    odd = [c for c in item.contacts if c.note and not c.note.startswith("the CAD cable is drawn")]
    for c in odd[:8]:
        notes.append(f"Cable '{name}', '{c.name}': {c.note}")
    if len(odd) > 8:
        notes.append(f"Cable '{name}': {plural(len(odd) - 8, 'more contact')} with a note (see the list)")
    gaps = [c for c in item.contacts if "the CAD cable is drawn" in c.note]
    if gaps:
        worst = max(gaps, key=lambda c: abs(c.gap))
        notes.append(f"Cable '{name}': the CAD cable does not lie exactly on {plural(len(gaps), 'contact')} (at most "
                     f"{_mm(abs(worst.gap))} mm {'off' if worst.gap > 0.0 else 'into'} '{worst.name}'); the app "
                     "draws it where CAD drew it")
    return notes


# ---------------------------------------------------------------------------
# the node trees (shared by all cables)
# ---------------------------------------------------------------------------

def _float_at(b, geometry, index, attribute: str):
    """A number attribute of the shapes mesh at a point index."""
    s = b.new("GeometryNodeSampleIndex", data_type="FLOAT", domain="POINT")
    b.link(geometry, s.inputs["Geometry"])
    b.link(index, s.inputs["Index"])
    src = b.new("GeometryNodeInputNamedAttribute", data_type="FLOAT")
    src.inputs["Name"].default_value = attribute
    b.link(flex._sock(src.outputs, "Attribute"), flex._sock(s.inputs, "Value"))
    return flex._sock(s.outputs, "Value")


def _capture(b, geometry, value):
    """Keep a number per point of a curve (it goes along onto the tube made from it)."""
    cap = b.new("GeometryNodeCaptureAttribute", domain="POINT")
    cap.capture_items.new("FLOAT", "Value")
    b.link(geometry, cap.inputs["Geometry"])
    b.link(value, cap.inputs["Value"])
    return cap.outputs["Geometry"], cap.outputs["Value"]


def _build(ng, moving: bool) -> None:
    """The part's shape is replaced by a round tube through its points of the shapes mesh (which are in the
    part's own coordinates), with the attribute the cable looks read. ``moving``: the points of the frame shown;
    else the first ``Count`` points – no Scene Time node, so a frame change does not work the tube out again."""
    b = flex._Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    shapes = flex._shapes_geometry(b, gin)
    if moving:
        line, index = flex._line(b, gin, flex._moment(b, gin))
    else:
        mesh = b.new("GeometryNodeMeshLine")
        b.link(gin.outputs["Count"], mesh.inputs["Count"])
        mesh.inputs["Offset"].default_value = (0.0, 0.0, 0.0)
        line, index = mesh.outputs["Mesh"], b.new("GeometryNodeInputIndex").outputs[0]
    place = b.new("GeometryNodeSetPosition")
    b.link(line, place.inputs["Geometry"])
    b.link(flex._sample(b, shapes, index), place.inputs["Position"])
    curve = b.new("GeometryNodeMeshToCurve")                      # a poly line: arcs come as points, lines as two
    b.link(place.outputs[0], curve.inputs["Mesh"])
    path, along = _capture(b, curve.outputs[0], _float_at(b, shapes, index, S_ATTR))
    circle = b.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = SIDES
    b.link(gin.outputs["Radius"], circle.inputs["Radius"])
    profile, share = _capture(b, circle.outputs["Curve"], b.new("GeometryNodeSplineParameter").outputs["Factor"])
    tube = b.new("GeometryNodeCurveToMesh")
    b.link(path, tube.inputs["Curve"])
    b.link(profile, tube.inputs["Profile Curve"])
    tube.inputs["Fill Caps"].default_value = True
    phi = b.new("ShaderNodeMath", operation="MULTIPLY")
    b.link(share, phi.inputs[0])
    phi.inputs[1].default_value = 2.0 * math.pi
    cos, sin = b.new("ShaderNodeMath", operation="COSINE"), b.new("ShaderNodeMath", operation="SINE")
    b.link(phi.outputs[0], cos.inputs[0])
    b.link(phi.outputs[0], sin.inputs[0])
    xyz = b.new("ShaderNodeCombineXYZ")
    b.link(cos.outputs[0], xyz.inputs["X"])
    b.link(sin.outputs[0], xyz.inputs["Y"])
    b.link(along, xyz.inputs["Z"])
    store = b.new("GeometryNodeStoreNamedAttribute", data_type="FLOAT_VECTOR", domain="POINT")
    store.inputs["Name"].default_value = cable_looks.ATTR
    b.link(tube.outputs[0], store.inputs["Geometry"])
    b.link(xyz.outputs[0], flex._sock(store.inputs, "Value"))
    b.link(flex._slot(b, flex._shade(b, store.outputs[0])), gout.inputs[0])


def _tree(moving: bool):
    """The shared node tree (still or moving); made (again) when missing or of an older version."""
    name = TREES[bool(moving)]
    ng = bpy.data.node_groups.get(name)
    if ng is not None and ng.get(PART) == VERSION:
        return ng
    if ng is not None:
        ng.name = name + " old"
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng[PART] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for label_, kind_ in _INPUTS:
        ng.interface.new_socket(label_, in_out="INPUT", socket_type=kind_)
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    _build(ng, bool(moving))
    _STATE["inputs"].pop(name, None)
    return ng


def _tree_inputs(ng) -> dict:
    out = _STATE["inputs"].get(ng.name)
    if out is None:
        out = {s.name: s.identifier for s in ng.interface.items_tree
               if getattr(s, "item_type", "SOCKET") == "SOCKET" and s.in_out == "INPUT"}
        _STATE["inputs"][ng.name] = out
    return out


def _drop_unused_trees() -> None:
    for ng in [g for g in bpy.data.node_groups if g.get(PART) is not None and g.users == 0]:
        bpy.data.node_groups.remove(ng)
    _STATE["inputs"].clear()


# ---------------------------------------------------------------------------
# the shapes mesh (one per cable)
# ---------------------------------------------------------------------------

def _shapes(scene, item, create: bool = False):
    ob = item.shapes
    if ob is not None and not _alive(scene, ob):
        ob = None
    if ob is None and create:
        me = bpy.data.meshes.new(f"{SHAPES} {label(item)}")
        me[PART] = True
        ob = bpy.data.objects.new(f"{SHAPES} {label(item)}", me)
        ob[PART] = True
        ob.hide_viewport = ob.hide_render = ob.hide_select = True
        flex._collection(scene).objects.link(ob)
        with _quiet(item):
            item.shapes = ob
    return ob


def _remove_shapes(scene, item) -> None:
    ob = item.shapes
    with _quiet(item):
        item.shapes = None
    if ob is not None and _alive(scene, ob):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    col = bpy.data.collections.get(flex.COLLECTION)
    if col is not None and not len(col.objects) and not len(col.children):
        bpy.data.collections.remove(col)
    _STATE["arrays"].clear()


def _layout_of(sh) -> tuple:
    """(frames, points per frame, first frame) a shapes mesh holds."""
    if sh is None:
        return 0, 0, 0
    return int(sh.get(_FRAMES, 0)), int(sh.get(_PER, 0)), int(sh.get(_FIRST, 0))


def _write_shapes(scene, item, pts: np.ndarray, s: np.ndarray, first: int) -> None:
    """pts (F, n, 3) in the cable part's coordinates, s (F, n) metres."""
    frames, per = pts.shape[0], pts.shape[1]
    sh = _shapes(scene, item, create=True)
    me = sh.data
    if len(me.vertices) != frames * per or S_ATTR not in me.attributes:
        new = bpy.data.meshes.new(sh.name)
        new[PART] = True
        new.vertices.add(frames * per)
        new.attributes.new(S_ATTR, "FLOAT", "POINT")
        sh.data = new
        if me.users == 0:
            bpy.data.meshes.remove(me)
        me = new
    co = np.ascontiguousarray(pts, np.float32)
    along = np.ascontiguousarray(s, np.float32)
    if frames * per:
        me.vertices.foreach_set("co", co.reshape(-1))
        me.attributes[S_ATTR].data.foreach_set("value", along.reshape(-1))
    me.update_tag()
    for key, value in ((_FRAMES, frames), (_PER, per), (_FIRST, int(first))):
        if sh.get(key) != value:
            sh[key] = value
    if sh.parent is not None:
        sh.parent = None
    if sh.matrix_basis != Matrix.Identity(4):
        sh.matrix_basis = Matrix.Identity(4)
    _STATE["arrays"][(scene.name, item.name)] = (co, along)


def _arrays(scene, item):
    """(points (F, n, 3), s (F, n)) of the cable's shapes mesh, or None."""
    sh = _shapes(scene, item)
    frames, per, _first = _layout_of(sh)
    if sh is None or not frames * per or len(sh.data.vertices) != frames * per or S_ATTR not in sh.data.attributes:
        return None
    hit = _STATE["arrays"].get((scene.name, item.name))
    if hit is not None and hit[0].shape == (frames, per, 3):
        return hit
    co = np.empty(frames * per * 3, np.float32)
    sh.data.vertices.foreach_get("co", co)
    along = np.empty(frames * per, np.float32)
    sh.data.attributes[S_ATTR].data.foreach_get("value", along)
    _STATE["arrays"][(scene.name, item.name)] = (co.reshape(frames, per, 3), along.reshape(frames, per))
    return _STATE["arrays"][(scene.name, item.name)]


def _sync(scene, item) -> None:
    """The cable part has its modifier with the inputs of its shapes mesh; a cable that is off, broken or has no
    path shows its CAD shape (modifier off)."""
    part = item.part
    if not _alive(scene, part):
        return
    sh = _shapes(scene, item)
    frames, per, first = _layout_of(sh)
    on = bool(item.enabled) and not broken(scene, item) and sh is not None and frames >= 1 and per >= 2
    mod = part.modifiers.get(MOD)
    if not on:
        if mod is not None and (mod.show_viewport or mod.show_render):
            mod.show_viewport = mod.show_render = False
        return
    tree = _tree(frames > 1)
    ins = _tree_inputs(tree)
    if mod is None or mod.type != "NODES":
        if mod is not None:
            part.modifiers.remove(mod)
        mod = part.modifiers.new(MOD, "NODES")
        if len(part.modifiers) > 1:               # first: what comes after works on the shape drawn
            part.modifiers.move(len(part.modifiers) - 1, 0)
    changed_ = False
    if mod.node_group != tree:
        mod.node_group = tree
        changed_ = True
    values = {"Shapes": sh, "First": first, "Frames": frames, "Per frame": per, "Offset": 0, "Count": per,
              "Radius": 0.5 * float(item.diameter) / _scale(_world(part))}
    for name, value in values.items():
        changed_ |= flex._put(mod, ins[name], value)
    if not (mod.show_viewport and mod.show_render):
        mod.show_viewport = mod.show_render = True
    if changed_:
        part.update_tag()
    old = [g for g in bpy.data.node_groups if g.get(PART) is not None and g.get(PART) != VERSION and g.users == 0]
    for ng in old:
        bpy.data.node_groups.remove(ng)


# ---------------------------------------------------------------------------
# solving
# ---------------------------------------------------------------------------

def _counts(radii, wrap) -> list:
    """Points per arc: one every 4 degrees, closer on a wide bend so the tube stays within ``SAG`` of it."""
    out = []
    for r, w in zip(radii, np.atleast_1d(wrap)):
        step = min(P.STEP, 2.0 * math.acos(max(0.0, 1.0 - SAG / max(float(r), 1e-9))))
        out.append(P.point_counts([w], max(step, math.radians(0.25)))[0])
    return out


def _solve_item(scene, item, rel: np.ndarray) -> dict:
    """The cable's shape at F moments. ``rel`` (F, K, 4, 4): where its carriers are, as the cable part sees them.
    Returns core.paths.solve_frames' result (points in the cable part's coordinates) + "scale" (part units to
    metres), "names" (the wheels' names) and "problems" with those names in them."""
    wheels, obs, w_slots, a_slot, b_slot = _inputs_of(item)
    scale = _scale(_world(item.part))
    F, W = rel.shape[0], len(wheels)
    R, T = rel[:, :, :3, :3], rel[:, :, :3, 3]

    def point(slot, p):
        return np.einsum("fij,j->fi", R[:, slot], np.asarray(p, dtype=float)) + T[:, slot]

    centres, axes = np.zeros((F, W, 3)), np.zeros((F, W, 3))
    for k, c in enumerate(wheels):
        centres[:, k] = point(w_slots[k], c.centre)
        a = np.einsum("fij,j->fi", R[:, w_slots[k]], np.array(c.axis, dtype=float))
        axes[:, k] = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
    radii = np.array([radius_of(item, c) / scale for c in wheels])
    sides = np.array([float(c.side) for c in wheels])
    starts, ends = point(a_slot, item.a_point), point(b_slot, item.b_point)
    on0, on1 = item.a_kind == "WHEEL" and W > 0, item.b_kind == "WHEEL" and W > 0
    res = P.solve_frames(starts, centres, axes, radii, sides, ends, on0, on1, held=True)
    _STATE["solves"] += F
    if res["ok"].any() and W:
        counts = _counts(radii * scale, res["wrap"][res["ok"]].max(axis=0))
        if list(counts) != [int(n) for n in res["counts"]]:
            res = P.solve_frames(starts, centres, axes, radii, sides, ends, on0, on1, counts=counts, held=True)
    names = [c.name for c in wheels]
    res["problems"] = {f: _named(t, names) for f, t in res["problems"].items()}
    res["scale"], res["names"] = scale, names
    _lifted(res, names)
    return res


def _lifted(res: dict, names: list) -> None:
    """A wheel the cable lifts off during a motion: its wrap jumps from little to a loop round the wheel (or the
    solver says so with ``lifted``). Such frames are bad frames: they keep the shape of the last good one."""
    ok, wrap = res["ok"], res["wrap"]
    F = len(ok)
    res["off"] = {}
    flags = res.get("lifted")
    last = -1
    for f in range(F):
        if not ok[f]:
            continue
        bad = -1
        if flags is not None and np.asarray(flags)[f].any():
            bad = int(np.argmax(np.asarray(flags)[f]))
        elif last >= 0 and len(names):
            jump = np.abs(wrap[f] - wrap[last])
            if float(jump.max()) > WRAP_JUMP:
                bad = int(np.argmax(jump))
        if bad < 0:
            last = f
            continue
        ok[f] = False
        res["bad"][f] = bad
        res["off"][f] = bad
        res["problems"][f] = f"the cable no longer touches '{names[bad]}' (it has lifted off)"
        if last >= 0:
            for key in ("points", "s", "wrap", "length"):
                res[key][f] = res[key][last]


def _note(scene, item, res: dict, first) -> list[str]:
    """Write the cable's problem (or clear it) and what the contacts show; returns the warning sentences.
    ``first``: the frame of moment 0, None for the pose shown."""
    wheels = _wheels(item)
    name = label(item)
    ok = res["ok"]
    text, frame, warnings = "", 0, []
    when = "in this pose" if first is None else None
    if not ok.all():
        k = int(np.argmax(~ok))
        frame = 0 if first is None else first + k
        why = res["problems"].get(k, "")
        bad = int(res["bad"][k])
        if k in res.get("off", {}):
            text = f"no longer touches '{wheels[bad].name}' {when or f'at frame {frame}'}"
        else:
            what = f"cannot go round '{wheels[bad].name}'" if 0 <= bad < len(wheels) else "has no path"
            text = f"{what} {when or f'at frame {frame}'}: {why}"
        warnings.append(f"Cable '{name}' {text}")
    if ok.any() and item.mbr > 0.0 and wheels:
        wrap = res["wrap"][ok]
        i, radius = P.tightest([P.Wheel(None, None, radius_of(item, c), int(c.side)) for c in wheels], wrap.max(axis=0))
        if i >= 0 and radius < float(item.mbr) - 1e-6:
            tight = (f"bends tighter than its smallest bend (MBR {_mm(item.mbr)} mm) at '{wheels[i].name}': "
                     f"{_mm(radius)} mm")
            warnings.append(f"Cable '{name}' {tight}")
            if not text:
                text = tight
                if first is not None:
                    frame = first + int(np.flatnonzero(ok)[int(np.argmax(wrap[:, i] >= math.radians(1.0)))])
    if item.problem != text or item.problem_frame != frame:
        with _quiet(item):
            item.problem, item.problem_frame = text, frame
    if ok.any():
        k = int(np.argmax(ok))
        scale = res["scale"]
        s = res["s"][k] * scale
        with _quiet(item):
            item.length = float(res["length"][k] * scale)
        for i, c in enumerate(wheels):
            lo, n = int(res["first"][i]), int(res["counts"][i])
            mid = 0.5 * float(s[lo] + s[lo + n - 1])
            wrap = float(res["wrap"][k, i])
            if abs(c.wrap - wrap) > 1e-7 or abs(c.s - mid) > 1e-6:
                with _quiet(c):
                    c.wrap, c.s = wrap, mid
    return warnings


def _usable(scene, item) -> bool:
    return bool(item.enabled) and not broken(scene, item)


def _draw(scene, item, rel: np.ndarray, first, was=None) -> list[str]:
    """Solve for these places and write the shapes mesh (a pose without a path keeps the shape it had). ``was``:
    the wraps the cable had a moment ago (posing): a wrap that jumps from them means it lifted off that wheel."""
    res = _solve_item(scene, item, rel)
    if was is not None and len(rel) == 1 and res["ok"][0] and len(was) == res["wrap"].shape[1] and len(was) and \
            not item.problem:
        jump = np.abs(res["wrap"][0] - np.asarray(was))
        if float(jump.max()) > WRAP_JUMP:
            bad = int(np.argmax(jump))
            res["ok"][0] = False
            res["bad"][0] = bad
            res["off"][0] = bad
            res["problems"][0] = f"the cable no longer touches '{res['names'][bad]}' (it has lifted off)"
    warnings = _note(scene, item, res, first)
    if res["ok"].any():
        scale = res["scale"]
        _write_shapes(scene, item, res["points"], res["s"] * scale, 0 if first is None else first)
    _sync(scene, item)
    return warnings


def _places_key(item, obs) -> str:
    return json.dumps([ob.name for ob in obs])


def _store_places(scene, item, rel: np.ndarray, obs, first: int) -> None:
    sh = _shapes(scene, item, create=True)
    idprops.store_array(sh, _PLACES, rel[:, :, :3, :], dtype=np.float32)
    sh[_PLACES_OBS] = _places_key(item, obs)
    sh[_PLACES_FIRST] = int(first)


def _drop_places(scene, item) -> None:
    sh = _shapes(scene, item)
    if sh is not None:
        for key in (_PLACES, _PLACES_OBS, _PLACES_FIRST):
            if key in sh:
                del sh[key]


def _stored_places(scene, item, obs):
    """(rel (F, K, 4, 4), first frame) read at the last Build for these carriers, or None."""
    sh = _shapes(scene, item)
    if sh is None or _PLACES not in sh or sh.get(_PLACES_OBS) != _places_key(item, obs) or not obs:
        return None
    data = np.array(sh[_PLACES], dtype=float)
    if data.size % (len(obs) * 12):
        return None
    data = data.reshape(-1, len(obs), 3, 4)
    rel = np.zeros((len(data), len(obs), 4, 4))
    rel[:, :, :3, :] = data
    rel[:, :, 3, 3] = 1.0
    return rel, int(sh.get(_PLACES_FIRST, 1))


def _rebuild(scene, item) -> list[str]:
    """The cable's shape again for how it is set now: the pose shown, or every frame read at the last Build."""
    if item is None:
        return []
    _STATE["busy"] += 1
    try:
        if not _usable(scene, item):
            if item.problem:
                with _quiet(item):
                    item.problem, item.problem_frame = "", 0
            _sync(scene, item)
            return []
        _wheels_, obs, _w, _a, _b = _inputs_of(item)
        stored = _stored_places(scene, item, obs) if _baked(scene) else None
        if stored is not None:
            return _draw(scene, item, stored[0], stored[1])
        if not _baked(scene):
            _drop_places(scene, item)
        rel = _rel_now(item, obs)
        _STATE["last"][(scene.name, item.name)] = rel
        return _draw(scene, item, rel[None], None)
    finally:
        _STATE["busy"] -= 1


# ---------------------------------------------------------------------------
# the look: what the material reads, and the group
# ---------------------------------------------------------------------------

def look_of(item) -> list:
    """The four numbers of ``fr_cable_look`` for the cable's settings (pitch m, starts, width, kind); [] for the
    plain look."""
    if item.look not in cable_looks.KINDS:
        return []
    return cable_looks.look_values(item.look, float(item.diameter), float(item.pitch), HAND * float(item.angle),
                                   float(item.stripe))


def _apply_look(scene, item) -> None:
    part = item.part
    if not _alive(scene, part):
        return
    values = look_of(item)
    if values:
        have = list(part[cable_looks.LOOK]) if cable_looks.LOOK in part else []
        if len(have) != len(values) or any(abs(a - b) > 1e-9 for a, b in zip(have, values)):
            idprops.store_array(part, cable_looks.LOOK, values)
            part.update_tag()
    elif cable_looks.LOOK in part:
        del part[cable_looks.LOOK]
        part.update_tag()
    _group(scene, item)


def _group(scene, item) -> None:
    """Look = Power cable / Steel wire rope: the part goes into the manual group of that name (made with the
    look's material when it is new). Plain: back to where it was – if the app put it there and it is still there."""
    from . import logic
    part = item.part
    s = scene.fresing
    want = GROUPS.get(item.look)
    cur = part.get("fr_group_manual", "") or ""
    if want:
        if cur == want:
            return
        if WAS not in part:
            part[WAS] = cur
        new = s.groups.get(want) is None
        part["fr_group_manual"] = want
        g = logic.ensure_group(s, want)
        if new:
            g.material = cable_looks.MATERIALS[item.look]
    else:
        if WAS not in part:
            return
        was = part[WAS]
        del part[WAS]
        if cur not in GROUPS.values():
            return                              # the user put it somewhere else since: it stays there
        if was:
            part["fr_group_manual"] = was
        else:
            del part["fr_group_manual"]
    logic.apply_rules(scene)
    logic.refresh_group_materials(scene)


def _pay_driver(scene, item) -> None:
    """``fr_cable_pay`` on the part = metres paid out x direction + 2.0, by a driver that needs no Python."""
    part = item.part
    if not _alive(scene, part):
        return
    j = joints.find(scene, item.joint) if item.joint else None
    top, k, c = joints.chain_affine(scene, j) if j is not None else (None, 1.0, 0.0)
    path = f'["{cable_looks.PAY}"]'
    ad = part.animation_data
    fc = ad.drivers.find(path) if ad is not None else None
    if top is None or top.motion is None:
        if fc is not None:
            part.driver_remove(path)
        part[cable_looks.PAY] = cable_looks.PAY_BIAS
        return
    sign = -1.0 if item.reverse else 1.0
    expr = joints.expression(k * sign, c * sign + cable_looks.PAY_BIAS)
    if fc is not None and fc.driver.type == "SCRIPTED" and fc.driver.expression == expr and \
            len(fc.driver.variables) == 1 and fc.driver.variables[0].targets[0].id == top.motion:
        return
    if cable_looks.PAY not in part:
        part[cable_looks.PAY] = cable_looks.PAY_BIAS
    part.id_properties_ui(cable_looks.PAY).update(min=-1.0e7, max=1.0e7, soft_min=-1.0e7, soft_max=1.0e7,
                                                  description="Metres of cable paid out + 2 (the cable looks read it)")
    if fc is not None:
        part.driver_remove(path)
    joints._scripted(part.driver_add(path), top.motion, expr)
    part.update_tag()


def _strip(scene, item, part) -> None:
    """A part is no cable any more: modifier, properties, driver and the look's group off."""
    try:
        mod = part.modifiers.get(MOD)
        if mod is not None:
            part.modifiers.remove(mod)
        try:
            part.driver_remove(f'["{cable_looks.PAY}"]')
        except TypeError:
            pass
        for key in (cable_looks.PAY, cable_looks.LOOK, PART):
            if key in part:
                del part[key]
        if WAS in part:
            from . import logic
            was = part[WAS]
            del part[WAS]
            if (part.get("fr_group_manual", "") or "") in GROUPS.values():
                if was:
                    part["fr_group_manual"] = was
                else:
                    del part["fr_group_manual"]
                logic.apply_rules(scene)
                logic.refresh_group_materials(scene)
        part.update_tag()
    except ReferenceError:
        pass


# ---------------------------------------------------------------------------
# what the rest of the app calls
# ---------------------------------------------------------------------------

def _cad_path(scene, item, memo: dict) -> tuple:
    """The cable's path with everything in the CAD pose: (points (n, 3) world, the metres along it (n,), the
    solve's result). No points when it has no path there."""
    res = _solve_item(scene, item, _cad_rel(item, memo))
    if not res["ok"].all():
        return np.zeros((0, 3)), np.zeros(0), res
    return _at(_cad(item.part, memo), res["points"][0]), res["s"][0] * res["scale"], res


def _free_ends(scene, item) -> None:
    """A free end runs straight on for the length typed (0 = as drawn in CAD): its point moves along the line on
    which the cable leaves its last bend."""
    wheels = _wheels(item)
    if not wheels or not _usable(scene, item):
        return
    todo = []
    for key, k in (("a", 0), ("b", -1)):
        if not getattr(item, key + "_free_end") or getattr(item, key + "_kind") != "FIXED" or \
                getattr(item, key + "_part") != wheels[k].carrier:
            continue
        if getattr(item, key + "_free") > 0.0:
            todo.append((key, k))
        elif key + "_cad_point" in item:        # 0: where CAD drew its end
            cad = tuple(float(v) for v in item[key + "_cad_point"])
            if max(abs(a - b) for a, b in zip(cad, getattr(item, key + "_point"))) > 1e-7:
                with _quiet(item):
                    setattr(item, key + "_point", cad)
    if not todo:
        return
    memo: dict = {}
    res = _solve_item(scene, item, _cad_rel(item, memo))
    if not res["ok"].all():
        return
    pts, scale = res["points"][0], res["scale"]
    for key, k in todo:
        want = float(getattr(item, key + "_free"))
        if key == "a":
            end, leaves = pts[0], pts[int(res["first"][0])]
        else:
            end, leaves = pts[-1], pts[int(res["first"][-1]) + int(res["counts"][-1]) - 1]
        run = float(np.linalg.norm(end - leaves))
        if run <= 1e-9 or abs(run * scale - want) < 1e-6:
            continue
        new = leaves + (end - leaves) / run * (want / scale)
        to_carrier = np.linalg.inv(_cad(wheels[k].carrier, memo)) @ _cad(item.part, memo)
        with _quiet(item):
            setattr(item, key + "_point", tuple(_at(to_carrier, new)))


def changed(scene, item) -> None:
    """A setting of ``item`` changed (props.py calls this): its couplings, its look and its shape are brought up
    to date – along a built animation too, from the places read at Build."""
    if _STATE["busy"] or index_of(scene, item) < 0:
        return
    name = item.name
    if _alive(scene, item.part):
        if item.get("look_was", item.look) != item.look:      # another look: its usual pitch, unless one was typed
            was = item["look_was"]
            usual = ROPE_LAY * item.diameter if was == "ROPE" else max(0.1, round(POWER_PITCH * item.diameter, 2))
            if abs(item.pitch - usual) < 1e-6 or abs(item.pitch - 0.5) < 1e-9:
                with _quiet(item):
                    item.pitch = _default_pitch(item)
        item["look_was"] = item.look
        _STATE["busy"] += 1
        try:
            _couple(scene, item)
            item = find(scene, name)
            _apply_look(scene, item)
            _pay_driver(scene, item)
            _free_ends(scene, item)
        finally:
            _STATE["busy"] -= 1
    _rebuild(scene, item)


def contact_changed(scene, contact) -> None:
    """A contact's "Turns with the cable" changed (props.py calls this)."""
    if _STATE["busy"]:
        return
    item, _k = _owner(scene, contact)
    if item is not None:
        _couple(scene, item)


def _guarded(scene, item, change, why: str) -> None:
    """Make a change to the contacts or ends and draw the path again; when the cable then has no path, put
    everything back and raise PathError(why + the reason)."""
    name = item.name
    snap = _snapshot(item)
    _STATE["busy"] += 1
    try:
        change()
        item = find(scene, name)
        _wheels_, obs, _w, _a, _b = _inputs_of(item)
        res = _solve_item(scene, item, _rel_now(item, obs)[None]) if _usable(scene, item) else None
        if res is not None and not res["ok"].all():
            _restore(item, snap)
            raise PathError(f"{why}: {res['problems'].get(0, 'the cable has no path then')}")
    finally:
        _STATE["busy"] -= 1


def _axis_of(ob, hit):
    """The round face axis of ``ob`` that is meant, as (a point on it, its direction) in the part's own
    coordinates: an axis the part is round all the way about when it has one (a sheave: its bore, groove and
    flanges are one line, whatever was clicked), else the axis of the round face that was clicked (a chute's
    trough); with nothing clicked the widest. None when the part has no round face."""
    me = ob.data
    if me is None or "fr_axes" not in me:
        return None
    axes = np.array(me["fr_axes"], dtype=float).reshape(-1, 7)
    axes = axes[np.linalg.norm(axes[:, 3:6], axis=1) > 1e-9]
    if not len(axes):
        return None
    verts, _tris = flex._mesh_arrays(me)
    d = axes[:, 3:6] / np.linalg.norm(axes[:, 3:6], axis=1, keepdims=True)
    full = np.array([bool(P.is_round(verts, a[:3], dk)) for a, dk in zip(axes, d)])
    pool = np.flatnonzero(full) if full.any() else np.arange(len(axes))

    def reach(k):                               # how far the part reaches from this axis
        rel = verts - axes[k, :3]
        return float(np.linalg.norm(rel - np.outer(rel @ d[k], d[k]), axis=1).max())

    size = np.array([axes[k, 6] if axes[k, 6] > 0.0 else reach(k) for k in pool])
    if hit is not None and len(pool) > 1:
        local = _at(np.linalg.inv(_world(ob)), np.array(hit, dtype=float))
        rel = local - axes[pool, :3]
        rho = np.linalg.norm(rel - d[pool] * np.einsum("ij,ij->i", rel, d[pool])[:, None], axis=1)
        k = int(pool[int(np.argmin(np.abs(rho - size)))])
    else:
        k = int(pool[int(np.argmax(size))])
    return axes[k, :3], d[k]


def add_contact(scene, item, ob, hit=None) -> int:
    """A clicked part joins the path: a roller when the cable already runs over it, else something the cable goes
    round (a sheave when it is round all the way, else a chute). ``hit``: the point clicked (world) – the cable
    is laid on that side of it. Returns its place in the list. Raises PathError in plain words."""
    name = _part_name(ob) or "Nothing"
    if not _usable(scene, item):
        raise PathError("This cable has no path yet: use 'From CAD cable' first.")
    if ob is None or ob.type != "MESH" or ob.get(build.PROP_KIND) != "part" or ob == item.part:
        raise PathError(f"'{name}' is not a part the cable can run over.")
    found = _axis_of(ob, hit)
    if found is None:
        raise PathError(f"'{name}' has no round face: the cable needs a roller, a sheave or a round chute.")
    memo: dict = {}
    w = flex._cad_world(ob, memo)
    origin, axis = _at(w, found[0]), _unit(w[:3, :3] @ found[1])
    verts, tris = flex._mesh_arrays(ob.data)
    vw = _at(w, verts)
    full = bool(P.is_round(vw, origin, axis))
    cable_r = 0.5 * float(item.cad_diameter or item.diameter)
    line, s_line, _res = _cad_path(scene, item, memo)    # the path as it is, in the CAD pose (world)
    if len(line) < 2:
        raise PathError("This cable has no path in the CAD pose: use 'From CAD cable' first.")
    # where along its axis the cable lies: where it was clicked, else where the cable passes nearest
    hit_cad = None
    if hit is not None:
        hit_cad = _at(w @ np.linalg.inv(_world(ob)), np.array(hit, dtype=float))
        at = float((hit_cad - origin) @ axis)
    else:
        rel = line - origin
        at = float((rel @ axis)[int(np.argmin(np.linalg.norm(rel - np.outer(rel @ axis, axis), axis=1)))])
    place, seat = P.seat(vw, tris, origin, axis, at, cable_r, search=2.0 * cable_r)
    here = float(P.surface_radius(vw, tris, origin, axis, at, 0.5 * cable_r))
    if seat <= 0.0 or here <= 0.0 or seat > here + cable_r - max(0.0002, 0.02 * cable_r):
        # no groove there (a plain roller, a drum's barrel: ``seat`` may sit anywhere within its search): the cable
        # lies where it is, on the surface
        place, seat = at, here + cable_r
    if here <= 0.0:
        raise PathError(f"The cable does not reach '{name}': it has no round surface where the cable would lie.")
    centre = origin + axis * float(place)
    surface = float(P.surface_radius(vw, tris, origin, axis, float(place), 0.5 * cable_r)) or seat - cable_r
    for c in item.contacts:
        if c.part == ob and np.linalg.norm(_row_of(c, memo)["centre"] - centre) < 0.5 * seat:
            raise PathError(f"'{name}' is in the cable's list already.")
    row = {"centre": centre, "axis": axis, "radius": float(seat), "surface": surface, "side": 1, "s": 0.0,
           "wrap": 0.0, "gap": 0.0, "full": full, "part": ob, "name": name, "note": "", "user": True}
    # does the cable run over it already (a roller)? its nearest pass lies at the seat's distance, square across
    seg = line[1:] - line[:-1]
    t = np.clip(np.einsum("ij,ij->i", centre - line[:-1], seg) / np.maximum(np.einsum("ij,ij->i", seg, seg), 1e-18),
                0.0, 1.0)
    foot = line[:-1] + seg * t[:, None]
    dist = np.linalg.norm(np.cross(foot - centre, axis), axis=1)
    i = int(np.argmin(dist))
    heading = _unit(seg[i])
    s_at = float(s_line[i] + t[i] * (s_line[i + 1] - s_line[i]))
    tol = max(P.TOUCH_TOL[0], P.TOUCH_TOL[1] * cable_r)
    passes = abs(float(dist[i]) - seat) <= tol and abs(float(heading @ axis)) < math.sin(P.SQUARE)
    iname = item.name
    if passes and full:
        row.update(kind="ROLLER", side=P._side(foot[i], centre, axis, heading), s=s_at, gap=float(dist[i]) - seat)
        index = next((n for n, c in enumerate(item.contacts) if c.s > s_at), len(item.contacts))
    else:
        if hit_cad is None and float(dist[i]) > seat + 2.0 * cable_r:
            raise PathError(f"The cable does not reach '{name}': it passes {_mm(float(dist[i]) - seat)} mm from "
                            "it. Click the place on it where the cable should lie.")
        row["kind"] = "SHEAVE" if full else "CHUTE"
        hit_dir = None
        if hit_cad is not None:
            h = hit_cad - centre
            h = h - axis * float(h @ axis)
            hit_dir = _unit(h) if float(np.linalg.norm(h)) > 1e-9 else None
        best = _fit_wheel(scene, item, row, hit_dir, memo)
        if best is None:
            raise PathError(f"The cable does not reach '{name}': it cannot be laid round it from where it runs "
                            "now. Click the place on it where the cable should lie, or add the parts before it "
                            "first.")
        index, row = best
        arc = row.pop("arc")
        if not full:                            # a chute: is its surface really round where the cable would bend?
            take = arc[np.unique(np.linspace(0, len(arc) - 1, min(len(arc), 9)).round().astype(int))]
            if _points_on(vw, tris, take, cable_r + tol) < UNDER * len(take):
                raise PathError(f"The cable would not lie on '{name}': it is not round where the cable would bend "
                                "round it. Pick a sheave, a roller or a round chute.")

    def change():
        it = find(scene, iname)
        _make_joints(scene, it, [row], memo)
        it = find(scene, iname)
        if "carrier" not in row:
            row["carrier"] = ob
        rows = [_row_of(c, memo) for c in it.contacts]
        rows.insert(index, row)
        with _quiet(it):
            it.contacts.clear()
            for d_ in rows:
                _write_contact(it.contacts.add(), d_, memo)
            it.contacts_index = index
        _reseat_ends(scene, it, memo)

    before = {j.name for j in scene.fresing.joints}
    try:
        _guarded(scene, item, change, f"'{name}' cannot join the path")
    except PathError:
        _remove_joints(scene, [j.name for j in scene.fresing.joints if j.name not in before])
        raise
    item = find(scene, iname)
    _notes_of_joints(scene, item, {})
    _couple(scene, item)
    item = find(scene, iname)
    with _quiet(item):
        item.moving = _can_move(item)
    forget()
    _rebuild(scene, item)
    return index


def _fit_wheel(scene, item, row: dict, hit_dir, memo: dict):
    """Where in the list and on which side a new wheel goes: every place and both sides are tried in the CAD
    pose. Of those that give a path that really goes round it, the one wins whose arc has the clicked point
    nearest its middle; with nothing clicked, the shortest. Returns (index among all contacts, the row) or
    None."""
    wheels = _wheels(item)
    rows = [_row_of(c, memo) for c in wheels]
    inv = np.linalg.inv(_cad(item.part, memo))
    scale = _scale(_cad(item.part, memo))

    def local(p):
        return _at(inv, p)

    def end(key):
        ob = getattr(item, key + "_part")
        return _at(inv @ _cad(ob, memo), np.array(getattr(item, key + "_point"), dtype=float))

    on0, on1 = item.a_kind == "WHEEL" and bool(wheels), item.b_kind == "WHEEL" and bool(wheels)
    best = None
    lo, hi = (1 if on0 else 0), (len(rows) - 1 if on1 else len(rows))
    for k in range(lo, hi + 1):
        for side in (1, -1):
            cand = rows[:k] + [dict(row, side=side)] + rows[k:]
            ws = [P.Wheel(local(d["centre"]), _unit(inv[:3, :3] @ d["axis"]),
                          (d["radius"] + (0.0 if d["kind"] == "BEND" or item.cad_diameter <= 0.0
                                          else 0.5 * (item.diameter - item.cad_diameter))) / scale, d["side"])
                  for d in cand]
            path = P.solve(end("a"), ws, end("b"), on0, on1, held=True)
            if not path.ok or path.wrap[k] < math.radians(0.5):
                continue
            first, n = int(path.first[k]), int(path.counts[k])
            score = float(path.length)
            if hit_dir is not None:
                mid = _unit(path.points[first + n // 2] - ws[k].centre) if n > 2 else \
                    _unit(0.5 * (path.points[first] + path.points[first + n - 1]) - ws[k].centre)
                score = math.acos(float(np.clip(mid @ _unit(inv[:3, :3] @ hit_dir), -1.0, 1.0)))
                if score > 0.5 * float(path.wrap[k]) + math.radians(5.0):
                    continue                    # the clicked point is not on this arc
            if best is None or score < best[0]:
                s_mid = 0.5 * float(path.s[first] + path.s[first + n - 1]) * scale
                best = (score, k, dict(row, side=side, s=s_mid, wrap=float(path.wrap[k]),
                                       arc=_at(_cad(item.part, memo), path.points[first:first + n])))
    if best is None:
        return None
    _length, k, new = best
    # its place among all contacts: after the wheel before it, by its place along the cable among the rollers
    index, seen = len(item.contacts), 0
    for n, c in enumerate(item.contacts):
        if c.kind in SHAPING:
            if seen == k:
                index = n
                break
            seen += 1
    while index > 0 and item.contacts[index - 1].kind == "ROLLER" and item.contacts[index - 1].s > new["s"]:
        index -= 1
    return index, new


def _reseat_ends(scene, item, memo: dict) -> None:
    """An end that starts on its first wheel, or a free end, stays with the wheel that is first (last) now."""
    wheels = _wheels(item)
    for key, k in (("a", 0), ("b", -1)):
        kind, free = getattr(item, key + "_kind"), getattr(item, key + "_free_end")
        ob = getattr(item, key + "_part")
        if kind == "WHEEL" and not wheels:
            want, kind = flex._stay_part(item.part), "FIXED"
        elif kind == "WHEEL" or free:
            want = wheels[k].carrier if wheels else flex._stay_part(item.part)
        else:
            continue
        if want == ob and kind == getattr(item, key + "_kind"):
            continue
        p = np.array(getattr(item, key + "_point"), dtype=float)
        move = np.linalg.inv(_cad(want, memo)) @ _cad(ob, memo) if _alive(scene, ob) else np.eye(4)
        with _quiet(item):
            setattr(item, key + "_kind", kind)
            setattr(item, key + "_part", want)
            setattr(item, key + "_uid", _uid(want))
            setattr(item, key + "_point", tuple(_at(move, p)))
        if key + "_cad_point" in item:
            item[key + "_cad_point"] = [float(v) for v in _at(move, np.array(item[key + "_cad_point"], dtype=float))]


def remove_contact(scene, item, index: int) -> None:
    """Take a contact off the list: the joint the app made for it goes, one the user made stops following the
    cable. Raises PathError when the cable has no path without it."""
    if not 0 <= index < len(item.contacts):
        return
    iname = item.name
    c = item.contacts[index]
    cname, joint, made, coupled = c.name, c.joint, bool(c.made_joint), bool(c.coupled)
    shared = any(o.joint == joint for k, o in enumerate(item.contacts) if k != index) if joint else False

    def change():
        it = find(scene, iname)
        memo: dict = {}
        with _quiet(it):
            it.contacts.remove(index)
            it.contacts_index = max(0, min(it.contacts_index, len(it.contacts) - 1))
        _reseat_ends(scene, it, memo)

    _guarded(scene, item, change, f"Without '{cname}' the cable has no path")
    if joint and not shared:
        if made:
            _remove_joints(scene, [joint])
        elif coupled:
            j = joints.find(scene, joint)
            if j is not None and j.follows == find(scene, iname).joint:
                joints.set_follows(scene, j, "")
    item = find(scene, iname)
    with _quiet(item):
        item.moving = _can_move(item)
    forget()
    _rebuild(scene, item)


def flip_contact(scene, item, index: int) -> None:
    """The cable goes round the other side of this contact (a roller: it turns the other way). Raises PathError
    when it cannot."""
    if not 0 <= index < len(item.contacts):
        return
    iname = item.name
    cname = item.contacts[index].name

    def change():
        c = find(scene, iname).contacts[index]
        with _quiet(c):
            c.side = -int(c.side)
            c.user = True

    _guarded(scene, item, change, f"The cable cannot go round the other side of '{cname}'")
    item = find(scene, iname)
    _couple(scene, item)
    _rebuild(scene, find(scene, iname))


def set_end(scene, item, end: str, ob=None) -> None:
    """End "A" (the start) or "B" stays with the part ``ob`` from now on, where it is now; None: a free end again
    (it stays with the nearest bend). Raises PathError."""
    key = end.lower()
    if key not in ("a", "b"):
        raise PathError("Pick end A or end B.")
    if not _usable(scene, item):
        raise PathError("This cable has no path yet: use 'From CAD cable' first.")
    wheels = _wheels(item)
    if ob is not None and (ob.get(build.PROP_KIND) not in build.MODEL_KINDS or ob == item.part):
        raise PathError(f"'{_part_name(ob)}' is not a part of the model the end can sit on.")
    iname = item.name
    memo: dict = {}
    line, _s, _res = _cad_path(scene, item, memo)
    if not len(line):
        raise PathError("This cable has no path in the CAD pose: use 'From CAD cable' first.")
    point = line[0] if key == "a" else line[-1]          # where the end is, CAD pose (world)

    def change():
        it = find(scene, iname)
        target = ob
        if target is None:
            target = wheels[0 if key == "a" else -1].carrier if wheels else flex._stay_part(it.part)
        with _quiet(it):
            setattr(it, key + "_kind", "FIXED")
            setattr(it, key + "_part", target)
            setattr(it, key + "_uid", _uid(target))
            setattr(it, key + "_point", tuple(_at(np.linalg.inv(_cad(target, memo)), point)))
            setattr(it, key + "_free_end", ob is None)
        if ob is None:
            if key + "_user" in it:
                del it[key + "_user"]
            it[key + "_cad_point"] = [float(v) for v in getattr(it, key + "_point")]
        else:
            it[key + "_user"] = True
            for extra in ("_cad_free", "_cad_point"):
                if key + extra in it:
                    del it[key + extra]

    _guarded(scene, item, change, "The end cannot go there")
    item = find(scene, iname)
    with _quiet(item):
        item.moving = _can_move(item)
    forget()
    _rebuild(scene, item)


def remove(scene, index: int) -> None:
    """Take the cable off the list: its part shows its CAD shape again, the joints the app made go, the joints it
    made follow the cable move by themselves again. A cable joint that was taken (not made) stays."""
    s = scene.fresing
    if not 0 <= index < len(s.cables):
        return
    item = s.cables[index]
    name = item.name
    _STATE["busy"] += 1
    try:
        gone = [c.joint for c in item.contacts if c.made_joint and c.joint]
        loose = [c.joint for c in item.contacts if c.coupled and not c.made_joint and c.joint]
        lead, made_lead = item.joint, bool(item.made_joint)
        todo = [n for n in loose if joints.find(scene, n) is not None and joints.find(scene, n).follows == lead]
        if todo:
            def run():
                for n in todo:
                    joints.set_follows(scene, joints.find(scene, n), "")
            if len(todo) <= 2:
                run()
            else:
                with joints._batch(scene):
                    run()
        _remove_joints(scene, list(dict.fromkeys(gone)) + ([lead] if made_lead and lead else []))
        item = find(scene, name)
        if _alive(scene, item.part):
            _strip(scene, item, item.part)
        _remove_shapes(scene, item)
        s.cables.remove(index_of(scene, item))
        s.cables_index = max(0, min(s.cables_index, len(s.cables) - 1))
    finally:
        _STATE["busy"] -= 1
    forget()
    _drop_unused_trees()


def _moved(scene, item):
    """The carriers' places when they are not where the cable was solved for, else None."""
    _wheels_, obs, _w, _a, _b = _inputs_of(item)
    rel = _rel_now(item, obs)
    last = _STATE["last"].get((scene.name, item.name))
    if last is not None and last.shape == rel.shape and float(np.abs(rel - last).max(initial=0.0)) <= MOVE_TOL:
        return None
    return rel


def _live(scene, force: bool = False) -> bool:
    """Solve the moving cables whose carriers moved against them (all cables with ``force``) for where things are
    now. True when something was written."""
    wrote = False
    for it in list(scene.fresing.cables):
        if not _usable(scene, it) or not (it.moving or force):
            continue
        rel = _moved(scene, it)
        if rel is None and not force:
            continue
        _wheels_, obs, _w, _a, _b = _inputs_of(it)
        rel = _rel_now(it, obs) if rel is None else rel
        _STATE["last"][(scene.name, it.name)] = rel
        _drop_places(scene, it)
        _draw(scene, it, rel[None], None, was=None if force else [float(c.wrap) for c in _wheels(it)])
        wrote = True
    return wrote


def refresh(scene, force: bool = False) -> None:
    """Live: the cables for where their sheaves are now (after a pose set by a script, in the background too). With
    a built animation the frames written at Build show; ``force`` works those out again."""
    if not len(scene.fresing.cables) or _STATE["busy"]:
        return
    if _baked(scene):
        if force:
            for it in list(scene.fresing.cables):
                _rebuild(scene, it)
        return
    if not force and not any(it.moving and it.enabled for it in scene.fresing.cables):
        return
    try:
        layer = bpy.context.view_layer if bpy.context.scene == scene else scene.view_layers[0]
        layer.update()
    except Exception:
        pass
    _STATE["busy"] += 1
    try:
        _live(scene, force=force)
    finally:
        _STATE["busy"] -= 1


def _bake(scene) -> list[str]:
    first, end = int(scene.frame_start), int(max(scene.frame_start, scene.frame_end))
    frames = end - first + 1
    notes, its = [], []
    for it in scene.fresing.cables:
        if not it.enabled:
            continue
        why = broken(scene, it)
        if why:
            if it.part_uid:
                notes.append(f"Cable '{label(it)}': {why} (see 4 Motion > Cables and paths)")
            continue
        its.append(it.name)
    can = [n for n in its if _can_move(find(scene, n))]
    animated = [n for n in can if _animated(find(scene, n))]
    mats = {}
    if can:
        obs = {}
        for n in can:
            it = find(scene, n)
            for ob in [it.part] + _inputs_of(it)[1]:
                obs[ob.name] = ob
        mats = flex.read_places(scene, list(obs.values()), first, frames if animated else 1, keep_shown=False)
        _STATE["steps"] += frames if animated else 1
    for n in its:
        it = find(scene, n)
        _wheels_, obs, _w, _a, _b = _inputs_of(it)
        if n in can:
            inv = np.linalg.inv(mats[it.part.name])
            rel = np.stack([inv @ mats[ob.name] for ob in obs], axis=1) if obs else np.zeros((len(inv), 0, 4, 4))
            if n not in animated or float(np.abs(rel - rel[:1]).max(initial=0.0)) <= MOVE_TOL:
                rel = rel[:1]
        else:
            rel = _rel_now(it, obs)[None]
        moving = len(rel) > 1
        if moving:
            _store_places(scene, it, rel, obs, first)
        else:
            _drop_places(scene, it)
        if it.moving != moving:
            with _quiet(it):
                it.moving = moving
        _STATE["last"].pop((scene.name, n), None)
        notes += _draw(scene, it, rel, first)
    return notes


def bake(scene, anim) -> list[str]:
    """The last step of every Build: a moving cable gets a shape for every frame. Returns warnings."""
    if not len(scene.fresing.cables):
        return []
    forget()
    _STATE["busy"] += 1
    try:
        return _bake(scene)
    except Exception as exc:                    # a Build never fails over a cable
        return [f"The cables could not be worked out ({exc or type(exc).__name__}): they show as they were"]
    finally:
        _STATE["busy"] -= 1


def after_clear(scene) -> None:
    """'Clear keys': a cable over things that can move follows them live again."""
    if not len(scene.fresing.cables):
        return
    _STATE["busy"] += 1
    try:
        for it in list(scene.fresing.cables):
            if not _usable(scene, it):
                continue
            can = _can_move(it)
            had = _layout_of(_shapes(scene, it))[0] > 1
            if it.moving != can:
                with _quiet(it):
                    it.moving = can
            if can or had:
                _drop_places(scene, it)
                _wheels_, obs, _w, _a, _b = _inputs_of(it)
                _draw(scene, it, _rel_now(it, obs)[None], None)
    finally:
        _STATE["busy"] -= 1
    forget()                                    # the parts may not be back in place yet: look again at the next update


def _moment_now(scene, item) -> int:
    frames, _per, first = _layout_of(_shapes(scene, item))
    return max(0, min(int(round(scene.frame_current + scene.frame_subframe - first)), frames - 1))


def shape_now(scene, item) -> np.ndarray:
    """The drawn centreline at the frame shown (n, 3), world: read from the shapes mesh, not solved again."""
    got = _arrays(scene, item)
    if got is None or not _alive(scene, item.part):
        return np.zeros((0, 3))
    return _at(_world(item.part), got[0][_moment_now(scene, item)].astype(float))


def lengths_now(scene, item) -> np.ndarray:
    """The metres along the cable of every point of ``shape_now``."""
    got = _arrays(scene, item)
    return got[1][_moment_now(scene, item)].astype(float) if got is not None else np.zeros(0)


def wheels_now(scene, item) -> list:
    """``core.paths.Wheel`` for every contact the cable bends round, world, where they are now."""
    out = []
    for c in _wheels(item):
        if not _alive(scene, c.carrier):
            continue
        m = _world(c.carrier)
        out.append(P.Wheel(_at(m, np.array(c.centre, dtype=float)), _unit(m[:3, :3] @ np.array(c.axis, dtype=float)),
                           radius_of(item, c), int(c.side)))
    return out


def status(scene, item) -> tuple[str, str]:
    """(a few words, "OK" | "WARN" | "ERROR" | "OFF") for the list row and the panel."""
    if not item.enabled:
        return "off", "OFF"
    why = broken(scene, item)
    if why:
        return why, "ERROR"
    if _arrays(scene, item) is None:
        return (item.problem or "its path cannot be drawn"), "ERROR"
    if item.problem:
        return item.problem, "WARN"
    n = len(item.contacts)
    return f"{item.length:.2f} m over {plural(n, 'contact')}" + (", a shape per frame" if item.moving and _baked(scene)
                                                                else ""), "OK"


_WORDS = ("CABLE", "CABLES", "KABEL", "KABELS", "WIRE ROPE", "WIREROPE", "ROPE", "ROPES", "WIRE", "SEIL", "DRAHTSEIL",
          "STAHLSEIL", "STAALKABEL", "STAALDRAAD", "TROS", "TROSSEN", "UMBILICAL", "HAWSER", "LIJN", "LEINE")
# … but not the things that hold, guide, store or end one
_NOT_WORDS = flex._NOT_WORDS + ("ROLLER", "ROLLERS", "ROL", "ROLLE", "SHEAVE", "SHEAVES", "SCHIJF", "SEILROLLE",
                                "WHEEL", "WIEL", "RAD", "ENGINE", "COIL", "END", "CHUTE", "WINCH", "LIER", "WINDE",
                                "TENSIONER", "CAROUSEL", "BASKET", "HOOK", "THIMBLE", "SHACKLE", "CHAIN", "KETTING",
                                "KETTE", "HIGHWAY", "LADDER", "TRAY", "PROTECTOR", "ANCHOR", "ARCH", "QUADRANT",
                                "FRAME", "TOWER", "CRADLE", "STAND", "COVER", "BOX", "CUTTER", "GRIPPER", "LOCK")
_GROUPS = ("Cables",)


def candidates(scene) -> list:
    """The model parts that look like a cable or a wire rope (by their material group or their name) and are no
    cable and no hose yet."""
    taken = {ob.name for ob in cable_parts(scene)} | {ob.name for ob in flex.flex_parts(scene)}
    out = []
    for ob in build.iter_parts(scene):
        if ob.name in taken or ob.get(build.PROP_EXCLUDED):
            continue
        words = " " + " ".join(_part_name(ob).upper().replace(".", " ").replace("_", " ").replace("-", " ").split()) + " "
        if any(f" {w} " in words for w in _NOT_WORDS):
            continue
        group = str(ob.get(build.PROP_GROUP, "") or "")
        if any(group == g or group.startswith(g + " #") for g in _GROUPS) or any(f" {w} " in words for w in _WORDS):
            out.append(ob)
    return out


def _clash_hook(scene):
    """The clash check leaves the drawn cable out: it lies on its rollers and sheaves on purpose (and the check
    would test the stiff CAD shape)."""
    return [], cable_parts(scene)


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]:
    """The model was replaced by a new revision: every cable goes to the matching new parts (by their part IDs),
    its joints are found again (they came back through the joints' own rebuild), and the cable is read again from
    the new CAD shape – what the user set stays. Returns notes for the report."""
    s = scene.fresing
    if not len(s.cables):
        return []
    notes = []
    forget()

    def concerned(it) -> bool:                  # a cable of another model stays as it is
        uids = [it.part_uid, it.a_uid, it.b_uid] + [u for c in it.contacts for u in (c.part_uid, c.carrier_uid)]
        return any(u and (u in mapping or u in by_uid) for u in uids)

    names = [it.name for it in s.cables if concerned(it)]
    _STATE["busy"] += 1
    try:
        for name in names:
            it = find(scene, name)
            who = f"Cable '{label(it)}'"
            with _quiet(it):
                it.part = flex._new_object(scene, it.part_uid, by_uid, mapping)
                it.shapes = it.shapes if _alive(scene, it.shapes) else None
            if it.joint and joints.find(scene, it.joint) is None and it.made_joint:
                try:                            # (a joint that moves nothing is not carried over by itself)
                    _new_cable_joint(scene, it.name, it.joint)
                except (PathError, RuntimeError) as exc:
                    notes.append(f"{who}: its speed joint could not be made again ({exc})")
            it = find(scene, name)
            gone = []
            for k in reversed(range(len(it.contacts))):
                c = it.contacts[k]
                part = flex._new_object(scene, c.part_uid, by_uid, mapping) if c.part_uid else None
                if c.part_uid and part is None:
                    gone.append(c.name)
                    it.contacts.remove(k)
                    continue
                j = joints.find(scene, c.joint) if c.joint else None
                if c.carrier_uid:
                    carrier = flex._new_object(scene, c.carrier_uid, by_uid, mapping)
                elif j is not None and j.frame is not None:
                    carrier = j.frame
                else:
                    carrier = part              # its joint did not come back: on the part itself for now
                with _quiet(c):
                    c.part, c.carrier = part, carrier
                    if c.joint and j is None:
                        c.joint, c.made_joint, c.coupled = "", False, False
            for cname in reversed(gone):
                notes.append(f"{who}: '{cname}' is gone in the new revision: the cable no longer runs over it")
            for key in ("a", "b"):
                uid = getattr(it, key + "_uid")
                if uid:
                    ob = flex._new_object(scene, uid, by_uid, mapping)
                    with _quiet(it):
                        setattr(it, key + "_part", ob)
                    if ob is None and it.get(key + "_user"):
                        del it[key + "_user"]
            wheels = _wheels(it)
            for key, k in (("a", 0), ("b", -1)):                # an end on a joint's arrow: the wheel's new one
                if not getattr(it, key + "_uid") and wheels and _alive(scene, wheels[k].carrier):
                    with _quiet(it):
                        setattr(it, key + "_part", wheels[k].carrier)
            if it.part is None:
                notes.append(f"{who}: its part is gone in the new revision")
        for name in names:
            it = find(scene, name)
            if it.part is None:
                continue
            who = f"Cable '{label(it)}'"
            try:
                read_cad(scene, it, it.part)
            except PathError as exc:
                notes.append(f"{who}: {exc}")
                try:
                    it = find(scene, name)
                    _couple(scene, it)
                    it = find(scene, name)
                    it.part[PART] = True
                    _apply_look(scene, it)
                    _pay_driver(scene, it)
                    _rebuild(scene, it)
                except Exception as exc2:       # noqa: BLE001
                    notes.append(f"{who} could not be drawn again ({exc2 or type(exc2).__name__})")
            except Exception as exc:            # a model update never fails over a cable
                notes.append(f"{who} could not be carried over ({exc or type(exc).__name__}): use 'From CAD cable'")
    finally:
        _STATE["busy"] -= 1
    return notes


# ---------------------------------------------------------------------------
# handlers
# ---------------------------------------------------------------------------

def forget() -> None:
    """Drop what this module remembers between calls (undo, redo, file load, a changed list)."""
    _STATE["last"].clear()
    _STATE["arrays"].clear()
    _STATE["inputs"].clear()


def _follow(scene) -> None:
    if _STATE["busy"] or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        s = scene.fresing
        if not len(s.cables) or s.anim_baked:
            return                              # nothing to do, or the built animation's frames show
        if not any(it.moving and it.enabled for it in s.cables):
            return                              # every cable lies still on its rollers
    except (AttributeError, ReferenceError):
        return
    if not bpy.app.background and threading.current_thread() is not threading.main_thread():
        return                                  # a render in the window: the shapes were written before it began
    _STATE["busy"] += 1
    try:
        if _live(scene):
            flex._redraw_views()
    except Exception as exc:                    # never break the app's update loop
        print("Fresing Render: cable update failed:", exc)
    finally:
        _STATE["busy"] -= 1


@persistent
def _on_depsgraph(scene, _depsgraph=None):
    _follow(scene)


@persistent
def _on_frame(scene, _depsgraph=None):
    """Keys the user made by hand (no built animation): a moving cable follows at every frame."""
    from . import machining
    if machining._STATE["guard"]:               # something is only reading the motion (clash._Guard)
        return
    _follow(scene)


@persistent
def _on_load(_dummy=None):
    forget()


@persistent
def _on_undo(_scene=None, _dummy=None):
    forget()


def _handlers():
    h = bpy.app.handlers
    return ((h.depsgraph_update_post, _on_depsgraph), (h.frame_change_post, _on_frame), (h.load_post, _on_load),
            (h.undo_post, _on_undo), (h.redo_post, _on_undo))


def register() -> None:
    from . import clash
    for lst, fn in _handlers():
        if fn not in lst:
            lst.append(fn)
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)


def unregister() -> None:
    from . import clash
    for lst, fn in _handlers():
        while fn in lst:
            lst.remove(fn)
    while _clash_hook in clash.HOOKS:
        clash.HOOKS.remove(_clash_hook)
    forget()


# ---------------------------------------------------------------------------
# the test model (tests, the test tour, the PC check)
# ---------------------------------------------------------------------------

TEST_ANIMATION = "Cable over sheaves"


def set_up_test_model(scene) -> dict:
    """The set-up of the cable paths test model (test_paths_a.step, tools/make_test_paths.py), already imported:
    the rotate joint "Luff" on the A-frame (-15° … +15°, + leans it forward), the cable "Wire rope" read from
    the part WIRE ROPE (steel wire rope look), and the animation "Cable over sheaves" – the cable runs at
    10 m/min for 6 s while the A-frame luffs to +12° and back. Not built. Returns the names of what was made."""
    def named(name):
        for ob in scene.objects:
            if ob.get(build.PROP_NAME) == name:
                return ob
        raise PathError(f"The model has no part '{name}'.")

    frame = named("A-FRAME.ASM")
    root = build.model_root_of(frame) or frame
    m = root.matrix_world
    luff = joints.create(scene, "ROTATE", [frame], m @ Vector((1.5, 0.0, 0.73)),
                         (m.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized(), name="Luff")
    luff.rot_min, luff.rot_max = math.radians(-15.0), math.radians(15.0)
    luff.use_limits = True
    luff_name = luff.name
    bpy.context.view_layer.update()
    item = add_cable(scene, "Wire rope")
    name = item.name
    with _quiet(item):
        item.look = "ROPE"
    item["look_was"] = "ROPE"
    notes = read_cad(scene, item, named("WIRE ROPE"))
    item = find(scene, name)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = TEST_ANIMATION, 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", item.joint, 0.0, 6.0, "LINEAR"
    b.speed_mmin = 10.0
    for start, to in ((1.5, 12.0), (3.0, 0.0)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", luff_name, start, 1.5, "SMOOTH"
        b.use_from = True
        b.to_angle = math.radians(to)
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    return {"joints": [luff_name, item.joint], "cable": name, "animation": TEST_ANIMATION,
            "contacts": [c.name for c in item.contacts], "notes": notes}
