"""Task 0027: milling in Blender on the test mill (tools/make_test_mill.py, tests/data/test_mill.step).

The machine: the table (with the 200 x 200 x 40 mm stock, z 30..70 mm) slides along Y, the carriage
along X, the head along Z. The flat end mill Ø10 has its tip at (0, 0, 90) mm, the ball end mill Ø6 at
(120, 0, 90) mm. Every size below is worked out by hand from those numbers.
"""

import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, logic, machining  # noqa: E402
from fresing_render.core import machining as core  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _setup_axes(sc):
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    _setup_axes(sc)
    return sc


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def anim(sc, moves, name="Mill"):
    """moves: (joint, start s, duration s, to mm); constant speed. Built like 'Build & play'."""
    s = sc.fresing
    a = s.animations.add()
    a.name, a.tail = name, 0.0
    for j, start, dur, to in moves:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    return animation.bake(sc, a)["frames"]


def set_up(sc, bit="END MILL D10"):
    click(ob(sc, bit))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    machining.sample(sc)


def wp_solid(sc):
    me = ob(sc, STOCK).data
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    return core.solid_from_mesh(v.reshape(-1, 3), t.reshape(-1, 3))


def stock_box():
    return mf.Manifold.cube((0.2, 0.2, 0.04)).translate((-0.1, -0.1, 0.03))


def removed(sc):
    gone = stock_box() - wp_solid(sc)
    return np.round(np.array(gone.bounding_box()) / MM, 2), gone.volume() / MM ** 3


def mesh_arrays(sc):
    me = ob(sc, STOCK).data
    v = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", v)
    p = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", p)
    return v, p


SLOT = [("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)]     # 5 mm deep, 50 mm long
SLOT_VOLUME = (50 * 10 + math.pi * 25) * 5


# ---------------------------------------------------------------------------


def test_bits_are_recognised_from_their_shape(scene):
    click(ob(scene, "END MILL D10"))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(scene, "BALL MILL D6"))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    m = machining.settings(scene)
    flat, ball = m.bits
    assert flat.detected == "Flat end mill Ø10.0 mm, 40 mm long"
    assert ball.detected == "Ball end mill Ø6.0 mm, 30 mm long"
    # the tip is the lower end, the axis points up the shank
    assert (ob(scene, "END MILL D10").matrix_world @ Vector(flat.tip) - Vector((0, 0, 0.09))).length < 1e-6
    assert Vector(flat.axis).z == pytest.approx(1.0)
    assert machining.tool_of(ball).kind == "BALL" and machining.tool_of(ball).radius == pytest.approx(0.003)
    # a part can only have one role
    click(ob(scene, "END MILL D10"))
    assert bpy.ops.fresing.mill_set_workpiece() == {"CANCELLED"}
    # typed-in sizes win over the part's shape
    flat.shape = "BALL"
    flat.diameter = 0.008
    t = machining.tool_of(flat)
    assert t.kind == "BALL" and t.radius == pytest.approx(0.004)
    # tip at the other end and back
    bpy.context.scene.fresing.milling.bits_index = 1
    assert bpy.ops.fresing.mill_flip_bit() == {"FINISHED"}
    assert (ob(scene, "BALL MILL D6").matrix_world @ Vector(ball.tip)).z == pytest.approx(0.12, abs=1e-6)
    assert bpy.ops.fresing.mill_flip_bit() == {"FINISHED"}
    assert ball.detected == "Ball end mill Ø6.0 mm, 30 mm long"


def test_slot_from_an_animation(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    wp = ob(scene, STOCK)
    m = machining.settings(scene)
    assert wp.data is m.cut_mesh and m.stock_mesh.name == STOCK and wp.data.name == f"{STOCK} (milled)"
    scene.frame_set(1)
    assert removed(scene)[1] == pytest.approx(0.0, abs=1e-3)        # the bit is still above the block
    scene.frame_set(frames)
    box, vol = removed(scene)
    assert list(box) == pytest.approx([-5, -5, 65, 55, 5, 70], abs=0.02)
    assert vol == pytest.approx(SLOT_VOLUME, rel=0.003)
    # half way along X (frame 51: 1 s of plunge = 25 frames, then 1 s of X)
    scene.frame_set(51)
    box, _vol = removed(scene)
    assert box[3] == pytest.approx(30.0, abs=0.05)
    # the stock mesh itself is untouched (other copies, Stop milling)
    assert len(m.stock_mesh.polygons) == 12


def test_scrubbing_back_and_forth_gives_the_same_mesh(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    seen = {}
    for f in (40, frames, 60, 20, 40, 60, frames, 1, 40):
        scene.frame_set(f)
        arrays = mesh_arrays(scene)
        if f in seen:
            assert all(np.array_equal(a, b) for a, b in zip(seen[f], arrays)), f
        seen[f] = arrays
    machining._RUNTIME.clear()                 # nothing kept: straight to the frame
    scene.frame_set(1)
    scene.frame_set(60)
    assert all(np.array_equal(a, b) for a, b in zip(seen[60], mesh_arrays(scene)))


def test_the_workpiece_moves_with_the_table(scene):
    # the bit plunges 3 mm, then the table slides 40 mm along +Y: the slot runs along -Y in the block
    frames = anim(scene, [("Z", 0.0, 0.5, -23.0), ("Y", 0.5, 1.0, 40.0)])
    set_up(scene)
    scene.frame_set(frames)
    box, vol = removed(scene)
    assert list(box) == pytest.approx([-5, -45, 67, 5, 5, 70], abs=0.02)
    assert vol == pytest.approx((40 * 10 + math.pi * 25) * 3, rel=0.003)


def test_ball_mill_groove(scene):
    # carriage -100 mm puts the ball mill over x = 20; down 3 mm; the table moves 30 mm
    frames = anim(scene, [("X", 0.0, 0.5, -100.0), ("Z", 0.5, 0.5, -23.0), ("Y", 1.0, 1.0, 30.0)])
    set_up(scene, bit="BALL MILL D6")
    scene.frame_set(frames)
    box, _vol = removed(scene)
    assert list(box) == pytest.approx([17, -33, 67, 23, 3, 70], abs=0.03)


def test_finish_at_the_cad_part_never_cuts_below_it(scene):
    # plunge 15 mm (to z = 55) where the finished part has its pocket floor at z = 60, then 30 mm along X
    frames = anim(scene, [("Z", 0.0, 1.0, -35.0), ("X", 1.0, 1.0, 30.0)])
    set_up(scene)
    fin = ob(scene, "FINISHED PART")
    click(fin)
    assert bpy.ops.fresing.mill_set_finished() == {"FINISHED"}
    assert logic.is_hidden(fin)
    scene.frame_set(frames)
    box, _vol = removed(scene)
    assert list(box) == pytest.approx([-5, -5, 60, 35, 5, 70], abs=0.02)     # stops at the pocket floor
    fv = np.empty(len(fin.data.vertices) * 3, np.float32)
    fin.data.vertices.foreach_get("co", fv)
    fin.data.calc_loop_triangles()
    ft = np.empty(len(fin.data.loop_triangles) * 3, np.int32)
    fin.data.loop_triangles.foreach_get("vertices", ft)
    finished = core.solid_from_mesh(fv.reshape(-1, 3), ft.reshape(-1, 3))
    assert (finished - wp_solid(scene)).volume() / MM ** 3 < 1e-3
    # clearing it: the bit cuts down to 55 mm and the part is shown again
    assert bpy.ops.fresing.mill_clear_finished() == {"FINISHED"}
    assert not logic.is_hidden(fin)
    scene.frame_set(frames - 1)
    scene.frame_set(frames)
    assert removed(scene)[0][2] == pytest.approx(55.0, abs=0.02)


def test_motion_change_is_read_again(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    sig = machining.settings(scene).path_sig
    anim(scene, [("Z", 0.0, 1.0, -27.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)], name="Deeper")
    assert machining.signature(scene) != sig
    machining.update_if_needed(scene)          # what the 3D view does a moment after the change
    scene.frame_set(frames)
    assert removed(scene)[0][2] == pytest.approx(63.0, abs=0.02)


def test_saved_and_opened_again(scene, tmp_path):
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    before = removed(scene)
    path = str(tmp_path / "milled.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    m = machining.settings(sc)
    assert len(m.bits) == 1 and m.workpiece is not None and m.path_sig == machining.signature(sc)
    sc.frame_set(1)
    assert removed(sc)[1] == pytest.approx(0.0, abs=1e-3)
    sc.frame_set(frames)
    after = removed(sc)
    assert list(after[0]) == list(before[0]) and after[1] == pytest.approx(before[1], rel=1e-9)


def test_off_and_stop_give_the_cad_mesh_back(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    m = machining.settings(scene)
    stock = m.stock_mesh
    wp = ob(scene, STOCK)
    m.enabled = False
    assert wp.data is stock and not any(me.get(machining.CUT_TAG) for me in bpy.data.meshes)
    m.enabled = True
    scene.frame_set(frames)
    assert wp.data.get(machining.CUT_TAG) and removed(scene)[1] == pytest.approx(SLOT_VOLUME, rel=0.003)
    assert bpy.ops.fresing.mill_stop() == {"FINISHED"}
    assert wp.data is stock and len(m.bits) == 0 and m.workpiece is None
    assert not any(me.get(machining.CUT_TAG) for me in bpy.data.meshes)


def test_model_update_keeps_the_set_up(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    fin = ob(scene, "FINISHED PART")
    click(fin)
    bpy.ops.fresing.mill_set_finished()
    scene.frame_set(frames)
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft", update_root=root.name) == {"FINISHED"}
    m = machining.settings(scene)
    assert len(m.bits) == 1 and m.bits[0].obj is ob(scene, "END MILL D10")
    assert m.workpiece is ob(scene, STOCK) and m.finished is ob(scene, "FINISHED PART")
    assert logic.is_hidden(m.finished)
    # the animation keys are cleared by a model update: build it again, and the cut follows
    a = scene.fresing.animations["Mill"]
    frames = animation.bake(scene, a)["frames"]
    machining.update_if_needed(scene)
    scene.frame_set(frames)
    box, vol = removed(scene)
    # the finished part's pocket ends at x = 50: the slot stops there
    assert list(box) == pytest.approx([-5, -5, 65, 50, 5, 70], abs=0.02)
    assert len([me for me in bpy.data.meshes if me.get(machining.CUT_TAG)]) == 1


def test_queue_reads_the_motion_before_rendering(scene):
    """The render queue opens the saved project and bakes the animation; prepare() reads the path."""
    frames = anim(scene, SLOT)
    set_up(scene)
    m = machining.settings(scene)
    m.path_sig = ""                            # as if the motion changed after the last look in the view
    machining._RUNTIME.clear()
    machining.prepare(scene)
    assert m.path_sig == machining.signature(scene)
    scene.frame_set(frames)
    assert removed(scene)[1] == pytest.approx(SLOT_VOLUME, rel=0.003)


def test_milling_panel_draws(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_machining
    errors = []

    def draw_all():
        for cls in ui_machining.CLASSES:
            if issubclass(cls, bpy.types.Panel):
                fake = type("P", (), {"layout": FakeLayout(errors)})()
                cls.draw(fake, bpy.context)
                for extra in ("draw_header", "draw_header_preset"):
                    getattr(cls, extra)(fake, bpy.context)
        m = machining.settings(bpy.context.scene)
        for item in m.bits:
            ui_machining.FRESING_UL_mill_bits.draw_item(None, bpy.context, FakeLayout(errors), m, item, 0, m, "", 0)

    draw_all()                                  # nothing set up yet
    anim(scene, SLOT)
    set_up(scene)
    for shape in ("AUTO", "FLAT", "BALL", "BULL", "VEE", "DRILL"):
        machining.settings(scene).bits[0].shape = shape
        draw_all()
    machining.settings(scene).enabled = False
    draw_all()
    assert not errors, errors


def test_milling_tooltips_are_written():
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import tooltip_report as t
    fresing_render.unregister()                # the check registers the extension itself
    try:
        items = [i for i in t.collect() if i.panel == "Milling"]
    finally:
        fresing_render.register()
    assert len(items) >= 12
    bad = [(i.label or i.ident, i.verdict, i.tooltip) for i in items if i.verdict != "ok"]
    assert not bad, bad


def test_queue_render_shows_the_cut(scene, tmp_path):
    """The real render queue (a background Blender): the last frame shows the slot, the first does not."""
    import time

    from PIL import Image

    from fresing_render.blender import queue
    s = scene.fresing
    set_up(scene)                              # picked while the bit can still be clicked
    # only the block and the table are in the picture: what moves is hidden (it still moves and cuts),
    # and the finished part (in the same place as the stock) too
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):
        logic.set_hidden(ob(scene, name), True)
    cam_data = bpy.data.cameras.new("Mill cam")
    cam = bpy.data.objects.new("Mill cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.12, -0.22, 0.24)
    cam.rotation_euler = (Vector((0.025, 0.0, 0.07)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 50
    scene.camera = cam
    # built after hiding and the camera: 'Build' remembers how things looked and the queue builds again
    anim(scene, [("Z", 0.0, 0.04, -25.0), ("X", 0.04, 0.04, 50.0)])         # 3 frames: above, plunged, slot
    s.use_gpu = False
    a = s.animations["Mill"]
    a.out_resolution, a.quality, a.video = "preview", "draft", "PNG"
    queue.add_job(scene, "ANIMATION", animation="Mill")
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "mill.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 600:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    frames = sorted(os.listdir(job.output))
    assert frames == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    first = np.asarray(Image.open(os.path.join(job.output, frames[0])).convert("RGB"), dtype=np.int16)
    last = np.asarray(Image.open(os.path.join(job.output, frames[-1])).convert("RGB"), dtype=np.int16)
    changed = np.abs(first - last).max(axis=2) > 25
    share = changed.mean()
    assert 0.002 < share < 0.2, share                    # the slot, and only the slot, changed
    ys, xs = np.nonzero(changed)
    assert np.ptp(xs) > 3 * np.ptp(ys) / 2, (np.ptp(xs), np.ptp(ys))   # a long slot, seen from the side
