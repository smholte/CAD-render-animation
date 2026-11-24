"""Real-app test, task 0290: 4 Motion's joints in a fold of their own; the panel stays still; a clicked joint shows
what it moves.

On the test luffer (tests/data/test_cylinder_a.step): the Joints fold starts folded under an open 4 Motion, a click
on its title opens it and *Add rotate joint* is on screen (found through the lesson highlight's ``found()``, the test
does not know where anything is). Then a follower slide joint (200 mm per turn of the arm, limits 0 … 50 mm) is
clicked in the list: its parts light up (``joint_show``). The arm is moved past the follower's limit: the short
"Beyond limits" comes on the value row, and the Limits row under it keeps its place to the pixel.

    BLENDER_USER_RESOURCES=~/fr_user UITEST_OUT=/tmp/jf xvfb-run -a -s "-screen 0 1800x1300x24" blender \\
        -p 0 0 1800 1300 --app-template fresing_render --enable-event-simulate --python tools/ui_test_joint_fold.py
Pictures (cropped) and the log go to $UITEST_OUT (default ~/fresing_ui_test_joint_fold).
"""

import importlib
import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_joint_fold"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_cylinder_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_joint_fold.log"), "w")
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


def metric(name, value):
    log(f"METRIC {name} {value:.3f}")


def mod(name):
    import addon_utils
    pkg = next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)
    return importlib.import_module(pkg + "." + name)


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


def scale():
    return bpy.context.preferences.system.ui_scale


def step(fn):
    STEPS.append(fn)
    return fn


def mouse_away():
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 200 + int(time.time() * 10) % 9,
                       y=region.y + 200)


def click(x, y):
    win = ui()[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)


def scroll(op, n=1, **kw):
    with override(side=True):
        for _ in range(n):
            getattr(bpy.ops.view2d, op)(**kw)


def redraw():
    hl().redraw()


def grab(name, x, y_top, w, h):
    """A piece of the screen as a PNG (x from the left, y from the top)."""
    path = os.path.join(OUT, name)
    subprocess.run(["import", "-window", "root", "-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y_top)}", "+repage",
                    path], check=False)
    return path


def grab_side(name, box=None, pad=70):
    """The side panel's full width round a rectangle of it (region pixels, y up); without one, all of it."""
    win, _area, _region, sb = ui()
    if box is None:
        return grab(name, sb.x, win.height - (sb.y + sb.height), sb.width, sb.height)
    y1 = min(box[3] + pad, sb.height)
    y0 = max(box[1] - pad, 0)
    return grab(name, sb.x, win.height - (sb.y + y1), sb.width, y1 - y0)


def grab_view(name):
    win, _area, region, sb = ui()
    w = (sb.x - region.x) if sb.x > region.x else region.width
    return grab(name, region.x, win.height - (region.y + region.height), w, region.height)


def in_region(box):
    _w, _a, _r, sb = ui()
    return box is not None and 0 <= box[0] < box[2] <= sb.width and 0 <= box[1] < box[3] <= sb.height


# ---------------------------------------------------------------------------
# bringing a target on screen, only with what the highlight itself found
# ---------------------------------------------------------------------------

def bring(state, want="button"):
    """One step of: scroll until the target's header or button is on screen; ``want`` "button": click a folded
    header open (once), then look further down. True when what is wanted is there and stands still."""
    f = hl().found()
    _w, _a, _r, sb = ui()
    now = time.time()
    if now - state.get("t", 0) < 0.45:
        return False
    state["t"] = now
    box = f.get("button") if f else None
    head = f.get("header") if f else None
    target = box if want == "button" else (head if box is None else None)
    if target is not None:
        was, state["was"] = state.get("was"), tuple(target)
        if was == tuple(target):                            # it stands still (at an edge: no further to scroll)
            return True
        if target[1] < 60:
            scroll("scroll_down", 3)
        elif target[3] > sb.height - 60:
            scroll("scroll_up", 3)
        return False
    if want == "header" and box is not None:
        return False                                        # the section is open: this target shows no header look
    if want == "button" and head is not None and not state.get("clicked"):
        was, state["head_was"] = state.get("head_was"), tuple(head)
        if head[3] < sb.height - 150 * scale() and was != tuple(head):
            scroll("scroll_down", 5)                        # the header up to the top: an open section then shows
            return False                                    # its button below it
        click(sb.x + int(f["hmark"][2] + 40 * scale()), sb.y + int((head[1] + head[3]) / 2))    # folded: the title
        state["clicked"] = True                             # opens it
        state["t"] = now + 0.5
        return False
    n = state.get("scrolls", 0)
    if n == 0 and not state.get("clicked"):
        scroll("scroll_up", 20, page=True)
    elif n < 80:
        scroll("scroll_down", 5)
    state["scrolls"] = n + 1
    redraw()
    return False


def wait_for(name, want="button", limit=45.0):
    """A step that brings the current target on screen."""
    state = {}

    def fn():
        state.setdefault("t0", time.time())
        if bring(state, want):
            mouse_away()
            return 0.6
        if time.time() - state["t0"] > limit:
            f = hl().found()
            check(f"{name}: the target came on screen", False,
                  f"button {f.get('button')}, header {f.get('header')}, note {hl()._S['note']!r}")
            return 0.2
        return "again"
    fn.__name__ = "wait_" + name
    STEPS.append(fn)




# ---------------------------------------------------------------------------
# the steps
# ---------------------------------------------------------------------------

@step
def s_esc_press():
    ui()[0].event_simulate(type="ESC", value="PRESS", x=700, y=500)
    return 0.3


@step
def s_esc_release():
    ui()[0].event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    return 0.5


@step
def s_import():
    # put back at the end: Blender saves changed preferences when it closes (CLAUDE.md 8)
    KEPT.update(overlap=bpy.context.preferences.system.use_region_overlap,
                scale=bpy.context.preferences.view.ui_scale)
    bpy.context.preferences.system.use_region_overlap = False      # else the side panel is see-through
    bpy.context.preferences.view.ui_scale = 1.0
    with override():
        bpy.ops.fresing.import_step(filepath=MODEL, quality="draft")
    return 1.0


def one(name):
    key = mod("blender.build").PROP_NAME
    return sorted((o for o in bpy.context.scene.objects if o.get(key) == name), key=lambda o: o.name)[0]


@step
def s_imported():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    J = mod("blender.joints")
    sc = bpy.context.scene
    lead = J.create(sc, "ROTATE", [one("ARM.ASM")], Vector((0.3, 0.6, 1.8)), Vector((0, 1, 0)), name="Arm")
    fol = J.create(sc, "SLIDE", [one("TELE.ASM")], Vector((0, 0.6, 0)), Vector((1, 0, 0)), name="Follower")
    J.set_follows(sc, sc.fresing.joints["Follower"], "Arm", ratio=200.0)          # 200 mm per turn
    fol = sc.fresing.joints["Follower"]
    fol.use_limits = True
    fol.slide_min, fol.slide_max = 0.0, 0.05
    J.set_value(sc.fresing.joints["Arm"], math.radians(20), use_limits=False)
    check("two joints made, the follower inside its limits",
          len(sc.fresing.joints) == 2 and not J.outside_limits(fol, J.get_value(fol)), str(J.get_value(fol)))
    P = mod("blender.panels")
    P.OPEN.clear()
    P.open_to("FRESING_PT_motion")
    check("the Joints fold starts folded (4 Motion open)", not P.is_open("FRESING_PT_joints")
          and P.is_open("FRESING_PT_motion"))
    hl().set_look("button", "D")
    hl().point(panel="FRESING_PT_joints", button="fresing.joint_pick_axis", text="Add rotate joint")
    redraw()
    return 0.8


wait_for("rotate")                                         # clicks the folded Joints title open


@step
def s_fold_opened():
    f = hl().found()
    P = mod("blender.panels")
    check("a click on the Joints title opened the fold", P.is_open("FRESING_PT_joints"))
    check("Add rotate joint is on screen in the Joints fold", in_region(f.get("button")), str(f.get("button")))
    if f.get("button"):
        grab_side("joints_fold.png", f["button"], pad=160)
    return 0.3


@step
def s_click_follower():
    sc = bpy.context.scene
    i = next(k for k, j in enumerate(sc.fresing.joints) if j.name == "Follower")
    with override(side=True):
        sc.fresing.joints_index = i                         # as a click on the list row does (its update runs)
    shown = mod("blender.joint_show").active()
    check("clicking the follower in the list shows what it moves", shown["kind"] == "joint"
          and shown["name"] == "Follower" and len(shown["main"]) >= 3, str(shown)[:200])
    check("…without selecting anything", not [o for o in sc.objects if o.select_get()])
    hl().point(panel="FRESING_PT_joints", prop="use_limits")
    redraw()
    return 0.8


wait_for("limits_in")


@step
def s_limits_in():
    f = hl().found()
    S["limits_in"] = f.get("button")
    check("the Limits row is found with the follower inside its limits", in_region(S["limits_in"]),
          str(S["limits_in"]))
    grab_view("view_joint_shown.png")
    sc = bpy.context.scene
    J = mod("blender.joints")
    J.set_value(sc.fresing.joints["Arm"], math.radians(170), use_limits=False)     # the arm moved on: 94 mm
    bpy.context.view_layer.update()
    fol = sc.fresing.joints["Follower"]
    check("the follower is past its limit now", J.outside_limits(fol, J.get_value(fol)), str(J.get_value(fol)))
    redraw()
    return 0.8


@step
def s_limits_beyond():
    f = hl().found()
    box = f.get("button")
    check("the Limits row has not moved (the warning took no line of its own)",
          box is not None and S.get("limits_in") is not None and tuple(box) == tuple(S["limits_in"]),
          f"{S.get('limits_in')} -> {box}")
    hl().point(panel="FRESING_PT_joints", button="fresing.limits_note")
    redraw()
    return 0.8


@step
def s_note_on_value_row():
    f = hl().found()
    box, lim = f.get("button"), S.get("limits_in")
    check("'Beyond limits' is shown, above the Limits row (on the value row)",
          box is not None and lim is not None and box[1] > lim[3], f"note {box}, limits {lim}")
    if box is not None:
        grab_side("beyond_limits.png", box, pad=90)
        _w, _a, _r, sb = ui()
        check("…and inside the side panel (not cut off at the right)", box[2] <= sb.width - 4, f"{box}, {sb.width}")
    return 0.3


@step
def s_clear():
    hl().clear()
    one("BASE").select_set(True)                           # a click elsewhere
    ui()[1].tag_redraw()                                    # (a real click redraws the view by itself)
    mouse_away()
    return 1.0


@step
def s_cleared():
    js = mod("blender.joint_show")
    check("a click elsewhere (another selection) ends the show", js.active()["kind"] == "", str(js.active())[:120])
    return 0.2


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
    if KEPT:
        bpy.context.preferences.system.use_region_overlap = KEPT["overlap"]
        bpy.context.preferences.view.ui_scale = KEPT["scale"]
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
    if r == "again":                                        # the step goes on by itself (it has its own limit)
        return 0.15
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 120:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
