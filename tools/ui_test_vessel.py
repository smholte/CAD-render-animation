"""Real-app test, vessel motion (task 0085): the crane on the Vessel deck, 5 Scene & Render > Vessel motion: the header
says Off, tick it (the crane and the deck move, the sea and the camera stay), the header shows the roll, Heading, Pick
pivot, Keep the selection still / level and back, save and open again, and the saved project in the real program
with scripts disabled (-Y): the vessel still moves while a Python-only control driver is refused.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_vessel.py
Screenshots and ui_test_vessel.log go to $UITEST_OUT (default ~/fresing_ui_test_vessel).
"""

import json
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_vessel"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_vessel.log"), "w")
RESULTS = []
STATE = {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail else ""))


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def op(_idname, **kw):
    """Call an operator like a button press (EXEC, with an undo step)."""
    group, op_name = _idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), op_name)("EXEC_DEFAULT", True, **kw)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def sidebar_shot(name, height=1500):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    h = min(height, sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{h}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def key(k, ctrl=False, shift=False):
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl, shift=shift)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name):
    return next((o for o in bpy.context.scene.objects if o.get("fr_name") == name), None)


def select(objs, active=None):
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = active or objs[-1]




def vm():
    return mod("blender.vessel_motion")


def tip():
    return named("BOOM").matrix_world @ Vector((1.5, 0.0, 0.0))


def open_panel():
    """5 Scene & Render and Vessel motion start closed: copies that start open."""
    for name in ("FRESING_PT_scene", "FRESING_PT_vessel_motion"):
        cls = getattr(bpy.types, name)
        if "DEFAULT_CLOSED" in getattr(cls, "bl_options", set()):
            bpy.utils.unregister_class(cls)
            cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
            bpy.utils.register_class(cls)


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region, sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=region.x + 300, y=region.y + 300)
    win.event_simulate(type="ESC", value="RELEASE", x=region.x + 300, y=region.y + 300)
    return 1.0


@step
def s_import():
    log("extension", pkg())
    with override():
        res = bpy.ops.fresing.import_step(filepath=MODEL, quality="normal")
    log("import", res, bpy.context.scene.fresing.last_message)
    return 1.0


@step
def s_wait():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    s = sc.fresing
    s.env_detail = "DETAILED"
    s.background = "DECK"
    op("fresing.camera_add", view="ISOMETRIC")
    win, area, region, sb = ui()
    area.spaces.active.shading.type = "SOLID"
    open_panel()
    redraw()
    return 1.0


@step
def s_off():
    sc = bpy.context.scene
    check("header says Off before it is ticked", vm().header(sc) == "Off", vm().header(sc))
    check("nothing is made while it is off", vm().rig("vessel") is None and not list(vm()._constraints(sc)))
    sc.fresing.vessel.enabled = True                   # the tick box (its update builds the swell and the rig)
    redraw()
    wiggle()
    return 1.0


@step
def s_on():
    sc = bpy.context.scene
    head = vm().header(sc)
    check("header: 'Calm · roll ±…°'", head.startswith("Calm · roll ±") and head.endswith("°"), head)
    sea = next(o for o in sc.objects if o.get("fr_env") == "sea")
    cam = sc.camera
    STATE["sea"], STATE["cam"] = sea.matrix_world.copy(), cam.matrix_world.copy()
    sc.frame_set(1)
    a = tip()
    sc.frame_set(90)
    b = tip()
    check("the crane moves between frames 1 and 90", (a - b).length > 0.02, f"{(a - b).length * 1000:.0f} mm")
    check("the sea and the camera stay", sea.matrix_world == STATE["sea"] and cam.matrix_world == STATE["cam"])
    deck = [o for o in sc.objects if o.get("fr_env") == "floor"]
    check("the deck moves with the vessel", deck and all(o.constraints.get(vm().CON) for o in deck))
    sb_text = vm().words(sc)
    check("the panel's line of numbers", sb_text.startswith("Over 2 minutes: roll ±"), sb_text)
    wiggle()
    return 1.0


@step
def s_screens():
    sidebar_shot("panel5_vessel_motion", 1700)
    sc = bpy.context.scene
    sc.fresing.vessel.heading = "BEAM"
    roll_beam = vm().peaks(sc)["roll"]
    sc.fresing.vessel.heading = "HEAD"
    roll_head = vm().peaks(sc)["roll"]
    check("a beam sea rolls more than a head sea", roll_beam > 2 * roll_head, f"{roll_beam:.2f} vs {roll_head:.2f}")
    sc.fresing.vessel.heading = "BEAM"
    r = op("fresing.vessel_pivot_pick")
    check("Pick pivot (scripts: the automatic point)", r == {"FINISHED"} and sc.fresing.vessel.pivot_mode == "PICK")
    sc.fresing.vessel.pivot_mode = "AUTO"
    select([named("TROLLEY.ASM")])
    r = op("fresing.vessel_still_add", mode="STILL")
    check("Keep the selection still", r == {"FINISHED"} and len(sc.fresing.vessel.still) == 1
          and any(c.name == vm().CON_STILL for _o, c in vm()._constraints(sc)))
    tr = named("TROLLEY")
    sc.frame_set(20)
    a = tr.matrix_world.translation.copy()
    sc.frame_set(140)
    check("the trolley stays put while the vessel moves", (tr.matrix_world.translation - a).length < 1e-4)
    sc.fresing.vessel.still_index = 0
    r = op("fresing.vessel_still_remove")
    check("Move with the vessel again", r == {"FINISHED"} and len(sc.fresing.vessel.still) == 0
          and not [c for _o, c in vm()._constraints(sc) if c.name != vm().CON])
    redraw()
    wiggle()
    return 1.0


@step
def s_noscripts():
    """The saved project in the real program with scripts disabled (-Y): the vessel moves as in the app, while a
    Python-only control driver is refused."""
    sc = bpy.context.scene
    ctrl = bpy.data.objects.new("NOSCRIPTS control", None)
    sc.collection.objects.link(ctrl)
    ctrl["v"] = -1.0
    fc = ctrl.driver_add('["v"]')
    fc.driver.type = "SCRIPTED"
    fc.driver.expression = "frame * float(bpy.app.version[0])"
    sc.frame_set(1)
    bpy.context.view_layer.update()
    saved = float(ctrl["v"])
    frames = [7, 120, 333]
    want = {}
    boom = named("BOOM")
    for f in frames:
        sc.frame_set(f)
        bpy.context.view_layer.update()
        want[f] = [v for row in boom.matrix_world for v in row]
    sc.frame_set(1)
    path = os.path.join(OUT, "vessel_noscripts.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.data.objects.remove(ctrl)
    fcs = vm().rig("vessel").animation_data.drivers
    simple = all(f.driver.is_simple_expression for f in fcs)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vessel_check_noscripts.py")
    res = subprocess.run([bpy.app.binary_path, "--factory-startup", "-b", "-Y", path, "--python", script, "--",
                          boom.name] + [str(f) for f in frames], capture_output=True, text=True, timeout=300)
    got, extra = {}, {}
    for line in res.stdout.splitlines():
        if line.startswith("NOSCRIPTS "):
            k, v = line[len("NOSCRIPTS "):].split(" ", 1)
            if k.isdigit():
                got[int(k)] = json.loads(v)
            else:
                extra[k] = v
    log("noscripts output:", extra, "control saved as", saved)
    try:
        worst = max(abs(a - b) for f in frames for a, b in zip(got[f], want[f]))
        ok = (worst < 1e-5 and extra.get("autoexec_fail") == "True" and abs(float(extra["control"]) - saved) < 1e-9)
    except (KeyError, ValueError):
        worst, ok = None, False
    check("scripts disabled (blender -Y): the crane moves exactly as in the app; Python drivers refused",
          simple and ok, f"simple {simple}, worst {worst}, {extra}, exit {res.returncode}")
    return 0.5


@step
def s_save():
    sc = bpy.context.scene
    sc.frame_set(250)
    STATE["tip"] = tip()
    path = os.path.join(OUT, "vessel_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    sc.frame_set(1)
    sc.frame_set(250)
    check("reopened: on, and the crane where it was at frame 250", sc.fresing.vessel.enabled
          and (tip() - STATE["tip"]).length < 1e-5)
    sc.fresing.vessel.enabled = False
    check("untick: no rig, no constraints left", vm().rig("vessel") is None and not list(vm()._constraints(sc)))
    shot("04_off")
    return 0.5


@step
def s_finish():
    failed = [r for r in RESULTS if not r[1]]
    log(f"RESULT {len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
    LOG.close()
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
    if r == "wait":
        if not _w[0]:
            _w[0] = time.time()
        if time.time() - _w[0] > 300:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        wiggle()                                         # events keep the import's timer going
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
