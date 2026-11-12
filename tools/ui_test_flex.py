"""Real-app test, hoses and drag chains (task 0058): the hoses model – a click on a hose in the 3D view, Add hose,
the arm luffs (the hose's end stays on its fitting), a click on the cable, Add cable, Find and add all, a hose made
too short warns, Fit to the CAD pose; then the gantry – a click on one chain link (the click selects the whole
gantry, the button takes the link's row), Add drag chain, X moves (the last link stays at its bracket), undo and
redo, save and open again.

The clicks in the 3D view are real mouse events (so "Click selects: Subassembly" does its work); the buttons are
pressed the way the other real-app tests press them (the operator run like a button, with an undo step) after
checking that the button is not grey.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x1400x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_flex.py
Screenshots and ui_test_flex.log go to $UITEST_OUT (default ~/fresing_ui_test_flex).
"""

import math
import os
import subprocess
import time
import traceback

import bpy
import numpy as np
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_flex"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
CHAINS = os.path.join(DATA, "test_flex_chains_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_flex.log"), "w")
RESULTS = []
STATE = {}
MM = 0.001
PIVOT = Vector((0.1, 0.0, 0.6))                 # the arm turns about Y through here (tools/make_test_flex.py)
HOSE_END = Vector((1.0, 0.12, 0.6))             # end 1 of HYDRAULIC HOSE ARM on FITTING ARM, as drawn
LUFF = math.radians(15.0)


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


def can(_idname) -> bool:
    """The button is not grey."""
    group, op_name = _idname.split(".")
    with override():
        return bool(getattr(getattr(bpy.ops, group), op_name).poll())


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


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


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


def children_of(asm_name):
    build = mod("blender.build")
    home = named(asm_name)
    return [o for o in build.iter_parts(bpy.context.scene) if build.logical_parent(o) == home]


def flex():
    return mod("blender.flex")


def items():
    return bpy.context.scene.fresing.flex


def item(name):
    return flex().find(bpy.context.scene, name)


def said() -> str:
    return bpy.context.scene.fresing.last_message


def spot_on(part):
    """A window pixel where a click hits ``part`` and nothing in front of it: the middle of one of its faces that
    looks at the viewer. None when the view shows no such face."""
    win, area, region, sb = ui()
    rv3d = region.data
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    me, mw = part.data, part.matrix_world
    best = None
    for poly in list(me.polygons)[::max(1, len(me.polygons) // 300)]:
        p = mw @ poly.center
        co = view3d_utils.location_3d_to_region_2d(region, rv3d, p)
        if co is None or not (120 < co.x < region.width - sb.width - 60 and 80 < co.y < region.height - 120):
            continue
        along = view3d_utils.region_2d_to_vector_3d(region, rv3d, co).normalized()
        facing = -(mw.to_3x3() @ poly.normal).normalized().dot(along)
        if facing < 0.6:
            continue
        if best is not None and facing <= best[0]:
            continue
        # a click takes the nearest part within a few pixels of the mouse: the part must be alone there
        if all(_first_hit(sc, dg, region, rv3d, co + Vector(d)) == part
               for d in ((0, 0), (ROUND, 0), (-ROUND, 0), (0, ROUND), (0, -ROUND))):
            best = (facing, int(round(region.x + co.x)), int(round(region.y + co.y)))
    return best[1:] if best else None


ROUND = 7                                       # pixels round the mouse that must show the same part


def _first_hit(sc, dg, region, rv3d, co):
    """The part seen at a pixel of the 3D view (None: the background)."""
    along = view3d_utils.region_2d_to_vector_3d(region, rv3d, co).normalized()
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co) - along * 50.0
    hit, _loc, _n, _i, ob, _m = sc.ray_cast(dg, origin, along)
    return ob.original if hit and ob is not None else None


def view(location, distance, turn=35.0, tilt=62.0):
    """Look at ``location`` from the front left, a little from above."""
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = (Quaternion((0, 0, 1), math.radians(-turn)) @ Quaternion((1, 0, 0), math.radians(tilt)))
    r3d.view_location = Vector(location)
    r3d.view_distance = distance
    area.spaces.active.shading.type = "SOLID"
    redraw()


def open_panel():
    """The panel sits far down the side panel, closed. For the pictures: a copy of it, open, right under 1 Import
    (panels are ordered by bl_order, then by when they were registered)."""
    if hasattr(bpy.types, "FRESING_PT_flex_shot"):
        return
    base = mod("blender.ui_flex").FRESING_PT_flex
    bpy.utils.register_class(type("FRESING_PT_flex_shot", (base,), {
        "bl_idname": "FRESING_PT_flex_shot", "bl_parent_id": "", "bl_options": set(), "bl_order": 0}))


def drawn(part):
    """The part as it is drawn now (its modifier applied): world points (n, 3)."""
    e = part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(e.data.vertices) * 3, np.float32)
    e.data.vertices.foreach_get("co", co)
    w = np.array(e.matrix_world, dtype=float)
    return co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3]


def tube_ends(part):
    """The middles of the drawn tube's first and last ring."""
    rings = drawn(part).reshape(-1, flex().SIDES, 3).mean(axis=1)
    return rings[0], rings[-1]


def gap(a, b) -> float:
    """The smallest distance between the drawn points of two parts (metres)."""
    pa, pb = drawn(a), drawn(b)
    return float(np.sqrt(((pa[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2)).min())


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
        res = bpy.ops.fresing.import_step(filepath=HOSES, quality="normal")
    log("import", res, said())
    return 1.0


@step
def s_wait():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    view((0.6, 0.15, 0.35), 2.6)
    open_panel()
    made = flex().set_up_test_hoses(sc)            # the joints "Luff" and "Slide" and the cylinder …
    while len(items()):
        flex().remove(sc, 0)                       # … and no hose yet: that is the user's work, below
    check("the hoses model: joints made, nothing in the list", made["joints"] == ["Luff", "Slide"]
          and len(items()) == 0 and mod("blender.ui_flex").FRESING_PT_flex.poll(bpy.context))
    check("click selects: Subassembly (as installed)", sc.fresing.pick_mode == "SUBASSEMBLY", sc.fresing.pick_mode)
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
    redraw()
    wiggle()
    return 1.5


@step
def s_empty():
    sidebar_shot("panel4_flex_empty", 1300)
    check("nothing selected: Add hose and Add drag chain are grey, Find is not",
          not can("fresing.flex_add_hose") and not can("fresing.flex_add_chain") and can("fresing.flex_find")
          and not can("fresing.flex_remove"))
    spot = spot_on(named("HYDRAULIC HOSE ARM"))
    check("the hose shows in the view", spot is not None)
    if spot:
        click(*spot)
    return 1.0


@step
def s_add_hose():
    sc = bpy.context.scene
    hose = named("HYDRAULIC HOSE ARM")
    with override():
        active, chosen = bpy.context.view_layer.objects.active, list(bpy.context.selected_objects)
    check("a click on the hose in the view selects it", active == hose and chosen == [hose],
          f"active {active.name if active else None}, {len(chosen)} selected")
    ok = can("fresing.flex_add_hose")
    r = op("fresing.flex_add_hose") if ok else None
    it = item("HYDRAULIC HOSE ARM")
    check("Add hose: the hose is in the list and follows the motion", ok and r == {"FINISHED"} and len(items()) == 1
          and it is not None and it.kind == "HOSE" and flex().status(sc, it)[1] == "OK", said())
    check("its ends were found: on the valve block's fitting and on the arm's",
          it is not None and it.a_part == named("FITTING VALVE C") and it.b_part == named("FITTING ARM"))
    mod("blender.joints").set_value(mod("blender.joints").find(sc, "Luff"), LUFF)       # the arm's tip goes up
    bpy.context.view_layer.update()
    view((0.78, 0.3, 0.5), 1.3)                             # close on the cable (10 mm thick) for the next click
    wiggle()
    return 1.5


@step
def s_hose_follows():
    hose = named("HYDRAULIC HOSE ARM")
    turned = Quaternion((0, -1, 0), LUFF) @ (HOSE_END - PIVOT) + PIVOT        # where the arm's fitting is now
    first, last = tube_ends(hose)
    off = float(np.linalg.norm(last - np.array(turned)))
    check("Luff 15 degrees: the hose's end is on the arm's fitting", off < 0.1 * MM and turned.z > 0.8,
          f"{off * 1000:.4f} mm off, fitting at z {turned.z * 1000:.0f} mm")
    off0 = float(np.linalg.norm(first - np.array((0.43, -0.07, 0.22))))
    check("… and its other end still on the valve block", off0 < 0.1 * MM, f"{off0 * 1000:.4f} mm off")
    shot("01_hose_follows")
    spot = spot_on(named("CABLE"))
    check("the cable shows in the view", spot is not None)
    if spot:
        click(*spot)
    return 1.0


@step
def s_add_cable():
    sc = bpy.context.scene
    with override():
        active = bpy.context.view_layer.objects.active
    check("a click on the cable selects it", active == named("CABLE"), active.name if active else "nothing")
    r = op("fresing.flex_add_hose", soft=True) if can("fresing.flex_add_hose") else None
    it = item("CABLE")
    check("Add cable: in the list, soft", r == {"FINISHED"} and it is not None and len(items()) == 2
          and abs(it.stiffness - 0.2) < 1e-6 and it.stiffness < item("HYDRAULIC HOSE ARM").stiffness, said())
    check("the cable's ends: on the slide's gland and on the arm's",
          it is not None and {it.a_part, it.b_part} == {named("SLIDE GLAND"), named("CABLE GLAND ARM")})
    r = op("fresing.flex_find", add=True)
    check("Find and add all: the two hoses of the cylinder come too", r == {"FINISHED"} and len(items()) == 4
          and item("HYDRAULIC HOSE CYL A") is not None and item("HYDRAULIC HOSE CYL B") is not None, said())
    mod("blender.joints").set_value(mod("blender.joints").find(sc, "Slide"), 0.1)
    bpy.context.view_layer.update()
    wiggle()
    return 1.5


@step
def s_all_follow():
    sc = bpy.context.scene
    worst = 0.0
    for it in items():
        first, last = tube_ends(it.part)
        for got, part, point in ((first, it.a_part, it.a_point), (last, it.b_part, it.b_point)):
            worst = max(worst, float(np.linalg.norm(got - np.array(part.matrix_world @ Vector(point)))))
    check("arm up, slide out: every end of the four is on its part", worst < 0.1 * MM, f"{worst * 1000:.4f} mm")
    check("all four follow the motion", all(flex().status(sc, it)[1] == "OK" for it in items()),
          ", ".join(flex().status(sc, it)[0] for it in items()))
    sc.fresing.flex_index = flex().index_of(sc, item("HYDRAULIC HOSE ARM"))
    item("HYDRAULIC HOSE ARM").length = 0.6                   # shorter than its ends are apart
    redraw()
    wiggle()
    return 1.5


@step
def s_warning():
    sc = bpy.context.scene
    it = item("HYDRAULIC HOSE ARM")
    text, level = flex().status(sc, it)
    ui_flex = mod("blender.ui_flex")
    check("a hose made too short warns, in the list and in the header", level == "WARN"
          and text.startswith("too short in this pose: needs ") and ui_flex.short_status(sc, it) == ("too short", True)
          and ui_flex.counts(sc) == ("1 of 4", True), text)
    sidebar_shot("panel4_flex_warning", 1300)
    r = op("fresing.flex_fit")
    it = item("HYDRAULIC HOSE ARM")
    check("Fit to the CAD pose: the drawn length again, no warning", r == {"FINISHED"}
          and abs(it.length - it.cad_length) < 1e-6 and flex().status(sc, it)[1] == "OK", f"{it.length * 1000:.1f} mm")
    redraw()
    wiggle()
    return 1.0


@step
def s_hoses_shot():
    sidebar_shot("panel4_flex", 1300)
    shot("02_hoses")
    with override():
        bpy.ops.wm.read_homefile(app_template="fresing_render")          # a new project for the gantry
    return 2.0


@step
def s_import_chains():
    with override():
        res = bpy.ops.fresing.import_step(filepath=CHAINS, quality="normal")
    log("import", res, said())
    return 1.0


@step
def s_wait_chains():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    view((0.0, 0.05, 0.25), 1.5, turn=25.0, tilt=55.0)       # close on the beam: the X chain lies on it
    open_panel()
    made = flex().set_up_test_chains(sc)
    while len(items()):
        flex().remove(sc, 0)
    check("the gantry: joints X, Y, Z made, nothing in the list", made["joints"] == ["X", "Y", "Z"]
          and len(items()) == 0)
    bracket = named("CHAIN BRACKET X MOVING")                # how near the chain's last link is drawn to it
    STATE["gap0"] = min(gap(o, bracket) for o in children_of("CHAIN X.ASM"))
    STATE["links"] = [o.name for o in children_of("CHAIN X.ASM")]
    with override():
        bpy.ops.ed.undo_push(message="Set-up")              # so Undo, further down, comes back to here
    redraw()
    wiggle()
    return 1.5


@step
def s_click_link():
    link = next((o for o in children_of("CHAIN X.ASM") if spot_on(o)), None)
    check("a link of the X chain shows in the view", link is not None)
    if link is not None:
        STATE["link"] = link.name
        click(*spot_on(link))
    return 1.0


@step
def s_add_chain():
    sc = bpy.context.scene
    link = bpy.data.objects.get(STATE.get("link", ""))
    with override():
        active, chosen = bpy.context.view_layer.objects.active, len(bpy.context.selected_objects)
    check("a click on one link: it is the active part, its whole subassembly is selected",
          link is not None and active == link and chosen > 18,
          f"{chosen} selected, active {active.name if active else None}, clicked {STATE.get('link')}")
    r = op("fresing.flex_add_chain") if can("fresing.flex_add_chain") else None
    it = item("CHAIN X.ASM")
    check("Add drag chain: the link's whole row is one chain", r == {"FINISHED"} and len(items()) == 1
          and it is not None and len(it.links) == 18 and flex().status(sc, it)[1] == "OK", said())
    check("fixed end on the beam's bracket, moving end on the carriage's; pitch 40 mm, bend radius 80 mm",
          it is not None and it.a_part == named("CHAIN BRACKET X FIXED") and it.b_part == named("CHAIN BRACKET X MOVING")
          and abs(it.pitch - 0.04) < 1e-5 and abs(it.radius - 0.08) < 1e-5,
          f"{it.pitch * 1000:.3f} / {it.radius * 1000:.3f} mm" if it else "")
    mod("blender.joints").set_value(mod("blender.joints").find(sc, "X"), 0.12)
    bpy.context.view_layer.update()
    wiggle()
    return 1.5


def last_link_ok(where: str) -> None:
    """The chain's moving end is on its bracket: the last pin exactly, the last link as near it as drawn."""
    sc = bpy.context.scene
    it = item("CHAIN X.ASM")
    pins = flex().pins_now(sc, it)
    off = float(np.linalg.norm(pins[-1] - np.array(it.b_part.matrix_world @ Vector(it.b_point))))
    chord = np.linalg.norm(np.diff(pins, axis=0), axis=1)
    last = flex().link_objects(it)[-1]
    g = gap(last, named("CHAIN BRACKET X MOVING"))
    check(f"{where}: the last link stays at its bracket, every link 40 mm from the next",
          off < 1e-6 and abs(g - STATE["gap0"]) < 0.05 * MM and float(np.abs(chord - 0.04).max()) < 1e-6
          and it.problem == "", f"pin {off * 1e6:.2f} um off, gap {g * 1000:.3f} mm (drawn {STATE['gap0'] * 1000:.3f})")


@step
def s_chain_follows():
    moved = named("CHAIN BRACKET X MOVING").matrix_world.translation.x
    last_link_ok("X at +120 mm")
    check("(the carriage did move)", abs(named("X.ASM").matrix_world.translation.x - 0.12) < 1e-5, f"{moved:.4f}")
    sidebar_shot("panel4_flex_chain", 1300)
    shot("03_chain")
    key("Z", ctrl=True)                                     # undo: Add drag chain
    return 1.5


@step
def s_undone():
    links = [bpy.data.objects.get(n) for n in STATE["links"]]
    check("Undo takes the chain off the list: the links show their CAD shape", len(items()) == 0
          and all(o is not None and o.modifiers.get(flex().MOD) is None for o in links), f"{len(items())} in the list")
    key("Z", ctrl=True, shift=True)                         # redo
    return 1.5


@step
def s_redone():
    sc = bpy.context.scene
    it = item("CHAIN X.ASM")
    check("Redo brings it back", it is not None and len(it.links) == 18 and len(items()) == 1)
    if it is not None:
        mod("blender.joints").set_value(mod("blender.joints").find(sc, "X"), -0.1)
        bpy.context.view_layer.update()
    wiggle()
    return 1.5


@step
def s_after_redo():
    if item("CHAIN X.ASM") is not None:
        last_link_ok("after undo and redo, X at -100 mm")
    else:
        check("after undo and redo: the chain follows", False, "no chain")
    path = os.path.join(OUT, "flex_project.blend")
    STATE["blend"] = path
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    it = item("CHAIN X.ASM")
    check("saved and opened again: the chain is in the list", it is not None and len(it.links) == 18)
    if it is not None:
        mod("blender.joints").set_value(mod("blender.joints").find(sc, "X"), 0.05)
        bpy.context.view_layer.update()
    wiggle()
    return 1.5


@step
def s_reopened_follows():
    if item("CHAIN X.ASM") is not None:
        last_link_ok("opened again, X at +50 mm")
    else:
        check("opened again: the chain follows", False, "no chain")
    r = op("fresing.flex_remove") if can("fresing.flex_remove") else None
    check("Remove: the list is empty, the links show their CAD shape", r == {"FINISHED"} and len(items()) == 0
          and all(o.modifiers.get(flex().MOD) is None for o in children_of("CHAIN X.ASM")), said())
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
