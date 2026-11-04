"""Buttons of the tree in 2 Structure and of the search/grouping tools in 3 Looks."""

from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty

from . import build, faces, finder, logic
from . import tree as tree_mod

# =============================================================================
# 2 Structure: the tree
# =============================================================================


class FRESING_OT_tree_toggle(bpy.types.Operator):
    """Open or close this assembly in the list"""

    bl_idname = "fresing.tree_toggle"
    bl_label = "Open / close"
    bl_options = {"INTERNAL"}

    index: IntProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= self.index < len(s.tree)):
            return {"CANCELLED"}
        tree_mod.set_open(s, self.index, not s.tree[self.index].expanded)
        return {"FINISHED"}


class FRESING_OT_tree_open_all(bpy.types.Operator):
    """Open or close every assembly in the list"""

    bl_idname = "fresing.tree_open_all"
    bl_label = "Open all"
    bl_options = {"INTERNAL"}

    open: BoolProperty(default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        tree_mod.open_all(context.scene.fresing, self.open)
        return {"FINISHED"}


class FRESING_OT_tree_row(bpy.types.Operator):
    """Select, add to the selection, zoom to, hide or show only this row"""

    bl_idname = "fresing.tree_row"
    bl_label = "Row action"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(options={"SKIP_SAVE"})
    action: EnumProperty(items=[("SELECT", "Select", "Select it in the view (Shift/Ctrl-click adds)"),
                                ("ADD", "Add", "Add it to the selection"),
                                ("FRAME", "Zoom to", "Select it and zoom the view onto it"),
                                ("HIDE", "Hide / show", "Hide or show it (also in renders)"),
                                ("ONLY", "Show only this", "Hide everything else")],
                         default="SELECT", options={"SKIP_SAVE"})
    extend: BoolProperty(default=False, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {"SELECT": "Select it in the view. Shift or Ctrl-click: add to the selection",
                "ADD": "Select this too (adds it to what is selected)",
                "FRAME": "Select it and zoom the view onto it",
                "HIDE": "Hide or show it (also in renders)",
                "ONLY": "Show only this, hide everything else (Show all brings it back)"}[properties.action]

    def invoke(self, context, event):
        self.extend = event.shift or event.ctrl
        return self.execute(context)

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        if not (0 <= self.index < len(s.tree)) or s.tree[self.index].obj is None:
            return {"CANCELLED"}
        item = s.tree[self.index]
        t = logic.Tree(scene)
        objs = tree_mod.row_objects(scene, item, t)
        if self.action == "HIDE":
            hidden = not logic.is_hidden(item.obj)
            if item.is_part:
                for o in objs:
                    logic.set_hidden(o, hidden, t)
            else:
                logic.set_hidden(item.obj, hidden, t)
            s.bounds_valid = False
            return {"FINISHED"}
        if self.action == "ONLY":
            tree_mod.show_only(scene, objs, item.label)
            return {"FINISHED"}
        tree_mod.select_objects(context, objs, extend=self.extend or self.action == "ADD")
        tree_mod._set_index_quietly(s, self.index)
        if self.action == "FRAME":
            tree_mod.frame_selected(context)
        return {"FINISHED"}


class FRESING_OT_show_only_selected(bpy.types.Operator):
    """Show only the selected parts and subassemblies; Show all brings everything back"""

    bl_idname = "fresing.show_only_selected"
    bl_label = "Show only selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        t = logic.Tree(context.scene)
        keep = []
        for ob in context.selected_objects:
            if ob.get(build.PROP_KIND) in build.MODEL_KINDS:
                keep += [ob] + t.descendants(ob)
        if not keep:
            self.report({"WARNING"}, "Select something first (click it in the view or in the list)")
            return {"CANCELLED"}
        tree_mod.show_only(context.scene, keep, "the selection")
        return {"FINISHED"}


class FRESING_OT_show_only_end(bpy.types.Operator):
    """Show everything that Show only hid (parts you hid yourself stay hidden)"""

    bl_idname = "fresing.show_only_end"
    bl_label = "Back to everything"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        tree_mod.end_show_only(context.scene)
        return {"FINISHED"}


# =============================================================================
# 3 Looks: find, group, rules
# =============================================================================

_GROUP_ITEMS: list = []         # Blender needs the enum strings to stay alive


def _group_items(self, context):
    _GROUP_ITEMS.clear()
    s = context.scene.fresing if context and context.scene else None
    if s is not None:
        for g in s.groups:
            _GROUP_ITEMS.append((g.name, g.name, f"Put them in {g.name}"))
    _GROUP_ITEMS.append(("__new__", "New group…", "A new group (named after the search)"))
    return _GROUP_ITEMS


class FRESING_OT_find_tick(bpy.types.Operator):
    """Tick or untick every part name found"""

    bl_idname = "fresing.find_tick"
    bl_label = "Tick all"
    bl_options = {"INTERNAL"}

    tick: BoolProperty(default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        for it in context.scene.fresing.found:
            it.use = self.tick
        return {"FINISHED"}


class FRESING_OT_find_word(bpy.types.Operator):
    """Find the parts with this word in their name"""

    bl_idname = "fresing.find_word"
    bl_label = "Find word"
    bl_options = {"INTERNAL"}

    word: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        context.scene.fresing.find_text = self.word        # runs the search
        return {"FINISHED"}


class FRESING_OT_find_select(bpy.types.Operator):
    """Select the ticked parts in the view"""

    bl_idname = "fresing.find_select"
    bl_label = "Select ticked"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        objs = finder.ticked_parts(context.scene)
        if not objs:
            return {"CANCELLED"}
        tree_mod.select_objects(context, objs)
        self.report({"INFO"}, f"{len(objs)} parts selected")
        return {"FINISHED"}


class FRESING_OT_find_assign(bpy.types.Operator):
    """Put the ticked parts in a material group"""

    bl_idname = "fresing.find_assign"
    bl_label = "Put ticked in group"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "group"

    group: EnumProperty(name="Group", items=_group_items)

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        objs = finder.ticked_parts(scene)
        if not objs:
            self.report({"WARNING"}, "Nothing ticked")
            return {"CANCELLED"}
        group = self.group
        if group == "__new__":
            group = finder.unique_group_name(s, finder.group_name_for(s.find_text))
        n = finder.put_in_group(scene, objs, group)
        finder.run_search(scene)
        self.report({"INFO"}, f"{n} parts in {group}")
        return {"FINISHED"}


class FRESING_OT_find_new_group(bpy.types.Operator):
    """Make a new group named after the search and put the ticked parts in it"""

    bl_idname = "fresing.find_new_group"
    bl_label = "New group from search"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        return bpy.ops.fresing.find_assign(group="__new__")


class FRESING_OT_find_rule(bpy.types.Operator):
    """Save this search as a sorting rule for the selected group: the next model revision sorts itself"""

    bl_idname = "fresing.find_rule"
    bl_label = "Make it a rule"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not finder.terms_of(s.find_text) or not (0 <= s.groups_index < len(s.groups)):
            self.report({"WARNING"}, "Search for something and pick a group first")
            return {"CANCELLED"}
        group = s.groups[s.groups_index].name
        field, op, value = finder.rule_for_search(s.find_text)
        finder.add_rule_on_top(s, group, field, op, value, note=f"from the search '{s.find_text.strip()}'")
        logic.apply_rules(context.scene)
        unticked = sum(1 for it in s.found if not it.use)
        extra = f" (it also covers the {unticked} unticked names)" if unticked else ""
        self.report({"INFO"}, f"Rule added: names with '{s.find_text.strip()}' go to {group}{extra}")
        return {"FINISHED"}


class FRESING_OT_rule_from_subassembly(bpy.types.Operator):
    """Sorting rule: every part inside the subassembly selected in 2 Structure goes to the selected group"""

    bl_idname = "fresing.rule_from_subassembly"
    bl_label = "Rule: this subassembly → this group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        if not (0 <= s.tree_index < len(s.tree)) or s.tree[s.tree_index].is_part \
                or not (0 <= s.groups_index < len(s.groups)):
            self.report({"WARNING"}, "Pick a subassembly in 2 Structure and a group here first")
            return {"CANCELLED"}
        sub = s.tree[s.tree_index].obj
        name = sub.get(build.PROP_NAME, sub.name)
        group = s.groups[s.groups_index].name
        finder.add_rule_on_top(s, group, "path", "contains", name, note="everything in this subassembly")
        logic.apply_rules(scene)
        self.report({"INFO"}, f"Every part in {name} goes to {group}")
        return {"FINISHED"}


class FRESING_OT_show_only_group(bpy.types.Operator):
    """Show only these parts (Show all brings everything back)"""

    bl_idname = "fresing.show_only_group"
    bl_label = "Show only these"
    bl_options = {"REGISTER", "UNDO"}

    group: StringProperty(options={"SKIP_SAVE"})       # '' = the parts no rule matched

    def execute(self, context):
        scene = context.scene
        if self.group:
            objs = logic.parts_in_group(scene, self.group)
            label = self.group
        else:
            objs = finder.unsorted_parts(scene)
            label = "unsorted parts"
        if not objs:
            self.report({"INFO"}, "No parts")
            return {"CANCELLED"}
        tree_mod.show_only(scene, objs, label)
        return {"FINISHED"}


class FRESING_OT_group_preset(bpy.types.Operator):
    """Give the selected group a ready-made machine material"""

    bl_idname = "fresing.group_preset"
    bl_label = "Ready-made material"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "preset"

    preset: EnumProperty(name="Material", items=[(p[0], p[1], "") for p in finder.PRESETS])

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.groups_index < len(s.groups)):
            return {"CANCELLED"}
        _pid, label, mat, color = next(p for p in finder.PRESETS if p[0] == self.preset)
        g = s.groups[s.groups_index]
        g.material = mat
        if color:
            g.color = color
        logic.refresh_group_materials(context.scene)
        self.report({"INFO"}, f"{g.name}: {label}")
        return {"FINISHED"}


class FRESING_OT_part_move_group(bpy.types.Operator):
    """Put the selected parts in another material group"""

    bl_idname = "fresing.part_move_group"
    bl_label = "Move to group"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "group"

    group: EnumProperty(name="Group", items=_group_items)

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        t = logic.Tree(scene)
        objs = []
        for ob in context.selected_objects:
            objs += [o for o in [ob] + t.descendants(ob) if o.get(build.PROP_KIND) == "part"]
        if not objs:
            return {"CANCELLED"}
        group = self.group
        if group == "__new__":
            first = objs[0].get(build.PROP_NAME, objs[0].name)
            group = finder.unique_group_name(s, finder.group_name_for(first.split()[0] if first else "New group"))
        n = finder.put_in_group(scene, objs, group)
        self.report({"INFO"}, f"{n} parts in {group}")
        return {"FINISHED"}


# =============================================================================
# 3 Looks: paint single faces
# =============================================================================

_FACE_GROUP_ITEMS: list = []


def _face_group_items(self, context):
    _FACE_GROUP_ITEMS.clear()
    s = context.scene.fresing if context and context.scene else None
    _FACE_GROUP_ITEMS.append((faces.SAME_AS_PART, "Like the rest of the part",
                              "These faces get the look of their part again"))
    if s is not None:
        for g in s.groups:
            _FACE_GROUP_ITEMS.append((g.name, g.name, f"These faces get the look of {g.name}"))
    return _FACE_GROUP_ITEMS


def paint_group(s) -> str:
    """The group 'Paint faces' paints with: the chosen one, else the one selected in the list."""
    if s.face_group and s.groups.get(s.face_group) is not None:
        return s.face_group
    if 0 <= s.groups_index < len(s.groups):
        return s.groups[s.groups_index].name
    return ""


def _region_under_mouse(context, event):
    """(region, 3D view data) of the 3D view under the mouse, or (None, None) (side panel, header...)."""
    for area in context.window.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for region in area.regions:
            if (region.type == "WINDOW" and region.x <= event.mouse_x < region.x + region.width
                    and region.y <= event.mouse_y < region.y + region.height):
                rv3d = region.data if getattr(region, "data", None) is not None else area.spaces.active.region_3d
                # the side panel lies over the view: a click on it is not a click on the model
                for other in area.regions:
                    if (other.type == "UI" and other.width > 1 and other.x <= event.mouse_x < other.x + other.width
                            and other.y <= event.mouse_y < other.y + other.height):
                        return None, None
                return region, rv3d
    return None, None


def face_under_mouse(context, region, rv3d, x: int, y: int):
    """(part object, CAD face number) under the point (x, y) of a 3D view region, or (None, -1)."""
    from bpy_extras import view3d_utils
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (x, y))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (x, y))
    depsgraph = context.evaluated_depsgraph_get()
    hit, _loc, _nrm, index, ob, _m = context.scene.ray_cast(depsgraph, origin, direction)
    if not hit or ob is None:
        return None, -1
    ob = getattr(ob, "original", ob)
    if ob.get(build.PROP_KIND) != "part" or ob.type != "MESH" or ob.data is None:
        return None, -1
    return ob, faces.face_of_polygon(ob.data, index)


def paint_click(context, ob, face: int, remove: bool = False) -> str:
    """What one click in 'Paint faces' does. Returns a message."""
    s = context.scene.fresing
    name = ob.get(build.PROP_NAME, ob.name)
    if remove:
        n = faces.unpaint(ob, [face])
        msg = f"{name}: face back to the look of the part" if n else f"{name}: that face was not painted"
    else:
        group = paint_group(s)
        if not group:
            return "Pick a group to paint with first"
        logic.ensure_group(s, group)
        faces.paint(ob, [face], group, s.face_only_copy)
        msg = f"{name}: face painted with {group}" + (" (this copy)" if s.face_only_copy else "")
    logic.apply_rules(context.scene)
    return msg


class FRESING_OT_paint_faces(bpy.types.Operator):
    """Click faces of parts in the view to give them the look of the chosen group (a whole CAD face
    per click). Shift+click: that face looks like the rest of its part again. Enter, Esc or
    right-click: done"""

    bl_idname = "fresing.paint_faces"
    bl_label = "Paint faces"
    bl_options = {"REGISTER", "UNDO"}

    _HINT = "Paint faces: click a face  ·  Shift+click: back to the part  ·  Enter / right-click: done"

    @classmethod
    def poll(cls, context):
        return context.window is not None and context.scene.fresing.model_count > 0

    def invoke(self, context, event):
        s = context.scene.fresing
        if not paint_group(s):
            self.report({"WARNING"}, "Pick a group to paint with first")
            return {"CANCELLED"}
        if s.face_painting:                       # pressed again: stop
            s.face_painting = False
            return {"CANCELLED"}
        s.face_painting = True
        self.painted = 0
        context.window_manager.modal_handler_add(self)
        try:
            context.workspace.status_text_set(self._HINT)
        except Exception:
            pass
        context.window.cursor_modal_set("PAINT_BRUSH")
        self._redraw(context)
        return {"RUNNING_MODAL"}

    def _redraw(self, context):
        for area in context.window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()

    def _finish(self, context):
        s = context.scene.fresing
        s.face_painting = False
        try:
            context.workspace.status_text_set(None)
        except Exception:
            pass
        context.window.cursor_modal_restore()
        self._redraw(context)
        if self.painted:
            self.report({"INFO"}, f"{self.painted} faces changed")
        return {"FINISHED"}

    def modal(self, context, event):
        s = context.scene.fresing
        if not s.face_painting:                   # "Done" in the side panel
            return self._finish(context)
        if event.value == "PRESS" and event.type in {"RET", "NUMPAD_ENTER", "ESC", "RIGHTMOUSE"}:
            region, _rv3d = _region_under_mouse(context, event)
            if event.type != "RIGHTMOUSE" or region is not None:
                return self._finish(context)
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            region, rv3d = _region_under_mouse(context, event)
            if region is None:
                return {"PASS_THROUGH"}          # buttons in the side panel keep working
            ob, face = face_under_mouse(context, region, rv3d, event.mouse_x - region.x, event.mouse_y - region.y)
            if ob is not None and face >= 0:
                self.report({"INFO"}, paint_click(context, ob, face, remove=event.shift))
                self.painted += 1
                self._redraw(context)
            return {"RUNNING_MODAL"}
        return {"PASS_THROUGH"}                   # turn, pan and zoom the view as usual


class FRESING_OT_paint_faces_done(bpy.types.Operator):
    """Stop painting faces (Enter, Esc or right-click in the view does the same)"""

    bl_idname = "fresing.paint_faces_done"
    bl_label = "Done"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        context.scene.fresing.face_painting = False
        return {"FINISHED"}


def _active_part(context):
    ob = context.active_object
    if ob is not None and ob.get(build.PROP_KIND) == "part" and ob.type == "MESH" and ob.data is not None:
        return ob
    return None


class FRESING_OT_face_set_group(bpy.types.Operator):
    """Choose the group of these faces: their material and colour come from that group. With
    'Only this copy' ticked, only the active copy of the part changes"""

    bl_idname = "fresing.face_set_group"
    bl_label = "Group of these faces"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "group"

    key: StringProperty(options={"SKIP_SAVE"})
    group: EnumProperty(name="Group", items=_face_group_items)

    def execute(self, context):
        ob = _active_part(context)
        if ob is None or not self.key:
            return {"CANCELLED"}
        s = context.scene.fresing
        faces.set_group(ob, self.key, self.group, s.face_only_copy)
        logic.apply_rules(context.scene)
        return {"FINISHED"}


class FRESING_OT_face_set_remove(bpy.types.Operator):
    """Back to the whole part: these faces get the look of the rest of the part again. With 'Only
    this copy' ticked, only on the active copy"""

    bl_idname = "fresing.face_set_remove"
    bl_label = "Back to whole part"
    bl_options = {"REGISTER", "UNDO"}

    key: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = _active_part(context)
        if ob is None or not self.key:
            return {"CANCELLED"}
        faces.remove(ob, self.key, context.scene.fresing.face_only_copy)
        logic.apply_rules(context.scene)
        return {"FINISHED"}


CLASSES = (
    FRESING_OT_paint_faces, FRESING_OT_paint_faces_done, FRESING_OT_face_set_group, FRESING_OT_face_set_remove,
    FRESING_OT_tree_toggle, FRESING_OT_tree_open_all, FRESING_OT_tree_row, FRESING_OT_show_only_selected,
    FRESING_OT_show_only_end, FRESING_OT_find_tick, FRESING_OT_find_word, FRESING_OT_find_select,
    FRESING_OT_find_assign, FRESING_OT_find_new_group, FRESING_OT_find_rule, FRESING_OT_rule_from_subassembly,
    FRESING_OT_show_only_group, FRESING_OT_group_preset, FRESING_OT_part_move_group,
)
