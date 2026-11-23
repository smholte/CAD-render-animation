"""Task 0297 prototype (findings only, never shipped): a Blender / Fresing Render switch at the top bar's right end.

Four looks: A plain button (text swaps at once), B a two-part pill whose filled side slides, C the label slides out and
the new one in, D a fade. Only Blender's own buttons: the top bar has no Python
draw handler. A timer asks redraws while the animation runs.

Run (settings folder from tools/web_install_app.py):
    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 2560x1440x24" blender -p 0 0 2560 1440 \
        --app-template fresing_render --enable-event-simulate --python tasks/0297_page/proto/switch_proto.py
Env: P297_OUT (output folder), P297_MODE = measure | clips, P297_WIDTH (window width, for the log)
"""
import json
import math
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("P297_OUT", "/tmp/p297")
MODE = os.environ.get("P297_MODE", "measure")
REDRAW = os.environ.get("P297_REDRAW", "area")       # area = the top bar only, window = the whole window
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, f"log_{MODE}.txt"), "w")
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tests", "data",
                     "test_crane_a.step")
RESULT = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[P297]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def pkg():
    import addon_utils
    for m in addon_utils.modules():
        if m.__name__.endswith("fresing_render"):
            return m.__name__
    return None


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


# ---------------------------------------------------------------------------------------------- the switch itself
S = {"look": "A", "t0": 0.0, "dur": 0.15, "frm": "fresing", "to": "fresing", "force": None,
     "area": None, "draws": [], "tick": 0, "slot": None, "busy": False}
WIDTH_UNITS = float(os.environ.get("P297_UNITS", "12"))   # the slot: 12 UI units (240 px at scale 1)
LABEL = {"fresing": "Fresing Render", "blender": "Blender"}


def shown() -> str:
    """'blender' when all of Blender is shown (Full access), else 'fresing'."""
    try:
        return "blender" if mod("blender.quiet").all_shown(bpy.context.scene) else "fresing"
    except Exception:  # noqa: BLE001
        return "fresing"


def progress() -> float:
    if S["force"] is not None:
        return S["force"]
    if not S["busy"]:
        return 1.0
    t = (time.perf_counter() - S["t0"]) / S["dur"]
    return max(0.0, min(1.0, t))


def ease(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * t)


class FRPROTO_OT_switch(bpy.types.Operator):
    """Prototype: switch between the Fresing window and all of Blender"""
    bl_idname = "fresing_proto.switch"
    bl_label = "Switch"

    def execute(self, context):
        frm = shown()
        t = time.perf_counter()
        bpy.ops.fresing.blender_all()
        RESULT.setdefault("op_ms", []).append((time.perf_counter() - t) * 1000)
        start(frm, shown())
        return {"FINISHED"}


def start(frm, to):
    S.update(frm=frm, to=to, t0=time.perf_counter(), busy=S["look"] != "A", tick=0)
    S["draws"] = []
    if S["busy"] and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.0)
    redraw()


def redraw():
    if REDRAW == "window":
        win = bpy.context.window_manager.windows[0]
        win.screen.show_statusbar = win.screen.show_statusbar
    elif REDRAW == "region" and S.get("region") is not None:
        try:
            S["region"].tag_redraw()
        except ReferenceError:
            S["region"] = None
    elif S["area"] is not None:
        try:
            S["area"].tag_redraw()
        except ReferenceError:
            S["area"] = None


def _tick():
    S["tick"] += 1
    redraw()
    if progress() >= 1.0:
        S["busy"] = False
        redraw()
        return None
    return 1 / 60


def _sub(row, units):
    sub = row.row(align=True)
    sub.ui_units_x = max(0.05, units)
    return sub


def _op(layout, key, icon, **kw):
    if key == "fresing" and icon:
        return layout.operator("fresing_proto.switch", text=LABEL[key], icon_value=icon, **kw)
    return layout.operator("fresing_proto.switch", text=LABEL[key], **kw)


def _draw_slot(self, context):
    """Appended to TOPBAR_HT_upper_bar: the far right of the top bar. Only Blender's own widgets: the top bar has no
    Python draw handler (no bpy.types.SpaceTopBar), so nothing can be drawn freely there."""
    if context.region is None or context.region.alignment != "RIGHT":
        return                           # the top bar is two regions; an appended draw runs in both
    S["area"] = context.area
    S["region"] = context.region
    RESULT["area_seen"] = context.area is not None
    S["draws"].append(time.perf_counter())
    t0 = time.perf_counter()
    row = self.layout.row(align=True)
    W = WIDTH_UNITS
    animating = S["busy"] or S["force"] is not None
    cur = S["to"] if animating else shown()
    frm = S["frm"] if animating else cur
    t = ease(progress())
    done = (not animating) or t >= 1.0
    icon = mod("blender.ui_topbar").mark_icon()
    look = S["look"]
    other_now = "blender" if cur == "fresing" else "fresing"
    other_was = "blender" if frm == "fresing" else "fresing"
    if look == "A":                      # names where the button takes you
        _op(_sub(row, W), other_now, icon)
    elif look == "B":                    # segmented pill, the filled half = where you are; it slides
        half = W / 2
        pos = {"fresing": 0.0, "blender": half}
        if done:
            for key in ("fresing", "blender"):
                _op(_sub(row, half), key, icon, depress=(key == cur))
        else:
            x = pos[frm] + (pos[cur] - pos[frm]) * t
            if x > 0.05:
                _sub(row, x).operator("fresing_proto.switch", text=" ")
            _sub(row, half).operator("fresing_proto.switch", text=LABEL[cur], depress=True)
            if half - x > 0.05:
                _sub(row, half - x).operator("fresing_proto.switch", text=" ")
    elif look == "C":                    # the label slides out to the left, the new one in from the right
        box = _sub(row, W)
        if done:
            _op(box, other_now, icon)
        elif t < 0.5:
            k = t / 0.5                  # old label moves left: its first letters go
            text = LABEL[other_was][int(round(len(LABEL[other_was]) * k)):]
            inner = box.row(align=True)
            inner.alignment = "LEFT"
            inner.operator("fresing_proto.switch", text=text or " ")
        else:
            k = (t - 0.5) / 0.5          # new label comes in from the right
            inner = box.row(align=True)
            pad = (1 - k) * W * 0.85
            if pad > 0.05:
                _sub(inner, pad).label(text="")
            inner.operator("fresing_proto.switch", text=LABEL[other_now])
    elif look == "D":                    # "fade": dimmed old -> dimmed new -> new (Blender has no alpha for widgets)
        sub = _sub(row, W)
        if done:
            key, active = other_now, True
        elif t < 0.5:
            key, active = other_was, False
        else:
            key, active = other_now, False
        sub.active = active
        _op(sub, key, icon)
    RESULT.setdefault("slot_py_ms", []).append((time.perf_counter() - t0) * 1000)


_H = []


def register_proto():
    bpy.utils.register_class(FRPROTO_OT_switch)
    bpy.types.TOPBAR_HT_upper_bar.append(_draw_slot)


# ---------------------------------------------------------------------------------------------- the run
STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


def win():
    return bpy.context.window_manager.windows[0]


def view3d():
    w = win()
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    return w, area, next(r for r in area.regions if r.type == "WINDOW")


def ov():
    w, area, region = view3d()
    return bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region, scene=w.scene)


def shot(name, crop=None):
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    dst = os.path.join(OUT, name)
    if crop:
        subprocess.run(["convert", full, "-crop", crop, "+repage", dst], check=False)
    else:
        subprocess.run(["cp", full, dst], check=False)
    return dst


@step
def s_start():
    w = win()
    log("window", w.width, w.height, "ui scale", bpy.context.preferences.view.ui_scale, "redraw", REDRAW)
    w.event_simulate(type="ESC", value="PRESS", x=700, y=700)
    w.event_simulate(type="ESC", value="RELEASE", x=700, y=700)
    register_proto()
    return 1.0


@step
def s_import():
    with ov():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="normal")
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    return 2.0


def _switch_and_time(look, n=6):
    """Click the switch n times (direct call as a button would); ms of the operator and until the next top-bar draw."""
    pass


SW = {"k": 0, "res": []}


def _measure_switch():
    """One switch: operator time, then wait for the first top-bar draw after it and for the animation's end."""
    S["draws"] = []
    t = time.perf_counter()
    with ov():
        bpy.ops.fresing_proto.switch()
    t1 = time.perf_counter()
    SW["pending"] = (t, t1, S["look"])
    return 0.6


def _collect():
    t, t1, look = SW["pending"]
    d = [x for x in S["draws"] if x > t1]
    first = (d[0] - t) * 1000 if d else -1
    anim = [x for x in d if x - t <= S["dur"] + 0.2]
    last = (anim[-1] - t) * 1000 if anim else -1
    SW["res"].append({"look": look, "op_ms": (t1 - t) * 1000, "first_draw_ms": first,
                      "topbar_draws_in_anim": len(anim), "last_draw_ms": last, "to": shown()})
    log("switch", SW["res"][-1])


def _draw_cost(label):
    """ms per whole-window redraw (wm.redraw_timer DRAW_WIN)."""
    w, area, region = view3d()
    with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region):
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=20)
        win_ms = (time.perf_counter() - t) * 1000 / 20
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        reg_ms = (time.perf_counter() - t) * 1000 / 20
    RESULT.setdefault("draw_cost", {})[label] = {"window_ms": round(win_ms, 2), "view3d_region_ms": round(reg_ms, 2)}
    log("draw cost", label, RESULT["draw_cost"][label])


PLAY = {"frames": [], "on": False}


def _frame_post(scene, *_a):
    if PLAY["on"]:
        PLAY["frames"].append(time.perf_counter())


def _loop_anim():
    """Keep the switch animation running (worst case: someone clicks it again and again)."""
    if not PLAY.get("loop"):
        return None
    if not S["busy"]:
        start(S["to"], "blender" if S["to"] == "fresing" else "fresing")
    return 0.02


def _play(seconds, loop_look):
    def go():
        sc = bpy.context.scene
        sc.frame_start, sc.frame_end = 1, 100000
        sc.render.fps = 60
        sc.sync_mode = "NONE"                     # play every frame as fast as it can: frames per second = cost
        PLAY["frames"], PLAY["on"] = [], True
        if loop_look:
            S["look"] = loop_look
            PLAY["loop"] = True
            bpy.app.timers.register(_loop_anim, first_interval=0.0)
        w, area, region = view3d()
        with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region):
            bpy.ops.screen.animation_play()
        PLAY["t0"] = time.perf_counter()
        return seconds

    def stop():
        w, area, region = view3d()
        with bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region):
            bpy.ops.screen.animation_cancel(restore_frame=True)
        PLAY["on"], PLAY["loop"] = False, False
        fr = PLAY["frames"]
        fps = (len(fr) - 1) / (fr[-1] - fr[0]) if len(fr) > 2 else 0
        gaps = sorted((b - a) * 1000 for a, b in zip(fr, fr[1:]))
        p95 = gaps[int(len(gaps) * 0.95)] if gaps else 0
        key = f"play_{loop_look or 'none'}_{REDRAW}"
        RESULT.setdefault("play", {})[key] = {"fps": round(fps, 1), "frames": len(fr),
                                              "p95_frame_ms": round(p95, 1)}
        log("play", key, RESULT["play"][key])
        S["look"] = "A"
        S["busy"] = False
        return 1.0
    return go, stop


def _measure_steps():
    out = []
    for look in (("B",) if os.environ.get("P297_QUICK") else ("A", "B", "C", "D")):
        def setlook(look=look):
            S["look"] = look
            if shown() != "fresing":
                with ov():
                    bpy.ops.fresing.blender_all()
            return 1.0
        out.append(setlook)
        for _k in range(3):
            out += [_measure_switch, lambda: (_collect(), 0.5)[1]]
            out += [_measure_switch, lambda: (_collect(), 0.5)[1]]
    out.append(lambda: (_draw_cost("fresing window"), 0.5)[1])
    def to_blender():
        with ov():
            bpy.ops.fresing.blender_all()
        return 1.0
    out += [to_blender, lambda: (_draw_cost("full Blender"), 0.5)[1], to_blender]
    bpy.app.handlers.frame_change_post.append(_frame_post)
    for look in ((None, "B") if os.environ.get("P297_QUICK") else (None, "B", None, "C")):
        go, stop = _play(4.0, look)
        out += [go, stop]
    return out


def _clip_steps():
    """Frames at fixed progress steps (an animation of 150 ms shown at 60 frames/s = 10 frames), cropped."""
    out = []
    def crop():
        w = win()
        sc = bpy.context.preferences.system.ui_scale
        h = int(30 * sc) + 2
        cw = int(820 * sc)
        return f"{cw}x{h}+{w.width - cw}+0"

    def full_bar(name):
        def f():
            w = win()
            sc = bpy.context.preferences.system.ui_scale
            shot(name, f"{w.width}x{int(30 * sc) + 2}+0+0")
            return 0.3
        return f

    out.append(full_bar("bar_full_fresing.png"))
    for look in ("A", "B", "C", "D"):
        for direction in ("fresing", "blender"):
            def prep(look=look, direction=direction):
                S["look"] = look
                if shown() != direction:
                    with ov():
                        bpy.ops.fresing.blender_all()
                S["frm"] = direction
                S["to"] = "blender" if direction == "fresing" else "fresing"
                return 1.0
            out.append(prep)
            n = 10 if look != "A" else 2
            for k in range(-2, n + 3):
                def fr(k=k, look=look, direction=direction, n=n):
                    if k == 0:
                        with ov():
                            bpy.ops.fresing.blender_all()       # the real switch, at the click
                    if look == "A" or k < 0:
                        S["force"] = None
                    else:
                        S["force"] = max(0.0, min(1.0, k / n))
                    redraw()
                    win().screen.show_statusbar = win().screen.show_statusbar
                    return 0.25
                def sh(k=k, look=look, direction=direction):
                    shot(f"f_{look}_{direction}_{k + 2:02d}.png", crop())
                    return 0.05
                out += [fr, sh]
            def done(look=look, direction=direction):
                S["force"] = None
                return 0.8
            out.append(done)
    def back():
        if shown() != "fresing":
            with ov():
                bpy.ops.fresing.blender_all()
        return 1.0
    out.append(back)
    out.append(full_bar("bar_full_fresing_after.png"))
    def toblender():
        S["look"] = "A"
        with ov():
            bpy.ops.fresing.blender_all()
        return 1.0
    out += [toblender, full_bar("bar_full_blender.png"), toblender]
    return out


@step
def s_plan():
    STEPS.extend(_measure_steps() if MODE == "measure" else _clip_steps())
    STEPS.append(s_quit)
    return 0.5


def s_quit():
    with open(os.path.join(OUT, f"result_{MODE}_{REDRAW}.json"), "w") as f:
        json.dump({"switches": SW["res"], **RESULT, "window": [win().width, win().height]}, f, indent=1)
    LOG.close()
    bpy.ops.wm.quit_blender()
    return None


_i = [0]
_wait = [0.0]


def driver():
    if _i[0] >= len(STEPS):
        return None
    fn = STEPS[_i[0]]
    try:
        r = fn()
    except Exception:
        log("ERROR in", getattr(fn, "__name__", fn), traceback.format_exc())
        r = 0.5
    if r == "wait":
        if not _wait[0]:
            _wait[0] = time.time()
        if time.time() - _wait[0] > 180:
            log("timeout")
            _i[0] += 1
        return 1.0
    _wait[0] = 0.0
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("P297_SCALE", "1.0"))
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
