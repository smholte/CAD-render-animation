"""What the app shows at its start (task 0199): the welcome for a new user and What's new after an update. No Blender.

The state is one small file in Blender's settings folder (``<config>/fresing_start.json``), so it survives updates and
belongs to the settings folder, as the owner's preferences do::

    {"last_run": "0.2.153",           the newest version started in this settings folder
     "welcome": {"later": 1, "never": false, "done": false},     later = starts that showed it
     "whats_new": {"from": "0.2.150", "to": "0.2.153", "opened": false},
     "setup": {"state": "done", "step": "done", "work": ["cnc"], "version": "0.2.233", "by": ""}}

``decide`` says what a start shows: ``"setup"`` (task 0276: the first-start set-up – no version ever ran here, at
most ``WELCOME_STARTS`` starts, until the user finishes or skips it; before 0276 this was the welcome),
``"whats_new"`` (the version went up since the last start; never after a downgrade or the same version again), or
``""``. ``setup.state`` is "" (not finished), "done" or "skipped"; ``by`` = "it" when a company's set-up file skipped
it; ``step`` = where the user left it; ``work`` = the ticks of its step 2 (they stay here, on this PC).
"""

from __future__ import annotations

import json
import os
import re

FILE_NAME = "fresing_start.json"
WELCOME_STARTS = 3                  # "Later" asks again at the next start, at most three starts
WHATS_NEW_LINES = 8                 # the popup's list of new functions: at most this many lines
BETTER_LINES = 5                    # ... and its second list, "Better since": at most this many lines
NO_POPUP_ENV = "FRESING_NO_WELCOME"         # set by the tests, the kit, the PC check: nothing pops up
TEST_ENV = "FRESING_WELCOME_TEST"           # the welcome's own real-app test: show it although events are simulated


def vtuple(v: str) -> tuple:
    """'0.2.153' -> (0, 2, 153); '' or junk -> ()."""
    if not isinstance(v, str) or not re.fullmatch(r"\d+(\.\d+)*", v.strip() or "x"):
        return ()
    return tuple(int(x) for x in v.strip().split("."))


def newer(a: str, b: str) -> bool:
    """Is version ``a`` newer than ``b``? A version is newer than nothing."""
    return bool(vtuple(a)) and vtuple(a) > vtuple(b)


def _int(v, default: int = 0) -> int:
    """A whole number from whatever a damaged file held (a string, null, 1e400 …): the default when it is none."""
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        return default
    try:
        return max(0, min(10 ** 6, int(float(v))))
    except (ValueError, OverflowError):
        return default


def _version(v) -> str:
    """A version string like '0.2.153', else '' (a junk version means: no version)."""
    return v.strip() if isinstance(v, str) and vtuple(v) else ""


SETUP_STATES = ("", "done", "skipped")


def fresh_setup() -> dict:
    return {"state": "", "step": "", "work": [], "version": "", "by": ""}


def fresh() -> dict:
    return {"last_run": "", "welcome": {"later": 0, "never": False, "done": False},
            "whats_new": {"from": "", "to": "", "opened": True}, "setup": fresh_setup()}


def load(path: str) -> dict:
    """The state in ``path``; a missing or broken file gives a fresh state (a new settings folder)."""
    out = fresh()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    out["last_run"] = _version(data.get("last_run"))
    w, wn = data.get("welcome"), data.get("whats_new")
    if isinstance(w, dict):                  # task 0236: every field is cleaned, a damaged file never breaks a start
        out["welcome"].update(later=_int(w.get("later")), never=w.get("never") is True, done=w.get("done") is True)
    if isinstance(wn, dict):
        out["whats_new"].update({"from": _version(wn.get("from")), "to": _version(wn.get("to")),
                                 "opened": wn.get("opened") is not False})
    su = data.get("setup")
    if isinstance(su, dict):                 # task 0276
        work = su.get("work")
        out["setup"].update(state=su.get("state") if su.get("state") in SETUP_STATES else "",
                            step=su.get("step") if isinstance(su.get("step"), str) else "",
                            work=[w for w in work if isinstance(w, str)][:20] if isinstance(work, list) else [],
                            version=_version(su.get("version")), by="it" if su.get("by") == "it" else "")
    return out


def save(path: str, state: dict) -> None:
    """Write the state (a temporary file first, so a crash never leaves half a file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    os.replace(tmp, path)


def decide(state: dict, version: str) -> str:
    """What this start of ``version`` shows: "setup", "whats_new" or "". Does not change the state."""
    last = state.get("last_run", "")
    w = state.get("welcome", {})
    if not last:
        if w.get("never") or w.get("done") or _int(w.get("later")) >= WELCOME_STARTS:
            return ""
        if (state.get("setup") or {}).get("state") in ("done", "skipped"):
            return ""
        return "setup"
    if newer(version, last):
        return "whats_new"
    return ""


def started(state: dict, version: str, shows: str) -> dict:
    """The state after a start of ``version`` that showed ``shows`` (the result of ``decide``).

    The welcome keeps ``last_run`` empty until the user answers it (so a user who closes the app at once is welcomed
    again); What's new remembers the versions and stays in the Fresing menu until it is opened once."""
    state = json.loads(json.dumps(state))
    if shows in ("setup", "welcome"):     # every start that shows it counts: at most WELCOME_STARTS starts
        w = state["welcome"]
        w["later"] = _int(w.get("later")) + 1
        if w["later"] >= WELCOME_STARTS:
            state["last_run"] = version  # asked often enough: from now on updates bring What's new
        return state
    last = state.get("last_run", "")
    if shows == "whats_new":
        wn = state["whats_new"]
        if wn.get("opened", True) or not wn.get("from"):     # several updates without opening it: keep the oldest
            wn["from"] = last
        wn.update(to=version, opened=False)
    if newer(version, last) or not last:
        state["last_run"] = version
    return state


def answer_welcome(state: dict, version: str, choice: str) -> dict:
    """The user answered the welcome: "tour" (takes the tour), "later" or "never"."""
    state = json.loads(json.dumps(state))
    w = state["welcome"]
    if choice == "later":                # the start that showed it counted already (``started``)
        return state
    if choice == "never":
        w["never"] = True
    else:
        w["done"] = True
    if not state.get("last_run") or newer(version, state["last_run"]):
        state["last_run"] = version
    return state


def setup_finished(state: dict, version: str, how: str, step: str = "", work=None, by: str = "") -> dict:
    """The first-start set-up ended: ``how`` "done" (the user went through it), "skipped" (Skip set-up, or a company's
    set-up file said so: ``by`` "it") or "" (closed on the way: asked again at the next start, at most
    ``WELCOME_STARTS`` starts). From a finished set-up on, updates bring What's new."""
    state = json.loads(json.dumps(state))
    su = state.setdefault("setup", fresh_setup())
    if step:
        su["step"] = step
    if work is not None:
        su["work"] = list(work)
    if how in ("done", "skipped"):
        su.update(state=how, version=version, by="it" if by == "it" else "")
        state["welcome"]["done"] = True
        if not state.get("last_run") or newer(version, state["last_run"]):
            state["last_run"] = version
    return state


def opened_whats_new(state: dict) -> dict:
    state = json.loads(json.dumps(state))
    state["whats_new"]["opened"] = True
    return state


def whats_new_pending(state: dict) -> bool:
    """Is What's new waiting in the Fresing menu (shown at start, not opened yet)?"""
    wn = state.get("whats_new", {})
    return bool(wn.get("to")) and not wn.get("opened", True)


def title(since: str, now: str, between: list | None = None) -> str:
    """'What's new in 0.2.153', or 'What's new since 0.2.150' when versions were skipped (``between``: the released
    versions known, from changelog.json; without them a jump of more than one in the last number counts as skipped)."""
    a, b = vtuple(since), vtuple(now)
    if not a or not b:
        return f"What's new in {now}"
    if between is not None:
        skipped = [v for v in between if newer(v, since) and newer(now, v)]
    else:
        skipped = [1] if (a[:-1] == b[:-1] and b[-1] - a[-1] > 1) or a[:-1] != b[:-1] else []
    return f"What's new since {since}" if skipped else f"What's new in {now}"


def in_range(v: str, since: str, now: str) -> bool:
    """Did ``v`` come after ``since`` and no later than ``now``?"""
    return bool(vtuple(v)) and newer(v, since) and not newer(v, now)


def new_functions(functions, since: str, now: str, limit: int = WHATS_NEW_LINES) -> list:
    """[(Function, "new")] of the functions added after ``since`` (up to ``now``): the ones a user meets first
    (``headline=True``) before the others, each group newest first, at most ``limit``. A junk or empty ``since`` gives
    nothing (task 0236: never "all 137 functions")."""
    if not vtuple(since):
        return []
    rows = [f for f in (functions.values() if isinstance(functions, dict) else functions)
            if in_range(f.since, since, now)]
    rows.sort(key=lambda f: (not getattr(f, "headline", False), tuple(-x for x in vtuple(f.since))))
    return [(f, "new") for f in rows[:limit]]


def better_functions(functions, since: str, now: str, limit: int = BETTER_LINES) -> list:
    """[(Function, "improved")] of the functions that got visibly better after ``since`` (``changed=``) and are not
    new in the range, newest first, at most ``limit`` (task 0236: What's new's second list, "Better since")."""
    if not vtuple(since):
        return []
    rows = [f for f in (functions.values() if isinstance(functions, dict) else functions)
            if in_range(getattr(f, "changed", ""), since, now) and not in_range(f.since, since, now)]
    rows.sort(key=lambda f: tuple(-x for x in vtuple(f.changed)))
    return [(f, "improved") for f in rows[:limit]]


def count_new_functions(functions, since: str, now: str) -> int:
    return len(new_functions(functions, since, now, limit=10 ** 6))


def count_better_functions(functions, since: str, now: str) -> int:
    return len(better_functions(functions, since, now, limit=10 ** 6))


def mark(added: str, changed: str, since: str, now: str) -> str:
    """"new", "changed" or "" for a tour set or stop seen by a user who last ran ``since``."""
    if not since:
        return ""
    if in_range(added, since, now):
        return "new"
    if in_range(changed, since, now):
        return "changed"
    return ""
