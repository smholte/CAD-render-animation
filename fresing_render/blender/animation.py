"""Animations: a list of timed blocks, turned into ordinary Blender keyframes.

Block kinds
    JOINT   move one joint from a value to a value
    POSE    move every joint and free-moved subassembly to a saved pose (exploded view...)
    CAMERA  cut to a saved camera, move to it, or orbit around the model; ride along a moving part, fly a path,
            or keep a part in the middle (task 0087, camera_path.py)
    SHOW / HIDE   make a subassembly appear or disappear (assembly sequences)
    FADE_OUT / FADE_IN  fade a subassembly away (to nothing or to the X-ray look) or back in (task 0073, fade.py)
    MOTOR   run a motor at a speed (rpm, or mm/s for a slide) for a while, with a ramp
            up and down; joints that follow it move along (their drivers read its keys)
    CYLINDER  move a cylinder's rod from a stroke to a stroke: the arm's joint gets a key on
            every frame, worked out from the stroke (the rod moves at the step's own pace)
    MECHANISM raise a scissor lift's platform from a height to a height
    GCODE   run a CNC program on the machine's X/Y/Z joints and spindle (task 0026, gcode.py); its
            length follows from the program; tool changes can play the tool changer's animation
    SEQUENCE take a subassembly apart part by part, or put it together (task 0100, sequence.py); its length
            follows from the number of parts, the time per part and the overlap

"Build" turns the blocks into keys (joint values, part positions, an animation
camera, visibility). Keys are owned by the app: building again replaces them,
and editing the joint structure clears them (the panel offers to rebuild).
Before building, the current pose, visibility and camera are saved so clearing
the keys puts the model back the way it was.
"""

from __future__ import annotations

import math
import os

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import build, joints, logic, states

TAG = "fr_anim"
ANIM_CAMERA = "Animation camera"

EASING = {
    # block easing -> (Blender interpolation, easing)
    "SMOOTH": ("SINE", "EASE_IN_OUT"),
    "LINEAR": ("LINEAR", "AUTO"),
    "EASE_IN": ("SINE", "EASE_IN"),
    "EASE_OUT": ("SINE", "EASE_OUT"),
}


def ease(kind: str, p: float) -> float:
    p = min(max(p, 0.0), 1.0)
    if kind == "LINEAR":
        return p
    if kind == "EASE_IN":
        return 1.0 - math.cos(p * math.pi / 2)
    if kind == "EASE_OUT":
        return math.sin(p * math.pi / 2)
    return 0.5 - 0.5 * math.cos(math.pi * p)


def fps_of(anim) -> int:
    return int(anim.fps)


def frame_of(anim, seconds: float) -> int:
    return 1 + int(round(max(0.0, seconds) * fps_of(anim)))


def is_instant(b) -> bool:
    return b.kind in ("SHOW", "HIDE") or (b.kind == "CAMERA" and b.camera_mode == "CUT")


def block_end(b) -> float:
    return b.start if is_instant(b) else b.start + b.duration


def length_seconds(anim) -> float:
    ends = [block_end(b) for b in anim.blocks if b.enabled]
    if not ends:
        return 1.0
    return max(1.0 / fps_of(anim), max(ends) + anim.tail)


def block_label(b, scene=None) -> str:
    if b.name:
        return b.name
    if b.kind == "JOINT":
        return b.joint or "Joint"
    if b.kind == "MOTOR":
        return f"Run {b.joint}" if b.joint else "Run motor"
    if b.kind == "CYLINDER":
        return f"Move {b.cylinder}" if b.cylinder else "Move cylinder"
    if b.kind == "MECHANISM":
        return f"Lift {b.mechanism}" if b.mechanism else "Lift height"
    if b.kind == "GCODE":
        f = os.path.basename(bpy.path.abspath(b.gcode_file)) if b.gcode_file else ""
        return f"Run {f}" if f else "Run G-code program"
    if b.kind == "POSE":
        return f"To pose {b.pose}" if b.pose else "To pose"
    if b.kind == "CAMERA":
        if b.camera_mode in ("RIDE", "PATH", "AIM"):
            from . import camera_path
            return camera_path.label(b)
        cam = b.camera.name if b.camera else "?"
        return {"CUT": f"Cut to {cam}", "MOVE": f"Camera to {cam}",
                "ORBIT": f"Orbit {math.degrees(b.orbit_angle):.0f}°"}.get(b.camera_mode, "Camera")
    target = b.target_name or "?"
    if b.kind == "FADE_OUT":
        return f"Fade {target} to X-ray" if b.fade_xray else f"Fade out {target}"
    if b.kind == "FADE_IN":
        return f"Fade in {target}"
    if b.kind == "SEQUENCE":
        from . import sequence
        return sequence.label(b)
    return f"{'Show' if b.kind == 'SHOW' else 'Hide'} {target}"


def fade_ends(b) -> tuple[float, float]:
    """(fade at the start, fade at the end) of a Fade step: 0 = the part as it is, 1 = gone (or fully X-ray)."""
    rest = 1.0 - min(max(float(b.fade_stop), 0.0), 100.0) / 100.0      # where the faded end lies
    return (0.0, rest) if b.kind == "FADE_OUT" else (rest, 0.0)


# ---------------------------------------------------------------------------
# Run motor: speed profile
# ---------------------------------------------------------------------------

def motor_ramps(b) -> tuple[float, float]:
    """(ramp up, ramp down) in seconds for a Run motor step; together never longer than the step."""
    r = max(0.0, float(b.ramp))
    up = r if b.easing in ("SMOOTH", "EASE_IN") else 0.0
    down = r if b.easing in ("SMOOTH", "EASE_OUT") else 0.0
    total = max(0.0, float(b.duration))
    if up + down > total > 0.0:                 # ramps longer than the step: shrink both in proportion
        k = total / (up + down)
        up, down = up * k, down * k
    elif total <= 0.0:
        up = down = 0.0
    return up, down


def motor_speed(j, b) -> float:
    """Speed of a Run motor step in internal units per second (rad/s for a rotate joint, m/s for a slide)."""
    if j.kind == "ROTATE":
        return float(b.speed_rpm) * joints.TURN / 60.0
    return float(b.speed_mms) / 1000.0


def motor_distance(speed: float, duration: float, up: float, down: float, t: float) -> float:
    """How far a motor has gone ``t`` seconds into the step: the speed rises evenly during ``up``,
    stays, and falls evenly during ``down`` (internal units)."""
    t = min(max(t, 0.0), duration)
    if up > 0.0 and t <= up:
        return speed * t * t / (2.0 * up)
    gone = speed * up / 2.0
    cruise_end = duration - down
    if t <= cruise_end:
        return gone + speed * (t - up)
    gone += speed * (cruise_end - up)
    left = duration - t
    return gone + speed * (down / 2.0 - left * left / (2.0 * down))


def motor_total(j, b) -> float:
    """How far a Run motor step takes its joint (rad / m)."""
    up, down = motor_ramps(b)
    d = max(0.0, float(b.duration))
    return motor_distance(motor_speed(j, b), d, up, down, d)


# ---------------------------------------------------------------------------
# keyframe plumbing (Blender 4.4+ layered actions)
# ---------------------------------------------------------------------------


def _channelbag(id_block, id_type: str):
    from bpy_extras import anim_utils
    ad = id_block.animation_data or id_block.animation_data_create()
    act = ad.action
    if act is None or not act.get(TAG):
        act = bpy.data.actions.new(f"FR {id_block.name}")
        act[TAG] = True
        ad.action = act
    slot = ad.action_slot
    if slot is None:
        slot = act.slots.new(id_type=id_type, name=id_block.name)
        ad.action_slot = slot
    id_block[TAG] = True
    return anim_utils.action_ensure_channelbag_for_slot(act, slot)


def _shared_visibility(objs, rows, n: int, fade_rows=None) -> None:
    """One action + slot with hide keys (and fade keys, task 0073), assigned to every object in ``objs``."""
    from bpy_extras import anim_utils
    act = bpy.data.actions.new(f"FR visibility {n + 1}")
    act[TAG] = True
    slot = act.slots.new(id_type="OBJECT", name=f"Visibility {n + 1}")
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    if rows:
        _write(cb, "hide_viewport", 0, rows)
        _write(cb, "hide_render", 0, rows)
    if fade_rows:
        _write(cb, '["fr_fade"]', 0, list(fade_rows))
    for ob in objs:
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = act
        ad.action_slot = slot
        ob[TAG] = True


def _write(cb, path: str, index: int, keys) -> None:
    """keys: list of (frame, value, interpolation, easing)."""
    fc = cb.fcurves.find(path, index=index)
    if fc is not None:
        cb.fcurves.remove(fc)
    fc = cb.fcurves.new(path, index=index)
    pts = fc.keyframe_points
    pts.add(len(keys))
    pts.foreach_set("co", [c for k in keys for c in (float(k[0]), float(k[1]))])
    for kp, k in zip(pts, keys):
        kp.interpolation = k[2]
        if k[2] not in ("CONSTANT", "LINEAR", "BEZIER"):
            kp.easing = k[3]
        kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    # not fc.update(): it merges keys less than 0.01 frame apart, and a G-code program played fast has moves that
    # short - a lift, a move over and the way down became one straight cut through the part (task 0029)
    pts.sort()
    pts.handles_recalc()


def _merge(keys: list, frame: int, value, interp: str, easing: str = "AUTO") -> None:
    """Add a key; a key on the same frame is replaced."""
    if keys and keys[-1][0] == frame:
        keys[-1] = (frame, value, interp, easing)
    elif keys and keys[-1][0] > frame:
        keys[:] = [k for k in keys if k[0] < frame]
        keys.append((frame, value, interp, easing))
    else:
        keys.append((frame, value, interp, easing))


def has_keys(scene) -> bool:
    return bool(scene.fresing.anim_baked)


def clear_keys(scene, restore: bool = True) -> None:
    """Remove every key made by 'Build animation' and put the model back as it was."""
    s = scene.fresing
    was_baked = bool(s.anim_baked)
    for ob in list(scene.objects):
        if ob.get(TAG):
            _drop_action(ob)
            del ob[TAG]
            if ob.get("fr_anim_hide"):
                if ob.hide_viewport:
                    ob.hide_viewport = False
                del ob["fr_anim_hide"]
        if ob.type == "CAMERA" and ob.data is not None and ob.data.get(TAG):
            _drop_action(ob.data)
            del ob.data[TAG]
    orphans = [a for a in bpy.data.actions if a.get(TAG) and a.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)          # one by one is slow with thousands of actions
    s.anim_baked = ""
    if was_baked:
        for m in [m for m in scene.timeline_markers if m.name.startswith("▸ ")]:
            scene.timeline_markers.remove(m)
    if restore and was_baked and s.anim_restore_saved:
        s.anim_restore_saved = False
        # values first, straight into the joints (no cad_pose here: it calls clear_keys)
        values, deltas = states.pose_targets(scene, s.anim_restore_pose)
        for j in s.joints:
            if j.name in values:
                joints.set_value(j, values[j.name], use_limits=False)
        joints.apply_free_moves(scene, deltas, reset_others=True)
        states.apply_visibility_data(scene, s.anim_restore_visibility)
        cam = bpy.data.objects.get(s.anim_restore_camera)
        if cam is not None:
            scene.camera = cam
    from . import fade, gcode, trails
    fade.after_clear(scene)                        # faded parts look as without the animation (task 0073)
    trails.after_clear(scene)
    gcode.after_clear(scene)                       # tool copies shown at tool changes (task 0026)
    from . import flex
    flex.after_clear(scene)                        # hoses and drag chains follow the parts live again (task 0058)
    from . import paths
    paths.after_clear(scene)                       # cables follow their sheaves live again (task 0078)
    if was_baked:
        from . import linkages
        linkages.refresh_all(scene, force=True)    # the links kept the place of the last frame shown
    if restore and was_baked:
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass


def _drop_action(id_block) -> None:
    ad = id_block.animation_data
    if ad is None:
        return
    ad.action = None                         # the action itself is removed in one batch afterwards


# ---------------------------------------------------------------------------
# camera state
# ---------------------------------------------------------------------------


class CamState:
    def __init__(self, matrix: Matrix, lens: float, ortho_scale: float, focus: float, cam_type: str):
        self.matrix = matrix.copy()
        self.lens = lens
        self.ortho_scale = ortho_scale
        self.focus = focus
        self.type = cam_type

    @classmethod
    def of(cls, ob) -> CamState:
        d = ob.data
        return cls(ob.matrix_world, d.lens, d.ortho_scale, d.dof.focus_distance, d.type)

    def blend(self, other: CamState, p: float) -> CamState:
        la, ra, _ = self.matrix.decompose()
        lb, rb, _ = other.matrix.decompose()
        loc = la.lerp(lb, p)
        rot = ra.slerp(rb, p)
        m = Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
        # lens: interpolate the field of view, which looks like a natural zoom
        fa, fb = math.atan(18.0 / self.lens), math.atan(18.0 / other.lens)
        lens = 18.0 / math.tan(fa + (fb - fa) * p)
        t = self.type if p < 1.0 else other.type
        return CamState(m, lens, self.ortho_scale + (other.ortho_scale - self.ortho_scale) * p,
                        self.focus + (other.focus - self.focus) * p, t)

    def orbited(self, centre: Vector, angle: float) -> CamState:
        rot = Matrix.Translation(centre) @ Matrix.Rotation(angle, 4, "Z") @ Matrix.Translation(-centre)
        out = CamState(rot @ self.matrix, self.lens, self.ortho_scale, self.focus, self.type)
        return out


def _camera_track(anim, segs, start: CamState, centre: Vector, f_end: int, ctx=None,
                  warnings: list | None = None) -> list[CamState]:
    """Camera state for every frame 1..f_end. ``ctx`` (camera_path.Context) is needed by the steps that ride along,
    fly a path or keep a part in the middle (task 0087); without it they are left out."""
    plan = []                     # (f0, f1, state at a frame of the step, end state)
    cur = start
    for b in segs:
        f0, f1 = frame_of(anim, b.start), frame_of(anim, b.start + b.duration)
        if b.camera_mode in ("RIDE", "PATH", "AIM"):
            if ctx is None:
                continue
            from . import camera_path
            got = camera_path.plan(ctx, anim, b, cur, f0, f1, warnings if warnings is not None else [])
            if got is None:
                continue
            at, end = got
            plan.append((f0, max(f1, f0), at, end))
            cur = end
            continue
        if b.camera_mode == "ORBIT":
            end = cur.orbited(centre, b.orbit_angle)
        elif b.camera is not None and b.camera.type == "CAMERA":
            end = CamState.of(b.camera)
        else:
            continue
        if b.camera_mode == "CUT":
            f1 = f0
        f1 = max(f1, f0)

        def at(f, a=cur, b_end=end, f0=f0, f1=f1, mode=b.camera_mode, angle=b.orbit_angle, easing=b.easing):
            p = ease(easing, (f - f0) / max(1, f1 - f0))
            return a.orbited(centre, angle * p) if mode == "ORBIT" else a.blend(b_end, p)
        plan.append((f0, f1, at, end))
        cur = end
    out = []
    for f in range(1, f_end + 1):
        st = start
        for f0, f1, at, b_end in plan:
            if f < f0:
                break
            if f >= f1:
                st = b_end
                continue
            st = at(f)
        out.append(st)
    return out


def _cameras_of(scene, anim) -> list:
    """The start camera and every camera a Move to / Cut step goes to."""
    out = [scene.camera] if scene.camera is not None and scene.camera.type == "CAMERA" else []
    for b in anim.blocks:
        cam = b.ride_camera if b.camera_mode == "RIDE" else b.camera if b.camera_mode in ("CUT", "MOVE") else None
        if b.enabled and b.kind == "CAMERA" and cam is not None and cam.type == "CAMERA" and cam not in out:
            out.append(cam)
    return out


def _fresh_blur(scene, anim) -> None:
    """The sharp distance of every camera of the animation, worked out again now that the start scene's pose is on:
    the copy stored on the camera was made where its sharp-spot part was then (bug hunt row 10)."""
    from . import cameras
    for cam in _cameras_of(scene, anim):
        if not cam.get("fr_anim_camera"):
            cameras.update_blur(cam, scene)


def _one_marker(start_cam, cam_blocks):
    """The sharp-spot marker every camera of the move shares, or None (no spot, or cameras with different ones)."""
    from . import cameras
    cams = [start_cam] + [b.camera for b in cam_blocks if b.camera_mode in ("CUT", "MOVE") and b.camera is not None
                          and b.camera.type == "CAMERA"]
    cams += [b.ride_camera for b in cam_blocks if b.camera_mode == "RIDE" and b.ride_camera is not None
             and b.ride_camera.type == "CAMERA"]
    markers = {cameras.focus_marker(c) for c in cams}
    return markers.pop() if len(markers) == 1 else None


def _anim_camera(scene, like) -> bpy.types.Object:
    from . import cameras
    ob = next((o for o in bpy.data.objects if o.get("fr_anim_camera")), None)
    if ob is None:
        data = bpy.data.cameras.new(ANIM_CAMERA)
        ob = bpy.data.objects.new(ANIM_CAMERA, data)
        ob["fr_anim_camera"] = True
        cameras.collection(scene).objects.link(ob)
    elif ob.name not in scene.objects:
        cameras.collection(scene).objects.link(ob)
    d, src = ob.data, like.data
    d.type = src.type
    d.display_size = src.display_size
    d.sensor_width, d.sensor_height, d.sensor_fit = src.sensor_width, src.sensor_height, src.sensor_fit
    d.clip_start, d.clip_end = src.clip_start, src.clip_end
    d.dof.use_dof = src.dof.use_dof
    d.dof.aperture_fstop = src.dof.aperture_fstop
    ob.rotation_mode = "QUATERNION"
    return ob


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------


def _model_centre(scene) -> Vector:
    mn, mx = logic.update_bounds(scene)
    return Vector(((mn + mx) / 2).tolist())


def _block_values(j, b) -> tuple[float, float]:
    if j.kind == "ROTATE":
        return b.from_angle, b.to_angle
    return b.from_dist, b.to_dist


def bake(scene, anim) -> dict:
    """Turn the blocks of ``anim`` into keyframes. Returns {'frames', 'seconds', 'warnings'}."""
    s = scene.fresing
    from . import sequence
    sequence.end_preview(scene)          # parts an Assembly sequence preview moved go back first (task 0100)
    clear_keys(scene)
    warnings: list[str] = []

    # remember the static state so 'Clear keys' can put it back
    states.capture_pose(scene, s.anim_restore_pose)
    states.capture_visibility(scene, s.anim_restore_visibility)
    s.anim_restore_camera = scene.camera.name if scene.camera else ""
    s.anim_restore_saved = True

    if anim.start_shot:
        warnings += states.apply_shot(scene, anim.start_shot)
    bpy.context.view_layer.update()
    _fresh_blur(scene, anim)

    from . import gcode
    atc_blocks = gcode.prepare(scene, anim, warnings)    # G-code steps: their length from the program
    sequence.prepare(scene, anim)                        # Assembly sequence steps: their length from the parts
    sequence.tidy_trails(scene)
    fps = fps_of(anim)
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    seconds = length_seconds(anim)
    f_end = frame_of(anim, seconds)
    scene.frame_start = 1
    scene.frame_end = f_end

    # joints that follow another one get their place from it (drivers): no keys, no state of their own
    jstate = {j.name: joints.get_value(j) for j in s.joints if not j.follows}
    ostate = {n: d for n, d in joints.free_moves(scene).items()}
    jkeys: dict[str, list] = {}
    okeys: dict[str, list] = {}
    vkeys: dict[str, list] = {}
    fkeys: dict[str, list] = {}          # fade (task 0073): name -> [(frame, fade, interp, easing)]
    fxray: dict[str, tuple] = {}         # name -> (X-ray on, colour, strength)
    tree = logic.Tree(scene)
    uids = states.by_uid(scene)
    ident = Matrix.Identity(4)

    busy_until: dict[str, int] = {}
    seq_home: dict = {}                  # Assembly sequence: a part's place before a Take apart step moved it

    def joint_move(j, v_from, v_to, f0, f1, easing):
        if busy_until.get(j.name, 0) > f0:
            warnings.append(f"Two steps move '{j.name}' at the same time; the later one takes over")
        busy_until[j.name] = max(f1, f0 + 1)
        keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
        interp, ez = EASING.get(easing, EASING["SMOOTH"])
        _merge(keys, f0, v_from, interp, ez)
        _merge(keys, max(f1, f0 + 1), v_to, "CONSTANT")
        jstate[j.name] = v_to

    def object_move(name, d_from, d_to, f0, f1, easing):
        keys = okeys.setdefault(name, [(1, ostate.get(name, ident), "CONSTANT", "AUTO")])
        interp, ez = EASING.get(easing, EASING["SMOOTH"])
        _merge(keys, f0, d_from, interp, ez)
        _merge(keys, max(f1, f0 + 1), d_to, "CONSTANT")
        ostate[name] = d_to

    def motor_run(j, b, f0, f1):
        """Keys for a Run motor step: one per frame while the speed changes, two for the even part."""
        if busy_until.get(j.name, 0) > f0:
            warnings.append(f"Two steps move '{j.name}' at the same time; the later one takes over")
        busy_until[j.name] = max(f1, f0 + 1)
        keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
        v0 = jstate[j.name]
        speed, total = motor_speed(j, b), max(0.0, float(b.duration))
        up, down = motor_ramps(b)
        span = max(1, f1 - f0)
        fps = fps_of(anim)
        frames = {f0, f0 + span}
        if up > 0.0 or down > 0.0:
            n_up, n_down = int(math.ceil(up * fps)) + 1, int(math.ceil(down * fps)) + 1
            frames |= {f for f in range(f0, f0 + span + 1) if f - f0 <= n_up or f0 + span - f <= n_down}
        lo, hi = joints.limits(j)

        def value_at(f):
            t = (f - f0) / span * total             # the step ends exactly on its last frame
            return v0 + motor_distance(speed, total, up, down, t)

        stopped = any(not lo <= value_at(f) <= hi for f in frames)
        if stopped:                                 # a key on every frame: it really stops at the limit
            frames = set(range(f0, f0 + span + 1))
        rows = [(f, min(max(value_at(f), lo), hi)) for f in sorted(frames)]
        for f, v in rows[:-1]:
            _merge(keys, f, v, "LINEAR")
        _merge(keys, rows[-1][0], rows[-1][1], "CONSTANT")
        jstate[j.name] = rows[-1][1]
        if stopped:
            hint = " (tick 'Motor' on it in 4 Motion to let it turn without end)" if j.kind == "ROTATE" else ""
            warnings.append(f"'{block_label(b)}': '{j.name}' reaches its limit and stops there{hint}")

    def cylinder_move(b, f0, f1):
        """Keys for a Move cylinder step: the stroke eases from -> to, the arm's joint gets its value on
        every frame (exact: the joint's angle is not a straight line of the stroke)."""
        from . import cylinders
        c = cylinders.find(scene, b.cylinder) if b.cylinder else None
        if c is None:
            warnings.append(f"'{block_label(b)}': cylinder '{b.cylinder}' not found" if b.cylinder else
                            f"'{block_label(b)}': pick a cylinder")
            return
        j, reason = cylinders.arm_joint(scene, c)
        if j is None:
            warnings.append(f"'{block_label(b)}': {reason}")
            return
        try:
            d = cylinders.drive(scene, c, j)
        except RuntimeError as exc:
            warnings.append(f"'{block_label(b)}': {exc}")
            return
        if busy_until.get(j.name, 0) > f0:
            warnings.append(f"Two steps move '{j.name}' at the same time; the later one takes over")
        span = max(1, f1 - f0)
        busy_until[j.name] = max(busy_until.get(j.name, 0), f0 + span)
        closed, full = c.closed_length, c.full_stroke
        s0 = d.length_at(jstate[j.name]) - closed if b.use_from else b.from_stroke
        s1 = b.to_stroke
        if outside(s0, full) or outside(s1, full):
            warnings.append(f"'{block_label(b)}': the stroke goes beyond 0 … {full * 1000:.0f} mm; it stops "
                            "at the end of the cylinder")
        s0, s1 = min(max(s0, 0.0), full), min(max(s1, 0.0), full)
        keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
        v = jstate[j.name]
        for f in range(f0, f0 + span + 1):
            stroke = s0 + (s1 - s0) * ease(b.easing, (f - f0) / span)
            v = joints.clamp(j, d.value_for(closed + stroke))
            _merge(keys, f, v, "LINEAR" if f < f0 + span else "CONSTANT")
        jstate[j.name] = v

    def mechanism_move(b, f0, f1):
        """Keys for a Lift height step: the platform's height eases from -> to, the drive joint gets its value
        on every frame (worked out by the mechanism's solver, walking along)."""
        from ..core import linkages as K
        from . import linkages
        m = linkages.find(scene, b.mechanism) if b.mechanism else None
        if m is None:
            warnings.append(f"'{block_label(b)}': mechanism '{b.mechanism}' not found" if b.mechanism else
                            f"'{block_label(b)}': pick a mechanism")
            return
        if not linkages.is_valid(m) or not linkages.has_height(m):
            warnings.append(f"'{block_label(b)}': '{m.name}' has no platform height (only scissor lifts do)"
                            if linkages.is_valid(m) else f"'{block_label(b)}': '{m.name}' is broken")
            return
        j = linkages.input_joint(scene, m)
        if j.follows:
            warnings.append(f"'{block_label(b)}': '{j.name}' follows another joint: move that one instead")
            return
        if busy_until.get(j.name, 0) > f0:
            warnings.append(f"Two steps move '{j.name}' at the same time; the later one takes over")
        span = max(1, f1 - f0)
        busy_until[j.name] = max(busy_until.get(j.name, 0), f0 + span)
        _lk, h, sign = linkages.linkage_of(m)
        lo, hi = sorted(sign * x for x in joints.limits(j))
        sol = linkages.solver(m).copy()
        try:
            sol.solve(sign * jstate[j.name])
        except K.Unreachable:
            pass
        h0 = h.of(sol.poses) if b.use_from else b.from_height
        keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
        short = ""
        v = sign * sol.value
        for f in range(f0, f0 + span + 1):
            target = h0 + (b.to_height - h0) * ease(b.easing, (f - f0) / span)
            try:
                v = sign * sol.value_for(h, target, lo, hi)
            except K.Unreachable as exc:
                short = short or str(exc)
                v = sign * sol.value
            _merge(keys, f, v, "LINEAR" if f < f0 + span else "CONSTANT")
        jstate[j.name] = v
        if short:
            warnings.append(f"'{block_label(b)}': the platform cannot reach {b.to_height * 1000:.0f} mm "
                            f"({short}); it stops at {h.of(sol.poses) * 1000:.0f} mm")

    def outside(stroke, full):
        return stroke < -1e-6 or stroke > full + 1e-6

    def free_joint(b):
        """The joint a JOINT or MOTOR step moves, or None (with a warning) when it cannot."""
        j = s.joints.get(b.joint)
        if j is None:
            warnings.append(f"'{block_label(b)}': joint '{b.joint}' not found" if b.joint else
                            f"'{block_label(b)}': pick a joint")
            return None
        if j.follows:
            top = joints.driver_of(scene, j)
            who = f"'{top.name}'" if top is not None else "the joint it follows"
            warnings.append(f"'{block_label(b)}': '{j.name}' follows another joint and moves with it: "
                            f"move {who} instead")
            return None
        return j

    def fade_step(b, f0, f1):
        """Keys for a Fade step: the fade of every part of the subassembly (and its decals) eases from -> to; a
        part faded out fully is hidden from the last frame on, a part faded in shows from the first."""
        from . import fade
        ob = uids.get(b.target_uid)
        if ob is None:
            warnings.append(f"'{block_label(b)}': subassembly not found" if b.target_uid else
                            f"'{block_label(b)}': pick a subassembly")
            return
        v0, v1 = fade_ends(b)
        f1 = max(f1, f0 + 1)
        interp, ez = EASING.get(b.easing, EASING["SMOOTH"])
        xray = (bool(b.fade_xray), tuple(b.fade_color), float(b.fade_strength))
        gone = not b.fade_xray and max(v0, v1) >= 1.0 - 1e-9
        for t in [ob] + tree.descendants(ob):
            if t.get(build.PROP_EXCLUDED) or t.type != "MESH":
                continue
            for o in fade.prepare(t):
                if o.name in fxray and fxray[o.name][0] != xray[0]:
                    warnings.append(f"'{block_label(b)}': '{o.get(build.PROP_NAME, o.name)}' fades to X-ray in one "
                                    "step and to nothing in another: the last one counts")
                fxray[o.name] = xray
                start = float(o.get(fade.FADE, 0.0)) if not o.get(fade.LOOK) else 0.0
                if b.kind == "FADE_IN":
                    start = v0                       # (before the step it is faded, or hidden)
                keys = fkeys.setdefault(o.name, [(1, start, "CONSTANT", "AUTO")])
                _merge(keys, f0, v0, interp, ez)
                _merge(keys, f1, v1, "CONSTANT")
            if not gone:
                if b.kind == "FADE_IN":
                    keys = vkeys.setdefault(t.name, [(1, bool(t.hide_render), "CONSTANT", "AUTO")])
                    _merge(keys, f0, False, "CONSTANT")
                continue
            if b.kind == "FADE_OUT":
                keys = vkeys.setdefault(t.name, [(1, bool(t.hide_render), "CONSTANT", "AUTO")])
                _merge(keys, f1, True, "CONSTANT")
            else:                                    # it was not there before: hidden until the fade starts
                keys = vkeys.setdefault(t.name, [(1, True, "CONSTANT", "AUTO")])
                _merge(keys, f0, False, "CONSTANT")

    cam_blocks = []
    blocks = sorted((b for b in anim.blocks if b.enabled), key=lambda b: b.start)
    last_key = 0.0
    for b in sorted(blocks + atc_blocks, key=lambda b: b.start):
        f0, f1 = frame_of(anim, b.start), frame_of(anim, b.start + b.duration)
        if b.kind == "JOINT":
            j = free_joint(b)
            if j is None:
                continue
            a, z = _block_values(j, b)
            v_from = jstate[j.name] if b.use_from else joints.clamp(j, a)
            joint_move(j, v_from, joints.clamp(j, z), f0, f1, b.easing)
        elif b.kind == "MOTOR":
            j = free_joint(b)
            if j is None or b.duration <= 0.0:          # (a run of 0 s does nothing)
                continue
            motor_run(j, b, f0, f1)
        elif b.kind == "CYLINDER":
            cylinder_move(b, f0, f1)
        elif b.kind == "MECHANISM":
            mechanism_move(b, f0, f1)
        elif b.kind == "GCODE":
            last_key = max(last_key, gcode.bake_step(scene, anim, b, f0, jstate, jkeys, vkeys, busy_until, warnings,
                                                     _merge))
        elif b.kind == "POSE":
            pose = s.poses.get(b.pose)
            if pose is None:
                warnings.append(f"'{block_label(b)}': pose '{b.pose}' not found")
                continue
            values, deltas = states.pose_targets(scene, pose)
            for j in s.joints:
                if j.follows:                       # (a pose saved before it followed another joint)
                    continue
                if j.name in values and abs(values[j.name] - jstate[j.name]) > 1e-9:
                    joint_move(j, jstate[j.name], joints.clamp(j, values[j.name]), f0, f1, b.easing)
            for name in set(ostate) | set(deltas):
                d_from, d_to = ostate.get(name, ident), deltas.get(name, ident)
                if any(abs(d_from[r][c] - d_to[r][c]) > 1e-9 for r in range(4) for c in range(4)):
                    object_move(name, d_from, d_to, f0, f1, b.easing)
        elif b.kind == "CAMERA":
            cam_blocks.append(b)
        elif b.kind in ("SHOW", "HIDE"):
            ob = uids.get(b.target_uid)
            if ob is None:
                warnings.append(f"'{block_label(b)}': subassembly not found")
                continue
            hidden = b.kind == "HIDE"
            for t in [ob] + tree.descendants(ob):
                if t.get(build.PROP_EXCLUDED):
                    continue
                keys = vkeys.setdefault(t.name, [(1, bool(t.hide_render), "CONSTANT", "AUTO")])
                _merge(keys, f0, hidden, "CONSTANT")
        elif b.kind in ("FADE_OUT", "FADE_IN"):
            fade_step(b, f0, f1)
        elif b.kind == "SEQUENCE":
            sequence.bake_step(scene, b, f0, sequence.Keys(anim, jstate, ostate, okeys, vkeys, fkeys, fxray,
                                                            seq_home, _merge, warnings, uids, tree))

    if last_key > f_end + 1e-6:             # a program step ran a little longer than worked out first
        f_end = int(math.ceil(last_key - 1e-6))
        scene.frame_end = f_end
        seconds = (f_end - 1) / fps

    # ---- joints that follow: their limits only warn ---------------------------
    # A follower is a straight-line function of the joint at the top of its chain, so its extremes
    # are at that joint's keys (the motion between two keys never turns back).
    for f in s.joints:
        if not f.follows or not f.use_limits:
            continue
        top = joints.driver_of(scene, f)
        if top is None or top.name not in jstate:
            continue
        seen = [k[1] for k in jkeys.get(top.name, [])] or [jstate[top.name]]
        if any(joints.outside_limits(f, joints.driven_value(scene, f, {top.name: v})) for v in seen):
            warnings.append(f"'{f.name}' follows '{top.name}' and goes beyond its own limits "
                            "(check the ratio, or the limits of either joint)")

    # ---- write keys ----------------------------------------------------------
    by_name = {o.name: o for o in scene.objects}         # objects.get() searches every time
    for name, keys in jkeys.items():
        j = s.joints.get(name)
        if j is None or j.motion is None:
            continue
        cb = _channelbag(j.motion, "OBJECT")
        _write(cb, f'["{joints.VALUE}"]', 0, keys)
    warnings += _mechanism_keys(scene, jkeys, f_end)
    for name, keys in okeys.items():
        ob = by_name.get(name)
        if ob is None:
            continue
        rest = build.rest_basis(ob)
        q_prev = None
        rows = []
        for f, delta, interp, ez in keys:
            loc, rot, _sc = (rest @ delta).decompose()
            if q_prev is not None and q_prev.dot(rot) < 0:
                rot = Quaternion((-rot.w, -rot.x, -rot.y, -rot.z))
            q_prev = rot
            rows.append((f, loc, rot, interp, ez))
        ob.rotation_mode = "QUATERNION"
        cb = _channelbag(ob, "OBJECT")
        for i in range(3):
            _write(cb, "location", i, [(f, loc[i], it, ez) for f, loc, _r, it, ez in rows])
        for i in range(4):
            _write(cb, "rotation_quaternion", i, [(f, rot[i], it, ez) for f, _l, rot, it, ez in rows])
    # Parts that only appear/disappear (or fade), all at the same moments, share ONE action and slot:
    # a subassembly of 1,000 parts then costs one action instead of 1,000.
    from . import fade
    shared: dict[tuple, list] = {}
    for name, (on, color, strength) in fxray.items():
        ob = by_name.get(name)
        if ob is not None:
            fade.set_xray(ob, on, color, strength)
            ob[fade.ANIM] = True
    for name in set(vkeys) | set(fkeys):
        ob = by_name.get(name)
        if ob is None:
            continue
        rows, frows = None, None
        if name in vkeys:
            try:
                if ob.hide_get():          # the viewport follows the keys from now on (hide_set is slow)
                    ob.hide_set(False)
            except RuntimeError:
                pass
            ob["fr_anim_hide"] = True
            rows = [(f, 1.0 if h else 0.0, "CONSTANT", "AUTO") for f, h, _i, _e in vkeys[name]]
        if name in fkeys:
            ob[fade.ANIM] = True
            frows = fkeys[name]
        if name in okeys:              # it also moves: its own action holds both
            cb = _channelbag(ob, "OBJECT")
            if rows:
                _write(cb, "hide_viewport", 0, rows)
                _write(cb, "hide_render", 0, rows)
            if frows:
                _write(cb, f'["{fade.FADE}"]', 0, frows)
        else:
            sig = (tuple((r[0], r[1]) for r in rows) if rows else None, tuple(frows) if frows else None)
            shared.setdefault(sig, []).append(ob)
    for n, ((sig, fsig), obs) in enumerate(shared.items()):
        _shared_visibility(obs, [(f, v, "CONSTANT", "AUTO") for f, v in sig] if sig else None, n, fsig)

    # ---- camera -------------------------------------------------------------
    start_cam = scene.camera
    if cam_blocks:
        if start_cam is None or start_cam.type != "CAMERA":
            first = next((b.camera for b in cam_blocks if b.camera is not None), None)
            start_cam = first
        if start_cam is None:
            warnings.append("Camera blocks need a start camera: pick one in the start scene or add a cut")
        else:
            centre = _model_centre(scene)
            ctx = None
            if any(b.camera_mode in ("RIDE", "PATH", "AIM") for b in cam_blocks):
                from . import camera_path
                ctx = camera_path.Context(scene, anim, cam_blocks, uids, centre, warnings)
            track = _camera_track(anim, cam_blocks, CamState.of(start_cam), centre, f_end, ctx, warnings)
            cam = _anim_camera(scene, start_cam)
            cb = _channelbag(cam, "OBJECT")
            rows = []
            q_prev = None
            for f, st in enumerate(track, start=1):
                loc, rot, _sc = st.matrix.decompose()
                if q_prev is not None and q_prev.dot(rot) < 0:
                    rot = Quaternion((-rot.w, -rot.x, -rot.y, -rot.z))
                q_prev = rot
                rows.append((f, loc, rot, st))
            for i in range(3):
                _write(cb, "location", i, [(f, loc[i], "LINEAR", "AUTO") for f, loc, _r, _s in rows])
            for i in range(4):
                _write(cb, "rotation_quaternion", i, [(f, rot[i], "LINEAR", "AUTO") for f, _l, rot, _s in rows])
            dcb = _channelbag(cam.data, "CAMERA")
            _write(dcb, "lens", 0, [(f, st.lens, "LINEAR", "AUTO") for f, _l, _r, st in rows])
            _write(dcb, "ortho_scale", 0, [(f, st.ortho_scale, "LINEAR", "AUTO") for f, _l, _r, st in rows])
            # one sharp spot for the whole move: the camera keeps it in focus on every frame, also while its
            # part moves (bug hunt row 10); otherwise the sharp distance goes from one camera's to the next
            marker = _one_marker(start_cam, cam_blocks)
            if ctx is not None and any(camera_path.looks_at_part(b) or (b.camera_mode == "PATH" and
                                                                         b.path_look == "MODEL")
                                       for b in cam_blocks if b.camera_mode in camera_path.MODES):
                marker = None           # the sharp distance follows the part the camera watches (task 0087)
            cam.data.dof.focus_object = marker
            if cam.data.dof.use_dof and marker is None:
                _write(dcb, "dof.focus_distance", 0, [(f, st.focus, "LINEAR", "AUTO") for f, _l, _r, st in rows])
            scene.camera = cam

    for b in blocks:
        scene.timeline_markers.new("▸ " + block_label(b), frame=frame_of(anim, b.start))
    s.anim_baked = anim.name
    from . import trails
    warnings += trails.update_all(scene, anim)     # trail lines (task 0073): read along the built motion
    from . import flex
    warnings += flex.bake(scene, anim)             # hoses and drag chains (task 0058): every frame's shape
    from . import paths
    warnings += paths.bake(scene, anim)            # cables over sheaves that move (task 0078): every frame's shape
    scene.frame_set(1)
    return {"frames": f_end, "seconds": seconds, "warnings": warnings}


def _mechanism_keys(scene, jkeys: dict, f_end: int) -> list[str]:
    """Mechanisms (task 0014): every link gets its place on every frame its drive joint moves (the solver walks
    along the frames, so it never jumps to another assembly mode). Returns warnings."""
    from ..core import linkages as K
    from . import linkages
    warnings = []
    for m in scene.fresing.mechanisms:
        if not linkages.is_valid(m):
            continue
        j = linkages.input_joint(scene, m)
        top, k, c = joints.chain_affine(scene, j)
        if top is None or top.name not in jkeys or top.motion is None:
            continue                                   # its drive joint does not move: the links stay put
        fc = None
        ad = top.motion.animation_data
        if ad is not None and ad.action is not None:
            cb = _channelbag(top.motion, "OBJECT")
            fc = cb.fcurves.find(f'["{joints.VALUE}"]', index=0)
        if fc is None:
            continue
        _lk, _h, sign = linkages.linkage_of(m)
        sol = linkages.solver(m).copy()
        rows = []
        stuck = ""
        for f in range(1, f_end + 1):
            v = sign * (k * fc.evaluate(f) + c)
            try:
                sol.solve(v)
            except K.Unreachable as exc:
                stuck = stuck or f"frame {f}: {exc}"
            rows.append((f, list(sol.poses)))
        if stuck:
            warnings.append(f"Mechanism '{m.name}' cannot follow its drive joint everywhere ({stuck}); it stops at "
                            "the last position it can reach")
        for idx, ln in enumerate(m.links):
            e = ln.empty
            if e is None:
                continue
            cb = _channelbag(e, "OBJECT")
            for path, i, comp in (("location", 0, 1), ("location", 1, 2), ("rotation_euler", 2, 0)):
                vals = [(f, p[idx][comp]) for f, p in rows]
                keys = [(f, val, "LINEAR", "AUTO") for n, (f, val) in enumerate(vals)
                        if n in (0, len(vals) - 1) or not (abs(val - vals[n - 1][1]) < 1e-12
                                                           and abs(val - vals[n + 1][1]) < 1e-12)]
                _write(cb, path, i, keys)
    return warnings


def active(scene):
    s = scene.fresing
    if 0 <= s.animations_index < len(s.animations):
        return s.animations[s.animations_index]
    return None


def unique_name(scene, base: str = "Animation") -> str:
    names = {a.name for a in scene.fresing.animations}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"
