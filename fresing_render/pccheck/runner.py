"""Runs the PC check inside a background Blender and writes the report.

Started by ``launcher.py`` (Start-menu shortcuts, Help > Fresing Render PC check…). The report is
written after every line (a crash still leaves one), and opened in the web browser at the end.

Where things go:
  report      <Desktop>\\Fresing Render PC check.html (the Desktop the shortcut passes; OneDrive-safe)
  history     <Blender settings>\\config\\fresing_pccheck\\history.json + pictures\\ (last runs' numbers
              and small pictures, to compare with; survives updates)
  work files  a temporary folder, removed at the end

Environment: FRESING_SELFTEST_NO_GPU=1 (test servers without a graphics card: graphics-card lines are
"skipped: no graphics card"), FRESING_PCCHECK_NO_OPEN=1 (do not open the report), FRESING_PCCHECK_DIR
(another history folder), FRESING_PCCHECK_ONLY (comma-separated line ids: run only those; tests).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

from . import core
from .core import FAILED, OK, SKIPPED, Skipped

REPORT_NAME = "Fresing Render PC check.html"
TOUR_REPORT_NAME = "Fresing Render test tour.html"
NO_GPU_ENV = "FRESING_SELFTEST_NO_GPU"
NO_OPEN_ENV = "FRESING_PCCHECK_NO_OPEN"
DIR_ENV = "FRESING_PCCHECK_DIR"
ONLY_ENV = "FRESING_PCCHECK_ONLY"
NO_GPU_TEXT = "no graphics card"
CANCEL_FILE = "cancel.flag"


def no_gpu_expected() -> bool:
    return os.environ.get(NO_GPU_ENV, "") == "1"


def history_dir() -> str:
    if os.environ.get(DIR_ENV):
        return os.environ[DIR_ENV]
    import bpy
    return bpy.utils.user_resource("CONFIG", path="fresing_pccheck")


def cancel_path() -> str:
    return os.path.join(history_dir(), CANCEL_FILE)


def cancel_requested() -> bool:
    return os.path.isfile(cancel_path())


def check_cancel() -> None:
    """Called between steps of long lines: stops the check when the owner asked for it."""
    if cancel_requested():
        raise core.Cancelled("cancelled")


def desktop_dir(given: str = "") -> str:
    """The Desktop: the one the shortcut passes, else Windows' own (OneDrive may have moved it)."""
    if given and os.path.isdir(given):
        return given
    if sys.platform == "win32":
        path = _known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")      # FOLDERID_Desktop
        if path:
            return path
    for cand in (os.path.join(os.path.expanduser("~"), "Desktop"),
                 os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop"), os.path.expanduser("~")):
        if os.path.isdir(cand):
            return cand
    return os.getcwd()


def _known_folder(guid_text: str) -> str:
    try:
        import ctypes
        import uuid
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                        ("Data4", ctypes.c_ubyte * 8)]

        u = uuid.UUID(guid_text)
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
    except Exception:  # noqa: BLE001 - fall back to the usual places
        pass
    return ""


# ---------------------------------------------------------------------------
# this PC
# ---------------------------------------------------------------------------

def _run_quiet(cmd: list, timeout: float = 10) -> str:
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, creationflags=flags)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def cpu_name() -> str:
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return " ".join(str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).split())
        except OSError:
            pass
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            for ln in fh:
                if ln.lower().startswith("model name"):
                    return " ".join(ln.split(":", 1)[1].split())
    except OSError:
        pass
    return platform.processor() or "unknown processor"


def ram_gb() -> int | str:
    if sys.platform == "win32":
        try:
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return round(m.ullTotalPhys / 2 ** 30)
        except Exception:  # noqa: BLE001
            pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("MemTotal:"):
                    return round(int(ln.split()[1]) / 2 ** 20)
    except OSError:
        pass
    return "?"


def gpu_driver() -> str:
    exe = shutil.which("nvidia-smi")
    if not exe and sys.platform == "win32":
        cand = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe")
        exe = cand if os.path.isfile(cand) else ""
    if exe:
        out = _run_quiet([exe, "--query-gpu=driver_version", "--format=csv,noheader"])
        if out:
            return out.splitlines()[0].strip()
    return "unknown"


def pc_info(gpu: str) -> dict:
    return {"cpu": cpu_name(), "cores": os.cpu_count() or "?", "ram_gb": ram_gb(), "gpu": gpu,
            "driver": gpu_driver() if gpu.startswith("GPU") else "-",
            "os": f"{platform.system()} {platform.release()} ({platform.version()})"}


# ---------------------------------------------------------------------------
# pictures (Blender reads and writes the PNGs: Blender's Python has no Pillow)
# ---------------------------------------------------------------------------

def read_pixels(path: str):
    """Screen values 0..1, rows top to bottom, RGB."""
    import bpy
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        if w == 0 or h == 0:
            raise RuntimeError("the picture file is empty or damaged")
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        linear = img.is_float or img.depth > 32       # 16-bit PNGs load as linear values (CLAUDE.md section 8)
    finally:
        bpy.data.images.remove(img)
    px = px.reshape(h, w, 4)[::-1, :, :3]
    if linear:
        px = np.where(px <= 0.0031308, px * 12.92, 1.055 * np.power(np.clip(px, 0, None), 1 / 2.4) - 0.055)
    return np.clip(px, 0.0, 1.0)


def write_png(path: str, px) -> bytes:
    import bpy
    import numpy as np
    h, w = px.shape[:2]
    img = bpy.data.images.new("fr_pccheck_thumb", w, h, alpha=False)
    try:
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :3] = px[::-1]
        img.pixels.foreach_set(rgba.ravel())
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)
    with open(path, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

class Context:
    """What a line gets: helpers for fresh projects, numbers, pictures and the graphics card."""

    def __init__(self, work: str, hist: str, run: core.Run, model: str = "", gpu: str = ""):
        self.work = work
        self.hist = hist
        self.run = run
        self.model = model
        self.gpu = gpu
        self.has_gpu = gpu.startswith("GPU")
        self.result: core.Result | None = None
        self.secrets: set = set()
        self.loaded = ("", "")                  # (line id, model path) of the project open now
        self.models: dict = {}                  # line id -> (model, quality) it imported

    # --- projects
    def fresh(self, step: str, quality: str = "draft", read_again: bool = False):
        """A new, empty project with ``step`` imported (built-in sorting rules). ``read_again``: read the
        STEP file itself, not the import cache of an earlier import (for the import times); the import
        makes the same cache again."""
        import bpy

        from ..blender import ops_import
        from ..blender import prefs as fr_prefs
        from ..importer import runner as import_runner
        if read_again:
            shutil.rmtree(import_runner.cache_dir_for(step, quality, ops_import.cache_root()), ignore_errors=True)
        bpy.ops.wm.read_homefile(use_empty=True)
        p = fr_prefs.get()
        saved = p.default_template if p else ""
        if p:
            p.default_template = ""
        try:
            scene = bpy.context.scene
            scene.fresing.out_folder = os.path.join(self.work, "renders")
            res = bpy.ops.fresing.import_step(filepath=step, quality=quality)
            if res != {"FINISHED"}:
                raise RuntimeError(f"the import returned {res}: {scene.fresing.last_message}")
        finally:
            if p:
                p.default_template = saved
        line_id = self.result.id if self.result else ""
        self.loaded = (line_id, step)
        self.models[line_id] = (step, quality)
        return bpy.context.scene

    def scene_of(self, line_id: str):
        """The project an earlier line imported: still open, or imported again."""
        import bpy
        if self.loaded[0] == line_id:
            return bpy.context.scene
        step, quality = self.models.get(line_id, ("", ""))
        if not step:
            raise RuntimeError(f"no project of '{line_id}'")
        current = self.result
        scene = self.fresh(step, quality)
        self.loaded = (line_id, step)
        self.result = current
        return scene

    def ok(self, line_id: str) -> bool:
        return any(r.id == line_id and r.status == OK for r in self.run.results)

    # --- numbers and pictures
    def metric(self, name: str, value, unit: str = "") -> None:
        if isinstance(value, float):
            value = round(value, 3)
        self.result.metrics[name] = (value, unit)

    def add_secrets(self, objs) -> None:
        """Names that must never get into the text block (the owner's part and assembly names)."""
        from ..blender import build
        for o in objs:
            self.secrets.add(o.get(build.PROP_NAME, ""))
            parent = build.parent_assembly(o)
            while parent is not None:
                self.secrets.add(parent.get(build.PROP_NAME, ""))
                parent = build.parent_assembly(parent)

    def picture(self, path: str, key: str, title: str, model_check: bool = True, gpu_optional: bool = False,
                width: int = 0, settings: str = ""):
        """``width``: a larger picture in the report (Heavy); ``settings``: shown under it (size, quality)."""
        if not path or not os.path.isfile(path):
            raise RuntimeError(f"the picture '{title}' was not written")
        px = read_pixels(path)
        self.picture_pixels(px, key, title, model_check, gpu_optional, width, settings)

    def picture_pixels(self, px, key: str, title: str, model_check: bool = True, gpu_optional: bool = False,
                       width: int = 0, settings: str = ""):
        thumb = core.thumbnail(px, width or core.THUMB_WIDTH)
        pic = core.Picture(key, title, problems=core.picture_problems(px, model_check), width=width,
                           settings=settings)
        old_path = os.path.join(self.hist, "pictures", self.run.key, key + ".png")
        old = read_pixels(old_path) if os.path.isfile(old_path) else None
        pic.difference = core.picture_difference(thumb, old)
        pic.flagged = pic.difference is not None and pic.difference > core.PICTURE_DIFF
        pic.thumb_png = write_png(old_path, thumb)
        if pic.problems and gpu_optional and not self.has_gpu and no_gpu_expected():
            pic.problems = []
            pic.title += " (no graphics card here: not judged)"
        self.result.pictures.append(pic)

    # --- graphics card
    def need_gpu(self) -> None:
        if self.has_gpu:
            return
        if no_gpu_expected():
            raise Skipped(f"skipped: {NO_GPU_TEXT}")
        raise RuntimeError("no supported graphics card found: renders use the processor (slow). Update the "
                           "NVIDIA driver (535 or newer), then run the PC check again")

    def gpu_optional(self, exc: BaseException) -> None:
        """EEVEE needs a graphics card; on a test server without one a failure is "skipped"."""
        if not self.has_gpu and no_gpu_expected():
            raise Skipped(f"skipped: {NO_GPU_TEXT} (EEVEE could not start here)") from exc


def is_own(ln) -> bool:
    """A line on the owner's own model ("own", or "ownheavy" in Heavy): numbers only in the text block."""
    return any(m.startswith("own") for m in ln.modes)


def _fingerprint(path: str) -> str:
    """A short code for "the same model file" (its size and content), never its name."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()[:10]
    except OSError:
        return "unknown"


def _console(text: str) -> None:
    print(text, flush=True)


def run(mode: str = "quick", desktop: str = "", model: str = "", open_report: bool | None = None,
        lines: list | None = None) -> core.Run:
    import bpy

    from .. import __version__
    from ..blender import render
    from . import checks
    mode = mode if mode in core.MODES else "quick"
    if mode == "tour":
        model = ""                                     # the tour has its own models
    hist = history_dir()
    os.makedirs(hist, exist_ok=True)
    report_path = os.path.join(desktop_dir(desktop), TOUR_REPORT_NAME if mode == "tour" else REPORT_NAME)
    history_path = os.path.join(hist, "history.json")
    history = core.load_history(history_path)
    gpu = render.setup_gpu()
    run = core.Run(__version__, mode, core.now(), blender=bpy.app.version_string, pc=pc_info(gpu),
                   own_model=bool(model), model_tag=_fingerprint(model) if model else "")
    work = tempfile.mkdtemp(prefix="fresing_pccheck_")
    ctx = Context(work, hist, run, model=model, gpu=gpu)
    if model:
        stem = os.path.splitext(os.path.basename(model))[0]
        ctx.secrets.update({os.path.basename(model), stem, os.path.dirname(model)})
    ctx.secrets.update({platform.node(), os.path.basename(os.path.expanduser("~"))})
    try:
        os.remove(cancel_path())            # an old request must not stop this run
    except OSError:
        pass
    from . import heavy
    run.scaled = mode == "heavy" and heavy.small()
    if lines is None and mode == "tour":               # the automatic test tour (task 0059)
        from . import tour
        tour.attach()
        lines = tour.lines()
    todo = core.lines_for(lines if lines is not None else checks.LINES, mode, bool(model))
    only = [x.strip() for x in os.environ.get(ONLY_ENV, "").split(",") if x.strip()]
    if only:
        todo = [ln for ln in todo if ln.id in only]
    if model:
        todo = [ln for ln in todo if not is_own(ln)] + [ln for ln in todo if is_own(ln)]
    _console(f"Fresing Render {__version__} PC check ({core.MODE_TITLES[mode]}{' + own model' if model else ''}), "
             f"{len(todo)} steps. The report opens by itself at the end: {report_path}")
    t_run = time.time()
    running = os.path.join(hist, "running.json")
    try:
        core.write_text(running, json.dumps({"pid": os.getpid(), "mode": mode, "date": run.date}))
    except OSError:
        pass

    lock = threading.RLock()

    def write_report():
        with lock:
            run.seconds = time.time() - t_run
            core.compare(run, history)
            try:
                block = core.text_block(run, ctx.secrets)
                core.write_text(report_path, core.html_report(run, block))
            except Exception as exc:  # noqa: BLE001 - the check goes on; the console shows every line anyway
                _console(f"Could not write the report: {exc}")
                block = ""
            return block

    stop_beat = threading.Event()

    def heartbeat():
        """The report shows the running line's time: write it again every few seconds (Heavy lines last minutes)."""
        while not stop_beat.wait(8.0):
            if run.finished:
                break
            write_report()

    if mode == "heavy":
        threading.Thread(target=heartbeat, daemon=True).start()

    for i, ln in enumerate(todo):
        res = core.Result(ln.id, ln.title, ln.since, own=is_own(ln), what=ln.what, expected=ln.expected,
                          started=time.time(), shows=ln.shows, not_shown=ln.not_shown)
        run.results.append(res)
        run.planned = [x.title for x in todo[i + 1:]]
        ctx.result = res
        write_report()
        _console(f"[{i + 1}/{len(todo)}] {ln.title} …")
        t0 = time.time()
        missing = [r for r in ln.requires if not ctx.ok(r)]
        cancelled = False
        try:
            check_cancel()
            if missing:
                raise Skipped("skipped: needs " + ", ".join(
                    next((x.title for x in todo if x.id == r), r) for r in missing) + " to work first")
            note = ln.fn(ctx)
            bad = [f"{p.title}: {'; '.join(p.problems)}" for p in res.pictures if p.problems]
            if bad:
                raise RuntimeError("picture check: " + " | ".join(bad))
            res.status, res.note = OK, (note or "") if not res.own else ""
        except (core.Cancelled, KeyboardInterrupt):
            res.status, res.reason, cancelled = SKIPPED, "cancelled by you", True
        except Skipped as exc:
            res.status, res.reason = SKIPPED, str(exc).removeprefix("skipped: ")
        except Exception as exc:  # noqa: BLE001 - a line that fails is reported, the check goes on
            res.status, res.reason, res.error_type = FAILED, str(exc) or type(exc).__name__, type(exc).__name__
            res.trace = traceback.format_exc()
        res.seconds = time.time() - t0
        mark = {OK: "[ OK ]", FAILED: "[FAIL]", SKIPPED: "[SKIP]"}[res.status]
        extra = f": {res.reason}" if res.reason else (f": {res.note}" if res.note else "")
        _console(f"{mark} {ln.title} ({res.seconds:.1f} s){extra}")
        if res.status == FAILED:
            _console(f"FAIL {ln.id}: {res.reason}")
        if cancelled:
            run.cancelled = True
            _console("Cancelled: the lines done so far are in the report.")
            break
    stop_beat.set()
    run.finished, run.planned = True, []
    block = write_report()
    try:
        core.save_history(history_path, core.add_to_history(history, core.run_record(run)))
        core.write_text(os.path.join(hist, "last_run.txt"), block + "\n")
    except OSError as exc:
        _console(f"Could not save the numbers of this run: {exc}")
    shutil.rmtree(work, ignore_errors=True)
    for leftover in (running, cancel_path()):
        try:
            os.remove(leftover)
        except OSError:
            pass
    c = run.counts()
    _console(block)
    _console(f"RESULT {c[OK] + c[SKIPPED]}/{len(run.results)} "
             f"({c[OK]} OK, {c[FAILED]} failed, {c[SKIPPED]} skipped) in {run.seconds:.0f} s")
    _console(f"Report: {report_path}")
    if open_report is None:
        open_report = os.environ.get(NO_OPEN_ENV, "") != "1"
    if open_report:
        try:
            from ..blender import files
            files.open_path(report_path)
        except Exception as exc:  # noqa: BLE001
            _console(f"Open the report yourself: {report_path} ({exc})")
    return run


def run_from_argv(argv: list | None = None) -> core.Run:
    """Entry point of the launcher: arguments after Blender's "--"."""
    argv = sys.argv if argv is None else argv
    extra = argv[argv.index("--") + 1:] if "--" in argv else []
    if extra and extra[0].strip().lower() == "tourbuild":       # Help > Make test tour project (task 0059)
        from ..blender import tour
        code = tour.build_main(extra[1] if len(extra) > 1 else "")
        if code:
            raise SystemExit(code)
        return None
    args = core.parse_args(extra)
    return run(args["mode"], args["desktop"], args["model"])
