"""Operators for hoses, cables and drag chains (4 Motion > Hoses and drag chains, task 0058).

The work is in flex.py; here is what a button does with the selection. Three things the buttons know:

* **What was clicked.** With "Click selects: Subassembly" a click on a hose selects its whole subassembly; the
  hose itself stays the active object. ``clicked`` gives that one part, so "Add hose" takes the hose and not the
  forty parts round it. Without it (parts picked one by one, a row selected in 2 Structure, the result of "Find
  hoses and chains") every selected part counts.
* **A chain's row of links.** One clicked link is enough: ``row_of`` gives the links that make one chain with it –
  by their names (``flex.siblings``) or, for bought-in links that are only a part number, the parts of the same
  shape in the same subassembly.
* **Cable or hose.** A part whose name or part type says cable starts soft, whichever button added it.
"""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty

from ..core.words import plural
from . import build, flex

MIN_LINKS = 4                 # fewer parts are no chain of links
TOO_FEW = (f"A drag chain has {MIN_LINKS} links or more: click one link (the app takes the whole row) or select "
           "all its links")
_CABLE_GROUP = "Cables"
_CABLE_WORDS = ("CABLE", "CABLES", "KABEL", "KABELS", "WIRE", "LEITUNG")


# ---------------------------------------------------------------------------
# what the buttons work on
# ---------------------------------------------------------------------------

def _name(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def _is_part(ob) -> bool:
    return ob is not None and ob.get(build.PROP_KIND) == "part" and ob.type == "MESH"


def selected_parts(context) -> list:
    """The selected model parts (no subassemblies, no joint arrows), the active one first."""
    parts = [ob for ob in context.selected_objects if _is_part(ob)]
    active = context.view_layer.objects.active
    if active in parts:
        parts.remove(active)
        parts.insert(0, active)
    return parts


def clicked(context):
    """The one part a click meant when it selected the part's whole subassembly: the active part, when a
    subassembly above it is selected too. None when the parts were picked one by one."""
    ob = context.view_layer.objects.active
    if not _is_part(ob) or not ob.select_get():
        return None
    p = build.logical_parent(ob)
    while p is not None:
        try:
            if p.select_get():
                return ob
        except RuntimeError:                      # not in this view layer
            pass
        p = build.logical_parent(p)
    return None


def targets(context) -> list:
    """The parts a button works on: the clicked part alone, else every selected part."""
    one = clicked(context)
    return [one] if one is not None else selected_parts(context)


def is_cable(ob) -> bool:
    """The part's material group, part type or name says cable (not hose)."""
    from ..core import part_types
    group = str(ob.get(build.PROP_GROUP, "") or "")
    if group == _CABLE_GROUP or group.startswith(_CABLE_GROUP + " #"):
        return True
    name = _name(ob)
    try:
        kind = part_types.type_of(name, build.path_of(ob))
    except Exception:
        kind = None
    if kind is not None:
        return kind == "cable"
    words = name.upper().replace(".", " ").replace("_", " ").replace("-", " ").split()
    return any(w in _CABLE_WORDS for w in words)


def row_of(scene, ob) -> list:
    """The links that make one chain with ``ob``: the chain parts found by name in its subassembly, else the
    parts of the same shape there. [] when ``ob`` is no link of a row (then it may be a chain drawn as one solid)."""
    row = flex.siblings(scene, ob)
    if len(row) >= MIN_LINKS and any(o == ob for o in row):
        return row
    taken = {o.name for o in flex.flex_parts(scene)}
    home = build.logical_parent(ob)
    same = [o for o in build.iter_parts(scene)
            if o.data == ob.data and o.name not in taken and build.logical_parent(o) == home]
    return same if len(same) >= MIN_LINKS else []


def _rows(parts: list) -> list:
    """Chain parts sorted into chains: the parts of one subassembly are one chain."""
    rows: dict = {}
    for ob in parts:
        home = build.logical_parent(ob)
        rows.setdefault(home.name if home is not None else "", []).append(ob)
    return list(rows.values())


def _try(scene, make, what: str):
    """Run ``make`` (one add). Returns (item, notes), or the plain reason why not. A part the app cannot read is
    refused in words (FlexError). Anything else is a fault in the app: it is named with the part, written to
    the console in full, and no half-made line stays in the list – the other parts still get their turn."""
    before = len(scene.fresing.flex)
    try:
        return make()
    except flex.FlexError as exc:
        reason = str(exc)
    except Exception as exc:                      # noqa: BLE001 - see above
        import traceback
        traceback.print_exc()
        reason = f"{what} could not be read (a fault in the app: {type(exc).__name__}: {exc})"
    while len(scene.fresing.flex) > before:
        flex.remove(scene, len(scene.fresing.flex) - 1)
    return reason


def _add(scene, hoses: list, rows: list, soft: bool = False) -> dict:
    """Add the hoses one by one and each row as one chain. Returns what happened: the names added
    (``hoses``, ``cables``, ``chains``), the reasons of parts that were refused, and notes."""
    out = {"hoses": [], "cables": [], "chains": [], "refused": [], "notes": []}
    for ob in hoses:
        cable = soft or is_cable(ob)
        got = _try(scene, lambda: flex.add_hose(scene, ob, soft=cable), f"'{_name(ob)}'")
        if isinstance(got, str):
            out["refused"].append(got)
            continue
        out["cables" if cable else "hoses"].append(got[0].name)    # names only: the list grows with every add
        out["notes"] += got[1]
    for row in rows:
        if 1 < len(row) < MIN_LINKS:
            out["refused"].append(TOO_FEW)
            continue
        # one part: a chain drawn as one solid, the app draws its links
        links, part = (row, None) if len(row) > 1 else ([], row[0])
        got = _try(scene, lambda: flex.add_chain(scene, links, part=part), f"The chain with '{_name(row[0])}'")
        if isinstance(got, str):
            out["refused"].append(got)
            continue
        out["chains"].append(got[0].name)
        out["notes"] += got[1]
    return out


def _counts(out: dict) -> str:
    """'2 hoses, 1 cable and 3 drag chains' of what was added ('' for nothing)."""
    words = [plural(len(out[key]), word) for key, word in (("hoses", "hose"), ("cables", "cable"),
                                                            ("chains", "drag chain")) if out[key]]
    return ", ".join(words[:-1]) + (" and " if len(words) > 1 else "") + words[-1] if words else ""


def _refusals(refused: list) -> str:
    if not refused:
        return ""
    if len(refused) == 1:
        return refused[0]
    return f"{len(refused)} parts were left out (the first: {refused[0]})"


def _say(context, op, text: str, level: str = "INFO") -> None:
    context.scene.fresing.last_message = text
    op.report({level}, text)


def _finish(context, op, out: dict, nothing: str) -> set:
    """Tell what was added and what was refused; the notes of flex.py (an end that touches no part) as warnings."""
    added = _counts(out)
    refused = _refusals(out["refused"])
    for note in out["notes"][:4]:
        op.report({"WARNING"}, note)
    if added:
        _say(context, op, f"{added} added: move a joint and {'it follows' if _total(out) == 1 else 'they follow'}"
             + (f". {refused}" if refused else ""), "WARNING" if refused else "INFO")
        return {"FINISHED"}
    _say(context, op, refused or nothing, "WARNING")
    return {"CANCELLED"}


def _total(out: dict) -> int:
    return len(out["hoses"]) + len(out["cables"]) + len(out["chains"])


def _select(context, parts: list) -> int:
    """Select exactly these parts in the view (the ones that can be: a hidden part cannot)."""
    from . import handlers
    vl = context.view_layer
    for ob in list(context.selected_objects):
        try:
            ob.select_set(False)
        except RuntimeError:
            pass
    done = []
    for ob in parts:
        try:
            ob.select_set(True)
            if ob.select_get():
                done.append(ob)
        except (RuntimeError, ReferenceError):
            pass
    if done:
        handlers.ignore_next(done[0])            # exactly these parts, not their subassembly
        vl.objects.active = done[0]
    return len(done)


def _item(context):
    return flex.active(context.scene)


class _Op:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        scene = context.scene
        return scene is not None and hasattr(scene, "fresing") and scene.fresing.model_count > 0


class _NeedsPart(_Op):
    """A button that works on the selected part(s)."""

    @classmethod
    def poll(cls, context):
        return super().poll(context) and any(_is_part(ob) for ob in context.selected_objects)


class _NeedsItem(_Op):
    """A button that works on the hose or chain chosen in the list."""

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _item(context) is not None


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

class FRESING_OT_flex_add_hose(_NeedsPart, bpy.types.Operator):
    """Makes the hose you clicked bend along with the motion: both ends stay on their fittings and its length
    stays the same. Click the hose in the 3D view first (or several, one by one), then press this. Then set its
    stiffness and sag under the list"""

    bl_idname = "fresing.flex_add_hose"
    bl_label = "Add hose"

    soft: BoolProperty(name="Cable", default=False, options={"SKIP_SAVE"},
                       description="Start soft, like a cable that hangs in an arc, instead of stiff like a "
                                   "hydraulic hose")

    @classmethod
    def description(cls, context, properties):
        if properties.soft:
            return ("Makes the cable you clicked hang and bend along with the motion: both ends stay on their "
                    "parts and its length stays the same. Click the cable in the 3D view first, then press this. "
                    "It starts soft; set its stiffness and sag under the list")
        return " ".join(cls.__doc__.split())

    def execute(self, context):
        scene = context.scene
        parts = targets(context)
        word = "cable" if self.soft else "hose"
        if not parts:
            _say(context, self, f"First click the {word} in the 3D view, then press this", "WARNING")
            return {"CANCELLED"}
        if len(parts) > 1:                       # the result of "Find hoses and chains": chain links wait for
            kinds = {ob.name: kind for ob, kind in flex.candidates(scene)}     # "Add drag chain"
            hoses = [ob for ob in parts if kinds.get(ob.name) != "CHAIN"]
            if not hoses:
                _say(context, self, "These parts are the links of a drag chain: press Add drag chain", "WARNING")
                return {"CANCELLED"}
            parts = hoses
        taken = {ob.name for ob in flex.flex_parts(scene)}
        free = [ob for ob in parts if ob.name not in taken]
        if not free:
            _say(context, self, f"'{_name(parts[0])}' already follows the motion: it is in the list"
                 if len(parts) == 1 else "These parts already follow the motion: they are in the list", "WARNING")
            return {"CANCELLED"}
        out = _add(scene, free, [], soft=self.soft)
        return _finish(context, self, out, f"First click the {word} in the 3D view, then press this")


class FRESING_OT_flex_add_chain(_NeedsPart, bpy.types.Operator):
    """Makes a drag chain (energy chain) roll along with the motion. Click one of its links in the 3D view: the
    app takes the whole row of links. Or select all its links yourself, or the one part a simplified chain is
    drawn as. Its fixed end, moving end, link length and bend radius are read from the CAD pose"""

    bl_idname = "fresing.flex_add_chain"
    bl_label = "Add drag chain"

    def execute(self, context):
        scene = context.scene
        parts = selected_parts(context)
        one = clicked(context) or (parts[0] if len(parts) == 1 else None)
        hint = ("First click one link of the drag chain in the 3D view (or select all its links), "
                "then press this")
        if not parts:
            _say(context, self, hint, "WARNING")
            return {"CANCELLED"}
        taken = {ob.name: it for it in scene.fresing.flex for ob in flex.parts_of(scene, it)}
        if one is not None:
            if one.name in taken:
                _say(context, self, f"'{_name(one)}' already follows the motion as '{flex.label(taken[one.name])}'",
                     "WARNING")
                return {"CANCELLED"}
            row = row_of(scene, one)
            rows = [row] if row else [[one]]      # no row of links: the chain is this one solid
        else:
            free = [ob for ob in parts if ob.name not in taken]
            kinds = {ob.name: kind for ob, kind in flex.candidates(scene)}
            links = [ob for ob in free if kinds.get(ob.name) == "CHAIN"]
            if links:                             # found by name: one chain per subassembly
                rows = _rows(links)
            elif len(free) >= MIN_LINKS:
                rows = [free]
            else:
                _say(context, self, TOO_FEW, "WARNING")
                return {"CANCELLED"}
        out = _add(scene, [], rows)
        return _finish(context, self, out, hint)


class FRESING_OT_flex_find(_Op, bpy.types.Operator):
    """Looks for the parts that are named like a hose, a cable or a drag chain and selects them in the 3D view,
    so you can see what was found. Then press Add hose or Add drag chain. Parts with other names are not found:
    click those yourself"""

    bl_idname = "fresing.flex_find"
    bl_label = "Find hoses and chains"

    add: BoolProperty(name="Add them", default=False, options={"SKIP_SAVE"},
                      description="Add everything that is found at once instead of only selecting it")

    @classmethod
    def description(cls, context, properties):
        if properties.add:
            return ("Looks for the parts that are named like a hose, a cable or a drag chain and makes them all "
                    "follow the motion at once: every hose and cable on its own, every row of chain links as one "
                    "drag chain. Parts that turn out to be something else are left as they are and named in "
                    "the message")
        return " ".join(cls.__doc__.split())

    def execute(self, context):
        scene = context.scene
        found = flex.candidates(scene)
        hoses = [ob for ob, kind in found if kind == "HOSE"]
        links = [ob for ob, kind in found if kind == "CHAIN"]
        if not found:
            _say(context, self, "No part is named like a hose, a cable or a drag chain. Click the part yourself, "
                 "then press Add hose or Add drag chain", "WARNING")
            return {"CANCELLED"}
        if self.add:
            out = _add(scene, hoses, _rows(links))
            return _finish(context, self, out, "Nothing could be added")
        n = _select(context, hoses + links)
        words = [plural(len(hoses), "hose or cable", "hoses and cables")] if hoses else []
        words += [plural(len(links), "chain link" if len(links) >= MIN_LINKS else "drag chain")] if links else []
        press = " / ".join((["Add hose"] if hoses else []) + (["Add drag chain"] if links else []))
        text = f"{' and '.join(words)} found and selected: press {press}"
        if n < len(found):
            text += f" ({plural(len(found) - n, 'hidden part')} could not be selected)"
        _say(context, self, text)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# the chosen item
# ---------------------------------------------------------------------------

class FRESING_OT_flex_remove(_NeedsItem, bpy.types.Operator):
    """Takes the chosen hose or drag chain off the list. Its part shows stiff again, exactly as in the CAD file;
    nothing is deleted from the model"""

    bl_idname = "fresing.flex_remove"
    bl_label = "Remove from the list"

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        name, word = flex.label(item), _word(item)
        flex.remove(scene, scene.fresing.flex_index)
        _say(context, self, f"{word} '{name}' removed from the list: it shows as in the CAD file again")
        return {"FINISHED"}


class FRESING_OT_flex_fit(_NeedsItem, bpy.types.Operator):
    """Reads the chosen hose or drag chain from the CAD file again: its length, diameter and ends, or a chain's
    link length, bend radius and ends. Use it after you changed these numbers and want the drawn ones back.
    Stiffness, sag and the smallest bend stay as you set them"""

    bl_idname = "fresing.flex_fit"
    bl_label = "Fit to the CAD pose"

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        name, word = flex.label(item), _word(item)
        try:
            notes = flex.fit_to_cad(scene, item)
        except flex.FlexError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        for note in notes:
            self.report({"WARNING"}, note)
        why = flex.broken(scene, _item(context))
        if why:                                   # a part of it is gone from the model: nothing to read
            _say(context, self, f"{word} '{name}': {why}", "WARNING")
            return {"CANCELLED"}
        _say(context, self, f"{word} '{name}' is as drawn in the CAD file again")
        return {"FINISHED"}


class FRESING_OT_flex_set_end(_NeedsItem, bpy.types.Operator):
    """Fixes this end to the part you selected: from now on the end moves with that part. Use it when the app
    picked the wrong part for an end, or says an end touches no part: click the fitting or bracket in the 3D
    view first, then press this. The end stays where it is now"""

    bl_idname = "fresing.flex_set_end"
    bl_label = "Set to selected part"

    end: EnumProperty(name="End", default="A", options={"SKIP_SAVE"},
                      description="Which end of the hose or chain is fixed to the selected part",
                      items=[("A", "End A", "The first end of a hose; a drag chain's fixed end"),
                             ("B", "End B", "The second end of a hose; a drag chain's moving end")])

    @classmethod
    def poll(cls, context):
        if not super().poll(context):
            return False
        return end_target(context, _item(context)) is not None

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        ob = end_target(context, item)
        if ob is None:
            _say(context, self, "First click the part this end is fixed to (not the hose itself)", "WARNING")
            return {"CANCELLED"}
        if ob.name in {o.name for o in flex.flex_parts(scene)}:
            _say(context, self, f"'{_name(ob)}' is a hose or chain itself: pick the fitting or bracket the end "
                 "is fixed to", "WARNING")
            return {"CANCELLED"}
        name = flex.label(item)
        flex.set_end_part(scene, item, self.end, ob)
        _say(context, self, f"{end_word(item, self.end)} of '{name}' now moves with '{_name(ob)}'")
        return {"FINISHED"}


class FRESING_OT_flex_swap_ends(_NeedsItem, bpy.types.Operator):
    """Makes the other end of the drag chain the fixed one. Use it when the chain rolls the wrong way: the fixed
    end is the one bolted to the part that stands still, the moving end rides with the axis"""

    bl_idname = "fresing.flex_swap_ends"
    bl_label = "Swap ends"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _item(context).kind == "CHAIN"

    def execute(self, context):
        scene = context.scene
        item = _item(context)
        name = flex.label(item)
        try:
            flex.swap_ends(scene, item)
        except flex.FlexError as exc:
            _say(context, self, str(exc), "WARNING")
            return {"CANCELLED"}
        item = _item(context)
        _say(context, self, f"Drag chain '{name}': the fixed end is now on '{_name(item.a_part)}'")
        return {"FINISHED"}


class FRESING_OT_flex_select(_NeedsItem, bpy.types.Operator):
    """Selects the chosen hose, or all links of the chosen drag chain, in the 3D view. So you can see which part
    of the machine this line of the list is"""

    bl_idname = "fresing.flex_select"
    bl_label = "Select"
    bl_options = {"REGISTER"}

    def execute(self, context):
        item = _item(context)
        n = _select(context, flex.parts_of(context.scene, item))
        if not n:
            _say(context, self, f"'{flex.label(item)}' is hidden or its part is gone: nothing to select", "WARNING")
            return {"CANCELLED"}
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# shared with the panel
# ---------------------------------------------------------------------------

def _word(item) -> str:
    return "Drag chain" if item.kind == "CHAIN" else "Hose"


def end_word(item, end: str) -> str:
    """What the panel calls an end: 'End A' / 'End B' of a hose, 'Fixed end' / 'Moving end' of a chain."""
    first = str(end).upper() == "A"
    if item.kind == "CHAIN":
        return "Fixed end" if first else "Moving end"
    return "End A" if first else "End B"


def end_target(context, item):
    """The part "Set to selected part" would take: the active object when it is a selected model part or
    subassembly and not the hose or a link of the chain itself. Else None."""
    if item is None:
        return None
    ob = context.view_layer.objects.active
    if ob is None or ob.get(build.PROP_KIND) not in build.MODEL_KINDS or not ob.select_get():
        return None
    if ob == item.part or any(r.obj == ob for r in item.links):
        return None
    return ob


CLASSES = (FRESING_OT_flex_add_hose, FRESING_OT_flex_add_chain, FRESING_OT_flex_find, FRESING_OT_flex_remove,
           FRESING_OT_flex_fit, FRESING_OT_flex_set_end, FRESING_OT_flex_swap_ends, FRESING_OT_flex_select)
