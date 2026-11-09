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


# ---------------------------------------------------------------------------
# task 0051: cut faces get their own look
# ---------------------------------------------------------------------------


def _block_group(sc, material_id, color=""):
    g = sc.fresing.groups[ob(sc, STOCK)[build.PROP_GROUP]]
    g.material = material_id
    if color:
        g.color = color
    return g


def _cut_faces(sc):
    wp = ob(sc, STOCK)
    me = wp.data
    n = int(me[machining.CUT_SLOT])
    mi = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("material_index", mi)
    return wp, n, mi


def test_cut_faces_get_their_own_look(scene):
    """A pocket in a mill-scale block shows bright machined steel inside; the outside keeps mill scale."""
    _block_group(scene, "steel_raw")
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    machining.refresh(scene, force=True)
    wp, n, mi = _cut_faces(scene)
    stock_slots = len(machining.settings(scene).stock_mesh.materials)
    assert n == stock_slots and len(wp.material_slots) == n + 1
    assert (mi == n).sum() > 20, "the slot's walls and floor are cut faces"
    assert (mi == 0).sum() > 6, "the block's own faces keep its look"
    mat = wp.material_slots[n].material
    assert mat.name.startswith(machining.CUT_MAT_PREFIX) and mat["fr_material"] == "steel_machined"
    assert wp.material_slots[n].link == "OBJECT"
    assert wp.material_slots[0].material["fr_material"] == "steel_raw"
    # the cut faces lie inside the slot: none on the block's outer faces
    me = wp.data
    me.calc_loop_triangles()
    centres = np.array([p.center[:] for p in me.polygons])
    cut = centres[mi == n]
    assert np.all(cut[:, 2] < 0.07 - 1e-6), "cut faces are below the top of the block"
    # 3 Looks: the block becomes aluminium plate -> the cut faces become machined aluminium at once
    _block_group(scene, "aluminium_sawn")
    assert wp.material_slots[n].material["fr_material"] == "aluminium_machined"
    # paint: the cut looks like the block
    _block_group(scene, "paint_satin")
    assert wp.material_slots[n].material is wp.material_slots[0].material
    # brass: the same metal, brighter (less rough), with milling marks
    _block_group(scene, "brass")
    m2 = wp.material_slots[n].material
    assert m2["fr_material"] == "brass" and "machined" in m2.name
    rough = next(nd for nd in m2.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
    assert rough.inputs["Roughness"].is_linked                 # marks drive the roughness


def test_cut_faces_same_and_pick(scene):
    s = machining.settings(scene)
    assert s.cut_look == "AUTO"                                   # the default (old projects too)
    _block_group(scene, "aluminium_anodized")
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    machining.refresh(scene, force=True)
    wp, n, _mi = _cut_faces(scene)
    s.cut_look = "SAME"
    assert wp.material_slots[n].material is wp.material_slots[0].material
    s.cut_look = "PICK"
    s.cut_material = "copper"
    assert wp.material_slots[n].material["fr_material"] == "copper"
    s.cut_material = "plastic_gloss"                              # takes the block group's colour
    _block_group(scene, "aluminium_anodized", "RAL 3020")
    assert wp.material_slots[n].material["fr_color"] == "RAL 3020"
    # Stop milling: the CAD mesh back with exactly its own slots
    stock = s.stock_mesh
    k = len(stock.materials)
    assert bpy.ops.fresing.mill_stop() == {"FINISHED"}
    assert wp.data is stock and len(stock.materials) == k and len(wp.material_slots) == k


def test_old_project_gets_the_cut_slot(scene):
    """A project milled before 0.2.40 has no cut slot on its milled mesh: the next frame adds it (Automatic)."""
    _block_group(scene, "steel_raw")
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    machining.refresh(scene, force=True)
    wp, n, _mi = _cut_faces(scene)
    me = wp.data
    while len(me.materials) > n:                                  # as an older version left it
        me.materials.pop()
    del me[machining.CUT_SLOT]
    machining.refresh(scene, force=True)
    wp, n2, mi = _cut_faces(scene)
    assert n2 == n and (mi == n).sum() > 20
    assert wp.material_slots[n].material["fr_material"] == "steel_machined"


def _mesh_tris(me):
    return len(me.polygons) if me is not None else 0


def test_decal_on_the_workpiece_survives_edits_while_milling(scene):
    """Bug hunt 0045 row 3: an edit of a decal on the milled block emptied it (0 triangles), also after Stop."""
    from fresing_render.blender import decals, faces
    wp = ob(scene, STOCK)
    me = wp.data
    top = max(range(len(me.polygons)), key=lambda i: me.polygons[i].normal.z)
    face = faces.face_of_polygon(me, top)
    centre = tuple(me.polygons[top].center)
    every = decals.add(wp, face, centre, (0, 0, 1), "TEXT", text="AlMg3")
    one = decals.add(wp, face, (centre[0] + 0.05, centre[1], centre[2]), (0, 0, 1), "TEXT", text="#1",
                     only_copy=True)
    for it in (every, one):
        assert _mesh_tris(it.mesh) > 0
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    s = machining.settings(scene)
    assert wp.data is s.cut_mesh and len(s.cut_mesh.fresing_decals) == 0     # no copy on the milled mesh
    assert decals.count(scene) == 2
    assert {it.key for it in decals.items_of(wp)} == {every.key, one.key}
    every = decals.find(every.key)
    one = decals.find(one.key)
    every.width = every.width * 1.5                     # an edit while milling is on
    one.width = one.width * 1.5
    assert _mesh_tris(every.mesh) > 0 and _mesh_tris(one.mesh) > 0
    assert decals.decal_objects_of(every) and decals.decal_objects_of(one)
    assert bpy.ops.fresing.mill_stop() == {"FINISHED"}
    every, one = decals.find(every.key), decals.find(one.key)
    assert wp.data is s.stock_mesh or wp.data.name == STOCK
    assert _mesh_tris(every.mesh) > 0 and _mesh_tris(one.mesh) > 0
    assert every.width == pytest.approx(decals.find(every.key).width)


def test_old_milled_mesh_with_copied_decals_is_mended(scene):
    """A project milled before 0.2.40 has the block's decals copied onto the milled mesh: they are dropped."""
    from fresing_render.blender import decals, faces
    wp = ob(scene, STOCK)
    me = wp.data
    top = max(range(len(me.polygons)), key=lambda i: me.polygons[i].normal.z)
    it = decals.add(wp, faces.face_of_polygon(me, top), tuple(me.polygons[top].center), (0, 0, 1), "TEXT",
                    text="AlMg3")
    key = it.key
    frames = anim(scene, SLOT)
    set_up(scene)
    s = machining.settings(scene)
    real = decals.find(key)
    old = s.cut_mesh.fresing_decals.add()             # as 0.2.39 left it: a copy sharing the decal mesh
    old.key = key
    decals.copy_settings(real, old)
    old.mesh = real.mesh
    old.mesh.clear_geometry()                         # the copy's edit emptied it
    scene.frame_set(frames)
    machining.refresh(scene, force=True)
    assert len(s.cut_mesh.fresing_decals) == 0
    assert _mesh_tris(decals.find(key).mesh) > 0


def test_frame_handler_on_the_render_thread(scene, monkeypatch):
    """Bug hunt 0045 row 13: a render in the window calls the frame handler on its own thread. Milling locks the
    interface during renders; with the lock taken off by hand the handler leaves the mesh alone there."""
    import threading
    scene.render.use_lock_interface = False
    frames = anim(scene, SLOT)
    set_up(scene)
    assert scene.render.use_lock_interface, "setting up milling locks the interface during renders"
    calls = []
    monkeypatch.setattr(machining, "refresh", lambda sc, *a, **k: calls.append(threading.current_thread().name))
    monkeypatch.setattr(machining, "_in_window", lambda: True)
    scene.frame_current = frames

    def on_thread():
        t = threading.Thread(target=machining._on_frame, args=(scene,), name="render")
        t.start()
        t.join()

    on_thread()
    assert calls == ["render"]                       # locked: the window does not draw meanwhile
    scene.render.use_lock_interface = False
    on_thread()
    assert calls == ["render"]                       # not locked: left alone off the main thread
    machining._on_frame(scene)
    assert calls[-1] == threading.main_thread().name   # the main thread always shows the frame


def test_one_frame_walks_the_objects_at_most_once(scene, monkeypatch):
    """Bug hunt 0045 row 20c: the frame code looked for its parts in the scene ~13 times and walked every object
    of the file 3 times a frame. Now one look per part and at most one walk per frame."""
    from fresing_render.blender import gcode
    frames = anim(scene, SLOT)
    set_up(scene)
    walks = []
    real = gcode.copies
    monkeypatch.setattr(gcode, "copies", lambda sc=None: walks.append(1) or real(sc))
    scene.frame_current = frames
    machining._on_frame(scene)
    assert len(walks) <= 1
    assert not machining._FRAME                      # nothing kept after the frame
    box, vol = removed(scene)
    assert vol == pytest.approx(SLOT_VOLUME, rel=0.003)


def test_queued_still_shows_the_cut_look(scene, tmp_path):
    """Task 0051: the render queue (a background Blender) shows the cut faces' look as the view does. The cut faces
    get a glowing material here, so they are the only white in the picture of a dark mill-scale block."""
    import time

    from PIL import Image

    from fresing_render.blender import queue
    s = scene.fresing
    _block_group(scene, "steel_raw")
    frames = anim(scene, [("Z", 0.0, 0.04, -25.0), ("X", 0.04, 0.04, 50.0)])
    set_up(scene)
    m = machining.settings(scene)
    m.cut_look = "PICK"
    m.cut_material = "emission_light"
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):
        logic.set_hidden(ob(scene, name), True)
    cam_data = bpy.data.cameras.new("Mill cam")
    cam = bpy.data.objects.new("Mill cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.0, -0.12, 0.30)
    cam.rotation_euler = (Vector((0.025, 0.0, 0.07)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam_data.lens = 50
    scene.camera = cam
    scene.frame_set(frames)
    wp, n, mi = _cut_faces(scene)
    assert (mi == n).sum() > 0
    s.use_gpu = False
    s.quality = "draft"
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = 320, 240, 100
    queue.add_job(scene, "STILL", quality="draft")
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "mill.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 600:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    img = np.asarray(Image.open(job.output).convert("RGB"), dtype=np.int16)
    white = (img.min(axis=2) > 235).mean()
    assert white > 0.001, white                      # the slot glows
    assert white < 0.1, white                        # and only the slot
