"""Installs a downloaded update while Fresing Render is closed, then starts the app again.

The app (``blender/updates.py``) downloads and checks the new extension zip, copies this file
to a folder of its own (the extension folder itself is replaced during the update), writes a
plan next to it and starts it with Blender's own Python:

    python -I update_helper.py <plan.json>

Plan (JSON): blender (blender program), wait_pid (the app's process), zip, expected_version,
old_version, repo (extension repository the app is installed in, e.g. "user_default"),
ext_dir (installed extension folder), template_dir (installed app template, "" = none),
restart (command line to start the app again, [] = none), status_file, log_file.

Steps: wait until the app has closed -> ``blender --command extension install-file`` (Blender's
own installer: unpacks next to the old version, then swaps) -> check the installed version ->
copy the app template that ships inside the new extension -> write the status file the app shows
at its next start -> start the app again (also when something failed: the old version still works).

Plain Python, no Blender modules: it runs while Blender is closed.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time

TEMPLATE_FILES_DIR = "app_template_files"     # inside the extension: the app template of that version
WAIT_SECONDS = 300                            # for the app to close
INSTALL_SECONDS = 900
RETRY_WAITS = (3.0, 5.0, 8.0)                 # seconds before each new try of Blender's installer
BUSY_FILE = "installing.json"                 # next to the status file while the helper works

# Windows process flags
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000


def _log(plan: dict, text: str) -> None:
    """The log file is what counts (UTF-8). The console may not print every character (a hidden
    console's code page): printing never stops the update."""
    line = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  {text}"
    try:
        print(line, flush=True)
    except Exception:  # noqa: BLE001 - UnicodeEncodeError, a closed stdout
        pass
    path = plan.get("log_file")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# waiting for the app to close
# ---------------------------------------------------------------------------

def _kernel32():
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.GetExitCodeProcess.restype = wintypes.BOOL
    k.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    k.WaitForSingleObject.restype = wintypes.DWORD
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    return k


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        k = _kernel32()
        handle = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() != 87             # ERROR_INVALID_PARAMETER: no such process
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259                         # STILL_ACTIVE
        finally:
            k.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:                                   # our own child that has ended (tests)
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        pass
    except OSError:
        pass
    try:                                   # Linux: a zombie has ended
        with open(f"/proc/{pid}/stat", encoding="ascii", errors="replace") as fh:
            return fh.read().rsplit(")", 1)[-1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _wait_windows(pid: int, seconds: float):
    """Windows: hold the process once and wait on it (no mix-up with a new process that gets the same
    number). True/False, or None when the process cannot be held (then the caller polls)."""
    import ctypes
    k = _kernel32()
    handle = k.OpenProcess(0x00100000 | 0x1000, False, pid)     # SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return True if ctypes.get_last_error() == 87 else None
    try:
        return k.WaitForSingleObject(handle, int(seconds * 1000)) == 0      # WAIT_OBJECT_0
    finally:
        k.CloseHandle(handle)


def wait_for_exit(pid: int, seconds: float, poll: float = 0.25) -> bool:
    if sys.platform == "win32":
        done = _wait_windows(pid, seconds)
        if done is not None:
            return done
    end = time.time() + seconds
    while time.time() < end:
        if not pid_alive(pid):
            return True
        time.sleep(poll)
    return not pid_alive(pid)


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

def installed_version(ext_dir: str) -> str:
    try:
        with open(os.path.join(ext_dir, "blender_manifest.toml"), encoding="utf-8") as fh:
            m = re.search(r'^version\s*=\s*"([^"]+)"', fh.read(), re.M)
        return m.group(1) if m else ""
    except OSError:
        return ""


def _child_flags() -> int:
    return CREATE_NO_WINDOW if sys.platform == "win32" else 0


def run_install(plan: dict) -> tuple[bool, str]:
    cmd = [plan["blender"], "--command", "extension", "install-file", "-r", plan.get("repo") or "user_default",
           "-e", plan["zip"]]
    _log(plan, "running: " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                              cwd=os.path.dirname(os.path.abspath(plan["zip"])), timeout=INSTALL_SECONDS,
                              creationflags=_child_flags())
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Blender could not be started to install the update ({exc})"
    text = proc.stdout.decode("utf-8", "replace") if proc.stdout else ""     # (the log file is UTF-8)
    for line in text.splitlines():
        _log(plan, "   " + line)
    if proc.returncode != 0:
        return False, f"Blender's installer stopped with exit code {proc.returncode}"
    return True, ""


def copy_template(src: str, dst: str) -> list[str]:
    """Copy the app template files from ``src`` over ``dst`` where they differ; returns the
    names copied. Old compiled files (__pycache__) in ``dst`` are removed with any change."""
    changed = []
    if not os.path.isdir(src):
        return changed
    os.makedirs(dst, exist_ok=True)
    for name in sorted(os.listdir(src)):
        s = os.path.join(src, name)
        if not os.path.isfile(s) or name.endswith(".pyc"):
            continue
        d = os.path.join(dst, name)
        try:
            with open(s, "rb") as a:
                new = a.read()
            old = None
            if os.path.isfile(d):
                with open(d, "rb") as b:
                    old = b.read()
            if old == new:
                continue
            tmp = d + ".new"
            with open(tmp, "wb") as fh:
                fh.write(new)
            os.replace(tmp, d)
            changed.append(name)
        except OSError:
            continue
    if changed:
        shutil.rmtree(os.path.join(dst, "__pycache__"), ignore_errors=True)
    return changed


def restart(plan: dict) -> str:
    """Start the app again, once (also when called a second time after an error)."""
    cmd = plan.get("restart") or []
    if not cmd or plan.get("_restarted"):
        return ""
    plan["_restarted"] = True
    kwargs = dict(cwd=os.path.dirname(os.path.abspath(cmd[0])) or None, stdin=subprocess.DEVNULL,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if sys.platform == "win32":
        base = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        try:
            subprocess.Popen(cmd, creationflags=base | CREATE_BREAKAWAY_FROM_JOB, **kwargs)
        except OSError:              # a job that does not allow breaking away
            subprocess.Popen(cmd, creationflags=base, **kwargs)
    else:
        subprocess.Popen(cmd, start_new_session=True, **kwargs)
    return " ".join(cmd)


def _busy_path(plan: dict) -> str:
    st = plan.get("status_file") or ""
    return os.path.join(os.path.dirname(st), BUSY_FILE) if st else ""


def mark_busy(plan: dict, busy: bool) -> None:
    """While the helper works, a file says so: an app started meanwhile (Desktop icon) tells the user to
    wait instead of starting on half-installed files."""
    path = _busy_path(plan)
    if not path:
        return
    try:
        if busy:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"pid": os.getpid(), "to": plan.get("expected_version", "")}, fh)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def write_status(plan: dict, ok: bool, message: str, version: str) -> None:
    path = plan.get("status_file")
    if not path:
        return
    data = {"ok": ok, "message": message, "from": plan.get("old_version", ""), "to": plan.get("expected_version", ""),
            "installed": version, "log": plan.get("log_file", ""),
            "time": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".new"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, path)
    except OSError as exc:
        _log(plan, f"could not write the status file: {exc}")


def run(plan: dict) -> bool:
    _log(plan, f"Fresing Render update {plan.get('old_version', '?')} -> {plan.get('expected_version', '?')}")
    pid = int(plan.get("wait_pid") or 0)
    if pid:
        _log(plan, f"waiting for Fresing Render (process {pid}) to close")
        if not wait_for_exit(pid, float(plan.get("wait_seconds") or WAIT_SECONDS)):
            _log(plan, "it did not close: nothing was changed")
            write_status(plan, False, "Fresing Render did not close, so the update was not installed. "
                                      "Press Update now again.", plan.get("old_version", ""))
            return False
        time.sleep(1.0)                       # let Windows release the files
    mark_busy(plan, True)
    try:
        ok, message, version = _install_with_retries(plan)
    finally:
        mark_busy(plan, False)
    if not version:
        _log(plan, "WARNING: no installed extension found after the update")
    if ok:
        tdir = plan.get("template_dir") or ""
        if tdir:
            try:
                changed = copy_template(os.path.join(plan["ext_dir"], TEMPLATE_FILES_DIR), tdir)
                _log(plan, "app template: " + (", ".join(changed) + " updated" if changed else "already current"))
            except OSError as exc:
                _log(plan, f"app template not updated: {exc}")
        try:
            os.remove(plan["zip"])
        except OSError:
            pass
        message = f"Updated to {version}."
    _log(plan, ("OK: " if ok else "FAILED: ") + message)
    write_status(plan, ok, message, version)
    try:
        started = restart(plan)
        if started:
            _log(plan, "started again: " + started)
    except OSError as exc:
        _log(plan, f"could not start Fresing Render again ({exc}): start it from the Desktop")
    return ok


def _install_with_retries(plan: dict) -> tuple[bool, str, str]:
    """Blender's installer, tried again after a pause when it fails or leaves another version (a virus
    scanner or an Explorer window can hold a file for a moment). The old version stays until the swap."""
    expected = plan.get("expected_version", "")
    waits = list(plan.get("retry_waits", RETRY_WAITS))
    while True:
        ok, message = run_install(plan)
        version = installed_version(plan["ext_dir"])
        if ok and expected and version != expected:
            ok, message = False, f"after installing, the version is '{version or 'missing'}' instead of {expected}"
        if ok or not waits:
            return ok, message, version
        wait = waits.pop(0)
        _log(plan, f"{message}: trying again in {wait:.0f} s")
        time.sleep(wait)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print(__doc__)
        return 2
    with open(argv[0], encoding="utf-8") as fh:
        plan = json.load(fh)
    try:
        return 0 if run(plan) else 1
    except Exception as exc:  # noqa: BLE001 - always leave a status and start the app again (once)
        _log(plan, f"FAILED: {type(exc).__name__}: {exc}")
        if not plan.get("_restarted"):           # an error after the restart must not undo a good result
            write_status(plan, False, f"The update stopped with an error ({exc}).",
                         installed_version(plan.get("ext_dir", "")))
        mark_busy(plan, False)
        try:
            restart(plan)
        except OSError:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
