"""Side panel: 4 Motion > Hoses and drag chains (task 0058). Same layout rules as ui.py."""

from __future__ import annotations

import bpy

from ..core.words import plural
from . import flex, ops_flex
from .ui import MEDIUM, _has_model, _Panel, big, big_row, fold, gap, header_status, list_rows, split_props, steps, wrap

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


def draw_kind(layout, context, item) -> None:
    """Kind · Colour · Size (task 0243, blender/kinds.py) of a hose, chain or cable, and what the size sets."""
    from . import kinds
    col = split_props(layout)
    if kinds.is_cable(item):
        cb = item
        col.prop(cb, "cable_kind", text="Kind")
        if kinds.kind_id(cb):
            col.prop(cb, "colour", text="Colour")
            col.prop(cb, "size", text="Size")
    else:
        fx = item
        if fx.kind == "CHAIN":
            if not kinds.can_size(fx):
                wrap(layout, context, "Its CAD links keep their own shape and size", icon="INFO")
                return
            col.prop(fx, "chain_kind", text="Type")
        else:
            col.prop(fx, "hose_kind", text="Kind")
        if kinds.kind_id(fx):
            col.prop(fx, "colour", text="Colour")
            col.prop(fx, "size", text="Size")
    if kinds.kind_id(item):
        wrap(layout, context, size_text(item), icon="BLANK1")


def size_text(item) -> str:
    """'Ø 22.6 mm, smallest bend 180 mm' / 'Width 64 mm, height 35 mm, link 35 mm, bend 75 mm' (custom too)."""
    from . import kinds
    if kinds.family(item) == "chain":
        return (f"Width {_mm(item.width)}, height {_mm(item.height)}, link {_mm(item.pitch)}, "
                f"bend {_mm(item.radius)}")
    bend = item.mbr if kinds.is_cable(item) else item.min_radius
    d = item.diameter * 1000.0
    return f"Ø {d:.1f} mm, smallest bend {_mm(bend)}" if d < 100 else f"Ø {d:.0f} mm, smallest bend {_mm(bend)}"


def _end_row(layout, context, item, end: str) -> None:
    """'End A on: <part>' with the small button that fixes the end to the selected part."""
    ob = item.a_part if end == "A" else item.b_part
    row = layout.row(align=True)
    name = ops_flex._name(ob) if ob is not None else "no part"
    wrap(row.column(), context, f"{ops_flex.end_word(item, end)} on: {name}", inset=40, alert=ob is None)
    row.operator("fresing.flex_set_end", text="", icon="EYEDROPPER").end = end


def route_text(item) -> str:
    """'Route: straight from end to end' / 'Route: through 2 clips and 1 via point' (task 0298)."""
    from . import flex_route
    vias = flex_route.count(item)
    clips = len(item.clips) - vias
    parts = ([plural(clips, "clip")] if clips else []) + ([plural(vias, "via point")] if vias else [])
    return "Route: " + (" and ".join(parts) if parts else "straight from end to end")


def _route_row(layout, context, item) -> None:
    """The route: what it runs through, Shape the route…, Clear (task 0298). Always drawn: the panel stays still."""
    from . import flex_route
    wrap(layout, context, route_text(item), icon="BLANK1")
    row = layout.row(align=True)
    row.operator("fresing.flex_route", text="Shape the route", icon="CURVE_PATH")
    sub = row.row(align=True)
    sub.enabled = flex_route.count(item) > 0
    sub.operator("fresing.flex_route_clear", text="", icon="X")


def _draw_buttons(layout) -> None:
    """Draw hose · Draw cable / Draw drag chain (task 0240): for what the CAD model does not have."""
    row = big_row(layout, MEDIUM)
    row.operator("fresing.flex_draw", text="Draw hose", icon="GREASEPENCIL").kind = "HOSE"
    row.operator("fresing.flex_draw", text="Draw cable", icon="GREASEPENCIL").kind = "CABLE"
    big(layout, "fresing.flex_draw", "Draw drag chain", "GREASEPENCIL").kind = "CHAIN"


def _replace_offer(layout, context) -> None:
    """A selected part named like a hose or chain (often simplified, task 0240): offer to draw one in its place."""
    scene = context.scene
    ob = context.view_layer.objects.active
    if ob is None or not ob.select_get() or ob.get("fr_kind") != "part" or ob.get("fr_drawn") or ob.get("fr_excluded"):
        return
    if ob.name in {o.name for o in flex.flex_parts(scene)}:
        return
    kind = flex._kind_by_name(ob)
    if not kind:
        return
    chain = kind != "HOSE"
    box = layout.box()
    wrap(box, context, f"'{ops_flex._name(ob)}' looks like a {'drag chain' if chain else 'hose'}. Draw one to "
         "replace it: the CAD part is hidden while the drawn one is there", icon="INFO")
    op = box.operator("fresing.flex_draw", text="Draw a drag chain to replace it" if chain else
                      "Draw a hose to replace it", icon="GREASEPENCIL")
    op.kind, op.replace = ("CHAIN" if chain else "HOSE"), ob.name
    gap(layout, size=0.5)


def _replaces_rows(layout, context, item, target: str) -> None:
    """A drawn item: the CAD part it replaces, with Replaces selected CAD part / Show it again (task 0240)."""
    from . import drawn
    names = drawn.replaced_names(item)
    if names:
        more = f" and {plural(len(names) - 1, 'more part')}" if len(names) > 1 else ""
        wrap(layout, context, f"Replaces: {names[0]}{more} (hidden for good)", icon="HIDE_ON")
    row = layout.row(align=True)
    row.operator("fresing.drawn_replace", text="Replaces selected CAD part", icon="UV_SYNC_SELECT").target = target
    if names:
        row.operator("fresing.drawn_unreplace", text="", icon="HIDE_OFF").target = target


def _add_buttons(layout, first: bool) -> None:
    """Draw … (task 0240) / Add hose · Add cable / Add drag chain / Find. ``first``: nothing added yet, so "Find and
    add all" is offered too. (All grey: the section's one blue button is Build & play.)"""
    _draw_buttons(layout)
    gap(layout, size=0.5)
    row = big_row(layout, MEDIUM)
    row.operator("fresing.flex_add_hose", text="Add hose", icon="ADD").soft = False
    row.operator("fresing.flex_add_hose", text="Add cable", icon="ADD").soft = True
    big(layout, "fresing.flex_add_chain", "Add drag chain", "ADD")
    gap(layout, size=0.5)
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
        text, alert = counts(context.scene)          # the long title leaves room for about 7 characters: the
        if not alert and text:                       # number alone ("3 chains" was cut off); a problem "1 of 5",
            text = text.split(" ")[0]                # red, without the icon
        header_status(self.layout, text or "none", alert=alert, limit=9)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        steps(layout, context, ["No hose in the CAD model? Press 'Draw hose', click the fitting at end A, any "
                                "clips, the fitting at end B, then Enter",
                                "A hose in the CAD model: click it in the 3D view (or press 'Find hoses and "
                                "chains'), then 'Add hose' or 'Add cable'",
                                "Move a joint: the hose follows, both ends stay on their parts",
                                "A drag chain: press 'Draw drag chain' and click its fixed bracket, then the "
                                "bracket on the part that moves – or, if the CAD model has one, click one of its "
                                "links (the app takes the whole row) and press 'Add drag chain'",
                                "Pick its Kind (or Type), Colour and Size under the list: the look and the numbers "
                                "follow"],
              key="fr_how_flex", used=bool(len(s.flex)))
        gap(layout)
        _replace_offer(layout, context)
        if not len(s.flex):
            _add_buttons(layout, first=True)
            return

        # -- the list
        row = layout.row()
        row.template_list("FRESING_UL_flex", "", s, "flex", s, "flex_index", rows=list_rows(len(s.flex), 2, 8))
        col = row.column(align=True)
        col.operator("fresing.flex_remove", text="", icon="REMOVE")
        col.operator("fresing.flex_select", text="", icon="RESTRICT_SELECT_OFF")
        gap(layout)
        _add_buttons(layout, first=False)

        # -- the chosen one
        fx = flex.active(scene)
        if fx is None:
            return
        gap(layout)
        chain = fx.kind == "CHAIN"
        wrap(layout, context, flex.label(fx) + ("  (drawn)" if fx.drawn else ""), icon=ICONS[fx.kind])
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

        gap(layout, size=0.5)
        draw_kind(layout, context, fx)                 # task 0243: kind, colour, size
        gap(layout, size=0.5)
        col = split_props(layout)
        if chain:
            col.prop(fx, "mode", text="Upper run")
            col.prop(fx, "radius", text="Bend radius")
            sub = col.row(align=True)
            sub.enabled = bool(fx.made_links)          # CAD links: as many as there are
            sub.prop(fx, "count", text="Links")
            if fx.drawn:
                col.prop(fx, "pitch", text="Link length")
        else:
            col.prop(fx, "stiffness", text="Stiffness")
            col.prop(fx, "sag", text="Sag")
            col.prop(fx, "min_radius", text="Smallest bend")
            col.prop(fx, "length", text="Length")
            cad = fx.cad_length
            if cad > 0.0 and abs(fx.length - cad) > DIFFERS * cad:
                layout.label(text=f"{'As drawn' if fx.drawn else 'In the CAD file'}: {cad * 1000.0:.1f} mm",
                             icon="BLANK1")
            col.prop(fx, "length_auto", text="Automatic length")
            col.prop(fx, "avoid", text="Avoid other parts")
            _route_row(layout, context, fx)

        gap(layout)
        _end_row(layout, context, fx, "A")
        _end_row(layout, context, fx, "B")
        if chain:
            row = layout.row(align=True)
            row.operator("fresing.flex_swap_ends", text="Swap ends", icon="ARROW_LEFTRIGHT")
            if fx.drawn:
                row.operator("fresing.flex_flip_bend", text="Flip bend", icon="MOD_MIRROR")
        if fx.drawn:
            layout.operator("fresing.flex_fit", text="Links for the travel" if chain else "Length as drawn",
                            icon="LOOP_BACK")
            gap(layout, size=0.5)
            _replaces_rows(layout, context, fx, "FLEX")
        else:
            layout.operator("fresing.flex_fit", text="Fit to the CAD pose", icon="LOOP_BACK")

        # -- rarely changed
        gap(layout)
        body = fold(layout, "fr_flex_more", "More", "PREFERENCES")
        if body:
            col = split_props(body)
            if chain:
                if not fx.drawn:
                    col.prop(fx, "pitch", text="Link length")
                if fx.made_links:
                    col.prop(fx, "width", text="Width")
                    col.prop(fx, "height", text="Height")
            else:
                col.prop(fx, "diameter", text="Diameter")


PANELS = (FRESING_PT_flex,)
CLASSES = (FRESING_UL_flex,) + PANELS
