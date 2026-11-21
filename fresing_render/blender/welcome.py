"""Start here (task 0199): the welcome for a new user and What's new after an update.

At the start of the app (never in the background, the tests, the PC check or the kit: ``core/start.py``'s
``NO_POPUP_ENV``, or simulated events) the state in ``<config>/fresing_start.json`` says what to show:

* **welcome** – the first starts in a settings folder: one line on the app, one on the test tour, Take the test tour /
  Later / Don't show this again. Later asks again at the next start, at most three starts.
* **whats_new** – the first start of a newer version: the new functions (``since=`` / ``changed=`` of
  ``core/functions.py``), the new and changed test models (``added=`` / ``changed=`` of the tour sets) and the tour of
  only those. Later keeps it in the Fresing menu until it is opened once.

Blender's splash shows at the start: the welcome and What's new then sit at the top of the splash (two windows on top
of each other were hard to read). Without a splash (a project opened by a double-click, the splash switched off) the
window shows once the project is open; on the very first start Blender's own quick set-up comes first and the welcome
follows when it is closed with Continue.
"""

from __future__ import annotations

import os
import tempfile
import textwrap

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from ..core import start as core

MEASURED_MINUTES = 3          # the whole tour on the 4-core test machine (task 0199): 141 s + ~1 min start of its Blender
_RUN = {"done": False, "shows": "", "splash": 0.0, "quick_setup": False, "waits": 0, "since": "", "now": ""}


def version() -> str:
    from .. import __version__
    return __version__


def state_path() -> str:
    return os.path.join(bpy.utils.user_resource("CONFIG"), core.FILE_NAME)


def load() -> dict:
    return core.load(state_path())


def save(state: dict) -> None:
    try:
        core.save(state_path(), state)
    except OSError as exc:
        print("Fresing Render: could not save the start state:", exc)


def suppressed() -> bool:
    """Nothing pops up: background runs, the tests and tools that set NO_POPUP_ENV, simulated events (real-app
    tests) unless the welcome's own test asks for it."""
    if bpy.app.background or os.environ.get(core.NO_POPUP_ENV):
        return True
    return bool(getattr(bpy.app, "use_event_simulate", False)) and not os.environ.get(core.TEST_ENV)


# ---------------------------------------------------------------------------
# what is new
# ---------------------------------------------------------------------------

def released_versions() -> list:
    """The versions in changelog.json next to the installed extension (newest first), [] when there is none."""
    import json
    from . import updates
    from ..core import updates as ucore
    try:
        with open(os.path.join(updates.PKG_DIR, ucore.CHANGELOG_NAME), encoding="utf-8") as fh:
            return [v.get("version", "") for v in json.load(fh).get("versions", []) if isinstance(v, dict)]
    except (OSError, ValueError, AttributeError):
        return []


def previous_version() -> str:
    """The version before this one (changelog.json), '' when not known."""
    older = [v for v in released_versions() if core.newer(version(), v)]
    return max(older, key=core.vtuple) if older else ""


def _existing_user_hint() -> str:
    """For a settings folder without a start file (the app before 0199): the version this user ran before, or ''.

    Only the update helper knows it for sure ("updated from X", ``updates._status``, read at register): such a user
    gets What's new. Anyone else gets the welcome (a reinstall over an old version too – it suggests the tour)."""
    from . import updates
    st = getattr(updates, "_status", {}) or {}
    return st["from"] if st.get("ok") and st.get("from") else ""


def since_for_marks() -> str:
    """The version the user ran before this update, for the tour's New / Changed marks ('' = no marks)."""
    wn = load().get("whats_new", {})
    return wn.get("from", "") if wn.get("to") == version() else ""


def functions_new(since: str, limit: int = core.WHATS_NEW_LINES) -> list:
    from ..core import functions
    return core.new_functions(functions.FUNCTIONS, since, version(), limit)


def functions_better(since: str, limit: int = core.BETTER_LINES) -> list:
    from ..core import functions
    return core.better_functions(functions.FUNCTIONS, since, version(), limit)


def sets_new(since: str) -> list:
    """[(TourSet, "new" | "changed")] of the tour, in the tour's order."""
    from . import tour
    out = []
    for ts in tour.SETS.values():
        kind = core.mark(ts.added, ts.changed, since, version())
        if kind:
            out.append((ts, kind))
    return out


def summary(since: str) -> str:
    sets = sets_new(since)
    n_new = sum(1 for _s, k in sets if k == "new")
    from ..core.words import plural
    return (f"{plural(len(functions_new(since, 10 ** 6)), 'new function')}, "
            f"{len(functions_better(since, 10 ** 6))} better, "
            f"{plural(n_new, 'new test model')}, {len(sets) - n_new} changed")


def tour_minutes() -> int:
    """About how long the whole tour takes to make: the last build on this PC, else the measured expectation."""
    from . import tour
    data = tour.read_progress(tour.default_folder())
    if data.get("finished") and int(data.get("total", 0)) >= len(tour.SETS) and data.get("seconds"):
        return max(1, round(float(data["seconds"]) / 60))
    return MEASURED_MINUTES


# ---------------------------------------------------------------------------
# at the start
# ---------------------------------------------------------------------------

def at_start(force: bool = False) -> str:
    """Decide what this start shows and remember the start (once per session). Returns "welcome", "whats_new" or
    ""."""
    if _RUN["done"] and not force:
        return _RUN["shows"]
    _RUN.update(done=True, shows="", splash=0.0, waits=0)
    if suppressed():
        return ""
    path = state_path()
    state = load()
    if not os.path.isfile(path) and not state["last_run"]:
        hint = _existing_user_hint()
        if hint:
            state["last_run"] = hint
            state["welcome"]["done"] = True
    shows = core.decide(state, version())
    state = core.started(state, version(), shows)
    save(state)
    _RUN.update(shows=shows, since=state["whats_new"].get("from", ""), now=version())
    return shows


def _splash_expected() -> bool:
    """Blender shows its splash at this start (switched on, no project opened from the command line)."""
    try:
        return bool(bpy.context.preferences.view.show_splash) and not bpy.data.filepath
    except AttributeError:
        return False


def _quick_setup_open() -> bool:
    """Blender's first-run quick set-up shows until it is closed with Continue (which saves the preferences)."""
    return not os.path.isfile(os.path.join(bpy.utils.user_resource("CONFIG"), "userpref.blend"))


def _window_override():
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm and wm.windows else None
    if win is None:
        return None
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    kw = {"window": win, "screen": win.screen}
    if area is not None:
        kw.update(area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None))
    return kw


def show_popup(kind: str) -> bool:
    kw = _window_override()
    if kw is None:
        return False
    op = "welcome" if kind == "welcome" else "whats_new"
    try:
        with bpy.context.temp_override(**kw):
            getattr(bpy.ops.fresing, op)("INVOKE_DEFAULT", at_start=True)
        return True
    except Exception as exc:  # noqa: BLE001 - never break the start of the app
        print("Fresing Render: could not show the start window:", exc)
        return False


def _tick():
    """Timer after the start: decide, then leave it to the splash or show the window."""
    try:
        if not _RUN["done"]:
            at_start()
            _RUN["quick_setup"] = _quick_setup_open()
        kind = _RUN["shows"]
        if not kind:
            return None
        if _RUN["splash"]:                 # the splash drew it: the user answers there
            return None
        if _splash_expected() and _RUN["waits"] < 8:      # give the splash a moment to draw
            _RUN["waits"] += 1
            return 0.5
        if _RUN["quick_setup"]:            # first run: after Blender's own Continue
            if _quick_setup_open():
                _RUN["waits"] += 1
                return 1.0 if _RUN["waits"] < 3600 else None
            _RUN["quick_setup"] = False
            return 0.5
        if bpy.context.window_manager is None or not bpy.context.window_manager.windows:
            return 0.5
        show_popup(kind)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: start window:", exc)
    return None


def _draw_splash(self, context):
    """At the top of Blender's splash: the welcome or What's new of this start."""
    if not _RUN["done"]:
        at_start()                         # the splash may draw before the start timer runs
        _RUN["quick_setup"] = _quick_setup_open()
    kind = _RUN["shows"]
    if not kind:
        return
    import time
    _RUN["splash"] = time.time()
    layout = self.layout
    box = layout.box()
    col = box.column()
    if kind == "welcome":
        col.label(text="Welcome to Fresing Render", icon="INFO")
        for line in WELCOME_TEXT(tour_minutes()):
            col.label(text=line)
        row = col.row(align=True)
        row.operator_context = "EXEC_DEFAULT"
        row.operator(FRESING_OT_welcome_answer.bl_idname, text="Open the Learning hub", icon="VIEW_CAMERA").choice = "TOUR"
        row.operator(FRESING_OT_welcome_answer.bl_idname, text="Later", icon="TIME").choice = "LATER"
        row.operator(FRESING_OT_welcome_answer.bl_idname, text="Don't show this again", icon="CANCEL").choice = "NEVER"
    else:
        col.label(text=core.title(_RUN["since"], version(), released_versions() or None), icon="INFO")
        col.label(text=summary(_RUN["since"]))
        row = col.row()
        row.operator_context = "INVOKE_DEFAULT"
        row.operator(FRESING_OT_whats_new.bl_idname, text="Show What's new…", icon="FORWARD").at_start = True
    layout.separator()


def _draw_quick_setup(self, context):
    if not _RUN["done"]:
        at_start()
        _RUN["quick_setup"] = True
    if _RUN["shows"]:
        self.layout.label(text="Fresing Render: press Continue – a short welcome follows", icon="INFO")


# ---------------------------------------------------------------------------
# texts
# ---------------------------------------------------------------------------

def WELCOME_TEXT(minutes: int) -> list:  # noqa: N802 - a text, called like one
    return ["Photo-realistic pictures and animations of your STEP assemblies.",
            "The Learning hub shows every function on small test models, one stop at a time.",
            f"Making it takes about {minutes} minutes on a PC like yours (in the background)."]


def _lines(layout, text: str, width: int = 88, icon: str = "NONE") -> None:
    for i, line in enumerate(textwrap.wrap(text, width) or [""]):
        layout.label(text=line, icon=icon if i == 0 else "BLANK1" if icon != "NONE" else "NONE")


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

def answer(choice: str) -> None:
    state = core.answer_welcome(load(), version(), {"TOUR": "tour", "LATER": "later", "NEVER": "never"}[choice])
    save(state)


def take_tour(context) -> None:
    kw = _window_override() or {}
    try:
        with context.temp_override(**kw):
            bpy.ops.fresing.tour_take("INVOKE_DEFAULT")
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: could not start the test tour:", exc)


class FRESING_OT_welcome(bpy.types.Operator):
    """Show the welcome window again: what the app is and how the Learning hub shows every function on small test
    models. Open the Learning hub makes it (in the background) or opens it"""

    bl_idname = "fresing.welcome"
    bl_label = "Welcome screen…"

    never: BoolProperty(name="Don't show this again", options={"SKIP_SAVE"},
                        description="Tick it and close with Cancel: the welcome does not show at the start again "
                                    "(it stays in the Fresing menu)")
    at_start: BoolProperty(options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=560, title="Welcome to Fresing Render",
                                                          confirm_text="Open the Learning hub")

    def draw(self, context):
        col = self.layout.column()
        for line in WELCOME_TEXT(tour_minutes()):
            _lines(col, line)
        col.separator()
        if self.at_start:
            _lines(col, "Cancel = later: asked again at the next start (at most three starts).", 84, icon="TIME")
        col.prop(self, "never")
        _lines(col, "Find it all again in the Fresing menu at the top (next to Help).", 84, icon="INFO")

    def execute(self, context):
        if self.at_start or self.never:
            answer("NEVER" if self.never else "TOUR")
        take_tour(context)
        return {"FINISHED"}

    def cancel(self, context):
        if self.never:
            answer("NEVER")
        elif self.at_start:
            answer("LATER")


class FRESING_OT_welcome_answer(bpy.types.Operator):
    """Answer the welcome: take the test tour now, ask again at the next start, or never show it again"""

    bl_idname = "fresing.welcome_answer"
    bl_label = "Answer the welcome"
    bl_options = {"INTERNAL"}

    choice: EnumProperty(items=[("TOUR", "Open the Learning hub", "Make the Learning hub (or open it) now"),
                                ("LATER", "Later", "Ask again at the next start (at most three starts)"),
                                ("NEVER", "Don't show this again", "The welcome does not show at the start again")])

    @classmethod
    def description(cls, context, props):
        return {"TOUR": "Make the Learning hub in the background (or open it when it is there): every function on "
                        "small test models, one stop at a time",
                "LATER": "Close the welcome; it shows again at the next start (at most three starts)",
                "NEVER": "Close the welcome for good. It stays in the Fresing menu at the top"}.get(
            getattr(props, "choice", ""), cls.__doc__)

    def execute(self, context):
        answer(self.choice)
        if self.choice == "TOUR":
            bpy.app.timers.register(lambda: (take_tour(bpy.context), None)[1], first_interval=0.2)
        return {"FINISHED"}


class FRESING_OT_whats_new(bpy.types.Operator):
    """What's new in this version: the new and improved functions, and the new and changed test models with a tour
    of only those (much quicker to make than the whole tour)"""

    bl_idname = "fresing.whats_new"
    bl_label = "What's new"

    at_start: BoolProperty(options={"HIDDEN", "SKIP_SAVE"})
    which: EnumProperty(name="Learning hub", default="NEW", options={"SKIP_SAVE"},
                        items=[("NEW", "Only the new and changed test models",
                                "Make a tour of only the new and changed test models: quicker than the whole tour"),
                               ("WHOLE", "The whole tour", "Make the whole Learning hub: every function, every model")],
                        description="Which Learning hub Make the tour makes")

    @classmethod
    def description(cls, context, props):
        return (f"{_menu_text()}: the new and improved functions, and a Learning hub of only the new and changed test "
                "models")

    def _since(self) -> str:
        st = load()
        wn = st.get("whats_new", {})
        if wn.get("to") == version() and wn.get("from"):
            return wn["from"]
        return previous_version()

    def invoke(self, context, event):
        if not self.at_start:                # opened from the menu: counts as opened
            save(core.opened_whats_new(load()))
        since = self._since()
        sets = sets_new(since)
        return context.window_manager.invoke_props_dialog(
            self, width=620, title=core.title(since, version(), released_versions() or None),
            confirm_text="Make the tour" if sets else "Close")

    def draw(self, context):
        since = self._since()
        layout = self.layout
        col = layout.column()
        funcs = functions_new(since)
        n_all = len(functions_new(since, 10 ** 6))
        better = functions_better(since)
        n_better = len(functions_better(since, 10 ** 6))
        if funcs or better:
            col.label(text=f"{n_all} new, {n_better} better")

        def rows(items, icon):
            for f, kind in items:
                text = textwrap.wrap(f.title, 62) or [""]
                row = col.split(factor=0.78, align=True)
                row.label(text=text[0], icon=icon)
                if f.guide:
                    op = row.operator(FRESING_OT_whats_new_guide.bl_idname, text="Show in guide", icon="HELP")
                    op.anchor = f.guide
                for more in text[1:]:
                    col.label(text=more, icon="BLANK1")

        if funcs:
            col.label(text="New functions")
            rows(funcs, "ADD")
            if n_all > len(funcs):
                col.label(text=f"… and {n_all - len(funcs)} more in the release notes")
        if better:
            col.separator()
            col.label(text=f"Better since {since}")
            rows(better, "MODIFIER")
            if n_better > len(better):
                col.label(text=f"… and {n_better - len(better)} more in the release notes")
        if not funcs and not better:
            col.label(text="Fixes and improvements: see the release notes.")
        col.operator(FRESING_OT_release_notes.bl_idname, icon="URL")
        if funcs:
            col.operator("fresing.learn_add_new", icon="BOOKMARKS").since = since
        col.separator()
        sets = sets_new(since)
        if sets:
            from ..core.words import plural
            n_new = sum(1 for _s, k in sets if k == "new")
            col.label(text=f"Learning hub: {plural(n_new, 'new test model')}, {len(sets) - n_new} changed")
            for ts, kind in sets:
                col.label(text=f"{ts.title}  ({'new' if kind == 'new' else 'changed'})",
                          icon="ADD" if kind == "new" else "MODIFIER")
            col.prop(self, "which", expand=True)
        else:
            col.label(text="No new or changed test models in the Learning hub this time.")
        if self.at_start:
            col.separator()
            _lines(col, "Cancel = later: What's new stays in the Fresing menu until you open it.", 76, icon="TIME")

    def execute(self, context):
        save(core.opened_whats_new(load()))
        since = self._since()
        sets = sets_new(since)
        if not sets:
            return {"FINISHED"}
        kw = _window_override() or {}
        only = "" if self.which == "WHOLE" else ",".join(ts.id for ts, _k in sets)
        try:
            with context.temp_override(**kw):
                bpy.ops.fresing.tour_make("EXEC_DEFAULT", only=only)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, f"Could not start the Learning hub: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


def guide_file() -> str:
    from . import updates
    return os.path.join(updates.PKG_DIR, "guide", "user_guide.html")


def guide_link_file(anchor: str) -> str:
    """A tiny page that jumps to a section of the user guide (a file path with #section loses the section on
    Windows when it is opened as a file)."""
    import json
    import pathlib
    target = pathlib.Path(guide_file()).as_uri() + "#" + anchor     # spaces and accents %-encoded (Windows paths)
    path = os.path.join(tempfile.gettempdir(), f"fresing_guide_{anchor}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"<!doctype html><meta charset='utf-8'><script>location.replace({json.dumps(target)});</script>"
                 f"<a href={json.dumps(target)}>Open the user guide</a>\n")
    return path


class FRESING_OT_whats_new_guide(bpy.types.Operator):
    """Open the user guide in your web browser at this function's section"""

    bl_idname = "fresing.whats_new_guide"
    bl_label = "Show in guide"
    bl_options = {"INTERNAL"}

    anchor: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        if not os.path.isfile(guide_file()):
            self.report({"ERROR"}, "The user guide is missing: run Install.bat again")
            return {"CANCELLED"}
        from . import files
        try:
            files.open_path(guide_link_file(self.anchor))
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open the user guide: {exc}")
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_release_notes(bpy.types.Operator):
    """Open this version's release page in your web browser: every change, in full"""

    bl_idname = "fresing.release_notes"
    bl_label = "All release notes"

    def execute(self, context):
        from . import updates
        from ..core import updates as ucore
        bpy.ops.wm.url_open(url=ucore.release_page(version(), updates.index_url()[0]))
        return {"FINISHED"}


def _menu_text() -> str:
    return f"What's new in {version()}"


CLASSES = (FRESING_OT_welcome, FRESING_OT_welcome_answer, FRESING_OT_whats_new, FRESING_OT_whats_new_guide,
           FRESING_OT_release_notes)


def register_handlers() -> None:
    for menu, fn in ((getattr(bpy.types, "WM_MT_splash", None), _draw_splash),
                     (getattr(bpy.types, "WM_MT_splash_quick_setup", None), _draw_quick_setup)):
        if menu is not None:
            menu.remove(fn)
            menu.prepend(fn)
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=1.5)


def unregister_handlers() -> None:
    for menu, fn in ((getattr(bpy.types, "WM_MT_splash", None), _draw_splash),
                     (getattr(bpy.types, "WM_MT_splash_quick_setup", None), _draw_quick_setup)):
        if menu is not None:
            menu.remove(fn)
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
