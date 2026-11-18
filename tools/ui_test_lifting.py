"""Real-app test, 8 Lifting plan (task 0201): the first-use dialog (I understand), placing the AT-40 by mouse (it
follows the mouse over the ground, the wheel turns it, a click puts it down), every built-in crane class placed in
one project with its joints where the maker's kinematics say for every pose of its file, unique names, Remove leaves
nothing behind; the test crane's boom as the load with its CoG marker; Hook to here by a click in the view and Above
the load; the panel's crane use is the chart's; save and open again.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_lifting.py
Screenshots and ui_test_lifting.log go to $UITEST_OUT (default ~/fresing_ui_test_lifting).
"""

import importlib
import math
import os
import subprocess
import time
import traceback

import bpy
import numpy as np
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_lifting"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_lifting.log"), "w")
RESULTS = []
S = {}


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
    return importlib.import_module(pkg() + "." + name)


def L():
    return mod("blender.lifting")


def ui():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == "VIEW_3D")
    region = next(r for r in area.regions if r.type == "WINDOW")
    sidebar = next(r for r in area.regions if r.type == "UI")
    return win, area, region, sidebar


def override():
    win, area, region, _sb = ui()
    return bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region, scene=win.scene)


def can(idname) -> bool:
    group, name = idname.split(".")
    with override():
        return bool(getattr(getattr(bpy.ops, group), name).poll())


def op(idname, **kw):
    group, name = idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), name)("EXEC_DEFAULT", True, **kw)


def invoke(idname, **kw):
    group, name = idname.split(".")
    with override():
        return getattr(getattr(bpy.ops, group), name)("INVOKE_DEFAULT", True, **kw)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def wiggle():
    win, _area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def sidebar_shot(name, height=1600):
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    subprocess.run(["convert", full, "-crop", f"{sb.width}x{min(height, sb.height)}+{sb.x}+{top}", "+repage",
                    os.path.join(OUT, name + ".png")], check=False)


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def view(location, distance, turn=35.0, tilt=62.0):
    _win, area, _region, _sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = (Quaternion((0, 0, 1), math.radians(-turn)) @ Quaternion((1, 0, 0), math.radians(tilt)))
    r3d.view_location = Vector(location)
    r3d.view_distance = distance
    area.spaces.active.clip_end = 2000.0
    redraw()


def pixel_of(world):
    """The window pixel of a world point (the 3D view's region)."""
    _win, _area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world))
    return int(round(region.x + co.x)), int(round(region.y + co.y))


def ground_under(px, z=0.0):
    """Where the ray through a window pixel meets the level plane at ``z`` (what a click on the ground gives)."""
    _win, _area, region, _sb = ui()
    co = (px[0] - region.x, px[1] - region.y)
    o = view3d_utils.region_2d_to_origin_3d(region, region.data, co)
    d = view3d_utils.region_2d_to_vector_3d(region, region.data, co)
    t = (z - o.z) / d.z
    return np.array(o + d * t)


def move_to(px):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=px[0], y=px[1])


def click(px):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=px[0], y=px[1])
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=px[0], y=px[1])
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=px[0], y=px[1])


def item(name):
    return os.path.join(mod("core.lifting_library").BUILTIN_DIR, name)


def counts():
    s = bpy.context.scene.fresing
    return (len(bpy.data.objects), sum(1 for m in bpy.data.meshes if m.users), len(bpy.data.collections),
            len(s.joints), len(s.cylinders),
            len(s.poses),
            len(s.cables), len(s.tracks))


def hook_errors(crane):
    """Largest distance (mm) of the hook block from the maker's kinematics over the file's poses."""
    C = mod("lifting_model.classes")
    lay = C.layout(crane.item_name)
    sc = bpy.context.scene
    worst = 0.0
    for p in L().pose_names(crane):
        L().apply_pose(sc, crane, p)
        want = L().to_world(crane, C.hook_point(lay, L().values(sc, crane)))
        got = L()._hook_block_world(sc, crane)
        worst = max(worst, float(np.linalg.norm(got - want)) * 1000.0)
    return worst


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_first_use():
    log("extension", pkg())
    win, _area, _region, _sb = ui()
    win.event_simulate(type="ESC", value="PRESS", x=700, y=500)      # the splash screen first (CLAUDE.md 8)
    win.event_simulate(type="ESC", value="RELEASE", x=700, y=500)
    os.environ.pop(L().ENV_UNDERSTOOD, None)
    check("a new user has not seen the planning-aid line: the section's buttons are grey",
          not L().understood() and not can("fresing.lifting_place") and not can("fresing.lifting_hook_here"))
    mod("blender.panels").open_to("FRESING_PT_lifting")
    redraw()
    wiggle()
    return 1.0


@step
def s_first_use_shot():
    sidebar_shot("lifting_first_use", 700)
    res = invoke("fresing.lifting_understand")
    check("the first use asks with a dialog", res == {"RUNNING_MODAL"} or res == {"INTERFACE"}, str(res))
    return 1.0


@step
def s_confirm():
    shot("lifting_dialog")
    win, _area, region, _sb = ui()
    win.event_simulate(type="RET", value="PRESS")
    win.event_simulate(type="RET", value="RELEASE")
    return 1.0


@step
def s_understood():
    ok = L().understood()
    if not ok:
        L().set_understood(True)                     # the rest of the test still runs
    check("I understand (Return in the dialog) opens the Lifting plan, kept as a preference", ok)
    with override():
        bpy.ops.fresing.import_step(filepath=CRANE, quality="draft")
    return 1.0


@step
def s_model():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    S["before"] = counts()
    view((6.0, 0.0, 0.0), 40.0)
    for p in ("FRESING_PT_lifting_equipment", "FRESING_PT_lifting_load", "FRESING_PT_lifting_hook"):
        mod("blender.panels").open_to(p)
    check("after I understand the buttons are there: Place…, Use selected parts", can("fresing.lifting_place")
          and can("fresing.lifting_load_selected"))
    op("fresing.lifting_pick", path=item("AT-40"))
    redraw()
    return 1.0


@step
def s_library_shot():
    sidebar_shot("lifting_library", 1900)
    res = invoke("fresing.lifting_place")
    check("Place… starts (the model is read, then it follows the mouse)", res == {"RUNNING_MODAL"}, str(res))
    S["t"] = time.time()
    return 0.5


@step
def s_follow():
    sc = bpy.context.scene
    if not sc.fresing.lifting.cranes:
        wiggle()
        return "wait"
    px = pixel_of((10.0, 6.0, 0.0))
    move_to(px)
    S["px"] = px
    return 0.7


@step
def s_wheel():
    c = bpy.context.scene.fresing.lifting.cranes[0]
    want = ground_under(S["px"])
    got = np.array(c.root.matrix_world.translation)
    check("the crane follows the mouse over the ground", np.linalg.norm(got - want) < 0.01,
          f"{np.linalg.norm(got - want) * 1000:.1f} mm")
    S["h0"] = L().heading_of(c)
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="WHEELUPMOUSE", value="PRESS", x=S["px"][0], y=S["px"][1])
    return 0.7


@step
def s_click():
    c = bpy.context.scene.fresing.lifting.cranes[0]
    d = math.degrees(L().heading_of(c) - S["h0"])
    check("the mouse wheel turns it by 15°", abs(d - 15.0) < 1e-3, f"{d:.3f}°")
    click(S["px"])
    return 1.0


@step
def s_placed():
    sc = bpy.context.scene
    c = sc.fresing.lifting.cranes[0]
    want = ground_under(S["px"])
    got = np.array(c.root.matrix_world.translation)
    check("a click puts it down where the ray meets the ground", np.linalg.norm(got - want) < 0.001
          and c.name == "AT-40", f"{np.linalg.norm(got - want) * 1000:.2f} mm")
    check("its joints carry its name", all(j.name.startswith("AT-40 · ") for j in L().own_joints(sc, c))
          and len(L().own_joints(sc, c)) == 19)
    err = hook_errors(c)
    check("AT-40: every pose of its file puts the hook block where its maker's kinematics say", err < 5.0,
          f"{err:.3f} mm")
    op("fresing.lifting_pose", pose="Set up")
    redraw()
    return 1.0


@step
def s_crane_shot():
    sidebar_shot("lifting_equipment", 1900)
    shot("lifting_view_at40")
    S["classes"] = [n for n in mod("lifting_model.classes").CLASSES if n != "AT-40"]
    S["k"] = 0
    S["worst"] = {}
    S["t_place"] = {}
    return 0.5


@step
def s_every_class():
    """One class per timer step (each reads its STEP once)."""
    names = S["classes"]
    if S["k"] < len(names):
        n = names[S["k"]]
        x, y = 60.0 * (1 + S["k"] % 4), 70.0 * (1 + S["k"] // 4)
        t0 = time.time()
        res = op("fresing.lifting_place", path=item(n), location=(x, y, 0.0), heading=0.3)
        S["t_place"][n] = time.time() - t0
        sc = bpy.context.scene
        c = sc.fresing.lifting.cranes[-1]
        S["worst"][n] = hook_errors(c) if res == {"FINISHED"} and c.item_name == n else 1e9
        log(n, res, f"{S['t_place'][n]:.1f} s", f"{S['worst'][n]:.3f} mm")
        S["k"] += 1
        return "wait"
    worst = max(S["worst"].values())
    check("every crane class placed in one project: every pose puts its hook block where its maker's kinematics say",
          worst < 5.0 and len(S["worst"]) == 11, ", ".join(f"{k} {v:.2f}" for k, v in S["worst"].items()))
    log("place times (s):", {k: round(v, 1) for k, v in S["t_place"].items()})
    sc = bpy.context.scene
    names = [j.name for j in sc.fresing.joints]
    check("12 cranes, no two joints with the same name", len(sc.fresing.lifting.cranes) == 12
          and len(names) == len(set(names)))
    op("fresing.lifting_place", path=item("AT-40"), location=(-30.0, 0.0, 0.0), heading=0.0)
    check("a second AT-40 is 'AT-40 2'", sc.fresing.lifting.cranes[-1].name == "AT-40 2")
    return 1.0


@step
def s_remove():
    sc = bpy.context.scene
    L_ = sc.fresing.lifting
    S["after_first"] = None
    while len(L_.cranes) > 1:
        L_.crane_index = len(L_.cranes) - 1
        op("fresing.lifting_remove")
    check("Remove: the other cranes are gone, the first is as it was",
          len(L_.cranes) == 1 and L_.cranes[0].name == "AT-40"
          and not any(j.name.startswith(("AT-1", "AT-2", "AT-5", "CC-", "KB-", "AT-40 2")) for j in sc.fresing.joints))
    S["one"] = counts()
    return 1.0


@step
def s_load():
    sc = bpy.context.scene
    build = mod("blender.build")
    boom = next(o for o in sc.objects if o.get(build.PROP_NAME) == L().EXAMPLE_LOAD)
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        boom.select_set(True)
        bpy.context.view_layer.objects.active = boom
    res = op("fresing.lifting_load_selected")
    ld = L().active_load(sc)
    check("Use selected parts makes the boom the load, its CoG marker inside it",
          res == {"FINISHED"} and ld is not None and L().check_cog(sc) != "")
    ld.mass_t, ld.source = 1.2, "DRAWING"
    view(tuple(L().cog_world(ld)), 4.0)
    redraw()
    return 1.0


@step
def s_hook_click():
    shot("lifting_view_cog")
    sidebar_shot("lifting_load", 1900)
    sc = bpy.context.scene
    c = L().active_crane(sc)
    target = np.array(c.root.matrix_world.translation) + np.array((-5.0, 3.0, 0.0))
    view(tuple(target), 40.0)                 # the point in the middle of the view, clear of the side panel
    S["hpx"] = pixel_of(target)
    res = invoke("fresing.lifting_hook_here")
    check("Hook to here waits for a click", res == {"RUNNING_MODAL"}, str(res))
    return 0.7


@step
def s_hook_clicked():
    click(S["hpx"])
    return 1.0


@step
def s_hook_done():
    sc = bpy.context.scene
    c = L().active_crane(sc)
    want = ground_under(S["hpx"], z=float(c.root.matrix_world.translation.z))
    got = L()._hook_block_world(sc, c)
    check("the click put the hook (plumb, its block) on the clicked ground", np.linalg.norm(got - want) < 0.005,
          f"{np.linalg.norm(got - want) * 1000:.2f} mm; {sc.fresing.lifting.message}")
    res = op("fresing.lifting_hook_above")
    ld = L().active_load(sc)
    got = L()._hook_block_world(sc, c)
    check("Above the load: the hook 2 m above the load's top, over its CoG",
          res == {"FINISHED"} and np.linalg.norm(got - L().above_load(sc, ld)) < 0.005)
    ro = L().readout(sc, c, ld)
    core = mod("core.lifting")
    ref = core.crane_use(1200.0 * ld.contingency, ro.radius, ro.chart, hook_block=L().hook_block_kg(c))
    check("the panel's crane use is the chart's at that radius", abs(ro.use - ref.use) < 1e-6 and ro.words == ref.words,
          f"{ro.use * 100:.3f} % vs {ref.use * 100:.3f} % {ro.words}")
    view(tuple(np.array(c.root.matrix_world.translation) + np.array((-4.0, 0.0, 3.0))), 30.0)
    redraw()
    return 1.0


@step
def s_save():
    shot("lifting_view_hook")
    sidebar_shot("lifting_hook", 1900)
    path = os.path.join(OUT, "lifting é.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    S["use"] = L().readout(bpy.context.scene, L().active_crane(bpy.context.scene),
                           L().active_load(bpy.context.scene)).use
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_opened():
    sc = bpy.context.scene
    c, ld = L().active_crane(sc), L().active_load(sc)
    ok = c is not None and ld is not None
    check("saved and opened: the crane, the load and the crane use are as before",
          ok and abs(L().readout(sc, c, ld).use - S["use"]) < 1e-9)
    if ok:
        check("opened: the hook block is still where the kinematics say", hook_errors(c) < 5.0)
        op("fresing.lifting_remove")
        op("fresing.lifting_load_remove")
        check("Remove the crane and the load: the project is as before the plan", counts() == S["before"],
              f"{counts()} vs {S['before']}")
    return 1.0


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
        if time.time() - _w[0] > 600:
            check(fn.__name__ + " timeout", False)
            _i[0] += 1
            _w[0] = 0.0
        return 0.3
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
