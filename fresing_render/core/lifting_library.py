"""Lifting equipment library (task 0190, Lifting lane L2): the user's own cranes, forklifts, hoists and rigging gear as
plain files – plain Python, no Blender.

One item = one folder: ``<name>/<name>.json`` + the model (``.step``/``.stp``, ``.glb``, ``.obj``, ``.fbx``) + an
optional picture (``.png``/``.jpg``/``.jpeg``/``.webp``). Copying the folder shares the item. The user's library is
``prefs.library_dir("Lifting equipment")`` (the Blender side passes it in); the built-ins are read-only in
``fresing_render/data/lifting/<class>/`` (task 0191) and carry ``"sample": true``.

The file (study 0180 section 4)::

    {
      "format": "fresing-lifting-equipment",   # required
      "format_version": "1.0",                 # "major.minor"; a higher major is refused, a lower one upgraded
      "kind": "mobile_crane",                  # required: what it is (KINDS lists the known ones; others are kept)
      "class": "AT-100",                       # size class (the app's class names, never a make)
      "name": "AT-100",                        # required: the name shown in the app
      "units": {"mass": "t", "length": "m"},   # every mass / length below is in these (t, kg, lb / m, mm, ft)
      "mass": {"carrier": 30.0, ...},          # mass per moving group (or one number)
      "cog": {"carrier": [0.5, 0, 1.2], ...},  # centre of gravity per group (or one [x, y, z]) in the model's frame
      "rig": {...},                            # the render-kit sheet's joints / cylinders / poses, by part names
      "charts": [                              # load charts, one per configuration (lifting.chart_from_dict)
        {"config": {"boom": 30.4, "counterweight": 40, "outriggers": 7.0, "hs": 1.5},
         "radius": [8, 10, 12], "capacity": [36.0, 29.5, null],     # null = a gap: not allowed there
         "wind_max": 9.8, "includes_hook_block": false, "interpolate": false}],
      "hook_blocks": [{"name": "main", "mass": 0.85, "sheaves": 5}],
      "outriggers": {...}, "tracks": {...}, "axles": {...},          # footprint data for checks C5 / C6
      "wll": 8.0,                              # rigging gear: working load limit (or {"straight": 8.0, "choke": 6.4})
      "limits": {...},                         # slew range, angles …
      "sample": true,                          # built-ins and unchanged copies of them: SAMPLE DATA
      "derived_from": "sha256:…",              # a copy of a sample: the sample's chart hash (chart_hash)
      "source": "maker chart no. …, entered by …, date"
    }

Config keys: ``boom``, ``jib``, ``outriggers`` in the length unit, ``counterweight`` in the mass unit, ``hs``
(significant wave height) always in metres; other keys are kept as they are. Fields this version does not know are
kept on write and named in a note. Messages are plain sentences; refused chart entries name their row.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field

from . import lifting

FORMAT = "fresing-lifting-equipment"
FORMAT_VERSION = "1.0"
MAJOR = 1

MODEL_EXTS = (".step", ".stp", ".glb", ".obj", ".fbx")
PICTURE_EXTS = (".png", ".jpg", ".jpeg", ".webp")
BUILTIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "lifting")

KINDS = (
    "mobile_crane", "crawler_crane", "knuckle_boom_crane", "other_crane", "offshore_crane", "vessel_crane", "overhead_crane",
    "tower_crane", "forklift", "telehandler", "chain_hoist", "spreader_beam", "lifting_frame", "sling", "shackle",
    "hook_block", "lifting_tool",
)
FIELDS = (
    "format", "format_version", "kind", "class", "name", "units", "mass", "cog", "rig", "charts", "hook_blocks",
    "outriggers", "tracks", "axles", "wll", "limits", "sample", "derived_from", "source",
)
SAMPLE_STILL = ("These are still the sample's charts: the SAMPLE mark stays. Enter the chart of your real equipment "
                "first.")
NEWER = "Made with a newer Fresing Render (format {v}) – update the app"


class LibraryError(ValueError):
    """A refusal, in plain words."""


# ---------------------------------------------------------------------------------------------------------------------
# Small helpers

def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _no_constants(name):
    raise ValueError(f"{name} is not a number")


def _load_json(path: str):
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh, parse_constant=_no_constants)


def units_of(data: dict) -> tuple[str, str]:
    """(mass unit, length unit) of a file; t and m when it gives none. Raises LibraryError on unknown units."""
    u = data.get("units", {"mass": "t", "length": "m"}) if isinstance(data, dict) else None
    mass, length = "t", "m"
    if isinstance(u, dict):
        mass, length = u.get("mass", "t"), u.get("length", "m")
    elif isinstance(u, (list, tuple)) or isinstance(u, str):
        parts = re.split(r"[\s,;/]+", u.strip()) if isinstance(u, str) else list(u)
        for p in parts:
            if p in lifting.MASS_UNITS:
                mass = p
            elif p in lifting.LENGTH_UNITS:
                length = p
            elif p:
                raise LibraryError(f"Unknown unit '{p}' (masses: t, kg, lb; lengths: m, mm, ft).")
    else:
        raise LibraryError("'units' must look like {\"mass\": \"t\", \"length\": \"m\"}.")
    if mass not in lifting.MASS_UNITS:
        raise LibraryError(f"Unknown mass unit '{mass}' (use t, kg or lb).")
    if length not in lifting.LENGTH_UNITS:
        raise LibraryError(f"Unknown length unit '{length}' (use m, mm or ft).")
    return mass, length


def _version(v) -> tuple[int, int] | None:
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"\s*(\d+)(?:\.(\d+))?\s*", v)
    return (int(m.group(1)), int(m.group(2) or 0)) if m else None


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def folder_name(name: str) -> str:
    """A folder / file name for an item's name that works on Windows."""
    s = _BAD_CHARS.sub("_", str(name)).strip().rstrip(". ")
    if not s:
        raise LibraryError("The item needs a name.")
    if s.split(".")[0].upper() in _RESERVED:
        s += "_"
    return s


def _inside(path: str, folder: str) -> bool:
    try:
        p, f = os.path.realpath(path), os.path.realpath(folder)
        return os.path.commonpath([p, f]) == f
    except ValueError:  # other drive on Windows
        return False


# ---------------------------------------------------------------------------------------------------------------------
# Upgrades: format major -> function that turns a dict of that major into the next one (in memory)

def _from_0(d: dict) -> dict:
    """Format 0 (the study's draft, no "format_version"): ``units`` was a list ["t", "m"]."""
    d = dict(d)
    if isinstance(d.get("units"), (list, tuple, str)):
        mass, length = units_of(d)
        d["units"] = {"mass": mass, "length": length}
    d["format_version"] = "1.0"
    return d


_UPGRADES = {0: _from_0}


# ---------------------------------------------------------------------------------------------------------------------
# The item

@dataclass
class Item:
    """One piece of equipment as read: its file's data (upgraded in memory) and what was found wrong with it."""

    data: dict
    folder: str = ""
    path: str = ""
    builtin: bool = False
    problems: list = field(default_factory=list)  # refusals: the item is listed but not used in checks
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)      # unknown fields, upgrades
    newer: bool = False                            # a newer format major: not read further, never written
    upgraded_from: str | None = None
    model: str | None = None
    picture: str | None = None

    @property
    def kind(self) -> str:
        return str(self.data.get("kind", "")) if isinstance(self.data, dict) else ""

    @property
    def cls(self) -> str:
        return str(self.data.get("class", "")) if isinstance(self.data, dict) else ""

    @property
    def name(self) -> str:
        if isinstance(self.data, dict) and isinstance(self.data.get("name"), str) and self.data["name"].strip():
            return self.data["name"]
        return os.path.basename(self.folder.rstrip("/\\")) if self.folder else ""

    @property
    def sample(self) -> bool:
        return is_sample(self)

    @property
    def ok(self) -> bool:
        return not self.problems


def new_item(kind: str, cls: str, name: str, mass_unit: str = "t", length_unit: str = "m", **fields) -> dict:
    """A new equipment file's data (not written yet)."""
    d = {"format": FORMAT, "format_version": FORMAT_VERSION, "kind": kind, "class": cls, "name": name,
         "units": {"mass": mass_unit, "length": length_unit}, "charts": [], "sample": False, "source": ""}
    d.update(fields)
    units_of(d)
    return d


def unknown_fields(data: dict) -> list[str]:
    return [k for k in data if k not in FIELDS] if isinstance(data, dict) else []


def _check_vec(v) -> bool:
    return isinstance(v, (list, tuple)) and len(v) == 3 and all(_num(x) for x in v)


def _read_charts(data: dict, mass: str, length: str, problems: list) -> list:
    charts = data.get("charts", [])
    if charts is None:
        return []
    if not isinstance(charts, list):
        problems.append("'charts' must be a list of charts.")
        return []
    out = []
    for i, d in enumerate(charts):
        if not isinstance(d, dict):
            problems.append(f"Chart {i + 1}: cannot be read (not a table of radius and capacity).")
            continue
        if not isinstance(d.get("radius", []), list) or not isinstance(d.get("capacity", []), list):
            problems.append(f"Chart {i + 1}: 'radius' and 'capacity' must be lists.")
            continue
        if not isinstance(d.get("config", {}), dict):
            problems.append(f"Chart {i + 1}: 'config' must look like {{\"boom\": 30.4}}.")
            continue
        bad = [k for k in ("boom", "jib", "outriggers", "counterweight", "hs")
               if k in d.get("config", {}) and not _num(d["config"][k])]
        if bad:
            problems.append(f"Chart {i + 1}: '{bad[0]}' in its configuration must be a number "
                            f"({d['config'][bad[0]]!r}).")
            continue
        if d.get("wind_max") is not None and not _num(d.get("wind_max")):
            problems.append(f"Chart {i + 1}: 'wind_max' must be a number (m/s).")
            continue
        try:
            c = lifting.chart_from_dict(d, mass, length)
        except (TypeError, ValueError, AttributeError) as e:
            problems.append(f"Chart {i + 1}: cannot be read ({e}).")
            continue
        if not c.name:
            c.name = d.get("name") or (_config_words(c.config) if c.config else f"chart {i + 1}")
        out.append(c)
    return out


def _config_words(config: dict) -> str:
    """'boom 30.4 m, counterweight 40 t' (SI config)."""
    parts = []
    for k, v in config.items():
        if not _num(v):
            parts.append(f"{k} {v}")
        elif k in ("boom", "jib", "outriggers", "hs"):
            parts.append(f"{'Hs' if k == 'hs' else k} {v:g} m")
        elif k == "counterweight":
            parts.append(f"{k} {lifting.tonnes(v):g} t")
        else:
            parts.append(f"{k} {v:g}")
    return ", ".join(parts)


def validate(data, builtin: bool = False) -> Item:
    """Check a file's data (already upgraded): problems refuse the item, warnings and notes do not."""
    item = Item(data=data if isinstance(data, dict) else {}, builtin=builtin)
    p, w = item.problems, item.warnings
    if not isinstance(data, dict):
        p.append("Not a Fresing Render lifting equipment file (the file is not a JSON object).")
        return item
    if data.get("format") != FORMAT:
        p.append(f"Not a Fresing Render lifting equipment file (\"format\" must be \"{FORMAT}\").")
        return item
    for k in ("kind", "name"):
        if not isinstance(data.get(k), str) or not data[k].strip():
            p.append(f"'{k}' is missing: every item needs a {k}.")
    if "class" in data and not isinstance(data["class"], str):
        p.append("'class' must be text (for example \"AT-100\").")
    if isinstance(data.get("kind"), str) and data["kind"].strip() and data["kind"] not in KINDS:
        item.notes.append(f"Kind '{data['kind']}' is not one the app knows yet: it is kept, but shown as 'other'.")
    try:
        mass, length = units_of(data)
    except LibraryError as e:
        p.append(str(e))
        mass, length = "t", "m"
    m = data.get("mass")
    if m is not None:
        vals = m.values() if isinstance(m, dict) else [m]
        if not all(_num(v) and v >= 0 for v in vals):
            p.append("'mass' must be a number of 0 or more, or one per moving group.")
    cog = data.get("cog")
    if cog is not None:
        vals = cog.values() if isinstance(cog, dict) else [cog]
        if not all(_check_vec(v) for v in vals):
            p.append("'cog' must be [x, y, z], or one [x, y, z] per moving group.")
    wll = data.get("wll")
    if wll is not None:
        vals = wll.values() if isinstance(wll, dict) else [wll]
        if not vals or not all(_num(v) and v > 0 for v in vals):
            p.append("'wll' must be a number above 0, or one per way of use (straight, choke, basket …).")
    hb = data.get("hook_blocks")
    if hb is not None:
        if not isinstance(hb, list) or not all(isinstance(b, dict) and _num(b.get("mass")) and b["mass"] >= 0
                                               for b in hb):
            p.append("'hook_blocks' must be a list of blocks, each with a mass of 0 or more.")
    for k in ("rig", "limits", "outriggers", "tracks", "axles"):
        if k in data and not isinstance(data[k], (dict, list)) and data[k] is not None:
            p.append(f"'{k}' must be a table (a JSON object or list).")
    if "sample" in data and not isinstance(data["sample"], bool):
        p.append("'sample' must be true or false.")
    if "derived_from" in data and data["derived_from"] is not None and not isinstance(data["derived_from"], str):
        p.append("'derived_from' must be text (the sample's chart hash).")
    if "source" in data and not isinstance(data["source"], str):
        p.append("'source' must be text.")
    charts = _read_charts(data, mass, length, p)
    if charts:
        e, ww = lifting.validate_charts(charts)
        p += e
        w += ww
    unknown = unknown_fields(data)
    if unknown:
        item.notes.append("Fields this version does not know are kept but not used: " + ", ".join(unknown) + ".")
    if builtin and data.get("sample") is not True:
        w.append("A built-in without the sample mark: it is treated as SAMPLE DATA all the same.")
    return item


def from_data(data, builtin: bool = False) -> Item:
    """An item from a file's data: format version checked, older formats upgraded in memory, then validated."""
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return validate(data, builtin)
    raw = data.get("format_version")
    ver = (0, 0) if raw is None else _version(raw)
    if ver is None:
        item = Item(data=data, builtin=builtin)
        item.problems.append(f"Unknown format version '{raw}' (expected something like \"{FORMAT_VERSION}\").")
        return item
    if ver[0] > MAJOR:
        item = Item(data=data, builtin=builtin, newer=True)
        item.problems.append(NEWER.format(v=raw) + ": it is not checked.")
        return item
    upgraded = None
    d = data
    try:
        while ver[0] < MAJOR:
            d = _UPGRADES[ver[0]](d)
            upgraded = upgraded or (raw if raw is not None else "0")
            ver = _version(d["format_version"])
    except (KeyError, LibraryError, TypeError) as e:
        item = Item(data=data, builtin=builtin)
        item.problems.append(f"Format {raw} cannot be upgraded ({e}).")
        return item
    item = validate(d, builtin)
    if upgraded is not None:
        item.upgraded_from = upgraded
        item.notes.append(f"Made with an older Fresing Render (format {upgraded}): upgraded here, written as "
                          f"{FORMAT_VERSION} when you save it.")
    elif ver[1] > int(FORMAT_VERSION.split(".")[1]):
        item.notes.append(f"Made with a newer Fresing Render (format {raw}): what it added is kept but not used.")
    return item


def _find(folder: str, exts, stem: str) -> str | None:
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    hits = [n for n in names if os.path.splitext(n)[1].lower() in exts and os.path.isfile(os.path.join(folder, n))]
    same = [n for n in hits if os.path.splitext(n)[0] == stem]
    pick = (same or hits or [None])[0]
    return os.path.join(folder, pick) if pick else None


def _json_of(folder: str) -> str | None:
    base = os.path.basename(os.path.normpath(folder))
    own = os.path.join(folder, base + ".json")
    if os.path.isfile(own):
        return own
    try:
        js = sorted(n for n in os.listdir(folder) if n.lower().endswith(".json") and not n.startswith("."))
    except OSError:
        return None
    for n in js:  # the one JSON that is an equipment file
        try:
            d = _load_json(os.path.join(folder, n))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("format") == FORMAT:
            return os.path.join(folder, n)
    return os.path.join(folder, js[0]) if len(js) == 1 else None


def read_item(path: str, builtin: bool | None = None) -> Item:
    """Read one item from its folder (or its .json). Never raises for a broken file: the item carries its problems.

    ``builtin``: None = decided from where the file lies (inside ``BUILTIN_DIR``)."""
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    if builtin is None:
        builtin = _inside(folder, BUILTIN_DIR)
    js = path if os.path.isfile(path) else _json_of(folder)
    if js is None:
        item = Item(data={}, folder=folder, builtin=builtin)
        item.problems.append("No equipment file (.json) in the folder.")
        return item
    try:
        data = _load_json(js)
    except UnicodeDecodeError:
        item = Item(data={}, folder=folder, path=js, builtin=builtin)
        item.problems.append("The file cannot be read: it is not UTF-8 text.")
        return item
    except ValueError as e:
        item = Item(data={}, folder=folder, path=js, builtin=builtin)
        item.problems.append(f"The file cannot be read: it is not valid JSON ({e}).")
        return item
    except OSError as e:
        item = Item(data={}, folder=folder, path=js, builtin=builtin)
        item.problems.append(f"The file cannot be opened ({e.strerror or e}).")
        return item
    item = from_data(data, builtin)
    item.folder, item.path = folder, js
    stem = os.path.splitext(os.path.basename(js))[0]
    item.model = _find(folder, MODEL_EXTS, stem)
    item.picture = _find(folder, PICTURE_EXTS, stem)
    return item


def list_items(user_folder: str | None = None, builtin_folder: str | None = BUILTIN_DIR) -> list[Item]:
    """Every item in the user's library and the built-in folder (read-only), user's first, each sorted by name.

    A folder that is missing gives nothing; a broken item is listed with its problem."""
    out = []
    for folder, builtin in ((user_folder, False), (builtin_folder, True)):
        if not folder or not os.path.isdir(folder):
            continue
        for n in sorted(os.listdir(folder), key=str.lower):
            sub = os.path.join(folder, n)
            if n.startswith(".") or not os.path.isdir(sub):
                continue
            out.append(read_item(sub, builtin=builtin))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Sample mark

def chart_hash(item_or_data) -> str:
    """A hash of the rated data – the charts (configuration, radius, capacity) and the WLL – in SI, so a change of units
    alone keeps it. ``derived_from`` of a copy holds the sample's."""
    data = item_or_data.data if isinstance(item_or_data, Item) else item_or_data
    mass, length = units_of(data)
    fm = lifting.MASS_UNITS[mass]
    charts = []
    for c in _read_charts(data, mass, length, []):
        charts.append({
            "config": {k: (round(v, 6) if _num(v) else v) for k, v in sorted(c.config.items())},
            "radius": [round(r, 6) if _num(r) else r for r in c.radius],
            "capacity": [None if x is None else (round(x, 3) if _num(x) else x) for x in c.capacity],
        })
    charts.sort(key=lambda c: json.dumps(c, sort_keys=True))
    wll = data.get("wll")
    if isinstance(wll, dict):
        wll = {k: round(v * fm, 3) if _num(v) else v for k, v in sorted(wll.items())}
    elif _num(wll):
        wll = round(wll * fm, 3)
    text = json.dumps({"charts": charts, "wll": wll}, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def is_sample(item_or_data) -> bool:
    """True for SAMPLE DATA: a built-in, an item marked ``sample``, or a copy whose charts still equal the sample's.

    L4 / L7 show "SAMPLE DATA – NOT FOR REAL LIFTS" (``lifting.SAMPLE_PAGE_MARK``) and the boom decal for these."""
    if isinstance(item_or_data, Item):
        if item_or_data.builtin:
            return True
        data = item_or_data.data
    else:
        data = item_or_data
    if not isinstance(data, dict):
        return False
    if data.get("sample") is True:
        return True
    d = data.get("derived_from")
    if isinstance(d, str) and d:
        try:
            return chart_hash(data) == d
        except LibraryError:
            return True
    return False


def clear_sample(item_or_data) -> str:
    """Take the SAMPLE mark off (in memory; save to keep it). Refused while the charts equal the sample's, and always
    for a built-in. Returns the sentence to show."""
    if isinstance(item_or_data, Item):
        if item_or_data.builtin:
            raise LibraryError("A built-in item always stays SAMPLE DATA: copy it to your library, then enter your "
                               "own chart.")
        data = item_or_data.data
    else:
        data = item_or_data
    d = data.get("derived_from")
    if isinstance(d, str) and d and chart_hash(data) == d:
        raise LibraryError(SAMPLE_STILL)
    data["sample"] = False
    return "The SAMPLE mark is off: the charts are your own now."


# ---------------------------------------------------------------------------------------------------------------------
# Write and copy

@dataclass
class Written:
    path: str
    notes: list


def _atomic_write(path: str, data: dict) -> None:
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False, allow_nan=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _refuse_builtin(path: str, builtin_folder: str | None) -> None:
    for b in {BUILTIN_DIR, builtin_folder} - {None, ""}:
        if _inside(path, b):
            raise LibraryError("The built-in equipment cannot be changed: copy it to your library first.")


def write_item(item_or_data, library: str, *, builtin_folder: str | None = BUILTIN_DIR) -> Written:
    """Write an item to ``<library>/<name>/<name>.json`` (the folder is made), atomically: a temporary file in the same
    folder, then replaced. Refused: into the built-in folder, a built-in item, a newer format, an item with problems,
    and ``sample`` false while the charts still equal the sample's. Upgraded items are written as the current format.
    Fields this version does not know are kept; the notes name them."""
    was = None
    if isinstance(item_or_data, Item):
        item = item_or_data
        was = item.upgraded_from
        if item.builtin:
            raise LibraryError("The built-in equipment cannot be changed: copy it to your library first.")
        if item.newer:
            raise LibraryError(NEWER.format(v=item.data.get("format_version"))
                               + ": saving it here would lose what it holds.")
        data = item.data
    else:
        data = item_or_data
    if not library:
        raise LibraryError("No library folder: set the library folder in the app's preferences first.")
    data = dict(data)
    data["format"] = FORMAT
    v = _version(data.get("format_version")) if data.get("format_version") is not None else (0, 0)
    if v is not None and v[0] > MAJOR:
        raise LibraryError(NEWER.format(v=data.get("format_version"))
                           + ": saving it here would lose what it holds.")
    checked = from_data(data)
    if checked.problems:
        raise LibraryError("Not saved: " + " ".join(checked.problems))
    data = dict(checked.data)
    if data.get("sample") is False and isinstance(data.get("derived_from"), str) and data["derived_from"] \
            and chart_hash(data) == data["derived_from"]:
        raise LibraryError("Not saved: " + SAMPLE_STILL)
    data["format_version"] = FORMAT_VERSION
    name = folder_name(data["name"])
    folder = os.path.join(library, name)
    _refuse_builtin(folder, builtin_folder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name + ".json")
    _atomic_write(path, data)
    notes = [n for n in checked.notes if not n.startswith("Made with an older")]
    was = was if was is not None else checked.upgraded_from
    if was is not None:
        notes.append(f"Written in format {FORMAT_VERSION} (was {was}).")
    return Written(path, notes)


def copy_item(item: Item, library: str, new_name: str, *, builtin_folder: str | None = BUILTIN_DIR) -> Item:
    """Copy an item (its file, model and picture) to the user's library under a new name. A copy of SAMPLE DATA stays
    SAMPLE DATA and records the sample's chart hash in ``derived_from``; the mark comes off with ``clear_sample`` once
    its charts are the user's own."""
    if item.newer:
        raise LibraryError(NEWER.format(v=item.data.get("format_version")) + ": it cannot be copied.")
    if item.problems:
        raise LibraryError("Not copied: " + " ".join(item.problems))
    name = folder_name(new_name)
    target = os.path.join(library, name)
    _refuse_builtin(target, builtin_folder)
    if os.path.exists(target):
        raise LibraryError(f"'{name}' is already in the library: pick another name.")
    data = json.loads(json.dumps(item.data))
    data["name"] = str(new_name).strip()
    if is_sample(item):
        data["sample"] = True
        own = item.data.get("derived_from")
        data["derived_from"] = own if isinstance(own, str) and own else chart_hash(item)
    os.makedirs(target)
    try:
        stem = os.path.splitext(os.path.basename(item.path))[0] if item.path else ""
        for p in (item.model, item.picture):
            if p and os.path.isfile(p):
                base, ext = os.path.splitext(os.path.basename(p))
                shutil.copy2(p, os.path.join(target, (name if base == stem else base) + ext))
        write_item(data, library, builtin_folder=builtin_folder)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return read_item(target, builtin=False)


# ---------------------------------------------------------------------------------------------------------------------
# Item -> checks

def _checked(item_or_data) -> Item:
    item = item_or_data if isinstance(item_or_data, Item) else from_data(item_or_data)
    if item.newer:
        raise LibraryError(NEWER.format(v=item.data.get("format_version")) + ": it is not checked.")
    if item.problems:
        raise LibraryError(item.problems[0])
    return item


def charts_of(item_or_data) -> list:
    """The item's charts as ``lifting.Chart`` in SI (kg, m), ready for ``lifting.pick_chart`` / ``crane_use``.
    A sample's charts carry ``sample=True``. Refused (LibraryError) for an item with problems or a newer format."""
    item = _checked(item_or_data)
    mass, length = units_of(item.data)
    charts = _read_charts(item.data, mass, length, [])
    s = is_sample(item)
    for c in charts:
        c.sample = c.sample or s
    return charts


def wll_of(item_or_data, use: str | None = None) -> float | None:
    """The working load limit in kg (None: the item has none). With a WLL per way of use, name it (``use``); without a
    name the first one ("straight") is given."""
    item = _checked(item_or_data)
    wll = item.data.get("wll")
    if wll is None:
        return None
    fm = lifting.MASS_UNITS[units_of(item.data)[0]]
    if isinstance(wll, dict):
        if use is None:
            use = "straight" if "straight" in wll else next(iter(wll))
        if use not in wll:
            raise LibraryError(f"No WLL for '{use}' (the file has: {', '.join(wll)}).")
        return wll[use] * fm
    return wll * fm


def hook_blocks_of(item_or_data) -> list[tuple[str, float]]:
    """(name, mass in kg) of each hook block."""
    item = _checked(item_or_data)
    fm = lifting.MASS_UNITS[units_of(item.data)[0]]
    return [(str(b.get("name", f"block {i + 1}")), b["mass"] * fm)
            for i, b in enumerate(item.data.get("hook_blocks") or [])]


# ---------------------------------------------------------------------------------------------------------------------
# Chart entry: a table or CSV -> charts, refused with the row number

_CONFIG_WORDS = {
    "boom": "boom", "boom length": "boom", "main boom": "boom", "jib": "jib", "fly jib": "jib", "luffing jib": "jib",
    "counterweight": "counterweight", "counter weight": "counterweight", "cw": "counterweight", "ballast": "counterweight",
    "outriggers": "outriggers", "outrigger": "outriggers", "outrigger spread": "outriggers", "spread": "outriggers",
    "hs": "hs", "wave height": "hs", "sea state": "hs",
}
_LENGTH_KEYS = ("boom", "jib", "outriggers")
_GAP = {"", "-", "–", "—", "n/a", "na", "x"}


@dataclass
class Entry:
    """Charts entered from a table or CSV. ``charts`` in SI; ``lines[i][j]`` = the table row / CSV line of chart i's
    row j. Refused when ``errors`` is not empty."""

    charts: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    lines: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def dicts(self, mass_unit: str = "t", length_unit: str = "m") -> list[dict]:
        """The charts in an equipment file's form and units."""
        out = []
        for c in self.charts:
            d = lifting.chart_to_dict(c, mass_unit, length_unit)
            for k in ("name", "sample", "wind_max"):
                if not d.get(k):
                    d.pop(k, None)
            if not d.get("includes_hook_block"):
                d.pop("includes_hook_block")
            out.append(d)
        return out


def _parse_number(cell, decimal_comma: bool):
    """(value, unit or None) from a cell; value None for a gap. Raises ValueError for anything else."""
    if cell is None:
        return None, None
    if isinstance(cell, tuple) and len(cell) == 2:  # already read (chart_csv)
        return cell
    if _num(cell):
        return float(cell), None
    s = str(cell).strip().replace(" ", "").replace(" ", "")
    if s.lower() in _GAP:
        return None, None
    m = re.fullmatch(r"([-+]?[\d.,]+)([a-zA-Z]*)", s)
    if not m:
        raise ValueError(s)
    n, unit = m.group(1), m.group(2) or None
    if "," in n and "." in n:  # the later one is the decimal mark, the other groups thousands
        dec = "," if n.rfind(",") > n.rfind(".") else "."
        n = n.replace("." if dec == "," else ",", "").replace(",", ".")
    elif "," in n:
        if not decimal_comma and re.fullmatch(r"[-+]?\d{1,3}(,\d{3})+", n):
            n = n.replace(",", "")
        else:
            n = n.replace(",", ".")
    v = float(n)
    if not math.isfinite(v):
        raise ValueError(s)
    if unit is not None:
        unit = unit.lower()
        if unit in ("lbs",):
            unit = "lb"
        if unit not in lifting.MASS_UNITS and unit not in lifting.LENGTH_UNITS:
            raise ValueError(s)
    return v, unit


def _config_key(word: str) -> str:
    w = re.sub(r"\s+", " ", word.strip().lower())
    return _CONFIG_WORDS.get(w, w.replace(" ", "_"))


def _config_si(config: dict, mass_unit: str, length_unit: str, where: str, errors: list) -> dict:
    """A config typed in the entry's units (or with its own unit per value) -> SI, as lifting.Chart holds it."""
    out = {}
    for k, v in config.items():
        key = _config_key(str(k))
        unit = None
        if isinstance(v, str):
            try:
                v, unit = _parse_number(v, decimal_comma=True)
            except ValueError:
                errors.append(f"{where}: '{k}' must be a number ({v!r}).")
                continue
            if v is None:
                continue
        if not _num(v):
            out[key] = v
            continue
        if key == "hs":
            f = lifting.LENGTH_UNITS[unit] if unit in lifting.LENGTH_UNITS else 1.0  # Hs: metres
        elif key in _LENGTH_KEYS:
            if unit in lifting.MASS_UNITS:
                errors.append(f"{where}: '{k}' is a length, not a mass ({v:g} {unit}).")
                continue
            f = lifting.LENGTH_UNITS[unit or length_unit]
        elif key == "counterweight":
            if unit in lifting.LENGTH_UNITS:
                errors.append(f"{where}: '{k}' is a mass, not a length ({v:g} {unit}).")
                continue
            f = lifting.MASS_UNITS[unit or mass_unit]
        else:
            f = 1.0
        out[key] = v * f
    return out


def chart_rows(rows, mass_unit: str = "t", length_unit: str = "m", lines=None) -> Entry:
    """Charts from a table's rows ``(config, radius, capacity)`` (or dicts with those keys). ``config`` is a dict
    (``{"boom": 30.4, "counterweight": 40}``); rows of one configuration form one chart, in the order typed. An empty
    capacity is a gap. Units of radius / capacity: ``mass_unit`` / ``length_unit`` (a cell may carry its own: "36 t").

    Refused (``errors``): a radius that is not a number above 0 or not rising, a capacity of 0 or less or not a number,
    a capacity that rises with the radius, a sea (Hs) column holding more than a calmer one. Warned: a longer boom
    holding more at the same radius. Every message names the row (``lines`` gives other row numbers, e.g. CSV lines)."""
    entry = Entry()
    try:
        fm, fl = lifting.MASS_UNITS[mass_unit], lifting.LENGTH_UNITS[length_unit]
    except KeyError:
        entry.errors.append(f"Unknown units '{mass_unit}' / '{length_unit}' (masses: t, kg, lb; lengths: m, mm, ft).")
        return entry
    groups: dict = {}
    for i, row in enumerate(rows):
        n = lines[i] if lines is not None else i + 1
        where = f"Row {n}"
        if isinstance(row, dict):
            config, r, c = row.get("config") or {}, row.get("radius"), row.get("capacity")
        else:
            try:
                config, r, c = row
            except (TypeError, ValueError):
                entry.errors.append(f"{where}: give a configuration, a radius and a capacity.")
                continue
        if config is None:
            config = {}
        if not isinstance(config, dict):
            entry.errors.append(f"{where}: the configuration must look like {{\"boom\": 30.4}}.")
            continue
        cfg = _config_si(config, mass_unit, length_unit, where, entry.errors)
        try:
            rv, ru = _parse_number(r, decimal_comma=True)
        except ValueError:
            rv, ru = "bad", None
        if rv is None or rv == "bad" or rv <= 0 or ru in lifting.MASS_UNITS:
            entry.errors.append(f"{where}: the radius must be a number above 0 ({r!r}).")
            continue
        try:
            cv, cu = _parse_number(c, decimal_comma=True)
        except ValueError:
            entry.errors.append(f"{where}: the capacity must be a number above 0, or empty for a gap ({c!r}).")
            continue
        if cu in lifting.LENGTH_UNITS:
            entry.errors.append(f"{where}: the capacity is a mass, not a length ({c!r}).")
            continue
        if cv is not None and cv <= 0:
            entry.errors.append(f"{where}: the capacity must be above 0 ({cv:g}); leave it empty for a gap.")
            continue
        radius = rv * (lifting.LENGTH_UNITS[ru] if ru else fl)
        cap = None if cv is None else cv * (lifting.MASS_UNITS[cu] if cu else fm)
        key = json.dumps(sorted(cfg.items()), default=str)
        if key not in groups:
            groups[key] = (lifting.Chart(radius=[], capacity=[], config=cfg), [])
        chart, ls = groups[key]
        if chart.radius and radius <= chart.radius[-1] + lifting.EPS:
            entry.errors.append(f"{where}: radii must rise from row to row ({radius / fl:g} {length_unit} after "
                                f"{chart.radius[-1] / fl:g} {length_unit}, row {ls[-1]}).")
            continue
        if cap is not None:
            prev = next(((pc, pl) for pc, pl in zip(reversed(chart.capacity), reversed(ls)) if pc is not None), None)
            if prev is not None and cap > prev[0] + lifting.EPS:
                entry.errors.append(f"{where}: the capacity rises with the radius ({cap / fm:g} {mass_unit} after "
                                    f"{prev[0] / fm:g} {mass_unit} in row {prev[1]}).")
                continue
        chart.radius.append(radius)
        chart.capacity.append(cap)
        ls.append(n)
    for chart, ls in groups.values():
        if all(c is None for c in chart.capacity):
            label = _config_words(chart.config) if chart.config else "the chart"
            entry.errors.append(f"Rows {ls[0]}–{ls[-1]}: {label} has no capacity at all.")
        entry.charts.append(chart)
        entry.lines.append(ls)
    if not entry.charts and not entry.errors:
        entry.errors.append("The table has no rows.")
    if not entry.errors:
        e, w = lifting.validate_charts(entry.charts)
        entry.errors += [_with_rows(m, entry) for m in e]
        entry.warnings += [_with_rows(m, entry) for m in w]
    return entry


def _with_rows(message: str, entry: Entry) -> str:
    """Add the rows of the radius a cross-chart message names ('At 12 m …')."""
    m = re.match(r"At ([\d.e+-]+) m", message)
    if not m:
        return message
    r = float(m.group(1))
    rows = [ls[j] for c, ls in zip(entry.charts, entry.lines) for j, x in enumerate(c.radius) if abs(x - r) < 1e-6]
    if not rows:
        return message
    return f"Rows {', '.join(str(x) for x in sorted(rows))}: " + message[0].lower() + message[1:]


_HEADER_UNIT = re.compile(r"[\[(]\s*([a-zA-Z]+)\s*[\])]|\b(t|kg|lb|lbs|m|mm|ft)\s*$")


def _column_unit(cell: str):
    m = _HEADER_UNIT.search(cell.strip())
    if not m:
        return None
    u = (m.group(1) or m.group(2)).lower()
    return "lb" if u == "lbs" else u


def _parse_config_line(cells: list[str], where: str, errors: list) -> dict:
    """'boom 30.4 m; counterweight=40 t; Hs 1.5' -> {"boom": "30.4m", …} (values with their unit, as text)."""
    text = ";".join(c for c in cells if c is not None)
    text = text.lstrip("#").strip()
    out = {}
    for part in re.split(r"[;\t]|,(?=\s*[A-Za-z])", text):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"([A-Za-z][A-Za-z _-]*?)\s*[=:]?\s*([-+]?\d[\d.,]*\s*[A-Za-z]*)", part)
        if not m:
            errors.append(f"{where}: cannot read the configuration '{part}' (write it like 'boom 30.4 m').")
            continue
        out[m.group(1)] = m.group(2)
    return out


def chart_csv(text: str, mass_unit: str = "t", length_unit: str = "m") -> Entry:
    """Charts from CSV text (pasted, or a file's content): ``radius;capacity`` or ``radius,capacity`` per line.

    - Separator: ``;`` (then a decimal comma is allowed: ``8,5``), a tab, or ``,`` (then decimal points).
    - A line that does not start with a number is a header: a column header (``radius (m);capacity (t)`` – sets the
      units: t / kg / lb, m / ft) or a configuration (``boom 30.4 m; counterweight 40 t``) that starts a new chart.
    - An empty capacity (or ``-``) is a gap. Lines starting with ``//`` are comments; empty lines are skipped.
    Messages name the CSV line."""
    entry = Entry()
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines()
    body = [ln for ln in lines if ln.strip()]
    if not body:
        entry.errors.append("The CSV is empty.")
        return entry
    if any(";" in ln for ln in body):
        delim, dec_comma = ";", True
    elif any("\t" in ln for ln in body):
        delim, dec_comma = "\t", True
    else:
        delim, dec_comma = ",", False
    rows, nums, config = [], [], {}
    m_unit, l_unit = mass_unit, length_unit
    for n, raw in enumerate(lines, start=1):
        s = raw.strip()
        if not s or s.startswith("//"):
            continue
        cells = next(csv.reader(io.StringIO(s), delimiter=delim))
        cells = [c.strip() for c in cells]
        while len(cells) > 2 and cells[-1] == "":
            cells.pop()
        first = cells[0] if cells else ""
        if s.startswith("#") or not re.match(r"[-+]?[\d.,]", first):
            low = s.lower()
            if any(w in low for w in ("radius", "capacity", "outreach", "reach", "load")):
                if len(cells) >= 1:
                    u = _column_unit(cells[0])
                    if u in lifting.LENGTH_UNITS:
                        l_unit = u
                    elif u is not None:
                        entry.errors.append(f"Line {n}: unknown length unit '{u}' for the radius (use m or ft).")
                if len(cells) >= 2:
                    u = _column_unit(cells[1])
                    if u in lifting.MASS_UNITS:
                        m_unit = u
                    elif u is not None:
                        entry.errors.append(f"Line {n}: unknown mass unit '{u}' for the capacity (use t, kg or lb).")
                continue
            config = _parse_config_line(cells, f"Line {n}", entry.errors)
            continue
        if len(cells) != 2:
            entry.errors.append(f"Line {n}: two columns expected (radius and capacity), found {len(cells)}.")
            continue
        # decimal-comma cells are read here, so the table reader sees plain numbers
        try:
            r = _parse_number(cells[0], dec_comma)
            c = _parse_number(cells[1], dec_comma)
        except ValueError:
            entry.errors.append(f"Line {n}: the radius and capacity must be numbers ('{cells[0]}', '{cells[1]}').")
            continue
        rows.append((dict(config), r, c))
        nums.append(n)
    if entry.errors:
        return entry
    out = chart_rows(rows, m_unit, l_unit, lines=nums)
    out.errors = [_as_lines(e) for e in out.errors]
    out.warnings = [_as_lines(w) for w in out.warnings]
    return out


def _as_lines(message: str) -> str:
    for a, b in (("Rows ", "Lines "), ("Row ", "Line "), (" row ", " line ")):
        message = message.replace(a, b)
    return message


def read_chart_csv(path: str, mass_unit: str = "t", length_unit: str = "m") -> Entry:
    """``chart_csv`` of a file (UTF-8, or Windows-1252 as Excel writes it)."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252", errors="replace")
    return chart_csv(text, mass_unit, length_unit)


def set_charts(data: dict, entry: Entry, replace: bool = True) -> dict:
    """Put an entry's charts into an item's data, in the item's units. Refused when the entry was refused."""
    if entry.errors:
        raise LibraryError("The chart was not taken: " + " ".join(entry.errors))
    mass, length = units_of(data)
    new = entry.dicts(mass, length)
    data["charts"] = new if replace else list(data.get("charts") or []) + new
    return data
