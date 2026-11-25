"""Real-app test, the app's layout kept on open (task 0198): every project the app opens shows the Fresing tab with the
toolbar folded and keeps its own view; Live preview keeps the user's last choice through tour / demo projects and an own
project opens as saved; the header button and fresing.show_panel bring a hidden side panel back; 0193's clip survives.
Task 0221: every project opens without Blender's Outliner / Properties column (also one saved with it), Fresing > Show /
Hide Blender's editors works both ways and is kept in the settings file, the Client view hides the column and greys the
entry, Region Overlap is off (the side panel solid) and a user's own "on" is kept.

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
    left = mod("blender.ui_left")                    # task 0260: the toolbar region holds the left panel
    check(tag + ": left panel shown, readable", sp.show_region_toolbar and left.width(area) >= 180,
          f"{left.width(area):.0f} px")
    check(tag + ": Fresing tab", ui_region(area).active_panel_category == "Fresing",
          ui_region(area).active_panel_category)
    # task 0062: every project opens calm – sections 1 to 8 folded, Blender's own workspace tabs hidden
    panels, lock = mod("blender.panels"), mod("blender.lock")
    check(tag + ": sections 1-8 folded, Blender's tabs hidden",
          not any(panels.is_open(s) for s in panels.SECTIONS) and lock.tabs_hidden(), str(sorted(panels.OPEN)))
    panels.open_all()                     # so the next project that opens has something to fold
    column_ok(tag, False)


def column_types(win=None):
    win = win or bpy.context.window_manager.windows[0]
    return sorted(a.type for a in win.screen.areas if a.type in ("OUTLINER", "PROPERTIES"))


def column_ok(tag, shown):
    """Task 0221: Blender's right-hand column hidden (the 3D view reaches the right edge) or shown."""
    win, area, _sp = view()
    if shown:
        check(tag + ": Outliner and Properties shown", column_types(win) == ["OUTLINER", "PROPERTIES"],
              str(column_types(win)))
        check(tag + ": ... right of the 3D view", area.x + area.width < win.width - 200, f"{area.x + area.width}")
    else:
        check(tag + ": no Outliner or Properties column", not column_types(win), str(column_types(win)))
        check(tag + ": the 3D view reaches the right edge", area.x + area.width >= win.width - 6,
              f"{area.x + area.width} of {win.width}")


def save_as(name, mark=None):
    path = os.path.join(TMP, name)
    if mark:
        bpy.context.scene[mark] = "0.0.0"
    bpy.ops.wm.save_as_mainfile(filepath=path)
    return path


def messy_view(distance=7.77, clip_end=20000.0):
    """The view of a project saved the way a background Blender (or a user) leaves it: panel hidden, toolbar hidden
    (task 0260: the toolbar region is the left panel – it must come back)."""
    _w, area, sp = view()
    sp.show_region_ui = False
    sp.show_region_toolbar = False
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
    ed = mod("blender.editors")
    win = bpy.context.window_manager.windows[0]
    check("a project can be saved with Blender's column (shown for the save)", ed.show(win), str(column_types(win)))
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
def s_other_tab_select():
    """Task 0332: outside Full access Blender's tabs Tool / View / Animation are hidden; only Item (Blender's own C
    panel) still shows, while an object is active – make one active so that tab is there."""
    sc = bpy.context.scene
    ob = sc.objects.get("FR layout test empty")
    if ob is None:
        ob = bpy.data.objects.new("FR layout test empty", None)
        sc.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    _w, area, _sp = view()
    area.tag_redraw()
    return 0.5


@step
def s_other_tab():
    _w, area, sp = view()
    ui_region(area).active_panel_category = "Item"
    from importlib import import_module
    h = import_module(pkg() + ".blender.ui_header")
    check("another tab open: the header button shows", not h.panel_visible(area))
    with override():
        bpy.ops.fresing.show_panel("EXEC_DEFAULT")
    check("... and brings the Fresing tab back", h.panel_visible(area))
    shot("11_back")
    ob = bpy.context.scene.objects.get("FR layout test empty")
    if ob is not None:
        bpy.data.objects.remove(ob)
    return 0.3


@step
def s_overlap():
    ed = mod("blender.editors")
    prefs = bpy.context.preferences.system
    check("Region Overlap is off: the side panel is solid", prefs.use_region_overlap is False)
    check("... and the settings file remembers that the app did it", ed.load()["overlap_off"])
    prefs.use_region_overlap = True                 # the user turns it on again in Edit > Preferences
    ed.on_load()
    check("a user's own Region Overlap on is kept at the next load", prefs.use_region_overlap is True)
    prefs.use_region_overlap = False                # put back for the next test in this settings folder
    return 0.3


@step
def s_editors_show():
    ed = mod("blender.editors")
    check("the Fresing menu has Show Blender's editors", "fresing.blender_editors" in mod("blender.ui_topbar").entries()
          and ed.menu_text() == "Show Blender's editors", ed.menu_text())
    with override():
        bpy.ops.fresing.blender_editors("EXEC_DEFAULT", True)
    check("the choice 'shown' is in the settings file", ed.read(ed.state_path())["editors"] == "shown")
    check("... and the entry now says Hide", ed.menu_text() == "Hide Blender's editors", ed.menu_text())
    return 1.0


@step
def s_editors_shown():
    column_ok("Show Blender's editors", True)
    win = bpy.context.window_manager.windows[0]
    out = next(a for a in win.screen.areas if a.type == "OUTLINER")
    props = next(a for a in win.screen.areas if a.type == "PROPERTIES")
    check("... Outliner on top, Properties below", out.y > props.y, f"{out.y} {props.y}")
    shot("20_editors_shown")
    with override():
        bpy.ops.fresing.blender_editors("EXEC_DEFAULT", True)
    return 1.0


@step
def s_editors_hidden():
    column_ok("Hide Blender's editors", False)
    with override():                                # repeatedly, faster than the window redraws: 5 clicks = shown
        for _ in range(5):
            bpy.ops.fresing.blender_editors("EXEC_DEFAULT", True)
    return 1.5


@step
def s_editors_again():
    column_ok("Show / Hide five times more", True)
    return 0.3


@step
def s_client_view():
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 1.0


@step
def s_client_hidden():
    column_ok("Client view", False)
    check("Client view: the entry is greyed", not bpy.ops.fresing.blender_editors.poll())
    check("... and its tooltip says why", "Client view" in mod("blender.editors").FRESING_OT_blender_editors
          .description(bpy.context, None))
    check("... the user's choice is still 'shown'", mod("blender.editors").chosen_shown())
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Full access")
    return 1.0


@step
def s_client_off():
    column_ok("Full access again: the user's choice back", True)
    with override():
        bpy.ops.fresing.blender_editors("EXEC_DEFAULT", True)      # back to hidden for the next test
    shot("21_editors_hidden")
    return 0.5


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
