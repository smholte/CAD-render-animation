"""Real-app test, test tour (task 0059): Make test tour project (built in this Blender), Open test tour project, the
Test tour panel on top of the Fresing tab, Go on a stop of the open project (animation built, playing, looking through
the camera), Go on a stop of another project (it opens, and the stop is set up after loading), OK / Problem, a note,
Copy results (clipboard and the text file).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_tour.py
Screenshots and ui_test_tour.log go to $UITEST_OUT (default ~/fresing_ui_test_tour).
"""

import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_tour"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_tour.log"), "w")
RESULTS = []
STATE = {}


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


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def op(_idname, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", True, **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def sidebar_shot(name, height=1500):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def key(k, ctrl=False, shift=False):
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl, shift=shift)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)




def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def tour():
    return mod("blender.tour")


@step
def s_start():
    win, area, region, sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 1.0


@step
def s_make():
    log("extension", pkg())
    check("Help menu has Make test tour project", hasattr(bpy.ops.fresing, "tour_make"))
    folder = os.path.join(OUT, "Test tour é")
    STATE["folder"] = folder
    STATE["version"] = _version()
    t0 = time.time()
    r = op("fresing.tour_make", folder=folder, in_place=True)
    hub = tour().hub_path(folder, STATE["version"])
    check("Make test tour project builds every project", r == {"FINISHED"} and os.path.isfile(hub),
          f"{time.time() - t0:.0f} s")
    log("built in", round(time.time() - t0), "s")
    STATE["hub"] = hub
    return 0.5


def _version():
    import importlib
    return importlib.import_module(pkg()).__version__


@step
def s_open():
    r = op("fresing.tour_open", filepath=STATE["hub"])
    check("Open test tour project", r == {"FINISHED"})
    return 2.0


@step
def s_panel():
    sc = bpy.context.scene
    check("the hub is a tour project", tour().is_tour(sc) and sc[tour().TAG] == tour().HUB_SET)
    check("the Test tour panel shows", bpy.types.FRESING_PT_tour.poll(bpy.context))
    win, area, region, sb = ui()
    area.spaces.active.show_region_ui = True
    try:
        sb.active_panel_category = "Fresing"
    except (AttributeError, TypeError):
        pass
    redraw()
    return 1.0


@step
def s_panel_shot():
    sidebar_shot("01_tour_panel")
    return 0.3


@step
def s_go_here():
    r = op("fresing.tour_go", stop="joint")
    sc = bpy.context.scene
    win, area, region, sb = ui()
    check("Go (same project): the animation is built", r == {"FINISHED"} and sc.fresing.anim_baked == "Boom up")
    check("Go: the view looks through the camera", area.spaces.active.region_3d.view_perspective == "CAMERA")
    check("Go: the animation plays", win.screen.is_animation_playing)
    return 1.5


@step
def s_go_other():
    with override():
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
    r = op("fresing.tour_go", stop="cylinder")
    check("Go (other project): Go returns", r == {"FINISHED"})
    return 3.0


@step
def s_go_other_done():
    sc = bpy.context.scene
    if sc.get(tour().TAG) != "cylinder" or sc.fresing.anim_baked != "Stroke out":
        return "wait"
    win, area, region, sb = ui()
    check("Go (other project): the cylinder project is open and its animation built",
          sc[tour().TAG] == "cylinder" and sc.fresing.anim_baked == "Stroke out")
    check("Go (other project): looking through the camera",
          area.spaces.active.region_3d.view_perspective == "CAMERA")
    st = tour().find("cylinder")
    check("Go (other project): the stop's number check passes", bool(st.check(sc)))
    with override():
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
    return 1.0


@step
def s_marks():
    r1 = op("fresing.tour_mark", stop="cylinder", state="OK")
    r2 = op("fresing.tour_mark", stop="looks", state="PROBLEM")
    r3 = op("fresing.tour_note", stop="looks", note="test note é")
    data = tour().load_results(STATE["folder"], STATE["version"])
    check("OK / Problem / Note are saved next to the tour",
          (r1, r2, r3) == ({"FINISHED"},) * 3 and data["stops"]["cylinder"]["state"] == "OK"
          and data["stops"]["looks"] == {"state": "PROBLEM", "note": "test note é"}, f"{(r1, r2, r3)} {data['stops'].get('cylinder')} {data['stops'].get('looks')}")
    redraw()
    return 0.5


@step
def s_copy():
    r = op("fresing.tour_copy")
    text = bpy.context.window_manager.clipboard
    path = tour().results_txt_path(STATE["folder"], STATE["version"])
    sea = tour().find("looks")
    check("Copy results: the clipboard has every stop", r == {"FINISHED"} and text.count("\n") >= len(tour().STOPS)
          and f"[PROBLEM] {sea.title} (looks) - test note é" in text, text[:200])
    check("Copy results: the text file next to the tour", os.path.isfile(path))
    sidebar_shot("02_tour_panel_marked")
    return 0.5


@step
def s_next():
    """Task 0275: Next = pick + Go in one click (the panel's Next button is ``fresing.tour_go``)."""
    here = tour().find("cylinder")
    nxt = next((s for s in tour().STOPS if s.number == here.number + 1), None)
    check("the stop after the cylinder's exists", nxt is not None)
    import inspect
    src = inspect.getsource(mod("blender.ui_tour"))
    check("the panel's Next button is Go on the next stop",
          'operator("fresing.tour_go", text=f"Next:' in src and 'operator("fresing.tour_pick", text=f"Next:' not in src)
    STATE["next"] = nxt
    with override():
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
    op("fresing.tour_go", stop=nxt.id)
    return 3.0


@step
def s_next_done():
    nxt = STATE["next"]
    sc = bpy.context.scene
    if sc.get(tour().TAG) != nxt.set or not nxt.check(sc):
        return "wait"
    data = tour().load_results(STATE["folder"], STATE["version"])
    check("Next set the next stop up in one click (its project open, its check passes)",
          sc[tour().TAG] == nxt.set and data["current"] == nxt.id)
    with override():
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel(restore_frame=False)
    return 0.5


def hp():
    return mod("blender.hub_progress")


def click(key):
    """A click on the card's button, at its place in the window (the build's modal takes it)."""
    win, area, region, sb = ui()
    pt = hp().button_point(key, mod("blender.ops_tour").building())
    if pt is None:
        return False
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=pt[0], y=pt[1])
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=pt[0], y=pt[1])
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=pt[0], y=pt[1])
    return True


def card_shot(name):
    """The card alone, cropped from a picture of the screen (for the guide)."""
    win, area, region, sb = ui()
    g = hp()._geometry(mod("blender.ops_tour").building())
    if g is None:
        return
    sc = bpy.context.preferences.system.ui_scale or 1.0
    x, y, w, h = int(g["x"]) - 4, int(win.height - g["y"] - g["h"]) - 4, int(g["w"]) + 8, int(g["h"]) + 8
    full = os.path.join(OUT, name + "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    subprocess.run(["convert", full, "-crop", f"{w}x{h}+{max(x, 0)}+{max(y, 0)}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)
    try:
        os.remove(full)
    except OSError:
        pass


@step
def s_card_start():
    """Task 0275: Make the Learning hub (one project, a real background build): the card is there at once."""
    STATE["cfolder"] = os.path.join(OUT, "Card tour")
    t0 = time.time()
    op("fresing.tour_make", folder=STATE["cfolder"], only="looks,cylinder,mill,linkage,waycover")   # long enough to stop
    ops = mod("blender.ops_tour")
    check("the card is there at once, mode progress", hp().STATE["mode"] == "progress" and hp().visible()
          and time.time() - t0 < 1.0, f"{time.time() - t0:.2f} s")
    data = ops.building()
    text = hp().line(data)
    check("the card's line says project N of M and the time left",
          text.startswith("Making the Learning hub: project 1 of 5 ") and "left" in text, text)
    check("the card has Hide and Stop making it", hp().button_point("hide", data) and hp().button_point("stop", data))
    return 2.0


@step
def s_card_hide():
    card_shot("hub_card_progress")
    if not click("hide"):
        check("Hide button found", False)
        return 0.5
    return 1.5


@step
def s_card_hidden():
    check("Hide: the card is hidden, the build goes on", hp().STATE["hidden"] and hp().active()
          and mod("blender.ops_tour").building().get("running") is not False)
    check("Show progress is possible while hidden", bpy.ops.fresing.hub_show.poll())
    op("fresing.hub_show")
    check("Show progress brings the card back", hp().visible())
    return 0.5


@step
def s_card_stop():
    click("stop")
    return 1.0


@step
def s_card_stop_ask():
    check("Stop making it asks once", hp().STATE["mode"] == "confirm")
    click("stop_no")
    return 1.0


@step
def s_card_stop_no():
    check("Keep making it goes back to the progress", hp().STATE["mode"] == "progress")
    click("stop")
    return 1.0


@step
def s_card_stop_yes():
    click("stop_yes")
    return 3.0


@step
def s_card_stopped():
    if hp().active() or mod("blender.ops_tour").building().get("running"):
        return "wait"
    check("Yes, stop: the build is stopped and the card goes", not hp().active() and not mod("blender.ops_tour").building())
    op("fresing.tour_make", folder=STATE["cfolder"], only="looks")      # again, to the end
    # a forced failure: the build's program is killed from outside at once (a slow machine must not finish first)
    mod("blender.ops_tour")._BUILD["proc"].kill()
    return 3.0


@step
def s_card_failed():
    if hp().STATE["mode"] != "failed":
        log("waiting for the failed card, mode:", hp().STATE["mode"], hp().STATE["gen"])
        return "wait"
    check("A failed build shows what failed and its log, with Try again",
          "log" in hp().STATE["log"].lower() and hp().STATE["why"] and hp().button_point("again", {}) is not None,
          hp().STATE["why"])
    card_shot("hub_card_failed")
    click("again")
    return 1.5


@step
def s_card_again():
    check("Try again starts the build and the card again", hp().STATE["mode"] == "progress")
    return 1.0


@step
def s_card_ready():
    if hp().STATE["mode"] != "ready":
        return "wait"
    hub = hp().STATE["hub"]
    check("Done: the card says the hub is ready", os.path.isfile(hub), hub)
    card_shot("hub_card_ready")
    click("open")
    return 3.0


@step
def s_card_opened():
    check("Open it now opens the hub and the card is gone",
          bpy.data.filepath.startswith(STATE["cfolder"]) and not hp().active(), bpy.data.filepath)
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_w = [0.0]


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
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 120:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        wiggle()
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
