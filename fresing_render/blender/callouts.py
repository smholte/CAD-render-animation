"""Labels pointing at parts (task 0025): where a label's point is in the picture, which labels are shown, where
their boxes go. Works for a still and for every frame of an animation (the point rides on its part).

The boxes and the line are put on the pictures by ``video.build_sequence``; the numbers (placing, fading, the
line) are in ``core/callouts.py``.
"""

from __future__ import annotations

import numpy as np

import bpy
from mathutils import Vector

from ..core import brand
from ..core import callouts as C
from . import build

PROP_KIND = build.PROP_KIND


# ---------------------------------------------------------------------------
# the settings
# ---------------------------------------------------------------------------


def window_for(anim, callout) -> tuple[float, float] | None:
    """(start, end) seconds of the step a label belongs to; None = shown all the time (also when the step
    is gone or switched off, so a label never disappears silently)."""
    if not callout.step or anim is None:
        return None
    from . import animation
    for b in anim.blocks:
        if b.enabled and b.name.strip() == callout.step.strip():
            return b.start, max(animation.block_end(b), b.start + 0.5)
    return None


def usable(callout) -> bool:
    return bool(callout.enabled and callout.part is not None and callout.text.strip())


def add(scene, part, world_point, text: str = "Label", step: str = ""):
    """A new label pointing at ``world_point`` on ``part``."""
    s = scene.fresing
    c = s.callouts.add()
    c.text = text
    c.part = part
    c.local = tuple(part.matrix_world.inverted() @ Vector(world_point))
    c.step = step
    s.callouts_index = len(s.callouts) - 1
    return c


def move_point(callout, part, world_point) -> None:
    callout.part = part
    callout.local = tuple(part.matrix_world.inverted() @ Vector(world_point))


def anchor_world(callout) -> Vector:
    return callout.part.matrix_world @ Vector(callout.local)


def is_hidden(ob) -> bool:
    """A part that is hidden in the render, or sits in a subassembly that is."""
    seen = 0
    while ob is not None and seen < 64:
        if ob.hide_render:
            return True
        ob = ob.parent
        seen += 1
    return False


# ---------------------------------------------------------------------------
# projecting into the picture
# ---------------------------------------------------------------------------


def picture_size(scene) -> tuple[int, int]:
    r = scene.render
    return (max(1, r.resolution_x * r.resolution_percentage // 100),
            max(1, r.resolution_y * r.resolution_percentage // 100))


def camera_matrix(scene, size) -> np.ndarray | None:
    """World to clip space of the scene's camera for a picture of ``size`` (4x4), or None without a camera."""
    cam = scene.camera
    if cam is None or cam.type != "CAMERA":
        return None
    depsgraph = bpy.context.evaluated_depsgraph_get()
    proj = cam.calc_matrix_camera(depsgraph, x=size[0], y=size[1], scale_x=1.0, scale_y=1.0)
    return np.array(proj @ cam.matrix_world.inverted(), dtype=np.float64)


def project(mat: np.ndarray, size, pts) -> tuple[np.ndarray, np.ndarray]:
    """Pixels (x, y from the bottom) of world points, and which of them are in front of the camera."""
    pts = np.asarray(pts, dtype=np.float64).reshape(-1, 3)
    h = np.concatenate([pts, np.ones((len(pts), 1))], axis=1) @ mat.T
    w = h[:, 3]
    front = w > 1e-9
    w_safe = np.where(front, w, 1.0)
    x = (h[:, 0] / w_safe + 1.0) * 0.5 * size[0]
    y = (h[:, 1] / w_safe + 1.0) * 0.5 * size[1]
    return np.stack([x, y], axis=1), front


def anchor_pixel(scene, callout, size, mat=None) -> tuple[float, float] | None:
    """Where the label's point is in the picture (pixels, y from the bottom); None when it is behind the camera."""
    mat = camera_matrix(scene, size) if mat is None else mat
    if mat is None or callout.part is None:
        return None
    px, front = project(mat, size, [tuple(anchor_world(callout))])
    if not front[0]:
        return None
    return float(px[0, 0]), float(px[0, 1])


def model_outline(scene, size, mat=None) -> tuple[float, float, float, float] | None:
    """The rectangle (x0, y0, x1, y1 in pixels) round all parts that are shown, as seen by the camera."""
    mat = camera_matrix(scene, size) if mat is None else mat
    if mat is None:
        return None
    mats, corners = [], []
    for ob in scene.objects:
        if ob.type != "MESH" or ob.get(PROP_KIND) != "part" or ob.hide_render:
            continue
        mats.append(np.array(ob.matrix_world))
        corners.append(np.array(ob.bound_box))
    if not mats:
        return None
    m = np.stack(mats)                                           # (n, 4, 4)
    c = np.concatenate([np.stack(corners), np.ones((len(corners), 8, 1))], axis=2)      # (n, 8, 4)
    world = np.einsum("nij,nkj->nki", m, c)[..., :3].reshape(-1, 3)
    px, front = project(mat, size, world)
    if not front.any():
        return None
    px = px[front]
    return float(px[:, 0].min()), float(px[:, 1].min()), float(px[:, 0].max()), float(px[:, 1].max())


# ---------------------------------------------------------------------------
# the labels in one picture
# ---------------------------------------------------------------------------


def measure(text: str, px: int, font_path: str = "") -> tuple[float, float]:
    """Width and height in pixels of ``text`` in the label font (Blender's own or the brand kit's)."""
    try:
        import blf
        fid = 0
        if font_path:
            fid = blf.load(font_path)
            if fid < 0:
                fid = 0
        blf.size(fid, px)
        w, h = blf.dimensions(fid, text)
        if w > 0:
            return float(w), float(max(h, px))
    except Exception:
        pass
    return C.estimate_text_width(text, px), float(px)


def draws_at(scene, size, seconds: float | None = None, anim=None, font_path: str = "") -> list[C.LabelDraw]:
    """The labels as they are drawn in the picture the camera sees now. ``seconds``/``anim``: a moment of an
    animation (labels tied to a step fade in and out); None: a still (every label that is on)."""
    s = scene.fresing
    if not s.callouts_on:
        return []
    mat = camera_matrix(scene, size)
    if mat is None:
        return []
    px_size = C.font_px(size[1], s.callout_size)
    todo = []
    for c in s.callouts:
        if not usable(c) or is_hidden(c.part):
            continue
        alpha = 1.0 if seconds is None else C.label_alpha(seconds, window_for(anim, c))
        if alpha <= 0.001:
            continue
        a = anchor_pixel(scene, c, size, mat)
        if a is None or not (0 <= a[0] <= size[0] and 0 <= a[1] <= size[1]):
            continue                                    # the point is out of the picture
        todo.append((c.text.strip(), a, alpha))
    if not todo:
        return []
    sizes = []
    for text, _a, _al in todo:
        w, h = measure(text, px_size, font_path)
        sizes.append(C.box_size(w, h, px_size))
    boxes = C.place_labels([a for _t, a, _al in todo], sizes, size, model_outline(scene, size, mat))
    return [C.LabelDraw(t, a, b, al) for (t, a, al), b in zip(todo, boxes)]


def track_for_animation(scene, anim, body_frames: int, fps: int, size, font_path: str = "", progress=None,
                        should_stop=None) -> dict[int, list[C.LabelDraw]]:
    """Labels of every frame of the animation: {frame 1..n: [LabelDraw]}. Steps through the frames (the points ride
    on their parts), so it must run after the animation is baked."""
    s = scene.fresing
    out: dict[int, list[C.LabelDraw]] = {}
    if not s.callouts_on or not any(usable(c) for c in s.callouts):
        return out
    for f in range(1, body_frames + 1):
        if should_stop is not None and should_stop():
            break
        scene.frame_set(f)
        d = draws_at(scene, size, (f - 1) / fps, anim, font_path)
        if d:
            out[f] = d
        if progress is not None and f % 20 == 0:
            progress(f / body_frames)
    return out


def style_colours(fin: brand.Finishing | None = None) -> tuple:
    """(box colour, text colour, line colour, line edge colour) as screen values from the brand kit."""
    c1 = brand.hex_to_rgb(fin.color1) if fin else brand.hex_to_rgb(brand.DEFAULT_COLOR_1)
    c2 = brand.hex_to_rgb(fin.color2, brand.DEFAULT_COLOR_2) if fin else (1.0, 1.0, 1.0)
    return c1, c2, c2, c1
