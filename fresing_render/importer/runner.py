"""Run the STEP reader in a separate process and follow its progress.

No bpy here, so it can be tested on its own.
"""

from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading

from . import step_reader

READER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step_reader.py")


def cache_key(step_path: str, quality: str) -> str:
    st = os.stat(step_path)
    raw = f"{os.path.abspath(step_path)}|{st.st_size}|{int(st.st_mtime)}|{quality}|v{step_reader.CACHE_VERSION}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def cache_dir_for(step_path: str, quality: str, cache_root: str) -> str:
    stem = os.path.splitext(os.path.basename(step_path))[0][:40]
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in stem)
    return os.path.join(cache_root, f"{safe}_{cache_key(step_path, quality)}")


def cache_is_valid(cache_dir: str) -> bool:
    tree = os.path.join(cache_dir, "tree.json")
    if not (os.path.isfile(tree) and os.path.isfile(os.path.join(cache_dir, "meshes.npz"))):
        return False
    try:
        with open(tree, encoding="utf-8") as fh:
            head = json.load(fh)
        return head.get("version") == step_reader.CACHE_VERSION
    except (OSError, ValueError):
        return False


def python_executable() -> str:
    """The Python to run the reader with. Inside Blender this is Blender's own Python."""
    exe = sys.executable
    base = os.path.basename(exe).lower()
    if base.startswith("blender"):
        # Very old Blender versions: sys.executable is blender itself; look for bundled python
        guess = os.path.join(os.path.dirname(exe), "python", "bin", "python.exe" if os.name == "nt" else "python3")
        if os.path.isfile(guess):
            return guess
    return exe


class ImportJob:
    """One STEP -> cache conversion in a child process."""

    def __init__(self, step_path: str, quality: str, cache_root: str):
        self.step_path = step_path
        self.quality = quality
        self.cache_dir = cache_dir_for(step_path, quality, cache_root)
        self.tmp_dir = self.cache_dir + ".partial"
        self.proc: subprocess.Popen | None = None
        self.events: "queue.Queue[dict]" = queue.Queue()
        self.stderr_lines: list[str] = []
        self.error: str | None = None
        self.done = False
        self.pct = 0.0
        self.message = "Waiting"

    @property
    def cached(self) -> bool:
        return cache_is_valid(self.cache_dir)

    def start(self) -> None:
        if os.path.isdir(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
        os.makedirs(os.path.dirname(self.cache_dir), exist_ok=True)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
        env["PYTHONUNBUFFERED"] = "1"
        flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
        self.proc = subprocess.Popen(
            [python_executable(), READER, self.step_path, self.tmp_dir, "--quality", self.quality],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
            env=env, creationflags=flags,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()

    def _read_stdout(self) -> None:
        assert self.proc and self.proc.stdout
        for line in self.proc.stdout:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                self.events.put(json.loads(line))
            except ValueError:
                continue

    def _read_stderr(self) -> None:
        assert self.proc and self.proc.stderr
        for line in self.proc.stderr:
            self.stderr_lines.append(line.rstrip())
            del self.stderr_lines[:-40]

    def poll(self) -> bool:
        """Process new events. Returns True when the job has finished (ok or error)."""
        while True:
            try:
                ev = self.events.get_nowait()
            except queue.Empty:
                break
            self.pct = ev.get("pct", self.pct)
            self.message = ev.get("msg", self.message)
            if ev.get("stage") == "error":
                self.error = ev.get("msg") or "Import failed"
        if self.proc is None or self.proc.poll() is None:
            return False
        # process ended: drain anything left
        while not self.events.empty():
            ev = self.events.get_nowait()
            if ev.get("stage") == "error":
                self.error = ev.get("msg")
        if self.proc.returncode != 0 and not self.error:
            tail = "\n".join(self.stderr_lines[-5:])
            self.error = f"Reader stopped (code {self.proc.returncode}). {tail}".strip()
        if not self.error:
            if os.path.isdir(self.cache_dir):
                shutil.rmtree(self.cache_dir, ignore_errors=True)
            os.replace(self.tmp_dir, self.cache_dir)
        self.done = True
        return True

    def cancel(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
        self.error = "Cancelled"
        self.done = True
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
