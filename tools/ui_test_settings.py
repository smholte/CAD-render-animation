"""Real-app test, Fresing Settings (task 0271): the Fresing menu's Settings… opens one window with a row of tabs; each
tab is clicked and draws its page; the window stays open when the main window is clicked; it opens on the last tab
after closing and opening again; Help / Fresing > My usage… opens it on My usage; it opens in the Client view. My usage
counts only the user's own input: a played animation with no mouse or key adds nothing (and the old marks – a change of
the project – are counted while it plays, to show what was counted before), a real mouse move marks presence.
Task 0283: one setting of each tab changed, the app started again (``ui_test_settings_restart.py``, same settings
folder, app template): every value is back; a damaged settings file: the app starts with the defaults and one note.
Task 0295: Fresing > Keys… opens the tab Keys; Measure's key changed by pressing Ctrl+Alt+K in the window, Copy on M
refused (Measure has it), Ctrl+Alt+K starts Measure in the 3D view and Alt+M no longer; the key is back after the
restart. Guide pictures of each tab when GUIDE_OUT is set.

Install the extension and the app template first (see ui_test_app.py), then run (FRESING_USAGE_TEST=1 so the usage
tracker counts although events are simulated):
    FRESING_USAGE_TEST=1 xvfb-run -a -s "-screen 0 1920x1080x24" blender --app-template fresing_render \\
        --enable-event-simulate -p 0 0 1920 1080 --python tools/ui_test_settings.py
Screenshots and ui_test_settings.log go to $UITEST_OUT (default ~/fresing_ui_test_settings).
"""

import os
import subprocess
import tempfile
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_settings"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_settings.log"), "w")
RESULTS = []
TMP = tempfile.mkdtemp(prefix="fr_settings é ")
S = {}


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
    return importlib.import_module(pkg() + ("." + name if name else ""))


def main_win():
    sm = mod("blender.ops_setup")
    return next(w for w in bpy.context.window_manager.windows if not sm.tab_of(w))


def view():
    win = main_win()
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return win, area, next(r for r in area.regions if r.type == "WINDOW")


def override():
    win, area, region = view()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def shot(name):
    path = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", path], check=False)
    return path


def redraw():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            area.tag_redraw()


def settings_wins():
    return mod("blender.ops_settings").settings_windows()


def side_region(win):
    area = mod("blender.ops_settings").settings_area(win)
    return area, next(r for r in area.regions if r.type == "TOOLS")      # the page: the toolbar region


def crop_window(path, win, name):
    """The Settings window's side panel, cut from a root screenshot (GUIDE_OUT set: into docs/img as a guide picture)."""
    out = os.environ.get("GUIDE_OUT")
    _area, reg = side_region(win)
    screen_h = int(subprocess.run(["identify", "-format", "%h", path], capture_output=True, text=True).stdout or 1080)
    left = win.x + reg.x
    top = screen_h - (win.y + reg.y + reg.height)
    log(f"settings window {win.x},{win.y} {win.width}x{win.height}; panel {reg.x},{reg.y} {reg.width}x{reg.height}")
    dst = os.path.join(out, name + ".png") if out else os.path.join(OUT, name + "_crop.png")
    subprocess.run(["convert", path, "-crop", f"{reg.width}x{reg.height}+{left}+{top}", "+repage", dst], check=False)
    # down to the page's last line (the empty panel below it and the tab strip at its right edge left out)
    got = subprocess.run(["convert", dst, "-crop", f"{max(reg.width - 40, 1)}x{reg.height}+0+0", "+repage", "-fuzz", "3%",
                          "-trim", "-format", "%h %Y", "info:"], capture_output=True, text=True).stdout.split()
    if len(got) == 2:
        h = int(got[0]) + int(got[1].split("+")[-1]) + 12
        subprocess.run(["convert", dst, "-crop", f"{reg.width}x{h}+0+0", "+repage", dst], check=False)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def wait_until(name, cond, seconds=30.0):
    def fn():
        if "t_wait" not in S:
            S["t_wait"] = time.time()
        try:
            ok = cond()
        except Exception:  # noqa: BLE001
            ok = False
        if ok or time.time() - S["t_wait"] > seconds:
            check(name, ok, f"{time.time() - S.pop('t_wait'):.1f} s")
            return 0.3
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


@step
def s_start():
    check("the extension is on", pkg() is not None)
    win, area, _r = view()
    win.event_simulate(type="ESC", value="PRESS", x=area.x + 30, y=area.y + 30)     # the splash swallows keys
    win.event_simulate(type="ESC", value="RELEASE", x=area.x + 30, y=area.y + 30)
    us = mod("blender.usage")
    check("the usage tracker counts in this test", us.counting())
    p = mod("blender.prefs").get()
    p.settings_tab = "general"
    redraw()
    return 1.5


# ----- My usage: an animation that plays by itself adds no time -----

@step
def s_play():
    scene = bpy.context.scene
    ob = bpy.data.objects.new("FR test mover", None)
    scene.collection.objects.link(ob)
    ob.keyframe_insert("location", frame=1)
    ob.location.x = 3.0
    ob.keyframe_insert("location", frame=60)
    scene.frame_start, scene.frame_end = 1, 60
    us = mod("blender.usage")
    us.record("fresing.render")                     # the user clicked Render image: the stage is Render & export
    S["stage"] = us.CLOCK.stage
    S["before"] = dict(us.state()["stages"])
    S["marks"] = us._S["marks"]
    S["changes"] = [0]

    def seen(*_a):
        S["changes"][0] += 1

    S["seen"] = seen
    bpy.app.handlers.depsgraph_update_post.append(seen)
    S["draws"] = [0]

    def drawn():
        S["draws"][0] += 1

    # how often the left panel (where the favourites bar sits) is drawn: each draw was a sign of the user before 0271
    S["draw_h"] = bpy.types.SpaceView3D.draw_handler_add(drawn, (), "TOOLS", "POST_PIXEL")
    us.IDLE_WAS = us.core.IDLE
    us.core.IDLE = 4.0                               # 4 s stand for the 2 minutes, so the test is short
    with override():
        bpy.ops.screen.animation_play()
    S["t_play"] = time.time()
    return 9.0                                       # 9 s of playback, nothing touched


@step
def s_play_stop():
    us = mod("blender.usage")
    playing = bpy.context.screen.is_animation_playing if bpy.context.screen else False
    with override():
        bpy.ops.screen.animation_cancel(restore_frame=False)
    log(f"while playing {time.time() - S['t_play']:.1f} s with no input: {S['changes'][0]} changes of the project, "
        f"{S['draws'][0]} draws of the left panel (each one was a sign of the user before task 0271), "
        f"{us._S['marks'] - S['marks']} presence marks")
    S["changes"][0] = S["draws"][0] = 0
    check("the animation played", playing or S["changes"][0] > 0)
    check("no presence mark while it played with no input", us._S["marks"] == S["marks"],
          us._S["marks"] - S["marks"])
    win, area, _r = view()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=area.x + 200, y=area.y + 200)   # back at the PC
    return 0.5


@step
def s_play_counted():
    us = mod("blender.usage")
    st = S["stage"]
    added = us.state()["stages"].get(st, 0.0) - S["before"].get(st, 0.0)
    check("a real mouse move marks presence (the keymap watcher)", us._S["marks"] > S["marks"], us._S["marks"])
    check("9 s of playback with no input added no time to My usage", added < 0.5, f"{added:.2f} s")
    win, area, _r = view()
    for i in range(6):                               # now the user works: a mouse move each 1.2 s
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=area.x + 210 + 5 * i, y=area.y + 200)
    S["t_work"] = time.time()
    return 0.3


@step
def s_work_counted():
    win, area, _r = view()
    if time.time() - S["t_work"] < 3.0:
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=area.x + 300 + int(10 * (time.time() % 10)),
                           y=area.y + 220)
        return "again"
    us = mod("blender.usage")
    st = S["stage"]
    added = us.state()["stages"].get(st, 0.0) - S["before"].get(st, 0.0)
    check("mouse moves while working are counted", added >= 1.5, f"{added:.2f} s")
    S["before"] = dict(us.state()["stages"])
    S["marks"] = us._S["marks"]
    S["changes"][0] = S["draws"][0] = 0
    _w, area, _r = view()
    area.spaces.active.shading.type = "RENDERED"     # Live preview left on, nobody at the PC
    S["t_live"] = time.time()
    return 9.0


@step
def s_live_done():
    us = mod("blender.usage")
    _w, area, _r = view()
    area.spaces.active.shading.type = "SOLID"
    bpy.app.handlers.depsgraph_update_post.remove(S["seen"])
    bpy.types.SpaceView3D.draw_handler_remove(S["draw_h"], "TOOLS")
    log(f"Live preview {time.time() - S['t_live']:.1f} s with no input: {S['changes'][0]} changes of the project, "
        f"{S['draws'][0]} draws of the left panel, {us._S['marks'] - S['marks']} presence marks")
    check("no presence mark while Live preview ran with no input", us._S["marks"] == S["marks"])
    st = S["stage"]
    added = us.state()["stages"].get(st, 0.0) - S["before"].get(st, 0.0)
    check("Live preview with no input added no time beyond the 4 s after the last move", added <= 4.5, f"{added:.2f} s")
    us.core.IDLE = us.IDLE_WAS
    return 0.5


# ----- the window -----

@step
def s_open():
    with override():
        r = bpy.ops.fresing.settings("INVOKE_DEFAULT")
    check("Fresing > Settings… starts the window", r == {"FINISHED"}, r)
    return 1.0


wait_until("the Settings window is open", lambda: len(settings_wins()) == 1, 20)


@step
def s_open_tab():
    w = settings_wins()[0]
    st = mod("blender.ops_settings")
    ok, other = st.shows_only_the_page(w)
    if not ok and S.setdefault("wide_tries", 0) < 40:
        S["wide_tries"] += 1
        return "again"
    check("the window shows only the Settings page: no other tab, no 3D view, no header", ok, other)
    uis = [r for a in w.screen.areas for r in a.regions if r.type == "UI" and r.width > 1]
    check("no side panel (so no tab strip) in the window", not uis, [r.width for r in uis])
    area, reg = side_region(w)
    log("region overlap:", bpy.context.preferences.system.use_region_overlap)
    log(f"window {w.width} x {w.height}; page {reg.width} x {reg.height}; regions "
        + ", ".join(f"{r.type} {r.width}" for r in area.regions))
    check("it opens on General", mod("blender.ui_settings").current() == "general")
    S["tabs"] = list(mod("blender.ui_settings").KEYS)
    S["clicked"] = []
    return 0.5


def tab_point(win, i):
    """Where the i-th tab button is drawn: the rows under the title row (sizes of Blender's default layout)."""
    ui = mod("blender.ui_settings")
    _area, reg = side_region(win)
    scale = bpy.context.preferences.system.ui_scale or 1.0
    n = ui.per_row(reg.width, scale)
    unit = 20 * scale
    left, width = reg.x + 10 * scale, reg.width - 20 * scale
    each = width / n
    title = unit * 1.2 + 10 * scale                 # the title row and the panel's top margin
    row_h = unit * 1.2
    x = left + each * (i % n + 0.5)
    y = reg.y + reg.height - title - row_h * (i // n + 0.5) - 6 * scale
    return int(x), int(y)


@step
def s_click_tabs():
    i = len(S["clicked"])
    if i >= len(S["tabs"]):
        return 0.3
    win = settings_wins()[0]
    x, y = tab_point(win, i)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    S["clicked"].append((S["tabs"][i], x, y))
    S["t_click"] = time.time()
    return 0.6


@step
def s_tab_check():
    key, x, y = S["clicked"][-1]
    got = mod("blender.ui_settings").current()
    if got != key and len(S.setdefault("retry", {})) < 20 and S["retry"].get(key, 0) < 2:
        # the first click into a new window's panel only gives it focus (CLAUDE.md section 8): click once more
        S["retry"][key] = S["retry"].get(key, 0) + 1
        win = settings_wins()[0]
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
        return "again"
    check(f"a click on the tab '{key}' shows its page", got == key, f"{got} at {x},{y}")
    if got != key:                                  # go on with the button's own call
        with override():
            bpy.ops.fresing.settings_tab("EXEC_DEFAULT", True, tab=key)
    redraw()
    return 0.8


@step
def s_tab_shot():
    key = S["clicked"][-1][0]
    win = settings_wins()[0]
    path = shot(f"10_tab_{key}")
    crop_window(path, win, "usage_window" if key == "usage" else f"settings_{key}")
    if len(S["clicked"]) < len(S["tabs"]):
        _i[0] = STEPS.index(s_click_tabs) - 1     # the next tab
    return 0.3


@step
def s_all_tabs():
    done = [k for k, _x, _y in S["clicked"]]
    check("every tab was clicked", done == S["tabs"], ", ".join(done))
    win, area, _r = view()                          # a click in the main window: the Settings window stays
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_stays():
    check("the Settings window stays open after a click in the main window", len(settings_wins()) == 1)
    with override():
        bpy.ops.fresing.settings_tab("EXEC_DEFAULT", True, tab="lessons")
        r = bpy.ops.fresing.settings("INVOKE_DEFAULT")
    check("opening it again gives no second window", r == {"FINISHED"} and len(settings_wins()) == 1)
    with override():
        bpy.ops.fresing.settings_close("EXEC_DEFAULT")
    return 1.0


wait_until("Close closes the Settings window", lambda: not settings_wins(), 10)


@step
def s_reopen():
    with override():
        bpy.ops.fresing.settings("INVOKE_DEFAULT")
    return 1.0


wait_until("it opens again", lambda: len(settings_wins()) == 1, 20)
wait_until("opened again, it shows only the Settings page",
           lambda: mod("blender.ops_settings").shows_only_the_page(settings_wins()[0])[0], 10)


@step
def s_kept():
    check("it opens on the last tab (Lessons)", mod("blender.ui_settings").current() == "lessons")
    with override():
        r = bpy.ops.fresing.usage_window("INVOKE_DEFAULT")
    check("My usage… opens the same window on My usage", r == {"FINISHED"} and len(settings_wins()) == 1
          and mod("blender.ui_settings").current() == "usage")
    redraw()
    return 1.0


@step
def s_client_close():
    with override():
        bpy.ops.fresing.settings_close("EXEC_DEFAULT")
    return 1.0


wait_until("closed before the Client view", lambda: not settings_wins(), 10)


@step
def s_client():
    redraw()
    with override():
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="Client view")
    return 3.0


@step
def s_client_open():
    with override():
        check("Client view: Settings… can be pressed", bpy.ops.fresing.settings.poll())
        r = bpy.ops.fresing.settings("INVOKE_DEFAULT")
    check("Client view: the window starts", r == {"FINISHED"}, r)
    return 1.0


wait_until("Client view: the Settings window opens", lambda: len(settings_wins()) == 1, 20)


@step
def s_client_shot():
    shot("20_client_view")
    redraw()
    with override():                                # back to All functions while the window stays open
        bpy.ops.fresing.workspace_pick("EXEC_DEFAULT", True, name="All functions")
    return 3.0


@step
def s_client_back():
    check("the Settings window stays open while the workspace changes", len(settings_wins()) == 1)
    with override():
        bpy.ops.fresing.settings_close("EXEC_DEFAULT")
    mod("blender.prefs").get().settings_tab = "general"
    return 1.0


wait_until("Close closes it", lambda: not settings_wins(), 10)


# ----- task 0295: Settings > Keys – a key changed by pressing it, a clash refused, the new key works -----

def settings_override():
    win = settings_wins()[0]
    area, reg = side_region(win)
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=reg, scene=win.scene)


@step
def s_keys_open():
    with override():
        r = bpy.ops.fresing.keys("INVOKE_DEFAULT")
    check("Fresing > Keys… starts the Settings window", r == {"FINISHED"}, r)
    return 1.0


wait_until("Keys…: the Settings window opens on Keys",
           lambda: len(settings_wins()) == 1 and mod("blender.ui_settings").current() == "keys", 20)


@step
def s_keys_capture():
    keys = mod("blender.keys")
    keys.reset()
    with settings_override():
        r = bpy.ops.fresing.key_change("INVOKE_DEFAULT", id="measure_all")
    check("a click on Measure's key waits for a key press", r == {"RUNNING_MODAL"} and keys.CAPTURE[0] == "measure_all",
          r)
    win = settings_wins()[0]
    _area, reg = side_region(win)
    x, y = reg.x + reg.width // 2, reg.y + reg.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="K", value="PRESS", x=x, y=y, ctrl=True, alt=True)
    win.event_simulate(type="K", value="RELEASE", x=x, y=y, ctrl=True, alt=True)
    return 1.0


@step
def s_keys_changed():
    keys, lock = mod("blender.keys"), mod("blender.lock")
    got = keys.changes()
    check("the pressed key is Measure's new key", got == {"measure_all": ("K", {"ctrl": True, "alt": True})}, got)
    items = [(kmi.idname, kmi.type, kmi.ctrl == 1, kmi.alt == 1) for _km, kmi in lock._KEYMAPS]
    check("the keymap has Ctrl+Alt+K for Measure, no Alt+M", ("fresing.measure", "K", True, True) in items
          and ("fresing.measure", "M", False, True) not in items, [i for i in items if i[0] == "fresing.measure"])
    bpy.context.window_manager.fresing_keys_search = "measure"     # the picture shows the changed key
    redraw()
    return 1.0


@step
def s_keys_shot():
    win = settings_wins()[0]
    path = shot("12_keys_changed")
    crop_window(path, win, "settings_keys_changed")
    bpy.context.window_manager.fresing_keys_search = ""
    with settings_override():                       # a clash: Copy on M (Measure's key) is refused
        bpy.ops.fresing.key_change("INVOKE_DEFAULT", id="copy")
    _area, reg = side_region(win)
    x, y = reg.x + reg.width // 2, reg.y + reg.height // 2
    win.event_simulate(type="M", value="PRESS", x=x, y=y)
    win.event_simulate(type="M", value="RELEASE", x=x, y=y)
    return 1.0


@step
def s_keys_clash():
    keys = mod("blender.keys")
    check("a key another Fresing key has is refused", "copy" not in keys.changes() and keys._LAST["warn"]
          and "Measure" in keys._LAST["text"], keys._LAST)
    with settings_override():
        bpy.ops.fresing.settings_close("EXEC_DEFAULT")
    win, area, _r = view()                          # the new key in the 3D view
    x, y = area.x + area.width // 2, area.y + area.height // 2
    S["mouse"] = (x, y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="K", value="PRESS", x=x, y=y, ctrl=True, alt=True)
    win.event_simulate(type="K", value="RELEASE", x=x, y=y, ctrl=True, alt=True)
    return 1.0


@step
def s_keys_works():
    measure = mod("blender.measure")
    check("Ctrl+Alt+K starts Measure in the 3D view", measure.tool_state() is not None)
    win, _area, _r = view()
    x, y = S["mouse"]
    win.event_simulate(type="ESC", value="PRESS", x=x, y=y)
    win.event_simulate(type="ESC", value="RELEASE", x=x, y=y)
    return 0.8


@step
def s_keys_old():
    win, _area, _r = view()
    x, y = S["mouse"]
    S["old_tool"] = mod("blender.measure").tool_state()
    win.event_simulate(type="M", value="PRESS", x=x, y=y, alt=True)
    win.event_simulate(type="M", value="RELEASE", x=x, y=y, alt=True)
    return 1.0


@step
def s_keys_old_check():
    tool = mod("blender.measure").tool_state()
    check("Measure was left with Esc", S["old_tool"] is None, S["old_tool"])
    check("Alt+M no longer starts Measure", tool is None)
    if tool is not None:
        win, _area, _r = view()
        x, y = S["mouse"]
        win.event_simulate(type="ESC", value="PRESS", x=x, y=y)
        win.event_simulate(type="ESC", value="RELEASE", x=x, y=y)
    return 0.8


# ----- task 0283: one setting of each tab changed, the app started again, every value back; a damaged file -----
KEPT = {
    "hover_highlight": False,                 # General
    "default_rule_set": "Offshore",           # General
    "keep_sections": True,                    # Side panel
    "lesson_part": "1",                       # Lessons
    "lesson_colour": [0.9, 0.1, 0.4],         # Lessons
    "backup_minutes": 12,                     # Backups
    "check_updates": False,                   # Updates
    "settings_tab": "backups",                # the window's last tab
    "key_changes": '{"measure_all": {"alt": true, "ctrl": true, "key": "K"}}',   # Keys (task 0295)
}


def restart(name):
    """The app started again in this settings folder with the app template; what it started with."""
    import json
    out = os.path.join(TMP, name + ".json")
    env = dict(os.environ, FR_SETTINGS_RESTART_OUT=out, FR_SETTINGS_NAMES=json.dumps(sorted(KEPT)),
               UITEST_OUT=os.path.join(OUT, name))
    child = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_test_settings_restart.py")
    t = time.time()
    try:
        subprocess.run([bpy.app.binary_path, "--app-template", "fresing_render", "--enable-event-simulate",
                        "-p", "0", "0", "1280", "900", "--python", child], env=env, timeout=240, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        log(f"the restarted app ({name}) did not finish in 240 s")
    try:
        got = json.load(open(out, encoding="utf-8"))
    except (OSError, ValueError):
        got = {}
    log(f"restarted app ({name}, {time.time() - t:.0f} s):", got)
    return got


@step
def s_keep_change():
    p = mod("blender.prefs").get()
    S["was"] = {n: (list(getattr(p, n)) if n == "lesson_colour" else getattr(p, n)) for n in KEPT}
    for n, v in KEPT.items():
        setattr(p, n, v)
    return 2.5                                         # the settings timer writes within a second


@step
def s_keep_written():
    import json
    store = mod("blender.settings_store")
    try:
        data = json.load(open(store.path(), encoding="utf-8"))["settings"]
    except (OSError, ValueError, KeyError) as exc:
        data = {"error": str(exc)}
    ok = all(n in data and (data[n] == v if n != "lesson_colour" else
                            all(abs(a - b) < 1e-4 for a, b in zip(data[n], v))) for n, v in KEPT.items())
    check("a change is written to the settings file by itself (no Save Preferences)", ok, str(data))
    return 0.3


@step
def s_keep_restart():
    got = restart("restart")
    check("the restarted app runs with the app template", got.get("template") == "fresing_render", got.get("template"))
    values = got.get("values", {})
    for n, v in KEPT.items():
        g = values.get(n)
        ok = (g == v) if n != "lesson_colour" else (isinstance(g, list) and all(abs(a - b) < 1e-3 for a, b in zip(g, v)))
        check(f"after a restart {n} is as chosen", ok, f"{g}, chosen {v}")
    check("after a restart no note about the settings file", got.get("notes") == [], str(got.get("notes")))
    check("after a restart the changed key is in the keymap (Ctrl+Alt+K for Measure)",
          ["K", True, True] in got.get("measure_keys", []) and ["M", False, True] not in got.get("measure_keys", []),
          got.get("measure_keys"))
    return 0.3


@step
def s_keep_damaged():
    store = mod("blender.settings_store")
    with open(store.path(), "w", encoding="utf-8") as fh:
        fh.write('{"format": "fresing-settings", "version": 1, "settings": {"keep_sections": tr')
    got = restart("damaged")
    check("a damaged settings file: the app starts all the same", got.get("started") is True, str(got))
    values = got.get("values", {})
    check("a damaged settings file: the defaults are used", values.get("keep_sections") is False
          and values.get("backup_minutes") == 5 and values.get("hover_highlight") is True, str(values))
    notes = got.get("notes") or []
    check("a damaged settings file: one plain note", len(notes) == 1 and "damaged" in notes[0], str(notes))
    folder = os.path.dirname(store.path())
    copies = [f for f in os.listdir(folder) if f.startswith("fresing_settings.broken-")]
    check("a damaged settings file: a copy is kept", len(copies) == 1, str(copies))
    for f in copies:
        os.remove(os.path.join(folder, f))
    return 0.3


@step
def s_keep_back():
    """Put the settings back: the next real-app test in this settings folder starts as before (CLAUDE.md 8)."""
    p = mod("blender.prefs").get()
    for n, v in S.get("was", {}).items():
        setattr(p, n, v)
    mod("blender.keys").reset()                     # task 0295: Measure's own key back (the keymap too)
    return 2.5


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
    except Exception:  # noqa: BLE001
        log("ERROR in", fn.__name__, traceback.format_exc())
        check(fn.__name__, False, "exception")
        r = 0.5
    if r == "again":
        return 0.2
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
