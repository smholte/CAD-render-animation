"""Test tour buttons (task 0059): make and open the tour, Go to a stop, OK / Problem, note, Copy results, the
automatic run. The stops and the build are in ``tour.py``; the panel is ``ui_tour.py``."""

from __future__ import annotations

import os
import subprocess
import sys

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import tour

_BUILD: dict = {}           # the running build: {"proc", "folder", "log", "version"}
_PENDING: dict = {}         # Go asked for a stop in another project: {"stop": id}


def _version() -> str:
    from .. import __version__
    return __version__


def _here(context) -> tuple[str, str]:
    """(folder, version) of the open tour project, else the default folder and this version."""
    folder, version = tour.tour_of_file(context.scene)
    return (folder, version) if folder else (tour.default_folder(), _version())


def building() -> dict:
    """The build that runs now (progress read from its file), or {}."""
    proc = _BUILD.get("proc")
    if proc is None:
        return {}
    data = tour.read_progress(_BUILD["folder"])
    data["running"] = proc.poll() is None
    return data


def progress_text() -> str:
    data = building()
    if not data or not data.get("running"):
        return ""
    total = data.get("total") or len(tour.SETS)
    done = min(int(data.get("done", 0)) + 1, total)
    step = data.get("step", "")
    return f"Making the test tour: project {done} of {total}" + (f" ({step})" if step else "") + " …"


# ---------------------------------------------------------------------------
# make and open
# ---------------------------------------------------------------------------

class FRESING_OT_tour_make(bpy.types.Operator):
    """Make the test tour: small projects from the app's own test models with every function set up, and a
    Test tour panel to go through them stop by stop. Takes about 2 minutes in the background; then open it with
    Help > Open test tour project"""

    bl_idname = "fresing.tour_make"
    bl_label = "Make test tour project…"

    folder: StringProperty(name="Folder", subtype="DIR_PATH",
                           description="Where the test tour goes. Default: Documents\\Fresing Render\\Test tour")
    in_place: BoolProperty(default=False, options={"HIDDEN", "SKIP_SAVE"})   # tests: build in this Blender

    _timer = None

    def invoke(self, context, event):
        if building().get("running"):
            self.report({"WARNING"}, "The test tour is being made: wait for it")
            return {"CANCELLED"}
        self.folder = self.folder or tour.default_folder()
        return context.window_manager.invoke_props_dialog(self, width=460, confirm_text="Make it")

    def draw(self, context):
        col = self.layout.column()
        col.label(text=f"A test tour for Fresing Render {_version()}: {len(tour.STOPS)} stops in "
                       f"{len(tour.SETS)} small projects.")
        col.label(text="It is made in the background (about 2 minutes); you can keep working.")
        if os.path.isfile(tour.hub_path(self.folder, _version())):
            col.label(text="A tour of this version is there already: it is made new;", icon="INFO")
            col.label(text="your OK / Problem ticks and notes are kept.")
        col.separator()
        col.prop(self, "folder")

    def execute(self, context):
        folder = bpy.path.abspath(self.folder) if self.folder else tour.default_folder()
        os.makedirs(folder, exist_ok=True)
        if self.in_place or bpy.app.background:
            out = tour.build_all(folder, _version())
            if out["errors"]:
                self.report({"ERROR"}, "Test tour: " + "; ".join(f"{k}: {v}" for k, v in out["errors"].items())[:300])
                return {"CANCELLED"}
            self.report({"INFO"}, f"Test tour made: {out['hub']}")
            return {"FINISHED"}
        exe = bpy.app.binary_path
        if not exe:
            self.report({"ERROR"}, "Blender's program was not found")
            return {"CANCELLED"}
        from ..pccheck import ops as pc_ops
        log = os.path.join(folder, "Make test tour log.txt")
        try:
            os.remove(tour.progress_path(folder))
        except OSError:
            pass
        kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" \
            else {"start_new_session": True}
        try:
            fh = open(log, "w", encoding="utf-8", errors="replace")
            proc = subprocess.Popen([exe, "--background", "--python", pc_ops.LAUNCHER, "--", "tourbuild", folder],
                                    cwd=os.path.dirname(exe), stdout=fh, stderr=subprocess.STDOUT, **kwargs)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not start making the test tour: {exc}")
            return {"CANCELLED"}
        _BUILD.update(proc=proc, folder=folder, log=log, version=_version(), fh=fh)
        self._timer = context.window_manager.event_timer_add(0.5, window=context.window)
        context.window_manager.modal_handler_add(self)
        self.report({"INFO"}, "Making the test tour in the background (about 2 minutes)")
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        text = progress_text()
        if text:
            context.workspace.status_text_set(text)
            for area in context.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
            return {"PASS_THROUGH"}
        context.window_manager.event_timer_remove(self._timer)
        context.workspace.status_text_set(None)
        proc, folder, version = _BUILD.get("proc"), _BUILD.get("folder", ""), _BUILD.get("version", _version())
        try:
            _BUILD["fh"].close()
        except (KeyError, OSError):
            pass
        _BUILD.clear()
        data = tour.read_progress(folder)
        hub = tour.hub_path(folder, version)
        errors = data.get("errors") or {}
        if data.get("finished") and os.path.isfile(hub):
            _ready_popup(context, hub)
            if errors:
                self.report({"WARNING"}, "Test tour made, but these projects failed: "
                                         + "; ".join(f"{k}: {v}" for k, v in errors.items())[:250])
            else:
                self.report({"INFO"}, f"Test tour ready ({data.get('seconds', 0):.0f} s): Help > Open test tour project")
            return {"FINISHED"}
        del proc
        why = "; ".join(f"{k}: {v}" for k, v in errors.items()) or "it stopped half-way"
        self.report({"ERROR"}, f"The test tour could not be made ({why[:200]}). Its log: "
                               f"{os.path.join(folder, 'Make test tour log.txt')}")
        return {"FINISHED"}


def _ready_popup(context, hub: str) -> None:
    def draw(menu, _context):
        menu.layout.label(text="The test tour is ready.")
        op = menu.layout.operator(FRESING_OT_tour_open.bl_idname, text="Open test tour project", icon="FILE_BLEND")
        op.filepath = hub

    try:
        context.window_manager.popup_menu(draw, title="Test tour", icon="CHECKMARK")
    except Exception:  # noqa: BLE001 - the report line says it too
        pass


class FRESING_OT_tour_open(bpy.types.Operator):
    """Open the test tour of this version (made with Make test tour project…). Save your own project first:
    changes that are not saved are lost"""

    bl_idname = "fresing.tour_open"
    bl_label = "Open test tour project"

    filepath: StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, event):
        if bpy.data.is_dirty and not tour.is_tour(context.scene):
            return context.window_manager.invoke_confirm(
                self, event, title="Open the test tour?", confirm_text="Open",
                message="This project has changes that are not saved: they are lost. Open the test tour anyway?")
        return self.execute(context)

    def execute(self, context):
        path = self.filepath or tour.hub_path(tour.default_folder(), _version())
        if not os.path.isfile(path):
            self.report({"ERROR"}, "No test tour for this version: Help > Make test tour project… first")
            return {"CANCELLED"}
        bpy.ops.wm.open_mainfile(filepath=path)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# the stops
# ---------------------------------------------------------------------------

def _stop_items(_self, _context):
    return [(s.id, f"{s.number}. {s.title}", s.see) for s in tour.STOPS]


class FRESING_OT_tour_pick(bpy.types.Operator):
    """Show this stop: what you should see and its buttons appear under the list. Then press Go"""

    bl_idname = "fresing.tour_pick"
    bl_label = "Pick stop"
    bl_options = {"INTERNAL"}

    stop: StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, props):
        st = tour.find(props.stop) if props else None
        return f"{st.number}. {st.title}: {st.see}" if st else cls.__doc__

    def execute(self, context):
        folder, version = tour.tour_of_file(context.scene)
        if not folder or tour.find(self.stop) is None:
            return {"CANCELLED"}
        data = tour.load_results(folder, version)
        data["current"] = self.stop
        tour.save_results(folder, version, data)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_tour_go(bpy.types.Operator):
    """Set this stop up: opens its project if needed, its saved scene and camera, builds and plays its animation,
    selects its part and looks through the camera. Then look and press OK or Problem"""

    bl_idname = "fresing.tour_go"
    bl_label = "Go"
    bl_options = {"REGISTER", "UNDO"}

    stop: StringProperty(options={"HIDDEN"})

    def execute(self, context):
        st = tour.find(self.stop)
        folder, version = tour.tour_of_file(context.scene)
        if st is None or not folder:
            self.report({"ERROR"}, "Open the test tour first (Help > Open test tour project)")
            return {"CANCELLED"}
        data = tour.load_results(folder, version)
        data["current"] = st.id
        tour.save_results(folder, version, data)
        path = tour.set_path(folder, version, st.set)
        if os.path.normcase(os.path.abspath(bpy.data.filepath)) != os.path.normcase(path):
            if not os.path.isfile(path):
                self.report({"ERROR"}, f"'{os.path.basename(path)}' is missing: make the test tour again")
                return {"CANCELLED"}
            _PENDING["stop"] = st.id
            if context.screen and context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel(restore_frame=False)
            bpy.ops.wm.open_mainfile(filepath=path)
            return {"FINISHED"}          # the stop is set up after loading (_after_load)
        warnings = tour.apply(st, context.scene)
        tour.show_in_ui(context, st)
        if warnings:
            self.report({"WARNING"}, "; ".join(warnings[:3]))
        else:
            self.report({"INFO"}, f"{st.number}. {st.title}: {st.where}" if st.where else f"{st.number}. {st.title}")
        return {"FINISHED"}


@persistent
def _after_load(_dummy=None):
    if bpy.app.background:
        return
    try:
        here = tour.is_tour(bpy.context.scene)
    except Exception:  # noqa: BLE001
        here = False
    if _PENDING.get("stop") or here:
        bpy.app.timers.register(_go_pending, first_interval=0.2)


def _show_tab() -> None:
    """A tour project opens with the side panel shown on the Fresing tab (the projects are saved in the background,
    without the app's screen)."""
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            area.spaces.active.show_region_ui = True
            for region in area.regions:
                if region.type == "UI":
                    try:
                        region.active_panel_category = "Fresing"
                    except (AttributeError, TypeError):
                        pass
            area.tag_redraw()


def _go_pending():
    try:
        if tour.is_tour(bpy.context.scene):
            _show_tab()
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render test tour:", exc)
    stop_id = _PENDING.pop("stop", "")
    if not stop_id:
        return None
    wm = bpy.context.window_manager
    win = wm.windows[0] if wm.windows else None
    if win is None:
        return None
    area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
    kw = {"window": win, "screen": win.screen}
    if area is not None:
        kw.update(area=area, region=next((r for r in area.regions if r.type == "WINDOW"), None))
    try:
        with bpy.context.temp_override(**kw):
            bpy.ops.fresing.tour_go("EXEC_DEFAULT", True, stop=stop_id)       # with its own undo step
    except Exception as exc:  # noqa: BLE001 - never break loading over a tour stop
        print("Fresing Render test tour: Go failed:", exc)
    return None


class FRESING_OT_tour_mark(bpy.types.Operator):
    """Mark this stop: OK when it looks right, Problem when something is wrong (then add a note). Click again to
    take the mark off. Saved next to the tour, for every project of the tour"""

    bl_idname = "fresing.tour_mark"
    bl_label = "Mark stop"
    bl_options = {"INTERNAL"}

    stop: StringProperty(options={"HIDDEN"})
    state: EnumProperty(items=[(tour.OK_STATE, "OK", "It looks right"),
                               (tour.PROBLEM, "Problem", "Something is wrong: add a note")])

    @classmethod
    def description(cls, context, props):
        if props and props.state == tour.PROBLEM:
            return "Something is wrong at this stop: marks it Problem. Then write what you saw with Note…"
        return "It looks right: marks this stop OK. Click again to take the mark off"

    def execute(self, context):
        folder, version = tour.tour_of_file(context.scene)
        if not folder:
            return {"CANCELLED"}
        tour.mark(folder, version, self.stop, state=self.state)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_tour_note(bpy.types.Operator):
    """Write a short note for this stop: what you saw, what was wrong. It goes into Copy results"""

    bl_idname = "fresing.tour_note"
    bl_label = "Note for this stop"
    bl_options = {"INTERNAL"}

    stop: StringProperty(options={"HIDDEN"})
    note: StringProperty(name="Note", description="What you saw at this stop, in a few words")

    def invoke(self, context, event):
        folder, version = tour.tour_of_file(context.scene)
        self.note = tour.load_results(folder, version)["stops"].get(self.stop, {}).get("note", "") if folder else ""
        return context.window_manager.invoke_props_dialog(self, width=500, confirm_text="Save note")

    def draw(self, context):
        st = tour.find(self.stop)
        if st:
            self.layout.label(text=f"{st.number}. {st.title}")
        self.layout.prop(self, "note", text="")

    def execute(self, context):
        folder, version = tour.tour_of_file(context.scene)
        if not folder:
            return {"CANCELLED"}
        tour.mark(folder, version, self.stop, note=self.note)
        _redraw(context)
        return {"FINISHED"}


class FRESING_OT_tour_copy(bpy.types.Operator):
    """Copy the results of the tour (version, PC, OK / Problem and your note for every stop) to paste into the lead
    chat. Also saved as a text file next to the tour"""

    bl_idname = "fresing.tour_copy"
    bl_label = "Copy results"

    def execute(self, context):
        folder, version = tour.tour_of_file(context.scene)
        if not folder:
            return {"CANCELLED"}
        text = tour.results_text(version, tour.load_results(folder, version), tour.pc_text())
        context.window_manager.clipboard = text
        path = tour.results_txt_path(folder, version)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        except OSError as exc:
            self.report({"WARNING"}, f"Copied; the text file could not be written: {exc}")
            return {"FINISHED"}
        self.report({"INFO"}, f"Results copied: paste them into the lead chat (also in {os.path.basename(path)})")
        return {"FINISHED"}


class FRESING_OT_tour_run(bpy.types.Operator):
    """Go through every stop by itself in the background: makes a fresh tour, renders a small picture of each stop
    and checks what can be checked with numbers. A report with a picture per stop opens in your web browser (about
    10 to 15 minutes). Your OK / Problem ticks stay as they are"""

    bl_idname = "fresing.tour_run"
    bl_label = "Run the whole tour by itself"

    def execute(self, context):
        return bpy.ops.fresing.pc_check("EXEC_DEFAULT", mode="tour")


class FRESING_OT_tour_folder(bpy.types.Operator):
    """Show the test tour's folder: the projects, the results file and the text of Copy results"""

    bl_idname = "fresing.tour_folder"
    bl_label = "Show the tour folder"

    def execute(self, context):
        from . import files
        folder, _version_ = _here(context)
        if not os.path.isdir(folder):
            self.report({"ERROR"}, "The test tour has not been made yet")
            return {"CANCELLED"}
        files.open_path(folder)
        return {"FINISHED"}


def _redraw(context) -> None:
    screen = getattr(context, "screen", None)
    for area in (screen.areas if screen else []):
        if area.type == "VIEW_3D":
            area.tag_redraw()


def draw_help(layout) -> None:
    """Help menu entries under the PC check (pccheck/ops.py draws them)."""
    text = progress_text()
    if text:
        layout.label(text=text, icon="TIME")
    else:
        layout.operator(FRESING_OT_tour_make.bl_idname, icon="VIEW_CAMERA")
    if os.path.isfile(tour.hub_path(tour.default_folder(), _version())):
        layout.operator(FRESING_OT_tour_open.bl_idname, icon="FILE_BLEND")


CLASSES = (FRESING_OT_tour_make, FRESING_OT_tour_open, FRESING_OT_tour_pick, FRESING_OT_tour_go,
           FRESING_OT_tour_mark, FRESING_OT_tour_note, FRESING_OT_tour_copy, FRESING_OT_tour_run,
           FRESING_OT_tour_folder)


def register_handlers() -> None:
    if _after_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_after_load)


def unregister_handlers() -> None:
    while _after_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_after_load)
