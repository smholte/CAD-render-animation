"""The left panel (task 0260): everything that is not a step of the work, on the left of the 3D view.

The right-hand Fresing panel keeps only the work (Make, the section tabs, Set-up window…, 1 … 8). The rest sits in
**the 3D view's toolbar region** – Blender's own left strip, where its tool buttons live:

    Live preview · Build & play  (always, also in the folded strip)
    update notice (after an update) · Workspace · Learning hub (+ its stops, the Lesson) · Favourites · What's next

**Why the toolbar region** (step 1 of the task, measured in Blender 5.2.3): it belongs to each 3D view, so it opens
and closes with the projects, the Set-up window and every layout like the side panel does; it scrolls; it can be
dragged wider by the user. Outside Full access Blender's tool buttons are not drawn there (``quiet._no_tools``);
in Full access they come back above the app's panels.

**Its width.** A script cannot set a region's width (``Region.width`` is read-only) and Blender's toolbar starts one
button wide. The width Blender keeps for the region (``ARegion.sizex``, a 16-bit number in pixels at UI scale 1) is
written here directly: it is found next to the region's own width and height (two 16-bit numbers), region type 5
(TOOLS) and alignment 3 (LEFT), and the stored width must agree with the width on screen – nothing is written unless
all of that matches (``sizex_address``). Switching the toolbar off and on makes Blender take it at once. A width the
user dragged is kept; the app only widens a region that is still a strip while the panel is meant to be open, and
narrows it to the strip when he folds it (``fresing.left_fold``; the choice is kept per user in the preferences).
"""

from __future__ import annotations

import ctypes

import bpy
from bpy.props import EnumProperty

from . import panels, ui

OPEN_WIDTH = 240             # px at UI scale 1: the left panel's width when nothing else was chosen
STRIP_WIDTH = 34             # … folded to its strip (one icon wide)
STRIP_BELOW = 110            # narrower than this, the panel draws as the strip
RGN_TOOLS, RGN_LEFT = 5, 3   # Blender 5.2.3: ``eRegion_Type`` RGN_TYPE_TOOLS, ``RGN_ALIGN_LEFT``
RGN_UI, RGN_RIGHT = 4, 4     # … RGN_TYPE_UI (the side panel), RGN_ALIGN_RIGHT (task 0271: the Settings window)
_KINDS = {"TOOLS": (RGN_TOOLS, RGN_LEFT), "UI": (RGN_UI, RGN_RIGHT)}
SCAN = 320                   # bytes of the region looked through for its stored width

QUICK = panels.QUICK


class LeftPanel:
    """A panel of the left panel: the 3D view's toolbar region. ``panels.install`` gives it the app's title row and
    poll like the panels of the Fresing tab."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    _fr_left = True


# ---------------------------------------------------------------------------
# the width
# ---------------------------------------------------------------------------

def _scale() -> float:
    try:
        return float(bpy.context.preferences.system.ui_scale) or 1.0
    except (AttributeError, TypeError):
        return 1.0


def tools_region(area):
    return next((r for r in area.regions if r.type == "TOOLS"), None) if area is not None else None


def sizex_address(region) -> int | None:
    """The address of the width Blender keeps for this (shown) toolbar region – or side panel (task 0271) –, or None
    when it cannot be found for certain. See the top of this file."""
    if region is None or region.type not in _KINDS or region.width <= 1 or region.height <= 1:
        return None
    rtype, align = _KINDS[region.type]
    base = region.as_pointer()
    if not base:
        return None
    w, h, scale = region.width, region.height, _scale()

    def short(off):
        return ctypes.c_short.from_address(base + off).value

    found = []
    for off in range(0, SCAN - 16, 2):
        if short(off) == w and short(off + 2) == h and short(off + 8) == rtype and short(off + 10) == align:
            stored = short(off + 14)
            if stored > 0 and abs(stored * scale - w) <= 8:
                found.append(base + off + 14)
    return found[0] if len(found) == 1 else None


def set_side_width(area, px: int) -> bool:
    """Task 0271: give a 3D view's side panel this width (px at UI scale 1), as ``set_width`` does for the toolbar.
    False when its stored width cannot be found for certain (it then keeps its width)."""
    region = next((r for r in area.regions if r.type == "UI"), None)
    addr = sizex_address(region)
    if addr is None:
        return False
    ctypes.c_short.from_address(addr).value = int(max(160, min(900, px)))
    space = area.spaces.active
    space.show_region_ui = False             # Blender takes the new width when the region is laid out again
    space.show_region_ui = True
    area.tag_redraw()
    return True


def fit_width(area, px: int) -> bool:
    """Task 0271: make the toolbar region ``px`` real pixels wide. Blender scales a stored width by its own DPI factor
    (not only the UI scale): the factor is read from the region as it is now (its pixels / its stored width). A
    region made wider than its area leaves is hidden by Blender ("too small"), so ``px`` must fit."""
    region = tools_region(area)
    addr = sizex_address(region)
    if addr is None:
        return False
    stored = ctypes.c_short.from_address(addr).value
    if stored <= 0:
        return False
    ctypes.c_short.from_address(addr).value = int(max(STRIP_WIDTH, min(900, px * stored / region.width)))
    space = area.spaces.active
    space.show_region_toolbar = False
    space.show_region_toolbar = True
    area.tag_redraw()
    return True


def width(area) -> float:
    """The left panel's width in px at UI scale 1 (0 when it is not shown)."""
    region = tools_region(area)
    if region is None or not area.spaces.active.show_region_toolbar or region.width <= 1:
        return 0.0
    return region.width / _scale()


def set_width(area, px: int) -> bool:
    """Give the 3D view's toolbar region this width (px at UI scale 1). False when it is not shown yet or its stored
    width cannot be found for certain (it then keeps Blender's width)."""
    region = tools_region(area)
    addr = sizex_address(region)
    if addr is None:
        return False
    ctypes.c_short.from_address(addr).value = int(max(STRIP_WIDTH, min(600, px)))
    space = area.spaces.active
    space.show_region_toolbar = False        # Blender takes the new width when the region is laid out again
    space.show_region_toolbar = True
    area.tag_redraw()
    return True


def _prefs():
    from . import prefs
    return prefs.get()


def folded() -> bool:
    p = _prefs()
    return bool(p is not None and p.left_folded)


def ensure(area) -> bool:
    """The left panel shown at its width in this 3D view (each load, ``ui_header.put_layout_right``). True when done;
    False: try again after the next redraw (a region gets its size only then)."""
    space = area.spaces.active
    if not space.show_region_toolbar:
        space.show_region_toolbar = True
        return False
    region = tools_region(area)
    if region is None or region.width <= 1:
        return False
    w = region.width / _scale()
    p = _prefs()
    want_strip = bool(p is not None and p.left_folded)
    if want_strip and w >= STRIP_BELOW:
        set_width(area, STRIP_WIDTH)
    elif not want_strip and w < STRIP_BELOW:
        set_width(area, p.left_width if p is not None else OPEN_WIDTH)
    return True


def strip(context) -> bool:
    """Is the left panel drawn as its narrow strip (folded, or dragged that narrow)?"""
    region = getattr(context, "region", None)
    if region is None or region.type != "TOOLS":
        return False
    return 1 < region.width / _scale() < STRIP_BELOW


def main_areas():
    """The 3D views of the app's main windows (not the Set-up window, not an output window)."""
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        if win.screen is None or panels.side_window(win):
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                yield area


# ---------------------------------------------------------------------------
# the row that is always there: Live preview, Build & play, fold
# ---------------------------------------------------------------------------

NO_ANIMATION = "Make an animation first in 6 Animation"


def preview_on(context) -> bool:
    space = getattr(context, "space_data", None)
    shading = getattr(space, "shading", None)
    return bool(shading is not None and shading.type == "RENDERED")


def has_animation(context) -> bool:
    try:
        from . import animation
        return animation.active(context.scene) is not None
    except Exception:  # noqa: BLE001
        return False


class FRESING_PT_left_quick(LeftPanel, bpy.types.Panel):
    bl_label = "Live preview and Build & play"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, "fresing", None) is not None

    def draw(self, context):
        layout = self.layout
        on = preview_on(context)
        anim = has_animation(context)
        if strip(context):
            col = layout.column(align=True)
            col.scale_y = 1.3
            col.operator("fresing.left_fold", text="", icon="TRIA_RIGHT")
            col.operator("fresing.preview", text="", icon="SHADING_RENDERED", depress=on)
            sub = col.column(align=True)
            sub.enabled = anim
            sub.operator("fresing.anim_build", text="", icon="PLAY").play = True
            col.operator("fresing.settings", text="", icon="PREFERENCES")     # task 0271
            return
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.operator("fresing.preview", text="Live preview: on" if on else "Live preview", icon="SHADING_RENDERED",
                     depress=on)
        sub = row.row(align=True)
        sub.enabled = anim
        sub.operator("fresing.anim_build", text="Build & play", icon="PLAY").play = True
        row.operator("fresing.settings", text="", icon="PREFERENCES")         # task 0271: Fresing Settings
        row.operator("fresing.left_fold", text="", icon="TRIA_LEFT")


class FRESING_OT_left_fold(bpy.types.Operator):
    """Folds the left panel to a narrow strip (Live preview and Build & play stay there as icons) – or opens it again.
    Your choice is kept for every project and the next start"""

    bl_idname = "fresing.left_fold"
    bl_label = "Fold the left panel"
    bl_options = {"INTERNAL"}

    @classmethod
    def description(cls, context, props):
        if folded():
            return "Opens the left panel again: Workspace, Learning hub, Favourites and What's next"
        return " ".join((cls.__doc__ or "").split())

    def execute(self, context):
        from . import editors
        p = _prefs()
        if p is None:
            return {"CANCELLED"}
        if not editors.settled():            # an area was just closed beside the view: after the next redraw
            bpy.app.timers.register(lambda: (bpy.ops.fresing.left_fold() and None), first_interval=0.1)
            return {"FINISHED"}
        fold = not p.left_folded
        areas = list(main_areas())
        if fold:
            here = context.area if context.area is not None and context.area.type == "VIEW_3D" else None
            w = width(here) if here is not None else 0.0
            if w >= STRIP_BELOW:
                p.left_width = int(round(w))
        p.left_folded = fold
        done = False
        for area in areas:
            area.spaces.active.show_region_toolbar = True
            done = set_width(area, STRIP_WIDTH if fold else p.left_width) or done
        if not done:
            self.report({"INFO"}, "Drag the left panel's edge to make it wider or narrower")
        panels.redraw()
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# the Learning hub
# ---------------------------------------------------------------------------

MODES = (("VIEW", "View"), ("SHOW", "Show me"), ("BUILD", "Build it yourself"))
LESSON_COMING = "Lesson coming"


def hub_state(scene) -> dict:
    """What the Learning hub block shows: is this a Learning hub project (a finished sample = View, or a lesson
    project = Show me / Build it yourself), which sample, which mode, does it have a lesson."""
    from . import lesson, tour
    lesson_id = str(scene.get(lesson.KEY, "") or "") if scene is not None else ""
    in_tour = tour.is_tour(scene)
    set_id = lesson_id
    if not set_id and in_tour:
        set_id = str(scene.get(tour.TAG, "") or "")
        if set_id == tour.HUB_SET and not tour.SETS.get(set_id):
            set_id = ""
    mode = str(scene.get(lesson.KEY_MODE, "SHOW") or "SHOW") if lesson_id else "VIEW"
    ts = tour.SETS.get(set_id)
    return {"in_hub": bool(in_tour or lesson_id), "set": set_id, "title": ts.title if ts is not None else set_id,
            "mode": mode if mode in dict(MODES) else "VIEW", "lesson": set_id in lesson.LESSONS}


class FRESING_PT_hub(LeftPanel, bpy.types.Panel):
    bl_label = "Learning hub"

    @classmethod
    def poll(cls, context):
        return getattr(context.scene, "fresing", None) is not None

    def draw_header(self, context):
        self.layout.label(icon="LIGHT")

    def draw_header_preset(self, context):
        st = hub_state(context.scene)
        if st["in_hub"]:
            ui.header_status(self.layout, {"VIEW": "View", "SHOW": "Show me", "BUILD": "Build it"}[st["mode"]])

    def draw(self, context):
        layout = self.layout
        st = hub_state(context.scene)
        split = layout.split(factor=0.25, align=True)          # the switch: View | Show me | Build it yourself
        split.scale_y = 1.15
        first = split.row(align=True)
        rest = split.split(factor=0.42, align=True)
        for (mode, text), part in zip(MODES, (first, rest.row(align=True), rest.row(align=True))):
            if mode != "VIEW" and st["in_hub"] and not st["lesson"]:
                part.enabled = False
            part.operator("fresing.hub_mode", text=text, depress=st["in_hub"] and st["mode"] == mode).mode = mode
        if not st["in_hub"]:
            ui.big_row(layout, ui.MEDIUM).operator("fresing.tour_take", text="Open the Learning hub", icon="LIGHT")
            ui.hint(layout, context, "Learn the app on sample projects. Your own project is not changed.")
            return
        if st["title"]:
            ui.wrap(layout, context, st["title"], icon="FILE_BLEND")
        if not st["lesson"]:
            ui.hint(layout, context, f"{LESSON_COMING}: Show me and Build it yourself come for this sample with a "
                                     "later update. View shows it finished." if st["set"] else
                                     "Pick a sample (Learn…) for Show me and Build it yourself.")
        layout.operator("fresing.learn_lessons", text="Learn…", icon="BOOKMARKS")


class FRESING_OT_hub_mode(bpy.types.Operator):
    """View, Show me or Build it yourself on a sample project of the Learning hub"""

    bl_idname = "fresing.hub_mode"
    bl_label = "Learning hub"
    bl_options = {"INTERNAL"}

    mode: EnumProperty(items=[(k, t, "") for k, t in MODES], options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        st = hub_state(context.scene)
        mode = getattr(props, "mode", "VIEW")
        what = {"VIEW": "View: the finished sample project with its stops – pick one, press Go and look",
                "SHOW": "Show me: the app does each step of the sample while you watch",
                "BUILD": "Build it yourself: you do each step where it glows, the app points and goes on"}[mode]
        if not st["in_hub"]:
            return what + ". Opens the Learn window with this way chosen: pick a sample there"
        if mode != "VIEW" and not st["lesson"]:
            return (f"{LESSON_COMING}: this sample gets Show me and Build it yourself with a later update. View shows "
                    "it finished")
        if st["mode"] == mode:
            return what + ". This is the way you are learning now"
        if mode != "VIEW" and st["mode"] != "VIEW":
            return what + ". Switches this lesson at once, at the step you are on"
        return what + ". Opens it as a project of its own (your changes here are asked about first)"

    def invoke(self, context, event):
        st = hub_state(context.scene)
        if st["in_hub"] and st["mode"] != self.mode and bpy.data.is_dirty and not (
                self.mode != "VIEW" and st["mode"] != "VIEW"):
            return context.window_manager.invoke_confirm(
                self, event, title="Open the other way to learn?", confirm_text="Open it",
                message="This project has changes that are not saved: they are lost. Save it first to keep them.")
        return self.execute(context)

    def execute(self, context):
        from . import lesson, ops_learning
        scene = context.scene
        st = hub_state(scene)
        if not st["in_hub"]:
            ops_learning.CHOSEN["mode"] = self.mode
            bpy.ops.fresing.learn_lessons("INVOKE_DEFAULT")
            return {"FINISHED"}
        if st["mode"] == self.mode:
            return {"FINISHED"}
        if self.mode != "VIEW" and not st["lesson"]:
            self.report({"INFO"}, f"{LESSON_COMING}: View shows this sample finished")
            return {"CANCELLED"}
        if self.mode == "VIEW":
            if not st["set"]:
                return {"CANCELLED"}
            lesson.stop()
            return bpy.ops.fresing.learn_view("EXEC_DEFAULT", set=st["set"])
        if st["mode"] != "VIEW":                  # Show me <-> Build it yourself: the same lesson, at once
            if lesson.running():
                lesson.set_mode(self.mode)
            else:
                lesson.start(scene, st["set"], self.mode)
            panels.redraw()
            return {"FINISHED"}
        ops_learning._open_later(st["set"], self.mode)     # from View: the lesson's own new project
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# What's next: its fold
# ---------------------------------------------------------------------------

def next_folded() -> bool:
    p = _prefs()
    return bool(p is not None and p.next_folded)


class FRESING_OT_next_fold(bpy.types.Operator):
    """Folds What's next to its title row, or opens it again. It stays as you leave it, also in other projects"""

    bl_idname = "fresing.next_fold"
    bl_label = "Open or fold What's next"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        p = _prefs()
        if p is None:
            return {"CANCELLED"}
        p.next_folded = not p.next_folded
        panels.redraw()
        return {"FINISHED"}


CLASSES = (FRESING_OT_left_fold, FRESING_OT_hub_mode, FRESING_OT_next_fold)
TOP = (FRESING_PT_left_quick,)               # first on the left panel
HUB = (FRESING_PT_hub,)                      # after the workspace switcher; then the stops and the Lesson
