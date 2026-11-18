"""Workspaces in a project (task 0062): the state, what a project uses, own-workspace files, switching.

``core/workspaces.py`` knows what a workspace shows; this module keeps a project's choice (three texts on the scene:
``ws_name``, ``ws_data``, ``ws_ticks``), answers the panels' question "does this panel show?" fast (it is asked for
every panel at every redraw), finds what a project uses so nothing in use is hidden unasked, and reads and writes the
user's own workspaces in the library folder "Workspaces". The lock and Blender's own tabs are ``lock.py``.
"""

from __future__ import annotations

import dataclasses
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

# task 0181: the user's own hides (the declutter prompt's "Hide"), on top of every workspace but Full access; never one
# the open project uses (usage.apply_personal works that out and puts the tuple here)
PERSONAL: dict = {"hide": ()}

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
    own = {n: v for n, v in library().items() if W.key_of(n) not in W.RESERVED}
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
def _hidden(name: str, data: str, tick_text: str, gen: int, personal: tuple = ()) -> tuple:
    """(hidden panels, shown function ids, lock, blender_ui, title-only panels) for a project state. Cached: asked
    at every redraw."""
    ws = None
    if data:
        try:
            ws = W.from_json(data, name)
        except ValueError:
            ws = None
    if ws is None:
        ws = W.find(name, _SCAN["found"]) or W.builtin("all")
    if personal and ws.key != "full":
        ws = dataclasses.replace(ws, hide=tuple(sorted(set(ws.hide) | set(personal))))   # never the library's copy
    t = W.parse_ticks(tick_text)
    return W.hidden_panels(ws, t), W.shown_functions(ws, t), ws.lock, ws.blender_ui, W.title_only_panels(ws, t)


def _state(scene) -> tuple:
    s = _settings(scene)
    if s is None:
        return frozenset(), None, False, False, frozenset()
    return _hidden(s.ws_name or default_name(), s.ws_data, s.ws_ticks, _SCAN["gen"], PERSONAL["hide"])


def panel_hidden(scene, panel: str) -> bool:
    return panel in _state(scene)[0]


def panel_title_only(scene, panel: str) -> bool:
    """A panel whose own functions are hidden but that holds a sub-panel that shows: its title row is drawn (a
    sub-panel needs its parent), its own body is not."""
    return panel in _state(scene)[4]


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


def used_functions(scene) -> dict:
    """{function id: (family, "3 tools")} for what this project has set up. Only what is cheap to read: asked
    when a family is ticked off, when a project opens and by the Workspace panel."""
    s = _settings(scene)
    out: dict = {}
    if s is None:
        return out

    def add(fid, text):
        f = F.FUNCTIONS.get(fid)
        if f is not None and fid not in out:
            out[fid] = (f.family, text)

    try:
        steps = [b for a in s.animations for b in a.blocks]
    except Exception:  # noqa: BLE001
        steps = []
    # task 0201: what a placed crane brings (its joints, cylinders, poses, tracks, hoist rope) belongs to the lifting
    # plan, not to the user's own motion: a Lifting plans project does not ask to show Motion for it
    lift = getattr(s, "lifting", None)
    own = tuple(c.name + " · " for c in lift.cranes) if lift is not None else ()

    def mine(name):
        return bool(own) and (name.startswith(own) or name.startswith(tuple("Cable " + p for p in own)))

    if lift is not None and len(lift.cranes):
        add("lifting.place", _count(len(lift.cranes), "crane"))
    if lift is not None and len(lift.loads):
        add("lifting.load", _count(len(lift.loads), "load"))
    # motion
    n = sum(1 for j in s.joints if not getattr(j, "hidden", False) and not mine(j.name))
    if n:
        add("joints.rotate", _count(n, "joint"))
    n = sum(1 for p in s.poses if not mine(p.name))
    if n:
        add("poses.pose", _count(n, "pose"))
    # machine motion
    for coll, word, fid in ((s.cylinders, "cylinder", "machines.cylinder"),
                            (s.mechanisms, "mechanism", "machines.mechanism"),
                            (s.waycovers, "way cover", "machines.waycover"), (s.tracks, "track", "machines.tracks")):
        n = sum(1 for x in coll if not mine(getattr(x, "name", "")))
        if n:
            add(fid, _count(n, word))
    if len(s.flex):
        add("machines.hoses", _count(len(s.flex), "hose or drag chain", "hoses and drag chains"))
    # CNC machine
    cnc = s.cnc
    if cnc.x_joint or cnc.y_joint or cnc.z_joint or cnc.spindle_joint or cnc.tool is not None:
        add("cnc.machine", "a CNC machine")
    if len(cnc.tools):
        add("cnc.tools", _count(len(cnc.tools), "tool"))
    n = sum(1 for b in steps if b.kind == "GCODE")
    if n:
        add("cnc.gcode", _count(n, "G-code step"))
    # milling
    mill = s.milling
    if len(mill.bits) or mill.workpiece is not None:
        add("milling.cut", "a milling set-up" + (f" with {plural(len(mill.bits), 'bit')}" if len(mill.bits) else ""))
    # cables, drums and the sea
    n = sum(1 for x in s.cables if not mine(x.name))
    if n:
        add("offshore.cables", _count(n, "cable"))
    if len(s.spools):
        add("offshore.spool", _count(len(s.spools), "drum or carousel", "drums and carousels"))
    if getattr(s.vessel, "enabled", False):
        add("offshore.vessel_motion", "vessel motion")
    n = len(getattr(s.vessel_work, "thrusters", ()))
    if n:
        add("offshore.vessel_work", _count(n, "thruster"))
    # animation
    if len(s.animations):
        add("animation.add", _count(len(s.animations), "animation"))
    if len(s.trails):
        add("animation.trails", _count(len(s.trails), "trail line"))
    # video finishing
    if len(s.callouts):
        add("animation.labels", _count(len(s.callouts), "label"))
    if s.brand_name or s.brand_logo:
        add("animation.brand", "a brand kit")
    if s.wm_on:
        add("animation.watermark", "a watermark")
    n = sum(1 for a in s.animations if a.fin_title_on or a.fin_end_on or a.fin_captions)
    if n:
        add("animation.finishing", _count(n, "video with cards or captions", "videos with cards or captions"))
    n = sum(len(a.cards) for a in s.animations)
    if n:
        add("animation.cards", _count(n, "picture card"))
    if any(a.music_on for a in s.animations):
        add("animation.music", "music")
    # render queue
    if len(s.queue):
        add("queue.still", _count(len(s.queue), "queued render"))
    # scene: what a workspace may hide of it
    if getattr(s.weather, "enabled", False):
        add("scene.weather", "Weather & time")
    # looks: what the Client view hides is hidden on purpose; cuts and decals are named for the question only
    if len(s.cuts):
        add("looks.cutaway", _count(len(s.cuts), "slice"))
    # house
    try:
        from . import house_import
        if house_import.has_house(scene):
            add("house.import", "a house from House Planner")
    except Exception:  # noqa: BLE001
        pass
    return out


def in_use(scene) -> dict:
    """{family: ["a CNC machine", "3 tools", "a G-code step"]} for the families this project has set up."""
    out: dict = {}
    for _fid, (family, text) in used_functions(scene).items():
        out.setdefault(family, []).append(text)
    return out


def hidden_used(scene) -> dict:
    """{function id: (family, text)} of what the project uses but does not show: its family is off, or its
    workspace hides it inside a family that shows (Way covers in Offshore & cable laying)."""
    shown = _state(scene)[1]
    if shown is None:
        return {}
    return {fid: v for fid, v in used_functions(scene).items() if fid not in shown}


def hidden_in_use(scene) -> list:
    """The families this project uses but does not (wholly) show – the user hid them, or the workspace does."""
    out = []
    for _fid, (family, _text) in hidden_used(scene).items():
        if family not in out:
            out.append(family)
    return out


def show_used(scene) -> list:
    """Show everything the project uses and does not show: its family ticked on, and a function its workspace
    hides inside a shown family ticked on by itself. Returns the families."""
    hidden = hidden_used(scene)
    if not hidden:
        return []
    ws = current(scene)
    t = ticks(scene)
    families = []
    for fid, (family, _text) in hidden.items():
        if family not in families:
            families.append(family)
        if family not in F.ALWAYS and not W.effective_families(ws, t).get(family, True):
            t[family] = True
        if fid not in W.shown_functions(ws, t):
            t[fid] = True
    _settings(scene).ws_ticks = W.ticks_json(t)
    _redraw()
    return families


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
    if not on:                              # hidden means hidden: also what was shown one by one
        for fid in [k for k in t if k in F.FUNCTIONS and F.FUNCTIONS[k].family == family]:
            del t[fid]
    s.ws_ticks = W.ticks_json(t)
    from . import panels
    panels.tab_check(scene)
    _redraw()


def changed(scene) -> bool:
    """True when the user's ticks differ from the workspace (there is something to save as an own workspace)."""
    return bool(ticks(scene))


def apply(scene) -> None:
    """Put the lock and Blender's own tabs / menus as the project's workspace says."""
    from . import lock, panels
    lock.apply(scene, locked(scene))
    lock.blender_ui(blender_ui(scene))
    panels.tab_check(scene)


def ensure(scene) -> bool:
    """A project from before workspaces (or a new one) gets the user's default workspace, with every family it
    uses shown. True when it was set now."""
    s = _settings(scene)
    if s is None or s.ws_name:
        return False
    if app_made(scene):                      # task 0213: an older tour / demo project (made before use_all)
        ws = W.builtin("all")
    else:
        ws = W.find(default_name(), library()) or W.builtin("all")
    s.ws_name = ws.name
    s.ws_data = ws.to_json() if ws.own else ""
    s.ws_ticks = ""
    if not ws.lock:                          # a Client view hides on purpose
        show_used(scene)
    return True


TAGS_APP_MADE = ("fr_tour", "fr_demo")    # tour.TAG, demo.TAG: projects the app makes to show what it can do


def app_made(scene) -> bool:
    """A test-tour or demo project: it opens with every function and unlocked, whatever the user's default
    workspace (task 0213, an older one has no workspace yet)."""
    return any(scene.get(tag) for tag in TAGS_APP_MADE)


def use_all(scene) -> None:
    """A project the app makes itself (test tour, demo, PC check, self-test) shows every function and is never
    locked, whatever workspace the user starts his own projects in."""
    s = _settings(scene)
    if s is None:
        return
    s.ws_name, s.ws_data, s.ws_ticks = W.DEFAULT, "", ""
    apply(scene)


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
    if W.key_of(name) in W.RESERVED:
        return False
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
        elif lock.ON[0]:                     # task 0213: an undo step pushed before the lock marked the objects
            lock.relock()                    # (an import) brings them back unmarked: mark them again
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
    try:                                     # the extension is switched on with a project open: its workspace counts
        scene = getattr(bpy.context, "scene", None)
        if scene is not None and _settings(scene) is not None and _settings(scene).ws_name:
            apply(scene)
    except Exception:  # noqa: BLE001 - at start-up there is no scene yet: the load handler does it
        pass


def unregister() -> None:
    for name, fn in _HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
