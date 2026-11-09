"""Task 0028: chips in Blender on the test mill (tools/make_test_mill.py, tests/data/test_mill.step).

The machine: the table (with the 200 x 200 x 40 mm stock, z 30..70 mm) slides along Y, the carriage along X, the
head along Z; the bed below the table has its top at z = 0 and its bottom (the lowest point of the machine) at
-60 mm. The flat end mill Ø10 has its tip at (0, 0, 90) mm.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, chips, joints, logic, machining  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"
SLOT = [("Z", 0.0, 1.0, -25.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)]     # 5 mm deep, 50 mm long


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture()
def scene(tmp_path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    machining._RUNTIME.clear()
    chips.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft") == {"FINISHED"}
    for name, asm, d in (("Y", "TABLE.ASM", (0, 1, 0)), ("X", "X.ASM", (1, 0, 0)), ("Z", "Z.ASM", (0, 0, 1))):
        o = ob(sc, asm)
        joints.create(sc, "SLIDE", [o], o.matrix_world.translation, Vector(d), name=name)
    return sc


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(o):
    for x in bpy.context.selected_objects:
        x.select_set(False)
    o.select_set(True)
    bpy.context.view_layer.objects.active = o


def anim(sc, moves, name="Mill", tail=0.5):
    s = sc.fresing
    a = s.animations.get(name) or s.animations.add()
    a.name, a.tail = name, tail
    a.blocks.clear()
    for j, start, dur, to in moves:
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j, start, dur, "LINEAR"
        b.use_from, b.to_dist = True, to * MM
    return animation.bake(sc, a)["frames"]


def set_up(sc, amount="FEW"):
    click(ob(sc, "END MILL D10"))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
    machining.sample(sc)
    machining.settings(sc).chips = amount


def points(name):
    o = bpy.data.objects.get(name)
    if o is None:
        return np.zeros((0, 3))
    v = np.empty(len(o.data.vertices) * 3, np.float32)
    o.data.vertices.foreach_get("co", v)
    return v.reshape(-1, 3)


def counts():
    return len(points(chips.OBJ_RIDE)), len(points(chips.OBJ_WORLD))


def first_cut_frame(bk):
    return int(np.nonzero(bk.volume > 0)[0][0]) + bk.f0


# ---------------------------------------------------------------------------


def test_chips_appear_while_cutting_and_land_on_the_machine(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    m = machining.settings(scene)
    bk = chips.runtime(scene)["bake"]
    assert bk.count == pytest.approx(bk.stats["removed_mm3"] * 0.45 * 0.12, abs=1)    # aluminium curls, Few
    first = first_cut_frame(bk)
    assert 18 <= first <= 23                         # the bit reaches the top (20 mm down) after 4/5 of the plunge
    for f in (1, first - 1):
        scene.frame_set(f)
        assert counts() == (0, 0), f
    scene.frame_set(first + 3)
    assert sum(counts()) > 0
    scene.frame_set(frames)
    ride, world = points(chips.OBJ_RIDE), points(chips.OBJ_WORLD)
    assert len(ride) > 5 and len(world) > 5
    # the riding chips follow the workpiece; those that fell off lie on the bed (top 0) or the floor (-60 mm)
    o = bpy.data.objects[chips.OBJ_RIDE]
    assert o.constraints[0].type == "COPY_TRANSFORMS" and o.constraints[0].target is ob(scene, STOCK)
    z = np.round(world[:, 2] / MM)
    assert set(np.unique(z)) <= {0.0, -60.0} and (z == 0.0).any()
    # every point is a chip in the picture
    dg = bpy.context.evaluated_depsgraph_get()
    n = sum(1 for i in dg.object_instances if i.is_instance and i.parent and
            i.parent.name in (chips.OBJ_RIDE, chips.OBJ_WORLD))
    assert n == len(ride) + len(world)
    assert chips.family(scene) == ("ALU", "default")
    assert "chips worked out" in chips.status(scene)
    assert m.chips == "FEW"


def test_riding_chips_go_along_with_the_table(scene):
    frames = anim(scene, SLOT + [("Y", 3.5, 1.0, 60.0)])
    set_up(scene)
    scene.frame_set(frames)
    o = bpy.data.objects[chips.OBJ_RIDE]
    assert (o.matrix_world.translation - Vector((0, 0.06, 0))).length < 1e-6
    # the chips on the table lie within the table (400 x 300, moved 60 mm) once in the world
    w = np.array([o.matrix_world @ Vector(p) for p in points(chips.OBJ_RIDE)])
    on_table = np.abs(w[:, 2] - 0.03) < 2 * MM
    assert on_table.any()
    assert (np.abs(w[on_table, 0]) <= 0.2 + 1e-6).all() and (np.abs(w[on_table, 1] - 0.06) <= 0.15 + 1e-6).all()


def test_the_same_chips_every_time_also_after_opening(scene, tmp_path):
    frames = anim(scene, SLOT)
    set_up(scene, "REALISTIC")
    scene.frame_set(frames - 8)
    scene.frame_set(frames)
    before = (points(chips.OBJ_RIDE).copy(), points(chips.OBJ_WORLD).copy())
    assert len(before[0]) + len(before[1]) > 100
    chips.forget()                                  # worked out again from scratch
    scene.frame_set(1)
    scene.frame_set(frames)
    again = (points(chips.OBJ_RIDE), points(chips.OBJ_WORLD))
    assert all(np.array_equal(a, b) for a, b in zip(before, again))
    path = str(tmp_path / "chips.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert machining.settings(sc).chips == "REALISTIC"
    sc.frame_set(1)
    assert counts() == (0, 0)
    sc.frame_set(frames)
    opened = (points(chips.OBJ_RIDE), points(chips.OBJ_WORLD))
    assert all(np.array_equal(a, b) for a, b in zip(before, opened))


def test_the_material_comes_from_the_workpiece(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    s = scene.fresing
    group = ob(scene, STOCK).get(build.PROP_GROUP)
    s.groups[group].material = "pom_white"
    machining.settings(scene).chips = "FEW"         # (the look changes the material, the setting shows again)
    chips.show(scene, frames)
    assert chips.family(scene) == ("PLASTIC", "material")
    shapes = bpy.data.collections[chips.SHAPES_COLLECTION].objects
    assert {o.data.materials[0].name for o in shapes} == {"FR chips PLASTIC"}
    assert all(o.name.startswith("FR chip ") for o in shapes)
    machining.settings(scene).chip_material = "BRASS"
    scene.frame_set(frames - 1)
    scene.frame_set(frames)
    assert chips.family(scene) == ("BRASS", "chosen")
    assert {o.data.materials[0].name for o in bpy.data.collections[chips.SHAPES_COLLECTION].objects} == \
        {"FR chips BRASS"}
    bk = chips.runtime(scene)["bake"]
    assert {bk.shapes[s][0].shape for s in bk.slot} == {"CRUMB"}
    # coolant mist: drops with a see-through material of their own
    machining.settings(scene).chip_mist = True
    scene.frame_set(30)
    bk = chips.runtime(scene)["bake"]
    assert bk.stats["mist"] > 0
    assert "FR chips MIST" in {o.data.materials[0].name for o in bpy.data.collections[chips.SHAPES_COLLECTION].objects}


def test_new_materials_throw_the_right_chips():
    """Task 0051: the 0046 looks and the new raw stock have a chip family."""
    from fresing_render.core import chips as cc
    for key, fam in (("steel_ground", "STEEL"), ("steel_turned", "STEEL"), ("chrome_rod", "STEEL"),
                     ("cast_iron_painted", "CAST_IRON"), ("aluminium_sawn", "ALU"), ("pom_black", "PLASTIC")):
        assert cc.family_for(["BLOCK"], key) == (fam, "material"), key


def test_a_frame_change_does_not_rebuild_every_object(scene):
    """Bug hunt 0045 row 15: chips assigned the node group's collection at every frame, and each assignment
    rebuilt the whole dependency graph (all objects updated: 168 ms a frame with 3,000 objects)."""
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames - 2)
    seen = []

    def count(_scene, depsgraph):
        seen.append(sum(1 for u in depsgraph.updates if isinstance(u.id, bpy.types.Object)))

    bpy.app.handlers.depsgraph_update_post.append(count)
    try:
        bpy.context.view_layer.update()
        seen.clear()
        info = next(n for n in bpy.data.node_groups[chips.NODE_GROUP].nodes
                    if n.bl_idname == "GeometryNodeCollectionInfo")
        before = info.inputs["Collection"].default_value
        chips.show(scene, frames - 1)
        chips.show(scene, frames)
        bpy.context.view_layer.update()
    finally:
        bpy.app.handlers.depsgraph_update_post.remove(count)
    assert info.inputs["Collection"].default_value == before
    n_obj = len(scene.objects)
    assert seen and max(seen) < n_obj / 2, (seen, n_obj)


def test_a_deeper_cut_makes_more_chips(scene):
    frames = anim(scene, SLOT)
    set_up(scene, "REALISTIC")
    scene.frame_set(frames)
    n5 = chips.runtime(scene)["bake"].count
    anim(scene, [("Z", 0.0, 1.0, -30.0), ("X", 1.0, 2.0, 50.0), ("Z", 3.0, 0.5, 0.0)])     # 10 mm deep
    machining.update_if_needed(scene)               # what the 3D view does a moment after the change
    scene.frame_set(frames)
    n10 = chips.runtime(scene)["bake"].count
    assert n10 / n5 == pytest.approx(2.0, rel=0.03)


def test_clear_chips_and_stop_milling_remove_everything(scene):
    frames = anim(scene, SLOT)
    set_up(scene)
    scene.frame_set(frames)
    assert bpy.data.objects.get(chips.OBJ_RIDE) is not None and bpy.data.node_groups.get(chips.NODE_GROUP)
    assert bpy.ops.fresing.chips_clear() == {"FINISHED"}
    m = machining.settings(scene)
    assert m.chips == "NONE"
    for name in (chips.OBJ_RIDE, chips.OBJ_WORLD):
        assert bpy.data.objects.get(name) is None
    assert bpy.data.collections.get(chips.SHAPES_COLLECTION) is None
    assert bpy.data.collections.get(chips.COLLECTION) is None
    assert bpy.data.node_groups.get(chips.NODE_GROUP) is None
    assert not [mt for mt in bpy.data.materials if mt.name.startswith(chips.MAT_PREFIX)]
    assert bpy.ops.fresing.chips_clear.poll() is False
    # milling off: no chips; on again: back
    m.chips = "FEW"
    scene.frame_set(frames)
    assert sum(counts()) > 0
    m.enabled = False
    assert counts() == (0, 0)
    m.enabled = True
    scene.frame_set(frames - 1)
    scene.frame_set(frames)
    assert sum(counts()) > 0
    assert bpy.ops.fresing.mill_stop() == {"FINISHED"}
    assert bpy.data.objects.get(chips.OBJ_RIDE) is None and bpy.data.objects.get(chips.OBJ_WORLD) is None


def test_chips_panel_draws(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_machining
    errors = []

    def draw():
        cls = ui_machining.FRESING_PT_milling_chips
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        if cls.poll(bpy.context):
            for fn in (cls.draw, cls.draw_header, cls.draw_header_preset):
                fn(fake, bpy.context)
        return cls.poll(bpy.context)

    assert not draw()                               # no milling set-up: no chips panel
    anim(scene, SLOT)
    set_up(scene, "NONE")
    for amount in ("NONE", "FEW", "REALISTIC"):
        machining.settings(scene).chips = amount
        assert draw()
    machining.settings(scene).enabled = False
    draw()
    assert not errors, errors


def test_chips_tooltips_are_written():
    import sys
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import tooltip_report as t
    fresing_render.unregister()
    try:
        items = [i for i in t.collect() if i.panel == "Chips"]
    finally:
        fresing_render.register()
    assert len(items) >= 5
    bad = [(i.label or i.ident, i.verdict, i.tooltip) for i in items if i.verdict != "ok"]
    assert not bad, bad


def test_queue_render_shows_chips(scene, tmp_path):
    """The real render queue (a background Blender) works the chips out by itself and renders them: seen from
    straight above, a patch of the block beside the slot (the slot itself is not in the picture) is bare in the
    first frame and has chips in the last."""
    import time

    from PIL import Image

    from fresing_render.blender import queue
    s = scene.fresing
    set_up(scene, "NONE")                              # picked while the bit can still be clicked
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):     # what moves still moves and cuts, it is only not seen
        logic.set_hidden(ob(scene, name), True)
    moves = [("Z", 0.0, 0.04, -25.0), ("X", 0.04, 0.08, 50.0)]
    frames = anim(scene, moves, tail=0.04)
    machining.sample(scene)
    machining.settings(scene).chips = "REALISTIC"
    scene.frame_set(frames)
    a = chips.runtime(scene)["bake"].at(frames)[0]
    pos = a["pos"]
    assert len(pos) > 50

    def inside(cx, cy):
        return int(((np.abs(pos[:, 0] - cx) < 0.022) & (np.abs(pos[:, 1] - cy) < 0.022)).sum())
    # a patch 50 mm wide that keeps clear of the slot (x -5..55, y -5..5 mm) and has the most chips
    best = max(((cx, cy) for cx in np.arange(-0.06, 0.11, 0.01) for cy in (-0.07, -0.05, -0.032, 0.032, 0.05, 0.07)),
               key=lambda c: inside(*c))
    assert inside(*best) >= 5, inside(*best)
    animation.clear_keys(scene)                         # back to how it was before building (also the camera)
    cam_data = bpy.data.cameras.new("Top cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 0.05
    cam = bpy.data.objects.new("Top cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (float(best[0]), float(best[1]), 0.3)
    scene.camera = cam
    frames = anim(scene, moves, tail=0.04)            # built again with this camera
    s.use_gpu = False
    an = s.animations["Mill"]
    an.out_format, an.out_resolution, an.quality, an.video = "square", "preview", "draft", "PNG"
    queue.add_job(scene, "ANIMATION", animation="Mill")
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "chips.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 600:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    names = sorted(os.listdir(job.output))
    assert len(names) == frames
    first = np.asarray(Image.open(os.path.join(job.output, names[0])).convert("RGB"), dtype=np.int16)
    last = np.asarray(Image.open(os.path.join(job.output, names[-1])).convert("RGB"), dtype=np.int16)
    # the same noise in both frames (fixed seed): what differs are the chips
    changed = (np.abs(first - last).max(axis=2) > 30).mean()
    assert changed > 0.002, changed
