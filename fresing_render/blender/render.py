"""Render settings, GPU selection and still renders."""

from __future__ import annotations

import functools
import os
import re
import sys
import time

import bpy
import numpy as np

from ..core import presets

QUALITY = {
    # samples, resolution %, adaptive threshold
    "draft": (48, 50, 0.05),
    "preview": (128, 100, 0.03),
    "final": (512, 100, 0.01),
    "best": (2048, 100, 0.005),
}

_DEVICE_ORDER = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL")


def setup_gpu() -> str:
    """Use the best available GPU backend. Returns a short description."""
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except KeyError:
        return "CPU (Cycles add-on not loaded)"
    for backend in _DEVICE_ORDER:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            continue
        try:
            prefs.refresh_devices()
        except Exception:
            prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            names = ", ".join(sorted({d.name for d in gpus}))
            return f"GPU ({backend}): {names}"
    try:
        prefs.compute_device_type = "NONE"
    except TypeError:
        pass
    return "CPU"


def _set(data, attr: str, value) -> None:
    """Assign only when the value changes: every assignment runs Blender's update code,
    and changing e.g. the render engine stops running preview jobs."""
    try:
        if getattr(data, attr) == value:
            return
    except AttributeError:
        pass
    setattr(data, attr, value)


def apply_output(scene, s) -> presets.OutputSize:
    size = presets.compute(s.out_format, s.out_resolution, s.out_orientation, int(s.out_dpi),
                           s.out_bleed_mm if s.out_use_bleed else 0.0, s.out_custom_w, s.out_custom_h)
    r = scene.render
    _set(r, "resolution_x", size.width)
    _set(r, "resolution_y", size.height)
    _set(r, "resolution_percentage", 100)
    _set(r, "pixel_aspect_x", 1.0)
    _set(r, "pixel_aspect_y", 1.0)
    return size


def apply_quality(scene, quality: str, use_gpu: bool = True) -> str:
    samples, pct, threshold = QUALITY.get(quality, QUALITY["final"])
    c = scene.cycles
    _set(scene.render, "engine", "CYCLES")
    device = setup_gpu() if use_gpu else "CPU"
    _set(c, "device", "GPU" if device.startswith("GPU") else "CPU")
    _set(c, "samples", samples)
    _set(c, "use_adaptive_sampling", True)
    _set(c, "adaptive_threshold", threshold)
    _set(c, "use_denoising", True)
    try:
        _set(c, "denoiser", "OPENIMAGEDENOISE")
    except TypeError:
        pass
    if hasattr(c, "denoising_use_gpu"):          # Blender's default denoises on the processor
        _set(c, "denoising_use_gpu", device.startswith("GPU"))
    _set(c, "max_bounces", 12)
    _set(c, "diffuse_bounces", 4)
    _set(c, "transmission_bounces", 12)
    _set(c, "glossy_bounces", 6)
    _set(c, "caustics_reflective", True)
    _set(c, "caustics_refractive", True)
    _set(scene.render, "resolution_percentage", pct)
    _set(scene.view_settings, "view_transform", "AgX")
    try:
        _set(scene.view_settings, "look", "AgX - Medium High Contrast")
    except TypeError:
        pass
    return device


@functools.lru_cache(maxsize=1)
def pictures_dir() -> str:
    """The user's Pictures folder (on Windows asked from the system: OneDrive may have moved it).
    Asked once per session: each ctypes structure type made here stays in memory for good."""
    if sys.platform == "win32":
        try:
            import ctypes
            import uuid
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", ctypes.c_ubyte * 8)]

            u = uuid.UUID("33E28130-4E1E-4676-835A-98395C3BC3BB")      # FOLDERID_Pictures
            guid = GUID(u.fields[0], u.fields[1], u.fields[2], (ctypes.c_ubyte * 8)(*u.bytes[8:]))
            path = ctypes.c_wchar_p()
            shell32 = ctypes.WinDLL("shell32")
            shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
                                                     ctypes.POINTER(ctypes.c_wchar_p)]
            shell32.SHGetKnownFolderPath.restype = ctypes.c_long
            if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(path)) == 0 and path.value:
                result = path.value
                ctypes.windll.ole32.CoTaskMemFree(path)
                if os.path.isdir(result):
                    return result
        except Exception:
            pass
    return os.path.join(os.path.expanduser("~"), "Pictures")


# Animation frames (Cycles): measured on the EGR line, interior close-up: 44 % less render
# time, mean difference 1.3/255 against the still settings (no caustics, fewer bounces,
# adaptive sampling stops a bit earlier). Fast GI was tried and darkened the image.
MOTION = {"caustics_reflective": False, "caustics_refractive": False, "max_bounces": 8,
          "diffuse_bounces": 3, "glossy_bounces": 4, "transmission_bounces": 8}
MOTION_THRESHOLD_FACTOR = 5.0 / 3.0          # preview 0.03 -> 0.05


def apply_motion_settings(scene) -> None:
    """Cycles settings for animation frames, on top of apply_quality."""
    c = scene.cycles
    for key, value in MOTION.items():
        _set(c, key, value)
    _set(c, "adaptive_threshold", round(min(0.1, c.adaptive_threshold * MOTION_THRESHOLD_FACTOR), 4))


def default_output_dir() -> str:
    if bpy.data.filepath:
        return bpy.path.abspath("//Renders")
    return os.path.join(pictures_dir(), "Fresing Render")


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "render"


def output_path(scene, s, suffix: str = "") -> str:
    folder = bpy.path.abspath(s.out_folder) if s.out_folder else default_output_dir()
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not stem:
        from . import build
        roots = build.model_roots(scene)
        src = roots[0].get(build.PROP_SOURCE, "") if roots else ""
        stem = os.path.splitext(os.path.basename(src))[0] or "model"
    stem = _safe(stem)
    cam = _safe(scene.camera.name) if scene.camera else "view"
    ext = ".jpg" if s.out_file_type == "JPEG" else ".png"
    pct = scene.render.resolution_percentage
    w = scene.render.resolution_x * pct // 100
    h = scene.render.resolution_y * pct // 100
    base = f"{stem}_{cam}_{w}x{h}{suffix}"
    path = os.path.join(folder, base + ext)
    n = 2
    while os.path.exists(path):  # never overwrite an earlier render
        path = os.path.join(folder, f"{base}_{n:03d}{ext}")
        n += 1
    return path


def _composite_over_color(png_path: str, color_srgb, out_path: str, file_type: str) -> None:
    """Put a transparent render on an exact background colour (no tone mapping on the colour).

    The input is an 8-bit PNG straight from the renderer (display values); it is read
    as data so Blender does not convert it, and written back as display values.
    """
    img = bpy.data.images.load(png_path, check_existing=False)
    try:
        img.colorspace_settings.is_data = True
        w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        a = px[:, :, 3:4]
        bg = np.array(color_srgb[:3], dtype=np.float32).reshape(1, 1, 3)
        rgb = px[:, :, :3] * a + bg * (1 - a)
        out = np.concatenate([rgb, np.ones((h, w, 1), np.float32)], axis=2)
        res = bpy.data.images.new("fr_out", w, h, alpha=False)
        res.colorspace_settings.is_data = True
        res.pixels.foreach_set(out.ravel())
        res.filepath_raw = out_path
        res.file_format = "JPEG" if file_type == "JPEG" else "PNG"
        res.save()
        bpy.data.images.remove(res)
    finally:
        bpy.data.images.remove(img)


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def needs_composite(s) -> bool:
    return s.background == "COLOR" or s.out_file_type == "JPEG"


def prepare_still(scene, s, quality: str) -> tuple[str, str, str]:
    """Set up output, quality, world and file settings. Returns (final path, file to render to, device)."""
    from . import world

    if scene.camera is None:
        raise RuntimeError("No camera: add a camera first")
    apply_output(scene, s)
    device = apply_quality(scene, quality, s.use_gpu)
    world.apply(scene, s)
    from . import section                        # cut-away in step here, on the main thread (bug hunt 0118 row 15)
    section.sync_for_render(scene)
    from . import cameras
    cameras.update_blur(scene.camera, scene)   # the camera may have been moved by hand since
    final = output_path(scene, s, "" if quality == "final" else f"_{quality}")
    r = scene.render
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    # 8-bit when the image is composited afterwards (exact colours); 16-bit otherwise
    r.image_settings.color_depth = "8" if needs_composite(s) else "16"
    if s.background == "COLOR":
        r.film_transparent = True
    target = final + ".tmp.png" if needs_composite(s) else final
    return final, target, device


def finish_still(scene, s, rendered: str, final: str, watermark: bool | None = None) -> None:
    """Composite the background colour / convert to JPEG where needed, then the logo and the watermark
    (task 0018). ``watermark``: None = as the switch in 5 Scene & Render says."""
    _finish_still_file(scene, s, rendered, final)
    from . import video
    fin = video.finishing_for_still(scene, s.wm_on if watermark is None else watermark)
    video.finish_picture(final, fin, s.out_file_type)


def _finish_still_file(scene, s, rendered: str, final: str) -> None:
    if s.background == "COLOR":
        col = tuple(linear_to_srgb(c) for c in s.background_color[:3])
        _composite_over_color(rendered, col, final, s.out_file_type)
        os.remove(rendered)
        scene.render.film_transparent = False
    elif s.out_file_type == "JPEG":
        _composite_over_color(rendered, (1, 1, 1), final, "JPEG")
        os.remove(rendered)
    elif rendered != final:
        os.replace(rendered, final)


def render_still(scene, s, quality: str = "final", filepath: str | None = None,
                 watermark: bool | None = None) -> dict:
    """Render the active camera to a file and wait for it (scripts, self-test, background mode)."""
    final, target, device = prepare_still(scene, s, quality)
    if filepath:
        final = filepath
        target = final + ".tmp.png" if needs_composite(s) else final
    r = scene.render
    t0 = time.time()
    r.filepath = target
    bpy.ops.render.render(write_still=True, scene=scene.name)
    finish_still(scene, s, target, final, watermark)
    return {"path": final, "seconds": round(time.time() - t0, 1), "device": device,
            "size": (r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100)}
