"""Real-app test, welds (task 0319): 3 Looks > Welds. 'Add weld…' and real clicks on the model – the base plate's top
(1 of 2), Enter, the fin's side (2 of 2), the seam shown, Enter makes the weld; a click on the side panel while picking
picks nothing; Esc cancels a second pick; the right-click entry starts the picker with the clicked face; undo / redo.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_welds.py
Screenshots and ui_test_welds.log go to $UITEST_OUT (default ~/fresing_ui_test_welds).
"""

import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_welds"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_weldment.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_welds.log"), "w")
RESULTS = []
STATE: dict = {}

TOP = (0.10, 0.26, 0.012)          # the base plate's top, in front of the fin seen from +y
SIDE = (0.09, 0.155, 0.07)         # the fin's +y side (the gusset stands at x 146..154 mm: clear of it)


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


def to_window(p):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(p))
    return int(region.x + co.x), int(region.y + co.y)


def event(kind, x, y, value="PRESS", **mods):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=kind, value=value, x=x, y=y, **mods)


def click(x, y, **mods):
    event("LEFTMOUSE", x, y, **mods)
    event("LEFTMOUSE", x, y, value="RELEASE", **mods)


def key(k, x, y, **mods):
    event(k, x, y, **mods)
    event(k, x, y, value="RELEASE", **mods)


def welds():
    return mod("blender.welds")


def picker():
    return mod("blender.ops_welds").picker()


def items():
    return list(bpy.context.scene.fresing_welds.items)


def weld_objects():
    return [o for o in bpy.context.scene.objects if o.get("fr_kind") in ("weld", "weld_heat")]


STEPS = []


def step(fn):
    STEPS.append(fn)
    return fn


@step
def s_start():
    win, area, region, sb = ui()
    key("ESC", region.x + 300, region.y + 300)          # closes the splash screen
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
    if bpy.context.scene.fresing.model_count == 0:
        return "wait"
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d                  # from the front (+y) and above: the plate's top and the fin's side
    r3d.view_perspective = "PERSP"
    eye = Vector((0.15, 0.75, 0.45))
    target = Vector((0.15, 0.17, 0.03))
    r3d.view_rotation = (eye - target).to_track_quat("Z", "Y")
    r3d.view_location = target
    r3d.view_distance = (eye - target).length
    area.spaces.active.shading.type = "SOLID"
    mod("blender.panels").open_to("FRESING_PT_welds")
    check("the Welds panel is in 3 Looks", hasattr(bpy.types, "FRESING_PT_welds")
          and bpy.types.FRESING_PT_welds.bl_parent_id == "FRESING_PT_looks")
    return 1.0


@step
def s_add_start():
    shot("01_before")
    with override():
        res = bpy.ops.fresing.weld_add("INVOKE_DEFAULT")              # the 'Add weld…' button
    s = bpy.context.scene.fresing_welds
    check("'Add weld' waits for the first part's faces", res == {"RUNNING_MODAL"} and s.picking == "A", res)
    return 0.5


@step
def s_side_panel_click():
    win, area, region, sb = ui()
    click(sb.x + sb.width // 2, sb.y + 40)                            # on the side panel, not on the model
    return 0.5


@step
def s_click_top():
    pk = picker()
    check("a click on the side panel picks no face", pk is not None and not pk.faces_a)
    click(*to_window(TOP))
    return 0.8


@step
def s_top_picked():
    pk = picker()
    base = welds().part_named(bpy.context.scene, "BASE PLATE")
    want = welds().face_at(base, TOP, (0, 0, 1))
    check("the click picks the base plate's top face", pk is not None and pk.part_a == base.name
          and pk.faces_a == {want}, (pk.part_a if pk else None, pk.faces_a if pk else None, want))
    shot("02_first_part")
    win, area, region, sb = ui()
    key("RET", *to_window(TOP))                                       # Enter: on to the second part
    return 0.8


@step
def s_step_b():
    s = bpy.context.scene.fresing_welds
    check("Enter goes on to the second part", s.picking == "B" and picker().step == "B", s.picking)
    click(*to_window(TOP))                                            # the first part again: refused
    return 0.6


@step
def s_refused():
    pk = picker()
    check("a click on the first part in step 2 picks nothing", not pk.faces_b and pk.step == "B")
    click(*to_window(SIDE))
    return 1.0


@step
def s_side_picked():
    pk = picker()
    s = bpy.context.scene.fresing_welds
    lens = [round(x.length * 1000) for x in s.preview]
    check("the fin's side is picked and the seam shows (200 mm)", pk.part_b and lens == [200], lens)
    shot("03_seam_shown")
    key("RET", *to_window(SIDE))                                      # Enter: Done
    return 1.0


@step
def s_done():
    its = items()
    s = bpy.context.scene.fresing_welds
    ok = len(its) == 1 and s.picking == "" and [round(x.length * 1000) for x in its[0].seams] == [200]
    check("Done makes the weld with its one seam", ok, [(it.name, len(it.seams)) for it in its])
    check("the bead and its heat zone are on the first part", len(weld_objects()) == 2
          and all(o.parent is not None and o.parent.get("fr_name") == "BASE PLATE" for o in weld_objects()))
    shot("04_weld_made")
    return 0.5


@step
def s_esc_start():
    with override():
        bpy.ops.fresing.weld_add("INVOKE_DEFAULT")
    click(*to_window(TOP))
    return 0.6


@step
def s_esc():
    key("ESC", *to_window(TOP))
    return 0.8


@step
def s_esc_done():
    s = bpy.context.scene.fresing_welds
    check("Esc cancels: no new weld, the picker is gone", len(items()) == 1 and s.picking == ""
          and picker() is None, (len(items()), s.picking))
    return 0.5


@step
def s_ctx_start():
    base = welds().part_named(bpy.context.scene, "BASE PLATE")
    with override():
        res = bpy.ops.fresing.ctx_weld("INVOKE_DEFAULT", part=base.name, point=TOP)   # 'Weld to another part…'
    pk = picker()
    want = welds().face_at(base, TOP, (0, 0, 1))
    check("'Weld to another part…' starts with the right-clicked face", res == {"RUNNING_MODAL"} or pk is not None)
    check("… which is the first part's face", pk is not None and pk.faces_a == {want},
          pk.faces_a if pk else None)
    return 0.5


@step
def s_ctx_cancel():
    win, area, region, sb = ui()
    with override():
        bpy.ops.fresing.weld_cancel()
    return 0.6


@step
def s_undo():
    check("Cancel stops the picker", picker() is None and bpy.context.scene.fresing_welds.picking == "")
    with override():
        bpy.ops.ed.undo()
    return 1.0


@step
def s_undone():
    check("Undo takes the weld away", len(items()) == 0 and not weld_objects(), (len(items()), len(weld_objects())))
    with override():
        bpy.ops.ed.redo()
    return 1.0


@step
def s_redone():
    check("Redo brings it back", len(items()) == 1 and len(weld_objects()) == 2,
          (len(items()), len(weld_objects())))
    it = items()[0] if items() else None
    if it is not None:
        it.size = 0.007                                               # a change after redo rebuilds the bead
    check("a change after redo rebuilds it", it is not None and not it.lost and len(weld_objects()) == 2)
    shot("05_redo")
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
