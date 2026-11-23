"""Fresing Settings > Locations and Exports (task 0272), and the "Save to" row of the outputs.

Locations: the note when the own folders were made switched off, the set-up files (add, look again, save as, and per
set-up Show changes / Edit / Remove), "Different from standard", then one fold per kind with its folders – badge, path,
reachable or not, and for your own ones on / off, up / down, remove. Exports: the export places, the default, "Also
save a copy to".
"""

from __future__ import annotations

import os

from ..core import locations as L
from . import locations
from .ui import fold, gap, hint, wrap


def _reach_text(loc) -> str:
    if not loc.on:
        return "switched off"
    if loc.reach is None:
        return "looking at it…"
    if loc.reach is False:
        return "cannot be reached now (network, VPN?) – its items are left out"
    return ""


def draw_locations(layout, context) -> None:
    st = locations.state()
    for note in locations.notes():
        wrap(layout, context, note, icon="ERROR", alert=True)
    if st.get("note_off"):
        box = layout.box()
        wrap(box, context, locations.NOTE_OFF + ".", icon="INFO")
        row = box.row(align=True)
        row.operator("fresing.loc_mine_all_on", icon="CHECKBOX_HLT")
        row.operator("fresing.loc_note_ok", text="Keep them off", icon="X")

    layout.label(text="Set-up files", icon="PACKAGE")
    sets = locations.setups()
    box = layout.box()
    if not sets:
        hint(box, context, "None: a set-up file (.frsetup) from your company or department brings its folders, "
                           "export places and settings in one go.")
    for s, _base, _u in sets:
        e = locations.entry(s.id) or {}
        col = box.column(align=True)
        row = col.row(align=True)
        row.label(text=f"{s.title()}  –  {s.name}", icon="LINKED" if e.get("mode") == "link" else "FILE")
        row.operator("fresing.loc_setup_changes", text="", icon="FILE_REFRESH").sid = s.id
        row.operator("fresing.loc_setup_edit", text="", icon="GREASEPENCIL").sid = s.id
        row.operator("fresing.loc_setup_remove", text="", icon="X").sid = s.id
        where = ("linked: " + (e.get("source") or "")) if e.get("mode") == "link" else "copied into the app"
        sub = col.row()
        sub.active = False
        sub.label(text=where + (f"  ·  {s.date}" if s.date else ""))
        for n in s.notes:
            wrap(col, context, n, icon="INFO")
    for u in st["updated"][-2:]:
        wrap(box, context, f"{u.get('text', '')} ({u.get('at', '')})", icon="FILE_REFRESH")
    row = layout.row(align=True)
    row.operator("fresing.loc_setup_add", icon="IMPORT")
    row.operator("fresing.loc_setup_save", icon="EXPORT")
    row.operator("fresing.loc_reload", text="", icon="FILE_REFRESH")

    gap(layout)
    body = fold(layout, "fr_loc_diff", "Different from standard", "MODIFIER")
    if body is not None:
        rows = locations.differences()
        if not rows:
            hint(body, context, "Everything is as the app comes.")
        for r in rows:
            row = body.row(align=True)
            row.label(text=f"{r.what}: {r.value}")
            right = row.row(align=True)
            right.alignment = "RIGHT"
            right.label(text=r.source)
            if r.own:
                right.operator("fresing.loc_back", text="", icon="LOOP_BACK").key = r.key

    gap(layout)
    layout.label(text="Folders", icon="FILE_FOLDER")
    hint(layout, context, "Each list in the app shows what all these folders hold, with a badge of where it comes "
                          "from. The top folder you can write to is where new things are saved.")
    for k in L.KINDS:
        locs = locations.folders(k.key, include_off=True)
        bad = sum(1 for x in locs if x.on and x.reach is False)
        title = f"{k.title}  ({len([x for x in locs if x.on])})" + ("  – one cannot be reached" if bad else "")
        body = fold(layout, "fr_loc_" + k.key, title, "FILE_FOLDER")
        if body is None:
            continue
        if k.note:
            hint(body, context, k.note + ".")
        for loc in locs:
            col = body.column(align=True)
            row = col.row(align=True)
            row.active = bool(loc.on and loc.reach)
            if loc.level == "mine":
                op = row.operator("fresing.loc_folder_on", text="", emboss=False,
                                  icon="CHECKBOX_HLT" if loc.on else "CHECKBOX_DEHLT")
                op.kind, op.index, op.on = k.key, loc.index, not loc.on
            row.label(text=f"{loc.badge}{' (inside the set-up)' if loc.packed else ''}: {loc.path}")
            right = row.row(align=True)
            right.alignment = "RIGHT"
            right.operator("fresing.loc_show", text="", icon="FILEBROWSER").path = loc.path
            if loc.level == "mine":
                for icon, step in (("TRIA_UP", -1), ("TRIA_DOWN", 1)):
                    op = right.operator("fresing.loc_folder_move", text="", icon=icon)
                    op.kind, op.index, op.step = k.key, loc.index, step
                op = right.operator("fresing.loc_folder_remove", text="", icon="X")
                op.kind, op.index = k.key, loc.index
            why = _reach_text(loc)
            if why:
                sub = col.row()
                sub.active = False
                sub.alert = loc.reach is False and loc.on
                sub.label(text="    " + why)
        body.operator("fresing.loc_folder_add", icon="ADD").kind = k.key


def draw_exports(layout, context) -> None:
    ex = locations.state()["exports"]
    default = locations.default_place()
    layout.label(text="Export places", icon="EXPORT")
    hint(layout, context, "Where pictures, videos and 3D pages go. Each output's Save to picks one; the default is "
                          "used unless a project picks another.")
    box = layout.box()
    for p in locations.places():
        row = box.row(align=True)
        op = row.operator("fresing.loc_place_default", text="", icon="RADIOBUT_ON" if p.key == default
                          else "RADIOBUT_OFF", emboss=False)
        op.place = p.key
        row.label(text=f"{p.name}  ·  {p.badge}")
        right = row.row(align=True)
        right.alignment = "RIGHT"
        if p.path:
            right.operator("fresing.loc_show", text="", icon="FILEBROWSER").path = p.path
        if p.level == "mine":
            right.operator("fresing.loc_place_remove", text="", icon="X").name = p.name
        if p.path:
            sub = box.row()
            sub.active = False
            sub.label(text="      " + p.path + ("\\<project>" if p.project_sub else ""))
    layout.operator("fresing.loc_place_add", icon="ADD")
    gap(layout)
    row = layout.row(align=True)
    row.operator("fresing.loc_also", text="", icon="CHECKBOX_HLT" if ex["also"] else "CHECKBOX_DEHLT",
                 emboss=False).on = not ex["also"]
    row.label(text="Also save a copy to")
    sub = row.row(align=True)
    sub.enabled = ex["also"]
    sub.operator_menu_enum("fresing.loc_also_to", "place", text=locations.also_name() or "(pick a place)")
    hint(layout, context, "The copy is made after the output is saved: a still, a video from the queue, a 3D page.")


def draw_save_to(layout, context, scene) -> None:
    """The "Save to: [place ▾]" row every output shows (render, queue, web 3D)."""
    s = scene.fresing
    row = layout.row(align=True)
    row.label(text="Save to")
    if s.out_folder:
        row.label(text="Own folder: " + os.path.basename(os.path.normpath(s.out_folder)), icon="FILE_FOLDER")
    else:
        row.operator_menu_enum("fresing.out_place", "place", text=locations.place_name(scene), icon="EXPORT")
    also = locations.also_name() if locations.state()["exports"]["also"] else ""
    if also:
        sub = layout.row()
        sub.active = False
        sub.label(text=f"Also a copy to {also}")
