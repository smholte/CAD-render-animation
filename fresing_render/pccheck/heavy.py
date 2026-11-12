"""PC check "Heavy" (task 0033): longer, bigger tests that really load the PC.

A big machine is *made at run time* (``heavy_scene.py``, about 3,000 placed / 600 unique generic parts) and
deleted at the end; nothing of it is in the repository. The lines then import it, work with it, render
stills up to 4K and a real 10 s animation through the queue. ``FRESING_PCCHECK_HEAVY_SMALL=1`` shrinks every
size (a few hundred parts, 12 frames, 480 × 270) so GitHub and small machines run the same lines in minutes.

Round 1: scene, import, working with it, stills, video. Round 2 (from the owner's first Heavy run on a 24-core PC
with an RTX 3090: 7 lines in 12 minutes, so the sizes stay): Detailed halls, milling with chips at length,
playback under load, and the own-model Heavy lines (4K picture, a 3 s EEVEE video).
"""

from __future__ import annotations

import math
import os
import subprocess
import sys
import time

import numpy as np

from . import core
from .checks import (DATA, H, MILL, _boom_joint, _check, _mill_scene, _ob, _per_frame,  # noqa: F401
                     _queue_job, _update, line)

SMALL_ENV = "FRESING_PCCHECK_HEAVY_SMALL"


def small() -> bool:
    return os.environ.get(SMALL_ENV, "") == "1"


def sizes() -> dict:
    """Every size of the Heavy lines, full or scaled down."""
    if small():
        return dict(unique=60, placed=300, w=480, h=270, w4k=640, h4k=360, seconds=0.16, clip_seconds=0.12,
                    sheet=4, still_quality=("draft", "draft"), anim_res=("preview", "square"))
    return dict(unique=600, placed=3000, w=1920, h=1080, w4k=3840, h4k=2160, seconds=10.0, clip_seconds=3.0,
                sheet=8, still_quality=("preview", "final"), anim_res=("hd", "presentation"))


def peak_memory_mb() -> float:
    """The biggest memory this program (Blender) has used so far, in MB. Windows: the peak working set
    (GetProcessMemoryInfo); Linux: the peak resident size."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(COUNTERS), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            c = COUNTERS()
            c.cb = ctypes.sizeof(COUNTERS)
            if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return c.PeakWorkingSetSize / 2 ** 20
        except Exception:  # noqa: BLE001
            pass
        return 0.0
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("VmHWM:"):
                    return int(ln.split()[1]) / 1024
    except OSError:
        pass
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except (ImportError, OSError):
        return 0.0


def _step(ctx) -> str:
    path = getattr(ctx, "heavy_step", "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("the big test machine was not made")
    return path


def _memory(ctx) -> None:
    mb = peak_memory_mb()
    if mb:
        ctx.metric("peak memory", round(mb), "MB")


def _output(s, w, h):
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = w, h


def _hero(ctx, scene):
    """Product studio light and a three-quarter camera on the whole machine."""
    import bpy

    from ..blender import cameras
    bpy.ops.fresing.light_look(look="PRODUCT")
    s = scene.fresing
    s.background = "COLOR"
    cameras.add_camera(scene, "ISO", name="Heavy hero")
    scene.camera.data.lens = 35.0                       # room for the parts that move in the video
    return s


# ---------------------------------------------------------------------------
# the scene
# ---------------------------------------------------------------------------

@line("heavy.scene", "Big test machine is made", "0.2.29", (H,), expected=60,
      what="A generic machine of about 3,000 placed parts is written as a STEP file in a temporary folder",
      shows="That the app's STEP writer/reader library works on a big assembly, and how fast this PC makes it",
      not_shown="Anything about your own parts: this machine is invented and is deleted afterwards")
def heavy_scene(ctx):
    from ..importer import runner as import_runner
    z = sizes()
    out = os.path.join(ctx.work, "heavy_machine.step")
    env = dict(os.environ)
    for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(var, None)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heavy_scene.py")
    t0 = time.time()
    r = subprocess.run([import_runner.python_executable(), script, out, str(z["unique"]), str(z["placed"])],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                       timeout=1800,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0 or not os.path.isfile(out):
        raise RuntimeError("the big test machine could not be written: " + (r.stderr or r.stdout).strip()[-300:])
    ctx.heavy_step = out
    ctx.metric("make", time.time() - t0, "s")
    ctx.metric("file size", round(os.path.getsize(out) / 1e6, 1), "MB")
    ctx.metric("parts placed", z["placed"], "")
    return f"{os.path.getsize(out) / 1e6:.0f} MB STEP file"


@line("heavy.import", "Big machine: import, build, sort", "0.2.29", (H,), requires=("heavy.scene",), expected=240,
      what="Reads the big STEP file on all cores, builds the objects and sorts the parts; then again from the cache",
      shows="Import speed on all your cores, build and sort time, how much memory the app needs for a big model",
      not_shown="Reading a STEP file from a slow network drive, or the extra memory of the helper programs")
def heavy_import(ctx):
    from ..blender import build
    from ..core import rules as R
    step = _step(ctx)
    t0 = time.time()
    scene = ctx.fresh(step, quality="normal", read_again=True)
    ctx.metric("import", time.time() - t0, "s")
    t0 = time.time()
    scene = ctx.fresh(step, quality="normal")
    ctx.metric("from cache (build + sort)", time.time() - t0, "s")
    parts = list(build.iter_parts(scene))
    z = sizes()
    _check(len(parts) >= z["placed"] * 0.9, f"only {len(parts)} parts came in of about {z['placed']}")
    unsorted = sum(1 for o in parts if o.get(build.PROP_GROUP) == R.FALLBACK_GROUP)
    tris, seen = 0, set()
    for o in parts:
        if o.data.name in seen:
            continue
        seen.add(o.data.name)
        tris += len(o.data.polygons)
    ctx.metric("parts", len(parts), "")
    ctx.metric("unique parts", len(seen), "")
    ctx.metric("faces (unique)", round(tris / 1e6, 2), "M")
    ctx.metric("sorted", round(100.0 * (len(parts) - unsorted) / max(1, len(parts)), 1), "%")
    _memory(ctx)
    return f"{len(parts)} parts, {len(seen)} unique"


@line("heavy.work", "Big machine: tree, search, show only, explode, pose, save", "0.2.29", (H,),
      requires=("heavy.import",), expected=90,
      what="Structure list, search, Show only, explode, a pose, then save the project and open it again",
      shows="Whether the side panel stays quick with 3,000 parts, and how big the saved project is",
      not_shown="Drawing the 3D view live on your screen (the check runs without a window)")
def heavy_work(ctx):
    import bpy

    from ..blender import build, finder, joints, logic, states, tree
    from mathutils import Vector
    scene = ctx.scene_of("heavy.import")
    s = scene.fresing
    t0 = time.time()
    logic.Tree(scene)
    ctx.metric("tree walk", time.time() - t0, "s")
    t0 = time.time()
    logic.rebuild_tree(scene)
    ctx.metric("structure list", time.time() - t0, "s")
    s.find_text = "BRACKET"
    t0 = time.time()
    found = finder.run_search(scene)
    ctx.metric("search", time.time() - t0, "s")
    _check(found > 0, "the search for BRACKET found nothing in the big machine")
    parts = [o for o in build.iter_parts(scene) if "BRACKET" in o.get(build.PROP_NAME, "")]
    t0 = time.time()
    tree.show_only(scene, parts[:200], "PC check")
    ctx.metric("show only", time.time() - t0, "s")
    tree.end_show_only(scene)
    root = build.model_roots(scene)[0]
    t0 = time.time()
    n = states.explode(scene, root, 0.5)
    _update()
    ctx.metric("explode", time.time() - t0, "s")
    _check(n >= 2, f"explode moved only {n} subassemblies")
    states.reset_pose(scene)
    mod = _ob(scene, "MODULE 01")
    j = joints.create(scene, "ROTATE", [mod], mod.matrix_world.translation.copy(), Vector((0, 0, 1)), name="Heavy turn")
    t0 = time.time()
    joints.set_value(j, math.radians(30))
    _update()
    ctx.metric("pose", time.time() - t0, "s")
    path = os.path.join(ctx.work, "PC check heavy.blend")
    t0 = time.time()
    bpy.ops.wm.save_as_mainfile(filepath=path)
    ctx.metric("save", time.time() - t0, "s")
    ctx.metric("project size", round(os.path.getsize(path) / 1e6, 1), "MB")
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=path)
    ctx.metric("open", time.time() - t0, "s")
    scene = bpy.context.scene
    _check(scene.fresing.joints.get("Heavy turn") is not None, "the joint is gone after opening the project again")
    joints.set_value(scene.fresing.joints.get("Heavy turn"), 0.0)
    _memory(ctx)
    return f"{found} names found, explode moved {n}"


# ---------------------------------------------------------------------------
# stills
# ---------------------------------------------------------------------------

def _still(ctx, scene, key, title, w, h, quality, gpu: bool):
    from ..blender import render
    s = scene.fresing
    _output(s, w, h)
    s.use_gpu = gpu
    path = os.path.join(ctx.work, f"{key}.png")
    info = render.render_still(scene, s, quality, filepath=path)
    device = info["device"]
    ctx.metric(key.replace("_", " "), info["seconds"], "s")
    ctx.picture(path, key, title, model_check=False, width=760,
                settings=f"{info['size'][0]} × {info['size'][1]}, Cycles {quality}, {device}")
    return info


@line("heavy.stills_cycles", "Big machine: Cycles pictures, HD and 4K", "0.2.29", (H,),
      requires=("heavy.import",), expected=420,
      what="The whole machine from a three-quarter view, Cycles on the graphics card: HD and 4K, Preview and Final",
      shows="How long a real picture of a big machine takes on your graphics card, at the sizes you deliver",
      not_shown="Graphics-card memory use (not readable here), or pictures with your own parts and materials")
def heavy_stills_cycles(ctx):
    from . import runner
    ctx.need_gpu()
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    _hero(ctx, scene)
    low, high = z["still_quality"]
    for key, title, w, h, q in (
            ("hd_preview", "Cycles HD, Preview", z["w"], z["h"], low),
            ("hd_final", "Cycles HD, Final", z["w"], z["h"], high),
            ("uhd_preview", "Cycles 4K, Preview", z["w4k"], z["h4k"], low),
            ("uhd_final", "Cycles 4K, Final", z["w4k"], z["h4k"], high)):
        runner.check_cancel()
        _still(ctx, scene, "cycles_" + key, title, w, h, q, True)
    _memory(ctx)
    return None


def _eevee_test(ctx, scene, res: str, fmt: str, key: str, title: str):
    """EEVEE time per frame through the queue (a time test of a short move), and its middle frame."""
    from ..blender import joints
    from mathutils import Vector
    j = scene.fresing.joints.get("Heavy turn")
    if j is None:
        mod = _ob(scene, "MODULE 01")
        j = joints.create(scene, "ROTATE", [mod], mod.matrix_world.translation.copy(), Vector((0, 0, 1)),
                          name="Heavy turn")
    a = scene.fresing.animations.get(key) or scene.fresing.animations.add()
    a.name, a.tail, a.quality, a.out_resolution, a.out_format = key, 0.0, "eevee", res, fmt
    if not len(a.blocks):
        b = a.blocks.add()
        b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", j.name, 2.0, False, math.radians(30)
    try:
        job = _queue_job(ctx, scene, "TEST", animation=a.name, minutes=30)
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise
    ctx.metric(key.replace("_", " "), _per_frame(job.message), "s/frame")
    ctx.picture(job.output, key, title, model_check=False, gpu_optional=True, width=760,
                settings=f"{res.upper()} EEVEE, a middle frame of the time test")


@line("heavy.stills_eevee", "Big machine: EEVEE per frame, HD and 4K", "0.2.29", (H,),
      requires=("heavy.import",), expected=180,
      what="The same machine with Fast preview (EEVEE): time per frame at HD and at 4K, through the queue",
      shows="How smooth real-time rendering is with a big model at the two sizes",
      not_shown="Cycles quality: EEVEE is the quick preview engine")
def heavy_stills_eevee(ctx):
    from . import runner
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    _hero(ctx, scene)
    scene.fresing.use_gpu = ctx.has_gpu
    small_run = small()
    combos = (("preview" if small_run else "hd", "square" if small_run else "presentation",
                                  "eevee_hd", "EEVEE HD per frame"),
                                 ("preview" if small_run else "4k", "square" if small_run else "presentation",
                                  "eevee_4k", "EEVEE 4K per frame"))
    for res, fmt, key, title in combos[:1] if small_run else combos:       # scaled down: one size is enough
        runner.check_cancel()
        _eevee_test(ctx, scene, res, fmt, key, title)
    _memory(ctx)
    return None


# ---------------------------------------------------------------------------
# a real animation through the queue
# ---------------------------------------------------------------------------

def _heavy_animation(ctx, scene, name: str, seconds: float, quality: str):
    """Steps on the big machine: a joint turns a module, another module slides, a motor runs a third."""
    from ..blender import joints
    from mathutils import Vector
    z = sizes()
    mods = [_ob(scene, f"MODULE {i:02d}") for i in (1, 2, 3)]
    j1 = scene.fresing.joints.get("Heavy turn") or joints.create(
        scene, "ROTATE", [mods[0]], mods[0].matrix_world.translation.copy(), Vector((0, 0, 1)), name="Heavy turn")
    j2 = scene.fresing.joints.get("Heavy slide") or joints.create(
        scene, "SLIDE", [mods[1]], mods[1].matrix_world.translation.copy(), Vector((1, 0, 0)), name="Heavy slide")
    j3 = scene.fresing.joints.get("Heavy motor")
    if j3 is None:
        j3 = joints.create(scene, "ROTATE", [mods[2]], mods[2].matrix_world.translation.copy(), Vector((0, 0, 1)),
                           name="Heavy motor")
        joints.set_motor(scene, j3, True)
    a = scene.fresing.animations.add()
    a.name, a.fps, a.tail, a.quality, a.video = name, "25", 0.0, quality, "MP4"
    a.out_resolution, a.out_format = z["anim_res"]
    third = seconds / 3.0
    for kind, joint, start, extra in (("JOINT", j1.name, 0.0, {"to_angle": math.radians(90)}),
                                      ("JOINT", j2.name, third, {"to_dist": 4.0}),
                                      ("MOTOR", j3.name, 2 * third, {"speed_rpm": 15.0})):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = kind, joint, start, third, "LINEAR"
        if kind == "JOINT":
            b.use_from = False
        for k, v in extra.items():
            setattr(b, k, v)
    return a


def _frames_of(job) -> list:
    folder = job.output[:-4]
    return sorted(f for f in os.listdir(folder) if f.endswith(".png"))


def _check_video(ctx, job, a, expected_frames: int, t_start: float, key: str, title: str, settings: str) -> str:
    """The numbers and pictures of a finished queue video: frames, file, motion visible, no black frames."""
    import bpy

    from . import runner
    _check(job.output.endswith(".mp4") and os.path.getsize(job.output) > 1000, "no MP4 video was made")
    frames = _frames_of(job)
    _check(abs(len(frames) - expected_frames) <= 1,
           f"{len(frames)} frames were rendered, {expected_frames} expected")
    folder = job.output[:-4]
    try:
        clip = bpy.data.movieclips.load(job.output)
        try:
            dur, size = clip.frame_duration, tuple(clip.size)
        finally:
            bpy.data.movieclips.remove(clip)
    except Exception as exc:  # noqa: BLE001 - say what is wrong in plain words
        raise RuntimeError(f"the video file does not open: {exc}") from exc
    _check(abs(dur - len(frames)) <= 2, f"the video has {dur} frames, the pictures {len(frames)}")
    n = min(len(frames), sizes()["sheet"])
    idx = sorted({round(i * (len(frames) - 1) / max(1, n - 1)) for i in range(n)})
    pics = [runner.read_pixels(os.path.join(folder, frames[i])) for i in idx]
    for i, px in zip(idx, pics):
        bad = core.picture_problems(px, False)
        _check(not bad, f"frame {i + 1} is {'; '.join(bad)}")
    diff = core.picture_difference(core.thumbnail(pics[0]), core.thumbnail(pics[-1]))
    _check(diff is not None and diff > 0.002, "the first and the last frame look the same: nothing moves")
    ctx.picture_pixels(core.contact_sheet(pics, cols=4), key + "_sheet", title + ": contact sheet", False,
                       width=760, settings=f"{len(idx)} frames across the video; {settings}")
    ctx.picture_pixels(pics[-1], key + "_last", title + ": last frame", False, width=760, settings=settings)
    total = time.time() - t_start
    first = min(os.path.getmtime(os.path.join(folder, f)) for f in frames)
    ctx.metric("frames", len(frames), "")
    ctx.metric("total", total, "s")
    ctx.metric("per frame", total / max(1, len(frames)), "s/frame")
    ctx.metric("start-up", max(0.0, first - t_start), "s")
    ctx.metric("video size", round(os.path.getsize(job.output) / 1e6, 1), "MB")
    ctx.metric("moves", round(diff, 3), "")
    _ = size
    return f"{len(frames)} frames, {size[0]} × {size[1]}, {total:.0f} s"


@line("heavy.video_eevee", "Big machine: 10 s EEVEE video, rendered fully", "0.2.29", (H,),
      requires=("heavy.import",), expected=420,
      what="A joint, a slide and a motor move the machine for 10 s (250 frames); the queue renders every frame "
           "(EEVEE, 1920 × 1080) and makes the MP4",
      shows="Time per frame over a long run, the queue's start-up, that the video has all frames and moves",
      not_shown="Cycles video quality, or the cylinders and mechanisms (those are in the Full check)")
def heavy_video_eevee(ctx):
    from . import runner
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    _hero(ctx, scene)
    scene.fresing.use_gpu = ctx.has_gpu
    a = _heavy_animation(ctx, scene, "Heavy EEVEE", z["seconds"], "eevee")
    runner.check_cancel()
    t0 = time.time()
    try:
        job = _queue_job(ctx, scene, "ANIMATION", animation=a.name, minutes=60)
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise
    return _check_video(ctx, job, a, round(z["seconds"] * 25) + 1, t0, "eevee_video", "EEVEE video",
                        f"{a.out_resolution}, EEVEE, {z['seconds']:.0f} s, 25 frames/s")


@line("heavy.video_cycles", "Big machine: Cycles Preview clip", "0.2.29", (H,),
      requires=("heavy.import",), expected=420,
      what="A shorter clip (3 s, 75 frames) rendered with Cycles Preview on the graphics card through the queue",
      shows="Time per frame of a real Cycles animation with a big model",
      not_shown="Final-quality animations (those take much longer)")
def heavy_video_cycles(ctx):
    from . import runner
    ctx.need_gpu()
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    _hero(ctx, scene)
    scene.fresing.use_gpu = True
    a = _heavy_animation(ctx, scene, "Heavy Cycles", z["clip_seconds"], "preview")
    runner.check_cancel()
    t0 = time.time()
    job = _queue_job(ctx, scene, "ANIMATION", animation=a.name, minutes=60)
    out = _check_video(ctx, job, a, round(z["clip_seconds"] * 25) + 1, t0, "cycles_video", "Cycles video",
                       f"{a.out_resolution}, Cycles Preview, {z['clip_seconds']:.0f} s")
    _memory(ctx)
    return out


# ---------------------------------------------------------------------------
# round 2: Detailed halls, milling with chips at length, playback under load
# ---------------------------------------------------------------------------

@line("heavy.halls", "Big machine: CNC hall and open sea, Detailed", "0.2.32", (H,), requires=("heavy.import",),
      expected=150,
      what="The big machine in the CNC hall and on the open sea with Detailed surroundings, Cycles Preview at HD "
           "on the graphics card",
      shows="What the Detailed surroundings (real waves, the whole hall) add to the render time of a big model",
      not_shown="The Simple surroundings (the Full check renders those) or halls with your own photos")
def heavy_halls(ctx):
    from ..blender import surroundings
    from . import runner
    ctx.need_gpu()
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    s = _hero(ctx, scene)
    low = z["still_quality"][0]
    for kind, key, title in (("CNC", "hall_detailed", "CNC hall, Detailed"), ("SEA", "sea_detailed", "Open sea, Detailed")):
        runner.check_cancel()
        s.env_detail = "DETAILED"
        s.background = kind
        _check(surroundings.root_object() is not None, f"the {title.lower()} was not built")
        _still(ctx, scene, key, title, z["w"], z["h"], low, True)
    s.background = "COLOR"
    s.env_detail = "SIMPLE"
    _memory(ctx)
    return None


@line("heavy.milling", "Milling: a long cut with chips", "0.2.32", (H,), expected=150,
      what="The test mill cuts a long slot (more than 100 frames); chips Realistic are worked out; the time per "
           "frame with and without chips",
      shows="How the milling view and the chips cope with a long program: work-out time, ms per frame, faces left in the block",
      not_shown="A real CNC program with thousands of moves (the G-code demo is a hand test on your machine)")
def heavy_milling(ctx):
    from ..blender import chips, machining
    z = sizes()
    scale = 0.15 if small() else 4.0                  # seconds of the program: about 100+ frames when full size
    chips.forget()
    scene, frames, stock = _mill_scene(ctx, scale=scale, x_mm=60.0 if small() else 150.0)
    if not small():
        _check(frames >= 100, f"the long cut has only {frames} frames")
    t0 = time.time()
    machining.sample(scene)
    ctx.metric("read motion", time.time() - t0, "s")
    probes = sorted({max(1, round(frames * i / 20)) for i in range(1, 21)})

    def scrub() -> float:
        t = time.time()
        for f in probes:
            scene.frame_set(f)
        return (time.time() - t) * 1000.0 / len(probes)

    machining.settings(scene).chips = "NONE"
    ctx.metric("per frame, no chips", scrub(), "ms/frame")
    t0 = time.time()
    machining.settings(scene).chips = "REALISTIC"
    scene.frame_set(frames)
    ctx.metric("chips work out", time.time() - t0, "s")
    ctx.metric("per frame, chips", scrub(), "ms/frame")
    me = machining.settings(scene).cut_mesh
    _check(me is not None and stock.data is me, "the block does not show its cut")
    ctx.metric("block faces", len(me.polygons), "")
    ctx.metric("frames", frames, "")
    _memory(ctx)
    return f"{frames} frames, {len(me.polygons)} faces in the block"


@line("heavy.playback", "Big machine: playback under load", "0.2.32", (H,), requires=("heavy.import",), expected=60,
      what="Three joints with a coupling move the 3,000-part machine through a 10 s animation; every frame is set "
           "and evaluated one after the other",
      shows="Milliseconds per frame while scrubbing a big machine with joints and couplings (the Full check shows "
            "0.03 to 0.09 ms on a small one)",
      not_shown="Drawing speed in the 3D view on your screen, cylinders and mechanisms (they are in the Full check)")
def heavy_playback(ctx):
    from ..blender import animation, joints
    from mathutils import Vector
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    a = _heavy_animation(ctx, scene, "Heavy playback", z["seconds"], "preview")
    mod = _ob(scene, "UNIT 02.3")
    j4 = joints.create(scene, "SLIDE", [mod], mod.matrix_world.translation.copy(), Vector((0, 1, 0)), name="Heavy coupled")
    joints.set_follows(scene, j4, "Heavy turn", ratio=0.01)
    t0 = time.time()
    frames = animation.bake(scene, a)["frames"]
    ctx.metric("build animation", time.time() - t0, "s")
    t0 = time.time()
    for f in range(1, frames + 1):
        scene.frame_set(f)
    ms = (time.time() - t0) * 1000.0 / frames
    ctx.metric("per frame", ms, "ms/frame")
    ctx.metric("frames", frames, "")
    animation.clear_keys(scene)
    _check(ms < 2000.0, f"playback takes {ms:.0f} ms per frame: far too slow")
    return f"{frames} frames, {ms:.1f} ms per frame"


@line("heavy.clash", "Big machine: clash check of a 10 s animation", "0.2.53", (H,), requires=("heavy.import",),
      expected=60,
      what="A module of the 3,000-part machine turns, another slides 4 m, a third runs as a motor (10 s); the clash "
           "check goes through every frame and between frames where parts move fast",
      shows="How long Check for clashes takes on a big machine (aim: well under a minute), how many clashes it "
            "lists (the made-up machine's modules really run through each other)",
      not_shown="Your own model's motion (try Check for clashes on it), the red parts in the view")
def heavy_clash(ctx):
    from ..blender import animation, clash
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    a = _heavy_animation(ctx, scene, "Heavy clash", z["seconds"], "preview")
    animation.bake(scene, a)
    t0 = time.time()
    run = clash.check(scene, store=False)
    secs = time.time() - t0
    animation.clear_keys(scene)
    st = run.stats
    ctx.metric("clash check", secs, "s")
    ctx.metric("moments", st["moments"] + st["between"], "")
    ctx.metric("clashes", len(run.rows), "")
    ctx.metric("parts held still", st.get("held", 0), "")         # round parts turning in place (task 0092)
    _check(st["moments"] > 0 and st["parts"] > 100, "the check did not go through the machine")
    _check(secs < 600.0, f"the clash check took {secs:.0f} s: far too slow")
    return (f"{st['parts']} parts, {st['bodies']} bodies, {st['moments']} frames + {st['between']} between: "
            f"{len(run.rows)} clashes in {secs:.1f} s ({st.get('held', 0)} turning parts held still)")


@line("heavy.vessel", "Big machine: vessel motion on the open sea", "0.2.65", (H,), requires=("heavy.import",),
      expected=30,
      what="The 3,000-part machine on the open sea: frames of the time line stepped through with vessel motion off "
           "and on (calm, beam sea); every part then moves each frame",
      shows="What vessel motion adds to each frame of a big model (playback in the view, building a video)",
      not_shown="The render time itself (about the same with and without it), the swell in the sea (Detail Simple)")
def heavy_vessel(ctx):
    from ..blender import vessel_motion
    z = sizes()
    scene = ctx.scene_of("heavy.import")
    s = scene.fresing
    before = (s.background, s.env_detail)
    s.env_detail = "SIMPLE"
    s.background = "SEA"
    frames = max(10, int(z["seconds"] * scene.render.fps))
    times = {}
    try:
        for on in (False, True):
            s.vessel.heading = "BEAM"
            s.vessel.enabled = on
            _check(on == (vessel_motion.rig("pivot") is not None),
                   "vessel motion did not switch " + ("on" if on else "off"))
            scene.frame_set(1)
            t0 = time.time()
            for f in range(2, frames + 2):
                scene.frame_set(f)
            times[on] = (time.time() - t0) * 1000.0 / frames
        ctx.metric("per frame, off", times[False], "ms/frame")
        ctx.metric("per frame, on", times[True], "ms/frame")
        _check(times[True] < 2000.0, f"a frame takes {times[True]:.0f} ms with vessel motion: far too slow")
    finally:
        s.vessel.enabled = False
        s.background, s.env_detail = before
    return (f"{frames} frames: {times[False]:.1f} ms per frame without, {times[True]:.1f} ms with vessel motion "
            f"(+{times[True] - times[False]:.1f} ms)")


# ---------------------------------------------------------------------------
# Heavy with the owner's own model: numbers only
# ---------------------------------------------------------------------------

OWNH = "ownheavy"


@line("own.heavy_4k", "Your model: 4K picture on the graphics card", "0.2.32", (OWNH,), requires=("own.import",),
      expected=120, what="A 3840 × 2160 Cycles Preview picture of your model on the graphics card",
      shows="How long a 4K picture of your own model takes, and the peak memory",
      not_shown="Final-quality pictures (several times slower)")
def own_heavy_4k(ctx):
    import bpy

    from ..blender import render
    ctx.need_gpu()
    z = sizes()
    scene = ctx.scene_of("own.import")
    bpy.ops.fresing.light_look(look="PRODUCT")
    s = scene.fresing
    s.background = "COLOR"
    _output(s, z["w4k"], z["h4k"])
    s.use_gpu = True
    path = os.path.join(ctx.work, "own_4k.png")
    info = render.render_still(scene, s, z["still_quality"][0], filepath=path)
    ctx.metric("render 4K", info["seconds"], "s")
    ctx.picture(path, "own_4k", "Your model, 4K (this PC only)", model_check=False)
    _memory(ctx)
    return None


@line("own.heavy_video", "Your model: 3 s EEVEE turntable, rendered fully", "0.2.32", (OWNH,),
      requires=("own.import",), expected=300,
      what="A 3 second turntable of your model at HD through the queue (EEVEE, every frame, MP4)",
      shows="Time per frame over a real run with your model, and the queue's start-up",
      not_shown="Cycles animations (see the time test lines)")
def own_heavy_video(ctx):
    from ..blender import turntable
    scene = ctx.scene_of("own.import")
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    s.turntable_seconds = 1.0 if small() else 3.0
    s.turntable_quality = "eevee"
    a = turntable.make(scene)["animation"]
    a.quality, a.video = "eevee", "MP4"
    a.out_resolution, a.out_format = sizes()["anim_res"]
    t0 = time.time()
    try:
        job = _queue_job(ctx, scene, "ANIMATION", animation=a.name, minutes=60)
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise
    frames = _frames_of(job)
    total = time.time() - t0
    ctx.metric("frames", len(frames), "")
    ctx.metric("total", total, "s")
    ctx.metric("per frame", total / max(1, len(frames)), "s/frame")
    _memory(ctx)
    return None


# ---------------------------------------------------------------------------
# the demo project (task 0077)
# ---------------------------------------------------------------------------

@line("heavy.demo", "Demo project: cable-lay vessel", "0.2.68", (H,), expected=300,
      what="Makes the demo project as Help > Make demo project does (the invented cable-lay vessel: model, 415 "
           "joints, sea, cameras, the animation 'What it can do today'), renders the overview and steps through the "
           "animation",
      shows="How long the demo takes to make on this PC, the Build time of its animation, the time per frame while "
            "you scrub it (1,250 parts, 300 joints turning), and the memory it needs",
      not_shown="The demo's video rendered in full (render it from the queue: 7 Render queue)")
def heavy_demo(ctx):
    import bpy

    from ..blender import animation, demo, render, states
    z = sizes()
    folder = os.path.join(ctx.work, "demo")
    t0 = time.time()
    out = demo.build_project(folder, "pccheck", small=small())
    ctx.loaded = ("", "")                                   # the PC check's project was replaced
    make = time.time() - t0
    ctx.metric("make", make, "s")
    for k in ("write", "import", "joints", "build"):
        if k in out["timings"]:
            ctx.metric(k, out["timings"][k], "s")
    bpy.ops.wm.open_mainfile(filepath=out["path"])
    scene = bpy.context.scene
    s = scene.fresing
    _check(len(s.joints) >= demo.MIN_JOINTS, f"the demo has {len(s.joints)} joints, not {demo.MIN_JOINTS}")
    a = s.animations.get(demo.ANIM)
    _check(a is not None, f"the demo has no animation '{demo.ANIM}'")
    t0 = time.time()
    animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    frames = list(range(scene.frame_start, scene.frame_end + 1, max(1, (scene.frame_end - scene.frame_start) // 40)))
    t0 = time.time()
    for f in frames:
        scene.frame_set(f)
    per = (time.time() - t0) / max(1, len(frames))
    ctx.metric("per frame", per, "s/frame")
    states.apply_shot(scene, demo.SEA_SHOT)
    scene.frame_set(scene.frame_start)
    _output(s, z["w"], z["h"])
    s.use_gpu = ctx.has_gpu
    path = os.path.join(ctx.work, "demo_overview.png")
    info = render.render_still(scene, s, z["still_quality"][0], filepath=path)
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "demo_overview", "Demo project: the vessel on the open sea")
    _memory(ctx)
    _check(per < 5.0, f"a frame of the demo animation takes {per:.1f} s: far too slow")
    return f"{len(s.joints)} joints, '{demo.ANIM}' {scene.frame_end} frames, {per * 1000:.0f} ms per frame"
