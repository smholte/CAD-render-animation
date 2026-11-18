"""Set up a crane (task 0203, Lifting lane L4b): the owner's own crane STEP made a lifting-plan crane, step by step in
the Set-up window (``ui_setup.py``), for four kinds – mobile telescopic, crawler, knuckle-boom and "other".

* **Nothing is copied** (the Set-up window's rule): every joint is made with the app's joints (``joints.create``,
  ``joints.set_follows``), cylinders with ``cylinders.create``, tracks with ``tracks.add``, the rope with the cable
  functions, poses with 4 Motion > Poses. A step draws the joint's own settings (its limits, Flip); what is done here
  shows in 4 Motion and the other way round.
* **Roles.** Each joint gets its role (``FRJoint.role``: slew, luff, telescope, jib, knuckle, extension, hoist, swing,
  outrigger, jack, track, travel); the lifting plan finds the crane's joints by it. A role knows its sense (luff + =
  up, telescope + = out, hoist + = down …): a joint made the wrong way round is turned at once.
* **Parts by name or by a click.** A step's parts are typed (the search box lists the model's parts and sub-assemblies
  whose names hold the text) or clicked in the main window (Use clicked). The axis of a joint comes from the picked
  parts' round faces (holes, pins, slewing rings – the CAD's own axes, ``fr_axes``), from a direction (along the part,
  straight down …) or from a click on the model (the hover picker of 4 Motion, ``fresing.joint_pick_axis``).
* Everything else the steps need (masses, CoG, the load chart, the hook point, spreads) is kept in
  ``scene.fresing.crane_setup`` (``FRCraneSetup``); Save writes the equipment file (``lifting_rig_out.py``).

The step lists: ``SETUPS`` (merged into ``ui_setup.SETUPS``), the green ticks: ``CHECKS``.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Vector

from ..core.words import plural
from . import build, joints, logic, ui

SEP = " | "                  # between names in a parts field
KIND_OF = {"CRANE_MOBILE": "mobile_crane", "CRANE_CRAWLER": "crawler_crane", "CRANE_KNUCKLE": "knuckle_boom_crane",
           "CRANE_OTHER": "other_crane"}
ROTATE_ROLES = ("slew", "luff", "jib", "knuckle", "swing", "track")
SLIDE_ROLES = ("telescope", "extension", "hoist", "outrigger", "jack", "travel")
ROLE_WORDS = {
    "slew": "Slew", "luff": "Luff", "telescope": "Telescope", "jib": "Jib", "knuckle": "Knuckle",
    "extension": "Extension", "hoist": "Hoist", "swing": "Hook swing", "outrigger": "Outrigger", "jack": "Jack",
    "track": "Track", "travel": "Travel",
}
SENSE = {
    "slew": "+ turns it anticlockwise seen from above", "luff": "+ raises the boom", "jib": "+ raises the jib",
    "knuckle": "+ raises the outer boom", "telescope": "+ slides the sections out", "extension": "+ slides out",
    "hoist": "+ lets the hook down", "outrigger": "+ slides the beams out", "jack": "+ lowers the jacks",
    "travel": "+ drives forward", "swing": "follows the boom: the hook hangs plumb", "track": "",
}
# the mass groups per kind: (key, title) – the keys the built-in files use
GROUPS = {
    "mobile_crane": [("carrier", "Carrier"), ("superstructure", "Superstructure"), ("counterweight", "Counterweight"),
                     ("boom", "Boom"), ("jib", "Fly jib"), ("hook_block", "Hook block")],
    "crawler_crane": [("lower", "Lower works"), ("upper", "Upper works"), ("counterweight", "Counterweight"),
                      ("boom", "Boom"), ("jib", "Luffing jib"), ("hook_block", "Hook block")],
    "knuckle_boom_crane": [("truck", "Truck"), ("column", "Column"), ("main_boom", "Main boom"),
                           ("outer_boom", "Outer boom"), ("hook_block", "Hook block")],
    "other_crane": [("base", "Base"), ("upper", "Upper part"), ("counterweight", "Counterweight"), ("boom", "Boom"),
                    ("jib", "Jib"), ("hook_block", "Hook block")],
}
# which joint's role moves a group (its "moves_with")
GROUP_ROLE = {"carrier": None, "truck": None, "base": None, "lower": "travel", "superstructure": "slew",
              "upper": "slew", "column": "slew", "counterweight": "slew", "boom": "luff", "main_boom": "luff",
              "jib": "jib", "outer_boom": "knuckle", "hook_block": "hoist"}


def settings(scene):
    return scene.fresing.crane_setup


def kind_of(scene) -> str:
    """The equipment kind of the Set-up window's crane set-up ('' when it shows another set-up)."""
    return KIND_OF.get(scene.fresing.setup_kind, "")


def changed(scene) -> None:
    """A setting of the set-up changed: the Check has to run again."""
    if scene is None:
        return
    cs = settings(scene)
    if cs.checked:
        cs.checked = False


# ---------------------------------------------------------------------------------------------------------------------
# the model and its parts by name

def model_root(scene):
    """The crane's model: the one picked in the Model step, else the project's only model."""
    cs = settings(scene)
    if cs.root is not None and cs.root.name in bpy.data.objects:
        return cs.root
    roots = build.model_roots(scene)
    return roots[0] if len(roots) == 1 else None


def name_of(ob) -> str:
    return str(ob.get(build.PROP_NAME, ob.name))


_LOOKUP: dict = {}


def lookup(root) -> dict:
    """CAD name -> [objects] below the model's root (the root too); cached on the number of objects."""
    if root is None:
        return {}
    key = (root.name, len(bpy.data.objects))
    hit = _LOOKUP.get("key")
    if hit == key:
        return _LOOKUP["map"]
    by: dict = {}
    for ob in [root] + list(logic.descendants(root)):
        by.setdefault(name_of(ob), []).append(ob)
        inst = str(ob.get(build.PROP_INSTANCE, "") or "")
        if inst and inst != name_of(ob):
            by.setdefault(inst, []).append(ob)
    _LOOKUP.update(key=key, map=by)
    return by


def forget() -> None:
    _LOOKUP.clear()


def split_names(text: str) -> list:
    return [n.strip() for n in (text or "").split("|") if n.strip()]


def objects_of(scene, text: str, many_ok: bool = False) -> tuple[list, list]:
    """(objects, problems) for names separated by |. A name that fits several parts is a problem (say which) – but
    for a track's link and shoe (``many_ok``) the first copy stands for them all."""
    by = lookup(model_root(scene))
    objs, bad = [], []
    for n in split_names(text):
        hits = by.get(n, [])
        if len(hits) == 1 or (many_ok and hits):
            objs.append(hits[0])
        elif not hits:
            bad.append(f"'{n}' is not in the model")
        else:
            bad.append(f"'{n}' is the name of {len(hits)} parts: pick the sub-assembly above them")
    return objs, bad


def matches(scene, text: str, limit: int = 12) -> list:
    """Names of sub-assemblies and parts holding ``text`` (no case), sub-assemblies first."""
    t = (text or "").strip().lower()
    if not t:
        return []
    by = lookup(model_root(scene))
    out = []
    for name, objs in by.items():
        if t in name.lower() and len(objs) == 1 and objs[0].get(build.PROP_KIND) in ("assembly", "part"):
            out.append((0 if objs[0].get(build.PROP_KIND) == "assembly" else 1, name))
    out.sort()
    return [n for _k, n in out[:limit]]


def clicked(context) -> list:
    """The parts or sub-assemblies clicked in the main window (its selection), each once, outermost first."""
    try:
        sel = [o for o in context.view_layer.objects if o.select_get()]
    except (AttributeError, RuntimeError):
        return []
    root = model_root(context.scene)
    inside = set(lookup(root).get(name_of(o), [None])[0] for o in sel) if root else set()
    return [o for o in sel if o in inside and o is not root]


def parts_of(objs) -> list:
    """The mesh parts of objects (sub-assemblies: every part below them)."""
    out = []
    for ob in objs:
        if ob.type == "MESH":
            out.append(ob)
        out += [d for d in logic.descendants(ob) if d.type == "MESH"]
    return out


# ---------------------------------------------------------------------------------------------------------------------
# the crane's joints

def in_model(scene, j, root=None) -> bool:
    root = root or model_root(scene)
    if root is None:
        return False
    inside = set(lookup(root).get(name_of(m), [None])[0] for m in joints.members(j))
    if any(m in inside for m in joints.members(j)):
        return True
    below = joints.rides_on(scene, j)
    return below is not None and in_model(scene, below, root)


def app_made(j) -> bool:
    """A joint the cable or track functions made (a sheave the rope turns, the rope's paid-out length, a track's
    wheels): not the crane's own – Place makes them again from the rope and the tracks."""
    m = j.motion
    if m is not None and bool(m.get("fr_cable")):
        return True
    scene = bpy.context.scene
    return any(w.made_joint and w.joint == j.name for t in scene.fresing.tracks for w in t.wheels)


def crane_joints(scene) -> list:
    root = model_root(scene)
    return [j for j in scene.fresing.joints if not app_made(j) and in_model(scene, j, root)]


def with_role(scene, role: str, driven_only: bool = False) -> list:
    return [j for j in crane_joints(scene) if j.role == role and not (driven_only and j.follows)]


def first(scene, role: str):
    got = with_role(scene, role, driven_only=True) or with_role(scene, role)
    return got[0] if got else None


def joint_text(j) -> str:
    names = ", ".join(name_of(m) for m in joints.members(j)[:3])
    return f"{j.name}: {names}" if names else j.name


def centre(objs) -> Vector:
    parts = parts_of(objs)
    if not parts:
        return Vector((0.0, 0.0, 0.0))
    mn, mx = build.world_bounds(parts)
    return Vector(((np.asarray(mn) + np.asarray(mx)) / 2.0).tolist())


def size_of(objs) -> np.ndarray:
    parts = parts_of(objs)
    if not parts:
        return np.zeros(3)
    mn, mx = build.world_bounds(parts)
    return np.asarray(mx, float) - np.asarray(mn, float)


def middle(scene) -> Vector:
    """The crane's middle: the slew axis' point, else the model's centre."""
    j = first(scene, "slew")
    if j is not None:
        o, _d = joints.axis_world(j)
        return Vector(o)
    root = model_root(scene)
    return centre([root]) if root is not None else Vector((0.0, 0.0, 0.0))


def sense_ok(scene, role: str, j) -> bool:
    """True when the joint moves the right way for its role (+ = up / out / down / anticlockwise)."""
    o, d = joints.axis_world(j)
    o, d = Vector(o), Vector(d)
    c = centre(joints.members(j)) if joints.members(j) else o
    if role == "slew":
        return d.z > 0.0
    if role in ("luff", "jib", "knuckle"):
        return d.cross(c - o).z > 0.0
    if role in ("hoist", "jack"):
        return d.z < 0.0
    if role in ("telescope", "extension"):
        piv = first(scene, "knuckle" if role == "extension" else "luff")
        p = Vector(joints.axis_world(piv)[0]) if piv is not None else middle(scene)
        return d.dot(c - p) > 0.0
    if role == "outrigger":
        m = middle(scene)
        v = Vector((c.x - m.x, c.y - m.y, 0.0))
        return Vector((d.x, d.y, 0.0)).dot(v) > 0.0
    return True


def orient(scene, role: str, j) -> bool:
    """Turn the joint round when it moves the wrong way for its role; True when it was turned."""
    if role in ("swing", "track", "travel") or sense_ok(scene, role, j):
        return False
    joints.flip(scene, j)
    return True


def _role_name(scene, role: str) -> str:
    kind = kind_of(scene)
    base = {"luff": "Main boom" if kind == "knuckle_boom_crane" else "Luff",
            "outrigger": "Stabilisers" if kind == "knuckle_boom_crane" else "Outriggers",
            "jack": "Legs" if kind == "knuckle_boom_crane" else "Jacks"}.get(role, ROLE_WORDS[role])
    return joints.unique_name(scene, base)


def make_joint(scene, role: str, objs, origin, direction, name: str = "", base=None, allow_empty: bool = False,
               stroke: float = 0.0, ref=None):
    """A joint of the app for a crane role: made, given its role, turned the right way, its Max = ``stroke`` (m or
    radians) for a slide when given. Returns the joint item."""
    kind = "ROTATE" if role in ROTATE_ROLES else "SLIDE"
    j = joints.create(scene, kind, list(objs), Vector(origin), Vector(direction), name=name or _role_name(scene, role),
                      base=base, ref=ref, allow_empty=allow_empty)
    jname = j.name
    j = joints.find(scene, jname)
    j.role = role
    orient(scene, role, joints.find(scene, jname))
    j = joints.find(scene, jname)
    if stroke > 0.0 and kind == "SLIDE":
        j.slide_min, j.slide_max = 0.0, float(stroke)
        j.use_limits = True
    changed(scene)
    return joints.find(scene, jname)


# ---------------------------------------------------------------------------------------------------------------------
# axes offered for a joint

UP = Vector((0.0, 0.0, 1.0))


def _mesh_axes(ob) -> list:
    """(origin, direction, radius) of a part's round faces, world, from the importer's ``fr_axes``."""
    me = ob.data if ob.type == "MESH" else None
    if me is None or "fr_axes" not in me:
        return []
    a = list(me["fr_axes"])
    mw = ob.matrix_world
    out = []
    for k in range(0, len(a) - 6, 7):
        o = mw @ Vector(a[k:k + 3])
        d = (mw.to_3x3() @ Vector(a[k + 3:k + 6])).normalized()
        u = Vector(a[k + 3:k + 6]).orthogonal().normalized()
        w = Vector(a[k + 3:k + 6]).cross(u).normalized()
        r = abs(a[k + 6]) * 0.5 * ((mw.to_3x3() @ u).length + (mw.to_3x3() @ w).length)
        out.append((o, d, r, ob))
    return out


def _same_line(a, b, tol: float = 2e-4) -> bool:
    (o1, d1), (o2, d2) = a, b
    if abs(abs(d1.dot(d2)) - 1.0) > 1e-6:
        return False
    v = o2 - o1
    return (v - v.dot(d1) * d1).length < tol


def _orientation_ok(role: str, d: Vector) -> bool:
    if role == "slew":
        return abs(d.dot(UP)) > 0.999
    if role in ("luff", "jib", "knuckle", "swing"):
        return abs(d.dot(UP)) < 0.02
    return True


def _where(p: Vector, scene) -> str:
    m = middle(scene)
    return f"at {p.x - m.x:+.2f}, {p.y - m.y:+.2f}, {p.z:.2f} m"


def axis_candidates(scene, role: str, objs) -> list:
    """[(label, origin, direction, radius, shared)] for the step: round faces of the picked parts (and of the parts
    they sit on that share the line: a pin through both), then directions. Best first: shared pins, the picked
    parts' own faces before deeper ones, the bigger round face first."""
    out = []
    if role in SLIDE_ROLES or role == "track":
        size = size_of(objs)
        c = centre(objs)
        if role in ("hoist", "jack"):
            out.append(("Straight down", c, -UP, 0.0, False))
        if role in ("telescope", "extension", "outrigger", "travel"):
            k = int(np.argmax(size[:3]))
            if role == "outrigger":
                k = 0 if size[0] >= size[1] else 1
            d = Vector([1.0 if i == k else 0.0 for i in range(3)])
            if role in ("telescope", "extension"):
                d = _along_boom(scene, role, objs) or d
            out.append(("Along the part (its longest side)", c, d, 0.0, False))
        for lab, d in (("Along X", Vector((1, 0, 0))), ("Along Y", Vector((0, 1, 0))), ("Straight up", UP)):
            out.append((lab, c, d, 0.0, False))
    seen = []
    own = set()
    for ob in objs:
        own.add(ob)
        own.update(ch for ch in logic.Tree().children(ob) if ch.type == "MESH")
    found = []
    for ob in parts_of(objs):
        for o, d, r, part in _mesh_axes(ob):
            if not _orientation_ok(role, d) or r <= 0.0:
                continue
            found.append((o, d, r, part, part in own))
    # the parts the picked ones sit on (the parent sub-assembly's own parts): a pin through both is "shared"
    base_parts = []
    tree = logic.Tree()
    for ob in objs:
        par = build.logical_parent(ob)
        if par is not None:
            base_parts += [c for c in tree.children(par) if c.type == "MESH" and c not in objs]
    base_axes = [(o, d) for ob in base_parts for o, d, r, _p in _mesh_axes(ob) if r > 0.0]
    found.sort(key=lambda f: (not any(_same_line((f[0], f[1]), b, 0.002) for b in base_axes), not f[4], -f[2]))
    for o, d, r, part, _own in found:
        if any(_same_line((o, d), s, 0.002) for s in seen):
            continue
        seen.append((o, d))
        shared = any(_same_line((o, d), b, 0.002) for b in base_axes)
        word = "pin" if shared else "round face"
        across = "upright" if abs(d.dot(UP)) > 0.999 else ("level" if abs(d.dot(UP)) < 0.02 else "slanted")
        label = f"{word} Ø{r * 2000:.0f} mm on {name_of(part)}, {across}"
        out.append((label, o, d, r, shared))
        if len(out) >= 24:
            break
    return out


def _along_boom(scene, role: str, objs):
    """A telescope / extension slides along the boom: the sections' long direction (their mesh points' main axis,
    square to the pivot's axis), pointing away from the pivot."""
    piv = first(scene, "knuckle" if role == "extension" else "luff")
    if piv is None:
        return None
    o, axis = joints.axis_world(piv)
    tree = logic.Tree()
    own = [c for ob in objs for c in ([ob] if ob.type == "MESH" else tree.children(ob)) if c.type == "MESH"]
    d = principal(own, Vector(axis))
    if d is None:
        return None
    if d.dot(centre(objs) - Vector(o)) < 0.0:
        d = -d
    return d


def find_axes(scene, role: str) -> int:
    """Fill the step's axis list for the picked parts."""
    cs = settings(scene)
    objs, _bad = objects_of(scene, cs.pick)
    cs.axes.clear()
    for label, o, d, r, shared in axis_candidates(scene, role, objs):
        a = cs.axes.add()
        a.label, a.origin, a.direction, a.radius, a.shared = label, tuple(o), tuple(d), r, shared
    cs.axis_index = 0 if len(cs.axes) else -1
    cs.axes_for = role + ":" + cs.pick
    return len(cs.axes)


def chosen_axis(scene):
    cs = settings(scene)
    if 0 <= cs.axis_index < len(cs.axes):
        a = cs.axes[cs.axis_index]
        return Vector(a.origin), Vector(a.direction), a
    return None


# ---------------------------------------------------------------------------------------------------------------------
# chains: telescope sections, extensions, outrigger corners

def make_chain(scene, role: str, objs, axis_o, axis_d, stroke: float, follow: bool = True, lead=None) -> list:
    """One slide joint per section, each riding on the one before, all following the first with ratio 1 (the
    sections share the stroke, as the built-in cranes and the way covers do). ``lead``: an existing joint the first
    one follows too (a further outrigger corner follows the first corner)."""
    made = []
    for i, ob in enumerate(objs):
        j = make_joint(scene, role, [ob], axis_o, axis_d, stroke=stroke)
        made.append(j.name)
        leader = lead if i == 0 else made[0]
        if follow and leader:
            joints.set_follows(scene, joints.find(scene, j.name), leader, ratio=1.0)
    return [joints.find(scene, n) for n in made]


def hook_wrappers(block) -> list:
    """The sub-assemblies round the hook block that only hold hook things (rope, block): outermost first – the
    built-in models' HOOK SWING.ASM. Stops at a sub-assembly a joint already moves."""
    out = []
    tree = logic.Tree()
    ob = build.logical_parent(block)
    scene = bpy.context.scene
    while ob is not None and ob.get(build.PROP_KIND) == "assembly" and not ob.get(build.PROP_ROOT):
        if joints.joint_of_object(scene, ob) is not None:
            break
        if len(tree.children(ob)) > 3:
            break
        out.append(ob)
        ob = build.logical_parent(ob)
    return out[::-1]


def make_hook(scene, block, sheave_point) -> dict:
    """The hook block's joints: one hook swing per turning boom joint (luff, then jib / knuckle) at the head sheave,
    each following its joint with ratio -1 (the block hangs plumb), and the hoist (straight down) riding on the last
    swing. Swings go on the sub-assemblies round the block when the model has them, else they move nothing and only
    carry the hoist."""
    # names, not items: the joint list grows below (items held across that go stale)
    turning = [j.name for j in (first(scene, "luff"), first(scene, "jib") or first(scene, "knuckle"))
               if j is not None]
    axes = {n: Vector(joints.axis_world(joints.find(scene, n))[1]) for n in turning}
    wraps = hook_wrappers(block)
    p = Vector(sheave_point)
    made = []
    base = None
    for i, tname in enumerate(turning):
        objs = [wraps[i]] if i < len(wraps) else []
        if not objs and base is None:
            below = _carrier_of(scene, block)
            base = below.motion if below is not None else None
        j = joints.create(scene, "ROTATE", objs, p, axes[tname], name=joints.unique_name(scene, "Hook swing"),
                          base=base if not objs else None, allow_empty=not objs)
        jname = j.name
        joints.find(scene, jname).role = "swing"
        joints.set_follows(scene, joints.find(scene, jname), tname, ratio=-1.0)
        made.append(jname)
        base = joints.find(scene, jname).motion
    hoist_base = None
    if made and len(wraps) < len(made):
        hoist_base = joints.find(scene, made[-1]).motion
    h = joints.create(scene, "SLIDE", [block], p, -UP, name=joints.unique_name(scene, "Hoist"), base=hoist_base)
    h = joints.find(scene, h.name)
    h.role = "hoist"
    changed(scene)
    return {"swings": made, "hoist": h.name}


def _carrier_of(scene, ob):
    """The joint that moves ``ob`` now (the last boom section's), or None."""
    cur = ob
    while cur is not None:
        j = joints.joint_of_object(scene, cur)
        if j is not None:
            return j
        cur = build.logical_parent(cur)
    return None


def find_hook_point(scene, block, sheave_point) -> Vector | None:
    """A first guess of the hook's saddle: on the plumb line under the head sheave, the top of the lowest piece of
    steel the line crosses (a ray from below: in at a piece's underside, out at its top). None when the line misses
    the block. The maker's drawing gives the exact point: the step lets the user type it."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    p = Vector(sheave_point)
    parts = parts_of([block])
    if not parts:
        return None
    mn, _mx = build.world_bounds(parts)
    start = Vector((p.x, p.y, float(mn[2]) - 1.0))
    pieces = []
    for ob in parts:
        inv = ob.matrix_world.inverted()
        tree = BVHTree.FromObject(ob, dg, deform=False)
        o = inv @ start
        d = (inv.to_3x3() @ UP).normalized()
        zs = []
        for _k in range(16):
            loc, _n, _i, _dist = tree.ray_cast(o, d)
            if loc is None:
                break
            zs.append((ob.matrix_world @ loc).z)
            o = loc + d * 1e-6
        pieces += [(zs[k], zs[k + 1]) for k in range(0, len(zs) - 1, 2)]
    if not pieces:
        return None
    _lo, hi = min(pieces)
    return Vector((p.x, p.y, hi))


# ---------------------------------------------------------------------------------------------------------------------
# the model's frame (the equipment file's coordinates: the STEP's mm)

def to_model(root, world) -> np.ndarray:
    M = np.array(root.matrix_world)
    return (np.linalg.inv(M) @ np.r_[np.asarray(world, float)[:3], 1.0])[:3] * 1000.0


def dir_to_model(root, d) -> np.ndarray:
    M = np.array(root.matrix_world)[:3, :3]
    v = np.linalg.inv(M) @ np.asarray(d, float)[:3]
    return v / np.linalg.norm(v)


def to_world(root, p_mm) -> Vector:
    return root.matrix_world @ (Vector(p_mm) / 1000.0)


# ---------------------------------------------------------------------------------------------------------------------
# groups' masses and CoG

def ensure_groups(scene) -> None:
    """The kind's mass groups, filled with the parts their joints move (a first guess the user can change)."""
    cs = settings(scene)
    kind = kind_of(scene) or "other_crane"
    have = {g.key for g in cs.groups}
    for key, _title in GROUPS[kind]:
        if key in have:
            continue
        g = cs.groups.add()
        g.key = key
        g.name = key
        role = GROUP_ROLE.get(key)
        j = first(scene, role) if role else None
        if j is not None:
            g.parts = SEP.join(name_of(m) for m in joints.members(j))


def group_title(scene, key: str) -> str:
    for kind_groups in GROUPS.values():
        for k, t in kind_groups:
            if k == key:
                return t
    return key.replace("_", " ").capitalize()


def work_out(scene, g) -> str:
    """The group's volume x density and its CoG from the parts' solid volumes (0201's load code: closed solids, an
    open part counts as its box). Call in the CAD pose. '' or a note."""
    from ..core import lifting_load as LD
    from . import lifting
    objs, bad = objects_of(scene, g.parts)
    if bad:
        return "; ".join(bad)
    parts = parts_of(objs)
    if not parts:
        return "No parts picked."
    items, opened = [], []
    for ob in parts:
        M = np.array(ob.matrix_world)
        det = abs(float(np.linalg.det(M[:3, :3])))
        sol = lifting._solid_of(ob)
        if not sol.closed:
            opened.append(name_of(ob))
            corners = np.array([list(v) for v in ob.bound_box])
            sol = LD.box_solid(corners.min(axis=0), corners.max(axis=0))
        items.append((sol.volume * det * g.density, (M @ np.r_[sol.centroid, 1.0])[:3]))
    mass, cog = LD.combine(items)
    g.volume_mass = float(mass)
    root = model_root(scene)
    if not g.cog_by_hand and root is not None:
        g.cog = tuple((to_model(root, cog) / 1000.0).tolist())
    g.worked = True
    return ("Not closed solids (their box was used): " + ", ".join(opened[:4])) if opened else ""


def group_mass_t(g) -> float:
    return g.mass_t if g.mass_mode == "ENTERED" else g.volume_mass / 1000.0


def update_marker(scene, g) -> None:
    """The group's CoG marker: an empty at its CoG, riding on the group's first part."""
    root = model_root(scene)
    objs, _bad = objects_of(scene, g.parts)
    name = f"FR crane CoG {g.key}"
    ob = g.marker if g.marker is not None and g.marker.name in bpy.data.objects else bpy.data.objects.get(name)
    if root is None or not objs:
        return
    if ob is None:
        ob = bpy.data.objects.new(name, None)
        ob.empty_display_type = "SPHERE"
        ob["fr_crane_cog"] = g.key
        scene.collection.objects.link(ob)
        g.marker = ob
    ob.empty_display_size = max(0.05, 0.02 * float(np.max(size_of([root]))))
    carrier = objs[0]
    w = to_world(root, np.asarray(g.cog) * 1000.0)
    from mathutils import Matrix
    ob.parent = carrier
    ob.matrix_parent_inverse = carrier.matrix_world.inverted()
    ob.matrix_basis = Matrix.Translation(w)


# ---------------------------------------------------------------------------------------------------------------------
# the load chart: the typed table <-> the library's entry (refusals by row)

def chart_entry(scene):
    """The typed charts as the library reads them (``lifting_library.chart_rows``): an Entry with its refusals."""
    from ..core import lifting_library as LL
    cs = settings(scene)
    rows, lines, n = [], [], 0
    # a key one configuration names is named by all (a 0 t counterweight is a configuration of its own); the fields
    # are 32-bit: round to 0.1 mm / 0.1 kg so a 10.8 m boom stays 10.8 m
    named = {k for c in cs.charts for k in ("boom", "jib", "counterweight", "outriggers") if getattr(c, k) > 0}
    for c in cs.charts:
        cfg = {}
        for k in ("boom", "counterweight", "outriggers"):
            if k in named:
                cfg[k] = round(float(getattr(c, k)), 4)
        if c.jib > 0:
            cfg["jib"] = round(float(c.jib), 4)
        for r in c.rows:
            n += 1
            rows.append((cfg, r.radius, r.capacity))
            lines.append(n)
    if not rows:
        return None
    return LL.chart_rows(rows, "t", "m", lines=lines)


def chart_dicts(scene) -> list:
    """The charts for the file (t, m), with wind, hook block and source; [] when there is none or it is refused."""
    cs = settings(scene)
    e = chart_entry(scene)
    if e is None or not e.ok:
        return []
    out = e.dicts("t", "m")
    for d in out:
        if cs.chart_wind > 0:
            d["wind_max"] = round(cs.chart_wind, 3)
        if cs.chart_hook:
            d["includes_hook_block"] = True
    return out


def fill_charts(scene, entry) -> int:
    """Put an entry's charts (CSV or a file) into the typed table, in t and m."""
    cs = settings(scene)
    cs.charts.clear()
    for ch in entry.charts:
        c = cs.charts.add()
        cfg = ch.config or {}
        c.boom = float(cfg.get("boom") or 0.0)
        c.jib = float(cfg.get("jib") or 0.0)
        c.counterweight = float(cfg.get("counterweight") or 0.0) / 1000.0
        c.outriggers = float(cfg.get("outriggers") or 0.0)
        for r, cap in zip(ch.radius, ch.capacity):
            row = c.rows.add()
            row.radius = f"{r:g}"
            row.capacity = "" if cap is None else f"{cap / 1000.0:g}"
    cs.chart_index = 0
    changed(scene)
    return len(entry.charts)


# ---------------------------------------------------------------------------------------------------------------------
# the steps: drawing

def _done(layout, context, text):
    from . import ui_setup
    return ui_setup.done_line(layout, context, text)


def _pick_box(layout, context, op_role: str, what: str):
    """The parts field: type a name (matches below), or Use clicked."""
    cs = settings(context.scene)
    box = layout.box()
    box.prop(cs, "search", text="", icon="VIEWZOOM")
    got = matches(context.scene, cs.search, limit=8)
    if got:
        col = box.column(align=True)
        for n in got:
            op = col.operator("fresing.crane_pick", text=n, icon="ADD")
            op.names, op.add = n, True
    elif cs.search.strip():
        ui.hint(box, context, "No part or sub-assembly holds that name.")
    row = box.row(align=True)
    row.operator("fresing.crane_pick", text="Use clicked", icon="RESTRICT_SELECT_OFF").use_clicked = True
    row.operator("fresing.crane_pick", text="Clear", icon="X").clear = True
    objs, bad = objects_of(context.scene, cs.pick, many_ok=op_role == "track")
    if objs:
        ui.wrap(box, context, f"{what}: " + ", ".join(name_of(o) for o in objs[:6]) + (" …" if len(objs) > 6 else ""),
                icon="RESTRICT_SELECT_OFF")
    else:
        ui.hint(box, context, f"{what}: none picked yet")
    for b in bad:
        ui.wrap(box, context, b, icon="ERROR", alert=True)
    return objs


def _axis_box(layout, context, role: str):
    cs = settings(context.scene)
    if cs.axes_for != role + ":" + cs.pick:
        ui.big(layout, "fresing.crane_axes", "Find the axes", "VIEWZOOM").role = role
        return False
    if not len(cs.axes):
        ui.wrap(layout, context, "No round face or direction fits: click the axis on the model instead.", icon="INFO")
    col = layout.column(align=True)
    for i, a in enumerate(cs.axes[:10]):
        op = col.operator("fresing.crane_axis_use", text=a.label, depress=i == cs.axis_index,
                          icon="LINKED" if a.shared else ("FORCE_VORTEX" if a.radius > 0 else "EMPTY_SINGLE_ARROW"))
        op.index = i
    if len(cs.axes) > 10:
        ui.hint(layout, context, f"{len(cs.axes) - 10} more: type a closer name above to narrow them.")
    return True


def _joint_rows(layout, context, js, role: str):
    """The made joints of a role: name, what it moves, the joint's own limits (4 Motion's settings), Flip."""
    for j in js:
        box = layout.box()
        box.label(text=joint_text(j), icon="CON_PIVOT" if j.kind == "ROTATE" else "CON_LOCLIKE")
        if j.follows:
            ui.hint(box, context, f"Follows {j.follows} (ratio {j.couple_ratio:g})")
            continue
        row = box.row(align=True)
        row.prop(j, "use_limits", text="Limits")
        sub = row.row(align=True)
        sub.active = j.use_limits
        if j.kind == "ROTATE":
            sub.prop(j, "rot_min", text="")
            sub.prop(j, "rot_max", text="")
        else:
            sub.prop(j, "slide_min", text="")
            sub.prop(j, "slide_max", text="")
        row = box.row(align=True)
        row.operator("fresing.crane_flip", text="Flip", icon="ARROW_LEFTRIGHT").joint = j.name
        row.operator("fresing.crane_remove", text="Remove", icon="TRASH").joint = j.name
        own = j.role if j.role in SENSE else role
        if SENSE.get(own):
            ui.hint(box, context, SENSE[own] + ("" if sense_ok(context.scene, own, j) else " – NOT SO: press Flip"))


def _joint_done(role):
    def done(context):
        js = with_role(context.scene, role, driven_only=True)
        return joint_text(js[0]) if js else ""
    return done


def _joint_step(role: str, text: str, what: str = "Moving parts", optional: str = "", chain: bool = False):
    """A step that makes one joint (or a chain of sections) for a role."""
    def draw(layout, context):
        scene = context.scene
        if model_root(scene) is None:
            ui.missing(layout, context, "First the crane's model: step 1.")
            return
        ui.wrap(layout, context, text, icon="INFO")
        if optional:
            ui.hint(layout, context, optional)
        js = with_role(scene, role)
        if js:
            _done(layout, context, f"{plural(len(js), 'joint')}: " + ", ".join(j.name for j in js[:4]))
            _joint_rows(layout, context, js, role)
            ui.gap(layout, size=0.5)
            ui.hint(layout, context, "To make it again: Remove, then pick below.")
        objs = _pick_box(layout, context, role, what)
        if not objs:
            return
        if _axis_box(layout, context, role):
            cs = settings(scene)
            if chain or role in SLIDE_ROLES:
                ui.split_props(layout).prop(cs, "stroke", text="Stroke")
            op = ui.big(layout, "fresing.crane_make", "Make " + ("the sections" if chain else ROLE_WORDS[role].lower())
                        + " joint" + ("s" if chain else ""), "CON_PIVOT")
            op.role, op.chain = role, chain
            ui.hint(layout, context, "Or click the axis on the model in the main window:")
            op = ui.big(layout, "fresing.crane_make_click", "Click the axis", "EYEDROPPER")
            op.role = role
    return draw, _joint_done(role)


def _model_done(context) -> str:
    root = model_root(context.scene)
    return f"Model: {name_of(root)}" if root is not None else ""


def _model(layout, context):
    scene = context.scene
    cs = settings(scene)
    roots = build.model_roots(scene)
    if not roots:
        ui.wrap(layout, context, "Import the STEP of your crane first, with the boom down and every joint at the "
                                 "place the maker's drawing calls 0 (boom level or as drawn, sections in, rope up).",
                icon="INFO")
        ui.big(layout, "fresing.import_step", "Import STEP…", "IMPORT")
        return
    if len(roots) > 1:
        ui.wrap(layout, context, "The project holds several models: pick the crane.", icon="INFO")
        layout.prop_search(cs, "root", scene, "objects", text="Crane")
    text = _model_done(context)
    if text:
        _done(layout, context, text)
    col = ui.split_props(layout)
    col.prop(cs, "name", text="Name")
    col.prop(cs, "cls", text="Class")
    ui.hint(layout, context, "Its name in your library. The crane's joints are made in the next steps; they show in "
                             f"{ui.where('motion')} too.")


def _cylinder_done(context) -> str:
    n = len(context.scene.fresing.cylinders)
    return plural(n, "cylinder") if n else ""


def _cylinder_part(layout, context, role: str):
    """A luff / knuckle cylinder (optional): barrel and rod by name, pins from the two parts' round faces."""
    ui.gap(layout, size=0.5)
    layout.label(text="Its cylinder (optional)")
    n = len(context.scene.fresing.cylinders)
    if n:
        _done(layout, context, plural(n, "cylinder") + f" in {ui.where('cylinders')}")
    op = ui.big(layout, "fresing.crane_cylinder", "Add the cylinder (barrel | rod)", "MOD_SIMPLEDEFORM")
    op.role = role
    ui.hint(layout, context, "Pick the barrel and then the rod above (in that order) and press it: the pins are "
                             "the round faces at their eyes.")


def _with_cylinder(step, role):
    draw0, done = step

    def draw(layout, context):
        draw0(layout, context)
        if with_role(context.scene, role):
            _cylinder_part(layout, context, role)
    return draw, done


def _hoist_done(context) -> str:
    cs = settings(context.scene)
    return f"Head sheave picked, {plural(cs.falls, 'fall')}" if cs.sheave_set else ""


def _hoist(layout, context):
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Pick the head sheave at the boom's (or jib's) tip: the rope hangs from its middle. "
                             "The hook block and its joints come in the next step.", icon="INFO")
    _pick_box(layout, context, "hoist", "Head sheave")
    text = _hoist_done(context)
    if text:
        _done(layout, context, text)
    ui.big(layout, "fresing.crane_sheave", "Use as head sheave", "FORCE_VORTEX")
    col = ui.split_props(layout)
    col.prop(cs, "falls", text="Falls")
    col.prop(cs, "rope_part", text="Rope part")
    ui.hint(layout, context, "Falls: how many rope lines hold the hook block (drawn later). Rope part: the hoist "
                             "rope drawn in the CAD (optional) – it then follows the hook.")


def _hook_done(context) -> str:
    j = first(context.scene, "hoist")
    cs = settings(context.scene)
    if j is None or not cs.hook_set:
        return ""
    return f"Hook block {cs.hook_part}, hook point set"


def _hook(layout, context):
    scene = context.scene
    cs = settings(scene)
    if not cs.sheave_set:
        ui.missing(layout, context, "First the head sheave (the step before).")
        return
    ui.wrap(layout, context, "Pick the hook block (its sub-assembly). The app makes the hoist (straight down from "
                             "the head sheave) and the hook swing joints that keep it plumb, and finds the hook's "
                             "saddle.", icon="INFO")
    text = _hook_done(context)
    if text:
        _done(layout, context, text)
        _joint_rows(layout, context, with_role(scene, "hoist"), "hoist")
        col = ui.split_props(layout)
        col.prop(cs, "hook_point", text="Hook point")
        col.prop(cs, "hook_block_t", text="Hook block, t")
        ui.hint(layout, context, "The hook point is in the model's frame with the rope up; change it when the "
                                 "saddle was missed.")
        return
    _pick_box(layout, context, "hoist", "Hook block")
    ui.big(layout, "fresing.crane_hook", "Make the hoist and hook", "TRACKER")


def _outrigger_done(context) -> str:
    js = with_role(context.scene, "outrigger")
    jacks = with_role(context.scene, "jack")
    if not js:
        return ""
    return f"{plural(len(js), 'beam joint')}, {plural(len(jacks), 'jack')}"


def _outriggers(layout, context):
    scene = context.scene
    cs = settings(scene)
    kind = kind_of(scene)
    word = "stabiliser" if kind == "knuckle_boom_crane" else "outrigger"
    ui.wrap(layout, context, f"One corner at a time: pick its {word} beam stages from the inside out, then its "
                             f"{'leg' if word == 'stabiliser' else 'jack'} last, and press Add corner. The first "
                             "corner's joints drive; the other corners follow them.", icon="INFO")
    ui.hint(layout, context, "Skip this step when the crane has none.")
    text = _outrigger_done(context)
    if text:
        _done(layout, context, text)
        _joint_rows(layout, context, [j for j in with_role(scene, "outrigger") + with_role(scene, "jack")
                                      if not j.follows], "outrigger")
    _pick_box(layout, context, "outrigger", "Beam stages, then the jack")
    col = ui.split_props(layout)
    col.prop(cs, "stroke", text="Beam stroke")
    col.prop(cs, "spreads", text="Spreads")
    op = ui.big(layout, "fresing.crane_corner", "Add corner", "ADD")
    op.jack_stroke = 0.0
    ui.hint(layout, context, "Spreads: full / middle / narrow, pad centre to pad centre (the charts' spreads).")


def _counterweight_done(context) -> str:
    cs = settings(context.scene)
    g = next((g for g in cs.groups if g.key == "counterweight" and g.parts), None)
    return f"Counterweight: {g.parts}" if g is not None else ""


def _counterweight(layout, context):
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Pick the counterweight's parts (they turn with the slew) and type the steps the "
                             "crane can carry.", icon="INFO")
    g = next((g for g in cs.groups if g.key == "counterweight"), None)
    text = _counterweight_done(context)
    if text:
        _done(layout, context, text)
    objs = _pick_box(layout, context, "counterweight", "Counterweight")
    if objs:
        ui.big(layout, "fresing.crane_group_parts", "Use as counterweight", "CHECKMARK").key = "counterweight"
    ui.split_props(layout).prop(cs, "counterweight_steps", text="Steps, t")
    if g is not None:
        ui.split_props(layout).prop(g, "mass_t", text="In the model, t")


def _tracks_done(context) -> str:
    n = len(context.scene.fresing.tracks)
    t = first(context.scene, "travel")
    if not n and t is None:
        return ""
    return f"{plural(n, 'track')}" + (f", travel: {t.name}" if t is not None else "")


def _tracks(layout, context):
    scene = context.scene
    ui.wrap(layout, context, "Travel: pick the whole crane (its top sub-assembly) and make the joint that drives it "
                             "along the tracks. Then each track: pick its wheels (drive sprocket first, then the "
                             "idler), then one link, then its shoe; press Add track.", icon="INFO")
    ui.hint(layout, context, "Skip this step when the crawler stays where it stands.")
    text = _tracks_done(context)
    if text:
        _done(layout, context, text)
    objs = _pick_box(layout, context, "travel", "Parts")
    if objs and first(scene, "travel") is None:
        if _axis_box(layout, context, "travel"):
            op = ui.big(layout, "fresing.crane_make", "Make the travel joint", "CON_LOCLIKE")
            op.role, op.chain = "travel", False
    elif objs:
        ui.big(layout, "fresing.crane_track", "Add track (wheels | link | shoe)", "MOD_ARRAY")


def _groups_done(context) -> str:
    cs = settings(context.scene)
    gs = [g for g in cs.groups if g.parts]
    if not gs or any(group_mass_t(g) <= 0 for g in gs):
        return ""
    return f"{plural(len(gs), 'group')}, {sum(group_mass_t(g) for g in gs):.1f} t"


def _groups(layout, context):
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Each group's mass (the maker's data sheet) or volume x density, and its centre of "
                             "gravity: worked out from the parts' solids, or typed. The markers show in the view.",
            icon="INFO")
    text = _groups_done(context)
    if text:
        _done(layout, context, text)
    if not len(cs.groups):
        ui.big(layout, "fresing.crane_groups", "Make the groups", "PACKAGE")
        return
    for g in cs.groups:
        box = layout.box()
        box.label(text=group_title(scene, g.key), icon="PACKAGE")
        box.prop(g, "parts", text="")
        row = box.row(align=True)
        row.prop(g, "mass_mode", expand=True)
        col = ui.split_props(box)
        if g.mass_mode == "ENTERED":
            col.prop(g, "mass_t", text="Mass, t")
        else:
            col.prop(g, "density", text="Density")
            box.label(text=f"= {g.volume_mass / 1000.0:.3f} t (estimate)")
        col.prop(g, "cog_by_hand", text="CoG by hand")
        sub = box.column(align=True)
        sub.active = g.cog_by_hand
        sub.prop(g, "cog", text="")
        box.operator("fresing.crane_group_work", text="Work out", icon="FILE_REFRESH").key = g.key


def _chart_done(context) -> str:
    e = chart_entry(context.scene)
    if e is None or not e.ok:
        return ""
    return f"{plural(len(e.charts), 'chart')}, no refusals"


def _chart(layout, context):
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Your crane's load chart, from the maker: one table per configuration (boom, jib, "
                             "counterweight, outrigger spread). Type it, paste it as CSV, or read a CSV file.",
            icon="INFO")
    row = layout.row(align=True)
    row.operator("fresing.crane_chart_csv", text="Paste CSV", icon="PASTEDOWN").paste = True
    row.operator("fresing.crane_chart_csv", text="Read CSV…", icon="FILE_FOLDER").paste = False
    row = layout.row(align=True)
    row.operator("fresing.crane_chart_add", text="Add configuration", icon="ADD")
    for ci, c in enumerate(cs.charts):
        box = layout.box()
        head = box.row(align=True)
        head.label(text=f"Configuration {ci + 1}")
        op = head.operator("fresing.crane_chart_add", text="", icon="X")
        op.remove = ci
        col = box.column(align=True)
        col.prop(c, "boom")
        col.prop(c, "jib")
        col.prop(c, "counterweight")
        col.prop(c, "outriggers")
        grid = box.column(align=True)
        row = grid.row(align=True)
        row.label(text="Radius, m")
        row.label(text="Capacity, t")
        for r in c.rows:
            row = grid.row(align=True)
            row.prop(r, "radius", text="")
            row.prop(r, "capacity", text="")
        op = box.operator("fresing.crane_chart_add", text="Add row", icon="ADD")
        op.row_of = ci
    e = chart_entry(scene)
    if e is not None:
        for m in e.errors[:8]:
            ui.wrap(layout, context, m, icon="ERROR", alert=True)
        for m in e.warnings[:4]:
            ui.wrap(layout, context, m, icon="INFO")
    elif not len(cs.charts):
        ui.hint(layout, context, "No chart: the crane can be placed and moved, but crane use says 'Not checked – "
                                 "no chart'.")
    text = _chart_done(context)
    if text:
        _done(layout, context, text)
    col = ui.split_props(layout)
    col.prop(cs, "chart_wind", text="Wind, m/s")
    col.prop(cs, "chart_hook", text="Includes hook block")
    col.prop(cs, "chart_source", text="Source")


def _poses_done(context) -> str:
    own = {j.name for j in crane_joints(context.scene)}
    n = sum(1 for p in context.scene.fresing.poses if any(pj.joint in own for pj in p.joints))
    return plural(n, "pose") if n else ""


def _poses(layout, context):
    scene = context.scene
    s = scene.fresing
    cs = settings(scene)
    ui.wrap(layout, context, "Save the crane's poses (Travel, Set up, Working …): move the joints in "
                             f"{ui.where('motion')}, then Save pose. The pose it starts in when placed is picked "
                             "below.", icon="INFO")
    text = _poses_done(context)
    if text:
        _done(layout, context, text)
    ui.big(layout, "fresing.pose_save", "Save pose", "ADD")
    col = layout.column(align=True)
    for p in s.poses:
        col.operator("fresing.pose_apply", text=p.name, icon="ARMATURE_DATA").name = p.name
    layout.prop_search(cs, "start_pose", s, "poses", text="Start pose")


def _check_done(context) -> str:
    cs = settings(context.scene)
    if not cs.checked:
        return ""
    red = [p for p in cs.problems if p.severity == "red"]
    return "" if red else "Check found nothing wrong"


def _check(layout, context):
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Runs every joint from its Min to its Max and every pose: the hook stays plumb, nothing "
                             "clashes, the masses and the CoG, the chart. A problem leads to its step.", icon="INFO")
    ui.big(layout, "fresing.crane_check", "Check", "CHECKMARK")
    text = _check_done(context)
    if text:
        _done(layout, context, text)
    for p in cs.problems:
        box = layout.box()
        ui.wrap(box, context, p.text, icon="ERROR" if p.severity == "red" else "INFO", alert=p.severity == "red")
        if p.step:
            box.operator("fresing.crane_go", text="Go to step", icon="TRIA_RIGHT").key = p.step


def _save_done(context) -> str:
    cs = settings(context.scene)
    return f"Saved: {cs.saved_path}" if cs.saved_path else ""


def _save(layout, context):
    cs = settings(context.scene)
    ui.wrap(layout, context, "Writes the crane into your library (Lifting equipment): its file, a copy of the STEP "
                             "and a small picture. Place it from 8 Lifting plan in any project.", icon="INFO")
    col = ui.split_props(layout)
    col.prop(cs, "name", text="Name")
    col.prop(cs, "cls", text="Class")
    ui.big(layout, "fresing.crane_save", "Save to library", "FILE_TICK")
    text = _save_done(context)
    if text:
        _done(layout, context, text)
    if cs.message:
        ui.wrap(layout, context, cs.message, icon="INFO")


def _joints_free_done(context) -> str:
    n = len([j for j in crane_joints(context.scene) if j.role != "NONE"])
    return plural(n, "joint") + " with a role" if n else ""


def _joints_free(layout, context):
    """Other crane: the building blocks in any order, each joint's role picked by hand."""
    scene = context.scene
    cs = settings(scene)
    ui.wrap(layout, context, "Make the joints in any order, from the bottom up: pick the parts, pick the role, find "
                             "the axes, Make. Slew, luff and hoist are needed; the hook block comes next.",
            icon="INFO")
    text = _joints_free_done(context)
    if text:
        _done(layout, context, text)
    for j in crane_joints(scene):
        row = layout.row(align=True)
        row.label(text=j.name)
        row.prop(j, "role", text="")
    objs = _pick_box(layout, context, cs.free_role, "Moving parts")
    layout.prop(cs, "free_role", text="Role")
    if objs and _axis_box(layout, context, cs.free_role):
        if cs.free_role in SLIDE_ROLES:
            ui.split_props(layout).prop(cs, "stroke", text="Stroke")
        op = ui.big(layout, "fresing.crane_make", "Make the joint", "CON_PIVOT")
        op.role, op.chain = cs.free_role, False


# step keys -> (title, draw, done); the lists per kind
_slew = _joint_step("slew", "Pick what turns on the slewing ring (the superstructure with its boom), then its axis: "
                            "the slewing ring's round face, upright.")
_luff = _with_cylinder(_joint_step("luff", "Pick the boom (its base section) and its pivot: the pin at its foot, "
                                           "level and across the boom."), "luff")
_boom = _with_cylinder(_joint_step("luff", "Pick the lattice boom and its foot pin (level, across the boom)."), "luff")
_main = _with_cylinder(_joint_step("luff", "Pick the main boom and its pin on the column (level)."), "luff")
_tele = _joint_step("telescope", "Pick the telescope sections from the base outwards (section 2, 3 …): one joint each, "
                                 "riding on the one before, sharing the stroke.", what="Sections", chain=True)
_fly = _joint_step("jib", "Pick the fly jib and its pin at the boom head.", optional="Optional: skip when the crane "
                                                                                     "has no fly jib.")
_ljib = _joint_step("jib", "Pick the luffing jib and its foot pin at the boom head.",
                    optional="Optional: skip when the crane has no luffing jib.")
_knuck = _with_cylinder(_joint_step("knuckle", "Pick the outer boom and its knuckle pin on the main boom."),
                        "knuckle")
_ext = _joint_step("extension", "Pick the extensions from the outer boom outwards: one joint each, riding on the one "
                                "before, sharing the stroke.", what="Extensions", chain=True)

STEP_LISTS = {
    "CRANE_MOBILE": [
        ("model", "Model", _model, _model_done), ("slew", "Slew", *_slew), ("luff", "Luff", *_luff),
        ("telescope", "Telescope", *_tele), ("jib", "Fly jib", *_fly), ("hoist", "Hoist", _hoist, _hoist_done),
        ("hook_block", "Hook block", _hook, _hook_done), ("outrigger", "Outriggers", _outriggers, _outrigger_done),
        ("counterweight", "Counterweight", _counterweight, _counterweight_done),
        ("masses", "Masses & CoG", _groups, _groups_done), ("chart", "Load chart", _chart, _chart_done),
        ("poses", "Poses", _poses, _poses_done), ("check", "Check", _check, _check_done),
        ("save", "Save", _save, _save_done)],
    "CRANE_CRAWLER": [
        ("model", "Model", _model, _model_done), ("travel", "Tracks", _tracks, _tracks_done),
        ("slew", "Slew", *_slew), ("luff", "Boom", *_boom), ("jib", "Luffing jib", *_ljib),
        ("hoist", "Hoist", _hoist, _hoist_done), ("hook_block", "Hook block", _hook, _hook_done),
        ("counterweight", "Counterweight", _counterweight, _counterweight_done),
        ("masses", "Masses & CoG", _groups, _groups_done), ("chart", "Load chart", _chart, _chart_done),
        ("poses", "Poses", _poses, _poses_done), ("check", "Check", _check, _check_done),
        ("save", "Save", _save, _save_done)],
    "CRANE_KNUCKLE": [
        ("model", "Model", _model, _model_done), ("slew", "Slew", *_slew), ("luff", "Main boom", *_main),
        ("knuckle", "Knuckle", *_knuck), ("extension", "Extensions", *_ext),
        ("hoist", "Winch", _hoist, _hoist_done), ("hook_block", "Hook", _hook, _hook_done),
        ("outrigger", "Stabilisers", _outriggers, _outrigger_done),
        ("masses", "Masses & CoG", _groups, _groups_done), ("chart", "Load chart", _chart, _chart_done),
        ("poses", "Poses", _poses, _poses_done), ("check", "Check", _check, _check_done),
        ("save", "Save", _save, _save_done)],
    "CRANE_OTHER": [
        ("model", "Model", _model, _model_done), ("joints", "Joints", _joints_free, _joints_free_done),
        ("hoist", "Hoist", _hoist, _hoist_done), ("hook_block", "Hook block", _hook, _hook_done),
        ("masses", "Masses & CoG", _groups, _groups_done), ("chart", "Load chart", _chart, _chart_done),
        ("poses", "Poses", _poses, _poses_done), ("check", "Check", _check, _check_done),
        ("save", "Save", _save, _save_done)],
}
TITLES = {"CRANE_MOBILE": "Set up a mobile crane", "CRANE_CRAWLER": "Set up a crawler crane",
          "CRANE_KNUCKLE": "Set up a knuckle-boom crane", "CRANE_OTHER": "Set up another crane"}
SETUPS = {k: (TITLES[k], [(t, d) for _key, t, d, _c in v]) for k, v in STEP_LISTS.items()}
CHECKS = {k: [c for _key, _t, _d, c in v] for k, v in STEP_LISTS.items()}
KIND_ICONS = {k: "OUTLINER_OB_ARMATURE" for k in STEP_LISTS}
# a problem's step key -> the step a kind has for it
ALIASES = {"tele": "telescope", "telescope": "telescope", "extension": "extension", "second": "jib",
           "swing": "hook_block", "hoist": "hook_block", "jack": "outrigger", "track": "travel",
           "groups": "masses", "mass": "masses", "cog": "masses", "footprint": "masses"}


def step_index(setup_kind: str, key: str) -> int:
    """The step of a kind that fixes a problem with this key (-1: none)."""
    steps = STEP_LISTS.get(setup_kind, [])
    keys = [k for k, *_r in steps]
    for k in (key, ALIASES.get(key, "")):
        if k in keys:
            return keys.index(k)
    if setup_kind == "CRANE_OTHER" and key in ROLE_WORDS:
        return keys.index("joints")
    if key in ("knuckle",) and "jib" in keys:
        return keys.index("jib")
    return -1


# ---------------------------------------------------------------------------------------------------------------------
# what a step makes besides a plain joint

def principal(objs, axis=None) -> Vector | None:
    """The long direction of parts (their box corners), square to ``axis`` when given."""
    chunks = []
    for ob in parts_of(objs):
        me = ob.data
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        M = np.array(ob.matrix_world)
        chunks.append(co @ M[:3, :3].T + M[:3, 3])
    if not chunks:
        return None
    P = np.concatenate(chunks)
    if len(P) < 2:
        return None
    P -= P.mean(axis=0)
    if axis is not None:
        a = np.asarray(axis, float)
        P -= np.outer(P @ a, a)
    _u, _s, vt = np.linalg.svd(P, full_matrices=False)
    return Vector(vt[0].tolist()).normalized()


def boom_angle_of(scene, j) -> float:
    """The angle above level of the parts a turning joint moves, radians (their long side, pointing away from the
    pivot): a first value for "Boom angle in the model"."""
    o, axis = joints.axis_world(j)
    d = principal(joints.members(j), axis)
    if d is None:
        return 0.0
    if d.dot(centre(joints.members(j)) - Vector(o)) < 0.0:
        d = -d
    return math.asin(max(-1.0, min(1.0, d.z)))


def after_make(scene, role: str, j) -> None:
    """Values the steps measure once a joint is made: the boom's and the jib's angle in the model."""
    cs = settings(scene)
    if role == "luff":
        cs.boom_angle = boom_angle_of(scene, j)
    elif role in ("jib", "knuckle"):
        lj = first(scene, "luff")
        cs.second_angle = boom_angle_of(scene, j) - (boom_angle_of(scene, lj) if lj is not None else 0.0)


def _level_axes(ob, along=None) -> list:
    out = []
    for o, d, r, _p in _mesh_axes(ob):
        if r <= 0.0:
            continue
        if along is not None and abs(abs(d.dot(along)) - 1.0) > 1e-3:
            continue
        out.append((o, d, r))
    return out


def _nearest_on(o, d, p) -> Vector:
    return o + d * (p - o).dot(d)


def make_cylinder(scene, role: str, barrel: bpy.types.Object, rod: bpy.types.Object) -> str:
    """The cylinder that drives a role's joint (``cylinders.create``): each pin is the eye's round face parallel to
    the joint's axis at the far end of its part; the barrel's eye sits on the part the joint rides on, the rod's on
    the part it moves (or the other way round, when the rod's eye lies on the base)."""
    from . import cylinders
    j = first(scene, role)
    if j is None:
        raise RuntimeError(f"Make the {ROLE_WORDS[role].lower()} joint first")
    _o, axis = joints.axis_world(j)
    axis = Vector(axis)
    pins = []
    for ob in (barrel, rod):
        cand = [a for p in parts_of([ob]) for a in _level_axes(p, axis)]
        if not cand:
            raise RuntimeError(f"{name_of(ob)} has no eye (a round face parallel to the joint's axis)")
        c = centre([ob])
        far = max(cand, key=lambda a: (_nearest_on(a[0], a[1], c) - c).length)
        pins.append((_nearest_on(far[0], far[1], c), far[1]))
    moved = joints.members(j)[0]
    below = joints.rides_on(scene, j)
    base = joints.members(below)[0] if below is not None and joints.members(below) else build.logical_parent(moved)
    mc = centre([moved])
    if (pins[1][0] - mc).length > (pins[0][0] - mc).length:     # the rod's eye is on the base
        carriers = (moved, base)
    else:
        carriers = (base, moved)
    name = cylinders.unique_name(scene, f"{ROLE_WORDS[role]} cylinder") if hasattr(cylinders, "unique_name") \
        else f"{ROLE_WORDS[role]} cylinder"
    got = cylinders.create(scene, [barrel], [rod], (pins[0][0], pins[0][1], barrel), (pins[1][0], pins[1][1], rod),
                           barrel_carrier=carriers[0], rod_carrier=carriers[1], name=name)
    c = got[0] if isinstance(got, tuple) else got
    changed(scene)
    return c.name


def sheave_centre(scene, ob) -> Vector | None:
    """The head sheave's centre: its biggest level round face's axis, at the sheave's middle."""
    best = None
    for p in parts_of([ob]):
        for o, d, r in _level_axes(p):
            if abs(d.z) > 0.02:
                continue
            if best is None or r > best[2]:
                best = (o, d, r)
    if best is None:
        return None
    return _nearest_on(best[0], best[1], centre([ob]))


def set_hook_point(scene, block) -> None:
    """The hook point (model frame, m) found on the plumb line under the head sheave, in the CAD pose."""
    cs = settings(scene)
    root = model_root(scene)
    with joints.cad_pose(scene):
        p = find_hook_point(scene, block, Vector(cs.sheave))
        if p is None:
            mn, _mx = build.world_bounds(parts_of([block]))
            p = Vector((cs.sheave[0], cs.sheave[1], float(mn[2])))
        cs.hook_point = tuple((to_model(root, p) / 1000.0).tolist())
    cs.hook_set = True
    changed(scene)


def make_rope(scene) -> None:
    """The rope drawn in the CAD as a cable whose end stays on the hook block (4 Motion > Cables and paths)."""
    cs = settings(scene)
    if not cs.rope_part or not cs.hook_part:
        return
    from . import lifting, sheet
    m = sheet.Model(scene, {"joints": []}, root=model_root(scene))
    lifting._rope(scene, m, {"rig": {"cables": [{"name": "Hoist rope", "part": cs.rope_part,
                                                 "end_on": cs.hook_part}]}})


def _out_direction(scene, ob) -> Vector:
    """An outrigger beam's direction out: its longest level side, away from the crane's middle line."""
    size = size_of([ob])
    d = Vector((1.0, 0.0, 0.0)) if size[0] >= size[1] else Vector((0.0, 1.0, 0.0))
    c, m = centre([ob]), middle(scene)
    if Vector((c.x - m.x, c.y - m.y, 0.0)).dot(d) < 0.0:
        d = -d
    return d


def make_corner(scene, beams, jack, stroke: float, jack_stroke: float = 0.0) -> list:
    """An outrigger corner: one slide per beam stage (out, riding on the one before) and the jack (down). The first
    corner's first stage and its jack drive; every other stage and jack follows them with ratio 1."""
    cs = settings(scene)
    lead_beam = next((j for j in with_role(scene, "outrigger") if not j.follows), None)
    lead_jack = next((j for j in with_role(scene, "jack") if not j.follows), None)
    # names and numbers now: the joint list grows below (items held across that go stale)
    lead_name = lead_beam.name if lead_beam is not None else ""
    lead_jack_name = lead_jack.name if lead_jack is not None else ""
    made = []
    js = jack_stroke or cs.jack_stroke or (lead_jack.slide_max if lead_jack is not None else 0.0)
    st = stroke or (lead_beam.slide_max if lead_beam is not None else 0.0)
    for ob in beams:
        d = _out_direction(scene, ob)
        name = _role_name(scene, "outrigger") if not lead_name else joints.unique_name(scene, "Outrigger 2")
        j = make_joint(scene, "outrigger", [ob], centre([ob]), d, name=name, stroke=st)
        if lead_name:
            joints.set_follows(scene, joints.find(scene, j.name), lead_name, ratio=1.0)
        else:
            lead_name = j.name
        made.append(j.name)
    jname = _role_name(scene, "jack") if not lead_jack_name else joints.unique_name(scene, "Jack 2")
    j = make_joint(scene, "jack", [jack], centre([jack]), -UP, name=jname, stroke=js)
    if lead_jack_name:
        joints.set_follows(scene, joints.find(scene, j.name), lead_jack_name, ratio=1.0)
    made.append(j.name)
    return made


def make_track(scene, wheels, link, riders) -> str:
    """A crawler track round the wheels, driven by the travel joint (``tracks.add``); the wheels' joints it makes get
    the role "track"."""
    from . import tracks
    travel = first(scene, "travel")
    before = {j.name for j in scene.fresing.joints}
    n = len(scene.fresing.tracks)
    name = "Left track" if n == 0 else ("Right track" if n == 1 else f"Track {n + 1}")
    try:
        item = tracks.add(scene, list(wheels), link, list(riders), joint=travel.name, name=name)
    except tracks.TrackError as exc:
        raise RuntimeError(str(exc)) from exc
    item = scene.fresing.tracks.get(name) or item
    item["fr_crane"] = {"link": name_of(link), "riders": [name_of(r) for r in riders]}
    for j in scene.fresing.joints:
        if j.name not in before:
            j.role = "track"
    changed(scene)
    return name


# ---------------------------------------------------------------------------------------------------------------------
# Check

def run_check(scene, clash: bool = True) -> list:
    """Every check of the Check step; the problems go into the set-up's list (each with the step that fixes it)."""
    from ..core import lifting_setup as LS
    from . import lifting_rig_out
    cs = settings(scene)
    problems = []
    try:
        data = lifting_rig_out.build(scene)
    except RuntimeError as exc:
        problems.append(LS.Problem(getattr(exc, "step", "") or "model", str(exc), "red"))
        data = None
    if data is not None:
        problems += LS.check(data)
        problems += [LS.Problem(k, t, "red") for k, t in lifting_rig_out.scene_problems(scene)]
        e = chart_entry(scene)                    # a refused table is not in the file at all: say so here
        if e is not None and not e.ok:
            problems += [LS.Problem("chart", "Load chart refused: " + m, "red") for m in e.errors[:5]]
        if clash and not any(p.severity == "red" for p in problems):
            problems += clash_problems(scene, data)
    cs.problems.clear()
    for p in problems:
        it = cs.problems.add()
        it.text, it.step, it.severity = p.text, p.step or "", p.severity
    cs.checked = True
    return problems


def hook_parts(scene) -> set:
    """Names of the hook block's parts and the rope: they hang where the hoist puts them."""
    out = set()
    h = first(scene, "hoist")
    objs = list(joints.members(h)) if h is not None else []
    cs = settings(scene)
    for n in (cs.hook_part, cs.rope_part):
        if n:
            objs += objects_of(scene, n, many_ok=True)[0]
    for ob in objs:
        for o in [ob] + list(logic.descendants(ob)):
            out.update((o.name, name_of(o)))          # the clash rows name parts by their CAD names
    return out


def clash_problems(scene, data) -> list:
    """The clash check (6 Animation > Clash check) on the crane's own motion, built as a check animation that is
    taken away again: every saved pose of the crane in turn (everything counts), then every driven joint from its Min
    to its Max and back with the others at 0 – there the hook block hangs wherever the rope happens to be (fully up),
    so its rows are left out: where it hangs is the poses' business."""
    from ..core import lifting_setup as LS
    from . import animation, clash, states
    s = scene.fresing
    drive = [j for j in crane_joints(scene) if not j.follows and j.role not in ("swing", "track", "hoist")]
    own = {j.name for j in crane_joints(scene)}
    poses = [p.name for p in s.poses if any(pj.joint in own for pj in p.joints)]
    steps, t = [], 0.0
    hanging = hook_parts(scene)
    states.save_pose(scene, "FR crane check start")
    try:
        a = s.animations.add()
        a.name = "FR crane check"
        a.fps = "25"
        a.tail = 0.0
        for name in poses:
            b = a.blocks.add()
            b.kind, b.start, b.duration, b.easing = "POSE", t, 1.0, "LINEAR"
            b.name = b.pose = name
            steps.append((t, t + 1.0, "poses", True))
            t += 1.0
        for j in drive:
            lo, hi = joints.limits(j)
            if not j.use_limits or hi - lo <= 0:
                continue
            for to in (hi, lo, 0.0 if lo <= 0.0 <= hi else lo):
                b = a.blocks.add()
                b.kind, b.start, b.duration, b.easing = "JOINT", t, 1.0, "LINEAR"
                b.name, b.joint = f"{j.name} → {to:g}", j.name
                b.use_from = True
                if j.kind == "ROTATE":
                    b.to_angle = to
                else:
                    b.to_dist = to
                steps.append((t, t + 1.0, j.role, False))
                t += 1.0
        if not steps:
            return []
        s.animations_index = list(s.animations).index(a)
        animation.bake(scene, a)
        scene.frame_set(scene.frame_start)
        run = clash.check(scene)
        out, seen = [], set()
        fps = 25.0
        for r in run.rows:
            if r.kind != "CLASH":
                continue
            sec = (r.frame_from - scene.frame_start) / fps
            hit = next(((rl, is_pose) for t0, t1, rl, is_pose in steps if t0 <= sec <= t1), ("", False))
            role, is_pose = hit
            if not is_pose and (r.a in hanging or r.b in hanging):
                continue
            key = (r.a, r.b, role)
            if key in seen:
                continue
            seen.add(key)
            what = "in a pose" if is_pose else f"while {ROLE_WORDS.get(role, 'a joint').lower()} moves"
            out.append(LS.Problem(role or "check", f"{r.a} × {r.b} clash by {r.depth * 1000:.1f} mm {what}", "red"))
        return out
    finally:
        animation.clear_keys(scene)
        i = s.animations.find("FR crane check")
        if i >= 0:
            s.animations.remove(i)
        if s.poses.find("FR crane check start") >= 0:
            states.apply_pose(scene, "FR crane check start")
            s.poses.remove(s.poses.find("FR crane check start"))
