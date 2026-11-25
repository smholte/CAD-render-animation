"""The side panel's own headers, what is open, the section tabs, and who shows (task 0062).

Blender keeps a panel's open / closed state per panel name and gives an add-on no way to set it. The owner wants
sections 1–8 folded at every start, a section tab that opens its section, and (later) lessons that open the fold they
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
SECTIONS = list(places.SECTIONS)             # the section classes, in order (8 since task 0201)
_ALL_OPEN = bool(os.environ.get("FRESING_UI_OPEN_FOLDS"))

PARENT: dict = {}            # panel class name -> its parent's ("" for a top panel), read from the classes
TITLE: dict = {}             # panel class name -> bl_label
DEFAULT_OPEN: set = set()    # what is open when nothing was changed: sub-panels without DEFAULT_CLOSED, top notices
OPEN: set = set()            # what is open now
_TAB = {"v": "ALL"}          # the section tab: "ALL" or "1" … "8" (a copy of the window manager's, read at every poll)
_PLAIN = set()               # panels that keep their own (header-less) drawing: the workspace row, the tabs
LEFT: set = set()            # task 0260: the panels of the left panel (the 3D view's toolbar region, ``ui_left.py``)
QUICK = "FRESING_PT_left_quick"     # … the one that shows also in the folded strip
SIDE_MARKS = ("fr_setup", "fr_output", "fr_settings", "fr_form",    # Set-up, output windows (task 0260),
              "fr_first_setup",                                 # + the first-start set-up (task 0276)
              "fr_materials")                                   # + the Materials window (task 0273)
#                                                    Settings (task 0271), function windows (task 0282)


def side_window(win) -> bool:
    """A window of the app's own (the Set-up window, an output window of Make): no left panel, no steps, never
    tidied like the main window."""
    try:
        screen = win.screen if win is not None else None
        return bool(screen is not None and any(screen.get(m) for m in SIDE_MARKS))
    except (AttributeError, ReferenceError):
        return False


def is_left(cls) -> bool:
    return (getattr(cls, "bl_space_type", "") == "VIEW_3D" and getattr(cls, "bl_region_type", "") == "TOOLS"
            and bool(getattr(cls, "_fr_left", False)))


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
    if not _LEFT_DONE and name in LEFT:                # the first look after the app started: the user's folds
        apply_left()
    return _ALL_OPEN or name in OPEN or (name in places.SECTIONS and name == tab_section())


def set_open(name: str, on: bool = True) -> None:
    (OPEN.add if on else OPEN.discard)(name)


# task 0278: the sections of the left panel keep the fold the user gave them – per user, in a small file in Blender's
# settings folder (``ui_left.STORE``: Blender does not keep an extension's own preferences over a restart while the app
# template is on), so a restart, another project and an update keep it. Only the user's own click
# (``FRESING_OT_panel_toggle``) is remembered; a lesson, a test or a picture that opens a panel is not.

def left_saved() -> dict:
    """The folds the user gave the left panel's sections: {panel name: open}."""
    from . import ui_left
    return ui_left.store().get("open", {})


def remember_left(name: str, on: bool) -> None:
    if name not in LEFT:
        return
    from . import ui_left
    opened = dict(left_saved())
    opened[name] = bool(on)
    ui_left.store_set(open=opened)


_LEFT_DONE: list = []          # not empty once the user's folds were put back since the app started


def apply_left() -> None:
    """Put the left panel's sections as the user left them (after the open set was reset)."""
    from . import ui_left
    if not ui_left._usable():                # a background Blender (queue, PC check): nothing of the user's
        return
    if not _LEFT_DONE:
        _LEFT_DONE.append(True)
    for name, on in left_saved().items():
        if name in LEFT:
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
    """The calm start: sections 1–8 folded, sub-panels as their class says."""
    OPEN.clear()
    OPEN.update(DEFAULT_OPEN)
    apply_left()
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
    apply_left()
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
        if side_window(win):                  # the Set-up window and the output windows show their own tab only
            return False
        if name in LEFT and name != QUICK:    # task 0260: the left panel folded to its strip
            from . import ui_left
            if ui_left.strip(context):
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


class _Toggling:
    """A layout whose plain labels (an icon, a short state) are the title row's own toggle buttons (task 0335): a
    click on them opens / folds the panel, as on Blender's own panels. Everything else passes through."""

    def __init__(self, layout, name, fixed):
        object.__setattr__(self, "_l", layout)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_fixed", fixed)

    def label(self, *args, **kw):
        lay = object.__getattribute__(self, "_l")
        if object.__getattribute__(self, "_fixed") or args or "icon_value" in kw or kw.get("translate") is False:
            return lay.label(*args, **kw)
        op = lay.operator("fresing.panel_toggle", text=kw.get("text", ""), icon=kw.get("icon", "NONE"), emboss=False)
        op.name = object.__getattribute__(self, "_name")
        return None

    def row(self, *args, **kw):
        sub = object.__getattribute__(self, "_l").row(*args, **kw)
        return _Toggling(sub, object.__getattribute__(self, "_name"), object.__getattribute__(self, "_fixed"))

    def __getattr__(self, item):
        return getattr(object.__getattribute__(self, "_l"), item)

    def __setattr__(self, item, value):
        setattr(object.__getattribute__(self, "_l"), item, value)


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
        head(_Stand(self, _Toggling(left, name, fixed)), context)
    from . import ui
    hook = ui.HOOKS.get("header")
    if hook is not None:
        hook(left, name)
    title = TITLE.get(name, getattr(cls, "bl_label", name))
    mid = row.row(align=True)                          # the title takes the rest of the row: all of it is the toggle
    if fixed:
        mid.alignment = "LEFT"
        mid.label(text=title)
    else:
        op = mid.operator("fresing.panel_toggle", text=title, emboss=False)
        op.name = name
    right = row.row(align=True)
    right.alignment = "RIGHT"
    preset = getattr(cls, "draw_header_preset", None)
    if preset is not None:
        preset(_Stand(self, _Toggling(right, name, fixed)), context)
    return opened


def _make_draw(cls, body):
    def draw(self, context):
        if getattr(self, "is_popover", True):          # no such attribute: a stand-in, not Blender's panel
            return body(self, context)                 # a test's stand-in, or a popover: the body only
        try:
            self.layout.context_string_set("fr_panel", cls.__name__)    # task 0181: a click knows its panel
        except Exception:  # noqa: BLE001
            pass
        if not C_PANEL["tried"]:                       # task 0367: Blender's C panels of the side panel
            _note_panel(self, cls)
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


# ---------------------------------------------------------------------------
# task 0367: Blender's "Transform" panel (tab Item) is C code – hidden outside Full access by its poll
# ---------------------------------------------------------------------------
#
# Blender's side-panel tabs are hidden by registering their Python panel classes again with a ``poll``
# (``ops_settings.quiet_panels``, task 0332). The tab Item's "Transform" panel is no Python class: registering a Python
# panel of that name REPLACES it for good (measured), and with it shown the Item tab stays beside Fresing whenever a part
# is selected. Blender keeps every panel of the 3D view's side panel in one list of panel types (C ``PanelType``:
# next, prev, idname at 16, label at 80, category at 284, flag at 688, poll at 696, draw at 720 in Blender 5.2.3 –
# read on its Linux build; the struct is plain C++ without platform types, the same on Windows x64). While the window is
# quiet the Transform panel's ``poll`` is the one of Blender's own Vertex Weights panel (``VIEW3D_PT_vgroup``, same tab,
# same signature: true only in Edit / Weight Paint with weights, false in Object Mode) – so the tab Item is gone in
# Object Mode, Blender's other modes (only reached in Full access) keep it – and Full access writes Blender's own back.
# Nothing is written unless every field read matches: the list is reached from a Fresing panel being drawn (its
# ``Panel`` holds its type at 16), whose idname, category "Fresing", HIDE_HEADER flag, poll and draw must all be
# right, and both C panels must be found by idname, label and category. Another Blender version: nothing is touched.

C_PANEL = {"tried": False, "transform": 0, "own": 0, "other": 0, "hidden": False, "want": None}
C_OFF = {"next": 0, "prev": 8, "idname": 16, "label": 80, "category": 284, "flag": 688, "poll": 696, "draw": 720,
         "panel_type": 16}
C_HIDDEN = ("VIEW3D_PT_transform",)          # what this hides (tests, the PC check)
_NO_HEADER = 2                               # PANEL_TYPE_NO_HEADER


def _ptr(addr: int) -> int:
    import ctypes
    return ctypes.c_void_p.from_address(addr).value or 0


def _text(addr: int) -> bytes:
    import ctypes
    return ctypes.string_at(addr, 64).split(b"\0")[0]


def _note_panel(panel, cls) -> None:
    """At the first draw of a Fresing side-panel panel: find Blender's Transform panel type (see above)."""
    if getattr(cls, "bl_region_type", "") != "UI":
        return                               # the left panel's types are another list
    C_PANEL["tried"] = True
    try:
        found = _find_c_panels(panel.as_pointer(), cls)
    except Exception as exc:  # noqa: BLE001 - Blender's Item tab then stays
        print("Fresing Render: Blender's Transform panel not found:", exc)
        return
    if found is None:
        print("Fresing Render: Blender's Transform panel not found for certain; its tab Item stays")
        return
    C_PANEL["transform"], C_PANEL["own"], C_PANEL["other"] = found
    if C_PANEL["want"] is not None:
        hide_c_panels(C_PANEL["want"])


def _find_c_panels(panel_addr: int, cls):
    """(Transform's type, its own poll, Vertex Weights' poll) or None when anything read does not match."""
    if bpy.app.version[:2] != (5, 2) or not panel_addr or getattr(cls, "bl_region_type", "") != "UI":
        return None
    o = C_OFF
    pt = _ptr(panel_addr + o["panel_type"])
    if not pt or pt % 8:
        return None
    import ctypes
    idname = (getattr(cls, "bl_idname", "") or cls.__name__).encode()
    if (_text(pt + o["idname"]) != idname or _text(pt + o["category"]) != CATEGORY.encode()
            or not ctypes.c_int.from_address(pt + o["flag"]).value & _NO_HEADER
            or not _ptr(pt + o["poll"]) or not _ptr(pt + o["draw"])):
        return None
    head, steps = pt, 0
    while _ptr(head + o["prev"]) and steps < 5000:
        head, steps = _ptr(head + o["prev"]), steps + 1
    types, p, steps = {}, head, 0
    while p and steps < 5000:
        name = _text(p + o["idname"])
        if name in (b"VIEW3D_PT_transform", b"VIEW3D_PT_vgroup"):
            types[name] = p
        p, steps = _ptr(p + o["next"]), steps + 1
    t, v = types.get(b"VIEW3D_PT_transform"), types.get(b"VIEW3D_PT_vgroup")
    if not t or not v:
        return None
    if (_text(t + o["label"]) != b"Transform" or _text(t + o["category"]) != b"Item"
            or _text(v + o["label"]) != b"Vertex Weights" or _text(v + o["category"]) != b"Item"):
        return None
    own, other = _ptr(t + o["poll"]), _ptr(v + o["poll"])
    if not own or not other or not _ptr(t + o["draw"]) or own == other:
        return None
    return t, own, other


def hide_c_panels(hide: bool) -> bool:
    """Blender's Transform panel (tab Item) hidden (quiet window) or Blender's own again. True when it is as asked;
    False while its type is not found yet (the next Fresing panel draw tries) or cannot be found."""
    import ctypes
    hide = bool(hide)
    C_PANEL["want"] = hide
    t = C_PANEL["transform"]
    if not t:
        return False
    slot = ctypes.c_void_p.from_address(t + C_OFF["poll"])
    now = slot.value or 0
    if now not in (C_PANEL["own"], C_PANEL["other"]):      # someone else changed it: leave it alone
        return False
    slot.value = C_PANEL["other"] if hide else C_PANEL["own"]
    C_PANEL["hidden"] = hide
    return True


def c_panels_hidden() -> bool:
    """Is Blender's Transform panel hidden now? (tests, the PC check)"""
    return bool(C_PANEL["hidden"])


def install(classes) -> None:
    """Run once over the classes before they are registered (safe to run again)."""
    from . import lock
    panels = [c for c in classes if isinstance(c, type) and issubclass(c, bpy.types.Panel)]
    for cls in panels:
        left = is_left(cls)
        if not left and (getattr(cls, "bl_space_type", "") != "VIEW_3D" or getattr(cls, "bl_region_type", "") != "UI"
                         or getattr(cls, "bl_category", "") != CATEGORY):
            continue
        name = cls.__name__
        if left:
            LEFT.add(name)
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
    from . import usage
    for cls in classes:                                # task 0181: every fresing.* button counts its clicks
        if isinstance(cls, type) and issubclass(cls, bpy.types.Operator):
            usage.wrap(cls)
    if not OPEN:
        OPEN.update(DEFAULT_OPEN)
        apply_left()


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
        if self.name in LEFT:                          # task 0278: a left section keeps its fold after a restart
            remember_left(self.name, self.name in OPEN)
        if self.name in OPEN:
            try:
                from . import usage
                usage.panel_opened(self.name)          # task 0181: opening a panel is a use of it
            except Exception:  # noqa: BLE001
                pass
        redraw()
        return {"FINISHED"}


class FRESING_OT_panel_tab(bpy.types.Operator):
    """Shows one section of the side panel at a time, opened – or all of them again"""

    bl_idname = "fresing.panel_tab"
    bl_label = "Section"
    bl_options = {"INTERNAL"}

    tab: StringProperty(default="ALL", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return tab_tip(properties.tab)       # task 0278 (owner 22:45): short – the longer words are in the guide

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


ALL_TIP = "All sections"


def tab_tip(tab: str) -> str:
    """A section tab's tooltip: only the section's name ("Import", "Lifting plan"); All: "All sections"."""
    if tab.isdigit() and 1 <= int(tab) <= len(SECTIONS):
        return list(places.SECTIONS.values())[int(tab) - 1].split(" ", 1)[1]
    return ALL_TIP


def _tab_items():
    return [("ALL", "All", ALL_TIP)] + [(str(i), str(i), tab_tip(str(i))) for i in range(1, len(places.SECTIONS) + 1)]


CLASSES = (FRESING_OT_panel_toggle, FRESING_OT_panel_tab)


def register() -> None:
    bpy.types.WindowManager.fresing_tab = EnumProperty(
        name="Section", items=_tab_items(), default="ALL", update=_tab_changed, options={"SKIP_SAVE"},
        description=f"Which section of the side panel shows: all {len(places.SECTIONS)}, or one at a time")
    bpy.types.WindowManager.fresing_fold_open = bpy.props.BoolProperty(
        name="Open", default=True, options={"SKIP_SAVE"},
        description="A fold a lesson points into is open while the lesson is there")
    _TAB["v"] = "ALL"
    _ONLY.clear()
    OPEN.clear()
    OPEN.update(DEFAULT_OPEN)


def unregister() -> None:
    if C_PANEL["hidden"]:
        hide_c_panels(False)                 # task 0367: Blender's own poll back before the extension goes
    C_PANEL.update(tried=False, want=None)
    for attr in ("fresing_tab", "fresing_fold_open"):
        if hasattr(bpy.types.WindowManager, attr):
            delattr(bpy.types.WindowManager, attr)
