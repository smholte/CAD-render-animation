"""People in the scene (task 0157): a person walks a path and does a list of things – Blender's side.

The maths is in ``core/people.py`` (paths, gaits, the schedule, the frames) and ``core/person_rig.py`` (the pose);
the armature in ``blender/person_rig.py``. Here:

* **People** are the person props of task 0155 (``fr_prop = PERSON``) with a rig. Their settings (``Object.
  fresing_person``) hold the path curve, the list of actions, a start delay and the item held at the start.
* **The path** is a poly curve "FR path <name>" in the collection "FR people" (Blender's own edit mode moves, inserts
  and deletes its points); the person's own place is point 0, the curve's points are 1, 2, … An overlay draws the line
  from the person to point 1 and the point numbers.
* **Items** ("FR item <kind>", ``fr_item`` = kind) lie on the floor or are carried: a Child Of "FR held <person> <hand>"
  on the person's hand bone per holder, plus "FR placed" (the vessel's rig when the deck moves); their influences and
  the item's place are keyed at Build.
* **Build** (``bake``, called by ``animation.bake`` after the drums): the plan (``plan``), a frame per frame of the
  animation (``Plan.sample``), keys on each person object (place, turn), its armature (bones, fingers) and the items.
  The surface below a foot comes from rays straight down (with the vessel at rest). The people's own time counts in
  the animation's length (``length``). Clear keys (``after_clear``) puts people and items back.
* **Preview** (``preview``): the people at a moment without building (the panel's slider).
* **Clash check**: a person that acts is checked as a body (its rest-pose mesh moved along its path, ``_clash_hook``);
  items are left out. Build warns when a path runs into a part (``check_paths``).
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import people as core
from ..core import person_rig as rigc
from ..core.words import plural
from . import person_rig

COLLECTION = "FR people"
ITEM_TAG = "fr_item"                # on an item: its kind
PATH_TAG = "fr_person_path"         # on a path curve: its person's name
HOME = "fr_home"                    # on a person / item while built or previewed: (x, y, z, turn about z) at rest
HELD = "FR held"                    # + " <person> <hand>": Child Of on a hand bone
PLACED = "FR placed"                # Child Of on the vessel's rig (deck moving) while lying somewhere
TAIL = 0.5                          # seconds after the last person has finished
_CACHE: dict = {"sig": None, "plan": None}
_DRAW = {"handle": None}


# =============================================================================
# what is in the scene
# =============================================================================


def _sur():
    from . import surroundings
    return surroundings


def people(scene) -> list:
    sur = _sur()
    return [ob for ob in sur.props(scene) if ob.get(sur.PROP_TAG) == "PERSON" and ob.name in scene.objects]


def acting(scene) -> list:
    """People with something to do (at least one action)."""
    return [ob for ob in people(scene) if len(ob.fresing_person.actions)]


def items(scene) -> list:
    return [ob for ob in scene.objects if ob.get(ITEM_TAG) in core.ITEMS]


def is_item(ob) -> bool:
    return ob is not None and ob.get(ITEM_TAG) in core.ITEMS


def is_person(ob) -> bool:
    return ob is not None and ob.get(_sur().PROP_TAG) == "PERSON"


def _collection(scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def home(ob) -> tuple:
    """(x, y, z, turn) where a person or item stands when nothing is built or previewed."""
    h = ob.get(HOME)
    if h is not None and len(h) == 4:
        return tuple(float(v) for v in h)
    return (ob.location.x, ob.location.y, ob.location.z, ob.rotation_euler.z)


def _keep_home(ob) -> None:
    if ob.get(HOME) is None:
        ob[HOME] = [ob.location.x, ob.location.y, ob.location.z, ob.rotation_euler.z]


def _back_home(ob) -> None:
    h = ob.get(HOME)
    if h is None:
        return
    ob.location = (h[0], h[1], h[2])
    ob.rotation_euler.z = h[3]
    del ob[HOME]


# =============================================================================
# adding people, paths and items
# =============================================================================


def add_person(scene, location=None, name: str = "", heading: float = 0.0, height: str = "1.75",
               outfit: str = "WORKSHOP"):
    """A person prop with a rig, standing at ``location`` (default: beside the machine)."""
    sur = _sur()
    ob = sur.add_prop(scene, "PERSON")
    if name:
        ob.name = name
    ps = ob.fresing_person
    ps.height_choice = height
    ps.outfit = outfit
    if location is not None:
        ob.location = Vector(location)
    ob.rotation_euler.z = heading
    person_rig.ensure(ob)
    return ob


def path_object(ob):
    p = ob.fresing_person.path
    return p if p is not None and p.name in bpy.data.objects and p.type == "CURVE" else None


def path_points(ob) -> list:
    """The clicked points of a person's path (world, at rest), in order."""
    p = path_object(ob)
    if p is None or not p.data.splines:
        return []
    sp = p.data.splines[0]
    M = p.matrix_world
    pts = sp.points if sp.type == "POLY" else sp.bezier_points
    return [tuple(M @ Vector(pt.co[:3])) for pt in pts]


def set_path(scene, ob, points) -> bpy.types.Object:
    """Give a person a path through ``points`` (world)."""
    p = path_object(ob)
    if p is None:
        cu = bpy.data.curves.new(f"FR path {ob.name}", "CURVE")
        cu.dimensions = "3D"
        p = bpy.data.objects.new(f"FR path {ob.name}", cu)
        _collection(scene).objects.link(p)
        p[PATH_TAG] = ob.name
        p.hide_render = True
        p.show_in_front = True
        ob.fresing_person.path = p
    cu = p.data
    cu.splines.clear()
    p.matrix_world = Matrix.Identity(4)
    pts = [tuple(v) for v in points]
    if pts:
        sp = cu.splines.new("POLY")
        sp.points.add(len(pts) - 1)
        for pt, v in zip(sp.points, pts):
            pt.co = (v[0], v[1], v[2] + 0.02, 1.0)
    forget()
    return p


def add_path_point(scene, ob, location) -> int:
    pts = path_points(ob)
    pts = [(x, y, z - 0.02) for x, y, z in pts]
    pts.append(tuple(location))
    set_path(scene, ob, pts)
    return len(pts)


def clear_path(ob) -> None:
    p = path_object(ob)
    if p is not None:
        data = p.data
        bpy.data.objects.remove(p)
        if data is not None and data.users == 0:
            bpy.data.curves.remove(data)
    ob.fresing_person.path = None
    forget()


def add_item(scene, kind: str, location=None, heading: float = 0.0):
    """An item lying on the floor (default: in front of the active person, else beside the machine)."""
    from . import surroundings as sur_b
    me = item_mesh(kind)
    ob = bpy.data.objects.new(f"FR item {core.ITEMS[kind].label}", me)
    _collection(scene).objects.link(ob)
    ob[ITEM_TAG] = kind
    ob.rotation_mode = "QUATERNION"
    if location is None:
        act = bpy.context.view_layer.objects.active if bpy.context.view_layer else None
        if is_person(act):
            h = act.rotation_euler.z
            f = core.facing(h)
            location = (act.location.x + f[0] * 0.6, act.location.y + f[1] * 0.6, act.location.z)
            heading = h
        else:
            from . import logic
            mn, mx = logic.cached_bounds(scene)
            location = (float(mx[0]) + 1.5, float(mn[1]) - 1.5, sur_b.floor_height(scene))
    ob.location = Vector(location)
    ob.rotation_quaternion = Matrix.Rotation(heading, 4, "Z").to_quaternion()
    return ob


def item_mesh(kind: str) -> bpy.types.Mesh:
    from . import surroundings as sur_b
    shapes = core.item_shapes(kind)
    keys = sorted({sh.mat for sh in shapes})
    index = {k: i for i, k in enumerate(keys)}
    m = sur_b._Mesh()
    for sh in shapes:
        m.shape(sh, index[sh.mat])
    me = m.to_mesh(f"FR item {core.ITEMS[kind].label}")
    for k in keys:
        me.materials.append(material(k))
    return me


_ITEM_LOOKS = {   # key: (sRGB colour, roughness, metallic)
    "item_red": ((0.72, 0.08, 0.06), 0.35, 0.0), "item_red_dark": ((0.5, 0.05, 0.04), 0.4, 0.0),
    "item_black": ((0.03, 0.03, 0.03), 0.55, 0.0), "item_steel": ((0.72, 0.73, 0.74), 0.32, 1.0),
    "item_board": ((0.45, 0.3, 0.17), 0.7, 0.0), "item_paper": ((0.93, 0.93, 0.9), 0.85, 0.0),
    "item_screen": ((0.02, 0.03, 0.05), 0.08, 0.0), "item_wood": ((0.6, 0.45, 0.28), 0.8, 0.0),
    "item_cable": ((0.05, 0.05, 0.06), 0.45, 0.0), "item_grey": ((0.45, 0.47, 0.5), 0.55, 0.0),
    "item_dark": ((0.12, 0.12, 0.13), 0.6, 0.0), "item_hose": ((0.04, 0.04, 0.04), 0.5, 0.0),
}


def material(key: str) -> bpy.types.Material:
    if key not in _ITEM_LOOKS:
        from . import props_scale
        return props_scale.material(key)
    name = "FR_item " + key
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    sur_b = _sur()
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    col, rough, metal = _ITEM_LOOKS[key]
    t = sur_b._NT(mat)
    co = sur_b._coords(t)
    n = sur_b._noise(t, 40.0, 3.0, 0.5, co)
    shader = sur_b._principled(t, sur_b._srgb(*col), sur_b._ramp(t, n, rough * 0.85, rough * 1.15), metal=metal,
                               normal=sur_b._bump(t, n, 0.03, 0.002))
    sur_b._output(t, shader, False, False)
    mat["fr_env"] = key
    return mat


def remove_person(scene, ob) -> None:
    clear_path(ob)
    arm = person_rig.rig_of(ob)
    for o in [arm, ob]:
        if o is None:
            continue
        data = o.data
        bpy.data.objects.remove(o)
        if data is not None and data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Armature):
                bpy.data.armatures.remove(data)
    forget()


# =============================================================================
# from the settings to the plan
# =============================================================================


def _target_of(a) -> tuple | None:
    if a.target_kind == "PART" and a.target_object is not None:
        ob = a.target_object
        corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        c = sum(corners, Vector()) / 8.0
        return (c.x, c.y, c.z)
    if a.target_kind == "POINT" and a.target_set:
        return tuple(a.target_point)
    return None


def action_spec(a) -> core.Action:
    other = ""
    if a.kind in core.NEEDS_OTHER or a.target_kind == "PERSON":
        other = a.other.name if a.other is not None else ""
    return core.Action(kind=a.kind, place=a.place, point=int(a.point), gait=a.gait, duration=float(a.duration),
                       other=other, target=_target_of(a) if a.kind not in core.NEEDS_OTHER else None,
                       item=a.item.name if a.item is not None else "",
                       wait_person=a.wait_person.name if a.wait_person is not None else "",
                       wait_step=int(a.wait_step))


def specs(scene) -> tuple:
    """(PersonSpec list, ItemSpec list) of the scene, at rest."""
    from . import props_scale
    out = []
    for ob in acting(scene):
        ps = ob.fresing_person
        x, y, z, h = home(ob)
        out.append(core.PersonSpec(
            name=ob.name, height=props_scale.person_settings(ob)["height"], place=(x, y, z), heading=h,
            path=tuple(path_points(ob)), actions=tuple(action_spec(a) for a in ps.actions), start=float(ps.start),
            carry=ps.carry.name if ps.carry is not None and is_item(ps.carry) else ""))
    its = []
    for ob in items(scene):
        x, y, z, _h = home(ob)
        its.append(core.ItemSpec(ob.name, ob[ITEM_TAG], (x, y, z), _item_heading(ob)))
    return out, its


def _item_heading(ob) -> float:
    q = ob.get(HOME + "_q")
    if q is not None:
        from mathutils import Quaternion
        return Quaternion(q).to_euler().z
    if ob.rotation_mode == "QUATERNION":
        return ob.rotation_quaternion.to_euler().z
    return ob.rotation_euler.z


def signature(scene) -> str:
    ps, its = specs(scene)
    return repr((ps, its, scene.render.fps))


class Ground:
    """The surface below a point: a ray straight down onto any shown mesh that is not a person, an item or a helper.
    Remembered per centimetre (the same spot is asked for at every frame)."""

    def __init__(self, scene):
        self.scene = scene
        self.dg = bpy.context.evaluated_depsgraph_get()
        self.floor = _sur().floor_height(scene)
        self.memo: dict = {}
        self.skip = {o.name for o in people(scene)} | {o.name for o in items(scene)}

    def __call__(self, x, y, z_near=None):
        top = (self.floor if z_near is None else float(z_near)) + 0.6
        key = (round(x, 2), round(y, 2), round(top, 1))
        hit = self.memo.get(key)
        if hit is not None:
            return hit
        z = self.floor
        o = Vector((x, y, top))
        d = Vector((0.0, 0.0, -1.0))
        for _ in range(8):
            ok, loc, _n, _i, ob, _m = self.scene.ray_cast(self.dg, o, d, distance=top - self.floor + 2.0)
            if not ok:
                break
            ob = getattr(ob, "original", ob)
            if ob.name in self.skip or ob.get(ITEM_TAG) or ob.get(PATH_TAG) or ob.hide_render:
                o = loc + d * 1e-3
                continue
            z = loc.z
            break
        self.memo[key] = z
        return z


def plan(scene, flat: bool = False) -> core.Plan:
    """The people's schedule. ``flat``: the floor as a plane (the times do not depend on the surface; for the panel
    and the animation's length), remembered until something changes."""
    ps, its = specs(scene)
    if flat:
        sig = repr((ps, its))
        if _CACHE["sig"] == sig and _CACHE["plan"] is not None:
            return _CACHE["plan"]
        pl = core.plan(ps, its, core.flat_ground(_sur().floor_height(scene)))
        _CACHE["sig"], _CACHE["plan"] = sig, pl
        return pl
    from . import vessel_motion
    with vessel_motion.at_rest(scene):
        g = Ground(scene)
        pl = core.plan(ps, its, g)
    pl.ground = g
    return pl


def length(scene) -> float:
    """How long the people act (seconds; 0 when nobody does anything). Part of the animation's length."""
    try:
        if not any(len(ob.fresing_person.actions) for ob in people(scene)):
            return 0.0
        pl = plan(scene, flat=True)
    except Exception as exc:                      # the length never breaks the panel or the Build
        print(f"Fresing Render: the people's time could not be worked out: {exc}")
        return 0.0
    return pl.length + TAIL if pl.length > 0 else 0.0


def forget() -> None:
    _CACHE["sig"], _CACHE["plan"] = None, None


# =============================================================================
# Build
# =============================================================================


def bake(scene, anim) -> list:
    """Keys for every person that acts and every item (Build). Returns warnings."""
    from . import animation
    end_preview(scene)
    actors = acting(scene)
    if not actors:
        return []
    warnings: list = []
    for ob in actors:
        person_rig.ensure(ob)
    for ob in actors + items(scene):
        _keep_home(ob)
    for ob in items(scene):
        if ob.get(HOME + "_q") is None:
            ob[HOME + "_q"] = list(ob.rotation_quaternion if ob.rotation_mode == "QUATERNION"
                                   else ob.rotation_euler.to_quaternion())
    scene.frame_set(1)
    pl = plan(scene)
    warnings += pl.warnings
    fps = animation.fps_of(anim)
    f_end = scene.frame_end
    need = int(math.floor(pl.length * fps + 1e-6)) + 1
    if need > f_end:
        scene.frame_end = need
        f_end = need
    frames = list(range(1, f_end + 1))
    rows = pl.sample(fps, (f_end - 1) / fps)
    for ob in actors:
        fr = rows[ob.name]
        person_rig.key_poses(ob, frames, [p for _r, p in fr], [r for r, _p in fr])
    _key_items(scene, pl, fps)
    warnings += check_paths(scene, pl, rows, fps)
    scene.frame_set(1)
    return warnings


def _vessel_target(ob):
    from . import vessel_motion
    con = ob.constraints.get(vessel_motion.CON)
    return con.target if con is not None and con.type == "CHILD_OF" else None


def _child_of(ob, name, target, subtarget=""):
    con = ob.constraints.get(name)
    if con is None:
        con = ob.constraints.new("CHILD_OF")
        con.name = name
        con.show_expanded = False
    con.set_inverse_pending = False
    con.target = target
    if subtarget:
        con.subtarget = subtarget
    con.inverse_matrix = Matrix.Identity(4)
    return con


def _drop_constraints(ob) -> None:
    for con in list(ob.constraints):
        if con.name.startswith(HELD) or con.name == PLACED:
            ob.constraints.remove(con)


def _basis_in_bone(state) -> Matrix:
    """A held item's own matrix under the Child Of of its hand bone (Blender's bone frame)."""
    C = rigc.C[f"{state.side}_hand"]
    G = np.asarray(state.grip, float)
    M = np.eye(4)
    M[:3, :3] = C.T @ G[:3, :3]
    M[:3, 3] = C.T @ G[:3, 3]
    return Matrix(M.tolist())


def _key_items(scene, pl: core.Plan, fps: float) -> None:
    from . import animation
    for name, states in pl.item_states.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        _drop_constraints(ob)
        ob.rotation_mode = "QUATERNION"
        holders = sorted({(s.person, s.side) for s in states if s.state == "HELD"})
        cons = {}
        for person, side in holders:
            pob = bpy.data.objects.get(person)
            arm = person_rig.rig_of(pob)
            if arm is None:
                continue
            cons[(person, side)] = _child_of(ob, f"{HELD} {person} {side}", arm, f"{side}_hand")
        vt = None
        for s in states:
            if s.state == "PLACED":
                continue
            pob = bpy.data.objects.get(s.person)
            vt = _vessel_target(pob) if pob is not None else None
            if vt is not None:
                break
        placed = _child_of(ob, PLACED, vt) if vt is not None else None
        cb = animation._channelbag(ob, "OBJECT")
        rows_loc = [[], [], []]
        rows_rot = [[], [], [], []]
        rows_inf = {key: [] for key in cons}
        rows_placed = []
        for s in states:
            f = 1.0 + s.t * fps
            if s.state == "HELD":
                M = _basis_in_bone(s)
            else:
                M = Matrix(np.asarray(s.world, float).tolist())
            loc, rot, _sc = M.decompose()
            for i in range(3):
                animation._merge(rows_loc[i], f, float(loc[i]), "CONSTANT")
            for i in range(4):
                animation._merge(rows_rot[i], f, float(rot[i]), "CONSTANT")
            for key in cons:
                on = s.state == "HELD" and (s.person, s.side) == key
                animation._merge(rows_inf[key], f, 1.0 if on else 0.0, "CONSTANT")
            animation._merge(rows_placed, f, 1.0 if s.state == "PLACED" else 0.0, "CONSTANT")
        for i in range(3):
            animation._write(cb, "location", i, rows_loc[i])
        for i in range(4):
            animation._write(cb, "rotation_quaternion", i, rows_rot[i])
        for key, con in cons.items():
            animation._write(cb, f'constraints["{bpy.utils.escape_identifier(con.name)}"].influence', 0,
                             rows_inf[key])
        if placed is not None:
            animation._write(cb, f'constraints["{PLACED}"].influence', 0, rows_placed)


def check_paths(scene, pl: core.Plan, rows: dict, fps: float) -> list:
    """Warnings for walks that run into a part (its place at the first frame): the person's body (a column 0.2 m
    round, from the knees to the head) must stay clear of every part."""
    from mathutils.bvhtree import BVHTree

    from . import build
    out = []
    parts = [ob for ob in build.iter_parts(scene) if ob.type == "MESH" and not ob.hide_render]
    if not parts:
        return out
    dg = bpy.context.evaluated_depsgraph_get()
    trees: dict = {}
    for name, person in pl.people.items():
        walks = [s for s in person.segs if s.kind in ("WALK", "TURN")]
        if not walks:
            continue
        k = person.fig.k
        samples = []
        for s in walks:
            n = max(2, int((s.t1 - s.t0) * 10))
            for i in range(n + 1):
                t = s.t0 + (s.t1 - s.t0) * i / n
                samples.append((t, person.root(t)))
        lo = np.min([[r[0], r[1], r[2]] for _t, r in samples], axis=0) - 0.5
        hi = np.max([[r[0], r[1], r[2]] for _t, r in samples], axis=0) + np.array((0.5, 0.5, 2.2))
        near = []
        for ob in parts:
            cs = np.array([tuple(ob.matrix_world @ Vector(c)) for c in ob.bound_box])
            if (cs.max(0) >= lo).all() and (cs.min(0) <= hi).all():
                near.append(ob)
        hit = None
        for t, r in samples:
            for ob in near:
                tree = trees.get(ob.name)
                if tree is None:
                    tree = trees[ob.name] = (BVHTree.FromObject(ob, dg), ob.matrix_world.inverted())
                bvh, inv = tree
                for hgt in (0.45, 1.0, 1.55):
                    p = inv @ Vector((r[0], r[1], r[2] + hgt * k))
                    loc, _n, _i, d = bvh.find_nearest(p, 0.2 * k)
                    if loc is not None:
                        hit = (t, ob)
                        break
                if hit:
                    break
            if hit:
                break
        if hit:
            from . import clash
            out.append(f"{name}'s path runs into '{clash.label(hit[1])}' about {hit[0]:.1f} s in: move the path's "
                       "points away from the machine (a person needs about 0.25 m on each side)")
    return out


# =============================================================================
# after Clear keys, the Preview slider, the rest state
# =============================================================================


def after_clear(scene) -> None:
    """Clear keys took the keys away: people and items back where they stand, in their panel pose."""
    for ob in people(scene) + items(scene):
        _back_home(ob)
    for ob in items(scene):
        q = ob.get(HOME + "_q")
        if q is not None:
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = q
            del ob[HOME + "_q"]
    rest_state(scene)


def rest_state(scene) -> None:
    """Nothing built or previewed: every rigged person in its panel pose, an item someone holds at the start in that
    hand, the others lying where they are."""
    from . import props_scale
    held = {}
    for ob in people(scene):
        arm = person_rig.rig_of(ob)
        if arm is None:
            continue
        fig = person_rig.figure(ob)
        person_rig.set_pose(ob, fig.from_angles(props_scale.person_settings(ob)["pose"]))
        c = ob.fresing_person.carry
        if c is not None and is_item(c):
            held[c.name] = ob
    for it in items(scene):
        _drop_constraints(it)
        pob = held.get(it.name)
        if pob is None:
            continue
        kind = it[ITEM_TAG]
        side = core.holding_hands(kind)[0]
        fig = person_rig.figure(pob)
        grip = core.inv4(core.hand_in_item(kind, side, fig.k))
        _child_of(it, f"{HELD} {pob.name} {side}", person_rig.rig_of(pob), f"{side}_hand")
        st = core.ItemState(0.0, "HELD", pob.name, side, grip)
        it.rotation_mode = "QUATERNION"
        _keep_home(it)
        if it.get(HOME + "_q") is None:
            it[HOME + "_q"] = list(it.rotation_quaternion)
        it.matrix_basis = _basis_in_bone(st)


def preview(scene, share: float) -> None:
    """Show the people ``share`` (0 … 1) of the way through their time, without keys."""
    if scene.fresing.anim_baked:
        return
    pl = plan(scene)
    if not pl.people:
        return
    t = share * pl.length
    for name, person in pl.people.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        _keep_home(ob)
        root, pose = pl.pose_at(name, t)
        ob.location = (root[0], root[1], root[2])
        ob.rotation_euler.z = root[3]
        person_rig.set_pose(ob, pose)
    for name, states in pl.item_states.items():
        it = bpy.data.objects.get(name)
        if it is None:
            continue
        cur = None
        for s in states:
            if s.t <= t + 1e-9:
                cur = s
        if cur is None:
            continue
        _keep_home(it)
        if it.get(HOME + "_q") is None:
            it[HOME + "_q"] = list(it.rotation_quaternion if it.rotation_mode == "QUATERNION"
                                   else it.rotation_euler.to_quaternion())
        _drop_constraints(it)
        it.rotation_mode = "QUATERNION"
        if cur.state == "HELD":
            pob = bpy.data.objects.get(cur.person)
            _child_of(it, f"{HELD} {cur.person} {cur.side}", person_rig.rig_of(pob), f"{cur.side}_hand")
            it.matrix_basis = _basis_in_bone(cur)
        else:
            it.matrix_basis = Matrix(np.asarray(cur.world, float).tolist())
    scene["fr_people_preview"] = 1


def end_preview(scene) -> None:
    if not scene.get("fr_people_preview"):
        return
    del scene["fr_people_preview"]
    for ob in people(scene) + items(scene):
        _back_home(ob)
    for ob in items(scene):
        q = ob.get(HOME + "_q")
        if q is not None:
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = q
            del ob[HOME + "_q"]
    s = scene.fresing
    if s.people_preview != 0.0:
        s["people_preview"] = 0.0
    rest_state(scene)


# =============================================================================
# the example: two people meet (the test tour, the PC check, the panel's Example button)
# =============================================================================

EXAMPLE = ("Anna", "Ben")


def set_up_example(scene):
    """Beside the machine: Anna walks in with a toolbox, stops by Ben, puts the box down, they shake hands and talk.
    Returns (Anna, Ben, the toolbox)."""
    from . import logic
    sur = _sur()
    mn, mx = logic.cached_bounds(scene)
    z = sur.floor_height(scene)
    x0 = float(mx[0]) + 1.6                       # a lane beside the machine's +x side, clear of it
    ymid = (float(mn[1]) + float(mx[1])) / 2
    ben = add_person(scene, (x0 + 0.8, ymid - 0.4, z), "Ben", heading=math.radians(90), height="1.85")
    anna = add_person(scene, (x0 + 0.3, ymid + 5.0, z), "Anna", heading=0.0, height="1.65",
                      outfit="OFFSHORE")
    box = add_item(scene, "TOOLBOX", (x0 + 1.6, ymid + 5.0, z), 0.0)
    set_path(scene, anna, [(x0 + 0.3, ymid + 2.2, z), (x0, ymid - 0.4, z)])
    a = anna.fresing_person
    a.carry = box
    _act(a, "WALK", place="END", gait="WALK")
    _act(a, "PUT_DOWN")
    _act(a, "GREET", other=ben)
    _act(a, "TALK", other=ben, duration=6.0)
    b = ben.fresing_person
    _act(b, "IDLE", duration=1.5)
    _act(b, "GREET", other=anna)
    _act(b, "TALK", other=anna, duration=6.0)
    rest_state(scene)
    forget()
    return anna, ben, box


def _act(ps, kind, **kw):
    a = ps.actions.add()
    a.kind = kind
    for k, v in kw.items():
        setattr(a, k, v)
    ps.actions_index = len(ps.actions) - 1
    return a


def check_example(scene) -> str:
    """What the tour and the PC check test on the built example: the order, the handshake together, feet on the
    floor without sliding, the box on the floor after Put down. Raises with a plain reason."""
    from . import animation
    anna, ben = (bpy.data.objects.get(n) for n in EXAMPLE)
    box = next((o for o in items(scene) if o[ITEM_TAG] == "TOOLBOX"), None)
    if anna is None or ben is None or box is None:
        raise RuntimeError("Anna, Ben or the toolbox is missing")
    if not scene.fresing.anim_baked:
        raise RuntimeError("the animation is not built")
    pl = plan(scene, flat=True)
    pa, pb = pl.people["Anna"], pl.people["Ben"]
    kinds = [s.kind for s in pa.segs]
    order = [k for k in kinds if k in ("WALK", "PUT_DOWN", "HANDSHAKE", "TALK")]
    if order != ["WALK", "PUT_DOWN", "HANDSHAKE", "TALK"]:
        raise RuntimeError(f"Anna does {', '.join(order).lower()} instead of walk, put down, greet, talk")
    ha = next(s for s in pa.segs if s.kind == "HANDSHAKE")
    hb = next((s for s in pb.segs if s.kind == "HANDSHAKE"), None)
    if hb is None or abs(ha.t0 - hb.t0) > 1e-3:
        raise RuntimeError("Anna and Ben do not shake hands at the same moment")
    fps = animation.fps_of(animation.active(scene))
    # feet on the floor and not sliding (read from the built keys of the armature)
    worst_slide, worst_float = 0.0, 0.0
    floor = _sur().floor_height(scene)
    for ob, person in ((anna, pa), (ben, pb)):
        for side in ("l", "r"):
            for plant in person.feet[side].plants:
                a = max(plant.down + plant.roll_in, 0.0) + 0.04
                b = min(plant.up - plant.roll_out, pl.length) - 0.04
                if b - a < 0.08:
                    continue
                pts = []
                for t in (a, (a + b) / 2, b):
                    scene.frame_set(int(t * fps) + 1, subframe=(t * fps) % 1.0)
                    m = person_rig.bone_world(ob, f"{side}_foot")
                    pts.append(m.translation.copy())
                worst_slide = max(worst_slide, max((p - pts[0]).length for p in pts))
                worst_float = max(worst_float, abs(pts[0].z - (floor + 0.085 * person.fig.k)))
    if worst_slide > 0.005:
        raise RuntimeError(f"a foot slides {worst_slide * 1000:.0f} mm while it stands")
    if worst_float > 0.01:
        raise RuntimeError(f"a standing foot is {worst_float * 1000:.0f} mm off the floor")
    put = next(s for s in pa.segs if s.kind == "PUT_DOWN")
    scene.frame_set(int(put.t1 * fps) + 3)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = box.evaluated_get(dg)
    co = np.zeros(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    low = float((np.asarray(box.matrix_world) @ np.c_[co.reshape(-1, 3), np.ones(len(co) // 3)].T)[2].min())
    if abs(low - floor) > 0.01:
        raise RuntimeError(f"the toolbox is {1000 * (low - floor):.0f} mm off the floor after Put down")
    scene.frame_set(1)
    walk = next(s for s in pa.segs if s.kind == "WALK")
    return (f"Anna walks {walk.t1 - walk.t0:.1f} s, puts the box down, they shake hands at {ha.t0:.1f} s and talk; "
            f"feet slide ≤ {worst_slide * 1000:.1f} mm")


# =============================================================================
# the clash check, the overlay, handlers
# =============================================================================


def _clash_hook(scene):
    """People that act are checked as bodies (their rest-pose mesh moved along their paths); items are left out."""
    return [ob for ob in acting(scene) if ob.type == "MESH"], items(scene)


def _draw_paths():
    """The selected person's path in the view: a line from the person to point 1, numbers at the points."""
    ctx = bpy.context
    scene = ctx.scene
    if scene is None:
        return
    ob = ctx.view_layer.objects.active if ctx.view_layer else None
    if not is_person(ob) or path_object(ob) is None:
        return
    region, rv3d = ctx.region, ctx.region_data
    if region is None or rv3d is None:
        return
    import blf
    import gpu
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from gpu_extras.batch import batch_for_shader
    pts = [tuple(home(ob)[:3])] + [tuple(p) for p in path_points(ob)]
    screen = [location_3d_to_region_2d(region, rv3d, Vector(p)) for p in pts]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    line = [tuple(s) for s in screen[:2] if s is not None]
    if len(line) == 2:
        batch = batch_for_shader(shader, "LINES", {"pos": line})
        shader.uniform_float("color", (1.0, 0.75, 0.1, 0.9))
        gpu.state.line_width_set(2.0)
        batch.draw(shader)
        gpu.state.line_width_set(1.0)
    font = 0
    blf.size(font, 15)
    for i, s in enumerate(screen):
        if s is None:
            continue
        blf.color(font, 1.0, 0.85, 0.2, 1.0)
        blf.position(font, s.x + 6, s.y + 6, 0)
        blf.draw(font, str(i) if i else f"0 {ob.name}")


@persistent
def _on_load(_dummy=None):
    forget()


def register() -> None:
    from . import clash
    if _clash_hook not in clash.HOOKS:
        clash.HOOKS.append(_clash_hook)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    if _DRAW["handle"] is None and not bpy.app.background:
        try:
            _DRAW["handle"] = bpy.types.SpaceView3D.draw_handler_add(_draw_paths, (), "WINDOW", "POST_PIXEL")
        except Exception:
            _DRAW["handle"] = None


def unregister() -> None:
    from . import clash
    while _clash_hook in clash.HOOKS:
        clash.HOOKS.remove(_clash_hook)
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if _DRAW["handle"] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW["handle"], "WINDOW")
        except Exception:
            pass
        _DRAW["handle"] = None
    forget()


def words(scene) -> str:
    """The panel header's state: '2 people · 18 s'."""
    n = len(people(scene))
    if not n:
        return ""
    secs = length(scene)
    return f"{plural(n, 'person', 'people')} · {secs:.0f} s" if secs else plural(n, "person", "people")
