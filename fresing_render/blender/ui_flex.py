"""Side panel: 4 Motion > Hoses and drag chains (task 0058). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import flex, ops_flex
from .ui import MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, split_props, steps, wrap

ICONS = {"HOSE": "CURVE_BEZCURVE", "CHAIN": "LINKED"}
ALERT = ("WARN", "ERROR")
DIFFERS = 0.002               # a length this share off the CAD one was set by hand: show the CAD one beside it


def _mm(metres: float) -> str:
    return f"{metres * 1000.0:.0f} mm"


def short_status(scene, item) -> tuple[str, bool]:
    """(a word or two for the list row, show it as a warning)."""
    text, level = flex.status(scene, item)
    if level == "OFF":
        return "off", False
    if level == "ERROR":
        return "part missing", True
    if level == "WARN":
        for start, word in (("too short", "too short"), ("bends tighter", "tight bend"), ("cannot reach", "out of reach")):
            if text.startswith(start):
                return word, True
        return "check", True
    if item.kind == "CHAIN":
        return plural(len(item.links) or item.count, "link"), False
    return _mm(item.length), False


def counts(scene) -> tuple[str, bool]:
    """('4 hoses' | '3 chains' | '5 items', something needs a look) for the panel header: with a problem the text
    is '1 of 5' (how many need a look). Kept this short because the panel's title is long: "3 hoses, 1 chain"
    ran into the title at the default width."""
    its = list(flex.items(scene))
    hoses = sum(1 for it in its if it.kind == "HOSE")
    chains = len(its) - hoses
    bad = sum(1 for it in its if flex.status(scene, it)[1] in ALERT)
    if bad:
        return f"{bad} of {len(its)}", True
    if hoses and chains:
        return plural(len(its), "item"), False
    return (plural(hoses, "hose") if hoses else plural(chains, "chain") if chains else ""), False


class FRESING_UL_flex(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        text, alert = short_status(context.scene, item)
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        row.prop(item, "name", text="", emboss=False, icon=ICONS[item.kind])
        sub = row.row(align=True)                # the name gets the room: only a problem (or "off") is spelled out
        sub.alignment = "RIGHT"
        sub.alert = alert
        if alert:
            sub.label(text=text, icon="ERROR")
        elif not item.enabled:
            sub.label(text=text)
        else:
            sub.label(text="", icon="CHECKMARK")


def _end_row(layout, context, item, end: str) -> None:
    """'End A on: <part>' with the small button that fixes the end to the selected part."""
    ob = item.a_part if end == "A" else item.b_part
    row = layout.row(align=True)
    name = ops_flex._name(ob) if ob is not None else "no part"
    wrap(row.column(), context, f"{ops_flex.end_word(item, end)} on: {name}", inset=40, alert=ob is None)
    row.operator("fresing.flex_set_end", text="", icon="EYEDROPPER").end = end


def _add_buttons(layout, first: bool) -> None:
    """Add hose · Add cable / Add drag chain / Find. ``first``: nothing added yet, so "Add hose" is the main button."""
    row = big_row(layout, MEDIUM)
    row.operator("fresing.flex_add_hose", text="Add hose", icon="ADD", depress=first).soft = False
    row.operator("fresing.flex_add_hose", text="Add cable", icon="ADD").soft = True
    big_row(layout, MEDIUM).operator("fresing.flex_add_chain", text="Add drag chain", icon="ADD")
    layout.operator("fresing.flex_find", text="Find hoses and chains", icon="VIEWZOOM").add = False
    if first:
        layout.operator("fresing.flex_find", text="Find and add all", icon="CHECKMARK").add = True


class FRESING_PT_flex(_Panel, bpy.types.Panel):
    bl_label = "Hoses and drag chains"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="CURVE_BEZCURVE")

    def draw_header_preset(self, context):
        text, alert = counts(context.scene)
        if text:
            header_status(self.layout, text, icon="ERROR" if alert else "NONE", alert=alert, limit=9)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not len(s.flex):
            steps(layout, context, ["Click the hose or cable in the 3D view (or press 'Find hoses and chains')",
                                    "Press 'Add hose' or 'Add cable'",
                                    "Move a joint: the hose follows, both ends stay on their parts",
                                    "A drag chain: click one of its links (the app takes the whole row), "
                                    "then 'Add drag chain'"])
            _add_buttons(layout, first=True)
            return

        # -- the list
        row = layout.row()
        row.template_list("FRESING_UL_flex", "", s, "flex", s, "flex_index", rows=list_rows(len(s.flex), 2, 8))
        col = row.column(align=True)
        col.operator("fresing.flex_remove", text="", icon="REMOVE")
        col.operator("fresing.flex_select", text="", icon="RESTRICT_SELECT_OFF")
        _add_buttons(layout, first=False)

        # -- the chosen one
        fx = flex.active(scene)
        if fx is None:
            return
        layout.separator()
        chain = fx.kind == "CHAIN"
        layout.label(text=flex.label(fx), icon=ICONS[fx.kind])
        text, level = flex.status(scene, fx)
        if level in ALERT:
            what = "Drag chain" if chain else "Hose"
            wrap(layout, context, f"{what} {text}" if level == "WARN" else f"{what}: {text}", icon="ERROR", alert=True)
            if level == "WARN" and not chain and text.startswith("too short"):
                wrap(layout, context, "Make 'Length' longer, or check the parts its ends sit on.", icon="BLANK1")
        elif level == "OFF":
            wrap(layout, context, "Off: it shows stiff, as in the CAD file. Tick it in the list to switch it on.",
                 icon="INFO")
        else:
            layout.label(text="Follows the motion", icon="CHECKMARK")

        col = split_props(layout)
        if chain:
            col.prop(fx, "mode", text="Upper run")
            col.prop(fx, "radius", text="Bend radius")
            sub = col.row(align=True)
            sub.enabled = bool(fx.made_links)          # CAD links: as many as there are
            sub.prop(fx, "count", text="Links")
        else:
            col.prop(fx, "stiffness", text="Stiffness")
            col.prop(fx, "sag", text="Sag")
            col.prop(fx, "min_radius", text="Smallest bend")
            col.prop(fx, "length", text="Length")
            cad = fx.cad_length
            if cad > 0.0 and abs(fx.length - cad) > DIFFERS * cad:
                layout.label(text=f"In the CAD file: {cad * 1000.0:.1f} mm", icon="BLANK1")

        _end_row(layout, context, fx, "A")
        _end_row(layout, context, fx, "B")
        if chain:
            layout.operator("fresing.flex_swap_ends", text="Swap ends", icon="ARROW_LEFTRIGHT")
        layout.operator("fresing.flex_fit", text="Fit to the CAD pose", icon="LOOP_BACK")

        # -- rarely changed
        body = fold(layout, "fr_flex_more", "More", "PREFERENCES")
        if body:
            col = split_props(body)
            if chain:
                col.prop(fx, "pitch", text="Link length")
                if fx.made_links:
                    col.prop(fx, "width", text="Width")
                    col.prop(fx, "height", text="Height")
            else:
                col.prop(fx, "diameter", text="Diameter")


PANELS = (FRESING_PT_flex,)
CLASSES = (FRESING_UL_flex,) + PANELS
