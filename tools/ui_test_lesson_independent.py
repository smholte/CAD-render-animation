"""Real-app test, task 0230's independent tester: trying to break a running lesson in the real app.

* Show me on the crane (fast timing): the side panel closed while it points, the side panel on another tab;
* Ctrl+Z (a simulated key) and ``ed.undo`` / ``ed.redo`` right after the app's own Build & play (CLAUDE.md 8: undo
  after a Build called from a script crashed Blender 5.2.3) – twice, then redo, then the app builds again and undo;
* Blender's right-hand column shown / hidden while a lesson points; a lesson started with the column shown;
* the Client view switched on while Show me runs;
* another project opened while a lesson runs: nothing of the lesson or the highlight stays behind.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/lesi xvfb-run -a -s "-screen 0 1800x1200x24" \\
        blender -p 0 0 1800 1200 --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_lesson_independent.py
"""

import importlib
import os
import time
import traceback

import bpy

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lesson_independent"))
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lesson_independent.log"), "w")
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
    area = max((a for a in win.screen.areas if a.type == "VIEW_3D"), key=lambda a: a.width * a.height)
    return (win, area, next(r for r in area.regions if r.type == "WINDOW"),
            next(r for r in area.regions if r.type == "UI"))


def override(side=False):
    win, area, region, sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=sb if side else region,
                                     scene=win.scene)


def step(fn):
    STEPS.append(fn)
    return fn


def redraw():
    for area in ui()[0].screen.areas:
        area.tag_redraw()


def wait_until(name, cond, seconds=30.0):
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


def fast(on=True):
    L = les()
    if "timing" not in S:
        S["timing"] = (L.SHOW_DELAY, L.SHOW_LATEST)
    if on:
        L.SHOW_DELAY, L.SHOW_LATEST = 0.3, 1.0
    else:                                           # hold: the app does not do the step by itself
        L.SHOW_DELAY = L.SHOW_LATEST = 600.0


def joints_n():
    return len(bpy.context.scene.fresing.joints)


# ---------------------------------------------------------------------------

@step
def s_setup():
    prefs = bpy.context.preferences
    KEPT.update(overlap=prefs.system.use_region_overlap)
    prefs.system.use_region_overlap = False
    win = ui()[0]
    win.event_simulate(type="ESC", value="PRESS", x=win.width // 2, y=win.height // 2)
    win.event_simulate(type="ESC", value="RELEASE", x=win.width // 2, y=win.height // 2)
    return 1.0


@step
def s_show_start():
    fast(True)
    with override():
        r = bpy.ops.fresing.learn_start(lesson="crane", mode="SHOW")
    check("Show me starts", r == {"FINISHED"}, r)
    return 1.0


wait_until("Show me runs at step 2", lambda: les().running() and les().state()["step"] == 1, 60)
wait_until("Show me does step 2 (light look)", lambda: les().state()["phase"] == "done", 15)


@step
def s_next_2():
    with override():
        bpy.ops.fresing.lesson_next()
    return 0.3


wait_until("step 3 pointed", lambda: les().state()["step"] == 2 and les().state()["phase"] == "point", 10)


# ----- the side panel closed while Show me points -----

@step
def s_close_side_panel():
    fast(False)
    S["joints"] = joints_n()
    _w, area, _r, _sb = ui()
    area.spaces.active.show_region_ui = False         # N
    S["t_closed"] = time.time()
    fast(True)
    return 0.2


wait_until("side panel closed: Show me still does the step (after SHOW_LATEST)",
           lambda: les().state()["phase"] == "done" and joints_n() == S["joints"] + 1, 15)


@step
def s_next_3():
    with override():
        bpy.ops.fresing.lesson_next()
    return 0.6


wait_until("pointing at step 4 opens the side panel again", lambda: ui()[1].spaces.active.show_region_ui, 10)


# ----- the side panel on another tab -----

@step
def s_other_tab():
    _w, _area, _r, sb = ui()
    try:
        sb.active_panel_category = "View"
    except Exception as e:  # noqa: BLE001
        log("tab", e)
    S["tab_set"] = sb.active_panel_category
    return 0.2


wait_until("Show me does step 4 with the side panel on another tab", lambda: les().state()["phase"] == "done", 15)


@step
def s_next_4():
    log("tab while step 4 ran:", S.get("tab_set"))
    with override():
        bpy.ops.fresing.lesson_next()
    return 0.6


wait_until("pointing at step 5 shows the Fresing tab again", lambda: ui()[3].active_panel_category == "Fresing", 10)


def _next_until(k):
    """Next whenever a step is done, until the lesson points at step k (0-based)."""
    def fn():
        st = les().state()
        if st["step"] >= k:
            check(f"Show me reached step {k + 1}", st["step"] == k, st)
            return 0.3
        if time.time() - S.setdefault("t_until", time.time()) > 120:
            check(f"Show me reached step {k + 1}", False, st)
            return 0.3
        if st["phase"] == "done":
            with override():
                bpy.ops.fresing.lesson_next()
            # stop playback Build & play started (it would change the frame under the test)
            scr = bpy.context.window_manager.windows[0].screen
            if scr.is_animation_playing:
                with override():
                    bpy.ops.screen.animation_cancel(restore_frame=False)
        redraw()
        return "again"
    fn.__name__ = f"next_until_{k}"
    STEPS.append(fn)

    def clear():
        S.pop("t_until", None)
        return 0.1
    STEPS.append(clear)


_next_until(9)                                       # step 10 (explode) pointed: the app's Build was just done


@step
def s_hold_and_stop_play():
    fast(False)
    scr = bpy.context.window_manager.windows[0].screen
    if scr.is_animation_playing:
        with override():
            bpy.ops.screen.animation_cancel(restore_frame=False)
    S["baked"] = bool(bpy.context.scene.fresing.anim_baked)
    check("the app's Build & play is done", S["baked"])
    return 0.5


# ----- Ctrl+Z right after the app's Build -----

@step
def s_ctrl_z():
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="Z", value="PRESS", ctrl=True, x=x, y=y)
    win.event_simulate(type="Z", value="RELEASE", ctrl=True, x=x, y=y)
    return 1.5


@step
def s_after_ctrl_z():
    st = les().state()
    sc = bpy.context.scene
    check("Ctrl+Z after the app's Build: no crash, the lesson goes back to 'Build and play'",
          st["step"] == 8 and not sc.fresing.anim_baked, f"{st}, baked {sc.fresing.anim_baked}")
    check("... and waits (held timing: it does not build again by itself yet)", st["phase"] == "point", st)
    with override():
        try:
            bpy.ops.ed.undo()
        except RuntimeError as e:
            log("undo", e)
    return 1.0


@step
def s_after_second_undo():
    st = les().state()
    check("a second undo: the lesson at the joint step (step 8)", st["step"] == 7, st)
    for _ in range(2):
        with override():
            try:
                bpy.ops.ed.redo()
            except RuntimeError as e:
                log("redo", e)
    return 1.0


@step
def s_after_redo():
    st = les().state()
    sc = bpy.context.scene
    check("redo twice: back at step 10, the Build there again", st["step"] == 9 and bool(sc.fresing.anim_baked),
          f"{st}, baked {sc.fresing.anim_baked}")
    with override():
        try:
            bpy.ops.ed.undo()
        except RuntimeError as e:
            log("undo", e)
    return 1.0


@step
def s_let_it_build_again():
    st = les().state()
    check("undo once more: at Build and play", st["step"] == 8, st)
    fast(True)
    return 0.2


@step
def s_held_after_undo():
    """After Ctrl+Z Show me waits (task 0230, finding 7): it does not build again by itself; Next does."""
    st = les().state()
    check("after Ctrl+Z Show me waits for Next (nothing built again by itself)", st["phase"] == "point"
          and not bpy.context.scene.fresing.anim_baked, st)
    fast(False)     # Next builds at once; held, Show me does not go on to the next step before the undo below (a
    #               # run where it moved the crane apart first undid that instead of the Build: 0.2.224's branch)
    with override():
        bpy.ops.fresing.lesson_next()
    return 0.3


wait_until("Next: Show me builds again", lambda: les().state()["step"] >= 8
           and bool(bpy.context.scene.fresing.anim_baked), 20)


@step
def s_undo_after_rebuild():
    fast(False)
    scr = bpy.context.window_manager.windows[0].screen
    if scr.is_animation_playing:
        with override():
            bpy.ops.screen.animation_cancel(restore_frame=False)
    with override():
        try:
            bpy.ops.ed.undo()
        except RuntimeError as e:
            log("undo", e)
    return 1.0


@step
def s_after_undo_rebuild():
    st = les().state()
    check("undo after the app built again: no crash, at Build and play", st["step"] == 8, st)
    return 0.3


# ----- Blender's column shown / hidden while a lesson points -----

@step
def s_column_show():
    ed = mod("blender.editors")
    S["column_was"] = ed.chosen_shown()
    with override():
        r = bpy.ops.fresing.blender_editors()
    check("Show Blender's editors while a lesson points", r == {"FINISHED"}, r)
    return 1.5


@step
def s_column_shown():
    ed = mod("blender.editors")
    check("... shown, the lesson still running", ed.shown() and les().running(), f"{ed.shown()} {les().state()}")
    with override():
        bpy.ops.fresing.blender_editors()
    return 1.5


@step
def s_column_hidden():
    ed = mod("blender.editors")
    check("... hidden again, the lesson still running and pointing", not ed.shown() and les().running()
          and hl().active(), f"{ed.shown()} {les().state()}")
    return 0.3


# ----- the Client view while Show me runs -----

@step
def s_client_view():
    S["joints"] = joints_n()
    with override():
        r = bpy.ops.fresing.workspace_pick(name="Client view")
    check("Client view on while a lesson runs", r == {"FINISHED"}, r)
    with override():
        refused = not bpy.ops.fresing.lesson_next.poll()
    check("... Next is refused in the Client view (it would change the locked project)", refused)
    return 0.5


@step
def s_client_view_after():
    lock = mod("blender.lock")
    check("... the lock is on", lock.ON[0])
    with override():
        stop_ok = bpy.ops.fresing.lesson_stop.poll()
    check("... Stop the lesson still works in the Client view", stop_ok)
    fast(True)
    return 2.5


@step
def s_client_view_edits():
    sc = bpy.context.scene
    st = les().state()
    log("Client view: the lesson's state", st, "baked", sc.fresing.anim_baked)
    check("... Show me does not change the locked project", not (st["phase"] == "done" and st["step"] == 8)
          or not sc.fresing.anim_baked, f"{st}, baked {sc.fresing.anim_baked}")
    fast(False)
    with override():
        bpy.ops.fresing.workspace_pick(name="All functions")
    return 1.0


# ----- another project opened while a lesson runs -----

@step
def s_save_other():
    lesm = les()
    if not lesm.running():
        with override():
            bpy.ops.fresing.lesson_resume(mode="BUILD")
    S["other"] = os.path.join(OUT, "other project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=S["other"], copy=True)
    check("a lesson runs before another project opens", les().running(), les().state())
    with override():
        bpy.ops.wm.read_homefile(use_empty=False)
    return 1.5


@step
def s_after_open():
    check("another project opened: the lesson ended", not les().running(), les().state())
    check("... nothing of the lesson or the highlight is left", les().handlers_left() == []
          and hl().handlers_left() == [], les().handlers_left() + hl().handlers_left())
    return 0.3


# ----- a lesson started with Blender's column shown -----

@step
def s_column_then_start():
    with override():
        bpy.ops.fresing.blender_editors()          # shown
    return 1.0


@step
def s_start_with_column():
    with override():
        r = bpy.ops.fresing.learn_start(lesson="mill", mode="BUILD")
    check("Build it yourself (mill) starts with Blender's column shown", r == {"FINISHED"}, r)
    return 1.0


wait_until("the mill lesson runs, no crash", lambda: les().running() and les().state()["step"] == 1, 60)


@step
def s_mill_stop():
    ed = mod("blender.editors")
    log("column after the lesson's new project:", ed.shown(), "chosen", ed.chosen_shown())
    with override():
        bpy.ops.fresing.lesson_stop()
    if ed.chosen_shown() != S.get("column_was", False):
        with override():
            bpy.ops.fresing.blender_editors()
    check("Stop: nothing left", les().handlers_left() == [] and hl().handlers_left() == [],
          les().handlers_left() + hl().handlers_left())
    return 0.5


# ----- Play on, real timings: is every button seen before the app does its step? -----

SEEN = {}


def _watch():
    L = les()
    if not L.running():
        return None
    st = L.state()
    k = (L.current().id, st["step"])
    if st["phase"] == "point":
        SEEN.setdefault(k, {"seen": False, "done": False})
        if L._S["seen_at"] is not None:
            SEEN[k]["seen"] = True
    elif st["phase"] == "done" and k in SEEN:
        SEEN[k]["done"] = True
    scr = bpy.context.window_manager.windows[0].screen
    if scr.is_animation_playing:
        bpy.ops.screen.animation_cancel(restore_frame=False)
    return 0.05


def _play_on(lesson_id):
    @step
    def start():
        L = les()
        L.SHOW_DELAY, L.SHOW_LATEST = S["timing"]
        p = mod("blender.prefs").get()
        S["play_on_was"] = p.lesson_play_on
        p.lesson_play_on = True
        with override():
            r = bpy.ops.fresing.learn_start(lesson=lesson_id, mode="SHOW")
        check(f"Play on: Show me ({lesson_id}) starts", r == {"FINISHED"}, r)
        bpy.app.timers.register(_watch, first_interval=2.0, persistent=True)
        return 2.0
    start.__name__ = f"play_on_{lesson_id}"
    wait_until(f"Play on: the {lesson_id} lesson runs to its end by itself",
               lambda: les().running() and les().step() is None, 240)

    @step
    def report():
        L = les()
        n = len(L.LESSONS[lesson_id].steps)
        unseen = [f"{k + 1} {L.LESSONS[lesson_id].steps[k].title}" for (lid, k), v in sorted(SEEN.items())
                  if lid == lesson_id and v["done"] and not v["seen"]]
        log(f"{lesson_id}: steps watched", sorted(k for (lid, k) in SEEN if lid == lesson_id), "unseen", unseen)
        check(f"Play on ({lesson_id}): every step's button was on screen before the app did it", not unseen,
              f"done unseen: {unseen} of {n}")
        mod("blender.prefs").get().lesson_play_on = S["play_on_was"]
        with override():
            bpy.ops.fresing.lesson_stop()
        return 0.5
    report.__name__ = f"play_on_report_{lesson_id}"


_play_on("crane")
_play_on("mill")


@step
def s_finish():
    if "timing" in S:
        les().SHOW_DELAY, les().SHOW_LATEST = S["timing"]
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    for r in failed:
        log("FAILED:", r[0], r[2])
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
