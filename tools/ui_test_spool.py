"""Real-app test, drums and carousels (task 0080): the spooling test model (test_spool.step) with its joints and its
two cables made by script, then with real mouse clicks in 4 Motion > Drums and carousels: Add drum (a click on the
button, the hover highlight on the drum, a click on the drum in the 3D view) – the drum is in the list, warns about
the fleet angle, turns with the wire's joint and draws the wire on it; "This joint follows the layer" (a click on the
button, "level" typed into its search, Enter) – the level wind goes along with the wraps and the warning is gone;
Add carousel by a click on the turntable – it turns with the power cable; undo and redo of that; the arm follows the
layer; the carousel switched off and on by a click on its tick box in the list; Build animation; save and open again
(the drawn rope, the tables and the followers are still there, at the same places).

Where a button is on the screen is not known to a script. The test draws a magenta strip right above the button it
wants (only while it looks for it) and finds that strip in a screenshot; the chosen row of the list is found by its
highlight colour (as tools/ui_test_paths.py).

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_spool.py
Screenshots and ui_test_spool.log go to $UITEST_OUT (default ~/fresing_ui_test_spool).
"""

import math
import os
import subprocess
import time
import traceback
import types

import bpy
import numpy as np
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_spool"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
MODEL = os.path.join(DATA, "test_spool.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_spool.log"), "w")
RESULTS = []
STATE = {"mark": ""}
MM = 0.001
END_FRAME = 201                                 # 8 s at 25 fps: 6 m of wire and 6 m of cable have run
R_LAYER3 = 0.194641                             # the wire's layer where the CAD rope leaves the drum (make_test_spool)


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[UITEST]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    log(("PASS " if ok else "FAIL ") + name + (f" ({detail})" if detail != "" else ""))


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


def sidebar_pixels():
    """The side panel as it is on the screen now: (pixels (h, w, 3), the window x of its left column, the window
    y of its top row), or None."""
    win, area, region, sb = ui()
    full = os.path.join(OUT, "_full.png")
    subprocess.run(["import", "-window", "root", full], check=False)
    top = win.height - (sb.y + sb.height)
    raw = subprocess.run(["convert", full, "-crop", f"{sb.width}x{sb.height}+{sb.x}+{top}", "+repage", "-depth", "8",
                          "rgb:-"], check=False, capture_output=True).stdout
    if len(raw) != sb.width * sb.height * 3:
        log("sidebar_pixels: got", len(raw), "bytes for", sb.width, "x", sb.height)
        return None
    return np.frombuffer(raw, np.uint8).reshape(sb.height, sb.width, 3).astype(int), sb.x, sb.y + sb.height - 1


def find_marker():
    """The magenta strip: {top, bottom, left, right} in side-panel pixels (from its top left corner) with the pixels
    themselves, or None."""
    got = sidebar_pixels()
    if got is None:
        return None
    img, x0, y_top = got
    m = (img[:, :, 0] > 200) & (img[:, :, 1] < 70) & (img[:, :, 2] > 200)
    rows = np.flatnonzero(m.sum(axis=1) > 40)
    if not len(rows):
        return None
    cols = np.flatnonzero(m[rows[0]:rows[-1] + 1].any(axis=0))
    return {"top": int(rows[0]), "bottom": int(rows[-1]), "left": int(cols[0]), "right": int(cols[-1]),
            "img": img, "x0": x0, "y_top": y_top}


def find_chosen_row(mark):
    """The highlighted (chosen) row of the first list below the marker: (the pixel row of its middle, the height
    of a row, the pixel column of its left end), or None."""
    theme = bpy.context.preferences.themes[0].user_interface.wcol_list_item.inner_sel
    colour = np.array([int(round(c * 255)) for c in theme[:3]])
    img = mark["img"]
    close = np.abs(img - colour).max(axis=2) <= 12
    wide = close.sum(axis=1) > 80
    wide[:mark["bottom"] + 4] = False
    rows = np.flatnonzero(wide)
    if not len(rows):
        return None
    last = rows[0]
    while last + 1 < len(wide) and wide[last + 1]:
        last += 1
    cols = np.flatnonzero(close[rows[0]:last + 1].any(axis=0))
    return (int(rows[0]) + int(last)) // 2, int(last) - int(rows[0]) + 1, int(cols[0])


def button_spot(mark, scale=1.0, where=0.5):
    """The window pixel of the button right under the marker: ``scale`` = its row's scale_y, ``where`` = how far
    along the row (0.25: the left one of two buttons, 0.75: the right one)."""
    unit = max(16, mark["bottom"] - mark["top"] + 1)
    x = mark["x0"] + mark["left"] + int(where * (mark["right"] - mark["left"]))
    y = mark["y_top"] - (mark["bottom"] + 3 + int(0.5 * scale * unit))
    return x, y


def click(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="PRESS", x=x, y=y)
    win.event_simulate(type="LEFTMOUSE", value="RELEASE", x=x, y=y)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x + 3, y=y + 3)


def move(x, y):
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x - 2, y=y - 2)
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)


def key(k, ctrl=False, shift=False):
    win, area, region, _sb = ui()
    x, y = region.x + region.width // 2, region.y + region.height // 2
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=x, y=y)
    win.event_simulate(type=k, value="PRESS", x=x, y=y, ctrl=ctrl, shift=shift)
    win.event_simulate(type=k, value="RELEASE", x=x, y=y, ctrl=ctrl, shift=shift)


def type_text(text, x, y):
    """Typing into the search field of an open popup (the mouse stays where it is)."""
    win = bpy.context.window_manager.windows[0]
    for ch in text:
        win.event_simulate(type=ch.upper(), value="PRESS", x=x, y=y, unicode=ch)
        win.event_simulate(type=ch.upper(), value="RELEASE", x=x, y=y)


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name, k=0):
    found = [o for o in bpy.context.scene.objects if o.get("fr_name") == name]
    return found[k] if len(found) > k else None


def spool():
    return mod("blender.spool")


def paths():
    return mod("blender.paths")


def joints():
    return mod("blender.joints")


def S():
    return mod("core.spool")


def said() -> str:
    return bpy.context.scene.fresing.last_message


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def value(name) -> float:
    j = joints().find(bpy.context.scene, name)
    return joints().get_value(j) if j is not None else float("nan")


def pay(cable, metres):
    """The cable's speed joint at ``metres`` paid out (as moving its slider), the cable solved again."""
    sc = bpy.context.scene
    joints().set_value(joints().find(sc, paths().find(sc, cable).joint), metres)
    update()
    paths().refresh(sc)
    update()


def first_hit(sc, dg, region, rv3d, co):
    """The part seen at a pixel of the 3D view (None: the background)."""
    along = view3d_utils.region_2d_to_vector_3d(region, rv3d, co).normalized()
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co) - along * 50.0
    hit, _loc, _n, _i, ob, _m = sc.ray_cast(dg, origin, along)
    return ob.original if hit and ob is not None else None


ROUND = 7                                       # pixels round the mouse that must show the same part


def spot_on(part):
    """A window pixel where a click hits ``part`` and nothing else within a few pixels: the middle one of all such
    pixels on a grid over the part's box on the screen. None when the view shows none."""
    win, area, region, sb = ui()
    rv3d = region.data
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    corners = [part.matrix_world @ Vector(c) for c in part.bound_box]
    co = [view3d_utils.location_3d_to_region_2d(region, rv3d, c) for c in corners]
    co = [c for c in co if c is not None]
    if not co:
        return None
    x_lo = max(80, int(min(c.x for c in co)))
    x_hi = min(region.width - sb.width - 40, int(max(c.x for c in co)))
    y_lo = max(80, int(min(c.y for c in co)))
    y_hi = min(region.height - 120, int(max(c.y for c in co)))
    good = []
    step_px = max(4, (x_hi - x_lo) // 60, (y_hi - y_lo) // 60)
    for x in range(x_lo, x_hi, step_px):
        for y in range(y_lo, y_hi, step_px):
            if first_hit(sc, dg, region, rv3d, Vector((x, y))) != part:
                continue
            if all(first_hit(sc, dg, region, rv3d, Vector((x + dx, y + dy))) == part
                   for dx, dy in ((ROUND, 0), (-ROUND, 0), (0, ROUND), (0, -ROUND))):
                good.append((x, y))
    if not good:
        return None
    g = np.array(good, dtype=float)
    k = int(np.argmin(np.linalg.norm(g - np.median(g, axis=0), axis=1)))
    return int(region.x + good[k][0]), int(region.y + good[k][1])


def view(location, distance, rotation=None):
    """Look at ``location``: from the front left, a little from above, or with ``rotation``."""
    win, area, region, sb = ui()
    r3d = area.spaces.active.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = rotation if rotation is not None else \
        (Quaternion((0, 0, 1), math.radians(-35.0)) @ Quaternion((1, 0, 0), math.radians(62.0)))
    r3d.view_location = Vector(location)
    r3d.view_distance = distance
    area.spaces.active.shading.type = "SOLID"
    redraw()


class _Marked:
    """The panel's layout, with a magenta strip drawn above the button ``STATE["mark"]`` names."""

    def __init__(self, real):
        self._real = real

    def __getattr__(self, name):
        return getattr(self._real, name)

    def operator(self, idname, **kw):
        if STATE["mark"] == idname:
            self._real.prop(bpy.context.window_manager, "fr_uitest_mark", text="")
        return self._real.operator(idname, **kw)


def open_panel():
    """The panel sits far down the side panel, closed. For the clicks and the pictures: a copy of it, open, right
    under 1 Import (panels are ordered by bl_order, then by when they were registered), which draws the magenta
    strip where ``STATE["mark"]`` says: "top" (above everything: for the list), "add" (above Add drum / Add
    carousel) or a button's operator."""
    if hasattr(bpy.types, "FRESING_PT_spools_shot"):
        return
    ui_spool = mod("blender.ui_spool")
    base = ui_spool.FRESING_PT_spools
    if not hasattr(bpy.types.WindowManager, "fr_uitest_mark"):
        bpy.types.WindowManager.fr_uitest_mark = bpy.props.FloatVectorProperty(
            subtype="COLOR", size=3, default=(1.0, 0.0, 1.0), min=0.0, max=1.0)

    def draw(self, context):
        if STATE["mark"] == "top":
            self.layout.prop(context.window_manager, "fr_uitest_mark", text="")
        base.draw(types.SimpleNamespace(layout=_Marked(self.layout)), context)

    bpy.utils.register_class(type("FRESING_PT_spools_shot", (base,), {
        "bl_idname": "FRESING_PT_spools_shot", "bl_parent_id": "", "bl_options": set(), "bl_order": 0,
        "draw": draw}))
    real = ui_spool._add_buttons

    def marked(layout, first):
        if STATE["mark"] == "add":
            layout.prop(bpy.context.window_manager, "fr_uitest_mark", text="")
        real(layout, first)

    ui_spool._add_buttons = marked


def evaluated_count(ob) -> int:
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return len(e.data.vertices) if e.type == "MESH" else -1


def rope_gap(sp, cable) -> float:
    """How far the free cable's start is from the rope drawn on the spool (metres)."""
    rope = sp.owner
    if rope is None:
        return 9.9
    e = rope.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(e.data.vertices) * 3, np.float32)
    e.data.vertices.foreach_get("co", co)
    if not len(co):
        return 9.9
    w = np.array(e.matrix_world, dtype=float)
    pts = co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3]
    start = np.array(paths().shape_now(bpy.context.scene, paths().find(bpy.context.scene, cable))[0], dtype=float)
    return float(np.linalg.norm(pts - start, axis=1).min())


def drawn_ok(sp) -> tuple:
    """(the spool's own rope draws something, the CAD coil draws nothing)."""
    rope = sp.owner
    return (rope is not None and rope.modifiers.get(spool().MOD) is not None and evaluated_count(rope) > 100,
            sp.coil is not None and evaluated_count(sp.coil) == 0)


def guide_off(sp) -> float:
    """How far the guide sheave's middle is from the circle of the turn being paid out (metres)."""
    sc = bpy.context.scene
    path = spool().path_of(sc, sp)
    fr = spool().frame_cad(sc, sp, {})
    g = np.linalg.inv(fr) @ np.r_[np.array(named("GUIDE SHEAVE").matrix_world.translation), 1.0]
    _phi, _a, r, _k = S().at(path, np.array([float(sp.wound) - spool().payout(sc, sp)]))
    return abs(math.hypot(g[0], g[1]) - float(r[0]))


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
    log("import", res, said())
    return 1.0


@step
def s_wait():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    J, P = joints(), paths()
    # the joints and the two cables as spool.set_up_test_model makes them (the spools come by clicks below)
    build = mod("blender.build")
    m = (build.model_root_of(named("DRUM.ASM")) or named("DRUM.ASM")).matrix_world

    def at(x, y, z):
        return m @ Vector((x * MM, y * MM, z * MM))

    def way(x, y, z):
        return (m.to_3x3() @ Vector((x, y, z))).normalized()

    with J._batch(sc):
        J.create(sc, "ROTATE", [named("DRUM.ASM")], at(0, 0, 450), way(0, 1, 0), name="Drum turn")
        J.create(sc, "SLIDE", [named("LEVEL WIND.ASM")], at(800, 0, 300), way(0, 1, 0), name="Level wind")
        J.create(sc, "ROTATE", [named("CAROUSEL.ASM")], at(3000, 0, 0), way(0, 0, 1), name="Carousel turn")
        J.create(sc, "ROTATE", [named("ARM.ASM")], at(4300, 0, 0), way(0, 0, 1), name="Arm slew")
    update()
    for cname, part, look in (("Wire", "WIRE ROPE", "ROPE"), ("Power cable", "POWER CABLE", "POWER")):
        item = P.add_cable(sc, cname)
        with P._quiet(item):
            item.look = look
        item["look_was"] = look
        P.read_cad(sc, item, named(part))
    sc.fresing.cables_index = [c.name for c in sc.fresing.cables].index("Wire")
    open_panel()
    ui_spool = mod("blender.ui_spool")
    check("the spooling model with its joints and the cables Wire and Power cable: the panel is there, no spool yet",
          len(sc.fresing.cables) == 2 and len(sc.fresing.spools) == 0 and ui_spool.FRESING_PT_spools.poll(bpy.context)
          and ui_spool.counts(sc) == ("–", False) and can("fresing.spool_add") and not can("fresing.spool_remove")
          and not can("fresing.spool_follower_add"), [c.name for c in sc.fresing.cables])
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
        bpy.ops.ed.undo_push(message="Set-up")
    view(np.array(named("WINCH DRUM").matrix_world.translation), 1.6)
    STATE["mark"] = "add"
    redraw()
    wiggle()
    return 1.5


@step
def s_click_add_drum():
    sidebar_shot("panel4_spools_empty", 700)
    mark = find_marker()
    check("the Add drum button is found in the side panel", mark is not None)
    if mark is not None:
        x, y = button_spot(mark, scale=1.5, where=0.25)
        log("Add drum click at", x, y, "marker rows", mark["top"], mark["bottom"])
        click(x, y)                                         # a real click on the button: its invoke starts the picker
    return 1.5


@step
def s_drum_hover():
    check("a mouse click on Add drum waits for a click on the drum, the status bar says so",
          mod("blender.hover").active() and len(bpy.context.scene.fresing.spools) == 0)
    spot = spot_on(named("WINCH DRUM"))
    STATE["spot"] = spot
    check("the drum shows in the view", spot is not None)
    if spot:
        move(*spot)
    return 1.0


@step
def s_drum_click():
    h = mod("blender.hover").current()
    check("the hover highlight shows the drum under the mouse", h is not None and h.part == named("WINCH DRUM").name
          and h.text == "Drum: WINCH DRUM" and not h.refused, h.text if h is not None else "no highlight")
    if STATE.get("spot"):
        log("drum click at", *STATE["spot"])
        click(*STATE["spot"])
    return 3.0


@step
def s_drum_added():
    sc = bpy.context.scene
    sp = spool().active(sc)
    check("a click on the drum: 'Drum' is in the list, on the wire, turned by the joint 'Drum turn', its CAD wire "
          "found", sp is not None and len(sc.fresing.spools) == 1 and sp.name == "Drum" and sp.kind == "DRUM"
          and sp.cable == "Wire" and sp.joint == "Drum turn" and not sp.made_joint and sp.coil == named("WIRE ON DRUM")
          and not mod("blender.hover").active(), said())
    if sp is None:
        return 0.5
    check("read from the drum: first layer at r 160 mm, 400 mm between the flanges, some metres on it",
          abs(sp.r1 - 0.160) < 1e-3 and abs(abs(sp.a_hi - sp.a_lo) - 0.4) < 1e-3 and sp.wound > 2.0,
          f"r1 {sp.r1 * 1000:.2f} mm, {abs(sp.a_hi - sp.a_lo) * 1000:.1f} mm, {sp.wound:.2f} m")
    text, icon = spool().status(sc, spool().active(sc))
    ui_spool = mod("blender.ui_spool")
    check("no level wind yet: the fleet angle warns, names the flange; in the header too", icon == "ERROR"
          and "fleet angle" in text.lower() and "flange" in text and ui_spool.counts(sc) == ("1 warning", True), text)
    rope_ok, coil_hidden = drawn_ok(spool().active(sc))
    check("the wire on the drum is drawn by the app, the CAD wire is hidden", rope_ok and coil_hidden,
          f"rope {rope_ok}, coil hidden {coil_hidden}")
    check("the wire's start is on the drum", paths().find(sc, "Wire").a_kind == "SPOOL"
          and joints().find(sc, "Drum turn").couple_table == "spool:Drum")
    pay("Wire", 1.0)
    turned = abs(value("Drum turn"))
    sp = spool().active(sc)
    check("1 m of wire paid out: the drum turns 1 m / r of its layer (294°), 1 m less on it",
          abs(turned * R_LAYER3 - 1.0) < 0.01 and abs(spool().payout(sc, sp) - 1.0) < 1e-6,
          f"{math.degrees(turned):.2f}°")
    gap = rope_gap(spool().active(sc), "Wire")
    check("… and the free wire starts where the wire drawn on the drum ends", gap < 0.011, f"{gap * 1000:.2f} mm")
    pay("Wire", 0.0)
    check("back at 0: the drum is back", abs(value("Drum turn")) < 1e-6, f"{math.degrees(value('Drum turn')):.4f}°")
    STATE["mark"] = "fresing.spool_follower_add"
    sc.fresing.last_message = ""                            # (its lines in 1 Import above would move the buttons)
    redraw()
    wiggle()
    return 1.0


@step
def s_click_follow():
    mark = find_marker()
    check("the button 'This joint follows the layer' is found in the side panel", mark is not None)
    if mark is not None:
        x, y = button_spot(mark)
        STATE["follow_at"] = (x, y)
        log("follow click at", x, y)
        click(x, y)                                         # its invoke opens a search of the joints
    return 1.5


@step
def s_type():
    x, y = STATE.get("follow_at", (0, 0))
    type_text("level", x, y)
    return 1.0


@step
def s_enter():
    shot("01_follow_search")
    x, y = STATE.get("follow_at", (0, 0))
    win = bpy.context.window_manager.windows[0]
    win.event_simulate(type="RET", value="PRESS", x=x, y=y)
    win.event_simulate(type="RET", value="RELEASE", x=x, y=y)
    return 1.5


@step
def s_followed():
    sc = bpy.context.scene
    sp = spool().active(sc)
    ok = sp is not None and len(sp.followers) == 1 and sp.followers[0].joint == "Level wind"
    check("'level' typed into its search, Enter: the level wind follows the layer, across the drum",
          ok and sp.followers[0].mode == "ACROSS" and joints().find(sc, "Level wind").couple_table == "spool:Drum",
          said())
    text, icon = spool().status(sc, spool().active(sc))
    check("… and the fleet angle warning is gone", icon == "CHECKMARK" and mod("blender.ui_spool").counts(sc)
          == ("1 spool", False), text)
    sp = spool().active(sc)
    path = spool().path_of(sc, sp)
    W0 = float(sp.wound)
    _phi, a0, _r, _k = S().at(path, np.array([W0]))
    _phi, a1, _r, _k = S().at(path, np.array([W0 - 1.0]))
    pay("Wire", 1.0)
    got, want = value("Level wind"), float(a1[0] - a0[0])
    check("1 m paid out: the level wind moves along the drum with the wrap (about 17 mm)",
          abs(abs(got) - abs(want)) < 1e-4 and 0.012 < abs(got) < 0.022, f"{got * 1000:.2f} mm, {want * 1000:.2f} mm")
    pay("Wire", W0 + 3.0)
    empty = spool().status(sc, spool().active(sc))
    pay("Wire", -(spool().active(sc).capacity - W0) - 2.0)
    full = spool().status(sc, spool().active(sc))
    pay("Wire", 0.0)
    check("3 m more paid out than it held: 'Runs empty' in red; 2 m more hauled in than fits: 'Overfills'; at 0: fine",
          empty[1] == "ERROR" and empty[0].startswith("Runs empty: 3.00 m more")
          and full[1] == "ERROR" and full[0].startswith("Overfills: 2.00 m more")
          and spool().status(sc, spool().active(sc))[1] == "CHECKMARK", f"{empty[0]} | {full[0]}")
    STATE["mark"] = "add"
    sc.fresing.last_message = ""
    sc.fresing.cables_index = [c.name for c in sc.fresing.cables].index("Power cable")
    view(np.array(named("TURNTABLE").matrix_world.translation) + np.array((0.0, 0.0, 0.3)), 3.0)
    redraw()
    wiggle()
    return 1.0


@step
def s_click_add_carousel():
    mark = find_marker()
    check("the Add carousel button is found under the list", mark is not None)
    if mark is not None:
        x, y = button_spot(mark, scale=1.25, where=0.75)
        log("Add carousel click at", x, y)
        click(x, y)
    return 1.5


@step
def s_carousel_hover():
    check("a mouse click on Add carousel waits for a click", mod("blender.hover").active())
    spot = spot_on(named("TURNTABLE"))
    STATE["spot"] = spot
    check("the turntable shows in the view", spot is not None)
    if spot:
        move(*spot)
    return 1.0


@step
def s_carousel_click():
    h = mod("blender.hover").current()
    check("the hover highlight shows the turntable", h is not None and h.part == named("TURNTABLE").name
          and h.text == "Carousel: TURNTABLE", h.text if h is not None else "no highlight")
    STATE["mark"] = ""
    if STATE.get("spot"):
        click(*STATE["spot"])
    return 3.0


def carousel_turns(sc) -> tuple:
    """(the carousel's turn x the radius it pays out from, for 1 m paid out; the turn in degrees)."""
    sp = spool().find(sc, "Carousel")
    path = spool().path_of(sc, sp)
    W0 = float(sp.wound)
    pay("Power cable", 1.0)
    turned = abs(value("Carousel turn"))
    pay("Power cable", 0.0)
    _phi, _a, r, _k = S().at(path, np.array([W0 - 0.5]))
    return turned * float(r[0]), math.degrees(turned)


@step
def s_carousel_added():
    sc = bpy.context.scene
    sp = spool().active(sc)
    check("a click on the turntable: 'Carousel' is in the list, on the power cable, turned by 'Carousel turn', its CAD "
          "coil found", sp is not None and len(sc.fresing.spools) == 2 and sp.name == "Carousel"
          and sp.kind == "CAROUSEL" and sp.cable == "Power cable" and sp.joint == "Carousel turn"
          and sp.coil == named("CABLE COIL") and not sp.problem, said())
    if sp is None or sp.kind != "CAROUSEL":
        return 0.5
    check("read from the coil: turns from r 340 to 840 mm", abs(sp.r_in - 0.34) < 2e-3 and abs(sp.r_out - 0.84) < 2e-3,
          f"{sp.r_in * 1000:.1f} .. {sp.r_out * 1000:.1f} mm")
    arc, deg = carousel_turns(sc)
    check("1 m of cable paid out: the carousel turns about 1 m / r of the turn it comes off", abs(arc - 1.0) < 0.06,
          f"{deg:.2f}°, x r = {arc:.4f} m")
    STATE["car_deg"] = deg
    key("Z", ctrl=True)                                     # undo: Add carousel
    return 2.0


@step
def s_undone():
    sc = bpy.context.scene
    names = [s.name for s in sc.fresing.spools]
    sp = spool().find(sc, "Drum")
    check("Undo: the carousel is gone, the power cable starts as drawn again, 'Carousel turn' follows nothing",
          names == ["Drum"] and paths().find(sc, "Power cable").a_kind != "SPOOL"
          and joints().find(sc, "Carousel turn").couple_table == "", names)
    ok = sp is not None and len(sp.followers) == 1
    if ok:
        pay("Wire", 1.0)
        turned = abs(value("Drum turn"))
        pay("Wire", 0.0)
    check("… the drum is still there with its level wind, and still turns with the wire",
          ok and abs(turned * R_LAYER3 - 1.0) < 0.01 and drawn_ok(spool().find(sc, "Drum")) == (True, True))
    key("Z", ctrl=True, shift=True)                         # redo
    return 2.0


@step
def s_redone():
    sc = bpy.context.scene
    names = [s.name for s in sc.fresing.spools]
    sp = spool().find(sc, "Carousel")
    check("Redo: the carousel is back, the power cable starts on it, its turn follows by table",
          names == ["Drum", "Carousel"] and paths().find(sc, "Power cable").a_kind == "SPOOL"
          and joints().find(sc, "Carousel turn").couple_table == "spool:Carousel", names)
    if sp is None:
        return 0.5
    check("… the cable on it is drawn, the CAD coil hidden", drawn_ok(sp) == (True, True), drawn_ok(sp))
    arc, deg = carousel_turns(sc)
    check("… and it turns as before", abs(deg - STATE.get("car_deg", -1.0)) < 1e-3, f"{deg:.3f}°")
    sc.fresing.spools_index = 1
    r = op("fresing.spool_follower_add", joint="Arm slew") if can("fresing.spool_follower_add") else None
    sp = spool().find(sc, "Carousel")
    check("'Arm slew' follows the layer: an arm over the coil", r == {"FINISHED"} and len(sp.followers) == 1
          and sp.followers[0].mode == "ARM" and joints().find(sc, "Arm slew").couple_table == "spool:Carousel", said())
    off0 = guide_off(spool().find(sc, "Carousel"))
    arm0 = math.degrees(value("Arm slew"))
    pay("Power cable", 3.0)
    arm = math.degrees(value("Arm slew"))
    off = guide_off(spool().find(sc, "Carousel"))
    pay("Power cable", 0.0)
    check("3 m paid out: the arm swings, its guide stays over the turn being paid out", abs(arm - arm0) > 0.2
          and off < 2 * MM and off0 < 2 * MM, f"arm {arm0:.3f}° -> {arm:.2f}°, guide {off0 * 1000:.2f} / "
          f"{off * 1000:.2f} mm off the turn")
    STATE["arm0"] = arm0
    STATE["car_deg"] = carousel_turns(sc)[1]                 # (with the arm swinging the turn is a little less)
    STATE["mark"] = "top"
    sc.fresing.last_message = ""
    view(np.array(named("TURNTABLE").matrix_world.translation) + np.array((0.0, 0.0, 0.3)), 3.0)
    redraw()
    wiggle()
    return 1.0


@step
def s_click_off():
    mark = find_marker()
    row = find_chosen_row(mark) if mark is not None else None
    check("the chosen row (Carousel) is found in the list", row is not None, f"{row}")
    if row is not None:
        middle, height, left = row
        x, y = mark["x0"] + left + 12, mark["y_top"] - middle
        STATE["tick"] = (x, y)
        log("tick box click at", x, y, "row", row)
        click(x, y)
    return 1.5


@step
def s_off():
    sc = bpy.context.scene
    sp = spool().find(sc, "Carousel")
    coil = named("CABLE COIL")
    text, icon = spool().status(sc, sp)
    check("a click on its tick box switches the carousel off: the CAD coil shows, the cable starts as drawn, the "
          "carousel and the arm follow nothing", not sp.enabled and icon == "HIDE_ON"
          and evaluated_count(coil) == len(coil.data.vertices) and spool()._made(sc, sp, "rope") is None
          and paths().find(sc, "Power cable").a_kind != "SPOOL"
          and joints().find(sc, "Carousel turn").couple_table == ""
          and joints().find(sc, "Arm slew").couple_table == "", text)
    if STATE.get("tick"):
        click(*STATE["tick"])
    return 1.5


@step
def s_on():
    sc = bpy.context.scene
    sp = spool().find(sc, "Carousel")
    check("… and on again: drawn, the cable on it, the carousel and the arm follow", sp.enabled and not sp.problem
          and drawn_ok(sp) == (True, True) and paths().find(sc, "Power cable").a_kind == "SPOOL"
          and joints().find(sc, "Carousel turn").couple_table == "spool:Carousel"
          and joints().find(sc, "Arm slew").couple_table == "spool:Carousel", spool().status(sc, sp)[0])
    arc, deg = carousel_turns(sc)
    check("… and turns as before", abs(deg - STATE.get("car_deg", -1.0)) < 1e-3, f"{deg:.3f}°")
    STATE["mark"] = ""
    sc.fresing.spools_index = 0                              # the drum, for the picture
    view(np.array(named("WINCH DRUM").matrix_world.translation), 1.6)
    redraw()
    wiggle()
    return 1.5


@step
def s_shot():
    sidebar_shot("panel4_spools", 900)
    shot("02_drum")
    sc = bpy.context.scene
    a = sc.fresing.animations.add()                          # the animation of spool.set_up_test_model
    a.name, a.tail, a.fps = "Spooling", 0.0, "25"
    for cname in ("Wire", "Power cable"):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", paths().find(sc, cname).joint, 0.0, 8.0, "LINEAR"
        b.use_from = True
        b.to_dist = 6.0
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    ok = can("fresing.anim_build")
    r = op("fresing.anim_build") if ok else None
    check("Build animation: built, no spool warns", r == {"FINISHED"} and sc.fresing.anim_baked == "Spooling"
          and all(not s.problem for s in sc.fresing.spools), said())
    wiggle()
    return 1.5


def places() -> dict:
    sc = bpy.context.scene
    return {"drum": value("Drum turn"), "wind": value("Level wind"), "car": value("Carousel turn"),
            "arm": value("Arm slew"), "pay": spool().payout(sc, spool().find(sc, "Drum")),
            "pay2": spool().payout(sc, spool().find(sc, "Carousel"))}


@step
def s_frames():
    sc = bpy.context.scene
    sc.frame_set(END_FRAME)
    update()
    got = places()
    log("end frame", {k: round(v, 5) for k, v in got.items()})
    check("at the last frame 6 m of wire and 6 m of cable have run, the drum, the carousel, the level wind and the "
          "arm have moved", abs(got["pay"] - 6.0) < 1e-3 and abs(got["pay2"] - 6.0) < 1e-3
          and abs(got["drum"]) > 20.0 and abs(got["car"]) > 5.0 and abs(got["wind"]) > 0.05 and abs(got["arm"]) > 1e-3,
          f"drum {math.degrees(got['drum']):.0f}°, carousel {math.degrees(got['car']):.0f}°, "
          f"level wind {got['wind'] * 1000:.0f} mm, arm {math.degrees(got['arm']):.2f}°")
    g1, g2 = rope_gap(spool().find(sc, "Drum"), "Wire"), rope_gap(spool().find(sc, "Carousel"), "Power cable")
    check("… both free cables start where the cable drawn on the spool ends", g1 < 0.011 and g2 < 0.021,
          f"{g1 * 1000:.2f} mm, {g2 * 1000:.2f} mm")
    STATE["end"] = got
    shot("03_end_frame")
    path = os.path.join(OUT, "spool_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    names = [s.name for s in sc.fresing.spools]
    d, c = spool().find(sc, "Drum"), spool().find(sc, "Carousel")
    ok = names == ["Drum", "Carousel"] and d is not None and c is not None
    check("saved and opened again: both spools are in the list with their followers and tables", ok
          and [f.joint for f in d.followers] == ["Level wind"] and [f.joint for f in c.followers] == ["Arm slew"]
          and all(joints().find(sc, n).couple_table == t for n, t in (
              ("Drum turn", "spool:Drum"), ("Level wind", "spool:Drum"), ("Carousel turn", "spool:Carousel"),
              ("Arm slew", "spool:Carousel"))), names)
    if not ok:
        return 0.5
    check("… the cable on both is drawn, the CAD wire and coil hidden", drawn_ok(d) == (True, True)
          and drawn_ok(c) == (True, True), f"{drawn_ok(d)} {drawn_ok(c)}")
    update()
    got, want = places(), STATE.get("end", {})
    worst = max((abs(got[k] - want[k]) for k in want), default=9.9)
    check("… at the last frame everything is where it was", sc.frame_current == END_FRAME and worst < 1e-5,
          f"frame {sc.frame_current}, worst {worst:.2e}")
    sc.frame_set(1)
    update()
    first = places()
    first["arm"] -= math.radians(STATE.get("arm0", 0.0))
    check("… and at frame 1 back at the start", max(abs(v) for v in first.values()) < 1e-5,
          {k: round(v, 6) for k, v in first.items()})
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
