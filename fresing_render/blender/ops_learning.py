"""Learn as you go: the buttons (task 0208) – the question's "Show me", the learning list's window, the right-click
"Add to my learning list", the quiet "Next to learn". They change nothing in the model (``lock.ALLOWED_PREFIXES``)."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty

from ..core import functions as F
from ..core import learning as core
from ..core.words import plural
from . import learning, usage


def _title(fid: str) -> str:
    return core.one_line(fid)


class FRESING_OT_learn_show(bpy.types.Operator):
    """Shows a function you have not used: in the user guide, or in the test tour (its first stop is set up and the
    button pointed at). The function is put on your learning list too"""

    bl_idname = "fresing.learn_show"
    bl_label = "Show me"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    how: EnumProperty(items=[("GUIDE", "Show me in the guide", "Opens the user guide at this function's section"),
                             ("TOUR", "Show me in the test tour",
                              "Sets up the test tour's stop for this function and points at its button")],
                      options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        if props is None:
            return cls.__doc__
        if props.how == "TOUR":
            opts = core.options(props.fid)
            return ("Sets up the test tour's stop for this function and points at its button. The function goes on "
                    "your learning list" if opts["tour"] else opts["why_no_tour"])
        return "Opens the user guide at this function's section. The function goes on your learning list"

    def execute(self, context):
        if self.fid not in F.FUNCTIONS:
            return {"CANCELLED"}
        panel = usage.prompt()
        if self.how == "TOUR":
            why = learning.show_in_tour(context, self.fid)
            if why:
                self.report({"WARNING"}, why)
                return {"CANCELLED"}
        else:
            if not learning.open_guide(F.FUNCTIONS[self.fid].guide):
                self.report({"ERROR"}, "This function has no guide section yet")
                return {"CANCELLED"}
        if panel and core.target_of_panel(panel) == self.fid:
            usage.answer(context.scene, "learn")                 # asked, and on the list
        else:
            core.add(usage.state(), self.fid)
            learning.save()
        _redraw()
        return {"FINISHED"}


class FRESING_OT_learn_add(bpy.types.Operator):
    """Puts this function on your learning list (Fresing > My learning list…): the guide and the test tour are one
    click away there, and it is ticked by itself once you use it on a few days"""

    bl_idname = "fresing.learn_add"
    bl_label = "Add to my learning list"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        if self.fid not in F.FUNCTIONS:
            return {"CANCELLED"}
        if core.add(usage.state(), self.fid):
            learning.save()
            self.report({"INFO"}, f"'{_title(self.fid)}' is on your learning list (Fresing > My learning list…)")
        _redraw()
        return {"FINISHED"}


class FRESING_OT_learn_add_new(bpy.types.Operator):
    """Puts the new and improved functions of this update on your learning list"""

    bl_idname = "fresing.learn_add_new"
    bl_label = "Add the new functions to my learning list"
    bl_options = {"INTERNAL"}

    since: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        n = core.add_many(usage.state(), core.new_since(self.since))
        learning.save()
        self.report({"INFO"}, f"{plural(n, 'function')} added to your learning list" if n
                    else "Nothing new to add (they are on your list already)")
        return {"FINISHED"}


class FRESING_OT_learn_done(bpy.types.Operator):
    """Ticks this function off your learning list (click again to take the tick away)"""

    bl_idname = "fresing.learn_done"
    bl_label = "Done"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        item = core.find(usage.state(), self.fid)
        if item is None:
            return {"CANCELLED"}
        core.set_done(usage.state(), self.fid, not item["done"])
        learning.save()
        return {"FINISHED"}


class FRESING_OT_learn_remove(bpy.types.Operator):
    """Takes this function off your learning list"""

    bl_idname = "fresing.learn_remove"
    bl_label = "Remove"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def execute(self, context):
        core.remove(usage.state(), self.fid)
        learning.save()
        return {"FINISHED"}


class FRESING_OT_learn_next(bpy.types.Operator):
    """Answers the quiet "Next to learn" line. Learn: the function goes on your learning list and its guide section
    opens. Not interested: it is not suggested again"""

    bl_idname = "fresing.learn_next"
    bl_label = "Learn"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    choice: EnumProperty(items=[("learn", "Learn", "Puts it on your learning list and opens its guide section"),
                                ("no", "Not interested", "It is not suggested again")], options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        return {"learn": "Puts this function on your learning list and opens its guide section",
                "no": "This function is not suggested again"}.get(getattr(props, "choice", ""), cls.__doc__)

    def execute(self, context):
        if self.fid not in F.FUNCTIONS:
            return {"CANCELLED"}
        core.answer_next(usage.state(), self.fid, self.choice)
        learning.save()
        if self.choice == "learn":
            learning.open_guide(F.FUNCTIONS[self.fid].guide)
        _redraw()
        return {"FINISHED"}


class FRESING_OT_learn_lesson(bpy.types.Operator):
    """A lesson for this function (Show me, Build it yourself): the lessons come with a later update"""

    bl_idname = "fresing.learn_lesson"
    bl_label = "Show me"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return False                 # the hook: the lessons task puts its lesson here

    def execute(self, context):
        return {"CANCELLED"}


class FRESING_OT_learn_window(bpy.types.Operator):
    """Your learning list: the functions you wanted to learn, each with its guide section and its test-tour stop.
    They are ticked by themselves when you use them on a few days. Counted and kept on this PC only"""

    bl_idname = "fresing.learn_window"
    bl_label = "My learning list"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        self._told = core.take_told(usage.state())            # said once
        learning.save()
        return context.window_manager.invoke_props_dialog(self, width=620, title="My learning list",
                                                          confirm_text="Close")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        draw_list(self.layout, getattr(self, "_told", []))


def draw_list(layout, told=()) -> None:
    s = usage.state()
    items = core.part(s)["list"]
    for fid in told:
        row = layout.row()
        row.label(text=core.say_learned(fid) + " – ticked off your list", icon="CHECKMARK")
    if not items:
        col = layout.column(align=True)
        for line in ("Nothing on your list yet.",
                     "Right-click any button > Add to my learning list, or use the question about an unused panel."):
            row = col.row()
            row.active = False
            row.label(text=line)
        return
    box = layout.box().column(align=True)
    for item in items:
        fid = item["id"]
        f = F.FUNCTIONS.get(fid)
        if f is None:
            continue
        row = box.row(align=True)
        split = row.split(factor=0.42, align=True)
        left = split.row(align=True)
        left.alignment = "LEFT"
        left.label(text=_clip(f.title, 34), icon="CHECKBOX_HLT" if item["done"] else "CHECKBOX_DEHLT")
        right = split.row(align=True)
        g = right.row(align=True)
        g.enabled = bool(f.guide)
        g.operator("fresing.learn_show", text="Guide").fid = fid
        t = right.row(align=True)
        t.enabled = bool(f.tour)
        op = t.operator("fresing.learn_show", text="Tour")
        op.fid, op.how = fid, "TOUR"
        lesson = right.row(align=True)
        lesson.enabled = False
        lesson.operator("fresing.learn_lesson", text="Show me").fid = fid
        right.operator("fresing.learn_done", text="Done" if not item["done"] else "Undo").fid = fid
        right.operator("fresing.learn_remove", text="", icon="X").fid = fid
        if item["auto"]:
            sub = box.row()
            sub.active = False
            sub.label(text="    ticked by itself: used on " + plural(core.part(s)["need_days"], "day"))


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[:n - 1].rstrip() + "…"


def _redraw() -> None:
    from . import panels
    panels.redraw()


# ---------------------------------------------------------------------------
# right-click on any button
# ---------------------------------------------------------------------------

def button_function(context) -> str:
    """The function of the button under the mouse ('' = none)."""
    op = getattr(context, "button_operator", None)
    prop = getattr(context, "button_prop", None)
    idname = ""
    if op is not None:
        try:
            idname = learning.idname_of(op.bl_rna.identifier)
        except Exception:  # noqa: BLE001
            idname = ""
    ident = getattr(prop, "identifier", "") if prop is not None else ""
    if not idname.startswith("fresing.") and not ident:
        return ""
    fid = learning.function_of_button(idname if idname.startswith("fresing.") else "", ident)
    return fid if core.teachable(fid) else ""


def _draw_context(self, context):
    try:
        fid = button_function(context)
    except Exception:  # noqa: BLE001 - a menu never breaks over this
        return
    if not fid:
        return
    layout = self.layout
    layout.separator()
    on = core.find(usage.state(), fid) is not None
    row = layout.row()
    row.enabled = not on
    row.operator("fresing.learn_add", text="On my learning list" if on else "Add to my learning list",
                 icon="BOOKMARKS").fid = fid


def _draw_fresing_menu(layout) -> None:
    n = len(core.open_items(usage.state()))
    layout.operator("fresing.learn_window", text="My learning list…" + (f" ({n})" if n else ""), icon="BOOKMARKS")


CLASSES = (FRESING_OT_learn_show, FRESING_OT_learn_add, FRESING_OT_learn_add_new, FRESING_OT_learn_done,
           FRESING_OT_learn_remove, FRESING_OT_learn_next, FRESING_OT_learn_lesson, FRESING_OT_learn_window)


def register() -> None:
    menu = bpy.types.UI_MT_button_context_menu
    menu.remove(_draw_context)
    menu.append(_draw_context)


def unregister() -> None:
    bpy.types.UI_MT_button_context_menu.remove(_draw_context)
