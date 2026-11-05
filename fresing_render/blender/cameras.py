"""Saved cameras: standard views fitted to the model or the selection, or the current view;
background blur with a sharp spot picked on the model; the turntable camera (task 0017)."""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import studio
from . import build

COLLECTION = "FR Cameras"
PROP_BLUR = "fr_blur"            # on a camera: NONE | LITTLE | STRONG (missing: made before task 0017)
PROP_FOCUS = "fr_focus"          # on the small marker of a camera's sharp spot
PROP_FOCUS_PART = "fr_focus_part"

# direction FROM the model centre TOWARDS the camera (front = -Y, right = +X)
VIEWS = {
    "ISOMETRIC": ("Isometric", (1.0, -1.0, 1.0)),
    "FRONT": ("Front", (0.0, -1.0, 0.12)),
    "SIDE": ("Side", (1.0, 0.0, 0.12)),
    "TOP": ("Top", (0.0, -0.0001, 1.0)),
    "LOW": ("3/4 hero, low", (1.0, -1.6, 0.25)),
    "HIGH": ("3/4 hero, high", (1.0, -1.6, 1.1)),
    "ISO": ("Iso front-right", (1.0, -1.0, 0.75)),
    "ISO_LEFT": ("Iso front-left", (-1.0, -1.0, 0.75)),
    "ISO_BACK": ("Iso back-right", (1.0, 1.0, 0.75)),
    "BACK": ("Back", (0.0, 1.0, 0.12)),
}
STANDARD_VIEWS = ("ISOMETRIC", "FRONT", "SIDE", "TOP", "LOW", "HIGH")     # the buttons in panel 5
ORTHO_VIEWS = ("ISOMETRIC",)     # no perspective: parallel lines stay parallel
VIEW_TIPS = {
    "ISOMETRIC": "The technical isometric view from the front right (35° from above), without perspective: "
                 "parallel edges stay parallel, like a CAD drawing",
    "FRONT": "Straight at the front of the machine, from a little above",
    "SIDE": "Straight at the right side of the machine, from a little above",
    "TOP": "Straight down from above: the layout of the machine",
    "LOW": "From the front right and low: the machine looks big and strong (hero shot)",
    "HIGH": "From the front right and higher up: shows the machine and its top (hero shot)",
    "ISO": "From the front right and above, with perspective (the camera of the import)",
    "ISO_LEFT": "From the front left and above, with perspective",
    "ISO_BACK": "From the back right and above, with perspective",
    "BACK": "Straight at the back of the machine, from a little above",
}
SPACE = {"TIGHT": 1.02, "NORMAL": 1.06, "ROOMY": 1.18}       # frame size around the model


def collection(scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def fr_cameras(scene) -> list[bpy.types.Object]:
    col = bpy.data.collections.get(COLLECTION)   # cheap: no scan over every part
    if col is None:
        return []
    return [ob for ob in col.objects if ob.type == "CAMERA" and ob.get("fr_camera")]


def _bounds(scene):
    parts = [ob for ob in build.iter_parts(scene) if ob.visible_get()] or list(build.iter_parts(scene))
    return build.world_bounds(parts)


def look_at(ob: bpy.types.Object, target: Vector) -> None:
    direction = target - ob.location
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = direction.to_track_quat("-Z", "Y")


def _points(scene) -> np.ndarray:
    """World-space bounding-box corners of every visible part (tighter than one big box)."""
    parts = [ob for ob in build.iter_parts(scene) if ob.visible_get()] or list(build.iter_parts(scene))
    pts = []
    for ob in parts:
        if ob.type != "MESH" or ob.data is None:
            continue
        mw = np.array(ob.matrix_world)
        bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        pts.append((mw @ bb.T).T[:, :3])
    if not pts:
        return np.array([[-1.0, -1.0, 0.0], [1.0, 1.0, 1.0]])
    return np.concatenate(pts)


def points_over_frames(scene, frames) -> np.ndarray:
    """Model corners at several animation frames (to frame a camera on the whole motion)."""
    current = scene.frame_current
    out = []
    try:
        for f in frames:
            scene.frame_set(int(f))
            out.append(_points(scene))
    finally:
        scene.frame_set(current)
    return np.concatenate(out) if out else _points(scene)


def fit(ob: bpy.types.Object, scene, direction=None, margin: float = 1.06, points=None) -> None:
    """Aim the camera along its view direction so the visible model fills the frame."""
    pts = _points(scene) if points is None else points
    center = (pts.min(axis=0) + pts.max(axis=0)) / 2
    if direction is None:
        bpy.context.view_layer.update()
        d = (ob.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    else:
        d = Vector(direction).normalized()
    cam = ob.data
    rx = scene.render.resolution_x * scene.render.pixel_aspect_x
    ry = scene.render.resolution_y * scene.render.pixel_aspect_y
    aspect = rx / max(1, ry)

    rot = (-d).to_track_quat("-Z", "Y")
    R = np.array(rot.to_matrix())              # columns: camera x, y, z axes in world space
    dvec = np.array(d)

    def camera_coords(c):
        return (pts - c) @ R                    # (N, 3) in camera axes, z towards the camera

    if cam.type == "ORTHO":
        for _ in range(2):
            P = camera_coords(center)
            mid = (P.min(axis=0) + P.max(axis=0)) / 2
            center = center + R[:, 0] * mid[0] + R[:, 1] * mid[1]
        P = camera_coords(center)
        w = (P[:, 0].max() - P[:, 0].min())
        h = (P[:, 1].max() - P[:, 1].min())
        depth = float(np.ptp(P[:, 2])) + 1.0
        ob.location = Vector((center + dvec * (depth * 2)).tolist())
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = rot
        # the ortho scale is the longer side of the picture: across for landscape, up for portrait
        cam.ortho_scale = (max(w, h * aspect) if aspect >= 1 else max(h, w / aspect)) * margin
        cam.clip_end = max(cam.clip_end, depth * 4)
        _after_move(ob, scene)
        return

    fov_long = 2 * math.atan(cam.sensor_width / (2 * cam.lens))
    if aspect >= 1:
        tx = math.tan(fov_long / 2)
        ty = tx / aspect
    else:
        ty = math.tan(fov_long / 2)
        tx = ty * aspect
    tx /= margin
    ty /= margin

    dist = 1.0
    for _ in range(3):
        P = camera_coords(center)
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        dist = float(max(np.max(np.abs(x) / tx + z), np.max(np.abs(y) / ty + z), 0.1))
        # re-centre on the projected extents so the model sits in the middle of the frame
        depth = np.maximum(dist - z, 1e-6)
        u, v = x / depth, y / depth
        du = (u.max() + u.min()) / 2
        dv = (v.max() + v.min()) / 2
        center = center + R[:, 0] * du * dist + R[:, 1] * dv * dist
    P = camera_coords(center)
    dist = float(max(np.max(np.abs(P[:, 0]) / tx + P[:, 2]), np.max(np.abs(P[:, 1]) / ty + P[:, 2]), 0.1))
    ob.location = Vector((center + dvec * dist).tolist())
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = rot
    cam.clip_start = max(0.001, dist * 0.002)
    cam.clip_end = max(100.0, dist * 10)
    if PROP_BLUR in ob:
        _after_move(ob, scene)
    elif cam.dof.use_dof:                      # a camera with blur from before task 0017
        cam.dof.focus_distance = dist


def display_size(scene) -> float:
    """Camera gizmo size in the viewport: small next to the model (Blender's default is 1 m)."""
    pts = _points(scene)
    size = float(np.linalg.norm(pts.max(axis=0) - pts.min(axis=0))) if len(pts) else 1.0
    return max(0.02, min(1.0, size * 0.04))


def add_camera(scene, view: str = "ISO", lens: float = 50.0, name: str | None = None, points=None,
               margin: float = 1.06, blur: str = "NONE") -> bpy.types.Object:
    """A camera for a standard view, fitted to ``points`` (default: the visible model)."""
    label, direction = VIEWS.get(view, VIEWS["ISO"])
    cam_data = bpy.data.cameras.new(name or label)
    cam_data.lens = lens
    cam_data.display_size = display_size(scene)
    if view in ORTHO_VIEWS:
        cam_data.type = "ORTHO"
    ob = bpy.data.objects.new(name or label, cam_data)
    ob["fr_camera"] = True
    ob[PROP_BLUR] = blur if view not in ORTHO_VIEWS else "NONE"
    collection(scene).objects.link(ob)
    fit(ob, scene, direction, margin=margin, points=points)
    _see_far_enough(scene)
    scene.camera = ob
    return ob


def _see_far_enough(scene) -> None:
    """A new camera must see as far as the surroundings reach (the sea goes to the horizon)."""
    try:
        from . import surroundings
        surroundings.fix_clip(scene)
    except Exception as exc:                 # never stop adding a camera over this
        print("Fresing Render: camera clipping not set:", exc)


def selection_points(scene) -> np.ndarray | None:
    """Corners of the selected parts (a selected subassembly counts with all its parts), or None."""
    from . import logic
    selected = [ob for ob in scene.objects if ob.select_get() and ob.get(build.PROP_KIND) in build.MODEL_KINDS]
    if not selected:
        return None
    parts = {ob for ob in selected if ob.get(build.PROP_KIND) == "part"}
    if any(ob.get(build.PROP_KIND) == "assembly" for ob in selected):
        tree = logic.Tree(scene)
        for ob in selected:
            if ob.get(build.PROP_KIND) == "assembly":
                parts.update(d for d in logic.descendants(ob, tree) if d.get(build.PROP_KIND) == "part")
    pts = []
    for ob in parts:
        if ob.type != "MESH" or ob.data is None or not ob.visible_get():
            continue
        mw = np.array(ob.matrix_world)
        bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        pts.append((mw @ bb.T).T[:, :3])
    return np.concatenate(pts) if pts else None


def frame_points(scene, frame: str = "MODEL"):
    """(points, framed the selection?) for the Frame setting: the whole model or the selection."""
    if frame == "SELECTION":
        pts = selection_points(scene)
        if pts is not None:
            return pts, True
    return _points(scene), False


def add_from_view(context, name: str = "View") -> bpy.types.Object | None:
    """Camera at the current 3D viewport view."""
    area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None) if context.screen else None
    if area is None:
        return None
    r3d = area.spaces.active.region_3d
    scene = context.scene
    cam_data = bpy.data.cameras.new(name)
    cam_data.display_size = display_size(scene)
    # the viewport's lens value assumes a 72 mm wide sensor; cameras use 36 mm
    cam_data.lens = area.spaces.active.lens / 2
    ob = bpy.data.objects.new(name, cam_data)
    ob["fr_camera"] = True
    collection(scene).objects.link(ob)
    ob.matrix_world = r3d.view_matrix.inverted()
    if r3d.view_perspective == "ORTHO":
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = r3d.view_distance * 2
    scene.camera = ob
    return ob


def set_dof(ob: bpy.types.Object, scene, enabled: bool, fstop: float = 5.6) -> None:
    """Blur on ('A little') or off (the Blur button of before task 0017; kept for scripts)."""
    set_blur(ob, scene, "LITTLE" if enabled else "NONE")


# ---------------------------------------------------------------------------
# background blur and the sharp spot (task 0017)
# ---------------------------------------------------------------------------


def blur_level(ob) -> str:
    """NONE | LITTLE | STRONG. A camera from before task 0017 with its own f-stop counts as LITTLE."""
    if ob is None or ob.type != "CAMERA":
        return "NONE"
    level = ob.get(PROP_BLUR)
    if level in studio.BLUR:
        return level
    return "LITTLE" if ob.data.dof.use_dof else "NONE"


def can_blur(ob) -> bool:
    return ob is not None and ob.type == "CAMERA" and ob.data.type == "PERSP"


def focus_marker(ob):
    """The small marker of the camera's sharp spot (None: the middle of the machine is sharp)."""
    if ob is None or ob.type != "CAMERA":
        return None
    fo = ob.data.dof.focus_object
    return fo if fo is not None and fo.get(PROP_FOCUS) else None


def _forward(ob) -> Vector:
    return (ob.matrix_world.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()


def _model_middle(scene) -> Vector:
    mn, mx = _bounds(scene)
    return Vector(((mn + mx) / 2).tolist())


def focus_distance(ob, scene) -> float:
    """Distance from the camera to the sharp spot along its view (the middle of the machine when
    no spot was picked): what Blender uses for the sharp plane."""
    bpy.context.view_layer.update()
    marker = focus_marker(ob)
    target = marker.matrix_world.translation if marker is not None else _model_middle(scene)
    d = (target - ob.matrix_world.translation).dot(_forward(ob))
    if d <= 0:                               # behind the camera: use the straight distance
        d = (target - ob.matrix_world.translation).length
    return max(0.001, float(d))


def update_blur(ob, scene) -> None:
    """Set the camera's sharp distance and f-stop from its blur level, lens and sharp spot.
    Call after the camera, its lens or its sharp spot changed (and before a render)."""
    if ob is None or ob.type != "CAMERA":
        return
    level = blur_level(ob)
    if PROP_BLUR not in ob:                  # a camera from before task 0017: keep its own f-stop
        return
    dof = ob.data.dof
    on = level != "NONE" and can_blur(ob)
    if dof.use_dof != on:
        dof.use_dof = on
    marker = focus_marker(ob)
    if marker is not None:
        try:
            marker.hide_set(not on)
        except RuntimeError:
            pass
    if not on:
        return
    dist = focus_distance(ob, scene)
    dof.focus_distance = dist                # also used by animations that start from this camera
    cam = ob.data
    sensor = cam.sensor_width if cam.sensor_fit != "VERTICAL" else cam.sensor_height
    dof.aperture_fstop = studio.blur_fstop(level, cam.lens, sensor, dist)


def set_blur(ob, scene, level: str) -> None:
    if ob is None or ob.type != "CAMERA":
        return
    ob[PROP_BLUR] = level if level in studio.BLUR else "NONE"
    update_blur(ob, scene)


def _after_move(ob, scene) -> None:
    if PROP_BLUR in ob:
        update_blur(ob, scene)


def set_focus(ob, scene, part, point) -> bpy.types.Object:
    """Make ``point`` (a world position on ``part``) the sharp spot of camera ``ob``. The spot moves
    with the part (joints, poses, animations)."""
    marker = focus_marker(ob)
    if marker is None:
        marker = bpy.data.objects.new(f"{ob.name} – sharp spot", None)
        marker[PROP_FOCUS] = True
        marker["fr_helper"] = True
        marker.empty_display_type = "SPHERE"
        collection(scene).objects.link(marker)
        ob.data.dof.focus_object = marker
    marker.empty_display_size = display_size(scene) * 0.25
    marker.hide_select = True
    for con in list(marker.constraints):
        marker.constraints.remove(con)
    marker.matrix_world = Matrix.Translation(Vector(point))
    if part is not None:
        con = marker.constraints.new("CHILD_OF")
        con.name = "Follows the part"
        con.target = part
        con.inverse_matrix = part.matrix_world.inverted()
        marker[PROP_FOCUS_PART] = part.get("fr_name", part.name)
    if PROP_BLUR not in ob or blur_level(ob) == "NONE":
        ob[PROP_BLUR] = "LITTLE"             # picking a sharp spot means: blur the rest
    update_blur(ob, scene)
    return marker


def clear_focus(ob, scene) -> None:
    """Back to a sharp middle of the machine."""
    marker = focus_marker(ob)
    if marker is None:
        return
    ob.data.dof.focus_object = None
    bpy.data.objects.remove(marker)
    update_blur(ob, scene)


def remove_camera(ob) -> None:
    """Delete a camera and the marker of its sharp spot."""
    marker = focus_marker(ob)
    bpy.data.objects.remove(ob)
    if marker is not None and not any(o.type == "CAMERA" and o.data.dof.focus_object == marker
                                      for o in bpy.data.objects):
        bpy.data.objects.remove(marker)


def focus_label(ob) -> str:
    marker = focus_marker(ob)
    if marker is None:
        return "Middle of the machine"
    return marker.get(PROP_FOCUS_PART) or "Picked spot"


# ---------------------------------------------------------------------------
# turntable camera (task 0017)
# ---------------------------------------------------------------------------

TURNTABLE_CAMERA = "Turntable camera"


def _turned(points: np.ndarray, centre_xy, angle: float) -> np.ndarray:
    c, s = math.cos(angle), math.sin(angle)
    out = points.copy()
    x = points[:, 0] - centre_xy[0]
    y = points[:, 1] - centre_xy[1]
    out[:, 0] = centre_xy[0] + c * x - s * y
    out[:, 1] = centre_xy[1] + s * x + c * y
    return out


def fit_turntable(ob, scene, az_deg: float, el_deg: float, margin: float = 1.06) -> float:
    """Aim the camera at a point on the upright axis through the middle of the machine (the axis
    an Orbit step turns around) from azimuth ``az_deg`` and height ``el_deg``, as close as possible
    with the whole machine in the picture at every angle of the turn. Returns the distance."""
    from . import logic
    mn, mx = logic.update_bounds(scene)          # the centre the Orbit step turns around
    cxy = ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2)
    base = _points(scene)
    pts = np.concatenate([_turned(base, cxy, math.radians(a)) for a in range(0, 360, 15)])
    az, el = math.radians(az_deg), math.radians(el_deg)
    d = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), math.sin(el)))
    cam = ob.data
    cam.type = "PERSP"
    rx = scene.render.resolution_x * scene.render.pixel_aspect_x
    ry = scene.render.resolution_y * scene.render.pixel_aspect_y
    aspect = rx / max(1, ry)
    rot = (-d).to_track_quat("-Z", "Y")
    R = np.array(rot.to_matrix())
    fov_long = 2 * math.atan(cam.sensor_width / (2 * cam.lens))
    if aspect >= 1:
        tx = math.tan(fov_long / 2)
        ty = tx / aspect
    else:
        ty = math.tan(fov_long / 2)
        tx = ty * aspect
    tx /= margin
    ty /= margin
    aim = np.array([cxy[0], cxy[1], (mn[2] + mx[2]) / 2])
    dist = 1.0
    for _ in range(6):
        P = (pts - aim) @ R
        x, y, z = P[:, 0], P[:, 1], P[:, 2]
        dist = float(max(np.max(np.abs(x) / tx + z), np.max(np.abs(y) / ty + z), 0.1))
        depth = np.maximum(dist - z, 1e-6)
        v = y / depth
        dv = (v.max() + v.min()) / 2
        if abs(R[2, 1]) > 1e-3:                  # slide the aim point up or down the axis only
            aim = aim + np.array([0.0, 0.0, dv * dist / R[2, 1]])
    P = (pts - aim) @ R
    dist = float(max(np.max(np.abs(P[:, 0]) / tx + P[:, 2]), np.max(np.abs(P[:, 1]) / ty + P[:, 2]), 0.1))
    ob.location = Vector((aim + np.array(d) * dist).tolist())
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = rot
    cam.clip_start = max(0.001, dist * 0.002)
    cam.clip_end = max(cam.clip_end, 100.0, dist * 10)
    # the sharp plane: the middle of the turn (the same distance at every angle)
    level = blur_level(ob)
    on = level != "NONE"
    cam.dof.use_dof = on
    cam.dof.focus_object = None
    if on:
        cam.dof.focus_distance = dist
        cam.dof.aperture_fstop = studio.blur_fstop(level, cam.lens, cam.sensor_width, dist)
    return dist


def turntable_camera(scene, az_deg: float, el_deg: float, lens: float = 50.0, blur: str = "NONE",
                     margin: float = 1.06) -> bpy.types.Object:
    """The camera of the turntable video (made once, aimed again every time)."""
    ob = next((o for o in collection(scene).objects if o.get("fr_turntable") and o.type == "CAMERA"), None)
    if ob is None:
        data = bpy.data.cameras.new(TURNTABLE_CAMERA)
        ob = bpy.data.objects.new(TURNTABLE_CAMERA, data)
        ob["fr_camera"] = True
        ob["fr_turntable"] = True
        collection(scene).objects.link(ob)
    ob.data.lens = lens
    ob.data.display_size = display_size(scene)
    ob[PROP_BLUR] = blur if blur in studio.BLUR else "NONE"
    fit_turntable(ob, scene, az_deg, el_deg, margin)
    _see_far_enough(scene)
    return ob


def frame_matrix_for_view(direction) -> Matrix:
    q = Vector(direction).normalized()
    return (-q).to_track_quat("-Z", "Y").to_matrix().to_4x4()
