"""Helper processes for the welds (task 0368). No Blender here.

Finding the welds of a model and making their beads and heat zones is plain Python with NumPy (``core/weld_cad.py``,
``core/welds.py``), ~0.06 s per weld on one core: a frame with 300 welds waited ~20 s at its import. The work is many
small, independent jobs – one bead piece's contacts, one pair of parts' beads measured, one weld's bead and heat zone –
so it is shared out over helper processes, job by job, and the master takes jobs too. A job's answer is the same
whoever works it out (the same functions on the same numbers), so the welds do not depend on the number of helpers
(``tests/test_weld_pool.py``).

The helpers are started as the liquid's (``core/liquid_pool.py``, whose Windows parts this file uses): a plain Python
(Blender's own Python inside Blender), this file with ``--helper <parent pid> <package>``, pickled messages on stdin /
stdout. Windows: no console window, below-normal priority, no crash dialog, a job object that ends them with the
master; every helper also watches its parent and stops when it is gone. A helper that does not come up, stops or
answers wrongly only costs time: its jobs are worked out by the master (``Pool.map`` never fails because of a helper).

A helper imports the welds' modules as the package ``core`` (this folder); the master's package is named differently
(``bl_ext.….fresing_render.core`` inside Blender). Pickled classes are renamed between the two on the way in
(``_Unpickler``).
"""

from __future__ import annotations

import io
import os
import pickle
import queue
import struct
import subprocess
import sys
import threading
import time

if __name__ == "__main__" and __package__ in (None, ""):      # started as a helper: become ``core.weld_pool``
    _HERE = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(_HERE))
    import core.weld_pool as _me                              # noqa: E402

    sys.exit(_me.helper_main(int(sys.argv[2]), sys.argv[3]) if len(sys.argv) > 3 and sys.argv[1] == "--helper"
             else 2)

from . import liquid_pool as _lp                              # noqa: E402  (the Windows parts of starting helpers)

_MSG = b"FRW1"
_HEAD = struct.Struct(">4sQ")
MAX_HELPERS = 12           # more helpers cost more to start than a model's welds win (300 welds: ~1 s of work each)
MIN_JOBS = 24              # fewer jobs than this: worked out by the master alone (a helper costs ~0.2–1 s to start)
START_TIMEOUT = 60.0       # s for a helper to come up (a virus scan of its first start can take a while)
ANSWER_TIMEOUT = 300.0     # s for one job's answer: longer = the helper hangs (its jobs go to the master)
OWN = __package__ or "core"   # this package's name here ("core" in a helper)

_SHARED: dict = {}          # in a helper: what the master shared (``Pool.share``)


def default_helpers() -> int:
    """All cores but one (the master works too), at most ``MAX_HELPERS``; 0 on a 1- or 2-core machine.
    ``FRESING_WELD_HELPERS=<n>`` sets it (tests, measuring; 0 = the master alone)."""
    env = os.environ.get("FRESING_WELD_HELPERS", "").strip()
    if env.isdigit():
        return min(int(env), MAX_HELPERS)
    cores = getattr(os, "process_cpu_count", os.cpu_count)() or 1
    n = min(cores - 1, MAX_HELPERS)
    return n if n >= 2 else 0


# ---- messages ------------------------------------------------------------------------------------------------------

class _Unpickler(pickle.Unpickler):
    """Classes of the other side's package name read as this side's (``prefix.x`` -> ``OWN.x``)."""

    def __init__(self, f, prefix: str):
        super().__init__(f)
        self.prefix = prefix

    def find_class(self, module, name):
        if self.prefix and self.prefix != OWN and (module == self.prefix or module.startswith(self.prefix + ".")):
            module = OWN + module[len(self.prefix):]
        return super().find_class(module, name)


def _dumps(obj) -> bytes:
    return pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)


def _loads(data: bytes, prefix: str):
    return _Unpickler(io.BytesIO(data), prefix).load()


def _send_bytes(stream, data: bytes) -> None:
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


def _recv_bytes(stream) -> bytes:
    tag, size = _HEAD.unpack(_read(stream, _HEAD.size))
    if tag != _MSG:
        raise RuntimeError("a weld helper sent something unexpected")
    return _read(stream, size)


def _function(name: str):
    """``"weld_cad.job_contacts"`` -> the function of that module in this package."""
    import importlib
    mod, fn = name.rsplit(".", 1)
    return getattr(importlib.import_module(f"{OWN}.{mod}"), fn)


# ---- in a helper ---------------------------------------------------------------------------------------------------

def helper_main(parent_pid: int, prefix: str) -> int:
    """Helper loop: messages in on stdin, answers out on stdout, until stdin closes."""
    _lp._no_crash_dialog()
    _lp._exit_with_parent(parent_pid)
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
    import numpy  # noqa: F401  (loaded before "ready": the first job does not pay for it)
    from . import weld_cad, welds  # noqa: F401
    _send_bytes(out, _dumps(("ready", os.getpid())))
    while True:
        try:
            data = _recv_bytes(inp)
        except EOFError:
            return 0
        try:
            msg = _loads(data, prefix)
        except Exception as exc:          # a message this helper cannot read: it says so and stops (its jobs go
            _send_bytes(out, _dumps(("broken", f"{type(exc).__name__}: {exc}")))   # to the master)
            return 1
        kind = msg[0]
        try:
            if kind == "share":
                _SHARED[msg[1]] = msg[2]
            elif kind == "job":
                _i, fn, args = msg[1], msg[2], msg[3]
                _send_bytes(out, _dumps(("done", _i, _function(fn)(_SHARED, *args))))
            else:
                _send_bytes(out, _dumps(("error", None, f"unknown message {kind!r}")))
        except Exception as exc:          # the master works this job out itself
            _send_bytes(out, _dumps(("error", msg[1] if kind == "job" else None, f"{type(exc).__name__}: {exc}")))


# ---- in the master -------------------------------------------------------------------------------------------------

class Pool:
    """Up to ``n`` helper processes, started when ``map`` first has enough jobs. ``n=0``: the master alone (the same
    answers). Use as ``with Pool() as pool:``.

    Nothing the master does waits on a helper without a time limit: every helper has a writer thread with its own
    outgoing queue (a big job never blocks the master on a full pipe – about 4 KB on Windows), one queue gathers every
    helper's answers, each job carries its ``map`` call's number (an answer from an earlier call that ended in an error
    is ignored), and a job a helper has not answered ``ANSWER_TIMEOUT`` after it was sent goes to the master."""

    def __init__(self, n: int | None = None, python: str | None = None, min_jobs: int | None = None):
        self.n = default_helpers() if n is None else max(0, min(int(n), MAX_HELPERS))
        self.python = python
        self.min_jobs = MIN_JOBS if min_jobs is None else min_jobs
        self.procs: list = []
        self.started = False
        self.shared: dict = {}             # name -> object (sent to helpers that come up later too)
        self.local: dict = {}              # what the master's own jobs read: ``shared`` + their caches (never sent)
        self.stats = {"helpers": 0, "jobs": 0, "by_helpers": 0, "start_s": 0.0, "errors": []}
        self._job = None
        self._job_close = None
        self._answers: queue.Queue = queue.Queue()     # (pid, message) from every helper
        self._out: dict = {}               # pid -> outgoing queue of bytes (None: stop the writer)
        self._calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    # -- helpers -------------------------------------------------------------------------------------------------
    def _start(self, want: int) -> None:
        if want <= 0:
            return
        self.started = True
        t0 = time.perf_counter()
        kwargs: dict = {}
        assign = None
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000 | 0x00004000   # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
            try:
                self._job, assign, self._job_close = _lp._kill_on_close_job()
            except Exception:
                assign = None                  # the helpers still stop by themselves, a bit later
        env = dict(os.environ)
        for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
            env.pop(var, None)                 # another program's Python settings must not leak in (as runner.py)
        env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
        kwargs["env"] = env
        cmd = [self.python or _lp.python_executable(), "-s", os.path.abspath(__file__), "--helper", str(os.getpid()),
               OWN]
        procs = []
        for _ in range(want):
            try:
                proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, **kwargs)
            except OSError as exc:
                self.stats["errors"].append(f"start: {exc}")
                break
            if assign is not None:
                try:
                    assign(proc)
                except Exception:
                    pass
            procs.append(proc)
            self._out[proc.pid] = q = queue.Queue()
            threading.Thread(target=self._reader, args=(proc, self._answers), daemon=True).start()
            threading.Thread(target=self._writer, args=(proc, q, self._answers), daemon=True).start()
        # every helper says it is ready (NumPy and the welds' code loaded) – one deadline for all of them
        waiting = {p.pid: p for p in procs}
        end = time.monotonic() + START_TIMEOUT
        while waiting and time.monotonic() < end:
            try:
                pid, msg = self._answers.get(timeout=max(0.05, end - time.monotonic()))
            except queue.Empty:
                break
            p = waiting.pop(pid, None)
            if p is None:
                continue
            if isinstance(msg, tuple) and msg[0] == "ready":
                self.procs.append(p)
            else:
                self.stats["errors"].append(f"start: {msg!r}")
                self._kill(p)
        for p in waiting.values():
            self.stats["errors"].append("start: no answer")
            self._kill(p)
        for name, obj in self.shared.items():
            self._share_to(name, obj)
        self.stats["helpers"] = len(self.procs)
        self.stats["start_s"] = time.perf_counter() - t0

    @staticmethod
    def _reader(proc, answers):
        while True:
            try:
                msg = _loads(_recv_bytes(proc.stdout), "core")   # a helper's package is "core"
            except BaseException as exc:      # noqa: BLE001 – end of the stream or a broken message
                answers.put((proc.pid, exc))
                return
            answers.put((proc.pid, msg))

    @staticmethod
    def _writer(proc, q, answers):
        """Sends a helper its messages in order; a broken pipe is said as an answer (the helper is lost)."""
        while True:
            data = q.get()
            if data is None:
                return
            try:
                _send_bytes(proc.stdin, data)
            except BaseException as exc:      # noqa: BLE001
                answers.put((proc.pid, exc))
                return

    def _post(self, p, data: bytes) -> None:
        self._out[p.pid].put(data)

    def _drop_helper(self, p) -> None:
        if p in self.procs:
            self.procs.remove(p)
        q = self._out.get(p.pid)
        if q is not None:
            q.put(None)
        self._kill(p)

    def _share_to(self, name, obj) -> None:
        """``obj`` to every helper (no answer awaited: a helper reads its messages in order, so a later job sees it).
        Something that cannot be pickled stays the master's: its helpers are not used any more."""
        try:
            data = _dumps(("share", name, obj))
        except Exception as exc:
            self.stats["errors"].append(f"share {name}: {exc}")
            for p in list(self.procs):
                self._drop_helper(p)
            return
        for p in self.procs:
            self._post(p, data)

    def share(self, name: str, obj) -> None:
        """Hand ``obj`` to every helper once (a job reads it as ``shared[name]``); the master's jobs get it too."""
        self.shared[name] = obj
        self.local[name] = obj
        if self.procs:
            self._share_to(name, obj)

    # -- work ----------------------------------------------------------------------------------------------------
    def map(self, fn: str, jobs: list) -> list:
        """``[function(shared, *args) for args in jobs]`` (``fn`` = "module.function" of this package), shared out
        over the helpers and the master, answers in the order of ``jobs``."""
        jobs = list(jobs)
        out: list = [None] * len(jobs)
        if not jobs:
            return out
        if not self.started and len(jobs) >= self.min_jobs:
            self._start(min(self.n, max(1, len(jobs) // 4)))
        f = _function(fn)
        self.stats["jobs"] += len(jobs)
        if not self.procs:
            return [f(self.local, *a) for a in jobs]
        self._calls += 1
        call = self._calls
        todo = list(range(len(jobs)))[::-1]            # popped from the end: in order
        sent: dict = {p.pid: {} for p in self.procs}   # pid -> {job number: when sent}
        by_pid = {p.pid: p for p in self.procs}
        done = [False] * len(jobs)
        mine: list = []                                # jobs a helper failed or lost, or not sendable: the master's

        def lost(p) -> None:
            mine.extend(sent.get(p.pid, {}))
            sent[p.pid] = {}
            self._drop_helper(p)

        def feed(p) -> None:
            while todo and p in self.procs and len(sent[p.pid]) < 2:   # two jobs each: no idle round trip
                i = todo.pop()
                try:
                    data = _dumps(("job", (call, i), fn, jobs[i]))
                except Exception as exc:              # a job that cannot be pickled: the master's
                    self.stats["errors"].append(f"job {i}: {exc}")
                    mine.append(i)
                    continue
                self._post(p, data)
                sent[p.pid][i] = time.monotonic()

        def take(pid, msg) -> None:
            p = by_pid.get(pid)
            if p is None or p not in self.procs:
                return
            if isinstance(msg, tuple) and msg[0] in ("done", "error") and isinstance(msg[1], tuple):
                c, i = msg[1]
                if c != call or i not in sent[pid]:
                    return                            # an answer of an earlier call: ignored
                del sent[pid][i]
                if msg[0] == "done":
                    if not done[i]:
                        out[i], done[i] = msg[2], True
                        self.stats["by_helpers"] += 1
                else:
                    self.stats["errors"].append(msg[2])
                    mine.append(i)
            elif isinstance(msg, tuple) and msg[0] in ("ok", "ready"):
                return
            else:                                     # stopped, a broken pipe or message
                self.stats["errors"].append(f"helper: {msg!r}")
                lost(p)

        def overdue() -> None:
            now = time.monotonic()
            for p in list(self.procs):
                if sent[p.pid] and now - min(sent[p.pid].values()) > ANSWER_TIMEOUT:
                    self.stats["errors"].append("a helper hangs")
                    lost(p)

        for p in list(self.procs):
            feed(p)
        while not all(done):
            while True:                                # the answers that are in
                try:
                    pid, msg = self._answers.get_nowait()
                except queue.Empty:
                    break
                take(pid, msg)
            overdue()
            for p in list(self.procs):
                feed(p)
            if mine or todo:                           # the master works one job itself
                i = mine.pop() if mine else todo.pop()
                if not done[i]:
                    out[i], done[i] = f(self.local, *jobs[i]), True
                continue
            if any(sent[p.pid] for p in self.procs):   # nothing left for the master: wait for an answer
                try:
                    pid, msg = self._answers.get(timeout=1.0)
                except queue.Empty:
                    continue
                take(pid, msg)
            else:
                mine.extend(i for i, d in enumerate(done) if not d)   # (only after a helper was lost)
        return out

    # -- end -----------------------------------------------------------------------------------------------------
    @staticmethod
    def _kill(p):
        try:
            p.kill()
            p.wait(timeout=5.0)
        except Exception:
            pass
        for stream in (p.stdin, p.stdout):
            try:
                stream.close()
            except Exception:
                pass

    def close(self) -> None:
        for p in self.procs:
            self._out[p.pid].put(None)               # the writer stops ...
            try:
                p.stdin.close()                     # ... and the helper's loop ends at EOF
            except Exception:
                pass
        end = time.time() + 3.0
        for p in self.procs:
            try:
                p.wait(timeout=max(0.1, end - time.time()))
            except Exception:
                pass
            self._kill(p)
        self.procs = []
        self.started = False
        if self._job_close is not None:
            try:
                self._job_close()
            except Exception:
                pass
            self._job_close = None


def _test_job(shared: dict, i: int, *extra) -> int:
    """A job for the tests (``tests/test_weld_pool.py``): fails in a helper for an odd i, never in the master; with
    ``extra`` = ("sleep", s, …) a helper sleeps s seconds on job 0; ("raise",) the master raises on any job."""
    helper = OWN == "core"
    if extra and extra[0] == "sleep":
        if helper and i == 0:
            time.sleep(extra[1])
        return i * i
    if extra and extra[0] == "raise":
        if not helper:
            raise ValueError("test")
        return i + 1000
    if i % 2 and helper:
        raise RuntimeError("test")
    return i * i
