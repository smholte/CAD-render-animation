"""Task 0305: the three animations of the study, done the way a new user does them, in the real app.

    BLENDER_USER_RESOURCES=~/fr_user xvfb-run -a -s "-screen 0 1600x2700x24" blender -p 0 0 1600 2700 \
        --app-template fresing_render --enable-event-simulate --python tasks/0305_proto/walk.py

Env: WALK=crane|mill|product (one per run), WALK_OUT (folder, default /tmp/walk0305).

Every user action is one ledger row (where, what, kind: click / type / pick / view) and is done the way its button
does it (the operator the button calls, or the property the field sets). Text boxes and dialogs count as one
"type". After the key actions a full-height screenshot of the side panel is taken (heights are read from them
afterwards by heights.py). The result is ledger_<walk>.json: rows, notes (what the user had to know that no panel
says), and what was built (seconds, frames, Build ok).
"""
import json
import math
import os
import subprocess
import time
import traceback

import bpy
from mathutils import Vector

WALK = os.environ.get("WALK", "crane")
OUT = os.environ.get("WALK_OUT", "/tmp/walk0305")
os.makedirs(OUT, exist_ok=True)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "fresing_render", "data")
MODEL = {"crane": "test_crane_a.step", "mill": "test_gantry.step", "product": "test_sequence.step"}[WALK]
LOG = open(os.path.join(OUT, f"walk_{WALK}.log"), "w")
ROWS, NOTES, RESULT = [], [], {}


def log(*a):
    msg = " ".join(str(x) for x in a)
    print("[WALK]", msg, flush=True)
    LOG.write(msg + "\n")
    LOG.flush()


def pkg():
    import addon_utils
    return next(m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render"))


def mod(name):
    import importlib
    return importlib.import_module(pkg() + "." + name)


def win():
    return bpy.context.window_manager.windows[0]


def view3d():
    w = win()
    area = next(a for a in w.screen.areas if a.type == "VIEW_3D")
    return w, area


def override():
    w, area = view3d()
    region = next(r for r in area.regions if r.type == "WINDOW")
    return bpy.context.temp_override(window=w, screen=w.screen, area=area, region=region, scene=w.scene)


def row(where, what, kind="click", n=1):
    """One user action (n of them: a menu = open + pick is 2 clicks)."""
    for _ in range(n):
        ROWS.append({"walk": WALK, "where": where, "what": what, "kind": kind})
    log(f"#{len(ROWS):3d} [{kind}] {where} :: {what}")


def note(text):
    NOTES.append(text)
    log("NOTE", text)


def ob(name):
    return next(o for o in bpy.context.scene.objects if o.get("fr_name") == name)


def select(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def sidebar_shot(name, panels_open):
    """The side panel with only these panels open, full height (heights.py reads where its content ends)."""
    panels = mod("blender.panels")
    # as the user sees it: the section's tab clicked (that section open, the top of the tab above it) and the
    # sub-panels the walk opened
    sec = {"FRESING_PT_animation": "6", "FRESING_PT_poses": "4"}.get(panels_open[0], "6")
    bpy.context.window_manager.fresing_tab = sec
    for n in panels_open:
        panels.open_to(n)
    w, area = view3d()
    sb = next(r for r in area.regions if r.type == "UI")
    settle(w)
    p = os.path.join(OUT, f"sb_{WALK}_{name}.png")
    # the side panel's rectangle in X coordinates (y from the top of the screen)
    H = w.height
    geo = f"{sb.width}x{sb.height}+{sb.x}+{H - (sb.y + sb.height)}"
    subprocess.run(["import", "-window", "root", "-crop", geo, "+repage", p], check=False)
    log("shot", p, geo)
    # the same with only the section itself (no sub-panels, nothing above it): where its last button sits
    panels.show_only(panels_open[:1])
    settle(w)
    p2 = os.path.join(OUT, f"only_{WALK}_{name}.png")
    subprocess.run(["import", "-window", "root", "-crop", geo, "+repage", p2], check=False)
    panels.show_only()
    settle(w)
    return p


def settle(w):
    """Blender slides panels into their new places over a few tenths of a second: draw until they stand still."""
    for _ in range(12):
        for a in w.screen.areas:
            a.tag_redraw()
        bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)
        time.sleep(0.05)


def view_shot(name):
    w, area = view3d()
    bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=2)
    p = os.path.join(OUT, f"view_{WALK}_{name}.png")
    H = w.height
    geo = f"{area.width}x{area.height}+{area.x}+{H - (area.y + area.height)}"
    subprocess.run(["import", "-window", "root", "-crop", geo, "+repage", p], check=False)
    return p


def anim():
    s = bpy.context.scene.fresing
    return s.animations[s.animations_index]


def add_step(kind, menu_label):
    row("6 Animation > Steps", f"+ (Add step) -> {menu_label}", n=2)
    with override():
        res = bpy.ops.fresing.block_add(kind=kind)
    assert res == {"FINISHED"}, res
    a = anim()
    a.blocks_index = len(a.blocks) - 1
    return a.blocks[a.blocks_index]


def build():
    row("left panel", "Build & play")
    t = time.perf_counter()
    with override():
        res = bpy.ops.fresing.anim_build()
    RESULT["build"] = str(res)
    RESULT["build_s"] = round(time.perf_counter() - t, 1)
    a = anim()
    an = mod("blender.animation")
    RESULT["seconds"] = round(an.length_seconds(a), 1)
    RESULT["frames"] = bpy.context.scene.frame_end - bpy.context.scene.frame_start + 1
    log("built", RESULT)


# ---------------------------------------------------------------------------
# the walks
# ---------------------------------------------------------------------------

AN = "FRESING_PT_animation"


def walk_crane():
    """A crane lift with a riding camera: boom up, trolley out, the camera rides on the trolley and looks down."""
    sc = bpy.context.scene
    s = sc.fresing
    joints, lesson = mod("blender.joints"), mod("blender.lesson")
    # what 4 Motion gives (the crane lesson up to its animation: light look, two joints, a camera, a saved scene)
    lesson.run(sc, "crane", until=6)
    log("joints", [j.name for j in s.joints], "shots", [x.name for x in s.shots])
    sidebar_shot("00_empty", [AN])
    row("section tabs", "6 (open 6 Animation)")
    row("6 Animation", "+ (new animation)")
    with override():
        bpy.ops.fresing.anim_add()
    a = anim()
    row("6 Animation", "name the animation", "type")
    a.name = "Lift"
    boom = next(j for j in s.joints if j.kind == "ROTATE")
    trolley = next(j for j in s.joints if j.kind == "SLIDE")
    b = add_step("JOINT", "Move joint")
    if b.joint != boom.name:
        note(f"The first Move joint step came with '{b.joint}' (the joint selected in 4 Motion's list), not the "
             "boom the user wanted: changed by its search list.")
        row("6 Animation > step", "Joint: open the search list, pick the boom", n=2)
        b.joint = boom.name
    row("6 Animation > step", "To (type an angle)", "type")
    b.use_from, b.to_angle = True, math.radians(35)
    sidebar_shot("01_one_step", [AN])
    b = add_step("JOINT", "Move joint")
    if b.joint != trolley.name:
        row("6 Animation > step", "Joint: open the search list, pick the trolley", n=2)
        b.joint = trolley.name
    row("6 Animation > step", "To (type a distance)", "type")
    b.use_from, b.to_dist = True, 1.2
    row("6 Animation > step", "Duration (type 4 s)", "type")
    b.duration = 4.0
    b = add_step("CAMERA", "Camera")
    row("6 Animation > step", "mode Ride")
    b.camera_mode = "RIDE"
    row("3D view", "click the trolley", "view")
    select(ob("TROLLEY.ASM"))
    row("6 Animation > step", "Use selected")
    with override():
        bpy.ops.fresing.block_target()
    note("The Camera step starts when the last step ends (6 s): to ride along the whole lift its Start must be typed "
         "back to 0 – nothing says that steps that should play together need the same Start, except the list's "
         "title 'overlaps play together'.")
    row("6 Animation > step", "Start (type 0)", "type")
    b.start = 0.0
    row("6 Animation > step", "Duration (type 6 s)", "type")
    b.duration = 6.0
    sidebar_shot("02_camera_step", [AN])
    build()
    view_shot("built")
    row("6 Animation > Video", "scroll down to Render animation", "scroll")
    row("6 Animation > Video", "Render animation")
    sidebar_shot("03_three_steps_built", [AN])


def walk_mill():
    """A mill program video: the gantry runs a short program; a camera close by; render."""
    sc = bpy.context.scene
    s = sc.fresing
    joints, gcode, tools = mod("blender.joints"), mod("blender.gcode"), mod("blender.tools")
    checks = mod("pccheck.checks")
    # what 4 Motion > CNC machine gives (set up as the PC check does): X/Y/Z, the tool, the workpiece
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(sc)
    tool = ob("TOOL T1 FLAT D6")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, ob("STOCK 300x200x30"))
    path = os.path.join(OUT, "program.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(checks.GCODE_TEST)
    sidebar_shot("00_empty", [AN])
    row("section tabs", "6 (open 6 Animation)")
    row("6 Animation", "+ (new animation)")
    with override():
        bpy.ops.fresing.anim_add()
    b = add_step("GCODE", "Run G-code program")
    row("6 Animation > step", "Program file: folder button, pick the file, Accept", "pick", n=3)
    b.gcode_file = path
    sidebar_shot("01_gcode_step", [AN])
    row("6 Animation > step", "Tools from the program")
    gcode.tools_from_program(sc, b)
    row("4 Motion > CNC machine > Tool changes", "T1 row: Use selected part (the tool in the spindle)", n=2)
    tools.use_part(sc, tools.row_of(sc, 1), tool)
    note("Tools from the program sits in the step, but saying which part is T1 is in 4 Motion > CNC machine: the user "
         "leaves 6 Animation for it (open section 4, its fold, then come back).")
    row("section tabs", "4 then 6 again (to and back)", n=2)
    log("gcode step", b.duration, "s")
    b = add_step("CAMERA", "Camera")
    row("6 Animation > step", "mode Aim (keep the tool in the middle)")
    b.camera_mode = "AIM"
    row("3D view", "click the tool", "view")
    select(tool)
    row("6 Animation > step", "Keep in the middle: Use selected")
    with override():
        bpy.ops.fresing.aim_target()
    row("6 Animation > step", "Start (type 0)", "type")
    b.start = 0.0
    row("6 Animation > step", "Duration (type the program's length)", "type")
    b.duration = max(1.0, anim().blocks[0].duration)
    note("To follow the tool for the whole program the user must read the G-code step's length off its row and type "
         "it into the camera step: there is no 'as long as the step above' or 'for the whole animation'.")
    sidebar_shot("02_camera_step", [AN])
    build()
    view_shot("built")
    row("6 Animation > Video", "scroll down to Render animation", "scroll")
    row("6 Animation > Video", "Render animation")
    sidebar_shot("03_built", [AN])


def walk_product():
    """A 20 s product animation with an exploded view: turn around the unit, it comes apart, holds, goes back."""
    sc = bpy.context.scene
    s = sc.fresing
    states, sequence = mod("blender.states"), mod("blender.sequence")
    unit = ob("SPINDLE.UNIT")
    # --- path A: the one-click product video
    sidebar_shot("00_empty", [AN])
    row("section tabs", "6 (open 6 Animation)")
    row("6 Animation > Make a product video", "open the fold to see the length", "click")
    note("The product video's shortest length is 'About 30 s': a 20 s video cannot be asked for; the steps "
         "it makes have to be shortened by hand afterwards.")
    t = time.perf_counter()
    row("6 Animation", "Make a product video")
    info = mod("blender.product_video").make(sc)
    a = info["animation"] if isinstance(info, dict) and "animation" in info else anim()
    RESULT["product_video_make_s"] = round(time.perf_counter() - t, 1)
    RESULT["product_video_seconds"] = round(mod("blender.animation").length_seconds(a), 1)
    RESULT["product_video_steps"] = [(x.kind, round(x.start, 1), round(x.duration, 1)) for x in a.blocks]
    log("product video", RESULT)
    sidebar_shot("01_product_video", [AN])
    # --- path B: by hand, an exploded view saved as a pose, then steps
    row("section tabs", "4 (open 4 Motion)")
    row("4 Motion", "open the fold Poses & exploded views")
    row("3D view", "click the spindle unit (whole subassembly picked)", "view")
    select(unit)
    sidebar_shot("02_poses_panel", ["FRESING_PT_poses"])
    row("4 Motion > Poses & exploded views", "Distance (drag or type)", "type")
    s.explode_factor = 0.8
    row("4 Motion > Poses & exploded views", "Explode")
    with override():
        n = bpy.ops.fresing.explode()
    log("explode", n)
    view_shot("exploded")
    note("Explode moves the pieces at once and cannot be tried again with another distance: a second Explode moves "
         "them further from where they now are (it explodes the exploded state). The user must press Everything back "
         "to CAD position (in 4 Motion's main panel, above) first – a different fold.")
    row("4 Motion > Poses & exploded views", "+ (save pose) and name it", "type", n=2)
    states.save_pose(sc, "Exploded")
    row("4 Motion", "Everything back to CAD position (scroll up to the main panel)", "click", n=2)
    states.reset_pose(sc)
    row("section tabs", "6 (open 6 Animation)")
    row("6 Animation", "+ (new animation)")
    with override():
        bpy.ops.fresing.anim_add()
    b = add_step("CAMERA", "Camera")
    row("6 Animation > step", "mode Orbit")
    b.camera_mode = "ORBIT"
    row("6 Animation > step", "Turn (type 360)", "type")
    b.orbit_angle = math.radians(360)
    row("6 Animation > step", "Duration (type 20)", "type")
    b.duration = 20.0
    b = add_step("POSE", "Go to pose")
    row("6 Animation > step", "Pose: open the search list, pick Exploded", n=2)
    b.pose = "Exploded"
    row("6 Animation > step", "Start (type 4)", "type")
    b.start, b.duration = 4.0, 3.0
    b = add_step("CAD", "Back to CAD")
    row("6 Animation > step", "Start (type 12)", "type")
    b.start, b.duration = 12.0, 3.0
    note("To hold the exploded view the user works out the gap between the two steps' times by hand (pose ends 7 s, "
         "back starts 12 s); nothing shows the steps on a time line, so the 'hold' is invisible.")
    note("Go to pose moves every piece at once along a straight line; for one-after-another the user needs the other "
         "step kind (Assembly sequence), which has its own exploded places (not the pose) – two ways to explode with "
         "different settings, nothing links them.")
    sidebar_shot("03_by_hand", [AN])
    build()
    RESULT["by_hand"] = dict(RESULT)
    view_shot("built")
    # --- path C: Assembly sequence (one after another), take apart + put together
    row("6 Animation", "+ (new animation)")
    with override():
        bpy.ops.fresing.anim_add()
    b = add_step("CAMERA", "Camera")
    row("6 Animation > step", "mode Orbit, Turn 360, Duration 20", "type", n=3)
    b.camera_mode, b.orbit_angle, b.duration = "ORBIT", math.radians(360), 20.0
    b = add_step("SEQUENCE", "Assembly sequence")
    select(unit)
    row("3D view", "click the spindle unit", "view")
    row("6 Animation > step", "Use selected")
    with override():
        bpy.ops.fresing.block_target()
    row("6 Animation > step", "Start (type 3)", "type")
    b.start = 3.0
    sequence.count(sc, b)
    apart_end = b.start + b.duration
    log("apart", b.seq_count, "parts", b.duration, "s")
    b2 = add_step("SEQUENCE", "Assembly sequence")
    row("6 Animation > step", "Put together")
    b2.seq_mode = "TOGETHER"
    row("3D view + step", "click the unit again, Use selected", n=2)
    with override():
        bpy.ops.fresing.block_target()
    row("6 Animation > step", "Start (type the end of take-apart + hold)", "type")
    b2.start = round(apart_end + 3.0, 1)
    sequence.count(sc, b2)
    note("Put together has to be told the same subassembly again (Use selected), and its own Direction / Order: "
         "nothing copies them from the Take apart step. A 'Take apart, hold, put back' preset would be 1 step.")
    sidebar_shot("04_sequence", [AN])
    build()
    view_shot("seq_built")


def main():
    try:
        w = win()
        w.event_simulate(type="ESC", value="PRESS", x=700, y=1300)
        w.event_simulate(type="ESC", value="RELEASE", x=700, y=1300)
        bpy.context.preferences.system.use_region_overlap = False
        mod("blender.workspaces").use_all(bpy.context.scene)
        bpy.app.timers.register(start_import, first_interval=1.0)
    except Exception:
        log(traceback.format_exc())
        finish()


def start_import():
    """A step of its own: an Esc sent in the same step reaches the import's modal handler and cancels it."""
    try:
        row("1 Import", "Import STEP…, pick the file, Import", "pick", n=3)
        with override():
            res = bpy.ops.fresing.import_step(filepath=os.path.join(DATA, MODEL), quality="draft")
        log("import", res)
        bpy.app.timers.register(wait_import, first_interval=1.0)
    except Exception:
        log(traceback.format_exc())
        finish()


_W = {"n": 0}


def wait_import():
    if bpy.context.scene.fresing.model_count == 0:
        _W["n"] += 1
        if _W["n"] % 10 == 1:
            log("waiting:", bpy.context.scene.fresing.last_message)
        if _W["n"] > 600:
            RESULT["error"] = "import never finished"
            finish()
            return None
        return 0.5
    try:
        {"crane": walk_crane, "mill": walk_mill, "product": walk_product}[WALK]()
    except Exception:
        log(traceback.format_exc())
        RESULT["error"] = traceback.format_exc().splitlines()[-1]
    finish()
    return None


def finish():
    with open(os.path.join(OUT, f"ledger_{WALK}.json"), "w") as fh:
        json.dump({"walk": WALK, "rows": ROWS, "notes": NOTES, "result": RESULT,
                   "clicks": sum(1 for r in ROWS if r["kind"] in ("click", "view", "pick")),
                   "typed": sum(1 for r in ROWS if r["kind"] == "type")}, fh, indent=1, default=str)
    log("done", len(ROWS), "actions")
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(main, first_interval=2.0)
