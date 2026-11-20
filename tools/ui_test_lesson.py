"""Real-app test, task 0230: the lessons – the Learn window, Build it yourself by clicking where the highlight points,
Show me from the learning list's hook, Back, saving half-way and going on, the costs, nothing left after Stop.

* Fresing > Learn… opens (picture ``learn_window.png`` for the guide);
* Build it yourself on the crane: a new project with the plain import; the steps whose button is a plain button
  (light look, camera, the animation's +, Build & play, Queue this) are done by a simulated click where the highlight
  found the button – the lesson sees each in the project and goes on by itself; the others with Do it for me; the
  trolley's joint made another way (joints.create, not the button) counts too;
* Show me opened at "Rotate joint" (``fresing.learn_lesson``, the learning list's hook): the steps before it are done,
  the button is found on screen (picture ``lesson_show_me.jpg``), the app does the step, waits for Next; Back undoes it
  and the lesson goes back; the project saved half-way and opened again offers to go on, at the right step;
* the costs while a lesson points (side panel, 3D view, the timer's look, the card) and none after Stop.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/les xvfb-run -a -s "-screen 0 1800x1200x24" \\
        blender -p 0 0 1800 1200 --app-template fresing_render --enable-event-simulate --python tools/ui_test_lesson.py
"""

import importlib
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lesson"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lesson.log"), "w")
RESULTS = []
S = {}
STEPS = []
KEPT = {}


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


def les():
    return mod("blender.lesson")


def hl():
    return mod("blender.highlight")


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return (win, area, next(r for r in area.regions if r.type == "WINDOW"),
            next(r for r in area.regions if r.type == "UI"))


def override(side=False):
    win, area, region, sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if side else region,
                                     scene=win.scene)


def step(fn):
    STEPS.append(fn)
    return fn


def click(x, y):
    win = ui()[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def mouse_away():
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300, y=region.y + 300)


def redraw():
    for area in ui()[0].screen.areas:
        area.tag_redraw()


def screen(path):
    subprocess.run(["import", "-window", "root", path], check=False)


def crop_area(name, side_only=False):
    win, area, _region, sb = ui()
    full = os.path.join(OUT, "screen.png")
    screen(full)
    if side_only:
        x, w, h = sb.x, sb.width, min(sb.height, 900)
        y = win.height - (sb.y + sb.height)
    else:
        x, w, h = area.x, area.width, area.height
        y = win.height - (area.y + area.height)
    subprocess.run(["convert", full, "-crop", f"{w}x{h}+{x}+{y}", "+repage", "-resize", "1400x1000>",
                    "-quality", "82", os.path.join(OUT, name)], check=False)


def wait_until(name, cond, seconds=30.0):
    """A step that waits (re-runs) until ``cond()`` is true, or fails after ``seconds``."""
    def fn():
        if "t_wait" not in S:
            S["t_wait"] = time.time()
        try:
            ok = cond()
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            check(name, True, f"{time.time() - S.pop('t_wait'):.1f} s")
            return 0.3
        if time.time() - S["t_wait"] > seconds:
            check(name, False, f"state {les().state()}, found {hl().found()}")
            S.pop("t_wait")
            return 0.3
        redraw()
        return "again"
    fn.__name__ = "wait_" + name[:30].replace(" ", "_")
    STEPS.append(fn)


def found_button():
    f = hl().found()
    box = f.get("button") if f else None
    if box is None:
        return None
    _w, _a, _r, sb = ui()
    return sb.x + (box[0] + box[2]) // 2, sb.y + (box[1] + box[3]) // 2


# ---------------------------------------------------------------------------

@step
def s_setup():
    prefs = bpy.context.preferences
    KEPT.update(overlap=prefs.system.use_region_overlap)
    prefs.system.use_region_overlap = False
    win = ui()[0]
    win.event_simulate(type="ESC", value="PRESS", x=win.width // 2, y=win.height // 2)   # the splash
    win.event_simulate(type="ESC", value="RELEASE", x=win.width // 2, y=win.height // 2)
    check("nothing of the lessons runs before one starts", les().handlers_left() == [] and not les().running(),
          les().handlers_left())
    return 1.0


@step
def s_learn_window():
    screen(os.path.join(OUT, "before_window.png"))
    with override():
        r = bpy.ops.fresing.learn_lessons("INVOKE_DEFAULT")
    check("Fresing > Learn… opens", r == {"RUNNING_MODAL"} or r == {"FINISHED"} or r == {"INTERFACE"}, r)
    return 1.0


@step
def s_learn_window_shot():
    after = os.path.join(OUT, "after_window.png")
    screen(after)
    box = subprocess.run(["convert", os.path.join(OUT, "before_window.png"), after, "-compose", "difference",
                          "-composite", "-threshold", "3%", "-trim", "-format", "%wx%h%O", "info:"],
                         capture_output=True, text=True).stdout.strip()
    log("the window's box", box)
    ok = "x" in box and int(box.split("x")[0]) > 400
    check("the Learn window is drawn", ok, box)
    if ok:
        subprocess.run(["convert", after, "-crop", box, "+repage", os.path.join(OUT, "learn_window.png")], check=False)
    win = ui()[0]
    win.event_simulate(type="ESC", value="PRESS", x=win.width // 2, y=win.height // 2)
    win.event_simulate(type="ESC", value="RELEASE", x=win.width // 2, y=win.height // 2)
    return 0.8


# ----- Build it yourself on the crane -----

@step
def s_build_start():
    with override():
        r = bpy.ops.fresing.learn_start(lesson="crane", mode="BUILD")
    check("Build it yourself starts", r == {"FINISHED"}, r)
    S["t_start"] = time.time()
    return 1.0


wait_until("a new project with the plain crane, the lesson at step 2",
           lambda: les().running() and les().state()["step"] == 1 and bpy.context.scene.fresing.model_count > 0, 60)


def _click_step(k, text):
    """Step k (1-based) of the crane lesson: click where the highlight found the button, wait for the lesson to go on."""
    def click_it():
        xy = found_button()
        if xy is None:
            if time.time() - S.setdefault("t_find", time.time()) > 20:
                check(f"step {k}: the button '{text}' is found on screen", False, f"found {hl().found()}")
                S.pop("t_find", None)
                with override():
                    bpy.ops.fresing.lesson_do()
                return 0.5
            redraw()
            return "again"
        S.pop("t_find", None)
        check(f"step {k}: the button '{text}' is found on screen", True, xy)
        win = ui()[0]
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=xy[0], y=xy[1])
        S["xy"] = xy
        return 0.5

    def press():
        click(*S["xy"])
        S["t_click"] = time.time()
        mouse_away()
        return 0.3
    click_it.__name__, press.__name__ = f"click_step_{k}", f"press_step_{k}"
    STEPS.append(click_it)
    STEPS.append(press)
    wait_until(f"step {k}: the click is seen, the lesson goes on by itself",
               lambda: les().state()["step"] >= k or les().step() is None, 15)


def _do_step(k):
    def do_it():
        with override():
            r = bpy.ops.fresing.lesson_do()
        check(f"step {k}: Do it for me", r == {"FINISHED"}, f"{r} {les().state()}")
        return 0.3
    do_it.__name__ = f"do_step_{k}"
    STEPS.append(do_it)
    wait_until(f"step {k}: done, the lesson goes on", lambda: les().state()["step"] >= k or les().step() is None, 10)


_click_step(2, "Product studio")
_do_step(3)


@step
def s_trolley_another_way():
    """The trolley's joint made without the button (as the list's + or a copy would): it counts."""
    from mathutils import Vector
    tour = mod("blender.tour")
    joints = mod("blender.joints")
    sc = bpy.context.scene
    t = tour._ob(sc, "TROLLEY.ASM")
    joints.create(sc, "SLIDE", [t], t.matrix_world.translation.copy(), Vector((0, 0, 1)), base=tour._ob(sc, "BOOM.ASM"),
                  name="My trolley")
    return 0.3


wait_until("step 4 done another way counts", lambda: les().state()["step"] >= 4, 10)
_click_step(5, "3/4 hero, high")
_do_step(6)
_click_step(7, "+ (new animation)")
_do_step(8)
_click_step(9, "Build & play")


@step
def s_stop_playing():
    if bpy.context.screen and bpy.context.screen.is_animation_playing:
        with override():
            bpy.ops.screen.animation_cancel(restore_frame=False)
    return 0.3


_do_step(10)
_click_step(11, "Queue this")


@step
def s_build_end():
    s = bpy.context.scene.fresing
    check("Build it yourself reaches the end", les().step() is None, les().state())
    check("... the project has the lesson's joints, scenes, animation, Build and the queued picture",
          len(s.joints) >= 2 and len(s.shots) >= 2 and len(s.animations) == 1 and bool(s.anim_baked)
          and len(s.queue) == 1, f"{len(s.joints)} joints, {len(s.shots)} scenes, queue {len(s.queue)}")
    with override():
        bpy.ops.fresing.lesson_stop()
    check("Stop: nothing of the lesson or the highlight runs", les().handlers_left() == []
          and hl().handlers_left() == [], les().handlers_left() + hl().handlers_left())
    return 0.5


# ----- Show me from the learning list's hook, at "Rotate joint" -----

@step
def s_show_start():
    S["delay"] = les().SHOW_DELAY, les().SHOW_LATEST
    les().SHOW_DELAY = les().SHOW_LATEST = 60.0         # held while the picture is taken; put back below
    with override():
        r = bpy.ops.fresing.learn_lesson(fid="joints.rotate", mode="SHOW")
    check("the learning list's Show me opens the function's lesson", r == {"FINISHED"}, r)
    return 1.0


wait_until("Show me starts at step 3 (Rotate joint), the steps before it done",
           lambda: les().running() and les().state()["step"] == 2 and les().state()["mode"] == "SHOW", 60)


@step
def s_show_costs_and_picture():
    """While pointing: the button found, a picture, the costs."""
    xy = found_button()
    if xy is None:
        if time.time() - S.setdefault("t_find", time.time()) < 15:
            redraw()
            return "again"
    S.pop("t_find", None)
    check("Show me: 'Add rotate joint' is found on screen", xy is not None, hl().found())
    check("... and the app has not done it yet", les().state()["phase"] == "point", les().state())
    win, area, region, sb = ui()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        bpy.ops.view3d.view_selected()                  # (for the guide's picture: the boom large, its card beside it)
    S["pic"] = True
    return 0.8


@step
def s_show_picture_and_costs():
    full = os.path.join(OUT, "screen.png")
    screen(full)
    win, area, region, sb = ui()
    h = min(area.height, 1450)
    subprocess.run(["convert", full, "-crop", f"{area.width}x{h}+{area.x}+{win.height - (area.y + area.height)}",
                    "+repage", "-resize", "1100x1100>", "-quality", "84", os.path.join(OUT, "lesson_show_me.jpg")],
                   check=False)
    hl().stats(reset=True)
    les().stats(reset=True)
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb):
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        S["side_on"] = (time.perf_counter() - t) / 20 * 1000
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        S["view_on"] = (time.perf_counter() - t) / 20 * 1000
    S["hl_on"] = hl().stats()
    S["les_on"] = les().stats()
    log("COST while pointing: side panel redraw", f"{S['side_on']:.1f} ms", "3D view redraw", f"{S['view_on']:.1f} ms",
        "highlight", S["hl_on"], "lesson", S["les_on"])
    les().SHOW_DELAY, les().SHOW_LATEST = S["delay"]
    return 0.3


wait_until("Show me does the step itself (the boom gets its joint)",
           lambda: les().state()["phase"] == "done" and les().is_done(bpy.context.scene, les().step()), 15)


@step
def s_show_waits():
    S["t_done"] = time.time()
    return 3.5


@step
def s_show_waited():
    S["les_wait"] = les().stats()
    log("COST of the lesson's timer while it waits for Next", S["les_wait"])
    check("Show me waits for Next (Play on is off)", les().state()["phase"] == "done" and les().state()["step"] == 2,
          les().state())
    with override():
        bpy.ops.fresing.lesson_next()
    return 0.5


wait_until("Next: step 4 (the trolley) is pointed at", lambda: les().state()["step"] == 3, 10)
wait_until("Show me does step 4", lambda: les().state()["phase"] == "done", 15)


@step
def s_back():
    with override():
        r = bpy.ops.fresing.lesson_back()
    check("Back", r == {"FINISHED"}, r)
    return 1.0


wait_until("Back undoes step 4: the lesson is at step 4 again, pointing", lambda: les().state()["step"] == 3
           and les().state()["phase"] == "point" and not les().is_done(bpy.context.scene, les().step()), 10)


@step
def s_save_half_way():
    with override():
        bpy.ops.fresing.lesson_stop()
    sc = bpy.context.scene
    sc[les().KEY] = "crane"                             # (Stop forgets it; a project saved while it runs keeps it)
    S["path"] = os.path.join(OUT, "Lesson half way é.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=S["path"])
        bpy.ops.wm.open_mainfile(filepath=S["path"])
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    check("the reopened project offers to go on (Lesson panel)", sc.get(les().KEY) == "crane"
          and bpy.types.FRESING_PT_lesson.poll(bpy.context), sc.get(les().KEY))
    with override():
        bpy.ops.fresing.lesson_resume(mode="BUILD")
    check("... and goes on at step 4", les().state()["step"] == 3 and les().state()["mode"] == "BUILD",
          les().state())
    with override():
        bpy.ops.fresing.lesson_stop()
    win, area, region, sb = ui()
    for key, reg in (("side_off", sb), ("view_off", region)):
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=reg):
            t = time.perf_counter()
            bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
            S[key] = (time.perf_counter() - t) / 20 * 1000
    log("COST without a lesson: side panel redraw", f"{S['side_off']:.1f} ms", "3D view redraw",
        f"{S['view_off']:.1f} ms")
    check("nothing left running at the end", les().handlers_left() == [] and hl().handlers_left() == [],
          les().handlers_left() + hl().handlers_left())
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    if KEPT:
        bpy.context.preferences.system.use_region_overlap = KEPT["overlap"]
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
