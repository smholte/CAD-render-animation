"""Saved cameras: standard views fitted to the model, or the current viewport view."""

from __future__ import annotations

import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import build

COLLECTION = "FR Cameras"

# direction FROM the model centre TOWARDS the camera
VIEWS = {
    "ISO": ("Iso front-right", (1.0, -1.0, 0.75)),
    "ISO_LEFT": ("Iso front-left", (-1.0, -1.0, 0.75)),
    "ISO_BACK": ("Iso back-right", (1.0, 1.0, 0.75)),
    "FRONT": ("Front", (0.0, -1.0, 0.12)),
    "SIDE": ("Side", (1.0, 0.0, 0.12)),
    "BACK": ("Back", (0.0, 1.0, 0.12)),
    "TOP": ("Top", (0.0, -0.0001, 1.0)),
    "LOW": ("Low hero", (1.0, -1.6, 0.25)),
}


def collection(scene) -> bpy.types.Collection:
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def fr_cameras(scene) -> list[bpy.types.Object]:
    return [ob for ob in scene.objects if ob.type == "CAMERA" and ob.get("fr_camera")]


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


def fit(ob: bpy.types.Object, scene, direction=None, margin: float = 1.06) -> None:
    """Aim the camera along its view direction so the visible model fills the frame."""
    pts = _points(scene)
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
        cam.ortho_scale = max(w, h * aspect) * margin
        cam.clip_end = max(cam.clip_end, depth * 4)
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
    if cam.dof.use_dof:
        cam.dof.focus_distance = dist


def add_camera(scene, view: str = "ISO", lens: float = 50.0, name: str | None = None) -> bpy.types.Object:
    label, direction = VIEWS.get(view, VIEWS["ISO"])
    cam_data = bpy.data.cameras.new(name or label)
    cam_data.lens = lens
    ob = bpy.data.objects.new(name or label, cam_data)
    ob["fr_camera"] = True
    collection(scene).objects.link(ob)
    fit(ob, scene, direction)
    scene.camera = ob
    return ob


def add_from_view(context, name: str = "View") -> bpy.types.Object | None:
    """Camera at the current 3D viewport view."""
    area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None) if context.screen else None
    if area is None:
        return None
    r3d = area.spaces.active.region_3d
    scene = context.scene
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = area.spaces.active.lens
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
    cam = ob.data
    cam.dof.use_dof = enabled
    if enabled:
        mn, mx = _bounds(scene)
        center = Vector(((mn + mx) / 2).tolist())
        cam.dof.focus_distance = (ob.matrix_world.translation - center).length
        cam.dof.aperture_fstop = fstop


def frame_matrix_for_view(direction) -> Matrix:
    q = Vector(direction).normalized()
    return (-q).to_track_quat("-Z", "Y").to_matrix().to_4x4()
