"""Real-app test, painted faces (task 0010): faces painted in CAD come in painted, 'Paint faces' with
real mouse clicks in the view, Shift+click, clicks on the side panel while painting, Enter.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_faces.py
Screenshots and ui_test_faces.log go to $UITEST_OUT (default ~/fresing_ui_test_faces).
"""

import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_faces"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_faces_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_faces.log"), "w")
RESULTS = []


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


def shot(name):
    subprocess.run(["import", "-window", "root", os.path.join(OUT, name + ".png")], check=False)


def find(name, n=0):
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name), key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def top_of(name):
    """Window position of the middle of a part's top face (view from straight above)."""
    ob = find(name)
    lo, hi = mod("blender.build").world_bounds([ob])
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(((lo[0] + hi[0]) / 2,
                                                                            (lo[1] + hi[1]) / 2, hi[2])))
    return int(region.x + co.x), int(region.y + co.y)


def click(x, y, shift=False):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y, shift=shift)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y, shift=shift)


def key(k, x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y)


def sets_of(name):
    return mod("blender.faces").get_sets(find(name).data)


def open_panel():
    cls = bpy.types.FRESING_PT_faces
    if "DEFAULT_CLOSED" in cls.bl_options:
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
    key("ESC", region.x + 300, region.y + 300)          # closes the splash screen
    return 1.0                                         # (an Esc still waiting would cancel the import)


@step
def s_import():
    log("extension", pkg())
    with override():
        res = bpy.ops.fresing.import_step(filepath=MODEL, quality="normal")
    log("import", res, bpy.context.scene.fresing.last_message)
    return 1.0


@step
def s_wait():
    if bpy.context.scene.fresing.model_count == 0:
        job = getattr(mod("blender.ops_import"), "_ACTIVE_JOB", None)
        if job is not None:
            log("waiting:", bpy.context.scene.fresing.last_message, job.message, job.pct,
                job.proc.poll() if job.proc else None, job.stderr_lines[-3:])
        return "wait"
    faces = mod("blender.faces")
    housing = find("HOUSING")
    check("faces painted in CAD come in painted",
          [st["key"] for st in sets_of("HOUSING")] == ["cad:#3355CC", "cad:#CC1A1A"]
          and faces.groups_on(housing) == ["Aluminum - Anodized Glossy (Blue) #3355CC", "Colour #CC1A1A"],
          faces.groups_on(housing))
    # view from straight above, the whole model in view; solid view shows the material colours
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((1, 0, 0, 0))
    r3d.view_location = Vector((0.45, 0.3, 0.0))
    r3d.view_distance = 1.4
    area.spaces.active.shading.type = "SOLID"
    area.spaces.active.shading.color_type = "MATERIAL"
    s = bpy.context.scene.fresing
    s.face_group = ""
    mod("blender.logic").ensure_group(s, "Red paint")
    g = s.groups["Red paint"]
    g.material, g.color = "paint_satin", "#FF0000"
    s.groups_index = next(i for i, x in enumerate(s.groups) if x.name == "Red paint")
    bpy.context.view_layer.objects.active = housing
    open_panel()
    return 1.0


@step
def s_paint_start():
    shot("01_cad_faces_and_panel")
    with override():
        res = bpy.ops.fresing.paint_faces("INVOKE_DEFAULT")       # the 'Paint faces…' button
    check("'Paint faces' starts", res == {"RUNNING_MODAL"} and bpy.context.scene.fresing.face_painting, res)
    return 0.5


@step
def s_click_cover():
    click(*top_of("COVER"))
    return 0.5


@step
def s_click_block():
    sets = sets_of("COVER")
    check("a click paints the whole face under the mouse",
          len(sets) == 1 and sets[0]["faces"] == [5] and sets[0]["group"] == "Red paint", sets)
    click(*top_of("BLOCK"))
    return 0.5


@step
def s_shift_click():
    check("a click on another part paints that one", [st["faces"] for st in sets_of("BLOCK")] == [[5]],
          sets_of("BLOCK"))
    shot("02_painted")
    click(*top_of("BLOCK"), shift=True)
    return 0.5


@step
def s_side_panel_click():
    check("Shift+click: back to the look of the part", sets_of("BLOCK") == [], sets_of("BLOCK"))
    win, area, region, sb = ui()
    before = sets_of("COVER")
    # on the side panel, not on the model: its empty right margin. The middle hit whatever button the layout put
    # there (the Wear slider of 0.2.39 moved the rows), and that button's undo step broke the undo check below
    click(sb.x + sb.width - 3, sb.y + 40)
    check("a click on the side panel paints nothing", sets_of("COVER") == before
          and bpy.context.scene.fresing.face_painting)
    return 0.5


@step
def s_enter():
    win, area, region, sb = ui()
    key("RET", region.x + 300, region.y + 300)
    return 0.5


@step
def s_after():
    s = bpy.context.scene.fresing
    check("Enter ends painting", not s.face_painting)
    cover = find("COVER")
    faces = mod("blender.faces")
    check("the painted face has the group's material", faces.groups_on(cover) == ["Red paint"]
          and cover.material_slots[1].material.name == "FR Red paint", faces.groups_on(cover))
    with override():
        res = bpy.ops.ed.undo()
    check("undo takes the painting back", res == {"FINISHED"} and sets_of("COVER") == [], sets_of("COVER"))
    with override():
        bpy.ops.ed.redo()
    check("redo brings it again", [st["faces"] for st in sets_of("COVER")] == [[5]], sets_of("COVER"))
    bpy.context.view_layer.objects.active = find("COVER")
    return 1.0


@step
def s_final_shot():
    shot("03_after_redo")
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
        win, area, region, _sb = ui()                    # events keep the import's timer going
        win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7,
                           y=region.y + 300)
        return 1.0
    _w[0] = 0.0
    _i[0] += 1
    return r


bpy.app.timers.register(driver, first_interval=3.0, persistent=True)
