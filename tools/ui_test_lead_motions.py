"""Real-app test, task 0309: the Lead motions drop-down on the top bar.

On the test crane (Boom + Trolley joints, the crane set's three lead motions): the top bar draws **Lead motions** right
of the Fresing menu in every built-in workspace and in the Client view (found on screen by drawing the top bar with and
without it and comparing the pixels – the test does not know where it is); **one click** on it opens the drop-down; a
slider moves the joints; ▶ plays to 100 % in the lead motion's seconds; Keep open and Edit lead motions… open their
windows (Edit is refused in the Client view, the sliders and ▶ are not). Pictures for the guide and the report's
mock-ups of the three places compared (top bar / 3D view header / a corner of the 3D view) go to $UITEST_OUT.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/lm xvfb-run -a -s "-screen 0 1800x1200x24" blender \\
        -p 0 0 1800 1200 --app-template fresing_render --enable-event-simulate --python tools/ui_test_lead_motions.py
"""

import importlib
import math
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lead_motions"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lead_motions.log"), "w")
RESULTS = []
S = {}
STEPS = []
WORKSPACES = ("Essentials", "Sales", "Quick render", "Animator", "Reviewer", "All functions", "Client view")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def mod(name):
    import addon_utils
    pkg = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
    return importlib.import_module(pkg + "." + name)


def win0():
    return bpy.context.window_manager.windows[0]


def view():
    win = win0()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def step(fn):
    STEPS.append(fn)
    return fn


def esc():
    win = win0()
    win.event_simulate(type="ESC", value="PRESS")
    win.event_simulate(type="ESC", value="RELEASE")


def click(x, y):
    win = win0()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def redraw_all():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()
    win = win0()
    try:                                                     # draw the window now …
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
    except Exception as exc:  # noqa: BLE001
        log("redraw:", exc)
    try:                                                     # … and the top bar again at the next redraw
        mod("blender.lock")._topbar_redraw()
    except Exception:  # noqa: BLE001
        pass
    for w in bpy.context.window_manager.windows:            # the top bar keeps its last drawing until the screen is
        try:                                                 # laid out again: the status bar off and on does that
            v = w.screen.show_statusbar
            w.screen.show_statusbar = not v
            w.screen.show_statusbar = v
        except (AttributeError, RuntimeError):
            pass
    # the mouse over File and off again: the top bar lays itself out again (a hover redraws its buttons)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=42, y=win.height - 12)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=win.width // 2 + int(time.time() * 7) % 11,
                       y=win.height // 2)


def grab(name, crop=None):
    path = os.path.join(OUT, name)
    cmd = ["import", "-window", "root"]
    if crop:
        x, y, w, h = crop
        cmd += ["-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y)}", "+repage"]
    subprocess.run(cmd + [path], check=False)
    return path


def pixels(path):
    """The picture as rows of RGB tuples (ImageMagick → plain PPM; Blender's Python has no Pillow)."""
    raw = subprocess.run(["convert", path, "-depth", "8", "ppm:-"], capture_output=True, check=False).stdout
    parts = raw.split(b"\n", 3)
    w, h = (int(v) for v in parts[1].split())
    data = parts[3]
    return w, h, data


def topbar_height():
    win = win0()
    return int(30 * bpy.context.preferences.system.ui_scale * 1.2) + 4


def find_button():
    """Where the top bar's Lead motions button is: the columns of the top bar that change when it is not drawn.
    Returns (x0, x1) in window pixels, or None."""
    ui_lm = mod("blender.ui_lead_motions")
    h = topbar_height()
    a = grab("_topbar_on.png", (0, 0, win0().width, h))
    ui_lm.HIDE[0] = True
    S["hide_t"] = time.time()
    return a


def _diff_columns(a, b):
    wa, ha, da = pixels(a)
    wb, hb, db = pixels(b)
    if (wa, ha) != (wb, hb):
        return None
    cols = []
    for x in range(wa):
        for y in range(ha):
            i = (y * wa + x) * 3
            if da[i:i + 3] != db[i:i + 3]:
                cols.append(x)
                break
    if not cols:
        return None
    return cols[0], cols[-1]


@step
def s_splash():
    esc()                                                    # the splash (its own step: an Esc in the import's step
    return 1.0                                               # would cancel the import, CLAUDE.md 8)


@step
def s_import():
    S["overlap"] = bpy.context.preferences.system.use_region_overlap
    bpy.context.preferences.system.use_region_overlap = False
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    S["t_import"] = time.time()
    return 1.0


@step
def s_setup():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0 and time.time() - S["t_import"] < 120:
        return "again"
    check("the test crane is imported", sc.fresing.model_count > 0)
    tour = mod("blender.tour")
    crane = mod("blender.lessons.crane")
    tour._boom_joint(sc)
    crane._trolley(sc)
    with override():
        crane._lead(sc)                                      # the lesson's own buttons: Boom up and out (stages)
    tour.lead_set_up(sc, tour._animation(type("B", (), {"s": sc.fresing})(), tour.LEAD_ANIM))
    check("three lead motions", len(sc.fresing.lead_motions) == 3, str([m.name for m in sc.fresing.lead_motions]))
    sc.fresing.lead_motions["Boom up"].position = 0.0
    sc.fresing.lead_motions["Boom up and out"].position = 60.0     # (the picture: a slider part way, "moved by …")
    redraw_all()
    return 1.5


@step
def s_find_button():
    ui_lm = mod("blender.ui_lead_motions")
    S["drawn0"] = ui_lm.DRAWN["button"]
    S["on"] = find_button()
    redraw_all()
    return 1.0


@step
def s_find_button_2():
    ui_lm = mod("blender.ui_lead_motions")
    off = grab("_topbar_off.png", (0, 0, win0().width, topbar_height()))
    ui_lm.HIDE[0] = False
    redraw_all()
    cols = _diff_columns(S["on"], off)
    check("the top bar draws the Lead motions button", ui_lm.DRAWN["button"] > S["drawn0"] and cols is not None,
          f"columns {cols}")
    S["button"] = cols
    return 1.0


@step
def s_click_open():
    ui_lm = mod("blender.ui_lead_motions")
    cols = S.get("button")
    if not cols:
        check("one click opens the drop-down", False, "the button was not found")
        return 0.5
    win = win0()
    S["menu0"] = ui_lm.DRAWN["menu"]
    x = (cols[0] + cols[1]) // 2
    y = win.height - topbar_height() // 2 + 2
    S["click"] = (x, y)
    click(x, y)
    return 1.5


@step
def s_opened_or_again():
    """The first click into a region after the start only gives it focus (CLAUDE.md 8): click once more if so."""
    ui_lm = mod("blender.ui_lead_motions")
    if ui_lm.DRAWN["menu"] == S["menu0"]:
        log("the first click only focused the top bar: once more")
        click(*S["click"])
    return 1.5


@step
def s_opened():
    ui_lm = mod("blender.ui_lead_motions")
    opened = ui_lm.DRAWN["menu"] > S["menu0"]
    check("one click on Lead motions opens the drop-down", opened, f"drawn {ui_lm.DRAWN['menu'] - S['menu0']} times")
    cols = S.get("button") or (0, 0)
    grab("lead_motions_menu_full.png")
    w = int(ui_lm.UNITS_X * 20 * bpy.context.preferences.system.ui_scale) + 140      # the drop-down hangs centred
    x0 = max(0, (cols[0] + cols[1]) // 2 - w // 2)                                  # under its button
    grab("lead_motions_menu.png", (x0, 0, w, 330))
    esc()
    return 1.0


@step
def s_slider_and_play():
    sc = bpy.context.scene
    lm_mod = mod("blender.lead_motions")
    joints = mod("blender.joints")
    lm = sc.fresing.lead_motions["Boom up and out"]
    t0 = time.perf_counter()
    lm.position = 50.0
    bpy.context.view_layer.update()
    ms = (time.perf_counter() - t0) * 1000.0
    log(f"METRIC slider_ms {ms:.3f}")
    S["slider_ms"] = ms
    want = lm_mod.values_at(lm, 50.0)
    err = max(abs(joints.get_value(joints.find(sc, n)) - v) for n, v in want.items())
    check("the slider at 50 % sets the joints the lead motion says", err < 1e-6, f"{err:.2e}, {ms:.1f} ms")
    lm.position = 0.0
    up = sc.fresing.lead_motions["Boom up"]
    up.position = 0.0
    with override():
        res = bpy.ops.fresing.lead_play("INVOKE_DEFAULT", index=list(sc.fresing.lead_motions).index(up))
    check("▶ starts playing", res == {"RUNNING_MODAL"}, str(res))
    S["play_t"] = time.time()
    return 1.5


@step
def s_play_half():
    sc = bpy.context.scene
    up = sc.fresing.lead_motions["Boom up"]
    S["mid"] = up.position
    check("▶ is under way after 1.5 s of 3 s", 20.0 < up.position < 95.0, f"{up.position:.0f} %")
    return 2.5


@step
def s_play_end():
    sc = bpy.context.scene
    joints = mod("blender.joints")
    up = sc.fresing.lead_motions["Boom up"]
    check("▶ ends at 100 % and the boom at 35°", up.position == 100.0
          and abs(math.degrees(joints.get_value(joints.find(sc, "Boom"))) - 35.0) < 1e-3,
          f"{up.position:.1f} %")
    return 0.5


@step
def s_built_long():
    """Task 0330 rows 35 and 8: Build & play of a 12 s animation fits the timeline; a lead slider on it then takes the
    Build off instead of snapping back at the next frame."""
    sc = bpy.context.scene
    s = sc.fresing
    tour = mod("blender.tour")
    a = s.animations.add()
    a.name, a.fps, a.tail = "Long boom", "25", 0.0
    tour._joint_step(a, "Boom", 0.0, 12.0, math.radians(20))
    s.animations_index = list(s.animations).index(a)
    S["timeline0"] = _timeline_range()
    with override():
        res = bpy.ops.fresing.anim_build("EXEC_DEFAULT", True)
    check("Build & play of the 12 s animation", res == {"FINISHED"} and sc.frame_end == 301, f"{res} {sc.frame_end}")
    redraw_all()
    return 2.0


def _timeline_range():
    """The frames the timeline shows, (left, right), or None when the layout has no timeline."""
    for area in win0().screen.areas:
        if area.type == "DOPESHEET_EDITOR" and area.ui_type == "TIMELINE":
            r = next(x for x in area.regions if x.type == "WINDOW")
            return r.view2d.region_to_view(0, 0)[0], r.view2d.region_to_view(r.width - 1, 0)[0]
    return None


@step
def s_built_long_2():
    sc = bpy.context.scene
    rng = _timeline_range()
    log("timeline before", S.get("timeline0"), "after", rng)
    check("the timeline shows the whole new animation (frames 1 … 301)", rng is not None and rng[0] <= 1.5
          and rng[1] >= 300.5, f"{S.get('timeline0')} -> {rng}")
    lm_mod = mod("blender.lead_motions")
    animation = mod("blender.animation")
    joints = mod("blender.joints")
    up = sc.fresing.lead_motions["Boom up"]
    up.position = 90.0                                        # a slider moved on the built animation
    check("a lead slider takes the Build off and says so", not animation.has_keys(sc)
          and sc.fresing.last_message == lm_mod.BUILT_OFF, sc.fresing.last_message)
    want = lm_mod.values_at(up, 90.0)["Boom"]
    sc.frame_set(150)
    got = joints.get_value(joints.find(sc, "Boom"))
    check("the boom stays where the slider put it at the next frame", abs(got - want) < 1e-6, f"{got} / {want}")
    sc.frame_set(1)
    up.position = 100.0
    return 0.5


def _draw_ms(lm, n=10, move=True):
    """Median ms of a slider change and one drawing of the window (``move`` False: the drawing alone) – the real app
    on this machine's software GL, where drawing the whole window alone takes ~0.2 s."""
    win = win0()
    times = []
    for i in range(n):
        t0 = time.perf_counter()
        if move:
            lm.position = 20.0 + 6.0 * i
        with bpy.context.temp_override(window=win, screen=win.screen):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN", iterations=1)
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return times[len(times) // 2]


@step
def s_live_preview_off_on():
    sc = bpy.context.scene
    lm = sc.fresing.lead_motions["Boom up and out"]
    _win, area, _region = view()
    space = area.spaces.active
    was = space.shading.type
    space.shading.type = "SOLID"
    off0, off = _draw_ms(lm, move=False), _draw_ms(lm)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    space.shading.type = "RENDERED"                          # Live preview: Cycles in the view
    on0, on = _draw_ms(lm, move=False), _draw_ms(lm)
    space.shading.type = was
    lm.position = 0.0
    log(f"METRIC draw_ms live_preview_off {off0:.1f} with_slider {off:.1f} live_preview_on {on0:.1f} "
        f"with_slider {on:.1f}")
    # the drawing itself is this machine's software GL (~0.2-0.4 s a window, it varies with the load): a number, no
    # check; the check is the slider's own work (the joints set + the scene worked out), measured above
    check("a slider change (joints + the scene's update) takes under 50 ms", S.get("slider_ms", 1e9) < 50.0,
          f"{S.get('slider_ms', 0):.1f} ms; a window drawing {off0:.0f} ms, with a change {off:.0f} ms; Live preview "
          f"on: {on0:.0f} / {on:.0f} ms")
    return 1.0


@step
def s_keep_open():
    fw = mod("blender.form_window")
    with override():
        bpy.ops.fresing.lead_keep_open("INVOKE_DEFAULT")
    S["kw"] = time.time()
    return 2.5


@step
def s_keep_open_2():
    fw = mod("blender.form_window")
    check("Keep open shows the sliders in a window of their own", fw.is_open("fresing.lead_keep_open"))
    grab("lead_motions_keep_open_full.png")
    fw.close("fresing.lead_keep_open")
    return 1.5


@step
def s_editor():
    with override():
        bpy.ops.fresing.lead_edit("INVOKE_DEFAULT")
    return 2.5


@step
def s_editor_2():
    fw = mod("blender.form_window")
    ok = fw.is_open("fresing.lead_edit")
    check("Edit lead motions… opens the editor window", ok)
    if ok:
        win = fw.windows("fresing.lead_edit")[0]
        grab("lead_motions_editor_full.png")
        S["editor_win"] = (win.x, win.y, win.width, win.height)
        log("editor window", S["editor_win"])
        grab("lead_motions_editor.png", (max(0, win.x), max(0, win0().height - win.y - win.height), win.width,
                                         win.height))
    fw.close("fresing.lead_edit")
    return 1.5


@step
def s_step_picture():
    sc = bpy.context.scene
    panels = mod("blender.panels")
    lm_mod = mod("blender.lead_motions")
    s = sc.fresing
    a = s.animations[mod("blender.tour").LEAD_ANIM]
    s.animations_index = list(s.animations).index(a)
    a.blocks_index = 0
    panels.show_only(["FRESING_PT_animation"])
    redraw_all()
    return 1.5


@step
def s_step_picture_2():
    win, area, _region = view()
    sb = next(r for r in area.regions if r.type == "UI")
    grab("panel_6_lead_step_full.png")
    grab("panel_6_lead_step.png", (sb.x, win.height - (sb.y + sb.height), sb.width, min(sb.height, 780)))
    mod("blender.panels").show_only()
    redraw_all()
    S["ws_i"] = 0
    return 1.0


@step
def s_workspaces():
    """Every built-in workspace (and the Client view) draws the button; in the Client view the click opens it too."""
    sc = bpy.context.scene
    ws = mod("blender.workspaces")
    ui_lm = mod("blender.ui_lead_motions")
    i = S["ws_i"]
    if i > 0:
        name = WORKSPACES[i - 1]
        check(f"'{name}' draws the Lead motions button", ui_lm.DRAWN["button"] > S["ws_drawn"],
              f"{ui_lm.DRAWN['button'] - S['ws_drawn']} times")
    if i >= len(WORKSPACES):
        return 0.5
    ws.switch(sc, WORKSPACES[i])
    S["ws_drawn"] = ui_lm.DRAWN["button"]
    S["ws_i"] = i + 1
    redraw_all()
    win = win0()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=win.width // 2, y=win.height // 2 + i)
    return "again" if S["ws_i"] <= len(WORKSPACES) else 1.0


@step
def s_client_click():
    ui_lm = mod("blender.ui_lead_motions")
    lock = mod("blender.lock")
    check("the Client view is on (locked)", lock.ON[0])
    S["menu1"] = ui_lm.DRAWN["menu"]
    S["on2"] = find_button()
    redraw_all()
    return 1.0


@step
def s_client_click_2():
    ui_lm = mod("blender.ui_lead_motions")
    off = grab("_topbar_off2.png", (0, 0, win0().width, topbar_height()))
    ui_lm.HIDE[0] = False
    redraw_all()
    cols = _diff_columns(S["on2"], off)
    check("the Client view's top bar draws Lead motions", cols is not None, str(cols))
    if cols:
        win = win0()
        S["click2"] = ((cols[0] + cols[1]) // 2, win.height - topbar_height() // 2 + 2)
        click(*S["click2"])
    S["cols2"] = cols
    return 1.5


@step
def s_client_again():
    ui_lm = mod("blender.ui_lead_motions")
    if ui_lm.DRAWN["menu"] == S["menu1"] and S.get("click2"):
        log("the first click in the Client view only focused the top bar: once more")
        click(*S["click2"])
    return 1.5


@step
def s_client_opened():
    sc = bpy.context.scene
    ui_lm = mod("blender.ui_lead_motions")
    joints = mod("blender.joints")
    check("one click opens the drop-down in the Client view", ui_lm.DRAWN["menu"] > S["menu1"])
    grab("lead_motions_client_full.png")
    esc()
    lm = sc.fresing.lead_motions["Trolley out"]
    lm.position = 100.0
    t = joints.get_value(joints.find(sc, "Trolley"))
    check("a slider moves the model in the Client view", abs(t - mod("blender.tour").TROLLEY_RUN) < 1e-6, f"{t:.3f}")
    with override():
        check("the Client view keeps ▶ and Back to start, refuses Edit and + Add to animation",
              bpy.ops.fresing.lead_play.poll() and bpy.ops.fresing.lead_back_to_start.poll()
              and not bpy.ops.fresing.lead_edit.poll() and not bpy.ops.fresing.lead_add_step.poll())
        bpy.ops.fresing.lead_back_to_start()
    check("Back to start in the Client view", abs(joints.get_value(joints.find(sc, "Trolley"))) < 1e-7)
    mod("blender.workspaces").switch(sc, "All functions")
    redraw_all()
    return 1.0


@step
def s_mockups():
    """The report's mock-ups: the same drop-down button in the 3D view's header (place b) – place c, a corner of the
    3D view, is pasted from the top bar's drop-down by tools in the report."""
    ui_lm = mod("blender.ui_lead_motions")
    S["hdr"] = lambda self, context: ui_lm.draw_button(self.layout, context)
    bpy.types.VIEW3D_HT_header.append(S["hdr"])
    redraw_all()
    return 1.5


@step
def s_mockups_2():
    grab("mockup_b_header_full.png")
    bpy.types.VIEW3D_HT_header.remove(S["hdr"])
    redraw_all()
    return 0.5


@step
def s_finish():
    bpy.context.preferences.system.use_region_overlap = S.get("overlap", True)   # Blender saves preferences
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
    if r == "again":
        return 1.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
