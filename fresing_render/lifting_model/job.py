"""Make a crane in the background (task 0204) – plain Python, no Blender.

``MakeJob`` writes the numbers to a file, starts ``run.py`` (the maker) as its own program with the given Python (in
the app: Blender's own, ``importer.runner.python_executable``) into a temporary folder, follows its progress file and
at the end puts the crane into the library folder through L2 (``core.lifting_library``): the STEP and the picture
first, then the equipment file with ``write_item`` (atomic) – so a half-made crane never shows in the library.
``cancel()`` stops the program and its children and deletes the temporary folder: nothing is left behind.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from ..core import lifting_library as LL
from . import params as P

RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py")
STAGES = {"start": "Starting", "shapes": "Making the shapes", "masses": "Working out the masses",
          "step": "Writing the model", "picture": "Drawing the picture", "done": "Putting it in the library"}


class MakeError(ValueError):
    pass


def target_folder(library: str, name: str) -> str:
    return os.path.join(library, LL.folder_name(name))


def name_problem(library: str, name: str, replace: bool = False) -> str:
    """'' or why the name cannot be used."""
    name = str(name or "").strip()
    if not name:
        return "Give the crane a name."
    try:
        stem = LL.folder_name(name)
    except LL.LibraryError as exc:
        return str(exc)
    if not library:
        return "No folder for lifting equipment you can save into: add one in Fresing Settings > Locations."
    if os.path.exists(os.path.join(library, stem)) and not replace:
        return f"'{name}' is already in your library: tick Replace or give another name."
    return ""


def kill_tree(pid: int) -> None:
    if not pid:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass


LEFTOVER: list = []         # temporary folders a cancel could not delete yet (Windows: a file still open)


def _sweep_leftovers() -> None:
    for d in list(LEFTOVER):
        shutil.rmtree(d, ignore_errors=True)
        if not os.path.exists(d):
            LEFTOVER.remove(d)


class MakeJob:
    """One crane made in the background. ``poll()`` -> True when done (then ``error`` or ``item_path``)."""

    def __init__(self, spec: dict, library: str, python: str | None = None, replace: bool = False):
        self.spec = dict(spec)
        self.library = library
        self.python = python or sys.executable
        self.replace = replace
        self.name = str(spec.get("name", "")).strip()
        self.proc = None
        self.tmp = ""
        self.error = ""
        self.item_path = ""
        self.share = 0.0
        self.stage = "start"
        self.started = 0.0
        self.seconds = 0.0
        self.done = False

    # -- start ------------------------------------------------------------------------------------------------
    def check(self) -> list:
        """Every reason it cannot start (plain words)."""
        out = []
        why = name_problem(self.library, self.name, self.replace)
        if why:
            out.append(why)
        out += [p.text for p in P.validate(self.spec["kind"], self.spec["values"])]
        return out

    def start(self) -> None:
        why = self.check()
        if why:
            raise MakeError(" ".join(why))
        _sweep_leftovers()
        self.tmp = tempfile.mkdtemp(prefix="fr_make_crane_")
        spec = dict(self.spec, values={k: (list(v) if isinstance(v, tuple) else v)
                                       for k, v in self.spec["values"].items()})
        with open(os.path.join(self.tmp, "numbers.json"), "w", encoding="utf-8") as fh:
            json.dump(spec, fh, indent=1)
        env = dict(os.environ)
        for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
            env.pop(var, None)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        out = os.path.join(self.tmp, "out")
        self._log = open(os.path.join(self.tmp, "log.txt"), "w", encoding="utf-8", errors="replace")
        kw = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if os.name == "nt" else \
            {"start_new_session": True}
        try:
            self.proc = subprocess.Popen([self.python, RUNNER, out, "--params",
                                          os.path.join(self.tmp, "numbers.json"),
                                          "--progress", os.path.join(self.tmp, "progress.json")],
                                         stdout=self._log, stderr=subprocess.STDOUT, env=env, **kw)
        except (OSError, ValueError) as exc:
            self._log.close()
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.done, self.error = True, f"The maker could not be started: {exc}"
            raise MakeError(self.error) from exc
        self.started = time.time()

    # -- follow -----------------------------------------------------------------------------------------------
    def text(self) -> str:
        return f"Making {self.name}: {STAGES.get(self.stage, self.stage)} ({100 * self.share:.0f}%)"

    def poll(self) -> bool:
        if self.done:
            return True
        if self.proc is None:
            return False
        try:
            with open(os.path.join(self.tmp, "progress.json"), encoding="utf-8") as fh:
                p = json.load(fh)
            self.stage, self.share = p.get("stage", self.stage), float(p.get("share", self.share))
        except (OSError, ValueError):
            pass
        if self.proc.poll() is None:
            return False
        self._log.close()
        try:
            if self.proc.returncode != 0:
                with open(os.path.join(self.tmp, "log.txt"), encoding="utf-8", errors="replace") as fh:
                    tail = fh.read().strip()
                not_made = [ln for ln in tail.splitlines() if ln.startswith("NOT MADE:")]
                self.error = (not_made[-1][len("NOT MADE:"):].strip() if not_made
                              else "The crane could not be made: " + tail[-400:])
            else:
                self.item_path = self.install()
        except (OSError, LL.LibraryError, ValueError) as exc:
            self.error = f"The crane could not be put in the library: {exc}"
        finally:
            self.seconds = time.time() - self.started
            shutil.rmtree(self.tmp, ignore_errors=True)
            self.done = True
        return True

    def wait(self, timeout: float = 300.0) -> bool:
        t0 = time.time()
        while not self.poll():
            if time.time() - t0 > timeout:
                self.cancel()
                self.error = "timed out"
                return True
            time.sleep(0.1)
        return True

    def install(self) -> str:
        """The made files into ``<library>/<stem>/``: model and picture first, the equipment file last (L2's
        ``write_item``). Returns the equipment file's path."""
        out = os.path.join(self.tmp, "out")
        stem = LL.folder_name(self.name)
        with open(os.path.join(out, f"{stem}.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        target = target_folder(self.library, self.name)
        LL._refuse_builtin(target, LL.BUILTIN_DIR)
        if os.path.exists(target) and not self.replace:
            raise MakeError(name_problem(self.library, self.name, False))
        os.makedirs(target, exist_ok=True)
        for ext in (".step", ".png"):
            src = os.path.join(out, stem + ext)
            if os.path.isfile(src):
                tmp = os.path.join(target, f".tmp-{stem}{ext}")
                try:
                    shutil.copyfile(src, tmp)
                    os.replace(tmp, os.path.join(target, stem + ext))
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)
        return LL.write_item(data, self.library).path

    # -- cancel -----------------------------------------------------------------------------------------------
    def cancel(self) -> None:
        if self.proc is not None and self.proc.poll() is None:
            kill_tree(self.proc.pid)
            try:
                self.proc.kill()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        try:
            self._log.close()
        except (AttributeError, OSError):
            pass
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)
            if os.path.exists(self.tmp):
                LEFTOVER.append(self.tmp)
        self.error = self.error or "cancelled"
        self.done = True
