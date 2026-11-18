"""Add-on preferences: where the shared library lives, rule sets, update checks."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, StringProperty

ADDON_ID = __package__.rsplit(".", 1)[0]


class FRESING_AP_prefs(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    library_path: StringProperty(
        name="Shared library", subtype="DIR_PATH",
        description="Folder with backgrounds (HDRI), templates, rule sets, logos and stickers, e.g. on the network. "
                    "A local copy also works")
    default_template: StringProperty(
        name="Default template", subtype="FILE_PATH",
        description="Template (.json) applied to every new import: rules, groups, paint schemes, background")
    default_rule_set: StringProperty(
        name="Default rule set", default="Standard",
        description="The rule set every new project starts with (3 Looks). A default template that names "
                    "a rule set wins over this")

    check_updates: BoolProperty(
        name="Check for updates at start-up", default=True,
        description="Look on GitHub for a newer Fresing Render a few seconds after the app starts. When there "
                    "is one, the Fresing tab shows \"Update available\" with what's new and an Update now button. "
                    "Needs Blender's online access (System > Network)")

    # ---- the side panel (task 0062) ----
    default_workspace: StringProperty(
        name="Workspace for new projects", default="All functions",
        description="The workspace a new project starts in, and the one a project from before workspaces opens in "
                    "(with everything it uses shown). Pick it in the Fresing tab: Workspace > Use for new projects")
    keep_sections: BoolProperty(
        name="Keep sections as I left them", default=False,
        description="Off: sections 1 to 7 start folded every time the app starts or a project opens, so the side "
                    "panel is calm and each title shows its state. On: a project opens with the sections and "
                    "sub-panels that were open when it was saved")
    keep_howto: BoolProperty(
        name="Keep How it works open", default=False,
        description="The numbered how-to of a function folds away by itself once the project has one (a cut, a "
                    "cylinder, a cable). Tick this to keep every How it works open")
    knows_ctrl_click: BoolProperty(
        default=False, options={"HIDDEN"},
        description="You have used Ctrl+click on a section title: the grey hint about it is no longer shown")
    lesson_button: EnumProperty(
        name="Button", default="C",
        description="How a lesson shows the button to press. Try both and keep the one you find clearer",
        items=[("C", "Spotlight", "The rest of the side panel is dimmed, the button stays clear with a thin outline"),
               ("D", "Bar and tint", "A bar on the button's left edge and the button tinted, breathing slowly")])
    lesson_section: EnumProperty(
        name="Folded section", default="5",
        description="How a lesson shows a folded section or sub-panel that must be opened",
        items=[("5", "Title in colour", "The title in the colour and a fold arrow that nods slowly"),
               ("4", "Bar", "A bar on the left edge of the title row")])
    lesson_part: EnumProperty(
        name="Part", default="3",
        description="How a lesson shows the part to click in the 3D view",
        items=[("3", "Rest faded", "Everything else is faded, the part stays clear in its own colour"),
               ("1", "Glow", "The part is covered in a see-through glow that breathes slowly")])
    lesson_colour: FloatVectorProperty(
        name="Colour", subtype="COLOR_GAMMA", size=3, min=0.0, max=1.0, default=(0.278, 0.608, 0.161),
        description="The colour of the lesson highlight (Fresing Green to start with)")

    hover_highlight: BoolProperty(
        name="Highlight what is under the mouse when picking", default=True,
        description="While you click on the model to pick something (an axis for a joint, a cylinder's pins, the sharp "
                    "spot, a label's point, a decal, a trail point, the CNC zero, a nozzle, a tool-changer pocket), the "
                    "face a click would use lights up in magenta with a short note, before you click. Switch it off "
                    "if it ever gets in the way; the clicks work the same")

    lifting_understood: BoolProperty(
        name="Lifting plans: planning aid understood", default=False,
        description="You ticked 'I understand' the first time you opened 8 Lifting plan: the app checks a lifting plan "
                    "against the data entered in it, not against the real equipment, ground or load")

    live_preview: BoolProperty(
        name="Live preview was on", default=False, options={"HIDDEN"},
        description="Remembers the last choice of the Live preview button (5 Scene & Render), so the test tour and "
                    "the demo project open with it on or off as you left it")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "library_path")
        layout.prop(self, "default_template")
        row = layout.row(align=True)
        row.label(text="Default rule set")
        row.operator_menu_enum("fresing.rule_set_default", "name", text=self.default_rule_set or "Standard",
                               icon="FILTER")
        layout.label(text="Library layout: <library>/HDRI/*.exr|*.hdr, <library>/Templates/*.json, "
                          "<library>/Rule sets/*.json, <library>/Logos/*.png and <library>/Stickers/*.png")
        layout.prop(self, "hover_highlight")
        box = layout.box()
        box.label(text="Side panel", icon="MENU_PANEL")
        row = box.row(align=True)
        row.label(text="Workspace for new projects")
        row.operator_menu_enum("fresing.workspace_default", "name", text=self.default_workspace or "All functions",
                               icon="WORKSPACE")
        box.prop(self, "keep_sections")
        box.prop(self, "keep_howto")
        box = layout.box()
        box.label(text="Lesson highlight", icon="LIGHT")
        row = box.row(align=True)
        row.prop(self, "lesson_button")
        row.prop(self, "lesson_section")
        row = box.row(align=True)
        row.prop(self, "lesson_part")
        row.prop(self, "lesson_colour")
        draw_updates(layout, self)


def draw_updates(layout, p) -> None:
    """The "Updates" box of the preferences: switch, Check now, address, last result."""
    from .. import __version__
    from . import updates
    box = layout.box()
    box.label(text=f"Updates – installed version {__version__}", icon="FILE_REFRESH")
    row = box.row()
    row.prop(p, "check_updates")
    row.operator("fresing.update_check", text="Check now", icon="FILE_REFRESH")
    if not bpy.app.online_access:
        box.label(text="Blender's online access is off (System > Network): no update checks", icon="ERROR")
    url, source = updates.index_url()
    box.label(text=f"Update address: {url}" + ("" if source == "GitHub" else f"  (from {source})"))
    state = updates._check.get("state")
    if state == "available":
        box.label(text=f"Update available: {updates._check.get('version')} – Update now in the Fresing tab",
                  icon="IMPORT")
    elif state == "none":
        box.label(text="You have the newest version", icon="CHECKMARK")
    elif state == "error":
        box.label(text="Last check: " + updates._check.get("message", ""), icon="ERROR")


def get() -> FRESING_AP_prefs | None:
    addon = bpy.context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None


def default_template_path() -> str:
    p = get()
    if p and p.default_template:
        path = bpy.path.abspath(p.default_template)
        if os.path.isfile(path):
            return path
    return ""


def library_dir(sub: str = "") -> str:
    p = get()
    if p and p.library_path:
        path = os.path.join(bpy.path.abspath(p.library_path), sub)
        if os.path.isdir(path):
            return path
    return ""


CLASSES = (FRESING_AP_prefs,)
