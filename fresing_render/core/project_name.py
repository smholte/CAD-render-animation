"""Project names (task 0291) – the rule, no Blender.

* **The first save of a new project** proposes the name of the first model imported into it: the model root's name
  without an Inventor version (" v8"), an occurrence number (":1"), Blender's ".001" and a file ending (".iam",
  ".stp" …), with the characters Windows does not allow in a file name replaced. Nothing imported: "Untitled
  project". The setting "Leave empty" (Settings > General) proposes no name at all.
* **Save as on a saved project** proposes "<name> (1)" – the next number free in that folder, (2), (3) …; a name
  that already ends in " (n)" counts on from it ("Crane (1)" -> "Crane (2)").
* An already saved project is never renamed by the app.
"""

from __future__ import annotations

import os
import re

UNTITLED = "Untitled project"
MODES = ("model", "empty")               # Settings > General "Name of a new project"
DEFAULT_MODE = "model"
EXT = ".blend"
MAX_LEN = 120                            # characters of a proposed name (Windows' paths stay short enough)

# file endings a model root's name may carry (CAD, mesh, the project itself)
ENDINGS = (".iam", ".ipt", ".ipn", ".idw", ".stp", ".step", ".stpz", ".p21", ".sldasm", ".sldprt", ".f3d", ".f3z",
           ".x_t", ".x_b", ".igs", ".iges", ".stl", ".obj", ".glb", ".gltf", ".3mf", ".fbx", ".dae", ".ply",
           ".blend")
FORBIDDEN = '<>:"/\\|?*'
RESERVED = {"CON", "PRN", "AUX", "NUL", "CLOCK$", "CONIN$", "CONOUT$",
            *(f"COM{c}" for c in "0123456789¹²³"), *(f"LPT{c}" for c in "0123456789¹²³")}

_INVENTOR = re.compile(r"\s+v\d+$", re.IGNORECASE)          # "Crane v8"
_OCCURRENCE = re.compile(r":\d+$")                           # "Crane:1"
_BLENDER = re.compile(r"\.\d{3}$")                           # "Crane.001"
_NUMBER = re.compile(r"^(.*?) \((\d+)\)$")                   # "Crane (2)"


def _strip_once(name: str) -> str:
    name = name.strip()
    name = _BLENDER.sub("", name)
    name = _OCCURRENCE.sub("", name)
    low = name.lower()
    for e in ENDINGS:
        if low.endswith(e) and len(name) > len(e):
            name = name[:-len(e)]
            break
    return _INVENTOR.sub("", name.strip())


def clean(name: str) -> str:
    """A file name (without ``.blend``) made from a model's name; "" when nothing usable is left."""
    name = str(name or "")
    for _ in range(4):                   # "Crane v8.iam:1.001" – each piece once, in any order
        new = _strip_once(name)
        if new == name:
            break
        name = new
    out = "".join("_" if (c in FORBIDDEN or ord(c) < 32 or ord(c) == 127) else c for c in name)
    out = re.sub(r"\s+", " ", out).strip()
    out = out[:MAX_LEN].rstrip(" .")     # Windows drops trailing dots and spaces itself
    out = out.lstrip(" .")               # no hidden-looking ".name"
    if not out or set(out) <= {"_", "."}:
        return ""
    base = out.split(".", 1)[0].rstrip(" ")
    if base.upper() in RESERVED:         # "CON", "aux.x", "COM1": a device name, not a file
        out = out + "_" if base == out else base + "_" + out[len(base):]
    return out


def proposal(model_name: str, mode: str = DEFAULT_MODE) -> str:
    """The name the first save proposes: the first model's name, "Untitled project", or "" (``mode`` "empty")."""
    if mode == "empty":
        return ""
    return clean(model_name) or UNTITLED


def split_number(stem: str) -> tuple[str, int]:
    """("Crane", 2) for "Crane (2)"; ("Crane", 0) for "Crane"."""
    m = _NUMBER.match(stem)
    if m and m.group(1).strip():
        return m.group(1), int(m.group(2))
    return stem, 0


def numbered(stem: str, n: int) -> str:
    return f"{stem} ({n})"


def next_free(stem: str, taken) -> str:
    """The Save-as proposal for the project ``stem``: "<base> (n)" with the first n past the project's own number
    whose ``.blend`` is not in ``taken`` (file names in the folder; compared without case, as Windows does)."""
    taken = {str(t).casefold() for t in taken}
    base, n = split_number(stem)
    n += 1
    while (numbered(base, n) + EXT).casefold() in taken:
        n += 1
        if n > 9999:
            break
    return numbered(base, n)


def next_free_in(folder: str, stem: str) -> str:
    try:
        taken = os.listdir(folder)
    except OSError:
        taken = []
    return next_free(stem, taken)


def stem_of(path: str) -> str:
    base = os.path.basename(path or "")
    return base[:-len(EXT)] if base.lower().endswith(EXT) else base


def file_name(name: str) -> str:
    """"<name>.blend" for a typed name ("" stays ""); a typed ".blend" is not doubled."""
    name = (name or "").strip()
    if not name:
        return ""
    return name if name.lower().endswith(EXT) else name + EXT


def typed_problem(name: str) -> str:
    """Why a name typed in the Save-as box cannot be a file name on Windows; "" when it can."""
    stem = file_name(name)
    stem = stem[:-len(EXT)] if stem else ""
    if not stem.strip():
        return "Type a name for the new project"
    bad = sorted({c for c in stem if c in FORBIDDEN or ord(c) < 32})
    if bad:
        return "A file name cannot hold " + " ".join(bad)
    if stem.rstrip(" .") != stem:
        return "A file name cannot end in a dot or a space"
    if stem.split(".", 1)[0].rstrip(" ").upper() in RESERVED:
        return f"\"{stem}\" is a name Windows keeps for itself"
    return ""
