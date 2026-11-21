"""The usage tracker in the app (task 0181): counting, the session, the personal hides, the favourites bar's jump.

``core/usage.py`` holds the rules; this module keeps the state in memory, writes it to ``<config>/fresing_usage.json``
(at most every ``SAVE_SECONDS`` while something changed, at a project save and when the app closes) and hooks in:

* **counting** – ``panels.install`` calls ``wrap(cls)`` for every ``fresing.*`` operator: its ``invoke`` (or, without
  one, its ``execute``) records one click before running. A button inside a button (an operator that calls another)
  counts once. The panel a button was clicked in comes with the click (``panels`` sets ``fr_panel`` on each panel's
  layout). Opening a panel (``fresing.panel_toggle``) counts for that panel;
* **active time** – a click, a panel opening, a change of the project (``depsgraph_update_post``) and a redraw of the
  favourites bar each mark "the user is here"; the time between two marks goes to the stage of the last used function
  unless it was longer than ``core.IDLE`` (2 min);
* **the session** – one app start; the favourites bar is sorted then, and never while the app runs;
* **personal hides** – a declutter answer "Hide" puts a panel's functions on the user's own list; ``workspaces``
  hides them on top of any workspace except Full access (``workspaces.PERSONAL``), never one the open project uses.

Nothing is counted in a background run (render queue, PC check, the kit), with ``FRESING_NO_USAGE``, or with simulated
events (real-app tests) unless ``FRESING_USAGE_TEST`` is set. No network: nothing here can send anything.
"""

from __future__ import annotations

import atexit
import datetime
import os
import time

import bpy
from bpy.app.handlers import persistent

from ..core import functions as F
from ..core import places
from ..core import usage as core

FILE_ENV = "FRESING_USAGE_FILE"          # tests: the usage file to use instead of the one in the settings folder
SAVE_SECONDS = 30.0
USED_SECONDS = 2.0                       # personal hides are looked at again at most this often (task 0236)
GO_SECONDS = 6.0                         # a favourite's button is pointed at this long

_S: dict = {"state": None, "path": "", "dirty": False, "note": "", "started": False, "prompt": "", "prompted": "",
            "go": "", "go_t": 0.0, "last_panel": "", "used_t": 0.0}
CLOCK = core.Clock()
_DEPTH = [0]
_BY_OP: dict = {}                        # operator id -> True when some function or rule names it (cheap skip)


# ---------------------------------------------------------------------------
# the state and its file
# ---------------------------------------------------------------------------

def path() -> str:
    return os.environ.get(FILE_ENV) or os.path.join(bpy.utils.user_resource("CONFIG"), core.FILE_NAME)


def state() -> dict:
    """The usage state (read from the file the first time)."""
    if _S["state"] is None or _S["path"] != path():
        _S["path"] = path()
        _S["state"], _S["note"] = core.load(_S["path"])
        if _S["note"]:
            print("Fresing Render (usage):", _S["note"])
    return _S["state"]


def save(force: bool = False) -> bool:
    if _S["state"] is None or not (force or _S["dirty"]):
        return False
    try:
        core.save(_S["path"] or path(), _S["state"])
    except OSError as exc:
        print("Fresing Render: could not save the usage file:", exc)
        return False
    _S["dirty"] = False
    return True


def changed() -> None:
    _S["dirty"] = True


def forget() -> None:
    """Read the file again next time (tests)."""
    _S.update(state=None, path="", dirty=False, note="", started=False, prompt="", prompted="", go="")
    CLOCK.last, CLOCK.stage = None, ""


def counting() -> bool:
    """Is this run counted? Not in the background, not with FRESING_NO_USAGE, not with simulated events (real-app
    tests) – unless FRESING_USAGE_TEST asks for it – and not when the user switched tracking off."""
    if os.environ.get(core.OFF_ENV):
        return False
    if not os.environ.get(core.TEST_ENV):
        if bpy.app.background or getattr(bpy.app, "use_event_simulate", False):
            return False
    return bool(state()["track"])


# ---------------------------------------------------------------------------
# counting
# ---------------------------------------------------------------------------

def _named(idname: str) -> bool:
    if not _BY_OP:
        for f in F.FUNCTIONS.values():
            if f.button:
                _BY_OP[f.button] = True
        for op in core.ALSO:
            _BY_OP[op] = True
        for op, _prop in core.BY_PROP:
            _BY_OP[op] = True
    return idname in _BY_OP


def _parts(context) -> int:
    scene = getattr(context, "scene", None)
    try:
        return sum(1 for ob in scene.objects if ob.type == "MESH") if scene is not None else 0
    except Exception:  # noqa: BLE001
        return 0


def record(idname: str, op=None, context=None) -> str:
    """One click on the button ``idname``: returns the function it counted for ('' = none)."""
    if idname in core.NOT_COUNTED or not counting():
        return ""
    s = state()
    fid = ""
    if _named(idname):
        props = {}
        for (bop, prop) in core.BY_PROP:
            if bop == idname and op is not None:
                props[prop] = getattr(op, prop, None)
        panel = str(getattr(context, "fr_panel", "") or "") if context is not None else ""
        _S["last_panel"] = panel
        fid = core.function_for(idname, panel, props)
    saved = 0.0
    if fid:
        f = F.FUNCTIONS.get(fid)
        if f is not None and f.manual_estimate:
            saved = core.estimate_seconds(fid, _parts(context) if f.manual_estimate[0] == "part" else 0)
    learned = core.count_click(s, idname, fid, saved, datetime.date.today().isoformat())
    if learned:
        _S["learned"] = True
    CLOCK.tick(s, stage=core.stage_of(fid) if fid else "")
    if fid and fid == _S["go"]:
        _end_go()
    changed()
    return fid


def panel_opened(name: str) -> None:
    if not counting():
        return
    s = state()
    core.count_panel(s, name)
    CLOCK.tick(s, stage=core.panel_stage(name))
    changed()


def activity() -> None:
    """A sign that the user is working (cheap: called at redraws and changes)."""
    s = _S["state"]
    if s is None or not s["track"]:
        return
    CLOCK.tick(s)
    _S["dirty"] = True if CLOCK.stage else _S["dirty"]


def _run(fn, idname: str, self, context, args):
    if _DEPTH[0]:
        return fn(self, context, *args)
    _DEPTH[0] += 1
    try:
        result = fn(self, context, *args)
    finally:
        _DEPTH[0] -= 1
    try:
        if "CANCELLED" not in (result or ()):
            record(idname, self, context)
    except Exception as exc:  # noqa: BLE001 - counting never breaks a button
        print("Fresing Render (usage):", exc)
    return result


def _wrap_call(fn, idname: str, invoke: bool):
    """Blender checks the number of arguments: invoke (self, context, event), execute (self, context)."""
    if invoke:
        def call(self, context, event):
            return _run(fn, idname, self, context, (event,))
    else:
        def call(self, context):
            return _run(fn, idname, self, context, ())
    call.__doc__ = fn.__doc__
    call._fr_usage = True
    return call


def wrap(cls) -> None:
    """Put the counting round an operator class (before it is registered; ``panels.install`` calls it)."""
    idname = getattr(cls, "bl_idname", "")
    if not idname.startswith("fresing.") or idname in core.NOT_COUNTED:
        return
    attr = "invoke" if "invoke" in _own_methods(cls) else "execute"
    fn = getattr(cls, attr, None)
    if fn is None or getattr(fn, "_fr_usage", False):
        return
    setattr(cls, attr, _wrap_call(fn, idname, attr == "invoke"))


def _own_methods(cls) -> set:
    out = set()
    for c in cls.__mro__:
        if c in (bpy.types.Operator, object):
            break
        out.update(k for k in ("invoke", "execute") if k in c.__dict__)
    return out


# ---------------------------------------------------------------------------
# the session, the bar
# ---------------------------------------------------------------------------

def start() -> None:
    """The app's start: a new session (while counted) and the bar sorted afresh."""
    if _S["started"]:
        return
    _S["started"] = True
    s = state()
    if counting():
        core.start_session(s, datetime.date.today().isoformat())
        _note_new_functions()
    else:
        s["bar"]["order"] = core.bar_order(s)
    save(force=counting())
    project_changed(getattr(bpy.context, "scene", None))


def _note_new_functions() -> None:
    """Task 0236: the functions What's new advertises after this update are not 'unused': the declutter question
    leaves their panels alone until ``threshold`` sessions have passed."""
    try:
        from ..core import start as start_core
        from . import welcome
        welcome.at_start()                       # idempotent: the start file knows this update before we ask
        wn = welcome.load().get("whats_new", {})
        if wn.get("to") == welcome.version() and wn.get("from"):
            rows = start_core.new_functions(F.FUNCTIONS, wn["from"], welcome.version(), 10 ** 6)
            core.note_new(state(), [f.id for f, _k in rows])
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render (usage): new functions not noted:", exc)


def bar(scene=None) -> list:
    """The favourites as fixed at this start: function ids the project's workspace shows."""
    s = state()
    if not s["bar"]["on"]:
        return []
    from . import workspaces
    out = []
    for fid in s["bar"]["order"]:
        f = F.FUNCTIONS.get(fid)
        if f is None:
            continue
        if scene is not None and not workspaces.shows(scene, fid):
            continue
        if f.panel not in F.MENUS and not hasattr(bpy.types, f.panel):
            continue
        out.append(fid)
    return out


def label(fid: str) -> str:
    """A favourite's short button text."""
    f = F.FUNCTIONS[fid]
    if f.short:                                  # task 0236: a label that fits the half-width button
        return f.short
    text = f.text or f.title
    for cut in (":", " (", ","):
        if cut in text:
            text = text.split(cut)[0]
    return text.rstrip("…").strip()


def go(context, fid: str) -> str:
    """A favourite clicked: a menu function runs; a side-panel function's section opens (its tab) down to its panel
    and the button is pointed at for a few seconds. Returns "run" or "shown"."""
    f = F.FUNCTIONS[fid]
    if f.panel in F.MENUS:
        area, _, name = f.button.partition(".")
        getattr(getattr(bpy.ops, area), name)("INVOKE_DEFAULT")
        return "run"
    from . import highlight, panels
    n = places.number_of(f.panel)
    wm = context.window_manager
    if n and hasattr(wm, "fresing_tab"):
        wm.fresing_tab = str(n)
    panels.open_to(f.panel)
    try:
        highlight.point_function(fid, open_panels=True)
        _S["go"], _S["go_t"] = fid, time.monotonic()
        if not bpy.app.timers.is_registered(_go_timer):
            bpy.app.timers.register(_go_timer, first_interval=GO_SECONDS)
    except Exception as exc:  # noqa: BLE001 - the jump worked; only the pointer failed
        print("Fresing Render (usage): no pointer:", exc)
    return "shown"


def _go_timer():
    if _S["go"] and time.monotonic() - _S["go_t"] >= GO_SECONDS - 0.05:
        _end_go()
        return None
    return GO_SECONDS if _S["go"] else None


def _end_go() -> None:
    if not _S["go"]:
        return
    _S["go"] = ""
    try:
        from . import highlight
        highlight.clear()
    except Exception:  # noqa: BLE001
        pass


def pin(fid: str, on: bool) -> None:
    core.pin(state(), fid, on)
    changed()
    save()


# ---------------------------------------------------------------------------
# personal hides and the declutter prompt
# ---------------------------------------------------------------------------

def _children() -> dict:
    out: dict = {}
    for name, (parent, _t) in places.PLACES.items():
        out.setdefault(parent, []).append(name)
    return out


def apply_personal(scene) -> tuple:
    """Hand the personal hides that apply to this project to ``workspaces`` (never one the project uses)."""
    from . import workspaces
    used = set(workspaces.used_functions(scene)) if scene is not None else set()
    hide = core.personal_hides(state(), used)
    if workspaces.PERSONAL["hide"] != hide:
        workspaces.PERSONAL["hide"] = hide
        from . import panels
        if scene is not None:
            panels.tab_check(scene)
        panels.redraw()
    return hide


def refresh_personal(scene, force: bool = False) -> None:
    """Task 0236: a panel the user hid shows again when the project starts using it (after Build, undo, a model
    update …). Looked at when the scene changes, at most every ``USED_SECONDS``, and only when something is hidden."""
    if scene is None or not state()["hidden"]:
        return
    now = time.monotonic()
    if not force and now - _S["used_t"] < USED_SECONDS:
        return
    _S["used_t"] = now
    apply_personal(scene)


def prompt() -> str:
    """The panel a declutter prompt asks about now ('' = none)."""
    return _S["prompt"]


def project_changed(scene) -> None:
    """A project opened (or the app started with one): the personal hides for it, and the session's one prompt –
    chosen once per session, dropped when this project uses that panel."""
    if scene is None or getattr(scene, "fresing", None) is None:
        return
    apply_personal(scene)
    from . import workspaces
    if _S["prompted"]:
        if _S["prompt"]:
            used = set(workspaces.used_functions(scene))
            if any(fid in used for fid in core.panel_functions(_S["prompt"])):
                _S["prompt"] = ""
        return
    if not counting():
        return
    s = state()
    hidden, shown = workspaces._state(scene)[0], workspaces._state(scene)[1]
    if shown is None:
        return
    cand = core.declutter_candidate(s, set(shown), set(workspaces.used_functions(scene)), set(hidden),
                                    children=_children(), titles=set(places.PLACES))
    if cand:
        _S["prompt"] = _S["prompted"] = cand


def answer(scene, choice: str) -> None:
    panel = _S["prompt"]
    if not panel:
        return
    core.answer_declutter(state(), panel, choice)
    _S["prompt"] = ""
    changed()
    save()
    if choice == "hide":
        apply_personal(scene)


def reset(scene) -> None:
    """Back to the workspace as it came: no personal hides, no pins."""
    core.reset(state())
    changed()
    save()
    apply_personal(scene)


def clear(with_list: bool = False) -> None:
    _S["state"] = core.clear(state(), with_list)
    CLOCK.last, CLOCK.stage = None, ""
    changed()
    save()


def panel_title(panel: str) -> str:
    return places.PLACES.get(panel, ("", panel.replace("FRESING_PT_", "").replace("_", " ").capitalize()))[1]


# ---------------------------------------------------------------------------
# handlers, timers
# ---------------------------------------------------------------------------

@persistent
def _on_load(_dummy=None):
    try:
        project_changed(bpy.context.scene)
    except Exception as exc:  # noqa: BLE001 - never break loading
        print("Fresing Render (usage):", exc)


@persistent
def _on_save(_dummy=None):
    from . import backups
    if backups.saving():                 # task 0246: an automatic backup
        return
    save()


@persistent
def _on_change(_scene=None, _depsgraph=None):
    activity()
    try:
        refresh_personal(_scene if getattr(_scene, "fresing", None) is not None else bpy.context.scene)
    except Exception as exc:  # noqa: BLE001 - never break a scene update
        print("Fresing Render (usage):", exc)


def _save_timer():
    save()
    return SAVE_SECONDS


def _start_timer():
    try:
        start()
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render (usage): not started:", exc)
    return None


_HANDLERS = (("load_post", _on_load), ("save_post", _on_save), ("depsgraph_update_post", _on_change))


def _at_exit():
    try:
        save()
    except Exception:  # noqa: BLE001
        pass


def register() -> None:
    from . import workspaces
    workspaces.PERSONAL["hide"] = ()
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)
    if not bpy.app.background:
        if not bpy.app.timers.is_registered(_start_timer):
            bpy.app.timers.register(_start_timer, first_interval=1.0)
        if not bpy.app.timers.is_registered(_save_timer):
            bpy.app.timers.register(_save_timer, first_interval=SAVE_SECONDS, persistent=True)
    atexit.unregister(_at_exit)
    atexit.register(_at_exit)


def unregister() -> None:
    save()
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
    for t in (_start_timer, _save_timer, _go_timer):
        if bpy.app.timers.is_registered(t):
            bpy.app.timers.unregister(t)
    from . import workspaces
    workspaces.PERSONAL["hide"] = ()
