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
    since: str = "0.2.47"
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


STOPS: list[Stop] = []
SETS: dict[str, TourSet] = {}


def stop(id: str, group: str, set: str, title: str, see: str, **kw) -> Stop:
    st = Stop(id, group, set, title, see, **kw)
    st.number = len(STOPS) + 1
    STOPS.append(st)
    return st


def tour_set(id: str, title: str, *models: str):
    def deco(fn):
        SETS[id] = TourSet(id, title, tuple(os.path.join(DATA, m) for m in models), fn)
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
    return joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], origin, direction, ref=pin, name="Boom")


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

@tour_set(HUB_SET, "Crane", "test_crane_a.step")
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
    g = s.groups.get("Colour #F9A800") or (s.groups[0] if len(s.groups) else None)
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
    return f"tip moved {moved * 1000:.0f} mm, {end} frames"


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
    return "title, end card, captions, logo"


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

@tour_set("looks", "Materials", "test_crane_a.step")
def build_materials(b: Build):
    from . import logic
    sc, s = b.scene, b.s
    _look("PRODUCT")
    picks = (("Welded frames", "cast_iron_painted", "", 0.6), ("Colour #F9A800", "paint_gloss", "RAL 1003", 0.6),
             ("Shafts", "steel_ground", "", 0.0), ("Colour #333333", "aluminium_anodized_black", "", 0.0),
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


@tour_set("faces", "Painted faces", "test_faces_a.step")
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


@tour_set("decals", "Logos and stickers", "test_decals_a.step")
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


@tour_set("marine", "Marine looks", "test_crane_a.step")
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


@tour_set("cutaway", "Cutaway", "test_crane_a.step")
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


@tour_set("mill", "Milling a slot", "test_mill.step")
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


@tour_set("cylinder", "Cylinder", "test_cylinder_a.step")
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


@tour_set("linkage", "Mechanisms", "test_linkage_a.step")
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


@tour_set("waycover", "Way cover", "test_waycover_b.step")
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


@tour_set("waycover2", "Two way covers", "test_waycover_c.step")
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


@tour_set("hoses", "Hoses and a cable", "test_flex_hoses_a.step")
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


@tour_set("chains", "Drag chains", "test_flex_chains_a.step")
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


@tour_set("cables", "Cable over sheaves", "test_paths_a.step")
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


@tour_set("spool", "Drum and carousel spooling", "test_spool.step")
def build_spool(b: Build):
    from . import spool
    sc = b.scene
    _look("PRODUCT")
    made = spool.set_up_test_model(sc)
    _check(made["animation"] == SPOOL_ANIM, f"the animation is called '{made['animation']}'")
    for name in made["spools"]:
        sp = spool.find(sc, name)
        _check(sp is not None and not sp.problem, f"'{name}': {sp.problem if sp is not None else 'missing'}")
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: spooling")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


SEA_ANIM = "Cable into the sea"


@tour_set("sea_cable", "Cable into the sea", "test_sea.step")
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
    cam = _camera(b, "ISO", "Tour view", lens=30.0)
    cam.matrix_world = paths_sea.view_matrix(sc, paths.find(sc, made["cable"]))
    shot = _shot(b, "Tour: into the sea")
    a = s.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


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


MOVING_ANIM = "Over the stern"


@tour_set("moving_cable", "A cable on a moving part", "test_moving.step")
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
    the stern, and after the let-go frame its start stays on the seabed while the block goes on; its length (start
    to its end on the seabed) is kept throughout."""
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
    drift = float(max(np.linalg.norm(p - starts[0]) for p in starts))
    went = float(max(np.linalg.norm(p - sheaves[0]) for p in sheaves))
    _check(tight < paths.TIGHT_TOL, f"the lift wire's free length changed by {tight * 1000:.1f} mm")
    _check(pay > 10.0, f"the winch paid out only {pay:.2f} m")
    _check(hangs[0] == "HORN" and hangs[-1] == "SHEAVE", f"the cable hangs from {hangs[0]} and then {hangs[-1]}")
    _check(max(totals) - min(totals) < 1e-3,
           f"the cable's length changed by {(max(totals) - min(totals)) * 1000:.1f} mm")
    _check(drift < 1e-3, f"the let-go start moved {drift * 1000:.1f} mm over the seabed")
    _check(went > 3.0, "the block did not go on after the let-go")
    return (f"the winch paid out {pay:.2f} m with the wire tight to {tight * 1000:.2f} mm; the cable left the horn "
            f"for the sheave, kept its length to {(max(totals) - min(totals)) * 1000:.2f} mm and its let-go start "
            f"stayed on the seabed to {drift * 1000:.2f} mm while the block went {went:.1f} m on")


TRACKS_ANIM = "Tracks"


@tour_set("tracks", "Tensioner tracks and a belt", "test_tracks.step")
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
    _check(drum[-1, 0] > 5.9 and car[-1, 0] > 5.9, "the cables did not pay out 6 m")
    _check(abs(drum[-1, 1]) > 30.0, f"the drum turned only {math.degrees(abs(drum[-1, 1])):.0f}°")
    _check(np.ptp(drum[:, 2]) > 0.1, "the level wind did not go along the drum")
    _check(abs(car[-1, 1]) > 6.0, f"the carousel turned only {math.degrees(abs(car[-1, 1])):.0f}°")
    _check(np.ptp(car[:, 2]) > 0.05, "the arm did not swing out with the layer")
    _check(off < 5e-4, f"a cable leaves its spool {off * 1000:.2f} mm off the circle of its layer")
    return (f"drum {math.degrees(abs(drum[-1, 1])) / 360.0:.1f} turns, level wind {np.ptp(drum[:, 2]) * 1000:.0f} mm, "
            f"carousel {math.degrees(abs(car[-1, 1])):.0f}°, arm {math.degrees(np.ptp(car[:, 2])):.1f}°; "
            f"leave points on their layer to {off * 1000:.2f} mm")


@tour_set("copies", "Two copies", "test_crane_a.step", "test_crane_a.step")
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


@tour_set("update", "Model update", "test_crane_a.step")
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


@tour_set("clash", "Clash check", "test_clash.step")
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


@tour_set("sequence", "Assembly sequence", "test_sequence.step")
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
    return f"{len(a.blocks)} steps, {animation.length_seconds(a):.0f} s without the cards"


@tour_set("productvideo", "Product video", "test_sequence.step")
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


@tour_set("gantry", "CNC gantry", "test_gantry.step")
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


@tour_set("atc", "Tool changer", "test_gantry.step")
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


@tour_set("doublearm", "Double-arm tool changer", "test_atc.step")
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


@tour_set("rotary4", "4th axis - rotary table", "test_4axis.step")
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


@tour_set("rotary5", "5th axis - trunnion", "test_5axis.step")
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


@tour_set("toolpath", "The app makes the toolpath", "test_toolpath.step")
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


@tour_set("tools", "Three tools and the hand", "test_mill.step")
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


@tour_set("marks", "Tool marks", "test_mill.step")
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


@tour_set("air", "Air blast", "test_mill.step")
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


@tour_set("coolant", "Coolant", "test_mill.step")
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


@tour_set("vessel", "Vessel motion", "test_crane_a.step")
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


@tour_set("weather", "Weather and time of day", "test_crane_a.step")
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


@tour_set("house", "House from House Planner", "sample-house.hpscene")
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


# ---------------------------------------------------------------------------
# the stops, in order (numbers follow this order)
# ---------------------------------------------------------------------------

LOOK, MOTION, MACH, OUT = GROUPS

stop("materials", LOOK, "looks", "Ready-made materials and Wear",
     "The crane in seven ready-made materials: yellow gloss paint and painted cast iron (both with Wear: in a "
     "rendered picture their sharp edges look worn and corners a little dirty), ground steel pin, black anodised "
     "trolley, rubber wheels, blue anodised cover, zinc flake bolts.",
     where="3 Looks: the material groups, Ready-made material…, Wear", check=_check_materials)
stop("faces", LOOK, "faces", "Painted faces",
     "The housing's two faces painted in CAD keep their own colours; one face of the cover is painted red by hand, "
     "the rest of the cover keeps its colour.", where="3 Looks > Paint faces", check=_check_faces)
stop("decals", LOOK, "decals", "Logos and stickers",
     "A yellow warning sticker and the text TEST TOUR lie flat on the panel; a 'hot surface' sticker is wrapped "
     "round the barrel.", where="3 Looks > Logos & stickers", check=_check_decals)
stop("cutaway", LOOK, "cutaway", "Cutaway: the pedestal opens up",
     "A cut slides in from the front and takes away the front half of the crane's pedestal and boom: the cut faces "
     "are red with hatch lines, the steel pin shows inside the fork. The other parts are not cut. Look in rendered "
     "view: the grey solid view shows the parts whole.", where="3 Looks > Cutaway; 6 Animation (Move joint step "
     "with the joint 'Cut 1')", since="0.2.64", animation=CUT_ANIM, at=1.0, play=True, check=_check_cutaway,
     auto="clip")
stop("cut_look", LOOK, "mill", "Cut faces and raw stock",
     "The steel block has dark mill scale outside; the walls and floor of the milled slot look freshly machined "
     "(bright steel).", where="4 Motion > Milling > Cut faces; 3 Looks (the block's group)",
     animation="Mill a slot", at=1.0, check=_check_cut_look)
stop("marine", LOOK, "marine", "Marine growth, streaks, concrete",
     "A yellow pile standing in water: dark green-brown growth with a ragged top just below the waterline, a "
     "greenish splash zone with thin rust streaks above it, clean yellow higher up. The grey wall behind has faint "
     "run-down streaks; the block in front is light grey concrete.",
     where="3 Looks: Ready-made material… (Marine paint, growth below the waterline; Marine paint, run-down "
           "streaks; Concrete)", since="0.2.94", check=_check_marine)
stop("sea", LOOK, HUB_SET, "Surroundings: open sea",
     "The crane stands in the open sea with waves; the sky and the light come from the sea set-up.",
     where="5 Scene & Render > Background & surroundings", check=_check_sea)
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
stop("night", LOOK, "weather", "Night shift",
     "The quay at night: a dark sky with stars and the moon, floodlights on masts light the crane, a damp sheen "
     "on the quay.", where="5 Scene & Render > Weather & time (Night shift)", since="0.2.88", check=_check_night)
stop("looks", LOOK, HUB_SET, "Light looks",
     "The Dark studio look: a dark background with rim lights. The other looks are one click each in 5 Scene & Render > Light look.",
     where="5 Scene & Render > Light look", check=_check_looks)

stop("joint", MOTION, HUB_SET, "Joint: the boom turns",
     "The boom turns up 35° about its pin and stops smoothly; everything on the boom goes with it.",
     where="4 Motion (joints); 6 Animation", animation="Boom up", play=True, select=("BOOM",), check=_check_boom,
     auto="clip")
stop("stack", MOTION, HUB_SET, "Stacked joints: boom + trolley",
     "The boom turns up while the trolley slides out along it: the two moves add up, the trolley stays on the "
     "boom.", where="4 Motion (the trolley's joint rides on the boom)", animation="Boom and trolley", play=True,
     select=("TROLLEY",), check=_check_stack, auto="clip")
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
     where="4 Motion > Poses & exploded views", check=_check_explode)
stop("cylinder", MOTION, "cylinder", "Cylinder: stroke drives the arm",
     "The rod comes out of the cylinder 150 mm and pushes the arm up; the rod's eye stays on its pin all the way.",
     where="4 Motion > Cylinders", animation="Stroke out", play=True, check=_check_cylinder, auto="clip")
stop("mechanism", MOTION, "linkage", "Mechanisms: scissor lift, crank",
     "The scissor lift rises to 1.5 m with every arm following; next to it the crank turns once and the piston "
     "slides back and forth.", where="4 Motion > Mechanisms", animation="Lift and crank", play=True,
     check=_check_linkage, auto="clip")
stop("waycover", MOTION, "waycover", "Way cover follows the axis",
     "The carriage slides 500 mm along X and back; the five cover sections telescope out and in with it, each by "
     "its own share.", where="4 Motion > Way covers", animation="X axis out and back", play=True,
     check=_check_waycover, auto="clip")
stop("waycover2", MOTION, "waycover2", "Two way covers on one axis",
     "A cover on each side of the carriage: as it slides 500 mm to the right the left cover opens and the right one "
     "closes, every section by its own share; the plates next to the carriage ride on it. And back.",
     where="4 Motion > Way covers", animation="Carriage across and back", play=True,
     check=_check_waycover_two, auto="clip")
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
     "towards the rim) and the arm swings out so its guide stays over the turn being paid out.",
     where="4 Motion > Drums and carousels", animation=SPOOL_ANIM, play=True, since="0.2.85", check=_check_spool,
     auto="clip")
stop("tracks", MOTION, "tracks", "Tensioner tracks and a belt",
     "Front, the tensioner: the cable runs through at 15 m/min and the pads of both tracks run round their sprockets "
     "with it – the pads that hold the cable move exactly as fast as the cable. The top track lifts 150 mm (its pads "
     "keep running) and comes back down to squeeze the cable 2 mm. Behind, a belt of separate links runs round three "
     "pulleys of different size; all wheels turn with the chain.",
     where="4 Motion > Tracks and belts", animation=TRACKS_ANIM, play=True, since="0.2.87", check=_check_tracks,
     auto="clip")
stop("sea_cable", MOTION, "sea_cable", "Cable into the sea",
     "The cable runs over the rollers and the horn at the stern and hangs in a curve down to the seabed 15 m below, "
     "seen through the cut-away behind the stern. It pays out at 60 m/min: its stripes run down the curve but stand "
     "still where it lies on the seabed, the seabed moves aft under the vessel, the touch-down stays 20 m behind the "
     "horn and the orange CPS set goes over the horn and down the curve on the cable.",
     where="4 Motion > Cables and paths > Into the sea", animation=SEA_ANIM, play=True, since="0.2.91",
     check=_check_sea_cable, auto="clip")
stop("moving_cable", MOTION, "moving_cable", "A cable on a moving part",
     "A trolley carries a block with a sheave aft along the gantry, over the stern; the hanger tilts and the block is "
     "lowered. The black cable end, clamped on the block, goes round the sheave and over the horn into the sea: "
     "once the sheave has gone past the horn the cable hangs from the sheave instead. Near the seabed the cable is "
     "let go: its end and its turn round the sheave stay on the seabed while the block is lifted away. The grey "
     "lift wire from the fairlead over the trolley's head sheave stays tight: its winch pays out as the trolley "
     "travels and the block goes down, and the head sheave turns with it.",
     where="4 Motion > Cables and paths (Winch keeps it tight, Let go here)", animation=MOVING_ANIM, play=True,
     since="0.2.95", check=_check_moving_cable, auto="clip")
stop("copies", MOTION, "copies", "Two copies of one STEP",
     "The test crane twice, side by side. The second one has its cover hidden; the first one keeps its cover.",
     where="1 Import (the same file twice); 2 Structure", check=_check_copies)
stop("update", MOTION, "update", "Model update A → B",
     "The crane is revision B: it has a new lamp on the boom (selected). The boom is still at 20° and the cover "
     "is still hidden: the work survived the update.", where="1 Import > Update model", select=("BOOM.LAMP",),
     check=_check_update)

stop("clash", MOTION, "clash", "Clash check: two arms meet",
     "Arm B turns into place, then arm A comes down onto it and runs 6 mm into it. 6 Animation > Clash check "
     "lists ARM.A × ARM.B, deepest 6.0 mm at the last frame; that row is clicked: both arms are selected and drawn "
     "red in the 3D view (their own colour stays in renders).", where="6 Animation > Clash check",
     since="0.2.53", animation="Arms meet", at=1.0, select=("ARM.A", "ARM.B"), check=_check_clash,
     setup=_clash_setup)

stop("sequence", MOTION, "sequence", "Assembly sequence",
     "The spindle unit comes apart part by part straight up: first the nut and the four bolts, then the pulley, the "
     "cover, the bearings, the spacer, the shaft and last the housing, each starting while the one before is still "
     "on its way; a thin blue line draws each part's path. Then it all comes back down in the reverse order and "
     "ends exactly where it was.", where="6 Animation (Add step > Assembly sequence)", since="0.2.79",
     animation=SEQUENCE_ANIM, at=0.5, play=True, check=lambda scene: check_sequence(scene), auto="clip")

stop("productvideo", MOTION, "productvideo", "One-click product video",
     "6 Animation > Make a product video made a whole film from the project: one turn round the machine, the "
     "spindle unit's joint swinging out and back with the camera watching it, then the unit taken apart part by part "
     "and put together again. Title and end card come at render time.", where="6 Animation > Make a product video",
     since="0.2.81", animation=PRODUCT_ANIM, at=0.5, play=True, check=lambda scene: check_product_video(scene),
     auto="clip")

stop("gcode", MACH, "gantry", "G-code program runs the machine",
     "The gantry runs a short program: lines, arcs, a tool change to T2 and drilling. The toolpath is drawn as a "
     "thin tube; the tool's tip follows it.", where="4 Motion > CNC machine; 6 Animation (Run G-code program)",
     animation="G-code", play=True, check=_check_gcode, auto="clip")
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
     where="4 Motion > CNC machine > Tools", animation="Three tools", at=1.0, check=_check_tools, auto="clip")
stop("hand", MACH, "tools", "Tool change by hand (BT30)",
     "At a tool change a gloved hand takes the tool out by its BT30 holder and puts the next one in; for a longer "
     "tool the spindle first rises by the difference, then comes down to the program.", where="4 Motion > CNC machine > Tool changes (Manual, Show hand)", animation="Three tools",
     at=-1.0, check=_check_hand)
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
     check=_check_atc, auto="clip")
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
     "While the bit cuts the slot, aluminium-coloured chips fly out and land on the table and the block.",
     where="4 Motion > Milling > Chips", animation="Mill a slot", play=True, check=_check_chips, auto="clip")
stop("air", MACH, "air", "Air blast",
     "The bit cuts a pocket with air on (M7 … M9): chips are blown away from the cut; at the end the part is "
     "blown clean.", where="4 Motion > CNC machine > Air blast", animation="Pocket with air", at=0.6, play=True,
     check=_check_air, auto="clip")

stop("coolant", MACH, "coolant", "Coolant (flood)",
     "The bit cuts a pocket with flood coolant (M8 … M9): two blue hoses squirt milky coolant at the tool, drops "
     "fly off it, the block gets a wet sheen; after M9 it dries.", where="4 Motion > CNC machine > Coolant",
     animation="Pocket with coolant", at=0.5, play=True, check=_check_coolant, auto="clip", since="0.2.48")

stop("still", OUT, HUB_SET, "Still picture",
     "The crane in the Product studio look from the tour's camera, the tour logo bottom right. Render picture (F12) makes it in full quality.",
     where="5 Scene & Render > Image size & render", check=_check_still)
stop("blur", OUT, HUB_SET, "Camera views and blur",
     "A long lens close on the crane; the trolley is sharp, the background softly blurred (in the camera view and "
     "the rendered picture).", where="5 Scene & Render > Camera", check=_check_blur)
stop("turntable", OUT, HUB_SET, "Turntable video",
     "The camera goes once round the crane in 4 seconds, at the same height.", where="5 Scene & Render > "
     "Turntable video", animation="Turntable", play=True, check=_check_turntable, auto="clip")
stop("finishing", OUT, HUB_SET, "Finished video: cards, captions",
     "The animation 'Finished video' has a title card, an end card, a caption 'The boom goes up', the tour logo "
     "and a TEST TOUR watermark. They are put on in the rendered MP4 video: render it with the queue (Render queue stop).",
     where="6 Animation > Video finishing; 5 Scene & Render > Brand kit", animation="Finished video",
     check=_check_finishing)
stop("labels", OUT, HUB_SET, "Labels with lines",
     "Two labels, 'Boom' and 'Trolley', with lines to their parts. Labels are drawn in rendered pictures and "
     "videos: press Render picture to see them.", where="5 Scene & Render > Labels", check=_check_labels,
     setup=_labels_on)
stop("queue", OUT, HUB_SET, "Render queue: picture + video",
     "7 Render queue holds a picture and a short video, both waiting. Start queue renders them in the background "
     "while you keep working; the finished files open from the list.", where="7 Render queue",
     check=_check_queue)
stop("startlater", OUT, HUB_SET, "Render queue: start later",
     "Under the queue's list, Start later with 'In …' (hours and minutes) or 'At …' (a clock time). Click it: the panel "
     "shows 'Starts in … - at …' with Start now and Cancel. Click Cancel. The app must stay open for a delayed start.",
     where="7 Render queue > Start later", check=_check_start_later)
stop("schemes", OUT, HUB_SET, "Render queue: every paint scheme",
     "7 Render queue > Every paint scheme lists the schemes 'Factory colours' and 'Blue', both ticked. Animation "
     "queues the selected animation once per ticked scheme (files named after the scheme); Current view does the same "
     "for a picture. Your own colours stay as they are.",
     where="7 Render queue > Every paint scheme", check=_check_schemes)
stop("shapes", OUT, HUB_SET, "Upright 9:16 and square 1:1",
     "The camera frame is upright (9:16, for phones). Switch Shape to 1:1 to see the square frame.",
     where="5 Scene & Render > Image size & render (Shape)", check=_check_shapes)


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
    _check(info["names"][1:3] == ["Part 1", "Part 2"], "the part names are not hidden")
    return f"{out['text']}; the page: {os.path.basename(out['html'])} (Open page in the panel)"


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
    _check(60.0 <= info.get("seconds", 0) <= 80.0, f"its animation lasts {info.get('seconds', 0):.0f} s")
    with open(demo.project_path(folder, __version__), "rb") as fh:
        head = fh.read(7)
    _check(head == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd", "the demo project file is not a Blender file")
    return (f"demo project {__version__}: {info['joints']} joints, '{demo.ANIM}' {info['seconds']:.0f} s "
            f"({info['frames']} frames)")

stop("web3d", OUT, HUB_SET, "Web 3D model",
     "This stop saves the crane as a web 3D model next to the tour. Press Open page in 5 Scene & Render > Web 3D "
     "model: your web browser shows the crane on a light background with its colours and shine; drag to turn it, "
     "scroll to zoom. The page is one file and also works without internet.",
     where="5 Scene & Render > Web 3D model", since="0.2.77", shot="Tour view", check=_check_web3d)

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
     "and moments (Preview shows each one) and the bake of the summer morning this tour made (Show in Explorer: "
     "sample-house.hpbake next to the tour, for House Planner).",
     where="File > Import > House Planner scene; 5 Scene & Render > House from House Planner", since="0.2.92",
     check=_check_house)

stop("demo", OUT, HUB_SET, "Demo project: cable-lay vessel",
     "Help > Make demo project… makes an invented cable-lay vessel in the background (a few minutes on your PC; the "
     "status bar shows how far). Then Help > Open demo project: the vessel on the open sea, 4 Motion lists 422 joints "
     "(314 on the vessel, 108 on the quay), 5 Scene & Render has the saved scene 'Loading at the quay', and 6 Animation "
     "> 'What it can do today' plays a video of about 75 s (Build & play). This stop only checks that the demo is "
     "there.",
     where="Help menu (Make demo project…, Open demo project)", since="0.2.68", shot="Tour view", check=_check_demo,
     auto=lambda ctx, scene, st: "")

# ---------------------------------------------------------------------------
# building the tour
# ---------------------------------------------------------------------------

def _fresh(models: tuple, out_folder: str):
    """A new empty project with the models imported (built-in sorting rules, Draft meshes)."""
    import bpy

    from . import prefs as fr_prefs
    bpy.ops.wm.read_homefile(use_empty=True)
    p = fr_prefs.get()
    saved = p.default_template if p else ""
    if p:
        p.default_template = ""
    try:
        scene = bpy.context.scene
        scene.fresing.out_folder = out_folder
        for m in models:
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


def build_main(folder: str = "") -> int:
    """Entry point of the background Blender ``launcher.py -- tourbuild [folder]``: builds, writes progress."""
    from .. import __version__
    folder = folder or default_folder()
    os.makedirs(folder, exist_ok=True)
    t0 = time.time()

    def progress(i, n, title):
        write_progress(folder, done=i, total=n, step=title, version=__version__, finished=False)
        print(f"[{i + 1}/{n}] {title} …" if title else "done", flush=True)

    out = build_all(folder, __version__, progress=progress)
    write_progress(folder, done=len(SETS), total=len(SETS), version=__version__, finished=True,
                   hub=out["hub"] if HUB_SET in out["files"] else "", errors=out["errors"],
                   seconds=round(time.time() - t0, 1))
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
