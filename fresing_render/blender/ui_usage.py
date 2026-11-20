"""The favourites bar and the quiet declutter question at the top of the Fresing tab (task 0181).

Order on the tab: update notice, test tour · Workspace · **Favourites** · What's next · tabs · Make · 1 … 7 (the bar
sits under the workspace switcher it belongs to; ``fresing_render._all_classes`` puts it there). The bar shows only
when it has buttons (a function used ``core.usage.MIN_CLICKS`` times, or a pin) or a question is waiting.
"""

from __future__ import annotations

import bpy

from ..core import functions as F
from . import learning, ui, usage
from .ui import _Panel, wrap


class FRESING_PT_favourites(_Panel, bpy.types.Panel):
    bl_label = "Favourites"
    bl_order = 0
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return bool(usage.prompt() or usage.bar(context.scene))

    def draw(self, context):
        layout = self.layout
        usage.activity()
        fids = usage.bar(context.scene)
        pins = usage.state()["bar"]["pins"]
        if fids:
            row = layout.row(align=True)
            left = row.row(align=True)
            left.alignment = "LEFT"
            left.label(text="Favourites", icon="SOLO_ON")
            right = row.row(align=True)
            right.alignment = "RIGHT"
            right.operator("fresing.usage_window", text="", icon="PREFERENCES", emboss=False)
            col = layout.column(align=True)
            for i, fid in enumerate(fids):
                if i % 2 == 0:
                    grid = col.row(align=True)
                f = F.FUNCTIONS[fid]
                icon = "PINNED" if fid in pins else "NONE"
                if f.panel in F.MENUS:
                    grid.operator(f.button, text=usage.label(fid), icon=icon)
                else:
                    grid.operator("fresing.usage_go", text=usage.label(fid), icon=icon).fid = fid
            if len(fids) % 2:
                grid.label(text="")                     # an odd last button keeps half the width
        panel = usage.prompt()
        if panel:
            if fids:
                ui.gap(layout)
                ui.gap(layout)                          # task 0236: the question stands apart from the buttons above
            q = learning.question(panel)
            box = layout.box()
            if q["fid"]:
                col = wrap(box, context, f"You haven't used {usage.panel_title(panel)} recently. Maybe you do not know "
                                         "it yet?", icon="LIGHT")
            else:
                col = wrap(box, context, f"You haven't used {usage.panel_title(panel)} recently. Hide it to clean up "
                                         "your workspace?", icon="HIDE_ON")
            col.active = False
            if q["fid"]:
                wrap(box, context, q["line"], inset=14)
            col = box.column(align=True)
            if q["fid"]:
                row = col.row(align=True)
                op = row.operator("fresing.learn_show", text="Show me in the guide")
                op.fid, op.how = q["fid"], "GUIDE"
                row.enabled = bool(q["guide"])
                row = col.row(align=True)
                op = row.operator("fresing.learn_show", text="Show me in the test tour")
                op.fid, op.how = q["fid"], "TOUR"
                row.enabled = bool(q["tour"])
                if F.FUNCTIONS[q["fid"]].lesson:              # task 0230: the function's lesson, at its step
                    op = col.operator("fresing.learn_lesson", text="Show me in a lesson")
                    op.fid, op.mode = q["fid"], "SHOW"
                col.operator("fresing.usage_declutter", text="Add to my learning list").choice = "learn"
            row = col.row(align=True)
            if q["can_hide"]:
                row.operator("fresing.usage_declutter", text="Hide it").choice = "hide"
            row.operator("fresing.usage_declutter", text="Not now").choice = "later"
            col.operator("fresing.usage_declutter", text="Don't ask again").choice = "never"

CLASSES = (FRESING_PT_favourites,)
