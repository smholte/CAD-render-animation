"""Task 0200: measures Blender's ways to show a panel "somewhere else" in the real app (xvfb, event simulation).

    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1920x1200x24" blender -p 0 0 1920 1200 \
        --app-template fresing_render --enable-event-simulate --python tasks/0200_proto/probe.py

Env: PROBE_OUT (folder, default /tmp/probe0200), PROBE_SCALE (UI scale, default 1.0), PROBE_MODEL (STEP file),
PROBE_ONLY (comma list of hosts: popover,dialog,popup,pie,tab,tools,window,split).
Writes probe.log + screenshots; every finding is one line "RESULT host question answer".
"""
import json
import os
import subprocess
import sys
import time
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import setup_window  # noqa: E402

OUT = os.environ.get("PROBE_OUT", "/tmp/probe0200")
os.makedirs(OUT, exist_ok=True)
MODEL = os.environ.get("PROBE_MODEL") or os.path.join(HERE, "..", "..", "fresing_render", "data", "test_gantry.step")
ONLY = [x for x in os.environ.get("PROBE_ONLY", "").split(",") if x]
LOG = open(os.path.join(OUT, "probe.log"), "w")
RESULTS = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[PROBE]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def result(host, q, ans):
    RESULTS.setdefault(host, {})[q] = ans
    log("RESULT", host, "|", q, "|", ans)


# ---- draw cost: every host draws through setup_window.draw_wizard
COST = {"n": 0, "t": 0.0}
_orig = setup_window.draw_wizard


def _timed(layout, context):
    t = time.perf_counter()
    _orig(layout, context)
    COST["n"] += 1
    COST["t"] += time.perf_counter() - t


setup_window.draw_wizard = _timed


def main_win():
    return bpy.context.window_manager.windows[0]


def view3d(win=None):
    win = win or main_win()
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override(win=None, region_type="WINDOW"):
    win, area, _r = view3d(win)
    region = next(r for r in area.regions if r.type == region_type)
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region)


def shot(name):
    p = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", p], check=False)
    return p


def diff_box(a, b, fuzz="8%"):
    """Bounding box (x, y, w, h, changed pixels; screen pixels, y from the top) of what differs between two shots,
    looked for inside the main 3D view only (the status bar and the side panel change on their own)."""
    win, area, region = view3d()
    H = win.height
    cx, cy, cw, ch = region.x, H - (region.y + region.height), region.width, region.height
    crop = f"{cw}x{ch}+{cx}+{cy}"
    d = os.path.join(OUT, "_diff.png")
    r = subprocess.run(["compare", "-metric", "AE", "-fuzz", fuzz, "(", a, "-crop", crop, "+repage", ")",
                        "(", b, "-crop", crop, "+repage", ")", "-highlight-color", "white",
                        "-lowlight-color", "black", "-compose", "src", d], capture_output=True, text=True)
    r2 = subprocess.run(["convert", d, "-morphology", "Open", "Square:2", "-trim", "-format", "%w %h %X %Y",
                         "info:"], capture_output=True, text=True)
    try:
        w, h, x, y = r2.stdout.split()
        n = int(float(r.stderr.split()[0])) if r.stderr.strip() else 0
        if int(w) <= 1 or int(h) <= 1:
            return None
        return int(x) + cx, int(y) + cy, int(w), int(h), n
    except Exception:
        return None


def move(win, x, y):
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x), y=int(y))


def click(win, x, y, ctrl=False):
    move(win, x, y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=int(x), y=int(y), ctrl=ctrl)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=int(x), y=int(y), ctrl=ctrl)


def drag(win, x0, y0, dx, dy, n=12):
    move(win, x0, y0)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=int(x0), y=int(y0))
    for k in range(1, n + 1):
        move(win, x0 + dx * k / n, y0 + dy * k / n)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=int(x0 + dx), y=int(y0 + dy))


def key(win, k, ctrl=False, x=None, y=None):
    kw = {}
    if x is not None:
        kw = dict(x=int(x), y=int(y))
    win.event_simulate(type=k, value="PRESS", ctrl=ctrl, **kw)
    win.event_simulate(type=k, value="RELEASE", ctrl=ctrl, **kw)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


STATE = {}


@step
def s_start():
    bpy.context.preferences.view.ui_scale = float(os.environ.get("PROBE_SCALE", "1.0"))
    bpy.context.preferences.system.use_region_overlap = False
    win = main_win()
    key(win, "ESC", x=900, y=600)
    setup_window.register()
    log("window", win.width, win.height)
    return 1.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=os.path.abspath(MODEL), quality="normal")
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    path = os.path.join(OUT, "probe.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    STATE["blend"] = path
    win, area, region = view3d()
    for a in win.screen.areas:
        log("area", a.type, a.x, a.y, a.width, a.height)
    return 2.0


@step
def s_base():
    win, area, region = view3d()
    move(win, region.x + region.width * 0.5, region.y + region.height * 0.5)
    STATE["base"] = shot("00_base")
    return 0.5


# ------------------------------------------------------------------------------------------------ popup kinds
def _open(kind):
    win, area, region = view3d()
    cx, cy = region.x + region.width * 0.4, region.y + region.height * 0.55
    move(win, cx, cy)
    with override():
        if kind == "popover":
            bpy.ops.wm.call_panel(name="FRESING_PT_setup_pop", keep_open=True)
        elif kind == "popover_nokeep":
            bpy.ops.wm.call_panel(name="FRESING_PT_setup_pop", keep_open=False)
        elif kind == "dialog":
            bpy.ops.fresing.setup_dialog("INVOKE_DEFAULT")
        elif kind == "popup":
            bpy.ops.fresing.setup_popup("INVOKE_DEFAULT")
        elif kind == "pie":
            bpy.ops.wm.call_menu_pie(name="VIEW3D_MT_view_pie")



def same_at(a, b, box):
    """Share of pixels that differ between two shots inside box (0 = the same picture there)."""
    x, y, w, h = box[:4]
    crop = f"{w}x{h}+{x}+{y}"
    r = subprocess.run(["compare", "-metric", "AE", "-fuzz", "8%", "(", a, "-crop", crop, "+repage", ")",
                        "(", b, "-crop", crop, "+repage", ")", "null:"], capture_output=True, text=True)
    try:
        return float(r.stderr.split()[0]) / float(w * h)
    except Exception:
        return 1.0


def popup_case(kind):
    """open, find, drag, mouse away, click in the 3D view, Ctrl+Z, Ctrl+S, redraw, close.

    'Open' is judged by the popup's own picture: the pixels of its box in the shot right after it opened."""
    seq = []
    skip = lambda: bool(ONLY and kind.split("_")[0] not in ONLY)   # noqa: E731
    S = {}

    def is_open(p):
        if not S.get("box"):
            return False
        return same_at(S["ref"], p, S["box"]) < 0.15

    def reopen():
        _open(kind)

    def s_open():
        if skip():
            return 0.0
        COST.update(n=0, t=0.0)
        _open(kind)
        return 1.0

    def s_find():
        if skip():
            return 0.0
        p = shot(f"{kind}_1_open")
        box = diff_box(STATE["base"], p)
        S["box"], S["ref"] = box, p
        result(kind, "opens", f"box {box[:4]}" if box else "nothing drawn")
        if box:
            subprocess.run(["convert", p, "-crop", "{2}x{3}+{0}+{1}".format(*box), "+repage",
                            os.path.join(OUT, f"{kind}_crop.png")])
        n, t = COST["n"], COST["t"]
        if kind != "pie":
            result(kind, "draw", f"{n} draws, {1000 * t / max(n, 1):.2f} ms each")
        return 0.3

    def s_drag():
        if not S.get("box"):
            return 0.0
        win = main_win()
        x, y, w, h, _n = S["box"]
        drag(win, x + w * 0.5, win.height - (y + 5), 240, -120)    # 5 px below its top edge
        return 0.8

    def s_drag_check():
        if not S.get("box"):
            return 0.0
        p = shot(f"{kind}_2_dragged")
        x, y, w, h, n = S["box"]
        moved = (x + 240, y + 120, w, h)
        if same_at(S["ref"], p, S["box"]) < 0.15:
            result(kind, "drag by its top edge", "stays where it is")
        elif same_at_shift(S["ref"], p, S["box"], 240, 120) < 0.2:
            result(kind, "drag by its top edge", "MOVES with the mouse")
            S["ref"] = p
            S["box"] = (x + 240, y + 120, w, h, n)
        else:
            result(kind, "drag by its top edge", "closed (or changed)")
            S["box"] = None
        return 0.3

    def s_away():
        if not S.get("box"):
            return 0.0
        win, area, region = view3d()
        for k in range(6):
            move(win, region.x + 60 + k * 4, region.y + 60)        # far from the popup
        return 1.0

    def s_away_check():
        if not S.get("box"):
            return 0.0
        ok = is_open(shot(f"{kind}_3_away"))
        result(kind, "mouse moved far away", "stays open" if ok else "closes")
        if not ok:
            reopen()
        return 1.0

    def s_click3d():
        if skip():
            return 0.0
        p = shot(f"{kind}_3b_before_click")
        if S.get("box") and not is_open(p):
            box = diff_box(STATE["base"], p)
            S["box"], S["ref"] = box, p
        if not S.get("box"):
            return 0.0
        win, area, region = view3d()
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
        x, y, w, h, _ = S["box"]
        # a spot of the 3D view outside the popup, on the model (middle of the view, else beside the popup)
        px, py = region.x + region.width * 0.5, region.y + region.height * 0.45
        sx, sy = px, win.height - py
        if x <= sx <= x + w and y <= sy <= y + h:
            px = x + w + 120
        S["clickat"] = (px, py)
        click(win, px, py)
        return 1.0

    def s_click3d_check():
        if not S.get("box"):
            return 0.0
        ok = is_open(shot(f"{kind}_4_click3d"))
        sel = [o.get("fr_name", o.name) for o in bpy.context.selected_objects]
        result(kind, "click a part in the 3D view", ("stays open" if ok else "closes") +
               (f"; the click selected {sel[:2]}" if sel else "; the click selected nothing"))
        if not ok:
            reopen()
        return 1.0

    def s_undo():
        if not S.get("box"):
            return 0.0
        win = main_win()
        x, y, w, h, _ = S["box"]
        S["undo_ref"] = shot(f"{kind}_5_before_undo")
        key(win, "Z", ctrl=True, x=x + w / 2, y=win.height - (y + h / 2))   # mouse over the popup
        return 1.0

    def s_undo_check():
        if not S.get("box"):
            return 0.0
        ok = same_at(S["undo_ref"], shot(f"{kind}_6_undo"), S["box"]) < 0.15
        result(kind, "Ctrl+Z (mouse over it)", "stays open" if ok else "closes")
        if not ok:
            reopen()
        return 1.0

    def s_save():
        if not S.get("box"):
            return 0.0
        win = main_win()
        x, y, w, h, _ = S["box"]
        S["save_ref"] = shot(f"{kind}_7_before_save")
        STATE["mtime"] = os.path.getmtime(STATE["blend"])
        key(win, "S", ctrl=True, x=x + w / 2, y=win.height - (y + h / 2))
        return 1.5

    def s_save_check():
        if not S.get("box"):
            return 0.0
        ok = same_at(S["save_ref"], shot(f"{kind}_8_save"), S["box"]) < 0.15
        saved = os.path.getmtime(STATE["blend"]) != STATE["mtime"]
        result(kind, "Ctrl+S (mouse over it)", ("stays open" if ok else "closes") +
               ("; file saved" if saved else "; file not saved"))
        if not ok:
            reopen()
        return 1.0

    def s_redraw():
        if not S.get("box"):
            return 0.0
        S["rd_ref"] = shot(f"{kind}_9_before_redraw")
        bpy.context.scene.frame_set(bpy.context.scene.frame_current + 1)
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                a.tag_redraw()
        return 1.0

    def s_redraw_check():
        if not S.get("box"):
            return 0.0
        ok = same_at(S["rd_ref"], shot(f"{kind}_10_redraw"), S["box"]) < 0.15
        result(kind, "frame change + redraw", "stays open" if ok else "closes")
        return 0.3

    def s_close():
        if skip():
            return 0.0
        win = main_win()
        for k in range(2):
            key(win, "ESC", x=600, y=600)
        return 1.0

    for f in (s_open, s_find, s_drag, s_drag_check, s_away, s_away_check, s_click3d, s_click3d_check, s_undo,
              s_undo_check, s_save, s_save_check, s_redraw, s_redraw_check, s_close):
        f.__name__ = f"{kind}:{f.__name__}"
        STEPS.append(f)


def same_at_shift(a, b, box, dx, dy):
    x, y, w, h = box[:4]
    r = subprocess.run(["compare", "-metric", "AE", "-fuzz", "8%", "(", a, "-crop", f"{w}x{h}+{x}+{y}", "+repage",
                        ")", "(", b, "-crop", f"{w}x{h}+{x + dx}+{y + dy}", "+repage", ")", "null:"],
                       capture_output=True, text=True)
    try:
        return float(r.stderr.split()[0]) / float(w * h)
    except Exception:
        return 1.0


for _k in ("popover", "popover_nokeep", "dialog", "popup", "pie"):
    popup_case(_k)


# ------------------------------------------------------------------------------------------------ Next inside a popover
@step
def s_pop_next_open():
    if ONLY and "popover" not in ONLY:
        return 0.0
    bpy.context.window_manager.fr_wiz_step = 0
    _open("popover")
    return 1.0


@step
def s_pop_next_click():
    if ONLY and "popover" not in ONLY:
        return 0.0
    p = shot("popover_n1")
    nb = diff_box(STATE["base"], p)
    STATE["pn"] = nb
    if not nb:
        return 0.0
    win = main_win()
    x, y, w, h, _ = nb
    STATE["next_at"] = (x + w * 0.75, win.height - (y + h - 18))
    for k in range(3):
        move(win, STATE["next_at"][0] - 6 + 3 * k, STATE["next_at"][1])   # hover first, as a hand does
    return 0.5


@step
def s_pop_next_press():
    if not STATE.get("pn"):
        return 0.0
    win = main_win()
    x, y = STATE["next_at"]
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=int(x), y=int(y))
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=int(x), y=int(y))
    return 1.0


@step
def s_pop_keys_away():
    """keep_open popover open, mouse over the 3D view far from it: do Ctrl+S and the N key reach the app?"""
    if not STATE.get("pn"):
        return 0.0
    result("popover", "press Next inside", f"step now {bpy.context.window_manager.fr_wiz_step} (was 0)")
    win, area, region = view3d()
    for k in range(4):
        move(win, region.x + 80 + 4 * k, region.y + 80)
    STATE["mtime"] = os.path.getmtime(STATE["blend"])
    STATE["pk_ref"] = shot("popover_n2")
    return 0.5


@step
def s_pop_keys_away2():
    if not STATE.get("pn"):
        return 0.0
    win, area, region = view3d()
    key(win, "S", ctrl=True, x=region.x + 92, y=region.y + 80)
    return 1.5


@step
def s_pop_next_check():
    if not STATE.get("pn"):
        return 0.0
    p = shot("popover_n3")
    saved = os.path.getmtime(STATE["blend"]) != STATE["mtime"]
    still = diff_box(STATE["base"], p)
    result("popover", "Ctrl+S with the mouse over the 3D view (popover open)",
           ("saved" if saved else "not saved") + ("; popover still there" if still and still[2] > 100 else
                                                  "; popover closed"))
    win = main_win()
    key(win, "ESC", x=600, y=600)
    return 1.0


# ------------------------------------------------------------------------------------------------ docked hosts
@step
def s_tab():
    if ONLY and "tab" not in ONLY:
        return 0.0
    win, area, region = view3d()
    area.spaces.active.show_region_ui = True
    sb = next(r for r in area.regions if r.type == "UI")
    STATE["tab_cat_before"] = sb.active_panel_category
    sb.active_panel_category = "Set-up"
    COST.update(n=0, t=0.0)
    area.tag_redraw()
    return 1.0


@step
def s_tab_check():
    if ONLY and "tab" not in ONLY:
        return 0.0
    win, area, region = view3d()
    sb = next(r for r in area.regions if r.type == "UI")
    result("tab", "shows", f"category now '{sb.active_panel_category}', {COST['n']} draws, "
           f"{1000 * COST['t'] / max(COST['n'], 1):.2f} ms each")
    p = shot("tab_1")
    subprocess.run(["convert", p, "-crop", f"{sb.width}x{sb.height}+{sb.x}+{win.height - sb.y - sb.height}",
                    "+repage", os.path.join(OUT, "tab_crop.png")])
    click(win, region.x + region.width * 0.5, region.y + region.height * 0.45)
    return 1.0


@step
def s_tab_click():
    if ONLY and "tab" not in ONLY:
        return 0.0
    win, area, region = view3d()
    sb = next(r for r in area.regions if r.type == "UI")
    result("tab", "click in the 3D view", f"tab stays: '{sb.active_panel_category}'; selected "
           f"{len(bpy.context.selected_objects)}")
    sb.active_panel_category = STATE["tab_cat_before"] or "Fresing"
    return 0.5


@step
def s_tools():
    if ONLY and "tools" not in ONLY:
        return 0.0
    win, area, region = view3d()
    area.spaces.active.show_region_toolbar = True
    COST.update(n=0, t=0.0)
    for r in area.regions:
        log("region", r.type, r.x, r.y, r.width, r.height, getattr(r, "active_panel_category", ""))
    area.tag_redraw()
    return 1.0


@step
def s_tools_check():
    if ONLY and "tools" not in ONLY:
        return 0.0
    win, area, region = view3d()
    tr = next(r for r in area.regions if r.type == "TOOLS")
    result("tools", "left toolbar region", f"width {tr.width}, {COST['n']} draws of the set-up panel")
    shot("tools_1")
    return 0.3


@step
def s_split():
    if ONLY and "split" not in ONLY:
        return 0.0
    win, area, region = view3d()
    STATE["areas_before"] = len(win.screen.areas)
    with override():
        bpy.ops.screen.area_split(direction="VERTICAL", factor=0.75)
    return 1.0


@step
def s_split_check():
    if ONLY and "split" not in ONLY:
        return 0.0
    win = main_win()
    areas = [a for a in win.screen.areas if a.type == "VIEW_3D"]
    result("split", "areas", f"{STATE['areas_before']} -> {len(win.screen.areas)}; 3D views "
           + ", ".join(f"{a.x},{a.y} {a.width}x{a.height}" for a in areas))
    small = min(areas, key=lambda a: a.width)
    sp = small.spaces.active
    sp.show_region_ui = True
    sp.show_region_header = False
    sp.show_region_toolbar = False
    for r in small.regions:
        if r.type == "UI":
            r.active_panel_category = "Set-up"
    STATE["split_area"] = small
    return 1.0


@step
def s_split_shot():
    if ONLY and "split" not in ONLY:
        return 0.0
    shot("split_1")
    return 0.3


@step
def s_split_close():
    if ONLY and "split" not in ONLY:
        return 0.0
    win = main_win()
    a = STATE["split_area"]
    with bpy.context.temp_override(window=win, screen=win.screen, area=a):
        bpy.ops.screen.area_close()
    return 1.0


# ------------------------------------------------------------------------------------------------ second window
@step
def s_window():
    if ONLY and "window" not in ONLY:
        return 0.0
    STATE["nwin"] = len(bpy.context.window_manager.windows)
    COST.update(n=0, t=0.0)
    with override():
        r = bpy.ops.fresing.setup_window()
    log("setup_window", r)
    return 2.0


@step
def s_window_check():
    if ONLY and "window" not in ONLY:
        return 0.0
    wm = bpy.context.window_manager
    ws = list(wm.windows)
    result("window", "opens", f"{STATE['nwin']} -> {len(ws)} windows; " +
           "; ".join(f"x={w.x} y={w.y} {w.width}x{w.height} parent={'yes' if w.parent else 'no'}" for w in ws))
    result("window", "draw", f"{COST['n']} draws, {1000 * COST['t'] / max(COST['n'], 1):.2f} ms each")
    p = shot("window_1")
    if len(ws) > 1:
        w2 = ws[-1]
        a = w2.screen.areas[0]
        cats = [getattr(r, "active_panel_category", "") for r in a.regions if r.type == "UI"]
        result("window", "its sidebar tab", str(cats))
        main_areas = [(x.type, x.width) for x in ws[0].screen.areas]
        result("window", "main window areas after", str(main_areas))
        subprocess.run(["convert", p, "-crop", f"{w2.width}x{w2.height}+{w2.x}+{ws[0].height - w2.y - w2.height}",
                        "+repage", os.path.join(OUT, "window_crop.png")])
        win, area, region = view3d()
        for o in bpy.context.selected_objects:
            o.select_set(False)
        # a click in the MAIN window's 3D view (the set-up window lies over its right edge)
        click(win, region.x + region.width * 0.42, region.y + region.height * 0.42)
    return 1.0


@step
def s_window_undo():
    if ONLY and "window" not in ONLY:
        return 0.0
    ws = list(bpy.context.window_manager.windows)
    result("window", "click in the main 3D view", f"{len(ws)} windows open; the click selected "
           f"{[o.get('fr_name', o.name) for o in bpy.context.selected_objects][:2]}")
    win, area, region = view3d()
    key(win, "Z", ctrl=True, x=region.x + 100, y=region.y + 100)
    return 1.0


@step
def s_window_save():
    if ONLY and "window" not in ONLY:
        return 0.0
    result("window", "Ctrl+Z", f"{len(bpy.context.window_manager.windows)} windows open")
    STATE["mtime"] = os.path.getmtime(STATE["blend"])
    win, area, region = view3d()
    key(win, "S", ctrl=True, x=region.x + 100, y=region.y + 100)
    return 1.5


@step
def s_window_save_check():
    if ONLY and "window" not in ONLY:
        return 0.0
    saved = os.path.getmtime(STATE["blend"]) != STATE["mtime"]
    result("window", "Ctrl+S", f"{len(bpy.context.window_manager.windows)} windows open; "
           f"{'saved' if saved else 'not saved'}")
    # redraw cost while both windows are open: frame changes
    COST.update(n=0, t=0.0)
    t = time.perf_counter()
    for k in range(10):
        bpy.context.scene.frame_set(k + 1)
        bpy.ops.wm.redraw_timer(type="DRAW_WIN", iterations=1)
    dt = time.perf_counter() - t
    result("window", "10 frame changes + redraws, two windows", f"{dt * 1000 / 10:.1f} ms each, "
           f"set-up panel drawn {COST['n']} times")
    return 0.5


@step
def s_window_close_main_redraw():
    if ONLY and "window" not in ONLY:
        return 0.0
    wm = bpy.context.window_manager
    if len(wm.windows) > 1:
        w2 = wm.windows[-1]
        with bpy.context.temp_override(window=w2):
            bpy.ops.wm.window_close()
    COST.update(n=0, t=0.0)
    t = time.perf_counter()
    for k in range(10):
        bpy.context.scene.frame_set(k + 1)
        bpy.ops.wm.redraw_timer(type="DRAW_WIN", iterations=1)
    dt = time.perf_counter() - t
    result("window", "10 frame changes + redraws, one window", f"{dt * 1000 / 10:.1f} ms each")
    return 0.5


@step
def s_window_reopen():
    """Is the second window kept in the saved file? Open it again, save, open the file with its UI."""
    if ONLY and "window" not in ONLY:
        return 0.0
    with override():
        bpy.ops.fresing.setup_window()
    return 2.0


@step
def s_window_cost():
    if ONLY and "window" not in ONLY:
        return 0.0
    wm = bpy.context.window_manager
    for i, w in enumerate(wm.windows):
        COST.update(n=0, t=0.0)
        t = time.perf_counter()
        with bpy.context.temp_override(window=w, screen=w.screen):
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=20)
        dt = (time.perf_counter() - t) / 20
        result("window", f"redraw of window {i + 1} ({w.width}x{w.height})",
               f"{dt * 1000:.1f} ms; set-up panel drawn {COST['n']} times, {1000 * COST['t'] / max(COST['n'], 1):.2f} ms each")
    shot("window_3_short")
    if len(wm.windows) > 1:
        w2 = wm.windows[-1]
        subprocess.run(["convert", os.path.join(OUT, "window_3_short.png"), "-crop",
                        f"{w2.width}x{w2.height}+{w2.x}+{wm.windows[0].height - w2.y - w2.height}", "+repage",
                        os.path.join(OUT, "window_crop2.png")])
        result("window", "short window", f"x={w2.x} y={w2.y} {w2.width}x{w2.height}; main areas "
               f"{[(x.type, x.width, x.height) for x in wm.windows[0].screen.areas]}")
    bpy.ops.wm.save_mainfile()
    STATE["n_saved"] = len(wm.windows)
    bpy.ops.wm.open_mainfile(filepath=STATE["blend"], load_ui=True)
    return 3.0


@step
def s_window_reopen_check():
    if ONLY and "window" not in ONLY:
        return 0.0
    ws = list(bpy.context.window_manager.windows)
    cats = []
    for w in ws:
        for a in w.screen.areas:
            for r in a.regions:
                if r.type == "UI" and a.type == "VIEW_3D":
                    cats.append(r.active_panel_category)
    result("window", "file saved with 2 windows, opened again", f"{STATE['n_saved']} -> {len(ws)} windows; "
           f"sidebar tabs {cats}")
    shot("window_2_reopened")
    return 0.5


@step
def s_end():
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(RESULTS, f, indent=1)
    LOG.close()
    bpy.ops.wm.quit_blender()


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
        r = 0.5
    if r == "wait":
        _w[0] = _w[0] or time.time()
        if time.time() - _w[0] > 180:
            log("timeout", fn.__name__)
            _i[0] += 1
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return max(r or 0.0, 0.05)


bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
