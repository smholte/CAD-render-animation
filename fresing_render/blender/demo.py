"""Demo project "Vessel in a wind park" (task 0077; task 0247): Help > Make demo project.

One click writes the invented ship and the wind park round it (``demo_model/``), imports them and sets them up the way
the owner would – groups and looks, the name and draft marks, the ship's joints (thrusters, propellers, radars, the deck
crane), the crane's hoist wire on its drum, the open sea with its seabed and a cut-away, the park on the seabed with the
power cable lying on it, saved cameras, a brand kit – and saves a ready project with the animation **"What it can do
today"**: the ship sails in and holds her place over the cable on her thrusters, her crane slews and lowers its hook,
the park's rotors turn, night falls. Everything goes through the app's own functions (the same calls the buttons make),
so the project is exactly what a user would have made.

    Documents\\Fresing Render\\Demo\\<version>\\Vessel in a wind park <version>.blend   the project
    Documents\\Fresing Render\\Demo\\<version>\\model\\                                 STEP files + the two sheets
    Documents\\Fresing Render\\Demo\\<version>\\making.json                             only while it is made

The menu item starts a background Blender (``pccheck/launcher.py -- demobuild <folder>``, ``build_main``), which runs
the model maker as its own program and then the stages below; the app shows the progress and can cancel at any moment
(``ops_demo.py``). A demo that failed or was cancelled leaves nothing behind (its folder is deleted). A demo kit
(task 0228, ``core/demo_kits.py``) is built by the same framework with its own maker and stages.

ADDING TO THE DEMO: the project is built as a list of small named **stages**, run in order::

    @stage("shot_crane", "Shot 3: the deck crane slews and lowers its hook")
    def shot_crane(d: Demo):
        a = d.animation                         # "What it can do today"
        d.joint(SLEW, d.t, 4.0, 90.0, label="The deck crane slews outboard")
        d.t += 4.0                              # the shot's length: the next shot starts there

A later task adds a stage (``@stage("crane", "…", after="joints")``) or replaces one by giving the same id
(``@stage("shot_crane", …)`` again: the newest wins, its place stays). Shots run in order and each advances ``d.t``
(seconds on the animation's time line), so a shot put between two others moves the later ones along. Keep a stage
small and name what it shows; ``d.progress()`` inside a long loop keeps the status bar alive and lets Cancel in.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Callable

TITLE = "Vessel in a wind park"
ANIM = "What it can do today"
SEA_SHOT = "Open sea"
QUAY_SHOT = "At the quay"
TAG = "fr_demo"                       # on the scene of the demo project: the version
MODEL_KEYS = ("assembly", "park", "quay")   # the ship, the wind park round it (task 0166), the quay
MIN_JOINTS = 33                       # the ship's 13 + the crane's hoist wire travel + the park's 19




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


def project_path(folder: str, version: str, title: str = "") -> str:
    """The project file; ``title``: a demo kit's (its folder is ``kit_folder``), else the app's own demo."""
    return os.path.join(project_dir(folder, version), f"{title or TITLE} {version}.blend")


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


def exists(folder: str, version: str, title: str = "") -> bool:
    """A finished demo of this version is there (not one that is being made)."""
    return os.path.isfile(project_path(folder, version, title)) and not os.path.isfile(progress_path(folder, version))


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
# demo kits (task 0228): a demo that comes from a zip the user added (core/demo_kits.py)
# ---------------------------------------------------------------------------

PUBLIC = True                         # the app's own demo is in the list (Help > Make demo project…)
KIT_TAG = "fr_demo_kit"               # on the scene of a kit's demo project: the kit's id
KITS = "Kits"                         # <demo folder>/Kits/<kit id>/<version>/: a kit's demo project


def kits_dir() -> str:
    """Where added kits are unpacked: Blender's config folder (``FRESING_DEMO_KITS`` for tests and the PC check)."""
    from ..core import demo_kits
    given = os.environ.get(demo_kits.ENV)
    if given:
        return given
    import bpy
    return os.path.join(bpy.utils.user_resource("CONFIG"), demo_kits.FOLDER)


def kit_folder(folder: str, kit_id: str) -> str:
    """The folder a kit's demo projects go in (``project_dir`` etc. take it as ``folder``), next to the app's own."""
    return os.path.join(folder, KITS, kit_id)


def app_package() -> str:
    """The app's package name as Blender loaded it (``fresing_render`` or ``bl_ext.<repo>.fresing_render``)."""
    return __name__.rsplit(".blender.", 1)[0]


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

    anim_name = ANIM                    # the animation ``animation`` makes (a demo kit's Demo may name its own)

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
        self.kit = None                          # task 0228: the demo kit being built (core/demo_kits.KitInfo)
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
        """Status line for the app ("Joints 120/317") and the moment Cancel gets in."""
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
        a = self.s.animations.get(self.anim_name)
        if a is None:
            a = self.s.animations.add()
            a.name, a.tail, a.fps = self.anim_name, 0.5, "25"
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
    keys = MODEL_KEYS if d.quay else ("assembly", "park")
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
        _import(d, "quay")
    d.timings["import"] = time.time() - t0


# ---------------------------------------------------------------------------
# looks: the ship's paint, glass, galvanised outfitting, the deck crane's yellow
# ---------------------------------------------------------------------------

LOOKS = [
    # group, material, colour, part names (CAD names), only inside these machines ('' = anywhere)
    ("Demo: orange", "paint_marine", "RAL 2004", ("HOOK BLOCK", "WINCH DRUM", "DRUM FLANGE"), ()),
    ("Demo: yellow structure", "paint_marine", "RAL 1003",
     ("CRANE PEDESTAL", "CRANE HOUSE", "CRANE BOOM", "HOIST BEARING", "BOOM HEAD SHEAVE", "HEAD SHEAVE BRACKET"), ()),
    ("Demo: non-slip deck", "powder_coat", "RAL 7037", ("MAIN DECK", "HATCH COVER"), ()),
    # the vessel (task 0153): hull paint above the boot top with run-down streaks, the black boot top and the red
    # antifouling with marine growth below the waterline, white superstructure, glass, galvanised outfitting
    ("Demo: hull", "paint_marine_streaks", "RAL 5003", ("HULL", "BULWARK", "NAME BOARD"), ()),
    ("Demo: boot top", "paint_marine_growth", "RAL 9005", ("BOOT TOP", "DRAFT MARK BOARD"), ()),
    ("Demo: antifouling", "paint_marine_growth", "RAL 3009",
     ("HULL BOTTOM", "SKEG", "BILGE KEEL", "THRUSTER HOUSING", "THRUSTER STRUT", "THRUSTER POD", "THRUSTER NOZZLE",
      "THRUSTER TUNNEL", "TUNNEL GEARBOX"), ()),
    ("Demo: propellers", "bronze", "", ("PROPELLER",), ()),
    ("Demo: superstructure", "paint_marine_streaks", "RAL 9010",
     ("ACCOMMODATION", "BRIDGE", "MAST", "FUNNEL", "RADAR PEDESTAL", "RADAR SCANNER", "CRANE CAB"), ()),
    ("Demo: funnel tops", "paint_marine", "RAL 9005", ("FUNNEL TOP",), ()),
    ("Demo: glass", "glass_tinted", "#3A4650", ("WINDOW", "BRIDGE WINDOW", "CAB WINDOW"), ()),
    ("Demo: galvanised", "galvanized", "", ("RAILING", "DAVIT", "ANTENNA"), ()),
    ("Demo: lifeboats", "plastic_gloss", "RAL 2004", ("LIFEBOAT",), ()),
    ("Demo: deck fittings", "paint_marine", "RAL 9005",
     ("BOLLARD", "FAIRLEAD", "WINDLASS", "HAWSE PIPE", "ANCHOR", "RUBBING STRAKE"), ()),
    ("Demo: lights", "emission_light", "RAL 9016", ("MAST LIGHT",), ()),
    ("Demo: power cable", "cable_black", "", ("CABLE", "CABLE END"), ()),
    ("Demo: wire rope", "galvanized", "", ("WIRE ROPE", "HOIST WIRE"), ()),
]


WEAR = {"Demo: deck fittings": 0.8, "Demo: hull": 0.35, "Demo: non-slip deck": 0.4, "Demo: yellow structure": 0.25}
#: the wear of a group (edge wear and dirt in its corners; task 0153: the rubbing strake where the fenders touch the
#: side is worn down to bare steel, the deck fittings too)


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
        g.wear = WEAR.get(group, 0.0)
    logic.apply_rules(d.scene)
    logic.refresh_group_materials(d.scene)
    d.notes.append(f"looks: {n} parts in {len(LOOKS)} demo groups")


# ---------------------------------------------------------------------------
# the vessel's name and draft marks (task 0153): text decals on its name and draft-mark boards
# ---------------------------------------------------------------------------

VESSEL_NAME = "DEMO LAYER"            # invented (demo_model/vessel.py NAME)
DRAFT_MARKS = (("7M", 1.0), ("6M", 0.0), ("5M", -1.0))     # draft from the keel (6 m at the waterline), height (m)
WHITE_INK = (0.85, 0.85, 0.83)




def _outer_face(ob):
    """(face, point, normal) in the part's coordinates: the face of a board that faces most away from the vessel's
    centre line (its outer face)."""
    from mathutils import Vector

    from . import decals, faces
    me = ob.data
    starts = faces.face_starts(me)
    root = ob
    while root.parent is not None:
        root = root.parent
    centre = ob.matrix_world @ Vector(_mean_co(ob))
    side = 1.0 if (root.matrix_world.inverted() @ centre).y > 0 else -1.0
    side_w = (root.matrix_world.to_3x3() @ Vector((0.0, side, 0.0))).normalized()
    best = None
    for k in range(max(0, len(starts) - 1)):
        pos, nrm = decals.face_triangles(me, k)
        if not len(pos):
            continue
        nl = Vector(nrm.reshape(-1, 3).mean(axis=0)).normalized()
        n = (ob.matrix_world.to_3x3() @ nl).normalized()
        score = n.dot(side_w)                 # the side flares: its normal leans down at the bow
        if score > 0.5 and (best is None or score > best[3]):
            best = (k, Vector(pos.reshape(-1, 3).mean(axis=0)), nl, score)
    if best is None:
        raise RuntimeError(f"the board {ob.name} has no face looking outboard")
    return best[:3]


def _mean_co(ob):
    import numpy as np
    co = np.empty(len(ob.data.vertices) * 3)
    ob.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3).mean(axis=0)


@stage("marks", "The vessel's name and draft marks", after="looks")
def vessel_marks(d: Demo):
    from mathutils import Vector

    from . import build, decals
    root = d.root()
    n = 0
    for ob in [o for o in _descendants(root) if o.get(build.PROP_NAME) in ("NAME BOARD", "DRAFT MARK BOARD")]:
        face, pt, nrm = _outer_face(ob)
        if ob.get(build.PROP_NAME) == "NAME BOARD":
            it = decals.add(ob, face, tuple(pt), tuple(nrm), "TEXT", text=VESSEL_NAME, only_copy=True)
            it.ink_color = WHITE_INK
            decals.fit(it)
            n += 1
            continue
        up = (ob.matrix_world.inverted().to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
        up = (up - up.dot(nrm) * nrm).normalized()
        for text, dz in DRAFT_MARKS:
            it = decals.add(ob, face, tuple(pt + up * dz), tuple(nrm), "TEXT", text=text, only_copy=True)
            it.ink_color = WHITE_INK
            it.height = 0.45
            n += 1
    d.notes.append(f"marks: {n} decals (name and draft marks)")


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


def make_joints(d: Demo, js: list[dict], key: str = "assembly", prefix: str = "", cable: str = "") -> int:
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
            if j.get("motor"):                          # turns without end (task 0153: propellers, radars, steers)
                joints.set_motor(sc, jt, True)
            joints.apply_limits(jt, joints._model_size(sc))
    return total



def _descendants(root):
    from . import logic
    return logic.descendants(root)


@stage("joints", "Joints")
def make_all_joints(d: Demo):
    from . import joints
    sc = d.scene
    t0 = time.time()
    n = make_joints(d, d.sheet("joints")["joints"], "assembly")
    joints.refresh_couplings(sc)
    d.timings["joints"] = time.time() - t0
    d.notes.append(f"joints: {n} of the ship from the sheet")


# ---------------------------------------------------------------------------
# the deck crane's hoist (task 0174; task 0247: the hook follows the wire): the wire on its drum as a cable
# ---------------------------------------------------------------------------

SLEW = "VESSEL: DECK CRANE: Slew"
HOOK = "VESSEL: DECK CRANE: Hook lower"
CRANE_SPOOL = "Crane hoist"
CRANE_WIRE = "Crane hoist wire"
CRANE_TRAVEL = "DECK CRANE: Hoist wire travel"


def _joint_ending(d: Demo, suffix: str) -> str:
    for j in d.s.joints:
        if j.name.endswith(suffix):
            return j.name
    raise RuntimeError(f"the demo has no joint '… {suffix}'")


def _winch_parts(d: Demo, drum_joint: str):
    """(drum, the CAD wire on the drum, every part of the winch, the winch's assembly) of the winch whose drum turns
    with ``drum_joint``."""
    from . import build, joints, logic
    unit = joints.members(joints.find(d.scene, drum_joint))[0]
    winch = build.logical_parent(unit)
    turning = {o.name for o in logic.descendants(unit)}
    parts = [o for o in logic.descendants(winch) if o.get(build.PROP_KIND) == "part"]
    drum = next(o for o in parts if o.get(build.PROP_NAME) == "WINCH DRUM" and o.name in turning)
    on_drum = next(o for o in parts if o.get(build.PROP_NAME) == "WIRE ROPE" and o.name in turning)
    return drum, on_drum, parts, winch


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


@stage("crane", "The deck crane's hoist: its wire on the drum, the hook on the wire", after="joints")
def crane_hoist(d: Demo):
    """The crane's hoist wire (in the CAD from the drum over the head sheave down to the hook block) becomes a cable on a
    speed joint of its own (m of wire paid out), spooled on its drum (4 Motion > Drums and carousels; the drum turns by
    the spool's table), its end on the hook block; the hook's slide joint follows the speed joint one to one, so paying
    out wire lowers the hook."""
    import numpy as np
    from mathutils import Vector

    from . import build, joints, paths, spool
    sc = d.scene
    t0 = time.time()
    drum_joint = _joint_ending(d, "DECK CRANE: Hoist drum turn")
    drum, on_drum, parts, _crane = _winch_parts(d, drum_joint)
    wire_part = next(o for o in parts if o.get(build.PROP_NAME) == "HOIST WIRE")
    hook = next(o for o in parts if o.get(build.PROP_NAME) == "HOOK BLOCK")
    deck = d.part("MAIN DECK", root=d.root())
    with joints._batch(sc):
        j = joints.create(sc, "SLIDE", [], Vector(np.array(joints.find(sc, drum_joint).frame.matrix_world.translation)),
                          Vector((0.0, 0.0, 1.0)), name=CRANE_TRAVEL, base=deck, allow_empty=True)
    j.use_limits = False
    item = paths.add_cable(sc, CRANE_WIRE, joint=CRANE_TRAVEL)
    with paths._quiet(item):
        item.look = "ROPE"
    item["look_was"] = "ROPE"
    paths.read_cad(sc, item, wire_part)
    spool.add(sc, "DRUM", drum, CRANE_WIRE, coil=on_drum, name=CRANE_SPOOL)
    _end_on(d, CRANE_WIRE, hook)
    sp = spool.find(sc, CRANE_SPOOL)
    if sp.problem:
        raise RuntimeError(f"deck crane: {sp.problem}")
    joints.set_follows(sc, joints.find(sc, HOOK), CRANE_TRAVEL, ratio=1.0)
    joints.refresh_couplings(sc)
    d.notes.append("spool: " + spool.summary(sc, sp))
    d.timings["crane"] = time.time() - t0


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

    from . import logic
    s = d.s
    res = bpy.ops.fresing.light_look(look="SUN")
    if res != {"FINISHED"}:
        raise RuntimeError(f"light look Sun returned {res}")
    s.env_detail = "SIMPLE"
    if d.quay:
        # the quay scene first: the ship moored starboard side to, Quayside surroundings
        quay = d.root("quay")
        s.background = "QUAY"
        s.water_level = _water_level(d)
        d.camera(QUAY_SHOT, (-36000.0, -62000.0, 36000.0), (50000.0, -14000.0, 4000.0), lens=30.0)
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


# ---------------------------------------------------------------------------
# the sea's depth and the cut-away (the cable on the seabed shows through it)
# ---------------------------------------------------------------------------

SEA_DEPTH = 30.0                      # m of water in the park (the park's ParkParams.water_depth)
SEA_CLARITY = 12.0                    # m: water clarity in the cut-away's walls
CUT_LENGTH = 150.0                    # m: the cut-away from the transom aft past turbine A's foot …
CUT_WIDTH = 30.0                      # … this wide


@stage("sea", "Sea depth and the cut-away behind the stern", after="surroundings")
def sea_stage(d: Demo):
    """30 m of water, a box of water taken away behind the stern (its size typed in: no cable hangs from the ship) out
    past turbine A's foot, water clarity 12 m."""
    s = d.s
    s.sea_depth = SEA_DEPTH
    s.sea_clarity = SEA_CLARITY
    s.sea_cut_auto = False
    s.sea_cut_length, s.sea_cut_width, s.sea_cut_start, s.sea_cut_side = CUT_LENGTH, CUT_WIDTH, 0.0, 0.0
    s.sea_cutaway = True
    s.sea_cut_ground = False                  # (switching the cut-away on may set it: the seabed stays closed)
    _update()
    d.notes.append(f"sea: {SEA_DEPTH:.0f} m deep, a cut-away {CUT_LENGTH:.0f} m x {CUT_WIDTH:.0f} m behind the stern")


# ---------------------------------------------------------------------------
# saved cameras (model mm: x to the bow, transom at 0, y to port, z up)
# ---------------------------------------------------------------------------

OVERVIEW = "Overview"
STERN_THRUSTERS = "Stern thrusters"
HULL_SIDE = "Hull side"
AT_THE_SEABED = "At the seabed"
DECK_CRANE = "Deck crane"

VIEWS = {
    OVERVIEW: ((-30000.0, -52000.0, 42000.0), (36000.0, 0.0, 3000.0), 30.0),
    STERN_THRUSTERS: ((-9000.0, -15000.0, -9500.0), (6000.0, 0.0, -5500.0), 24.0),    # task 0153: under water
    HULL_SIDE: ((146000.0, -32000.0, 4500.0), (96000.0, -9000.0, 1500.0), 32.0),     # the bow, along the stb side
    # under water in the cut-away, along the cable aft to turbine A's foot (its J-tube, the scour rock)
    AT_THE_SEABED: ((-60000.0, -14000.0, -24000.0), (-128000.0, 0.0, -27000.0), 28.0),
    DECK_CRANE: ((150000.0, 40000.0, 40000.0), (80000.0, 12000.0, 14000.0), 30.0),    # ahead on port: the crane outboard
}


@stage("cameras", "Saved cameras")
def saved_cameras(d: Demo):
    for name, (at, target, lens) in VIEWS.items():
        d.camera(name, at, target, lens)
    d.scene.camera = d.scene.objects.get(OVERVIEW)


@stage("brand", "Brand kit Demo")
def brand_kit(d: Demo):
    from . import tour
    s = d.s
    s.brand_name = "Demo"
    s.brand_logo = tour._logo(os.path.join(d.dir, "Demo logo.png"))
    s.brand_contact = "Fresing Render demo · an invented ship"


# ---------------------------------------------------------------------------
# the animation "What it can do today": one stage per shot (about a minute)
# ---------------------------------------------------------------------------

def _uid(ob) -> str:
    from . import build
    return ob[build.PROP_UID]


@stage("shot_fly", "Shot 1: fly round the ship")
def shot_fly(d: Demo):
    from . import build
    a = d.animation
    a.start_shot = OVERVIEW
    a.fin_title_on, a.fin_end_on, a.fin_captions = True, True, True
    a.fin_title, a.fin_subtitle = TITLE, "What Fresing Render can do today · an invented ship"
    a.fin_title_seconds = a.fin_end_seconds = 3.0
    a.fin_logo = "BR"
    hull = d.part("HULL", root=d.root())
    fly = d.camera_step("PATH", d.t, 6.0, "She sails in on a calm sea", easing="LINEAR", cam_blend=0.0,
                        path_look="PART", aim_uid=_uid(hull), aim_name=hull.get(build.PROP_NAME, "HULL"))
    for p in ((95000.0, -70000.0, 30000.0), (40000.0, -85000.0, 26000.0), (-15000.0, -60000.0, 24000.0)):
        fly.path_points.add().co = d.mm(p)
    fly.path_from_here = True
    d.camera_step("RIDE", d.t + 6.0, 3.0, "", target_uid=_uid(hull), target_name="HULL", cam_blend=0.5,
                  ride_level=True)                       # then the camera rides with the vessel on the swell
    d.t += 9.0


CRANE_SLEW = 90.0                     # deg: the boom swings outboard to port
CRANE_DROP = 20.0                     # m of wire paid out: the hook goes down beside the ship
CRANE_SECONDS = 4.0                   # each of the two moves


@stage("shot_crane", "Shot 3: the deck crane slews outboard and lowers its hook")
def shot_crane(d: Demo):
    cam = d.scene.objects.get(DECK_CRANE)
    d.camera_step("CUT", d.t, 0.0, "", camera=cam)
    d.joint(SLEW, d.t, CRANE_SECONDS, CRANE_SLEW, label="On DP over the cable: the deck crane slews outboard …")
    d.joint(CRANE_TRAVEL, d.t + CRANE_SECONDS, CRANE_SECONDS, CRANE_DROP, slide=True,
            label="… and lowers its hook: the wire comes off the drum layer by layer")
    d.camera_step("ORBIT", d.t, 2 * CRANE_SECONDS, "", orbit_angle=math.radians(-10.0), easing="SMOOTH")
    d.t += 2 * CRANE_SECONDS


@stage("shot_hull", "Shot 4: along the hull, the stern thrusters under water")
def shot_hull(d: Demo):
    d.camera_step("CUT", d.t, 0.0, "", camera=d.scene.objects.get(HULL_SIDE))
    d.camera_step("ORBIT", d.t, 5.0, "She holds her place on her thrusters (dynamic positioning)",
                  orbit_angle=math.radians(6.0), easing="SMOOTH")
    d.t += 5.0
    d.camera_step("CUT", d.t, 0.0, "", camera=d.scene.objects.get(STERN_THRUSTERS))
    d.camera_step("ORBIT", d.t, 5.0, "Under water: the azimuth thrusters turn and push", orbit_angle=math.radians(-8.0),
                  easing="SMOOTH")
    d.t += 5.0


@stage("shot_seabed", "Shot 5: at the seabed – the power cable lies on it")
def shot_seabed(d: Demo):
    d.camera_step("CUT", d.t, 0.0, "", camera=d.scene.objects.get(AT_THE_SEABED))
    d.camera_step("ORBIT", d.t, 6.0, f"At the seabed, {SEA_DEPTH:.0f} m down: the power cable comes down turbine A's "
                  "J-tube and lies on along the seabed, right under the ship", orbit_angle=math.radians(8.0),
                  easing="SMOOTH")
    d.t += 6.0


# the vessel's propellers and radars turn through the whole animation (task 0153; 0154's water effects read the
# propellers' joints): rev/min in video time
PROPELLER_RPM = {"AZIMUTH THRUSTER": 30.0, "BOW THRUSTER": 40.0}
RADAR_RPM = 24.0


def turning_joints(d: Demo) -> list[tuple[str, float]]:
    """(joint, rev/min) of every propeller and radar of the sheet."""
    out = []
    for j in d.sheet("joints")["joints"]:
        n = j["name"]
        if n.endswith("Propeller turn"):
            out.append((n, next(v for k, v in PROPELLER_RPM.items() if k in n)))
        elif n.startswith("VESSEL: SUPERSTRUCTURE: Radar"):
            out.append((n, RADAR_RPM))
    return out


# task 0154: what the vessel does – she arrives at 6 knots (shot 1 and the park's: a wake, her waves, a bow wave), then
# holds her place over the cable on her thrusters (DP, gently to starboard) from the crane's shot on
TRANSIT_KNOTS = 6.0
DP_THRUST = 0.35
DP_CHANGE = 3.0                       # s: the change from sailing to DP, ending as the crane's shot starts


def _shot_start(d: Demo, camera: str) -> float:
    for b in sorted(d.animation.blocks, key=lambda x: x.start):
        if b.kind == "CAMERA" and b.camera is not None and b.camera.name == camera:
            return float(b.start)
    raise RuntimeError(f"the animation has no camera step to '{camera}'")


@stage("propulsion", "The vessel at work: sailing in, then on DP; the propellers and radars turn")
def propulsion(d: Demo):
    from . import states, vessel_work
    sc, s = d.scene, d.s
    for name, rpm in turning_joints(d):
        if name.endswith("Propeller turn"):
            continue                                   # (Vessel at work turns them)
        blk = d.animation.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", name, 0.0, d.t, "LINEAR"
        blk.speed_rpm = rpm
    vessel_work.find(sc)
    for r in s.vessel_work.thrusters:
        r.rpm = next(v for k, v in PROPELLER_RPM.items() if k in r.joint)
    s.weather.vessel_speed = TRANSIT_KNOTS
    s.vessel_work.mode = "AHEAD"
    # the start scene ("Overview") puts back what it saved: it saves this setting too now
    shot = s.shots.get(d.animation.start_shot)
    if shot is not None:
        data = json.loads(shot.world or "{}")
        data.setdefault("weather", {})["vessel_speed"] = TRANSIT_KNOTS
        data["vessel_work"] = json.loads(states.settings_json(s, ("vessel_work",)))["vessel_work"]
        shot.world = json.dumps(data)
    t = _shot_start(d, DECK_CRANE) - DP_CHANGE
    blk = d.animation.blocks.add()
    blk.kind, blk.start, blk.duration, blk.easing = "VESSEL", t, DP_CHANGE, "SMOOTH"
    blk.vw_mode, blk.vw_side, blk.vw_thrust = "DP", "STBD", DP_THRUST
    d.notes.append(f"vessel at work: {len(s.vessel_work.thrusters)} thrusters; ahead {TRANSIT_KNOTS:g} kn, DP from "
                   f"{t + DP_CHANGE:.1f} s")


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
    from . import workspaces
    workspaces.use_all(scene)                    # the demo shows everything, whatever the user's default workspace
    scene.fresing.out_folder = os.path.join(project_dir(folder, version), "Renders")
    return scene


def build_project(folder: str, version: str = "", small: bool = False, progress=None, only=(), kit=None) -> dict:
    """Make the demo project of ``version`` in ``folder`` (an older one of that version is replaced). Returns
    {"path", "seconds" per stage, "timings", "notes"}. Raises Cancelled / RuntimeError; then nothing is left.

    ``kit`` (task 0228, a ``core/demo_kits.KitInfo`` of an added kit): the kit's demo instead of the app's own – only
    the kit's maker and stages run (``_kit_build``); ``folder`` is then its ``kit_folder``."""
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
    title = kit.title if kit is not None else ""
    out = {"path": project_path(folder, version, title), "seconds": {}}
    d = None
    from . import prefs as fr_prefs
    p = fr_prefs.get()
    saved_template = p.default_template if p else ""
    if p:
        p.default_template = ""
    try:
        with _kit_build(kit) as demo_class:
            scene = _fresh(folder, version)
            d = demo_class(scene, folder, version, small, report)
            d.kit = kit
            stages = [s for s in STAGES if not only or s.id in only]
            for st in stages:
                d.stage = st.title
                d.progress(st.title)
                t0 = time.time()
                st.fn(d)
                out["seconds"][st.id] = round(time.time() - t0, 1)
                try:
                    from . import surroundings
                    surroundings.fix_view_clip(bpy.context.scene)   # task 0193: far things (the park) in view
                except Exception:  # noqa: BLE001
                    pass
            scene = bpy.context.scene
            scene[TAG] = version
            if kit is not None:
                scene[KIT_TAG] = kit.id
            d.progress("Saving")
            a = scene.fresing.animations.get(d.anim_name)
            _write_json(summary_path(folder, version), {
                "version": version, "joints": len(scene.fresing.joints), "cylinders": len(scene.fresing.cylinders),
                "animation": d.anim_name, "kit": kit.id if kit is not None else "", "frames": int(scene.frame_end - scene.frame_start + 1) if a else 0,
                "seconds": round(max(b.start + b.duration for b in a.blocks), 1) if a and len(a.blocks) else 0.0,
                "small": small})
            bpy.ops.wm.save_as_mainfile(filepath=project_path(folder, version, title), check_existing=False)
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


# ---------------------------------------------------------------------------
# a demo kit's build (task 0228): only the kit's maker and stages, the app's own set aside
# ---------------------------------------------------------------------------

def _run_kit_maker(d: Demo) -> None:
    """The kit's ``maker`` as its own program (``core/demo_kit_run.py``, Blender's Python, the bundled OpenCascade)."""
    from ..importer import runner as import_runner
    kit = d.kit
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core", "demo_kit_run.py")
    os.makedirs(d.model_dir, exist_ok=True)
    prog = os.path.join(d.model_dir, "kit maker.json")
    log = os.path.join(d.model_dir, "kit maker log.txt")
    env = dict(os.environ)
    for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(var, None)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p and os.path.isdir(p))
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [import_runner.python_executable(), script, kit.folder, kit.maker, d.model_dir, "--progress", prog]
    if d.small:
        cmd.append("--small")
    with open(log, "w", encoding="utf-8", errors="replace") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, env=env, cwd=kit.folder,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        d.helper_pid = proc.pid
        try:
            while proc.poll() is None:
                try:
                    with open(prog, encoding="utf-8") as pf:
                        p = json.load(pf)
                except (OSError, ValueError):
                    p = {}
                d.progress(str(p.get("text") or "Making the model's shapes"), int(p.get("done") or 0),
                           int(p.get("total") or 0))
                time.sleep(0.5)
        except Cancelled:
            proc.kill()
            proc.wait()
            raise
        finally:
            d.helper_pid = 0
    if proc.returncode != 0:
        with open(log, encoding="utf-8", errors="replace") as fh:
            tail = fh.read().strip()[-400:]
        raise RuntimeError(f"the kit's model could not be written: {tail}")
    for f in (prog, log):
        try:
            os.remove(f)
        except OSError:
            pass


def _kit_model(d: Demo):
    d.progress("Making the model's shapes")
    t0 = time.time()
    _run_kit_maker(d)
    d.timings["write"] = time.time() - t0


@contextlib.contextmanager
def _kit_build(kit):
    """While a kit is built: the app's own stages set aside, the kit's maker first (stage ``kit_model``), then the
    stages its ``stage_module`` registers with ``@stage``; the Demo class the stages get (the kit's own, if it has
    one). On the way out the app's stages are back and the kit's code forgotten. ``kit`` None: the app's own demo."""
    if kit is None:
        yield Demo
        return
    import importlib

    from ..core import demo_kits
    saved = STAGES[:]
    STAGES[:] = [Stage("kit_model", "The model (written)", _kit_model)] if kit.maker else []
    try:
        with demo_kits.loaded(kit.folder, app_package()):
            gone = demo_kits.missing_uses(kit, app_package())
            if gone:
                raise RuntimeError(f"the demo kit '{kit.title}' needs {', '.join(gone[:4])}, which this app version "
                                   f"does not have: download the kit's newer version")
            try:
                mod = importlib.import_module(kit.stage_module)
            except Exception as exc:  # noqa: BLE001 - said plainly
                raise RuntimeError(f"the demo kit's stages could not be loaded ({type(exc).__name__}: {exc})") \
                    from exc
            have = {st.id for st in STAGES}
            lost = [x for x in kit.stages if x not in have]
            if lost:
                raise RuntimeError(f"the demo kit's stage module did not register {', '.join(lost[:4])}")
            cls = getattr(mod, "Demo", Demo)
            yield cls if isinstance(cls, type) and issubclass(cls, Demo) else Demo
    finally:
        STAGES[:] = saved


def result_path(folder: str) -> str:
    """The background build's last word (next to the version folders: it outlives a cancelled build)."""
    return os.path.join(folder, "Make demo result.json")


def _line(text: str) -> None:
    """A line of the build's log (``Make demo log.txt``), written out at once – the log's last line is the last thing
    that happened (task 0371: the owner's log ended ten stages before the failure)."""
    try:
        sys.stdout.flush()
        os.write(sys.stdout.fileno(), (text.rstrip("\n") + "\n").encode("utf-8", "replace"))
    except (OSError, ValueError, AttributeError):
        print(text, flush=True)


def _line_buffered() -> None:
    """Everything else printed to the log (Blender's and the app's own lines) goes out line by line too."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True, write_through=True)
        except (AttributeError, ValueError, OSError):
            pass


def build_main(folder: str = "", small: bool = False, kit: str = "") -> int:
    """Entry point of the background Blender ``launcher.py -- demobuild [folder] [small] [--kit <id>]`` (task 0228:
    ``--kit``: an added demo kit's demo; ``folder`` is then its ``kit_folder``)."""
    from .. import __version__
    _line_buffered()
    folder = folder or (kit_folder(default_folder(), kit) if kit else default_folder())
    os.makedirs(folder, exist_ok=True)
    t0 = time.time()
    info = None
    if kit:
        from ..core import demo_kits
        info = demo_kits.get(kits_dir(), kit)
        why = (f"the demo kit '{kit}' is not added (Help > Make demo project… > Add a demo kit…)" if info is None
               else demo_kits.version_message(info, __version__))
        if why:
            res = {"version": __version__, "finished": False, "error": why, "kit": kit}
            _write_json(result_path(folder), res)
            _line(f"Demo project: {json.dumps(res)}")
            return 1

    def progress(stage_title, text, done, total):
        _line(f"{stage_title}: {text}" if text and text != stage_title else stage_title)

    res = {"version": __version__, "finished": False}
    try:
        out = build_project(folder, __version__, small=small, progress=progress, kit=info)
        res.update(finished=True, path=out["path"], seconds=round(time.time() - t0, 1), stages=out["seconds"],
                   timings=out["timings"], notes=out["notes"])
        code = 0
    except Cancelled:
        res.update(cancelled=True)
        code = 2
    except Exception as exc:  # noqa: BLE001 - said in the result and the log
        import traceback
        _line(traceback.format_exc())
        res.update(error=f"{type(exc).__name__}: {exc}")
        code = 1
    _write_json(result_path(folder), res)
    _line(f"Demo project: {json.dumps(res)[:1500]}")
    return code
from . import demo_park  # noqa: E402,F401  (task 0166: registers the wind park's stages)
