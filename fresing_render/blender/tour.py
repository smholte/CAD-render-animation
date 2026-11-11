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
stop("cut_look", LOOK, "mill", "Cut faces and raw stock",
     "The steel block has dark mill scale outside; the walls and floor of the milled slot look freshly machined "
     "(bright steel).", where="4 Motion > Milling > Cut faces; 3 Looks (the block's group)",
     animation="Mill a slot", at=1.0, check=_check_cut_look)
stop("sea", LOOK, HUB_SET, "Surroundings: open sea",
     "The crane stands in the open sea with waves; the sky and the light come from the sea set-up.",
     where="5 Scene & Render > Background & surroundings", check=_check_sea)
stop("vessel", LOOK, "vessel", "Vessel motion at sea",
     "The crane stands on the vessel deck in a calm beam sea: deck, containers and crane roll gently (about ±1.5°, "
     "once in 11 s), pitch a little and rise and fall with the long waves while the boom goes up. The sea, the sky "
     "and the camera stay put.", where="5 Scene & Render > Vessel motion", since="0.2.61", animation=VESSEL_ANIM,
     at=0.5, play=True, check=_check_vessel, auto="clip")
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

stop("gcode", MACH, "gantry", "G-code program runs the machine",
     "The gantry runs a short program: lines, arcs, a tool change to T2 and drilling. The toolpath is drawn as a "
     "thin tube; the tool's tip follows it.", where="4 Motion > CNC machine; 6 Animation (Run G-code program)",
     animation="G-code", play=True, check=_check_gcode, auto="clip")
stop("tools", MACH, "tools", "Three tools with M6 and G43",
     "A Ø50 face mill faces a strip, a Ø10 end mill cuts a slot, a chamfer mill runs along its edge: three tools "
     "from the tool list, each in a BT30 holder, changed with M6 and measured with G43.",
     where="4 Motion > CNC machine > Tools", animation="Three tools", at=1.0, check=_check_tools, auto="clip")
stop("hand", MACH, "tools", "Tool change by hand (BT30)",
     "At a tool change the head goes up, a gloved hand takes the tool out by its BT30 holder and puts the next one "
     "in.", where="4 Motion > CNC machine > Tool changes (Manual, Show hand)", animation="Three tools",
     at=-1.0, check=_check_hand)
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
