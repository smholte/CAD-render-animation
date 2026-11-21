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
* **File > New** (and Ctrl+N, which opens the same menu): only New project = what a fresh app start gives.

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
KEEP = "fr_ws_before_all"     # per scene: the workspace Show all of Blender came from (JSON of the three fields)
DRAWN = {"header": 0, "header_blender": 0, "splash": 0, "file_new": 0}   # draws counted (tests, the PC check)
LOCKED_TEXT = "Not in the Client view – Workspace > Full access unlocks it"
SHOW_TEXT = "Show all of Blender"
BACK_TEXT = "Back to the Fresing window"

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


_TOOL = {"show": None, "tries": 0}


def _tool_header_tick():
    """Set the tool header row once Blender's column is closed and the view was drawn (task 0221's lesson)."""
    from . import editors
    _TOOL["tries"] += 1
    if (not editors.settled() or editors.busy()) and _TOOL["tries"] < 100:
        return 0.1
    show = _TOOL["show"]
    if show is None:
        return None
    try:
        for area in _views():
            sp = area.spaces.active
            if sp.show_region_tool_header != show:
                sp.show_region_tool_header = show
    except Exception as exc:  # noqa: BLE001 - never break the switch over the layout
        print("Fresing Render: tool header row not set:", exc)
    return None


def tool_header(show: bool) -> None:
    """Show or hide the tool header row of every 3D view (not the Set-up window), from a timer."""
    if bpy.app.background:
        return
    _TOOL["show"], _TOOL["tries"] = bool(show), 0
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
    ON[0] = quiet
    if quiet:
        tool_header(False)
    elif toolbar:
        tool_header(True)
    if changed:
        from . import lock
        lock._topbar_redraw()
    return changed


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
    for cls_name, attr in list(_PATCHED):
        cls = getattr(bpy.types, cls_name, None)
        if cls is not None:
            _unpatch(cls, attr)
    _PATCHED.clear()
    _SWAPPED.clear()
    ON[0] = False


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


CLASSES = (FRESING_OT_blender_all,)
