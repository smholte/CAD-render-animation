"""G-code programs drive the machine (task 0026): the CNC machine set-up and the "Run G-code program" step.

The machine (4 Motion > CNC machine, ``scene.fresing.cnc``):

    X, Y, Z     three slide joints; each moves the tool or the workpiece (found from what they carry).
                The program's +X is the direction the tool moves *relative to the workpiece*; by default the
                one closest to the model's +X (+Y, +Z), "Reverse" turns it round.
    spindle     a rotate joint (a motor) that turns as S / M3 / M4 / M5 say
    tool        the part in the spindle; its tip is the point the program steers (LinuxCNC with G43)
    workpiece   and the work zero on it: a corner or centre of its box (in the machine's axes), or a clicked
                point, plus a shift. Shown as arrows ("FR work zero", a child of the workpiece).
    machine zero  the X/Y/Z joint values at G53 X0 Y0 Z0 (and G28): the CAD position unless set
    tools       T number -> a part of the model (a tool in the carousel) or a simple shape from its sizes

Machine coordinates (mm) and joint values (m) are linked by  value = home + sign * machine / 1000  per axis,
and the work zero (G54) is the machine position at which the tool's tip touches the work zero. The reader
(``core/gcode.py``) turns the program into machine coordinates; the bake puts a key on the three joints at
the start and end of every move and along arcs (every frame, and as often as a chord error of 0.002 mm
needs), so the joints move exactly as the program says between the keys too.

Tool changes (M6, task 0041, toolchange.py): a copy of the new tool's part (or a simple shape) appears in the
spindle at the swap moment; the part in the carousel disappears while it is in the spindle. Manual: the head goes to
the change position, pauses (optionally a hand swaps the tool) and comes back. ATC: tools in pockets, the carousel
turns, the spindle leaves the old tool in its pocket and takes the new one; an animation of the rest of the changer
can play at every M6, split at its swap moment (its steps are added to the video; the program waits for it).

Toolpath: one object "FR toolpath" (a child of the work zero, so it moves with the workpiece) with the path
as edges and a Geometry Nodes modifier that makes thin tubes: cutting moves orange, already cut green
(compared with the scene's frame, no Python), rapids dashed blue.
"""

from __future__ import annotations

import hashlib
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import gcode as core
from ..core import machining as mcore
from . import build, joints

MM = 0.001
TAG = "fr_cnc"                       # on objects, meshes, materials and node groups the CNC set-up makes
COLLECTION = "FR CNC"
ZERO_NAME = "FR work zero"
PATH_NAME = "FR toolpath"
NODE_GROUP = "FR toolpath tubes"
PATH_RADIUS = 0.4 * MM
DASH, GAP = 3.0, 2.0                # mm: rapids are drawn as dashes this long, with gaps this long
KEY_TOL = 0.002                      # mm: chord error allowed between two keys on an arc
SLOW_TURN = 1.0 / 7.0                # "Looks right": at most this much of a turn per picture
TEXT_PREFIX = "FR program "
WORLD_AXES = (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))

_CACHE: dict = {}                    # program key -> core.Program
_INFO: dict = {}                     # program signature + step settings -> summary for the panel (info_key)


class SetupError(RuntimeError):
    """The CNC machine is not set up (the message says what is missing, in plain words)."""


def settings(scene):
    return scene.fresing.cnc


def label(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else "-"


# ---------------------------------------------------------------------------
# the machine
# ---------------------------------------------------------------------------

def axis_joint_names(c) -> tuple:
    return (c.x_joint, c.y_joint, c.z_joint)


def _carries(j, ob) -> bool:
    """True when joint ``j`` moves ``ob`` (``ob`` hangs under its motion empty)."""
    p = ob
    while p is not None:
        if p is j.motion:
            return True
        p = p.parent
    return False


def _rest_tip(ob):
    """(tip, axis) of a tool part in its own space; the axis points from the tip into the holder."""
    from . import machining
    key = ("tip", ob.name, ob.data.name if ob.data else "", len(ob.data.vertices) if ob.data else 0)
    hit = _CACHE.get(key)
    if hit is None:
        info = machining.detect(ob, snap=False)
        hit = (Vector(info["tip"]), Vector(info["axis"]).normalized(), info["tool"])
        _CACHE[key] = hit
    tip, axis = machining.on_turning_axis(ob, hit[0], hit[1])   # on the spindle's axis (task 0049)
    return tip, axis, hit[2]


def tool_frame(ob) -> Matrix:
    """The tool's tip frame in its own space: origin at the tip, Z along the tool (into the holder)."""
    tip, axis, _t = _rest_tip(ob)
    rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    return Matrix.Translation(tip) @ rot


class Machine:
    """The set-up worked out for the current pose (see the module's docstring)."""

    def __init__(self, scene):
        c = settings(scene)
        s = scene.fresing
        self.scene = scene
        self.joints = []
        for letter, name in zip("XYZ", axis_joint_names(c)):
            j = s.joints.get(name) if name else None
            if j is None:
                raise SetupError(f"Pick the {letter} joint in 4 Motion > CNC machine" if not name else
                                 f"The {letter} joint '{name}' is gone: pick it again")
            if j.kind != "SLIDE":
                raise SetupError(f"'{j.name}' turns: the {letter} axis needs a slide joint")
            if j.follows:
                raise SetupError(f"'{j.name}' follows another joint: the {letter} axis needs a joint that moves "
                                 "by itself")
            if not joints.is_valid(j):
                raise SetupError(f"The {letter} joint '{j.name}' is broken")
            self.joints.append(j)
        if len({j.name for j in self.joints}) < 3:
            raise SetupError("X, Y and Z must be three different joints")
        self.tool = c.tool
        self.workpiece = c.workpiece
        if self.tool is None:
            raise SetupError("Click the tool in the spindle, then press Tool")
        if self.workpiece is None:
            raise SetupError("Click the workpiece, then press Workpiece")
        rel = []
        for letter, j in zip("XYZ", self.joints):
            t, w = _carries(j, self.tool), _carries(j, self.workpiece)
            if t == w:
                raise SetupError(f"'{j.name}' ({letter}) moves {'both the tool and' if t else 'neither the tool nor'}"
                                 " the workpiece")
            _o, d = joints.axis_world(j)
            rel.append(d if t else -d)
        self.moves_tool = [_carries(j, self.tool) for j in self.joints]
        self.auto = [1.0 if r.dot(w) >= 0 else -1.0 for r, w in zip(rel, WORLD_AXES)]
        rev = (c.x_reverse, c.y_reverse, c.z_reverse)
        self.sign = [a * (-1.0 if r else 1.0) for a, r in zip(self.auto, rev)]
        e = [r * s_ for r, s_ in zip(rel, self.sign)]
        ex = e[0].normalized()
        ey = (e[1] - ex * e[1].dot(ex)).normalized()
        ez = ex.cross(ey)
        d = ez.dot(e[2].normalized())
        if abs(e[0].normalized().dot(e[1].normalized())) > 0.02 or abs(d) < 0.999:
            if d < -0.999:
                raise SetupError("X, Y and Z do not make a right-handed machine: tick Reverse on one axis "
                                 "(usually Z: +Z must lift the tool)")
            raise SetupError("The X, Y and Z joints are not at right angles to each other")
        self.rot = Matrix((ex, ey, ez)).transposed()           # columns: the program's axes in the world
        self.zero = self._zero_point(c)                         # world
        tip_world = self.tool.matrix_world @ _rest_tip(self.tool)[0]
        t_local = self.rot.transposed() @ (tip_world - self.zero)
        self.values = [joints.get_value(j) for j in self.joints]
        self.home = list(c.home) if c.home_set else [0.0, 0.0, 0.0]
        # joint values with the tip on the work zero, and that point in machine coordinates (G54)
        v_wz = [v - s_ * t for v, s_, t in zip(self.values, self.sign, t_local)]
        self.g54 = tuple(s_ * (v - h) / MM for s_, v, h in zip(self.sign, v_wz, self.home))
        self.rapid = (c.rapid_x, c.rapid_y, c.rapid_z)

    def _zero_point(self, c) -> Vector:
        wp = self.workpiece
        if c.zero_mode == "POINT":
            p = wp.matrix_world @ Vector(c.zero_point)
        else:
            co = _world_points(wp)
            loc = co @ np.array(self.rot)                      # coordinates along the program's axes
            lo, hi = loc.min(axis=0), loc.max(axis=0)
            mid = (lo + hi) / 2
            x, y = {"TOP_CENTRE": (mid[0], mid[1]), "BOTTOM_CENTRE": (mid[0], mid[1]),
                    "TOP_FL": (lo[0], lo[1]), "TOP_FR": (hi[0], lo[1]), "TOP_BL": (lo[0], hi[1]),
                    "TOP_BR": (hi[0], hi[1])}[c.zero_mode]
            z = lo[2] if c.zero_mode == "BOTTOM_CENTRE" else hi[2]
            p = self.rot @ Vector((float(x), float(y), float(z)))
        return p + self.rot @ Vector(c.zero_shift)

    def values_for(self, m) -> tuple:
        """Joint values (m) for a machine position (mm)."""
        return tuple(h + s_ * x * MM for h, s_, x in zip(self.home, self.sign, m))

    def machine_of(self, values) -> tuple:
        return tuple(s_ * (v - h) / MM for s_, v, h in zip(self.sign, values, self.home))

    def zero_matrix(self) -> Matrix:
        return Matrix.Translation(self.zero) @ self.rot.to_4x4()

    def describe_axes(self) -> list:
        out = []
        for letter, j, s_, t in zip("XYZ", self.joints, self.sign, self.moves_tool):
            out.append(f"{letter}: '{j.name}' moves the {'tool' if t else 'workpiece'}"
                       + ("" if s_ * (1 if t else -1) > 0 else " (joint's + = program's -)"))
        return out


def _world_points(ob) -> np.ndarray:
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mw = np.array(ob.matrix_world)
    return co @ mw[:3, :3].T + mw[:3, 3]


def machine(scene) -> Machine:
    return Machine(scene)


def _first_value(j) -> float:
    """The joint's value on frame 1: its key there once an animation is built, else its value now."""
    ad = j.motion.animation_data if j.motion is not None else None
    act = ad.action if ad is not None else None
    if act is not None and act.get("fr_anim"):
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    fc = cb.fcurves.find(f'["{joints.VALUE}"]', index=0)
                    if fc is not None:
                        return fc.evaluate(1.0)
    return joints.get_value(j)


def start_point(mach: Machine | None):
    """Where the machine is when the animation starts (machine coordinates, mm): a program step starts from
    there. (The same whatever frame is shown, so the step's length does not change while scrubbing.)"""
    return mach.machine_of([_first_value(j) for j in mach.joints]) if mach is not None else None


def problem(scene) -> str:
    """'' when the machine is set up, else what is missing."""
    try:
        Machine(scene)
    except SetupError as exc:
        return str(exc)
    return ""


def find_axes(scene) -> list[str]:
    """Pick X, Y, Z (slide joints closest to the model's axes) and the spindle (a motor, else a rotate joint
    about the Z direction that carries the tool). Returns what was set, in words."""
    c = settings(scene)
    s = scene.fresing
    slides = [j for j in s.joints if j.kind == "SLIDE" and not j.follows and joints.is_valid(j)]
    done, used = [], set()
    for letter, w, attr in zip("XYZ", WORLD_AXES, ("x_joint", "y_joint", "z_joint")):
        best, score = None, 0.9
        for j in slides:
            if j.name in used:
                continue
            _o, d = joints.axis_world(j)
            if abs(d.dot(w)) > score:
                best, score = j, abs(d.dot(w))
        if best is not None:
            used.add(best.name)
            c["_busy"] = True
            setattr(c, attr, best.name)
            del c["_busy"]
            done.append(f"{letter} = '{best.name}'")
    rot = [j for j in s.joints if j.kind == "ROTATE" and not j.follows and joints.is_valid(j)]
    spin = [j for j in rot if j.is_motor] or [j for j in rot if abs(joints.axis_world(j)[1].z) > 0.9
                                              and (c.tool is None or _carries(j, c.tool))]
    if spin:
        c["_busy"] = True
        c.spindle_joint = spin[0].name
        del c["_busy"]
        done.append(f"spindle = '{spin[0].name}'")
    setup_changed(scene)
    return done


def use_tool(scene, ob) -> None:
    c = settings(scene)
    _rest_tip(ob)                                   # raises RuntimeError when it has no shape
    c["_busy"] = True
    c.tool = ob
    c.tool_uid = ob.get(build.PROP_UID, "")
    del c["_busy"]
    setup_changed(scene)


def use_workpiece(scene, ob) -> None:
    c = settings(scene)
    c["_busy"] = True
    c.workpiece = ob
    c.workpiece_uid = ob.get(build.PROP_UID, "")
    del c["_busy"]
    setup_changed(scene)


def snap_point(ob, world: Vector, part_size: float | None = None) -> Vector:
    """The clicked point, moved onto the nearest corner (mesh vertex) when one is within 3 % of the part's
    size (at most 5 mm). Returns a point in the part's own space."""
    local = ob.matrix_world.inverted() @ world
    me = ob.data
    n = len(me.vertices)
    if n:
        co = np.empty(n * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        d = np.linalg.norm(co - np.array(local), axis=1)
        k = int(np.argmin(d))
        size = part_size or float(np.linalg.norm(co.max(axis=0) - co.min(axis=0)))
        if d[k] <= min(5 * MM, 0.03 * size):
            return Vector(co[k].tolist())
    return local


def set_zero_point(scene, ob, world: Vector) -> None:
    c = settings(scene)
    c["_busy"] = True
    if ob is not c.workpiece:
        c.workpiece = ob
        c.workpiece_uid = ob.get(build.PROP_UID, "")
    c.zero_point = snap_point(ob, world)
    c.zero_mode = "POINT"
    c.zero_shift = (0.0, 0.0, 0.0)
    del c["_busy"]
    setup_changed(scene)


def set_home_here(scene, here: bool = True) -> None:
    c = settings(scene)
    s = scene.fresing
    if here:
        vals = []
        for name in axis_joint_names(c):
            j = s.joints.get(name)
            vals.append(joints.get_value(j) if j is not None else 0.0)
        c.home = vals
        c.home_set = True
    else:
        c.home = (0.0, 0.0, 0.0)
        c.home_set = False
    setup_changed(scene)


# ---------------------------------------------------------------------------
# the work zero marker
# ---------------------------------------------------------------------------

def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _place(ob, parent, world: Matrix) -> None:
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = (parent.matrix_world.inverted() @ world) if parent is not None else world


def zero_marker(scene, mach: Machine | None = None):
    """Make or move the work zero's arrows (a child of the workpiece). None when not set up."""
    c = settings(scene)
    try:
        mach = mach or Machine(scene)
    except SetupError:
        mach = None
    ob = c.zero_empty
    if mach is None:
        if ob is not None:
            ob.hide_viewport = True
        return None
    if ob is None or ob.name not in bpy.data.objects:
        ob = bpy.data.objects.new(ZERO_NAME, None)
        ob.empty_display_type = "ARROWS"
        ob[TAG] = "zero"
        ob[build.PROP_KIND] = "cnc"
        c.zero_empty = ob
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    ob.empty_display_size = max(10 * MM, min(60 * MM, _size(mach.workpiece) * 0.25))
    ob.hide_render = True
    ob.hide_viewport = False
    ob.show_name = True
    _place(ob, mach.workpiece, mach.zero_matrix())
    return ob


def _size(ob) -> float:
    try:
        co = _world_points(ob)
        return float(np.linalg.norm(co.max(axis=0) - co.min(axis=0)))
    except Exception:
        return 0.1


def spindle_is_motor(scene) -> bool:
    """A newly picked spindle joint turns without end: tick its 'Motor' (task 0037 problem 4: Build only warned
    afterwards). Once per pick, so 'Motor' can still be switched off by hand. True when it was ticked now."""
    c = settings(scene)
    name = c.spindle_joint
    if c.get("fr_spindle_motor") == name:
        return False
    j = scene.fresing.joints.get(name) if name else None
    if j is None or j.kind != "ROTATE" or j.follows or not joints.is_valid(j):
        return False
    c["fr_spindle_motor"] = name
    if joints.is_motor(j):
        return False
    joints.set_motor(scene, j, True)
    return True


def setup_changed(scene) -> None:
    """Something in the set-up changed: move the zero marker, and the steps' lengths follow (rapid speeds)."""
    try:
        zero_marker(scene)
    except Exception:
        pass
    try:
        spindle_is_motor(scene)
    except Exception as exc:
        print("Fresing Render: spindle not made a motor:", exc)
    for a in scene.fresing.animations:
        for b in a.blocks:
            if b.kind == "GCODE" and b.gcode_file:
                try:
                    step_changed(scene, b, path=False)
                except Exception:
                    pass
    _redraw()


def _redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in getattr(wm, "windows", []) or []:
        for area in win.screen.areas:
            area.tag_redraw()


# ---------------------------------------------------------------------------
# programs
# ---------------------------------------------------------------------------

def _text_copy(path: str):
    for t in bpy.data.texts:
        if t.get("fr_gcode_path") == path:
            return t
    return None


PROGRAM_ABS = "fr_gcode_abs"          # on a step: the program's absolute path when it was picked (task 0051)
TABLE_ABS = "fr_tool_table_abs"       # on the CNC settings: the same for the tool table


def file_path(path_prop: str, remembered: str = "") -> str:
    """The absolute path of a file setting. '//…' is next to the project; when no file is there (the render queue
    renders a copy of the project saved in another folder) the absolute path remembered when it was picked."""
    path = bpy.path.abspath(path_prop) if path_prop else ""
    if path and remembered and not os.path.isfile(path) and os.path.isfile(remembered):
        return remembered
    return path


def keep_path(owner, prop: str, memo: str) -> None:
    """A file setting changed: remember its absolute path, and store a file next to the saved project (or in a
    folder below it) as '//…', so the project and its files can move to another PC together (0037 problem 6)."""
    val = getattr(owner, prop)
    if not val:
        if memo in owner:
            del owner[memo]
        return
    absolute = os.path.normpath(bpy.path.abspath(val))
    owner[memo] = absolute
    if not bpy.data.filepath or val.startswith("//"):
        return
    try:
        rel = os.path.relpath(absolute, os.path.dirname(bpy.path.abspath(bpy.data.filepath)))
    except ValueError:                                   # another drive (Windows)
        return
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        return
    owner["_busy"] = True
    try:
        setattr(owner, prop, "//" + rel.replace(os.sep, "/"))
    finally:
        del owner["_busy"]


def program_text(path_prop: str, remembered: str = "") -> tuple[str, str]:
    """(text, note) of a program: the file, or the copy kept in the project when the file is gone.
    Keeps the copy up to date. Raises FileNotFoundError when neither is there."""
    path = file_path(path_prop, remembered)
    key = os.path.normcase(os.path.abspath(path)) if path else ""
    copy = _text_copy(path_prop) or (_text_copy(key) if key else None)
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        if copy is None or copy.get("fr_gcode_sig") != _sig(text):
            try:
                if copy is None:
                    copy = bpy.data.texts.new(TEXT_PREFIX + os.path.basename(path))
                    copy["fr_gcode_path"] = path_prop
                    copy[TAG] = "program"
                copy.from_string(text)
                copy["fr_gcode_sig"] = _sig(text)
            except Exception:                    # (inside a draw: ID data cannot be written; fine)
                pass
        return text, ""
    if copy is not None:
        return copy.as_string(), f"The file is not there ({path or path_prop}): using the copy saved in the project"
    raise FileNotFoundError(path or path_prop)


def _sig(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8", "replace"), digest_size=12).hexdigest()


def tool_table(scene) -> dict:
    c = settings(scene)
    if not c.tool_table:
        return {}
    path = file_path(c.tool_table, c.get(TABLE_ABS, ""))
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return core.read_tool_table(fh.read())
    except OSError:
        return {}


def read_program(scene, b, mach: Machine | None = None, start=None):
    """(Program, note) for a step; cached. ``mach``: the set-up (else neutral offsets, for the length only)."""
    text, note = program_text(b.gcode_file, b.get(PROGRAM_ABS, ""))
    path = file_path(b.gcode_file, b.get(PROGRAM_ABS, ""))
    g54 = mach.g54 if mach is not None else (0.0, 0.0, 0.0)
    rapid = mach.rapid if mach is not None else tuple(getattr(settings(scene), f"rapid_{a}") for a in "xyz")
    tt = tool_table(scene)
    key = ("prog", _sig(text), tuple(round(x, 6) for x in g54), tuple(rapid),
           tuple(round(x, 6) for x in start) if start is not None else None,
           tuple(sorted((n, t.diameter, t.length) for n, t in tt.items())), os.path.dirname(path))
    prog = _CACHE.get(key)
    if prog is None:
        prog = core.read(text, g54=g54, rapid=rapid, home=(0.0, 0.0, 0.0), tools=tt, base_dir=os.path.dirname(path),
                         start=start)
        if len(_CACHE) > 24:
            _CACHE.clear()
        _CACHE[key] = prog
    return prog, note


def atc_animation(scene, anim, b):
    """The tool changer's animation of a step, or (None, warning)."""
    if not b.gcode_atc:
        return None, ""
    a = scene.fresing.animations.get(b.gcode_atc)
    if a is None:
        return None, f"tool-changer animation '{b.gcode_atc}' not found"
    if anim is not None and a.name == anim.name:
        return None, "the tool-changer animation cannot be the animation itself"
    return a, ""


def _atc_length(a) -> float:
    from . import animation
    ends = [animation.block_end(x) for x in a.blocks if x.enabled and x.kind != "GCODE"]
    return max(ends) if ends else 0.0


def timing(scene, anim, b, mach: Machine | None = None) -> core.Timing:
    """How the step plays: speed, lines, and its tool changes (task 0041: manual or ATC, see toolchange.py)."""
    from . import toolchange
    ch = toolchange.changer(scene, anim, b, mach)
    return core.Timing(speed=b.gcode_speed, factor=b.gcode_factor, fit_seconds=b.gcode_fit,
                       rapid_factor=b.gcode_rapid, tool_change=ch.pause, swap=ch.pause / 2, line_from=b.gcode_from,
                       line_to=b.gcode_to, clean=float(b.gcode_clean_time) if b.gcode_clean else 0.0,
                       clean_sweep=settings(scene).air_source == "SPINDLE", changer=ch)


def _anim_of(scene, b):
    for a in scene.fresing.animations:
        for x in a.blocks:
            if x == b:
                return a
    return None


def step_changed(scene, b, path: bool = True) -> None:
    """A G-code step's settings changed: its duration follows from the program (and the summary)."""
    if not b.gcode_file:
        return
    anim = _anim_of(scene, b)
    try:
        mach = Machine(scene)
    except SetupError:
        mach = None
    try:
        prog, note = read_program(scene, b, mach, start=start_point(mach))
    except FileNotFoundError as exc:
        _INFO[info_key(b)] = {"error": f"File not found: {exc}"}
        return
    sch = core.Schedule(prog, timing(scene, anim, b))
    b["_busy"] = True
    try:
        if abs(b.duration - sch.duration) > 1e-6:
            b.duration = max(0.0, sch.duration)
    finally:
        del b["_busy"]
    _INFO[info_key(b)] = summary(prog, sch, note, scene, b)
    if path and b.gcode_path and mach is not None:
        try:
            show_path(scene, anim)
        except Exception:
            pass


def summary(prog, sch, note: str = "", scene=None, b=None) -> dict:
    moves = [m for m in prog.moves if m.moving]
    probs = prog.problems
    air_text = cool_text = ""
    if scene is not None:                              # the air codes are shown (task 0039): not a problem
        from . import air
        c = settings(scene)
        mine = {f"M{c.air_on_code}", f"M{c.air_off_code}"}
        from . import coolant
        if coolant.is_on(scene):
            mine |= coolant.codes(scene)
        probs = [p for p in probs if p.code not in mine]
        air_text = air.describe(scene, sch)
        if b is not None:
            try:
                cool_text = coolant.describe(scene, sch, b)
            except Exception:
                cool_text = ""
    from . import toolchange
    try:
        tc_notes = toolchange.notes(scene, sch) if scene is not None else []
    except Exception:
        tc_notes = []
    return {"lines": prog.lines, "moves": len(moves), "machine_s": prog.duration, "video_s": sch.duration,
            "air": air_text, "coolant": cool_text, "tool_changes": tc_notes,
            "tools": prog.tool_numbers(), "problems": [p.describe() for p in probs], "notes": list(prog.notes),
            "note": note, "name": prog.name, "changes": len([c for c in sch.changes if c.length > 0]),
            "ended": prog.ended,
            "tool_info": {n: t.describe() for n, t in prog.tools.items()},
            "missing": _missing(scene, prog)}


def _missing(scene, prog) -> list:
    if scene is None:
        return []
    from . import tools
    try:
        return tools.missing(scene, prog)
    except Exception:
        return []


def info_key(b) -> tuple:
    """What a step's summary depends on: its program (the file's size and time, or the copy kept in the project)
    and every setting of the step. Not the step's memory address: after a step was removed or moved another step
    sat there and showed this one's lines (bug hunt 0045 row 16, task 0051)."""
    path = file_path(b.gcode_file, b.get(PROGRAM_ABS, "")) if b.gcode_file else ""
    try:
        st = os.stat(path)
        prog = (path, st.st_size, st.st_mtime_ns)
    except OSError:
        copy = _text_copy(b.gcode_file)
        prog = (path, copy.get("fr_gcode_sig", "") if copy is not None else "")
    vals = []
    for p in b.bl_rna.properties:
        if p.identifier.startswith("gcode_"):
            v = getattr(b, p.identifier)
            vals.append(tuple(v) if hasattr(v, "__len__") and not isinstance(v, str) else v)
    return prog + tuple(vals)


def forget() -> None:
    """Drop every cached summary (a project was opened)."""
    _INFO.clear()


def info(scene, b) -> dict:
    """The summary of a step's program for the panel (worked out when missing)."""
    key = info_key(b)
    hit = _INFO.get(key)
    if hit is None and b.gcode_file:
        try:
            prog, note = read_program(scene, b, None)
            hit = summary(prog, core.Schedule(prog, timing(scene, _anim_of(scene, b), b)), note, scene, b)
        except FileNotFoundError as exc:
            hit = {"error": f"File not found: {exc}"}
        except Exception as exc:                           # never break the panel
            hit = {"error": str(exc)}
        if len(_INFO) > 64:                                # settings typed one after the other: keep it small
            _INFO.clear()
        _INFO[key] = hit
    return hit or {}


def fmt_time(sec: float) -> str:
    sec = max(0.0, sec)
    if sec < 60:
        return f"{sec:.1f} s"
    m, s_ = divmod(int(round(sec)), 60)
    if m < 60:
        return f"{m} min {s_:02d} s"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


# ---------------------------------------------------------------------------
# tools in the spindle
# ---------------------------------------------------------------------------

def tool_entry(scene, number: int):
    return next((t for t in settings(scene).tools if t.number == number), None)


def tool_spec(scene, prog, n: int):
    """The sizes of tool ``n``: its tool list row, else the program's tool comment or the tool table, else a Ø6 mm
    flat end mill (task 0040)."""
    from ..core import tools as tcore
    from . import tools
    entry = tool_entry(scene, n)
    if entry is not None:
        return tools.spec_of(entry)
    info = prog.tools.get(n) if prog is not None else None
    if info is not None and info.diameter:
        return tcore.from_info(info)
    spec = tcore.default("FLAT", n)
    spec.diameter, spec.flute_length, spec.stick_out = 6 * MM, 0.0, 0.0
    return tcore.resolved(spec)


def first_tool(sch) -> int:
    """The tool in the spindle when the step starts (0: the part in the spindle as it is)."""
    if sch.first_tool:
        return sch.first_tool
    return 0


def length_offsets(scene, mach: Machine, numbers, first: int) -> dict:
    """{T: metres the spindle moves up for that tool}: the difference of its length from the tip to the gauge line
    to the reference tool's (the row of the part in the spindle, else the first tool of the step), like G43. Only
    tools with a row. The length is the row's gauge length, else stick-out + holder length (task 0049): tools in
    different holders get the right difference; tools that all share one holder the same as before."""
    from . import tools
    c = settings(scene)
    if not c.tool_lengths:
        return {}
    ref_row = next((t for t in c.tools if t.obj is not None and t.obj is mach.tool), None)
    if ref_row is None and first:
        ref_row = tool_entry(scene, first)
    if ref_row is None:
        return {}
    ref = tools.core.gauge_length(tools.spec_of(ref_row))
    out = {}
    for n in numbers:
        row = tool_entry(scene, n)
        if row is not None and row.obj is not mach.tool:
            out[n] = tools.core.gauge_length(tools.spec_of(row)) - ref
    return out


def _remove_tool_copies(scene=None) -> None:
    obs = [o for o in bpy.data.objects if o.get(TAG) == "tool"]
    meshes = {o.data for o in obs if o.data is not None and o.data.get(TAG) == "tool"}
    for o in obs:
        bpy.data.objects.remove(o)
    for me in meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)


def tool_objects(scene, mach: Machine, prog, numbers, offsets: dict | None = None) -> tuple[dict, dict, list]:
    """For every T number: (the object that shows it in the spindle, the part that leaves the carousel or
    None). Copies are made as needed: a part of the model, the row's STEP model, or a tool drawn from its sizes
    (task 0040); a longer tool reaches further below the spindle (``offsets``). Each copy carries its sizes
    (``fr_spec``) and its tip and axis in its own space (``fr_tip``, ``fr_axis``) so milling cuts with it.
    Returns ({n: show}, {n: carousel part}, warnings)."""
    from . import tools
    spindle = mach.tool
    world = spindle.matrix_world @ tool_frame(spindle)          # where every tool's tip goes, Z into the spindle
    parent = spindle.parent
    offsets = offsets or {}
    show, away, warnings = {}, {}, []
    col = _collection(scene)
    tool_mat, holder_mat = tools.tool_materials(scene, spindle)
    for n in numbers:
        entry = tool_entry(scene, n)
        part = entry.obj if entry is not None else None
        if part is spindle:
            show[n] = spindle
            continue
        spec = tool_spec(scene, prog, n)
        shift = Matrix.Translation((0.0, 0.0, -offsets.get(n, 0.0)))
        frame = None
        if part is not None:
            try:
                frame = tool_frame(part)
            except RuntimeError:
                warnings.append(f"T{n}: the part '{label(part)}' has no shape to read; it is drawn from its sizes")
                part = None
        if part is not None:
            ob = bpy.data.objects.new(f"FR tool T{n}", part.data)
            for i, slot in enumerate(part.material_slots):
                if slot.link == "OBJECT" and i < len(ob.material_slots):
                    ob.material_slots[i].link = "OBJECT"
                    ob.material_slots[i].material = slot.material
            away[n] = part
        elif entry is not None and entry.step_mesh is not None:
            me = entry.step_mesh
            if not me.materials:
                me.materials.append(tool_mat)
            ob = bpy.data.objects.new(f"FR tool T{n}", me)
            axis = Vector(entry.axis)
            axis = axis.normalized() if axis.length > 1e-9 else Vector((0, 0, 1))
            frame = Matrix.Translation(Vector(entry.tip)) @ axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
        else:
            me = tools.drawn_mesh(spec, f"FR tool T{n}")
            me.materials.append(tool_mat)
            me.materials.append(holder_mat)
            ob = bpy.data.objects.new(f"FR tool T{n}", me)
            if entry is None and not (prog.tools.get(n) and prog.tools[n].diameter):
                warnings.append(f"T{n}: no sizes known (no tool comment, tool table or tool list row): shown "
                                "as a Ø6 mm flat end mill")
        want = world @ shift @ (frame.inverted() if frame is not None else Matrix.Identity(4))
        tip = frame.translation if frame is not None else Vector((0, 0, 0))
        ax = (frame.to_3x3() @ Vector((0, 0, 1))) if frame is not None else Vector((0, 0, 1))
        ob[TAG] = "tool"
        ob["fr_cnc_t"] = n
        ob["fr_spec"] = tools.spec_json(spec)
        ob["fr_tip"] = list(tip)
        ob["fr_axis"] = list(ax.normalized())
        ob[build.PROP_KIND] = "cnc"
        col.objects.link(ob)
        _place(ob, parent, want)
        ob.hide_viewport = True
        ob.hide_render = True
        ob.hide_select = True
        show[n] = ob
    return show, away, warnings


def copies(scene=None) -> dict:
    """{T: copy object} of the tool copies a build made."""
    return {int(o["fr_cnc_t"]): o for o in bpy.data.objects if o.get(TAG) == "tool" and "fr_cnc_t" in o}


def schedule(scene) -> list:
    """[(frame, T)] from the build: from that frame on, tool T is in the spindle (0: the part in the spindle)."""
    c = settings(scene)
    if "fr_tools" not in c:
        return []
    a = list(c["fr_tools"])
    return [(float(a[k]), int(a[k + 1])) for k in range(0, len(a) - 1, 2)]


def corner_times(samples, angle: float = 2.0) -> list:
    """Times of the keys where the path turns by more than ``angle`` degrees (a move's end meeting the next move at
    an angle): milling reads the tool there too, so the cut goes into the corner (task 0049)."""
    out = []
    lim = math.cos(math.radians(angle))
    for (_ta, a), (t, b), (_tc, c) in zip(samples, samples[1:], samples[2:]):
        u = Vector(b) - Vector(a)
        v = Vector(c) - Vector(b)
        if u.length < 1e-6 or v.length < 1e-6:
            continue
        if u.normalized().dot(v.normalized()) < lim:
            out.append(t)
    return out


def corners(scene) -> list:
    """Frames (fractional) of the program's corners from the last build (task 0049)."""
    c = settings(scene)
    return [float(x) for x in c["fr_corners"]] if "fr_corners" in c else []


def _record_corners(scene, frames) -> None:
    from .idprops import store_array
    c = settings(scene)
    old = list(c["fr_corners"]) if "fr_corners" in c else []
    store_array(c, "fr_corners", old + [float(f) for f in frames])


def _record_schedule(scene, rows) -> None:
    from .idprops import store_array
    c = settings(scene)
    old = list(c["fr_tools"]) if "fr_tools" in c else []
    for f, n in rows:
        old += [float(f), float(n)]
    store_array(c, "fr_tools", old)


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

class Shifted:
    """A step of the tool changer's animation, played at a tool change: the same step, from ``offset`` s on, the part
    of the changer's animation from ``s0`` s played ``scale`` times as long (task 0041: split at the swap, "Changer
    speed", "Fit into")."""

    def __init__(self, b, offset: float, s0: float = 0.0, scale: float = 1.0):
        self._b = b
        self._offset = offset
        self._s0 = s0
        self._scale = scale

    def __getattr__(self, name):
        return getattr(self._b, name)

    @property
    def start(self):
        return self._offset + (self._b.start - self._s0) * self._scale

    @property
    def duration(self):
        return self._b.duration * self._scale

    @property
    def enabled(self):
        return True

    @property
    def atc_step(self):
        return True


def prepare(scene, anim, warnings: list) -> list:
    """Before a bake: every G-code step's length from its program; returns the tool changer's steps to add
    (shifted to each tool change)."""
    extra = []
    from . import air
    air.prepare(scene)                                     # air frames: written again by the steps (task 0039)
    from . import coolant
    coolant.prepare(scene)                                 # coolant frames: written again by the steps (task 0042)
    c = settings(scene)
    for k in ("fr_tools", "fr_corners"):                   # which tool is in the spindle, the program's corners:
        if k in c:                                         # written by the steps
            del c[k]
    try:
        mach = Machine(scene)
    except SetupError:
        mach = None
    for b in anim.blocks:
        if not b.enabled or b.kind != "GCODE":
            continue
        if not b.gcode_file:
            continue
        try:
            prog, _note = read_program(scene, b, mach, start=start_point(mach))
        except FileNotFoundError:
            continue
        sch = core.Schedule(prog, timing(scene, anim, b, mach))
        b["_busy"] = True
        b.duration = sch.duration
        del b["_busy"]
        if c.changer != "ATC":
            continue
        a, w = atc_animation(scene, anim, b)
        if w:
            warnings.append(f"'{_label(b)}': {w}")
        if a is None or not sch.changes:
            continue
        from . import toolchange
        axes = set(axis_joint_names(c))
        car = toolchange.carousel(scene)
        turned = car.name if car is not None and c.pockets else ""
        blocks = []
        for x in a.blocks:
            if not x.enabled or x.kind == "GCODE":
                continue
            if x.kind in ("JOINT", "MOTOR") and x.joint in axes:
                warnings.append(f"'{_label(b)}': the tool-changer animation '{a.name}' moves '{x.joint}', an axis "
                                "of the program: left out (move the head with the program, e.g. G53 G0 Z0 before M6)")
                continue
            if x.kind in ("JOINT", "MOTOR") and turned and x.joint == turned:
                warnings.append(f"'{_label(b)}': the tool-changer animation '{a.name}' turns the carousel "
                                f"'{x.joint}': left out (the app turns it to the right pocket)")
                continue
            blocks.append(x)
        for ch in sch.changes:
            parts = ch.seq_parts()
            for k, (t, s0, s1, scale) in enumerate(parts):
                last = k == len(parts) - 1
                for x in blocks:
                    if s0 - 1e-9 <= x.start and (x.start < s1 - 1e-9 or last):
                        extra.append(Shifted(x, b.start + t, s0, scale))
    return extra


def _label(b) -> str:
    from . import animation
    return animation.block_label(b)


def bake_step(scene, anim, b, f0: int, jstate: dict, jkeys: dict, vkeys: dict, busy_until: dict,
              warnings: list, merge) -> float:
    """Keys for a Run G-code program step (called by animation.bake). Returns the frame its last key is on."""
    from . import animation
    name = _label(b)
    if not b.gcode_file:
        warnings.append(f"'{name}': pick a program file")
        return f0
    try:
        mach = Machine(scene)
    except SetupError as exc:
        warnings.append(f"'{name}': {exc}")
        return f0
    start = mach.machine_of([jstate[j.name] for j in mach.joints])
    if all(abs(a - b_) < 1e-6 for a, b_ in zip(start, start_point(mach))):
        start = start_point(mach)                      # the same numbers as for the step's length: one read
    try:
        prog, note = read_program(scene, b, mach, start=start)
    except FileNotFoundError as exc:
        warnings.append(f"'{name}': file not found ({exc})")
        return f0
    if note:
        warnings.append(f"'{name}': {note}")
    c = settings(scene)
    from . import coolant
    quiet = {f"M{c.air_on_code}", f"M{c.air_off_code}"} | (coolant.codes(scene) if coolant.is_on(scene) else set())
    probs = [p for p in prog.problems if p.code not in quiet]
    for p in probs[:4]:
        warnings.append(f"'{name}': {p.describe(3)}")
    if len(probs) > 4:
        warnings.append(f"'{name}': {len(probs) - 4} more things the app does not show (see the step)")
    sch = core.Schedule(prog, timing(scene, anim, b, mach))
    if not sch.pieces:
        warnings.append(f"'{name}': the program has no moves on lines {b.gcode_from or 1} … {b.gcode_to or 'end'}")
        return f0
    fps = animation.fps_of(anim)
    span = sch.duration * fps
    for j in mach.joints:
        if busy_until.get(j.name, 0) > f0:
            warnings.append(f"Two steps move '{j.name}' at the same time; the later one takes over")
        busy_until[j.name] = max(busy_until.get(j.name, 0), f0 + int(math.ceil(span)))
    from . import tools
    for n, line in tools.missing(scene, prog):
        warnings.append(f"'{name}': T{n} (line {line}) is not in the tool list: it is drawn from the program's "
                        "sizes – add it in 4 Motion > CNC machine > Tools")
    numbers = sorted({n for _s, n, _t, _d in sch.tool_events if n} | ({sch.first_tool} if sch.first_tool else set()))
    offsets = length_offsets(scene, mach, numbers, first_tool(sch) or (sch.tool_events[0][1] if sch.tool_events
                                                                        else 0))
    lift = _lift(sch, offsets)
    # X, Y, Z: a key at every move's ends and along arcs
    samples = sch.samples(fps, tol=KEY_TOL)
    if offsets:                                     # a key where the spindle's length adjustment starts and ends
        have = {round(t, 9) for t, _p in samples}
        extra_t = {x for c in sch.changes if c.length > 0 for x in (c.swap, c.out_end, c.back_start, c.start,
                                                                     c.start + c.length)}
        samples = sorted(samples + [(t, sch.point_at(t)) for t in sorted(extra_t) if round(t, 9) not in have],
                         key=lambda x: x[0])
    _record_corners(scene, [f0 + t * fps for t in corner_times(samples)])
    rows = [[], [], []]
    for t, pt in samples:
        f = f0 + t * fps
        dz = lift(t)
        vals = mach.values_for((pt[0], pt[1], pt[2] + dz) if dz else pt)
        for i, v in enumerate(vals):
            rows[i].append((f, v))
    for i, j in enumerate(mach.joints):
        keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
        for n, (f, v) in enumerate(rows[i]):
            merge(keys, f, v, "LINEAR" if n < len(rows[i]) - 1 else "CONSTANT")
        jstate[j.name] = rows[i][-1][1]
        if j.use_limits:                         # like the machine's soft limits: say on which line
            for p in sch.pieces:
                m = p.move
                pts = [m.b] + ([m.at(k / 8) for k in range(1, 8)] if m.kind == "ARC" else [])
                if any(joints.outside_limits(j, mach.values_for(pt)[i]) for pt in pts):
                    warnings.append(f"'{name}': '{j.name}' goes beyond its limits (first at line {m.line}); the "
                                    "joint stops there")
                    break
    _spindle_keys(scene, anim, b, sch, f0, jstate, jkeys, busy_until, warnings, merge)
    from . import air
    air.record(scene, sch, b, f0, fps, vkeys, merge)        # when air blows (task 0039)
    if air.problem(scene) and (b.gcode_clean or air.step_spans(scene, sch, b)):
        warnings.append(f"'{name}': air blast: {air.problem(scene)} (4 Motion > CNC machine > Air blast)")
    from . import toolchange
    if sch.tool_events or sch.first_tool:
        toolchange.tool_keys(scene, mach, prog, sch, f0, fps, vkeys, jkeys, jstate, busy_until, warnings, merge,
                             name, offsets)
    if coolant.is_on(scene):                                # coolant frames, after the tool copies (task 0042)
        try:
            coolant.record(scene, sch, b, mach, f0, fps, offsets)
        except Exception as exc:
            warnings.append(f"'{name}': the coolant could not be built ({exc})")
        if coolant.problem(scene):
            warnings.append(f"'{name}': coolant: {coolant.problem(scene)} (4 Motion > CNC machine > Coolant)")
    if b.gcode_path:
        try:
            show_path(scene, anim, mach=mach)
        except Exception as exc:                                     # the motion is what matters
            warnings.append(f"'{name}': the toolpath could not be drawn ({exc})")
    return f0 + span


def _spindle_keys(scene, anim, b, sch, f0, jstate, jkeys, busy_until, warnings, merge) -> None:
    from . import animation
    c = settings(scene)
    if not c.spindle_joint:
        return
    j = scene.fresing.joints.get(c.spindle_joint)
    name = _label(b)
    if j is None or j.kind != "ROTATE" or j.follows or not joints.is_valid(j):
        warnings.append(f"'{name}': the spindle joint '{c.spindle_joint}' is not a rotate joint that moves by "
                        "itself: the spindle does not turn")
        return
    keys_rpm = sch.spindle_keys()
    if all(abs(r) < 1e-9 for _t, r in keys_rpm):
        return
    fps = animation.fps_of(anim)
    cap = SLOW_TURN * fps * 60.0
    keys = jkeys.setdefault(j.name, [(1, jstate[j.name], "CONSTANT", "AUTO")])
    angle = jstate[j.name]
    end = sch.duration
    pts = keys_rpm + [(end, None)]
    # M3 = clockwise seen from above: a negative turn about an axis pointing up
    way = -1.0 if joints.axis_world(j)[1].z >= 0 else 1.0
    rows = [(0.0, angle)]
    for (t0, rpm), (t1, _r) in zip(pts, pts[1:]):
        shown = rpm if b.gcode_spindle == "REAL" else math.copysign(min(abs(rpm), cap), rpm)
        angle += way * shown * joints.TURN / 60.0 * max(0.0, t1 - t0)
        rows.append((t1, angle))
    lo, hi = joints.limits(j)
    if not joints.is_motor(j) and any(not lo <= v <= hi for _t, v in rows):
        warnings.append(f"'{name}': tick 'Motor' on the spindle joint '{j.name}' in 4 Motion so it can turn "
                        "without end")
    for n, (t, v) in enumerate(rows):
        merge(keys, f0 + t * fps, min(max(v, lo), hi), "LINEAR" if n < len(rows) - 1 else "CONSTANT")
    jstate[j.name] = min(max(rows[-1][1], lo), hi)
    busy_until[j.name] = max(busy_until.get(j.name, 0), f0 + int(math.ceil(end * fps)))


def _lift(sch, offsets: dict):
    """Machine Z (mm) added at a moment of the step for the length of the tool in the spindle (like G43). When the head
    stays where it is for a change, it changes from the swap to the end of the change (the new tool is in; the old one
    kept its point). When the head goes to the changer (task 0041) it is 0 there – the spindle's gauge line is where
    the pocket is – and changes on the way out and the way back."""
    first = first_tool(sch) or (sch.timing.changer.start_tool if sch.timing.changer is not None else 0)
    knots = [(0.0, offsets.get(first, 0.0) / MM)]
    cur = knots[0][1]
    for c in sch.changes:
        if c.length <= 0:
            continue
        new = offsets.get(c.tool, 0.0) / MM
        end = c.start + c.length
        if c.moves:
            knots += [(c.start, cur), (c.out_end, 0.0), (c.back_start, 0.0), (end, new)]
        else:
            knots += [(c.swap, cur), (end, new)]
        cur = new
    if all(abs(v) < 1e-9 for _t, v in knots):
        return lambda t: 0.0
    ts = [t for t, _v in knots]

    def lift(t: float) -> float:
        import bisect
        k = bisect.bisect_right(ts, t + 1e-9) - 1
        if k < 0:
            return knots[0][1]
        if k >= len(knots) - 1:
            return knots[-1][1]
        (ta, va), (tb, vb) = knots[k], knots[k + 1]
        if tb - ta <= 1e-12:
            return vb
        return va + (vb - va) * (t - ta) / (tb - ta)
    return lift


def after_clear(scene) -> None:
    """'Clear keys': the tool copies go (they are made again by the next build), and the air with them."""
    _remove_tool_copies(scene)
    c = settings(scene)
    for k in ("fr_tools", "fr_corners"):
        if k in c:
            del c[k]
    from . import air
    air.clear(scene)
    air.remove_cone()
    from . import coolant
    coolant.clear(scene)


# ---------------------------------------------------------------------------
# the toolpath
# ---------------------------------------------------------------------------

def _material(name: str, rgb) -> bpy.types.Material:
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get(TAG) == "path":
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat[TAG] = "path"
    mat.diffuse_color = (*rgb, 1.0)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (*rgb, 1.0)
    em.inputs["Strength"].default_value = 1.5
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def _node_group() -> bpy.types.NodeTree:
    ng = bpy.data.node_groups.get(NODE_GROUP)
    if ng is not None and ng.get(TAG) == "path2":
        return ng
    if ng is not None:
        bpy.data.node_groups.remove(ng)
    ng = bpy.data.node_groups.new(NODE_GROUP, "GeometryNodeTree")
    ng[TAG] = "path2"
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    rad = ng.interface.new_socket("Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    rad.default_value = PATH_RADIUS
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, L = ng.nodes, ng.links
    gin, gout = n.new("NodeGroupInput"), n.new("NodeGroupOutput")
    to_curve = n.new("GeometryNodeMeshToCurve")
    circle = n.new("GeometryNodeCurvePrimitiveCircle")
    circle.inputs["Resolution"].default_value = 6
    to_mesh = n.new("GeometryNodeCurveToMesh")
    frame_attr = n.new("GeometryNodeInputNamedAttribute")
    frame_attr.data_type = "FLOAT"
    frame_attr.inputs["Name"].default_value = "fr_frame"
    rapid_attr = n.new("GeometryNodeInputNamedAttribute")
    rapid_attr.data_type = "FLOAT"
    rapid_attr.inputs["Name"].default_value = "fr_rapid"
    now = n.new("GeometryNodeInputSceneTime")
    cmp = n.new("FunctionNodeCompare")
    cmp.data_type = "FLOAT"
    cmp.operation = "LESS_EQUAL"
    is_rapid = n.new("FunctionNodeCompare")
    is_rapid.data_type = "FLOAT"
    is_rapid.operation = "GREATER_THAN"
    is_rapid.inputs[1].default_value = 0.5
    m_cut = n.new("GeometryNodeSetMaterial")
    m_done = n.new("GeometryNodeSetMaterial")
    m_rapid = n.new("GeometryNodeSetMaterial")
    m_cut.inputs["Material"].default_value = _material("FR toolpath to cut", (1.0, 0.42, 0.04))
    m_done.inputs["Material"].default_value = _material("FR toolpath cut", (0.08, 0.75, 0.2))
    m_rapid.inputs["Material"].default_value = _material("FR toolpath rapid", (0.25, 0.5, 1.0))
    L.new(gin.outputs["Geometry"], to_curve.inputs["Mesh"])
    L.new(gin.outputs["Radius"], circle.inputs["Radius"])
    L.new(to_curve.outputs["Curve"], to_mesh.inputs["Curve"])
    L.new(circle.outputs["Curve"], to_mesh.inputs["Profile Curve"])
    L.new(to_mesh.outputs["Mesh"], m_cut.inputs["Geometry"])
    L.new(frame_attr.outputs["Attribute"], cmp.inputs[0])
    L.new(now.outputs["Frame"], cmp.inputs[1])
    L.new(m_cut.outputs["Geometry"], m_done.inputs["Geometry"])
    L.new(cmp.outputs["Result"], m_done.inputs["Selection"])
    L.new(rapid_attr.outputs["Attribute"], is_rapid.inputs[0])
    L.new(m_done.outputs["Geometry"], m_rapid.inputs["Geometry"])
    L.new(is_rapid.outputs["Result"], m_rapid.inputs["Selection"])
    L.new(m_rapid.outputs["Geometry"], gout.inputs["Geometry"])
    for k, node in enumerate((gin, to_curve, to_mesh, m_cut, m_done, m_rapid, gout)):
        node.location = (k * 220, 0)
    for k, node in enumerate((circle, frame_attr, now, cmp, rapid_attr, is_rapid)):
        node.location = (200 + k * 200, -300)
    return ng


def _dashes(pts: list) -> list:
    """A rapid's polyline cut into dashes: [[(x, y, z, frame) ...] ...]."""
    out = []
    cur = [pts[0]]
    on, left = True, DASH
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a[:3], b[:3])
        pos = 0.0
        while seg - pos > left:
            pos += left
            u = pos / seg
            p = tuple(a[k] + (b[k] - a[k]) * u for k in range(4))
            if on:
                cur.append(p)
                out.append(cur)
                cur = []
            else:
                cur = [p]
            on = not on
            left = DASH if on else GAP
        left -= seg - pos
        if on:
            cur.append(b)
    if on and len(cur) > 1:
        out.append(cur)
    return out


def path_geometry(scene, anim, mach: Machine) -> tuple:
    """(points (n x 3, m, in the work zero's frame), edges (k x 2), frame per point, rapid per point) of
    every G-code step of ``anim`` with Show toolpath on."""
    from . import animation
    fps = animation.fps_of(anim)
    pts, edges, frames, rapid = [], [], [], []
    g54 = np.array(mach.g54)
    for b in anim.blocks:
        if not (b.enabled and b.kind == "GCODE" and b.gcode_file and b.gcode_path):
            continue
        try:
            prog, _n = read_program(scene, b, mach, start=start_point(mach))
        except FileNotFoundError:
            continue
        sch = core.Schedule(prog, timing(scene, anim, b))
        f0 = animation.frame_of(anim, b.start)
        for is_rapid, line in sch.path(tol=0.01, max_step=1.0 / fps):
            pieces = _dashes(line) if is_rapid else [line]
            for piece in pieces:
                if len(piece) < 2:
                    continue
                base = len(pts)
                for x, y, z, t in piece:
                    pts.append(((x - g54[0]) * MM, (y - g54[1]) * MM, (z - g54[2]) * MM))
                    frames.append(f0 + t * fps)
                    rapid.append(1.0 if is_rapid else 0.0)
                edges += [(base + k, base + k + 1) for k in range(len(piece) - 1)]
    return (np.array(pts, dtype=np.float32).reshape(-1, 3), np.array(edges, dtype=np.int32).reshape(-1, 2),
            np.array(frames, dtype=np.float32), np.array(rapid, dtype=np.float32))


def show_path(scene, anim=None, mach: Machine | None = None):
    """Make (or update) the toolpath object for the animation's G-code steps. Returns it, or None."""
    from . import animation
    anim = anim or animation.active(scene)
    if anim is None:
        return None
    mach = mach or Machine(scene)
    zero = zero_marker(scene, mach)
    co, ed, fr, rp = path_geometry(scene, anim, mach)
    ob = next((o for o in bpy.data.objects if o.get(TAG) == "path"), None)
    if not len(ed):
        if ob is not None:
            remove_path()
        return None
    me = bpy.data.meshes.new(PATH_NAME)
    me[TAG] = "path"
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.reshape(-1))
    me.edges.add(len(ed))
    me.edges.foreach_set("vertices", ed.reshape(-1))
    me.update()
    a = me.attributes.new("fr_frame", "FLOAT", "POINT")
    a.data.foreach_set("value", fr)
    a = me.attributes.new("fr_rapid", "FLOAT", "POINT")
    a.data.foreach_set("value", rp)
    if ob is None:
        ob = bpy.data.objects.new(PATH_NAME, me)
        ob[TAG] = "path"
        ob[build.PROP_KIND] = "cnc"
        ob.hide_select = True
    else:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    mod = ob.modifiers.get("Toolpath")
    if mod is None:
        mod = ob.modifiers.new("Toolpath", "NODES")
    ng = _node_group()
    if mod.node_group is not ng:
        mod.node_group = ng
    ob.parent = zero
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    in_render = any(b.enabled and b.kind == "GCODE" and b.gcode_path and b.gcode_path_render for b in anim.blocks)
    ob.hide_render = not in_render
    ob.hide_viewport = False
    return ob


def remove_path() -> None:
    for ob in [o for o in bpy.data.objects if o.get(TAG) == "path"]:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def path_object():
    return next((o for o in bpy.data.objects if o.get(TAG) == "path"), None)


# ---------------------------------------------------------------------------
# tools from the program, model updates, renames
# ---------------------------------------------------------------------------

def tools_from_program(scene, b) -> int:
    """Add a tool list row for every T number of the step's program that has none (sizes from the program's tool
    comments or the tool table). Returns how many."""
    from . import tools
    prog, _n = read_program(scene, b, None)
    return tools.from_program(scene, prog)


def renamed_joint(scene, old: str, new: str) -> None:
    c = settings(scene)
    for attr in ("x_joint", "y_joint", "z_joint", "spindle_joint", "carousel_joint"):
        if getattr(c, attr) == old:
            c["_busy"] = True
            setattr(c, attr, new)
            del c["_busy"]


def before_model_update(scene) -> None:
    """The model is made again: the marker and the toolpath hang on the workpiece; they are made again after."""
    _remove_tool_copies(scene)
    remove_path()
    from . import toolchange
    toolchange.before_model_update(scene)
    from . import air, coolant
    air.before_model_update(scene)
    coolant.before_model_update(scene)
    c = settings(scene)
    ob = c.zero_empty
    if ob is not None:
        c.zero_empty = None
        bpy.data.objects.remove(ob)


def after_model_update(scene, mapping: dict, by_uid_new: dict) -> list[str]:
    c = settings(scene)
    notes = []

    def new(uid):
        if not uid:
            return None
        nu = mapping.get(uid, uid)
        return by_uid_new.get(uid) or next((o for o in scene.objects if o.get(build.PROP_UID) == nu), None)

    c["_busy"] = True
    try:
        for attr, uid_attr, what in (("tool", "tool_uid", "the tool in the spindle"),
                                     ("workpiece", "workpiece_uid", "the workpiece")):
            uid = getattr(c, uid_attr)
            if not uid:
                continue
            ob = new(uid)
            setattr(c, attr, ob)
            if ob is None:
                notes.append(f"CNC machine: {what} is gone in the new revision (pick it again in 4 Motion > "
                             "CNC machine)")
                setattr(c, uid_attr, "")
            else:
                setattr(c, uid_attr, ob.get(build.PROP_UID, ""))
        for t in c.tools:
            if t.uid:
                ob = new(t.uid)
                t.obj = ob
                if ob is None:
                    notes.append(f"CNC machine: the part of tool T{t.number} is gone in the new revision")
                    t.uid = ""
                else:
                    t.uid = ob.get(build.PROP_UID, "")
    finally:
        del c["_busy"]
    from . import air, toolchange
    notes += air.after_model_update(scene, new)
    from . import coolant
    notes += coolant.after_model_update(scene, new)
    notes += toolchange.after_model_update(scene, new)
    _CACHE.clear()
    setup_changed(scene)
    return notes


def frame_of_line(scene, anim, b, line: int):
    """The frame at which the step's program starts the first move on ``line`` (or the next line with one)."""
    from . import animation
    try:
        mach = Machine(scene)
    except SetupError:
        mach = None
    prog, _n = read_program(scene, b, mach, start=start_point(mach))
    sch = core.Schedule(prog, timing(scene, anim, b))
    p = next((p for p in sch.pieces if p.move.line >= line), None)
    if p is None:
        return None
    return animation.frame_of(anim, b.start) + p.v0 * animation.fps_of(anim)
