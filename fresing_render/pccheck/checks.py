"""The lines of the PC check: one function per main function of the app, run on the test models in
``data/`` (generic models made by tools/make_test_*.py, never the owner's files).

Every line is a function ``fn(ctx)`` registered with ``@line(...)``. It returns a short note (or
None), raises an exception when the function does not work (reported as FAILED with the reason) and
``Skipped`` when it does not apply here (for example no graphics card). ``ctx`` (runner.Context) holds
the helpers: ``ctx.fresh(model)`` for a new project with a test model, ``ctx.metric()`` for numbers
compared with the last runs, ``ctx.picture()`` for a rendered picture, ``ctx.need_gpu()``.

A task that adds something the owner can see adds its line here, with ``since`` = the version it comes
in (CLAUDE.md section 6). Lines run in the order they are listed.
"""

from __future__ import annotations

import math
import os
import time

from .core import Cancelled, Line, Skipped

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
MACHINE = os.path.join(DATA, "test_machine.step")
MATERIALS = os.path.join(DATA, "test_materials.step")
CRANE_A = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
FACES = os.path.join(DATA, "test_faces_a.step")
MILL = os.path.join(DATA, "test_mill.step")
TOOLPATH = os.path.join(DATA, "test_toolpath.step")
DECALS = os.path.join(DATA, "test_decals_a.step")
LUFFER = os.path.join(DATA, "test_cylinder_a.step")
LINKAGES = os.path.join(DATA, "test_linkage_a.step")
GANTRY = os.path.join(DATA, "test_gantry.step")
ATC = os.path.join(DATA, "test_atc.step")
FOUR_AXIS = os.path.join(DATA, "test_4axis.step")
FIVE_AXIS = os.path.join(DATA, "test_5axis.step")
WAYCOVER = os.path.join(DATA, "test_waycover_b.step")
WAYCOVER_OWNER = os.path.join(DATA, "test_waycover_a.step")
WAYCOVER_TWO = os.path.join(DATA, "test_waycover_c.step")
CLASH = os.path.join(DATA, "test_clash.step")

LINES: list[Line] = []
Q, F, OWN, H = "quick", "full", "own", "heavy"


def line(id: str, title: str, since: str, modes=(F,), requires=(), what: str = "", expected: int = 0,
         shows: str = "", not_shown: str = ""):
    def deco(fn):
        LINES.append(Line(id, title, since, tuple(modes), fn, tuple(requires), what, expected, shows, not_shown))
        return fn
    return deco


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ob(scene, name, n=0):
    from ..blender import build
    hits = sorted((o for o in scene.objects if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
    if len(hits) <= n:
        raise RuntimeError(f"the test model has no part '{name}'")
    return hits[n]


def _update():
    import bpy
    bpy.context.view_layer.update()


def _check(cond: bool, message: str) -> None:
    if not cond:
        raise RuntimeError(message)


def _boom_joint(scene):
    """The crane's boom turns about its pin (picked like a click on the pin's round face)."""
    from mathutils import Vector

    from ..blender import joints
    pin = _ob(scene, "BOOM.PIN")
    origin, direction, _desc = joints.axis_from_hit(pin, 0, Vector((0.1, 0.3, 0.42)), Vector((0, 0, 1)))
    return joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], origin, direction, ref=pin, name="Boom")


def _tip(scene):
    from mathutils import Vector
    return _ob(scene, "BOOM").matrix_world @ Vector((1.5, 0, 0))


def _wait_queue(scene, minutes: float):
    from ..blender import queue
    from . import runner
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < minutes * 60:
        if runner.cancel_requested():
            queue.kill(scene)
            raise Cancelled("cancelled")
        time.sleep(0.5)
    if queue.is_running(scene):
        queue.kill(scene)
        raise RuntimeError(f"the queue did not finish within {minutes:.0f} minutes")
    queue.sync(scene)


def _queue_job(ctx, scene, kind, minutes=10.0, **kw):
    """Add one job, start the background queue, wait; returns the finished job."""
    import bpy

    from ..blender import queue
    s = scene.fresing
    for i in reversed(range(len(s.queue))):
        s.queue.remove(i)
    queue.add_job(scene, kind, **kw)
    time.sleep(1.05)            # a queue started in the same second as the last one would reuse its folder
    qdir = queue.start(bpy.context)
    _wait_queue(scene, minutes)
    job = s.queue[-1]
    if job.status != "DONE":
        raise RuntimeError(f"{job.status}: {job.message} | {queue.log_tail(qdir, 8)}")
    return job


def _small_output(s, w=320, h=180):
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = w, h


def _short_animation(scene, name, joint, angle_deg=30.0, seconds=0.4, quality="draft"):
    s = scene.fresing
    a = s.animations.add()
    a.name, a.tail, a.quality = name, 0.0, quality
    a.out_resolution, a.out_format = "preview", "square"
    b = a.blocks.add()
    b.kind, b.joint, b.duration, b.use_from, b.to_angle = "JOINT", joint, seconds, False, math.radians(angle_deg)
    return a


# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------

@line("app.start", "App starts, test models present", "0.1.0", (Q, F),
      what="The extension is on in this Blender and the test models are inside it")
def app_start(ctx):
    import bpy
    _check(hasattr(bpy.types.Scene, "fresing"), "the Fresing Render settings are missing: run Install.bat again")
    _check(hasattr(bpy.ops.fresing, "import_step"), "the import button is missing: run Install.bat again")
    missing = [os.path.basename(p) for p in (MACHINE, MATERIALS, CRANE_A, CRANE_B, FACES, MILL, DECALS)
               if not os.path.isfile(p)]
    _check(not missing, f"test models missing: {', '.join(missing)}")
    return f"Blender {bpy.app.version_string}"


@line("gpu.device", "Graphics card found", "0.1.0", (Q, F), what="Cycles finds the graphics card (OptiX/CUDA)")
def gpu_device(ctx):
    ctx.need_gpu()
    return ctx.gpu


# ---------------------------------------------------------------------------
# import and sorting
# ---------------------------------------------------------------------------

@line("import.crane", "Import + sorting: test crane", "0.1.0", (Q, F),
      what="STEP file read on all cores, parts built and sorted into groups")
def import_crane(ctx):
    from ..blender import build
    t0 = time.time()
    scene = ctx.fresh(CRANE_A, quality="normal", read_again=True)
    ctx.metric("import", time.time() - t0, "s")
    parts = list(build.iter_parts(scene))
    _check(len(parts) >= 10, f"only {len(parts)} parts imported")
    groups = scene.fresing.groups
    _check(len(groups) >= 3, f"only {len(groups)} groups made")
    ctx.metric("parts", len(parts), "")
    return f"{len(parts)} parts in {len(groups)} groups"


@line("import.machine", "Import + sorting: fasteners and colours", "0.1.0",
      what="Bolts by their DIN/ISO names, colours from CAD, the part-type library")
def import_machine(ctx):
    from ..blender import build
    scene = ctx.fresh(MACHINE)
    parts = list(build.iter_parts(scene))
    _check(len(parts) == 11, f"expected 11 parts, got {len(parts)}")
    groups = {g.name: g for g in scene.fresing.groups}
    _check(groups.get("Fasteners galvanized") and groups["Fasteners galvanized"].count == 4,
           "the 4 galvanized bolts are not sorted together")
    _check(groups.get("Fasteners black") and groups["Fasteners black"].count == 4,
           "the 4 black bolts are not sorted together")
    _check(_ob(scene, "SIGNAL.LAMP")[build.PROP_GROUP] == "Signal towers & lamps",
           "the part-type library did not recognise the signal lamp")
    return f"{len(parts)} parts, {len(groups)} groups"


@line("import.materials", "CAD material names", "0.2.8", what="Material and appearance names read from STEP")
def import_materials(ctx):
    from ..blender import build
    scene = ctx.fresh(MATERIALS)
    names = {o[build.PROP_NAME]: o for o in build.iter_parts(scene)}
    _check("PLATE" in names and "SEAL RING" in names, "the test parts are missing")
    groups = {o[build.PROP_GROUP] for o in names.values()}
    _check(len(groups) >= 2, "all parts ended up in one group: the CAD material names were not used")
    return f"{len(names)} parts, {len(groups)} groups"


@line("faces.painted", "Painted faces", "0.2.9",
      what="Faces painted in CAD come in painted; a face painted by hand keeps its look")
def faces_painted(ctx):
    import bpy

    from ..blender import faces, logic, ops_panels
    scene = ctx.fresh(FACES)
    housing = _ob(scene, "HOUSING")
    sets = faces.get_sets(housing.data)
    _check(len(sets) == 2, f"the housing should have 2 painted faces from CAD, has {len(sets)}")
    s = scene.fresing
    cover = _ob(scene, "COVER")
    logic.ensure_group(s, "PC check red")
    s.face_group = "PC check red"
    bpy.context.view_layer.objects.active = cover
    ops_panels.paint_click(bpy.context, cover, 5)
    _check(faces.groups_on(cover) == ["PC check red"], "painting a face by hand did not work")
    _check(len(cover.material_slots) == 2, "the painted face got no material of its own")
    return "2 CAD faces, 1 by hand"


@line("decals.add", "Decals: text and stickers on the model", "0.2.21",
      what="A warning sticker and a text on a flat face, a sticker round a barrel; rendered small")
def decals_add(ctx):
    import bpy

    from ..blender import decals
    scene = ctx.fresh(DECALS)
    panel, barrel = _ob(scene, "PANEL"), _ob(scene, "BARREL")
    warn = decals.add(panel, 5, (0.31, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="WARN_GENERAL")
    text = decals.add(panel, 5, (0.12, 0.15, 0.01), (0, 0, 1), "TEXT", text="PC CHECK")
    hot = decals.add(barrel, 0, (0.06, 0.0, 0.1), (1, 0, 0), "STICKER", sticker="WARN_HOT")
    _check(len(decals.items_of(panel)) == 2 and len(decals.items_of(barrel)) == 1, "the decals were not added")
    shown = [o for o in bpy.data.objects if decals.is_decal(o)]
    _check(len(shown) >= 3, f"only {len(shown)} decals are shown on the model")
    _check(warn.width > 0 and text.width > 0 and hot.width > 0, "a decal has no size")
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "decals", "Decals (processor, draft)")
    return f"{len(shown)} decals; render {info['seconds']} s"


@line("looks.materials", "Materials: the material sheet", "0.2.39",
      what="Every ready-made material on a block with a chamfer, a disc and a shaft, rendered with Cycles: "
           "judge metals, paint, rubber and glass in one picture")
def looks_materials(ctx):
    from ..blender import material_sheet
    from ..core import materials_lib
    scene = material_sheet.build()
    path = os.path.join(ctx.work, "material_sheet.png")
    try:
        if ctx.has_gpu:
            info = material_sheet.render(scene, path, "CYCLES", samples=64, width=1600, use_gpu=True)
        else:
            info = material_sheet.render(scene, path, "CYCLES", samples=12, width=800)
    finally:
        material_sheet.remove()
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "material_sheet", "Material sheet (Cycles)", model_check=False, width=1000,
                settings=f"{info['size'][0]} x {info['size'][1]}, {info['device']}")
    return f"{len(materials_lib.MATERIALS)} materials; render {info['seconds']} s on the {info['device']}"


@line("rules.switch", "Rule sets: switch and back", "0.2.13",
      what="Another rule set sorts the parts its way; hand picks stay; back to Standard")
def rules_switch(ctx):
    from ..blender import build, logic, rule_sets
    from ..core import rule_sets as RS
    from ..core import rules as R
    scene = ctx.fresh(MACHINE)
    s = scene.fresing
    frame = _ob(scene, "FRAME")
    logic.ensure_group(s, "PC check by hand")
    frame["fr_group_manual"] = "PC check by hand"
    logic.apply_rules(scene)
    other = RS.RuleSet("PC check", [R.Rule("Bolts", "is_standard", "any", "")], {"Bolts": ("stainless_brushed", "")}, {})
    preview = rule_sets.preview(scene, other)
    rule_sets.switch(scene, other)
    _check(_ob(scene, "ISO 7380 M6x12")[build.PROP_GROUP] == "Bolts", "the new rule set's rule did not sort")
    _check(frame[build.PROP_GROUP] == "PC check by hand", "a part put in a group by hand lost its group")
    rule_sets.switch(scene, RS.standard())
    _check(_ob(scene, "ISO 7380 M6x12")[build.PROP_GROUP] == "Fasteners black", "back to Standard did not sort back")
    return f"{preview['moved']} parts moved and back"


# ---------------------------------------------------------------------------
# motion
# ---------------------------------------------------------------------------

@line("joints.rotate", "Joint: rotate", "0.2.0", (Q, F), requires=("import.crane",),
      what="The crane's boom turns about its pin and comes back")
def joints_rotate(ctx):
    from ..blender import joints
    scene = ctx.scene_of("import.crane")
    j = _boom_joint(scene)
    before = _tip(scene).copy()
    joints.set_value(j, math.radians(30))
    _update()
    moved = (_tip(scene) - before).length
    joints.set_value(j, 0.0)
    _update()
    back = (_tip(scene) - before).length
    _check(moved > 0.5 and back < 1e-4, f"the boom did not turn as expected (tip moved {moved * 1000:.0f} mm, "
                                        f"back {back * 1000:.2f} mm)")
    joints.remove(scene, j)
    return f"tip moved {moved * 1000:.0f} mm at 30°"


@line("joints.stack", "Joints: slide riding on a rotate (stack)", "0.2.10",
      what="The trolley slides along the boom while the boom turns: the moves add up")
def joints_stack(ctx):
    from mathutils import Matrix, Vector

    from ..blender import joints
    scene = ctx.fresh(CRANE_A)
    jb = _boom_joint(scene)
    trolley = _ob(scene, "TROLLEY.ASM")
    cad = trolley.matrix_world.translation.copy()
    jt = joints.create(scene, "SLIDE", [trolley], cad, Vector((1, 0, 0)), base=_ob(scene, "BOOM.ASM"), name="Trolley")
    sign = 1 if joints.axis_world(jb)[1].y > 0 else -1
    joints.set_value(jb, math.radians(30))
    joints.set_value(jt, 0.2)
    _update()
    pivot = Vector((0.1, 0.3, 0.4))
    want = pivot + Matrix.Rotation(sign * math.radians(30), 3, "Y") @ (cad - pivot + Vector((0.2, 0, 0)))
    err = (trolley.matrix_world.translation - want).length
    _check(err < 1e-3, f"the trolley is {err * 1000:.1f} mm off where boom + slide put it")
    return "boom 30° + trolley 200 mm"


@line("joints.cylinder", "Cylinder: follows the arm, the stroke drives it", "0.2.25",
      what="The luffer's arm turns: the cylinder's rod eye stays on its pin; a set stroke turns the arm to the "
           "angle of the triangle pivot – barrel pin – rod pin")
def joints_cylinder(ctx):
    from mathutils import Matrix, Vector

    from ..blender import build, cylinders, joints
    scene = ctx.fresh(LUFFER)

    def at_y(name, y):              # the cylinder at y = 80 mm (there are two side by side)
        hits = [o for o in scene.objects if o.get(build.PROP_NAME) == name]
        _check(bool(hits), f"the test model has no part '{name}'")
        return min(hits, key=lambda o: abs(o.matrix_world.translation.y - y))

    along_y = Vector((0, 1, 0))
    pivot, barrel_pin, rod_pin = Vector((0.1, 0.08, 0.6)), Vector((0.5, 0.08, 0.15)), Vector((0.8, 0.08, 0.45))
    arm = joints.create(scene, "ROTATE", [_ob(scene, "ARM.ASM")], Vector((0.1, 0.2, 0.6)), along_y, name="Luff")
    c, _notes = cylinders.create(scene, [at_y("CYL.BARREL", 0.08)], [at_y("CYL.ROD", 0.08)],
                                 (barrel_pin, along_y, _ob(scene, "BASE.PIN")),
                                 (rod_pin, along_y, _ob(scene, "ARM.ROD.PIN")))
    _update()
    eye = at_y("ROD.EYE", 0.08)
    eye_centre = eye.matrix_world.inverted() @ rod_pin
    joints.set_value(arm, math.radians(20))
    _update()
    want = pivot + Matrix.Rotation(math.radians(20), 3, "Y") @ (rod_pin - pivot)
    err = (eye.matrix_world @ eye_centre - want).length
    _check(err < 1e-4, f"the rod's eye is {err * 1000:.2f} mm off its pin with the arm at 20°")
    cylinders.set_mode(scene, c, "DRIVE")
    cylinders.set_stroke(scene, c, 0.1)
    a, b = (barrel_pin - pivot).length, (rod_pin - pivot).length
    length0, length = (rod_pin - barrel_pin).length, c.closed_length + 0.1
    expected = (math.acos((a * a + b * b - length0 * length0) / (2 * a * b))
                - math.acos((a * a + b * b - length * length) / (2 * a * b)))
    got = joints.get_value(arm)
    _check(abs(got - expected) < 1e-4, f"stroke 100 mm turned the arm to {math.degrees(got):.2f}°, "
                                       f"not {math.degrees(expected):.2f}°")
    return f"eye on its pin to {err * 1000:.3f} mm; stroke 100 mm → arm {math.degrees(got):.2f}°"


@line("joints.mechanism", "Mechanisms: scissor lift height, slider-crank", "0.2.26",
      what="A 3-stage scissor lift is made from its arms (pins found by themselves): the platform goes to 1.5 m "
           "and every arm follows; a slider-crank's piston sits where the formula says")
def joints_mechanism(ctx):
    import time

    from ..blender import linkages
    scene = ctx.fresh(LINKAGES)

    def axis_xz(name):
        part = _ob(scene, name)
        p = part.matrix_world @ __import__("mathutils").Vector(part.data["fr_axes"][0:3])
        return p.x, p.z

    arms = [_ob(scene, f"LIFT.ARM.{s}.{i}") for i in (1, 2, 3) for s in ("IN", "OUT")]
    t0 = time.time()
    m = linkages.create(scene, "SCISSOR", [[a] for a in arms] + [[_ob(scene, "LIFT.PLATFORM.ASM")]],
                        base=_ob(scene, "LIFT.BASE.ASM"))
    ctx.metric("mechanism set-up", time.time() - t0, "s")
    t0 = time.time()
    m.height = 1.5
    ctx.metric("scissor 0.78 → 1.5 m", (time.time() - t0) * 1000.0, "ms")
    _update()
    _update()
    x, z = axis_xz("LIFT.PLATFORM.PIN")
    _check(abs(z - 1.6) < 1e-4, f"the platform's pin is at {z * 1000:.1f} mm, not 1600 mm")
    from ..blender import build
    rollers = [o for o in scene.objects if o.get(build.PROP_NAME) == "LIFT.ROLLER"]
    low = min(rollers, key=lambda o: o.matrix_world.translation.z)          # the bottom one, on the base
    p = low.matrix_world @ __import__("mathutils").Vector(low.data["fr_axes"][0:3])
    rx, rz = p.x, p.z
    want = math.cos(math.asin(0.5))                                  # 3 stages of 1 m at 30°: the roller at cos 30°
    _check(abs(rx - want) < 1e-4 and abs(rz - 0.1) < 1e-4,
           f"the bottom roller is at ({rx * 1000:.1f}, {rz * 1000:.1f}) mm, not ({want * 1000:.1f}, 100.0)")
    s = linkages.create(scene, "SLIDER", [[_ob(scene, n)] for n in ("CRANK.CRANK.ASM", "CRANK.ROD.ASM",
                                                                         "CRANK.PISTON.ASM")],
                        base=_ob(scene, "CRANK.BASE.ASM"))
    j = linkages.input_joint(scene, s)
    from ..blender import joints
    joints.set_value(j, math.radians(100))
    _update()
    _update()
    bx, bz = axis_xz("CRANK.CRANK.PIN")
    t = math.atan2(bz - 0.3, bx - 3.2)
    want = 3.2 + 0.1 * math.cos(t) + math.sqrt(0.09 - (0.1 * math.sin(t) - 0.02) ** 2)
    px, _pz = axis_xz("CRANK.ROD.PIN")
    _check(abs(px - want) < 1e-4, f"the piston's pin is at x {px * 1000:.2f} mm, not {want * 1000:.2f} mm")
    return f"platform 1500 mm, roller on its line; piston to {abs(px - want) * 1000:.3f} mm"


GCODE_TEST = """(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
G21 G90 G94 G17
T1 M6
S8000 M3
G0 X-40 Y-30 Z5
G1 Z-2 F600
G1 X40 F1500
G2 X40 Y30 I0 J30
G18 G3 X20 Z-2 I-10 K0
G17 G0 Z10
T2 M6
G98 G81 X-60 Y60 Z-5 R2 F300
X-40
G80
G53 G0 Z0
M30
"""


@line("motion.gcode", "G-code program drives X, Y, Z and the tool change", "0.2.30",
      what="The test gantry runs a short LinuxCNC program (lines, arcs in two planes, a tool change, drilling): "
           "the tool's tip follows the program, the new tool shows in the spindle, the toolpath is drawn")
def motion_gcode(ctx):
    import bpy
    from mathutils import Vector

    from ..blender import animation, gcode, joints
    from ..core import gcode as core
    scene = ctx.fresh(GANTRY)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool = _ob(scene, "TOOL T1 FLAT D6")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, _ob(scene, "STOCK 300x200x30"))
    _check(gcode.problem(scene) == "", f"the CNC set-up is not ready: {gcode.problem(scene)}")
    path = os.path.join(ctx.work, "pccheck_gcode.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(GCODE_TEST)
    a = scene.fresing.animations.add()
    a.name, a.tail = "G-code", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    from ..blender import tools
    gcode.tools_from_program(scene, b)                 # as the owner does: Tools from the program (task 0040)
    t1 = tools.row_of(scene, 1)
    _check(t1 is not None and tools.row_of(scene, 2) is not None, "Tools from the program did not add T1 and T2")
    tools.use_part(scene, t1, tool)                    # T1 is the tool in the spindle
    t0 = time.time()
    r = animation.bake(scene, a)
    ctx.metric("bake", time.time() - t0, "s")
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    prog = gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0]
    sch = core.Schedule(prog, gcode.timing(scene, a, b))
    tip = gcode._rest_tip(tool)[0]
    zero = scene.fresing.cnc.zero_empty
    worst = 0.0
    for f in range(1, r["frames"] + 1, 5):
        scene.frame_set(f)
        got = zero.matrix_world.inverted() @ (tool.matrix_world @ tip) / 0.001
        want = Vector(sch.point_at((f - 1) / 25.0)) - Vector(mach.g54)
        if not tool.hide_render:
            worst = max(worst, (got - want).length)
    _check(worst < 0.01, f"the tool's tip is {worst:.3f} mm away from the program's path")
    copy = next((o for o in bpy.data.objects if o.get(gcode.TAG) == "tool" and o.get("fr_cnc_t") == 2), None)
    scene.frame_set(r["frames"])
    _check(copy is not None and not copy.hide_render and tool.hide_render, "T2 does not show in the spindle "
           "after the tool change")
    _check(gcode.path_object() is not None, "no toolpath drawn")
    return f"tip on the path to {worst:.4f} mm, {r['frames']} frames, T1 → T2"


TOOLCHANGE_TEST = """(T1 D=6. CR=0. - flat end mill)
(T2 D=4. CR=2. - ball end mill)
(T3 D=5. CR=0. TAPER=118deg - drill)
(T4 D=8. CR=1. - bullnose end mill)
G21 G90
G0 X10 Y0 Z5
T2 M6
G1 X20 F600
T3 M6
G0 X30 Y10 Z5
T4 M6
G0 X40 Y20 Z5
T1 M6
G0 X0 Y0 Z5
M30
"""


@line("motion.toolchange", "Tool changes: by hand, and a tool changer with 8 pockets", "0.2.45",
      what="The test gantry changes tools by hand (short pause, the gloved hand, rendered as it takes the tool) and "
           "with a carousel of 8 pockets and 4 tools: every tool in its pocket from the first frame, the right "
           "pocket at the spindle at every change, the old tool back in its own pocket")
def motion_toolchange(ctx):
    import bpy
    from mathutils import Vector

    from ..blender import animation, cameras, gcode, joints, toolchange, tools
    from ..core import gcode as core
    scene = ctx.fresh(GANTRY)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool = _ob(scene, "TOOL T1 FLAT D6")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, _ob(scene, "STOCK 300x200x30"))
    _check(gcode.problem(scene) == "", f"the CNC set-up is not ready: {gcode.problem(scene)}")
    path = os.path.join(ctx.work, "pccheck_toolchange.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TOOLCHANGE_TEST)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Tool changes", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    gcode.tools_from_program(scene, b)
    rows = {n: tools.row_of(scene, n) for n in (1, 2, 3, 4)}
    _check(all(rows.values()), "Tools from the program did not add T1 … T4")
    tools.use_part(scene, rows[1], tool)
    tools.use_part(scene, rows[2], _ob(scene, "TOOL T2 BALL D4"))
    tools.use_part(scene, rows[3], _ob(scene, "TOOL T3 DRILL D5"))
    for n, length in ((1, 30), (2, 30), (3, 40), (4, 30)):
        rows[n].length = length * 0.001

    # by hand, with the hand
    _check(abs(b.gcode_tc_time - 1.0) < 1e-6 and not b.gcode_hand, "the pause is not 1 s / the hand is not off "
           "by default")
    b.gcode_hand = True
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, b, mach))
    c = sch.changes[0]
    hand = bpy.data.objects.get(toolchange.HAND_NAME)
    _check(hand is not None and c.hand is not None, "no hand at the manual tool change")
    out_t, _in_t = toolchange.TC.hand_events(*c.hand)
    f = 1 + (out_t + 0.15) * 25
    scene.frame_set(int(f))
    carried = next((o for o in bpy.data.objects if o.get("fr_cnc_carry") == 1), None)
    _check(not hand.hide_render and carried is not None and not carried.hide_render and tool.hide_render,
           "the hand does not hold the old tool after taking it out of the spindle")
    tip = tool.matrix_world @ gcode._rest_tip(tool)[0]
    pts = __import__("numpy").array([tuple(tip + Vector(d)) for d in ((-0.12, -0.3, -0.1), (0.12, 0.08, 0.12))])
    cam = cameras.add_camera(scene, "ISO", 50.0, "PC check hand", points=pts)
    scene.camera = cam
    _small_output(scene.fresing, 480, 360)
    _cpu_still(ctx, scene, "toolchange_hand", "Manual tool change: the hand takes T1 out (processor, draft)")
    hand_s = c.length

    # the tool changer: 8 pockets round the carousel, T1 in pocket 7, T2 and T3 in their CAD places
    animation.clear_keys(scene)
    car = _ob(scene, "CAROUSEL.ASM")
    joints.create(scene, "ROTATE", [car], Vector((0.5, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    cnc = scene.fresing.cnc
    cnc.changer = "ATC"
    cnc.carousel_joint = "Carousel"
    rows[1].pocket = 7
    station = Vector((0.56, 0, 0.14))
    toolchange.add_pocket(scene, _ob(scene, "CAROUSEL DISC"), station)
    cnc.pocket_count = 8
    why = toolchange.fill_carousel(scene)
    _check(not why, why)
    _check(not toolchange.problems(scene), "; ".join(toolchange.problems(scene)))
    t0 = time.time()
    r = animation.bake(scene, a)
    ctx.metric("bake", time.time() - t0, "s")
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, b, mach))
    changes = [x for x in sch.changes if x.length > 0]
    _check([(x.old_pocket, x.new_pocket) for x in changes] == [(7, 1), (1, 3), (3, 4), (4, 7)],
           "the tools go to the wrong pockets: " + ", ".join(f"{x.old_pocket}->{x.new_pocket}" for x in changes))
    scene.frame_set(1)
    in_pocket = {o["fr_cnc_pocket"]: o for o in bpy.data.objects if "fr_cnc_pocket" in o}
    _check(sorted(in_pocket) == [1, 4] and in_pocket[1].hide_render and not in_pocket[4].hide_render,
           "the tools are not shown in their pockets on the first frame")
    pockets = {p.number: p for p in cnc.pockets}
    worst = 0.0
    for x in changes:
        for when, pk in ((x.drop, x.old_pocket), (x.swap, x.new_pocket)):
            fr = 1 + when * 25
            scene.frame_set(int(fr), subframe=fr - int(fr))
            got = toolchange.pocket_world(pockets[pk])[0]
            worst = max(worst, (got - station).length / 0.001)
    _check(worst < 0.01, f"a pocket is {worst:.3f} mm away from the spindle when the tool is swapped")
    t3 = _ob(scene, "TOOL T3 DRILL D5")
    fr = 1 + (changes[2].drop + 0.1) * 25
    scene.frame_set(int(fr))
    _check(not t3.hide_render, "T3 is not back in its pocket after the change")
    return f"hand {hand_s:.1f} s per change; ATC: 4 changes, pockets at the spindle to {worst:.4f} mm"


@line("motion.doublearm", "Double-arm tool changer: grip, pull, half turn, push", "0.2.51",
      what="The test mill with a double-arm changer and a 12-pot magazine changes three BT30 tools: the pot tips "
           "down, the arm grips both tools, pulls, turns 180° and pushes; every hand-over within 0.01 mm, the old "
           "tool in the pot the new one came from; rendered at the half turn")
def motion_doublearm(ctx):
    import bpy
    import numpy as np
    from mathutils import Vector

    from ..blender import animation, cameras, doublearm, gcode
    from ..core import gcode as core
    scene = ctx.fresh(ATC)
    path = os.path.join(ctx.work, "pccheck_doublearm.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doublearm.TEST_PROGRAM)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Double-arm", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    doublearm.set_up_test_model(scene, b)
    bad = [t for ok, t in doublearm.check(scene) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    t0 = time.time()
    r = animation.bake(scene, a)
    ctx.metric("bake", time.time() - t0, "s")
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, b, mach))
    arm = [x for x in sch.changes if x.kind == "arm"]
    _check([(x.tool, x.new_pocket) for x in arm] == [(2, 2), (3, 5), (1, 2)],
           "the tools go to the wrong pots: " + ", ".join(f"T{x.tool} from {x.new_pocket}" for x in arm))
    rows = {p.number: p for p in scene.fresing.cnc.pockets}

    def world(o):
        return o.parent.matrix_world @ o.matrix_parent_inverse @ o.matrix_basis

    def gap(p, q):
        me = p.data
        idx = range(0, len(me.vertices), max(1, len(me.vertices) // 6))
        mp, mq = world(p), world(q)
        return max((mp @ me.vertices[i].co - mq @ me.vertices[i].co).length for i in idx) / 0.001

    def held(n, tag, parent=None):
        return next(o for o in bpy.data.objects if o.get(tag) == n and (parent is None or o.parent is parent)
                    and not o.hide_render)

    def spindle_of(n):
        return mach.tool if n == 1 else gcode.copies()[n]

    worst = 0.0
    fps = 25
    for x in arm:
        times = x.arm_times()
        pot = rows[x.new_pocket].obj
        for when, pairs in ((times["grip"][1] + 1e-4, ((x.old, "spindle"), (x.tool, "pot"))),
                            (times["push"][1] - 1e-4, ((x.tool, "spindle"), (x.old, "pot")))):
            fr = 1 + when * fps
            scene.frame_set(int(fr), subframe=fr - int(fr))
            for n, other in pairs:
                on_arm = held(n, "fr_cnc_carry")
                there = spindle_of(n) if other == "spindle" else next(
                    o for o in bpy.data.objects if o.get("fr_cnc_pocket") == n and o.parent is pot)
                worst = max(worst, gap(on_arm, there))
    _check(worst < 0.01, f"a tool jumps {worst:.3f} mm when it goes from one holder to the next")
    ctx.metric("handover", worst * 1000.0, "µm")
    first = arm[0]
    t = first.arm_times()
    ctx.metric("change", t["back"][1] - t["grip"][0], "s")
    mid = (t["swap"][0] + t["swap"][1]) / 2
    fr = 1 + mid * fps
    scene.frame_set(int(fr), subframe=fr - int(fr))
    centre = Vector((-0.13, 0.0, 0.24))
    pts = np.array([tuple(centre + Vector(d)) for d in ((-0.2, -0.16, -0.12), (0.2, 0.16, 0.1))])
    cam = cameras.add_camera(scene, "ISO", 50.0, "PC check arm", points=pts)
    scene.camera = cam
    _small_output(scene.fresing, 480, 360)
    _cpu_still(ctx, scene, "doublearm", "Double-arm changer at its half turn (processor, draft)")
    return (f"3 changes, T1 back from pot 2; hand-overs within {worst:.4f} mm; arm {t['back'][1] - t['grip'][0]:.2f} "
            "s per change")


@line("milling.rotary", "4th and 5th axis: rotary table and trunnion", "0.2.52",
      what="The 4-axis test mill turns its round bar while a slot is milled wrapped round it and two flats are cut "
           "(Plain); the 5-axis trunnion tilts and turns its block while the tool follows the part (TCP); the cut "
           "depths are measured, the tool tip stays on its point of the part within 0.01 mm; rendered")
def milling_rotary(ctx):
    import math

    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from ..blender import animation, cameras, gcode, machining, rotary
    from ..core import gcode as core

    def program(scene, name, text):
        path = os.path.join(ctx.work, f"pccheck_{name}.ngc")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        a = scene.fresing.animations.add()
        a.name, a.tail = name, 0.0
        b = a.blocks.add()
        b.kind = "GCODE"
        b.gcode_file = path
        b.gcode_speed, b.gcode_fit = "FIT", 6.0
        return a, b

    # 5 axes first (no render): the tool tip on its point of the turning block
    scene = ctx.fresh(FIVE_AXIS)
    a, b = program(scene, "5axis", rotary.TEST_PROGRAM_5AXIS)
    rotary.set_up_test_model(scene, b, five=True, milling=False)
    bad = [t for ok, t in rotary.check(scene) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, b, mach))
    tip_l = gcode._rest_tip(mach.tool)[0]
    wp = mach.workpiece
    scene.frame_set(1)
    home_inv = wp.matrix_world.inverted()
    worst = 0.0
    for k in range(60):
        t = sch.duration * (k + 0.5) / 60
        if any(c.start <= t <= c.start + c.length for c in sch.changes):
            continue
        fr = 1 + t * 25
        scene.frame_set(int(fr), subframe=fr - int(fr))
        want = wp.matrix_world @ (home_inv @ (mach.zero + mach.rot @ (Vector(sch.point_at(t)) - Vector(mach.g54))
                                              * 0.001))
        worst = max(worst, ((mach.tool.matrix_world @ tip_l) - want).length / 0.001)
    _check(worst < 0.01, f"with TCP the tool tip strays {worst:.3f} mm from its point on the turning block")
    ctx.metric("tcp", worst * 1000.0, "µm")

    # 4 axes, Plain: the wrapped slot and the flats are cut into the bar
    scene = ctx.fresh(FOUR_AXIS)
    a, b = program(scene, "4axis", rotary.TEST_PROGRAM_4AXIS)
    rotary.set_up_test_model(scene, b)
    t0 = time.time()
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    scene.frame_set(1)
    home = machining.workpiece(scene).matrix_world.copy()
    machining.sample(scene)
    end = scene.frame_end
    _check(machining.refresh(scene, frame=end, force=True), machining.status(scene))
    ctx.metric("cut", time.time() - t0, "s")
    me = machining.settings(scene).cut_mesh
    me.calc_loop_triangles()
    w = home
    verts = [w @ v.co for v in me.vertices]
    bvh = BVHTree.FromPolygons(verts, [tuple(t.vertices) for t in me.loop_triangles], all_triangles=True)

    def radius(x, ang):
        d = Vector((0.0, -math.sin(math.radians(ang)), math.cos(math.radians(ang))))
        start = Vector((x * 0.001, 0.0, 0.15)) + d * 0.06
        hit = bvh.ray_cast(start, -d)[0]
        return 60.0 - ((hit - start).length / 0.001) if hit is not None else 0.0
    got = [radius(-90.0 + 80.0 * th / 360.0, th) for th in (90.0, 270.0)] + [radius(35.0, 0.0), radius(35.0, 180.0)]
    want = [23.0, 23.0, 22.0, 22.0]
    err = max(abs(g - w_) for g, w_ in zip(got, want))
    _check(err < 0.05, "the cuts on the bar are not where the program puts them: radius "
           + ", ".join(f"{g:.2f}" for g in got) + " mm (should be 23, 23, 22, 22)")
    scene.frame_set(int(end * 0.3))
    pts = [(-0.12, -0.03, 0.12), (0.12, 0.03, 0.2)]
    import numpy as np
    cam = cameras.add_camera(scene, "ISO", 50.0, "PC check rotary", points=np.array(pts))
    scene.camera = cam
    _small_output(scene.fresing, 480, 360)
    _cpu_still(ctx, scene, "rotary", "4th axis: the bar turns, the slot wraps round it (processor, draft)")
    return f"cut depths within {err:.3f} mm; TCP tip within {worst:.4f} mm"


def _ob_v(scene, name):
    """A part by name, also when CAD added a version ("Section 1 v8")."""
    from ..blender import build
    for o in scene.objects:
        n = o.get(build.PROP_NAME, "")
        if o.get(build.PROP_KIND) == "part" and (n == name or n.startswith(name + " v")):
            return o
    raise RuntimeError(f"the test model has no part '{name}'")


@line("machining.waycover", "Way covers follow a machine axis", "0.2.28", modes=(F,),
      what="Five cover sections follow a 500 mm slide axis: 100, 200, 300, 400, 500 mm; the 5-section "
           "way-cover model with its housing counting: 105 mm steps")
def machining_waycover(ctx):
    from mathutils import Vector

    from ..blender import joints, waycover
    scene = ctx.fresh(WAYCOVER)

    def min_x(o):
        return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)

    names = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
             ["COVER.5"]]
    rest = [min_x(_ob(scene, g[0])) for g in names]
    axis = joints.create(scene, "SLIDE", [_ob(scene, "CARRIAGE")], Vector((0.1, 0.15, 0.1)), Vector((1, 0, 0)),
                         name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, 0.5
    c = waycover.settings(scene)
    c.axis, c.total = "X axis", 0.5
    for g in names:
        waycover.add_section(scene, [_ob(scene, n) for n in g])
    built, problems = waycover.make(scene)
    _check(built == 5 and not problems, f"the way cover was not made: {problems}")
    joints.set_value(joints.find(scene, "X axis"), 0.5)
    _update()
    _update()
    got = [(min_x(_ob(scene, g[0])) - r) * 1000.0 for g, r in zip(names, rest)]
    for k, mm in enumerate(got, start=1):
        _check(abs(mm - 100.0 * k) < 0.05, f"section {k} moved {mm:.2f} mm, not {100 * k} mm")
    _check(joints.couplings_simple(scene), "the cover couplings need Python scripts (they must not)")
    # the 5-section way-cover model: the housing counts as the first section, 420 mm in 4 steps of 105 mm
    scene = ctx.fresh(WAYCOVER_OWNER)
    plate = _ob_v(scene, "Mounting plate")
    ax = joints.create(scene, "SLIDE", [], Vector((0, 0, 0)), Vector((0, 0, 1)), name="Axis", base=plate,
                       allow_empty=True)
    ax.use_limits = True
    ax.slide_min, ax.slide_max = -0.21, 0.21
    c = waycover.settings(scene)
    c.axis, c.housing_counts = "Axis", True
    _check(waycover.read_total(scene) == "", "the travel could not be read from the axis")
    for k in range(1, 6):
        waycover.add_section(scene, [_ob_v(scene, f"Section {k}")])
    built, problems = waycover.make(scene)
    _check(built == 5 and not problems, f"the way-cover model was not set up: {problems}")
    joints.set_value(joints.find(scene, "Axis"), 0.21)
    _update()
    _update()
    z = [min((o.matrix_world @ Vector(cc)).z for cc in o.bound_box) for o in
         (_ob_v(scene, f"Section {k}") for k in range(1, 6))]
    gaps = [(b - a) * 1000.0 for a, b in zip(z, z[1:])]
    _check(all(abs(g - 115.0) < 0.05 for g in gaps), "the sections are not 115 mm apart when fully open: "
           + ", ".join(f"{g:.1f}" for g in gaps))
    return f"5 sections to {got[-1]:.1f} mm; way-cover model open: gaps {gaps[0]:.1f} mm"


@line("machining.waycover_two", "Two way covers on one axis", "0.2.61", modes=(F,),
      what="A cover each side of the carriage on one 500 mm axis, the plate next to the carriage bolted to it (the "
           "carriage section): the left cover opens and the right one closes, section k by k/5 of the axis; a Build "
           "gives no warning")
def machining_waycover_two(ctx):
    from mathutils import Vector

    from ..blender import animation, joints, waycover
    scene = ctx.fresh(WAYCOVER_TWO)

    def min_x(o):
        return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)

    rest = {f"{s}{k}": min_x(_ob(scene, f"COVER.{s}.{k}")) for s in "LR" for k in range(1, 6)}
    covers = waycover.set_up_test_model(scene, carriage=True)
    _check(len(covers) == 2 and all(waycover.is_made(scene, x) for c in covers for x in c.sections),
           "the two covers were not made")
    _check(all(c.sections[4].carriage for c in covers), "the sections next to the carriage are not carriage sections")
    worst = 0.0
    for axis in (0.5, 0.2):
        joints.set_value(joints.find(scene, "X axis"), axis)
        _update()
        _update()
        for key, r in rest.items():
            k = int(key[1:])
            mm = (min_x(_ob(scene, f"COVER.{key[0]}.{k}")) - r) * 1000.0
            worst = max(worst, abs(mm - axis * 1000.0 * k / 5))
            _check(abs(mm - axis * 1000.0 * k / 5) < 0.05,
                   f"section {k} of the {'left' if key[0] == 'L' else 'right'} cover moved {mm:.2f} mm, not "
                   f"{axis * 1000.0 * k / 5:.1f} mm")
    a = scene.fresing.animations.add()
    a.name, a.fps = "Covers", "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from, b.to_dist = "JOINT", "X axis", 0, 2, False, 0.0
    res = animation.bake(scene, a)
    _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    return f"2 covers, 10 sections, worst {worst:.3f} mm off; no warning at Build"


@line("animation.clash", "Clash check: parts that run into each other", "0.2.53",
      what="An arm comes down onto another one (6.0 mm deep at the end): the check finds that pair, its frames and "
           "depth; an "
           "arm swung past a thin post within one frame is caught between the frames; pins turning in their bores "
           "give no clash")
def animation_clash(ctx):
    from ..blender import animation, clash, tour
    scene = ctx.fresh(CLASH)
    s = scene.fresing
    a = s.animations.add()
    a.name, a.tail, a.fps = "Arms meet", 0.0, "25"
    tour.clash_arms(scene, a)
    animation.bake(scene, a)
    t0 = time.time()
    run = clash.check(scene)
    ctx.metric("clash check", time.time() - t0, "s")
    rows = [r for r in run.rows if r.kind == "CLASH"]
    _check(len(rows) == 1, f"{len(rows)} clashes found, not 1: " + "; ".join(clash.core.row_text(r) for r in rows[:3]))
    r = rows[0]
    _check({r.a, r.b} == {"ARM.A", "ARM.B"}, f"the clash found is {r.a} × {r.b}, not the two arms")
    _check(abs(r.depth * 1000 - tour.CLASH_DEPTH) < 0.2, f"the arms are {r.depth * 1000:.2f} mm deep, not 6.0 mm")
    _check(any(m.name.startswith(clash.MARK) for m in scene.timeline_markers), "no marker on the time line")
    # an arm swung through a thin post in one frame (0.04 s): found between the frames
    fast = s.animations.add()
    fast.name, fast.tail, fast.fps = "Fast swing", 0.2, "25"
    b = fast.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from, b.to_angle = "JOINT", "Arm A", 0.0, 0.04, True, math.radians(90)
    animation.bake(scene, fast)
    run2 = clash.check(scene)
    post = [x for x in run2.rows if x.kind == "CLASH" and "POST" in (x.a, x.b)]
    _check(bool(post), "an arm swung through a post within one frame and was not found")
    _check(post[0].t_deep != round(post[0].t_deep), "the post was found on a frame, not between frames")
    return f"{clash.core.row_text(r)}; post found at frame {post[0].t_deep:.2f}; {run.stats['seconds']:.1f} s"


@line("couplings.motor", "Coupling + motor + Run motor step", "0.2.18",
      what="A motor drives the trolley and the trolley turns its wheel; the Run motor step bakes")
def couplings_motor(ctx):
    from mathutils import Vector

    from ..blender import animation, joints
    scene = ctx.fresh(CRANE_A)
    X, Y = Vector((1, 0, 0)), Vector((0, 1, 0))
    tr = _ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [tr], tr.matrix_world.translation.copy(), X, name="Trolley")
    w = _ob(scene, "WHEEL", 0)
    joints.create(scene, "ROTATE", [w], w.matrix_world.translation.copy(), Y, name="Wheel")
    cover = _ob(scene, "COVER")
    joints.create(scene, "ROTATE", [cover], cover.matrix_world.translation.copy(), X, name="Motor")
    joints.set_motor(scene, joints.find(scene, "Motor"), True)
    joints.set_follows(scene, joints.find(scene, "Trolley"), "Motor", ratio=50.0)      # 50 mm per turn
    joints.set_follows(scene, joints.find(scene, "Wheel"), "Trolley", ratio=360.0 / (math.pi * 50))
    joints.set_value(joints.find(scene, "Motor"), 2 * 2 * math.pi)
    _update()
    trolley = joints.get_value(joints.find(scene, "Trolley"))
    wheel = joints.get_value(joints.find(scene, "Wheel"))
    _check(abs(trolley - 0.1) < 1e-4, f"2 motor turns moved the trolley {trolley * 1000:.1f} mm, not 100 mm")
    _check(abs(wheel - 4.0) < 1e-3, f"the wheel turned {math.degrees(wheel):.0f}°, not {math.degrees(4.0):.0f}°")
    joints.set_value(joints.find(scene, "Motor"), 0.0)
    a = scene.fresing.animations.add()
    a.name, a.fps, a.tail = "Run", "25", 0.0
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.speed_rpm, b.easing = "MOTOR", "Motor", 0.0, 5.0, 12.0, "LINEAR"
    info = animation.bake(scene, a)
    scene.frame_set(info["frames"])
    turns = joints.get_value(joints.find(scene, "Motor")) / (2 * math.pi)
    animation.clear_keys(scene)
    _check(abs(turns - 1.0) < 0.01, f"12 rpm for 5 s gave {turns:.2f} turns, not 1")
    return "motor → trolley → wheel; 12 rpm × 5 s = 1 turn"


@line("states.poses", "Poses, explode, visibility, saved scenes", "0.2.0",
      what="Save a pose, explode, hide a part, save a scene; each comes back exactly")
def states_all(ctx):
    from ..blender import build, cameras, joints, logic, states
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    j = _boom_joint(scene)
    joints.set_value(j, math.radians(20))
    _update()
    want = _tip(scene).copy()
    states.save_pose(scene, "Up")
    states.reset_pose(scene)
    _update()
    _check((_tip(scene) - want).length > 0.05, "Reset pose did not move the boom back")
    _check(states.apply_pose(scene, "Up"), "the pose could not be applied")
    _update()
    _check((_tip(scene) - want).length < 1e-4, "the pose did not bring the boom back")
    states.reset_pose(scene)
    root = build.model_roots(scene)[0]
    n = states.explode(scene, root, 0.5)
    _check(n >= 3, f"explode moved only {n} subassemblies")
    states.reset_pose(scene)
    cover = _ob(scene, "COVER")
    logic.set_hidden(cover, True)
    states.save_visibility(scene, "No cover")
    states.show_all(scene)
    _check(states.apply_visibility(scene, "No cover") and cover.hide_render, "the visibility set did not hide the cover")
    joints.set_value(j, math.radians(25))
    s.background = "TRANSPARENT"
    cam_a = scene.camera
    states.save_shot(scene, "Hero")
    cameras.add_camera(scene, "FRONT")
    joints.set_value(j, 0.0)
    states.show_all(scene)
    s.background = "COLOR"
    warnings = states.apply_shot(scene, "Hero")
    _check(not warnings, "; ".join(warnings))
    _check(scene.camera is cam_a and abs(math.degrees(joints.get_value(j)) - 25) < 1e-6 and cover.hide_render
           and s.background == "TRANSPARENT", "the saved scene did not bring camera, pose, visibility and background back")
    return f"explode moved {n}"


@line("model.update", "Model update A → B keeps the work", "0.2.0",
      what="A new revision of the crane: joints, poses and hidden parts are kept")
def model_update(ctx):
    import bpy

    from ..blender import build, joints, logic, states
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    j = _boom_joint(scene)
    joints.set_value(j, math.radians(20))
    logic.set_hidden(_ob(scene, "COVER"), True)
    states.save_pose(scene, "Work")
    _update()
    tip = _tip(scene).copy()
    root = build.model_roots(scene)[0]
    t0 = time.time()
    res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=root.name)
    ctx.metric("update", time.time() - t0, "s")
    _check(res == {"FINISHED"}, f"the model update returned {res}: {s.last_message}")
    _update()
    _check(len(s.joints) == 1 and joints.is_valid(s.joints[0]), "the joint was lost")
    _check(abs(math.degrees(joints.get_value(s.joints[0])) - 20) < 1e-6, "the joint lost its value")
    _check((_tip(scene) - tip).length < 1e-4, "the boom moved")
    _check(logic.is_hidden(_ob(scene, "COVER")), "the hidden cover is shown again")
    _check([x.text for x in s.report_new] == ["BOOM.LAMP"], "the new part of revision B was not reported")
    return f"{len(list(build.iter_parts(scene)))} parts, new: BOOM.LAMP"


@line("model.update_safe", "Model update across two models, labels, all or nothing", "0.2.41",
      what="The crane's boom turns on the machine's frame and has a label: updating either model keeps both; "
           "an update from a damaged file changes nothing")
def model_update_safe(ctx):
    import bpy
    from mathutils import Vector

    from ..blender import build, callouts, joints, reimport
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    _check(bpy.ops.fresing.import_step(filepath=MACHINE, quality="draft") == {"FINISHED"}, "the machine did not import")
    frame = next((o for o in scene.objects if o.get(build.PROP_NAME) == "FRAME"
                  and joints._root(o).get(build.PROP_NAME) == "TEST.MACHINE"), None)
    _check(frame is not None, "the test machine has no FRAME")
    j = joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], Vector((0.1, 0.3, 0.4)), Vector((0, 0, 1)),
                      name="Slew", base=frame)
    joints.set_value(j, math.radians(20))
    boom = _ob(scene, "BOOM")
    callouts.add(scene, boom, boom.matrix_world.translation, "Boom")
    _update()
    tip = _tip(scene).copy()

    def root(name):
        return next(r for r in build.model_roots(scene) if r.get(build.PROP_NAME) == name)

    for path, model in ((MACHINE, "TEST.MACHINE"), (CRANE_B, "TEST.CRANE")):
        res = bpy.ops.fresing.import_step(filepath=path, quality="draft", update_root=root(model).name)
        _check(res == {"FINISHED"}, f"updating {model} returned {res}: {s.last_message}")
        _update()
        j = joints.find(scene, "Slew")
        _check(j is not None and joints.is_valid(j), f"updating {model} lost the joint between the two models")
        _check(j.frame.parent is not None and joints._root(j.frame.parent).get(build.PROP_NAME) == "TEST.MACHINE",
               f"after updating {model} the joint no longer sits on the machine")
        _check((_tip(scene) - tip).length < 1e-4, f"updating {model} moved the boom")
        _check(s.callouts[0].part is _ob(scene, "BOOM"), f"updating {model} cut the label off its part")
    bad = os.path.join(ctx.work, "damaged import")
    os.makedirs(bad, exist_ok=True)
    with open(os.path.join(bad, "tree.json"), "w") as f:
        f.write("{}")
    with open(os.path.join(bad, "meshes.npz"), "wb") as f:
        f.write(b"damaged")
    n_obj = len(bpy.data.objects)
    try:
        reimport.update_model(bpy.context, root("TEST.CRANE"), bad)
        raise RuntimeError("an update from a damaged file did not stop")
    except reimport.UpdateFailed:
        pass
    _check(len(bpy.data.objects) == n_obj and joints.find(scene, "Slew") is not None
           and (_tip(scene) - tip).length < 1e-4, "a failed update changed the project")
    return "joint and label kept both ways; damaged file: nothing changed"


@line("model.two_copies", "The same STEP twice: two separate cranes", "0.2.44",
      what="The test crane imported twice: hiding a part of the second crane and updating it never touch the first")
def model_two_copies(ctx):
    import bpy

    from ..blender import build, logic, states
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    _check(bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"},
           "the second crane did not import")
    first, second = sorted(build.model_roots(scene), key=build.uid_scope)
    _check(build.uid_scope(second) != "", "the second crane got the same part IDs as the first")

    def cover(root):
        return next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER" and build.model_root_of(o) == root)

    logic.set_hidden(cover(second), True)
    states.save_visibility(scene, "Second cover off")
    states.show_all(scene)
    states.apply_visibility(scene, "Second cover off")
    _check(logic.is_hidden(cover(second)) and not logic.is_hidden(cover(first)),
           "the visibility set of the second crane hid the first crane's cover")
    first_name = first.name
    res = bpy.ops.fresing.import_step(filepath=CRANE_B, quality="draft", update_root=second.name)
    _check(res == {"FINISHED"}, f"updating the second crane returned {res}: {s.last_message}")
    first = bpy.data.objects[first_name]
    second = next(r for r in build.model_roots(scene) if r is not first)
    _check(not any(o.get(build.PROP_NAME) == "BOOM.LAMP" and build.model_root_of(o) == first for o in scene.objects),
           "updating the second crane changed the first")
    states.apply_visibility(scene, "Second cover off")
    _check(logic.is_hidden(cover(second)) and not logic.is_hidden(cover(first)),
           "after the update the visibility set hid the wrong crane's cover")
    return "two cranes kept apart"


@line("project.reopen", "Save + reopen a project", "0.1.0",
      what="The project is saved, opened again, and its joint still works")
def project_reopen(ctx):
    import bpy

    from ..blender import joints
    scene = ctx.fresh(CRANE_A)
    _boom_joint(scene)
    path = os.path.join(ctx.work, "PC check project.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    scene = bpy.context.scene
    j = scene.fresing.joints.get("Boom")
    _check(j is not None, "the joint is gone after opening the project again")
    before = _tip(scene).copy()
    joints.set_value(j, math.radians(30))
    _update()
    _check((_tip(scene) - before).length > 0.5, "the joint does not move after opening the project again")
    size = os.path.getsize(path) / 1e6
    return f"{size:.1f} MB"


# ---------------------------------------------------------------------------
# scene: surroundings, light, cameras
# ---------------------------------------------------------------------------

def _cpu_still(ctx, scene, key, title, model_check=True, quality="draft"):
    from ..blender import render
    s = scene.fresing
    s.use_gpu = False
    path = os.path.join(ctx.work, f"{key}.png")
    info = render.render_still(scene, s, quality, filepath=path)
    ctx.picture(path, key, title, model_check=model_check)
    return info


@line("motion.fade", "Fade to X-ray and a trail line", "0.2.59",
      what="The crane's cover fades to X-ray while the boom turns up and the trolley runs out; a line draws the "
           "trolley's path. A frame half way is rendered small (processor, draft), and its time compared with the "
           "same frame without the fade")
def motion_fade(ctx):
    import bpy
    from mathutils import Vector

    from ..blender import animation, joints, render, tour
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    tour._boom_joint(scene)
    trolley = _ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=_ob(scene, "BOOM.ASM"), name="Trolley")
    a = s.animations.add()
    a.name, a.tail, a.fps = tour.FADE_ANIM, 0.0, "25"
    tour.fade_and_trail(scene, a)
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with trail line", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_fade(scene)
    _small_output(s)
    s.use_gpu = False
    mid = 1 + round(1.25 * 25)                     # half way through the fade
    times = {}
    for key, fading in (("plain", False), ("fade", True)):
        if not fading:
            a.blocks[2].enabled = False
            animation.bake(scene, a)
        else:
            a.blocks[2].enabled = True
            animation.bake(scene, a)
        scene.frame_set(mid)
        path = os.path.join(ctx.work, f"fade_{key}.png")
        t1 = time.time()
        render.render_still(scene, s, "draft", filepath=path)
        times[key] = time.time() - t1
    ctx.picture(path, "fade", "Cover half way to X-ray, the trolley's trail (processor, draft)")
    epath = os.path.join(ctx.work, "fade_eevee.png")
    render.render_still(scene, s, "eevee", filepath=epath)            # the same frame in EEVEE
    ctx.picture(epath, "fade_eevee", "Cover half way to X-ray (EEVEE)")
    ctx.metric("render fading frame", times["fade"], "s")
    ratio = times["fade"] / max(times["plain"], 1e-3)
    bpy.context.view_layer.update()
    return f"{note}; fading frame {times['fade']:.1f} s vs {times['plain']:.1f} s without ({ratio:.2f}x)"


@line("scene.sea", "Surroundings: open sea", "0.2.12", what="The crane on the open sea (Simple), rendered small")
def scene_sea(ctx):
    from ..blender import surroundings
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.env_detail = "SIMPLE"
    s.background = "SEA"
    _check(surroundings.root_object() is not None, "the sea was not built")
    _small_output(s)
    info = _cpu_still(ctx, scene, "sea", "Open sea (processor, draft)", model_check=False)
    return f"rendered in {info['seconds']} s"


@line("scene.hall", "Surroundings: CNC hall", "0.2.12", what="The crane in the CNC hall (Simple), rendered small")
def scene_hall(ctx):
    from ..blender import surroundings
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.env_detail = "SIMPLE"
    s.background = "CNC"
    _check(surroundings.root_object() is not None, "the hall was not built")
    _small_output(s)
    info = _cpu_still(ctx, scene, "hall", "CNC hall (processor, draft)", model_check=False)
    return f"rendered in {info['seconds']} s"


@line("scene.looks", "Light looks", "0.2.17", what="All five light looks apply; Product studio rendered small")
def scene_looks(ctx):
    import bpy

    from ..core import studio
    scene = ctx.fresh(CRANE_A)
    for look in studio.LOOKS:
        res = bpy.ops.fresing.light_look(look=look)
        _check(res == {"FINISHED"}, f"light look {look} returned {res}")
    bpy.ops.fresing.light_look(look="PRODUCT")
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "look_product", "Product studio look (processor, draft)")
    return f"{len(studio.LOOKS)} looks; render {info['seconds']} s"


@line("scene.views", "Camera views", "0.2.17", what="Every one-click view frames the whole model")
def scene_views(ctx):
    import bpy
    import numpy as np

    from ..blender import build, cameras, render
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    _small_output(s, 64, 36)
    render.apply_output(scene, s)
    corners = []
    for o in build.iter_parts(scene):
        corners += [o.matrix_world @ Vector(c) for c in o.bound_box]
    bad = []
    for view in cameras.STANDARD_VIEWS:
        res = bpy.ops.fresing.camera_add(view=view)
        _check(res == {"FINISHED"}, f"view {view} returned {res}")
        _update()
        co = np.array([tuple(world_to_camera_view(scene, scene.camera, p)) for p in corners])
        if co[:, 0].min() < -0.01 or co[:, 0].max() > 1.01 or co[:, 1].min() < -0.01 or co[:, 1].max() > 1.01:
            bad.append(view)
    _check(not bad, f"these views cut the model off: {', '.join(bad)}")
    return f"{len(cameras.STANDARD_VIEWS)} views"


@line("scene.blur", "Background blur + sharp spot", "0.2.17", what="Blur on, a sharp spot on the trolley")
def scene_blur(ctx):
    from ..blender import cameras
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    cam = scene.camera
    s.camera_blur = "LITTLE"
    _check(cam.data.dof.use_dof, "the blur did not switch on")
    middle = cam.data.dof.focus_distance
    trolley = _ob(scene, "TROLLEY")
    cameras.set_focus(cam, scene, trolley, trolley.matrix_world.translation.copy())
    _check(abs(cam.data.dof.focus_distance - middle) > 0.005, "the sharp spot did not change the focus distance")
    _check(cameras.focus_marker(cam) is not None, "no marker for the sharp spot")
    return f"focus {cam.data.dof.focus_distance:.2f} m"


@line("scene.turntable", "Turntable video (queue)", "0.2.17",
      what="One-click turntable; its time test renders two frames in the background queue")
def scene_turntable(ctx):
    from ..blender import turntable
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.turntable_seconds = 2.0
    s.turntable_quality = "draft"
    s.use_gpu = ctx.has_gpu
    a = turntable.make(scene)["animation"]
    a.out_resolution, a.out_format, a.video = "preview", "square", "PNG"
    job = _queue_job(ctx, scene, "TEST", animation=a.name, minutes=10)
    ctx.picture(job.output, "turntable", "Turntable, middle frame (time test)")
    ctx.metric("per frame", _per_frame(job.message), "s/frame")
    return job.message


def _per_frame(message: str) -> float:
    try:
        return float(message.split(" s per frame")[0].split()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"no time per frame in '{message}'") from None


@line("camera.path", "Camera rides along a part and flies a path", "0.2.62",
      what="The crane's boom turns up while the trolley runs out; the camera rides on the boom for 2 s, then flies a "
           "path round the crane keeping the trolley in the middle. Its error numbers are measured; six frames are "
           "rendered small (processor, draft) as a contact sheet")
def camera_path(ctx):
    from mathutils import Vector

    from ..blender import animation, joints, render, tour
    from . import core, runner
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    tour._boom_joint(scene)
    trolley = _ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=_ob(scene, "BOOM.ASM"), name="Trolley")
    a = s.animations.add()
    a.name, a.tail, a.fps = tour.CAMERA_ANIM, 0.0, "25"
    tour.camera_rides(scene, a)
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_camera(scene)
    _small_output(s)
    s.use_gpu = False
    frames = [round(1 + k * (info["frames"] - 1) / 5) for k in range(6)]
    pics = []
    for f in frames:
        scene.frame_set(f)
        path = os.path.join(ctx.work, f"camera_{f:03d}.png")
        render.render_still(scene, s, "draft", filepath=path)
        pics.append(runner.read_pixels(path))
    for f, px in zip(frames, pics):
        bad = core.picture_problems(px, True)
        _check(not bad, f"frame {f} is {'; '.join(bad)}")
    ctx.picture_pixels(core.contact_sheet(pics, cols=3), "camera_path", "Ride on the boom, then fly round the crane",
                       width=760, settings=f"frames {', '.join(str(f) for f in frames)} (processor, draft)")
    return note


@line("video.finishing", "Logo and watermark on a picture (brand kit)", "0.2.23",
      what="A queue picture gets the brand-kit logo in a corner and a watermark across it")
def video_finishing(ctx):
    import numpy as np

    from ..blender import queue
    from . import runner
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = False
    _small_output(s)
    logo = os.path.join(ctx.work, "PC check logo.png")
    px = np.zeros((40, 80, 3), np.float32)
    px[...] = (0.9, 0.08, 0.08)
    runner.write_png(logo, px)
    s.still_logo, s.brand_logo, s.still_logo_size = "BL", logo, 0.25
    s.wm_kind, s.wm_size, s.wm_opacity, s.wm_text = "CUSTOM", 0.3, 1.0, "PC CHECK"
    s.out_file_type, s.background = "PNG", "COLOR"
    out = {}
    for mark in (False, True):
        job = {"id": f"pc{int(mark)}", "kind": "STILL", "shot": "", "camera": "", "quality": "draft",
               "out_dir": os.path.join(ctx.work, "finishing"), "label": "PC check", "watermark": mark}
        out[mark] = queue.run_job(scene, job, lambda *a: None, lambda: False)
    a, b = runner.read_pixels(out[False]), runner.read_pixels(out[True])
    h, w = a.shape[:2]
    corner = a[int(h * 0.75):, :int(w * 0.3)]
    _check(float((corner[..., 0] - corner[..., 2]).max()) > 0.5, "the logo is not in the bottom-left corner")
    centre = (slice(h // 4, 3 * h // 4), slice(w // 6, 5 * w // 6))
    _check(float(np.abs(b - a)[centre].max()) > 0.06, "the watermark is not on the picture")
    ctx.picture(out[True], "finishing", "Logo and watermark (processor, draft)")
    return "logo and watermark on the picture"


def _mill_scene(ctx, scale: float = 1.0, x_mm: float = 50.0):
    """The test mill with X/Y/Z slides, a short slot (plunge 25 mm, then 50 mm along X), the flat end
    mill as bit and the block as workpiece. ``scale`` makes the program longer (Heavy), ``x_mm`` the slot."""
    import bpy
    from mathutils import Vector

    from ..blender import animation, joints, machining
    from ..core import machining as core
    if not core.available():
        raise RuntimeError("the Manifold library did not load: run Install.bat again")
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Mill", 0.0
    for j, start, dur, to in (("Z", 0.0, 0.4 * scale, -25.0), ("X", 0.4 * scale, 0.8 * scale, x_mm)):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * 0.001
    frames = animation.bake(scene, a)["frames"]
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bit = _ob(scene, "END MILL D10")
    bit.select_set(True)
    bpy.context.view_layer.objects.active = bit
    _check(bpy.ops.fresing.mill_add_bit() == {"FINISHED"}, "the bit could not be picked")
    bit.select_set(False)
    stock = _ob(scene, "STOCK 200x200x40")
    stock.select_set(True)
    bpy.context.view_layer.objects.active = stock
    _check(bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}, "the block could not be picked")
    return scene, frames, stock


@line("milling.cut", "Milling: material disappears where the bit cuts", "0.2.19",
      what="The mill's bit cuts a slot into the block over a few frames")
def milling_cut(ctx):
    from ..blender import machining
    scene, frames, stock = _mill_scene(ctx)
    t0 = time.time()
    machining.sample(scene)
    for f in range(1, frames + 1, max(1, frames // 6)):
        scene.frame_set(f)
    scene.frame_set(frames)
    ctx.metric("read motion + 7 frames", time.time() - t0, "s")
    me = machining.settings(scene).cut_mesh
    _check(me is not None and stock.data is me, "the block does not show its cut")
    _check(len(me.polygons) > 12, "nothing was cut out of the block")
    return f"{len(me.polygons)} faces after the cut"


@line("milling.cut_look", "Milling: cut faces look freshly cut", "0.2.43",
      what="A slot in a mill-scale steel block: its walls and floor get machined steel, the outside keeps mill scale")
def milling_cut_look(ctx):
    import numpy as np

    from ..blender import machining
    scene, frames, stock = _mill_scene(ctx)
    g = scene.fresing.groups.get(stock.get("fr_group", ""))
    _check(g is not None, "the block has no material group in 3 Looks")
    g.material = "steel_raw"
    machining.sample(scene)
    scene.frame_set(frames)
    machining.refresh(scene, force=True)
    me = machining.settings(scene).cut_mesh
    _check(me is not None and stock.data is me, "the block does not show its cut")
    n = int(me.get(machining.CUT_SLOT, -1))
    _check(0 < n < len(stock.material_slots), "the milled block has no material slot for cut faces")
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    cut, outside = int((mi == n).sum()), int((mi != n).sum())
    _check(cut > 0, "no face of the slot has the cut look")
    _check(outside > 0, "the block's outside lost its own look")
    mat = stock.material_slots[n].material
    _check(mat is not None and mat.get("fr_material") == "steel_machined",
           f"cut faces show '{mat.name if mat else 'nothing'}', not machined steel")
    _check(stock.material_slots[0].material.get("fr_material") == "steel_raw", "the outside is not mill scale")
    return f"{cut} cut faces: {mat.name[len(machining.CUT_MAT_PREFIX):]}; {outside} faces keep the block's look"


@line("milling.chips", "Milling: chips fly", "0.2.22",
      what="Aluminium chips appear while the bit cuts the slot and land on the machine")
def milling_chips(ctx):
    import bpy

    from ..blender import chips, machining
    chips.forget()
    scene, frames, _stock = _mill_scene(ctx)
    machining.sample(scene)
    t0 = time.time()
    machining.settings(scene).chips = "FEW"
    scene.frame_set(frames)
    ctx.metric("work out", time.time() - t0, "s")
    n = sum(len(o.data.vertices) for o in (bpy.data.objects.get(chips.OBJ_RIDE), bpy.data.objects.get(chips.OBJ_WORLD))
            if o is not None)
    _check(n > 0, "no chips at the end of the cut")
    return f"{n} chips; {chips.family_text(scene)}"


AIR_POCKET = """(T1 D=10. CR=0. - flat end mill)
G21 G90 G94 G17
S9000 M3
G0 X-30 Y-20 Z5
M7
G1 Z-4 F900
G1 X30 F2400
G1 Y-6
G1 X-30
G1 Y8
G1 X30
G1 Y20
G1 X-30
M9
G0 Z20
M5
M30
"""


@line("milling.air", "Milling: air blast blows the chips away", "0.2.34",
      what="The test mill cuts a pocket with air on (M7 ... M9) through the spindle and blows the part clean at the "
           "end; chips on the block at the last frame without and with air, and the time per frame")
def milling_air(ctx):
    import bpy
    import numpy as np

    from ..blender import air, animation, chips, gcode, machining
    chips.forget()
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    from mathutils import Vector

    from ..blender import joints
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool, stock = _ob(scene, "END MILL D10"), _ob(scene, "STOCK 200x200x40")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, stock)
    _check(gcode.problem(scene) == "", f"the CNC set-up is not ready: {gcode.problem(scene)}")
    for ob, op in ((tool, bpy.ops.fresing.mill_add_bit), (stock, bpy.ops.fresing.mill_set_workpiece)):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        _check(op() == {"FINISHED"}, f"'{ob.name}' could not be picked for milling")
    path = os.path.join(ctx.work, "pccheck_air.ngc")
    a = scene.fresing.animations.add()
    a.name, a.tail = "Air", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_path = "FIT", 3.0, False

    def run(text, clean):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        b.gcode_clean, b.gcode_clean_time = clean, 1.0
        b.gcode_file = path
        gcode.step_changed(scene, b)
        frames = animation.bake(scene, a)["frames"]
        machining.sample(scene)
        machining.settings(scene).chips = "FEW"
        t0 = time.time()
        bk = chips.bake(scene, force=True)
        work = time.time() - t0
        _check(bk is not None and bk.count > 0, "no chips were worked out")
        t0 = time.time()
        shown = list(range(frames - 9, frames + 1))
        for f in shown:
            scene.frame_set(f)
        per = (time.time() - t0) / len(shown) * 1000.0
        s = machining.settings(scene)
        m0 = np.array(s["fr_wp_m"][:16]).reshape(4, 4)
        me = s.stock_mesh
        v = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", v)
        w = v.reshape(-1, 3) @ m0[:3, :3].T + m0[:3, 3]
        lo, hi = w.min(axis=0), w.max(axis=0)
        p = bk.at(frames)[0]["pos"]
        on = int(((p[:, 0] > lo[0]) & (p[:, 0] < hi[0]) & (p[:, 1] > lo[1]) & (p[:, 1] < hi[1])
                  & (p[:, 2] > hi[2] - 0.006)).sum())
        animation.clear_keys(scene)
        return on, per, work, bk

    off, per_off, work_off, _bk = run(AIR_POCKET.replace("M7\n", "").replace("M9\n", ""), False)
    on, per_on, work_on, bk = run(AIR_POCKET, True)
    ctx.metric("frame without air", per_off, "ms")
    ctx.metric("frame with air", per_on, "ms")
    ctx.metric("chips worked out, with air", work_on, "s")
    _check(off > 20, f"only {off} chips on the block without air: the test cut makes too few")
    _check(on <= max(2, off // 20), f"{on} of {off} chips still on the block at the end with air on")
    _check(bk.stats.get("air_s", 0) > 1.0, "the air did not blow (no M7 seen)")
    return (f"chips on the block at the end: {off} without air, {on} with air (blown clean 1 s); "
            f"{per_off:.0f} / {per_on:.0f} ms per frame; {air.codes_text(scene)}")


COOLANT_POCKET = """(T1 D=10. CR=0. - flat end mill)
G21 G90 G94 G17
S9000 M3
G0 X-30 Y-20 Z5
M8
G1 Z-4 F900
G1 X30 F2400
G1 Y-6
G1 X-30
G1 Y8
G1 X30
M9
G0 Z20
G4 P2
M5
M30
"""


@line("milling.coolant", "Milling: coolant floods the tool", "0.2.48",
      what="The test mill cuts a pocket with flood coolant (M8 ... M9) from two automatic hoses: jets and splash "
           "while it cuts, the block gets wet and dries after M9, a frame looks the same whatever frame came "
           "before; the time per frame with and without coolant and a Cycles picture of the flood")
def milling_coolant(ctx):
    import bpy
    import numpy as np
    from mathutils import Vector

    from ..blender import animation, coolant, gcode, joints, machining
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool, stock = _ob(scene, "END MILL D10"), _ob(scene, "STOCK 200x200x40")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, stock)
    _check(gcode.problem(scene) == "", f"the CNC set-up is not ready: {gcode.problem(scene)}")
    path = os.path.join(ctx.work, "pccheck_coolant.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(COOLANT_POCKET)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Coolant", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_path = "FIT", 3.0, False
    b.gcode_file = path
    gcode.step_changed(scene, b)

    def per_frame(frames):
        shown = list(range(max(1, frames - 30), frames - 10))
        t0 = time.time()
        for f in shown:
            scene.frame_set(f)
        return (time.time() - t0) / len(shown) * 1000.0

    frames = animation.bake(scene, a)["frames"]
    off = per_frame(frames)
    scene.fresing.coolant.enabled = True
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    sp = coolant.spans()
    _check(len(sp) == 1, f"{len(sp)} coolant spans, not 1 (M8 ... M9 not seen)")
    on = per_frame(frames)
    ctx.metric("frame without coolant", off, "ms")
    ctx.metric("frame with coolant", on, "ms")
    mid = int((sp[0, 0] + sp[0, 1]) / 2)

    def liquid(before):
        scene.frame_set(before)
        scene.frame_set(mid)
        jets = bpy.data.objects[coolant.JETS].data
        drops = bpy.data.objects[coolant.DROPS].data
        a_ = np.empty(len(jets.vertices) * 3)
        jets.vertices.foreach_get("co", a_)
        b_ = np.empty(len(drops.vertices) * 3)
        drops.vertices.foreach_get("co", b_)
        return a_, b_
    j1, d1 = liquid(10)
    j2, d2 = liquid(frames)
    _check(len(j1) > 0, "no jets while the coolant flows")
    _check(len(d1) > 0, "no splash at the tool while it cuts")
    _check(np.array_equal(j1, j2) and np.array_equal(d1, d2), "the same frame looks different after another frame")
    root = coolant.root()
    scene.frame_set(int(sp[0, 1]) - 1)
    wet = float(root[coolant.WET_PROP])
    _check(wet > 0.8, f"the block is only {wet:.2f} wet at the end of the flood")
    scene.frame_set(frames)
    later = float(root[coolant.WET_PROP])
    _check(later < wet, "the block does not dry after M9")
    n_wet = len(coolant.wet_parts(scene))
    _check(n_wet >= 1, "no part gets wet")
    # a picture of the flood: a camera close to the tool
    scene.frame_set(mid)
    cam = bpy.data.cameras.new("PC check coolant")
    co = bpy.data.objects.new("PC check coolant", cam)
    scene.collection.objects.link(co)
    tip = tool.matrix_world @ gcode._rest_tip(tool)[0]
    co.location = tip + Vector((0.12, -0.24, 0.09))
    co.rotation_euler = ((tip + Vector((0, 0, 0.012))) - co.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = co
    scene.fresing.out_resolution = "preview"
    info = _cpu_still(ctx, scene, "coolant", "Flood coolant at the tool (processor, draft)", model_check=False)
    ctx.metric("still with coolant", info["seconds"], "s")
    return (f"{len(j1) // 3} jet points, {len(d1) // 3} drops; wet {wet:.2f} at M9, {later:.2f} at the end; "
            f"{n_wet} wet parts; {off:.0f} / {on:.0f} ms per frame without / with coolant")


TOOLS_PROGRAM = """(TWO TOOLS)
G21 G90 G94 G17 G54
T1 M6
S3000 M3
G0 X-130 Y-50 Z5
G1 Z-1 F4000
G1 X130
G0 Z10
T2 M6
S6000 M3
G0 X40 Y40 Z5
G1 Z-8 F300
G0 Z10
M5
M30
"""


@line("milling.tools", "Milling: each tool of the tool list cuts with its own shape", "0.2.36",
      what="The test mill runs a program with a tool change: a Ø50 face mill on a BT30 arbor faces a strip 1 mm deep, "
           "then a Ø6 drill in a BT30 chuck (25 mm longer, tip to gauge line) drills a hole 8 mm deep; both are read "
           "back from the milled block, with the length offset and the time per frame")
def milling_tools(ctx):
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from ..blender import animation, gcode, joints, machining, tools
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool, stock = _ob(scene, "END MILL D10"), _ob(scene, "STOCK 200x200x40")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, stock)
    _check(gcode.problem(scene) == "", f"the CNC set-up is not ready: {gcode.problem(scene)}")
    for ob, op in ((tool, bpy.ops.fresing.mill_add_bit), (stock, bpy.ops.fresing.mill_set_workpiece)):
        for o in bpy.context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        _check(op() == {"FINISHED"}, f"'{ob.name}' could not be picked for milling")
    machining.settings(scene).detail = "FINE"
    face = tools.add_row(scene, "FACE", 1)
    face.diameter, face.lead_angle = 0.05, 1.5707963
    face.length, face.holder, face.holder_length = 0.04, "BT30", 0.045      # a BT30 arbor (task 0049)
    drill = tools.add_row(scene, "DRILL", 2)
    drill.diameter = 0.006
    drill.length, drill.holder, drill.holder_length = 0.05, "BT30", 0.06    # in a BT30 chuck: 25 mm longer
    path = os.path.join(ctx.work, "pccheck_tools.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(TOOLS_PROGRAM)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Tools", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_path, b.gcode_tc_time = "FIT", 4.0, False, 0.5
    b.gcode_file = path
    gcode.step_changed(scene, b)
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    lift = gcode.length_offsets(scene, gcode.Machine(scene), [1, 2], 1).get(2, 0.0) * 1000.0
    _check(abs(lift - 25.0) < 0.01, f"the drill's length offset is {lift:.2f} mm, not 25 mm (tip to gauge line: "
                                    "110 against 85 mm)")
    _check(len(gcode.corners(scene)) >= 2, "milling does not know the program's corners")
    frames = r["frames"]
    t0 = time.time()
    machining.sample(scene)
    ctx.metric("read motion", time.time() - t0, "s")
    t0 = time.time()
    shown = list(range(max(1, frames - 9), frames + 1))
    for f in shown:
        scene.frame_set(f)
    per = (time.time() - t0) / len(shown) * 1000.0
    ctx.metric("frame", per, "ms")
    _check(machining.refresh(scene, force=True), machining.status(scene) or "the block does not show its cut")
    me = stock.data
    mw = stock.matrix_world
    bvh = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    zero = gcode.settings(scene).zero_empty.matrix_world.translation

    def depth(x, y):
        hit = bvh.ray_cast(zero + Vector((x, y, 0.1)), Vector((0, 0, -1)))
        _check(hit[0] is not None, f"nothing under ({x * 1000:.0f}, {y * 1000:.0f}) mm")
        return (zero.z - hit[0].z) * 1000.0

    d_face, d_edge, d_drill = depth(0.0, -0.05), depth(0.0, -0.0245), depth(0.04, 0.04)
    _check(abs(d_face - 1.0) < 0.05, f"the face mill cut {d_face:.2f} mm deep, not 1 mm")
    _check(abs(d_edge) < 0.05, f"the face mill cut wider than Ø50 ({d_edge:.2f} mm deep 25.5 mm from its path)")
    _check(abs(d_drill - 8.0) < 0.05, f"the drill went {d_drill:.2f} mm deep, not 8 mm")
    return (f"face mill 1.00 → {d_face:.2f} mm, drill 8.00 → {d_drill:.2f} mm, BT30 length offset 25.00 → "
            f"{lift:.2f} mm; {per:.0f} ms per frame")


@line("milling.toolpath", "Milling: the app makes the toolpath", "0.2.55",
      what="The toolpath test model: a block and the finished part (pocket, rounded boss, dome, a cap that hangs "
           "over, a hole). The app makes the roughing (flat Ø10) and finishing (ball Ø10) program at Draft, adds its "
           "step, builds it and cuts to the end; the block is measured against the part from above")
def milling_toolpath(ctx):
    import numpy as np
    from mathutils import Vector

    from ..blender import animation, machining, toolpath
    machining._RUNTIME.clear()
    scene = ctx.fresh(TOOLPATH, "normal")
    toolpath.set_up_test_model(scene, detail="DRAFT")
    _check(toolpath.problem(scene) == "", toolpath.problem(scene))
    t0 = time.time()
    out = toolpath.make(scene)
    ctx.metric("make", time.time() - t0, "s")
    ctx.metric("moves", out["moves"])
    _check(not out["problems"], "; ".join(out["problems"][:2]))
    _check("Undercut" in out["undercut"], "the cap that hangs over was not reported as an undercut")
    a, _b = toolpath.step(scene)
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    t0 = time.time()
    machining.sample(scene)
    scene.frame_set(scene.frame_end)
    _check(machining.refresh(scene, force=True), machining.status(scene) or "the block does not show its cut")
    ctx.metric("cut to the end", time.time() - t0, "s")
    wp = machining.settings(scene).workpiece
    me = wp.data
    from mathutils.bvhtree import BVHTree
    bvh = BVHTree.FromPolygons([v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])

    def top(x, y):                          # mm, in the block's own space (the model's: base top at 55)
        hit = bvh.ray_cast(Vector((x * 0.001, y * 0.001, 0.2)), Vector((0, 0, -1)))
        _check(hit[0] is not None, f"nothing under ({x}, {y}) mm")
        return hit[0].z * 1000.0

    got = {"base top": (top(0.0, -30.0), 55.0), "pocket floor": (top(30.0, -21.0), 47.0),
           "boss top": (top(-40.0, -20.0), 65.0), "dome top": (top(-22.0, 18.0), 65.0)}
    for name, (z, want) in got.items():
        _check(z >= want - 0.01, f"the {name} was cut {want - z:.3f} mm too deep")
        _check(z <= want + 0.15, f"the {name} kept {z - want:.3f} mm of stock")
    worst = max(z - want for z, want in got.values())
    del np
    return (f"{out['moves']:,} moves made in {out['seconds']:.1f} s; base, pocket, boss and dome within "
            f"{worst:.3f} mm of the part; undercut reported")


# ---------------------------------------------------------------------------
# renders and the queue
# ---------------------------------------------------------------------------

def _crane_still_scene(ctx):
    """The crane with the Product studio look and a fresh camera."""
    import bpy
    scene = ctx.scene_of("import.crane") if ctx.ok("import.crane") else ctx.fresh(CRANE_A)
    bpy.ops.fresing.light_look(look="PRODUCT")
    s = scene.fresing
    s.background = "COLOR"
    s.out_format = "presentation"
    return scene


@line("render.gpu", "Still on the graphics card (Cycles, HD)", "0.1.0", (Q, F), requires=("import.crane",),
      what="A 1920 × 1080 picture of the crane on the graphics card, noise removal on the card")
def render_gpu(ctx):
    from ..blender import render
    ctx.need_gpu()
    scene = _crane_still_scene(ctx)
    s = scene.fresing
    s.use_gpu = True
    s.out_resolution = "hd"
    path = os.path.join(ctx.work, "gpu_hd.png")
    info = render.render_still(scene, s, "preview", filepath=path)
    _check(info["device"].startswith("GPU"), f"rendered on {info['device']}, not on the graphics card")
    denoise = "card" if getattr(scene.cycles, "denoising_use_gpu", False) else "processor"
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "gpu_hd", "Cycles on the graphics card, HD, Preview quality")
    return f"{info['size'][0]}×{info['size'][1]} in {info['seconds']} s, noise removal on the {denoise}"


@line("render.cpu", "Still on the processor (Cycles)", "0.1.0", requires=("import.crane",),
      what="A small Draft picture (480 × 270) on the processor, for comparison")
def render_cpu(ctx):
    from ..blender import render
    scene = _crane_still_scene(ctx)
    s = scene.fresing
    s.use_gpu = False
    s.out_resolution = "preview"
    path = os.path.join(ctx.work, "cpu_preview.png")
    info = render.render_still(scene, s, "draft", filepath=path)
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "cpu_preview", "Cycles on the processor, 540p, Draft")
    return f"{info['size'][0]}×{info['size'][1]} in {info['seconds']} s"


@line("render.eevee", "EEVEE: time per frame at HD", "0.2.4", requires=("import.crane",),
      what="Time test of a short motion at HD with Fast preview (EEVEE), in the background queue: two stills")
def render_eevee(ctx):
    scene = ctx.fresh(CRANE_A)
    j = _boom_joint(scene)
    a = _short_animation(scene, "PC check EEVEE HD", j.name, seconds=2.0, quality="eevee")
    a.out_resolution, a.out_format = "hd", "presentation"
    try:
        job = _queue_job(ctx, scene, "TEST", animation=a.name, minutes=10)
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise
    ctx.metric("per frame", _per_frame(job.message), "s/frame")
    ctx.picture(job.output, "eevee_hd", "EEVEE, HD, a middle frame", gpu_optional=True)
    return job.message


@line("queue.video", "Short MP4 video through the queue", "0.2.0", requires=("import.crane",),
      what="The boom turns a little (3 frames, Draft); the background queue renders them and makes an MP4")
def queue_video(ctx):
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    j = _boom_joint(scene)
    a = _short_animation(scene, "PC check video", j.name, seconds=0.08, quality="draft")    # 3 frames
    a.video = "MP4"
    t0 = time.time()
    job = _queue_job(ctx, scene, "ANIMATION", animation=a.name, minutes=10)
    ctx.metric("video", time.time() - t0, "s")
    _check(job.output.endswith(".mp4") and os.path.getsize(job.output) > 1000, "no MP4 video was made")
    frames = sorted(f for f in os.listdir(job.output[:-4]) if f.endswith(".png"))
    ctx.picture(os.path.join(job.output[:-4], frames[-1]), "video_last", "MP4 video, last frame (Draft)")
    return f"{len(frames)} frames, {os.path.getsize(job.output) // 1024} KB"


@line("video.labels", "Labels with lines on a picture and an MP4 with music", "0.2.27", requires=("import.crane",),
      what="A label points at a part of the crane in a picture; a short MP4 gets a picture card and music "
           "(a sound track as long as the video)")
def video_labels(ctx):
    import wave

    import numpy as np

    from ..blender import callouts, queue
    from . import runner
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = False
    _small_output(s)
    s.out_file_type, s.background = "PNG", "COLOR"
    boom = _ob(scene, "BOOM")
    callouts.add(scene, boom, boom.matrix_world.translation, "Boom")
    out = {}
    for on in (False, True):
        s.callouts_on = on
        job = {"id": f"pl{int(on)}", "kind": "STILL", "shot": "", "camera": "", "quality": "draft",
               "out_dir": os.path.join(ctx.work, "labels"), "label": "PC check", "watermark": False}
        out[on] = queue.run_job(scene, job, lambda *a: None, lambda: False)
    a, b = runner.read_pixels(out[False]), runner.read_pixels(out[True])
    _check(float(np.abs(b - a).max()) > 0.2, "the label is not on the picture")
    ctx.picture(out[True], "labels", "A label with a line to the boom (processor, draft)")
    # a short video with a picture in a corner and music under it
    s.callouts_on = True
    j = _boom_joint(scene)
    an = _short_animation(scene, "PC check music", j.name, seconds=0.2, quality="draft")
    an.video, an.fps = "MP4", "24"
    card_file = os.path.join(ctx.work, "PC check card.png")
    runner.write_png(card_file, np.full((40, 80, 3), (0.9, 0.1, 0.1), np.float32))
    c = an.cards.add()
    c.path, c.duration, c.mode = card_file, 0.2, "CORNER"
    wav = os.path.join(ctx.work, "PC check music.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes((np.sin(np.arange(22050 * 3) * 0.12) * 12000).astype("<i2").tobytes())
    an.music_on, an.music_file, an.music_fade_in, an.music_fade_out = True, wav, 0.1, 0.1
    job = _queue_job(ctx, scene, "ANIMATION", animation=an.name, minutes=10)
    _check(job.output.endswith(".mp4") and os.path.getsize(job.output) > 1000, "no MP4 video was made")
    import aud
    sound = aud.Sound(job.output)
    seconds = sound.length / sound.specs[0]
    frames = len([f for f in os.listdir(job.output[:-4]) if f.endswith(".png")])
    _check(abs(seconds - frames / 24.0) < 0.15, f"the music is {seconds:.2f} s long, the video {frames / 24.0:.2f} s")
    return f"label drawn; video with music: {frames} frames, sound {seconds:.2f} s"


@line("queue.frame_shown", "Queued picture of an animation frame = the view", "0.2.46", requires=("import.crane",),
      what="A built animation stopped at a frame (boom up, cover hidden, camera orbiting): Add image to the queue "
           "renders that frame, the same as Render image")
def queue_frame_shown(ctx):
    import bpy
    import numpy as np

    from ..blender import animation, build, queue, render
    from . import runner
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = False
    _small_output(s)
    from mathutils import Vector

    from ..blender import joints
    j = _boom_joint(scene)
    boom = _ob(scene, "BOOM")
    joints.set_value(j, math.radians(30))
    bpy.context.view_layer.update()
    up = (boom.matrix_world @ Vector((1.5, 0, 0))).z > 0.4      # the boom goes up, not into the floor
    joints.set_value(j, 0.0)
    a = _short_animation(scene, "PC check frame", j.name, angle_deg=30.0 if up else -30.0, seconds=2.0,
                         quality="draft")
    cover = _ob(scene, "COVER")
    h = a.blocks.add()
    h.kind, h.start, h.target_uid, h.target_name = "HIDE", 1.0, cover[build.PROP_UID], "COVER"
    c = a.blocks.add()
    c.kind, c.camera_mode, c.orbit_angle, c.start, c.duration = "CAMERA", "ORBIT", math.radians(90), 0.0, 2.0
    animation.bake(scene, a)
    scene.frame_set(40)
    view = os.path.join(ctx.work, "frame_view.png")
    render.render_still(scene, s, "draft", filepath=view)
    _check(bpy.ops.fresing.queue_add(kind="STILL") == {"FINISHED"}, "Add image did not work")
    q = s.queue[-1]
    job = {"id": q.job_id, "kind": "STILL", "shot": q.shot, "camera": "", "quality": "draft",
           "out_dir": os.path.join(ctx.work, "frame_queue"), "label": q.label, "watermark": False}
    out = queue.run_job(scene, job, lambda *a: None, lambda: False)       # what the background queue does
    _check(cover.hide_render, "the queue showed the cover that is hidden at this frame")
    diff = float(np.abs(runner.read_pixels(out) - runner.read_pixels(view)).mean())
    ctx.metric("difference", round(diff, 4), "")
    _check(diff < 0.02, f"the queued picture differs from the view (mean difference {diff:.3f})")
    ctx.picture(out, "queue_frame", "Queued picture of frame 40: boom up, cover hidden (processor, draft)")
    return f"same picture as the view (difference {diff:.4f})"


@line("queue.schemes", "Queued pictures in every paint scheme", "0.2.60", requires=("import.crane",),
      what="Every paint scheme (7 Render queue): the same view in two schemes, each file named after its scheme, "
           "the crane's yellow parts blue in the second; the open project keeps its colours")
def queue_schemes(ctx):
    import bpy
    import numpy as np

    from ..blender import cameras, logic, queue
    from . import runner
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = False
    _small_output(s)
    if scene.camera is None:
        cameras.add_camera(scene, "ISO")
    yellow = next((g for g in s.groups if g.color.upper() == "#F9A800"), None)
    _check(yellow is not None, "the crane has no yellow group")
    logic.save_scheme(s, "Factory")
    yellow.color = "RAL 5010"
    logic.save_scheme(s, "Blue")
    logic.apply_scheme(scene, "Factory")
    for i in reversed(range(len(s.queue))):
        s.queue.remove(i)
    _check(bpy.ops.fresing.queue_schemes(kind="STILL") == {"FINISHED"}, "Every paint scheme > Current view did "
                                                                         "not work")
    _check([j.scheme for j in s.queue] == ["Factory", "Blue"], f"jobs: {[j.label for j in s.queue]}")
    t0 = time.time()
    outs = {}
    for q in list(s.queue):                       # what the background queue does, one job after the other
        job = {"id": q.job_id, "kind": "STILL", "shot": q.shot, "camera": "", "quality": "draft", "scheme": q.scheme,
               "out_dir": os.path.join(ctx.work, "schemes"), "label": q.label, "watermark": False}
        outs[q.scheme] = queue.run_job(scene, job, lambda *a: None, lambda: False)
        logic.apply_scheme(scene, "Factory")      # the background queue opens the project afresh for every job
    ctx.metric("two pictures", time.time() - t0, "s")
    _check(all(os.path.basename(p).endswith(f"_{n}.png") for n, p in outs.items()),
           f"the files are not named after their scheme: {[os.path.basename(p) for p in outs.values()]}")
    a, b = runner.read_pixels(outs["Factory"])[..., :3], runner.read_pixels(outs["Blue"])[..., :3]
    changed = np.abs(a - b).max(axis=-1) > 0.1
    _check(changed.sum() > 50, "the two schemes gave the same picture")
    fa, fb = a[changed].mean(axis=0), b[changed].mean(axis=0)
    _check(fb[2] > fb[0] and fa[0] > fa[2], f"wrong colours: factory {fa.round(2)}, blue {fb.round(2)}")
    _check(yellow.color.upper() == "#F9A800", "queueing changed the project's colours")
    ctx.picture(outs["Blue"], "queue_schemes", "The same view queued in the scheme 'Blue' (processor, draft)")
    return f"2 pictures, {int(changed.sum())} pixels changed colour"


@line("queue.eevee", "Short EEVEE video through the queue", "0.2.4", (Q, F), requires=("import.crane",),
      what="The same short motion with Fast preview (EEVEE) in the background queue")
def queue_eevee(ctx):
    scene = ctx.fresh(CRANE_A)
    j = _boom_joint(scene)
    a = _short_animation(scene, "PC check EEVEE", j.name, seconds=0.2, quality="eevee")     # 6 frames
    a.video = "MP4"
    t0 = time.time()
    try:
        job = _queue_job(ctx, scene, "ANIMATION", animation=a.name, minutes=10)
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise
    secs = time.time() - t0
    frames = sorted(f for f in os.listdir(job.output[:-4]) if f.endswith(".png"))
    ctx.metric("video", secs, "s")
    ctx.metric("per frame", secs / max(1, len(frames)), "s/frame")
    ctx.picture(os.path.join(job.output[:-4], frames[-1]), "eevee_video_last", "EEVEE video, last frame",
                gpu_optional=True)
    return f"{len(frames)} frames in {secs:.0f} s (with starting the queue)"


@line("queue.time_test", "Time test", "0.2.4", requires=("import.crane",),
      what="Two frames of an animation with the real settings: time per frame")
def queue_time_test(ctx):
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    j = _boom_joint(scene)
    a = _short_animation(scene, "PC check time", j.name, seconds=2.0, quality="preview")
    job = _queue_job(ctx, scene, "TEST", animation=a.name, minutes=10)
    _check("s per frame" in job.message, f"no time per frame: {job.message}")
    ctx.metric("per frame", _per_frame(job.message), "s/frame")
    return job.message


@line("tour.make", "Test tour: the projects are made, every stop's Go works", "0.2.47",
      what="Makes the test tour (a small project per test model) and does Go and the number check of every stop, "
           "without pictures (the PC check's mode Test tour renders them)")
def tour_make(ctx):
    import bpy

    from .. import __version__
    from ..blender import tour
    folder = os.path.join(ctx.work, "Test tour")
    t0 = time.time()
    out = tour.build_all(folder, __version__)
    ctx.metric("make", time.time() - t0, "s")
    _check(not out["errors"], "; ".join(f"{tour.SETS[k].title}: {v}" for k, v in out["errors"].items()))
    bad = []
    for st in tour.STOPS:
        from . import runner
        runner.check_cancel()
        tour.open_set(folder, __version__, st.set)
        try:
            warnings = tour.apply(st, bpy.context.scene)
            if warnings:
                raise RuntimeError("; ".join(warnings[:2]))
            st.check(bpy.context.scene)
        except Exception as exc:  # noqa: BLE001 - every stop is tried; the failures are listed
            bad.append(f"{st.number}. {st.title}: {exc}")
    _check(not bad, " | ".join(bad[:4]))
    return f"{len(out['files'])} projects in {time.time() - t0:.0f} s, {len(tour.STOPS)} stops"


@line("updates.check", "Update check", "0.2.16", what="The update address answers (nothing is installed)")
def updates_check(ctx):
    import bpy

    from .. import __version__
    from ..core import updates as core
    url, source = core.index_url_from(bpy.utils.user_resource("CONFIG"))
    if not bpy.app.online_access:
        raise Skipped("Blender's online access is off, so the app does not look for updates")
    res = core.check(url, __version__, tuple(bpy.app.version), timeout=20)
    state = res.get("state")
    if state == "error":
        if source == "GitHub" and "HTTP 404" in res.get("message", ""):
            return "GitHub answers; no version published there yet"
        raise RuntimeError(f"{res.get('message')}: the app cannot look for updates on this PC")
    if state == "available":
        return f"update {res['version']} available"
    return f"{__version__} is the newest" if state != "needs_installer" else f"{res['version']} needs a new installer"


@line("updates.safe", "Safe updates (other windows, backup, old notes)", "0.2.42",
      what="Update now finds other Fresing Render windows, can put the old version back, ignores a note left by a "
           "stopped update (nothing is installed)")
def updates_safe(ctx):
    import json
    import shutil
    import subprocess
    import sys
    import tempfile

    import bpy

    from .. import update_helper as H
    from ..blender import project_lock
    me = os.getpid()
    exe = bpy.app.binary_path
    others: list = []
    if os.path.basename(exe).lower() in H.BLENDER_NAMES:      # (not Blender as a Python module: the tests)
        image = H.process_image(me)                  # Windows: QueryFullProcessImageNameW
        _check(bool(image), "the app cannot read which program a process runs: it cannot tell a second window")
        _check(os.path.basename(image).lower() in H.BLENDER_NAMES, f"this process is {os.path.basename(image)}")
        _check(me in H._all_pids(), "the list of running programs does not hold this one")
        _check(H._norm(image).startswith(H._norm(os.path.dirname(exe)).rstrip("\\/") + os.sep),
               "this Blender's own folder does not match its program's place")
        others = H.other_blenders(os.path.dirname(exe))
    work = tempfile.mkdtemp(prefix="fresing pc check é ")
    try:
        # a note left by an update that stopped: its number now belongs to another program (here: this Blender),
        # or its helper has ended
        note = os.path.join(work, H.BUSY_FILE)
        if os.path.basename(exe).lower() in H.BLENDER_NAMES:
            with open(note, "w", encoding="utf-8") as fh:
                json.dump({"pid": me, "to": "9.9.9", "started": time.time(), "exe": "python.exe"}, fh)
            _check(H.busy_helper(note) is None and not os.path.exists(note),
                   "an old update note would block Update now")
        from ..importer.runner import python_executable
        child = subprocess.Popen([python_executable(), "-c", "pass"], creationflags=H._child_flags())
        child.wait()
        with open(note, "w", encoding="utf-8") as fh:
            json.dump({"pid": child.pid, "to": "9.9.9", "started": time.time(), "exe": "python.exe"}, fh)
        _check(H.busy_helper(note) is None, "a note of an update whose helper has ended would block Update now")
        # backup and put back (a rename on the same disk), with a space and an accent in the path
        ext = os.path.join(work, "extensions", "fresing_render")
        os.makedirs(os.path.join(ext, "wheels"))
        with open(os.path.join(ext, "blender_manifest.toml"), "w", encoding="utf-8") as fh:
            fh.write('version = "0.0.1"\n')
        with open(os.path.join(ext, "wheels", "x.whl"), "wb") as fh:
            fh.write(b"x" * 1000)
        plan = {"ext_dir": ext, "backup_dir": os.path.join(work, "backup", "fresing_render"),
                "log_file": os.path.join(work, "log.txt")}
        backup = H.make_backup(plan)
        _check(bool(backup), "no backup of the extension could be made")
        shutil.rmtree(ext)
        _check(H.restore_backup(plan, backup) and H.installed_version(ext) == "0.0.1",
               "the old version could not be put back")
        # this window's own project lock is not "someone else"
        _check(project_lock._is_me(project_lock.me()), "this window counts its own project lock as someone else's")
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return "no other Fresing Render running" if not others else f"{len(others)} other Fresing Render running"


# ---------------------------------------------------------------------------
# the owner's own model: numbers only
# ---------------------------------------------------------------------------

@line("own.import", "Your model: import + sorting", "0.2.24", (OWN,),
      what="Import time, parts, unique parts, triangles, share sorted by the rules")
def own_import(ctx):
    from ..blender import build
    from ..core import rules as R
    t0 = time.time()
    scene = ctx.fresh(ctx.model, quality="normal", read_again=True)
    ctx.metric("import", time.time() - t0, "s")
    parts = list(build.iter_parts(scene))
    ctx.add_secrets(parts)
    unsorted = sum(1 for o in parts if o.get(build.PROP_GROUP) == R.FALLBACK_GROUP)
    ctx.metric("parts", len(parts), "")
    ctx.metric("unique parts", len({o.data.name for o in parts}), "")
    tris = 0
    for o in parts:
        o.data.calc_loop_triangles()
        tris += len(o.data.loop_triangles)
    ctx.metric("triangles", round(tris / 1e6, 2), "M")
    ctx.metric("sorted", round(100.0 * (len(parts) - unsorted) / max(1, len(parts)), 1), "%")
    return None


@line("own.gpu", "Your model: still on the graphics card", "0.2.24", (OWN,), requires=("own.import",),
      what="An HD picture of your model on the graphics card (Preview quality)")
def own_gpu(ctx):
    import bpy

    from ..blender import render
    ctx.need_gpu()
    scene = ctx.scene_of("own.import")
    bpy.ops.fresing.light_look(look="PRODUCT")
    s = scene.fresing
    s.use_gpu, s.background, s.out_format, s.out_resolution = True, "COLOR", "presentation", "hd"
    path = os.path.join(ctx.work, "own_gpu.png")
    info = render.render_still(scene, s, "preview", filepath=path)
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "own_gpu", "Your model on the graphics card (this PC only)")
    return None


def _own_time_test(ctx, quality: str):
    from ..blender import turntable
    scene = ctx.scene_of("own.import")
    s = scene.fresing
    s.use_gpu = ctx.has_gpu
    s.turntable_quality = quality
    a = turntable.make(scene)["animation"]
    a.quality = quality
    job = _queue_job(ctx, scene, "TEST", animation=a.name, minutes=30, quality=quality)
    ctx.metric("per frame", _per_frame(job.message), "s/frame")
    return None


@line("own.time_preview", "Your model: Time test, Preview", "0.2.24", (OWN,), requires=("own.import",),
      what="Time per frame of a turntable at HD, Preview quality (Cycles)")
def own_time_preview(ctx):
    return _own_time_test(ctx, "preview")


@line("own.time_eevee", "Your model: Time test, EEVEE", "0.2.24", (OWN,), requires=("own.import",),
      what="Time per frame of a turntable at HD with Fast preview (EEVEE)")
def own_time_eevee(ctx):
    try:
        return _own_time_test(ctx, "eevee")
    except RuntimeError as exc:
        ctx.gpu_optional(exc)
        raise


from . import heavy  # noqa: E402,F401 - registers the Heavy lines (task 0033)
