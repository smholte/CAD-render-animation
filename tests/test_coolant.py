"""Task 0042: coolant on the test mill (tests/data/test_mill.step) with a G-code program.

The block (200 x 200 x 40 mm, top at z = 70 mm) sits on the table that slides along Y; the head (spindle Ø60 mm,
bottom at z = 130 mm, the Ø10 end mill's tip at z = 90 mm) moves along X and Z. The program cuts a pocket with
flood on (M8) and switches it off (M9) before it goes up.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import air, animation, build, chips, coolant, gcode, joints, machining  # noqa: E402
from fresing_render.core import coolant as ccore  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"
TOOL = "END MILL D10"

POCKET = """%
(POCKET WITH FLOOD)
(T1 D=10. CR=0. - flat end mill)
G21 G90 G94 G17
S9000 M3
G0 X-30 Y-20 Z5
M8
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
G4 P3
M5
M30
%
"""


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    assert bpy.ops.fresing.cnc_find_axes() == {"FINISHED"}
    click(ob(sc, TOOL))
    assert bpy.ops.fresing.cnc_use_tool() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.cnc_use_workpiece() == {"FINISHED"}
    assert gcode.problem(sc) == ""
    sc["tmp"] = str(tmp_path)
    return sc


def build_program(sc, text=POCKET, fit=4.0, fps=25, **kw):
    path = os.path.join(sc["tmp"], "pocket.ngc")
    with open(path, "w") as fh:
        fh.write(text)
    s = sc.fresing
    a = s.animations.get("Program") or s.animations.add()
    a.name, a.tail, a.fps = "Program", 0.0, str(fps)
    a.blocks.clear()
    b = a.blocks.add()
    b.kind = "GCODE"
    b.gcode_speed, b.gcode_fit, b.gcode_path = "FIT", fit, False
    for k, v in kw.items():
        setattr(b, k, v)
    b.gcode_file = path
    r = animation.bake(sc, a)
    return a, b, r["frames"]


def drawn(sc, f):
    sc.frame_set(f)
    jets = bpy.data.objects.get(coolant.JETS)
    drops = bpy.data.objects.get(coolant.DROPS)
    return (len(jets.data.vertices) if jets else 0), (len(drops.data.vertices) if drops else 0)


# ---------------------------------------------------------------------------


def test_off_by_default_nothing_made(scene):
    _a, b, frames = build_program(scene)
    assert not scene.fresing.coolant.enabled
    assert coolant.root() is None and bpy.data.objects.get(coolant.JETS) is None
    assert not any(coolant.WET_ATTR in o for o in scene.objects)
    assert not any(m.get("fr_coolant_patch") for m in bpy.data.materials)
    assert gcode.info(scene, b).get("coolant", "") == ""
    # M8 is not reported as a problem (it never was: M7/M8/M9 are noted)
    assert not any("M8" in p for p in gcode.info(scene, b)["problems"])


def test_flood_from_the_program(scene):
    scene.fresing.coolant.enabled = True
    _a, b, frames = build_program(scene)
    sp = coolant.spans()
    assert len(sp) == 1 and sp[0, 2] == ccore.FLOOD
    assert 1 <= sp[0, 0] < 0.3 * frames and 0.5 * frames < sp[0, 1] < frames
    assert gcode.info(scene, b)["coolant"].startswith("Coolant: flood 1 time")
    r = coolant.root()
    assert r is not None and r.parent is not None
    # the coolant space: at the tool's tip, Z up the tool
    tip = ob(scene, TOOL).matrix_world @ gcode._rest_tip(ob(scene, TOOL))[0]
    assert (r.matrix_world.translation - tip).length < 1e-4
    assert (r.matrix_world.to_3x3() @ Vector((0, 0, 1))).z > 0.99
    # before M8: no jets; while it flows: jets and splash; after M9 and drying: nothing
    nj, nd = drawn(scene, 1)
    assert nj == 0
    mid = int((sp[0, 0] + sp[0, 1]) / 2)
    nj, nd = drawn(scene, mid)
    assert nj > 100 and nd > 20
    nj, nd = drawn(scene, frames)
    assert nj == 0
    # automatic hoses: 2, aimed at the tool
    hoses = bpy.data.objects.get(coolant.HOSES)
    assert hoses is not None and len(hoses.data.vertices) > 500
    # the wet sheen: the block and the table get wet, the head does not
    wet = {o.get(build.PROP_NAME, o.name) for o in coolant.wet_parts(scene)}
    assert STOCK in wet and TOOL not in wet and "SPINDLE" not in wet
    mats = {m for o in coolant.wet_parts(scene) for m in coolant._materials_of(o)}
    assert mats and all(coolant.is_patched(m) for m in mats)
    # the wet level: 0 before, near 1 at the end of the flood, drying after
    scene.frame_set(1)
    assert r[coolant.WET_PROP] < 0.01
    scene.frame_set(int(sp[0, 1]) - 1)
    assert r[coolant.WET_PROP] > 0.8


def test_frames_are_the_same_whatever_came_before(scene):
    scene.fresing.coolant.enabled = True
    _a, _b, frames = build_program(scene)
    sp = coolant.spans()
    f = int((sp[0, 0] + sp[0, 1]) / 2)

    def snap(before):
        scene.frame_set(before)
        scene.frame_set(f)
        jets = bpy.data.objects[coolant.JETS].data
        drops = bpy.data.objects[coolant.DROPS].data
        a = np.empty(len(jets.vertices) * 3)
        jets.vertices.foreach_get("co", a)
        b = np.empty(len(drops.vertices) * 3)
        drops.vertices.foreach_get("co", b)
        return a, b
    a10, b10 = snap(10)
    a90, b90 = snap(min(frames, f + 40))
    assert np.array_equal(a10, a90) and np.array_equal(b10, b90)
    assert len(b10) > 0


def test_switched_off_leaves_nothing(scene):
    scene.fresing.coolant.enabled = True
    build_program(scene)
    assert coolant.wet_parts(scene)
    scene.fresing.coolant.enabled = False
    assert coolant.root() is None and bpy.data.objects.get(coolant.HOSES) is None
    assert not coolant.wet_parts(scene)
    assert not any(m.get("fr_coolant_patch") for m in bpy.data.materials)
    assert not any(n.get("fr_coolant") for m in bpy.data.materials if m.node_tree for n in m.node_tree.nodes)


TWO_TOOLS = """%
(T1 D=10. CR=0. - flat end mill)
(T2 D=6. CR=0. - flat end mill)
G21 G90 G94 G17
T1 M6
S9000 M3
G0 X-30 Y-20 Z5
M8
G1 Z-2 F900
G1 X30 F2400
M9
G0 Z20
T2 M6
S9000 M3
G0 X0 Y0 Z5
M8
G1 Z-6 F300
G1 X20 F900
M9
G0 Z20
M5
M30
%
"""


def test_mist_and_air_from_m7_together(scene):
    scene.fresing.coolant.enabled = True
    scene.fresing.cnc.air_on_code = 7
    _a, b, frames = build_program(scene, POCKET.replace("M8", "M7"))
    sp = coolant.spans()
    assert len(sp) == 1 and sp[0, 2] == ccore.MIST
    ap = air.spans(scene)
    assert len(ap) == 1 and abs(ap[0, 0] - sp[0, 0]) < 1e-6 and abs(ap[0, 1] - sp[0, 1]) < 1e-6   # M9 stops both
    mid = int((sp[0, 0] + sp[0, 1]) / 2)
    nj, nd = drawn(scene, mid)
    assert nj == 0 and nd > 200                     # mist: drops, no solid stream
    # mist code 0: M7 is air only
    scene.fresing.coolant.mist_code = 0
    build_program(scene, POCKET.replace("M8", "M7"))
    assert len(coolant.spans()) == 0 and len(air.spans(scene)) == 1
    # the step decides: always flood, or off
    scene.fresing.coolant.mist_code = 7
    build_program(scene, POCKET.replace("M8\n", "").replace("M9\n", ""), gcode_coolant="FLOOD")
    assert len(coolant.spans()) == 1 and coolant.spans()[0, 2] == ccore.FLOOD
    _a, b, _f = build_program(scene, gcode_coolant="OFF")
    assert len(coolant.spans()) == 0 and gcode.info(scene, b)["coolant"] == "Coolant: off in this step"


def test_hoses_follow_the_tool_after_a_tool_change(scene):
    scene.fresing.coolant.enabled = True
    scene.fresing.cnc.tool_lengths = True
    _a, _b, frames = build_program(scene, TWO_TOOLS, fit=6.0)
    r = coolant.root()
    sched = gcode.schedule(scene)
    assert len(sched) >= 2, sched
    tools = np.array(r["fr_tools"]).reshape(-1, 3)
    assert len(tools) >= 2 and len({round(x, 5) for x in tools[:, 2]}) >= 2      # two radii: Ø10 and Ø6
    sp = coolant.spans()
    assert len(sp) == 2
    hoses = bpy.data.objects[coolant.HOSES]

    def tip_z(f):
        scene.frame_set(f)
        return coolant._tool_at(scene, r, f), hoses.data.get("fr_key")
    (t1, k1), (t2, k2) = tip_z(int(sp[0, 0]) + 2), tip_z(int(sp[1, 0]) + 2)
    assert t1[1] != t2[1]                       # the radius of the tool in the spindle
    if abs(t1[0] - t2[0]) > 1e-6:               # a tool of another length: the hoses bend again
        assert k1 != k2


def test_picked_nozzle_squirts_from_the_part(scene):
    s = scene.fresing.coolant
    s.enabled = True
    spindle = ob(scene, "SPINDLE")
    tip_world = Vector((-28 * MM, 0.0, 130 * MM))              # the spindle's bottom edge, on the left
    note = coolant.add_nozzle(scene, spindle, tip_world)
    assert "clicked" in note and s.source == "PARTS" and len(s.nozzles) == 1
    d = spindle.matrix_world.to_3x3() @ Vector(s.nozzles[0].dir)
    assert d.z < -0.5 and d.x > 0.3                            # down and in, at the tool
    assert coolant.problem(scene) == ""
    _a, _b, frames = build_program(scene)
    assert bpy.data.objects.get(coolant.HOSES) is None          # no app hoses with the model's own nozzles
    sp = coolant.spans()
    scene.frame_set(int((sp[0, 0] + sp[0, 1]) / 2))
    jets = bpy.data.objects[coolant.JETS]
    v = np.empty(len(jets.data.vertices) * 3)
    jets.data.vertices.foreach_get("co", v)
    w = np.array(jets.matrix_world) @ np.c_[v.reshape(-1, 3), np.ones(len(v) // 3)].T
    tip_now = spindle.matrix_world @ Vector(s.nozzles[0].tip)
    assert np.linalg.norm(w[:3].T - np.array(tip_now), axis=1).min() < 3 * MM      # the stream starts at the tip
    # aim and flip
    assert bpy.ops.fresing.cnc_coolant_aim(flip=True) == {"FINISHED"}
    assert (spindle.matrix_world.to_3x3() @ Vector(s.nozzles[0].dir)).z > 0.5
    assert bpy.ops.fresing.cnc_coolant_aim() == {"FINISHED"}
    assert (spindle.matrix_world.to_3x3() @ Vector(s.nozzles[0].dir)).z < -0.5
    # model update keeps the nozzle
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft", update_root=root.name) == {"FINISHED"}
    assert s.nozzles[0].obj is ob(scene, "SPINDLE") and s.nozzles[0].uid
    assert bpy.ops.fresing.cnc_coolant_remove() == {"FINISHED"}
    assert len(s.nozzles) == 0 and coolant.problem(scene).startswith("Pick the nozzles")


def test_save_and_open_again(scene, tmp_path):
    scene.fresing.coolant.enabled = True
    _a, _b, frames = build_program(scene)
    sp = coolant.spans()
    mid = int((sp[0, 0] + sp[0, 1]) / 2)
    before = drawn(scene, mid)
    path = str(tmp_path / "coolant.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert sc.fresing.coolant.enabled and len(coolant.spans()) == 1
    assert drawn(sc, 1)[0] == 0
    assert drawn(sc, mid) == before
    r = coolant.root()
    sc.frame_set(mid)
    assert r[coolant.WET_PROP] > 0.5
    assert all(coolant.is_patched(m) for o in coolant.wet_parts(sc) for m in coolant._materials_of(o))


def test_wet_sheen_goes_back_exactly(scene):
    blk = ob(scene, STOCK)
    mats = coolant._materials_of(blk)
    assert mats

    def shape(m):
        nt = m.node_tree
        return (len(nt.nodes), sorted((ln.from_node.name, ln.from_socket.identifier, ln.to_node.name,
                                       ln.to_socket.identifier) for ln in nt.links))
    old = [shape(m) for m in mats]
    scene.fresing.coolant.enabled = True
    build_program(scene)
    assert all(coolant.is_patched(m) for m in mats)
    assert [shape(m) for m in mats] != old
    scene.fresing.coolant.wet_parts = False
    assert [shape(m) for m in mats] == old and not coolant.wet_parts(scene)
    scene.fresing.coolant.wet_parts = True
    assert all(coolant.is_patched(m) for m in mats)
    animation.clear_keys(scene)
    assert len(coolant.spans()) == 0 and drawn(scene, 30) == (0, 0)


def test_wet_chips_fly_less_far(scene):
    click(ob(scene, TOOL))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(scene, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    _a, _b, frames = build_program(scene)
    machining.sample(scene)
    machining.settings(scene).chips = "REALISTIC"
    dry = chips.bake(scene, force=True)
    scene.fresing.coolant.enabled = True
    build_program(scene)
    machining.sample(scene)
    wet = chips.bake(scene, force=True)
    assert dry.stats["wet"] == 0 and wet.stats["wet"] > 0.8 * wet.stats["chips"]

    def spread(bk):
        p = bk.rest_p[np.isfinite(bk.rest_t) & (bk.rest_space == 0)]
        return float(np.median(np.linalg.norm(p[:, :2] - np.median(p[:, :2], axis=0), axis=1)))
    print(f"\nchips: median distance from the middle of the pile {spread(dry) * 1000:.1f} mm dry, "
          f"{spread(wet) * 1000:.1f} mm wet")
    assert spread(wet) < spread(dry)
    sp = coolant.spans()
    scene.frame_set(int(sp[0, 1]) - 2)
    ride = bpy.data.objects[chips.OBJ_RIDE]
    a = ride.data.attributes.get("fr_wet")
    assert a is not None and len(ride.data.vertices) and a.data[0].value > 0.8
