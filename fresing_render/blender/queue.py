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
import shutil
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
    if kind in ("ANIMATION", "TEST"):
        anim = s.animations.get(animation)
        job.quality = quality or (anim.quality if anim else "preview")
    else:
        job.quality = quality or s.quality
    job.watermark = bool(s.wm_on) and kind != "TEST"
    relabel(job)
    job.status = "WAITING"
    s.queue_index = len(s.queue) - 1
    return job


QUEUE_ONLY = "fr_queue_only"     # on a hidden saved scene or camera made by "Add image" (not in any list)


def view_camera(scene):
    """The camera "Add image" stores: the active camera, or, while a built animation moves the camera, a still copy
    of it as it is at this frame (bug hunt row 7: the queue clears the keys, and the animation camera with them)."""
    cam = scene.camera
    if cam is None or not cam.get("fr_anim_camera") or not scene.fresing.anim_baked:
        return cam
    from . import cameras
    bpy.context.view_layer.update()
    data = cam.data.copy()
    if data.animation_data is not None:
        data.animation_data_clear()
    name = "Queue camera"
    n = 2
    while name in bpy.data.objects:
        name = f"Queue camera {n}"
        n += 1
    data.name = name
    ob = bpy.data.objects.new(name, data)
    ob.matrix_world = cam.matrix_world.copy()
    ob[QUEUE_ONLY] = True
    cameras.collection(scene).objects.link(ob)
    try:
        ob.hide_set(True)
    except RuntimeError:
        pass
    return ob


def tidy_queue_only(scene) -> None:
    """Remove hidden "Add image" scenes and cameras that no job uses any more."""
    s = scene.fresing
    used = {j.shot for j in s.queue}
    for shot in [x for x in s.shots if x.get(QUEUE_ONLY)]:
        if shot.name not in used:
            s.shots.remove(list(s.shots).index(shot))
    cams = {x.camera.name for x in s.shots if x.camera is not None}
    for ob in [o for o in bpy.data.objects if o.get(QUEUE_ONLY) and o.type == "CAMERA"]:
        if ob.name not in cams and ob is not scene.camera:
            data = ob.data
            bpy.data.objects.remove(ob)
            if data is not None and data.users == 0:
                bpy.data.cameras.remove(data)


def relabel(job) -> None:
    """The job's name in the list, from what it renders (also after a rename: bug hunt row 17c)."""
    if job.kind in ("ANIMATION", "TEST"):
        label = f"{'Time test' if job.kind == 'TEST' else 'Animation'}: {job.animation}"
    else:
        label = f"Image: {job.shot or job.camera or 'current view'}"
    if job.watermark:
        label += " (with watermark)"
    job.label = label


def last_time_test(scene, animation: str):
    """The newest time test of an animation in the queue list, or None."""
    for job in reversed(scene.fresing.queue):
        if job.kind == "TEST" and job.animation == animation:
            return job
    return None


# Runtime state of the queue in this session. Kept outside the scene so undo cannot
# make the app forget a running renderer; the scene copy is for reopening the project.
# It belongs to the project that started it: another project opened afterwards keeps its own queue (bug hunt row 9).
_RUNTIME = {"pid": 0, "dir": "", "killed": False, "project": ""}
_ALIVE_CACHE: dict[int, tuple[float, bool]] = {}


def _ours(scene) -> bool:
    """True when the queue this session started belongs to the open project: the same file, or the scene still
    names its folder (saved under a new name since)."""
    if not _RUNTIME["pid"] and not _RUNTIME["dir"]:
        return False
    if _RUNTIME["dir"] and scene.fresing.queue_dir == _RUNTIME["dir"]:
        return True
    return os.path.normcase(os.path.abspath(bpy.data.filepath)) == _RUNTIME["project"] if bpy.data.filepath \
        else _RUNTIME["project"] == ""


def belongs_here(scene) -> bool:
    """A queue this session started for the open project is still going (used when a project is opened)."""
    return bool(_RUNTIME["pid"]) and _ours(scene)


def current(scene) -> tuple[int, str]:
    s = scene.fresing
    if _RUNTIME["pid"] and _ours(scene):
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
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                        ctypes.POINTER(wintypes.DWORD)]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
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
    _tidy_old_queues(os.path.join(out_dir, "_queue"))
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
                     "camera": j.camera, "quality": j.quality, "out_dir": out_dir, "label": j.label,
                     "watermark": bool(j.watermark)})
    s.queue_dir = qdir
    undo = _absolute_paths(scene)                # '//…' would point next to the copy (bug hunt row 18)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=blend, copy=True, compress=False, relative_remap=True)
    finally:
        for owner, key, value in undo:
            owner[key] = value
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
    project = os.path.normcase(os.path.abspath(bpy.data.filepath)) if bpy.data.filepath else ""
    _RUNTIME.update(pid=proc.pid, dir=qdir, killed=False, project=project)
    ensure_polling()
    return qdir


_PROCS: dict[int, subprocess.Popen] = {}

PATH_KEYS = ("hdri_path", "light_hdri_path", "brand_logo", "brand_font")    # file settings of scene.fresing


def _absolute_paths(scene) -> list:
    """Make every '//…' file setting absolute for the queue's copy (it is saved in another folder, and Blender only
    remaps its own file paths). Written as ID properties, so no world rebuild runs. Returns what to put back."""
    if not bpy.data.filepath:
        return []
    undo = []

    def fix(owner, key):
        val = owner.get(key)
        if isinstance(val, str) and val.startswith("//"):
            undo.append((owner, key, val))
            owner[key] = os.path.normpath(bpy.path.abspath(val))

    s = scene.fresing
    for key in PATH_KEYS:
        fix(s, key)
    for anim in s.animations:
        fix(anim, "music_file")
        for card in anim.cards:
            fix(card, "path")
    for shot in s.shots:                         # a saved scene keeps its 360° photo in its world settings
        try:
            data = json.loads(shot.world or "{}")
        except ValueError:
            continue
        changed = False
        for key in ("hdri_path", "light_hdri_path"):
            val = data.get(key)
            if isinstance(val, str) and val.startswith("//"):
                data[key] = os.path.normpath(bpy.path.abspath(val))
                changed = True
        if changed:
            undo.append((shot, "world", shot.world))
            shot["world"] = json.dumps(data)
    return undo


def skip(scene, job_id: str) -> None:
    """A waiting job was taken out of the list while the queue runs: the runner leaves it out (bug hunt row 17a)."""
    _pid, qdir = current(scene)
    if qdir:
        try:
            open(os.path.join(qdir, f"skip_{job_id}"), "w").close()
        except OSError:
            pass


def skipped(qdir: str, job_id: str) -> bool:
    return bool(qdir) and os.path.exists(os.path.join(qdir, f"skip_{job_id}"))


def _tidy_old_queues(root: str) -> None:
    """Remove project copies left by queues that were killed (they can be big on a share)."""
    if not os.path.isdir(root):
        return
    for name in os.listdir(root):
        qd = os.path.join(root, name)
        if not os.path.isdir(qd):
            continue
        st = read_status(qd)
        if st.get("running") and _pid_alive_os(int(st.get("pid", 0))):
            continue                         # a queue that is really still running
        for f in os.listdir(qd):
            if f.endswith(".blend") or f.endswith(".blend1"):
                try:
                    os.remove(os.path.join(qd, f))
                except OSError:
                    pass


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
    if _RUNTIME["pid"] and _ours(scene):     # after an undo the scene may have lost these
        s.queue_pid, s.queue_dir = pid, qdir
    st = read_status(qdir)
    jobs_info = st.get("jobs", {})
    known = {j.job_id for j in s.queue}
    queued = _queued_jobs(qdir)
    for qj in queued:                        # jobs the scene lost (undo) are shown again
        if qj["id"] not in known and qj["id"] in jobs_info and not skipped(qdir, qj["id"]):
            j = s.queue.add()
            j.job_id, j.kind, j.label = qj["id"], qj["kind"], qj.get("label", "")
            j.shot, j.animation, j.camera, j.quality = qj["shot"], qj["animation"], qj["camera"], qj["quality"]
            j.watermark = bool(qj.get("watermark"))
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
            if pid == _RUNTIME["pid"]:
                _RUNTIME["pid"] = 0
            ids = {qj["id"] for qj in queued}
            for j in s.queue:
                if j.status == "RUNNING" or (j.status == "WAITING" and j.job_id in ids
                                             and j.job_id not in jobs_info):
                    # the runner died while rendering, or before it wrote anything (bug hunt row 17e)
                    j.status = "STOPPED" if killed else "FAILED"
                    j.message = "Stopped" if killed else "Renderer stopped unexpectedly: " + (
                        log_tail(qdir) or "no log (Blender did not start)")
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


def run_job(scene, job: dict, progress, should_stop):
    """Returns the output path, or (output path, message) for a time test."""
    from . import states
    s = scene.fresing
    s.out_folder = job["out_dir"]
    if job["kind"] == "STILL":
        if job.get("shot"):
            if s.shots.get(job["shot"]) is None:          # bug hunt row 17d: never a picture of something else
                raise RuntimeError(f"The saved scene '{job['shot']}' was deleted")
            for w in states.apply_shot(scene, job["shot"]):
                progress(0, w)
        if job.get("camera"):
            cam = bpy.data.objects.get(job["camera"])
            if cam is not None:
                scene.camera = cam
        if should_stop():
            raise Stopped()
        from . import machining                  # milling (task 0027): the cut at this frame
        machining.prepare(scene, progress)
        progress(5, "Rendering image")
        info = render.render_still(scene, s, job.get("quality") or s.quality, watermark=bool(job.get("watermark")))
        return info["path"]
    if job["kind"] == "TEST":
        return time_test(scene, job, progress, should_stop)
    return render_animation(scene, job, progress, should_stop)


def _setup_animation(scene, job: dict, progress) -> dict:
    """Bake the animation and set up engine, size and files exactly as for the real render."""
    from ..core import presets
    from . import animation, world

    s = scene.fresing
    anim = s.animations.get(job["animation"])
    if anim is None:
        raise RuntimeError(f"Animation '{job['animation']}' not found")
    info = animation.bake(scene, anim)
    for w in info["warnings"]:
        progress(0, w)
    from . import machining                      # milling (task 0027): read the bits' motion of this animation
    machining.prepare(scene, progress)
    quality = job.get("quality") or anim.quality
    size = presets.compute(anim.out_format, anim.out_resolution, "auto", 300, 0.0, 1920, 1080)
    if job.get("scale"):                         # the automatic test tour (task 0059): small frames
        import dataclasses
        k = float(job["scale"])
        size = dataclasses.replace(size, width=max(16, round(size.width * k / 2) * 2),
                                   height=max(16, round(size.height * k / 2) * 2))
    r = scene.render
    r.resolution_x, r.resolution_y = size.width, size.height
    from . import video                          # task 0018: square / upright videos: crop or extend the framing
    video.apply_shape_fit(scene, anim.shape_fit, anim.out_format)
    if quality == "eevee":
        r.engine = "BLENDER_EEVEE"
        try:
            scene.eevee.taa_render_samples = 64
        except AttributeError:
            pass
        device = "EEVEE"
    else:
        device = render.apply_quality(scene, quality, s.use_gpu)
        render.apply_motion_settings(scene)   # animation frames: less time on light bouncing around
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
    return {"anim": anim, "frames": info["frames"], "quality": quality, "size": size, "device": device,
            "composite": composite, "color": tuple(render.linear_to_srgb(c) for c in s.background_color[:3]),
            "name": f"{stem}_{render._safe(anim.name)}_{size.width}x{size.height}_{quality}"}


def _render_frame(scene, setup: dict, f: int, final: str) -> tuple[float, float]:
    """Render frame ``f`` to ``final``. Returns (seconds rendering, seconds saving)."""
    r = scene.render
    t0 = time.time()
    scene.frame_set(f)
    target = final[:-4] + ".tmp.png"          # a frame cut off by "Stop now" never looks finished
    r.filepath = target
    bpy.ops.render.render(write_still=True, scene=scene.name)
    t1 = time.time()
    if setup["composite"]:
        render._composite_over_color(target, setup["color"], final[:-4] + ".part.png", "PNG")
        os.remove(target)
        os.replace(final[:-4] + ".part.png", final)
    else:
        os.replace(target, final)
    t2 = time.time()
    print(f"frame {f}: render {t1 - t0:.1f} s, save {t2 - t1:.1f} s", flush=True)
    return t1 - t0, t2 - t1


def render_animation(scene, job: dict, progress, should_stop) -> str:
    setup = _setup_animation(scene, job, progress)
    anim, f_end, device = setup["anim"], setup["frames"], setup["device"]
    size = setup["size"]
    folder = os.path.join(job["out_dir"], f"{setup['name']}_{job['id']}")
    os.makedirs(folder, exist_ok=True)
    keep_frames(folder, fingerprint(scene, setup), f_end, progress)
    t0 = time.time()
    done = 0
    for f in range(1, f_end + 1):
        if should_stop():
            raise Stopped()
        final = os.path.join(folder, f"frame_{f:04d}.png")
        if os.path.exists(final):              # resume after a stop
            continue
        _render_frame(scene, setup, f, final)
        done += 1
        per = (time.time() - t0) / done
        left = per * (f_end - f)
        progress(95.0 * f / f_end, f"Frame {f} of {f_end} on {device} ({per:.1f} s per frame, "
                                   f"about {_duration(left)} left)")
    if anim.video == "MP4":
        from . import video
        for w in video.warnings_for(scene, anim):
            progress(96, w)
        fin = video.finishing_for_animation(scene, anim, bool(job.get("watermark")))
        from . import callouts                    # task 0025: where the labels are in every frame
        if scene.fresing.callouts_on and any(callouts.usable(c) for c in scene.fresing.callouts):
            progress(95, "Working out where the labels go")
            fps = int(anim.fps)
            fin.label_px = callouts.C.font_px(size.height, scene.fresing.callout_size)
            fin.label_track = callouts.track_for_animation(
                scene, anim, f_end, fps, (size.width, size.height), fin.font,
                progress=lambda part: progress(95 + part, "Working out where the labels go"), should_stop=should_stop)
            if should_stop():
                raise Stopped()
        progress(96, "Making the video" + (" with cards, logo, captions or watermark" if fin.active else ""))
        mp4 = folder + ".mp4"
        encode_mp4(folder, mp4, size.width, size.height, int(anim.fps),
                   white_under=scene.fresing.background == "TRANSPARENT", finishing=fin,
                   steps=video.captions_of(anim, scene), last=f_end)
        return mp4
    if job.get("watermark") or anim.fin_logo != "NONE" or anim.fin_title_on or anim.fin_end_on or anim.fin_captions:
        progress(96, "Logo, cards, captions and watermark only go into MP4 videos, not into PNG frames")
    return folder


FINGERPRINT = "fingerprint.txt"


def fingerprint(scene, setup: dict) -> str:
    """What the frames of a built animation depend on: size, quality, length, every key of the animation (parts,
    joints, hiding, camera), and the place, hiding and look of every object at frame 1. A job started again after a
    stop keeps its frames only when this is unchanged (bug hunt row 8)."""
    import hashlib
    from . import animation
    h = hashlib.sha256()

    def add(*vals):
        h.update(repr(vals).encode("utf-8", "replace"))

    r = scene.render
    add("v1", setup["frames"], setup["quality"], r.resolution_x, r.resolution_y, r.engine, r.fps,
        r.film_transparent, setup.get("composite"), tuple(round(c, 4) for c in setup.get("color", ())))
    add(sorted((k, str(v)) for k, v in _scene_settings(scene.fresing)))
    for act in sorted((a for a in bpy.data.actions if a.get(animation.TAG) and a.users), key=lambda a: a.name):
        for slot_bag in _fcurves(act):
            for fc in slot_bag:
                co = [0.0] * (2 * len(fc.keyframe_points))
                fc.keyframe_points.foreach_get("co", co)
                add(act.name, fc.data_path, fc.array_index, [round(x, 5) for x in co],
                    [k.interpolation for k in fc.keyframe_points])
    scene.frame_set(1)
    for ob in sorted(scene.objects, key=lambda o: o.name):
        if ob.type not in ("MESH", "CAMERA", "LIGHT", "EMPTY", "CURVES", "POINTCLOUD", "VOLUME", "FONT", "CURVE"):
            continue
        mats = tuple(sl.material.name if sl.material else "" for sl in ob.material_slots)
        add(ob.name, ob.type, ob.hide_render, ob.data.name if ob.data else "", mats,
            [round(x, 5) for row in ob.matrix_world for x in row])
    cam = scene.camera
    if cam is not None and cam.type == "CAMERA":
        d = cam.data
        add(cam.name, d.type, round(d.lens, 4), round(d.ortho_scale, 4), d.dof.use_dof,
            round(d.dof.focus_distance, 4), round(d.dof.aperture_fstop, 4),
            d.dof.focus_object.name if d.dof.focus_object else "")
    return h.hexdigest()


def _scene_settings(s):
    from . import states
    for key in states.WORLD_KEYS + ("camera_blur",):
        if hasattr(s, key):
            yield key, states._plain(getattr(s, key))
    for g in s.groups:
        yield "group " + g.name, (g.material, states._plain(g.color))


def _fcurves(act):
    """The F-curves of an action, slot by slot (Blender 5 keeps them in channel bags)."""
    out = []
    for layer in getattr(act, "layers", []):
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.append(list(bag.fcurves))
    if not out and hasattr(act, "fcurves"):
        out.append(list(act.fcurves))
    return out


def _frame_number(name: str) -> int:
    """frame_0012.png -> 12; anything else -> 0."""
    if not (name.startswith("frame_") and name.endswith(".png")) or name.endswith((".tmp.png", ".part.png")):
        return 0
    digits = name[6:-4]
    return int(digits) if digits.isdigit() else 0


def keep_frames(folder: str, print_: str, f_end: int, progress=None) -> None:
    """Frames already in ``folder`` are kept only when they were made from the same animation and settings, and only
    up to its last frame; anything else is deleted before rendering (bug hunt row 8)."""
    path = os.path.join(folder, FINGERPRINT)
    try:
        with open(path, encoding="utf-8") as fh:
            old = fh.read().strip()
    except OSError:
        old = ""
    frames = [f for f in os.listdir(folder) if _frame_number(f)]
    if old != print_:
        drop = frames
        if drop and progress is not None:
            progress(0, f"The animation or its settings changed since the last run: rendering all "
                        f"{f_end} frames again")
    else:
        drop = [f for f in frames if _frame_number(f) > f_end]
    for f in drop:
        try:
            os.remove(os.path.join(folder, f))
        except OSError:
            pass
    if old != print_:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(print_ + "\n")


def time_test(scene, job: dict, progress, should_stop) -> tuple[str, str]:
    """Render the first frame and one from the middle with the real settings.

    The first frame includes loading the model onto the graphics card; the middle one is
    what every further frame costs. Returns (the middle frame, the estimate)."""
    setup = _setup_animation(scene, job, progress)
    f_end, size = setup["frames"], setup["size"]
    folder = os.path.join(job["out_dir"], "_time_tests")
    os.makedirs(folder, exist_ok=True)
    progress(5, "Rendering the first frame (includes loading the model)")
    first = os.path.join(folder, f"{setup['name']}_{job['id']}_frame_0001.png")
    r1, s1 = _render_frame(scene, setup, 1, first)
    if f_end < 2:
        return first, f"Time test: {r1 + s1:.0f} s for the only frame"
    if should_stop():
        raise Stopped()
    mid = max(2, (f_end + 1) // 2)
    progress(50, f"Rendering frame {mid} (a typical frame)")
    path = os.path.join(folder, f"{setup['name']}_{job['id']}_frame_{mid:04d}.png")
    r2, s2 = _render_frame(scene, setup, mid, path)
    try:
        os.remove(first)
    except OSError:
        pass
    per = r2 + s2
    total = r1 + s1 + per * (f_end - 1)
    msg = (f"{per:.1f} s per frame on {setup['device']}: about {_duration(total)} for {f_end} frames "
           f"at {size.width}x{size.height}")
    return path, msg


def _duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def _no_frame_cache(enc) -> None:
    """The encode reads every frame once: keep none of them in the sequencer cache (task 0043). A 4K frame
    cost 33 MB of cache, up to the cache limit, inside the process that also holds the whole project."""
    se = enc.sequence_editor
    if se is None:
        return
    for name in ("use_cache_raw", "use_cache_preprocessed", "use_cache_composite", "use_cache_final"):
        if hasattr(se, name):
            setattr(se, name, False)


def encode_mp4(frames_dir: str, out_path: str, width: int, height: int, fps: int, white_under: bool = False,
               finishing=None, steps=None, last: int | None = None) -> str:
    """Put numbered PNG frames into an H.264 MP4 with Blender's own video encoder.

    ``last``: the animation's last frame; only frame_0001 … frame_<last> go in, and all of them must be there (bug
    hunt row 8: frames of an older, longer run stayed in the folder). ``finishing`` (core.brand.Finishing) adds the
    logo, title and end card, captions (from ``steps``) and the watermark (task 0018)."""
    files = sorted((f for f in os.listdir(frames_dir) if _frame_number(f)), key=_frame_number)
    if last is not None:
        files = [f for f in files if _frame_number(f) <= last]
        missing = sorted(set(range(1, last + 1)) - {_frame_number(f) for f in files})
        if missing:
            raise RuntimeError(f"{len(missing)} of {last} frames are missing (first: frame {missing[0]})")
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
        from . import video
        label_dir = os.path.join(frames_dir, "_labels")
        if finishing is not None and finishing.label_track:
            finishing.label_dir = label_dir
        plan = video.build_sequence(enc, [os.path.join(frames_dir, f) for f in files], (width, height), fps,
                                    finishing, steps, white_under=white_under)
        _no_frame_cache(enc)
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
        if plan.music is not None:                        # task 0025: music under the video
            ff.audio_codec = "AAC"
            ff.audio_bitrate = 192
            ff.audio_mixrate = 48000
            ff.audio_channels = "STEREO"
        else:
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
        shutil.rmtree(os.path.join(frames_dir, "_labels"), ignore_errors=True)
    return out_path
