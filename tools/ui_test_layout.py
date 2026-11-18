"""Real-app test, the app's layout kept on open (task 0198): every project the app opens shows the Fresing tab with the
toolbar folded and keeps its own view; Live preview keeps the user's last choice through tour / demo projects and an own
project opens as saved; the header button and fresing.show_panel bring a hidden side panel back; 0193's clip survives.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_layout.py
Screenshots and ui_test_layout.log go to $UITEST_OUT (default ~/fresing_ui_test_layout).
"""

import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_layout"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_layout.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_layout é ")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def view():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return win, area, area.spaces.active


def ui_region(area):
    return next(r for r in area.regions if r.type == "UI")


def override():
    win, area, _sp = view()
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def layout_ok(tag):
    _w, area, sp = view()
    check(tag + ": side panel shown", sp.show_region_ui)
    check(tag + ": toolbar folded", not sp.show_region_toolbar)
    check(tag + ": Fresing tab", ui_region(area).active_panel_category == "Fresing",
          ui_region(area).active_panel_category)
    # task 0062: every project opens calm – sections 1 to 7 folded, Blender's own workspace tabs hidden
    panels, lock = mod("blender.panels"), mod("blender.lock")
    check(tag + ": sections 1-7 folded, Blender's tabs hidden",
          not any(panels.is_open(s) for s in panels.SECTIONS) and lock.tabs_hidden(), str(sorted(panels.OPEN)))
    panels.open_all()                     # so the next project that opens has something to fold


def save_as(name, mark=None):
    path = os.path.join(TMP, name)
    if mark:
        bpy.context.scene[mark] = "0.0.0"
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


def messy_view(distance=7.77, clip_end=20000.0):
    """The view of a project saved the way a background Blender (or a user) leaves it: panel hidden, toolbar shown."""
    _w, area, sp = view()
    sp.show_region_ui = False
    sp.show_region_toolbar = True
    sp.shading.type = "MATERIAL"
    sp.clip_end = clip_end
    sp.region_3d.view_distance = distance


STEPS = []
STATE = {}


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    check("the extension is on", pkg() is not None)
    layout_ok("new project")
    shot("00_start")
    return 0.5


@step
def s_own_project():
    messy_view()
    STATE["own"] = save_as("own project.blend")
    return 0.3


@step
def s_open_own():
    bpy.ops.wm.open_mainfile(filepath=STATE["own"])
    return 1.5


@step
def s_check_own():
    layout_ok("own project")
    _w, _a, sp = view()
    check("own project keeps its view distance", abs(sp.region_3d.view_distance - 7.77) < 0.01,
          sp.region_3d.view_distance)
    check("own project keeps its shading", sp.shading.type == "MATERIAL", sp.shading.type)
    check("a far clip of 20 km survives the load (task 0193)", sp.clip_end >= 19999.0, sp.clip_end)
    return 0.3


@step
def s_older_project():
    """A project saved by an older version: no Fresing preference or panel state in the file."""
    messy_view()
    bpy.context.scene["fr_saved_by"] = "0.2.140"
    STATE["old"] = save_as("old 0.2.140.blend")
    bpy.ops.wm.open_mainfile(filepath=STATE["old"])
    return 1.5


@step
def s_check_old():
    layout_ok("project of 0.2.140")
    return 0.3


@step
def s_prefs():
    from importlib import import_module
    prefs = import_module(pkg() + ".blender.prefs")
    p = prefs.get()
    check("the Live preview choice is a stored preference", p is not None and "live_preview" in p.bl_rna.properties
          and not p.bl_rna.properties["live_preview"].is_skip_save)
    p.live_preview = False
    mod("blender.tour")
    from importlib import import_module as im
    tour = im(pkg() + ".blender.tour")
    messy_view()
    STATE["tour"] = save_as("tour set.blend", mark=tour.TAG)
    return 0.3


def preview_on():
    return view()[2].shading.type == "RENDERED"


@step
def s_preview_button_on():
    messy_view()
    view()[2].shading.type = "SOLID"
    with override():
        bpy.ops.fresing.preview("EXEC_DEFAULT", True)
    check("the Live preview button turns it on", preview_on())
    from importlib import import_module
    p = import_module(pkg() + ".blender.prefs").get()
    check("... and remembers it", p.live_preview)
    return 0.3


@step
def s_open_tour_on():
    bpy.ops.wm.open_mainfile(filepath=STATE["tour"])
    return 2.0


@step
def s_check_tour_on():
    layout_ok("tour set")
    check("a tour set opens with Live preview on (last choice)", preview_on(), view()[2].shading.type)
    with override():
        bpy.ops.fresing.preview("EXEC_DEFAULT", True)
    check("button turns it off", not preview_on())
    return 0.3


@step
def s_open_tour_off():
    bpy.ops.wm.open_mainfile(filepath=STATE["tour"])
    return 2.0


@step
def s_check_tour_off():
    check("a tour set opens with Live preview off after turning it off", not preview_on(), view()[2].shading.type)
    # the same for the demo project
    from importlib import import_module
    demo = import_module(pkg() + ".blender.demo")
    p = import_module(pkg() + ".blender.prefs").get()
    p.live_preview = True
    STATE["demo"] = save_as("demo.blend", mark=demo.TAG)
    return 0.3


@step
def s_open_demo():
    bpy.ops.wm.open_mainfile(filepath=STATE["demo"])
    return 2.0


@step
def s_check_demo():
    layout_ok("demo project")
    check("the demo opens with Live preview on (last choice)", preview_on())
    # an own project opens as saved: saved SOLID, preference on
    from importlib import import_module
    sc = bpy.context.scene
    for tag in (import_module(pkg() + ".blender.demo").TAG, import_module(pkg() + ".blender.tour").TAG):
        if tag in sc:
            del sc[tag]
    messy_view()
    view()[2].shading.type = "SOLID"
    STATE["own2"] = save_as("own 2.blend")
    bpy.ops.wm.open_mainfile(filepath=STATE["own2"])
    return 1.5


@step
def s_check_own2():
    check("an own project opens as saved (Live preview not forced)", not preview_on(), view()[2].shading.type)
    return 0.3


@step
def s_hide_panel():
    _w, area, sp = view()
    sp.show_region_ui = False
    from importlib import import_module
    h = import_module(pkg() + ".blender.ui_header")
    check("hidden side panel: the header button shows", not h.panel_visible(area))
    area.tag_redraw()
    return 1.0


@step
def s_shot_hidden():
    shot("10_panel_hidden")
    return 0.3


@step
def s_show_panel():
    with override():
        bpy.ops.fresing.show_panel("EXEC_DEFAULT")
    _w, area, sp = view()
    check("Show the Fresing panel brings the panel back", sp.show_region_ui)
    check("... on the Fresing tab", ui_region(area).active_panel_category == "Fresing")
    from importlib import import_module
    check("the header button is gone again", import_module(pkg() + ".blender.ui_header").panel_visible(area))
    return 0.5


@step
def s_other_tab():
    _w, area, sp = view()
    ui_region(area).active_panel_category = "View"
    from importlib import import_module
    h = import_module(pkg() + ".blender.ui_header")
    check("another tab open: the header button shows", not h.panel_visible(area))
    with override():
        bpy.ops.fresing.show_panel("EXEC_DEFAULT")
    check("... and brings the Fresing tab back", h.panel_visible(area))
    shot("11_back")
    return 0.3


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
