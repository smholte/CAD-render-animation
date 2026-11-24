"""What lead motions look like (task 0309): the **Lead motions ▾** drop-down on the top bar, the same rows in the Keep
open window, the editor (Edit lead motions…, a function window) and the Lead motion step's settings in 6 Animation.

The drop-down is a popover on the top bar, right of the Fresing menu (``ui_topbar.py`` draws it with the menu). The top
bar is drawn in every workspace and in the Client view (lock.py draws Blender's menus there too), so it is one click away
everywhere – the place the task's mock-ups compared it with (the 3D view's header, a corner of the 3D view) is in the
report. One row per lead motion: its name (and "moved by …" when another lead motion or a hand moved its joints
since), a slider with the ends labelled (the joint's own values when it moves one joint), ▶ and + Add to animation.
"""

from __future__ import annotations

import bpy

from ..core import lead_motions as core
from ..core.words import plural
from . import lead_motions

UNITS_X = 20                         # the drop-down's width (UI units)


def _end_labels(scene, lm) -> tuple[str, str]:
    rows = lead_motions.to_core(lm).rows
    return core.end_labels(rows, lambda j, v: lead_motions.unit_text(scene, j, v))


def draw_menu(layout, context, in_window: bool = False) -> None:
    """The rows of the drop-down (and of the Keep open window)."""
    scene = context.scene
    s = scene.fresing
    col = layout.column()
    if not len(s.lead_motions):
        col.label(text="No lead motions yet: one slider per function of the machine.", icon="INFO")
        col.operator("fresing.lead_make_one", text="Make one…", icon="ADD")
        return
    for i, lm in enumerate(s.lead_motions):
        box = col.box() if not in_window else col.column()
        head = box.row(align=True)
        head.label(text=lm.name, icon="CON_ACTION")
        note = lead_motions.status(scene, lm)
        if not lead_motions.usable(scene, lm):
            note = "no joint it can move"
        if note:
            sub = head.row()
            sub.alignment = "RIGHT"
            sub.alert = note == "no joint it can move"
            sub.label(text=note)
        row = box.row(align=True)
        lo, hi = _end_labels(scene, lm)
        a = row.row()
        a.ui_units_x = 3
        a.alignment = "RIGHT"
        a.label(text=lo)
        row.prop(lm, "position", text="", slider=True)
        b = row.row()
        b.ui_units_x = 3
        b.label(text=hi)
        op = row.operator("fresing.lead_play", text="", icon="PLAY_REVERSE" if lm.position >= 99.95 else "PLAY")
        op.index = i
        op = row.operator("fresing.lead_add_step", text="", icon="ADD")
        op.index = i
    col.separator()
    row = col.row(align=True)
    row.operator("fresing.lead_back_to_start", text="Back to start", icon="LOOP_BACK")
    if not in_window:
        row.operator("fresing.lead_keep_open", text="Keep open", icon="WINDOW")
    row = col.row(align=True)
    row.operator("fresing.lead_show_all", text="Show every function", icon="SEQUENCE")
    row.operator("fresing.lead_edit", text="Edit lead motions…", icon="PREFERENCES")


class TOPBAR_PT_fresing_lead(bpy.types.Panel):
    """The Lead motions drop-down on the top bar"""

    bl_space_type = "TOPBAR"
    bl_region_type = "HEADER"
    bl_label = "Lead motions"
    bl_ui_units_x = UNITS_X

    def draw(self, context):
        DRAWN["menu"] += 1
        self.layout.label(text="Lead motions: one slider per function", icon="CON_ACTION")
        draw_menu(self.layout, context)


DRAWN = {"menu": 0, "button": 0}     # how often the drop-down and its button were drawn (tests)
HIDE = [False]                       # the real-app test finds the button by drawing the top bar without it once


def draw_button(layout, context) -> None:
    """The top bar's button (``ui_topbar`` calls it right after the Fresing menu)."""
    DRAWN["button"] += 1
    if HIDE[0]:
        return
    layout.popover(panel=TOPBAR_PT_fresing_lead.__name__, text="Lead motions", icon="CON_ACTION")


# ---------------------------------------------------------------------------
# the editor
# ---------------------------------------------------------------------------

class FRESING_UL_lead_motions(bpy.types.UIList):
    """The lead motions, in the order of the menu"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="CON_ACTION")
        n = len(item.rows)
        bad = sum(1 for r in item.rows if lead_motions.row_problem(context.scene, r))
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.alert = bad > 0
        sub.label(text=plural(n, "joint") + (f", {bad} left out" if bad else ""))


class FRESING_UL_lead_rows(bpy.types.UIList):
    """The joints of a lead motion: value at 0 % → at 100 %, and its part of the slider"""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        scene = context.scene
        row = layout.row(align=True)
        why = lead_motions.row_problem(scene, item)
        name = row.row()
        name.alert = bool(why)
        name.label(text=item.joint or "?", icon="ERROR" if why else "CON_PIVOT")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.alert = bool(why)
        if why:
            sub.label(text=why)
        else:
            a = lead_motions.unit_text(scene, item.joint, item.v0)
            b = lead_motions.unit_text(scene, item.joint, item.v1)
            sub.label(text=f"{a} → {b}   {item.start:.0f}–{item.end:.0f} %   stage {item.stage}")


def draw_editor(layout, context) -> None:
    from . import joints
    scene = context.scene
    s = scene.fresing
    col = layout.column()
    col.label(text="One slider per function: the Lead motions menu on the top bar lists them in this order.")
    row = col.row()
    row.template_list("FRESING_UL_lead_motions", "", s, "lead_motions", s, "lead_index", rows=4)
    side = row.column(align=True)
    side.operator("fresing.lead_new", text="", icon="ADD")
    side.operator("fresing.lead_remove", text="", icon="REMOVE")
    side.separator()
    side.operator("fresing.lead_move", text="", icon="TRIA_UP").direction = "UP"
    side.operator("fresing.lead_move", text="", icon="TRIA_DOWN").direction = "DOWN"
    lm = lead_motions.active(scene)
    if lm is None:
        col.label(text="Press + for a new lead motion.", icon="INFO")
        return
    box = col.box()
    box.prop(lm, "name", text="Name")
    box.prop(lm, "description", text="Description")
    r = box.row(align=True)
    r.prop(lm, "seconds", text="Seconds for ▶")
    r.prop(lm, "position", text="Now", slider=True)
    r.operator("fresing.lead_test", text="Test", icon="PLAY").index = s.lead_index

    # the three ways to give it its joints
    col.separator()
    col.label(text="Its joints – three ways:", icon="CON_PIVOT")
    box = col.box()
    box.label(text="From two poses (4 Motion > Poses): start = 0 %, end = 100 %")
    r = box.row(align=True)
    r.prop_search(s, "lead_pose_a", s, "poses", text="Start")
    r.prop_search(s, "lead_pose_b", s, "poses", text="End")
    box.operator("fresing.lead_from_poses", icon="ARMATURE_DATA")
    box = col.box()
    if lead_motions.recording(scene):
        box.label(text="Recording: move the joints to where the motion ends, then Set end", icon="REC")
    else:
        box.label(text="Record: machine where it starts → Set start, move the joints → Set end")
    r = box.row(align=True)
    r.operator("fresing.lead_record_start", icon="REC")
    r.operator("fresing.lead_record_end", icon="CHECKMARK")
    box = col.box()
    box.label(text="Pick a joint, then type its values below")
    r = box.row(align=True)
    r.prop_search(s, "lead_pick", s, "joints", text="", icon="CON_PIVOT")
    r.operator("fresing.lead_row_add", icon="ADD")

    # the rows
    col.separator()
    col.label(text=f"Joints of '{lm.name}' (joints that follow one of them move along):")
    row = col.row()
    row.template_list("FRESING_UL_lead_rows", "", lm, "rows", lm, "rows_index", rows=3)
    side = row.column(align=True)
    side.operator("fresing.lead_row_remove", text="", icon="REMOVE")
    side.separator()
    side.operator("fresing.lead_row_move", text="", icon="TRIA_UP").direction = "UP"
    side.operator("fresing.lead_row_move", text="", icon="TRIA_DOWN").direction = "DOWN"
    if 0 <= lm.rows_index < len(lm.rows):
        rr = lm.rows[lm.rows_index]
        box = col.box()
        box.prop_search(rr, "joint", s, "joints", text="Joint")
        why = lead_motions.row_problem(scene, rr)
        if why:
            w = box.row()
            w.alert = True
            w.label(text=f"This row is left out: {why}", icon="ERROR")
        j = joints.find(scene, rr.joint)
        suffix = "angle" if j is None or j.kind == "ROTATE" else "dist"
        r = box.row(align=True)
        r.prop(rr, f"v0_{suffix}", text="At 0 %")
        r.operator("fresing.lead_row_here", text="", icon="EYEDROPPER").end = "V0"
        r = box.row(align=True)
        r.prop(rr, f"v1_{suffix}", text="At 100 %")
        r.operator("fresing.lead_row_here", text="", icon="EYEDROPPER").end = "V1"
        r = box.row(align=True)
        r.prop(rr, "start", text="Starts at")
        r.prop(rr, "end", text="Ends at")
        r = box.row(align=True)
        r.prop(rr, "easing", text="")
        r.prop(rr, "stage", text="Stage")
    # stages
    col.separator()
    box = col.box()
    box.label(text="Order the joints: give each joint a stage (1 first, then 2 …)", icon="SORTTIME")
    r = box.row(align=True)
    r.prop(s, "lead_overlap", text="Overlap")
    r.operator("fresing.lead_stages", icon="SORTTIME")


# ---------------------------------------------------------------------------
# the step in 6 Animation
# ---------------------------------------------------------------------------

def draw_step(context, box, scene, a, b) -> None:
    from .ui import split_props, wrap
    s = scene.fresing
    if not len(s.lead_motions):
        wrap(box, context, "No lead motions yet: make them with Lead motions on the top bar (Edit lead motions…)",
             icon="INFO", inset=12)
        box.operator("fresing.lead_make_one", text="Make one…", icon="ADD")
        return
    col = split_props(box)
    col.prop_search(b, "lead", s, "lead_motions", text="Lead motion", icon="CON_ACTION")
    lm = s.lead_motions.get(b.lead)
    if lm is None:
        return
    col = split_props(box)
    col.prop(b, "lead_use_from", text="From where it is")
    if not b.lead_use_from:
        col.prop(b, "lead_from", text="From")
    col.prop(b, "lead_to", text="To")
    names = [r.joint for r in lm.rows if not lead_motions.row_problem(scene, r)]
    bad = [r.joint or "?" for r in lm.rows if lead_motions.row_problem(scene, r)]
    if names:
        wrap(box, context, "Moves " + ", ".join(dict.fromkeys(names)), icon="CON_PIVOT", inset=12)
    if bad:
        wrap(box, context, "Left out (missing or following another joint): " + ", ".join(bad), icon="ERROR",
             alert=True, inset=12)
    others = _same_joint_steps(a, b, set(names))
    if others:
        wrap(box, context, f"'{others[0]}' moves the same joints at the same time: the later-starting step takes "
             "over from its start", icon="ERROR", alert=True, inset=12)


def _same_joint_steps(anim, b, names: set) -> list:
    """Labels of other steps that move one of these joints while ``b`` runs."""
    from . import animation
    out = []
    t0, t1 = b.start, b.start + b.duration
    scene = anim.id_data
    for x in anim.blocks:
        if x == b or not x.enabled or animation.block_end(x) <= t0 or x.start >= t1:
            continue
        moved = set()
        if x.kind in ("JOINT", "MOTOR"):
            moved = {x.joint}
        elif x.kind == "LEAD":
            lm = scene.fresing.lead_motions.get(x.lead)
            moved = {r.joint for r in lm.rows} if lm is not None else set()
        if moved & names:
            out.append(animation.block_label(x))
    return out


CLASSES = (TOPBAR_PT_fresing_lead, FRESING_UL_lead_motions, FRESING_UL_lead_rows)
