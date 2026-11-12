"""Demo project "Cable-lay vessel" (task 0077): Help > Make demo project.

One click writes the invented cable-lay vessel spread (``demo_model/``, tasks 0076 + 0084), imports it and sets it up
the way the owner would – groups and looks, every joint of the joint sheet (stacks, couplings, a "Cable travel" slide
joint the cable-turned rollers follow), the quadrant handler's cylinders, the open sea, saved cameras, a brand kit –
and saves a ready project with the animation **"What it can do today"**. Everything goes through the app's own
functions (the same calls the buttons make), so the project is exactly what a user would have made.

    Documents\\Fresing Render\\Demo\\<version>\\Demo cable-lay vessel <version>.blend   the project
    Documents\\Fresing Render\\Demo\\<version>\\model\\                                  STEP files + the two sheets
    Documents\\Fresing Render\\Demo\\<version>\\making.json                              only while it is made

The menu item starts a background Blender (``pccheck/launcher.py -- demobuild <folder>``, ``build_main``), which runs
the model maker as its own program and then the stages below; the app shows the progress and can cancel at any moment
(``ops_demo.py``). A demo that failed or was cancelled leaves nothing behind (its folder is deleted).

ADDING TO THE DEMO (tasks 0078–0082: cable, tensioner tracks, spooling, catenary, quadrant operations): the project is
built as a list of small named **stages**, run in order::

    @stage("rollers", "Shot: roller highways")
    def shot_rollers(d: Demo):
        a = d.animation                         # "What it can do today"
        d.joint(CABLE, d.t, 8.0, 1.33, slide=True, label="Rollers turn with the cable")
        d.t += 8.0                              # the shot's length: the next shot starts there

A later task adds a stage (``@stage("cable", "Cable on its path", after="joints")``) or replaces one by giving the
same id (``@stage("rollers", …)`` again: the newest wins, its place stays). Shots run in order and each advances
``d.t`` (seconds on the animation's time line), so a shot put between two others moves the later ones along. Keep a
stage small and name what it shows; ``d.progress()`` inside a long loop keeps the status bar alive and lets Cancel in.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

TITLE = "Demo cable-lay vessel"
ANIM = "What it can do today"
CABLE = "Cable travel"                # the slide joint (m of cable paid out) every cable-turned part follows
SEA_SHOT = "Open sea"
QUAY_SHOT = "Loading at the quay"
TAG = "fr_demo"                       # on the scene of the demo project: the version
MODEL_KEYS = ("assembly", "quay_loading")
QUAY_PREFIX = "QUAY: "                # in front of the quay file's joint names (its sheet names them on their own)
SPEED = 10.0                          # m/min of cable while laying (0083)
LAPSE = 10                            # time-lapse factor of the carousel shot
MIN_JOINTS = 315                      # the joint sheet's 314 + Cable travel (the quay's come on top)


class Cancelled(Exception):
    """Cancel was pressed: the build stops and its folder is deleted."""


# ---------------------------------------------------------------------------
# where things go
# ---------------------------------------------------------------------------

def default_folder() -> str:
    from . import tour
    return os.path.join(tour.documents_dir(), "Fresing Render", "Demo")


def project_dir(folder: str, version: str) -> str:
    return os.path.join(folder, version)


def project_path(folder: str, version: str) -> str:
    return os.path.join(project_dir(folder, version), f"{TITLE} {version}.blend")


def model_dir(folder: str, version: str) -> str:
    return os.path.join(project_dir(folder, version), "model")


def progress_path(folder: str, version: str) -> str:
    """Written while the demo is made (stage, counts, the helper programs' ids); deleted when it is ready."""
    return os.path.join(project_dir(folder, version), "making.json")


def summary_path(folder: str, version: str) -> str:
    """A few numbers of the finished demo (the test tour's stop reads them without opening the project)."""
    return os.path.join(project_dir(folder, version), "demo.json")


def read_summary(folder: str, version: str) -> dict:
    try:
        with open(summary_path(folder, version), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def cancel_path(folder: str, version: str) -> str:
    return os.path.join(project_dir(folder, version), "cancel")


def exists(folder: str, version: str) -> bool:
    """A finished demo of this version is there (not one that is being made)."""
    return os.path.isfile(project_path(folder, version)) and not os.path.isfile(progress_path(folder, version))


def read_progress(folder: str, version: str) -> dict:
    try:
        with open(progress_path(folder, version), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path: str, data: dict) -> None:
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def remove(folder: str, version: str) -> str:
    """Delete the demo of this version (a half-made one too). '' when gone, else why not."""
    d = project_dir(folder, version)
    for _ in range(10):
        shutil.rmtree(d, ignore_errors=True)
        if not os.path.exists(d):
            return ""
        time.sleep(0.3)                     # Windows: a helper program may still hold a file for a moment
    return f"could not delete {d} (a file in it is open)"


def is_demo(scene) -> bool:
    return bool(scene.get(TAG))


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

@dataclass
class Stage:
    id: str
    title: str
    fn: Callable


STAGES: list[Stage] = []


def stage(id: str, title: str, after: str = ""):
    """Register a stage (see the module docstring). Same id: replaces that stage in its place. ``after``: put a new
    stage right after the one with that id (default: at the end)."""
    def deco(fn):
        st = Stage(id, title, fn)
        for i, old in enumerate(STAGES):
            if old.id == id:
                STAGES[i] = st
                return fn
        at = next((i + 1 for i, s in enumerate(STAGES) if s.id == after), len(STAGES)) if after else len(STAGES)
        STAGES.insert(at, st)
        return fn
    return deco


class Demo:
    """What a stage gets: the scene, the files, the sheets, the animation and its time cursor ``t``."""

    def __init__(self, scene, folder: str, version: str, small: bool = False, progress=None):
        self.scene = scene
        self.folder = folder
        self.version = version
        self.small = small                  # the PC check's scaled-down form (GitHub): Draft meshes, no quay
        self.quay = not small
        self._progress = progress
        self.stage = ""
        self.timings: dict[str, float] = {}
        self.notes: list[str] = []
        self.t = 0.0
        self._sheets: dict = {}

    @property
    def s(self):
        return self.scene.fresing

    @property
    def dir(self) -> str:
        return project_dir(self.folder, self.version)

    @property
    def model_dir(self) -> str:
        return model_dir(self.folder, self.version)

    def file(self, key: str) -> str:
        from ..demo_model import layout
        return os.path.join(self.model_dir, layout.FILES[key])

    def sheet(self, which: str) -> dict:
        """'joints' or 'route': the model maker's JSON sheets."""
        if which not in self._sheets:
            from ..demo_model import layout
            name = layout.JOINTS_JSON if which == "joints" else layout.ROUTE_JSON
            with open(os.path.join(self.model_dir, name), encoding="utf-8") as fh:
                self._sheets[which] = json.load(fh)
        return self._sheets[which]

    def progress(self, text: str = "", done: int = 0, total: int = 0) -> None:
        """Status line for the app ("Joints 120/307") and the moment Cancel gets in."""
        if os.path.isfile(cancel_path(self.folder, self.version)):
            raise Cancelled()
        if self._progress:
            self._progress(self.stage, text, done, total)

    # ---- lookups ----
    def by_uid(self, scope: str = "") -> dict:
        from . import build
        return {o.get(build.PROP_UID): o for o in self.scene.objects if o.get(build.PROP_UID)}

    def root(self, key: str = "assembly"):
        from . import build
        want = os.path.normcase(os.path.abspath(self.file(key)))
        for r in build.model_roots(self.scene):
            if os.path.normcase(os.path.abspath(r.get(build.PROP_SOURCE, ""))) == want:
                return r
        raise RuntimeError(f"the demo model {os.path.basename(self.file(key))} is not in the project")

    def part(self, name: str, n: int = 0, root=None):
        """The n-th object named ``name`` (CAD name) in the model, by its ID."""
        from . import build, logic
        objs = logic.descendants(root) if root is not None else self.scene.objects
        hits = sorted((o for o in objs if o.get(build.PROP_NAME) == name), key=lambda o: o.get(build.PROP_UID))
        if len(hits) <= n:
            raise RuntimeError(f"the demo model has no part '{name}'")
        return hits[n]

    def uid(self, uid: str):
        from . import build
        for o in self.scene.objects:
            if o.get(build.PROP_UID) == uid:
                return o
        raise RuntimeError(f"the demo model has no part {uid}")

    def mm(self, p, key: str = "assembly"):
        """A model point (mm, the sheets) as a world point (m)."""
        from mathutils import Vector
        return self.root(key).matrix_world @ (Vector(p) / 1000.0)

    # ---- the animation ----
    @property
    def animation(self):
        a = self.s.animations.get(ANIM)
        if a is None:
            a = self.s.animations.add()
            a.name, a.tail, a.fps = ANIM, 0.5, "25"
            a.quality, a.out_resolution, a.out_format, a.video = "preview", "hd", "presentation", "MP4"
        return a

    def joint(self, joint: str, start: float, seconds: float, to: float, slide: bool = False, label: str = "",
              easing: str = "SMOOTH"):
        """A Move joint step (to: m for a slide joint, degrees for a rotate joint)."""
        blk = self.animation.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", joint, start, seconds, easing
        blk.use_from = True
        if slide:
            blk.to_dist = to
        else:
            blk.to_angle = math.radians(to)
        blk.name = label
        return blk

    def camera_step(self, mode: str, start: float, seconds: float, label: str = "", **kw):
        blk = self.animation.blocks.add()
        blk.kind, blk.camera_mode, blk.start, blk.duration = "CAMERA", mode, start, seconds
        for k, v in kw.items():
            setattr(blk, k, v)
        blk.name = label
        return blk

    def middle(self, ob):
        """The middle of a part's box (world)."""
        from mathutils import Vector
        return sum((ob.matrix_world @ Vector(c) for c in ob.bound_box), Vector()) / 8.0

    def camera(self, name: str, at, target, lens: float = 35.0):
        """A saved camera at ``at`` looking at ``target`` (model mm; or a part: ``at`` is then an offset in mm
        from its middle), and its saved scene of the same name."""
        from mathutils import Vector

        from . import cameras, states
        cam = cameras.add_camera(self.scene, "ISO", lens, name)
        if isinstance(target, str):
            tgt = self.middle(self.part(target, root=self.root()))
            loc = tgt + Vector(at) / 1000.0
        else:
            loc, tgt = self.mm(at), self.mm(target)
        from mathutils import Matrix
        cam.matrix_world = Matrix.Translation(loc) @ (tgt - loc).to_track_quat("-Z", "Y").to_matrix().to_4x4()
        cam.data.clip_end = max(cam.data.clip_end, 2000.0)
        self.scene.camera = cam
        states.save_shot(self.scene, name)
        return cam


def _update():
    import bpy
    bpy.context.view_layer.update()


# ---------------------------------------------------------------------------
# model: the maker as its own program, then the import
# ---------------------------------------------------------------------------

def _run_maker(d: Demo) -> None:
    """``demo_model/make.py`` with Blender's Python and the bundled OpenCascade (like the PC check's heavy_scene)."""
    from ..importer import runner as import_runner
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo_model", "make.py")
    prog = os.path.join(d.model_dir, "maker.json")
    env = dict(os.environ)
    for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(var, None)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    log = os.path.join(d.model_dir, "maker log.txt")
    keys = MODEL_KEYS if d.quay else ("assembly",)
    os.makedirs(d.model_dir, exist_ok=True)
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.Popen([import_runner.python_executable(), script, d.model_dir, "--only", ",".join(keys),
                                 "--progress", prog], stdout=fh, stderr=subprocess.STDOUT, env=env,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        d.helper_pid = proc.pid
        try:
            while proc.poll() is None:
                try:
                    with open(prog, encoding="utf-8") as pf:
                        p = json.load(pf)
                except (OSError, ValueError):
                    p = {}
                if p.get("stage") == "write":
                    d.progress(f"Writing the model {int(p.get('done', 0)) + 1}/{p.get('total', len(keys))}")
                else:
                    d.progress("Making the model's shapes")
                time.sleep(0.5)
        except Cancelled:
            proc.kill()
            proc.wait()
            raise
        finally:
            d.helper_pid = 0
    if proc.returncode != 0 or not all(os.path.isfile(d.file(k)) for k in keys):
        with open(log, encoding="utf-8", errors="replace") as fh:
            tail = fh.read().strip()[-300:]
        raise RuntimeError(f"the demo model could not be written: {tail}")
    for f in (prog, log):
        try:
            os.remove(f)
        except OSError:
            pass


def _import(d: Demo, key: str) -> None:
    import bpy
    quality = "draft" if d.small else "normal"
    res = bpy.ops.fresing.import_step(filepath=d.file(key), quality=quality)
    if res != {"FINISHED"}:
        raise RuntimeError(f"the import of {os.path.basename(d.file(key))} returned {res}: {d.s.last_message}")


@stage("model", "The model (written, imported)")
def make_model(d: Demo):
    d.progress("Making the model's shapes")
    t0 = time.time()
    _run_maker(d)
    d.timings["write"] = time.time() - t0
    d.progress("Importing")
    t0 = time.time()
    _import(d, "assembly")
    if d.quay:
        _import(d, "quay_loading")
    d.timings["import"] = time.time() - t0


# ---------------------------------------------------------------------------
# looks (0083 item 8): deep blue machinery, orange accents, yellow structure, grey deck, rubber pads, black cable
# ---------------------------------------------------------------------------

LOOKS = [
    # group, material, colour, part names (CAD names), only inside these machines ('' = anywhere)
    ("Demo: machinery blue", "paint_marine", "RAL 5010",
     ("TENSIONER BASE FRAME", "TOP TRACK FRAME", "CABLE ENGINE FRAME", "TOP WHEEL FRAME", "WINCH BASE FRAME",
      "HYDRAULIC MOTOR", "PLANETARY GEARBOX", "DRIVE BRACKET", "WINCH PEDESTAL"), ()),
    ("Demo: orange", "paint_marine", "RAL 2004",
     ("RIM FENCE", "TURNTABLE", "BARREL", "TOP TRACK LIFT FRAME", "CPS RAMP", "CPS SLIDE", "INNER CORE",
      "WINCH DRUM", "DRUM FLANGE", "LEBUS RISER"), ()),
    ("Demo: yellow structure", "paint_marine", "RAL 1003",
     ("ROLLER CRADLE", "ROLLER STAND", "ROLLER TRESTLE", "TOWER COLUMN", "ARCH", "ARCH FRAME", "GUIDE CAGE",
      "GUIDE FRAME", "SLEW HOUSING", "RADIUS CONTROLLER", "CHUTE", "CHUTE SUPPORT", "RAMP SUPPORT", "CPS RACK",
      "QUADRANT FRAME", "QUADRANT GUTTER", "HANDLER FRAME", "RAIL TRESTLE", "RAIL BOGIE", "SHEAVE POST",
      "SHEAVE HEAD", "HINGE BRACKET", "CYLINDER BRACKET", "CYLINDER LUG", "ROLLER BRACKET", "FOOT FRAME",
      "CRADLE LIFT FRAME", "A&R PAD EYE", "PAD EYE", "HANDLER TOP PULLEY", "TIPPING SHEAVE", "FOOT SHEAVE"), ()),
    ("Demo: deck grey", "paint_marine", "RAL 7037", ("MAIN DECK", "CAROUSEL WELL"), ()),
    ("Demo: walkways", "paint_marine", "RAL 6011", ("GRATING WALKWAY",), ()),
    ("Demo: rubber pads", "rubber_black", "", ("TRACK PAD", "CABLE ENGINE WHEEL"), ()),
    ("Demo: steel", "steel_raw", "", ("PAD BACK PLATE", "TRACK CHAIN LINK", "DRIVE SPROCKET", "IDLER SPROCKET",
                                       "QUADRANT RAIL"), ()),
    ("Demo: rollers", "steel_machined", "", ("CABLE ROLLER", "GUIDE ROLLER", "SUPPORT ROLLER", "RAIL WHEEL"), ()),
    ("Demo: power cable", "cable_black", "", ("CABLE", "CABLE COIL", "CABLE END"), ()),
    ("Demo: wire rope", "galvanized", "", ("WIRE ROPE",), ()),
]


@stage("looks", "Groups and looks")
def looks(d: Demo):
    from . import build, logic
    names = {}
    for group, _mat, _col, parts, _within in LOOKS:
        for n in parts:
            names[n] = group
    n = 0
    for ob in build.iter_parts(d.scene):
        g = names.get(ob.get(build.PROP_NAME))
        if g:
            ob["fr_group_manual"] = g                 # as "Assign selected" does
            n += 1
    for group, mat, col, _parts, _within in LOOKS:
        g = logic.ensure_group(d.s, group)
        g.material = mat
        if col:
            g.color = col
    logic.apply_rules(d.scene)
    logic.refresh_group_materials(d.scene)
    d.notes.append(f"looks: {n} parts in {len(LOOKS)} demo groups")


# ---------------------------------------------------------------------------
# joints: every joint of the sheet; the cable-turned ones follow "Cable travel"
# ---------------------------------------------------------------------------

def _sheet_order(js: list[dict]) -> list[dict]:
    """Leaders and the joints others ride on first."""
    by = {j["name"]: j for j in js}
    out, done = [], set()

    def add(j, seen=()):
        if j["name"] in done or j["name"] in seen:
            return
        for dep in (j.get("rides_on"), j["drive"].get("follows")):
            if dep and dep in by:
                add(by[dep], seen + (j["name"],))
        done.add(j["name"])
        out.append(j)
    for j in js:
        add(j)
    return out


def make_joints(d: Demo, js: list[dict], key: str = "assembly", prefix: str = "", cable: str = CABLE) -> int:
    """The sheet's joints through ``joints.create`` / ``set_follows`` (the buttons' own calls). Returns the count."""
    from mathutils import Vector

    from . import build, joints
    sc = d.scene
    root = d.root(key)
    scope = root.get(build.PROP_UID_SCOPE, "")
    by_uid = {}
    for o in [root] + list(_descendants(root)):
        u = o.get(build.PROP_UID)
        if u:
            by_uid[u[len(scope):] if scope and u.startswith(scope) else u] = o
    M = root.matrix_world
    order = _sheet_order(js)
    total = len(order)
    with joints._batch(sc):
        for i, j in enumerate(order):
            if i % 10 == 0:
                d.progress(f"Joints {i}/{total}", i, total)
            objs = [by_uid[u] for u in j["parts"] if u in by_uid]
            if len(objs) != len(j["parts"]):
                raise RuntimeError(f"joint '{j['name']}': parts missing in the model")
            origin = M @ (Vector(j["axis"]["point"]) / 1000.0)
            direction = (M.to_3x3() @ Vector(j["axis"]["direction"])).normalized()
            base = None
            if j.get("rides_on"):
                below = joints.find(sc, prefix + j["rides_on"])
                base = below.motion if below is not None else None     # (made in this batch: fine, task 0093)
            jt = joints.create(sc, "ROTATE" if j["type"] == "rotate" else "SLIDE", objs, origin, direction,
                               name=prefix + j["name"], base=base)
            if jt.name != prefix + j["name"]:
                raise RuntimeError(f"joint '{j['name']}' got the name '{jt.name}'")
            lim = j.get("limits")
            if lim is not None:
                if jt.kind == "ROTATE":
                    jt.rot_min, jt.rot_max = math.radians(lim[0]), math.radians(lim[1])
                else:
                    jt.slide_min, jt.slide_max = lim[0] / 1000.0, lim[1] / 1000.0
                jt.use_limits = True
        for j in order:                                 # couplings once every joint is there
            drive = j["drive"]
            jt = sc.fresing.joints.get(prefix + j["name"])
            if drive.get("by") == "follows":
                joints.set_follows(sc, jt, prefix + drive["follows"], ratio=float(drive["ratio"]))
            elif drive.get("by") in ("cable", "carousel") and cable and "deg_per_mm" in drive:
                if not waits_for_tracks(j["name"]):
                    joints.set_follows(sc, jt, cable, ratio=float(drive["deg_per_mm"]))
            joints.apply_limits(jt, joints._model_size(sc))
    return total


def waits_for_tracks(name: str) -> bool:
    """The tensioners' track sprockets: turned alone (the track chain stands still until task 0079 runs it) their
    teeth would go through the chain's links. They get their joint, but follow the cable only once the tracks run."""
    return name.startswith("TENSIONER") and "sprocket" in name.lower()


def turning_in_place(scene) -> list:
    """The parts that only turn about their own round axis (rollers, sheaves, wheels, drums, the carousel with its coil)
    and the static cable: what the test's clash check leaves out (``tests/test_demo_project.py``). Such a part sweeps
    only its own room, so it cannot run into anything it does not touch at the start; checked frame by frame, the
    300 rollers made the check take hours on this model (task 0077, open point for the clash lane). The D-quadrant's
    rail wheels too (task 0091): in the time-lapse they turn ~170° a frame, and the check's step between two frames
    (one screw motion) then carries a rolling wheel's centre off its straight path into the rail."""
    from . import build, joints
    out = []
    for j in scene.fresing.joints:
        if j.kind != "ROTATE":
            continue
        top = joints.driver_of(scene, j)
        if top is None or not (top.name in (CABLE, TRAVEL) or top.name.endswith("Drum turn")):
            continue
        for m in joints.members(j):
            out.append(m)
            out += [o for o in m.children_recursive if o.get(build.PROP_KIND) == "part"]
    out += [o for o in build.iter_parts(scene) if o.get(build.PROP_NAME) == "CABLE"]
    return out


def _descendants(root):
    from . import logic
    return logic.descendants(root)


@stage("joints", "Joints")
def make_all_joints(d: Demo):
    from mathutils import Vector

    from . import build, joints
    sc = d.scene
    t0 = time.time()
    deck = d.part("MAIN DECK", root=d.root())
    # "Cable travel": metres of cable paid out towards the sea; moves nothing itself (task 0078 puts the cable on it)
    with joints._batch(sc):
        cab = joints.create(sc, "SLIDE", [], d.mm((0.0, 0.0, 3000.0)), Vector((-1.0, 0.0, 0.0)), name=CABLE,
                            base=deck, allow_empty=True)
    cab.use_limits = False
    n = make_joints(d, d.sheet("joints")["joints"], "assembly")
    if d.quay:
        quay = d.sheet("joints")["machine_files"].get("demo_quay_loading.step", [])
        n += make_joints(d, quay, "quay_loading", QUAY_PREFIX, cable="")
    joints.refresh_couplings(sc)
    d.timings["joints"] = time.time() - t0
    d.notes.append(f"joints: {n} from the sheets + {CABLE}")
    del build


# ---------------------------------------------------------------------------
# cylinders: the quadrant handler's two (pin points in the route sheet); the tensioners' four lift cylinders have no
# pin points in the sheet: their rods ride on the lift joint as the sheet says
# ---------------------------------------------------------------------------

def _nearest(d: Demo, name: str, point):
    """The part called ``name`` whose middle is nearest to ``point`` (world)."""
    from mathutils import Vector

    from . import build
    best, dist = None, 1e30
    for o in build.iter_parts(d.scene):
        if o.get(build.PROP_NAME) != name:
            continue
        c = sum((o.matrix_world @ Vector(v) for v in o.bound_box), Vector()) / 8.0
        if (c - point).length < dist:
            best, dist = o, (c - point).length
    if best is None:
        raise RuntimeError(f"the demo model has no part '{name}'")
    return best


@stage("cylinders", "Cylinders")
def make_cylinders(d: Demo):
    from mathutils import Vector

    from . import cylinders
    h = d.sheet("route")["quadrant"]["handler"]
    axis = (d.root().matrix_world.to_3x3() @ Vector(h["axis"])).normalized()
    made = 0
    for k, c in enumerate(h["cylinders"]):
        asm, rod = d.uid(c["barrel"]), d.uid(c["rod"])
        barrel = [o for o in asm.children if o is not rod]          # the sheet names the cylinder's assembly
        bp, rp = d.mm(c["barrel_pin"]), d.mm(c["rod_pin"])
        frame = d.part("HANDLER FRAME", root=d.root())             # the handler tilt's part: carries the rod pin
        cyl, _notes = cylinders.create(d.scene, barrel, [rod], (bp, axis, barrel[0]), (rp, axis, rod),
                                       barrel_carrier=_nearest(d, "CYLINDER BRACKET", bp), rod_carrier=frame,
                                       name=f"Handler cylinder {'port' if c['barrel_pin'][1] > 0 else 'stb'}")
        made += 1
    d.notes.append(f"cylinders: {made} (quadrant handler, follow the handler tilt)")


# ---------------------------------------------------------------------------
# wires that move with their ends (task 0095): the A&R wire and the two tipping wires
# ---------------------------------------------------------------------------
#
# Demo parts, not an app function (the moving cable of task 0078 may replace them). Everything is Blender's own:
# empties ride on the parts with a Child Of constraint (inverse = identity), a straight piece is a 1 m cylinder kept on
# its start by Copy Location and stretched to its end by Stretch To, the turn over a sheave is a curve along the
# groove whose visible part (bevel start/end) a simple-expression driver of the joint values sets. So they work with
# scripts off, in the render queue and at any frame rate. A sheave's tangent point is an empty at the sheave's centre
# that turns about the axle towards the wire's far end (Locked Track) with a child one rope radius out, square to that
# direction: with the far end metres away it lies within a few mm of the true tangent (the wire cuts ~1 mm into the
# groove at most). None of these objects is a part: the clash check, the model tree and Build leave them alone.

WIRES = "FR demo wires"               # the collection
WIRE_TAG = "fr_demo_wire"             # on every object of the wires: which wire
DRUM_TILT = "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn on tilt"


def _wire_coll(d: Demo):
    import bpy
    c = bpy.data.collections.get(WIRES)
    if c is None:
        c = bpy.data.collections.new(WIRES)
        d.scene.collection.children.link(c)
    return c


def _frame(origin, x=None, y=None):
    """A world matrix at ``origin`` whose y axis is ``y`` (and x as near ``x`` as square to it)."""
    from mathutils import Matrix, Vector
    y = Vector(y).normalized() if y is not None else Vector((0, 1, 0))
    x = Vector(x) if x is not None else Vector((1, 0, 0))
    x = (x - y * x.dot(y))
    x = x.normalized() if x.length > 1e-9 else y.orthogonal().normalized()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = origin
    return m


def _rider(d: Demo, name: str, wire: str, carrier, M):
    """An empty that rides on ``carrier`` (a part) at the world matrix ``M`` (as the scene stands now)."""
    import bpy
    from mathutils import Matrix
    ob = bpy.data.objects.new(name, None)
    _wire_coll(d).objects.link(ob)
    ob.empty_display_size = 0.05
    ob[WIRE_TAG] = wire
    ob.hide_select = True
    ob.matrix_basis = carrier.matrix_world.inverted() @ M
    con = ob.constraints.new("CHILD_OF")
    con.target = carrier
    con.set_inverse_pending = False
    con.inverse_matrix = Matrix.Identity(4)
    return ob


def _tangent(d: Demo, name: str, wire: str, carrier, centre, axle, x, r: float, towards, side: float):
    """The tangent point on a sheave (centre, axle, rope radius r) for a wire running on to ``towards`` (an object):
    an aim empty turning about the axle towards it, and the point r out square to that direction (``side`` +-1)."""
    import bpy
    from mathutils import Matrix
    aim = _rider(d, name + " aim", wire, carrier, _frame(centre, x, axle))
    lt = aim.constraints.new("LOCKED_TRACK")
    lt.target = towards
    lt.lock_axis, lt.track_axis = "LOCK_Y", "TRACK_X"
    t = bpy.data.objects.new(name, None)
    _wire_coll(d).objects.link(t)
    t.empty_display_size = 0.05
    t[WIRE_TAG] = wire
    t.hide_select = True
    t.parent = aim
    t.matrix_parent_inverse = Matrix.Identity(4)
    t.location = (0.0, 0.0, side * r)
    return t


def _material(d: Demo):
    """The wire ropes' look (the group "Demo: wire rope")."""
    from . import build
    for ob in build.iter_parts(d.scene):
        if ob.get(build.PROP_NAME) == "WIRE ROPE" and ob.active_material is not None:
            return ob.active_material
    return None


def _straight(d: Demo, name: str, wire: str, start, end, radius: float):
    """A straight wire piece from ``start`` to ``end`` (objects): a 1 m cylinder along y, Copy Location + Stretch To."""
    import bpy
    me = bpy.data.meshes.get("FR wire piece %.4f" % radius)
    if me is None:
        import bmesh
        me = bpy.data.meshes.new("FR wire piece %.4f" % radius)
        bm = bmesh.new()
        n = 12
        ring0 = [bm.verts.new((radius * math.cos(2 * math.pi * k / n), 0.0, radius * math.sin(2 * math.pi * k / n)))
                 for k in range(n)]
        ring1 = [bm.verts.new((v.co.x, 1.0, v.co.z)) for v in ring0]
        for k in range(n):
            bm.faces.new((ring0[k], ring0[(k + 1) % n], ring1[(k + 1) % n], ring1[k]))
        bm.faces.new(ring0[::-1])
        bm.faces.new(ring1)
        bm.to_mesh(me)
        bm.free()
        for poly in me.polygons:
            poly.use_smooth = True
        mat = _material(d)
        if mat is not None:
            me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    _wire_coll(d).objects.link(ob)
    ob[WIRE_TAG] = wire
    ob.hide_select = True
    cl = ob.constraints.new("COPY_LOCATION")
    cl.target = start
    st = ob.constraints.new("STRETCH_TO")
    st.target = end
    st.rest_length = 1.0
    st.volume = "NO_VOLUME"
    st.keep_axis = "PLANE_Z"
    return ob


def _arc(d: Demo, name: str, wire: str, carrier, M, pts, radius: float):
    """A wire along ``pts`` (in the frame ``M``, world as the scene stands now) riding on ``carrier``: a poly curve
    with a round bevel whose start / end factors (along its length) drivers set."""
    import bpy
    from mathutils import Matrix
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.use_fill_caps = True
    cu.bevel_factor_mapping_start = cu.bevel_factor_mapping_end = "SPLINE"
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p_, q in zip(sp.points, pts):
        p_.co = (q[0], q[1], q[2], 1.0)
    mat = _material(d)
    if mat is not None:
        cu.materials.append(mat)
    ob = bpy.data.objects.new(name, cu)
    _wire_coll(d).objects.link(ob)
    ob[WIRE_TAG] = wire
    ob.hide_select = True
    ob.matrix_basis = carrier.matrix_world.inverted() @ M
    con = ob.constraints.new("CHILD_OF")
    con.target = carrier
    con.set_inverse_pending = False
    con.inverse_matrix = Matrix.Identity(4)
    return ob


def _drive(ob, path: str, expr: str, variables: dict, index: int = -1):
    """A simple-expression driver: ``variables`` name -> (object, data path)."""
    fc = ob.driver_add(path, index) if index >= 0 else ob.driver_add(path)
    drv = fc.driver
    drv.type = "SCRIPTED"
    for n, (target, dp) in variables.items():
        v = drv.variables.new()
        v.name = n
        v.targets[0].id = target
        v.targets[0].data_path = dp
    drv.expression = expr
    if not drv.is_simple_expression:
        raise RuntimeError(f"the wire's driver '{expr}' is not a simple expression")
    return fc


def _poly(xs, ys, deg: int = 4) -> str:
    """A polynomial through the samples as a simple expression in ``t`` (Horner)."""
    import numpy as np
    c = np.polyfit(np.asarray(xs, float), np.asarray(ys, float), deg)
    out = f"{c[0]:.9g}"
    for a in c[1:]:
        out = f"({out}) * t + {a:.9g}"
    return out


def _angle_in(M, ob) -> float:
    """The angle (rad, from x towards z) of an object's world place in the frame M."""
    p_ = M.inverted() @ ob.matrix_world.translation
    return math.atan2(p_.z, p_.x)


@stage("wires", "Wires that move: A&R wire, tipping wires", after="cylinders")
def make_wires(d: Demo):
    """The A&R wire from its drum to the D's eye at the top of the curve (over the handler's top pulley once the handler
    tilts) and the tipping wires from the swivel posts over their sheaves to a parked end, or to the D's bottom corners
    once it is on the handler (task 0095). Sampled at 51 tilts to set the drivers of the turns over the sheaves."""
    import numpy as np
    from mathutils import Vector

    from . import joints
    sc = d.scene
    W = d.sheet("route")["wires"]
    tilt, trav = sc.fresing.joints[TILT], sc.fresing.joints[TRAVEL]
    tmax = trav.slide_max
    t_var = {"t": (tilt.motion, f'["{joints.VALUE}"]')}
    v_var = {"v": (trav.motion, f'["{joints.VALUE}"]')}
    on = f"(v > {tmax - 0.001:.6f})"                         # the D is at the end of its travel, on the handler
    R = d.root().matrix_world.to_3x3()
    vec = lambda v: (R @ Vector(v)).normalized()  # noqa: E731
    _update()
    # ---- the A&R wire
    a = W["ar"]
    rd, rp = a["drum_r"] / 1000.0, a["pulley_r"] / 1000.0
    rr = a["rope_d"] / 2000.0
    drum_car, eye_car, pul_car = d.uid(a["drum_carrier"]), d.uid(a["eye_carrier"]), d.uid(a["pulley_carrier"])
    X = vec((1.0, 0.0, 0.0))
    dc = _rider(d, "A&R drum centre", "ar", drum_car, _frame(d.mm(a["drum_centre"]), X, vec(a["drum_axis"])))
    eye = _rider(d, "A&R eye", "ar", eye_car, _frame(d.mm(a["eye"]), X, vec(a["pulley_axis"])))
    t2 = _tangent(d, "A&R on pulley", "ar", pul_car, d.mm(a["pulley_centre"]), vec(a["pulley_axis"]), X, rp, dc, +1)
    end = _rider(d, "A&R wire end", "ar", eye_car, _frame(d.mm(a["eye"])))
    end.constraints.clear()
    c1 = end.constraints.new("COPY_LOCATION")
    c1.target = eye
    c2 = end.constraints.new("COPY_LOCATION")
    c2.target = t2
    d1 = _tangent(d, "A&R off drum", "ar", drum_car, d.mm(a["drum_centre"]), vec(a["drum_axis"]), X, rd, end, +1)
    t3 = _rider(d, "A&R off pulley", "ar", pul_car, _frame(d.mm(a["pulley_exit"])))
    _straight(d, "A&R wire (deck)", "ar", d1, end, rr)
    w2 = _straight(d, "A&R wire (pulley to eye)", "ar", t3, eye, rr)
    # the side of the tangent points: the one nearer the expected place (the drum's top, the pulley's top)
    _update()
    for t_, want in ((d1, d.mm(np.array(a["drum_centre"]) + [0, 0, a["drum_r"]])),
                     (t2, d.mm(np.array(a["pulley_centre"]) + [0, 0, a["pulley_r"]]))):
        if (t_.matrix_world.translation - want).length > rd:
            t_.location = -t_.location
    # the turn over the pulley: in the pulley's frame (x along the handler, z square to it), angles from x to z
    PM = _frame(d.mm(a["pulley_centre"]), X, vec(a["pulley_axis"]))
    a3 = _angle_in(PM, t3)
    thetas = np.linspace(0.0, math.radians(a["tilt_end"]), 51)
    a2 = []
    PMc = pul_car.matrix_world.inverted() @ PM               # the pulley's frame on the handler frame
    joints.set_value(trav, tmax)
    for th in thetas:
        joints.set_value(tilt, float(th))
        _update()
        _update()
        a2.append(_angle_in(pul_car.matrix_world @ PMc, t2))  # in the tilting pulley's frame
    joints.set_value(tilt, 0.0)
    joints.set_value(trav, 0.0)
    _update()
    _update()                                                # (the riders below read the parts' places at rest)
    a2 = np.unwrap(np.array(a2))
    a3 = float(a3)
    k = np.nonzero(a2 <= a3)[0]
    if not len(k) or k[0] == 0:
        raise RuntimeError("the A&R wire never bears on the top pulley")
    i = int(k[0])
    th0 = float(thetas[i - 1] + (thetas[i] - thetas[i - 1]) * (a2[i - 1] - a3) / (a2[i - 1] - a2[i]))
    lo = float(a2[-1])
    pts = [(rp * math.cos(x), 0.0, rp * math.sin(x)) for x in np.linspace(lo, a3, 48)]
    arc = _arc(d, "A&R wire (over the pulley)", "ar", pul_car, PM, pts, rr)
    sel = thetas >= th0 - 0.05
    f = (a2[sel] - lo) / (a3 - lo)
    expr = f"clamp({_poly(thetas[sel], f)}, 0.0, 1.0) if t > {th0:.6f} else 1.0"
    _drive(arc.data, "bevel_factor_start", expr, dict(t_var))
    show = f"1.0 if (t > {th0:.6f}) * {on} else 0.0"
    _drive(c2, "influence", show, dict(t_var, **v_var))
    for ax in (0, 2):
        _drive(w2, "scale", show, dict(t_var, **v_var), ax)
    d.wires = {"ar_contact_deg": round(math.degrees(th0), 2)}
    # ---- the tipping wires
    for key in ("port", "stb"):
        w = W[f"tipping_{key}"]
        r = w["head_r"] / 1000.0
        rt_ = w["rope_d"] / 2000.0
        head = d.uid(w["head_carrier"])
        eyep = d.uid(w["eye_carrier"])
        hx, hax = vec(w["head_x"]), vec(w["head_axis"])
        C = d.mm(w["head_centre"])
        HM = _frame(C, hx, hax)
        park = _rider(d, f"Tipping {key} park", key, head, _frame(d.mm(w["park"])))
        e = _rider(d, f"Tipping {key} eye", key, eyep, _frame(d.mm(w["eye"])))
        tend = _rider(d, f"Tipping {key} wire end", key, head, _frame(d.mm(w["park"])))
        tend.constraints.clear()
        k1 = tend.constraints.new("COPY_LOCATION")
        k1.target = park
        k2 = tend.constraints.new("COPY_LOCATION")
        k2.target = e
        _drive(k2, "influence", f"1.0 if {on} else 0.0", dict(v_var))
        tt = _tangent(d, f"Tipping {key} off sheave", key, head, C, hax, hx, r, tend, +1)
        _straight(d, f"Tipping wire {key}", key, tt, tend, rt_)
        _update()
        want = C + hx * r
        if (tt.matrix_world.translation - want).length > r:
            tt.location = -tt.location
        # the lead up the post's axis and the turn over the head sheave (in the head's frame)
        lead_z = (HM.inverted() @ d.mm(w["lead_start"])).z
        pts = [(-r, 0.0, lead_z), (-r, 0.0, 0.0)] + [(r * math.cos(x), 0.0, r * math.sin(x))
                                                       for x in np.linspace(math.pi, 0.0, 61)[1:]]
        lead = -lead_z
        total = lead + r * math.pi
        arc_t = _arc(d, f"Tipping wire {key} (over the sheave)", key, head, HM, pts, rt_)
        _update()
        HMh = head.matrix_world.inverted() @ HM                 # the head's frame on its carrier

        def end_factor():
            ang = _angle_in(head.matrix_world @ HMh, tt)
            return (lead + r * (math.pi - max(0.0, min(math.pi, ang)))) / total
        f_park = end_factor()
        joints.set_value(trav, tmax)
        fs = []
        for th in thetas:
            joints.set_value(tilt, float(th))
            _update()
            _update()
            fs.append(end_factor())
        joints.set_value(tilt, 0.0)
        joints.set_value(trav, 0.0)
        _update()
        _update()
        _drive(arc_t.data, "bevel_factor_end", f"clamp({_poly(thetas, fs)}, 0.0, 1.0) if {on} else {f_park:.6f}",
               dict(t_var, **v_var))
    _update()
    d.notes.append(f"wires: A&R (bears on the top pulley from {d.wires['ar_contact_deg']}° of tilt), 2 tipping wires")


# ---------------------------------------------------------------------------
# surroundings, light, saved scenes
# ---------------------------------------------------------------------------

def _water_level(d: Demo) -> float:
    """The sea's level above the model's lowest point: the waterline is z = 0 of the model (the sheets)."""
    from . import logic
    mn, _mx = logic.update_bounds(d.scene)
    return round(float(d.mm((0.0, 0.0, 0.0)).z - mn[2]), 3)


@stage("surroundings", "Sea, light and the quay scene")
def surroundings(d: Demo):
    import bpy

    from . import logic, states
    s = d.s
    res = bpy.ops.fresing.light_look(look="SUN")
    if res != {"FINISHED"}:
        raise RuntimeError(f"light look Sun returned {res}")
    s.env_detail = "SIMPLE"
    if d.quay:
        # the quay scene first: quay model shown, Quayside surroundings
        quay = d.root("quay_loading")
        s.background = "QUAY"
        s.water_level = _water_level(d)
        d.camera(QUAY_SHOT, (-36000.0, -62000.0, 36000.0), (8000.0, -18000.0, 4000.0), lens=30.0)
        # the open sea: the quay hidden
        logic.set_hidden(quay, True)
    s.background = "SEA"
    s.sea_state = "CALM"
    s.water_level = _water_level(d)
    if hasattr(s, "vessel"):                  # vessel motion (task 0085): the vessel heaves, pitches, rolls (Calm)
        s.vessel.heading = "BOW"
        s.vessel.enabled = True
        _update()
    d.camera(SEA_SHOT, (-30000.0, -52000.0, 42000.0), (36000.0, 0.0, 3000.0), lens=30.0)
    del states


# ---------------------------------------------------------------------------
# saved cameras (model mm: x to the bow, transom at 0, y to port, z up)
# ---------------------------------------------------------------------------

VIEWS = {
    "Overview": ((-30000.0, -52000.0, 42000.0), (36000.0, 0.0, 3000.0), 30.0),
    "Deck from above": ((50000.0, -45000.0, 135000.0), (52000.0, 0.0, 3000.0), 30.0),
    "Carousel": ((42000.0, -20000.0, 16000.0), (60000.0, 0.0, 4000.0), 26.0),
    "Roller highway": ((14000.0, -10500.0, 6200.0), (24000.0, -5850.0, 5000.0), 24.0),
    "Tensioner": ((21500.0, -14500.0, 8500.0), (27300.0, -5850.0, 5600.0), 30.0),
    "Handling winch": ((-2600.0, -3200.0, 1300.0), "WINCH DRUM", 45.0),
    "Stern": ((-13000.0, -21000.0, 13000.0), (6000.0, 0.0, 4000.0), 28.0),
    "Quadrant": ((-7000.0, 15000.0, 9000.0), "QUADRANT FRAME", 26.0),
}


@stage("cameras", "Saved cameras")
def saved_cameras(d: Demo):
    for name, (at, target, lens) in VIEWS.items():
        d.camera(name, at, target, lens)
    d.scene.camera = d.scene.objects.get("Overview")


@stage("brand", "Brand kit Demo")
def brand_kit(d: Demo):
    from . import tour
    s = d.s
    s.brand_name = "Demo"
    s.brand_logo = tour._logo(os.path.join(d.dir, "Demo logo.png"))
    s.brand_contact = "Fresing Render demo · an invented vessel"


# ---------------------------------------------------------------------------
# the animation "What it can do today": one stage per shot (0083's shot list as far as today's functions go)
# ---------------------------------------------------------------------------

def _uid(ob) -> str:
    from . import build
    return ob[build.PROP_UID]


@stage("shot_fly", "Shot 1: fly round the vessel")
def shot_fly(d: Demo):
    from . import build
    a = d.animation
    a.start_shot = "Overview"
    a.fin_title_on, a.fin_end_on, a.fin_captions = True, True, True
    a.fin_title, a.fin_subtitle = "Cable-lay vessel", "What Fresing Render can do today · an invented vessel"
    a.fin_title_seconds = a.fin_end_seconds = 3.0
    a.fin_logo = "BR"
    carousel = d.part("TURNTABLE", root=d.root())
    fly = d.camera_step("PATH", d.t, 6.0, "On a calm sea", easing="LINEAR", cam_blend=0.0, path_look="PART",
                        aim_uid=_uid(carousel), aim_name=carousel.get(build.PROP_NAME, "TURNTABLE"))
    for p in ((95000.0, -70000.0, 30000.0), (40000.0, -85000.0, 26000.0), (-15000.0, -60000.0, 24000.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    hull = d.part("HULL", root=d.root())
    d.camera_step("RIDE", d.t + 6.0, 3.0, "", target_uid=_uid(hull), target_name="HULL", cam_blend=0.5,
                  ride_level=True)                       # then the camera rides with the vessel on the swell
    d.t += 9.0


@stage("shot_deck", "Shot 2: the deck from above")
def shot_deck(d: Demo):
    cam = d.scene.objects.get("Deck from above")
    d.camera_step("MOVE", d.t, 2.0, "The deck: carousel, highways, tensioners, quadrant", camera=cam)
    d.camera_step("ORBIT", d.t + 2.0, 4.0, "", orbit_angle=math.radians(20.0), easing="LINEAR")
    d.t += 6.0


@stage("shot_carousel", "Shot 3: carousel and arch")
def shot_carousel(d: Demo):
    cam = d.scene.objects.get("Carousel")
    secs = 10.0
    metres = SPEED / 60.0 * secs * LAPSE                 # 10 m/min real, time-lapse x 10
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.joint(CABLE, d.t, secs, metres, slide=True, easing="LINEAR",
            label=f"Carousel turns, the arch follows (x {LAPSE})")
    d.joint("LOADING TOWER: Arch slew", d.t, secs, 6.0, easing="SMOOTH")
    d.t += secs
    d.cable_end = metres


@stage("shot_rollers", "Shot 4: roller highways")
def shot_rollers(d: Demo):
    secs = 7.0
    start = getattr(d, "cable_end", 0.0)
    metres = start + SPEED / 60.0 * secs * 3              # x 3
    cam = d.scene.objects.get("Roller highway")
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    fly = d.camera_step("PATH", d.t, secs, "Rollers turn with the cable (x 3)", easing="LINEAR", cam_blend=0.0,
                        path_look="AHEAD")
    for p in ((22000.0, -9800.0, 6000.0), (34000.0, -9200.0, 6200.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    d.joint(CABLE, d.t, secs, metres, slide=True, easing="LINEAR")
    d.t += secs
    d.cable_end = metres


TENSIONER = "TENSIONER 2"
LABELS = (("TRACK PAD", "Track pads (rubber)"), ("DRIVE SPROCKET", "Drive sprocket"),
          ("PISTON ROD", "Lift cylinder"), ("TOP TRACK LIFT FRAME", "Lift frame"))
XRAY_STEP = "X-ray: the tensioner's frames"


@stage("shot_tensioner", "Shot 5: tensioner opens and squeezes, X-ray with labels")
def shot_tensioner(d: Demo):
    from . import build, callouts
    cam = d.scene.objects.get("Tensioner")
    t = d.t
    d.camera_step("CUT", t, 0.0, "", camera=cam)
    lift, tilt = f"{TENSIONER}: Top track lift", f"{TENSIONER}: Top track tilt"
    d.joint(lift, t, 3.0, 0.6, slide=True, label="The top track lifts (real speed)")
    d.joint(tilt, t + 3.0, 3.0, 20.0, label="… and tilts out of the line")
    d.joint(tilt, t + 6.5, 2.5, 0.0)
    d.joint(lift, t + 9.0, 3.0, -0.02, slide=True, label="It closes and squeezes the cable")
    t += 12.0
    ten = next(o for o in d.root().children_recursive if o.get(build.PROP_UID, "").endswith("/TENSIONER#2"))
    frames = [o for o in ten.children_recursive if o.get(build.PROP_NAME) in ("TENSIONER BASE FRAME",
                                                                                "TOP TRACK FRAME")]
    for k, fr in enumerate(frames):
        blk = d.animation.blocks.add()
        blk.kind, blk.start, blk.duration, blk.easing = "FADE_OUT", t, 1.5, "SMOOTH"
        blk.target_uid, blk.target_name = fr[build.PROP_UID], fr.get(build.PROP_NAME)
        blk.fade_xray = True
        blk.name = XRAY_STEP if k == 0 else ""
    for name, text in LABELS:
        part = next((o for o in ten.children_recursive if o.get(build.PROP_NAME) == name), None)
        if part is not None:
            from mathutils import Vector
            co = [part.matrix_world @ Vector(c) for c in part.bound_box]
            centre = sum(co, Vector()) / 8.0
            callouts.add(d.scene, part, centre, text, step=XRAY_STEP)
    d.s.callouts_on = True
    if frames:
        d.animation.blocks[len(d.animation.blocks) - len(frames)].duration = 4.0     # the labels' step: 4 s
    for fr in frames:
        f = d.animation.blocks.add()
        f.kind, f.start, f.duration, f.easing = "FADE_IN", t + 4.0, 1.0, "SMOOTH"
        f.target_uid, f.target_name = fr[build.PROP_UID], fr.get(build.PROP_NAME)
        f.fade_xray = True
    d.t = t + 5.0


@stage("shot_drum", "Shot 6: handling winch drum, depth of field")
def shot_drum(d: Demo):
    from . import cameras, states
    cam = d.scene.objects.get("Handling winch")
    drum = d.part("WINCH DRUM", root=d.root())
    keep = d.scene.camera
    d.scene.camera = cam                        # the blur setting is the active camera's
    d.s.camera_blur = "LITTLE"
    cameras.set_focus(cam, d.scene, drum, d.middle(drum))
    states.save_shot(d.scene, cam.name)
    d.scene.camera = keep
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.joint("HANDLING WINCH 1: Drum turn", d.t, 7.0, 360.0, easing="SMOOTH",
            label="Handling winch: Lebus drum, 35° crossovers and risers at the flanges")
    d.t += 7.0


QUADRANT_SPEED = 6.0                  # m/min: the D-quadrant's travel aft (an invented, plausible speed)
QUADRANT_LAPSE = 60                   # its time-lapse factor in shot 7
TRAVEL = "QUADRANT SYSTEM: Quadrant travel"
TILT = "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"
TIP = "QUADRANT SYSTEM: Quadrant tip"
TILT_TO = 100.0                       # degrees at the end of shot 7 (the tilt's whole range)
TILT_SECONDS = 4.0


def cradle_drop(d: Demo) -> tuple[str, float]:
    """The S-bend's cradles in the D's lane (task 0091): the joint the others follow and how far it drops (m)."""
    for j in d.sheet("joints")["joints"]:
        if j["name"].endswith(" drop") and j["drive"].get("by") == "operator":
            return j["name"], j["limits"][1] / 1000.0
    raise RuntimeError("the demo model has no cradle that drops")


@stage("shot_quadrant", "Shot 7: the D-quadrant travels aft, the tipping wires are connected, the handler tilts")
def shot_quadrant(d: Demo):
    """The quadrant system's whole move (tasks 0091, 0095): the S-bend's cradles in the middle lane drop, the D travels
    aft on its rails onto the handler (time-lapse) with the A&R wire paying out from its winch, the tipping wires are
    connected to the D's bottom corners, and the handler tilts over the stern carrying it: the D ends vertical, curve up,
    hanging from the A&R wire over the top pulley (the owner's pictures). It is not tipped: task 0082 lowers it into the
    sea vertical and tips it near the sea bottom. 0 clash rows over the shot (``tests/test_demo_project.py``)."""
    from . import build
    t = d.t
    cam = d.scene.objects.get("Quadrant")
    quad = d.part("QUADRANT FRAME", root=d.root())
    lead, drop = cradle_drop(d)
    travel = d.sheet("route")["quadrant"]["travel"][1] / 1000.0
    secs = round(travel / (QUADRANT_SPEED / 60.0) / QUADRANT_LAPSE, 1)
    d.camera_step("CUT", t, 0.0, "", camera=cam)
    d.joint(lead, t, 1.5, drop, slide=True, label="The S-bend's cradles drop out of the D-quadrant's way")
    t += 1.5
    d.joint(TRAVEL, t, secs, travel, slide=True, easing="SMOOTH",
            label=f"The D-quadrant travels aft onto the handler on its A&R wire (x {QUADRANT_LAPSE})")
    fly = d.camera_step("PATH", t, secs, "", easing="SMOOTH", cam_blend=0.0, path_look="PART", aim_uid=_uid(quad),
                        aim_name=quad.get(build.PROP_NAME, "QUADRANT FRAME"))
    for p in ((22000.0, 15500.0, 9500.0), (-3000.0, 15000.0, 9000.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    t += secs
    d.camera_step("MOVE", t, 1.5, "The tipping wires are connected to the D's bottom corners",
                  camera=d.scene.objects.get("Stern"))
    t += 1.0
    d.joint(TILT, t, TILT_SECONDS, TILT_TO,
            label="The handler tilts over the stern: the D hangs vertical from the A&R wire over the top pulley")
    drum = next(j for j in d.sheet("joints")["joints"] if j["name"] == DRUM_TILT)["drive"]
    k = drum["step_from"]
    d.joint(DRUM_TILT, t + k * TILT_SECONDS, (1.0 - k) * TILT_SECONDS, drum["payout_mm"] * drum["deg_per_mm"])
    t += TILT_SECONDS
    d.camera_step("ORBIT", t, 3.0, "", orbit_angle=math.radians(8.0), easing="SMOOTH")   # a hold on the end picture
    d.t = t + 3.0


@stage("finish", "Animation")
def finish(d: Demo):
    from . import animation
    sc = d.scene
    a = d.animation
    d.s.animations_index = list(d.s.animations).index(a)
    d.progress("Animation")
    t0 = time.time()
    r = animation.bake(sc, a)
    d.timings["build"] = time.time() - t0
    if r["warnings"]:
        d.notes.append("animation: " + "; ".join(r["warnings"][:3]))
    sc.frame_set(sc.frame_start)


# ---------------------------------------------------------------------------
# the whole build
# ---------------------------------------------------------------------------

def _fresh(folder: str, version: str):
    """A new empty project (the user's default template is not applied: the demo makes its own looks)."""
    import bpy
    bpy.ops.wm.read_homefile(use_empty=True)
    scene = bpy.context.scene
    scene.fresing.out_folder = os.path.join(project_dir(folder, version), "Renders")
    return scene


def build_project(folder: str, version: str = "", small: bool = False, progress=None, only=()) -> dict:
    """Make the demo project of ``version`` in ``folder`` (an older one of that version is replaced). Returns
    {"path", "seconds" per stage, "timings", "notes"}. Raises Cancelled / RuntimeError; then nothing is left."""
    import bpy

    from .. import __version__
    version = version or __version__
    gone = remove(folder, version)
    if gone:
        raise RuntimeError(gone)
    os.makedirs(project_dir(folder, version), exist_ok=True)
    state = {"stage": "", "text": "", "done": 0, "total": 0}

    def report(stage_title, text, done, total):
        state.update(stage=stage_title, text=text, done=done, total=total)
        _write_json(progress_path(folder, version), dict(state, pid=os.getpid(), helper=getattr(d, "helper_pid", 0),
                                                         version=version))
        if progress:
            progress(stage_title, text, done, total)

    _write_json(progress_path(folder, version), {"stage": "", "pid": os.getpid(), "version": version})
    out = {"path": project_path(folder, version), "seconds": {}}
    d = None
    from . import prefs as fr_prefs
    p = fr_prefs.get()
    saved_template = p.default_template if p else ""
    if p:
        p.default_template = ""
    try:
        scene = _fresh(folder, version)
        d = Demo(scene, folder, version, small, report)
        stages = [s for s in STAGES if not only or s.id in only]
        for st in stages:
            d.stage = st.title
            d.progress(st.title)
            t0 = time.time()
            st.fn(d)
            out["seconds"][st.id] = round(time.time() - t0, 1)
        scene = bpy.context.scene
        scene[TAG] = version
        d.progress("Saving")
        a = scene.fresing.animations.get(ANIM)
        _write_json(summary_path(folder, version), {
            "version": version, "joints": len(scene.fresing.joints), "cylinders": len(scene.fresing.cylinders),
            "animation": ANIM, "frames": int(scene.frame_end - scene.frame_start + 1) if a else 0,
            "seconds": round(max(b.start + b.duration for b in a.blocks), 1) if a and len(a.blocks) else 0.0,
            "small": small})
        bpy.ops.wm.save_as_mainfile(filepath=project_path(folder, version), check_existing=False)
    except BaseException:
        try:
            import bpy as _b
            _b.ops.wm.read_homefile(use_empty=True)        # let go of the files before deleting them
        except Exception:  # noqa: BLE001
            pass
        remove(folder, version)
        raise
    finally:
        if p:
            p.default_template = saved_template
    for f in (progress_path(folder, version), cancel_path(folder, version)):
        try:
            os.remove(f)
        except OSError:
            pass
    out["timings"] = {k: round(v, 1) for k, v in d.timings.items()}
    out["notes"] = d.notes
    return out


def result_path(folder: str) -> str:
    """The background build's last word (next to the version folders: it outlives a cancelled build)."""
    return os.path.join(folder, "Make demo result.json")


def build_main(folder: str = "", small: bool = False) -> int:
    """Entry point of the background Blender ``launcher.py -- demobuild [folder]``."""
    from .. import __version__
    folder = folder or default_folder()
    os.makedirs(folder, exist_ok=True)
    t0 = time.time()

    def progress(stage_title, text, done, total):
        print(f"{stage_title}: {text}" if text and text != stage_title else stage_title, flush=True)

    res = {"version": __version__, "finished": False}
    try:
        out = build_project(folder, __version__, small=small, progress=progress)
        res.update(finished=True, path=out["path"], seconds=round(time.time() - t0, 1), stages=out["seconds"],
                   timings=out["timings"], notes=out["notes"])
        code = 0
    except Cancelled:
        res.update(cancelled=True)
        code = 2
    except Exception as exc:  # noqa: BLE001 - said in the result and the log
        import traceback
        print(traceback.format_exc(), flush=True)
        res.update(error=f"{type(exc).__name__}: {exc}")
        code = 1
    _write_json(result_path(folder), res)
    print(f"Demo project: {json.dumps(res)[:1500]}", flush=True)
    return code
