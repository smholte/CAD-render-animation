"""The render kit's run control (task 0144): no Blender, plain Python.

- the owner's choices (graphics-card load, max temperature, quiet hours, what happens at the end) and the standard
  kept outside the kit (``%LOCALAPPDATA%\\Fresing Render\\site_kit.json``) so a newly downloaded kit keeps them;
- the expected wall time with those choices (``wall_seconds``; kit_window.ps1 has the same loop for its live label);
- the ``Pacer``: pauses between frames so the graphics card works about ``load`` % of the time (after a frame of t s
  it waits t * (100 / load - 1) s), a temperature guard (``nvidia-smi``, read-only, no admin rights), Pause / Resume /
  Stop from the status window (``output/control.txt``) and ``output/status.json`` for that window;
- the ``RunState`` (``output/run_state.json``): which pictures and clips of a run are finished, so a run that stopped
  (PC restarted, window closed, Stop) can be continued.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

STANDARD_FILE = "site_kit.json"
DEFAULT_STANDARD = {
    "load": 100,                  # % of the time the graphics card renders (40 … 100)
    "max_temp": 0,                # °C; 0 = no temperature guard (else 70 … 85)
    "quiet_on": False,            # quiet hours: their own load and max temperature
    "quiet_start": "22:00",
    "quiet_end": "07:00",
    "quiet_load": 60,
    "quiet_max_temp": 70,
    "when_done": "nothing",       # nothing | sleep | shutdown
}
WHEN_DONE = ("nothing", "sleep", "shutdown")
LOAD_MIN, LOAD_MAX = 40, 100
TEMP_MIN, TEMP_MAX = 70, 85
COOL_BY = 3.0                     # the guard waits until this far below the max (no on/off at every frame)
GPU_READ_EVERY = 10.0             # s between two nvidia-smi reads
STEP = 300.0                      # s: the time step of the expected-time loop (kit_window.ps1 uses the same)
CONTROL = "control.txt"
STATUS = "status.json"
STATE = "run_state.json"
STOPPED_CODE = 4                  # the .bat: "Stopped – double-click again to continue"


class Stopped(Exception):
    """The owner pressed Stop in the status window."""


# ---------------------------------------------------------------------------
# choices and the standard
# ---------------------------------------------------------------------------

def standard_path() -> str:
    """Where the standard choices live: next to the app's own folder, never inside the kit (a new kit keeps them).
    ``FRESING_KIT_STANDARD`` overrides it (tests)."""
    if os.environ.get("FRESING_KIT_STANDARD"):
        return os.environ["FRESING_KIT_STANDARD"]
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "Fresing Render", STANDARD_FILE)


def _clock_ok(text) -> bool:
    try:
        h, m = (int(x) for x in str(text).strip().split(":"))
    except ValueError:
        return False
    return 0 <= h < 24 and 0 <= m < 60


def clean(raw: dict | None) -> dict:
    """Any choices dict (a file written by hand, an older kit) -> valid values; unknown keys are kept."""
    out = dict(DEFAULT_STANDARD)
    raw = raw if isinstance(raw, dict) else {}
    out.update({k: v for k, v in raw.items() if k not in DEFAULT_STANDARD})

    def num(key, lo, hi, zero_ok=False):
        try:
            v = int(round(float(raw.get(key, DEFAULT_STANDARD[key]))))
        except (TypeError, ValueError):
            return DEFAULT_STANDARD[key]
        if zero_ok and v <= 0:
            return 0
        return min(hi, max(lo, v))

    out["load"] = num("load", LOAD_MIN, LOAD_MAX)
    out["max_temp"] = num("max_temp", TEMP_MIN, TEMP_MAX, zero_ok=True)
    out["quiet_load"] = num("quiet_load", LOAD_MIN, LOAD_MAX)
    out["quiet_max_temp"] = num("quiet_max_temp", TEMP_MIN, TEMP_MAX, zero_ok=True)
    out["quiet_on"] = bool(raw.get("quiet_on", False)) and str(raw.get("quiet_on")).lower() not in ("false", "0")
    for key in ("quiet_start", "quiet_end"):
        out[key] = str(raw.get(key, DEFAULT_STANDARD[key])).strip()
        if not _clock_ok(out[key]):
            out[key] = DEFAULT_STANDARD[key]
        h, m = (int(x) for x in out[key].split(":"))
        out[key] = f"{h:02d}:{m:02d}"
    wd = str(raw.get("when_done", "nothing")).strip().lower().replace(" ", "").replace("_", "")
    out["when_done"] = {"shutdown": "shutdown", "sleep": "sleep"}.get(wd, "nothing")
    return out


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8-sig") as fh:          # PowerShell may write a BOM
            return json.load(fh)
    except (OSError, ValueError):
        return None


def load_standard(path: str | None = None) -> dict:
    return clean(_read_json(path or standard_path()))


def save_standard(choices: dict, path: str | None = None) -> str:
    path = path or standard_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    keep = {k: clean(choices)[k] for k in DEFAULT_STANDARD}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(keep, fh, indent=1)
    return path


def load_choices(path: str = "") -> dict:
    """The window's answer (``--choices=<file>``) or, without one (the console fallback), the saved standard."""
    raw = _read_json(path) if path else None
    if raw is None:
        return load_standard()
    return clean(raw)


# ---------------------------------------------------------------------------
# quiet hours and the expected time
# ---------------------------------------------------------------------------

def _minutes(clock: str) -> int:
    h, m = (int(x) for x in clock.split(":"))
    return h * 60 + m


def in_quiet(choices: dict, epoch: float) -> bool:
    if not choices.get("quiet_on"):
        return False
    lt = time.localtime(epoch)
    now = lt.tm_hour * 60 + lt.tm_min
    a, b = _minutes(choices["quiet_start"]), _minutes(choices["quiet_end"])
    if a == b:
        return False
    return a <= now < b if a < b else (now >= a or now < b)        # 22:00–07:00 goes over midnight


def limits_at(choices: dict, epoch: float) -> tuple[int, int]:
    """(load %, max °C or 0) that apply at ``epoch``."""
    if in_quiet(choices, epoch):
        return choices["quiet_load"], choices["quiet_max_temp"]
    return choices["load"], choices["max_temp"]


def wall_seconds(gpu_s: float, cpu_s: float, start: float, choices: dict) -> float:
    """Wall time of ``gpu_s`` seconds of graphics-card work (frames, stills) and ``cpu_s`` of other work (imports,
    projects, video encoding) started at ``start``: in steps of STEP seconds, each step does work at the speed of
    the load that applies then (pauses stretch a GPU second to 100 / load). The temperature guard's waits are not
    counted (they depend on the room). kit_window.ps1 ``Get-WallSeconds`` is the same loop."""
    total = gpu_s + cpu_s
    if total <= 0:
        return 0.0
    gshare = gpu_s / total
    left, t = total, 0.0
    for _ in range(100000):
        load = limits_at(choices, start + t)[0]
        stretch = (1.0 - gshare) + gshare * 100.0 / load        # wall seconds per second of work
        work = STEP / stretch
        if work >= left:
            return t + left * stretch
        left -= work
        t += STEP
    return t


def say_time(seconds: float) -> str:
    m = int(round(seconds / 60.0))
    return f"{m // 60} h {m % 60:02d} min" if m >= 60 else f"{max(1, m)} min"


# ---------------------------------------------------------------------------
# the graphics card's temperature (read-only, no admin rights)
# ---------------------------------------------------------------------------

def read_gpu() -> dict | None:
    """{'temp': °C, 'util': %, 'power': W} of the first NVIDIA card, or None (no nvidia-smi, no card)."""
    flags = 0x08000000 if sys.platform == "win32" else 0          # CREATE_NO_WINDOW: no console popping up
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=temperature.gpu,utilization.gpu,power.draw",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10,
                             creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0 or not res.stdout.strip():
        return None
    return parse_gpu(res.stdout)


def parse_gpu(text: str) -> dict | None:
    line = text.strip().splitlines()[0]
    vals = [v.strip() for v in line.split(",")]

    def num(i):
        try:
            return float(vals[i])
        except (IndexError, ValueError):
            return None                          # "[N/A]" (power on some cards)
    if num(0) is None:
        return None
    return {"temp": num(0), "util": num(1), "power": num(2)}


# ---------------------------------------------------------------------------
# the pacer
# ---------------------------------------------------------------------------

class Pacer:
    """Called around every frame of the run (stills, clip frames). Injected ``clock``, ``sleep`` and ``gpu`` make it
    testable with a fake renderer."""

    def __init__(self, choices: dict, out: str = "", log=print, clock=time.time, sleep=time.sleep, gpu=read_gpu):
        self.c = clean(choices)
        self.out = out
        self.log = log
        self.clock, self.sleep, self.gpu = clock, sleep, gpu
        self.waited = 0.0               # s of duty-cycle pauses
        self.cooled = 0.0               # s waited for the temperature
        self.paused_s = 0.0
        self.frames = 0
        self._mark = None               # end of the last pacing (start of the frame being rendered)
        self._gpu_at, self._gpu_val = -1e18, None
        self._gpu_warned = False
        self.status = {"state": "starting", "clip": 0.0, "pid": os.getpid()}   # the status window checks it lives
        self.progress_fn = None         # () -> (share done 0 … 1, expected end epoch): set by the run
        if out:
            os.makedirs(out, exist_ok=True)
            self._write_control("run")

    # --- control file and status ---
    def _write_control(self, word: str) -> None:
        try:
            with open(os.path.join(self.out, CONTROL), "w", encoding="ascii") as fh:
                fh.write(word + "\n")
        except OSError:
            pass

    def control(self) -> str:
        if not self.out:
            return "run"
        try:
            with open(os.path.join(self.out, CONTROL), encoding="utf-8-sig", errors="replace") as fh:
                word = fh.read().strip().lower()
        except OSError:
            return "run"
        return word if word in ("pause", "stop") else "run"

    def show(self, **kw) -> None:
        """Update status.json (the status window reads it every 2 s)."""
        self.status.update(kw)
        if "step" in kw and "clip" not in kw:
            self.status["clip"] = 0.0
        if self.progress_fn is not None:
            try:
                share, end = self.progress_fn()
                self.status["pct"] = round(100.0 * min(1.0, max(0.0, share)), 1)
                self.status["end"] = time.strftime("%H:%M", time.localtime(end)) if end else ""
            except Exception:                    # the status must never stop a render
                pass
        self.status.setdefault("load", limits_at(self.c, self.clock())[0])
        if not self.out:
            return
        self.status["updated"] = self.clock()
        tmp = os.path.join(self.out, STATUS + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.status, fh, ensure_ascii=True)
            os.replace(tmp, os.path.join(self.out, STATUS))
        except OSError:
            pass

    def temperature(self, force: bool = False) -> float | None:
        now = self.clock()
        if force or now - self._gpu_at >= GPU_READ_EVERY:
            self._gpu_at = now
            self._gpu_val = self.gpu()
            if self._gpu_val:
                self.status.update(temp=self._gpu_val["temp"], util=self._gpu_val["util"])
        return self._gpu_val["temp"] if self._gpu_val else None

    # --- waiting that stays responsive ---
    def _nap(self, seconds: float, why: str) -> float:
        """Sleep ``seconds`` in slices of at most 1 s, honouring Pause and Stop. Returns the time spent."""
        t0 = self.clock()
        end = t0 + seconds
        while True:
            self.checkpoint()
            now = self.clock()
            if now >= end:
                return now - t0
            self.sleep(min(1.0, end - now))

    def checkpoint(self) -> None:
        """Pause (waits while the status window says pause) and Stop (raises Stopped)."""
        word = self.control()
        if word == "stop":
            raise Stopped()
        if word == "pause":
            before = self.status.get("state")
            self.show(state="paused")
            self.log("  paused (status window) – press Resume to go on")
            t0 = self.clock()
            while True:
                self.sleep(1.0)
                word = self.control()
                if word == "stop":
                    raise Stopped()
                if word != "pause":
                    break
            self.paused_s += self.clock() - t0
            self.log("  going on")
            self.show(state=before or "running")

    def guard(self) -> None:
        """Before a frame: wait while the card is at or above the max temperature of this hour."""
        self.checkpoint()
        max_t = limits_at(self.c, self.clock())[1]
        if not max_t:
            return
        temp = self.temperature()
        if temp is None:
            if not self._gpu_warned:
                self._gpu_warned = True
                self.log("  NOTE: the graphics card's temperature cannot be read (nvidia-smi): no temperature guard")
            return
        if temp < max_t:
            return
        self.log(f"  graphics card at {temp:.0f} °C (max {max_t} °C): waiting until it is {max_t - COOL_BY:.0f} °C")
        before = self.status.get("state")
        t0 = self.clock()
        while temp is not None and temp > max_t - COOL_BY:
            self.show(state="cooling")
            self._nap(10.0, "cooling")
            temp = self.temperature(force=True)
            max_t = limits_at(self.c, self.clock())[1]
            if not max_t:
                break
        took = self.clock() - t0
        self.cooled += took
        self.log(f"  cooled down in {took:.0f} s")
        self.show(state=before or "running")

    def after_frame(self, took: float) -> float:
        """A frame (still or clip frame) took ``took`` s of rendering: pause so the card works ``load`` % of the
        time. Returns the pause."""
        self.frames += 1
        load = limits_at(self.c, self.clock())[0]
        if load != self.status.get("load"):
            self.show(load=load)
        wait = max(0.0, took) * (100.0 / load - 1.0)
        if wait > 0:
            self.waited += self._nap(wait, "pause")
        return wait

    # --- the two ways frames are made ---
    def before_still(self) -> None:
        self.guard()
        self._mark = self.clock()

    def after_still(self) -> float:
        took = self.clock() - (self._mark if self._mark is not None else self.clock())
        self._mark = None
        return self.after_frame(took)

    def clip_progress(self, pct: float, msg: str) -> None:
        """The queue's progress (0 … 95 % for the frames): the status window's line."""
        self.show(step=f"Video: {msg}", clip=min(1.0, max(0.0, pct / 95.0)))

    def start_clip(self) -> None:
        """Before the app's queue renders a clip: its set-up is not a frame."""
        self._mark = None

    def frame_hook(self) -> bool:
        """The queue's ``should_stop``: called before every frame. Paces the frame that just ended (from the last
        call to now), guards the temperature, honours Pause; Stop raises Stopped (the queue never sees True)."""
        if self._mark is not None:
            self.after_frame(self.clock() - self._mark)
        self.guard()
        self._mark = self.clock()
        return False

    def end_clip(self) -> None:
        """After the queue's last frame (no call follows it): pace that one too."""
        if self._mark is not None:
            self.after_frame(self.clock() - self._mark)
        self._mark = None


# ---------------------------------------------------------------------------
# the run's state: continue a run that stopped
# ---------------------------------------------------------------------------

class RunState:
    """output/run_state.json: {"started": "2026-11-15 23:10", "models": [ids], "units": {id: [unit keys]},
    "done": {id: [unit keys]}, "items": {id: [items]}, "complete": [ids], "finished": bool, "choices": {...}}.
    A unit is one still ("still:<view>") or one model's clip ("video")."""

    def __init__(self, out: str, data: dict | None = None):
        self.out = out
        self.data = data or {}

    @property
    def path(self) -> str:
        return os.path.join(self.out, STATE)

    @classmethod
    def load(cls, out: str) -> "RunState | None":
        data = _read_json(os.path.join(out, STATE))
        if not isinstance(data, dict) or not isinstance(data.get("models"), list):
            return None
        for key in ("units", "done", "items"):
            if not isinstance(data.get(key), dict):
                data[key] = {}
        if not isinstance(data.get("complete"), list):
            data["complete"] = []
        return cls(out, data)

    @classmethod
    def new(cls, out: str, models: list[dict], choices: dict, when: float | None = None) -> "RunState":
        when = time.time() if when is None else when
        st = cls(out, {"started": time.strftime("%Y-%m-%d %H:%M", time.localtime(when)), "models": [m["id"] for m in models],
                       "units": {m["id"]: units_of(m) for m in models}, "done": {}, "items": {}, "complete": [],
                       "finished": False, "choices": clean(choices)})
        st.save()
        return st

    def save(self) -> None:
        os.makedirs(self.out, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=1, ensure_ascii=True)
        os.replace(tmp, self.path)

    def is_done(self, model: str, unit: str) -> bool:
        return unit in self.data["done"].get(model, [])

    def record(self, model: str, unit: str, item: dict | None) -> None:
        done = self.data["done"].setdefault(model, [])
        if unit not in done:
            done.append(unit)
        items = self.data["items"].setdefault(model, [])
        if item is not None:
            items[:] = [i for i in items if i.get("file") != item.get("file")] + [item]
        self.save()

    def complete(self, model: str) -> None:
        if model not in self.data["complete"]:
            self.data["complete"].append(model)
        self.save()

    def finish(self) -> None:
        self.data["finished"] = True
        self.save()

    def counts(self) -> tuple[int, int]:
        """(finished pictures and clips, all of the run)."""
        total = sum(len(u) for u in self.data["units"].values())
        done = sum(len(set(d) & set(self.data["units"].get(m, []))) for m, d in self.data["done"].items())
        return done, total

    def all_items(self) -> list[dict]:
        return [it for m in self.data["models"] for it in self.data["items"].get(m, [])]


def units_of(m: dict) -> list[str]:
    return [f"still:{v.lower()}" for v in m["views"]] + ([] if m.get("video", "none") == "none" else ["video"])


def resume_info(out: str) -> dict | None:
    """The run that can be continued: {'started', 'done', 'total', 'models'} – None when there is none (no run, or it
    finished)."""
    st = RunState.load(out)
    if st is None or st.data.get("finished"):
        return None
    done, total = st.counts()
    if total == 0 or done >= total and len(st.data["complete"]) >= len(st.data["models"]):
        return None
    return {"started": st.data.get("started", "?"), "done": done, "total": total, "models": list(st.data["models"])}


def resume_text(info: dict) -> str:
    return f"Continue the run of {info['started']} ({info['done']} of {info['total']} done)"
