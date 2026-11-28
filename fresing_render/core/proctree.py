"""A program and every program it starts, as one thing that can be stopped for sure (task 0371).

The demo build (Help > Make demo project) is a background Blender that starts the model maker and, per model, the STEP
reader, which starts its helpers. Cancel used to stop the Blender's tree once (``taskkill /T`` / the process group) and
let Make it start a new build as soon as the Blender itself had ended – also when the build had stopped by itself after
Cancel and nothing was stopped at all, and while the processes it had started were still ending. ``Tree`` keeps the
whole tree together from its start and says whether *any* of it still runs:

* **Windows:** the started program goes into a job object of its own (no limits, no kill-on-close: a build keeps
  running when the app is closed, as before). Programs it starts are in the job too (the STEP reader's own job for
  its helpers nests inside it). ``kill`` = ``TerminateJobObject``; ``alive`` = the job still has an active process.
* **Linux / macOS:** the program starts a session of its own (``start_new_session``); its group is the tree.
  ``kill`` = SIGKILL to the group; ``alive`` = a process of the group still exists.

No bpy here (tested with plain Python).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"


def _k32():
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    k32.TerminateJobObject.restype = wintypes.BOOL
    k32.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
                                              ctypes.c_void_p]
    k32.QueryInformationJobObject.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    return k32


def _active_in_job(k32, job) -> int:
    """JOBOBJECT_BASIC_ACCOUNTING_INFORMATION.ActiveProcesses (-1: could not be asked)."""
    import ctypes
    from ctypes import wintypes

    class ACCOUNTING(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                    ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]

    info = ACCOUNTING()
    if not k32.QueryInformationJobObject(job, 1, ctypes.byref(info), ctypes.sizeof(info), None):
        return -1                                                     # 1 = JobObjectBasicAccountingInformation
    return int(info.ActiveProcesses)


class Tree:
    """``Tree(cmd, **popen_kwargs)``: starts ``cmd`` (``subprocess.Popen``) as the root of a tree; ``proc`` is its
    Popen. ``kill()`` stops every program of the tree, ``alive()`` says whether any still runs, ``wait(timeout)``
    waits until none does."""

    def __init__(self, cmd, **kwargs):
        self._job = None
        self._k32 = None
        self._killed = False
        self.job_error = ""                        # Windows: why the tree has no job object (then taskkill /T)
        if WINDOWS:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(cmd, **kwargs)
        self.pid = self.proc.pid
        self.pgid = 0
        if WINDOWS:
            try:
                import ctypes
                k32 = _k32()
                job = k32.CreateJobObjectW(None, None)
                if job and k32.AssignProcessToJobObject(job, int(self.proc._handle)):
                    self._job, self._k32 = job, k32
                else:
                    self.job_error = f"Windows error {ctypes.get_last_error()}"
                    if job:
                        k32.CloseHandle(job)
            except Exception as exc:  # noqa: BLE001 - without a job the tree is stopped with taskkill /T
                self._job = None
                self.job_error = str(exc) or type(exc).__name__
            if self.job_error:
                print(f"Fresing Render: a program could not be put in a job object ({self.job_error}); "
                      "it is stopped with taskkill instead")
        else:
            try:
                self.pgid = os.getpgid(self.pid)
            except OSError:
                self.pgid = self.pid               # it ended already; its group had its number

    def kill(self) -> None:
        """Stop every program of the tree (nothing happens to programs outside it)."""
        if WINDOWS:
            if self._job is not None:
                self._k32.TerminateJobObject(self._job, 1)
            elif self.proc.poll() is None and not self._killed:
                self._killed = True                # taskkill waits for its answer: once is enough
                kill_pid_tree(self.pid)
            return
        try:
            os.killpg(self.pgid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        self.proc.poll()                           # reap the root, so its group number can go

    @property
    def in_job(self) -> bool:
        """Windows: the tree is held by a job object (else only its first program is known)."""
        return self._job is not None

    def alive(self) -> bool:
        """A program of the tree still runs (or is still ending)."""
        if self.proc.poll() is None:
            return True
        if WINDOWS:
            if self._job is None:
                return False
            return _active_in_job(self._k32, self._job) > 0
        running = _group_running(self.pgid)
        if running is not None:
            return running
        try:
            os.killpg(self.pgid, 0)
        except ProcessLookupError:
            return False
        except OSError:                            # EPERM: a process of another user took the number (not ours)
            return False
        return True

    def wait(self, timeout: float = 30.0) -> bool:
        """Wait until nothing of the tree runs; True when that happened within ``timeout`` seconds."""
        end = time.monotonic() + timeout
        while self.alive():
            if time.monotonic() > end:
                return False
            time.sleep(0.05)
        return True

    def close(self) -> None:
        if self._job is not None:
            try:
                self._k32.CloseHandle(self._job)
            except Exception:  # noqa: BLE001
                pass
            self._job = None


def _group_running(pgid: int):
    """Linux: a process of group ``pgid`` that is not a zombie (an ended child whose parent has not collected it yet –
    in a container nobody may ever collect it). None where /proc cannot tell (macOS)."""
    if not os.path.isdir("/proc/self"):
        return None
    try:
        names = os.listdir("/proc")
    except OSError:
        return None
    for name in names:
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", "rb") as fh:
                stat = fh.read().decode("ascii", "replace")
        except OSError:
            continue
        fields = stat[stat.rfind(")") + 2:].split()          # after "pid (name) ": state ppid pgrp …
        if len(fields) >= 3 and fields[2] == str(pgid) and fields[0] not in ("Z", "X"):
            return True
    return False


def kill_pid_tree(pid: int) -> None:
    """Stop a program and every program it started, known only by its number (``taskkill /T`` / its group)."""
    if not pid:
        return
    try:
        if WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
