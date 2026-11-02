"""Operators for structure, looks (groups, rules, schemes) and rendering."""

from __future__ import annotations

import os
import subprocess
import sys

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from ..core import rules as R
from ..core.template import GroupLook, Scheme, Template
from . import build, cameras, logic, render, world

# =============================================================================
# Structure
# =============================================================================


def _active_tree_obj(context):
    s = context.scene.fresing
    if 0 <= s.tree_index < len(s.tree):
        return s.tree[s.tree_index].obj
    return None


class FRESING_OT_tree_refresh(bpy.types.Operator):
    """Rebuild the subassembly list"""

    bl_idname = "fresing.tree_refresh"
    bl_label = "Refresh"

    def execute(self, context):
        logic.rebuild_tree(context.scene)
        return {"FINISHED"}


class FRESING_OT_select_subassembly(bpy.types.Operator):
    """Select a subassembly with all its parts"""

    bl_idname = "fresing.select_subassembly"
    bl_label = "Select subassembly"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})
    extend: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name) if self.name else _active_tree_obj(context)
        if ob is None:
            return {"CANCELLED"}
        if not self.extend:
            for o in context.selected_objects:
                o.select_set(False)
        for d in [ob] + logic.descendants(ob):
            if d.visible_get() and not d.hide_select:
                d.select_set(True)
        try:
            ob.select_set(True)
        except RuntimeError:
            pass
        context.view_layer.objects.active = ob
        return {"FINISHED"}


class FRESING_OT_toggle_lock(bpy.types.Operator):
    """Locked: moves only with its parent. Unlocked: can be moved on its own"""

    bl_idname = "fresing.toggle_lock"
    bl_label = "Lock / unlock subassembly"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {"CANCELLED"}
        logic.set_locked(ob, not ob.get(build.PROP_LOCKED, True))
        return {"FINISHED"}


class FRESING_OT_toggle_hide(bpy.types.Operator):
    """Show or hide a subassembly (also in renders)"""

    bl_idname = "fresing.toggle_hide"
    bl_label = "Show / hide"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {"CANCELLED"}
        logic.set_hidden(ob, not logic.is_hidden(ob))
        return {"FINISHED"}


class FRESING_OT_hide_selected(bpy.types.Operator):
    """Hide the selected parts (also in renders). Use Show all to bring them back"""

    bl_idname = "fresing.hide_selected"
    bl_label = "Hide selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        for ob in context.selected_objects:
            if ob.get(build.PROP_KIND):
                logic.set_hidden(ob, True)
        return {"FINISHED"}


class FRESING_OT_show_all(bpy.types.Operator):
    """Show every hidden part again (parts removed with Clean-up stay hidden)"""

    bl_idname = "fresing.show_all"
    bl_label = "Show all"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        for ob in context.scene.objects:
            if ob.get(build.PROP_KIND) and not ob.get(build.PROP_EXCLUDED):
                logic.set_hidden(ob, False)
        return {"FINISHED"}


class FRESING_OT_exclude_selected(bpy.types.Operator):
    """Remove the selected parts from every view and render (internal parts, hidden fasteners...)"""

    bl_idname = "fresing.exclude_selected"
    bl_label = "Remove for good"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = logic.exclude([ob for ob in context.selected_objects if ob.get(build.PROP_KIND)], True)
        self.report({"INFO"}, f"Removed {n} parts (Restore removed parts brings them back)")
        return {"FINISHED"}


class FRESING_OT_restore_excluded(bpy.types.Operator):
    """Bring back all parts removed with Clean-up"""

    bl_idname = "fresing.restore_excluded"
    bl_label = "Restore removed parts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = logic.restore_excluded(context.scene)
        self.report({"INFO"}, f"Restored {n} parts")
        return {"FINISHED"}


class FRESING_OT_select_small(bpy.types.Operator):
    """Select parts smaller than the given size (mm)"""

    bl_idname = "fresing.select_small"
    bl_label = "Select small parts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        for o in context.selected_objects:
            o.select_set(False)
        objs = logic.small_parts(context.scene, s.small_part_mm)
        for ob in objs:
            if ob.visible_get():
                ob.select_set(True)
        self.report({"INFO"}, f"{len(objs)} parts smaller than {s.small_part_mm:g} mm")
        return {"FINISHED"}


# =============================================================================
# Looks: groups, rules, schemes, templates
# =============================================================================


class FRESING_OT_apply_rules(bpy.types.Operator):
    """Sort all parts into material groups using the rules (manual assignments are kept)"""

    bl_idname = "fresing.apply_rules"
    bl_label = "Sort parts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        res = logic.apply_rules(context.scene)
        self.report({"INFO"}, f"{res['parts']} parts in {res['groups']} groups, {res['unmatched']} unsorted")
        return {"FINISHED"}


class FRESING_OT_group_add(bpy.types.Operator):
    """Add a new material group"""

    bl_idname = "fresing.group_add"
    bl_label = "New group"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="New group")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        s = context.scene.fresing
        name = self.name.strip() or "New group"
        base, i = name, 2
        while s.groups.get(name):
            name = f"{base} {i}"
            i += 1
        logic.ensure_group(s, name)
        s.groups_index = len(s.groups) - 1
        return {"FINISHED"}


class FRESING_OT_group_remove(bpy.types.Operator):
    """Remove the material group; its parts are sorted again by the rules"""

    bl_idname = "fresing.group_remove"
    bl_label = "Remove group"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.groups_index < len(s.groups)):
            return {"CANCELLED"}
        name = s.groups[s.groups_index].name
        for ob in build.iter_parts(context.scene):
            if ob.get("fr_group_manual") == name:
                del ob["fr_group_manual"]
        s.groups.remove(s.groups_index)
        s.groups_index = max(0, s.groups_index - 1)
        logic.apply_rules(context.scene)
        return {"FINISHED"}


class FRESING_OT_group_select(bpy.types.Operator):
    """Select all parts in the active material group"""

    bl_idname = "fresing.group_select"
    bl_label = "Select parts"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.groups_index < len(s.groups)):
            return {"CANCELLED"}
        for o in context.selected_objects:
            o.select_set(False)
        objs = logic.parts_in_group(context.scene, s.groups[s.groups_index].name)
        last = None
        for ob in objs:
            if ob.visible_get():
                ob.select_set(True)
                last = ob
        if last:
            context.view_layer.objects.active = last
        self.report({"INFO"}, f"{len(objs)} parts")
        return {"FINISHED"}


class FRESING_OT_group_assign(bpy.types.Operator):
    """Put the selected parts in the active material group (overrides the rules for these parts)"""

    bl_idname = "fresing.group_assign"
    bl_label = "Assign selected"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if not (0 <= s.groups_index < len(s.groups)):
            return {"CANCELLED"}
        group = s.groups[s.groups_index].name
        n = 0
        for ob in context.selected_objects:
            targets = [ob] + logic.descendants(ob)
            for t in targets:
                if t.get(build.PROP_KIND) == "part" and t.type == "MESH":
                    t["fr_group_manual"] = group
                    n += 1
        logic.apply_rules(context.scene)
        self.report({"INFO"}, f"{n} parts assigned to {group}")
        return {"FINISHED"}


class FRESING_OT_group_unassign(bpy.types.Operator):
    """Let the rules decide again for the selected parts"""

    bl_idname = "fresing.group_unassign"
    bl_label = "Back to rules"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = 0
        for ob in context.selected_objects:
            for t in [ob] + logic.descendants(ob):
                if "fr_group_manual" in t:
                    del t["fr_group_manual"]
                    n += 1
        logic.apply_rules(context.scene)
        self.report({"INFO"}, f"{n} parts follow the rules again")
        return {"FINISHED"}


class FRESING_OT_rule_add(bpy.types.Operator):
    """Add a sorting rule (checked from top to bottom; the first match wins)"""

    bl_idname = "fresing.rule_add"
    bl_label = "Add rule"
    bl_options = {"REGISTER", "UNDO"}

    from_selection: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    def execute(self, context):
        s = context.scene.fresing
        r = s.rules.add()
        r.field, r.op = "name", "contains"
        group = s.groups[s.groups_index].name if 0 <= s.groups_index < len(s.groups) else "New group"
        r.target = group
        ob = context.active_object
        if self.from_selection and ob is not None and ob.get(build.PROP_KIND) == "part":
            r.value = ob.get(build.PROP_NAME, ob.name)
        # new rules go to the top so they win over the defaults
        s.rules.move(len(s.rules) - 1, 0)
        s.rules_index = 0
        return {"FINISHED"}


class FRESING_OT_rule_remove(bpy.types.Operator):
    bl_idname = "fresing.rule_remove"
    bl_label = "Remove rule"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.rules_index < len(s.rules):
            s.rules.remove(s.rules_index)
            s.rules_index = max(0, s.rules_index - 1)
        return {"FINISHED"}


class FRESING_OT_rule_move(bpy.types.Operator):
    bl_idname = "fresing.rule_move"
    bl_label = "Move rule"
    bl_options = {"REGISTER", "UNDO"}

    direction: EnumProperty(items=[("UP", "Up", ""), ("DOWN", "Down", "")])

    def execute(self, context):
        s = context.scene.fresing
        i = s.rules_index
        j = i - 1 if self.direction == "UP" else i + 1
        if 0 <= i < len(s.rules) and 0 <= j < len(s.rules):
            s.rules.move(i, j)
            s.rules_index = j
        return {"FINISHED"}


class FRESING_OT_rules_reset(bpy.types.Operator):
    """Replace all rules with the built-in defaults"""

    bl_idname = "fresing.rules_reset"
    bl_label = "Reset rules to defaults"
    bl_options = {"REGISTER", "UNDO"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        logic.load_rules_into_scene(context.scene.fresing, R.default_rules())
        logic.apply_rules(context.scene)
        return {"FINISHED"}


class FRESING_OT_scheme_save(bpy.types.Operator):
    """Save the current materials of all groups as a paint scheme"""

    bl_idname = "fresing.scheme_save"
    bl_label = "Save paint scheme"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="Standard")

    def invoke(self, context, event):
        s = context.scene.fresing
        if 0 <= s.schemes_index < len(s.schemes):
            self.name = s.schemes[s.schemes_index].name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        s = context.scene.fresing
        logic.save_scheme(s, self.name.strip() or "Scheme")
        s.schemes_index = list(s.schemes.keys()).index(self.name.strip() or "Scheme")
        return {"FINISHED"}


class FRESING_OT_scheme_apply(bpy.types.Operator):
    """Switch all groups to this paint scheme"""

    bl_idname = "fresing.scheme_apply"
    bl_label = "Use scheme"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        s = context.scene.fresing
        name = self.name or (s.schemes[s.schemes_index].name if 0 <= s.schemes_index < len(s.schemes) else "")
        n = logic.apply_scheme(context.scene, name)
        self.report({"INFO"}, f"Scheme '{name}' applied to {n} groups")
        return {"FINISHED"}


class FRESING_OT_scheme_remove(bpy.types.Operator):
    bl_idname = "fresing.scheme_remove"
    bl_label = "Delete scheme"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.schemes_index < len(s.schemes):
            s.schemes.remove(s.schemes_index)
            s.schemes_index = max(0, s.schemes_index - 1)
        return {"FINISHED"}


def _plain(value):
    """Blender property value -> JSON-friendly value (colours become lists)."""
    if isinstance(value, (str, bool, int, float)):
        return value
    try:
        return [float(v) for v in value]
    except TypeError:
        return value


def _template_from_scene(scene) -> Template:
    s = scene.fresing
    t = Template(name=os.path.splitext(os.path.basename(bpy.data.filepath))[0] or "Template")
    t.rules = logic.rules_from_scene(s)
    current = Scheme("Current", {g.name: GroupLook(g.material, g.color) for g in s.groups})
    t.schemes = [current] + [Scheme(sc.name, {lk.group: GroupLook(lk.material, lk.color) for lk in sc.looks})
                             for sc in s.schemes]
    t.background = {k: _plain(getattr(s, k)) for k in (
        "background", "background_color", "lighting", "light_rotation", "light_strength", "sun_elevation",
        "exposure", "floor", "floor_use_own_color", "floor_color")}
    t.output = {k: getattr(s, k) for k in ("out_format", "out_resolution", "out_orientation", "out_dpi",
                                          "out_use_bleed", "out_bleed_mm", "out_file_type", "quality")}
    return t


def apply_template(scene, t: Template) -> None:
    s = scene.fresing
    logic.load_rules_into_scene(s, t.rules)
    for sch in t.schemes:
        if sch.name == "Current":
            for gname, look in sch.looks.items():
                g = logic.ensure_group(s, gname)
                g.material, g.color = look.material, look.color
            continue
        target = s.schemes.get(sch.name) or s.schemes.add()
        target.name = sch.name
        target.looks.clear()
        for gname, look in sch.looks.items():
            lk = target.looks.add()
            lk.group, lk.material, lk.color = gname, look.material, look.color
    live = s.live_update
    s.live_update = False
    for k, v in t.background.items():
        try:
            setattr(s, k, v)
        except (AttributeError, TypeError, ValueError):
            pass
    for k, v in t.output.items():
        try:
            setattr(s, k, v)
        except (AttributeError, TypeError, ValueError):
            pass
    s.live_update = live
    logic.apply_rules(scene)
    world.apply(scene, s)


class FRESING_OT_template_export(bpy.types.Operator, ExportHelper):
    """Save rules, groups, paint schemes, background and output settings as a template"""

    bl_idname = "fresing.template_export"
    bl_label = "Save template"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        _template_from_scene(context.scene).save(self.filepath)
        self.report({"INFO"}, f"Template saved: {self.filepath}")
        return {"FINISHED"}


class FRESING_OT_template_import(bpy.types.Operator, ImportHelper):
    """Load a template: rules, groups, paint schemes, background and output settings"""

    bl_idname = "fresing.template_import"
    bl_label = "Load template"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            t = Template.load(self.filepath)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, f"Could not load template: {exc}")
            return {"CANCELLED"}
        apply_template(context.scene, t)
        self.report({"INFO"}, f"Template loaded: {t.name}")
        return {"FINISHED"}


class FRESING_OT_pick_ral(bpy.types.Operator):
    """Pick a RAL colour for the active group"""

    bl_idname = "fresing.pick_ral"
    bl_label = "RAL colour"
    bl_property = "code"

    def _items(self, context):
        from ..core import ral
        return [(c, f"RAL {c} {n}", h) for c, n, h in ral.RAL_CLASSIC]

    code: EnumProperty(items=_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        s = context.scene.fresing
        if 0 <= s.groups_index < len(s.groups):
            s.groups[s.groups_index].color = f"RAL {self.code}"
        return {"FINISHED"}


# =============================================================================
# Background, cameras, render
# =============================================================================


def _library_hdris():
    from . import prefs
    folder = prefs.library_dir("HDRI")
    found = []
    if folder:
        for dirpath, _dirs, files in os.walk(folder):
            for f in sorted(files):
                if f.lower().endswith((".exr", ".hdr")):
                    full = os.path.join(dirpath, f)
                    found.append((full, os.path.splitext(os.path.relpath(full, folder))[0].replace(os.sep, " / ")))
    return found


class FRESING_OT_pick_hdri(bpy.types.Operator):
    """Pick a 360° photo from the shared library (Preferences > Add-ons > Fresing Render)"""

    bl_idname = "fresing.pick_hdri"
    bl_label = "360° photo from library"
    bl_property = "path"

    def _items(self, context):
        items = [(p, label, p) for p, label in _library_hdris()]
        return items or [("NONE", "No library set (Preferences > Fresing Render)", "")]

    path: EnumProperty(items=_items)
    target: EnumProperty(items=[("BACKGROUND", "Background", ""), ("LIGHT", "Light", "")],
                         default="BACKGROUND", options={"SKIP_SAVE"})

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if self.path == "NONE":
            self.report({"WARNING"}, "Set the shared library folder in the add-on preferences")
            return {"CANCELLED"}
        s = context.scene.fresing
        if self.target == "LIGHT":
            s.light_hdri_path = self.path
        else:
            s.hdri_path = self.path
        return {"FINISHED"}


class FRESING_OT_world_apply(bpy.types.Operator):
    """Rebuild background, light and floor"""

    bl_idname = "fresing.world_apply"
    bl_label = "Update background"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        world.apply(context.scene, context.scene.fresing)
        return {"FINISHED"}


class FRESING_OT_camera_add(bpy.types.Operator):
    """Add a camera that frames the whole model"""

    bl_idname = "fresing.camera_add"
    bl_label = "Add camera"
    bl_options = {"REGISTER", "UNDO"}

    view: EnumProperty(name="View", items=[(k, v[0], "") for k, v in cameras.VIEWS.items()] +
                       [("VIEW", "Current view", "Camera where you are looking now")], default="ISO")
    lens: IntProperty(name="Lens (mm)", default=50, min=10, max=300)

    def execute(self, context):
        scene = context.scene
        render.apply_output(scene, scene.fresing)
        if self.view == "VIEW":
            ob = cameras.add_from_view(context, "My view")
            if ob is None:
                self.report({"ERROR"}, "No 3D view found")
                return {"CANCELLED"}
        else:
            ob = cameras.add_camera(scene, self.view, float(self.lens))
        scene.camera = ob
        return {"FINISHED"}


class FRESING_OT_camera_activate(bpy.types.Operator):
    """Render from this camera and look through it"""

    bl_idname = "fresing.camera_activate"
    bl_label = "Use camera"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is None:
            return {"CANCELLED"}
        context.scene.camera = ob
        area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None) if context.screen else None
        if area is not None:
            area.spaces.active.region_3d.view_perspective = "CAMERA"
        return {"FINISHED"}


class FRESING_OT_camera_fit(bpy.types.Operator):
    """Move the active camera so the visible model fills the frame"""

    bl_idname = "fresing.camera_fit"
    bl_label = "Fit model in frame"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cam = context.scene.camera
        if cam is None:
            return {"CANCELLED"}
        render.apply_output(context.scene, context.scene.fresing)
        cameras.fit(cam, context.scene)
        return {"FINISHED"}


class FRESING_OT_camera_remove(bpy.types.Operator):
    bl_idname = "fresing.camera_remove"
    bl_label = "Delete camera"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"SKIP_SAVE"})

    def execute(self, context):
        ob = bpy.data.objects.get(self.name)
        if ob is not None:
            bpy.data.objects.remove(ob)
        return {"FINISHED"}


class FRESING_OT_camera_dof(bpy.types.Operator):
    """Turn background blur (depth of field) on or off for the active camera"""

    bl_idname = "fresing.camera_dof"
    bl_label = "Background blur"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cam = context.scene.camera
        if cam is None:
            return {"CANCELLED"}
        cameras.set_dof(cam, context.scene, not cam.data.dof.use_dof, cam.data.dof.aperture_fstop or 5.6)
        return {"FINISHED"}


class FRESING_OT_preview(bpy.types.Operator):
    """Toggle a live render preview in the viewport"""

    bl_idname = "fresing.preview"
    bl_label = "Live preview"

    def execute(self, context):
        scene = context.scene
        render.apply_quality(scene, "draft", scene.fresing.use_gpu)
        world.apply(scene, scene.fresing)
        area = next((a for a in context.screen.areas if a.type == "VIEW_3D"), None) if context.screen else None
        if area is None:
            return {"CANCELLED"}
        shading = area.spaces.active.shading
        shading.type = "SOLID" if shading.type == "RENDERED" else "RENDERED"
        scene.cycles.preview_samples = 64
        scene.cycles.use_preview_denoising = True
        return {"FINISHED"}


_PENDING_RENDER: dict = {}


def _on_render_done(scene, *args):
    info = _PENDING_RENDER.pop("job", None)
    try:
        bpy.app.handlers.render_complete.remove(_on_render_done)
    except ValueError:
        pass
    try:
        bpy.app.handlers.render_cancel.remove(_on_render_cancel)
    except ValueError:
        pass
    if not info:
        return
    s = scene.fresing
    img = bpy.data.images.get("Render Result")
    if img is None:
        return
    tmp = info["tmp"]
    img.save_render(tmp, scene=scene)
    final = info["path"]
    if s.background == "COLOR":
        col = tuple(render.linear_to_srgb(c) for c in s.background_color[:3])
        render._composite_over_color(tmp, col, final, s.out_file_type)
        os.remove(tmp)
        scene.render.film_transparent = False
    elif s.out_file_type == "JPEG":
        render._composite_over_color(tmp, (1, 1, 1), final, "JPEG")
        os.remove(tmp)
    else:
        os.replace(tmp, final)
    s.last_message = f"Saved {final}"
    print("Fresing Render: saved", final)


def _on_render_cancel(scene, *args):
    _PENDING_RENDER.pop("job", None)
    for h, lst in ((_on_render_done, bpy.app.handlers.render_complete),
                   (_on_render_cancel, bpy.app.handlers.render_cancel)):
        try:
            lst.remove(h)
        except ValueError:
            pass
    if scene.fresing.background == "COLOR":
        scene.render.film_transparent = False


class FRESING_OT_render(bpy.types.Operator):
    """Render the active camera and save the image"""

    bl_idname = "fresing.render"
    bl_label = "Render image"

    quality: EnumProperty(items=[("draft", "Draft", ""), ("preview", "Preview", ""), ("final", "Final", ""),
                                 ("best", "Best", ""), ("SETTING", "From settings", "")], default="SETTING")

    def execute(self, context):
        scene = context.scene
        s = scene.fresing
        if scene.camera is None:
            self.report({"ERROR"}, "Add a camera first")
            return {"CANCELLED"}
        quality = s.quality if self.quality == "SETTING" else self.quality
        if bpy.app.background or context.window is None:  # no UI / scripted
            info = render.render_still(scene, s, quality)
            self.report({"INFO"}, f"Saved {info['path']} ({info['seconds']} s, {info['device']})")
            return {"FINISHED"}
        render.apply_output(scene, s)
        device = render.apply_quality(scene, quality, s.use_gpu)
        world.apply(scene, s)
        path = render.output_path(scene, s, "" if quality == "final" else f"_{quality}")
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        if s.background == "COLOR":
            scene.render.film_transparent = True
        _PENDING_RENDER["job"] = {"path": path, "tmp": path + ".tmp.png"}
        if _on_render_done not in bpy.app.handlers.render_complete:
            bpy.app.handlers.render_complete.append(_on_render_done)
        if _on_render_cancel not in bpy.app.handlers.render_cancel:
            bpy.app.handlers.render_cancel.append(_on_render_cancel)
        s.last_message = f"Rendering on {device}..."
        bpy.ops.render.render("INVOKE_DEFAULT")
        return {"FINISHED"}


class FRESING_OT_open_folder(bpy.types.Operator):
    """Open the folder where renders are saved"""

    bl_idname = "fresing.open_folder"
    bl_label = "Open render folder"

    def execute(self, context):
        s = context.scene.fresing
        folder = bpy.path.abspath(s.out_folder) if s.out_folder else render.default_output_dir()
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)  # noqa: S606 - opening a folder for the user
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return {"FINISHED"}


CLASSES = (
    FRESING_OT_tree_refresh, FRESING_OT_select_subassembly, FRESING_OT_toggle_lock, FRESING_OT_toggle_hide,
    FRESING_OT_hide_selected, FRESING_OT_show_all, FRESING_OT_exclude_selected, FRESING_OT_restore_excluded,
    FRESING_OT_select_small,
    FRESING_OT_apply_rules, FRESING_OT_group_add, FRESING_OT_group_remove, FRESING_OT_group_select,
    FRESING_OT_group_assign, FRESING_OT_group_unassign, FRESING_OT_rule_add, FRESING_OT_rule_remove,
    FRESING_OT_rule_move, FRESING_OT_rules_reset, FRESING_OT_scheme_save, FRESING_OT_scheme_apply,
    FRESING_OT_scheme_remove, FRESING_OT_template_export, FRESING_OT_template_import, FRESING_OT_pick_ral,
    FRESING_OT_pick_hdri, FRESING_OT_world_apply, FRESING_OT_camera_add, FRESING_OT_camera_activate, FRESING_OT_camera_fit,
    FRESING_OT_camera_remove, FRESING_OT_camera_dof, FRESING_OT_preview, FRESING_OT_render,
    FRESING_OT_open_folder,
)
