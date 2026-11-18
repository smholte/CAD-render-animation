"""Fresing Render – pictures and a video for the web page (task 0047).

Run by "Make site pictures.bat" with the Blender of the installed Fresing Render, in the background:

    blender.exe --background --python make_site_pictures.py -- <models folder> <output folder> [settings file]

For every model in the settings file (models.ini next to this script) it does what a user would do in the app:
import the STEP file with the app's own importer and sorting rules, pick a light look and surroundings, add the
camera views, render the stills on the graphics card (Cycles) and a short video through the app's own animation
code. A model with ``project = <name>`` (task 0112) first becomes a project that moves: joints, cylinders, poses and an
animation from ``projects/<name>.json`` (``projects.py``). ``video`` is ``turntable`` (one turn round the machine),
``product`` (6 Animation > Make a product video: a turn, the motions, a take-apart), ``animation`` (the project's own
animation, a seamless loop) or ``none``; ``weather`` puts a preset of 5 Scene & Render > Weather & time on. Everything
goes into the output folder:

    full/<model>_<view>.png       the full-size pictures (keep them)
    full/<model>.blend            the project, to open in Fresing Render and change by hand
    send/<model>_<view>.jpg       web copies
    send/<model>_<video>.mp4      the videos (web size) and send/<model>_<video>_poster.jpg, a picture of each
    send/site_pictures.json       what each picture shows and the model's credit line
    site_pictures_<date>.zip      send/ and log.txt in one file: upload this one (README.txt says where)
    contact_sheet.html            all pictures on one page (double-click to look at them)
    log.txt                       what was done, with the app's version and the times

It also runs on Linux with Blender as a Python module (the tests in tests/test_site.py) or a Linux Blender,
with ``--small`` (480 px wide, Draft, processor, short videos): ``python make_site_pictures.py <models> <out> --small``.
``--start-at=HH:MM`` waits until then (the PC stays awake); the expected time is shown before it starts.

Task 0144: the start window (kit_window.ps1) asks ``--estimate-json=<file>`` first (the models with their expected
seconds, the saved standard, a run to continue), then starts the run with ``--choices=<file>`` (graphics-card load,
max temperature, quiet hours, models, start time, what happens at the end) and ``--resume`` to continue a run that
stopped. Pauses between frames, the temperature guard, Pause / Stop and the run's state: kit_run.py.
"""

from __future__ import annotations

import configparser
import html
import importlib
import json
import os
import shutil
import sys
import time
import traceback
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import kit_run  # noqa: E402  (next to this file; no Blender)

DEFAULTS = {
    "width": "2400", "height": "1350", "quality": "final", "import_quality": "fine",
    "video_seconds": "10", "video_quality": "preview", "video_height": "MIDDLE",
}
VIDEOS = ("none", "turntable", "product", "animation")
KIT_SHEETS = os.path.join(HERE, "projects")
VIEW_NAMES = ("ISOMETRIC", "FRONT", "SIDE", "TOP", "LOW", "HIGH", "ISO", "ISO_LEFT")
LOOKS = ("PRODUCT", "WHITE", "DARK", "SUN", "OVERCAST")
BACKGROUNDS = ("COLOR", "SKY", "SEA", "DECK", "QUAY", "FACTORY", "CNC", "ASSEMBLY", "WAREHOUSE")
QUALITIES = ("draft", "preview", "final", "best")


class Log:
    def __init__(self, path: str, append: bool = False):
        self.path = path
        self.t0 = time.time()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a" if append else "w", encoding="utf-8") as fh:
            fh.write(f"Fresing site pictures – {'continued' if append else 'started'} "
                     f"{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    def __call__(self, text: str) -> None:
        line = f"[{time.time() - self.t0:7.0f} s] {text}"
        print(line, flush=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return [w.strip().upper() for w in text.replace(";", ",").split(",") if w.strip()]


def _read_text(path: str) -> str:
    """models.ini as Notepad may save it: UTF-8 (with or without BOM), "Unicode" (UTF-16) or ANSI."""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def find_model(models_dir: str, name: str) -> str:
    """The model file, also when Windows hid the extension while renaming ("evo.step.step") or the case
    differs; when it is not in ``models_dir``, also in the "models" folder of an older kit next to this one (task 0112:
    the new kit brings Thor and the press, the owner's first kit has the others). '' when there is none."""
    hit = _find_in(models_dir, name)
    if hit or os.path.isabs(name):
        return hit
    kit = os.path.dirname(os.path.abspath(models_dir))
    try:
        siblings = sorted(os.listdir(os.path.dirname(kit)))
    except OSError:
        return ""
    for sib in siblings:
        other = os.path.join(os.path.dirname(kit), sib)
        if os.path.normcase(other) == os.path.normcase(kit) or not os.path.isdir(other):
            continue
        for sub in ("models", os.path.join(sib, "models")):          # unzipped once or twice ("x\\x\\models")
            hit = _find_in(os.path.join(other, sub), name)
            if hit:
                return hit
    return ""


def _find_in(models_dir: str, name: str) -> str:
    path = name if os.path.isabs(name) else os.path.join(models_dir, name)
    if os.path.isfile(path):
        return path
    folder, base = os.path.split(path)
    stem = os.path.splitext(base)[0].lower()
    try:
        files = os.listdir(folder)
    except OSError:
        return ""
    wanted = {base.lower(), base.lower() + ".step", base.lower() + ".stp", stem + ".step", stem + ".stp",
              stem + ".step.step", stem + ".stp.stp", stem}
    for f in sorted(files):
        if f.lower() in wanted and os.path.isfile(os.path.join(folder, f)):
            return os.path.join(folder, f)
    return ""


def parse_clock(text: str) -> tuple[int, int]:
    """'23:30' (or '23.30', '2330') -> (23, 30). Raises ValueError with a plain reason."""
    t = text.strip().replace(".", ":")
    if ":" not in t and len(t) in (3, 4) and t.isdigit():
        t = t[:-2] + ":" + t[-2:]
    try:
        h, mnt = (int(x) for x in t.split(":"))
    except ValueError:
        raise ValueError(f"start time '{text}': type it like 23:30") from None
    if not (0 <= h < 24 and 0 <= mnt < 60):
        raise ValueError(f"start time '{text}': type it like 23:30")
    return h, mnt


def seconds_until(h: int, mnt: int, now: float | None = None) -> float:
    """Seconds from now to the next h:mm (today, or tomorrow when it has passed)."""
    now = time.time() if now is None else now
    lt = time.localtime(now)
    target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, mnt, 0, 0, 0, -1))
    if target <= now:
        target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, h, mnt, 0, 0, 0, -1))
    return target - now


def wait_until(text: str, log, sleep=time.sleep, pacer=None) -> None:
    """Wait until h:mm. With a ``pacer`` (task 0144) the wait is in short steps and Stop in the status window ends
    it (``kit_run.Stopped``)."""
    h, mnt = parse_clock(text)
    left = seconds_until(h, mnt)
    log(f"Waiting until {h:02d}:{mnt:02d} ({left / 3600:.1f} h). The PC stays awake; close this window to cancel.")
    if pacer is not None:
        pacer.show(state="waiting", step=f"Starts at {h:02d}:{mnt:02d}")
    last_said = left
    while left > 0:
        step = min(left, 600.0 if pacer is None else 5.0)
        if pacer is not None:
            pacer.checkpoint()
        sleep(step)
        left -= step
        if left > 0 and last_said - left >= 600.0 - 1e-6:
            last_said = left
            log(f"  starting in {left / 60:.0f} min")


# ---------------------------------------------------------------------------
# the expected time (task 0112): rules of thumb for an RTX 3090, refined by the kit's own first still
# ---------------------------------------------------------------------------

SAMPLES = {"draft": 48, "preview": 128, "final": 512, "best": 2048, "eevee": 0}
GPU_S_PER_MPIX_SAMPLE = 0.02      # Cycles on an RTX 3090, a machine in a studio light (an assumption, see the report)
EEVEE_S_PER_FRAME = 1.5
FRAME_OVERHEAD_S = 1.0            # per video frame: the app's work, saving the picture
IMPORT_S_PER_MB = 0.4             # the STEP import at Fine on 24 cores
PROJECT_S = 60.0                  # joints, poses, the animation built


def video_frames(m: dict, general: dict, small: bool = False) -> int:
    """Frames of the model's video (25 fps; the turntable's own length, a product video ~30 s, the loop's length)."""
    if m["video"] == "none":
        return 0
    if small:
        return 12
    if m["video"] == "turntable":
        return int(float(m.get("video_seconds", general["video_seconds"])) * 25)
    if m["video"] == "product":
        return 30 * 25
    try:
        with open(os.path.join(KIT_SHEETS, m["project"] + ".json"), encoding="utf-8") as fh:
            return int(round(float(json.load(fh)["animation"]["seconds"]) * 25))
    except (OSError, ValueError, KeyError):
        return 250


def estimate_parts(m: dict, general: dict, models_dir: str, rate: float = GPU_S_PER_MPIX_SAMPLE) -> dict:
    """One model's expected seconds in parts (task 0144): 'cpu' (import, project – no graphics card), 'still' (one
    still), 'stills' (all), 'video' (its frames: the graphics card's work the pauses stretch), 'gpu' = stills + video."""
    w, h = float(general["width"]), float(general["height"])
    path = find_model(models_dir, m["file"])
    mb = os.path.getsize(path) / 1e6 if path else 0.0
    cpu = mb * IMPORT_S_PER_MB + (PROJECT_S if m["project"] else 0.0)
    q = m.get("quality", general["quality"])
    still = (w * h / 1e6) * SAMPLES.get(q, 512) * rate
    vq = m.get("video_quality", general["video_quality"])
    frames = video_frames(m, general)
    per = EEVEE_S_PER_FRAME if vq == "eevee" else 1920 * 1080 / 1e6 * SAMPLES.get(vq, 128) * rate
    video = frames * (per + FRAME_OVERHEAD_S)
    stills = len(m["views"]) * still
    return {"cpu": cpu, "still": still, "stills": stills, "video": video, "gpu": stills + video,
            "total": cpu + stills + video}


def estimate(models: list[dict], general: dict, models_dir: str, rate: float = GPU_S_PER_MPIX_SAMPLE) -> dict:
    """{model id: seconds} and 'total' (s): the import, the stills and the video of each model, at full load.
    ``rate`` = seconds per megapixel and sample (Cycles); the kit measures it on its first still and estimates again."""
    out = {m["id"]: estimate_parts(m, general, models_dir, rate)["total"] for m in models}
    out["total"] = sum(out.values())
    return out


def left_parts(m: dict, general: dict, models_dir: str, state=None, rate: float = GPU_S_PER_MPIX_SAMPLE) -> dict:
    """{'gpu', 'cpu'} seconds still to do of model ``m`` (finished stills and clip of a run being continued left out;
    a model not complete is imported again)."""
    p = estimate_parts(m, general, models_dir, rate)
    if state is None:
        return {"gpu": p["gpu"], "cpu": p["cpu"]}
    if m["id"] in state.data["complete"]:
        return {"gpu": 0.0, "cpu": 0.0}
    gpu = sum(p["still"] for v in m["views"] if not state.is_done(m["id"], f"still:{v.lower()}"))
    gpu += 0.0 if state.is_done(m["id"], "video") else p["video"]
    return {"gpu": gpu, "cpu": p["cpu"]}


def say_time(seconds: float) -> str:
    m = int(round(seconds / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{max(1, m)} min"


def keep_awake() -> None:
    """Windows: no sleep while the pictures render (as the render queue does; released when Blender ends)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass


def parse_colours(text: str, where: str) -> list[tuple[str, str, str]]:
    """'colours =' lines: <part name pattern> = <material> [colour] -> [(pattern, material, colour)].
    Patterns use * (any text) and ? (one character), not case sensitive; the first line that fits a part wins."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith((";", "#")):
            continue
        if "=" not in line:
            raise ValueError(f"[{where}] colours: '{line}' needs 'part name = material colour'")
        pattern, look = (x.strip() for x in line.split("=", 1))
        words = look.split(None, 1)
        if not pattern or not words:
            raise ValueError(f"[{where}] colours: '{line}' needs 'part name = material colour'")
        out.append((pattern, words[0], words[1] if len(words) > 1 else ""))
    return out


WEATHER = {"CLEAR_DAY": "Clear day", "GREY_NORTH_SEA": "Grey North Sea", "STORM": "Storm",
           "SNOW_QUAY": "Snow at the quay", "NIGHT_SHIFT": "Night shift"}      # 5 Scene & Render > Weather & time


def weather_id(text: str, where: str) -> str:
    """A weather preset by its id (CLEAR_DAY) or its name in the app (Clear day); '' for none."""
    t = text.strip()
    if not t or t.lower() == "none":
        return ""
    for k, label in WEATHER.items():
        if t.upper().replace(" ", "_") == k or t.lower() == label.lower():
            return k
    raise ValueError(f"[{where}] weather = {t}: use none or one of {', '.join(WEATHER.values())}")


def sheet_cameras(project: str) -> dict:
    """{NAME IN CAPITALS: name} of the cameras a project's sheet brings (task 0116: e.g. "Work boat")."""
    if not project:
        return {}
    try:
        with open(os.path.join(KIT_SHEETS, project + ".json"), encoding="utf-8") as fh:
            return {c["name"].upper(): c["name"] for c in json.load(fh).get("cameras", [])}
    except (OSError, ValueError, KeyError):
        return {}


def read_settings(path: str) -> tuple[dict, list[dict]]:
    """The [settings] section and one dict per model section, checked. Raises ValueError with a plain
    reason when something is wrong (shown in the window and the log)."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(_read_text(path))
    general = dict(DEFAULTS)
    if cp.has_section("settings"):
        general.update({k: v.strip() for k, v in cp.items("settings")})
    general["start_at"] = general.get("start_at", "").strip()
    if general["start_at"]:
        parse_clock(general["start_at"])
    for key in ("width", "height", "video_seconds"):
        try:
            float(general[key])
        except ValueError:
            raise ValueError(f"[settings] {key} = {general[key]}: must be a number") from None
    for key in ("quality", "video_quality"):
        if general[key] not in QUALITIES + (("eevee",) if key == "video_quality" else ()):
            raise ValueError(f"[settings] {key} = {general[key]}: use one of {', '.join(QUALITIES)}")
    models = []
    for sec in cp.sections():
        if sec == "settings":
            continue
        m = {k: v.strip() for k, v in cp.items(sec)}
        m["id"] = sec
        if not m.get("file"):
            raise ValueError(f"[{sec}] has no 'file = …' line")
        m["views"] = _words(m.get("views", "LOW, ISO_LEFT")) or ["LOW"]
        own = sheet_cameras(m.get("project", "").strip())
        bad = [v for v in m["views"] if v not in VIEW_NAMES and v.upper() not in own]
        if bad:
            raise ValueError(f"[{sec}] views: {', '.join(bad)} unknown; use {', '.join(VIEW_NAMES)}"
                             + (f" or a camera of the project: {', '.join(own.values())}" if own else ""))
        m["look"] = m.get("look", "PRODUCT").upper()
        if m["look"] not in LOOKS:
            raise ValueError(f"[{sec}] look = {m['look']}: use one of {', '.join(LOOKS)}")
        m["surroundings"] = m.get("surroundings", "COLOR").upper()
        if m["surroundings"] not in BACKGROUNDS:
            raise ValueError(f"[{sec}] surroundings = {m['surroundings']}: use one of {', '.join(BACKGROUNDS)}")
        m["video"] = m.get("video", "none").lower()
        if m["video"] not in VIDEOS:
            raise ValueError(f"[{sec}] video = {m['video']}: use {', '.join(VIDEOS)}")
        m["project"] = m.get("project", "").strip()
        if m["project"] and not os.path.isfile(os.path.join(KIT_SHEETS, m["project"] + ".json")):
            raise ValueError(f"[{sec}] project = {m['project']}: no projects\\{m['project']}.json next to this file")
        if m["video"] == "animation" and not m["project"]:
            raise ValueError(f"[{sec}] video = animation needs a 'project = …' line (the animation comes from it)")
        m["weather"] = weather_id(m.get("weather", ""), sec)
        if m["weather"] and m["surroundings"] in ("COLOR",):
            raise ValueError(f"[{sec}] weather = {m['weather']}: the weather needs surroundings outdoors "
                             f"(SKY, SEA, DECK or QUAY), not {m['surroundings']}")
        m["take_apart"] = m.get("take_apart", "auto").strip() or "auto"
        m["up_axis"] = m.get("up_axis", "Z").upper()
        if m["up_axis"] not in ("Z", "Y"):
            raise ValueError(f"[{sec}] up_axis = {m['up_axis']}: use Z or Y")
        for key in ("lens", "rotate_light"):
            if key in m:
                try:
                    float(m[key])
                except ValueError:
                    raise ValueError(f"[{sec}] {key} = {m[key]}: must be a number") from None
        m["colours"] = parse_colours(m.get("colours", ""), sec)
        if not m.get("credit"):
            raise ValueError(f"[{sec}] has no 'credit = …' line (the licence needs it on the page)")
        models.append(m)
    if not models:
        raise ValueError("models.ini lists no models")
    return general, models


# ---------------------------------------------------------------------------
# the app
# ---------------------------------------------------------------------------

def load_app():
    """The installed Fresing Render (real Blender), or the package next to this repository (Blender as a
    Python module, the tests). Returns the package module."""
    import bpy
    try:
        import addon_utils
        for mod in addon_utils.modules():
            if mod.__name__ == "fresing_render" or mod.__name__.endswith(".fresing_render"):
                addon_utils.enable(mod.__name__, default_set=True)
                if "cycles" not in bpy.context.preferences.addons:
                    addon_utils.enable("cycles", default_set=False)
                return importlib.import_module(mod.__name__)
    except ImportError:
        pass
    repo = os.path.dirname(os.path.dirname(HERE))
    if os.path.isdir(os.path.join(repo, "fresing_render")) and repo not in sys.path:
        sys.path.insert(0, repo)
    pkg = importlib.import_module("fresing_render")
    if not hasattr(bpy.types.Scene, "fresing"):
        pkg.register()
    return pkg


def fresh_import(pkg, path: str, quality: str, up_axis: str, out_dir: str):
    import bpy
    prefs = importlib.import_module(pkg.__name__ + ".blender.prefs").get()
    bpy.ops.wm.read_homefile(use_empty=True)
    try:                                         # app 0.2.151 and newer: every function, never locked
        importlib.import_module(pkg.__name__ + ".blender.workspaces").use_all(bpy.context.scene)
    except (ImportError, AttributeError):
        pass
    saved = prefs.default_template if prefs else ""
    if prefs:
        prefs.default_template = ""          # the built-in sorting rules, not the owner's own template
    try:
        scene = bpy.context.scene
        s = scene.fresing
        s.out_folder = out_dir
        s.import_quality = quality
        s.import_up_axis = up_axis
        res = bpy.ops.fresing.import_step(filepath=path, quality=quality, up_axis=up_axis)
        if res != {"FINISHED"}:
            raise RuntimeError(f"the import returned {res}: {s.last_message}")
    finally:
        if prefs:
            prefs.default_template = saved
    return bpy.context.scene


def paint(pkg, scene, rules: list[tuple[str, str, str]]) -> dict:
    """Give parts whose names fit a 'colours' line that material and colour (a group "Site: <pattern>" each, as
    the owner would make by hand). Returns {pattern: parts}."""
    import fnmatch
    build = importlib.import_module(pkg.__name__ + ".blender.build")
    logic = importlib.import_module(pkg.__name__ + ".blender.logic")
    materials = importlib.import_module(pkg.__name__ + ".blender.materials")
    lib = importlib.import_module(pkg.__name__ + ".core.materials_lib")
    ral = importlib.import_module(pkg.__name__ + ".core.ral")
    known = set(getattr(lib, "MATERIALS", {}))
    s = scene.fresing
    groups, counts = {}, {}
    for pattern, mat_id, colour in rules:
        if known and mat_id not in known:
            raise RuntimeError(f"colours: material '{mat_id}' unknown; use one of {', '.join(sorted(known))}")
        if colour and ral.parse_colour(colour) is None:
            raise RuntimeError(f"colours: colour '{colour}' unknown; use a RAL number (RAL 2004) or #RRGGBB")
        g = logic.ensure_group(s, f"Site: {pattern}")
        g.material = mat_id
        g.color = colour
        groups[pattern] = materials.ensure_material(g.name, g.material, g.color)
        counts[pattern] = 0
    for ob in build.iter_parts(scene):
        name = str(ob.get(build.PROP_NAME, ob.name)).lower()
        for pattern, _mat, _col in rules:
            if fnmatch.fnmatchcase(name, pattern.lower()):
                ob[build.PROP_GROUP] = f"Site: {pattern}"
                materials.assign(ob, groups[pattern])
                counts[pattern] += 1
                break
    for g in s.groups:
        if g.name.startswith("Site: "):
            g.count = counts.get(g.name[6:], 0)
    return counts


def set_scene(pkg, scene, m: dict, size: tuple[int, int]) -> None:
    import bpy
    s = scene.fresing
    bpy.ops.fresing.light_look(look=m["look"])
    if m["surroundings"] != "COLOR":
        s.env_detail = "DETAILED"
        s.background = m["surroundings"]
    if "rotate_light" in m:
        s.light_rotation = float(m["rotate_light"])
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = size


def jpg_copy(png: str, jpg: str, width: int, quality: int = 90) -> None:
    """A JPG copy of a PNG, ``width`` pixels wide (smaller only), with Blender's own image code."""
    import bpy
    img = bpy.data.images.load(png)
    try:
        w, h = img.size
        if w > width:
            img.scale(width, max(1, round(h * width / w)))
        img.file_format = "JPEG"
        img.save(filepath=jpg, quality=quality)
    finally:
        bpy.data.images.remove(img)


def web_mp4(pkg, frames_dir: str, out_path: str, width: int, height: int, fps: int, files: list | None = None) -> str:
    """The rendered frames as an H.264 MP4 small enough for a web page (the app's own encoder, one quality
    step lower than its videos)."""
    import bpy
    video = importlib.import_module(pkg.__name__ + ".blender.video")
    files = files if files is not None else sorted(
        f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")
        and not f.endswith((".tmp.png", ".part.png")))
    if not files:
        raise RuntimeError("no frames to put in the video")
    enc = bpy.data.scenes.new("FR site video")
    try:
        r = enc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = width, height, 100
        r.fps, r.fps_base = fps, 1.0
        enc.frame_start, enc.frame_end = 1, len(files)
        enc.view_settings.view_transform = "Standard"
        video.build_sequence(enc, [os.path.join(frames_dir, f) for f in files], (width, height), fps, None, None)
        im = r.image_settings
        try:
            im.media_type = "VIDEO"
        except (AttributeError, TypeError):
            pass
        im.file_format = "FFMPEG"
        ff = r.ffmpeg
        ff.format, ff.codec, ff.constant_rate_factor, ff.ffmpeg_preset = "MPEG4", "H264", "MEDIUM", "BEST"
        ff.gopsize = max(1, fps)
        ff.audio_codec = "NONE"
        tmp = os.path.join(frames_dir, "_web")
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        r.filepath = os.path.join(tmp, "video")
        r.use_file_extension = True
        bpy.ops.render.render(animation=True, scene=enc.name)
        made = [f for f in os.listdir(tmp) if f.lower().endswith(".mp4")]
        if not made:
            raise RuntimeError("the video encoder wrote no file")
        if os.path.exists(out_path):
            os.remove(out_path)
        os.replace(os.path.join(tmp, made[0]), out_path)
        shutil.rmtree(tmp, ignore_errors=True)
    finally:
        bpy.data.scenes.remove(enc)
    return out_path


def _clean_frames(pkg, full: str, anim_name: str) -> None:
    """Frames of an earlier run of the same animation would be kept (the queue resumes): start afresh."""
    import bpy
    queue = importlib.import_module(pkg.__name__ + ".blender.queue")
    stem = queue.render._safe(os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "animation")
    for old in os.listdir(full):
        if old.startswith(f"{stem}_{queue.render._safe(anim_name)}_") and old.endswith("_site"):
            shutil.rmtree(os.path.join(full, old), ignore_errors=True)


def render_clip(pkg, scene, a, m: dict, quality: str, full: str, send: str, kind: str, log,
                loop: bool = False, poster_at: float = 1.0 / 3.0, pacer=None, resume: bool = False) -> tuple[str, str]:
    """Render animation ``a`` through the app's render queue (frames), then the web MP4 and a poster picture (the
    frame ``poster_at`` of the way in). A loop leaves its last frame out: it is the first one again. Returns the
    paths. ``pacer`` (task 0144) is called before every frame (the queue's should_stop): pauses, temperature, Pause and
    Stop. ``resume`` keeps the frames an earlier run of the same clip made (the queue's own resume)."""
    queue = importlib.import_module(pkg.__name__ + ".blender.queue")
    a.video = "PNG"                              # the frames; the web MP4 is made below
    job = {"id": "site", "kind": "ANIMATION", "animation": a.name, "quality": quality, "out_dir": full,
           "label": kind, "watermark": False}
    last = [0.0]

    def progress(pct, msg):
        if pacer is not None:
            pacer.clip_progress(pct, msg)
        if time.time() - last[0] > 20 or pct >= 95:
            last[0] = time.time()
            log(f"  video {pct:.0f}%: {msg}")

    if not resume:
        _clean_frames(pkg, full, a.name)
    if pacer is not None:
        pacer.start_clip()
    folder = queue.render_animation(scene, job, progress, pacer.frame_hook if pacer is not None else (lambda: False))
    if pacer is not None:
        pacer.end_clip()
    frames = sorted(f for f in os.listdir(folder) if f.startswith("frame_") and f.endswith(".png")
                    and not f.endswith((".tmp.png", ".part.png")))
    if loop and len(frames) > 2:
        frames = frames[:-1]
    size = scene.render.resolution_x, scene.render.resolution_y
    out = os.path.join(send, f"{m['id']}_{kind}.mp4")
    web_mp4(pkg, folder, out, size[0], size[1], int(a.fps), frames)
    poster = os.path.join(send, f"{m['id']}_{kind}_poster.jpg")
    jpg_copy(os.path.join(folder, frames[min(len(frames) - 1, int(len(frames) * poster_at))]), poster, size[0],
             quality=88)
    return out, poster


def turntable_video(pkg, scene, m: dict, general: dict, full: str, send: str, small: bool, log,
                    **pace) -> tuple[str, str]:
    turntable = importlib.import_module(pkg.__name__ + ".blender.turntable")
    s = scene.fresing
    s.turntable_seconds = 2.0 if small else float(m.get("video_seconds", general["video_seconds"]))
    s.turntable_height = m.get("video_height", general["video_height"]).upper()
    s.turntable_quality = "draft" if small else general["video_quality"]
    a = turntable.make(scene)["animation"]
    a.out_format = "presentation"
    a.out_resolution = "preview" if small else "hd"
    if small:
        a.fps = "24"
    return render_clip(pkg, scene, a, m, s.turntable_quality, full, send, "turntable", log, **pace)


def _open_to(pkg, scene, ob) -> bool:
    """Select a sub-assembly in 2 Structure as a user would: open its parents' rows, click its row."""
    tree = importlib.import_module(pkg.__name__ + ".blender.tree")
    p = ob.parent
    while p is not None:
        p[tree.OPEN] = True
        p = p.parent
    tree.rebuild(scene)
    s = scene.fresing
    for i, row in enumerate(s.tree):
        if row.obj is not None and row.obj.name == ob.name:
            s.tree_index = i
            return True
    return False


def product_video(pkg, scene, m: dict, general: dict, full: str, send: str, small: bool, log,
                  **pace) -> tuple[str, str]:
    """6 Animation > Make a product video (task 0101), about 30 s, no title or end card (a gallery clip loops)."""
    pv = importlib.import_module(pkg.__name__ + ".blender.product_video")
    build = importlib.import_module(pkg.__name__ + ".blender.build")
    s = scene.fresing
    s.pv_seconds = "30"
    s.pv_title_on = s.pv_end_on = False
    s.pv_captions = False
    s.pv_title = m.get("title", "")
    want = m["take_apart"]
    if want.lower() == "none":
        s.pv_sub = "NONE"
    elif want.lower() == "auto":
        s.pv_sub = "AUTO"
    else:
        hits = [o for o in scene.objects if o.get(build.PROP_NAME) == want and o.get(build.PROP_KIND) == "assembly"]
        if len(hits) != 1 or not _open_to(pkg, scene, hits[0]):
            raise RuntimeError(f"take_apart = {want}: no (single) sub-assembly of that name")
        s.pv_sub = "SELECTED"
    info = pv.make(scene)
    a = info["animation"]
    if info.get("left_out"):
        log("  product video leaves out: " + "; ".join(info["left_out"]))
    a.out_format = "presentation"
    a.out_resolution = "preview" if small else "hd"
    quality = "draft" if small else general["video_quality"]
    if small:                                    # the tests: a few frames of it are enough
        seq = [i for i, b in enumerate(a.blocks) if b.kind == "SEQUENCE"]
        if seq:                                  # chosen and planned above; its frames cost the most: not rendered
            log(f"  small test: {info['sub'].get(build.PROP_NAME)} is chosen, its steps are not rendered")
            for i in reversed(seq):
                a.blocks.remove(i)
        _shorten(a, 0.5)
    # the poster: its first picture, the camera that frames the whole machine (later ones may be close-ups)
    return render_clip(pkg, scene, a, m, quality, full, send, "product", log, poster_at=0.0, **pace)


def _shorten(a, seconds: float) -> None:
    """The small test: the animation squeezed into ``seconds`` at 24 fps (a few frames)."""
    a.fps = "24"
    a.tail = 0.0
    total = max((b.start + b.duration for b in a.blocks), default=1.0) or 1.0
    k = seconds / total
    for b in a.blocks:
        b.start *= k
        b.duration *= k
        if b.kind == "SEQUENCE":                 # its length follows from its parts: the time per part
            b.seq_part_time = max(0.01, b.seq_part_time * k)


def animation_video(pkg, scene, m: dict, general: dict, full: str, send: str, small: bool, log,
                    **pace) -> tuple[str, str]:
    """The project's own animation (its sheet), as a seamless loop."""
    projects = _projects()
    a = projects.animation_item(scene, projects.load(os.path.join(KIT_SHEETS, m["project"] + ".json")))
    if a is None:
        raise RuntimeError(f"the project {m['project']} has no animation")
    a.out_format = "presentation"
    a.out_resolution = "preview" if small else "hd"
    quality = "draft" if small else general["video_quality"]
    if small:
        _shorten(a, 0.5)
    return render_clip(pkg, scene, a, m, quality, full, send, "loop", log, loop=True, **pace)


def _projects():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import projects
    return projects


def make_project(pkg, scene, m: dict, log) -> dict:
    """The model as a project that moves (projects/<name>.json): joints, cylinders, poses, its animation."""
    projects = _projects()
    sheet = projects.load(os.path.join(KIT_SHEETS, m["project"] + ".json"))
    res = projects.make(pkg, scene, sheet, check=False, log=log)
    animation = importlib.import_module(pkg.__name__ + ".blender.animation")
    if animation.has_keys(scene):                # stills and videos start from the model as it stands
        animation.clear_keys(scene)
    return res


def refresh_start_shot(pkg, scene, m: dict) -> None:
    """The project's animation starts from a saved scene stored when the project was made; Build puts its light,
    surroundings and weather back. Store it again now that the look and the weather are set (same camera, same pose)."""
    states = importlib.import_module(pkg.__name__ + ".blender.states")
    a = _projects().animation_item(scene, _projects().load(os.path.join(KIT_SHEETS, m["project"] + ".json")))
    shot = scene.fresing.shots.get(a.start_shot) if a is not None and a.start_shot else None
    if shot is not None:
        states.save_shot(scene, shot.name, camera=shot.camera)


def set_weather(pkg, scene, preset: str) -> None:
    weather = importlib.import_module(pkg.__name__ + ".blender.weather")
    scene.fresing.weather.enabled = True
    weather.use_preset(scene, preset)


VIDEO_MAKERS = {"turntable": turntable_video, "product": product_video, "animation": animation_video}


def do_model(pkg, m: dict, general: dict, models_dir: str, out: str, small: bool, log, cpu: bool = False,
             clock: dict | None = None, pacer=None, state=None, resume: bool = False) -> list[dict]:
    """One model: import, colours, project, look, stills, video, the .blend. With a ``state`` (task 0144) every
    finished still and clip is recorded at once, and those an earlier run finished are skipped."""
    import bpy
    render = importlib.import_module(pkg.__name__ + ".blender.render")
    cameras = importlib.import_module(pkg.__name__ + ".blender.cameras")
    states = importlib.import_module(pkg.__name__ + ".blender.states")
    full, send = os.path.join(out, "full"), os.path.join(out, "send")
    path = find_model(models_dir, m["file"])
    if not path:
        raise RuntimeError(f"file not found: {m['file']} in {models_dir} – put it in the models folder or fix "
                           f"'file =' in models.ini")
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(models_dir):
        log(f"  {m['file']} taken from {os.path.dirname(path)}")
    t0 = time.time()
    scene = fresh_import(pkg, path, "draft" if small else m.get("import_quality", general["import_quality"]),
                         m["up_axis"], full)
    parts = sum(1 for _ in importlib.import_module(pkg.__name__ + ".blender.build").iter_parts(scene))
    log(f"  imported {parts} parts in {time.time() - t0:.0f} s")
    width = 480 if small else int(float(general["width"]))
    height = round(width * float(general["height"]) / float(general["width"]))
    if m["colours"]:
        counts = paint(pkg, scene, m["colours"])
        log("  colours: " + ", ".join(f"{p} {n}" for p, n in counts.items()))
    if m["project"]:
        make_project(pkg, scene, m, log)
    set_scene(pkg, scene, m, (width, height))
    if m["weather"]:
        set_weather(pkg, scene, m["weather"])
        log(f"  weather: {WEATHER[m['weather']]}")
    try:                                         # the marine growth look follows the sea just set (task 0116)
        importlib.import_module(pkg.__name__ + ".blender.marine_looks").sync(scene)
    except ImportError:
        pass
    if m["project"]:
        refresh_start_shot(pkg, scene, m)
    s = scene.fresing
    s.use_gpu = not (small or cpu)
    quality = "draft" if small else m.get("quality", general["quality"])
    pose = m.get("pose", "").strip()
    if pose:
        if not states.apply_pose(scene, pose):
            raise RuntimeError(f"pose = {pose}: the project has no saved pose of that name")
        bpy.context.view_layer.update()
    made = []
    captions = [c.strip() for c in m.get("captions", "").split("|")]
    own = sheet_cameras(m["project"])
    for i, view in enumerate(m["views"]):
        unit = f"still:{view.lower()}"
        jpg = os.path.join(send, f"{m['id']}_{view.lower().replace(' ', '_')}.jpg")
        if view not in VIEW_NAMES and view.upper() in own:       # a camera the project brings (its sheet)
            projects = _projects()
            sheet = projects.load(os.path.join(KIT_SHEETS, m["project"] + ".json"))
            cam = projects.sheet_camera(pkg, scene, projects.Model(pkg, scene, sheet), own[view.upper()])
        else:
            cam = cameras.add_camera(scene, view, lens=float(m.get("lens", 50)), name=f"Site {view}",
                                     margin=cameras.SPACE.get(m.get("space", "NORMAL").upper(), 1.06))
        scene.camera = cam
        png = os.path.join(full, f"{m['id']}_{view.lower().replace(' ', '_')}.png")
        if state is not None and state.is_done(m["id"], unit) and os.path.isfile(jpg):
            # the camera is made all the same: the scene must be as in the earlier run, or the clip's frames that
            # run made are not kept (the queue compares a fingerprint of every object)
            log(f"  {view}: done in the earlier run")
            continue
        if pacer is not None:
            pacer.show(step=f"Picture {i + 1} of {len(m['views'])} ({view})")
            pacer.before_still()
        t1 = time.time()
        info = render.render_still(scene, s, quality, filepath=png)
        took = time.time() - t1
        if clock is not None and quality in SAMPLES and SAMPLES[quality]:
            clock.setdefault("rates", []).append(took / (info["size"][0] * info["size"][1] / 1e6 * SAMPLES[quality]))
        jpg_copy(png, jpg, width)
        caption = captions[i] if i < len(captions) and captions[i] else m.get("title", m["id"])
        made.append({"file": os.path.basename(jpg), "model": m["id"], "caption": caption, "kind": "picture"})
        log(f"  {view}: {info['size'][0]}×{info['size'][1]} on {info['device']} in {took:.0f} s")
        if state is not None:
            state.record(m["id"], unit, made[-1])
        if pacer is not None:
            pause = pacer.after_still()
            if pause >= 1.0:
                log(f"  pause {pause:.0f} s ({pacer.status.get('load', 100)} % load)")
    if pose:                                     # the videos start from the model as it was made
        states.apply_pose(scene, (_projects().load(os.path.join(KIT_SHEETS, m["project"] + ".json"))
                                  .get("start_pose") or pose) if m["project"] else pose)
    video_done = state is not None and state.is_done(m["id"], "video")
    if video_done:
        log("  video: done in the earlier run")
    if m["video"] != "none" and not video_done:
        t1 = time.time()
        if pacer is not None:
            pacer.show(step="Video")
        pace = {"pacer": pacer, "resume": resume} if pacer is not None else {}
        mp4, poster = VIDEO_MAKERS[m["video"]](pkg, scene, m, general, full, send, small, log, **pace)
        default = {"turntable": "turntable", "product": "product video", "animation": "in motion"}[m["video"]]
        made.append({"file": os.path.basename(mp4), "poster": os.path.basename(poster), "model": m["id"],
                     "kind": "video", "video": m["video"], "loop": m["video"] in ("turntable", "animation"),
                     "caption": m.get("video_caption", f"{m.get('title', m['id'])}: {default}")})
        log(f"  video ({m['video']}): {os.path.getsize(mp4) / 1e6:.1f} MB in {time.time() - t1:.0f} s")
        if state is not None:
            state.record(m["id"], "video", made[-1])
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(full, f"{m['id']}.blend"), copy=True)
    return made


def contact_sheet(out: str, items: list[dict], models: list[dict], errors: list[str]) -> str:
    rows = []
    for it in items:
        src = "send/" + it["file"]
        poster = f' poster="send/{it["poster"]}"' if it.get("poster") else ""
        tag = (f'<video src="{src}"{poster} controls muted loop></video>' if it["kind"] == "video"
               else f'<a href="{src}"><img src="{src}" alt=""></a>')
        rows.append(f"<figure>{tag}<figcaption><b>{html.escape(it['file'])}</b><br>"
                    f"{html.escape(it['caption'])}</figcaption></figure>")
    credits = "".join(f"<li>{html.escape(m['credit'])}</li>" for m in models)
    errs = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
    page = (
        "<!doctype html><meta charset=utf-8><title>Fresing site pictures</title>"
        "<style>body{font:15px system-ui,sans-serif;margin:24px;color:#252E36;background:#F1F3F5}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px}"
        "figure{margin:0;background:#fff;padding:8px;border:1px solid #D3D9DE}img,video{width:100%}"
        ".err{color:#B42318}</style><h1>Fresing site pictures</h1>"
        + (f"<ul class=err>{errs}</ul>" if errs else "")
        + f"<main>{''.join(rows)}</main><h2>Credits</h2><ul>{credits}</ul>")
    path = os.path.join(out, "contact_sheet.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return path


def zip_name(when: float | None = None) -> str:
    return f"site_pictures_{time.strftime('%Y-%m-%d', time.localtime(when))}.zip"


def make_zip(out: str) -> str:
    """send/ and the log in one zip, named by the date: the file to upload (README.txt, step 6)."""
    send = os.path.join(out, "send")
    path = os.path.join(out, zip_name())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:     # JPG and MP4 do not shrink further
        for f in sorted(os.listdir(send)):
            z.write(os.path.join(send, f), f)
        log = os.path.join(out, "log.txt")
        if os.path.isfile(log):
            z.write(log, "log.txt")
    return path


def run(models_dir: str, out: str, settings: str, small: bool = False, only: str = "", cpu: bool = False,
        start_at: str = "", choices: str = "", resume: bool = False) -> int:
    log = Log(os.path.join(out, "log.txt"), append=resume)
    keep_awake()
    for old in os.listdir(out) if os.path.isdir(out) else ():         # never leave last run's results
        if old == "contact_sheet.html" or (old.startswith("site_pictures_") and old.endswith(".zip")) \
                or old == "Fresing site pictures.zip":
            try:
                os.remove(os.path.join(out, old))
            except OSError:
                pass
    code = 3
    try:
        code = _run_paced(models_dir, out, settings, small, only, cpu, log, start_at, choices, resume)
    finally:
        # real Blender turns every non-zero end into the code of --python-exit-code: the .bat reads the true code
        # (4 = stopped by hand) from this file (task 0144)
        try:
            with open(os.path.join(out, kit_run.RESULT), "w", encoding="ascii") as fh:
                fh.write(str(code))
        except OSError:
            pass
    return code


def _run_paced(models_dir, out, settings, small, only, cpu, log, start_at, choices, resume) -> int:
    pacer = None
    try:
        pacer = kit_run.Pacer(kit_run.load_choices(choices), out, log)
        return _run(models_dir, out, settings, small, only, cpu, log, start_at, pacer, resume)
    except kit_run.Stopped:
        log("Stopped before the first picture. Double-click the kit again to start.")
        if pacer is not None:
            pacer.show(state="stopped")
        return kit_run.STOPPED_CODE
    except Exception:
        log("PROBLEM (the run stopped):\n" + traceback.format_exc())
        if pacer is not None:
            pacer.show(state="stopped", step="Stopped with a problem: see log.txt")
        return 3


def describe_choices(c: dict) -> str:
    """The choices in one line for the log."""
    t = f"{c['load']} % load" + (f", max {c['max_temp']} °C" if c["max_temp"] else "")
    if c["quiet_on"]:
        t += (f"; quiet hours {c['quiet_start']}–{c['quiet_end']}: {c['quiet_load']} % load"
              + (f", max {c['quiet_max_temp']} °C" if c["quiet_max_temp"] else ""))
    return t + {"nothing": "", "sleep": "; sleep when done", "shutdown": "; shut down when done"}[c["when_done"]]


def _run(models_dir, out, settings, small, only, cpu, log, start_at="", pacer=None, resume=False) -> int:
    pacer = pacer or kit_run.Pacer(kit_run.DEFAULT_STANDARD, out, log)
    choices = pacer.c
    try:
        general, models = read_settings(settings)
        start_at = start_at or general["start_at"]
        if start_at:
            parse_clock(start_at)
    except (OSError, ValueError, configparser.Error) as exc:
        log(f"PROBLEM in {settings}: {exc}")
        return 2
    state = kit_run.RunState.load(out) if resume else None
    if resume and (state is None or state.data.get("finished")):
        log("There is no stopped run to continue in this output folder: starting a new run.")
        resume, state = False, None
    if resume:
        by_id = {m["id"]: m for m in models}
        gone = [i for i in state.data["models"] if i not in by_id]
        if gone:
            log("NOTE: no longer in models.ini, left out: " + ", ".join(gone))
        models = [by_id[i] for i in state.data["models"] if i in by_id]
        done, total = state.counts()
        log(f"Continuing the run of {state.data.get('started', '?')}: {done} of {total} pictures and clips done")
    else:
        wanted = choices.get("models")
        if isinstance(wanted, str):
            wanted = [w for w in wanted.split(",") if w]
        if wanted:
            unknown = [w for w in wanted if w not in {m["id"] for m in models}]
            if unknown:
                log("NOTE: not in models.ini, left out: " + ", ".join(unknown))
            models = [m for m in models if m["id"] in wanted]
        if only:
            models = [m for m in models if m["id"] in only.split(",")]
    log("Graphics card: " + describe_choices(choices))
    est = estimate(models, general, models_dir)
    rest = {"gpu": 0.0, "cpu": 0.0}
    for m in models:
        for k, v in left_parts(m, general, models_dir, state).items():
            rest[k] += v
    wall = kit_run.wall_seconds(rest["gpu"], rest["cpu"], time.time(), choices)
    log("Expected time on an RTX 3090 (a rough first guess; corrected after the first picture): about "
        + say_time(wall) + (f" with the pauses (at full load {say_time(rest['gpu'] + rest['cpu'])})"
                            if abs(wall - rest["gpu"] - rest["cpu"]) > 60 else "")
        + " – " + ", ".join(f"{m['id']} {say_time(est[m['id']])}" for m in models))
    if start_at:
        wait_until(start_at, log, pacer=pacer)
    for sub in ("full", "send"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    if not resume:
        for old in os.listdir(os.path.join(out, "send")):
            os.remove(os.path.join(out, "send", old))
        state = kit_run.RunState.new(out, models, choices)
    pkg = load_app()
    render = importlib.import_module(pkg.__name__ + ".blender.render")
    if small:                                    # a quick test on a machine without a graphics card
        render.QUALITY["draft"] = (8,) + tuple(render.QUALITY["draft"][1:])
    device = "processor (small test)" if small else "processor" if cpu else render.setup_gpu()
    log(f"Fresing Render {getattr(pkg, '__version__', '?')}, renders on: {device}")
    if not (small or cpu) and not device.startswith("GPU"):
        log("NOTE: no graphics card found – this will be very slow. Close the window to stop.")
    errors, clock = [], {}
    t_start = time.time()
    k_rate = [1.0]                               # measured rate / the rule of thumb
    parts = {m["id"]: estimate_parts(m, general, models_dir) for m in models}
    total_s = sum(p["total"] for p in parts.values()) or 1.0
    now_model = [None]

    def progress_fn():
        done_s = 0.0
        for m in models:
            p = parts[m["id"]]
            if m["id"] in state.data["complete"]:
                done_s += p["total"]
                continue
            done_s += p["still"] * sum(state.is_done(m["id"], f"still:{v.lower()}") for v in m["views"])
            if state.is_done(m["id"], "video"):
                done_s += p["video"]
            elif m["id"] == now_model[0]:
                done_s += p["video"] * pacer.status.get("clip", 0.0)
        left = {"gpu": 0.0, "cpu": 0.0}
        for m in models:
            for k, v in left_parts(m, general, models_dir, state).items():
                left[k] += v
        if now_model[0] is not None and not state.is_done(now_model[0], "video"):
            m = next(x for x in models if x["id"] == now_model[0])
            left["gpu"] -= parts[m["id"]]["video"] * pacer.status.get("clip", 0.0)
        end = time.time() + kit_run.wall_seconds(max(0.0, left["gpu"]) * k_rate[0], left["cpu"], time.time(), choices)
        return done_s / total_s, end

    pacer.progress_fn = progress_fn
    stopped = False
    for n, m in enumerate(models, 1):
        title = m.get("title", m["id"])
        if m["id"] in state.data["complete"]:
            log(f"Model {n} of {len(models)}: {m['id']} – done in the earlier run")
            continue
        log(f"Model {n} of {len(models)}: {m['id']} ({m['file']})")
        now_model[0] = m["id"]
        pacer.show(state="running", model=title, model_n=n, models=len(models), step="Importing and setting up")
        t_model = time.time()
        try:
            do_model(pkg, m, general, models_dir, out, small, log, cpu, clock, pacer=pacer, state=state, resume=resume)
            state.complete(m["id"])
        except kit_run.Stopped:
            stopped = True
            log("  STOPPED (status window): what is done is kept")
            break
        except Exception as exc:                  # one bad model must not stop the others
            traceback.print_exc()
            errors.append(f"{m['id']}: {exc}")
            log(f"  PROBLEM: {exc}")
        log(f"  {m['id']} took {say_time(time.time() - t_model)}")
        if clock.get("rates") and n < len(models) and not (small or cpu):
            rate = sorted(clock["rates"])[len(clock["rates"]) // 2]
            k_rate[0] = rate / GPU_S_PER_MPIX_SAMPLE
            left = {"gpu": 0.0, "cpu": 0.0}
            for x in models[n:]:
                for k, v in left_parts(x, general, models_dir, state, rate).items():
                    left[k] += v
            rest_s = kit_run.wall_seconds(left["gpu"], left["cpu"], time.time(), choices)
            log(f"  measured {rate:.4f} s per megapixel and sample: the rest takes about {say_time(rest_s)} "
                f"(done at about {time.strftime('%H:%M', time.localtime(time.time() + rest_s))})")
    now_model[0] = None
    items = state.all_items()
    used = {it["model"] for it in items}
    info = {"made": time.strftime("%Y-%m-%d %H:%M"), "app": getattr(pkg, "__version__", "?"), "device": device,
            "seconds": round(time.time() - t_start), "items": items,
            "models": {m["id"]: {k: m.get(k, "") for k in ("title", "credit", "link", "licence", "licence_link")}
                       for m in models if m["id"] in used}}
    with open(os.path.join(out, "send", "site_pictures.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)
    sheet = contact_sheet(out, items, [m for m in models if m["id"] in used], errors)
    if pacer.waited or pacer.cooled or pacer.paused_s:
        log(f"Pauses for the graphics card: {say_time(pacer.waited)}; waiting for it to cool: "
            f"{say_time(pacer.cooled) if pacer.cooled else 'none'}; paused by hand: "
            f"{say_time(pacer.paused_s) if pacer.paused_s else 'none'}")
    done, total = state.counts()
    log(f"{'Stopped' if stopped else 'Done'}: {sum(1 for i in items if i['kind'] == 'picture')} pictures, "
        f"{sum(1 for i in items if i['kind'] == 'video')} videos ({done} of {total} of the run), {len(errors)} problems, "
        f"in {say_time(time.time() - t_start)}")
    log(f"Contact sheet: {sheet}")
    z = make_zip(out)
    log(f"To upload: {z} ({os.path.getsize(z) / 1e6:.1f} MB)")
    if stopped:
        log("Double-click the kit again and tick 'Continue the run' to make the rest.")
        pacer.show(state="stopped", step=f"Stopped: {done} of {total} done")
        return kit_run.STOPPED_CODE
    state.finish()
    pacer.show(state="finished", step="Done", pct=100.0)
    return 1 if errors else 0


def show_estimate(models_dir: str, settings: str, only: str = "", json_path: str = "", out: str = "") -> int:
    """The .bat asks this first: the expected time, and the models whose STEP file is missing. With ``json_path``
    (task 0144) it also writes what the start window needs: each model's seconds (graphics card / other), the saved
    standard choices, and the run in ``out`` that can be continued."""
    try:
        general, models = read_settings(settings)
    except (OSError, ValueError, configparser.Error) as exc:
        print(f"PROBLEM in {settings}: {exc}")
        return 2
    if only:
        models = [m for m in models if m["id"] in only.split(",")]
    est = estimate(models, general, models_dir)
    print(f"Expected time on an RTX 3090 at full load: about {say_time(est['total'])} for {len(models)} models.")
    rows = []
    for m in models:
        where = find_model(models_dir, m["file"])
        note = "" if where else "   (file not found: this model is skipped)"
        print(f"  {m.get('title', m['id'])}: about {say_time(est[m['id']])}{note}")
        p = estimate_parts(m, general, models_dir)
        rows.append({"id": m["id"], "title": m.get("title", m["id"]), "gpu": round(p["gpu"], 1),
                     "cpu": round(p["cpu"], 1), "found": bool(where)})
    if json_path:
        info = {"models": rows, "standard": kit_run.load_standard(), "standard_file": kit_run.standard_path(),
                "factory": dict(kit_run.DEFAULT_STANDARD), "step": kit_run.STEP, "resume": None}
        res = kit_run.resume_info(out) if out else None
        if res:
            state = kit_run.RunState.load(out)
            by_id = {m["id"]: m for m in models}
            left = {"gpu": 0.0, "cpu": 0.0}
            for i in res["models"]:
                if i in by_id:
                    for k, v in left_parts(by_id[i], general, models_dir, state).items():
                        left[k] += v
            res.update(text=kit_run.resume_text(res), gpu=round(left["gpu"], 1), cpu=round(left["cpu"], 1),
                       choices=state.data.get("choices", {}))
            info["resume"] = res
        os.makedirs(os.path.dirname(os.path.abspath(json_path)), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(info, fh, indent=1, ensure_ascii=True)        # ASCII: PowerShell 5.1 reads it as ANSI
    return 0


def ask_resume(out: str, ask=input) -> bool:
    """The console route (no start window, task 0163): a run that stopped can be continued here too. Enter or Y =
    continue it; N = start afresh (the finished pictures in send/ are deleted). A closed console counts as Y: a
    night's work is never thrown away by accident."""
    res = kit_run.resume_info(out)
    if not res:
        return False
    try:
        a = ask(f"{kit_run.resume_text(res)}? Y = continue it, N = start again and delete it (Y/n): ")
    except (EOFError, OSError):
        return True
    return a.strip().lower() not in ("n", "no")


def main(argv: list[str]) -> int:
    args = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    small = "--small" in args
    cpu = "--cpu" in args
    resume = "--resume" in args
    only = start_at = json_path = choices = ""
    estimate_only = "--estimate-only" in args
    ask_for_resume = "--ask-resume" in args
    rest = []
    for a in args:
        if a in ("--estimate-only", "--resume", "--ask-resume"):
            continue
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        elif a.startswith("--start-at="):
            start_at = a.split("=", 1)[1].strip()
        elif a.startswith("--estimate-json="):
            json_path, estimate_only = a.split("=", 1)[1].strip(), True
        elif a.startswith("--choices="):
            choices = a.split("=", 1)[1].strip()
        elif a not in ("--small", "--cpu"):
            rest.append(a)
    if len(rest) < 2:
        print("usage: make_site_pictures.py <models folder> <output folder> [models.ini] [--small] [--cpu] "
              "[--only=a,b] [--start-at=HH:MM] [--estimate-only | --estimate-json=<file>] [--choices=<file>] "
              "[--resume] [--ask-resume]")
        return 2
    settings = rest[2] if len(rest) > 2 else os.path.join(HERE, "models.ini")
    if estimate_only:
        return show_estimate(os.path.abspath(rest[0]), os.path.abspath(settings), only,
                             os.path.abspath(json_path) if json_path else "", os.path.abspath(rest[1]))
    if ask_for_resume and not resume and not choices:
        resume = ask_resume(os.path.abspath(rest[1]))
    if choices:
        c = kit_run.load_choices(os.path.abspath(choices))
        start_at = start_at or c.get("start_at", "") or ""
        resume = resume or bool(c.get("resume"))
    return run(os.path.abspath(rest[0]), os.path.abspath(rest[1]), os.path.abspath(settings), small, only, cpu,
               start_at, os.path.abspath(choices) if choices else "", resume)


if __name__ == "__main__":
    code = main(sys.argv)
    if "--" not in sys.argv:             # Blender as a Python module (tests): exit with the code
        sys.exit(code)
    if code:                             # real Blender: --python-exit-code turns this into the .bat's code
        raise SystemExit(f"finished with problems (code {code}): see log.txt in the output folder")
