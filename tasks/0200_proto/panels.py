"""Task 0200: side-panel heights per section, and pictures of the layout prototypes (real app, xvfb).

    P_MODE=heights P_SCALE=1.0|1.5 P_OPEN=0|1 ...   heights of every section as it starts (P_OPEN=0) or with every
                                                     sub-panel and fold open (P_OPEN=1, also FRESING_UI_OPEN_FOLDS=1)
    P_MODE=layouts P_SCALE=1.5 ...                   pictures of layouts A, B, C, T and Ctrl+click on a header
Run like the other scripts here (blender --app-template fresing_render --enable-event-simulate --python ...).
Output: $P_OUT (default /tmp/panels0200): panels.log (lines "HEIGHT ..."), pictures.
"""
import os
import subprocess
import sys
import traceback

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import layouts  # noqa: E402

MODE = os.environ.get("P_MODE", "heights")
SCALE = float(os.environ.get("P_SCALE", "1.0"))
OPEN = os.environ.get("P_OPEN") == "1"
OUT = os.environ.get("P_OUT", "/tmp/panels0200")
os.makedirs(OUT, exist_ok=True)
CRANE = os.path.join(HERE, "..", "..", "fresing_render", "data", "test_crane_a.step")
LOG = open(os.path.join(OUT, f"panels_{MODE}_{SCALE}_{int(OPEN)}.log"), "w")


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[PANELS]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def areas():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sb = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sb


def override(rtype="WINDOW"):
    win, area, region, sb = areas()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area,
                                     region=sb if rtype == "UI" else region)


def shot(name):
    p = os.path.join(OUT, name + ".png")
    subprocess.run(["import", "-window", "root", p], check=False)
    return p


def crop(p, x, y_top, w, h, name):
    subprocess.run(["convert", p, "-crop", f"{w}x{h}+{x}+{y_top}", "+repage", os.path.join(OUT, name + ".png")])


def sidebar_crop(p, name, h=None):
    win, area, region, sb = areas()
    top = win.height - (sb.y + sb.height)
    crop(p, sb.x, top, sb.width, h or sb.height, name)


def open_all_panels():
    for name in [n for n in dir(bpy.types) if n.startswith("FRESING_PT_")]:
        cls = getattr(bpy.types, name)
        if "DEFAULT_CLOSED" in getattr(cls, "bl_options", set()):
            try:
                bpy.utils.unregister_class(cls)
                cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
                bpy.utils.register_class(cls)
            except Exception:
                log("reopen failed", name)


def redraw():
    for w in bpy.context.window_manager.windows:
        for a in w.screen.areas:
            a.tag_redraw()


def scroll(down):
    with override("UI"):
        for _ in range(int(os.environ.get("P_SCROLLS", "60"))):
            if down:
                bpy.ops.view2d.scroll_down(deltax=0, deltay=400, page=False)
            else:
                bpy.ops.view2d.scroll_up(deltax=0, deltay=400, page=False)
    redraw()


def wiggle():
    win, area, region, sb = areas()
    for k in range(6):
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=sb.x + 40 + k, y=sb.y + 300 + 30 * k)
    redraw()


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    bpy.context.preferences.view.ui_scale = SCALE
    bpy.context.preferences.system.use_region_overlap = False
    win = areas()[0]
    win.event_simulate(type="ESC", value="PRESS", x=900, y=600)
    win.event_simulate(type="ESC", value="RELEASE", x=900, y=600)
    if OPEN:
        open_all_panels()
    return 1.0


@step
def s_import():
    with override():
        bpy.ops.fresing.import_step(filepath=os.path.abspath(CRANE), quality="normal")
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    if MODE == "layouts":
        a = bpy.context.scene.fresing.animations.add()           # an animation, so its video settings show
        a.name = "Luff and travel"
    win, area, region, sb = areas()
    log("sidebar", sb.width, sb.height, "scale", SCALE, "open", OPEN)
    return 2.0


# ------------------------------------------------------------------------------------------------ heights
def height_steps():
    if MODE != "heights":
        return
    items = [("ALL", "all sections")] + [(str(i + 1), layouts.SECTIONS[i]) for i in range(7)]

    @step
    def s_gate():
        bpy.types.WindowManager.fr_section = bpy.props.EnumProperty(
            items=[(k, k, "") for k, _ in items], default="ALL")
        layouts.regate()
        return 1.0

    for key, label in items:
        def s_set(key=key):
            bpy.context.window_manager.fr_section = key
            scroll(False)
            wiggle()
            return 1.5

        def s_down():
            wiggle()
            scroll(True)
            return 1.0

        def s_measure(key=key, label=label):
            win, area, region, sb = areas()
            scroll(True)
            vy = -sb.view2d.region_to_view(0, 0)[1]          # the region's bottom, from the content's top
            log("view y", vy)
            if vy > sb.height + 2:
                total, fits = vy, "scrolls"
            else:                                            # it fits: where the drawn content ends
                p = shot(f"h_{key}_{SCALE}_{int(OPEN)}")
                sidebar_crop(p, f"hs_{key}_{SCALE}_{int(OPEN)}")
                total = -1                                   # measured afterwards from the picture (heights.py)
                fits = "fits"
            log(f"HEIGHT scale={SCALE} open={int(OPEN)} section={key} px={int(total)} sidebar={sb.height} "
                f"screens={total / sb.height:.1f} {fits} ({label})")
            return 0.3
        s_set.__name__, s_down.__name__, s_measure.__name__ = f"set{key}", f"down{key}", f"measure{key}"
        STEPS.extend([s_set, s_down, s_measure])


height_steps()


# ------------------------------------------------------------------------------------------------ layout pictures
def layout_steps():
    if MODE != "layouts":
        return

    @step
    def s_before():
        wiggle()
        p = shot("L0_before")
        sidebar_crop(p, "L0_sidebar_before")
        win, area, region, sb = areas()
        hdr = next(r for r in area.regions if r.type == "HEADER")
        crop(p, hdr.x, win.height - (hdr.y + hdr.height), hdr.width, hdr.height, "L0_header_before")
        return 0.3

    @step
    def s_make_on():
        layouts.enable_make()
        redraw()
        wiggle()
        return 1.5

    @step
    def s_make_shot():
        wiggle()
        p = shot("LA_make")
        sidebar_crop(p, "LA_sidebar", h=int(330 * SCALE))
        win, area, region, sb = areas()
        hdr = next(r for r in area.regions if r.type == "HEADER")
        crop(p, hdr.x, win.height - (hdr.y + hdr.height), hdr.width, hdr.height, "LB_header")
        crop(p, 0, 0, win.width, int(26 * SCALE), "LC_topbar")
        return 0.3

    def popover_of(panel, name, at=(0.62, 0.85), xy=None):
        def s_open():
            win, area, region, sb = areas()
            x, y = xy or (region.x + region.width * at[0], region.y + region.height * at[1])
            win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=int(x), y=int(y))
            with override():
                try:
                    bpy.ops.wm.call_panel(name=panel, keep_open=True)
                    log("POPOVER", panel, "opened")
                except Exception as exc:
                    log("POPOVER", panel, "FAILED", exc)
            return 0.35                          # shot before a tooltip shows

        def s_shot():
            shot(name)
            win = areas()[0]
            win.event_simulate(type="ESC", value="PRESS", x=600, y=600)
            win.event_simulate(type="ESC", value="RELEASE", x=600, y=600)
            return 0.8
        s_open.__name__, s_shot.__name__ = "open_" + name, "shot_" + name
        STEPS.extend([s_open, s_shot])

    popover_of("FRESING_PT_turntable", "LA_pop_turntable", at=(0.45, 0.8))
    popover_of("FRESING_PT_output", "LA_pop_still", at=(0.45, 0.8))
    popover_of("FRESING_PT_make_anim", "LA_pop_anim", at=(0.45, 0.8))
    popover_of("FRESING_PT_web3d", "LA_pop_web", at=(0.45, 0.95))
    popover_of("FRESING_PT_make_header", "LB_pop", xy=(1514, 1200 - 58))

    @step
    def s_menu():
        win, area, region, sb = areas()
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=402, y=win.height - 18)
        with override():
            bpy.ops.wm.call_menu(name="FRESING_MT_make")
        return 1.5

    @step
    def s_menu_shot():
        shot("LC_menu")
        win = areas()[0]
        win.event_simulate(type="ESC", value="PRESS", x=600, y=600)
        win.event_simulate(type="ESC", value="RELEASE", x=600, y=600)
        return 0.8

    @step
    def s_tabs():
        layouts.enable_tabs()
        bpy.context.window_manager.fr_section = "5"
        redraw()
        wiggle()
        return 1.5

    @step
    def s_tabs_shot():
        wiggle()
        p = shot("LT_tabs5")
        sidebar_crop(p, "LT_sidebar5")
        bpy.context.window_manager.fr_section = "ALL"
        redraw()
        return 1.0

    @step
    def s_ctrl_click():
        """Blender's own Ctrl+click on a section header: does it fold all the others?"""
        wiggle()
        p = shot("LK_before")
        sidebar_crop(p, "LK_sidebar_before")
        win, area, region, sb = areas()
        # the first section header under the tab row: "1 Import"
        y = sb.y + sb.height - int(52 * SCALE)
        x = sb.x + int(90 * SCALE)
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y, ctrl=True)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y, ctrl=True)
        return 2.0

    @step
    def s_ctrl_shot():
        wiggle()
        p = shot("LK_after")
        sidebar_crop(p, "LK_sidebar_after")
        return 0.3


    @step
    def s_ctrl_click2():
        """Then Ctrl+click on '4 Motion' (5th row under the Make panel): only that section opens?"""
        win, area, region, sb = areas()
        y = sb.y + sb.height - int(461 * SCALE / 1.5)
        x = sb.x + int(90 * SCALE)
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
        win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y, ctrl=True)
        win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y, ctrl=True)
        return 2.0

    @step
    def s_ctrl_shot2():
        wiggle()
        p = shot("LK_after2")
        sidebar_crop(p, "LK_sidebar_after2")
        return 0.3


layout_steps()


@step
def s_quit():
    LOG.close()
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
