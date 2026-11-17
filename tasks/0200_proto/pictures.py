"""Task 0200: pictures of the set-up window prototype, step by step (real app, xvfb).

    PIC_WIZ=CNC|MECH PIC_OUT=<dir> BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1920x1200x24" \
        blender -p 0 0 1920 1200 --app-template fresing_render --enable-event-simulate \
        --python tasks/0200_proto/pictures.py
"""
import os
import subprocess
import sys
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import setup_window  # noqa: E402

WIZ = os.environ.get("PIC_WIZ", "CNC")
OUT = os.environ.get("PIC_OUT", "/tmp/pics0200")
os.makedirs(OUT, exist_ok=True)
DATA = os.path.join(HERE, "..", "..", "fresing_render", "data")
MODEL = os.path.join(DATA, "test_gantry.step" if WIZ == "CNC" else "test_linkage_a.step")
SCALE = float(os.environ.get("PIC_SCALE", "1.5"))


def log(*a):
    print("[PICS]", *a, flush=True)


def view3d():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    return win, area, region


def override():
    win, area, region = view3d()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region)


def shot(name):
    p = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", p], check=False)
    return p


def crop_window(p, w, name):
    H = bpy.context.window_manager.windows[0].height
    subprocess.run(["convert", p, "-crop", f"{w.width}x{w.height}+{w.x}+{H - w.y - w.height}", "+repage",
                    os.path.join(OUT, name + ".png")])


def by_name(prefix):
    return next(o for o in bpy.context.scene.objects if (o.get("fr_name") or "").startswith(prefix))


def redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    bpy.context.preferences.view.ui_scale = SCALE
    bpy.context.preferences.system.use_region_overlap = False
    win = view3d()[0]
    win.event_simulate(type="ESC", value="PRESS", x=900, y=600)
    win.event_simulate(type="ESC", value="RELEASE", x=900, y=600)
    setup_window.register()
    bpy.context.window_manager.fr_wiz_kind = WIZ
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
    for o in bpy.context.scene.objects:
        o.select_set(o.type == "MESH" and not o.name.startswith("FR "))
    with override():
        bpy.ops.view3d.view_selected()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    return 1.0


@step
def s_window():
    with override():
        bpy.ops.fresing.setup_window(width=int(330 * SCALE), height=int(390 * SCALE))
    return 2.5


def make_step(k):
    def s_set():
        wm = bpy.context.window_manager
        wm.fr_wiz_step = k
        sc = bpy.context.scene
        for o in bpy.context.selected_objects:
            o.select_set(False)
        name = None
        if WIZ == "CNC" and k == 2:
            name = "STOCK"
        if WIZ == "MECH" and k == 1:
            name = "LIFT.BASE"
        if WIZ == "MECH" and k >= 2:
            sc.fresing.mech_kind = "SCISSOR"
            if k == 1 or k >= 2:
                try:
                    sc.fresing.mech_base = by_name("LIFT.BASE")
                except Exception:
                    log("base", traceback.format_exc())
            for o in sc.objects:
                n = o.get("fr_name") or ""
                if n.startswith("LIFT.ARM.") and n.count(".") == 3 or n == "LIFT.PLATFORM.ASM":
                    o.select_set(True)
                    bpy.context.view_layer.objects.active = o
        if name:
            try:
                o = by_name(name)
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
            except StopIteration:
                log("no part", name)
        if WIZ == "MECH" and k == 0:
            sc.fresing.mech_kind = "SCISSOR"
        redraw()
        return 1.5

    def s_shot():
        p = shot(f"{WIZ.lower()}_full_{k + 1}")
        wm = bpy.context.window_manager
        if len(wm.windows) > 1:
            crop_window(p, wm.windows[-1], f"{WIZ.lower()}_step{k + 1}")
        return 0.3
    s_set.__name__, s_shot.__name__ = f"set{k}", f"shot{k}"
    STEPS.extend([s_set, s_shot])


for _k in range(len(setup_window.WIZARDS[WIZ][1])):
    make_step(_k)


@step
def s_popover():
    """The same content as a popover over the 3D view (for the comparison picture)."""
    wm = bpy.context.window_manager
    if len(wm.windows) > 1:
        with bpy.context.temp_override(window=wm.windows[-1]):
            bpy.ops.wm.window_close()
    wm.fr_wiz_step = 0
    win, area, region = view3d()
    x, y = region.x + region.width * 0.18, region.y + region.height * 0.8
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x), y=int(y))
    with override():
        bpy.ops.wm.call_panel(name="FRESING_PT_setup_pop", keep_open=True)
    return 1.5


@step
def s_popover_shot():
    shot(f"{WIZ.lower()}_popover_full")
    win = view3d()[0]
    win.event_simulate(type="ESC", value="PRESS", x=600, y=600)
    win.event_simulate(type="ESC", value="RELEASE", x=600, y=600)
    return 0.5


@step
def s_quit():
    bpy.ops.wm.quit_blender()


_i = [0]
_w = [0]


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
        _w[0] += 1
        if _w[0] > 180:
            _i[0] += 1
        return 1.0
    _i[0] += 1
    return max(r or 0.0, 0.05)


bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
