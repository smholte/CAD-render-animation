"""The automatic test tour (task 0059): the PC check's mode **Tour** goes through every stop of the test tour by itself.

It builds a fresh test tour in its work folder (the owner's own tour project and his OK / Problem ticks stay as they
are), then for every stop: opens its project, does what **Go** does, runs the stop's number check and renders a small
picture (Cycles; on the graphics card when there is one) or three frames of its motion. The report is the PC check's
report, with a card per stop: the picture, "what you should see" and OK / FAILED for the number checks. The owner can
start it, walk away, and later tick OK / Problem in the tour panel while looking at the report.
"""

from __future__ import annotations

import os
import time

from .core import Line

PIC_CPU = 480          # longest side of a picture without a graphics card (GitHub, the web machine)
PIC_GPU = 960


def lines() -> list[Line]:
    from ..blender import tour
    out = [Line("tour.build", "Make test tour project", "0.2.47", ("tour",), _build, (),
                f"Builds the {len(tour.SETS)} test tour projects from the test models")]
    for st in tour.STOPS:
        out.append(Line(f"tour.{st.id}", f"{st.number}. {st.title}", st.since, ("tour",),
                        (lambda ctx, st=st: run_stop(ctx, st)), ("tour.build",), st.see))
    return out


def _folder(ctx) -> str:
    return os.path.join(ctx.work, "Test tour")


def _build(ctx):
    from .. import __version__
    from ..blender import tour
    t0 = time.time()
    out = tour.build_all(_folder(ctx), __version__)
    ctx.metric("build", time.time() - t0, "s")
    if out["errors"]:
        raise RuntimeError("; ".join(f"{tour.SETS[k].title}: {v}" for k, v in out["errors"].items()))
    return f"{len(out['files'])} projects in {time.time() - t0:.0f} s"


def run_stop(ctx, st):
    import bpy

    from .. import __version__
    from ..blender import tour
    from . import runner
    tour.open_set(_folder(ctx), __version__, st.set)
    scene = bpy.context.scene
    warnings = tour.apply(st, scene)
    if warnings:
        raise RuntimeError("Go: " + "; ".join(warnings[:3]))
    runner.check_cancel()
    note = st.check(scene) if st.check else ""
    runner.check_cancel()
    if callable(st.auto):
        extra = st.auto(ctx, scene, st)
    elif st.auto == "clip":
        extra = clip(ctx, scene, st)
    elif st.auto == "still":
        extra = still(ctx, scene, st)
    else:
        extra = ""
    return "; ".join(x for x in (note, extra) if x)


def small_size(ctx, scene) -> None:
    """The picture's shape as the stop has it, made small: custom size, longest side PIC_CPU / PIC_GPU."""
    from ..blender import render
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    size = render.apply_output(scene, s)
    longest = PIC_GPU if ctx.has_gpu else PIC_CPU
    k = longest / max(size.width, size.height)
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = max(16, round(size.width * k)), max(16, round(size.height * k))


def _quality(ctx) -> str:
    return "preview" if ctx.has_gpu else "draft"


def render_to(ctx, scene, key: str) -> str:
    from ..blender import render
    path = os.path.join(ctx.work, "tour pictures", f"{key}.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    render.render_still(scene, scene.fresing, _quality(ctx), filepath=path, watermark=False)
    return path


def _device(ctx) -> str:
    return "graphics card" if ctx.has_gpu else "processor"


def still(ctx, scene, st) -> str:
    small_size(ctx, scene)
    t0 = time.time()
    path = render_to(ctx, scene, st.id)
    ctx.metric("render", time.time() - t0, "s")
    ctx.picture(path, st.id, f"{st.number}. {st.title}", model_check=False,
                settings=f"Cycles on the {_device(ctx)}, {_quality(ctx)}, frame {scene.frame_current}")
    return ""


def clip(ctx, scene, st, count: int = 3) -> str:
    """Three frames of the stop's motion side by side: start, middle, end (or round the stop's frame)."""
    from . import core, runner
    small_size(ctx, scene)
    f0, f1 = scene.frame_start, scene.frame_end
    shown = scene.frame_current
    frames = sorted({f0, (f0 + f1) // 2, f1} if shown in (f0, f1) else {f0, shown, f1})[:count]
    pics = []
    t0 = time.time()
    for f in frames:
        runner.check_cancel()
        scene.frame_set(f)
        pics.append(runner.read_pixels(render_to(ctx, scene, f"{st.id}_{f}")))
    ctx.metric("render", time.time() - t0, "s")
    scene.frame_set(shown)
    sheet = core.contact_sheet(pics, cols=len(pics), width=320)
    for i, px in enumerate(pics):
        bad = core.picture_problems(px, model_check=False)
        if bad:
            raise RuntimeError(f"frame {frames[i]}: {'; '.join(bad)}")
    ctx.picture_pixels(sheet, st.id, f"{st.number}. {st.title}: frames {', '.join(map(str, frames))}",
                       model_check=False, width=3 * 320 + 16,
                       settings=f"Cycles on the {_device(ctx)}, {_quality(ctx)}")
    return ""


# ---------------------------------------------------------------------------
# stops that render through the queue (labels, finished video, queue, shapes)
# ---------------------------------------------------------------------------

def _job(ctx, scene, kind: str, **kw):
    from ..blender import queue
    job = {"id": f"tour{int(time.time() * 1000) % 100000}", "kind": kind, "shot": "", "camera": "",
           "quality": "draft", "out_dir": os.path.join(ctx.work, "tour queue"), "label": "Test tour",
           "watermark": False}
    job.update(kw)
    return queue.run_job(scene, job, lambda *a: None, lambda: False)


def _video_scale(ctx) -> float:
    """Video frames in the automatic run: a quarter of 540p on the processor, half on the graphics card."""
    return 0.5 if ctx.has_gpu else 0.25


def labels(ctx, scene, st) -> str:
    small_size(ctx, scene)
    out = _job(ctx, scene, "STILL", quality=_quality(ctx))
    ctx.picture(out, st.id, f"{st.number}. {st.title}", model_check=False)
    return ""


def finished_video(ctx, scene, st) -> str:
    """The finished MP4 through the queue (processor/graphics card, Draft): its length is title + motion + end
    card; its first picture (the title card) and a frame of the motion with logo and caption go in the report."""
    import bpy

    from . import core
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    a = s.animations.get(st.animation)
    t0 = time.time()
    mp4 = _job(ctx, scene, "ANIMATION", animation=a.name, watermark=True, scale=_video_scale(ctx))
    ctx.metric("video", time.time() - t0, "s")
    if not (mp4.endswith(".mp4") and os.path.isfile(mp4) and os.path.getsize(mp4) > 1000):
        raise RuntimeError("no MP4 video was made")
    clip_ = bpy.data.movieclips.load(mp4)
    try:
        frames = clip_.frame_duration
    finally:
        bpy.data.movieclips.remove(clip_)
    body = len([f for f in os.listdir(mp4[:-4]) if f.startswith("frame_") and f.endswith(".png")])
    fps = int(a.fps)
    want = body + round(a.fin_title_seconds * fps) + round(a.fin_end_seconds * fps)
    if abs(frames - want) > 1:
        raise RuntimeError(f"the video has {frames} frames, not {want} (title card + {body} + end card)")
    pics = _movie_frames(mp4, [1, round(a.fin_title_seconds * fps) + body // 2, frames], ctx.work)
    if pics:
        ctx.picture_pixels(core.contact_sheet(pics, cols=len(pics), width=320), st.id,
                           f"{st.number}. {st.title}: title card, motion, end card", model_check=False,
                           width=3 * 320 + 16, settings=f"MP4, {frames} frames")
    else:
        frame = sorted(f for f in os.listdir(mp4[:-4]) if f.endswith(".png"))[-1]
        ctx.picture(os.path.join(mp4[:-4], frame), st.id, f"{st.number}. {st.title}: last frame", model_check=False)
    return f"MP4 {frames} frames ({fps} fps), {os.path.getsize(mp4) // 1024} KB"


def _movie_frames(path: str, frames: list, work: str) -> list:
    """Frames of a video as screen values (rows top to bottom), read back with the Video Sequencer (no 3D render);
    an empty list when Blender cannot read the video here."""
    import bpy

    from . import runner
    sc = bpy.data.scenes.new("FR tour video")
    out = []
    try:
        se = sc.sequence_editor_create()
        strip = se.strips.new_movie(name="video", filepath=path, channel=1, frame_start=1)
        w, h = strip.elements[0].orig_width, strip.elements[0].orig_height
        r = sc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = w or 960, h or 540, 100
        r.use_sequencer = True
        r.image_settings.file_format = "PNG"
        sc.frame_start, sc.frame_end = 1, max(1, strip.frame_final_duration)
        for f in frames:
            sc.frame_set(min(max(1, f), sc.frame_end))
            png = os.path.join(work, f"tour video frame {f}.png")
            r.filepath = png
            # rendered as the context's scene: render(scene=...) takes the frame of the scene in the context
            with bpy.context.temp_override(scene=sc):
                bpy.ops.render.render(write_still=True)
            out.append(runner.read_pixels(png))
    except Exception as exc:  # noqa: BLE001 - the report then shows a rendered frame instead
        print("Fresing Render test tour: could not read the video back:", exc)
        return []
    finally:
        bpy.data.scenes.remove(sc)
    return out


def queue_jobs(ctx, scene, st) -> str:
    """The two waiting jobs of the queue, rendered as the queue renders them (in this Blender)."""
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    done = []
    t0 = time.time()
    for job in list(s.queue):
        out = _job(ctx, scene, job.kind, shot=job.shot, animation=job.animation, camera=job.camera,
                   quality="draft", scale=_video_scale(ctx))
        done.append(out)
    ctx.metric("queue", time.time() - t0, "s")
    still_out = next((o for o in done if o.lower().endswith(".png")), "")
    video = next((o for o in done if o.lower().endswith(".mp4")), "")
    if not still_out or not video or os.path.getsize(video) < 1000:
        raise RuntimeError(f"the queue did not make a picture and a video: {[os.path.basename(o) for o in done]}")
    ctx.picture(still_out, st.id, f"{st.number}. {st.title}: the queued picture", model_check=False)
    return f"picture + MP4 ({os.path.getsize(video) // 1024} KB)"


def shapes(ctx, scene, st) -> str:
    from ..blender import render
    s = scene.fresing
    sizes = []
    for fmt in ("social", "square"):
        s.out_format = fmt
        render.apply_output(scene, s)
        small_size(ctx, scene)
        path = render_to(ctx, scene, f"{st.id}_{fmt}")
        sizes.append(f"{s.out_custom_w} x {s.out_custom_h}")
        ctx.picture(path, f"{st.id}_{fmt}", f"{st.number}. {st.title}: {'9:16' if fmt == 'social' else '1:1'}",
                    model_check=False)
    return ", ".join(sizes)


def attach() -> None:
    """The stops that render their own way."""
    from ..blender import tour
    for sid, fn in (("labels", labels), ("finishing", finished_video), ("queue", queue_jobs), ("shapes", shapes)):
        st = tour.find(sid)
        if st is not None and not callable(st.auto):
            st.auto = fn
