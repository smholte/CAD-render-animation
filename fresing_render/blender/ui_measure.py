"""The **Measure ▾** drop-down on the top bar (task 0322), right of Lead motions.

The top bar is drawn in every workspace and in the Client view (``ui_topbar`` draws this button with the Fresing
menu), so measuring is one click away everywhere. The drop-down: the big Measure button (the result by what you click,
as the 3D page's measure tool), the six kinds, the measurements made (each with Copy and Remove), Clear all, the units
and the switches Keep measurements / Show in renders.
"""

from __future__ import annotations

import bpy

from ..core import measure as core
from ..core.words import plural
from . import measure

UNITS_X = 17                         # the drop-down's width (UI units)
DRAWN = {"button": 0, "panel": 0}    # tests
KEYS = "Key M (Alt+M in Full access) · Shift: no snap · Esc: done"


def draw_menu(layout, context) -> None:
    scene = context.scene
    st = getattr(scene, "fresing_measure", None)
    if st is None:
        return
    layout.operator_context = "INVOKE_DEFAULT"
    col = layout.column()
    row = col.row()
    row.scale_y = 1.4
    op = row.operator("fresing.measure", text="Measure", icon=core.ICONS["SMART"])
    op.kind = "SMART"
    grid = col.grid_flow(columns=2, even_columns=True, align=True)
    for k in core.KINDS[1:]:
        op = grid.operator("fresing.measure", text=core.TITLES[k], icon=core.ICONS[k],
                           depress=(st.last == k))
        op.kind = k
    hint = col.row()
    hint.enabled = False
    hint.label(text=KEYS)
    col.separator()
    box = col.box()
    head = box.row()
    head.label(text=plural(len(st.items), "measurement") if len(st.items) else "No measurements yet",
               icon="DRIVER_DISTANCE")
    sub = head.row()
    sub.alignment = "RIGHT"
    sub.operator("fresing.measure_clear", text="Clear all", icon="TRASH")
    for i, item in enumerate(st.items):
        r = measure.result(scene, item)
        row = box.row(align=True)
        row.prop(item, "show", text="", emboss=False, icon="HIDE_OFF" if item.show else "HIDE_ON")
        text = core.summary(item.kind, r, st.units) if r is not None else f"{item.name}: a part is gone"
        lab = row.row()
        lab.alert = r is None
        lab.label(text=text)
        op = row.operator("fresing.measure_copy", text="", icon="COPYDOWN")
        op.index = i
        op = row.operator("fresing.measure_remove", text="", icon="X")
        op.index = i
    col.separator()
    row = col.row()
    row.label(text="Units")
    row.prop(st, "units", expand=True)
    col.prop(st, "show")
    col.prop(st, "keep")
    col.prop(st, "in_renders")
    col.prop(st, "label_size", slider=True)


class TOPBAR_PT_fresing_measure(bpy.types.Panel):
    """Measure in the 3D view: distances, edges, gaps, angles, diameters, a point to an axis"""

    bl_space_type = "TOPBAR"
    bl_region_type = "HEADER"
    bl_label = "Measure"
    bl_ui_units_x = UNITS_X

    def draw(self, context):
        DRAWN["panel"] += 1
        draw_menu(self.layout, context)


HIDE = [False]                        # tests that picture the top bar without it


def draw_button(layout, context) -> None:
    """The top bar's button (``ui_topbar`` calls it right after Lead motions)."""
    DRAWN["button"] += 1
    if HIDE[0]:
        return
    st = getattr(getattr(context, "scene", None), "fresing_measure", None)
    n = len(st.items) if st is not None else 0
    layout.popover(panel=TOPBAR_PT_fresing_measure.__name__, text="Measure" + (f" ({n})" if n else ""),
                   icon="DRIVER_DISTANCE")


CLASSES = (TOPBAR_PT_fresing_measure,)
