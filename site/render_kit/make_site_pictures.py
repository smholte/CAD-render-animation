"""Fresing Render – pictures and a video for the web page (task 0047).

Run by "Make site pictures.bat" with the Blender of the installed Fresing Render, in the background:

    blender.exe --background --python make_site_pictures.py -- <models folder> <output folder> [settings file]

For every model in the settings file (models.ini next to this script) it does what a user would do in the app:
import the STEP file with the app's own importer and sorting rules, pick a light look and surroundings, add the
camera views, render the stills on the graphics card (Cycles) and, for the model marked ``video = turntable``,
render a turntable video through the app's own animation code. Everything goes into the output folder:

    full/<model>_<view>.png       the full-size pictures (keep them)
    full/<model>.blend            the project, to open in Fresing Render and change by hand
    send/<model>_<view>.jpg       web copies (send these back)
    send/<model>_turntable.mp4    the video (web size)
    send/site_pictures.json       what each picture shows and the model's credit line
    Fresing site pictures.zip     the send/ folder in one file, to attach in the chat
    contact_sheet.html            all pictures on one page (double-click to look at them)
    log.txt                       what was done, with times

It also runs on Linux with Blender as a Python module (the tests in tests/test_site.py) or a Linux Blender,
with ``--small`` (480 px wide, Draft, processor): ``python make_site_pictures.py <models> <out> --small``.
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
SEND_LIMIT_MB = 29.0            # the chat takes files up to 30 MB

DEFAULTS = {
    "width": "2400", "height": "1350", "quality": "final", "import_quality": "fine",
    "video_seconds": "10", "video_quality": "preview", "video_height": "MIDDLE",
}
VIEW_NAMES = ("ISOMETRIC", "FRONT", "SIDE", "TOP", "LOW", "HIGH", "ISO", "ISO_LEFT")
LOOKS = ("PRODUCT", "WHITE", "DARK", "SUN", "OVERCAST")
BACKGROUNDS = ("COLOR", "SKY", "SEA", "DECK", "QUAY", "FACTORY", "CNC", "ASSEMBLY", "WAREHOUSE")
QUALITIES = ("draft", "preview", "final", "best")


class Log:
    def __init__(self, path: str):
        self.path = path
        self.t0 = time.time()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"Fresing site pictures – started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

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
    differs. '' when there is none."""
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


def keep_awake() -> None:
    """Windows: no sleep while the pictures render (as the render queue does; released when Blender ends)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass


def read_settings(path: str) -> tuple[dict, list[dict]]:
    """The [settings] section and one dict per model section, checked. Raises ValueError with a plain
    reason when something is wrong (shown in the window and the log)."""
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(_read_text(path))
    general = dict(DEFAULTS)
    if cp.has_section("settings"):
        general.update({k: v.strip() for k, v in cp.items("settings")})
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
        bad = [v for v in m["views"] if v not in VIEW_NAMES]
        if bad:
            raise ValueError(f"[{sec}] views: {', '.join(bad)} unknown; use {', '.join(VIEW_NAMES)}")
        m["look"] = m.get("look", "PRODUCT").upper()
        if m["look"] not in LOOKS:
            raise ValueError(f"[{sec}] look = {m['look']}: use one of {', '.join(LOOKS)}")
        m["surroundings"] = m.get("surroundings", "COLOR").upper()
        if m["surroundings"] not in BACKGROUNDS:
            raise ValueError(f"[{sec}] surroundings = {m['surroundings']}: use one of {', '.join(BACKGROUNDS)}")
        m["video"] = m.get("video", "none").lower()
        if m["video"] not in ("none", "turntable"):
            raise ValueError(f"[{sec}] video = {m['video']}: use none or turntable")
        m["up_axis"] = m.get("up_axis", "Z").upper()
        if m["up_axis"] not in ("Z", "Y"):
            raise ValueError(f"[{sec}] up_axis = {m['up_axis']}: use Z or Y")
        for key in ("lens", "rotate_light"):
            if key in m:
                try:
                    float(m[key])
                except ValueError:
                    raise ValueError(f"[{sec}] {key} = {m[key]}: must be a number") from None
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


def web_mp4(pkg, frames_dir: str, out_path: str, width: int, height: int, fps: int) -> str:
    """The rendered frames as an H.264 MP4 small enough for a web page (the app's own encoder, one quality
    step lower than its videos)."""
    import bpy
    video = importlib.import_module(pkg.__name__ + ".blender.video")
    files = sorted(f for f in os.listdir(frames_dir) if f.startswith("frame_") and f.endswith(".png")
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


def turntable_video(pkg, scene, m: dict, general: dict, full: str, send: str, small: bool, log) -> str:
    import bpy
    turntable = importlib.import_module(pkg.__name__ + ".blender.turntable")
    queue = importlib.import_module(pkg.__name__ + ".blender.queue")
    s = scene.fresing
    s.turntable_seconds = 2.0 if small else float(m.get("video_seconds", general["video_seconds"]))
    s.turntable_height = m.get("video_height", general["video_height"]).upper()
    s.turntable_quality = "draft" if small else general["video_quality"]
    a = turntable.make(scene)["animation"]
    a.out_format = "presentation"
    a.out_resolution = "preview" if small else "hd"
    a.video = "PNG"                              # the frames; the web MP4 is made below
    if small:
        a.fps = "24"
    job = {"id": "site", "kind": "ANIMATION", "animation": a.name, "quality": s.turntable_quality,
           "out_dir": full, "label": "turntable", "watermark": False}
    last = [0.0]

    def progress(pct, msg):
        if time.time() - last[0] > 20 or pct >= 95:
            last[0] = time.time()
            log(f"  video {pct:.0f}%: {msg}")

    stem = queue.render._safe(os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "animation")
    for old in os.listdir(full):                 # frames of an earlier run would be kept (the queue resumes)
        if old.startswith(f"{stem}_{queue.render._safe(a.name)}_") and old.endswith("_site"):
            shutil.rmtree(os.path.join(full, old), ignore_errors=True)
    folder = queue.render_animation(scene, job, progress, lambda: False)
    size = scene.render.resolution_x, scene.render.resolution_y
    out = os.path.join(send, f"{m['id']}_turntable.mp4")
    web_mp4(pkg, folder, out, size[0], size[1], int(a.fps))
    return out


def do_model(pkg, m: dict, general: dict, models_dir: str, out: str, small: bool, log, cpu: bool = False) -> list[dict]:
    import bpy
    render = importlib.import_module(pkg.__name__ + ".blender.render")
    cameras = importlib.import_module(pkg.__name__ + ".blender.cameras")
    full, send = os.path.join(out, "full"), os.path.join(out, "send")
    path = find_model(models_dir, m["file"])
    if not path:
        raise RuntimeError(f"file not found: {m['file']} in {models_dir} – put it in the models folder or fix "
                           f"'file =' in models.ini")
    t0 = time.time()
    scene = fresh_import(pkg, path, "draft" if small else m.get("import_quality", general["import_quality"]),
                         m["up_axis"], full)
    parts = sum(1 for _ in importlib.import_module(pkg.__name__ + ".blender.build").iter_parts(scene))
    log(f"  imported {parts} parts in {time.time() - t0:.0f} s")
    width = 480 if small else int(float(general["width"]))
    height = round(width * float(general["height"]) / float(general["width"]))
    set_scene(pkg, scene, m, (width, height))
    s = scene.fresing
    s.use_gpu = not (small or cpu)
    quality = "draft" if small else m.get("quality", general["quality"])
    made = []
    captions = [c.strip() for c in m.get("captions", "").split("|")]
    for i, view in enumerate(m["views"]):
        cam = cameras.add_camera(scene, view, lens=float(m.get("lens", 50)), name=f"Site {view}",
                                 margin=cameras.SPACE.get(m.get("space", "NORMAL").upper(), 1.06))
        scene.camera = cam
        png = os.path.join(full, f"{m['id']}_{view.lower()}.png")
        t1 = time.time()
        info = render.render_still(scene, s, quality, filepath=png)
        jpg = os.path.join(send, f"{m['id']}_{view.lower()}.jpg")
        jpg_copy(png, jpg, width)
        caption = captions[i] if i < len(captions) and captions[i] else m.get("title", m["id"])
        made.append({"file": os.path.basename(jpg), "model": m["id"], "caption": caption, "kind": "picture"})
        log(f"  {view}: {info['size'][0]}×{info['size'][1]} on {info['device']} in {time.time() - t1:.0f} s")
    if m["video"] == "turntable":
        t1 = time.time()
        mp4 = turntable_video(pkg, scene, m, general, full, send, small, log)
        made.append({"file": os.path.basename(mp4), "model": m["id"], "kind": "video",
                     "caption": m.get("video_caption", f"{m.get('title', m['id'])}: turntable")})
        log(f"  video: {os.path.getsize(mp4) / 1e6:.1f} MB in {time.time() - t1:.0f} s")
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(full, f"{m['id']}.blend"), copy=True)
    return made


def contact_sheet(out: str, items: list[dict], models: list[dict], errors: list[str]) -> str:
    rows = []
    for it in items:
        src = "send/" + it["file"]
        tag = (f'<video src="{src}" controls muted loop></video>' if it["kind"] == "video"
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


def make_zip(out: str) -> str:
    send = os.path.join(out, "send")
    path = os.path.join(out, "Fresing site pictures.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:     # JPG and MP4 do not shrink further
        for f in sorted(os.listdir(send)):
            z.write(os.path.join(send, f), f)
    return path


def run(models_dir: str, out: str, settings: str, small: bool = False, only: str = "", cpu: bool = False) -> int:
    log = Log(os.path.join(out, "log.txt"))
    keep_awake()
    for old in ("Fresing site pictures.zip", "contact_sheet.html"):     # never leave last run's results
        try:
            os.remove(os.path.join(out, old))
        except OSError:
            pass
    try:
        return _run(models_dir, out, settings, small, only, cpu, log)
    except Exception:
        log("PROBLEM (the run stopped):\n" + traceback.format_exc())
        return 3


def _run(models_dir, out, settings, small, only, cpu, log) -> int:
    try:
        general, models = read_settings(settings)
    except (OSError, ValueError, configparser.Error) as exc:
        log(f"PROBLEM in {settings}: {exc}")
        return 2
    if only:
        models = [m for m in models if m["id"] in only.split(",")]
    for sub in ("full", "send"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    for old in os.listdir(os.path.join(out, "send")):
        os.remove(os.path.join(out, "send", old))
    pkg = load_app()
    render = importlib.import_module(pkg.__name__ + ".blender.render")
    if small:                                    # a quick test on a machine without a graphics card
        render.QUALITY["draft"] = (8,) + tuple(render.QUALITY["draft"][1:])
    device = "processor (small test)" if small else "processor" if cpu else render.setup_gpu()
    log(f"Fresing Render {getattr(pkg, '__version__', '?')}, renders on: {device}")
    if not (small or cpu) and not device.startswith("GPU"):
        log("NOTE: no graphics card found – this will be very slow. Close the window to stop.")
    items, errors = [], []
    for n, m in enumerate(models, 1):
        log(f"Model {n} of {len(models)}: {m['id']} ({m['file']})")
        try:
            items += do_model(pkg, m, general, models_dir, out, small, log, cpu)
        except Exception as exc:                  # one bad model must not stop the others
            traceback.print_exc()
            errors.append(f"{m['id']}: {exc}")
            log(f"  PROBLEM: {exc}")
    used = {it["model"] for it in items}
    info = {"made": time.strftime("%Y-%m-%d %H:%M"), "app": getattr(pkg, "__version__", "?"), "device": device,
            "items": items,
            "models": {m["id"]: {k: m.get(k, "") for k in ("title", "credit", "link", "licence")}
                       for m in models if m["id"] in used}}
    with open(os.path.join(out, "send", "site_pictures.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)
    sheet = contact_sheet(out, items, [m for m in models if m["id"] in used], errors)
    z = make_zip(out)
    mb = os.path.getsize(z) / 1e6
    log(f"Contact sheet: {sheet}")
    log(f"To send back: {z} ({mb:.1f} MB)")
    if mb > SEND_LIMIT_MB:
        log(f"NOTE: the zip is over {SEND_LIMIT_MB:.0f} MB: send the files in send\\ in two messages instead")
    log(f"Done: {sum(1 for i in items if i['kind'] == 'picture')} pictures, "
        f"{sum(1 for i in items if i['kind'] == 'video')} video, {len(errors)} problems")
    return 1 if errors else 0


def main(argv: list[str]) -> int:
    args = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    small = "--small" in args
    cpu = "--cpu" in args
    only = ""
    rest = []
    for a in args:
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        elif a not in ("--small", "--cpu"):
            rest.append(a)
    if len(rest) < 2:
        print("usage: make_site_pictures.py <models folder> <output folder> [models.ini] [--small] [--cpu] [--only=a,b]")
        return 2
    settings = rest[2] if len(rest) > 2 else os.path.join(HERE, "models.ini")
    return run(os.path.abspath(rest[0]), os.path.abspath(rest[1]), os.path.abspath(settings), small, only, cpu)


if __name__ == "__main__":
    code = main(sys.argv)
    if "--" not in sys.argv:             # Blender as a Python module (tests): exit with the code
        sys.exit(code)
    if code:                             # real Blender: --python-exit-code turns this into the .bat's code
        raise SystemExit(f"finished with problems (code {code}): see log.txt in the output folder")
