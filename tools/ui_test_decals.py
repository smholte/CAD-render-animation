"""Real-app test, decals (task 0024): 3 Looks > Logos & stickers. 'Add decal…' and a real click on the
model, a click on the side panel while placing, 'Move with the mouse' (mouse, wheel turns, Ctrl+wheel
sizes, click puts it down, Esc puts it back), undo/redo, a text decal on one copy only.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_decals.py
Screenshots and ui_test_decals.log go to $UITEST_OUT (default ~/fresing_ui_test_decals).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_decals"))
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data", "test_decals_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_decals.log"), "w")
RESULTS = []
STATE: dict = {}


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
    hits = sorted((o for o in bpy.context.scene.objects if o.get("fr_name") == name and o.get("fr_kind") == "part"),
                  key=lambda o: o.get("fr_uid"))
    return hits[n] if len(hits) > n else None


def to_window(p):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(p))
    return int(region.x + co.x), int(region.y + co.y)


def top_of(name, n=0, dx=0.0, dy=0.0):
    """Window position of a spot on a part's top face (view from straight above)."""
    lo, hi = mod("blender.build").world_bounds([find(name, n)])
    return to_window(((lo[0] + hi[0]) / 2 + dx, (lo[1] + hi[1]) / 2 + dy, hi[2]))


def event(kind, x, y, value="PRESS", **mods):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=kind, value=value, x=x, y=y, **mods)


def click(x, y):
    event("LEFTMOUSE", x, y)
    event("LEFTMOUSE", x, y, value="RELEASE")


def key(k, x, y, **mods):
    event(k, x, y, **mods)
    event(k, x, y, value="RELEASE", **mods)


def move(x, y):
    bpy.context.window_manager.windows[0].event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)


def decals_of(name, n=0):
    return mod("blender.decals").items_of(find(name, n))


def decal_objects():
    return [o for o in bpy.context.scene.objects if o.get("fr_kind") == "decal"]


def open_panels():
    for cls in (bpy.types.FRESING_PT_looks, bpy.types.FRESING_PT_decals):
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
        return "wait"
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d                 # straight down on the panel and the barrels
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Quaternion((1, 0, 0, 0))
    r3d.view_location = Vector((0.55, 0.15, 0.0))
    r3d.view_distance = 1.6
    area.spaces.active.shading.type = "SOLID"
    d = bpy.context.scene.fresing_decal
    d.kind, d.sticker = "STICKER", "WARN_GENERAL"
    bpy.context.view_layer.objects.active = find("PANEL")
    open_panels()
    check("the 'Logos & stickers' fold is in 3 Looks", hasattr(bpy.types, "FRESING_PT_decals")
          and bpy.types.FRESING_PT_decals.bl_parent_id == "FRESING_PT_looks")
    return 1.0


@step
def s_add_start():
    shot("01_before")
    with override():
        res = bpy.ops.fresing.decal_add("INVOKE_DEFAULT")            # the 'Add decal…' button
    check("'Add decal' waits for a click", res == {"RUNNING_MODAL"} and bpy.context.scene.fresing_decal.placing, res)
    return 0.5


@step
def s_side_panel_click():
    win, area, region, sb = ui()
    click(sb.x + sb.width // 2, sb.y + 40)                           # on the side panel, not on the model
    return 0.5


@step
def s_click_panel():
    check("a click on the side panel puts nothing on the model", decal_objects() == []
          and bpy.context.scene.fresing_decal.placing)
    STATE["spot"] = top_of("PANEL", dx=-0.08, dy=0.03)
    click(*STATE["spot"])
    return 0.8


@step
def s_added():
    d = bpy.context.scene.fresing_decal
    items = decals_of("PANEL")
    panel = find("PANEL")
    ok = len(items) == 1 and items[0].face == 5 and not d.placing
    check("a click puts the sticker on the face under the mouse", ok, [(it.name, it.face) for it in items])
    if not items:
        return 0.5
    it = items[0]
    world = panel.matrix_world @ Vector(it.anchor)
    lo, hi = mod("blender.build").world_bounds([panel])
    want = Vector(((lo[0] + hi[0]) / 2 - 0.08, (lo[1] + hi[1]) / 2 + 0.03, hi[2]))
    check("its centre is where it was clicked", (world - want).length < 0.004, (tuple(world), tuple(want)))
    obs = decal_objects()
    check("it shows on the model, as a child of the part", len(obs) == 1 and obs[0].parent == panel
          and d.active == it.key and bpy.context.view_layer.objects.active == panel)
    STATE["anchor"] = tuple(it.anchor)
    STATE["key"] = it.key
    shot("02_added")
    with override():
        res = bpy.ops.fresing.decal_move("INVOKE_DEFAULT", key=it.key)   # 'Move with the mouse'
    check("'Move with the mouse' starts", res == {"RUNNING_MODAL"}, res)
    x, y = top_of("PANEL", dx=0.05, dy=-0.02)
    move(x - 10, y)
    move(x, y)
    return 0.5


@step
def s_turn_and_size():
    it = decals_of("PANEL")[0]
    STATE["moved"] = tuple(it.anchor)
    STATE["width"] = it.width
    x, y = top_of("PANEL", dx=0.05, dy=-0.02)
    event("WHEELUPMOUSE", x, y)                      # a wheel step is one PRESS (no release)
    event("WHEELUPMOUSE", x, y, ctrl=True)
    return 0.5


@step
def s_put_down():
    it = decals_of("PANEL")[0]
    moved = Vector(STATE["moved"]) - Vector(STATE["anchor"])
    check("it follows the mouse", abs(moved.x - 0.13) < 0.004 and abs(moved.y + 0.05) < 0.004, tuple(moved))
    check("the wheel turns it, Ctrl+wheel makes it bigger",
          abs(math.degrees(it.angle) - 15.0) < 0.01 and abs(it.width / STATE["width"] - 1.1) < 0.001,
          (math.degrees(it.angle), it.width / STATE["width"]))
    click(*top_of("PANEL", dx=0.05, dy=-0.02))
    return 0.5


@step
def s_esc_puts_back():
    STATE["placed"] = tuple(decals_of("PANEL")[0].anchor)
    with override():
        bpy.ops.fresing.decal_move("INVOKE_DEFAULT", key=STATE["key"])
    x, y = top_of("PANEL", dx=-0.1, dy=0.08)
    move(x - 10, y)
    move(x, y)
    return 0.5


@step
def s_esc():
    win, area, region, sb = ui()
    key("ESC", region.x + 300, region.y + 300)
    return 0.5


@step
def s_after_esc():
    it = decals_of("PANEL")[0]
    check("Esc puts it back where it was", (Vector(it.anchor) - Vector(STATE["placed"])).length < 1e-6,
          tuple(it.anchor))
    shot("03_moved_turned")
    with override():
        res = bpy.ops.ed.undo()
    check("undo takes the move back", res == {"FINISHED"} and decals_of("PANEL")
          and (Vector(decals_of("PANEL")[0].anchor) - Vector(STATE["anchor"])).length < 1e-6)
    with override():
        bpy.ops.ed.redo()
    check("redo brings it again", decals_of("PANEL")
          and (Vector(decals_of("PANEL")[0].anchor) - Vector(STATE["placed"])).length < 1e-6
          and len(decal_objects()) == 1)
    d = bpy.context.scene.fresing_decal
    d.kind, d.text, d.only_copy = "TEXT", "SN 0002", True
    with override():
        bpy.ops.fresing.decal_add("INVOKE_DEFAULT")
    return 0.5


@step
def s_click_barrel():
    click(*top_of("BARREL", 1))                     # the top of the second barrel
    return 0.8


@step
def s_one_copy():
    b0, b1 = find("BARREL", 0), find("BARREL", 1)
    on_b1 = [it.name for it in b1.fresing_decals]
    check("'Only this copy': the text goes on the clicked copy only",
          on_b1 == ["SN 0002"] and len(b1.data.fresing_decals) == 0 and not b0.fresing_decals
          and sorted(o.parent.name for o in decal_objects()) == sorted([b1.name, find("PANEL").name]), on_b1)
    bpy.context.scene.fresing_decal.only_copy = False
    shot("04_text_on_one_copy")
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
