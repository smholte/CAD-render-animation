"""Side panel: 4 Motion > Cables and paths (task 0078). Same layout rules as ui.py."""

from __future__ import annotations

import math
import time

import bpy
import numpy as np

from ..core.words import plural
from . import joints, ops_paths, paths
from .ops_flex import _name
from .ui import MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, primary, split_props, steps, wrap

ICON = "CURVE_PATH"
KIND_ICONS = {"SHEAVE": "MESH_TORUS", "ROLLER": "MESH_CYLINDER", "CHUTE": "SPHERECURVE", "BEND": "MOD_CURVE"}
KIND_SAYS = {"SHEAVE": "Sheave: the cable bends round it and turns it",
             "ROLLER": "Roller: the cable turns it, but does not bend round it",
             "CHUTE": "Chute: the cable bends round it and slides over it",
             "BEND": "Bend: the cable bends here as it was drawn, no part carries it"}
PASS_ICONS = {"over": "TRIA_UP", "under": "TRIA_DOWN", "beside": "TRIA_RIGHT", "round": "FILE_REFRESH", "": "BLANK1"}
PASS_SAYS = {"over": "the cable runs over it", "under": "the cable runs under it",
             "beside": "the cable runs past its side", "round": "the cable goes more than half round it"}
ALERT = ("WARN", "ERROR")
LEVEL_ICONS = {"OK": "CHECKMARK", "WARN": "ERROR", "ERROR": "ERROR", "OFF": "INFO"}
NAME_SHARE = 0.5                          # of a row of "What it touches": the name; the numbers have the rest
TOP = 0.95                                # the cable passes a wheel's top when it comes within 18° of straight above
GAP_NOTE = "the CAD cable is drawn"      # a contact's note that begins so is no fault: said without the red
FOUND_AGE = 5.0                           # seconds the number on "Add all … found" is kept before it is counted again

# runtime only: names and numbers, nothing of Blender is kept
_FOUND = {"key": None, "n": 0, "at": 0.0}
_PASSES: dict = {}


def forget() -> None:
    _FOUND.update(key=None, n=0, at=0.0)
    _PASSES.clear()


# ---------------------------------------------------------------------------
# words and numbers the panel shows
# ---------------------------------------------------------------------------

def short_status(scene, item) -> tuple[str, bool]:
    """(a word or two for the list row, show it as a warning); ('', False) when all is well."""
    text, level = paths.status(scene, item)
    if level == "OFF":
        return "off", False
    if level == "ERROR":
        return "no path", True
    if level == "WARN":
        for start, word in (("bends tighter", "tight bend"), ("no longer touches", "lifted off"),
                            ("goes ", "check side"), ("cannot go round", "no path"), ("has no path", "no path"),
                            ("its speed joint", "no speed")):
            if text.startswith(start):
                return word, True
        return "check", True
    return "", False


def counts(scene) -> tuple[str, bool]:
    """('2 cables' | '1 warning' | '–', something needs a look) for the panel header. Kept this short because the
    title is long: "1 cable, 1 warning" ran into it at the default width."""
    its = list(paths.items(scene))
    if not its:
        return "–", False
    bad = sum(1 for it in its if paths.status(scene, it)[1] in ALERT)
    return (plural(bad, "warning"), True) if bad else (plural(len(its), "cable"), False)


def found_count(scene) -> int:
    """How many parts are named like a cable and are no cable yet. Looking walks every part's name, so the number
    is kept until parts or cables come or go (and for at most ``FOUND_AGE`` seconds)."""
    s = scene.fresing
    key = (scene.name, len(scene.objects), len(s.cables), len(s.flex))
    now = time.monotonic()
    if _FOUND["key"] != key or now - _FOUND["at"] > FOUND_AGE:
        _FOUND.update(key=key, n=len(paths.candidates(scene)), at=now)
    return _FOUND["n"]


def diameter_text(item, c) -> str:
    """'Ø 500': twice the distance from the contact's axis to the cable's middle, mm."""
    return f"Ø {2000.0 * paths.radius_of(item, c):.0f}"


def wrap_text(c) -> str:
    """'192°' for something the cable bends round, '–' for a roller it only runs over."""
    return f"{math.degrees(c.wrap):.0f}°" if c.kind in paths.SHAPING else "–"


def ratio_text(scene, item, c) -> str:
    """'0.229° per mm': how far the contact's joint turns per mm of cable ('' when it does not turn)."""
    if c.kind not in paths.TURNING or not c.joint:
        return ""
    ratio = abs(float(c.ratio)) or abs(paths.ratio_of(scene, item, c))
    return f"{ratio:.3f}° per mm" if ratio else ""


def _where(shape: np.ndarray, centre: np.ndarray, axis: np.ndarray, radius: float) -> str:
    """Where a path (n, 3) lies on a wheel, seen with Z up: 'over', 'under', 'beside', 'round' (it passes both the
    top and the bottom) or '' when it cannot be told."""
    if len(shape) < 2:
        return ""
    a, seg = shape[:-1], shape[1:] - shape[:-1]
    t = np.clip(((centre - a) * seg).sum(axis=1) / np.maximum((seg * seg).sum(axis=1), 1e-18), 0.0, 1.0)
    rel = a + seg * t[:, None] - centre                         # each piece of the path: its point nearest the centre
    rel -= np.outer(rel @ axis, axis)
    dist = np.linalg.norm(rel, axis=1)
    near = (dist <= dist.min() + 0.001 + 0.02 * radius) & (dist > 1e-9)
    if not near.any():
        return ""
    ups = rel[near][:, 2] / dist[near]                          # 1: straight above the axis, -1: straight below
    top, bottom = bool(ups.max() > TOP), bool(ups.min() < -TOP)
    if top and bottom:
        return "round"
    if top or bottom:                                           # the cable passes its top (or its bottom) …
        return "over" if top else "under"
    u = rel[near].sum(axis=0)                                   # … else: the middle of where it lies on it
    up = float(u[2]) / (float(np.linalg.norm(u)) or 1.0)
    return "over" if up > 0.5 else "under" if up < -0.5 else "beside"


def pass_word(scene, item, index: int) -> str:
    """Where the cable lies on its contact ``index`` in the pose shown ('over', 'under', 'beside', 'round' or '').
    Worked out from the drawn path, one contact at a time (a list draws only the rows it shows), and kept until
    the path changes."""
    if not 0 <= index < len(item.contacts):
        return ""
    key = (scene.name, paths.index_of(scene, item))
    stamp = (scene.frame_current, round(float(item.length), 7), len(item.contacts), bool(item.enabled))
    hit = _PASSES.get(key)
    if hit is None or hit[0] != stamp:
        if len(_PASSES) > 50:
            _PASSES.clear()
        shape = np.asarray(paths.shape_now(scene, item), dtype=float) if item.enabled else np.zeros((0, 3))
        hit = _PASSES[key] = (stamp, shape, {})
    word = hit[2].get(index)
    if word is None:
        c = item.contacts[index]
        word = ""
        if c.carrier is not None:
            m = np.array(c.carrier.matrix_world, dtype=float)
            axis = m[:3, :3] @ np.array(c.axis, dtype=float)
            word = _where(hit[1], m[:3, :3] @ np.array(c.centre, dtype=float) + m[:3, 3],
                          axis / (np.linalg.norm(axis) or 1.0), paths.radius_of(item, c))
        hit[2][index] = word
    return word


def passes(scene, item) -> list[str]:
    """``pass_word`` for every contact of the cable."""
    return [pass_word(scene, item, i) for i in range(len(item.contacts))]


def end_text(item, end: str) -> tuple[str, bool]:
    """('Start on: WINCH DRUM' | 'End: free, stays with CHUTE' | …, the end has no part)."""
    key = end.lower()
    word = "Start" if key == "a" else "End"
    part = getattr(item, key + "_part")
    wheels = [c for c in item.contacts if c.kind in paths.SHAPING]
    near = wheels[0 if key == "a" else -1].name if wheels else ""
    if getattr(item, key + "_kind") == "WHEEL" and near:
        return f"{word}: lies on {near}", False
    if getattr(item, key + "_free_end"):
        return f"{word}: free" + (f", stays with {near}" if near else ""), False
    if part is None:
        return f"{word}: no part", True
    return f"{word} on: {_name(part)}", False


# ---------------------------------------------------------------------------
# the two lists
# ---------------------------------------------------------------------------

class FRESING_UL_cables(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        text, alert = short_status(context.scene, item)
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon=ICON)
        sub = row.row(align=True)                # the name gets the room: only a problem (or "off") is spelled out
        sub.alignment = "RIGHT"
        sub.alert = alert
        if alert:
            sub.label(text=text, icon="ERROR")
        elif text:
            sub.label(text=text)
        else:
            sub.label(text="", icon="CHECKMARK")


class FRESING_UL_cable_contacts(bpy.types.UIList):
    """One line per thing the cable touches: kind, name, Ø at the cable's middle, wrap, over / under, turns."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=NAME_SHARE, align=True)      # the name keeps its share of the row
        split.label(text=item.name, icon=KIND_ICONS.get(item.kind, "DOT"))
        row = split.row(align=True)
        for text, width in ((diameter_text(data, item), 2.4), (wrap_text(item), 1.6)):
            sub = row.row(align=True)
            sub.ui_units_x = width
            sub.alignment = "RIGHT"
            sub.label(text=text)
        sub = row.row(align=True)
        sub.ui_units_x = 1.8
        sub.label(text="", icon=PASS_ICONS[pass_word(context.scene, data, index)])
        if item.kind in paths.TURNING and item.joint:
            sub.prop(item, "turns", text="")
        else:
            sub.label(text="", icon="BLANK1")


# ---------------------------------------------------------------------------
# the panel
# ---------------------------------------------------------------------------

def _add_buttons(layout, scene, first: bool) -> None:
    """Add cable (the main button while the list is empty) and, when parts are named like a cable, Add all. Above
    them the choice they act on (task 0079): an existing slide joint as the new cable's speed."""
    split_props(layout).prop_search(scene.fresing, "cable_speed", scene.fresing, "joints", text="Speed from")
    if first:
        primary(layout, "fresing.cable_add", "Add cable", "ADD")
    else:
        big_row(layout, MEDIUM).operator("fresing.cable_add", text="Add cable", icon="ADD")
    n = found_count(scene)
    if n:
        layout.operator("fresing.cable_add_all", text=f"Add all {n} found by name", icon="VIEWZOOM")


def _end_row(layout, context, cb, end: str) -> None:
    """'End on: <part>' with the pipette that fixes the end to a clicked part and, for an end on a part, the
    small button that makes it a free end again."""
    text, alert = end_text(cb, end)
    row = layout.row(align=True)
    wrap(row.column(), context, text, inset=64, alert=alert)
    op = row.operator("fresing.cable_end", text="", icon="EYEDROPPER")
    op.end, op.free = end, False
    key = end.lower()
    if getattr(cb, key + "_kind") == "FIXED" and not getattr(cb, key + "_free_end"):
        op = row.operator("fresing.cable_end", text="", icon="X")
        op.end, op.free = end, True


def _contact_details(layout, context, cb, index: int) -> None:
    """The chosen contact, under the list: what it is, its numbers, its note."""
    scene = context.scene
    ct = cb.contacts[index]
    box = layout.box()
    box.label(text=ct.name, icon=KIND_ICONS.get(ct.kind, "DOT"))
    where = PASS_SAYS.get(pass_word(scene, cb, index), "")
    wrap(box, context, KIND_SAYS.get(ct.kind, ct.kind) + (f"; {where}" if where else ""), inset=12)
    col = box.column(align=True)
    col.label(text=f"{diameter_text(cb, ct)} mm at the cable's middle")
    if ct.kind in paths.SHAPING:
        col.label(text=f"Wrap {wrap_text(ct)}")
    ratio = ratio_text(scene, cb, ct)
    if ct.kind in paths.TURNING and ct.joint:
        col.label(text=f"Turns {ratio}" if ratio and ct.turns else "Stands still")
        wrap(col, context, f"Its joint: {ct.joint}", inset=12)
        box.prop(ct, "turns", text="Turns with the cable")
    elif ct.kind in paths.TURNING:
        col.label(text="Has no joint: it does not turn")
    else:
        col.label(text="Does not turn")
    if ct.note:
        gap = ct.note.startswith(GAP_NOTE)
        wrap(box, context, ct.note[:1].upper() + ct.note[1:], icon="INFO" if gap else "ERROR", inset=12,
             alert=not gap)


class FRESING_PT_cables(_Panel, bpy.types.Panel):
    bl_label = "Cables and paths"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon=ICON)

    def draw_header_preset(self, context):
        text, alert = counts(context.scene)
        header_status(self.layout, text, icon="ERROR" if alert else "NONE", alert=alert, limit=11)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not len(s.cables):
            steps(layout, context, ["Click the cable or wire rope in the 3D view",
                                    "Press 'Add cable': the app reads what it runs over and makes all of that "
                                    "turn with it",
                                    "Give it a speed: in 6 Animation add the step 'Run motor', speed in m/min"])
            _add_buttons(layout, scene, first=True)
            return

        # -- the list
        row = layout.row()
        row.template_list("FRESING_UL_cables", "", s, "cables", s, "cables_index", rows=list_rows(len(s.cables), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.cable_remove", text="", icon="REMOVE")
        col.operator("fresing.cable_select", text="", icon="RESTRICT_SELECT_OFF")
        _add_buttons(layout, scene, first=False)

        # -- the chosen one
        cb = paths.active(scene)
        if cb is None:
            return
        layout.separator()
        layout.label(text=paths.label(cb), icon=ICON)
        text, level = paths.status(scene, cb)
        if level == "OFF":
            wrap(layout, context, "Off: it shows as in the CAD file and nothing turns with it. Tick it in the list "
                 "to switch it on.", icon="INFO")
        elif level in ALERT:
            wrap(layout, context, f"Cable {text}" if level == "WARN" and not text.startswith("its ")
                 else f"Cable: {text}", icon="ERROR", alert=True)
        else:
            wrap(layout, context, text[:1].upper() + text[1:], icon=LEVEL_ICONS[level])

        # -- its speed
        if cb.joint and joints.find(scene, cb.joint) is not None:
            wrap(layout, context, f"Cable speed: joint '{cb.joint}'", icon="FORCE_VORTEX")
            wrap(layout, context, "Animate it in 6 Animation with the step Run motor: speed in m/min", icon="BLANK1")
            layout.operator("fresing.cable_motor_step", text="Add a Run motor step", icon="ADD")

        # -- its look
        col = split_props(layout)
        col.prop(cb, "look", text="Look")
        if cb.look == "POWER":
            col.prop(cb, "pitch", text="Stripe distance")
            col.prop(cb, "angle", text="Stripe angle")
            col.prop(cb, "stripe", text="Stripe width")
        elif cb.look == "ROPE":
            col.prop(cb, "pitch", text="Lay length")
        layout.operator("fresing.cable_read", text="From CAD cable again", icon="FILE_REFRESH")

        # -- what it touches
        layout.separator()
        n = len(cb.contacts)
        layout.label(text=f"What it touches ({n})" if n else "What it touches", icon="LINKED")
        # (the list has the whole width – its rows hold a name and four columns – so its buttons sit under it)
        layout.template_list("FRESING_UL_cable_contacts", "", cb, "contacts", cb, "contacts_index",
                             rows=list_rows(n, 3, 8))
        row = layout.row(align=True)
        row.operator("fresing.cable_contact_add", text="Add", icon="ADD")
        row.operator("fresing.cable_contact_remove", text="Remove", icon="REMOVE")
        row.operator("fresing.cable_contact_flip", text="Flip side")
        _item, index = ops_paths.chosen_contact(context)
        if index >= 0:
            _contact_details(layout, context, cb, index)
        _end_row(layout, context, cb, "A")
        _end_row(layout, context, cb, "B")

        # -- rarely changed
        body = fold(layout, "fr_cables_more", "More", "PREFERENCES")
        if body:
            col = split_props(body)                 # (labels of up to 15 letters fit beside their field)
            col.prop(cb, "diameter", text="Diameter")
            col.prop(cb, "mbr", text="Min. bend (MBR)")
            if cb.a_free_end:
                col.prop(cb, "a_free", text="Free at start")
            if cb.b_free_end:
                col.prop(cb, "b_free", text="Free at end")
            col = body.column(align=True)
            col.prop(cb, "reverse", text="Runs the other way")
            col.prop(cb, "still", text="Stays as drawn")


PANELS = (FRESING_PT_cables,)
CLASSES = (FRESING_UL_cables, FRESING_UL_cable_contacts) + PANELS
