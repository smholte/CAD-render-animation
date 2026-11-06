"""Labels pointing at parts (task 0025): where the clicked point of a part is in the picture, frame by frame,
and the transparent pictures with the lines. The boxes and the text are put on the video by ``video.py``.

A label stores the part (an object, one copy) and the clicked point in the part's own coordinates, so the point
rides along when the part moves in an animation. Hidden parts (the part or any parent hidden for the render)
and points outside the picture or behind the camera give no line and no box for that frame."""

from __future__ import annotations

import os

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from ..core import brand
from ..core import callouts as C

SUBFOLDER = "_lines"


def text_of(item) -> str:
    """The label's words ('\\n' typed in the field is a line break)."""
    return item.text.replace("\\n", "\n").strip()


def is_hidden(obj) -> bool:
    ob = obj
    while ob is not None:
        if ob.hide_render:
            return True
        ob = ob.parent
    return False


def anchor_world(item) -> Vector | None:
    obj = item.obj
    if obj is None or obj.name not in bpy.data.objects:
        return None
    return obj.matrix_world @ Vector(item.local)


def project(scene, point: Vector, size) -> tuple[float, float] | None:
    """(x, y) pixels from the bottom-left of the picture, or None when the point is not in the picture."""
    cam = scene.camera
    if cam is None or cam.type != "CAMERA":
        return None
    co = world_to_camera_view(scene, cam, point)
    if co.z <= 0 or not (0.0 <= co.x <= 1.0 and 0.0 <= co.y <= 1.0):
        return None
    return co.x * size[0], co.y * size[1]


def anchor_at(scene, item, size) -> tuple[float, float] | None:
    """Where the label's point is in the picture right now (None = no line)."""
    if item.obj is None or is_hidden(item.obj):
        return None
    p = anchor_world(item)
    return project(scene, p, size) if p is not None else None


def render_size(scene) -> tuple[int, int]:
    r = scene.render
    return r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100


def model_outline(scene, size) -> tuple[float, float, float, float] | None:
    """Rectangle (x0, y0, x1, y1) in the picture around the visible meshes now, or None."""
    cam = scene.camera
    if cam is None or cam.type != "CAMERA":
        return None
    pts = []
    for ob in scene.objects:
        if ob.type != "MESH" or is_hidden(ob) or ob.name.startswith("FR "):
            continue
        mw = ob.matrix_world
        pts.extend(mw @ Vector(c) for c in ob.bound_box)
    if not pts:
        return None
    xs, ys = [], []
    for p in pts:
        co = world_to_camera_view(scene, cam, p)
        if co.z > 0:
            xs.append(co.x)
            ys.append(co.y)
    if not xs:
        return None
    return (max(0.0, min(xs)) * size[0], max(0.0, min(ys)) * size[1],
            min(1.0, max(xs)) * size[0], min(1.0, max(ys)) * size[1])


def font_px(scene, size) -> int:
    return brand.card_font_size(size[1], C.SIZE_FACTORS.get(scene.fresing.callout_size, C.SIZE_FACTORS["MEDIUM"]))


def _steps(anim) -> dict[str, tuple[float, float]]:
    from . import animation
    return {b.name.strip(): (b.start, animation.block_end(b)) for b in anim.blocks if b.enabled and b.name.strip()}


def _make_plans(scene, items, windows, frames, size, fps, set_frame):
    """The LabelPlans: for each label, its point at every frame in ``frames`` where it is shown."""
    plans = []
    for item, (first, last) in zip(items, windows):
        plans.append(C.LabelPlan(text_of(item), first, last))
    for f in frames:
        todo = [(item, pl) for item, pl in zip(items, plans) if pl.first <= f <= pl.last]
        if not todo:
            continue
        set_frame(f)
        for item, pl in todo:
            a = anchor_at(scene, item, size)
            if a is not None:
                pl.anchors[f] = a
    return plans


def _arrange(scene, plans, items, size, outline) -> None:
    px = font_px(scene, size)
    shown = [(pl, it) for pl, it in zip(plans, items) if pl.anchors]
    if not shown:
        return
    sizes = [C.box_size(pl.text, px) for pl, _ in shown]
    mean = [tuple(np.mean(np.array(list(pl.anchors.values())), axis=0)) for pl, _ in shown]
    manual = [(it.box_x * size[0], it.box_y * size[1] - sizes[i][1]) if it.manual else None
              for i, (_, it) in enumerate(shown)]
    boxes = C.place_boxes(sizes, mean, size, outline, manual)
    for (pl, _), box in zip(shown, boxes):
        pl.box = box


def usable(scene, video: bool) -> list:
    out = []
    for item in scene.fresing.callouts:
        if item.obj is None or not text_of(item):
            continue
        if (item.on_video if video else item.on_still):
            out.append(item)
    return out


def plan_video(scene, anim, body_frames: int, fps: int, size, folder: str):
    """(labels, {body frame: lines picture}) for an animation. Writes the lines pictures into ``folder``."""
    items = usable(scene, True)
    if not items:
        return [], {}
    steps = _steps(anim)
    windows = []
    for it in items:
        if it.step.strip() and it.step.strip() in steps:
            a, b = steps[it.step.strip()]
            first = 1 + brand.seconds_to_frames(a, fps)
            last = max(first, brand.seconds_to_frames(b, fps))
        else:
            first, last = 1, body_frames
        windows.append((max(1, first), min(body_frames, last)))
    current = scene.frame_current
    try:
        plans = _make_plans(scene, items, windows, range(1, body_frames + 1), size, fps, scene.frame_set)
        outline = None
        for f in sorted({1, max(1, body_frames // 2), body_frames}):
            scene.frame_set(f)
            o = model_outline(scene, size)
            if o is not None:
                outline = o if outline is None else (min(outline[0], o[0]), min(outline[1], o[1]),
                                                     max(outline[2], o[2]), max(outline[3], o[3]))
    finally:
        scene.frame_set(current)
    _arrange(scene, plans, items, size, outline)
    plans = [pl for pl in plans if pl.anchors]
    fade = brand.seconds_to_frames(brand.CAPTION_FADE_SECONDS, fps)
    lines = write_lines(plans, size, folder, fade, scene.fresing)
    return plans, lines


def plan_still(scene, size, folder: str):
    """(labels, lines picture or {}) for the current frame and camera."""
    items = usable(scene, False)
    if not items:
        return [], {}
    f = scene.frame_current
    plans = _make_plans(scene, items, [(f, f)] * len(items), [f], size, 1, lambda _f: None)
    _arrange(scene, plans, items, size, model_outline(scene, size))
    plans = [pl for pl in plans if pl.anchors]
    return plans, write_lines(plans, size, folder, 0, scene.fresing)


def fade_alpha(first: int, last: int, frame: int, fade: int) -> float:
    from .video import fade_segments
    for a, b, opacity in fade_segments(first, last, fade):
        if a <= frame <= b:
            return opacity
    return 1.0


def write_lines(plans, size, folder: str, fade: int, s) -> dict:
    """One transparent picture per body frame that has lines: {frame: path}."""
    if not plans:
        return {}
    os.makedirs(folder, exist_ok=True)
    frames = sorted({f for pl in plans for f in pl.frames()})
    col2 = brand.hex_to_rgb(brand.linear_to_hex(s.brand_color2), brand.DEFAULT_COLOR_2)
    col1 = brand.hex_to_rgb(brand.linear_to_hex(s.brand_color1))
    width = max(1.5, C.LINE_WIDTH * size[1])
    out = {}
    W, H = size
    for f in frames:
        buf = np.zeros((H, W, 4), dtype=np.float32)
        for pl in plans:
            if f not in pl.anchors:
                continue
            a = pl.anchors[f]
            run = next(r for r in C.runs(pl.frames()) if r[0] <= f <= r[1])
            alpha = fade_alpha(run[0], run[1], f, fade) if fade else 1.0
            C.draw_line(buf, C.line_end(pl.box, a), a, width, col2, col1, alpha, dot=max(3.0, width * 2.2))
        path = os.path.join(folder, f"lines_{f:04d}.png")
        save_rgba(buf, path)
        out[f] = path
    return out


def save_rgba(buf: np.ndarray, path: str) -> None:
    h, w = buf.shape[:2]
    img = bpy.data.images.new("FR lines", w, h, alpha=True)
    try:
        img.alpha_mode = "STRAIGHT"
        img.pixels.foreach_set(np.ascontiguousarray(buf).ravel())
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)


def add(scene, part, local, text: str = ""):
    """Put a label on ``part`` at the point ``local`` (part coordinates). Returns the new item."""
    from . import build
    s = scene.fresing
    item = s.callouts.add()
    item.obj = part
    item.local = tuple(local)
    item.text = text or str(part.get(build.PROP_NAME, part.name))
    s.callouts_index = len(s.callouts) - 1
    return item
