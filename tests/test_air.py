"""Task 0039: air blast on the test mill (tests/data/test_mill.step) with a G-code program.

The block (200 x 200 x 40 mm, top at z = 70 mm) sits on the table that slides along Y; the head (spindle
Ø60 mm, bottom at z = 130 mm, the Ø10 end mill's tip at z = 90 mm) moves along X and Z. The program cuts a
pocket 60 x 40 mm, 4 mm deep, in the middle of the block, with air on (M7) while it cuts and off (M9) before
it goes up.
"""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
mf = pytest.importorskip("manifold3d")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import air, animation, build, chips, gcode, joints, machining  # noqa: E402
from fresing_render.core import gcode as gcore  # noqa: E402

HERE = os.path.dirname(__file__)
MILL = os.path.join(HERE, "data", "test_mill.step")
MM = 0.001
STOCK = "STOCK 200x200x40"
TOOL = "END MILL D10"
TOP = 0.07

POCKET = """%
(POCKET WITH AIR)
(T1 D=10. CR=0. - flat end mill)
G21 G90 G94 G17
S9000 M3
G0 X-30 Y-20 Z5
M7
G1 Z-4 F900
G1 X30 F2400
G1 Y-12
G1 X-30
G1 Y-4
G1 X30
G1 Y4
G1 X-30
G1 Y12
G1 X30
G1 Y20
G1 X-30
M9
G0 Z20
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
    click(ob(sc, TOOL))
    assert bpy.ops.fresing.mill_add_bit() == {"FINISHED"}
    click(ob(sc, STOCK))
    assert bpy.ops.fresing.mill_set_workpiece() == {"FINISHED"}
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
    machining.sample(sc)
    return a, b, r["frames"]


def on_block(bk, frame) -> int:
    """Chips lying on (or just over) the block's top at a frame (riding space: the world as at the first frame)."""
    p = bk.at(frame)[0]["pos"]
    s = machining.settings(bpy.context.scene)
    me = s.stock_mesh
    v = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", v)
    m0 = np.array(s["fr_wp_m"][:16]).reshape(4, 4)
    w = v.reshape(-1, 3) @ m0[:3, :3].T + m0[:3, 3]
    lo, hi = w.min(axis=0), w.max(axis=0)
    inside = (p[:, 0] > lo[0]) & (p[:, 0] < hi[0]) & (p[:, 1] > lo[1]) & (p[:, 1] < hi[1]) & (p[:, 2] > hi[2] - 0.006)
    return int(inside.sum())


def chips_at_end(sc, frames, amount="REALISTIC"):
    machining.settings(sc).chips = amount
    bk = chips.bake(sc, force=True)
    assert bk is not None and bk.count > 0
    return bk, on_block(bk, frames)


# ---------------------------------------------------------------------------


def test_air_codes_give_the_air_frames(scene):
    _a, b, frames = build_program(scene)
    sp = air.spans(scene)
    assert len(sp) == 1 and sp[0, 2] == 0.0
    # on from the M7 (before the plunge) to the M9 (before the tool goes up): most of the step
    assert 1 <= sp[0, 0] < 0.3 * frames and 0.8 * frames < sp[0, 1] <= frames + 1
    info = gcode.info(scene, b)
    assert info["air"].startswith("Air: on 1 time")
    # other codes: M8 / M9 do not match M7 -> no air; "always" -> while the spindle turns
    scene.fresing.cnc.air_on_code = 8
    build_program(scene)
    assert len(air.spans(scene)) == 0
    scene.fresing.cnc.air_always = True
    build_program(scene)
    sp2 = air.spans(scene)
    assert len(sp2) == 1 and sp2[0, 0] < sp[0, 0] + 1e-6 and sp2[0, 1] >= sp[0, 1] - 1e-6
    # Clear keys: no air any more
    animation.clear_keys(scene)
    assert len(air.spans(scene)) == 0


def test_user_air_code_is_not_reported_as_a_problem(scene):
    text = POCKET.replace("M7", "M101").replace("M9", "M102")
    scene.fresing.cnc.air_on_code, scene.fresing.cnc.air_off_code = 101, 102
    _a, b, _f = build_program(scene, text)
    info = gcode.info(scene, b)
    assert not any("M101" in p or "M102" in p for p in info["problems"]), info["problems"]
    assert len(air.spans(scene)) == 1
    scene.fresing.cnc.air_on_code = 7                       # another code: M101 is reported again (at once)
    assert any("M101" in p for p in gcode.info(scene, b)["problems"])


def test_through_the_spindle_blows_the_chips_off_the_block(scene):
    _a, _b, frames = build_program(scene)
    bk_air, n_air = chips_at_end(scene, frames)
    animation.clear_keys(scene)
    _a, _b, frames2 = build_program(scene, POCKET.replace("M7\n", "").replace("M9\n", ""))
    assert frames2 == frames
    bk_off, n_off = chips_at_end(scene, frames)
    print(f"\nthrough the spindle: {n_off} chips on the block without air, {n_air} with air "
          f"(of {bk_off.count} / {bk_air.count}; blown up again {bk_air.stats['blown']} times)")
    assert n_off > 50
    assert n_air < 0.25 * n_off


def test_external_nozzle_follows_the_head_and_blows(scene):
    spindle = ob(scene, "SPINDLE")
    tip_world = Vector((-28 * MM, 0.0, 130 * MM))              # the spindle's bottom edge, on the left
    note = air.use_nozzle(scene, spindle, tip_world)
    assert "clicked" in note and scene.fresing.cnc.air_source == "NOZZLE"
    d = spindle.matrix_world.to_3x3() @ Vector(scene.fresing.cnc.air_dir)
    assert d.z < -0.5                                          # aimed down at the workpiece
    scene.fresing.cnc.air_strength = "STRONG"
    _a, _b, frames = build_program(scene)
    s = machining.settings(scene)
    o = np.array(s["fr_air_o"]).reshape(-1, 3)
    assert len(o) == frames
    # the nozzle sits on the head: it goes down 25 mm with Z for the cut (Z -4 from Z 5 … and up to 20 mm)
    assert float(np.ptp(o[:, 2])) > 0.015
    assert float(np.ptp(o[:, 0])) > 0.05                       # and along X with the carriage
    bk, n_air = chips_at_end(scene, frames)
    scene.fresing.cnc.air_source = "SPINDLE"
    scene.fresing.cnc.air_on_code = 150                         # (no air: the program has no M150)
    build_program(scene)
    _bk0, n_off = chips_at_end(scene, frames)
    print(f"\nexternal nozzle (strong): {n_off} chips on the block without air, {n_air} with air")
    assert n_air < 0.5 * n_off


def test_blow_the_part_clean_at_the_end(scene):
    text = POCKET.replace("M7\n", "").replace("M9\n", "")      # no air in the program
    _a, b0, frames0 = build_program(scene, text)
    _bk, n_off = chips_at_end(scene, frames0)
    animation.clear_keys(scene)
    _a, b, frames = build_program(scene, text, gcode_clean=True, gcode_clean_time=2.0)
    assert frames == frames0 + 2 * 25 or abs(frames - (frames0 + 50)) <= 1
    sp = air.spans(scene)
    assert len(sp) == 1 and sp[0, 2] == 1.0 and sp[0, 1] - sp[0, 0] == pytest.approx(50, abs=1)
    # the tool goes over the part (through the spindle): X moves during the clean time
    xs = []
    for f in range(int(sp[0, 0]) + 1, frames, 5):
        scene.frame_set(f)
        xs.append(joints.get_value(scene.fresing.joints["X"]))
    assert max(xs) - min(xs) > 0.05
    bk, n_clean = chips_at_end(scene, frames)
    print(f"\nblow the part clean: {n_off} chips on the block before, {n_clean} at the last frame")
    assert n_clean <= max(3, 0.02 * n_off)
    assert bk.stats["blown"] > 0.5 * n_off                     # the lying chips were picked up and blown away
    assert "blows the part clean" in gcode.info(scene, b)["air"]


def test_blow_clean_from_a_nozzle_on_the_head(scene):
    air.use_nozzle(scene, ob(scene, "SPINDLE"), Vector((-28 * MM, 0.0, 130 * MM)))
    text = POCKET.replace("M7\n", "").replace("M9\n", "")
    _a, _b, frames = build_program(scene, text, gcode_clean=True, gcode_clean_time=2.0)
    xs = []
    sp = air.spans(scene)
    for f in range(int(sp[0, 0]) + 1, frames, 5):
        scene.frame_set(f)
        xs.append(joints.get_value(scene.fresing.joints["X"]))
    assert max(xs) - min(xs) < 1e-6                            # the tool stays where it is (only goes up)
    bk, n_clean = chips_at_end(scene, frames)
    before = on_block(bk, int(sp[0, 0]))
    print(f"\nblow clean from the nozzle (normal): {before} chips on the block before, {n_clean} at the last frame")
    assert n_clean <= max(5, 0.05 * before)


def test_the_same_chips_every_time(scene):
    _a, _b, frames = build_program(scene)
    machining.settings(scene).chips = "FEW"
    a = chips.bake(scene, force=True)
    b = chips.bake(scene, force=True)
    for f in (frames // 2, frames):
        x, y = a.at(f), b.at(f)
        for sp in (0, 1):
            assert np.array_equal(x[sp]["pos"], y[sp]["pos"]) and np.array_equal(x[sp]["slot"], y[sp]["slot"])


def test_old_projects_have_no_air(scene):
    c = scene.fresing.cnc
    assert (c.air_on_code, c.air_off_code, c.air_always, c.air_source, c.air_show) == (7, 9, False, "SPINDLE", False)
    _a, b, _f = build_program(scene, POCKET.replace("M7\n", "").replace("M9\n", ""))
    assert len(air.spans(scene)) == 0 and not b.gcode_clean
    assert air.inputs(scene, [], [], None, 1) is None


def test_show_air_cone_only_while_it_blows(scene):
    scene.fresing.cnc.air_show = True
    _a, _b, frames = build_program(scene)
    cone = bpy.data.objects.get(air.CONE_NAME)
    assert cone is not None and cone.parent is ob(scene, TOOL)
    sp = air.spans(scene)
    scene.frame_set(1)
    assert cone.hide_render
    scene.frame_set(int((sp[0, 0] + sp[0, 1]) / 2))
    assert not cone.hide_render
    scene.frame_set(frames)
    assert cone.hide_render
    scene.fresing.cnc.air_show = False
    assert bpy.data.objects.get(air.CONE_NAME) is None


def test_schedule_clean_moves_and_path():
    prog = gcore.read(POCKET)
    t = gcore.Timing(speed="FIT", fit_seconds=4.0, clean=2.0, clean_sweep=True)
    sch = gcore.Schedule(prog, t)
    assert sch.duration == pytest.approx(6.0) and sch.clean_span == pytest.approx((4.0, 6.0))
    clean = [p for p in sch.pieces if p.move.cycle == gcore.CLEAN]
    zs = {round(p.move.b[2], 6) for p in clean if p.move.moving}
    assert zs == {round(5.0 + gcore.CLEAN_LIFT, 6)}            # 15 mm over the highest feed move (the plunge from Z5)
    # the drawn toolpath leaves the clean moves out
    assert all(pt[3] <= 4.0 + 1e-9 for _r, line in sch.path() for pt in line)
    nozzle = gcore.Schedule(prog, gcore.Timing(speed="FIT", fit_seconds=4.0, clean=2.0, clean_sweep=False))
    xs = {round(p.move.b[0], 6) for p in nozzle.pieces if p.move.cycle == gcore.CLEAN}
    assert len(xs) == 1                                        # the tool stays where it is (it only goes up)
    assert sch.air_spans() == [(pytest.approx(sch.pieces[1].v0, abs=0.2), pytest.approx(sch.program_end, abs=0.3))]


def test_tooltips_of_the_air_settings():
    from fresing_render.blender.props import FRAnimBlock, FRCnc
    for cls, names in ((FRCnc, ("air_on_code", "air_off_code", "air_always", "air_source", "air_tip", "air_dir",
                                "air_strength", "air_cone", "air_reach", "air_show")),
                       (FRAnimBlock, ("gcode_clean", "gcode_clean_time"))):
        for n in names:
            assert len(cls.bl_rna.properties[n].description) > 30, n
    for op in ("cnc_air_nozzle", "cnc_air_click", "cnc_air_aim"):
        assert len(getattr(bpy.ops.fresing, op).get_rna_type().description) > 30, op


def test_queue_render_blows_the_part_clean(scene):
    """The real render queue (a background run) works the chips and the air out by itself: seen from straight
    above, a patch of the block beside the pocket has chips when the program ends and is bare again (as in the
    first frame) at the end of 'Blow the part clean'."""
    import time

    from PIL import Image

    from fresing_render.blender import logic, queue
    s = scene.fresing
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):          # what moves still moves and cuts, it is only not seen
        logic.set_hidden(ob(scene, name), True)
    text = POCKET.replace("M7\n", "").replace("M9\n", "")
    _a, _b, frames = build_program(scene, text, fit=0.3, fps=24, gcode_clean=True, gcode_clean_time=0.5)
    machining.settings(scene).chips = "REALISTIC"
    bk = chips.bake(scene, force=True)
    f_end = int(air.spans(scene)[0, 0])                          # the program's end: the blast starts
    pos = bk.at(f_end)[0]["pos"]

    def inside(p, cx, cy):
        return int(((np.abs(p[:, 0] - cx) < 0.02) & (np.abs(p[:, 1] - cy) < 0.02) & (p[:, 2] > TOP - 0.006)).sum())
    # a patch 40 mm wide on the block, clear of the pocket (x -35..35, y -25..25 mm), with the most chips
    spots = [(cx, cy) for cx in np.arange(-0.07, 0.071, 0.01) for cy in (-0.07, -0.05, 0.05, 0.07)]
    best = max(spots, key=lambda c: inside(pos, *c))
    assert inside(pos, *best) >= 5, inside(pos, *best)
    assert inside(bk.at(frames)[0]["pos"], *best) == 0
    animation.clear_keys(scene)
    cam_data = bpy.data.cameras.new("Top cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = 0.04
    cam = bpy.data.objects.new("Top cam", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (float(best[0]), float(best[1]), 0.3)
    scene.camera = cam
    for name in ("X.ASM", "COLUMN", "FINISHED PART"):
        logic.set_hidden(ob(scene, name), True)
    a, _b, frames2 = build_program(scene, text, fit=0.3, fps=24, gcode_clean=True, gcode_clean_time=0.5)
    assert frames2 == frames
    s.use_gpu = False
    a.out_format, a.out_resolution, a.quality, a.video = "square", "preview", "draft", "PNG"
    queue.add_job(scene, "ANIMATION", animation=a.name)
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(scene["tmp"], "air.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 900:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    names = sorted(f for f in os.listdir(job.output) if f.endswith(".png"))      # (fingerprint.txt: task 0054)
    assert len(names) == frames

    def pic(f):
        return np.asarray(Image.open(os.path.join(job.output, names[f - 1])).convert("RGB"), dtype=np.int16)
    first, mid, last = pic(1), pic(f_end), pic(frames)
    with_chips = (np.abs(mid - first).max(axis=2) > 30).mean()
    left = (np.abs(last - first).max(axis=2) > 30).mean()
    print(f"\nqueue: {with_chips:.4f} of the patch changed by chips at the program's end, {left:.4f} at the last frame")
    assert with_chips > 0.002 and left < 0.25 * with_chips


def test_panels_draw_with_air(scene):
    from test_blender import FakeLayout

    from fresing_render.blender import ops_gcode, ui_gcode, ui_machining
    errors = []

    def draw_all():
        for cls in (ui_gcode.FRESING_PT_cnc, ui_machining.FRESING_PT_milling_chips):
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            if cls.poll(bpy.context):
                for fn in (cls.draw, cls.draw_header, cls.draw_header_preset):
                    fn(fake, bpy.context)
        a = scene.fresing.animations.get("Program")
        if a is not None and len(a.blocks):
            ui_gcode.draw_step(bpy.context, FakeLayout(errors), scene, a, a.blocks[0])
            a.blocks_index = 0
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            ops_gcode.FRESING_OT_gcode_report.draw(fake, bpy.context)

    draw_all()
    machining.settings(scene).chips = "FEW"
    build_program(scene, gcode_clean=True)
    draw_all()
    scene.fresing.cnc.air_source = "NOZZLE"                       # no nozzle yet: says what to do
    assert air.problem(scene)
    draw_all()
    air.use_nozzle(scene, ob(scene, "SPINDLE"))
    assert air.problem(scene) == ""
    draw_all()
    assert not errors, errors


def test_nozzle_from_its_shape_aim_and_flip(scene):
    spindle = ob(scene, "SPINDLE")
    note = air.use_nozzle(scene, spindle)
    assert "shape" in note
    c = scene.fresing.cnc
    tip_w = spindle.matrix_world @ Vector(c.air_tip)
    assert tip_w.z == pytest.approx(130 * MM, abs=2 * MM)          # the spindle's end nearest the workpiece
    d = spindle.matrix_world.to_3x3() @ Vector(c.air_dir)
    assert d.z < -0.9                                             # blowing out of that end, down its axis
    assert bpy.ops.fresing.cnc_air_aim(flip=True) == {"FINISHED"}
    assert (spindle.matrix_world.to_3x3() @ Vector(c.air_dir)).z > 0.9
    assert bpy.ops.fresing.cnc_air_aim() == {"FINISHED"}
    assert (spindle.matrix_world.to_3x3() @ Vector(c.air_dir)).z < -0.5
    assert bpy.ops.fresing.cnc_air_nozzle(clear=True) == {"FINISHED"}
    assert c.air_nozzle is None and c.air_source == "SPINDLE"


def test_model_update_keeps_the_nozzle(scene):
    air.use_nozzle(scene, ob(scene, "SPINDLE"))
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=MILL, quality="draft", update_root=root.name) == {"FINISHED"}
    c = scene.fresing.cnc
    assert c.air_nozzle is ob(scene, "SPINDLE") and c.air_nozzle_uid
    assert c.air_source == "NOZZLE"
