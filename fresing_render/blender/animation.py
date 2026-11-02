"""Animations: a list of timed blocks, turned into ordinary Blender keyframes.

Block kinds
    JOINT   move one joint from a value to a value
    POSE    move every joint and free-moved subassembly to a saved pose (exploded view...)
    CAMERA  cut to a saved camera, move to it, or orbit around the model
    SHOW / HIDE   make a subassembly appear or disappear (assembly sequences)

"Build" turns the blocks into keys (joint values, part positions, an animation
camera, visibility). Keys are owned by the app: building again replaces them,
and editing the joint structure clears them (the panel offers to rebuild).
Before building, the current pose, visibility and camera are saved so clearing
the keys puts the model back the way it was.
"""

from __future__ import annotations

import math

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
    if b.kind == "POSE":
        return f"To pose {b.pose}" if b.pose else "To pose"
    if b.kind == "CAMERA":
        cam = b.camera.name if b.camera else "?"
        return {"CUT": f"Cut to {cam}", "MOVE": f"Camera to {cam}",
                "ORBIT": f"Orbit {math.degrees(b.orbit_angle):.0f}°"}.get(b.camera_mode, "Camera")
    target = b.target_name or "?"
    return f"{'Show' if b.kind == 'SHOW' else 'Hide'} {target}"


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
    fc.update()


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


def _camera_track(anim, segs, start: CamState, centre: Vector, f_end: int) -> list[CamState]:
    """Camera state for every frame 1..f_end."""
    plan = []                     # (f0, f1, start_state, end_state, mode, angle, easing)
    cur = start
    for b in segs:
        f0, f1 = frame_of(anim, b.start), frame_of(anim, b.start + b.duration)
        if b.camera_mode == "ORBIT":
            end = cur.orbited(centre, b.orbit_angle)
        elif b.camera is not None and b.camera.type == "CAMERA":
            end = CamState.of(b.camera)
        else:
            continue
        if b.camera_mode == "CUT":
            f1 = f0
        plan.append((f0, max(f1, f0), cur, end, b.camera_mode, b.orbit_angle, b.easing))
        cur = end
    out = []
    for f in range(1, f_end + 1):
        st = start
        for f0, f1, a, b_end, mode, angle, easing in plan:
            if f < f0:
                break
            if f >= f1:
                st = b_end
                continue
            p = ease(easing, (f - f0) / max(1, f1 - f0))
            st = a.orbited(centre, angle * p) if mode == "ORBIT" else a.blend(b_end, p)
        out.append(st)
    return out


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

    fps = fps_of(anim)
    scene.render.fps = fps
    scene.render.fps_base = 1.0
    seconds = length_seconds(anim)
    f_end = frame_of(anim, seconds)
    scene.frame_start = 1
    scene.frame_end = f_end

    jstate = {j.name: joints.get_value(j) for j in s.joints}
    ostate = {n: d for n, d in joints.free_moves(scene).items()}
    jkeys: dict[str, list] = {}
    okeys: dict[str, list] = {}
    vkeys: dict[str, list] = {}
    tree = logic.Tree(scene)
    uids = states.by_uid(scene)
    ident = Matrix.Identity(4)

    busy_until: dict[str, int] = {}

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

    cam_blocks = []
    blocks = sorted((b for b in anim.blocks if b.enabled), key=lambda b: b.start)
    for b in blocks:
        f0, f1 = frame_of(anim, b.start), frame_of(anim, b.start + b.duration)
        if b.kind == "JOINT":
            j = s.joints.get(b.joint)
            if j is None:
                warnings.append(f"'{block_label(b)}': joint '{b.joint}' not found")
                continue
            a, z = _block_values(j, b)
            v_from = jstate[j.name] if b.use_from else joints.clamp(j, a)
            joint_move(j, v_from, joints.clamp(j, z), f0, f1, b.easing)
        elif b.kind == "POSE":
            pose = s.poses.get(b.pose)
            if pose is None:
                warnings.append(f"'{block_label(b)}': pose '{b.pose}' not found")
                continue
            values, deltas = states.pose_targets(scene, pose)
            for j in s.joints:
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

    # ---- write keys ----------------------------------------------------------
    for name, keys in jkeys.items():
        j = s.joints.get(name)
        if j is None or j.motion is None:
            continue
        cb = _channelbag(j.motion, "OBJECT")
        _write(cb, f'["{joints.VALUE}"]', 0, keys)
    for name, keys in okeys.items():
        ob = bpy.data.objects.get(name)
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
    for name, keys in vkeys.items():
        ob = bpy.data.objects.get(name)
        if ob is None:
            continue
        try:
            ob.hide_set(False)         # the viewport follows the keys from now on
        except RuntimeError:
            pass
        ob["fr_anim_hide"] = True
        cb = _channelbag(ob, "OBJECT")
        rows = [(f, 1.0 if h else 0.0, "CONSTANT", "AUTO") for f, h, _i, _e in keys]
        _write(cb, "hide_viewport", 0, rows)
        _write(cb, "hide_render", 0, rows)

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
            track = _camera_track(anim, cam_blocks, CamState.of(start_cam), centre, f_end)
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
            if cam.data.dof.use_dof:
                _write(dcb, "dof.focus_distance", 0, [(f, st.focus, "LINEAR", "AUTO") for f, _l, _r, st in rows])
            scene.camera = cam

    for b in blocks:
        scene.timeline_markers.new("▸ " + block_label(b), frame=frame_of(anim, b.start))
    s.anim_baked = anim.name
    scene.frame_set(1)
    return {"frames": f_end, "seconds": seconds, "warnings": warnings}


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
