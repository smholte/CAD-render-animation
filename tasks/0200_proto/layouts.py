"""Task 0200 prototype (never merged): all outputs side by side, and section tabs against scrolling.

Outputs (three layouts, the same six outputs, settings in the app's OWN sub-panels shown as popovers):
  A  "Make" panel at the top of the Fresing tab: a row of big buttons, each opens that output's settings
  B  "Make" popover in the 3D view's header (always on screen, whatever the side panel shows)
  C  "Make" menu in the top bar (File Edit Render Window Help Make): one click per output, no settings
Scrolling:
  T  a row of section tabs (1–7, All) at the top of the Fresing tab: only the chosen section is drawn
"""
import sys

import bpy

OUTPUTS = [
    # (key, text, icon, settings panel shown as a popover, main operator, its text)
    ("still", "Picture", "RENDER_STILL", "FRESING_PT_output", "fresing.render", "Render image"),
    ("turn", "Turntable", "FILE_MOVIE", "FRESING_PT_turntable", "fresing.turntable", "Make turntable video"),
    ("anim", "Animation", "RENDER_ANIMATION", "FRESING_PT_make_anim", None, None),
    ("product", "Product video", "SEQUENCE", "FRESING_PT_make_product", "fresing.product_video",
     "Make a product video"),
    ("web", "3D page", "WORLD", "FRESING_PT_web3d", "fresing.web3d_export", "Export…"),
    ("queue", "Queue", "SORTTIME", "FRESING_PT_queue", "fresing.queue_start", "Start queue"),
]


def _pkg():
    for name in sys.modules:
        if name.endswith("fresing_render") and name + ".blender" in sys.modules:
            return name


def _m(name):
    import importlib
    return importlib.import_module(_pkg() + "." + name)


class FRESING_PT_make_anim(bpy.types.Panel):
    """The selected animation's video settings (today in 6 Animation, under the steps)."""
    bl_label = "Animation video"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    def draw(self, context):
        layout = self.layout
        s = context.scene.fresing
        ui = _m("blender.ui")
        if not s.animations:
            layout.label(text="No animation yet: 6 Animation > Add", icon="INFO")
            return
        a = s.animations[min(s.animations_index, len(s.animations) - 1)]
        layout.prop(s, "animations_index", text="Animation")
        col = ui.split_props(layout)
        col.prop(a, "out_resolution", text="Size")
        col.prop(a, "out_format", text="Shape")
        col.prop(a, "video", text="File")
        col.prop(a, "quality", text="Quality")
        op = layout.operator("fresing.queue_add", text="Time test (2 frames)", icon="SORTTIME")
        op.kind, op.name, op.start = "TEST", a.name, True
        op = ui.primary(layout, "fresing.queue_add", "Render animation", "RENDER_ANIMATION")
        op.kind, op.name, op.start = "ANIMATION", a.name, True


class FRESING_PT_make_product(bpy.types.Panel):
    bl_label = "Product video"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_ui_units_x = 15

    def draw(self, context):
        _m("blender.ui_motion")._draw_product_video(self.layout, context)


def draw_make(layout, context, big=True):
    grid = layout.grid_flow(columns=2, even_columns=True, even_rows=True, align=True)
    for key, text, icon, panel, _op, _t in OUTPUTS:
        col = grid.column(align=True)
        col.scale_y = 1.6 if big else 1.0
        col.popover(panel=panel, text=text, icon=icon)


class FRESING_PT_make(bpy.types.Panel):
    """Layout A: one 'Make' section on top of the Fresing tab."""
    bl_label = "Make"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fresing"
    bl_order = 0

    def draw_header(self, context):
        self.layout.label(icon="RENDER_STILL")

    def draw(self, context):
        draw_make(self.layout, context)
        self.layout.label(text="Each button opens its settings and its Make button", icon="INFO")


class FRESING_PT_make_header(bpy.types.Panel):
    """Layout B: the header popover lists every output with its main button and its settings beside it."""
    bl_label = "Make"
    bl_space_type = "VIEW_3D"
    bl_region_type = "HEADER"
    bl_ui_units_x = 14

    def draw(self, context):
        layout = self.layout
        for key, text, icon, panel, op, optext in OUTPUTS:
            row = layout.row(align=True)
            row.scale_y = 1.3
            if op:
                row.operator(op, text=text, icon=icon)
            else:
                row.label(text=text, icon=icon)
            row.popover(panel=panel, text="", icon="PREFERENCES")


def header_draw(self, context):
    if context.area and context.area.type == "VIEW_3D":
        self.layout.popover(panel="FRESING_PT_make_header", text="Make", icon="RENDER_STILL")


class FRESING_MT_make(bpy.types.Menu):
    """Layout C: a 'Make' menu in the top bar."""
    bl_label = "Make"
    bl_idname = "FRESING_MT_make"

    def draw(self, context):
        layout = self.layout
        layout.operator("fresing.render", text="Picture of this view", icon="RENDER_STILL")
        layout.operator("fresing.turntable", text="Turntable video", icon="FILE_MOVIE")
        layout.operator("fresing.queue_add", text="Animation video", icon="RENDER_ANIMATION").kind = "ANIMATION"
        layout.operator("fresing.product_video", text="Product video", icon="SEQUENCE")
        layout.operator("fresing.web3d_export", text="3D page (web 3D model)…", icon="WORLD")
        layout.separator()
        layout.operator("fresing.queue_start", text="Start the render queue", icon="SORTTIME")


def topbar_draw(self, context):
    self.layout.menu("FRESING_MT_make")


# ---------------------------------------------------------------------------------------- section tabs
SECTIONS = ["FRESING_PT_import", "FRESING_PT_structure", "FRESING_PT_looks", "FRESING_PT_motion",
            "FRESING_PT_scene", "FRESING_PT_animation", "FRESING_PT_queue"]
ICONS = ["IMPORT", "OUTLINER", "MATERIAL", "CON_PIVOT", "SCENE", "RENDER_ANIMATION", "SORTTIME"]
_ORIG_POLL = {}


class FRESING_PT_tabs(bpy.types.Panel):
    """Layout T: a row of section tabs; the chosen section is the only one drawn."""
    bl_label = ""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Fresing"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    def draw(self, context):
        row = self.layout.row(align=True)
        row.scale_y = 1.5
        row.prop(context.window_manager, "fr_section", expand=True, icon_only=False)


def _gate(name):
    cls = getattr(bpy.types, name)
    orig = _ORIG_POLL.setdefault(name, cls.__dict__.get("poll"))
    k = str(SECTIONS.index(name) + 1)

    def poll(c, context):
        sel = context.window_manager.fr_section
        if sel != "ALL" and sel != k:
            return False
        return orig.__func__(c, context) if orig is not None else True
    cls.poll = classmethod(poll)


def regate():
    """Measured: Blender decides at registration whether a panel has a poll, so a poll added later is never
    called (1 Import has none). Every Fresing panel is registered again, parents first, with the gate."""
    names = [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]
    classes = {n: getattr(bpy.types, n) for n in names}

    def depth(c):
        d, p = 0, getattr(c, "bl_parent_id", "")
        while p:
            d += 1
            p = getattr(classes.get(p), "bl_parent_id", "") if p in classes else ""
        return d
    order = sorted(classes.values(), key=depth)
    for c in reversed(order):
        bpy.utils.unregister_class(c)
    for n in SECTIONS:
        _gate_cls(classes[n], n)
    for c in order:
        bpy.utils.register_class(c)


def _gate_cls(cls, name):
    orig = _ORIG_POLL.setdefault(name, cls.__dict__.get("poll"))
    k = str(SECTIONS.index(name) + 1)

    def poll(c, context):
        sel = context.window_manager.fr_section
        if sel != "ALL" and sel != k:
            return False
        return orig.__func__(c, context) if orig is not None else True
    cls.poll = classmethod(poll)


def enable_tabs():
    items = [("ALL", "All", "Every section")] + [(str(i + 1), str(i + 1), SECTIONS[i][11:].title())
                                                  for i in range(7)]
    bpy.types.WindowManager.fr_section = bpy.props.EnumProperty(items=items, default="ALL")
    bpy.utils.register_class(FRESING_PT_tabs)    # registered first: the others are registered again after it
    regate()


def widen(names=("FRESING_PT_output", "FRESING_PT_turntable", "FRESING_PT_web3d"), units=18):
    """A side-panel sub-panel shown as a popover is only ~10 units wide (text cut off): give it a width.
    Measured: bl_ui_units_x must be set before registration (register again)."""
    for n in names:
        cls = getattr(bpy.types, n)
        try:
            bpy.utils.unregister_class(cls)
            cls.bl_ui_units_x = units
            bpy.utils.register_class(cls)
        except Exception as exc:
            print("[0200] widen", n, exc)


def enable_make(a=True, b=True, c=True):
    widen()
    for cls in (FRESING_PT_make_anim, FRESING_PT_make_product, FRESING_PT_make_header, FRESING_MT_make):
        bpy.utils.register_class(cls)
    if a:
        imp = bpy.types.FRESING_PT_import
        bpy.utils.unregister_class(imp)
        bpy.utils.register_class(FRESING_PT_make)
        bpy.utils.register_class(imp)
    if b:
        bpy.types.VIEW3D_HT_header.append(header_draw)
    if c:
        bpy.types.TOPBAR_MT_editor_menus.append(topbar_draw)
