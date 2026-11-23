"""Place and Remove (task 0292): the numbers and words of 2 Structure > Place, without Blender.

* **Snap** – where a typed, dragged or mouse-moved value lands: off, 1 / 10 / 100 mm, 5 / 15 / 45 degrees.
* **Steps** – the ± buttons beside the fields: 10 or 100 mm, 15 or 90 degrees.
* **The Remove window's list** – what goes with a model, a subassembly or parts (``summary``), in plain words.
* **Put on the floor** – how far something must go up or down so its lowest point sits on the floor (``to_floor``).

The matrix work lives in ``blender/place.py`` (it needs Blender's matrices); the rules it follows are written at
the top of that file.
"""

from __future__ import annotations

from .words import plural

SNAP_MOVE = (("OFF", "Off", 0.0), ("1", "1 mm", 1.0), ("10", "10 mm", 10.0), ("100", "100 mm", 100.0))
SNAP_TURN = (("OFF", "Off", 0.0), ("5", "5°", 5.0), ("15", "15°", 15.0), ("45", "45°", 45.0))
STEP_MOVE = (("10", "10 mm", 10.0), ("100", "100 mm", 100.0))
STEP_TURN = (("15", "15°", 15.0), ("90", "90°", 90.0))


def size_of(table, key: str) -> float:
    """The number behind a choice of one of the tables above (0 for Off or an unknown key)."""
    for k, _label, value in table:
        if k == key:
            return value
    return 0.0


def snap(value: float, step: float) -> float:
    """``value`` rounded to the nearest multiple of ``step`` (as it is when ``step`` is 0 or less)."""
    if step <= 0.0:
        return float(value)
    out = round(float(value) / step) * step
    return 0.0 if out == 0.0 else out          # never "-0"


def to_floor(lowest_z: float, floor_z: float = 0.0) -> float:
    """How far to move up (positive) or down so the lowest point lands on the floor."""
    return float(floor_z) - float(lowest_z)


def wrap_degrees(value: float) -> float:
    """An angle in -180 … 180 (what the Turn fields show)."""
    v = (float(value) + 180.0) % 360.0 - 180.0
    return 0.0 if v == 0.0 else v


# ---------------------------------------------------------------------------
# the Remove window
# ---------------------------------------------------------------------------

# (key in the plan, singular word, plural word or None) in the order the window lists them
GOES = (
    ("models", "model", None),
    ("subassemblies", "subassembly", None),
    ("parts", "part", None),
    ("joints", "joint", None),
    ("cylinders", "cylinder", None),
    ("mechanisms", "mechanism", None),
    ("way_covers", "way cover", None),
    ("hoses", "hose or drag chain", "hoses and drag chains"),
    ("cables", "cable", None),
    ("spools", "drum or carousel", "drums and carousels"),
    ("tracks", "track or belt", "tracks and belts"),
    ("labels", "label", None),
    ("decals", "logo or sticker", "logos and stickers"),
    ("steps", "animation step", None),
)


def summary(plan: dict) -> list[str]:
    """The lines of the Remove window: what goes, then what only loses something, then what stays.

    ``plan`` holds counts under the keys of ``GOES`` and lists of plain sentences under ``"loses"`` (a joint that
    keeps other parts, a step that also moves other things) and ``"names"`` (what was chosen)."""
    lines = []
    goes = [plural(int(plan.get(key, 0)), one, many) for key, one, many in GOES if int(plan.get(key, 0) or 0) > 0]
    if goes:
        lines.append("Goes: " + ", ".join(goes))
    for text in plan.get("loses", ()) or ():
        lines.append(text)
    return lines


def title(plan: dict) -> str:
    """The window's first line: 'Remove "Crane"?' or 'Remove 3 parts?'."""
    names = list(plan.get("names", ()) or ())
    if len(names) == 1:
        return f"Remove '{names[0]}'?"
    if not names:
        return "Nothing to remove"
    return f"Remove '{names[0]}' and {len(names) - 1} more?"
