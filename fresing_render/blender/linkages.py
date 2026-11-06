"""Mechanisms: scissor lifts, four-bar and parallel arms, slider-cranks and other planar linkages (task 0014).

How a mechanism is built in Blender:

    base (the subassembly the mechanism stands on)
     ├─ joint frame └─ joint motion └─ the input link     a normal joint (rotate or slide): the *input*
     └─ mechanism frame   empty on the input pin; Z = the pins' direction (the plane's normal)
         ├─ link 1        empty: slides in X/Y and turns about Z of the frame; the link's subassemblies on it
         ├─ link 2 …

The owner moves the input joint (by hand, in a pose, in an animation step, through a coupling or a motor,
or with a cylinder in drive mode); the solver (``core.linkages``) places every other link, exactly, never
jumping to another assembly mode. In the 3D view that happens when the input changes (a depsgraph handler);
'Build animation' writes keys for every link on every frame the input moves, so playback, background renders
and files opened with Python scripts disabled need no add-on code.

What is stored: the links (subassemblies), the type, and the set-up worked out when the mechanism was added
(``setup``: pins, tracks and the input in the frame's own 2D coordinates, metres) plus where the solver is
(``solved_value``, ``signs``: the assembly mode of every two-answer step). The pins are found from the parts'
round faces (holes, shafts) shared by two links; a model update finds them again on the new revision.
"""

from __future__ import annotations

import json
import math

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import cylinders as CC
from ..core import linkages as K
from ..core.words import plural
from . import build, joints

KIND_FRAME, KIND_LINK = build.LINKAGE_KINDS
PROP = "fr_mechanism"
KINDS = (("SCISSOR", "Scissor lift"), ("FOURBAR", "Four-bar or parallel arm"),
         ("SLIDER", "Slider-crank"), ("OTHER", "Other linkage"))
_STATE = {"busy": False, "cad": 0}
_SOLVERS: dict = {}


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def mechanisms(scene):
    return scene.fresing.mechanisms


def find(scene, name: str):
    return scene.fresing.mechanisms.get(name)


def kind_label(kind: str) -> str:
    return dict(KINDS).get(kind, kind)


def label(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name)


def link_objs(link) -> list:
    return [r.obj for r in link.objs if r.obj is not None]


def members(m) -> list:
    """Every subassembly the mechanism moves itself (the input link moves with its joint)."""
    return [o for k, ln in enumerate(m.links) if k > 0 and ln.empty is not None for o in link_objs(ln)]


def all_link_objs(m) -> list:
    return [o for k, ln in enumerate(m.links) if k > 0 for o in link_objs(ln)]


def empties(m) -> list:
    return [ln.empty for ln in m.links if ln.empty is not None] + ([m.frame] if m.frame is not None else [])


def setup(m) -> dict:
    try:
        return json.loads(m.setup) if m.setup else {}
    except ValueError:
        return {}


def input_joint(scene, m):
    if m.joint_motion is None:
        return None
    for j in scene.fresing.joints:
        if j.motion is m.joint_motion:
            return j
    return None


def is_valid(m) -> bool:
    scene = m.id_data
    if m.frame is None or not m.setup or len(m.links) < 2:
        return False
    if any(ln.empty is not None and ln.empty.parent is not m.frame for ln in m.links):
        return False
    j = input_joint(scene, m)
    return j is not None and joints.is_valid(j)


def broken_reason(scene, m) -> str:
    if m.frame is None or any(ln.empty is not None and ln.empty.parent is not m.frame for ln in m.links):
        return "One of its markers was deleted: remove it and add it again"
    if input_joint(scene, m) is None:
        return "The joint that drives it was removed: remove the mechanism and add it again"
    return "Its set-up is incomplete: remove it and add it again"


def mechanism_of_object(scene, ob):
    """The mechanism that moves ``ob`` directly (one of its links, the input link included), or None."""
    for m in scene.fresing.mechanisms:
        for k, ln in enumerate(m.links):
            if k > 0 and any(o is ob for o in link_objs(ln)):
                return m
    return None


def mechanism_for_empty(scene, ob):
    if ob is None or ob.get(build.PROP_KIND) not in build.LINKAGE_KINDS:
        return None
    return find(scene, ob.get(PROP, ""))


def drives(scene, j):
    """The mechanism whose input is joint ``j``, or None."""
    if j is None or j.motion is None:
        return None
    for m in scene.fresing.mechanisms:
        if m.joint_motion is j.motion:
            return m
    return None


def unique_name(scene, base: str) -> str:
    names = {m.name for m in scene.fresing.mechanisms}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def _update() -> None:
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# geometry read from the parts
# ---------------------------------------------------------------------------

def _parts(ob, skip=()) -> list:
    """Mesh parts that move with ``ob`` as one piece: ``ob`` and its children, not through the empties of
    joints, cylinders or mechanisms (what hangs on those moves by itself), not into ``skip``."""
    out = []
    todo = [ob]
    skip_names = {o.name for o in skip}
    while todo:
        o = todo.pop()
        if o.name in skip_names:
            continue
        if o.type == "MESH" and o.get(build.PROP_KIND) == "part":
            out.append(o)
        for ch in o.children:
            if ch.get(build.PROP_KIND) in build.JOINT_KINDS:
                continue
            todo.append(ch)
    return out


def _axes(parts) -> list:
    """(origin, direction) of every round face's axis of ``parts``, world space."""
    out = []
    for ob in parts:
        me = ob.data
        if me is None or "fr_axes" not in me:
            continue
        a = me["fr_axes"]
        mw = ob.matrix_world
        rot = mw.to_3x3()
        for k in range(0, len(a) - 6, 7):
            d = rot @ Vector(a[k + 3:k + 6])
            if d.length < 1e-9:
                continue
            out.append((mw @ Vector(a[k:k + 3]), d.normalized()))
    return out


def _plane_frame(origin: Vector, normal: Vector) -> Matrix:
    n = normal.normalized()
    helper = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u = (helper - n * helper.dot(n)).normalized()
    if abs(n.z) < 0.9:                    # the frame's X along the floor where it can be: horizontal
        u = n.cross(Vector((0, 0, 1))).normalized()
        if u.length < 0.5:
            u = Vector((1, 0, 0))
    v = n.cross(u)
    m = Matrix.Identity(4)
    for r in range(3):
        m[r][0], m[r][1], m[r][2], m[r][3] = u[r], v[r], n[r], origin[r]
    return m


def _to2d(inv: Matrix, p: Vector) -> tuple:
    q = inv @ p
    return (float(q.x), float(q.y))


def _dedupe(points, tol) -> list:
    out = []
    for p in points:
        if not any(math.hypot(p[0] - q[0], p[1] - q[1]) <= tol for q in out):
            out.append(p)
    return out


def _points(axes, frame_inv: Matrix, n: Vector, tol: float) -> list:
    """2D points of the axes parallel to ``n``."""
    pts = [_to2d(frame_inv, o) for o, d in axes if CC.parallel(d, n)]
    return _dedupe(pts, tol)


def _inplane(axes, frame_inv: Matrix, n: Vector) -> list:
    """(2D point, 2D direction) of the axes at right angles to ``n`` (a piston's or a guide's)."""
    rot = frame_inv.to_3x3()
    out = []
    for o, d in axes:
        if abs(d.dot(n)) < math.sin(CC.PARALLEL_TOL):
            dd = rot @ d
            out.append((_to2d(frame_inv, o), (float(dd.x), float(dd.y))))
    return out


def _model_tol(scene) -> float:
    return max(2e-4, joints._model_size(scene) * 1e-4)


# ---------------------------------------------------------------------------
# set-up: links -> pins, tracks, input
# ---------------------------------------------------------------------------

def check_links(scene, links, base) -> str:
    """'' when these subassemblies can be the links of a mechanism on ``base``, else the reason."""
    from . import cylinders
    flat = [o for ln in links for o in ln]
    if not flat:
        return "Select the moving parts of the mechanism (each arm or link a subassembly), then press the button"
    seen = set()
    owner = {o.name: ln for ln in links for o in ln}
    for ob in flat:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            return f"{ob.name} is not part of the model"
        if build.logical_parent(ob) is None:
            return "The whole model cannot be a link: select the arms or links inside it"
        if ob.name in seen:
            return f"'{label(ob)}' is picked twice"
        seen.add(ob.name)
        if base is not None and (ob is base or joints._is_cad_ancestor(ob, base)):
            return f"'{label(ob)}' holds the base: it cannot be a moving link"
        other = mechanism_of_object(scene, ob)
        if other is not None:
            return f"'{label(ob)}' is already a link of mechanism '{other.name}'"
        j = joints.joint_of_object(scene, ob)
        if j is not None:
            # a joint that moves this one link (on the base) may become the drive joint; anything else may not
            if ({o.name for o in joints.members(j)} != {o.name for o in owner[ob.name]}
                    or joints.rides_on(scene, j) is not None):
                return (f"'{label(ob)}' moves with joint '{j.name}': remove that joint first (the mechanism makes "
                        "the joint it needs)")
            continue
        if cylinders.cylinder_of_object(scene, ob) is not None:
            return f"'{label(ob)}' is part of a cylinder: pick the arms the cylinder is pinned to"
        if ob.parent is not None and ob.parent.get(build.PROP_KIND) in build.JOINT_KINDS:
            return f"'{label(ob)}' already moves with something else (a joint or a cylinder)"
    for ob in flat:
        for other in flat:
            if other is not ob and joints._is_cad_ancestor(other, ob):
                return f"'{label(ob)}' is inside '{label(other)}': pick each link once, as one subassembly"
    if len(flat) < 2 and len(links) < 2:
        return "A mechanism has at least two moving links: select all of them"
    return ""


def default_base(objs):
    return build.logical_parent(objs[0])


def _layout(kind: str, names, points, inplane, tol: float, drive_link: int | None):
    """(names, groups, Linkage, height) for the links' 2D round-face points. ``groups[i]``: the merged link
    of picked link i (0 = the base: it cannot move)."""
    n = len(names)
    raw = K.find_pins(points, tol, chain=False)
    groups = K.rigid_groups(n, raw, tol)
    if any(g == 0 for g in groups[1:]):
        stuck = [names[i] for i in range(1, n) if groups[i] == 0]
        raise K.SetupError(f"{', '.join(stuck)} {'is' if len(stuck) == 1 else 'are'} pinned to the base at two "
                           "places, so it cannot move. Pick only the parts that move, and pick the base itself "
                           "with Base (parts like a cylinder are not part of the base)")
    mnames, pins = K.merge(names, raw, groups, tol)
    ng = len(mnames)
    mpoints = [[] for _ in range(ng)]
    minplane = [[] for _ in range(ng)]
    for i in range(n):
        mpoints[groups[i]] += points[i]
        minplane[groups[i]] += inplane[i]
    mpoints = [_dedupe(p, tol) for p in mpoints]
    slots, slides, height = [], [], None
    if kind == "SCISSOR":
        platform = K.scissor_platform(ng, pins, mpoints, tol)
        lay = K.scissor(ng, pins, mpoints, platform, tol)
        slots, height = lay.slots, lay.height
        inp = ("pin", lay.input_pin)
    else:
        # a link turning on one pin only and nothing else: a slider block on the base (slides, never turns)
        for g in range(1, ng):
            pts = _dedupe([c.p for c in pins if g in (c.a, c.b)], tol)
            if len(pts) != 1:
                continue
            p = pts[0]
            cand = sorted(minplane[g], key=lambda pd: abs(_cross2(pd[1], (p[0] - pd[0][0], p[1] - pd[0][1]))))
            if not cand:
                raise K.SetupError(f"'{mnames[g]}' hangs on one pin only and has no round face along its track "
                                   "(a piston or a guide bore): it cannot be placed")
            slides.append(K.Slide(g, 0, p, cand[0][1]))
        base_pins = [k for k, c in enumerate(pins) if 0 in (c.a, c.b)]
        if kind == "SLIDER" and len(slides) != 1:
            raise K.SetupError("A slider-crank needs a crank on the base, a rod, and a slider (a piston or block "
                               "pinned to the rod only)")
        if kind == "FOURBAR" and (ng != 4 or len(pins) != 4 or len(base_pins) != 2):
            raise K.SetupError(f"A four-bar has 3 moving links joined by 4 pins (2 of them on the base); found "
                               f"{plural(ng - 1, 'moving link')} and {plural(len(pins), 'pin')}"
                               f"{' (' + str(len(base_pins)) + ' on the base)' if len(pins) else ''}")
        if not base_pins and not slides:
            raise K.SetupError("No link turns on the base: no pin was found between a link and the base. Check the "
                               "base (it must have the holes the links turn in)")
        inp = None
        want = groups[drive_link] if drive_link is not None else None
        for k in base_pins:
            c = pins[k]
            g = c.b if c.a == 0 else c.a
            if want is None or g == want:
                inp = ("pin", k)
                break
        if inp is None and want is not None:
            for k, sl in enumerate(slides):
                if sl.link == want:
                    inp = ("slide", k)
        if inp is None:
            inp = ("pin", base_pins[0]) if base_pins else ("slide", 0)
    lk = K.Linkage(mnames, pins, slots, slides, inp)
    return mnames, groups, lk, height


def _cross2(a, b) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _find_plane(link_axes, all_axes_flat):
    """The pins' direction: of the round-face directions, the one that makes the most pins between links."""
    dirs = []
    for _o, d in all_axes_flat:
        for k, (dd, cnt) in enumerate(dirs):
            if CC.parallel(d, dd):
                dirs[k] = (dd, cnt + 1)
                break
        else:
            dirs.append((d, 1))
    dirs.sort(key=lambda x: -x[1])
    return [d for d, _c in dirs[:4]]


def _geometry(scene, links, base, flip: bool = False):
    """Everything the set-up needs, read in the CAD pose. Returns a dict. ``flip``: the plane seen from the
    other side (the input's positive direction the other way round)."""
    tol = _model_tol(scene)
    flat = [o for ln in links for o in ln]
    base_parts = _parts(base, skip=flat) if base is not None else []
    link_parts = [[p for o in ln for p in _parts(o)] for ln in links]
    axes = [_axes(base_parts)] + [_axes(ps) for ps in link_parts]
    flat_axes = [a for ax in axes[1:] for a in ax]
    if not flat_axes:
        raise RuntimeError("The picked parts have no round faces (holes, pins, shafts): the pins cannot be found")
    centre = sum((o for o, _d in flat_axes), Vector()) / len(flat_axes)
    best = None
    for n in _find_plane(axes, flat_axes):
        frame = _plane_frame(centre, n)
        inv = frame.inverted()
        pts = [_points(ax, inv, n, tol) for ax in axes]
        count = len(K.find_pins(pts, tol, chain=False))
        if best is None or count > best[0]:
            best = (count, n, frame, pts)
    _count, n, frame, pts = best
    if flip:
        n = -n
        frame = _plane_frame(centre, n)
        pts = [_points(ax, frame.inverted(), n, tol) for ax in axes]
    inv = frame.inverted()
    inplane = [_inplane(ax, inv, n) for ax in axes]
    names = ["base"] + [", ".join(label(o) for o in ln) for ln in links]
    return {"tol": tol, "normal": n, "frame": frame, "points": pts, "inplane": inplane, "names": names}


def _shift(lk: K.Linkage, height, origin):
    """The same mechanism with every point moved by -origin (the frame goes onto the input pin)."""
    def s(p):
        return (p[0] - origin[0], p[1] - origin[1])
    pins = [K.Pin(c.a, c.b, s(c.p)) for c in lk.pins]
    slots = [K.Slot(c.link, c.guide, s(c.p), c.d) for c in lk.slots]
    slides = [K.Slide(c.link, c.guide, s(c.p), c.d) for c in lk.slides]
    h = K.Height(height.i, s(height.a), s(height.ref), height.up) if height is not None else None
    return K.Linkage(lk.names, pins, slots, slides, lk.input), h


def _to_json(lk: K.Linkage, height, sign: int, kind: str) -> str:
    return json.dumps({
        "kind": kind, "names": lk.names,
        "pins": [[c.a, c.b, *c.p] for c in lk.pins],
        "slots": [[c.link, c.guide, *c.p, *c.d] for c in lk.slots],
        "slides": [[c.link, c.guide, *c.p, *c.d] for c in lk.slides],
        "input": list(lk.input), "sign": sign,
        "height": [height.i, *height.a, *height.ref, *height.up] if height is not None else None,
    })


def linkage_of(m):
    """(Linkage, Height or None, sign) from the stored set-up."""
    d = setup(m)
    lk = K.Linkage(d["names"], [K.Pin(a, b, (x, y)) for a, b, x, y in d["pins"]],
                   [K.Slot(a, b, (x, y), (u, v)) for a, b, x, y, u, v in d["slots"]],
                   [K.Slide(a, b, (x, y), (u, v)) for a, b, x, y, u, v in d["slides"]], tuple(d["input"]))
    h = d.get("height")
    height = K.Height(h[0], (h[1], h[2]), (h[3], h[4]), (h[5], h[6])) if h else None
    return lk, height, int(d.get("sign", 1))


def _input_axis_world(frame: Matrix, lk: K.Linkage, normal: Vector):
    kind, k = lk.input
    if kind == "pin":
        p = lk.pins[k].p
        return frame @ Vector((p[0], p[1], 0.0)), normal.copy(), "ROTATE"
    sl = lk.slides[k]
    d = frame.to_3x3() @ Vector((sl.d[0], sl.d[1], 0.0))
    return frame @ Vector((sl.p[0], sl.p[1], 0.0)), d.normalized(), "SLIDE"


def _reuse_joint(scene, objs, kind, origin, direction):
    """An existing joint that moves exactly ``objs`` about/along this axis: (joint, sign) or (None, 0)."""
    names = {o.name for o in objs}
    for j in scene.fresing.joints:
        if not joints.is_valid(j) or {o.name for o in joints.members(j)} != names or j.kind != kind:
            continue
        o, d = joints.axis_world(j)
        if not CC.parallel(d, direction):
            continue
        if kind == "ROTATE":
            off = (origin - o) - d * (origin - o).dot(d)
            if off.length > _model_tol(scene) * 5:
                continue
        return j, (1 if d.dot(direction) > 0 else -1)
    return None, 0


def create(scene, kind: str, links, base=None, name: str = "", drive=None, joint_name: str = ""):
    """New mechanism. ``links``: a list of links, each a list of subassemblies (one per selected object
    usually). ``drive``: a subassembly of the link the input joint should move (default: the first link that
    turns on the base). ``joint_name``: use this joint as the input (a model update). Returns the item."""
    links = [[o for o in ln if o is not None] for ln in links]
    links = [ln for ln in links if ln]
    flat = [o for ln in links for o in ln]
    if base is None and flat:
        base = default_base(flat)
    reason = check_links(scene, links, base)
    if reason:
        raise RuntimeError(reason)
    if base is None:
        raise RuntimeError("The mechanism needs a base to stand on")
    drive_link = None
    if drive is not None:
        for i, ln in enumerate(links):
            if any(o is drive or joints._is_cad_ancestor(o, drive) for o in ln):
                drive_link = i + 1
    s = scene.fresing
    name = unique_name(scene, name or f"{kind_label(kind)}")
    with joints.cad_pose(scene):
        geo = _geometry(scene, links, base)
        try:
            names, groups, lk, height = _layout(kind, geo["names"], geo["points"], geo["inplane"], geo["tol"],
                                                drive_link)
            if height is not None and _height_slope(lk, height) < 0:
                # a scissor lift goes up with a positive drive angle: look at the plane from the other side
                geo = _geometry(scene, links, base, flip=True)
                names, groups, lk, height = _layout(kind, geo["names"], geo["points"], geo["inplane"], geo["tol"],
                                                    drive_link)
        except K.SetupError as exc:
            raise RuntimeError(str(exc)) from exc
        kin, k = lk.input
        origin2d = lk.pins[k].p if kin == "pin" else lk.slides[k].p
        lk, height = _shift(lk, height, origin2d)
        frame_world = geo["frame"] @ Matrix.Translation(Vector((origin2d[0], origin2d[1], 0.0)))
        try:
            K.Solver(lk)
        except K.SetupError as exc:
            raise RuntimeError(str(exc)) from exc
        normal = geo["normal"]
        # the merged links: their subassemblies
        mlinks = [[] for _ in range(len(names))]
        for i, ln in enumerate(links):
            mlinks[groups[i + 1]] += ln
        in_objs = mlinks[lk.input_link]
        for g, objs in enumerate(mlinks):
            if g in (0, lk.input_link):
                continue
            for o in objs:
                oj = joints.joint_of_object(scene, o)
                if oj is not None:
                    raise RuntimeError(f"'{label(o)}' moves with joint '{oj.name}', but it is not the link that "
                                       "drives the mechanism: remove that joint first")
        origin, direction, jkind = _input_axis_world(frame_world, lk, normal)
        j = s.joints.get(joint_name) if joint_name else None
        sign = 1
        if j is not None:
            if {o.name for o in joints.members(j)} != {o.name for o in in_objs}:
                j = None
            else:
                _o, d = joints.axis_world(j)
                sign = 1 if d.dot(direction) > 0 else -1
        if j is None:
            j, sign = _reuse_joint(scene, in_objs, jkind, origin, direction)
        own = j is None
        if j is None:
            j = joints.create(scene, jkind, in_objs, origin, direction, name=joint_name or f"{name} drive",
                              base=base, stack=False)
            sign = 1
        jmotion = j.motion
        # the frame and one empty per link the mechanism moves itself
        size = joints._model_size(scene) * 0.05
        coll = base.users_collection[0] if base.users_collection else scene.collection
        frame = _new_empty(f"Mechanism {name}", KIND_FRAME, coll, size, "ARROWS", name)
        frame.parent = base
        frame.matrix_parent_inverse = Matrix.Identity(4)
        frame.matrix_basis = base.matrix_world.inverted() @ frame_world
        m = s.mechanisms.add()
        m["name"] = name
        m["_old_name"] = name
        m.kind = kind
        m.frame = frame
        m.base = base
        m.joint_motion = jmotion
        m.own_joint = own
        m.setup = _to_json(lk, height, sign, kind)
        m.solved_value = 0.0
        m.signs = ""
        for g, objs in enumerate(mlinks):
            ln = m.links.add()
            ln.name = names[g] if g else "base"
            if g == 0:
                ref = ln.objs.add()
                ref.obj = base
                continue
            for o in objs:
                ref = ln.objs.add()
                ref.obj = o
            if g == lk.input_link:
                continue
            e = _new_empty(f"Mechanism {name} ({names[g][:40]})", KIND_LINK, coll, size * 0.3, "PLAIN_AXES", name)
            e.parent = frame
            e.matrix_parent_inverse = Matrix.Identity(4)
            e.matrix_basis = Matrix.Identity(4)
            e.rotation_mode = "XYZ"
            try:
                e.hide_set(True)
            except RuntimeError:
                pass
            ln.empty = e
            for o in objs:
                joints._attach(o, e, frame_world)
        _update()
    if own and not joint_name:
        m["_limits_msg"] = _limits_from_reach(scene, m)
    s.mechanisms_index = len(s.mechanisms) - 1
    refresh(scene, m, force=True)
    _update()
    return m


def _height_slope(lk: K.Linkage, height) -> float:
    sol = K.Solver(lk)
    h0 = height.of(sol.poses)
    for v in (sol.step, -sol.step):
        try:
            s = sol.copy()
            s.solve(v)
            return (height.of(s.poses) - h0) / v
        except K.Unreachable:
            continue
    return 0.0


def reach(lk: K.Linkage, height=None) -> tuple[float, float]:
    """The input's range (solver terms) where the mechanism can be put together; for a scissor lift also with
    the platform above the base: from 2 % of its highest height up (flat arms are a dead position: the stages
    could fold either way)."""
    sol = K.Solver(lk)
    lo, hi = sol.limits()
    if height is None or math.isinf(lo) or math.isinf(hi):
        return lo, hi
    ends = {}
    for v in (lo, hi):
        s = sol.copy()
        s.solve(v)
        ends[v] = height.of(s.poses)
    top_v = max(ends, key=ends.get)
    low = 0.02 * ends[top_v]
    s = sol.copy()
    try:
        bottom = s.value_for(height, low, lo, hi)
    except K.Unreachable:
        bottom = lo if top_v == hi else hi
    return (bottom, hi) if top_v == hi else (lo, bottom)


def _new_empty(name, kind, collection, size, display, mech_name):
    ob = joints._new_empty(name, kind, collection, size, display)
    ob[PROP] = mech_name
    try:
        ob.hide_viewport = not bpy.context.scene.fresing.show_joints
    except Exception:
        pass
    return ob


def _limits_from_reach(scene, m) -> str:
    """The input joint stops where the mechanism can still be put together. Returns a message ('' none)."""
    j = input_joint(scene, m)
    if j is None:
        return ""
    lk, h, sign = linkage_of(m)
    try:
        lo, hi = reach(lk, h)
    except K.SetupError:
        return ""
    if math.isinf(lo) and math.isinf(hi):
        return ""                     # turns all the way round: leave the joint as it is
    margin = 1e-4 if j.kind == "ROTATE" else 1e-5
    lo, hi = sorted((sign * (lo + margin), sign * (hi - margin)))
    lo = max(lo, -math.radians(3600)) if j.kind == "ROTATE" else max(lo, -1000.0)
    hi = min(hi, math.radians(3600)) if j.kind == "ROTATE" else min(hi, 1000.0)
    if j.kind == "ROTATE":
        j["rot_min"], j["rot_max"] = lo, hi
    else:
        j["slide_min"], j["slide_max"] = lo, hi
    j["use_limits"] = True
    joints.apply_limits(j, joints._model_size(scene))
    unit = joints.unit_label(j.kind)
    return (f"'{j.name}' stops where the mechanism does: {joints.to_display(j.kind, lo):.1f}{unit} … "
            f"{joints.to_display(j.kind, hi):.1f}{unit}")


# ---------------------------------------------------------------------------
# solving and placing the links
# ---------------------------------------------------------------------------

def solver(m) -> K.Solver:
    """The solver of ``m``, at the position the mechanism is in (its stored state)."""
    key = (m.id_data.name, m.name)
    cached = _SOLVERS.get(key)
    if cached is None or cached[0] != m.setup:
        lk, _h, _s = linkage_of(m)
        cached = (m.setup, K.Solver(lk))
        _SOLVERS[key] = cached
    sol = cached[1]
    try:
        signs = json.loads(m.signs) if m.signs else list(sol.cad_signs)
    except ValueError:
        signs = list(sol.cad_signs)
    if abs(sol.value - m.solved_value) > 1e-12 or sol.signs != signs:
        sol.set_state(m.solved_value, signs)
    return sol


def forget() -> None:
    _SOLVERS.clear()


def _apply(m, poses) -> None:
    for k, ln in enumerate(m.links):
        e = ln.empty
        if e is None or k >= len(poses):
            continue
        th, tx, ty = poses[k]
        if abs(e.location.x - tx) > 1e-9 or abs(e.location.y - ty) > 1e-9 or abs(e.location.z) > 1e-9:
            e.location = (tx, ty, 0.0)
        if abs(e.rotation_euler.z - th) > 1e-9 or abs(e.rotation_euler.x) > 1e-9 or abs(e.rotation_euler.y) > 1e-9:
            e.rotation_euler = (0.0, 0.0, th)


def value_of(scene, m) -> float:
    """The input's value in the solver's terms (the joint's value with the sign of its axis)."""
    j = input_joint(scene, m)
    _lk, _h, sign = linkage_of(m)
    return sign * joints.get_value(j) if j is not None else 0.0


def refresh(scene, m, force: bool = False) -> str:
    """Place the links for the input joint's value now. Beyond reach the joint is put back at the last
    position the mechanism could take, and the reason is kept in ``m.status``. Returns that reason."""
    if not is_valid(m) or _STATE["cad"]:
        return ""
    j = input_joint(scene, m)
    lk, _h, sign = linkage_of(m)
    v = sign * joints.get_value(j)
    if not force and abs(v - m.solved_value) < 1e-10:
        return ""
    sol = solver(m)
    status = ""
    try:
        sol.solve(v)
    except K.Unreachable as exc:
        status = f"{exc}: it stops at the last position it can reach"
        joints.set_value(j, sign * sol.value, use_limits=False)
    _apply(m, sol.poses)
    m.solved_value = sol.value
    m.signs = json.dumps(sol.signs)
    if m.status != status:
        m.status = status
    return status


def _keyed(m) -> bool:
    return any(e.animation_data is not None and e.animation_data.action is not None
               for e in (ln.empty for ln in m.links) if e is not None)


def refresh_all(scene, force: bool = False) -> None:
    if _STATE["cad"]:
        return
    for m in list(scene.fresing.mechanisms):
        if is_valid(m) and not _keyed(m):
            refresh(scene, m, force=force)


@persistent
def _on_depsgraph(scene, _depsgraph=None):
    if _STATE["busy"] or _STATE["cad"] or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        if not scene.fresing.mechanisms:
            return
    except (AttributeError, ReferenceError):
        return
    _STATE["busy"] = True
    try:
        refresh_all(scene)
    except Exception as exc:                       # never break the app's update loop
        print("Fresing Render: mechanism update failed:", exc)
    finally:
        _STATE["busy"] = False


@persistent
def _on_load(_dummy=None):
    forget()


def register():
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.load_post, _on_load)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    for lst, fn in ((bpy.app.handlers.depsgraph_update_post, _on_depsgraph),
                    (bpy.app.handlers.load_post, _on_load)):
        while fn in lst:
            lst.remove(fn)
    forget()


# ---------------------------------------------------------------------------
# the CAD pose (joints.cad_pose): every link back on its CAD place, and back after
# ---------------------------------------------------------------------------

def cad_enter(scene) -> dict:
    _STATE["cad"] += 1
    saved = {}
    for m in scene.fresing.mechanisms:
        for ln in m.links:
            e = ln.empty
            if e is not None:
                saved[e.name] = (tuple(e.location), tuple(e.rotation_euler))
                e.location = (0.0, 0.0, 0.0)
                e.rotation_euler = (0.0, 0.0, 0.0)
    return saved


def cad_leave(scene, saved: dict) -> None:
    _STATE["cad"] = max(0, _STATE["cad"] - 1)
    for name, (loc, rot) in saved.items():
        e = bpy.data.objects.get(name)
        if e is not None:
            e.location = loc
            e.rotation_euler = rot


# ---------------------------------------------------------------------------
# other inputs: the platform's height, a cylinder's length
# ---------------------------------------------------------------------------

def has_height(m) -> bool:
    return bool(setup(m).get("height"))


def height_now(scene, m) -> float:
    _lk, h, _s = linkage_of(m)
    if h is None or not is_valid(m):
        return 0.0
    return h.of(solver(m).poses)


def joint_value_for_height(scene, m, height: float) -> tuple[float, str]:
    """(joint value, '' or the reason it stops short) for the platform at ``height`` (m)."""
    _lk, h, sign = linkage_of(m)
    if h is None:
        raise RuntimeError("This mechanism has no platform height")
    sol = solver(m).copy()
    j = input_joint(scene, m)
    lo, hi = joints.limits(j)
    lo, hi = sorted((sign * lo, sign * hi))
    try:
        v = sol.value_for(h, height, lo, hi)
        return sign * v, ""
    except K.Unreachable as exc:
        return sign * sol.value, str(exc)


def set_height(scene, m, height: float) -> str:
    v, reason = joint_value_for_height(scene, m, height)
    j = input_joint(scene, m)
    joints.set_value(j, v)
    refresh(scene, m)
    _update()
    return reason


def height_range(scene, m) -> tuple[float, float]:
    """Lowest and highest platform height within the input joint's limits."""
    lk, h, sign = linkage_of(m)
    j = input_joint(scene, m)
    if h is None or j is None:
        return (0.0, 0.0)
    lo, hi = joints.limits(j)
    out = []
    for v in (lo, hi):
        sol = solver(m).copy()
        try:
            sol.solve(sign * v)
        except K.Unreachable:
            pass
        out.append(h.of(sol.poses))
    return (min(out), max(out))


def _link_index_of(m, ob):
    """Which link ``ob`` moves with (0 = the base), or None when it is not part of the mechanism."""
    p = ob
    while p is not None:
        for k, ln in enumerate(m.links):
            if k == 0:
                continue
            if any(o is p for o in link_objs(ln)):
                return k
        if p is m.base:
            return 0
        p = build.logical_parent(p)
    return None


def link_of_point(scene, m, carrier):
    """(link index, link pose) of a cylinder pin's carrier part, or (None, None)."""
    k = _link_index_of(m, carrier)
    if k is None:
        return None, None
    return k, solver(m).poses[k]


class Drive:
    """A cylinder whose two pins sit on links of a mechanism: its length <-> the mechanism's input joint.
    Same use as ``core.cylinders.Drive`` (value_for, length_at, values_for_range), the values the joint's."""

    def __init__(self, scene, m, barrel_pin: Vector, barrel_carrier, rod_pin: Vector, rod_carrier):
        self.m_name = m.name
        lk, _h, self.sign = linkage_of(m)
        self.sol = solver(m).copy()
        inv = m.frame.matrix_world.inverted()
        pts = []
        for p, carrier in ((barrel_pin, barrel_carrier), (rod_pin, rod_carrier)):
            k = _link_index_of(m, carrier)
            if k is None:
                raise RuntimeError(f"'{label(carrier)}' is not part of mechanism '{m.name}'")
            q = _to2d(inv, p)
            th, tx, ty = self.sol.poses[k]
            # back to the link's CAD place
            x, y = q[0] - tx, q[1] - ty
            c, s = math.cos(-th), math.sin(-th)
            pts.append((k, (c * x - s * y, s * x + c * y)))
        if pts[0][0] == pts[1][0]:
            raise RuntimeError("Both pins of the cylinder are on the same link: it cannot move it")
        self.measure = K.Distance(pts[0][0], pts[0][1], pts[1][0], pts[1][1])
        j = input_joint(scene, m)
        lo, hi = joints.limits(j)
        self.lo, self.hi = sorted((self.sign * lo, self.sign * hi))

    def length_at(self, value: float) -> float:
        s = self.sol.copy()
        try:
            s.solve(self.sign * value)
        except K.Unreachable:
            pass
        return self.measure.of(s.poses)

    def value_for(self, length: float) -> float:
        try:
            v = self.sol.value_for(self.measure, length, self.lo, self.hi)
        except K.Unreachable:
            v = self.sol.value
        return self.sign * v

    def values_for_range(self, lo: float, hi: float) -> tuple[float, float]:
        keep = self.sol.copy()
        a = self.value_for(lo)
        self.sol = keep.copy()
        b = self.value_for(hi)
        self.sol = keep
        return (min(a, b), max(a, b))


def cylinder_mechanism(scene, c):
    """The mechanism a cylinder's pins sit on (either pin on one of its moving links), or None."""
    for m in scene.fresing.mechanisms:
        if not is_valid(m):
            continue
        ks = [_link_index_of(m, ob) for ob in (c.frame.parent, c.pin.parent) if ob is not None]
        if any(k is not None and k > 0 for k in ks) and all(k is not None for k in ks):
            return m
    return None


# ---------------------------------------------------------------------------
# conflicts with joints and cylinders
# ---------------------------------------------------------------------------

def joint_conflict(scene, objs, base, joint=None) -> str:
    """'' when a joint may move ``objs`` (sitting on ``base``) without breaking a mechanism, else the reason."""
    for m in scene.fresing.mechanisms:
        mj = input_joint(scene, m)
        if joint is not None and mj is not None and mj.name == joint.name:
            continue                              # the mechanism's own input joint
        for ob in objs:
            for o in all_link_objs(m):
                if ob is o or joints._is_cad_ancestor(ob, o):          # (a part inside a link may ride on it)
                    return (f"'{label(ob)}' is part of mechanism '{m.name}', which moves it. Move the mechanism with "
                            f"its drive joint '{mj.name if mj else '?'}'")
    return ""


# ---------------------------------------------------------------------------
# remove, rename, show
# ---------------------------------------------------------------------------

def _dissolve(scene, m, keep_joint: bool = True) -> None:
    """Take a mechanism apart, in the CAD pose (the caller is in it)."""
    s = scene.fresing
    for ob in members(m):
        joints._detach(ob)
    for e in empties(m):
        bpy.data.objects.remove(e, do_unlink=True)
    _SOLVERS.pop((scene.name, m.name), None)
    idx = next(i for i, x in enumerate(s.mechanisms) if x == m)
    s.mechanisms.remove(idx)
    s.mechanisms_index = max(0, min(s.mechanisms_index, len(s.mechanisms) - 1))


def remove(scene, m) -> str:
    """Remove the mechanism: its links go back to their CAD place. The drive joint goes too when the mechanism
    made it. Returns a message."""
    name = m.name
    j = input_joint(scene, m)
    own = bool(m.own_joint)
    jname = j.name if j is not None else ""
    with joints.cad_pose(scene):
        m = find(scene, name)
        _dissolve(scene, m)
    if own and j is not None:
        j = scene.fresing.joints.get(jname)
        if j is not None:
            joints.remove(scene, j)
        return f"Mechanism '{name}' removed; its parts are back in their place"
    return (f"Mechanism '{name}' removed; its parts are back in their place"
            + (f" ('{jname}' still moves its first link)" if jname else ""))


def rename(scene, m, old: str) -> None:
    for e in empties(m):
        e[PROP] = m.name
    cached = _SOLVERS.pop((scene.name, old), None)
    if cached is not None:
        _SOLVERS[(scene.name, m.name)] = cached
    for anim in scene.fresing.animations:
        for b in anim.blocks:
            if b.kind == "MECHANISM" and b.mechanism == old:
                b.mechanism = m.name


def show(scene, visible: bool) -> None:
    for m in scene.fresing.mechanisms:
        if m.frame is not None:
            m.frame.hide_viewport = not visible


# ---------------------------------------------------------------------------
# model updates: a mechanism as plain data
# ---------------------------------------------------------------------------

def to_spec(scene, m) -> dict:
    j = input_joint(scene, m)
    lk, _h, _s = linkage_of(m)

    def uids(objs):
        return [o.get(build.PROP_UID) for o in objs]
    return {
        "name": m.name, "kind": m.kind, "base": m.base.get(build.PROP_UID) if m.base is not None else None,
        "links": [uids(link_objs(ln)) for k, ln in enumerate(m.links) if k > 0],
        "input_link": lk.input_link - 1,
        "joint": j.name if j is not None else "", "own_joint": bool(m.own_joint),
    }


def _belongs(m, root) -> bool:
    if root is None:
        return True
    objs = all_link_objs(m) + ([m.base] if m.base is not None else [])
    return not objs or any(joints._root(o) is root for o in objs)


def before_model_update(scene, root=None) -> list[dict]:
    """The mechanisms of the model under ``root`` come apart (parts back in the CAD tree); their specs are
    returned to build them again on the new revision (after the joints)."""
    specs = []
    with joints.cad_pose(scene):
        for name in [m.name for m in scene.fresing.mechanisms]:
            m = find(scene, name)
            if not _belongs(m, root):
                continue
            specs.append(to_spec(scene, m) if is_valid(m) else {"name": name, "broken": True})
            _dissolve(scene, m)
    return specs


def rebuild_from_specs(scene, specs: list[dict], by_uid: dict) -> list[str]:
    notes = []
    for sp in specs:
        if sp.get("broken"):
            notes.append(f"Mechanism '{sp['name']}' was broken: it was removed, its parts are back in their place. "
                         "Add it again in 4 Motion > Mechanisms")
            continue
        links = [[o for o in (by_uid.get(u) for u in uids) if o is not None] for uids in sp["links"]]
        lost = sum(len(u) for u in sp["links"]) - sum(len(ln) for ln in links)
        if lost:
            notes.append(f"Mechanism '{sp['name']}': {plural(lost, 'part')} no longer in the model")
        base = by_uid.get(sp.get("base")) if sp.get("base") else None
        k = sp.get("input_link", 0)
        drive = links[k][0] if 0 <= k < len(links) and links[k] else None
        try:
            m = create(scene, sp["kind"], links, base=base, name=sp["name"], drive=drive,
                       joint_name=sp.get("joint", ""))
            m.own_joint = sp.get("own_joint", False)
        except RuntimeError as exc:
            notes.append(f"Mechanism '{sp['name']}' could not be rebuilt: {exc}")
    return notes
