"""PC check "Stress" (task 0315): a made-up ~10,000-part model and every heavy action timed.

The model (``stress_scene.py``: an invented offshore substation topside, about 11,000 placed / 2,000 unique parts,
44 % bolts, nuts and washers, B-spline cables, lofts and fillets) is *made at run time* in a temporary folder and
deleted at the end; nothing of it is in the repository. Each line measures one heavy action – import at Draft and
Normal, the side panel's lists and search, selecting and hovering, the Solid view and the first Live-preview picture,
the joints and Build, a joint drag, the clash check, save and open, a backup, Undo, a model update with about 1 % of
the parts changed, a 4K render and the web 3D export – with its time, the peak memory while it ran and a mark against
a limit (``limit=``: about twice the first measurement on the 4-core web machine without a graphics card, task
report 0315; the Solid view's limit is meant for a PC with one). The run is compared with the previous Stress
run on the same PC (15 % slower = flagged: ``core.SLOWER_BY_MODE``) and written as a table next to the report
(``core.stress_csv``).

``FRESING_PCCHECK_STRESS_SMALL=1`` makes the small model (a few hundred parts, seconds): tests and a quick look.
Without a graphics card (GitHub) the Solid view is skipped when it cannot start and the render is small, on the
processor.
"""

from __future__ import annotations

import functools
import json
import math
import os
import subprocess
import sys
import threading
import time

from .checks import _check, _update, line
from .heavy import peak_memory_mb

S = "stress"
SMALL_ENV = "FRESING_PCCHECK_STRESS_SMALL"
TABLE_NAME = "Fresing Render stress table.csv"
SINCE = "0.2.234"


def small() -> bool:
    return os.environ.get(SMALL_ENV, "") == "1"


def current_memory_mb() -> float:
    """The memory this program (Blender) uses now, in MB: Windows the working set, Linux the resident size."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class COUNTERS(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            psapi = ctypes.WinDLL("psapi", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(COUNTERS), wintypes.DWORD]
            psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
            c = COUNTERS()
            c.cb = ctypes.sizeof(COUNTERS)
            if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return c.WorkingSetSize / 2 ** 20
        except Exception:  # noqa: BLE001
            pass
        return 0.0
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for ln in fh:
                if ln.startswith("VmRSS:"):
                    return int(ln.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


class MemoryWatch:
    """The highest memory use while a line runs (sampled four times a second in a thread): the program's own peak
    since its start (``peak_memory_mb``) says nothing about one line once an earlier line used more."""

    def __init__(self, every: float = 0.25):
        self.every = every
        self.peak = current_memory_mb()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.wait(self.every):
            self.peak = max(self.peak, current_memory_mb())

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_exc):
        self._stop.set()
        self._thread.join(timeout=2.0)
        self.peak = max(self.peak, current_memory_mb())
        return False


def stress_line(id: str, title: str, expected: int, limit: float, what: str, shows: str, not_shown: str,
                requires=()):
    """A Stress line: its peak memory is measured while it runs (also when it fails)."""
    def deco(fn):
        @functools.wraps(fn)
        def run(ctx):
            with MemoryWatch() as w:
                try:
                    return fn(ctx)
                finally:
                    if w.peak and ctx.result is not None:
                        ctx.metric("peak memory", round(max(w.peak, current_memory_mb())), "MB")
        return line(id, title, SINCE, (S,), requires=requires, what=what, expected=expected, shows=shows,
                    not_shown=not_shown, limit=limit)(run)
    return deco


def minutes_expected() -> int:
    """About how long the whole Stress run takes on the owner's PC (the lines' ``expected``), for the start text."""
    from . import checks
    secs = sum(ln.expected for ln in checks.LINES if S in ln.modes)
    return max(1, round(secs / 60.0))


# ---------------------------------------------------------------------------
# the model
# ---------------------------------------------------------------------------

def make_model(out: str, revision: str = "A", timeout: float = 3600) -> dict:
    """``stress_scene.py`` as its own program (Blender's Python with the bundled OpenCascade, like the Heavy machine);
    returns its numbers (placed, unique, fasteners, faces, seconds …)."""
    from ..importer import runner as import_runner
    env = dict(os.environ)
    for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(var, None)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stress_scene.py")
    info = os.path.splitext(out)[0] + ".info.json"
    cmd = [import_runner.python_executable(), script, out, "--revision", revision, "--json", info]
    if small():
        cmd.append("--small")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True,
                            encoding="utf-8", errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    from . import runner
    t0 = time.time()
    try:
        while proc.poll() is None:              # Cancel works while it runs (it takes about a minute)
            if runner.cancel_requested() or time.time() - t0 > timeout:
                proc.kill()
                proc.wait()
                runner.check_cancel()
                raise RuntimeError(f"making the stress model took longer than {timeout / 60:.0f} minutes")
            time.sleep(0.5)
        text = proc.stdout.read() if proc.stdout else ""
    finally:
        if proc.stdout:
            proc.stdout.close()
    if proc.returncode != 0 or not os.path.isfile(out) or not os.path.isfile(info):
        raise RuntimeError("the stress model could not be written: " + text.strip()[-300:])
    with open(info, encoding="utf-8") as fh:
        return json.load(fh)


def _step(ctx) -> str:
    path = getattr(ctx, "stress_step", "")
    if not path or not os.path.isfile(path):
        raise RuntimeError("the stress model was not made")
    return path


def _triangles(scene) -> tuple[int, int]:
    """(triangles of every placed part, of the unique parts) as the app's meshes hold them."""
    import numpy as np

    from ..blender import build
    per_mesh: dict = {}
    placed = 0
    for o in build.iter_parts(scene):
        me = o.data
        n = per_mesh.get(me.name)
        if n is None:
            sizes = np.empty(len(me.polygons), np.int32)
            me.polygons.foreach_get("loop_total", sizes)
            n = per_mesh[me.name] = int((sizes - 2).sum())
        placed += n
    return placed, sum(per_mesh.values())


def _root(scene):
    from ..blender import build
    roots = build.model_roots(scene)
    _check(bool(roots), "no model in the project")
    return roots[0]


# ---------------------------------------------------------------------------
# lines
# ---------------------------------------------------------------------------

@stress_line("stress.model", "Stress model is made", 45, 120,
             what="An invented offshore substation topside of about 11,000 placed parts (2,000 unique, 44 % bolts, "
                  "nuts and washers, B-spline cables, lofts and fillets) is written as a STEP file in a temporary folder",
             shows="That OpenCascade can write a very big assembly here, and how big such a file gets",
             not_shown="Anything about your own models: it is made up and deleted afterwards")
def stress_model(ctx):
    out = os.path.join(ctx.work, "stress_topside.step")
    t0 = time.time()
    info = make_model(out)
    ctx.stress_step = out
    ctx.stress_info = info
    ctx.metric("make", time.time() - t0, "s")
    ctx.metric("file", round(os.path.getsize(out) / 1e6, 1), "MB")
    ctx.metric("parts placed", info["placed"], "")
    ctx.metric("unique parts", info["unique"], "")
    ctx.metric("fasteners", round(100 * info["fastener_share"]), "%")
    ctx.metric("faces (unique)", info["faces_unique"], "")
    return f"{info['placed']} parts, {info['unique']} unique, {os.path.getsize(out) / 1e6:.0f} MB"


def _import(ctx, quality: str):
    from ..blender import build
    step = _step(ctx)
    t0 = time.time()
    scene = ctx.fresh(step, quality=quality, read_again=True)
    secs = time.time() - t0
    parts = list(build.iter_parts(scene))
    info = getattr(ctx, "stress_info", {})
    want = info.get("placed", 0)
    _check(len(parts) >= want * 0.99, f"only {len(parts)} of {want} parts came in")
    placed, unique = _triangles(scene)
    ctx.metric("import", secs, "s")
    ctx.metric("parts", len(parts), "")
    ctx.metric("triangles", round(placed / 1e6, 2), "M")
    ctx.metric("triangles (unique)", round(unique / 1e6, 2), "M")
    return scene, parts, placed


@stress_line("stress.import_draft", "Stress model: import at Draft", 30, 120, requires=("stress.model",),
             what="Reads the stress model's STEP file at Draft detail on all cores, builds the objects and sorts them",
             shows="How long a very big model takes to come in at the lightest detail, and the memory it needs",
             not_shown="The memory of the reader's helper programs (only the app's own)")
def stress_import_draft(ctx):
    _scene, parts, placed = _import(ctx, "draft")
    return f"{len(parts)} parts, {placed / 1e6:.1f} M triangles"


@stress_line("stress.import_normal", "Stress model: import at Normal, then from the cache", 50, 240,
             requires=("stress.model",),
             what="Reads the stress model at Normal detail (the default), then opens it once more from the import cache",
             shows="Import time at the detail you use every day; build + sort time on its own (from the cache)",
             not_shown="Fine detail (about 3 times the triangles of Normal), a network drive")
def stress_import_normal(ctx):
    _scene, parts, placed = _import(ctx, "normal")
    t0 = time.time()
    ctx.fresh(_step(ctx), quality="normal")
    ctx.metric("from cache (build + sort)", time.time() - t0, "s")
    return f"{len(parts)} parts, {placed / 1e6:.1f} M triangles"


@stress_line("stress.lists", "Stress model: sorting, Structure list, groups and search", 2, 10,
             requires=("stress.import_normal",),
             what="Sort parts into groups again, the Structure list built and drawn (with and without a search), "
                  "Find & sort parts searching 'CABLE', a group's parts selected",
             shows="Whether the side panel stays quick with 11,000 parts (each list is worked out at every redraw)",
             not_shown="Drawing the panel on your screen (the check runs without a window)")
def stress_lists(ctx):
    import bpy

    from ..blender import finder, logic, tree
    scene = ctx.scene_of("stress.import_normal")
    s = scene.fresing
    t0 = time.time()
    res = logic.apply_rules(scene)
    ctx.metric("sort parts", time.time() - t0, "s")
    t0 = time.time()
    logic.rebuild_tree(scene)
    ctx.metric("structure list", time.time() - t0, "s")
    t0 = time.time()
    rows = tree.visible_rows(s, "")
    ctx.metric("one redraw of the list", (time.time() - t0) * 1000.0, "ms")
    t0 = time.time()
    tree.visible_rows(s, "BOLT")
    ctx.metric("one redraw, searching", (time.time() - t0) * 1000.0, "ms")
    s.find_text = "CABLE"
    t0 = time.time()
    found = finder.run_search(scene)
    ctx.metric("find", time.time() - t0, "s")
    _check(found > 0, "the search for CABLE found nothing")
    big = max(range(len(s.groups)), key=lambda i: len(logic.parts_in_group(scene, s.groups[i].name)))
    s.groups_index = big
    t0 = time.time()
    bpy.ops.fresing.group_select()
    ctx.metric("select a group", time.time() - t0, "s")
    n_sel = len(bpy.context.selected_objects)
    for o in bpy.context.selected_objects:
        o.select_set(False)
    return (f"{res['parts']} parts in {res['groups']} groups, {len(rows)} list rows, {found} names found, "
            f"{n_sel} selected")


@stress_line("stress.select", "Stress model: select all, hover highlight", 2, 10, requires=("stress.import_normal",),
             what="Every part selected and deselected; then 60 mouse positions over the model worked out as the hover "
                  "highlight does (a ray into the model, the CAD face under it)",
             shows="Selecting a whole big model, and the time per mouse move while picking an axis",
             not_shown="The outline drawing of a selection on your screen")
def stress_select(ctx):
    import statistics

    import bpy
    from mathutils import Vector

    from ..blender import build, hover
    scene = ctx.scene_of("stress.import_normal")
    parts = list(build.iter_parts(scene))
    t0 = time.time()
    for o in parts:
        o.select_set(True)
    _update()
    ctx.metric("select all", time.time() - t0, "s")
    t0 = time.time()
    for o in parts:
        o.select_set(False)
    _update()
    ctx.metric("deselect all", time.time() - t0, "s")
    dg = bpy.context.evaluated_depsgraph_get()
    lo = Vector((min(o.matrix_world.translation.x for o in parts), min(o.matrix_world.translation.y for o in parts), 0))
    hi = Vector((max(o.matrix_world.translation.x for o in parts), max(o.matrix_world.translation.y for o in parts), 0))
    top = max(o.matrix_world.translation.z for o in parts) + 30.0
    times, hits = [], 0
    for i in range(60):
        u, v = (i % 10 + 0.5) / 10.0, (i // 10 + 0.5) / 6.0
        origin = Vector((lo.x + (hi.x - lo.x) * u, lo.y + (hi.y - lo.y) * v, top))
        direction = Vector((0.0, 0.0, -1.0))            # straight down onto the roof, the crane and the decks
        t0 = time.perf_counter()
        h = hover.look(scene, dg, origin, direction)
        times.append((time.perf_counter() - t0) * 1000.0)
        hits += 1 if h.part else 0
    ctx.metric("hover, mean", statistics.mean(times), "ms")
    ctx.metric("hover, slowest", max(times), "ms")
    _check(hits >= 15, f"only {hits} of 60 mouse positions found a part")       # gratings let rays through
    return f"{len(parts)} parts; hover {statistics.mean(times):.1f} ms per mouse move ({hits} of 60 on a part)"


def _camera(scene):
    """A three-quarter camera on the whole model (as Render image's default view)."""
    from ..blender import cameras
    cameras.add_camera(scene, "ISO", name="Stress view")
    scene.camera.data.lens = 35.0
    return scene.camera


@stress_line("stress.solid", "Stress model: Solid view, first picture and turning", 20, 120,
             requires=("stress.import_normal",),
             what="The model drawn as the Solid view draws it (Workbench) at 1920 x 1080: the first picture, then 12 "
                  "pictures while the camera turns round it",
             shows="How long the 3D view needs for its first picture of a big model and how many pictures a second it "
                   "manages while you turn it",
             not_shown="Your screen's own refresh and the side panel drawn beside it")
def stress_solid(ctx):
    import bpy
    from mathutils import Matrix
    scene = ctx.scene_of("stress.import_normal")
    cam = _camera(scene)
    r = scene.render
    before = (r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath)
    out = os.path.join(ctx.work, "solid.png")
    try:
        r.engine = "BLENDER_WORKBENCH"
        scene.display.shading.light = "STUDIO"
        r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
        r.filepath = out
        t0 = time.time()
        try:
            bpy.ops.render.render(write_still=True)
        except RuntimeError as exc:
            ctx.gpu_optional(exc)
            raise
        first = time.time() - t0
        ctx.metric("first picture", first, "s")
        pivot = cam.matrix_world.copy()
        centre = sum((o.matrix_world.translation for o in scene.objects if o.type == "MESH"),
                     cam.matrix_world.translation * 0) / max(1, sum(1 for o in scene.objects if o.type == "MESH"))
        t0 = time.time()
        for k in range(12):
            turn = Matrix.Translation(centre) @ Matrix.Rotation(math.radians(5 * (k + 1)), 4, "Z") @ \
                Matrix.Translation(-centre)
            cam.matrix_world = turn @ pivot
            bpy.ops.render.render(write_still=False)
        fps = 12.0 / max(1e-6, time.time() - t0)
        ctx.metric("turning", fps, "pictures/s")
        cam.matrix_world = pivot
    finally:
        r.engine, r.resolution_x, r.resolution_y, r.resolution_percentage, r.filepath = before
    ctx.picture(out, "stress_solid", "Stress model, Solid view", model_check=False, gpu_optional=True, width=760,
                settings="1920 × 1080, Workbench (Solid view)")
    return f"first picture {first:.1f} s, {fps:.1f} pictures a second while turning"


@stress_line("stress.live", "Stress model: Live preview's first picture", 15, 60, requires=("stress.import_normal",),
             what="A Cycles picture at the Live preview's size and samples (960 x 540, 4 samples), on the graphics card "
                  "when there is one: what you wait for before Live preview shows the model",
             shows="The start-up of Cycles on a big model: building its scene (BVH) and the first samples",
             not_shown="The picture getting sharper afterwards, a final render (see the 4K line)")
def stress_live(ctx):
    from ..blender import render
    scene = ctx.scene_of("stress.import_normal")
    if scene.camera is None:
        _camera(scene)
    s = scene.fresing
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 960, 540
    s.use_gpu = ctx.has_gpu
    path = os.path.join(ctx.work, "live.png")
    info = render.render_still(scene, s, "draft", filepath=path)
    ctx.metric("first picture", info["seconds"], "s")
    ctx.picture(path, "stress_live", "Stress model, first Live-preview picture", model_check=False, width=760,
                settings=f"{info['size'][0]} × {info['size'][1]}, Cycles Draft, {info['device']}")
    return f"{info['seconds']:.1f} s on {info['device']}"


# --- joints, Build, drag, clash -------------------------------------------------------------------------

def make_joints(scene, sheet: dict) -> int:
    """The maker's joints (crane slew, boom, hoist; davit; room doors) through ``joints.create`` – the buttons' own
    call – on the parts the sheet names by their importer uids."""
    from mathutils import Vector

    from ..blender import build, joints, logic
    root = _root(scene)
    scope = root.get(build.PROP_UID_SCOPE, "")
    by_uid = {}
    for o in [root] + list(logic.descendants(root)):
        u = o.get(build.PROP_UID)
        if u:
            by_uid[u[len(scope):] if scope and u.startswith(scope) else u] = o
    M = root.matrix_world
    done: dict = {}
    js = sheet["joints"]
    order, seen = [], set()
    while len(order) < len(js):                     # a joint after the one it rides on
        for j in js:
            if j["name"] not in seen and (not j.get("rides_on") or j["rides_on"] in seen):
                order.append(j)
                seen.add(j["name"])
    with joints._batch(scene):
        for j in order:
            objs = [by_uid[u] for u in j["parts"] if u in by_uid]
            _check(len(objs) == len(j["parts"]), f"joint '{j['name']}': its parts are missing in the model")
            origin = M @ (Vector(j["axis"]["point"]) / 1000.0)
            direction = (M.to_3x3() @ Vector(j["axis"]["direction"])).normalized()
            base = done[j["rides_on"]].motion if j.get("rides_on") else None
            jt = joints.create(scene, "ROTATE" if j["type"] == "rotate" else "SLIDE", objs, origin, direction,
                               name=j["name"], base=base)
            lim = j.get("limits")
            if lim is not None:
                if jt.kind == "ROTATE":
                    jt.rot_min, jt.rot_max = math.radians(lim[0]), math.radians(lim[1])
                else:
                    jt.slide_min, jt.slide_max = lim[0] / 1000.0, lim[1] / 1000.0
                jt.use_limits = True
            done[j["name"]] = jt
    return len(order)


def _joint(scene, ending: str):
    for j in scene.fresing.joints:
        if j.name.endswith(ending):
            return j
    raise RuntimeError(f"the stress model has no joint '… {ending}'")


def _animation(scene, seconds: float):
    """Slew 120°, boom up 20°, hook down 4 m, davit 90°, every door open 90°, over ``seconds``."""
    a = scene.fresing.animations.get("Stress") or scene.fresing.animations.add()
    a.name, a.fps, a.tail, a.quality, a.video = "Stress", "25", 0.0, "preview", "MP4"
    while len(a.blocks):
        a.blocks.remove(0)
    t = seconds
    steps = [(_joint(scene, ": Slew"), 0.0, t * 0.6, {"to_angle": math.radians(120)}),
             (_joint(scene, ": Boom luff"), t * 0.2, t * 0.5, {"to_angle": math.radians(20)}),
             (_joint(scene, ": Hoist"), t * 0.4, t * 0.6, {"to_dist": 4.0}),
             (_joint(scene, ": Davit slew"), 0.0, t * 0.5, {"to_angle": math.radians(90)})]
    steps += [(j, t * 0.1, t * 0.4, {"to_angle": math.radians(90)}) for j in scene.fresing.joints
              if j.name.endswith(": Swing")]
    for j, start, dur, extra in steps:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing, b.use_from = "JOINT", j.name, start, dur, "LINEAR", False
        for k, v in extra.items():
            setattr(b, k, v)
    return a


@stress_line("stress.build", "Stress model: joints, Build and playback", 8, 30, requires=("stress.import_normal",),
             what="The crane's slew, boom and hoist, the davit and every room door made as joints; a 10 s animation "
                  "of them built (Build), then played frame by frame",
             shows="Making joints, Build and playback on a big model whose moving parts are a small share of it",
             not_shown="Cables, hoses and drag chains that follow the motion (their own lines in Heavy)")
def stress_build(ctx):
    from ..blender import animation
    scene = ctx.scene_of("stress.import_normal")
    with open(os.path.splitext(_step(ctx))[0] + ".joints.json", encoding="utf-8") as fh:
        sheet = json.load(fh)
    t0 = time.time()
    n = make_joints(scene, sheet)
    _update()
    ctx.metric("make joints", time.time() - t0, "s")
    ctx.metric("joints", n, "")
    a = _animation(scene, 2.0 if small() else 10.0)
    t0 = time.time()
    frames = animation.bake(scene, a)["frames"]
    ctx.metric("build", time.time() - t0, "s")
    t0 = time.time()
    for f in range(1, frames + 1):
        scene.frame_set(f)
    ms = (time.time() - t0) * 1000.0 / frames
    ctx.metric("playback", ms, "ms/frame")
    ctx.metric("frames", frames, "")
    scene.frame_set(1)
    return f"{n} joints, {frames} frames, {ms:.1f} ms per frame"


@stress_line("stress.drag", "Stress model: dragging a joint", 4, 15, requires=("stress.build",),
             what="The crane's slew joint set to 40 values one after the other, the scene updated after each – what "
                  "dragging its value in 4 Motion > Joints does at every mouse move",
             shows="Whether the crane follows the mouse smoothly in a big model",
             not_shown="Drawing the view after each step (see the Solid view line)")
def stress_drag(ctx):
    from ..blender import animation, joints
    scene = ctx.scene_of("stress.import_normal")
    animation.clear_keys(scene)
    j = _joint(scene, ": Slew")
    times = []
    for k in range(40):
        t0 = time.perf_counter()
        joints.set_value(j, math.radians(3 * (k + 1)))
        _update()
        times.append((time.perf_counter() - t0) * 1000.0)
    joints.set_value(j, 0.0)
    _update()
    ms = sum(times) / len(times)
    ctx.metric("per step", ms, "ms")
    ctx.metric("slowest step", max(times), "ms")
    return f"{ms:.1f} ms per step (slowest {max(times):.0f} ms)"


@stress_line("stress.clash", "Stress model: clash check of the animation", 45, 120, requires=("stress.build",),
             what="Check for clashes on the 10 s animation: the crane slews over the roof, the hook goes down, the "
                  "doors open",
             shows="How long the clash check takes when a few hundred moving parts pass 11,000 standing ones",
             not_shown="The red parts in the view")
def stress_clash(ctx):
    from ..blender import animation, clash
    scene = ctx.scene_of("stress.import_normal")
    a = scene.fresing.animations.get("Stress") or _animation(scene, 2.0 if small() else 10.0)
    animation.bake(scene, a)
    t0 = time.time()
    run = clash.check(scene, store=False)
    secs = time.time() - t0
    st = run.stats
    ctx.metric("clash check", secs, "s")
    ctx.metric("moments", st["moments"] + st["between"], "")
    ctx.metric("clashes", len(run.rows), "")
    _check(st["moments"] > 0, "the check went through no frame")
    return f"{st['parts']} parts, {st['moments']} frames + {st['between']} between: {len(run.rows)} clashes"


@stress_line("stress.save", "Stress model: save and open", 5, 15, requires=("stress.build",),
             what="The project with the model, its joints and animation saved as a .blend file, then opened again",
             shows="Save and open times of a big project and how big its file gets",
             not_shown="A slow network drive")
def stress_save(ctx):
    import bpy
    ctx.scene_of("stress.import_normal")
    path = os.path.join(ctx.work, "Stress project.blend")
    t0 = time.time()
    bpy.ops.wm.save_as_mainfile(filepath=path)
    ctx.metric("save", time.time() - t0, "s")
    ctx.metric("project file", round(os.path.getsize(path) / 1e6, 1), "MB")
    t0 = time.time()
    bpy.ops.wm.open_mainfile(filepath=path)
    ctx.metric("open", time.time() - t0, "s")
    scene = bpy.context.scene
    _check(_joint(scene, ": Slew") is not None, "the joints are gone after opening the project again")
    return f"{os.path.getsize(path) / 1e6:.0f} MB"


@stress_line("stress.backup", "Stress model: an automatic backup", 2, 10, requires=("stress.save",),
             what="An automatic backup copy of the open big project written into a temporary folder (what the app does "
                  "every few minutes while you work)",
             shows="How long the app is busy with a backup of a big project",
             not_shown="Cleaning up old backups (the Full check tests that)")
def stress_backup(ctx):
    from ..blender import backups
    path = os.path.join(ctx.work, "Backups", "Stress project backup.blend")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t0 = time.perf_counter()
    backups.write_copy(path)
    secs = time.perf_counter() - t0
    _check(os.path.isfile(path), "no backup was written")
    ctx.metric("backup", secs, "s")
    ctx.metric("backup file", round(os.path.getsize(path) / 1e6, 1), "MB")
    return f"{secs:.1f} s"


@stress_line("stress.undo", "Stress model: Undo after a big action", 10, 30, requires=("stress.save",),
             what="Every part sorted into groups again (Sort parts) and then undone with Undo, as Ctrl+Z does",
             shows="How long you wait for Undo in a big project (Blender keeps a copy of the whole project per step)",
             not_shown="Undo of an import or a model update (it works the same way: the whole project)")
def stress_undo(ctx):
    import bpy

    from ..blender import build
    scene = bpy.context.scene
    n = sum(1 for _ in build.iter_parts(scene))
    bpy.ops.ed.undo_push(message="Before the stress action")
    t0 = time.time()
    res = bpy.ops.fresing.apply_rules()
    ctx.metric("sort parts", time.time() - t0, "s")
    _check(res == {"FINISHED"}, f"Sort parts returned {res}")
    t0 = time.time()
    bpy.ops.ed.undo_push(message="Sort parts")         # what a button with Undo does after its work
    ctx.metric("undo step", time.time() - t0, "s")
    if not bpy.ops.ed.undo.poll():
        from .core import Skipped
        raise Skipped("skipped: no undo history here (Blender as a Python module keeps none)")
    t0 = time.time()
    res = bpy.ops.ed.undo()
    ctx.metric("undo", time.time() - t0, "s")
    _check(res == {"FINISHED"}, f"Undo returned {res}")
    _check(sum(1 for _ in build.iter_parts(bpy.context.scene)) == n, "the parts changed with the Undo")
    return None


@stress_line("stress.render", "Stress model: Render image 4K", 120, 600, requires=("stress.import_normal",),
             what="Render image of the whole model from a three-quarter view: 3840 x 2160, Preview, on the graphics "
                  "card (without one: Draft on the processor, 480 x 270)",
             shows="Render time and whether a big model fits the graphics card's memory at 4K",
             not_shown="Final quality (about 4 times the samples), graphics-card memory use (not readable here)")
def stress_render(ctx):
    import bpy

    from ..blender import render
    scene = bpy.context.scene
    if scene.camera is None:
        _camera(scene)
    s = scene.fresing
    s.out_format = "custom"
    if ctx.has_gpu:
        s.out_custom_w, s.out_custom_h, quality = 3840, 2160, "preview"
    else:
        s.out_custom_w, s.out_custom_h, quality = 960, 540, "draft"
    s.use_gpu = ctx.has_gpu
    path = os.path.join(ctx.work, "stress_4k.png")
    info = render.render_still(scene, s, quality, filepath=path)
    ctx.metric("render", info["seconds"], "s")
    ctx.picture(path, "stress_render", "Stress model, Render image", model_check=False, width=760,
                settings=f"{info['size'][0]} × {info['size'][1]}, Cycles {quality}, {info['device']}")
    return f"{info['size'][0]} × {info['size'][1]} in {info['seconds']:.0f} s on {info['device']}"


@stress_line("stress.web3d", "Stress model: web 3D model", 60, 180, requires=("stress.import_normal",),
             what="The whole model saved as a web 3D model (.glb, Texture size 1024, compressed: the panel's default) "
                  "and read back",
             shows="How long the web 3D export of a very big model takes and how big the file gets",
             not_shown="How fast a browser shows it (open the page on a phone)")
def stress_web3d(ctx):
    import bpy

    from ..blender import web3d
    from ..core import web3d as core
    out = web3d.export(bpy.context.scene, os.path.join(ctx.work, "web3d", "Stress model.glb"), size=1024)
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file breaks the glTF rules: {bad[:2]}")
    ctx.metric("export", out["seconds"], "s")
    ctx.metric("file", round(len(data) / 1e6, 1), "MB")
    return out["text"]


@stress_line("stress.update", "Stress model: model update with about 1 % changed", 120, 360, requires=("stress.save",),
             what="A second revision of the model (about 1 % of the placed parts changed: cables re-routed, a cabinet "
                  "type, a spool, valve bonnets, the boom's sheave) is made and read in with Model update",
             shows="How long a model update of a big model takes when only a few parts changed, and that the joints "
                   "stay",
             not_shown="An update where most parts changed (about a fresh import)")
def stress_update(ctx):
    import bpy

    from ..blender import build, joints
    scene = bpy.context.scene
    n_joints = len(scene.fresing.joints)
    out = os.path.join(ctx.work, "stress_topside_rev_b.step")
    t0 = time.time()
    info = make_model(out, revision="B")
    ctx.metric("make revision B", time.time() - t0, "s")
    ctx.metric("parts changed", info["changed_placed"], "")
    ctx.metric("share changed", round(100.0 * info["changed_placed"] / max(1, info["placed"]), 1), "%")
    root = _root(scene)
    t0 = time.time()
    res = bpy.ops.fresing.import_step(filepath=out, quality="normal", update_root=root.name)
    secs = time.time() - t0
    _check(res == {"FINISHED"}, f"the model update returned {res}: {scene.fresing.last_message}")
    _update()
    ctx.metric("model update", secs, "s")
    scene = bpy.context.scene
    _check(len(scene.fresing.joints) == n_joints and all(joints.is_valid(j) for j in scene.fresing.joints),
           "the model update lost joints")
    parts = sum(1 for _ in build.iter_parts(scene))
    _check(parts >= info["placed"] * 0.99, f"only {parts} of {info['placed']} parts after the update")
    return f"{info['changed_placed']} of {info['placed']} parts changed; joints kept"


def write_table(run, folder: str) -> str:
    """The Stress table next to the report (CSV, opens in Excel); returns its path."""
    from . import core
    path = os.path.join(folder, TABLE_NAME)
    core.write_text(path, core.stress_csv(run))
    return path
