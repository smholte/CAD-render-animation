"""Moving and turning models, subassemblies and parts in the 3D view (task 0307; the Place lane – task 0292 adds the
fields, the gizmo and Remove here).

Blender's own G / R / S move, turn and scale what is selected. In this app they did nothing for the owner: the numbers
showed in the header while moving, and on a click or Enter the part was back. The causes (task 0307's report):

* **Locked in place.** An import locks every subassembly and part (``logic.lock_all``: ``lock_location`` /
  ``lock_rotation`` / ``lock_scale``), so a subassembly moves only with the one it is in. Blender's G then runs, shows
  its numbers and moves nothing – silently. Unlocking (2 Structure > Locked in place, or the right-click menu's
  **Unlock so it can move**) lets G / R move it, and the move stays.
* **A built animation.** Build & play saves how things stood and puts that back at the next Build and at Stop: a
  move made while an animation is built is undone later, without a word.
* **Scale.** Parts keep their CAD size (``lock_scale`` is always on): S never scales them.
* **The Client view** locks everything (``lock.py``): nothing can be selected, so G / R have nothing to move; the
  key stays off its allow-list (it is no viewing operator).

So the app's own key (``fresing.move_key`` on G / R / S in Object Mode, ``lock.APP_KEYS``) looks at what would move
before Blender does: when nothing of it can move, it says why in the status bar at once and Blender's G is not
started; otherwise it passes the key on to Blender (``PASS_THROUGH``), unchanged.

**Place (task 0292)** – 2 Structure > Place, the right-click menu's Move / turn…, the arrows and rings: X / Y / Z and
turns typed or stepped, moved and turned with the mouse, Put on the floor, Back to the CAD place. The rules:

* **Three places of a subassembly or part.** Its *file place* (where the STEP file has it, ``fr_file_basis`` once it
  was placed – before that its CAD place is the file place), its *CAD place* (``fr_cad_basis``: where the app treats
  it as standing in the model) and a *free move* on top (G / R by hand, exploded views: ``fr_rest_basis`` vs the
  object's own matrix). **Place moves the CAD place** – as if the CAD file had it there: Build, poses, saved scenes,
  Reset pose and a model update keep it. A free move made with G / R stays what it was (a pose's or exploded view's
  move, taken off by Reset pose). Back to the CAD place puts the file place back (and takes the free move off).
* **A model** is placed by its root: the whole model moves – joints, cylinders, mechanisms, hoses, cables, labels and
  cameras riding on its parts. Its import place (``fr_rest_basis`` of the root, with the import's Up axis) is what
  Back to where it was imported puts back.
* **A subassembly that a joint moves** (it is the joint's member): when the move takes *everything* the joint moves,
  the joint's axis goes with it (its frame moves; the frame's place before is kept on the joint's motion empty,
  ``FRAME_FROM``, so Back to the CAD place puts both back). When the joint moves other parts too, only the chosen
  ones move and the axis stays where it is.
* **Locked in place** refuses Place as it refuses G (unlock it: the lock beside the name, or in the tree row).
* **A built animation** is taken off first ("Build again"); **the Client view** refuses (it is locked).

The matrix algebra keeps one rule of joints.py true: for a part a joint carries, ``cad @ rest⁻¹`` is the fixed
relation between its CAD parent and the joint's motion in the CAD pose. A move in the part's parent's coordinates
(``L``) changes rest and CAD place together; when a joint's frame moves, the CAD places are worked out again in the
CAD pose (``_rederive``).
"""

from __future__ import annotations

import json
import math

import bpy
import numpy as np
from bpy.props import EnumProperty
from mathutils import Euler, Matrix, Vector

from ..core import place as core
from . import build

MODES = (("TRANSLATE", "Move", "G: move"), ("ROTATE", "Turn", "R: turn"), ("RESIZE", "Scale", "S: scale"))
LAST = [""]                 # the last message (tests, the PC check)
STOPPED = [0]               # keys that did not start Blender's move (tests, the PC check)


def _name(ob) -> str:
    return ob.get(build.PROP_NAME) or ob.name


def movers(context) -> list:
    """What Blender's G / R would move: the selected model objects without a selected object above them (Blender
    moves a selected child with its selected parent, not on its own)."""
    sel = [o for o in context.selected_objects]
    chosen = set(o.name for o in sel)
    out = []
    for ob in sel:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            continue
        p = ob.parent
        while p is not None and p.name not in chosen:
            p = p.parent
        if p is None:
            out.append(ob)
    return out


def lock_owner(ob):
    """The subassembly whose lock holds ``ob``: itself when it is one, else the nearest one above it."""
    p = ob
    while p is not None and p.get(build.PROP_KIND) != "assembly":
        p = build.logical_parent(p)
    return p


def _locked(ob, mode: str) -> bool:
    lk = {"TRANSLATE": ob.lock_location, "ROTATE": ob.lock_rotation, "RESIZE": ob.lock_scale}[mode]
    return all(lk)


def why_not(context, mode: str) -> tuple:
    """(message, how many of the movers cannot move) – ("", 0) when Blender's key may run as it is."""
    from ..core import places
    from . import animation
    scene = context.scene
    obs = movers(context)
    if not obs:
        return "", 0
    if animation.has_keys(scene):
        what = {"TRANSLATE": "move", "ROTATE": "turn", "RESIZE": "scale"}[mode]
        return (f"The animation is built: a {what} now would be undone at the next Build. Stop it first "
                f"({places.where('motion')} > Stop it to move joints by hand), then press the key again"), len(obs)
    held = [o for o in obs if _locked(o, mode)]
    if not held:
        return "", 0
    if mode == "RESIZE":
        return "Parts keep their size from the CAD model: S does not scale them", len(held)
    owner = lock_owner(held[0]) or held[0]
    return (f"'{_name(owner)}' is locked in place – right-click it > Unlock so it can move (or "
            f"{places.where('structure')} > Locked in place), then press the key again"), len(held)


class FRESING_OT_move_key(bpy.types.Operator):
    """G / R / S in the 3D view: move, turn or scale what is selected, as in Blender. When it cannot move (locked in
    place, or an animation is built that would undo the move), the status bar says why at once, and what to do"""

    bl_idname = "fresing.move_key"
    bl_label = "Move / turn"
    bl_options = {"INTERNAL"}

    mode: EnumProperty(items=MODES, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        scene = getattr(context, "scene", None)
        return (context.mode == "OBJECT" and scene is not None and getattr(scene, "fresing", None) is not None
                and context.area is not None and context.area.type == "VIEW_3D")

    def _check(self, context):
        msg, n = why_not(context, self.mode)
        if not msg:
            return {"PASS_THROUGH"}
        LAST[0] = msg
        self.report({"WARNING"}, msg)
        if n < len(movers(context)):                 # some of it can move: Blender moves those
            return {"PASS_THROUGH"}
        STOPPED[0] += 1
        return {"CANCELLED"}

    def invoke(self, context, event):
        return self._check(context)

    def execute(self, context):                      # scripts and tests: the check alone
        res = self._check(context)
        return {"FINISHED"} if res == {"PASS_THROUGH"} else res


class FRESING_OT_ctx_unlock(bpy.types.Operator):
    """Unlocks the subassembly you right-clicked, so G moves it and R turns it (it stays where you put it); click again
    to lock it in place. Locked, it moves only with the subassembly it is in. Same as 2 Structure > Locked in place"""

    bl_idname = "fresing.ctx_unlock"
    bl_label = "Unlock so it can move"
    bl_options = {"REGISTER", "UNDO"}

    part: bpy.props.StringProperty(options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        from . import logic
        ob = bpy.data.objects.get(self.part) if self.part else None
        owner = lock_owner(ob) if ob is not None else None
        if owner is None or owner.name not in context.scene.objects:
            self.report({"WARNING"}, "Right-click a part in the 3D view first")
            return {"CANCELLED"}
        locked = not owner.get(build.PROP_LOCKED, True)
        logic.set_locked(owner, locked)
        self.report({"INFO"}, f"'{_name(owner)}' is " + ("locked in place" if locked
                                                         else "unlocked: G moves it, R turns it"))
        return {"FINISHED"}


def menu_text(ob) -> str:
    """The right-click menu's entry for the lock of ``ob``'s subassembly."""
    owner = lock_owner(ob) if ob is not None else None
    if owner is not None and not owner.get(build.PROP_LOCKED, True):
        return "Lock in place"
    return "Unlock so it can move"

# ===========================================================================
# Place (task 0292)
# ===========================================================================

FILE = "fr_file_basis"             # a placed subassembly / part: its CAD place in the STEP file (16 floats)
FRAME_FROM = "fr_place_frame"      # on a joint's motion empty: its frame's place before Place moved it (JSON)
NOTE = [""]                        # the last Place / Remove message (tests, the PC check)


def is_root(ob) -> bool:
    return bool(ob.get(build.PROP_ROOT))


def target(context):
    """The one thing Place's fields show: the active object when it is one of what would move, else the first."""
    obs = movers(context)
    if not obs:
        return None
    act = getattr(context, "active_object", None)
    return act if act is not None and act in obs else obs[0]


def locked(ob) -> bool:
    """Locked in place (as G sees it): its place and its turn are both locked."""
    return all(ob.lock_location) and all(ob.lock_rotation)


def refused(context, objs=None) -> str:
    """Why Place cannot move what is chosen now ('' when it can)."""
    from . import lock
    if lock.ON[0]:
        return lock.MESSAGE
    objs = movers(context) if objs is None else objs
    if not objs:
        return "Select a model, subassembly or part first: click it in the view or a row of 2 Structure"
    held = [o for o in objs if locked(o)]
    if held:
        owner = held[0]
        return (f"'{_name(owner)}' is locked in place – click the lock beside its name (or in its 2 Structure row) "
                "so it can move")
    return ""


def _pw(ob) -> Matrix:
    """The world matrix of what ``ob``'s own matrix is relative to."""
    if ob.parent is None:
        return Matrix.Identity(4)
    return ob.parent.matrix_world @ ob.matrix_parent_inverse


def _member(ob) -> bool:
    """True when a joint carries ``ob`` (it is a joint's member: its CAD parent is remembered)."""
    return isinstance(ob.get(build.PROP_CAD_PARENT), bpy.types.Object)


def file_basis(ob) -> Matrix:
    m = build.get_mat(ob, FILE)
    return m if m is not None else build.cad_basis(ob)


def is_placed(ob) -> bool:
    """Moved by Place away from where the STEP file has it (a model: away from where it was imported)."""
    if is_root(ob):
        from . import joints
        return not joints._same(ob.matrix_basis, build.rest_basis(ob))
    if build.get_mat(ob, FILE) is not None:
        return True
    return _frame_moved(bpy.context.scene, ob) is not None


def _remember_file(ob) -> None:
    if FILE not in ob:
        build.set_mat(ob, FILE, build.cad_basis(ob))


def _frame_moved(scene, ob):
    """The joint whose frame Place moved together with ``ob`` (``ob`` one of its members), or None."""
    from . import joints
    j = joints.joint_of_object(scene, ob) if scene is not None else None
    if j is not None and j.motion is not None and FRAME_FROM in j.motion:
        return j
    return None


def _follow_joints(scene, objs) -> dict:
    """{joint name: joint} of the joints whose axis goes with this move: everything they move is chosen."""
    from . import joints
    names = {o.name for o in objs}
    out = {}
    for ob in objs:
        j = joints.joint_of_object(scene, ob)
        if j is None or j.frame is None or j.name in out:
            continue
        mem = joints.members(j)
        if mem and all(m.name in names for m in mem):
            out[j.name] = j
    return out


def _under(ob, empties) -> bool:
    p = ob.parent
    while p is not None:
        if p in empties:
            return True
        p = p.parent
    return False


def _take_build_off(scene) -> bool:
    from . import animation
    if animation.has_keys(scene):
        animation.clear_keys(scene)
        return True
    return False


def _rederive(scene, before: dict | None = None) -> int:
    """A joint's frame moved: work the CAD places out again in the CAD pose (``cad = CAD parent⁻¹ @ world`` for
    every part a joint carries). A part whose CAD place changes keeps its file place first. Returns how many."""
    from . import joints
    n = 0
    with joints.cad_pose(scene):
        bpy.context.view_layer.update()
        for ob in scene.objects:
            cp = ob.get(build.PROP_CAD_PARENT)
            if not isinstance(cp, bpy.types.Object) or ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
                continue
            new = cp.matrix_world.inverted() @ ob.matrix_world
            old = build.cad_basis(ob)
            if joints._same(new, old):
                continue
            if FILE not in ob:
                build.set_mat(ob, FILE, old)
            build.set_mat(ob, build.PROP_CAD_BASIS, new)
            n += 1
    return n


def _tidy_file(ob) -> None:
    """A part back on its file place forgets it was placed."""
    from . import joints
    m = build.get_mat(ob, FILE)
    if m is not None and joints._same(m, build.cad_basis(ob)):
        del ob[FILE]


def _move_one(ob, D: Matrix) -> None:
    """Move one subassembly or part by the world matrix ``D`` (the current pose): its CAD place and rest place
    together, a free move on top kept as it was."""
    P = _pw(ob)
    L = P.inverted() @ D @ P
    rest, cad, basis = build.rest_basis(ob), build.cad_basis(ob), ob.matrix_basis.copy()
    try:
        free = rest.inverted() @ basis
    except ValueError:
        free = Matrix.Identity(4)
    _remember_file(ob)
    rest2 = L @ rest
    if _member(ob):
        cad2 = cad @ rest.inverted() @ rest2
    else:
        cad2 = L @ cad
    build.set_mat(ob, build.PROP_REST_BASIS, rest2)
    build.set_mat(ob, build.PROP_CAD_BASIS, cad2)
    ob.matrix_basis = rest2 @ free
    _tidy_file(ob)


def _elsewhere_children(scene, objs) -> bool:
    """A part whose CAD parent is one of these (or below one) but which a joint outside carries: its CAD place must
    be worked out again."""
    from . import logic
    names = {o.name for o in objs}
    tree = logic.Tree(scene)
    inside = set(names)
    for o in objs:
        inside.update(d.name for d in tree.descendants(o))
    for ob in scene.objects:
        cp = ob.get(build.PROP_CAD_PARENT)
        if isinstance(cp, bpy.types.Object) and cp.name in inside:
            p, moved = ob.parent, False
            while p is not None:
                if p.name in names:
                    moved = True
                    break
                p = p.parent
            if not moved:
                return True
    return False


def move(scene, objs, D: Matrix) -> str:
    """Move models, subassemblies or parts by the world matrix ``D`` (as they stand now). Returns a note ('' or
    "Build again" …). The rules: the top of this file."""
    from . import joints
    objs = [o for o in objs if o is not None and o.name in scene.objects]
    if not objs:
        return ""
    note = "The built animation was taken off: Build again" if _take_build_off(scene) else ""
    follow = _follow_joints(scene, objs)
    frames = {j.frame for j in follow.values()}
    rest = [o for o in objs if not (joints.joint_of_object(scene, o) is not None
                                    and joints.joint_of_object(scene, o).name in follow)
            and not _under(o, frames)]
    for j in follow.values():
        f = j.frame
        if FRAME_FROM not in j.motion:
            j.motion[FRAME_FROM] = json.dumps(build.mat_to_list(f.matrix_basis))
        for m in joints.members(j):
            _remember_file(m)
        f.matrix_basis = _pw(f).inverted() @ D @ f.matrix_world
    if follow:
        bpy.context.view_layer.update()
    for ob in rest:
        if is_root(ob):
            ob.matrix_basis = _pw(ob).inverted() @ D @ ob.matrix_world
        else:
            _move_one(ob, D)
    if follow or _elsewhere_children(scene, [o for o in rest if not is_root(o)]):
        _rederive(scene)
        for j in follow.values():
            for m in joints.members(j):
                _tidy_file(m)
    _after(scene)
    NOTE[0] = note
    return note


def _after(scene) -> None:
    from . import logic
    try:
        bpy.context.view_layer.update()
    except Exception:  # noqa: BLE001
        pass
    scene.fresing.bounds_valid = False
    logic.drop_tree_cache()
    try:
        from . import flex, linkages, paths
        linkages.refresh_all(scene)
        flex.refresh(scene)
        paths.refresh(scene)
    except Exception as exc:  # noqa: BLE001 - a follower that cannot follow never stops a move
        print("Fresing Render: after Place:", exc)


def back_to_cad(scene, objs) -> str:
    """Subassemblies and parts back on the place the STEP file has them (no free move either); a model back where it
    was imported. Returns a note."""
    from . import joints
    objs = [o for o in objs if o is not None and o.name in scene.objects]
    if not objs:
        return ""
    note = "The built animation was taken off: Build again" if _take_build_off(scene) else ""
    frames = False
    for ob in objs:
        j = _frame_moved(scene, ob)
        if j is not None:
            j.frame.matrix_basis = build.list_to_mat(json.loads(j.motion[FRAME_FROM]))
            del j.motion[FRAME_FROM]
            frames = True
    if frames:
        bpy.context.view_layer.update()
        _rederive(scene)
    for ob in objs:
        if is_root(ob):
            ob.matrix_basis = build.rest_basis(ob)
            continue
        f = file_basis(ob)
        cad, rest = build.cad_basis(ob), build.rest_basis(ob)
        if _member(ob):
            rest2 = (cad @ rest.inverted()).inverted() @ f
        else:
            rest2 = f @ cad.inverted() @ rest
        build.set_mat(ob, build.PROP_CAD_BASIS, f)
        build.set_mat(ob, build.PROP_REST_BASIS, rest2)
        ob.matrix_basis = rest2
        if FILE in ob:
            del ob[FILE]
    if frames or _elsewhere_children(scene, [o for o in objs if not is_root(o)]):
        _rederive(scene)
        for ob in scene.objects:
            if FILE in ob:
                _tidy_file(ob)
    _after(scene)
    NOTE[0] = note
    return note


def carry_over(ob_old, ob_new) -> None:
    """A model update (reimport.py): a placed part of the old revision stays placed in the new one – the same move
    in its CAD parent's coordinates, on top of where the new file has it."""
    old_file = build.get_mat(ob_old, FILE)
    if old_file is None:
        return
    L = build.cad_basis(ob_old) @ old_file.inverted()
    new_file = build.cad_basis(ob_new)
    build.set_mat(ob_new, FILE, new_file)
    placed = L @ new_file
    build.set_mat(ob_new, build.PROP_CAD_BASIS, placed)
    build.set_mat(ob_new, build.PROP_REST_BASIS, placed)
    ob_new.matrix_basis = placed


# ---------------------------------------------------------------------------
# what the fields show: positions and turns
# ---------------------------------------------------------------------------

def _meshes(scene, ob) -> list:
    from . import logic
    obs = [ob] + logic.cached_tree(scene).descendants(ob)
    return [o for o in obs if o.type == "MESH" and o.get(build.PROP_KIND) == "part" and o.data is not None]


def bounds(scene, ob) -> tuple:
    """(lowest corner, highest corner) of what ``ob`` stands for, in the world (boxes of its parts)."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for m in _meshes(scene, ob):
        M = np.array(m.matrix_world)
        c = np.array([tuple(v) for v in m.bound_box], dtype=float)
        w = c @ M[:3, :3].T + M[:3, 3]
        lo = np.minimum(lo, w.min(axis=0))
        hi = np.maximum(hi, w.max(axis=0))
    if not np.all(np.isfinite(lo)):
        t = ob.matrix_world.translation
        return Vector(t), Vector(t)
    return Vector(lo), Vector(hi)


def pivot(scene, objs) -> Vector:
    """What a turn turns about: the middle of the chosen things' boxes."""
    lo, hi = None, None
    for ob in objs:
        a, b = bounds(scene, ob)
        lo = a if lo is None else Vector(np.minimum(lo, a))
        hi = b if hi is None else Vector(np.maximum(hi, b))
    return (lo + hi) / 2.0 if lo is not None else Vector()


def lowest_z(scene, objs) -> float:
    """The lowest point of the chosen things' parts (their points, not boxes) in the world."""
    z = math.inf
    for ob in objs:
        for m in _meshes(scene, ob):
            n = len(m.data.vertices)
            if not n:
                continue
            co = np.empty(n * 3, dtype=np.float32)
            m.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3).astype(float)
            M = np.array(m.matrix_world)
            z = min(z, float((co @ M[2, :3] + M[2, 3]).min()))
    return z


def floor_z(scene) -> float:
    """The floor: the surroundings' floor when there are surroundings, else z = 0."""
    from . import surroundings
    root = surroundings.root_object()
    if root is not None and root.get("fr_kind"):
        return float(root.location.z)
    return 0.0


def reference(scene, ob) -> Matrix:
    """Where ``ob`` would be in the world on its file place (a model: where it was imported), as things stand now."""
    if is_root(ob):
        return _pw(ob) @ build.rest_basis(ob)
    base = _pw(ob) @ build.rest_basis(ob)
    try:
        return base @ build.cad_basis(ob).inverted() @ file_basis(ob)
    except ValueError:
        return base


def axes(scene, ob) -> Matrix:
    """The model's own axes (3x3) – what Place's "Model axes" measure along."""
    if is_root(ob):
        return reference(scene, ob).to_3x3().normalized()
    root = build.model_root_of(ob)
    return (root.matrix_world.to_3x3().normalized() if root is not None else Matrix.Identity(3))


def numbers(scene, ob, space: str) -> tuple:
    """(x, y, z in mm, turn about x, y, z in degrees) as the fields show them: World = where its origin is and how it
    is turned in the world; Model axes = how far it is from its file place (a model: from where it was imported),
    along and about the model's own axes."""
    W = ob.matrix_world
    if space == "WORLD":
        t = W.translation
        e = W.to_3x3().normalized().to_euler("XYZ")
    else:
        ref = reference(scene, ob)
        A = axes(scene, ob)
        t = A.transposed() @ (W.translation - ref.translation)
        R = W.to_3x3().normalized() @ ref.to_3x3().normalized().transposed()
        e = (A.transposed() @ R @ A).to_euler("XYZ")
    return (t.x * 1000.0, t.y * 1000.0, t.z * 1000.0,
            core.wrap_degrees(math.degrees(e.x)), core.wrap_degrees(math.degrees(e.y)),
            core.wrap_degrees(math.degrees(e.z)))


def delta_for(scene, ob, space: str, index: int, value: float, objs=None) -> Matrix:
    """The world move that gives field ``index`` (0–2 position in mm, 3–5 turn in degrees) the new ``value``."""
    now = list(numbers(scene, ob, space))
    W = ob.matrix_world
    if index < 3:
        d = Vector((0.0, 0.0, 0.0))
        d[index] = (value - now[index]) / 1000.0
        if space != "WORLD":
            d = axes(scene, ob) @ d
        return Matrix.Translation(d)
    now[index] = value
    e = Euler([math.radians(a) for a in now[3:]], "XYZ").to_matrix()
    if space == "WORLD":
        R_new = e
    else:
        A = axes(scene, ob)
        R_new = A @ e @ A.transposed() @ reference(scene, ob).to_3x3().normalized()
    turn = R_new @ W.to_3x3().normalized().transposed()
    p = pivot(scene, objs or [ob])
    return Matrix.Translation(p) @ turn.to_4x4() @ Matrix.Translation(-p)


def step_delta(scene, ob, space: str, axis: int, amount: float, turn: bool, objs=None) -> Matrix:
    """A step: ``amount`` mm along, or degrees about, world or model axis ``axis`` (0, 1, 2)."""
    a = Vector((0.0, 0.0, 0.0))
    a[axis] = 1.0
    if space != "WORLD":
        a = axes(scene, ob) @ a
    if not turn:
        return Matrix.Translation(a * (amount / 1000.0))
    p = pivot(scene, objs or [ob])
    return Matrix.Translation(p) @ Matrix.Rotation(math.radians(amount), 4, a) @ Matrix.Translation(-p)


def put_on_floor(scene, objs) -> float:
    """Move the chosen things up or down so their lowest point sits on the floor. Returns the move in metres."""
    z = lowest_z(scene, objs)
    if not math.isfinite(z):
        return 0.0
    dz = core.to_floor(z, floor_z(scene))
    if abs(dz) > 1e-7:
        move(scene, objs, Matrix.Translation((0.0, 0.0, dz)))
    return dz


# ---------------------------------------------------------------------------
# the fields of 2 Structure > Place (scene.fresing.place: get / set)
# ---------------------------------------------------------------------------

def _space(scene) -> str:
    return scene.fresing.place.space


def field_get(index: int) -> float:
    context = bpy.context
    scene = getattr(context, "scene", None)
    if scene is None or getattr(scene, "fresing", None) is None:
        return 0.0
    ob = target(context)
    if ob is None:
        return 0.0
    try:
        v = round(float(numbers(scene, ob, _space(scene))[index]), 4)       # no "-0.000002" from float32 matrices
        return 0.0 if v == 0.0 else v
    except (ValueError, ReferenceError):
        return 0.0


def field_set(index: int, value: float) -> None:
    context = bpy.context
    scene = context.scene
    objs = movers(context)
    why = refused(context, objs)
    if why:
        NOTE[0] = why
        return
    ob = target(context)
    st = scene.fresing.place
    size = core.size_of(core.SNAP_MOVE, st.snap_move) if index < 3 else core.size_of(core.SNAP_TURN, st.snap_turn)
    value = core.snap(value, size)
    if abs(value - field_get(index)) < 1e-6:
        return
    move(scene, objs, delta_for(scene, ob, _space(scene), index, value, objs))


def apply(context, D: Matrix) -> str:
    """Place what is selected by the world matrix ``D``: '' when done (or a note), else why not (raises nothing)."""
    objs = movers(context)
    why = refused(context, objs)
    if why:
        raise RuntimeError(why)
    return move(context.scene, objs, D)


def state(scene) -> str:
    """The Place panel's header: what it shows."""
    from . import lock
    if lock.ON[0]:
        return "locked"
    ob = target(bpy.context)
    if ob is None:
        return "none selected"
    if locked(ob):
        return "locked"
    return "placed" if is_placed(ob) else "CAD place" if not is_root(ob) else "as imported"


CLASSES = (FRESING_OT_move_key, FRESING_OT_ctx_unlock)
