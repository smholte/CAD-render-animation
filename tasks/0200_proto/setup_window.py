"""Task 0200 prototype (never merged): a step-by-step set-up window for "Set up a CNC mill" and "Set up a mechanism".

One drawing function (``draw_wizard``) is shown by four hosts, so the study can compare them on the same content:
  * POPOVER  - ``wm.call_panel(name="FRESING_PT_setup_pop", keep_open=True)``: floats over the 3D view
  * TAB      - a sidebar tab "Set-up" next to "Fresing" (``FRESING_PT_setup_tab``)
  * WINDOW   - a second app window: the 3D view area copied (``screen.area_dupli``), its sidebar on the "Set-up" tab
  * DIALOG   - ``invoke_props_dialog`` (measured only: it blocks the 3D view)

Load it into the running app with ``--python tasks/0200_proto/setup_window.py`` (after the extension is on). The
buttons are the app's own operators and settings (4 Motion > CNC machine, 4 Motion > Mechanisms): nothing is copied.
"""
import sys

import bpy


def _pkg():
    for name in sys.modules:
        if name.endswith("fresing_render") and name + ".blender" in sys.modules:
            return name
    raise RuntimeError("Fresing Render is not on")


def _m(name):
    import importlib
    return importlib.import_module(_pkg() + "." + name)


def say(layout, text, icon="NONE", alert=False, width=34):
    """Text on as many lines as it needs, for a host of fixed width (ui.wrap measures the side panel)."""
    import textwrap
    col = layout.column(align=True)
    col.alert = alert
    for i, line in enumerate(textwrap.wrap(text, width) or [""]):
        col.label(text=line, icon=icon if i == 0 else ("BLANK1" if icon != "NONE" else "NONE"))


# ---------------------------------------------------------------------------------------------------------------
# the steps
# ---------------------------------------------------------------------------------------------------------------

def _cnc_axes(layout, context):
    ui = _m("blender.ui")
    s = context.scene.fresing
    cnc = _m("blender.gcode").settings(context.scene)
    say(layout, "Make slide joints for X, Y and Z first (4 Motion > Add joint). Then let the app "
                             "find which is which, or pick them.", icon="INFO")
    ui.primary(layout, "fresing.cnc_find_axes", "Find the axes", "VIEWZOOM", ui.MEDIUM)
    box = layout.box()
    for ax in "xyz":
        row = box.row(align=True)
        row.prop_search(cnc, f"{ax}_joint", s, "joints", text=ax.upper(), icon="CON_LOCLIKE")
        row.prop(cnc, f"{ax}_reverse", text="", icon="ARROW_LEFTRIGHT", toggle=True)


def _cnc_spindle(layout, context):
    ui = _m("blender.ui")
    s = context.scene.fresing
    cnc = _m("blender.gcode").settings(context.scene)
    say(layout, "The spindle is a rotate joint with Motor ticked (4 Motion). Pick it here.",
            icon="INFO")
    layout.prop_search(cnc, "spindle_joint", s, "joints", text="Spindle", icon="FORCE_VORTEX")


def _cnc_parts(layout, context):
    ui = _m("blender.ui")
    gcode = _m("blender.gcode")
    cnc = gcode.settings(context.scene)
    ob = context.active_object if context.active_object and context.active_object.select_get() else None
    say(layout, f"Clicked: {gcode.label(ob)}" if ob else "Click a part in the view (this window "
            "stays open)", icon="RESTRICT_SELECT_OFF" if ob else "RESTRICT_SELECT_ON")
    for op, prop, text in (("fresing.cnc_use_tool", "tool", "Tool"), ("fresing.cnc_use_workpiece", "workpiece",
                                                                      "Workpiece")):
        row = layout.row(align=True)
        sub = row.row(align=True)
        sub.ui_units_x = 5.4
        sub.operator(op, text=text, icon="RESTRICT_SELECT_OFF")
        val = getattr(cnc, prop)
        row.label(text=gcode.label(val) if val else "not picked yet", icon="CHECKMARK" if val else "BLANK1")


def _cnc_zero(layout, context):
    ui = _m("blender.ui")
    cnc = _m("blender.gcode").settings(context.scene)
    col = ui.split_props(layout)
    col.prop(cnc, "zero_mode", text="Work zero")
    if cnc.zero_mode == "POINT":
        layout.operator("fresing.cnc_zero_click", text="Click the zero point", icon="EYEDROPPER")
    why = _m("blender.gcode").problem(context.scene)
    say(layout, why or "Machine ready", icon="ERROR" if why else "CHECKMARK", alert=bool(why))


def _cnc_program(layout, context):
    ui = _m("blender.ui")
    say(layout, "Adds the step 'Run G-code program' to the animation; pick the program file in "
                             "6 Animation.", icon="INFO")
    op = ui.primary(layout, "fresing.block_add", "Add 'Run G-code program'", "FILE_SCRIPT", ui.MEDIUM)
    op.kind = "GCODE"


def _mech_kind(layout, context):
    ui = _m("blender.ui")
    s = context.scene.fresing
    layout.prop(s, "mech_kind", text="Type")
    lines = _m("blender.ui_motion").MECH_STEPS.get(s.mech_kind, [])
    if lines:
        say(layout, "Then: " + lines[0], icon="INFO")


def _mech_base(layout, context):
    ui = _m("blender.ui")
    s = context.scene.fresing
    linkages = _m("blender.linkages")
    say(layout, "Click the base in the view (the frame it stands on), then press Base.",
            icon="INFO")
    row = layout.row(align=True)
    sub = row.row(align=True)
    sub.ui_units_x = 3.6
    sub.operator("fresing.mechanism_pick_base", text="Base", icon="RESTRICT_SELECT_OFF")
    row.label(text=linkages.label(s.mech_base) if s.mech_base else "not picked yet",
              icon="CHECKMARK" if s.mech_base else "BLANK1")


def _mech_links(layout, context):
    ui = _m("blender.ui")
    from importlib import import_module
    picked = import_module(_pkg() + ".blender.ops_linkages").picked_links(context)
    say(layout, "Ctrl+click every moving link in the view; click the one that drives last.",
            icon="INFO")
    words = _m("core.words")
    say(layout, f"Selected: {words.plural(len(picked), 'subassembly')}" if picked else
            "Nothing selected yet", icon="RESTRICT_SELECT_OFF" if picked else "RESTRICT_SELECT_ON")


def _mech_add(layout, context):
    ui = _m("blender.ui")
    s = context.scene.fresing
    ui.primary(layout, "fresing.mechanism_add", "Add mechanism", "LINKED", ui.MEDIUM)
    if s.mechanisms:
        m = s.mechanisms[min(s.mechanisms_index, len(s.mechanisms) - 1)]
        say(layout, f"Made: {m.name}. Move it in 4 Motion > Mechanisms.", icon="CHECKMARK")


WIZARDS = {
    "CNC": ("Set up a CNC mill", [("Axes X, Y, Z", _cnc_axes), ("Spindle", _cnc_spindle),
                                  ("Tool and workpiece", _cnc_parts), ("Work zero", _cnc_zero),
                                  ("G-code program", _cnc_program)]),
    "MECH": ("Set up a mechanism", [("Type", _mech_kind), ("Base", _mech_base), ("Moving links", _mech_links),
                                    ("Add it", _mech_add)]),
}


def draw_wizard(layout, context):
    wm = context.window_manager
    title, steps = WIZARDS[wm.fr_wiz_kind]
    k = max(0, min(wm.fr_wiz_step, len(steps) - 1))
    head = layout.row(align=True)
    head.prop(wm, "fr_wiz_kind", text="")
    dots = layout.row(align=True)
    for i, (name, _fn) in enumerate(steps):
        op = dots.operator("fresing.wiz_go", text=str(i + 1), depress=(i == k))
        op.step = i
    box = layout.box()
    box.label(text=f"Step {k + 1} of {len(steps)}: {steps[k][0]}", icon="PREFERENCES")
    steps[k][1](box, context)
    row = layout.row(align=True)
    row.scale_y = 1.3
    sub = row.row(align=True)
    sub.enabled = k > 0
    sub.operator("fresing.wiz_go", text="Back", icon="TRIA_LEFT").step = k - 1
    sub = row.row(align=True)
    sub.enabled = k < len(steps) - 1
    sub.operator("fresing.wiz_go", text="Next", icon="TRIA_RIGHT").step = k + 1


class FRESING_OT_wiz_go(bpy.types.Operator):
    """Goes to this step of the set-up"""
    bl_idname = "fresing.wiz_go"
    bl_label = "Go to step"
    step: bpy.props.IntProperty()

    def execute(self, context):
        context.window_manager.fr_wiz_step = self.step
        for win in context.window_manager.windows:
            for a in win.screen.areas:
                a.tag_redraw()
        return {"FINISHED"}


class FRESING_PT_setup_pop(bpy.types.Panel):
    """Popover host (wm.call_panel, keep_open)."""
    bl_label = "Set-up"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 16

    def draw(self, context):
        draw_wizard(self.layout, context)


class FRESING_PT_setup_tab(bpy.types.Panel):
    """Sidebar host: its own tab 'Set-up' (also what the second window shows)."""
    bl_label = "Set-up"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Set-up"

    def draw(self, context):
        draw_wizard(self.layout, context)


class FRESING_PT_setup_tools(bpy.types.Panel):
    """Left toolbar host (region TOOLS) - measured: Blender 5.2 does not draw add-on panels there."""
    bl_label = "Set-up"
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"

    def draw(self, context):
        draw_wizard(self.layout, context)


class FRESING_OT_setup_dialog(bpy.types.Operator):
    """Dialog host (invoke_props_dialog)"""
    bl_idname = "fresing.setup_dialog"
    bl_label = "Set-up"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420, title="Set up", confirm_text="Close")

    def draw(self, context):
        draw_wizard(self.layout, context)

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_setup_popup(bpy.types.Operator):
    """Popup host (invoke_popup)"""
    bl_idname = "fresing.setup_popup"
    bl_label = "Set-up"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=420)

    def draw(self, context):
        draw_wizard(self.layout, context)

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_setup_window(bpy.types.Operator):
    """Opens the set-up in a window of its own: drag it anywhere, also onto a second screen"""
    bl_idname = "fresing.setup_window"
    bl_label = "Set-up window"

    width: bpy.props.IntProperty(default=380)
    height: bpy.props.IntProperty(default=560)

    def execute(self, context):
        """A narrow area is split off the 3D view, copied into a window of its own (it gets the area's size and
        place) and closed again in the main window. The new window's sidebar shows the 'Set-up' tab."""
        wm = context.window_manager
        win = context.window
        area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
        before_areas = set(win.screen.areas[:])
        with context.temp_override(window=win, area=area):
            bpy.ops.screen.area_split(direction="VERTICAL", factor=1.0 - self.width / max(area.width, 1))
        small = next(a for a in win.screen.areas if a not in before_areas and a.type == "VIEW_3D")
        if small.width > area.width:
            small = area
        height = self.height

        def split2():                      # and a short one: its top part (only once the first split has a size)
            before2 = set(win.screen.areas[:])
            with bpy.context.temp_override(window=win, area=small):
                bpy.ops.screen.area_split(direction="HORIZONTAL", factor=1.0 - height / max(small.height, 1))
            top = next(a for a in win.screen.areas if a not in before2)
            if top.y < small.y:
                top, rest = small, top
            else:
                rest = small
            _SPLIT[:] = [rest]
            bpy.app.timers.register(lambda: _to_window(wm, win, top), first_interval=0.1)
            return None
        bpy.app.timers.register(split2, first_interval=0.1)
        return {"FINISHED"}


_SPLIT = []


def _to_window(wm, win, small):
        before = set(wm.windows[:])
        with bpy.context.temp_override(window=win, area=small):
            bpy.ops.screen.area_dupli("INVOKE_DEFAULT")
        for a in [small] + _SPLIT:
            with bpy.context.temp_override(window=win, area=a):
                bpy.ops.screen.area_close()
        new = [w for w in wm.windows if w not in before]
        if not new:
            print("[0200] no window opened")
            return None
        a = new[0].screen.areas[0]
        sp = a.spaces.active
        sp.show_region_ui = True
        sp.show_region_toolbar = False
        sp.show_region_header = False
        sp.show_region_tool_header = False
        sp.overlay.show_overlays = False
        sp.show_gizmo = False

        tries = [0]

        def later():                       # the tab can only be set once the sidebar has drawn its tabs
            tries[0] += 1
            if tries[0] > 25:
                return None
            try:
                for r in a.regions:
                    if r.type == "UI":
                        r.active_panel_category = "Set-up"
                a.tag_redraw()
            except Exception as exc:
                print("[0200] tab", exc)
                return 0.2
            return None
        bpy.app.timers.register(later, first_interval=0.2)
        return None


CLASSES = (FRESING_OT_wiz_go, FRESING_PT_setup_pop, FRESING_PT_setup_tab, FRESING_PT_setup_tools,
           FRESING_OT_setup_dialog, FRESING_OT_setup_popup, FRESING_OT_setup_window)


def register():
    bpy.types.WindowManager.fr_wiz_kind = bpy.props.EnumProperty(
        name="Set-up", items=[(k, v[0], "") for k, v in WIZARDS.items()],
        update=lambda self, ctx: setattr(self, "fr_wiz_step", 0))
    bpy.types.WindowManager.fr_wiz_step = bpy.props.IntProperty(min=0)
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except RuntimeError as exc:                     # measured: the TOOLS host is refused
            print("[0200] not registered:", c.__name__, exc)


if __name__ == "__main__":
    register()
