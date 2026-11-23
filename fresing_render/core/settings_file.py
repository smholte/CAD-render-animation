"""The app's own settings file (task 0283) – no Blender.

Blender 5.2.3 does not keep an extension's own preferences over a restart while the app template is on (task 0278's
finding), so every Fresing setting of ``blender/prefs.py`` is kept in one small JSON file per user in Blender's
settings folder, ``<config>/fresing_settings.json``::

    {"format": "fresing-settings", "version": 1, "settings": {"keep_sections": true, "backup_minutes": 10, ...}}

* Only values that differ from the app's default are written: a setting the user never changed follows a new
  default of a later version, and the file shows at a glance what this user chose. IT may copy the file to another
  PC (``docs/COMPANY-USE.md``).
* A **spec** says which settings exist, their kind and limits: ``{name: Kind}``. It is made from the registered
  preferences in ``blender/settings_store.py``, so a setting added to ``prefs.py`` is kept with no change here.
* **Reading** never fails: a missing file gives nothing; a broken one (not JSON, not ours, wrong shape) gives
  nothing, is copied aside as ``fresing_settings.broken-<time>.json`` and gives one plain note; a value of the wrong
  kind or out of its range is left out (one note naming it). A file of a **newer** version is read for the settings
  this version knows; the others are kept and written back unchanged (going back to an older app loses nothing).
* **Writing** goes through a temporary file and a rename, so a crash or a full disk never leaves half a file.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field

FILE_NAME = "fresing_settings.json"
FORMAT = "fresing-settings"
VERSION = 1


@dataclass(frozen=True)
class Kind:
    """One setting: ``type`` is bool / int / float / str / enum / colour."""
    type: str
    default: object = None
    min: float | None = None
    max: float | None = None
    items: tuple = ()          # enum: the allowed identifiers
    size: int = 0              # colour / vector: number of values


@dataclass
class Result:
    values: dict = field(default_factory=dict)     # name -> value, only settings of the spec, cleaned
    extra: dict = field(default_factory=dict)      # settings this version does not know (kept when writing)
    notes: list = field(default_factory=list)      # plain sentences for the user (a broken file, a value left out)
    detail: str = ""                               # why a file was taken as damaged (for the console, not the user)
    found: bool = False                            # a file was there (broken or not)
    version: int = 0                               # the file's version (0: none / broken)


# ---------------------------------------------------------------------------
# values
# ---------------------------------------------------------------------------

def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def clean(value, kind: Kind):
    """The value as the setting takes it, or raise ValueError with a plain reason."""
    t = kind.type
    if t == "bool":
        if isinstance(value, bool):
            return value
        raise ValueError("not on/off")
    if t == "int":
        if isinstance(value, float) and _num(value) and value == int(value):
            value = int(value)
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("not a whole number")
        return int(_limit(value, kind))
    if t == "float":
        if not _num(value):
            raise ValueError("not a number")
        return float(_limit(float(value), kind))
    if t == "str":
        if not isinstance(value, str):
            raise ValueError("not a text")
        if any(ord(c) < 32 for c in value):
            raise ValueError("holds a control character")
        return value
    if t == "enum":
        if not isinstance(value, str) or value not in kind.items:
            raise ValueError("not one of the choices")
        return value
    if t == "colour":
        if (not isinstance(value, (list, tuple)) or len(value) != kind.size or not all(_num(x) for x in value)):
            raise ValueError(f"not {kind.size} numbers")
        return tuple(round(float(_limit(float(x), kind)), 6) for x in value)
    raise ValueError(f"unknown kind {t}")


def _limit(v, kind: Kind):
    if kind.min is not None and v < kind.min:
        raise ValueError(f"below {kind.min:g}")
    if kind.max is not None and v > kind.max:
        raise ValueError(f"above {kind.max:g}")
    return v


def same(a, b) -> bool:
    """Equal as settings (colours and floats within float32 rounding)."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if _num(a) and _num(b) and (isinstance(a, float) or isinstance(b, float)):
        return abs(float(a) - float(b)) <= 1e-6 * max(1.0, abs(float(a)), abs(float(b)))
    return type(a) is type(b) and a == b


def changed(values: dict, spec: dict) -> dict:
    """Only the values that differ from their default (what the file holds)."""
    return {n: v for n, v in values.items() if n in spec and not same(v, spec[n].default)}


# ---------------------------------------------------------------------------
# the file
# ---------------------------------------------------------------------------

def read(path: str, spec: dict) -> Result:
    res = Result()
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return res
    except OSError as exc:
        res.found = True
        res.notes.append(f"Your Fresing settings could not be read ({exc.strerror or exc}): the defaults are used.")
        return res
    res.found = True
    try:
        data = json.loads(raw.decode("utf-8-sig"), parse_constant=_no_constant)
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ValueError("not a Fresing settings file")
        version = data.get("version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError("no version")
        settings = data.get("settings")
        if not isinstance(settings, dict):
            raise ValueError("no settings")
    except (ValueError, UnicodeDecodeError) as exc:
        kept = keep_broken(path)
        where = f" A copy is kept as {os.path.basename(kept)}." if kept else ""
        res.detail = str(exc)
        res.notes.append(f"Your Fresing settings file was damaged: the defaults are used.{where}")
        return res
    res.version = version
    bad = []
    for name, value in settings.items():
        if not isinstance(name, str):
            continue
        if name not in spec:
            res.extra[name] = value
            continue
        try:
            res.values[name] = clean(value, spec[name])
        except ValueError as exc:
            bad.append(f"{name} ({exc})")
    if bad:
        res.notes.append("Some Fresing settings were left at their default: " + ", ".join(sorted(bad)) + ".")
    return res


def _no_constant(name):
    raise ValueError(f"{name} is not a number")


def keep_broken(path: str) -> str:
    """Copy a broken file aside (never deleted: the user or IT may want it); its path, or '' when that failed."""
    stem, ext = os.path.splitext(path)
    target = f"{stem}.broken-{time.strftime('%Y%m%d-%H%M%S')}{ext}"
    n = 1
    while os.path.exists(target):
        n += 1
        target = f"{stem}.broken-{time.strftime('%Y%m%d-%H%M%S')}-{n}{ext}"
    try:
        shutil.copyfile(path, target)
    except OSError:
        return ""
    return target


def text(values: dict, spec: dict, extra: dict | None = None) -> str:
    settings = dict(extra or {})
    for name, v in changed(values, spec).items():
        settings[name] = list(v) if isinstance(v, tuple) else v
    data = {"format": FORMAT, "version": VERSION, "settings": dict(sorted(settings.items()))}
    return json.dumps(data, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def write(path: str, values: dict, spec: dict, extra: dict | None = None) -> None:
    """Write the file (temporary file + rename). Raises OSError when it cannot be written."""
    body = text(values, spec, extra)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
