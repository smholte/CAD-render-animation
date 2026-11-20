"""PROTOTYPE 0244 (never merged): pictures and timings of the side-panel look for steps 4 and 5.

    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1920x1080x24" blender -p 0 0 1920 1080 \
        --app-template fresing_render --enable-event-simulate --python tools/proto_0244_shots.py
Env: P244_OUT (folder), P244_TAG ("1920"), P244_SCALE (UI scale, 1.0), P244_ONLY (comma list of shot names),
P244_TIME=1 (timings after the pictures).
"""

import json
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("P244_OUT", os.path.expanduser("~/p244"))
TAG = os.environ.get("P244_TAG", "1920")
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, f"log_{TAG}.txt"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[P244]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def mod(name):
    import importlib
    import addon_utils
    pkg = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    return importlib.import_module(pkg + "." + name)


def areas():
    win = bpy.context.window_manager.windows[0]
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override(sidebar=False):
    win, area, region, sb = areas()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if sidebar else region,
                                     scene=win.scene)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region, sb = areas()
    win.event_simulate(type="ESC", value="PRESS", x=700, y=500)
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    return 1.0


@step
def s_import():
    with override():
        res = bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    log("import", res)
    return 1.0


@step
def s_wait():
    return "wait" if bpy.context.scene.fresing.model_count == 0 else 1.0


@step
def s_state():
    sc = bpy.context.scene
    tour = mod("blender.tour")
    tour._boom_joint(sc)
    sc.fresing.cylinders_index = 0
    ob = next(o for o in sc.objects if o.get("fr_name") == "BOOM.ASM")
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    log("joints", len(sc.fresing.joints), "cylinders", len(sc.fresing.cylinders))
    for o in sc.objects:
        o.select_set(o.get("fr_name", "").startswith(("BOOM", "PEDESTAL", "HYDRAULIC", "TROLLEY", "BASE")))
    with override():
        bpy.ops.view3d.view_selected()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    return 1.0


# ---------------------------------------------------------------------------
# the shots: (name, look settings, open panels, open folds)
# ---------------------------------------------------------------------------

M, SC, CYL = "FRESING_PT_motion", "FRESING_PT_scene", "FRESING_PT_cylinders"
SHOTS = [   # name, look, open panels, open folds, scroll (px at UI scale 1: 560 = step 4 at the top)
    ("old_step4", dict(look="old"), [M], [], 560),
    ("old_cyl", dict(look="old"), [M, CYL], [], 1090),
    ("new_step4", dict(look="new"), [M], [], 560),
    ("new_step4_strip", dict(look="new", overlay="strip"), [M], [], 560),
    ("new_cyl", dict(look="new"), [M, CYL], ["fr_cylinder_setup"], 1090),
    ("new_cyl_brand", dict(look="new", arrow="brand"), [M, CYL], ["fr_cylinder_setup"], 1090),
    ("new_step5_closed", dict(look="new"), [], [], 560),
    ("new_step5", dict(look="new"), [SC, "FRESING_PT_camera"], [], 560),
    ("fallback_step4", dict(look="fallback"), [M], [], 560),
    ("fallback_cyl", dict(look="fallback"), [M, CYL], ["fr_cylinder_setup"], 1090),
    ("fold_cyl", dict(look="new", how="fold"), [M, CYL], ["fr_cylinder_setup"], 1090),
    ("lpanel_cyl", dict(look="fallback", how="lpanel"), [M], [], 1090),
    ("new_three", dict(look="new"), [M, CYL, "FRESING_PT_poses", "FRESING_PT_mechanisms"], [], 1090),
]
ONLY = [s for s in os.environ.get("P244_ONLY", "").split(",") if s]
if ONLY:
    SHOTS = [s for s in SHOTS if s[0] in ONLY]
_k = [0]


def _set(look, opened, folds):
    l2 = mod("blender.look244")
    panels = mod("blender.panels")
    base = dict(look="old", how="sub", arrow="light", one_open=False, overlay="full", probe=False)
    base.update(look)
    l2.set(**base)
    panels.OPEN.clear()
    panels.OPEN.update(panels.DEFAULT_OPEN)
    for n in panels.PARENT:
        if panels.PARENT[n] in (M, SC):
            panels.OPEN.discard(n)
    panels.OPEN.update(opened)
    l2.FOLDS.clear()
    l2.FOLDS.update(folds)


def _scroll_to(px_at_1):
    """The side panel scrolled so step 4's title row is near its top (the top of the tab is out of the way)."""
    win, area, region, sb = areas()
    v2 = sb.view2d
    with override(sidebar=True):
        for _ in range(40):
            bpy.ops.view2d.scroll_up(deltax=0, deltay=200)
        y0 = v2.region_to_view(0, sb.height)[1]
        for _ in range(200):
            bpy.ops.view2d.scroll_down(deltax=0, deltay=10)
            if y0 - v2.region_to_view(0, sb.height)[1] >= px_at_1 * bpy.context.preferences.view.ui_scale:
                break
        log("scrolled", y0 - v2.region_to_view(0, sb.height)[1])


def _shot(name):
    win, area, region, sb = areas()
    full = os.path.join(OUT, f"{name}_{TAG}_window.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    crop = os.path.join(OUT, f"{name}_{TAG}_panel.png")
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{sb.height}+{sb.x}+{top}", "+repage", crop], check=False)
    log("shot", name, "sidebar", sb.x, sb.y, sb.width, sb.height, "overlay found", mod("blender.look244").STATS)


@step
def s_shots():
    if _k[0] >= len(SHOTS) * 3:
        return 0.5
    i, phase = divmod(_k[0], 3)
    name, look, opened, folds, scroll = SHOTS[i]
    win, area, region, sb = areas()
    if phase == 0:
        _set(look, opened, folds)
    elif phase == 1:
        _scroll_to(scroll)
    else:
        _shot(name)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + _k[0], y=region.y + 300)
    for a in win.screen.areas:
        a.tag_redraw()
    _k[0] += 1
    return "again" if _k[0] < len(SHOTS) * 3 else 0.5


@step
def s_full_blender():
    """Show all of Blender's editors with the new greys (Outliner + Properties next to the view)."""
    if ONLY and "blender" not in ONLY:
        return 0.1
    _set(dict(look="new"), [M, CYL], ["fr_cylinder_setup"])
    ed = mod("blender.editors")
    ed.choose(True)
    ed.request(True)
    return 3.0


@step
def s_full_blender_shot():
    if ONLY and "blender" not in ONLY:
        return 0.1
    win = bpy.context.window_manager.windows[0]
    for a in win.screen.areas:
        if a.type == "PROPERTIES":
            try:
                a.spaces[0].context = "RENDER"
            except Exception:  # noqa: BLE001
                pass
        a.tag_redraw()
    full = os.path.join(OUT, f"blender_new_{TAG}_window.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    mod("blender.look244").set(look="new", probe=True)
    return 2.0


@step
def s_full_blender_probe():
    if ONLY and "blender" not in ONLY:
        return 0.1
    full = os.path.join(OUT, f"blender_probe_{TAG}_window.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    mod("blender.look244").set(look="old", probe=False)
    return 2.0


@step
def s_full_blender_old():
    if ONLY and "blender" not in ONLY:
        return 0.1
    full = os.path.join(OUT, f"blender_old_{TAG}_window.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    ed = mod("blender.editors")
    ed.choose(False)
    ed.request(False)
    return 3.0


# ---------------------------------------------------------------------------
# timings: the side panel's redraw, wm.redraw_timer DRAW on the side panel region
# ---------------------------------------------------------------------------

def _measure(kind, n, action=None):
    """n redraws of the side panel (``kind`` of wm.redraw_timer), ``action(k)`` before each: wall ms per redraw,
    overlay ms per draw, markers found in the last draw."""
    l2 = mod("blender.look244")
    l2.STATS.update(n=0, t=0.0, found=0)
    tt = 0.0
    with override(sidebar=True):
        for k in range(n):
            if action is not None:
                action(k)
            t0 = time.perf_counter()
            bpy.ops.wm.redraw_timer(type=kind, iterations=1)
            tt += time.perf_counter() - t0
    return tt / n * 1000, l2.STATS["t"] / max(1, l2.STATS["n"]) * 1000, l2.STATS["found"]


def _scroll(k):
    win, area, region, sb = areas()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb):
        try:
            if k % 2 == 0:
                bpy.ops.view2d.scroll_down(deltax=0, deltay=40)
            else:
                bpy.ops.view2d.scroll_up(deltax=0, deltay=40)
        except RuntimeError:
            pass


def _drag(k):
    import math
    joints = mod("blender.joints")
    joints.set_value(bpy.context.scene.fresing.joints[0], math.radians(5 + (k % 10)))
    bpy.context.view_layer.update()


TIMES = []


@step
def s_times():
    if not os.environ.get("P244_TIME"):
        return 0.1
    l2 = mod("blender.look244")
    _set(dict(look="new"), [M], [])
    for kind in ("DRAW", "DRAW_SWAP", "DRAW_WIN", "DRAW_WIN_SWAP"):
        with override(sidebar=True):
            l2.STATS.update(n=0, t=0.0, found=-1)
            t0 = time.perf_counter()
            bpy.ops.wm.redraw_timer(type=kind, iterations=10)
            log("probe redraw", kind, round((time.perf_counter() - t0) * 100, 2), "ms", dict(l2.STATS))
    cases = [("old", dict(look="old")), ("fallback", dict(look="fallback")),
             ("new_full", dict(look="new", overlay="full")), ("new_strip", dict(look="new", overlay="strip"))]
    opens = {0: [M], 1: [M, CYL], 3: [M, CYL, "FRESING_PT_poses", "FRESING_PT_mechanisms"]}
    for rep in range(2):
        for cname, look in cases:
            for k, opened in opens.items():
                _set(look, opened, [])
                _scroll_to(560 if k == 0 else 1090)
                _measure("DRAW", 3)
                draw_ms = _measure("DRAW", 30)[0]                  # the panel's layout + drawing
                swap_ms, ov, found = _measure("DRAW_SWAP", 15)     # a whole redraw as shown (overlay finds its markers)
                row = dict(rep=rep, case=cname, open=k, draw_ms=round(draw_ms, 2), swap_ms=round(swap_ms, 2),
                           overlay_ms=round(ov, 2), found=found)
                if k == 1:
                    w, ov2, f2 = _measure("DRAW_SWAP", 20, _scroll)
                    row.update(scroll_swap_ms=round(w, 2), scroll_overlay_ms=round(ov2, 2), scroll_found=f2)
                    w, ov2, f2 = _measure("DRAW_SWAP", 20, _drag)
                    row.update(drag_swap_ms=round(w, 2), drag_overlay_ms=round(ov2, 2), drag_found=f2)
                    mod("blender.joints").set_value(bpy.context.scene.fresing.joints[0], 0.0)
                TIMES.append(row)
                log("time", json.dumps(row))
    win, area, region, sb = areas()
    with open(os.path.join(OUT, f"times_{TAG}.json"), "w") as fh:
        json.dump(dict(window=[win.width, win.height], sidebar=[sb.width, sb.height],
                       scale=bpy.context.preferences.view.ui_scale, rows=TIMES), fh, indent=1)
    return 0.5


@step
def s_quit():
    LOG.close()
    bpy.ops.wm.quit_blender()


_i = [0]
_wait = [0.0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:  # noqa: BLE001
        log("ERROR in", fn.__name__, traceback.format_exc())
        r = 0.5
    if r == "again":
        return 1.0
    if r == "wait":
        if not _wait[0]:
            _wait[0] = time.time()
        if time.time() - _wait[0] > 180:
            log(fn.__name__, "timeout")
            _i[0] += 1
        return 1.0
    _wait[0] = 0.0
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("P244_SCALE", "1.0"))
bpy.context.preferences.view.show_splash = False
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
