"""4 Motion > Milling > Make a toolpath (task 0029): the app writes the program that cuts the block into the part.

What it uses: the milling set-up's workpiece (the stock) and finished part (0027), the CNC machine's set-up for the
program's coordinates (work zero, 0026), two tools of the tool list (0040). ``core/toolpath.py`` makes the paths and
the program text (no Blender). The program is written next to the project (``<project> toolpath.ngc``) and goes in as
a normal "Run G-code program" step, marked as the app's (``STEP_TAG``): making it again replaces that step's program,
and asks first when the file was changed by hand since. Everything else - spindle, tool changes, coolant, air, chips,
the drawn toolpath, the material removal - works as for any program.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile

import bpy
import numpy as np

from ..core import toolpath as core
from . import gcode, machining, tools

MM = 0.001
STEP_TAG = "fr_toolpath"                 # on the step the app made
FILE_SUFFIX = " toolpath.ngc"
_RUN = {}                                # scene name -> {"running", "progress", "text", "cancel"}


class NotReady(RuntimeError):
    pass


def settings(scene):
    return scene.fresing.toolpath


def runtime(scene) -> dict:
    return _RUN.setdefault(scene.name, {})


def _row(scene, value) -> object | None:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return tools.row_of(scene, n) if n > 0 else None


def picked(scene) -> tuple:
    """(roughing row, finishing row) of the tool list, None where none is picked."""
    t = settings(scene)
    return _row(scene, t.rough_tool), _row(scene, t.finish_tool)


def material(scene) -> tuple[str, str]:
    """(ALU / STEEL / POM, how it was found) for the speeds and feeds."""
    t = settings(scene)
    if t.material != "AUTO":
        return t.material, "picked"
    try:
        from . import chips
        fam, why = chips.family(scene)
    except Exception:
        return "ALU", "aluminium (nothing else found)"
    m = {"ALU": "ALU", "PLASTIC": "POM", "WOOD": "POM"}.get(fam, "STEEL")
    return m, why


def problem(scene) -> str:
    """'' when a toolpath can be made, else what to do first."""
    m = machining.settings(scene)
    if not machining.core.available():
        return "The Manifold library did not load: run Install.bat again"
    if m.workpiece is None:
        return "Click the raw block and press 'Use as workpiece' (above)"
    if m.finished is None or m.finished.type != "MESH":
        return "Click the finished part and press 'Use as finished part' (above)"
    p = gcode.problem(scene)
    if p:
        return f"Set up the CNC machine first (4 Motion > CNC machine): {p}"
    c = gcode.settings(scene)
    if c.workpiece is not m.workpiece:
        return "The CNC machine's workpiece is another part than the milling workpiece: press Workpiece in 4 Motion " \
               "> CNC machine with the raw block clicked"
    r, f = picked(scene)
    if r is None and f is None:
        return "Pick a roughing tool, a finishing tool or both (add them in 4 Motion > CNC machine > Tools)"
    for row in (r, f):
        if row is not None and row.kind not in core.KINDS:
            return f"T{row.number} cannot make a toolpath: use {core.KIND_TEXT}"
    return ""


def _tris(me, matrix) -> np.ndarray:
    """A mesh's triangles through ``matrix`` (4x4), in mm."""
    me.calc_loop_triangles()
    n = len(me.loop_triangles)
    v = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", v)
    v = v.reshape(-1, 3)
    t = np.empty(n * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    m = np.asarray(matrix, dtype=np.float64)
    w = v @ m[:3, :3].T + m[:3, 3]
    return w[t.reshape(-1, 3)] / MM


def inputs(scene) -> tuple:
    """(part triangles, stock triangles, roughing spec, finishing spec, core.Settings): program coordinates, mm."""
    why = problem(scene)
    if why:
        raise NotReady(why)
    m = machining.settings(scene)
    mach = gcode.Machine(scene)
    wp, fin = m.workpiece, m.finished
    to_prog = mach.zero_matrix().inverted()
    wp_world = wp.matrix_world
    stock_me = m.stock_mesh or wp.data
    stock = _tris(stock_me, to_prog @ wp_world)
    rel = machining._cad_world(wp).inverted() @ machining._cad_world(fin)        # the part in the block's space
    part = _tris(fin.data, to_prog @ wp_world @ rel)
    t = settings(scene)
    r, f = picked(scene)
    c = gcode.settings(scene)
    mat, _why = material(scene)
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0] if bpy.data.filepath else "Project"
    st = core.Settings(leave=t.leave / MM, step_down=t.step_down / MM, stepover=t.stepover / 100.0,
                       scallop=t.scallop / MM, angle=float(np.degrees(t.angle)), detail=t.detail, material=mat,
                       rough_rpm=t.rough_rpm, rough_feed=t.rough_feed, finish_rpm=t.finish_rpm,
                       finish_feed=t.finish_feed, coolant=t.coolant, air_on=c.air_on_code, air_off=c.air_off_code,
                       name=f"{stem}: toolpath made by Fresing Render")
    return (part, stock, tools.spec_of(r) if r is not None else None,
            tools.spec_of(f) if f is not None else None, st)


# ---------------------------------------------------------------------------
# the program file and its step
# ---------------------------------------------------------------------------

def program_path() -> tuple[str, str]:
    """(absolute path, the path as the step stores it): next to the saved project, else in a temporary folder (the
    project keeps a copy of the program either way)."""
    if bpy.data.filepath:
        d = os.path.dirname(bpy.path.abspath(bpy.data.filepath))
        name = os.path.splitext(os.path.basename(bpy.data.filepath))[0] + FILE_SUFFIX
        return os.path.join(d, name), "//" + name
    d = os.path.join(tempfile.gettempdir(), "Fresing Render")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "Project" + FILE_SUFFIX)
    return p, p


def sig(text: str) -> str:
    return hashlib.blake2b(text.encode("utf-8", "replace"), digest_size=12).hexdigest()


def step(scene):
    """(animation, step) of the step the app made, or (None, None)."""
    for a in scene.fresing.animations:
        for b in a.blocks:
            if b.kind == "GCODE" and b.get(STEP_TAG):
                return a, b
    return None, None


def edited_by_hand(scene) -> str:
    """The program's path when its file was changed since the app wrote it, else ''."""
    _a, b = step(scene)
    t = settings(scene)
    if b is None or not t.program_sig:
        return ""
    path = gcode.file_path(b.gcode_file, b.get(gcode.PROGRAM_ABS, ""))
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return ""
    return path if sig(text) != t.program_sig else ""


def write(scene, res: core.Result, path: str = "") -> tuple:
    """Write the program and put it in its step (a new one in the animation shown in 6 Animation, or the step made
    before). ``path``: where (else next to the project). Returns (animation, step, path)."""
    from . import animation
    path, stored = (path, path) if path else program_path()
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(res.text)
    t = settings(scene)
    t.program_sig = sig(res.text)
    s = scene.fresing
    a, b = step(scene)
    if b is None:
        a = animation.active(scene)
        if a is None:
            a = s.animations.add()
            a.name = "Toolpath"
            s.animations_index = len(s.animations) - 1
        prev_end = max((animation.block_end(x) for x in a.blocks), default=0.0)
        b = a.blocks.add()
        b.kind = "GCODE"
        b.easing = "LINEAR"
        b.start = round(prev_end, 2)
        b.name = "Toolpath"
        b[STEP_TAG] = True
        b["_busy"] = True
        try:
            b.gcode_speed = "FIT"
            b.gcode_fit = 30.0
            b.gcode_rapid = 4.0
        finally:
            del b["_busy"]
    b.gcode_file = stored                       # (always set: the same path again re-reads the new text)
    b[gcode.PROGRAM_ABS] = os.path.normpath(path)
    gcode.forget()
    gcode.step_changed(scene, b)
    if scene.fresing.anim_baked:
        scene.fresing.last_message = "The toolpath changed: press Build animation in 6 Animation"
    return a, b, path


def save_result(scene, res: core.Result, b) -> dict:
    """The result line's numbers, kept with the project."""
    feed = rapid = 0.0
    for p in res.passes:
        f, r = core.path_length(p.moves)
        feed += f
        rapid += r
    info = gcode.info(scene, b) if b is not None else {}
    out = {"moves": res.moves(), "feed_m": feed / 1000.0, "rapid_m": rapid / 1000.0,
           "machine_s": float(info.get("machine_s", 0.0)), "video_s": float(info.get("video_s", 0.0)),
           "seconds": res.seconds, "undercut": res.undercut.get("text", ""),
           "passes": [{"title": p.title, "tool": p.tool.number, "moves": len(p.moves), "rpm": p.cut.rpm,
                       "feed": p.cut.feed} for p in res.passes],
           "levels": int(res.stats.get("rough_levels", 0)), "lines": int(res.stats.get("finish_lines", 0)),
           "stepover": float(res.stats.get("finish_stepover", 0.0)),
           "problems": info.get("problems", [])}
    settings(scene).result = json.dumps(out)
    return out


def result(scene) -> dict:
    try:
        return json.loads(settings(scene).result or "{}")
    except ValueError:
        return {}


def result_lines(scene) -> list:
    """The result in words for the panel."""
    r = result(scene)
    if not r:
        return []
    out = [f"{r['moves']:,} moves, {r['feed_m']:.1f} m cutting + {r['rapid_m']:.1f} m in the air"]
    if r.get("machine_s"):
        out.append(f"On the machine {gcode.fmt_time(r['machine_s'])}; the step plays it in "
                   f"{gcode.fmt_time(r['video_s'])}")
    bits = []
    for p in r.get("passes", []):
        bits.append(f"{p['title']} T{p['tool']}: {p['moves']:,} moves, S{p['rpm']:.0f} F{p['feed']:.0f}")
    out += bits
    if r.get("levels"):
        out.append(f"Roughing in {r['levels']} levels")
    if r.get("lines"):
        out.append(f"Finishing in {r['lines']} lines {r['stepover']:.2f} mm apart")
    out.append(f"Made in {r['seconds']:.1f} s")
    return out


class Job:
    """One making of the toolpath: ``steps()`` yields the progress (0 … 1) and the text; then ``finish()``."""

    def __init__(self, scene, path: str = ""):
        self.scene = scene
        self.path = path
        self.part, self.stock, self.rough, self.finish_spec, self.st = inputs(scene)
        self.res = None
        self.text = "Starting"

    def steps(self):
        g = core.make(self.part, self.stock, self.rough, self.finish_spec, self.st)
        try:
            while True:
                fr, self.text = next(g)
                yield fr
        except StopIteration as stop:
            self.res = stop.value

    def run(self):
        for _p in self.steps():
            pass
        return self.finish()

    def finish(self) -> dict:
        a, b, path = write(self.scene, self.res, self.path)
        out = save_result(self.scene, self.res, b)
        out.update(animation=a.name, path=path)
        return out


def make(scene, path: str = "") -> dict:
    """Make the toolpath to the end (scripts, tests, the PC check, the test tour)."""
    return Job(scene, path).run()


# ---------------------------------------------------------------------------
# the test model (tests, PC check, test tour)
# ---------------------------------------------------------------------------

TEST_MODEL = "test_toolpath.step"        # tools/make_test_toolpath.py
TEST_STOCK = "STOCK 120x80x40"
TEST_PART = "FINISHED PART"
TEST_TOOL = "END MILL D10"


def set_up_test_model(scene, detail: str = "NORMAL") -> None:
    """The test model as the owner would set it up: X/Y/Z joints, the CNC machine (tool in the spindle, the block
    as workpiece, work zero on its top centre), milling (the block, the finished part), T1 flat Ø10 (roughing, in
    the spindle) and T2 ball Ø10 (finishing) in the tool list, both picked here."""
    from mathutils import Vector

    from . import build, joints

    def ob(name):
        return next(o for o in scene.objects if o.get(build.PROP_NAME) == name)

    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(asm)
        joints.create(scene, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    gcode.find_axes(scene)
    tool, stock, fin = ob(TEST_TOOL), ob(TEST_STOCK), ob(TEST_PART)
    gcode.use_tool(scene, tool)
    gcode.use_workpiece(scene, stock)
    machining.add_bit(scene, tool)
    machining.set_workpiece(scene, stock)
    machining.set_finished(scene, fin)
    r1 = tools.add_row(scene, "FLAT", 1)
    r1.diameter, r1.length, r1.flute_length = 0.010, 0.045, 0.030
    r2 = tools.add_row(scene, "BALL", 2)
    r2.diameter, r2.length, r2.flute_length = 0.010, 0.040, 0.025
    tools.use_part(scene, tools.row_of(scene, 1), tool)
    t = settings(scene)
    t.rough_tool, t.finish_tool, t.detail = "1", "2", detail
