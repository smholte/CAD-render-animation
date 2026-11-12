"""Vessel motion at sea (task 0085): the model, the vessel deck and the props heave, pitch and roll with the sea.

How it works (the maths is in ``core/vessel_motion.py``):

* A small rig of empties in the collection "FR Vessel motion": **FR Vessel** sits on the pivot (default: at the
  waterline under the middle of the hull) and carries heave (its z), roll (its x turn) and pitch (its y turn); its
  child **FR Vessel pivot** takes the pivot off again, so its world matrix is the vessel's whole motion
  ``T(pivot + heave) · R(pitch) · R(roll) · T(-pivot)``.
* Every model root, every object of the Vessel deck (not the sea) and every prop gets a **Child Of** constraint
  "FR vessel motion" on FR Vessel pivot: it moves as if it stood on the deck. Joints, cylinders, mechanisms, decals,
  labels, way covers, fades and trails hang on the parts, so they keep working on top of it. The sea, the sky, the
  halls and the cameras get nothing: they stay in the world.
* Each moving channel is a **driver** whose simple expression gives the time in seconds (``frame * fps_base / fps``,
  as the sea's waves use) and **built-in sine modifiers** on it, one per wave (amplitude, frequency, phase from
  ``core``). No Python runs: it plays with "Auto Run Python Scripts" off, in the render queue and at any frame rate,
  and the vessel stays in step with the waves the sea shows. (A driver expression may hold 255 characters, too
  few for 30 sines; keys would have to be baked again whenever the animation's length or speed changes.)
* **Stays still**: picked subassemblies keep their place in the world: "Still" takes the whole motion out (a
  constraint on the inverse rig), "Level" only roll and pitch (heave stays). Their joints still work, as if the
  vessel lay still.

Nothing is made while vessel motion is off or the surroundings are not the Open sea or the Vessel deck: such a
project is exactly as before (no rig, no constraints, no swell in the sea).
"""

from __future__ import annotations

import contextlib
import json
import math

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core import surroundings as S
from ..core import vessel_motion as core

COLLECTION = "FR Vessel motion"
TAG = "fr_vessel"                 # on the rig's empties (value: their role)
CON = "FR vessel motion"          # Child Of on everything that moves with the vessel
CON_STILL = "FR vessel still"     # Child Of on the inverse rig: stays where it is in the world
CON_LEVEL = "FR vessel level"     # Child Of on the inverse rig without heave: stays level, heaves with the vessel
CONSTRAINTS = (CON, CON_STILL, CON_LEVEL)
KINDS = ("SEA", "DECK")           # surroundings a vessel can move in
NAMES = {"vessel": "FR Vessel", "pivot": "FR Vessel pivot", "still": "FR Vessel still",
         "still_pivot": "FR Vessel still pivot", "level": "FR Vessel level", "level_pivot": "FR Vessel level pivot"}
MODES = (("STILL", "Still", "Stays where it is in the world: no heave, pitch or roll (a motion-compensated gangway "
                            "or a hook that holds its place)"),
         ("LEVEL", "Level", "Stays level: roll and pitch are taken out, it still rises and falls with the vessel"))

_STATE = {"resting": 0, "busy": False, "sig": {}}


# =============================================================================
# settings and what they mean
# =============================================================================


def settings(scene):
    return scene.fresing.vessel


def effective(scene) -> bool:
    """Vessel motion is on and the surroundings are a sea a vessel moves in."""
    s = scene.fresing
    return bool(s.vessel.enabled) and s.background in KINDS


def _surroundings():
    from . import surroundings
    return surroundings


def _sea_object():
    sur = _surroundings()
    for ob in bpy.data.objects:
        if ob.get(sur.TAG) == "sea":
            return ob
    return None


def swell_rows(s) -> list:
    """The long swell the sea gets while vessel motion is on (``s`` = scene.fresing); [] otherwise."""
    if not (s.vessel.enabled and s.background in KINDS):
        return []
    return [w.as_tuple() for w in core.swell(s.sea_state, s.vessel.heading)]


def swell_key(s) -> str:
    """Part of the surroundings' settings key: the sea is built again when the swell changes ('' = none)."""
    rows = swell_rows(s)
    return f"{s.vessel.heading}" if rows else ""


def _sea_waves(state: str) -> list:
    sur = _surroundings()
    return core.waves_from_tuples(sur._waves(state))


def hull(scene) -> dict | None:
    """Where the vessel is (world, at rest): its middle, length, beam and the water's height. None: no sea."""
    sur = _surroundings()
    s = scene.fresing
    root = sur.root_object()
    sea = _sea_object()
    if root is None or sea is None or not root.get("fr_kind") or root.get("fr_kind") not in KINDS:
        return None
    mn = Vector(root.get("fr_min", (0.0, 0.0, 0.0)))
    mx = Vector(root.get("fr_max", (1.0, 1.0, 1.0)))
    # from the parent chain: a sea made a moment ago has no world matrix yet
    at = (root.matrix_basis @ sea.matrix_parent_inverse @ sea.matrix_basis).translation if sea.parent == root \
        else sea.matrix_basis.translation
    water = float(at.z)
    if root["fr_kind"] == "DECK":
        size = tuple(max(float(v), 0.05) for v in (mx - mn))
        lay = S.build("DECK", size, s.env_detail, s.water_level)
        box = next(b for b in lay.parts.get("structure", []) if isinstance(b, S.Box) and b.mat == "hull")
        middle = (root.location.x + box.x, root.location.y + box.y)
        length, beam = box.sx, box.sy
    else:
        middle = ((mn.x + mx.x) / 2, (mn.y + mx.y) / 2)
        length, beam = float(mx.x - mn.x), float(mx.y - mn.y)
    return {"middle": middle, "length": max(length, core.MIN_LENGTH), "beam": max(beam, core.MIN_BEAM),
            "water": water, "sea_xy": (float(at.x), float(at.y)),
            "model_middle": ((mn.x + mx.x) / 2, (mn.y + mx.y) / 2)}


def size(scene) -> tuple[float, float]:
    """Length and beam the motion uses (read from the deck or the model, or the user's own)."""
    v = settings(scene)
    if not v.auto_size:
        return max(v.length, core.MIN_LENGTH), max(v.beam, core.MIN_BEAM)
    h = hull(scene)
    return (h["length"], h["beam"]) if h else core.REFERENCE_SIZE


def pivot(scene) -> Vector | None:
    """The point the vessel turns about (world, at rest)."""
    v = settings(scene)
    if v.pivot_mode == "PICK":
        return Vector(v.pivot)
    h = hull(scene)
    if h is None:
        return None
    x, y = h["middle"] if scene.fresing.background == "DECK" else h["model_middle"]
    return Vector((x, y, h["water"]))


def core_settings(scene) -> core.Settings | None:
    h = hull(scene)
    if h is None:
        return None
    s = scene.fresing
    v = s.vessel
    length, beam = size(scene)
    centre = (h["middle"][0] - h["sea_xy"][0], h["middle"][1] - h["sea_xy"][1])
    return core.Settings(state=s.sea_state, heading=v.heading, strength=v.strength / 100.0, length=length, beam=beam,
                         roll_period=v.roll_period, centre=centre)


def motion(scene) -> core.Motion | None:
    st = core_settings(scene)
    if st is None:
        return None
    return core.motion(st, _sea_waves(scene.fresing.sea_state))


# =============================================================================
# holding the vessel still while something measures the model
# =============================================================================


def _constraints(scene=None):
    for ob in (scene.objects if scene is not None else bpy.data.objects):
        for con in ob.constraints:
            if con.name in CONSTRAINTS and con.type == "CHILD_OF":
                yield ob, con


@contextlib.contextmanager
def at_rest(scene):
    """Inside: the model, deck and props stand where they would on a still sea (the surroundings measure the model,
    a model update rebuilds joints from world places). Nested uses are fine; sync() waits until the outermost ends."""
    _STATE["resting"] += 1
    muted = []
    try:
        if _STATE["resting"] == 1:
            for ob, con in _constraints(scene):
                if not con.mute:
                    con.mute = True
                    muted.append((ob.name, con.name))     # names: an object may be deleted inside (model update)
            if muted:
                bpy.context.view_layer.update()
        yield
    finally:
        _STATE["resting"] -= 1
        for ob_name, con_name in muted:
            ob = bpy.data.objects.get(ob_name)
            con = ob.constraints.get(con_name) if ob is not None else None
            if con is not None:
                con.mute = False
        if muted:
            bpy.context.view_layer.update()


# =============================================================================
# the rig
# =============================================================================


def _collection(scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def rig(role: str = "pivot"):
    ob = bpy.data.objects.get(NAMES[role])
    return ob if ob is not None and ob.get(TAG) == role else None


def _empty(scene, role: str, parent=None) -> bpy.types.Object:
    ob = rig(role)
    if ob is None:
        ob = bpy.data.objects.new(NAMES[role], None)
        ob[TAG] = role
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.5
    ob.hide_render = True
    ob.hide_select = True
    if ob.parent != parent:
        ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.rotation_mode = "XYZ"
    return ob


def _clear_drivers(ob) -> None:
    ad = ob.animation_data
    if ad is None:
        return
    for fc in list(ad.drivers):
        ad.drivers.remove(fc)


def _channel(scene, ob, path: str, index: int, base: float, terms) -> None:
    """``ob.path[index]`` = base + sum(amp * sin(phase - omega * t)), t = the scene's time in seconds."""
    fc = ob.driver_add(path, index)
    d = fc.driver
    d.type = "SCRIPTED"
    while d.variables:
        d.variables.remove(d.variables[0])
    for name, prop in (("f", "render.fps"), ("b", "render.fps_base")):
        var = d.variables.new()
        var.name = name
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "SCENE"
        var.targets[0].id = scene
        var.targets[0].data_path = prop
    # never a small number (CLAUDE.md section 8: Blender wrote 0 for small driver results): T0 seconds on top
    d.expression = f"frame * b / f + {core.T0:.1f}"
    for m in list(fc.modifiers):
        fc.modifiers.remove(m)
    g = fc.modifiers.new("GENERATOR")           # the constant: replaces the driver's own value (the time)
    g.mode = "POLYNOMIAL"
    g.poly_order = 1
    g.use_additive = False
    g.coefficients = (float(base), 0.0)
    for amp, omega, phase in terms:
        m = fc.modifiers.new("FNGENERATOR")
        m.function_type = "SIN"
        m.use_additive = True
        m.amplitude = float(amp)
        m.phase_multiplier = -float(omega)
        m.phase_offset = math.fmod(float(phase) + float(omega) * core.T0, 2 * math.pi)
        m.value_offset = 0.0


def _neg(ch: core.Channel) -> list:
    return [(-a, w, p) for a, w, p in ch.terms]


def _build_rig(scene, mo: core.Motion, p: Vector, need_still: bool, need_level: bool) -> None:
    v = _empty(scene, "vessel")
    _clear_drivers(v)
    v.location = (p.x, p.y, p.z)
    v.rotation_euler = (0.0, 0.0, 0.0)
    _channel(scene, v, "location", 2, p.z, mo.heave.terms)
    _channel(scene, v, "rotation_euler", 0, 0.0, mo.roll.terms)
    _channel(scene, v, "rotation_euler", 1, 0.0, mo.pitch.terms)
    piv = _empty(scene, "pivot", v)
    _clear_drivers(piv)
    piv.location = (-p.x, -p.y, -p.z)
    piv.rotation_euler = (0.0, 0.0, 0.0)
    for role, wanted, heave in (("still", need_still, False), ("level", need_level, True)):
        top, low = rig(role), rig(role + "_pivot")
        if not wanted:
            for ob in (low, top):
                if ob is not None:
                    bpy.data.objects.remove(ob)
            continue
        # still: T(p) R^-1 T(-p - heave) = the inverse of the vessel's motion; level: T(heave) on top of that
        top = _empty(scene, role)
        _clear_drivers(top)
        top.rotation_mode = "ZYX"                 # Rx(-roll) · Ry(-pitch): the inverse of Ry(pitch) · Rx(roll)
        top.location = (p.x, p.y, p.z)
        top.rotation_euler = (0.0, 0.0, 0.0)
        if heave:
            _channel(scene, top, "location", 2, p.z, mo.heave.terms)
        _channel(scene, top, "rotation_euler", 0, 0.0, _neg(mo.roll))
        _channel(scene, top, "rotation_euler", 1, 0.0, _neg(mo.pitch))
        low = _empty(scene, role + "_pivot", top)
        _clear_drivers(low)
        low.location = (-p.x, -p.y, -p.z)
        _channel(scene, low, "location", 2, -p.z, _neg(mo.heave))


def remove(scene=None) -> None:
    """Take vessel motion out of the project completely (constraints, rig, collection)."""
    for ob, con in list(_constraints(scene)):
        ob.constraints.remove(con)
    for role in ("still_pivot", "level_pivot", "pivot", "still", "level", "vessel"):
        ob = rig(role)
        if ob is not None:
            bpy.data.objects.remove(ob)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and not col.objects:
        bpy.data.collections.remove(col)


# =============================================================================
# what moves
# =============================================================================


def followers(scene) -> list:
    """Every model root, the Vessel deck's objects (not the sea) and the props."""
    from . import build
    sur = _surroundings()
    out = list(build.model_roots(scene))
    root = sur.root_object()
    if root is not None and root.get("fr_kind") == "DECK":
        out += [ob for ob in sur._objects(scene) if ob.get(sur.TAG) not in ("sea", "root")]
    out += sur.props(scene)
    return out


def marked(scene) -> dict:
    """Objects the user picked to stay still: {object name: "STILL" | "LEVEL"} (only those that still exist)."""
    from . import states
    by = states.by_uid(scene)
    out = {}
    for m in settings(scene).still:
        ob = by.get(m.uid)
        if ob is not None:
            out[ob.name] = m.mode
    return out


def _still_owners(scene, marks: dict) -> dict:
    """Which objects get the still/level constraint: the top of each marked subassembly in Blender's own tree (a
    part a joint from outside moves hangs under that joint's empty: it gets its own)."""
    from . import build, logic
    if not marks:
        return {}
    tree = logic.Tree(scene)
    mode_of: dict[str, str] = {}
    objs = {ob.name: ob for ob in scene.objects}
    for name, mode in marks.items():
        ob = objs.get(name)
        if ob is None:
            continue
        # a mark inside another mark: the outer one wins
        p, inside = build.logical_parent(ob), False
        while p is not None:
            if p.name in marks:
                inside = True
                break
            p = build.logical_parent(p)
        if inside:
            continue
        mode_of[name] = mode
        for d in tree.descendants(ob):
            mode_of.setdefault(d.name, mode)
    owners = {}
    for name, mode in mode_of.items():
        ob = objs[name]
        p = ob.parent
        covered = False
        while p is not None:
            if p.name in mode_of:
                covered = True
                break
            p = p.parent
        if not covered:
            owners[name] = mode
    return owners


def _ensure_con(ob, name: str, target) -> bool:
    con = ob.constraints.get(name)
    changed = False
    if con is not None and con.type != "CHILD_OF":
        ob.constraints.remove(con)
        con = None
    if con is None:
        con = ob.constraints.new("CHILD_OF")
        con.name = name
        con.show_expanded = False
        changed = True
    if con.set_inverse_pending:           # a new Child Of takes the target's place at its first update as its
        con.set_inverse_pending = False   # inverse (the model would stay where it was then): never here
        changed = True
    if con.target != target:
        con.target = target
        changed = True
    if any(abs(con.inverse_matrix[i][j] - (1.0 if i == j else 0.0)) > 1e-12 for i in range(4) for j in range(4)):
        con.inverse_matrix = Matrix.Identity(4)
        changed = True
    if con.mute and not _STATE["resting"]:
        con.mute = False
        changed = True
    return changed


def _drop_con(ob, name: str) -> bool:
    con = ob.constraints.get(name)
    if con is not None and con.type == "CHILD_OF":
        ob.constraints.remove(con)
        return True
    return False


# =============================================================================
# keeping it in step
# =============================================================================


def _key(scene, st: core.Settings, p: Vector, owners: dict) -> str:
    return json.dumps({"m": core.key(st), "p": [round(c, 4) for c in p],
                       "still": sorted(set(owners.values()))}, sort_keys=True)


def sync(scene) -> bool:
    """Make the rig and the constraints match the settings. Cheap when nothing changed. Returns True when
    something was changed."""
    if _STATE["resting"] or _STATE["busy"]:
        return False
    _STATE["busy"] = True
    try:
        return _sync(scene)
    finally:
        _STATE["busy"] = False


def _sync(scene) -> bool:
    if not effective(scene):
        had = rig("vessel") is not None or any(True for _ in _constraints(scene))
        if had:
            remove(scene)
        return had
    st = core_settings(scene)
    p = pivot(scene)
    if st is None or p is None:
        return False
    owners = _still_owners(scene, marked(scene))
    k = _key(scene, st, p, owners)
    changed = False
    v = rig("vessel")
    if v is None or rig("pivot") is None or v.get("fr_key") != k:
        mo = core.motion(st, _sea_waves(scene.fresing.sea_state))
        _build_rig(scene, mo, p, "STILL" in owners.values(), "LEVEL" in owners.values())
        v = rig("vessel")
        v["fr_key"] = k
        m = core.measure(mo, 120.0, 0.04)
        v["fr_peaks"] = json.dumps({c: round(m[c], 4) for c in m})
        changed = True
    target = rig("pivot")
    moving = set()
    for ob in followers(scene):
        moving.add(ob.name)
        changed |= _ensure_con(ob, CON, target)
    for ob, con in list(_constraints(scene)):
        if con.name == CON and ob.name not in moving:
            ob.constraints.remove(con)
            changed = True
    targets = {"STILL": rig("still_pivot"), "LEVEL": rig("level_pivot")}
    for ob, con in list(_constraints(scene)):
        if con.name in (CON_STILL, CON_LEVEL):
            mode = owners.get(ob.name)
            if mode is None or (CON_STILL if mode == "STILL" else CON_LEVEL) != con.name:
                ob.constraints.remove(con)
                changed = True
    for name, mode in owners.items():
        ob = scene.objects.get(name)
        if ob is not None:
            changed |= _ensure_con(ob, CON_STILL if mode == "STILL" else CON_LEVEL, targets[mode])
    _STATE["sig"][scene.name] = _signature(scene)
    if changed:
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass
    return changed


def changed(scene, sea: bool = False) -> None:
    """A setting changed. ``sea``: the swell changes too, so the sea is built again (the surroundings call sync)."""
    if sea:
        from . import world
        world.apply(scene, scene.fresing)
    else:
        sync(scene)


def after_surroundings(scene) -> None:
    """The surroundings were made or checked (world.apply): the deck may be new."""
    try:
        sync(scene)
    except Exception as exc:                 # never stop a render over this
        print("Fresing Render: vessel motion not set up:", exc)


def after_model_update(scene, mapping: dict) -> list[str]:
    """Model update (reimport): the picked subassemblies follow their new part IDs; the new root moves along."""
    notes = []
    still = settings(scene).still
    for i in reversed(range(len(still))):
        m = still[i]
        new = mapping.get(m.uid)
        if new is None:
            continue
        if new.startswith("gone:"):
            notes.append(f"Vessel motion: '{m.label}' is not in the new model, so it no longer stays still "
                         "(5 Scene & Render > Vessel motion)")
            still.remove(i)
        else:
            m.uid = new
    sync(scene)
    return notes


def _signature(scene) -> tuple:
    """Cheap fingerprint of what decides the constraints: models, props, joints, picks."""
    s = scene.fresing
    from . import surroundings
    col = bpy.data.collections.get(surroundings.PROPS_COLLECTION)
    return (s.model_count, len(col.objects) if col is not None else 0, len(s.vessel.still),
            tuple((j.name, len(j.members)) for j in s.joints) if len(s.vessel.still) else ())


def _resync():
    try:
        scene = bpy.context.scene
        if scene is not None and hasattr(scene, "fresing"):
            sync(scene)
    except Exception as exc:
        print("Fresing Render: vessel motion update failed:", exc)
    return None


@persistent
def _on_depsgraph(scene, _depsgraph=None):
    """A model came in, a prop was added, a joint changed: the constraints follow (a timer, after this update)."""
    if _STATE["busy"] or _STATE["resting"] or scene is None:
        return
    try:
        if rig("vessel") is None or not effective(scene):
            return
        if _STATE["sig"].get(scene.name) == _signature(scene):
            return
    except (AttributeError, ReferenceError):
        return
    if bpy.app.background:
        _resync()
    elif not bpy.app.timers.is_registered(_resync):
        bpy.app.timers.register(_resync, first_interval=0.0)


@persistent
def _on_load(_dummy=None):
    _STATE["sig"].clear()


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
    if bpy.app.timers.is_registered(_resync):
        bpy.app.timers.unregister(_resync)


# =============================================================================
# for the panel
# =============================================================================


def peaks(scene) -> dict:
    v = rig("vessel")
    try:
        return json.loads(v.get("fr_peaks", "{}")) if v is not None else {}
    except ValueError:
        return {}


def header(scene) -> str:
    """'Off' / 'Calm · roll ±1.2°'."""
    if not effective(scene):
        return "Off"
    pk = peaks(scene)
    return core.summary(scene.fresing.sea_state, settings(scene).strength / 100.0, pk.get("roll", 0.0))


def words(scene) -> str:
    """One line of what the vessel does now (the panel)."""
    pk = peaks(scene)
    if not pk:
        return ""
    return (f"Over 2 minutes: roll ±{pk['roll']:.1f}° (every {pk['roll_s']:.0f} s), pitch ±{pk['pitch']:.1f}° "
            f"(every {pk['pitch_s']:.0f} s), heave ±{pk['heave']:.2f} m (every {pk['heave_s']:.0f} s)")


def to_rest(scene, world_point: Vector) -> Vector:
    """A point clicked on the moving model/deck: where it is on a still sea."""
    piv = rig("pivot")
    if piv is None:
        return Vector(world_point)
    return piv.matrix_world.inverted() @ Vector(world_point)


def add_marks(scene, objs, mode: str) -> int:
    """Picked subassemblies stay still ("STILL") or level ("LEVEL"). Returns how many were added or changed."""
    from . import build
    still = settings(scene).still
    n = 0
    for ob in objs:
        uid = ob.get(build.PROP_UID)
        if not uid:
            continue
        m = next((m for m in still if m.uid == uid), None)
        if m is None:
            m = still.add()
            m.uid = uid
        if m.mode != mode or not m.label:
            n += 1
        m.mode = mode
        m.label = ob.get(build.PROP_NAME, ob.name)
    sync(scene)
    return n
