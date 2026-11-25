"""Settings > Keys (task 0295): every key of the app, Fresing's own keys changeable, a printable key sheet.

The list (``rows``) is made when it is drawn: the view and select rows from Blender's input preferences (a 3-button
mouse emulated with Alt, the number row as numpad), Fresing's own keys from ``lock.app_keys()`` (``lock.APP_KEYS``
with the user's changes), Blender's swallowed keys from ``lock.BLENDER_KEYS`` – a key added in ``lock.py`` shows here
by itself – and the Blender keys that still work from ``KEPT``.

**Changing a key** (``fresing.key_change``): the row's button waits for the next key press in the window (Esc or a
click elsewhere: not changed); ``core/keys.check_new`` refuses a key another of Fresing's own keys has and warns about
one Blender uses (read from Blender's own key settings). The change is kept as JSON text in the preference
``key_changes`` – the settings file of task 0283 keeps it over a restart – and the keys are added again at once
(``lock.refresh_keys``). **Reset** puts one key (or all) back.
"""

from __future__ import annotations

import datetime
import os
import tempfile

import bpy
from bpy.props import BoolProperty, StringProperty

from ..core import keys as core

# Blender keys that still work outside Full access: (what, key, where)
KEPT = (
    ("Hide what is selected", "H", "3D view"),
    ("Show everything hidden again", "Alt+H", "3D view"),
    ("Hide everything else", "Shift+H", "3D view"),
    ("Undo", "Ctrl+Z", "everywhere"),
    ("Redo", "Ctrl+Shift+Z", "everywhere"),
    ("Play / stop the animation", "Space", "everywhere"),
    ("Make this area fill the window (and back)", "Ctrl+Space", "everywhere"),
    ("Search for a command", "F3", "everywhere"),
    ("Show / hide the side panel", "N", "3D view"),
    ("Full screen", "F11", "everywhere"),
    ("Save the project", "Ctrl+S", "everywhere"),
    ("Open a project", "Ctrl+O", "everywhere"),
    ("New project", "Ctrl+N", "everywhere"),
    ("Shading (pie menu)", "Z", "3D view"),
    ("Snap menu", "Shift+S", "3D view"),
    ("Exact move: after G / R / S", "X / Y / Z, a number", "3D view"),
)

_LAST = {"id": "", "text": "", "warn": False}     # the answer to the last change (shown at the top of the own keys)
CAPTURE = [""]                                    # the own key waiting for a press ("" = none)


def _prefs():
    from . import prefs
    try:
        return prefs.get()
    except Exception:  # noqa: BLE001
        return None


def changes() -> dict:
    from . import lock
    return lock.own_changes()


def _store(new: dict) -> None:
    p = _prefs()
    if p is None:
        raise RuntimeError("Fresing Render's settings are not there (is the extension switched on?)")
    p.key_changes = core.write_changes(new)
    try:
        from . import settings_store
        settings_store.save(p)                    # at once: a crash right after the change keeps it
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: changed key not written yet:", exc)
    from . import lock
    lock.refresh_keys()


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------

def _view_rows(context) -> list:
    inp = getattr(getattr(context, "preferences", None), "inputs", None)
    emulate = bool(getattr(inp, "use_emulate_3_button_mouse", False))
    numrow = bool(getattr(inp, "use_emulate_numpad", False))
    mid = "Alt+left mouse drag" if emulate else "Middle mouse drag"
    num = "1 / 3 / 7" if numrow else "Numpad 1 / 3 / 7"
    R = core.Row
    return [
        R("view", "Turn the view (orbit)", mid, "3D view"),
        R("view", "Move the view sideways (pan)", "Shift+" + mid[0].lower() + mid[1:], "3D view"),
        R("view", "Zoom in and out", "Mouse wheel", "3D view"),
        R("view", "Zoom smoothly", "Ctrl+" + mid[0].lower() + mid[1:], "3D view"),
        R("view", "Touchpad: turn the view", "Two fingers", "3D view"),
        R("view", "Touchpad: pan", "Shift+two fingers", "3D view"),
        R("view", "Touchpad: zoom", "Pinch", "3D view"),
        R("view", "Front / right / top view", num, "3D view"),
        R("view", "Back / left / bottom view", "Ctrl+" + num, "3D view"),
        R("view", "Look through the camera", "Numpad 0" if not numrow else "0 (number row)", "3D view"),
        R("view", "Perspective or flat (orthographic)", "Numpad 5" if not numrow else "5 (number row)", "3D view"),
        R("view", "Zoom to what is selected", "Numpad .", "3D view"),
        R("view", "Zoom to everything", "Home", "3D view"),
        R("view", "View directions (pie menu)", "`", "3D view"),
    ]


def _select_rows() -> list:
    R = core.Row
    return [
        R("select", "Select a part (also in Structure)", "Left mouse", "3D view"),
        R("select", "Add to / take from the selection", "Shift+left mouse", "3D view"),
        R("select", "Select in a box", "Drag on empty space", "3D view"),
        R("select", "Select all / nothing", "A / Alt+A", "3D view"),
        R("select", "Select the subassembly of a part", "Double-click", "Structure"),
    ]


def _where(keymap: str, op: str) -> str:
    return {"Screen": "everywhere", "Window": "everywhere"}.get(keymap, "3D view")


def _op_label(op: str) -> str:
    area, _, name = op.partition(".")
    try:
        return getattr(getattr(bpy.ops, area), name).get_rna_type().name or op
    except (AttributeError, KeyError, RuntimeError):
        return op


def own_rows(ch: dict | None = None) -> list:
    from . import lock
    ch = changes() if ch is None else ch
    out = []
    for (n, _sp, k, m, op, props), (_n0, _s0, k0, m0, _o0, _p0) in zip(lock.app_keys(ch), lock.APP_KEYS):
        kid = core.own_id(op, k0, m0)
        if kid:
            what = core.OWN[kid][3]
        elif op == "fresing.move_key":
            what = {"TRANSLATE": "Move", "ROTATE": "Turn", "RESIZE": "Scale"}.get(props.get("mode"), "Move") + \
                " what is selected (checks first)"
        elif op == "fresing.view_menu":
            what = "Fresing's right-click menu"
        else:
            what = _op_label(op)
        out.append(core.Row("own", what, core.label(k, m), _where(n, op), id=kid,
                            default=core.label(k0, m0) if kid else ""))
    return out


def off_rows() -> list:
    from . import lock
    out, seen = [], set()
    ch = changes()
    mine = [core.own_key(kid, ch) for kid in ch]
    for n, _sp, k, m, what in lock.BLENDER_KEYS:
        key = core.label(k, m)
        where = {"Outliner": "Outliner", "User Interface": "on a setting", "Window": "everywhere",
                 "Screen": "everywhere"}.get(n, "3D view")
        if (what, key, where) in seen:
            continue
        seen.add((what, key, where))
        given = n not in ("Outliner", "User Interface") and any(core.same((k, m), x) for x in mine)
        out.append(core.Row("off", what[:1].upper() + what[1:], key, where,
                            note="now one of your Fresing keys" if given else "works in Full access"))
    return out


def rows(context=None) -> list:
    """Every row of the list, in group order."""
    context = context or bpy.context
    R = core.Row
    return (_view_rows(context) + _select_rows() + own_rows()
            + [R("kept", w, k, wh) for w, k, wh in KEPT] + off_rows())


def blender_taken() -> list:
    """[(key, modifiers, what)] of Blender's own keys that work in the 3D view (its default key settings) and the kept
    keys the app knows of."""
    out = []
    try:
        kc = bpy.context.window_manager.keyconfigs.default
    except AttributeError:
        kc = None
    names = ("Object Mode", "Object Non-modal", "3D View", "3D View Generic", "Screen", "Window", "Frames")
    if kc is not None:
        for name in names:
            km = kc.keymaps.get(name)
            if km is None:
                continue
            for kmi in km.keymap_items:
                if not kmi.active or kmi.map_type not in ("KEYBOARD", "MOUSE") or kmi.value not in ("PRESS", "CLICK"):
                    continue
                mods = {"any": True} if kmi.any else {m: True for m in core.MODS if getattr(kmi, m) == 1}
                out.append((kmi.type, mods, kmi.name or kmi.idname))
    return out


def own_now(ch: dict | None = None) -> dict:
    ch = changes() if ch is None else ch
    return {kid: core.own_key(kid, ch) for kid in core.OWN}


def change(kid: str, key: str, mods: dict) -> core.Check:
    """Give Fresing's own key ``kid`` the key ``key`` + ``mods`` (when allowed); the answer in plain words."""
    ch = changes()
    res = core.check_new(kid, key, mods, own_now(ch), blender_taken())
    if res.ok:
        ch[kid] = (key, {m: True for m in core.MODS if mods.get(m)})
        _store(ch)
    return res


def reset(kid: str = "") -> int:
    """Put one of Fresing's own keys back to its default ('' = all). Returns how many were changed."""
    ch = changes()
    n = len(ch) if not kid else int(kid in ch)
    if kid:
        ch.pop(kid, None)
    else:
        ch = {}
    _store(ch)
    return n


def sheet_path() -> str:
    return os.path.join(tempfile.gettempdir(), "Fresing Render keys.html")


def write_sheet(path: str = "") -> str:
    from . import welcome
    path = path or sheet_path()
    text = core.sheet_html(rows(), welcome.version(), datetime.date.today().isoformat())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

def _redraw() -> None:
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def _say(kid: str, res: core.Check, key_text: str) -> None:
    if not res.ok:
        _LAST.update(id=kid, text=res.refusal, warn=True)
    else:
        text = f"{core.OWN[kid][3].split(' (')[0]}: now {key_text}"
        if res.warnings:
            text += " – " + res.warnings[0]
        _LAST.update(id=kid, text=text, warn=bool(res.warnings))


class FRESING_OT_key_change(bpy.types.Operator):
    """Gives this Fresing key another key: click, then press the new key (with Ctrl, Shift or Alt if you like). Esc
    or a click elsewhere: not changed. A key another Fresing key has is refused; one Blender uses gives a warning"""

    bl_idname = "fresing.key_change"
    bl_label = "Change key"
    bl_options = {"INTERNAL"}

    id: StringProperty(name="Key", options={"SKIP_SAVE", "HIDDEN"})
    key: StringProperty(name="New key", options={"SKIP_SAVE", "HIDDEN"},
                        description="The new key (Blender's name, e.g. K or F9); empty: wait for a key press")
    ctrl: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})
    shift: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})
    alt: BoolProperty(options={"SKIP_SAVE", "HIDDEN"})

    def _set(self, key, mods) -> set:
        res = change(self.id, key, mods)
        text = core.label(key, mods)
        _say(self.id, res, text)
        _redraw()
        if not res.ok:
            self.report({"WARNING"}, res.refusal)
            return {"CANCELLED"}
        self.report({"WARNING"} if res.warnings else {"INFO"}, _LAST["text"])
        return {"FINISHED"}

    def execute(self, context):
        if self.id not in core.OWN:
            self.report({"ERROR"}, f"'{self.id}' is not one of Fresing's own keys")
            return {"CANCELLED"}
        if not self.key:
            return self.invoke(context, None)
        return self._set(self.key, {"ctrl": self.ctrl, "shift": self.shift, "alt": self.alt})

    def invoke(self, context, event):
        if self.id not in core.OWN:
            return {"CANCELLED"}
        if self.key:
            return self.execute(context)
        CAPTURE[0] = self.id
        _LAST.update(id=self.id, text="Press the new key (Esc: not changed)", warn=False)
        context.window_manager.modal_handler_add(self)
        _redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        t = event.type
        if event.value != "PRESS" or t in core.MODIFIER_KEYS or t.startswith(("MOUSE", "INBETWEEN", "TIMER",
                                                                               "TRACKPAD", "NDOF_MOTION")):
            return {"RUNNING_MODAL"}
        CAPTURE[0] = ""
        if t in ("ESC", "LEFTMOUSE", "MIDDLEMOUSE"):
            _LAST.update(id=self.id, text="Not changed", warn=False)
            _redraw()
            return {"CANCELLED"}
        self._set(t, {"ctrl": event.ctrl, "shift": event.shift, "alt": event.alt})
        return {"FINISHED"}

    def cancel(self, context):
        CAPTURE[0] = ""


class FRESING_OT_key_reset(bpy.types.Operator):
    """Puts this Fresing key back to the key it had when the app came (without a key named: all of them)"""

    bl_idname = "fresing.key_reset"
    bl_label = "Reset key"
    bl_options = {"INTERNAL"}

    id: StringProperty(name="Key", options={"SKIP_SAVE", "HIDDEN"})

    def execute(self, context):
        if self.id and self.id not in core.OWN:
            self.report({"ERROR"}, f"'{self.id}' is not one of Fresing's own keys")
            return {"CANCELLED"}
        reset(self.id)
        if self.id:
            _LAST.update(id=self.id, text=f"{core.OWN[self.id][3].split(' (')[0]}: back to "
                                          f"{core.label(*core.own_key(self.id, {}))}", warn=False)
        else:
            _LAST.update(id="", text="All Fresing keys are back to the keys they came with", warn=False)
        _redraw()
        self.report({"INFO"}, _LAST["text"])
        return {"FINISHED"}


class FRESING_OT_key_sheet(bpy.types.Operator):
    """Makes a key sheet – every key of the app on one A4 page – and opens it in your web browser: print it there or
    save it as a PDF (your changed keys are on it)"""

    bl_idname = "fresing.key_sheet"
    bl_label = "Print key sheet"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        try:
            path = write_sheet()
        except OSError as exc:
            self.report({"ERROR"}, f"The key sheet could not be written: {exc}")
            return {"CANCELLED"}
        if not bpy.app.background:
            from . import files
            files.open_path(path)
        self.report({"INFO"}, f"Key sheet: {path}")
        return {"FINISHED"}


CLIENT_TEXT = ("Not in the Client view: Blender's key settings are in Blender's Preferences, which the Client view keeps "
               "closed – Workspace > Full access unlocks it")


def client_view(context) -> bool:
    """Is the project in the Client view (its lock on)? Task 0367: Blender's key settings are greyed there."""
    scene = getattr(context, "scene", None)
    if scene is None or getattr(scene, "fresing", None) is None:
        return False
    try:
        from . import workspaces
        return bool(workspaces.locked(scene))
    except Exception:  # noqa: BLE001
        return False


class FRESING_OT_keys_blender(bpy.types.Operator):
    """Opens Blender's own key settings (Preferences > Keymap). That is Blender's list: there you change Blender's
    keys, not Fresing's – those are in Fresing Settings > Keys"""

    bl_idname = "fresing.keys_blender"
    bl_label = "Blender's own key settings"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        """Task 0367 (0332's open point): not in the Client view – Blender's Preferences could switch the app off."""
        if client_view(context):
            cls.poll_message_set(CLIENT_TEXT)
            return False
        return True

    @classmethod
    def description(cls, context, props):
        doc = " ".join((cls.__doc__ or "").split())
        return CLIENT_TEXT + ". " + doc if client_view(context) else doc

    def execute(self, context):
        context.preferences.active_section = "KEYMAP"
        if not bpy.app.background:
            bpy.ops.screen.userpref_show("INVOKE_DEFAULT", section="KEYMAP")
        return {"FINISHED"}


class FRESING_OT_keys(bpy.types.Operator):
    """Opens Fresing Settings on the tab Keys: every key of the app, change Fresing's own keys, print a key sheet"""

    bl_idname = "fresing.keys"
    bl_label = "Keys"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        from . import ops_settings
        return ops_settings.open_settings(self, context, "keys")


CLASSES = (FRESING_OT_key_change, FRESING_OT_key_reset, FRESING_OT_key_sheet, FRESING_OT_keys_blender,
           FRESING_OT_keys)


# ---------------------------------------------------------------------------
# the tab
# ---------------------------------------------------------------------------

def _row(col, r, context, wide: int) -> None:
    split = col.split(factor=0.3 if wide > 80 else 0.4, align=True)
    left = split.row(align=True)
    if r.group == "own" and r.id:
        waiting = CAPTURE[0] == r.id
        left.operator(FRESING_OT_key_change.bl_idname, text="Press a key…" if waiting else r.key,
                      depress=waiting).id = r.id
        if r.changed:
            left.operator(FRESING_OT_key_reset.bl_idname, text="", icon="LOOP_BACK").id = r.id
    else:
        left.label(text=r.key)
    note = r.note if r.note and r.note != "works in Full access" else ""    # the off group's title says so
    text = r.what + (f" ({note})" if note else "") + ("" if r.where in ("3D view", "everywhere") else f" – {r.where}")
    split.label(text=text)


def draw(layout, context) -> None:
    from . import ui, ui_settings
    wm = context.window_manager
    wide = ui_settings.chars(context)
    top = layout.row(align=True)
    if hasattr(wm, "fresing_keys_search"):
        top.prop(wm, "fresing_keys_search", text="", icon="VIEWZOOM")
    top.operator(FRESING_OT_key_sheet.bl_idname, text="Print key sheet", icon="FILE_TEXT")
    ui.hint(layout, context, "Outside Full access – in Full access every key is Blender's own (Fresing > Show all "
                             "of Blender). Click one of Fresing's own keys, then press its new key.")
    shown = core.search(rows(context), getattr(wm, "fresing_keys_search", ""))
    for gkey, gtitle in core.GROUPS:
        mine = [r for r in shown if r.group == gkey]
        if gkey == "own":
            box = layout.box()
            head = box.row()
            head.label(text=gtitle, icon="EVENT_F")
            sub = head.row()
            sub.alignment = "RIGHT"
            sub.enabled = bool(changes())
            sub.operator(FRESING_OT_key_reset.bl_idname, text="Reset all", icon="LOOP_BACK").id = ""
            line = box.row()                     # always drawn: the panel stays still (owner, 23 Nov)
            line.alert = bool(_LAST["warn"])
            line.label(text=_LAST["text"] or " ", icon="ERROR" if _LAST["warn"] else "BLANK1")
        elif not mine:
            continue
        else:
            box = layout.box()
            box.label(text=gtitle, icon={"view": "VIEW3D", "select": "RESTRICT_SELECT_OFF", "kept": "BLENDER",
                                         "off": "CANCEL"}.get(gkey, "DOT"))
        col = box.column(align=True)
        col.active = gkey != "off"
        for r in mine:
            _row(col, r, context, wide)
        if gkey == "own" and not mine:
            col.label(text="No Fresing key matches the search")
    layout.separator()
    layout.operator(FRESING_OT_keys_blender.bl_idname, icon="BLENDER")
    ui.hint(layout, context, "Blender's own key settings change Blender's keys (used in Full access), not Fresing's.")


def _draw_keys_help(self, context):
    self.layout.operator(FRESING_OT_keys.bl_idname, text="Keys…", icon="KEYINGSET")


def register() -> None:
    bpy.types.TOPBAR_MT_help.remove(_draw_keys_help)
    bpy.types.TOPBAR_MT_help.append(_draw_keys_help)
    bpy.types.WindowManager.fresing_keys_search = StringProperty(
        name="Search keys", default="", options={"TEXTEDIT_UPDATE"},
        description="Shows only the keys whose words or key hold what you type (e.g. render, F12, hide)")


def unregister() -> None:
    bpy.types.TOPBAR_MT_help.remove(_draw_keys_help)
    try:
        del bpy.types.WindowManager.fresing_keys_search
    except AttributeError:
        pass
