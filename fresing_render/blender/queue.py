"""Render queue: stills and animations rendered by a separate Blender in the background.

Starting the queue saves a copy of the project with the jobs into a queue folder
(next to the renders) and starts ``queue_runner.py`` in a background Blender. The
runner keeps going when the app is closed, so a queue can run overnight. It
writes ``status.json``; the app reads it every few seconds while it is open.

    <render folder>/_queue/<time>/
        <project>.blend   copy of the project at the moment the queue started
        queue.json        the jobs
        status.json       written by the runner
        stop              created by the Stop button
        log.txt           runner output
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import uuid

import bpy

from . import render

RUNNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "queue_runner.py")
PACKAGE = __package__.rsplit(".", 1)[0]
_POLL_SECONDS = 2.0


class Stopped(Exception):
    pass


# ---------------------------------------------------------------------------
# jobs (UI side)
# ---------------------------------------------------------------------------


def add_job(scene, kind: str, shot: str = "", animation: str = "", quality: str = "", camera: str = ""):
    s = scene.fresing
    job = s.queue.add()
    job.job_id = uuid.uuid4().hex[:8]
    job.kind = kind
    job.shot = shot
    job.animation = animation
    job.camera = camera
    if kind == "ANIMATION":
        anim = s.animations.get(animation)
        job.quality = quality or (anim.quality if anim else "preview")
        job.label = f"Animation: {animation}"
    else:
        job.quality = quality or s.quality
        job.label = f"Image: {shot or camera or 'current view'}"
    job.status = "WAITING"
    s.queue_index = len(s.queue) - 1
    return job


# Runtime state of the queue in this session. Kept outside the scene so undo cannot
# make the app forget a running renderer; the scene copy is for reopening the project.
_RUNTIME = {"pid": 0, "dir": "", "killed": False}
_ALIVE_CACHE: dict[int, tuple[float, bool]] = {}


def current(scene) -> tuple[int, str]:
    s = scene.fresing
    if _RUNTIME["pid"]:
        return _RUNTIME["pid"], _RUNTIME["dir"]
    return s.queue_pid, s.queue_dir


def is_running(scene) -> bool:
    pid, qdir = current(scene)
    if not pid:
        return False
    return _pid_alive(pid, qdir)


def _pid_alive(pid: int, qdir: str = "") -> bool:
    """Cheap enough to call from panel drawing (cached for a second)."""
    if pid <= 0:
        return False
    proc = _PROCS.get(pid)
    if proc is not None:                     # started by this session: ask the process object
        return proc.poll() is None
    hit = _ALIVE_CACHE.get(pid)
    if hit is not None and time.time() - hit[0] < 1.0:
        return hit[1]
    alive = _status_says_running(qdir, pid) and _pid_alive_os(pid)
    _ALIVE_CACHE[pid] = (time.time(), alive)
    return alive


def _status_says_running(qdir: str, pid: int) -> bool:
    """The runner writes its pid and running=False when it ends; a reused pid is not ours."""
    if not qdir:
        return False
    st = read_status(qdir)
    if not st:
        return os.path.isfile(os.path.join(qdir, "queue.json"))     # just started, no status yet
    return bool(st.get("running")) and int(st.get("pid", 0)) == pid


def _pid_alive_os(pid: int) -> bool:
    """True if ``pid`` is a running Blender (or Python, in tests) process."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
                return False
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return False
            exe = os.path.basename(buf.value).lower()
            return exe.startswith("blender") or exe.startswith("python")
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:                                   # a finished child that was never waited for
        pid_done, _ = os.waitpid(pid, os.WNOHANG)
        return pid_done == 0
    except ChildProcessError:
        return True
    except OSError:
        return True


def queue_root() -> str:
    return os.path.join(render.default_output_dir(), "_queue")


PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def runner_command(queue_dir: str) -> list[str]:
    exe = bpy.app.binary_path
    if exe and os.path.basename(exe).lower().startswith("blender"):
        return [exe, "--background", "--python", RUNNER, "--", queue_dir, PACKAGE]
    # Blender as a Python module (tests): run the runner with this Python and import the
    # package by its folder name (Blender's "bl_ext" namespace only exists inside Blender)
    return [sys.executable, RUNNER, queue_dir, os.path.basename(PACKAGE_DIR)]


def start(context) -> str:
    """Save a snapshot of the project with the waiting jobs and start the runner. Returns the queue folder."""
    scene = context.scene
    s = scene.fresing
    if is_running(scene):
        raise RuntimeError("The queue is already running")
    waiting = [j for j in s.queue if j.status in ("WAITING", "STOPPED", "FAILED")]
    if not waiting:
        raise RuntimeError("Nothing to render: add images or animations to the queue first")
    out_dir = bpy.path.abspath(s.out_folder) if s.out_folder else render.default_output_dir()
    os.makedirs(out_dir, exist_ok=True)
    qdir = os.path.join(out_dir, "_queue", time.strftime("%Y-%m-%d_%H%M%S"))
    os.makedirs(qdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not stem:                             # not saved yet: name the renders after the model
        from . import build
        roots = build.model_roots(scene)
        src = roots[0].get(build.PROP_SOURCE, "") if roots else ""
        stem = os.path.splitext(os.path.basename(src))[0] or "project"
    blend = os.path.join(qdir, f"{render._safe(stem)}.blend")
    jobs = []
    for j in waiting:
        j.status = "WAITING"
        j.progress = 0.0
        j.message = "Waiting"
        jobs.append({"id": j.job_id, "kind": j.kind, "shot": j.shot, "animation": j.animation,
                     "camera": j.camera, "quality": j.quality, "out_dir": out_dir, "label": j.label})
    s.queue_dir = qdir
    bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True, compress=False, relative_remap=True)
    with open(os.path.join(qdir, "queue.json"), "w", encoding="utf-8") as fh:
        json.dump({"blend": blend, "project": bpy.data.filepath, "jobs": jobs}, fh, indent=1)
    env = dict(os.environ)
    cmd = runner_command(qdir)
    if cmd[0] == sys.executable:
        # Blender as a Python module: only the folder that holds this package (Blender's own
        # script folders on sys.path would shadow the real bpy module)
        env["PYTHONPATH"] = os.path.dirname(PACKAGE_DIR)
    kwargs = {}
    if sys.platform == "win32":
        # its own process group without a window: keeps running when the app closes
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NO_WINDOW", 0)
                                   | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    else:
        kwargs["start_new_session"] = True
    with open(os.path.join(qdir, "log.txt"), "w", encoding="utf-8") as log:   # the child keeps its own handle
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=qdir, **kwargs)
    s.queue_pid = proc.pid
    _PROCS[proc.pid] = proc
    _RUNTIME.update(pid=proc.pid, dir=qdir, killed=False)
    ensure_polling()
    return qdir


_PROCS: dict[int, subprocess.Popen] = {}


def stop(scene) -> None:
    _pid, qdir = current(scene)
    if qdir:
        try:
            open(os.path.join(qdir, "stop"), "w").close()
        except OSError:
            pass


def kill(scene) -> None:
    """Stop at once (the frame being rendered is lost)."""
    s = scene.fresing
    pid, _qdir = current(scene)
    stop(scene)
    proc = _PROCS.get(pid)
    try:
        if proc is not None:
            proc.kill()
        elif pid and _pid_alive_os(pid):          # checked: it is a Blender, not a reused number
            if sys.platform == "win32":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=10,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                os.kill(pid, 15)
    except Exception:
        pass
    _RUNTIME["killed"] = True
    for j in s.queue:
        if j.status in ("RUNNING", "WAITING"):
            j.status = "STOPPED"
            j.message = "Stopped"


def read_status(qdir: str) -> dict:
    try:
        with open(os.path.join(qdir, "status.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def log_tail(qdir: str, lines: int = 6) -> str:
    try:
        with open(os.path.join(qdir, "log.txt"), encoding="utf-8", errors="replace") as fh:
            tail = fh.read().splitlines()[-lines:]
        return " | ".join(t.strip() for t in tail if t.strip())
    except OSError:
        return ""


def _queued_jobs(qdir: str) -> list[dict]:
    try:
        with open(os.path.join(qdir, "queue.json"), encoding="utf-8") as fh:
            return json.load(fh).get("jobs", [])
    except (OSError, ValueError):
        return []


def sync(scene) -> bool:
    """Copy the runner's status into the job list. Returns True while the runner is going."""
    s = scene.fresing
    pid, qdir = current(scene)
    if not qdir:
        return False
    if _RUNTIME["pid"]:                      # after an undo the scene may have lost these
        s.queue_pid, s.queue_dir = pid, qdir
    st = read_status(qdir)
    jobs_info = st.get("jobs", {})
    known = {j.job_id for j in s.queue}
    for qj in _queued_jobs(qdir):            # jobs the scene lost (undo) are shown again
        if qj["id"] not in known and qj["id"] in jobs_info:
            j = s.queue.add()
            j.job_id, j.kind, j.label = qj["id"], qj["kind"], qj.get("label", "")
            j.shot, j.animation, j.camera, j.quality = qj["shot"], qj["animation"], qj["camera"], qj["quality"]
    killed = _RUNTIME["killed"]
    for j in s.queue:
        info = jobs_info.get(j.job_id)
        if not info:
            continue
        status = info.get("status", j.status)
        if killed and status in ("RUNNING", "WAITING"):
            status = "STOPPED"
        j.status = status
        j.progress = float(info.get("progress", j.progress))
        j.message = "Stopped" if killed and status == "STOPPED" else info.get("message", j.message)
        j.output = info.get("output", j.output)
    alive = is_running(scene)
    if not alive:
        proc = _PROCS.pop(pid, None)
        if proc is not None:
            try:
                proc.wait(timeout=0)
            except Exception:
                pass
        if pid:
            s.queue_pid = 0
            _RUNTIME["pid"] = 0
            for j in s.queue:
                if j.status == "RUNNING":       # the runner died while rendering
                    j.status = "STOPPED" if killed else "FAILED"
                    j.message = "Stopped" if killed else "Renderer stopped unexpectedly: " + log_tail(qdir)
    return alive


def _poll():
    try:
        scene = bpy.context.scene
        alive = sync(scene)
        for area in getattr(bpy.context.screen, "areas", []) if bpy.context.screen else []:
            if area.type == "VIEW_3D":
                area.tag_redraw()
    except Exception:
        return _POLL_SECONDS
    return _POLL_SECONDS if alive else None


def ensure_polling() -> None:
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, first_interval=_POLL_SECONDS, persistent=True)


# ---------------------------------------------------------------------------
# rendering a job (runner side, inside the background Blender)
# ---------------------------------------------------------------------------


def run_job(scene, job: dict, progress, should_stop) -> str:
    from . import states
    s = scene.fresing
    s.out_folder = job["out_dir"]
    if job["kind"] == "STILL":
        if job.get("shot"):
            for w in states.apply_shot(scene, job["shot"]):
                progress(0, w)
        if job.get("camera"):
            cam = bpy.data.objects.get(job["camera"])
            if cam is not None:
                scene.camera = cam
        if should_stop():
            raise Stopped()
        progress(5, "Rendering image")
        info = render.render_still(scene, s, job.get("quality") or s.quality)
        return info["path"]
    return render_animation(scene, job, progress, should_stop)


def render_animation(scene, job: dict, progress, should_stop) -> str:
    from ..core import presets
    from . import animation, world

    s = scene.fresing
    anim = s.animations.get(job["animation"])
    if anim is None:
        raise RuntimeError(f"Animation '{job['animation']}' not found")
    info = animation.bake(scene, anim)
    for w in info["warnings"]:
        progress(0, w)
    quality = job.get("quality") or anim.quality
    size = presets.compute(anim.out_format, anim.out_resolution, "auto", 300, 0.0, 1920, 1080)
    r = scene.render
    r.resolution_x, r.resolution_y = size.width, size.height
    if quality == "eevee":
        r.engine = "BLENDER_EEVEE"
        try:
            scene.eevee.taa_render_samples = 64
        except AttributeError:
            pass
        device = "EEVEE"
    else:
        device = render.apply_quality(scene, quality, s.use_gpu)
        r.use_persistent_data = True          # keep the scene on the GPU between frames
    r.resolution_percentage = 100
    world.apply(scene, s)
    floor = bpy.data.objects.get(world.FLOOR_NAME)
    if quality == "eevee" and floor is not None and s.floor == "SHADOW":
        floor.hide_render = True              # EEVEE has no shadow catcher
    composite = s.background == "COLOR"
    if composite:
        r.film_transparent = True
    im = r.image_settings
    try:
        im.media_type = "IMAGE"
    except (AttributeError, TypeError):
        pass
    im.file_format = "PNG"
    im.color_mode = "RGBA"
    im.color_depth = "8"
    stem = render._safe(os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "animation")
    folder = os.path.join(job["out_dir"], f"{stem}_{render._safe(anim.name)}_{size.width}x{size.height}_{quality}_{job['id']}")
    os.makedirs(folder, exist_ok=True)
    col = tuple(render.linear_to_srgb(c) for c in s.background_color[:3])
    f_end = info["frames"]
    t0 = time.time()
    done = 0
    for f in range(1, f_end + 1):
        if should_stop():
            raise Stopped()
        final = os.path.join(folder, f"frame_{f:04d}.png")
        if os.path.exists(final):              # resume after a stop
            continue
        scene.frame_set(f)
        target = final[:-4] + ".tmp.png"      # a frame cut off by "Stop now" never looks finished
        r.filepath = target
        bpy.ops.render.render(write_still=True, scene=scene.name)
        if composite:
            render._composite_over_color(target, col, final[:-4] + ".part.png", "PNG")
            os.remove(target)
            os.replace(final[:-4] + ".part.png", final)
        else:
            os.replace(target, final)
        done += 1
        per = (time.time() - t0) / done
        left = per * (f_end - f)
        progress(95.0 * f / f_end, f"Frame {f} of {f_end} on {device} ({per:.1f} s per frame, "
                                   f"about {_duration(left)} left)")
    if anim.video == "MP4":
        progress(96, "Making the video")
        mp4 = folder + ".mp4"
        encode_mp4(folder, mp4, size.width, size.height, int(anim.fps),
                   white_under=s.background == "TRANSPARENT")
        return mp4
    return folder


def _duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def encode_mp4(frames_dir: str, out_path: str, width: int, height: int, fps: int, white_under: bool = False) -> str:
    """Put numbered PNG frames into an H.264 MP4 with Blender's own video encoder."""
    def number(name: str) -> int:
        digits = "".join(ch for ch in name if ch.isdigit())
        return int(digits) if digits else 0

    files = sorted((f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")
                    and not f.endswith((".tmp.png", ".part.png"))), key=number)
    if not files:
        raise RuntimeError("No frames to put in the video")
    enc = bpy.data.scenes.new("FR encode")
    try:
        r = enc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
        r.fps, r.fps_base = fps, 1.0
        enc.frame_start, enc.frame_end = 1, len(files)
        enc.view_settings.view_transform = "Standard"     # frames are finished images: no second tone mapping
        try:
            enc.view_settings.look = "None"
        except TypeError:
            pass
        se = enc.sequence_editor_create()
        strips = se.strips
        if white_under:
            bg = strips.new_effect(name="white", type="COLOR", channel=1, frame_start=1, length=len(files))
            bg.color = (1.0, 1.0, 1.0)
        img = strips.new_image(name="frames", filepath=os.path.join(frames_dir, files[0]), channel=2,
                               frame_start=1)
        for f in files[1:]:
            img.elements.append(f)
        img.blend_type = "ALPHA_OVER"
        im = r.image_settings
        try:
            im.media_type = "VIDEO"
        except (AttributeError, TypeError):
            pass
        im.file_format = "FFMPEG"
        ff = r.ffmpeg
        ff.format = "MPEG4"
        ff.codec = "H264"
        ff.constant_rate_factor = "HIGH"
        ff.ffmpeg_preset = "GOOD"
        ff.gopsize = max(1, fps)
        ff.audio_codec = "NONE"
        tmp_dir = os.path.join(frames_dir, "_video")
        os.makedirs(tmp_dir, exist_ok=True)
        for old in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, old))
        r.filepath = os.path.join(tmp_dir, "video")
        r.use_file_extension = True
        bpy.ops.render.render(animation=True, scene=enc.name)
        made = [f for f in os.listdir(tmp_dir) if f.lower().endswith((".mp4", ".mpg", ".mpeg", ".mkv", ".avi"))]
        if not made:
            raise RuntimeError("The video encoder wrote no file")
        if os.path.exists(out_path):
            os.remove(out_path)
        os.replace(os.path.join(tmp_dir, made[0]), out_path)
        os.rmdir(tmp_dir)
    finally:
        bpy.data.scenes.remove(enc)
    return out_path
