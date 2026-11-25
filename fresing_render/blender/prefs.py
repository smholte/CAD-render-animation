"""Add-on preferences: default template, rule set and workspace, update checks, … (the folders: locations.py)."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatVectorProperty, IntProperty, StringProperty

from ..core import places

ADDON_ID = __package__.rsplit(".", 1)[0]


class FRESING_AP_prefs(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    library_path: StringProperty(
        name="Shared library (before 0272)", subtype="DIR_PATH", options={"HIDDEN"},
        description="The one library folder of versions before task 0272. At the first start of a newer version it "
                    "becomes your own (Mine) folder for every kind in Fresing Settings > Locations; it is not used "
                    "after that")
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
        name="Workspace for new projects", default="",
        description="The workspace a new project starts in, and the one a project from before workspaces opens in "
                    "(with everything it uses shown). Empty: not chosen yet – new projects start in Essentials. "
                    "Pick it in the Fresing tab: Workspace > Use for new projects")
    workspace_stars: StringProperty(
        default="", options={"HIDDEN"},
        description="Task 0294: the workspaces you starred, in the order you starred them – they sit at the top of "
                    "the Workspace drop-down")
    keep_sections: BoolProperty(
        name="Keep sections as I left them", default=False,
        description=f"Off: sections 1 to {len(places.SECTIONS)} start folded every time the app starts or a project opens, so the side "
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
    lesson_play_on: BoolProperty(
        name="Play on", default=False,
        description="Show me goes on to the next step by itself after a short pause, instead of waiting for Next. "
                    "Remembered for your next lessons")
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

    # ---- automatic backups (task 0246) ----
    backups_on: BoolProperty(
        name="Make automatic backups", default=True,
        description="Saves a copy of the open project every few minutes while you work, in a folder Backups next to "
                    "the project (a project never saved: Documents\\Fresing Render\\Backups\\Unsaved projects). "
                    "Fresing > Restore a backup… puts one back. Untick it for none, e.g. on a very big project")
    backup_minutes: IntProperty(
        name="Every (minutes)", default=5, min=1, max=60,
        description="How often a backup is made while something changes. Nothing changed: no new file. Saving the "
                    "project yourself starts the time again")
    backup_keep: IntProperty(
        name="Keep the last", default=5, min=1, max=50,
        description="How many of the newest backups are kept; older ones are deleted, except one a day (below)")
    backup_days: IntProperty(
        name="One a day for (days)", default=7, min=0, max=60,
        description="Also keeps the newest backup of each of these last days (today counts as one). 0: only the "
                    "last backups above")

    # ---- project names (task 0291) ----
    new_project_name: EnumProperty(
        name="Name of a new project",
        items=(("model", "First model's name", "The first save of a new project proposes the name of the first model "
                "you imported (without an Inventor version like \" v8\"), in that model's folder"),
               ("empty", "Leave empty", "The first save of a new project proposes no name: you type one")),
        default="model",
        description="What the first save of a new project proposes as its file name. Save as on a saved project "
                    "always proposes its name with (1), (2) …")

    left_folded: BoolProperty(
        name="Left panel folded", default=False, options={"HIDDEN"},
        description="The left panel is folded to its narrow strip (Live preview, Build & play, Fresing Settings, the unfold "
                    "button)")
    left_width: IntProperty(
        name="Left panel width", default=240, min=120, max=600, options={"HIDDEN"},
        description="How wide the left panel opens again after it was folded (pixels at UI scale 1)")
    next_folded: BoolProperty(
        name="What's next folded", default=False, options={"HIDDEN"},
        description="What's next and Next to learn on the left panel are folded to their title row")
    make_open: BoolProperty(
        name="Make list open", default=False, options={"HIDDEN"},
        description="Make at the top of the Fresing panel shows the labelled list instead of the row of icons")

    live_preview: BoolProperty(
        name="Live preview was on", default=False, options={"HIDDEN"},
        description="Remembers the last choice of the Live preview button (top left), so the Learning hub and "
                    "the demo project open with it on or off as you left it")

    settings_tab: StringProperty(
        name="Settings tab", default="general", options={"HIDDEN"},
        description="The tab the Fresing Settings window opened on last time (it opens there again)")

    key_changes: StringProperty(
        name="Changed keys", default="", options={"HIDDEN"},
        description="Fresing's own keys you gave another key in Fresing Settings > Keys (task 0295: kept in the "
                    "settings file)")

    window_places: StringProperty(
        name="Window places", default="", options={"HIDDEN"},
        description="Where the app's own windows were and how big (Make, Fresing Settings, the function windows), "
                    "so each opens there again (task 0282: kept in the settings file)")

    def draw(self, context):
        """Task 0271: the settings live in the Fresing Settings window; this page only points there (the
        properties stay here, so old projects, scripts and saved preferences keep working)."""
        layout = self.layout
        layout.label(text="Fresing Render's settings are in their own window: Fresing > Settings…", icon="INFO")
        row = layout.row()
        row.scale_y = 1.3
        row.operator("fresing.settings", text="Open Fresing Settings", icon="PREFERENCES")


def draw_general(layout, p) -> None:
    """Settings > General (task 0271): template, rule set, workspace for new projects, hover, library folder.
    Task 0283: a line that the settings are kept by themselves, and a note when the settings file was damaged."""
    col = layout.column()
    try:
        from . import settings_store
        for note in settings_store.notes():
            row = col.row()
            row.alert = True
            row.label(text=note, icon="ERROR")
    except Exception:  # noqa: BLE001 - never break the settings page
        pass
    hint = col.row()
    hint.active = False
    hint.label(text="Your settings are kept for you: nothing to save", icon="CHECKMARK")
    col.separator()
    row = col.row()
    row.label(text="Folders for models, logos, rule sets …:", icon="FILE_FOLDER")
    row.operator("fresing.settings_tab", text="Locations").tab = "locations"
    col.separator()
    col.prop(p, "default_template")
    row = col.row(align=True)
    row.label(text="Default rule set")
    row.operator_menu_enum("fresing.rule_set_default", "name", text=p.default_rule_set or "Standard", icon="FILTER")
    row = col.row(align=True)
    row.label(text="Workspace for new projects")
    row.operator_menu_enum("fresing.workspace_default", "name", text=p.default_workspace or "Essentials (not chosen yet)",
                           icon="WORKSPACE")
    col.separator()
    row = col.row(align=True)
    row.label(text="Name of a new project")
    row.prop(p, "new_project_name", text="")
    col.separator()
    col.prop(p, "hover_highlight")


def draw_side_panel(layout, p) -> None:
    """Settings > Side panel (task 0271): how sections and How it works open."""
    col = layout.column()
    col.prop(p, "keep_sections")
    col.prop(p, "keep_howto")


def draw_lessons(layout, p) -> None:
    """Settings > Lessons (task 0271): how a lesson points at a button, a section and a part."""
    col = layout.column()
    col.label(text="Lesson highlight", icon="LIGHT")
    col.prop(p, "lesson_button")
    col.prop(p, "lesson_section")
    col.prop(p, "lesson_part")
    col.prop(p, "lesson_colour")
    col.separator()
    col.prop(p, "lesson_play_on")


def draw_backups(layout, p) -> None:
    """The "Backups" box of the preferences (task 0246): the switch, the three numbers, the folder's size."""
    box = layout.box()
    box.label(text="Automatic backups", icon="FILE_BACKUP")
    box.prop(p, "backups_on")
    row = box.column(align=True)
    row.active = p.backups_on
    row.prop(p, "backup_minutes")
    row.prop(p, "backup_keep")
    row.prop(p, "backup_days")
    try:
        from ..core import backups as core
        from . import backups
        found = backups.project_backups()
        if bpy.data.filepath:
            where = "the Backups folder next to this project"
        else:
            where = "Unsaved projects"
        box.label(text=f"{len(found)} backups of this project: {core.size_text(core.total_size(found))}")
        sub = box.row()
        sub.active = False
        sub.label(text=f"In {where}. Fresing > Restore a backup… puts one back")
    except Exception:  # noqa: BLE001 - never break the preferences
        pass


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
    """The first readable folder of a kind, named by its old sub-folder ("Templates", "HDRI" …) – task 0272: through
    Fresing Settings > Locations; kept for older callers."""
    from ..core import locations as L
    from . import locations
    k = L.BY_SUB.get(sub.casefold()) if sub else None
    return locations.first_path(k.key) if k else ""


CLASSES = (FRESING_AP_prefs,)
