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


def fit(ob: bpy.types.Object, scene, direction=None, margin: float = 1.08) -> None:
    """Move the camera along its view direction so the whole model fits the frame."""
    mn, mx = _bounds(scene)
    center = Vector(((mn + mx) / 2).tolist())
    corners = [Vector((x, y, z)) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    if direction is None:
        bpy.context.view_layer.update()
        d = (ob.matrix_world.to_quaternion() @ Vector((0, 0, 1))).normalized()
    else:
        d = Vector(direction).normalized()
    cam = ob.data
    rx, ry = scene.render.resolution_x * scene.render.pixel_aspect_x, scene.render.resolution_y * scene.render.pixel_aspect_y
    aspect = rx / max(1, ry)
    # horizontal / vertical half field of view
    if cam.type == "ORTHO":
        ob.location = center + d * (np.linalg.norm(mx - mn) * 2 + 1)
        look_at(ob, center)
        rot = ob.rotation_quaternion.to_matrix().inverted()
        pts = [rot @ (c - ob.location) for c in corners]
        w = max(abs(p.x) for p in pts) * 2
        h = max(abs(p.y) for p in pts) * 2
        cam.ortho_scale = max(w, h * aspect) * margin
        cam.clip_end = max(cam.clip_end, (ob.location - center).length * 3)
        return
    sensor = cam.sensor_width
    fov_long = 2 * math.atan(sensor / (2 * cam.lens))
    if aspect >= 1:
        fov_x = fov_long
        fov_y = 2 * math.atan(math.tan(fov_long / 2) / aspect)
    else:
        fov_y = fov_long
        fov_x = 2 * math.atan(math.tan(fov_long / 2) * aspect)
    # orientation looking at the centre from direction d
    ob.location = center + d * 10.0
    look_at(ob, center)
    rot_inv = ob.rotation_quaternion.to_matrix().inverted()   # matrix_world is not updated yet
    right_axis = Vector((1, 0, 0))
    up_axis = Vector((0, 1, 0))
    dist_needed = 0.0
    for c in corners:
        p = rot_inv @ (c - center)            # camera-aligned offset from centre
        depth_offset = -p.z                   # positive = further from camera
        tx = math.tan(fov_x / 2) / margin
        ty = math.tan(fov_y / 2) / margin
        dist_needed = max(dist_needed, abs(p.dot(right_axis)) / tx - depth_offset,
                          abs(p.dot(up_axis)) / ty - depth_offset)
    dist = max(dist_needed, 0.1)
    ob.location = center + d * dist
    look_at(ob, center)
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
