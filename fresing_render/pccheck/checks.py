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

from .core import Line, Skipped

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
MACHINE = os.path.join(DATA, "test_machine.step")
MATERIALS = os.path.join(DATA, "test_materials.step")
CRANE_A = os.path.join(DATA, "test_crane_a.step")
CRANE_B = os.path.join(DATA, "test_crane_b.step")
FACES = os.path.join(DATA, "test_faces_a.step")
MILL = os.path.join(DATA, "test_mill.step")
DECALS = os.path.join(DATA, "test_decals_a.step")
LUFFER = os.path.join(DATA, "test_cylinder_a.step")
LINKAGES = os.path.join(DATA, "test_linkage_a.step")

LINES: list[Line] = []
Q, F, OWN = "quick", "full", "own"


def line(id: str, title: str, since: str, modes=(F,), requires=(), what: str = ""):
    def deco(fn):
        LINES.append(Line(id, title, since, tuple(modes), fn, tuple(requires), what))
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
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < minutes * 60:
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


def _mill_scene(ctx):
    """The test mill with X/Y/Z slides, a short slot (plunge 25 mm, then 50 mm along X), the flat end
    mill as bit and the block as workpiece."""
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
    for j, start, dur, to in (("Z", 0.0, 0.4, -25.0), ("X", 0.4, 0.8, 50.0)):
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
