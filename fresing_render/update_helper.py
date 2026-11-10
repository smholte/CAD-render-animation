"""Installs a downloaded update while Fresing Render is closed, then starts the app again.

The app (``blender/updates.py``) downloads and checks the new extension zip, copies this file
to a folder of its own (the extension folder itself is replaced during the update), writes a
plan next to it and starts it with Blender's own Python:

    python -I update_helper.py <plan.json>

Plan (JSON): blender (blender program), wait_pid (the app's process), zip, expected_version,
old_version, repo (extension repository the app is installed in, e.g. "user_default"),
ext_dir (installed extension folder), template_dir (installed app template, "" = none),
restart (command line to start the app again, [] = none), status_file, log_file.

Steps: wait until the app has closed, and every other Blender of the same install (a second window, a
queued render, the PC check) -> copy the installed extension to a backup -> ``blender --command extension
install-file`` (Blender's own installer: unpacks next to the old version, then swaps) -> check the installed
version; when the extension folder is gone (a failed swap), put the backup back -> copy the app template
that ships inside the new extension -> write the status file the app shows at its next start -> start the
app again (also when something failed: the old version still works).

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
BACKUP_DIR = "backup"                         # next to the status file: the old extension during the install
# a busy file older than this is left over from a helper that was killed (power cut, log-off): the longest a
# helper can take is the wait for the app plus every try of the installer
# (the wait for other Blenders, every try of the installer, the backup and a margin)
BUSY_MAX_SECONDS = 2 * WAIT_SECONDS + INSTALL_SECONDS * (len(RETRY_WAITS) + 1) + sum(RETRY_WAITS) + 600
BLENDER_NAMES = ("blender.exe", "blender")    # the program files of the Blenders a helper waits for

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

_K32: list = []


def _kernel32():
    if _K32:
        return _K32[0]
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
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                             ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.restype = wintypes.BOOL
    k.K32EnumProcesses.argtypes = [ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    k.K32EnumProcesses.restype = wintypes.BOOL
    _K32.append(k)
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


def process_image(pid: int) -> str:
    """The program file a running process was started from ('' when there is no such process or it cannot be
    read, e.g. another user's process)."""
    if pid <= 0:
        return ""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        try:
            k = _kernel32()
            handle = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return ""
            try:
                buf = ctypes.create_unicode_buffer(32768)
                size = wintypes.DWORD(len(buf))
                if not k.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    return ""
                return buf.value
            finally:
                k.CloseHandle(handle)
        except (OSError, AttributeError):
            return ""
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return ""


def _all_pids() -> list[int]:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        try:
            k = _kernel32()
            n = 4096
            while True:
                arr = (wintypes.DWORD * n)()
                got = wintypes.DWORD()
                if not k.K32EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got)):
                    return []
                count = got.value // ctypes.sizeof(wintypes.DWORD)
                if count < n:
                    return [int(p) for p in arr[:count]]
                n *= 2
        except (OSError, AttributeError):
            return []
    try:
        return [int(d) for d in os.listdir("/proc") if d.isdigit()]
    except OSError:
        return []


def _long_path(path: str) -> str:
    """Windows: the long spelling of a path (8.3 short names like PROGRA~1 written out), case as stored.
    Returns the path unchanged when it cannot be asked (Linux, a path that does not exist)."""
    if sys.platform != "win32":
        return path
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(32768)
        n = ctypes.windll.kernel32.GetLongPathNameW(path, buf, len(buf))
        return buf.value if 0 < n < len(buf) else path
    except (OSError, AttributeError):
        return path


def _norm(path: str) -> str:
    # Windows: the names as the system reports them, short 8.3 names written out (no realpath: it opens every
    # file); Linux: links resolved
    if sys.platform == "win32":
        return os.path.normcase(os.path.abspath(_long_path(os.path.abspath(path))))
    return os.path.normcase(os.path.realpath(path))


def _identity(path: str):
    """(volume, file index) of a file or folder: the same thing under any spelling, also a ``subst`` drive
    letter or a link. None when it cannot be asked."""
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_dev, st.st_ino) if st.st_ino else None


def same_place(a: str, b: str) -> bool:
    """Do two paths name the same file or folder: same normalised long spelling, or same file identity."""
    if not a or not b:
        return False
    if _norm(a) == _norm(b):
        return True
    ia, ib = _identity(a), _identity(b)
    return ia is not None and ia == ib


def is_inside(path: str, root: str, depth: int = 8) -> bool:
    """Is ``path`` inside the folder ``root`` (any spelling, also a ``subst`` drive): by the normalised names
    first, then by looking for ``root``'s identity among the first ``depth`` parent folders of ``path``."""
    if not path or not root:
        return False
    base = _norm(root).rstrip("\\/") + os.sep
    if _norm(path).startswith(base):
        return True
    want = _identity(root)
    if want is None:
        return False
    cur = os.path.dirname(os.path.abspath(path))
    for _ in range(depth):
        if _identity(cur) == want:
            return True
        up = os.path.dirname(cur)
        if up == cur:
            break
        cur = up
    return False


def other_blenders(install_dir: str, exclude=()) -> list[int]:
    """Running Blenders started from ``install_dir`` (the app's own Blender folder), apart from ``exclude`` and
    this process: a second app window, a queued render, the PC check. As Install.bat checks. Matches by long
    spelling and by file identity, so 8.3 short names and ``subst`` drives are found too (task 0060)."""
    if not install_dir:
        return []
    skip = {int(p) for p in exclude if p} | {os.getpid()}
    found = []
    for pid in _all_pids():
        if pid in skip:
            continue
        image = process_image(pid)
        if not image or os.path.basename(image).lower() not in BLENDER_NAMES:
            continue
        if is_inside(image, install_dir) and pid_alive(pid):
            found.append(pid)
    return sorted(found)


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
                json.dump({"pid": os.getpid(), "to": plan.get("expected_version", ""), "started": time.time(),
                           "exe": sys.executable}, fh)
        elif os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def busy_helper(path: str, now: float | None = None) -> dict | None:
    """What the busy file ``path`` says when a helper is really installing right now, else None. A file left by
    a helper that was killed (power cut, log-off, virus scanner) is deleted: it is older than a helper can
    take, or its process number now belongs to another program (Windows reuses them)."""
    try:
        with open(path, encoding="utf-8") as fh:
            info = json.load(fh)
        pid = int(info.get("pid", 0))
    except (OSError, ValueError, TypeError, AttributeError):
        return None
    now = time.time() if now is None else now
    try:
        started = float(info.get("started") or os.path.getmtime(path))     # older helpers wrote no time
    except (OSError, TypeError, ValueError):
        started = 0.0
    stale = ""
    if not pid_alive(pid):
        stale = "its helper has ended"
    elif now - started > BUSY_MAX_SECONDS:
        stale = f"it is {(now - started) / 60:.0f} min old"
    else:
        # the helper and the app run as the same user, so the helper's program can always be read: a number that
        # cannot be read (a system service after a restart) or that is another program is not the helper
        image = process_image(pid)
        want = info.get("exe") or ""
        if not image:
            stale = f"process {pid} is not the update helper"
        elif want and not same_place(image, want):
            stale = f"process {pid} is now {os.path.basename(image)}"
        elif not want and not os.path.basename(image).lower().startswith("python"):
            stale = f"process {pid} is now {os.path.basename(image)}"
    if stale:
        try:
            os.remove(path)
        except OSError:
            pass
        print(f"Fresing Render: an old update note was removed ({stale})")
        return None
    return info


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
    mark_busy(plan, True)            # an app started from the Desktop meanwhile says "being installed"
    try:
        if not wait_for_others(plan, pid):
            blocked = True
        else:
            blocked = False
            backup = make_backup(plan)
            plan["_backup"] = backup
            ok, message, version = _install_with_retries(plan)
            if not version and backup:
                ok, message, version = _put_back(plan, message)
            if backup and os.path.isdir(backup) and installed_version(plan["ext_dir"]):
                shutil.rmtree(backup, ignore_errors=True)
    finally:
        mark_busy(plan, False)
    if blocked:
        write_status(plan, False, "Another Fresing Render was still open (a second window, a queued render or "
                                  "the PC check), so the update was not installed. Close it, then press Update now "
                                  "again.", plan.get("old_version", ""))
        _start_again(plan)
        return False
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
    _start_again(plan)
    return ok


def _start_again(plan: dict) -> None:
    try:
        started = restart(plan)
        if started:
            _log(plan, "started again: " + started)
    except OSError as exc:
        _log(plan, f"could not start Fresing Render again ({exc}): start it from the Desktop")


def _put_back(plan: dict, message: str) -> tuple[bool, str, str]:
    """The extension folder is gone after the install (a swap that failed half-way): put the backup back, so the
    app opens with the old version and says what happened instead of opening as plain Blender."""
    backup = plan.get("_backup") or ""
    _log(plan, "WARNING: no installed extension found after the update: putting the old version back")
    if not backup or not restore_backup(plan, backup):
        return False, message, ""
    version = installed_version(plan["ext_dir"])
    return False, (f"The update to {plan.get('expected_version', '?')} could not be installed ({message}), so the "
                   f"old version {version} was put back. Press Update now again later, or run Install.bat."), version


def wait_for_others(plan: dict, app_pid: int) -> bool:
    """Wait until no other Blender of the same install runs (a second app window, a queued render, the PC check):
    Blender's installer swaps files those still use. When one stays open, nothing is changed, the status says
    why and the app starts again with the old version (``run``). True when the install can go ahead."""
    install_dir = os.path.dirname(os.path.abspath(plan.get("blender") or ""))
    if not plan.get("blender"):
        return True
    others = other_blenders(install_dir, exclude=(app_pid,))
    if not others:
        return True
    _log(plan, "waiting for the other Blender(s) of this install to close: process " + ", ".join(map(str, others)))
    end = time.time() + float(plan.get("wait_seconds") or WAIT_SECONDS)
    for other in others:
        wait_for_exit(other, max(0.0, end - time.time()))
    left = [p for p in other_blenders(install_dir, exclude=(app_pid,)) if p in others]
    if not left:
        time.sleep(1.0)
        return True
    _log(plan, "still open: process " + ", ".join(map(str, left)) + ": nothing was changed")
    return False


def _remove_tree(path: str, tries: int = 3) -> bool:
    """Delete a folder, also read-only files, trying again after a pause (a virus scanner can hold a file for a
    moment). True when it is gone."""
    import stat

    def writable(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass
    for attempt in range(tries):
        if not os.path.lexists(path):
            return True
        try:
            shutil.rmtree(path, onexc=writable)
        except OSError:
            pass
        if not os.path.lexists(path):
            return True
        if attempt < tries - 1:
            time.sleep(1.0)
    return not os.path.lexists(path)


def _backup_path(plan: dict) -> str:
    if plan.get("backup_dir"):
        return plan["backup_dir"]
    st = plan.get("status_file") or ""
    return os.path.join(os.path.dirname(st), BACKUP_DIR, "fresing_render") if st else ""


def make_backup(plan: dict) -> str:
    """Copy the installed extension aside before Blender's installer removes it (it deletes the old folder before
    it renames the new one in). Returns the backup folder, '' when there is none (a failed copy is no reason
    not to update: it only means there is nothing to put back)."""
    src, dst = plan.get("ext_dir") or "", _backup_path(plan)
    if not dst or not installed_version(src):
        return ""
    t0 = time.time()
    try:
        _remove_tree(dst)                                 # an older backup
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
    except (OSError, shutil.Error) as exc:
        _log(plan, f"no backup of the old version ({exc})")
        shutil.rmtree(dst, ignore_errors=True)
        return ""
    _log(plan, f"backup of {installed_version(dst)} made in {time.time() - t0:.1f} s: {dst}")
    return dst


def restore_backup(plan: dict, backup: str) -> bool:
    """Put the backup back where the extension was (what is left of a half-done swap is removed first)."""
    dst = plan["ext_dir"]
    try:
        try:
            if not _remove_tree(dst):
                raise OSError("what is left of the new version cannot be deleted")
            os.replace(backup, dst)                       # same disk: a rename
        except OSError:                                   # copy over whatever could not be deleted
            shutil.copytree(backup, dst, dirs_exist_ok=True)
            _remove_tree(backup)
    except (OSError, shutil.Error) as exc:
        _log(plan, f"could not put the old version back ({exc}); a copy is in {backup}: run Install.bat")
        return False
    ok = bool(installed_version(dst))
    _log(plan, f"old version {installed_version(dst)} put back" if ok else "the old version could not be put back")
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
        try:
            if plan.get("_backup") and not installed_version(plan.get("ext_dir", "")):
                restore_backup(plan, plan["_backup"])
        except Exception:  # noqa: BLE001
            pass
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
