"""Side panel, phase 2: 4 Motion, saved scenes, 6 Animation, 7 Render queue.

Same layout rules as ui.py: steps top to bottom, the main button big, details of the
selected list item right under the list, rarely used settings folded away.
"""

from __future__ import annotations

import bpy

from . import animation, build, cylinders, joints, linkages, queue
from ..core.words import plural
from .ui import (BIG, MEDIUM, _has_model, _Panel, big_row, fold, header_status, list_rows, primary, split_props,
                 steps, use_button, wrap)

# =============================================================================
# 4 Motion
# =============================================================================


def joint_icon(j) -> str:
    if joints.is_motor(j):
        return "FORCE_VORTEX"
    return "CON_ROTLIKE" if j.kind == "ROTATE" else "CON_LOCLIKE"


class FRESING_UL_joints(bpy.types.UIList):
    """Joints; a joint riding on another one is listed right under it, indented. A joint that follows
    another one shows its value greyed out (it cannot be moved by hand) after a link icon."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        d = joints.depth(context.scene, item)
        if d:
            row.separator(factor=1.2 * d)
        row.prop(item, "name", text="", emboss=False, icon=joint_icon(item))
        if item.follows:
            row.label(text="", icon="LINKED")
        sub = row.row(align=True)
        sub.ui_units_x = 4.2                   # room for "-1234 mm"; the name gets the rest of the row
        if item.motion is not None:
            sub.enabled = not item.follows
            sub.prop(item.motion, f'["{joints.VALUE}"]', text="")
        else:
            sub.label(text="(broken)", icon="ERROR")

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [self.bitflag_filter_item] * len(items)
        if self.filter_name:
            needle = self.filter_name.lower()
            flags = [f if needle in it.name.lower() else 0 for f, it in zip(flags, items)]
        order, _depths = joints.tree_order(context.scene)
        neworder = [0] * len(items)
        for pos, i in enumerate(order):
            if i < len(neworder):
                neworder[i] = pos
        return flags, neworder


def _names(objs, n: int = 2) -> str:
    names = [o.get(build.PROP_NAME, o.name) for o in objs]
    return ", ".join(names[:n]) + (f" +{len(names) - n}" if len(names) > n else "")


class FRESING_PT_motion(_Panel, bpy.types.Panel):
    bl_label = "4  Motion"
    bl_order = 3

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="CON_ROTLIKE")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.joints)
        header_status(self.layout, f"{n} joint{'s' if n != 1 else ''}" if n else "no joints")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        from .ops_motion import selected_movers
        if animation.has_keys(scene):
            box = layout.box()
            box.alert = True
            wrap(box, context, f"Animation '{s.anim_baked}' is built: the joints follow it.", icon="INFO", inset=12)
            box.operator("fresing.anim_clear", text="Stop it to move joints by hand", icon="CANCEL")

        # -- adding a joint: what moves, then the button, then a click on the pivot
        if not s.joints:
            steps(layout, context, ["Click what should move (subassembly or part)",
                                    "Add rotate joint or Add slide joint",
                                    "Click its pivot hole or shaft in the view"])
        movers = selected_movers(context)
        if movers:
            wrap(layout, context, f"Selected: {_names(movers)}", icon="RESTRICT_SELECT_OFF")
            below, reason = joints.stack_info(scene, movers)
            if reason:
                wrap(layout, context, reason, icon="ERROR", alert=True)
            elif below is not None:
                wrap(layout, context, f"Adds a joint on top of '{below.name}': the moves add up", icon="LINKED")
        else:
            wrap(layout, context, "Nothing selected: click what should move", icon="RESTRICT_SELECT_ON", alert=True)
        row = big_row(layout, MEDIUM)
        op = row.operator("fresing.joint_pick_axis", text="Add rotate joint", icon="CON_ROTLIKE")
        op.mode, op.kind = "NEW", "ROTATE"
        op = row.operator("fresing.joint_pick_axis", text="Add slide joint", icon="CON_LOCLIKE")
        op.mode, op.kind = "NEW", "SLIDE"

        if s.joints:
            _draw_joints(context, layout, s)
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = MEDIUM
        row.operator("fresing.pose_reset", text="Everything back to CAD position", icon="LOOP_BACK")


def _draw_joints(context, layout, s):
    layout.separator()
    row = layout.row()
    row.template_list("FRESING_UL_joints", "", s, "joints", s, "joints_index", rows=list_rows(len(s.joints), 2, 8))
    side = row.column(align=True)
    side.operator("fresing.joint_remove", text="", icon="REMOVE")
    layout.prop(s, "show_joints", text="Show joint arrows in the view")

    j = s.joints[s.joints_index] if 0 <= s.joints_index < len(s.joints) else None
    if j is not None and not joints.is_valid(j):
        box = layout.box()
        box.alert = True
        box.label(text="This joint is broken (its arrow was deleted)", icon="ERROR")
        box.operator("fresing.joint_remove", text="Remove it (parts go back to their place)")
    elif j is not None:
        scene = context.scene
        box = layout.box()
        box.label(text=j.name, icon=joint_icon(j))
        below = joints.rides_on(scene, j)
        if below is not None:
            # in a stack: the order matters for rotations, so it is shown with the swap right under it
            wrap(box, context, f"Rides on '{below.name}'", icon="LINKED", inset=12)
            sub = box.row(align=True)
            sub.enabled = not joints.swap_check(scene, j)      # the tooltip says why not
            sub.operator("fresing.joint_swap", text="Swap order", icon="UV_SYNC_SELECT")
        mech = linkages.drives(scene, j)
        if mech is not None:
            wrap(box, context, f"Drives mechanism '{mech.name}'", icon="LINKED", inset=12)
        lead = joints.leader(scene, j)
        row = box.row(align=True)
        row.scale_y = BIG
        row.enabled = not j.follows
        row.prop(j.motion, f'["{joints.VALUE}"]', text="Angle" if j.kind == "ROTATE" else "Distance")
        if joints.is_motor(j):
            box.label(text=f"= {joints.get_value(j) / joints.TURN:.2f} turns", icon="FORCE_VORTEX")
        if j.follows:
            if j.use_limits and joints.outside_limits(j, joints.get_value(j)):
                wrap(box, context, "Beyond its limits now: check the ratio, or the limits", icon="ERROR",
                     alert=True, inset=12)
        else:
            row = box.row(align=True)
            for t, label in (("ZERO", "CAD (0)"), ("MIN", "Min"), ("MAX", "Max")):
                sub = row.row(align=True)
                sub.enabled = t == "ZERO" or (j.use_limits and not joints.is_motor(j))
                sub.operator("fresing.joint_value", text=label).target = t
        if not joints.is_motor(j):
            row = box.row(align=True)
            row.prop(j, "use_limits", text="Limits")
            if j.use_limits:
                if j.kind == "ROTATE":
                    row.prop(j, "rot_min", text="")
                    row.prop(j, "rot_max", text="")
                else:
                    row.prop(j, "slide_min", text="")
                    row.prop(j, "slide_max", text="")
        if j.kind == "ROTATE":
            box.prop(j, "is_motor")
        _draw_coupling(context, box, s, j, lead)

        # a fold needs the full panel width, so it sits right under the box
        body = fold(layout, "fr_joint_setup", "Set-up: what moves, axis, type", icon="PREFERENCES")
        if body:
            mem = joints.moved_objects(context.scene, j)
            wrap(body, context, f"Moves: {_names(mem, 3) or 'nothing'}", icon="OBJECT_DATA")
            above = joints.riders(context.scene, j)
            if above:
                names = ", ".join("'" + r.name + "'" for r in above)
                wrap(body, context, f"Carries: {names}", icon="LINKED")
            row = body.row(align=True)
            row.operator("fresing.joint_members", text="Add", icon="ADD").action = "ADD"
            row.operator("fresing.joint_members", text="Remove", icon="REMOVE").action = "REMOVE"
            row.operator("fresing.joint_members", text="Select", icon="RESTRICT_SELECT_OFF").action = "SELECT"
            body.label(text="(Add / Remove use the selected parts)")
            row = body.row(align=True)
            row.label(text="Axis")
            op = row.operator("fresing.joint_pick_axis", text="", icon="EYEDROPPER")
            op.mode = "EDIT"
            row.operator("fresing.joint_flip", text="", icon="ARROW_LEFTRIGHT")
            for ax in ("X", "Y", "Z"):
                row.operator("fresing.joint_axis_preset", text=ax).axis = ax
            row = body.row(align=True)
            row.label(text="Type")
            for kind, label in (("ROTATE", "Rotate"), ("SLIDE", "Slide")):
                op = row.operator("fresing.joint_kind", text=label, depress=j.kind == kind)
                op.kind = kind
            if below is None:                         # a joint in a stack sits on the joint under it
                col = split_props(body)
                col.prop(j, "base", text="Sits on")


def _draw_coupling(context, box, s, j, lead) -> None:
    """How the joint moves: by itself, or following another joint at a ratio (task 0012)."""
    scene = context.scene
    box.separator(factor=0.5)
    row = box.row(align=True)
    row.operator("fresing.joint_follow", text="Moves by itself", depress=not j.follows).mode = "FREE"
    row.operator("fresing.joint_follow", text="Follows a joint", depress=bool(j.follows)).mode = "FOLLOW"
    if j.follows:
        col = split_props(box)
        col.prop_search(j, "follows", s, "joints", text="Joint", icon="LINKED")
        if lead is not None:
            # the unit is the label: "mm per turn" (of the joint picked right above)
            col.prop(j, "couple_ratio", text=joints.ratio_unit(lead.kind, j.kind))
            if j.kind == "ROTATE":
                col.prop(j, "couple_offset_angle", text="Offset")
            else:
                col.prop(j, "couple_offset_dist", text="Offset")
            hint = _ratio_hint(lead, j)
            if hint:
                wrap(box, context, hint, icon="INFO", inset=12)
        else:
            wrap(box, context, f"'{j.follows}' is not there any more: pick another joint, or By itself",
                 icon="ERROR", alert=True, inset=12)
    err = j.get("_follow_error", "")
    if err:
        wrap(box, context, err, icon="ERROR", alert=True, inset=12)
    driven = joints.followers(scene, j)
    if driven:
        names = ", ".join("'" + x.name + "'" for x in driven)
        wrap(box, context, f"Drives {names}", icon="LINKED", inset=12)


def _ratio_hint(lead, j) -> str:
    """The ratio in other words: what a rolling wheel or pinion of that size does."""
    r = j.couple_ratio
    if lead.kind == "SLIDE" and j.kind == "ROTATE" and abs(r) > 1e-9:
        per_turn = 360.0 / abs(r)                     # mm of travel for one turn
        return f"One turn every {per_turn:.1f} mm: a wheel of Ø{per_turn / 3.141592653589793:.1f} mm rolling along"
    if lead.kind == "ROTATE" and j.kind == "SLIDE" and abs(r) > 1e-9:
        return (f"{abs(r):g} mm for each turn: a screw with that pitch, or a pinion of "
                f"Ø{abs(r) / 3.141592653589793:.1f} mm on a rack")
    if lead.kind == j.kind and r < 0:
        return "Negative: it moves the other way (gears, gripper jaws)"
    return ""


# -----------------------------------------------------------------------------
# cylinders (task 0013)
# -----------------------------------------------------------------------------


def _mm(v: float) -> str:
    return f"{v * 1000.0:,.0f} mm"


class FRESING_UL_cylinders(bpy.types.UIList):
    """Cylinders, with how far each rod is out now."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False,
                 icon="CON_STRETCHTO" if item.mode == "DRIVE" else "CON_LOCKTRACK")
        sub = row.row()
        sub.alignment = "RIGHT"
        if cylinders.is_valid(item):
            stroke = cylinders.stroke_now(context.scene, item)
            sub.alert = cylinders.outside_stroke(item, stroke)
            sub.label(text=_mm(stroke))
        else:
            sub.label(text="(broken)", icon="ERROR")


class FRESING_PT_cylinders(_Panel, bpy.types.Panel):
    bl_label = "Cylinders"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="CON_STRETCHTO")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.cylinders)
        header_status(self.layout, plural(n, "cylinder") if n else "none")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not s.cylinders:
            steps(layout, context, ["Click the barrel (in the view or 2 Structure), press Barrel",
                                    "Click the rod, press Rod",
                                    "Add cylinder, then click the barrel's pin and the rod's pin"])
        for role, coll, text in (("BARREL", s.cyl_pick_barrel, "Barrel"), ("ROD", s.cyl_pick_rod, "Rod")):
            row = layout.row(align=True)
            sub = row.row(align=True)
            sub.ui_units_x = 3.6
            sub.operator("fresing.cylinder_pick_parts", text=text, icon="RESTRICT_SELECT_OFF").role = role
            picked = [r.obj for r in coll if r.obj is not None]
            row.label(text=_names(picked) if picked else "not picked yet", icon="CHECKMARK" if picked else "BLANK1")
        primary(layout, "fresing.cylinder_add", "Add cylinder (then click the 2 pins)", "CON_STRETCHTO", MEDIUM)

        if not s.cylinders:
            return
        layout.separator()
        row = layout.row()
        row.template_list("FRESING_UL_cylinders", "", s, "cylinders", s, "cylinders_index",
                          rows=list_rows(len(s.cylinders), 2, 6))
        row.column(align=True).operator("fresing.cylinder_remove", text="", icon="REMOVE")
        c = s.cylinders[s.cylinders_index] if 0 <= s.cylinders_index < len(s.cylinders) else None
        if c is None:
            return
        if not cylinders.is_valid(c):
            box = layout.box()
            box.alert = True
            box.label(text="This cylinder is broken (a marker was deleted)", icon="ERROR")
            box.operator("fresing.cylinder_remove", text="Remove it (parts go back to their place)")
            return
        _draw_cylinder(context, layout, scene, c)


def _draw_cylinder(context, layout, scene, cyl) -> None:
    box = layout.box()
    box.label(text=cyl.name, icon="CON_STRETCHTO")
    row = box.row(align=True)
    row.operator("fresing.cylinder_mode", text="Follows the arm", depress=cyl.mode == "FOLLOW").mode = "FOLLOW"
    row.operator("fresing.cylinder_mode", text="Drives the arm", depress=cyl.mode == "DRIVE").mode = "DRIVE"
    j, reason = cylinders.arm_joint(scene, cyl)
    stroke = cylinders.stroke_now(scene, cyl)
    if cyl.mode == "DRIVE" and j is not None:
        row = box.row(align=True)
        row.scale_y = BIG
        row.prop(cyl, "stroke", text="Stroke")
        row = box.row(align=True)
        for t, text in (("IN", "Fully in"), ("CAD", "CAD"), ("OUT", "Fully out")):
            row.operator("fresing.cylinder_stroke", text=text).target = t
        wrap(box, context, f"Turns '{j.name}' to match" if j.kind == "ROTATE" else f"Slides '{j.name}' to match",
             icon="LINKED", inset=12)
    else:
        wrap(box, context, f"Stroke now: {_mm(stroke)} (of {_mm(cyl.full_stroke)})", icon="CON_LOCKTRACK", inset=12)
        if cyl.mode == "DRIVE" or j is None:
            wrap(box, context, reason, icon="ERROR" if cyl.mode == "DRIVE" else "INFO", alert=cyl.mode == "DRIVE",
                 inset=12)
    if cylinders.outside_stroke(cyl, stroke):
        wrap(box, context, "The rod is out further than its stroke allows (or in further): check the arm's "
                           "limits, or the lengths below", icon="ERROR", alert=True, inset=12)
    col = split_props(box)
    col.prop(cyl, "closed_length", text="Closed length")
    col.prop(cyl, "full_stroke", text="Full stroke")
    row = box.row(align=True)
    row.operator("fresing.cylinder_estimate", text="From the model", icon="MOD_LENGTH")
    sub = row.row()
    sub.alignment = "RIGHT"
    sub.label(text="measured" if cyl.measured else "rough guess", icon="CHECKMARK" if cyl.measured else "QUESTION")
    wrap(box, context, f"Pin to pin now: {_mm(cylinders.length_now(cyl))}", inset=12)

    body = fold(layout, "fr_cylinder_setup", "Set-up: parts and pins", icon="PREFERENCES")
    if body:
        for action, text, objs in (("BARREL", "Barrel", cylinders.barrel_objs(cyl)),
                                   ("ROD", "Rod", cylinders.rod_objs(cyl)),
                                   ("STAGES", "Stages", cylinders.stage_objs(cyl))):
            row = body.row(align=True)
            sub = row.row(align=True)
            sub.ui_units_x = 3.6
            sub.operator("fresing.cylinder_parts", text=text, icon="RESTRICT_SELECT_OFF").action = action
            row.label(text=_names(objs) if objs else "none")
        if cyl.stages:
            body.operator("fresing.cylinder_parts", text="No stages", icon="X").action = "NO_STAGES"
        for action, text, ob in (("BARREL_PIN", "Barrel pin", cyl.frame.parent), ("ROD_PIN", "Rod pin", cyl.pin.parent)):
            row = body.row(align=True)
            sub = row.row(align=True)
            sub.ui_units_x = 3.6
            sub.operator("fresing.cylinder_parts", text=text, icon="RESTRICT_SELECT_OFF").action = action
            row.label(text=f"in {ob.get(build.PROP_NAME, ob.name)}" if ob is not None else "-")
        body.label(text="(these buttons use the selected parts)")
        row = body.row(align=True)
        row.operator("fresing.cylinder_pins", text="Pins again", icon="EYEDROPPER")
        row.operator("fresing.cylinder_parts", text="Select parts", icon="RESTRICT_SELECT_OFF").action = "SELECT"


# -----------------------------------------------------------------------------
# mechanisms (task 0014)
# -----------------------------------------------------------------------------

MECH_STEPS = {
    "SCISSOR": ["Click the base (the frame it stands on), press Base",
                "Select every arm and the platform (Ctrl+click in the view or in 2 Structure)",
                "Add mechanism: the pins and the rollers are found by themselves",
                "Set the height (or the drive angle) below"],
    "FOURBAR": ["Click the base (the part the two arms turn on), press Base",
                "Select the crank, the coupler and the rocker; click the one that drives last",
                "Add mechanism: the four pins are found by themselves"],
    "SLIDER": ["Click the base (with the crank's bearing and the guide), press Base",
               "Select the crank, the rod and the slider; click the crank last",
               "Add mechanism: the pins and the slide are found by themselves"],
    "OTHER": ["Click the base, press Base",
              "Select every moving link (each a subassembly); click the one that drives last",
              "Add mechanism: pins are found where two links share a hole or shaft"],
}


def _mech_icon(m) -> str:
    return {"SCISSOR": "SORT_DESC", "FOURBAR": "MOD_SIMPLEDEFORM", "SLIDER": "CON_LOCLIKE"}.get(m.kind, "LINKED")


class FRESING_UL_mechanisms(bpy.types.UIList):
    """Mechanisms, with the height of a scissor lift or the drive joint's value."""

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon=_mech_icon(item))
        sub = row.row()
        sub.alignment = "RIGHT"
        if not linkages.is_valid(item):
            sub.label(text="(broken)", icon="ERROR")
        elif item.status:
            sub.label(text="", icon="ERROR")
        elif linkages.has_height(item):
            sub.label(text=_mm(linkages.height_now(context.scene, item)))


class FRESING_PT_mechanisms(_Panel, bpy.types.Panel):
    bl_label = "Mechanisms"
    bl_parent_id = "FRESING_PT_motion"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="LINKED")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.mechanisms)
        header_status(self.layout, plural(n, "mechanism") if n else "none")

    def draw(self, context):
        from .ops_linkages import picked_links
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        layout.prop(s, "mech_kind", text="Type")
        if not s.mechanisms:
            steps(layout, context, MECH_STEPS.get(s.mech_kind, MECH_STEPS["OTHER"]))
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.ui_units_x = 3.6
        sub.operator("fresing.mechanism_pick_base", text="Base", icon="RESTRICT_SELECT_OFF")
        if s.mech_base is not None:
            row.label(text=linkages.label(s.mech_base), icon="CHECKMARK")
            row.operator("fresing.mechanism_pick_base", text="", icon="X").clear = True
        else:
            row.label(text="the rest of the subassembly", icon="BLANK1")
        links = picked_links(context)
        if links:
            wrap(layout, context, f"Links: {plural(len(links), 'subassembly')} selected ({_names(links)})",
                 icon="RESTRICT_SELECT_OFF")
        else:
            wrap(layout, context, "No links selected: select the moving parts", icon="RESTRICT_SELECT_ON")
        primary(layout, "fresing.mechanism_add", "Add mechanism", "LINKED", MEDIUM)

        if not s.mechanisms:
            return
        layout.separator()
        row = layout.row()
        row.template_list("FRESING_UL_mechanisms", "", s, "mechanisms", s, "mechanisms_index",
                          rows=list_rows(len(s.mechanisms), 2, 6))
        row.column(align=True).operator("fresing.mechanism_remove", text="", icon="REMOVE")
        mech = s.mechanisms[s.mechanisms_index] if 0 <= s.mechanisms_index < len(s.mechanisms) else None
        if mech is None:
            return
        if not linkages.is_valid(mech):
            box = layout.box()
            box.alert = True
            wrap(box, context, f"This mechanism is broken: {linkages.broken_reason(scene, mech)}", icon="ERROR")
            box.operator("fresing.mechanism_remove", text="Remove it (parts go back to their place)")
            return
        _draw_mechanism(context, layout, scene, mech)


def _draw_mechanism(context, layout, scene, mech) -> None:
    box = layout.box()
    box.label(text=f"{mech.name} ({linkages.kind_label(mech.kind)})", icon=_mech_icon(mech))
    j = linkages.input_joint(scene, mech)
    if linkages.has_height(mech):
        row = box.row(align=True)
        row.scale_y = BIG
        row.enabled = not j.follows
        row.prop(mech, "height", text="Height")
        row = box.row(align=True)
        row.enabled = not j.follows
        for t, text in (("LOW", "Lowest"), ("CAD", "CAD"), ("HIGH", "Highest")):
            row.operator("fresing.mechanism_height", text=text).target = t
        lo, hi = linkages.height_range(scene, mech)
        wrap(box, context, f"Height {_mm(lo)} … {_mm(hi)} (pin to pin, within the drive joint's limits)", inset=12)
    row = box.row(align=True)
    row.enabled = not j.follows
    row.prop(j.motion, f'["{joints.VALUE}"]', text="Drive angle" if j.kind == "ROTATE" else "Drive")
    row.operator("fresing.mechanism_drive_joint", text="", icon="CON_PIVOT")
    if j.follows:
        wrap(box, context, f"'{j.name}' follows '{j.follows}': move that one", icon="LINKED", inset=12)
    else:
        wrap(box, context, f"Moved by joint '{j.name}' (also in poses, animation steps, by a cylinder)",
             icon="CON_PIVOT", inset=12)
    if mech.status:
        wrap(box, context, mech.status, icon="ERROR", alert=True, inset=12)
    body = fold(layout, "fr_mechanism_setup", "Set-up: links and pins", icon="PREFERENCES")
    if body:
        d = linkages.setup(mech)
        wrap(body, context, f"{plural(len(mech.links) - 1, 'link')}, {plural(len(d.get('pins', [])), 'pin')}"
                            + (f", {plural(len(d['slots']), 'roller')}" if d.get("slots") else "")
                            + (f", {plural(len(d['slides']), 'slider')}" if d.get("slides") else ""),
             icon="INFO")
        for k, ln in enumerate(mech.links):
            if k == 0:
                wrap(body, context, f"Base: {linkages.label(mech.base) if mech.base else '-'}", icon="BLANK1")
                continue
            wrap(body, context, f"{k}. {ln.name}" + ("  (drive)" if ln.empty is None else ""), icon="BLANK1")
        body.operator("fresing.mechanism_select", text="Select parts", icon="RESTRICT_SELECT_OFF")


class FRESING_UL_poses(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="ARMATURE_DATA")
        use_button(row, "fresing.pose_apply", item.name)


class FRESING_PT_poses(_Panel, bpy.types.Panel):
    bl_label = "Poses & exploded views"
    bl_parent_id = "FRESING_PT_motion"

    def draw_header(self, context):
        self.layout.label(icon="ARMATURE_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "A pose keeps every joint position and moved part. + saves the model as it is now.")
        row = layout.row()
        row.template_list("FRESING_UL_poses", "", s, "poses", s, "poses_index", rows=list_rows(len(s.poses), 2, 6))
        col = row.column(align=True)
        col.operator("fresing.pose_save", text="", icon="ADD")
        col.operator("fresing.pose_remove", text="", icon="REMOVE")
        col.operator("fresing.pose_update", text="", icon="FILE_REFRESH")

        layout.separator()
        layout.label(text="Exploded view", icon="FULLSCREEN_EXIT")
        box = layout.box()
        from .ops_motion import _target_subassembly
        target = _target_subassembly(context)
        box.label(text=f"Explodes: {target.get(build.PROP_NAME, target.name) if target else '-'}",
                  icon="OUTLINER_OB_GROUP_INSTANCE")
        col = split_props(box)
        col.prop(s, "explode_level", text="Pieces")
        col.prop(s, "explode_direction", text="Direction")
        col.prop(s, "explode_factor", text="Distance")
        row = big_row(box, MEDIUM)
        row.operator("fresing.explode", text="Explode", icon="FULLSCREEN_EXIT")
        box.label(text="Keep it: + above saves it as a pose")


# =============================================================================
# saved scenes (under 5 Scene & Render)
# =============================================================================


class FRESING_UL_shots(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        active = context.scene.fresing.active_shot == item.name
        row.prop(item, "name", text="", emboss=False, icon="RADIOBUT_ON" if active else "RADIOBUT_OFF")
        use_button(row, "fresing.shot_apply", item.name)

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        flags = [0 if it.get("fr_queue_only") else self.bitflag_filter_item for it in items]
        if self.filter_name:
            needle = self.filter_name.lower()
            flags = [f if needle in it.name.lower() else 0 for f, it in zip(flags, items)]
        return flags, []


class FRESING_PT_shots(_Panel, bpy.types.Panel):
    bl_label = "Saved scenes"
    bl_parent_id = "FRESING_PT_scene"

    def draw_header(self, context):
        self.layout.label(icon="SCENE_DATA")

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        wrap(layout, context, "Colours, pose, visibility, camera and background under one name. "
                              "+ saves how it looks now.")
        n = sum(1 for sh in s.shots if not sh.get("fr_queue_only"))
        row = layout.row()
        row.template_list("FRESING_UL_shots", "", s, "shots", s, "shots_index", rows=list_rows(n, 2, 6))
        col = row.column(align=True)
        col.operator("fresing.shot_save", text="", icon="ADD")
        col.operator("fresing.shot_remove", text="", icon="REMOVE")
        col.operator("fresing.shot_update", text="", icon="FILE_REFRESH")
        if 0 <= s.shots_index < len(s.shots) and not s.shots[s.shots_index].get("fr_queue_only"):
            shot = s.shots[s.shots_index]
            box = layout.box()

            def what(v):
                return "as saved" if v == "__current__" else (v or "left as it is")

            col = split_props(box)
            col.prop(shot, "camera", text="Camera")
            info = box.column(align=True)
            info.label(text=f"Colours: {what(shot.scheme)}")
            info.label(text=f"Pose: {what(shot.pose)}")
            info.label(text=f"Visibility: {what(shot.visibility)}")
        row = big_row(layout, MEDIUM)
        op = row.operator("fresing.queue_add", text="Queue this", icon="ADD")
        op.kind = "SHOT"
        op = row.operator("fresing.queue_add", text="Queue all", icon="DOCUMENTS")
        op.kind = "ALL_SHOTS"


# =============================================================================
# 6 Animation
# =============================================================================

_KIND_ICON = {"JOINT": "CON_PIVOT", "POSE": "ARMATURE_DATA", "CAMERA": "VIEW_CAMERA", "SHOW": "HIDE_OFF",
              "HIDE": "HIDE_ON", "MOTOR": "FORCE_VORTEX", "CYLINDER": "CON_STRETCHTO", "MECHANISM": "SORT_DESC",
              "GCODE": "FILE_SCRIPT"}


def _follower_note(context, box, scene, j) -> bool:
    """A step cannot move a joint that follows another one: say which one to move instead."""
    if j is None or not j.follows:
        return False
    top = joints.driver_of(scene, j)
    who = f"'{top.name}'" if top is not None else "the joint it follows"
    wrap(box, context, f"'{j.name}' follows another joint and moves with it: pick {who} here instead",
         icon="ERROR", alert=True, inset=12)
    return True


class FRESING_UL_anims(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="RENDER_ANIMATION")
        sub = row.row()
        sub.alignment = "RIGHT"
        sub.label(text=f"{animation.length_seconds(item):.1f} s")


class FRESING_UL_blocks(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        if item.kind in ("JOINT", "MOTOR") and item.joint:
            j = context.scene.fresing.joints.get(item.joint)
            row.alert = j is not None and bool(j.follows)          # it would do nothing: the details say why
        row.prop(item, "enabled", text="")
        row.label(text=animation.block_label(item), icon=_KIND_ICON.get(item.kind, "DOT"))
        sub = row.row()
        sub.alignment = "RIGHT"
        if not animation.is_instant(item):
            sub.label(text=f"{item.start:.1f}–{item.start + item.duration:.1f} s")
        else:
            sub.label(text=f"at {item.start:.1f} s")


class FRESING_PT_animation(_Panel, bpy.types.Panel):
    bl_label = "6  Animation"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="RENDER_ANIMATION")

    def draw_header_preset(self, context):
        a = animation.active(context.scene)
        if a is not None:
            header_status(self.layout, f"{animation.length_seconds(a):.1f} s")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        if not s.animations:
            steps(layout, context, ["Make joints and poses in 4 Motion",
                                    "+ below adds an animation",
                                    "Add steps: joint moves, poses, camera, show/hide",
                                    "Build & play, then Render animation"])
        row = layout.row()
        row.template_list("FRESING_UL_anims", "", s, "animations", s, "animations_index",
                          rows=list_rows(len(s.animations), 1, 4))
        col = row.column(align=True)
        col.operator("fresing.anim_add", text="", icon="ADD")
        col.operator("fresing.anim_remove", text="", icon="REMOVE")
        a = animation.active(scene)
        if a is None:
            return
        col = split_props(layout)
        col.prop_search(a, "start_shot", s, "shots", text="Start from", icon="SCENE_DATA")
        col.prop(a, "fps", text="Frame rate")
        col.prop(a, "tail", text="Hold at end (s)")

        # -- steps and the selected step
        layout.label(text="Steps (overlapping steps play together)", icon="SEQ_STRIP_DUPLICATE")
        row = layout.row()
        row.template_list("FRESING_UL_blocks", "", a, "blocks", a, "blocks_index",
                          rows=list_rows(len(a.blocks), 3, 8))
        col = row.column(align=True)
        col.operator_menu_enum("fresing.block_add", "kind", text="", icon="ADD")
        col.operator("fresing.block_remove", text="", icon="REMOVE")
        col.separator()
        col.operator("fresing.block_move", text="", icon="TRIA_UP").direction = "UP"
        col.operator("fresing.block_move", text="", icon="TRIA_DOWN").direction = "DOWN"
        col.operator("fresing.block_duplicate", text="", icon="DUPLICATE")

        if 0 <= a.blocks_index < len(a.blocks):
            b = a.blocks[a.blocks_index]
            box = layout.box()
            box.label(text=animation.block_label(b), icon=_KIND_ICON.get(b.kind, "DOT"))
            col = split_props(box)
            if b.kind == "MOTOR":
                col.prop_search(b, "joint", s, "joints", text="Joint", icon="FORCE_VORTEX")
                j = s.joints.get(b.joint)
                if j is not None and not _follower_note(context, box, scene, j):
                    col = split_props(box)
                    sub = col.row(align=True)
                    sub.scale_y = MEDIUM
                    if j.kind == "ROTATE":
                        sub.prop(b, "speed_rpm", text="Speed (rpm)")
                        turns = animation.motor_total(j, b) / joints.TURN
                        text = f"{turns:.2f} turns in this step"
                        if not joints.is_motor(j) and abs(turns) > 0.5:
                            text += ". Tick 'Motor' on the joint in 4 Motion so it can turn without end"
                    else:
                        sub.prop(b, "speed_mms", text="Speed (mm/s)")
                        text = f"{animation.motor_total(j, b) * 1000.0:.0f} mm in this step"
                    wrap(box, context, text, icon="INFO", inset=12)
                    n = len(joints.all_followers(scene, j))
                    if n:
                        wrap(box, context, f"{n} joint{'s' if n != 1 else ''} follow{'s' if n == 1 else ''} it",
                             icon="LINKED", inset=12)
            elif b.kind == "JOINT":
                col.prop_search(b, "joint", s, "joints", text="Joint", icon="CON_PIVOT")
                j = s.joints.get(b.joint)
                if j is not None and not _follower_note(context, box, scene, j):
                    col.prop(b, "use_from", text="From where it is")
                    if j.kind == "ROTATE":
                        if not b.use_from:
                            col.prop(b, "from_angle", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_angle", text="To")
                    else:
                        if not b.use_from:
                            col.prop(b, "from_dist", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_dist", text="To")
                    if j.use_limits:
                        lo, hi = joints.limits(j)
                        box.label(text=f"Limits {joints.to_display(j.kind, lo):.0f} … "
                                       f"{joints.to_display(j.kind, hi):.0f} {joints.unit_label(j.kind)}")
            elif b.kind == "CYLINDER":
                col.prop_search(b, "cylinder", s, "cylinders", text="Cylinder", icon="CON_STRETCHTO")
                c = s.cylinders.get(b.cylinder)
                if c is not None:
                    j, reason = cylinders.arm_joint(scene, c)
                    if j is None:
                        wrap(box, context, reason, icon="ERROR", alert=True, inset=12)
                    else:
                        col = split_props(box)
                        col.prop(b, "use_from", text="From where it is")
                        if not b.use_from:
                            col.prop(b, "from_stroke", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_stroke", text="To")
                        box.label(text=f"Stroke 0 … {_mm(c.full_stroke)}; moves '{j.name}'")
            elif b.kind == "MECHANISM":
                col.prop_search(b, "mechanism", s, "mechanisms", text="Lift", icon="SORT_DESC")
                m = s.mechanisms.get(b.mechanism)
                if m is not None:
                    if not linkages.is_valid(m) or not linkages.has_height(m):
                        wrap(box, context, "Only a scissor lift has a height: pick one" if linkages.is_valid(m)
                             else "This mechanism is broken", icon="ERROR", alert=True, inset=12)
                    else:
                        col = split_props(box)
                        col.prop(b, "use_from", text="From where it is")
                        if not b.use_from:
                            col.prop(b, "from_height", text="From")
                        sub = col.row(align=True)
                        sub.scale_y = MEDIUM
                        sub.prop(b, "to_height", text="To")
                        lo, hi = linkages.height_range(scene, m)
                        box.label(text=f"Height {_mm(lo)} … {_mm(hi)}")
            elif b.kind == "GCODE":
                from .ui_gcode import draw_step
                draw_step(context, box, scene, a, b)
            elif b.kind == "POSE":
                col.prop_search(b, "pose", s, "poses", text="Pose", icon="ARMATURE_DATA")
            elif b.kind == "CAMERA":
                box.row(align=True).prop(b, "camera_mode", expand=True)
                col = split_props(box)
                if b.camera_mode == "ORBIT":
                    col.prop(b, "orbit_angle", text="Turn")
                else:
                    col.prop(b, "camera", text="To camera")
            else:
                row = box.row(align=True)
                row.label(text=b.target_name or "Nothing picked", icon="OBJECT_DATA")
                row.operator("fresing.block_target", text="Use selected", icon="EYEDROPPER")
            col = split_props(box)
            col.prop(b, "start", text="Start (s)")
            if b.kind == "GCODE":
                pass                                # its length follows from the program (shown above)
            elif b.kind not in ("SHOW", "HIDE") and not (b.kind == "CAMERA" and b.camera_mode == "CUT"):
                col.prop(b, "duration", text="Duration (s)")
                col.prop(b, "easing", text="Motion")
                if b.kind == "MOTOR" and b.easing != "LINEAR":
                    col.prop(b, "ramp", text="Ramp (s)")
            col.prop(b, "name", text="Label")

        # -- check it
        layout.separator()
        row = big_row(layout, MEDIUM)
        row.operator("fresing.anim_build", text="Build & play", icon="PLAY").play = True
        row.operator("fresing.anim_clear", text="", icon="CANCEL")
        if s.anim_baked:
            layout.label(text="Built · Space plays it again", icon="CHECKMARK")
        layout.operator("fresing.anim_fit_camera", text="Fit camera to the whole motion", icon="FULLSCREEN_ENTER")

        # -- the video
        layout.separator()
        layout.label(text="Video", icon="FILE_MOVIE")
        box = layout.box()
        col = split_props(box)
        col.prop(a, "out_resolution", text="Size")
        col.prop(a, "out_format", text="Shape")
        col.prop(a, "video", text="File")
        col.prop(a, "quality", text="Quality")
        secs = animation.length_seconds(a)
        frames = animation.frame_of(a, secs)
        box.label(text=f"{secs:.1f} s · {frames} frames", icon="TIME")
        test = queue.last_time_test(scene, a.name)
        if test is not None:
            if test.status == "DONE":
                wrap(box, context, test.message, icon="CHECKMARK", inset=12)
            elif test.status in ("WAITING", "RUNNING"):
                wrap(box, context, "Time test: " + (test.message or "waiting in the queue"), icon="SORTTIME",
                     inset=12)
        op = box.operator("fresing.queue_add", text="Time test (2 frames)", icon="SORTTIME")
        op.kind, op.name, op.start = "TEST", a.name, True
        op = primary(box, "fresing.queue_add", "Render animation", "RENDER_ANIMATION")
        op.kind, op.name, op.start = "ANIMATION", a.name, True


# =============================================================================
# 7 Render queue
# =============================================================================

_STATUS_ICON = {"WAITING": "TIME", "RUNNING": "RENDER_ANIMATION", "DONE": "CHECKMARK", "FAILED": "ERROR",
                "STOPPED": "CANCEL"}


class FRESING_UL_queue(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.alert = item.status == "FAILED"
        row.label(text=item.label, icon=_STATUS_ICON.get(item.status, "DOT"))
        sub = row.row()
        sub.alignment = "RIGHT"
        if item.status == "RUNNING":
            sub.label(text=f"{item.progress:.0f}%")
        else:
            sub.label(text=item.bl_rna.properties["status"].enum_items[item.status].name)


def _queue_status(scene) -> tuple[str, str, bool]:
    s = scene.fresing
    run = [j for j in s.queue if j.status == "RUNNING"]
    if run:
        return f"{run[0].progress:.0f}% done", "NONE", False
    wait = sum(1 for j in s.queue if j.status in ("WAITING", "STOPPED"))
    failed = sum(1 for j in s.queue if j.status == "FAILED")
    if failed:
        return f"{failed} failed", "NONE", True
    if wait:
        return f"{wait} waiting", "NONE", False
    if s.queue:
        return "all done", "NONE", False
    return "", "NONE", False


class FRESING_PT_queue(_Panel, bpy.types.Panel):
    bl_label = "7  Render queue"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def draw_header(self, context):
        self.layout.label(icon="SEQUENCE")

    def draw_header_preset(self, context):
        text, icon, alert = _queue_status(context.scene)
        if text:
            header_status(self.layout, text, icon=icon, alert=alert)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        s = scene.fresing
        running = queue.is_running(scene)
        row = layout.row(align=True)
        op = row.operator("fresing.queue_add", text="Current view", icon="ADD")
        op.kind = "STILL"
        op = row.operator("fresing.queue_add", text="All scenes", icon="DOCUMENTS")
        op.kind = "ALL_SHOTS"
        layout.label(text="Animations: Render animation in 6", icon="INFO")
        row = layout.row()
        row.template_list("FRESING_UL_queue", "", s, "queue", s, "queue_index", rows=list_rows(len(s.queue), 3, 8))
        col = row.column(align=True)
        col.operator("fresing.queue_remove", text="", icon="REMOVE")
        col.operator("fresing.queue_remove", text="", icon="BRUSH_DATA").finished = True
        if 0 <= s.queue_index < len(s.queue):
            job = s.queue[s.queue_index]
            box = layout.box()
            box.alert = job.status == "FAILED"
            box.label(text=job.label, icon=_STATUS_ICON.get(job.status, "DOT"))
            if job.status == "RUNNING":
                box.progress(factor=job.progress / 100.0, text=f"{job.progress:.0f}%")
            if job.message:
                wrap(box, context, job.message, inset=12)
            if job.output:
                row = box.row(align=True)
                row.scale_y = MEDIUM
                row.operator("fresing.queue_open", text="Open", icon="PLAY" if job.kind == "ANIMATION" else "IMAGE")
                row.operator("fresing.show_in_folder", text="Show in folder", icon="FILE_FOLDER").path = job.output
        layout.separator()
        if running:
            row = big_row(layout, MEDIUM)
            row.operator("fresing.queue_stop", text="Stop after this frame", icon="PAUSE")
            sub = row.row(align=True)
            sub.alert = True
            sub.operator("fresing.queue_stop", text="Stop now", icon="CANCEL").now = True
            layout.label(text="Keeps going if you close the app", icon="INFO")
        elif any(j.status in ("WAITING", "STOPPED", "FAILED") for j in s.queue):
            primary(layout, "fresing.queue_start", "Start queue", "PLAY")
        else:
            row = big_row(layout)
            row.operator("fresing.queue_start", text="Start queue", icon="PLAY")
        if s.queue_dir:
            layout.operator("fresing.queue_log", text="Open log (time per frame, errors)", icon="TEXT")


CLASSES = (
    FRESING_UL_joints, FRESING_UL_cylinders, FRESING_UL_poses, FRESING_UL_shots, FRESING_UL_anims, FRESING_UL_blocks,
    FRESING_UL_queue, FRESING_UL_mechanisms, FRESING_PT_motion, FRESING_PT_cylinders, FRESING_PT_mechanisms,
    FRESING_PT_poses, FRESING_PT_shots, FRESING_PT_animation, FRESING_PT_queue,
)
