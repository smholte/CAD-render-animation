"""Task 0133 – the highlight looks side by side, in the real app (branch task/0133-highlight-looks only).

On the test crane: Build it yourself at step 2 (*Product studio*, next to the blue *White, endless*) and step 3 (*Add
rotate joint*, aligned with *Add slide joint*) with each button look A–F (a picture of each, a short clip of each at
step 3), the three part looks on the boom, then step 7 (6 Animation is closed) with each section marker. Costs per look.

    BLENDER_USER_RESOURCES=~/fr_user LESSON_OUT=/tmp/looks xvfb-run -a -s "-screen 0 1600x1000x24" \\
        blender -p 0 0 1600 1000 --app-template fresing_render --enable-event-simulate --python tools/lesson_looks_app.py

Output in $LESSON_OUT: looks.log, looks.json (costs), b2_<look>.png, b3_<look>.png, clip_<look>/NN.png (+ times.txt),
part_<n>.png, section_<n>.png. tools/lesson_looks_sheets.py makes the comparison sheets and clips from them.
"""

import importlib
import json
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("LESSON_OUT", "/tmp/looks")
os.makedirs(OUT, exist_ok=True)
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
LOG = open(os.path.join(OUT, "looks.log"), "w")
RESULT = {"fail": 0, "ok": 0}
L = {}
COSTS = {}
CLIP_FRAMES, CLIP_DT = 20, 0.13


def log(*a):
    m = " ".join(str(x) for x in a)
    print("[LOOKS]", m, flush=True)
    LOG.write(m + "\n")
    LOG.flush()


def check(cond, what):
    log(("OK   " if cond else "FAIL ") + what)
    RESULT["ok" if cond else "fail"] += 1


def mod(n):
    import addon_utils
    p = next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))
    return importlib.import_module(p + "." + n)


def areas():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    return win, area, next(r for r in area.regions if r.type == "WINDOW"), next(r for r in area.regions if r.type == "UI")


def grab(path, x, y_top, w, h):
    subprocess.run(["import", "-window", "root", "-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y_top)}", "+repage", path],
                   check=False)


def grab_side(path, box, h=150):
    """The side panel's full width, ``h`` px high, centred on a rectangle of the side panel (region pixels, y up)."""
    win, area, region, sb = areas()
    cy = (box[1] + box[3]) / 2
    top = win.height - (sb.y + cy) - h / 2
    top = min(max(top, win.height - (sb.y + sb.height)), win.height - sb.y - h)
    grab(path, sb.x, top, sb.width, h)


def grab_view(path):
    win, area, region, sb = areas()
    w = sb.x - region.x                                  # the view without the side panel over it
    grab(path, region.x, win.height - (region.y + region.height), w, region.height)


def les():
    return L["les"]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


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
def s_start():
    L["les"] = mod("blender.lesson")
    les().register()
    bpy.ops.fresing.light_look(look="WHITE")
    les().start(bpy.context.scene, "crane", "BUILD")
    L["t0"] = time.time()
    return 1.5


@step
def s_step2_found():
    S = les()._S
    if (S["box"] is None or S["step"] != 1) and time.time() - L["t0"] < 10:
        return "wait"
    check(S["step"] == 1 and S["box"] is not None, f"step 2: 'Product studio' found, its button {S['box']}")
    return 0.3


def looks_at(prefix, kinds):
    for k in kinds:
        def set_it(k=k):
            les().set_look("button", k)
            return 1.3                                    # E closes in in 0.7 s, C fades in in 0.4 s

        def shoot(k=k):
            S = les()._S
            if S["box"] is None:
                check(False, f"{prefix} look {k}: no button")
                return 0.2
            grab_side(os.path.join(OUT, f"{prefix}_{k}.png"), S["box"])
            log("picture", f"{prefix}_{k}.png", S["box"])
            return 0.2
        STEPS.append(set_it)
        STEPS.append(shoot)


looks_at("b2", "ABCDEF")


@step
def s_to_step3():
    bpy.ops.fresing.light_look(look="PRODUCT")          # the user does step 2: the lesson goes on by itself
    L["t1"] = time.time()
    return 0.5


@step
def s_step3_found():
    S = les()._S
    if (S["box"] is None or S["step"] != 2) and time.time() - L["t1"] < 12:
        return "wait"
    win, area, region, sb = areas()
    box = S["box"]
    check(S["step"] == 2 and box is not None, f"step 3: 'Add rotate joint' found, its button {box}")
    if box is not None:
        check(box[2] - box[0] < 0.55 * sb.width,
              f"aligned buttons: the look sits on 'Add rotate joint' only ({box[2] - box[0]} of {sb.width} px wide)")
    return 0.3


def clips(kinds):
    for k in kinds:
        def set_it(k=k):
            les().set_look("button", k)
            les()._S["stats"]["look"].pop("button " + k, None)
            return 1.3

        def shoot(k=k):
            S = les()._S
            grab_side(os.path.join(OUT, f"b3_{k}.png"), S["box"])
            les().set_look("button", k)                  # the clip starts at the switch: E closes in, C fades in
            d = os.path.join(OUT, f"clip_{k}")
            os.makedirs(d, exist_ok=True)
            L["clip"] = (k, d, 0, [], S["box"])
            return 0.05

        def frame(k=k):
            k_, d, i, times, box = L["clip"]
            if i >= CLIP_FRAMES:
                with open(os.path.join(d, "times.txt"), "w") as fh:
                    fh.write("\n".join(f"{t:.3f}" for t in times))
                n, s = les()._S["stats"]["look"].get("button " + k, [0, 0.0])
                COSTS["button " + k] = 1000 * s / max(n, 1)
                log(f"look {k}: clip of {i} frames over {times[-1] - times[0]:.2f} s; drawing the look "
                    f"{COSTS['button ' + k]:.3f} ms per side-panel redraw ({n} redraws)")
                return 0.1
            times.append(time.time())
            grab_side(os.path.join(d, f"{i:02d}.png"), box)
            L["clip"] = (k_, d, i + 1, times, box)
            return "again"
        STEPS.extend([set_it, shoot, frame])


clips("ABCDEF")


@step
def s_parts():
    S = les()._S
    win, area, region, sb = areas()
    with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
        les().stop()
        t = time.perf_counter()
        bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
        COSTS["view without a lesson"] = 1000 * (time.perf_counter() - t) / 20
    les().start(bpy.context.scene, "crane", "BUILD")
    les().set_look("button", "A")
    check(S["step"] == 2, "back at step 3 (the boom's parts glow)")
    return 1.0


def parts(kinds):
    for k in kinds:
        def go(k=k):
            les().set_look("part", k)
            return 1.0

        def shoot(k=k):
            grab_view(os.path.join(OUT, f"part_{k}.png"))
            win, area, region, sb = areas()
            les()._S["stats"]["look"].pop("part " + k, None)
            with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
                t = time.perf_counter()
                bpy.ops.wm.redraw_timer(type="DRAW", iterations=20)
                COSTS[f"view with part look {k}"] = 1000 * (time.perf_counter() - t) / 20
            n, s = les()._S["stats"]["look"].get("part " + k, [0, 0.0])
            COSTS["part " + k] = 1000 * s / max(n, 1)
            log(f"part look {k}: 3D view {COSTS[f'view with part look {k}']:.1f} ms per redraw, the look's own "
                f"drawing {COSTS['part ' + k]:.2f} ms ({n} draws); note: {les()._S.get('note') or 'none'}")
            check(n > 0 and not les()._S.get("note"), f"part look {k} drawn without an error")
            return 0.3
        STEPS.extend([go, shoot])


parts("123")


@step
def s_to_step7():
    S = les()._S
    sc = bpy.context.scene
    les().set_look("part", "1")
    for _ in range(4):                                 # steps 3 … 6 done as Show me would do them
        les().do_step(sc)
        les().next_step(sc)
    L["t7"] = time.time()
    log("now at step", S["step"] + 1)
    return 0.5


@step
def s_step7_found():
    S = les()._S
    if S["found_header"] is None and time.time() - L["t7"] < 12:
        return "wait"
    check(S["step"] == 6 and S["found"] is None and S["hbox"] is not None,
          f"step 7: 6 Animation is closed, its header found {S['hbox']}")
    return 0.3


def sections(kinds):
    for k in kinds:
        def go(k=k):
            les().set_look("section", k)
            les()._S["stats"]["look"].pop("section " + k, None)
            return 1.0

        def shoot(k=k):
            S = les()._S
            grab_side(os.path.join(OUT, f"section_{k}.png"), S["hbox"], h=110)
            n, s = S["stats"]["look"].get("section " + k, [0, 0.0])
            COSTS["section " + k] = 1000 * s / max(n, 1)
            log(f"section look {k}: {COSTS['section ' + k]:.3f} ms per side-panel redraw ({n} redraws)")
            check(n > 0, f"section look {k} drawn")
            return 0.3
        STEPS.extend([go, shoot])


sections("123")


@step
def s_costs():
    st = les()._S["stats"]
    win, area, region, sb = areas()
    COSTS["find (pixel search + boxes)"] = 1000 * st["read_s"] / max(1, st["reads"])
    COSTS["side panel"] = f"{sb.width}x{sb.height}"
    COSTS["view"] = f"{region.width}x{region.height}"
    log(f"finding the button (pixels read, markers, button box): {COSTS['find (pixel search + boxes)']:.2f} ms per "
        f"side-panel redraw ({st['reads']} times)")
    log("notes:", les()._S.get("note") or "none")
    check(not les()._S.get("note"), "no drawing error noted")
    json.dump(COSTS, open(os.path.join(OUT, "looks.json"), "w"), indent=1)
    return 0.3


@step
def s_quit():
    log(f"CHECKS OK: {RESULT['ok']}, FAILED: {RESULT['fail']}")
    les().stop()
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
    if r == "again":
        return CLIP_DT
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("LESSON_SCALE", "1.0"))
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
