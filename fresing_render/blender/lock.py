"""The Client view's lock, and Blender's own tabs and menus (task 0062).

**The lock** (the owner's pick: level b – view only, Blender's own edits blocked too; no password). While the
project's workspace has ``lock`` (the built-in Client view, or an own workspace made from it):

* every ``fresing.*`` operator that changes the project is refused (``panels.install`` puts a ``poll`` on them that
  asks ``ON``; ``ALLOWED`` is the short list that still works: import, render, queue, saved scenes, camera views,
  light looks, turntable, help, updates, the workspace switcher itself);
* every object is made unclickable (``hide_select``) and locked in place (``lock_location`` / rotation / scale), the
  selection and the active object are cleared – so Blender's own G / R / S, Delete and Edit Mode act on nothing. What
  each object had before is remembered on the object (``fr_cv``) and put back, also the app's own "Locked in place";
* Delete, X, Tab and Ctrl+Shift+S are swallowed by an add-on keymap (its operator's ``poll`` is the lock, so the keys
  pass on to Blender's own the moment the lock is off – measured in the real app);
* the Outliner areas show the Info editor instead (remembered on the screen, put back), and the File menu loses
  Save As, Save Copy, Link, Append, Import and Export. Task 0213: an Outliner opened any other way while the lock is
  on – the editor-type menu of an area, Shift+F9, a new window, another of Blender's workspaces (Ctrl+Page Up), an
  area maximised with Ctrl+Space – is turned back into Info by a guard that looks every ``GUARD_EVERY`` s (and at
  once when an area's editor type is picked from its menu). The Outliner is the one editor that selects parts the
  lock made unclickable, so with it gone nothing can be selected and deleted;
* an undo to a step from before the lock marked the objects (an import) marks them again (``relock``).

Switching to a workspace without the lock (Full access, or any other) undoes all of it. What still gets through:
Ctrl+Z of earlier work, File > Open, the Properties editor's own buttons, the Python console (level b of 0062 is
the owner's pick: these stay).

**Blender's own tabs** (Layout, Modeling, Sculpting …): hidden in every workspace except Full access by drawing the
top bar's left part without them. No Blender workspace is deleted; Full access draws the tabs again.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

ON = [False]                 # the lock is on (asked by every fresing operator's poll: keep it a plain list)
MARK = "fr_cv"               # per object: what the lock changed (bit 0: was clickable; bits 1-9: was not locked)
NEW = 1 << 10                # … and bit 10: made while the lock was on (the app may set its own locks after us)
SCREEN_MARK = "fr_cv_areas"  # per screen: the areas (by index) whose Outliner was replaced
MESSAGE = "Client view: the project is locked against changes. Workspace > Full access unlocks it"

# fresing operators that still work in the Client view: looking, importing, rendering – nothing that edits the model
ALLOWED = {
    "fresing.import_step", "fresing.import_mesh", "fresing.report_clear",
    "fresing.render", "fresing.preview", "fresing.turntable", "fresing.light_look", "fresing.pick_hdri",
    "fresing.camera_activate", "fresing.shot_apply",
    "fresing.camera_add", "fresing.shot_save",          # task 0213: camera views and saved scenes are the Client
    "fresing.queue_schemes", "fresing.queue_schemes_tick",   # view's own (the new camera is locked like the rest)
    "fresing.queue_add", "fresing.queue_log", "fresing.queue_open", "fresing.queue_remove", "fresing.queue_start",
    "fresing.queue_start_cancel", "fresing.queue_start_later", "fresing.queue_start_now", "fresing.queue_stop",
    "fresing.open_file", "fresing.open_folder", "fresing.show_in_folder", "fresing.user_guide",
    "fresing.show_panel", "fresing.pc_check", "fresing.pc_check_cancel",
    "fresing.demo_make", "fresing.demo_open", "fresing.demo_cancel",
    "fresing.tour_make", "fresing.tour_open", "fresing.tour_go", "fresing.tour_pick", "fresing.tour_mark",
    "fresing.tour_note", "fresing.tour_copy", "fresing.tour_folder", "fresing.tour_run",
    "fresing.tour_take", "fresing.tour_cancel",                  # task 0199: the Fresing menu – they only open or
    "fresing.welcome", "fresing.welcome_answer", "fresing.whats_new", "fresing.whats_new_guide",   # show something
    "fresing.release_notes", "fresing.about", "fresing.about_open",   # task 0206: only opens a window / a file
    "fresing.self_test", "fresing.open_app_folder",              # task 0212: a check in its own window, a folder
    "fresing.client_locked",
    "fresing.rebake", "fresing.rebake_cancel",          # cables follow a sea change the Client view may make
}
ALLOWED_PREFIXES = ("fresing.update_", "fresing.workspace_", "fresing.family_", "fresing.panel_", "fresing.next_",
                    "fresing.make_", "fresing.usage_", "fresing.learn_")     # task 0181: the usage tracker changes nothing in the model


def scene_locked(context) -> bool:
    """With the lock on in this file: is the scene this button is pressed in the locked one? (A file may hold a
    second scene in another workspace; the update handler moves the lock when the shown scene changes.)"""
    scene = getattr(context, "scene", None)
    if scene is None or getattr(scene, "fresing", None) is None:
        return True
    try:
        from . import workspaces
        return workspaces.locked(scene)
    except Exception:  # noqa: BLE001
        return True


def allowed(idname: str) -> bool:
    """Does this fresing operator still work while the lock is on?"""
    return idname in ALLOWED or idname.startswith(ALLOWED_PREFIXES)


# ---------------------------------------------------------------------------
# the objects
# ---------------------------------------------------------------------------

_LOCKS = ("lock_location", "lock_rotation", "lock_scale")
_COUNT = [0]
_BUSY = [False]              # the lock is being put on or off: the update handler keeps out


def _lock_object(ob, new: bool = False) -> None:
    if MARK in ob:
        return
    bits = NEW if new else 0
    if not ob.hide_select:
        bits |= 1
        ob.hide_select = True
    k = 1
    for attr in _LOCKS:
        vec = getattr(ob, attr)
        for i in range(3):
            if not vec[i]:
                bits |= 1 << k
                vec[i] = True
            k += 1
    ob[MARK] = bits


def _unlock_object(ob) -> None:
    bits = ob.get(MARK)
    if bits is None:
        return
    bits = int(bits)
    if bits & 1:
        ob.hide_select = False
    k = 1
    for attr in _LOCKS:
        vec = getattr(ob, attr)
        for i in range(3):
            if bits & (1 << k):
                vec[i] = False
            k += 1
    del ob[MARK]
    if bits & NEW:
        _as_the_app_leaves_it(ob)


def _as_the_app_leaves_it(ob) -> None:
    """An object made while the lock was on was marked the moment it appeared – before the app had given it its
    own locks (an import locks every part in place and makes removed parts unclickable a little later). So after
    the unlock a model's part is put as the app itself would leave it."""
    from . import build
    kind = ob.get(build.PROP_KIND)
    if kind not in ("assembly", "part"):
        return
    locked = bool(ob.get(build.PROP_LOCKED, True)) if kind == "assembly" else True
    if kind == "part":                                   # a part follows the nearest assembly above it
        parent = ob.parent
        while parent is not None and parent.get(build.PROP_KIND) != "assembly":
            parent = parent.parent
        if parent is not None:
            locked = bool(parent.get(build.PROP_LOCKED, True))
    ob.lock_location = (locked,) * 3
    ob.lock_rotation = (locked,) * 3
    ob.lock_scale = (True,) * 3
    if ob.get(build.PROP_EXCLUDED):
        ob.hide_select = True


def _lock_all() -> None:
    for ob in bpy.data.objects:
        _lock_object(ob)
    _COUNT[0] = len(bpy.data.objects)
    for sc in bpy.data.scenes:
        for vl in sc.view_layers:
            for ob in list(vl.objects):
                try:
                    if ob is not None and ob.select_get(view_layer=vl):
                        ob.select_set(False, view_layer=vl)
                except (RuntimeError, AttributeError):
                    pass
            try:
                vl.objects.active = None
            except (RuntimeError, AttributeError):
                pass


def _unlock_all() -> None:
    for ob in bpy.data.objects:
        _unlock_object(ob)


def relock() -> int:
    """While the lock is on: mark every object that has lost its mark (an undo to a step pushed before the lock
    marked a new object, task 0213) and clear the selection. Returns how many were marked now."""
    if not ON[0]:
        return 0
    n = 0
    for ob in bpy.data.objects:
        if MARK not in ob:
            _lock_object(ob, new=True)
            n += 1
    if n:
        _lock_all()                          # marks nothing more; clears the selection and the active object
    _COUNT[0] = len(bpy.data.objects)
    return n


def marked() -> int:
    """How many objects carry the lock's mark (0 = the lock is off in this project)."""
    return sum(1 for ob in bpy.data.objects if MARK in ob)


@persistent
def _after_change(scene=None, _depsgraph=None):
    """While the lock is on: an object made meanwhile (an import, a turntable camera) is locked too. And the lock
    follows the scene that is shown: a file may hold a second scene in another workspace."""
    try:
        from . import workspaces
        shown = bpy.context.scene
        if shown is not None and getattr(shown, "fresing", None) is not None and not _BUSY[0]:
            want = workspaces.locked(shown)
            if want != ON[0]:
                apply(shown, want)
                blender_ui(workspaces.blender_ui(shown))
    except Exception:  # noqa: BLE001 - never break an update over the lock
        pass
    if ON[0] and len(bpy.data.objects) != _COUNT[0]:
        relock()                             # also clears the selection (a new camera came selected)


# ---------------------------------------------------------------------------
# the Outliner, the File menu, the keys
# ---------------------------------------------------------------------------

GUARD_EVERY = 0.1                       # s: how often the guard looks for an Outliner while the lock is on
LOCKED_TYPES = ("OUTLINER",)             # editors that are never shown while the lock is on


def _swap_outliners(on: bool) -> int:
    """On: every Outliner area of every window becomes Info (its place is remembered on the screen). Off: those
    areas are Outliners again. Returns how many areas were changed."""
    wm = bpy.context.window_manager
    if wm is None or bpy.app.background:
        return 0
    n = 0
    for win in wm.windows:
        screen = win.screen
        if screen is None:
            continue
        if on:
            idx = [i for i, a in enumerate(screen.areas) if a.type in LOCKED_TYPES]
            if idx:
                for i in idx:
                    screen.areas[i].ui_type = "INFO"
                screen[SCREEN_MARK] = sorted(set(list(screen.get(SCREEN_MARK, ())) + idx))
                n += len(idx)
        elif SCREEN_MARK in screen:
            for i in screen[SCREEN_MARK]:
                if i < len(screen.areas) and screen.areas[i].type == "INFO":
                    screen.areas[i].ui_type = "OUTLINER"
                    n += 1
            del screen[SCREEN_MARK]
    return n


def _guard():
    """The timer that keeps every Outliner out while the lock is on (task 0213). Stops when the lock goes off."""
    if not ON[0]:
        _GUARD[0] = False
        return None
    try:
        if _swap_outliners(True):
            _topbar_redraw()
    except Exception:  # noqa: BLE001 - never stop the guard over one window
        pass
    return GUARD_EVERY


_GUARD = [False]
_OWNER = object()                        # the msgbus owner of the editor-type watch


def _on_area_type():
    """An area's editor type was picked from its menu: look at once rather than at the guard's next turn."""
    if ON[0]:
        try:
            bpy.app.timers.register(_guard_once, first_interval=0.0)
        except Exception:  # noqa: BLE001
            pass


def _guard_once():
    if ON[0]:
        _swap_outliners(True)
    return None


def _start_guard() -> None:
    if bpy.app.background:
        return
    if not _GUARD[0]:
        _GUARD[0] = True
        try:
            bpy.app.timers.register(_guard, first_interval=GUARD_EVERY, persistent=True)
        except Exception:  # noqa: BLE001
            _GUARD[0] = False
    try:
        bpy.msgbus.clear_by_owner(_OWNER)
        for prop in ("ui_type", "type"):
            bpy.msgbus.subscribe_rna(key=(bpy.types.Area, prop), owner=_OWNER, args=(), notify=_on_area_type)
    except Exception:  # noqa: BLE001
        pass


def _stop_guard() -> None:
    try:
        bpy.msgbus.clear_by_owner(_OWNER)
    except Exception:  # noqa: BLE001
        pass
    if _GUARD[0] and bpy.app.timers.is_registered(_guard):
        bpy.app.timers.unregister(_guard)
    _GUARD[0] = False


def _file_menu_locked(self, context):
    """Blender's File menu without the entries that change or copy the project (Client view)."""
    layout = self.layout
    layout.operator_context = "INVOKE_AREA"
    layout.menu("TOPBAR_MT_file_new", text="New", icon="FILE_NEW")
    layout.operator("wm.open_mainfile", text="Open...", icon="FILE_FOLDER")
    layout.menu("TOPBAR_MT_file_open_recent")
    layout.operator("wm.revert_mainfile")
    layout.separator()
    layout.operator_context = "EXEC_AREA" if context.blend_data.is_saved else "INVOKE_AREA"
    layout.operator("wm.save_mainfile", text="Save", icon="FILE_TICK")
    layout.separator()
    layout.label(text="Client view: Save As, Import and Export are off", icon="LOCKED")
    layout.separator()
    layout.operator("wm.quit_blender", text="Quit", icon="QUIT")


_ORIG: dict = {}


def _patch(cls, attr: str, fn) -> None:
    key = (cls.__name__, attr)
    if key not in _ORIG:
        _ORIG[key] = cls.__dict__.get(attr, getattr(cls, attr))
        setattr(cls, attr, fn)


def _unpatch(cls, attr: str) -> None:
    key = (cls.__name__, attr)
    if key in _ORIG:
        setattr(cls, attr, _ORIG.pop(key))


def _topbar_redraw() -> None:
    """The top bar is no area of the screen: a window redraw is asked from a timer (never while drawing)."""
    if bpy.app.background:
        return

    def later():
        wm = bpy.context.window_manager
        for win in (wm.windows if wm else ()):
            for area in win.screen.areas:
                area.tag_redraw()
            try:
                win.screen.show_statusbar = win.screen.show_statusbar      # tags the whole window
            except (AttributeError, RuntimeError):
                pass
        return None

    try:
        bpy.app.timers.register(later, first_interval=0.05)
    except Exception:  # noqa: BLE001
        pass


def _file_menu(on: bool) -> None:
    try:
        cls = bpy.types.TOPBAR_MT_file
    except AttributeError:
        return
    if on:
        _patch(cls, "draw", _file_menu_locked)
    else:
        _unpatch(cls, "draw")


class FRESING_OT_client_locked(bpy.types.Operator):
    """The project is locked against changes in the Client view: this key does nothing here. Pick Workspace >
    Full access at the top of the Fresing tab to unlock it"""

    bl_idname = "fresing.client_locked"
    bl_label = "Locked in the Client view"

    @classmethod
    def poll(cls, context):
        return ON[0]

    def execute(self, context):
        self.report({"WARNING"}, MESSAGE)
        return {"FINISHED"}


_KEYS = (("Object Mode", "EMPTY", "DEL", {}), ("Object Mode", "EMPTY", "X", {}),
         ("Object Non-modal", "EMPTY", "TAB", {}), ("Outliner", "OUTLINER", "DEL", {}),
         ("Outliner", "OUTLINER", "X", {}), ("Window", "EMPTY", "S", {"ctrl": True, "shift": True}))
_KEYMAPS: list = []


def _add_keys() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm is not None else None
    if kc is None or _KEYMAPS:
        return
    for name, space, key, mods in _KEYS:
        km = kc.keymaps.new(name=name, space_type=space)
        kmi = km.keymap_items.new(FRESING_OT_client_locked.bl_idname, key, "PRESS", **mods)
        _KEYMAPS.append((km, kmi))


def _remove_keys() -> None:
    for km, kmi in _KEYMAPS:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _KEYMAPS.clear()


# ---------------------------------------------------------------------------
# on and off
# ---------------------------------------------------------------------------

def apply(scene, on: bool) -> None:
    """Put the lock on or off for the open project. Safe to call again: only what is not locked yet is locked, and
    only what the lock changed is put back."""
    on = bool(on)
    _BUSY[0] = True
    try:
        if on:
            ON[0] = True
            _lock_all()
        else:
            ON[0] = False
            if marked():
                _unlock_all()
        _swap_outliners(on)
        _file_menu(on)
        if on:
            _start_guard()
        else:
            _stop_guard()
    finally:
        _BUSY[0] = False
    _topbar_redraw()


# ---------------------------------------------------------------------------
# Blender's own workspace tabs, toolbar
# ---------------------------------------------------------------------------

def _draw_left_no_tabs(self, context):
    """Blender's top bar, left part, without the workspace tabs (the app has its own word "Workspace")."""
    layout = self.layout
    bpy.types.TOPBAR_MT_editor_menus.draw_collapsible(context, layout)
    screen = context.screen
    if screen is not None and screen.show_fullscreen:
        layout.separator(type="LINE")
        layout.operator("screen.back_to_previous", icon="SCREEN_BACK", text="Back to Previous")


_SHOWN = [None]              # Blender's tabs: True shown, False hidden, None not decided yet


def tabs_hidden() -> bool:
    return _SHOWN[0] is False


def blender_ui(on: bool, toolbar: bool = False) -> None:
    """``on`` (Full access): Blender's workspace tabs are drawn again. Off: the top bar is drawn without them.
    ``toolbar``: also show Blender's toolbar in the 3D views (when the user switches to Full access; a project that
    opens starts with it folded in every workspace)."""
    on = bool(on)
    try:
        cls = bpy.types.TOPBAR_HT_upper_bar
    except AttributeError:
        return
    if on:
        _unpatch(cls, "draw_left")
    else:
        _patch(cls, "draw_left", _draw_left_no_tabs)
    changed = _SHOWN[0] is not on
    _SHOWN[0] = on
    wm = bpy.context.window_manager
    if not bpy.app.background and wm is not None:
        for win in wm.windows:
            for area in win.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                space = area.spaces.active
                if on and toolbar:
                    space.show_region_toolbar = True
                elif not on and changed:
                    space.show_region_toolbar = False
    if changed:
        _topbar_redraw()


CLASSES = (FRESING_OT_client_locked,)


def register() -> None:
    if _after_change not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_after_change)
    if not bpy.app.background:
        _add_keys()


def unregister() -> None:
    while _after_change in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_after_change)
    _remove_keys()
    ON[0] = False
    _stop_guard()
    try:                                   # the extension is switched off in a locked project: the parts are free
        if marked():                       # again (the project's workspace still says Client view: it locks again
            _unlock_all()                  # when the extension is back on)
        _swap_outliners(False)
    except Exception:  # noqa: BLE001
        pass
    for cls_name, attr in list(_ORIG):
        cls = getattr(bpy.types, cls_name, None)
        if cls is not None:
            _unpatch(cls, attr)
    _SHOWN[0] = None
