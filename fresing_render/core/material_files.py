"""Materials for the material picker (task 0273): the built-ins as entries, own / department / company materials as
folders, the project's copies – plain Python, no Blender (the Blender side is ``blender/material_picker.py``).

**An entry** (``Entry``) is one thing the picker shows: a library material (key ``builtin:<id>``), a ready-made
material with its colour (``preset:<id>``, ``materials_lib.PRESETS``) or an own material (``own:<id>``). Every entry
names the library material it starts from (``base``) and what it changes (``changes``: ``color``, ``wear``, ``rust``,
``finish`` = {size (m), angle (degrees), amount, base, kind}). A group that gets an entry gets exactly those values,
so a project never needs the entry's folder to render.

**An own material is one folder** in a Materials location (task 0272), like an item of the lifting library (0190)::

    <Materials folder>/<name>/material.json       # this file
    <Materials folder>/<name>/picture.png         # made by the app when the material is saved (Make the picture again)
    <Materials folder>/<name>/material.blend      # only for a material made in Blender's own shader editor

    {
      "format": "fresing-material",      # required
      "format_version": "1.0",           # "major.minor": a higher major is listed with its problem and never
                                          # written; a higher minor: what it added is kept but not used
      "id": "3f2a…",                     # required: a fixed id (the same material in two folders is listed twice)
      "name": "Our machine blue",        # required
      "description": "…", "author": "…", "made_with": "0.2.238", "made": "2026-11-24",
      "base": "paint_satin",             # required: the library material it starts from
      "changes": {"color": "RAL 5015", "wear": 0.1, "rust": 0.0,
                  "finish": {"size": 0.0008, "angle": 30, "amount": 0.8, "base": "STEEL", "kind": ""}},
      "tags": {"material": "Paint", "colour": "blue", "looks": ["satin"]},   # worked out when missing
      "blend": {"file": "material.blend", "material": "Shader name", "images_outside": ["D:/tex/a.png"]}
    }

A broken folder (no file, not JSON, a newer major, a missing name …) is still an entry: it carries ``problems`` and
is listed greyed with them, never used.
"""

from __future__ import annotations

import colorsys
import datetime as _dt
import hashlib
import json
import math
import os
import re
import tempfile
import uuid
from dataclasses import dataclass, field

from . import finishes as fin_core
from . import materials_lib as ML
from . import ral

FORMAT = "fresing-material"
FORMAT_VERSION = "1.0"
MAJOR, MINOR = 1, 0
JSON_NAME = "material.json"
PICTURE_NAME = "picture.png"
BLEND_NAME = "material.blend"
FIELDS = ("format", "format_version", "id", "name", "description", "author", "made_with", "made", "base", "changes",
          "tags", "blend")
CHANGE_KEYS = ("color", "wear", "rust", "finish")
NEWER = "Made with a newer Fresing Render (format {v}): update the app to use it"
MAX_JSON = 1024 * 1024                  # a material.json bigger than this is not read (it is not one)

#: raise when the swatch, its light or the picture size change: every built-in's picture is then made again
PICTURE_VERSION = 1      # (also when blender/material_pictures.py's SIZE, PATTERN or FINISH_SCALE change)
PICTURE_SIZE = 256
PICTURES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "material_pictures")
HASHES = "hashes.json"
PICTURE_EXT = ".jpg"

#: the colour a colour-taking built-in is pictured in (the window draws a chip of the group's colour on it)
PICTURE_COLOURS = {
    "paint_gloss": "RAL 3020", "paint_satin": "RAL 5010", "paint_matte": "RAL 7016", "powder_coat": "RAL 9005",
    "paint_marine": "RAL 1003", "paint_marine_growth": "RAL 3000", "paint_marine_streaks": "RAL 7035",
    "paint_blade_eroded": "RAL 7035", "wire_mesh": "RAL 9005", "aluminium_anodized_color": "#3A5A8C",
    "plastic_gloss": "RAL 3020", "plastic_matte": "RAL 9005", "glass_tinted": "RAL 7016",
    "emission_light": "RAL 9010", "cast_iron_painted": "RAL 6011", "hose_hydraulic": "RAL 9005",
    "hose_sleeve": "RAL 2004", "rubber_grip": "RAL 9005", "crosshatch": "RAL 9005", "fabric": "RAL 7021",
    "grille": "RAL 9005", "soft_touch": "RAL 7024", "hammertone": "RAL 7031", "wrinkle": "RAL 9005",
    "antiskid": "RAL 7040", "vdi": "RAL 9005", "leather": "RAL 8019", "from_file": "RAL 7035",
}
DEFAULT_PICTURE_COLOUR = "RAL 7035"


class MaterialError(ValueError):
    """A refusal, in plain words."""


@dataclass
class Entry:
    key: str                                   # builtin:<id> / preset:<id> / own:<id>
    name: str
    source: str = "builtin"                    # builtin / company / department / mine / project
    badge: str = "Built-in"
    base: str = "paint_satin"
    changes: dict = field(default_factory=dict)
    kind: str = "Other"                        # the Material filter (materials_lib.KINDS)
    colour: str = "any"                        # the Colour filter (materials_lib.COLOURS)
    looks: tuple = ()
    description: str = ""
    author: str = ""
    picture: str = ""                          # a file, or "" (the window shows a plain swatch)
    folder: str = ""                           # an own material's folder
    blend: str = ""                            # its material.blend
    blend_material: str = ""                   # the material's name inside it
    images_outside: tuple = ()                 # image files the Blender material uses that are not in its folder
    data: dict = field(default_factory=dict)   # the whole material.json (own materials)
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    newer: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def is_blend(self) -> bool:
        return bool(self.blend_material)

    @property
    def takes_colour(self) -> bool:
        """The group's own colour is used (a paint with no colour of its own)."""
        return ML.needs_color(self.base) and not self.changes.get("color") and not self.is_blend

    @property
    def own_id(self) -> str:
        return self.key.split(":", 1)[1] if self.key.startswith("own:") else ""

    def label(self) -> str:
        return self.name if self.source == "builtin" else f"{self.name}  ·  {self.badge}"


# ---------------------------------------------------------------------------------------------------------------------
# colours

def rgb_of(colour_text: str):
    """sRGB (0..1) of a RAL code or hex colour, or None."""
    parsed = ral.parse_colour(colour_text) if colour_text else None
    return tuple(parsed[1]) if parsed else None


def colour_family(rgb) -> str:
    """The Colour filter's family of an sRGB colour (0..1): white, grey, black, red, orange, yellow, green, blue,
    purple, brown."""
    r, g, b = (min(max(float(c), 0.0), 1.0) for c in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    v = max(r, g, b)
    chroma = v - min(r, g, b)
    if chroma < 0.08 or (s < 0.18 and chroma < 0.15):
        if l > 0.82:
            return "white"
        if l < 0.16:
            return "black"
        return "grey"
    if v < 0.12:
        return "black"
    deg = h * 360.0
    if deg < 15 or deg >= 340:
        return "brown" if v < 0.45 else "red"
    if deg < 45:
        return "brown" if v < 0.55 or (s < 0.5 and l < 0.5) else "orange"
    if deg < 70:
        return "brown" if v < 0.45 else "yellow"
    if deg < 170:
        return "green"
    if deg < 255:
        return "blue"
    if deg < 290:
        return "purple"
    return "purple" if l < 0.6 else "red"


# ---------------------------------------------------------------------------------------------------------------------
# the built-ins

def _tags(mid: str) -> tuple:
    fn = getattr(ML, "tags", None)
    return fn(mid) if fn else ("Other", "any" if ML.needs_color(mid) else "metal", ("matte",))


def _describe(mid: str) -> str:
    fn = getattr(ML, "describe", None)
    return fn(mid) if fn else ML.get(mid)["label"]


def picture_name(key: str) -> str:
    """The file name of a built-in's picture: ``<id>.jpg`` / ``preset_<id>.jpg``."""
    kind, _sep, ident = key.partition(":")
    return ("preset_" if kind == "preset" else "") + ident + PICTURE_EXT


def picture_colour(key: str) -> str:
    """The colour a built-in is pictured in ('' for a material with a colour of its own)."""
    kind, _sep, ident = key.partition(":")
    if kind == "preset":
        p = next((p for p in ML.PRESETS if p[0] == ident), None)
        return p[3] if p else ""
    if ML.needs_color(ident):
        return PICTURE_COLOURS.get(ident, DEFAULT_PICTURE_COLOUR)
    return ""


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, float):
        return round(v, 6)
    if callable(v):                         # a finish's helper function: its name (an address changes every run)
        return getattr(v, "__qualname__", type(v).__name__)
    if v is None or isinstance(v, (str, int, bool)):
        return v
    return repr(v)


def picture_hash(key: str) -> str:
    """What a built-in's picture is made from: its library spec, its finish's spec, its picture colour, the swatch's
    version. A change to any of them asks for a new picture (``tests/test_material_pictures.py``)."""
    _kind, _sep, ident = key.partition(":")
    base = ident
    if key.startswith("preset:"):
        p = next((p for p in ML.PRESETS if p[0] == ident), None)
        base = p[2] if p else ident
    spec = {"material": _jsonable(ML.MATERIALS.get(base, {})), "finish": _jsonable(fin_core.get(base) or {}),
            "colour": picture_colour(key), "version": PICTURE_VERSION, "size": PICTURE_SIZE}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def builtin_keys() -> list:
    """Every built-in entry's key, in the order the picker lists them (library order, then the presets)."""
    keys = [f"builtin:{m}" for m in ML.MATERIALS if m not in ML.NOT_PICKED]
    keys += [f"preset:{p[0]}" for p in ML.PRESETS if p[3]]
    return keys


_BUILTINS: list | None = None


def builtin_entries(pictures_dir: str = PICTURES_DIR) -> list:
    """The built-in entries (made once)."""
    global _BUILTINS
    if _BUILTINS is not None and pictures_dir == PICTURES_DIR:
        return _BUILTINS
    out = []
    for key in builtin_keys():
        kind, _sep, ident = key.partition(":")
        if kind == "builtin":
            spec = ML.MATERIALS[ident]
            k, c, looks = _tags(ident)
            e = Entry(key=key, name=spec["label"], base=ident, kind=k, colour=c, looks=tuple(looks),
                      description=_describe(ident))
        else:
            _pid, label, mid, colour = next(p for p in ML.PRESETS if p[0] == ident)
            k, c, looks = _tags(mid)
            rgb = rgb_of(colour)
            e = Entry(key=key, name=label, base=mid, changes={"color": colour}, kind=k,
                      colour=colour_family(rgb) if rgb else c, looks=tuple(looks),
                      description=f"{_describe(mid)} – in {colour}")
        pic = os.path.join(pictures_dir, picture_name(key))
        e.picture = pic if os.path.isfile(pic) else ""
        out.append(e)
    if pictures_dir == PICTURES_DIR:
        _BUILTINS = out
    return out


def builtin(key: str):
    """The built-in entry of a key, or None."""
    return next((e for e in builtin_entries() if e.key == key), None)


def builtin_for(material: str, color: str = ""):
    """The built-in entry a group with this material (and colour) shows: a ready-made entry with that exact colour,
    else the library material itself."""
    for e in builtin_entries():
        if e.key.startswith("preset:") and e.base == material and color and \
                str(e.changes.get("color", "")).strip().upper() == color.strip().upper():
            return e
    return builtin(f"builtin:{material}")


# ---------------------------------------------------------------------------------------------------------------------
# changes: what a group's settings are, as an entry's ``changes``

def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def clean_changes(base: str, changes, problems: list | None = None) -> dict:
    """``changes`` checked against the base material: only what it uses, numbers inside their limits. Unknown keys and
    wrong values are left out (named in ``problems`` when given)."""
    out: dict = {}
    if not isinstance(changes, dict):
        if changes not in (None, {}) and problems is not None:
            problems.append("'changes' is not a list of settings: left out.")
        return out
    for k, v in changes.items():
        if k not in CHANGE_KEYS:
            if problems is not None:
                problems.append(f"Unknown setting '{k}' in 'changes': left out.")
            continue
        if k == "color":
            if not isinstance(v, str) or (v.strip() and ral.parse_colour(v) is None):
                if problems is not None:
                    problems.append(f"The colour '{v}' is not a RAL code or a hex colour (#13447C): left out.")
                continue
            if v.strip() and ML.needs_color(base):
                out["color"] = v.strip()
        elif k in ("wear", "rust"):
            if not _num(v):
                if problems is not None:
                    problems.append(f"'{k}' is not a number: left out.")
                continue
            val = min(max(float(v), 0.0), 1.0)
            if k == "rust" and not ML.rust_kind(base):
                continue
            if val:
                out[k] = round(val, 4)
        elif k == "finish":
            if fin_core.get(base) is None or not isinstance(v, dict):
                continue
            size = v.get("size") if _num(v.get("size")) else None
            angle = v.get("angle") if _num(v.get("angle")) else None
            amount = v.get("amount") if _num(v.get("amount")) else None
            c = fin_core.clean(base, size=size, angle=angle, amount=amount,
                               base=v.get("base") if isinstance(v.get("base"), str) else None,
                               kind=v.get("kind") if isinstance(v.get("kind"), str) else None)
            used = fin_core.settings_of(base)
            out["finish"] = {n: (round(float(c[n]), 7) if n in ("size", "angle", "amount") else c[n])
                             for n in ("size", "angle", "amount", "base", "kind") if n in used}
    return out


def changes_of(material: str, color: str = "", wear: float = 0.0, rust: float = 0.0, finish: dict | None = None) -> dict:
    """A group's settings as an entry's ``changes`` (``finish``: {size m, angle degrees, amount, base, kind})."""
    return clean_changes(material, {"color": color or "", "wear": wear, "rust": rust, "finish": finish or {}})


def values_of(entry: Entry) -> dict:
    """What a group gets from an entry: material, color, wear, rust and the finish's settings (defaults where the
    entry says nothing) – {"material", "color", "wear", "rust", "finish": {size, angle, amount, base, kind} or None}.
    ``color`` is None when the entry has none (the group keeps its own)."""
    base = entry.base if entry.base in ML.MATERIALS else "paint_satin"
    ch = entry.changes or {}
    fin = None
    if fin_core.get(base) is not None:
        d = fin_core.defaults(base)
        d.update(ch.get("finish") or {})
        fin = fin_core.clean(base, **{k: d.get(k) for k in ("size", "angle", "amount", "base", "kind")})
    return {"material": "blender_material" if entry.is_blend else base, "color": ch.get("color"),
            "wear": float(ch.get("wear", 0.0)), "rust": float(ch.get("rust", 0.0)), "finish": fin}


# ---------------------------------------------------------------------------------------------------------------------
# the file

def new_id() -> str:
    return uuid.uuid4().hex[:16]


def today() -> str:
    return _dt.date.today().isoformat()


def new_material(name: str, base: str, changes: dict | None = None, description: str = "", author: str = "",
                 made_with: str = "", blend: dict | None = None, ident: str = "") -> dict:
    """A material.json's data (checked: ``MaterialError`` for a missing name or an unknown base)."""
    name = " ".join(str(name or "").split())
    if not name:
        raise MaterialError("The material needs a name.")
    if base not in ML.MATERIALS:
        raise MaterialError(f"Unknown library material '{base}'.")
    d = {"format": FORMAT, "format_version": FORMAT_VERSION, "id": ident or new_id(), "name": name,
         "description": " ".join(str(description or "").split()), "author": str(author or ""),
         "made_with": str(made_with or ""), "made": today(), "base": base,
         "changes": clean_changes(base, changes or {})}
    k, c, looks = auto_tags(base, d["changes"], blend=bool(blend))
    d["tags"] = {"material": k, "colour": c, "looks": list(looks)}
    if blend:
        d["blend"] = {"file": BLEND_NAME, "material": str(blend.get("material", "")),
                      "images_outside": [str(p) for p in blend.get("images_outside", [])]}
    return d


def auto_tags(base: str, changes: dict, blend: bool = False) -> tuple:
    """Tags for an own material: its base's, the colour family from its own colour."""
    k, c, looks = _tags(base) if base in ML.MATERIALS else ("Other", "any", ("matte",))
    rgb = rgb_of(changes.get("color", "")) if changes else None
    if rgb:
        c = colour_family(rgb)
    if blend:
        k, c = "Other", "any"
    return k, c, tuple(looks)


def _version(v):
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"(\d{1,4})\.(\d{1,4})", v.strip())
    return (int(m.group(1)), int(m.group(2))) if m else None


def _text(v, limit: int = 400) -> str:
    return " ".join(str(v).split())[:limit] if isinstance(v, (str, int, float)) and not isinstance(v, bool) else ""


def entry_from_data(data, source: str = "mine", badge: str = "Mine", folder: str = "") -> Entry:
    """An entry from a material.json's data. Never raises: a broken file gives an entry with ``problems``."""
    e = Entry(key="own:", name=os.path.basename(folder.rstrip("/\\")) or "Material", source=source, badge=badge,
              folder=folder)
    if not isinstance(data, dict):
        e.problems.append("The file is not a material (no settings in it).")
        return e
    e.data = data
    if data.get("format") != FORMAT:
        e.problems.append("Not a Fresing material file (its 'format' is not \"fresing-material\").")
        return e
    raw = data.get("format_version")
    ver = _version(raw)
    if ver is None:
        e.problems.append(f"Unknown format version '{raw}' (expected something like \"{FORMAT_VERSION}\").")
        return e
    if ver[0] > MAJOR:
        e.newer = True
        e.problems.append(NEWER.format(v=raw))
        e.name = _text(data.get("name")) or e.name
        return e
    if ver[0] == MAJOR and ver[1] > MINOR:
        e.notes.append(f"Made with a newer Fresing Render (format {raw}): what it added is kept but not used.")
    unknown = [k for k in data if k not in FIELDS]
    if unknown:
        e.notes.append("Kept but not used: " + ", ".join(sorted(map(str, unknown))))
    ident = data.get("id")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_-]{4,64}", ident):
        e.problems.append("The material has no id (or a wrong one).")
    else:
        e.key = "own:" + ident
    name = _text(data.get("name"), 120)
    if not name:
        e.problems.append("The material has no name.")
    else:
        e.name = name
    base = data.get("base")
    if not isinstance(base, str) or base not in ML.MATERIALS or base == "blender_material":
        e.problems.append(f"Unknown library material '{base}' (made with a newer app?).")
        base = "paint_satin"
    e.base = base
    e.changes = clean_changes(base, data.get("changes", {}), e.notes)
    e.description = _text(data.get("description"))
    e.author = _text(data.get("author"), 120)
    blend = data.get("blend")
    if blend is not None:
        if not isinstance(blend, dict) or not _text(blend.get("material"), 200):
            e.problems.append("'blend' names no material.")
        else:
            e.blend_material = _text(blend.get("material"), 200)
            f = blend.get("file", BLEND_NAME)
            f = f if isinstance(f, str) and f and os.path.basename(f) == f else BLEND_NAME
            e.blend = os.path.join(folder, f) if folder else ""
            outside = blend.get("images_outside", [])
            e.images_outside = tuple(str(p) for p in outside if isinstance(p, str)) if isinstance(outside, list) else ()
            if folder and not os.path.isfile(e.blend):
                e.problems.append(f"Its Blender file ({f}) is not in the folder.")
    k, c, looks = auto_tags(base, e.changes, blend=bool(e.blend_material))
    tags = data.get("tags")
    if isinstance(tags, dict):
        if tags.get("material") in getattr(ML, "KINDS", ()):
            k = tags["material"]
        if tags.get("colour") in getattr(ML, "COLOURS", ()):
            c = tags["colour"]
        lk = [x for x in tags.get("looks", []) if x in getattr(ML, "LOOKS", ())] \
            if isinstance(tags.get("looks"), list) else []
        if lk:
            looks = tuple(dict.fromkeys(lk))
    e.kind, e.colour, e.looks = k, c, tuple(looks)
    if folder:
        pic = os.path.join(folder, PICTURE_NAME)
        e.picture = pic if os.path.isfile(pic) else ""
    return e


def read_folder(folder: str, source: str = "mine", badge: str = "Mine") -> Entry:
    """One own material from its folder. Never raises."""
    js = os.path.join(folder, JSON_NAME)
    if not os.path.isfile(js):
        e = entry_from_data({}, source, badge, folder)
        e.problems = ["No material.json in the folder."]
        return e
    try:
        if os.path.getsize(js) > MAX_JSON:
            raise MaterialError("too big")
        with open(js, "rb") as fh:
            raw = fh.read()
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=_no_constants)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        e = entry_from_data({}, source, badge, folder)
        e.problems = [f"material.json cannot be read: {_short(exc)}"]
        return e
    return entry_from_data(data, source, badge, folder)


def _no_constants(name):
    raise ValueError(f"{name} is not allowed")


def _short(exc) -> str:
    return " ".join(str(exc).split())[:160] or type(exc).__name__


def list_folder(root: str, source: str = "mine", badge: str = "Mine") -> list:
    """Every material folder in a Materials folder (sub-folders, sorted by name; a sub-folder with neither a
    material.json nor a material.blend is not a material and is skipped). Never raises."""
    out = []
    try:
        names = sorted(os.listdir(root), key=str.casefold)
    except OSError:
        return out
    for n in names:
        full = os.path.join(root, n)
        if n.startswith(".") or not os.path.isdir(full):
            continue
        try:
            inside = set(os.listdir(full))
        except OSError:
            continue
        if JSON_NAME not in inside and BLEND_NAME not in inside:
            continue
        out.append(read_folder(full, source, badge))
    return out


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$",
             *(f"COM{i}" for i in "0123456789¹²³"), *(f"LPT{i}" for i in "0123456789¹²³")}


def folder_name(name: str) -> str:
    """A folder name for a material's name that works on Windows."""
    s = _BAD_CHARS.sub("_", str(name)).strip().rstrip(". ")[:80].strip().rstrip(". ")
    if not s:
        raise MaterialError("The material needs a name.")
    if s.split(".")[0].strip().upper() in _RESERVED:
        s += "_"
    return s


def free_folder(root: str, name: str) -> str:
    base = folder_name(name)
    p, n = os.path.join(root, base), 2
    while os.path.exists(p):
        p, n = os.path.join(root, f"{base} ({n})"), n + 1
    return p


def write_json(folder: str, data: dict) -> str:
    """Write material.json into ``folder`` (made when needed), through a temporary file. Refuses data of a newer
    format (it would lose what that version added)."""
    ver = _version(data.get("format_version"))
    if ver is None or ver[0] > MAJOR:
        raise MaterialError("Made with a newer Fresing Render: it is not written over.")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, JSON_NAME)
    fd, tmp = tempfile.mkstemp(prefix=".material.", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return path


def save_new(root: str, data: dict) -> str:
    """A new material folder in ``root`` named after the material; returns the folder."""
    folder = free_folder(root, data.get("name", ""))
    write_json(folder, data)
    return folder


# ---------------------------------------------------------------------------------------------------------------------
# the window's filters

SOURCE_ORDER = {"builtin": 0, "project": 1, "company": 2, "department": 3, "mine": 4}


def sources(entries) -> list:
    """[(badge, source)] of the entries, in the order Built-in, This project, Company, each department, Mine."""
    seen: dict = {}
    for e in entries:
        seen.setdefault(e.badge, e.source)
    return sorted(seen.items(), key=lambda it: (SOURCE_ORDER.get(it[1], 9), it[0].casefold()))


def matches(e: Entry, text: str = "", badge: str = "", kind: str = "", colour: str = "", look: str = "") -> bool:
    """Does an entry pass the filters ("" = any). The search looks at the name, description, author, tags and badge;
    every word must be found."""
    if badge and e.badge != badge:
        return False
    if kind and e.kind != kind:
        return False
    if colour and e.colour != colour:
        return False
    if look and look not in e.looks:
        return False
    words = str(text or "").casefold().split()
    if words:
        hay = " ".join([e.name, e.description, e.author, e.kind, e.colour, " ".join(e.looks), e.badge,
                        ML.get(e.base)["label"], str(e.changes.get("color", ""))]).casefold()
        if not all(w in hay for w in words):
            return False
    return True


def filter_entries(entries, text: str = "", badge: str = "", kind: str = "", colour: str = "", look: str = "") -> list:
    return [e for e in entries if matches(e, text, badge, kind, colour, look)]


def merge(builtins: list, own: list, project: list) -> list:
    """The picker's list: the built-ins, then own materials sorted by name (company, department, mine), then the
    project's copies of own materials whose folder is not there (same id found in a folder: the folder's is shown)."""
    have = {e.key for e in own if e.ok}
    rest = [e for e in project if e.key not in have]
    own_sorted = sorted(own, key=lambda e: (e.name.casefold(), SOURCE_ORDER.get(e.source, 9), e.badge))
    return list(builtins) + own_sorted + sorted(rest, key=lambda e: e.name.casefold())
