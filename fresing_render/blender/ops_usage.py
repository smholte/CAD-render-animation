"""The usage tracker's buttons (task 0181): the favourites bar, the declutter prompt, My usage, profiles.

Every one of them changes nothing in the model (they are allowed in the Client view: ``lock.ALLOWED_PREFIXES``).
"""

from __future__ import annotations

import json
import os

import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..core import functions as F
from ..core import usage as core
from ..core import workspaces as W
from ..core.words import plural
from . import usage


def _fn_ok(fid: str) -> bool:
    return fid in F.FUNCTIONS


class FRESING_OT_usage_go(bpy.types.Operator):
    """One of your most used functions. Click: its section opens and the button is pointed at for a few seconds (a
    menu line runs straight away). The bar is sorted when the app starts, never while you work"""

    bl_idname = "fresing.usage_go"
    bl_label = "Go to favourite"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        f = F.FUNCTIONS.get(properties.fid)
        if f is None:
            return cls.__doc__.split(". ")[0]
        n = usage.state()["functions"].get(f.id, [0, 0])[0]
        where = F.MENUS.get(f.panel) or _where(f)
        pinned = " Pinned." if f.id in usage.state()["bar"]["pins"] else ""
        return (f"{f.title} – used {plural(n, 'time')}. Click: opens {where} and points at the button."
                f"{pinned} Pin, unpin or switch the bar off in Fresing > My usage")

    def execute(self, context):
        if not _fn_ok(self.fid):
            return {"CANCELLED"}
        usage.go(context, self.fid)
        return {"FINISHED"}


def _where(f) -> str:
    try:
        from ..core import places
        return places.where(f.panel, "")
    except KeyError:
        return "its panel"


class FRESING_OT_usage_pin(bpy.types.Operator):
    """Pins this function to the favourites bar so it stays whatever you use most (or unpins it). A new pin shows at
    once at the end of the bar; the rest is sorted again at the next start"""

    bl_idname = "fresing.usage_pin"
    bl_label = "Pin to the favourites bar"
    bl_options = {"INTERNAL"}

    fid: StringProperty(options={"SKIP_SAVE"})
    on: BoolProperty(default=True, options={"SKIP_SAVE"})

    def execute(self, context):
        if not _fn_ok(self.fid):
            return {"CANCELLED"}
        usage.pin(self.fid, self.on)
        from . import panels
        panels.redraw()
        return {"FINISHED"}


class FRESING_OT_usage_declutter(bpy.types.Operator):
    """Answers the quiet question about a panel you have not used for a while. Hide: the panel goes out of your side
    panel (in every workspace but Full access; never while a project uses it). Not now: this panel is not asked about
    again. Don't ask again: no more such questions (switch them back on in Fresing > My usage)"""

    bl_idname = "fresing.usage_declutter"
    bl_label = "Hide unused panel"
    bl_options = {"INTERNAL"}

    choice: EnumProperty(items=[("hide", "Hide", "Hides this panel from your side panel. Fresing > My usage > Back to "
                                                 "the workspace as it came shows it again"),
                                ("later", "Not now", "Keeps the panel; it is not asked about again"),
                                ("never", "Don't ask again", "No more questions about unused panels")],
                         options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        return {"hide": "Hides this panel from your side panel (in every workspace but Full access; never while a "
                        "project uses it). Fresing > My usage > Back to the workspace as it came shows it again",
                "later": "Keeps the panel where it is; it is not asked about again",
                "never": "No more questions about unused panels. Switch them back on in Fresing > My usage"
                }.get(properties.choice, cls.__doc__)

    def execute(self, context):
        panel = usage.prompt()
        if not panel:
            return {"CANCELLED"}
        usage.answer(context.scene, self.choice)
        if self.choice == "hide":
            self.report({"INFO"}, f"'{usage.panel_title(panel)}' is hidden. Fresing > My usage > Back to the "
                                  "workspace as it came shows it again")
        return {"FINISHED"}


class FRESING_OT_usage_reset(bpy.types.Operator):
    """Puts the side panel back as the workspace came: the panels you hid show again and your pins are dropped (what
    you used is still counted, so the bar fills itself again at the next start)"""

    bl_idname = "fresing.usage_reset"
    bl_label = "Back to the workspace as it came"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        usage.reset(context.scene)
        self.report({"INFO"}, "Your hidden panels show again and your pins are gone")
        return {"FINISHED"}


class FRESING_OT_usage_clear(bpy.types.Operator):
    """Deletes what the app counted about your work on this PC: clicks, panel openings, time per stage and time saved.
    Your switches, pins and hidden panels stay"""

    bl_idname = "fresing.usage_clear"
    bl_label = "Clear my usage data"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title="Clear my usage data?",
                                                     message="The counts and times on this PC are deleted.",
                                                     confirm_text="Clear", icon="WARNING")

    def execute(self, context):
        usage.clear()
        self.report({"INFO"}, "Your usage data is cleared")
        return {"FINISHED"}


class FRESING_OT_usage_folder(bpy.types.Operator):
    """Shows the usage file in its folder: one small text file on this PC, never sent anywhere"""

    bl_idname = "fresing.usage_folder"
    bl_label = "Show the file"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        usage.save(force=True)
        from . import files
        files.show_in_folder(usage.path())
        return {"FINISHED"}


def _profiles_folder() -> str:
    from . import workspaces
    path, _shared, problem = workspaces.folder(fresh=True)
    if problem:
        raise OSError(problem)
    return path


class FRESING_OT_usage_export(bpy.types.Operator):
    """Saves your side panel as a profile: this project's workspace with your favourites bar and the panels you hid,
    as one file in the library folder "Workspaces". A colleague or a team uses it with Import profile. Your usage
    counts go in only when you tick it"""

    bl_idname = "fresing.usage_export"
    bl_label = "Export profile"
    bl_options = {"INTERNAL"}

    name: StringProperty(name="Name", description="The profile's name, for example \"Offshore team\"")
    with_counts: BoolProperty(name="Include my usage counts", default=False,
                              description="Also writes how often you used each function into the file (so another "
                                          "PC's favourites bar starts from them). Off: only the bar and the hides")

    def invoke(self, context, event):
        from . import workspaces
        if not self.name:
            self.name = f"{workspaces.name_of(context.scene)} – my profile"
        return context.window_manager.invoke_props_dialog(self, width=420, title="Export profile",
                                                          confirm_text="Save")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "name")
        col.prop(self, "with_counts")

    def execute(self, context):
        try:
            path = export_profile(context.scene, self.name, self.with_counts)
        except (OSError, ValueError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Profile saved: {path}")
        return {"FINISHED"}


def export_profile(scene, name: str, with_counts: bool = False) -> str:
    """Write the profile (an own-workspace file with the bar and the hides) into the Workspaces folder; this project
    uses it from now on. Returns the file."""
    from . import workspaces
    name = W.clean_name(name)
    problem = W.name_problem(name)
    if problem:
        raise ValueError(problem)
    ws = W.make_own(name, workspaces.current(scene), workspaces.ticks(scene), "Profile: workspace, favourites bar "
                                                                              "and hidden panels")
    ws.hide = tuple(sorted(set(ws.hide) | set(workspaces.PERSONAL["hide"])))
    ws.extra = core.profile_part(usage.state(), with_counts)
    path = W.save_in(_profiles_folder(), ws)
    workspaces.forget_scan()
    workspaces.library(force=True)
    s = scene.fresing
    s.ws_name, s.ws_data, s.ws_ticks = ws.name, ws.to_json(), ""
    workspaces.apply(scene)
    return path


def import_profile(scene, filepath: str, with_counts: bool = False) -> str:
    """Use a profile file: it is copied into the Workspaces folder (replacing an own workspace of its name), this
    project switches to it and the favourites bar takes its pins. Returns the workspace's name."""
    from . import workspaces
    with open(filepath, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    ws = W.from_dict(data)                                     # ValueError: not a workspace / profile file
    if W.key_of(ws.name) in W.RESERVED:
        raise ValueError(f"'{ws.name}' is the app's own workspace: rename the profile file's name first")
    ws.extra.pop("usage", None)                                # the library copy never carries someone's counts
    W.save_in(_profiles_folder(), ws)
    workspaces.forget_scan()
    workspaces.switch(scene, ws.name)
    core.take_profile(usage.state(), data, with_counts)
    usage.changed()
    usage.save()
    usage.apply_personal(scene)
    return ws.name


class FRESING_OT_usage_import(bpy.types.Operator, ImportHelper):
    """Uses a profile file (a workspace with a favourites bar, from Export profile): it is copied into your library
    folder "Workspaces" – replacing your own workspace of the same name –, this project switches to it and your
    favourites bar takes its pins"""

    bl_idname = "fresing.usage_import"
    bl_label = "Import profile"
    bl_options = {"INTERNAL"}

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    with_counts: BoolProperty(name="Add the usage counts in the file", default=False,
                              description="Adds the counts a profile carries to yours (your favourites bar is "
                                          "sorted with them at the next start). Off: only its bar and hides")

    def execute(self, context):
        try:
            name = import_profile(context.scene, self.filepath, self.with_counts)
        except (OSError, ValueError, KeyError) as exc:
            self.report({"ERROR"}, f"Not a profile: {exc}")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Profile '{name}' is used in this project")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# My usage
# ---------------------------------------------------------------------------

TOP_ROWS = 10


class FRESING_OT_usage_window(bpy.types.Operator):
    """What you use, counted on this PC only (nothing is sent): your most used functions with a pin each, where your
    time goes per stage, and the time the app saved you (an estimate, with how it is worked out). Also the switches:
    Track my usage, the favourites bar, the questions about unused panels"""

    bl_idname = "fresing.usage_window"
    bl_label = "My usage"
    bl_options = {"INTERNAL"}

    def invoke(self, context, event):
        usage.save()
        return context.window_manager.invoke_props_dialog(self, width=560, title="My usage", confirm_text="Close")

    def execute(self, context):
        return {"FINISHED"}

    def draw(self, context):
        draw_window(self.layout, context)


def draw_window(layout, context) -> None:
    s = usage.state()
    wm = context.window_manager
    col = layout.column(align=True)
    col.label(text=f"Counted on this PC only, never sent: {plural(s['sessions'], 'app start')}"
                   + (f" since {s['first']}" if s["first"] else ""), icon="LOCKED")
    row = layout.row()
    row.prop(wm, "fresing_usage_track")
    row.operator("fresing.usage_folder", icon="FILE_FOLDER")
    if not usage.counting() and s["track"]:
        sub = layout.row()
        sub.active = False
        sub.label(text="Not counting in this run (a test or a background run)", icon="INFO")

    layout.separator()
    layout.label(text="Favourites bar", icon="SOLO_ON")
    row = layout.row()
    row.prop(wm, "fresing_usage_bar")
    sub = row.row()
    sub.enabled = s["bar"]["on"]
    sub.prop(wm, "fresing_usage_bar_size")
    ranking = core.ranking(s)
    pins = s["bar"]["pins"]
    rows = list(dict.fromkeys(pins + ranking))[:max(TOP_ROWS, len(pins))]
    if rows:
        box = layout.box().column(align=True)
        for fid in rows:
            f = F.FUNCTIONS.get(fid)
            if f is None:
                continue
            r = box.row(align=True)
            n = s["functions"].get(fid, [0, 0])[0]
            r.label(text=f.title)
            right = r.row(align=True)
            right.alignment = "RIGHT"
            right.label(text=plural(n, "use"))
            if fid in core.bar_candidates():
                op = right.operator("fresing.usage_pin", text="", icon="PINNED" if fid in pins else "UNPINNED",
                                    emboss=False)
                op.fid, op.on = fid, fid not in pins
    else:
        _grey(layout, f"Nothing yet: a function used {core.MIN_CLICKS} times or more joins the bar at the next start.")

    layout.separator()
    layout.label(text="Where your time goes (active time; idle over 2 min is left out)", icon="TIME")
    for _k, title, sec, share in core.stage_rows(s):
        r = layout.row()
        split = r.split(factor=0.36)
        split.label(text=title)
        split.progress(factor=share, text=core.duration(sec) if sec else "–")

    layout.separator()
    rows = core.saved_rows(s)
    total = sum(r[1] for r in rows)
    layout.label(text=f"Time saved – an estimate: about {core.duration(total)}" if rows else
                 "Time saved – an estimate", icon="SORTTIME")
    if rows:
        box = layout.box().column(align=True)
        for fid, sec, n in rows[:8]:
            f = F.FUNCTIONS[fid]
            r = box.row()
            r.label(text=f"{f.title}: {plural(n, 'use')}")
            r2 = r.row()
            r2.alignment = "RIGHT"
            r2.label(text=f"~{core.duration(sec)}")
            _grey(box, "    " + core.basis(fid))
    _grey(layout, "Worked out from the uses counted here and a guess of the manual work")
    _grey(layout, "per use or per part – not a measurement.")

    layout.separator()
    layout.label(text="Unused panels", icon="HIDE_ON")
    row = layout.row()
    row.prop(wm, "fresing_usage_declutter")
    sub = row.row()
    sub.enabled = s["declutter"]["on"]
    sub.prop(wm, "fresing_usage_threshold")
    n = len({F.FUNCTIONS[h].panel for h in s["hidden"] if h in F.FUNCTIONS})
    col = layout.column(align=True)
    col.operator("fresing.usage_reset", icon="LOOP_BACK",
                 text="Back to the workspace as it came" + (f" ({plural(n, 'hidden panel')})" if n else ""))
    row = col.row(align=True)
    row.operator("fresing.usage_export", text="Export profile…", icon="EXPORT")
    row.operator("fresing.usage_import", text="Import profile…", icon="IMPORT")
    col.operator("fresing.usage_clear", icon="TRASH")


def _grey(layout, text: str) -> None:
    row = layout.row()
    row.active = False
    row.label(text=text)


# ---------------------------------------------------------------------------
# the switches as settings (so the window stays open while they change)
# ---------------------------------------------------------------------------

def _getter(*keys):
    def get(self):
        d = usage.state()
        for k in keys:
            d = d[k]
        return d
    return get


def _setter(*keys, then=None):
    def set_(self, value):
        d = usage.state()
        for k in keys[:-1]:
            d = d[k]
        d[keys[-1]] = value
        usage.changed()
        usage.save()
        if then is not None:
            then()
    return set_


def _bar_changed():
    from . import panels
    panels.redraw()


def _declutter_changed():
    if not usage.state()["declutter"]["on"]:
        usage._S["prompt"] = ""
    _bar_changed()


SETTINGS = {
    "fresing_usage_track": BoolProperty(
        name="Track my usage", get=_getter("track"), set=_setter("track"),
        description="Counts which functions you use, on this PC only (one small file in your settings folder; nothing "
                    "is ever sent). Off: nothing new is counted; what was counted stays until you clear it"),
    "fresing_usage_bar": BoolProperty(
        name="Show the favourites bar", get=_getter("bar", "on"), set=_setter("bar", "on", then=_bar_changed),
        description="Your most used functions as buttons at the top of the Fresing tab, sorted when the app starts"),
    "fresing_usage_bar_size": IntProperty(
        name="Buttons", min=core.BAR_MIN, max=core.BAR_MAX, get=_getter("bar", "size"),
        set=_setter("bar", "size"),
        description="How many functions the favourites bar holds (pinned ones always show). Takes effect at the next "
                    "start"),
    "fresing_usage_declutter": BoolProperty(
        name="Offer to hide unused panels", get=_getter("declutter", "on"),
        set=_setter("declutter", "on", then=_declutter_changed),
        description="Now and then a quiet question at the top of the Fresing tab: hide a panel you have not used for a "
                    "while? At most one per start, never about something the open project uses"),
    "fresing_usage_threshold": IntProperty(
        name="After starts", min=1, max=1000, get=_getter("declutter", "threshold"),
        set=_setter("declutter", "threshold"),
        description="A panel is offered for hiding when you have not used it in this many app starts"),
}

CLASSES = (FRESING_OT_usage_go, FRESING_OT_usage_pin, FRESING_OT_usage_declutter, FRESING_OT_usage_reset,
           FRESING_OT_usage_clear, FRESING_OT_usage_folder, FRESING_OT_usage_export, FRESING_OT_usage_import,
           FRESING_OT_usage_window)


def _draw_help(self, context):
    self.layout.separator()
    self.layout.operator("fresing.usage_window", text="My usage…", icon="TIME")


def register() -> None:
    for name, prop in SETTINGS.items():
        setattr(bpy.types.WindowManager, name, prop)
    bpy.types.TOPBAR_MT_help.remove(_draw_help)
    bpy.types.TOPBAR_MT_help.append(_draw_help)
    usage.register()


def unregister() -> None:
    usage.unregister()
    bpy.types.TOPBAR_MT_help.remove(_draw_help)
    for name in SETTINGS:
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
