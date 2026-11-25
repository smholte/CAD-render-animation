"""A quiet window (task 0241, study 0222 package A).

Outside Blender's-UI workspaces (everything but Full access) a user who does not know Blender sees only what views the
model and the app's own buttons:

* **the 3D view header**: the editor-type button, the View menu, gizmos, overlays, X-ray and shading (Solid /
  Material / Live preview) and the app's Make / Fresing buttons – no Object Mode menu, no Select / Add / Object menus, no
  transform orientation, pivot, snapping, proportional editing, no "Selectability & visibility" drop-down. In any mode
  other than Object Mode (reached in Full access) Blender's own header is drawn: never without the mode menu there;
* **the tool header row** (select-box buttons, Options) off in every 3D view – from a timer that waits until Blender's
  column (task 0221) is closed and the view was drawn (``editors.settled``: setting a 3D view's settings right after a
  screen change crashed Blender 5.2.3);
* **the top bar's right part**: no Scene and View Layer selectors;
* **the splash**: below the welcome / What's new box (``welcome.py``) Fresing's lines only – New project, Open…,
  Recover Last Session, the recent files, Take the test tour, Demo project, User guide;
* **File > New** (and Ctrl+N, which opens the same menu): only New project = what a fresh app start gives;
* **Edit** (task 0332, 0328 row 7): Undo, Redo, Undo History, Menu Search and Fresing Settings – no Rename Active Item,
  Batch Rename, Lock Object Modes or Blender's Preferences (F2 / Ctrl+F2 / Ctrl+, are swallowed in lock.py); the F4
  file menu likewise without Preferences, Link, Append, Import and Export;
* **File, Render, Window, Help** (task 0367, study 0222 package C): File keeps New project, Open, Open Recent, Revert,
  Recover, Save, Save As, Save Copy, the app's Import STEP… / Import mesh model… / Import House Planner scene… (the
  last two were in Blender's File > Import list) and Quit (no Link, Append, Data Previews,
  Export, External Data, Clean Up, Defaults; the Client view keeps lock.py's shorter one); Render = the app's Render
  image, Render animation, Render queue and View last render (F11); Window = Toggle Window Fullscreen, Show Status Bar,
  Save Screenshot (Ctrl+Page Up / Down are swallowed in lock.py); Help = Fresing's lines, Blender's own (Manual,
  Support … Report a Bug, Save System Info) in one sub-menu "Blender" at the bottom;
* **the side panel's tabs** (task 0332 + 0367): Blender's Tool, View, Animation, Item and glTF Variants are hidden
  (``ops_settings.quiet_panels`` for their Python panels, ``panels.hide_c_panels`` for the Item tab's C panel
  "Transform"); another add-on's tab stays;
* **the picture after a render** (task 0332, row 13): the image editor's header of a Render Result says what was saved
  in the app's words – Open, Show in folder, Close – instead of slots, view layer and passes; Blender's text over the
  finished picture ("Frame:1 | Time … | Mem …") is switched off (it shows while the render runs);
* **the redo panel** ("Adjust Last Operation", bottom left of the 3D view) off in every 3D view (task 0332, row 28);
* **back to the app's layout** (task 0332, row 5): a Blender workspace tab picked in Full access (Animation, Shading …)
  is left again when the window turns quiet – the main window goes back to the Blender workspace it had when Full
  access began (else "Layout", the app's own), so Back to the Fresing window never strands the user without tabs.

Everything switches with ``lock.blender_ui`` (the one switch of Blender's own tabs, task 0062): Full access, or
Fresing > Show all of Blender, brings it all back at once.

**Appended draw functions survive.** Blender keeps a class's own ``draw`` and every add-on's appended / prepended
function in one list (``cls.draw._draw_funcs``). Only Blender's own entry in that list is swapped for the quiet one
(``_swap``), so Make, the Fresing button, the welcome box and any other add-on's items are drawn as before; the top
bar's right part is a method of its own (``draw_right``) and is replaced like lock.py replaces ``draw_left``.

Nothing here runs in a background Blender (queue render, PC check, self-test, kits).
"""

from __future__ import annotations

import json

import bpy

from .panels import side_window

ON = [False]                  # the quiet window is drawn
_SEEN_LOUD = [False]          # task 0332: Blender's own drawing was on since the start (Full access was used)
KEEP = "fr_ws_before_all"     # per scene: the workspace Show all of Blender came from (JSON of the three fields)
DRAWN = {"header": 0, "header_blender": 0, "splash": 0, "file_new": 0, "edit": 0, "file_context": 0, "image": 0,
         "file": 0, "render": 0, "window": 0, "help": 0, "help_blender": 0}   # draws counted (tests, the PC check)
LOCKED_TEXT = "Not in the Client view – Workspace > Full access unlocks it"
SHOW_TEXT = "Show all of Blender"
BACK_TEXT = "Back to the Fresing window"
APP_LAYOUT = "Layout"         # the Blender workspace that holds the app's layout (a fresh start's, the app template's)
EDIT_KEEPS = ("ed.undo", "ed.redo", "TOPBAR_MT_undo_history", "wm.search_menu", "fresing.settings")
EDIT_DROPS = ("wm.call_panel", "wm.batch_rename", "lock_object_mode", "screen.userpref_show")
# task 0367: what the quiet File / Render / Window menus hold, in order (tests, the PC check) and what they leave out
FILE_KEEPS = ("wm.read_homefile", "wm.open_mainfile", "TOPBAR_MT_file_open_recent", "wm.revert_mainfile",
              "TOPBAR_MT_file_recover", "fresing.save", "fresing.save_as", "wm.save_as_mainfile",
              "fresing.import_step", "fresing.import_mesh", "fresing.house_import", "wm.quit_blender")
FILE_DROPS = ("wm.link", "wm.append", "TOPBAR_MT_file_previews", "TOPBAR_MT_file_import", "TOPBAR_MT_file_export",
              "wm.collection_export_all", "TOPBAR_MT_file_external_data", "TOPBAR_MT_file_cleanup",
              "TOPBAR_MT_file_defaults")
RENDER_KEEPS = ("fresing.render", "fresing.key_render", "fresing.make_window", "render.view_show")
RENDER_DROPS = ("render.render", "sound.mixdown", "render.play_rendered_anim", "use_lock_interface")
WINDOW_KEEPS = ("wm.window_fullscreen_toggle", "show_statusbar", "screen.screenshot")
WINDOW_DROPS = ("wm.window_new", "wm.window_new_main", "screen.workspace_cycle", "screen.screenshot_area",
                "wm.console_toggle", "wm.set_stereo_3d")
HELP_MENU = "TOPBAR_MT_fresing_help_blender"

# what the quiet 3D view header keeps (tests, the PC check)
HEADER_KEEPS = ("editor type", "View menu", "gizmos", "overlays", "X-ray", "shading")
HEADER_DROPS = ("Object Mode", "Select", "Add", "Object", "transform orientation", "pivot", "snapping",
                "proportional editing", "Selectability & visibility")


# ---------------------------------------------------------------------------
# swapping Blender's own entry in a draw list
# ---------------------------------------------------------------------------

_SWAPPED: dict = {}           # class name -> (Blender's own draw, the quiet one)
_PATCHED: dict = {}           # (class name, attribute) -> the original method


def draw_funcs(cls) -> list:
    """The class's list of draw functions (Blender's own + the appended ones), made if it has none yet."""
    return cls._dyn_ui_initialize()


def _own(cls, funcs):
    """Blender's own ``draw`` of this class inside its draw list (the add-ons' functions have other names)."""
    wants = [k.__name__ + ".draw" for k in cls.__mro__ if "draw" in k.__dict__ and k.__name__ != "_GenericUI"]
    for want in wants or [cls.__name__ + ".draw"]:      # task 0260: a panel may draw with its base class's draw
        i = next((i for i, f in enumerate(funcs) if getattr(f, "__qualname__", "") == want
                  or getattr(f, "__qualname__", "").endswith("." + want)), -1)
        if i >= 0:
            return i
    return -1


def swap(cls, quiet_fn) -> bool:
    """Draw ``quiet_fn`` in place of Blender's own draw of ``cls``; every appended / prepended function stays where it
    is. True when it is swapped (now or before)."""
    name = cls.__name__
    if name in _SWAPPED:
        return True
    funcs = draw_funcs(cls)
    i = _own(cls, funcs)
    if i < 0:
        return False
    _SWAPPED[name] = (funcs[i], quiet_fn)
    funcs[i] = quiet_fn
    return True


def unswap(cls) -> None:
    pair = _SWAPPED.pop(cls.__name__, None)
    if pair is None:
        return
    orig, quiet_fn = pair
    funcs = draw_funcs(cls)
    for i, f in enumerate(funcs):
        if f is quiet_fn:
            funcs[i] = orig


def blender_draw(cls):
    """Blender's own draw of a swapped class (the quiet one falls back to it); None when not swapped."""
    pair = _SWAPPED.get(cls.__name__)
    return pair[0] if pair else None


def _patch(cls, attr: str, fn) -> None:
    key = (cls.__name__, attr)
    if key not in _PATCHED:
        _PATCHED[key] = cls.__dict__.get(attr, getattr(cls, attr))
        setattr(cls, attr, fn)


def _unpatch(cls, attr: str) -> None:
    key = (cls.__name__, attr)
    if key in _PATCHED:
        setattr(cls, attr, _PATCHED.pop(key))


# ---------------------------------------------------------------------------
# the quiet drawings (based on Blender 5.2.3's own, scripts/startup/bl_ui and bl_operators/wm.py)
# ---------------------------------------------------------------------------

def _header(self, context):
    """The 3D view header: view the model, nothing to edit it with. Another mode than Object Mode: Blender's own."""
    if context.mode != "OBJECT":
        orig = blender_draw(bpy.types.VIEW3D_HT_header)
        if orig is not None:
            DRAWN["header_blender"] += 1
            return orig(self, context)
    DRAWN["header"] += 1
    layout = self.layout
    view = context.space_data
    shading = view.shading
    overlay = view.overlay
    layout.row(align=True).template_header()
    layout.menu("VIEW3D_MT_view")
    layout.separator_spacer()

    row = layout.row(align=True)                     # gizmo toggle & popover
    row.prop(view, "show_gizmo", text="", toggle=True, icon="GIZMO")
    sub = row.row(align=True)
    sub.active = view.show_gizmo
    sub.popover(panel="VIEW3D_PT_gizmo_display", text="")

    row = layout.row(align=True)                     # overlay toggle & popover
    row.prop(overlay, "show_overlays", icon="OVERLAY", text="")
    sub = row.row(align=True)
    sub.active = overlay.show_overlays
    sub.popover(panel="VIEW3D_PT_overlay", text="")

    row = layout.row()                               # X-ray
    row.active = shading.type in {"WIREFRAME", "SOLID"}
    try:
        from bl_ui.space_view3d import _toggle_xray_operator
        _toggle_xray_operator(row, context, text="")
    except Exception:  # noqa: BLE001 - Blender's helper moved: the plain toggle
        row.operator("view3d.toggle_xray", text="", icon="XRAY")

    row = layout.row(align=True)                     # shading
    row.prop(shading, "type", text="", expand=True)
    sub = row.row(align=True)
    sub.popover(panel="VIEW3D_PT_shading", text="")


def _draw_right(self, context):
    """The top bar's right part without the Scene and View Layer selectors."""
    layout = self.layout
    screen = context.screen
    if screen is not None and not screen.show_statusbar:
        layout.template_reports_banner()
        layout.template_running_jobs()


def template() -> str:
    """The app template a fresh start uses ('' = Blender's General, when the extension runs without the app)."""
    try:
        return bpy.context.preferences.app_template or ""
    except AttributeError:
        return ""


def new_project(layout, text: str = "New project"):
    props = layout.operator("wm.read_homefile", text=text, icon="FILE_NEW")
    props.app_template = template()
    return props


def _file_new(self, context):
    """File > New and Ctrl+N: only New project (the app's own start: mm, Cycles, the app's layout)."""
    DRAWN["file_new"] += 1
    layout = self.layout
    layout.operator_context = "INVOKE_DEFAULT"
    new_project(layout)


def _edit(self, context):
    """Edit (task 0332): undo, redo, search and the app's own settings – nothing that renames or opens Blender's
    Preferences (an extension can be switched off there; Fresing Settings holds the app's settings)."""
    DRAWN["edit"] += 1
    layout = self.layout
    layout.operator("ed.undo", icon="LOOP_BACK")
    layout.operator("ed.redo", icon="LOOP_FORWARDS")
    layout.menu("TOPBAR_MT_undo_history")
    layout.separator()
    layout.operator("wm.search_menu", text="Menu Search...", icon="VIEWZOOM")
    if _has("fresing.settings"):
        layout.separator()
        layout.operator("fresing.settings", text="Fresing Settings...", icon="PREFERENCES")


def _file_context(self, context):
    """F4's file menu (task 0332): New, Open, Open Recent – no Preferences, Link, Append, Import or Export."""
    DRAWN["file_context"] += 1
    layout = self.layout
    layout.operator_context = "INVOKE_AREA"
    layout.menu("TOPBAR_MT_file_new", text="New", icon="FILE_NEW")
    layout.operator("wm.open_mainfile", text="Open...", icon="FILE_FOLDER")
    layout.menu("TOPBAR_MT_file_open_recent")


def _op(layout, idname: str, **kw):
    """An app operator line; left out when the operator is not registered (the extension without the app)."""
    if idname.startswith("fresing.") and not _has(idname):
        return None
    return layout.operator(idname, **kw)


def _file(self, context):
    """File (task 0367): open, save and quit, and the app's two imports – no Link, Append, Blender's Import / Export
    lists, External Data, Clean Up or Defaults. Save and Save As are the app's (task 0291: a new project's name)."""
    DRAWN["file"] += 1
    layout = self.layout
    layout.operator_context = "INVOKE_AREA"
    new_project(layout)
    layout.operator("wm.open_mainfile", text="Open...", icon="FILE_FOLDER")
    layout.menu("TOPBAR_MT_file_open_recent")
    layout.operator("wm.revert_mainfile")
    layout.menu("TOPBAR_MT_file_recover")
    layout.separator()
    if _has("fresing.save"):
        layout.operator("fresing.save", text="Save", icon="FILE_TICK")
    else:
        layout.operator("wm.save_mainfile", text="Save", icon="FILE_TICK")
    if _has("fresing.save_as"):
        layout.operator("fresing.save_as", text="Save As...")
    else:
        layout.operator("wm.save_as_mainfile", text="Save As...")
    copy = layout.operator("wm.save_as_mainfile", text="Save Copy...")
    copy.copy = True
    layout.separator()
    _op(layout, "fresing.import_step", text="Import STEP...", icon="IMPORT")
    _op(layout, "fresing.import_mesh", text="Import mesh model...", icon="IMPORT")
    _op(layout, "fresing.house_import", text="Import House Planner scene...", icon="IMPORT")   # (task 0114)
    layout.separator()
    layout.operator("wm.quit_blender", text="Quit", icon="QUIT")


def _render(self, context):
    """Render (task 0367): the app's renders – the picture of the active camera, the selected animation, the render
    queue – and the last render again (F11). Blender's own Render Image / Animation would skip the app's settings."""
    DRAWN["render"] += 1
    layout = self.layout
    layout.operator_context = "INVOKE_DEFAULT"
    _op(layout, "fresing.render", text="Render Image", icon="RENDER_STILL")
    props = _op(layout, "fresing.key_render", text="Render Animation", icon="RENDER_ANIMATION")
    if props is not None:
        props.animation = True
    props = _op(layout, "fresing.make_window", text="Render Queue...", icon="SORTTIME")
    if props is not None:
        props.key = "queue"
    layout.separator()
    layout.operator("render.view_show", text="View Last Render", icon="IMAGE")


def _window(self, context):
    """Window (task 0367): full screen, the status bar and a screenshot – no new windows and no Next / Previous
    Workspace (they lead to Blender's workspaces, whose tabs are hidden)."""
    DRAWN["window"] += 1
    layout = self.layout
    layout.operator("wm.window_fullscreen_toggle", icon="FULLSCREEN_ENTER")
    layout.separator()
    if context.screen is not None:
        layout.prop(context.screen, "show_statusbar")
    layout.separator()
    layout.operator("screen.screenshot", text="Save Screenshot...")


def _help(self, context):
    """Help (task 0367): Blender's own lines are not drawn here – the sub-menu "Blender" at the bottom holds them."""
    DRAWN["help"] += 1


def _help_blender_line(self, context):
    """The last line of the quiet Help menu: Blender's own help in one sub-menu (appended last, see ``apply``)."""
    if not ON[0]:
        return
    layout = self.layout
    layout.separator()
    layout.menu(HELP_MENU, text="Blender", icon="BLENDER")


class TOPBAR_MT_fresing_help_blender(bpy.types.Menu):
    """Blender's own help: its manual, support and community pages, release notes, Report a Bug and Save System
    Info (for a bug report to Blender)"""

    bl_idname = HELP_MENU
    bl_label = "Blender"

    def draw(self, context):
        DRAWN["help_blender"] += 1
        help_cls = getattr(bpy.types, "TOPBAR_MT_help", None)
        orig = blender_draw(help_cls) if help_cls is not None else None
        if orig is None and help_cls is not None:
            funcs = draw_funcs(help_cls)
            i = _own(help_cls, funcs)
            orig = funcs[i] if i >= 0 else None
        if orig is not None:
            orig(self, context)


class _Rec:
    """A stand-in layout that writes down what a menu draws (tests, the PC check): operator ids, menu ids, props."""

    class _Props:
        def __setattr__(self, name, value):
            object.__setattr__(self, name, value)

    def __init__(self):
        self.seen = []
        self.operator_context = "INVOKE_DEFAULT"

    def operator(self, idname, **kw):
        self.seen.append(idname)
        return _Rec._Props()

    def menu(self, idname, **kw):
        self.seen.append(idname)

    def prop(self, data, name, **kw):
        self.seen.append(name)

    def label(self, **kw):
        self.seen.append("label:" + kw.get("text", ""))

    def separator(self, **kw):
        pass

    def row(self, **kw):
        return self

    def column(self, **kw):
        return self


def lines(draw_fn, context=None) -> list:
    """What a quiet menu draws, in order (``_file``, ``_render``, ``_window`` …): operator / menu ids and props."""
    rec = _Rec()

    class _S:
        layout = rec
    ctx = context if context is not None else bpy.context
    draw_fn(_S(), ctx)
    return rec.seen


def file_menu(self, context) -> bool:
    """project_name.py's File menu asks this first: True when the quiet File menu was drawn."""
    if not ON[0]:
        return False
    _file(self, context)
    return True


def render_words(scene) -> tuple:
    """What the header of the finished picture says (task 0332): (text, icon, the saved file or '')."""
    import os
    if bpy.app.is_job_running("RENDER"):
        return "Rendering – the picture is saved when it is done", "RENDER_STILL", ""
    s = getattr(scene, "fresing", None) if scene is not None else None
    path = getattr(s, "last_render", "") if s is not None else ""
    if path and os.path.exists(path):
        return "Saved: " + os.path.basename(path), "CHECKMARK", path
    return "The rendered picture", "IMAGE", ""


def render_areas():
    """Image editors (any window) that show a render."""
    wm = bpy.context.window_manager
    for win in (wm.windows if wm is not None else ()):
        for area in (win.screen.areas if win.screen is not None else ()):
            if area.type == "IMAGE_EDITOR":
                ima = getattr(area.spaces.active, "image", None)
                if ima is not None and ima.type == "RENDER_RESULT":
                    yield win, area


def render_info(show: bool) -> None:
    """Blender's text over a finished render ("Frame:1 | Time … | Mem …") on or off (task 0332: off while quiet; the
    header says what was saved). Set with the area in the context."""
    for win, area in list(render_areas()):
        ov = area.spaces.active.overlay
        if ov.show_text_info != show:
            region = next((r for r in area.regions if r.type == "WINDOW"), None)
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                ov.show_text_info = show


def _render_info_tick():
    try:
        if ON[0] and not bpy.app.is_job_running("RENDER"):
            render_info(False)
    except Exception as exc:  # noqa: BLE001 - cosmetic
        print("Fresing Render: render text not hidden:", exc)
    return None


def _image_header(self, context):
    """The header of Blender's image editor showing a render (task 0332, 0328 row 13): the View menu (zoom, fit) and
    the app's words – what was saved, Open, Show in folder, Close. Any other image, or another mode: Blender's own."""
    sima = context.space_data
    ima = getattr(sima, "image", None)
    if ima is None or ima.type != "RENDER_RESULT" or getattr(sima, "mode", "VIEW") != "VIEW":
        orig = blender_draw(bpy.types.IMAGE_HT_header)
        if orig is not None:
            return orig(self, context)
        return None
    DRAWN["image"] += 1
    if (getattr(sima, "overlay", None) is not None and sima.overlay.show_text_info
            and not bpy.app.is_job_running("RENDER") and not bpy.app.timers.is_registered(_render_info_tick)):
        bpy.app.timers.register(_render_info_tick, first_interval=0.0)    # nothing is set while drawing
    layout = self.layout
    layout.menu("IMAGE_MT_view", text="View")
    layout.operator("image.view_all", text="Fit", icon="FULLSCREEN_EXIT").fit_view = True
    layout.separator_spacer()
    text, icon, path = render_words(context.scene)
    layout.label(text=text, icon=icon)
    if path:
        row = layout.row(align=True)
        row.operator("fresing.open_file", text="Open", icon="IMAGE").path = path
        row.operator("fresing.show_in_folder", text="Show in folder", icon="FILE_FOLDER").path = path
    layout.separator_spacer()
    layout.operator("render.view_cancel", text="Close", icon="X")


def _has(idname: str) -> bool:
    from . import ui_topbar
    return ui_topbar._has(idname)


def splash_lines() -> list:
    """The operator ids of the splash's Fresing lines, in order (tests, the PC check)."""
    from . import ops_demo
    out = ["wm.read_homefile", "wm.open_mainfile", "wm.recover_last_session", "fresing.tour_take",
           ops_demo.FRESING_OT_demo_make.bl_idname, "fresing.user_guide"]
    return [i for i in out if not i.startswith("fresing.") or _has(i)]


def _splash(self, context):
    """Blender's splash with Fresing's lines only (the welcome / What's new box is prepended by welcome.py)."""
    from . import ops_demo
    DRAWN["splash"] += 1
    layout = self.layout
    layout.operator_context = "EXEC_DEFAULT"
    layout.emboss = "PULLDOWN_MENU"
    split = layout.split()

    col1 = split.column()
    col1.label(text="Start")
    col1.operator_context = "INVOKE_DEFAULT"
    new_project(col1)
    col1.operator("wm.open_mainfile", text="Open...", icon="FILE_FOLDER")
    col1.operator("wm.recover_last_session", icon="RECOVER_LAST")
    col1.separator()
    if _has("fresing.tour_take"):                    # the same operator as Fresing > Take the test tour
        col1.operator("fresing.tour_take", text="Open the Learning hub", icon="VIEW_CAMERA")
    if _has(ops_demo.FRESING_OT_demo_make.bl_idname):    # the same operator as Help > Make demo project…
        col1.operator(ops_demo.FRESING_OT_demo_make.bl_idname, text="Demo project", icon="MOD_OCEAN")
    if _has("fresing.user_guide"):
        col1.operator("fresing.user_guide", text="User guide", icon="HELP")

    col2 = split.column()
    title = col2.row()
    title.label(text="Recent Files")
    if col2.template_recent_files(rows=5):
        more = col2.column()
        more.operator_context = "INVOKE_DEFAULT"
        more.operator("wm.search_single_menu", text="More...", icon="VIEWZOOM").menu_idname = \
            "TOPBAR_MT_file_open_recent"
    else:
        col2.label(text="None yet")
    layout.separator()


# ---------------------------------------------------------------------------
# on and off
# ---------------------------------------------------------------------------

def _classes():
    t = bpy.types
    return ((getattr(t, "VIEW3D_HT_header", None), _header), (getattr(t, "WM_MT_splash", None), _splash),
            (getattr(t, "TOPBAR_MT_file_new", None), _file_new),
            (getattr(t, "TOPBAR_MT_edit", None), _edit),                     # task 0332: rows 7 and 13
            (getattr(t, "TOPBAR_MT_file_context_menu", None), _file_context),
            (getattr(t, "IMAGE_HT_header", None), _image_header),
            (getattr(t, "TOPBAR_MT_file", None), _file),                     # task 0367: package C (project_name.py
            (getattr(t, "TOPBAR_MT_render", None), _render),                 # swaps File first: then it asks
            (getattr(t, "TOPBAR_MT_window", None), _window),                 # ``file_menu``)
            (getattr(t, "TOPBAR_MT_help", None), _help),
            (getattr(t, "VIEW3D_PT_tools_active", None), _no_tools))      # task 0260: the left panel without Blender's tools


def _no_tools(self, context):
    """Task 0260: Blender's tool buttons are not drawn in the 3D view's toolbar region outside Full access – the region
    holds the app's left panel (``ui_left.py``); Full access (Show all of Blender) brings the tools back above it.
    Another mode than Object Mode: Blender's own (as the header)."""
    if context.mode != "OBJECT":
        orig = blender_draw(bpy.types.VIEW3D_PT_tools_active)
        if orig is not None:
            return orig(self, context)
    return None


def _views(include_setup: bool = False):
    wm = bpy.context.window_manager
    for win in (wm.windows if wm is not None else ()):
        if win.screen is None or (side_window(win) and not include_setup):
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                yield area


_TOOL = {"show": None, "tries": 0, "hud": None, "workspace": ""}
LOUD_WS = [""]                # task 0332: the main window's Blender workspace when Full access began ("" = not known)


def main_windows():
    wm = bpy.context.window_manager
    return [w for w in (wm.windows if wm is not None else ()) if w.screen is not None and not side_window(w)]


def back_workspace() -> str:
    """The Blender workspace the main window goes back to when it turns quiet (task 0332): the one it had when Full
    access began, else the app's own ("Layout"); '' when neither is in the file."""
    for name in (LOUD_WS[0], APP_LAYOUT):
        if name and bpy.data.workspaces.get(name) is not None:
            return name
    return ""


def _go_back_workspace() -> bool:
    """Put every main window on ``_TOOL["workspace"]``. True when a window was switched (its screen changes at the
    next event: the views are set at the tick after)."""
    name = _TOOL["workspace"]
    _TOOL["workspace"] = ""
    ws = bpy.data.workspaces.get(name) if name else None
    if ws is None:
        return False
    moved = False
    for win in main_windows():
        if win.workspace != ws:
            win.workspace = ws
            moved = True
    return moved


def _set_hud(area, show: bool) -> None:
    """The redo panel of one 3D view on or off. Its update needs the area in the context: set from a timer without it,
    switching it back ON crashed Blender 5.2.3 (segfault, also in a plain Blender – task 0332)."""
    win = next((w for w in bpy.context.window_manager.windows
                if w.screen is not None and any(a == area for a in w.screen.areas)), None)
    region = next((r for r in area.regions if r.type == "WINDOW"), None)
    if win is None or region is None:
        return
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        area.spaces.active.show_region_hud = show


def _tool_header_tick():
    """Set the tool header row and the redo panel once Blender's column is closed and the view was drawn (task 0221's
    lesson); first, a main window left on another Blender workspace goes back to the app's (task 0332)."""
    from . import editors
    _TOOL["tries"] += 1
    if (not editors.settled() or editors.busy()) and _TOOL["tries"] < 100:
        return 0.1
    try:
        if _TOOL["workspace"] and _go_back_workspace():
            _TOOL["tries"] = 0
            return 0.1                       # the new screen is set at the next event: its views at the next tick
    except Exception as exc:  # noqa: BLE001 - never break the switch over the layout
        print("Fresing Render: workspace not put back:", exc)
    show, hud = _TOOL["show"], _TOOL["hud"]
    try:
        for area in _views():
            sp = area.spaces.active
            if show is not None and sp.show_region_tool_header != show:
                sp.show_region_tool_header = show
            if hud is not None and sp.show_region_hud != hud:
                _set_hud(area, hud)
    except Exception as exc:  # noqa: BLE001 - never break the switch over the layout
        print("Fresing Render: tool header row not set:", exc)
    return None


def tool_header(show: bool | None, hud: bool | None = None, workspace: str = "") -> None:
    """Show or hide the tool header row (``show``) and the redo panel (``hud``) of every 3D view (not the Set-up
    window) – None leaves it – and put the main window back on ``workspace`` first; from a timer."""
    if bpy.app.background:
        return
    _TOOL["show"], _TOOL["hud"], _TOOL["tries"] = (None if show is None else bool(show)), hud, 0
    if workspace:
        _TOOL["workspace"] = workspace
    if not bpy.app.timers.is_registered(_tool_header_tick):
        bpy.app.timers.register(_tool_header_tick, first_interval=0.05)


def apply(quiet: bool, toolbar: bool = False) -> bool:
    """Quiet (every workspace but Full access) or Blender's own drawing. ``toolbar``: the user switched to Full
    access – the tool header row comes back with Blender's toolbar. True when the drawing changed."""
    if bpy.app.background:
        return False
    quiet = bool(quiet)
    changed = quiet != ON[0]
    for cls, fn in _classes():
        if cls is None:
            continue
        if quiet:
            swap(cls, fn)
        else:
            unswap(cls)
    upper = getattr(bpy.types, "TOPBAR_HT_upper_bar", None)
    if upper is not None:
        if quiet:
            _patch(upper, "draw_right", _draw_right)
        else:
            _unpatch(upper, "draw_right")
    back = ""
    if changed and not quiet:                # task 0332: Full access begins – remember the app's Blender workspace
        wins = main_windows()
        LOUD_WS[0] = wins[0].workspace.name if wins and wins[0].workspace is not None else ""
    elif changed and quiet and ON[0] is False and _SEEN_LOUD[0]:
        back = back_workspace()
        wins = main_windows()
        if back and all(w.workspace is not None and w.workspace.name == back for w in wins):
            back = ""
    if not quiet:
        _SEEN_LOUD[0] = True
    ON[0] = quiet
    _help_line(quiet)
    try:                                     # task 0367: Blender's side-panel tabs (late panels too, the Item tab)
        from . import ops_settings, panels
        if quiet:
            ops_settings.quiet_panels()
        panels.hide_c_panels(quiet)
    except Exception as exc:  # noqa: BLE001 - never break the switch over the side panel
        print("Fresing Render: Blender's side-panel tabs not switched:", exc)
    if not quiet and changed:
        try:
            render_info(True)                # Blender's text over a render back in Full access
        except Exception:  # noqa: BLE001
            pass
    if quiet:
        tool_header(False, hud=False, workspace=back)
    else:
        tool_header(True if toolbar else None, hud=True)
    if changed:
        from . import lock
        lock._topbar_redraw()
    return changed


def _help_line(quiet: bool) -> None:
    """The "Blender" sub-menu line at the very bottom of Help while quiet (appended again so it stays the last)."""
    cls = getattr(bpy.types, "TOPBAR_MT_help", None)
    if cls is None:
        return
    cls.remove(_help_blender_line)
    if quiet:
        cls.append(_help_blender_line)


def _first():
    """At the start (the extension switched on with no project loaded yet): the default workspace decides."""
    try:
        from . import lock, workspaces
        scene = bpy.context.scene
        if lock._SHOWN[0] is None and scene is not None and getattr(scene, "fresing", None) is not None:
            lock.blender_ui(workspaces.blender_ui(scene))
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: quiet window not set at the start:", exc)
    return None


def register() -> None:
    if not bpy.app.background and not bpy.app.timers.is_registered(_first):
        bpy.app.timers.register(_first, first_interval=0.0)


def unregister() -> None:
    if bpy.app.timers.is_registered(_first):
        bpy.app.timers.unregister(_first)
    if bpy.app.timers.is_registered(_tool_header_tick):
        bpy.app.timers.unregister(_tool_header_tick)
    for cls, _fn in _classes():
        if cls is not None:
            unswap(cls)
    _help_line(False)
    for cls_name, attr in list(_PATCHED):
        cls = getattr(bpy.types, cls_name, None)
        if cls is not None:
            _unpatch(cls, attr)
    _PATCHED.clear()
    _SWAPPED.clear()
    ON[0] = False
    _SEEN_LOUD[0] = False
    LOUD_WS[0] = ""


# ---------------------------------------------------------------------------
# Fresing > Show all of Blender / Back to the Fresing window
# ---------------------------------------------------------------------------

def _locked(context) -> bool:
    scene = getattr(context, "scene", None)
    if scene is None or getattr(scene, "fresing", None) is None:
        return False
    from . import workspaces
    return workspaces.locked(scene)


def all_shown(scene) -> bool:
    from . import workspaces
    return scene is not None and getattr(scene, "fresing", None) is not None and workspaces.blender_ui(scene)


def menu_text(scene=None) -> str:
    scene = scene if scene is not None else getattr(bpy.context, "scene", None)
    return BACK_TEXT if all_shown(scene) else SHOW_TEXT


class FRESING_OT_blender_all(bpy.types.Operator):
    """Shows all of Blender: its menus (Object, Add, Select), tools, workspace tabs, keys and the full splash – for
    users who know Blender. It switches the project to Workspace Full access; your model and settings are not
    changed. Click again (Back to the Fresing window) to return to the workspace you came from"""

    bl_idname = "fresing.blender_all"
    bl_label = "Show all of Blender"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if _locked(context):
            cls.poll_message_set(LOCKED_TEXT)
            return False
        scene = getattr(context, "scene", None)
        return scene is not None and getattr(scene, "fresing", None) is not None

    @classmethod
    def description(cls, context, props):
        doc = " ".join((cls.__doc__ or "").split())
        if _locked(context):
            return LOCKED_TEXT + ". " + doc
        if all_shown(getattr(context, "scene", None)):
            return ("Back to the Fresing window: hides Blender's own menus, tools, tabs and its full splash again and "
                    "returns the project to the workspace it was in before Show all of Blender. Your model and "
                    "settings are not changed")
        return doc

    def execute(self, context):
        from ..core import workspaces as W
        from . import lock, workspaces
        scene = context.scene
        s = scene.fresing
        if all_shown(scene):
            kept = scene.get(KEEP)
            name = ""
            if kept:
                try:
                    d = json.loads(kept)
                    s.ws_name, s.ws_data, s.ws_ticks = d["name"], d.get("data", ""), d.get("ticks", "")
                    name = d["name"]
                except (ValueError, KeyError, TypeError):
                    name = ""
                del scene[KEEP]
            if name:
                workspaces.apply(scene)
                workspaces._redraw()
            else:
                name = workspaces.default_name()
                ws = W.find(name, workspaces.library())
                if ws is None or ws.blender_ui:
                    name = W.DEFAULT
                try:
                    workspaces.switch(scene, name)
                except KeyError:
                    workspaces.switch(scene, W.DEFAULT)
                    name = W.DEFAULT
            if workspaces.blender_ui(scene):          # the remembered one was Full access itself
                workspaces.switch(scene, W.DEFAULT)
                name = W.DEFAULT
            self.report({"INFO"}, f"Back to the Fresing window (workspace {workspaces.name_of(scene)}). "
                                  "Fresing > Show all of Blender brings Blender's menus back")
            return {"FINISHED"}
        scene[KEEP] = json.dumps({"name": s.ws_name or workspaces.name_of(scene), "data": s.ws_data,
                                  "ticks": s.ws_ticks})
        try:
            workspaces.switch(scene, W.NAMES["full"])
        except KeyError as exc:
            del scene[KEEP]
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        lock.blender_ui(True, toolbar=True)
        self.report({"INFO"}, "All of Blender shown (Workspace Full access). Fresing > Back to the Fresing window "
                              "hides it again")
        return {"FINISHED"}


CLASSES = (FRESING_OT_blender_all, TOPBAR_MT_fresing_help_blender)
