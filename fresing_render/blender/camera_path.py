"""Camera steps that ride along a part, fly a path or keep a part in the middle (task 0087).

The three new modes of the Camera step ("Ride along", "Fly a path", "Watch part") are worked out at Build like the
old ones: the Animation camera gets a key on every frame (animation.py ``_camera_track``). What they need from the
scene - where the ridden or watched part is on every frame of the step - is read once before (``Context``: the frames
are set one by one, as the trail lines do). Nothing runs while the animation plays: plain keys, so it works with
scripts off, in the render queue and in saved projects.

Ride along   the camera keeps its place and view on a part: camera(f) = part(f) @ offset, the offset taken where the
             camera is when the step starts (or from a saved camera, placed with the model as it stands at Build).
             Keep level: the camera follows the part's place and its turn about the vertical, never its tilt.
Fly a path   a smooth curve through points (core/camera_path.Path), flown at an even speed with a ramp up and down;
             it looks ahead, at the model or at a part. The path is shown in the view (a curve object that never
             renders) and kept in the step (``path_points``).
Watch part   the camera stays where it is and turns so the part's middle is in the middle of the picture.

Every new step glides in from where the camera was over ``cam_blend`` seconds, so it never jumps; after the step the
camera stays where the step left it, and the next step starts from there.
"""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from ..core import camera_path as P
from . import build

MODES = ("RIDE", "PATH", "AIM")
PROP_PATH = "fr_camera_path"            # on the curve object that shows a step's path


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def looks_at_part(b) -> bool:
    return (b.camera_mode == "AIM" or (b.camera_mode == "RIDE" and b.ride_look == "PART")
            or (b.camera_mode == "PATH" and b.path_look == "PART"))


def label(b) -> str:
    """The step's name in the list and on the timeline."""
    if b.camera_mode == "RIDE":
        return f"Ride on {b.target_name}" if b.target_name else "Ride along"
    if b.camera_mode == "PATH":
        return "Fly a path"
    return f"Watch {b.aim_name}" if b.aim_name else "Watch a part"


def look_at(pos: Vector, target: Vector) -> Matrix:
    """A camera matrix at ``pos`` looking at ``target``, upright (its picture's top towards +Z)."""
    d = Vector(target) - Vector(pos)
    if d.length < 1e-9:
        d = Vector((0.0, 1.0, 0.0))
    q = d.to_track_quat("-Z", "Y")
    return Matrix.Translation(pos) @ q.to_matrix().to_4x4()


def _rotation(m: Matrix) -> Matrix:
    """The turn of a 4 x 4 matrix as a clean 3 x 3 rotation (scale taken off)."""
    return m.to_quaternion().to_matrix()


# ---------------------------------------------------------------------------
# reading the parts over the frames
# ---------------------------------------------------------------------------

class Context:
    """Where the parts the new camera steps ride or watch are, at every frame they need (read once, at Build)."""

    def __init__(self, scene, anim, blocks, uids: dict, centre: Vector, warnings: list):
        from . import animation
        self.scene = scene
        self.centre = Vector(centre)
        self.objects: dict[str, bpy.types.Object] = {}
        self.at_build: dict[str, Matrix] = {}
        self.middle: dict[str, Vector] = {}           # the part's middle, in its own coordinates
        self.mats: dict[str, dict[int, Matrix]] = {}
        frames: dict[str, set] = {}
        for b in blocks:
            if b.camera_mode not in MODES:
                continue
            f0, f1 = animation.frame_of(anim, b.start), animation.frame_of(anim, b.start + b.duration)
            span = set(range(f0, max(f1, f0) + 1))
            wanted = []
            if b.camera_mode == "RIDE":
                wanted.append((b.target_uid, b.target_name, "the part to ride on"))
            if looks_at_part(b):
                wanted.append((b.aim_uid, b.aim_name, "the part to keep in the middle"))
            for uid, name, what in wanted:
                ob = uids.get(uid) if uid else None
                if ob is None:
                    warnings.append(f"'{animation.block_label(b)}': " + (f"'{name}' not found" if uid else
                                                                         f"pick {what}"))
                    continue
                self.objects[uid] = ob
                frames.setdefault(uid, set()).update(span)
        for fs in frames.values():
            fs.add(1)                       # frame 1: the model as it stands at Build (the same in the queue)
        self._sample(frames)

    def _sample(self, frames: dict) -> None:
        if not frames:
            return
        from . import clash
        scene = self.scene
        every = sorted(set().union(*frames.values()))
        keep = (scene.frame_current, scene.frame_subframe)
        needed = set(self.objects.values())
        shy = [o for o in scene.objects if not o.hide_viewport and o not in needed
               and any(m.type == "NODES" for m in getattr(o, "modifiers", ()))]
        for o in shy:                       # only drawn (toolpath, chips, coolant): not worked out at every frame
            o.hide_viewport = True
        try:
            with clash._Guard():
                for f in every:
                    scene.frame_set(int(f))
                    for uid, fs in frames.items():
                        if f in fs:
                            ob = self.objects[uid]
                            self.mats.setdefault(uid, {})[f] = ob.matrix_world.copy()
                            if f == 1:
                                self.at_build[uid] = ob.matrix_world.copy()
                                self.middle[uid] = self.at_build[uid].inverted_safe() @ _middle(ob)
        finally:
            for o in shy:
                o.hide_viewport = False
            scene.frame_set(keep[0], subframe=keep[1])

    def has(self, uid: str) -> bool:
        return uid in self.mats

    def world(self, uid: str, f: int) -> Matrix:
        m = self.mats[uid]
        if f in m:
            return m[f]
        return m[min(m, key=lambda k: abs(k - f))]

    def point(self, uid: str, f: int) -> Vector:
        """The part's middle in the world at frame ``f``."""
        return self.world(uid, f) @ self.middle[uid]


def _middle(ob) -> Vector:
    """The middle of the box round the part (or every part of the subassembly), in the world."""
    obs = [o for o in [ob] + list(ob.children_recursive)
           if o.type == "MESH" and o.data is not None and not o.get(build.PROP_EXCLUDED)]
    if not obs:
        return ob.matrix_world.translation.copy()
    pts = []
    for o in obs:
        mw = o.matrix_world
        pts += [mw @ Vector(c) for c in o.bound_box]
    arr = np.array([tuple(p) for p in pts])
    return Vector(((arr.min(axis=0) + arr.max(axis=0)) / 2).tolist())


# ---------------------------------------------------------------------------
# the plan of one step
# ---------------------------------------------------------------------------

def plan(ctx: Context, anim, b, cur, f0: int, f1: int, warnings: list):
    """(state at a frame of the step, state at its end) for a new camera step starting from ``cur`` (a CamState),
    or None when it cannot be done (a warning says why)."""
    from . import animation
    CamState = animation.CamState
    name = animation.block_label(b)
    f1 = max(f1, f0)
    aim = b.aim_uid if looks_at_part(b) else ""
    if looks_at_part(b) and not ctx.has(aim):
        return None                                  # (Context warned: not picked or not found)
    if b.camera_mode == "RIDE" and not ctx.has(b.target_uid):
        return None

    if b.camera_mode == "RIDE":
        uid = b.target_uid
        p0 = ctx.world(uid, f0)
        if b.ride_camera is not None and b.ride_camera.type == "CAMERA":
            base = CamState.of(b.ride_camera)
            offset = ctx.at_build[uid].inverted_safe() @ base.matrix
        else:
            base = cur
            offset = p0.inverted_safe() @ cur.matrix
        start = p0 @ offset
        start_rot = _rotation(start)
        r0_inv = _rotation(p0).transposed()

        def target(f):
            pf = ctx.world(uid, f)
            m = pf @ offset
            pos = m.translation.copy()
            if b.ride_look == "PART":
                pt = ctx.point(aim, f)
                return CamState(look_at(pos, pt), base.lens, base.ortho_scale, max(0.001, (pt - pos).length),
                                base.type)
            if b.ride_level:
                yaw = P.heading(np.array(_rotation(pf) @ r0_inv))
                m = Matrix.Translation(pos) @ (Matrix.Rotation(yaw, 3, "Z") @ start_rot).to_4x4()
            else:
                m = Matrix.Translation(pos) @ _rotation(m).to_4x4()
            return CamState(m, base.lens, base.ortho_scale, base.focus, base.type)

    elif b.camera_mode == "AIM":
        pos = cur.matrix.translation.copy()

        def target(f):
            pt = ctx.point(aim, f)
            return CamState(look_at(pos, pt), cur.lens, cur.ortho_scale, max(0.001, (pt - pos).length), cur.type)

    else:                                                        # PATH
        pts = [tuple(p.co) for p in b.path_points]
        if b.path_from_here:
            pts = [tuple(cur.matrix.translation)] + pts
        try:
            path = P.Path(pts)
        except ValueError:
            warnings.append(f"'{name}': the path needs at least "
                            f"{'one point' if b.path_from_here else 'two points'} (Make path from saved cameras, "
                            "or Add this view)")
            return None
        up, down = P.ramp_shares(b.easing, b.ramp, b.duration)
        span = max(1, f1 - f0)

        def target(f):
            s = P.ramped((f - f0) / span, up, down) * path.length
            pos = Vector(path.point(s).tolist())
            if b.path_look == "PART":
                pt = ctx.point(aim, f)
            elif b.path_look == "MODEL":
                pt = ctx.centre
            else:
                pt = pos + Vector(path.direction(s).tolist())
            focus = cur.focus if b.path_look == "AHEAD" else max(0.001, (pt - pos).length)
            return CamState(look_at(pos, pt), cur.lens, cur.ortho_scale, focus, cur.type)

    fps = animation.fps_of(anim)
    nb = int(round(max(0.0, b.cam_blend) * fps))
    first = target(f0)

    def at(f):
        st = target(f)
        if nb > 0 and f < f0 + nb:
            return glide(cur, first, st, 1.0 - animation.ease("SMOOTH", (f - f0) / nb))
        return st

    return at, at(f1)


def glide(cur, first, st, k: float):
    """``st`` with ``k`` (1 … 0) of the difference between where the camera was (``cur``) and where the step starts
    (``first``) added: at the step's first frame exactly ``cur``, then the difference fades away. A step that starts
    where the camera is moves exactly as it would without the blend (a ride stays on its part)."""
    from . import animation
    la, ra, _ = cur.matrix.decompose()
    lf, rf, _ = first.matrix.decompose()
    ls, rs, _ = st.matrix.decompose()
    loc = ls + (la - lf) * k
    delta = rf.rotation_difference(ra)                 # first @ delta = cur (in the camera's own frame)
    rot = rs @ Quaternion().slerp(delta, k)
    m = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
    fa, ff, fs = (math.atan(18.0 / x.lens) for x in (cur, first, st))
    lens = 18.0 / math.tan(fs + (fa - ff) * k)
    return animation.CamState(m, lens, st.ortho_scale + (cur.ortho_scale - first.ortho_scale) * k,
                              max(0.001, st.focus + (cur.focus - first.focus) * k), cur.type if k >= 1.0 else st.type)


# ---------------------------------------------------------------------------
# the path shown in the view
# ---------------------------------------------------------------------------

def show_path(scene, b) -> bpy.types.Object | None:
    """Make (or update) the curve that shows a Fly a path step's path in the view; it never renders."""
    from . import cameras
    pts = [tuple(p.co) for p in b.path_points]
    ob = b.path_obj
    if not pts:
        if ob is not None:
            remove_path(b)
        return None
    try:
        line = P.Path(pts).dense[::8].tolist() + [pts[-1]] if len(P.clean(pts)) > 1 else pts
    except ValueError:
        line = pts
    if ob is None or ob.name not in bpy.data.objects or ob.type != "CURVE":
        cu = bpy.data.curves.new("Camera path", "CURVE")
        cu.dimensions = "3D"
        ob = bpy.data.objects.new("Camera path", cu)
        ob[PROP_PATH] = True
        ob["fr_helper"] = True
        b.path_obj = ob
    col = cameras.collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    cu = ob.data
    cu.splines.clear()
    sp = cu.splines.new("POLY")
    sp.points.add(len(line) - 1)
    sp.points.foreach_set("co", [c for p in line for c in (p[0], p[1], p[2], 1.0)])
    ob.matrix_world = Matrix.Identity(4)
    ob.hide_render = True
    ob.hide_select = True
    ob.show_in_front = True
    return ob


def remove_path(b) -> None:
    ob = b.path_obj
    b.path_obj = None
    if ob is not None and ob.name in bpy.data.objects:
        cu = ob.data
        bpy.data.objects.remove(ob)
        if cu is not None and cu.users == 0:
            bpy.data.curves.remove(cu)


def copy_path(scene, src, dst) -> None:
    """A duplicated step gets its own copy of the points and its own line in the view."""
    dst.path_obj = None
    dst.path_points.clear()
    for p in src.path_points:
        dst.path_points.add().co = p.co
    show_path(scene, dst)


def tidy_paths(scene) -> None:
    """Remove path curves no step uses any more (a step was deleted or changed mode)."""
    used = {b.path_obj for a in scene.fresing.animations for b in a.blocks
            if b.kind == "CAMERA" and b.camera_mode == "PATH" and b.path_obj is not None}
    for ob in [o for o in bpy.data.objects if o.get(PROP_PATH) and o not in used]:
        cu = ob.data
        bpy.data.objects.remove(ob)
        if cu is not None and cu.users == 0:
            bpy.data.curves.remove(cu)


def view_point(context) -> Vector | None:
    """Where the 3D view looks from (the camera's place when the view looks through a camera)."""
    space = getattr(context, "space_data", None)
    r3d = getattr(space, "region_3d", None) if space is not None and space.type == "VIEW_3D" else None
    if r3d is None:
        for area in getattr(context.screen, "areas", []) if context.screen else []:
            if area.type == "VIEW_3D":
                r3d = area.spaces.active.region_3d
                break
    if r3d is None:
        return None
    if r3d.view_perspective == "CAMERA" and context.scene.camera is not None:
        return context.scene.camera.matrix_world.translation.copy()
    return r3d.view_matrix.inverted().translation.copy()


def from_cameras(scene) -> list:
    """The places of the saved cameras (5 Scene & Render), in their order."""
    from . import cameras
    return [tuple(c.matrix_world.translation) for c in cameras.fr_cameras(scene) if not c.get("fr_anim_camera")]


def angle_between(a: Matrix, b: Matrix) -> float:
    """Degrees between two rotations (for tests and the PC check)."""
    qa = np.array(tuple(a.to_quaternion()), dtype=float)
    qb = np.array(tuple(b.to_quaternion()), dtype=float)
    qa, qb = qa / np.linalg.norm(qa), qb / np.linalg.norm(qb)
    chord = min(np.linalg.norm(qa - qb), np.linalg.norm(qa + qb))     # exact also for tiny angles (acos is not)
    return math.degrees(4 * math.asin(min(1.0, chord / 2)))
