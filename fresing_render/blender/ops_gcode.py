"""Operators of 4 Motion > CNC machine and the "Run G-code program" step (task 0026)."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, IntProperty

from ..core.words import plural
from . import animation, build, gcode
from .ops_machining import clicked_part


class _CncOp:
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene is not None and hasattr(context.scene, "fresing")


def _step(context):
    """The selected step of the active animation, when it is a G-code step."""
    a = animation.active(context.scene)
    if a is None or not 0 <= a.blocks_index < len(a.blocks):
        return None
    b = a.blocks[a.blocks_index]
    return b if b.kind == "GCODE" else None


class FRESING_OT_cnc_find_axes(_CncOp, bpy.types.Operator):
    """Picks the X, Y and Z joints (the slide joints that point along the model's X, Y and Z) and the
    spindle (a motor joint) by themselves. Check them below and change one if it is wrong"""

    bl_idname = "fresing.cnc_find_axes"
    bl_label = "Find the axes"

    def execute(self, context):
        done = gcode.find_axes(context.scene)
        if not done:
            self.report({"WARNING"}, "No slide joints along X, Y or Z: make them in 4 Motion first")
            return {"CANCELLED"}
        self.report({"INFO"}, "Found: " + ", ".join(done))
        return {"FINISHED"}


class FRESING_OT_cnc_use_tool(_CncOp, bpy.types.Operator):
    """Makes the part you clicked last the tool in the spindle: its tip is the point the program steers.
    Click the cutter itself, not its holder"""

    bl_idname = "fresing.cnc_use_tool"
    bl_label = "Tool"

    def execute(self, context):
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the tool in the spindle in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        if ob is gcode.settings(context.scene).workpiece:
            self.report({"WARNING"}, f"'{gcode.label(ob)}' is the workpiece")
            return {"CANCELLED"}
        try:
            gcode.use_tool(context.scene, ob)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Tool in the spindle: {gcode.label(ob)}")
        return {"FINISHED"}


class FRESING_OT_cnc_use_workpiece(_CncOp, bpy.types.Operator):
    """Makes the part you clicked last the workpiece: the program's zero (work zero) sits on it and
    moves with it"""

    bl_idname = "fresing.cnc_use_workpiece"
    bl_label = "Workpiece"

    def execute(self, context):
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the workpiece in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        if ob is gcode.settings(context.scene).tool:
            self.report({"WARNING"}, f"'{gcode.label(ob)}' is the tool")
            return {"CANCELLED"}
        gcode.use_workpiece(context.scene, ob)
        self.report({"INFO"}, f"Workpiece: {gcode.label(ob)}")
        return {"FINISHED"}


class FRESING_OT_cnc_zero_click(_CncOp, bpy.types.Operator):
    """Click the point on the workpiece that is the program's zero, as in the CAM set-up. A click near a
    corner snaps onto it. Esc cancels"""

    bl_idname = "fresing.cnc_zero_click"
    bl_label = "Click the zero point"

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        context.workspace.status_text_set("Click the program's zero on the workpiece (a corner snaps).  "
                                          "Esc / right-click: cancel.  Middle mouse / scroll: move the view")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from .ops_motion import _raycast, over_panel
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = _raycast(context, event)
        c = gcode.settings(context.scene)
        if res is None or res[0].get(build.PROP_KIND) != "part" or res[0] is c.tool:
            context.workspace.status_text_set("Missed the workpiece: click on it. Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        gcode.set_zero_point(context.scene, ob, loc)
        self.report({"INFO"}, f"Work zero on '{gcode.label(ob)}'")
        return {"FINISHED"}


class FRESING_OT_cnc_home(_CncOp, bpy.types.Operator):
    """Machine zero (G53 X0 Y0 Z0, where G28 goes): the X, Y and Z joints as they are now. Move them to the
    machine's home position first (usually Z right up). Off: the CAD position"""

    bl_idname = "fresing.cnc_home"
    bl_label = "Machine zero here"

    clear: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.clear:
            return "Machine zero (G53 X0 Y0 Z0) back at the CAD position: every axis joint at 0"
        return cls.__doc__.replace("\n", " ")

    def execute(self, context):
        gcode.set_home_here(context.scene, not self.clear)
        return {"FINISHED"}


class FRESING_OT_cnc_tool_add(_CncOp, bpy.types.Operator):
    """Adds a tool to the list: its T number, and the part of the model it is (a tool in the
    carousel), or its sizes for a simple tool shape"""

    bl_idname = "fresing.cnc_tool_add"
    bl_label = "Add tool"

    def execute(self, context):
        c = gcode.settings(context.scene)
        used = {t.number for t in c.tools}
        n = 1
        while n in used:
            n += 1
        t = c.tools.add()
        t["_busy"] = True
        t.number = n
        t.source = "typed"
        del t["_busy"]
        c.tools_index = len(c.tools) - 1
        return {"FINISHED"}


class FRESING_OT_cnc_tool_remove(_CncOp, bpy.types.Operator):
    """Takes the selected tool out of the list (the part itself stays)"""

    bl_idname = "fresing.cnc_tool_remove"
    bl_label = "Remove tool"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and len(gcode.settings(context.scene).tools) > 0

    def execute(self, context):
        c = gcode.settings(context.scene)
        if 0 <= c.tools_index < len(c.tools):
            c.tools.remove(c.tools_index)
            c.tools_index = max(0, min(c.tools_index, len(c.tools) - 1))
        return {"FINISHED"}


class FRESING_OT_cnc_tool_part(_CncOp, bpy.types.Operator):
    """Makes the part you clicked last this tool (for example the tool standing in the carousel). At a
    tool change it disappears from there and shows in the spindle"""

    bl_idname = "fresing.cnc_tool_part"
    bl_label = "Use clicked part"

    clear: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.clear:
            return "This tool has no part of the model: a simple shape is drawn from its sizes"
        return cls.__doc__.replace("\n", " ")

    @classmethod
    def poll(cls, context):
        c = gcode.settings(context.scene) if super().poll(context) else None
        return c is not None and 0 <= c.tools_index < len(c.tools)

    def execute(self, context):
        c = gcode.settings(context.scene)
        t = c.tools[c.tools_index]
        if self.clear:
            t.obj, t.uid = None, ""
            return {"FINISHED"}
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the tool's part in the view first")
            return {"CANCELLED"}
        try:
            gcode.tool_frame(ob)
        except RuntimeError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        t.obj = ob
        t.uid = ob.get(build.PROP_UID, "")
        self.report({"INFO"}, f"T{t.number}: {gcode.label(ob)}")
        return {"FINISHED"}


class FRESING_OT_cnc_tools_from_program(_CncOp, bpy.types.Operator):
    """Adds every tool the selected step's program uses to the tool list, with the sizes from the
    program's tool comments (Fusion writes them) or the tool table"""

    bl_idname = "fresing.cnc_tools_from_program"
    bl_label = "Tools from the program"

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _program_step(context) is not None

    def execute(self, context):
        b = _program_step(context)
        try:
            n = gcode.tools_from_program(context.scene, b)
        except FileNotFoundError as exc:
            self.report({"WARNING"}, f"File not found: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{plural(n, 'tool')} added" if n else "Every tool of the program is in the list")
        return {"FINISHED"}


def _program_step(context):
    """The selected G-code step, else the first G-code step of the active animation (with a file)."""
    b = _step(context)
    if b is not None and b.gcode_file:
        return b
    a = animation.active(context.scene)
    if a is None:
        return None
    return next((x for x in a.blocks if x.kind == "GCODE" and x.gcode_file), None)


class FRESING_OT_gcode_toolpath(_CncOp, bpy.types.Operator):
    """Draws the toolpath of this animation's G-code steps on the workpiece now (Build & play draws it
    too). Cutting moves orange (green once cut), rapids dashed blue"""

    bl_idname = "fresing.gcode_toolpath"
    bl_label = "Show toolpath"

    remove: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.remove:
            return "Takes the toolpath line out of the view (Build & play draws it again when Show toolpath is on)"
        return cls.__doc__.replace("\n", " ")

    def execute(self, context):
        if self.remove:
            gcode.remove_path()
            return {"FINISHED"}
        try:
            ob = gcode.show_path(context.scene)
        except gcode.SetupError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}
        except FileNotFoundError as exc:
            self.report({"WARNING"}, f"File not found: {exc}")
            return {"CANCELLED"}
        if ob is None:
            self.report({"WARNING"}, "No G-code step with 'Show toolpath' and a program in this animation")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_gcode_report(_CncOp, bpy.types.Operator):
    """Lists everything about the selected step's program: what the app does not show (with line
    numbers), the notes, the tools"""

    bl_idname = "fresing.gcode_report"
    bl_label = "Program details"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _step(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=560)

    def draw(self, context):
        b = _step(context)
        info = gcode.info(context.scene, b) if b is not None else {}
        col = self.layout.column(align=True)
        if info.get("error"):
            col.label(text=info["error"], icon="ERROR")
            return
        col.label(text=f"{animation.block_label(b)}: {plural(info.get('lines', 0), 'line')}, "
                       f"{plural(info.get('moves', 0), 'move')}, {gcode.fmt_time(info.get('machine_s', 0))} "
                       "on the machine", icon="FILE_SCRIPT")
        col.separator()
        probs = info.get("problems", [])
        col.label(text="Not shown:" if probs else "Everything in the program is shown",
                  icon="ERROR" if probs else "CHECKMARK")
        for p in probs[:20]:
            col.label(text="   " + p)
        if len(probs) > 20:
            col.label(text=f"   … and {len(probs) - 20} more")
        if info.get("air"):
            col.separator()
            c = gcode.settings(context.scene)
            col.label(text=f"{info['air']} (air codes M{c.air_on_code} / M{c.air_off_code}"
                           f"{', always while the spindle turns' if c.air_always else ''})", icon="FORCE_WIND")
        notes = info.get("notes", [])
        if notes:
            col.separator()
            col.label(text="Notes:", icon="INFO")
            for n in notes[:10]:
                col.label(text="   " + n)
        tools = info.get("tool_info", {})
        if tools:
            col.separator()
            col.label(text="Tools:", icon="TOOL_SETTINGS")
            for n in sorted(tools):
                col.label(text=f"   T{n}: {tools[n]}")

    def execute(self, context):
        return {"FINISHED"}


class FRESING_OT_gcode_reload(_CncOp, bpy.types.Operator):
    """Reads the program file again (after you changed it in the CAM or an editor): the step's length
    and the toolpath follow"""

    bl_idname = "fresing.gcode_reload"
    bl_label = "Read again"

    @classmethod
    def poll(cls, context):
        b = _step(context) if super().poll(context) else None
        return b is not None and bool(b.gcode_file)

    def execute(self, context):
        gcode._CACHE.clear()
        gcode._INFO.clear()
        b = _step(context)
        gcode.step_changed(context.scene, b)
        info = gcode.info(context.scene, b)
        if info.get("error"):
            self.report({"WARNING"}, info["error"])
            return {"CANCELLED"}
        self.report({"INFO"}, f"{plural(info.get('lines', 0), 'line')} read, {gcode.fmt_time(info.get('video_s', 0))} "
                              "in the video")
        return {"FINISHED"}


class FRESING_OT_gcode_go_line(_CncOp, bpy.types.Operator):
    """Puts the timeline at the moment the program reaches a line (Build & play first)"""

    bl_idname = "fresing.gcode_go_line"
    bl_label = "Go to line"

    line: IntProperty(name="Line", default=1, min=1)

    @classmethod
    def poll(cls, context):
        return super().poll(context) and _step(context) is not None and bool(context.scene.fresing.anim_baked)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=260)

    def execute(self, context):
        scene = context.scene
        b = _step(context)
        f = gcode.frame_of_line(scene, animation.active(scene), b, self.line)
        if f is None:
            self.report({"WARNING"}, f"Line {self.line} has no move in this step")
            return {"CANCELLED"}
        scene.frame_set(int(f), subframe=f - int(f))
        return {"FINISHED"}


class FRESING_OT_cnc_air_nozzle(_CncOp, bpy.types.Operator):
    """Makes the part you clicked last the air nozzle: the air comes out of the end of it nearest the
    workpiece and blows along it. It moves with the part (on the head or the frame). Check the aim below"""

    bl_idname = "fresing.cnc_air_nozzle"
    bl_label = "Use clicked part"

    clear: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.clear:
            return "Forgets the nozzle part: the air comes through the spindle again"
        return " ".join(cls.__doc__.split())

    def execute(self, context):
        from . import air
        c = gcode.settings(context.scene)
        if self.clear:
            c["_busy"] = True
            c.air_nozzle = None
            c.air_nozzle_uid = ""
            del c["_busy"]
            c.air_source = "SPINDLE"
            return {"FINISHED"}
        ob = clicked_part(context)
        if ob is None:
            self.report({"WARNING"}, "Click the nozzle in the view first (a part, not a subassembly)")
            return {"CANCELLED"}
        if ob is c.workpiece or ob is c.tool:
            self.report({"WARNING"}, f"'{gcode.label(ob)}' is the {'workpiece' if ob is c.workpiece else 'tool'}: "
                                     "click the nozzle")
            return {"CANCELLED"}
        note = air.use_nozzle(context.scene, ob)
        self.report({"INFO"}, f"Air nozzle: {gcode.label(ob)} ({note})")
        return {"FINISHED"}


class FRESING_OT_cnc_air_click(_CncOp, bpy.types.Operator):
    """Click the spot on a part where the air comes out: that part becomes the nozzle and blows from there
    towards the workpiece. Esc cancels"""

    bl_idname = "fresing.cnc_air_click"
    bl_label = "Click the nozzle point"

    def invoke(self, context, event):
        if context.area is None or context.area.type != "VIEW_3D":
            self.report({"WARNING"}, "Use this from the 3D view")
            return {"CANCELLED"}
        context.window.cursor_modal_set("EYEDROPPER")
        context.workspace.status_text_set("Click the spot where the air comes out.  Esc / right-click: cancel.  "
                                          "Middle mouse / scroll: move the view")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from . import air
        from .ops_motion import _raycast, over_panel
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = _raycast(context, event)
        c = gcode.settings(context.scene)
        if res is None or res[0].get(build.PROP_KIND) != "part" or res[0] is c.workpiece:
            context.workspace.status_text_set("Missed: click on the nozzle (not the workpiece). Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, _index, loc, _normal = res
        self._end(context)
        air.use_nozzle(context.scene, ob, loc)
        self.report({"INFO"}, f"Air nozzle: {gcode.label(ob)}, blowing at the workpiece")
        return {"FINISHED"}


class FRESING_OT_cnc_air_aim(_CncOp, bpy.types.Operator):
    """Aims the nozzle at the middle of the workpiece"""

    bl_idname = "fresing.cnc_air_aim"
    bl_label = "Aim at the workpiece"

    flip: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if properties.flip:
            return "Turns the nozzle round: it blows the other way (when it was read from the wrong end)"
        return cls.__doc__

    @classmethod
    def poll(cls, context):
        return super().poll(context) and gcode.settings(context.scene).air_nozzle is not None

    def execute(self, context):
        from . import air
        if self.flip:
            air.flip(context.scene)
            return {"FINISHED"}
        if not air.aim_at_workpiece(context.scene):
            self.report({"WARNING"}, "Pick the workpiece first (Workpiece above, or in 4 Motion > Milling)")
            return {"CANCELLED"}
        return {"FINISHED"}


CLASSES = (FRESING_OT_cnc_air_nozzle, FRESING_OT_cnc_air_click, FRESING_OT_cnc_air_aim, FRESING_OT_cnc_find_axes, FRESING_OT_cnc_use_tool, FRESING_OT_cnc_use_workpiece, FRESING_OT_cnc_zero_click,
           FRESING_OT_cnc_home, FRESING_OT_cnc_tool_add, FRESING_OT_cnc_tool_remove, FRESING_OT_cnc_tool_part,
           FRESING_OT_cnc_tools_from_program, FRESING_OT_gcode_toolpath, FRESING_OT_gcode_report,
           FRESING_OT_gcode_reload, FRESING_OT_gcode_go_line)
