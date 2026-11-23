"""8 Lifting plan > Equipment > Make a crane… (task 0204): the dialog, the maker as a background program (progress,
Cancel – the app keeps redrawing), the crane into the library, then Place now; and Enter your chart… for an item of
your own (a CSV table, L2's chart entry: the SAMPLE mark comes off once the charts are your own).

Why a dialog and not the Set-up window: making a crane is one form (type, start from a class, numbers, name) with no
steps to go through, and the Set-up window is the place of 0203's step-by-step rigging of your own STEP crane.
"""

from __future__ import annotations

import os

import bpy
from bpy.props import StringProperty

from ..core import lifting_library as LL
from ..lifting_model import job as J
from ..lifting_model import params as P
from . import lifting
from . import ui_lifting_make as U

STATE: dict = {"job": None, "message": "", "error": False, "made": ""}


def running():
    j = STATE.get("job")
    return j if j is not None and not j.done else None


def _redraw() -> None:
    wm = bpy.context.window_manager
    for win in wm.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def _ok(context) -> bool:
    return lifting.understood()


def make_library() -> str:
    """The "Lifting equipment" folder Make writes into: the first one you can write to, Mine first (task 0272: made
    when it is not there yet); '' only when every such folder is switched off or read-only."""
    lib = lifting.user_folder(make=True)
    if lib:
        lifting.library(force=True)
    return lib


def cancel_all() -> None:
    """At unregister / quit: a running maker stopped, its temporary folder deleted."""
    job = running()
    if job is not None:
        job.cancel()


def unique_name(base: str) -> str:
    lib = make_library()
    if not lib or J.name_problem(lib, base) == "":
        return base
    for k in range(2, 1000):
        cand = f"{base} {k}"
        if J.name_problem(lib, cand) == "":
            return cand
    return base


def start(context, spec: dict, replace: bool = False) -> J.MakeJob:
    """The job started (MakeError naming every reason it cannot)."""
    from ..importer import runner
    if running() is not None:
        raise J.MakeError("A crane is being made already: wait for it or cancel it.")
    job = J.MakeJob(spec, make_library(), runner.python_executable(), replace=replace)
    job.start()
    STATE.update(job=job, message="", error=False, made="")
    return job


def make_now(spec: dict, library: str, replace: bool = False) -> J.MakeJob:
    """Make a crane and wait for it (the test tour, the PC check, scripts). MakeError naming why it failed."""
    from ..importer import runner
    job = J.MakeJob(spec, library, runner.python_executable(), replace=replace)
    job.start()
    job.wait()
    if job.error:
        raise J.MakeError(job.error)
    return job


TOUR_CRANE = "AT-100 with 5 sections"


def tour_spec() -> dict:
    """The test tour's and the PC check's crane: the AT-100's numbers with 5 boom sections instead of 7 and the boom
    50 m fully out instead of 60 m (with 5 sections 60 m is refused: they would not keep enough of themselves in
    each other)."""
    v = P.of_class("AT-100")
    v.update(sections=5, Lmax=50000.0)
    return {"kind": "AT", "name": TOUR_CRANE, "start": "AT-100", "values": v}


def finish(context, job: J.MakeJob) -> None:
    """After the job: the message, the library read again, the new crane picked (Place… shows it)."""
    if job.error:
        STATE.update(message=("Making the crane was cancelled: nothing was written." if job.error == "cancelled"
                              else job.error), error=job.error != "cancelled", made="")
    else:
        lifting.library(force=True)
        try:
            lifting.plan(context.scene).pick = job.item_path
        except Exception:  # noqa: BLE001
            pass
        STATE.update(message=f"{job.name} is in your library ({job.seconds:.1f} s). Its chart is a SAMPLE: enter the "
                             "chart of your real crane before you plan a lift.", error=False, made=job.item_path)
    _redraw()


def _place_now_popup(context, path: str, name: str) -> None:
    def draw(menu, _context):
        lay = menu.layout
        lay.operator_context = "INVOKE_DEFAULT"
        lay.operator("fresing.lifting_place", text=f"Place {name} now…", icon="IMPORT").path = path
        lay.operator("fresing.lifting_chart_csv", text="Enter the chart of your real crane…",
                     icon="SPREADSHEET").item = path
    try:
        context.window_manager.popup_menu(draw, title=f"{name} is in your library", icon="CHECKMARK")
    except Exception:  # noqa: BLE001 – no window (background)
        pass


class FRESING_OT_lifting_make(bpy.types.Operator):
    """Makes a ready-rigged crane from numbers: pick a type, start from a built-in class, change the numbers you care
    about, press Make. It is drawn in the background and lands in your library with a SAMPLE chart"""
    bl_idname = "fresing.lifting_make"
    bl_label = "Make a crane"
    bl_options = {"REGISTER"}

    _timer = None

    @classmethod
    def poll(cls, context):
        return _ok(context) and running() is None

    def invoke(self, context, event):
        m = U.settings(context)
        if not m.name.strip() or m.name == "My crane":
            m.name = unique_name(f"My {m.start}")
        from . import form_window
        return form_window.open(self, context, width=490, height=700, title="Make a crane", confirm="Make",
                                icon="MOD_BUILD")

    def draw(self, context):
        U.draw_dialog(self.layout, context, U.settings(context))

    def execute(self, context):
        m = U.settings(context)
        if not make_library():
            from . import locations
            self.report({"ERROR"}, locations.no_folder_text("lifting"))
            return {"CANCELLED"}
        try:
            job = start(context, U.spec_of(m), m.replace)
        except J.MakeError as exc:
            self.report({"ERROR"}, str(exc))
            STATE.update(message=str(exc), error=True)
            return {"CANCELLED"}
        if bpy.app.background or context.window is None:
            job.wait()
            finish(context, job)
            if job.error:
                self.report({"ERROR"}, job.error)
                return {"CANCELLED"}
            self.report({"INFO"}, f"Made {job.name}")
            return {"FINISHED"}
        self._timer = context.window_manager.event_timer_add(0.25, window=context.window)
        context.window_manager.modal_handler_add(self)
        _redraw()
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        if event.type != "TIMER":
            return {"PASS_THROUGH"}
        job = STATE.get("job")
        if job is None or job.poll():
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
            if job is not None:
                finish(context, job)
                if not job.error:
                    _place_now_popup(context, job.item_path, job.name)
            return {"FINISHED"} if job is not None and not job.error else {"CANCELLED"}
        _redraw()
        return {"PASS_THROUGH"}


class FRESING_OT_lifting_make_cancel(bpy.types.Operator):
    """Stops making the crane: nothing is written to your library"""
    bl_idname = "fresing.lifting_make_cancel"
    bl_label = "Cancel making the crane"

    @classmethod
    def poll(cls, context):
        return running() is not None

    def execute(self, context):
        job = running()
        if job is not None:
            job.cancel()
            finish(context, job)
        return {"FINISHED"}


class FRESING_OT_lifting_make_masses(bpy.types.Operator):
    """Fills the masses (and the hook block) from the start class's rule, scaled by the sizes you changed. Change
    them afterwards if you know better"""
    bl_idname = "fresing.lifting_make_masses"
    bl_label = "Masses from the class rule"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        m = U.settings(context)
        v = U.values_of(m)
        try:
            got = P.suggest_masses(m.kind, v, m.start)
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as exc:
            self.report({"ERROR"}, f"No masses: {exc}")
            return {"CANCELLED"}
        for k, x in got.items():
            f = P.field(m.kind, k)
            setattr(m, U.prop_name(m.kind, k), min(f.hi, max(f.lo, f.to_ui(x))))
        return {"FINISHED"}


class FRESING_OT_lifting_chart_csv(bpy.types.Operator):
    """Reads the chart of your real crane from a CSV table (radius, capacity; a line per configuration: boom,
    counterweight, outriggers) into this crane of your library. The SAMPLE mark comes off once its charts are your own"""
    bl_idname = "fresing.lifting_chart_csv"
    bl_label = "Enter your chart…"
    bl_options = {"REGISTER"}

    item: StringProperty(options={"SKIP_SAVE"}, description="The equipment item ('' = the picked one)")
    filepath: StringProperty(subtype="FILE_PATH", options={"SKIP_SAVE"})
    filter_glob: StringProperty(default="*.csv;*.txt", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return _ok(context)

    def _path(self, context) -> str:
        return self.item or lifting.plan(context.scene).pick

    def invoke(self, context, event):
        it = lifting.item_at(self._path(context)) if self._path(context) else None
        if it is None or it.builtin:
            self.report({"WARNING"}, "Pick a crane of your own library first (a built-in always stays a sample)")
            return {"CANCELLED"}
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        path = self._path(context)
        try:
            msg = enter_chart(path, self.filepath)
        except (LL.LibraryError, OSError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        lifting.library(force=True)
        STATE.update(message=msg, error=False)
        self.report({"INFO"}, msg)
        _redraw()
        return {"FINISHED"}


def enter_chart(item_path: str, csv_path: str) -> str:
    """L2's chart entry for an item of the user's library: the CSV's charts replace the item's, the SAMPLE mark comes
    off when they differ from the sample's (``clear_sample``), the file is written again. Returns the sentence."""
    it = lifting.item_at(item_path)
    if it.builtin:
        raise LL.LibraryError("A built-in item always stays SAMPLE DATA: make or copy one into your library first.")
    mass, length = LL.units_of(it.data)
    entry = LL.read_chart_csv(csv_path, mass, length)
    if getattr(entry, "errors", None):
        raise LL.LibraryError(" ".join(entry.errors[:3]))
    data = LL.set_charts(dict(it.data), entry, replace=True)
    msg = LL.clear_sample(data)
    LL.write_item(data, os.path.dirname(os.path.dirname(it.path)))
    return f"{it.name}: chart entered. {msg}"


CLASSES = (FRESING_OT_lifting_make, FRESING_OT_lifting_make_cancel, FRESING_OT_lifting_make_masses,
           FRESING_OT_lifting_chart_csv)
