"""Side panel: 5 Scene & Render > House from House Planner (task 0114). Same layout rules as ui.py: the steps top to
bottom, the main button big and blue, a state in the header."""

from __future__ import annotations

import os

import bpy

from ..core import words
from . import house_bake, house_import, lightbake, ops_house
from .ui import _Panel, header_status, primary, split_props, wrap

LIGHT_WORDS = {"LIVE": "Live only (nothing baked; snow, photos and videos only)",
               "SOFT": "Soft light baked, sun live", "ALL": "Everything baked"}
_EST: dict = {}                  # (scene, house file, mtime) -> estimate (read once, not at every redraw)


def _estimate(scene) -> dict | None:
    path = house_import.package_path(scene)
    try:
        key = (scene.name, path, os.path.getmtime(path), scene.cycles.device)
    except (OSError, AttributeError):
        return None
    if key not in _EST:
        _EST.clear()
        try:
            _EST[key] = house_bake.estimate(scene)
        except Exception:  # noqa: BLE001 - an estimate never breaks the panel
            _EST[key] = None
    return _EST[key]


class FRESING_PT_house(_Panel, bpy.types.Panel):
    bl_label = "House from House Planner"
    bl_parent_id = "FRESING_PT_scene"

    @classmethod
    def poll(cls, context):
        return house_import.has_house(context.scene)

    def draw_header(self, context):
        self.layout.label(icon="HOME")

    def draw_header_preset(self, context):
        rt = ops_house.runtime(context.scene)
        if rt.get("running"):
            header_status(self.layout, "baking")
        elif house_import.settings(context.scene).last_bake:
            header_status(self.layout, "baked")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        h = house_import.settings(scene)
        try:
            house = house_import.house(scene)
        except Exception as exc:  # noqa: BLE001 - files moved or broken: say so, offer the import
            wrap(layout, context, str(exc), icon="ERROR", alert=True)
            layout.operator("fresing.house_import", text="Import House Planner scene…", icon="IMPORT")
            return
        rec = house.recipe
        box = layout.box()
        box.label(text=house.title or house.id, icon="HOME")
        if house.version_name:
            box.label(text=f"Plan version: {house.version_name}", icon="BLANK1")
        box.label(text=words.plural(len(house.surfaces), "surface"), icon="BLANK1")

        # -- what House Planner asks for (read-only: it is set in House Planner's export dialog)
        layout.label(text="Light", icon="LIGHT_SUN")
        col = layout.column(align=True)
        col.label(text=LIGHT_WORDS.get(rec.light, rec.light), icon="BLANK1")
        col.label(text=f"Quality {rec.preset.capitalize()}: {rec.samples} samples, "
                       f"{rec.texels_per_m:g} texels per metre", icon="BLANK1")

        # -- seasons and moments, each with Preview
        layout.label(text="Moments to bake", icon="TIME")
        for season in rec.seasons:
            sub = layout.box()
            snow = f", snow {season.snow_cover:.0%}" if season.snow_cover > 0 else ""
            sub.label(text=f"{season.label or season.id} ({season.date}{snow})", icon="WORLD")
            for m in [m for m in rec.moments if m.season == season.id]:
                row = sub.row(align=True)
                el = m.elevation
                state = "night" if el < 0 else f"sun {el:.0f}°"
                row.label(text=f"{m.label or m.id}  {m.time}  ({state})",
                          icon="RADIOBUT_ON" if h.moment == m.id else "RADIOBUT_OFF")
                row.operator("fresing.house_preview", text="Preview", icon="HIDE_OFF").moment = m.id
        if rec.open_storeys:
            names = {s.id: s.name for s in house.storeys}
            layout.label(text="Also open from above: " + ", ".join(names.get(s, s) for s in rec.open_storeys),
                         icon="BLANK1")
        if rec.photos or rec.videos:
            layout.label(text=f"{words.plural(len(rec.photos), 'photo')}, {words.plural(len(rec.videos), 'video')}",
                         icon="IMAGE_DATA")

        # -- the bake
        rt = ops_house.runtime(scene)
        if rt.get("running"):
            layout.progress(factor=float(rt.get("progress", 0.0)), type="BAR", text=rt.get("text", "Baking"))
            layout.operator("fresing.house_cancel", text="Cancel", icon="CANCEL")
            return
        est = _estimate(scene)
        if est is not None and est["seconds"] > 0:
            where = "on the graphics card (estimate)" if est["gpu"] else "on this PC's processor"
            layout.label(text=f"Takes {lightbake.duration(est['seconds'])} {where}", icon="SORTTIME")
        primary(layout, "fresing.house_bake", "Bake and export…", "RENDER_STILL")
        wrap(layout, context, "Writes " + os.path.basename(house_bake.default_path(scene)) + " next to the project. "
             "Open it in House Planner.", icon="INFO")
        if h.last_bake:
            layout.label(text=h.last_text or os.path.basename(h.last_bake), icon="CHECKMARK")
            layout.operator("fresing.house_show", text="Show in Explorer", icon="FILE_FOLDER")
            lines = [x for x in h.last_problems.split("\n") if x.strip()]
            if lines:
                col = layout.column(align=True)
                col.label(text=words.plural(len(lines), "note") + " from the bake:", icon="INFO")
                for line in lines[:8]:
                    wrap(col, context, line, inset=1)
                if len(lines) > 8:
                    col.label(text=f"… and {len(lines) - 8} more", icon="BLANK1")


CLASSES = (FRESING_PT_house,)
__all__ = ["CLASSES", "split_props"]
