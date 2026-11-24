"""The favourites bar and the quiet declutter question at the top of the Fresing tab (task 0181).

Since task 0260 on the left panel: Live preview · Build & play, Workspace, Learning hub, **Favourites**, What's next
(``fresing_render._all_classes`` puts it there); since task 0278 it folds like the other left sections, kept per
user. The bar shows only when it has buttons (a function used ``core.usage.MIN_CLICKS`` times, or a pin) or a question
is waiting.
"""

from __future__ import annotations

import bpy

from ..core import functions as F
from . import learning, panels, ui, usage
from .ui import wrap
from .ui_left import LeftPanel

QUESTION = "1 question"          # task 0278: on the folded Favourites header while the declutter question waits


class FRESING_PT_favourites(LeftPanel, bpy.types.Panel):  # task 0260: on the left panel
    bl_label = "Favourites"
    bl_order = 0
    # task 0278: the app's title row with the fold arrow, like Learning hub and Lesson; the fold is kept per user

    @classmethod
    def poll(cls, context):
        return bool(usage.prompt() or usage.bar(context.scene))

    def draw_header(self, context):
        self.layout.label(icon="SOLO_ON")

    def draw_header_preset(self, context):
        row = self.layout.row(align=True)
        row.alignment = "RIGHT"
        if usage.prompt() and not panels.is_open("FRESING_PT_favourites"):
            row.label(text=QUESTION, icon="LIGHT")           # folded: the waiting question still shows
        row.operator("fresing.usage_window", text="", icon="PREFERENCES", emboss=False)

    def draw(self, context):
        layout = self.layout
        fids = usage.bar(context.scene)
        pins = usage.state()["bar"]["pins"]
        if fids:
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
                op = row.operator("fresing.learn_show", text="Show me in the guide",
                                  icon="CHECKMARK" if usage.shown("GUIDE") else "NONE")
                op.fid, op.how = q["fid"], "GUIDE"
                row.enabled = bool(q["guide"])
                row = col.row(align=True)
                op = row.operator("fresing.learn_show", text="Show me in the Learning hub",
                                  icon="CHECKMARK" if usage.shown("TOUR") else "NONE")
                op.fid, op.how = q["fid"], "TOUR"
                row.enabled = bool(q["tour"])
                if F.FUNCTIONS[q["fid"]].lesson:              # task 0230: the function's lesson, at its step
                    op = col.operator("fresing.learn_lesson", text="Show me in a lesson",
                                      icon="CHECKMARK" if usage.shown("LESSON") else "NONE")
                    op.fid, op.mode = q["fid"], "SHOW"
                col.operator("fresing.usage_declutter", text="Add to my learning list").choice = "learn"
            row = col.row(align=True)
            if q["can_hide"]:
                row.operator("fresing.usage_declutter", text="Hide it").choice = "hide"
            row.operator("fresing.usage_declutter", text="Not now").choice = "later"
            col.operator("fresing.usage_declutter", text="Don't ask again").choice = "never"

CLASSES = (FRESING_PT_favourites,)
