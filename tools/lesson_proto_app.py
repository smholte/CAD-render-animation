"""Task 0123 study – the lesson prototype in the real app (branch task/0123-learning-study only).

Build it yourself on the crane's step 2 (the light look): the button glows, the script clicks where the glow says the
button is (as a user would), the lesson sees it and goes on. Then Show me on steps 3, 4 and 5 (rotate joint, the
trolley's stacked slide joint, a camera), Back once, the card's More, and the costs.

    BLENDER_USER_RESOURCES=~/fr_user LESSON_OUT=/tmp/lesson xvfb-run -a -s "-screen 0 1600x1000x24" \
        blender -p 0 0 1600 1000 --app-template fresing_render --enable-event-simulate --python tools/lesson_proto_app.py

The extension in ~/fr_user must be this branch's (tools/web_install_app.py). Output: $LESSON_OUT/lesson.log + pictures.
"""

import importlib
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("LESSON_OUT", "/tmp/lesson")
os.makedirs(OUT, exist_ok=True)
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
LOG = open(os.path.join(OUT, "lesson.log"), "w")
RESULT = {"fail": 0}


def log(*a):
    m = " ".join(str(x) for x in a)
    print("[LESSON]", m, flush=True)
    LOG.write(m + "\n")
    LOG.flush()


def check(cond, what):
    log(("OK   " if cond else "FAIL ") + what)
    if not cond:
        RESULT["fail"] += 1


def pkg():
    import addon_utils
    return next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))


def mod(n):
    return importlib.import_module(pkg() + "." + n)


def areas():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return win, area, next(r for r in area.regions if r.type == "WINDOW"), next(r for r in area.regions if r.type == "UI")


def shot(name, side_only=False):
    win, area, region, sb = areas()
    full = os.path.join(OUT, "screen.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    if side_only:
        x, w, h = sb.x, sb.width, sb.height
        y = win.height - (sb.y + sb.height)
    else:
        x, w = area.x, area.width
        y, h = win.height - (area.y + area.height), area.height
    subprocess.run(["convert", full, "-crop", f"{w}x{h}+{x}+{y}", "+repage", "-resize", "900x900>",
                    "-quality", "80", os.path.join(OUT, name)], check=False)
    log("picture", name)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


L = {}


@step
def s_esc():
    win, area, region, sb = areas()
    win.event_simulate(type="ESC", value="PRESS", x=700, y=500)
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    return 1.0


@step
def s_import():
    win, area, region, sb = areas()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        log("import", bpy.ops.fresing.import_step(filepath=CRANE, quality="draft"))
    return 1.0


@step
def s_wait():
    return "wait" if bpy.context.scene.fresing.model_count == 0 else 1.0


@step
def s_viewport_cost_before():
    win, area, region, sb = areas()
    L["les"] = mod("blender.lesson")
    L["les"].register()
    bpy.ops.fresing.light_look(look="WHITE")          # "Product studio" is what the lesson asks for
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=30)
        L["view_before"] = (time.perf_counter() - t) / 30
    return 0.5


# ----- Build it yourself: step 2, the light look -----

@step
def s_build_start():
    L["les"].start(bpy.context.scene, "crane", "BUILD")
    S = L["les"]._S
    check(S["step"] == 1, f"Build it yourself starts at the first step not done: step {S['step'] + 1} (2 expected)")
    return 2.0


@step
def s_build_point():
    S = L["les"]._S
    check(S["found"] is not None, f"the glowing button found in the side panel's pixels: {S['found']}")
    shot("1_build_point.jpg")
    shot("1_build_point_side.jpg", side_only=True)
    return 0.3


@step
def s_build_click():
    S = L["les"]._S
    win, area, region, sb = areas()
    x0, y0, x1, y1 = S["found"]
    x, y = sb.x + x1 + 30, sb.y + (y0 + y1) // 2            # just right of the marker: on the button
    log("button from x", x0, "to", S.get("found_right"), "in the side panel")
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    L["t_click"] = time.time()
    return 0.6


@step
def s_build_seen():
    S = L["les"]._S
    if S.get("seen_at") is None and time.time() - L["t_click"] < 8.0:
        return "wait"
    seen = S.get("seen_at")
    from_core = mod("core.studio").look_matches("PRODUCT", bpy.context.scene.fresing)
    check(from_core, "the click on the glowing place pressed 'Product studio'")
    check(seen is not None, "the lesson saw the click" + (f" {seen - L['t_click']:.2f} s after it" if seen else "")
          + f" ({S.get('ticks', 0)} ticks of the lesson's timer so far)")
    shot("2_build_done.jpg")
    return 1.8


@step
def s_build_next():
    S = L["les"]._S
    check(S["step"] == 2, f"…and went on by itself to step {S['step'] + 1} (3 expected)")
    L["les"].stop()
    return 0.5


# ----- Show me: steps 3, 4, 5 -----

@step
def s_show_start():
    L["les"].start(bpy.context.scene, "crane", "SHOW")
    L["les"]._S["more"] = True                          # the card with More open
    return 0.8


@step
def s_show3_point():
    S = L["les"]._S
    if S["found"] is None and S["phase"] == "point" and time.time() - L.setdefault("t3", time.time()) < 8:
        return "wait"                               # the side panel is still scrolling to the button
    seq = [ph for _t, mode, k, ph in S["history"] if mode == "SHOW" and k == 2]
    check(S["step"] == 2 and seq[:1] == ["point"], f"Show me points at step {S['step'] + 1} first: {seq}")
    check(S["found"] is not None, f"'Add rotate joint' glows: {S['found']}")
    shot("3_show_joint_point.jpg")
    return 2.0


@step
def s_show3_done():
    S = L["les"]._S
    if S["phase"] != "done" and time.time() - L.setdefault("t3d", time.time()) < 6:
        return "wait"
    log(f"Show me did the step {S['t_phase'] - (S.get('target_seen') or S['t_phase']):.2f} s after the glow showed;"
        f" history {[(round(t - S['history'][0][0], 2), m, k + 1, ph) for t, m, k, ph in S['history']]}")
    sc = bpy.context.scene
    check(S["phase"] == "done", "after the glow was seen, the app made the joint itself")
    check(mod("blender.lesson_crane")._joint_on(sc, "BOOM.ASM", "ROTATE") is not None, "the boom has its joint")
    shot("4_show_joint_done.jpg")
    return 1.8


@step
def s_show4():
    bpy.ops.fresing.lesson_next()
    return 0.8


@step
def s_show4_point():
    S = L["les"]._S
    check(S["step"] == 3 and S["found"] is not None, f"step 4: 'Add slide joint' glows: {S['found']}")
    shot("5_show_trolley_point.jpg")
    return 1.8


@step
def s_show5():
    sc = bpy.context.scene
    j = mod("blender.lesson_crane")._joint_on(sc, "TROLLEY.ASM", "SLIDE")
    check(j is not None, "the trolley's slide joint was made (on top of the boom's)")
    bpy.ops.fresing.lesson_next()
    return 0.8


@step
def s_show5_point():
    return 1.0


@step
def s_show5_point2():
    S = L["les"]._S
    if S["found"] is None and S["phase"] == "point" and time.time() - L.setdefault("t5", time.time()) < 8:
        return "wait"
    check(S["step"] == 4, f"step 5 (camera): found button {S['found']}, header {S['found_header']}, "
                          f"scrolled {S['scrolls']} pages")
    shot("6_show_camera_point.jpg")
    shot("6_show_camera_side.jpg", side_only=True)
    return 2.5


@step
def s_back():
    S = L["les"]._S
    check(S["phase"] == "done", "the camera was made")
    win, area, region, sb = areas()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        try:
            bpy.ops.fresing.lesson_back()
        except Exception as e:  # noqa: BLE001
            log("back:", e)
    return 1.0


@step
def s_back_seen():
    S = L["les"]._S
    cams = sum(1 for o in bpy.context.scene.objects if o.get("fr_camera"))
    log(f"after Back: step {S['step'] + 1}, phase {S['phase']}, cameras {cams}")
    return 0.5


@step
def s_closed_section():
    """Step 7 (animation +) lives in 6 Animation, which starts closed: its header glows instead."""
    les = L["les"]
    sc = bpy.context.scene
    les.do_step(sc)                                 # the camera again (Back took it away)
    les.next_step(sc)
    les.do_step(sc)                                 # step 6: the saved scene
    les._S["mode"] = "BUILD"                        # wait at step 7, do not do it
    les.next_step(sc)
    L["t7"] = time.time()
    return 0.5


@step
def s_closed_seen():
    S = L["les"]._S
    if S["found_header"] is None and time.time() - L["t7"] < 10:
        return "wait"
    check(S["step"] == 6 and S["found"] is None and S["found_header"] is not None,
          f"step 7: 6 Animation is closed, its header glows: {S['found_header']} (button {S['found']})")
    win, area, region, sb = areas()
    log("scrolls", S["scrolls"], "view top", sb.view2d.region_to_view(0, sb.height), "bottom",
        sb.view2d.region_to_view(0, 0), "header marker found", S["found_header"])
    shot("7_closed_section_side.jpg", side_only=True)
    return 0.5


@step
def s_costs():
    S = L["les"]._S
    st = S["stats"]
    win, area, region, sb = areas()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=30)
        during = (time.perf_counter() - t) / 30
    log(f"side panel: {st['draws']} wrapped panel draws, {1000 * st['draw_s'] / max(1, st['draws']):.3f} ms each;"
        f" pixel search {st['reads']} times, {1000 * st['read_s'] / max(1, st['reads']):.2f} ms each "
        f"(side panel {sb.width}x{sb.height})")
    log(f"3D view redraw: {1000 * L['view_before']:.2f} ms without a lesson, {1000 * during:.2f} ms with part glow "
        f"and card ({region.width}x{region.height})")
    log("notes:", S.get("note") or "none")
    return 0.5


@step
def s_quit():
    log("FAILED CHECKS:", RESULT["fail"])
    L["les"].stop()
    LOG.close()
    bpy.ops.wm.quit_blender()


_i = [0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    try:
        r = STEPS[_i[0]]()
    except Exception:
        log("ERROR in", STEPS[_i[0]].__name__, traceback.format_exc())
        RESULT["fail"] += 1
        r = 0.5
    if r == "wait":
        return 0.1
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("LESSON_SCALE", "1.0"))
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
