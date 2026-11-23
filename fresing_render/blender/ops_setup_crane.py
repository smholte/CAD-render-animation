"""The buttons of Set up a crane (task 0203): the Set-up window's crane steps (``setup_crane.py`` draws them).

Each button does one thing with the app's own functions – a joint (``joints.create``), a chain of sections that share a
stroke (``joints.set_follows``), a cylinder (``cylinders.create``), a track (``tracks.add``), the hook block's joints –
so what it makes shows in 4 Motion as if made there. Tests and the tour press them by name ("EXEC_DEFAULT")."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Vector

from . import joints, setup_crane as SC

ROLE_ITEMS = [(k, w, "") for k, w in SC.ROLE_WORDS.items()]


def _redraw():
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        for area in win.screen.areas:
            area.tag_redraw()


def _has_model(context) -> bool:
    return SC.model_root(context.scene) is not None


def _say(context, text: str) -> None:
    SC.settings(context.scene).message = text


class FRESING_OT_crane_setup(bpy.types.Operator):
    """Opens the Set-up window on Set up a crane: make your own crane's STEP a lifting-plan crane step by step –
    its joints, hook, masses and load chart – and save it to your library"""

    bl_idname = "fresing.crane_setup"
    bl_label = "Set up a crane"
    bl_options = set()

    kind: EnumProperty(
        name="Kind", default="CRANE_MOBILE",
        items=[("CRANE_MOBILE", "Mobile telescopic crane", "A telescopic crane on wheels with outriggers"),
               ("CRANE_CRAWLER", "Crawler crane", "A lattice-boom crane on tracks, with or without a luffing jib"),
               ("CRANE_KNUCKLE", "Knuckle-boom crane", "A truck-mounted knuckle-boom crane with stabilisers"),
               ("CRANE_OTHER", "Other crane", "Any other crane: you give each joint its role")],
        description="The kind of crane: each has its own steps")

    def execute(self, context):
        from . import ops_setup
        ops_setup.set_kind(context.scene, self.kind)
        SC.forget()
        SC.keep_root(context.scene)
        if bpy.app.background:
            return {"FINISHED"}
        return bpy.ops.fresing.setup_window(kind=self.kind)


class FRESING_OT_crane_pick(bpy.types.Operator):
    """Picks parts or sub-assemblies for this step: by name (from the list), or those clicked in the main window"""

    bl_idname = "fresing.crane_pick"
    bl_label = "Pick parts"
    bl_options = {"REGISTER", "UNDO"}

    names: StringProperty(name="Names", default="", options={"SKIP_SAVE"},
                          description="Part or sub-assembly names, separated by |")
    add: BoolProperty(default=False, options={"SKIP_SAVE"}, description="Add to what is picked (else replace)")
    use_clicked: BoolProperty(default=False, options={"SKIP_SAVE"},
                              description="Take the parts clicked (selected) in the main window")
    clear: BoolProperty(default=False, options={"SKIP_SAVE"}, description="Pick nothing")

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, "clear", False):
            return "Clears the parts picked for this step"
        if getattr(properties, "use_clicked", False):
            return ("Takes the parts or sub-assemblies you clicked in the main window (Ctrl+click for more) for this "
                    "step")
        return "Adds this part or sub-assembly to the parts of this step"

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        cs = SC.settings(context.scene)
        if self.clear:
            cs.pick = ""
            return {"FINISHED"}
        if self.use_clicked:
            got = [SC.name_of(o) for o in SC.clicked(context)]
            if not got:
                self.report({"WARNING"}, "Nothing of the crane is clicked in the main window")
                return {"CANCELLED"}
            names = got
        else:
            names = SC.split_names(self.names)
        have = SC.split_names(cs.pick) if self.add else []
        for n in names:
            if n not in have:
                have.append(n)
        cs.pick = SC.SEP.join(have)
        cs.search = ""
        _objs, bad = SC.objects_of(context.scene, cs.pick)
        if bad:
            self.report({"WARNING"}, "; ".join(bad))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_axes(bpy.types.Operator):
    """Lists the axes the picked parts offer: their round faces (holes, pins, slewing rings) and directions"""

    bl_idname = "fresing.crane_axes"
    bl_label = "Find the axes"
    bl_options = {"REGISTER"}

    role: EnumProperty(items=ROLE_ITEMS, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _has_model(context) and bool(SC.settings(context.scene).pick)

    def execute(self, context):
        n = SC.find_axes(context.scene, self.role)
        self.report({"INFO"}, f"{n} axes found")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_axis_use(bpy.types.Operator):
    """Uses this axis for the joint: a round face's axis (through its centre) or the direction named"""

    bl_idname = "fresing.crane_axis_use"
    bl_label = "Use this axis"
    bl_options = {"INTERNAL"}

    index: IntProperty(default=0, options={"SKIP_SAVE"})

    def execute(self, context):
        cs = SC.settings(context.scene)
        if not 0 <= self.index < len(cs.axes):
            return {"CANCELLED"}
        cs.axis_index = self.index
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_make(bpy.types.Operator):
    """Makes the joint for this role from the picked parts and the axis chosen above. It shows in 4 Motion > Joints
    too; its limits are set below"""

    bl_idname = "fresing.crane_make"
    bl_label = "Make the joint"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(items=ROLE_ITEMS, options={"SKIP_SAVE"})
    chain: BoolProperty(default=False, options={"SKIP_SAVE"},
                        description="One joint per picked section, each riding on the one before, sharing the stroke")

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick)
        if bad or not objs:
            self.report({"WARNING"}, "; ".join(bad) or "Pick the parts first")
            return {"CANCELLED"}
        ax = SC.chosen_axis(scene)
        if ax is None:
            self.report({"WARNING"}, "Find the axes and pick one first")
            return {"CANCELLED"}
        o, d, _a = ax
        try:
            if self.chain:
                lead = None
                made = SC.make_chain(scene, self.role, objs, o, d, cs.stroke, lead=lead)
                text = ", ".join(j.name for j in made)
            else:
                j = SC.make_joint(scene, self.role, objs, o, d, stroke=cs.stroke)
                text = j.name
                SC.after_make(scene, self.role, j)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.pick = ""
        cs.axes.clear()
        cs.axes_for = ""
        _say(context, f"Made: {text}")
        self.report({"INFO"}, f"Made: {text}")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_make_click(bpy.types.Operator):
    """Makes the joint for this role from the picked parts: click its axis on the model in the main window – a hole
    or pin (axis through its centre) or a flat face (axis at right angles to it). Esc cancels"""

    bl_idname = "fresing.crane_make_click"
    bl_label = "Click the axis"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(items=ROLE_ITEMS, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _has_model(context) and bool(SC.settings(context.scene).pick)

    def invoke(self, context, event):
        from . import hover, ops_setup
        if ops_setup.is_setup_window(context.window) or context.area is None or context.area.type != "VIEW_3D":
            win, area, region = ops_setup.main_view(context)
            if area is None:
                self.report({"WARNING"}, "This needs a 3D view in the main window")
                return {"CANCELLED"}
            with context.temp_override(window=win, screen=win.screen, area=area, region=region):
                bpy.ops.fresing.crane_make_click("INVOKE_DEFAULT", role=self.role)
            return {"FINISHED"}
        context.window.cursor_modal_set("EYEDROPPER")
        hover.start(context, self, "Click the axis: a hole or pin (through its centre) or a flat face (at right "
                                   "angles to it).  Esc / right-click: cancel")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        from . import hover
        hover.end(self, context)
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        from . import hover
        from .ops_motion import over_panel
        hover.on_event(self, context, event)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            self._end(context)
            return {"CANCELLED"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS" or over_panel(context, event):
            return {"PASS_THROUGH"}
        res = hover.pick(context, event)
        if res is None:
            hover.prompt(context, "Missed the model: click a part. Esc: cancel")
            return {"RUNNING_MODAL"}
        ob, index, loc, normal = res
        origin, direction, desc = joints.axis_from_hit(ob, index, loc, normal)
        self._end(context)
        scene = context.scene
        objs, _bad = SC.objects_of(scene, SC.settings(scene).pick)
        try:
            j = SC.make_joint(scene, self.role, objs, origin, direction, stroke=SC.settings(scene).stroke, ref=ob)
            SC.after_make(scene, self.role, j)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        SC.settings(scene).pick = ""
        _say(context, f"Made: {j.name} on a {desc}")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_flip(bpy.types.Operator):
    """Turns the joint's axis round: + then moves the other way"""

    bl_idname = "fresing.crane_flip"
    bl_label = "Flip"
    bl_options = {"REGISTER", "UNDO"}

    joint: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        j = joints.find(context.scene, self.joint)
        if j is None:
            return {"CANCELLED"}
        joints.flip(context.scene, j)
        SC.changed(context.scene)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_remove(bpy.types.Operator):
    """Removes this joint (and the ones that follow it, when it drives sections or corners). Its parts go back to
    their CAD place"""

    bl_idname = "fresing.crane_remove"
    bl_label = "Remove"
    bl_options = {"REGISTER", "UNDO"}

    joint: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        scene = context.scene
        j = joints.find(scene, self.joint)
        if j is None:
            return {"CANCELLED"}
        names = [f.name for f in joints.all_followers(scene, j)][::-1] + [self.joint]
        s = scene.fresing
        for n in names:
            jj = joints.find(scene, n)
            if jj is None:
                continue
            s.joints_index = list(s.joints).index(jj)
            bpy.ops.fresing.joint_remove()
        SC.changed(scene)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_cylinder(bpy.types.Operator):
    """Adds the cylinder that drives this joint: pick its barrel, then its rod (in that order). The pins are the
    round faces at their eyes; it shows in 4 Motion > Cylinders"""

    bl_idname = "fresing.crane_cylinder"
    bl_label = "Add the cylinder"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(items=ROLE_ITEMS, options={"SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick)
        if bad or len(objs) < 2:
            self.report({"WARNING"}, "; ".join(bad) or "Pick the barrel, then the rod")
            return {"CANCELLED"}
        try:
            c = SC.make_cylinder(scene, self.role, objs[0], objs[1])
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.pick = ""
        _say(context, f"Cylinder '{c}' added")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_sheave(bpy.types.Operator):
    """Uses the picked part as the head sheave: the hoist rope hangs from its centre"""

    bl_idname = "fresing.crane_sheave"
    bl_label = "Use as head sheave"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and bool(SC.settings(context.scene).pick)

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick)
        if bad or not objs:
            self.report({"WARNING"}, "; ".join(bad) or "Pick the head sheave first")
            return {"CANCELLED"}
        p = SC.sheave_centre(scene, objs[0])
        if p is None:
            self.report({"WARNING"}, f"{SC.name_of(objs[0])} has no level round face: pick the sheave itself")
            return {"CANCELLED"}
        cs.sheave, cs.sheave_set = tuple(p), True
        cs.pick = ""
        SC.changed(scene)
        _say(context, f"Head sheave: {SC.name_of(objs[0])}")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_hook(bpy.types.Operator):
    """Makes the hoist (straight down from the head sheave) and the hook swing joints that keep the picked hook block
    plumb, and finds the hook's saddle"""

    bl_idname = "fresing.crane_hook"
    bl_label = "Make the hoist and hook"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        cs = SC.settings(context.scene)
        return _has_model(context) and cs.sheave_set and bool(cs.pick)

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick)
        if bad or not objs:
            self.report({"WARNING"}, "; ".join(bad) or "Pick the hook block first")
            return {"CANCELLED"}
        if SC.first(scene, "luff") is None:
            self.report({"WARNING"}, "Make the boom's joint first (Luff / Boom / Main boom)")
            return {"CANCELLED"}
        try:
            got = SC.make_hook(scene, objs[0], Vector(cs.sheave))
            SC.set_hook_point(scene, objs[0])
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.hook_part = SC.name_of(objs[0])
        cs.pick = ""
        try:
            SC.make_rope(scene)
        except Exception as exc:  # noqa: BLE001 - a rope that cannot follow must not stop the set-up
            _say(context, f"The rope stays as drawn: {exc}")
        else:
            _say(context, f"Made: {got['hoist']} and {len(got['swings'])} hook swing joint(s)")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_corner(bpy.types.Operator):
    """Adds an outrigger (stabiliser) corner: the picked beam stages from the inside out, the jack (leg) last. The
    first corner drives, the others follow it"""

    bl_idname = "fresing.crane_corner"
    bl_label = "Add corner"
    bl_options = {"REGISTER", "UNDO"}

    jack_stroke: FloatProperty(name="Jack stroke", default=0.0, min=0.0, unit="LENGTH", options={"SKIP_SAVE"},
                               description="How far the jack (leg) goes down, m. 0: as the first corner's")

    @classmethod
    def poll(cls, context):
        return _has_model(context) and bool(SC.settings(context.scene).pick)

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick)
        if bad or len(objs) < 2:
            self.report({"WARNING"}, "; ".join(bad) or "Pick the beam stage(s), then the jack")
            return {"CANCELLED"}
        try:
            made = SC.make_corner(scene, objs[:-1], objs[-1], cs.stroke, self.jack_stroke)
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.pick = ""
        _say(context, "Corner: " + ", ".join(made))
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_track(bpy.types.Operator):
    """Adds a crawler track: the picked wheels (drive sprocket first), then one link, then its shoe last. The track
    runs with the travel joint (4 Motion > Tracks and belts)"""

    bl_idname = "fresing.crane_track"
    bl_label = "Add track"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_model(context) and SC.first(context.scene, "travel") is not None

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        objs, bad = SC.objects_of(scene, cs.pick, many_ok=True)
        if bad or len(objs) < 4:
            self.report({"WARNING"}, "; ".join(bad) or "Pick two wheels, a link and a shoe")
            return {"CANCELLED"}
        try:
            name = SC.make_track(scene, objs[:-2], objs[-2], [objs[-1]])
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.pick = ""
        _say(context, f"Track '{name}' added")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_group_parts(bpy.types.Operator):
    """Uses the picked parts for this mass group"""

    bl_idname = "fresing.crane_group_parts"
    bl_label = "Use for the group"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        SC.ensure_groups(scene)
        g = next((g for g in cs.groups if g.key == self.key), None)
        if g is None:
            g = cs.groups.add()
            g.key = g.name = self.key
        g.parts = cs.pick
        cs.pick = ""
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_groups(bpy.types.Operator):
    """Makes the crane's mass groups (carrier, superstructure, counterweight, boom …), each filled with the parts its
    joint moves: change them below when they are not right"""

    bl_idname = "fresing.crane_groups"
    bl_label = "Make the groups"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        SC.ensure_groups(context.scene)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_group_work(bpy.types.Operator):
    """Works out the group's volume x density and its centre of gravity from the parts' solids (in the CAD pose), and
    puts its marker there"""

    bl_idname = "fresing.crane_group_work"
    bl_label = "Work out"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        scene = context.scene
        cs = SC.settings(scene)
        groups = [g for g in cs.groups if g.key == self.key or not self.key]
        notes = []
        with joints.cad_pose(scene):
            for g in groups:
                if g.parts:
                    n = SC.work_out(scene, g)
                    if n:
                        notes.append(f"{SC.group_title(scene, g.key)}: {n}")
        for g in groups:
            if g.parts:
                SC.update_marker(scene, g)
        _say(context, "; ".join(notes) if notes else "Worked out")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_chart_add(bpy.types.Operator):
    """Adds a configuration (or a row to one), or removes a configuration"""

    bl_idname = "fresing.crane_chart_add"
    bl_label = "Chart"
    bl_options = {"REGISTER", "UNDO"}

    row_of: IntProperty(default=-1, options={"SKIP_SAVE"})
    remove: IntProperty(default=-1, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, "remove", -1) >= 0:
            return "Removes this configuration and its rows"
        if getattr(properties, "row_of", -1) >= 0:
            return "Adds a row (radius and capacity) to this configuration"
        return "Adds a configuration: a boom length (jib, counterweight, spread) with its own rows"

    def execute(self, context):
        cs = SC.settings(context.scene)
        if self.remove >= 0:
            if self.remove < len(cs.charts):
                cs.charts.remove(self.remove)
        elif self.row_of >= 0:
            if self.row_of < len(cs.charts):
                cs.charts[self.row_of].rows.add()
        else:
            cs.charts.add().rows.add()
        SC.changed(context.scene)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_chart_csv(bpy.types.Operator):
    """Reads the load chart from CSV: pasted (copied from a spreadsheet) or from a file. A line like 'boom 30.4 m;
    counterweight 40 t' starts a configuration; then 'radius;capacity' per line"""

    bl_idname = "fresing.crane_chart_csv"
    bl_label = "Chart from CSV"
    bl_options = {"REGISTER", "UNDO"}

    paste: BoolProperty(default=True, options={"SKIP_SAVE"})
    text: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"},
                         description="The CSV text (empty: the clipboard)")
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default="*.csv;*.txt", options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        if getattr(properties, "paste", True):
            return ("Reads the load chart copied from a spreadsheet or the maker's file (radius;capacity per line; "
                    "a line like 'boom 30.4 m' starts a configuration). Refused rows are named")
        return "Reads the load chart from a CSV file. Refused rows are named"

    def invoke(self, context, event):
        if self.paste:
            return self.execute(context)
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from ..core import lifting_library as LL
        if self.paste:
            text = self.text or context.window_manager.clipboard
            entry = LL.chart_csv(text or "", "t", "m")
        else:
            if not self.filepath or not os.path.isfile(self.filepath):
                self.report({"WARNING"}, "Pick a CSV file")
                return {"CANCELLED"}
            entry = LL.read_chart_csv(self.filepath, "t", "m")
        if not entry.ok:
            SC.settings(context.scene).message = "Chart not taken: " + " ".join(entry.errors[:5])
            self.report({"WARNING"}, "Chart not taken: " + " ".join(entry.errors[:3]))
            return {"CANCELLED"}
        n = SC.fill_charts(context.scene, entry)
        _say(context, f"{n} configuration(s) read")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_check(bpy.types.Operator):
    """Checks the crane: every joint from its Min to its Max and every pose (the hook stays plumb, nothing clashes,
    no follower goes past its limits), the masses and CoG, the chart. Each problem leads to its step"""

    bl_idname = "fresing.crane_check"
    bl_label = "Check"
    bl_options = {"REGISTER"}

    clash: BoolProperty(default=True, options={"SKIP_SAVE"},
                        description="Also run the clash check on the crane's own motion (takes longer)")

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        problems = SC.run_check(context.scene, clash=self.clash)
        red = [p for p in problems if p.severity == "red"]
        self.report({"WARNING"} if red else {"INFO"},
                    f"{len(red)} problem(s)" if red else "Check found nothing wrong")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_go(bpy.types.Operator):
    """Goes to the step that fixes this problem"""

    bl_idname = "fresing.crane_go"
    bl_label = "Go to step"
    bl_options = {"INTERNAL"}

    key: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        from . import ops_setup
        k = SC.step_index(context.scene.fresing.setup_kind, self.key)
        if k < 0:
            return {"CANCELLED"}
        ops_setup.go(context.scene, k)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_crane_save(bpy.types.Operator):
    """Saves the crane to your library (Lifting equipment): its file with joints, poses, hook, masses, CoG and chart,
    a copy of the STEP and a picture. Place it from 8 Lifting plan in any project"""

    bl_idname = "fresing.crane_save"
    bl_label = "Save to library"
    bl_options = {"REGISTER"}

    library: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"},
                            description="The folder to save into (empty: your first Lifting equipment folder, Fresing Settings > "
                                        "Locations)")

    @classmethod
    def poll(cls, context):
        return _has_model(context)

    def execute(self, context):
        from . import lifting, lifting_rig_out
        scene = context.scene
        cs = SC.settings(scene)
        folder = self.library or lifting.user_folder()
        try:
            path = lifting_rig_out.save(scene, folder)
        except (RuntimeError, ValueError) as exc:
            cs.message = str(exc)
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        cs.saved_path = path
        cs.message = f"Saved to {os.path.dirname(path)}. Place it from 8 Lifting plan > Equipment."
        lifting.library(force=True)
        self.report({"INFO"}, cs.message)
        _redraw()
        return {"FINISHED"}


CLASSES = (FRESING_OT_crane_setup, FRESING_OT_crane_pick, FRESING_OT_crane_axes, FRESING_OT_crane_axis_use,
           FRESING_OT_crane_make, FRESING_OT_crane_make_click, FRESING_OT_crane_flip, FRESING_OT_crane_remove,
           FRESING_OT_crane_cylinder, FRESING_OT_crane_sheave, FRESING_OT_crane_hook, FRESING_OT_crane_corner,
           FRESING_OT_crane_track, FRESING_OT_crane_group_parts, FRESING_OT_crane_groups,
           FRESING_OT_crane_group_work,
           FRESING_OT_crane_chart_add, FRESING_OT_crane_chart_csv, FRESING_OT_crane_check, FRESING_OT_crane_go,
           FRESING_OT_crane_save)


def register():
    if SC.forget not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(SC.forget)


def unregister():
    while SC.forget in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(SC.forget)
