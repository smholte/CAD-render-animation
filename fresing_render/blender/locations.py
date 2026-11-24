"""Locations (task 0272): the folders the app reads from, the set-up files, the export places – Blender side.

``core/locations.py`` has the rules (kinds, the ``.frsetup`` file, merging, export places, the migration); this file
keeps the user's state in ``<config>/fresing_locations.json`` and answers the app's readers:

* ``folders(kind)`` – every folder of a kind (company set-ups, department set-ups, Mine), each with its badge and
  whether it can be reached (looked at in a helper thread: a server that does not answer is never waited for);
  ``paths(kind)`` – the ones that can be read now; ``items(kind, …)`` – what they hold, merged, each with its badge.
* ``save_folder(kind)`` / ``save_choices(kind)`` – where something new is saved: the writable folders, Mine first.
* ``output_dir(scene)`` – THE folder an output goes to (the project's export place, the user's default, or the
  project's own folder of before); ``copy_also(scene, path)`` – the "also a copy to" place.

**Set-ups** (``install``, ``remove``, ``refresh``): every set-up is kept as a copy in ``<config>/fresing_setups/<id>
.frsetup`` with its content unpacked beside it (read-only to the app). A *linked* one also remembers where it lies and
is read again at the next start when it changed there ("Company set-up updated (3 → 4)", Show changes). A set-up
file in the folder of the approved version (``docs/COMPANY-USE.md``: the update address is a folder) is picked up by
itself.

**The first start of this version** (``load`` → ``core.migrate``): a Shared library folder of before becomes Mine for
every kind; without one the ready-made folders ``Documents\\Fresing Render\\Library\\…`` are made – switched off,
with one note, when a set-up was there first.
"""

from __future__ import annotations

import os
import time

import bpy

from ..core import locations as L

ENV = "FRESING_LOCATIONS_FILE"           # tests: the state file (its folder also holds the set-ups)
ENV_SETUP_FOLDER = "FRESING_SETUP_FOLDER"   # tests: the folder where IT puts the set-up file for everyone
TICK = 10.0
NOTE_OFF = ("Your organisation's set-up is in use. Your own folders are ready but switched off – turn them on in "
            "Fresing Settings > Locations")

REACH = L.Reach()
_S: dict = {"state": None, "setups": None, "notes": [], "loaded": False, "popup_done": False, "gen": 0}


# ---------------------------------------------------------------------------------------------------------------------
# files

def path() -> str:
    return os.environ.get(ENV) or os.path.join(bpy.utils.user_resource("CONFIG"), L.STATE_FILE)


def setups_dir() -> str:
    return os.path.join(os.path.dirname(path()), L.SETUPS_DIR)


def usable() -> bool:
    """The state file is written only in the app's own window (or when a test names the file)."""
    return bool(os.environ.get(ENV)) or not bpy.app.background


def documents() -> str:
    from . import rule_sets
    return rule_sets.documents_dir()


def _prefs():
    from . import prefs
    try:
        return prefs.get()
    except Exception:  # noqa: BLE001
        return None


def state() -> dict:
    """The user's state (read once). In a background run without a file: the ready-made folders, nothing written."""
    if _S["state"] is None:
        st, note = L.read_state(path())
        if note:
            _S["notes"].append(note)
        if not st["migrated"]:
            p = _prefs()
            L.migrate(st, bpy.path.abspath(p.library_path) if p is not None and p.library_path else "", documents(),
                      bool(st["setups"]))
        _S["state"] = st
    return _S["state"]


def save_state() -> None:
    _changed()
    if not usable():
        return
    try:
        L.write_state(path(), state())
    except OSError as exc:
        print("Fresing Render: could not save the locations:", exc)


def _changed() -> None:
    """Something changed: lists are read again (each reader keys its cache on ``generation()``)."""
    _S["gen"] += 1
    _S["setups"] = None
    for mod, name in (("rule_sets", "forget_scan"), ("workspaces", "forget_scan")):
        try:
            getattr(__import__(f"{__package__}.{mod}", fromlist=[name]), name)()
        except Exception:  # noqa: BLE001 - a reader that is not loaded yet
            pass
    try:
        from . import lifting
        lifting._LIB["items"] = None
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import ops_main
        ops_main._LIBRARY_SCAN.clear()
    except Exception:  # noqa: BLE001
        pass


def generation() -> int:
    return _S["gen"]


def notes() -> list:
    return list(_S["notes"])


# ---------------------------------------------------------------------------------------------------------------------
# set-ups

def setups() -> list:
    """[(Setup, folder of its file, unpacked content folder)] in the order they were added."""
    if _S["setups"] is None:
        out = []
        for e in state()["setups"]:
            f = e.get("file") or ""
            try:
                s = L.read_setup(f)
            except L.SetupError as exc:
                if f"{e.get('id')}: {exc}" not in _S["notes"]:
                    _S["notes"].append(f"{e.get('label') or e.get('name') or e.get('id')}: {exc}")
                continue
            base = os.path.dirname(e.get("source") or f)        # relative folders: next to the file as it was given
            out.append((s, base, os.path.join(setups_dir(), s.id)))
        _S["setups"] = out
    return _S["setups"]


def entry(sid: str):
    return next((e for e in state()["setups"] if e.get("id") == sid), None)


def setup_of(sid: str):
    return next((s for s, _b, _u in setups() if s.id == sid), None)


def _stamp(p: str) -> list:
    try:
        st = os.stat(p)
        return [int(st.st_mtime), int(st.st_size)]
    except OSError:
        return []


def check(path_: str) -> tuple:
    """(new Setup, the installed one with the same id or None, the change lines). SetupError when it cannot be used."""
    new = L.read_setup(path_)
    old = setup_of(new.id)
    lines = L.changes(old, new)
    if old is not None:
        cp = os.path.join(setups_dir(), new.id + L.SETUP_EXT)
        if os.path.isfile(cp):
            lines += L.content_changed(os.path.join(setups_dir(), new.id), path_)
    return new, old, lines


def install(src: str, mode: str = "", auto: bool = False) -> L.Setup:
    """Bring a set-up in (or replace the one with the same id): its copy and content in the config folder, its
    settings put into Fresing Settings. ``mode`` "copy" or "link" ('' = link for a network path, else copy)."""
    import shutil
    s = L.read_setup(src)
    mode = mode or ("link" if L.is_unc(src) else "copy")
    os.makedirs(setups_dir(), exist_ok=True)
    copy = os.path.join(setups_dir(), s.id + L.SETUP_EXT)
    if not L.same_path(os.path.abspath(src), copy):
        tmp = copy + ".tmp"
        shutil.copyfile(src, tmp)
        os.replace(tmp, copy)
    L.unpack(copy, os.path.join(setups_dir(), s.id))
    st = state()
    e = entry(s.id)
    new = {"id": s.id, "mode": mode, "source": os.path.abspath(src), "file": copy, "version": s.version,
           "name": s.name, "level": s.level, "label": s.label, "stamp": _stamp(src), "auto": auto}
    if e is None:
        st["setups"].append(new)
    else:
        e.update(new)
    apply_settings(s)
    save_state()
    return s


def remove(sid: str) -> bool:
    import shutil
    st = state()
    e = entry(sid)
    if e is None:
        return False
    st["setups"].remove(e)
    for p in (os.path.join(setups_dir(), sid + L.SETUP_EXT),):
        try:
            os.remove(p)
        except OSError:
            pass
    shutil.rmtree(os.path.join(setups_dir(), sid), ignore_errors=True)
    save_state()
    return True


def apply_settings(s: L.Setup) -> list:
    """Put a set-up's settings into Fresing Settings; returns the names left out (unknown or a wrong value)."""
    from . import settings_store
    p = _prefs()
    left = []
    if p is None:
        return list(s.settings)
    spec = settings_store.spec()
    for name, value in s.settings.items():
        if name not in spec or name in ("library_path", "settings_tab"):
            left.append(name)
            continue
        try:
            if spec[name].type == "colour":
                value = tuple(float(x) for x in value)
            setattr(p, name, value)
        except (TypeError, ValueError, AttributeError) as exc:
            print(f"Fresing Render: set-up {s.badge}: setting {name} not used:", exc)
            left.append(name)
    return left


def refresh(force: bool = False) -> list:
    """Linked set-ups that changed where they lie are taken in again; set-up files in the approved version's folder
    picked up. Never waits for a folder that does not answer. Returns the notices ("Company set-up updated (3 → 4)")."""
    out = []
    for e in list(state()["setups"]):
        if e.get("mode") != "link":
            continue
        src = e.get("source") or ""
        if REACH.state(os.path.dirname(src) or ".") is not True:
            continue
        stamp = _stamp(src)
        if not stamp or (stamp == e.get("stamp") and not force):
            continue
        try:
            new, old, lines = check(src)
        except L.SetupError as exc:
            _S["notes"].append(f"{e.get('label') or e.get('name')}: the linked file changed and cannot be used: {exc}")
            e["stamp"] = stamp
            continue
        if new.id != e["id"]:
            e["stamp"] = stamp
            continue
        was = old.version if old is not None else e.get("version")
        install(src, "link", auto=e.get("auto", False))
        if lines:
            text = f"{new.badge} set-up updated ({was} → {new.version})" if was != new.version else \
                f"{new.badge} set-up changed"
            state()["updated"].append({"id": new.id, "text": text, "lines": lines, "at": L.now_text()})
            out.append(text)
    out += pick_up()
    if out:
        save_state()
    return out


def approved_folder() -> str:
    """The folder of the approved version (the update address is a file or folder, not GitHub): IT puts the set-up
    file for everyone there. '' when updates come from the internet."""
    env = os.environ.get(ENV_SETUP_FOLDER)
    if env:
        return env
    try:
        from ..core import updates as core_updates
        from . import updates
        url, _source = updates.index_url()
        path = core_updates.local_path(url, windows=os.name == "nt") if url else ""
    except Exception:  # noqa: BLE001
        return ""
    if not path:
        return ""
    # decided from the text, never by asking the disk: a server that does not answer must not hold up the start
    import ntpath
    import posixpath
    paths = ntpath if os.name == "nt" else posixpath
    return paths.dirname(path) if path.lower().endswith(".json") else path.rstrip("\\/")


_PICKED: dict = {}               # file in the approved folder -> its stamp when it was last read


def pick_up() -> list:
    """Set-up files in the approved folder that are not in yet are added (linked)."""
    folder = approved_folder()
    if not folder or REACH.state(folder) is not True:
        return []
    out = []
    try:
        names = sorted(n for n in os.listdir(folder) if n.lower().endswith(L.SETUP_EXT))
    except OSError:
        return []
    for n in names:
        src = os.path.join(folder, n)
        stamp = _stamp(src)
        if _PICKED.get(src) == stamp:             # read once; a changed file is taken in by refresh (linked)
            continue
        _PICKED[src] = stamp
        try:
            s = L.read_setup(src)
        except L.SetupError as exc:
            _S["notes"].append(str(exc))
            continue
        if entry(s.id) is None:
            install(src, "link", auto=True)
            out.append(f"{s.badge} set-up added from {folder}")
    return out


# ---------------------------------------------------------------------------------------------------------------------
# start

def load() -> None:
    """At the start (after the settings file was read): the state, set-ups from IT's folder, the migration, the
    ready-made folders made."""
    if not usable():
        return
    _S.update(state=None, setups=None, notes=[], loaded=False)
    st, note = L.read_state(path())
    if note:
        _S["notes"].append(note)
    _S["state"] = st
    if not st["migrated"]:
        approved = approved_folder()
        if approved:
            REACH.state(approved)
            REACH.settle([approved], timeout=2.0)     # first start only: IT's set-up must count before the migration
        pick_up()
        p = _prefs()
        lib = bpy.path.abspath(p.library_path) if p is not None and p.library_path else ""
        for folder in L.migrate(st, lib, documents(), bool(st["setups"])):
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError as exc:
                print("Fresing Render: could not make", folder, exc)
        save_state()
    _S["loaded"] = True


def _tick():
    try:
        if not _S["loaded"]:
            load()
        else:
            refresh()
        _popup()
    except Exception as exc:  # noqa: BLE001 - a timer that raises is dropped
        print("Fresing Render: locations:", exc)
    return TICK


def _popup() -> None:
    """The one note for a user whose own folders were made switched off (a set-up was there first)."""
    st = state()
    if _S["popup_done"] or not st.get("note_off") or bpy.app.background:
        return
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm and wm.windows else None
    if win is None:
        return
    _S["popup_done"] = True

    def draw(self, _context):
        self.layout.label(text="Your organisation's set-up is in use.")
        self.layout.label(text="Your own folders are ready but switched off: turn them on in")
        self.layout.operator("fresing.settings", text="Fresing Settings > Locations", icon="PREFERENCES").tab = \
            "locations"
    try:
        with bpy.context.temp_override(window=win):
            wm.popup_menu(draw, title="Fresing Render: folders", icon="INFO")
    except Exception:  # noqa: BLE001
        pass


def register() -> None:
    if not usable():
        return
    try:
        load()
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render: locations not read:", exc)
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=2.0, persistent=True)


def unregister() -> None:
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)


def forget() -> None:
    """Tests: as a new start."""
    _S.update(state=None, setups=None, notes=[], loaded=False, popup_done=False)
    REACH.forget()
    _WRITABLE.clear()
    _changed()


# ---------------------------------------------------------------------------------------------------------------------
# the readers

def folders(kind: str, include_off: bool = False) -> list:
    """Every folder of a kind (``core.Loc``), each with ``reach``: True, False (cannot be reached) or None (being
    looked at – its items are left out until the answer comes)."""
    out = L.locations(state(), setups(), kind, include_off=include_off)
    for loc in out:
        loc.reach = REACH.state(loc.path) if loc.on else None
    return out


def paths(kind: str) -> list:
    """The folders of a kind that can be read now, in order."""
    seen, out = [], []
    for loc in folders(kind):
        if loc.reach and not any(L.same_path(loc.path, s) for s in seen):
            seen.append(loc.path)
            out.append(loc.path)
    return out


def first_path(kind: str) -> str:
    p = paths(kind)
    return p[0] if p else ""


def badge_of(file_path: str, kind: str) -> str:
    """The badge of the folder a file lies in ('' when it is in none of the kind's folders)."""
    fp = os.path.normcase(os.path.abspath(file_path))
    for loc in folders(kind):
        root = os.path.normcase(os.path.abspath(loc.path))
        if fp.startswith(root.rstrip("\\/") + os.sep):
            return loc.badge
    return ""


def items(kind: str, exts: tuple = (), dirs: bool = False, walk: bool = False) -> list:
    """[(key, name, path, Loc)] of what the kind's folders hold: files ending in ``exts`` (or sub-folders with
    ``dirs``), merged and sorted by name; the same name twice gets the key "name (badge)"."""
    found = []
    for loc in folders(kind):
        if not loc.reach:
            continue
        try:
            if walk:
                for dirpath, sub, files in os.walk(loc.path):
                    sub.sort()
                    for f in files:
                        if f.lower().endswith(exts) and not f.startswith("."):
                            full = os.path.join(dirpath, f)
                            name = os.path.splitext(os.path.relpath(full, loc.path))[0].replace(os.sep, " / ")
                            found.append((name, loc, full))
            else:
                for f in os.listdir(loc.path):
                    full = os.path.join(loc.path, f)
                    if f.startswith("."):
                        continue
                    if dirs and os.path.isdir(full):
                        found.append((f, loc, full))
                    elif not dirs and f.lower().endswith(exts) and os.path.isfile(full):
                        found.append((os.path.splitext(f)[0], loc, full))
        except OSError:
            continue
    merged = L.merge(found)
    keys = L.unique_keys([(n, loc.badge) for n, loc, _p in merged])
    return [(k, n, p, loc) for k, (n, loc, p) in zip(keys, merged)]


_WRITABLE: dict = {}             # path -> (answer, time): asked at most every REACH.ttl seconds (panels ask on redraw)


def _can_write(path: str) -> bool:
    now = time.monotonic()
    hit = _WRITABLE.get(path)
    if hit is not None and now - hit[1] < REACH.ttl:
        return hit[0]
    ok = L.writable(path)                 # a real try (Windows' os.access says yes to every folder)
    _WRITABLE[path] = (ok, now)
    return ok


def _usable_for_saving(loc) -> bool:
    """A folder something new may be saved into: one of a set-up's own content never; one that can be reached and
    written; a Mine folder that is not there yet when it is a ready-made one or its parent folder is there and can
    be written (it is made then) – never one on a server that does not answer."""
    if loc.packed or not loc.on:
        return False
    if loc.reach:
        return _can_write(loc.path)
    if loc.level != "mine":
        return False
    if loc.ready:
        return True
    parent = os.path.dirname(os.path.normpath(loc.path))
    return bool(parent) and REACH.state(parent) is True and _can_write(parent)


def save_choices(kind: str) -> list:
    """[(folder, label)] where something new of this kind can be saved: the writable folders, Mine first. (The
    Client view's lock refuses the buttons of Locations and Exports: they are not on ``lock.ALLOWED``.)"""
    out = []
    for loc in sorted(folders(kind), key=lambda x: 0 if x.level == "mine" else 1):
        if _usable_for_saving(loc) and not any(L.same_path(loc.path, o[0]) for o in out):
            out.append((loc.path, f"{loc.badge}: {loc.path}"))
    return out


def save_folder(kind: str, make: bool = True) -> str:
    """The first folder something new of this kind is saved into (made when it is a Mine folder that is not there
    yet); '' when there is none – the caller says "add one in Fresing Settings > Locations"."""
    ch = save_choices(kind)
    if not ch:
        return ""
    p = ch[0][0]
    if make:
        try:
            os.makedirs(p, exist_ok=True)
        except OSError:
            return ""
        made(p)
    return p


def look_again() -> None:
    """Every folder looked at again (Refresh / Look again buttons): the last answers stay until the new ones come."""
    REACH.forget()
    _WRITABLE.clear()
    _changed()


def made(folder: str) -> None:
    """A folder the app has just made to save into: it counts as there at once."""
    REACH.mark(folder, True)
    _WRITABLE.pop(folder, None)


def no_folder_text(kind: str) -> str:
    return (f"No folder for {L.kind(kind).title.lower()} you can save into: switch one on or add one in "
            "Fresing Settings > Locations")


# ---------------------------------------------------------------------------------------------------------------------
# Mine folders

def add_mine(kind: str, folder: str) -> bool:
    ok = L._add_mine(state(), kind, folder, on=True)
    if ok:
        save_state()
    return ok


def set_mine_root(root: str, on: bool = True) -> None:
    """Every kind's own folders replaced by ``root``/<its sub-folder> (as a Shared library folder of before): tests,
    and a quick way to point the app at one library folder. '' = no own folders at all."""
    st = state()
    for k in L.KINDS:
        st["mine"][k.key] = [{"path": os.path.join(root, k.sub), "on": on, "ready": False}] if root else []
    REACH.forget()
    _WRITABLE.clear()
    save_state()


def mine_list(kind: str) -> list:
    return state()["mine"].setdefault(kind, [])


def set_on(kind: str, index: int, on: bool) -> None:
    lst = mine_list(kind)
    if 0 <= index < len(lst):
        lst[index]["on"] = bool(on)
        if on:
            try:
                os.makedirs(lst[index]["path"], exist_ok=True)
            except OSError:
                pass
        if all(f["on"] for k in L.KIND_KEYS for f in state()["mine"].get(k, []) if f.get("ready")):
            state()["note_off"] = False
        save_state()


def move_mine(kind: str, index: int, step: int) -> None:
    lst = mine_list(kind)
    j = index + step
    if 0 <= index < len(lst) and 0 <= j < len(lst):
        lst[index], lst[j] = lst[j], lst[index]
        save_state()


def remove_mine(kind: str, index: int) -> None:
    lst = mine_list(kind)
    if 0 <= index < len(lst):
        lst.pop(index)
        save_state()


# ---------------------------------------------------------------------------------------------------------------------
# export places

def places() -> list:
    return L.places(state(), setups())


def default_place() -> str:
    key = state()["exports"]["default"]
    return key if L.find_place(places(), key) else L.DEFAULT_PLACE


def project_name(scene=None) -> str:
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if stem:
        return stem
    try:
        from . import build
        roots = build.model_roots(scene or bpy.context.scene)
        src = roots[0].get(build.PROP_SOURCE, "") if roots else ""
        return os.path.splitext(os.path.basename(src))[0]
    except Exception:  # noqa: BLE001
        return ""


def place_of(scene):
    """The export place of this project: its own choice, else the user's default."""
    s = getattr(scene, "fresing", None) if scene is not None else None
    key = getattr(s, "out_place", "") if s is not None else ""
    all_ = places()
    return L.find_place(all_, key) or L.find_place(all_, default_place()) or all_[0]


def place_dir(place, scene=None) -> str:
    from . import render
    proj = bpy.path.abspath("//") if bpy.data.filepath else ""
    pfile = bpy.data.filepath or ""
    return L.place_folder(place, pfile if proj else "", project_name(scene) if scene is not None or pfile else "",
                          render.pictures_dir())


def output_dir(scene) -> str:
    """THE folder every output of this project goes to (pictures, the queue's videos and stills, 3D pages): the
    project's own folder when one was typed in (as before 0272), else its export place."""
    s = getattr(scene, "fresing", None) if scene is not None else None
    if s is not None and getattr(s, "out_folder", ""):
        return bpy.path.abspath(s.out_folder)
    return place_dir(place_of(scene), scene)


def also_dir(scene) -> str:
    """The folder of the "Also save a copy to" place, '' when off (or it is the same folder)."""
    ex = state()["exports"]
    if not ex["also"] or not ex["also_to"]:
        return ""
    pl = L.find_place(places(), ex["also_to"])
    if pl is None:
        return ""
    d = place_dir(pl, scene)
    return "" if L.same_path(d, output_dir(scene)) else d


def copy_also(scene, out: str) -> str:
    """Copy a finished output to the "also" place. Returns the copy ('' = none); a failure is printed, never
    raised – the output itself is saved."""
    d = also_dir(scene)
    if not d or not out or not os.path.exists(out):
        return ""
    try:
        return L.copy_output(out, d)
    except OSError as exc:
        print("Fresing Render: the copy to", d, "failed:", exc)
        return ""


# ---------------------------------------------------------------------------------------------------------------------
# different from standard

def differences() -> list:
    from . import settings_store
    p = _prefs()
    if p is None:
        return []
    spec = settings_store.spec()
    skip = {"settings_tab", "live_preview", "knows_ctrl_click", "make_open", "lifting_understood", "library_path",
            "window_places"}           # task 0276: where the app's windows were is no setting anyone chose
    values = {n: v for n, v in settings_store.current(p).items() if n not in skip}
    defaults = {n: k.default for n, k in spec.items()}
    return L.differences(values, defaults, setups(), state())


def back_to_standard(key: str) -> bool:
    """One of the user's own rows put back to the app's standard."""
    from . import settings_store
    if key.startswith("setting:"):
        p = _prefs()
        name = key.split(":", 1)[1]
        kind_ = settings_store.spec().get(name)
        if p is None or kind_ is None:
            return False
        setattr(p, name, kind_.default)
        return True
    if key.startswith("folder:"):
        _f, kind, idx = key.split(":", 2)
        lst = mine_list(kind)
        i = int(idx)
        if 0 <= i < len(lst):
            if lst[i].get("ready"):
                lst[i]["on"] = True
            else:
                lst.pop(i)
            save_state()
            return True
        return False
    ex = state()["exports"]
    if key == "export:default":
        ex["default"] = L.DEFAULT_PLACE
    elif key == "export:also":
        ex["also"] = False
    elif key.startswith("export:own:"):
        name = key.split(":", 2)[2]
        ex["own"] = [e for e in ex["own"] if e["name"] != name]
    else:
        return False
    save_state()
    return True


def user_content() -> dict:
    """{kind: first Mine folder that is on} – what "Save as a set-up file" can pack."""
    out = {}
    for k in L.KIND_KEYS:
        for f in mine_list(k):
            if f["on"] and os.path.isdir(f["path"]):
                out[k] = f["path"]
                break
    return out


def wait_reach(timeout: float = 5.0) -> None:
    """Tests: every folder looked at."""
    end = time.monotonic() + timeout
    for k in L.KIND_KEYS:
        REACH.settle([loc.path for loc in L.locations(state(), setups(), k, include_off=True)],
                     timeout=max(0.0, end - time.monotonic()))


_WHERE: dict = {}


def where_items(kind: str):
    """Items for a "Save in" choice of a dialog: the writable folders of a kind, Mine first (kept alive here)."""
    def items(self, context):
        lst = [(p, label, f"Saves into {p}") for p, label in save_choices(kind)]
        _WHERE[kind] = lst or [("NONE", "No folder you can save into", no_folder_text(kind))]
        return _WHERE[kind]
    return items


def where_value(value: str) -> str:
    return "" if value in ("", "NONE") else value


def also_name() -> str:
    pl = L.find_place(places(), state()["exports"]["also_to"])
    return pl.name if pl is not None else ""


def place_name(scene) -> str:
    return place_of(scene).name
