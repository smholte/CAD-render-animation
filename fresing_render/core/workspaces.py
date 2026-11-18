"""Workspaces: which functions the side panel shows (task 0062). No Blender here.

A **workspace** is a set of function families for one kind of work ("CNC & machining", "Offshore & cable laying" …),
picked with one switcher at the top of the Fresing tab. Under it the user ticks single **families** on or off for the
project at hand. Hiding never deletes or switches off anything: the work stays in the project and in renders; only
panels go away.

* Built-in workspaces come from the function list (``core/functions.py``): each function says which workspaces show
  it (``workspaces=``, else its family's row of ``FAMILY_WORKSPACES``). A function built later adds itself.
* **Own workspaces** are one ``.json`` file each in the library folder "Workspaces" (share one by copying the file).
  An own workspace with a built-in's name wins, and the panel says so. A file from a newer version opens in an older
  one: families and functions this version does not know are ignored; families the file does not know follow the
  workspace it was based on.
* What a project needs to decide what shows is three small texts: the workspace's name, its definition (for an own
  workspace: the project opens the same on a PC that does not have the file) and the user's ticks.

What shows: a function shows when its family is on and the workspace does not hide it. A family the user ticked ON
himself shows all its functions. A panel shows when one of the functions that name it shows; a panel no function
names always shows.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from . import functions as F

RESERVED = ("all", "full")   # "All functions" shows everything, "Full access" always unlocks: never an own one's name
MARKER = "fresing_render_workspace"
VERSION = 1
FOLDER = "Workspaces"
MAX_NAME = 60
DEFAULT = "All functions"

# key -> (name, what it is for, locks the model, shows Blender's own tabs / toolbar / menus)
BUILTIN = {
    "all": ("All functions", "Every function of the app. Blender's own tabs and toolbar stay out of the way", False,
            False),
    "cnc": ("CNC & machining", "G-code, toolpaths, axis set-up, tools, milling, way covers, clash check. Hides the "
                               "sea, cables and drums, weather, exploded views", False, False),
    "offshore": ("Offshore & cable laying", "Sea and seabed, vessel motion, cables, drums and carousels, cylinders, "
                                            "weather. Hides G-code, tools and milling", False, False),
    "product": ("Product design & R&D", "Looks and paint, exploded views and assembly sequence, cutaway, turntable, "
                                        "web 3D model. Hides G-code, milling, cables and the sea", False, False),
    "client": ("Client view", "For showing a finished project: import, surroundings, camera views, saved scenes, "
                              "turntable, render. Everything else is hidden and the model is locked against "
                              "changes", True, False),
    "education": ("Education & training", "Learning the app on the test models: every kind of motion, the animation "
                                          "steps, camera. Hides the web 3D model", False, False),
    "lifting": ("Lifting plans", "Lifting plans with ready-rigged cranes from the library: place, load and CoG, "
                                 "hook to here, crane use. Also import, structure, looks, scene, animation and the "
                                 "render queue. Hides CNC, milling, cables and the sea", False, False),
    "full": ("Full access", "Every function, plus Blender's own workspace tabs, toolbar and menus. Also undoes the "
                            "Client view's lock", False, True),
}
NAMES = {key: v[0] for key, v in BUILTIN.items()}
PROFILE_KEYS = ("favourites", "usage")     # task 0181: what a profile adds to an own-workspace file


@dataclass
class Workspace:
    name: str
    key: str = ""                                   # the built-in's key; "" for an own workspace
    note: str = ""
    families: dict = field(default_factory=dict)    # family -> shown
    hide: tuple = ()                                # function ids hidden although their family shows
    lock: bool = False                              # the Client view's lock
    blender_ui: bool = False                        # Blender's own tabs, toolbar and menus
    based_on: str = ""                              # an own workspace: the built-in key it started from
    path: str = ""
    extra: dict = field(default_factory=dict)       # task 0181, a profile: "favourites" (and "usage" when ticked)

    @property
    def own(self) -> bool:
        return not self.key

    def to_dict(self, usage: bool = True) -> dict:
        out = {MARKER: VERSION, "name": self.name, "note": self.note, "based_on": self.based_on or self.key,
               "families": {k: bool(v) for k, v in sorted(self.families.items())}, "hide": sorted(self.hide),
               "lock": bool(self.lock), "blender_ui": bool(self.blender_ui)}
        for key in PROFILE_KEYS:                    # a profile's parts (task 0181); older versions ignore them
            if key in self.extra and (usage or key != "usage"):
                out[key] = self.extra[key]
        return out

    def to_json(self) -> str:
        """The definition a project keeps (never a profile's usage counts)."""
        return json.dumps(self.to_dict(usage=False), separators=(",", ":"), sort_keys=True)


def families(funcs=None) -> list:
    """The family keys, in the order of the function list."""
    return list(F.FAMILIES)


def tickable() -> list:
    """The families that have a tick (the others always show)."""
    return [f for f in F.FAMILIES if f not in F.ALWAYS]


def _functions(funcs=None) -> list:
    funcs = F.FUNCTIONS if funcs is None else funcs
    return list(funcs.values()) if isinstance(funcs, dict) else list(funcs)


def builtin(key: str, funcs=None) -> Workspace:
    """The built-in workspace ``key``, worked out from the function list as it is now."""
    name, note, lock, blender_ui = BUILTIN[key]
    items = _functions(funcs)
    fam = {f: False for f in F.FAMILIES}
    hide = []
    for fn in items:
        if fn.shown_in(key):
            fam[fn.family] = True
    for fn in items:
        if fam.get(fn.family) and not fn.shown_in(key):
            hide.append(fn.id)
    for f in F.ALWAYS:                    # always-on families have no tick: what a workspace hides of them is in hide
        if not fam.get(f):
            fam[f] = True
            hide += [fn.id for fn in items if fn.family == f]
    return Workspace(name=name, key=key, note=note, families=fam, hide=tuple(sorted(set(hide))), lock=lock,
                     blender_ui=blender_ui)


def builtins(funcs=None) -> list:
    return [builtin(k, funcs) for k in BUILTIN]


def key_of(name: str) -> str:
    """The built-in key for a built-in's name (or key), else ''."""
    if name in BUILTIN:
        return name
    low = (name or "").casefold()
    return next((k for k, n in NAMES.items() if n.casefold() == low), "")


def from_dict(d: dict, name: str = "", funcs=None) -> Workspace:
    """An own workspace from its file's content. Unknown families and functions are ignored; a family the file
    does not name follows the built-in it was based on (shown, when that is unknown too)."""
    if not isinstance(d, dict) or MARKER not in d:
        raise ValueError("not a Fresing Render workspace file")
    name = clean_name(str(d.get("name") or name))
    if not name:
        raise ValueError("the workspace file has no name")
    based = key_of(str(d.get("based_on") or ""))
    base = builtin(based, funcs) if based else None
    given = d.get("families") if isinstance(d.get("families"), dict) else {}
    fam = {}
    for f in F.FAMILIES:
        if f in F.ALWAYS:
            fam[f] = True
        elif f in given:
            fam[f] = bool(given[f])
        else:
            fam[f] = base.families.get(f, True) if base else True
    known = {fn.id for fn in _functions(funcs)}
    hide = tuple(sorted(str(h) for h in (d.get("hide") or ()) if str(h) in known))
    extra = {k: d[k] for k in PROFILE_KEYS if isinstance(d.get(k), dict)}
    return Workspace(name=name, key="", note=str(d.get("note") or ""), families=fam, hide=hide,
                     lock=bool(d.get("lock")), blender_ui=bool(d.get("blender_ui")), based_on=based, extra=extra)


def from_json(text: str, name: str = "", funcs=None) -> Workspace:
    return from_dict(json.loads(text), name, funcs)


def find(name: str, own: dict | None = None, funcs=None) -> Workspace | None:
    """The workspace called ``name``: an own one from ``own`` ({name: (path, Workspace)}) wins over a built-in –
    except All functions and Full access, which are always the app's own."""
    low = (name or "").casefold()
    if key_of(name) in RESERVED:
        return builtin(key_of(name), funcs)
    for n, hit in (own or {}).items():
        if n.casefold() == low:
            ws = hit[1] if isinstance(hit, tuple) else hit
            return ws
    key = key_of(name)
    return builtin(key, funcs) if key else None


def shadows(name: str, own: dict | None = None) -> bool:
    """True when an own workspace has a built-in's name (it wins; the panel says so). Not for All functions and
    Full access: those are always the app's own."""
    low = (name or "").casefold()
    return bool(key_of(name)) and key_of(name) not in RESERVED and any(n.casefold() == low for n in (own or {}))


# ---------------------------------------------------------------------------
# what shows
# ---------------------------------------------------------------------------

def parse_ticks(text: str) -> dict:
    """The user's ticks of a project: {family: bool}; anything unreadable counts as no ticks."""
    try:
        d = json.loads(text) if text else {}
    except ValueError:
        return {}
    if not isinstance(d, dict):
        return {}
    return {str(k): bool(v) for k, v in d.items() if _tick_key(k, v)}


def _tick_key(k, v) -> bool:
    """A tick is a family that has one (on or off), or a single function shown although the workspace hides it."""
    return (k in F.FAMILIES and k not in F.ALWAYS) or (k in F.FUNCTIONS and bool(v))


def ticks_json(ticks: dict) -> str:
    ticks = {k: bool(v) for k, v in ticks.items() if _tick_key(k, v)}
    return json.dumps(ticks, separators=(",", ":"), sort_keys=True) if ticks else ""


def effective_families(ws: Workspace, ticks: dict | None = None) -> dict:
    """{family: shown} with the user's ticks on top of the workspace."""
    out = {}
    for f in F.FAMILIES:
        if f in F.ALWAYS:
            out[f] = True
        elif ticks and f in ticks:
            out[f] = bool(ticks[f])
        else:
            out[f] = bool(ws.families.get(f, True))
    return out


def shown_functions(ws: Workspace, ticks: dict | None = None, funcs=None) -> frozenset:
    """The ids of the functions that show. A family the user ticked on himself shows all its functions."""
    fam = effective_families(ws, ticks)
    forced = {f for f, v in (ticks or {}).items() if v and f in F.FAMILIES and not ws.families.get(f, True)}
    single = {f for f, v in (ticks or {}).items() if v and f not in F.FAMILIES}     # shown one by one (in use)
    hide = set(ws.hide)
    return frozenset(fn.id for fn in _functions(funcs)
                     if fn.id in single
                     or (fam.get(fn.family, True) and (fn.id not in hide or fn.family in forced)))


def _own_hidden(ws: Workspace, ticks: dict | None = None, funcs=None) -> set:
    shown = shown_functions(ws, ticks, funcs)
    by_panel: dict = {}
    for fn in _functions(funcs):
        if fn.panel in F.MENUS:
            continue
        by_panel.setdefault(fn.panel, []).append(fn.id in shown)
    return {p for p, flags in by_panel.items() if not any(flags)}


def _kept_for_children(own_hidden: set) -> set:
    """The panels whose own functions are all hidden but that hold a sub-panel that shows: Blender draws a
    sub-panel only under its parent, so such a panel keeps its title row (without its own body)."""
    from . import places
    keep = set()
    for panel in list(places.PLACES):
        if panel in own_hidden:
            continue
        parent, seen = places.PLACES[panel][0], set()
        while parent and parent not in seen:
            seen.add(parent)
            if parent in own_hidden:
                keep.add(parent)
            parent = places.PLACES.get(parent, ("",))[0]
    return keep


def hidden_panels(ws: Workspace, ticks: dict | None = None, funcs=None) -> frozenset:
    """The panels (class names) that do not show: every function that names them is hidden, and nothing under
    them shows either."""
    own = _own_hidden(ws, ticks, funcs)
    return frozenset(own - _kept_for_children(own))


def title_only_panels(ws: Workspace, ticks: dict | None = None, funcs=None) -> frozenset:
    """The panels that show only their title row, for the sub-panels under them: their own functions are hidden
    (4 Motion with the family Motion ticked off while the CNC machine under it shows)."""
    return frozenset(_kept_for_children(_own_hidden(ws, ticks, funcs)))


def panel_families(funcs=None) -> dict:
    """{panel class name: the families of the functions that name it}."""
    out: dict = {}
    for fn in _functions(funcs):
        if fn.panel not in F.MENUS:
            out.setdefault(fn.panel, set()).add(fn.family)
    return out


def family_title(family: str) -> str:
    """The short name of a family for a tick: "Machine motion" (the list in brackets goes in the tooltip)."""
    return F.FAMILIES.get(family, family).split(" (")[0]


def family_note(family: str, funcs=None) -> str:
    """What a family holds, for its tooltip: the titles of its functions."""
    titles = [fn.title for fn in _functions(funcs) if fn.family == family]
    return "; ".join(titles[:8]) + (f"; and {len(titles) - 8} more" if len(titles) > 8 else "")


def hide_warning(family: str, uses: list) -> str:
    """The text of the popup when a family the project uses is switched off. ``uses``: what is set up
    ("a CNC machine", "3 tools", "a G-code step")."""
    uses = [u for u in uses if u]
    if not uses:
        return ""
    what = uses[0] if len(uses) == 1 else ", ".join(uses[:-1]) + " and " + uses[-1]
    one = len(uses) == 1 and uses[0].split(" ", 1)[0] in ("a", "an", "1", "the")
    return (f"This project has {what}. {'It stays' if one else 'They stay'} in the project and "
            f"{'keeps' if one else 'keep'} working in renders; only the panels are hidden.")


# ---------------------------------------------------------------------------
# own workspaces: one file each in the library folder "Workspaces"
# ---------------------------------------------------------------------------

_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def clean_name(name: str) -> str:
    """One space between words, at most MAX_NAME characters, no space at either end (also after the cut)."""
    return " ".join((name or "").split())[:MAX_NAME].strip()


def name_problem(name: str, existing=()) -> str:
    """Why this name cannot be used for a new own workspace ('' = fine). A built-in's name is allowed: the own
    workspace then wins over the built-in one (the panel says so)."""
    name = clean_name(name)
    if not name:
        return "Give the workspace a name"
    if key_of(name) in RESERVED:
        return (f"'{NAMES[key_of(name)]}' is the app's own workspace (it must always show everything"
                f"{' and unlock' if key_of(name) == 'full' else ''}): pick another name")
    if any(name.casefold() == e.casefold() for e in existing):
        return f"There is already a workspace of your own called '{name}': pick another name"
    if not any(ch.isalnum() for ch in name):
        return "Use letters or digits in the name"
    return ""


def file_name(name: str) -> str:
    """A file name that works on Windows and network shares (the real name is inside the file)."""
    base = _BAD_CHARS.sub("_", clean_name(name)).rstrip(". ")
    if base.split(".")[0].strip().upper() in _RESERVED:        # "NUL.old" is still the device on Windows
        base = "_" + base
    return (base or "Workspace") + ".json"


def load(path: str, funcs=None) -> Workspace:
    with open(path, encoding="utf-8-sig") as fh:               # Notepad's "UTF-8 with BOM" too
        ws = from_dict(json.load(fh), funcs=funcs)
    ws.path = path
    return ws


def scan(folder: str, funcs=None) -> dict:
    """{name: (path, Workspace)} of the own workspaces in a folder; other or damaged files are skipped. Two files
    with the same name inside (a copy made in Explorer): the one whose file name belongs to the name counts."""
    found: dict = {}
    if not folder or not os.path.isdir(folder):
        return found
    try:
        names = sorted(os.listdir(folder), key=str.casefold)
    except OSError:
        return found
    for f in names:
        if not f.lower().endswith(".json") or f.startswith("."):
            continue
        path = os.path.join(folder, f)
        try:
            ws = load(path, funcs)
        except Exception:  # noqa: BLE001 - unreadable, damaged or not a workspace: one bad file never stops the rest
            continue
        if ws.name in found and f.casefold() != file_name(ws.name).casefold():
            continue
        found[ws.name] = (path, ws)
    return found


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def free_path(folder: str, name: str, own: str = "") -> str:
    """A file for the workspace ``name`` that holds no other file: 'Name.json', else 'Name (2).json' …"""
    base = file_name(name)[:-5]
    k = 1
    while True:
        path = os.path.join(folder, f"{base}.json" if k == 1 else f"{base} ({k}).json")
        if not os.path.exists(path) or (own and _same_file(path, own)):
            return path
        k += 1


def save_in(folder: str, ws: Workspace) -> str:
    """Write an own workspace into the folder (made when missing); replaces its own file, never another's."""
    os.makedirs(folder, exist_ok=True)
    hit = scan(folder).get(ws.name)
    path = hit[0] if hit else free_path(folder, ws.name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ws.to_dict(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)
    ws.path = path
    return path


def rename_in(folder: str, old: str, new: str) -> str:
    known = scan(folder)
    if old not in known:
        raise FileNotFoundError(f"'{old}' is not in the Workspaces folder")
    new = clean_name(new)
    problem = name_problem(new, [n for n in known if n != old])
    if problem:
        raise ValueError(problem)
    path, ws = known[old]
    ws.name = new
    target = free_path(folder, new, own=path)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(ws.to_dict(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, target)
    if not _same_file(path, target):
        try:
            os.remove(path)
        except OSError:
            pass
    return target


def delete_in(folder: str, name: str) -> None:
    hit = scan(folder).get(name)
    if hit is None:
        raise FileNotFoundError(f"'{name}' is not in the Workspaces folder")
    os.remove(hit[0])


def make_own(name: str, base: Workspace, ticks: dict | None = None, note: str = "") -> Workspace:
    """An own workspace from what shows now: the base workspace with the user's ticks worked in."""
    fam = effective_families(base, ticks)
    forced = {f for f, v in (ticks or {}).items() if v and f in F.FAMILIES and not base.families.get(f, True)}
    single = {f for f, v in (ticks or {}).items() if v and f not in F.FAMILIES}
    hide = tuple(h for h in base.hide if h not in single
                 and (F.FUNCTIONS.get(h) is None or F.FUNCTIONS[h].family not in forced))
    for fid in single:                               # a single function of a hidden family: the family shows, the
        f = F.FUNCTIONS.get(fid)                     # rest of it stays hidden
        if f is not None and not fam.get(f.family, True):
            fam[f.family] = True
            hide += tuple(o.id for o in F.FUNCTIONS.values() if o.family == f.family and o.id not in single)
    return Workspace(name=clean_name(name), key="", note=note or f"Based on '{base.name}'", families=fam,
                     hide=tuple(sorted(hide)), lock=base.lock, blender_ui=base.blender_ui,
                     based_on=base.key or base.based_on)
