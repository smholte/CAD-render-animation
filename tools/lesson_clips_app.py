"""Task 0168 – smooth 3 s clips of every highlight look in every colour, in the real app (branch only, never merged).

On the test crane (``test_crane_a.step``): buttons at step 3 (*Add rotate joint*, joined to *Add slide joint*), closed
sections at step 7 (6 Animation closed), parts at step 3 (the boom). The looks' clock is set per picture
(``lesson.begin_clip / set_clock``): 75 pictures = 25 per second for 3 s, every movement joins up at 3 s. UI scale 2.0.

    BLENDER_USER_RESOURCES=~/fr_user LESSON_OUT=/tmp/clips LESSON_GROUP=buttons LESSON_ONLY=ABCDEFG \\
        xvfb-run -a -s "-screen 0 1600x1000x24" blender -p 0 0 1600 1000 --app-template fresing_render \\
        --enable-event-simulate --python tools/lesson_clips_app.py

LESSON_GROUP = buttons | sections | parts; LESSON_ONLY = the look letters / numbers to make (default all);
LESSON_COLOURS = names of ``lesson.COLOURS`` separated by "|" (default all six); LESSON_FRAMES = pictures per clip (75).
Output in $LESSON_OUT: clips/<kind>_<look>_<HEX>.mp4 + .jpg (poster), clips_<group>_<only>.json (descriptions, costs).
"""

import importlib
import json
import os
import subprocess
import time
import traceback

import bpy

OUT = os.environ.get("LESSON_OUT", "/tmp/clips")
GROUP = os.environ.get("LESSON_GROUP", "buttons")
ONLY = os.environ.get("LESSON_ONLY", "")
FRAMES = int(os.environ.get("LESSON_FRAMES", "75"))
FPS = 25
os.makedirs(os.path.join(OUT, "clips"), exist_ok=True)
TAG = f"{GROUP}_{ONLY or 'all'}"
CRANE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
LOG = open(os.path.join(OUT, f"clips_{TAG}.log"), "w")
RESULT = {"fail": 0, "ok": 0}
L = {}
META = {"costs": {}, "desc": {}, "grab_ms": []}


def log(*a):
    m = " ".join(str(x) for x in a)
    print("[CLIPS]", m, flush=True)
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


def les():
    return L["les"]


def redraw_now():
    win, area, region, sb = areas()
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)


def grab(path, x, y_top, w, h):
    subprocess.run(["import", "-window", "root", "-crop", f"{int(w)}x{int(h)}+{int(x)}+{int(y_top)}", "+repage", path],
                   check=False)


def crop_side(box, h):
    win, area, region, sb = areas()
    cy = (box[1] + box[3]) / 2
    top = win.height - (sb.y + cy) - h / 2
    top = min(max(top, win.height - (sb.y + sb.height)), win.height - sb.y - h)
    return sb.x, top, sb.width, h


def crop_parts():
    """The crane's part and its text card, fixed for every picture of every clip (the card's size does not change)."""
    win, area, region, sb = areas()
    x, y, w, h, box = les()._S["card"]
    pad = 36
    x0 = max(min(x, box[0]) - pad, 0)
    x1 = min(max(x + w, box[2]) + pad, sb.x - region.x)
    y0 = max(min(y, box[1]) - pad, 0)
    y1 = min(max(y + h, box[3]) + pad, region.height)
    return region.x + x0, win.height - (region.y + y1), x1 - x0, y1 - y0


def make_clip(kind, look, hexname, crop):
    """75 pictures with the clock set per picture, then H.264. Returns the drawing cost per redraw (ms)."""
    S = les()._S
    key = f"{kind} {look}"
    S["stats"]["look"].pop(key, None)
    d = os.path.join(OUT, f"tmp_{TAG}")
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    les().begin_clip()
    les().set_clock(0.0)
    for _ in range(3):                                   # the box is found from the first picture, not before
        redraw_now()
    t0 = time.time()
    for i in range(FRAMES):
        les().set_clock(i / FPS)
        redraw_now()
        grab(os.path.join(d, f"{i:03d}.png"), *crop)
    META["grab_ms"].append(1000 * (time.time() - t0) / FRAMES)
    les().end_clip()
    n, s = S["stats"]["look"].get(key, [0, 0.0])
    cost = 1000 * s / max(n, 1)
    base = os.path.join(OUT, "clips", f"{kind}_{look}_{hexname}")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(d, "%03d.png"),
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", os.environ.get("LESSON_CRF", "27"), "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-an", base + ".mp4"], check=True)
    subprocess.run(["convert", os.path.join(d, f"{min(30, FRAMES - 1):03d}.png"), "-quality", "78", base + ".jpg"],
                   check=False)
    return cost, n


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
def s_step2():
    S = les()._S
    if (S["box"] is None or S["step"] != 1) and time.time() - L["t0"] < 45:
        return "wait"
    bpy.ops.fresing.light_look(look="PRODUCT")          # the user does step 2: the lesson goes on by itself
    L["t1"] = time.time()
    return 0.5


@step
def s_step3():
    S = les()._S
    if (S["box"] is None or S["step"] != 2) and time.time() - L["t1"] < 45:
        return "wait"
    if S["box"] is None:
        subprocess.run(["import", "-window", "root", os.path.join(OUT, "debug.png")], check=False)
    check(S["step"] == 2 and S["box"] is not None, f"step 3 found, button {S['box']} step {S['step']} found {S['found']} note {S.get('note')}")
    if GROUP == "sections":
        for _ in range(4):                               # steps 3 … 6 done as Show me would do them
            les().do_step(bpy.context.scene)
            les().next_step(bpy.context.scene)
        L["t7"] = time.time()
    return 0.5


@step
def s_step7():
    if GROUP != "sections":
        return 0.1
    S = les()._S
    if S["found_header"] is None and time.time() - L["t7"] < 15:
        return "wait"
    check(S["step"] == 6 and S["hbox"] is not None, f"step 7: closed section header {S['hbox']}")
    return 0.3


def colours_for(kind, look):
    names = os.environ.get("LESSON_COLOURS", "")
    names = names.split("|") if names else list(les().COLOURS)
    if kind == "button" and look == "F":
        return [("Blender blue", "#4772B3")]
    return [(n, les().COLOURS[n]) for n in names]


@step
def s_clips():
    les_ = les()
    kind = {"buttons": "button", "sections": "section", "parts": "part"}[GROUP]
    table = {"button": les_.BUTTON_LOOKS, "section": les_.SECTION_LOOKS, "part": les_.PART_LOOKS}[kind]
    looks = [k for k in table if not ONLY or k in ONLY]
    S = les_._S
    les_.set_look("button", "A")
    for _ in range(3):
        redraw_now()
    if kind == "parts":
        L["crop"] = None
    for look in looks:
        les_.set_look(kind, look)
        META["desc"][f"{kind} {look}"] = table[look]
        for name, hx in colours_for(kind, look):
            les_.set_colour(hx)
            les_.begin_clip()
            les_.set_clock(0.0)
            for _ in range(4):
                redraw_now()
            if kind == "button":
                crop = crop_side(S["box"], 150 * 2) if S["box"] else None
            elif kind == "section":
                crop = crop_side(S["hbox"], 110 * 2) if S["hbox"] else None
            else:
                crop = L.get("crop") or crop_parts()
                L["crop"] = crop
            les_.end_clip()
            if crop is None:
                check(False, f"{kind} {look} {name}: target not found")
                continue
            cost, n = make_clip(kind, look, hx.lstrip("#").upper(), crop)
            META["costs"][f"{kind} {look} {hx}"] = cost
            check(n > 0 and not S.get("note"), f"{kind} {look} {name}: {cost:.3f} ms per redraw ({n} drawn)"
                  + (f" NOTE {S['note']}" if S.get("note") else ""))
            S["note"] = ""
    st = S["stats"]
    META["find_ms"] = 1000 * st["read_s"] / max(1, st["reads"])
    return 0.3


@step
def s_quit():
    json.dump(META, open(os.path.join(OUT, f"clips_{TAG}.json"), "w"), indent=1)
    log(f"CHECKS OK: {RESULT['ok']}, FAILED: {RESULT['fail']}; grab {sum(META['grab_ms']) / max(1, len(META['grab_ms'])):.0f}"
        f" ms per picture")
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
    _i[0] += 1
    return r


bpy.context.preferences.view.ui_scale = float(os.environ.get("LESSON_SCALE", "2.0"))
bpy.app.timers.register(driver, first_interval=4.0, persistent=True)
