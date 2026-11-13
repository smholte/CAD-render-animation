"""Tracks and belts (task 0079): a chain of CAD links, pads and plates runs round its wheels.

A **track** (``scene.fresing.tracks``, 4 Motion > Tracks and belts) is a closed chain of separate CAD links – each
hinging on two pins one pitch apart – round two or more wheels (sprockets, idlers, support rollers), with parts that
ride on the links (pads, back plates). The owner clicks the wheels, one link and, if he likes, a pad and a plate; the
app finds their copies, reads the chain's pins from the links' round hinge faces and lays the loop round the wheels
(``core/tracks.py`` has the maths). Then:

* **Every link, pad and plate moves round the loop by itself, with no Python per frame.** Each gets a Geometry Nodes
  modifier "FR track" (tree "FR track part") that moves its own geometry: its first hinge goes to the loop's point at
  ``c = Phase + Travel`` (taken round the loop), its second hinge exactly one pitch further along the loop (the
  chord). The loop is a hidden mesh "FR track loop <name>" whose points are the loop sampled every 2 mm of chain, in
  the coordinates of the **carrier** (the first wheel's joint arrow): a track carried by joints (a tensioner's lift
  and tilt) moves with them and costs nothing more. ``Travel`` is a driver on the speed joint (a simple expression,
  no scripts): metres of chain, kept to 0 … loop length, + 2. So the parts' visibility, materials, paint schemes,
  fades, selection and hiding with their subassembly keep working (their objects stay where the CAD file has them).
* **The wheels turn with the chain** one tooth per pitch (``core.tracks.Loop.rate``): their own rotate joint when
  they have one on that axis (coupled to the speed joint if it moves by itself; a coupling of its own that is off by
  more than 0.5 % is reported and kept), else a joint the app makes (tagged ``fr_track``).
* **The speed** is a joint: by default the cable of 4 Motion > Cables and paths that runs nearest the track's runs,
  in the direction that moves the pads on that run with the cable; any slide joint (metres) or a rotate joint of one
  of the track's wheels. Without a cable the app makes a slide joint "Track <name>".

A track keeps its parts by part ID (model updates: ``after_model_update``) and is left out of the clash check (its
parts are moved by their modifiers, which the check does not see: ``_clash_hook``).
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import tracks as T
from ..core.words import plural
from . import build, flex, joints

TAG = "fr_track"                    # on a moving part, the loop object and an app-made wheel joint: the track's name
ROLE = "fr_track_role"              # on a moving part: "link" / "rider"; on the loop object: "loop"
MOD = "FR track"
TREE = "FR track part"
LOOP = "FR track loop"
VERSION = 1                         # of the node tree
BIAS = 2.0                          # Travel = metres of chain (0 … length) + BIAS: never a small number (CLAUDE.md 8)
RATIO_TOL = 0.005                   # a wheel's own coupling this far off is reported
NEAR_CABLE = 0.6                    # m: a cable this close to a run is the track's default speed
_INPUTS = (("Loop", "NodeSocketObject"), ("Carrier", "NodeSocketObject"), ("Length", "NodeSocketFloat"),
           ("Count", "NodeSocketInt"), ("Travel", "NodeSocketFloat"), ("Phase", "NodeSocketFloat"),
           ("Offset", "NodeSocketVector"), ("Turn", "NodeSocketVector"), ("Size", "NodeSocketFloat"))
_STATE = {"inputs": {}, "busy": 0}


class TrackError(RuntimeError):
    """A track cannot be made or changed: the message says why, in plain words."""


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def items(scene):
    return scene.fresing.tracks


def active(scene):
    s = scene.fresing
    return s.tracks[s.tracks_index] if 0 <= s.tracks_index < len(s.tracks) else None


def find(scene, name: str):
    for it in scene.fresing.tracks:
        if it.name == name:
            return it
    return None


def index_of(scene, item) -> int:
    for i, x in enumerate(scene.fresing.tracks):
        if x == item:
            return i
    return -1


def label(item) -> str:
    return item.name or "Track"


def _alive(scene, ob) -> bool:
    return flex._alive(scene, ob)


def _unique(scene, base: str) -> str:
    names = {x.name for x in scene.fresing.tracks}
    name, n = base, 2
    while name in names:
        name, n = f"{base} {n}", n + 1
    return name


def _name(ob) -> str:
    return str(ob.get(build.PROP_NAME, "") or ob.name) if ob is not None else ""


def key_of(item) -> str:
    """What the track's parts, loop and app-made joints are tagged with: fixed when it is made (a renamed track keeps
    its parts)."""
    return item.key or item.name


def _new_key(scene) -> str:
    keys = {key_of(x) for x in scene.fresing.tracks}
    n = 1
    while f"track {n}" in keys:
        n += 1
    return f"track {n}"


def parts_of(scene, item) -> list:
    """The CAD parts the track moves (links, pads, plates)."""
    return [ob for ob in scene.objects if ob.get(TAG) == key_of(item) and ob.get(ROLE) in ("link", "rider")]


def track_parts(scene) -> list:
    """Every part a track moves (any track)."""
    if not len(scene.fresing.tracks):
        return []
    return [ob for ob in scene.objects if ob.get(ROLE) in ("link", "rider") and ob.get(TAG)]


def wheel_parts(scene, item) -> list:
    return [w.part for w in item.wheels if _alive(scene, w.part)]


def loop_object(scene, item):
    ob = item.loop
    return ob if _alive(scene, ob) else None


def _mm(m: float) -> str:
    return f"{m * 1000.0:.0f}" if abs(m) >= 0.01 else f"{m * 1000.0:.1f}"


# ---------------------------------------------------------------------------
# reading parts
# ---------------------------------------------------------------------------

def _np(m) -> np.ndarray:
    return np.array(m, dtype=float)


def _at(m: np.ndarray, p) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    return p @ m[:3, :3].T + m[:3, 3]


def _axes(ob) -> np.ndarray:
    """The part's round-face axes (K, 7: point, unit direction, radius), in its own coordinates."""
    me = ob.data if ob is not None and ob.type == "MESH" else None
    if me is None or "fr_axes" not in me:
        return np.zeros((0, 7))
    a = np.array(me["fr_axes"], dtype=float).reshape(-1, 7)
    n = np.linalg.norm(a[:, 3:6], axis=1)
    a = a[n > 1e-9]
    a[:, 3:6] /= np.linalg.norm(a[:, 3:6], axis=1, keepdims=True)
    return a


def _centre(ob) -> np.ndarray:
    return np.array([tuple(c) for c in ob.bound_box], dtype=float).mean(axis=0)


def wheel_axis(ob):
    """(a point on the axis, direction, radius) of a wheel in its own coordinates: of its round faces, the axis
    that runs nearest its middle (a sprocket's bore and hub, not a tooth gap); radius = the largest round face on
    that axis (0 when none says). None when it has no round face."""
    a = _axes(ob)
    if not len(a):
        return None
    mid = _centre(ob)
    rel = mid - a[:, :3]
    off = np.linalg.norm(rel - a[:, 3:6] * np.einsum("ij,ij->i", rel, a[:, 3:6])[:, None], axis=1)
    k = int(np.argmin(off + 1e-6 * -a[:, 6]))
    d = a[k, 3:6]
    on = (off <= off[k] + 1e-4) & (np.abs(a[:, 3:6] @ d) > 0.9999)
    r = float(a[on, 6].max()) if on.any() else 0.0
    point = a[k, :3] + d * float((mid - a[k, :3]) @ d)       # level with the wheel's middle
    return point, d, r


def link_hinges(ob, normal=None):
    """A link's two hinge points in its own coordinates: on the two farthest-apart round axes parallel to each other
    (and to ``normal``, the wheels' axis in the link's coordinates, when given), level with the link's middle. None
    when it has no such pair."""
    a = _axes(ob)
    if len(a) < 2:
        return None
    if normal is not None:
        nrm = np.asarray(normal, dtype=float)
        nrm = nrm / np.linalg.norm(nrm)
        a = a[np.abs(a[:, 3:6] @ nrm) > math.cos(math.radians(2.0))]
        if len(a) < 2:
            return None
        d = nrm
    else:
        d = a[0, 3:6]
        a = a[np.abs(a[:, 3:6] @ d) > math.cos(math.radians(2.0))]
    mid = _centre(ob)
    pts = a[:, :3] + np.outer((mid - a[:, :3]) @ d, d)             # each axis level with the middle
    best, pair = 0.0, None
    for i in range(len(pts)):
        dist = np.linalg.norm(pts - pts[i], axis=1)
        j = int(np.argmax(dist))
        if dist[j] > best:
            best, pair = float(dist[j]), (i, j)
    if pair is None or best <= 1e-6:
        return None
    return pts[pair[0]], pts[pair[1]]


def copies(scene, ob, near=None) -> list:
    """The parts of the same kind as ``ob``: the parts of the same name in its subassembly (or one or two levels up
    when it holds fewer than 3), else of the same mesh. ``near`` (centre, reach): only those whose middle lies within
    reach of the centre (world)."""
    taken = {o.name for o in track_parts(scene)} | {o.name for o in flex.flex_parts(scene)}
    name = _name(ob)
    home = build.logical_parent(ob)
    out = []
    for _level in range(3):
        same = [o for o in build.iter_parts(scene) if o.name not in taken and not o.get(build.PROP_EXCLUDED)
                and (o == ob or (_name(o) == name and _under(o, home)))]
        if len(same) < 3:
            same = [o for o in build.iter_parts(scene) if o.name not in taken and (o == ob or (o.data == ob.data
                                                                                              and _under(o, home)))]
        out = same
        if len(out) >= 3 or home is None:
            break
        home = build.logical_parent(home)
    if near is not None:
        centre, reach = near
        memo: dict = {}
        out = [o for o in out if o == ob or np.linalg.norm(_at(flex._cad_world(o, memo), _centre(o)) - centre) <= reach]
    return out


def _under(ob, home) -> bool:
    if home is None:
        return True
    p = build.logical_parent(ob)
    while p is not None:
        if p == home:
            return True
        p = build.logical_parent(p)
    return False


def _read(scene, wheels: list, chain, riders) -> dict:
    """Everything the loop needs, in the CAD pose (world): wheels, the chain, every part's place."""
    memo: dict = {}
    if chain is None or chain.type != "MESH":
        raise TrackError("Click one link of the chain (a part with its two hinge pins or holes).")
    wl = []
    for ob, _hit in wheels:
        if ob == chain:
            raise TrackError(f"'{_name(ob)}' is the chain link: click it as the link, not as a wheel.")
        ax = wheel_axis(ob)
        if ax is None:
            raise TrackError(f"'{_name(ob)}' has no round face: click a sprocket, idler or roller of the track.")
        M = flex._cad_world(ob, memo)
        p, d, r = ax
        scale = float(np.cbrt(abs(np.linalg.det(M[:3, :3])))) or 1.0
        wl.append({"part": ob, "centre": _at(M, p), "axis": T._unit(M[:3, :3] @ d), "radius": r * scale})
    if len(wl) < 2:
        raise TrackError("A track runs round at least 2 wheels: click them round the loop.")
    if len({w["part"].name for w in wl}) < len(wl):
        raise TrackError("A wheel was clicked twice: click each wheel once.")
    n = wl[0]["axis"]
    centre = np.mean([w["centre"] for w in wl], axis=0)
    span = max(float(np.linalg.norm(w["centre"] - centre)) for w in wl)
    MC = flex._cad_world(chain, memo)
    loc_n = np.linalg.inv(MC[:3, :3]) @ n
    h = link_hinges(chain, loc_n)
    if h is None:
        raise TrackError(f"'{_name(chain)}' has no two hinge pins or holes parallel to the wheels' axes: click a "
                         "link of the chain (a part with a pin or hole at each end).")
    pitch = float(np.linalg.norm(MC[:3, :3] @ (h[1] - h[0])))
    reach = span + 4.0 * max(w["radius"] for w in wl) + 4.0 * pitch
    links = copies(scene, chain, (centre, reach))
    hinges, kept = [], []
    for o in links:
        M = flex._cad_world(o, memo)
        hh = link_hinges(o, np.linalg.inv(M[:3, :3]) @ n)
        if hh is None:
            continue
        hinges.append([_at(M, hh[0]), _at(M, hh[1])])
        kept.append(o)
    if not kept:
        raise TrackError(f"No links like '{_name(chain)}' were found.")
    try:
        sel = T.loop_of(hinges, next(i for i, o in enumerate(kept) if o == chain))
        kept = [kept[i] for i in sel]
        ch = T.chain_of([hinges[i] for i in sel])
        loop = T.fit(ch, [w["centre"] for w in wl], [w["axis"] for w in wl], [_name(w["part"]) for w in wl])
    except T.TrackError as exc:
        raise TrackError(str(exc)) from exc
    # each link's first hinge (along the loop) is pin i of its pair
    link_rows = []
    hz = np.asarray([hinges[i] for i in sel])
    for li, o in enumerate(kept):
        a, b = ch.link_pins[li]
        link_rows.append({"part": o, "pin": int(a)})
    c_pins, _d = loop.locate(ch.pins)
    del hz
    # riders: their copies, each on its nearest link
    rider_rows = []
    taken = {o.name for o in kept} | {w["part"].name for w in wl}
    link_mid = np.array([0.5 * (ch.pins[r["pin"]] + ch.pins[(r["pin"] + 1) % len(ch.pins)]) for r in link_rows])
    for rider in riders or ():
        if rider is None or rider.name in taken:
            continue
        group = [o for o in copies(scene, rider, (centre, reach)) if o.name not in taken]
        for o in group:
            m = _at(flex._cad_world(o, memo), _centre(o))
            k = int(np.argmin(np.linalg.norm(link_mid - m, axis=1)))
            rider_rows.append({"part": o, "pin": link_rows[k]["pin"]})
            taken.add(o.name)
    return {"wheels": wl, "chain": ch, "loop": loop, "links": link_rows, "riders": rider_rows, "c_pins": c_pins,
            "memo": memo, "n": loop.n}


# ---------------------------------------------------------------------------
# the node tree (shared by every track part)
# ---------------------------------------------------------------------------

def _build_tree(ng) -> None:
    b = flex._Nodes(ng)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")

    def math_(op, x, y=None):
        n = b.new("ShaderNodeMath", operation=op)
        b.link(x, n.inputs[0]) if not isinstance(x, (int, float)) else setattr(n.inputs[0], "default_value", x)
        if y is not None:
            b.link(y, n.inputs[1]) if not isinstance(y, (int, float)) else setattr(n.inputs[1], "default_value", y)
        return n.outputs[0]

    # c = floored_mod(Travel - BIAS + Phase, Length); f = c / Length * Count
    c = math_("FLOORED_MODULO", math_("ADD", math_("SUBTRACT", gin.outputs["Travel"], BIAS), gin.outputs["Phase"]),
              gin.outputs["Length"])
    f = math_("MULTIPLY", math_("DIVIDE", c, gin.outputs["Length"]), gin.outputs["Count"])
    fl = math_("FLOOR", f)
    t = math_("SUBTRACT", f, fl)
    i0f = b.new("FunctionNodeFloatToInt", rounding_mode="FLOOR")
    b.link(fl, i0f.inputs[0])
    i0 = b.new("FunctionNodeIntegerMath", operation="FLOORED_MODULO")
    b.link(i0f.outputs[0], i0.inputs[0])
    b.link(gin.outputs["Count"], i0.inputs[1])
    i1p = b.new("FunctionNodeIntegerMath", operation="ADD")
    b.link(i0.outputs[0], i1p.inputs[0])
    i1p.inputs[1].default_value = 1
    i1 = b.new("FunctionNodeIntegerMath", operation="FLOORED_MODULO")
    b.link(i1p.outputs[0], i1.inputs[0])
    b.link(gin.outputs["Count"], i1.inputs[1])
    loop = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Loop"], loop.inputs["Object"])
    geo = loop.outputs["Geometry"]

    def mixed(attribute: str):
        v0 = flex._sample(b, geo, i0.outputs[0], attribute)
        v1 = flex._sample(b, geo, i1.outputs[0], attribute)
        mix = b.new("ShaderNodeMix", data_type="VECTOR", clamp_factor=False)
        b.link(t, mix.inputs["Factor"])
        b.link(v0, flex._sock(mix.inputs, "A"))
        b.link(v1, flex._sock(mix.inputs, "B"))
        return flex._sock(mix.outputs, "Result")

    place = b.new("FunctionNodeCombineTransform")
    b.link(mixed(""), place.inputs["Translation"])
    b.link(flex._rotation(b, mixed("fr_x"), mixed("fr_z")), place.inputs["Rotation"])
    # Local: Offset, Turn (Euler), Size
    rot = b.new("FunctionNodeEulerToRotation")
    b.link(gin.outputs["Turn"], rot.inputs[0])
    local = b.new("FunctionNodeCombineTransform")
    b.link(gin.outputs["Offset"], local.inputs["Translation"])
    b.link(rot.outputs[0], local.inputs["Rotation"])
    size = b.new("ShaderNodeCombineXYZ")
    for k in range(3):
        b.link(gin.outputs["Size"], size.inputs[k])
    b.link(size.outputs[0], local.inputs["Scale"])
    carrier = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.link(gin.outputs["Carrier"], carrier.inputs["Object"])
    m1 = b.new("FunctionNodeMatrixMultiply")
    b.link(place.outputs[0], m1.inputs[0])
    b.link(local.outputs[0], m1.inputs[1])
    m2 = b.new("FunctionNodeMatrixMultiply")
    b.link(carrier.outputs["Transform"], m2.inputs[0])
    b.link(m1.outputs[0], m2.inputs[1])
    m3 = b.new("FunctionNodeMatrixMultiply")
    b.link(flex._to_own_space(b), m3.inputs[0])
    b.link(m2.outputs[0], m3.inputs[1])
    b.link(flex._move(b, gin.outputs["Geometry"], m3.outputs[0]), gout.inputs[0])


def _tree():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get(TAG) == VERSION:
        return ng
    if ng is not None:
        ng.name = TREE + " old"
    ng = bpy.data.node_groups.new(TREE, "GeometryNodeTree")
    ng[TAG] = VERSION
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    for label_, kind_ in _INPUTS:
        ng.interface.new_socket(label_, in_out="INPUT", socket_type=kind_)
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    _build_tree(ng)
    _STATE["inputs"].pop(TREE, None)
    return ng


def _inputs(ng) -> dict:
    out = _STATE["inputs"].get(ng.name)
    if out is None:
        out = {s.name: s.identifier for s in ng.interface.items_tree
               if getattr(s, "item_type", "SOCKET") == "SOCKET" and s.in_out == "INPUT"}
        _STATE["inputs"][ng.name] = out
    return out


def _drop_unused_tree() -> None:
    for name in (TREE, TREE + " old"):
        ng = bpy.data.node_groups.get(name)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)


# ---------------------------------------------------------------------------
# the loop object
# ---------------------------------------------------------------------------

def _loop_mesh(name: str, A: np.ndarray, X: np.ndarray, Z: np.ndarray):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(A))
    me.vertices.foreach_set("co", A.astype(np.float32).reshape(-1))
    for attr, vals in (("fr_x", X), ("fr_z", Z)):
        at = me.attributes.new(attr, "FLOAT_VECTOR", "POINT")
        at.data.foreach_set("vector", vals.astype(np.float32).reshape(-1))
    me[TAG] = True
    me.update()
    return me


def _set_loop(scene, item, A, X, Z):
    name = f"{LOOP} {label(item)}"
    me = _loop_mesh(name, A, X, Z)
    ob = loop_object(scene, item)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        ob[TAG] = key_of(item)
        ob[ROLE] = "loop"
        ob[build.PROP_KIND] = "track"
        flex._collection(scene).objects.link(ob)
        ob.hide_viewport = ob.hide_render = ob.hide_select = True
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    with flex._quiet(item):
        item.loop = ob
    return ob


def _remove_loop(scene, item) -> None:
    ob = item.loop
    if ob is not None:
        try:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        except ReferenceError:
            pass
    with flex._quiet(item):
        item.loop = None


# ---------------------------------------------------------------------------
# set-up: wheels' joints, the loop, every part's modifier
# ---------------------------------------------------------------------------

def _own_joint(scene, part, centre, axis, radius, memo):
    from . import paths
    return paths._own_joint(scene, part, centre, axis, max(radius, 0.01), memo, paths._joint_names(scene))


def _make_wheel_joints(scene, item, geo: dict) -> None:
    """Each wheel's rotate joint: its own on its axis, else a new one (inside a batch: one CAD pose)."""
    memo = geo["memo"]
    for k, w in enumerate(geo["wheels"]):
        row = item.wheels[k]
        own = _own_joint(scene, w["part"], w["centre"], w["axis"], w["radius"], memo)
        if own:
            j = joints.find(scene, own)
            mine = j is not None and j.motion is not None and j.motion.get(TAG) == key_of(item)
            with flex._quiet(row):
                row.joint, row.made_joint = own, mine           # (one it made before a model update is still its own)
                row.coupled = row.coupled or mine
            continue
        try:
            j = joints.create(scene, "ROTATE", [w["part"]], Vector(w["centre"]), Vector(w["axis"]))
        except RuntimeError as exc:
            with flex._quiet(row):
                row.note = f"it cannot turn: {exc}"
            continue
        j.motion[TAG] = key_of(item)
        with flex._quiet(row):
            row.joint, row.made_joint, row.coupled = j.name, True, True
        memo.clear()


def _axis_sign(scene, item, j) -> float:
    """+1 when joint ``j`` turns about the loop's normal, -1 about the other way (read in the carrier's coordinates,
    so in any pose)."""
    if j is None or j.frame is None or not _alive(scene, item.carrier):
        return 1.0
    rel = np.linalg.inv(_np(joints.world_of(scene, item.carrier))) @ _np(joints.world_of(scene, j.frame))
    return 1.0 if float(T._unit(rel[:3, 2]) @ np.array(item.normal)) >= 0.0 else -1.0


def _carrier(scene, item):
    """The first wheel's joint arrow (it moves with what carries the wheels, but does not turn)."""
    for w in item.wheels:
        j = joints.find(scene, w.joint) if w.joint else None
        if j is not None and j.frame is not None:
            return j.frame
    return None


def _check_carrier(scene, item) -> None:
    frames = [joints.find(scene, w.joint).frame for w in item.wheels
              if w.joint and joints.find(scene, w.joint) is not None]
    if len(frames) < 2:
        return
    ref = flex._movers(frames[0])
    for w, f in zip(item.wheels[1:], frames[1:]):
        if flex._movers(f) != ref:
            raise TrackError(f"'{w.name}' moves against '{item.wheels[0].name}' (another joint carries it): a track "
                             "whose wheels move against each other (a tension idler on a joint) is not done yet.")


def add(scene, wheels, chain, riders=(), joint: str = "", name: str = "", key: str = ""):
    """A new track. ``wheels``: the wheel parts round the loop (or (part, hit point) pairs), at least 2; ``chain``:
    one link; ``riders``: one pad, one plate … (their copies ride along). ``joint``: its speed ('' = the nearest
    cable's, else a new slide joint). Raises TrackError in plain words and leaves nothing behind then."""
    s = scene.fresing
    pairs = [(w if isinstance(w, tuple) else (w, None)) for w in wheels]
    if joint:
        j = joints.find(scene, joint)
        if j is None:
            raise TrackError(f"There is no joint called '{joint}'.")
    geo = _read(scene, pairs, chain, riders)
    key = key if key and key not in {key_of(x) for x in s.tracks} else _new_key(scene)
    item = s.tracks.add()
    with flex._quiet(item):
        item.key = key
        item.name = _unique(scene, name or _default_name(chain))
        item.chain_uid = str(chain.get(build.PROP_UID, ""))
        item.rider_uids = "\n".join(str(r.get(build.PROP_UID, "")) for r in riders or () if r is not None)
    s.tracks_index = len(s.tracks) - 1
    for w in geo["wheels"]:
        row = item.wheels.add()
        with flex._quiet(row):
            row.name = _name(w["part"])
            row.part = w["part"]
            row.part_uid = str(w["part"].get(build.PROP_UID, ""))
    try:
        notes = _setup(scene, item, geo, joint)
    except Exception:
        remove(scene, len(s.tracks) - 1)
        raise
    item = s.tracks[len(s.tracks) - 1]
    with flex._quiet(item):
        item.notes = "\n".join(notes)
    return item


def _default_name(chain) -> str:
    home = build.logical_parent(chain)
    base = _name(home) if home is not None and home.get(build.PROP_KIND) == "assembly" else "Track"
    return base.replace(".ASM", "").strip().title() or "Track"


def _setup(scene, item, geo: dict, joint: str = "") -> list[str]:
    """Wheels' joints, the speed, the loop, the parts' modifiers and drivers. Returns notes."""
    notes = []
    loop, ch = geo["loop"], geo["chain"]
    with joints._batch(scene):                        # one CAD pose: the wheels' joints, the carrier, the parts
        _make_wheel_joints(scene, item, geo)
        carrier = _carrier(scene, item)
        if carrier is None:
            raise TrackError("None of the wheels could get a joint to turn on, so the track has nothing to run on.")
        Cw = _np(joints.world_of(scene, carrier))
        data = _parts_data(scene, item, geo, Cw)
    item = find(scene, item.name)
    _check_carrier(scene, item)
    # wheels: radius, side, rate (rad about the loop's normal per metre of chain)
    for k, wf in enumerate(loop.wheels):
        row = item.wheels[wf.index]
        w = geo["wheels"][wf.index]
        rate = loop.rate(k, w["radius"])
        with flex._quiet(row):
            row.radius, row.side, row.wrapped, row.rate = float(wf.radius), int(wf.side), bool(wf.wrapped), rate
            row.wrap = float(wf.wrap)
    note = T.length_note(loop, len(geo["links"]))
    if note:
        notes.append(note)
    with flex._quiet(item):
        item.pitch = float(ch.pitch)
        item.links = len(geo["links"])
        item.parts = len(geo["links"]) + len(geo["riders"])
        item.length = float(loop.length)
        item.chain_length = float(len(geo["links"]) * ch.pitch)
        item.normal = tuple(float(v) for v in T._unit(np.linalg.inv(Cw)[:3, :3] @ loop.n))   # carrier coordinates
        item.carrier = carrier
        item.data = json.dumps(data["rows"])
    # the speed
    if not joint:
        joint, sign, why = _default_speed(scene, loop)
        if joint:
            notes.append(why)
        else:
            joint = _new_speed_joint(scene, item).name
            sign = 1.0
            with flex._quiet(item):
                item.made_joint = True
            notes.append(f"No cable runs through it: it got its own speed joint '{joint}' (metres of chain). Pick "
                         "a cable's joint as its speed in the panel, or give it a Run motor step")
        with flex._quiet(item):
            item.reverse = sign < 0.0
    with flex._quiet(item):
        item.joint = joint
    _set_loop(scene, item, data["A"], data["X"], data["Z"])
    _attach(scene, item, data)
    notes += couple(scene, item)
    _write_drivers(scene, item)
    return notes


def _parts_data(scene, item, geo: dict, Cw: np.ndarray) -> dict:
    """The loop table and every part's phase and local matrix, in the carrier's coordinates (CAD pose)."""
    loop = geo["loop"]
    Ci = np.linalg.inv(Cw)
    A, X, Z, m = loop.table()
    Ac = _at(Ci, A)
    R = Ci[:3, :3]
    Xc = X @ R.T
    Zc = Z @ R.T
    Xc /= np.linalg.norm(Xc, axis=1, keepdims=True)
    Zc /= np.linalg.norm(Zc, axis=1, keepdims=True)
    c_pins = geo["c_pins"]
    memo = {}
    rows = []
    frames = {}
    for kind, group in (("link", geo["links"]), ("rider", geo["riders"])):
        for r in group:
            ob = r["part"]
            c0 = float(c_pins[r["pin"]])
            F = frames.get(r["pin"])
            if F is None:
                Fw = loop.matrices([c0])[0]
                F = Ci @ Fw
                F[:3, :3] /= np.linalg.norm(F[:3, :3], axis=0, keepdims=True)
                frames[r["pin"]] = F
            local = np.linalg.inv(F) @ Ci @ flex._cad_world(ob, memo)
            rows.append({"name": ob.name, "uid": str(ob.get(build.PROP_UID, "")), "kind": kind, "c0": c0,
                         "local": [float(v) for v in local.reshape(-1)]})
    return {"A": Ac, "X": Xc, "Z": Zc, "M": m, "rows": rows}


def _local_inputs(local) -> tuple:
    L = Matrix([list(local[i * 4:(i + 1) * 4]) for i in range(4)])
    loc, rot, sc = L.decompose()
    return tuple(loc), tuple(rot.to_euler("XYZ")), float(sum(sc) / 3.0)


def _attach(scene, item, data: dict) -> None:
    """Each part gets its modifier "FR track" with its phase and local matrix."""
    tree = _tree()
    ins = _inputs(tree)
    loop = loop_object(scene, item)
    for r in data["rows"]:
        ob = bpy.data.objects.get(r["name"])
        if ob is None:
            continue
        ob[TAG] = key_of(item)
        ob[ROLE] = r["kind"]
        mod = ob.modifiers.get(MOD)
        if mod is None or mod.type != "NODES":
            mod = ob.modifiers.new(MOD, "NODES")
        if mod.node_group != tree:
            mod.node_group = tree
        off, turn, size = _local_inputs(r["local"])
        flex._put(mod, ins["Loop"], loop)
        flex._put(mod, ins["Carrier"], item.carrier)
        flex._put(mod, ins["Length"], float(item.length))
        flex._put(mod, ins["Count"], int(data["M"]))
        flex._put(mod, ins["Phase"], float(r["c0"]))
        flex._put(mod, ins["Size"], float(size))
        getattr(mod.properties.inputs, ins["Offset"]).value = off
        getattr(mod.properties.inputs, ins["Turn"]).value = turn
        getattr(mod.properties.inputs, ins["Travel"]).value = BIAS
        mod.show_viewport = mod.show_render = bool(item.enabled)


def _strip(ob) -> None:
    try:
        mod = ob.modifiers.get(MOD)
        if mod is not None:
            ad = ob.animation_data
            if ad is not None:
                for fc in list(ad.drivers):
                    if fc.data_path.startswith(f'modifiers["{MOD}"]'):
                        ad.drivers.remove(fc)
            ob.modifiers.remove(mod)
        for key in (TAG, ROLE):
            if key in ob:
                del ob[key]
    except ReferenceError:
        pass


# ---------------------------------------------------------------------------
# the speed: which joint, how many metres of chain per unit of it
# ---------------------------------------------------------------------------

def _new_speed_joint(scene, item):
    roots = build.model_roots(scene)
    if not roots:
        raise TrackError("There is no model yet: import one first (1 Import).")
    base = roots[0]
    jname = joints.unique_name(scene, f"Track {label(item)}")
    with joints._batch(scene):
        w = joints.world_of(scene, base)
        j = joints.create(scene, "SLIDE", [], w.translation.copy(),
                          (w.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized(), name=jname, base=base,
                          allow_empty=True)
        j.motion[TAG] = key_of(item)
        jname = j.name
    j = joints.find(scene, jname)
    if j.use_limits:
        j.use_limits = False
    joints.apply_limits(j, joints._model_size(scene))
    return j


def _default_speed(scene, loop) -> tuple:
    """(the joint of the cable that runs nearest one of the loop's runs, the direction sign, a note) or ('', 1, '')."""
    from . import paths
    best = None
    runs = loop.runs()
    if not runs:
        return "", 1.0, ""
    for it in paths.items(scene):
        if not it.enabled or not it.joint or joints.find(scene, it.joint) is None:
            continue
        try:
            pts = paths.shape_now(scene, it)
        except Exception:                                  # noqa: BLE001 - a cable that cannot be read is no candidate
            continue
        if len(pts) < 2:
            continue
        pts = _dense(np.asarray(pts, dtype=float), 0.02)
        for a, b, c_start in runs:
            seg = b - a
            L2 = float(seg @ seg)
            if L2 <= 0.0:
                continue
            t = np.clip(((pts - a) @ seg) / L2, 0.0, 1.0)
            d = np.linalg.norm(pts - (a + np.outer(t, seg)), axis=1)
            k = int(np.argmin(d))
            if d[k] > NEAR_CABLE or not (0.0 < t[k] < 1.0):
                continue
            if best is None or d[k] < best[0]:
                k2 = min(k + 1, len(pts) - 1)
                k1 = max(k2 - 1, 0)
                cdir = T._unit(pts[k2] - pts[k1]) * (-1.0 if it.reverse else 1.0)
                sign = 1.0 if float(cdir @ T._unit(seg)) >= 0.0 else -1.0
                best = (float(d[k]), it, sign)
    if best is None:
        return "", 1.0, ""
    _d, it, sign = best
    return it.joint, sign, f"Its speed: cable '{paths.label(it)}' (joint '{it.joint}'), the pads on the run it " \
        "passes move with it"


def _dense(pts: np.ndarray, step: float) -> np.ndarray:
    """A polyline with extra points so that no piece is longer than ``step`` (same shape, same order)."""
    out = [pts[:1]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.ceil(float(np.linalg.norm(b - a)) / step)))
        t = (np.arange(1, n + 1) / n)[:, None]
        out.append(a + t * (b - a))
    return np.concatenate(out)


def speed_map(scene, item):
    """(top joint, K, C): metres of chain the track has run = K x top's value + C (None when it has no usable
    speed joint), and a reason when not."""
    j = joints.find(scene, item.joint) if item.joint else None
    if j is None or j.motion is None:
        return None, 1.0, 0.0, f"its speed joint '{item.joint}' is gone" if item.joint else "it has no speed joint"
    top, k, c = joints.chain_affine(scene, j)
    if top is None or top.motion is None:
        return None, 1.0, 0.0, f"'{j.name}' follows another joint by a table: pick a joint with a plain speed"
    if j.kind == "SLIDE":
        g = -1.0 if item.reverse else 1.0
    else:                              # a wheel's own turn: the chain runs the way that wheel turns (no reverse)
        w = next((w for w in item.wheels if w.joint == j.name), None)
        if w is None or w.rate == 0.0:
            return None, 1.0, 0.0, f"'{j.name}' turns none of its wheels: pick a slide joint or a wheel's joint"
        g = _axis_sign(scene, item, j) / float(w.rate)
    return top, g * k, g * c, ""


def wheel_ratio(scene, item, w) -> float:
    """The ratio (as typed in the joints panel) a wheel's joint follows the track's speed joint with: ° per mm for
    a slide speed joint, turns per turn for a rotate one. 0.0 when it cannot."""
    j = joints.find(scene, w.joint) if w.joint else None
    lead = joints.find(scene, item.joint) if item.joint else None
    if j is None or lead is None or j.frame is None or w.rate == 0.0:
        return 0.0
    s_w = _axis_sign(scene, item, j)
    if lead.kind == "SLIDE":
        sign = -1.0 if item.reverse else 1.0
        return math.degrees(sign * w.rate * s_w) / 1000.0
    lw = next((x for x in item.wheels if x.joint == lead.name), None)
    if lw is None or lw.rate == 0.0:
        return 0.0
    return (w.rate * s_w) / (lw.rate * _axis_sign(scene, item, lead))


def couple(scene, item) -> list[str]:
    """The wheels' joints follow the speed joint at their ratios (the ones the app made or coupled; a wheel joint that
    moves by itself is coupled; one that follows the speed joint at another ratio is reported and kept)."""
    notes = []
    lead = joints.find(scene, item.joint) if item.joint else None
    todo = []
    for w in item.wheels:
        j = joints.find(scene, w.joint) if w.joint else None
        if j is None:
            continue
        if lead is not None and j.name == lead.name:      # this wheel drives the track now: it moves by itself
            if j.follows and (w.coupled or w.made_joint):
                todo.append((j.name, "", None))
            continue
        ratio = wheel_ratio(scene, item, w)
        with flex._quiet(w):
            w.ratio = ratio
        want = bool(item.enabled and lead is not None and ratio != 0.0)
        if not want:
            if (w.coupled or w.made_joint) and j.follows == item.joint:
                todo.append((j.name, "", None))
            continue
        if j.follows == item.joint and not j.couple_table:
            if abs(j.couple_ratio - ratio) <= RATIO_TOL * abs(ratio):
                continue
            if not (w.coupled or w.made_joint):
                text = (f"'{w.name}' follows '{item.joint}' at {j.couple_ratio:.5g} by its own coupling, the chain "
                        f"needs {ratio:.5g}: kept (its teeth will drift through the links)")
                with flex._quiet(w):
                    w.note = text
                notes.append(text)
                continue
            todo.append((j.name, item.joint, ratio))
        elif j.follows and not (w.coupled or w.made_joint):
            text = f"'{w.name}' follows '{j.follows}' by its own coupling: kept"
            with flex._quiet(w):
                w.note = text
            notes.append(text)
        else:
            todo.append((j.name, item.joint, ratio))
            with flex._quiet(w):
                w.coupled = True
    for name, follows, ratio in todo:
        j = joints.find(scene, name)
        try:
            if follows:
                joints.set_follows(scene, j, follows, ratio=ratio, offset_value=0.0)
            else:
                joints.set_follows(scene, j, "")
        except RuntimeError as exc:
            notes.append(f"'{name}' cannot follow '{follows}': {exc}")
    return notes


def _write_drivers(scene, item) -> None:
    """Every part's Travel: the driver on the speed joint (or the plain bias when the track has no speed)."""
    top, k, c, why = speed_map(scene, item)
    with flex._quiet(item):
        item.problem = why if item.enabled else ""
    tree = _tree()
    ins = _inputs(tree)
    path = f'modifiers["{MOD}"].properties.inputs.{ins["Travel"]}.value'
    expr = T.drive_expression(k, c, float(item.length), BIAS) if top is not None else ""
    for ob in parts_of(scene, item):
        mod = ob.modifiers.get(MOD)
        if mod is None:
            continue
        ad = ob.animation_data
        fc = ad.drivers.find(path) if ad is not None else None
        if top is None:
            if fc is not None:
                ob.driver_remove(path)
            getattr(mod.properties.inputs, ins["Travel"]).value = BIAS
            continue
        if fc is not None and fc.driver.expression == expr and len(fc.driver.variables) == 1 and \
                fc.driver.variables[0].targets[0].id == top.motion:
            continue
        if fc is not None:
            ob.driver_remove(path)
        joints._scripted(ob.driver_add(path), top.motion, expr)
        ob.update_tag()


# ---------------------------------------------------------------------------
# changes, removal
# ---------------------------------------------------------------------------

def changed(scene, item) -> None:
    """A setting of the track changed (on/off, speed joint, direction)."""
    if _STATE["busy"]:
        return
    _STATE["busy"] += 1
    try:
        for ob in parts_of(scene, item):
            mod = ob.modifiers.get(MOD)
            if mod is not None and (mod.show_viewport != bool(item.enabled) or mod.show_render != bool(item.enabled)):
                mod.show_viewport = mod.show_render = bool(item.enabled)
        couple(scene, item)
        _write_drivers(scene, item)
    finally:
        _STATE["busy"] -= 1


def remove(scene, index: int) -> None:
    """Take a track off the list: its parts show as in the CAD file, the joints the app made go."""
    s = scene.fresing
    if not 0 <= index < len(s.tracks):
        return
    item = s.tracks[index]
    for ob in parts_of(scene, item):
        _strip(ob)
    _remove_loop(scene, item)
    made = [w.joint for w in item.wheels if w.made_joint and w.joint]
    coupled = [w.joint for w in item.wheels if w.coupled and not w.made_joint and w.joint]
    if item.made_joint and item.joint:
        made.append(item.joint)
    item = s.tracks[index]
    for jn in coupled:
        j = joints.find(scene, jn)
        if j is not None and j.follows:
            try:
                joints.set_follows(scene, j, "")
            except RuntimeError:
                pass
    from . import paths
    paths._remove_joints(scene, [n for n in made if joints.find(scene, n) is not None])
    s.tracks.remove(index)
    s.tracks_index = max(0, min(s.tracks_index, len(s.tracks) - 1))
    if not len(s.tracks):
        _drop_unused_tree()


# ---------------------------------------------------------------------------
# what it shows now (tests, the panel, the PC check)
# ---------------------------------------------------------------------------

def travel_now(scene, item) -> float:
    """Metres of chain the track has run, as the drivers have it now (0 … length)."""
    top, k, c, _why = speed_map(scene, item)
    if top is None or item.length <= 0.0:
        return 0.0
    u = k * joints.get_value(top) + c
    return u - item.length * math.floor(u / item.length)


def _row(item, ob_name: str):
    for r in _rows_of_data(item):
        if r["name"] == ob_name:
            return r
    return None


def _rows_of_data(item) -> list:
    try:
        return json.loads(item.data or "[]")
    except ValueError:
        return []


def table_of(scene, item):
    """(A, X, Z) of the loop table in the carrier's coordinates, as stored."""
    ob = loop_object(scene, item)
    me = ob.data
    n = len(me.vertices)
    A = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", A)
    out = [A.reshape(-1, 3).astype(float)]
    for attr in ("fr_x", "fr_z"):
        v = np.empty(n * 3, np.float32)
        me.attributes[attr].data.foreach_get("vector", v)
        out.append(v.reshape(-1, 3).astype(float))
    return tuple(out)


def frame_at(scene, item, c: float) -> np.ndarray:
    """The 4 x 4 frame (carrier coordinates) the node tree gives a link whose first hinge is at chain parameter c."""
    A, X, Z = table_of(scene, item)
    m = len(A)
    f = (c % item.length) / item.length * m
    i0 = int(math.floor(f)) % m
    i1 = (i0 + 1) % m
    t = f - math.floor(f)
    a = A[i0] * (1 - t) + A[i1] * t
    x = T._unit(X[i0] * (1 - t) + X[i1] * t)
    z = Z[i0] * (1 - t) + Z[i1] * t
    y = T._unit(np.cross(z, x))
    z = np.cross(x, y)
    F = np.eye(4)
    F[:3, 0], F[:3, 1], F[:3, 2], F[:3, 3] = x, y, z, a
    return F


def matrix_now(scene, item, ob) -> np.ndarray:
    """Where the modifier draws part ``ob`` now (world, 4 x 4) – the same sum the node tree does, in Python."""
    r = _row(item, ob.name)
    if r is None:
        return _np(ob.matrix_world)
    c = r["c0"] + travel_now(scene, item)
    local = np.array(r["local"]).reshape(4, 4)
    return _np(item.carrier.matrix_world) @ frame_at(scene, item, c) @ local


def hinge_world(scene, item, ob) -> tuple:
    """A link's two hinge points now (world), from the evaluated mesh: the CAD hinges moved by the modifier."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        n = len(me.vertices)
        co = np.empty(n * 3, np.float32)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3).astype(float)
    finally:
        ev.to_mesh_clear()
    h = link_hinges(ob, None)
    # the modifier moves the geometry rigidly: fit that move from the original points to the evaluated ones
    verts, _tris = flex._mesh_arrays(ob.data)
    R, t = _rigid(verts, co)
    W = _np(ob.matrix_world)
    return _at(W, h[0] @ R.T + t), _at(W, h[1] @ R.T + t)


def _rigid(a: np.ndarray, b: np.ndarray):
    """The rigid move (R, t) with b ≈ a R^T + t (Kabsch)."""
    ca, cb = a.mean(axis=0), b.mean(axis=0)
    H = (a - ca).T @ (b - cb)
    U, _S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    return R, cb - ca @ R.T


def status(scene, item) -> tuple[str, str]:
    """(a few words, "OK" | "WARN" | "ERROR" | "OFF")."""
    if not item.enabled:
        return "Off: as in the CAD file", "OFF"
    if item.problem:
        return item.problem, "ERROR"
    if loop_object(scene, item) is None or not _alive(scene, item.carrier):
        return "Its loop is gone: remove it and add it again", "ERROR"
    if any(w.note for w in item.wheels):
        return f"{plural(item.parts, 'part')} on {item.joint}; see the notes", "WARN"
    return f"{plural(item.parts, 'part')} run on '{item.joint}'", "OK"


def summary(scene, item) -> str:
    return (f"{label(item)}: {plural(item.links, 'link')} of {_mm(item.pitch)} mm, {plural(item.parts, 'part')} "
            f"moving, {plural(len(item.wheels), 'wheel')}, loop {item.length:.3f} m, speed '{item.joint}'")


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]:
    """The model was replaced: every track is set up again on the new parts (found by part ID), keeping its name,
    speed joint, direction and on/off."""
    s = scene.fresing
    if not len(s.tracks):
        return []
    notes = []
    keep = []
    for it in s.tracks:
        keep.append({"name": it.name, "key": key_of(it), "joint": it.joint, "reverse": bool(it.reverse), "enabled": bool(it.enabled),
                     "made_joint": bool(it.made_joint),
                     "wheels": [w.part_uid for w in it.wheels], "chain": it.chain_uid,
                     "coupled": [w.part_uid for w in it.wheels if w.coupled],
                     "riders": [u for u in it.rider_uids.split("\n") if u]})
    while len(s.tracks):
        it = s.tracks[0]
        for ob in parts_of(scene, it):
            _strip(ob)
        _remove_loop(scene, it)
        s.tracks.remove(0)
    for k in keep:
        def ob_of(uid):
            return flex._new_object(scene, uid, by_uid, mapping) if uid else None
        wheels = [ob_of(u) for u in k["wheels"]]
        chain = ob_of(k["chain"])
        riders = [ob_of(u) for u in k["riders"]]
        if chain is None or any(w is None for w in wheels):
            notes.append(f"Track '{k['name']}': its link or a wheel is gone in the new revision; add it again")
            continue
        joint = k["joint"] if joints.find(scene, k["joint"]) is not None else ""
        try:
            it = add(scene, wheels, chain, [r for r in riders if r is not None], joint=joint, name=k["name"],
                     key=k["key"])
        except TrackError as exc:
            notes.append(f"Track '{k['name']}': {exc}")
            continue
        with flex._quiet(it):
            it.reverse = k["reverse"]
            it.enabled = k["enabled"]
            it.made_joint = it.made_joint or (k["made_joint"] and joint == k["joint"])
        for w in it.wheels:
            if w.part_uid in k["coupled"]:
                with flex._quiet(w):
                    w.coupled = True
        changed(scene, it)
    return notes


# ---------------------------------------------------------------------------
# handlers, clash hook
# ---------------------------------------------------------------------------

def _clash_hook(scene):
    """The clash check leaves the track parts out: their modifiers move them round the loop (the check reads the
    objects' places, which stand still), and the links hinge on each other and on the sprockets' teeth."""
    return [], track_parts(scene)


def forget() -> None:
    _STATE["inputs"].clear()


@persistent
def _on_load(_dummy=None):
    forget()


def _handlers():
    h = bpy.app.handlers
    return ((h.load_post, _on_load), (h.undo_post, _on_load), (h.redo_post, _on_load))


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

TEST_ANIMATION = "Tracks"
TEST_TRACKS = ("Bottom track", "Top track", "Belt")
TEST_CABLE = "Cable"
TEST_LIFT = "Top track lift"


def set_up_test_model(scene) -> dict:
    """The set-up of the tracks test model (test_tracks.step, tools/make_test_tracks.py), already imported: the
    joint "Top track lift" (+Z, the top carriage), the cable "Cable" read from the CAD (its joint is the tracks'
    speed), the tracks "Bottom track" and "Top track" (two sprockets, two support rollers, the links, the pads) and
    "Belt" (three pulleys, its links; its own speed joint); the animation "Tracks" (8 s: 2 m of cable, 1 m of belt,
    the top track lifts 150 mm and comes back to squeeze the cable 2 mm). Not built. Returns the names."""
    from mathutils import Vector

    from . import paths

    def uid(u):
        for ob in scene.objects:
            if ob.get(build.PROP_UID) == u:
                return ob
        raise TrackError(f"The model has no part '{u}'.")

    base = "TEST.TRACKS#1/"
    carriage = uid(base + "TOP CARRIAGE.ASM#1")
    root = uid("TEST.TRACKS#1")
    m = root.matrix_world
    with joints._batch(scene):
        joints.create(scene, "SLIDE", [carriage], m @ Vector((0.0, 0.0, 1.2)),
                      (m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized(), name=TEST_LIFT)
    lift = joints.find(scene, TEST_LIFT)
    lift.slide_min, lift.slide_max, lift.use_limits = -0.005, 0.3, True
    bpy.context.view_layer.update()
    out = {"joints": [TEST_LIFT], "notes": []}
    cab = paths.add_cable(scene, TEST_CABLE)
    out["notes"] += paths.read_cad(scene, cab, uid(base + "CABLE#1"))
    cable_joint = paths.find(scene, TEST_CABLE).joint
    out["joints"].append(cable_joint)
    for name, asm in (("Bottom track", "BOTTOM TRACK.ASM#1/"), ("Top track", "TOP CARRIAGE.ASM#1/TOP TRACK.ASM#1/")):
        p = base + asm
        wheels = [uid(p + "DRIVE SPROCKET#1"), uid(p + "SUPPORT ROLLER#1"), uid(p + "SUPPORT ROLLER#2"),
                  uid(p + "IDLER SPROCKET#1")]
        it = add(scene, wheels, uid(p + "TRACK CHAIN LINK#2"), [uid(p + "TRACK PAD#2")], name=name)
        out["notes"] += [n for n in it.notes.split("\n") if n]
    p = base + "BELT DRIVE.ASM#1/"
    belt = add(scene, [uid(p + f"BELT PULLEY {k}#1") for k in "ABC"], uid(p + "BELT LINK#1"), name="Belt")
    out["joints"].append(belt.joint)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = TEST_ANIMATION, 0.0, "25"
    for jn, start, secs, to in ((cable_joint, 0.0, 8.0, 2.0), (belt.joint, 0.0, 8.0, 1.0), (TEST_LIFT, 1.0, 2.0, 0.15),
                                (TEST_LIFT, 4.0, 2.0, -0.002)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", jn, start, secs, "LINEAR"
        b.use_from = jn != TEST_LIFT
        b.to_dist = to
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    out.update(tracks=list(TEST_TRACKS), cable=TEST_CABLE, animation=TEST_ANIMATION)
    return out


def off_loop(scene, item, points) -> np.ndarray:
    """How far each world point is from the track's loop as drawn now (the table's polyline, carried by the
    carrier): for tests, the tour and the PC check."""
    A, _X, _Z = table_of(scene, item)
    C = _np(item.carrier.matrix_world)
    a = A @ C[:3, :3].T + C[:3, 3]
    seg = np.roll(a, -1, axis=0) - a
    g = np.maximum((seg * seg).sum(axis=1), 1e-18)
    out = []
    for p in np.atleast_2d(np.asarray(points, dtype=float)):
        t = np.clip(((p - a) * seg).sum(axis=1) / g, 0.0, 1.0)
        out.append(float(np.linalg.norm(a + seg * t[:, None] - p, axis=1).min()))
    return np.array(out)
