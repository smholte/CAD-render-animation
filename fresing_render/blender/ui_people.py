"""Side panel: 6 Animation > People (task 0157). Same layout rules as ui.py: steps top to bottom, the main button
big, the selected item's details under its list, a state in the header."""

from __future__ import annotations

import bpy

from ..core import people as core
from ..core.words import plural
from . import people
from .ui import _Panel, big, gap, header_status, list_rows, split_props, steps, wrap

_ICONS = {"WALK": "TRACKING", "STOP": "PAUSE", "TURN": "LOOP_BACK", "PICK_UP": "TRIA_UP", "PUT_DOWN": "TRIA_DOWN",
          "WAVE": "HAND", "GREET": "COMMUNITY", "TALK": "OUTLINER_DATA_SPEAKER", "POINT": "FORWARD",
          "LOOK": "HIDE_OFF", "IDLE": "TIME", "OPERATE": "TOOL_SETTINGS"}
_LABEL = {i: n for i, n, _d in core.ACTION_ITEMS}
_GAIT = {i: n for i, n, _d in core.GAIT_ITEMS}


def action_text(a) -> str:
    """One line for a step in the list: 'Walk to point 2 (Brisk)', 'Greet Ben', 'Talk with Ben, 6 s'."""
    where = {"POINT": f" at point {a.point}", "END": " at the path's end"}.get(a.place, "")
    if a.kind == "WALK":
        to = f"to point {a.point}" if a.place == "POINT" else ("to the end" if a.place == "END" else "on")
        return f"Walk {to} ({_GAIT.get(a.gait, a.gait).lower()})"
    other = a.other.name if a.other is not None else "…"
    if a.kind == "GREET":
        text = f"Greet {other}"
    elif a.kind == "TALK":
        text = f"Talk with {other}"
    elif a.kind == "PICK_UP":
        text = f"Pick up {a.item.name if a.item is not None else '…'}"
    elif a.kind in ("TURN", "LOOK", "POINT"):
        what = {"PART": a.target_object.name if a.target_object is not None else "…",
                "PERSON": other, "POINT": "a point" if a.target_set else "…"}[a.target_kind]
        text = f"{_LABEL[a.kind]} {what}"
    else:
        text = _LABEL.get(a.kind, a.kind)
    if a.kind in core.HAS_DURATION:
        secs = a.duration if a.duration > 0 else core.DEFAULT_DURATION.get(a.kind, 1.0)
        text += f", {secs:.0f} s"
    if a.wait_person is not None:
        text = f"(after {a.wait_person.name} {a.wait_step}) " + text
    return text + where


class FRESING_UL_person_actions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text=f"{index + 1}. {action_text(item)}", icon=_ICONS.get(item.kind, "DOT"))


class FRESING_PT_people(_Panel, bpy.types.Panel):
    bl_label = "People"
    bl_parent_id = "FRESING_PT_animation"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="COMMUNITY")

    def draw_header_preset(self, context):
        header_status(self.layout, people.words(context.scene) or "none", limit=22)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        everyone = people.people(scene)
        steps(layout, context, ["Add a person: click on the floor where it stands",
                                "Draw its path: click the points it walks through",
                                "Add its steps: walk, stop, carry, greet, talk …",
                                "Press Build & play above"],
              key="fr_how_people", used=bool(everyone))
        gap(layout)
        big(layout, "fresing.person_add", "Add person", "ADD")
        layout.operator("fresing.people_example", icon="COMMUNITY")
        if not everyone:
            return
        gap(layout)
        active = context.view_layer.objects.active
        col = layout.column(align=True)
        for ob in everyone:
            n = len(ob.fresing_person.actions)
            row = col.row(align=True)
            op = row.operator("fresing.person_select", text=f"{ob.name}  ·  {plural(n, 'step')}",
                              icon="USER", depress=(ob == active))
            op.name = ob.name
        if not people.is_person(active):
            wrap(layout, context, "Click a person above (or in the view) for its path and steps.", icon="INFO")
            gap(layout)
            self._items(layout, context)
            return
        self._person(layout, context, active)
        gap(layout)
        self._items(layout, context)
        gap(layout)
        self._preview(layout, context)

    def _person(self, layout, context, ob):
        person = ob.fresing_person
        box = layout.box()
        row = box.row(align=True)
        row.prop(ob, "name", text="", icon="USER")
        row.operator("fresing.person_remove", text="", icon="TRASH")
        col = split_props(box)
        col.prop(person, "height_choice")
        col.prop(person, "outfit")
        row = box.row(align=True)
        row.prop(person, "helmet", toggle=True)
        row.prop(person, "gloves", toggle=True)
        row.prop(person, "look")
        col = split_props(box)
        col.prop(person, "carry")
        col.prop(person, "start")
        # the path
        gap(box)
        box.label(text="Path", icon="CURVE_PATH")
        pts = people.path_points(ob)
        if context.mode == "EDIT_CURVE":
            big(box, "fresing.person_path_edit", "Done editing", "CHECKMARK")
        elif not pts:
            big(box, "fresing.person_path_draw", "Draw path", "GREASEPENCIL")
        else:
            wrap(box, context, f"{plural(len(pts), 'point')} (numbers in the view; 0 = where the person starts)")
            row = box.row(align=True)
            row.operator("fresing.person_path_draw", text="Add points", icon="GREASEPENCIL")
            row.operator("fresing.person_path_edit", text="Edit points", icon="EDITMODE_HLT")
            row.operator("fresing.person_path_clear", text="", icon="TRASH")
        # the steps
        gap(box)
        box.label(text="Steps (top to bottom)", icon="SEQUENCE")
        row = box.row()
        row.template_list("FRESING_UL_person_actions", "", person, "actions", person, "actions_index",
                          rows=list_rows(len(person.actions), 3, 8))
        side = row.column(align=True)
        side.operator_menu_enum("fresing.person_action_add", "kind", text="", icon="ADD")
        side.operator("fresing.person_action_remove", text="", icon="REMOVE")
        side.separator()
        side.operator("fresing.person_action_move", text="", icon="TRIA_UP").direction = -1
        side.operator("fresing.person_action_move", text="", icon="TRIA_DOWN").direction = 1
        if 0 <= person.actions_index < len(person.actions):
            self._action(box, context, person.actions[person.actions_index])

    def _action(self, layout, context, act):
        sub = layout.box()
        col = split_props(sub)
        col.prop(act, "kind")
        if act.kind == "WALK":
            col.prop(act, "place", text="To")
        else:
            col.prop(act, "place")
        if act.place == "POINT":
            col.prop(act, "point")
        if act.kind == "WALK" or act.place != "HERE":
            col.prop(act, "gait")
        if act.kind in core.NEEDS_OTHER:
            col.prop(act, "other")
        if act.kind in ("TURN", "LOOK", "POINT"):
            col.prop(act, "target_kind")
            if act.target_kind == "PART":
                col.prop(act, "target_object")
            elif act.target_kind == "PERSON":
                col.prop(act, "other", text="Person")
        if act.kind == "OPERATE" or (act.kind in ("TURN", "LOOK", "POINT") and act.target_kind == "POINT"):
            sub.operator("fresing.person_pick_point", icon="EYEDROPPER",
                         text="Pick point again" if act.target_set else "Pick point")
        if act.kind == "PICK_UP":
            col.prop(act, "item")
        if act.kind in core.HAS_DURATION:
            col.prop(act, "duration")
        col = split_props(sub)
        col.prop(act, "wait_person")
        if act.wait_person is not None:
            col.prop(act, "wait_step")

    def _items(self, layout, context):
        its = people.items(context.scene)
        row = layout.row(align=True)
        row.operator_menu_enum("fresing.person_item_add", "kind", text="Add item", icon="PACKAGE")
        if its:
            row.label(text=plural(len(its), "item"))

    def _preview(self, layout, context):
        scene = context.scene
        if scene.fresing.anim_baked:
            wrap(layout, context, "Built: play the animation to see the people. Clear keys to change them.",
                 icon="INFO")
            return
        pl = people.plan(scene, flat=True)
        if pl.people:
            layout.prop(scene.fresing, "people_preview", slider=True,
                        text=f"Preview ({pl.length:.1f} s)")
        for w in pl.warnings[:4]:
            wrap(layout, context, w, icon="ERROR", alert=True)


CLASSES = (FRESING_UL_person_actions, FRESING_PT_people)
