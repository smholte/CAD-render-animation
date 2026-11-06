"""Operators for the brand kit (panel 5 Scene & Render, task 0018)."""

from __future__ import annotations

import bpy
from bpy.props import StringProperty

from ..core import brand
from . import video


class FRESING_OT_brand_save(bpy.types.Operator):
    """Saves this brand kit (logo, colours, font, contact line) in the shared library under the name above.
    Other projects and colleagues can then load it with 'Load a kit'. An older kit of the same name is replaced"""
    bl_idname = "fresing.brand_save"
    bl_label = "Save kit"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.fresing.brand_name.strip())

    def execute(self, context):
        s = context.scene.fresing
        folder, _shared, problem = video.kit_folder()
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        kit = video.kit_from_settings(s)
        source = bpy.path.abspath(s.brand_logo) if s.brand_logo else ""
        try:
            stored = brand.save_kit(folder, kit, source)
        except (ValueError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        s.brand_logo = brand.logo_path(folder, stored) or s.brand_logo
        self.report({"INFO"}, f"Brand kit '{stored.name}' saved")
        return {"FINISHED"}


class FRESING_OT_brand_load(bpy.types.Operator):
    """Fills in the brand kit from one saved in the library: its logo, colours, font and contact line.
    This project keeps its own copy of the settings"""
    bl_idname = "fresing.brand_load"
    bl_label = "Load a kit"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        folder, _shared, problem = video.kit_folder()
        kit = brand.load_kit(folder, self.name)
        if kit is None:
            self.report({"ERROR"}, problem or f"Brand kit '{self.name}' cannot be read")
            return {"CANCELLED"}
        video.load_into_settings(context.scene.fresing, folder, kit)
        self.report({"INFO"}, f"Brand kit '{kit.name}' loaded")
        return {"FINISHED"}


class FRESING_OT_brand_delete(bpy.types.Operator):
    """Deletes the kit with the name above from the library (its logo copy too). This project keeps its settings"""
    bl_idname = "fresing.brand_delete"
    bl_label = "Delete from library"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        folder, _shared, problem = video.kit_folder()
        name = context.scene.fresing.brand_name.strip()
        return bool(name) and not problem and brand.load_kit(folder, name) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        folder, _shared, problem = video.kit_folder()
        name = context.scene.fresing.brand_name.strip()
        if problem or not brand.delete_kit(folder, name):
            self.report({"ERROR"}, problem or "Nothing to delete")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Brand kit '{name}' deleted from the library")
        return {"FINISHED"}


class FRESING_MT_brand_kits(bpy.types.Menu):
    bl_label = "Load a kit"
    bl_description = "The brand kits in the shared library. Pick one to fill in the logo, colours, font and contact line"

    def draw(self, context):
        layout = self.layout
        folder, _shared, problem = video.kit_folder()
        kits = brand.list_kits(folder)
        if problem:
            layout.label(text=problem, icon="ERROR")
        elif not kits:
            layout.label(text="No saved kits yet: fill in a kit and press Save kit", icon="INFO")
        for kit in kits:
            layout.operator("fresing.brand_load", text=kit.name, icon="BOOKMARKS").name = kit.name


CLASSES = (FRESING_OT_brand_save, FRESING_OT_brand_load, FRESING_OT_brand_delete, FRESING_MT_brand_kits)
