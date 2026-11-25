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
    out = [f"Fresing Render Learning hub {version} - {time.strftime('%Y-%m-%d %H:%M')}"]
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


def _surround(b: Build, kind: str) -> None:
    """Task 0233: the set's own surroundings (a hall, the quay, the warehouse), simple detail, made round the model
    as it stands now: call it after the set-up, before the camera is placed."""
    b.s.env_detail = "SIMPLE"
    b.s.background = kind
    _update()


def _studio(b: Build) -> None:
    """Task 0233: a clean studio for the looks and the product videos: the product light, a soft light-grey
    background; the floor stays "Shadow only", so the machine stands on an endless light ground with its shadow."""
    s = b.s
    _look("PRODUCT")
    s.background = "COLOR"
    s.background_color = (0.88, 0.89, 0.9)
    _update()


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


def _xyz(scene, names=(("Y", "Y.ASM", (0, 1, 0)), ("X", "X.ASM", (-1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1)))):
    """The three slide axes; on the test mill (task 0249: a VMC) also its two Y way covers, so the saddle never runs
    into them (``waycover.set_up_test_mill``)."""
    from mathutils import Vector

    from . import joints, waycover
    for name, asm, d in names:
        o = _ob(scene, asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    waycover.set_up_test_mill(scene)


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


def _mill_with_cnc(scene) -> None:
    """Milling cuts with the CNC machine's tool and workpiece (task 0223: a program through a block that stayed whole
    showed its path running through uncut material)."""
    from . import machining
    from ..core import machining as mcore
    _check(mcore.available(), "the Manifold library did not load: run Install.bat again")
    why = machining.use_cnc(scene)
    _check(not why, why)
    _hide_finished(scene)


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


# the test crane (tools/make_test_crane.py, task 0259: a service crane at real size), m
CRANE_PIVOT = (0.5, 1.5, 2.4)          # the boom pin's centre
CRANE_PIN_R = 0.05                     # the boom pin Ø100
CRANE_BOOM = 7.5                       # the boom's length from the pin
TROLLEY_RUN = 1.75                     # the trolley's run out along the boom in the tour's animations


def _boom_joint(scene):
    from mathutils import Vector

    from . import joints
    pin = _ob(scene, "BOOM.PIN")
    origin, direction, _desc = joints.axis_from_hit(pin, 0, Vector(CRANE_PIVOT) + Vector((0, 0, CRANE_PIN_R)),
                                                    Vector((0, 0, 1)))
    if direction.y > 0:              # + turns the boom up (along +Y it went down through the base: found by 0065)
        direction = -direction
    j = joints.create(scene, "ROTATE", [_ob(scene, "BOOM.ASM")], origin, direction, ref=pin, name="Boom")
    luff_cylinder(scene)
    return j


LUFF = "Luffing cylinder"
YELLOW = "Welded frames & structures #F9A800"       # the crane's yellow group: boom and pedestal (task 0122)
LUFF_ROD_EYE = (2.6, 1.5, 2.025)       # the rod eye's centre in the CAD pose, m (tools/make_test_crane.py luff_pins)
LUFF_PIN_HALF = 0.11                   # m: half a luffing pin's length (its axis from its head side)


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
        return m @ Vector((0, LUFF_PIN_HALF, 0)), (m.to_3x3() @ Vector((0, 1, 0))).normalized(), ob

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
    return _ob(scene, "BOOM").matrix_world @ Vector((CRANE_BOOM, 0, 0))


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


def _music(path: str) -> str:
    """A few seconds of a soft made-up chord as a WAV file (no one's music: the tour's own)."""
    import wave

    import numpy as np
    rate = 22050
    t = np.arange(rate * 4) / rate
    tone = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 277.2, 329.6)) / 3.0
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((tone * 9000).astype("<i2").tobytes())
    return path


# ---------------------------------------------------------------------------
# the sets (one project each) and their stops
# ---------------------------------------------------------------------------

# ----- the crane (the hub: the project the owner opens) -----

@tour_set(HUB_SET, "Crane", "test_crane_a.step", added="0.2.47", changed="0.2.256")
def build_crane(b: Build):
    """The crane lesson's steps first (``lessons/crane.py``: View, Show me and Build it yourself make the same
    project, task 0230), then the tour's own extra shots."""
    import bpy

    from . import animation, callouts, cameras, lesson, queue, turntable
    sc, s = b.scene, b.s
    lesson.run(sc, HUB_SET)
    _bake(sc, s.animations["Boom up"])           # the lesson's animation builds without a warning
    animation.clear_keys(sc)                     # the tour's project opens unbuilt: Go builds what a stop shows
    view = _camera(b, "ISO", "Tour view")
    _shot(b, "Tour view")
    s.animations["Boom up"].start_shot = "Tour view"
    s.env_detail = "SIMPLE"

    # Look: light looks
    s.background = "COLOR"
    _look("DARK")
    sc.camera = view
    _shot(b, "@looks")
    _look("PRODUCT")

    # Motion: joint, stack, exploded view
    a = _animation(b, "Boom and trolley", "Tour view")
    _joint_step(a, "Boom", 0.0, 3.0, math.radians(25))
    _joint_step(a, "Trolley", 0.0, 3.0, TROLLEY_RUN, slide=True)
    fade_and_trail(sc, _animation(b, FADE_ANIM, "Tour view"))
    camera_rides(sc, _animation(b, CAMERA_ANIM, "Tour view"))
    lead_set_up(sc, _animation(b, LEAD_ANIM, "Tour view"))    # task 0309: lead motions + every function
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
    card = a.cards.add()                         # a picture card in a corner and music under it (task 0230)
    card.path, card.name, card.start, card.duration, card.mode = logo, "Tour logo", 0.3, 1.0, "CORNER"
    a.music_on, a.music_file, a.music_fade_in, a.music_fade_out = True, _music(b.file("Tour music.wav")), 0.2, 0.5

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
LEAD_ANIM = "Every function"            # task 0309: Show every function of the crane's lead motions


def lead_set_up(scene, anim) -> None:
    """The crane's lead motions (task 0309): the lesson made 'Boom up and out' (two stages); here 'Boom up' and
    'Trolley out', and an animation made by Show every function (shared with the PC check)."""
    import math

    from ..core import lead_motions as core
    from . import lead_motions
    s = scene.fresing
    if s.lead_motions.get("Boom up") is None:
        lead_motions.add(scene, "Boom up", [core.Row("Boom", 0.0, math.radians(35))], seconds=3.0,
                         description="The boom goes up to 35°")
    if s.lead_motions.get("Trolley out") is None:
        lead_motions.add(scene, "Trolley out", [core.Row("Trolley", 0.0, TROLLEY_RUN, easing="LINEAR")], seconds=3.0)
    s.lead_index = 0
    anim.fin_captions = True
    lead_motions.show_every_function(scene, anim)


def _check_lead(scene):
    import bpy

    from ..core import lead_motions as core
    from . import animation, joints, lead_motions, ui_topbar
    s = scene.fresing
    _check(len(s.lead_motions) >= 3, f"only {len(s.lead_motions)} lead motions (Boom up and out, Boom up, Trolley out)")
    bad = [f"{lm.name}: {r.joint}" for lm in s.lead_motions for r in lm.rows if lead_motions.row_problem(scene, r)]
    _check(not bad, "rows that cannot move: " + ", ".join(bad))
    _check(ui_topbar._draw_in_editor_menus in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize(),
           "the top bar has no Lead motions button")
    a = s.animations.get(LEAD_ANIM)
    _check(a is not None and len(a.blocks) == 2 * len(s.lead_motions), "the animation 'Every function' is missing a step")
    b = a.blocks[0]
    lm = s.lead_motions[b.lead]
    f0, f1 = animation.frame_of(a, b.start), animation.frame_of(a, b.start + b.duration)
    scene.frame_set((f0 + f1) // 2)
    want = core.values(lead_motions.to_core(lm), core.step_position(0, 100, b.easing, ((f0 + f1) // 2 - f0) / (f1 - f0)))
    err = max(abs(joints.get_value(joints.find(scene, n)) - v) for n, v in want.items())
    _check(err < 1e-4, f"half way through '{b.lead}' the joints are {err:.5f} off what its slider gives")
    return f"{len(s.lead_motions)} lead motions; '{lm.name}' half way = its slider at 50 %"


def fade_and_trail(scene, a) -> None:
    """Fade, X-ray and trail (task 0073): the boom turns up while the trolley runs out; the cover turns X-ray, a line
    draws the trolley's path. Also used by the PC check line motion.fade."""
    from . import build, trails
    _joint_step(a, "Boom", 0.0, 3.0, math.radians(25), label="The boom goes up")
    _joint_step(a, "Trolley", 0.0, 3.0, TROLLEY_RUN, slide=True)
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
    t.color, t.thickness = (0.05, 0.85, 0.2), 0.04        # green: the crane is yellow


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
    _joint_step(a, "Trolley", 0.0, PATH_END, TROLLEY_RUN, slide=True)
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
    _check(moved > 2.5, f"the boom's tip moved only {moved * 1000:.0f} mm")
    off = luff_eye_off(scene)
    _check(off < 0.05, f"the luffing cylinder's rod eye is {off:.2f} mm off its pin under the boom")
    return f"tip moved {moved * 1000:.0f} mm, {end} frames; rod eye on its pin to {off:.3f} mm"


def luff_eye_off(scene) -> float:
    """How far (mm) the luffing cylinder's rod eye sits from the pin under the boom, square to the pin."""
    from mathutils import Vector
    _update()
    rod, pin = _ob(scene, "HYDRAULIC CYLINDER.ROD"), _ob(scene, "BOOM.LUFF.PIN")
    pr = pin.matrix_world @ Vector((0, LUFF_PIN_HALF, 0))
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
    pivot = Vector(CRANE_PIVOT)
    a, d = joints.get_value(jb), joints.get_value(jt)
    want = pivot + Matrix.Rotation(sign * a, 3, "Y") @ (cad - pivot + Vector((d, 0, 0)))
    err = (trolley.matrix_world.translation - want).length
    _check(abs(math.degrees(a) - 25) < 0.01 and abs(d - TROLLEY_RUN) < 1e-5,
           f"at the end the boom is at {math.degrees(a):.1f}° and the trolley at {d * 1000:.0f} mm")
    _check(err < 1e-3, f"the trolley is {err * 1000:.1f} mm off where boom + slide put it")
    return f"boom 25° + trolley {TROLLEY_RUN * 1000:.0f} mm"


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
    _check(moved > 1.5, f"the turntable camera moved only {moved * 1000:.0f} mm in half the video")
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
    import os
    cards = [c for c in a.cards if c.enabled and os.path.isfile(bpy_abspath(c.path))]
    _check(len(cards) == 1, f"{len(cards)} picture cards, not 1")
    _check(a.music_on and os.path.isfile(bpy_abspath(a.music_file)), "no music under the video")
    return "title, end card, captions, logo, Fresing logo watermark, a picture card, music"


def bpy_abspath(path: str) -> str:
    import bpy
    return bpy.path.abspath(path)


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

@tour_set("looks", "Materials", "test_crane_a.step", added="0.2.47", changed="0.2.245")
def build_materials(b: Build):
    from . import logic
    sc, s = b.scene, b.s
    _studio(b)
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
    # task 0233: the camera on the worn parts (their sharp edges and corners show Wear only close up)
    from . import build
    import numpy as np
    worn = [ob for g in s.groups if g.wear > 0.5 for ob in logic.parts_in_group(sc, g.name)]
    mn, mx = build.world_bounds(worn)
    pts = np.array([(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])])
    _camera(b, "ISO", "Tour view", lens=60.0, points=pts)
    _shot(b, "@materials")
    # task 0273: this project's materials – four on the short list (3 Looks, above Material)
    from ..core import material_files
    from . import material_picker
    for key in PICKER_LIST:
        material_picker.add_to_project(sc, material_files.builtin(key))
    s.groups_index = next((i for i, g in enumerate(s.groups) if g.name.startswith("Welded frames")), 0)
    _shot(b, "@material_picker")
    # task 0314: the blue covers adjusted – duller, dusty, a clear coat
    cov = next(g for g in s.groups if g.name.startswith("Covers"))
    for k, v in ADJUST.items():
        setattr(cov, "adj_" + k, v)


ADJUST = {"shine": -0.5, "dirt": 0.6, "coat": 0.8}


def _set_up_adjust(scene):
    s = scene.fresing
    s.groups_index = next((i for i, g in enumerate(s.groups) if g.name.startswith("Covers")), s.groups_index)


def _check_adjust(scene):
    """Task 0314: the Covers group's material has the node "FR adjust" with the stop's values; the picker draws its
    Adjust box for it."""
    import bpy

    from . import look_adjust, materials, ui_material_picker, ui_settings
    g = next(g for g in scene.fresing.groups if g.name.startswith("Covers"))
    mat = materials.group_material(g)
    n = look_adjust.node_of(mat)
    _check(n is not None, "the Covers' material has no FR adjust node")
    for k, v in ADJUST.items():
        got = n.inputs[look_adjust.label(k)].default_value
        _check(abs(got - v) < 1e-4, f"{look_adjust.label(k)} is {got:.2f}, not {v}")
    ui_material_picker.draw_adjust(ui_settings._Any(), bpy.context, g,
                                   ui_material_picker.MP.find(scene, ui_material_picker.MP.group_key(g)))
    return ", ".join(f"{look_adjust.label(k)} {v:+.1f}" for k, v in ADJUST.items())


PICKER_LIST = ("builtin:chrome", "preset:paint_5010", "builtin:knurl_diamond", "builtin:rubber_black")


def _check_picker(scene):
    """Task 0273: the short list and the Materials window's list (its draw, with a stand-in layout)."""
    import bpy

    from ..core import material_files
    from . import material_picker, ui_material_picker, ui_settings
    listed = [e for e, on, _u in material_picker.short_list(scene) if on]
    _check([e.key for e in listed] == list(PICKER_LIST), f"this project's list is {[e.key for e in listed]}")
    _check(all(e.picture for e in listed), "a material on the list has no picture")
    every = ui_material_picker.visible(bpy.context)
    _check(len(every) >= len(material_files.builtin_keys()), f"the window lists {len(every)} materials")
    ui_material_picker.draw_window(ui_settings._Any(), bpy.context)
    return f"{len(listed)} on this project's list, {len(every)} materials in the window"


def _check_materials(scene):
    s = scene.fresing
    worn = [g for g in s.groups if g.wear > 0.5]
    _check(worn, "no group has Wear")
    mats = {g.material for g in s.groups}
    _check(len(mats) >= 4, f"only {len(mats)} different materials")
    return f"{len(mats)} materials, Wear {worn[0].wear:.1f} on '{worn[0].name}'"


@tour_set("faces", "Painted faces", "test_faces_r.step", added="0.2.47", changed="0.2.239")
def build_faces(b: Build):
    import bpy

    from . import logic, ops_panels, welds
    sc, s = b.scene, b.s
    _studio(b)                                      # task 0235: a studio – the painted faces are the picture
    cover = _ob(sc, "COVER")
    logic.ensure_group(s, "Painted by hand (tour)")
    s.groups["Painted by hand (tour)"].material = "paint_gloss"
    s.groups["Painted by hand (tour)"].color = "RAL 3020"
    s.face_group = "Painted by hand (tour)"
    bpy.context.view_layer.objects.active = cover
    top = welds.face_at(cover, (0.2, 0.15, 0.006), (0, 0, 1))      # the sheet's top face (its number is not fixed)
    _check(top >= 0, "the cover's top face was not found")
    ops_panels.paint_click(bpy.context, cover, top)
    _camera(b, "ISO", "Tour view")
    _shot(b, "@faces")


def _check_faces(scene):
    from . import faces
    sets = faces.get_sets(_ob(scene, "HOUSING").data)
    _check(len(sets) == 2, f"the housing should have 2 painted faces from CAD, has {len(sets)}")
    _check(faces.groups_on(_ob(scene, "COVER")) == ["Painted by hand (tour)"], "the face painted by hand lost its paint")
    return "2 CAD faces, 1 by hand"


@tour_set("decals", "Logos and stickers", "test_decals_r.step", added="0.2.47", changed="0.2.239")
def build_decals(b: Build):
    from . import decals, welds
    sc = b.scene
    _look("PRODUCT")
    panel, barrel = _ob(sc, "PANEL"), _ob(sc, "BARREL")
    # task 0235: real size – a 1.2 x 0.8 m door panel and a 200 l drum; faces are found by where they lie
    top = welds.face_at(panel, (0.6, 0.4, 0.02), (0, 0, 1))
    side = _round_face(barrel)
    _check(top >= 0 and side >= 0, "the panel's top or the drum's round face was not found")
    warn = decals.add(panel, top, (0.90, 0.40, 0.02), (0, 0, 1), "STICKER", sticker="WARN_GENERAL")
    text = decals.add(panel, top, (0.30, 0.40, 0.02), (0, 0, 1), "TEXT", text="TEST TOUR")
    hot = decals.add(barrel, side, (0.207, -0.207, 0.45), (0.7071, -0.7071, 0), "STICKER", sticker="WARN_HOT")
    for it, w in ((warn, 0.28), (text, 0.40), (hot, 0.22)):     # sized for a panel and a drum seen across a hall
        it.width = w
        it.height = max(w * it.aspect, 0.01)
    _surround(b, "FACTORY")                         # task 0235: the machine hall, so the drums and the panel stand
    _camera(b, "ISO", "Tour view")                  # in a workshop
    _shot(b, "@decals")


def _round_face(ob) -> int:
    """The CAD face of a part that a decal wraps round (the biggest one that does), -1 if none."""
    from . import decals, faces
    n = len(faces.face_starts(decals.cad_mesh(ob))) - 1
    for f in range(max(n, 0)):
        if decals.wraps_round(ob, f):
            return f
    return -1


@tour_set("welds", "Welds", "test_weldment.step", added="0.2.231", changed="0.2.251")
def build_welds(b: Build):
    import bpy

    from . import build, welds
    sc = b.scene
    _look("PRODUCT")
    welds.set_up_test_model(sc)
    welds.settings(sc).symbols = True             # task 0320: the ISO 2553 symbols (view only)
    _camera(b, "ISO", "Tour view")
    _shot(b, "@welds")
    # task 0323: the Inventor-like CAD-weld frame beside it – its welds come in with the import
    have = set(build.model_roots(sc))
    res = bpy.ops.fresing.import_step(filepath=os.path.join(DATA, "test_weldment_cad_inventor.step"), quality="draft")
    _check(res == {"FINISHED"}, f"the CAD-weld frame's import returned {res}")
    root = next(r for r in build.model_roots(sc) if r not in have)
    root.matrix_basis.translation.y -= 0.45
    build.set_mat(root, build.PROP_REST_BASIS, root.matrix_basis)
    _update()
    _close_camera(b, (0.28, -0.30, 0.03), 0.42, "Tour CAD welds")
    _shot(b, "@welds_cad")


def _check_welds(scene):
    from . import welds
    own = [it for it in welds.items(scene) if not it.from_cad]      # (the CAD-weld frame beside it: stop welds_cad)
    st = {"welds": len(own), "seams": sum(1 for it in own for x in it.seams if x.enabled),
          "metres": sum(float(it.get("fr_length", 0.0)) for it in own), "lost": sum(1 for it in own if it.lost)}
    _check(st["welds"] == len(welds.TEST_WELDS), f"{st['welds']} welds, not {len(welds.TEST_WELDS)}")
    _check(st["lost"] == 0, f"{st['lost']} welds lost their faces")
    beads = sum(1 for it in own for o in welds.objects_of(it) if o.get("fr_kind") == welds.KIND)
    _check(beads == st["welds"], f"only {beads} of {st['welds']} welds have a bead")
    _check(2.0 < st["metres"] < 2.5, f"{st['metres']:.2f} m of bead, not about 2.2 m")
    from ..core import weld_symbols as core_symbols     # task 0320: the symbols are on, in the view only
    from . import weld_symbols
    s = welds.settings(scene)
    _check(s.symbols and not s.symbols_render, "the weld symbols are not on (view only)")
    texts = [core_symbols.one_line(weld_symbols.symbol_of(it, i + 1)) for i, it in enumerate(own)]
    _check(texts[0] == "a5 ◺/◸ 200 < 135", f"weld 1's symbol reads '{texts[0]}'")
    _check(sum(t.startswith("○") for t in texts) == 3, f"{sum(t.startswith('○') for t in texts)} all-round symbols, not 3")
    return f"{st['welds']} welds, {st['seams']} seams, {st['metres']:.2f} m of bead; symbols {', '.join(texts[:2])} …"


def _check_welds_cad(scene):
    """Task 0323: the Inventor-like frame's six beads became welds at its import, with their sizes."""
    from . import build, weld_cad, welds
    rows = sorted((r[1], r[2], round(r[3]), r[4]) for r in weld_cad.table(scene))
    want = sorted([("FILLET", 5.0, 200, False), ("FILLET", 4.0, 120, False), ("FILLET", 4.0, 189, True),
                   ("FILLET", 4.0, 240, True), ("FILLET", 4.0, 80, False), ("BUTT", 15.5, 300, False)])
    _check(len(rows) == 6, f"{len(rows)} welds from the CAD file, not 6")
    for got, exp in zip(rows, want):
        _check(got[0] == exp[0] and abs(got[1] - exp[1]) <= 0.5 and abs(got[2] - exp[2]) <= 1 and got[3] == exp[3],
               f"a weld from the CAD file reads {got}, not {exp}")
    cad = [it for it in welds.items(scene) if it.from_cad]
    _check(all(it.cad_shape and len(welds.objects_of(it)) == 2 for it in cad), "a CAD weld has no bead or heat zone")
    src = [o for o in build.iter_parts(scene) if o.get(weld_cad.SOURCE)]
    _check(len(src) == 1 and src[0].get(build.PROP_EXCLUDED), "the CAD welds part shows (it should be left out)")
    inter = next((it for it in cad if it.intermittent), None)
    _check(inter is not None, "the intermittent weld is not one weld")
    return "6 welds from the CAD file: " + ", ".join(f"{k.lower()} {s:g} mm" for k, s, _l, _c in rows[:3]) + " …"


WELDING = "Welding"
WELDING_SHOWS = ("FRESING_PT_welds", "FRESING_PT_looks", "FRESING_PT_import", "FRESING_PT_scene", "FRESING_PT_camera",
                 "FRESING_PT_output")
WELDING_HIDES = ("FRESING_PT_motion", "FRESING_PT_animation", "FRESING_PT_cnc", "FRESING_PT_cables",
                 "FRESING_PT_queue", "FRESING_PT_web3d")


def _welding_open(scene):
    """Task 0321: the stop switches the welds project to the workspace Welding, its Workspace row open."""
    from . import panels, workspaces
    workspaces.switch(scene, WELDING)
    panels.set_open("FRESING_PT_workspace", True)
    panels.set_open("FRESING_PT_welds", True)


def _check_workspace_welding(scene):
    """Workspaces round 3 (task 0321): Welding shows the welds and the render options, hides motion and the rest; the
    welds stay as they are."""
    from ..core import workspaces as W
    from . import lock, welds, workspaces
    before = welds.stats(scene)["welds"]
    if workspaces.name_of(scene) != WELDING:
        workspaces.switch(scene, WELDING)
    for p in WELDING_SHOWS:
        _check(not workspaces.panel_hidden(scene, p), f"Welding hides {p[11:]}")
    for p in WELDING_HIDES:
        _check(workspaces.panel_hidden(scene, p), f"Welding shows {p[11:]}")
    _check(not lock.ON[0], "Welding locks the project")
    _check(welds.stats(scene)["welds"] == before, "switching the workspace changed the welds")
    names = [n for n, _note, _own in workspaces.names()]
    for key in ("welding", "builder", "video", "houses"):
        _check(W.NAMES[key] in names, f"{W.NAMES[key]} is not in the Workspace list")
    n = len(workspaces._state(scene)[1])
    return f"Welding: {n} functions; the list has {len(names)} workspaces"


def _check_decals(scene):
    import bpy

    from . import decals
    shown = [o for o in bpy.data.objects if decals.is_decal(o)]
    _check(len(shown) >= 3, f"only {len(shown)} decals on the model")
    return f"{len(shown)} decals"


MARKS_ANIM = "Tool marks"


CUT_ANIM = "The pedestal opens up"
CUT_FROM = 1.0                  # the cut starts 1 m in front of the pedestal (nothing cut) and slides to the middle


def cutaway(scene, a=None):
    """Cutaway (task 0086): a plane cut through the crane's pedestal and boom, hatched, taking away the half that
    faces the camera; ``a``: a Move joint step slides it in from 1 m in front. Also used by the PC check line
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


# task 0234: the marine set stands a monopile with its transition piece in the open sea (12 m deep, 9 m of the pile in
# the seabed), the cut-away round it with the ground open: the pile is seen from its toe to the platform
OFFSHORE_DEPTH, OFFSHORE_EMBED = 12.0, 9.0      # water depth, the pile's length in the seabed (m)
OFFSHORE_TOP = 18.0                             # the transition piece's platform over the water (m)
OFFSHORE_PARTS = {           # name: (material id, colour, radius, z from, z to (m over the water), x, y) - cylinders
    "MONOPILE": ("paint_marine_growth", "RAL 1023", 2.5, -OFFSHORE_DEPTH - OFFSHORE_EMBED, 3.0, 0.0, 0.0),
    "TRANSITION PIECE": ("paint_marine_streaks", "RAL 1023", 2.75, 2.0, OFFSHORE_TOP, 0.0, 0.0),
    "BOAT LANDING PS": ("paint_marine_growth", "RAL 1023", 0.2, -3.0, 9.0, -3.25, 0.75),
    "BOAT LANDING SB": ("paint_marine_growth", "RAL 1023", 0.2, -3.0, 9.0, -3.25, -0.75),
    "PLATFORM": ("paint_marine_streaks", "RAL 7035", 5.0, OFFSHORE_TOP, OFFSHORE_TOP + 0.4, 0.0, 0.0),
}
OFFSHORE_MATTRESS = ("SCOUR MATTRESS", 7.0, 0.35)   # a concrete mattress round the pile on the seabed: half size, height


def offshore_structure(scene) -> dict:
    """Task 0234: a monopile and its transition piece (with a platform and a boat landing) and a concrete scour
    mattress, made as parts of the model so the sea is built round them (the test crane's own parts are left out);
    the water's surface at world z 0. Returns {part name: object}."""
    import bmesh
    import bpy

    from . import build, logic, materials
    root = build.model_roots(scene)[0]
    logic.exclude([ob for ob in root.children if ob.get(build.PROP_KIND) in ("part", "assembly")])
    made = {}

    def part(name, bm, mat_id, colour):
        me = bpy.data.meshes.new(f"Offshore {name}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"Offshore {name}", me)
        scene.collection.objects.link(ob)
        ob.parent = root
        ob.matrix_parent_inverse = root.matrix_world.inverted()
        ob[build.PROP_KIND], ob[build.PROP_NAME], ob[build.PROP_UID] = "part", name, f"offshore {name.lower()}"
        materials.assign(ob, materials.ensure_material(f"Offshore: {name.title()}", mat_id, colour))
        for poly in me.polygons:
            poly.use_smooth = len(poly.vertices) == 4
        made[name] = ob
    for name, (mat_id, colour, r, z0, z1, x, y) in OFFSHORE_PARTS.items():
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=48 if r > 1.0 else 16, radius1=r, radius2=r, depth=z1 - z0)
        bmesh.ops.translate(bm, vec=(x, y, (z0 + z1) / 2), verts=bm.verts)
        part(name, bm, mat_id, colour)
    name, half, h = OFFSHORE_MATTRESS
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(2 * half, 2 * half, h), verts=bm.verts)
    bmesh.ops.translate(bm, vec=(0.0, 0.0, -OFFSHORE_DEPTH + h / 2 - 0.05), verts=bm.verts)
    part(name, bm, "concrete", "")
    _update()
    return made


@tour_set("marine", "Marine looks", "test_crane_a.step", added="0.2.94", changed="0.2.203")
def build_marine(b: Build):
    """Task 0234: the marine looks on a monopile in the open sea (study 0224: the pile standing in the real sea with
    the sea cut-away, the waterline from the sea, the whole pile in frame)."""
    import numpy as np
    from mathutils import Vector

    from . import build, marine_looks
    sc, s = b.scene, b.s
    _look("PRODUCT")
    offshore_structure(sc)
    low = float(build.world_bounds(list(build.iter_parts(sc)))[0][2])
    s.background, s.env_detail, s.sea_state = "SEA", "SIMPLE", "CALM"
    s.sea_depth, s.sea_clarity = OFFSHORE_DEPTH, 12.0
    s.water_level = float(-low)                    # the water's surface at world z 0
    s.sea_cut_auto = False                         # the box from the pile's axis towards the camera (-x): the
    s.sea_cut_length, s.sea_cut_width = 36.0, 30.0  # pile stands in its far wall, its front seen down to the toe
    from . import surroundings
    mn, mx = surroundings._model_box(sc)
    s.sea_cut_start = float(mn[0])
    s.sea_cut_side = -float(mn[1] + mx[1]) / 2.0
    s.sea_cutaway = True                           # (the ground goes on by itself: the pile reaches into the seabed)
    _update()
    marine_looks.sync(sc)
    eye, at = Vector((-52.0, -24.0, 38.0)), Vector((0.0, 0.0, -3.0))
    cam = _camera(b, "ISO", "Tour marine", lens=24.0)
    cam.matrix_world = Matrix_look(eye, at)
    cam.data.clip_end = 2000.0
    _shot(b, "@marine")


def Matrix_look(eye, at):
    """A camera matrix at ``eye`` looking at ``at`` (up: +z)."""
    from mathutils import Matrix
    return Matrix.Translation(eye) @ (at - eye).to_track_quat("-Z", "Y").to_matrix().to_4x4()


def _check_marine(scene):
    """The monopile's growth below the sea's waterline and the transition piece's streaks, the concrete mattress on
    the seabed, the ground open in the cut-away, the whole pile (toe to platform) inside the picture."""
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from . import marine_looks, surroundings
    want = {"MONOPILE": "paint_marine_growth", "TRANSITION PIECE": "paint_marine_streaks",
            OFFSHORE_MATTRESS[0]: "concrete"}
    got = {n: bpy.data.objects.get(f"Offshore {n}") for n in want}
    _check(all(got.values()), f"missing: {', '.join(n for n, o in got.items() if o is None)}")
    for n, mat in want.items():
        _check(got[n].active_material is not None and got[n].active_material.get("fr_material") == mat,
               f"the {n.lower()} is not {mat}")
    _check(marine_looks.nodes_of(got["MONOPILE"].active_material), "the monopile's material has no marine growth")
    water = marine_looks.waterline(scene)
    sea = surroundings.waterline(scene)
    _check(sea is not None and abs(water - sea) < 1e-3, f"the growth's waterline {water:.2f} m is not the sea's")
    _check(abs(water) < 0.05, f"the sea's surface is at {water:.2f} m, not at the pile's 0")
    s = scene.fresing
    _check(s.sea_cutaway and s.sea_cut_ground, "the cut-away or its ground is off")
    cam = scene.camera
    ends = {"toe": Vector((0.0, 0.0, water - OFFSHORE_DEPTH - OFFSHORE_EMBED)),
            "platform": Vector((0.0, 0.0, water + OFFSHORE_TOP + 0.4))}
    for n, p in ends.items():
        v = world_to_camera_view(scene, cam, p)
        _check(0.02 < v.x < 0.98 and 0.02 < v.y < 0.98 and v.z > 0, f"the pile's {n} is outside the picture")
    return (f"growth below the waterline at {water:+.2f} m (the sea's), streaks, concrete; the pile from its toe "
            f"{OFFSHORE_DEPTH + OFFSHORE_EMBED:.0f} m down to the platform in the picture")


# task 0274: the finishes on the sample board of test_finishes.step (tools/make_test_finishes.py): part name -> (the
# library material, its colour); the headset shows the owner's photo of study 0270 (knurled knob, spun cap, moulded
# cross-hatch shell, soft-touch band, speaker cloth, leather cushions)
FINISH_BOARD = {
    "KNOB DIAMOND KNURL": ("knurl_diamond", ""), "KNOB STRAIGHT KNURL": ("knurl_straight", ""),
    "GRIP HANDLE": ("rubber_grip", "RAL 9005"), "CAP SPUN": ("spun", ""), "SHAFT FACED": ("faced", ""),
    "BUSHING HONED": ("honed", ""), "CUP CROSS-HATCH": ("crosshatch", "RAL 5010"),
    "DISC SPEAKER CLOTH": ("fabric", "RAL 7016"), "DISC GRILLE": ("grille", "RAL 9005"), "PLATE TREAD": ("tread", ""),
    "PLATE PERFORATED": ("perforated", ""), "PLATE EXPANDED": ("expanded", ""), "WAY SCRAPED": ("scraped", ""),
    "BAND SOFT-TOUCH": ("soft_touch", "RAL 7021"), "BLOCK BEAD-BLASTED": ("bead_blasted", ""),
    "BLOCK SHOT-BLASTED": ("shot_blasted", ""), "BLOCK HAMMERTONE": ("hammertone", "RAL 6011"),
    "BLOCK WRINKLE": ("wrinkle", "RAL 9005"), "PLATE ANTI-SKID": ("antiskid", "RAL 7040"),
    "CUP VDI 30": ("vdi", "RAL 7012"), "CUP LEATHER": ("leather", "RAL 8017"), "PLATE SPANGLE": ("spangle", ""),
    "BLOCK AS-CAST": ("as_cast", ""),
    "HEADSET BAND": ("soft_touch", "RAL 9005"), "HEADSET YOKE": ("bead_blasted", ""),
    "HEADSET CUP": ("crosshatch", "RAL 5010"), "HEADSET CUSHION": ("leather", "RAL 9005"),
    "HEADSET DISC": ("fabric", "RAL 9005"), "HEADSET CAP": ("spun", ""), "HEADSET KNOB": ("knurl_diamond", ""),
    # task 0318: carbon fibre on curved parts and folds, perlage, the Rust slider on six metals
    "CUP CARBON": ("carbon_fibre", ""), "TUBE CARBON": ("carbon_fibre", ""), "PANEL CARBON": ("carbon_fibre", ""),
    "HOOD CARBON": ("carbon_fibre", ""), "PLATE CARBON": ("carbon_fibre", ""), "DISC PERLAGE": ("perlage", ""),
    "PLATE RUST BARE STEEL": ("steel_raw", ""), "BLOCK RUST CAST IRON": ("cast_iron", ""),
    "BLOCK RUST PAINTED": ("paint_satin", "RAL 5010"), "BLOCK RUST GALVANIZED": ("galvanized", ""),
    "PLATE RUST STAINLESS": ("stainless_brushed", ""), "PLATE RUST ALUMINIUM": ("aluminium_machined", ""),
}
#: task 0318: the rust row's Wear and Rust (stainless and aluminium have no Rust slider: the value stays unused)
RUST_BOARD = {"PLATE RUST BARE STEEL": (0.0, 0.7), "BLOCK RUST CAST IRON": (0.3, 0.45), "BLOCK RUST PAINTED": (0.5, 0.8),
              "BLOCK RUST GALVANIZED": (0.4, 0.6), "PLATE RUST STAINLESS": (0.0, 0.8),
              "PLATE RUST ALUMINIUM": (0.0, 0.8)}
#: the carbon panel and hood show the plain weave, matte; the rest the 2x2 twill, glossy
CARBON_PLAIN = ("PANEL CARBON",)


def finishes_demo(scene) -> dict:
    """Task 0274: every part of the finishes test model in a group of its own with its finish (the board's 23 and the
    headset's). Returns {part name: group}. Used by the test tour and the PC check."""
    from . import build, logic
    s = scene.fresing
    by_name: dict = {}
    for ob in build.iter_parts(scene):
        by_name.setdefault(ob.get(build.PROP_NAME, ""), []).append(ob)
    groups = {}
    for name, (mat_id, colour) in FINISH_BOARD.items():
        obs = by_name.get(name)
        if not obs:
            continue
        group = f"Finish: {name.title()}"
        for ob in obs:
            ob["fr_group_manual"] = group
        logic.ensure_group(s, group)
        groups[name] = group
    logic.apply_rules(scene)
    for name, group in groups.items():
        g = s.groups[group]
        mat_id, colour = FINISH_BOARD[name]
        g.material = mat_id
        if colour:
            g.color = colour
        if name in RUST_BOARD:
            g.wear, g.rust = RUST_BOARD[name]
        if name in CARBON_PLAIN:
            g.fin_kind, g.fin_amount = "PLAIN", 0.0
    logic.refresh_group_materials(scene)
    from . import cameras
    cameras.update_pixel_angle(scene)
    return groups


@tour_set("finishes", "Finishes", "test_finishes.step", added="0.2.229", changed="0.2.237")
def build_finishes(b: Build):
    """Task 0274: the 23 finishes on the sample board and the headphone-like set, seen from the front; task 0318: the
    carbon fibre and perlage samples and the rust row in front of them."""
    sc = b.scene
    _look("PRODUCT")
    finishes_demo(sc)
    _camera(b, "HIGH", "Tour finishes", lens=50.0)
    _shot(b, "@finishes")


def _check_finishes(scene):
    """Every board part has its finish; the knurled knob carries the face data (round faces with a whole number of
    teeth, end faces on its axis); the fade's pixel angle follows the camera."""
    import numpy as np

    from ..core import finishes as fin_core
    from . import build, cameras, finishes
    parts = {ob.get(build.PROP_NAME, ""): ob for ob in build.iter_parts(scene)}
    missing = [n for n in FINISH_BOARD if n not in parts]
    _check(not missing, f"missing parts: {', '.join(missing)}")
    wrong = [n for n, (m, _c) in FINISH_BOARD.items()
             if parts[n].active_material is None or parts[n].active_material.get("fr_material") != m]
    _check(not wrong, f"without their finish: {', '.join(wrong)}")
    built = {parts[n].active_material.get(finishes.PROP_FINISH) for n in FINISH_BOARD} - {None}
    _check(len(built) == len(fin_core.FINISHES), f"{len(built)} finishes built, not {len(fin_core.FINISHES)}")
    # task 0318: the rust row rusts where it is logical, the carbon dome is a sphere, the tube has a closed ring
    from . import rust
    rusty = [n for n in RUST_BOARD if float(parts[n].active_material.get(rust.PROP, 0.0)) > 0]
    _check(sorted(rusty) == sorted(n for n in RUST_BOARD if "STAINLESS" not in n and "ALUMINIUM" not in n),
           f"rusty: {', '.join(rusty)}")
    cup = parts["CUP CARBON"].data
    kc = np.empty(len(cup.polygons), np.float32)
    cup.attributes["fr_fx_k"].data.foreach_get("value", kc)
    _check((np.abs(kc) == 3).any(), "the carbon cup's dome was not read as a sphere")
    knob = parts["KNOB DIAMOND KNURL"].data
    _check(finishes.has_faces(knob), "the knurled knob has no face data")
    k = np.empty(len(knob.polygons), np.float32)
    knob.attributes["fr_fx_k"].data.foreach_get("value", k)
    r = np.empty(len(knob.polygons), np.float32)
    knob.attributes["fr_fx_r"].data.foreach_get("value", r)
    _check((k == 1).any() and (k == 2).any(), "the knob's round face or end faces were not found")
    radius = float(np.median(r[k == 1]))
    _check(abs(radius - 0.010) < 0.0003, f"the knob's round face has radius {radius * 1000:.2f} mm, not 10")
    angle = scene.get(fin_core.PIXEL_PROP, 0.0)
    _check(abs(angle - cameras.pixel_angle(scene)) <= 0.011 * angle, "the fade's pixel angle is not the camera's")
    n = fin_core.teeth(radius, 0.0008, 30.0)
    return (f"{len(built)} finishes; knob Ø{radius * 2000:.1f} mm: {n} teeth round it; pixel angle {angle:.2e} rad; "
            f"{len(rusty)} rusty groups")


@tour_set("cutaway", "Slice", "test_crane_a.step", added="0.2.64", changed="0.2.203")
def build_cutaway(b: Build):
    from mathutils import Vector
    sc = b.scene
    _studio(b)
    ped = _ob(sc, "PEDESTAL")
    centre = sum((ped.matrix_world @ Vector(c) for c in ped.bound_box), Vector()) / 8.0
    _close_camera(b, centre + Vector((0.5, 0.0, 0.25)), 2.75, "Tour cutaway")
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


@tour_set("measure", "Measure", "test_crane_a.step", added="0.2.244")
def build_measure(b: Build):
    """Task 0322: the crane's base measured – its thickness, two bolt holes, a hole's Ø and, through a slice that takes
    the base's front half away, the cut face to the back face (``measure.set_up_test``, shared with the PC check).
    Show in renders is on here, so the tour's picture shows the labels too."""
    from mathutils import Vector

    from . import measure
    sc = b.scene
    _studio(b)
    measure.set_up_test(sc)
    measure.settings(sc).in_renders = True
    _close_camera(b, Vector((2.5, 1.5, 0.4)), 4.2, "Tour measure")
    _shot(b, "@measure")


def _check_measure(scene):
    import bpy

    from . import measure, ui_topbar
    rows = measure.check_test(scene)
    _check(len(rows) == 4, f"{len(rows)} of the 4 measurements are there")
    for name, got, want in rows:
        _check(got is not None, f"'{name}': a part it measures is gone")
        _check(abs(got - want) < 1e-5, f"'{name}' reads {got * 1000:.3f} mm, the base's drawing says {want * 1000:.2f} mm")
    _check(ui_topbar._draw_in_editor_menus in bpy.types.TOPBAR_MT_editor_menus._dyn_ui_initialize(),
           "the top bar has no Measure button")
    col = bpy.data.collections.get(measure.COLLECTION)
    _check(col is not None and sum(1 for o in col.objects if o.type == "FONT") == 4,
           "Show in renders is on but the labels are not in the picture")
    return "500.00 / 4 500.00 / Ø 33.00 / 1 500.00 mm, each within 0.01 mm"


@tour_set("mill", "Milling a slot", "test_mill.step", added="0.2.47", changed="0.2.262")
def build_mill(b: Build):
    """The mill lesson's steps (``lessons/mill.py``, task 0230): View, Show me and Build it yourself make the same
    project; the stops show what it made."""
    from . import lesson
    lesson.run(b.scene, "mill")
    mill_leads(b.scene)                          # task 0309: the table's two travels as lead motions
    b.scene.frame_set(b.scene.frame_start)


def mill_leads(scene) -> None:
    """The test mill's lead motions (task 0309): Table X travel and Table Y travel (the mill has no door)."""
    from ..core import lead_motions as core
    from . import lead_motions
    s = scene.fresing
    for name, joint, to in (("Table X travel", "X", 0.3), ("Table Y travel", "Y", 0.2)):
        if s.lead_motions.get(name) is None and s.joints.get(joint) is not None:
            lead_motions.add(scene, name, [core.Row(joint, 0.0, to, easing="SMOOTH")], seconds=3.0)


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


@tour_set("cylinder", "Cylinder", "test_cylinder_a.step", added="0.2.47", changed="0.2.211")
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
    barrel_pin, rod_pin = Vector((1.5, 0.24, 0.45)), Vector((2.4, 0.24, 1.35))
    joints.create(sc, "ROTATE", [_ob(sc, "ARM.ASM")], Vector((0.3, 0.6, 1.8)), along_y, name="Luff")
    c, _notes = cylinders.create(sc, [at_y("CYL.BARREL", 0.24)], [at_y("CYL.ROD", 0.24)],
                                 (barrel_pin, along_y, _ob(sc, "BASE.PIN")),
                                 (rod_pin, along_y, _ob(sc, "ARM.ROD.PIN")), name="Luff cylinder")
    _update()
    cylinders.set_mode(sc, c, "DRIVE")
    # the second cylinder and the telescopic one follow the arm (task 0067: left standing, the arm's pin tore through
    # their eyes)
    for barrel, rod, stage, y in (("CYL.BARREL", "CYL.ROD", "", 0.96), ("TELE.BARREL", "TELE.ROD", "TELE.STAGE", 0.6)):
        cylinders.create(sc, [at_y(barrel, y)], [at_y(rod, y)],
                         (Vector((1.5, y, 0.45)), along_y, _ob(sc, "BASE.PIN")),
                         (Vector((2.4, y, 1.35)), along_y, _ob(sc, "ARM.ROD.PIN")),
                         name=f"Follower {barrel.split('.')[0].lower()}", stages=[at_y(stage, y)] if stage else ())
    _update()
    _surround(b, "FACTORY")
    _camera(b, "FRONT", "Tour view")
    shot = _shot(b, "Tour: cylinder")
    a = _animation(b, "Stroke out", shot.name)
    blk = a.blocks.add()
    blk.kind, blk.cylinder, blk.start, blk.duration = "CYLINDER", c.name, 0.0, 3.0
    blk.use_from, blk.from_stroke, blk.to_stroke = False, 0.0, min(0.45, c.full_stroke)
    blk.name = "Stroke 0 → 450 mm"


def _check_cylinder(scene):
    from mathutils import Vector

    from . import build, cylinders, joints
    c = cylinders.find(scene, "Luff cylinder")
    _check(c is not None, "the cylinder is missing")
    arm = joints.find(scene, "Luff")
    eyes = [o for o in scene.objects if o.get(build.PROP_NAME) == "ROD.EYE"]
    eye = min(eyes, key=lambda o: abs(o.matrix_world.translation.y - 0.24))
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


@tour_set("linkage", "Mechanisms", "test_linkage_a.step", added="0.2.47", changed="0.2.213")
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
    crank = _ob(sc, "FOURBAR.CRANK.ASM")
    s3 = linkages.create(sc, "FOURBAR", [[_ob(sc, "FOURBAR.COUPLER.ASM")], [_ob(sc, "FOURBAR.ROCKER.ASM")], [crank]],
                         base=_ob(sc, "FOURBAR.BASE.ASM"), drive=crank, name="Four-bar")
    j3 = linkages.input_joint(sc, s3)
    _update()
    _update()
    # the lifting cylinder follows the bottom inner arm (task 0067: left standing, the arm's pin tore through its eye)
    along_y = Vector((0, 1, 0))
    cylinders.create(sc, [_ob(sc, "LIFT.CYL.BARREL")], [_ob(sc, "LIFT.CYL.ROD")],
                     (Vector((0.45, -0.08, 0.1)), along_y, _ob(sc, "LIFT.BASE.CYL.PIN")),
                     (Vector(LIFT_ROD_PIN), along_y, _ob(sc, "LIFT.CYL.PIN")), name="Lift cylinder")
    _update()
    _surround(b, "ASSEMBLY")
    from . import build
    import numpy as np
    mn, mx = build.world_bounds([o for o in sc.objects if o.get(build.PROP_NAME)])
    top = max(float(mx[2]), 1.65)             # task 0233: the scissor platform rises to 1.5 m: keep it in the frame
    pts = np.array([(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], top)])
    _camera(b, "FRONT", "Tour view", points=pts)
    shot = _shot(b, "Tour: mechanisms")
    a = _animation(b, "Lift and crank", shot.name)
    blk = a.blocks.add()
    blk.kind, blk.mechanism, blk.start, blk.duration = "MECHANISM", m.name, 0.0, 3.0
    blk.use_from, blk.to_height = True, 1.5
    blk.name = "Platform to 1.5 m"
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", j.name, 0.0, 3.0, "LINEAR"
    blk.use_from, blk.to_angle = True, math.radians(360)
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", j3.name, 0.0, 3.0, "LINEAR"
    blk.use_from, blk.to_angle = True, math.radians(360)


def _check_linkage(scene):
    from mathutils import Vector
    part = _ob(scene, "LIFT.PLATFORM.PIN")
    scene.frame_set(scene.frame_end)
    _update()
    _update()
    p = part.matrix_world @ Vector(part.data["fr_axes"][0:3])
    _check(abs(p.z - 1.6) < 1e-3, f"the platform's pin is at {p.z * 1000:.1f} mm, not 1600 mm")

    def pin(name):
        o = _ob(scene, name)
        q = o.matrix_world @ Vector(o.data["fr_axes"][0:3])
        return q.x, q.z

    # the four-bar: a full crank turn ends where it began, and the rocker swings in between
    c_end = pin("FOURBAR.ROCKER.PIN")
    scene.frame_set(scene.frame_start)
    _update()
    _update()
    c0 = pin("FOURBAR.ROCKER.PIN")
    _check(math.hypot(c_end[0] - c0[0], c_end[1] - c0[1]) < 1e-3,
           "the four-bar's rocker is not back where it began after one crank turn")
    scene.frame_set(round((scene.frame_start + scene.frame_end) / 2))
    _update()
    _update()
    cm, bm, dm = pin("FOURBAR.ROCKER.PIN"), pin("FOURBAR.CRANK.PIN"), pin("FOURBAR.COUPLER.PIN")
    swing = math.hypot(cm[0] - c0[0], cm[1] - c0[1])
    _check(swing > 0.01, f"the four-bar's rocker moved only {swing * 1000:.1f} mm")
    _check(math.hypot(dm[0] - cm[0], dm[1] - cm[1]) < 1e-3, "the coupler's pin left the rocker's")
    _check(abs(math.hypot(bm[0] - 2.0, bm[1] - 0.3) - 0.12) < 1e-3, "the crank's pin is not 120 mm from its centre")
    return f"platform at 1.5 m, four-bar rocker swings {swing * 1000:.0f} mm"


@tour_set("waycover", "Way cover", "test_waycover_b.step", added="0.2.47", changed="0.2.215")
def build_waycover(b: Build):
    from mathutils import Vector

    from . import joints, waycover
    sc = b.scene
    _look("PRODUCT")
    names = [["COVER.1.PLATE", "COVER.1.FLANGE"], ["COVER.2"], ["COVER.3.PLATE", "COVER.3.FLANGE"], ["COVER.4"],
             ["COVER.5"]]
    axis = joints.create(sc, "SLIDE", [_ob(sc, "CARRIAGE")], Vector((0.2, 0.3, 0.2)), Vector((1, 0, 0)),
                         name="X axis")
    axis.use_limits = True
    axis.slide_min, axis.slide_max = 0.0, waycover.TEST_TRAVEL
    c = waycover.settings(sc)
    c.axis, c.total = "X axis", waycover.TEST_TRAVEL
    for g in names:
        waycover.add_section(sc, [_ob(sc, n) for n in g])
    built, problems = waycover.make(sc)
    _check(built == 5 and not problems, f"the way cover was not made: {problems}")
    _surround(b, "ASSEMBLY")
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: way cover")
    a = _animation(b, "X axis out and back", shot.name)
    _joint_step(a, "X axis", 0.0, 2.0, waycover.TEST_TRAVEL, slide=True)
    _joint_step(a, "X axis", 2.5, 2.0, 0.0, slide=True)


@tour_set("waycover2", "Two way covers", "test_waycover_c.step", added="0.2.61", changed="0.2.215")
def build_waycover_two(b: Build):
    from . import waycover
    sc = b.scene
    _look("PRODUCT")
    waycover.set_up_test_model(sc, carriage=True)
    _surround(b, "ASSEMBLY")
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: two way covers")
    a = _animation(b, "Carriage across and back", shot.name)
    _joint_step(a, "X axis", 0.0, 2.0, waycover.TEST_TRAVEL, slide=True)
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
    _check(abs(mm[0] - 200) < 0.1 and abs(mm[1] - 800) < 0.1,
           f"the right cover's sections 1 and 4 moved {mm[0]:.1f} and {mm[1]:.1f} mm, not 200 and 800 mm")
    return "right cover closed: sections 200 … 1000 mm"


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
    _check(abs(mm - 1000) < 0.1, f"the last section moved {mm:.1f} mm, not 1000 mm")
    return "5 sections, the last 1000 mm"


# ---------------------------------------------------------------------------
# hoses, a cable and drag chains (task 0058)
# ---------------------------------------------------------------------------

HOSES_ANIM = "Arm up and down"
CHAINS_ANIM = "Program with drag chains"
CHAINS_PROGRAM = """(T1 D=6. CR=0. - flat end mill)
G21 G90 G94 G17
G0 X0 Y0 Z40
G1 X325 Y-200 Z15 F6000
G1 X-325 Y200 Z70
G2 X-225 Y200 I50 J0
G0 X0 Y0 Z40
M30
"""


def hoses_motion(a) -> None:
    """The steps of the hoses stop: the arm goes up 18° and down to -8° while the slide goes out and back."""
    _joint_step(a, "Luff", 0.0, 2.0, math.radians(18.0), label="Arm up 18°")
    _joint_step(a, "Slide", 0.5, 2.0, 0.36, slide=True, label="Slide out 360 mm")
    _joint_step(a, "Luff", 2.0, 2.0, math.radians(-8.0), label="Arm down to -8°")
    _joint_step(a, "Slide", 2.5, 1.5, -0.30, slide=True, label="Slide back 660 mm")


@tour_set("hoses", "Hoses and a cable", "test_flex_hoses_a.step", added="0.2.78", changed="0.2.211")
def build_hoses(b: Build):
    from . import flex
    sc = b.scene
    _look("PRODUCT")
    made = flex.set_up_test_hoses(sc)
    _check(len(made["items"]) == 4, f"only {len(made['items'])} of the 4 hoses were made")
    _update()
    _surround(b, "FACTORY")
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


AVOID_ANIM = "Lift down and up"
AVOID_VIA = (0.72, 0.24, 0.66)          # world m: the via point of the route stop, beside the block on the camera side


def avoid_motion(a) -> None:
    """The steps of the avoid stops: the lift goes down 400 mm (its fitting below the block's top) and up again."""
    _joint_step(a, "Lift", 0.0, 2.0, -0.4, slide=True, label="Lift down 400 mm")
    _joint_step(a, "Lift", 2.5, 1.5, 0.1, slide=True, label="Lift up 500 mm")


@tour_set("flex_avoid", "A hose avoids a block, a route shaped by hand", "test_flex_avoid_a.step", added="0.2.225",
          changed="0.2.225")
def build_flex_avoid(b: Build):
    """Task 0298: the hose of the avoid model (a block in its way, a lift that goes down) with Avoid other parts on."""
    from . import flex
    sc = b.scene
    _look("PRODUCT")
    made = flex.set_up_test_avoid(sc, avoid=True)
    _check(len(made["items"]) == 1, "the hose was not made")
    _update()
    _surround(b, "FACTORY")
    _camera(b, "FRONT", "Tour view")
    shot = _shot(b, "Tour: avoid")
    avoid_motion(_animation(b, AVOID_ANIM, shot.name))


def _avoid_hose(scene):
    from . import flex
    it = next((x for x in scene.fresing.flex if x.kind == "HOSE"), None)
    _check(it is not None, "the hose is missing")
    return it


def _route_off(scene) -> None:
    """The avoid stop shows the hose without via points (the route stop's one taken off again)."""
    from . import flex_route
    it = _avoid_hose(scene)
    if flex_route.count(it):
        flex_route.clear(scene, it)


def _route_on(scene) -> None:
    """The route stop: one via point beside the block, on the camera's side (once)."""
    import numpy as np

    from . import flex, flex_route
    it = _avoid_hose(scene)
    if not flex_route.count(it):
        flex.refresh(scene, force=True)
        line = flex.shape_now(scene, it)
        k = int(np.argmin(np.linalg.norm(line - np.array(AVOID_VIA), axis=1)))
        at, weight = flex_route.where_on(it, line, k)
        flex_route.add(scene, it, np.array(AVOID_VIA), at, weight)


def _avoid_over_frames(scene, fn):
    frames = sorted({scene.frame_start, scene.frame_end} |
                    {round(scene.frame_start + k * (scene.frame_end - scene.frame_start) / 10) for k in range(1, 10)})
    out = []
    for f in frames:
        scene.frame_set(f)
        _update()
        out.append(fn())
    return out


def check_flex_avoid(scene):
    """The hose stays out of the block at every frame looked at (its surface at most 2.5 mm in where it bends round
    an edge) and lies on it at the lowest point of the lift (its surface within 6 mm of the block's: the push of a
    part grows from nothing over a little of the clearance, so it rests a few mm above)."""
    from . import build, flex, flex_avoid
    from ..core import flex as fcore
    it = _avoid_hose(scene)
    _check(it.avoid, "'Avoid other parts' is off")
    block = next((o for o in scene.objects if o.get(build.PROP_NAME) == "BLOCK"), None)
    _check(block is not None, "the block is missing")
    _check(block.name in {o.name for o in flex_avoid.parts_for(scene, it)}, "the hose does not avoid the block")
    import numpy as np
    body = flex_avoid.body_of(block)

    def gap():
        inv = np.linalg.inv(flex_avoid._rigid(np.array(block.matrix_world)))
        pts = fcore.resample(flex.shape_now(scene, it), 400)
        return float(body.distance(pts @ inv[:3, :3].T + inv[:3, 3])[0].min()) - 0.5 * it.diameter
    gaps = _avoid_over_frames(scene, gap)
    worst = min(gaps)
    _check(worst > -0.0025, f"the hose goes {-worst * 1000:.1f} mm into the block")
    _check(worst < 0.006, f"the hose never comes down onto the block (nearest {worst * 1000:.1f} mm)")
    return f"the hose's surface stays within {max(-worst, 0.0) * 1000:.2f} mm of the block's at every frame looked at"


def check_flex_route(scene):
    """The hose runs through its via point at every frame looked at; the via point rides down with the lift."""
    import numpy as np

    from . import flex, flex_route
    it = _avoid_hose(scene)
    _check(flex_route.count(it) == 1, f"the hose has {flex_route.count(it)} via points, not 1")

    def miss():
        via = flex_route.stops_now(it)[1][0]
        return float(np.linalg.norm(flex.shape_now(scene, it) - via, axis=1).min()), via
    got = _avoid_over_frames(scene, miss)
    worst = max(m for m, _v in got)
    travel = max(float(np.linalg.norm(v - got[0][1])) for _m, v in got)
    _check(worst < 1e-4, f"the hose misses its via point by {worst * 1000:.2f} mm")
    _check(travel > 0.05, f"the via point moved only {travel * 1000:.0f} mm with the lift")
    return f"through its via point to {worst * 1000:.3f} mm; the via point rides {travel * 1000:.0f} mm with the lift"


@tour_set("chains", "Drag chains", "test_flex_chains_a.step", added="0.2.78", changed="0.2.215")
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
    _surround(b, "FACTORY")
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


@tour_set("cables", "Cable over sheaves", "test_paths_a.step", added="0.2.80", changed="0.2.230")
def build_cables(b: Build):
    from . import paths
    sc = b.scene
    _look("PRODUCT")
    made = paths.set_up_test_model(sc, winch=True)
    # task 0263: the rope starts on the winch drum's wire (a drum of Drums and carousels), then 5 things it touches
    _check(len(made["contacts"]) == 5, f"only {len(made['contacts'])} of the 5 things the rope touches were found")
    _check(made["animation"] == CABLE_ANIM, f"the animation is called '{made['animation']}'")
    _update()
    _surround(b, "WAREHOUSE")
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: cable")
    a = sc.fresing.animations[made["animation"]]
    a.start_shot = shot.name
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"


def _check_cables(scene):
    """Along the built animation: the rope lies on every wheel it bends round, the sheaves and rollers have turned
    exactly as far as the rope ran, the winch drum as far as that on its layer (task 0263: it winds the wire off
    layer by layer), and the rope follows the luffing A-frame."""
    import numpy as np

    from . import joints, paths, spool
    its = list(paths.items(scene))
    _check(len(its) == 1, "the cable is missing")
    it = its[0]
    _check(paths.status(scene, it)[1] == "OK", f"the cable says: {paths.status(scene, it)[0]}")
    cab = joints.find(scene, it.joint)
    _check(cab is not None, "the cable's speed joint is missing")
    sp = spool.of_cable(scene, it)
    _check(sp is not None and not sp.problem, "the rope does not start on the winch drum"
           if sp is None else f"the winch drum says: {sp.problem}")
    drum = joints.find(scene, sp.joint)
    drum0 = None
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
        drum0 = joints.get_value(drum) if drum0 is None else drum0
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
    turned = abs(joints.get_value(drum) - drum0)
    _check(pay > 0.9, f"only {pay:.2f} m of rope ran: the cable speed does not move it")
    _check(off < 5e-4, f"the rope is {off * 1000:.2f} mm off a sheave")
    _check(slip < 1e-3, f"a sheave or roller is {slip * 1000:.2f} mm behind the rope")
    _check(moved > 0.05, f"the rope moved only {moved * 1000:.0f} mm: it does not follow the A-frame")
    _check(turning == 4, f"{turning} of the 4 turning sheaves and rollers turn")
    # the drum: the rope comes off its 3rd layer (rope middle r 0.2536 m; on the 2nd 0.2328): pay / r radians
    _check(pay / 0.2536 - 0.05 < turned < pay / 0.2328 + 0.05,
           f"the winch drum turned {math.degrees(turned):.0f}° for {pay:.2f} m of rope")
    return (f"{len(it.contacts)} contacts, {pay:.2f} m of rope ran, the rope on its sheaves to {off * 1000:.2f} mm, "
            f"{turning} parts turning with it to {slip * 1000:.3f} mm, the winch drum {math.degrees(turned):.0f}°")


# ---------------------------------------------------------------------------
# hoses, a drag chain and a cable route drawn by clicking (task 0240)
# ---------------------------------------------------------------------------

DRAWN_ANIM = "Drawn hose, chain and cable"
DRAWN_CHAINS_AT = (0.0, -1.5, 0.9)              # the gantry beside the hoses model (m; task 0261: the arm x 3; task
                                                # 0262: the router x 2.5, its stand on the hoses model's floor)
DRAWN_PATHS_AT = (0.0, 2.5, 0.0)                # the cable model on the other side (task 0263: its base 1.9 m wide)
DRAWN_HOSE, DRAWN_CHAIN, DRAWN_CABLE = "Hose 1", "Drag chain 1", "Drawn rope"
#: task 0243: drawn hoses on the base's top behind the arm, past the rail's end (free of the CAD hoses and cable there), one
#: per kind, in three rows of two: each an arch between two ends 300 mm apart along X, looking up
KIND_ROW = ("HYDRAULIC", "BRAIDED", "PNEUMATIC", "SLEEVE", "MACHINE", "POWER")
KIND_ROW_X, KIND_ROW_Y, KIND_ROW_SPAN = (1.80, 2.20), (1.08, 1.17, 1.26), 0.30          # m, along the base (model coordinates)
DRAWN_CHAIN_TYPE = "CLOSED"


def _drawn_click(scene, root, origin, direction, want: str, hide=()):
    """A click as Draw hose / Draw drag chain / Draw cable route take it: a ray (in the model's own coordinates, so
    a moved model is clicked where it is now) cast as the picker casts it, with the CAD parts in ``hide`` hidden
    meanwhile (the picker hides the part it replaces: it lies on the fittings). Returns the spot."""
    import bpy
    from mathutils import Vector

    from . import build, drawn, hover, logic
    for ob in hide:
        logic.set_visible_flags(ob, True)
    _update()
    try:
        m = root.matrix_world
        o, d = m @ Vector(origin), (m.to_3x3() @ Vector(direction)).normalized()
        ob, index, loc, normal = hover.cast(scene, bpy.context.evaluated_depsgraph_get(), o, d)
        _check(index >= 0 and ob.get(build.PROP_NAME) == want,
               f"the click meant for '{want}' hits '{ob.get(build.PROP_NAME) if ob is not None else 'nothing'}'")
        sp = drawn.spot(ob, index, loc, normal)
        return sp
    finally:
        for ob in hide:
            if not ob.get(build.PROP_EXCLUDED):
                logic.set_visible_flags(ob, False)
        _update()


def drawn_hose_setup(scene, root) -> str:
    """On the hoses model (tools/make_test_flex.py, at ``root``): the CAD hose HYDRAULIC HOSE ARM leaves the list, and
    a hose is drawn in its place – end A on FITTING VALVE C, two clips on the base's top, end B on FITTING ARM –,
    replacing it. The luff gets its limits first (the length then fits the whole travel). Returns the item's name."""
    import math

    from . import flex, joints
    i = next((k for k, it in enumerate(scene.fresing.flex) if it.name == "HYDRAULIC HOSE ARM"), -1)
    if i >= 0:
        flex.remove(scene, i)
    luff = joints.find(scene, "Luff")
    luff.rot_min, luff.rot_max, luff.use_limits = math.radians(-20.0), math.radians(20.0), True
    cad = _ob(scene, "HYDRAULIC HOSE ARM")
    spots = [_drawn_click(scene, root, (1.292, -0.209, 1.0), (0, 0, -1), "FITTING VALVE C", (cad,)),
             _drawn_click(scene, root, (1.8, -0.36, 2.5), (0, 0, -1), "BASE", (cad,)),
             _drawn_click(scene, root, (2.55, -0.36, 2.5), (0, 0, -1), "BASE", (cad,)),
             _drawn_click(scene, root, (3.002, -0.9, 1.8), (0, 1, 0), "FITTING ARM", (cad,))]
    item, notes = flex.draw_hose(scene, spots, replace=cad)
    _check(not notes, "; ".join(notes))
    return item.name


def drawn_chain_setup(scene, root) -> str:
    """On the gantry (test_flex_chains_a.step, at ``root``, its joints made by ``flex.set_up_test_chains``): the CAD
    chain X leaves the list and a drag chain is drawn between its two brackets, replacing the CAD links."""
    from . import build, flex
    i = next((k for k, it in enumerate(scene.fresing.flex) if it.name == "CHAIN X.ASM"), -1)
    if i >= 0:
        flex.remove(scene, i)
    home = _ob(scene, "CHAIN X.ASM")
    links = [o for o in build.iter_parts(scene) if build.logical_parent(o) == home]
    a = _drawn_click(scene, root, (-0.07, -1.0, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED", links)
    b = _drawn_click(scene, root, (-0.01, -1.0, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING", links)
    item, notes = flex.draw_chain(scene, a, b, replace=links[0])
    _check(not notes, "; ".join(notes))
    return item.name


def drawn_cable_setup(scene, root) -> str:
    """On the cable model (test_paths_a.step, at ``root``): the joint "A-frame luff" and a cable route drawn by
    clicking – the wire on the winch drum (task 0263; "Drum turn" turns the drum with it), SHEAVE 1, SHEAVE 2, the
    CHUTE, a free end –, replacing the CAD rope."""
    from mathutils import Vector

    from . import joints, paths
    rope = _ob(scene, "WIRE ROPE")
    m = root.matrix_world
    # task 0263: the winch holds wire – the drum and the wire on it turn together; the route starts on the wire
    joints.create(scene, "ROTATE", [_ob(scene, "WINCH DRUM"), _ob(scene, "WIRE ON DRUM")], m @ Vector((1.125, 0.0, 0.6)),
                  (m.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized(), name="Drum turn")
    start = _drawn_click(scene, root, (0.0, 0.0, 0.6), (1, 0, 0), "WIRE ON DRUM", (rope,))
    wheels = []                 # (task 0263: A-frame and base x 2.5 – above SHEAVE 1, below SHEAVE 2, above the chute)
    for name, o, d in (("SHEAVE 1", (4.776, 0.0, 6.0), (0, 0, -1)), ("SHEAVE 2", (3.75, 0.0, 1.0), (0, 0, 1)),
                       ("CHUTE", (6.75, 0.0, 2.5), (0, 0, -1))):
        sp = _drawn_click(scene, root, o, d, name, (rope,))
        wheels.append((sp["part"], sp["hit"], False))
    item, _notes = paths.draw_cable(scene, start, wheels, None, name=DRAWN_CABLE, diameter=0.024, replace=rope)
    luff = joints.create(scene, "ROTATE", [_ob(scene, "A-FRAME.ASM")], m @ Vector((3.75, 0.0, 1.825)),
                         (m.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized(), name="A-frame luff")
    luff.rot_min, luff.rot_max, luff.use_limits = -0.26, 0.26, True
    return item.name


def kind_row_setup(scene, root) -> list:
    """Task 0243, on the hoses model (at ``root``): a hose of each kind of ``KIND_ROW`` drawn on the base's top, in
    three rows of two arches, each with its kind's first colour and the standard size nearest 20 mm. Returns the items' names."""
    from ..core import flex_kinds
    from . import flex
    names = []
    for k, kid in enumerate(KIND_ROW):
        x, y = KIND_ROW_X[k % 2], KIND_ROW_Y[k // 2]
        done = [flex.find(scene, n).part for n in names]        # (an arch drawn already may be over the spot)
        a = _drawn_click(scene, root, (x, y, 1.0), (0, 0, -1), "BASE", done)
        b = _drawn_click(scene, root, (x + KIND_ROW_SPAN, y, 1.0), (0, 0, -1), "BASE", done)
        item, notes = flex.draw_hose(scene, [a, b], soft=flex_kinds.get(kid).family == "cable",
                                     name=flex_kinds.get(kid).label)
        _check(not notes, "; ".join(notes))
        item.hose_kind = kid
        item.sag = 0.0                          # (the soft cables too: an arch each, not hanging into the base)
        names.append(item.name)
    return names


def drawn_motion(a, cable_joint: str) -> None:
    """The steps of the drawn stops: the arm luffs, X travels, the A-frame luffs while the drawn rope runs."""
    _joint_step(a, "Luff", 0.0, 2.0, math.radians(16.0), label="Arm up 16°")
    _joint_step(a, "Luff", 2.0, 2.0, math.radians(-10.0), label="Arm down to -10°")
    _joint_step(a, "X", 0.0, 2.0, 0.14, slide=True, label="X out 140 mm")
    _joint_step(a, "X", 2.0, 2.0, -0.14, slide=True, label="X back 280 mm")
    _joint_step(a, "A-frame luff", 0.5, 1.5, math.radians(10.0), label="A-frame forward")
    _joint_step(a, "A-frame luff", 2.5, 1.5, 0.0, label="A-frame back")
    blk = a.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "MOTOR", cable_joint, 0.0, 4.0, "LINEAR"
    blk.speed_mmin = 10.0


@tour_set("flex_drawn", "Hoses, a chain and a cable drawn by clicking", "test_flex_hoses_a.step",
          "test_flex_chains_a.step", "test_paths_a.step", added="0.2.180", changed="0.2.230")
def build_flex_drawn(b: Build):
    from mathutils import Vector

    from . import build, flex, paths
    sc, s = b.scene, b.s
    _look("PRODUCT")
    s.background, s.env_detail = "FACTORY", "SIMPLE"
    roots = sorted(build.model_roots(sc), key=build.uid_scope)
    _check(len(roots) == 3, f"{len(roots)} models instead of 3")
    hoses, chains, cable = roots
    chains.location = chains.location + Vector(DRAWN_CHAINS_AT)
    cable.location = cable.location + Vector(DRAWN_PATHS_AT)
    _update()
    flex.set_up_test_hoses(sc)
    flex.set_up_test_chains(sc)
    for name in ("HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B", "CABLE", "CHAIN Y.ASM", "CHAIN Z.ASM"):
        it = flex.find(sc, name)                # (only the drawn ones in this set's list)
        if it is not None:
            flex.remove(sc, flex.index_of(sc, it))
    _update()
    hose = drawn_hose_setup(sc, hoses)
    chain = drawn_chain_setup(sc, chains)
    rope = drawn_cable_setup(sc, cable)
    _check((hose, chain, rope) == (DRAWN_HOSE, DRAWN_CHAIN, DRAWN_CABLE), f"named {hose}, {chain}, {rope}")
    # task 0243: standard kinds – a row of one hose per kind, the chain closed, the rope galvanised
    kind_row_setup(sc, hoses)
    flex.find(sc, DRAWN_CHAIN).chain_kind = DRAWN_CHAIN_TYPE
    cab = paths.find(sc, DRAWN_CABLE)
    cab.cable_kind = "ROPE"
    cab.colour = "GALVANISED"
    cab.size = "R16"                            # sheaves of Ø360: at least 20 x d (ISO 4308-1, M5) allows 18 mm
    _update()
    _camera(b, "ISO", "Tour view")
    shot = _shot(b, "Tour: drawn hose, chain and cable")
    drawn_motion(_animation(b, DRAWN_ANIM, shot.name), paths.find(sc, DRAWN_CABLE).joint)


def check_drawn_hose(scene) -> str:
    """The drawn hose over the animation: ends on their fittings, through its clips, its length kept."""
    import numpy as np

    from ..core import flex as fcore
    from . import drawn, flex
    it = flex.find(scene, DRAWN_HOSE)
    _check(it is not None and it.drawn, "the drawn hose is missing")
    _check(len(it.clips) == 2, f"it runs through {len(it.clips)} clips, not 2")
    end = stretch = moved = 0.0
    first = None
    for f in sorted({scene.frame_start, scene.frame_end} | set(range(scene.frame_start, scene.frame_end, 12))):
        scene.frame_set(f)
        _update()
        line = flex.shape_now(scene, it)
        stops = [drawn.world_spot(it.a_part, it.a_point, it.a_dir)[0]]
        stops += [drawn.world_spot(c.part, c.point, c.dir)[0] for c in it.clips]
        stops.append(drawn.world_spot(it.b_part, it.b_point, it.b_dir)[0])
        for p in stops:
            end = max(end, float(np.linalg.norm(line - p, axis=1).min()))
        stretch = max(stretch, abs(float(fcore.polyline_length(line)) / it.length - 1.0))
        first = line if first is None else first
        moved = max(moved, float(np.abs(line - first).max()))
    _check(not it.problem, f"'{it.name}': {it.problem}")
    _check(moved > 0.05, f"the drawn hose moved only {moved * 1000:.0f} mm")
    _check(end < 1e-4, f"the drawn hose is {end * 1000:.3f} mm off an end or a clip")
    _check(stretch < 0.005, f"the drawn hose changed its length by {stretch * 100:.2f} %")
    return f"through 2 clips, ends and clips on their parts to {end * 1000:.3f} mm, length kept to {stretch * 100:.2f} %"


def check_drawn_chain(scene) -> str:
    """The drawn chain over the animation: links one pitch apart, the moving end on its bracket."""
    import numpy as np

    from . import drawn, flex
    it = flex.find(scene, DRAWN_CHAIN)
    _check(it is not None and it.drawn and it.made_links, "the drawn drag chain is missing")
    chord = end = moved = 0.0
    first = None
    for f in sorted({scene.frame_start, scene.frame_end} | set(range(scene.frame_start, scene.frame_end, 12))):
        scene.frame_set(f)
        _update()
        pins = flex.pins_now(scene, it)
        chord = max(chord, float(np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max()))
        end = max(end, float(np.linalg.norm(pins[-1] - drawn.world_spot(it.b_part, it.b_point, (1, 0, 0))[0])))
        first = pins if first is None else first
        moved = max(moved, float(np.abs(pins - first).max()))
    _check(not it.problem, f"'{it.name}': {it.problem}")
    _check(moved > 0.05, f"the drawn chain moved only {moved * 1000:.0f} mm")
    _check(chord < 1e-5, f"a link is {chord * 1000:.4f} mm longer or shorter than its link length")
    _check(end < 1e-4, f"the chain's moving end is {end * 1000:.3f} mm off its bracket")
    return f"{it.count} links one pitch apart to {chord * 1000:.4f} mm, moving end on its bracket to {end * 1000:.3f} mm"


def check_drawn_cable(scene) -> str:
    """The drawn cable route over the animation: as the CAD rope it replaces – six contacts, five turning, on its
    sheaves, paid out."""
    import numpy as np

    from . import joints, paths
    it = paths.find(scene, DRAWN_CABLE)
    _check(it is not None and it.drawn, "the drawn cable is missing")
    _check(paths.status(scene, it)[1] == "OK", f"the cable says: {paths.status(scene, it)[0]}")
    kinds = [c.kind for c in it.contacts]
    _check(kinds == ["SHEAVE", "SHEAVE", "SHEAVE", "ROLLER", "ROLLER", "CHUTE"], f"its contacts: {kinds}")
    cab = joints.find(scene, it.joint)
    off = slip = pay = 0.0
    for f in sorted({scene.frame_start, scene.frame_end} | set(range(scene.frame_start, scene.frame_end, 15))):
        scene.frame_set(f)
        _update()
        pts = np.array(paths.shape_now(scene, it), dtype=float)
        for w in paths.wheels_now(scene, it):
            d = pts - np.asarray(w.centre, float)
            ax = np.asarray(w.axis, float)
            off = max(off, abs(float(np.linalg.norm(d - np.outer(d @ ax, ax), axis=1).min()) - float(w.radius)))
        pay = joints.get_value(cab)
        for c in it.contacts:
            if c.kind in paths.TURNING and c.turns and c.joint:
                j = joints.find(scene, c.joint)
                slip = max(slip, abs(joints.get_value(j) - math.radians(c.ratio) * pay * 1000.0)
                           * paths.radius_of(it, c))
    _check(pay > 0.5, f"only {pay:.2f} m of rope ran")
    _check(off < 5e-4, f"the rope is {off * 1000:.2f} mm off a sheave")
    _check(slip < 1e-3, f"a sheave or roller is {slip * 1000:.2f} mm behind the rope")
    return f"6 contacts, {pay:.2f} m ran, on its sheaves to {off * 1000:.2f} mm, wheels turn with it"


def _tube_radius(scene, item) -> float:
    """The drawn tube's radius, measured: the largest distance of its points from the middle line, in a slice
    across the middle of the hose."""
    import bpy
    import numpy as np

    from . import flex
    _update()
    ob = item.part.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ob.to_mesh()
    pts = np.array([v.co[:] for v in me.vertices], dtype=float)
    ob.to_mesh_clear()
    mw = np.array(item.part.matrix_world)
    pts = pts @ mw[:3, :3].T + mw[:3, 3]
    line = flex.shape_now(scene, item)
    k = len(line) // 2
    mid, tan = line[k], line[k + 1] - line[k - 1]
    tan = tan / np.linalg.norm(tan)
    rel = pts - mid
    near = rel[(np.abs(rel @ tan) < 0.003) & (np.linalg.norm(rel, axis=1) < 0.1)]
    _check(len(near) > 0, f"'{item.name}': no tube points at its middle")
    return float(np.linalg.norm(near - np.outer(near @ tan, tan), axis=1).max())


def check_flex_kinds(scene) -> str:
    """Task 0243: one drawn hose per kind – the size's Ø drawn (to 0.1 mm), the kind's look (one shared material per
    kind and colour), the hose patterns' numbers; the rope's kind and colour."""
    from ..core import flex_kinds
    from . import cable_looks, flex, paths
    mats, worst = {}, 0.0
    for kid in KIND_ROW:
        k = flex_kinds.get(kid)
        it = flex.find(scene, k.label)
        _check(it is not None and it.hose_kind == kid, f"the {k.label.lower()} is missing")
        sz = flex_kinds.size(kid, it.size_id)
        _check(sz is not None, f"'{it.name}' has no standard size")
        _check(abs(it.diameter - sz.od) < 1e-6 and abs(it.min_radius - sz.bend) < 1e-6,
               f"'{it.name}': its numbers are not those of {sz.label}")
        worst = max(worst, abs(2.0 * _tube_radius(scene, it) - sz.od))
        mat = it.part.material_slots[0].material if it.part.material_slots else None
        _check(mat is not None and mat.get("fr_material") == k.colours[0].material,
               f"'{it.name}' has the look {mat.get('fr_material') if mat else None}, not {k.colours[0].material}")
        mats[kid] = mat
        if k.pattern:
            _check(cable_looks.LOOK in it.part and int(round(it.part[cable_looks.LOOK][3])) ==
                   int(cable_looks.KINDS[k.pattern]), f"'{it.name}' draws no {k.pattern.lower()} pattern")
        _check(flex.status(scene, it)[1] == "OK", f"'{it.name}': {flex.status(scene, it)[0]}")
    _check(len({m.name for m in mats.values()}) == len(KIND_ROW), "two kinds share one look")
    _check(worst < 1e-4, f"a hose is drawn {worst * 1000:.2f} mm thicker or thinner than its size")
    cab = paths.find(scene, DRAWN_CABLE)
    _check(cab.cable_kind == "ROPE" and cab.part.get("fr_group_manual") == "Wire ropes, galvanised"
           and abs(cab.diameter - 0.016) < 1e-6, "the drawn rope is not a galvanised wire rope of 16 mm")
    return f"{len(KIND_ROW)} kinds, each Ø as its size to {worst * 1000:.3f} mm, one look per kind; the rope galvanised"


def check_chain_types(scene) -> str:
    """Task 0243: the drawn chain as each of the four types in turn, at the start, middle and end of X's travel: its
    standard numbers, links one pitch apart, the moving end on its bracket; back to the closed chain at the end."""
    import numpy as np

    from ..core import flex_kinds
    from . import drawn, flex
    it = flex.find(scene, DRAWN_CHAIN)
    _check(it is not None and it.made_links, "the drawn drag chain is missing")
    frames = (scene.frame_start, (scene.frame_start + scene.frame_end) // 2 - 10, scene.frame_end)
    chord = end = 0.0
    try:
        for kid in ("OPEN", "CLOSED", "HALF", "STEEL"):
            it.chain_kind = kid
            sz = flex_kinds.size(kid, it.size_id)
            _check(sz is not None and abs(it.pitch - sz.pitch) < 1e-6 and abs(it.width - sz.width) < 1e-6,
                   f"the {kid.lower()} chain does not have its size's numbers")
            for f in frames:
                scene.frame_set(f)
                _update()
                flex.refresh(scene, force=True)
                _check(flex.status(scene, it)[1] == "OK", f"{kid.lower()} chain: {flex.status(scene, it)[0]}")
                pins = flex.pins_now(scene, it)
                chord = max(chord, float(np.abs(np.linalg.norm(np.diff(pins, axis=0), axis=1) - it.pitch).max()))
                end = max(end, float(np.linalg.norm(pins[-1] - drawn.world_spot(it.b_part, it.b_point,
                                                                                 (1, 0, 0))[0])))
    finally:
        it.chain_kind = DRAWN_CHAIN_TYPE
        scene.frame_set(scene.frame_start)
        _update()
    _check(chord < 1e-5, f"a link is {chord * 1000:.4f} mm off its link length")
    _check(end < 1e-4, f"the chain's moving end is {end * 1000:.3f} mm off its bracket")
    return f"open, closed, half-open and steel: links one pitch apart to {chord * 1000:.4f} mm, end on its bracket " \
           f"to {end * 1000:.3f} mm"


def check_drawn_replace(scene) -> str:
    """The CAD parts the drawn ones replace: hidden for good – the view, renders, the clash check, the web model."""
    from . import build, clash, flex, paths, web3d
    items = [flex.find(scene, DRAWN_HOSE), flex.find(scene, DRAWN_CHAIN), paths.find(scene, DRAWN_CABLE)]
    _check(all(it is not None for it in items), "a drawn item is missing")
    replaced = [r.obj for it in items for r in it.replaces if r.obj is not None]
    _check(len(replaced) == 1 + 24 + 1, f"{len(replaced)} replaced CAD parts, not 26 (hose, 24 links, rope)")
    checked = {o.name for o in clash.objects(scene)}
    web = {o.name for o in web3d.objects(scene)[0]}
    for ob in replaced:
        name = ob.get(build.PROP_NAME)
        _check(ob.get(build.PROP_EXCLUDED) and ob.hide_render and not ob.visible_get(), f"'{name}' still shows")
        _check(ob.name not in checked, f"'{name}' is still in the clash check")
        _check(ob.name not in web, f"'{name}' is still in the web 3D model")
    for it in items:
        _check(it.part.name in web, f"the drawn '{it.name}' is not in the web 3D model")
    return "the CAD hose, the 24 CAD links and the CAD rope hidden for good; the drawn ones in the web model"


SPOOL_ANIM = "Spooling"


@tour_set("spool", "Drum and carousel spooling", "test_spool.step", added="0.2.85", changed="0.2.230")
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


@tour_set("served", "Served cable look", "test_spool.step", added="0.2.116", changed="0.2.230")
def build_served(b: Build):
    sc = b.scene
    _look("PRODUCT")
    made = served_demo(sc)
    _check(made["animation"] == SPOOL_ANIM, f"the animation is called '{made['animation']}'")
    _update()
    _surround(b, "FACTORY")
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


@tour_set("sea_cable", "Cable into the sea", "test_sea.step", added="0.2.91", changed="0.2.196")
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
    cam.data.lens = 22.0                    # task 0234: wider, so the hull shows with the cable
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


@tour_set("vessel_work", "Vessel at work", "test_thrusters.step", added="0.2.127", changed="0.2.196")
def build_vessel_work(b: Build):
    """Task 0154: a workboat with two azimuths and a bow thruster sails ahead at 8 knots, then pushes sideways."""
    from mathutils import Matrix, Vector

    from . import vessel_work
    sc = b.scene
    _look("PRODUCT")
    vessel_work.set_up_test_model(sc)
    _update()
    cam = _camera(b, "ISO", "Tour view", lens=28.0)
    root = next(o for o in sc.objects if o.get("fr_uid") == "TEST.THRUSTERS#1")      # task 0234: from the port
    w = root.matrix_world                                                            # bow, closer: the hull, its
    at, look = w @ Vector((54.0, 30.0, 13.0)), w @ Vector((16.0, 2.0, -0.5))        # wake and the jets to port
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


@tour_set("moving_cable", "A cable on a moving part", "test_moving.step", added="0.2.95", changed="0.2.196")
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


@tour_set("swivel", "A sheave on a swivel", "test_swivel.step", added="0.2.138", changed="0.2.199")
def build_swivel(b: Build):
    from . import paths, paths_swivel
    sc = b.scene
    _look("PRODUCT")
    made = paths_swivel.set_up_test_model(sc)
    _check(made["animation"] == SWIVEL_ANIM, f"the animation is called '{made['animation']}'")
    it = paths.find(sc, made["cable"])
    _check(it is not None and not it.problem, f"'{made['cable']}': {it.problem if it is not None else 'missing'}")
    _update()
    _surround(b, "FACTORY")
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


@tour_set("tracks", "Tensioner tracks and a belt", "test_tracks.step", added="0.2.87", changed="0.2.177")
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
    tilt = joints.find(scene, tracks.TEST_TILT)
    off = chord = 0.0
    lifts, tilts = [], []
    for f in sorted(set(range(scene.frame_start, scene.frame_end + 1, 25)) | {scene.frame_end}):
        scene.frame_set(f)
        _update()
        lifts.append(joints.get_value(lift))
        tilts.append(joints.get_value(tilt) if tilt is not None else 0.0)
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
    _check(math.degrees(max(tilts)) > tracks.TEST_TILT_DEG - 0.1 and abs(tilts[-1]) < 1e-4,
           f"the tensioner tilted {math.degrees(max(tilts)):.1f}° (and back)")
    return (f"{ran:.2f} m of cable, the pads with it to {abs(run - want) * 1000:.2f} mm, sprocket "
            f"{math.degrees(turn):.0f}°; hinges on their loops to {off * 1000:.3f} mm, one "
            f"pitch apart to {chord * 1000:.3f} mm; top track lifted {max(lifts) * 1000:.0f} mm, the tensioner tilted "
            f"{math.degrees(max(tilts)):.1f}°")


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
    # 6 m off the top layer from r 1.20 outwards: 6 / 1.24 … 6 / 1.20 = 4.8 … 5.0 rad (task 0263: the carousel x 2)
    _check(abs(car[six, 1]) > 4.5, f"the carousel turned only {math.degrees(abs(car[six, 1])):.0f}°")
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


@tour_set("copies", "Two copies", "test_crane_a.step", "test_crane_a.step", added="0.2.47", changed="0.2.203")
def build_copies(b: Build):
    from mathutils import Vector

    from . import build, logic, states
    sc = b.scene
    _look("PRODUCT")
    first, second = sorted(build.model_roots(sc), key=build.uid_scope)
    second.location = second.location + Vector((0.0, 4.5, 0.0))      # 1.5 m between the bases
    _update()
    cover = next(o for o in sc.objects if o.get(build.PROP_NAME) == "COVER" and build.model_root_of(o) == second)
    logic.set_hidden(cover, True)
    states.save_visibility(sc, "Second crane without cover")
    _surround(b, "ASSEMBLY")
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


@tour_set("update", "Model update", "test_crane_a.step", added="0.2.47", changed="0.2.203")
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
    _surround(b, "FACTORY")
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


def _accel_program(steps: int = 48) -> str:
    """Task 0103: 2 mm zigzag steps above the block (G64), the same back with exact stops (G61), then one long line.
    Task 0262: 48 steps each way (were 24): the router's head starts 215 mm above the block, and its long first rapid
    made acceleration only 1.19 x longer than without; 48 steps: 1.29 x."""
    out = ["(T1 D=6. CR=0. - flat end mill)", "G21 G90 G94 G17 G64", "G0 X-30 Y-10 Z3", "G1 F3000"]
    x = -30
    for k in range(steps):
        if k % 2 == 0:
            x += 2
            out.append(f"X{x}")
        else:
            out.append(f"Y{-8 if (k // 2) % 2 == 0 else -10}")
    out.append("G61")
    for k in range(steps):
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


@tour_set("clash", "Clash check", "test_clash.step", added="0.2.53", changed="0.2.199")
def build_clash(b: Build):
    sc = b.scene
    _look("PRODUCT")
    _surround(b, "FACTORY")
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


@tour_set("sequence", "Assembly sequence", "test_sequence.step", added="0.2.79", changed="0.2.213")
def build_sequence(b: Build):
    sc = b.scene
    _studio(b)
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


@tour_set("productvideo", "Product video", "test_sequence.step", added="0.2.81", changed="0.2.213")
def build_productvideo(b: Build):
    from mathutils import Vector

    from . import build as bld, joints, product_video
    sc = b.scene
    _studio(b)
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


@tour_set("sequenceframe", "Round a frame, back to CAD", "test_sequence_frame.step", added="0.2.102", changed="0.2.199")
def build_sequenceframe(b: Build):
    from . import states
    sc = b.scene
    _studio(b)
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
    return np.array([(x, y, z) for x in (-0.15, 0.15) for y in (-0.15, 0.15) for z in (0.0, 0.95 * TALL)])


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


@tour_set("gantry", "CNC gantry", "test_gantry.step", added="0.2.47", changed="0.2.215")
def build_gantry(b: Build):
    from . import gcode, tools
    sc = b.scene
    tool = _gantry(b)
    _mill_with_cnc(sc)                             # task 0223: the program's cuts take the block away
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


@tour_set("atc", "Tool changer", "test_gantry.step", added="0.2.47", changed="0.2.215")
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
    joints.create(sc, "ROTATE", [car], Vector((1.25, 0, 0)), Vector((0, 0, 1)), name="Carousel")
    cnc = sc.fresing.cnc
    cnc.changer, cnc.carousel_joint = "ATC", "Carousel"
    rows[1].pocket = 7
    toolchange.add_pocket(sc, _ob(sc, "CAROUSEL DISC"), Vector((1.40, 0, 0.35)))
    cnc.pocket_count = 8
    why = toolchange.fill_carousel(sc)
    _check(not why, why)
    _check(not toolchange.problems(sc), "; ".join(toolchange.problems(sc)))
    _close_camera(b, Vector((1.25, 0.0, 0.45)), 0.9, "Tour carousel")
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


@tour_set("doublearm", "Double-arm tool changer", "test_atc.step", added="0.2.51", changed="0.2.207")
def build_doublearm(b: Build):
    from mathutils import Vector

    from . import doublearm
    sc = b.scene
    a = _animation(b, "Double-arm changer")
    blk = _gcode_step(a, _program(b, "Tour double-arm.ngc", doublearm.TEST_PROGRAM), sc)
    doublearm.set_up_test_model(sc, blk)
    bad = [t for ok, t in doublearm.check(sc) if not ok]
    _check(not bad, "; ".join(bad[:2]))
    _mill_with_cnc(sc)                             # task 0223: the program's cuts take the block away
    _close_camera(b, Vector((-0.32, 0.0, 0.36)), 0.8, "Tour double arm")   # the arm, the station, the block
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


@tour_set("rotary4", "4th axis - rotary table", "test_4axis.step", added="0.2.52", changed="0.2.207")
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
    _close_camera(b, Vector((-0.05, 0.0, 0.22)), 0.36, "Tour 4th axis")
    a.start_shot = _shot(b, "Tour: 4th axis").name


@tour_set("rotary5", "5th axis - trunnion", "test_5axis.step", added="0.2.52", changed="0.2.207")
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
    _close_camera(b, Vector((0.0, 0.0, 0.28)), 0.34, "Tour 5th axis")
    a.start_shot = _shot(b, "Tour: 5th axis").name


@tour_set("toolpath", "The app makes the toolpath", "test_toolpath.step", added="0.2.55", changed="0.2.195")
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
TOOLS_TOUR = """(THREE TOOLS: FACE MILL, END MILL, CHAMFER MILL - BT40)
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


@tour_set("tools", "Three tools and the hand", "test_mill.step", added="0.2.47", changed="0.2.262")
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
    face.diameter, face.length, face.holder, face.holder_length = 0.05, 0.085, "BT40", 0.045
    face.lead_angle = 1.5707963
    end = tools.add_row(sc, "FLAT", 2)
    end.diameter, end.length, end.holder, end.holder_length = 0.01, 0.098, "BT40", 0.06
    vee = tools.add_row(sc, "VEE", 3)
    vee.diameter, vee.length, vee.holder, vee.holder_length = 0.01, 0.09, "BT40", 0.06
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
    _check(all(r.holder == "BT40" for r in tools.rows(scene) if r.number in (1, 2, 3)), "not all three are BT40")
    return "T1 face mill, T2 end mill, T3 chamfer mill (BT40); length offsets " + ", ".join(
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
MARKS_TOUR = f"""(TOOL MARKS: FACE MILL, END MILL, DRILL - BT40)
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


@tour_set("marks", "Tool marks", "test_mill.step", added="0.2.73", changed="0.2.262")
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
    face.diameter, face.length, face.holder, face.holder_length = 0.05, 0.085, "BT40", 0.045
    face.lead_angle = 1.5707963
    end = tools.add_row(sc, "FLAT", 2)
    end.diameter, end.length, end.holder, end.holder_length = 0.01, 0.098, "BT40", 0.06
    drill = tools.add_row(sc, "DRILL", 3)
    drill.diameter, drill.length, drill.holder, drill.holder_length = 0.0085, 0.09, "BT40", 0.06
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
    # task 0280: the test mill is a VMC (task 0249) – its table carries the block away at the end of the program
    # (X-90): the camera rides on the table, so the stop's last frame still shows the cut
    _update()
    table = _ob(sc, "X.ASM")
    cam.parent, cam.matrix_parent_inverse = table, table.matrix_world.inverted()
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


@tour_set("air", "Air blast", "test_mill.step", added="0.2.47", changed="0.2.262")
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


COOLANT_TOUR = AIR_TOUR.replace("M7", "M8").replace("S9000", "S15000")    # task 0257: a fast tool (7.9 m/s)


@tour_set("coolant", "Coolant", "test_mill.step", added="0.2.48", changed="0.2.262")
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


@tour_set("liquid", "Coolant liquid", "test_mill.step", added="0.2.262", changed="0.2.262")
def build_liquid(b: Build):
    """Task 0346: the coolant collects on the VMC – fills the pocket, runs over the table into the tray."""
    from mathutils import Vector

    from . import liquid
    sc = b.scene
    _look("PRODUCT")
    _xyz(sc)
    a, r = liquid.set_up_test_model(sc, os.path.dirname(b.file("Tour liquid.ngc")), axes=False, name="Coolant liquid",
                                    before_build=_hide_finished)
    _check(not r["warnings"], "; ".join(r["warnings"][:2]))
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"
    stock = _ob(sc, "STOCK 200x200x40")
    _close_camera(b, stock.matrix_world.translation + Vector((0.0, -0.05, 0.0)), 0.45, "Tour liquid")
    a.start_shot = _shot(b, "Tour: coolant liquid").name


def _check_liquid(scene):
    """The liquid is worked out (Draft) and lies in the pocket, on the table and in the tray; drawn this frame."""
    import bpy

    from . import coolant, liquid
    _check(liquid.problem(scene) == "", liquid.problem(scene))
    info = liquid.bake_now(scene)
    _check(info is not None, "the liquid was not worked out")
    liquid.show(scene)
    rd, beds = liquid._open(scene)
    _check(rd is not None, "no bake for the project as it is")
    f = scene.frame_current
    depths = rd.read(f)[0]
    vols = [float(d.sum()) * g[0] ** 2 * 1e3 for d, g in zip(depths, beds.geom)]
    _check(vols[0] > 0.01, f"only {vols[0]:.3f} l on the table at frame {f}")
    sp = coolant.spans()
    _check(len(sp) == 1, f"{len(sp)} coolant spans, not 1")
    ob = bpy.data.objects.get(liquid.OBJ_TABLE)
    _check(ob is not None and len(ob.data.polygons) > 0, "no liquid drawn on the table")
    return (f"{vols[0]:.2f} l on the table, {vols[1]:.2f} l in the tray at frame {f}; "
            f"{len(ob.data.polygons):,} faces drawn")


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
    # task 0257: the tool turns at 15,000 rpm – its air layer turns part of the jets away
    from ..core import coolant as core
    rpm = coolant.rpm_at(coolant.root(), f)
    _check(rpm == 15000, f"the coolant reads {rpm} rpm, not the program's 15000")
    _z, radius = coolant._tool_at(scene, coolant.root(), f)
    v = core.rim_speed(rpm, radius)
    share = core.deflect_share(v, scene.fresing.coolant.flow)
    _check(share > 0.1, f"at {v:.1f} m/s the air layer turns away only {share:.0%} of the jets")
    return (f"flood {(sp[0, 1] - sp[0, 0]) / scene.render.fps:.1f} s; {len(coolant.wet_parts(scene))} wet parts; "
            f"tool {v:.1f} m/s, {share:.0%} of the jets turned away")


def _check_air(scene):
    from . import air, chips
    _milled(scene)
    bk = chips.bake(scene, force=True)
    _check(bk is not None and bk.count > 0, "no chips were worked out")
    _check(bk.stats.get("air_s", 0) > 1.0, "the air did not blow (no M7 seen)")
    return f"{bk.count} chips; {air.codes_text(scene)}"


# ----- vessel motion at sea (task 0085) -----

VESSEL_ANIM = "Vessel at sea"


VESSEL_PROPS = ("PERSON", "IBC")          # beside the 8 m test crane on the deck


@tour_set("vessel", "Vessel motion", "test_crane_a.step", added="0.2.65", changed="0.2.203")
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
    _update()
    import numpy as np

    from . import build, props_scale, surroundings  # task 0234: a person and a tank on the deck give the scale
    props = [surroundings.add_prop(sc, kind) for kind in VESSEL_PROPS]
    mn, mx = build.world_bounds(list(build.iter_parts(sc)))
    for ob, (dx, dy) in zip(props, ((-0.2, 1.0), (1.2, 1.6))):      # behind the crane, seen from the camera
        ob.location.x, ob.location.y = float(mx[0]) + dx, float(mx[1]) + dy
    _update()
    crane = np.array([(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])], float)
    _camera(b, "ISO", "Tour deck", lens=24.0, points=np.vstack([crane, props_scale.corners(props)]))
    s.vessel.enabled = True
    _update()
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
    from . import surroundings
    props = sorted(p.get(surroundings.PROP_TAG) for p in surroundings.props(scene))
    _check(props == sorted(VESSEL_PROPS), f"the deck's props are {props}, not a person and an IBC tank")
    for p in surroundings.props(scene):
        _check(p.constraints.get(vessel_motion.CON) is not None, f"the {p.name} does not ride on the vessel")
    return vessel_motion.words(scene) + "; a person and an IBC tank ride on the deck"


# ----- weather and time of day (task 0109) -----

WEATHER_ANIM = "Weather changes"


# ----- props for scale in detail (task 0155) -----


@tour_set("props", "Props for scale and people", "test_crane_a.step", added="0.2.124", changed="0.2.203")
def build_props(b: Build):
    from . import cameras, props_scale
    _look("PRODUCT")
    _surround(b, "WAREHOUSE")                  # task 0233: real-size things belong in a warehouse (or on a quay)
    obs = props_scale.line_up(b.scene)
    cameras.add_camera(b.scene, "ISO", 50.0, "Tour props", points=props_scale.corners(obs))
    _shot(b, "@props")


def _check_props(scene):
    from . import props_scale
    return props_scale.check_line_up(scene)


# ----- people walk, carry and meet (task 0157) -----

PEOPLE_ANIM = "Two people meet"


OPERATOR_ANIM = "A person changes the tool"


@tour_set("operator", "A person changes the tool", "test_mill_cabinet.step", added="0.2.132", changed="0.2.195")
def build_operator(b: Build):
    """The test mill in its enclosure (tools/make_test_mill_cabinet.py; task 0249: the larger VMC): one manual change
    from T1 to T2 done by the operator, who walks up, opens the sliding doors, swaps the tools over the trolley, closes the door and walks
    away (task 0156; the set-up is shared with the PC check: ``tc_person.set_up_test_model``)."""
    from . import cameras, tc_person
    sc = b.scene
    _look("PRODUCT")
    a = tc_person.set_up_test_model(sc, b.file("Tour operator.ngc"))
    _mill_with_cnc(sc)                             # task 0223: the program's two cuts take the block away
    a.quality, a.out_resolution, a.out_format = "draft", "preview", "presentation"
    cam = cameras.add_camera(sc, "ISO", 40.0, "Tour operator", points=tc_person.test_camera_points())
    sc.camera = cam
    a.start_shot = _shot(b, "@operator").name


def _check_operator(scene):
    from . import tc_person
    return tc_person.check_test_model(scene)


@tour_set("people", "People walk and meet", "test_crane_a.step", added="0.2.128", changed="0.2.203")
def build_people(b: Build):
    import numpy as np

    from . import cameras, people, props_scale
    from . import surroundings as sur
    _look("PRODUCT")
    _surround(b, "QUAY")                       # task 0233: people on the quay round a real-size container, not beside
    anna, ben, box = people.set_up_example(b.scene)         # beside the crane (task 0259: at real size)
    pts = people.example_corners(b.scene)
    mn, mx = pts.min(0), pts.max(0)
    cont = sur.add_prop(b.scene, "CONTAINER")
    cont.rotation_euler.z = math.radians(90.0)
    _update()
    cb = props_scale.corners([cont])
    cont.location = (cont.location.x + (mx[0] + 3.0 - cb[:, 0].min()),
                     cont.location.y + ((mn[1] + mx[1]) / 2 - (cb[:, 1].min() + cb[:, 1].max()) / 2), cont.location.z)
    _update()
    pts = np.vstack([pts, props_scale.corners([cont])])
    cameras.add_camera(b.scene, "ISO", 50.0, "Tour people", points=pts)
    a = _animation(b, PEOPLE_ANIM)
    a.start_shot = _shot(b, "@people").name


def _check_people(scene):
    from . import people
    return people.check_example(scene)


# task 0299: the new presets, each a saved scene of the quay (stop id, preset)
WEATHER_PRESET_STOPS = (("wx_sunrise", "SUNRISE"), ("wx_sunset", "SUNSET"), ("wx_mist", "SEA_MIST"),
                        ("wx_hail", "HAIL"), ("wx_heat", "HOT_CALM"))
STORM_SHOT = "Storm coming"
# where Go shows the thunderstorm: its set flash (Change to puts it at 80 % of the 4 s change: 3.2 s) in 4 s + 1 s tail
STORM_AT = 3.2 / 5.0


@tour_set("weather", "Weather and time of day", "test_crane_a.step", added="0.2.88", changed="0.2.228")
def build_weather(b: Build):
    """The weather lesson's steps first (``lessons/weather.py``, task 0299: Weather & time on, a preset, Change to
    Thunderstorm at the playhead), then the tour's own scenes."""
    from . import lesson, weather
    from .lessons import weather as wx_lesson
    sc, s = b.scene, b.s
    lesson.run(sc, "weather")
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
    s.weather.flood_strength = 4.0               # task 0233: at 400 px the picture was almost black
    _update()
    _shot(b, "@night")
    for stop_id, preset in WEATHER_PRESET_STOPS:            # task 0299
        weather.use_preset(sc, preset)
        _update()
        _shot(b, "@" + stop_id)
    # the lesson's thunderstorm: from a clear day (the weather the project is left in, so Go puts back nothing), seen
    # low so the sky (and the bolts) show
    quay = sc.camera
    _camera(b, "LOW", "Tour storm", lens=22.0)
    weather.use_preset(sc, "CLEAR_DAY")
    _update()
    storm = s.animations[wx_lesson.ANIM]
    storm.tail, storm.quality, storm.out_resolution, storm.out_format = 1.0, "draft", "preview", "presentation"
    storm.start_shot = _shot(b, STORM_SHOT).name
    sc.camera = quay
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


def _check_preset(name: str, extra=None):
    """A stop's check for a weather preset (task 0299): Weather & time on with the preset's values, its channels as
    the preset says, and ``extra(scene)`` -> a few words."""
    def check(scene):
        from ..core import weather as core
        from . import weather
        _check(weather.enabled(scene), "Weather & time is off")
        w = scene.fresing.weather
        _check(w.preset == name, f"the preset is {w.preset}, not {name}")
        want = core.derive(core.preset(name, weather.state(scene)), weather.place(scene))
        for ch in ("sun_el", "rain", "hail", "mist", "heat", "lightning"):
            _check(abs(_channel(scene, ch) - want[ch]) < 1e-3, f"{ch} is {_channel(scene, ch):.3f}, not "
                                                             f"{want[ch]:.3f}")
        words = extra(scene) if extra is not None else ""
        return weather.header(scene) + (f" · {words}" if words else "")
    return check


def _sun_low(morning: bool):
    def extra(scene):
        el = _channel(scene, "sun_el")
        _check(0.0 < el < 8.0, f"the sun stands at {el:.1f}°, not low over the horizon")
        hour = scene.fresing.weather.hour
        _check((hour < 12.0) == morning, f"{hour:.2f} h is not in the {'morning' if morning else 'evening'}")
        _check(_channel(scene, "flood") < 0.01, "the floodlights are on")
        return f"sun {el:.1f}° up"
    return extra


def _mist_on(scene):
    from . import weather_sky
    ng = scene.compositing_node_group
    _check(ng is not None and ng.name == weather_sky.FOG_GROUP, "the mist is not laid over the picture")
    _check(scene.view_layers[0].use_pass_position, "the mist has no Position pass")
    return f"mist {_channel(scene, 'mist'):.0f} per km at the water"


def _hail_on(scene):
    roles = {o.get("fr_weather") for o in scene.objects}
    _check("hail" in roles and "bounce" in roles, "the falling or bouncing hail is missing")
    return "hail falls and bounces"


def _heat_on(scene):
    from . import weather_sky
    ng = scene.compositing_node_group
    _check(ng is not None and ng.name == weather_sky.FOG_GROUP, "no heat shimmer over the picture")
    return "heat shimmer on"


def _check_storm(scene):
    """The lesson's thunderstorm video: the storm comes, lightning flashes only once it is there (task 0299)."""
    from . import weather
    from .lessons import weather as wx_lesson
    _check(weather.enabled(scene), "Weather & time is off")
    a = scene.fresing.animations.get(wx_lesson.ANIM)
    _check(a is not None and any(b.kind == "WEATHER" for b in a.blocks), "the thunderstorm video has no weather step")
    _check(scene.fresing.anim_baked == wx_lesson.ANIM, "the thunderstorm video is not built")
    frames = range(scene.frame_start, scene.frame_end + 1)
    rows = []
    shown = scene.frame_current
    for f in frames:
        scene.frame_set(f)
        rows.append((_channel(scene, "lightning"), _channel(scene, "flash"), _channel(scene, "rain")))
    scene.frame_set(shown)                       # (the stop's picture is the flash)
    flashes = [f for f, r in zip(frames, rows) if r[1] > 0.3]
    _check(frame_for(scene, find("wx_thunder")) in flashes, "Go does not show the flash")
    _check(rows[0][0] < 0.01 and rows[-1][0] > 0.5, f"lightning {rows[0][0]:.2f} -> {rows[-1][0]:.2f}")
    _check(flashes, "no lightning flash")
    _check(all(rows[f - scene.frame_start][0] > 0.0 for f in flashes), "a flash before the storm came")
    roles = [o.get("fr_weather") for o in scene.objects]
    _check(roles.count("bolt") == 4 and "lightning" in roles, "the bolts or the lightning lamp are missing")
    return f"{len(flashes)} frames with a flash; rain {rows[0][2]:.2f} -> {rows[-1][2]:.2f}"


# ----- a house from House Planner (task 0114) -----

HOUSE_MOMENT = "summer-evening"


@tour_set("house", "House from House Planner", "sample-house.hpscene", added="0.2.92", changed="0.2.173")
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
    pt = Vector((2.0 * math.cos(a) * math.cos(a), 2.0 * math.sin(a), 1.1875))
    ob, index, loc, normal = hover.cast(scene, bpy.context.evaluated_depsgraph_get(), pt + n * 0.01, -n)
    _check(index >= 0, "the click did not hit the slewing ring")
    o, d, desc = joints.axis_from_hit(ob, index, loc, normal)
    return ob, o, d, desc


@tour_set("mesh", "Mesh model (glTF)", "test_mesh_crane.glb", added="0.2.99", changed="0.2.211")
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
    _surround(b, "FACTORY")
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
    _check(abs(dia - 4000.0) < 20.0, f"the ring measures Ø{dia:.1f} mm, it is Ø4000")
    base = _ob(scene, "BASE")
    _check(base.material_slots[0].material is not None and base.material_slots[0].material.get("fr_has_texture"),
           "the base lost its texture from the file")
    return f"ring Ø{dia:.1f} mm, axis {off:.2f}° off vertical"


@tour_set("import", "Import again and Up axis", "test_crane_a.step", added="0.2.218", changed="0.2.218")
def build_import(b: Build):
    """Task 0289: the crane imported, then a second copy from 1 Import > Imported models > Import again (the stored
    copy, nothing read), moved aside and turned to Y up on its line – it lies on its side, as a Y-up file would."""
    import bpy

    from . import build, ops_import
    from ..core import import_cache
    sc = b.scene
    _look("PRODUCT")
    src = os.path.normcase(os.path.abspath(build.model_roots(sc)[0].get(build.PROP_SOURCE, "")))
    e = next((x for x in import_cache.entries(ops_import.cache_root())
              if os.path.normcase(os.path.abspath(x.source)) == src), None)
    _check(e is not None, "the crane's import is not in the cache")
    res = bpy.ops.fresing.import_step("EXEC_DEFAULT", again=e.id)
    _check(res == {"FINISHED"}, f"Import again returned {res}")
    second = build.model_roots(sc)[1]
    second.location.x += IMPORT_ASIDE
    build.set_mat(second, build.PROP_REST_BASIS, second.matrix_basis)
    _update()
    res = bpy.ops.fresing.model_up_axis("EXEC_DEFAULT", root=second.name, axis="Y")
    _check(res == {"FINISHED"}, f"Up axis returned {res}")
    _update()
    _surround(b, "FACTORY")
    _camera(b, "ISO", "Tour view")
    _shot(b, "@import_again")


IMPORT_ASIDE = 5.0                   # m: the second copy stands this far along +X


def _check_import(scene):
    from . import build, logic
    roots = build.model_roots(scene)
    _check(len(roots) == 2, f"expected 2 copies of the crane, there are {len(roots)}")
    axes = [logic.up_axis_of(r) for r in roots]
    _check(axes == ["Z", "Y"], f"the copies' up axes are {axes}, expected Z and Y")
    n = [len([o for o in build.iter_parts(scene) if build.logical_parent(o) is not None and _root_is(o, r)])
         for r in roots]
    _check(n[0] == n[1] and n[0] > 10, f"the copies have {n[0]} and {n[1]} parts")
    return f"2 copies of {n[0]} parts, Z up and Y up"


def _root_is(ob, root) -> bool:
    from . import build
    while ob is not None:
        if ob == root:
            return True
        ob = build.logical_parent(ob)
    return False


# ---------------------------------------------------------------------------
# the stops, in order (numbers follow this order)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Lifting plan (task 0201): an AT-40 beside the test crane, the test crane's boom as the load
# ---------------------------------------------------------------------------

# the invented loads of test_loads.step (task 0231), each sized for its equipment: the pump skid is the lift of the
# set, the IBC and the container stand in the yard (the container is the big crane's load, the IBC the forklift's)
LIFT_CRANE = "AT-40"
LIFT_LOAD, LIFT_LOAD_MASS = "PUMP SKID.ASM", 6.0          # t, invented ("estimate" as source)
YARD_LOADS = (("IBC ON PALLET.ASM", 1.1), ("PUMP SKID.ASM", 6.0), ("20 FT CONTAINER.ASM", 18.0))
MAT_H = 0.2                                               # m: a crane mat's thickness
LIFT_VIEW = "ISO_LEFT"                                    # from the IBC's side: crane and container stay behind the skid


def _yard(b: Build) -> None:
    """The quayside ground of the Lifting sets (task 0231)."""
    _look("PRODUCT")
    b.s.env_detail = "SIMPLE"
    b.s.background = "QUAY"
    _update()


def _crane_mats(b: Build, crane) -> int:
    """A crane mat under each outrigger pad of the crane in the set-up pose: plain boxes named 'Tour crane mat N'
    (the Lifting plan has no mats yet), put where the pads are worked out from the crane's own file."""
    import bpy
    import numpy as np

    from . import lifting, materials
    data = lifting.item_at(lifting.path_of(crane)).data
    og = data["outriggers"]
    pose = next(p for p in data["rig"]["poses"] if p["name"] == "Set up")
    half_b = float(og["b_in"]) + int(og["stages"]) * float(pose["values"].get("Outriggers", 0.0)) / 1000.0
    pad = max(og.get("pad", [0.6, 0.6])) * 2.4
    root = crane.root
    M = np.array(root.matrix_world)
    mat = materials.ensure_material("Crane mat", "paint_satin", "RAL 8001")
    n = 0
    for sx in (-1, 1):
        for sy in (-1, 1):
            c = M @ np.array([sx * float(og["a"]), sy * half_b, 0.0, 1.0])
            x, y = pad / 2, pad / 2
            vs = [(-x, -y, -MAT_H), (x, -y, -MAT_H), (x, y, -MAT_H), (-x, y, -MAT_H),
                  (-x, -y, 0), (x, -y, 0), (x, y, 0), (-x, y, 0)]
            fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
            n += 1
            me = bpy.data.meshes.new(f"Tour crane mat {n}")
            me.from_pydata(vs, [], fs)
            me.update()
            me.materials.append(mat)
            ob = bpy.data.objects.new(f"Tour crane mat {n}", me)
            ob.location = (float(c[0]), float(c[1]), MAT_H)
            ob.rotation_euler = (0.0, 0.0, lifting.heading_of(crane))
            b.scene.collection.objects.link(ob)
    return n


def _yard_crane(b: Build, path: str, at: tuple, heading: float = math.pi):
    """A crane from the library on mats at ``at`` (x, y) on the yard, in its pose 'Set up'."""
    import bpy

    from . import lifting
    c = lifting.place(bpy.context, path, (at[0], at[1], MAT_H), heading)
    lifting.apply_pose(b.scene, c, "Set up")
    _update()
    _crane_mats(b, c)
    return c


def _skid_load(b: Build):
    """The pump skid as the Lifting plan's load: 6 t invented, CoG computed from its parts (the pump and the motor stand
    off the middle, so the CoG is not in the middle of the frame)."""
    from . import build, lifting, logic
    part = next(o for o in logic.descendants(build.model_roots(b.scene)[0])
                if o.get(build.PROP_NAME) == LIFT_LOAD)
    ld = lifting.new_load(b.scene, [part], "Pump skid")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", LIFT_LOAD_MASS, "ESTIMATE"
    return ld


@tour_set("lifting", "Lifting plan – crane, load, hook and rigging", "test_loads.step", added="0.2.156",
          changed="0.2.192")
def build_lifting(b: Build):
    """Task 0231: a yard – an IBC on its pallet, a pump skid and a 20 ft container on the quayside – and an AT-40 on four
    crane mats behind the skid; the skid is the load. The camera looks from the other side of the skid, so the
    crane's carrier is never between the camera and the CoG (every stop checks that)."""
    import bpy

    from . import lifting
    sc = b.scene
    _yard(b)
    c = _yard_crane(b, os.path.join(DATA, "lifting", LIFT_CRANE), (1.0, 7.6))
    _camera(b, LIFT_VIEW, "Tour lifting", lens=35.0, points=_lifting_points(sc))
    _shot(b, "@lifting_place")
    ld = _skid_load(b)
    _close_camera(b, lifting.cog_world(ld), 5.5, "Tour lifting CoG", view=LIFT_VIEW)
    _shot(b, "@lifting_cog")
    a = lifting.hook_to(sc, c, lifting.above_load(sc, ld), ld)
    _check(a.ok, f"Hook to here: {a.reason}")
    _update()
    _camera(b, LIFT_VIEW, "Tour lifting hook", lens=35.0, points=_lifting_points(sc, LIFT_LOAD))
    _shot(b, "@lifting_hook")
    # task 0232: the rigging – the skid on a 4-leg chain set (its CoG off the middle: it tilts, the legs nearest the
    # CoG carry most), the empty container on the LF-20 lifting frame; the AT-40's rope reeved in its 4 falls
    ct = _container_load(b)
    sc.fresing.lifting.load_index = 0
    _rig_up(sc, ld, ct)
    _lift_rig(sc)
    _update()
    _camera(b, LIFT_VIEW, "Tour lifting rig", lens=35.0, points=_lifting_points(sc, LIFT_LOAD))
    _shot(b, "@lifting_rig")
    _lift_spreader(sc)
    _update()
    _camera(b, LIFT_VIEW, "Tour lifting spreader", lens=35.0, points=_lifting_points(sc, LIFT_CONTAINER))
    _shot(b, "@lifting_spreader")
    _lift_rest(sc)
    sc.fresing.lifting.load_index = 0


LIFT_CONTAINER, LIFT_CONTAINER_MASS = "20 FT CONTAINER.ASM", 2.3     # t: an empty 20 ft container (tare, estimate)
SKID_LEGS, SKID_CLEAR = 4.0, 4.6            # m: the skid's chain legs; the hook that far above its top
CONTAINER_LEGS, FRAME_LEGS, CONTAINER_CLEAR = 1.2, 3.0, 5.6


def _container_load(b: Build):
    from . import build, lifting, logic
    part = next(o for o in logic.descendants(build.model_roots(b.scene)[0])
                if o.get(build.PROP_NAME) == LIFT_CONTAINER)
    ld = lifting.new_load(b.scene, [part], "Container")
    ld.mass_mode, ld.mass_t, ld.source = "ENTERED", LIFT_CONTAINER_MASS, "ESTIMATE"
    return ld


def _rig_up(scene, skid, ct) -> None:
    """The gear of both loads (picked as a planner would; Hang picks nothing then)."""
    from . import lifting_rig
    lifting_rig.find_named(scene, skid)
    skid.sling, skid.shackle = "builtin:CH8-4L-13", "builtin:SH-4.75"
    skid.leg_length = SKID_LEGS
    lifting_rig.find_named(scene, ct)
    ct.sling, ct.shackle, ct.spreader = "builtin:CH8-2L-10", "builtin:SH-3.25", "builtin:LF-20"
    ct.leg_length, ct.top_length = CONTAINER_LEGS, FRAME_LEGS


def _lift_loads(scene):
    from . import lifting
    L = lifting.plan(scene)
    return {ld.name: ld for ld in L.loads}


def _lift_rest(scene) -> None:
    """Every load of the set back on the ground, unrigged (the stops before the rigging, and before each hang)."""
    from . import lifting_rig
    for ld in _lift_loads(scene).values():
        if ld.rig_state != "NONE":
            lifting_rig.remove(scene, ld)
    scene.fresing.lifting.load_index = 0


def _hang_one(scene, name: str) -> None:
    from . import lifting, lifting_rig
    _lift_rest(scene)
    L = lifting.plan(scene)
    ld = _lift_loads(scene)[name]
    L.load_index = list(L.loads).index(ld)
    c = L.cranes[0]
    p = lifting.above_load(scene, ld)
    p[2] += {"Pump skid": SKID_CLEAR, "Container": CONTAINER_CLEAR}[name] - ld.clearance   # the legs' room
    a = lifting.hook_to(scene, c, p, ld)
    _check(a.ok, f"Hook to here above the {name.lower()}: {a.reason}")
    lifting_rig.hang(scene, c, ld)


def _lift_rig(scene) -> None:
    _hang_one(scene, "Pump skid")


def _lift_spreader(scene) -> None:
    _hang_one(scene, "Container")


@tour_set("crane_setup", "Set up a crane – the KB-20 from its bare STEP", "lifting/KB-20/KB-20.step",
          added="0.2.161", changed="0.2.176")
def build_crane_setup(b: Build):
    """Task 0203: the built-in KB-20's bare STEP rigged through Set up a crane's own buttons, by names (the steps of
    a knuckle-boom crane), checked; the Set-up window would open on its Check step."""
    from . import crane_example, setup_crane
    sc = b.scene
    _yard(b)
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
@tour_set("lifting_make", "Lifting plan – a crane made from numbers", "test_loads.step", added="0.2.159",
          changed="0.2.217")
def build_lifting_make(b: Build):
    """Task 0204 / 0231: Make a crane… – the AT-100's numbers with 5 sections and a 50 m boom, made into a library next
    to the tour, placed on mats beside the yard's container and set up; its boom stands out, slewed over the yard (pose 'Working' + slew 90°) and
    the panel shows its radius and chart. No Hook to here: that is the 'lifting' set's stop."""
    import bpy

    from . import lifting, ops_lifting_make
    sc = b.scene
    _yard(b)
    lib = os.path.join(b.folder, "Lifting equipment")
    os.makedirs(lib, exist_ok=True)
    job = ops_lifting_make.make_now(ops_lifting_make.tour_spec(), lib, replace=True)
    c = _yard_crane(b, job.item_path, (9.0, 10.5))
    lifting.apply_pose(sc, c, "Working")
    v = lifting.values(sc, c)
    v["Slew"] = 90.0                           # the boom over the yard, not over the water
    lifting.set_values(sc, c, v)
    c.pose = ""
    _update()
    _camera(b, LIFT_VIEW, "Tour lifting make", lens=35.0, points=_lifting_points(sc, "20 FT CONTAINER.ASM"))
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
    v = lifting.values(scene, c)
    if abs(v.get("Slew", 0.0) - 90.0) > 0.5 or v.get("Telescope", 0.0) <= 0.0:
        raise ValueError(f"the boom is not slewed over the yard and out (slew {v.get('Slew')}, telescope "
                         f"{v.get('Telescope')})")
    ro = lifting.readout(scene, c)
    if isinstance(ro, str):
        raise ValueError(f"no reach readout: {ro}")
    if ro.radius < 8.0:
        raise ValueError(f"the boom reaches only {ro.radius:.1f} m (the pose 'Working' puts it out)")
    return (lifting.check_rig(scene) + f"; boom out: radius {ro.radius:.1f} m, chart '{ro.chart.name}'")


def _lifting_points(scene, only: str = ""):
    """Box corners of every part (the camera frames the whole yard); ``only``: the crane, the mats and that
    sub-assembly's parts (a closer picture of the lift)."""
    import numpy as np

    from . import build, logic
    keep = None
    if only:
        root = next(o for o in logic.descendants(build.model_roots(scene)[0]) if o.get(build.PROP_NAME) == only)
        keep = {o.name for o in logic.descendants(root)}
        keep |= {o.name for r in build.model_roots(scene)[1:] for o in logic.descendants(r)}
    pts = []
    for ob in list(build.iter_parts(scene)) + [o for o in scene.objects if o.name.startswith("Tour crane mat")]:
        if keep is not None and ob.name not in keep and not ob.name.startswith("Tour crane mat"):
            continue
        M = np.array(ob.matrix_world)
        for c in ob.bound_box:
            pts.append((M @ np.r_[np.asarray(c, float), 1.0])[:3])
    return np.array(pts)


def _cog_in_view(scene, with_hook: bool = False, load=None) -> str:
    """Task 0231: what the camera must show at a Lifting stop – the load's CoG is in the picture and nothing but the
    load itself is between the camera and the CoG (a ray from the camera to the CoG; study 0224 found the crane's own
    carrier deck in the way at every Lifting stop, which no check had caught); with ``with_hook`` the hook block is in
    the picture too. ValueError with the plain reason."""
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from . import lifting
    L = lifting.plan(scene)
    if not L.loads:
        raise ValueError("no load in the lifting plan")
    ld = load or L.loads[0]
    cam = scene.camera
    if cam is None:
        raise ValueError("the stop has no camera")
    cog = lifting.cog_world(ld)
    if cog is None:
        raise ValueError("the load has no CoG marker")
    cog = Vector(tuple(cog))
    mine = {o.name for o in lifting.load_parts(ld)}
    eye = cam.matrix_world.translation.copy()
    ray = cog - eye
    dist = ray.length
    dg = bpy.context.evaluated_depsgraph_get()
    ok, loc, _n, _i, ob, _m = scene.ray_cast(dg, eye, ray.normalized(), distance=dist + 0.01)
    drawn = ob is not None and (ob.get("fr_rigging") or ob.get("fr_reeved"))     # the app's slings and rope (0232)
    if ok and ob is not None and ob.name not in mine and not drawn and (loc - eye).length < dist - 0.02:
        raise ValueError(f"'{ob.get(build_mod().PROP_NAME, ob.name)}' is between the camera and the CoG "
                         f"({(loc - eye).length:.1f} of {dist:.1f} m from the camera)")
    uv = world_to_camera_view(scene, cam, cog)
    if not (0.02 < uv.x < 0.98 and 0.02 < uv.y < 0.98 and uv.z > 0):
        raise ValueError(f"the CoG is not in the picture (at {uv.x:.2f}, {uv.y:.2f})")
    out = f"the CoG is in view, nothing between it and the camera ({dist:.1f} m)"
    if with_hook:
        c = L.cranes[0] if L.cranes else None
        hook = lifting._hook_block_world(scene, c) if c is not None else None
        if hook is None:
            raise ValueError("the crane has no hook block")
        uh = world_to_camera_view(scene, cam, Vector(tuple(hook)))
        if not (0.0 < uh.x < 1.0 and 0.0 < uh.y < 1.0 and uh.z > 0):
            raise ValueError(f"the hook block is not in the picture (at {uh.x:.2f}, {uh.y:.2f})")
        out += ", the hook block too"
    return out


def build_mod():
    from . import build
    return build


def _check_lifting_place(scene):
    from . import lifting
    return lifting.check_rig(scene) + "; " + _cog_in_view(scene)


def _check_lifting_cog(scene):
    from . import lifting
    return lifting.check_cog(scene) + "; " + _cog_in_view(scene)


def _check_lifting_hook(scene):
    from . import lifting
    return lifting.check_example(scene) + "; " + _cog_in_view(scene, with_hook=True)


def _check_lifting_rig(scene):
    from . import lifting, lifting_rig, lifting_rope
    L = lifting.plan(scene)
    ld = _lift_loads(scene)["Pump skid"]
    r = lifting_rig.result(ld)
    _check(len(ld.points) == 4 and r is not None and r["tilt"] > 1.0, "the skid does not hang tilted on 4 legs")
    near = max(r["legs"], key=lambda lg: lg["force"])
    msg = lifting_rig.check_hang(scene, L.cranes[0], ld)
    return (msg + f"; most: leg {near['name']}; " + lifting_rope.check(scene, L.cranes[0]) + "; "
            + _cog_in_view(scene, with_hook=True, load=ld))


def _check_lifting_spreader(scene):
    from . import lifting, lifting_rig
    L = lifting.plan(scene)
    ld = _lift_loads(scene)["Container"]
    r = lifting_rig.result(ld)
    _check(r is not None and len(r["legs"]) == 6, "the container does not hang on the frame (2 top + 4 legs)")
    _check(all(c["status"] != "red" for c in r["checks"]), "a rigging check is red")
    return lifting_rig.check_hang(scene, L.cranes[0], ld) + "; " + _cog_in_view(scene, load=ld)

LOOK, MOTION, MACH, OUT = GROUPS

stop("materials", LOOK, "looks", "Ready-made materials and Wear",
     "The crane in eight ready-made materials: yellow gloss paint on boom and pedestal, painted cast iron on base "
     "and trolley (both with Wear: in a rendered picture their sharp edges look worn and corners a little dirty), "
     "ground steel pins, a black anodised cylinder barrel with a chrome rod, rubber wheels, blue anodised cover, "
     "zinc flake bolts. The camera is close on the worn base and trolley, where Wear shows.",
     where="3 Looks: the material groups, More materials…, Wear", check=_check_materials, since="0.2.47", changed="0.2.199")
stop("material_picker", LOOK, "looks", "Material picker, project list",
     "3 Looks, pick a group: above Material, 'This project's materials' shows four small pictures – chrome, blue "
     "paint RAL 5010, a diamond knurl, black rubber; a click on one gives the group that material. More materials… "
     "opens the Materials window: a picture of every material, filters Source / Material / Colour / Look on the left, "
     "the picked one large on the right with Use for <group>, Add to this project and Save as my material….",
     where="3 Looks > a group > This project's materials, More materials…", check=_check_picker, since="0.2.241")
stop("look_adjust", LOOK, "looks", "Adjust a look",
     "The blue anodised covers look duller and dusty, with a clear coat on top (Shine −0.5, Dirt 0.6, Clear coat "
     "0.8; render to see it). 3 Looks > Covers > More materials…: under 'Use for Covers' the box Adjust shows Shine, "
     "Metal ↔ paint, Wear and edges, Dirt, Relief and Clear coat with these values, and Reset; the picture on the right "
     "is made again a moment after a slider moves.",
     where="3 Looks > a group > More materials… > Adjust", check=_check_adjust, setup=_set_up_adjust,
     shot="Material picker, project list", since="0.2.245")
stop("faces", LOOK, "faces", "Painted faces",
     "The housing's two faces painted in CAD keep their own colours; one face of the cover is painted red by hand, "
     "the rest of the cover keeps its colour.", where="3 Looks > Paint faces", check=_check_faces, since="0.2.47")
stop("decals", LOOK, "decals", "Logos and stickers",
     "A yellow warning sticker and the text TEST TOUR lie flat on a 1.2 m door panel; a 'hot surface' sticker is "
     "wrapped round each 200 l drum, in a machine hall.", where="3 Looks > Logos & stickers", check=_check_decals, since="0.2.47")
stop("welds", LOOK, "welds", "Welds",
     "A small invented weldment: a blue painted fillet along the fin's foot (the paint over the ripples), a grey MAG "
     "weld with spatter under the gusset, a rusty one up its side, a stainless all-round weld with straw, purple and "
     "blue heat tint round the post, a pickled (matt, no tint) one round the branch, a bright aluminium saddle where "
     "the branch meets the tube and a butt joint ground flush to the extension plate. Beside each weld its ISO 2553 "
     "symbol with its number 1–7: 'a5' and a triangle on both sides of the line for the fin, a circle at the bend for "
     "the three all-round welds, the process number (135, 141, 131) in the tail. They show in the view only.",
     where="3 Looks > Welds (Weld symbols, Weld list…)", check=_check_welds, since="0.2.231", changed="0.2.240")
stop("welds_cad", LOOK, "welds", "Welds from the CAD file",
     "A second invented weldment, exported as Inventor does (all its solid welds one part 'Welds'), seen close up. Its "
     "six beads came in with the import as welds: a fillet along the rib's foot, four short pieces on its other side "
     "(one intermittent weld), a ring round the tube, one bead round the box post's four corners, a fillet with "
     "unequal legs at the stiffener and a V groove with its cap between the two blue plates. Each keeps its CAD shape "
     "and has the app's looks: painted blue like the plate, ripples showing through, a narrow tint strip beside it. "
     "In the list they have the import icon; open one: 'From the CAD file (by its name) · fillet a4 · legs 10 × 6 mm'.",
     where="3 Looks > Welds (From the CAD file)", check=_check_welds_cad, since="0.2.251")
stop("workspace_welding", LOOK, "welds", "The workspace Welding",
     "The same weldment, the Workspace row on the left panel now says 'Welding' (its small arrow open). The side "
     "panel shows only what welding needs: 1 Import, 2 Structure, 3 Looks with Welds open, 5 Scene & Render (light, "
     "camera, picture). 4 Motion, 6 Animation, the render queue and the CNC machine are gone; the welds are all still "
     "there, with their symbols. Open the Workspace list: Welding, Machine builder, Video producer and Houses are new, each with its own "
     "icon and a star. Pick All functions to have everything back.",
     where="The Workspace row on the left panel", since="0.2.242", shot="Welds", setup=_welding_open,
     check=_check_workspace_welding, auto=lambda ctx, scene, st: "")
stop("cutaway", LOOK, "cutaway", "Slice: the pedestal opens up",
     "A slice slides in from the front and takes away the front half of the crane's pedestal and boom: the cut faces "
     "are red with hatch lines, the steel pin shows inside the fork. The other parts are not cut. Look in rendered "
     "view: the grey solid view shows the parts whole.", where="3 Looks > Slice; 6 Animation (Move joint step "
     "with the joint 'Slice 1')", since="0.2.64", changed="0.2.170", animation=CUT_ANIM, at=1.0, play=True, check=_check_cutaway,
     auto="clip")
stop("measure", LOOK, "measure", "Measure in the 3D view",
     "Four labels on the crane's base: its thickness 'Between the planes 500.00 mm', two bolt holes 'Distance "
     "4 500.00 mm' with X / Y / Z, a hole's 'Ø 33.00 mm', and through the slice (the base's front half is gone) the cut "
     "face to the back face '1 500.00 mm'. Then click Measure on the top bar (or press M), click a face, another face: "
     "a new label. Corners, edge middles and hole centres snap; Shift does not.", where="Top bar > Measure (key M)",
     since="0.2.244", check=_check_measure)
stop("cut_look", LOOK, "mill", "Cut faces and raw stock",
     "The steel block has dark mill scale outside; the walls and floor of the milled slot look freshly machined "
     "(bright steel).", where="4 Motion > Milling > Cut faces; 3 Looks (the block's group)",
     animation="Mill a slot", at=1.0, check=_check_cut_look, since="0.2.47", changed="0.2.195")
stop("marine", LOOK, "marine", "Marine growth, streaks, concrete",
     "A yellow monopile stands in the open sea, seen through a cut-away down to its toe 9 m in the seabed: dark "
     "green-brown growth with a ragged top just below the waterline, a greenish splash zone with thin rust streaks "
     "above it; the transition piece above it is clean yellow with faint run-down streaks under its grey platform, and "
     "a light grey concrete mattress lies round the pile on the seabed.",
     where="3 Looks: Ready-made material… (Marine paint, growth below the waterline; Marine paint, run-down "
           "streaks; Concrete); 5 Scene & Render > Background: Open sea, cut-away with the ground", since="0.2.94",
     check=_check_marine, changed="0.2.196")
stop("finishes", LOOK, "finishes", "Finishes, carbon fibre and rust",
     "A board of 23 samples in their finishes, from the back row: diamond and straight knurled knobs, a rubber grip, a "
     "spun cap, a shaft with a faced end, a honed half bushing; a blue cross-hatch cup, speaker cloth, a black grille "
     "with holes, tread, perforated and expanded plates; scraped way, soft-touch arch, bead- and shot-blasted, "
     "hammertone and wrinkle blocks; anti-skid plate, VDI and leather cups, a spangled plate, an as-cast block. In "
     "front of them: carbon fibre on a cup, a tube with a cone, a U-shaped folded panel (plain weave, matte), a "
     "free-form hood and a plate – the weave runs on round the curves and across the folds without a seam – and a "
     "perlage disc; then the rust row: rusty bare steel, a cast iron block with rust patches, a blue painted block "
     "rusting at its worn edges with short streaks below, a galvanized block with white rust, and stainless and "
     "aluminium plates that stay clean. On the left a headphone-like set: knurled knob, spun cap, cross-hatch cups, "
     "leather cushions. Look in rendered view and zoom in: the patterns show up close and fade calmly further away.",
     where="3 Looks: a group's Material (Metal, Plastic & rubber, Paint …) and its own settings under it (Pitch, "
           "Angle, Metal, Kind …); Rust under Wear", since="0.2.229", changed="0.2.237", check=_check_finishes)
stop("served", LOOK, "served", "Served cable with marker bands",
     "Close up where the power cable leaves the carousel: black yarn served almost straight round the cable – fine "
     "grooves, some strands darker or lighter, a little dust – and two yellow painted marker lines that wind "
     "round the whole cable as one spiral, once round per metre, with ragged edges, the paint thinner in the grooves. "
     "Played, the lines run along with the cable, also on the coil.",
     where="4 Motion > Cables and paths: Look = Served cable (yarn)", animation=SPOOL_ANIM, play=True,
     since="0.2.116", check=_check_served, auto="clip", changed="0.2.230")
stop("vessel", LOOK, "vessel", "Vessel motion at sea",
     "The crane stands on the vessel deck in a calm beam sea, a person and an IBC tank beside it for scale: "
     "deck, containers, the person and the crane roll gently (about ±1.5°, once in 11 s), pitch a little and rise and "
     "fall with the long waves while the boom goes up. The sea, the sky and the camera stay put.",
     where="5 Scene & Render > Vessel motion; Props for scale", since="0.2.65", animation=VESSEL_ANIM,
     at=0.5, play=True, check=_check_vessel, auto="clip", changed="0.2.196")
stop("weather", LOOK, "weather", "Weather: grey North Sea",
     "The crane on the quay in grey North Sea weather: overcast, a strong breeze, drizzle slanting in the wind and "
     "haze in the distance; the crane and the quay look wet (darker, glossy, puddles on flat parts).",
     where="5 Scene & Render > Weather & time", since="0.2.88", check=_check_weather)
stop("weather_step", LOOK, "weather", "Weather changes in a video",
     "A Weather & time step: a clear late morning turns into a wet dusk over four seconds – the sun sinks and "
     "turns orange, clouds come in, the rain starts and the crane gets wet. Go shows it about halfway: the light is "
     "already lower and the rain is just starting.",
     where="6 Animation > Weather & time step", since="0.2.88", animation=WEATHER_ANIM, at=0.6, play=True,
     check=_check_weather, auto="clip", changed="0.2.199")
stop("start_scene", LOOK, "weather", "Save into start scene",
     "Weather & time shows a box under its tick: \"Build puts back the start scene 'Clear day': Weather Grey North Sea "
     "→ Clear Day …\" with the button Save into start scene. Clicking it would keep the grey weather at Build (leave it "
     "here: the tour's weather video starts from a clear day).", where="5 Scene & Render > Weather & time",
     since="0.2.125", shot="Weather: grey North Sea", check=_check_start_scene)
stop("night", LOOK, "weather", "Night shift",
     "The quay at night: a dark sky with stars and the moon, floodlights on masts light the crane, a damp sheen "
     "on the quay (turned up to 4 for the picture).", where="5 Scene & Render > Weather & time (Night shift)", since="0.2.88", check=_check_night, changed="0.2.199")
stop("wx_thunder", LOOK, "weather", "Thunderstorm in a video",
     "Change to Thunderstorm at the playhead (the weather lesson's last step): a clear day over the sea turns into a "
     "thunderstorm over four seconds – dark clouds, a downpour – and a lightning flash lights the whole quay while a "
     "bolt strikes in the distance. Go shows the moment of the flash.",
     where="5 Scene & Render > Weather & time > Change to … Add at playhead", since="0.2.228",
     animation="Weather", at=STORM_AT, play=True, check=_check_storm, auto="clip")
stop("wx_sunrise", LOOK, "weather", "Sunrise",
     "The quay just after sunrise: a low golden sun from the east, long shadows across the quay, a few clouds lit "
     "from below, dew on the crane.", where="5 Scene & Render > Weather & time > Presets (Sunrise)",
     since="0.2.228", check=_check_preset("SUNRISE", _sun_low(True)))
stop("wx_sunset", LOOK, "weather", "Sunset",
     "The quay at sunset: the sun low in the west, orange light on the crane's boom, long shadows.",
     where="5 Scene & Render > Weather & time > Presets (Sunset)", since="0.2.228",
     check=_check_preset("SUNSET", _sun_low(False)))
stop("wx_mist", LOOK, "weather", "Fog / sea mist",
     "Thick mist lying on the quay and the water: the far quay and the sea are gone, the crane's far end is paler "
     "than its foot. In a video banks of it drift by and the crane fades in and out.",
     where="5 Scene & Render > Weather & time > Presets (Sea mist); Sea mist", since="0.2.228",
     check=_check_preset("SEA_MIST", _mist_on))
stop("wx_hail", LOOK, "weather", "Hail / sleet",
     "A cold shower: white hail stones and sleet falling, small stones bouncing on the quay and the crane's top "
     "faces, grey light, everything wet, a little slush.", where="5 Scene & Render > Weather & time > Presets "
     "(Hail / sleet); Hail", since="0.2.228", check=_check_preset("HAIL", _hail_on))
stop("wx_heat", LOOK, "weather", "Hot and calm",
     "A hot afternoon without wind: bright sun, a pale warm haze over the far sea; in a render the horizon wavers "
     "with heat shimmer.", where="5 Scene & Render > Weather & time > Presets (Hot, calm); Heat", since="0.2.228",
     check=_check_preset("HOT_CALM", _heat_on))
stop("props", LOOK, "props", "Props for scale and people",
     "In a warehouse, beside the crane: three people – one standing in navy overalls and a yellow helmet, one pointing in an orange "
     "offshore coverall with reflective bands and gloves, one with both hands forward in office clothes and a "
     "yellow vest – then a container with ribbed walls, a pallet of taped boxes, a red and white barrier, an IBC "
     "tank in its cage, a rack of four gas bottles and a red tool trolley. Faces, fingers and shoe soles show close "
     "up; nothing floats or sinks into the floor.",
     where="5 Scene & Render > Props for scale (click a person for its pose and clothes)", since="0.2.124",
     check=_check_props, changed="0.2.199")
stop("looks", LOOK, HUB_SET, "Light looks",
     "The Dark studio look: a dark background with rim lights. The other looks are one click each in 5 Scene & Render > Light look.",
     where="5 Scene & Render > Light look", check=_check_looks, since="0.2.47")

stop("import_again", LOOK, "import", "Import again and Up axis",
     "Two copies of the test crane. The left one was imported as usual; the right one came from 1 Import > Imported "
     "models > Import again – the stored copy, in a second, nothing read – and its line's Up axis was set to Y up: it "
     "lies on its side, as a model drawn Y up in its CAD would stand. Imported models lists the crane with its parts, "
     "date and size; Z up / Y up on each model's line turns it back.",
     where="1 Import: the model's line (Up axis), Imported models", since="0.2.218", check=_check_import)
stop("joint", MOTION, HUB_SET, "Joint: the boom turns",
     "The boom turns up 35° about its pin and stops smoothly; everything on the boom goes with it. The luffing "
     "cylinder under it follows: its rod slides out and its eye stays on the pin under the boom.",
     where="4 Motion > Joints; 6 Animation", animation="Boom up", play=True, select=("BOOM",), check=_check_boom,
     auto="clip", since="0.2.47", changed="0.2.224")
stop("stack", MOTION, HUB_SET, "Stacked joints: boom + trolley",
     "The boom turns up while the trolley slides out along it: the two moves add up, the trolley stays on the "
     "boom.", where="4 Motion > Joints (the trolley's joint rides on the boom)", animation="Boom and trolley",
     play=True, select=("TROLLEY",), check=_check_stack, auto="clip", since="0.2.47", changed="0.2.224")
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
stop("lead_motions", MOTION, HUB_SET, "Lead motions: a slider each",
     "The crane shows every function: 'Boom up and out' (the boom goes up, then the trolley runs out), 'Boom up' and "
     "'Trolley out', each out and back, its name as a caption. Then click Lead motions on the top bar (right of the "
     "Fresing menu): one slider per function. Drag 'Boom up and out' – the boom goes up first, the trolley follows; "
     "▶ plays it, ▶ again plays it back; Back to start puts all at 0 %.", where="Top bar > Lead motions; 6 Animation "
     "(Lead motion step)", since="0.2.236", animation=LEAD_ANIM, play=True, check=_check_lead, auto="clip")
stop("explode", MOTION, HUB_SET, "Exploded view",
     "The crane's subassemblies are pulled apart outwards; Reset pose puts them back.",
     where="4 Motion > Poses & exploded views", check=_check_explode, since="0.2.47")
stop("cylinder", MOTION, "cylinder", "Cylinder: stroke drives the arm",
     "The rod comes out of the cylinder 450 mm and pushes the arm up; the rod's eye stays on its pin all the way and "
     "the barrel, with its oil ports and pipe, tilts about its own pin.",
     where="4 Motion > Cylinders", animation="Stroke out", play=True, check=_check_cylinder, auto="clip", since="0.2.47", changed="0.2.224")
stop("mechanism", MOTION, "linkage", "Mechanisms: lift, 4-bar, crank",
     "The scissor lift rises to 1.5 m with every arm following; in the middle the four-bar's crank turns once and "
     "its coupler, with the tool block, swings the rocker; on the right the crank turns once and the piston "
     "slides back and forth.", where="4 Motion > Mechanisms", animation="Lift and crank", play=True,
     check=_check_linkage, auto="clip", since="0.2.47", changed="0.2.199")
stop("waycover", MOTION, "waycover", "Way cover follows the axis",
     "The carriage slides 1000 mm along X on its rails and back; the five folded-sheet cover sections telescope out "
     "and in with it, each by its own share, over the rails and the ball screw.", where="4 Motion > Way covers", animation="X axis out and back", play=True,
     check=_check_waycover, auto="clip", since="0.2.47", changed="0.2.215")
stop("waycover2", MOTION, "waycover2", "Two way covers on one axis",
     "A cover on each side of the carriage: as it slides 1000 mm to the right the left cover opens and the right one "
     "closes, every section by its own share; the plates next to the carriage ride on it. And back.",
     where="4 Motion > Way covers", animation="Carriage across and back", play=True,
     check=_check_waycover_two, auto="clip", since="0.2.61", changed="0.2.215")
stop("hoses", MOTION, "hoses", "Hoses and a cable follow the arm",
     "The arm goes up and down and the slide travels: the three hydraulic hoses and the hanging cable bend along, "
     "their ends stay on the fittings and none gets longer or shorter.", where="4 Motion > Hoses and drag chains",
     animation=HOSES_ANIM, play=True, since="0.2.78", changed="0.2.211", check=_check_hoses, auto="clip")
stop("chains", MOTION, "chains", "Drag chains roll with the axes",
     "A short G-code program moves X, Y and Z: each axis' drag chain rolls over its bend, link by link, and its "
     "moving end stays on its bracket.", where="4 Motion > Hoses and drag chains", animation=CHAINS_ANIM, play=True,
     since="0.2.78", changed="0.2.215", check=_check_chains, auto="clip")
stop("cables", MOTION, "cables", "Cable over sheaves and rollers",
     "The winch drum is full of wire rope, layer on layer. The rope comes off it, goes over the two sheaves of the "
     "A-frame, through the V rollers and over the chute at 10 m/min: its strands run along, the drum turns and its "
     "top layer gets shorter wrap by wrap, and both sheaves and both rollers turn with it. Meanwhile the A-frame "
     "leans forward and back and the rope stays in its grooves.",
     where="4 Motion > Cables and paths", animation=CABLE_ANIM, play=True, since="0.2.80", check=_check_cables,
     auto="clip", changed="0.2.230")
stop("flex_avoid", MOTION, "flex_avoid", "A hose lies on a block",
     "Front: the lift goes down 400 mm and up again. The hose has 'Avoid other parts' on: where it would sag through "
     "the grey block it lies on its top and slides along it; its ends stay on their fittings and it keeps its length.",
     where="4 Motion > Hoses and drag chains > Avoid other parts", animation=AVOID_ANIM, play=True, since="0.2.225",
     check=check_flex_avoid, setup=_route_off, auto="clip")
stop("flex_route", MOTION, "flex_avoid", "A route shaped by a via point",
     "The same hose with one via point set by hand beside the block (Shape the route): it runs through that point "
     "at every frame, and the point rides down and up with the lift, part of the way, as the end it is nearer to.",
     where="4 Motion > Hoses and drag chains > Shape the route", animation=AVOID_ANIM, at=0.4, since="0.2.225",
     check=check_flex_route, setup=_route_on, auto="clip")
stop("drawn_hose", MOTION, "flex_drawn", "A drawn hose through two clips",
     "Front: a hydraulic hose that was drawn with four clicks – the valve block's fitting, two clips on the base, the "
     "arm's fitting. The arm goes up and down: the hose bends along, stays in its two clips on the base and on both "
     "fittings, and keeps its length.", where="4 Motion > Hoses and drag chains > Draw hose", animation=DRAWN_ANIM,
     play=True, since="0.2.180", changed="0.2.211", check=check_drawn_hose, auto="clip")
stop("drawn_chain", MOTION, "flex_drawn", "A drawn drag chain",
     "Left: the gantry's X chain was drawn with two clicks on its brackets; the app draws its links. X travels out "
     "and back: the chain rolls over its bend, link by link, and its moving end stays on its bracket.",
     where="4 Motion > Hoses and drag chains > Draw drag chain", animation=DRAWN_ANIM, play=True, at=0.5,
     since="0.2.180", changed="0.2.215", check=check_drawn_chain, auto="clip")
stop("drawn_cable", MOTION, "flex_drawn", "A drawn cable route",
     "Right: the wire rope was drawn by clicking the drum, the two sheaves and the chute. It runs at 10 m/min: the "
     "drum, the sheaves and the V rollers turn with it, and it stays in its grooves while the A-frame leans.",
     where="4 Motion > Cables and paths > Draw cable route", animation=DRAWN_ANIM, play=True, at=0.6,
     since="0.2.180", check=check_drawn_cable, auto="clip", changed="0.2.230")
stop("drawn_replace", MOTION, "flex_drawn", "Replaced CAD parts are hidden",
     "The CAD hose, the gantry's 24 CAD chain links and the CAD rope do not show: the drawn ones replace them – also "
     "in renders, the clash check and the web 3D model. Remove a drawn one and its CAD part shows again.",
     where="4 Motion > Hoses and drag chains > Replaces selected CAD part", shot="Tour: drawn hose, chain and cable",
     since="0.2.180", changed="0.2.215", check=check_drawn_replace)
stop("flex_kinds", MOTION, "flex_drawn", "Hose and cable kinds and sizes",
     "Behind the arm on the base, six drawn arches in three rows, one per kind: a black hydraulic hose with a white printed line, "
     "a steel-braided hose (a woven steel look), a blue pneumatic tube, a black spiral sleeve over a hose, a grey "
     "machine cable and a black power cable. The drawn rope on the right is a galvanised 16 mm wire rope (duller than bright steel).",
     where="4 Motion > Hoses and drag chains > Kind · Colour · Size", shot="Tour: drawn hose, chain and cable",
     since="0.2.182", changed="0.2.211", check=check_flex_kinds)
stop("chain_types", MOTION, "flex_drawn", "Drag chain types",
     "The drawn chain on the gantry is a closed chain now: lids top and bottom, a closed tube. Its Type can be "
     "open, closed, half-open (a lid on the outside of the bend) or steel; each rolls with X as before.",
     where="4 Motion > Hoses and drag chains > Type", animation=DRAWN_ANIM, play=True, at=0.5,
     since="0.2.182", changed="0.2.215", check=check_chain_types, auto="clip")
stop("spool", MOTION, "spool", "Drum and carousel spooling",
     "Left, the winch: the wire comes off the drum wrap by wrap and the level wind goes along with it, so the wire "
     "runs straight to its sheave. Right, the carousel: its top layer gets smaller turn by turn (paid out "
     "towards the rim) and the arm swings out so its guide stays over the turn being paid out. Then, fast: the drum "
     "winds its wire fully in – every layer is wire, with its climbs at the flanges – and pays it all out to its "
     "anchor; the carousel pays its cable all out (every layer cable, one after the other, down to its core) and "
     "winds it back in. No grey sleeve or ring under the top layer.",
     where="4 Motion > Drums and carousels", animation=SPOOL_ANIM, play=True, since="0.2.85", check=_check_spool,
     auto="clip", changed="0.2.230")
stop("tracks", MOTION, "tracks", "Tensioner tracks and a belt",
     "Front, the tensioner: the cable runs through at 15 m/min and the pads of both tracks run round their sprockets "
     "with it – the pads that hold the cable move exactly as fast as the cable. The top track lifts 150 mm (its pads "
     "keep running; the rods of its two lift cylinders slide up into the barrels on the portal) and comes back down "
     "to squeeze the cable 2 mm. Meanwhile the whole tensioner tilts 6° on its hinge and back, pushed up by the tilt "
     "cylinder under its deck: the tracks, their pads and the cable go with it and keep running. Behind, a belt of "
     "separate links runs round three pulleys of different size; all wheels turn with the chain.",
     where="4 Motion > Tracks and belts", animation=TRACKS_ANIM, play=True, since="0.2.87", check=_check_tracks,
     auto="clip", changed="0.2.177")
stop("sea_cable", MOTION, "sea_cable", "Cable into the sea",
     "The cable runs over the rollers and the horn at the stern and hangs in a curve down to the seabed 15 m below, "
     "seen through the cut-away behind the stern. It pays out at 60 m/min: its stripes run down the curve but stand "
     "still where it lies on the seabed, the seabed moves aft under the vessel, the touch-down stays 20 m behind the "
     "horn and the orange CPS set goes over the horn and down the curve on the cable. A label of four lines points "
     "at the touch-down: Lay data, the top tension, the layback and the speed (60 m/min while it pays out).",
     where="4 Motion > Cables and paths > Into the sea", animation=SEA_ANIM, play=True, since="0.2.91",
     check=_check_sea_cable, auto="clip", changed="0.2.196")
stop("vessel_work", MOTION, "vessel_work", "Vessel at work: wake and jets",
     "A blue workboat (a fine bow under a raised forecastle, a white wheelhouse) sails ahead, seen from close by off "
     "its port bow: a white wake trails behind its stern, fading and breaking up; its waves fan out "
     "behind the bow in a wedge each side (about 20° to the track) and white water rolls off the bow. After 3 s it "
     "slows to a stop and pushes sideways: the azimuths under the stern swing round, the wake fades, and white, boiling "
     "jets stream out from the port side – the bow thruster's and the azimuths' – while the propellers turn.",
     where="5 Scene & Render > Vessel at work; 6 Animation: Vessel at work step", animation=VESSEL_ANIM, play=True,
     since="0.2.127", check=_check_vessel_work, auto="clip", changed="0.2.196")
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
     since="0.2.95", check=_check_moving_cable, auto="clip", changed="0.2.196")
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
     "joint", since="0.2.99", changed="0.2.211", animation=MESH_ANIM, at=1.0, play=True, check=_check_mesh, auto="clip")

stop("lifting_place", MOTION, "lifting", "Lifting: a crane placed",
     "On a quayside yard – an IBC on its pallet, a pump skid and a 20 ft container – stands the built-in AT-40 sample "
     "crane, placed from 8 Lifting plan > Equipment and set up on its four outriggers, each on a timber crane mat "
     "(pose 'Set up': beams out, pads down). Its joints carry its name ('AT-40 · Slew', 'AT-40 · Luff' …); the panel "
     "shows the planning-aid line and the SAMPLE line.", where="8 Lifting plan > Equipment", since="0.2.156", check=_check_lifting_place,
     setup=_lift_rest)
stop("lifting_cog", MOTION, "lifting", "Lifting: the load and its CoG",
     "The pump skid is the load (8 Lifting plan > Load: 6 t, an invented estimate). The CoG symbol – a circle in "
     "black and white quarters, 'CoG' next to it – sits inside the skid, off the middle of its frame because the pump "
     "and the motor stand on one side, drawn on top of everything; the panel says '(computed)'.", where="8 Lifting plan > Load", since="0.2.156", check=_check_lifting_cog,
     setup=_lift_rest)
stop("lifting_hook", MOTION, "lifting", "Lifting: Hook to here, crane use",
     "Above the skid: the AT-40 slewed, luffed and telescoped so its hook block hangs plumb 2 m above the skid's "
     "top, over the CoG. Hook & capacity shows the radius, the hook height, the boom, the chart row (next longer "
     "radius), the gross load (6 t + the rigging picked for it + the 0.45 t hook block), the crane use in % with "
     "'Within entered limits' and the hoist line pull on its 4 falls.",
     where="8 Lifting plan > Hook & capacity", since="0.2.156", changed="0.2.192", check=_check_lifting_hook,
     setup=_lift_rest)
stop("lifting_rig", MOTION, "lifting", "Lifting: skid on a 4-leg sling",
     "The pump skid hangs on the AT-40's hook on a 4-leg grade 8 chain set (4 m legs, a 4.75 t bow shackle in each "
     "padeye – found by their names). Its CoG is off the middle (pump and motor on one side), so it hangs tilted a "
     "few degrees with the CoG straight under the hook; 8 Lifting plan > Rigging lists each leg's angle and force – "
     "the legs nearest the CoG carry most – and the checks: sling legs (two legs carry, C3) and each shackle (C4). "
     "The hoist rope runs in its 4 falls over 2 head and 2 block sheaves to the winch drum.",
     where="8 Lifting plan > Rigging", since="0.2.192", check=_check_lifting_rig, setup=_lift_rig)
stop("lifting_spreader", MOTION, "lifting", "Lifting: container on a frame",
     "The empty 20 ft container (2.3 t) hangs under the LF-20 lifting frame: two top legs from the hook to the "
     "frame, four short legs straight down to its top corner castings (found by name). Rigging shows the six legs "
     "– the four bottom ones nearly vertical – and the checks: the top legs (C2), the frame's WLL and each bottom leg "
     "and shackle (C4); none red.",
     where="8 Lifting plan > Rigging", since="0.2.192", check=_check_lifting_spreader, setup=_lift_spreader)

stop("crane_setup", MOTION, "crane_setup", "Set up a crane: KB-20 rigged",
     "The built-in KB-20's bare STEP made a lifting-plan crane through Set up a crane (8 Lifting plan > Equipment > Set "
     "up a crane… > Knuckle-boom crane): its slew, main boom, knuckle, five extensions, hoist with two hook swings and "
     "four stabiliser corners are app joints with their roles (4 Motion > Joints), its two cylinders, poses, masses and "
     "chart are in; the crane stands in its pose 'Working'. The Set-up window is on its step Check: nothing wrong.",
     where="8 Lifting plan > Equipment > Set up a crane…", since="0.2.161", check=_check_crane_setup)
stop("lifting_make", MOTION, "lifting_make", "Lifting: a crane from numbers",
     "On the yard stands 'AT-100 with 5 sections': made with 8 Lifting plan > Equipment > Make a crane… from the "
     "AT-100's numbers with 5 boom sections instead of 7 (boom 50 m fully out). It is set up on its outriggers and "
     "mats, its boom raised, slewed over the yard and telescoped out; the panel shows its radius and chart. Its boom "
     "has 5 sections (joints Telescope … Telescope 5) and the panel shows the SAMPLE line: its chart is invented. "
     "Make a crane… opens its form in a window of its own: it stays open while you click in the main window, can be "
     "dragged onto another screen and opens again where it was.",
     where="8 Lifting plan > Equipment > Make a crane…", since="0.2.159", changed="0.2.217",
     check=_check_lifting_make)

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
     "On the quay beside a 20 ft container (the crane stands out of the picture at the left) Anna (orange coverall) walks in carrying a red toolbox, her feet stepping without sliding. "
     "She stops by Ben, bends and puts the box on the floor; they turn to each other, shake hands and talk – "
     "nodding, taking turns, gesturing with their hands.",
     where="6 Animation > People (Example: two people meet, then Build)", since="0.2.128", animation=PEOPLE_ANIM,
     at=0.55, play=True, check=_check_people, auto="clip", changed="0.2.203")
# ---------------------------------------------------------------------------
# task 0292: Place and Remove
# ---------------------------------------------------------------------------

@tour_set("place", "Place and remove", "test_crane_a.step", added="0.2.219", changed="0.2.219")
def build_place(b: Build):
    """The crane with the crane lesson's joints, cylinder and animation, placed 1 m along X and turned a quarter turn
    with 2 Structure > Place; its trolley removed with Remove… (the trolley's joint went with it)."""
    import math

    from mathutils import Matrix

    from . import lesson, ops_place, place, remove
    sc = b.scene
    lesson.run(sc, "crane")
    _studio(b)
    root = _ob(sc, "TEST.CRANE")
    ops_place.set_lock(root, False)
    place.move(sc, [root], Matrix.Translation((1.0, 0.0, 0.0)) @ Matrix.Rotation(math.radians(90.0), 4, "Z"))
    remove.remove(sc, [_ob(sc, "TROLLEY.ASM")])
    _update()
    _camera(b, "ISO", "Tour view")
    _shot(b, "@place")


def _place_setup(scene):
    from . import panels
    try:
        panels.open_to("FRESING_PT_place")
    except Exception:  # noqa: BLE001 - the stop still opens
        pass


def _check_place(scene):
    from . import place
    root = _ob(scene, "TEST.CRANE")
    x, y, z, rx, ry, rz = place.numbers(scene, root, "MODEL")
    _check(abs(x - 1000.0) < 0.5 and abs(y) < 0.5 and abs(z) < 0.5, f"the crane is {x:.0f}, {y:.0f}, {z:.0f} mm from "
           "where it was imported, not 1000, 0, 0")
    _check(abs(rz - 90.0) < 0.05, f"the crane is turned {rz:.1f}°, not 90°")
    _check(place.is_placed(root), "the crane does not count as placed")
    return f"moved {x:.0f} mm, turned {rz:.0f}°"


def _check_remove(scene):
    from . import build, joints
    s = scene.fresing
    left = [o for o in scene.objects if o.get(build.PROP_NAME) in ("TROLLEY.ASM", "TROLLEY", "WHEEL")]
    _check(not left, f"the trolley is still there: {[o.name for o in left]}")
    _check([j.name for j in s.joints] == ["Boom"], f"the joints are {[j.name for j in s.joints]}, not only Boom")
    _check(all(joints.is_valid(j) for j in s.joints) and len(s.cylinders) == 1, "the boom's joint or the cylinder broke")
    n = sum(1 for o in build.iter_parts(scene))
    _check(n == 17, f"{n} parts left, not 17")
    return f"{n} parts left, joints {[j.name for j in s.joints]}"


stop("place", MOTION, "place", "Place: crane moved and turned",
     "The crane stands 1 m to the side of where it was imported and turned a quarter turn. 2 Structure > Place, with "
     "the crane selected, shows Model axes X 1000, Y 0, Z 0 and Turn Z 90 (World: where it stands). Its joints and "
     "cylinder moved with it: the boom still luffs about its pin.",
     where=places.where("FRESING_PT_place"), since="0.2.219", select=("TEST.CRANE",), check=_check_place,
     setup=_place_setup)
stop("remove", MOTION, "place", "Remove: the trolley is gone",
     "The crane has no trolley: it was removed with Remove… (the window listed 3 parts, 1 joint). The trolley's "
     "joint went with it; the boom's joint and the luffing cylinder still work. 2 Structure shows 17 parts.",
     where=places.where("FRESING_PT_structure") + " > Place > Remove…", since="0.2.219", shot="Place: crane moved and "
     "turned", select=("TEST.CRANE",), check=_check_remove)

# ---------------------------------------------------------------------------
# task 0293: Copy and paste with joints and mechanisms
# ---------------------------------------------------------------------------

@tour_set("copy", "Copy and paste", "test_crane_a.step", added="0.2.227", changed="0.2.227")
def build_copy(b: Build):
    """The crane with the crane lesson's joints, cylinder and animation, copied with Copy / Paste: a second crane
    beside it with its own joints "Boom (2)" and "Trolley (2)" and its own cylinder; the copy's boom is up 25°, the
    original's at its CAD place, so the two show they move by themselves."""
    import math

    from . import animation, copy, joints, lesson, ops_place
    sc = b.scene
    lesson.run(sc, "crane")
    animation.clear_keys(sc)
    _studio(b)
    p = copy.paste(sc, [_ob(sc, "TEST.CRANE")])
    ops_place.set_lock(_ob(sc, "TEST.CRANE (2)"), False)            # as Paste leaves it: ready for Place
    joints.set_value(joints.find(sc, "Boom (2)"), math.radians(25.0))
    copy.LAST.clear()
    copy.LAST.update(p)
    _update()
    _camera(b, "ISO", "Tour view")
    _shot(b, "@copy")


def _copy_setup(scene):
    from . import panels
    try:
        panels.open_to("FRESING_PT_place")
    except Exception:  # noqa: BLE001 - the stop still opens
        pass


def _check_copy(scene):
    import math

    from . import build, copy, cylinders, joints
    s = scene.fresing
    roots = {r.get(build.PROP_NAME): r for r in build.model_roots(scene)}
    _check(set(roots) == {"TEST.CRANE", "TEST.CRANE (2)"}, f"the models are {sorted(roots)}, not the crane and its copy")
    names = [j.name for j in s.joints]
    _check(names == ["Boom", "Trolley", "Boom (2)", "Trolley (2)"], f"the joints are {names}")
    _check(all(joints.is_valid(j) for j in s.joints) and len(s.cylinders) == 2
           and all(cylinders.is_valid(c) for c in s.cylinders), "a joint or cylinder of the copy is broken")
    a, c = roots["TEST.CRANE"], roots["TEST.CRANE (2)"]
    boom = [o for o in build.iter_parts(scene) if o.get(build.PROP_NAME) == "BOOM"]
    _check(len(boom) == 2 and boom[0].data is boom[1].data, "the copy's boom does not share its shape")
    up = math.degrees(joints.get_value(joints.find(scene, "Boom (2)")))
    _check(abs(up - 25.0) < 0.05 and abs(joints.get_value(joints.find(scene, "Boom"))) < 1e-6,
           f"the copy's boom is at {up:.1f}°, not 25° (the original's at 0°)")
    dx = c.matrix_world.translation.x - a.matrix_world.translation.x
    _check(dx > 1.0, f"the copy stands {dx * 1000:.0f} mm from the crane, not beside it")
    _check(c.get(copy.GROUP) and c.get(copy.GROUP) == a.get(copy.GROUP), "the copy is not in the crane's copy group")
    return f"2 cranes {dx * 1000:.0f} mm apart, joints {names}, copy's boom {up:.0f}°"


stop("copy", MOTION, "copy", "Copy: crane and its own joints",
     "Two cranes side by side: the right one is a copy made with Copy and Paste (right-click > Copy, then Paste or "
     "Ctrl+V). It has its own joints 'Boom (2)' and 'Trolley (2)' and its own cylinder 'Luffing cylinder (2)' (4 "
     "Motion): its boom is up 25°, the original's is down – they move by themselves. 2 Structure shows two models, "
     "'TEST.CRANE' and 'TEST.CRANE (2)'. Its parts share their shapes with the original.",
     where=places.where("FRESING_PT_place") + " > Copy / Paste", since="0.2.227", select=("TEST.CRANE (2)",),
     check=_check_copy, setup=_copy_setup)

stop("operator", MACH, "operator", "A person changes the tool",
     "The test mill stands in its own enclosure. Before the tool change the operator walks up, opens the two sliding "
     "doors by the left door's handle (the right door slides the other way), leans in, presses the release button "
     "with the left hand and takes the end mill out by its BT40 holder, lays it on the tool trolley, takes the ball "
     "mill, puts it in, closes the doors and walks away after the program. "
     "The hands stay on the holder and the handle; the feet do not slide; nobody walks through the machine. Each "
     "tool cuts a shallow strip into the block.",
     where="6 Animation > Run G-code program > Lines, tool changes … (Changed by: Person); 4 Motion > CNC machine > "
           "Tool changes > Person at the machine", since="0.2.132", changed="0.2.205", animation=OPERATOR_ANIM,
     at=0.45, play=True,
     check=_check_operator, auto="clip")
stop("gcode", MACH, "gantry", "G-code program runs the machine",
     "The gantry runs on its rails through a short program: lines, arcs, a tool change to T2 and drilling. The "
     "toolpath is drawn as a thin tube; the tool's tip follows it and cuts the block where the program goes into it: "
     "a 2 mm slot with an arc and two drilled holes, their faces with tool marks.",
     where="4 Motion > CNC machine; 6 Animation (Run G-code program); 4 Motion > Milling",
     animation="G-code", play=True, check=_check_gcode, auto="clip", since="0.2.47", changed="0.2.215")
stop("accel", MACH, "gantry", "Acceleration: slow short moves",
     "The tool runs 2 mm zigzag steps above the block: first blended (G64) – it slows at each corner but keeps going –, "
     "then the same steps back with exact stops (G61) – it stops at every corner –, then one long line where it speeds "
     "up, runs and slows down. 6 Animation shows the step's time with and without acceleration (with is clearly "
     "longer).", where="4 Motion > CNC machine > Machine (Speed up and slow down); 6 Animation (Run G-code program)",
     animation=ACCEL_ANIM, play=True, since="0.2.83", changed="0.2.215", check=_check_accel, auto="clip")
stop("tools", MACH, "tools", "Three tools with M6 and G43",
     "A Ø50 face mill faces a strip, a Ø10 end mill cuts a slot, a chamfer mill runs along its edge: three tools "
     "from the tool list, each in a BT40 holder, changed with M6 and measured with G43. No tool goes into the block "
     "where the program does not cut (the end mill is 28 mm longer than the face mill). An M6 without G43 for the "
     "new tool would get a line in the Build result and a row in the clash check.",
     where="4 Motion > CNC machine > Tools", animation="Three tools", at=1.0, check=_check_tools, auto="clip", since="0.2.47", changed="0.2.205")
stop("hand", MACH, "tools", "Tool change by hand (BT40)",
     "At a tool change a gloved hand takes the tool out by its BT40 holder and puts the next one in; for a longer "
     "tool the spindle first rises by the difference, then comes down to the program.", where="4 Motion > CNC machine > Tool changes (Manual, Show hand)", animation="Three tools",
     at=-1.0, check=_check_hand, since="0.2.47", changed="0.2.195")
stop("marks", MACH, "marks", "Tool marks on cut faces",
     "A close-up of the milled aluminium block. The faced strip shows the wide arcs of the Ø50 face mill, bulging the "
     "way it went; the pocket's floor shows the finer arcs of the Ø10 end mill; its walls show fine upright lines and "
     "a level line where the second depth starts; the drilled hole shows rings. Look in "
     "rendered view and orbit: the sheen swirls with the arcs. The marks are drawn 7 times further apart than real "
     "(Mark size) so they show.",
     where="4 Motion > Milling (Tool marks, Mark size, Strength)", since="0.2.73", changed="0.2.205", animation=MARKS_ANIM,
     at=1.0,
     check=_check_marks)
stop("atc", MACH, "atc", "Tool changer: 8-pocket carousel",
     "The tools stand in their pockets from the first frame; at each change the carousel turns the shortest way, "
     "the right pocket comes to the spindle and the old tool goes back to its own pocket.",
     where="4 Motion > CNC machine > Tool changes (Tool changer)", animation="Tool changer", play=True,
     check=_check_atc, auto="clip", since="0.2.47", changed="0.2.215")
stop("doublearm", MACH, "doublearm", "Double-arm tool change",
     "Three BT40 tools: at each Tn the 24-pot side magazine turns the next tool's pot to the arm and tips it down; "
     "at M6 the head goes up, the arm turns onto both tools, pulls them out, turns half round and pushes them in. The "
     "old tool goes into the pot the new one came from; no tool ever jumps or hangs in the air. Each tool cuts the "
     "block where the program goes into it: two shallow strips and a short plunge.",
     where="4 Motion > CNC machine > Tool changes (Double-arm)", animation="Double-arm changer", play=True,
     since="0.2.51", changed="0.2.207", check=_check_doublearm, auto="clip")
stop("rotary4", MACH, "rotary4", "4th axis: the bar turns",
     "A rotary table turns a round bar while the tool cuts a slot wrapped once round it, then mills a flat on top, "
     "turns the bar half round and mills the same flat underneath. The orange toolpath lies on the bar and turns "
     "with it.", where="4 Motion > CNC machine > Rotary axes (4th / 5th axis)", animation="4th axis", play=True,
     since="0.2.52", changed="0.2.207", check=_check_rotary4, auto="clip")
stop("rotary5", MACH, "rotary5", "5th axis: tilt and turn (TCP)",
     "The trunnion tilts the block 30° and the tool mills a pocket on its side, the table turns half round for the "
     "second pocket, then a groove is cut while the table turns 90°. With Tool follows the part the tool tip stays "
     "on the block's path the whole time.", where="4 Motion > CNC machine > Rotary axes (Kinematics: Tool follows "
     "the part)", animation="5th axis", play=True, since="0.2.52", changed="0.2.207", check=_check_rotary5, auto="clip")
stop("toolpath", MACH, "toolpath", "Make a toolpath: rough + finish",
     "The app made the program itself: the flat end mill T1 roughs the block level by level (zigzag, then once round "
     "the walls, ramping in), the ball end mill T2 finishes in lines across. The block turns into the part with its "
     "pocket, rounded boss and dome; the stock under the overhanging cap and in the hole stays.",
     where="4 Motion > Milling > Make a toolpath", animation="Toolpath", at=0.75, play=True, since="0.2.55",
     changed="0.2.205",
     check=_check_toolpath, auto="clip")
stop("chips", MACH, "mill", "Chips fly",
     "While the bit cuts the slot, aluminium-coloured chips fly out and land on the table, the clamps and the block.",
     where="4 Motion > Milling > Chips", animation="Mill a slot", play=True, check=_check_chips, auto="clip", since="0.2.47", changed="0.2.205")
stop("air", MACH, "air", "Air blast",
     "The bit cuts a pocket with air on (M7 … M9): chips are blown away from the cut; at the end the part is "
     "blown clean.", where="4 Motion > CNC machine > Air blast", animation="Pocket with air", at=0.6, play=True,
     check=_check_air, auto="clip", since="0.2.47", changed="0.2.205")

stop("coolant", MACH, "coolant", "Coolant (flood)",
     "The bit cuts a pocket with flood coolant (M8 … M9) at 15,000 rpm: two blue hoses squirt milky coolant at the "
     "tool; just before the tool the jets' ends bend round with the turn and break into a fine mist that swirls "
     "round it, and a fast, fine, flat spray flies off in the turning direction at the jets' height; the block "
     "gets a wet sheen; after M9 it dries.", where="4 Motion > CNC machine > Coolant",
     animation="Pocket with coolant", at=0.5, play=True, check=_check_coolant, auto="clip", since="0.2.48",
     changed="0.2.205")

stop("liquid", MACH, "liquid", "Coolant liquid on the machine",
     "The bit cuts a pocket and an open slot with flood coolant and 'Liquid on the machine' ticked: milky coolant "
     "fills the pocket and the slot, spills over the block onto the table, runs along the T-slots and off the "
     "table's ends into the chip tray, which runs to the drain at its front right corner. After M9 the pocket stays "
     "full. (It is worked out a moment after Build & play: the Coolant panel shows how far.)",
     where="4 Motion > CNC machine > Coolant (Liquid on the machine)", animation="Coolant liquid", at=0.8,
     play=True, check=_check_liquid, auto="clip", since="0.2.262")


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
     "Press Set-up window… (under the section tabs at the top of the Fresing panel, or in 4 Motion > CNC machine): a "
     "small window of "
     "its own opens with 'Set up a CNC mill', step 1 of 5 – the axes X, Y and Z, already picked on this machine (a "
     "green tick). Next goes through the spindle, the tool and the workpiece, the work zero and the G-code program; "
     "the buttons are the same as in the side panel. Drag the window anywhere, also onto a second screen, and click "
     "parts in the main window while it is open. The drop-down at its top switches to 'Set up a mechanism'.",
     where="Set-up window… under the section tabs; 4 Motion > CNC machine; 4 Motion > Mechanisms", since="0.2.152",
     changed="0.2.215",
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
     "The animation 'Finished video' has a title card, an end card, a caption 'The boom goes up', the tour logo, a "
     "TEST TOUR watermark, the logo as a picture card in a corner and a soft chord as music. They are put on in the "
     "rendered MP4 video: render it with the queue (Render queue stop).",
     where=f"{places.where('finishing')}; {places.where('brand')}; {places.where('cards')}; {places.where('music')}",
     animation="Finished video", check=_check_finishing, since="0.2.47", changed="0.2.189")
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
    from . import web3d_film                             # task 0252: the built camera animation gives the page a Film
    film = web3d_film.camera(scene) is not None
    out = web3d.export(scene, os.path.join(out_dir, "Crane web 3D.glb"), size=512, animation=film)
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
    _check(film and len(st.get("films") or []) == 1, "the page has no Film (the camera animation is built)")
    lead = st.get("lead") or {}                         # task 0310: the crane's lead motions as sliders
    want = [lm.name for lm in scene.fresing.lead_motions]
    _check([m["name"] for m in lead.get("motions", [])] == want,
           f"the page's Motions are {[m['name'] for m in lead.get('motions', [])]}, not {want}")
    _check(len(lead.get("joints", [])) == 2, "the page has no clip for the boom and the trolley")
    from ..core import web3d_faces as wf                # task 0135: the faces for measuring (the boom pin Ø100)
    faces = wf.read(data)
    _check(faces and out.get("face_bytes", 0) > 0, "the file has no faces for measuring")
    edges = wf.read_edges(data)                         # task 0219: the straight and round edges
    _check(sum(len(e) for e in edges.values()) > 0, "the file has no edges for measuring")
    _check("fr_tools" in open(out["html"], encoding="utf-8").read() or "partTools" in
           open(out["html"], encoding="utf-8").read(), "the page has no part tools")
    return (f"{out['text']}; the page: {os.path.basename(out['html'])} (Open page in the panel); "
            f"{len(st['views'])} saved views; Film {out.get('film_keys', 0)} of {out.get('film_frames', 0)} frames; "
            f"Motions: {len(lead['motions'])} sliders; "
            f"faces for measuring in {len(faces)} meshes, "
            f"{sum(len(e) for e in edges.values())} edges")


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
    _check(50.0 <= info.get("seconds", 0) <= 80.0, f"its animation lasts {info.get('seconds', 0):.0f} s")
    with open(demo.project_path(folder, __version__), "rb") as fh:
        head = fh.read(7)
    _check(head == b"BLENDER" or head[:4] == b"\x28\xb5\x2f\xfd", "the demo project file is not a Blender file")
    return (f"demo project {__version__}: {info['joints']} joints, '{demo.ANIM}' {info['seconds']:.0f} s "
            f"({info['frames']} frames)")

stop("web3d", OUT, HUB_SET, "Web 3D model",
     "This stop saves the crane as a web 3D model next to the tour. Press Open page in 5 Scene & Render > Web 3D "
     "model: your web browser shows the crane on a light background with its colours and shine; drag to turn it, "
     "scroll to zoom. The page is one file and also works without internet. On the right: the gear opens the "
     "settings (quality, live pictures a second, your graphics card's name, auto-turn, sun; give the crane a quick flick with the mouse and let go: it keeps turning), then Fullscreen, Reset "
     "view, Screenshot, Copy link, keys (?) and the eye that hides every control; bottom left one button per saved "
     "camera. A still crane draws nothing while you do not touch it. A red bar at the top only when the browser "
     "draws without the graphics card. On the left the part tools: Part info (click a part: a card with its group, "
     "and Round face Ø … for a pin or a hole), Measure (click the boom pin: Ø 100.0 mm; two flat faces: the distance "
     "between them; move the pointer close to an edge – it lights up orange – and click it: a straight edge gives its "
     "length, a hole's rim its Ø; two edges: the distance between them; the numbers never cover each other), Slice (C: Add slice, then click a face or X / Y / Z – the near side of the crane is cut away, the cut "
     "faces red; add a second slice, Edit one and drag its arrow or a yellow knob, Delete it with the ×) and Fade the "
     "rest (click a part: the rest goes see-through). The animation 'Camera rides and flies' is built, so the page "
     "plays it with a Film button (a film camera) at the end of the play bar: pressed, the page shows the motion through "
     "the video's camera – it rides on the boom, then flies round the crane watching the trolley; drag to leave the "
     "Film (the motion plays on, the button gets an orange ring), press it again to glide back. Bottom left, above the "
     "views: Motions (3) opens a slider per lead motion – 'Boom up and out', 'Boom up', 'Trolley out' – with ▶ and Back "
     "to start: drag 'Boom up and out' and the boom goes up, then the trolley runs out; then drag 'Boom up' – the boom "
     "follows and the trolley stays out. A slider pauses the animation; Play gives it back.",
     where="5 Scene & Render > Web 3D model", since="0.2.77", shot="Tour view", animation=CAMERA_ANIM,
     check=_check_web3d, changed="0.2.238")

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
TOOLBOX_TITLE = "Sample house – test tour"


def toolbox_folder() -> str:
    """The test tour's own Toolbox folder (task 0217), next to the tour project – never the real one."""
    import tempfile

    import bpy
    base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else tempfile.gettempdir()
    return os.path.join(base, "Toolbox (test tour)")


def _toolbox_setup(scene):
    """A house sent the way House Planner will send it, into the tour's own Toolbox folder; the app watches that
    folder until the job is over (then the real one again)."""
    import shutil
    from pathlib import Path

    from ..core import toolbox as tb
    from . import toolbox_inbox as ti
    root = Path(toolbox_folder())
    if (root / "toolbox-folder.json").is_file() and not tb.is_link(root):
        shutil.rmtree(root, ignore_errors=True)
    ti.use_folder(root, keep=root.parent / "Toolbox (test tour) kept", home_after=True, samples=4, photo_samples=4,
                  quick=True)
    tb.play_house_planner(root, Path(DATA) / "sample-house.hpscene", TOOLBOX_TITLE)
    ti.look()


def _check_toolbox(scene):
    """The tour's job: waiting (Bake now in the panel); after Bake now, baked and sent back. In the automatic runs (no
    window) only the waiting is checked: the PC check's line house.toolbox bakes and sends back."""
    import json
    from pathlib import Path

    import bpy

    from ..core import house_scene as hs
    from ..core import toolbox as tb
    from . import toolbox_inbox as ti
    root = Path(toolbox_folder())
    inbox = root / "tools" / tb.ME / "inbox"
    _check(inbox.is_dir(), "the tour's Toolbox folder is missing: press Go again")
    jobs = []
    for d in sorted(inbox.iterdir()):
        try:
            if json.loads((d / "job.json").read_text("utf-8")).get("title") == TOOLBOX_TITLE:
                jobs.append(d)
        except (OSError, ValueError):
            continue
    _check(jobs, "no house arrived in the tour's Toolbox folder: press Go again")
    d = jobs[-1]
    st = json.loads((d / "status.json").read_text("utf-8")) if (d / "status.json").is_file() else {}
    if st.get("state") == "waiting" and bpy.app.background:
        # the automatic runs (Test tour line, mode Tour) check that the house waits for Bake now; the bake itself is
        # the PC check's line house.toolbox (~40 s: run here too it pushed the PC check past its time on GitHub)
        _check(st.get("text", "").endswith("press Bake now"), f"the house does not wait for Bake now: {st}")
        _check([j.id for j in ti.waiting()] == [d.name], "the app does not show the house with Bake now")
        return "the house waits for Bake now (the PC check's line house.toolbox bakes it and sends it back)"
    _check(st.get("state") != "waiting", "the house waits: press Bake now in 5 Scene & Render > House from House "
           "Planner, then check again when it says Sent back to House Planner")
    _check(st.get("state") != "working", "it still bakes: check again when it says Sent back to House Planner")
    _check(st.get("state") == "done", f"the job ended {st.get('state')}: {st.get('text', '')}")
    reply = root / "tools" / tb.HOUSE_PLANNER / "inbox" / st.get("reply", "-")
    _check(reply.is_dir(), "no reply job in House Planner's inbox")
    job = json.loads((reply / "job.json").read_text("utf-8"))
    bake = reply / job["files"][0]["name"]
    bad = hs.structure_problems(str(bake), hs.read_scene(os.path.join(DATA, "sample-house.hpscene")))
    _check(not bad, "the bake package sent back is not right: " + "; ".join(bad[:2]))
    _check(not any(s.name.startswith("House –") for s in bpy.data.scenes), "the house's own scene is still there")
    return f"sent back to House Planner: {bake.name}, {bake.stat().st_size / 1024:.0f} KB"


stop("house", OUT, "house", "House from House Planner",
     "The made-up sample house from House Planner on a summer evening: a low sun from the north-west, long warm "
     "shadows across the plot, the terrace in front. 5 Scene & Render > House from House Planner lists the seasons "
     "and moments (Preview shows each one) and the bake of the summer morning this tour made (Show in folder: "
     "sample-house.hpbake next to the tour, for House Planner).",
     where="File > Import > House Planner scene; 5 Scene & Render > House from House Planner", since="0.2.92",
     check=_check_house, changed="0.2.152")
stop("house_toolbox", OUT, "house", "A house arrives by itself",
     "A house sent from House Planner waits at the top of 5 Scene & Render > House from House Planner: \"From House "
     "Planner: Sample house – test tour\" with Bake now and Not now. Press Bake now: a scene \"House – Sample house – "
     "test tour\" shows the house while it bakes (progress and Cancel in the panel), then the tour comes back and the "
     "panel says Sent back to House Planner. (The tour uses a Toolbox folder of its own next to the tour project, "
     "and bakes small: one moment, 4 samples.)",
     where="5 Scene & Render > House from House Planner", since="0.2.173", shot="House from House Planner",
     check=_check_toolbox, setup=_toolbox_setup, auto=lambda ctx, scene, st: "")

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
        # task 0294: Essentials first, the task workspaces, a star on every row of the list
        _check(workspaces.names()[0][0] == "Essentials", "Essentials is not first in the Workspace list")
        workspaces.switch(scene, "Sales")
        # task 0321: Sales moves joints (4 Motion > Joints shows) but does not add them; the project is not locked
        _check(not workspaces.panel_hidden(scene, "FRESING_PT_joints") and not workspaces.shows(scene, "joints.rotate")
               and workspaces.panel_hidden(scene, "FRESING_PT_structure")
               and not workspaces.panel_hidden(scene, "FRESING_PT_shots") and not lock.ON[0],
               "Sales does not show moving joints without adding them, saved scenes, an unlocked project")
        _check(hasattr(bpy.types, "FRESING_MT_workspaces") and hasattr(bpy.ops.fresing, "workspace_star"),
               "the Workspace list with its stars is missing")
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
     "On the left panel (left of the 3D view) the row under Live preview says 'All functions': the workspace. Its "
     "small arrow is open here: under "
     "'Functions in this project' every family of functions has a tick. Untick 'CNC machine' and 'Milling': their "
     "panels leave 4 Motion, the project stays as it is; tick them again and they are back. Pick 'Client view' in the "
     "list: only looking and rendering are left and no part can be clicked or deleted; pick 'All functions' again. "
     "The list starts with Essentials (where a new user starts) and has Sales, Quick render, Animator, Reviewer, Welding, "
     "Machine builder, Video producer and Houses for "
     "one job each; the star beside a workspace puts it on top of the list, above a line (click it again to take it "
     "away). "
     f"Sections 1 to {len(places.SECTIONS)} start folded: click a title to open it, Ctrl+click keeps only that one open, the tabs "
     "All · 1 … 8 under Make show one section at a time.",
     where="The Workspace row on the left panel", since="0.2.152", changed="0.2.242", shot="Tour view",
     check=_check_workspace, setup=_workspace_open, auto=lambda ctx, scene, st: "")
stop("make", OUT, HUB_SET, "Make: each output in a window",
     "At the top of the Fresing panel is Make: one row of six large icons – Picture, Product video, Turntable, 3D page, "
     "Animation and Queue (rest the mouse on one for its name; click Make for the list with names). Click Picture: a "
     "small window opens with the settings of 5 Scene & Render > Image size & render and a blue Render image button. "
     "On its left is a strip with the same six icons, Picture pressed: click 3D page and the same window shows the 3D "
     "page's settings. Drag the strip's right edge wider: the names show beside the icons. Drag the window anywhere, "
     "click in the 3D view: it stays open until you close it (× at its top). Click Picture again: no second window. "
     "The same list is under Make in the header of the 3D view.",
     where="Make, at the top of the Fresing panel; Make in the 3D view's header", since="0.2.152", changed="0.2.223",
     shot="Tour view", check=_check_make, auto=lambda ctx, scene, st: "")


def _check_render_view(scene):
    """Render this view (task 0308): a camera made where the view's eye is and taken away again – the scene's camera
    and everything else as before."""
    import bpy

    from . import ops_render_view
    _check(hasattr(bpy.ops.fresing, "render_view"), "the button Render this view is missing")
    cam = scene.camera
    _check(cam is not None and cam.type == "CAMERA", "the crane set has no camera to stand in for the view")
    before = (scene.camera, len(bpy.data.objects), len(bpy.data.cameras))
    aspect = scene.render.resolution_x / max(1, scene.render.resolution_y)
    state = ops_render_view.setup(scene, bpy.context, view=ops_render_view.stand_in(cam, aspect))
    try:
        made = scene.camera
        _check(made != cam and made.get(ops_render_view.VIEW_MARK), "no camera was made for the view")
        off = (made.matrix_world.translation - cam.matrix_world.translation).length
        _check(off < 1e-4, f"the view's camera stands {off * 1000:.1f} mm from the view's eye")
        lens = made.data.lens
    finally:
        ops_render_view.undo(scene, state)
    _check((scene.camera, len(bpy.data.objects), len(bpy.data.cameras)) == before,
           "Render this view left a camera behind or changed the active camera")
    return f"lens {lens:.1f} mm, nothing left behind"


stop("render_view", OUT, HUB_SET, "Render this view",
     "Under the Make row: Render this view. Turn and zoom the 3D view to any angle you like (no camera needed) and "
     "click it: the render window shows exactly what the view showed, at the Picture's size and quality (its shape "
     "fitted round the view, nothing of the view cut off), and the picture is saved as <project>_View_<date>_<time>. "
     "The active camera in 5 Scene & Render is the same as before and no new camera is in the list. In camera view "
     "(Numpad 0) it renders that camera.",
     where="Make, at the top of the Fresing panel (under the icons); Make in the 3D view's header", since="0.2.223",
     shot="Tour view", check=_check_render_view, auto=lambda ctx, scene, st: "")

stop("demo", OUT, HUB_SET, "Demo: Vessel in a wind park",
     "Help > Make demo project… opens a small window of its own; Make it there makes the demo 'Vessel in a wind park' "
     "in the background (a minute or two on your PC; "
     "the status bar shows how far). Then Help > Open demo project: an invented ship on the open sea in a wind park "
     "of nine turbines; 4 Motion lists 33 joints (the ship's thrusters, propellers, radars and deck crane, the park's "
     "turbines), 5 Scene & Render has the saved scene 'At the quay' and the saved cameras 'Stern thrusters' (under "
     "water: two azimuth thrusters, their propellers in nozzles), 'Hull side' (the bow with its name, draft marks and "
     "the black boot top), 'Deck crane' and 'At the seabed' (the power cable on the seabed, through the cut-away), and "
     "6 Animation > 'What it can do today' plays a video of about a minute (Build & play): the ship sails in and holds "
     "her place, her crane slews and lowers its hook, the rotors turn, night falls. This stop only checks that the "
     "demo is there.",
     where="Help menu (Make demo project…, Open demo project)", since="0.2.68", changed="0.2.217", shot="Tour view", check=_check_demo,
     auto=lambda ctx, scene, st: "")

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
     "disappears. Opening any project (this tour, the demo, your own) always shows the Fresing tab and the left panel "
     "(Live preview, Workspace, Learning hub …) at the left of the view. Live preview stays on or off as you left it when you go to another Learning hub project.",
     where="The 3D view's header (right end) while the side panel is hidden", since="0.2.150", changed="0.2.197",
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
     "At the top of the window, after Help, there is a menu Fresing: Open the Learning hub, What's new in this version, "
     "Show the Fresing panel, the demo project, the user guide, the PC check, Check for updates and the Welcome "
     "screen. What's new lists the new functions with Show in guide, and the new and changed test models with a tour "
     "of only those. In the Learning hub stops on the left panel new stops say \"New\" and changed ones \"Changed\" "
     "after an update.",
     where="The Fresing menu in the top bar (after Help)", since="0.2.155", shot="Tour view",
     check=_check_start_here, auto=lambda ctx, scene, st: "")

def _check_keys(scene):
    """Task 0253: Blender's keys swallowed outside Full access, F12 bound to the app, the right-click menu's entries."""
    import bpy

    from . import context_menu, lock
    _check(hasattr(bpy.ops.fresing, "blender_key") and hasattr(bpy.ops.fresing, "view_menu"),
           "the operators of the keys and the right-click menu are missing")
    _check(lock.keys_quiet(), "the tour project is in Full access: Blender's keys are not swallowed")
    _check(bpy.ops.fresing.blender_key.poll() and bpy.ops.fresing.key_render.poll(),
           "Blender's keys are not swallowed here")
    part = next((o for o in scene.objects if o.get("fr_name") == "BOOM"), None)
    _check(part is not None, "the boom is missing")
    target = context_menu.target_of(scene, part)
    return f"{len(lock.BLENDER_KEYS)} Blender keys swallowed; right-click on the boom: menu for {target.get('fr_name')}"


stop("keys", OUT, HUB_SET, "Keys and the right-click menu",
     "Click the boom, then press Delete, X, Shift+D or Ctrl+J: nothing happens to the crane, and the status bar at the "
     "bottom says \"That is a Blender key – Fresing > Show all of Blender gives you Blender's keys\". H still hides the "
     "boom, Alt+H shows it again. Right-click on the boom: a short menu – Zoom to it, Show in 2 Structure, Hide, Show "
     "only this, Add a label here, Add joint here… – try Zoom to it and Show only this (Show all brings the crane back). "
     "Right-click on empty space: Zoom to all, Show all. F12 renders a picture with the app (as Render image). Fresing > "
     "Show all of Blender: Delete deletes again and the right-click shows Blender's own menu; Back to the Fresing "
     "window takes them away again.",
     where="The 3D view (keys and right-click); Fresing > Show all of Blender", since="0.2.202", shot="Tour view",
     check=_check_keys, auto=lambda ctx, scene, st: "")

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
     "Fresing > My usage… (also at the end of Help) opens Fresing Settings on its tab My usage: what the app counted "
     "on this PC – nothing is sent anywhere: your most used functions with a pin each, where your time goes per stage "
     "(bars; only while you use the app – a played animation with nobody at the mouse adds nothing), and the "
     "time saved, marked as an estimate with how it is worked out. Use a button a few times (for example Render image "
     "twice): at the next start of the app it is on the favourites bar on the left panel; a click on it opens "
     "its section and points at the button. After 10 starts a panel you never used gets one quiet question at the "
     "top: Hide / Not now / Don't ask again.",
     where="Fresing menu > My usage…; the favourites bar on the left panel", since="0.2.158", changed="0.2.201",
     shot="Tour view", check=_check_usage, auto=lambda ctx, scene, st: "")


def _check_settings(scene):
    """Fresing Settings (task 0271): its ways in and every tab drawn (no window opens in the check)."""
    import bpy

    from . import ui_settings, ui_topbar
    _check("fresing.settings" in ui_topbar.entries(), "Settings… is not in the Fresing menu")
    _check(hasattr(bpy.ops.fresing, "settings_tab"), "the tab button is missing")
    drawn = ui_settings.draw_all(bpy.context)
    _check(drawn == list(ui_settings.KEYS), f"only these tabs draw: {', '.join(drawn)}")
    return f"{len(drawn)} tabs: " + ", ".join(t[1] for t in ui_settings.TABS)


stop("settings", OUT, HUB_SET, "Fresing Settings",
     "Fresing > Settings… (or the gear at the top of the left panel) opens one window with a row of tabs along its "
     "top: General, Side panel, Lessons, Backups, Updates, My usage, About. Click a tab: its page shows. Close the "
     "window with its X and open it again: it opens on the same tab. Drag it elsewhere, click in the main window: it "
     "stays open.",
     where="Fresing menu > Settings…; the gear on the left panel", since="0.2.201",
     shot="Tour view", check=_check_settings, auto=lambda ctx, scene, st: "")

def _check_keys_tab(scene):
    """Task 0295: Settings > Keys – the list from the live key lists, every group, a change and Reset (the user's own
    changed keys are put back as they were)."""
    import bpy

    from ..core import keys as core
    from . import keys, lock, prefs, ui_settings, ui_topbar
    _check("fresing.keys" in ui_topbar.entries(), "Keys… is not in the Fresing menu")
    _check("keys" in ui_settings.draw_all(bpy.context), "the tab Keys does not draw")
    rows = keys.rows()
    _check({r.group for r in rows} == set(core.GROUP_KEYS), "a group of keys is missing")
    p = prefs.get()
    if p is None:                     # no preferences (Blender as a module): the rules only, nothing stored
        _check(not core.check_new("copy", "M", {}, keys.own_now({}), []).ok, "a clash was not refused")
    else:
        was = p.key_changes
        try:
            keys.reset()
            _check(keys.change("measure_all", "K", {"ctrl": True, "alt": True}).ok,
                   "Ctrl+Alt+K for Measure was refused")
            _check(not keys.change("copy", "K", {"ctrl": True, "alt": True}).ok, "a clash was not refused")
            keys.reset()
        finally:
            p.key_changes = was
            lock.refresh_keys()
    own = sum(1 for r in rows if r.group == "own")
    return f"{len(rows)} keys in {len(core.GROUPS)} groups, {own} of them Fresing's own"


stop("keys_tab", OUT, HUB_SET, "All keys in one list",
     "Fresing > Keys… opens Fresing Settings on its tab Keys: the keys in groups – Move the view, Select, Fresing's "
     "own keys, Blender keys that still work and, greyed, Blender keys that do nothing outside Full access. Type "
     "render in the search field: only the render keys stay. Click F12 (Render the picture), press F9: the line under "
     "the title says it is now F9, F9 renders, F12 no longer does; close the app and start it again: still F9. Click "
     "Measure's M and press F9: refused, \"already Fresing's key for: Render the picture\". Reset all puts F12 back. Print key sheet "
     "opens one A4 page in the browser.",
     where="Fresing menu > Keys… (also Help > Keys…); Fresing Settings > Keys", since="0.2.256",
     shot="Tour view", check=_check_keys_tab, auto=lambda ctx, scene, st: "")

def _check_locations(scene):
    """Task 0272: Locations and Exports in Fresing Settings – what the tour reads only (the user's own folders and
    set-ups are never changed by the tour): both tabs draw, every kind has its folders, every output has its folder,
    and a set-up file made in a temporary folder reads back with its change list."""
    import bpy
    import tempfile

    from ..core import locations as L
    from . import locations, ui_settings
    drawn = ui_settings.draw_all(bpy.context)
    _check("locations" in drawn and "exports" in drawn, f"only these tabs draw: {', '.join(drawn)}")
    for op in ("loc_setup_add", "loc_setup_save", "loc_folder_add", "loc_place_add", "out_place"):
        _check(hasattr(bpy.ops.fresing, op), f"the button fresing.{op} is missing")
    folders = {k.key: locations.folders(k.key, include_off=True) for k in L.KINDS}
    _check(all(folders.values()), "a kind has no folder: " + ", ".join(k for k, v in folders.items() if not v))
    _check(bool(locations.output_dir(scene)), "the outputs have no folder")
    with tempfile.TemporaryDirectory(prefix="fr_tour_setup ") as tmp:
        a, b = os.path.join(tmp, "Ours.frsetup"), os.path.join(tmp, "Ours renamed.frsetup")
        L.write_setup(a, L.Setup(id="tour", name="Ours", version=1))
        L.write_setup(b, L.Setup(id="tour", name="Ours", version=2, locations={"logos": ["\\\\server\\Logos"]}))
        lines = L.changes(L.read_setup(a), L.read_setup(b))
    _check("Version 1 → 2" in lines, f"a renamed newer set-up gave {lines}")
    return (f"{len(L.KINDS)} kinds, {sum(len(v) for v in folders.values())} folders; "
            f"{len(locations.places())} export places; {len(locations.setups())} set-ups")


stop("locations", OUT, HUB_SET, "Locations and Exports",
     "Fresing > Settings…, the tabs Locations and Exports. Locations: Set-up files at the top (Add a set-up file…, "
     "Save as a set-up file…), Different from standard, then a fold per kind (STEP models, Materials, Logos …) with "
     "its folders – each with its badge (Company, Department, Mine). Exports: the export places, the default one "
     "ticked, Also save a copy to. 5 Scene & Render > Render image > Files: Save to shows the project's place.",
     where="Fresing menu > Settings… > Locations, Exports", since="0.2.210",
     shot="Tour view", check=_check_locations, auto=lambda ctx, scene, st: "")

def _check_fr_mark(scene):
    """Task 0279: the Fr mark in place of Blender's logo, its menu's lines."""
    from . import ui_topbar
    _check(ui_topbar.mark_shown(), "Blender's logo is still drawn at the left of the top bar")
    e = ui_topbar.mark_entries()
    _check(e == ["fresing.about", "fresing.settings", "TOPBAR_MT_blender"], f"the Fr menu's lines: {e}")
    for idname in e[:2]:
        _check(ui_topbar._has(idname), f"the operator {idname} is missing")
    return "Fr mark; menu: About Fresing Render…, Fresing Settings…, Blender"


stop("fr_mark", OUT, HUB_SET, "The Fr mark in the top bar",
     "At the far left of the top bar stands the green and white Fr mark (no Blender logo). Click it: a short menu "
     "with About Fresing Render…, Fresing Settings… and, under a line, Blender with Blender's own menu (Splash Screen, "
     "About Blender …). Switch the workspace (Full access, the Client view): the Fr mark stays.",
     where="the top bar, far left", since="0.2.209",
     shot="Tour view", check=_check_fr_mark, auto=lambda ctx, scene, st: "")


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
     "An unused panel's question (after 10 starts) offers Show me in the guide, Show me in the Learning hub and Add to my "
     "learning list beside Hide it (the Show me buttons leave the question open, with a tick, and do not list the function). Fresing > My learning list… shows the list: Guide, Tour, Done and a cross for each "
     "function, ticked by itself after you used it on 3 days. Right-click a button of any function > Add to my "
     "learning list. After an update, What's new has Add the new functions to my learning list. The What's next card "
     "may have one quiet line \"Next to learn: …\" with Learn and Not interested. My learning list opens in a window "
     "of its own that stays open beside your work; Esc with the mouse over it closes it.",
     where="Fresing menu > My learning list…; the question and the What's next card on the left panel",
     since="0.2.160", changed="0.2.232", shot="Tour view", check=_check_learn, auto=lambda ctx, scene, st: "")

def _check_lessons(scene):
    """Lessons (task 0230): the Learn window, the two lessons, and the hub made of the crane lesson's steps."""
    import bpy

    from ..core import functions
    from . import lesson, ui_topbar
    for op in ("learn_lessons", "lesson_start", "lesson_next", "lesson_do", "lesson_back", "lesson_stop"):
        _check(hasattr(bpy.ops.fresing, op), f"the button fresing.{op} is missing")
    _check("fresing.learn_lessons" in ui_topbar.entries(), "Learn… is not in the Fresing menu")
    for lid in ("crane", "mill", "weather"):
        les = lesson.LESSONS.get(lid)
        _check(les is not None, f"the {lid} lesson is missing")
        for k, st in enumerate(les.steps, 1):
            _check(st.function in functions.FUNCTIONS, f"{lid} step {k}: unknown function {st.function}")
    les = lesson.LESSONS[HUB_SET]
    done = sum(1 for st in les.steps if lesson.is_done(scene, st))
    _check(done >= len(les.steps) - 1, f"only {done} of the crane lesson's {len(les.steps)} steps are in this project")
    return (f"crane lesson {len(les.steps)} steps ({done} done in this project), mill lesson "
            f"{len(lesson.LESSONS['mill'].steps)} steps, weather lesson {len(lesson.LESSONS['weather'].steps)} steps")


stop("lessons", OUT, HUB_SET, "Learn: Show me, Build it",
     "Fresing > Learn… lists the learning sets. Crane, Milling a slot and Weather have three buttons: View opens this test "
     "tour at the set, Show me opens a new project with the plain model and the app does each step itself – the "
     "button glows, a card beside the part says what happens, Next goes on (or tick Play on) – and Build it yourself "
     "lets you do each step: it goes on by itself once the project shows the step done. The other sets say 'Lesson "
     "coming'. Learn… is a window of its own: click in the main window and it stays open, drag it onto another "
     "screen, close it with Close or its X.",
     where="Fresing menu > Learn…; the Learning hub switch and the Lesson panel on the left panel",
     since="0.2.189", changed="0.2.228", shot="Tour view", check=_check_lessons, auto=lambda ctx, scene, st: "")



def _backup_setup(scene):
    """Task 0246: a backup of the tour project, made now (as the timer does after 5 minutes of work)."""
    from . import backups
    backups.make(scene, force=True)


def _check_backups(scene):
    import bpy

    from ..core import backups as core
    from . import backups, ui_topbar
    _check("fresing.backups_window" in ui_topbar.entries(), "Restore a backup… is not in the Fresing menu")
    _check(bool(bpy.data.filepath), "the tour project has no file: no Backups folder next to it")
    found = backups.project_backups()
    _check(bool(found), "no backup of the tour project: " + (backups._S.get("last_reason") or "none was made"))
    folder = os.path.dirname(found[0].path)
    _check(folder == core.folder_next_to(bpy.data.filepath), f"the backup is not next to the project but in {folder}")
    others = [n for n in os.listdir(folder) if core.parse(n, core.project_name(bpy.data.filepath)) is None]
    _check(not others, f"other files in the Backups folder: {others}")
    return f"{len(found)} backup(s) of the tour project, {core.size_text(core.total_size(found))}"


stop("backups", OUT, "faces", "Automatic backups",
     "Fresing > Restore a backup… opens a window of its own (it stays open while you work) listing a backup of this "
     "tour project made just now (Today and the time, its size), with Restore and a folder button. Restore keeps your work as a backup first, then opens the backup. In Edit > "
     "Preferences > Add-ons > Fresing Render the box Automatic backups has the switch, every 5 minutes, keep the last 5 "
     "and one a day for 7 days.",
     where="Fresing menu > Restore a backup…; Edit > Preferences > Add-ons > Fresing Render > Automatic backups",
     since="0.2.187", changed="0.2.217", shot="Painted faces", check=_check_backups, setup=_backup_setup)

# ---------------------------------------------------------------------------
# every machining stop: the block shows what the program does (task 0223)
# ---------------------------------------------------------------------------

#: the sets of a CNC mill or a milling bit: their stops also check the cut (marks on every cut face, every move
#: through the block cut, no program running through a block that nothing cuts)
MILLING_SETS = ("mill", "gantry", "atc", "doublearm", "rotary4", "rotary5", "toolpath", "tools", "marks", "air",
                "coolant", "liquid", "operator")


def check_milling(scene) -> str:
    """The milled block shows what the program does: every cut face has tool marks, the cut faces' material draws
    them, every move through the block took material away, and no program runs through a block nothing cuts. Raises
    with the reason; returns a short note."""
    from . import machining
    f, sub = scene.frame_current, scene.frame_subframe
    try:
        a = machining.audit(scene)
    finally:
        if (scene.frame_current, scene.frame_subframe) != (f, sub):
            scene.frame_set(f, subframe=sub)
    bad = machining.audit_problems(a)
    _check(not bad, "; ".join(bad))
    if not a["set_up"]:
        return ""
    return (f"cut {a['cut_mm2']:,.0f} mm², all with tool marks ({a['route']}); every move through the block cut "
            f"({a['points']:,} tip points)")


def _and_milling(check):
    def both(scene):
        note = check(scene)
        more = check_milling(scene)
        return "; ".join(x for x in (note, more) if x)
    both.__name__ = getattr(check, "__name__", "check")
    both.milling = True
    return both


for _st in STOPS:
    if _st.set in MILLING_SETS and _st.check is not None and not getattr(_st.check, "milling", False):
        _st.check = _and_milling(_st.check)
del _st

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
        raise RuntimeError(f"the tour project '{os.path.basename(path)}' is missing: make the Learning hub again "
                           "(Help > Make the Learning hub)")
    bpy.ops.wm.open_mainfile(filepath=path)
    return True
