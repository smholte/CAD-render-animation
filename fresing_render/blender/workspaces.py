"""Workspaces in a project (task 0062): the state, what a project uses, own-workspace files, switching.

``core/workspaces.py`` knows what a workspace shows; this module keeps a project's choice (three texts on the scene:
``ws_name``, ``ws_data``, ``ws_ticks``), answers the panels' question "does this panel show?" fast (it is asked for
every panel at every redraw), finds what a project uses so nothing in use is hidden unasked, and reads and writes the
user's own workspaces in the library folder "Workspaces". The lock and Blender's own tabs are ``lock.py``.
"""

from __future__ import annotations

import functools
import os
import time

import bpy
from bpy.app.handlers import persistent

from ..core import functions as F
from ..core import workspaces as W
from ..core.words import plural

ENV_FOLDER = "FRESING_WORKSPACES_DIR"        # tests: use this folder instead of the library
SCAN_SECONDS = 15.0                          # a network folder is read at most this often while drawing

# ---------------------------------------------------------------------------
# where the own workspaces are
# ---------------------------------------------------------------------------

_FOLDER: dict = {"key": None, "time": 0.0, "ok": True}
_SCAN: dict = {"key": None, "time": 0.0, "found": {}, "gen": 0}


def folder(fresh: bool = False) -> tuple:
    """(folder, shared, problem): the "Workspaces" folder, whether it is in the shared library, and why it cannot
    be used right now ('' = fine). As for rule sets: without a shared library it is Documents/Fresing Render."""
    override = os.environ.get(ENV_FOLDER)
    if override:
        return override, True, ""
    from . import prefs, rule_sets
    p = prefs.get()
    lib = bpy.path.abspath(p.library_path) if p is not None and p.library_path else ""
    if not lib:
        return os.path.join(rule_sets.documents_dir(), "Fresing Render", W.FOLDER), False, ""
    now = time.monotonic()
    if fresh or _FOLDER["key"] != lib or now - _FOLDER["time"] > SCAN_SECONDS:
        _FOLDER.update(key=lib, time=now, ok=os.path.isdir(lib))
    path = os.path.join(lib, W.FOLDER)
    if not _FOLDER["ok"]:
        return path, True, f"The shared library cannot be reached ({lib})"
    return path, True, ""


def library(force: bool = False) -> dict:
    """{name: (file, Workspace)} of the own workspaces (read again at most every few seconds)."""
    path, _shared, problem = folder(fresh=force)
    if problem:
        return {}
    now = time.monotonic()
    if force or _SCAN["key"] != path or now - _SCAN["time"] > SCAN_SECONDS:
        found = W.scan(path)
        if force or _SCAN["key"] != path or {k: v[1].to_json() for k, v in found.items()} != \
                {k: v[1].to_json() for k, v in _SCAN["found"].items()}:
            _SCAN["gen"] += 1
            _hidden.cache_clear()
        _SCAN.update(key=path, time=now, found=found)
    return _SCAN["found"]


def forget_scan() -> None:
    _SCAN["key"] = None
    _FOLDER["key"] = None
    _hidden.cache_clear()


def names() -> list:
    """Every workspace the switcher lists: (name, note, own) – the built-in ones first, then the user's own. A
    built-in whose name an own workspace took is left out (the own one wins)."""
    own = library()
    low = {n.casefold() for n in own}
    out = [(n, W.BUILTIN[k][1], False) for k, n in W.NAMES.items() if n.casefold() not in low]
    out += [(n, ws.note or "Your own workspace", True) for n, (_p, ws) in sorted(own.items(),
                                                                                key=lambda kv: kv[0].casefold())]
    return out


def default_name() -> str:
    """The workspace new projects start in (Preferences); the built-in default when that one is gone."""
    from . import prefs
    p = prefs.get()
    name = (p.default_workspace if p is not None else "") or W.DEFAULT
    return name if W.find(name, library()) is not None else W.DEFAULT


# ---------------------------------------------------------------------------
# a project's state
# ---------------------------------------------------------------------------

def _settings(scene):
    return getattr(scene, "fresing", None)


def name_of(scene) -> str:
    """The project's workspace; a project that has none yet counts as the default one."""
    s = _settings(scene)
    return (s.ws_name if s is not None else "") or default_name()


def current(scene) -> W.Workspace:
    """The workspace the project uses: the definition kept in the project for an own one (so it opens the same
    without the file), the built-in worked out from today's function list otherwise."""
    s = _settings(scene)
    name = name_of(scene)
    if s is not None and s.ws_data:
        try:
            return W.from_json(s.ws_data, name)
        except ValueError:
            pass
    return W.find(name, library()) or W.builtin("all")


def ticks(scene) -> dict:
    s = _settings(scene)
    return W.parse_ticks(s.ws_ticks) if s is not None else {}


@functools.lru_cache(maxsize=64)
def _hidden(name: str, data: str, tick_text: str, gen: int) -> tuple:
    """(hidden panels, shown function ids, lock, blender_ui) for a project state. Cached: asked at every redraw."""
    ws = None
    if data:
        try:
            ws = W.from_json(data, name)
        except ValueError:
            ws = None
    if ws is None:
        ws = W.find(name, _SCAN["found"]) or W.builtin("all")
    t = W.parse_ticks(tick_text)
    return W.hidden_panels(ws, t), W.shown_functions(ws, t), ws.lock, ws.blender_ui


def _state(scene) -> tuple:
    s = _settings(scene)
    if s is None:
        return frozenset(), None, False, False
    return _hidden(s.ws_name or default_name(), s.ws_data, s.ws_ticks, _SCAN["gen"])


def panel_hidden(scene, panel: str) -> bool:
    return panel in _state(scene)[0]


def shows(scene, fid: str) -> bool:
    """Does the project's workspace show this function (an id of core/functions.py)? For the few spots where a
    panel holds functions of several kinds."""
    shown = _state(scene)[1]
    return True if shown is None else fid in shown


def locked(scene) -> bool:
    return bool(_state(scene)[2])


def blender_ui(scene) -> bool:
    return bool(_state(scene)[3])


def family_on(scene, family: str) -> bool:
    return W.effective_families(current(scene), ticks(scene)).get(family, True)


# ---------------------------------------------------------------------------
# what a project uses
# ---------------------------------------------------------------------------

def _count(n: int, one: str, many: str | None = None) -> str:
    return plural(n, one, many) if n != 1 else (("an " if one[:1] in "aeiou" else "a ") + one)


def in_use(scene) -> dict:
    """{family: ["a CNC machine", "3 tools", "a G-code step"]} for the families this project has set up. Only what
    is cheap to read: asked when a family is ticked off and when a project opens."""
    s = _settings(scene)
    out: dict = {}
    if s is None:
        return out

    def add(family, text):
        out.setdefault(family, []).append(text)

    try:
        steps = [b for a in s.animations for b in a.blocks]
    except Exception:  # noqa: BLE001
        steps = []
    # motion
    n = sum(1 for j in s.joints if not getattr(j, "hidden", False))
    if n:
        add("motion", _count(n, "joint"))
    if len(s.poses):
        add("motion", _count(len(s.poses), "pose"))
    # machine motion
    for coll, word in ((s.cylinders, "cylinder"), (s.mechanisms, "mechanism"), (s.waycovers, "way cover"),
                       (s.tracks, "track")):
        if len(coll):
            add("machines", _count(len(coll), word))
    if len(s.flex):
        add("machines", _count(len(s.flex), "hose or drag chain", "hoses and drag chains"))
    # CNC machine
    cnc = s.cnc
    if cnc.x_joint or cnc.y_joint or cnc.z_joint or cnc.spindle_joint or cnc.tool is not None:
        add("cnc", "a CNC machine")
    if len(cnc.tools):
        add("cnc", _count(len(cnc.tools), "tool"))
    n = sum(1 for b in steps if b.kind == "GCODE")
    if n:
        add("cnc", _count(n, "G-code step"))
    # milling
    mill = s.milling
    if len(mill.bits) or mill.workpiece is not None:
        add("milling", "a milling set-up" + (f" with {plural(len(mill.bits), 'bit')}" if len(mill.bits) else ""))
    # cables, drums and the sea
    for coll, word in ((s.cables, "cable"), (s.spools, "drum or carousel")):
        if len(coll):
            add("offshore", _count(len(coll), word, "drums and carousels" if word.startswith("drum") else None))
    if getattr(s.vessel, "enabled", False):
        add("offshore", "vessel motion")
    n = len(getattr(s.vessel_work, "thrusters", ()))
    if n:
        add("offshore", _count(n, "thruster"))
    # animation
    if len(s.animations):
        add("animation", _count(len(s.animations), "animation"))
    if len(s.trails):
        add("animation", _count(len(s.trails), "trail line"))
    # video finishing
    if len(s.callouts):
        add("video", _count(len(s.callouts), "label"))
    if s.brand_name or s.brand_logo:
        add("video", "a brand kit")
    if s.wm_on:
        add("video", "a watermark")
    n = sum(1 for a in s.animations if a.fin_title_on or a.fin_end_on or a.fin_captions)
    if n:
        add("video", _count(n, "video with cards or captions", "videos with cards or captions"))
    n = sum(len(a.cards) for a in s.animations)
    if n:
        add("video", _count(n, "picture card"))
    if any(a.music_on for a in s.animations):
        add("video", "music")
    # render queue
    if len(s.queue):
        add("queue", _count(len(s.queue), "queued render"))
    # house
    try:
        from . import house_import
        if house_import.has_house(scene):
            add("house", "a house from House Planner")
    except Exception:  # noqa: BLE001
        pass
    return out


def hidden_in_use(scene) -> list:
    """The families this project uses but does not show (the user hid them, or the workspace does)."""
    fam = W.effective_families(current(scene), ticks(scene))
    return [f for f in in_use(scene) if not fam.get(f, True)]


def show_used(scene) -> list:
    """Tick on every family the project uses and does not show; returns them."""
    hidden = hidden_in_use(scene)
    if hidden:
        t = ticks(scene)
        for f in hidden:
            t[f] = True
        _settings(scene).ws_ticks = W.ticks_json(t)
        _redraw()
    return hidden


# ---------------------------------------------------------------------------
# switching
# ---------------------------------------------------------------------------

def _redraw() -> None:
    wm = bpy.context.window_manager
    if wm is None:
        return
    for win in wm.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def switch(scene, name: str, keep_used: bool = False) -> W.Workspace:
    """The project uses this workspace from now on; the ticks start afresh. ``keep_used``: families the project
    uses stay shown (a project from before workspaces, a template)."""
    s = _settings(scene)
    ws = W.find(name, library(force=True))
    if ws is None:
        raise KeyError(f"There is no workspace called '{name}'")
    s.ws_name = ws.name
    s.ws_data = ws.to_json() if ws.own else ""
    s.ws_ticks = ""
    if keep_used:
        show_used(scene)
    apply(scene)
    _redraw()
    return ws


def set_tick(scene, family: str, on: bool) -> None:
    """Switch one family on or off in this project (on top of its workspace)."""
    if family in F.ALWAYS or family not in F.FAMILIES:
        return
    s = _settings(scene)
    t = ticks(scene)
    if bool(current(scene).families.get(family, True)) == bool(on):
        t.pop(family, None)                 # back to what the workspace says: no tick to remember
    else:
        t[family] = bool(on)
    s.ws_ticks = W.ticks_json(t)
    _redraw()


def changed(scene) -> bool:
    """True when the user's ticks differ from the workspace (there is something to save as an own workspace)."""
    return bool(ticks(scene))


def apply(scene) -> None:
    """Put the lock and Blender's own tabs / menus as the project's workspace says."""
    from . import lock
    lock.apply(scene, locked(scene))
    lock.blender_ui(blender_ui(scene))


def ensure(scene) -> bool:
    """A project from before workspaces (or a new one) gets the user's default workspace, with every family it
    uses shown. True when it was set now."""
    s = _settings(scene)
    if s is None or s.ws_name:
        return False
    ws = W.find(default_name(), library()) or W.builtin("all")
    s.ws_name = ws.name
    s.ws_data = ws.to_json() if ws.own else ""
    s.ws_ticks = ""
    show_used(scene)
    return True


def on_load(scene) -> None:
    """After a project is open: a workspace for a project that has none, then the lock and Blender's tabs as that
    workspace says (the lock's marks are in the project; Blender's tabs are not)."""
    if scene is None or _settings(scene) is None:
        return
    library(force=True)
    ensure(scene)
    apply(scene)


# ---------------------------------------------------------------------------
# own workspaces
# ---------------------------------------------------------------------------

def _writable_folder() -> str:
    path, _shared, problem = folder(fresh=True)
    if problem:
        raise OSError(problem)
    return path


def save_own(scene, name: str, note: str = "") -> str:
    """Save what shows now as an own workspace (a new one, or over an own one of that name); the project uses it
    from now on. Returns the file."""
    name = W.clean_name(name)
    problem = W.name_problem(name)
    if problem:
        raise ValueError(problem)
    ws = W.make_own(name, current(scene), ticks(scene), note)
    path = W.save_in(_writable_folder(), ws)
    forget_scan()
    library(force=True)
    s = _settings(scene)
    s.ws_name, s.ws_data, s.ws_ticks = ws.name, ws.to_json(), ""
    apply(scene)
    _redraw()
    return path


def rename_own(scene, old: str, new: str) -> str:
    """Rename an own workspace's file; this project follows when it uses it."""
    new = W.clean_name(new)
    path = W.rename_in(_writable_folder(), old, new)
    forget_scan()
    library(force=True)
    s = _settings(scene)
    if s is not None and s.ws_name == old:
        s.ws_name = new
        if s.ws_data:
            ws = W.from_json(s.ws_data, new)
            ws.name = new
            s.ws_data = ws.to_json()
    _redraw()
    return path


def delete_own(scene, name: str) -> None:
    """Delete an own workspace's file. A project that uses it keeps its copy until it picks another workspace."""
    W.delete_in(_writable_folder(), name)
    forget_scan()
    library(force=True)
    _redraw()


def is_own(name: str) -> bool:
    return any(n.casefold() == (name or "").casefold() for n in library())


# ---------------------------------------------------------------------------
# handlers: a project opens, is saved, an undo
# ---------------------------------------------------------------------------

@persistent
def _on_load(_dummy=None):
    from . import panels
    scene = bpy.context.scene
    try:
        on_load(scene)
    except Exception as exc:  # noqa: BLE001 - never break loading
        print("Fresing Render: workspace not set:", exc)
    try:
        panels.on_load(scene)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: sections not folded:", exc)


@persistent
def _on_save(_dummy=None):
    from . import panels
    for sc in bpy.data.scenes:
        try:
            panels.on_save(sc)
        except Exception:  # noqa: BLE001
            pass


@persistent
def _after_undo(_dummy=None):
    """Undo and redo put the project's workspace back; the lock and Blender's tabs follow it."""
    from . import lock
    scene = bpy.context.scene
    if scene is None or _settings(scene) is None:
        return
    try:
        if locked(scene) != lock.ON[0] or bool(lock.marked()) != lock.ON[0]:
            lock.apply(scene, locked(scene))
        if blender_ui(scene) == lock.tabs_hidden():
            lock.blender_ui(blender_ui(scene))
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: lock not put right after undo:", exc)


_HANDLERS = (("load_post", _on_load), ("save_pre", _on_save), ("undo_post", _after_undo), ("redo_post", _after_undo))


def register() -> None:
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)
    forget_scan()


def unregister() -> None:
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
