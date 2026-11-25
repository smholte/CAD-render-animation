"""The first-start set-up (task 0276): one window that walks a new user through the app's set-up, in place of Blender's
own first-start window (language, keys, theme).

**When it opens:** the first start in a settings folder (``core/start.py`` ``decide`` = "setup"; the welcome of 0199
before it), at most three starts until it is finished or skipped; never in a background run, the queue, the PC check,
the kit, with ``FRESING_NO_WELCOME``, with simulated events (real-app tests set ``FRESING_WELCOME_TEST``) or in the
Client view. An update from a version before this task brings What's new, not the set-up. A company's set-up file
(``.frsetup``, task 0272) may say ``"first_setup": "skip"``: such PCs start straight in. Fresing > Set up again… opens
it any time.

**Blender's own first-start window** shows while Blender's settings folder has no saved preferences. The app template
calls ``at_load`` when the start-up file is read – before Blender makes its splash: Blender's choices (its keys, its
theme, the language) are written and saved (``blender_choices``), so that window never comes, and on the start that
shows the set-up the splash is left out once (``prefs.view.show_splash`` off for this start, on again a moment later).

**The window** is made like Fresing Settings (task 0271): ``ops_setup.open_window`` with the screen mark
``fr_first_setup``, its page in the 3D view's toolbar region. Steps (``core/first_setup.STEPS``), each with Back /
Next, a step bar on top and **Skip set-up** always there:

1. Welcome – what the app is; the language of Blender's menus (Fresing's own texts are English).
2. Your work – ticks → "Workspace for new projects" (``prefs.default_workspace``; the rule: ``core.RULE``) and the
   Learning hub's first chapter.
3. Your PC – the PC check's Quick lines in a background Blender (``first_setup_probe.py``), said in plain words; the
   suggested Live preview is set (``prefs.live_preview``, the button's remembered choice).
4. Your company and your folders – the set-up file found by itself or **Open set-up file…** / dropped on the window,
   what it sets ("Different from standard"), the STEP models folder and where renders go.
5. The Learning hub – make it now (0275's card in the main window; go on meanwhile) or later.
6. Done – Import your first STEP… · Open the Learning hub · Open the demo project · Save my set-up as a file….

Every choice is one that exists elsewhere (Fresing Settings, Locations, Blender's preferences); the ticks stay in the
start file. Nothing leaves the PC.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, PointerProperty, StringProperty

from ..core import first_setup as core
from . import ops_setup, ui
from .ops_setup import FIRST_SETUP_MARK

KEY = "first_setup"
LOCKED_TEXT = "Not in the Client view: switch to another workspace first (Workspace at the top of the Fresing tab)"
SIZE = (560, 640)                  # px at UI scale 1
TITLE = "Set up Fresing Render"
PROBE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "first_setup_probe.py")

_S: dict = {"quiet": False, "splash_hidden": False, "proc": None, "out": "", "probe": None, "started": 0.0, "splash_off": False, "at_load": False,
            "pending": False, "prefilled": False}


# ---------------------------------------------------------------------------
# Blender's own first-start window
# ---------------------------------------------------------------------------

def userpref_saved() -> bool:
    return os.path.isfile(os.path.join(bpy.utils.user_resource("CONFIG"), "userpref.blend"))


def blender_choices(language: str = "") -> None:
    """What Blender's own quick set-up asks, written by the app and saved, so that window never comes: Blender's own
    keys (the app's key rules of task 0253 sit on top), Blender's own theme, English unless ``language``."""
    try:
        kc = bpy.context.window_manager.keyconfigs
        if kc.active is not None and kc.active.name != "Blender" and "Blender" in kc:
            kc.active = kc["Blender"]
    except (AttributeError, TypeError, KeyError):
        pass
    if language:
        set_language(language, save=False)
    save_prefs()


def save_prefs() -> bool:
    try:
        bpy.context.preferences.is_dirty = True
        bpy.ops.wm.save_userpref()
        return True
    except Exception as exc:  # noqa: BLE001 - Blender saves changed preferences when it closes anyway
        print("Fresing Render: Blender's preferences not saved:", exc)
        return False


def at_load(_name: str = "") -> None:
    """Called by the app template when the start-up file is read (its load_post), before Blender makes its splash:
    Blender's preferences saved when there are none; on the start that shows the set-up, no splash this time."""
    if bpy.app.background or _S["at_load"]:
        return
    _S["at_load"] = True
    if not userpref_saved():
        blender_choices()
    from . import welcome
    if welcome.at_start() == "setup":
        p = bpy.context.preferences
        if p.view.show_splash:
            p.view.show_splash = False            # this start only: the set-up is the first window
            _S["splash_off"] = _S["splash_hidden"] = True
            bpy.app.timers.register(_splash_back, first_interval=3.0)


def _splash_back():
    if _S["splash_off"]:
        _S["splash_off"] = False
        bpy.context.preferences.view.show_splash = True
    return None


def set_language(code: str, save: bool = True) -> bool:
    """Blender's own menus in ``code`` (Fresing's texts stay English; new objects keep English names)."""
    if not core.language_ok(code):
        return False
    v = bpy.context.preferences.view
    try:
        if v.language != code:
            v.language = code
        if code != "en_US":
            v.use_translate_interface = True
            v.use_translate_tooltips = True
            v.use_translate_new_dataname = False
    except (TypeError, ValueError, AttributeError) as exc:
        print("Fresing Render: language not set:", exc)
        return False
    if save:
        save_prefs()
    return True


def languages_here() -> list:
    """The set-up's languages that this Blender has."""
    try:
        have = {i.identifier for i in bpy.types.PreferencesView.bl_rna.properties["language"].enum_items}
    except (KeyError, AttributeError):
        have = set()
    return [x for x in core.LANGUAGES if not have or x[0] in have or x[0] == "en_US"]


# ---------------------------------------------------------------------------
# the values
# ---------------------------------------------------------------------------

def _lang_items(_self, _context):
    return [(k, t, d) for k, t, d in languages_here()]


def _language_changed(self, context):
    set_language(self.language)


def _work_changed(self, context):
    if not _S["quiet"]:                          # (pre-filling the window writes nothing: only a click does)
        apply_work(ticks(self))


def apply_work(t: list) -> str:
    """The ticks' workspace into "Workspace for new projects" (kept by the settings file)."""
    from . import prefs
    name, _why = core.workspace_for(t)
    p = prefs.get()
    if p is not None and p.default_workspace != name:
        p.default_workspace = name
    return name


_ANN = {
    "step": EnumProperty(name="Step", items=[(k, t, "") for k, t in core.STEPS], default="welcome"),
    "language": EnumProperty(name="Language", items=_lang_items, update=_language_changed,
                             description="The language of Blender's own menus under the app. Fresing Render's own "
                                         "buttons and texts are in English"),
}
for _k, _title, _ws, _ch in core.WORK:
    _ANN["work_" + _k] = BoolProperty(name=_title, default=False, update=_work_changed,
                                      description=f"You do {_title.lower()}: sets the workspace new projects start "
                                                  "in and what the Learning hub shows first")

FRFirstSetup = type("FRFirstSetup", (bpy.types.PropertyGroup,),
                    {"__annotations__": _ANN, "__module__": __name__,
                     "__doc__": "The choices of the first-start set-up while its window is open (task 0276)"})


def values(context=None):
    wm = getattr(context or bpy.context, "window_manager", None)
    return getattr(wm, "fresing_first_setup", None) if wm is not None else None


def ticks(v) -> list:
    return [k for k in core.WORK_KEYS if getattr(v, "work_" + k, False)]


def step_index(v) -> int:
    return core.STEP_KEYS.index(v.step) if v is not None and v.step in core.STEP_KEYS else 0


def suggested_chapter() -> str:
    """The Learning hub's chapter for the work ticked in the set-up ('' when nothing was ticked)."""
    try:
        from . import welcome
        return core.chapter_for(welcome.load().get("setup", {}).get("work") or [])
    except Exception:  # noqa: BLE001
        return ""


def from_setups() -> dict:
    """What the set-up files in use say about the first start (task 0272's ``first_start``)."""
    try:
        from . import locations
        return core.from_setups([s.first_start for s, _b, _u in locations.setups()])
    except Exception:  # noqa: BLE001
        return core.from_setups([])


def setup_workspace() -> tuple:
    """(workspace, badge) a set-up file sets for new projects, else ('', '')."""
    try:
        from . import locations
        for s, _b, _u in locations.setups():
            ws = s.settings.get("default_workspace") or s.first_start.get("workspace")
            if isinstance(ws, str) and ws:
                return ws, s.title()
    except Exception:  # noqa: BLE001
        pass
    return "", ""


def prefill(v) -> None:
    """The values a window starts with: the ticks kept in the start file, else what a set-up file says, else the
    current "Workspace for new projects"; the language Blender has."""
    from . import welcome, workspaces
    st = welcome.load()
    fs = from_setups()
    if fs["workspace"] and not workspaces.chosen():     # a company's set-up file names the workspace (IT pre-set)
        from . import prefs
        p = prefs.get()
        if p is not None:
            p.default_workspace = fs["workspace"]
    t = list(st.get("setup", {}).get("work") or fs["work"])
    if not t:
        t = core.ticks_for(fs["workspace"] or setup_workspace()[0] or workspaces.chosen())
    _S["quiet"] = True
    try:
        for k in core.WORK_KEYS:
            name = "work_" + k
            if getattr(v, name) != (k in t):
                setattr(v, name, k in t)
    finally:
        _S["quiet"] = False
    lang = bpy.context.preferences.view.language
    if fs["language"] and st.get("setup", {}).get("state") == "":
        lang = fs["language"]
    if core.language_ok(lang) and v.language != lang:
        v.language = lang
    step = st.get("setup", {}).get("step", "")
    v.step = step if step in core.STEP_KEYS and step != "done" else "welcome"


# ---------------------------------------------------------------------------
# step 3: the PC check's Quick lines in a background Blender
# ---------------------------------------------------------------------------

def probe_running() -> bool:
    proc = _S["proc"]
    return proc is not None and proc.poll() is None


def start_probe() -> str:
    """Start the PC lines in a background Blender; '' when started, else why not."""
    if probe_running():
        return ""
    exe = bpy.app.binary_path
    try:
        from .. import winexe
        exe = winexe.console_exe(exe) or exe          # Windows: blender.exe (no window: CREATE_NO_WINDOW below)
    except Exception:  # noqa: BLE001
        pass
    if not exe or not os.path.isfile(exe):
        return "Blender's program was not found"
    out = os.path.join(tempfile.gettempdir(), f"fresing_setup_probe_{os.getpid()}.json")
    try:
        os.remove(out)
    except OSError:
        pass
    kwargs = ({"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32"
              else {"start_new_session": True})
    env = dict(os.environ)
    env.pop("FRESING_WELCOME_TEST", None)
    try:
        _S["proc"] = subprocess.Popen([exe, "--background", "--python", PROBE, "--", out,
                                       os.environ.get(core.PROBE_ENV, "")],
                                      cwd=os.path.dirname(exe), env=env, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL, **kwargs)
    except OSError as exc:
        return f"The PC check could not start: {exc}"
    _S.update(out=out, probe=None, started=time.time())
    if not bpy.app.timers.is_registered(_watch_probe):
        bpy.app.timers.register(_watch_probe, first_interval=0.5)
    return ""


def _watch_probe():
    proc = _S["proc"]
    if proc is None:
        return None
    if proc.poll() is None:
        ops_setup.redraw_all()
        return 0.5
    _S["proc"] = None
    try:
        with open(_S["out"], encoding="utf-8") as fh:
            _S["probe"] = json.load(fh)
    except (OSError, ValueError):
        _S["probe"] = {"error": f"no answer (Blender stopped with code {proc.returncode})", "results": []}
    try:
        os.remove(_S["out"])
    except OSError:
        pass
    summary = core.pc_summary(_S["probe"]) if not core.probe_failed_text(_S["probe"]) else None
    if summary is not None:
        from . import prefs
        p = prefs.get()
        if p is not None and p.live_preview != summary["live_preview"]:
            p.live_preview = summary["live_preview"]        # the Live preview button's remembered choice
    ops_setup.redraw_all()
    return None


def probe_seconds() -> int:
    return int(time.time() - _S["started"]) if _S["started"] else 0


# ---------------------------------------------------------------------------
# the window
# ---------------------------------------------------------------------------

def windows() -> list:
    wm = getattr(bpy.context, "window_manager", None)
    out = []
    for win in (wm.windows if wm is not None else ()):
        try:
            if win.screen.get(FIRST_SETUP_MARK):
                out.append(win)
        except (AttributeError, ReferenceError):
            continue
    return out


def client_view() -> bool:
    try:
        from . import lock
        return bool(lock.ON[0])
    except Exception:  # noqa: BLE001
        return False


def open_window(context=None, at_start: bool = False) -> str:
    """Open the set-up window ('' when it opens or is open, else why not)."""
    context = context or bpy.context
    if bpy.app.background:
        return "The set-up opens only in the app's own window"
    if client_view():
        return "The set-up does not open in the Client view: switch to another workspace first"
    v = values(context)
    there = windows()
    if there:
        from .. import winplace
        winplace.raise_window(there[0], KEY)
        return ""
    if v is not None and (not at_start or not _S["prefilled"]):
        prefill(v)
        _S["prefilled"] = True
    if ops_setup.busy():
        return "A window is opening: a moment, then press again"
    win, area, _region = ops_setup.main_view(context)
    if area is None:
        return "The set-up needs a 3D view in the main window"
    if win.screen.show_fullscreen:
        return "The 3D view fills the whole window: go back to the normal layout first (Ctrl+Space)"
    from . import ops_make, ops_settings
    size = ops_make.kept_size(KEY) or SIZE
    ops_setup.open_window(win, area, mark=FIRST_SETUP_MARK, value=KEY, done=ops_settings._opened, size=size)
    return ""


def close_window(only=None) -> None:
    """Close the set-up window(s); ``only`` = the keys (``_window_key``) of the ones to close, else all."""
    from . import ops_make

    def chosen():
        return [w for w in windows() if only is None or _window_key(w) in only]

    for win in chosen():
        try:
            ops_make.remember(win)
        except Exception:  # noqa: BLE001
            pass

    def later():
        for win in chosen():
            try:
                with bpy.context.temp_override(window=win, screen=win.screen, area=win.screen.areas[0]):
                    bpy.ops.wm.window_close()
            except (RuntimeError, ReferenceError, IndexError) as exc:
                print("Fresing Render: the set-up window did not close:", exc)
        return None

    bpy.app.timers.register(later, first_interval=0.01)


def remember(how: str = "") -> None:
    """Write where the set-up stands into the start file: ``how`` "done", "skipped" or "" (left on the way)."""
    from . import welcome
    v = values()
    state = welcome.core.setup_finished(welcome.load(), welcome.version(), how,
                                        step=v.step if v is not None else "",
                                        work=ticks(v) if v is not None else None)
    welcome.save(state)


def in_main(fn) -> None:
    """Run ``fn(context)`` in the main window a moment later (after the set-up window's button is done)."""
    def later():
        win, area, region = ops_setup.main_view(bpy.context)
        kw = {"window": win, "screen": win.screen, "area": area, "region": region} if win is not None else {}
        try:
            with bpy.context.temp_override(**kw):
                fn(bpy.context)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: after the set-up:", exc)
        return None

    bpy.app.timers.register(later, first_interval=0.15)


# ---------------------------------------------------------------------------
# the Learning hub and the demo, as the set-up sees them
# ---------------------------------------------------------------------------

def hub_state() -> tuple:
    """("making", text) while it is made, ("ready", "") when this version's whole hub is there, ("none", "")."""
    from . import ops_tour, tour, welcome
    if ops_tour.building().get("running"):
        return "making", ops_tour.progress_text()
    folder = tour.default_folder()
    if tour.ready_path(folder, welcome.version()) and len(tour.made_sets(folder, welcome.version())) == len(tour.SETS):
        return "ready", ""
    return "none", ""


def demo_ready() -> bool:
    try:
        from . import demo, welcome
        return bool(demo.PUBLIC) and demo.exists(demo.default_folder(), welcome.version())
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def draw_step_bar(layout, v) -> None:
    i = step_index(v)
    row = layout.row(align=True)
    for n, (k, title) in enumerate(core.STEPS):
        op = row.operator("fresing.first_setup_step", text=f"{n + 1}" if n != i else f"{n + 1} {title}",
                          depress=n == i)
        op.go = "TO"
        op.to = k


def draw_welcome(layout, context, v) -> None:
    from . import welcome
    ui.wrap(layout, context, "Photo-realistic pictures and animations of your STEP assemblies – machines, cranes, "
                             "vessels –, made by the people who design them. No rendering knowledge needed.")
    ui.wrap(layout, context, "This set-up takes a minute: your work, a quick look at your PC, your company's set-up "
                             "and folders, and the Learning hub. Skip it any time; Fresing > Set up again… runs it "
                             "again.", icon="INFO")
    ui.gap(layout)
    layout.label(text="Language", icon="WORLD")
    layout.prop(v, "language", text="")
    ui.hint(layout, context, "Fresing Render's own buttons and texts are in English. Another language changes "
                             "Blender's menus under them (Nederlands, Deutsch).")
    if welcome.version():
        ui.hint(layout, context, f"Fresing Render {welcome.version()}")


def draw_work(layout, context, v) -> None:
    layout.label(text="What do you do? Tick all that fit", icon="USER")
    col = layout.grid_flow(row_major=True, columns=2, even_columns=True, align=True)   # 13 ticks (task 0321)
    for k, title, _ws, _ch in core.WORK:
        col.prop(v, "work_" + k, text=title)
    ui.gap(layout)
    from . import workspaces
    box = layout.box()
    box.label(text=f"New projects start in: {workspaces.default_name()}", icon="WORKSPACE")
    ui.hint(box, context, core.RULE)
    ws, badge = setup_workspace()
    if ws:
        ui.wrap(layout, context, f"Your set-up file ({badge}) chose {ws}; your ticks change it for you.", icon="INFO")
    ch = core.chapter_for(ticks(v))
    if ch:
        from . import tour
        ui.hint(layout, context, f"The Learning hub opens on its chapter {tour.GROUP_TITLES.get(ch, ch)}.")


def draw_pc(layout, context, v) -> None:
    probe = _S["probe"]
    if probe_running():
        layout.label(text=f"Looking at your PC … {probe_seconds()} s", icon="TIME")
        ui.hint(layout, context, "A second Blender in the background imports the test crane and renders one picture "
                                 "on the graphics card (about 20 s to a minute). Go on meanwhile if you like.")
        return
    if probe is None:
        ui.wrap(layout, context, "A quick look at your PC: is there a graphics card the renders can use, how fast is "
                                 "a picture – and what to set for it. Nothing leaves your PC.")
        ui.big(layout, "fresing.first_setup_pc", "Check my PC", icon="DESKTOP")
        return
    bad = core.probe_failed_text(probe)
    if bad:
        ui.wrap(layout, context, bad, icon="ERROR", alert=True)
        layout.operator("fresing.first_setup_pc", text="Try again", icon="FILE_REFRESH")
        return
    s = core.pc_summary(probe)
    box = layout.box()
    for icon, text in s["lines"]:
        ui.wrap(box, context, text, icon=icon)
    ui.gap(layout)
    ui.wrap(layout, context, "Suggested: " + s["suggest"], icon="LIGHT")
    if s["slow"]:
        ui.wrap(layout, context, s["slow"], icon="ERROR", alert=True)
    ui.hint(layout, context, "Live preview is set as suggested. The full PC check (Fresing > Tools and checks) "
                             "tests every function.")
    layout.operator("fresing.first_setup_pc", text="Check again", icon="FILE_REFRESH")


def draw_company(layout, context, v) -> None:
    from . import locations
    from ..core import locations as L
    sets = locations.setups()
    layout.label(text="A set-up file from your company?", icon="FILE_FOLDER")
    if sets:
        for s, _b, _u in sets:
            ui.wrap(layout, context, f"In use: {s.name} ({s.title()})", icon="CHECKMARK")
        rows = [r for r in locations.differences() if not r.own]      # what the set-up files set
        if rows:
            box = layout.box()
            box.label(text="Different from standard")
            for r in rows[:8]:
                ui.wrap(box, context, f"{setting_title(r)}: {r.value}  ·  {r.source}")
            if len(rows) > 8:
                ui.hint(box, context, f"… and {len(rows) - 8} more in Fresing Settings > Locations")
    else:
        ui.wrap(layout, context, "Do you have a Fresing set-up file (.frsetup) from your company, department or a "
                                 "colleague? It brings their folders for models, logos and materials, and their "
                                 "settings. Open it, or drop it on this window. No file: go on with Next.")
    layout.operator("fresing.loc_setup_add", text="Open set-up file…", icon="FILEBROWSER")
    ui.gap(layout)
    layout.label(text="Your STEP models", icon="FILE_3D")
    step = locations.folders("step")
    for loc in step[:3]:
        ui.hint(layout, context, f"{loc.path}  ·  {loc.badge}")
    if not step:
        ui.hint(layout, context, "No folder yet.")
    op = layout.operator("fresing.loc_folder_add", text="Add my STEP models folder…", icon="ADD")
    op.kind = "step"
    ui.gap(layout)
    layout.label(text="Where renders go", icon="EXPORT")
    default = locations.default_place()
    place = next((p for p in locations.places() if p.key == default), None)
    layout.operator_menu_enum("fresing.loc_place_default", "place",
                              text=place.name if place is not None else L.BUILTIN_PLACES[0][1])
    ui.hint(layout, context, "Standard: next to the project, in a folder Renders. More in Fresing Settings > "
                             "Exports.")


def setting_title(row) -> str:
    """A "Different from standard" row's name as the Settings window shows it (its property's name)."""
    if row.key.startswith("setting:"):
        from . import prefs
        prop = prefs.FRESING_AP_prefs.bl_rna.properties.get(row.key.split(":", 1)[1])
        if prop is not None and prop.name:
            return prop.name
    return row.what


def draw_hub(layout, context, v) -> None:
    state, text = hub_state()
    ui.wrap(layout, context, "The Learning hub shows every function on small test models, one stop at a time: "
                             "View, Show me, or Build it yourself. Your own projects are not touched.")
    ui.gap(layout)
    if state == "making":
        layout.label(text=text or "Making the Learning hub …", icon="TIME")
        ui.hint(layout, context, "Go on with Next: it is made in the background, the card in the main window shows "
                                 "how far it is.")
    elif state == "ready":
        layout.label(text="The Learning hub of this version is ready.", icon="CHECKMARK")
    else:
        from . import welcome
        ui.big(layout, "fresing.first_setup_hub", "Make it now", icon="VIEW_CAMERA")
        ui.hint(layout, context, f"About {welcome.tour_minutes()} minutes in the background; you can go on. Or later: "
                                 "Fresing > Open the Learning hub.")


def draw_done(layout, context, v) -> None:
    ui.wrap(layout, context, "All set. What first?", icon="CHECKMARK")
    ui.gap(layout)
    ui.primary(layout, "fresing.first_setup_finish", "Import your first STEP…", icon="IMPORT").action = "IMPORT"
    state, text = hub_state()
    row = ui.big_row(layout, ui.MEDIUM)
    row.enabled = state != "making"
    row.operator("fresing.first_setup_finish", text="Open the Learning hub" if state != "making" else
                 (text or "Making the Learning hub …"), icon="VIEW_CAMERA").action = "HUB"
    row = ui.big_row(layout, ui.MEDIUM)
    row.operator("fresing.first_setup_finish", text="Open the demo project" if demo_ready() else
                 "Make the demo project…", icon="FILE_BLEND").action = "DEMO"
    ui.gap(layout)
    layout.operator("fresing.loc_setup_save", text="Save my set-up as a file…", icon="EXPORT")
    ui.hint(layout, context, "For a colleague: your folders and settings in one .frsetup file.")
    ui.gap(layout)
    ui.hint(layout, context, "Change any of this in Fresing > Settings…; Fresing > Set up again… runs this again.")


DRAW = {"welcome": draw_welcome, "work": draw_work, "pc": draw_pc, "company": draw_company, "hub": draw_hub,
        "done": draw_done}


class FRESING_PT_first_setup(bpy.types.Panel):
    """The first-start set-up's page (task 0276): step bar, the step, Back / Next and Skip set-up."""
    bl_space_type = "VIEW_3D"
    bl_region_type = "TOOLS"
    bl_label = TITLE
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        win = getattr(context, "window", None)
        try:
            return bool(win is not None and win.screen.get(FIRST_SETUP_MARK))
        except (AttributeError, ReferenceError):
            return False

    def draw(self, context):
        layout = self.layout
        v = values(context)
        row = layout.row(align=True)
        row.scale_y = 1.2
        row.label(text=TITLE, icon="PREFERENCES")
        right = row.row(align=True)
        right.alignment = "RIGHT"
        right.operator("fresing.first_setup_skip", text="Skip set-up", emboss=False)
        if v is None:
            return
        draw_step_bar(layout, v)
        ui.gap(layout, line=True)
        i = step_index(v)
        key, title = core.STEPS[i]
        layout.label(text=f"{i + 1} of {len(core.STEPS)}: {core.HEADINGS.get(key, title)}")
        try:
            DRAW[v.step](layout.column(), context, v)
        except Exception as exc:  # noqa: BLE001 - say it, keep Back / Next / Skip working
            print("Fresing Render: the set-up step does not draw:", exc)
            ui.wrap(layout, context, f"This step could not draw ({exc}).", icon="ERROR", alert=True)
        ui.gap(layout, line=True)
        row = layout.row(align=True)
        row.scale_y = 1.3
        back = row.row(align=True)
        back.enabled = i > 0
        back.operator("fresing.first_setup_step", text="Back", icon="BACK").go = "BACK"
        if i < len(core.STEPS) - 1:
            row.operator("fresing.first_setup_step", text="Next", icon="FORWARD", depress=True).go = "NEXT"
        else:
            row.operator("fresing.first_setup_finish", text="Close", icon="CHECKMARK", depress=True).action = "CLOSE"


# ---------------------------------------------------------------------------
# operators
# ---------------------------------------------------------------------------

class FRESING_OT_first_setup(bpy.types.Operator):
    """Runs the first-start set-up again: your work and workspace, a look at your PC, your company's set-up file and
    folders, the Learning hub. Every choice is also in Fresing Settings"""

    bl_idname = "fresing.first_setup"
    bl_label = "Set up again…"
    bl_options = set()

    @classmethod
    def description(cls, context, props):
        if client_view():
            return LOCKED_TEXT
        return " ".join(cls.__doc__.split())

    def execute(self, context):
        v = values(context)
        if v is not None:
            prefill(v)
            v.step = "welcome"
        _S["prefilled"] = True
        why = open_window(context)
        if why:
            self.report({"WARNING"}, why)
            return {"CANCELLED"}
        return {"FINISHED"}


class FRESING_OT_first_setup_step(bpy.types.Operator):
    """Goes to another step of the set-up. Nothing is lost: every choice is kept as you make it"""

    bl_idname = "fresing.first_setup_step"
    bl_label = "Set-up step"
    bl_options = {"INTERNAL"}

    go: EnumProperty(items=[("NEXT", "Next", "The next step"), ("BACK", "Back", "The step before"),
                            ("TO", "To", "This step")], default="NEXT", options={"SKIP_SAVE"})
    to: StringProperty(default="", options={"SKIP_SAVE", "HIDDEN"})

    @classmethod
    def description(cls, context, props):
        go = getattr(props, "go", "NEXT")
        if go == "TO":
            title = dict(core.STEPS).get(getattr(props, "to", ""), "")
            return f"Go to the step {title}" if title else cls.__doc__
        return {"NEXT": "The next step of the set-up (what you chose here is kept already)",
                "BACK": "The step before"}.get(go, cls.__doc__)

    def execute(self, context):
        v = values(context)
        if v is None:
            return {"CANCELLED"}
        i = step_index(v)
        if self.go == "TO" and self.to in core.STEP_KEYS:
            j = core.STEP_KEYS.index(self.to)
        else:
            j = i + (1 if self.go == "NEXT" else -1)
        j = max(0, min(len(core.STEPS) - 1, j))
        v.step = core.STEP_KEYS[j]
        if v.step == "pc" and _S["probe"] is None and not probe_running():
            why = start_probe()                     # step 3 starts looking at once
            if why:
                self.report({"WARNING"}, why)
        remember("")
        ops_setup.redraw_all()
        return {"FINISHED"}


class FRESING_OT_first_setup_skip(bpy.types.Operator):
    """Closes the set-up for good: the app starts as it is (Essentials, the standard folders). Fresing > Set up
    again… runs it any time; every choice is also in Fresing Settings"""

    bl_idname = "fresing.first_setup_skip"
    bl_label = "Skip set-up"
    bl_options = set()

    def execute(self, context):
        remember("skipped")
        close_window()
        return {"FINISHED"}


class FRESING_OT_first_setup_pc(bpy.types.Operator):
    """Looks at your PC: a second Blender in the background imports the test crane and renders one picture on the
    graphics card, then the set-up says what it found and what to set. Nothing leaves your PC"""

    bl_idname = "fresing.first_setup_pc"
    bl_label = "Check my PC"
    bl_options = set()

    def execute(self, context):
        _S["probe"] = None
        why = start_probe()
        if why:
            self.report({"ERROR"}, why)
            return {"CANCELLED"}
        ops_setup.redraw_all()
        return {"FINISHED"}


class FRESING_OT_first_setup_hub(bpy.types.Operator):
    """Makes the Learning hub now, in the background: a card in the main window shows how far it is. Go on with
    the set-up meanwhile"""

    bl_idname = "fresing.first_setup_hub"
    bl_label = "Make the Learning hub now"
    bl_options = set()

    def execute(self, context):
        if hub_state()[0] != "none":
            return {"CANCELLED"}
        in_main(lambda c: bpy.ops.fresing.tour_make("EXEC_DEFAULT"))
        bpy.app.timers.register(lambda: (ops_setup.redraw_all(), None)[1], first_interval=1.0)
        return {"FINISHED"}


class FRESING_OT_first_setup_finish(bpy.types.Operator):
    """Ends the set-up and does this in the main window"""

    bl_idname = "fresing.first_setup_finish"
    bl_label = "Finish the set-up"
    bl_options = set()

    action: EnumProperty(items=[("CLOSE", "Close", "Close the set-up"),
                                ("IMPORT", "Import your first STEP…", "Close the set-up and pick a STEP file"),
                                ("HUB", "Open the Learning hub", "Close the set-up and open the Learning hub"),
                                ("DEMO", "Open the demo project", "Close the set-up and open the demo project")],
                         default="CLOSE", options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, props):
        return {"CLOSE": "Closes the set-up: you are ready to go",
                "IMPORT": "Closes the set-up and opens the file browser: pick a STEP file of your own",
                "HUB": "Closes the set-up and opens the Learning hub (made first when it is not there yet)",
                "DEMO": "Closes the set-up and opens the demo project (or its Make window when it is not made yet)",
                }.get(getattr(props, "action", ""), cls.__doc__)

    def execute(self, context):
        v = values(context)
        if v is not None:
            v.step = "done"
        remember("done")
        close_window()
        if self.action == "IMPORT":
            in_main(lambda c: bpy.ops.fresing.import_step("INVOKE_DEFAULT"))
        elif self.action == "HUB":
            in_main(lambda c: bpy.ops.fresing.tour_take("INVOKE_DEFAULT"))
        elif self.action == "DEMO":
            in_main(lambda c: bpy.ops.fresing.demo_open("INVOKE_DEFAULT") if demo_ready()
                    else bpy.ops.fresing.demo_make("INVOKE_DEFAULT"))
        return {"FINISHED"}


CLASSES = (FRFirstSetup, FRESING_PT_first_setup, FRESING_OT_first_setup, FRESING_OT_first_setup_step,
           FRESING_OT_first_setup_skip, FRESING_OT_first_setup_pc, FRESING_OT_first_setup_hub,
           FRESING_OT_first_setup_finish)


def _window_key(win) -> tuple:
    try:
        return (win.as_pointer(), win.screen.name)
    except (AttributeError, ReferenceError):
        return (0, "")


@persistent
def _on_load(_dummy=None):
    """A project opened: a set-up window it brought along (saved with it) closes – only that one (0328 row 1): the
    windows that are there at this load are the opened file's own, so a set-up window made after it (the first
    start's own, opened a moment after the start-up file was read) stays until Next / Skip / Close."""
    if bpy.app.background or not _S["at_load"]:
        return
    brought = {_window_key(w) for w in windows()}
    if not brought:
        return

    def later():
        from . import editors
        if editors.busy() or ops_setup.busy():
            return 0.1
        close_window(only=brought)
        return None

    bpy.app.timers.register(later, first_interval=0.6)


def register() -> None:
    bpy.types.WindowManager.fresing_first_setup = PointerProperty(type=FRFirstSetup)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister() -> None:
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    try:
        del bpy.types.WindowManager.fresing_first_setup
    except AttributeError:
        pass
