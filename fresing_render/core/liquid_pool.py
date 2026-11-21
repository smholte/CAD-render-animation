"""Helper processes for the coolant liquid (task 0255). No Blender here.

A big chart's sub-steps are shared out over helper processes. Every chart's arrays live in shared memory
(``multiprocessing.shared_memory``, one block per chart); the master and the helpers step their own windows of the
same arrays (``liquid.Kernel``), one sub-step at a time: the master sends every helper "next sub-step", steps its own
share and waits until all helpers answer. A window's result is the same bit for bit whoever steps it, so the liquid
does not depend on the number of helpers (``tests/test_liquid_pool.py``).

The helpers are started as the STEP reader starts its own (``importer/step_reader.py``): a plain Python (Blender's own
Python inside Blender, never Blender itself), this file with ``--helper <parent pid>``, pickled messages on stdin /
stdout. Windows: no console window (``CREATE_NO_WINDOW``; Python's multiprocessing cannot pass that flag), below-normal
priority, no crash dialog, and a job object that ends them when the master ends; Linux: they die with the parent
(``PR_SET_PDEATHSIG``). Every helper also watches its parent and stops when it is gone.
"""

from __future__ import annotations

import os
import pickle
import queue
import struct
import subprocess
import sys
import threading
import time

import numpy as np

try:                                   # inside the package
    from . import liquid
except ImportError:                    # run as a helper script
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import liquid                      # noqa: E402

from multiprocessing import shared_memory

_MSG = b"FRL1"
_HEAD = struct.Struct(">4sQ")
MIN_CELLS = 16000          # a frame's stepped cells per helper below which the helper is not worth a round trip
MAX_HELPERS = 32
START_TIMEOUT = 60.0       # s for a helper to come up (a virus scan of its first start can take a while)
ANSWER_TIMEOUT = 120.0     # s for one answer (a sub-step takes milliseconds): longer = the helper hangs


class HelperError(RuntimeError):
    """A helper stopped or answered wrongly; the liquid's state is not complete. Run again with fewer helpers."""


def python_executable() -> str:
    """The Python to run helpers with: Blender's own Python inside Blender (as ``importer.runner``)."""
    exe = sys.executable
    if os.path.basename(exe).lower().startswith("blender"):
        guess = os.path.join(os.path.dirname(exe), "python", "bin", "python.exe" if os.name == "nt" else "python3")
        if os.path.isfile(guess):
            return guess
    return exe


def default_helpers() -> int:
    """All cores but one (the master steps a share itself), at most ``MAX_HELPERS``; 0 on a 1- or 2-core machine."""
    cores = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    n = min(cores - 1, MAX_HELPERS)
    return n if n >= 2 else 0


# ---- the arrays of a chart in one shared block ------------------------------------------------------------------

def layout(NY, NX):
    """[(name, shape, dtype, offset)], total bytes: the chart's arrays in one block, each 64-byte aligned."""
    out = []
    off = 0
    for name, kind, dt in liquid.ARRAYS:
        shp = liquid.array_shape(kind, NY, NX)
        size = int(np.prod(shp)) * np.dtype(dt).itemsize
        out.append((name, shp, dt, off))
        off += (size + 63) // 64 * 64
    return out, max(off, 64)


def _views(buf, NY, NX):
    lay, _ = layout(NY, NX)
    return {name: np.ndarray(shp, dtype=dt, buffer=buf, offset=off) for name, shp, dt, off in lay}


def _attach(name):
    try:
        return shared_memory.SharedMemory(name=name, track=False)      # Python 3.13+: the master owns it
    except TypeError:                                                  # older Python: no 'track'
        shm = shared_memory.SharedMemory(name=name)
        try:
            from multiprocessing import resource_tracker
            resource_tracker.unregister(shm._name, "shared_memory")    # noqa: SLF001 – else it is unlinked at exit
        except Exception:
            pass
        return shm


# ---- messages ------------------------------------------------------------------------------------------------------

def _send(stream, obj) -> None:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    stream.write(_HEAD.pack(_MSG, len(data)))
    stream.write(data)
    stream.flush()


def _read(stream, n):
    parts = []
    while n > 0:
        b = stream.read(n)
        if not b:
            raise EOFError("helper stopped")
        parts.append(b)
        n -= len(b)
    return b"".join(parts)


def _recv(stream):
    head = _read(stream, _HEAD.size)
    tag, size = _HEAD.unpack(head)
    if tag != _MSG:
        raise HelperError("a liquid helper sent something unexpected")
    return pickle.loads(_read(stream, size))


# ---- in a helper ---------------------------------------------------------------------------------------------------

def _exit_with_parent(parent_pid: int) -> None:
    """A helper stops at once when the master stops (also when it is killed)."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k32.OpenProcess.restype = wintypes.HANDLE
        k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        k32.WaitForSingleObject.restype = wintypes.DWORD
        handle = k32.OpenProcess(0x00100000, False, parent_pid)          # SYNCHRONIZE
        if not handle:
            os._exit(0)

        def watch():
            k32.WaitForSingleObject(handle, 0xFFFFFFFF)                    # INFINITE
            os._exit(0)
    else:
        def watch():
            while os.getppid() == parent_pid:
                time.sleep(0.5)
            os._exit(0)
    threading.Thread(target=watch, daemon=True).start()


def _no_crash_dialog() -> None:
    """Windows: a crash ends the process at once instead of waiting on an error-report window."""
    if os.name == "nt":
        try:
            import ctypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.SetErrorMode.argtypes = [ctypes.c_uint]
            k32.SetErrorMode.restype = ctypes.c_uint
            k32.SetErrorMode(0x0001 | 0x0002)        # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX
        except Exception:
            pass


def helper_main(parent_pid: int) -> int:
    """Helper loop: messages in on stdin, answers out on stdout, until stdin closes or "quit"."""
    _no_crash_dialog()
    _exit_with_parent(parent_pid)
    if os.name != "nt":
        try:
            os.nice(5)               # Windows: the master starts helpers below normal priority
        except OSError:
            pass
    out_fd = os.dup(1)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)              # anything printed must not end up in the answer stream
    sys.stdout = open(os.devnull, "w")
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(0, os.O_BINARY)
        msvcrt.setmode(out_fd, os.O_BINARY)
    out = os.fdopen(out_fd, "wb")
    inp = sys.stdin.buffer
    shms = []
    kernels = {}
    current = None
    _send(out, ("ready", os.getpid()))
    try:
        while True:
            try:
                msg = _recv(inp)
            except EOFError:
                return 0
            kind = msg[0]
            try:
                if kind == "init":
                    for c, name, NY, NX, meta in msg[1]:
                        shm = _attach(name)
                        shms.append(shm)
                        kernels[c] = liquid.Kernel(_views(shm.buf, NY, NX), meta)
                    _send(out, ("ok",))
                elif kind == "frame":
                    _, c, runs, n, dt, gc, gb, uniform, push, rain = msg
                    current = kernels[c]
                    current.frame(runs, n, dt, gc, gb, uniform, push, rain)
                    current.sub(0)
                    _send(out, ("ok", current.report(liquid.tiles_of)) if n == 1 else ("ok",))
                elif kind == "sub":
                    k, last = msg[1], msg[2]
                    current.sub(k)
                    _send(out, ("ok", current.report(liquid.tiles_of)) if last else ("ok",))
                elif kind == "quit":
                    _send(out, ("ok",))
                    return 0
                else:
                    _send(out, ("error", f"unknown message {kind!r}"))
            except Exception as exc:          # tell the master; it stops the bake
                _send(out, ("error", f"{type(exc).__name__}: {exc}"))
    finally:
        kernels.clear()
        current = None
        for shm in shms:
            try:
                shm.close()
            except Exception:
                pass


# ---- in the master -------------------------------------------------------------------------------------------------

def _kill_on_close_job():
    """Windows job object that ends its processes when the master ends (also when it is killed)."""
    import ctypes
    from ctypes import wintypes

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [(n, ctypes.c_ulonglong) for n in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class BASIC_LIMITS(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class EXTENDED_LIMITS(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC_LIMITS), ("IoInfo", IO_COUNTERS),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryLimit", ctypes.c_size_t), ("PeakJobMemoryLimit", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.SetInformationJobObject.restype = wintypes.BOOL
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.AssignProcessToJobObject.restype = wintypes.BOOL
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.CloseHandle.restype = wintypes.BOOL
    job = k32.CreateJobObjectW(None, None)
    if not job:
        return None, None, None
    info = EXTENDED_LIMITS()
    info.BasicLimitInformation.LimitFlags = 0x00002000            # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):   # ExtendedLimitInformation
        k32.CloseHandle(job)
        return None, None, None

    def assign(proc) -> None:
        if not k32.AssignProcessToJobObject(job, int(proc._handle)):   # noqa: SLF001
            sys.stderr.write(f"liquid helper not in job (error {ctypes.get_last_error()}); it stops by itself\n")

    def close() -> None:
        k32.CloseHandle(job)
    return job, assign, close


class Pool:
    """``n`` helper processes and the charts' shared memory. ``python``: the Python to start them with."""

    HelperError = HelperError

    def __init__(self, n: int, python: str | None = None):
        self.procs: list[subprocess.Popen] = []
        self.shms: list = []
        self.charts: list = []                 # (c, name, NY, NX)
        self.broken = None
        self._job = None
        self._job_close = None
        kwargs: dict = {}
        assign = None
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000 | 0x00004000   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
            try:
                self._job, assign, self._job_close = _kill_on_close_job()
            except Exception:
                assign = None                  # the helpers still stop by themselves, a bit later
        # (Linux: no PR_SET_PDEATHSIG through preexec_fn – forking a many-threaded Blender with one can deadlock;
        # every helper watches its parent itself.)
        env = dict(os.environ)
        for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
            env.pop(var, None)                 # another program's Python settings must not leak in (as runner.py)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
        kwargs["env"] = env
        self._queues: dict = {}
        cmd = [python or python_executable(), "-s", os.path.abspath(__file__), "--helper", str(os.getpid())]
        for _ in range(max(0, min(int(n), MAX_HELPERS))):
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
            except OSError:
                break
            if assign is not None:
                try:
                    assign(proc)
                except Exception:
                    pass
            self.procs.append(proc)
            self._queues[proc.pid] = q = queue.Queue()
            threading.Thread(target=self._reader, args=(proc, q), daemon=True).start()
        alive = []
        for p in self.procs:                   # every helper says it is ready (numpy loaded)
            try:
                msg = self._queues[p.pid].get(timeout=START_TIMEOUT)
                if isinstance(msg, tuple) and msg[0] == "ready":
                    alive.append(p)
                    continue
            except queue.Empty:
                pass
            self._stop(p)                      # it did not come up: the others do its share
        self.procs = alive

    @staticmethod
    def _reader(proc, q):
        """Reads a helper's answers into its queue (so the master can wait with a time-out)."""
        while True:
            try:
                q.put(_recv(proc.stdout))
            except BaseException as exc:      # noqa: BLE001 – end of the stream or a broken message
                q.put(exc)
                return

    @property
    def size(self) -> int:
        return len(self.procs)

    def allocate(self, c, NY, NX):
        """The arrays of chart c in a new shared block (zeros)."""
        _, total = layout(NY, NX)
        shm = shared_memory.SharedMemory(create=True, size=total)      # the system hands it out zeroed
        self.shms.append(shm)
        self.charts.append((c, shm.name, NY, NX))
        return _views(shm.buf, NY, NX)

    def start(self, metas):
        """Every helper attaches to the charts' blocks."""
        items = [(c, name, NY, NX, metas[c]) for c, name, NY, NX in self.charts]
        ok = []
        for p in self.procs:
            try:
                _send(p.stdin, ("init", items))
                ok.append(p)
            except Exception:
                self._stop(p)
        alive = []
        for p in ok:                            # a helper that cannot attach is dropped: the others do its share
            try:
                self._answer(p, START_TIMEOUT)
                alive.append(p)
            except HelperError:
                self._stop(p)
        self.broken = None
        self.procs = alive

    def worth(self, cells) -> bool:
        return self.broken is None and self.size > 0 and cells >= 2 * MIN_CELLS

    def _answer(self, p, timeout=None):
        timeout = ANSWER_TIMEOUT if timeout is None else timeout
        try:
            msg = self._queues[p.pid].get(timeout=timeout)
        except queue.Empty:
            self.broken = f"a liquid helper did not answer within {timeout:.0f} s"
            self._kill(p)
            raise HelperError(self.broken) from None
        if isinstance(msg, BaseException):
            self.broken = f"a liquid helper stopped ({msg or type(msg).__name__})"
            raise HelperError(self.broken) from msg
        if not isinstance(msg, tuple) or msg[0] != "ok":
            self.broken = f"a liquid helper failed: {msg[1] if len(msg) > 1 else msg}"
            raise HelperError(self.broken)
        return msg

    @staticmethod
    def split(runs, parts, T=None):
        """Share runs out over ``parts`` workers by their cells (largest first); long runs are halved at tile
        boundaries while there are fewer than 2 runs per worker. Any split gives the same liquid."""
        T = T or liquid.TILE
        runs = list(runs)
        while len(runs) < 2 * parts:
            big = max(range(len(runs)), key=lambda k: (runs[k][3] - runs[k][2]) * (runs[k][1] - runs[k][0]))
            r0, r1, c0, c1 = runs[big]
            tiles = -(-(c1 - c0) // T)
            if tiles < 2:
                break
            mid = c0 + (tiles // 2) * T
            runs[big:big + 1] = [(r0, r1, c0, mid), (r0, r1, mid, c1)]
        size = [0] * parts
        out = [[] for _ in range(parts)]
        for r in sorted(runs, key=lambda r: -(r[1] - r[0]) * (r[3] - r[2])):
            k = min(range(parts), key=lambda i: size[i])
            out[k].append(r)
            size[k] += (r[1] - r[0]) * (r[3] - r[2])
        return out

    def frame(self, c, runs, n, dt, gc, gb, uniform, push, rain, local):
        """Step chart c's ``runs`` through ``n`` sub-steps with the helpers and ``local`` (the master's kernel)."""
        if self.broken:
            raise HelperError(self.broken)
        try:
            return self._frame(c, runs, n, dt, gc, gb, uniform, push, rain, local)
        except BaseException as exc:          # noqa: BLE001 – the helpers' answers are out of step now: no more
            if self.broken is None:
                self.broken = f"the liquid bake stopped in a frame ({type(exc).__name__}: {exc})"
            raise

    def _frame(self, c, runs, n, dt, gc, gb, uniform, push, rain, local):
        cells = sum((r1 - r0) * (r3 - r2) for r0, r1, r2, r3 in runs)
        parts = max(1, min(self.size + 1, cells // MIN_CELLS))
        shares = self.split(runs, parts)
        mine, theirs = shares[0], [s for s in shares[1:] if s]
        helpers = self.procs[:len(theirs)]
        gc = np.asarray(gc, float)
        gb = np.asarray(gb, float)
        for p, share in zip(helpers, theirs):
            self._post(p, ("frame", c, share, n, dt, gc, gb, uniform, push, rain))
        local.frame(mine, n, dt, gc, gb, uniform, push, rain)
        reports = []
        for k in range(n):
            if k > 0:
                for p in helpers:
                    self._post(p, ("sub", k, k == n - 1))
            local.sub(k)
            for p in helpers:
                msg = self._answer(p)
                if k == n - 1:
                    reports.extend(msg[1])
        reports.extend(local.report(liquid.tiles_of))
        return reports

    def _post(self, p, msg):
        try:
            _send(p.stdin, msg)
        except Exception as exc:
            self.broken = f"a liquid helper stopped ({exc})"
            raise HelperError(self.broken) from exc

    @staticmethod
    def _kill(p):
        try:
            p.kill()
            p.wait(timeout=5.0)
        except Exception:
            pass

    @classmethod
    def _stop(cls, p):
        try:
            p.stdin.close()
        except Exception:
            pass
        try:
            p.wait(timeout=2.0)
        except Exception:
            cls._kill(p)

    def close(self) -> None:
        """Stop the helpers and free the shared memory (the arrays handed out are no longer usable)."""
        for p in self.procs:
            try:
                p.stdin.close()                 # the helper's loop ends at EOF
            except Exception:
                pass
        end = time.time() + 3.0
        for p in self.procs:
            try:
                p.wait(timeout=max(0.1, end - time.time()))
            except Exception:
                self._kill(p)
        self.procs = []
        for shm in self.shms:
            try:
                shm.close()
            except BufferError:                 # a view is still held by the caller: freed when the last view goes
                pass
            except Exception:
                pass
            try:
                shm.unlink()
            except Exception:
                pass
        self.shms = []
        if self._job_close is not None:
            try:
                self._job_close()
            except Exception:
                pass
            self._job_close = None


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--helper":
        sys.exit(helper_main(int(sys.argv[2])))
    sys.exit("usage: liquid_pool.py --helper <parent pid>")
