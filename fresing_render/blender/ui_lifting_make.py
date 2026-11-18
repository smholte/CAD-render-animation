"""8 Lifting plan > Equipment > Make a crane… (task 0204): the dialog's numbers and its drawing, and the line in the
Equipment panel (the button, the running job's progress with Cancel, then Place now / Enter your chart).

The numbers live on the window manager (``WindowManager.fresing_crane_make``), not in the project: making a crane
writes a library item, it changes nothing in the open project. One property per number of every kind, made from
``lifting_model/params.py`` (label, unit, limits); the dialog shows the kind's numbers in folds. Nothing heavy is
worked out while drawing: the "fits" line is ``params.validate`` (a few ms), cached on the numbers.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

from ..core import lifting as core
from ..lifting_model import classes as C
from ..lifting_model import params as P
from .ui import gap

DIALOG_CHARS = 72           # characters per line in the dialog (470 px wide): ``ui.wrap`` measures the side panel


def lines(layout, text: str, icon: str = "NONE", alert: bool = False, grey: bool = False):
    """Text wrapped at the dialog's width, the icon on the first line."""
    import textwrap
    col = layout.column(align=True)
    col.alert = alert
    col.active = not grey
    for k, ln in enumerate(textwrap.wrap(text, DIALOG_CHARS) or [""]):
        col.label(text=ln, icon=icon if k == 0 else "BLANK1" if icon != "NONE" else "NONE")
    return col

_CACHE: dict = {"key": None, "problems": []}
_ITEMS: dict = {}            # kind -> enum items (kept: Blender needs the strings to live)
UNIT_WORDS = {"m": "m", "mm": "mm", "t": "t", "deg": "°", "m/s": "m/s", "t·m": "t·m", "": ""}


def prop_name(kind: str, key: str) -> str:
    return f"{kind.lower()}_{key}"


def _start_items(self, context):
    kind = self.kind if self else "AT"
    if kind not in _ITEMS:
        _ITEMS[kind] = [(n, n, f"Start from the built-in {n}: its numbers fill the dialog")
                        for n in C.names(kind)]
    return _ITEMS[kind]


def load_class(m, name: str) -> None:
    """The class's numbers into the dialog."""
    c = C.CLASSES[name]
    vals = P.of_class(name)
    for f in P.FIELDS[c.kind]:
        setattr(m, prop_name(c.kind, f.key), f.to_ui(vals[f.key]))


def _start_changed(self, context):
    if self.start in C.CLASSES:
        load_class(self, self.start)


def _kind_changed(self, context):
    names = C.names(self.kind)
    pick = names[1] if len(names) > 1 else names[0]
    self.start = pick                       # loads its numbers (update of ``start``)


def values_of(m) -> dict:
    """The dialog's numbers as ``params`` values (the dataclass's units)."""
    out = {}
    for f in P.FIELDS[m.kind]:
        x = getattr(m, prop_name(m.kind, f.key))
        try:
            out[f.key] = f.from_ui(x)
        except ValueError:
            out[f.key] = x                  # validate names it
    return out


def spec_of(m) -> dict:
    from .. import __version__
    from ..lifting_model.make import SPEC_FORMAT
    return {"format": SPEC_FORMAT, "kind": m.kind, "name": m.name.strip(), "start": m.start,
            "values": values_of(m), "app": __version__}


def problems_of(m) -> list:
    """``params.validate`` of the dialog's numbers (cached on them)."""
    v = values_of(m)
    key = (m.kind, tuple(sorted((k, str(x)) for k, x in v.items())))
    if _CACHE["key"] != key:
        try:
            _CACHE["problems"] = P.validate(m.kind, v)
        except Exception as exc:  # noqa: BLE001 – the dialog must still draw
            _CACHE["problems"] = [P.Problem("error", f"These numbers cannot be worked out: {exc}")]
        _CACHE["key"] = key
    return _CACHE["problems"]


def _annotations() -> dict:
    ann = {
        "kind": EnumProperty(
            name="Type", items=[(k, P.KIND_LABELS[k], C.KIND_WORDS[k].capitalize()) for k in P.KINDS],
            default="AT", update=_kind_changed,
            description="The kind of crane to make: its numbers and folds follow. Then pick the class to start from"),
        "start": EnumProperty(
            name="Start from", items=_start_items, update=_start_changed,
            description="The built-in class whose numbers fill the dialog: change only the numbers you care about"),
        "name": StringProperty(
            name="Name", default="My crane",
            description="The crane's name in your library (a folder of that name in 'Lifting equipment')"),
        "replace": BoolProperty(
            name="Replace", default=False,
            description="Replaces a crane of the same name in your library. Off: a name already used is refused"),
    }
    for kind, fields in P.FIELDS.items():
        for f in fields:
            unit = UNIT_WORDS.get(f.unit, f.unit)
            label = f"{f.label} ({unit})" if unit else f.label
            rng = f"{f.lo:g} … {f.hi:g} {unit}".strip()
            what = (f.tip + ". ") if f.tip else ""
            if f.is_list:
                ann[prop_name(kind, f.key)] = StringProperty(
                    name=label, description=f"{what}A list of lengths in m, rising, separated by commas "
                                            f"(each {rng}). Make refuses what does not fit")
            elif f.integer:
                ann[prop_name(kind, f.key)] = IntProperty(
                    name=label, min=int(f.lo), max=int(f.hi),
                    description=f"{what}Between {rng.replace(' …', ' and').strip()}. Make refuses what does not fit")
            else:
                prec = {"m": 2, "mm": 0, "t": 2, "deg": 1, "m/s": 1, "t·m": 1}.get(f.unit, 2)
                ann[prop_name(kind, f.key)] = FloatProperty(
                    name=label, min=f.lo, max=f.hi, precision=prec, step=10 if f.unit in ("m", "t") else 100,
                    description=f"{what}Between {rng.replace(' …', ' and')}. Make refuses what does not fit")
    return ann


FRCraneMake = type("FRCraneMake", (bpy.types.PropertyGroup,), {"__annotations__": _annotations(),
                                                                 "__doc__": "Make a crane: the dialog's numbers"})


def settings(context=None):
    wm = (context or bpy.context).window_manager
    m = wm.fresing_crane_make
    if not m.get("_loaded"):
        m["_loaded"] = True
        load_class(m, m.start or "AT-100")
    return m


# ---------------------------------------------------------------------------------------------------------------------
# drawing

def draw_dialog(layout, context, m) -> None:
    layout.prop(m, "kind")
    layout.prop(m, "start")
    lines(layout, "Change only the numbers you care about; the rest stay the class's. Lengths in m, masses in t.",
          grey=True)
    for fold_name in P.FOLDS[m.kind]:
        header, body = layout.panel(f"fr_crane_make_{m.kind}_{fold_name}", default_closed=fold_name != "Boom")
        header.label(text=fold_name)
        if body is None:
            continue
        col = body.column(align=True)
        col.use_property_split = True
        col.use_property_decorate = False
        for f in P.fields_in(m.kind, fold_name):
            col.prop(m, prop_name(m.kind, f.key))
        if fold_name == "Masses":
            body.operator("fresing.lifting_make_masses", text="Masses from the class rule", icon="FILE_REFRESH")
    gap(layout)
    probs = problems_of(m)
    if probs:
        lines(layout, probs[0].text + (f"  (+{len(probs) - 1} more)" if len(probs) > 1 else ""), icon="ERROR",
              alert=True)
    else:
        lines(layout, "Fits: Make draws it, rigs it and works out its SAMPLE chart.", icon="CHECKMARK")
    gap(layout)
    col = layout.column(align=True)
    col.prop(m, "name")
    col.prop(m, "replace")
    from . import ops_lifting_make
    from ..lifting_model import job as J
    why = J.name_problem(ops_lifting_make.make_library(), m.name, m.replace)
    if why:
        lines(layout, why, icon="ERROR", alert=True)
    lines(layout, core.SAMPLE_MARK, icon="ERROR", alert=True)


def draw_in_equipment(layout, context) -> None:
    """One line in 8 Lifting plan > Equipment: Make a crane… (or the running job, or what to do with the crane
    just made)."""
    from . import ops_lifting_make as O
    job = O.running()
    if job is not None:
        row = layout.row(align=True)
        row.label(text=job.text(), icon="TIME")
        row.operator("fresing.lifting_make_cancel", text="Cancel", icon="CANCEL")
        return
    layout.operator("fresing.lifting_make", text="Make a crane…", icon="MODIFIER")
    from .ui import wrap
    last = O.STATE.get("message", "")
    if last:
        wrap(layout, context, last, icon="ERROR" if O.STATE.get("error") else "INFO", alert=bool(O.STATE.get("error")))
    made = O.STATE.get("made", "")
    if made:
        row = layout.row(align=True)
        row.operator("fresing.lifting_place", text="Place now…", icon="IMPORT").path = made
        row.operator("fresing.lifting_chart_csv", text="Enter your chart…", icon="SPREADSHEET").item = made


CLASSES = (FRCraneMake,)


def register_props() -> None:
    bpy.types.WindowManager.fresing_crane_make = bpy.props.PointerProperty(type=FRCraneMake)


def unregister_props() -> None:
    if hasattr(bpy.types.WindowManager, "fresing_crane_make"):
        del bpy.types.WindowManager.fresing_crane_make
