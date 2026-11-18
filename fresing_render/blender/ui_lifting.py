"""Side panel: 8 Lifting plan (task 0201) – Equipment, Load, Hook & capacity. Same layout rules as ui.py.

Nothing is worked out while drawing: the readout comes from ``lifting.readout`` (cached on a cheap key), the library
from ``lifting.library`` (read once until Refresh)."""

from __future__ import annotations

import os

import bpy

from ..core import lifting as core
from ..core.words import plural
from . import lifting
from .ui import _Panel, big, fold, gap, header_status, hint, primary, split_props, steps, wrap

STATUS_ICON = {core.OK: "STRIP_COLOR_04", core.AMBER: "STRIP_COLOR_02", core.RED: "STRIP_COLOR_01",
               core.NOT_CHECKED: "STRIP_COLOR_09"}
_PREVIEWS = {"coll": None}


def _t(kg: float) -> str:
    t = core.tonnes(kg)
    return f"{t:.2f} t" if t < 100 else f"{t:.1f} t"


def _icon_of(path: str) -> int:
    """The item's picture as an icon (loaded once)."""
    if not path or not os.path.isfile(path):
        return 0
    if _PREVIEWS["coll"] is None:
        import bpy.utils.previews
        _PREVIEWS["coll"] = bpy.utils.previews.new()
    coll = _PREVIEWS["coll"]
    if path not in coll:
        try:
            coll.load(path, path, "IMAGE")
        except Exception:  # noqa: BLE001
            return 0
    return coll[path].icon_id


def _ok(context) -> bool:
    return lifting.understood()


def _sample_line(layout, context):
    wrap(layout, context, core.SAMPLE_MARK, icon="ERROR", alert=True)


class FRESING_PT_lifting(_Panel, bpy.types.Panel):
    bl_label = "8  Lifting plan"
    bl_order = 7
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(icon="CON_ARMATURE")

    def draw_header_preset(self, context):
        L = context.scene.fresing.lifting
        if L.cranes or L.loads:
            header_status(self.layout, f"{plural(len(L.cranes), 'crane')} · {plural(len(L.loads), 'load')}", limit=20)

    def draw(self, context):
        layout = self.layout
        L = context.scene.fresing.lifting
        if not _ok(context):
            wrap(layout, context, core.PLANNING_AID, icon="INFO")
            gap(layout)
            primary(layout, "fresing.lifting_understand", "Start the Lifting plan…", "CHECKBOX_HLT")
            return
        wrap(layout, context, core.PLANNING_AID, icon="INFO")
        if any(c.builtin or _is_sample(c) for c in L.cranes):
            _sample_line(layout, context)
        gap(layout)
        steps(layout, context, ["Equipment: pick a crane, Place… and click where it stands; pick its pose and set-up",
                                "Load: select the parts to lift (or a box), check the mass and the CoG marker",
                                "Hook & capacity: Hook to here – the crane moves its hook there and shows the crane "
                                "use at that radius"],
              key="fr_how_lifting", used=bool(L.cranes))
        gap(layout)
        if L.cranes:
            primary(layout, "fresing.lifting_hook_here", "Hook to here", "TRACKER")
        else:
            primary(layout, "fresing.lifting_place", "Place a crane…", "IMPORT")
        if L.message:
            wrap(layout, context, L.message, icon="INFO")


def _is_sample(crane) -> bool:
    try:
        return lifting.item_at(crane.item_path).sample
    except Exception:  # noqa: BLE001
        return False


class FRESING_PT_lifting_equipment(_Panel, bpy.types.Panel):
    bl_label = "Equipment"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="OUTLINER_OB_ARMATURE")

    def draw_header_preset(self, context):
        c = lifting.active_crane(context.scene)
        header_status(self.layout, c.name if c else "none placed")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        L = scene.fresing.lifting
        if L.cranes:
            col = layout.column(align=True)
            for i, c in enumerate(L.cranes):
                row = col.row(align=True)
                op = row.operator("fresing.lifting_select", text=c.name + ("  (SAMPLE)" if c.builtin else ""),
                                  icon="OUTLINER_OB_ARMATURE", depress=i == L.crane_index)
                op.index = i
            c = lifting.active_crane(scene)
            if c is not None:
                _draw_crane(layout, context, scene, c)
            gap(layout, line=True)
        body = fold(layout, "fr_lifting_library", "Add a crane from the library", icon="ADD", closed=bool(L.cranes))
        if body is not None:
            _draw_library(body, context, L)


def _draw_crane(layout, context, scene, c):
    changed = lifting.file_changed(c)
    if changed:
        wrap(layout, context, changed, icon="ERROR", alert=True)
    gap(layout)
    poses = lifting.pose_names(c)
    if poses:
        layout.label(text="Pose")
        grid = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for p in poses:
            grid.operator("fresing.lifting_pose", text=p, depress=p == c.pose).pose = p
    vals = lifting.LR.setup_values(lifting.charts_of(c))
    if vals:
        gap(layout)
        layout.label(text="Set-up the chart is picked for")
        if "counterweight" in vals:
            col = split_props(layout)
            col.prop(c, "counterweight", text="Counterweight (t)")
            row = layout.row(align=True)
            for v in vals["counterweight"]:
                t = core.tonnes(v)
                op = row.operator("fresing.lifting_setup_value", text=f"{t:g} t",
                                  depress=abs(t - c.counterweight) < 1e-6)
                op.key, op.value = "counterweight", t
        if "outriggers" in vals:
            layout.prop(c, "spread_from_pose", text="Outrigger spread from the pose")
            if not c.spread_from_pose:
                col = split_props(layout)
                col.prop(c, "outriggers", text="Spread (m)")
            row = layout.row(align=True)
            for v in vals["outriggers"]:
                op = row.operator("fresing.lifting_setup_value", text=f"{v:g} m",
                                  depress=not c.spread_from_pose and abs(v - c.outriggers) < 1e-6)
                op.key, op.value = "outriggers", v
            if c.spread_from_pose:
                sp = lifting.setup(scene, c).get("outriggers")
                if sp is not None:
                    hint(layout, context, f"The pose gives {sp:.2f} m.")
    gap(layout)
    row = layout.row(align=True)
    row.operator("fresing.lifting_move", text="Move…", icon="ORIENTATION_GLOBAL")
    row.operator("fresing.lifting_remove", text="Remove", icon="TRASH")


def _draw_library(layout, context, L):
    items = lifting.library()
    picked = None
    for title, group in lifting.by_kind(items):
        layout.label(text=title)
        col = layout.column(align=True)
        for it in group:
            path = it.path or it.folder
            row = col.row(align=True)
            row.alert = not it.ok
            text = it.name + ("" if it.ok else "  – " + it.problems[0])
            row.operator("fresing.lifting_pick", text=text, depress=path == L.pick,
                         icon="OUTLINER_OB_ARMATURE" if it.ok else "ERROR").path = path
            if path == L.pick:
                picked = it
    row = layout.row(align=True)
    row.operator("fresing.lifting_library", text="Refresh", icon="FILE_REFRESH")
    row.operator_menu_enum("fresing.crane_setup", "kind", text="Set up a crane…", icon="PREFERENCES")  # task 0203
    if not lifting.user_folder():
        hint(layout, context, "Your own equipment: a folder 'Lifting equipment' in your library folder (Preferences).")
    if picked is not None:
        gap(layout)
        icon = _icon_of(picked.picture or "")
        if icon:
            layout.template_icon(icon_value=icon, scale=6.0)
        if picked.sample:
            wrap(layout, context, core.SAMPLE_PAGE_MARK, icon="ERROR", alert=True)
        big(layout, "fresing.lifting_place", f"Place {picked.name}…", icon="IMPORT")
        hint(layout, context, "Click where it stands (ground, deck or any surface); the mouse wheel turns it; Esc "
                              "cancels.")


class FRESING_PT_lifting_load(_Panel, bpy.types.Panel):
    bl_label = "Load"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="PACKAGE")

    def draw_header_preset(self, context):
        ld = lifting.active_load(context.scene)
        if ld is not None:
            header_status(self.layout, _t(lifting.load_mass(context.scene, ld)[0]))
        else:
            header_status(self.layout, "none")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        L = scene.fresing.lifting
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("fresing.lifting_load_selected", text="Use selected parts", icon="RESTRICT_SELECT_OFF")
        row.operator("fresing.lifting_box", text="Box…", icon="MESH_CUBE")
        if not L.loads:
            hint(layout, context, "Select the parts to lift in the 3D view or the Structure list, then Use selected "
                                  "parts. Or add a box of a size and mass you type.")
            return
        if len(L.loads) > 1:
            col = layout.column(align=True)
            for i, ld in enumerate(L.loads):
                col.operator("fresing.lifting_load_select", text=ld.name, icon="PACKAGE",
                             depress=i == L.load_index).index = i
        ld = lifting.active_load(scene)
        if ld is None:
            return
        gap(layout)
        n = len(lifting.load_parts(ld))
        layout.label(text=f"{ld.name}: " + ("a box" if ld.kind == "BOX" else plural(n, "part")), icon="PACKAGE")
        col = split_props(layout)
        if ld.kind == "PARTS":
            col.prop(ld, "mass_mode", text="Mass")
        if ld.kind == "BOX" or ld.mass_mode == "ENTERED":
            col.prop(ld, "mass_t", text="Mass (t)")
            col.prop(ld, "source", text="Source")
        else:
            col.label(text=f"{_t(ld.volume_mass)}  (estimate)")
        if ld.kind == "PARTS":
            body = fold(layout, "fr_lifting_volume", f"Volume {ld.volume:.3f} m³ x density = {_t(ld.volume_mass)}",
                        icon="MOD_PHYSICS", closed=True)
            if body is not None:
                c2 = split_props(body)
                for d in ld.densities:
                    c2.prop(d, "density", text=d.name)
                if ld.open_parts:
                    wrap(body, context, f"Not closed solids, their box was used: {ld.open_parts}", icon="ERROR")
        col = split_props(layout)
        col.prop(ld, "contingency", text="Contingency")
        _draw_gross(layout, context, scene, ld)
        gap(layout)
        cog = lifting.cog_world(ld)
        by_hand = lifting.cog_by_hand(ld)
        if cog is not None:
            col = layout.column(align=True)
            col.label(text="CoG " + ("set by hand" if by_hand else "computed"), icon="PIVOT_MEDIAN")
            col.label(text=f"x {cog[0]:.3f}  y {cog[1]:.3f}  z {cog[2]:.3f} m", icon="BLANK1")
        row = layout.row(align=True)
        row.operator("fresing.lifting_cog_move", text="Move", icon="ORIENTATION_GLOBAL")
        row.operator("fresing.lifting_cog_back", text="Back to computed", icon="LOOP_BACK")
        gap(layout)
        row = layout.row(align=True)
        row.operator("fresing.lifting_load_refresh", text="Work out again", icon="FILE_REFRESH")
        row.operator("fresing.lifting_load_remove", text="Remove", icon="TRASH")


def _draw_gross(layout, context, scene, ld):
    m, src = lifting.load_mass(scene, ld)
    c = lifting.active_crane(scene)
    hb = lifting.hook_block_kg(c) if c is not None else 0.0
    ro = lifting.readout(scene, c, ld) if c is not None else None
    includes = bool(getattr(getattr(ro, "chart", None), "includes_hook_block", False))
    g = lifting.LD.gross(m, ld.contingency, hb, includes)
    box = layout.box()
    col = box.column(align=True)
    col.label(text=f"Load {_t(m)} x {ld.contingency:.2f} = {_t(g.factored)}")
    col.label(text=f"   ({src})")
    col.label(text="Rigging 0 t (slings come later)")
    if c is not None:
        col.label(text=f"Hook block {_t(g.hook_block)}" + (" (in the chart)" if includes else ""))
    col.label(text=f"Gross load {_t(g.total)}", icon="FORCE_FORCE")


class FRESING_PT_lifting_hook(_Panel, bpy.types.Panel):
    bl_label = "Hook & capacity"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="TRACKER")

    def draw_header_preset(self, context):
        c = lifting.active_crane(context.scene)
        if c is None:
            header_status(self.layout, "no crane")
            return
        ro = lifting.readout(context.scene, c, lifting.active_load(context.scene))
        if isinstance(ro, str):
            header_status(self.layout, "–")
        elif ro.use is not None:
            header_status(self.layout, f"{ro.use * 100:.0f} %", icon=STATUS_ICON[ro.status],
                          alert=ro.status == core.RED)
        else:
            header_status(self.layout, "no chart", alert=True)

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        c = lifting.active_crane(scene)
        if c is None:
            wrap(layout, context, "No crane yet: place one under Equipment.", icon="INFO")
            return
        ld = lifting.active_load(scene)
        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("fresing.lifting_hook_here", text="Hook to here", icon="TRACKER")
        row.operator("fresing.lifting_hook_above", text="Above the load", icon="TRIA_UP_BAR")
        if ld is not None:
            col = split_props(layout)
            col.prop(ld, "clearance", text="Clearance")
        ro = lifting.readout(scene, c, ld)
        gap(layout)
        if isinstance(ro, str):
            wrap(layout, context, ro, icon="ERROR", alert=True)
            return
        box = layout.box()
        col = box.column(align=True)
        col.label(text=f"{c.name}")
        col.label(text=f"Radius {ro.radius:.2f} m · hook height {ro.height:.2f} m")
        line = f"Boom {ro.boom:.2f} m at {ro.boom_angle:.1f}°"
        if ro.jib:
            line += f" · jib {ro.jib:g} m at {ro.second_angle:.1f}° to the boom"
        elif ro.second_angle is not None:
            line += f" · knuckle {ro.second_angle:.1f}°"
        col.label(text=line)
        gap(layout)
        if ro.chart is not None:
            wrap(layout, context, ro.chart_note, icon="INFO")
        if ro.capacity is not None:
            col = layout.column(align=True)
            col.label(text=f"Chart row {ro.row:g} m (next longer radius)")
            col.label(text=f"Capacity {_t(ro.capacity)} · gross load {_t(ro.gross)}")
            row = layout.row()
            row.scale_y = 1.4
            row.alert = ro.status == core.RED
            row.label(text=f"Crane use {ro.use * 100:.0f} % – {ro.words}", icon=STATUS_ICON[ro.status])
        else:
            row = layout.row()
            row.alert = True
            row.label(text=f"Gross load {_t(ro.gross)}: {ro.words}", icon=STATUS_ICON[core.RED])
            wrap(layout, context, ro.reason, icon="ERROR", alert=True)
        if ro.sample:
            _sample_line(layout, context)
        hint(layout, context, f"Limits: amber from {core.DEFAULT_LIMITS.crane * 100:.0f} % of the chart, red above "
                              "100 %. Within the entered chart and limits only.")


CLASSES = (FRESING_PT_lifting, FRESING_PT_lifting_equipment, FRESING_PT_lifting_load, FRESING_PT_lifting_hook)


def unregister_previews():
    if _PREVIEWS["coll"] is not None:
        import bpy.utils.previews
        bpy.utils.previews.remove(_PREVIEWS["coll"])
        _PREVIEWS["coll"] = None
