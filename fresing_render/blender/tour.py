"""Test tour (task 0059): one project the owner opens to see every function of the app work.

"Make test tour project" (Help menu) builds, in a background Blender, a set of small projects from the generic test
models in ``data/`` (never the owner's files):

    Documents\\Fresing Render\\Test tour\\Test tour <version>.blend            the crane: most stops (the "hub")
    Documents\\Fresing Render\\Test tour\\Test tour <version> files\\*.blend   one project per other test model
    Documents\\Fresing Render\\Test tour\\Test tour <version> results.json     OK / Problem and notes per stop

Every project shows the **Test tour** panel (``ui_tour.py``): numbered stops, each with "what you should see", **Go**
(opens the right project, its saved scene, builds and plays the animation, selects the part), **OK / Problem** and a
note, and **Copy results**. The PC check's mode **Tour** (``pccheck/tour.py``) goes through every stop by itself and
writes a report with a picture per stop.

ADDING A STOP (every new function the owner can see adds one, CLAUDE.md section 6): one ``stop(...)`` entry below,
in its group, with a title, the "what you should see" text, where to look in the side panel, the set (test model
project) it lives in, and

* ``shot``: the saved scene Go applies (camera, pose, visibility, looks, background, image size). Make it in the
  set's build function with ``_shot(b, "@<stop id>")`` after setting things up the way the stop shows them;
* or ``animation``: the animation Go builds and shows (its "start scene" set to the stop's shot), with ``at`` =
  where on its time line (0 … 1) and ``play``;
* optional ``select`` (part names), ``check`` (a number check ``fn(scene) -> note``, raises with a plain reason),
  ``auto`` (what the automatic run renders: "still", "clip" = three frames, or ``fn(ctx, scene)``).

A new test model set: a ``@tour_set("id", "Title", model)`` build function. Keep builds small: the whole tour must
build in about 2 minutes.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable

from ..core import places

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

GROUPS = ("Look", "Motion", "Machining", "Output")
GROUP_TITLES = {"Look": "Look", "Motion": "Motion", "Machining": "Machining", "Output": "Pictures and videos"}
TAG = "fr_tour"                    # on the scene of every tour project: the set id
TAG_VERSION = "fr_tour_version"
HUB_SET = "crane"
OK_STATE, PROBLEM = "OK", "PROBLEM"


@dataclass
class Stop:
    id: str
    group: str
    set: str
    title: str
    see: str                       # what you should see (plain words, shown in the panel and the report)
    where: str = ""                # where in the side panel the function lives
    since: str = ""                # the version it came in (task 0199: the precheck wants it on every stop)
    changed: str = ""              # the version that last changed what it shows (What's new marks it "Changed")
    shot: str = ""                 # saved scene Go applies (default: the title, when the set made one)
    animation: str = ""            # animation Go builds and shows
    at: float = 0.0                # where on the animation (0 = first frame, 1 = last)
    play: bool = False
    select: tuple = ()
    check: Callable | None = None
    auto: object = "still"         # "still", "clip", or fn(ctx, scene) -> note
    setup: Callable | None = None  # extra set-up after the shot / animation: fn(scene)
    number: int = 0


@dataclass
class TourSet:
    id: str
    title: str
    models: tuple
    build: Callable
    added: str = ""                # the version the set came in (task 0199)
    changed: str = ""              # the version its build, stops or test model last changed (tools/tour_versions.py)


STOPS: list[Stop] = []
SETS: dict[str, TourSet] = {}


def stop(id: str, group: str, set: str, title: str, see: str, **kw) -> Stop:
    st = Stop(id, group, set, title, see, **kw)
    st.number = len(STOPS) + 1
    STOPS.append(st)
    return st


def tour_set(id: str, title: str, *models: str, added: str = "", changed: str = ""):
    def deco(fn):
        SETS[id] = TourSet(id, title, tuple(os.path.join(DATA, m) for m in models), fn, added, changed)
        return fn
    return deco


def find(stop_id: str) -> Stop | None:
    return next((s for s in STOPS if s.id == stop_id), None)


def shot_name(st: Stop) -> str:
    return st.shot or st.title


# ---------------------------------------------------------------------------
# where things go
# ---------------------------------------------------------------------------

def documents_dir() -> str:
    from . import rule_sets
    return rule_sets.documents_dir()


def default_folder() -> str:
    return os.path.join(documents_dir(), "Fresing Render", "Test tour")


def hub_path(folder: str, version: str) -> str:
    return os.path.join(folder, f"Test tour {version}.blend")


def files_dir(folder: str, version: str) -> str:
    return os.path.join(folder, f"Test tour {version} files")


def set_path(folder: str, version: str, set_id: str) -> str:
    if set_id == HUB_SET:
        return hub_path(folder, version)
    return os.path.join(files_dir(folder, version), f"{SETS[set_id].title}.blend")


def results_path(folder: str, version: str) -> str:
    return os.path.join(folder, f"Test tour {version} results.json")


def results_txt_path(folder: str, version: str) -> str:
    return os.path.join(folder, f"Test tour {version} results.txt")


def progress_path(folder: str) -> str:
    return os.path.join(folder, "building.json")


def is_tour(scene) -> bool:
    return bool(scene is not None and scene.get(TAG))


def tour_of_file(scene=None) -> tuple[str, str]:
    """(tour folder, version) of the open project, or ("", "") when it is not a tour project."""
    import bpy
    scene = scene or bpy.context.scene
    if not is_tour(scene) or not bpy.data.filepath:
        return "", ""
    here = os.path.dirname(bpy.data.filepath)
    folder = here if scene[TAG] == HUB_SET else os.path.dirname(here)
    return folder, str(scene.get(TAG_VERSION, ""))


# ---------------------------------------------------------------------------
# results: OK / Problem and a note per stop (a JSON file next to the tour, shared by all its projects)
# ---------------------------------------------------------------------------

def load_results(folder: str, version: str) -> dict:
    try:
        with open(results_path(folder, version), encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data.setdefault("stops", {})
            return data
    except (OSError, ValueError):
        pass
    return {"version": version, "stops": {}, "current": ""}


def save_results(folder: str, version: str, data: dict) -> None:
    path = results_path(folder, version)
    os.makedirs(folder, exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, path)


def mark(folder: str, version: str, stop_id: str, state: str | None = None, note: str | None = None) -> dict:
    data = load_results(folder, version)
    row = data["stops"].setdefault(stop_id, {"state": "", "note": ""})
    if state is not None:
        row["state"] = "" if row.get("state") == state else state       # a second click takes it off again
    if note is not None:
        row["note"] = " ".join(note.split())
    save_results(folder, version, data)
    return data


def results_text(version: str, data: dict, pc: str = "") -> str:
    """The short text the owner pastes into the lead chat: version, PC, per stop OK / Problem + note."""
    rows = data.get("stops", {})
    n_ok = sum(1 for s in STOPS if rows.get(s.id, {}).get("state") == OK_STATE)
    n_bad = sum(1 for s in STOPS if rows.get(s.id, {}).get("state") == PROBLEM)
    out = [f"Fresing Render test tour {version} - {time.strftime('%Y-%m-%d %H:%M')}"]
    if pc:
        out.append(f"PC: {pc}")
    out.append(f"{n_ok} OK, {n_bad} problem, {len(STOPS) - n_ok - n_bad} not looked at, of {len(STOPS)} stops")
    for s in STOPS:
        row = rows.get(s.id, {})
        state = {OK_STATE: "OK", PROBLEM: "PROBLEM"}.get(row.get("state", ""), "-")
        line = f"{s.number:2d}. [{state}] {s.title} ({s.id})"
        if row.get("note"):
            line += f" - {row['note']}"
        out.append(line)
    return "\n".join(out)


def pc_text() -> str:
    """One line about this PC (processor, graphics card): no names."""
    try:
        from ..pccheck import runner
        from . import render
        gpu = render.setup_gpu()
        return f"{runner.cpu_name()}, {os.cpu_count()} cores, {runner.ram_gb()} GB; {gpu}"
    except Exception:  # noqa: BLE001 - the text works without it
        return ""


# ---------------------------------------------------------------------------
# small helpers for the set builds
# ---------------------------------------------------------------------------

class Build:
    """What a set's build function gets: the scene, the folder for its files, the version."""

    def __init__(self, scene, folder: str, version: str):
        self.scene = scene
        self.folder = folder
        self.version = version

    @property
    def s(self):
        return self.scene.fresing

    def file(self, name: str) -> str:
        d = files_dir(self.folder, self.version)
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, name)


def _ob(scene, name, n=0):
    from . import build
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


def _camera(b: Build, view: str = "ISO", name: str = "Tour view", lens: float = 50.0, points=None):
    from . import cameras
    cam = cameras.add_camera(b.scene, view, lens, name, points=points)
    b.scene.camera = cam
    return cam


def _close_camera(b: Build, centre, size: float, name: str, view: str = "ISO"):
    """A camera fitted to a box of ``size`` (m) round ``centre`` (world): a close-up."""
    import numpy as np
    from mathutils import Vector
    c = Vector(centre)
    pts = np.array([tuple(c + Vector((dx, dy, dz)) * size) for dx in (-0.5, 0.5) for dy in (-0.5, 0.5)
                    for dz in (-0.5, 0.5)])
    return _camera(b, view, name, points=pts)


def _shot(b: Build, name: str):
    """Save the scene as it is now. "@<stop id>": the saved scene of that stop (named like the stop)."""
    from . import states
    if name.startswith("@"):
        st = find(name[1:])
        _check(st is not None, f"no stop '{name[1:]}'")
        name = shot_name(st)
    return states.save_shot(b.scene, name)


def _look(look: str = "PRODUCT") -> None:
    import bpy
    res = bpy.ops.fresing.light_look(look=look)
    _check(res == {"FINISHED"}, f"light look {look} returned {res}")


def _animation(b: Build, name: str, shot: str = "", fps: str = "25"):
    a = b.s.animations.add()
    a.name, a.tail, a.fps = name, 0.0, fps
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"
    if shot:
        a.start_shot = shot
    return a


def _joint_step(a, joint: str, start: float, seconds: float, to: float, slide: bool = False, label: str = "",
                easing: str = "SMOOTH"):
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", joint, start, seconds, easing
    blk.use_from = True
    if slide:
        blk.to_dist = to
    else:
        blk.to_angle = to
    if label:
        blk.name = label
    return blk


def _xyz(scene, names=(("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1)))):
    from mathutils import Vector

    from . import joints
    for name, asm, d in names:
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)


GANTRY_AXES = (("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1)))


def _pick(role: str, ob) -> None:
    """Milling: the bit or the workpiece (as "Use as bit" / "Use as workpiece" do; no clicks needed)."""
    from . import machining
    from ..core import machining as mcore
    _check(mcore.available(), "the Manifold library did not load: run Install.bat again")
    if role == "bit":
        machining.add_bit(bpy_scene(), ob)
    else:
        machining.set_workpiece(bpy_scene(), ob)
        _hide_finished(bpy_scene())


def _hide_finished(scene) -> None:
    """The test mill's FINISHED PART lies on the stock (a shape for "finish at the CAD part") and its BALL MILL D6 sits
    on the head beside the end mill, its tip as low: shown, the bit cut through the one and the other went into the
    stock (the clash check said so, task 0067). Hidden, as a user would, unless the ball mill is a bit."""
    from . import build, logic, machining
    bits = {ob.name for _it, ob in machining.bits(scene)}
    for ob in scene.objects:
        if (ob.get(build.PROP_NAME) in ("FINISHED PART", "BALL MILL D6") and ob.name not in bits
                and not logic.is_hidden(ob)):
            logic.set_hidden(ob, True)


def bpy_scene():
    import bpy
    return bpy.context.scene


def _program(b: Build, name: str, text: str) -> str:
    path = b.file(name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _gcode_step(a, path: str, scene, **kw):
    from . import gcode
    blk = a.blocks.add()
    blk.kind = "GCODE"
    for k, v in kw.items():
        setattr(blk, k, v)
    blk.gcode_file = path
    gcode.step_changed(scene, blk)
    return blk


def _bake(scene, a) -> dict:
    from . import animation
    r = animation.bake(scene, a)
    _check(not r["warnings"], f"'{a.name}': " + "; ".join(r["warnings"][:2]))
    return r


def _boom_joint(scene):
    from mathutils import Vector

    from . import joints
    pin = _ob(scene, "BOOM.PIN")
    origin, direction, _desc = joints.axis_from_hit(pin, 0, Vector((0.1, 0.3, 0.42)), Vector((0, 0, 1)))
    if direction.y > 0:              # + turns the boom up (along +Y it went down through the base: found by 0065)
        direction = -direction
    j = joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], origin, direction, ref=pin, name="Boom")
    luff_cylinder(scene)
    return j


LUFF = "Luffing cylinder"
YELLOW = "Welded frames & structures #F9A800"       # the crane's yellow group: boom and pedestal (task 0122)
LUFF_ROD_EYE = (0.52, 0.3, 0.325)      # the rod eye's centre in the CAD pose, m (tools/make_test_crane.py luff_pins)


def luff_cylinder(scene):
    """The crane's luffing cylinder (task 0122) follows the boom: its barrel turns on the pedestal's pin, its rod's eye
    stays on the pin under the boom. Made once per project (the crane's first copy); None on a crane without one."""
    from mathutils import Vector

    from . import build, cylinders, joints
    if cylinders.find(scene, LUFF) is not None:
        return cylinders.find(scene, LUFF)
    if not any(o.get(build.PROP_NAME) == "HYDRAULIC CYLINDER.BARREL" for o in scene.objects):
        return None

    def pin_at(name):                  # a pin part's axis: along its own +y, from its own origin (its head side)
        ob = _ob(scene, name)
        m = ob.matrix_world
        return m @ Vector((0, 0.022, 0)), (m.to_3x3() @ Vector((0, 1, 0))).normalized(), ob

    c, _notes = cylinders.create(scene, [_ob(scene, "HYDRAULIC CYLINDER.BARREL")], [_ob(scene, "HYDRAULIC CYLINDER.ROD")],
                                 pin_at("PEDESTAL.LUFF.PIN"), pin_at("BOOM.LUFF.PIN"), name=LUFF)
    _update()
    # the boom stops where the cylinder does (closed … fully out: about -1.5° … 37.6°); outside it the rod would leave
    # its barrel (found by the independent tester)
    j, _reason = cylinders.arm_joint(scene, c)
    if j is not None:
        lo, hi = cylinders.drive(scene, c, j).values_for_range(c.closed_length, c.closed_length + c.full_stroke)
        j.rot_min, j.rot_max = min(lo, hi), max(lo, hi)
        j.use_limits = True
        joints.apply_limits(j, joints._model_size(scene))
    return c


def _tip(scene):
    from mathutils import Vector
    return _ob(scene, "BOOM").matrix_world @ Vector((1.5, 0, 0))


def _logo(path: str) -> str:
    """A small generic two-colour logo picture (no brand: the tour's own)."""
    import numpy as np

    from ..pccheck import runner
    px = np.zeros((60, 160, 3), np.float32)
    px[...] = (0.05, 0.22, 0.55)
    px[12:48, 12:48] = (0.95, 0.55, 0.05)
    px[22:38, 60:150] = (0.95, 0.95, 0.95)
    runner.write_png(path, px)
    return path


# ---------------------------------------------------------------------------
# the sets (one project each) and their stops
# ---------------------------------------------------------------------------

# ----- the crane (the hub: the project the owner opens) -----

@tour_set(HUB_SET, "Crane", "test_crane_a.step", added="0.2.47", changed="0.2.160")
def build_crane(b: Build):
    import bpy

    from . import callouts, cameras, joints, queue, turntable
    sc, s = b.scene, b.s
    _look("PRODUCT")
    boom = _boom_joint(sc)
    trolley = _ob(sc, "TROLLEY.ASM")
    from mathutils import Vector
    joints.create(sc, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=_ob(sc, "BOOM.ASM"), name="Trolley")
    view = _camera(b, "ISO", "Tour view")
    _shot(b, "Tour view")

    # Look: open sea, light looks
    s.env_detail = "SIMPLE"
    s.background = "SEA"
    _camera(b, "ISO", "Tour sea", lens=35.0)
    _shot(b, "@sea")
    _look("PRODUCT")
    s.background = "COLOR"
    _look("DARK")
    sc.camera = view
    _shot(b, "@looks")
    _look("PRODUCT")

    # Motion: joint, stack, exploded view
    a = _animation(b, "Boom up", "Tour view")
    _joint_step(a, "Boom", 0.0, 2.0, math.radians(35), label="Boom goes up")
    a = _animation(b, "Boom and trolley", "Tour view")
    _joint_step(a, "Boom", 0.0, 3.0, math.radians(25))
    _joint_step(a, "Trolley", 0.0, 3.0, 0.35, slide=True)
    fade_and_trail(sc, _animation(b, FADE_ANIM, "Tour view"))
    camera_rides(sc, _animation(b, CAMERA_ANIM, "Tour view"))
    from . import build, states
    root = build.model_roots(sc)[0]
    states.explode(sc, root, 0.6)
    _update()
    _camera(b, "ISO", "Tour explode", lens=40.0)
    _shot(b, "@explode")
    states.reset_pose(sc)
    sc.camera = view

    # Output: still, blur, turntable, finished video, labels, queue, shapes
    _shot(b, "@still")
    cam = _camera(b, "ISO", "Tour blur", lens=85.0)
    s.camera_blur = "LITTLE"
    t = _ob(sc, "TROLLEY")
    cameras.set_focus(cam, sc, t, t.matrix_world.translation.copy())
    _shot(b, "@blur")
    sc.camera = view

    s.turntable_seconds, s.turntable_quality = 4.0, "draft"
    tt = turntable.make(sc)["animation"]
    tt.out_resolution, tt.out_format = "preview", "presentation"
    sc.camera = view

    logo = _logo(b.file("Tour logo.png"))
    s.brand_logo = logo
    s.brand_contact = "www.example.com · test tour"
    s.wm_kind, s.wm_text, s.wm_size, s.wm_opacity = "CUSTOM", "TEST TOUR", 0.3, 0.5
    s.still_logo = "BR"          # the still's logo (a still with a logo was black off frame 1 until task 0060)
    a = _animation(b, "Finished video", "Tour view")
    _joint_step(a, "Boom", 0.0, 1.0, math.radians(30), label="The boom goes up")
    a.fin_logo, a.fin_title_on, a.fin_end_on, a.fin_captions = "BR", True, True, True
    a.fin_title, a.fin_subtitle = "Test crane", f"Fresing Render {b.version} test tour"
    a.fin_title_seconds = a.fin_end_seconds = 1.0
    a.video = "MP4"

    callouts.add(sc, _ob(sc, "BOOM"), _ob(sc, "BOOM").matrix_world.translation.copy(), "Boom")
    callouts.add(sc, _ob(sc, "TROLLEY"), _ob(sc, "TROLLEY").matrix_world.translation.copy(), "Trolley")
    s.callouts_on = True
    _shot(b, "@labels")
    s.callouts_on = False

    a = _animation(b, "Queue video", "Tour view")
    _joint_step(a, "Boom", 0.0, 0.4, math.radians(20))
    a.video = "MP4"
    for i in reversed(range(len(s.queue))):
        s.queue.remove(i)
    queue.add_job(sc, "STILL", shot="Still picture", quality="draft")
    queue.add_job(sc, "ANIMATION", animation="Queue video", quality="draft")
    _shot(b, "@queue")
    _shot(b, "@startlater")
    from . import logic                          # Every paint scheme (task 0074): two schemes to queue in
    logic.save_scheme(s, "Factory colours")
    g = s.groups.get(YELLOW) or (s.groups[0] if len(s.groups) else None)
    if g is not None:
        g.color = "RAL 5010"
        logic.save_scheme(s, "Blue")
        logic.apply_scheme(sc, "Factory colours")
    _shot(b, "@schemes")

    s.out_format = "social"
    from . import render
    render.apply_output(sc, s)
    _camera(b, "FRONT", "Tour upright")
    _shot(b, "@shapes")
    s.out_format = "presentation"
    render.apply_output(sc, s)
    sc.camera = view
    states.apply_shot(sc, "Tour view")
    bpy.context.view_layer.update()


FADE_ANIM = "Fade and trail"


def fade_and_trail(scene, a) -> None:
    """Fade, X-ray and trail (task 0073): the boom turns up while the trolley runs out; the cover turns X-ray, a line
    draws the trolley's path. Also used by the PC check line motion.fade."""
    from . import build, trails
    _joint_step(a, "Boom", 0.0, 3.0, math.radians(25), label="The boom goes up")
    _joint_step(a, "Trolley", 0.0, 3.0, 0.35, slide=True)
    cover = _ob(scene, "COVER")
    blk = a.blocks.add()
    blk.kind, blk.start, blk.duration, blk.easing = "FADE_OUT", 0.5, 1.5, "SMOOTH"
    blk.target_uid, blk.target_name = cover[build.PROP_UID], "COVER"
    blk.fade_xray = True
    blk.name = "The cover turns X-ray"
    trolley = _ob(scene, "TROLLEY")
    co = [v.co for v in trolley.data.vertices]
    centre = [(min(c[k] for c in co) + max(c[k] for c in co)) / 2 for k in range(3)]
    t = trails.add(scene, trolley, "CLICKED", centre)
    t.animation = a.name
    t.name = "Trolley path"
    t.color, t.thickness = (0.05, 0.85, 0.2), 0.008       # green: the crane is yellow


def _check_fade(scene):
    from mathutils import Vector

    from . import fade, trails
    cover = _ob(scene, "COVER")
    end = scene.frame_end
    scene.frame_set(1)
    _check(float(cover.get(fade.FADE, 0.0)) == 0.0, "the cover is see-through at the start")
    scene.frame_set(end)
    _check(abs(float(cover.get(fade.FADE, 0.0)) - 1.0) < 1e-6 and cover.get(fade.XRAY) == 1.0,
           "the cover did not turn X-ray")
    _check(not cover.hide_render, "the cover is hidden instead of X-ray")
    t = next((x for x in scene.fresing.trails if x.animation == FADE_ANIM), None)
    _check(t is not None and t.obj is not None and not t.obj.hide_viewport, "the trolley's trail line is not drawn")
    fr, pts = trails.frame_points(scene, t)
    _check(len(fr) > 20, f"the trail line has only {len(fr)} points")
    want = t.part.matrix_world @ Vector(t.local)
    off = (Vector(pts[-1]) - want).length
    _check(off < 1e-5, f"the trail line ends {off * 1000:.3f} mm from the trolley")
    length = float(sum((Vector(pts[k + 1]) - Vector(pts[k])).length for k in range(len(pts) - 1)))
    return f"cover X-ray at frame {end}; trail {len(fr)} points, {length * 1000:.0f} mm long"


CAMERA_ANIM = "Camera rides and flies"
RIDE_END, PATH_END = 2.0, 4.0


def camera_rides(scene, a) -> None:
    """Camera that rides along and flies a path (task 0087): the boom turns up while the trolley runs out; for 2 s the
    camera rides on the boom, then it flies a path round the crane and keeps the trolley in the middle. Also used by
    the PC check line camera.path."""
    from mathutils import Vector

    from . import build
    _joint_step(a, "Boom", 0.0, PATH_END, math.radians(30), label="The boom goes up")
    _joint_step(a, "Trolley", 0.0, PATH_END, 0.35, slide=True)
    boom, trolley = _ob(scene, "BOOM"), _ob(scene, "TROLLEY")
    ride = a.blocks.add()
    ride.kind, ride.camera_mode, ride.start, ride.duration, ride.cam_blend = "CAMERA", "RIDE", 0.0, RIDE_END, 0.0
    ride.target_uid, ride.target_name = boom[build.PROP_UID], "BOOM"
    ride.name = "The camera rides on the boom"
    fly = a.blocks.add()
    fly.kind, fly.camera_mode, fly.start, fly.duration = "CAMERA", "PATH", RIDE_END, PATH_END - RIDE_END
    fly.easing, fly.cam_blend, fly.path_look = "LINEAR", 0.5, "PART"
    fly.aim_uid, fly.aim_name = trolley[build.PROP_UID], "TROLLEY"
    fly.name = "The camera flies round, watching the trolley"
    s = scene.fresing
    mn, mx = Vector(s.bounds_min), Vector(s.bounds_max)
    c, size = (mn + mx) / 2, max((mx - mn).length, 0.5)
    for d in ((0.9, -1.1, 0.7), (-0.2, -1.4, 0.9), (-1.2, -0.6, 1.1)):
        fly.path_points.add().co = c + Vector(d) * size
    from . import camera_path
    camera_path.show_path(scene, fly)


def _check_camera(scene):
    """The camera's error numbers: the ride against the boom, the path's end and speed, the trolley in the middle."""
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from . import animation, camera_path
    a = scene.fresing.animations.get(CAMERA_ANIM) or animation.active(scene)
    boom = _ob(scene, "BOOM")
    fps = animation.fps_of(a)
    f_ride, f_end = animation.frame_of(a, RIDE_END), animation.frame_of(a, PATH_END)
    scene.frame_set(1)
    cam = scene.camera
    _check(cam is not None and cam.get("fr_anim_camera"), "the animation has no Animation camera")
    offset = boom.matrix_world.inverted() @ cam.matrix_world
    ride_mm = ride_deg = 0.0
    for f in range(1, f_ride + 1):
        scene.frame_set(f)
        want = boom.matrix_world @ offset
        ride_mm = max(ride_mm, (cam.matrix_world.translation - want.translation).length * 1000)
        ride_deg = max(ride_deg, camera_path.angle_between(cam.matrix_world, want))
    _check(ride_mm < 0.01 and ride_deg < 0.01,
           f"the riding camera is {ride_mm:.3f} mm / {ride_deg:.3f}° off the boom")
    fly = next(b for b in a.blocks if b.kind == "CAMERA" and b.camera_mode == "PATH")
    last = Vector(fly.path_points[len(fly.path_points) - 1].co)
    start_blend = f_ride + int(round(fly.cam_blend * fps))
    pos, middle = [], 0.0
    trolley = _ob(scene, "TROLLEY")
    for f in range(f_ride, f_end + 1):
        scene.frame_set(f)
        pos.append(cam.matrix_world.translation.copy())
        if f >= start_blend:
            uv = world_to_camera_view(scene, cam, camera_path._middle(trolley))
            middle = max(middle, abs(uv.x - 0.5), abs(uv.y - 0.5))
    end_mm = (pos[-1] - last).length * 1000
    from ..core import camera_path as P                   # speed measured along the path (a bend is no slow-down)
    path = P.Path([tuple(pos[0])] + [tuple(p.co) for p in fly.path_points])
    along = [path.locate(tuple(p)) for p in pos]
    steps = [along[i + 1] - along[i] for i in range(len(along) - 1)]
    even = (max(steps) / max(min(steps), 1e-9) - 1.0) * 100
    _check(end_mm < 0.01, f"the path ends {end_mm:.3f} mm from its last point")
    _check(even < 2.0, f"the speed along the path changes by {even:.1f} %")
    _check(middle < 0.01, f"the trolley is {middle * 100:.1f} % off the middle of the picture")
    return (f"ride {ride_mm:.4f} mm / {ride_deg:.4f}° off the boom; path end {end_mm:.4f} mm, speed even within "
            f"{even:.2f} %; trolley {middle * 100:.2f} % off the middle")


def _looks() -> list:
    from ..core import studio
    return list(studio.LOOKS)


def _check_sea(scene):
    from . import surroundings
    _check(scene.fresing.background == "SEA", "the background is not the open sea")
    _check(surroundings.root_object() is not None, "the sea was not built")
    return "open sea built"


def _check_looks(scene):
    import bpy
    for look in _looks():
        res = bpy.ops.fresing.light_look(look=look)
        _check(res == {"FINISHED"}, f"light look {look} returned {res}")
    from . import states
    states.apply_shot(scene, "Light looks")
    return f"{len(_looks())} looks apply"


def _check_boom(scene):
    from . import joints
    j = joints.find(scene, "Boom")
    _check(j is not None, "the joint 'Boom' is missing")
    end = scene.frame_end
    scene.frame_set(1)
    a = _tip(scene).copy()
    scene.frame_set(end)
    moved = (_tip(scene) - a).length
    _check(moved > 0.5, f"the boom's tip moved only {moved * 1000:.0f} mm")
    off = luff_eye_off(scene)
    _check(off < 0.05, f"the luffing cylinder's rod eye is {off:.2f} mm off its pin under the boom")
    return f"tip moved {moved * 1000:.0f} mm, {end} frames; rod eye on its pin to {off:.3f} mm"


def luff_eye_off(scene) -> float:
    """How far (mm) the luffing cylinder's rod eye sits from the pin under the boom, square to the pin."""
    from mathutils import Vector
    _update()
    rod, pin = _ob(scene, "HYDRAULIC CYLINDER.ROD"), _ob(scene, "BOOM.LUFF.PIN")
    pr = pin.matrix_world @ Vector((0, 0.022, 0))
    axis = (pin.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
    eye = rod.matrix_world @ Vector(LUFF_ROD_EYE)     # the rod's own coordinates are the crane's (its assembly sits at 0)
    v = eye - pr
    return (v - axis * v.dot(axis)).length * 1000.0


def _check_stack(scene):
    from mathutils import Matrix, Vector

    from . import joints
    jb, jt = joints.find(scene, "Boom"), joints.find(scene, "Trolley")
    _check(jb is not None and jt is not None, "the joints 'Boom' and 'Trolley' are missing")
    trolley = _ob(scene, "TROLLEY.ASM")
    scene.frame_set(1)
    cad = trolley.matrix_world.translation.copy()
    scene.frame_set(scene.frame_end)
    sign = 1 if joints.axis_world(jb)[1].y > 0 else -1
    pivot = Vector((0.1, 0.3, 0.4))
    a, d = joints.get_value(jb), joints.get_value(jt)
    want = pivot + Matrix.Rotation(sign * a, 3, "Y") @ (cad - pivot + Vector((d, 0, 0)))
    err = (trolley.matrix_world.translation - want).length
    _check(abs(math.degrees(a) - 25) < 0.01 and abs(d - 0.35) < 1e-5,
           f"at the end the boom is at {math.degrees(a):.1f}° and the trolley at {d * 1000:.0f} mm")
    _check(err < 1e-3, f"the trolley is {err * 1000:.1f} mm off where boom + slide put it")
    return "boom 25° + trolley 350 mm"


def _check_explode(scene):
    from . import joints
    n = len(joints.free_moves(scene))
    _check(n >= 3, f"the exploded view moved only {n} subassemblies")
    return f"{n} subassemblies moved"


def _check_still(scene):
    _check(scene.camera is not None, "no camera")
    return f"camera '{scene.camera.name}'"


def _check_blur(scene):
    from . import cameras
    cam = scene.camera
    _check(cam is not None and cam.data.dof.use_dof, "the background blur is off")
    _check(cameras.focus_marker(cam) is not None, "no marker for the sharp spot")
    return f"focus {cam.data.dof.focus_distance:.2f} m"


def _check_turntable(scene):
    cam = scene.camera
    _check(cam is not None, "no camera")
    scene.frame_set(1)
    a = cam.matrix_world.translation.copy()
    scene.frame_set(max(2, scene.frame_end // 2))
    moved = (cam.matrix_world.translation - a).length
    _check(moved > 0.3, f"the turntable camera moved only {moved * 1000:.0f} mm in half the video")
    return f"{scene.frame_end} frames"


def _check_finishing(scene):
    a = scene.fresing.animations.get("Finished video")
    _check(a is not None and a.fin_title_on and a.fin_end_on and a.fin_captions and a.fin_logo != "NONE",
           "title card, end card, captions or logo are off")
    from . import video
    _check(video.captions_of(a, scene), "no captions")
    _check(bool(video._logo_path(scene.fresing)), "the brand kit's logo file is missing")
    s = scene.fresing
    was = s.wm_kind
    try:                                      # task 0176: the Fresing logo is there as a watermark choice
        s.wm_kind = "FRESING_LOGO"
        fin = video.finishing_for_still(scene, True)
    finally:
        s.wm_kind = was
    _check(bool(fin.wm_logo_file) and not fin.watermark, "the Fresing logo watermark file is missing")
    return "title, end card, captions, logo, Fresing logo watermark"


def _labels_on(scene):
    scene.fresing.callouts_on = True


def _check_labels(scene):
    from . import callouts
    s = scene.fresing
    n = sum(1 for c in s.callouts if callouts.usable(c))
    _check(n == 2 and s.callouts_on, f"{n} labels, labels {'on' if s.callouts_on else 'off'}")
    return "2 labels"


def _check_queue(scene):
    s = scene.fresing
    kinds = sorted(j.kind for j in s.queue)
    _check(kinds == ["ANIMATION", "STILL"], f"the queue holds {kinds}, not a picture and a video")
    return "a picture and a video waiting"


def _check_start_later(scene):
    from . import queue
    try:
        queue.schedule(scene, 3600)              # the same call as the Start later button; then cancelled again
        _check(queue.delay_pending() and queue.describe_delay().startswith("Starts in"),
               "Start later did not set a delayed start")
        text = queue.describe_delay()
    finally:
        queue.cancel_delay()
    _check(not queue.delay_pending(), "Cancel did not stop the delayed start")
    return text


def _check_schemes(scene):
    from . import queue
    s = scene.fresing
    names = queue.schemes_to_queue(scene, "ALL")
    _check(len(names) >= 2, f"{len(names)} paint schemes: the tour needs two")
    looks = [(g.name, g.color, g.material) for g in s.groups]
    before = len(s.queue)
    try:
        jobs = queue.add_in_schemes(scene, "ANIMATION", names, animation="Queue video")
        got = [(j.kind, j.scheme) for j in s.queue[before:]]
        _check(len(jobs) == len(names) and got == [("ANIMATION", n) for n in names],
               f"the queue got {got}, not one video per scheme")
        _check(all(j.label.endswith(f"in {j.scheme}") for j in s.queue[before:]), "a job does not name its scheme")
    finally:
        for i in reversed(range(before, len(s.queue))):
            s.queue.remove(i)
    _check([(g.name, g.color, g.material) for g in s.groups] == looks, "queueing changed the project's colours")
    return f"{len(names)} videos: " + ", ".join(names)


def _check_shapes(scene):
    r = scene.render
    _check(r.resolution_y > r.resolution_x, f"the picture is {r.resolution_x} x {r.resolution_y}: not upright")
    return f"{r.resolution_x} x {r.resolution_y}"


# ----- the other test models -----

@tour_set("looks", "Materials", "test_crane_a.step", added="0.2.47", changed="0.2.101")
def build_materials(b: Build):
    from . import logic
    sc, s = b.scene, b.s
    _look("PRODUCT")
    picks = (("Welded frames", "paint_gloss", "RAL 1003", 0.6), ("Colour #333333", "cast_iron_painted", "", 0.6),
             ("Shafts", "steel_ground", "", 0.0), ("Hydraulic", "aluminium_anodized_black", "", 0.0),
             ("Chrome rods", "chrome_rod", "", 0.0),
             ("Casters", "rubber_black", "", 0.0), ("Covers", "aluminium_anodized_color", "#2E6DB4", 0.0),
             ("Fasteners", "zinc_flake", "", 0.0))
    for g in s.groups:
        for start, mat, col, wear in picks:
            if g.name.startswith(start):
                g.material = mat
                if col:
                    g.color = col
                g.wear = wear
    logic.refresh_group_materials(sc)
    _camera(b, "ISO", "Tour view", lens=60.0)
    _shot(b, "@materials")


def _check_materials(scene):
    s = scene.fresing
    worn = [g for g in s.groups if g.wear > 0.5]
    _check(worn, "no group has Wear")
    mats = {g.material for g in s.groups}
    _check(len(mats) >= 4, f"only {len(mats)} different materials")
    return f"{len(mats)} materials, Wear {worn[0].wear:.1f} on '{worn[0].name}'"


@tour_set("faces", "Painted faces", "test_faces_a.step", added="0.2.47")
def build_faces(b: Build):
    import bpy

    from . import logic, ops_panels
    sc, s = b.scene, b.s
    _look("PRODUCT")
    cover = _ob(sc, "COVER")
    logic.ensure_group(s, "Painted by hand (tour)")
    s.groups["Painted by hand (tour)"].material = "paint_gloss"
    s.groups["Painted by hand (tour)"].color = "RAL 3020"
    s.face_group = "Painted by hand (tour)"
    bpy.context.view_layer.objects.active = cover
    ops_panels.paint_click(bpy.context, cover, 5)
    _camera(b, "ISO", "Tour view")
    _shot(b, "@faces")


def _check_faces(scene):
    from . import faces
    sets = faces.get_sets(_ob(scene, "HOUSING").data)
    _check(len(sets) == 2, f"the housing should have 2 painted faces from CAD, has {len(sets)}")
    _check(faces.groups_on(_ob(scene, "COVER")) == ["Painted by hand (tour)"], "the face painted by hand lost its paint")
    return "2 CAD faces, 1 by hand"


@tour_set("decals", "Logos and stickers", "test_decals_a.step", added="0.2.47")
def build_decals(b: Build):
    from . import decals
    sc = b.scene
    _look("PRODUCT")
    panel, barrel = _ob(sc, "PANEL"), _ob(sc, "BARREL")
    decals.add(panel, 5, (0.31, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="WARN_GENERAL")
    decals.add(panel, 5, (0.12, 0.15, 0.01), (0, 0, 1), "TEXT", text="TEST TOUR")
    decals.add(barrel, 0, (0.06, 0.0, 0.1), (1, 0, 0), "STICKER", sticker="WARN_HOT")
    _camera(b, "ISO", "Tour view")
    _shot(b, "@decals")


def _check_decals(scene):
    import bpy

    from . import decals
    shown = [o for o in bpy.data.objects if decals.is_decal(o)]
    _check(len(shown) >= 3, f"only {len(shown)} decals on the model")
    return f"{len(shown)} decals"


MILL_SLOT = (("Z", 0.0, 0.8, -25.0), ("X", 0.8, 1.6, 60.0))
MARKS_ANIM = "Tool marks"


def _mill_set(b: Build, chips: str = "", raw: str = ""):
    """The test mill with X/Y/Z, a slot (plunge 25 mm, 60 mm along X), the end mill as bit, the block as workpiece."""
    from . import machining
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    a = _animation(b, "Mill a slot")
    for j, start, dur, to in MILL_SLOT:
        blk = a.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", j, start, dur, "LINEAR"
        blk.use_from, blk.to_dist = True, to * 0.001
    import bpy
    _pick("bit", _ob(sc, "END MILL D10"))
    stock = _ob(sc, "STOCK 200x200x40")
    _pick("workpiece", stock)
    if raw:
        g = sc.fresing.groups.get(stock.get("fr_group", ""))
        if g is not None:
            g.material = raw
    if chips:
        machining.settings(sc).chips = chips
    from mathutils import Vector
    tip = stock.matrix_world.translation + Vector((0.0, 0.0, 0.05))
    cam = _close_camera(b, tip, 0.25, "Tour close-up")
    a.start_shot = _shot(b, "Tour: close-up").name
    del cam
    _bake(sc, a)
    return a


CUT_ANIM = "The pedestal opens up"
CUT_FROM = 0.2                  # the cut starts 200 mm in front of the pedestal (nothing cut) and slides to the middle


def cutaway(scene, a=None):
    """Cutaway (task 0086): a plane cut through the crane's pedestal and boom, hatched, taking away the half that
    faces the camera; ``a``: a Move joint step slides it in from 200 mm in front. Also used by the PC check line
    looks.cutaway. Returns the cut."""
    from mathutils import Euler, Matrix, Vector

    from . import section
    ped = _ob(scene, "PEDESTAL")
    cut = section.add(scene, [("PART", ped, ""), ("PART", _ob(scene, "BOOM"), "")], "PLANE")
    centre = sum((ped.matrix_world @ Vector(c) for c in ped.bound_box), Vector()) / 8.0
    # through the pedestal's middle, along the boom; the arrow to the front (-Y): the front half goes
    section.set_world(scene, cut, Matrix.Translation(centre) @ Euler((math.pi / 2, 0.0, 0.0)).to_matrix().to_4x4())
    cut.hatch = True
    if a is not None:
        blk = _joint_step(a, section.joint_of(scene, cut).name, 0.0, 2.0, 0.0, slide=True,
                          label="The cut slides in", easing="SMOOTH")
        blk.use_from = False
        blk.from_dist = CUT_FROM
    return cut


MARINE_WATER = 4.5            # the marine stop's waterline: above the studio floor, which would hide the pile's foot


def marine_demo(scene, water: float = MARINE_WATER) -> dict:
    """The marine looks (task 0116) on plain shapes: a yellow pile 1.2 m across and 8 m tall standing 4 m deep in
    water (marine paint with growth), a grey wall with run-down streaks, a concrete block; the crane is hidden.
    The waterline is the scene's (``marine_looks.WATERLINE``), as the sea of the surroundings sets it.
    Returns {material id: material}. Used by the test tour and the PC check."""
    import bpy

    from . import build, marine_looks, materials
    for ob in build.iter_parts(scene):
        ob.hide_render = ob.hide_viewport = True
    scene[marine_looks.WATERLINE] = float(water)
    made = {}

    def add(name, make, mat_id, colour, location, scale=(1.0, 1.0, 1.0)):
        import bmesh
        bm = bmesh.new()
        make(bm)
        me = bpy.data.meshes.new(f"Marine {name}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"Marine {name}", me)      # no bpy.ops: works from any button (tour Make)
        scene.collection.objects.link(ob)
        ob.location, ob.scale = location, scale
        mat = materials.ensure_material(f"Marine looks: {name}", mat_id, colour)
        materials.assign(ob, mat)
        made[mat_id] = mat

    def cylinder(bm):
        import bmesh
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48, radius1=0.6, radius2=0.6, depth=8.0)

    def cube(bm):
        import bmesh
        bmesh.ops.create_cube(bm, size=1.0)
    add("pile", cylinder, "paint_marine_growth", "RAL 1023", (0.0, 0.0, water))
    add("wall", cube, "paint_marine_streaks", "RAL 7035", (2.2, 1.5, 3.0), (1.2, 0.3, 6.0))
    add("block", cube, "concrete", "", (-2.0, 0.8, 0.5), (1.6, 1.6, 1.0))
    return made


def marine_camera(scene, water: float = MARINE_WATER, name: str = "Marine looks"):
    import bpy
    from mathutils import Matrix, Vector
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    scene.collection.objects.link(cam)
    eye, target = Vector((5.0, -11.0, water + 1.0)), Vector((0.0, 0.0, water - 0.3))
    fwd = (target - eye).normalized()
    right = fwd.cross(Vector((0.0, 0.0, 1.0))).normalized()
    up = right.cross(fwd)
    cam.matrix_world = Matrix([[right[0], up[0], -fwd[0], eye[0]], [right[1], up[1], -fwd[1], eye[1]],
                               [right[2], up[2], -fwd[2], eye[2]], [0, 0, 0, 1]])
    cam.data.lens = 40.0
    cam["fr_camera"] = True
    scene.camera = cam
    return cam


@tour_set("marine", "Marine looks", "test_crane_a.step", added="0.2.94", changed="0.2.101")
def build_marine(b: Build):
    _look("PRODUCT")
    marine_demo(b.scene)
    marine_camera(b.scene, name="Tour marine")
    _shot(b, "@marine")


def _check_marine(scene):
    import bpy

    from . import marine_looks
    want = {"paint_marine_growth", "paint_marine_streaks", "concrete"}
    shown = {ob.active_material.get("fr_material") for ob in bpy.data.objects
             if ob.name.startswith("Marine ") and ob.type == "MESH" and ob.active_material is not None}
    _check(want <= shown, f"missing looks: {', '.join(sorted(want - shown))}")
    pile = bpy.data.objects.get("Marine pile")
    _check(marine_looks.nodes_of(pile.active_material), "the pile's material has no marine growth")
    _check(abs(marine_looks.waterline(scene) - MARINE_WATER) < 1e-6, "the waterline moved")
    return f"{len(want)} marine looks, waterline {MARINE_WATER:.1f} m"


@tour_set("cutaway", "Slice", "test_crane_a.step", added="0.2.64", changed="0.2.168")
def build_cutaway(b: Build):
    from mathutils import Vector
    sc = b.scene
    _look("PRODUCT")
    ped = _ob(sc, "PEDESTAL")
    centre = sum((ped.matrix_world @ Vector(c) for c in ped.bound_box), Vector()) / 8.0
    _close_camera(b, centre + Vector((0.1, 0.0, 0.05)), 0.55, "Tour cutaway")
    shot = _shot(b, "Tour: cutaway")
    cutaway(sc, _animation(b, CUT_ANIM, shot.name))


def _check_cutaway(scene):
    from mathutils import Vector

    from . import joints, section
    cut = scene.fresing.cuts[0] if len(scene.fresing.cuts) else None
    _check(cut is not None and cut.enabled, "there is no cut, or it is off")
    names = sorted(p.get("fr_name", p.name) for p in section.cut_parts(scene, cut))
    _check(names == ["BOOM", "PEDESTAL"], f"the cut cuts {names}, not the boom and the pedestal")
    _check(all(section.is_wrapped(m) for p in section.cut_parts(scene, cut) for m in section._materials(p)),
           "a material of a cut part shows no cut")
    j = section.joint_of(scene, cut)
    _check(j is not None, "the cut has no slide joint")
    _o, d = joints.axis_world(j)
    scene.frame_set(1)
    start = cut.shape.matrix_world.translation.copy()
    scene.frame_set(scene.frame_end)
    end = cut.shape.matrix_world.translation.copy()
    moved = (start - end).dot(d)
    _check(abs(moved - CUT_FROM) < 1e-5, f"the cut slid {moved * 1000:.1f} mm, not {CUT_FROM * 1000:.0f} mm")
    ped = _ob(scene, "PEDESTAL")
    centre = sum((ped.matrix_world @ Vector(c) for c in ped.bound_box), Vector()) / 8.0
    off = abs((end - centre).dot(d))
    _check(off < 1e-4, f"at the end the cut is {off * 1000:.1f} mm from the pedestal's middle")
    return f"{len(names)} parts cut, slid {moved * 1000:.0f} mm into the middle"


@tour_set("mill", "Milling a slot", "test_mill.step", added="0.2.47", changed="0.2.101")
def build_mill(b: Build):
    _mill_set(b, chips="FEW", raw="steel_raw")


def _milled(scene):
    from . import machining
    machining.update_if_needed(scene)
    machining.refresh(scene, force=True)
    return machining.settings(scene).cut_mesh


def _check_cut_look(scene):
    import numpy as np

    from . import machining
    scene.frame_set(scene.frame_end)
    me = _milled(scene)
    stock = _ob(scene, "STOCK 200x200x40")
    _check(me is not None and stock.data is me, "the block does not show its cut")
    n = int(me.get(machining.CUT_SLOT, -1))
    _check(0 < n < len(stock.material_slots), "the milled block has no material slot for cut faces")
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    cut = int((mi == n).sum())
    _check(cut > 0, "no face of the slot has the cut look")
    mat = stock.material_slots[n].material
    _check(mat is not None and mat.get("fr_material") == "steel_machined",
           f"cut faces show '{mat.name if mat else 'nothing'}', not machined steel")
    return f"{cut} cut faces machined, the rest mill scale"


def _check_chips(scene):
    import bpy

    from . import chips
    scene.frame_set(scene.frame_end)
    _milled(scene)
    scene.frame_set(scene.frame_end)
    n = sum(len(o.data.vertices) for o in (bpy.data.objects.get(chips.OBJ_RIDE), bpy.data.objects.get(chips.OBJ_WORLD))
            if o is not None)
    _check(n > 0, "no chips at the end of the cut")
    return f"{n} chips"


@tour_set("cylinder", "Cylinder", "test_cylinder_a.step", added="0.2.47", changed="0.2.101")
def build_cylinder(b: Build):
    from mathutils import Vector

    from . import build, cylinders, joints
    sc = b.scene
    _look("PRODUCT")

    def at_y(name, y):
        hits = [o for o in sc.objects if o.get(build.PROP_NAME) == name]
        _check(bool(hits), f"the test model has no part '{name}'")
        return min(hits, key=lambda o: abs(o.matrix_world.translation.y - y))

    along_y = Vector((0, 1, 0))
    barrel_pin, rod_pin = Vector((0.5, 0.08, 0.15)), Vector((0.8, 0.08, 0.45))
    joints.create(sc, "ROTATE", [_ob(sc, "ARM.ASM")], Vector((0.1, 0.2, 0.6)), along_y, name="Luff")
    c, _notes = cylinders.create(sc, [at_y("CYL.BARREL", 0.08)], [at_y("CYL.ROD", 0.08)],
                                 (barrel_pin, along_y, _ob(sc, "BASE.PIN")),
                                 (rod_pin, along_y, _ob(sc, "ARM.ROD.PIN")), name="Luff cylinder")
    _update()
    cylinders.set_mode(sc, c, "DRIVE")
    # the second cylinder and the telescopic one follow the arm (task 0067: left standing, the arm's pin tore through
    # their eyes)
    for barrel, rod, stage, y in (("CYL.BARREL", "CYL.ROD", "", 0.32), ("TELE.BARREL", "TELE.ROD", "TELE.STAGE", 0.2)):
        cylinders.create(sc, [at_y(barrel, y)], [at_y(rod, y)],
                         (Vector((0.5, y, 0.15)), along_y, _ob(sc, "BASE.PIN")),
                         (Vector((0.8, y, 0.45)), along_y, _ob(sc, "ARM.ROD.PIN")),
                         name=f"Follower {barrel.split('.')[0].lower()}", stages=[at_y(stage, y)] if stage else ())
    _update()
    _camera(b, "FRONT", "Tour view")
    shot = _shot(b, "Tour: cylinder")
    a = _animation(b, "Stroke out", shot.name)
    blk = a.blocks.add()
    blk.kind, blk.cylinder, blk.start, blk.duration = "CYLINDER", c.name, 0.0, 3.0
    blk.use_from, blk.from_stroke, blk.to_stroke = False, 0.0, min(0.15, c.full_stroke)
    blk.name = "Stroke 0 → 150 mm"


def _check_cylinder(scene):
    from mathutils import Vector

    from . import build, cylinders, joints
    c = cylinders.find(scene, "Luff cylinder")
    _check(c is not None, "the cylinder is missing")
    arm = joints.find(scene, "Luff")
    eyes = [o for o in scene.objects if o.get(build.PROP_NAME) == "ROD.EYE"]
    eye = min(eyes, key=lambda o: abs(o.matrix_world.translation.y - 0.08))
    pin = _ob(scene, "ARM.ROD.PIN")

    def off():                      # the eye's hole axis against the pin's axis (both along Y), in mm
        pe = eye.matrix_world @ Vector(eye.data["fr_axes"][0:3])
        pp = pin.matrix_world @ Vector(pin.data["fr_axes"][0:3])
        return math.hypot(pe.x - pp.x, pe.z - pp.z) * 1000.0

    worst = 0.0
    scene.frame_set(1)
    _update()
    a0 = joints.get_value(arm)
    for f in (1, scene.frame_end // 2, scene.frame_end):
        scene.frame_set(f)
        _update()
        worst = max(worst, off())
    a1 = joints.get_value(arm)
    _check(abs(a1 - a0) > math.radians(3), f"the arm turned only {math.degrees(a1 - a0):.1f}°")
    _check(worst < 0.05, f"the rod's eye is {worst:.2f} mm off its pin")
    err = worst / 1000.0
    return f"arm {abs(math.degrees(a1 - a0)):.1f}°, eye on its pin to {err * 1000:.3f} mm"


LIFT_ROD_PIN = (0.75 * math.cos(math.radians(15.0)), -0.08, 0.1 + 0.75 * math.sin(math.radians(15.0)))


@tour_set("linkage", "Mechanisms", "test_linkage_a.step", added="0.2.47", changed="0.2.54")
def build_linkage(b: Build):
    from mathutils import Vector

    from . import cylinders, linkages
    sc = b.scene
    _look("PRODUCT")
    arms = [_ob(sc, f"LIFT.ARM.{s}.{i}") for i in (1, 2, 3) for s in ("IN", "OUT")]
    m = linkages.create(sc, "SCISSOR", [[x] for x in arms] + [[_ob(sc, "LIFT.PLATFORM.ASM")]],
                        base=_ob(sc, "LIFT.BASE.ASM"), name="Scissor lift")
    s2 = linkages.create(sc, "SLIDER", [[_ob(sc, n)] for n in ("CRANK.CRANK.ASM", "CRANK.ROD.ASM", "CRANK.PISTON.ASM")],
                         base=_ob(sc, "CRANK.BASE.ASM"), name="Slider-crank")
    j = linkages.input_joint(sc, s2)
    _update()
    _update()
    # the lifting cylinder follows the bottom inner arm (task 0067: left standing, the arm's pin tore through its eye)
    along_y = Vector((0, 1, 0))
    cylinders.create(sc, [_ob(sc, "LIFT.CYL.BARREL")], [_ob(sc, "LIFT.CYL.ROD")],
                     (Vector((0.45, -0.08, 0.1)), along_y, _ob(sc, "LIFT.BASE.CYL.PIN")),
                     (Vector(LIFT_ROD_PIN), along_y, _ob(sc, "LIFT.CYL.PIN")), name="Lift cylinder")
    _update()
    _camera(b, "FRONT", "Tour view")
    shot = _shot(b, "Tour: mechanisms")
    a = _animation(b, "Lift and crank", shot.name)
    blk = a.blocks.add()
    blk.kind, blk.mechanism, blk.start, blk.duration = "MECHANISM", m.name, 0.0, 3.0
    blk.use_from, blk.to_height = True, 1.5
    blk.name = "Platform to 1.5 m"
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", j.name, 0.0, 3.0, "LINEAR"
    blk.use_from, blk.to_angle = True, math.radians(360)


def _check_linkage(scene):
    from mathutils import Vector
    part = _ob(scene, "LIFT.PLATFORM.PIN")
    scene.frame_set(scene.frame_end)
    _update()
    _update()
    p = part.matrix_world @ Vector(part.data["fr_axes"][0:3])
    _check(abs(p.z - 1.6) < 1e-3, f"the platform's pin is at {p.z * 1000:.1f} mm, not 1600 mm")
    return "platform at 1.5 m"


@tour_set("waycover", "Way cover", "test_waycover_b.step", added="0.2.47", changed="0.2.101")
def build_waycover(b: Build):
    from mathutils import Vector

    from . import joints, waycover
    sc = b.scene
    _look("PRODUCT")
    names = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
             ["COVER.5"]]
    axis = joints.create(sc, "SLIDE", [_ob(sc, "CARRIAGE")], Vector((0.1, 0.15, 0.1)), Vector((1, 0, 0)),
                         name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, 0.5
    c = waycover.settings(sc)
    c.axis, c.total = "X axis", 0.5
    for g in names:
        waycover.add_section(sc, [_ob(sc, n) for n in g])
    built, problems = waycover.make(sc)
    _check(built == 5 and not problems, f"the way cover was not made: {problems}")
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: way cover")
    a = _animation(b, "X axis out and back", shot.name)
    _joint_step(a, "X axis", 0.0, 2.0, 0.5, slide=True)
    _joint_step(a, "X axis", 2.5, 2.0, 0.0, slide=True)


@tour_set("waycover2", "Two way covers", "test_waycover_c.step", added="0.2.61", changed="0.2.101")
def build_waycover_two(b: Build):
    from . import waycover
    sc = b.scene
    _look("PRODUCT")
    waycover.set_up_test_model(sc, carriage=True)
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: two way covers")
    a = _animation(b, "Carriage across and back", shot.name)
    _joint_step(a, "X axis", 0.0, 2.0, 0.5, slide=True)
    _joint_step(a, "X axis", 2.5, 2.0, 0.0, slide=True)


def _check_waycover_two(scene):
    from mathutils import Vector

    def min_x(o):
        return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)

    scene.frame_set(1)
    _update()
    rest = [min_x(_ob(scene, f"COVER.R.{k}")) for k in (1, 4)]
    scene.frame_set(round(1 + 2.0 * 25))
    _update()
    _update()
    mm = [(min_x(_ob(scene, f"COVER.R.{k}")) - r) * 1000 for k, r in zip((1, 4), rest)]
    _check(abs(mm[0] - 100) < 0.1 and abs(mm[1] - 400) < 0.1,
           f"the right cover's sections 1 and 4 moved {mm[0]:.1f} and {mm[1]:.1f} mm, not 100 and 400 mm")
    return "right cover closed: sections 100 … 500 mm"


def _check_waycover(scene):
    from mathutils import Vector

    def min_x(o):
        return min((o.matrix_world @ Vector(c)).x for c in o.bound_box)

    scene.frame_set(1)
    _update()
    rest = min_x(_ob(scene, "COVER.5"))
    f = round(1 + 2.0 * 25)
    scene.frame_set(f)
    _update()
    _update()
    mm = (min_x(_ob(scene, "COVER.5")) - rest) * 1000
    _check(abs(mm - 500) < 0.1, f"the last section moved {mm:.1f} mm, not 500 mm")
    return "5 sections, the last 500 mm"


# ---------------------------------------------------------------------------
# hoses, a cable and drag chains (task 0058)
# ---------------------------------------------------------------------------

HOSES_ANIM = "Arm up and down"
CHAINS_ANIM = "Program with drag chains"
CHAINS_PROGRAM = """(T1 D=6. CR=0. - flat end mill)
G21 G90 G94 G17
G0 X0 Y0 Z40
G1 X130 Y-80 Z15 F6000
G1 X-130 Y80 Z70
G2 X-90 Y80 I20 J0
G0 X0 Y0 Z40
M30
"""


def hoses_motion(a) -> None:
    """The steps of the hoses stop: the arm goes up 18° and down to -8° while the slide goes out and back."""
    _joint_step(a, "Luff", 0.0, 2.0, math.radians(18.0), label="Arm up 18°")
    _joint_step(a, "Slide", 0.5, 2.0, 0.12, slide=True, label="Slide out 120 mm")
    _joint_step(a, "Luff", 2.0, 2.0, math.radians(-8.0), label="Arm down to -8°")
    _joint_step(a, "Slide", 2.5, 1.5, -0.10, slide=True, label="Slide back 220 mm")


@tour_set("hoses", "Hoses and a cable", "test_flex_hoses_a.step", added="0.2.78")
def build_hoses(b: Build):
    from . import flex
    sc = b.scene
    _look("PRODUCT")
    made = flex.set_up_test_hoses(sc)
    _check(len(made["items"]) == 4, f"only {len(made['items'])} of the 4 hoses were made")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: hoses")
    hoses_motion(_animation(b, HOSES_ANIM, shot.name))


def flex_errors(scene) -> tuple[float, float, float]:
    """How well the hoses and chains shown at this frame fit, read from what is drawn: the largest distance of an
    end from its point on the part it sits on (m), the largest error of a hose's length (share), the largest
    error of a chain's link length (m)."""
    from mathutils import Vector

    from ..core import flex as fcore
    from . import flex
    end = stretch = chord = 0.0
    for it in scene.fresing.flex:
        if not it.enabled:
            continue
        if it.kind == "HOSE":
            pts = flex.shape_now(scene, it)
            a = it.a_part.matrix_world @ Vector(it.a_point)
            c = it.b_part.matrix_world @ Vector(it.b_point)
            end = max(end, (Vector(pts[0]) - a).length, (Vector(pts[-1]) - c).length)
            stretch = max(stretch, abs(float(fcore.polyline_length(pts)) / it.length - 1.0))
        else:
            pins = flex.pins_now(scene, it)
            c = it.b_part.matrix_world @ Vector(it.b_point)
            end = max(end, (Vector(pins[-1]) - c).length)
            for i in range(len(pins) - 1):
                chord = max(chord, abs((Vector(pins[i + 1]) - Vector(pins[i])).length - it.pitch))
    return end, stretch, chord


def _flex_over_frames(scene, kind: str):
    """(largest end error, largest length error, largest link error, how far the shapes moved) over the animation."""
    import numpy as np

    from . import flex
    items = [it for it in scene.fresing.flex if it.kind == kind]
    _check(bool(items), "the hoses are missing" if kind == "HOSE" else "the drag chains are missing")
    worst = [0.0, 0.0, 0.0]
    first, moved = None, 0.0
    frames = sorted({1, scene.frame_end} | {round(1 + k * (scene.frame_end - 1) / 8) for k in range(1, 8)})
    for f in frames:
        scene.frame_set(f)
        _update()
        worst = [max(w, e) for w, e in zip(worst, flex_errors(scene))]
        now = [np.array(flex.shape_now(scene, it)) for it in items]
        if first is None:
            first = now
        moved = max(moved, max(float(np.abs(n - f0).max()) for n, f0 in zip(now, first)))
    for it in items:
        _check(not it.problem, f"'{it.name}': {it.problem}")
    return worst[0], worst[1], worst[2], moved


def _check_hoses(scene):
    end, stretch, _chord, moved = _flex_over_frames(scene, "HOSE")
    _check(moved > 0.05, f"the hoses moved only {moved * 1000:.0f} mm: they do not follow the arm")
    _check(end < 1e-4, f"a hose end is {end * 1000:.2f} mm off its fitting")
    _check(stretch < 0.005, f"a hose changed its length by {stretch * 100:.2f} %")
    return f"4 hoses, ends on their fittings to {end * 1000:.3f} mm, length kept to {stretch * 100:.2f} %"


@tour_set("chains", "Drag chains", "test_flex_chains_a.step", added="0.2.78")
def build_chains(b: Build):
    from . import flex, gcode
    sc = b.scene
    _look("PRODUCT")
    made = flex.set_up_test_chains(sc)
    _check(len(made["items"]) == 3, f"only {len(made['items'])} of the 3 drag chains were made")
    gcode.find_axes(sc)
    gcode.use_tool(sc, _ob(sc, "TOOL T1 FLAT D6"))
    gcode.use_workpiece(sc, _ob(sc, "STOCK 300x200x30"))
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: drag chains")
    a = _animation(b, CHAINS_ANIM, shot.name)
    _gcode_step(a, _program(b, "Drag chains program.ngc", CHAINS_PROGRAM), sc)


def _check_chains(scene):
    end, _stretch, chord, moved = _flex_over_frames(scene, "CHAIN")
    _check(moved > 0.05, f"the chains' links moved only {moved * 1000:.0f} mm: they do not follow the axes")
    _check(end < 1e-5, f"a chain's moving end is {end * 1000:.3f} mm off its part")
    _check(chord < 1e-5, f"a link is {chord * 1000:.3f} mm longer or shorter than its link length")
    n = sum(it.count for it in scene.fresing.flex if it.kind == "CHAIN")
    return f"3 chains, {n} links, the moving ends on their parts to {end * 1000:.3f} mm"


# ---------------------------------------------------------------------------
# a cable over sheaves, rollers and a chute (task 0078)
# ---------------------------------------------------------------------------

CABLE_ANIM = "Cable over sheaves"


@tour_set("cables", "Cable over sheaves", "test_paths_a.step", added="0.2.80")
def build_cables(b: Build):
    from . import paths
    sc = b.scene
    _look("PRODUCT")
    made = paths.set_up_test_model(sc)
    _check(len(made["contacts"]) == 6, f"only {len(made['contacts'])} of the 6 things the rope touches were found")
    _check(made["animation"] == CABLE_ANIM, f"the animation is called '{made['animation']}'")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: cable")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_cables(scene):
    """Along the built animation: the rope lies on every wheel it bends round, the drum, sheaves and rollers have
    turned exactly as far as the rope ran, and the rope follows the luffing A-frame."""
    import numpy as np

    from . import joints, paths
    its = list(paths.items(scene))
    _check(len(its) == 1, "the cable is missing")
    it = its[0]
    _check(paths.status(scene, it)[1] == "OK", f"the cable says: {paths.status(scene, it)[0]}")
    cab = joints.find(scene, it.joint)
    _check(cab is not None, "the cable's speed joint is missing")
    off = slip = moved = pay = 0.0
    first = None
    for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 15)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        pts = np.array(paths.shape_now(scene, it), dtype=float)
        for w in paths.wheels_now(scene, it):
            d = pts - np.asarray(w.centre, float)
            ax = np.asarray(w.axis, float)
            rad = np.linalg.norm(d - np.outer(d @ ax, ax), axis=1)
            off = max(off, abs(float(rad.min()) - float(w.radius)))
        pay = joints.get_value(cab)
        for c in it.contacts:
            if c.kind in paths.TURNING and c.turns and c.joint:
                j = joints.find(scene, c.joint)
                _check(j is not None, f"'{c.name}' has lost its joint")
                want = math.radians(c.ratio) * pay * 1000.0
                slip = max(slip, abs(joints.get_value(j) - want) * paths.radius_of(it, c))
        if first is None:
            first = pts
        elif pts.shape == first.shape:
            moved = max(moved, float(np.abs(pts - first).max()))
    turning = sum(1 for c in it.contacts if c.kind in paths.TURNING and c.turns and c.joint)
    _check(pay > 0.9, f"only {pay:.2f} m of rope ran: the cable speed does not move it")
    _check(off < 5e-4, f"the rope is {off * 1000:.2f} mm off a sheave")
    _check(slip < 1e-3, f"a sheave or roller is {slip * 1000:.2f} mm behind the rope")
    _check(moved > 0.05, f"the rope moved only {moved * 1000:.0f} mm: it does not follow the A-frame")
    _check(turning == 5, f"{turning} of the 5 turning parts turn")
    return (f"{len(it.contacts)} contacts, {pay:.2f} m of rope ran, the rope on its sheaves to {off * 1000:.2f} mm, "
            f"{turning} parts turning with it to {slip * 1000:.3f} mm")


SPOOL_ANIM = "Spooling"


@tour_set("spool", "Drum and carousel spooling", "test_spool.step", added="0.2.85", changed="0.2.139")
def build_spool(b: Build):
    from . import spool
    sc = b.scene
    _look("PRODUCT")
    made = spool.set_up_test_model(sc)
    _check(made["animation"] == SPOOL_ANIM, f"the animation is called '{made['animation']}'")
    spool.add_full_range_steps(sc, SPOOL_ANIM)          # task 0174: the drum filled and emptied, the carousel emptied
    for name in made["spools"]:
        sp = spool.find(sc, name)
        _check(sp is not None and not sp.problem, f"'{name}': {sp.problem if sp is not None else 'missing'}")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: spooling")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


SERVED_CABLE = "POWER CABLE"     # the test spool model's cable that gets the served look (task 0158)


def served_demo(scene) -> dict:
    """test_spool.step (imported) set up as for the spooling stop, its power cable (and the coil on the carousel) with
    the served-cable look: black yarn, pairs of yellow marker bands (task 0158). Shared by the tour, the PC check and
    the guide pictures. Returns ``spool.set_up_test_model``'s dict with "cable" = the cable item's name."""
    from . import build, paths, spool
    made = spool.set_up_test_model(scene)
    it = next(i for i in paths.items(scene) if i.part.get(build.PROP_NAME) == SERVED_CABLE)
    it.look = "SERVED"
    made["cable"] = it.name
    return made


def served_camera(scene, name: str = "Served cable"):
    """A close-up of the served cable where it leaves the carousel's coil: the coil, the bands, the yarn."""
    import numpy as np

    from . import cameras, paths
    it = paths.find(scene, served_demo_cable(scene))
    pts = np.asarray(paths.shape_now(scene, it), float)
    c = pts[len(pts) // 3]
    box = np.array([c + 0.22 * np.array((dx, dy, dz)) for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)])
    cam = cameras.add_camera(scene, "ISO", 50.0, name, points=box)
    scene.camera = cam
    return cam


def served_demo_cable(scene) -> str:
    from . import build, paths
    return next(i.name for i in paths.items(scene) if i.part.get(build.PROP_NAME) == SERVED_CABLE)


@tour_set("served", "Served cable look", "test_spool.step", added="0.2.116", changed="0.2.139")
def build_served(b: Build):
    sc = b.scene
    _look("PRODUCT")
    made = served_demo(sc)
    _check(made["animation"] == SPOOL_ANIM, f"the animation is called '{made['animation']}'")
    _update()
    served_camera(sc, "Tour served cable")
    shot = _shot(b, "Tour: served cable")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_served(scene):
    """The power cable and its coil have the served look; the bands run with the paid-out length."""
    from . import cable_looks, joints, paths, spool
    it = paths.find(scene, served_demo_cable(scene))
    _check(it is not None and it.look == "SERVED", "the cable has not got the served look")
    part = it.part
    _check(all(k in part for k in cable_looks.PROPS), "the cable's part lacks the served look's settings")
    mat = part.material_slots[0].material if part.material_slots else None
    _check(mat is not None and cable_looks.NODE_YARN in cable_looks.nodes_of(mat), "the material draws no yarn")
    sp = spool.of_cable(scene, it)
    coil = spool._made(scene, sp, "rope") if sp is not None else None
    _check(coil is not None and list(coil.get(cable_looks.YARN, [])) == list(part[cable_looks.YARN]),
           "the coil on the carousel has not got the served look")
    cab = joints.find(scene, it.joint)
    ran = []
    for f in (scene.frame_start, scene.frame_end):
        scene.frame_set(f)
        _update()
        ran.append((joints.get_value(cab), float(part[cable_looks.PAY]) - cable_looks.PAY_BIAS))
    sign = -1.0 if it.reverse else 1.0
    moved = ran[1][1] - ran[0][1]
    _check(abs(moved - sign * (ran[1][0] - ran[0][0])) < 1e-3 and abs(moved) > 0.5,
           f"the bands moved {moved:.3f} m while the cable ran {ran[1][0] - ran[0][0]:.3f} m")
    n = int(round(part[cable_looks.YARN][1]))
    return f"served look on the cable and its coil, {abs(n)} yarn strands round it, the bands ran {abs(moved):.2f} m"


SEA_ANIM = "Cable into the sea"


@tour_set("sea_cable", "Cable into the sea", "test_sea.step", added="0.2.91", changed="0.2.141")
def build_sea(b: Build):
    from . import paths, paths_sea
    sc = b.scene
    s = sc.fresing
    _look("PRODUCT")
    s.background, s.env_detail, s.sea_state = "SEA", "SIMPLE", "CALM"
    s.water_level = 2.0                     # the hull's draft: the waterline is the model's z = 0
    s.sea_depth, s.sea_clarity = 15.0, 15.0
    _update()
    made = paths_sea.set_up_test_model(sc)
    _check(made["animation"] == SEA_ANIM, f"the animation is called '{made['animation']}'")
    it = paths.find(sc, made["cable"])
    _check(it is not None and it.b_kind == "SEA" and not it.problem,
           f"the cable into the sea: {it.problem if it is not None else 'missing'}")
    s.sea_cut_auto = True
    s.sea_cutaway = True
    _update()
    add_lay_label(sc, paths.find(sc, made["cable"]))       # task 0173: the cable's live numbers in a label
    cam = _camera(b, "ISO", "Tour view", lens=30.0)
    cam.matrix_world = paths_sea.view_matrix(sc, paths.find(sc, made["cable"]))
    shot = _shot(b, "Tour: into the sea")
    a = s.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


LAY_LABEL = "Lay data\\nTop tension {top} kN\\nLayback {layback} m\\nSpeed {speed} m/min"


def add_lay_label(scene, item):
    """Task 0173: a label of several lines on the cable into the sea, pointing at its touch-down, showing its live
    numbers (the test tour's set and the PC check's line share it)."""
    from . import callouts, paths_sea
    got = paths_sea.tdp_world(scene, item)
    _check(got is not None, "the cable into the sea has no touch-down")
    c = callouts.add(scene, item.part, got[1], LAY_LABEL)
    scene.fresing.callouts_on = True
    return c


def _check_lay_label(scene, it, n) -> None:
    """The lay data label shows the cable's numbers at the frame shown (task 0173)."""
    from . import callouts
    from ..core import callouts as C
    labels = [c for c in scene.fresing.callouts if c.part == it.part and C.fields_in(c.text)]
    _check(len(labels) == 1, f"{len(labels)} labels with the cable's numbers (1 expected)")
    rows = callouts.label_text(scene, labels[0]).split("\n")
    _check(len(rows) == 4 and rows[1] == f"Top tension {n['top']:.1f} kN" and rows[2] == f"Layback {n['layback']:.1f} m",
           f"the lay data label reads {rows}, the cable {n['top']:.1f} kN, {n['layback']:.1f} m")


def _check_sea_cable(scene):
    """Along the built animation: the cable keeps its length from the horn to its end on the seabed, the touch-down
    stays the layback behind the horn (the vessel moves with the lay), its end lies still on the seabed (it moves
    aft with the seabed) and the CPS set goes down the catenary on the cable."""
    import numpy as np

    from . import build, paths, paths_riders, paths_sea
    its = [it for it in paths.items(scene) if it.b_kind == "SEA"]
    _check(len(its) == 1, "the cable into the sea is missing")
    it = its[0]
    _check(paths.status(scene, it)[1] == "OK", f"the cable says: {paths.status(scene, it)[0]}")
    lays, ends, low = [], [], 1e9
    for f in (scene.frame_start, (scene.frame_start + scene.frame_end) // 2, scene.frame_end):
        scene.frame_set(f)
        _update()
        n = paths_sea.numbers(scene, it)
        lays.append(n["layback"])
        _check_lay_label(scene, it, n)
        line = np.array(paths.shape_now(scene, it), dtype=float)
        bed = np.array(paths_sea.bed(scene).matrix_world)
        ends.append(np.linalg.inv(bed)[:3, :3] @ line[-1] + np.linalg.inv(bed)[:3, 3])
        rings = [p.part for r in it.riders for p in r.parts if p.part.get(build.PROP_NAME) == "VERTEBRA"]
        dg = __import__("bpy").context.evaluated_depsgraph_get()
        for ring in rings:
            ev = ring.evaluated_get(dg)
            low = min(low, float((np.array(ev.matrix_world) @ np.r_[np.array(ev.data.vertices[0].co), 1.0])[2]))
    pay = paths_sea.payout(scene, it)
    drift = float(max(np.linalg.norm(e - ends[0]) for e in ends))
    _check(pay > 7.0, f"only {pay:.2f} m of cable ran")
    _check(max(lays) - min(lays) < 0.01, f"the layback changed from {min(lays):.2f} to {max(lays):.2f} m")
    _check(drift < 1e-3, f"the cable's end on the seabed moved {drift * 1000:.1f} mm over the seabed")
    _check(low < -1.0, "the CPS set did not go down into the sea")
    _check(len(paths_riders.rider_parts(scene)) == 9, "the CPS set's 9 parts do not all ride on the cable")
    return (f"{pay:.2f} m paid out, layback {lays[0]:.2f} m held to {(max(lays) - min(lays)) * 1000:.1f} mm, the end "
            f"on the seabed still to {drift * 1000:.2f} mm, the CPS set {-low:.1f} m under the water")


VESSEL_ANIM = "Vessel at work"


@tour_set("vessel_work", "Vessel at work", "test_thrusters.step", added="0.2.127")
def build_vessel_work(b: Build):
    """Task 0154: a workboat with two azimuths and a bow thruster sails ahead at 8 knots, then pushes sideways."""
    from mathutils import Matrix, Vector

    from . import vessel_work
    sc = b.scene
    _look("PRODUCT")
    vessel_work.set_up_test_model(sc)
    _update()
    cam = _camera(b, "ISO", "Tour view", lens=28.0)
    at, look = Vector((-45.0, -50.0, 40.0)), Vector((5.0, 0.0, -3.0))
    cam.matrix_world = Matrix.Translation(at) @ (look - at).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    cam.data.clip_end = 5000.0
    shot = _shot(b, "Tour: vessel at work")
    a = _animation(b, VESSEL_ANIM, shot.name)
    blk = a.blocks.add()
    blk.kind, blk.start, blk.duration, blk.easing = "VESSEL", 3.0, 3.0, "SMOOTH"
    blk.vw_mode, blk.vw_side, blk.vw_thrust = "DP", "STBD", 0.7
    blk = a.blocks.add()                                  # (a still moment at the end)
    blk.kind, blk.start, blk.duration, blk.easing = "VESSEL", 8.0, 2.0, "SMOOTH"
    blk.vw_mode, blk.vw_side, blk.vw_thrust = "DP", "STBD", 0.7


def _check_vessel_work(scene):
    """Along the built animation: the wake's speed channel goes from 8 knots to 0, the bow thruster's load up, the
    azimuths steer from 0 to -90° and every propeller turns."""
    import math

    from ..core import vessel_work as vw_core
    from . import joints, vessel_work
    rows = list(scene.fresing.vessel_work.thrusters)
    _check([r.kind for r in rows] == ["AZIMUTH", "AZIMUTH", "TUNNEL"], "the three thrusters were not found")
    out = []
    for f in (scene.frame_start + 25, scene.frame_end):
        scene.frame_set(f)
        _update()
        out.append((float(scene.get(vw_core.prop("ahead"), -1)), float(scene.get(vw_core.prop("t2"), -1)),
                    joints.get_value(joints.find(scene, rows[0].steer)),
                    [joints.get_value(joints.find(scene, r.joint)) for r in rows]))
    (v0, t0, s0, p0), (v1, t1, s1, p1) = out
    _check(abs(v0 - 8.0) < 1e-3 and v1 == 0.0, f"the speed went from {v0:.1f} to {v1:.1f} knots, not 8 to 0")
    _check(t0 == 0.0 and abs(t1 - 0.7) < 1e-3, f"the bow thruster's load went from {t0:.2f} to {t1:.2f}, not 0 to 0.7")
    _check(abs(s0) < 1e-4 and abs(s1 + math.pi / 2) < 1e-3, f"the azimuth steered from {math.degrees(s0):.0f}° to "
           f"{math.degrees(s1):.0f}°, not 0 to -90°")
    _check(all(abs(b - a) > 1.0 for a, b in zip(p0, p1)), "a propeller did not turn")
    _check(vessel_work.stored_layout(scene) is not None, "the sea was built without the vessel's water")
    return "8 kn to 0, bow thruster to 70 %, azimuths steered to -90°, 3 propellers turning"


MOVING_ANIM = "Over the stern"


@tour_set("moving_cable", "A cable on a moving part", "test_moving.step", added="0.2.95", changed="0.2.103")
def build_moving(b: Build):
    from . import paths
    sc = b.scene
    s = sc.fresing
    _look("PRODUCT")
    s.background, s.env_detail, s.sea_state = "SEA", "SIMPLE", "CALM"
    s.water_level = 2.0                     # the hull's draft: the waterline is the model's z = 0
    s.sea_depth, s.sea_clarity = 15.0, 15.0
    _update()
    made = paths.set_up_moving_model(sc)
    _check(made["animation"] == MOVING_ANIM, f"the animation is called '{made['animation']}'")
    for name in (made["cable"], made["wire"]):
        it = paths.find(sc, name)
        _check(it is not None and not it.problem, f"'{name}': {it.problem if it is not None else 'missing'}")
    s.sea_cut_auto = True
    s.sea_cutaway = True
    _update()
    _camera(b, "ISO", "Tour view", lens=30.0, points=paths.moving_view_points(sc))
    shot = _shot(b, "Tour: over the stern")
    a = s.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_moving_cable(scene):
    """Along the built animation: the lift wire's winch keeps it tight (its free length as drawn to 0.5 mm, what it
    pays out turns the head sheave), the cable end leaves the horn and hangs from the sheave once that has gone over
    the stern, and after the let-go frame its start stays behind while the block goes on and settles onto the seabed
    (task 0125: it only goes down, and lies on the seabed at the end); its length (start to its end on the seabed) is
    kept throughout."""
    import numpy as np

    from . import build, paths, paths_sea
    it, w = paths.find(scene, paths.MOVING_CABLE), paths.find(scene, paths.MOVING_WIRE)
    _check(it is not None and w is not None, "the cable end or the lift wire is missing")
    for x in (it, w):
        _check(paths.status(scene, x)[1] == "OK", f"'{x.name}' says: {paths.status(scene, x)[0]}")
    free0 = paths.free_length(scene, w, cad=True)
    f0 = int(round(paths.MOVING_LET_GO * 25)) + 1
    tight, totals, hangs, starts, sheaves = 0.0, [], [], [], []
    sheave = next(o for o in scene.objects if o.get(build.PROP_NAME) == "SHEAVE")
    for f in (scene.frame_start, f0 - 60, f0, (f0 + scene.frame_end) // 2, scene.frame_end):
        scene.frame_set(f)
        _update()
        it, w = paths.find(scene, paths.MOVING_CABLE), paths.find(scene, paths.MOVING_WIRE)
        tight = max(tight, abs(paths.free_length(scene, w) - paths.tight_payout(scene, w) - free0))
        totals.append(float(paths.lengths_now(scene, it)[-1]))
        hangs.append(paths_sea.numbers(scene, it).get("hang_off", ""))
        if f >= f0:
            inv = np.linalg.inv(np.array(paths_sea.bed(scene).matrix_world))
            line = np.array(paths.shape_now(scene, it), dtype=float)
            starts.append(inv[:3, :3] @ line[0] + inv[:3, 3])
            sheaves.append(inv[:3, :3] @ np.array(sheave.matrix_world)[:3, 3] + inv[:3, 3])
    pay = paths.tight_payout(scene, w)
    zs = [float(p[2]) for p in starts]
    bottom = paths_sea.bottom_z(scene, it)
    sank = all(b <= a + 1e-6 for a, b in zip(zs, zs[1:]))
    drift = abs(zs[-1] - bottom)
    went = float(max(np.linalg.norm(p - sheaves[0]) for p in sheaves))
    _check(tight < paths.TIGHT_TOL, f"the lift wire's free length changed by {tight * 1000:.1f} mm")
    _check(pay > 10.0, f"the winch paid out only {pay:.2f} m")
    _check(hangs[0] == "HORN" and hangs[-1] == "SHEAVE", f"the cable hangs from {hangs[0]} and then {hangs[-1]}")
    _check(max(totals) - min(totals) < 1e-3,
           f"the cable's length changed by {(max(totals) - min(totals)) * 1000:.1f} mm")
    _check(sank and drift < 0.01, f"the let-go start did not settle onto the seabed: {zs[-1] - bottom:.3f} m over it")
    _check(went > 3.0, "the block did not go on after the let-go")
    return (f"the winch paid out {pay:.2f} m with the wire tight to {tight * 1000:.2f} mm; the cable left the horn "
            f"for the sheave, kept its length to {(max(totals) - min(totals)) * 1000:.2f} mm and its let-go start "
            f"settled {zs[0] - zs[-1]:.2f} m onto the seabed (to {drift * 1000:.1f} mm) while the block went "
            f"{went:.1f} m on")


SWIVEL_ANIM = "Davit slews"


@tour_set("swivel", "A sheave on a swivel", "test_swivel.step", added="0.2.138")
def build_swivel(b: Build):
    from . import paths, paths_swivel
    sc = b.scene
    _look("PRODUCT")
    made = paths_swivel.set_up_test_model(sc)
    _check(made["animation"] == SWIVEL_ANIM, f"the animation is called '{made['animation']}'")
    it = paths.find(sc, made["cable"])
    _check(it is not None and not it.problem, f"'{made['cable']}': {it.problem if it is not None else 'missing'}")
    _update()
    _camera(b, "ISO", "Tour view", lens=35.0)
    shot = _shot(b, "Tour: swivel")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_swivel(scene):
    """Along the built animation (task 0172): the davit slews ±45° and the swivel head turns with the wire – the wire
    from the fairlead comes into the sheave in the sheave's plane (within 1°) at every 5th frame – over a range of
    more than 30°, the wire kept tight and with no warning."""
    import numpy as np

    from . import joints, paths, paths_swivel
    it = paths.find(scene, paths_swivel.TEST_CABLE)
    _check(it is not None, "the davit wire is missing")
    _check(paths.status(scene, it)[1] == "OK", f"the wire says: {paths.status(scene, it)[0]}")
    sw = joints.find(scene, paths_swivel.TEST_SWIVEL)
    _check(sw is not None, "the swivel joint is missing")
    worst, turns = 0.0, []
    for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 5)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        it = paths.find(scene, paths_swivel.TEST_CABLE)
        pts = np.array(paths.shape_now(scene, it), dtype=float)
        run = pts[1] - pts[0]
        run /= max(float(np.linalg.norm(run)), 1e-12)
        axis = np.asarray(paths.wheels_now(scene, it)[0].axis, dtype=float)
        worst = max(worst, math.degrees(math.asin(min(1.0, abs(float(run @ axis))))))
        turns.append(math.degrees(joints.get_value(sw)))
    span = max(turns) - min(turns)
    _check(worst < 1.0, f"the wire comes into the sheave {worst:.2f}° out of its plane")
    _check(span > 30.0, f"the swivel turned only {span:.1f}°")
    return f"the swivel turned {span:.1f}° with the wire, the wire in the sheave's plane to {worst:.3f}°"


TRACKS_ANIM = "Tracks"


@tour_set("tracks", "Tensioner tracks and a belt", "test_tracks.step", added="0.2.87", changed="0.2.101")
def build_tracks(b: Build):
    from . import tracks
    sc = b.scene
    _look("PRODUCT")
    made = tracks.set_up_test_model(sc)
    _check(made["animation"] == TRACKS_ANIM, f"the animation is called '{made['animation']}'")
    for it in tracks.items(sc):
        text, level = tracks.status(sc, it)
        _check(level == "OK", f"'{it.name}': {text}")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: tracks")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_tracks(scene):
    """Along the built animation: every link's two hinges on its loop one pitch apart, the tensioner's gripping pads
    ran as far as the cable, the sprockets turned one tooth per link, the top track lifted and came back."""
    import numpy as np

    from . import joints, paths, tracks
    its = [tracks.find(scene, n) for n in tracks.TEST_TRACKS]
    _check(all(it is not None for it in its), "a track is missing")
    cab = joints.find(scene, paths.find(scene, tracks.TEST_CABLE).joint)
    lift = joints.find(scene, tracks.TEST_LIFT)
    off = chord = 0.0
    lifts = []
    for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 25)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        lifts.append(joints.get_value(lift))
        for it in its:
            for ob in [o for o in tracks.parts_of(scene, it) if o.get(tracks.ROLE) == "link"][::5]:
                a, b = tracks.hinge_world(scene, it, ob)
                chord = max(chord, abs(float(np.linalg.norm(b - a)) - it.pitch))
                off = max(off, float(tracks.off_loop(scene, it, [a, b]).max()))
    ran = joints.get_value(cab)
    bot = its[0]
    run = tracks.travel_now(scene, bot)
    run = min(run, bot.length - run)
    want = ran % bot.length
    want = min(want, bot.length - want)
    spr = joints.find(scene, bot.wheels[0].joint)
    turn = abs(joints.get_value(spr))
    _check(ran > 1.9, f"only {ran:.2f} m of cable ran")
    _check(abs(run - want) < 1e-4, f"the pads ran {run:.4f} m, the cable {want:.4f} m (round the loop)")
    _check(abs(turn - abs(bot.wheels[0].rate) * ran) < 1e-4, "a sprocket does not turn one tooth per link")
    _check(off < 1e-4, f"a link's hinge is {off * 1000:.2f} mm off its loop")
    _check(chord < 5e-5, f"a link's hinges are {chord * 1000:.3f} mm from one pitch apart")
    _check(max(lifts) > 0.14 and abs(lifts[-1] + 0.002) < 1e-4, "the top track did not lift and squeeze")
    return (f"{ran:.2f} m of cable, the pads with it to {abs(run - want) * 1000:.2f} mm, sprocket "
            f"{math.degrees(turn):.0f}°; hinges on their loops to {off * 1000:.3f} mm, one "
            f"pitch apart to {chord * 1000:.3f} mm; top track lifted {max(lifts) * 1000:.0f} mm")


def _check_spool(scene):
    """Along the built animation: the drum turned and the level wind went along with the wrap being paid out, the
    carousel turned and its arm swung out; each cable leaves its spool on the circle of its layer."""
    import numpy as np

    from ..core import spool as S
    from . import joints, spool
    sps = [spool.find(scene, n) for n in ("Drum", "Carousel")]
    _check(all(sp is not None for sp in sps), "a drum or carousel is missing")
    seen = {sp.name: [] for sp in sps}
    off = 0.0
    for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 25)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        for sp in sps:
            from . import paths
            path = spool.path_of(scene, sp)
            p = spool.payout(scene, sp)
            start = np.asarray(paths.shape_now(scene, paths.find(scene, sp.cable))[0], dtype=float)
            loc = np.linalg.inv(spool.frame_cad(scene, sp, {})) @ np.r_[start, 1.0]
            _phi, _a, r, _k = S.at(path, np.array([sp.wound - p]))
            off = max(off, abs(math.hypot(loc[0], loc[1]) - float(r[0])))
            seen[sp.name].append([p, joints.get_value(joints.find(scene, sp.joint))] +
                                 [joints.get_value(joints.find(scene, fl.joint)) for fl in sp.followers])
    drum, car = np.array(seen["Drum"]), np.array(seen["Carousel"])
    six = int(np.argmin(np.abs(np.array([f for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 25))
                                                            | {scene.frame_end})]) - (scene.frame_start + 200))))
    _check(drum[six, 0] > 5.9 and car[six, 0] > 5.9, "the cables did not pay out 6 m")
    _check(abs(drum[six, 1]) > 30.0, f"the drum turned only {math.degrees(abs(drum[six, 1])):.0f}°")
    _check(np.ptp(drum[:six + 1, 2]) > 0.1, "the level wind did not go along the drum")
    _check(abs(car[six, 1]) > 6.0, f"the carousel turned only {math.degrees(abs(car[six, 1])):.0f}°")
    _check(np.ptp(car[:six + 1, 2]) > 0.05, "the arm did not swing out with the layer")
    _check(off < 5e-4, f"a cable leaves its spool {off * 1000:.2f} mm off the circle of its layer")
    full = _check_full_spools(scene, sps)
    return (f"drum {math.degrees(abs(drum[six, 1])) / 360.0:.1f} turns, level wind {np.ptp(drum[:, 2]) * 1000:.0f} mm, "
            f"carousel {math.degrees(abs(car[six, 1])):.0f}°, arm {math.degrees(np.ptp(car[:, 2])):.1f}°; "
            f"leave points on their layer to {off * 1000:.2f} mm; {full}")


def _check_full_spools(scene, sps) -> str:
    """Task 0174: every layer is cable – at frames through the fill and the emptying (``spool.add_full_range_steps``)
    the full layers shown are the right ones and, with the moving rope, one cable from the anchor to the leave point
    (no gap of more than 1 mm); the drum full shows every layer, both empty show none."""
    import numpy as np

    from ..core import spool as S
    from . import spool
    worst, most = 0.0, {sp.name: 0 for sp in sps}
    fewest = {sp.name: 10**9 for sp in sps}
    for f in sorted(set(range(scene.frame_start + 200, scene.frame_end + 1, 10)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        for sp in sps:
            path = spool.path_of(scene, sp)
            p = spool.payout(scene, sp)
            want = S.shown_layers(path, float(sp.wound), np.array([p]))[0]
            layers = spool.layer_objects(scene, sp)
            got = np.array([not ob.hide_viewport for ob in layers], bool)
            _check(len(layers) == path.layer_count - 1 and np.array_equal(want, got),
                   f"'{sp.name}' at frame {f}: layers shown {got.astype(int).tolist()}, wanted "
                   f"{want.astype(int).tolist()}")
            on = min(max(float(sp.wound) - p, 0.0), float(path.total))
            spans = [(float(lo), float(hi)) for (lo, hi), shown in zip(S.layer_spans(path)[:-1], got) if shown]
            spans.append((float(S.drawn_from(path, float(sp.wound), np.array([p]))[0]), on))
            reach = 0.0
            for lo, hi in sorted(spans):
                worst = max(worst, lo - reach)
                reach = max(reach, hi)
            if on > 1e-3:
                worst = max(worst, abs(reach - on))
            most[sp.name] = max(most[sp.name], int(got.sum()))
            fewest[sp.name] = min(fewest[sp.name], int(got.sum()))
    drum = next(sp for sp in sps if sp.name == "Drum")
    n_drum = spool.path_of(scene, drum).layer_count - 1
    _check(worst < 1e-3, f"the drawn cable has a gap of {worst * 1000:.1f} mm")
    _check(most["Drum"] == n_drum and fewest["Drum"] == 0, f"the drum showed {fewest['Drum']} … {most['Drum']} of "
           f"its {n_drum} full layers (wanted all when full, none when empty)")
    _check(fewest["Carousel"] == 0, "the carousel was not emptied")
    return (f"drum filled ({n_drum + 1} layers) and emptied, carousel emptied and filled ({most['Carousel']} full "
            f"layers), one cable to {worst * 1000:.2f} mm")


@tour_set("copies", "Two copies", "test_crane_a.step", "test_crane_a.step", added="0.2.47", changed="0.2.101")
def build_copies(b: Build):
    from mathutils import Vector

    from . import build, logic, states
    sc = b.scene
    _look("PRODUCT")
    first, second = sorted(build.model_roots(sc), key=build.uid_scope)
    second.location = second.location + Vector((0.0, 2.2, 0.0))
    _update()
    cover = next(o for o in sc.objects if o.get(build.PROP_NAME) == "COVER" and build.model_root_of(o) == second)
    logic.set_hidden(cover, True)
    states.save_visibility(sc, "Second crane without cover")
    _camera(b, "ISO", "Tour view")
    _shot(b, "@copies")


def _check_copies(scene):
    from . import build, logic
    roots = sorted(build.model_roots(scene), key=build.uid_scope)
    _check(len(roots) == 2 and build.uid_scope(roots[1]) != "", "the two cranes share their part IDs")

    def cover(root):
        return next(o for o in scene.objects if o.get(build.PROP_NAME) == "COVER" and build.model_root_of(o) == root)

    _check(logic.is_hidden(cover(roots[1])) and not logic.is_hidden(cover(roots[0])),
           "hiding the second crane's cover touched the first crane")
    return "two cranes kept apart"


@tour_set("update", "Model update", "test_crane_a.step", added="0.2.47", changed="0.2.101")
def build_update(b: Build):
    import bpy

    from . import build, joints, logic, states
    sc, s = b.scene, b.s
    _look("PRODUCT")
    j = _boom_joint(sc)
    joints.set_value(j, math.radians(20))
    logic.set_hidden(_ob(sc, "COVER"), True)
    states.save_pose(sc, "Work")
    _update()
    root = build.model_roots(sc)[0]
    res = bpy.ops.fresing.import_step(filepath=os.path.join(DATA, "test_crane_b.step"), quality="draft",
                                      update_root=root.name)
    _check(res == {"FINISHED"}, f"the model update returned {res}: {s.last_message}")
    _update()
    _camera(b, "ISO", "Tour view")
    _shot(b, "@update")


def _check_update(scene):
    from . import joints, logic
    s = scene.fresing
    j = joints.find(scene, "Boom")
    _check(j is not None and joints.is_valid(j), "the joint was lost")
    _check(abs(math.degrees(joints.get_value(j)) - 20) < 1e-3, "the joint lost its value")
    _check(logic.is_hidden(_ob(scene, "COVER")), "the hidden cover is shown again")
    _ob(scene, "BOOM.LAMP")
    del s
    return "joint, pose and hidden cover kept; new: BOOM.LAMP"


ACCEL_ANIM = "Acceleration"


def _accel_program() -> str:
    """Task 0103: 2 mm zigzag steps above the block (G64), the same back with exact stops (G61), then one long line."""
    out = ["(T1 D=6. CR=0. - flat end mill)", "G21 G90 G94 G17 G64", "G0 X-30 Y-10 Z3", "G1 F3000"]
    x = -30
    for k in range(24):
        if k % 2 == 0:
            x += 2
            out.append(f"X{x}")
        else:
            out.append(f"Y{-8 if (k // 2) % 2 == 0 else -10}")
    out.append("G61")
    for k in range(24):
        if k % 2 == 0:
            x -= 2
            out.append(f"X{x}")
        else:
            out.append(f"Y{-8 if (k // 2) % 2 == 0 else -10}")
    out += ["G64", "G1 X30 Y10", "G0 Z10", "M30"]
    return "\n".join(out) + "\n"


ACCEL_TOUR = _accel_program()

GCODE_TOUR = """(T1 D=6. CR=0. - flat end mill)
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


# ----- clash check (task 0065) -----

CLASH_ARMS = (("Arm B", "ARM.B.ASM", (1.0, 0.0, 0.0), 90.0), ("Arm A", "ARM.A.ASM", (0.0, 0.044, 0.0), -90.0))
CLASH_DEPTH = 6.0                # mm: arm A's underside goes this far into arm B (tools/make_test_clash.py)


def clash_arms(scene, a, seconds: float = 1.0) -> None:
    """The clash test model: a joint on each arm's pin; arm B turns into place, then arm A turns down onto it until
    A's underside is 6.0 mm inside B (also used by the PC check and the tests)."""
    from mathutils import Vector

    from . import joints
    for k, (name, asm, pivot, deg) in enumerate(CLASH_ARMS):
        if joints.find(scene, name) is None:
            joints.create(scene, "ROTATE", [_ob(scene, asm)], Vector(pivot), Vector((0, 0, 1)), name=name)
        _joint_step(a, name, k * seconds, seconds, math.radians(deg))


@tour_set("clash", "Clash check", "test_clash.step", added="0.2.53")
def build_clash(b: Build):
    sc = b.scene
    _look("PRODUCT")
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: clash check")
    clash_arms(sc, _animation(b, "Arms meet", shot.name))


def _clash_setup(scene):
    """Go: check the built animation and show its clash (as clicking Check for clashes, then the row)."""
    from . import clash
    clash.check(scene)
    c = clash.settings(scene)
    if len(c.rows):
        c.rows_index = 0                      # what a click on the row does: frame, selection, red


def _check_clash(scene):
    from . import clash
    c = clash.settings(scene)
    if not c.checked:
        clash.check(scene)
    rows = [r for r in c.rows if r.kind == "CLASH"]
    _check(len(rows) == 1, f"{len(rows)} clashes found, not 1: " + "; ".join(f"{r.label_a} × {r.label_b}"
                                                                           for r in rows[:3]))
    r = rows[0]
    _check({r.label_a, r.label_b} == {"ARM.A", "ARM.B"}, f"the clash is {r.label_a} × {r.label_b}, not the arms")
    _check(abs(r.depth * 1000 - CLASH_DEPTH) < 0.2, f"the arms are {r.depth * 1000:.2f} mm deep, not 6.0 mm")
    _check(r.frame_to == scene.frame_end, f"the clash ends at frame {r.frame_to}, not at the end")
    return f"ARM.A × ARM.B, frames {r.frame_from}–{r.frame_to}, {r.depth * 1000:.1f} mm"


SEQUENCE_ANIM = "Take apart and put together"
SEQUENCE_UNIT = "SPINDLE.UNIT"            # tools/make_test_sequence.py: 12 parts, 5 fasteners
TALL = 1.0                                # m: the top of the column the parts make when taken apart


def sequence_steps(scene, a) -> tuple:
    """The spindle unit is taken apart along its own +Z axis (fasteners first, trail lines), then put together
    again straight down. Returns the two steps."""
    from . import build, sequence
    u = _ob(scene, SEQUENCE_UNIT)
    out = []
    for mode in ("APART", "TOGETHER"):
        blk = a.blocks.add()
        blk.kind, blk.seq_mode, blk.seq_id = "SEQUENCE", mode, f"tour{mode.lower()}"
        blk.target_uid, blk.target_name = u[build.PROP_UID], u[build.PROP_NAME]
        blk.seq_direction, blk.seq_axis, blk.seq_order = "AXIS", "Z", "OUTSIDE_IN"
        blk.seq_part_time, blk.seq_overlap, blk.seq_trails = 0.6, 50.0, mode == "APART"
        sequence.count(scene, blk)
        blk.start = out[0].start + out[0].duration + 0.5 if out else 0.0
        out.append(blk)
    return tuple(out)


def check_sequence(scene, a=None) -> str:
    """Take apart: every part out, fasteners first, the order staggered; put together: every part back within
    0.01 mm of where it started. Leaves the frame where it was."""
    from . import animation, build, sequence
    a = a or next((x for x in scene.fresing.animations if x.name == SEQUENCE_ANIM), None)
    _check(a is not None, f"no animation '{SEQUENCE_ANIM}'")
    if scene.fresing.anim_baked != a.name:
        animation.bake(scene, a)
    apart, together = [b for b in a.blocks if b.kind == "SEQUENCE"][:2]
    parts = sequence.movers(scene, _ob(scene, SEQUENCE_UNIT)).parts
    _check(len(parts) == 12, f"{len(parts)} parts move, not 12")
    keep = scene.frame_current
    try:
        def at(f):
            scene.frame_set(f)
            return {o.name: o.matrix_world.copy() for o in parts}
        home = at(1)
        out = at(animation.frame_of(a, apart.start + apart.duration))
        end = at(scene.frame_end)
    finally:
        scene.frame_set(keep)
    least = min((out[n].translation - home[n].translation).length for n in home)
    _check(least > 0.05, f"a part moved only {least * 1000:.0f} mm when taken apart")
    worst = max(max(abs(x) for r in (end[n] - home[n]) for x in r) for n in home)
    _check(worst < 1e-5, f"put together, a part is {worst * 1000:.3f} mm from its place")
    starts = sorted(parts, key=lambda o: animation._channelbag(o, "OBJECT").fcurves.find("location", index=2)
                    .keyframe_points[1].co[0])
    names = [o.get(build.PROP_NAME, o.name) for o in starts[:5]]
    _check(all(sequence.fasteners.parse(n) for n in names), f"not the fasteners first: {', '.join(names)}")
    trails = [t for t in scene.fresing.trails if t.seq_owner == apart.seq_id]
    _check(len(trails) == 12, f"{len(trails)} trail lines, not 12")
    return f"12 parts out (least {least * 1000:.0f} mm), 5 fasteners first, back within {worst * 1000:.4f} mm"


@tour_set("sequence", "Assembly sequence", "test_sequence.step", added="0.2.79", changed="0.2.101")
def build_sequence(b: Build):
    sc = b.scene
    _look("PRODUCT")
    _camera(b, "ISO", "Tour view", points=_tall_view_points(sc))
    shot = _shot(b, "Tour: assembly sequence")
    a = _animation(b, SEQUENCE_ANIM, shot.name)
    sequence_steps(sc, a)


PRODUCT_ANIM = "Product video"


def check_product_video(scene) -> str:
    """The one-click product video (task 0101): its steps are in order (turn round, a joint there and back, the
    take-apart and put-together) and Build gives no warning."""
    from . import animation, product_video
    a = product_video.find_animation(scene)
    _check(a is not None, "no 'Product video' animation")
    if scene.fresing.anim_baked != a.name:
        res = animation.bake(scene, a)
        _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    kinds = [b.kind for b in a.blocks]
    _check(kinds[0] == "CAMERA" and a.blocks[0].camera_mode == "ORBIT", "it does not start with the turn round")
    _check(kinds.count("JOINT") == 2 and kinds.count("SEQUENCE") == 2, f"steps are {kinds}")
    _check(kinds.index("JOINT") < kinds.index("SEQUENCE"), "the take-apart comes before the motion")
    close = [b for b in a.blocks if b.kind == "CAMERA" and b.name.startswith("Close-up")]   # task 0129: picked
    _check(close and all(b.camera is not None for b in close), "no close-up the app picked")
    return f"{len(a.blocks)} steps, {len(close)} close-up, {animation.length_seconds(a):.0f} s without the cards"


@tour_set("productvideo", "Product video", "test_sequence.step", added="0.2.81", changed="0.2.102")
def build_productvideo(b: Build):
    from mathutils import Vector

    from . import build as bld, joints, product_video
    sc = b.scene
    _look("PRODUCT")
    u = _ob(sc, SEQUENCE_UNIT)
    j = joints.create(sc, "ROTATE", [u], Vector((0.3, 0.0, 0.0)), Vector((0, 0, 1)), name="Turn unit")
    j.use_limits, j.rot_min, j.rot_max = True, -0.6, 0.6
    del bld
    sc.fresing.pv_seconds = "30"
    info = product_video.make(sc)
    a = info["animation"]
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


FRAME_ANIM = "Round the frame"
BACK_ANIM = "Back to CAD"
FRAME_UNIT = "SLIDE.UNIT"               # tools/make_test_sequence.py --frame: 7 parts under a portal frame
FRAME_UNDER = ("RAIL BLOCK", "COVER", "CARRIAGE", "GRIPPER BLOCK", "SPLIT PIN")   # under its beam


def frame_rig(scene):
    """The frame model's two joints (task 0129): the carriage slides along X on the rail block, the gripper block
    lifts on the carriage – both ride on a part of the unit."""
    from mathutils import Vector

    from . import joints
    s = scene.fresing
    if "Carriage" in s.joints and "Gripper lift" in s.joints:
        return s.joints["Carriage"], s.joints["Gripper lift"]
    rail, car, blk = _ob(scene, "RAIL BLOCK"), _ob(scene, "CARRIAGE"), _ob(scene, "GRIPPER BLOCK")
    slide = joints.create(scene, "SLIDE", [car], Vector((0, 0, 0.04)), Vector((1, 0, 0)), name="Carriage", base=rail)
    slide.use_limits, slide.slide_min, slide.slide_max = True, -0.05, 0.06
    lift = joints.create(scene, "SLIDE", [blk], Vector((0, 0, 0.08)), Vector((0, 0, 1)), name="Gripper lift",
                         base=car)
    lift.use_limits, lift.slide_min, lift.slide_max = True, 0.0, 0.02
    return slide, lift


def frame_steps(scene, a) -> tuple:
    """The carriage slides 50 mm and the gripper lifts 10 mm; then the unit comes apart straight up – the parts under
    the frame's beam go sideways –, holds, and comes together again. Returns the two sequence steps."""
    from . import build, sequence
    slide, lift = frame_rig(scene)
    _joint_step(a, slide.name, 0.0, 1.0, 0.05, slide=True)
    _joint_step(a, lift.name, 0.0, 1.0, 0.01, slide=True)
    u = _ob(scene, FRAME_UNIT)
    out = []
    for mode in ("APART", "TOGETHER"):
        blk = a.blocks.add()
        blk.kind, blk.seq_mode, blk.seq_id = "SEQUENCE", mode, f"tourframe{mode.lower()}"
        blk.target_uid, blk.target_name = u[build.PROP_UID], u[build.PROP_NAME]
        blk.seq_direction, blk.seq_order = "UP", "OUTSIDE_IN"
        blk.seq_part_time, blk.seq_overlap = 0.6, 50.0
        sequence.count(scene, blk)
        blk.start = out[0].start + out[0].duration + 0.5 if out else 1.2
        out.append(blk)
    return tuple(out)


def check_frame(scene) -> str:
    """Parts under the beam leave sideways, the bolts up; the gripper block (a rider) leaves before the carriage and
    stays where it flew while the carriage leaves; all back within 0.01 mm; Build gives no warning."""
    from . import animation, build, sequence
    a = next((x for x in scene.fresing.animations if x.name == FRAME_ANIM), None)
    _check(a is not None, f"no animation '{FRAME_ANIM}'")
    if scene.fresing.anim_baked != a.name:
        res = animation.bake(scene, a)
        _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    apart = next(b for b in a.blocks if b.kind == "SEQUENCE")
    parts = sequence.movers(scene, _ob(scene, FRAME_UNIT)).parts
    _check(len(parts) == 7, f"{len(parts)} parts move, not 7")
    keep = scene.frame_current
    try:
        def at(f):
            scene.frame_set(f)
            return {o.name: o.matrix_world.copy() for o in parts}
        home = at(animation.frame_of(a, apart.start))
        out = at(animation.frame_of(a, apart.start + apart.duration))
        end = at(scene.frame_end)
    finally:
        scene.frame_set(keep)
    side = 0
    for o in parts:
        d = out[o.name].translation - home[o.name].translation
        nm = o.get(build.PROP_NAME, o.name)
        _check(d.length > 0.05, f"'{nm}' moved only {d.length * 1000:.0f} mm")
        if nm in FRAME_UNDER:
            _check(abs(d.z) < 1e-5, f"'{nm}' flew up through the frame's beam")
            side += 1
        else:
            _check(d.z > 0.05, f"'{nm}' did not go up")
    worst = max(max(abs(x) for r in (end[n] - home[n]) for x in r) for n in home)
    _check(worst < 1e-5, f"put together, a part is {worst * 1000:.3f} mm from where it started")
    return f"7 parts out, {side} sideways under the beam, back within {worst * 1000:.4f} mm"


def check_back_to_cad(scene) -> str:
    """The carriage and the gripper slide out (a pose), then Back to CAD brings both back to 0 over its second."""
    from . import animation, joints
    a = next((x for x in scene.fresing.animations if x.name == BACK_ANIM), None)
    _check(a is not None, f"no animation '{BACK_ANIM}'")
    if scene.fresing.anim_baked != a.name:
        res = animation.bake(scene, a)
        _check(not res["warnings"], "Build warns: " + "; ".join(res["warnings"]))
    slide, lift = frame_rig(scene)
    cad = next(b for b in a.blocks if b.kind == "CAD")
    keep = scene.frame_current
    try:
        scene.frame_set(animation.frame_of(a, cad.start))
        before = joints.get_value(slide)
        scene.frame_set(animation.frame_of(a, cad.start + cad.duration / 2))
        mid = joints.get_value(slide)
        scene.frame_set(scene.frame_end)
        after = (joints.get_value(slide), joints.get_value(lift))
    finally:
        scene.frame_set(keep)
    _check(before > 0.05, f"the pose put the carriage at {before * 1000:.0f} mm, not 60 mm")
    _check(0.0 < mid < before, "half way, the carriage is not on its way back")
    _check(max(abs(x) for x in after) < 1e-6, f"Back to CAD left the joints at {after}")
    return f"carriage {before * 1000:.0f} mm -> {mid * 1000:.0f} mm -> 0, gripper -> 0"


@tour_set("sequenceframe", "Round a frame, back to CAD", "test_sequence_frame.step", added="0.2.102")
def build_sequenceframe(b: Build):
    from . import states
    sc = b.scene
    _look("PRODUCT")
    pts = __import__("numpy").array([(x, y, z) for x in (-0.2, 0.2) for y in (-0.2, 0.35) for z in (0.0, 0.25)])
    _camera(b, "ISO", "Tour view", points=pts)
    shot = _shot(b, "Tour: round a frame")
    a = _animation(b, FRAME_ANIM, shot.name)
    frame_steps(sc, a)
    slide, lift = frame_rig(sc)
    from . import joints
    joints.set_value(slide, 0.06)
    joints.set_value(lift, 0.02)
    _update()
    pose = states.save_pose(sc, "Slid out")
    joints.set_value(slide, 0.0)
    joints.set_value(lift, 0.0)
    _update()
    back = _animation(b, BACK_ANIM, shot.name)
    p = back.blocks.add()
    p.kind, p.pose, p.start, p.duration, p.easing = "POSE", pose.name, 0.0, 1.0, "SMOOTH"
    c = back.blocks.add()
    c.kind, c.start, c.duration, c.easing, c.cad_whole = "CAD", 1.5, 1.0, "SMOOTH", True


def _tall_view_points(scene):
    """The unit and the column of parts above it when it is taken apart (about 0.9 m high)."""
    import numpy as np
    return np.array([(x, y, z) for x in (-0.2, 0.2) for y in (-0.2, 0.2) for z in (0.0, TALL)])


def _gantry(b: Build, tools_too: bool = False):
    from . import gcode, tools
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc, GANTRY_AXES)
    gcode.find_axes(sc)
    tool = _ob(sc, "TOOL T1 FLAT D6")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, _ob(sc, "STOCK 300x200x30"))
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    del tools, tools_too
    return tool


@tour_set("gantry", "CNC gantry", "test_gantry.step", added="0.2.47", changed="0.2.161")
def build_gantry(b: Build):
    from . import gcode, tools
    sc = b.scene
    tool = _gantry(b)
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: CNC gantry")
    a = _animation(b, "G-code", shot.name)
    blk = _gcode_step(a, _program(b, "Tour program.ngc", GCODE_TOUR), sc)
    gcode.tools_from_program(sc, blk)
    tools.use_part(sc, tools.row_of(sc, 1), tool)
    # task 0103: many short moves above the block, timed with acceleration
    _check(sc.fresing.cnc.use_accel, "Speed up and slow down is off for a new machine")
    acc = _animation(b, ACCEL_ANIM, shot.name)
    _gcode_step(acc, _program(b, "Acceleration.ngc", ACCEL_TOUR), sc)


def _check_accel(scene):
    from . import gcode
    a = scene.fresing.animations.get(ACCEL_ANIM)
    _check(a is not None and len(a.blocks) == 1, f"no animation '{ACCEL_ANIM}'")
    blk = a.blocks[0]
    info = gcode.info(scene, blk)
    _check(info.get("accel"), "the program is not timed with acceleration (4 Motion > CNC machine > Machine)")
    with_s, without = info["machine_s"], info["plain_s"]
    _check(with_s > 1.2 * without, f"with acceleration {with_s:.2f} s is not clearly longer than {without:.2f} s")
    _check(blk.duration > without, f"the step lasts {blk.duration:.2f} s, not longer than {without:.2f} s")
    return f"{gcode.fmt_time(with_s)} – {gcode.fmt_time(without)} without acceleration"


def _check_gcode(scene):
    import bpy

    from . import gcode
    _check(gcode.path_object() is not None, "no toolpath drawn")
    copy = next((o for o in bpy.data.objects if o.get(gcode.TAG) == "tool" and o.get("fr_cnc_t") == 2), None)
    scene.frame_set(scene.frame_end)
    tool = _ob(scene, "TOOL T1 FLAT D6")
    _check(copy is not None and not copy.hide_render and tool.hide_render, "T2 does not show in the spindle "
           "after the tool change")
    return f"{scene.frame_end} frames, T1 → T2, toolpath drawn"


TOOLCHANGE_TOUR = """(T1 D=6. CR=0. - flat end mill)
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


@tour_set("atc", "Tool changer", "test_gantry.step", added="0.2.47", changed="0.2.101")
def build_atc(b: Build):
    from mathutils import Vector

    from . import gcode, joints, toolchange, tools
    sc = b.scene
    tool = _gantry(b)
    a = _animation(b, "Tool changer")
    blk = _gcode_step(a, _program(b, "Tour tool changes.ngc", TOOLCHANGE_TOUR), sc)
    gcode.tools_from_program(sc, blk)
    rows = {n: tools.row_of(sc, n) for n in (1, 2, 3, 4)}
    _check(all(rows.values()), "Tools from the program did not add T1 … T4")
    tools.use_part(sc, rows[1], tool)
    tools.use_part(sc, rows[2], _ob(sc, "TOOL T2 BALL D4"))
    tools.use_part(sc, rows[3], _ob(sc, "TOOL T3 DRILL D5"))
    for n, length in ((1, 30), (2, 30), (3, 40), (4, 30)):
        rows[n].length = length * 0.001
    car = _ob(sc, "CAROUSEL.ASM")
    joints.create(sc, "ROTATE", [car], Vector((0.5, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    cnc = sc.fresing.cnc
    cnc.changer, cnc.carousel_joint = "ATC", "Carousel"
    rows[1].pocket = 7
    toolchange.add_pocket(sc, _ob(sc, "CAROUSEL DISC"), Vector((0.56, 0, 0.14)))
    cnc.pocket_count = 8
    why = toolchange.fill_carousel(sc)
    _check(not why, why)
    _check(not toolchange.problems(sc), "; ".join(toolchange.problems(sc)))
    _close_camera(b, Vector((0.5, 0.0, 0.2)), 0.45, "Tour carousel")
    a.start_shot = _shot(b, "Tour: carousel").name


def _changes(scene, a):
    from . import gcode
    from ..core import gcode as core
    blk = next(x for x in a.blocks if x.kind == "GCODE")
    mach = gcode.Machine(scene)
    sch = core.Schedule(gcode.read_program(scene, blk, mach, start=gcode.start_point(mach))[0],
                        gcode.timing(scene, a, blk, mach))
    return sch


def _check_atc(scene):
    import bpy
    a = scene.fresing.animations.get("Tool changer")
    sch = _changes(scene, a)
    changes = [x for x in sch.changes if x.length > 0]
    _check([(x.old_pocket, x.new_pocket) for x in changes] == [(7, 1), (1, 3), (3, 4), (4, 7)],
           "the tools go to the wrong pockets: " + ", ".join(f"{x.old_pocket}->{x.new_pocket}" for x in changes))
    scene.frame_set(1)
    in_pocket = {o["fr_cnc_pocket"]: o for o in bpy.data.objects if "fr_cnc_pocket" in o}
    _check(sorted(in_pocket) == [1, 4], "the tools are not shown in their pockets on the first frame")
    return "4 changes, every tool to its own pocket"


@tour_set("doublearm", "Double-arm tool changer", "test_atc.step", added="0.2.51", changed="0.2.101")
def build_doublearm(b: Build):
    from mathutils import Vector

    from . import doublearm
    sc = b.scene
    a = _animation(b, "Double-arm changer")
    blk = _gcode_step(a, _program(b, "Tour double-arm.ngc", doublearm.TEST_PROGRAM), sc)
    doublearm.set_up_test_model(sc, blk)
    bad = [t for ok, t in doublearm.check(sc) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    _close_camera(b, Vector((-0.17, 0.0, 0.26)), 0.42, "Tour double arm")
    a.start_shot = _shot(b, "Tour: double arm").name


def _check_doublearm(scene):
    import bpy
    a = scene.fresing.animations.get("Double-arm changer")
    sch = _changes(scene, a)
    arm = [x for x in sch.changes if x.kind == "arm"]
    _check([(x.tool, x.new_pocket) for x in arm] == [(2, 2), (3, 5), (1, 2)],
           "the tools go to the wrong pots: " + ", ".join(f"T{x.tool} from pot {x.new_pocket}" for x in arm))
    t = arm[0].arm_times()
    mid = (t["swap"][0] + t["swap"][1]) / 2
    fr = 1 + mid * int(a.fps)
    scene.frame_set(int(fr), subframe=fr - int(fr))
    held = sorted(o["fr_cnc_carry"] for o in bpy.data.objects if o.get("fr_cnc_carry") and not o.hide_render)
    _check(held == [1, 2], f"the arm does not hold T1 and T2 at its half turn (it holds {held})")
    return f"3 changes, random pots; arm {t['back'][1] - t['grip'][0]:.1f} s per change"


@tour_set("rotary4", "4th axis - rotary table", "test_4axis.step", added="0.2.52", changed="0.2.101")
def build_rotary4(b: Build):
    from mathutils import Vector

    from . import rotary
    sc = b.scene
    a = _animation(b, "4th axis")
    blk = _gcode_step(a, _program(b, "Tour 4th axis.ngc", rotary.TEST_PROGRAM_4AXIS), sc, gcode_path=True,
                      gcode_speed="FIT", gcode_fit=14.0)
    rotary.set_up_test_model(sc, blk)
    bad = [t for ok, t in rotary.check(sc) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    _close_camera(b, Vector((-0.03, 0.0, 0.16)), 0.3, "Tour 4th axis")
    a.start_shot = _shot(b, "Tour: 4th axis").name


@tour_set("rotary5", "5th axis - trunnion", "test_5axis.step", added="0.2.52", changed="0.2.101")
def build_rotary5(b: Build):
    from mathutils import Vector

    from . import rotary
    sc = b.scene
    a = _animation(b, "5th axis")
    blk = _gcode_step(a, _program(b, "Tour 5th axis.ngc", rotary.TEST_PROGRAM_5AXIS), sc, gcode_path=True,
                      gcode_speed="FIT", gcode_fit=12.0)
    rotary.set_up_test_model(sc, blk, five=True)
    bad = [t for ok, t in rotary.check(sc) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    _close_camera(b, Vector((0.0, 0.0, 0.17)), 0.26, "Tour 5th axis")
    a.start_shot = _shot(b, "Tour: 5th axis").name


@tour_set("toolpath", "The app makes the toolpath", "test_toolpath.step", added="0.2.55", changed="0.2.101")
def build_toolpath(b: Build):
    from mathutils import Vector

    from . import machining, toolpath
    sc = b.scene
    _look("PRODUCT")
    toolpath.set_up_test_model(sc, detail="DRAFT")
    t = toolpath.settings(sc)                      # a coarse program, quick to cut and to check for clashes
    t.scallop, t.step_down, t.stepover = 0.0005, 0.010, 90.0
    a = _animation(b, "Toolpath")
    sc.fresing.animations_index = list(sc.fresing.animations).index(a)
    out = toolpath.make(sc, b.file("Tour toolpath.ngc"))
    _check(not out["problems"], "; ".join(out["problems"][:2]))
    _a, blk = toolpath.step(sc)
    blk.gcode_fit = 10.0
    machining.settings(sc).chips = "NONE"
    machining.settings(sc).detail = "FAST"         # (the clash check of every tour animation reads it per moment)
    _close_camera(b, Vector((0.0, 0.0, 0.07)), 0.22, "Tour toolpath")
    a.start_shot = _shot(b, "Tour: toolpath").name


def _check_toolpath(scene):
    from . import toolpath
    _a, blk = toolpath.step(scene)
    _check(blk is not None, "the toolpath's step is missing")
    r = toolpath.result(scene)
    _check(r.get("moves", 0) > 300, "the toolpath has hardly any moves")
    _check([p["tool"] for p in r.get("passes", [])] == [1, 2], "roughing with T1 and finishing with T2 are not both "
                                                              "there")
    _check("Undercut" in r.get("undercut", ""), "the cap that hangs over is not reported as an undercut")
    return f"{r['moves']:,} moves (T1 roughing, T2 finishing), {gcode_time(r)} on the machine; undercut reported"


def gcode_time(r: dict) -> str:
    from . import gcode
    return gcode.fmt_time(r.get("machine_s", 0.0))


def _rotary_at(scene, name: str, letter: str, when):
    """(the joint's angle in the program's degrees, the program's) at the move ``when`` picks, halfway through it."""
    from . import gcode, rotary
    a = scene.fresing.animations.get(name)
    sch = _changes(scene, a)
    p = next(p for p in sch.pieces if when(p.move))
    t = p.v0 + p.vd / 2
    fr = 1 + t * int(a.fps)
    scene.frame_set(int(fr), subframe=fr - int(fr))
    mach = gcode.Machine(scene)
    k = rotary.LETTERS.index(letter)
    return mach.axes[k].angle_of(rotary.joints.get_value(mach.axes[k].joint)), sch.rot_at(t)[k]


def _check_rotary4(scene):
    got, want = _rotary_at(scene, "4th axis", "A", lambda m: m.kind == "FEED" and m.turn > 1)
    _check(abs(got - want) < 0.01, f"A is at {got:.2f}° halfway along the wrapped slot, the program says {want:.2f}°")
    return f"A at {got:.1f}° halfway along the slot (as the program says)"


def _check_rotary5(scene):
    from . import gcode
    _check(gcode.settings(scene).kinematics == "TCP", "the trunnion is not set to Tool follows the part")
    got, want = _rotary_at(scene, "5th axis", "C", lambda m: m.kind == "FEED" and m.turn > 1)
    _check(abs(got - want) < 0.01, f"C is at {got:.2f}° halfway along the groove, the program says {want:.2f}°")
    return f"C at {got:.1f}° halfway along the groove, the tool follows the part"


# the cuts lie in the finished part's pocket (x -50..50, y -30..30, 10 deep): elsewhere the block is the finished part
# up to its top, and a cut there goes into it; the face pass starts at X-10 so the ball mill hanging 120 mm beside the
# spindle stays off the block (the clash check says so since task 0029 keeps every key of a fast program)
TOOLS_TOUR = """(THREE TOOLS: FACE MILL, END MILL, CHAMFER MILL - BT30)
G21 G90 G94 G17 G54
T1 M6 G43 H1
S6000 M3
G0 X-10 Y0 Z5
G1 Z-1 F3000
G1 X20
G0 Z10
M5
T2 M6 G43 H2
S12000 M3
G0 X-40 Y20 Z5
G1 Z-6 F600
G1 X40 F1500
G0 Z10
M5
T3 M6 G43 H3
S10000 M3
G0 X-40 Y-20 Z5
G1 Z-2 F800
G1 X40 F1200
G0 Z20
M5
M30
"""


@tour_set("tools", "Three tools and the hand", "test_mill.step", added="0.2.47", changed="0.2.101")
def build_tools(b: Build):
    import bpy
    from mathutils import Vector

    from . import gcode, machining, toolchange, tools
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    gcode.find_axes(sc)
    tool, stock = _ob(sc, "END MILL D10"), _ob(sc, "STOCK 200x200x40")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, stock)
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    _pick("bit", tool)
    _pick("workpiece", stock)
    face = tools.add_row(sc, "FACE", 1)
    face.diameter, face.length, face.holder, face.holder_length = 0.05, 0.085, "BT30", 0.045
    face.lead_angle = 1.5707963
    end = tools.add_row(sc, "FLAT", 2)
    end.diameter, end.length, end.holder, end.holder_length = 0.01, 0.098, "BT30", 0.06
    vee = tools.add_row(sc, "VEE", 3)
    vee.diameter, vee.length, vee.holder, vee.holder_length = 0.01, 0.09, "BT30", 0.06
    a = _animation(b, "Three tools")
    _gcode_step(a, _program(b, "Tour three tools.ngc", TOOLS_TOUR), sc, gcode_speed="FIT", gcode_fit=14.0,
                gcode_tc_time=1.0, gcode_hand=True)
    del machining, toolchange
    tip = stock.matrix_world.translation + Vector((0.0, 0.0, 0.08))
    _close_camera(b, tip, 0.35, "Tour close-up")
    a.start_shot = _shot(b, "Tour: spindle").name


def _hand_time(scene) -> float:
    from . import toolchange
    a = scene.fresing.animations.get("Three tools")
    sch = _changes(scene, a)
    c = next((x for x in sch.changes if x.hand is not None), None)
    _check(c is not None, "no hand at the manual tool changes")
    out_t, _in_t = toolchange.TC.hand_events(*c.hand)
    return out_t + 0.15


def _check_tools(scene):
    from . import gcode, tools
    lift = gcode.length_offsets(scene, gcode.Machine(scene), [1, 2, 3], 1)
    _check(len(tools.rows(scene)) >= 3, "the tool list has fewer than 3 tools")
    _check(all(r.holder == "BT30" for r in tools.rows(scene) if r.number in (1, 2, 3)), "not all three are BT30")
    return "T1 face mill, T2 end mill, T3 chamfer mill (BT30); length offsets " + ", ".join(
        f"T{k} {v * 1000:+.0f} mm" for k, v in sorted(lift.items()))


def _check_hand(scene):
    import bpy

    from . import toolchange
    hand = bpy.data.objects.get(toolchange.HAND_NAME)
    _check(hand is not None, "no hand")
    _check(not hand.hide_render, "the hand is not shown at this frame")
    carried = [o for o in bpy.data.objects if "fr_cnc_carry" in o and not o.hide_render]
    _check(carried, "the hand holds no tool")
    return "the gloved hand holds the tool"


# tool marks (task 0061): the same rules as above - every cut lies in the finished part's pocket (x -50..50,
# y -30..30, 10 deep) and the face mill stays at X-10 or more. The face mill leaves a strip 80 x 50 mm, 1 mm deep; the
# end mill cuts a pocket 50 x 16 mm at the front of it in two depths (3 and 5 mm); the drill makes one hole behind
# the pocket. Both depths run along the same wall, as in an ordinary program: the wall is then one flat face, and
# the line where the depths meet is drawn by the marks (``Moves.step``, 2 mm). At the end the head goes up and to the
# left, out of the picture.
# Before each tool change the head goes up to Z50: after a change the head comes back to where it was, and the end
# mill and the drill are longer than the face mill - from Z10 the longer tool would dive into the block.
MARKS_FEED, MARKS_SPEED = 900.0, 3000.0          # the face mill: 900 mm/min at 3000 rpm = 0.30 mm per turn
MARKS_SIZE = 7.0                                 # Mark size of the set: the arcs show in a close-up
MARKS_CAMERA = 0.125                             # m from the camera to the middle of the faced strip
MARKS_TOUR = f"""(TOOL MARKS: FACE MILL, END MILL, DRILL - BT30)
G21 G90 G94 G17 G54
T1 M6 G43 H1
S{MARKS_SPEED:g} M3
G0 X-10 Y0 Z5
G1 Z-1 F{MARKS_FEED:g}
G1 X20
G0 Z50
M5
T2 M6 G43 H2
S4000 M3
G0 X-20 Y-17 Z5
G1 Z-3 F400
G1 X20 F1200
G1 Y-11
G1 X-20
G1 Y-17
G1 Z-5 F400
G1 X20 F1200
G1 Y-11
G1 X-20
G1 Y-17
G0 Z50
M5
T3 M6 G43 H3
S2400 M3
G0 X25 Y8 Z5
G81 Z-7 R2 F300
G80
G0 Z60
G0 X-90 Y0
M5
M30
"""


@tour_set("marks", "Tool marks", "test_mill.step", added="0.2.73", changed="0.2.101")
def build_marks(b: Build):
    from mathutils import Vector

    from . import gcode, machining, tools
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    gcode.find_axes(sc)
    tool, stock = _ob(sc, "END MILL D10"), _ob(sc, "STOCK 200x200x40")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, stock)
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    _pick("bit", tool)
    _pick("workpiece", stock)
    g = sc.fresing.groups.get(stock.get("fr_group", ""))
    _check(g is not None, "the block has no material group in 3 Looks")
    g.material = "aluminium_sawn"                  # a sawn aluminium plate: its cut faces are bright machined metal
    m = machining.settings(sc)
    m.marks, m.marks_size, m.marks_strength = True, MARKS_SIZE, 1.0
    face = tools.add_row(sc, "FACE", 1)
    face.diameter, face.length, face.holder, face.holder_length = 0.05, 0.085, "BT30", 0.045
    face.lead_angle = 1.5707963
    end = tools.add_row(sc, "FLAT", 2)
    end.diameter, end.length, end.holder, end.holder_length = 0.01, 0.098, "BT30", 0.06
    drill = tools.add_row(sc, "DRILL", 3)
    drill.diameter, drill.length, drill.holder, drill.holder_length = 0.0085, 0.09, "BT30", 0.06
    a = _animation(b, MARKS_ANIM)
    _gcode_step(a, _program(b, "Tour tool marks.ngc", MARKS_TOUR), sc, gcode_speed="FIT", gcode_fit=10.0,
                gcode_tc_time=0.6, gcode_path=False)
    # close and low over the faced strip, so the sheen of the arcs shows
    _update()                                      # (the work zero is new: its place is known after an update)
    zero = gcode.settings(sc).zero_empty.matrix_world.translation
    centre = zero + Vector((0.005, 0.0, -0.002))
    cam = _close_camera(b, centre, 0.05, "Tour tool marks", view="ISO")
    _update()
    away = cam.matrix_world.translation - centre   # nearer than the fit goes: the strip fills the picture
    cam.location = centre + away.normalized() * MARKS_CAMERA
    cam.data.clip_start = 0.01
    a.start_shot = _shot(b, "Tour: tool marks").name


def _check_marks(scene):
    import numpy as np

    from ..core import toolmarks as tm
    from . import machining, toolmarks
    scene.frame_set(scene.frame_end)
    me = _milled(scene)
    stock = _ob(scene, "STOCK 200x200x40")
    _check(me is not None and stock.data is me, "the block does not show its cut")
    _check(machining.settings(scene).marks, "Tool marks is switched off in 4 Motion > Milling")
    _check(all(k in me.attributes for k in tm.ATTRS), "the milled block does not know which move made its cut faces")
    p = np.empty(len(me.polygons) * 3, np.float32)
    me.attributes[tm.ATTR_P].data.foreach_get("vector", p)
    p = p.reshape(-1, 3)
    kind = np.rint(p[:, 0]).astype(int)
    count = {k: int((kind == k).sum()) for k in (tm.ARCS, tm.FLANK, tm.RINGS, tm.RINGS_WALL)}
    _check(count[tm.ARCS] > 0, "no cut face has the arcs of a tool's flat bottom")
    _check(count[tm.FLANK] > 0, "no wall has the lines of a tool's side")
    _check(count[tm.RINGS] + count[tm.RINGS_WALL] > 0 and count[tm.RINGS] > 0, "the drilled hole has no rings")
    faced = (kind == tm.ARCS) & (np.abs(p[:, 1] - 0.025) < 0.0005)        # under the Ø50 face mill
    _check(bool(faced.any()), "no face of the faced strip has the face mill's arcs (radius 25 mm)")
    gap, want = float(np.median(p[faced, 2])) * 1000.0, MARKS_FEED / MARKS_SPEED
    _check(abs(gap - want) < 0.01 * want, f"the face mill's arcs are {gap:.3f} mm apart, the program gives "
                                          f"F{MARKS_FEED:g} / S{MARKS_SPEED:g} = {want:.2f} mm")
    floor = (kind == tm.ARCS) & (np.abs(p[:, 1] - 0.005) < 0.0005)        # under the Ø10 end mill
    _check(bool(floor.any()), "the pocket's floor has no arcs of the end mill (radius 5 mm)")
    # the pocket's walls: cut in two depths 2 mm apart (on a wall the second number is the step-down)
    wall = (kind == tm.FLANK) & (np.abs(p[:, 1] - 0.002) < 0.0001)
    _check(bool(wall.any()), "the pocket's walls do not know where the second depth starts (2 mm above the floor)")
    n = int(me.get(machining.CUT_SLOT, -1))
    mat = stock.material_slots[n].material if 0 < n < len(stock.material_slots) else None
    _check(mat is not None and toolmarks.group_node(mat) is not None, "the cut faces' material draws no tool marks")
    size = toolmarks.group_node(mat).inputs["Size"].default_value
    _check(abs(size - MARKS_SIZE) < 1e-6, f"Mark size is {size:g} in the material, not {MARKS_SIZE:g}")
    return (f"arcs {gap:.2f} mm apart on the faced strip (F{MARKS_FEED:g} S{MARKS_SPEED:g}), finer arcs on the "
            f"pocket floor, lines on the walls, rings in the hole; {count[tm.ARCS]} / {count[tm.FLANK]} / "
            f"{count[tm.RINGS] + count[tm.RINGS_WALL]} cut faces with arcs / lines / rings, drawn x{MARKS_SIZE:g}")


AIR_TOUR = """(T1 D=10. CR=0. - flat end mill)
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


@tour_set("air", "Air blast", "test_mill.step", added="0.2.47", changed="0.2.101")
def build_air(b: Build):
    import bpy
    from mathutils import Vector

    from . import gcode, machining
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    gcode.find_axes(sc)
    tool, stock = _ob(sc, "END MILL D10"), _ob(sc, "STOCK 200x200x40")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, stock)
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    _pick("bit", tool)
    _pick("workpiece", stock)
    machining.settings(sc).chips = "FEW"
    a = _animation(b, "Pocket with air")
    _gcode_step(a, _program(b, "Tour air.ngc", AIR_TOUR), sc, gcode_speed="FIT", gcode_fit=4.0, gcode_path=False,
                gcode_clean=True, gcode_clean_time=1.0)
    tip = stock.matrix_world.translation + Vector((0.0, 0.0, 0.05))
    _close_camera(b, tip, 0.3, "Tour close-up")
    a.start_shot = _shot(b, "Tour: air blast").name


COOLANT_TOUR = AIR_TOUR.replace("M7", "M8")


@tour_set("coolant", "Coolant", "test_mill.step", added="0.2.48", changed="0.2.101")
def build_coolant(b: Build):
    from mathutils import Vector

    from . import gcode
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    gcode.find_axes(sc)
    tool, stock = _ob(sc, "END MILL D10"), _ob(sc, "STOCK 200x200x40")
    gcode.use_tool(sc, tool)
    gcode.use_workpiece(sc, stock)
    _check(gcode.problem(sc) == "", f"the CNC set-up is not ready: {gcode.problem(sc)}")
    _pick("bit", tool)
    _pick("workpiece", stock)
    sc.fresing.coolant.enabled = True
    a = _animation(b, "Pocket with coolant")
    _gcode_step(a, _program(b, "Tour coolant.ngc", COOLANT_TOUR), sc, gcode_speed="FIT", gcode_fit=4.0,
                gcode_path=False)
    tip = stock.matrix_world.translation + Vector((0.0, 0.0, 0.05))
    _close_camera(b, tip, 0.25, "Tour close-up")
    a.start_shot = _shot(b, "Tour: coolant").name


def _check_coolant(scene):
    import bpy

    from . import coolant
    sp = coolant.spans()
    _check(len(sp) == 1, f"{len(sp)} coolant spans, not 1 (M8 … M9 not seen)")
    f = scene.frame_current
    _check(sp[0, 0] <= f < sp[0, 1], f"frame {f} is not while the coolant flows")
    jets = bpy.data.objects.get(coolant.JETS)
    _check(jets is not None and len(jets.data.vertices) > 0, "no jets at the tool")
    _check(coolant.wet_parts(scene), "no part gets wet")
    return f"flood {(sp[0, 1] - sp[0, 0]) / scene.render.fps:.1f} s; {len(coolant.wet_parts(scene))} wet parts"


def _check_air(scene):
    from . import air, chips
    _milled(scene)
    bk = chips.bake(scene, force=True)
    _check(bk is not None and bk.count > 0, "no chips were worked out")
    _check(bk.stats.get("air_s", 0) > 1.0, "the air did not blow (no M7 seen)")
    return f"{bk.count} chips; {air.codes_text(scene)}"


# ----- vessel motion at sea (task 0085) -----

VESSEL_ANIM = "Vessel at sea"


@tour_set("vessel", "Vessel motion", "test_crane_a.step", added="0.2.65", changed="0.2.101")
def build_vessel(b: Build):
    from mathutils import Vector

    from . import joints
    sc, s = b.scene, b.s
    _look("PRODUCT")
    _boom_joint(sc)
    trolley = _ob(sc, "TROLLEY.ASM")              # rides on the boom (else the boom turns through it)
    joints.create(sc, "SLIDE", [trolley], trolley.matrix_world.translation.copy(), Vector((1, 0, 0)),
                  base=_ob(sc, "BOOM.ASM"), name="Trolley")
    s.env_detail = "DETAILED"
    s.background = "DECK"
    s.sea_state = "CALM"
    s.vessel.heading = "BEAM"
    s.vessel.enabled = True
    _update()
    _camera(b, "ISO", "Tour deck", lens=24.0)
    a = _animation(b, VESSEL_ANIM)
    _joint_step(a, "Boom", 1.0, 6.0, math.radians(20), label="Boom up at sea")
    a.start_shot = _shot(b, "@vessel").name
    # task 0106: the web page with its surroundings (stop "web3d_env"): the project's sea and motion, rain and haze
    from . import web3d_env
    w = s.web3d
    w.texture_size = "512"
    w.env_mode = "PROJECT"
    web3d_env.fill_from_project(sc)
    w.env_haze = True
    w.env_haze_strength = 30.0
    w.env_rain = True
    w.env_clouds = "SOME"
    _shot(b, "@web3d_env")


def _check_vessel(scene):
    from . import vessel_motion
    _check(vessel_motion.effective(scene), "vessel motion is off (or the surroundings are not the Vessel deck)")
    _check(vessel_motion.rig("pivot") is not None, "the vessel's rig is missing")
    sea = next((o for o in scene.objects if o.get("fr_env") == "sea"), None)
    _check(sea is not None and not sea.constraints, "the sea moves with the vessel")
    pk = vessel_motion.peaks(scene)
    _check(1.0 <= pk.get("roll", 0.0) <= 2.0, f"roll ±{pk.get('roll', 0.0):.2f}° is not a calm beam sea (1-2°)")
    _check(pk.get("roll", 0.0) > 2 * pk.get("pitch", 9.0), "in a beam sea the vessel should roll more than pitch")
    base = _ob(scene, "BASE")
    scene.frame_set(1)
    a = base.matrix_world.copy()
    scene.frame_set(max(2, scene.frame_end // 2))
    moved = (base.matrix_world.translation - a.translation).length
    _check(moved > 0.01, f"the crane's base moved only {moved * 1000:.0f} mm")
    return vessel_motion.words(scene)


# ----- weather and time of day (task 0109) -----

WEATHER_ANIM = "Weather changes"


# ----- props for scale in detail (task 0155) -----


@tour_set("props", "Props for scale and people", "test_crane_a.step", added="0.2.124")
def build_props(b: Build):
    from . import cameras, props_scale
    _look("PRODUCT")
    obs = props_scale.line_up(b.scene)
    cameras.add_camera(b.scene, "ISO", 50.0, "Tour props", points=props_scale.corners(obs))
    _shot(b, "@props")


def _check_props(scene):
    from . import props_scale
    return props_scale.check_line_up(scene)


# ----- people walk, carry and meet (task 0157) -----

PEOPLE_ANIM = "Two people meet"


OPERATOR_ANIM = "A person changes the tool"


@tour_set("operator", "A person changes the tool", "test_mill_cabinet.step", added="0.2.132")
def build_operator(b: Build):
    """The test mill on its cabinet (tools/make_test_mill_cabinet.py): one manual change from T1 to T2 done by the
    operator, who walks up, opens the sliding door, swaps the tools over the trolley, closes the door and walks
    away (task 0156; the set-up is shared with the PC check: ``tc_person.set_up_test_model``)."""
    from . import cameras, tc_person
    sc = b.scene
    _look("PRODUCT")
    a = tc_person.set_up_test_model(sc, b.file("Tour operator.ngc"))
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"
    cam = cameras.add_camera(sc, "ISO", 40.0, "Tour operator", points=tc_person.test_camera_points())
    sc.camera = cam
    a.start_shot = _shot(b, "@operator").name


def _check_operator(scene):
    from . import tc_person
    return tc_person.check_test_model(scene)


@tour_set("people", "People walk and meet", "test_crane_a.step", added="0.2.128")
def build_people(b: Build):
    from . import cameras, people
    _look("PRODUCT")
    anna, ben, box = people.set_up_example(b.scene)
    cameras.add_camera(b.scene, "ISO", 50.0, "Tour people", points=people.example_corners(b.scene))
    a = _animation(b, PEOPLE_ANIM)
    a.start_shot = _shot(b, "@people").name


def _check_people(scene):
    from . import people
    return people.check_example(scene)


@tour_set("weather", "Weather and time of day", "test_crane_a.step", added="0.2.88", changed="0.2.125")
def build_weather(b: Build):
    from . import weather
    sc, s = b.scene, b.s
    _look("PRODUCT")
    s.env_detail = "SIMPLE"
    s.background = "QUAY"
    _update()
    _camera(b, "ISO", "Tour quay", lens=28.0)
    s.weather.enabled = True
    weather.use_preset(sc, "GREY_NORTH_SEA")
    _update()
    _shot(b, "@weather")
    weather.use_preset(sc, "NIGHT_SHIFT")
    _update()
    _shot(b, "@night")
    weather.use_preset(sc, "CLEAR_DAY")
    _update()
    a = _animation(b, WEATHER_ANIM)
    blk = a.blocks.add()
    blk.kind, blk.start, blk.duration, blk.easing = "WEATHER", 0.5, 4.0, "LINEAR"
    weather.step_init(sc, a, blk)
    blk.wx_hour, blk.wx_clouds, blk.wx_low_clouds, blk.wx_rain, blk.wx_wet = 18.5, 0.9, 0.4, 0.6, 0.8
    blk.wx_visibility, blk.wx_wind = 6000.0, 6.0
    blk.name = "Day to dusk, rain starting"
    a.start_shot = _shot(b, "Clear day").name


def _channel(scene, name):
    from ..core import weather as core
    return float(scene.get(core.prop(name), -1.0))


def _check_weather(scene):
    from . import weather
    _check(weather.enabled(scene), "Weather & time is off")
    _check(scene.fresing.background == "QUAY", "the background is not the quayside")
    if scene.fresing.anim_baked:
        scene.frame_set(1)
        rain0, day0 = _channel(scene, "rain"), _channel(scene, "day")
        scene.frame_set(scene.frame_end)
        rain1, day1 = _channel(scene, "rain"), _channel(scene, "day")
        _check(rain0 < 0.01 < rain1, f"the rain does not start (rain {rain0:.2f} -> {rain1:.2f})")
        _check(day1 < day0, f"it does not get darker (daylight {day0:.2f} -> {day1:.2f})")
        return f"rain {rain0:.2f} -> {rain1:.2f}, daylight {day0:.2f} -> {day1:.2f}"
    _check(_channel(scene, "wet") > 0.3, "the machine is not wet")
    _check(_channel(scene, "rain") > 0.05, "no rain falls")
    _check(any(o.get("fr_weather") == "rain" for o in scene.objects), "the rain object is missing")
    return weather.header(scene)


def _check_start_scene(scene):
    """Task 0160: the weather shown is not the start scene's: Build would put it back, and the panel says so."""
    from . import states
    a = scene.fresing.animations.get(WEATHER_ANIM)
    _check(a is not None and a.start_shot, "the weather video has no start scene")
    scene.fresing.animations_index = list(scene.fresing.animations).index(a)
    changes = states.start_scene_changes(scene, a.start_shot, ["weather"])
    _check(changes, f"the weather shown is the start scene's '{a.start_shot}': nothing to save into it")
    return f"Build puts back '{a.start_shot}': {states.start_scene_words(changes)}"


def _check_night(scene):
    from . import weather
    _check(weather.enabled(scene), "Weather & time is off")
    _check(_channel(scene, "night") > 0.9, f"it is not dark (night {_channel(scene, 'night'):.2f})")
    _check(_channel(scene, "flood") > 0.5, "the floodlights are off")
    lamps = [o for o in scene.objects if o.type == "LIGHT" and o.get("fr_weather")]
    _check(len(lamps) >= 2, f"only {len(lamps)} night lamps")
    return weather.header(scene)


# ----- a house from House Planner (task 0114) -----

HOUSE_MOMENT = "summer-evening"


@tour_set("house", "House from House Planner", "sample-house.hpscene", added="0.2.92", changed="0.2.152")
def build_house(b: Build):
    """The made-up sample house: imported, one moment baked small (the package next to the tour), the evening
    shown in the view from the recipe's garden camera."""
    import shutil

    import bpy

    from . import house_bake, house_import
    sc = b.scene
    src = b.file("sample-house.hpscene")
    shutil.copyfile(os.path.join(DATA, "sample-house.hpscene"), src)
    house = house_import.import_scene(sc, src)["house"]
    path = b.file("sample-house.hpbake")
    out = house_bake.HouseBake(sc, path, moments=[house.recipe.moments[0].id], photos=False, videos=False,
                               samples=4).run()
    h = house_import.settings(sc)
    h.last_bake, h.last_seconds = out["path"], float(out["seconds"])
    h.last_problems = "\n".join(out["problems"])
    h.last_text = f"1 moment baked in {out['seconds'] / 60:.1f} min (tour: 4 samples)"
    cam = house.recipe.cameras.get("garden-view") or next(iter(house.recipe.cameras.values()))
    data = bpy.data.cameras.new("Tour garden")
    data.sensor_fit = "VERTICAL"
    data.angle_y = math.radians(float(cam.fov))
    ob = bpy.data.objects.new("Tour garden", data)
    sc.collection.objects.link(ob)
    ob.matrix_world = house_bake.camera_matrix(cam.position, cam.target)
    sc.camera = ob
    house_import.preview(sc, HOUSE_MOMENT)
    _update()
    _shot(b, "@house")


def _check_house(scene):
    from ..core import house_scene as hs
    from . import house_import
    _check(house_import.has_house(scene), "no house in this project")
    h = house_import.settings(scene)
    house = house_import.house(scene)
    m = next((x for x in house.recipe.moments if x.id == HOUSE_MOMENT), None)
    _check(m is not None, f"the sample has no moment '{HOUSE_MOMENT}'")
    el, az = hs.sun_angles(m.direction)
    got = house_import._angle(el, az, _channel(scene, "sun_el"), _channel(scene, "sun_az"))
    _check(got < 0.5, f"the sky's sun is {got:.1f}° from House Planner's evening sun")
    _check(bool(h.last_bake) and os.path.exists(h.last_bake), "the bake package next to the tour is missing")
    bad = hs.structure_problems(h.last_bake, house)
    _check(not bad, "the bake package is not right: " + "; ".join(bad[:2]))
    return f"evening sun {el:.1f}° high; package {os.path.getsize(h.last_bake) / 1024:.0f} KB"


# ----- a mesh model (task 0117) -----

MESH_ANIM = "Slew the turret"


def mesh_ring_click(scene):
    """Click the mesh crane's facetted slewing ring like a user: a ray at its outer wall, half way up, between two
    corners. Returns (part, axis origin, axis direction, the picker's words)."""
    import bpy
    from mathutils import Vector

    from . import hover, joints
    a = math.radians(3.75)                              # half a facet of the 48-sided ring
    n = Vector((math.cos(a), math.sin(a), 0.0))
    pt = Vector((0.8 * math.cos(a) * math.cos(a), 0.8 * math.sin(a), 0.475))
    ob, index, loc, normal = hover.cast(scene, bpy.context.evaluated_depsgraph_get(), pt + n * 0.01, -n)
    _check(index >= 0, "the click did not hit the slewing ring")
    o, d, desc = joints.axis_from_hit(ob, index, loc, normal)
    return ob, o, d, desc


@tour_set("mesh", "Mesh model (glTF)", "test_mesh_crane.glb", added="0.2.99")
def build_mesh(b: Build):
    """The invented mesh crane (a glTF file: no CAD faces) imported; its 48-sided slewing ring clicked for a joint
    that turns the turret, as a user does it."""
    from . import joints
    sc = b.scene
    _look("PRODUCT")
    _update()
    _ring, o, d, _desc = mesh_ring_click(sc)
    joints.create(sc, "ROTATE", [_ob(sc, "TURRET")], o, d, name="Slew", base=_ob(sc, "BASE"))
    _update()
    _camera(b, "ISO", "Tour view")
    _shot(b, "@mesh_import")
    a = _animation(b, MESH_ANIM, shot=shot_name(find("mesh_import")))
    _joint_step(a, "Slew", 0.0, 4.0, math.radians(120), label="The turret turns on the ring")
    _bake(sc, a)


def _check_mesh(scene):
    from . import build, joints, mesh_import
    root = build.model_roots(scene)[0]
    _check(mesh_import.is_mesh_model(root), "the crane did not come in as a mesh model")
    _check("Mesh crane" in root.get(mesh_import.PROP_CREDIT, ""), "the file's credit line is missing")
    j = joints.find(scene, "Slew")
    _check(j is not None and joints.is_valid(j), "the joint on the slewing ring is missing")
    ring, _o, d, desc = mesh_ring_click(scene)
    _check(ring.get(build.PROP_NAME) == "SLEWING RING" and desc.startswith("round face"),
           f"the ring's wall is not a round face ({desc})")
    off = math.degrees(math.acos(min(1.0, abs(d.normalized().z))))
    _check(off < 0.5, f"the ring's axis is {off:.2f}° off vertical")
    dia = float(desc.split("Ø")[1].split()[0])
    _check(abs(dia - 1600.0) < 8.0, f"the ring measures Ø{dia:.1f} mm, it is Ø1600")
    base = _ob(scene, "BASE")
    _check(base.material_slots[0].material is not None and base.material_slots[0].material.get("fr_has_texture"),
           "the base lost its texture from the file")
    return f"ring Ø{dia:.1f} mm, axis {off:.2f}° off vertical"


# ---------------------------------------------------------------------------
# the stops, in order (numbers follow this order)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lifting plan (task 0201): an AT-40 beside the test crane, the test crane's boom as the load
# ---------------------------------------------------------------------------

@tour_set("lifting", "Lifting plan – crane, load and hook", "test_crane_a.step", added="0.2.156",
          changed="0.2.159")
def build_lifting(b: Build):
    import bpy
    import numpy as np

    from . import build, lifting, logic
    sc = b.scene
    _look("PRODUCT")
    roots = build.model_roots(sc)
    mn, mx = (np.asarray(v, float) for v in logic.update_bounds(sc))
    c = lifting.place(bpy.context, os.path.join(DATA, "lifting", lifting.EXAMPLE_CRANE),
                      (float(mx[0]) + 6.0, float(0.5 * (mn[1] + mx[1])), float(mn[2])), math.pi)
    lifting.apply_pose(sc, c, "Set up")
    _update()
    pts = _lifting_points(sc)
    _camera(b, "ISO", "Tour lifting", lens=35.0, points=pts)
    _shot(b, "@lifting_place")
    part = next(o for o in logic.descendants(roots[0]) if o.get(build.PROP_NAME) == lifting.EXAMPLE_LOAD)
    ld = lifting.new_load(sc, [part], "Test crane boom")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", lifting.EXAMPLE_MASS, "DRAWING"
    _close_camera(b, lifting.cog_world(ld), 1.6, "Tour lifting CoG")
    _shot(b, "@lifting_cog")
    a = lifting.hook_to(sc, c, lifting.above_load(sc, ld), ld)
    _check(a.ok, f"Hook to here: {a.reason}")
    _camera(b, "ISO", "Tour lifting hook", lens=35.0, points=_lifting_points(sc))
    _shot(b, "@lifting_hook")


@tour_set("crane_setup", "Set up a crane – the KB-20 from its bare STEP", "lifting/KB-20/KB-20.step",
          added="0.2.161", changed="0.2.166")
def build_crane_setup(b: Build):
    """Task 0203: the built-in KB-20's bare STEP rigged through Set up a crane's own buttons, by names (the steps of
    a knuckle-boom crane), checked; the Set-up window would open on its Check step."""
    from . import crane_example, setup_crane
    sc = b.scene
    _look("PRODUCT")
    crane_example.rig(sc, "KB-20", check=True, clash=False)
    from . import ops_setup
    k = setup_crane.step_index("CRANE_KNUCKLE", "check")
    ops_setup.go(sc, k)
    for name in ("Working",):
        if name in sc.fresing.poses:
            from . import states
            states.apply_pose(sc, name)
    _update()
    _camera(b, "ISO", "Tour crane set-up", lens=35.0, points=_crane_points(sc))
    _shot(b, "@crane_setup")


def _crane_points(scene):
    """Every part's box corners (the camera frames the whole crane)."""
    import numpy as np

    from . import build
    pts = [np.array(ob.matrix_world) @ np.r_[np.asarray(c, float), 1.0] for ob in build.iter_parts(scene)
           for c in ob.bound_box]
    return np.array([p[:3] for p in pts])


def _check_crane_setup(scene):
    from . import setup_crane as SC
    cs = SC.settings(scene)
    js = SC.crane_joints(scene)
    roles = sorted({j.role for j in js if j.role != "NONE"})
    _check(len(js) >= 20, f"{len(js)} crane joints (want the KB-20's 21)")
    _check({"slew", "luff", "knuckle", "extension", "hoist", "swing", "outrigger", "jack"} <= set(roles),
           f"roles {roles}")
    _check(cs.hook_set and cs.checked, "the hook point is not set or Check did not run")
    red = [p.text for p in cs.problems if p.severity == "red"]
    _check(not red, "Check: " + "; ".join(red[:2]))
    return f"{len(js)} joints with {len(roles)} roles, hook point set, Check: nothing wrong"
@tour_set("lifting_make", "Lifting plan – a crane made from numbers", "test_crane_a.step", added="0.2.159",
          changed="0.2.159")
def build_lifting_make(b: Build):
    """Task 0204: Make a crane… – the AT-100's numbers with 5 sections and a 50 m boom, made into a library next to the
    tour, placed beside the test crane, set up, Hook to here above the test crane's boom."""
    import bpy
    import numpy as np

    from . import build, lifting, logic, ops_lifting_make
    sc = b.scene
    _look("PRODUCT")
    lib = os.path.join(b.folder, "Lifting equipment")
    os.makedirs(lib, exist_ok=True)
    job = ops_lifting_make.make_now(ops_lifting_make.tour_spec(), lib, replace=True)
    roots = build.model_roots(sc)
    mn, mx = (np.asarray(v, float) for v in logic.update_bounds(sc))
    c = lifting.place(bpy.context, job.item_path, (float(mx[0]) + 7.0, float(0.5 * (mn[1] + mx[1])), float(mn[2])),
                      math.pi)
    lifting.apply_pose(sc, c, "Set up")
    part = next(o for o in logic.descendants(roots[0]) if o.get(build.PROP_NAME) == lifting.EXAMPLE_LOAD)
    ld = lifting.new_load(sc, [part], "Test crane boom")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", lifting.EXAMPLE_MASS, "DRAWING"
    a = lifting.hook_to(sc, c, lifting.above_load(sc, ld), ld)
    _check(a.ok, f"Hook to here: {a.reason}")
    _update()
    _camera(b, "ISO", "Tour lifting make", lens=35.0, points=_lifting_points(sc))
    _shot(b, "@lifting_make")


def _check_lifting_make(scene):
    from . import lifting, ops_lifting_make
    L = lifting.plan(scene)
    if not L.cranes:
        raise ValueError("no crane in the lifting plan")
    c = L.cranes[0]
    if c.item_name != ops_lifting_make.TOUR_CRANE:
        raise ValueError(f"the crane is {c.item_name}, not the one made from numbers")
    tele = [j.name for j in lifting.own_joints(scene, c) if "Telescope" in j.name]
    if len(tele) != 4:
        raise ValueError(f"{len(tele)} telescope joints, not 4 (5 sections)")
    if not lifting.item_at(lifting.path_of(c)).sample:
        raise ValueError("the made crane is not marked SAMPLE")
    return lifting.check_rig(scene) + "; " + lifting.check_example(scene)


def _lifting_points(scene):
    import numpy as np

    from . import build
    pts = []
    for ob in build.iter_parts(scene):
        M = np.array(ob.matrix_world)
        for c in ob.bound_box:
            pts.append((M @ np.r_[np.asarray(c, float), 1.0])[:3])
    return np.array(pts)


def _check_lifting_place(scene):
    from . import lifting
    return lifting.check_rig(scene)


def _check_lifting_cog(scene):
    from . import lifting
    return lifting.check_cog(scene)


def _check_lifting_hook(scene):
    from . import lifting
    return lifting.check_example(scene)

LOOK, MOTION, MACH, OUT = GROUPS

stop("materials", LOOK, "looks", "Ready-made materials and Wear",
     "The crane in eight ready-made materials: yellow gloss paint on boom and pedestal, painted cast iron on base "
     "and trolley (both with Wear: in a rendered picture their sharp edges look worn and corners a little dirty), "
     "ground steel pins, a black anodised cylinder barrel with a chrome rod, rubber wheels, blue anodised cover, "
     "zinc flake bolts.",
     where="3 Looks: the material groups, Ready-made material…, Wear", check=_check_materials, since="0.2.47", changed="0.2.101")
stop("faces", LOOK, "faces", "Painted faces",
     "The housing's two faces painted in CAD keep their own colours; one face of the cover is painted red by hand, "
     "the rest of the cover keeps its colour.", where="3 Looks > Paint faces", check=_check_faces, since="0.2.47")
stop("decals", LOOK, "decals", "Logos and stickers",
     "A yellow warning sticker and the text TEST TOUR lie flat on the panel; a 'hot surface' sticker is wrapped "
     "round the barrel.", where="3 Looks > Logos & stickers", check=_check_decals, since="0.2.47")
stop("cutaway", LOOK, "cutaway", "Slice: the pedestal opens up",
     "A slice slides in from the front and takes away the front half of the crane's pedestal and boom: the cut faces "
     "are red with hatch lines, the steel pin shows inside the fork. The other parts are not cut. Look in rendered "
     "view: the grey solid view shows the parts whole.", where="3 Looks > Slice; 6 Animation (Move joint step "
     "with the joint 'Slice 1')", since="0.2.64", changed="0.2.168", animation=CUT_ANIM, at=1.0, play=True, check=_check_cutaway,
     auto="clip")
stop("cut_look", LOOK, "mill", "Cut faces and raw stock",
     "The steel block has dark mill scale outside; the walls and floor of the milled slot look freshly machined "
     "(bright steel).", where="4 Motion > Milling > Cut faces; 3 Looks (the block's group)",
     animation="Mill a slot", at=1.0, check=_check_cut_look, since="0.2.47")
stop("marine", LOOK, "marine", "Marine growth, streaks, concrete",
     "A yellow pile standing in water: dark green-brown growth with a ragged top just below the waterline, a "
     "greenish splash zone with thin rust streaks above it, clean yellow higher up. The grey wall behind has faint "
     "run-down streaks; the block in front is light grey concrete.",
     where="3 Looks: Ready-made material… (Marine paint, growth below the waterline; Marine paint, run-down "
           "streaks; Concrete)", since="0.2.94", check=_check_marine)
stop("served", LOOK, "served", "Served cable with marker bands",
     "Close up where the power cable leaves the carousel: black yarn served almost straight round the cable – fine "
     "grooves, some strands darker or lighter, a little dust – and two yellow painted marker lines that wind "
     "round the whole cable as one spiral, once round per metre, with ragged edges, the paint thinner in the grooves. "
     "Played, the lines run along with the cable, also on the coil.",
     where="4 Motion > Cables and paths: Look = Served cable (yarn)", animation=SPOOL_ANIM, play=True,
     since="0.2.116", check=_check_served, auto="clip", changed="0.2.123")
stop("sea", LOOK, HUB_SET, "Surroundings: open sea",
     "The crane stands in the open sea with waves; the sky and the light come from the sea set-up.",
     where="5 Scene & Render > Background & surroundings", check=_check_sea, since="0.2.47")
stop("vessel", LOOK, "vessel", "Vessel motion at sea",
     "The crane stands on the vessel deck in a calm beam sea: deck, containers and crane roll gently (about ±1.5°, "
     "once in 11 s), pitch a little and rise and fall with the long waves while the boom goes up. The sea, the sky "
     "and the camera stay put.", where="5 Scene & Render > Vessel motion", since="0.2.65", animation=VESSEL_ANIM,
     at=0.5, play=True, check=_check_vessel, auto="clip")
stop("weather", LOOK, "weather", "Weather: grey North Sea",
     "The crane on the quay in grey North Sea weather: overcast, a strong breeze, drizzle slanting in the wind and "
     "haze in the distance; the crane and the quay look wet (darker, glossy, puddles on flat parts).",
     where="5 Scene & Render > Weather & time", since="0.2.88", check=_check_weather)
stop("weather_step", LOOK, "weather", "Weather changes in a video",
     "A Weather & time step: a clear late morning turns into a wet dusk over four seconds – the sun sinks and "
     "turns orange, clouds come in, the rain starts and the crane gets wet.",
     where="6 Animation > Weather & time step", since="0.2.88", animation=WEATHER_ANIM, at=1.0, play=True,
     check=_check_weather, auto="clip")
stop("start_scene", LOOK, "weather", "Save into start scene",
     "Weather & time shows a box under its tick: \"Build puts back the start scene 'Clear day': Weather Grey North Sea "
     "→ Clear Day …\" with the button Save into start scene. Clicking it would keep the grey weather at Build (leave it "
     "here: the tour's weather video starts from a clear day).", where="5 Scene & Render > Weather & time",
     since="0.2.125", shot="Weather: grey North Sea", check=_check_start_scene)
stop("night", LOOK, "weather", "Night shift",
     "The quay at night: a dark sky with stars and the moon, floodlights on masts light the crane, a damp sheen "
     "on the quay.", where="5 Scene & Render > Weather & time (Night shift)", since="0.2.88", check=_check_night)
stop("props", LOOK, "props", "Props for scale and people",
     "Beside the crane: three people – one standing in navy overalls and a yellow helmet, one pointing in an orange "
     "offshore coverall with reflective bands and gloves, one with both hands forward in office clothes and a "
     "yellow vest – then a container with ribbed walls, a pallet of taped boxes, a red and white barrier, an IBC "
     "tank in its cage, a rack of four gas bottles and a red tool trolley. Faces, fingers and shoe soles show close "
     "up; nothing floats or sinks into the floor.",
     where="5 Scene & Render > Props for scale (click a person for its pose and clothes)", since="0.2.124",
     check=_check_props)
stop("looks", LOOK, HUB_SET, "Light looks",
     "The Dark studio look: a dark background with rim lights. The other looks are one click each in 5 Scene & Render > Light look.",
     where="5 Scene & Render > Light look", check=_check_looks, since="0.2.47")

stop("joint", MOTION, HUB_SET, "Joint: the boom turns",
     "The boom turns up 35° about its pin and stops smoothly; everything on the boom goes with it. The luffing "
     "cylinder under it follows: its rod slides out and its eye stays on the pin under the boom.",
     where="4 Motion (joints); 6 Animation", animation="Boom up", play=True, select=("BOOM",), check=_check_boom,
     auto="clip", since="0.2.47", changed="0.2.101")
stop("stack", MOTION, HUB_SET, "Stacked joints: boom + trolley",
     "The boom turns up while the trolley slides out along it: the two moves add up, the trolley stays on the "
     "boom.", where="4 Motion (the trolley's joint rides on the boom)", animation="Boom and trolley", play=True,
     select=("TROLLEY",), check=_check_stack, auto="clip", since="0.2.47")
stop("fade", MOTION, HUB_SET, "Fade, X-ray and trail",
     "The boom turns up while the trolley runs out along it; meanwhile the cover fades into a light-blue X-ray "
     "(see-through, glowing edges) and a green line draws the path of the trolley's centre behind it. Look in "
     "rendered view: the solid view shows no see-through.", where="6 Animation (Fade out step), 6 Animation > Trail "
     "lines, 3 Looks > X-ray look", since="0.2.59", animation=FADE_ANIM, at=1.0, play=True, check=_check_fade,
     auto="clip")
stop("camera", MOTION, HUB_SET, "Camera rides and flies",
     "The boom turns up while the trolley runs out. For two seconds the camera rides on the boom: the boom stays put "
     "in the picture while the base turns away below it. Then the camera flies round the crane on a smooth path, "
     "keeping the trolley in the middle of the picture. The thin line in the view is the path (never in renders).",
     where="6 Animation (Camera step: Ride along, Fly a path, Watch part)", since="0.2.62", animation=CAMERA_ANIM,
     play=True, check=_check_camera, auto="clip")
stop("explode", MOTION, HUB_SET, "Exploded view",
     "The crane's subassemblies are pulled apart outwards; Reset pose puts them back.",
     where="4 Motion > Poses & exploded views", check=_check_explode, since="0.2.47")
stop("cylinder", MOTION, "cylinder", "Cylinder: stroke drives the arm",
     "The rod comes out of the cylinder 150 mm and pushes the arm up; the rod's eye stays on its pin all the way and "
     "the barrel, with its oil ports and pipe, tilts about its own pin.",
     where="4 Motion > Cylinders", animation="Stroke out", play=True, check=_check_cylinder, auto="clip", since="0.2.47", changed="0.2.101")
stop("mechanism", MOTION, "linkage", "Mechanisms: scissor lift, crank",
     "The scissor lift rises to 1.5 m with every arm following; next to it the crank turns once and the piston "
     "slides back and forth.", where="4 Motion > Mechanisms", animation="Lift and crank", play=True,
     check=_check_linkage, auto="clip", since="0.2.47")
stop("waycover", MOTION, "waycover", "Way cover follows the axis",
     "The carriage slides 500 mm along X on its rails and back; the five folded-sheet cover sections telescope out "
     "and in with it, each by its own share, over the rails and the ball screw.", where="4 Motion > Way covers", animation="X axis out and back", play=True,
     check=_check_waycover, auto="clip", since="0.2.47", changed="0.2.101")
stop("waycover2", MOTION, "waycover2", "Two way covers on one axis",
     "A cover on each side of the carriage: as it slides 500 mm to the right the left cover opens and the right one "
     "closes, every section by its own share; the plates next to the carriage ride on it. And back.",
     where="4 Motion > Way covers", animation="Carriage across and back", play=True,
     check=_check_waycover_two, auto="clip", since="0.2.61")
stop("hoses", MOTION, "hoses", "Hoses and a cable follow the arm",
     "The arm goes up and down and the slide travels: the three hydraulic hoses and the hanging cable bend along, "
     "their ends stay on the fittings and none gets longer or shorter.", where="4 Motion > Hoses and drag chains",
     animation=HOSES_ANIM, play=True, since="0.2.78", check=_check_hoses, auto="clip")
stop("chains", MOTION, "chains", "Drag chains roll with the axes",
     "A short G-code program moves X, Y and Z: each axis' drag chain rolls over its bend, link by link, and its "
     "moving end stays on its bracket.", where="4 Motion > Hoses and drag chains", animation=CHAINS_ANIM, play=True,
     since="0.2.78", check=_check_chains, auto="clip")
stop("cables", MOTION, "cables", "Cable over sheaves and rollers",
     "The wire rope comes off the winch drum, goes over the two sheaves of the A-frame, through the V rollers and "
     "over the chute at 10 m/min: its strands run along, and the drum, both sheaves and both rollers turn with it. "
     "Meanwhile the A-frame leans forward and back and the rope stays in its grooves.",
     where="4 Motion > Cables and paths", animation=CABLE_ANIM, play=True, since="0.2.80", check=_check_cables,
     auto="clip")
stop("spool", MOTION, "spool", "Drum and carousel spooling",
     "Left, the winch: the wire comes off the drum wrap by wrap and the level wind goes along with it, so the wire "
     "runs straight to its sheave. Right, the carousel: its top layer gets smaller turn by turn (paid out "
     "towards the rim) and the arm swings out so its guide stays over the turn being paid out. Then, fast: the drum "
     "winds its wire fully in – every layer is wire, with its climbs at the flanges – and pays it all out to its "
     "anchor; the carousel pays its cable all out (every layer cable, one after the other, down to its core) and "
     "winds it back in. No grey sleeve or ring under the top layer.",
     where="4 Motion > Drums and carousels", animation=SPOOL_ANIM, play=True, since="0.2.85", check=_check_spool,
     auto="clip", changed="0.2.139")
stop("tracks", MOTION, "tracks", "Tensioner tracks and a belt",
     "Front, the tensioner: the cable runs through at 15 m/min and the pads of both tracks run round their sprockets "
     "with it – the pads that hold the cable move exactly as fast as the cable. The top track lifts 150 mm (its pads "
     "keep running; the rods of its two lift cylinders slide up into the barrels on the portal) and comes back down "
     "to squeeze the cable 2 mm. Behind, a belt of separate links runs round three pulleys of different size; all "
     "wheels turn with the chain.",
     where="4 Motion > Tracks and belts", animation=TRACKS_ANIM, play=True, since="0.2.87", check=_check_tracks,
     auto="clip", changed="0.2.101")
stop("sea_cable", MOTION, "sea_cable", "Cable into the sea",
     "The cable runs over the rollers and the horn at the stern and hangs in a curve down to the seabed 15 m below, "
     "seen through the cut-away behind the stern. It pays out at 60 m/min: its stripes run down the curve but stand "
     "still where it lies on the seabed, the seabed moves aft under the vessel, the touch-down stays 20 m behind the "
     "horn and the orange CPS set goes over the horn and down the curve on the cable. A label of four lines points "
     "at the touch-down: Lay data, the top tension, the layback and the speed (60 m/min while it pays out).",
     where="4 Motion > Cables and paths > Into the sea", animation=SEA_ANIM, play=True, since="0.2.91",
     check=_check_sea_cable, auto="clip", changed="0.2.141")
stop("vessel_work", MOTION, "vessel_work", "Vessel at work: wake and jets",
     "A blue workboat sails ahead: a white wake trails behind its stern, fading and breaking up; its waves fan out "
     "behind the bow in a wedge each side (about 20° to the track) and white water rolls off the bow. After 3 s it "
     "slows to a stop and pushes sideways: the azimuths under the stern swing round, the wake fades, and white, boiling "
     "jets stream out from the port side – the bow thruster's and the azimuths' – while the propellers turn.",
     where="5 Scene & Render > Vessel at work; 6 Animation: Vessel at work step", animation=VESSEL_ANIM, play=True,
     since="0.2.127", check=_check_vessel_work, auto="clip")
stop("moving_cable", MOTION, "moving_cable", "A cable on a moving part",
     "A trolley carries a block with a sheave aft along the gantry, over the stern; the hanger tilts and the block is "
     "lowered. The black cable end, clamped on the block, goes round the sheave and over the horn into the sea: "
     "once the sheave has gone past the horn the cable hangs from the sheave instead. Near the seabed the cable is "
     "let go: its end and its turn round the sheave stay behind while the block is lifted away, and settle onto the "
     "seabed in 2 s – the loop lies flat on it. The grey "
     "lift wire from the fairlead over the trolley's head sheave stays tight: its winch pays out as the trolley "
     "travels and the block goes down, and the head sheave turns with it.",
     where="4 Motion > Cables and paths (Winch keeps it tight, Let go here, Into the sea > Settles in)",
     animation=MOVING_ANIM, play=True,
     since="0.2.95", check=_check_moving_cable, auto="clip", changed="0.2.103")
stop("swivel", MOTION, "swivel", "Sheave turns to follow its wire",
     "A yellow deck davit slews 45° one way, 90° back and home again. Its grey wire comes from a fairlead on the deck, "
     "over a sheave under the arm's tip and straight down into the orange hook block. The sheave hangs in a swivel "
     "head: as the arm swings, the head turns about the tip so the wire from the fairlead always runs straight into "
     "the sheave's groove, never across its side; the hook block hangs still under the tip.",
     where="4 Motion > Cables and paths > What it touches: the sheave's Swivel", animation=SWIVEL_ANIM, play=True,
     since="0.2.138", check=_check_swivel, auto="clip")
stop("copies", MOTION, "copies", "Two copies of one STEP",
     "The test crane twice, side by side. The second one has its cover hidden; the first one keeps its cover.",
     where="1 Import (the same file twice); 2 Structure", check=_check_copies, since="0.2.47")
stop("update", MOTION, "update", "Model update A → B",
     "The crane is revision B: it has a new lamp on the boom (selected). The boom is still at 20° and the cover "
     "is still hidden: the work survived the update.", where="1 Import > Update model", select=("BOOM.LAMP",),
     check=_check_update, since="0.2.47")
stop("mesh_import", MOTION, "mesh", "Mesh model: joint on a ring",
     "An invented crane read from a glTF mesh file (no CAD faces): its base shows the file's own grey checker "
     "texture, the other parts the file's colours. The 48-sided slewing ring was clicked like a round CAD face: the "
     "joint 'Slew' turns the turret (cab, boom) 120° about the ring's centre, without wobble. 1 Import shows the "
     "file and its credit line.", where="File > Import > Mesh model (glTF, OBJ, FBX); 1 Import; 4 Motion > Add "
     "joint", since="0.2.99", animation=MESH_ANIM, at=1.0, play=True, check=_check_mesh, auto="clip")

stop("lifting_place", MOTION, "lifting", "Lifting: a crane placed",
     "Beside the test crane stands the built-in AT-40 sample crane, placed from 8 Lifting plan > Equipment, its boom "
     "turned towards the test crane and set up on its four outriggers (pose 'Set up': beams out, pads down on the "
     "ground). Its joints carry its name ('AT-40 · Slew', 'AT-40 · Luff' …); the panel shows the planning-aid line "
     "and the SAMPLE line.", where="8 Lifting plan > Equipment", since="0.2.156", check=_check_lifting_place)
stop("lifting_cog", MOTION, "lifting", "Lifting: the load and its CoG",
     "The test crane's yellow boom is the load (8 Lifting plan > Load: 1.2 t from the drawing). The CoG symbol – a "
     "circle in black and white quarters, 'CoG' next to it – sits inside the boom, drawn on top of everything; the "
     "panel says '(computed)'.", where="8 Lifting plan > Load", since="0.2.156", check=_check_lifting_cog)
stop("lifting_hook", MOTION, "lifting", "Lifting: Hook to here, crane use",
     "Above the load: the AT-40 slewed, luffed and telescoped so its hook block hangs plumb 2 m above the boom's "
     "top, over the CoG. Hook & capacity shows the radius, the hook height, the boom, the chart row (next longer "
     "radius), the gross load (1.2 t + the 0.45 t hook block) and the crane use in % with 'Within entered limits'.",
     where="8 Lifting plan > Hook & capacity", since="0.2.156", check=_check_lifting_hook)

stop("crane_setup", MOTION, "crane_setup", "Set up a crane: KB-20 rigged",
     "The built-in KB-20's bare STEP made a lifting-plan crane through Set up a crane (8 Lifting plan > Equipment > Set "
     "up a crane… > Knuckle-boom crane): its slew, main boom, knuckle, five extensions, hoist with two hook swings and "
     "four stabiliser corners are app joints with their roles (4 Motion > Joints), its two cylinders, poses, masses and "
     "chart are in; the crane stands in its pose 'Working'. The Set-up window is on its step Check: nothing wrong.",
     where="8 Lifting plan > Equipment > Set up a crane…", since="0.2.161", check=_check_crane_setup)
stop("lifting_make", MOTION, "lifting_make", "Lifting: a crane from numbers",
     "Beside the test crane stands 'AT-100 with 5 sections': made with 8 Lifting plan > Equipment > Make a crane… "
     "from the AT-100's numbers with 5 boom sections instead of 7 (boom 50 m fully out). It is set up on its "
     "outriggers and its hook hangs above the test crane's boom (Hook to here). Its boom has 5 sections (joints "
     "Telescope … Telescope 5) and the panel shows the SAMPLE line: its chart is invented.",
     where="8 Lifting plan > Equipment > Make a crane…", since="0.2.159", check=_check_lifting_make)

stop("clash", MOTION, "clash", "Clash check: two arms meet",
     "Arm B turns into place, then arm A comes down onto it and runs 6 mm into it. 6 Animation > Clash check "
     "lists ARM.A × ARM.B, deepest 6.0 mm at the last frame; that row is clicked: both arms are selected and drawn "
     "red in the 3D view (their own colour stays in renders).", where="6 Animation > Clash check",
     since="0.2.53", animation="Arms meet", at=1.0, select=("ARM.A", "ARM.B"), check=_check_clash,
     setup=_clash_setup)

stop("sequence", MOTION, "sequence", "Assembly sequence",
     "The spindle unit comes apart part by part straight up: first the nut and the four bolts, then the pulley, the "
     "cover, the bearings, the spacer, the shaft and last the housing, each starting while the one before is still "
     "on its way (the pulley's key slides up out of the shaft's keyway); a thin blue line draws each part's path. Then it all comes back down in the reverse order and "
     "ends exactly where it was.", where="6 Animation (Add step > Assembly sequence)", since="0.2.79",
     animation=SEQUENCE_ANIM, at=0.5, play=True, check=lambda scene: check_sequence(scene), auto="clip", changed="0.2.101")

stop("productvideo", MOTION, "productvideo", "One-click product video",
     "6 Animation > Make a product video made a whole film from the project: one turn round the machine, the "
     "spindle unit's joint swinging out and back with the camera watching it, then the unit taken apart part by part "
     "and put together again, and at the end a close-up of the unit the app picked (no saved close-up camera). Title "
     "and end card come at render time.", where="6 Animation > Make a product video",
     since="0.2.81", animation=PRODUCT_ANIM, at=0.5, play=True, check=lambda scene: check_product_video(scene),
     auto="clip", changed="0.2.102")

stop("sequenceframe", MOTION, "sequenceframe", "Sequence round a frame, a rider",
     "A slide unit stands under a yellow portal frame. The carriage slides 50 mm and the gripper on it lifts a little; "
     "then the unit comes apart 'Up': the two bolts go straight up past the beam, but every part under the beam goes "
     "sideways out of the frame's open side instead of through it. The gripper block (it rides on the carriage) "
     "leaves first, from where the carriage put it, and stays where it flew while the carriage leaves under it. Then "
     "it all comes back and ends exactly where it was.", where="6 Animation (Add step > Assembly sequence)",
     since="0.2.102", animation=FRAME_ANIM, at=0.45, play=True, check=lambda scene: check_frame(scene), auto="clip")

stop("backtocad", MOTION, "sequenceframe", "Back to CAD step",
     "The saved pose 'Slid out' moves the carriage and the gripper out; then the step 'Back to CAD' slides both back "
     "to where the CAD file has them, smoothly, over one second.", where="6 Animation (Add step > Back to CAD)",
     since="0.2.102", animation=BACK_ANIM, at=0.75, play=True, check=lambda scene: check_back_to_cad(scene),
     auto="clip")

stop("people", MOTION, "people", "People walk, carry and meet",
     "Beside the crane Anna (orange coverall) walks in carrying a red toolbox, her feet stepping without sliding. "
     "She stops by Ben, bends and puts the box on the floor; they turn to each other, shake hands and talk – "
     "nodding, taking turns, gesturing with their hands.",
     where="6 Animation > People (Example: two people meet, then Build)", since="0.2.128", animation=PEOPLE_ANIM,
     at=0.55, play=True, check=_check_people, auto="clip")
stop("operator", MACH, "operator", "A person changes the tool",
     "On the test mill in its cabinet the operator walks up before the tool change, opens the sliding door with "
     "the handle, presses the release button with the left hand and takes the end mill out by its BT30 holder, lays "
     "it on the tool trolley, takes the ball mill, puts it in, closes the door and walks away after the program. "
     "The hands stay on the holder and the handle; the feet do not slide; nobody walks through the machine.",
     where="6 Animation > Run G-code program > Lines, tool changes … (Changed by: Person); 4 Motion > CNC machine > "
           "Tool changes > Person at the machine", since="0.2.132", animation=OPERATOR_ANIM, at=0.45, play=True,
     check=_check_operator, auto="clip")
stop("gcode", MACH, "gantry", "G-code program runs the machine",
     "The gantry runs on its rails through a short program: lines, arcs, a tool change to T2 and drilling. The "
     "toolpath is drawn as a thin tube; the tool's tip follows it.", where="4 Motion > CNC machine; 6 Animation (Run G-code program)",
     animation="G-code", play=True, check=_check_gcode, auto="clip", since="0.2.47", changed="0.2.101")
stop("accel", MACH, "gantry", "Acceleration: slow short moves",
     "The tool runs 2 mm zigzag steps above the block: first blended (G64) – it slows at each corner but keeps going –, "
     "then the same steps back with exact stops (G61) – it stops at every corner –, then one long line where it speeds "
     "up, runs and slows down. 6 Animation shows the step's time with and without acceleration (with is clearly "
     "longer).", where="4 Motion > CNC machine > Machine (Speed up and slow down); 6 Animation (Run G-code program)",
     animation=ACCEL_ANIM, play=True, since="0.2.83", check=_check_accel, auto="clip")
stop("tools", MACH, "tools", "Three tools with M6 and G43",
     "A Ø50 face mill faces a strip, a Ø10 end mill cuts a slot, a chamfer mill runs along its edge: three tools "
     "from the tool list, each in a BT30 holder, changed with M6 and measured with G43. No tool goes into the block "
     "where the program does not cut (the end mill is 28 mm longer than the face mill). An M6 without G43 for the "
     "new tool would get a line in the Build result and a row in the clash check.",
     where="4 Motion > CNC machine > Tools", animation="Three tools", at=1.0, check=_check_tools, auto="clip", since="0.2.47", changed="0.2.76")
stop("hand", MACH, "tools", "Tool change by hand (BT30)",
     "At a tool change a gloved hand takes the tool out by its BT30 holder and puts the next one in; for a longer "
     "tool the spindle first rises by the difference, then comes down to the program.", where="4 Motion > CNC machine > Tool changes (Manual, Show hand)", animation="Three tools",
     at=-1.0, check=_check_hand, since="0.2.47", changed="0.2.76")
stop("marks", MACH, "marks", "Tool marks on cut faces",
     "A close-up of the milled aluminium block. The faced strip shows the wide arcs of the Ø50 face mill, bulging the "
     "way it went; the pocket's floor shows the finer arcs of the Ø10 end mill; its walls show fine upright lines and "
     "a level line where the second depth starts; the drilled hole shows rings. Look in "
     "rendered view and orbit: the sheen swirls with the arcs. The marks are drawn 7 times further apart than real "
     "(Mark size) so they show.",
     where="4 Motion > Milling (Tool marks, Mark size, Strength)", since="0.2.73", animation=MARKS_ANIM, at=1.0,
     check=_check_marks)
stop("atc", MACH, "atc", "Tool changer: 8-pocket carousel",
     "The tools stand in their pockets from the first frame; at each change the carousel turns the shortest way, "
     "the right pocket comes to the spindle and the old tool goes back to its own pocket.",
     where="4 Motion > CNC machine > Tool changes (Tool changer)", animation="Tool changer", play=True,
     check=_check_atc, auto="clip", since="0.2.47")
stop("doublearm", MACH, "doublearm", "Double-arm tool change",
     "Three BT30 tools: at each Tn the magazine turns the next tool's pot to the arm and tips it down; at M6 the head "
     "goes up, the arm turns onto both tools, pulls them out, turns half round and pushes them in. The old tool goes "
     "into the pot the new one came from; no tool ever jumps or hangs in the air.",
     where="4 Motion > CNC machine > Tool changes (Double-arm)", animation="Double-arm changer", play=True,
     since="0.2.51", check=_check_doublearm, auto="clip")
stop("rotary4", MACH, "rotary4", "4th axis: the bar turns",
     "A rotary table turns a round bar while the tool cuts a slot wrapped once round it, then mills a flat on top, "
     "turns the bar half round and mills the same flat underneath. The orange toolpath lies on the bar and turns "
     "with it.", where="4 Motion > CNC machine > Rotary axes (4th / 5th axis)", animation="4th axis", play=True,
     since="0.2.52", check=_check_rotary4, auto="clip")
stop("rotary5", MACH, "rotary5", "5th axis: tilt and turn (TCP)",
     "The trunnion tilts the block 30° and the tool mills a pocket on its side, the table turns half round for the "
     "second pocket, then a groove is cut while the table turns 90°. With Tool follows the part the tool tip stays "
     "on the block's path the whole time.", where="4 Motion > CNC machine > Rotary axes (Kinematics: Tool follows "
     "the part)", animation="5th axis", play=True, since="0.2.52", check=_check_rotary5, auto="clip")
stop("toolpath", MACH, "toolpath", "Make a toolpath: rough + finish",
     "The app made the program itself: the flat end mill T1 roughs the block level by level (zigzag, then once round "
     "the walls, ramping in), the ball end mill T2 finishes in lines across. The block turns into the part with its "
     "pocket, rounded boss and dome; the stock under the overhanging cap and in the hole stays.",
     where="4 Motion > Milling > Make a toolpath", animation="Toolpath", at=0.75, play=True, since="0.2.55",
     check=_check_toolpath, auto="clip")
stop("chips", MACH, "mill", "Chips fly",
     "While the bit cuts the slot, aluminium-coloured chips fly out and land on the table, the clamps and the block.",
     where="4 Motion > Milling > Chips", animation="Mill a slot", play=True, check=_check_chips, auto="clip", since="0.2.47", changed="0.2.101")
stop("air", MACH, "air", "Air blast",
     "The bit cuts a pocket with air on (M7 … M9): chips are blown away from the cut; at the end the part is "
     "blown clean.", where="4 Motion > CNC machine > Air blast", animation="Pocket with air", at=0.6, play=True,
     check=_check_air, auto="clip", since="0.2.47")

stop("coolant", MACH, "coolant", "Coolant (flood)",
     "The bit cuts a pocket with flood coolant (M8 … M9): two blue hoses squirt milky coolant at the tool, drops "
     "fly off it, the block gets a wet sheen; after M9 it dries.", where="4 Motion > CNC machine > Coolant",
     animation="Pocket with coolant", at=0.5, play=True, check=_check_coolant, auto="clip", since="0.2.48")


def _check_setup(scene):
    """The Set-up window's steps (task 0062): both set-ups are there and stand on this machine's state."""
    import bpy

    from . import ui_setup
    _check({"CNC", "MECH"} <= set(ui_setup.SETUPS),         # (task 0203 added the crane set-ups)
           "the Set-up window does not have the CNC mill and the mechanism")
    n_cnc, n_mech = len(ui_setup.SETUPS["CNC"][1]), len(ui_setup.SETUPS["MECH"][1])
    _check(n_cnc == 5 and n_mech == 4, f"the set-ups have {n_cnc} and {n_mech} steps (5 and 4 expected)")
    kind, step, steps = ui_setup.current(scene)
    _check(kind == "CNC" and step == 0 and len(steps) == 5, f"the stop does not open the CNC mill's first step ({kind} {step})")
    for name in ("setup_window", "setup_go"):
        _check(hasattr(bpy.ops.fresing, name), f"the operator fresing.{name} is missing")
    cnc = scene.fresing.cnc
    _check(bool(cnc.x_joint and cnc.y_joint and cnc.z_joint), "the gantry's axes are not set up: step 1 has nothing to show")
    return f"CNC mill {n_cnc} steps, mechanism {n_mech} steps"


def _setup_first_step(scene):
    s = scene.fresing
    s.setup_kind = "CNC"
    s.setup_step = 0
    scene["fr_setup_of"] = "CNC"


stop("setup", MACH, "gantry", "Set-up window: step by step",
     "Press Set-up window… (in Make at the top of the Fresing tab, or in 4 Motion > CNC machine): a small window of "
     "its own opens with 'Set up a CNC mill', step 1 of 5 – the axes X, Y and Z, already picked on this machine (a "
     "green tick). Next goes through the spindle, the tool and the workpiece, the work zero and the G-code program; "
     "the buttons are the same as in the side panel. Drag the window anywhere, also onto a second screen, and click "
     "parts in the main window while it is open. The drop-down at its top switches to 'Set up a mechanism'.",
     where="Make > Set-up window…; 4 Motion > CNC machine; 4 Motion > Mechanisms", since="0.2.152",
     animation="G-code", check=_check_setup, setup=_setup_first_step, auto=lambda ctx, scene, st: "")

stop("still", OUT, HUB_SET, "Still picture",
     "The crane in the Product studio look from the tour's camera, the tour logo bottom right. Render picture (F12) makes it in full quality.",
     where="5 Scene & Render > Image size & render", check=_check_still, since="0.2.47", changed="0.2.50")
stop("blur", OUT, HUB_SET, "Camera views and blur",
     "A long lens close on the crane; the trolley is sharp, the background softly blurred (in the camera view and "
     "the rendered picture).", where="5 Scene & Render > Camera", check=_check_blur, since="0.2.47")
stop("turntable", OUT, HUB_SET, "Turntable video",
     "The camera goes once round the crane in 4 seconds, at the same height.", where="5 Scene & Render > "
     "Turntable video", animation="Turntable", play=True, check=_check_turntable, auto="clip", since="0.2.47")
stop("finishing", OUT, HUB_SET, "Finished video: cards, captions",
     "The animation 'Finished video' has a title card, an end card, a caption 'The boom goes up', the tour logo "
     "and a TEST TOUR watermark. They are put on in the rendered MP4 video: render it with the queue (Render queue stop).",
     where=f"{places.where('finishing')}; {places.where('brand')}", animation="Finished video",
     check=_check_finishing, since="0.2.47", changed="0.2.152")
stop("labels", OUT, HUB_SET, "Labels with lines",
     "Two labels, 'Boom' and 'Trolley', with lines to their parts. Labels are drawn in rendered pictures and "
     "videos: press Render picture to see them.", where=places.where("labels"), check=_check_labels,
     setup=_labels_on, since="0.2.47", changed="0.2.152")
stop("queue", OUT, HUB_SET, "Render queue: picture + video",
     "7 Render queue holds a picture and a short video, both waiting. Start queue renders them in the background "
     "while you keep working; the finished files open from the list.", where="7 Render queue",
     check=_check_queue, since="0.2.47")
stop("startlater", OUT, HUB_SET, "Render queue: start later",
     "Under the queue's list, Start later with 'In …' (hours and minutes) or 'At …' (a clock time). Click it: the panel "
     "shows 'Starts in … - at …' with Start now and Cancel. Click Cancel. The app must stay open for a delayed start.",
     where="7 Render queue > Start later", check=_check_start_later, since="0.2.49")
stop("schemes", OUT, HUB_SET, "Render queue: every paint scheme",
     "7 Render queue > Every paint scheme lists the schemes 'Factory colours' and 'Blue', both ticked. Animation "
     "queues the selected animation once per ticked scheme (files named after the scheme); Current view does the same "
     "for a picture. Your own colours stay as they are.",
     where="7 Render queue > Every paint scheme", check=_check_schemes, since="0.2.60")
stop("shapes", OUT, HUB_SET, "Upright 9:16 and square 1:1",
     "The camera frame is upright (9:16, for phones). Switch Shape to 1:1 to see the square frame.",
     where="5 Scene & Render > Image size & render (Shape)", check=_check_shapes, since="0.2.47")


def _check_web3d(scene):
    """Web 3D model (task 0099): export the crane next to the tour (512 px, quick) and read the file back."""
    import tempfile

    from ..core import web3d as core
    from . import web3d
    folder, version = tour_of_file(scene)
    out_dir = files_dir(folder, version) if folder else tempfile.mkdtemp(prefix="fr_tour_web3d_")
    os.makedirs(out_dir, exist_ok=True)
    scene.fresing.web3d.texture_size = "512"
    out = web3d.export(scene, os.path.join(out_dir, "Crane web 3D.glb"), size=512)
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file is not valid glTF: {bad[:1]}")
    info = core.summary(data)
    _check(info["parts"] == out["parts"] > 0, f"{info['parts']} parts in the file, {out['parts']} shown")
    _check(os.path.exists(out["html"]), "the viewer page was not written")
    w = scene.fresing.web3d                              # task 0165: Marine detail starts at Normal (the crane has no marine look)
    _check(w.marine_detail == "NORMAL" and web3d.marine_estimate(scene) is None, "Marine detail is not Normal")
    _check(info["names"][1:3] == ["Part 1", "Part 2"], "the part names are not hidden")
    from ..core import web3d_env as env                 # task 0134: the player is in the page, with the saved views
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    _check(st.get("plain") and isinstance(st.get("views"), list), "the page has no player settings or no views")
    from ..core import web3d_faces as wf                # task 0135: the faces for measuring (the boom pin Ø40)
    faces = wf.read(data)
    _check(faces and out.get("face_bytes", 0) > 0, "the file has no faces for measuring")
    _check("fr_tools" in open(out["html"], encoding="utf-8").read() or "partTools" in
           open(out["html"], encoding="utf-8").read(), "the page has no part tools")
    return (f"{out['text']}; the page: {os.path.basename(out['html'])} (Open page in the panel); "
            f"{len(st['views'])} saved views; faces for measuring in {len(faces)} meshes")


def _check_web3d_env(scene):
    """Web 3D model with surroundings (task 0106): export the crane on the deck with the sea, vessel motion, sky,
    haze and rain next to the tour and read the page's settings back."""
    import tempfile

    from ..core import web3d as core
    from ..core import web3d_env as env
    from . import web3d, web3d_env
    folder, version = tour_of_file(scene)
    out_dir = files_dir(folder, version) if folder else tempfile.mkdtemp(prefix="fr_tour_web3d_env_")
    os.makedirs(out_dir, exist_ok=True)
    ch = web3d_env.choice(scene)
    _check(ch is not None and ch["sea"] and ch["vessel"], "Surroundings on the page is not 'As in the project' "
                                                          "with the sea and vessel motion")
    out = web3d.export(scene, os.path.join(out_dir, "Crane at sea web 3D.glb"), size=512, surroundings=ch)
    with open(out["path"], "rb") as fh:
        bad = core.problems(fh.read())
    _check(not bad, f"the file is not valid glTF: {bad[:1]}")
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    _check(st["sea"] and st["vessel"] and st["haze"] and st["rain"], "the page lacks the sea, the motion, haze or rain")
    _check(st["sea"]["state"] == scene.fresing.sea_state, "the page's sea is not the project's")
    return f"{out['text']}; on the page: {out.get('env_items', '')} (Open page in the panel)"


def _check_web3d_light(scene):
    """Web 3D model with baked light (task 0107): the crane with Soft light baked, sun live (Draft, few samples, so
    the tour stays quick), read back: every shown part carries its own baked light."""
    import tempfile

    from ..core import web3d as core
    from ..core import web3d_env as env
    from . import web3d
    folder, version = tour_of_file(scene)
    out_dir = files_dir(folder, version) if folder else tempfile.mkdtemp(prefix="fr_tour_web3d_light_")
    os.makedirs(out_dir, exist_ok=True)
    w = scene.fresing.web3d
    w.light, w.light_quality = "SOFT", "DRAFT"
    out = web3d.export(scene, os.path.join(out_dir, "Crane baked light web 3D.glb"), size=512, light="SOFT",
                       light_quality="DRAFT", light_samples=8)
    with open(out["path"], "rb") as fh:
        data = fh.read()
    bad = core.problems(data)
    _check(not bad, f"the file is not valid glTF: {bad[:1]}")
    doc, _bin = core.read_glb(data)
    lit = sum(1 for m in doc["meshes"] for p in m["primitives"][:1]
              if "TEXCOORD_1" in p["attributes"] or "_FR_LIGHT" in p["attributes"])
    _check(lit >= out["parts"] > 0, f"{lit} parts carry baked light, {out['parts']} are shown")
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    _check((st.get("light") or {}).get("light") == "SOFT", "the page does not use the baked light")
    return f"{out['text']} (Open page in the panel)"


def _check_demo(scene):
    """The demo project (task 0077): never made inside the tour (it takes minutes); read its summary if it is there."""
    from .. import __version__
    from . import demo
    folder = demo.default_folder()
    if not demo.exists(folder, __version__):
        return "No demo project for this version yet: Help > Make demo project first"
    info = demo.read_summary(folder, __version__)
    _check(info.get("joints", 0) >= demo.MIN_JOINTS,
           f"the demo project has {info.get('joints', 0)} joints, not {demo.MIN_JOINTS}")
    _check(120.0 <= info.get("seconds", 0) <= 200.0, f"its animation lasts {info.get('seconds', 0):.0f} s")
    with open(demo.project_path(folder, __version__), "rb") as fh:
        head = fh.read(7)
    _check(head == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd", "the demo project file is not a Blender file")
    return (f"demo project {__version__}: {info['joints']} joints, '{demo.ANIM}' {info['seconds']:.0f} s "
            f"({info['frames']} frames)")

stop("web3d", OUT, HUB_SET, "Web 3D model",
     "This stop saves the crane as a web 3D model next to the tour. Press Open page in 5 Scene & Render > Web 3D "
     "model: your web browser shows the crane on a light background with its colours and shine; drag to turn it, "
     "scroll to zoom. The page is one file and also works without internet. On the right: the gear opens the "
     "settings (quality, live pictures a second, your graphics card's name, auto-turn, sun), then Fullscreen, Reset "
     "view, Screenshot, Copy link, keys (?) and the eye that hides every control; bottom left one button per saved "
     "camera. A still crane draws nothing while you do not touch it. A red bar at the top only when the browser "
     "draws without the graphics card. On the left the part tools: Part info (click a part: a card with its group, "
     "and Round face Ø … for a pin or a hole), Measure (click the boom pin: Ø 40.0 mm; two flat faces: the distance "
     "between them), Cutaway (a slider cuts the crane, the cut faces red) and Fade the rest (click a part: the rest "
     "goes see-through).",
     where="5 Scene & Render > Web 3D model", since="0.2.77", shot="Tour view", check=_check_web3d, changed="0.2.131")

stop("web3d_env", OUT, "vessel", "Web 3D model with surroundings",
     "This stop saves the crane on the vessel deck as a web 3D model with its surroundings next to the tour. Press "
     "Open page in 5 Scene & Render > Web 3D model: your browser shows the crane on the deck on a moving calm sea "
     "under a sky with some clouds; the deck rolls gently with the waves, it rains lightly and the horizon is hazy; "
     "the sun's shadows move with the boom. Drag to turn, scroll to zoom. The fold Surroundings on the page shows "
     "what was picked.", where="5 Scene & Render > Web 3D model > Surroundings on the page", since="0.2.86",
     check=_check_web3d_env)

stop("web3d_light", OUT, HUB_SET, "Web 3D model with baked light",
     "This stop saves the crane as a web 3D model with Light: Soft light baked, sun live (Bake quality Draft, quick). "
     "Press Open page in 5 Scene & Render > Web 3D model: the crane has soft shadows under the boom and the cab, "
     "darker corners and inside edges, and a little coloured light bounced from the yellow parts; turn it – the "
     "sun's sharp shadows still move with the view as before. The fold Light shows the choice, the bake quality and "
     "the estimate.", where="5 Scene & Render > Web 3D model > Light", since="0.2.89", shot="Tour view",
     check=_check_web3d_light)
stop("house", OUT, "house", "House from House Planner",
     "The made-up sample house from House Planner on a summer evening: a low sun from the north-west, long warm "
     "shadows across the plot, the terrace in front. 5 Scene & Render > House from House Planner lists the seasons "
     "and moments (Preview shows each one) and the bake of the summer morning this tour made (Show in folder: "
     "sample-house.hpbake next to the tour, for House Planner).",
     where="File > Import > House Planner scene; 5 Scene & Render > House from House Planner", since="0.2.92",
     check=_check_house, changed="0.2.152")

def _check_workspace(scene):
    """Workspaces and the function families (task 0062): hide, show, lock and unlock – the project stays as it was."""
    import bpy

    from ..core import workspaces as W
    from . import lock, panels, workspaces
    s = scene.fresing
    was = (workspaces.name_of(scene), s.ws_data, s.ws_ticks)
    before = (len(scene.objects), len(s.joints), len(s.animations))
    state = {ob.name: (ob.hide_select, tuple(ob.lock_location)) for ob in scene.objects}
    try:
        workspaces.switch(scene, "CNC & machining")
        _check(workspaces.panel_hidden(scene, "FRESING_PT_cables") and not workspaces.panel_hidden(scene, "FRESING_PT_cnc"),
               "the workspace CNC & machining does not hide Cables and paths and show the CNC machine")
        workspaces.set_tick(scene, "milling", False)
        _check(not bpy.types.FRESING_PT_milling.poll(bpy.context), "Milling is still drawn after its family was ticked off")
        used = workspaces.in_use(scene)
        _check("motion" in used and "animation" in used, "the crane's joints and animations are not seen as in use")
        workspaces.switch(scene, "Client view")
        _check(lock.ON[0] and all(ob.hide_select for ob in scene.objects), "the Client view did not lock the parts")
        workspaces.switch(scene, "Full access")
        _check(not lock.ON[0] and lock.marked() == 0
               and state == {ob.name: (ob.hide_select, tuple(ob.lock_location)) for ob in scene.objects},
               "Full access did not put the parts back as they were")
    finally:
        s.ws_name, s.ws_data, s.ws_ticks = was
        workspaces.apply(scene)
    _check((len(scene.objects), len(s.joints), len(s.animations)) == before, "hiding or locking changed the project")
    _check(set(panels.SECTIONS) <= set(panels.PARENT), "the sections have no title rows of their own")
    return f"{len(W.BUILTIN)} workspaces, {len(W.tickable())} families; hidden, locked and back"


def _workspace_open(scene):
    from . import panels
    panels.set_open("FRESING_PT_workspace", True)


def _check_make(scene):
    """The Make list (task 0062): every output with its own settings panel, in the side panel and the view's header."""
    import bpy

    from . import ui_top
    outs = ui_top._outputs(scene)
    _check(len(outs) == len(ui_top.OUTPUTS) == 6, f"the Make list has {len(outs)} of 6 outputs")
    for _key, text, _icon, panel, _fid, op, _optext in outs:
        _check(hasattr(bpy.types, panel), f"Make > {text}: its settings panel is missing")
        _check(not op or hasattr(bpy.ops.fresing, op.split(".")[1]), f"Make > {text}: its button is missing")
    _check(ui_top._draw_view_header in bpy.types.VIEW3D_HT_header.draw._draw_funcs,
           "Make is not in the 3D view's header")
    return "6 outputs, each with its settings; also in the 3D view's header"


stop("workspace", OUT, HUB_SET, "Functions in this project",
     "The top row of the Fresing tab says 'All functions': the workspace. Its small arrow is open here: under "
     "'Functions in this project' every family of functions has a tick. Untick 'CNC machine' and 'Milling': their "
     "panels leave 4 Motion, the project stays as it is; tick them again and they are back. Pick 'Client view' in the "
     "list: only looking and rendering are left and no part can be clicked or deleted; pick 'All functions' again. "
     "Sections 1 to 7 start folded: click a title to open it, Ctrl+click keeps only that one open, the tabs "
     "All · 1 … 7 show one section at a time.",
     where="The Workspace row at the top of the Fresing tab", since="0.2.152", shot="Tour view",
     check=_check_workspace, setup=_workspace_open, auto=lambda ctx, scene, st: "")
stop("make", OUT, HUB_SET, "Make: every output side by side",
     "Above 1 Import is the Make list: Picture, Product video, Turntable, 3D page, Animation and Queue. Click "
     "Picture: the settings of 5 Scene & Render > Image size & render open right there, with a blue Render image "
     "button. The same list is under Make in the header of the 3D view, so it is there whatever the side panel shows.",
     where="Make, above 1 Import; Make in the 3D view's header", since="0.2.152", shot="Tour view", check=_check_make,
     auto=lambda ctx, scene, st: "")

stop("demo", OUT, HUB_SET, "Demo project: cable-lay vessel",
     "Help > Make demo project… makes an invented cable-lay vessel in the background (a few minutes on your PC; the "
     "status bar shows how far). Then Help > Open demo project: the vessel on the open sea, 4 Motion lists 432 joints "
     "(324 on the vessel, 108 on the quay), 5 Scene & Render has the saved scene 'Loading at the quay' and the saved "
     "cameras 'Stern thrusters' (under water: two azimuth thrusters, their propellers in nozzles) and 'Hull side' (the "
     "bow with its name, draft marks and the black boot top), and 6 Animation > 'What it can do today' plays a video "
     "of about 2 ½ minutes (Build & play) in which the propellers and radars keep turning. This stop only checks that "
     "the demo is there.",
     where="Help menu (Make demo project…, Open demo project)", since="0.2.68", shot="Tour view", check=_check_demo,
     auto=lambda ctx, scene, st: "", changed="0.2.120")

def _check_panel_back(scene):
    """The header button and its operator (task 0198)."""
    import bpy

    from . import ui_header
    _check(hasattr(bpy.ops.fresing, "show_panel"), "the operator 'Show the Fresing panel' is missing")
    _check(ui_header._draw_header in bpy.types.VIEW3D_HT_header.draw._draw_funcs,
           "the Fresing button is not in the 3D view's header")
    return "the Fresing button and its operator are there"


stop("panel_back", OUT, HUB_SET, "Fresing panel always back",
     "Move the mouse over the 3D view and press N: the side panel goes away, and a small Fresing button appears at "
     "the right end of the 3D view's header. Click it: the side panel is back on the Fresing tab and the button "
     "disappears. Opening any project (this tour, the demo, your own) always shows the Fresing tab with Blender's "
     "toolbar folded. Live preview stays on or off as you left it when you go to another test tour project.",
     where="The 3D view's header (right end) while the side panel is hidden", since="0.2.150",
     shot="Tour view", check=_check_panel_back, auto=lambda ctx, scene, st: "")

def _check_start_here(scene):
    import bpy

    from ..core import functions, start
    from . import ui_topbar, welcome
    _check(ui_topbar._draw_in_editor_menus in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize(),
           "the Fresing menu is not in the top bar")
    for idname in ui_topbar.entries():
        if idname == "fresing.user_guide":
            continue                                   # the app template's (not there in a bare extension)
        _check(ui_topbar._has(idname), f"the Fresing menu's operator {idname} is missing")
    prev = welcome.previous_version()
    rows = start.new_functions(functions.FUNCTIONS, prev or "0.2.0", welcome.version())
    if not rows:            # (task 0202: a release that brings no new function – What's new can still list functions)
        rows = start.new_functions(functions.FUNCTIONS, "0.2.0", welcome.version())
    _check(bool(rows), "What's new lists no function")
    return f"the Fresing menu has {len(ui_topbar.entries())} entries; What's new since {prev or '-'} lists {len(rows)}"


stop("start_here", OUT, HUB_SET, "Start here: the Fresing menu",
     "At the top of the window, after Help, there is a menu Fresing: Take the test tour, What's new in this version, "
     "Show the Fresing panel, the demo project, the user guide, the PC check, Check for updates and the Welcome "
     "screen. What's new lists the new functions with Show in guide, and the new and changed test models with a tour "
     "of only those. In this Test tour panel new stops say \"New\" and changed ones \"Changed\" after an update.",
     where="The Fresing menu in the top bar (after Help)", since="0.2.155", shot="Tour view",
     check=_check_start_here, auto=lambda ctx, scene, st: "")

def _check_usage(scene):
    """The usage tracker (task 0181): its panel, buttons and menu lines, and its rules on a made-up state (the
    user's own usage file is never touched by the tour)."""
    import bpy

    from ..core import places
    from ..core import usage as core
    from . import ui_topbar
    _check(hasattr(bpy.types, "FRESING_PT_favourites"), "the favourites bar's panel is missing")
    for op in ("usage_go", "usage_pin", "usage_declutter", "usage_reset", "usage_clear", "usage_window",
               "usage_export", "usage_import"):
        _check(hasattr(bpy.ops.fresing, op), f"the button fresing.{op} is missing")
    _check("fresing.usage_window" in ui_topbar.entries(), "My usage… is not in the Fresing menu")
    s = core.fresh()
    for op, n in (("fresing.turntable", 5), ("fresing.render", 3), ("fresing.decal_add", 2)):
        for _ in range(n):
            core.count_click(s, op, core.function_for(op))
    core.start_session(s)
    _check(s["bar"]["order"] == ["scene.turntable", "scene.still", "looks.decals"],
           f"the bar of a made-up user is {s['bar']['order']}")
    s["sessions"] = core.THRESHOLD_DEFAULT
    panel = core.declutter_candidate(s, set(core.F.FUNCTIONS), set(), titles=set(places.PLACES))
    _check(bool(panel), "no unused panel is offered after 10 starts")
    return f"bar of 3 favourites; after 10 starts '{places.PLACES[panel][1]}' would be offered for hiding"


stop("usage", OUT, HUB_SET, "Favourites bar and My usage",
     "Fresing > My usage… (also at the end of Help) opens a window that says what the app counted on this PC – nothing "
     "is sent anywhere: your most used functions with a pin each, where your time goes per stage (bars), and the "
     "time saved, marked as an estimate with how it is worked out. Use a button a few times (for example Render image "
     "twice): at the next start of the app it is on the favourites bar under the Workspace row; a click on it opens "
     "its section and points at the button. After 10 starts a panel you never used gets one quiet question at the "
     "top: Hide / Not now / Don't ask again.",
     where="Fresing menu > My usage…; the favourites bar under the Workspace row", since="0.2.158",
     shot="Tour view", check=_check_usage, auto=lambda ctx, scene, st: "")

def _check_learn(scene):
    """Learn as you go (task 0208): its buttons, the menu line, and its rules on a made-up user (the user's own usage
    file is never touched by the tour)."""
    import bpy

    from ..core import learning as L
    from ..core import places
    from ..core import usage as core
    from . import ui_topbar
    for op in ("learn_show", "learn_add", "learn_add_new", "learn_done", "learn_remove", "learn_next", "learn_window"):
        _check(hasattr(bpy.ops.fresing, op), f"the button fresing.{op} is missing")
    _check("fresing.learn_window" in ui_topbar.entries(), "My learning list… is not in the Fresing menu")
    s = core.fresh()
    for _ in range(3):
        core.count_click(s, "fresing.turntable", core.function_for("fresing.turntable"), today="2026-11-01")
    s["sessions"] = core.THRESHOLD_DEFAULT
    panel = core.declutter_candidate(s, set(core.F.FUNCTIONS), set(), titles=set(places.PLACES))
    fid = L.target_of_panel(panel)
    _check(bool(fid), f"the question about '{panel}' has nothing to teach")
    _check(L.add(s, fid), "a function does not go on the learning list")
    got = []
    for day in ("2026-11-02", "2026-11-03", "2026-11-04"):
        got += core.count_click(s, "x", fid, today=day)
    _check(got == [fid] and L.find(s, fid)["done"], "a function used on 3 days is not ticked by itself")
    nxt = L.candidates(s, set(core.F.FUNCTIONS), set())
    _check(bool(nxt), "no 'next to learn' for a user of the turntable")
    return f"'{L.one_line(fid)}' taught, listed and ticked after 3 days; next to learn: '{L.one_line(nxt[0][0])}'"


stop("learn", OUT, HUB_SET, "Learn as you go",
     "An unused panel's question (after 10 starts) offers Show me in the guide, Show me in the test tour and Add to my "
     "learning list beside Hide it. Fresing > My learning list… shows the list: Guide, Tour, Done and a cross for each "
     "function, ticked by itself after you used it on 3 days. Right-click a button of any function > Add to my "
     "learning list. After an update, What's new has Add the new functions to my learning list. The What's next card "
     "may have one quiet line \"Next to learn: …\" with Learn and Not interested.",
     where="Fresing menu > My learning list…; the question at the top of the Fresing tab; the What's next card",
     since="0.2.160", shot="Tour view", check=_check_learn, auto=lambda ctx, scene, st: "")

# ---------------------------------------------------------------------------
# building the tour
# ---------------------------------------------------------------------------

def _fresh(models: tuple, out_folder: str):
    """A new empty project with the models imported (built-in sorting rules, Draft meshes)."""
    import bpy

    from . import prefs as fr_prefs
    from . import workspaces
    bpy.ops.wm.read_homefile(use_empty=True)
    workspaces.use_all(bpy.context.scene)        # a tour project shows what it teaches, whatever the user's default
    p = fr_prefs.get()
    saved = p.default_template if p else ""
    if p:
        p.default_template = ""
    try:
        scene = bpy.context.scene
        scene.fresing.out_folder = out_folder
        from ..importer.runner import is_mesh
        for m in models:
            if is_mesh(m):                  # a mesh model (task 0117)
                res = bpy.ops.fresing.import_mesh(filepath=m)
                if res != {"FINISHED"}:
                    raise RuntimeError(f"the import of {os.path.basename(m)} returned {res}: "
                                       f"{scene.fresing.last_message}")
                continue
            if not m.lower().endswith((".step", ".stp")):
                continue                    # (a house scene: the set's build imports it itself, task 0114)
            res = bpy.ops.fresing.import_step(filepath=m, quality="draft")
            if res != {"FINISHED"}:
                raise RuntimeError(f"the import of {os.path.basename(m)} returned {res}: "
                                   f"{scene.fresing.last_message}")
    finally:
        if p:
            p.default_template = saved
    return bpy.context.scene


def write_progress(folder: str, **data) -> None:
    from ..pccheck import core
    data.setdefault("pid", os.getpid())
    try:
        core.write_text(progress_path(folder), json.dumps(data))
    except OSError:
        pass


def read_progress(folder: str) -> dict:
    try:
        with open(progress_path(folder), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def build_all(folder: str, version: str = "", only: tuple = (), progress=None) -> dict:
    """Build every set's project into ``folder`` (the hub last, so it is the file left open). Returns
    {"hub": path, "files": {set id: path}, "seconds": {set id: s}, "errors": {set id: text}}."""
    import bpy

    from .. import __version__
    version = version or __version__
    os.makedirs(files_dir(folder, version), exist_ok=True)
    order = [k for k in SETS if k != HUB_SET] + [HUB_SET]
    if only:
        order = [k for k in order if k in only]
    out = {"hub": hub_path(folder, version), "files": {}, "seconds": {}, "errors": {}}
    renders = os.path.join(folder, "Renders")
    for i, set_id in enumerate(order):
        ts = SETS[set_id]
        if progress:
            progress(i, len(order), ts.title)
        t0 = time.time()
        try:
            scene = _fresh(ts.models, renders)
            ts.build(Build(scene, folder, version))
            scene = bpy.context.scene
            scene[TAG] = set_id
            scene[TAG_VERSION] = version
            scene.frame_set(scene.frame_start)
            path = set_path(folder, version, set_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
            out["files"][set_id] = path
        except Exception as exc:  # noqa: BLE001 - one set that fails leaves the others
            import traceback
            out["errors"][set_id] = f"{type(exc).__name__}: {exc}"
            print(f"Fresing Render test tour: '{ts.title}' failed: {exc}\n{traceback.format_exc()}", flush=True)
        out["seconds"][set_id] = round(time.time() - t0, 1)
    if progress:
        progress(len(order), len(order), "")
    return out


def ready_path(folder: str, version: str) -> str:
    """The project to open of a made tour: the hub, or – a tour of only the new and changed models (task 0199) – the
    first set that was made. '' when nothing is made."""
    hub = hub_path(folder, version)
    if os.path.isfile(hub):
        return hub
    for set_id in SETS:
        path = set_path(folder, version, set_id)
        if os.path.isfile(path):
            return path
    return ""


def made_sets(folder: str, version: str) -> list:
    """The ids of the sets whose project is there."""
    return [k for k in SETS if os.path.isfile(set_path(folder, version, k))]


def build_main(folder: str = "", only: tuple = ()) -> int:
    """Entry point of the background Blender ``launcher.py -- tourbuild [folder] [only=a,b]``: builds, writes
    progress. ``only``: the sets to make (What's new: the new and changed test models), () = all."""
    from .. import __version__
    folder = folder or default_folder()
    only = tuple(k for k in only if k in SETS)
    os.makedirs(folder, exist_ok=True)
    t0 = time.time()

    def progress(i, n, title):
        write_progress(folder, done=i, total=n, step=title, version=__version__, finished=False)
        print(f"[{i + 1}/{n}] {title} …" if title else "done", flush=True)

    out = build_all(folder, __version__, only=only, progress=progress)
    n = len(only) if only else len(SETS)
    write_progress(folder, done=n, total=n, version=__version__, finished=True,
                   hub=out["hub"] if HUB_SET in out["files"] else ready_path(folder, __version__),
                   errors=out["errors"], seconds=round(time.time() - t0, 1), only=list(only))
    print(f"Test tour built in {time.time() - t0:.0f} s: {out['hub']}", flush=True)
    for k, v in out["errors"].items():
        print(f"FAILED {k}: {v}", flush=True)
    return 0 if not out["errors"] else 1


# ---------------------------------------------------------------------------
# Go: set a stop up
# ---------------------------------------------------------------------------

def frame_for(scene, st: Stop) -> int:
    """The frame a stop shows: ``at`` along the animation (negative: the stop's own time, see _hand_time)."""
    if st.at < 0 and st.id == "hand":
        a = scene.fresing.animations.get(st.animation)
        fps = int(a.fps) if a else 25
        return int(1 + _hand_time(scene) * fps)
    return int(round(scene.frame_start + (scene.frame_end - scene.frame_start) * max(0.0, min(1.0, st.at))))


def panel_of(st: Stop) -> str:
    """The side-panel panel a stop's function lives in (from the function list), or ''."""
    from ..core import functions
    for f in functions.FUNCTIONS.values():
        if st.id in f.tour and f.panel.startswith("FRESING_PT_"):
            return f.panel
    return ""


def open_panel_of(st: Stop) -> str:
    """Open the stop's panel in the side panel and fold the other sections (the user need not look for it)."""
    from . import panels
    name = panel_of(st)
    if name not in panels.PARENT:
        return ""
    sec = panels.section_of(name)
    if sec:
        panels.only(sec)
    panels.open_to(name)
    return name


def apply(st: Stop, scene=None) -> list[str]:
    """Set the open tour project up for a stop: its saved scene, its animation built and at its frame, its parts
    selected. Returns warnings. Works in the background too (the automatic run)."""
    import bpy

    from . import animation, machining, states
    scene = scene or bpy.context.scene
    s = scene.fresing
    warnings: list[str] = []
    if st.animation:
        a = s.animations.get(st.animation)
        if a is None:
            return [f"the animation '{st.animation}' is missing"]
        s.animations_index = list(s.animations).index(a)
        if s.anim_baked != a.name:
            r = animation.bake(scene, a)
            warnings += r["warnings"]
        scene.frame_set(frame_for(scene, st))
    else:
        shot = shot_name(st)
        if s.shots.get(shot) is None:
            return [f"the saved scene '{shot}' is missing"]
        warnings += states.apply_shot(scene, shot)
        scene.frame_set(scene.frame_start)
    if len(s.callouts):
        s.callouts_on = False             # labels only on their own stop (they show in every render)
    try:                                  # task 0062: Go opens the stop's own panel and folds the other sections
        open_panel_of(st)
    except Exception as exc:  # noqa: BLE001 - the stop still opens
        warnings.append(f"side panel: {exc}")
    if st.setup is not None:
        st.setup(scene)
    if machining.is_active(scene):
        try:
            machining.update_if_needed(scene)
        except Exception as exc:  # noqa: BLE001 - the stop still opens
            warnings.append(f"milling: {exc}")
    if st.select:
        vl = bpy.context.view_layer
        for o in list(vl.objects.selected):
            o.select_set(False)
        first = None
        for name in st.select:
            try:
                ob = _ob(scene, name)
            except RuntimeError:
                continue
            ob.select_set(True)
            first = first or ob
        if first is not None:
            vl.objects.active = first
    try:
        bpy.context.view_layer.update()
    except Exception:  # noqa: BLE001
        pass
    return warnings


def show_in_ui(context, st: Stop) -> None:
    """In the app: the 3D view looks through the camera, the side panel shows the Fresing tab, play if asked."""
    import bpy
    screen = getattr(context, "screen", None) or (context.window.screen if context.window else None)
    if screen is None:
        return
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        if not space.show_region_ui:
            space.show_region_ui = True
        r3d = space.region_3d
        if r3d is not None and context.scene.camera is not None:
            r3d.view_perspective = "CAMERA"
        for region in area.regions:
            if region.type == "UI":
                try:
                    region.active_panel_category = "Fresing"
                except (AttributeError, TypeError):
                    pass
        area.tag_redraw()
    if st.play:
        try:
            with context.temp_override(screen=screen):
                if not context.screen.is_animation_playing:
                    bpy.ops.screen.animation_play()
        except Exception:  # noqa: BLE001 - playing is a nicety
            pass
    elif screen.is_animation_playing:
        try:
            bpy.ops.screen.animation_cancel(restore_frame=False)
        except Exception:  # noqa: BLE001
            pass


def open_set(folder: str, version: str, set_id: str) -> bool:
    """Open the project of a set (if it is not the open one). True when another file was opened."""
    import bpy
    path = set_path(folder, version, set_id)
    if bpy.data.filepath and os.path.normcase(os.path.abspath(bpy.data.filepath)) == os.path.normcase(path):
        return False
    if not os.path.isfile(path):
        raise RuntimeError(f"the tour project '{os.path.basename(path)}' is missing: make the test tour again "
                           "(Help > Make test tour project)")
    bpy.ops.wm.open_mainfile(filepath=path)
    return True
