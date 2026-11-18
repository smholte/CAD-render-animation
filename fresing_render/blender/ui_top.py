"""The top of the Fresing tab (task 0062): Workspace switcher with the function families, the What's next card,
the section tabs, and Make – every way to make a picture, a video or a 3D page side by side.

Order on the tab: update notice, test tour (their own files) · Workspace · What's next · tabs · Make · 1 … 7.

**Make** does not move anything: each button opens the app's own settings panel of that output (5 Scene & Render >
Image size & render, Turntable video, Web 3D model; 6 Animation; 7 Render queue) as a popover with its own Make
button, so no section is renumbered. The same list sits in the 3D view's header ("Make"), reachable whatever the
side panel shows.
"""

from __future__ import annotations

import bpy

from ..core import functions as F
from ..core import places
from ..core import workspaces as W
from ..core.words import plural
from . import panels, ui, workspaces
from .ui import _Panel, big_row, header_status, hint, wrap


# =============================================================================
# Workspace
# =============================================================================


class FRESING_PT_workspace(_Panel, bpy.types.Panel):
    bl_label = "Workspace"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        name = workspaces.name_of(scene)
        ws = workspaces.current(scene)
        opened = panels.is_open("FRESING_PT_workspace")
        box = layout.box()
        row = box.row(align=True)
        row.scale_y = 1.15
        left = row.row(align=True)
        left.alignment = "LEFT"
        op = left.operator("fresing.panel_toggle", text="", emboss=False,
                           icon="DOWNARROW_HLT" if opened else "RIGHTARROW")
        op.name = "FRESING_PT_workspace"
        left.label(text="", icon="LOCKED" if ws.lock else "WORKSPACE")
        row.operator_menu_enum("fresing.workspace_pick", "name", text=name)
        hidden = workspaces.hidden_in_use(scene)
        if hidden and not ws.lock:
            row = layout.row(align=True)
            row.alert = True
            row.label(text=f"In use but hidden: {plural(len(hidden), 'family', 'families')}", icon="ERROR")
            sub = row.row(align=True)
            sub.ui_units_x = 3.2
            sub.operator("fresing.workspace_show_used", text="Show")
        if ws.lock:
            wrap(layout, context, "The project is locked against changes. Full access unlocks it.", icon="LOCKED")
        if not opened:
            return
        if ws.note:
            hint(layout, context, ws.note)
        if W.shadows(name, workspaces.library()):
            wrap(layout, context, f"Your own workspace '{name}' is used instead of the built-in one of that name.",
                 icon="INFO")
        ui.gap(layout)
        layout.label(text="Functions in this project")
        fam = W.effective_families(ws, workspaces.ticks(scene))
        used = workspaces.in_use(scene)
        col = layout.column(align=True)
        for f in W.tickable():
            row = col.row(align=True)
            left = row.row(align=True)
            left.alignment = "LEFT"
            op = left.operator("fresing.family_toggle", text=W.family_title(f), emboss=False,
                               icon="CHECKBOX_HLT" if fam.get(f) else "CHECKBOX_DEHLT")
            op.family = f
            if f in used:
                right = row.row(align=True)
                right.alignment = "RIGHT"
                right.active = False
                right.label(text="in use")
        hint(layout, context, "Hiding keeps the work: it stays in the project and in renders.")
        ui.gap(layout)
        col = layout.column(align=True)
        col.operator("fresing.workspace_all", icon="HIDE_OFF")
        col.operator("fresing.workspace_show_used", icon="CHECKMARK")
        ui.gap(layout)
        col = layout.column(align=True)
        col.operator("fresing.workspace_save", text="Save as my own…", icon="ADD")
        row = col.row(align=True)
        row.operator("fresing.workspace_rename", text="Rename…")
        row.operator("fresing.workspace_delete", text="Delete…")
        row = col.row(align=True)
        row.operator("fresing.workspace_refresh", icon="FILE_REFRESH")
        row.operator("fresing.workspace_folder", icon="FILE_FOLDER")
        op = layout.operator("fresing.workspace_default", text="Use for new projects", icon="FILE_NEW")
        op.current = True
        if workspaces.default_name() == name:
            hint(layout, context, "New projects start in this workspace.")


# =============================================================================
# What's next
# =============================================================================


def next_step(scene) -> tuple:
    """(text, section panel to open or '', button text) for the card: the next thing to do in this project."""
    s = scene.fresing
    if s.model_count == 0:
        return ("Start here: open 1 Import and press Import STEP… – or try the app on a test model first "
                "(Help > Make test tour project).", "FRESING_PT_import", "Open 1 Import")
    if not len(s.groups) or s.unmatched:
        return ("Next: 3 Looks > Sort parts into groups gives every part its material. Hide what you do not "
                "need in 2 Structure.", "FRESING_PT_looks", "Open 3 Looks")
    return ("Next: 5 Scene & Render – pick the surroundings and a camera view, then Render image. The Make "
            "list below has every kind of output.", "FRESING_PT_scene", "Open 5 Scene & Render")


class FRESING_PT_next(_Panel, bpy.types.Panel):
    bl_label = "What's next"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        s = context.scene.fresing
        return not s.next_hidden and not s.rendered_once and not workspaces.locked(context.scene)

    def draw(self, context):
        text, panel, button = next_step(context.scene)
        box = self.layout.box()
        row = box.row()
        row.label(text="What's next", icon="LIGHT")
        row.operator("fresing.next_hide", text="", icon="X", emboss=False)
        wrap(box, context, text, inset=14)
        if panel and not panels.is_open(panel):
            box.operator("fresing.next_go", text=button, icon="TRIA_DOWN").panel = panel


# =============================================================================
# section tabs
# =============================================================================


class FRESING_PT_tabs(_Panel, bpy.types.Panel):
    bl_label = "Sections"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.scale_y = 1.2
        now = panels.tab()
        row.operator("fresing.panel_tab", text="All", depress=now == "ALL").tab = "ALL"
        for i in range(1, len(places.SECTIONS) + 1):
            row.operator("fresing.panel_tab", text=str(i), depress=now == str(i)).tab = str(i)
        from . import prefs
        p = prefs.get()
        if p is not None and not p.knows_ctrl_click:
            hint(layout, context, "Ctrl+click a title: only that one stays open.")


# =============================================================================
# Make: every output side by side
# =============================================================================

# key, button text, icon, the popover panel, the function that must show, the main operator (header list), its text
OUTPUTS = (
    ("still", "Picture", "RENDER_STILL", "FRESING_PT_make_still", "scene.still", "fresing.render", "Render image"),
    ("product", "Product video", "SEQUENCE", "FRESING_PT_make_product", "animation.product_video",
     "fresing.product_video", "Make a product video"),
    ("turn", "Turntable", "FILE_MOVIE", "FRESING_PT_make_turn", "scene.turntable", "fresing.turntable",
     "Make turntable video"),
    ("web", "3D page", "WORLD", "FRESING_PT_make_web", "web.export", "fresing.web3d_export", "Export…"),
    ("anim", "Animation", "RENDER_ANIMATION", "FRESING_PT_make_anim", "animation.add", "", ""),
    ("queue", "Queue", "SORTTIME", "FRESING_PT_make_queue", "queue.still", "fresing.queue_start", "Start queue"),
)
POPOVER_UNITS = 17


def _outputs(scene):
    return [o for o in OUTPUTS if workspaces.shows(scene, o[4])]


def draw_make(layout, context) -> None:
    grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True, align=True)
    for _key, text, icon, panel, _fid, _op, _t in _outputs(context.scene):
        col = grid.column(align=True)
        col.scale_y = 1.35
        col.popover(panel=panel, text=text, icon=icon)


class FRESING_PT_make(_Panel, bpy.types.Panel):
    bl_label = "Make"
    bl_order = 0

    @classmethod
    def poll(cls, context):
        return context.scene.fresing.model_count > 0

    def draw_header(self, context):
        self.layout.label(icon="RENDER_RESULT")

    def draw_header_preset(self, context):
        n = len(context.scene.fresing.queue)
        if n:
            header_status(self.layout, f"{n} queued")

    def draw(self, context):
        layout = self.layout
        draw_make(layout, context)
        hint(layout, context, "Each button opens that output's settings with its own Make button.")
        if hasattr(bpy.types, "FRESING_OT_setup_window") and (
                workspaces.shows(context.scene, "cnc.machine")
                or workspaces.shows(context.scene, "machines.mechanism")):
            ui.gap(layout)
            layout.operator("fresing.setup_window", text="Set-up window…", icon="WINDOW").kind = ""


class _Popover:
    """A settings panel of the side panel shown as a popover: the same body, as wide as a popover needs, its main
    button blue."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = POPOVER_UNITS
    target = ""

    def draw(self, context):
        cls = getattr(bpy.types, self.target, None)
        if cls is None:
            self.layout.label(text="Not available", icon="ERROR")
            return
        with ui.popover_width(POPOVER_UNITS):
            panels.body_of(cls)(self, context)


class FRESING_PT_make_still(_Popover, bpy.types.Panel):
    bl_label = "Picture"
    target = "FRESING_PT_output"


class FRESING_PT_make_turn(_Popover, bpy.types.Panel):
    bl_label = "Turntable video"
    target = "FRESING_PT_turntable"


class FRESING_PT_make_web(_Popover, bpy.types.Panel):
    bl_label = "3D page (web 3D model)"
    target = "FRESING_PT_web3d"


class FRESING_PT_make_queue(_Popover, bpy.types.Panel):
    bl_label = "Render queue"
    target = "FRESING_PT_queue"


class FRESING_PT_make_product(bpy.types.Panel):
    bl_label = "Product video"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = POPOVER_UNITS

    def draw(self, context):
        from . import ui_motion
        with ui.popover_width(POPOVER_UNITS):
            ui_motion._draw_product_video(self.layout, context)


class FRESING_PT_make_anim(bpy.types.Panel):
    """The selected animation as a video: its size, shape and quality, a time test, and Render animation."""
    bl_label = "Animation video"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = POPOVER_UNITS

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        with ui.popover_width(POPOVER_UNITS):
            if not len(s.animations):
                wrap(layout, context, f"No animation yet: make one in {places.where('animation')} (Add animation, "
                                      "then its steps).", icon="INFO")
                return
            a = s.animations[min(s.animations_index, len(s.animations) - 1)]
            layout.label(text=f"Animation: {a.name}", icon="RENDER_ANIMATION")
            col = ui.split_props(layout)
            col.prop(a, "out_resolution", text="Size")
            col.prop(a, "out_format", text="Shape")
            col.prop(a, "quality", text="Quality")
            col.prop(a, "video", text="File")
            ui.gap(layout)
            op = layout.operator("fresing.queue_add", text="Time test (2 frames)", icon="SORTTIME")
            op.kind, op.name, op.start = "TEST", a.name, True
            op = ui.primary(layout, "fresing.queue_add", "Render animation", "RENDER_ANIMATION", ui.MEDIUM)
            op.kind, op.name, op.start = "ANIMATION", a.name, True
            hint(layout, context, f"The steps, cameras and finishing are in {places.where('animation')}.")


class FRESING_PT_make_header(bpy.types.Panel):
    """The Make list in the 3D view's header: every output with its main button and its settings beside it."""
    bl_label = "Make"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 13

    def draw(self, context):
        layout = self.layout
        if context.scene.fresing.model_count == 0:
            layout.label(text="Import a model first (1 Import)", icon="INFO")
            return
        for _key, text, icon, panel, _fid, op, _optext in _outputs(context.scene):
            row = layout.row(align=True)
            row.scale_y = 1.25
            if op:
                row.operator(op, text=text, icon=icon)
            else:
                row.popover(panel=panel, text=text, icon=icon)
                continue
            row.popover(panel=panel, text="", icon="PREFERENCES")


def _draw_view_header(self, context):
    area = context.area
    if area is None or area.type != "VIEW_3D" or not hasattr(context.scene, "fresing"):
        return
    self.layout.popover(panel="FRESING_PT_make_header", text="Make", icon="RENDER_RESULT")


TOP = (FRESING_PT_workspace, FRESING_PT_next, FRESING_PT_tabs, FRESING_PT_make)        # before 1 Import, in this order
POPOVERS = (FRESING_PT_make_still, FRESING_PT_make_turn, FRESING_PT_make_web, FRESING_PT_make_queue,
            FRESING_PT_make_product, FRESING_PT_make_anim, FRESING_PT_make_header)
CLASSES = TOP + POPOVERS


def register_header() -> None:
    bpy.types.VIEW3D_HT_header.remove(_draw_view_header)
    bpy.types.VIEW3D_HT_header.append(_draw_view_header)


def unregister_header() -> None:
    bpy.types.VIEW3D_HT_header.remove(_draw_view_header)
