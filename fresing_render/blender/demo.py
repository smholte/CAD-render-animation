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

ADDING TO THE DEMO (tasks 0079–0082: tensioner tracks, spooling, catenary, quadrant operations; 0078 added ``cable``): the project is
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
LAPSE = 90                            # time-lapse factor of the carousel shot (task 0080: 150 m, three turns come off)
MIN_JOINTS = 311                      # the joint sheet's 310 + Cable travel (the quay's come on top)


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
    ("Demo: wire rope", "galvanized", "", ("WIRE ROPE", "A&R WIRE", "TIPPING WIRE"), ()),
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
                joints.set_follows(sc, jt, cable, ratio=float(drive["deg_per_mm"]))
            joints.apply_limits(jt, joints._model_size(sc))
    return total


def turning_in_place(scene) -> list:
    """The parts that only turn about their own round axis (rollers, sheaves, wheels, drums, the carousel with its
    coil): what a clash check may leave out to save time (the cable on its path, task 0078, is left out by the
    check itself). Such a part sweeps
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
        if top is None or not (top.name in (CABLE, TRAVEL, WINCH_TRAVEL) or top.name.endswith("Drum turn")):
            continue
        for m in joints.members(j):
            out.append(m)
            out += [o for o in m.children_recursive if o.get(build.PROP_KIND) == "part"]
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
# cylinders: the quadrant handler's two and the tensioners' tilt cylinders (task 0102), pin points in the route sheet;
# the tensioners' lift cylinders stand straight under the lift frame: their rods ride on the lift joint
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# the cable on its path (task 0078)
# ---------------------------------------------------------------------------

CABLE_ITEM = "Power cable"            # the cable in 4 Motion > Cables and paths


@stage("cable", "Cable on its path", after="joints")
def cable_on_its_path(d: Demo):
    """The CAD cable becomes a cable on its path (4 Motion > Cables and paths, as the button "Add cable" does): its
    centreline is read, the bends and the rollers it rests on are found, and it gets the power-cable look whose
    yellow stripes run with "Cable travel" – the joint every cable-turned roller already follows. It stays as drawn
    (``still``): its turn round the D-quadrant's gutter does not travel with the quadrant yet (task 0082)."""
    from . import paths
    sc = d.scene
    t0 = time.time()
    d.progress("Reading the cable")
    part = d.part("CABLE", root=d.root())
    item = paths.add_cable(sc, CABLE_ITEM, joint=CABLE)
    notes = paths.read_cad(sc, item, part)
    item = paths.find(sc, CABLE_ITEM)
    item.still = True
    item.mbr = float(d.sheet("route")["cable"]["mbr"]) / 1000.0
    item.pitch, item.angle, item.stripe = 0.6, math.radians(45.0), 0.3
    d.timings["cable"] = time.time() - t0
    d.notes.append("cable: " + (notes[0] if notes else "read"))
    for n in notes[1:4]:
        d.notes.append("cable: " + n)


# ---------------------------------------------------------------------------
# the tensioners' tracks run with the cable (task 0079)
# ---------------------------------------------------------------------------

TRACK_SIDES = (("bottom", "Bottom"), ("top", "Top"))


@stage("tracks", "Tensioner tracks: the pads run with the cable", after="cable")
def tracks_stage(d: Demo):
    """Each tensioner's two tracks become tracks of 4 Motion > Tracks and belts (as "Add track" does): the two
    sprockets, one chain link, one pad and one back plate are clicked; the app finds the other 35 of each, lays the
    loop and runs the chain on "Cable travel" (the cable passes between the tracks, so its joint is the default), the
    pads on the gripping runs moving with the cable. The sprockets' own joints already follow the cable at one tooth
    per link (the joint sheet's ratio): they are kept as they are."""
    from . import joints, tracks
    sc = d.scene
    t0 = time.time()
    n = 0
    for ten in d.sheet("route")["tensioners"]:
        for key, word in TRACK_SIDES:
            tr = next(x for x in ten["tracks"] if x["name"] == key)
            d.progress(f"{ten['name']}: {key} track", n, 4)
            wheels = [joints.members(joints.find(sc, f"{ten['name']}: {word} track {which} sprocket turn"))[0]
                      for which in ("drive", "idler")]
            it = tracks.add(sc, wheels, d.uid(tr["links"][0]), [d.uid(tr["pads"][0]), d.uid(tr["back_plates"][0])],
                            name=f"{ten['name'].title()} {key} track")
            if it.joint != CABLE:
                raise RuntimeError(f"track '{it.name}' runs on '{it.joint}', not on {CABLE}")
            n += 1
            d.notes.append("tracks: " + tracks.summary(sc, it))
    d.timings["tracks"] = time.time() - t0


# ---------------------------------------------------------------------------
# the carousel and a handling winch spool their cable (task 0080)
# ---------------------------------------------------------------------------

SPOOL_ITEM = "Carousel"               # in 4 Motion > Drums and carousels
WINCH_SPOOL = "Handling winch 1"
WINCH_WIRE = "Handling wire 1"        # the handling winch's wire as a cable (its fairlead rope)
WINCH_TRAVEL = "HANDLING WINCH 1: Wire travel"     # its speed (m of wire paid out); the drum follows it by table


def _joint_ending(d: Demo, suffix: str) -> str:
    for j in d.s.joints:
        if j.name.endswith(suffix):
            return j.name
    raise RuntimeError(f"the demo has no joint '… {suffix}'")


@stage("spool", "Carousel and winch drum: the cable comes off layer by layer", after="cable")
def spool_stage(d: Demo):
    """The carousel's coil becomes a spool of the power cable on "Cable travel" (4 Motion > Drums and carousels, as
    "Add carousel" does): "Carousel turn" follows the cable by table, the loading arch slews with the layer and the
    guide's roller cage swivels along the turn. Handling winch 1 (shot 6) gets its wire on its Lebus drum the same
    way: the fairlead rope becomes a cable with its own speed joint, the drum follows it by table."""
    from mathutils import Vector

    from . import joints, paths, spool
    sc = d.scene
    t0 = time.time()
    d.progress("The carousel's coil")
    table = d.part("TURNTABLE", root=d.root())
    coil = d.part("CABLE COIL", root=d.root())
    spool.add(sc, "CAROUSEL", table, CABLE_ITEM, coil=coil, name=SPOOL_ITEM)
    for suffix, mode in (("Arch slew", "ARM"), ("Guide cage swivel", "ALONG")):
        spool.add_follower(sc, spool.find(sc, SPOOL_ITEM), _joint_ending(d, suffix), mode)
    sp = spool.find(sc, SPOOL_ITEM)
    d.notes.append("spool: " + spool.summary(sc, sp))
    d.timings["spool carousel"] = time.time() - t0
    # handling winch 1: its wire (the fairlead rope) on a speed joint of its own, the Lebus drum spools it
    t1 = time.time()
    d.progress("Handling winch 1's drum")
    root = d.root()
    from . import build, logic
    unit = joints.members(joints.find(sc, "HANDLING WINCH 1: Drum turn"))[0]      # the drum unit (turns)
    winch = build.logical_parent(unit)
    turning = {o.name for o in logic.descendants(unit)}
    parts = [o for o in logic.descendants(winch) if o.get(build.PROP_KIND) == "part"]
    rope = next(o for o in parts if o.get(build.PROP_NAME) == "WIRE ROPE" and o.name not in turning)
    drum = next(o for o in parts if o.get(build.PROP_NAME) == "WINCH DRUM" and o.name in turning)
    on_drum = next(o for o in parts if o.get(build.PROP_NAME) == "WIRE ROPE" and o.name in turning)
    deck = d.part("MAIN DECK", root=root)
    with joints._batch(sc):
        j = joints.create(sc, "SLIDE", [], d.mm((0.0, 0.0, 3000.0)), Vector((-1.0, 0.0, 0.0)), name=WINCH_TRAVEL,
                          base=deck, allow_empty=True)
    j.use_limits = False
    item = paths.add_cable(sc, WINCH_WIRE, joint=WINCH_TRAVEL)
    paths.read_cad(sc, item, rope)
    item = paths.find(sc, WINCH_WIRE)
    item.look = "ROPE"
    spool.add(sc, "DRUM", drum, WINCH_WIRE, coil=on_drum, name=WINCH_SPOOL)
    sp = spool.find(sc, WINCH_SPOOL)
    sp.groove = "LEBUS"
    # its level wind follows the layer (task 0081): the fairlead sheave stays in line with the wrap, no fleet angle
    spool.add_follower(sc, spool.find(sc, WINCH_SPOOL), "HANDLING WINCH 1: Level wind", "ACROSS")
    d.notes.append("spool: " + spool.summary(sc, spool.find(sc, WINCH_SPOOL)))
    d.timings["spool winch"] = time.time() - t1


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
    # the tensioners' tilt cylinders (task 0102): barrel pinned on the lift frame, rod on the tilting carriage
    for t in d.sheet("route")["tensioners"]:
        for k, c in enumerate(t.get("tilt_cylinders", [])):
            barrel, rod = d.uid(c["barrel"]), d.uid(c["rod"])
            ax = (d.root().matrix_world.to_3x3() @ Vector(c["axis"])).normalized()
            bp, rp = d.mm(c["barrel_pin"]), d.mm(c["rod_pin"])
            cylinders.create(d.scene, [barrel], [rod], (bp, ax, barrel), (rp, ax, rod),
                             barrel_carrier=_nearest(d, c["barrel_on"], bp), rod_carrier=_nearest(d, c["rod_on"], rp),
                             name=f"{t['name'].title()} tilt cylinder {k + 1}")
            made += 1
    d.notes.append(f"cylinders: {made} (quadrant handler: follow the handler tilt; tensioners: follow the top "
                   "track's tilt)")


# ---------------------------------------------------------------------------
# the quadrant operation's own parts (task 0082): the A&R wire, the tipping wires, the second end and its CPS set
# ---------------------------------------------------------------------------
#
# The model holds them in the CAD pose (``demo_model/layout.py``): the A&R wire from its drum to the D's eye, the
# tipping wires from the swivel posts over their head sheaves to the D's bar-end pad eyes, the cable's second end
# from the D's lane-B bar end round the gutter to the sea, and a CPS set with its pull head at the bar end. They are
# hidden (excluded) until the quadrant operation: shots 1–8 show the lay cable, and nothing reads them as a roller or a
# contact of the lay cable. Task 0082 makes them app cables (keep tight, sea end, let go) and a rider in the stage
# "wires" and shows them in shots 9–12.

AR_WIRE = "A&R WIRE"
TIPPING_WIRE = "TIPPING WIRE"


def quadrant_ops_parts(d: Demo) -> list:
    """The CAD parts (and the CPS set's assembly) of the quadrant operation: A&R wire, tipping wires, second end,
    CPS."""
    from . import build
    se = d.sheet("route")["second_end"]
    out = [o for o in build.iter_parts(d.scene) if o.get(build.PROP_NAME) in (AR_WIRE, TIPPING_WIRE)]
    return out + [d.uid(se["solid"]), d.uid(se["cps"])]


@stage("hold", "The quadrant operation's wires and second end: kept out until shot 9", after="looks")
def hold_quadrant_parts(d: Demo):
    from . import logic
    objs = quadrant_ops_parts(d)
    n = logic.exclude(objs)
    d.notes.append(f"quadrant operation: {n} parts kept out until shot 9 (wires, second end, CPS)")


AR_ITEM = "A&R wire"                  # the A&R wire straight from its drum to the D's eye (while the D travels)
AR_PULLEY_ITEM = "A&R wire over the pulley"   # the same wire once it bears on the handler's top pulley
AR_SPOOL = "A&R winch"
AR_DRUM = "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn"
PULLEY_TURN = "QUADRANT SYSTEM: QUADRANT HANDLER: Top pulley turn"
TIP_ITEMS = (("port", "Tipping wire port"), ("stb", "Tipping wire stb"))
SECOND_ITEM = "Second end"            # the cable's second end, round the D's gutter (shots 9–12)
CPS_RIDER = "CPS on the second end"
LOWER = "QUADRANT SYSTEM: Quadrant lower"


def _parts_named(d: Demo, name: str) -> list:
    from . import build
    return sorted((o for o in build.iter_parts(d.scene) if o.get(build.PROP_NAME) == name),
                  key=lambda o: o.get(build.PROP_UID))


def _rope_cable(d: Demo, name: str, part):
    """A wire rope as a cable of 4 Motion > Cables and paths (as "Add cable" and "From CAD cable" do), its own speed
    joint, the steel wire rope look."""
    from . import flex, paths
    sc = d.scene
    from . import logic
    logic.exclude([part], False)
    logic.set_hidden(part, True)
    item = paths.add_cable(sc, name)
    with flex._quiet(item):
        item.look = "ROPE"
    item["look_was"] = "ROPE"
    notes = paths.read_cad(sc, item, part)
    return paths.find(sc, name), notes


def _end_on(d: Demo, name: str, part) -> None:
    """The cable's end at ``part`` (the one nearer it) stays with that part (as "End B: this part" does)."""
    import numpy as np

    from . import paths
    sc = d.scene
    it = paths.find(sc, name)
    shape = paths.shape_now(sc, it)
    c = np.array(d.middle(part))
    end = "a" if np.linalg.norm(shape[0] - c) < np.linalg.norm(shape[-1] - c) else "b"
    paths.set_end(sc, it, end, part)


@stage("wires", "Wires that move: A&R wire, tipping wires, the second end", after="cylinders")
def make_wires(d: Demo):
    """Task 0082: the quadrant operation's wires and the cable's second end become cables of 4 Motion > Cables and paths
    (they are shown from shot 9 on: hidden here, Show steps there).

    - The A&R wire: read from the CAD wire, spooled on the A&R winch's drum (as handling winch 1, 0080), "Winch keeps
      it tight" (0082): the drum pays out what the D's travel, the tilt and the lowering need. It is in the list twice:
      straight from the drum to the D's eye (shown while the D travels and the handler starts to tilt), and the same
      wire with the handler's top pulley added (shown from where the wire meets the pulley; its speed follows the
      first's). The pulley is turned by the lowering's own steps (the wire runs over it only once the D hangs from it).
    - The tipping wires: read from the CAD wires (post top, over the head sheave, to the D's bar ends), "Winch keeps it
      tight"; the head sheave follows each wire (the app), the foot sheave and the winch drum follow its speed joint.
    - The second end: read from CABLE END (round the D's gutter, side A, horn A), the power cable look; its sea end and
      its CPS are added after shot 8 (stage "quadrant_ops")."""
    import numpy as np

    from . import joints, logic, paths, spool
    sc = d.scene
    t0 = time.time()
    objs = quadrant_ops_parts(d)
    for o in objs:                                      # each comes in when it is read (two A&R wires lie as one)
        logic.set_hidden(o, True)                       # shown in shot 9 (Show steps): not in shots 1–8
    js = {j["name"]: j for j in d.sheet("joints")["joints"]}
    # ---- the A&R wire: spooled on its drum, kept tight
    d.progress("The A&R wire")
    ar1, ar2 = _parts_named(d, AR_WIRE)
    item, notes = _rope_cable(d, AR_ITEM, ar1)
    from . import build
    unit = joints.members(joints.find(sc, AR_DRUM))[0]
    turning = {o.name for o in logic.descendants(unit)}
    parts = [o for o in logic.descendants(build.logical_parent(unit)) if o.get(build.PROP_KIND) == "part"]
    drum = next(o for o in parts if o.get(build.PROP_NAME) == "WINCH DRUM" and o.name in turning)
    coil = next(o for o in parts if o.get(build.PROP_NAME) == "WIRE ROPE" and o.name in turning)
    W = d.sheet("route")["wires"]
    spool.add(sc, "DRUM", drum, AR_ITEM, coil=coil, name=AR_SPOOL)
    paths.read_cad(sc, paths.find(sc, AR_ITEM), ar1)     # read again: now it starts on its spool, ends at the D's eye
    warn = paths.set_keep_tight(sc, paths.find(sc, AR_ITEM), True)
    if warn:
        raise RuntimeError("; ".join(warn))
    # ... and the same wire over the handler's top pulley (its speed follows the first's)
    pulley_turn = joints.find(sc, PULLEY_TURN)
    joints.set_follows(sc, pulley_turn, "")             # (it followed Cable travel: the lowering's steps turn it)
    item2, _n = _rope_cable(d, AR_PULLEY_ITEM, ar2)
    pulley = d.part("HANDLER TOP PULLEY", root=d.root())
    k = paths.add_contact(sc, paths.find(sc, AR_PULLEY_ITEM), pulley,
                          d.mm(np.array(W["ar"]["pulley_centre"]) + [0.0, 0.0, W["ar"]["pulley_r"]]))
    item2 = paths.find(sc, AR_PULLEY_ITEM)
    item2.contacts[k].turns = False
    if joints.find(sc, PULLEY_TURN).follows:
        joints.set_follows(sc, joints.find(sc, PULLEY_TURN), "")
    item = paths.find(sc, AR_ITEM)
    joints.set_follows(sc, joints.find(sc, paths.find(sc, AR_PULLEY_ITEM).joint), item.joint, ratio=1.0)
    d.notes.append("wires: " + (notes[0] if notes else AR_ITEM))
    # ---- the tipping wires: kept tight, the foot sheave and the winch drum follow the wire's speed
    for (key, name), part in zip(TIP_ITEMS, _parts_named(d, TIPPING_WIRE)):
        d.progress(f"The tipping wire {key}")
        joints.set_follows(sc, joints.find(sc, f"QUADRANT SYSTEM: Swivel sheave {key} turn"), "")
        it, notes = _rope_cable(d, name, part)
        _end_on(d, name, d.uid(W[f"tipping_{key}"]["eye_carrier"]))
        # the bend drawn for the fleet angle off the head sheave is in the air, not on a part: the wire runs straight
        # from the sheave to the D's eye wherever the D goes
        it = paths.find(sc, name)
        for i in reversed([i for i, c in enumerate(it.contacts) if c.kind == "BEND"]):
            paths.remove_contact(sc, paths.find(sc, name), i)
        it = paths.find(sc, name)
        warn = paths.set_keep_tight(sc, it, True)
        if warn:
            raise RuntimeError("; ".join(warn))
        it = paths.find(sc, name)
        sign = -1.0 if it.reverse else 1.0
        for jn in (f"QUADRANT SYSTEM: Swivel sheave {key} foot sheave turn",
                   f"QUADRANT SYSTEM: TIPPING WINCH {key.upper()}: Drum turn"):
            joints.set_follows(sc, joints.find(sc, jn), it.joint, ratio=sign * float(js[jn]["drive"]["deg_per_mm"]))
        d.notes.append("wires: " + (notes[0] if notes else name))
    # ---- the second end
    d.progress("The second end")
    part = d.uid(d.sheet("route")["second_end"]["solid"])
    logic.exclude([part, d.uid(d.sheet("route")["second_end"]["cps"])], False)
    for o in (part, d.uid(d.sheet("route")["second_end"]["cps"])):
        logic.set_hidden(o, True)
    it = paths.add_cable(sc, SECOND_ITEM)
    notes = paths.read_cad(sc, it, part)
    it = paths.find(sc, SECOND_ITEM)
    it.mbr = float(d.sheet("route")["cable"]["mbr"]) / 1000.0
    it.pitch, it.angle, it.stripe = 0.6, math.radians(45.0), 0.3
    d.notes.append("second end: " + (notes[0] if notes else "read"))
    d.timings["wires"] = time.time() - t0


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
# the cable into the sea (task 0081)
# ---------------------------------------------------------------------------

SEA_DEPTH = 30.0                      # m of water at the lay site
SEA_LAYBACK = 32.0                    # m from horn A to the touch-down: 0083's numbers for 30 m (26–39 m at 20–50 m)
SEA_LAID = 120.0                      # m already on the seabed behind the touch-down when the animation starts
SEA_CLARITY = 12.0                    # m: water clarity in the cut-away's walls
SEA_SHOT_SECONDS = 10.0
INTO_SEA = "Into the sea"             # the saved camera of shot 8


@stage("sea", "Cable into the sea: catenary to the seabed, cut-away behind the stern", after="surroundings")
def sea_stage(d: Demo):
    """The power cable hangs from horn A into the sea (4 Motion > Cables and paths > Into the sea, as the button
    does): 30 m of water, the touch-down 32 m behind the horn, 120 m already on the seabed; the vessel moves with
    the lay, so the touch-down stays behind it while the seabed passes under. The Sea gets its seabed at 30 m, a
    cut-away behind the stern placed by the cable, water clarity 12 m."""
    from . import paths, paths_sea
    sc = d.scene
    t0 = time.time()
    d.progress("The cable into the sea")
    s = d.s
    s.sea_depth = SEA_DEPTH
    item = paths.find(sc, CABLE_ITEM)
    item.sea_depth, item.sea_layback, item.sea_laid, item.sea_mode = 0.0, SEA_LAYBACK, SEA_LAID, "LAYBACK"
    notes = paths_sea.add_sea_end(sc, paths.find(sc, CABLE_ITEM))
    item = paths.find(sc, CABLE_ITEM)
    if item.problem:
        raise RuntimeError(f"the cable into the sea: {item.problem}")
    s.sea_clarity = SEA_CLARITY
    s.sea_cut_auto = True
    s.sea_cutaway = True
    _update()
    n = paths_sea.numbers(sc, item)
    d.notes.append(f"sea: layback {n['layback']:.1f} m, leaves horn A at {n['angle']:.0f}°, bottom tension "
                   f"{n['bottom']:.1f} kN, top {n['top']:.1f} kN" + (f"; {notes[0]}" if notes else ""))
    d.timings["sea"] = time.time() - t0


# ---------------------------------------------------------------------------
# saved cameras (model mm: x to the bow, transom at 0, y to port, z up)
# ---------------------------------------------------------------------------

VIEWS = {
    "Overview": ((-30000.0, -52000.0, 42000.0), (36000.0, 0.0, 3000.0), 30.0),
    "Deck from above": ((50000.0, -45000.0, 135000.0), (52000.0, 0.0, 3000.0), 30.0),
    "Carousel": ((42000.0, -20000.0, 16000.0), (60000.0, 0.0, 4000.0), 26.0),
    "Roller highway": ((12000.0, -8700.0, 6200.0), (22000.0, -4050.0, 5000.0), 24.0),
    "Tensioner": ((19000.0, -14500.0, 9500.0), (26000.0, -5000.0, 6000.0), 30.0),
    "Handling winch": ((-2600.0, -3200.0, 1300.0), "WINCH DRUM", 45.0),
    "Stern": ((-13000.0, -21000.0, 13000.0), (6000.0, 0.0, 4000.0), 28.0),
    "Quadrant": ((-7000.0, 15000.0, 9000.0), "QUADRANT FRAME", 26.0),
    INTO_SEA: ((-48000.0, -40000.0, 22000.0), (-16000.0, 0.0, -14000.0), 30.0),
    "Over the stern": ((-38000.0, -30000.0, 10000.0), (-3000.0, 0.0, -10000.0), 30.0),       # shots 10, 12 (0082)
    "At the seabed": ((-30000.0, -24000.0, 4000.0), (-6000.0, 0.0, -27000.0), 32.0),         # shot 11
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
    """Task 0080: the cable comes off the carousel's top layer turn by turn – the carousel turns by table, the arch
    slews and the guide's cage swivels with the layer (no hand-made arch step any more)."""
    cam = d.scene.objects.get("Carousel")
    secs = 10.0
    metres = SPEED / 60.0 * secs * LAPSE                 # 10 m/min real, time-lapse
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.joint(CABLE, d.t, secs, metres, slide=True, easing="LINEAR",
            label=f"The top layer pays out, the arch follows (x {LAPSE})")
    d.t += secs
    d.cable_end = metres


@stage("shot_rollers", "Shot 4: roller highways")
def shot_rollers(d: Demo):
    """Real time (task 0078): the cable runs at 10 m/min – a Run motor step on "Cable travel", speed in m/min – its
    yellow stripes pass the rollers and every roller turns with it."""
    secs = 7.0
    start = getattr(d, "cable_end", 0.0)
    cam = d.scene.objects.get("Roller highway")
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    fly = d.camera_step("PATH", d.t, secs, f"The cable runs at {SPEED:.0f} m/min: every roller turns with it",
                        easing="LINEAR", cam_blend=0.0, path_look="AHEAD")
    for p in ((20000.0, -8000.0, 6000.0), (32000.0, -7400.0, 6200.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    blk = d.animation.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", CABLE, d.t, secs, "LINEAR"
    blk.speed_mmin = SPEED
    d.t += secs
    d.cable_end = start + SPEED / 60.0 * secs


TENSIONER = "TENSIONER 2"
LABELS = (("TRACK PAD", "Track pads (rubber)"), ("DRIVE SPROCKET", "Drive sprocket"),
          ("PISTON ROD", "Lift cylinder"), ("TOP TRACK LIFT FRAME", "Lift frame"))
XRAY_STEP = "X-ray: the tensioner's frames"
TENSIONERS = ("TENSIONER 1", "TENSIONER 2")


def tensioner_open(d: Demo, name: str) -> tuple[float, float]:
    """How far a tensioner's top track lifts (m) and tilts out (deg) to open (task 0102): its lift's top limit and the
    tilt's whole range – nothing of it then stands between the two cable lines."""
    js = {j["name"]: j for j in d.sheet("joints")["joints"]}
    return js[f"{name}: Top track lift"]["limits"][1] / 1000.0, js[f"{name}: Top track tilt"]["limits"][1]


@stage("shot_tensioner", "Shot 5: tensioner opens and squeezes, X-ray with labels")
def shot_tensioner(d: Demo):
    """Task 0102, as the owner works: the top track lifts, then tilts out to the vessel's side (starboard for tensioner
    2, about its hinge along the cable on the outboard side), back, and closes on the cable. Task 0079: from the
    squeeze on the cable runs at 10 m/min and the tracks' pads run with it (also through the X-ray and its labels)."""
    from . import build, callouts
    cam = d.scene.objects.get("Tensioner")
    t = d.t
    d.camera_step("CUT", t, 0.0, "", camera=cam)
    lift, tilt = f"{TENSIONER}: Top track lift", f"{TENSIONER}: Top track tilt"
    up, out = tensioner_open(d, TENSIONER)
    d.joint(lift, t, 3.0, up, slide=True, label="The top track lifts (real speed)")
    d.joint(tilt, t + 3.0, 3.0, out, label="… then tilts out to the vessel's side, clear of the cable's line")
    d.joint(tilt, t + 6.5, 2.5, 0.0)
    d.joint(lift, t + 9.0, 3.0, -0.02, slide=True, label="It closes and squeezes the cable")
    # task 0079: from the squeeze on the cable runs again (real speed) and the pads run with it, through the X-ray
    run = 8.0
    blk = d.animation.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", CABLE, t + 9.0, run, "LINEAR"
    blk.speed_mmin = SPEED
    d.cable_end = getattr(d, "cable_end", 0.0) + SPEED / 60.0 * run
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
    d.joint(WINCH_TRAVEL, d.t, 7.0, 6.0, slide=True, easing="SMOOTH",
            label="Handling winch: the wire comes off the Lebus drum, 35° crossovers")
    d.t += 7.0


QUADRANT_SPEED = 6.0                  # m/min: the D-quadrant's travel aft (an invented, plausible speed)
QUADRANT_LAPSE = 60                   # its time-lapse factor in shot 9
TRAVEL = "QUADRANT SYSTEM: Quadrant travel"
TILT = "QUADRANT SYSTEM: QUADRANT HANDLER: Handler tilt"
TIP = "QUADRANT SYSTEM: Quadrant tip"
TILT_TO = 100.0                       # degrees at the end of shot 9 (the owner's "about 100°")
TILT_SECONDS = 4.0
AR_SPEED = 10.0                       # m/min: the A&R winch lowers and hoists the D (0083: 5–15 m/min)
TIP_MINUTES = 15.0                    # the tipping (0083: 10–20 min, est.)
OVER_THE_STERN = "Over the stern"     # the saved cameras of shots 10 and 11
AT_THE_SEABED = "At the seabed"


def cradle_drops(d: Demo) -> list[tuple[str, float]]:
    """The lanes' cradles in the D's way (task 0102: one lead joint per lane, the others of the lane follow it): each
    lead joint and how far it drops (m)."""
    out = [(j["name"], j["limits"][1] / 1000.0) for j in d.sheet("joints")["joints"]
           if j["name"].endswith(" drop") and j["drive"].get("by") == "operator"]
    if not out:
        raise RuntimeError("the demo model has no cradle that drops")
    return out


@stage("shot_sea", "Shot 8: into the sea – the catenary to the touch-down, the cable on the seabed")
def shot_sea(d: Demo):
    """From above and aft of the stern quarter, through the cut-away: the cable pays out at 10 m/min for 10 s, its
    stripes run down the catenary to the touch-down and stand still on the seabed, the seabed passes aft under the
    vessel (it moves with the lay), vessel motion Calm."""
    cam = d.scene.objects.get(INTO_SEA)
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.camera_step("ORBIT", d.t, SEA_SHOT_SECONDS, f"Into the sea: the cable hangs to the seabed {SEA_DEPTH:.0f} m "
                  f"down and is laid at {SPEED:.0f} m/min", orbit_angle=math.radians(-10.0), easing="SMOOTH")
    blk = d.animation.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", CABLE, d.t, SEA_SHOT_SECONDS, "LINEAR"
    blk.speed_mmin = SPEED
    d.t += SEA_SHOT_SECONDS


# ---------------------------------------------------------------------------
# the quadrant operation (task 0082): the second end goes over the stern on the D, into the sea, tipped off on the
# seabed (the owner's steps, tasks/0083 "Quadrant sequence")
# ---------------------------------------------------------------------------

def _cable_value_at(d: Demo, t: float) -> float:
    """Metres of 'Cable travel' at the animation's time ``t`` (its Move and Run motor steps before it)."""
    v = 0.0
    for b in sorted((b for b in d.animation.blocks if b.joint == CABLE and b.start < t), key=lambda b: b.start):
        if b.kind == "JOINT":
            v = float(b.to_dist)
        elif b.kind == "MOTOR":
            v += float(b.speed_mmin) / 60.0 * min(float(b.duration), t - float(b.start))
    return v


def _step(d: Demo, kind: str, ob, t: float, label: str = ""):
    """A Show or Hide step for a part or assembly."""
    from . import build
    blk = d.animation.blocks.add()
    blk.kind, blk.start, blk.duration = kind, t, 0.0
    blk.target_uid, blk.target_name = _uid(ob), ob.get(build.PROP_NAME, ob.name)
    blk.name = label
    return blk


def _part_of(d: Demo, name: str):
    from . import paths
    return paths.find(d.scene, name).part


def _smooth_at(share: float) -> float:
    """Where in a SMOOTH step's time a share of its way is reached."""
    return math.acos(1.0 - 2.0 * min(max(share, 0.0), 1.0)) / math.pi


def ar_contact_tilt(d: Demo) -> float:
    """The handler's tilt (deg) where the A&R wire, the D at the end of its travel, comes to bear on the top pulley."""
    from ..demo_model import layout
    from ..demo_model import route as rt
    from ..demo_model.params import Params
    p = Params()
    pos = rt.positions(p)
    W = d.sheet("route")["wires"]["ar"]
    D = [W["drum_centre"][0], W["drum_centre"][2]]
    lo, hi = 0.0, rt.TILT_END
    if layout.ar_wire_length(p, pos, D, W["drum_r"], lo)[1] or not layout.ar_wire_length(p, pos, D, W["drum_r"], hi)[1]:
        raise RuntimeError("the A&R wire does not come onto the top pulley while the handler tilts")
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if layout.ar_wire_length(p, pos, D, W["drum_r"], mid)[1] else (mid, hi)
    return hi


class _Pose:
    """The D (and the second end on its gutter) at joint values of the quadrant system, read from the model in the app
    (model mm): set, read, put back."""

    def __init__(self, d: Demo):
        from . import joints
        self.d, self.sc = d, d.scene
        q = d.sheet("route")["quadrant"]
        self.quad = d.uid(q["uid"])
        self.names = (TRAVEL, TILT, LOWER, TIP)
        self.was = {n: joints.get_value(joints.find(self.sc, n)) for n in self.names}
        self.parts = [o for o in [self.quad] + list(_descendants(self.quad)) if o.type == "MESH"]
        arc = d.sheet("route")["second_end"]["route"]["segments"][0]
        import numpy as np
        c, nrm, p0 = (np.array(arc[k], float) for k in ("centre", "normal", "start"))
        from ..demo_model.route import rotate
        self.arc = np.array([c + rotate(p0 - c, nrm, a) for a in np.linspace(0.0, math.radians(arc["angle_deg"]), 37)])
        self.M0 = self._at({})

    def _at(self, values: dict):
        import numpy as np

        from . import joints
        for n in self.names:
            joints.set_value(joints.find(self.sc, n), float(values.get(n, 0.0)))
        _update()
        _update()
        R = np.array(self.d.root().matrix_world)
        return np.linalg.inv(R) @ np.array(self.quad.matrix_world)

    def put_back(self):
        from . import joints
        for n, v in self.was.items():
            joints.set_value(joints.find(self.sc, n), v)
        _update()
        _update()

    def lows(self, values: dict) -> tuple[float, float]:
        """(lowest point of the D, lowest point of the cable round its gutter), model mm (z), at these values (m, rad)."""
        import numpy as np
        M = self._at(values)
        R = np.linalg.inv(np.array(self.d.root().matrix_world))
        zs = []
        for o in self.parts:
            W = R @ np.array(o.matrix_world)
            box = np.array([tuple(c) for c in o.bound_box]) @ W[:3, :3].T + W[:3, 3]
            zs.append(box[:, 2].min() * 1000.0)
        D = M @ np.linalg.inv(self.M0)
        arc = self.arc @ D[:3, :3].T + D[:3, 3] * 1000.0
        return float(min(zs)), float(arc[:, 2].min())


@stage("quadrant_ops", "The second end into the sea and its CPS (for shots 9–12)", after="shot_sea")
def quadrant_ops(d: Demo):
    """The second end gets its sea end where the vessel is at shot 9 (the seabed has moved aft with the cable paid out
    in shots 1–8): its catenary from horn A to the seabed as the lay cable's, 30 m of water; nothing is paid out, so its
    length is kept by the sea end alone. Its CPS set rides on it (0081), the pull head at its start, on the D's bar end;
    the stage also works out how deep the D goes (``d.quadrant``)."""
    import numpy as np

    from . import build, flex, paths, paths_riders, paths_sea
    sc = d.scene
    t0 = time.time()
    d.progress("The second end into the sea")
    item = paths.find(sc, SECOND_ITEM)
    item.sea_depth, item.sea_layback, item.sea_laid, item.sea_mode = 0.0, SEA_LAYBACK, SEA_LAID, "LAYBACK"
    notes = paths_sea.add_sea_end(sc, paths.find(sc, SECOND_ITEM))
    item = paths.find(sc, SECOND_ITEM)
    if item.problem:
        raise RuntimeError(f"the second end into the sea: {item.problem}")
    cps = d.uid(d.sheet("route")["second_end"]["cps"])
    length = d.sheet("route")["second_end"]["cps_length"] / 1000.0
    paths_riders.add(sc, item, [cps], where="END", at=float(item.sea_mark) - length, name=CPS_RIDER)
    item = paths.find(sc, SECOND_ITEM)
    r = item.riders[len(item.riders) - 1]
    head = [p for p in r.parts if p.part is not None and p.part.get(build.PROP_NAME) == "PULL HEAD"]
    if head and float(head[0].at) < 0.5 * float(r.length):
        r.flip = True                                   # its front (the bend restrictors) looks towards the sea
        item = paths.find(sc, SECOND_ITEM)
        r = item.riders[len(item.riders) - 1]
    r.at = float(item.sea_mark) - float(r.length)       # the pull head at the cable's start, on the D's bar end
    # its end lies on the seabed where it is when shot 9 starts: the seabed has passed aft by the lay cable's payout
    # of shots 1–8 by then (it moves with the lay cable, the first cable into the sea)
    lay = paths.find(sc, CABLE_ITEM)
    u = np.array(lay.sea_dir, dtype=float)
    u[2] = 0.0
    u /= max(float(np.linalg.norm(u)), 1e-12)
    ahead = _cable_value_at(d, d.t)
    with flex._quiet(item):                             # (as it is: not set again from the layback)
        item.sea_start = tuple(np.array(item.sea_start, dtype=float) - ahead * u)
    paths.changed(sc, item)
    item = paths.find(sc, SECOND_ITEM)
    r = item.riders[len(item.riders) - 1]
    # how deep: lowered with the D hanging plumb until its lowest point is 1.5 m over the seabed (shot 10), tipped
    # there towards flat (shot 11) and lowered on until the cable round its gutter lies on the seabed (let go there)
    q = d.sheet("route")["quadrant"]
    pose = _Pose(d)
    try:
        base = {TRAVEL: q["travel"][1] / 1000.0, TILT: math.radians(q["lower_tilt"])}
        hang = dict(base, **{TIP: math.radians(q["hang_tip"])})
        flat = dict(base, **{TIP: math.radians(-q["lower_tilt"])})
        bed = -SEA_DEPTH * 1000.0
        low_hang, _ = pose.lows(hang)
        l1 = (low_hang - (bed + 1500.0)) / 1000.0
        _, low_cable = pose.lows(flat)
        l2 = (low_cable - 1000.0 * paths_sea.bottom_z(sc, item)) / 1000.0
        sink = bed - pose.lows(dict(flat, **{LOWER: l2}))[0]
    finally:
        pose.put_back()
    d.quadrant = {"lower_1": round(l1, 3), "lower_2": round(l2, 3), "sink": round(sink, 1)}
    d.notes.append(f"second end: sea end {notes[0] if notes else 'set'}; CPS rider, front {r.mark:.1f} m along the "
                   f"cable; the D lowered {l1:.1f} m, tipped, lowered to {l2:.1f} m (its frame {sink:.0f} mm into "
                   "the seabed)")
    d.timings["quadrant_ops"] = time.time() - t0


@stage("shot_quadrant", "Shot 9: the D carries the second end aft and over the stern", after="quadrant_ops")
def shot_quadrant(d: Demo):
    """The owner's steps 1–7 with the cable: the lay cable gives way to the second end (its end shackled at the D's bar
    end, round the gutter, along side A and over horn A into the sea, its CPS on it). Both tensioners open – the top
    track lifts, then tilts out – and the lanes' cradles drop, the D travels aft on its rails between the tensioners onto
    the handler with the bight on it (time-lapse), the A&R wire paying out from its winch (kept tight); the tipping
    wires are connected to the D's bar ends, and the handler tilts over the stern carrying it: the A&R wire comes onto
    the top pulley, the cable leaves horn A and hangs from the D's gutter, the D ends vertical, curve up, hanging from
    the A&R wire, both legs of the cable going down into the water (tasks 0091, 0095, 0102, 0082)."""
    from . import build, paths
    t = d.t
    cam = d.scene.objects.get("Quadrant")
    quad = d.part("QUADRANT FRAME", root=d.root())
    travel = d.sheet("route")["quadrant"]["travel"][1] / 1000.0
    secs = round(travel / (QUADRANT_SPEED / 60.0) / QUADRANT_LAPSE, 1)
    d.camera_step("CUT", t, 0.0, "", camera=cam)
    _step(d, "HIDE", paths.find(d.scene, CABLE_ITEM).part, t)
    _step(d, "SHOW", _part_of(d, SECOND_ITEM), t, "The second end: shackled at the D's bar end, round its gutter, over "
                                                  "horn A into the sea, its CPS on it")
    _step(d, "SHOW", d.uid(d.sheet("route")["second_end"]["cps"]), t)
    _step(d, "SHOW", _part_of(d, AR_ITEM), t)
    for k, name in enumerate(TENSIONERS):
        up, out = tensioner_open(d, name)
        d.joint(f"{name}: Top track lift", t, 1.5, up, slide=True,
                label="Both tensioners open: the top track lifts …" if k == 0 else "")
        d.joint(f"{name}: Top track tilt", t + 1.5, 2.0, out,
                label="… and tilts out to its own side, the lanes' cradles drop: the D's way is clear"
                if k == 0 else "")
    for lead, drop in cradle_drops(d):                 # the lanes' cradles drop while the tensioners tilt out
        d.joint(lead, t + 1.5, 1.5, drop, slide=True)
    t += 3.5
    d.joint(TRAVEL, t, secs, travel, slide=True, easing="SMOOTH",
            label=f"The D-quadrant carries the cable aft between the tensioners onto the handler, on its A&R wire "
                  f"(x {QUADRANT_LAPSE})")
    fly = d.camera_step("PATH", t, secs, "", easing="SMOOTH", cam_blend=0.0, path_look="PART", aim_uid=_uid(quad),
                        aim_name=quad.get(build.PROP_NAME, "QUADRANT FRAME"))
    for p in ((22000.0, 15500.0, 9500.0), (-3000.0, 15000.0, 9000.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    t += secs
    d.camera_step("MOVE", t, 1.5, "The tipping wires are connected to the D's bar ends",
                  camera=d.scene.objects.get("Stern"))
    for _key, name in TIP_ITEMS:
        _step(d, "SHOW", _part_of(d, name), t + 0.5)
    t += 1.0
    d.joint(TILT, t, TILT_SECONDS, TILT_TO,
            label="The handler tilts over the stern: the wire comes onto the top pulley, the D hangs vertical, both "
                  "legs of the cable down into the water")
    swap = t + TILT_SECONDS * _smooth_at(ar_contact_tilt(d) / TILT_TO)
    _step(d, "HIDE", _part_of(d, AR_ITEM), swap)
    _step(d, "SHOW", _part_of(d, AR_PULLEY_ITEM), swap)
    t += TILT_SECONDS
    d.camera_step("ORBIT", t, 3.0, "", orbit_angle=math.radians(8.0), easing="SMOOTH")   # a hold on the end picture
    d.t = t + 3.0


def _pulley(d: Demo, t: float, seconds: float, lowered_m: float) -> None:
    """The top pulley turns with the wire the A&R winch pays out over it (to the angle for ``lowered_m`` of lowering)."""
    dpm = next(j for j in d.sheet("joints")["joints"] if j["name"] == PULLEY_TURN)["drive"]["deg_per_mm"]
    d.joint(PULLEY_TURN, t, seconds, lowered_m * 1000.0 * float(dpm))


@stage("shot_lower", "Shot 10: the A&R winch lowers the D vertical into the sea", after="shot_quadrant")
def shot_lower(d: Demo):
    """The owner's steps 8–10: the handler tilts on to LOWER_TILT and the D, taken by its A&R wire, hangs plumb from its
    eye (clear of the stern's horns); the A&R winch lowers it into the water and down to 1.5 m over the seabed, the
    tipping winches paying out in step (both wires kept tight), the vessel creeping on along the route (the seabed
    passes aft); from over the stern quarter through the cut-away (time-lapse)."""
    q = d.sheet("route")["quadrant"]
    l1 = d.quadrant["lower_1"]
    t = d.t
    d.camera_step("CUT", t, 0.0, "", camera=d.scene.objects.get(OVER_THE_STERN))
    d.joint(TILT, t, 2.0, q["lower_tilt"], label="The handler tilts on: the D hangs plumb from its A&R wire")
    d.joint(TIP, t, 2.0, q["hang_tip"])
    t += 2.0
    secs = 8.0
    lapse = round(l1 / (AR_SPEED / 60.0) / secs)
    d.joint(LOWER, t, secs, l1, slide=True,
            label=f"The A&R winch lowers the D into the sea, the tipping winches pay out in step, the vessel creeps on "
                  f"(x {lapse})")
    _pulley(d, t, secs, l1)
    blk = d.animation.blocks.add()                      # the vessel creeps along the route: the seabed passes aft
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", CABLE, t, secs, "LINEAR"
    blk.speed_mmin = 0.5 * l1 / secs * 60.0
    d.camera_step("ORBIT", t, secs, "", orbit_angle=math.radians(-12.0), easing="SMOOTH")
    d.t = t + secs + 1.0


@stage("shot_tip", "Shot 11: near the seabed the D tips, the cable lies on the seabed and is let go", after="shot_lower")
def shot_tip(d: Demo):
    """The owner's steps 11–13: near the seabed the A&R winch holds and the tipping winches pay out more – the D tips
    about its A&R eye towards flat; lowered onto the seabed, the cable round its gutter lies there and the second end is
    let go (its start and its turn round the gutter stay on the seabed: Let go, 0082)."""
    from . import animation, paths
    l1, l2 = d.quadrant["lower_1"], d.quadrant["lower_2"]
    q = d.sheet("route")["quadrant"]
    t = d.t
    d.camera_step("CUT", t, 0.0, "", camera=d.scene.objects.get(AT_THE_SEABED))
    secs = 5.0
    d.joint(TIP, t, secs, -q["lower_tilt"],
            label=f"Near the seabed the A&R winch holds, the tipping winches pay out: the D tips towards flat "
                  f"(x {round(TIP_MINUTES * 60.0 / secs)})")
    t += secs
    d.joint(LOWER, t, 3.0, l2, slide=True, label="Lowered onto the seabed: the cable round the gutter lies on it")
    _pulley(d, t, 3.0, l2)
    t += 3.0
    sc = d.scene
    frame = animation.frame_of(d.animation, t)
    it = paths.find(sc, SECOND_ITEM)
    gutter = [i for i, c in enumerate(it.contacts)
              if c.kind in ("CHUTE", "SHEAVE", "BEND") and c.part is not None and "QUADRANT" in c.name]
    for which in ["a"] + [str(i) for i in gutter]:
        paths.let_go(sc, paths.find(sc, SECOND_ITEM), which, frame)
    d.camera_step("ORBIT", t, 2.0, "Let go: the cable end and its CPS stay on the seabed",
                  orbit_angle=math.radians(6.0), easing="SMOOTH")
    d.t = t + 2.0


@stage("shot_back", "Shot 12: the D comes back up, over the stern and onto its rails", after="shot_tip")
def shot_back(d: Demo):
    """The owner's steps 14–15: the A&R winch hoists the D (it tips back to hang plumb on the way), the handler tilts
    back down with it (the A&R wire leaves the top pulley), the tipping wires are taken off, the D travels back along
    its rails to its stationary place; at last the tensioners' top tracks come down again and the cradles rise."""
    from . import paths
    q = d.sheet("route")["quadrant"]
    l1, l2 = d.quadrant["lower_1"], d.quadrant["lower_2"]
    t = d.t
    d.camera_step("MOVE", t, 2.0, "", camera=d.scene.objects.get(OVER_THE_STERN))
    d.joint(LOWER, t, 2.0, l1, slide=True, label="The A&R winch hoists the D off the seabed …")
    _pulley(d, t, 2.0, l1)
    t += 2.0
    secs = 6.0
    d.joint(TIP, t, 2.0, q["hang_tip"])
    d.joint(LOWER, t, secs, 0.0, slide=True,
            label=f"… and back up out of the water (x {round(l1 / (AR_SPEED / 60.0) / secs)})")
    _pulley(d, t, secs, 0.0)
    t += secs
    d.camera_step("CUT", t, 0.0, "", camera=d.scene.objects.get("Stern"))
    d.joint(TIP, t, 1.0, 0.0)
    t += 1.0
    d.joint(TILT, t, TILT_SECONDS, 0.0, label="The handler tilts back down with the D")
    swap = t + TILT_SECONDS * (1.0 - _smooth_at(ar_contact_tilt(d) / q["lower_tilt"]))
    _step(d, "HIDE", _part_of(d, AR_PULLEY_ITEM), swap)
    _step(d, "SHOW", _part_of(d, AR_ITEM), swap)
    t += TILT_SECONDS
    for _key, name in TIP_ITEMS:
        _step(d, "HIDE", _part_of(d, name), t, "The tipping wires are taken off" if _key == "port" else "")
    travel = d.sheet("route")["quadrant"]["travel"][1] / 1000.0
    secs = round(travel / (QUADRANT_SPEED / 60.0) / QUADRANT_LAPSE, 1)
    d.camera_step("MOVE", t, 2.0, "", camera=d.scene.objects.get("Quadrant"))
    d.joint(TRAVEL, t + 0.5, secs, 0.0, slide=True,
            label=f"The D travels back to its stationary place (x {QUADRANT_LAPSE})")
    t += 0.5 + secs
    for k, name in enumerate(TENSIONERS):
        d.joint(f"{name}: Top track tilt", t, 2.0, 0.0,
                label="The tensioners' top tracks come down again, the cradles rise" if k == 0 else "")
        d.joint(f"{name}: Top track lift", t + 2.0, 1.5, 0.0, slide=True)
    for lead, _drop in cradle_drops(d):
        d.joint(lead, t, 1.5, 0.0, slide=True)
    d.t = t + 3.5 + 1.0
    del paths


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
