"""One-click turntable video (task 0017).

Makes (or updates) three ordinary things the owner can also see and change elsewhere:
* the camera "Turntable camera", aimed at the upright axis through the middle of the machine, far
  enough away that the whole machine stays in the picture all the way round;
* the saved scene "Turntable": the machine as it is now (colours, pose, visibility, background), seen
  from that camera;
* the animation "Turntable" (6 Animation): that scene as its start and one camera Orbit step once
  round, at constant speed, so the video loops without a jump.
The animation itself is made by animation.py (Motion lane), unchanged; the queue renders it.
"""

from __future__ import annotations

import math

from ..core import presets, studio
from . import animation, cameras, logic, render, states

TAG = "fr_turntable"
NAME = "Turntable"


def find_animation(scene):
    return next((a for a in scene.fresing.animations if a.get(TAG)), None)


def _start_azimuth(cam, centre_xy) -> float:
    """Start the turn where the active camera looks from (front right when there is none)."""
    if cam is None or cam.type != "CAMERA":
        return -45.0
    p = cam.matrix_world.translation
    dx, dy = p.x - centre_xy[0], p.y - centre_xy[1]
    if math.hypot(dx, dy) < 1e-6:            # straight above: no side to start from
        return -45.0
    return math.degrees(math.atan2(dy, dx))


def make(scene) -> dict:
    """Make or update the turntable camera, scene and animation. Returns what was made."""
    s = scene.fresing
    if animation.has_keys(scene):            # a built animation: back to the model as it was
        animation.clear_keys(scene)
    src = scene.camera if scene.camera is not None and scene.camera.type == "CAMERA" else None
    lens = src.data.lens if src is not None and src.data.type == "PERSP" else 50.0
    blur = cameras.blur_level(src) if cameras.can_blur(src) else "NONE"
    mn, mx = logic.update_bounds(scene)
    az = _start_azimuth(src, ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2))
    el = studio.TURNTABLE_HEIGHTS.get(s.turntable_height, studio.TURNTABLE_HEIGHTS["MIDDLE"])

    a = find_animation(scene)
    if a is None:
        a = s.animations.add()
        a.name = animation.unique_name(scene, NAME)
        a[TAG] = True

    # fit for the shape of the video, not of the still picture
    size = presets.compute(a.out_format, a.out_resolution, "auto", 300, 0.0, 1920, 1080)
    r = scene.render
    r.resolution_x, r.resolution_y = size.width, size.height
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    try:
        cam = cameras.turntable_camera(scene, az, el, lens, blur, cameras.SPACE.get(s.view_space, 1.06))
    finally:
        render.apply_output(scene, s)

    keep_index = s.shots_index
    shot = states.save_shot(scene, NAME, camera=cam)
    s.shots_index = keep_index if keep_index < len(s.shots) else s.shots_index
    if scene.camera is None:
        scene.camera = cam

    fps = int(a.fps)
    frames, duration, angle = studio.turntable_timing(s.turntable_seconds, fps)
    a.start_shot = shot.name
    a.tail = 0.0
    a.quality = s.turntable_quality
    a.blocks.clear()
    b = a.blocks.add()
    b.name = "Once round the machine"
    b.kind = "CAMERA"
    b.camera_mode = "ORBIT"
    b.orbit_angle = math.radians(angle)
    b.start = 0.0
    b.duration = duration
    b.easing = "LINEAR"
    s.animations_index = list(s.animations).index(a)
    return {"camera": cam, "animation": a, "shot": shot, "frames": frames, "seconds": frames / fps,
            "size": size}


def slow_note(s) -> str:
    """What to say about render time next to the turntable button ('' when nothing to say)."""
    from ..core import surroundings as env
    if s.background in env.HALL_KINDS:
        note = ("Halls take 1.4 to 2.8 times as long to render as the studio (measured on a test PC "
                "without a graphics card)")
        if s.env_detail == "DETAILED":
            note += "; Simple is faster"
        return note
    return ""


def is_turntable_running(scene) -> bool:
    a = find_animation(scene)
    return a is not None and any(j.animation == a.name and j.status in ("WAITING", "RUNNING")
                                 for j in scene.fresing.queue)
