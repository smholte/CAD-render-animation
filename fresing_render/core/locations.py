"""Locations (task 0272): several folders per kind of thing the app reads, marked Company / Department / Mine, the
set-up file ``.frsetup`` that brings a company's or a department's folders and settings, and the export places.
No Blender here: the Blender side is ``blender/locations.py``.

**Kinds** (``KINDS``): STEP models, materials, logos, stickers, backgrounds (360° photos), templates, rule sets,
workspaces, brand kits, lifting equipment. Each has the sub-folder name it had in the old single "Shared library"
(``sub``), so a library folder of before keeps its layout.

**Levels:** Company and Department come from set-up files, Mine are the user's own folders. A list in the app shows
the items of every folder together, sorted by name, each with its badge; the same name in two places shows twice
(``merge``), never one hiding the other.

**A set-up file** is ONE zip ``<name>.frsetup``: ``setup.json`` (``FORMAT``, a fixed ``id``, name, level, label,
``version`` + date, who made it, the settings it sets, locations per kind, export places, first-start choices) and,
optionally, the content itself in folders named like the kinds' ``sub`` (``Logos/…``, ``Rule sets/…``). A file with
the same ``id`` is the same set-up whatever its file name: ``compare`` + ``changes`` say what an update changes.
``read_setup`` checks it with plain-word refusals (``SetupError``): not a zip, no ``setup.json``, not a Fresing
set-up, made by a newer app (what is left out is named in ``Setup.notes``), content of an unknown kind, a path that
would write outside its folder, a file over the size limit.

**The state file** ``fresing_locations.json`` (next to ``fresing_settings.json``) holds the user's set-ups (copied or
linked), the Mine folders per kind (each on or off), the export places and the default. ``migrate`` runs once: a
Shared library folder of before becomes Mine for every kind; without one the app makes its own ready-made folders
(``Documents\\Fresing Render\\Library``), switched off when a set-up file was there first.

**Reachable or not** (``Reach``): a folder on a server that does not answer is never waited for – it is looked at in a
helper thread; until the answer comes it counts as "checking" and its items are left out.
"""

from __future__ import annotations

import concurrent.futures
import copy
import datetime as _dt
import json
import os
import re
import tempfile
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field

FORMAT = "fresing-setup"
FORMAT_VERSION = 1
SETUP_EXT = ".frsetup"
SETUP_JSON = "setup.json"
STATE_FILE = "fresing_locations.json"
STATE_VERSION = 1
SETUPS_DIR = "fresing_setups"           # copies of set-up files and their unpacked content, in the config folder
READY_DIR = ("Fresing Render", "Library")    # the ready-made Mine folder under Documents

MAX_FILE = 200 * 1024 * 1024            # one file inside a set-up
MAX_TOTAL = 1024 * 1024 * 1024          # everything inside a set-up, unpacked
MAX_FILES = 20000


@dataclass(frozen=True)
class Kind:
    key: str
    title: str
    sub: str                     # the sub-folder name in a library folder and in a set-up file's content
    note: str = ""


KINDS = (
    Kind("step", "STEP models", "STEP models", "Import STEP… opens in the first one and lists them all on its left"),
    Kind("materials", "Materials", "Materials", "Read by the material picker (a later version)"),
    Kind("logos", "Logos", "Logos", "Decals: pictures in 5 Scene & Render > Decals"),
    Kind("stickers", "Stickers", "Stickers", "Decals: pictures in 5 Scene & Render > Decals"),
    Kind("backgrounds", "Backgrounds (360° photos)", "HDRI", ".exr / .hdr files for 5 Scene & Render > Background"),
    Kind("templates", "Templates", "Templates", "Template (.json) files: 3 Looks > Templates"),
    Kind("rule_sets", "Rule sets", "Rule sets", "3 Looks > Rule set"),
    Kind("workspaces", "Workspaces", "Workspaces", "Your own workspaces (Workspace at the top)"),
    Kind("brand_kits", "Brand kits", "Brand kits", "6 Animation > Finishing > Brand kit"),
    Kind("lifting", "Lifting equipment", "Lifting equipment", "8 Lifting plan: cranes, slings, mats you made"),
)
KIND_KEYS = tuple(k.key for k in KINDS)
BY_KEY = {k.key: k for k in KINDS}
BY_SUB = {k.sub.casefold(): k for k in KINDS}

LEVELS = {"company": "Company", "department": "Department", "mine": "Mine"}
ORDER = {"builtin": 0, "company": 1, "department": 2, "mine": 3}

BUILTIN_PLACES = (("project", "Next to the project (Renders)"),
                  ("pictures", "Pictures\\Fresing Render\\<project>"))
DEFAULT_PLACE = "project"            # owner, 21 Nov 17:39 (decision 0004): renders stay next to the project


class SetupError(Exception):
    """A set-up file that cannot be used; the message is in plain words for the user."""


def kind(key: str) -> Kind:
    if key not in BY_KEY:
        raise KeyError(f"no kind {key!r}")
    return BY_KEY[key]


def now_text() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------------------------------------------------
# the set-up file

@dataclass
class Setup:
    id: str
    name: str
    level: str = "company"
    label: str = ""
    version: int = 1
    date: str = ""
    made_by: str = ""
    app: str = ""                                    # the app version that wrote it
    settings: dict = field(default_factory=dict)     # name -> value of the app's settings (Fresing Settings)
    locations: dict = field(default_factory=dict)    # kind -> [path] (absolute, UNC, or relative to the file)
    exports: list = field(default_factory=list)      # [{"name", "path", "project_sub"}]
    first_start: dict = field(default_factory=dict)  # choices for the first-start set-up (task 0276)
    content: dict = field(default_factory=dict)      # kind -> [relative file names] packed inside
    notes: list = field(default_factory=list)        # what was left out when reading (a newer app's parts)

    @property
    def badge(self) -> str:
        return self.label.strip() or LEVELS.get(self.level, self.level.title())

    def title(self) -> str:
        return f"{self.badge} v{self.version}"

    def to_data(self) -> dict:
        return {"format": FORMAT, "format_version": FORMAT_VERSION, "id": self.id, "name": self.name,
                "level": self.level, "label": self.label, "version": int(self.version), "date": self.date,
                "made_by": self.made_by, "app": self.app, "settings": dict(self.settings),
                "locations": {k: list(v) for k, v in self.locations.items() if v},
                "exports": [dict(e) for e in self.exports], "first_start": dict(self.first_start)}


KNOWN_KEYS = {"format", "format_version", "id", "name", "level", "label", "version", "date", "made_by", "app",
              "settings", "locations", "exports", "first_start"}


def new_id() -> str:
    return uuid.uuid4().hex[:16]


RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
SKIP_FILES = {"thumbs.db", "desktop.ini", ".ds_store"}


def _is_dir_entry(name: str) -> bool:
    return name.endswith(("/", "\\"))


def _bad_name(name: str) -> str:
    """'' or why a name inside the zip may not be unpacked: a path that would leave its folder (absolute, a drive,
    '..'), or a name Windows cannot hold (a ':' – drives and hidden streams –, a device name such as CON or NUL, a
    trailing dot or space, <>"|?* or control characters). Checked before anything is written."""
    n = name.replace("\\", "/")
    if not n or n.startswith("/") or "\0" in n:
        return f"'{name}' is an absolute path"
    parts = [p for p in n.split("/") if p]
    for p in parts:
        if p.strip(" .") == "" and ".." in p or p == "..":
            return f"'{name}' points outside the set-up's folder"
        if ":" in p:
            return f"'{name}' names a drive or a hidden stream (':')"
        if p.split(".")[0].strip().casefold() in RESERVED:
            return f"'{name}' uses a name Windows keeps for devices ({p})"
        if p != p.rstrip(" ."):
            return f"'{name}' ends a name with a dot or a space, which Windows drops"
        if any(c in p for c in '<>"|?*') or any(ord(c) < 32 for c in p):
            return f"'{name}' has a character Windows does not allow in a file name"
    return ""


def _content_kind(name: str):
    """(Kind, relative path inside the kind's folder) of a file in the zip, or (None, top folder)."""
    parts = [p for p in name.replace("\\", "/").split("/") if p]
    if len(parts) < 2:
        return None, parts[0] if parts else ""
    k = BY_SUB.get(parts[0].casefold())
    return (k, "/".join(parts[1:])) if k else (None, parts[0])


def read_setup(path: str) -> Setup:
    """Read and check a set-up file. SetupError (plain words) when it cannot be used."""
    base = os.path.basename(path)
    if not os.path.isfile(path):
        raise SetupError(f"{base}: the file is not there")
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise SetupError(f"{base} is not a Fresing set-up file (it is not a zip file or it is damaged)") from exc
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILES:
            raise SetupError(f"{base} holds {len(infos)} files, more than the {MAX_FILES} a set-up may hold")
        total = 0
        content: dict = {}
        seen: dict = {}
        for info in infos:
            why = _bad_name(info.filename)
            if why:
                raise SetupError(f"{base} was refused: {why}")
            if info.is_dir() or _is_dir_entry(info.filename) or info.filename == SETUP_JSON:
                continue
            low = info.filename.replace("\\", "/").casefold()
            if low in seen:
                raise SetupError(f"{base} was refused: '{info.filename}' and '{seen[low]}' are one file on Windows "
                                 "(they differ only in capitals)")
            seen[low] = info.filename
            if info.file_size > MAX_FILE:
                raise SetupError(f"{base}: '{info.filename}' is {info.file_size // (1024 * 1024)} MB, more than the "
                                 f"{MAX_FILE // (1024 * 1024)} MB one file in a set-up may be")
            total += info.file_size
            k, rel = _content_kind(info.filename)
            if k is None:
                raise SetupError(f"{base}: the folder '{rel}' is no kind the app knows (it knows "
                                 + ", ".join(x.sub for x in KINDS) + ")")
            content.setdefault(k.key, []).append(rel)
        if total > MAX_TOTAL:
            raise SetupError(f"{base}: its content is {total // (1024 * 1024)} MB, more than the "
                             f"{MAX_TOTAL // (1024 * 1024)} MB a set-up may hold")
        try:
            raw = zf.read(SETUP_JSON)
        except KeyError:
            raise SetupError(f"{base} is not a Fresing set-up file (it has no {SETUP_JSON})") from None
        except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
            raise SetupError(f"{base} is damaged ({exc})") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SetupError(f"{base}: its {SETUP_JSON} cannot be read ({exc})") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise SetupError(f"{base} is not a Fresing set-up file")
    s = from_data(data, base)
    for k in content:
        content[k].sort(key=str.casefold)
    s.content = content
    return s


def from_data(data: dict, base: str = "the set-up") -> Setup:
    notes = []
    fv = data.get("format_version", 1)
    if not isinstance(fv, int) or fv < 1:
        raise SetupError(f"{base}: its format version {fv!r} is not a number")
    left = sorted(k for k in data if k not in KNOWN_KEYS)
    if fv > FORMAT_VERSION:
        notes.append(f"Made by a newer app (set-up format {fv}, this app reads {FORMAT_VERSION})"
                     + (": left out " + ", ".join(left) if left else ""))
    sid = str(data.get("id") or "").strip()
    if not sid or not re.match(r"^[A-Za-z0-9_.-]{1,64}$", sid):
        raise SetupError(f"{base}: it has no valid id")
    level = data.get("level", "company")
    if level not in ("company", "department"):
        raise SetupError(f"{base}: its level '{level}' is neither company nor department")
    try:
        version = int(data.get("version", 1))
    except (TypeError, ValueError):
        raise SetupError(f"{base}: its version is not a number") from None
    locs = {}
    for k, v in (data.get("locations") or {}).items():
        if k not in BY_KEY:
            notes.append(f"Left out the locations of '{k}' (a kind this app does not know)")
            continue
        if isinstance(v, str):
            v = [v]
        locs[k] = [str(p) for p in v if str(p).strip()]
    exports = []
    for e in data.get("exports") or []:
        if isinstance(e, dict) and str(e.get("name", "")).strip() and str(e.get("path", "")).strip():
            exports.append({"name": str(e["name"]).strip(), "path": str(e["path"]).strip(),
                            "project_sub": bool(e.get("project_sub", True))})
    settings = data.get("settings") or {}
    if not isinstance(settings, dict):
        raise SetupError(f"{base}: its settings are not a list of names and values")
    return Setup(id=sid, name=str(data.get("name") or sid), level=level, label=str(data.get("label") or ""),
                 version=max(1, version), date=str(data.get("date") or ""), made_by=str(data.get("made_by") or ""),
                 app=str(data.get("app") or ""), settings=dict(settings), locations=locs, exports=exports,
                 first_start=dict(data.get("first_start") or {}), notes=notes)


def write_setup(path: str, setup: Setup, content: dict | None = None) -> str:
    """Write a set-up file: ``content`` = {kind: folder} packed under the kind's sub-folder. The file is written next
    to its place and moved over it, so a reader never sees half a file."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(folder, exist_ok=True)
    packed: dict = {}
    fd, tmp = tempfile.mkstemp(prefix=".frsetup-", suffix=".tmp", dir=folder)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            total = 0
            for key, src in (content or {}).items():
                if not src or not os.path.isdir(src):
                    continue
                sub = kind(key).sub
                for dirpath, dirs, files in os.walk(src):
                    dirs.sort()
                    for f in sorted(files):
                        if f.startswith(".") or f.casefold() in SKIP_FILES:
                            continue
                        full = os.path.join(dirpath, f)
                        rel = os.path.relpath(full, src).replace(os.sep, "/")
                        size = os.path.getsize(full)
                        if size > MAX_FILE:
                            raise SetupError(f"'{rel}' in {src} is {size // (1024 * 1024)} MB, more than the "
                                             f"{MAX_FILE // (1024 * 1024)} MB one file in a set-up may be")
                        total += size
                        if total > MAX_TOTAL:
                            raise SetupError(f"The content is more than {MAX_TOTAL // (1024 * 1024)} MB")
                        zf.write(full, f"{sub}/{rel}")
                        packed.setdefault(key, []).append(rel)
            zf.writestr(SETUP_JSON, json.dumps(setup.to_data(), indent=1, ensure_ascii=False))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    setup.content = {k: sorted(v, key=str.casefold) for k, v in packed.items()}
    return path


def unpack(path: str, dest: str) -> dict:
    """Unpack a set-up's content into ``dest/<sub>/…`` (``dest`` emptied first). {kind: folder} of what it holds."""
    import shutil
    read_setup(path)                                  # the checks first: nothing written for a refused file
    new = dest.rstrip("\\/") + ".new"
    shutil.rmtree(new, ignore_errors=True)
    os.makedirs(new, exist_ok=True)
    out = {}
    root = os.path.realpath(new)
    try:
        with zipfile.ZipFile(path) as zf:
            for info in zf.infolist():
                if info.is_dir() or _is_dir_entry(info.filename) or info.filename == SETUP_JSON:
                    continue
                k, rel = _content_kind(info.filename)
                target = os.path.realpath(os.path.join(new, k.sub, *rel.replace("\\", "/").split("/")))
                try:
                    inside = os.path.commonpath([root, target]) == root
                except ValueError:                    # another drive (Windows)
                    inside = False
                if not inside:                        # second guard (links, odd names)
                    raise SetupError(f"'{info.filename}' points outside the set-up's folder")
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                out[k.key] = os.path.join(dest, k.sub)
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)        # the old content stays as it was
        raise
    old = dest.rstrip("\\/") + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(dest):
        os.replace(dest, old)
    os.replace(new, dest)
    shutil.rmtree(old, ignore_errors=True)
    return out


def content_dirs(dest: str) -> dict:
    """{kind: folder} of an unpacked set-up's content folders that are there."""
    out = {}
    for k in KINDS:
        p = os.path.join(dest, k.sub)
        if os.path.isdir(p):
            out[k.key] = p
    return out


def compare(old: Setup, new: Setup) -> str:
    """'newer', 'older' or 'same' (by the set-up's own version number)."""
    if new.version > old.version:
        return "newer"
    if new.version < old.version:
        return "older"
    return "same"


def changes(old: Setup | None, new: Setup) -> list:
    """What taking ``new`` in place of ``old`` changes, one plain line each (empty: nothing)."""
    if old is None:
        return ["New set-up: " + new.title()]
    out = []
    if old.version != new.version:
        out.append(f"Version {old.version} → {new.version}")
    for attr, title in (("name", "Name"), ("level", "Level"), ("label", "Label")):
        a, b = getattr(old, attr), getattr(new, attr)
        if a != b:
            out.append(f"{title}: {a or '–'} → {b or '–'}")
    for name in sorted(set(old.settings) | set(new.settings)):
        a, b = old.settings.get(name), new.settings.get(name)
        if a != b:
            if name not in old.settings:
                out.append(f"Setting {name}: set to {b!r}")
            elif name not in new.settings:
                out.append(f"Setting {name}: no longer set (was {a!r})")
            else:
                out.append(f"Setting {name}: {a!r} → {b!r}")
    for k in KINDS:
        a, b = old.locations.get(k.key, []), new.locations.get(k.key, [])
        for p in b:
            if p not in a:
                out.append(f"{k.title}: folder added {p}")
        for p in a:
            if p not in b:
                out.append(f"{k.title}: folder removed {p}")
    ea = {e["name"]: e for e in old.exports}
    eb = {e["name"]: e for e in new.exports}
    for n in eb:
        if n not in ea:
            out.append(f"Export place added: {n} ({eb[n]['path']})")
        elif ea[n] != eb[n]:
            out.append(f"Export place changed: {n} ({ea[n]['path']} → {eb[n]['path']})")
    for n in ea:
        if n not in eb:
            out.append(f"Export place removed: {n}")
    for k in KINDS:
        a, b = set(old.content.get(k.key, [])), set(new.content.get(k.key, []))
        if b - a:
            out.append(f"{k.title}: {_count(len(b - a), 'file')} added ({_few(b - a)})")
        if a - b:
            out.append(f"{k.title}: {_count(len(a - b), 'file')} removed ({_few(a - b)})")
    if old.first_start != new.first_start:
        out.append("First-start choices changed")
    return out


def content_changed(old_dir: str, new_path: str) -> list:
    """Files of the same name whose size or bytes differ between an unpacked set-up and a new file."""
    out = []
    if not os.path.isdir(old_dir):
        return out
    with zipfile.ZipFile(new_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or info.filename == SETUP_JSON:
                continue
            k, rel = _content_kind(info.filename)
            if k is None:
                continue
            old = os.path.join(old_dir, k.sub, *rel.split("/"))
            if os.path.isfile(old):
                if os.path.getsize(old) != info.file_size:
                    out.append(f"{k.title}: {rel} changed")
                else:
                    with open(old, "rb") as fh:
                        if fh.read() != zf.read(info):
                            out.append(f"{k.title}: {rel} changed")
    return out


def _count(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _few(names) -> str:
    names = sorted(names, key=str.casefold)
    return ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")


# ---------------------------------------------------------------------------------------------------------------------
# the state file

def empty_state() -> dict:
    return {"state_version": STATE_VERSION, "migrated": False, "setups": [], "mine": {k: [] for k in KIND_KEYS},
            "exports": {"default": DEFAULT_PLACE, "also": False, "also_to": "", "own": []},
            "note_off": False, "updated": []}


def read_state(path: str) -> tuple:
    """(state, note): the state from its file; a missing file gives an empty state, a damaged one too with a note
    (and a copy of it kept beside it, so nothing is lost)."""
    st = empty_state()
    if not os.path.isfile(path):
        return st, ""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("not a list of settings")
    except (OSError, ValueError) as exc:
        try:
            import shutil
            shutil.copyfile(path, path + ".damaged")
        except OSError:
            pass
        return st, f"The locations file could not be read ({exc}): your folders start as new; a copy was kept"
    for key in ("migrated", "note_off"):
        st[key] = bool(data.get(key, st[key]))
    for s in data.get("setups") or []:
        if isinstance(s, dict) and s.get("id") and s.get("file"):
            st["setups"].append({k: s.get(k) for k in ("id", "mode", "source", "file", "version", "name", "level",
                                                       "label", "stamp", "auto")})
    mine = data.get("mine") or {}
    for k in KIND_KEYS:
        for f in mine.get(k) or []:
            if isinstance(f, dict) and str(f.get("path", "")).strip():
                st["mine"][k].append({"path": str(f["path"]), "on": bool(f.get("on", True)),
                                      "ready": bool(f.get("ready", False))})
    ex = data.get("exports") or {}
    st["exports"]["default"] = str(ex.get("default") or DEFAULT_PLACE)
    st["exports"]["also"] = bool(ex.get("also", False))
    st["exports"]["also_to"] = str(ex.get("also_to") or "")
    for e in ex.get("own") or []:
        if isinstance(e, dict) and str(e.get("name", "")).strip() and str(e.get("path", "")).strip():
            st["exports"]["own"].append({"name": str(e["name"]), "path": str(e["path"]),
                                         "project_sub": bool(e.get("project_sub", True))})
    st["updated"] = [u for u in (data.get("updated") or []) if isinstance(u, dict)]
    return st, ""


def write_state(path: str, state: dict, tries: int = 5) -> None:
    """Written to a temporary file of its own, then moved over the old one; a refusal (another program holds the
    file for a moment) is tried again a few times, and the temporary file never stays behind."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".fresing_locations-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, ensure_ascii=False)
        for i in range(tries):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if i == tries - 1:
                    raise
                time.sleep(0.1)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def ready_root(documents: str) -> str:
    return os.path.join(documents, *READY_DIR)


def migrate(state: dict, library_path: str, documents: str, has_setups: bool) -> list:
    """Run once (``state["migrated"]``): the old Shared library folder becomes Mine for every kind; without one the
    ready-made folders are added (switched off when a set-up was there first – then ``note_off`` asks for the note).
    Folders the app used before without a library (Documents\\Fresing Render\\Rule sets …) stay as Mine too.
    Returns the folders to make (the caller makes them). Nothing is moved."""
    if state.get("migrated"):
        return []
    make = []
    lib = (library_path or "").strip()
    if lib:
        for k in KINDS:
            _add_mine(state, k.key, os.path.join(lib, k.sub), on=True)
    else:
        root = ready_root(documents)
        old = os.path.join(documents, "Fresing Render")
        for k in KINDS:
            p = os.path.join(root, k.sub)
            _add_mine(state, k.key, p, on=not has_setups, ready=True)
            make.append(p)
            was = os.path.join(old, k.sub)        # where rule sets, workspaces, logos, brand kits went before
            if k.key in ("rule_sets", "workspaces", "logos", "stickers", "brand_kits") and _has_files(was):
                _add_mine(state, k.key, was, on=True)
        if has_setups:
            state["note_off"] = True
    state["migrated"] = True
    return make


def _has_files(folder: str) -> bool:
    try:
        return any(not n.startswith(".") for n in os.listdir(folder))
    except OSError:
        return False


def _add_mine(state, key, path, on=True, ready=False) -> bool:
    lst = state["mine"].setdefault(key, [])
    if any(same_path(f["path"], path) for f in lst):
        return False
    lst.append({"path": path, "on": on, "ready": ready})
    return True


def same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a or "")) == os.path.normcase(os.path.normpath(b or ""))


# ---------------------------------------------------------------------------------------------------------------------
# resolving folders

def is_unc(path: str) -> bool:
    return path.startswith("\\\\") or path.startswith("//")


def resolve(path: str, base: str) -> str:
    """A folder named in a set-up: absolute (``C:\\…``, ``\\\\server\\share\\…``, ``/…``) as it is, ``~`` expanded,
    else relative to the folder of the set-up file (a set-up kept in a synced folder works wherever it lands)."""
    p = os.path.expandvars(os.path.expanduser(path.strip()))
    if re.match(r"^[A-Za-z]:(?![\\/])", p):               # "X:Logos" (drive-relative): taken as X:\Logos
        p = p[:2] + "\\" + p[2:]
    if is_unc(p) or os.path.isabs(p) or re.match(r"^[A-Za-z]:[\\/]", p):
        return p
    return os.path.normpath(os.path.join(base, p.replace("\\", os.sep).replace("/", os.sep)))


@dataclass
class Loc:
    kind: str
    path: str
    level: str                     # builtin / company / department / mine
    badge: str
    source: str                    # a set-up's id, "mine", "builtin"
    on: bool = True
    ready: bool = False            # a ready-made Mine folder
    packed: bool = False           # a set-up's own content (read-only)
    index: int = -1                # the Mine folder's index in the state (for up / down / remove)
    reach: object = None           # True / False / None (being looked at), set by the Blender side


def locations(state: dict, setups: list, key: str, include_off: bool = False) -> list:
    """Every folder of a kind, in order: company set-ups, department set-ups, then Mine (top = first choice).
    ``setups`` = [(Setup, file's folder, unpacked content folder or "")], in the order the user added them."""
    out = []
    for lvl in ("company", "department"):
        for s, base, unpacked in setups:
            if s.level != lvl:
                continue
            if unpacked and key in s.content:
                out.append(Loc(key, os.path.join(unpacked, kind(key).sub), lvl, s.badge, s.id, packed=True))
            for p in s.locations.get(key, []):
                out.append(Loc(key, resolve(p, base), lvl, s.badge, s.id))
    for i, f in enumerate(state["mine"].get(key, [])):
        if f["on"] or include_off:
            out.append(Loc(key, f["path"], "mine", "Mine", "mine", on=f["on"], ready=f.get("ready", False), index=i))
    return out


def unique_keys(entries: list) -> list:
    """Keys for a list of (name, badge): the name itself for its first place, "name (badge)" for the others – so
    the same name in two places is listed twice, each findable."""
    taken: set = set()
    out = []
    for name, badge in entries:
        key = name
        if key.casefold() in taken:
            key, n = f"{name} ({badge})", 2
            while key.casefold() in taken:
                key, n = f"{name} ({badge} {n})", n + 1
        taken.add(key.casefold())
        out.append(key)
    return out


def merge(items: list) -> list:
    """Sort (name, Loc, payload) by name, then by level (company before department before mine) and folder order;
    every entry kept."""
    return sorted(items, key=lambda it: (it[0].casefold(), ORDER.get(it[1].level, 9)))


def writable(path: str) -> bool:
    """Can new files go there (the folder, or the first folder above it that exists). Tried for real – a small file
    made and deleted – because on Windows ``os.access`` says yes to every folder, whatever the share's rights."""
    p = os.path.abspath(path)
    while p and not os.path.isdir(p):
        up = os.path.dirname(p)
        if up == p:
            return False
        p = up
    if not os.access(p, os.W_OK):
        return False
    try:
        fd, probe = tempfile.mkstemp(prefix=".fresing-write-", dir=p)
        os.close(fd)
        os.remove(probe)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------------------------------------------------
# reachable or not, without waiting

SLOW_ENV = "FRESING_LOCATIONS_SLOW"       # tests: "<path prefix>=<seconds>" makes looking at such a folder slow


class Reach:
    """Whether folders can be reached, looked at in helper threads. ``state(path)`` never blocks longer than
    ``wait`` seconds: True (there), False (not there / no answer within ``timeout``), None (still looking)."""

    def __init__(self, ttl: float = 30.0, timeout: float = 8.0, wait: float = 0.05, workers: int = 8):
        self.ttl, self.timeout, self.wait = ttl, timeout, wait
        # two pools: folders on a server (\\\\server\\share) never hold up the PC's own folders behind them
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fr-reach")
        self._net = concurrent.futures.ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fr-reach-net")
        self._lock = threading.Lock()
        self._known: dict = {}        # path -> (answer, time)
        self._busy: dict = {}         # path -> (future, started)
        self.on_change = None         # called (from a helper thread) when an answer changed

    @staticmethod
    def _look(path: str) -> bool:
        slow = os.environ.get(SLOW_ENV, "")
        if slow and "=" in slow:
            prefix, secs = slow.rsplit("=", 1)
            if path.startswith(prefix):
                time.sleep(float(secs))
        return os.path.isdir(path)

    def _done(self, path, fut):
        try:
            ok = bool(fut.result())
        except Exception:  # noqa: BLE001 - any error: cannot be reached
            ok = False
        with self._lock:
            old = self._known.get(path, (None, 0))[0]
            self._known[path] = (ok, time.monotonic())
            self._busy.pop(path, None)
        if old != ok and self.on_change:
            try:
                self.on_change(path, ok)
            except Exception:  # noqa: BLE001
                pass

    def state(self, path: str):
        """True / False / None (never looked at, answer not in yet). A stale answer is looked at again in the
        background; its new answer is given when it comes within ``wait`` seconds, else the last one."""
        now = time.monotonic()
        with self._lock:
            known = self._known.get(path)
            busy = self._busy.get(path)
            if busy is not None and now - busy[1] > self.timeout and (known is None or known[0] is not False):
                self._known[path] = (False, now)          # no answer in time: counts as not there, still looking
                known = self._known[path]
            fresh = known is not None and now - known[1] < self.ttl
            start = not fresh and busy is None
            if start:
                fut = (self._net if is_unc(path) else self._pool).submit(self._look, path)
                self._busy[path] = busy = (fut, now)
        if start:                                         # outside the lock: a done future calls back at once
            fut.add_done_callback(lambda f, p=path: self._done(p, f))
        if busy is not None and self.wait > 0 and (start or known is None):
            try:
                busy[0].result(timeout=self.wait)
            except Exception:  # noqa: BLE001 - not yet (or failed): the record says
                pass
        with self._lock:
            k = self._known.get(path)
        return k[0] if k is not None else None

    def mark(self, path: str, ok: bool = True) -> None:
        """The app itself just made (or saw) the folder: no need to look."""
        with self._lock:
            self._known[path] = (bool(ok), time.monotonic())

    def forget(self, path: str | None = None) -> None:
        """Look again at the next ask (the last answer is kept meanwhile: a server that does not answer keeps its
        old answer, nothing flickers)."""
        with self._lock:
            for p in (list(self._known) if path is None else [path]):
                if p in self._known:
                    self._known[p] = (self._known[p][0], -1e9)

    def settle(self, paths, timeout: float = 5.0) -> None:
        """Tests: wait until every path has an answer."""
        end = time.monotonic() + timeout
        for p in paths:
            while self.state(p) is None and time.monotonic() < end:
                time.sleep(0.01)


# ---------------------------------------------------------------------------------------------------------------------
# export places

@dataclass
class Place:
    key: str
    name: str
    path: str                     # '' for the two built-in ones
    project_sub: bool = True
    level: str = "builtin"
    badge: str = "Built-in"


def places(state: dict, setups: list) -> list:
    out = [Place(k, n, "") for k, n in BUILTIN_PLACES]
    for s, base, _unpacked in setups:
        for e in s.exports:
            out.append(Place(f"{s.id}:{e['name']}", e["name"], resolve(e["path"], base), e.get("project_sub", True),
                             s.level, s.badge))
    for e in state["exports"]["own"]:
        out.append(Place("mine:" + e["name"], e["name"], e["path"], e.get("project_sub", True), "mine", "Mine"))
    return out


def find_place(all_places: list, key: str):
    return next((p for p in all_places if p.key == key), None)


def safe_folder(name: str) -> str:
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name or "").strip(" .")
    if n.split(".")[0].strip().casefold() in RESERVED:     # CON, NUL, COM1 …: Windows cannot make such a folder
        n = "_" + n
    return n or "Project"


def place_folder(place: Place, project_file: str, project_name: str, pictures: str) -> str:
    """The folder an output goes to in a place. Next to the project: its Renders folder (a project never saved:
    Pictures\\Fresing Render, as before); Pictures: Pictures\\Fresing Render\\<project>; a named place: its folder,
    with the project's name as a sub-folder when the place says so."""
    sub = safe_folder(project_name) if project_name else ""
    if place.key == "project":
        if project_file:
            return os.path.join(os.path.dirname(project_file), "Renders")
        return os.path.join(pictures, "Fresing Render")
    if place.key == "pictures":
        return os.path.join(pictures, "Fresing Render", sub) if sub else os.path.join(pictures, "Fresing Render")
    return os.path.join(place.path, sub) if (place.project_sub and sub) else place.path


def free_name(folder: str, name: str) -> str:
    """A path in ``folder`` for ``name`` that is not taken (``name_2`` …): a copy never overwrites."""
    stem, ext = os.path.splitext(name)
    path = os.path.join(folder, name)
    n = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem}_{n}{ext}")
        n += 1
    return path


def copy_output(src: str, folder: str) -> str:
    """Copy a finished output (a file, or a folder of frames) into ``folder``. Returns the copy's path."""
    import shutil
    os.makedirs(folder, exist_ok=True)
    dst = free_name(folder, os.path.basename(src.rstrip("\\/")))
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)
    return dst


# ---------------------------------------------------------------------------------------------------------------------
# different from standard

@dataclass
class Row:
    key: str           # "setting:<name>", "folder:<kind>:<index>", "export:default", "setup:<id>"
    what: str
    value: str
    source: str        # "Company v4", "Offshore department v2", "Mine"
    own: bool          # the user's own: Back to standard is offered


def differences(values: dict, defaults: dict, setups: list, state: dict) -> list:
    """Every setting and folder that differs from the app's standard, with where it comes from."""
    out = []
    for name in sorted(values):
        v, d = values[name], defaults.get(name)
        if _same(v, d):
            continue
        src = next((s for s, _b, _u in setups if name in s.settings and _same(s.settings[name], v)), None)
        out.append(Row("setting:" + name, name, _show(v), src.title() if src else "Mine", src is None))
    for s, base, unpacked in setups:
        for k in KINDS:
            for p in s.locations.get(k.key, []):
                out.append(Row(f"setup:{s.id}", k.title, resolve(p, base), s.title(), False))
            if unpacked and k.key in s.content:
                out.append(Row(f"setup:{s.id}", k.title, f"{len(s.content[k.key])} files inside the set-up",
                               s.title(), False))
        for e in s.exports:
            out.append(Row(f"setup:{s.id}", "Export place", f"{e['name']}: {e['path']}", s.title(), False))
    for k in KINDS:
        for i, f in enumerate(state["mine"].get(k.key, [])):
            if f.get("ready") and f["on"]:
                continue                                  # the ready-made folders are the standard
            what = k.title + ("" if f["on"] else " (switched off)")
            out.append(Row(f"folder:{k.key}:{i}", what, f["path"], "Mine", True))
    ex = state["exports"]
    if ex["default"] != DEFAULT_PLACE:
        out.append(Row("export:default", "Default export place", ex["default"].split(":", 1)[-1], "Mine", True))
    if ex["also"]:
        out.append(Row("export:also", "Also a copy to", ex["also_to"].split(":", 1)[-1] or "–", "Mine", True))
    for e in ex["own"]:
        out.append(Row("export:own:" + e["name"], "Export place", f"{e['name']}: {e['path']}", "Mine", True))
    return out


def _same(a, b) -> bool:
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) < 1e-6
        except (TypeError, ValueError):
            return False
    return a == b


def _show(v) -> str:
    if isinstance(v, (list, tuple)):
        return "(" + ", ".join(f"{x:.3g}" if isinstance(x, float) else str(x) for x in v) + ")"
    if isinstance(v, bool):
        return "on" if v else "off"
    return str(v) if v != "" else "(empty)"


def deep(state: dict) -> dict:
    return copy.deepcopy(state)
