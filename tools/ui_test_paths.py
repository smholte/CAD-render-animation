"""Real-app test, cables and paths (task 0078): the wire-rope model – a click on the rope in the 3D view, a real
mouse click on the Add cable button, a click on a row of "What it touches"; a contact removed and added back with
the click picker (Esc cancels it once, the hover highlight shows the sheave, then a click in the view); Flip side,
undo and redo (the cable is still drawn on its path after each); then a new project with the luff joint and the
animation of ``paths.set_up_test_model``: Build animation, the rope follows the luffing frame and the sheaves
turn, save and open again, Remove.

Where a button is on the screen is not known to a script. The test draws a magenta strip right above the Add cable
button (only while it looks for it) and finds that strip in a screenshot; the chosen row of a list is found by
its highlight colour. Everything else is pressed the way the other real-app tests press buttons (the operator
run like a button, with an undo step) after checking that the button is not grey.

Install the extension and the app template first (see ui_test_app.py), then run:
    xvfb-run -a -s "-screen 0 1800x2600x24" blender --app-template fresing_render --enable-event-simulate \\
        --python tools/ui_test_paths.py
Screenshots and ui_test_paths.log go to $UITEST_OUT (default ~/fresing_ui_test_paths).
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

OUT = os.environ.get("UITEST_OUT", os.path.join(os.path.expanduser("~"), "fresing_ui_test_paths"))
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "data")
MODEL = os.path.join(DATA, "test_paths_a.step")
os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, "ui_test_paths.log"), "w")
RESULTS = []
STATE = {"mark": False}
MM = 0.001
ORDER = ["WINCH DRUM", "SHEAVE 1", "SHEAVE 2", "V ROLLER", "V ROLLER", "CHUTE"]
LUFF_FRAME = 76                                 # 3.0 s at 25 fps: the A-frame is at +12 degrees
END_FRAME = 151                                 # 6.0 s: one metre of rope has run


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
    """The magenta strip above the Add cable button: {top, bottom, left, right} in side-panel pixels (from its top
    left corner) with the pixels themselves, or None."""
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
    wide[:mark["bottom"] + 30] = False                    # (the Add cable button itself is right under the marker)
    rows = np.flatnonzero(wide)
    if not len(rows):
        return None
    last = rows[0]
    while last + 1 < len(wide) and wide[last + 1]:
        last += 1
    cols = np.flatnonzero(close[rows[0]:last + 1].any(axis=0))
    return (int(rows[0]) + int(last)) // 2, int(last) - int(rows[0]) + 1, int(cols[0])


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


def wiggle():
    win, area, region, _sb = ui()
    win.event_simulate(type="MOUSEMOVE", value="NOTHING", x=region.x + 300 + int(time.time()) % 7, y=region.y + 300)


def redraw():
    for a in bpy.context.window_manager.windows[0].screen.areas:
        a.tag_redraw()


def named(name, k=0):
    found = [o for o in bpy.context.scene.objects if o.get("fr_name") == name]
    return found[k] if len(found) > k else None


def paths():
    return mod("blender.paths")


def joints():
    return mod("blender.joints")


def cable():
    return paths().active(bpy.context.scene)


def contacts():
    it = cable()
    return [c.name for c in it.contacts] if it is not None else []


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
        if facing < 0.6 or (best is not None and facing <= best[0]):
            continue
        # a click takes the nearest part within a few pixels of the mouse: the part must be alone there
        if all(first_hit(sc, dg, region, rv3d, co + Vector(d)) == part
               for d in ((0, 0), (ROUND, 0), (-ROUND, 0), (0, ROUND), (0, -ROUND))):
            best = (facing, int(round(region.x + co.x)), int(round(region.y + co.y)))
    return best[1:] if best else None


ROUND = 7                                       # pixels round the mouse that must show the same part


def first_hit(sc, dg, region, rv3d, co):
    """The part seen at a pixel of the 3D view (None: the background)."""
    along = view3d_utils.region_2d_to_vector_3d(region, rv3d, co).normalized()
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, co) - along * 50.0
    hit, _loc, _n, _i, ob, _m = sc.ray_cast(dg, origin, along)
    return ob.original if hit and ob is not None else None


def to_window(world_pt):
    win, area, region, _sb = ui()
    co = view3d_utils.location_3d_to_region_2d(region, region.data, Vector(world_pt))
    return int(round(region.x + co.x)), int(round(region.y + co.y))


def seen_at(x, y):
    """The part a click at this window pixel would hit."""
    win, area, region, _sb = ui()
    return first_hit(bpy.context.scene, bpy.context.evaluated_depsgraph_get(), region, region.data,
                     Vector((x - region.x, y - region.y)))


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


def open_panel():
    """The panel sits far down the side panel, closed. For the clicks and the pictures: a copy of it, open, right
    under 1 Import (panels are ordered by bl_order, then by when they were registered). And the magenta strip
    above the Add cable button, drawn only while ``STATE["mark"]`` is on."""
    if hasattr(bpy.types, "FRESING_PT_cables_shot"):
        return
    ui_paths = mod("blender.ui_paths")
    base = ui_paths.FRESING_PT_cables
    bpy.utils.register_class(type("FRESING_PT_cables_shot", (base,), {
        "bl_idname": "FRESING_PT_cables_shot", "bl_parent_id": "", "bl_options": set(), "bl_order": 0}))
    if not hasattr(bpy.types.WindowManager, "fr_uitest_mark"):
        bpy.types.WindowManager.fr_uitest_mark = bpy.props.FloatVectorProperty(
            subtype="COLOR", size=3, default=(1.0, 0.0, 1.0), min=0.0, max=1.0)
    real = ui_paths._add_buttons

    def marked(layout, scene, first):
        if STATE["mark"]:
            layout.prop(bpy.context.window_manager, "fr_uitest_mark", text="")
        real(layout, scene, first)

    ui_paths._add_buttons = marked


def drawn(part):
    """The middles of the rings of the cable as it is drawn now (its modifier applied): world points (n, 3)."""
    e = part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    co = np.empty(len(e.data.vertices) * 3, np.float32)
    e.data.vertices.foreach_get("co", co)
    w = np.array(e.matrix_world, dtype=float)
    pts = co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3]
    sides = paths().SIDES
    return pts.reshape(-1, sides, 3).mean(axis=1) if len(pts) and len(pts) % sides == 0 else np.zeros((0, 3))


def shape():
    """The cable's path at the frame shown, as the app keeps it: world points (n, 3)."""
    return np.array(paths().shape_now(bpy.context.scene, cable()), dtype=float)


def to_line(points, line) -> float:
    """The furthest any of the points is from the polyline (metres); 9.9 when there is nothing to compare."""
    if len(points) < 2 or len(line) < 2:
        return 9.9
    a, seg = line[:-1], line[1:] - line[:-1]
    t = np.einsum("pli,li->pl", points[:, None] - a[None], seg) / np.maximum(np.einsum("li,li->l", seg, seg), 1e-30)
    foot = a[None] + np.clip(t, 0.0, 1.0)[..., None] * seg[None]
    return float(np.linalg.norm(points[:, None] - foot, axis=2).min(axis=1).max())


def same(a, b) -> float:
    """The largest difference between two paths (metres); 9.9 when they have another number of points."""
    return float(np.abs(a - b).max()) if a.shape == b.shape and len(a) else 9.9


def on_path() -> float:
    """How far the drawn cable is off the path the app keeps for it (metres)."""
    return to_line(drawn(cable().part), shape())


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
    view((2.0, 0.0, 0.7), 1.6)                              # close on the level run of the rope (24 mm thick)
    open_panel()
    check("the rope model: no cable in the list, the panel is there", len(sc.fresing.cables) == 0
          and mod("blender.ui_paths").FRESING_PT_cables.poll(bpy.context)
          and mod("blender.ui_paths").counts(sc) == ("–", False))
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
        bpy.ops.ed.undo_push(message="Set-up")
    redraw()
    wiggle()
    return 1.5


@step
def s_empty():
    sc = bpy.context.scene
    sidebar_shot("panel4_cables_empty", 1300)
    check("no cable yet: Add cable and Add all are live, the buttons of a cable are grey",
          can("fresing.cable_add") and can("fresing.cable_add_all") and not can("fresing.cable_remove")
          and not can("fresing.cable_read") and not can("fresing.cable_contact_add") and not can("fresing.cable_end")
          and mod("blender.ui_paths").found_count(sc) == 1)
    spot = spot_on(named("WIRE ROPE"))
    check("the rope shows in the view", spot is not None)
    if spot:
        click(*spot)
    return 1.0


@step
def s_selected():
    rope = named("WIRE ROPE")
    with override():
        active, chosen = bpy.context.view_layer.objects.active, list(bpy.context.selected_objects)
    check("a click on the rope in the view selects it", active == rope and rope in chosen,
          f"active {active.name if active else None}, {len(chosen)} selected")
    STATE["mark"] = True                                    # the magenta strip above the Add cable button
    redraw()
    wiggle()
    return 1.0


@step
def s_click_add():
    mark = find_marker()
    check("the Add cable button is found in the side panel", mark is not None)
    if mark is not None:
        unit = max(16, mark["bottom"] - mark["top"] + 1)
        x = mark["x0"] + (mark["left"] + mark["right"]) // 2
        y = mark["y_top"] - (mark["bottom"] + int(0.9 * unit))
        log("Add cable click at", x, y, "marker rows", mark["top"], mark["bottom"])
        click(x, y)                                         # a real click on the button: its invoke, the selection
    return 2.5


@step
def s_added():
    sc = bpy.context.scene
    it = cable()
    P = paths()
    check("a mouse click on Add cable: the rope is in the list, read from its CAD part: 6 contacts",
          it is not None and len(sc.fresing.cables) == 1 and it.part == named("WIRE ROPE") and contacts() == ORDER
          and P.status(sc, it)[1] == "OK", f"{contacts()} | {said()}")
    if it is None:
        return 0.5
    check("the message says what was found", said().startswith("Cable 'WIRE ROPE': 3 sheaves, 2 rollers, 1 chute; "
                                                              "Ø 24 mm, 7.02 m"), said())
    J = joints()
    turning = [c for c in it.contacts if c.kind in ("SHEAVE", "ROLLER")]
    check("named a rope: steel wire rope look; its speed joint is made; the five round parts follow it",
          it.look == "ROPE" and J.find(sc, it.joint) is not None and len(turning) == 5
          and all(J.find(sc, c.joint) is not None and J.find(sc, c.joint).follows == it.joint for c in turning),
          f"look {it.look}, joint {it.joint}")
    off = on_path()
    check("the rope is drawn by the app, on its path", it.part.modifiers.get(P.MOD) is not None and off < 0.1 * MM
          and len(shape()) > 20, f"{off * 1000:.4f} mm off, {len(shape())} points")
    STATE["shape0"] = shape().copy()
    redraw()
    wiggle()
    return 1.0


@step
def s_click_row():
    mark = find_marker()
    row = find_chosen_row(mark) if mark is not None else None
    check("the chosen row of 'What it touches' is found in the side panel", row is not None and cable() is not None
          and cable().contacts_index == 0, f"{row}")
    if row is not None:
        middle, height, left = row
        height = height if 14 <= height <= 34 else 20
        x = mark["x0"] + left + 60
        y = mark["y_top"] - (middle + 2 * height)           # two rows further down: the third contact
        log("row click at", x, y, "row", middle, height, left)
        click(x, y)
    return 1.0


@step
def s_row():
    it = cable()
    check("a mouse click on the third row chooses SHEAVE 2", it is not None and it.contacts_index == 2,
          it.contacts_index if it is not None else "no cable")
    STATE["mark"] = False
    redraw()
    wiggle()
    return 1.0


@step
def s_shot():
    sidebar_shot("panel4_cables", 1500)                     # the open panel, SHEAVE 2 chosen
    cable().mbr = 0.25                                      # sheave 2 bends the rope at 180 mm
    redraw()
    wiggle()
    return 1.0


@step
def s_warning():
    sc = bpy.context.scene
    sidebar_shot("panel4_cables_warning", 1500)
    it = cable()
    P = paths()
    ui_paths = mod("blender.ui_paths")
    check("a bend tighter than the smallest bend warns: in the list, in the header, under the list",
          P.status(sc, it)[1] == "WARN" and "'SHEAVE 2'" in P.status(sc, it)[0]
          and ui_paths.short_status(sc, it) == ("tight bend", True) and ui_paths.counts(sc) == ("1 warning", True),
          P.status(sc, it)[0])
    it.mbr = 0.0
    check("… and is gone with the limit", P.status(sc, it)[1] == "OK" and ui_paths.counts(sc) == ("1 cable", False))
    it.contacts_index = 1                                   # SHEAVE 1: where the rope lies on it, for the click later
    c = it.contacts[1]
    centre = np.array(P.wheels_now(sc, it)[1].centre, dtype=float)
    line = STATE["shape0"]
    arc = line[np.linalg.norm(line - centre, axis=1) < c.radius + 1 * MM]
    middle = arc[len(arc) // 2]
    STATE["hit"] = centre + (middle - centre) * (c.surface / c.radius)       # on the groove's bottom
    out = (middle - centre) / np.linalg.norm(middle - centre)
    joint = c.joint
    r = op("fresing.cable_contact_remove") if can("fresing.cable_contact_remove") else None
    it = cable()
    check("Remove (-): SHEAVE 1 is off the list, its joint is gone, the rope runs straight past it",
          r == {"FINISHED"} and contacts() == ORDER[:1] + ORDER[2:] and joints().find(sc, joint) is None
          and P.status(sc, it)[1] == "OK" and float(np.linalg.norm(shape() - centre, axis=1).min()) > c.radius + 0.1,
          said())
    view(STATE["hit"], 0.7, rotation=Vector(out).to_track_quat("Z", "Y"))    # look straight into the groove
    wiggle()
    return 1.5


@step
def s_pick_start():
    x, y = to_window(STATE["hit"])
    STATE["spot"] = (x, y)
    seen = seen_at(x, y)
    check("the sheave's groove shows in the view", seen == named("SHEAVE 1"), seen.name if seen else "nothing")
    with override():
        r = bpy.ops.fresing.cable_contact_add("INVOKE_DEFAULT")
    check("Add (+) waits for a click, the status bar says what to click", r == {"RUNNING_MODAL"}
          and mod("blender.hover").active(), r)
    return 0.8


@step
def s_pick_esc():
    key("ESC")                                              # (a step of its own: it must reach the picker)
    return 1.0


@step
def s_pick_cancelled():
    check("Esc cancels the picker: nothing is added", not mod("blender.hover").active() and len(contacts()) == 5)
    with override():
        r = bpy.ops.fresing.cable_contact_add("INVOKE_DEFAULT")
    STATE["again"] = r
    return 0.8


@step
def s_pick_hover():
    move(*STATE["spot"])
    return 1.0


@step
def s_pick_click():
    h = mod("blender.hover").current()
    check("Add (+) again: the hover highlight shows the sheave under the mouse",
          STATE.get("again") == {"RUNNING_MODAL"} and h is not None and h.part == named("SHEAVE 1").name
          and not h.refused and h.text == "Cable over SHEAVE 1", h.text if h is not None else "no highlight")
    log("sheave click at", *STATE["spot"])
    click(*STATE["spot"])
    return 2.0


@step
def s_picked():
    sc = bpy.context.scene
    it = cable()
    P = paths()
    off = same(shape(), STATE["shape0"])                    # (its seat is measured again where it was clicked)
    STATE["back"] = shape().copy()
    check("a click on the sheave where the rope lay: it is back in its place, the rope as before",
          contacts() == ORDER and not mod("blender.hover").active() and off < 0.2 * MM
          and said() == "'SHEAVE 1' added as a sheave: number 2 of 6 along 'WIRE ROPE'",
          f"{contacts()} | {off * 1000:.4f} mm | {said()}")
    c = it.contacts[1]
    j = joints().find(sc, c.joint)
    check("… and it turns with the rope again", c.kind == "SHEAVE" and c.user and j is not None
          and j.follows == it.joint, c.joint)
    it.contacts_index = 2
    r = op("fresing.cable_contact_flip") if can("fresing.cable_contact_flip") else None
    it = cable()
    STATE["flipped"] = shape().copy()
    longer = float(np.linalg.norm(np.diff(STATE["flipped"], axis=0), axis=1).sum()
                   - np.linalg.norm(np.diff(STATE["back"], axis=0), axis=1).sum())
    check("Flip side: the rope goes over SHEAVE 2 instead of under it", r == {"FINISHED"} and it.contacts[2].side == 1
          and math.degrees(it.contacts[2].wrap) > 180.0 and longer > 0.2 and P.status(sc, it)[1] == "OK"
          and on_path() < 0.1 * MM, f"{math.degrees(it.contacts[2].wrap):.0f} degrees, {longer * 1000:.0f} mm longer")
    view((1.6, 0.0, 0.9), 4.2)
    wiggle()
    return 1.0


@step
def s_undo():
    shot("01_flipped")
    key("Z", ctrl=True)                                     # undo: Flip side
    return 1.5


@step
def s_undone():
    it = cable()
    ok = it is not None and len(it.contacts) == 6 and it.contacts[2].side == -1
    off, drawn_off = (same(shape(), STATE["back"]), on_path()) if ok else (9.9, 9.9)
    check("Undo: the rope runs under SHEAVE 2 again, and is drawn there", ok and off < 0.01 * MM
          and drawn_off < 0.1 * MM and to_line(drawn(it.part), STATE["back"]) < 0.1 * MM,
          f"path {off * 1000:.4f} mm, drawn {drawn_off * 1000:.4f} mm off")
    key("Z", ctrl=True, shift=True)                         # redo
    return 1.5


@step
def s_redone():
    sc = bpy.context.scene
    it = cable()
    ok = it is not None and len(it.contacts) == 6 and it.contacts[2].side == 1
    off, drawn_off = (same(shape(), STATE["flipped"]), on_path()) if ok else (9.9, 9.9)
    check("Redo: over SHEAVE 2 again, and drawn there", ok and off < 0.01 * MM and drawn_off < 0.1 * MM
          and to_line(drawn(it.part), STATE["flipped"]) < 0.1 * MM,
          f"path {off * 1000:.4f} mm, drawn {drawn_off * 1000:.4f} mm off")
    if ok:
        it.contacts_index = 2
        r = op("fresing.cable_contact_flip") if can("fresing.cable_contact_flip") else None
        check("Flip side once more: under it, as before", r == {"FINISHED"}
              and same(shape(), STATE["back"]) < 0.01 * MM and paths().status(sc, cable())[1] == "OK")
    with override():
        bpy.ops.wm.read_homefile(app_template="fresing_render")          # a new project: the luffing frame
    return 2.0


@step
def s_import_again():
    STATE["mark"] = False
    with override():
        res = bpy.ops.fresing.import_step(filepath=MODEL, quality="normal")
    log("import", res, said())
    return 1.0


@step
def s_wait_again():
    sc = bpy.context.scene
    if sc.fresing.model_count == 0:
        return "wait"
    view((2.0, 0.0, 0.7), 1.6)                              # close on the level run of the rope again
    with override():
        for o in bpy.context.selected_objects:
            o.select_set(False)
        bpy.context.view_layer.objects.active = None
    wiggle()
    return 1.5


@step
def s_add_picker():
    with override():
        r = bpy.ops.fresing.cable_add("INVOKE_DEFAULT")     # nothing selected: the button asks for a click
    spot = spot_on(named("WIRE ROPE"))
    STATE["spot"] = spot
    check("Add cable with nothing selected waits for a click on the cable", r == {"RUNNING_MODAL"}
          and mod("blender.hover").active() and spot is not None and len(bpy.context.scene.fresing.cables) == 0, r)
    if spot:
        move(*spot)
    return 1.0


@step
def s_add_click():
    h = mod("blender.hover").current()
    check("the hover highlight shows the rope under the mouse", h is not None and h.part == named("WIRE ROPE").name
          and h.text == "Cable: WIRE ROPE" and not h.refused, h.text if h is not None else "no highlight")
    if STATE.get("spot"):
        click(*STATE["spot"])
    return 2.5


@step
def s_add_picked():
    sc = bpy.context.scene
    P = paths()
    check("a click on the rope adds it: 6 contacts", cable() is not None and contacts() == ORDER
          and cable().part == named("WIRE ROPE") and not mod("blender.hover").active(), f"{contacts()} | {said()}")
    while len(sc.fresing.cables):                           # the set-up below makes its own cable
        P.remove(sc, 0)
    view((1.6, 0.0, 0.9), 4.2)
    made = P.set_up_test_model(sc)                          # the joint "Luff", the cable, the animation
    it = cable()
    check("the luffing frame: the joint Luff, the cable 'Wire rope' and its animation are made",
          made["joints"][0] == "Luff" and made["contacts"] == ORDER and it is not None and it.moving
          and not sc.fresing.anim_baked, f"{made['joints']}, moving {it.moving if it else None}")
    ok = can("fresing.anim_build")
    r = op("fresing.anim_build") if ok else None            # the Build animation button of 6 Animation
    check("Build animation: built, without a warning for the cable", r == {"FINISHED"}
          and sc.fresing.anim_baked == made["animation"] and cable().problem == ""
          and P.status(sc, cable())[0].endswith("a shape per frame"), f"{said()} | {P.status(sc, cable())[0]}")
    wiggle()
    return 1.5


@step
def s_frames():
    sc = bpy.context.scene
    P, J = paths(), joints()
    it = cable()
    got = {}
    for frame in (1, LUFF_FRAME, END_FRAME):
        sc.frame_set(frame)
        bpy.context.view_layer.update()
        got[frame] = (shape().copy(), on_path(), math.degrees(J.get_value(J.find(sc, "Luff"))),
                      J.get_value(J.find(sc, it.joint)))
    log("frames", {f: (round(g[1] * 1000, 4), round(g[2], 3), round(g[3], 4)) for f, g in got.items()})
    check("frame 1, 76 and 151: the A-frame luffs to 12 degrees and back, one metre of rope runs",
          abs(got[1][2]) < 1e-3 and abs(got[LUFF_FRAME][2] - 12.0) < 0.01 and abs(got[END_FRAME][2]) < 0.01
          and abs(got[1][3]) < 1e-6 and abs(got[LUFF_FRAME][3] - 0.5) < 1e-3 and abs(got[END_FRAME][3] - 1.0) < 1e-3,
          f"luff {got[LUFF_FRAME][2]:.3f}, rope {got[END_FRAME][3]:.4f} m")
    moved = float(np.linalg.norm(got[LUFF_FRAME][0] - got[1][0], axis=1).max()) \
        if got[LUFF_FRAME][0].shape == got[1][0].shape else 0.0
    check("the drawn rope differs between the luffed frame and the first, and is back at the end",
          moved > 0.1 and same(got[END_FRAME][0], got[1][0]) < 0.05 * MM, f"moved {moved * 1000:.0f} mm")
    check("at every one of them the rope is drawn on its path", max(g[1] for g in got.values()) < 0.1 * MM,
          f"{max(g[1] for g in got.values()) * 1000:.4f} mm")
    turned = []
    for c in it.contacts:                                   # at frame 151: degrees per mm x 1,000 mm
        if c.joint:
            turned.append(abs(math.degrees(J.get_value(J.find(sc, c.joint))) - c.ratio * 1000.0))
    check("the drum, the two sheaves and the two rollers have turned as far as one metre of rope turns them",
          len(turned) == 5 and max(turned) < 0.05 and abs(it.contacts[1].ratio * 1000.0) > 200.0,
          f"worst {max(turned) if turned else -1:.4f} degrees off, sheave 1 {it.contacts[1].ratio * 1000.0:.1f} "
          "degrees")
    sc.frame_set(LUFF_FRAME)
    bpy.context.view_layer.update()
    STATE["shape1"], STATE["luffed"] = got[1][0], got[LUFF_FRAME][0]
    shot("02_luffed")
    path = os.path.join(OUT, "paths_project.blend")
    with override():
        bpy.ops.wm.save_as_mainfile(filepath=path)
    with override():
        bpy.ops.wm.open_mainfile(filepath=path)
    return 2.0


@step
def s_reopened():
    sc = bpy.context.scene
    it = cable()
    ok = it is not None and contacts() == ORDER and sc.frame_current == LUFF_FRAME
    check("saved and opened again: the cable is in the list, at the luffed frame the same shape, drawn on it",
          ok and same(shape(), STATE["luffed"]) < 0.01 * MM and on_path() < 0.1 * MM
          and paths().status(sc, it)[1] == "OK", f"frame {sc.frame_current}")
    if ok:
        sc.frame_set(1)
        bpy.context.view_layer.update()
        check("… and at frame 1 the first shape", same(shape(), STATE["shape1"]) < 0.01 * MM and on_path() < 0.1 * MM)
    wiggle()
    return 1.0


@step
def s_remove():
    sc = bpy.context.scene
    rope = named("WIRE ROPE")
    r = op("fresing.cable_remove") if can("fresing.cable_remove") else None
    bpy.context.view_layer.update()
    e = rope.evaluated_get(bpy.context.evaluated_depsgraph_get())
    check("Remove: the list is empty, the rope shows its CAD shape again, only the joint Luff is left",
          r == {"FINISHED"} and len(sc.fresing.cables) == 0 and rope.modifiers.get(paths().MOD) is None
          and len(e.data.vertices) == len(rope.data.vertices) and [j.name for j in sc.fresing.joints] == ["Luff"],
          f"{said()} | joints {[j.name for j in sc.fresing.joints]}")
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
