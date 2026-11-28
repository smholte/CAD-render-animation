"""Side panel: 8 Lifting plan (task 0201) – Equipment, Load, Rigging (task 0232), Hook & capacity. Same layout rules as ui.py.

Nothing is worked out while drawing: the readout comes from ``lifting.readout`` (cached on a cheap key), the library
from ``lifting.library`` (read once until Refresh)."""

from __future__ import annotations

import os

import bpy

from ..core import lifting as core
from ..core.words import plural
from . import lifting
from .ui import _Panel, big, fold, gap, header_status, hint, missing, primary, split_props, steps, wrap

STATUS_ICON = {core.OK: "STRIP_COLOR_04", core.AMBER: "STRIP_COLOR_02", core.RED: "STRIP_COLOR_01",
               core.NOT_CHECKED: "STRIP_COLOR_09"}
_PREVIEWS = {"coll": None}


def _t(kg: float) -> str:
    t = core.tonnes(kg)
    return f"{t:.2f} t" if t < 100 else f"{t:.1f} t"


def picture_key(path: str) -> str:
    """The cache key of a picture: its path with its change time and size (task 0349: keyed on the path alone, a
    crane made again with Replace showed its old picture until Blender was restarted)."""
    try:
        st = os.stat(path)
    except OSError:
        return ""
    return f"{path}|{st.st_mtime_ns}|{st.st_size}"


def _icon_of(path: str) -> int:
    """The item's picture as an icon (loaded once per version of the file)."""
    if not path or not os.path.isfile(path):
        return 0
    if _PREVIEWS["coll"] is None:
        import bpy.utils.previews
        _PREVIEWS["coll"] = bpy.utils.previews.new()
    coll = _PREVIEWS["coll"]
    key = picture_key(path)
    if key not in coll:
        try:
            coll.load(key, path, "IMAGE", force_reload=True)
        except Exception:  # noqa: BLE001
            return 0
    return coll[key].icon_id


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
                                "Rigging: the lift points, the sling set and shackles; Hang on the hook – the load hangs "
                                "under the hook with each leg's force",
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
            elif lifting.picked_crane(scene) is not None:          # its model was deleted (0209 row 4)
                wrap(layout, context, f"The model of {lifting.picked_crane(scene).name} is gone: Remove takes its "
                     "joints, poses and cables out too.", icon="ERROR", alert=True)
                layout.operator("fresing.lifting_remove", text="Remove", icon="TRASH")
            gap(layout, line=True)
        body = fold(layout, "fr_lifting_library", "Add a crane from the library", icon="ADD", closed=bool(L.cranes))
        if body is not None:
            _draw_library(body, context, L)
        from . import ui_lifting_make
        ui_lifting_make.draw_in_equipment(layout, context)     # task 0204: Make a crane…


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
    from . import lifting_rope
    if lifting_rope.is_reeved(c):
        layout.label(text=f"Hoist rope: {plural(c.falls, 'fall')}, reeved", icon="CON_FOLLOWPATH")
    else:
        hint(layout, context, "The hoist rope is one piece (placed before rope reeving came).")
        layout.operator("fresing.lifting_reeve", text="Reeve the rope", icon="CON_FOLLOWPATH")
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
        hint(layout, context, "Your own equipment: switch on or add a Lifting equipment folder in Fresing Settings > "
                              "Locations.")
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
        if ld.kind == "PARTS" and n == 0:             # task 0337 (0328 row 24): never used, never a green readout
            wrap(layout, context, lifting.NO_PARTS.format(name=ld.name), icon="ERROR", alert=True)
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
    from . import lifting_rig
    rg = lifting_rig.rigging_mass(ld)
    col.label(text=f"Rigging {_t(rg)}" + ("" if ld.points else " (no rigging yet)"))
    if c is not None:
        col.label(text=f"Hook block {_t(g.hook_block)}" + (" (in the chart)" if includes else ""))
    col.label(text=f"Gross load {_t(g.total + rg)}", icon="FORCE_FORCE")


class FRESING_PT_lifting_rigging(_Panel, bpy.types.Panel):
    bl_label = "Rigging"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="LINKED")

    def draw_header_preset(self, context):
        ld = lifting.active_load(context.scene)
        if ld is None:
            header_status(self.layout, "no load")
        elif ld.rig_state == "HUNG":
            header_status(self.layout, "on the hook")
        elif ld.rig_state == "DOWN":
            header_status(self.layout, "set down")
        else:
            header_status(self.layout, plural(len(ld.points), "lift point"))

    def draw(self, context):
        from . import lifting_rig as RG
        layout = self.layout
        scene = context.scene
        ld = lifting.active_load(scene)
        if ld is None:
            missing(layout, context, "No load yet: make one under Load first.")
            return
        steps(layout, context, ["Lift points: Find lift points (padeyes, lugs, corner castings by name) or Add lift "
                                "point and click them on the load",
                                "Gear: a sling set, the shackles, a spreader if wanted (Hang picks the smallest chain "
                                "sling and shackle that carry it when none is picked)",
                                "Hang on the hook: the load hangs under the active crane's hook; the legs' angles and "
                                "forces are checked (C2–C4)"],
              key="fr_how_lifting_rigging", used=bool(ld.points))
        gap(layout)
        layout.label(text=f"{ld.name}: lift points", icon="EMPTY_SINGLE_ARROW")
        row = layout.row(align=True)
        row.operator("fresing.lifting_points_find", text="Find lift points", icon="VIEWZOOM")
        row.operator("fresing.lifting_point_add", text="Add lift point", icon="ADD")
        if ld.points:
            col = layout.column(align=True)
            for i, p in enumerate(ld.points):
                part = p.obj.get("fr_name", p.obj.name) if p.obj is not None else "(part gone)"
                col.label(text=f"{p.name}: {part}", icon="DOT")
                row = col.row(align=True)
                row.prop(p, "length", text="Leg")
                row.operator("fresing.lifting_point_remove", text="", icon="X").index = i
            hint(layout, context, "Leg 0 = the sling set's leg length.")
        gap(layout)
        layout.label(text="Gear", icon="LINKED")
        for op, title, path, empty in (("fresing.lifting_sling", "Sling", ld.sling, "picked when hung"),
                                       ("fresing.lifting_shackle", "Shackles", ld.shackle, "picked when hung"),
                                       ("fresing.lifting_spreader", "Spreader", ld.spreader, "none")):
            g = RG.gear(path)
            split = layout.split(factor=0.3, align=True)
            split.label(text=title)
            split.operator_menu_enum(op, "item", text=RG.GR.label(g) if g is not None else empty)
        col = split_props(layout)
        col.prop(ld, "leg_length", text="Leg length")
        if ld.spreader:
            col.prop(ld, "top_length", text="Top legs")
        if len(ld.points) in (3, 4) and not ld.spreader:
            col.prop(ld, "leg_mode", text="3 / 4 legs")
        hint(layout, context, f"Rigging {_t(RG.rigging_mass(ld))} (slings, shackles, spreader): added to the gross "
                              "load.")
        gap(layout)
        if lifting.active_crane(scene) is None:
            missing(layout, context, "No crane yet: place one under Equipment.")
        else:
            big(layout, "fresing.lifting_hang", "Hang on the hook" if ld.rig_state != "HUNG" else
                "Hang on the hook again", icon="TRIA_DOWN_BAR")
        row = layout.row(align=True)
        row.operator("fresing.lifting_set_down", text="Set down", icon="TRIA_DOWN")
        row.operator("fresing.lifting_rig_remove", text="Remove", icon="TRASH")
        _draw_hang(layout, context, scene, ld)


def _draw_hang(layout, context, scene, ld):
    from . import lifting_rig as RG
    r = RG.result(ld)
    if r is None or ld.rig_state == "NONE":
        return
    gap(layout)
    if RG.stale(scene, ld):
        wrap(layout, context, "The mass, the gear or the lift points changed since it was hung: Hang on the hook "
                              "again.", icon="ERROR", alert=True)
    box = layout.box()
    col = box.column(align=True)
    col.label(text=("On the hook" if ld.rig_state == "HUNG" else "Set down") + f" · tilt {r['tilt']:.1f}°")
    for lg in r["legs"]:
        row = col.row(align=True)
        word = f"{lg['name']}: {_t(lg['force'] / core.G)} at {lg['angle']:.0f}°" if lg["taut"] else \
            f"{lg['name']}: slack"
        if lg["at_hook"] and abs(lg["planned"] - lg["force"]) > 1.0:
            word += f" (plan {_t(lg['planned'] / core.G)})"
        row.label(text=word)
        if ld.rig_state == "HUNG":
            row.operator("fresing.lifting_leg_go", text="", icon="VIEWZOOM").leg = lg["name"]
    for p in r["problems"]:
        wrap(layout, context, p, icon="ERROR", alert=True)
    for n in r["notes"]:
        wrap(layout, context, n, icon="INFO")
    gap(layout)
    for chk in r["checks"]:
        rows = chk["parts"] or [chk]
        for x in rows:
            row = layout.row()
            row.alert = x["status"] == core.RED
            use = f" {x['use'] * 100:.0f} %" if x.get("use") is not None else ""
            row.label(text=f"{chk['check']} {x['title']}:{use}", icon=STATUS_ICON[x["status"]])
    hint(layout, context, f"Limits: amber from {core.DEFAULT_LIMITS.rigging * 100:.0f} % of a WLL, red above 100 %. "
                          "Within the entered gear and limits only.")


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
            header_status(self.layout, "no chart", alert=ro.status == core.RED)     # no chart at all: grey (0203)

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
            red = ro.status == core.RED                     # task 0203: no chart at all = "Not checked", grey
            row = layout.row()
            row.alert = red
            row.label(text=f"Gross load {_t(ro.gross)}: {ro.words}", icon=STATUS_ICON.get(ro.status, "INFO"))
            wrap(layout, context, ro.reason, icon="ERROR" if red else "INFO", alert=red)
        lp = lifting.line_pull(scene, c, ro.gross)
        row = layout.row()
        row.alert = lp.status == core.RED
        row.label(text=f"Line pull {_t(lp.value)} ({plural(int(lp.inputs['falls']), 'fall')})"
                       + (f": {lp.use * 100:.0f} %" if lp.use is not None else ""),
                  icon=STATUS_ICON[lp.status])
        if ro.sample:
            _sample_line(layout, context)
        hint(layout, context, f"Limits: amber from {core.DEFAULT_LIMITS.crane * 100:.0f} % of the chart, red above "
                              "100 %. Within the entered chart and limits only.")


# ---------------------------------------------------------------------------------------------------------------------
# task 0348: the lift path and the checks along it

def _short(t: float | None) -> str:
    return "–" if t is None else f"{t:.0f}"


class FRESING_PT_lifting_path(_Panel, bpy.types.Panel):
    bl_label = "Lift path & checks"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="IPO_EASE_IN_OUT")

    def draw_header_preset(self, context):
        from . import lifting_path as LP
        rs = LP.rows(context.scene)
        if not rs:
            header_status(self.layout, "not checked")
            return
        w = core.worst_status(r.status for r in rs)
        header_status(self.layout, f"worst: {LP.P.COLOUR[w]}", icon=STATUS_ICON[w], alert=w == core.RED)

    def draw(self, context):
        from . import lifting_path as LP
        layout = self.layout
        scene = context.scene
        L = scene.fresing.lifting
        c = lifting.active_crane(scene)
        if c is None:
            missing(layout, context, "No crane yet: place one under Equipment.")
            return
        ld = lifting.active_load(scene)
        steps(layout, context, ["Pick: the load where it hangs now (Rigging > Hang on the hook)",
                                "Set-down point: click where the load goes – the app proposes the steps (hoist "
                                "clear, slew, luff / telescope, travel, lower) as an animation you can change in 6 "
                                "Animation; or use one of your own animations",
                                "Check along the path: every check at the keys and between them, each with its worst "
                                "moment; Go there shows it"],
              key="fr_how_lifting_path", used=bool(L.path_anim))
        gap(layout)
        if ld is not None:
            hung = ld.rig_state == "HUNG" and ld.hung_on == c.name
            layout.label(text=f"Pick: {ld.name} – " + ("on the hook" if hung else "not hung: the hook alone"),
                         icon="PACKAGE")
        col = split_props(layout)
        col.prop(L, "path_clearance", text="Hoist clear")
        big(layout, "fresing.lifting_set_down_point", "Set-down point…", icon="TRIA_DOWN_BAR")
        row = layout.row(align=True)
        row.operator("fresing.lifting_path_propose", text="Propose again", icon="FILE_REFRESH")
        row.operator_menu_enum("fresing.lifting_path_use", "anim", text="Use an animation", icon="SEQUENCE")
        a = LP.path_anim(scene)
        if a is not None:
            word = "proposed steps" if LP.is_proposed(a) else "your own animation"
            hint(layout, context, f"Path: '{a.name}' ({word}) – change its steps in 6 Animation.")
        else:
            hint(layout, context, "No path yet.")
        gap(layout)
        layout.label(text="Ground under the mats or tracks", icon="WORLD")
        col = split_props(layout)
        col.prop(L, "allowable_kpa", text="Allowable (kPa)")
        col.prop(L, "mat_size", text="Mat (m)")
        gap(layout)
        big(layout, "fresing.lifting_path_check", "Check along the path", icon="VIEWZOOM")
        r = LP.result(scene)
        stale = LP.stale(scene)
        if r is None:
            state = "Not checked yet."
        elif stale:
            state = "Changed since it was checked: Check along the path again."
        else:
            state = f"Checked: {r['evaluations']} moments."
        row = layout.row()
        row.alert = stale
        row.label(text=state, icon="ERROR" if stale else "INFO")
        if r is not None:
            _draw_rows(layout, context, LP.rows(scene), go=True, stale=stale)
        gap(layout)
        live = LP.live_rows(scene)
        body = fold(layout, "fr_lifting_live", "Now (the pose shown)", icon="TIME", closed=True,
                    state=LP.P.COLOUR[LP.P.worst_of(live)] if isinstance(live, list) else "–")
        if body is not None:
            if isinstance(live, str):
                wrap(body, context, live, icon="ERROR", alert=True)
            else:
                _draw_rows(body, context, live, go=False)
        gap(layout)
        layout.prop(L, "data_box", text="Lift data box in renders and videos")
        hint(layout, context, "Limits: crane amber from 75 %, rigging and ground from 90 %, red above 100 %. Within "
                              "the entered chart, gear, ground and limits only.")


class FRESING_PT_lifting_zones(_Panel, bpy.types.Panel):
    bl_label = "Clearance & zones"
    bl_parent_id = "FRESING_PT_lifting"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def draw_header(self, context):
        self.layout.label(icon="MOD_LENGTH")

    def draw_header_preset(self, context):
        from . import lifting_path as LP
        live = LP.live_rows(context.scene) if lifting.active_crane(context.scene) is not None else None
        row = next((r for r in live if r.id == "CLR"), None) if isinstance(live, list) else None
        if row is None or row.status == core.NOT_CHECKED:
            header_status(self.layout, "not checked")
            return
        header_status(self.layout, f"clearance {row.value}", icon=STATUS_ICON[row.status],
                      alert=row.status == core.RED)

    def draw(self, context):
        from . import lifting_path as LP
        from . import lifting_zones as LZ
        layout = self.layout
        scene = context.scene
        L = scene.fresing.lifting
        if lifting.active_crane(scene) is None:
            missing(layout, context, "No crane yet: place one under Equipment.")
            return
        steps(layout, context, ["Clearance needed: how far the boom, the load and the rigging stay from everything "
                                "else in the project – checked now and along the path",
                                "On the ground: the reach rings, the exclusion zone and the outrigger mats or tracks "
                                "coloured by the ground pressure",
                                "Plan sheet: the plan view, the range diagram and the checks on one page to print"],
              key="fr_how_lifting_zones", used=bool(L.path_result))
        gap(layout)
        col = split_props(layout)
        col.prop(L, "clearance_m", text="Clearance needed")
        live = LP.live_rows(scene)
        row = next((r for r in live if r.id == "CLR"), None) if isinstance(live, list) else None
        if row is not None:
            wrap(layout, context, row.words, icon=STATUS_ICON[row.status], alert=row.status == core.RED)
        hint(layout, context, "Default: OSHA's 10 ft (3.05 m) from power lines up to 50 kV – set what your site asks.")
        gap(layout)
        layout.label(text="On the ground", icon="MESH_GRID")
        col = layout.column(align=True)
        col.prop(L, "show_reach")
        col.prop(L, "show_zone")
        col.prop(L, "show_footprint")
        col = split_props(layout)
        col.prop(L, "zone_margin", text="Zone margin")
        d = LZ.live_view(scene)
        if d is not None:
            hint(layout, context, (d.get("reach") or {}).get("words", ""))
            pads = d.get("patches") or []
            if pads:
                worst = max(pads, key=lambda p: (P_RANK[p["status"]], p["pressure"] or 0.0))
                words = (f"Ground now: {worst['name']} {core.kPa(worst['pressure']):.0f} kPa"
                         if worst["pressure"] is not None else "Ground now: outside the base")
                wrap(layout, context, words + (f" ({worst['use'] * 100:.0f} % of the allowable)"
                                               if worst.get("use") is not None else " – enter the allowable pressure "
                                               "under Lift path & checks"),
                     icon=STATUS_ICON[worst["status"]], alert=worst["status"] == core.RED)
        gap(layout)
        big(layout, "fresing.lifting_plan_sheet", "Plan sheet…", icon="DOCUMENTS")
        hint(layout, context, "Checked along the path: the sheet shows the whole path; else the pose shown.")


P_RANK = {core.OK: 0, core.NOT_CHECKED: 1, core.AMBER: 2, core.RED: 3}


def _draw_rows(layout, context, rows, go: bool, stale: bool = False):
    from . import lifting_path as LP
    col = layout.column(align=True)
    for r in rows:
        row = col.row(align=True)
        row.alert = r.status == core.RED and not stale
        sp = row.split(factor=0.55, align=True)
        sp.label(text=r.title, icon=STATUS_ICON[r.status])
        sp2 = sp.split(factor=0.5, align=True)
        sp2.label(text=f"{r.use * 100:.0f} %" if r.use is not None else (r.value if r.status != core.NOT_CHECKED
                                                                          else "grey"))
        if go:
            sub = sp2.row(align=True)
            sub.label(text=f"f {_short(r.t)}")
            op = sub.operator("fresing.lifting_path_go", text="", icon="VIEWZOOM")
            op.check = r.id
    body = fold(layout, "fr_lifting_words" if go else "fr_lifting_words_now", "In words", icon="TEXT", closed=True)
    if body is not None:
        for r in rows:
            wrap(body, context, r.words, icon=STATUS_ICON[r.status], alert=r.status == core.RED and not stale)
            if r.value or r.limit:
                hint(body, context, f"Worst value {r.value or '–'} · limit {r.limit or '–'}"
                     + (f" · frame {r.t:.1f}" if r.t is not None else ""), inset=1)
        if any(LP.P.RANK[r.status] == 1 for r in rows):
            hint(body, context, "Grey: not checked – the reason is in its line.")


CLASSES = (FRESING_PT_lifting, FRESING_PT_lifting_equipment, FRESING_PT_lifting_load, FRESING_PT_lifting_rigging,
           FRESING_PT_lifting_hook, FRESING_PT_lifting_path, FRESING_PT_lifting_zones)


def unregister_previews():
    if _PREVIEWS["coll"] is not None:
        import bpy.utils.previews
        bpy.utils.previews.remove(_PREVIEWS["coll"])
        _PREVIEWS["coll"] = None
