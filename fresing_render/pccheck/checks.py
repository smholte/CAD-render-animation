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
import re
import shutil
import time

from .core import Cancelled, Line, Skipped

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
MACHINE = os.path.join(DATA, "test_machine.step")
MATERIALS = os.path.join(DATA, "test_materials.step")
CRANE_A = os.path.join(DATA, "test_crane_a.step")
LOADS = os.path.join(DATA, "test_loads.step")          # task 0231: the invented loads (pump skid, container)
CRANE_B = os.path.join(DATA, "test_crane_b.step")
FACES = os.path.join(DATA, "test_faces_a.step")
MILL = os.path.join(DATA, "test_mill.step")
MILL_CABINET = os.path.join(DATA, "test_mill_cabinet.step")
TOOLPATH = os.path.join(DATA, "test_toolpath.step")
DECALS = os.path.join(DATA, "test_decals_a.step")
WELDMENT = os.path.join(DATA, "test_weldment.step")
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
FLEX_HOSES = os.path.join(DATA, "test_flex_hoses_a.step")
FLEX_CHAINS = os.path.join(DATA, "test_flex_chains_a.step")
FLEX_AVOID = os.path.join(DATA, "test_flex_avoid_a.step")
PATHS = os.path.join(DATA, "test_paths_a.step")
SPOOL = os.path.join(DATA, "test_spool.step")
TRACKS = os.path.join(DATA, "test_tracks.step")
SEA_CABLE = os.path.join(DATA, "test_sea.step")
MOVING_CABLE = os.path.join(DATA, "test_moving.step")
SWIVEL = os.path.join(DATA, "test_swivel.step")
SEQUENCE = os.path.join(DATA, "test_sequence.step")
SEQUENCE_FRAME = os.path.join(DATA, "test_sequence_frame.step")
MESH_CRANE = os.path.join(DATA, "test_mesh_crane.glb")

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
    """The crane's boom turns about its pin (picked like a click on the pin's round face), + turns it up; the
    luffing cylinder follows it (task 0122). The same joint as the test tour's."""
    from ..blender import tour
    return tour._boom_joint(scene)


def _tip(scene):
    from mathutils import Vector
    from ..blender import tour
    return _ob(scene, "BOOM").matrix_world @ Vector((tour.CRANE_BOOM, 0, 0))


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


@line("pc.gpu", "Graphics card used: window and renders", "0.2.221", (Q, F),
      what="The graphics card draws the window and renders – not the processor's built-in graphics (task 0296)")
def pc_gpu(ctx):
    from ..blender import gpu_choice
    from .runner import NO_GPU_TEXT, no_gpu_expected
    status, text = gpu_choice.check(no_gpu_expected())
    if status == "skip":
        raise Skipped(f"skipped: {NO_GPU_TEXT}")
    _check(status == "ok", text)
    return text


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


@line("import.shapes", "Unnamed washer, nut and O-ring sorted by their shape", "0.2.222",
      what="Parts called Part1 … Part4: the washer and the nut go to the fasteners, the O-ring to the seals")
def import_shapes(ctx):
    """Task 0302: a small STEP written now with OpenCascade (made-up parts, nothing of anyone's), imported and
    sorted with the built-in rules."""
    import math as _m

    from ..blender import build
    from ..demo_model import geom as g
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
    root = g.Asm("SHAPES")
    corner = 13.0 / _m.sqrt(3.0)
    hexagon = [(corner * _m.cos(_m.radians(30 + 60 * k)), corner * _m.sin(_m.radians(30 + 60 * k))) for k in range(6)]
    for name, shape, x in (("Part1", g.cut(g.cyl(8.0, 1.6), g.cyl(4.3, 4.0, (0, 0, -1))), 0.0),
                           ("Part2", g.cut(g.polygon_prism(hexagon, 6.8), g.cyl(4.25, 9.0, (0, 0, -1))), 30.0),
                           ("Part3", BRepPrimAPI_MakeTorus(20.0, 2.0).Shape(), 80.0),
                           ("Part4", g.box(0, 0, 0, 40, 20, 10), 140.0)):
        root.add(g.Part(name, shape, (0.6, 0.6, 0.6)), g.T(x, 0, 0))
    path = os.path.join(ctx.work, "unnamed_shapes.step")
    g.write_step(root, path)
    scene = ctx.fresh(path)
    got = {n: _ob(scene, n)[build.PROP_GROUP] for n in ("Part1", "Part2", "Part3", "Part4")}
    _check(got["Part1"] == "Fasteners default", f"the unnamed washer went to '{got['Part1']}'")
    _check(got["Part2"] == "Fasteners default", f"the unnamed nut went to '{got['Part2']}'")
    _check(got["Part3"] == "Seals & O-rings", f"the unnamed O-ring went to '{got['Part3']}'")
    _check(got["Part4"] not in ("Fasteners default", "Seals & O-rings"), "the plain block was taken for a fastener")
    return "washer, nut and O-ring found by their shape"


@line("import.materials", "CAD material names", "0.2.8", what="Material and appearance names read from STEP")
def import_materials(ctx):
    from ..blender import build
    scene = ctx.fresh(MATERIALS)
    names = {o[build.PROP_NAME]: o for o in build.iter_parts(scene)}
    _check("PLATE" in names and "SEAL RING" in names, "the test parts are missing")
    groups = {o[build.PROP_GROUP] for o in names.values()}
    _check(len(groups) >= 2, "all parts ended up in one group: the CAD material names were not used")
    return f"{len(names)} parts, {len(groups)} groups"


class _Drop:
    """What a FileHandler hands the import (task 0289): the dropped file's folder and name, the panel's choices."""

    def __init__(self, path, scene):
        self.directory, self.files = os.path.dirname(path), [type("F", (), {"name": os.path.basename(path)})()]
        self.quality, self.up_axis = scene.fresing.import_quality, scene.fresing.import_up_axis
        self.reports = []

    def execute(self, context):
        import bpy
        return bpy.ops.fresing.import_step("EXEC_DEFAULT", filepath=os.path.join(self.directory, self.files[0].name),
                                           quality=self.quality, up_axis=self.up_axis)

    def report(self, kind, text):
        self.reports.append(text)


def _copy_crane(ctx, name: str) -> str:
    folder = os.path.join(ctx.work, "dropped é")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    shutil.copy(CRANE_A, path)
    return path


@line("import.drop", "A dropped STEP file comes in as with Import STEP…", "0.2.218",
      what="A file dropped on the view: 1 Import opens, the panel's Detail and Up axis are used, the same message")
def import_drop(ctx):
    import bpy

    from ..blender import build, logic, ops_import, panels
    bpy.ops.wm.read_homefile(use_empty=True)
    from ..blender import workspaces
    scene = bpy.context.scene
    workspaces.use_all(scene)
    scene.fresing.out_folder = os.path.join(ctx.work, "renders")
    scene.fresing.import_quality, scene.fresing.import_up_axis = "draft", "Y"
    panels.OPEN.discard(ops_import.PANEL)
    res = ops_import._dropped(_Drop(_copy_crane(ctx, "dropped crane.step"), scene), bpy.context)
    _check(res == {"FINISHED"}, f"the drop's import returned {res}: {scene.fresing.last_message}")
    _check(panels.is_open(ops_import.PANEL), "1 Import did not open")
    root = build.model_roots(scene)[0]
    _check(root.get("fr_quality") == "draft", "the panel's Detail was not used")
    _check(logic.up_axis_of(root) == "Y", "the panel's Up axis was not used")
    _check(scene.fresing.last_message.startswith("Imported dropped crane.step"), scene.fresing.last_message)
    from ..core import import_cache
    for e in import_cache.entries(ops_import.cache_root()):       # leave the owner's cache as it was
        if os.path.basename(e.source) == "dropped crane.step" and os.path.dirname(e.source).endswith("dropped é"):
            import_cache.remove(e, ops_import.cache_root())
    return "1 Import open, Draft, Y up"


@line("import.again", "Imported models: Import again, Remove from cache", "0.2.218",
      what="A model in the import cache imported again without reading the file, then removed from the cache")
def import_again(ctx):
    import bpy

    from ..blender import build, ops_import
    from ..core import import_cache
    path = _copy_crane(ctx, "crane again.step")
    scene = ctx.fresh(path, read_again=True)
    root_dir = ops_import.cache_root()
    e = next((x for x in import_cache.entries(root_dir) if os.path.normcase(x.source) == os.path.normcase(path)), None)
    _check(e is not None, "the import is not in the Imported models list")
    _check(e.state == import_cache.OK, f"the stored import says '{import_cache.state_text(e)}'")
    t0 = time.time()
    res = bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id)
    ctx.metric("again", time.time() - t0, "s")
    _check(res == {"FINISHED"} and len(build.model_roots(scene)) == 2, f"Import again returned {res}")
    _check("from cache" in scene.fresing.last_message, f"not from the cache: {scene.fresing.last_message}")
    res = bpy.ops.fresing.cache_remove("EXEC_DEFAULT", entry=e.id)
    _check(res == {"FINISHED"} and not os.path.exists(e.folder), "Remove from cache left the folder")
    return f"{import_cache.size_text(e.size)} stored, again in {time.time() - t0:.1f} s"


@line("import.up_axis", "Up axis changed after the import", "0.2.218",
      what="The crane turned to Y up and back after its import: a joint and a built animation give the same motion")
def import_up_axis(ctx):
    import bpy
    from mathutils import Matrix, Vector

    from ..blender import animation, build, joints, logic
    scene = ctx.fresh(CRANE_A)
    root = build.model_roots(scene)[0]
    boom = _ob(scene, "BOOM.ASM")
    j = joints.create(scene, "ROTATE", [boom], Vector((0.1, 0.3, 0.4)), Vector((0.0, 0.0, 1.0)),
                      ref=_ob(scene, "BOOM.PIN"), name="Up axis check")
    an = scene.fresing.animations.add()
    an.name = "Up axis check"
    b = an.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j.name, 0.0, 2.0, "LINEAR"
    b.use_from, b.to_angle = True, math.radians(80)

    def tips():
        animation.bake(scene, scene.fresing.animations["Up axis check"])
        out = []
        for f in (1, 30):
            scene.frame_set(f)
            out.append(boom.matrix_world @ Vector((1.0, 0.0, 0.0)))
        scene.frame_set(1)
        return out
    before = tips()
    res = bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Y")
    _check(res == {"FINISHED"} and logic.up_axis_of(root) == "Y", f"Y up returned {res}")
    _check(not animation.has_keys(scene), "the built animation was not taken off")
    turn = Matrix.Rotation(math.radians(90), 4, "X")
    off = max((turn @ p - q).length for p, q in zip(before, tips()))
    _check(off < 1e-3, f"after Y up the boom moves {off * 1000:.1f} mm off the turned motion")
    bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=root.name, axis="Z")
    off = max((p - q).length for p, q in zip(before, tips()))
    _check(off < 1e-3, f"back to Z up the boom is {off * 1000:.1f} mm off")
    return "Y up and back, the same motion"


@line("import.mesh", "Mesh model (glTF): import, faces, a joint on a facetted ring", "0.2.99",
      what="The invented mesh crane read from a glTF file: its looks from the file, its 48-sided ring clicked for a "
           "joint that turns the turret")
def import_mesh(ctx):
    import bpy

    from ..blender import build, joints, mesh_import, tour
    t0 = time.time()
    scene = ctx.fresh(MESH_CRANE, read_again=True)
    ctx.metric("import", time.time() - t0, "s")
    root = build.model_roots(scene)[0]
    _check(mesh_import.is_mesh_model(root), "the crane did not come in as a mesh model")
    _check("Mesh crane" in root.get(mesh_import.PROP_CREDIT, ""), "the file's credit line was not read")
    parts = list(build.iter_parts(scene))
    _check(len(parts) == 10, f"expected 10 parts, got {len(parts)}")
    base = _ob(scene, "BASE")
    mat = base.material_slots[0].material
    _check(mat is not None and mat.get("fr_has_texture"), "the base did not get the file's texture")
    img = next((n.image for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"), None)
    _check(img is not None and img.packed_file is not None, "the texture is not packed into the project")
    bpy.context.view_layer.update()
    ring, o, d, desc = tour.mesh_ring_click(scene)
    _check(desc.startswith("round face"), f"the ring's wall is not a round face ({desc})")
    off = math.degrees(math.acos(min(1.0, abs(d.normalized().z))))
    dia = float(desc.split("Ø")[1].split()[0])
    _check(off < 0.5 and abs(dia - 4000.0) < 20.0, f"the ring's axis is {off:.2f}° off and Ø{dia:.1f} mm (Ø4000)")
    j = joints.create(scene, "ROTATE", [_ob(scene, "TURRET")], o, d, name="Slew", base=base)
    tip0 = _ob(scene, "BOOM").matrix_world.translation.copy()
    joints.set_value(j, math.radians(90))
    bpy.context.view_layer.update()
    tip = _ob(scene, "BOOM").matrix_world.translation
    _check(abs(tip.z - tip0.z) < 1e-4 and abs(tip.y - tip0.x) < 0.01, "the turret did not turn about the ring")
    return f"ring Ø{dia:.1f} mm, axis {off:.2f}° off vertical"


@line("import.mesh_fbx", "Mesh model (FBX) through Blender's own importer", "0.2.99",
      requires=("import.mesh",),
      what="The mesh crane saved as FBX and read again: a background Blender converts it, the app reads the result")
def import_mesh_fbx(ctx):
    import bpy

    from ..blender import build
    scene = ctx.scene_of("import.mesh")
    fbx = os.path.join(ctx.work, "mesh crane.fbx")
    bpy.ops.object.select_all(action="DESELECT")
    res = bpy.ops.export_scene.fbx(filepath=fbx, path_mode="COPY", embed_textures=True)
    _check(res == {"FINISHED"} and os.path.isfile(fbx), f"the FBX file was not written ({res})")
    t0 = time.time()
    scene = ctx.fresh(fbx, read_again=True)
    ctx.metric("import", time.time() - t0, "s")
    names = {o.get(build.PROP_NAME) for o in build.iter_parts(scene)}
    _check({"BASE", "SLEWING RING", "BOOM"} <= names, f"parts missing after the FBX round trip: {sorted(names)[:6]}")
    ring = _ob(scene, "SLEWING RING")
    dims = sorted(ring.dimensions)
    _check(abs(dims[-1] - 4.0) < 0.01, f"the ring is {dims[-1]:.3f} m across after the FBX round trip (4.0 m)")
    return f"{len(names)} parts back from FBX"


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


@line("lifting.place", "Lifting plan: place a crane from the library", "0.2.156",
      what="The built-in AT-40 sample crane placed beside the test crane (import, joints, cylinders, poses, the hoist "
           "rope as a cable); every pose of its file puts the hook block where the crane's own kinematics say; a "
           "second AT-40 gets its own names; Remove leaves nothing of it")
def lifting_place(ctx):
    import bpy

    from ..blender import lifting
    scene = ctx.fresh(CRANE_A)
    n0 = len(bpy.data.objects), len(scene.fresing.joints)
    t0 = time.time()
    c = lifting.place(bpy.context, os.path.join(DATA, "lifting", lifting.EXAMPLE_CRANE), (8.0, 0.0, 0.0), math.pi)
    t_place = time.time() - t0
    msg = lifting.check_rig(scene)
    c2 = lifting.place(bpy.context, os.path.join(DATA, "lifting", lifting.EXAMPLE_CRANE), (-8.0, 0.0, 0.0), 0.0)
    _check(c2.name == lifting.EXAMPLE_CRANE + " 2", f"the second crane is called '{c2.name}'")
    names = [j.name for j in scene.fresing.joints]
    _check(len(names) == len(set(names)), "two joints share a name")
    lifting.remove(scene, scene.fresing.lifting.cranes[1])
    lifting.remove(scene, scene.fresing.lifting.cranes[0])
    _check((len(bpy.data.objects), len(scene.fresing.joints)) == n0, "Remove left something of the cranes behind")
    ctx.metric("place AT-40", round(t_place, 1), "s")
    return msg


@line("lifting.setup", "Lifting plan: set up an own crane from its STEP", "0.2.161",
      what="The built-in KB-20's bare STEP rigged through Set up a crane's buttons by names (joints with roles, "
           "cylinders, hook, stabilisers, masses, chart, poses), Check, Save into a library; the saved file equals the "
           "built-in rig; placed again it hooks where the built-in crane hooks")
def lifting_setup(ctx):
    import bpy
    import numpy as np

    from ..blender import crane_example, lifting, lifting_rig_out
    from ..core import lifting_reach as LR
    step = os.path.join(DATA, "lifting", "KB-20", "KB-20.step")
    scene = ctx.fresh(step, quality="normal")
    t0 = time.time()
    made = crane_example.rig(scene, "KB-20", check=True, clash=False)
    t_rig = time.time() - t0
    from ..blender import setup_crane
    red = [p.text for p in setup_crane.settings(scene).problems if p.severity == "red"]
    _check(not red, "Check: " + "; ".join(red[:2]))
    lib = os.path.join(ctx.work, "lifting_setup_library")      # the check's own folder, never the user's library
    shutil.rmtree(lib, ignore_errors=True)
    os.makedirs(lib, exist_ok=True)
    path = lifting_rig_out.save(scene, lib)
    import json
    with open(path, encoding="utf-8") as fh:
        saved = json.load(fh)
    diffs = crane_example.compare("KB-20", saved, made)
    _check(not diffs, "the saved crane differs from the built-in: " + "; ".join(diffs[:3]))
    scene = ctx.fresh(CRANE_A)
    c = lifting.place(bpy.context, path, (8.0, 0.0, 0.0), 0.0)
    ref = LR.Rig(crane_example.builtin("KB-20"))
    target = ref.hook({"Main boom": 30.0, "Knuckle": -20.0, "Extension": 500.0, "Hoist": 2000.0})
    t1 = time.time()
    a = lifting.hook_to(scene, c, lifting.to_world(c, target))
    t_hook = time.time() - t1
    _check(a.ok, f"Hook to here on the own crane: {a.reason}")
    err = float(np.linalg.norm(lifting.rig_of(c).hook({**lifting.values(scene, c), **a.values}) - target))
    _check(err < 5.0, f"the hook is {err:.1f} mm off")
    ctx.metric("set up KB-20", round(t_rig, 1), "s")
    ctx.metric("hook to here (own crane)", round(t_hook * 1000.0), "ms")
    return f"{len(saved['rig']['joints'])} joints saved, the same as the built-in; hook {err:.1f} mm from the point"


@line("lifting.hook", "Lifting plan: load, CoG and Hook to here", "0.2.156",
      what="The test crane's boom made the load (1.2 t), its CoG marker worked out from the parts' volumes; the "
           "AT-40 puts its hook above it with Hook to here; the crane use shown is the chart's at that radius")
def lifting_hook(ctx):
    import bpy

    from ..blender import lifting
    scene = ctx.fresh(CRANE_A)
    t0 = time.time()
    c, ld, a = lifting.set_up_example(bpy.context)
    _check(a.ok, f"Hook to here: {a.reason}")
    t_all = time.time() - t0
    cog = lifting.check_cog(scene)
    t1 = time.time()
    a = lifting.hook_to(scene, c, lifting.above_load(scene, ld), ld)
    t_hook = time.time() - t1
    _check(a.ok, f"Hook to here again: {a.reason}")
    msg = lifting.check_example(scene)
    ctx.metric("hook to here", round(t_hook * 1000.0), "ms")
    ctx.metric("crane + load + hook", round(t_all, 1), "s")
    return f"{cog}; {msg}"


@line("lifting.hang", "Lifting plan: rig the pump skid and hang it on the hook", "0.2.192",
      what="The pump skid of test_loads.step (6 t) as the load, its four padeyes found by name, Above the load with "
           "the AT-40, Hang on the hook: its CoG under the hook, the legs' forces within 1 % of the hand formulas "
           "(C3 rule), the load follows the hook; Set down leaves it where it is")
def lifting_hang(ctx):
    import bpy

    from ..blender import build, lifting, lifting_rig, logic
    scene = ctx.fresh(LOADS)
    c = lifting.place(bpy.context, os.path.join(DATA, "lifting", lifting.EXAMPLE_CRANE), (1.0, 7.6, 0.0), math.pi)
    lifting.apply_pose(scene, c, "Set up")
    part = next(o for o in logic.descendants(build.model_roots(scene)[0]) if o.get(build.PROP_NAME) == "PUMP SKID.ASM")
    ld = lifting.new_load(scene, [part], "Pump skid")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", 6.0, "ESTIMATE"
    _check(lifting_rig.find_named(scene, ld) == 4, "the skid's four padeyes were not found by their names")
    ld.leg_length = 4.0
    ld.clearance = 3.2
    a = lifting.hook_to(scene, c, lifting.above_load(scene, ld), ld)
    _check(a.ok, f"Hook to here: {a.reason}")
    t0 = time.time()
    lifting_rig.hang(scene, c, ld)
    t_hang = time.time() - t0
    msg = lifting_rig.check_hang(scene)
    before = lifting.cog_world(ld)
    lifting_rig.set_down(scene, ld)
    import numpy as np
    _check(np.linalg.norm(lifting.cog_world(ld) - before) < 1e-6, "Set down moved the load")
    ctx.metric("hang on the hook", round(t_hang * 1000.0), "ms")
    return msg


@line("lifting.reeve", "Lifting plan: the AT-100's rope reeved in 8 falls", "0.2.192",
      what="The AT-100 placed: its hoist rope runs from the drum over 4 head and 4 block sheaves in 8 falls; the hook "
           "1 m up winds 8 m of rope (the drawn rope's length and the drum's turn); the line pull (C10) is shown")
def lifting_reeve(ctx):
    import bpy

    from ..blender import lifting, lifting_rope
    scene = ctx.fresh(LOADS)
    c = lifting.place(bpy.context, os.path.join(DATA, "lifting", "AT-100"), (1.0, 12.0, 0.0), math.pi)
    lifting.apply_pose(scene, c, "Working")
    msg = lifting_rope.check(scene, c, 1.0)
    rig = lifting.rig_of(c)
    hoist = rig.role["hoist"]
    v = lifting.values(scene, c)[hoist]
    t0 = time.time()
    for k in range(10):
        lifting.set_values(scene, c, {hoist: v + 200.0 * (k + 1)})
    t_move = (time.time() - t0) / 10
    lifting.set_values(scene, c, {hoist: v})
    ro = lifting.readout(scene, c)
    lp = lifting.line_pull(scene, c, ro.gross if not isinstance(ro, str) else 0.0)
    ctx.metric("hook move, AT-100 reeved", round(t_move * 1000.0, 1), "ms")
    return msg + f"; {lp.message}"


@line("lifting.make", "Lifting plan: make a crane from numbers", "0.2.159",
      what="Make a crane…: the AT-100's numbers with 5 boom sections and a 50 m boom made in the background into a "
           "library folder (model, equipment file with a SAMPLE chart, picture), placed beside the test crane, every "
           "pose where its own kinematics say, Hook to here above the test crane's boom; a refused set of numbers "
           "names its rule")
def lifting_make(ctx):
    import bpy

    from ..blender import lifting, ops_lifting_make
    from ..core import lifting_library as LL
    from ..lifting_model import params
    scene = ctx.fresh(CRANE_A)
    bad = dict(ops_lifting_make.tour_spec()["values"], Lmax=60000.0)
    _check([p.rule for p in params.validate("AT", bad)] == ["sections_overlap"],
           "5 sections at 60 m were not refused for their overlap")
    lib = os.path.join(ctx.work, "Lifting equipment")
    t0 = time.time()
    job = ops_lifting_make.make_now(ops_lifting_make.tour_spec(), lib, replace=True)
    t_make = time.time() - t0
    it = LL.read_item(job.item_path)
    _check(it.ok and it.sample and it.model and it.picture, "the made crane is not a complete SAMPLE item")
    c = lifting.place(bpy.context, job.item_path, (9.0, 0.0, 0.0), math.pi)
    lifting.apply_pose(scene, c, "Set up")
    msg = lifting.check_rig(scene)
    from ..blender import build, logic
    roots = [r for r in build.model_roots(scene) if lifting.crane_of_root(scene, r) is None]
    part = next(o for o in logic.descendants(roots[0]) if o.get(build.PROP_NAME) == lifting.EXAMPLE_LOAD)
    ld = lifting.new_load(scene, [part], "Test crane boom")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", lifting.EXAMPLE_MASS, "DRAWING"
    a = lifting.hook_to(scene, c, lifting.above_load(scene, ld), ld)
    _check(a.ok, f"Hook to here: {a.reason}")
    ctx.metric("make AT-100 5 sections", round(t_make, 1), "s")
    return f"made in {t_make:.1f} s; {msg}; {lifting.check_example(scene)}"


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


@line("looks.welds", "Welds: two picked faces give a bead", "0.2.226",
      what="The base plate's top and one side of the fin picked as in Inventor: one fillet 200 mm long; then every joint "
           "of the test weldment welded with another look (painted, MAG, rusty, stainless, pickled, aluminium, ground); "
           "rendered small")
def looks_welds(ctx):
    import time

    from ..blender import welds
    scene = ctx.fresh(WELDMENT)
    t0 = time.perf_counter()
    it = welds.pick_test_weld(scene)
    ms = (time.perf_counter() - t0) * 1000.0
    seams = [s.length for s in it.seams if s.enabled]
    _check(len(seams) == 1 and abs(seams[0] - 0.2) < 0.002, f"the picked faces gave seams of {seams} m, not one of 0.2 m")
    _check(abs(float(it.get("fr_length", 0.0)) - 0.2) < 0.002, "the bead is not 200 mm long")
    _check(len(welds.objects_of(it)) == 2, "the weld has no bead or no heat zone")
    welds.remove(scene, it)
    welds.set_up_test_model(scene)
    st = welds.stats(scene)
    _check(st["welds"] == len(welds.TEST_WELDS) and st["lost"] == 0, f"{st['welds']} welds, {st['lost']} lost")
    ctx.metric("weld_pick_ms", round(ms), "ms")
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "welds", "Welds (processor, draft)")
    return f"200 mm fillet from two picked faces in {ms:.0f} ms; {st['welds']} welds, {st['metres']:.2f} m; " \
           f"render {info['seconds']} s"


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


@line("looks.marine", "Marine looks: growth at the waterline, streaks, concrete", "0.2.94",
      what="A yellow pile 1.2 m across and 8 m tall standing 4 m deep in water (marine paint with growth), a grey wall "
           "with run-down streaks and a concrete block, rendered small (processor, draft): judge the dark "
           "green-brown growth with its ragged top just below the waterline, the greenish splash zone with rust "
           "streaks above it, clean yellow higher up")
def looks_marine(ctx):
    from ..blender import marine_looks, render, tour
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    water = tour.MARINE_WATER
    made = tour.marine_demo(scene, water)
    _check(marine_looks.nodes_of(made["paint_marine_growth"]), "the growth look has no marine nodes")
    lo, hi = marine_looks.growth_band()
    _check(marine_looks.growth(lo - 0.01) == 1.0 and marine_looks.growth(hi + 0.01) == 0.0,
           "the growth band is not below the waterline")
    _check(marine_looks.waterline(scene) == water, "the material does not read the scene's waterline")
    tour.marine_camera(scene, water)
    _small_output(s)
    s.use_gpu = False
    path = os.path.join(ctx.work, "marine_looks.png")
    info = render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "marine_looks", "Marine looks (processor, draft)", model_check=False)
    return f"growth band {lo:+.2f} … {hi:+.2f} m round the waterline; render {info['seconds']} s"


@line("looks.served_cable", "Served cable look: yarn and marker bands", "0.2.116",
      what="The test carousel's power cable with Look = Served cable (yarn): black yarn served almost straight round "
           "it and two yellow painted marker lines winding round it as a spiral, on the cable and on its coil; built, the bands run with the cable. "
           "A close-up is rendered small (processor, draft): judge the fine grooves, the darker and lighter strands, "
           "the ragged band edges")
def looks_served_cable(ctx):
    from ..blender import animation, render, tour
    scene = ctx.fresh(SPOOL)
    s = scene.fresing
    made = tour.served_demo(scene)
    tour.served_camera(scene)
    a = s.animations[made["animation"]]
    info = animation.bake(scene, a)
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_served(scene)
    scene.frame_set(scene.frame_start)
    _small_output(s)
    s.use_gpu = False
    path = os.path.join(ctx.work, "served_cable.png")
    t0 = time.time()
    render.render_still(scene, s, "draft", filepath=path)
    ctx.metric("render the served cable close-up", time.time() - t0, "s")
    ctx.picture(path, "served_cable", "The served cable leaving the carousel: yarn and yellow bands (processor, draft)")
    return note


@line("looks.cutaway", "Slice: a slice through the pedestal", "0.2.64",
      what="A plane cut through the crane's pedestal and boom (hatched red cut faces, the pin inside), slid in by a "
           "Move joint step; the end frame is rendered small (processor, draft), and its time compared with the "
           "same frame without the cut")
def looks_cutaway(ctx):
    import numpy as np
    from mathutils import Vector

    from ..blender import animation, cameras, render, tour
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    ped = _ob(scene, "PEDESTAL")
    centre = sum((ped.matrix_world @ Vector(c) for c in ped.bound_box), Vector()) / 8.0
    pts = np.array([tuple(centre + Vector((0.5 + dx, dy, 0.25 + dz))) for dx in (-1.35, 1.35)
                    for dy in (-1.35, 1.35) for dz in (-1.35, 1.35)])
    scene.camera = cameras.add_camera(scene, "ISO", 50.0, "Cut view", points=pts)
    a = s.animations.add()
    a.name, a.tail, a.fps = tour.CUT_ANIM, 0.0, "25"
    t0 = time.time()
    cut = tour.cutaway(scene, a)
    ctx.metric("add cut", time.time() - t0, "s")
    info = animation.bake(scene, a)
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_cutaway(scene)
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(scene.frame_end)
    times = {}
    for key, on in (("warm", True), ("plain", False), ("cut", True)):     # the first render loads the scene
        cut.enabled = on
        path = os.path.join(ctx.work, f"cutaway_{key}.png")
        t1 = time.time()
        render.render_still(scene, s, "draft", filepath=path)
        times[key] = time.time() - t1
    ctx.picture(path, "cutaway", "The pedestal and boom cut open, red hatched cut faces (processor, draft)")
    ctx.metric("render with cut", times["cut"], "s")
    ratio = times["cut"] / max(times["plain"], 1e-3)
    return f"{note}; frame {times['cut']:.1f} s with the cut vs {times['plain']:.1f} s without ({ratio:.2f}x)"


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


@line("panel.workspaces", "Workspaces: families hidden and shown, an own workspace, the Client view's lock", "0.2.152",
      what="A workspace hides panels and keeps the work; an own workspace is one file in a folder with a space and "
           "an accent; the Client view locks every part and Full access unlocks them exactly")
def panel_workspaces(ctx):
    import shutil
    import tempfile

    import bpy

    from ..blender import lock, panels, workspaces
    from ..core import workspaces as W
    scene = ctx.fresh(MACHINE)
    s = scene.fresing
    folder = os.path.join(tempfile.mkdtemp(prefix="fr_pc_"), "Werkplek één", W.FOLDER)
    old_env = os.environ.get(workspaces.ENV_FOLDER)
    os.environ[workspaces.ENV_FOLDER] = folder
    workspaces.forget_scan()
    try:
        # a workspace hides panels and keeps the work
        before = (len(scene.objects), len(s.groups), s.cnc.x_joint)
        s.cnc.x_joint = "X"
        workspaces.switch(scene, "Offshore & cable laying")
        _check(workspaces.panel_hidden(scene, "FRESING_PT_cnc") and not workspaces.panel_hidden(scene, "FRESING_PT_cables"),
               "the workspace Offshore & cable laying does not hide the CNC machine and show Cables and paths")
        _check(not bpy.types.FRESING_PT_cnc.poll(bpy.context), "a hidden panel is still drawn")
        _check(workspaces.hidden_in_use(scene) == ["cnc"], "the project's CNC machine is not seen as in use")
        _check("a CNC machine" in W.hide_warning("cnc", workspaces.in_use(scene)["cnc"]),
               "the question before hiding does not name what is set up")
        _check(workspaces.show_used(scene) == ["cnc"] and workspaces.family_on(scene, "cnc"),
               "Show what the project uses did not bring the CNC machine back")
        workspaces.set_tick(scene, "web", False)
        hidden = len(workspaces._state(scene)[0])
        # an own workspace is one file
        path = workspaces.save_own(scene, "PC check – eigen")
        _check(os.path.isfile(path) and os.listdir(folder) == [os.path.basename(path)],
               f"the own workspace was not saved as one file in {folder}")
        workspaces.switch(scene, W.DEFAULT)
        _check(not workspaces.panel_hidden(scene, "FRESING_PT_web3d"), "All functions does not show everything")
        workspaces.switch(scene, "PC check – eigen")
        _check(workspaces.panel_hidden(scene, "FRESING_PT_web3d") and workspaces.family_on(scene, "cnc")
               and len(workspaces._state(scene)[0]) == hidden, "the own workspace does not show what was saved")
        workspaces.delete_own(scene, "PC check – eigen")
        _check(os.listdir(folder) == [] and workspaces.panel_hidden(scene, "FRESING_PT_web3d"),
               "deleting the own workspace's file did not leave the project its copy")
        s.cnc.x_joint = before[2]
        # the Client view's lock, and back
        was = {ob.name: (ob.hide_select, tuple(ob.lock_location), tuple(ob.lock_rotation), tuple(ob.lock_scale))
               for ob in scene.objects}
        workspaces.switch(scene, "Client view")
        _check(lock.ON[0] and all(ob.hide_select and all(ob.lock_location) for ob in scene.objects),
               "the Client view did not lock every part")
        _check(bpy.ops.fresing.group_add.poll() is False and bpy.ops.fresing.light_look.poll(),
               "the Client view does not refuse editing buttons (or refuses the light looks too)")
        # task 0227: Ctrl+Z never leaves the Client view, a part freed or selected while locked is taken back
        part = next((ob for ob in scene.objects if ob.type == "MESH"), None)
        workspaces._before_undo()                     # what an undo to before the pick leaves, as the handlers see it
        lock._unlock_all()
        s.ws_name = W.DEFAULT
        if part is not None:
            part.select_set(True)
        workspaces._after_undo()
        _check(workspaces.name_of(scene) == "Client view" and lock.ON[0] and not bpy.context.selected_objects
               and all(ob.hide_select for ob in scene.objects),
               "Ctrl+Z took the project out of the Client view (or left a part selected)")
        if part is not None:
            part.hide_select = False
            part.select_set(True)
            lock._after_change()
            _check(part.hide_select and not bpy.context.selected_objects,
                   "a part made clickable and selected in the Client view was not taken back")
        workspaces.switch(scene, "Full access")
        now = {ob.name: (ob.hide_select, tuple(ob.lock_location), tuple(ob.lock_rotation), tuple(ob.lock_scale))
               for ob in scene.objects}
        _check(not lock.ON[0] and lock.marked() == 0 and now == was,
               "Full access did not put every part back as it was before the lock")
        _check((len(scene.objects), len(s.groups)) == before[:2], "hiding or locking changed the project")
        _check(not any(panels.is_open(sec) for sec in panels.SECTIONS) or bool(panels.OPEN),
               "the side panel's sections have no open / folded state")
        return f"{hidden} panels hidden and back, {len(was)} objects locked and unlocked"
    finally:
        try:
            workspaces.switch(scene, W.DEFAULT)
        except Exception:  # noqa: BLE001 - the other lines must find the app as it was
            lock.apply(scene, False)
        if old_env is None:
            os.environ.pop(workspaces.ENV_FOLDER, None)
        else:
            os.environ[workspaces.ENV_FOLDER] = old_env
        workspaces.forget_scan()
        shutil.rmtree(os.path.dirname(os.path.dirname(folder)), ignore_errors=True)


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
    _check(moved > 2.5 and back < 1e-4, f"the boom did not turn as expected (tip moved {moved * 1000:.0f} mm, "
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
    joints.set_value(jt, 1.0)
    _update()
    from ..blender import tour
    pivot = Vector(tour.CRANE_PIVOT)
    want = pivot + Matrix.Rotation(sign * math.radians(30), 3, "Y") @ (cad - pivot + Vector((1.0, 0, 0)))
    err = (trolley.matrix_world.translation - want).length
    _check(err < 1e-3, f"the trolley is {err * 1000:.1f} mm off where boom + slide put it")
    return "boom 30° + trolley 1000 mm"


@line("joints.show", "Joints: a clicked joint shows what it moves", "0.2.224",
      what="Clicking the boom's joint in 4 Motion > Joints lights up the boom, the trolley riding on it lighter")
def joints_show(ctx):
    from mathutils import Vector

    from ..blender import joint_show, joints
    scene = ctx.fresh(CRANE_A)
    jb = _boom_joint(scene)
    boom = jb.name
    trolley_ob = _ob(scene, "TROLLEY.ASM")
    joints.create(scene, "SLIDE", [trolley_ob], trolley_ob.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=_ob(scene, "BOOM.ASM"), name="Trolley")
    s = scene.fresing
    names = [j.name for j in s.joints]
    s.joints_index = names.index(boom)                  # as a click on the list row
    shown = joint_show.active()
    joint_show.clear()
    trolley = {o.name for o in _ob(scene, "TROLLEY.ASM").children_recursive if o.type == "MESH"}
    _check(shown["name"] == boom and shown["main"], f"nothing shown for '{boom}': {shown}")
    _check(trolley and trolley <= set(shown["riders"]) and not trolley & set(shown["main"]),
           "the trolley riding on the boom is not shown in the lighter shade")
    _check(not [o for o in scene.objects if o.select_get()], "showing a joint selected parts")
    return f"{len(shown['main'])} parts lit, {len(shown['riders'])} riding on it"


@line("joints.cylinder", "Cylinder: follows the arm, the stroke drives it", "0.2.25",
      what="The luffer's arm turns: the cylinder's rod eye stays on its pin; a set stroke turns the arm to the "
           "angle of the triangle pivot – barrel pin – rod pin")
def joints_cylinder(ctx):
    from mathutils import Matrix, Vector

    from ..blender import build, cylinders, joints
    scene = ctx.fresh(LUFFER)

    def at_y(name, y):              # the cylinder at y = 240 mm (there are two side by side)
        hits = [o for o in scene.objects if o.get(build.PROP_NAME) == name]
        _check(bool(hits), f"the test model has no part '{name}'")
        return min(hits, key=lambda o: abs(o.matrix_world.translation.y - y))

    along_y = Vector((0, 1, 0))
    pivot, barrel_pin, rod_pin = Vector((0.3, 0.24, 1.8)), Vector((1.5, 0.24, 0.45)), Vector((2.4, 0.24, 1.35))
    arm = joints.create(scene, "ROTATE", [_ob(scene, "ARM.ASM")], Vector((0.3, 0.6, 1.8)), along_y, name="Luff")
    c, _notes = cylinders.create(scene, [at_y("CYL.BARREL", 0.24)], [at_y("CYL.ROD", 0.24)],
                                 (barrel_pin, along_y, _ob(scene, "BASE.PIN")),
                                 (rod_pin, along_y, _ob(scene, "ARM.ROD.PIN")))
    _update()
    eye = at_y("ROD.EYE", 0.24)
    eye_centre = eye.matrix_world.inverted() @ rod_pin
    joints.set_value(arm, math.radians(20))
    _update()
    want = pivot + Matrix.Rotation(math.radians(20), 3, "Y") @ (rod_pin - pivot)
    err = (eye.matrix_world @ eye_centre - want).length
    _check(err < 1e-4, f"the rod's eye is {err * 1000:.2f} mm off its pin with the arm at 20°")
    cylinders.set_mode(scene, c, "DRIVE")
    cylinders.set_stroke(scene, c, 0.3)
    a, b = (barrel_pin - pivot).length, (rod_pin - pivot).length
    length0, length = (rod_pin - barrel_pin).length, c.closed_length + 0.3
    expected = (math.acos((a * a + b * b - length0 * length0) / (2 * a * b))
                - math.acos((a * a + b * b - length * length) / (2 * a * b)))
    got = joints.get_value(arm)
    _check(abs(got - expected) < 1e-4, f"stroke 300 mm turned the arm to {math.degrees(got):.2f}°, "
                                       f"not {math.degrees(expected):.2f}°")
    return f"eye on its pin to {err * 1000:.3f} mm; stroke 300 mm → arm {math.degrees(got):.2f}°"


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


@line("motion.flex", "Hoses, a cable and drag chains follow the motion", "0.2.78",
      what="A luffing arm with three hydraulic hoses and a hanging cable, a gantry with a drag chain on each axis: "
           "posed and in a built animation the hose ends stay on their fittings, the hoses keep their length, the "
           "chains' links keep their length and the moving ends stay on their parts; the same frame always gives "
           "the same shape")
def motion_flex(ctx):
    import numpy as np

    from ..blender import animation, cameras, flex, joints, render, tour
    scene = ctx.fresh(FLEX_HOSES)
    s = scene.fresing
    t0 = time.time()
    made = flex.set_up_test_hoses(scene)
    ctx.metric("add 4 hoses", time.time() - t0, "s")
    _check(len(made["items"]) == 4, f"only {len(made['items'])} of the 4 hoses were made")
    # posed by hand (no animation): the hoses follow at once
    joints.set_value(joints.find(scene, "Luff"), math.radians(15.0))
    joints.set_value(joints.find(scene, "Slide"), 0.3)
    _update()
    flex.refresh(scene)
    end, stretch, _chord = tour.flex_errors(scene)
    _check(end < 1e-4, f"posed by hand, a hose end is {end * 1000:.2f} mm off its fitting")
    _check(stretch < 0.005, f"posed by hand, a hose changed its length by {stretch * 100:.2f} %")
    joints.set_value(joints.find(scene, "Luff"), 0.0)
    joints.set_value(joints.find(scene, "Slide"), 0.0)
    _update()
    # a built animation: every frame's shape is worked out at Build
    scene.camera = cameras.add_camera(scene, "ISO", 50.0, "Hoses view")
    a = s.animations.add()
    a.name, a.tail, a.fps = tour.HOSES_ANIM, 0.0, "25"
    tour.hoses_motion(a)
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with hoses", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_hoses(scene)
    item = flex.find(scene, made["items"][0])
    shapes = []
    for before in (10, 90):                       # the same frame after another frame: the same shape
        scene.frame_set(before)
        scene.frame_set(50)
        _update()
        shapes.append(np.array(flex.shape_now(scene, item)))
    _check(float(np.abs(shapes[0] - shapes[1]).max()) == 0.0, "frame 50 looks different after frame 10 than after "
                                                              "frame 90")
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(50)
    path = os.path.join(ctx.work, "flex_hoses.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "flex_hoses", "Arm up: three hoses and the cable bent along (processor, draft)")

    scene = ctx.fresh(FLEX_CHAINS)
    s = scene.fresing                             # (the first project is closed: its settings are gone)
    made = flex.set_up_test_chains(scene)
    _check(len(made["items"]) == 3, f"only {len(made['items'])} of the 3 drag chains were made")
    worst_end = worst_link = 0.0
    for x, y, z in ((0.14, 0.0, 0.0), (-0.14, 0.09, 0.05), (0.0, -0.09, -0.04)):
        for name, v in (("X", x), ("Y", y), ("Z", z)):
            joints.set_value(joints.find(scene, name), v)
        _update()
        flex.refresh(scene)
        end, _stretch, chord = tour.flex_errors(scene)
        worst_end, worst_link = max(worst_end, end), max(worst_link, chord)
        for it in s.flex:
            _check(not it.problem, f"'{it.name}': {it.problem}")
    _check(worst_end < 1e-5, f"a chain's moving end is {worst_end * 1000:.3f} mm off its part")
    _check(worst_link < 1e-5, f"a chain link is {worst_link * 1000:.3f} mm off its link length")
    return f"{note}; 3 chains: moving ends to {worst_end * 1000:.3f} mm"


@line("motion.drawn", "Hoses, a drag chain and a cable route drawn by clicking", "0.2.180",
      what="Task 0240: on the hoses model a hose is drawn by four clicks (two fittings, two clips) in place of a CAD "
           "hose, which is hidden; posed at three luff angles its ends and clips stay on their parts and it keeps its "
           "length. On the gantry a drag chain is drawn between the X chain's two brackets: its links stay one pitch "
           "apart and its moving end on its bracket as X travels. On the cable model a route is drawn by clicking the "
           "drum, two sheaves and the chute: it reads the same six contacts as the CAD rope and its sheaves turn with it")
def motion_drawn(ctx):
    import numpy as np

    from ..blender import build, drawn, flex, joints, paths, tour
    scene = ctx.fresh(FLEX_HOSES)
    flex.set_up_test_hoses(scene)
    root = build.model_roots(scene)[0]
    t0 = time.time()
    name = tour.drawn_hose_setup(scene, root)
    ctx.metric("draw a hose through two clips", time.time() - t0, "s")
    it = flex.find(scene, name)
    _check(it is not None and len(it.clips) == 2, "the drawn hose or its clips are missing")
    cad = next(o for o in scene.objects if o.get(build.PROP_NAME) == "HYDRAULIC HOSE ARM")
    _check(cad.get(build.PROP_EXCLUDED) and cad.hide_render, "the CAD hose it replaces still shows")
    worst = 0.0
    for deg in (0.0, 15.0, -12.0):
        joints.set_value(joints.find(scene, "Luff"), math.radians(deg))
        _update()
        flex.refresh(scene)
        it = flex.find(scene, name)
        line = flex.shape_now(scene, it)
        stops = [drawn.world_spot(it.a_part, it.a_point, it.a_dir)[0]]
        stops += [drawn.world_spot(c.part, c.point, c.dir)[0] for c in it.clips]
        stops.append(drawn.world_spot(it.b_part, it.b_point, it.b_dir)[0])
        worst = max([worst] + [float(np.linalg.norm(line - p, axis=1).min()) for p in stops])
        _check(not it.problem, f"at {deg:.0f}°: {it.problem}")
    _check(worst < 1e-4, f"the drawn hose is {worst * 1000:.3f} mm off an end or a clip")

    scene = ctx.fresh(FLEX_CHAINS)
    flex.set_up_test_chains(scene)
    name = tour.drawn_chain_setup(scene, build.model_roots(scene)[0])
    chord = end = 0.0
    for x in (0.14, -0.14, 0.0):
        joints.set_value(joints.find(scene, "X"), x)
        _update()
        flex.refresh(scene)
        it = flex.find(scene, name)
        pins = flex.pins_now(scene, it)
        chord = max(chord, float(np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max()))
        end = max(end, float(np.linalg.norm(pins[-1] - drawn.world_spot(it.b_part, it.b_point, (1, 0, 0))[0])))
        _check(not it.problem, f"X at {x * 1000:.0f} mm: {it.problem}")
    _check(chord < 1e-5 and end < 1e-4, f"the drawn chain: links {chord * 1000:.4f} mm off, end {end * 1000:.3f} mm off")

    scene = ctx.fresh(PATHS)
    name = tour.drawn_cable_setup(scene, build.model_roots(scene)[0])
    it = paths.find(scene, name)
    kinds = [c.kind for c in it.contacts]
    _check(kinds == ["SHEAVE", "SHEAVE", "SHEAVE", "ROLLER", "ROLLER", "CHUTE"], f"the drawn route reads {kinds}")
    lead = joints.find(scene, it.joint)
    turning = [joints.find(scene, c.joint) for c in it.contacts if c.kind in paths.TURNING and c.joint]
    _check(len(turning) == 5 and all(j is not None and j.follows == lead.name for j in turning),
           "not every sheave and roller turns with the drawn cable")
    return (f"hose through 2 clips on its parts to {worst * 1000:.3f} mm; chain links to {chord * 1000:.4f} mm; "
            "cable route: 6 contacts, 5 turning")


@line("motion.flex_avoid", "A hose avoids other parts; a route shaped by a via point", "0.2.225",
      what="Task 0298: on the avoid model (a block in a Ø20 hose's way, a lift that goes 400 mm down) the hose with "
           "'Avoid other parts' on stays out of the block at five lift heights (without it, it sags 85 mm into it), "
           "and in a built animation at every frame. Then a via point is set beside the block: the hose runs through "
           "it and it rides with the lift; the clash check with 'Check hoses that avoid parts' lists nothing for it")
def motion_flex_avoid(ctx):
    import numpy as np

    from ..blender import animation, build, clash, flex, flex_avoid, flex_route, joints, tour
    from ..core import flex as fcore
    scene = ctx.fresh(FLEX_AVOID)
    made = flex.set_up_test_avoid(scene, avoid=False)
    it = flex.find(scene, made["items"][0])
    block = next(o for o in scene.objects if o.get(build.PROP_NAME) == "BLOCK")
    body = flex_avoid.body_of(block)

    def gap():
        inv = np.linalg.inv(flex_avoid._rigid(np.array(block.matrix_world)))
        pts = fcore.resample(flex.shape_now(scene, it), 400)
        return float(body.distance(pts @ inv[:3, :3].T + inv[:3, 3])[0].min()) - 0.5 * it.diameter

    def lift(v):
        joints.set_value(joints.find(scene, "Lift"), v)
        _update()
        flex.refresh(scene)
    lift(-0.4)
    off = gap()
    _check(off < -0.05, f"without 'Avoid other parts' the hose should sag into the block (it is {off * 1000:.0f} mm off)")
    it.avoid = True
    t0 = time.time()
    worst = 1.0
    for v in (-0.4, -0.3, -0.15, 0.0, 0.1):
        lift(v)
        worst = min(worst, gap())
    ctx.metric("a hose that avoids a block, five lift heights", time.time() - t0, "s")
    _check(worst > -0.0025, f"with 'Avoid other parts' the hose still goes {-worst * 1000:.1f} mm into the block")
    lift(0.0)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = "Lift", 0.0, "25"
    tour.avoid_motion(a)
    t0 = time.time()
    r = animation.bake(scene, a)
    ctx.metric("build the avoid animation", time.time() - t0, "s")
    _check(not r["warnings"], "; ".join(r["warnings"]))
    built = 1.0
    for f in range(scene.frame_start, scene.frame_end + 1, 5):
        scene.frame_set(f)
        built = min(built, gap())
    _check(built > -0.0025, f"in the built animation the hose goes {-built * 1000:.1f} mm into the block")
    scene.fresing.clash.hoses = True
    run = clash.check(scene, store=False)
    _check(not [x for x in run.rows if it.part.name in x.names], "the clash check lists the hose that avoids parts")
    tour._route_on(scene)
    it = flex.find(scene, made["items"][0])
    _check(flex_route.count(it) == 1, "the via point was not set")
    miss = 0.0
    for f in range(scene.frame_start, scene.frame_end + 1, 10):
        scene.frame_set(f)
        via = flex_route.stops_now(it)[1][0]
        miss = max(miss, float(np.linalg.norm(flex.shape_now(scene, it) - via, axis=1).min()))
    _check(miss < 1e-4, f"the hose misses its via point by {miss * 1000:.2f} mm")
    return (f"off: {-off * 1000:.0f} mm in the block; on: at most {max(-worst, -built, 0.0) * 1000:.2f} mm (live and "
            f"built); through its via point to {miss * 1000:.3f} mm")


@line("motion.flex_kinds", "Hose and cable kinds, chain types and standard sizes", "0.2.182",
      what="Task 0243: on the hoses model six hoses are drawn and each gets a kind – hydraulic, steel-braided, "
           "pneumatic, protective sleeve, machine cable, power cable: a size pick sets its diameter and smallest bend, "
           "the tube is drawn that thick, each kind has its own look (one shared material per kind and colour), a "
           "number typed by hand makes the size Custom. On the gantry a drawn drag chain is open, closed, half-open and "
           "steel in turn: links one pitch apart, its moving end on its bracket as X travels. A small processor render "
           "of the six hoses")
def motion_flex_kinds(ctx):
    import numpy as np

    from ..blender import build, cameras, drawn, flex, joints, render, tour
    from ..core import flex_kinds
    scene = ctx.fresh(FLEX_HOSES)
    flex.set_up_test_hoses(scene)
    root = build.model_roots(scene)[0]
    t0 = time.time()
    names = tour.kind_row_setup(scene, root)
    ctx.metric("six hoses drawn and given a kind", time.time() - t0, "s")
    looks = set()
    worst = 0.0
    for name, kid in zip(names, tour.KIND_ROW):
        it = flex.find(scene, name)
        sz = flex_kinds.size(kid, it.size_id)
        _check(sz is not None and abs(it.diameter - sz.od) < 1e-6 and abs(it.min_radius - sz.bend) < 1e-6,
               f"'{name}' does not have its standard size's numbers")
        worst = max(worst, abs(2.0 * tour._tube_radius(scene, it) - sz.od))
        looks.add(it.part.material_slots[0].material.name)
        _check(not it.problem, f"'{name}': {it.problem}")
    _check(worst < 1e-4, f"a hose is drawn {worst * 1000:.2f} mm off its size's diameter")
    _check(len(looks) == len(names), "two kinds share one look")
    it = flex.find(scene, names[2])
    it.diameter = it.diameter + 0.001
    _check(it.size == "CUSTOM", "a diameter typed by hand did not make the size Custom")
    it.size = "OD8"
    _check(abs(it.diameter - 0.008) < 1e-6, "the size 8 mm did not set the diameter")
    m = root.matrix_world
    from mathutils import Vector
    cam = cameras.add_camera(scene, "ISO", 32.0, name="PC check kinds")
    at, target = m @ Vector((2.15, 2.23, 1.05)), m @ Vector((2.15, 1.17, 0.3))
    from mathutils import Matrix
    cam.matrix_world = Matrix.Translation(at) @ (target - at).normalized().to_track_quat("-Z", "Y").to_matrix().to_4x4()
    scene.camera = cam
    s = scene.fresing
    _small_output(s)
    s.use_gpu = False
    path = os.path.join(ctx.work, "flex_kinds.png")
    info = render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "flex_kinds", "Hose and cable kinds (processor, draft)", model_check=False)

    scene = ctx.fresh(FLEX_CHAINS)
    flex.set_up_test_chains(scene)
    name = tour.drawn_chain_setup(scene, build.model_roots(scene)[0])
    chord = end = 0.0
    for kid in ("OPEN", "CLOSED", "HALF", "STEEL"):
        it = flex.find(scene, name)
        it.chain_kind = kid
        _check(flex_kinds.size(kid, it.size_id) is not None, f"the {kid.lower()} chain got no standard size")
        for x in (0.14, -0.14):
            joints.set_value(joints.find(scene, "X"), x)
            _update()
            flex.refresh(scene)
            it = flex.find(scene, name)
            pins = flex.pins_now(scene, it)
            chord = max(chord, float(np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max()))
            end = max(end, float(np.linalg.norm(pins[-1] - drawn.world_spot(it.b_part, it.b_point, (1, 0, 0))[0])))
            _check(not it.problem, f"{kid.lower()} chain, X at {x * 1000:.0f} mm: {it.problem}")
    _check(chord < 1e-5 and end < 1e-4, f"chain types: links {chord * 1000:.4f} mm off, end {end * 1000:.3f} mm off")
    return (f"6 kinds, Ø to {worst * 1000:.3f} mm, {len(looks)} looks; 4 chain types: links to {chord * 1000:.4f} mm; "
            f"render {info['seconds']} s")


@line("motion.paths", "A cable runs over sheaves, rollers and a chute", "0.2.80",
      what="A winch drum, an A-frame with two grooved sheaves, a V-roller cradle and a chute: the wire rope is read "
           "from its CAD solid and lies in the grooves; a Run motor step moves it at 10 m/min and the drum, the "
           "sheaves and the rollers turn exactly with it; the rope follows the luffing A-frame, and its strands "
           "have moved by the length that ran")
def motion_paths(ctx):
    from ..blender import animation, cable_looks, cameras, joints, paths, render, tour
    scene = ctx.fresh(PATHS)
    s = scene.fresing
    t0 = time.time()
    made = paths.set_up_test_model(scene)
    ctx.metric("read the cable", time.time() - t0, "s")
    item = paths.find(scene, made["cable"])
    kinds = [c.kind for c in item.contacts]
    _check(kinds == ["SHEAVE", "SHEAVE", "SHEAVE", "ROLLER", "ROLLER", "CHUTE"],
           f"the rope should touch a drum, 2 sheaves, 2 rollers and a chute; found: {', '.join(kinds) or 'nothing'}")
    _check(abs(item.diameter - 0.024) < 0.0005, f"the rope's diameter was read as {item.diameter * 1000:.1f} mm (24)")
    # posed by hand (no animation): the rope follows the A-frame at once
    before = paths.shape_now(scene, item).copy()
    joints.set_value(joints.find(scene, "Luff"), math.radians(10.0))
    _update()
    paths.refresh(scene)
    item = paths.find(scene, made["cable"])
    _check(paths.status(scene, item)[1] == "OK", f"posed by hand, the cable says: {paths.status(scene, item)[0]}")
    after = paths.shape_now(scene, item)
    _check(after.shape != before.shape or float(abs(after - before).max()) > 0.02,
           "posed by hand, the rope did not follow the A-frame")
    joints.set_value(joints.find(scene, "Luff"), 0.0)
    _update()
    paths.refresh(scene)
    # a built animation: 6 s at 10 m/min while the A-frame luffs
    scene.camera = cameras.add_camera(scene, "ISO", 50.0, "Cable view")
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with the cable", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_cables(scene)
    scene.frame_set(scene.frame_end)
    _update()
    item = paths.find(scene, made["cable"])
    ran = joints.get_value(joints.find(scene, item.joint))
    shown = float(item.part[cable_looks.PAY]) - cable_looks.PAY_BIAS
    _check(abs(ran - 1.0) < 0.01, f"{ran:.3f} m of rope ran in 6 s at 10 m/min (1.000 m expected)")
    _check(abs(shown - ran) < 1e-3, f"the rope's strands are {abs(shown - ran) * 1000:.1f} mm off the rope itself")
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(60)
    path = os.path.join(ctx.work, "cable_paths.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "cable_paths", "The rope over drum, sheaves, V rollers and chute, the A-frame leaning forward "
                                     "(processor, draft)")
    return note


@line("motion.spool", "A drum and a carousel spool their cable layer by layer", "0.2.85",
      what="A winch drum with a level wind and a carousel with a slewing arm: each cable comes off its spool layer by "
           "layer; the drum and the carousel turn by table with the cable speed, the level wind and the arm follow "
           "the layer, and the cable leaves its spool on the circle of its layer. Every layer is cable (task 0174): "
           "the drum is wound fully in and out again, the carousel emptied and filled, one cable from the anchor to "
           "where it leaves")
def motion_spool(ctx):
    from ..blender import animation, cameras, render, spool, tour
    scene = ctx.fresh(SPOOL)
    s = scene.fresing
    t0 = time.time()
    made = spool.set_up_test_model(scene)
    spool.add_full_range_steps(scene, made["animation"])      # task 0174: a full spool emptied and filled
    ctx.metric("set up the drum and the carousel", time.time() - t0, "s")
    for name in made["spools"]:
        sp = spool.find(scene, name)
        _check(sp is not None and not sp.problem, f"'{name}': {sp.problem if sp is not None else 'missing'}")
    scene.camera = cameras.add_camera(scene, "ISO", 35.0, "Spool view")
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with two spools", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_spool(scene)
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(scene.frame_end)
    path = os.path.join(ctx.work, "spool.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "spool", "The drum with its layers and level wind, the carousel with its arm (processor, draft)")
    return note


@line("motion.sea_cable", "A cable hangs into the sea and a CPS set rides down on it", "0.2.91",
      what="A cable over rollers and a stern horn hangs into 15 m of water in a catenary to the seabed and lies on it; "
           "a Run motor step pays it out at 60 m/min: the touch-down stays 20 m behind the horn, the seabed and the "
           "cable's end on it move aft, the CPS set goes over the horn and down the catenary; seen through the "
           "cut-away behind the stern; a label shows its top tension, layback and speed (task 0173)")
def motion_sea_cable(ctx):
    from ..blender import animation, paths, paths_sea, render, tour
    scene = ctx.fresh(SEA_CABLE)
    s = scene.fresing
    s.background, s.env_detail, s.sea_state, s.water_level = "SEA", "SIMPLE", "CALM", 2.0
    s.sea_depth = 15.0
    t0 = time.time()
    made = paths_sea.set_up_test_model(scene)
    ctx.metric("set up the cable into the sea", time.time() - t0, "s")
    item = paths.find(scene, made["cable"])
    _check(item.b_kind == "SEA" and not item.problem, f"the cable into the sea: {item.problem or 'no sea end'}")
    n = paths_sea.numbers(scene, item)
    _check(abs(n.get("layback", 0.0) - 20.0) < 0.01, f"the layback is {n.get('layback', 0.0):.2f} m (20 m set)")
    s.sea_cutaway = True
    tour.add_lay_label(scene, item)                 # task 0173: the cable's live numbers in a label
    from ..blender import cameras
    scene.camera = cameras.add_camera(scene, "ISO", 30.0, "Sea view")
    scene.camera.matrix_world = paths_sea.view_matrix(scene, item)
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with the cable into the sea", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_sea_cable(scene)
    times = []
    for f in range(scene.frame_start, scene.frame_end + 1, 4):
        t0 = time.perf_counter()
        scene.frame_set(f)
        times.append(time.perf_counter() - t0)
    times.sort()
    ctx.metric("frame change with the sea cable", 1000.0 * times[len(times) // 2], "ms")
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(scene.frame_end)
    path = os.path.join(ctx.work, "sea_cable.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "sea_cable", "The cable from the horn down to the seabed through the cut-away, the CPS set on "
                                   "it (processor, draft)")
    return note


@line("motion.moving_cable", "A cable on a moving part: kept tight, hung on, let go, settles", "0.2.95",
      what="A trolley carries a block with a sheave aft over the stern, its hanger tilts and the block is lowered: the "
           "lift wire's winch keeps the wire tight (it pays out what the moving sheaves need), the cable end on the "
           "block leaves the stern horn and hangs from the block's sheave, and is let go near the seabed – its start "
           "and its turn round the sheave stay behind while the block is lifted away and settle onto the seabed in "
           "2 s (task 0125)")
def motion_moving_cable(ctx):
    from ..blender import animation, cameras, paths, render, tour
    scene = ctx.fresh(MOVING_CABLE)
    s = scene.fresing
    s.background, s.env_detail, s.sea_state, s.water_level = "SEA", "SIMPLE", "CALM", 2.0
    s.sea_depth = 15.0
    t0 = time.time()
    made = paths.set_up_moving_model(scene)
    ctx.metric("set up the cable on a moving part", time.time() - t0, "s")
    for name in (made["cable"], made["wire"]):
        item = paths.find(scene, name)
        _check(item is not None and not item.problem, f"'{name}': {item.problem if item is not None else 'missing'}")
    s.sea_cutaway = True
    scene.camera = cameras.add_camera(scene, "ISO", 30.0, "Moving view", points=paths.moving_view_points(scene))
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with a cable on a moving part", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_moving_cable(scene)
    times = []
    for f in range(scene.frame_start, scene.frame_end + 1, 6):
        t0 = time.perf_counter()
        scene.frame_set(f)
        times.append(time.perf_counter() - t0)
    times.sort()
    ctx.metric("frame change with the moving cable", 1000.0 * times[len(times) // 2], "ms")
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(scene.frame_end)
    path = os.path.join(ctx.work, "moving_cable.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "moving_cable", "The block lifted away from the cable end it let go on the seabed, the lift wire "
                                      "tight over the head sheave (processor, draft)")
    return note


@line("motion.swivel", "A sheave on a swivel turns to follow its wire", "0.2.138",
      what="A deck davit slews ±45° while its wire runs from a fixed fairlead over a sheave on a swivel head at the "
           "arm's tip and down into the hook block: Build turns the swivel at every frame so the wire comes into the "
           "sheave in its plane (task 0172)")
def motion_swivel(ctx):
    from ..blender import animation, cameras, paths_swivel, render, tour
    scene = ctx.fresh(SWIVEL)
    s = scene.fresing
    t0 = time.time()
    made = paths_swivel.set_up_test_model(scene)
    ctx.metric("set up the swivel", time.time() - t0, "s")
    scene.camera = cameras.add_camera(scene, "ISO", 35.0, "Swivel view")
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with a swivel", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    note = tour._check_swivel(scene)
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(scene.frame_start + int(0.3 * (scene.frame_end - scene.frame_start)))
    path = os.path.join(ctx.work, "swivel.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "swivel", "The davit slewed, its swivel head turned so the wire runs straight into the sheave "
                                "(processor, draft)")
    return note


@line("motion.tracks", "Tensioner tracks and a belt run with the cable", "0.2.87",
      what="The tensioner test model: the cable runs, the pads of both tracks run round their sprockets with it (the "
           "pads holding the cable as fast as the cable), the top track lifts and squeezes, the tensioner tilts 6° on "
           "its hinge and back, a belt of separate links "
           "runs round three pulleys; every link's two hinges on its loop, one pitch apart")
def motion_tracks(ctx):
    from ..blender import animation, cameras, render, tour, tracks
    scene = ctx.fresh(TRACKS)
    s = scene.fresing
    t0 = time.time()
    made = tracks.set_up_test_model(scene)
    ctx.metric("set up three tracks", time.time() - t0, "s")
    for it in tracks.items(scene):
        text, level = tracks.status(scene, it)
        _check(level == "OK", f"'{it.name}': {text}")
    scene.camera = cameras.add_camera(scene, "ISO", 35.0, "Tracks view")
    a = s.animations[made["animation"]]
    t0 = time.time()
    info = animation.bake(scene, a)
    ctx.metric("build with three tracks", time.time() - t0, "s")
    _check(not info["warnings"], "; ".join(info["warnings"][:2]))
    t0 = time.time()
    frames = list(range(scene.frame_start, scene.frame_end + 1, 4))
    for f in frames:
        scene.frame_set(f)
    ctx.metric("frame change with 146 track parts running", (time.time() - t0) / len(frames) * 1000.0, "ms")
    note = tour._check_tracks(scene)
    _small_output(s)
    s.use_gpu = False
    scene.frame_set(100)
    path = os.path.join(ctx.work, "tracks.png")
    render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "tracks", "The tensioner with its pads running and the top track lifted, the belt behind "
                                "(processor, draft)")
    return note


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


ACCEL_INI = """[TRAJ]
LINEAR_UNITS = mm
[AXIS_X]
MAX_VELOCITY = 100
MAX_ACCELERATION = 800
[AXIS_Y]
MAX_VELOCITY = 100
MAX_ACCELERATION = 800
[AXIS_Z]
MAX_VELOCITY = 50
MAX_ACCELERATION = 500
"""


@line("gcode.acceleration", "G-code timed with acceleration (G64 / G61, LinuxCNC INI)", "0.2.83",
      what="The test gantry reads an invented LinuxCNC .ini (speeds and accelerations), then runs 2 mm zigzag steps "
           "blended (G64) and with exact stops (G61) and one long line: the step lasts clearly longer than without "
           "acceleration and the tool's tip is on the speed profile's place at frames and between them")
def gcode_acceleration(ctx):
    from mathutils import Vector

    from ..blender import animation, gcode, joints, tour
    from ..core import gcode as core
    scene = ctx.fresh(GANTRY)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool = _ob(scene, "TOOL T1 FLAT D6")
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, _ob(scene, "STOCK 300x200x30"))
    c = scene.fresing.cnc
    _check(c.use_accel, "Speed up and slow down is off for a new machine")
    ini = os.path.join(ctx.work, "pccheck_machine.ini")
    with open(ini, "w", encoding="utf-8") as fh:
        fh.write(ACCEL_INI)
    got = gcode.read_ini(scene, ini)
    _check(set(got) == {"x", "y", "z"}, f"the .ini gave the axes {sorted(got)} (X, Y, Z expected)")
    _check(abs(c.accel_x - 800) < 1e-6 and abs(c.accel_z - 500) < 1e-6 and abs(c.rapid_x - 6000) < 1e-6,
           f"the .ini's values were not filled in (X {c.rapid_x:.0f} mm/min, {c.accel_x:.0f} mm/s²)")
    path = os.path.join(ctx.work, "pccheck_accel.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(tour.ACCEL_TOUR)
    a = scene.fresing.animations.add()
    a.name, a.tail = "Acceleration", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    gcode.step_changed(scene, b)
    info = gcode.info(scene, b)
    with_s, plain = info.get("machine_s", 0.0), info.get("plain_s", 0.0)
    _check(info.get("accel") and with_s > 1.2 * plain, f"with acceleration {with_s:.2f} s, without {plain:.2f} s: "
           "not clearly longer")
    t0 = time.time()
    r = animation.bake(scene, a)
    ctx.metric("bake", time.time() - t0, "s")
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    mach = gcode.Machine(scene)
    prog = gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0]
    sch = core.Schedule(prog, gcode.timing(scene, a, b))
    tip = gcode._rest_tip(tool)[0]
    zero = c.zero_empty
    worst = 0.0
    for f in range(1, r["frames"] + 1, 2):
        for sub in (0.0, 0.5):
            scene.frame_set(f, subframe=sub)
            here = zero.matrix_world.inverted() @ (tool.matrix_world @ tip) / 0.001
            want = Vector(sch.point_at((f + sub - 1) / 25.0)) - Vector(mach.g54)
            worst = max(worst, (here - want).length)
    _check(worst < 0.01, f"the tool's tip is {worst:.3f} mm away from the speed profile's place")
    c.use_accel = False
    off = gcode.info(scene, b)
    _check(not off.get("accel") and abs(b.duration - plain) < 1e-3, f"switched off the step lasts {b.duration:.2f} s, "
           f"{plain:.2f} s expected")
    return (f"{gcode.fmt_time(with_s)} – {gcode.fmt_time(plain)} without acceleration; tip on the profile to "
            f"{worst:.4f} mm")


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
    joints.create(scene, "ROTATE", [car], Vector((1.25, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    cnc = scene.fresing.cnc
    cnc.changer = "ATC"
    cnc.carousel_joint = "Carousel"
    rows[1].pocket = 7
    station = Vector((1.40, 0, 0.35))
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
      what="The test mill with a double-arm changer and a 24-pot side magazine changes three BT40 tools: the pot tips "
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
    centre = Vector((-0.23, 0.0, 0.5))                      # the arm's hub, the tools pulled down (task 0250)
    pts = np.array([tuple(centre + Vector(d)) for d in ((-0.3, -0.26, -0.16), (0.3, 0.26, 0.14))])
    cam = cameras.add_camera(scene, "ISO", 50.0, "PC check arm", points=pts)
    scene.camera = cam
    _small_output(scene.fresing, 480, 360)
    _cpu_still(ctx, scene, "doublearm", "Double-arm changer at its half turn (processor, draft)")
    return (f"3 changes, T1 back from pot 2; hand-overs within {worst:.4f} mm; arm {t['back'][1] - t['grip'][0]:.2f} "
            "s per change")


def _rotary_why(scene, home, me) -> str:
    """What to look at when the 4th axis' cut is not where it should be (task 0127: seen on 3 GitHub runs out of
    many, never on a chat machine in 36 runs): did the bits' path read from the motion come into the bar (then the
    cut went wrong), or not (then the motion was read wrong); how long the reading and the cut took; where the bar
    and the A axis were; the machine's processors."""
    import numpy as np

    from ..blender import joints, machining, rotary
    out = []
    try:
        m = np.array(home, dtype=float)
        for c in machining.cut_items(scene):
            o = np.asarray(c.path.o, dtype=float).reshape(-1, 3)
            if not len(o):
                out.append("path: no samples")
                continue
            w = o @ m[:3, :3].T + m[:3, 3]
            r = np.hypot(w[:, 1], w[:, 2] - rotary.TEST_A_4[2]) / 0.001
            out.append(f"path: {len(o)} samples, the tip comes {r.min():.2f} mm near the bar's axis")
    except Exception as exc:                    # (the reason is wanted even if this goes wrong)
        out.append(f"path not read: {exc}")
    rt = machining.runtime(scene)
    ja = scene.fresing.joints.get("Rotary A")
    a1 = math.degrees(joints.get_value(ja)) if ja is not None else float("nan")
    out.append(f"read in {rt.get('sample_s', 0.0):.1f} s; {machining.status(scene)}; cut mesh {len(me.polygons)} faces")
    out.append(f"bar at frame {scene.frame_current}: turned {math.degrees(home.to_euler().x):.1f}°, A {a1:.1f}°")
    out.append(f"{os.cpu_count()} processors")
    return "[" + "; ".join(out) + "]"


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
        start = Vector((x * 0.001, 0.0, rotary.TEST_A_4[2])) + d * 0.06
        hit = bvh.ray_cast(start, -d)[0]
        return 60.0 - ((hit - start).length / 0.001) if hit is not None else 0.0
    got = [radius(-90.0 + 80.0 * th / 360.0, th) for th in (90.0, 270.0)] + [radius(35.0, 0.0), radius(35.0, 180.0)]
    want = [23.0, 23.0, 22.0, 22.0]
    err = max(abs(g - w_) for g, w_ in zip(got, want))
    _check(err < 0.05, "the cuts on the bar are not where the program puts them: radius "
           + ", ".join(f"{g:.2f}" for g in got) + " mm (should be 23, 23, 22, 22) " + _rotary_why(scene, home, me))
    scene.frame_set(int(end * 0.3))
    pts = [(-0.12, -0.03, 0.18), (0.12, 0.03, 0.26)]         # round the bar (its axis at z 0.21, task 0250)
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
      what="Five cover sections follow a 1000 mm slide axis: 200, 400, 600, 800, 1000 mm (drawn at 400 mm: on their "
           "CAD place there, 120 ... 600 mm at 1000 mm); the 5-section "
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
    axis = joints.create(scene, "SLIDE", [_ob(scene, "CARRIAGE")], Vector((0.2, 0.3, 0.2)), Vector((1, 0, 0)),
                         name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, waycover.TEST_TRAVEL
    c = waycover.settings(scene)
    c.axis, c.total = "X axis", waycover.TEST_TRAVEL
    for g in names:
        waycover.add_section(scene, [_ob(scene, n) for n in g])
    built, problems = waycover.make(scene)
    _check(built == 5 and not problems, f"the way cover was not made: {problems}")
    joints.set_value(joints.find(scene, "X axis"), 1.0)
    _update()
    _update()
    got = [(min_x(_ob(scene, g[0])) - r) * 1000.0 for g, r in zip(names, rest)]
    for k, mm in enumerate(got, start=1):
        _check(abs(mm - 200.0 * k) < 0.05, f"section {k} moved {mm:.2f} mm, not {200 * k} mm")
    _check(joints.couplings_simple(scene), "the cover couplings need Python scripts (they must not)")
    # "Drawn at" (task 0090): drawn with the axis at 400 mm, the sections stand on their CAD place there
    c.drawn_at = 0.4
    joints.set_value(joints.find(scene, "X axis"), 0.4)
    _update()
    _update()
    off = max(abs(min_x(_ob(scene, g[0])) - r) * 1000.0 for g, r in zip(names, rest))
    _check(off < 0.05, f"drawn at 400 mm, a section is {off:.2f} mm off its CAD place at 400 mm")
    joints.set_value(joints.find(scene, "X axis"), 1.0)
    _update()
    _update()
    got_d = [(min_x(_ob(scene, g[0])) - r) * 1000.0 for g, r in zip(names, rest)]
    for k, mm in enumerate(got_d, start=1):
        _check(abs(mm - 120.0 * k) < 0.05, f"drawn at 400 mm, section {k} moved {mm:.2f} mm at 1000 mm, not {120 * k}")
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
      what="A cover each side of the carriage on one 1000 mm axis, the plate next to the carriage bolted to it (the "
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
    for axis in (1.0, 0.4):
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


@line("animation.sequence", "Assembly sequence: take apart, put together", "0.2.79",
      what="A spindle unit of 12 parts is taken apart along its own axis (bolts and nut first, staggered, trail "
           "lines) and put together again: every part ends within 0.01 mm of its place, and nothing runs into "
           "anything on the way (clash check)")
def animation_sequence(ctx):
    from ..blender import animation, clash, tour
    scene = ctx.fresh(SEQUENCE)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = tour.SEQUENCE_ANIM, 0.0, "25"
    tour.sequence_steps(scene, a)
    t0 = time.time()
    res = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    note = tour.check_sequence(scene, a)
    run = clash.check(scene)
    _check(not run.rows, f"{len(run.rows)} clashes on the way: " + "; ".join(clash.core.row_text(r)
                                                                           for r in run.rows[:3]))
    return note + "; no clash"


@line("animation.product_video", "One-click product video", "0.2.81",
      what="6 Animation > Make a product video builds the animation 'Product video' from a project with one joint "
           "and a subassembly: the turn round, the joint there and back, the take-apart and put-together; Build "
           "animation gives no warning")
def animation_product_video(ctx):
    from mathutils import Vector

    from ..blender import animation, joints, product_video, tour
    scene = ctx.fresh(SEQUENCE)
    u = _ob(scene, tour.SEQUENCE_UNIT)
    j = joints.create(scene, "ROTATE", [u], Vector((0.3, 0.0, 0.0)), Vector((0, 0, 1)), name="Turn unit")
    j.use_limits, j.rot_min, j.rot_max = True, -0.6, 0.6
    import bpy
    _check(bpy.ops.fresing.product_video() == {"FINISHED"}, "Make a product video did not finish")
    t0 = time.time()
    a = product_video.find_animation(scene)
    res = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    return tour.check_product_video(scene)


@line("animation.sequence_frame", "Assembly sequence round a frame, a part riding on another", "0.2.102",
      what="A slide unit under a portal frame comes apart 'Up': the parts under the frame's beam go sideways instead "
           "of through it, the gripper block (it rides on the carriage) leaves first from where the carriage put it; "
           "put together, every part ends within 0.01 mm of its place, and the clash check finds nothing")
def animation_sequence_frame(ctx):
    from ..blender import animation, clash, tour
    scene = ctx.fresh(SEQUENCE_FRAME)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = tour.FRAME_ANIM, 0.0, "25"
    tour.frame_steps(scene, a)
    t0 = time.time()
    res = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    note = tour.check_frame(scene)
    run = clash.check(scene)
    _check(not run.rows, f"{len(run.rows)} clashes on the way: " + "; ".join(clash.core.row_text(r)
                                                                           for r in run.rows[:3]))
    return note + "; no clash"


@line("animation.back_to_cad", "Back to CAD step", "0.2.102",
      what="A Go to pose step slides the carriage and the gripper out, then a Back to CAD step brings both joints "
           "back to 0 over one second (eased)")
def animation_back_to_cad(ctx):
    from ..blender import animation, states, tour
    scene = ctx.fresh(SEQUENCE_FRAME)
    slide, lift = tour.frame_rig(scene)
    from ..blender import joints
    joints.set_value(slide, 0.06)
    joints.set_value(lift, 0.02)
    import bpy
    bpy.context.view_layer.update()
    pose = states.save_pose(scene, "Slid out")
    joints.set_value(slide, 0.0)
    joints.set_value(lift, 0.0)
    a = scene.fresing.animations.add()
    a.name, a.tail, a.fps = tour.BACK_ANIM, 0.0, "25"
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    p = a.blocks.add()
    p.kind, p.pose, p.start, p.duration = "POSE", pose.name, 0.0, 1.0
    _check(bpy.ops.fresing.block_add(kind="CAD") == {"FINISHED"}, "Add step > Back to CAD did not finish")
    c = a.blocks[-1]
    c.start, c.duration = 1.5, 1.0
    return tour.check_back_to_cad(scene)


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
    from ..blender import tour
    j = joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], Vector(tour.CRANE_PIVOT), Vector((0, 0, 1)),
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


@line("motion.hover", "Hover highlight when picking", "0.2.63",
      what="20 spots on the test crane (holes, shafts, flat faces) worked out as the mouse would: the face that lights "
           "up is the CAD face the click then uses, with the same axis; the time per mouse move")
def motion_hover(ctx):
    import statistics

    import bpy
    from mathutils import Vector

    from ..blender import build, faces, hover, joints
    scene = ctx.fresh(CRANE_A)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    parts = sorted((o for o in scene.objects if o.get(build.PROP_KIND) == "part"), key=lambda o: o.name)
    spots, times, kinds = 0, [], set()
    for ob in parts * 3:
        if spots >= 20:
            break
        me = ob.data
        starts = faces.face_starts(me)
        face = (spots * 7 + len(ob.name)) % (len(starts) - 1)
        poly = me.polygons[int(starts[face])]
        mw = ob.matrix_world
        at = mw @ poly.center
        n = (mw.to_3x3().inverted().transposed() @ poly.normal).normalized()
        origin, direction = at + n * 0.0005, -n
        part, index, loc, normal = hover.cast(scene, dg, origin, direction)
        if part is not ob or index != poly.index:
            continue                               # another part lies in front of this spot
        t0 = time.perf_counter()
        h = hover.look(scene, dg, origin, direction)
        times.append((time.perf_counter() - t0) * 1000.0)
        o, d, _desc = joints.axis_from_hit(part, index, loc, normal)
        _check(h.part == ob.name and h.face == face,
               f"{ob.name}: the highlight shows face {h.face} of '{h.part}', the click uses face {face}")
        _check((h.origin - o).length < 1e-9 and (h.direction - d).length < 1e-9,
               f"{ob.name}: the highlighted axis is not the axis the click gives")
        kinds.add(h.kind)
        spots += 1
    _check(spots >= 20, f"only {spots} spots on the crane could be reached")
    _check("flat" in kinds and kinds & {"hole", "shaft"}, f"not every kind of face was tried: {sorted(kinds)}")
    h = hover.look(scene, dg, Vector((0, 0, 50)), Vector((0, 0, 1)))
    _check(not h.part, "empty space lit up as a part")
    # the point pickers (task 0089): same part and face as the click, a dot where it lands
    pts = 0
    for ob in parts[:12]:
        starts = faces.face_starts(ob.data)
        poly = ob.data.polygons[int(starts[0])]
        n = (ob.matrix_world.to_3x3().inverted().transposed() @ poly.normal).normalized()
        origin, direction = ob.matrix_world @ poly.center + n * 0.0005, -n
        part, index, loc, _nrm = hover.cast(scene, dg, origin, direction)
        if part is not ob or index != poly.index:
            continue
        hp = hover.look_point(scene, dg, origin, direction, lambda o, name, *_a: f"Spot on {name}")
        _check(hp.part == ob.name and hp.face == faces.face_of_polygon(ob.data, index) and hp.point is not None
               and (hp.point - loc).length < 1e-9 and hp.text.startswith("Spot on "),
               f"{ob.name}: the point highlight is not where the click lands")
        pts += 1
    _check(pts >= 3, f"only {pts} point spots could be reached")
    ctx.metric("time per mouse move (median)", round(statistics.median(times), 2), "ms")
    ctx.metric("time per mouse move (slowest)", round(max(times), 2), "ms")
    return f"{spots} spots right ({', '.join(sorted(kinds))}); {statistics.median(times):.2f} ms per mouse move"


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


@line("scene.sea_ground", "Sea cut-away: the ground and a pile below the seabed", "0.2.115",
      what="The crane on the open sea with a bright red pile that goes 30 m into the ground; the cut-away box round the "
           "pile also cuts the seabed: the soil section shows (layers) and the pile is seen down into it, rendered "
           "small (processor, draft); with the ground off the same view shows no pile (task 0148)")
def scene_sea_ground(ctx):
    import bmesh
    import bpy
    import numpy as np

    from ..blender import build, cameras, surroundings
    from .runner import read_pixels
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.env_detail, s.background = "SIMPLE", "SEA"
    root = build.model_roots(scene)[0]
    low = float(build.world_bounds(list(build.iter_parts(scene)))[0][2])
    foot = low - 30.0                                  # the pile's foot: 30 m under the crane's lowest point
    me = bpy.data.meshes.new("Test pile")
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=1.5, radius2=1.5, depth=40.0)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, foot + 20.0), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.new("Test pile red")
    mat.diffuse_color = (1.0, 0.0, 0.0, 1.0)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.0, 0.0, 1.0)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    me.materials.append(mat)
    pile = bpy.data.objects.new("Test pile", me)
    scene.collection.objects.link(pile)
    pile.parent = root
    pile[build.PROP_KIND] = "part"
    pile[build.PROP_UID] = "test pile"
    bpy.context.view_layer.update()
    mn, mx = surroundings._model_box(scene)
    s.sea_depth = 30.0
    s.water_level = float(low - float(mn[2]) + 30.0)   # the water 30 m over the pile's foot: the seabed at the crane's foot
    s.sea_cut_auto = False
    s.sea_cut_length = s.sea_cut_width = 30.0
    s.sea_cut_start = float(mn[0]) - 15.0
    s.sea_cut_side = -float(mn[1] + mx[1]) / 2.0
    s.sea_cutaway = True
    _check(s.sea_cut_ground, "the ground did not go on by itself although a part reaches below the seabed")
    soil = [o for o in bpy.data.objects if o.get(surroundings.TAG) == "soil"]
    _check(len(soil) == 1, f"{len(soil)} soil sections were made (1 wanted)")
    water = surroundings.waterline(scene)
    _check(abs(soil[0]["fr_soil_depth"] - 35.0) < 1.0, f"the soil section is {soil[0]['fr_soil_depth']:.1f} m deep "
                                                      "(the pile's 30 m and 5 m more wanted)")
    _small_output(s, 192, 108)
    cam = cameras.add_camera(scene, "ISO", 30.0, "Ground view")
    from mathutils import Vector
    eye, at = Vector((-12.0, 0.0, water + 14.0)), Vector((0.0, 0.0, water - 30.0 - 12.0))
    cam.matrix_world = (at - eye).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    cam.matrix_world.translation = eye
    cam.data.lens = 60.0
    scene.camera = cam
    info = _cpu_still(ctx, scene, "sea_ground", "The pile below the seabed in the cut-away (processor, draft)",
                      model_check=False)
    px = read_pixels(os.path.join(ctx.work, "sea_ground.png"))
    h, w = px.shape[:2]
    red = (px[..., 0] > 0.5) & (px[..., 1] < 0.15) & (px[..., 2] < 0.15)
    _check(red[h // 2 - 6:h // 2 + 6, w // 2 - 6:w // 2 + 6].any(), "the pile below the seabed is not seen in the cut")
    s.sea_cut_ground = False                           # the same view, the seabed closed
    path = os.path.join(ctx.work, "sea_ground_off.png")
    from ..blender import render
    render.render_still(scene, s, "draft", filepath=path)
    off = read_pixels(path)
    shut = (off[..., 0] > 0.5) & (off[..., 1] < 0.15) & (off[..., 2] < 0.15)
    _check(shut[h // 2 - 6:h // 2 + 6, w // 2 - 6:w // 2 + 6].sum() < red[h // 2 - 6:h // 2 + 6, w // 2 - 6:w // 2 + 6].sum()
           // 2 + 1, "with the ground off the pile below the seabed is still seen")
    return f"rendered in {info['seconds']} s"


# ---------------------------------------------------------------------------
# weather and time of day (task 0109)
# ---------------------------------------------------------------------------

def _weather_scene(ctx, background="QUAY", preset=None):
    from ..blender import weather
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.env_detail = "SIMPLE"
    s.background = background
    s.weather.enabled = True
    if preset:
        weather.use_preset(scene, preset)
    _small_output(s)
    return scene


def _wx(scene, name) -> float:
    from ..core import weather as core
    return float(scene.get(core.prop(name), -1.0))


def _mean_light(path) -> float:
    import bpy
    img = bpy.data.images.load(path, check_existing=False)
    try:
        import numpy as np
        px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        return float(px.reshape(-1, 4)[:, :3].mean())
    finally:
        bpy.data.images.remove(img)


@line("weather.time", "Weather: time of day, sunrise to night", "0.2.88",
      what="The crane on the quay at 07:00, 12:00, 18:30 and 23:00 (equinox, 55° N): the sun's height and the "
           "daylight follow the clock, the floodlights come on at dusk; noon and midnight rendered small (processor, "
           "draft) – noon must be brighter")
def weather_time(ctx):
    from ..blender import weather
    from ..core import weather as core
    scene = _weather_scene(ctx)
    w = scene.fresing.weather
    w.use_date, w.latitude = False, core.DEFAULT_LATITUDE        # the equinox at 55° N, whatever the first switch took
    seen = {}
    for hour in (7.0, 12.0, 18.5, 23.0):
        w.hour = hour
        el, _az = core.sun_of(weather.state(scene))
        _check(abs(_wx(scene, "sun_el") - el) < 0.01, f"{core.clock(hour)}: the sun stands at "
                                                       f"{_wx(scene, 'sun_el'):.1f}°, not {el:.1f}°")
        seen[hour] = (_wx(scene, "day"), _wx(scene, "flood"))
    _check(seen[12.0][0] > 0.99 and seen[23.0][0] < 0.01, f"daylight at noon / midnight: {seen[12.0][0]:.2f} / "
                                                          f"{seen[23.0][0]:.2f}")
    _check(seen[23.0][1] > 0.9 and seen[12.0][1] < 0.01, "the floodlights do not follow the clock (Auto)")
    w.hour = 12.0
    noon = _cpu_still(ctx, scene, "weather_noon", "Quay at noon (processor, draft)")
    light_noon = _mean_light(os.path.join(ctx.work, "weather_noon.png"))
    w.hour = 23.0
    night = _cpu_still(ctx, scene, "weather_night", "Quay at 23:00, floodlights (processor, draft)")
    light_night = _mean_light(os.path.join(ctx.work, "weather_night.png"))
    _check(light_noon > light_night * 1.2, f"noon ({light_noon:.3f}) is not brighter than midnight "
                                           f"({light_night:.3f})")
    lamps = [o for o in scene.objects if o.type == "LIGHT" and o.get("fr_weather")]
    _check(lamps, "no floodlights at night")
    ctx.metric("noon", noon["seconds"], "s")
    ctx.metric("night", night["seconds"], "s")
    return f"sun follows the clock; {len(lamps)} night lamps; noon {noon['seconds']} s, night {night['seconds']} s"


@line("weather.rain", "Weather: rain and the wet look", "0.2.88",
      what="Storm on the quay: heavy rain falls, slanting with a gale; the crane's looks get the weather node "
           "group (wet: darker, glossy). Rendered small (processor, draft), the time compared with the "
           "same picture without weather")
def weather_rain(ctx):
    from ..blender import weather_look
    scene = _weather_scene(ctx, preset="STORM")
    _check(_wx(scene, "rain") > 0.5 and _wx(scene, "wet") > 0.9, "the Storm preset has no rain or is not wet")
    _check(any(o.get("fr_weather") == "rain" for o in scene.objects), "no rain object")
    mats = {sl.material for o in scene.objects if o.get("fr_uid") and o.type == "MESH" for sl in o.material_slots
            if sl.material is not None}
    wrapped = sum(1 for m in mats if weather_look.is_wrapped(m))
    _check(mats and wrapped == len(mats), f"{wrapped} of {len(mats)} looks have the weather group")
    wet = _cpu_still(ctx, scene, "weather_rain", "Storm on the quay (processor, draft)")
    scene.fresing.weather.enabled = False
    _check(not any(weather_look.is_wrapped(m) for m in mats), "a look kept the weather group with weather off")
    _check(not any(o.get("fr_weather") for o in scene.objects), "weather objects stayed with weather off")
    dry = _cpu_still(ctx, scene, "weather_off", "The same without weather (processor, draft)")
    ctx.metric("storm", wet["seconds"], "s")
    ctx.metric("no weather", dry["seconds"], "s")
    return f"storm {wet['seconds']} s, no weather {dry['seconds']} s"


@line("weather.snow", "Weather: snow layer and falling snow", "0.2.88",
      what="Snow at the quay: flakes fall, a snow layer lies on the crane's upward faces under the open sky. Rendered "
           "small (processor, draft)")
def weather_snow(ctx):
    scene = _weather_scene(ctx, preset="SNOW_QUAY")
    _check(_wx(scene, "cover") > 0.5 and _wx(scene, "snow") > 0.3, "the preset has no snow")
    _check(any(o.get("fr_weather") == "snow" for o in scene.objects), "no snow object")
    info = _cpu_still(ctx, scene, "weather_snow", "Snow at the quay (processor, draft)")
    ctx.metric("snow", info["seconds"], "s")
    return f"rendered in {info['seconds']} s"


@line("weather.fog", "Weather: fog and haze", "0.2.88",
      what="The open sea with 400 m visibility: the far sea fades into the fog. Rendered small (processor, draft) "
           "and compared with clear air")
def weather_fog(ctx):
    scene = _weather_scene(ctx, background="SEA", preset="CLEAR_DAY")
    clear = _cpu_still(ctx, scene, "weather_clear", "Clear air (processor, draft)")
    scene.fresing.weather.visibility = 400.0
    _check(abs(_wx(scene, "fog") - 3.912 / 0.4) < 0.01, f"fog density {_wx(scene, 'fog'):.2f} per km")
    foggy = _cpu_still(ctx, scene, "weather_fog", "Fog, 400 m (processor, draft)")
    ctx.metric("clear", clear["seconds"], "s")
    ctx.metric("fog", foggy["seconds"], "s")
    return f"clear {clear['seconds']} s, fog {foggy['seconds']} s"


@line("weather.sea", "Weather: the sea follows the wind", "0.2.88",
      what="The open sea 'From the wind' at Beaufort 3, 6 and 9: the waves grow and the share of white caps grows "
           "as published measurements say (Monahan & O'Muircheartaigh 1980)")
def weather_sea(ctx):
    from ..core import sea, weather as core
    scene = _weather_scene(ctx, background="SEA")
    s = scene.fresing
    s.sea_state = "WIND"
    rows = []
    for bft in (3.0, 6.0, 9.0):
        s.weather.wind = bft
        _check(abs(_wx(scene, "foam") - sea.foam_threshold(bft)) < 1e-6, "the sea's foam does not follow the wind")
        rows.append((bft, sea.whitecap_coverage(core.bft_to_ms(bft))))
    _check(rows[0][1] < rows[1][1] < rows[2][1], f"white caps do not grow with the wind: {rows}")
    return ", ".join(f"Bft {b:.0f}: {c * 100:.2g} % white caps" for b, c in rows)


@line("weather.step", "Weather: a Weather & time step in a video", "0.2.88",
      what="An animation with one Weather & time step (noon to dusk, rain starting): the build keys the weather, the "
           "first and last frames differ, Clear keys puts the panel's weather back")
def weather_step(ctx):
    from ..blender import animation, weather
    scene = _weather_scene(ctx, preset="CLEAR_DAY")
    s = scene.fresing
    a = s.animations.add()
    a.name, a.tail, a.quality = "Weather step", 0.0, "draft"
    b = a.blocks.add()
    b.kind, b.start, b.duration = "WEATHER", 0.0, 2.0
    weather.step_init(scene, a, b)
    b.wx_hour, b.wx_rain = 18.5, 0.6
    res = animation.bake(scene, a)
    s.anim_baked = a.name
    scene.frame_set(1)
    day0, rain0 = _wx(scene, "day"), _wx(scene, "rain")
    scene.frame_set(scene.frame_end)
    day1, rain1 = _wx(scene, "day"), _wx(scene, "rain")
    _check(day1 < day0 and rain1 > rain0 + 0.5, f"daylight {day0:.2f} -> {day1:.2f}, rain {rain0:.2f} -> {rain1:.2f}")
    animation.clear_keys(scene)
    _check(not weather.keyed(scene), "Clear keys left weather keys")
    return f"{res['frames']} frames; daylight {day0:.2f} -> {day1:.2f}, rain {rain0:.2f} -> {rain1:.2f}"


@line("house.bake", "House from House Planner: import, bake, export", "0.2.92",
      what="The made-up sample house (sample-house.hpscene): File > Import > House Planner scene, then Bake and export "
           "of one moment (summer morning, 4 samples, no photo); the package's structure is checked (files, page "
           "sizes and rows, rectangles = each surface's map size, light per vertex = each surface's vertex count)")
def house_bake(ctx):
    import bpy

    from ..blender import house_bake as hb
    from ..blender import house_import
    from ..core import house_scene as hs
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    from ..blender import workspaces
    workspaces.use_all(scene)                    # the check's own project: every function, never locked
    src = os.path.join(DATA, "sample-house.hpscene")
    folder = os.path.join(ctx.work, "house")
    os.makedirs(folder, exist_ok=True)
    local = os.path.join(folder, "sample-house.hpscene")
    shutil.copyfile(src, local)
    t0 = time.time()
    out = house_import.import_scene(scene, local)
    t_import = time.time() - t0
    house = out["house"]
    _check(len(house_import.parts(scene)) == len([s for s in house.surfaces.values() if s.mesh is not None]),
           "not every surface of the house came in")
    _check(house_import.lights(scene), "the ceiling lamp's light did not come in")
    path = os.path.join(folder, "sample-house.hpbake")
    res = hb.HouseBake(scene, path, moments=[house.recipe.moments[0].id], photos=False, videos=False,
                       samples=4).run()
    _check(os.path.exists(path), "no bake package was written")
    bad = hs.structure_problems(path, house)
    _check(not bad, "the bake package is not right: " + "; ".join(bad[:3]))
    ctx.metric("import", round(t_import, 1), "s")
    ctx.metric("bake one moment", round(res["seconds"], 1), "s")
    return (f"{len(house.surfaces)} surfaces; one moment baked in {res['seconds']:.0f} s, package "
            f"{os.path.getsize(path) / 1024:.0f} KB")


@line("house.toolbox", "A house from House Planner by itself (Toolbox folder)", "0.2.173",
      what="A house sent the way House Planner sends it, into a Toolbox folder in the check's own folder (never your "
           "real one): it waits, Bake now (one moment, 4 samples) imports it into a scene of its own and sends the "
           "bake package back as a job in House Planner's inbox; the status is done, the house scene is gone and the "
           "check's project is as it was")
def house_toolbox(ctx):
    from pathlib import Path

    import bpy

    from ..blender import toolbox_inbox as ti
    from ..blender import workspaces
    from ..core import house_scene as hs
    from ..core import toolbox as tb
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    workspaces.use_all(scene)
    root = Path(ctx.work) / "Toolbox"
    old = os.environ.get("TOOLBOX_HOME")
    os.environ["TOOLBOX_HOME"] = str(root)            # the check's own folder, never the real one
    try:
        _check(tb.home() == root, "TOOLBOX_HOME is not used")
        ib = ti.use_folder(tb.home(), keep=Path(ctx.work) / "kept", timer=False, samples=4, photo_samples=4,
                           quick=True)
        _check(not ib.problem, ib.problem)
        jid = tb.play_house_planner(root, Path(DATA) / "sample-house.hpscene", "Sample house – PC check")
        objects = sorted(o.name for o in scene.objects)
        ti.look()
        st = tb.read_doc(root / "tools" / tb.ME / "inbox" / jid / "status.json", "status")
        _check(st["state"] == "waiting", f"the job is {st['state']}, not waiting")
        t0 = time.time()
        with bpy.context.temp_override(scene=scene):
            why = ti.start(bpy.context, jid)
        _check(not why, f"Bake now: {why}")
        st = tb.read_doc(root / "tools" / tb.ME / "inbox" / jid / "status.json", "status")
        _check(st["state"] == "done" and st.get("reply"), f"the job ended {st['state']}: {st.get('text', '')}")
        reply = root / "tools" / tb.HOUSE_PLANNER / "inbox" / st["reply"]
        job = tb.read_doc(reply / "job.json", "job")
        bake = reply / job["files"][0]["name"]
        bad = hs.structure_problems(str(bake), hs.read_scene(os.path.join(DATA, "sample-house.hpscene")))
        _check(not bad, "the bake package sent back is not right: " + "; ".join(bad[:3]))
        _check(len(bpy.data.scenes) == 1, "the house's own scene was not removed")
        _check(sorted(o.name for o in scene.objects) == objects, "the project changed")
        ctx.metric("bake and send back", round(time.time() - t0, 1), "s")
        return f"sent back: {bake.name}, {bake.stat().st_size / 1024:.0f} KB in {time.time() - t0:.0f} s"
    finally:
        ti._S["inbox"] = None
        if old is None:
            os.environ.pop("TOOLBOX_HOME", None)
        else:
            os.environ["TOOLBOX_HOME"] = old


@line("web3d.export", "Web 3D model: export with baked looks", "0.2.77",
      what="The test mill saved as a web 3D model (.glb, Texture size 1024, compressed as a big model is) and its "
           "one-file page; the file is read back, checked against the glTF rules (part names hidden) and opened by "
           "Blender's own glTF importer. The page's player (task 0134) is opened in Edge or Chrome without a window: "
           "its settings menu, keys help and link, Space pauses a page with motion, and it says it draws without the "
           "graphics card. Task 0135: the part tools on the mill's page – a click picks a part and shows its card, "
           "two clicks measure, Fade the rest works, and the file carries the faces for measuring. Task 0218: "
           "six slices cut every part together and are deleted again")
def web3d_export(ctx):
    from ..blender import build, web3d
    from ..core import web3d as core
    scene = ctx.fresh(MILL)
    shown = len([p for p in build.iter_parts(scene) if p.visible_get()])
    out = web3d.export(scene, os.path.join(ctx.work, "web3d", "Test mill web 3D.glb"), size=1024, compress=True)
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    info = core.summary(data)
    _check(info["parts"] == shown, f"{info['parts']} parts in the file, {shown} shown")
    _check(info["textures"] >= 1, "no look was baked into a picture")
    _check(len(data) < 5_000_000, f"the file is {len(data) / 1e6:.1f} MB (at most 5 MB for the test mill)")
    _check(all(n.startswith(("Model", "Part ")) for n in info["names"]), "a part name is in the file")
    with open(out["html"], encoding="utf-8") as fh:
        page = fh.read()
    _check("FRTHREE" in page and 'id="fr-glb"' in page and "fr-menu" in page,
           "the page has no player or no model inside")
    _check(info["compressed"] and "MeshoptDecoder" in page, "the file was not compressed (meshopt)")
    lib = web3d.meshopt_native()
    _check(lib is not None, "Blender's meshopt library was not found: big files are packed less tightly "
                            f"(looked in {web3d.meshopt_paths()[:2]})")
    got = _gltf_triangles(out["path"])                  # Blender's glTF importer reads the compressed file
    _check(got == info["triangles"], f"Blender read {got} triangles back, the file has {info['triangles']}")
    ctx.metric("export", out["seconds"], "s")
    ctx.metric("file", len(data) / 1e6, "MB")
    return f"{out['text']}; read back by Blender's glTF importer; {_player_check(out['html'], ctx)}"


@line("web3d.small", "Web 3D model: smaller file – packed motion, WebP, model packed in the page", "0.2.143",
      what="Task 0175: the test mill with a part that slides and turns, one that only turns and one shown and hidden, "
           "saved as a compressed web 3D model with its animation: the keys are packed with meshopt's filters, a "
           "path that never moves and the frames between shown / hidden are left out, every frame stays within "
           "0.1 mm and 0.05°, the look pictures are WebP when Blender writes them smaller and as faithful, and the "
           "page holds the model gzip-packed; opened in Edge or Chrome without a window it unpacks the model and "
           "plays the keys as the app worked them out")
def web3d_small(ctx):
    import numpy as np

    from ..blender import build, web3d
    from ..core import web3d as core
    from ..core import web3d_env as env
    from ..core import web3d_keys as keys
    scene = ctx.fresh(MILL)
    parts = sorted(build.iter_parts(scene), key=lambda o: o.name)
    slide, turn, blink = parts[3], parts[5], parts[7]
    for ob in (slide, turn):
        ob.rotation_mode = "XYZ"
        ob.keyframe_insert("location", frame=1)
        ob.keyframe_insert("rotation_euler", frame=1)
    slide.location.x += 0.25
    slide.rotation_euler.z += 0.6
    turn.rotation_euler.x += 6.0
    for ob in (slide, turn):
        ob.keyframe_insert("location", frame=41)
        ob.keyframe_insert("rotation_euler", frame=41)
    for frame, hidden in ((1, False), (20, True), (35, False)):
        blink.hide_render = blink.hide_viewport = hidden
        blink.keyframe_insert("hide_render", frame=frame)
        blink.keyframe_insert("hide_viewport", frame=frame)
    scene.frame_start, scene.frame_end = 1, 41
    scene.frame_set(1)
    scene.fresing.anim_baked = "PC check"
    job = web3d.Job(scene, os.path.join(ctx.work, "web3d", "Small file.glb"), size=512, animation=True, compress=True)
    out = job.run()
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    doc, binary = core.read_glb(data)
    filters = {((v.get("extensions") or {}).get(core.MESHOPT) or {}).get("filter") for v in doc["bufferViews"]}
    _check({"QUATERNION", "EXPONENTIAL"} <= filters, f"the keys were not packed with meshopt's filters ({filters})")
    _check(out.get("still_tracks", 0) >= 1, "a path that never moves was written all the same")
    anim = doc["animations"][0]
    ch = {}
    for c in anim["channels"]:
        smp = anim["samplers"][c["sampler"]]
        ch[(c["target"]["node"], c["target"]["path"])] = (
            core.accessor_array(doc, binary, smp["input"])[:, 0].astype(np.float64),
            core.accessor_array(doc, binary, smp["output"]).astype(np.float64))
    node = {ob.name: n for ob, n in job._nodes}
    fps = scene.render.fps / scene.render.fps_base
    worst = [0.0, 0.0]
    for f in range(1, 42):
        scene.frame_set(f)
        for ob in (slide, turn):
            n = node[ob.name]
            tt, qq, _s = core.decompose(np.array(ob.matrix_world)[None])
            t = (f - 1) / fps
            p = keys.played(*ch[(n, "translation")], [t], "translation")[0] if (n, "translation") in ch else \
                np.array(doc["nodes"][n]["translation"])
            ang, _far = keys.turn_error(keys.played(*ch[(n, "rotation")], [t], "rotation"), keys.unit(qq))
            worst = [max(worst[0], float(np.linalg.norm(p - tt[0]))), max(worst[1], float(ang[0]))]
    scene.frame_set(1)
    _check(worst[0] <= keys.POS_TOL * 1.05 and worst[1] <= keys.ANGLE_TOL * 1.05,
           f"a part is {worst[0] * 1000:.3f} mm / {np.degrees(worst[1]):.3f}° off its place at a frame")
    webp = out.get("webp", 0)
    pics = "WebP pictures: " + (f"{webp} of {len(doc.get('images', []))}" if webp else
                                "none (the JPGs were smaller or more faithful)")
    with open(out["html"], encoding="utf-8") as fh:
        page = fh.read()
    _check('data-gzip="1"' in page and env.page_glb(page) == data, "the page does not hold the packed model")
    ctx.metric("file", len(data) / 1e6, "MB")
    browser = env.find_browser()
    if not browser:
        return f"{out['text']}; {pics}; no Edge or Chrome on this PC: the page was not opened"
    t = 0.9
    try:
        got = env.read_page(out["html"], browser, f"auto=0&frames=2&t={t}&places=1", seconds=90)
    except RuntimeError as exc:
        return f"{out['text']}; {pics}; {os.path.basename(browser)} gave no answer ({exc}); not counted"
    if got["state"].startswith("error") and re.search(r"webgl|context|swiftshader", got["state"], re.I):
        return f"{out['text']}; {pics}; no WebGL in the browser without a window; not counted"
    _check(not got["state"].startswith("error"), f"the page reports an error: {got['state']}")
    places = got.get("places") or {}
    _check(got["state"] != "loading", "the page gave no places of its parts: still loading after a second, longer "
                                      "opening")
    _check(places, f"the page gave no places of its parts ({got['state'][:60]})")
    n = node[slide.name]
    here = np.array(places[str(n)], np.float64)
    want = keys.played(*ch[(n, "rotation")], [t], "rotation")[0]
    _check(np.abs(here[3:7] - want).max() < 1e-4, "the page plays the packed turns differently from the app")
    return f"{out['text']}; keys within 0.1 mm / 0.05°; {pics}; the page unpacked and played it in " \
           f"{os.path.basename(browser)}{env.tries_note(got)}"


@line("web3d.film", "Web 3D model: Film – the video's camera on the page", "0.2.194",
      what="Task 0252: the crane with a built animation whose camera rides on the boom, flies a path watching the "
           "trolley (with a glide-in), cuts to a second camera and keeps the trolley in the middle, saved as a web 3D "
           "model with its animation and the three Film tick boxes on: the page's Film gives the app's Animation "
           "camera at every frame (within 1 mm per metre of the crane and 0.05°), holds the shot before the cut, and "
           "has the captions, the label and the cards; opened in Edge or Chrome without a window in the Film at a "
           "moment of the ride and halfway into the cut's frame, its camera is the app's (the cut jumps, never glides)")
def web3d_film(ctx):
    import bpy
    import numpy as np

    from ..blender import web3d, web3d_film as film_b
    from ..core import web3d_env as env
    from ..core import web3d_film as F
    scene = ctx.fresh(CRANE_A)
    film_b.set_up_test(scene)
    out = web3d.export(scene, os.path.join(ctx.work, "web3d", "Crane film.glb"), size=512, animation=True,
                       film_captions=True, film_labels=True, film_cards=True)
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    films = st.get("films") or []
    _check(len(films) == 1, "the page has no Film (the project has a built Animation camera)")
    film = films[0]
    _check(all(k in film for k in ("captions", "labels", "cards")), "the Film's captions, labels or cards are missing")
    cam = film_b.camera(scene)
    dg = bpy.context.evaluated_depsgraph_get()
    w, h = scene.render.resolution_x, scene.render.resolution_y
    mats, vfov = [], []
    for f in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(f)
        ev = cam.evaluated_get(dg)
        mats.append(np.array(ev.matrix_world))
        p = np.array(ev.calc_matrix_camera(dg, x=w, y=h, scale_x=1.0, scale_y=1.0))
        vfov.append(math.degrees(2 * math.atan(1.0 / p[1, 1])))
    scene.frame_set(scene.frame_start)
    pos, q = F.pose(np.array(mats))
    dec = F.decode(film)
    ep, ea, ev_ = F.errors(dec, pos, q, vfov)
    size = float(np.linalg.norm(np.subtract(st["model"]["max"], st["model"]["min"])))
    _check(ep <= 1e-3 * max(size, 1.0) and ea <= 0.05 and ev_ <= 0.05,
           f"the Film is {ep * 1000:.2f} mm / {ea:.3f}° / fov {ev_:.3f}° off the app's camera at a frame")
    cuts = film_b.cut_frames(scene)
    k = cuts[0] - scene.frame_start if cuts else -1
    _check(k > 0 and film["cut"] == [k], f"the cut is not in the Film ({film.get('cut')}, want {k})")
    text = (f"{dec['n']} frames, {len(dec['keys'])} kept, {F.size_bytes(film) / 1000:.1f} KB; worst {ep * 1000:.2f} mm, "
            f"{ea:.3f}°")
    ctx.metric("film", F.size_bytes(film) / 1000, "KB")
    browser = env.find_browser()
    if not browser:
        return f"{text}; no Edge or Chrome on this PC: the page was not opened"
    for frame, want in ((13, 13), (k - 0.5, k - 1)):
        query = f"auto=0&frames=2&film=1&paused=1&time={frame / dec['fps']:.6f}"
        try:
            got = env.read_page(out["html"], browser, query, seconds=90)
        except RuntimeError as exc:
            return f"{text}; {os.path.basename(browser)} gave no answer ({exc}); not counted"
        if got["state"].startswith("error") and re.search(r"webgl|context|swiftshader", got["state"], re.I):
            return f"{text}; no WebGL in the browser without a window; not counted"
        _check(not got["state"].startswith("error"), f"the page reports an error: {got['state']}")
        _check(got["state"] != "loading", "the page was still loading after a second, longer opening")
        fs = (got.get("player") or {}).get("film")
        _check(fs and fs.get("on"), f"the page did not open in the Film ({got['state'][:60]})")
        off = float(np.linalg.norm(np.array(fs["camPos"]) - pos[want]))
        ang = math.degrees(2 * math.acos(min(1.0, abs(float(np.dot(fs["camQuat"], q[want]))))))
        what = "at the ride" if want == 13 else "halfway into the cut's frame (the shot before must hold)"
        _check(off <= 1e-3 * max(size, 1.0) and ang <= 0.05,
               f"the page's camera {what} is {off * 1000:.1f} mm / {ang:.2f}° off the app's")
    return f"{text}; the page's camera is the app's at the ride and holds before the cut in {os.path.basename(browser)}"


def _player_check(page_path: str, ctx) -> str:
    """Task 0134: the page's player in this PC's Edge or Chrome without a window (software drawing): the settings
    menu, the keys help and the link work, Space pauses and plays a page with motion, and the page says it draws
    without the graphics card (a headless browser has none)."""
    from ..core import web3d as core
    from ..core import web3d_env as env
    browser = env.find_browser()
    if not browser:
        return "no Edge or Chrome on this PC: the player was not opened"
    # a page with motion: two plates, one moving (the test mill exports still)
    g = core.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.5, 0.5, 0.5, 1.0]}})
    import numpy as np
    pos = np.array([[-1, 0, -1], [1, 0, -1], [1, 0, 1], [-1, 0, 1]], float)
    mesh = g.mesh("p", pos, np.tile(np.array([[0, 127, 0]], np.int8), (4, 1)), None,
                  [(look, np.array([[0, 2, 1], [0, 3, 2]]))], quantize=False)
    g.node({"mesh": mesh})
    g.node({"mesh": mesh, "translation": [3.0, 0.0, 0.0]})
    t = np.linspace(0, 2, 5)
    g.animation("A", t, [(1, "translation", np.array([[3.0, 0.3 * np.sin(x), 0.0] for x in t]))])
    st = env.settings(env.default_choice(), [-1, -1, 0], [4, 1, 0.5], plain=True)
    moving = os.path.join(ctx.work, "web3d", "player check.html")
    with open(moving, "w", encoding="utf-8") as fh:
        fh.write(env.page_html("Player check", g.glb(), st, animated=True))
    found = []
    for path in (page_path, moving):
        got = None
        for _try in range(2):                   # a busy PC: the browser may stop before the page is ready
            try:
                got = env.read_page(path, browser, "selftest=1", seconds=90)
            except RuntimeError as exc:
                return f"{os.path.basename(browser)} gave no answer ({exc}); not counted"
            if got.get("selftest") or got["state"].startswith("error"):
                break
        if got["state"].startswith("error") and re.search(r"webgl|context|swiftshader", got["state"], re.I):
            return f"no WebGL in the browser without a window ({got['state'][:80]}); not counted"
        _check(not got["state"].startswith("error"), f"the page reports an error: {got['state']}")
        if not got.get("selftest"):
            return (f"the player gave no answer in {os.path.basename(browser)} without a window (page: "
                    f"{got['state'][:40]}); not counted")
        r = dict(got["selftest"], tools=got.get("tools"))
        _check(r.get("menu"), "the page's settings menu did not open")
        _check(r.get("help") and r.get("link"), "the page's keys help or its link to the view does not work")
        _check(r.get("flick"), "a quick flick did not set the page's model spinning (or a slow drag did, or a press "
                               "did not stop it)")
        found.append(r)
    _check(found[1].get("space") is True, "Space did not pause and play the page's motion")
    tools = found[0].get("tools") or {}                 # task 0135: the part tools on the exported page
    _check(tools.get("faces"), "the page has no faces for measuring (Faces for measuring is on by default)")
    _check(tools.get("ok"), f"the page's part tools did not work: {tools}")
    _check(tools.get("edges", 0) > 0, "the page has no edges for measuring (task 0219)")
    warned = found[0].get("warned")
    _check(bool(warned), "the page did not say it draws without the graphics card (a browser without a window "
                         "has none)")
    return (f"player: menu, keys help, link, Space pause, flick spin, 'no graphics card' bar ({warned}); part tools: card, measure, "
            f"fade, {tools.get('slices', 0)} slices, {tools.get('edges', 0)} edges, labels apart in "
            f"{os.path.basename(browser)}")


@line("web3d.moving", "Web 3D model: cables, ropes and coils move with their looks", "0.2.114",
      what="The spool test model (a winch drum and a carousel, a wire rope and a power cable) built and saved as a web "
           "3D model with its animation: the free cables, the rope on the drum and the coil on the carousel are drawn "
           "by the page with their looks and move as in the app (checked at three moments within 3 mm), the CAD "
           "coils the spools hide are left out; the page is opened in Edge or Chrome without a window")
def web3d_moving(ctx):
    import bpy
    import numpy as np

    from ..blender import animation, spool, web3d
    from ..core import web3d as core
    from ..core import web3d_env as env
    from ..core import web3d_tubes as T
    scene = ctx.fresh(SPOOL)
    made = spool.set_up_test_model(scene)
    animation.bake(scene, scene.fresing.animations[made["animation"]])
    scene.frame_set(scene.frame_start)
    job = web3d.Job(scene, os.path.join(ctx.work, "web3d", "Spools web 3D.glb"), size=512, animation=True)
    out = job.run()
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    _check(out["drawn"] == {"HIDDEN": 2, "TUBE": 2, "SPOOL": 2}, f"drawn parts read as {out['drawn']}")
    doc, binary = core.read_glb(data)
    node_ob = {node: ob for ob, node in job._nodes}
    specs = {node_ob[k].name: nd["extras"]["fr_tube"] for k, nd in enumerate(doc["nodes"])
             if (nd.get("extras") or {}).get("fr_tube")}
    _check(len(specs) == 4 and all(sp.get("look") for sp in specs.values()), "not every cable has its look on the page")
    fps = scene.render.fps / scene.render.fps_base
    worst = 0.0
    for f in (scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end - 1):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        for name, sp in specs.items():
            arr = {}
            for k in ("times", "lo", "step", "q", "n0", "s0", "trim_t", "trim", "trim_n0", "s", "slo", "sstep",
                      "nq", "pay_t", "pay"):
                if isinstance(sp.get(k), int) and not isinstance(sp.get(k), bool):
                    a = core.accessor_array(doc, binary, sp[k])
                    arr[k] = a.reshape(-1) if k in ("times", "step", "s0", "trim_t", "s", "slo", "sstep",
                                                    "pay_t", "pay") else a
            page = T.at(sp, arr, (f - scene.frame_start) / fps)
            me = bpy.data.objects[name].evaluated_get(dg).data
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            cen = co.reshape(-1, sp["sides"], 3).mean(axis=1)
            _check(len(cen) == len(page["points"]), f"'{name}' at frame {f}: {len(page['points'])} rings on the page, "
                                                    f"{len(cen)} in the app")
            worst = max(worst, float(np.linalg.norm(cen - page["points"], axis=1).max()))
    _check(worst < 0.003, f"a cable on the page is {worst * 1000:.1f} mm away from the app's")
    ctx.metric("export", out["seconds"], "s")
    ctx.metric("file", len(data) / 1e6, "MB")
    note = f"{out['text']}; 4 cables and ropes move with their looks, at most {worst * 1000:.1f} mm from the app"
    browser = env.find_browser()
    if browser and out.get("html"):
        try:
            got = env.read_page(out["html"], browser, "auto=0&frames=2&t=4&tubes=1", seconds=120)
        except RuntimeError as exc:
            return note + f"; the page gave no answer ({exc}); not counted"
        if got["state"].startswith("error") and re.search(r"webgl|context|swiftshader", got["state"], re.I):
            return note + "; no WebGL in the browser without a window: not counted"
        _check(not got["state"].startswith("error"), f"the page reports an error: {got['state']}")
        if got.get("tubes") is not None:
            _check(len(got["tubes"]) == 4, f"the page draws {len(got['tubes'])} cables (4 in the file)")
            note += "; the page draws all 4"
    return note


@line("web3d.under", "Web 3D model under the sea: seabed, cut-away, the camera under water", "0.2.129",
      what="The sea cable test model (a cable over a stern horn into 15 m of water) with the cut-away behind the stern "
           "and the ground in it, saved as a web 3D model with its animation and the sea: the page holds the seabed, "
           "the box where the app has it, the water's clarity, the soil section and the seabed's drift; opened in "
           "Edge or Chrome without a window, the page must show them, with 'Under the sea' and 'Camera under water' in "
           "its settings")
def web3d_under(ctx):
    from ..blender import animation, paths_sea, surroundings, web3d, web3d_env
    from ..core import web3d as core
    from ..core import web3d_env as env
    scene = ctx.fresh(SEA_CABLE)
    s = scene.fresing
    s.background, s.env_detail, s.sea_state, s.water_level = "SEA", "SIMPLE", "CALM", 2.0
    s.sea_depth = 15.0
    made = paths_sea.set_up_test_model(scene)
    s.sea_cutaway = True
    s.sea_cut_ground = True
    animation.bake(scene, s.animations[made["animation"]])
    s.web3d.env_mode = "PROJECT"
    ch = web3d_env.choice(scene)
    out = web3d.export(scene, os.path.join(ctx.work, "web3d", "Sea cable web 3D.glb"), size=512, surroundings=ch,
                       animation=True)
    with open(out["path"], "rb") as fh:
        bad = core.problems(fh.read())
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    u = st.get("under")
    _check(u is not None, "the page has no seabed although the project is on the open sea")
    box = surroundings.sea_cut_box(scene)
    _check(u["cut"] is not None and box is not None, "the page has no cut-away box")
    off = max(abs(u["cut"]["origin"][i] - box["origin"][i]) for i in (0, 1))
    _check(off < 0.01 and abs(u["cut"]["length"] - box["length"]) < 0.01,
           f"the page's box is {off:.2f} m from the app's, {u['cut']['length']:.1f} m long ({box['length']:.1f} m)")
    _check(abs(u["clarity"] - s.sea_clarity) < 1e-4, f"the page's clarity is {u['clarity']} m ({s.sea_clarity:.1f} m)")
    _check(u["ground"] is not None, "the page has no soil section in the cut-away")
    _check(u["motion"] is not None, "the page's seabed does not drift while the cable pays out")
    ctx.metric("export", out["seconds"], "s")
    note = (f"{out['text']}; on the page: {out.get('env_items', '')}; box {u['cut']['length']:.0f} x "
            f"{u['cut']['width']:.0f} m, clarity {u['clarity']:.0f} m, soil {u['ground']['depth']:.0f} m deep")
    browser = env.find_browser()
    if not browser:
        return note + "; no Edge or Chrome on this PC: the page itself was not opened"
    try:
        got = env.read_page(out["html"], browser, "auto=0&frames=3&t=4", seconds=120)
    except RuntimeError as exc:
        return note + f"; the page gave no answer ({exc}); not counted"
    if got["state"].startswith("error") and re.search(r"webgl|context|swiftshader", got["state"], re.I):
        return note + "; no WebGL in the browser without a window: not counted"
    _check(not got["state"].startswith("error"), f"the page reports an error: {got['state']}")
    pl = got.get("player") or {}
    under = pl.get("under") or {}
    _check(got["state"] != "loading", "the page was still loading after a second, longer opening")
    _check(under.get("under") and under.get("cut") and under.get("ground") and under.get("dive"),
           f"the page does not show the seabed, the box, the soil or the camera under water: {under}")
    _check("under" in (pl.get("items") or []) and "dive" in (pl.get("items") or []),
           "the page's settings have no 'Under the sea' or 'Camera under water'")
    return note + "; the page shows them (Under the sea and Camera under water in its settings)" + env.tries_note(got)


@line("web3d.bake", "Web 3D model with baked light", "0.2.89",
      what="The test mill saved as a web 3D model with Light: Soft light baked, sun live (Bake quality Draft): Cycles "
           "bakes the light on this PC's graphics card when it renders with one; every shown part gets its own baked "
           "light; the file is checked against the glTF rules and read back by Blender")
def web3d_bake(ctx):
    from ..blender import build, web3d
    from ..core import web3d as core
    from ..core import web3d_env as env
    scene = ctx.fresh(MILL)
    shown = len([p for p in build.iter_parts(scene) if p.visible_get()])
    out = web3d.export(scene, os.path.join(ctx.work, "web3d", "Test mill baked light.glb"), size=512, light="SOFT",
                       light_quality="DRAFT")
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    doc, _bin = core.read_glb(data)
    lit = 0
    for n in doc["nodes"]:
        if not n.get("name", "").startswith("Part "):
            continue
        mesh = n.get("mesh")
        if mesh is None:
            mesh = next((doc["nodes"][c]["mesh"] for c in n.get("children", []) if "mesh" in doc["nodes"][c]), None)
        attrs = doc["meshes"][mesh]["primitives"][0]["attributes"] if mesh is not None else {}
        lit += "TEXCOORD_1" in attrs or "_FR_LIGHT" in attrs
    _check(lit == shown, f"{lit} of {shown} parts carry baked light")
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    _check((st.get("light") or {}).get("light") == "SOFT", "the page does not use the baked light")
    got = _gltf_triangles(out["path"])
    _check(got == core.summary(data)["triangles"], "Blender's glTF importer did not read every triangle back")
    ctx.metric("bake", out["light_seconds"], "s")
    ctx.metric("light", out["light_bytes"] / 1e6, "MB")
    return out["text"]


def _gltf_triangles(path: str) -> int:
    """Triangles Blender's own glTF importer reads from ``path`` (into a scene of its own, removed again)."""
    import addon_utils
    import bpy
    addon_utils.enable("io_scene_gltf2", default_set=True)
    keep = bpy.context.window.scene if bpy.context.window else None
    sc = bpy.data.scenes.new("FR glTF read back")
    try:
        with bpy.context.temp_override(scene=sc):
            if bpy.context.window:
                bpy.context.window.scene = sc
            bpy.ops.import_scene.gltf(filepath=path)
        obs = [o for o in sc.objects if o.type == "MESH"]
        return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in obs)
    finally:
        if keep is not None:
            bpy.context.window.scene = keep
        meshes = {o.data for o in sc.objects if o.type == "MESH"}
        for o in list(sc.objects):
            bpy.data.objects.remove(o)
        for me in meshes:
            if me.users == 0:
                bpy.data.meshes.remove(me)
        bpy.data.scenes.remove(sc)


@line("web3d.surroundings", "Web 3D model with its surroundings", "0.2.86",
      what="The crane on the Vessel deck in a rough sea with vessel motion, exported with every surroundings item "
           "on (sea, vessel motion, sky with clouds, haze, rain and spray, sun shadows); the page's settings read "
           "back and checked against the project, then the page opened without a window in Edge or Chrome when the "
           "PC has one (software drawing): it must report no error")
def web3d_surroundings(ctx):
    from ..blender import web3d, web3d_env, world
    from ..core import web3d as core
    from ..core import web3d_env as env
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.background = "DECK"
    s.sea_state = "ROUGH"
    s.vessel.enabled = True
    world.apply(scene, s)
    w = s.web3d
    w.env_mode = "PROJECT"
    web3d_env.fill_from_project(scene)
    w.env_clouds = "SOME"
    w.env_haze = w.env_rain = w.env_shadows = True
    ch = web3d_env.choice(scene)
    _check(ch["sea"] and ch["vessel"], "the fold did not take the sea and vessel motion from the project")
    out = web3d.export(scene, os.path.join(ctx.work, "web3d", "Crane at sea web 3D.glb"), size=512, surroundings=ch)
    with open(out["path"], "rb") as fh:
        bad = core.problems(fh.read())
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    with open(out["html"], encoding="utf-8") as fh:
        page = fh.read()
    st = env.page_settings(page)
    _check(st["sea"] and st["sea"]["state"] == "ROUGH" and st["vessel"], "the page has no rough sea or no vessel motion")
    _check(st["haze"] and st["rain"] and st["rain"]["spray"] and st["shadows"], "haze, rain, spray or shadows are off")
    _check(st["sky"]["clouds"] == "SOME", "the page's sky has no clouds")
    _check("FRTHREE" in page and "FRMath" in page and "https://" not in page.split('id="fr-env"')[0],
           "the page's code is not inside it (it would need the internet)")
    ctx.metric("export", out["seconds"], "s")
    ctx.metric("page", os.path.getsize(out["html"]) / 1e6, "MB")
    note = "no Edge or Chrome on this PC: the page itself was not opened"
    browser = env.find_browser()
    if browser:
        t0 = time.perf_counter()
        try:
            state = env.open_headless(out["html"], browser, seconds=45)
        except RuntimeError as exc:
            state = f"no answer ({exc})"
        if state.startswith("error") and re.search(r"webgl|context|swiftshader", state, re.I):
            state = f"no WebGL in the browser without a window ({state[:80]})"      # the browser's, not the page's
        _check(not state.startswith("error"), f"the page reports an error in {os.path.basename(browser)}: {state}")
        if state.startswith("ready"):
            ctx.metric("browser", time.perf_counter() - t0, "s")
            note = f"opened without a window in {os.path.basename(browser)}: {state}"
        else:
            note = f"{os.path.basename(browser)} gave no answer in time ({state}); not counted"
    return f"{out['text']}; on the page: {out.get('env_items', '')}; {note}"


@line("scene.vessel_motion", "Vessel motion at sea", "0.2.65",
      what="The crane on the Vessel deck in a calm beam sea: the deck and the crane heave, pitch and roll, the sea "
           "and the camera stay. Amplitudes measured over 2 minutes; a frame rendered small (processor, draft)")
def scene_vessel_motion(ctx):
    import math

    import bpy

    from ..blender import surroundings, vessel_motion
    from ..core import vessel_motion as vcore
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.env_detail = "SIMPLE"
    s.background = "DECK"
    s.sea_state = "CALM"
    s.vessel.heading = "BEAM"
    s.vessel.enabled = True
    _check(surroundings.root_object() is not None, "the vessel deck was not built")
    piv = vessel_motion.rig("pivot")
    _check(piv is not None, "vessel motion did not set itself up")
    p = vessel_motion.pivot(scene)
    sea = next((o for o in scene.objects if o.get(surroundings.TAG) == "sea"), None)
    _check(sea is not None and not sea.constraints, "the sea moves with the vessel")
    roll, pitch, heave = [], [], []
    t0 = time.time()
    n = 0
    for f in range(0, int(120 * scene.render.fps), 4):         # 2 minutes, every 4th frame
        scene.frame_set(f)
        mw = piv.matrix_world
        e = mw.to_3x3().to_euler("XYZ")
        roll.append(e.x)
        pitch.append(e.y)
        heave.append((mw @ p).z - p.z)
        n += 1
    ctx.metric("frame change with vessel motion", (time.time() - t0) / max(n, 1) * 1000, "ms")
    dt = 4 / scene.render.fps
    r, q, h = math.degrees(vcore.peak(roll)), math.degrees(vcore.peak(pitch)), vcore.peak(heave)
    rs = vcore.mean_period(roll, dt)
    ctx.metric("roll", r, "deg")
    ctx.metric("pitch", q, "deg")
    ctx.metric("heave", h, "m")
    _check(1.0 <= r <= 2.0 and 9.0 <= rs <= 13.0, f"roll ±{r:.2f}° every {rs:.1f} s is not a calm beam sea")
    _check(q < r and 0.05 <= h <= 0.5, f"pitch ±{q:.2f}°, heave ±{h:.2f} m: not a calm sea")
    scene.frame_set(int(5.5 * scene.render.fps))                 # the vessel well over to one side
    bpy.context.view_layer.update()
    _small_output(s)
    info = _cpu_still(ctx, scene, "vessel", "Vessel deck, rolling (processor, draft)", model_check=False)
    return (f"roll ±{r:.1f}° every {rs:.0f} s, pitch ±{q:.2f}°, heave ±{h:.2f} m; rendered in {info['seconds']} s")


@line("scene.vessel_work", "Vessel at work: wake, waves, thruster jets", "0.2.127",
      what="A workboat with two azimuths and a bow thruster (test model) on the open sea: sailing ahead at 8 knots "
           "(a wake, the waves 19.5° each side, a bow wave), then pushed sideways (the azimuths steer round, white "
           "jets beside the hull); the propellers' keys after Build. Both rendered small (processor, draft): judge "
           "the white trail behind the stern and the jets streaming out on one side")
def scene_vessel_work(ctx):
    import math

    import bpy

    from ..blender import animation, joints, vessel_work
    from ..core import vessel_work as vw_core
    scene = ctx.fresh(os.path.join(DATA, "test_thrusters.step"))
    s = scene.fresing
    t0 = time.time()
    vessel_work.set_up_test_model(scene)
    ctx.metric("set up (sea with the vessel's water)", time.time() - t0, "s")
    rows = list(s.vessel_work.thrusters)
    _check([r.kind for r in rows] == ["AZIMUTH", "AZIMUTH", "TUNNEL"],
           f"Find thrusters found {', '.join(r.kind.lower() for r in rows) or 'nothing'}, not two azimuths and a tunnel")
    _check(vessel_work.stored_layout(scene) is not None, "the sea was built without the vessel's water")
    from mathutils import Matrix, Vector
    cam = bpy.data.objects.new("PC check vessel", bpy.data.cameras.new("PC check vessel"))
    scene.collection.objects.link(cam)
    at, look = Vector((-45.0, -50.0, 40.0)), Vector((5.0, 0.0, -3.0))
    cam.matrix_world = Matrix.Translation(at) @ (look - at).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    cam.data.lens, cam.data.clip_end = 28.0, 5000.0
    scene.camera = cam
    _small_output(s)
    a = _cpu_still(ctx, scene, "vessel_ahead", "Vessel at work: ahead 8 knots (processor, draft)", model_check=False)
    s.vessel_work.side, s.vessel_work.thrust, s.vessel_work.mode = "STBD", 0.7, "DP"
    steer = joints.get_value(joints.find(scene, rows[0].steer))
    _check(abs(steer + math.pi / 2) < 1e-3, f"the azimuth steered to {math.degrees(steer):.0f}°, not -90°")
    b = _cpu_still(ctx, scene, "vessel_dp", "Vessel at work: sideways (processor, draft)", model_check=False)
    # Build: a step from ahead to sideways; the propellers get keys
    s.vessel_work.mode = "AHEAD"
    anim = s.animations.add()
    anim.name, anim.tail = "PC check vessel", 0.0
    blk = anim.blocks.add()
    blk.kind, blk.start, blk.duration, blk.vw_mode, blk.vw_thrust = "VESSEL", 1.0, 2.0, "DP", 0.7
    t0 = time.time()
    r = animation.bake(scene, anim)
    ctx.metric("build", time.time() - t0, "s")
    _check(not [w for w in r["warnings"] if "Vessel" in w], "; ".join(r["warnings"]))
    tun = joints.find(scene, rows[2].joint)
    vals = []
    for f in (scene.frame_start, scene.frame_end):
        scene.frame_set(f)
        vals.append((float(scene.get(vw_core.prop("ahead"), -1)), joints.get_value(tun)))
    _check(abs(vals[0][0] - 8.0) < 1e-3 and vals[1][0] == 0.0, "the speed's keys do not go from 8 knots to 0")
    _check(abs(vals[1][1] - vals[0][1]) > 1.0, "the bow thruster's propeller does not turn")
    animation.clear_keys(scene)
    return f"ahead rendered in {a['seconds']} s, sideways in {b['seconds']} s; azimuths steer to -90°"


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


@line("scene.props", "Props for scale and people in detail", "0.2.124",
      what="Every prop beside the crane and three people in other poses and clothes (task 0155): all on the floor, "
           "detailed near the camera and light far away, rendered small (processor, draft)")
def scene_props(ctx):
    import bpy

    from ..blender import cameras, props_scale
    scene = ctx.fresh(CRANE_A)
    t0 = time.time()
    obs = props_scale.line_up(scene)
    ctx.metric("add every prop and three people", time.time() - t0, "s")
    cameras.add_camera(scene, "ISO", 50.0, "PC check props", points=props_scale.corners(obs))
    words = props_scale.check_line_up(scene)
    cam = scene.camera
    far = cam.location.copy()
    cam.location = obs[0].matrix_world.translation + (cam.location - obs[0].matrix_world.translation).normalized() * (
        scene.fresing.props_far + 10.0)
    bpy.context.view_layer.update()
    _check(props_scale.visible_level(obs[0]) == "LIGHT", "a person far from the camera still shows its detailed version")
    cam.location = far
    bpy.context.view_layer.update()
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "props", "Props for scale and people (processor, draft)", model_check=False)
    return f"{words}; render {info['seconds']} s"


@line("toolchange.person", "A person changes the tool", "0.2.132",
      what="The test mill in its enclosure (task 0156; task 0249: the larger VMC): the operator walks up before the "
           "tool change, opens the sliding doors, takes T1 out, lays it on the trolley, puts T2 in, closes the doors "
           "and walks away. Build, the pause "
           "grown to what the person needs, the hand on the holder, the frame time, a small render (processor, draft)")
def toolchange_person(ctx):
    import bpy
    import numpy as np

    from ..blender import animation, cameras, gcode, tc_person
    from ..core import gcode as core
    from ..core import toolchange as TC
    scene = ctx.fresh(MILL_CABINET)
    a = tc_person.set_up_test_model(scene, os.path.join(ctx.work, "pccheck_operator.ngc"))
    t0 = time.time()
    res = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not res["warnings"], "Build warned: " + "; ".join(res["warnings"][:3]))
    words = tc_person.check_test_model(scene)
    scene.frame_set(1)
    b = a.blocks[0]
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, b, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, b, mach))
    c = next((x for x in sch.changes if x.person), None)
    _check(c is not None, "no tool change done by the person")
    _check(c.hand[1] >= TC.person_min(c.door) - 1e-6, f"the pause is {c.hand[1]:.1f} s, shorter than the person "
           f"needs ({TC.person_min(c.door):.1f} s)")
    keys = {n: (x, y) for x, y, n in TC.person_keys(*c.hand, c.door)}
    f_grip = 1 + keys["grip"][1] * 25.0
    scene.frame_set(int(round(f_grip)))
    op = tc_person.operator(scene)
    from ..blender import person_rig
    hand = person_rig.bone_world(op, "r_hand").translation
    spindle = mach.tool
    tip = tc_person._world(spindle) @ gcode.tool_frame(spindle).translation
    d = float(np.hypot(hand.x - tip.x, hand.y - tip.y))
    _check(d < 0.15, f"the right hand is {d * 100:.0f} cm beside the tool at the grip")
    t0 = time.time()
    n = 40
    for f in range(int(f_grip) - 20, int(f_grip) + 20):
        scene.frame_set(f)
    ctx.metric("frame time with the operator", (time.time() - t0) / n * 1000.0, "ms")
    cameras.add_camera(scene, "ISO", 40.0, "PC check operator", points=tc_person.test_camera_points())
    scene.frame_set(int(f_grip))
    bpy.context.view_layer.update()
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "operator", "The operator takes the tool out (processor, draft)",
                      model_check=False)
    return f"{words}; render {info['seconds']} s"


@line("people.walk", "People walk, carry and meet", "0.2.128",
      what="Two people beside the crane (task 0157): Anna walks in with a toolbox, puts it down, they shake hands "
           "and talk. Build, feet on the floor without sliding, the box on the floor, the frame time with them, a "
           "small render (processor, draft)")
def people_walk(ctx):
    import bpy

    from ..blender import animation, cameras, people
    scene = ctx.fresh(CRANE_A)
    t0 = time.time()
    people.set_up_example(scene)
    ctx.metric("add two people with their steps", time.time() - t0, "s")
    a = scene.fresing.animations.add()
    a.name, a.tail = "People", 0.0
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    t0 = time.time()
    res = animation.bake(scene, a)
    ctx.metric("build", time.time() - t0, "s")
    _check(not res["warnings"], "Build warned: " + "; ".join(res["warnings"]))
    words = people.check_example(scene)
    t0 = time.time()
    n = min(scene.frame_end, 60)
    for f in range(1, n + 1):
        scene.frame_set(f)
    ctx.metric("frame time with two people", (time.time() - t0) / n * 1000.0, "ms")
    cameras.add_camera(scene, "ISO", 50.0, "PC check people", points=people.example_corners(scene))
    scene.frame_set(int(scene.frame_end * 0.55))
    bpy.context.view_layer.update()
    _small_output(scene.fresing)
    info = _cpu_still(ctx, scene, "people", "People meet (processor, draft)", model_check=False)
    return f"{words}; render {info['seconds']} s"


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


@line("scene.render_view", "Render this view", "0.2.223",
      what="Render this view from a set view of the crane matches Render image from a camera at the same place; no "
           "camera is left behind")
def scene_render_view(ctx):
    import bpy
    import numpy as np

    from ..blender import ops_render_view, render
    scene = ctx.fresh(CRANE_A)
    s = scene.fresing
    s.use_gpu = False
    _small_output(s, 160, 90)
    bpy.ops.fresing.camera_add(view="HIGH")                # a perspective view (the isometric one is orthographic)
    _update()
    shot = scene.camera
    _check(shot is not None, "no camera for the comparison")
    before = (scene.camera, len(bpy.data.objects), len(bpy.data.cameras))
    by_camera = os.path.join(ctx.work, "render_view_camera.png")
    render.render_still(scene, s, "draft", filepath=by_camera)
    state = ops_render_view.setup(scene, bpy.context, view=ops_render_view.stand_in(shot, 160 / 90))
    try:
        _check(scene.camera != shot and scene.camera.get(ops_render_view.VIEW_MARK), "no view camera was made")
        by_view = render.view_output_path(scene, s)
        t0 = time.time()
        render.render_still(scene, s, "draft", filepath=by_view)
        seconds = round(time.time() - t0, 1)
    finally:
        ops_render_view.undo(scene, state)
    _check((scene.camera, len(bpy.data.objects), len(bpy.data.cameras)) == before,
           "Render this view left a camera behind or changed the active camera")
    _check("_View_" in os.path.basename(by_view), f"the file is called {os.path.basename(by_view)}")

    def pixels(path):
        img = bpy.data.images.load(path)
        px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
        img.pixels.foreach_get(px)
        bpy.data.images.remove(img)
        return px
    a, b = pixels(by_camera), pixels(by_view)
    diff = float(np.abs(a - b).max()) if a.shape == b.shape else 1.0
    _check(a.shape == b.shape and diff < 0.05,
           f"Render this view differs from Render image from the same place (largest difference {diff:.3f})")
    ctx.picture(by_view, "render_view", "Render this view (processor, draft) – the same as from the camera")
    return f"same picture as from the camera (difference {diff:.3f}); {seconds} s"


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
    # task 0176: the Fresing logo as the watermark, tiled across the picture and in the centre
    s.wm_kind, s.wm_opacity, s.wm_tint, s.wm_size = "FRESING_LOGO", 1.0, "WHITE", 0.1
    logos = {}
    for place in ("TILED", "CENTRE"):
        s.wm_place = place
        job = {"id": f"pcl{place}", "kind": "STILL", "shot": "", "camera": "", "quality": "draft",
               "out_dir": os.path.join(ctx.work, "finishing"), "label": "PC check", "watermark": True}
        logos[place] = runner.read_pixels(queue.run_job(scene, job, lambda *a: None, lambda: False))
    for place, pic in logos.items():
        _check(float(np.abs(pic - a)[centre].max()) > 0.06, f"the Fresing logo ({place.lower()}) is not on the picture")
    edge = (slice(0, h // 5), slice(0, w // 5))
    _check(float(np.abs(logos["TILED"] - a)[edge].max()) > 0.06, "the tiled logo does not reach the corner")
    _check(float(np.abs(logos["CENTRE"] - a)[edge].max()) < 0.02, "the centre logo is in the corner")
    ctx.picture_pixels(logos["TILED"], "finishing_logo", "Fresing logo watermark, tiled (processor, draft)")
    return "logo, watermark words and the Fresing logo watermark on the picture"


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
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
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
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
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
           "before; the spindle speed sets the splash (task 0257: rim speed, a film on a slow tool, the jets turned "
           "away at speed); the time per frame with and without coolant and a Cycles picture of the flood")
def milling_coolant(ctx):
    import bpy
    import numpy as np
    from mathutils import Vector

    from ..blender import animation, coolant, gcode, joints, machining
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
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
    # task 0257: the spindle's speed (S9000) is read per frame and sets the look
    from ..core import coolant as core
    rpm = coolant.rpm_at(root, mid)
    _check(rpm == 9000, f"the coolant reads {rpm} rpm at the middle of the flood, not the program's 9000")
    _z, radius = coolant._tool_at(scene, root, mid)
    v = core.rim_speed(rpm, radius)
    _check(4.0 < v < 5.5, f"the D10 at 9000 rpm turns at {v:.2f} m/s at its rim, not about 4.7")
    flow = scene.fresing.coolant.flow
    on1 = lambda t: np.ones_like(np.asarray(t, float))       # noqa: E731
    g = np.array([0.0, 0.0, -core.G])
    slow = core.splash(np.zeros(3), radius, 0.008, 300.0, 25.0, on1, flow, g, rpm=1000)
    fast = core.splash(np.zeros(3), radius, 0.008, 300.0, 25.0, on1, flow, g, rpm=15000)
    film = int((np.linalg.norm(slow.drops[:, :2], axis=1) < radius + 1.2 * core.MM).sum())
    _check(film > 30, f"at 1000 rpm only {film} drops lie on the tool: no film")
    _check(np.median(fast.sizes) < 0.5 * np.median(slow.sizes), "the fast tool's drops are not finer")
    share = core.deflect_share(core.rim_speed(15000, radius), flow)
    _check(share > 0.1 and core.deflect_share(v, flow) == 0.0,
           f"the air layer turns away {share:.0%} at 15000 rpm (expected some) and "
           f"{core.deflect_share(v, flow):.0%} at 9000 (expected none)")
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
            f"{n_wet} wet parts; {v:.1f} m/s at the rim, {film} film drops at 1000 rpm, {share:.0%} of the jets "
            f"turned away at 15000; {off:.0f} / {on:.0f} ms per frame without / with coolant")


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
      what="The test mill runs a program with a tool change: a Ø50 face mill on a BT40 arbor faces a strip 1 mm deep, "
           "then a Ø6 drill in a BT40 chuck (25 mm longer, tip to gauge line) drills a hole 8 mm deep; both are read "
           "back from the milled block, with the length offset and the time per frame")
def milling_tools(ctx):
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from ..blender import animation, gcode, joints, machining, tools
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
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
    face.length, face.holder, face.holder_length = 0.04, "BT40", 0.045      # an arbor (task 0049; BT40: task 0249)
    drill = tools.add_row(scene, "DRILL", 2)
    drill.diameter = 0.006
    drill.length, drill.holder, drill.holder_length = 0.05, "BT40", 0.06    # in a chuck: 25 mm longer
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
    return (f"face mill 1.00 → {d_face:.2f} mm, drill 8.00 → {d_drill:.2f} mm, BT40 length offset 25.00 → "
            f"{lift:.2f} mm; {per:.0f} ms per frame")


@line("milling.marks", "Milling: tool marks on the cut faces", "0.2.73",
      what="The test mill runs the test tour's three-tool program: a Ø50 face mill faces a strip, a Ø10 end mill "
           "cuts a pocket in two depths, a drill makes a hole. Every cut face must know the tool that made it "
           "(arcs on the floors, lines on the walls, rings in the hole; the face mill's arcs as far apart as the "
           "program's feed and speed say) and the cut faces' material must draw the marks; the Tool marks tick takes "
           "them off and puts them back. A close-up of the cut (processor, draft) and the time to rebuild the "
           "milled block for a frame, with and without marks")
def milling_marks(ctx):
    import statistics

    from ..blender import animation, machining, render, toolmarks, tour
    from ..core import toolmarks as tm
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    tour.build_marks(tour.Build(scene, ctx.work, "pccheck"))
    a = scene.fresing.animations.get(tour.MARKS_ANIM)
    _check(a is not None, "the animation with the program is missing")
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    frames = r["frames"]
    machining.sample(scene)
    note = tour._check_marks(scene)          # arcs, lines and rings are there; the face mill's arcs are F / S apart
    source = machining.marks_source(scene)
    _check("program" in source and not source.startswith("No program"),
           f"the Milling panel does not say the marks come from the program: '{source}'")
    m = machining.settings(scene)
    stock = _ob(scene, "STOCK 200x200x40")

    def has_marks():
        """(the milled mesh knows the moves, the cut faces' material draws marks) as they are now."""
        me = m.cut_mesh
        n = int(me.get(machining.CUT_SLOT, -1))
        _check(0 < n < len(stock.material_slots), "the milled block has no material slot for cut faces")
        return (all(k in me.attributes for k in tm.ATTRS),
                toolmarks.group_node(stock.material_slots[n].material) is not None)

    def rebuild():
        """Median time to write the milled block again for a frame, ms (six frames across the program, each
        three times)."""
        shown = sorted({max(1, round(frames * k / 8)) for k in range(3, 9)})
        for f in shown:                                      # once without the clock: every cut is worked out
            machining.refresh(scene, frame=f, force=True)
        times = []
        for f in shown * 3:
            t1 = time.perf_counter()
            _check(machining.refresh(scene, frame=f, force=True), machining.status(scene) or "no milled block")
            times.append((time.perf_counter() - t1) * 1000.0)
        return statistics.median(times)

    _check(has_marks() == (True, True), "the cut faces have no tool marks although Tool marks is ticked")
    with_marks = rebuild()
    m.marks = False
    _check(has_marks() == (False, False), "Tool marks is switched off, but the cut faces still carry the marks")
    without = rebuild()
    m.marks = True
    _check(has_marks() == (True, True), "Tool marks switched on again did not bring the marks back")
    ctx.metric("rebuild with marks", with_marks, "ms")
    ctx.metric("rebuild without marks", without, "ms")
    # the picture: the tour stop's close-up of the faced strip, the pocket and the hole at the end of the program
    scene.frame_set(scene.frame_end)
    machining.refresh(scene, force=True)
    s = scene.fresing
    s.use_gpu = False
    s.out_resolution = "preview"
    path = os.path.join(ctx.work, "marks.png")
    info = render.render_still(scene, s, "draft", filepath=path)
    ctx.picture(path, "marks", f"Tool marks: faced strip, pocket, drilled hole; drawn x{m.marks_size:g} "
                               "(processor, draft)", model_check=False, width=480)
    ctx.metric("still with marks", info["seconds"], "s")
    return f"{note}; rebuilt in {with_marks:.0f} ms per frame ({without:.0f} ms without marks)"


@line("milling.shows_program", "Milling: the block shows what the program does", "0.2.171",
      what="The test gantry runs the test tour's G-code program (a 2 mm slot with an arc, a tool change, two drilled "
           "holes) with Milling using the CNC machine's tool and workpiece. Every cut face must have tool marks and "
           "every move through the block must take material away (the tool's tip, 0.3 mm up its axis, tested every "
           "0.5 mm along the program); the block is painted, as imported, so its cuts must show bare machined metal. "
           "Then Milling is taken off: the check must find the program running through a block nothing cuts, and Use "
           "the CNC machine's tool and workpiece must put it right")
def milling_shows_program(ctx):
    from ..blender import animation, machining, tour
    machining._RUNTIME.clear()
    scene = ctx.fresh(GANTRY)
    tour.build_gantry(tour.Build(scene, ctx.work, "pccheck"))
    a = scene.fresing.animations.get("G-code")
    _check(a is not None, "the animation with the program is missing")
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    t0 = time.time()
    note = tour.check_milling(scene)
    ctx.metric("check", time.time() - t0, "s")
    mat = machining.cut_material(scene, machining.workpiece(scene))
    _check(mat is not None and mat.get("fr_material") == "aluminium_machined",
           f"the painted block's cuts show '{mat.name if mat else 'its paint'}', not bare machined aluminium")
    machining.stop(scene)                             # Milling off: the program still runs through the block
    _check(machining.cnc_unused(scene), "the panels do not offer Use the CNC tool and workpiece")
    a_ = machining.audit(scene)
    _check(a_.get("through", 0) > 0, "the program runs through the block that nothing cuts, but the check does not "
                                     "find it")
    why = machining.use_cnc(scene)
    _check(not why, why)
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    tour.check_milling(scene)
    return note + f"; without Milling: {a_['through']} points of the program inside the uncut block found"


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


def _finish_depth(x: float, y: float) -> float:
    """How deep (mm, below the block's top) the finishing program of ``_finish_scene`` runs at (x, y) mm."""
    return 2.0 + 0.8 * math.sin(x / 9.0) * math.cos(y / 7.0)


def _finish_scene(ctx, xs, ys, seconds: float = 6.0):
    """The test mill with a finishing program as a user would run it (task 0146): T1, a Ø10 ball (the part in the
    spindle, with the tool list's sizes), follows a wavy surface 1.2 to 2.8 mm deep in a zigzag over the points
    ``xs`` x ``ys`` (mm from the work zero, the middle of the block's top). A G-code step fitted into ``seconds``
    of video (milling reads the bit's path frame by frame: a frame should not hold hundreds of moves), built;
    milling is set up. Returns (scene, frames, block)."""
    import bpy
    from mathutils import Vector

    from ..blender import animation, gcode, joints, machining, tools
    from ..core import machining as core
    if not core.available():
        raise RuntimeError("the Manifold library did not load: run Install.bat again")
    machining._RUNTIME.clear()
    scene = ctx.fresh(MILL)
    for name, asm, d in (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
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
    tools.use_part(scene, tools.add_row(scene, "BALL", 1), tool)
    ball = tools.row_of(scene, 1)                   # (Use part reads the part's own shape, a flat end mill:
    ball.kind = "BALL"                              # the owner then picks the type and types the sizes)
    ball.diameter, ball.length, ball.flute_length = 0.010, 0.040, 0.025
    rows = ["(FINISHING RASTER)", "G21 G90 G94 G17 G54", "T1 M6", "S12000 M3",
            f"G0 X{xs[0]:.3f} Y{ys[0]:.3f} Z5", f"G1 Z{-_finish_depth(xs[0], ys[0]):.4f} F1200"]
    for k, y in enumerate(ys):
        for x in (xs if k % 2 == 0 else xs[::-1]):
            rows.append(f"G1 X{x:.3f} Y{y:.3f} Z{-_finish_depth(x, y):.4f}")
    rows += ["G0 Z10", "M5", "M30", ""]
    path = os.path.join(ctx.work, "pccheck_finish.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(rows))
    a = scene.fresing.animations.add()
    a.name, a.tail = "Finish", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_path = "FIT", float(seconds), False
    b.gcode_file = path
    gcode.step_changed(scene, b)
    r = animation.bake(scene, a)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    return scene, r["frames"], stock


def _top_of(scene, stock):
    """A function (x, y in mm from the work zero) -> how deep the milled block's top lies there, in mm below the
    work zero (the middle of the block's uncut top)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from ..blender import gcode
    me, mw = stock.data, stock.matrix_world
    bvh = BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons])
    zero = gcode.settings(scene).zero_empty.matrix_world.translation.copy()

    def depth(x, y):
        hit = bvh.ray_cast(zero + Vector((x * 0.001, y * 0.001, 0.1)), Vector((0, 0, -1)))
        _check(hit[0] is not None, f"nothing under ({x:.1f}, {y:.1f}) mm")
        return (zero.z - hit[0].z) * 1000.0
    return depth


@line("milling.fast_map", "Milling: a long finishing program as a height map", "0.2.117",
      what="The test mill runs a finishing program of 1,500 short moves (a Ø10 ball follows a wavy surface, passes "
           "0.5 mm apart). "
           "The block is worked out as a height map (Fast 3-axis passes, on by itself) and, for comparison, with an "
           "exact cut per move: both must show the same surface, at the depth the program says. The time and the "
           "number of faces of both")
def milling_fast_map(ctx):
    from ..blender import machining
    xs = [-30.0 + 1.0 * k for k in range(61)]
    ys = [-6.0 + 0.5 * k for k in range(25)]      # (0.6 mm apart was just below the map's density limit, task 0249)
    scene, frames, stock = _finish_scene(ctx, xs, ys)
    machining.sample(scene)
    m = machining.settings(scene)
    _check(m.fast_map, "Fast 3-axis passes is not on in a new project")
    probes = [(xs[i], ys[j]) for i in (6, 18, 30, 42, 54) for j in (3, 10, 17)]
    got = {}
    for fast in (True, False):
        m.fast_map = fast
        t0 = time.time()
        _check(machining.refresh(scene, frame=float(frames), force=True),
               machining.status(scene) or "the block does not show its cut")
        seconds = time.time() - t0
        used = "height map" in machining.status(scene)
        _check(used == fast, ("the long program was not worked out as a height map" if fast else
                              "Fast 3-axis passes is off, but the height map was still used")
               + f": '{machining.status(scene)}'")
        depth = _top_of(scene, stock)
        got[fast] = (seconds, len(stock.data.polygons), [depth(x, y) for x, y in probes])
    m.fast_map = True
    ctx.metric("height map", got[True][0], "s")
    ctx.metric("exact cuts", got[False][0], "s")
    ctx.metric("faces, height map", got[True][1], "")
    ctx.metric("faces, exact", got[False][1], "")
    apart = max(abs(a - b) for a, b in zip(got[True][2], got[False][2]))
    _check(apart < 0.03, f"the height map and the exact cut are {apart:.3f} mm apart (more than 0.03 mm)")
    off = max(abs(d - _finish_depth(x, y)) for d, (x, y) in zip(got[True][2], probes))
    _check(off < 0.05, f"the cut is {off:.3f} mm away from the depth the program says")
    return (f"{got[True][0]:.1f} s and {got[True][1]:,} faces as a height map, {got[False][0]:.1f} s and "
            f"{got[False][1]:,} faces cut exactly; the two surfaces {apart:.3f} mm apart at most")


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


@line("app.layout", "The Fresing panel always comes back (layout on open, Live preview kept, header button)", "0.2.150",
      what="Checks the header button, the operator that shows the Fresing panel and the stored Live preview choice")
def app_layout(ctx):
    import bpy

    from ..blender import prefs, ui_header
    _check(hasattr(bpy.ops.fresing, "show_panel"), "the operator 'Show the Fresing panel' is missing")
    _check(ui_header._on_load in bpy.app.handlers.load_post, "the layout is not put right when a project opens")
    _check(ui_header._draw_header in bpy.types.VIEW3D_HT_header.draw._draw_funcs,
           "the Fresing button is not in the 3D view's header")
    p = prefs.get()
    _check(p is not None and hasattr(p, "live_preview"), "the Live preview choice is not stored")
    return None


@line("app.editors", "Blender's Outliner and Properties hidden, Fresing > Show Blender's editors brings them back, "
      "a solid side panel", "0.2.179",
      what="Checks that the layout is put right when a project opens, the menu entry Fresing > Show / Hide Blender's "
           "editors and its own reason in the Client view, which areas count as "
           "Blender's column (only an Outliner or Properties editor right next to the 3D view), the width it comes "
           "back at, the choice file in the settings folder, and Region Overlap off once (a user's own on kept)")
def app_editors(ctx):
    import bpy

    from ..blender import editors, lock, ui_header, ui_topbar
    _check(ui_topbar._has("fresing.blender_editors"), "the operator 'Show Blender's editors' is missing")
    _check("fresing.blender_editors" in ui_topbar.entries(), "Show Blender's editors is not in the Fresing menu")
    _check(ui_header._on_load in bpy.app.handlers.load_post, "the layout is not put right when a project opens")
    _check("fresing.blender_editors" in lock.ALLOWED, "the entry would be refused without its Client view reason")
    factory = [("PROPERTIES", 1579, 24, 339, 837), ("OUTLINER", 1579, 864, 339, 189),
               ("DOPESHEET_EDITOR", 2, 24, 1574, 74), ("VIEW_3D", 2, 101, 1574, 952)]
    _check(sorted(editors.column_indices(factory, editors.main_index(factory))) == [0, 1],
           "Blender's Outliner / Properties column is not recognised")
    own = [("OUTLINER", 2, 101, 300, 952), ("VIEW_3D", 305, 101, 1270, 952), ("IMAGE_EDITOR", 1579, 24, 339, 1029)]
    _check(editors.column_indices(own, editors.main_index(own)) == [], "a layout of the user's own would be changed")
    f = editors.split_factor(1920, 1916)
    _check(abs((1 - f) * 1916 - 339) < 2, f"the column would come back {int((1 - f) * 1916)} px wide, not 339")
    path = os.path.join(ctx.work, "Layout é", editors.FILE_NAME)
    _check(editors.read(path)["editors"] == "hidden", "a new user does not start with Blender's editors hidden")
    editors.write(path, {"editors": "shown", "overlap_off": True})
    _check(editors.read(path) == {"editors": "shown", "overlap_off": True}, "the choice is not kept in its file")
    real = editors.load()
    if not bpy.context.preferences.system.use_region_overlap:
        overlap = "off (solid side panel)"
    elif real["overlap_off"]:
        overlap = "on (your own choice, kept)"
    else:
        overlap = "on – the app switches it off at its next start"
    return f"your choice: Blender's editors {real['editors']}; Region Overlap {overlap}"


@line("backups.makes_one", "Automatic backups: a copy of the open project, the keep rule, nothing else deleted",
      "0.2.187",
      what="Saves a backup copy of the open project into a temporary folder (the project keeps its file name and its "
           "unsaved mark, the save handlers keep out), then runs the keep rule on made-up backups next to other files "
           "and checks that only old backups of that project were deleted")
def backups_makes_one(ctx):
    import time
    from datetime import date, datetime, timedelta

    import bpy

    from ..blender import backups, ui_topbar
    from ..core import backups as core
    _check(ui_topbar._has("fresing.backups_window"), "the operator 'Restore a backup…' is missing")
    _check("fresing.backups_window" in ui_topbar.entries(), "Restore a backup… is not in the Fresing menu")
    folder = os.path.join(ctx.work, "Backups é")
    os.makedirs(folder, exist_ok=True)
    before, dirty = bpy.data.filepath, bpy.data.is_dirty
    path = os.path.join(folder, core.backup_name("PC check", datetime.now()))
    t0 = time.perf_counter()
    backups.write_copy(path)
    secs = time.perf_counter() - t0
    _check(os.path.isfile(path) and os.path.getsize(path) > 0, "no backup file was written")
    _check(bpy.data.filepath == before, "the open project's file name changed with the backup")
    _check(bpy.data.is_dirty == dirty, "the open project's unsaved mark changed with the backup")
    _check(not backups.saving(), "the 'saving a backup' flag stayed on")
    keep = os.path.join(ctx.work, "Keep é")
    os.makedirs(keep, exist_ok=True)
    today = date.today()
    made = []
    for i in range(12):                                # 12 backups, one every 6 hours back from now
        t = datetime.now() - timedelta(hours=6 * i)
        p = os.path.join(keep, core.backup_name("Mill", t))
        with open(p, "wb") as f:
            f.write(b"x")
        made.append((t, p))
    others = ["Mill.blend", "Mill.blend1", "Lathe backup 2020-01-01 10-00.blend", "notes.txt"]
    for n in others:
        with open(os.path.join(keep, n), "wb") as f:
            f.write(b"y")
    gone = core.clean(keep, "Mill", 5, 7, today)
    left = set(os.listdir(keep))
    _check(all(n in left for n in others), "a file that is not a backup of this project was deleted")
    kept = core.keep(core.listing(keep, "Mill") + [core.Backup(p, t, 1, 0.0) for t, p in made if p in gone], 5, 7,
                     today)
    _check(not (kept & set(gone)), "a backup the keep rule keeps was deleted")
    _check(len(core.listing(keep, "Mill")) == len(kept) and len(kept) >= 5, f"{len(kept)} backups kept")
    ctx.metric("backup", secs, "s")
    return f"a backup of {core.size_text(os.path.getsize(path))} in {secs:.2f} s; {len(gone)} old backups deleted, " \
           f"{len(kept)} kept, other files left alone"


@line("app.quiet", "A quiet window: the 3D view header shows View, shading and Make, no Object / Add menus; the "
      "splash shows Fresing's lines; Fresing > Show all of Blender brings Blender's menus back, Back to the Fresing "
      "window hides them", "0.2.184",
      what="Checks that the quiet drawings swap only Blender's own part of the 3D view header, the splash and File > "
           "New (an add-on's appended items stay, also after switching back and forth), the splash's lines, and "
           "Fresing > Show all of Blender / Back to the Fresing window on a project: Full access and back to the "
           "workspace it came from, greyed in the Client view")
def app_quiet(ctx):
    import bpy

    from ..blender import quiet, ui_topbar, workspaces
    _check(ui_topbar._has("fresing.blender_all"), "the operator 'Show all of Blender' is missing")
    e = ui_topbar.entries()
    _check("fresing.blender_all" in e and e.index("fresing.blender_all")
           == e.index("fresing.blender_editors") + 1, "Show all of Blender is not below Show Blender's editors")
    for cls in (bpy.types.VIEW3D_HT_header, bpy.types.WM_MT_splash, bpy.types.TOPBAR_MT_file_new):
        _check(quiet._own(cls, quiet.draw_funcs(cls)) >= 0 or quiet.blender_draw(cls) is not None,
               f"Blender's own drawing of {cls.__name__} is not found: the quiet window cannot replace it")

    class FR_MT_pccheck_quiet(bpy.types.Menu):
        bl_label = "PC check"

        def draw(self, context):
            pass

    def addon_item(self, context):
        pass

    def quiet_draw(self, context):
        pass

    bpy.utils.register_class(FR_MT_pccheck_quiet)
    try:
        FR_MT_pccheck_quiet.append(addon_item)
        own = quiet.draw_funcs(FR_MT_pccheck_quiet)[0]
        for _ in range(2):                              # patch / unpatch / patch
            _check(quiet.swap(FR_MT_pccheck_quiet, quiet_draw), "Blender's own drawing could not be swapped")
            _check(quiet.draw_funcs(FR_MT_pccheck_quiet) == [quiet_draw, addon_item],
                   "an add-on's item was lost when the quiet drawing came in")
            quiet.unswap(FR_MT_pccheck_quiet)
            _check(quiet.draw_funcs(FR_MT_pccheck_quiet) == [own, addon_item], "Blender's own drawing did not come back")
    finally:
        quiet.unswap(FR_MT_pccheck_quiet)
        bpy.utils.unregister_class(FR_MT_pccheck_quiet)
    lines = quiet.splash_lines()
    _check(lines[:3] == ["wm.read_homefile", "wm.open_mainfile", "wm.recover_last_session"],
           f"the splash does not start with New project, Open, Recover ({lines})")
    scene = bpy.context.scene
    before = workspaces.name_of(scene)
    try:
        workspaces.switch(scene, "Product design & R&D")
        _check(quiet.menu_text(scene) == quiet.SHOW_TEXT, f"the entry reads '{quiet.menu_text(scene)}'")
        for _ in range(2):
            bpy.ops.fresing.blender_all()
            _check(workspaces.name_of(scene) == "Full access", "Show all of Blender did not switch to Full access")
            _check(quiet.menu_text(scene) == quiet.BACK_TEXT, f"the entry reads '{quiet.menu_text(scene)}'")
            bpy.ops.fresing.blender_all()
            _check(workspaces.name_of(scene) == "Product design & R&D",
                   f"Back to the Fresing window went to '{workspaces.name_of(scene)}'")
        workspaces.switch(scene, "Client view")
        _check(not bpy.ops.fresing.blender_all.poll(), "Show all of Blender is not greyed in the Client view")
    finally:
        workspaces.switch(scene, "Full access")
        try:
            workspaces.switch(scene, before if before != "Client view" else "All functions")
        except KeyError:                               # an own workspace whose file is not here
            workspaces.switch(scene, "All functions")
    if bpy.app.background:
        shown = "not drawn here (the check runs without a window)"
    else:
        shown = "quiet" if quiet.ON[0] else "Blender's own (Full access)"
    return f"the window's drawing: {shown}"


@line("app.keys", "Blender's keys: Delete, Shift+D, Ctrl+J … do nothing outside Full access and say how to get them; F12 / "
      "Ctrl+F12 render with the app; right-click on a part opens a short Fresing menu", "0.2.202",
      what="Checks the list of swallowed keys (and that H, A, G, Ctrl+Z stay Blender's), that they are swallowed in "
           "every workspace but Full access and come back in Full access, that a swallowed key changes nothing in the "
           "project, the Client view's own message, F12 / Ctrl+F12 bound to the app's render, and the right-click "
           "menu: Blender's own drawing found, the Fresing menu's entries on empty space")
def app_keys(ctx):
    import bpy

    from ..blender import context_menu, lock, quiet, workspaces
    labels = {lock.key_label(k, m) for _km, _sp, k, m, _w in lock.BLENDER_KEYS}
    for want in ("X", "Delete", "Tab", "Shift+D", "Alt+D", "Ctrl+J", "Ctrl+P", "Ctrl+A", "M", "Shift+A", "Ctrl+H",
                 "Ctrl+1", "Ctrl+Page Up", "I", "K"):
        _check(want in labels, f"the key {want} is not swallowed outside Full access")
    for keep in ("H", "A", "G", "R", "S"):
        _check(keep not in labels, f"the key {keep} should stay Blender's")
    app = {(k, bool(m.get("ctrl"))): op for _km, _sp, k, m, op, _p in lock.APP_KEYS}
    _check(app.get(("F12", False)) == "fresing.key_render" and app.get(("F12", True)) == "fresing.key_render",
           "F12 / Ctrl+F12 are not bound to the app's render")
    cls = bpy.types.VIEW3D_MT_object_context_menu
    _check(quiet._own(cls, quiet.draw_funcs(cls)) >= 0 or quiet.blender_draw(cls) is not None,
           "Blender's own right-click menu is not found: the Fresing menu cannot replace it")
    if not bpy.app.background:
        kc = bpy.context.window_manager.keyconfigs.addon
        items = [(kmi.idname, kmi.type) for km in kc.keymaps for kmi in km.keymap_items
                 if kmi.idname.startswith("fresing.")]
        _check(("fresing.key_render", "F12") in items, "the F12 key is not in the app's key map")
        _check(("fresing.view_menu", "RIGHTMOUSE") in items, "the right mouse is not in the app's key map")
    scene = bpy.context.scene
    before = workspaces.name_of(scene)

    def state():
        return (sorted((o.name, o.parent.name if o.parent else "", o.hide_render) for o in scene.objects),
                bpy.context.mode, len(bpy.data.actions), len(bpy.data.collections))

    try:
        workspaces.switch(scene, "Product design & R&D")
        _check(lock.keys_quiet() and bpy.ops.fresing.blender_key.poll() and bpy.ops.fresing.key_render.poll(),
               "Blender's keys are not swallowed outside Full access")
        was, kept = state(), lock.KEPT[0]
        for _km, _sp, k, m, _w in lock.BLENDER_KEYS:
            bpy.ops.fresing.blender_key(key=lock.key_label(k, m))
        _check(lock.KEPT[0] - kept == len(lock.BLENDER_KEYS), "not every Blender key was swallowed")
        _check(state() == was, "a swallowed key changed the project")
        context_menu.HIT.update(target="", part="")

        class Layout:
            def __init__(self):
                self.texts, self.operator_context = [], ""

            def label(self, text="", icon="NONE"):
                pass

            def separator(self, **_kw):
                pass

            def operator(self, idname, text="", icon="NONE"):
                self.texts.append(text)
                return type("Props", (), {})()

        lay = Layout()
        context_menu._draw(type("Menu", (), {"layout": lay})(), bpy.context)
        _check(tuple(lay.texts) == context_menu.ON_EMPTY, f"the right-click menu on empty space shows {lay.texts}")
        workspaces.switch(scene, "Client view")
        sw = lock.SWALLOWED[0]
        bpy.ops.fresing.blender_key(key="Shift+D")
        _check(lock.SWALLOWED[0] == sw + 1, "the Client view does not give its own message for a Blender key")
        workspaces.switch(scene, "Full access")
        _check(not lock.keys_quiet() and not bpy.ops.fresing.blender_key.poll()
               and not bpy.ops.fresing.key_render.poll() and not bpy.ops.fresing.view_menu.poll(),
               "Full access does not give Blender's keys back")
    finally:
        workspaces.switch(scene, "Full access")
        try:
            workspaces.switch(scene, before if before != "Client view" else "All functions")
        except KeyError:                               # an own workspace whose file is not here
            workspaces.switch(scene, "All functions")
    return f"{len(lock.BLENDER_KEYS)} Blender keys swallowed outside Full access, back in Full access; F12 = the app's render"


@line("structure.move", "Move and turn with G / R: what is locked in place says so, Unlock so it can move, the move "
      "stays", "0.2.216",
      what="On the test crane: G / R / S bound to the app's check; the fresh import is locked in place and G says how "
           "to unlock it; the right-click menu's Unlock so it can move; a move then stays; after Build G says the "
           "animation is built and where to stop it; S never scales a part")
def structure_move(ctx):
    import types

    import bpy

    from ..blender import build, lock, logic, place
    scene = ctx.fresh(CRANE_A, quality="draft")
    keys = {(k, p.get("mode")) for _km, _sp, k, _m, op, p in lock.APP_KEYS if op == "fresing.move_key"}
    _check(keys == {("G", "TRANSLATE"), ("R", "ROTATE"), ("S", "RESIZE")}, f"G / R / S are not bound to the check: {keys}")
    asm = next(o for o in scene.objects if o.get(build.PROP_NAME) == "BOOM.ASM")

    def sel(*obs):
        return types.SimpleNamespace(scene=scene, selected_objects=list(obs))

    msg, _n = place.why_not(sel(asm), "TRANSLATE")
    _check("locked in place" in msg and "Unlock so it can move" in msg,
           f"G on the fresh import does not say it is locked in place: '{msg}'")
    _check(bpy.ops.fresing.ctx_unlock(part=asm.name) == {"FINISHED"} and not any(asm.lock_location),
           "Unlock so it can move did not unlock the boom's subassembly")
    _check(place.why_not(sel(asm), "TRANSLATE") == ("", 0) and place.why_not(sel(asm), "ROTATE") == ("", 0),
           "the unlocked boom still cannot move")
    was = asm.location.x
    asm.location.x += 0.1
    bpy.context.view_layer.update()
    _check(abs(asm.location.x - was - 0.1) < 1e-6, "the moved boom did not stay")
    _check("keep their size" in place.why_not(sel(asm), "RESIZE")[0], "S does not say parts keep their size")
    from ..blender import tour
    tour._boom_joint(scene)
    a = tour._animation(types.SimpleNamespace(s=scene.fresing), "Up")
    tour._joint_step(a, "Boom", 0, 1, 20)
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    _check(bpy.ops.fresing.anim_build() == {"FINISHED"}, "Build & play failed")
    msg, _n = place.why_not(sel(asm), "TRANSLATE")
    _check(msg.startswith("The animation is built"), f"G after Build does not say the animation is built: '{msg}'")
    bpy.ops.fresing.anim_clear()
    logic.set_locked(asm, True)
    return "locked: says how to unlock; unlocked: the move stays; after Build: says stop it first"


@line("place.move", "Place: a model moved 1 m and turned 90° builds the same motion; the boom moved 100 mm takes its "
      "joint along; Back to the CAD place", "0.2.219",
      what="On the test crane with the crane lesson's joints, cylinder and animation: the whole crane moved 1 m along X "
           "and turned 90° builds the same motion, moved; the boom subassembly moved 100 mm up takes its joint's axis "
           "along and keeps it through Build; Back to the CAD place puts both back; the fields read the move")
def place_move(ctx):
    import math
    import time

    import bpy
    from mathutils import Matrix

    from ..blender import animation, build, joints, lesson, ops_place, place
    scene = ctx.fresh(CRANE_A, quality="draft")
    lesson.run(scene, "crane")
    s = scene.fresing
    a = s.animations[0]

    def ob(name):
        return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)

    def places(frames):
        out = {}
        for f in frames:
            scene.frame_set(f)
            out[f] = ob("BOOM").matrix_world.copy()
        return out

    def close(m, n):
        return all(abs(m[r][c] - n[r][c]) < 3e-4 for r in range(4) for c in range(4))

    info = animation.bake(scene, a)
    frames = (1, info["frames"])
    before = places(frames)
    animation.clear_keys(scene)
    root = ob("TEST.CRANE")
    ops_place.set_lock(root, False)
    D = Matrix.Translation((1.0, 0.0, 0.0)) @ Matrix.Rotation(math.radians(90.0), 4, "Z")
    t0 = time.time()
    place.move(scene, [root], D)
    ctx.metric("move", time.time() - t0, "s")
    animation.bake(scene, a)
    after = places(frames)
    _check(all(close(D @ before[f], after[f]) for f in frames), "the moved crane's boom does not move as before")
    x = place.numbers(scene, root, "MODEL")[0]
    _check(abs(x - 1000.0) < 0.5, f"Place's Model-axes X reads {x:.1f} mm, not 1000")
    animation.clear_keys(scene)
    place.back_to_cad(scene, [root])
    boom = ob("BOOM.ASM")
    ops_place.set_lock(boom, False)
    j = joints.find(scene, "Boom")
    o0, _d = joints.axis_world(j)
    place.move(scene, [boom], Matrix.Translation((0.0, 0.0, 0.1)))
    _update()
    o1, _d = joints.axis_world(j)
    _check(abs((o1 - o0).z - 0.1) < 1e-5, f"the boom's joint did not go along: {(o1 - o0).z * 1000:.2f} mm")
    animation.bake(scene, a)
    animation.clear_keys(scene)
    _update()
    _check(abs((joints.axis_world(j)[0] - o0).z - 0.1) < 1e-5, "Build lost the boom's new place")
    place.back_to_cad(scene, [boom])
    _update()
    _check((joints.axis_world(j)[0] - o0).length < 1e-5, "Back to the CAD place did not put the joint back")
    return "crane moved 1 m + 90°: same motion; boom +100 mm: joint along, kept by Build; back again"


@line("place.remove", "Remove: a subassembly and a model with what lives on them; nothing left pointing at nothing",
      "0.2.219",
      what="On the test crane with the crane lesson's set-up and a label: the window's list (parts, joints, cylinder, "
           "steps), the trolley removed (its joint goes, the boom and cylinder still work), then the whole crane "
           "removed – no joint, cylinder, label, step or object of it left")
def place_remove(ctx):
    import time

    import bpy

    from ..blender import animation, build, lesson, remove
    scene = ctx.fresh(CRANE_A, quality="draft")
    lesson.run(scene, "crane")
    s = scene.fresing

    def ob(name):
        return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)

    c = s.callouts.add()
    c.text, c.part = "Boom", ob("BOOM")
    trolley = ob("TROLLEY.ASM")
    p = remove.plan(scene, [trolley])
    _check((p["parts"], p["joints"]) == (3, 1), f"the trolley's list is wrong: {p['parts']} parts, {p['joints']} joints")
    _check(bpy.ops.fresing.remove(names=trolley.name) == {"FINISHED"}, "Remove of the trolley failed")
    _check([j.name for j in s.joints] == ["Boom"] and len(s.cylinders) == 1, "the boom's joint or the cylinder is gone")
    _check(animation.bake(scene, s.animations[0])["frames"] > 1, "the crane without its trolley does not build")
    animation.clear_keys(scene)
    root = ob("TEST.CRANE")
    p = remove.plan(scene, [root])
    lines = remove.lines(p)
    _check(lines and lines[0].startswith("Goes: 1 model, 17 parts, 1 joint, 1 cylinder"), f"the list: {lines[:1]}")
    t0 = time.time()
    _check(bpy.ops.fresing.remove(names=root.name) == {"FINISHED"}, "Remove of the crane failed")
    ctx.metric("remove", time.time() - t0, "s")
    left = [o.name for o in scene.objects if o.get(build.PROP_KIND) in build.MODEL_KINDS + build.JOINT_KINDS]
    _check(not left and not len(s.joints) and not len(s.cylinders) and not len(s.callouts),
           f"left after Remove: {left[:5]}, {len(s.joints)} joints, {len(s.callouts)} labels")
    _check(not any(len(a.blocks) for a in s.animations), "an animation step of the crane is left")
    return "trolley: its joint went, the rest builds; crane: nothing left"


@line("app.start_here", "Start here: the Fresing menu, the welcome and What's new after an update", "0.2.155",
      what="Checks the Fresing menu in the top bar, the start file (welcome three times, What's new once after an "
           "update, nothing after the same version), the page that opens the user guide at a section, and that What's "
           "new lists functions and a tour of the new and changed test models")
def app_start_here(ctx):
    import bpy

    from ..blender import ui_topbar, welcome
    from ..core import start
    _check(ui_topbar._draw_in_editor_menus in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize(),
           "the Fresing menu is not in the top bar")
    for idname in ("fresing.tour_take", "fresing.whats_new", "fresing.welcome", "fresing.show_panel"):
        _check(ui_topbar._has(idname), f"the Fresing menu's operator {idname} is missing")
    path = os.path.join(ctx.work, "Start é", start.FILE_NAME)          # the settings folder's file, with an accent
    state, now = start.load(path), welcome.version()
    shown = []
    for _ in range(4):                                                   # a new user: the welcome three starts
        kind = start.decide(state, now)
        shown.append(kind)
        state = start.started(state, now, kind)
        start.save(path, state)
        state = start.load(path)
    _check(shown == ["welcome"] * 3 + [""], f"the welcome showed {shown} (expected three times, then not)")
    older = welcome.previous_version() or "0.2.0"
    state = dict(start.load(path), last_run=older)
    _check(start.decide(state, now) == "whats_new", "What's new does not show after an update")
    state = start.started(state, now, "whats_new")
    _check(start.decide(state, now) == "", "What's new shows twice for the same version")
    page = welcome.guide_link_file("start-here")
    _check(os.path.isfile(page) and "#start-here" in open(page, encoding="utf-8").read(),
           "the page that opens the user guide at a section was not written")
    n_f, n_s = len(welcome.functions_new(older)), len(welcome.sets_new("0.2.0"))
    if n_f == 0:            # (task 0202: a release that brings no new function – What's new can still list functions)
        n_f = len(welcome.functions_new("0.2.0"))
    _check(n_f > 0 and n_s > 0, f"What's new lists {n_f} functions and {n_s} test models")
    return f"What's new since {older}: {n_f} functions"


@line("app.tools", "One shortcut only: Fresing Render on the Desktop and in the Start menu, the extras in the Tools folder "
      "and in Fresing > Tools and checks", "0.2.167",
      what="Checks the menu Fresing > Tools and checks (Run the self-test, PC check, Open the app folder) and, in an "
           "installed app on Windows, that the Desktop and the Start menu hold only the Fresing Render shortcut of this "
           "install (no PC check or self-test shortcuts there any more, no Start-menu folder) and that the Tools folder "
           "of the app holds the self-test, the three PC checks, the safe start and the user guide")
def app_tools(ctx):
    import bpy

    from .. import appicon
    from ..blender import apptools, ui_topbar
    for idname in apptools.entries():
        _check(ui_topbar._has(idname), f"the operator {idname} is missing")
        _check(idname in ui_topbar.entries(), f"{idname} is not in the Fresing menu")
    _check(hasattr(bpy.types, apptools.MENU), "the menu Fresing > Tools and checks is missing")
    folder = appicon.install_dir(bpy.app.binary_path)
    if not folder or os.name != "nt":
        return "menu checked; not an app installed with Install.bat on Windows: shortcuts not checked"
    desktop, programs, _ = appicon.known_folders()
    for path in appicon.old_shortcuts(desktop, programs):
        target = appicon.read_shortcut(path).get("target", "")
        _check(not appicon.is_inside(target, folder),
               f"an old shortcut of this install is still there: {path} (it should be in the Tools folder now)")
    gone = [where for where, d in (("Desktop", desktop), ("Start menu", programs))
            if not os.path.isfile(os.path.join(d, appicon.APP_LNK))]          # removed by the user: a note only
    from .. import winexe
    want = appicon.tools_specs(folder, winexe.blender_exe_of(bpy.app.binary_path), desktop, appicon.HERE)
    tools = appicon.tools_dir(folder)
    have = sorted(n for n in os.listdir(tools) if n.lower().endswith(".lnk")) if os.path.isdir(tools) else []
    missing = sorted({s["path"] for s in want.values()} - {os.path.join(tools, n) for n in have})
    _check(not missing, f"missing in the Tools folder: {', '.join(os.path.basename(m) for m in missing)}")
    if gone:
        return f"no Fresing Render shortcut on the {' or in the '.join(gone)} (removed?); Tools folder: {len(have)} shortcuts"
    return f"Desktop and Start menu: Fresing Render only; Tools folder: {len(have)} shortcuts"


@line("app.licences", "Licence files in this install, About Fresing Render, Blender's extension sync off", "0.2.162",
      what="Checks that the licence (GPL), the third-party notices, the page for companies and the licence texts of the "
           "libraries are inside this install, the About window and its buttons are there (Fresing and Help menu), a "
           "copy of a licence opens as a text file, Blender's own licence folder is next to its program, and Blender's "
           "own extension repositories do not sync at start")
def app_licences(ctx):
    import bpy

    from ..blender import about, ext_sync, ui_topbar
    from ..core import about as core
    pkg = about.package_dir()
    gone = core.missing(pkg)
    _check(not gone, f"licence files missing from this install: {', '.join(gone)}")
    path = core.find(pkg, core.LICENCE)
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    _check("GNU GENERAL PUBLIC LICENSE" in text and "Version 3" in text, "LICENSE is not the GPL version 3")
    texts = os.path.join(core.folder(pkg), core.THIRD_PARTY)
    n_texts = len([f for f in os.listdir(texts) if f != "SOURCES.txt"]) if os.path.isdir(texts) else 0
    _check(n_texts >= 20, f"only {n_texts} third-party licence texts in {texts}")
    for idname in ("fresing.about", "fresing.about_open"):
        _check(ui_topbar._has(idname), f"the operator {idname} is missing")
    _check("fresing.about" in ui_topbar.entries(), "About is not in the Fresing menu")
    _check(about._draw_about_help in bpy.types.TOPBAR_MT_help._dyn_ui_initialize(), "About is not in the Help menu")
    copy = about.readable_copy(path, "Licence")
    _check(copy.endswith(".txt") and os.path.isfile(copy), "the licence copy for the text program was not made")
    binary = bpy.app.binary_path or ""
    if os.path.basename(binary).lower().startswith("blender"):
        _check(os.path.isdir(os.path.join(os.path.dirname(binary), "license")),
               "Blender's own licence folder is not next to its program")
    on = ext_sync.synced()
    _check(not on or os.path.isfile(ext_sync.state_path()),
           f"Blender's extension repository syncs at start: {', '.join(on)}")
    return None


@line("app.fr_mark", "The Fr mark stands at the left of the top bar in place of Blender's logo; its menu has About "
      "Fresing Render…, Fresing Settings… and Blender", "0.2.209",
      what="Checks that the top bar draws the Fr mark (with its picture) as its first item and File, Edit, Render, "
           "Window, Help, Fresing after it, that its menu has its three lines, and that switching the app's part off "
           "gives Blender's logo back")
def app_fr_mark(ctx):
    import bpy

    from ..blender import ui_topbar

    class _Rec:
        def __init__(self):
            self.menus = []
            self.operator_context = ""

        def menu(self, menu, **kw):
            self.menus.append((menu, kw))

        def operator(self, *a, **kw):
            pass

        def separator(self, *a, **kw):
            pass

    class _Area:
        show_menus = True

    class _Ctx:
        area = _Area()

    def top():
        rec = _Rec()
        holder = type("M", (), {"layout": rec})()
        for f in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize():
            f(holder, _Ctx())
        return [m for m, _kw in rec.menus], rec.menus

    _check(ui_topbar.mark_shown(), "Blender's logo is still drawn at the left of the top bar")
    names, menus = top()
    _check(names[:1] == [ui_topbar.MARK_MENU], f"the top bar's first item is {names[:1]}")
    _check(names[1:7] == ["TOPBAR_MT_file", "TOPBAR_MT_edit", "TOPBAR_MT_render", "TOPBAR_MT_window",
                          "TOPBAR_MT_help", ui_topbar.MENU], f"the top bar's menus after the mark: {names[1:]}")
    _check(bpy.app.background or ui_topbar.mark_icon() > 0, "the Fr mark's picture did not load")
    _check(ui_topbar.mark_entries() == ["fresing.about", "fresing.settings", "TOPBAR_MT_blender"],
           f"the Fr menu's lines: {ui_topbar.mark_entries()}")
    ui_topbar.unregister_handlers()
    try:
        off, _m = top()
        _check(off[:1] == ["TOPBAR_MT_blender"], "switched off, Blender's logo did not come back")
    finally:
        ui_topbar.register_handlers()
    _check(ui_topbar.mark_shown(), "the Fr mark did not come back")
    return "Fr mark first; its menu: About, Settings, Blender"


@line("app.settings", "Fresing Settings: one window with tabs; only your own input counts as time in My usage",
      "0.2.201",
      what="Every tab of the Settings window draws (General, Side panel, Lessons, Backups, Updates, My usage, About), "
           "the window's buttons are in the Fresing menu, the left panel and the Add-ons page, a tab is kept for the "
           "next opening, and a played animation with no mouse or key adds no time to My usage")
def app_settings(ctx):
    import bpy

    from ..blender import ops_settings, prefs, ui_settings, ui_topbar, usage
    from ..core import usage as core
    _check("fresing.settings" in ui_topbar.entries(), "Settings… is not in the Fresing menu")
    for idname in ("fresing.settings", "fresing.settings_tab", "fresing.settings_close", "fresing.presence"):
        _check(ui_topbar._has(idname), f"the operator {idname} is missing")
    drawn = ui_settings.draw_all(bpy.context)
    _check(drawn == list(ui_settings.KEYS), f"only these tabs draw: {', '.join(drawn)}")
    p = prefs.get()
    _check(p is not None, "the add-on's preferences are missing")
    was = p.settings_tab
    try:
        _check(ops_settings.set_tab("usage") and ui_settings.current() == "usage", "the tab My usage is not kept")
    finally:
        p.settings_tab = was
    s = core.fresh()
    clock = core.Clock()
    clock.tick(s, now=0.0, stage="render")              # a click, then 10 minutes of playback with no input
    clock.tick(s, now=600.0)
    _check(s["stages"].get("render", 0.0) == 0.0, f"10 min away counted {s['stages'].get('render')} s")
    _check(usage._on_change.__code__.co_names.count("activity") == 0, "a change of the project still counts as you")
    return f"{len(drawn)} tabs draw; 10 min of playback with no input: 0 s counted"


@line("app.windows", "Function windows: Make a crane and the other forms in a window of their own", "0.2.217",
      what="Every function that opens a form (Make a crane, Save as my own workspace, Restore a backup, the PC check, "
           "Learn … 23 of them) has its values as the window's own, draws its form there, and its Make runs the "
           "function with those values – a refused one says why and the window stays; window sizes and places are "
           "kept in the settings file")
def app_windows(ctx):
    import bpy

    from ..blender import form_window as fw
    from ..blender import ops_make, ui_settings
    bad = []
    for idname in fw.WINDOWS:
        cls = fw.op_class(idname)
        if cls is None:
            bad.append(f"{idname} missing")
            continue
        fw.make_group(cls)
        fw._FORMS.setdefault(idname, {"cls": cls, "title": "", "confirm": "OK", "icon": "WINDOW",
                                      "extra": {"_told": []}, "error": ""})
        try:
            if not fw.draw_form(ui_settings._Any(), bpy.context, idname):
                bad.append(f"{idname} has no values")
        except Exception as exc:  # noqa: BLE001 - the line names every form that does not draw
            bad.append(f"{idname}: {exc}"[:120])
    _check(not bad, "these windows do not draw: " + "; ".join(bad))
    fw.data("fresing.gcode_go_line").line = 7
    res, why = fw.run("fresing.gcode_go_line")                 # no CNC machine here: refused, with a reason
    _check(res == {"CANCELLED"} and bool(why), f"a refused Make gave {res} '{why}'")
    places, sizes = ops_make.parse(ops_make.dump({"settings": [1, 2, 300, 400]}, {"form:fresing.pose_save": [340, 150]}))
    _check(places == {"settings": [1, 2, 300, 400]} and sizes == {"form:fresing.pose_save": [340, 150]},
           "window sizes and places are not read back as written")
    return f"{len(fw.WINDOWS)} function windows draw their forms; a refused Make says why"


@line("settings.kept", "Settings kept over a restart: the app's own settings file", "0.2.206",
      what="Changes a setting of each tab of the Settings window, starts the settings as at a new start (Blender's "
           "own preferences forgotten) and reads them back from the app's settings file (in a folder with an accent); "
           "a damaged file gives the defaults, one note and a copy of the damaged file")
def settings_kept(ctx):
    from ..blender import prefs, settings_store
    from ..core import settings_file as sf
    p = prefs.get()
    _check(p is not None, "the add-on's preferences are missing")
    spec = settings_store.spec()
    was = {n: settings_store.current_one(p, n, k) for n, k in spec.items()}
    chosen = {"hover_highlight": False, "keep_sections": True, "lesson_part": "1", "lesson_colour": (0.9, 0.1, 0.4),
              "backup_minutes": 12, "check_updates": False}
    env = settings_store.ENV
    old_env = os.environ.get(env)
    os.environ[env] = os.path.join(ctx.work, "settings é", sf.FILE_NAME)
    try:
        settings_store.forget()
        _check(settings_store.load(), "the settings file was not started")
        for n, v in chosen.items():
            setattr(p, n, v)
        _check(settings_store.save(), "a change was not written to the settings file")
        for n, k in spec.items():                     # a new start: Blender gives the defaults
            setattr(p, n, k.default)
        settings_store.forget()
        settings_store.load()
        got = {n: settings_store.current_one(p, n, spec[n]) for n in chosen}
        _check(all(sf.same(got[n], v) for n, v in chosen.items()), f"after a restart the settings are {got}")
        with open(settings_store.path(), "w", encoding="utf-8") as fh:
            fh.write('{"format": "fresing-settings", "settings": {')
        settings_store.forget()
        settings_store.load()
        _check(p.keep_sections is False and p.backup_minutes == 5, "a damaged file did not give the defaults")
        _check(len(settings_store.notes()) == 1, f"a damaged file gave the notes {settings_store.notes()}")
        copies = [f for f in os.listdir(os.path.dirname(settings_store.path())) if ".broken-" in f]
        _check(len(copies) == 1, f"the damaged file was not kept aside: {copies}")
    finally:
        for n, v in was.items():
            try:
                setattr(p, n, v)
            except Exception:  # noqa: BLE001
                pass
        if old_env is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = old_env
        settings_store.forget()
    return f"{len(chosen)} settings kept over a restart; {len(spec)} settings in the file; a damaged file: defaults"


@line("settings.locations", "Locations: folders of the company, a department and your own; set-up files; export places",
      "0.2.210",
      what="In a folder of its own (with an accent): a new user's ready-made folders are made and on; a company set-up "
           "file (copied) and a department one (linked) bring a logo and a rule set each – both listed with their "
           "badges next to your own, the same logo name twice shown twice; saving asks where (your own folder first); "
           "a renamed newer set-up is the same one with its change list; a folder on a server that does not answer "
           "does not slow the reading; Save to and Also save a copy to put a picture into two places")
def settings_locations(ctx):
    import time as _time

    from ..blender import decals, locations, ops_rule_sets, prefs, settings_store
    from ..core import locations as L
    from ..core import rule_sets as RS
    p = prefs.get()
    _check(p is not None, "the add-on's preferences are missing")
    work = os.path.join(ctx.work, "locations é")
    was_prefs = settings_store.current(p)
    was_env = {k: os.environ.get(k) for k in (locations.ENV, "FRESING_RULE_SETS_DIR", L.SLOW_ENV)}
    was_docs = locations.documents
    os.environ[locations.ENV] = os.path.join(work, "config", L.STATE_FILE)
    os.environ.pop("FRESING_RULE_SETS_DIR", None)
    locations.documents = lambda: os.path.join(work, "Documents")
    try:
        locations.forget()
        locations.load()
        root = L.ready_root(locations.documents())
        _check(all(os.path.isdir(os.path.join(root, k.sub)) for k in L.KINDS), "the ready-made folders were not made")
        with open(os.path.join(root, "Logos", "acme.png"), "wb") as fh:
            fh.write(b"mine")

        def folder(name, files=()):
            d = os.path.join(work, name)
            os.makedirs(d, exist_ok=True)
            for f in files:
                with open(os.path.join(d, f), "wb") as fh:
                    fh.write(b"x")
            return d
        rules = folder("company rules")
        RS.save_in(rules, RS.empty("Acme rules"))
        c = os.path.join(work, "Company.frsetup")
        L.write_setup(c, L.Setup(id="pc-check-co", name="Company", version=1, locations={"rule_sets": [rules]}),
                      {"logos": folder("company logos", ("acme.png",))})
        d = os.path.join(work, "Offshore.frsetup")
        L.write_setup(d, L.Setup(id="pc-check-dep", name="Offshore", level="department", label="Offshore", version=1),
                      {"logos": folder("dep logos", ("buoy.png",))})
        locations.install(c, "copy")
        locations.install(d, "link")
        locations.wait_reach()
        pics = [lbl for lbl, _p in decals.library_pictures()]
        _check({"Logos: acme  ·  Company", "Logos: acme  ·  Mine", "Logos: buoy  ·  Offshore"} <= set(pics),
               f"the logos listed are {pics}")
        labels = [e[1] for e in ops_rule_sets._library_entries()]
        _check("Acme rules  ·  Company" in labels, f"the rule sets listed are {labels}")
        ch = [lbl.split(":")[0] for _p, lbl in locations.save_choices("rule_sets")]
        _check(ch[:2] == ["Mine", "Company"], f"saving offers {ch}")
        renamed = os.path.join(work, "Offshore NEW.frsetup")
        L.write_setup(renamed, L.Setup(id="pc-check-dep", name="Offshore", level="department", label="Offshore",
                                       version=2))
        new, old, lines = locations.check(renamed)
        _check(old is not None and "Version 1 → 2" in lines, f"a renamed newer set-up gave {lines}")
        dead = os.path.join(work, "dead server")
        os.environ[L.SLOW_ENV] = f"{dead}=5"
        locations.add_mine("logos", os.path.join(dead, "Logos"))
        locations.forget()
        t0 = _time.perf_counter()
        locations.load()
        decals.library_pictures()
        took = _time.perf_counter() - t0
        _check(took < 1.0, f"a folder on a server that does not answer slowed the reading to {took:.1f} s")
        ctx.metric("locations.dead_server_ms", round(took * 1000), "ms")
        share = folder("marketing")
        locations.state()["exports"]["own"].append({"name": "Marketing", "path": share, "project_sub": False})
        locations.state()["exports"].update(also=True, also_to="mine:Marketing")
        pic = os.path.join(work, "still.png")
        with open(pic, "wb") as fh:
            fh.write(b"png")
        import bpy
        copy = locations.copy_also(bpy.context.scene, pic)
        _check(bool(copy) and os.path.dirname(copy) == share, f"the copy went to {copy!r}")
    finally:
        os.environ.pop(L.SLOW_ENV, None)
        for k, v in was_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        locations.documents = was_docs
        for n, v in was_prefs.items():
            try:
                setattr(p, n, v)
            except Exception:  # noqa: BLE001
                pass
        locations.forget()
        try:
            locations.load()
        except Exception:  # noqa: BLE001
            pass
    return f"{len(pics)} logos from 3 places with badges; dead server: {took * 1000:.0f} ms; also a copy: ok"


@line("app.usage", "Usage tracker: counting on this PC, the favourites bar, unused panels, My usage", "0.2.158",
      what="Counts clicks into a usage file of its own (never yours; with an accent in its folder), checks every "
           "Fresing button counts, the bar is sorted at a start only, a panel is offered for hiding after 10 starts "
           "and never while the project uses it, a broken file starts empty and keeps a copy, and what one counted "
           "click costs")
def app_usage(ctx):
    import time

    import bpy

    from ..blender import usage, workspaces
    from ..core import places
    from ..core import usage as core
    missing = [c.bl_idname for c in bpy.types.Operator.__subclasses__()
               if getattr(c, "bl_idname", "").startswith("fresing.") and c.bl_idname not in core.NOT_COUNTED
               and not any(getattr(getattr(c, a, None), "_fr_usage", False) for a in ("invoke", "execute"))]
    _check(not missing, f"{len(missing)} Fresing buttons do not count their clicks: {', '.join(missing[:5])}")
    folder = os.path.join(ctx.work, "Usage é")
    path = os.path.join(folder, core.FILE_NAME)
    old = {k: os.environ.get(k) for k in (usage.FILE_ENV, core.TEST_ENV)}
    os.environ[usage.FILE_ENV], os.environ[core.TEST_ENV] = path, "1"
    usage.forget()
    try:
        _check(usage.counting(), "the usage tracker does not count")
        for _ in range(3):
            usage.record("fresing.turntable")
        usage.record("fresing.render")
        n = 300
        t0 = time.perf_counter()
        for _ in range(n):
            usage.record("fresing.render")
        ms = (time.perf_counter() - t0) / n * 1000
        ctx.metric("usage_click", ms, "ms")
        _check(ms < 2.0, f"one counted click costs {ms:.2f} ms")
        usage.start()
        s = usage.state()
        _check(s["bar"]["order"][:2] == ["scene.still", "scene.turntable"], f"the bar is {s['bar']['order']}")
        _check(usage.save(force=True) and os.path.isfile(path), "the usage file was not written")
        s["sessions"] = core.THRESHOLD_DEFAULT
        scene = ctx.fresh(CRANE_A)
        usage._S["prompted"] = ""
        usage.project_changed(scene)
        panel = usage.prompt()
        _check(bool(panel), "no unused panel is offered after 10 starts")
        used = set(workspaces.used_functions(scene))
        _check(not used & set(core.panel_functions(panel)), "a panel the project uses is offered for hiding")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{broken")
        usage.forget()
        _check(usage.state() == core.fresh() and os.path.isfile(path + ".broken"),
               "a broken usage file does not start empty with a copy kept")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        usage.forget()
        workspaces.PERSONAL["hide"] = ()
    return f"one counted click {ms:.3f} ms; after 10 starts '{places.PLACES[panel][1]}' would be offered for hiding"


@line("app.learning", "Learn as you go: the question teaches, the learning list, next to learn", "0.2.160",
      what="The question about an unused panel offers the guide, the Learning hub and the learning list beside Hide (and "
           "only Hide when teaching is off); a function on the list is ticked by itself after use on 3 days and the "
           "list says so once; the quiet 'next to learn' never offers what was hidden, turned down or is used by the "
           "project; the usage file keeps the list (with an accent in its folder) and an older file without it reads")
def app_learning(ctx):
    import bpy

    from ..blender import learning, ops_learning, usage, workspaces
    from ..core import learning as L
    from ..core import usage as core
    for op in ("learn_show", "learn_add", "learn_add_new", "learn_done", "learn_remove", "learn_next", "learn_window"):
        _check(hasattr(bpy.ops.fresing, op), f"the button fresing.{op} is missing")
    folder = os.path.join(ctx.work, "Learning é")
    path = os.path.join(folder, core.FILE_NAME)
    old = {k: os.environ.get(k) for k in (usage.FILE_ENV, core.TEST_ENV)}
    os.environ[usage.FILE_ENV], os.environ[core.TEST_ENV] = path, "1"
    usage.forget()
    try:
        s = usage.state()
        for _ in range(3):
            usage.record("fresing.turntable")
        s["sessions"] = core.THRESHOLD_DEFAULT
        scene = ctx.fresh(CRANE_A)
        usage._S["prompted"] = ""
        usage.project_changed(scene)
        panel = usage.prompt()
        _check(bool(panel), "no unused panel is offered after 10 starts")
        q = learning.question(panel)
        _check(bool(q["fid"]) and bool(q["guide"]), f"the question about '{panel}' has nothing to show")
        s["learning"]["teach"] = False
        _check(not learning.question(panel)["fid"], "the question teaches although teaching is off")
        s["learning"]["teach"] = True
        usage.answer(scene, "learn")
        _check(L.find(s, q["fid"]) is not None, "'Add to my learning list' did not put it on the list")
        _check(usage.save(force=True) and os.path.isfile(path), "the usage file was not written")
        usage.forget()
        _check(L.find(usage.state(), q["fid"]) is not None, "the learning list is not kept in the usage file")
        s = usage.state()
        got = []
        for day in ("2026-11-01", "2026-11-02", "2026-11-03"):
            got += L.note_use(s, q["fid"], day)
        _check(got == [q["fid"]] and L.take_told(s) == [q["fid"]] and not L.take_told(s),
               "a function used on 3 days is not ticked by itself, or the list says so twice")
        used = set(workspaces.used_functions(scene))
        shown = set(workspaces._state(scene)[1] or ())
        cands = [c[0] for c in L.candidates(s, shown, used)]
        _check(not used & set(cands), "'next to learn' offers a function the project uses")
        _check(ops_learning.learning.idname_of("FRESING_OT_sort_parts") == "fresing.sort_parts",
               "a right-clicked button's operator is not found")
        legacy = {k: v for k, v in core.fresh().items() if k != "learning"}
        legacy[core.MARKER] = 1
        _check(core.clean(legacy)["learning"] == L.fresh(), "an older usage file does not read")
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        usage.forget()
        workspaces.PERSONAL["hide"] = ()
    return f"'{L.one_line(q['fid'])}' offered, listed, ticked after 3 days; next to learn: {len(cands)} candidates"


@line("app.lessons", "Lessons: the crane in Build it yourself to the end, Show me's first three steps", "0.2.189",
      what="Fresing > Learn… is there; the crane lesson in Build it yourself does every step with Do it for me and goes "
           "on by itself once the project shows each done (11 steps: joints, camera, scene, animation, Build, exploded "
           "view, the queue); Show me points, does steps 2 to 4 itself and waits for Next; nothing of the lesson runs "
           "after Stop")
def app_lessons(ctx):
    import time

    import bpy

    from ..blender import highlight, lesson, ui_topbar
    _check("fresing.learn_lessons" in ui_topbar.entries(), "Learn… is not in the Fresing menu")
    les = lesson.LESSONS.get("crane")
    _check(les is not None and len(les.steps) == 11, "the crane lesson is missing or not 11 steps")
    t0 = time.time()
    scene = ctx.fresh(CRANE_A)
    lesson.start(scene, "crane", "BUILD")
    try:
        _check(lesson.state()["step"] == 1, f"Build it yourself starts at step {lesson.state()['step'] + 1}, not 2")
        k = 1
        while lesson.step() is not None:
            st = lesson.step()
            _check(not lesson.is_done(scene, st), f"step {k + 1} '{st.title}' counts as done before it was done")
            _check(lesson.do_step(scene), f"Do it for me failed at step {k + 1} '{st.title}': {lesson.state()['failed']}")
            now = time.time()
            lesson.tick(scene, now=now + lesson.DONE_PAUSE + 0.1)       # "Done", then on by itself
            k += 1
            _check(lesson.state()["step"] == k or lesson.step() is None, f"the lesson did not go on after step {k}")
        build_s = time.time() - t0
        s = scene.fresing
        _check(len(s.joints) >= 2 and len(s.shots) >= 2 and s.anim_baked and len(s.queue) == 1,
               "the crane lesson's project misses its joints, scenes, built animation or queued picture")
    finally:
        lesson.stop(forget=True)
    _check(lesson.handlers_left() == [] and highlight.handlers_left() == [],
           f"left running after Stop: {lesson.handlers_left() + highlight.handlers_left()}")
    t1 = time.time()
    scene = ctx.fresh(CRANE_A)
    lesson.start(scene, "crane", "SHOW")
    try:
        for k in (2, 3, 4):
            st = lesson.step()
            _check(lesson.state()["phase"] == "point", f"Show me does not point at step {k}")
            now = time.time()
            lesson.tick(scene, now=now)
            _check(lesson.state()["phase"] == "point", f"Show me did step {k} before pointing at it")
            lesson.tick(scene, now=now + lesson.SHOW_LATEST + 0.1)
            _check(lesson.state()["phase"] == "done" and lesson.is_done(scene, st),
                   f"Show me did not do step {k} '{st.title}': {lesson.state()['failed']}")
            lesson.tick(scene, now=now + lesson.SHOW_LATEST + lesson.PLAY_PAUSE + 5.0)
            _check(lesson.state()["phase"] == "done", "Show me went on without Next (Play on is off)")
            bpy.ops.fresing.lesson_next()
        _check(lesson.state()["step"] == 4, f"Show me is at step {lesson.state()['step'] + 1}, not 5")
    finally:
        lesson.stop(forget=True)
    ctx.metric("lesson build", build_s, "s")
    return (f"Build it yourself: 10 steps done for you in {build_s:.1f} s; Show me: steps 2–4 in "
            f"{time.time() - t1:.1f} s; nothing left running")


@line("panel.two", "Two panels: the work on the right, the rest on the left; Make's windows; the Learning hub switch",
      "0.2.197",
      what="The right panel starts with Make (one row of six outputs) and the section tabs, the left panel holds Live "
           "preview + Build & play, the update notice, Workspace, the Learning hub, Favourites and What's next; each "
           "output has its own window with a tooltip; on the crane sample the switch goes View -> Show me -> Build it "
           "yourself. (Run without a window: the left panel's width, the windows on screen and scrolling are checked "
           "by the real-app test and on your PC.)")
def panel_two(ctx):
    import bpy

    from .. import _all_classes
    from ..blender import lesson, ops_make, panels, ui_left, ui_top
    classes = _all_classes()
    left = [c.__name__ for c in classes if panels.is_left(c)]
    _check(left[:1] == ["FRESING_PT_left_quick"] and left[-1:] == ["FRESING_PT_next"]
           and {"FRESING_PT_workspace", "FRESING_PT_hub", "FRESING_PT_favourites", "FRESING_PT_update"} <= set(left),
           f"the left panel holds {left}")
    right = [c.__name__ for c in classes if getattr(c, "bl_region_type", "") == "UI"
             and getattr(c, "bl_category", "") == "Fresing"]
    _check(right[:3] == ["FRESING_PT_make", "FRESING_PT_tabs", "FRESING_PT_import"],
           f"the right panel starts with {right[:3]}, not Make, the tabs, 1 Import")
    _check(not set(left) & set(right), "a panel is on both sides")
    keys = list(ops_make.outputs())
    _check(len(keys) == 6, f"Make has {len(keys)} outputs, not 6")
    for key in keys:
        props = type("P", (), {"key": key})()
        text = bpy.types.FRESING_OT_make_window.description(bpy.context, props)
        _check(ops_make.title(key) in text and len(text) > 60, f"the output '{key}' has no proper tooltip: {text!r}")
    _check(bpy.ops.fresing.make_window.poll() and bpy.ops.fresing.left_fold.poll(), "Make's windows or the fold refused")
    scene = ctx.fresh(CRANE_A)
    from ..blender import tour
    scene[tour.TAG] = "crane"
    st = ui_left.hub_state(scene)
    _check(st["in_hub"] and st["mode"] == "VIEW" and st["lesson"], f"the crane sample does not show as View: {st}")
    del scene[tour.TAG]
    lesson.start(scene, "crane", "SHOW")
    try:
        _check(ui_left.hub_state(scene)["mode"] == "SHOW", "the crane lesson does not show as Show me")
        _check(bpy.ops.fresing.hub_mode("EXEC_DEFAULT", mode="BUILD") == {"FINISHED"}
               and ui_left.hub_state(scene)["mode"] == "BUILD" and lesson.state()["mode"] == "BUILD",
               "the switch did not go from Show me to Build it yourself")
    finally:
        lesson.stop(forget=True)
    _check(not ui_left.hub_state(scene)["in_hub"], "an own project still counts as a Learning hub project")
    _check(callable(ui_top.draw_make), "Make's drawing is missing")


@line("panel.folds", "Left panel: Live preview and Build & play once, top left; every section keeps its fold", "0.2.204",
      what="Live preview and Build & play are only on the left panel (not in 5 Scene & Render or 6 Animation); "
           "Favourites folds with its arrow like Learning hub, Lesson and Workspace, and every fold (with the left "
           "panel's own and What's next) is written to a small file in the settings folder and read back as after a "
           "restart. (Checked with a file of its own: your own folds are not changed.)")
def panel_folds(ctx):
    import inspect

    import bpy

    from ..blender import panels, ui, ui_left, ui_motion
    from ..core import functions as F
    out = inspect.getsource(panels.body_of(ui.FRESING_PT_output))
    anim = inspect.getsource(panels.body_of(ui_motion.FRESING_PT_animation))
    _check("fresing.preview" not in out, "5 Scene & Render still draws Live preview")
    _check("fresing.anim_build" not in anim, "6 Animation still draws Build & play")
    _check(F.FUNCTIONS["animation.build"].panel == "FRESING_PT_left_quick", "Build & play is not listed on the left")
    _check("FRESING_PT_favourites" in panels.LEFT and "FRESING_PT_favourites" not in panels._PLAIN,
           "Favourites has no title row with a fold arrow")
    env = ui_left.STORE_ENV
    old_env = os.environ.get(env)
    os.environ[env] = os.path.join(ctx.work, "left folds", ui_left.STORE)
    names = ("FRESING_PT_favourites", "FRESING_PT_hub", "FRESING_PT_lesson", "FRESING_PT_workspace")
    kept_open = set(panels.OPEN)
    try:
        before = {n: panels.is_open(n) for n in names}
        for n in names:
            _check(bpy.ops.fresing.panel_toggle("EXEC_DEFAULT", name=n) == {"FINISHED"}, f"{n} did not fold")
        want = {n: not before[n] for n in names}
        _check(ui_left.store().get("open") == want, f"the folds were not written: {ui_left.store()}")
        panels.OPEN.clear()                              # as a new start: nothing in memory, only the file
        panels.OPEN.update(panels.DEFAULT_OPEN)
        panels._LEFT_DONE.clear()
        got = {n: panels.is_open(n) for n in names}
        _check(got == want, f"after a restart the folds are {got}, not {want}")
        ui_left.store_set(folded=True, width=260, next_folded=True)
        ui_left._SYNCED.clear()
        _check(ui_left.folded() and ui_left.next_folded(), "the left panel's own fold / What's next not read back")
    finally:
        p = ui_left._prefs()
        if p is not None:
            p.left_folded, p.next_folded = False, False
        ui_left._SYNCED.clear()
        if old_env is None:
            os.environ.pop(env, None)
        else:
            os.environ[env] = old_env
        panels.OPEN.clear()
        panels.OPEN.update(kept_open)
        panels._LEFT_DONE.clear()


@line("tour.make", "Learning hub: the projects are made, every stop's Go works", "0.2.47",
      what="Makes the Learning hub (a small project per test model) and does Go and the number check of every stop, "
           "without pictures (the PC check's mode Learning hub renders them)")
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


@line("demo.kit", "Demo kits: add a kit, make its demo, remove it", "0.2.178",
      what="Adds the made-up test kit (a box on a deck plate) to a kits folder of the check's own, makes its demo the "
           "way Help > Make demo project… does (the kit's model maker as a program of its own, its stage, Build), "
           "checks that the box's slide joint moves the box and that the saved camera is there, then removes the kit")
def demo_kit(ctx):
    import bpy

    from .. import __version__
    from ..blender import demo, joints
    from ..core import demo_kits
    kits = os.path.join(ctx.work, "Demo kits é")                 # never the user's own kits folder
    old = os.environ.get(demo_kits.ENV)
    os.environ[demo_kits.ENV] = kits
    try:
        info = demo_kits.add(os.path.join(DATA, "demo_kit_test.zip"), demo.kits_dir(), __version__)
        _check([k.id for k in demo_kits.list_kits(kits)] == ["test-kit"], "the added kit is not in the list")
        folder = demo.kit_folder(os.path.join(ctx.work, "Demo é"), info.id)
        t0 = time.time()
        out = demo.build_project(folder, __version__, small=True, kit=info)
        ctx.metric("make", time.time() - t0, "s")
        _check(list(out["seconds"]) == ["kit_model", "box", "finish"], f"the kit's build ran {list(out['seconds'])}")
        _check(demo.exists(folder, __version__, info.title), "the kit's demo project was not saved")
        bpy.ops.wm.open_mainfile(filepath=out["path"])
        sc = bpy.context.scene
        jt = sc.fresing.joints.get("Box slide")
        _check(jt is not None, "the kit's demo has no joint 'Box slide'")
        box = next((o for o in sc.objects if o.get("fr_name") == "TEST BOX"), None)
        _check(box is not None, "the kit's demo has no box")
        x0 = box.matrix_world.translation.x
        joints.set_value(jt, 1.5)
        bpy.context.view_layer.update()
        moved = box.matrix_world.translation.x - x0
        _check(abs(moved - 1.5) < 1e-3, f"the joint moved the box {moved:.3f} m, not 1.5 m")
        _check(any(s.name == "Box from the side" for s in sc.fresing.shots), "the kit's saved camera is missing")
        _check(demo_kits.remove(kits, info.id) and not demo_kits.list_kits(kits), "the kit could not be removed")
    finally:
        if old is None:
            os.environ.pop(demo_kits.ENV, None)
        else:
            os.environ[demo_kits.ENV] = old
    return f"test kit made in {time.time() - t0:.0f} s, its joint moves the box"


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
