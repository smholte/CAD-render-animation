"""Task 0029: the app makes the toolpath - in Blender, on tools/make_test_toolpath.py.

The block (STOCK 120x80x40, x -60..60, y -40..40, z 30..70 mm) becomes the FINISHED PART: base top z = 55, a boss with
rounded top edges (top 65), a pocket (floor 47), a dome (top 65), a mushroom whose cap hangs over (the undercut) and a
through hole. T1 flat Ø10 roughs, T2 ball Ø10 finishes. The important check: the block cut by the made program (with
'finish at the CAD part' off, so nothing hides a gouge) is never inside the part by more than 0.01 mm, measured with
rays from outside; and where the ball reaches, it leaves little.
"""

import json
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, gcode, machining, toolpath  # noqa: E402
from fresing_render.core import toolpath as tp  # noqa: E402

HERE = os.path.dirname(__file__)
MODEL = os.path.join(HERE, "data", "test_toolpath.step")
GANTRY = os.path.join(HERE, "data", "test_gantry.step")
MM = 0.001


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    d = tmp_path_factory.mktemp("toolpath")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    gcode._CACHE.clear()
    gcode._INFO.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(d)
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    toolpath.set_up_test_model(sc)
    bpy.ops.wm.save_as_mainfile(filepath=str(d / "part.blend"))
    sc = bpy.context.scene
    assert toolpath.problem(sc) == ""
    assert bpy.ops.fresing.toolpath_make() == {"FINISHED"}
    return d


def test_step_and_program(made):
    sc = bpy.context.scene
    a, b = toolpath.step(sc)
    assert b is not None and b.kind == "GCODE" and b.get(toolpath.STEP_TAG)
    assert b.gcode_file == "//part toolpath.ngc"                    # next to the project
    path = os.path.join(str(made), "part toolpath.ngc")
    assert os.path.isfile(path)
    assert b.gcode_speed == "FIT" and b.duration == pytest.approx(30.0, abs=0.01)
    info = gcode.info(sc, b)
    assert info["problems"] == [] and info["missing"] == [] and info["tools"] == [1, 2]
    r = toolpath.result(sc)
    assert r["moves"] > 1000 and r["machine_s"] > 600 and r["video_s"] == pytest.approx(30.0, abs=0.01)
    assert "Undercut" in r["undercut"]
    assert any("Roughing" in line for line in toolpath.result_lines(sc))
    assert "Undercut" in sc.fresing.last_message


def test_again_replaces_its_step(made):
    sc = bpy.context.scene
    _a, b = toolpath.step(sc)
    path = gcode.file_path(b.gcode_file, b.get(gcode.PROGRAM_ABS, ""))
    before = open(path).read()
    assert toolpath.edited_by_hand(sc) == ""
    t = toolpath.settings(sc)
    t.angle = 1.5707963                                             # lines along Y
    assert bpy.ops.fresing.toolpath_make() == {"FINISHED"}
    steps = [x for a in sc.fresing.animations for x in a.blocks if x.kind == "GCODE"]
    assert len(steps) == 1 and steps[0].get(toolpath.STEP_TAG)
    after = open(path).read()
    assert after != before
    with open(path, "a") as fh:                                     # an edit by hand is noticed (the button asks)
        fh.write("(changed by hand)\n")
    assert toolpath.edited_by_hand(sc) == os.path.normpath(path)
    t.angle = 0.0
    assert bpy.ops.fresing.toolpath_make() == {"FINISHED"}
    assert toolpath.edited_by_hand(sc) == ""
    assert open(path).read() == before                              # the same settings give the same program


def _rays(bvh, origins, d):
    out = np.full(len(origins), np.inf)
    for k, o in enumerate(origins):
        hit = bvh.ray_cast(Vector(o), Vector(d))
        if hit[0] is not None:
            out[k] = hit[3]
    return out


def _bvh(me, matrix):
    m = np.array(matrix)
    v = np.array([tuple(x.co) for x in me.vertices]) @ m[:3, :3].T + m[:3, 3]
    return BVHTree.FromPolygons([tuple(p) for p in v], [tuple(p.vertices) for p in me.polygons]), v


def test_cut_never_into_the_part(made):
    """Cut to the end with 'finish at the CAD part' off; everything in the block's own space, mm."""
    sc = bpy.context.scene
    m = machining.settings(sc)
    wp, fin = m.workpiece, m.finished
    rel = machining._cad_world(wp).inverted() @ machining._cad_world(fin)
    machining.set_finished(sc, None, update=False)
    a, _b = toolpath.step(sc)
    r = animation.bake(sc, a)
    assert not r["warnings"], r["warnings"]
    machining.update_if_needed(sc)                 # (a script reads the path itself, CLAUDE.md section 8)
    sc.frame_set(sc.frame_end)
    assert machining.refresh(sc, force=True), machining.status(sc)
    mm = np.diag([1000.0, 1000.0, 1000.0, 1.0])
    cut, _v = _bvh(wp.data, mm)
    part, pv = _bvh(fin.data, mm @ np.array(rel))
    tris = []
    me = fin.data
    me.calc_loop_triangles()
    for lt in me.loop_triangles:
        tris.append([pv[i] for i in lt.vertices])
    tris = np.array(tris)

    # from above, on a grid
    xs, ys = np.arange(-58, 58.01, 0.5), np.arange(-38, 38.01, 0.5)
    X, Y = np.meshgrid(xs, ys)
    top = np.stack([X.ravel(), Y.ravel(), np.full(X.size, 100.0)], axis=1)
    d_part = _rays(part, top, (0, 0, -1)).reshape(X.shape)
    d_cut = _rays(cut, top, (0, 0, -1)).reshape(X.shape)
    zp = 100.0 - d_part
    gy, gx = np.gradient(np.where(np.isfinite(zp), zp, 0.0), 0.5)
    gentle = np.isfinite(zp) & (np.hypot(gx, gy) < np.tan(np.radians(30)))
    for k in range(2):                            # not next to a wall either
        gentle[1:-1, 1:-1] &= gentle[:-2, 1:-1] & gentle[2:, 1:-1] & gentle[1:-1, :-2] & gentle[1:-1, 2:]
    deep = d_cut - d_part                         # > 0: the cut went below the part's top
    assert gentle.sum() > 20000
    worst = float(deep[gentle].max())
    assert worst <= 0.01, f"the cut goes {worst:.4f} mm into the part from above"

    # into the walls, sideways: pocket (x 12..48, y -32..-10, floor 47), boss (x -52..-28, y -32..-8), cap (x 17..39)
    side = []
    for z in (49.0, 51.0, 53.0):
        for y in np.arange(-30, -11, 1.0):
            side += [((30.0, y, z), (-1, 0, 0)), ((30.0, y, z), (1, 0, 0))]
        for x in np.arange(14, 47, 1.0):
            side += [((x, -21.0, z), (0, -1, 0)), ((x, -21.0, z), (0, 1, 0))]
    for z in (57.0, 59.0, 61.0):
        for y in np.arange(-30, -9, 1.0):
            side += [((-20.0, y, z), (-1, 0, 0)), ((-58.0, y, z), (1, 0, 0))]
    for z in (60.5, 62.0, 63.5):
        for y in np.arange(15, 30, 1.0):
            side += [((10.0, y, z), (1, 0, 0)), ((46.0, y, z), (-1, 0, 0))]
    worst_side = 0.0
    for o, dirn in side:
        dp = _rays(part, [o], dirn)[0]
        dc = _rays(cut, [o], dirn)[0]
        if np.isfinite(dp):
            worst_side = max(worst_side, dc - dp)
    assert worst_side <= 0.01, f"the cut goes {worst_side:.4f} mm into a wall"

    # stock left where the ball reaches straight down (its tip touches the part right under it)
    ball = tp.DropCutter(tp.Mesh(tris), tp.Shape(5.0, 5.0))
    pts = np.stack([X[gentle], Y[gentle]], axis=1)
    reach = np.abs(ball.z(pts) - zp[gentle]) < 0.02
    left = -deep[gentle][reach]
    assert reach.sum() > 10000
    assert float(left.max()) <= 0.12, f"up to {left.max():.3f} mm left where the ball reaches"
    assert float(np.median(left)) <= 0.03

    # the undercut's stock is still under the cap, the hole is still full
    def inside(p, dirn=(-1, 0, 0)):
        hit = cut.ray_cast(Vector(p), Vector(dirn))
        return hit[0] is not None and hit[1].dot(Vector(dirn)) > 0
    assert inside((20.0, 22.0, 57.5))
    assert inside((52.0, 30.0, 50.0), (0, 0, 1))
    print(f"cut: {worst:.4f} mm into the part from above, {worst_side:.4f} mm into walls; up to {left.max():.3f} mm "
          f"left where the ball reaches (median {np.median(left):.4f})")


def test_scripts_off(made):
    """No Python in what the toolpath adds: every driver an average or a simple expression."""
    for o in bpy.data.objects:
        ad = o.animation_data
        for d in (ad.drivers if ad else []):
            assert d.driver.type != "SCRIPTED" or d.driver.is_simple_expression, (o.name, d.driver.expression)


def test_save_and_reopen(made):
    sc = bpy.context.scene
    r = toolpath.result(sc)
    t = toolpath.settings(sc)
    t.scallop = 0.00002
    p = str(made / "again.blend")
    bpy.ops.wm.save_as_mainfile(filepath=p)
    bpy.ops.wm.open_mainfile(filepath=p)
    sc = bpy.context.scene
    t = toolpath.settings(sc)
    assert t.rough_tool == "1" and t.finish_tool == "2" and t.scallop == pytest.approx(0.00002)
    assert toolpath.result(sc) == r
    _a, b = toolpath.step(sc)
    assert b is not None and b.get(toolpath.STEP_TAG)
    assert gcode.info(sc, b)["problems"] == []
    assert json.loads(t.result)["moves"] == r["moves"]


def test_keys_close_together_are_kept():
    """Build writes keys less than 0.01 frame apart (a fast program's short moves) as they are: Blender's
    FCurve.update() merged them, and the tool cut straight across where the program lifted over the part."""
    from bpy_extras import anim_utils
    o = bpy.data.objects.new("keys", None)
    o["v"] = 0.0
    act = bpy.data.actions.new("keys")
    o.animation_data_create().action = act
    slot = act.slots.new(id_type="OBJECT", name="keys")
    o.animation_data.action_slot = slot
    cb = anim_utils.action_ensure_channelbag_for_slot(act, slot)
    animation._write(cb, '["v"]', 0, [(1.0, 0.0, "LINEAR", "AUTO"), (1.004, 5.0, "LINEAR", "AUTO"),
                                     (1.009, 0.0, "LINEAR", "AUTO"), (2.0, 1.0, "CONSTANT", "AUTO")])
    fc = cb.fcurves.find('["v"]')
    assert len(fc.keyframe_points) == 4
    assert fc.evaluate(1.004) == pytest.approx(5.0, abs=1e-3)


def test_a_project_without_it_is_unchanged():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    assert bpy.ops.fresing.import_step(filepath=GANTRY, quality="draft") == {"FINISHED"}
    assert toolpath.step(sc) == (None, None)
    assert toolpath.result(sc) == {} and toolpath.result_lines(sc) == []
    assert toolpath.problem(sc)                     # says what to set up first
    assert bpy.ops.fresing.toolpath_make() == {"CANCELLED"}
    assert len(sc.fresing.animations) == 0
