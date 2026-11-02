"""Add-on preferences: where the shared library lives."""

from __future__ import annotations

import os

import bpy
from bpy.props import StringProperty

ADDON_ID = __package__.rsplit(".", 1)[0]


class FRESING_AP_prefs(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    library_path: StringProperty(
        name="Shared library", subtype="DIR_PATH",
        description="Folder with backgrounds (HDRI) and templates, e.g. on the network. A local copy also works")
    default_template: StringProperty(
        name="Default template", subtype="FILE_PATH",
        description="Template (.json) applied to every new import: rules, groups, paint schemes, background")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "library_path")
        layout.prop(self, "default_template")
        layout.label(text="Library layout: <library>/HDRI/*.exr|*.hdr and <library>/Templates/*.json")


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
