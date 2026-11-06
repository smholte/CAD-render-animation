"""Add-on preferences: where the shared library lives, rule sets, update checks."""

from __future__ import annotations

import os

import bpy
from bpy.props import BoolProperty, StringProperty

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
