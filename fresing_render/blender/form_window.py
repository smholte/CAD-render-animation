"""Function windows (task 0282): a function's form – Make a crane, Save as my own workspace, the PC check's choices … –
opens in a small window of its own instead of a Blender dialog. It stays open while you click in the main window,
can be dragged anywhere (also onto a second screen) and comes back where it was.

**One call turns a dialog into a window.** An operator's ``invoke`` that ended in
``context.window_manager.invoke_props_dialog(self, width=…, title=…, confirm_text=…)`` now ends in::

    return form_window.open(self, context, width=…, title=…, confirm="Make")

``confirm=None`` makes a window with only Close (About, Program details, Restore a backup …). Nothing else changes:
the operator keeps its properties, its ``draw`` and its ``execute``.

* **The values** live in a property group made from the operator's own properties (same names, defaults, choices,
  limits; ``make_group``) on the window manager – kept while the window is open, never saved with a project. ``open``
  copies what ``invoke`` worked out into it; the operator's ``draw`` draws them in the window (``_Self`` stands in for
  the operator, ``_Layout`` hands Blender the group where the draw names the operator). Opening the same function
  again brings its window to the front and keeps what was typed – unless it is about something else now (one of its
  hidden properties differs: Note for another stop, Rename another rule set), then it starts from ``invoke``'s values.
* **Make / OK** (``fresing.form_ok``) runs the operator's ``execute`` with those values in the main window – as the
  dialog's OK did, with its undo step – so what it needs from the scene (the selected part, the model) is read when it
  is pressed. Refused (its ``poll``: no model, a job running, the Client view) or failed: the window stays open and
  says why. Done: the window closes. **Cancel**, the X and **Esc** with the mouse over the window close it (``Return``
  there is Make, as in a dialog).
* **The window** is made like Fresing Settings (task 0271): ``ops_setup.open_window`` with the screen mark ``fr_form``
  = the operator's id, its page in the 3D view's toolbar region made as wide as the window, nothing else in it.
  Its size and place are kept per function in the settings file (``ops_make.remember``; the place on Windows).
* A form window left open when another project opens is closed (its values belong to the project before).

Client view: a function refused there today is still refused – its button never opens the window, and Make runs the
operator's own ``poll``. ``fresing.form_*`` itself is allowed (``lock.ALLOWED_PREFIXES``).

In a background run (tests, the queue) ``open`` does what the dialog did: ``invoke_props_dialog`` (a no-op there).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from bpy.props import StringProperty

from . import ops_setup, panels, ui
from .ops_setup import FORM_MARK

PREFIX = "fr_form_"                 # the window manager's pointer to a form's values: fr_form_<op name>
WIDTH, HEIGHT = 420, 360            # a form window's size when its call names none (px at UI scale 1)
TITLE_ROW = 1.2

# The inventory of task 0282 (its report has the table): the dialogs that are windows now …
WINDOWS = (
    "fresing.about", "fresing.backups_window", "fresing.demo_make", "fresing.gcode_report", "fresing.gcode_go_line",
    "fresing.learn_lessons", "fresing.learn_window", "fresing.lifting_box", "fresing.lifting_make",
    "fresing.pose_save", "fresing.vis_save", "fresing.shot_save", "fresing.group_add", "fresing.scheme_save",
    "fresing.rule_set_save_as", "fresing.rule_set_new_empty", "fresing.rule_set_rename", "fresing.tour_make",
    "fresing.tour_note", "fresing.usage_export", "fresing.workspace_save", "fresing.workspace_rename",
    "fresing.pc_check",
    "fresing.place_window", "fresing.remove",       # task 0292: Move / turn…, Remove…
    "fresing.lead_edit", "fresing.lead_keep_open",  # task 0309: Edit lead motions…, the sliders that stay open
    "fresing.weld_list",                            # task 0320: the weld list
)
# … and the ones that stay small popups: a yes / no question or a short message that needs one click (a click
# elsewhere is "no"), a search list, or a file that belongs to another task (``tests/test_form_window.py`` checks
# that every dialog of the app is in one of the two lists)
POPUPS = {
    "fresing.backup_offer": "a question when a project opens: Open the backup or not",
    "fresing.save_as": "one name, selected to type over, then Save (task 0291)",
    "fresing.lifting_understand": "one click: I understand",
    "fresing.loc_setup_update": "a question: Update the set-up (with what changes) or keep the old one",
    "fresing.loc_setup_changes": "a short list of what the last update changed",
    "fresing.rule_set_switch": "a question: Switch rule set (with what changes) or not",
    "fresing.usage_clear": "Are you sure? (its one tick belongs to the question)",
    "fresing.update_install": "a question before the app closes for an update: save the changes or not (task 0316)",
    "fresing.web3d_export": "a question before the file browser: bake the shadows anyway",
    "fresing.family_toggle": "a question: hide a family the project uses",
    "fresing.welcome": "the welcome – task 0276 makes it the first-start set-up (welcome.py is its file)",
    "fresing.whats_new": "What's new after an update – welcome.py belongs to task 0276",
    "fresing.gpu_notice": "task 0296: the calm graphics-card notice at the start – Use the graphics card / not now",
    "fresing.gpu_how": "task 0296: Show me how – steps to read, with two buttons",
}

_FORMS: dict = {}                   # idname -> {"cls", "title", "confirm", "icon", "extra": {...}, "error": str}
_GROUPS: dict = {}                  # idname -> the property group class made for it


# ---------------------------------------------------------------------------
# which window is which
# ---------------------------------------------------------------------------

def key_of(win) -> str:
    """The operator id a form window shows ('' for any other window)."""
    try:
        return str(win.screen.get(FORM_MARK) or "")
    except (AttributeError, ReferenceError):
        return ""


def windows(idname: str | None = None) -> list:
    """The open form windows (of one function, or all)."""
    wm = getattr(bpy.context, "window_manager", None)
    out = []
    for win in (wm.windows if wm is not None else ()):
        k = key_of(win)
        if k and (idname is None or k == idname):
            out.append(win)
    return out


def is_open(idname: str) -> bool:
    return bool(windows(idname))


def place_key(idname: str) -> str:
    """The key a form window's size and place are kept under in the settings file."""
    return "form:" + idname


def op_class(idname: str):
    """The registered operator class of ``fresing.x`` (None when there is none)."""
    form = _FORMS.get(idname)
    if form is not None:
        return form["cls"]
    cat, _, name = idname.partition(".")
    return getattr(bpy.types, f"{cat.upper()}_OT_{name}", None)


def title(idname: str) -> str:
    form = _FORMS.get(idname)
    if form is not None and form.get("title"):
        return form["title"]
    cls = op_class(idname)
    return str(getattr(cls, "bl_label", "") or idname).rstrip("…").rstrip(".")


# ---------------------------------------------------------------------------
# the values: a property group made from the operator's properties
# ---------------------------------------------------------------------------

def _attr(idname: str) -> str:
    return PREFIX + idname.replace(".", "_")


def annotations(cls) -> dict:
    """The operator's property definitions (its own and its bases'), in order."""
    out = {}
    for c in reversed(cls.__mro__):
        if c in (bpy.types.Operator, object) or not isinstance(c.__dict__.get("__annotations__"), dict):
            continue
        out.update(c.__dict__["__annotations__"])
    return out


def props_rna(cls):
    """The registered operator's properties (its ``OperatorProperties``), or None when it is not registered."""
    cat, _, name = str(getattr(cls, "bl_idname", "")).partition(".")
    try:
        return getattr(getattr(bpy.ops, cat), name).get_rna_type()
    except (AttributeError, KeyError, RuntimeError):
        return None


def _props(cls) -> list:
    rna = props_rna(cls)
    return [p for p in (rna.properties if rna is not None else ()) if p.identifier != "rna_type"]


def prop_names(cls) -> list:
    """Every property of the operator (as registered), in order."""
    if props_rna(cls) is None:
        return list(annotations(cls))
    return [p.identifier for p in _props(cls)]


def hidden_names(cls) -> list:
    return [p.identifier for p in _props(cls) if p.is_hidden]


def make_group(cls):
    """The property group of this operator's form (made and registered once; the window manager points at it)."""
    idname = cls.bl_idname
    group = _GROUPS.get(idname)
    if group is not None:
        return group
    name = "FRESING_PG_form_" + idname.replace(".", "_")
    group = type(name, (bpy.types.PropertyGroup,), {"__annotations__": dict(annotations(cls)),
                                                    "__module__": cls.__module__,
                                                    "__doc__": f"The values of the window '{cls.bl_label}'"})
    bpy.utils.register_class(group)
    setattr(bpy.types.WindowManager, _attr(idname), bpy.props.PointerProperty(type=group))
    _GROUPS[idname] = group
    return group


def data(idname: str, context=None):
    """The values of a form (its property group on the window manager), or None when it was never opened."""
    if idname not in _GROUPS:
        return None
    wm = getattr(context or bpy.context, "window_manager", None)
    return getattr(wm, _attr(idname), None) if wm is not None else None


def _plain(value):
    """A property value as plain Python (vectors and colours as tuples, enum flags as sets)."""
    if isinstance(value, (str, int, float, bool, set)) or value is None:
        return value
    try:
        return tuple(value)
    except TypeError:
        return value


def values(idname: str, context=None) -> dict:
    """{name: value} of a form, as keywords for its operator."""
    d = data(idname, context)
    cls = op_class(idname)
    if d is None or cls is None:
        return {}
    out = {}
    for name in prop_names(cls):
        try:
            out[name] = _plain(getattr(d, name))
        except AttributeError:
            continue
    return out


def _copy(src, dst, names) -> None:
    for name in names:
        try:
            v = getattr(src, name)
        except AttributeError:
            continue
        try:
            if _plain(getattr(dst, name)) != _plain(v):
                setattr(dst, name, v)
        except (AttributeError, TypeError, ValueError) as exc:     # an enum item that is not there now …
            print(f"Fresing Render: the window's value {name} not set:", exc)


# ---------------------------------------------------------------------------
# drawing the operator's own draw() in the window
# ---------------------------------------------------------------------------

class _Layout:
    """A layout that hands Blender the form's values where the operator's draw names the operator itself."""

    __slots__ = ("_lay", "_me", "_data")

    def __init__(self, lay, me, d):
        object.__setattr__(self, "_lay", lay)
        object.__setattr__(self, "_me", me)
        object.__setattr__(self, "_data", d)

    def _arg(self, a):
        return self._data if a is self._me else a

    def _wrap(self, r):
        if isinstance(r, bpy.types.UILayout) or getattr(type(r), "_layout_like", False):    # (tests: a stand-in)
            return _Layout(r, self._me, self._data)
        if isinstance(r, tuple):
            return tuple(self._wrap(x) for x in r)
        return r

    def __getattr__(self, name):
        a = getattr(self._lay, name)
        if not callable(a):
            return a

        def call(*args, **kw):
            args = tuple(self._arg(x) for x in args)
            kw = {k: self._arg(v) for k, v in kw.items()}
            return self._wrap(a(*args, **kw))
        return call

    def __setattr__(self, name, value):
        setattr(self._lay, name, value)


class _Self:
    """Stands in for the operator in its ``draw`` inside the window: its properties are the form's values, other
    attributes the class's (methods bound to this stand-in) or what ``invoke`` worked out (``extra``)."""

    def __init__(self, cls, d, layout, extra: dict):
        object.__setattr__(self, "_cls", cls)
        object.__setattr__(self, "_data", d)
        object.__setattr__(self, "_extra", extra)
        object.__setattr__(self, "_props", set(prop_names(cls)))
        object.__setattr__(self, "layout", _Layout(layout, self, d) if layout is not None else None)

    def __getattr__(self, name):
        if name in self._extra:
            return self._extra[name]
        if name in self._props:
            return getattr(self._data, name)
        if name == "properties":
            return self._data
        a = getattr(self._cls, name)
        if hasattr(a, "__get__") and not isinstance(a, (staticmethod, classmethod, property, type)) \
                and callable(a):
            return a.__get__(self, self._cls)
        return a

    def __setattr__(self, name, value):
        if name in self._props:
            setattr(self._data, name, value)
        else:
            self._extra[name] = value

    def report(self, _kind, message):          # (a draw that reports: shown in the console)
        print("Fresing Render:", message)


def default_draw(layout, d, cls) -> None:
    """What Blender's dialog draws for an operator without a ``draw``: each property that is not hidden."""
    col = layout.column()
    for p in _props(cls):
        if not p.is_hidden:
            col.prop(d, p.identifier)


def draw_form(layout, context, idname: str) -> bool:
    """The form's body as its operator draws it. False when there is nothing to draw (never opened)."""
    cls, d = op_class(idname), data(idname, context)
    if cls is None or d is None:
        return False
    form = _FORMS.get(idname, {})
    if "draw" in _own(cls):
        cls.draw(_Self(cls, d, layout, form.setdefault("extra", {})), context)
    else:
        default_draw(layout, d, cls)
    return True


def _own(cls) -> set:
    out = set()
    for c in cls.__mro__:
        if c in (bpy.types.Operator, object):
            break
        out.update(k for k in ("draw", "invoke", "execute", "cancel") if k in c.__dict__)
    return out


# ---------------------------------------------------------------------------
# opening
# ---------------------------------------------------------------------------

def open(op, context, width: int = 0, height: int = 0, title: str = "", confirm: str | None = "OK",  # noqa: A001
         icon: str = "", extra: dict | None = None, **dialog) -> set:
    """Show ``op``'s form in a window of its own (see the top of this file). Call it at the end of ``invoke`` in place
    of ``invoke_props_dialog`` / ``invoke_popup``. ``confirm`` is the Make / OK button's text (None: only Close),
    ``extra`` what the draw needs besides the properties (``invoke``'s own findings), ``width`` / ``height`` the
    window's first size (px at UI scale 1; a size the user gave it later wins)."""
    cls = type(op)
    idname = cls.bl_idname
    wm = context.window_manager
    if bpy.app.background or getattr(context, "window", None) is None or wm is None:
        # no windows to open: what the dialog did (tests in the background, scripts)
        kw = dict(dialog)
        if width:
            kw["width"] = width
        if title:
            kw["title"] = title
        if confirm:
            kw["confirm_text"] = confirm
        return wm.invoke_props_dialog(op, **kw)
    there = windows(idname)
    prepare(op, context, bool(there), title=title, confirm=confirm, icon=icon, extra=extra)
    if there:
        from .. import winplace
        ops_setup.restore_tabs()
        ops_setup.redraw_all()
        winplace.raise_window(there[0], place_key(idname))
        return {"FINISHED"}
    if ops_setup.busy():
        op.report({"INFO"}, "A window is opening: a moment, then press again")
        return {"CANCELLED"}
    win, area, _region = ops_setup.main_view(context)
    if area is None:
        op.report({"WARNING"}, f"'{title or cls.bl_label}' needs a 3D view in the main window")
        return {"CANCELLED"}
    if win.screen.show_fullscreen:
        op.report({"WARNING"}, "The 3D view fills the whole window: go back to the normal layout first "
                               "(Ctrl+Space), then press it again")
        return {"CANCELLED"}
    from . import ops_make
    size = ops_make.kept_size(place_key(idname)) or (width or WIDTH, height or HEIGHT)
    ops_setup.open_window(win, area, mark=FORM_MARK, value=idname, done=_opened, size=size)
    return {"FINISHED"}


def prepare(op, context, open_now: bool, title: str = "", confirm: str | None = "OK", icon: str = "",
            extra: dict | None = None) -> bool:
    """Put what ``invoke`` worked out into the form's values – unless its window is open and about the same thing
    (every hidden property equal): then what was typed stays. True when the values were (re)set."""
    cls = type(op)
    idname = cls.bl_idname
    make_group(cls)
    d = data(idname, context)
    form = _FORMS.get(idname)
    fresh = (form is None or not open_now
             or any(_plain(getattr(op, n)) != _plain(getattr(d, n, None)) for n in hidden_names(cls)))
    if fresh:
        _copy(op, d, prop_names(cls))
        _FORMS[idname] = {"cls": cls, "title": title or str(cls.bl_label).rstrip("…").rstrip("."),
                          "confirm": confirm, "icon": icon or "WINDOW", "extra": dict(extra or {}), "error": ""}
    else:
        form["title"] = title or form["title"]
        form["confirm"] = confirm
        form["cls"] = cls
    return fresh


def _opened(win) -> None:
    from . import ops_settings
    ops_settings._opened(win)


# ---------------------------------------------------------------------------
# Make / OK, Close
# ---------------------------------------------------------------------------

def _poll_text(exc) -> str:
    text = str(exc).strip()
    for cut in ("poll() failed, context is incorrect", "poll() Missing message"):
        if cut in text:
            return ""
    if ".poll()" in text:
        text = text.split(".poll()", 1)[1].strip()
    return text


def run(idname: str, context=None) -> tuple:
    """Run the form's operator with its values in the main window: (result set, message for the window)."""
    context = context or bpy.context
    cls = op_class(idname)
    if cls is None or data(idname, context) is None:
        return {"CANCELLED"}, "This window's function is not there any more: close it."
    kw = values(idname, context)
    cat, _, name = idname.partition(".")
    op = getattr(getattr(bpy.ops, cat), name)
    win, area, region = ops_setup.main_view(context)
    undo = "UNDO" in (getattr(cls, "bl_options", set()) or set()) and not bpy.app.background   # (no undo stack there)
    override = {"window": win, "screen": win.screen, "area": area, "region": region} if win is not None else {}
    try:
        with context.temp_override(**override):
            res = op("EXEC_DEFAULT", undo, **kw)
    except RuntimeError as exc:
        text = str(exc).strip()
        if ".poll()" in text:                                     # refused by its poll: its own message, if any
            return {"CANCELLED"}, _poll_text(exc) or _refused(idname)
        if text.startswith("Error:"):
            text = text[len("Error:"):].strip()
        return {"CANCELLED"}, text or "It did not work"
    except (TypeError, ValueError) as exc:
        return {"CANCELLED"}, f"It did not work: {exc}"
    if "CANCELLED" in res:
        return res, "Not done – the reason is at the bottom of the main window."
    return res, ""


def _refused(idname: str) -> str:
    """Why the operator cannot run now (its own poll message where it has one)."""
    try:
        from . import lock
        if not lock.allowed(idname) and lock.ON[0]:
            return lock.MESSAGE
    except Exception:  # noqa: BLE001
        pass
    return "Not possible now: what this needs is not there any more (the model, the part, the step) – or a job " \
           "is still running."


class FRESING_OT_form_ok(bpy.types.Operator):
    """Does what this window is for, with the values in it, in the main window; the window then closes"""

    bl_idname = "fresing.form_ok"
    bl_label = "OK"
    bl_options = set()          # (not REGISTER: no "adjust last operation" box)

    form: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        idname = getattr(properties, "form", "") or ""
        f = _FORMS.get(idname)
        doc = getattr(op_class(idname), "__doc__", "") or ""
        if f is None or not doc:
            return " ".join(cls.__doc__.split())
        return " ".join(doc.split()) + ". The window closes when it is done"

    def execute(self, context):
        return press_ok(self.form or key_of(context.window), context)


def press_ok(idname: str, context) -> set:
    """The window's Make / OK: run its function; done – the window closes; refused or failed – it stays, saying why.
    (Called by the button and by Return – never through ``bpy.ops`` from another operator: the function's undo step
    is pushed only by a call made at the top.)"""
    form = _FORMS.get(idname)
    if form is None:
        close(idname, context)
        return {"CANCELLED"}
    res, why = run(idname, context)
    form["error"] = why
    if "CANCELLED" in res:
        ops_setup.redraw_all()
        return {"CANCELLED"}
    close(idname, context, done=True)
    return {"FINISHED"}


class FRESING_OT_form_close(bpy.types.Operator):
    """Closes this window without doing anything. Its button opens it again"""

    bl_idname = "fresing.form_close"
    bl_label = "Close"
    bl_options = set()

    form: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        close(self.form or key_of(context.window), context)
        return {"FINISHED"}


class FRESING_OT_form_key(bpy.types.Operator):
    """Esc closes the window under the mouse, Return does what it is for (as in a dialog)"""

    bl_idname = "fresing.form_key"
    bl_label = "Window key"
    bl_options = {"INTERNAL"}

    ok: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def poll(cls, context):
        return bool(key_of(getattr(context, "window", None)))      # elsewhere the key is Blender's own

    def execute(self, context):
        idname = key_of(context.window)
        form = _FORMS.get(idname)
        if self.ok and form is not None and form.get("confirm"):
            return press_ok(idname, context)
        close(idname, context)
        return {"FINISHED"}


def cancelled(idname: str, context=None) -> None:
    """The window was closed without its OK (Cancel, the X, Esc, Close, another project): the operator's own
    ``cancel`` runs, as it did when its dialog was cancelled."""
    cls, d = op_class(idname), data(idname, context)
    if cls is None or d is None or "cancel" not in _own(cls):
        return
    form = _FORMS.get(idname, {})
    try:
        cls.cancel(_Self(cls, d, None, form.setdefault("extra", {})), context or bpy.context)
    except Exception as exc:  # noqa: BLE001
        print(f"Fresing Render: {idname} after its window closed:", exc)


def close(idname: str, context=None, done: bool = False) -> None:
    """Close a form's window (all when ``idname`` is ''), its size and place kept first. ``done``: after its OK
    (else the operator's ``cancel`` runs)."""
    from . import ops_make
    context = context or bpy.context
    if not done:
        for k in ([idname] if idname else [key_of(w) for w in windows()]):
            cancelled(k, context)
    wins = windows(idname or None)
    for win in wins:
        try:
            ops_make.remember(win)
        except Exception:  # noqa: BLE001
            pass
    for k in ([idname] if idname else list(_FORMS)):
        f = _FORMS.get(k)
        if f is not None:
            f["error"] = ""
    if getattr(context, "window", None) in wins:   # pressed in the window itself: Blender still needs it
        bpy.app.timers.register(lambda: _close_now(idname), first_interval=0.01)
    else:
        _close_now(idname)


def _close_now(idname: str):
    for win in windows(idname or None):
        try:
            with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
                bpy.ops.wm.window_close()
        except (RuntimeError, ReferenceError, IndexError) as exc:
            print("Fresing Render: a window did not close:", exc)
    panels.redraw()
    return None


# ---------------------------------------------------------------------------
# the window's page
# ---------------------------------------------------------------------------

class FRESING_PT_form_window(bpy.types.Panel):
    """A function's form in its own window (task 0282): title, the form, Make / OK and Cancel."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_label = "Window"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return bool(key_of(getattr(context, "window", None)))

    def draw(self, context):
        layout = self.layout
        idname = key_of(context.window)
        form = _FORMS.get(idname, {})
        row = layout.row(align=True)
        row.scale_y = TITLE_ROW
        row.label(text=title(idname), icon=form.get("icon", "WINDOW") or "WINDOW")
        right = row.row(align=True)
        right.alignment = "RIGHT"
        right.operator("fresing.form_close", text="", icon="X", emboss=False).form = idname
        ui.gap(layout)
        body = layout.column()
        try:
            shown = draw_form(body, context, idname)
        except Exception as exc:  # noqa: BLE001 - say it in the window, keep Close working
            print(f"Fresing Render: the window {idname} does not draw:", exc)
            ui.wrap(layout, context, f"This window could not draw its form ({exc}).", icon="ERROR", alert=True)
            shown = True
        if not shown:
            ui.wrap(layout, context, "This window belongs to a project that is closed now: close it and press its "
                                     "button again.", icon="INFO")
        if form.get("error"):
            ui.gap(layout)
            ui.wrap(layout, context, form["error"], icon="ERROR", alert=True)
        ui.gap(layout, line=True)
        row = layout.row(align=True)
        row.scale_y = 1.3
        confirm = form.get("confirm") if shown else None
        if confirm:
            row.operator("fresing.form_close", text="Cancel").form = idname
            row.operator("fresing.form_ok", text=confirm, depress=True).form = idname
        else:
            row.operator("fresing.form_close", text="Close").form = idname


# ---------------------------------------------------------------------------
# keys, a project opened, register
# ---------------------------------------------------------------------------

# Esc: in the window's page (the 3D view's toolbar region) Blender's "Frames" keymap takes Esc first (cancel playback),
# so the add-on's Esc sits in that keymap (an add-on's item comes before Blender's own of the same keymap); Return in
# "Window". Elsewhere their poll is False and the key goes on to Blender as before.
KEYS = (("Frames", "ESC", False), ("Window", "RET", True), ("Window", "NUMPAD_ENTER", True))
_KEYMAPS: list = []


def add_keys() -> None:
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm is not None else None
    if kc is None:
        return
    remove_keys()
    for name, key, is_ok in KEYS:
        km = kc.keymaps.new(name=name, space_type="EMPTY")
        kmi = km.keymap_items.new(FRESING_OT_form_key.bl_idname, key, "PRESS", head=True)
        kmi.properties.ok = is_ok
        _KEYMAPS.append((km, kmi))


def remove_keys() -> None:
    for km, kmi in _KEYMAPS:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    _KEYMAPS.clear()


@persistent
def _on_load(_dummy=None):
    """Another project is open: form windows it brought along (saved with it) close – their values belonged to the
    project before. One window per timer step, once the main window is settled (CLAUDE.md, 0221 / 0271)."""
    for f in _FORMS.values():
        f["error"] = ""
    if bpy.app.background:
        return
    tries = [0]

    def later():
        from . import editors
        tries[0] += 1
        if tries[0] > 200:
            return None
        if editors.busy() or ops_setup.busy():
            return 0.1
        wins = windows()
        if not wins:
            return None
        cancelled(key_of(wins[0]))
        try:
            with bpy.context.temp_override(window=wins[0], screen=wins[0].screen, area=wins[0].screen.areas[0]):
                bpy.ops.wm.window_close()
        except (RuntimeError, ReferenceError, IndexError) as exc:
            print("Fresing Render: a window of the project before did not close:", exc)
            return None
        return 0.2 if len(wins) > 1 else None

    bpy.app.timers.register(later, first_interval=0.5)


CLASSES = (FRESING_OT_form_ok, FRESING_OT_form_close, FRESING_OT_form_key, FRESING_PT_form_window)


def register() -> None:
    add_keys()
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister() -> None:
    remove_keys()
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    for idname, group in list(_GROUPS.items()):
        try:
            delattr(bpy.types.WindowManager, _attr(idname))
        except AttributeError:
            pass
        try:
            bpy.utils.unregister_class(group)
        except RuntimeError:
            pass
    _GROUPS.clear()
    _FORMS.clear()
