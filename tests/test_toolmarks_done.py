"""Task 0061, tool marks on cut faces: the independent tests.

Written from the task's "Done when" list (tasks/0061-tool-marks.md) by an agent that wrote none of the code. Every
test drives the real thing: a model is imported, milled through the app's own operators, and the milled mesh that
Blender shows is read back. Nothing here writes the attributes by hand.

The test mill (tools/make_test_mill.py): the block is 200 x 200 x 40 mm, x/y -100 .. 100, z 30 .. 70 in its own
space; the table carries it along Y, the carriage moves the tool along X, the head along Z. A program's zero is the
middle of the block's top, so program Z-1 is z 69 mm in the block's own space. All places below are in that space,
in mm: the marks are stored in the milled mesh's own space too.

What the mesh must hold (the contract, fresing_render/core/toolmarks.py): four per-face attributes
fr_mk_o / fr_mk_d / fr_mk_a / fr_mk_p = (kind, radius, spacing).
"""

import math
import os
import re
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, gcode, joints, logic, machining, tools  # noqa: E402
from fresing_render.core import toolmarks as TM  # noqa: E402

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "data")
MILL = os.path.join(DATA, "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"
BIT = "END MILL D10"
GROUP = "FR tool marks"                    # the node group's name (the task's Design table)
TAG = "fr_test_done_scene"                 # on the scene: which of this file's set-ups it holds
X, Y, Z = np.eye(3)

_KEPT: dict = {}                           # what a set-up's tests need to know about it (frames, ...)


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


# ---------------------------------------------------------------------------
# setting a scene up, as a user would
# ---------------------------------------------------------------------------

def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) in (name, name + " v"))


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def fresh(folder, model=MILL):
    """An empty Blender with ``model`` imported."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(folder)
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    return sc


def fresh_mill(folder, material="aluminium_machined"):
    """The test mill with its three slide joints; the block made of ``material`` in 3 Looks ("" = as imported)."""
    sc = fresh(folder)
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    if material:
        block_group(sc).material = material
    return sc


def block_group(sc):
    return sc.fresing.groups[ob(sc, STOCK)[build.PROP_GROUP]]


def pick_bit_and_block(sc):
    click(ob(sc, BIT))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}


def joint_animation(sc, moves, seconds=0.4, name="Mill"):
    """moves: (joint, to mm, a name or ""), one after the other at constant speed. Built like 'Build & play'.
    Returns (last frame, {name: the frame just after that move})."""
    a = sc.fresing.animations.add()
    a.name, a.tail = name, 0.0
    t, after = 0.0, {}
    for joint, to, tag in moves:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", joint, t, seconds, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
        t += seconds
        if tag:
            after[tag] = int(round(t * sc.render.fps)) + 2
    return animation.bake(sc, a)["frames"], after


def cnc_machine(sc):
    """The test mill as a CNC machine: axes found, the end mill in the spindle, the block as the workpiece."""
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    click(ob(sc, BIT))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    assert gcode.problem(sc) == "", gcode.problem(sc)
    pick_bit_and_block(sc)


def program_step(sc, folder, text, fit=8.0, name="Program"):
    """A 'Run G-code program' step with ``text``, squeezed into ``fit`` seconds, built. Returns the animation."""
    path = os.path.join(str(folder), name.lower() + ".ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    a = sc.fresing.animations.add()
    a.name, a.tail = name, 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_tc_time = "FIT", fit, 0.5
    b.gcode_file = path
    gcode.step_changed(sc, b)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    machining.sample(sc)                    # (a script reads the bits' path itself after Build)
    return a


def show_end(sc):
    sc.frame_set(sc.frame_end)
    assert machining.refresh(sc, force=True), machining.status(sc)


# ---------------------------------------------------------------------------
# reading the milled mesh back
# ---------------------------------------------------------------------------

class Milled:
    """The workpiece's mesh as Blender has it now. Per face: its corners ``P`` (n, 3, 3), its own normal ``fn``
    (worked out here from the corners), area, whether it has the cut faces' material, the four attributes, and
    the normals Blender shades its three corners with (``cn``)."""

    def __init__(self, sc, wp=None):
        self.ob = wp or machining.workpiece(sc)
        me = self.ob.data
        n = len(me.polygons)
        assert len(me.loops) == 3 * n, "the milled mesh is not all triangles"
        self.n = n
        self.names = [a.name for a in me.attributes]
        self.domains = {a.name: (a.domain, a.data_type) for a in me.attributes}

        def read(get, key, width=3, kind=np.float32):
            a = np.empty(n * width, kind)
            get(key, a)
            return a.reshape(n, width) if width > 1 else a

        v = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", v)
        corners = read(me.loops.foreach_get, "vertex_index", 3, np.int32)
        self.P = v.reshape(-1, 3)[corners].astype(float)
        cross = np.cross(self.P[:, 1] - self.P[:, 0], self.P[:, 2] - self.P[:, 0])
        twice = np.linalg.norm(cross, axis=1)
        self.area = twice / 2
        # a face one could ever see: wider than 2 thousandths of a mm. (The mesh has needles - up to 16 mm long,
        # 0.0002 to 0.0012 mm wide - along the edges of a curved cut; no picture shows them. They are floor
        # faces shaded as the wall next to them.)
        longest = np.linalg.norm(self.P - np.roll(self.P, 1, axis=1), axis=2).max(axis=1)
        self.real = twice > 2e-6 * longest
        self.fn = cross / np.where(twice > 0, twice, 1.0)[:, None]
        self.c = self.P.mean(axis=1)
        slot = me.get(machining.CUT_SLOT)
        self.slot = slot
        mi = read(me.polygons.foreach_get, "material_index", 1, np.int32)
        self.cut = (mi == slot) if slot is not None else np.zeros(n, bool)
        self.has_marks = all(k in me.attributes for k in TM.ATTRS)
        if self.has_marks:
            self.o, self.d, self.a, self.p = (read(me.attributes[k].data.foreach_get, "vector").astype(float)
                                              for k in TM.ATTRS)
            self.kind = np.rint(self.p[:, 0]).astype(int)
            self.radius, self.spacing = self.p[:, 1], self.p[:, 2]
        self.cn = read(me.corner_normals.foreach_get, "vector", 9).reshape(n, 3, 3).astype(float)

    def under(self, x, y, below=False):
        """The face one sees at (x, y) mm looking straight down (``below``: straight up from underneath)."""
        q = np.array([x, y]) * MM
        a, b, c = self.P[:, 0, :2], self.P[:, 1, :2], self.P[:, 2, :2]

        def side(u, w):
            return (w[:, 0] - u[:, 0]) * (q[1] - u[:, 1]) - (w[:, 1] - u[:, 1]) * (q[0] - u[:, 0])

        s1, s2, s3 = side(a, b), side(b, c), side(c, a)
        if below:
            s1, s2, s3 = -s1, -s2, -s3
        idx = np.nonzero((s1 > 0) & (s2 > 0) & (s3 > 0))[0]          # (faces turned towards the viewer)
        assert len(idx), f"no face at ({x}, {y}) mm"
        z = (s2[idx] * self.P[idx, 0, 2] + s3[idx] * self.P[idx, 1, 2] + s1[idx] * self.P[idx, 2, 2]) \
            / (s1[idx] + s2[idx] + s3[idx])
        return int(idx[np.argmin(z) if below else np.argmax(z)])

    def height(self, i):
        return float(self.c[i, 2] / MM)

    def level(self, z=None):
        """Faces lying flat (all three corners at one height, facing straight up or down) that one could see;
        ``z``: at that height (mm)."""
        zs = self.P[:, :, 2]
        sel = self.real & (zs.max(axis=1) - zs.min(axis=1) < 1e-6) & (np.abs(self.fn[:, 2]) > 0.999)
        if z is not None:
            sel &= np.abs(self.c[:, 2] / MM - z) < 0.02
        return sel

    def corner_angle(self, sel, to=None):
        """The biggest angle (degrees) between a corner's shading normal and its face's own normal (or ``to``)."""
        if not sel.any():
            return 0.0
        ref = self.fn[sel][:, None, :] if to is None else np.asarray(to, float)
        return float(np.degrees(np.arccos(np.clip((self.cn[sel] * ref).sum(axis=-1), -1.0, 1.0))).max())


def cut_face_material(sc):
    """The material the cut faces are shown with: the workpiece's slot for cut faces."""
    wp = machining.workpiece(sc)
    slot = wp.data.get(machining.CUT_SLOT)
    assert slot is not None and len(wp.material_slots) > slot, "the milled mesh has no slot for cut faces"
    return wp.material_slots[slot].material


def marks_node(mat):
    """The "FR tool marks" node of a material, or None."""
    if mat is None or mat.node_tree is None:
        return None
    return next((n for n in mat.node_tree.nodes
                 if n.bl_idname == "ShaderNodeGroup" and n.node_tree is not None and n.node_tree.name == GROUP), None)


def all_nodes(tree, seen=None):
    seen = set() if seen is None else seen
    for n in tree.nodes:
        yield n
        if n.bl_idname == "ShaderNodeGroup" and n.node_tree is not None and n.node_tree.name not in seen:
            seen.add(n.node_tree.name)
            yield from all_nodes(n.node_tree, seen)


def wave(signal, pixel, period):
    """How strongly a row of pixels (``pixel`` wide) repeats every ``period``: the size of that wave in it."""
    win = np.hanning(len(signal))
    s = (signal - signal.mean()) * win
    x = (np.arange(len(s)) + 0.5) * pixel
    return float(abs(np.exp(-2j * math.pi * x / period) @ s) / win.sum() * 2)


def find_period(signal, pixel, lo, hi):
    """The period between lo and hi a row of pixels repeats with: where that wave and its first two overtones
    together are strongest (a saw-tooth has strong overtones)."""
    periods = np.exp(np.linspace(math.log(lo), math.log(hi), 3000))
    power = [sum(wave(signal, pixel, p / k) ** 2 for k in (1, 2, 3)) for p in periods]
    return float(periods[int(np.argmax(power))])


# ---------------------------------------------------------------------------
# the set-ups several tests share (built once; a test that leaves one changed calls spoil())
# ---------------------------------------------------------------------------

# Two passes across each other, no program: the Ø10 end mill goes along +X at y 0, 2 mm deep (floor z 68), lifts,
# then the table carries the block so that the tool goes along +Y at x 0, 5 mm deep (floor z 65).
CROSSING = (("X", -40, ""), ("Z", -22, ""), ("X", 40, ""), ("Z", 0, "first"), ("X", 0, ""), ("Y", 40, ""),
            ("Z", -25, ""), ("Y", -40, ""), ("Z", 0, ""))

# Four tools from the tool list.
# T1 face mill Ø50: a strip along +X at Y-60, 1 deep, F2400 at S3000 = 0.8 mm per turn.
# T2 end mill Ø10, 2 flutes, S12000: a pocket in two depths - 3 deep along +X at Y20 (y 15 .. 25) and back along -X
#    at Y26 (y 21 .. 31) at F600 = 0.025 mm per tooth, then 6 deep along +X at Y23 (y 18 .. 28) at F1200 = 0.05 mm
#    per tooth, which leaves a ledge 3 mm wide at each side; then a round groove 2 deep, clockwise (G2), radius 20
#    about (-50, 60), at F600.
# T3 drill Ø6: a hole 10 deep at X60 Y70, F200 at S8000 = 0.025 mm per turn.
# T4 chamfer mill 90 degrees: a V groove 2 deep along +X at Y-10.
# The tool is lifted to Z60 before each change: the next tool with its holder is up to 28 mm longer, and the change
# happens where the spindle stands. (Changed at Z10, as the test tour's "Three tools" program does, the new tool
# stands 17.7 mm inside the block and leaves a Ø10 hole there - so it was before this task too.) The program ends
# with the table back at Y0, so at the last frame the block stands where it stood at the start.
F_FACE, S_FACE = 2400.0, 3000.0
F_END, F_DEEP, S_END, FLUTES_END = 600.0, 1200.0, 12000.0, 2
F_DRILL, S_DRILL = 200.0, 8000.0
F_VEE, S_VEE = 800.0, 10000.0
GROOVE = (-50.0, 60.0, 20.0)                 # the round groove: centre x, y and radius; its floor at z 68
FOUR_TOOLS = f"""%
(FACE MILL, END MILL, DRILL, CHAMFER MILL)
G21 G90 G94 G17 G54
T1 M6 G43 H1
S{S_FACE:g} M3
G0 X-40 Y-60 Z5
G1 Z-1 F{F_FACE:g}
G1 X40
G0 Z60
M5
T2 M6 G43 H2
S{S_END:g} M3
G0 X-40 Y20 Z5
G1 Z-3 F{F_END:g}
G1 X40
G1 Y26
G1 X-40
G1 Y23
G1 Z-6
G1 X40 F{F_DEEP:g}
G0 Z5
G0 X{GROOVE[0] - GROOVE[2]:g} Y{GROOVE[1]:g}
G1 Z-2 F{F_END:g}
G2 X{GROOVE[0] - GROOVE[2]:g} Y{GROOVE[1]:g} I{GROOVE[2]:g} J0
G0 Z60
M5
T3 M6 G43 H3
S{S_DRILL:g} M3
G0 X60 Y70 Z5
G1 Z-10 F{F_DRILL:g}
G0 Z60
M5
T4 M6 G43 H4
S{S_VEE:g} M3
G0 X-40 Y-10 Z5
G1 Z-2 F{F_VEE:g}
G1 X40
G0 Z60
G0 X60 Y0
M5
M30
%
"""
STRIP_Y, STRIP_Z = -60.0, 69.0              # the faced strip's middle line and floor
HOLE = (60.0, 70.0)

# One tool, one feed (the end mill that is in the spindle): a slot 2 deep along +X.
ONE_FEED = """%
G21 G90 G17 G54
S12000 M3
G0 X-40 Y0 Z5
G1 Z-2 F800
G1 X40
G0 Z10
M5
M30
%
"""


def tool_list(sc, face=True, end=True, drill=True, vee=True):
    if face:
        r = tools.add_row(sc, "FACE", 1)
        r.diameter, r.length, r.holder, r.holder_length, r.lead_angle = 0.05, 0.085, "BT30", 0.045, math.pi / 2
    if end:
        r = tools.add_row(sc, "FLAT", 2)
        r.diameter, r.length, r.holder, r.holder_length, r.flutes = 0.01, 0.098, "BT30", 0.06, FLUTES_END
    if drill:
        r = tools.add_row(sc, "DRILL", 3)
        r.diameter, r.length, r.holder, r.holder_length = 0.006, 0.09, "BT30", 0.06
    if vee:
        r = tools.add_row(sc, "VEE", 4)
        r.diameter, r.length, r.holder, r.holder_length = 0.01, 0.09, "BT30", 0.06


def build_crossing(folder):
    sc = fresh_mill(folder)
    frames, after = joint_animation(sc, CROSSING)
    pick_bit_and_block(sc)
    machining.sample(sc)
    sc.frame_set(frames)
    _KEPT["crossing"] = dict(frames=frames, after_first=after["first"])
    return sc


def build_program(folder):
    sc = fresh_mill(folder)
    cnc_machine(sc)
    tool_list(sc)
    program_step(sc, folder, FOUR_TOOLS, fit=10.0)
    show_end(sc)
    return sc


def build_toolpath(folder):
    """Task 0029's test model, set up and made as its test tour stop does (a coarse program, detail Fast)."""
    from fresing_render.blender import toolpath
    sc = fresh(folder, os.path.join(DATA, toolpath.TEST_MODEL))
    toolpath.set_up_test_model(sc, detail="DRAFT")
    t = toolpath.settings(sc)
    t.scallop, t.step_down, t.stepover = 0.0005, 0.010, 90.0
    a = sc.fresing.animations.add()
    a.name, a.tail = "Toolpath", 0.0
    sc.fresing.animations_index = list(sc.fresing.animations).index(a)
    out = toolpath.make(sc, os.path.join(str(folder), "toolpath.ngc"))
    assert not out["problems"], out["problems"]
    a, blk = toolpath.step(sc)
    blk.gcode_fit = 10.0
    machining.settings(sc).detail = "FAST"
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    machining.update_if_needed(sc)
    _KEPT["toolpath"] = dict(roughed=int(next(f for f, n in gcode.schedule(sc) if n == 2)) - 1)
    return sc


def build_rotary(folder):
    """Task 0066's 4-axis test model with its own program: a slot wrapped once round the bar while it turns, then
    a flat 3 deep at A0 and one at A180 (the bar is Ø50 along X, its axis at z 150 mm in its own space)."""
    from fresing_render.blender import rotary
    sc = fresh(folder, os.path.join(DATA, "test_4axis.step"))
    path = os.path.join(str(folder), "prog.ngc")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(rotary.TEST_PROGRAM_4AXIS)
    a = sc.fresing.animations.add()
    a.name, a.tail = "Program", 0.0
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_file = path
    b.gcode_speed, b.gcode_fit = "FIT", 6.0
    rotary.set_up_test_model(sc, b, five=False, milling=True)
    r = animation.bake(sc, a)
    assert not r.get("warnings"), r.get("warnings")
    machining.sample(sc)
    return sc


BUILDERS = {"crossing": build_crossing, "program": build_program, "toolpath": build_toolpath,
            "rotary": build_rotary}


def shared(name, tmp_path_factory):
    """The set-up ``name`` in the open scene: built now unless it is the one that is open."""
    sc = bpy.context.scene
    if sc.get(TAG) != name:
        sc = BUILDERS[name](tmp_path_factory.mktemp(name))
        sc[TAG] = name
    return sc


def spoil():
    """This test changed the open set-up: the next test builds its own."""
    bpy.context.scene[TAG] = ""


@pytest.fixture()
def crossing(tmp_path_factory):
    return shared("crossing", tmp_path_factory)


@pytest.fixture()
def program(tmp_path_factory):
    return shared("program", tmp_path_factory)


# ---------------------------------------------------------------------------
# Done when 1: each cut triangle knows the move that made it last
# ---------------------------------------------------------------------------

def test_two_passes_across_each_other_each_shows_its_own_marks(crossing):
    sc = crossing
    sc.frame_set(_KEPT["crossing"]["frames"])
    m = Milled(sc)
    assert m.has_marks, f"the milled mesh has no tool-mark attributes: {m.names}"
    for name in TM.ATTRS:
        assert m.domains[name] == ("FACE", "FLOAT_VECTOR"), (name, m.domains[name])
    # where the passes cross, the second (deeper) pass shows: its floor, its direction
    for x, y in ((0.7, 1.3), (-3.1, 2.2), (2.9, -3.6)):
        i = m.under(x, y)
        assert m.cut[i] and m.kind[i] == TM.ARCS, f"crossing at ({x}, {y}): not a cut floor with arcs"
        assert m.height(i) == pytest.approx(65.0, abs=0.01), "the crossing is not at the second pass's depth"
        assert m.d[i] == pytest.approx(Y, abs=1e-4), f"the crossing shows direction {m.d[i]}, the second pass went +Y"
    # the first pass's floor outside the crossing keeps the first pass's marks
    for x, y in ((20.3, 1.1), (-30.2, 2.7), (9.4, -3.3), (-8.6, 0.4)):
        i = m.under(x, y)
        assert m.cut[i] and m.kind[i] == TM.ARCS and m.height(i) == pytest.approx(68.0, abs=0.01)
        assert m.d[i] == pytest.approx(X, abs=1e-4), f"pass 1's floor at ({x}, {y}) shows direction {m.d[i]}, not +X"
    # the second pass's floor outside the crossing (the table moved the block: the marks are in the block's space)
    for x, y in ((1.2, 20.4), (-2.1, -30.3)):
        i = m.under(x, y)
        assert m.cut[i] and m.kind[i] == TM.ARCS and m.height(i) == pytest.approx(65.0, abs=0.01)
        assert m.d[i] == pytest.approx(Y, abs=1e-4), f"pass 2's floor at ({x}, {y}) shows direction {m.d[i]}, not +Y"
    # both floors: the Ø10 end mill's arcs, the tool's axis straight up, the start point on the floor's plane
    fl = m.cut & m.level() & (m.fn[:, 2] > 0)
    assert fl.sum() > 20 and set(m.kind[fl]) == {TM.ARCS}
    assert m.radius[fl] == pytest.approx(5 * MM, abs=1e-6)
    assert m.a[fl] == pytest.approx(np.tile(Z, (fl.sum(), 1)), abs=1e-4)
    assert np.abs(((m.c[fl] - m.o[fl]) * m.a[fl]).sum(axis=1)).max() < 5e-6, "the floors do not lie at the tip's height"
    # what the cutter did not touch has no marks; what it cut has
    top = m.under(61.3, 57.1)
    assert not m.cut[top] and m.kind[top] == TM.NONE and m.height(top) == pytest.approx(70.0, abs=0.01)
    assert np.all(m.kind[~m.cut] == TM.NONE), "faces of the stock that were not cut carry tool marks"
    assert np.all(m.kind[m.cut & m.real] != TM.NONE), "some cut faces do not know their move"


def test_scrubbing_back_shows_the_first_pass_again(crossing):
    sc = crossing
    k = _KEPT["crossing"]
    sc.frame_set(k["frames"])
    end = Milled(sc)
    sc.frame_set(k["after_first"])                      # the first pass is done, the second has not started
    m = Milled(sc)
    i = m.under(0.7, 1.3)
    assert m.cut[i] and m.kind[i] == TM.ARCS and m.height(i) == pytest.approx(68.0, abs=0.01)
    assert m.d[i] == pytest.approx(X, abs=1e-4), "before the second pass the crossing must show the first pass (+X)"
    j = m.under(1.2, 20.4)
    assert not m.cut[j] and m.kind[j] == TM.NONE, "the second pass's place is cut before the second pass"
    sc.frame_set(k["frames"])                           # and forward again: exactly what was there
    again = Milled(sc)
    assert again.n == end.n
    for a, b in ((again.o, end.o), (again.d, end.d), (again.a, end.a), (again.p, end.p)):
        assert np.array_equal(a, b), "scrubbing back and forth changed the marks"


# ---------------------------------------------------------------------------
# Done when 5: no dark facets
# ---------------------------------------------------------------------------

def check_flat_faces_are_shaded_flat(m, where):
    assert m.domains.get("custom_normal") == ("CORNER", "FLOAT_VECTOR"), \
        f"{where}: the milled mesh has no normals of its own per corner: {m.domains.get('custom_normal')}"
    floors = m.cut & m.level() & (m.fn[:, 2] > 0)
    top = ~m.cut & m.level(70.0)
    assert floors.sum() > 10 and top.sum() >= 2, (floors.sum(), top.sum())
    worst = m.corner_angle(floors)
    assert worst < 0.5, f"{where}: a flat cut floor is shaded {worst:.2f} degrees off flat (a dark facet)"
    worst = m.corner_angle(top)
    assert worst < 0.5, f"{where}: the block's untouched top is shaded {worst:.2f} degrees off flat"


def test_no_dark_facets_after_two_passes(crossing):
    crossing.frame_set(_KEPT["crossing"]["frames"])
    assert machining.refresh(crossing, force=True)
    check_flat_faces_are_shaded_flat(Milled(crossing), "two passes across each other")
    crossing.frame_set(_KEPT["crossing"]["after_first"] + 12)          # the tool is in the cut
    check_flat_faces_are_shaded_flat(Milled(crossing), "half way through the second pass")
    crossing.frame_set(_KEPT["crossing"]["frames"])


# ---------------------------------------------------------------------------
# Done when 4: the sheen follows the arcs; strength by material
# ---------------------------------------------------------------------------

def test_cut_material_takes_its_sheen_from_the_marks(crossing):
    sc = crossing
    mat = cut_face_material(sc)
    node = marks_node(mat)
    assert node is not None, f"the cut faces' material '{mat.name}' has no '{GROUP}' node"
    bsdf = next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    for socket in ("Tangent", "Anisotropic", "Normal", "Roughness"):
        links = bsdf.inputs[socket].links
        assert links and links[0].from_node == node, f"the BSDF's {socket} does not come from the tool marks"
    # the nodes read the same four attributes the mesh carries
    read = {n.attribute_name for n in all_nodes(node.node_tree) if n.bl_idname == "ShaderNodeAttribute"}
    assert set(TM.ATTRS) <= read, f"the node group reads {sorted(read)}, the mesh carries {TM.ATTRS}"
    assert "Size" in node.inputs and "Strength" in node.inputs


def test_marks_are_crisp_on_aluminium_finer_on_steel_faint_on_plastic(crossing):
    from fresing_render.blender import toolmarks as nodes
    sc = crossing
    ridge, sheen = nodes.LOOK_INPUTS["ridge"], nodes.LOOK_INPUTS["anisotropic"]
    got = {}
    try:
        for block in ("aluminium_machined", "steel_raw", "cast_iron", "pom_white"):
            block_group(sc).material = block
            assert machining.refresh(sc, force=True)
            node = marks_node(cut_face_material(sc))
            assert node is not None, f"a block of {block}: the cut faces have no tool marks"
            got[block] = (node.inputs[ridge].default_value, node.inputs[sheen].default_value)
    finally:
        block_group(sc).material = "aluminium_machined"
        machining.refresh(sc, force=True)
    assert got["aluminium_machined"][0] > got["steel_raw"][0] > got["cast_iron"][0] > 0, got
    assert got["aluminium_machined"][1] > got["steel_raw"][1] > got["cast_iron"][1] > 0, got
    assert 0 < got["pom_white"][0] <= got["cast_iron"][0], f"plastic: only faint lines, got {got['pom_white']}"
    assert got["pom_white"][1] == 0, f"plastic has no sheen across its marks, got {got['pom_white'][1]}"


def test_a_painted_block_as_imported_shows_tool_marks_too(tmp_path):
    """An imported part is painted until its material is picked in 3 Looks (the test mill's block: satin paint).
    'Tool marks' is ticked by default and the panel shows its line - so the cut faces must show marks (the brief:
    "a milled face shows the marks of the tool that made it"), or the panel must not offer them."""
    sc = fresh_mill(tmp_path, material="")
    assert block_group(sc).material.startswith("paint"), block_group(sc).material
    frames, _after = joint_animation(sc, (("Z", -25, ""), ("X", 50, ""), ("Z", 0, "")))
    pick_bit_and_block(sc)
    machining.sample(sc)
    sc.frame_set(frames)
    m = machining.settings(sc)
    assert m.marks and m.cut_look == "AUTO"
    text = machining.marks_source(sc)
    assert Milled(sc).has_marks
    mat = cut_face_material(sc)
    assert marks_node(mat) is not None, (
        f"painted block, Tool marks ticked, the panel says '{text}' - but the cut faces' material "
        f"'{mat.name}' has no '{GROUP}' node: no marks show")


# ---------------------------------------------------------------------------
# Done when 6: scripts off, off / on, Mark size and Strength, the panel's line
# ---------------------------------------------------------------------------

def test_works_with_scripts_off_no_drivers_no_script_nodes(crossing):
    sc = crossing
    mat = cut_face_material(sc)
    node = marks_node(mat)
    assert node is not None
    assert mat.animation_data is None and mat.node_tree.animation_data is None, "the cut material has drivers"
    assert node.node_tree.animation_data is None, f"the node group '{GROUP}' has drivers"
    assert machining.workpiece(sc).data.animation_data is None, "the milled mesh has drivers"
    kinds = {n.bl_idname for n in all_nodes(mat.node_tree)}
    assert "ShaderNodeScript" not in kinds, "the cut material uses a script node"
    assert not [k for k in kinds if "Image" in k], f"the cut material needs a picture file: {sorted(kinds)}"


def test_settings_are_on_by_default_and_have_tooltips(crossing):
    m = machining.settings(crossing)
    props = m.bl_rna.properties
    assert props["marks"].default is True, "Tool marks is not on by default"
    assert props["marks_size"].default == 1.0 and props["marks_strength"].default == 1.0
    assert (props["marks_size"].hard_min, props["marks_size"].hard_max) == (1.0, 10.0), "Mark size: 1 (real) to 10"
    assert props["marks_strength"].hard_min == 0.0
    for key in ("marks", "marks_size", "marks_strength"):
        assert len(props[key].description) > 30 and "\n" not in props[key].description, f"{key} has no tooltip"


def test_tool_marks_off_takes_them_away_and_on_brings_them_back(crossing):
    sc = crossing
    m = machining.settings(sc)
    before = Milled(sc)
    assert before.has_marks and marks_node(cut_face_material(sc)) is not None
    try:
        m.marks = False
        off = Milled(sc)
        left = [k for k in TM.ATTRS if k in off.names]
        assert not left, f"Tool marks off: the milled mesh still carries {left}"
        assert marks_node(cut_face_material(sc)) is None, "Tool marks off: the cut material still has the node"
        assert off.n == before.n and off.cut.sum() == before.cut.sum(), "Tool marks off changed the cut itself"
        check = off.cut & off.level() & (off.fn[:, 2] > 0)
        assert off.corner_angle(check) < 0.5, "Tool marks off: the floors are not shaded flat any more"
    finally:
        m.marks = True
    on = Milled(sc)
    assert on.has_marks and marks_node(cut_face_material(sc)) is not None, "Tool marks on again: not back"
    assert np.array_equal(on.p, before.p) and np.array_equal(on.d, before.d)


def test_cut_material_off_and_on_again_keeps_the_marks(crossing):
    sc = crossing
    s = machining.settings(sc)
    wp = machining.workpiece(sc)
    before = Milled(sc)
    try:
        s.enabled = False                              # 'Cut material' off: the block shows its CAD shape
        assert not any(k in wp.data.attributes for k in TM.ATTRS)
        s.marks = False                                # changing the settings meanwhile breaks nothing
        s.marks = True
        s.marks_size = 3.0
    finally:
        s.enabled = True
        s.marks_size = 1.0
    sc.frame_set(_KEPT["crossing"]["frames"])
    assert machining.refresh(sc, force=True)
    after = Milled(sc)
    assert after.has_marks and after.n == before.n and np.array_equal(after.p, before.p)
    assert marks_node(cut_face_material(sc)) is not None


def test_mark_size_and_strength_change_the_nodes_and_nothing_else(crossing):
    sc = crossing
    m = machining.settings(sc)
    mat = cut_face_material(sc)
    node = marks_node(mat)
    me = machining.workpiece(sc).data
    me.attributes.new("fr_test_not_rewritten", "FLOAT", "FACE")      # writing the mesh again would drop this
    was = (mat.as_pointer(), len(mat.node_tree.nodes), len(mat.node_tree.links), mat.name)
    try:
        m.marks_size = 6.0
        m.marks_strength = 1.7
        mat2 = cut_face_material(sc)
        node2 = marks_node(mat2)
        assert node2 is not None
        assert node2.inputs["Size"].default_value == pytest.approx(6.0), "Mark size did not reach the nodes"
        assert node2.inputs["Strength"].default_value == pytest.approx(1.7), "Strength did not reach the nodes"
        assert (mat2.as_pointer(), len(mat2.node_tree.nodes), len(mat2.node_tree.links), mat2.name) == was, \
            "changing Mark size or Strength built the material again"
        assert "fr_test_not_rewritten" in machining.workpiece(sc).data.attributes, \
            "changing Mark size or Strength wrote the mesh again"
        assert node is not None
    finally:
        m.marks_size, m.marks_strength = 1.0, 1.0
        a = machining.workpiece(sc).data.attributes.get("fr_test_not_rewritten")
        if a is not None:
            machining.workpiece(sc).data.attributes.remove(a)
    assert marks_node(cut_face_material(sc)).inputs["Size"].default_value == pytest.approx(1.0)


def test_panel_line_without_a_program_names_the_typical_feed(crossing):
    sc = crossing
    text = machining.marks_source(sc)
    assert text.lower().startswith("no program"), text
    assert "aluminium" in text and "0.05 mm per tooth" in text, text
    m = Milled(sc)
    fl = m.cut & m.level() & (m.fn[:, 2] > 0)
    assert m.spacing[fl] == pytest.approx(0.05 * MM, rel=1e-4), "the floor's marks are not 0.05 mm apart"


# ---------------------------------------------------------------------------
# Done when 2: face mill - arcs with the right radius and spacing
# ---------------------------------------------------------------------------

def test_face_mill_arcs_have_the_mills_radius_and_the_feed_per_turn(program):
    sc = program
    show_end(sc)
    rows = [(f, s) for _frame, f, s in gcode.feeds(sc)]
    assert rows == [(F_FACE, S_FACE), (F_END, S_END), (F_DEEP, S_END), (F_END, S_END), (F_DRILL, S_DRILL),
                    (F_VEE, S_VEE), (0.0, 0.0)], f"the build kept these feeds and speeds: {rows}"
    m = Milled(sc)
    assert m.has_marks
    per_turn = F_FACE / S_FACE * MM                                    # 0.8 mm
    for x, y in ((0.7, -58.9), (-31.3, -44.2), (27.9, -79.6), (55.1, -61.7), (-12.4, -83.2)):
        i = m.under(x, y)
        assert m.cut[i] and m.kind[i] == TM.ARCS, f"faced strip at ({x}, {y}): kind {m.kind[i]}, not arcs"
        assert m.height(i) == pytest.approx(STRIP_Z, abs=0.01)
        assert m.radius[i] == pytest.approx(25 * MM, abs=1e-6), f"arcs of radius {m.radius[i] / MM} mm, mill Ø50"
        assert m.spacing[i] == pytest.approx(per_turn, rel=1e-4), \
            f"arcs {m.spacing[i] / MM:.4f} mm apart; F{F_FACE:g} / S{S_FACE:g} = {per_turn / MM} mm per turn"
        assert m.d[i] == pytest.approx(X, abs=1e-4) and m.a[i] == pytest.approx(Z, abs=1e-4)
    strip = m.cut & m.level(STRIP_Z) & (m.fn[:, 2] > 0)
    assert strip.sum() > 20 and set(m.kind[strip]) == {TM.ARCS}
    assert m.radius[strip] == pytest.approx(25 * MM, abs=1e-6)
    assert m.spacing[strip] == pytest.approx(per_turn, rel=1e-4)
    # the centres of the arcs run along the pass: the start point lies on the line y -60, at the floor's height
    assert m.o[strip][:, 1] == pytest.approx(STRIP_Y * MM, abs=2e-6)
    assert m.o[strip][:, 2] == pytest.approx(STRIP_Z * MM, abs=2e-6)


def test_points_on_one_arc_have_the_same_mark_number(program):
    sc = program
    show_end(sc)
    m = Milled(sc)
    i = m.under(0.7, -58.9)
    o, d, a, radius, spacing = m.o[i], m.d[i], m.a[i], m.radius[i], m.spacing[i]
    w = np.cross(a, d)
    angles = np.radians(np.linspace(-80, 80, 9))
    for s in (0.030, 0.050, 0.0712):                    # the tool's centre this far along the pass
        centre = o + s * d
        pts = centre + radius * (np.cos(angles)[:, None] * d + np.sin(angles)[:, None] * w)
        for p in pts:                                   # these points are on the faced floor, cut by this move
            j = m.under(p[0] / MM, p[1] / MM)
            assert m.kind[j] == TM.ARCS and m.o[j] == pytest.approx(o, abs=1e-9), "not on the faced floor"
            assert abs((p - o) @ a) < 2e-6
        u, ridge, groove = TM.pattern(TM.ARCS, pts, o, d, a, radius, spacing)
        assert u == pytest.approx(s, abs=1e-9), f"points {radius / MM:g} mm from one centre have different marks"
        assert np.ptp(ridge) < 1e-6
        along = np.abs((groove * (pts - centre)).sum(axis=1)) / radius
        assert along.max() < 1e-6, "the groove does not run along the arc"
        # one turn of the mill later: the next arc, the same place in its mark
        _u2, ridge2, _g2 = TM.pattern(TM.ARCS, pts + spacing * d, o, d, a, radius, spacing)
        assert ridge2 == pytest.approx(ridge, abs=1e-5)
        # and half a turn later the other end of a mark
        _u3, ridge3, _g3 = TM.pattern(TM.ARCS, pts + 0.25 * spacing * d, o, d, a, radius, spacing)
        assert np.abs(ridge3 - ridge).max() > 0.1


def test_end_mill_pocket_floor_arcs_follow_each_pass(program):
    sc = program
    show_end(sc)
    m = Milled(sc)
    slow = F_END / S_END / FLUTES_END * MM                             # 0.025 mm per tooth
    fast = F_DEEP / S_END / FLUTES_END * MM                            # 0.05 mm: the deeper pass is fed faster
    spots = (("the ledge the first pass left", (3.3, 16.4), 67.0, X, slow),
             ("the ledge the pass back left", (-7.1, 29.6), 67.0, -X, slow),
             ("the deeper floor", (2.9, 22.7), 64.0, X, fast),
             ("the deeper floor", (-21.7, 19.2), 64.0, X, fast))
    for what, (x, y), z, feed, per_tooth in spots:
        i = m.under(x, y)
        assert m.cut[i] and m.kind[i] == TM.ARCS, f"{what}: kind {m.kind[i]}, not arcs"
        assert m.height(i) == pytest.approx(z, abs=0.01), what
        assert m.d[i] == pytest.approx(feed, abs=1e-4), f"{what}: marks along {m.d[i]}, the pass went {feed}"
        assert m.radius[i] == pytest.approx(5 * MM, abs=1e-6), what
        assert m.spacing[i] == pytest.approx(per_tooth, rel=1e-4), \
            f"{what}: marks {m.spacing[i] / MM:.4f} mm apart, feed per tooth is {per_tooth / MM} mm"


def pocket_wall(m, y, facing, z0, z1):
    """The straight wall of the pocket at ``y`` mm (between z0 and z1), away from the pocket's round ends."""
    ys, zs = m.P[:, :, 1] / MM, m.P[:, :, 2] / MM
    return (m.cut & (m.area > 1e-8) & (np.abs(ys - y).max(axis=1) < 0.01) & (m.fn[:, 1] * facing > 0.9999)
            & (np.abs(m.c[:, 0]) < 30 * MM) & (zs.min(axis=1) > z0 - 0.01) & (zs.max(axis=1) < z1 + 0.01))


def test_pocket_walls_have_feed_lines_and_the_step_down_shows(program):
    sc = program
    show_end(sc)
    m = Milled(sc)
    slow, fast = F_END / S_END / FLUTES_END * MM, F_DEEP / S_END / FLUTES_END * MM
    walls = {"upper wall at y 15": (pocket_wall(m, 15, +1, 67, 70), 67.0, X, slow),
             "upper wall at y 31": (pocket_wall(m, 31, -1, 67, 70), 67.0, -X, slow),
             "lower wall at y 18": (pocket_wall(m, 18, +1, 64, 67), 64.0, X, fast),
             "lower wall at y 28": (pocket_wall(m, 28, -1, 64, 67), 64.0, X, fast)}
    for what, (sel, tip_z, feed, per_tooth) in walls.items():
        assert sel.any(), f"{what}: not found"
        assert set(m.kind[sel]) == {TM.FLANK}, f"{what}: kinds {set(m.kind[sel])}, not the lines of the tool's side"
        assert m.d[sel] == pytest.approx(np.tile(feed, (sel.sum(), 1)), abs=1e-4), f"{what}: wrong feed direction"
        assert m.a[sel] == pytest.approx(np.tile(Z, (sel.sum(), 1)), abs=1e-4)
        assert m.spacing[sel] == pytest.approx(per_tooth, rel=1e-4), \
            f"{what}: lines {np.unique(m.spacing[sel]) / MM} mm apart, feed per tooth there is {per_tooth / MM} mm"
        # each depth's wall belongs to the pass at that depth: the two bands differ, a step-down shows
        assert m.o[sel][:, 2] == pytest.approx(tip_z * MM, abs=2e-6), f"{what}: made by a pass at another depth"
        # and it is shaded as a wall: nothing of the ledge's direction in its corners
        tilt = np.degrees(np.arcsin(np.abs(m.cn[sel][:, :, 2]).max()))
        assert tilt < 0.5, f"{what}: its shading leans {tilt:.2f} degrees towards the ledge (the step is blurred)"
    for what, y0, y1 in (("ledge y 15 .. 18", 15, 18), ("ledge y 28 .. 31", 28, 31)):
        ys = m.P[:, :, 1] / MM
        ledge = m.cut & m.level(67.0) & (ys.min(axis=1) > y0 - 0.01) & (ys.max(axis=1) < y1 + 0.01) \
            & (np.abs(m.c[:, 0]) < 30 * MM)
        assert ledge.any(), f"{what}: not found"
        assert m.corner_angle(ledge, to=Z) < 0.5, f"{what}: not shaded flat, the step-down line is blurred"
    floor = m.cut & m.level(64.0)
    assert floor.any() and m.corner_angle(floor, to=Z) < 0.5, "the pocket's floor is not shaded flat"


def test_drilled_hole_has_rings_on_its_point_and_its_wall(program):
    sc = program
    show_end(sc)
    m = Milled(sc)
    off = np.hypot(m.c[:, 0] / MM - HOLE[0], m.c[:, 1] / MM - HOLE[1])
    hole = m.cut & (m.area > 1e-8) & (off < 3.2)
    assert hole.sum() > 30
    assert set(m.kind[hole]) == {TM.RINGS, TM.RINGS_WALL}, f"kinds in the drilled hole: {set(m.kind[hole])}"
    assert m.P[hole][:, :, 2].min() / MM == pytest.approx(60.0, abs=0.02), "the hole is not 10 mm deep"
    cone = hole & (m.fn[:, 2] > 0.3) & (m.fn[:, 2] < 0.99)
    wall = hole & (np.abs(m.fn[:, 2]) < 0.01)
    assert cone.sum() > 10 and set(m.kind[cone]) == {TM.RINGS}, "the drill point's cone has no rings"
    assert wall.sum() > 10 and set(m.kind[wall]) == {TM.RINGS_WALL}, "the hole's wall has no rings"
    per_turn = F_DRILL / S_DRILL * MM                                  # 0.025 mm
    assert m.spacing[wall] == pytest.approx(per_turn, rel=1e-4), \
        f"rings on the wall {np.unique(m.spacing[wall]) / MM} mm apart, the drill feeds {per_turn / MM} mm per turn"
    assert TM.SPACING_MIN <= m.spacing[cone].min() and m.spacing[cone].max() <= TM.SPACING_MAX
    # shaded as a round hole: the wall smooth round the hole (each flat facet's corners lean towards its
    # neighbours), and nothing of the point's cone in the wall's shading
    lean = m.corner_angle(wall)
    assert 1.0 < lean < 8.0, f"the hole's wall is not shaded round: its corners lean {lean:.2f} degrees"
    tilt = np.degrees(np.arcsin(np.abs(m.cn[wall][:, :, 2]).max()))
    assert tilt < 0.5, f"the hole's wall is shaded {tilt:.2f} degrees towards the drill point (a sharp edge blurred)"
    for sel in (cone, wall):                           # rings round the hole's own axis
        assert np.abs(m.d[sel]).max() < 1e-6, "a straight plunge has no feed direction"
        assert m.a[sel] == pytest.approx(np.tile(Z, (sel.sum(), 1)), abs=1e-4)
        assert np.hypot(m.o[sel][:, 0] / MM - HOLE[0], m.o[sel][:, 1] / MM - HOLE[1]).max() < 0.005


def test_round_groove_marks_turn_with_the_tool(program):
    """A full circle (G2, clockwise): on the groove's floor the marks point the way the tool went at that place."""
    sc = program
    show_end(sc)
    m = Milled(sc)
    cx, cy, r = GROOVE
    for deg in (20, 65, 110, 155, 200, 245, 290, 335):
        t = math.radians(deg)
        i = m.under(cx + r * math.cos(t), cy + r * math.sin(t))
        assert m.cut[i] and m.kind[i] == TM.ARCS, f"round groove at {deg} degrees: kind {m.kind[i]}, not arcs"
        assert m.height(i) == pytest.approx(68.0, abs=0.01)
        went = np.array([math.sin(t), -math.cos(t), 0.0])              # clockwise seen from above
        off = math.degrees(math.acos(float(np.clip(m.d[i] @ went, -1, 1))))
        # (the Ø10 tool's edge reaches a spot 5 mm = 14 degrees of the circle before its centre does)
        assert off < 25, f"round groove at {deg} degrees: marks point {off:.0f} degrees off the tool's way {went}"
        assert m.spacing[i] == pytest.approx(F_END / S_END / FLUTES_END * MM, rel=1e-4)


def test_chamfer_mill_leaves_lines_along_its_path(program):
    sc = program
    show_end(sc)
    m = Milled(sc)
    for x, y in ((-20.3, -11.1), (0.7, -9.2), (25.4, -10.9), (31.8, -8.7)):          # both flanks of the V
        i = m.under(x, y)
        assert m.cut[i] and 68.0 < m.height(i) < 70.0, f"no V groove at ({x}, {y})"
        assert m.kind[i] == TM.ALONG, f"V groove at ({x}, {y}): kind {m.kind[i]}, not lines along the path"
        assert m.d[i] == pytest.approx(X, abs=1e-4) and m.a[i] == pytest.approx(Z, abs=1e-4)
        assert TM.SPACING_MIN <= m.spacing[i] <= TM.SPACING_MAX
        assert abs(abs(m.fn[i][1]) - math.sqrt(0.5)) < 0.01, "the V's flank is not at 45 degrees"


def test_no_dark_facets_after_four_tools(program):
    show_end(program)
    check_flat_faces_are_shaded_flat(Milled(program), "face mill, pocket, round groove, hole and V groove")


def test_v_groove_flat_flanks_are_shaded_flat(program):
    """The two flanks of the chamfer mill's straight groove are flat faces, 80 mm long (two triangles each). The
    brief: "flat faces flat". Where a flank meets the round end of the groove its corners must not take the
    cone's direction - the error would be spread over the whole flank."""
    sc = program
    show_end(sc)
    m = Milled(sc)
    flanks = m.cut & (m.kind == TM.ALONG) & (m.area > 1e-6) & (np.abs(m.fn[:, 0]) < 1e-3) \
        & (np.abs(np.abs(m.fn[:, 1]) - math.sqrt(0.5)) < 0.01)
    assert flanks.sum() >= 4, "the V groove's flanks were not found"
    worst = m.corner_angle(flanks)
    assert worst < 0.5, (f"the V groove's flat flanks ({m.area[flanks].sum() / MM ** 2:.0f} mm2) are shaded "
                         f"{worst:.2f} degrees off flat at their ends")


def test_panel_line_with_a_program_says_so(program):
    text = machining.marks_source(program)
    assert "program" in text.lower() and "no program" not in text.lower() and "typical" not in text.lower(), text


def test_render_shows_the_arcs_one_per_turn_times_mark_size(program, tmp_path):
    """One small Cycles picture from straight above the faced strip, Mark size 10, a lamp low over +X: along the
    feed the brightness repeats every (feed per turn) x 10 = 8 mm, within 5 %."""
    sc = program
    show_end(sc)
    wp = machining.workpiece(sc)
    assert np.allclose(np.array(wp.matrix_world), np.eye(4), atol=1e-5), "the block is not back where it started"
    machining.settings(sc).marks_size = 10.0
    spoil()
    for o in sc.objects:
        o.hide_render = o is not wp
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.use_denoising = False
    sc.cycles.pixel_filter_type = "BOX"
    sc.cycles.samples = 32
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 160, 20, 100
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.view_settings.view_transform = "Standard"
    sc.world = bpy.data.worlds.new("dark")
    cam = bpy.data.objects.new("above", bpy.data.cameras.new("above"))
    sc.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale = "ORTHO", 0.080               # 80 mm along the feed: 0.5 mm per pixel
    cam.matrix_world = wp.matrix_world @ Matrix.Translation((0.0, STRIP_Y * MM, STRIP_Z * MM + 0.25))
    sc.camera = cam
    lamp = bpy.data.objects.new("low lamp", bpy.data.lights.new("low lamp", "SUN"))
    sc.collection.objects.link(lamp)
    lamp.data.energy = 3.0
    up = math.radians(25)
    lamp.rotation_euler = Vector((math.cos(up), 0.0, math.sin(up))).to_track_quat("Z", "Y").to_euler()
    sc.render.filepath = str(tmp_path / "strip.exr")
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(sc.render.filepath)
    px = np.empty(160 * 20 * 4, np.float32)
    img.pixels.foreach_get(px)
    row = px.reshape(20, 160, 4)[7:13, :, :3].mean(axis=(0, 2)).astype(float)      # 3 mm round the middle line
    expect = F_FACE / S_FACE * MM * 10.0
    assert row.max() - row.min() > 0.2 * row.mean(), f"no marks in the picture: {np.round(row[:24], 4)}"
    got = find_period(row, 0.080 / 160, 0.3 * expect, 3.0 * expect)
    assert abs(got - expect) < 0.05 * expect, \
        f"the picture repeats every {got / MM:.2f} mm along the feed; feed per turn x 10 = {expect / MM:.2f} mm"


# ---------------------------------------------------------------------------
# Done when 6: save / reopen, old projects, model update, the render queue
# ---------------------------------------------------------------------------

def test_saved_and_opened_again_keeps_the_marks_and_the_programs_feed(tmp_path):
    sc = fresh_mill(tmp_path)
    cnc_machine(sc)
    program_step(sc, tmp_path, ONE_FEED, fit=3.0)
    show_end(sc)
    text = machining.marks_source(sc)
    assert "F800" in text and "S12000" in text, f"the panel does not name the program's feed and speed: '{text}'"
    edges = re.search(r"(\d+) (flute|insert)", text)
    assert edges, f"the panel does not say how many flutes: '{text}'"
    per_tooth = 800.0 / 12000.0 / int(edges.group(1)) * MM
    m = Milled(sc)
    i = m.under(3.3, 1.9)
    assert m.kind[i] == TM.ARCS and m.height(i) == pytest.approx(68.0, abs=0.01)
    assert m.spacing[i] == pytest.approx(per_tooth, rel=1e-4), \
        f"marks {m.spacing[i] / MM:.4f} mm apart, but the panel says '{text}' = {per_tooth / MM:.4f} mm per tooth"
    s = machining.settings(sc)
    s.marks_size, s.marks_strength = 7.0, 1.5
    end = sc.frame_end
    path = str(tmp_path / "marks.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = machining.settings(sc)
    assert s.marks and s.marks_size == pytest.approx(7.0) and s.marks_strength == pytest.approx(1.5)
    sc.frame_set(1)                                    # the first refresh after opening: nothing cut yet
    first = Milled(sc)
    assert first.has_marks and not first.cut.any()
    sc.frame_set(end)
    again = Milled(sc)
    assert again.has_marks, "after opening the project again the milled mesh has no tool-mark attributes"
    i = again.under(3.3, 1.9)
    assert again.kind[i] == TM.ARCS and again.d[i] == pytest.approx(X, abs=1e-4)
    assert again.spacing[i] == pytest.approx(per_tooth, rel=1e-4), "the program's feed was lost with the file"
    assert np.array_equal(again.p, m.p) and np.array_equal(again.o, m.o)
    node = marks_node(cut_face_material(sc))
    assert node is not None and node.inputs["Size"].default_value == pytest.approx(7.0)
    assert node.inputs["Strength"].default_value == pytest.approx(1.5)
    assert machining.marks_source(sc) == text


def test_building_again_with_another_feed_moves_the_marks(tmp_path):
    """The program is changed to half the feed and built again. The video takes as long as before ('fit into'),
    so the tool's motion is the same - only the feed differs, and the marks must follow it."""
    sc = fresh_mill(tmp_path)
    cnc_machine(sc)
    a = program_step(sc, tmp_path, ONE_FEED, fit=3.0)
    show_end(sc)
    first = Milled(sc)
    i = first.under(3.3, 1.9)
    assert first.kind[i] == TM.ARCS
    slower = tmp_path / "slower.ngc"
    slower.write_text(ONE_FEED.replace("F800", "F400"))
    b = a.blocks[0]
    b.gcode_file = str(slower)
    gcode.step_changed(sc, b)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    machining.update_if_needed(sc)
    show_end(sc)
    text = machining.marks_source(sc)
    assert "F400" in text and "F800" not in text, f"the panel still names the old feed: '{text}'"
    m = Milled(sc)
    i2 = m.under(3.3, 1.9)
    assert m.kind[i2] == TM.ARCS
    assert m.spacing[i2] == pytest.approx(first.spacing[i] / 2, rel=1e-4), \
        f"half the feed, but the marks are {m.spacing[i2] / MM:.4f} mm apart (before: {first.spacing[i] / MM:.4f})"
    fl = m.cut & m.level(68.0)
    assert m.spacing[fl] == pytest.approx(first.spacing[i] / 2, rel=1e-4)


def test_settings_change_nothing_before_anything_is_picked(tmp_path):
    sc = fresh_mill(tmp_path)
    s = machining.settings(sc)
    s.marks = False
    s.marks = True
    s.marks_size, s.marks_strength = 5.0, 0.5
    assert machining.marks_source(sc) == ""
    assert not any(me.get(machining.CUT_TAG) for me in bpy.data.meshes)
    frames, _after = joint_animation(sc, (("Z", -25, ""), ("X", 50, ""), ("Z", 0, "")))
    pick_bit_and_block(sc)
    machining.sample(sc)
    sc.frame_set(frames)
    node = marks_node(cut_face_material(sc))           # what was set before shows once the block is picked
    assert Milled(sc).has_marks and node is not None
    assert node.inputs["Size"].default_value == pytest.approx(5.0)
    assert node.inputs["Strength"].default_value == pytest.approx(0.5)


def test_an_old_project_gets_the_marks_at_its_next_refresh(tmp_path):
    """A project milled before tool marks: its milled mesh has no attributes, its cut material no marks node and
    its settings no 'Tool marks' value. Made here by building with the tick off and then forgetting the tick."""
    sc = fresh_mill(tmp_path)
    frames, _after = joint_animation(sc, (("Z", -25, ""), ("X", 50, ""), ("Z", 0, "")))
    pick_bit_and_block(sc)
    machining.sample(sc)
    sc.frame_set(frames)
    s = machining.settings(sc)
    s.marks = False
    assert not Milled(sc).has_marks and marks_node(cut_face_material(sc)) is None
    for key in ("marks", "marks_size", "marks_strength"):
        s.property_unset(key)
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    s = machining.settings(sc)
    assert not s.is_property_set("marks") and s.marks, "an old project does not get Tool marks by default"
    assert not Milled(sc).has_marks                    # (as it was saved)
    sc.frame_set(frames)                               # the next refresh
    m = Milled(sc)
    assert m.has_marks, "an old project's milled mesh gets no tool-mark attributes"
    assert marks_node(cut_face_material(sc)) is not None, "an old project's cut material gets no tool marks"
    i = m.under(20.3, 1.1)
    assert m.cut[i] and m.kind[i] == TM.ARCS and m.d[i] == pytest.approx(X, abs=1e-4)


def test_model_update_keeps_the_marks(tmp_path):
    sc = fresh_mill(tmp_path)
    frames, _after = joint_animation(sc, (("Z", -25, ""), ("X", 50, ""), ("Z", 0, "")))
    pick_bit_and_block(sc)
    machining.sample(sc)
    click(ob(sc, "FINISHED PART"))
    assert bpy.ops.fresing.mill_set_finished() == {"FINISHED"}
    s = machining.settings(sc)
    s.marks_size = 4.0
    sc.frame_set(frames)
    assert Milled(sc).has_marks
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft", update_root=root.name) == {"FINISHED"}
    s = machining.settings(sc)
    assert s.marks and s.marks_size == pytest.approx(4.0), "the model update lost the tool-mark settings"
    assert s.workpiece is ob(sc, STOCK)
    # the animation keys are cleared by a model update: build it again, and the cut follows
    frames = animation.bake(sc, sc.fresing.animations["Mill"])["frames"]
    machining.update_if_needed(sc)
    sc.frame_set(frames)
    m = Milled(sc)
    assert m.has_marks, "after a model update the milled mesh has no tool-mark attributes"
    i = m.under(20.3, 1.1)                             # the slot's floor, 5 deep, inside the finished part's pocket
    assert m.cut[i] and m.height(i) == pytest.approx(65.0, abs=0.01)
    assert m.kind[i] == TM.ARCS and m.d[i] == pytest.approx(X, abs=1e-4) and m.radius[i] == pytest.approx(0.005)
    node = marks_node(cut_face_material(sc))
    assert node is not None and node.inputs["Size"].default_value == pytest.approx(4.0)
    assert m.corner_angle(m.cut & m.level(65.0), to=Z) < 0.5


FACE_ONLY = f"""%
G21 G90 G94 G17 G54
T1 M6 G43 H1
S{S_FACE:g} M3
G0 X-40 Y-60 Z5
G1 Z-1 F{F_FACE:g}
G1 X40
G0 Z60
G0 X60 Y0
M5
M30
%
"""


def test_queued_still_shows_the_marks_and_none_with_the_tick_off(tmp_path):
    """The real render queue (a background Blender that opens the saved project and builds it again): a still
    from straight above the faced strip, Mark size 10. With Tool marks on the picture repeats every 8 mm along
    the feed (F2400 / S3000 x 10); with the tick off it does not."""
    from PIL import Image

    from fresing_render.blender import queue
    sc = fresh_mill(tmp_path)
    s = sc.fresing
    cnc_machine(sc)
    tool_list(sc, end=False, drill=False, vee=False)
    # hidden and the camera set before Build: Build remembers how things looked, and the queue builds again
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):
        logic.set_hidden(ob(sc, name), True)
    cam = bpy.data.objects.new("above", bpy.data.cameras.new("above"))
    sc.collection.objects.link(cam)
    cam.data.type, cam.data.ortho_scale = "ORTHO", 0.060               # 60 mm along the feed
    cam.matrix_world = Matrix.Translation((0.0, STRIP_Y * MM, STRIP_Z * MM + 0.25))
    sc.camera = cam
    lamp = bpy.data.objects.new("low lamp", bpy.data.lights.new("low lamp", "SUN"))
    sc.collection.objects.link(lamp)
    lamp.data.energy = 3.0
    up = math.radians(25)
    lamp.rotation_euler = Vector((math.cos(up), 0.0, math.sin(up))).to_track_quat("Z", "Y").to_euler()
    machining.settings(sc).marks_size = 10.0
    program_step(sc, tmp_path, FACE_ONLY, fit=3.0)
    show_end(sc)
    assert "program" in machining.marks_source(sc).lower(), machining.marks_source(sc)
    s.use_gpu = False
    s.quality = "draft"
    s.out_format, s.out_custom_w, s.out_custom_h = "custom", 240, 80   # a draft renders half of it: 120 x 40 px

    def queued(name):
        job_index = len(s.queue)
        queue.add_job(sc, "STILL", quality="draft")
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "queued.blend"))
        qdir = queue.start(bpy.context)
        t0 = time.time()
        while queue.is_running(sc) and time.time() - t0 < 300:
            time.sleep(0.5)
        queue.sync(sc)
        job = s.queue[job_index]
        assert job.status == "DONE", (name, job.message, queue.log_tail(qdir, 40))
        img = np.asarray(Image.open(job.output).convert("L"), dtype=float)
        h, w = img.shape
        assert w <= 120, f"the test picture is {w} px wide"
        return img[h // 2 - h // 6:h // 2 + h // 6].mean(axis=0), 0.060 / w

    with_marks, pixel = queued("marks on")
    machining.settings(sc).marks = False
    without, _pixel = queued("marks off")
    expect = F_FACE / S_FACE * MM * 10.0
    on, off = wave(with_marks, pixel, expect), wave(without, pixel, expect)
    assert on > 2.0, f"the queued picture shows no marks every {expect / MM:g} mm (wave {on:.2f} of 255 grey levels)"
    assert on > 4 * off, f"Tool marks on and off look alike in the queue: wave {on:.2f} against {off:.2f}"
    got = find_period(with_marks, pixel, 0.5 * expect, 2.0 * expect)
    assert abs(got - expect) < 0.10 * expect, f"the queued picture repeats every {got / MM:.2f} mm, not 8"
    assert np.abs(with_marks - without).mean() > 1.0, "the two queued pictures are the same"


# ---------------------------------------------------------------------------
# "Not in this task", but must not break: the 4th axis (0066), the app's own toolpath (0029)
# ---------------------------------------------------------------------------

def test_4axis_test_model_runs_with_marks_on(tmp_path_factory):
    sc = shared("rotary", tmp_path_factory)
    assert machining.settings(sc).marks
    end = sc.frame_end
    for f in (1, end // 4, end // 2, 3 * end // 4, end):               # the wrapped slot, then the two flats
        sc.frame_set(f)
        assert machining.refresh(sc, force=True), (f, machining.status(sc))
        m = Milled(sc)
        assert m.has_marks, f"frame {f}: no tool-mark attributes on the turning bar"
        assert np.all(m.kind[~m.cut] == TM.NONE)
        assert np.isfinite(m.o).all() and np.isfinite(m.d).all() and np.isfinite(m.a).all() and np.isfinite(m.p).all()
        known = m.kind > 0
        if known.any():                                # a tool axis and a feed direction are unit vectors
            assert np.linalg.norm(m.a[known], axis=1) == pytest.approx(1.0, abs=1e-3)
            length = np.linalg.norm(m.d[known], axis=1)
            assert np.all((np.abs(length - 1.0) < 1e-3) | (length < 1e-3))
    # the flats are cut by plain straight moves, one with the bar at A0 (now on top) and one at A180 (now
    # underneath): floors with arcs, and the tool's axis as the bar saw it - away from the bar on both sides
    seen = 0
    for below, away in ((False, Z), (True, -Z)):
        for x, y in ((27.3, -6.1), (35.7, 3.4), (44.2, -9.3), (31.9, 8.8)):
            i = m.under(x, y, below=below)
            assert m.cut[i], f"the flat at ({x}, {y}) is not cut"
            assert m.kind[i] == TM.ARCS, f"flat at ({x}, {y}), {'underneath' if below else 'on top'}: kind {m.kind[i]}"
            assert m.a[i] == pytest.approx(away, abs=1e-3), \
                f"flat {'underneath' if below else 'on top'}: the tool's axis is stored as {m.a[i]}, not {away}"
            assert m.fn[i] @ m.a[i] > 0.999 and abs(m.d[i] @ m.a[i]) < 1e-3
            assert m.radius[i] == pytest.approx(3 * MM, abs=1e-6)
            seen += 1
    assert seen == 8


def test_4axis_flats_on_the_bar_are_shaded_flat(tmp_path_factory):
    """No dark facets: the two flats milled into the round bar are flat floors. (Where a flat ends in the bar's
    round skin - 28 degrees between the two there - a few small faces lean towards the skin: measured 15 faces,
    2 of 1,694 mm2, up to 4 degrees. That little is let through here; more of it would show.)"""
    sc = shared("rotary", tmp_path_factory)
    sc.frame_set(sc.frame_end)
    assert machining.refresh(sc, force=True), machining.status(sc)
    m = Milled(sc)
    flats = m.cut & m.level() & (m.kind == TM.ARCS)
    assert flats.sum() > 20
    off = np.degrees(np.arccos(np.clip((m.cn[flats] * m.fn[flats][:, None, :]).sum(axis=-1), -1, 1))).max(axis=1)
    bad = off > 0.5
    share = m.area[flats][bad].sum() / m.area[flats].sum()
    assert share < 0.01 and off.max() < 5.0, (
        f"{bad.sum()} of {flats.sum()} faces of the two flats are shaded off flat, up to {off.max():.2f} degrees: "
        f"{m.area[flats][bad].sum() / MM ** 2:.0f} of {m.area[flats].sum() / MM ** 2:.0f} mm2")


TOOLPATH_GRID = [(x + 0.37, y + 0.21) for x in range(-56, 57, 4) for y in range(-36, 37, 4)]


def cut_faces_seen_from_above(m):
    faces = sorted({m.under(x, y) for x, y in TOOLPATH_GRID})
    return [i for i in faces if m.cut[i]]


def test_app_made_toolpath_shows_marks_on_what_it_cut(tmp_path_factory):
    sc = shared("toolpath", tmp_path_factory)
    sc.frame_set(_KEPT["toolpath"]["roughed"])         # roughing done with the flat end mill
    assert machining.refresh(sc, force=True), machining.status(sc)
    m = Milled(sc)
    assert m.has_marks
    faces = cut_faces_seen_from_above(m)
    assert len(faces) > 20
    assert all(m.kind[i] > 0 for i in faces), "after roughing: cut faces seen from above without marks"
    kinds = {int(m.kind[i]) for i in faces}
    assert TM.ARCS in kinds and TM.ACROSS not in kinds, f"after roughing with a flat end mill: kinds {kinds}"
    sc.frame_set(sc.frame_end)                         # finished with the ball mill
    assert machining.refresh(sc, force=True), machining.status(sc)
    m = Milled(sc)
    assert m.has_marks
    faces = cut_faces_seen_from_above(m)
    blank = [i for i in faces if m.kind[i] == 0]
    assert not blank, f"{len(blank)} of {len(faces)} cut faces seen from above have no marks"
    kinds = {int(m.kind[i]) for i in faces}
    assert TM.ACROSS in kinds, f"after finishing with a ball mill no face has a ball pass's marks: kinds {kinds}"
    per_tooth = m.spacing[[i for i in faces if m.kind[i] == TM.ACROSS]]
    assert TM.SPACING_MIN <= per_tooth.min() and per_tooth.max() <= TM.SPACING_MAX
    assert "program" in machining.marks_source(sc).lower()


def test_app_made_toolpath_flat_floors_stay_flat(tmp_path_factory):
    """No dark facets: the flat floors the end mill left (two levels) are shaded flat - after roughing, and still
    after the ball mill has finished the slopes next to them."""
    sc = shared("toolpath", tmp_path_factory)
    for frame, when in ((_KEPT["toolpath"]["roughed"], "after roughing"), (sc.frame_end, "after finishing")):
        sc.frame_set(frame)
        assert machining.refresh(sc, force=True), machining.status(sc)
        m = Milled(sc)
        floors = m.cut & m.level() & (m.fn[:, 2] > 0) & (m.kind == TM.ARCS)
        assert floors.sum() > 10, when
        off = np.degrees(np.arccos(np.clip((m.cn[floors] * m.fn[floors][:, None, :]).sum(axis=-1), -1, 1))).max(axis=1)
        bad = off > 0.5
        assert not bad.any(), (
            f"{when}: {bad.sum()} of {floors.sum()} flat floor faces are shaded off flat, up to {off.max():.1f} "
            f"degrees: {m.area[floors][bad].sum() / MM ** 2:.0f} of {m.area[floors].sum() / MM ** 2:.0f} mm2 of floor")
