"""The side panel's own headers, what is open, the section tabs, and who shows (task 0062).

Blender keeps a panel's open / closed state per panel name and gives an add-on no way to set it. The owner wants
sections 1–7 folded at every start, a section tab that opens its section, and (later) lessons that open the fold they
point into. So every panel of the Fresing tab is registered **without Blender's header** (``HIDE_HEADER``) and draws
its own title row, and the open set is the app's:

* ``install(classes)`` runs once before the classes are registered (``fresing_render._classes``). For each panel of
  the Fresing tab it keeps the class's own ``draw`` and puts one around it that draws the title row first (fold arrow,
  the class's ``draw_header`` icon, the title; the class's ``draw_header_preset`` state on the right) and the body
  only when the panel is open. A panel file needs no change for it. It also puts a ``poll`` on the class: a panel
  shows when its section's tab is chosen (or All), its parents are open and the project's workspace shows it.
  For each ``fresing.*`` operator it puts a ``poll`` that refuses it while the Client view's lock is on
  (``lock.ALLOWED`` is what still works).
* The open set (``is_open`` / ``set_open`` / ``open_to`` / ``fold_sections``) lives in this module, not in the
  project: it is no undo step and no change of the file. Sections start folded at every start and every load;
  sub-panels start as their class says (open unless ``DEFAULT_CLOSED``). With Preferences > "Keep sections as I left
  them" the set is written into the project when it is saved and read back when it opens.
* Click on a title = open / fold. **Ctrl+click = only this one stays open** (its neighbours on the same level fold).
* ``FRESING_UI_OPEN_FOLDS`` (screenshots of everything): every panel counts as open.

A panel drawn as a popover (the Make list) or called directly with a stand-in ``self`` (tests) draws its body
without a title row.
"""

from __future__ import annotations

import os

import bpy
from bpy.props import EnumProperty, StringProperty

from ..core import places

CATEGORY = "Fresing"
SECTIONS = list(places.SECTIONS)             # the seven section classes, in order
_ALL_OPEN = bool(os.environ.get("FRESING_UI_OPEN_FOLDS"))

PARENT: dict = {}            # panel class name -> its parent's ("" for a top panel), read from the classes
TITLE: dict = {}             # panel class name -> bl_label
DEFAULT_OPEN: set = set()    # what is open when nothing was changed: sub-panels without DEFAULT_CLOSED, top notices
OPEN: set = set()            # what is open now
_TAB = {"v": "ALL"}          # the section tab: "ALL" or "1" … "7" (a copy of the window manager's, read at every poll)
_PLAIN = set()               # panels that keep their own (header-less) drawing: the workspace row, the tabs


# ---------------------------------------------------------------------------
# the open set
# ---------------------------------------------------------------------------

def section_of(name: str) -> str:
    """The section a panel belongs to ("" for the panels above 1 Import)."""
    seen = set()
    while PARENT.get(name) and name not in seen:
        seen.add(name)
        name = PARENT[name]
    return name if name in places.SECTIONS else ""


def tab() -> str:
    return _TAB["v"]


def tab_section() -> str:
    """The section the chosen tab shows ("" for All)."""
    v = _TAB["v"]
    return SECTIONS[int(v) - 1] if v.isdigit() and 1 <= int(v) <= len(SECTIONS) else ""


def is_open(name: str) -> bool:
    return _ALL_OPEN or name in OPEN or (name in places.SECTIONS and name == tab_section())


def set_open(name: str, on: bool = True) -> None:
    (OPEN.add if on else OPEN.discard)(name)


def open_to(name: str) -> None:
    """Open a panel and every panel above it (a lesson points into it; a test wants to see it)."""
    seen = set()
    while name and name not in seen:
        seen.add(name)
        OPEN.add(name)
        name = PARENT.get(name, "")
    redraw()


def open_all() -> None:
    OPEN.update(PARENT)
    redraw()


def fold_sections() -> None:
    """The calm start: sections 1–7 folded, sub-panels as their class says."""
    OPEN.clear()
    OPEN.update(DEFAULT_OPEN)
    redraw()


def only(name: str) -> None:
    """Ctrl+click: this panel open, its neighbours on the same level folded."""
    parent = PARENT.get(name, "")
    for other, p in PARENT.items():
        if p == parent and other != name and (parent or other in places.SECTIONS):
            OPEN.discard(other)
    OPEN.add(name)


_ONLY: set = set()           # tests and pictures: when not empty, only these panels (and what is above them) show


def show_only(names=(), opened: bool = True) -> None:
    """For real-app tests and pictures: show only these panels of the Fresing tab (with the panels above them, so
    they can show at all), opened. ``show_only()`` without names shows everything again. The top of the tab
    (Workspace, tabs, Make …) is hidden too unless named."""
    _ONLY.clear()
    for name in names:
        n, seen = name, set()
        while n and n not in seen:
            seen.add(n)
            _ONLY.add(n)
            if opened or n != name:
                OPEN.add(n)
            n = PARENT.get(n, "")
    redraw()


NOTHING = "-"                # the saved open set of a project with everything folded ("" = nothing was saved)


def saved_text() -> str:
    return ",".join(sorted(OPEN)) or NOTHING


def restore(text: str) -> None:
    OPEN.clear()
    OPEN.update(n for n in (text or "").split(",") if n in PARENT)


def tab_check(scene) -> None:
    """Back to All when the chosen tab's section no longer shows (the workspace hides it)."""
    sec = tab_section()
    if not sec or scene is None:
        return
    from . import workspaces
    if workspaces.panel_hidden(scene, sec):
        _TAB["v"] = "ALL"
        wm = getattr(bpy.context, "window_manager", None)
        if wm is not None and hasattr(wm, "fresing_tab") and wm.fresing_tab != "ALL":
            wm.fresing_tab = "ALL"


def redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    if wm is None:
        return
    for win in wm.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _keep() -> bool:
    try:
        from . import prefs
        p = prefs.get()
        return bool(p is not None and p.keep_sections)
    except Exception:  # noqa: BLE001
        return False


def on_load(scene) -> None:
    """A project is open: sections folded – or, with the preference, as they were when it was saved."""
    s = getattr(scene, "fresing", None)
    if _keep() and s is not None and s.panels_open:
        restore(s.panels_open)
    else:
        OPEN.clear()
        OPEN.update(DEFAULT_OPEN)
    _TAB["v"] = "ALL"
    wm = getattr(bpy.context, "window_manager", None)
    if wm is not None and hasattr(wm, "fresing_tab") and wm.fresing_tab != "ALL":
        wm.fresing_tab = "ALL"


def on_save(scene) -> None:
    s = getattr(scene, "fresing", None)
    if s is None:
        return
    text = saved_text() if _keep() else ""
    if s.panels_open != text:
        s.panels_open = text


# ---------------------------------------------------------------------------
# who shows
# ---------------------------------------------------------------------------

def visible(name: str, context, folds: bool | None = None) -> bool:
    """Does this panel show now? The project's workspace must show it; and in the app's window (``folds``) its
    section's tab must be chosen (or All) and the panels above it open. Without a window (a script, a test, the
    render queue's background app) nothing is folded: there the answer is only whether the project shows it."""
    if _ONLY and name not in _ONLY:
        return False
    if folds is None:
        folds = not bpy.app.background
    if folds:
        win = getattr(context, "window", None)
        if win is not None and win.screen.get("fr_setup"):      # the Set-up window shows its own tab only
            return False
        sec = section_of(name)
        if sec:
            t = tab_section()
            if t and t != sec:
                return False
        p = PARENT.get(name, "")
        while p:
            if not is_open(p):
                return False
            p = PARENT.get(p, "")
    scene = getattr(context, "scene", None)
    if scene is not None:
        from . import workspaces
        if workspaces.panel_hidden(scene, name):
            return False
    return True


# ---------------------------------------------------------------------------
# the title row
# ---------------------------------------------------------------------------

class _Stand:
    """Stands in for a panel's ``self`` while its ``draw_header`` / ``draw_header_preset`` draw into a part of
    the app's title row: the same object, another ``layout``."""

    def __init__(self, real, layout):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "layout", layout)

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_real"), item)


def level_of(name: str) -> int:
    n, seen = 0, set()
    while PARENT.get(name) and name not in seen:
        seen.add(name)
        name = PARENT[name]
        n += 1
    return n


def draw_title(self, context, cls) -> bool:
    """The title row of a panel; True when its body is to be drawn."""
    name = cls.__name__
    layout = self.layout
    level = level_of(name)
    section = name in places.SECTIONS
    fixed = section and name == tab_section()          # the tab's own section cannot be folded
    opened = is_open(name)
    box = layout.box()
    row = box.row(align=True)
    if level == 0:
        row.scale_y = 1.15
    for _ in range(max(0, level - 1)):
        row.separator(factor=1.6)
    left = row.row(align=True)
    left.alignment = "LEFT"
    if fixed:
        left.label(text="", icon="BLANK1")
    else:
        op = left.operator("fresing.panel_toggle", text="", emboss=False,
                           icon="DOWNARROW_HLT" if opened else "RIGHTARROW")
        op.name = name
    head = getattr(cls, "draw_header", None)
    if head is not None:
        head(_Stand(self, left), context)
    title = TITLE.get(name, getattr(cls, "bl_label", name))
    if fixed:
        left.label(text=title)
    else:
        op = left.operator("fresing.panel_toggle", text=title, emboss=False)
        op.name = name
    right = row.row(align=True)
    right.alignment = "RIGHT"
    preset = getattr(cls, "draw_header_preset", None)
    if preset is not None:
        preset(_Stand(self, right), context)
    from . import ui
    hook = ui.HOOKS.get("header")
    if hook is not None:
        hook(left, name)
    return opened


def _make_draw(cls, body):
    def draw(self, context):
        if getattr(self, "is_popover", True):          # no such attribute: a stand-in, not Blender's panel
            return body(self, context)                 # a test's stand-in, or a popover: the body only
        if draw_title(self, context, cls):
            scene = getattr(context, "scene", None)
            if scene is not None:
                from . import workspaces
                if workspaces.panel_title_only(scene, cls.__name__):
                    return None            # shown for the sub-panels under it; its own functions are hidden
            return body(self, context)
        return None
    draw.__doc__ = body.__doc__
    draw._fr_body = body
    return draw


def _make_poll(cls, own):
    name = cls.__name__

    def poll(c, context):
        if not visible(name, context):
            return False
        return own(context) if own is not None else True
    return classmethod(poll)


def _make_op_poll(cls, own):
    from . import lock
    on = lock.ON

    def poll(c, context):
        if on[0] and lock.scene_locked(context):
            c.poll_message_set(lock.MESSAGE)
            return False
        return own(context) if own is not None else True
    return classmethod(poll)


def body_of(cls):
    """The panel's own ``draw`` (its body, without the title row): the Make list draws it in a popover."""
    return getattr(cls.draw, "_fr_body", cls.draw)


def install(classes) -> None:
    """Run once over the classes before they are registered (safe to run again)."""
    from . import lock
    panels = [c for c in classes if isinstance(c, type) and issubclass(c, bpy.types.Panel)]
    for cls in panels:
        if (getattr(cls, "bl_space_type", "") != "VIEW_3D" or getattr(cls, "bl_region_type", "") != "UI"
                or getattr(cls, "bl_category", "") != CATEGORY):
            continue
        name = cls.__name__
        PARENT[name] = getattr(cls, "bl_parent_id", "") or ""
        TITLE[name] = getattr(cls, "bl_label", name)
        if cls.__dict__.get("_fr_installed"):
            continue
        cls._fr_installed = True
        opts = set(getattr(cls, "bl_options", ()) or ())
        plain = "HIDE_HEADER" in opts                  # draws its own top (the workspace row, the tabs)
        if plain:
            _PLAIN.add(name)
        elif "DEFAULT_CLOSED" not in opts and name not in places.SECTIONS:
            DEFAULT_OPEN.add(name)
        cls.bl_options = (opts - {"DEFAULT_CLOSED"}) | {"HIDE_HEADER"}
        own = getattr(cls, "poll", None)
        cls.poll = _make_poll(cls, own)
        if not plain:
            cls.draw = _make_draw(cls, cls.draw)
    for cls in classes:
        if not (isinstance(cls, type) and issubclass(cls, bpy.types.Operator)):
            continue
        idname = getattr(cls, "bl_idname", "")
        if not idname.startswith("fresing.") or lock.allowed(idname) or cls.__dict__.get("_fr_installed"):
            continue
        cls._fr_installed = True
        cls.poll = _make_op_poll(cls, getattr(cls, "poll", None))
    if not OPEN:
        OPEN.update(DEFAULT_OPEN)


# ---------------------------------------------------------------------------
# the operator behind every title, the tabs
# ---------------------------------------------------------------------------

class FRESING_OT_panel_toggle(bpy.types.Operator):
    """Opens or folds this part of the side panel. Ctrl+click: only this one stays open, the others on its
    level fold – the quick way to a calm panel"""

    bl_idname = "fresing.panel_toggle"
    bl_label = "Open or fold"
    bl_options = {"INTERNAL"}

    name: StringProperty(options={"SKIP_SAVE"})
    only: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})

    def invoke(self, context, event):
        self.only = bool(event.ctrl)
        return self.execute(context)

    def execute(self, context):
        if self.name not in PARENT:
            return {"CANCELLED"}
        if self.only:
            only(self.name)
            try:
                from . import prefs
                p = prefs.get()
                if p is not None and not p.knows_ctrl_click:
                    p.knows_ctrl_click = True
            except Exception:  # noqa: BLE001
                pass
        else:
            set_open(self.name, self.name not in OPEN)
        redraw()
        return {"FINISHED"}


class FRESING_OT_panel_tab(bpy.types.Operator):
    """Shows one section of the side panel at a time, opened – or all seven again"""

    bl_idname = "fresing.panel_tab"
    bl_label = "Section"
    bl_options = {"INTERNAL"}

    tab: StringProperty(default="ALL", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        t = properties.tab
        if t.isdigit() and 1 <= int(t) <= len(SECTIONS):
            title = list(places.SECTIONS.values())[int(t) - 1]
            return (f"Shows only {title}, opened: the other sections are out of the way until you click All "
                    "again")
        if t == "ALL":
            return "Shows every section again, each folded or open as you left it"
        return "Shows only this section of the side panel, opened: the others are out of the way until you click All"

    def execute(self, context):
        t = self.tab if self.tab == "ALL" or (self.tab.isdigit() and 1 <= int(self.tab) <= len(SECTIONS)) else "ALL"
        if t != "ALL":
            from . import workspaces
            if workspaces.panel_hidden(context.scene, SECTIONS[int(t) - 1]):
                self.report({"INFO"}, "This project's workspace does not show that section")
                t = "ALL"
        context.window_manager.fresing_tab = t
        return {"FINISHED"}


def _tab_changed(self, context):
    _TAB["v"] = self.fresing_tab
    redraw()


def _tab_items():
    items = [("ALL", "All", "Shows every section, each folded or open as you left it")]
    for i, title in enumerate(places.SECTIONS.values(), 1):
        items.append((str(i), str(i), f"Shows only {title}, opened: the others are out of the way until you click "
                                      "All again"))
    return items


CLASSES = (FRESING_OT_panel_toggle, FRESING_OT_panel_tab)


def register() -> None:
    bpy.types.WindowManager.fresing_tab = EnumProperty(
        name="Section", items=_tab_items(), default="ALL", update=_tab_changed, options={"SKIP_SAVE"},
        description="Which section of the side panel shows: all seven, or one at a time")
    bpy.types.WindowManager.fresing_fold_open = bpy.props.BoolProperty(
        name="Open", default=True, options={"SKIP_SAVE"},
        description="A fold a lesson points into is open while the lesson is there")
    _TAB["v"] = "ALL"
    _ONLY.clear()
    OPEN.clear()
    OPEN.update(DEFAULT_OPEN)


def unregister() -> None:
    for attr in ("fresing_tab", "fresing_fold_open"):
        if hasattr(bpy.types.WindowManager, attr):
            delattr(bpy.types.WindowManager, attr)
