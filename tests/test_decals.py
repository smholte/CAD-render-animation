"""Decals (task 0024) in Blender: pictures, text and stickers on flat and round faces, every copy or one
copy, moving and sizing by numbers, hiding with the part, model update, save + reopen, templates and a
background render that shows them."""

import os
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
DECALS_A = os.path.join(HERE, "data", "test_decals_a.step")
DECALS_B = os.path.join(HERE, "data", "test_decals_b.step")

import fresing_render  # noqa: E402
from fresing_render.blender import build, decals, logic, ops_main, queue, states  # noqa: E402
from fresing_render.core import decal_geometry as G  # noqa: E402
from fresing_render.core.template import Template  # noqa: E402

# face numbers in OpenCascade's order: a box 0 -X, 1 +X, 2 -Y, 3 +Y, 4 -Z, 5 +Z; a cylinder 0 = round face
TOP, PLUS_X, ROUND = 5, 1, 0


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def fresh(path=DECALS_A):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return bpy.context.scene


@pytest.fixture()
def scene(tmp_path):
    sc = fresh()
    sc.fresing.out_folder = str(tmp_path)
    return sc


def part(sc, name, n=0):
    hits = sorted((o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name), key=lambda o: o[build.PROP_UID])
    return hits[n]


def decal_objects(sc=None):
    return [o for o in bpy.data.objects if decals.is_decal(o)]


def bounds(item):
    co = np.array([v.co[:] for v in item.mesh.vertices])
    return co.min(axis=0), co.max(axis=0)


@pytest.fixture()
def logo(tmp_path):
    """A 64 x 32 picture: left half red, right half blue."""
    img = bpy.data.images.new("logo", 64, 32, alpha=True)
    px = np.zeros((32, 64, 4), dtype=np.float32)
    px[:, :32] = (1, 0, 0, 1)
    px[:, 32:] = (0, 0, 1, 1)
    img.pixels.foreach_set(px.reshape(-1))
    path = str(tmp_path / "Logo ä.png")
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    return path


def test_picture_on_a_flat_face(scene, logo):
    panel = part(scene, "PANEL")
    it = decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    assert it.name == "Logo ä" and it.kind == "PICTURE" and it.aspect == pytest.approx(0.5)
    assert it.picture.packed_file is not None                         # kept inside the project
    assert it.height == pytest.approx(it.width * 0.5)
    lo, hi = bounds(it)
    assert hi[2] == pytest.approx(0.01 + G.OFFSET, abs=1e-6) and lo[2] == pytest.approx(hi[2], abs=1e-6)
    assert ((lo + hi) / 2)[:2] == pytest.approx((0.2, 0.15), abs=1e-5)  # centred on the click
    assert (hi - lo)[0] == pytest.approx(it.width, rel=1e-5)          # upright on a top face: +Y is up
    obs = decal_objects()
    assert len(obs) == 1 and obs[0].parent is panel and obs[0].data is it.mesh
    assert obs[0].hide_select and not obs[0].visible_shadow
    assert obs[0].matrix_world == panel.matrix_world                  # in the part's own coordinates


def test_text_and_sticker_on_a_round_face_all_copies_and_one_copy(scene):
    b0, b1 = part(scene, "BARREL", 0), part(scene, "BARREL", 1)
    assert b0.data is b1.data                                         # two copies of one part
    sticker = decals.add(b0, ROUND, (0.06, 0.0, 0.1), (1, 0, 0), "STICKER", sticker="WARN_HOT")
    serial = decals.add(b1, ROUND, (0.06, 0.0, 0.25), (1, 0, 0), "TEXT", text="SN 0002", only_copy=True)
    assert decals.on_all_copies(sticker) and not decals.on_all_copies(serial)
    assert [it.name for it in decals.items_of(b0)] == ["Warning: hot surface"]
    assert [it.name for it in decals.items_of(b1)] == ["Warning: hot surface", "SN 0002"]
    by_parent = sorted((o.parent.name, o[decals.PROP_KEY]) for o in decal_objects())
    assert by_parent == sorted([(b0.name, sticker.key), (b1.name, sticker.key), (b1.name, serial.key)])
    # wrapped round the barrel: every point at the barrel's radius, the arc as long as the decal is wide
    p = np.array([v.co[:] for v in sticker.mesh.vertices])
    r = np.hypot(p[:, 0], p[:, 1])
    assert r.max() == pytest.approx(0.06 + G.OFFSET, rel=1e-3) and r.min() > 0.059
    arc = np.ptp(np.arctan2(p[:, 1], p[:, 0])) * 0.06
    assert arc == pytest.approx(sticker.width, rel=0.02)
    assert np.ptp(p[:, 2]) == pytest.approx(sticker.height, rel=1e-4)
    assert sticker.width == pytest.approx(0.1)                       # a warning sign starts at 100 mm
    assert sticker.use_field and tuple(sticker.field_color) == pytest.approx((0.947, 0.392, 0.0), abs=0.01)


def test_move_turn_and_size_by_numbers(scene, logo):
    it = decals.add(part(scene, "PANEL"), TOP, (0.2, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    it.width = 0.1
    assert it.height == pytest.approx(0.05)                          # proportions kept
    it.offset_x, it.offset_y = 0.03, -0.02
    lo, hi = bounds(it)
    assert ((lo + hi) / 2)[:2] == pytest.approx((0.23, 0.13), abs=1e-5)
    import math
    it.angle = math.radians(90)
    lo, hi = bounds(it)
    assert (hi - lo)[:2] == pytest.approx((0.05, 0.1), abs=1e-5)
    it.keep_ratio = False
    it.height = 0.02
    assert it.width == pytest.approx(0.1)
    it.keep_ratio = True
    assert it.height == pytest.approx(0.05)
    decals.fit(it)
    lo, hi = bounds(it)
    assert ((lo + hi) / 2)[:2] == pytest.approx((0.2, 0.15), abs=1e-5)   # centred on the face again
    assert (hi - lo)[:2] == pytest.approx((0.135, 0.27), rel=1e-4)    # turned: its width runs along the 300 mm side
    decals.make_upright(it)
    assert it.angle == 0.0


def test_decal_hides_with_its_part_and_can_be_switched_off(scene):
    panel = part(scene, "PANEL")
    it = decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="CE")
    ob = decal_objects()[0]
    dg = bpy.context.evaluated_depsgraph_get()

    def hidden():
        bpy.context.view_layer.update()
        e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return bool(e.hide_render), bool(e.hide_viewport)

    assert hidden() == (False, False)
    logic.set_hidden(panel, True)
    assert hidden() == (True, True)
    logic.set_hidden(panel, False)
    assert hidden() == (False, False) and not ob.hide_get()           # never hidden on its own in the view
    it.hidden = True
    assert hidden() == (True, True)
    it.hidden = False
    # an animation that hides the part hides the decal too (plain MAX drivers: no scripts needed)
    panel.hide_render = False
    panel.keyframe_insert("hide_render", frame=1)
    panel.hide_render = True
    panel.keyframe_insert("hide_render", frame=5)
    bpy.context.scene.frame_set(1)
    assert ob.evaluated_get(dg).hide_render is False
    bpy.context.scene.frame_set(5)
    assert ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).hide_render is True
    assert {fc.data_path for fc in ob.animation_data.drivers} == {"hide_render", "hide_viewport"}
    assert all(fc.driver.type == "MAX" for fc in ob.animation_data.drivers)
    # decals are not part of the CAD structure (the tree, hiding subassemblies, exploding)
    assert ob not in logic.Tree(scene).descendants(panel)


def test_a_click_on_a_sticker_counts_as_a_click_on_the_face_under_it(scene):
    from fresing_render.blender import faces
    panel = part(scene, "PANEL")
    decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="CE")
    ob = decal_objects()[0]
    hit = panel.matrix_world @ __import__("mathutils").Vector((0.2, 0.15, 0.01 + G.OFFSET))
    who, poly, loc, _n = decals.through(ob, 0, hit, (0, 0, 1))
    assert who is panel and faces.face_of_polygon(panel.data, poly) == TOP
    assert (loc - (panel.matrix_world @ __import__("mathutils").Vector((0.2, 0.15, 0.01)))).length < 1e-6
    assert decals.through(panel, 3, hit, (0, 0, 1))[:2] == (panel, 3)          # anything else: unchanged


def test_remove_and_every_copy_this_copy(scene):
    b0, b1 = part(scene, "BARREL", 0), part(scene, "BARREL", 1)
    it = decals.add(b0, ROUND, (0.06, 0.0, 0.1), (1, 0, 0), "STICKER", sticker="ARROW")
    assert len(decal_objects()) == 2
    one = decals.set_scope(it, b1, only_copy=True)
    assert [o.parent for o in decal_objects()] == [b1] and not decals.on_all_copies(one)
    back = decals.set_scope(one, b1, only_copy=False)
    assert len(decal_objects()) == 2 and decals.on_all_copies(back)
    mat, img = back.material.name, back.picture.name
    decals.remove(back)
    assert decal_objects() == [] and decals.count() == 0
    assert mat not in bpy.data.materials and img not in bpy.data.images     # nothing left behind


def test_type_plate_and_every_sticker_are_drawn(scene):
    panel = part(scene, "PANEL")
    plate = decals.add(panel, TOP, (0.1, 0.1, 0.01), (0, 0, 1), "STICKER", sticker="TYPE_PLATE")
    assert plate.finish == "METAL" and plate.use_field and plate.use_edge
    size = tuple(plate.picture.size)
    plate.plate_serial = "SN 4711"                                    # drawn again, same picture, same size
    assert tuple(plate.picture.size) == size and decals.count() == 1
    for key in ("CE", "WARN_GENERAL", "WARN_HAND", "WARN_ELECTRIC", "WARN_LOAD", "ARROW_TURN"):
        plate.sticker = key
        px = np.empty(len(plate.picture.pixels), dtype=np.float32)
        plate.picture.pixels.foreach_get(px)
        assert px.reshape(-1, 4)[:, 0].mean() > 0.02, key             # ink drawn


def test_model_update_keeps_decals_whose_spot_is_still_there(scene):
    s = scene.fresing
    panel, box = part(scene, "PANEL"), part(scene, "BOX")
    b1 = part(scene, "BARREL", 1)
    decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "TEXT", text="Panel")
    decals.add(part(scene, "BARREL", 0), ROUND, (0.06, 0.0, 0.05), (1, 0, 0), "STICKER", sticker="WARN_HOT")
    decals.add(b1, ROUND, (0.0, 0.06, 0.1), (0, 1, 0), "TEXT", text="SN 0002", only_copy=True)
    decals.add(box, TOP, (0.05, 0.05, 0.1), (0, 0, 1), "TEXT", text="Top")
    decals.add(box, PLUS_X, (0.1, 0.05, 0.05), (1, 0, 0), "TEXT", text="Side")
    root = build.model_roots(scene)[0]
    assert bpy.ops.fresing.import_step(filepath=DECALS_B, quality="draft", update_root=root.name) == {"FINISHED"}
    names = lambda p: sorted(it.name for it in decals.items_of(p))   # noqa: E731
    assert names(part(scene, "PANEL")) == ["Panel"]
    assert names(part(scene, "BARREL", 0)) == ["Warning: hot surface"]
    assert names(part(scene, "BARREL", 1)) == ["SN 0002", "Warning: hot surface"]
    box = part(scene, "BOX")
    by_name = {it.name: it for it in decals.items_of(box)}
    assert not by_name["Top"].lost and by_name["Side"].lost          # the +X face moved 20 mm
    shown = sorted((o.parent[build.PROP_NAME], o.name.split(" on ")[0]) for o in decal_objects())
    assert shown == [("BARREL", "SN 0002"), ("BARREL", "Warning: hot surface"), ("BARREL", "Warning: hot surface"),
                     ("BOX", "Top"), ("PANEL", "Panel")]
    assert all(o.parent is not None and o.parent.name in bpy.context.scene.objects for o in decal_objects())
    notes = [n.text for n in s.report_notes]
    assert any(n.startswith("BOX:") and "'Side'" in n for n in notes), notes
    assert len([n for n in notes if "decal" in n]) == 1
    # placed again with the mouse: back on
    side = by_name["Side"]
    decals.place(side, box, PLUS_X, (0.12, 0.05, 0.05), (1, 0, 0))
    assert not side.lost and len(decal_objects()) == 6


def test_save_and_reopen(scene, logo, tmp_path):
    decals.add(part(scene, "PANEL"), TOP, (0.2, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    decals.add(part(scene, "BARREL", 1), ROUND, (0.06, 0.0, 0.1), (1, 0, 0), "TEXT", text="SN|0002", only_copy=True)
    path = str(tmp_path / "decals.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    os.remove(logo)                                                   # the picture travels inside the project
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    items = {it.name: it for _p, it in decals.all_decals()}
    assert set(items) == {"Logo ä", "SN"}
    assert all(it.picture.packed_file is not None and len(it.mesh.polygons) for it in items.values())
    assert len(decal_objects()) == 2
    items["SN"].width = 0.05                                          # still works after reopening
    assert items["SN"].height == pytest.approx(0.05 * items["SN"].aspect)
    assert decals.count(sc) == 2


def test_template_puts_decals_on_parts_of_the_same_name(scene, logo, tmp_path):
    decals.add(part(scene, "PANEL"), TOP, (0.2, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    decals.add(part(scene, "BARREL", 0), ROUND, (0.06, 0.0, 0.1), (1, 0, 0), "STICKER", sticker="WARN_LOAD")
    t = ops_main._template_from_scene(scene)
    assert len(t.decals) == 2
    path = str(tmp_path / "t.json")
    t.save(path)
    fresh(DECALS_B)
    ops_main.apply_template(bpy.context.scene, Template.load(path))
    sc = bpy.context.scene
    assert sorted(it.name for _p, it in decals.all_decals()) == ["Logo ä", "Warning: hanging load"]
    assert len(decal_objects()) == 3                                  # both barrels
    assert decals.count(sc) == 2


def test_panel_draws(scene, logo):
    from test_blender import FakeLayout
    from fresing_render.blender import ui_decals
    d = scene.fresing_decal
    errors = []

    def draw():
        fake = type("P", (), {"layout": FakeLayout(errors)})()
        ui_decals.FRESING_PT_decals.draw(fake, bpy.context)
        ui_decals.FRESING_PT_decals.draw_header_preset(fake, bpy.context)

    draw()
    panel = part(scene, "PANEL")
    bpy.context.view_layer.objects.active = panel
    for kind in ("PICTURE", "TEXT", "STICKER"):
        d.kind = kind
        draw()
    decals.add(panel, TOP, (0.2, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    decals.add(panel, TOP, (0.1, 0.1, 0.01), (0, 0, 1), "TEXT", text="A")
    plate = decals.add(panel, TOP, (0.3, 0.2, 0.01), (0, 0, 1), "STICKER", sticker="TYPE_PLATE", only_copy=True)
    for it in decals.items_of(panel):
        d.active = it.key
        draw()
    plate.lost = True
    draw()
    d.placing = True
    draw()
    d.placing = False
    assert not errors, errors


def test_settings_problem_messages(scene):
    from fresing_render.blender import ops_decals
    d = scene.fresing_decal
    d.kind = "PICTURE"
    assert "Pick a picture" in ops_decals.settings_problem(d)
    d.picture = "/no/such/file.png"
    assert "not found" in ops_decals.settings_problem(d)
    d.kind = "TEXT"
    assert ops_decals.settings_problem(d) == "Type the text first"
    d.text = "Hi"
    assert ops_decals.settings_problem(d) == ""


def test_decals_in_a_background_render(scene, logo, tmp_path):
    """The queue renders a saved copy of the project in another Blender: the decals must show there,
    the right way round (red half of the picture on the left)."""
    s = scene.fresing
    panel = part(scene, "PANEL")
    for ob in build.iter_parts(scene):
        if ob is not panel:
            ob.hide_render = True
    pic = decals.add(panel, TOP, (0.12, 0.15, 0.01), (0, 0, 1), "PICTURE", picture=logo)
    pic.width = 0.16
    warn = decals.add(panel, TOP, (0.31, 0.15, 0.01), (0, 0, 1), "STICKER", sticker="WARN_GENERAL")
    warn.width = 0.14
    cam_data = bpy.data.cameras.new("Top")
    cam = bpy.data.objects.new("Top", cam_data)
    scene.collection.objects.link(cam)
    cam.location = (0.2, 0.15, 1.0)                                     # straight down, +Y up in the picture
    cam_data.type, cam_data.ortho_scale = "ORTHO", 0.42
    scene.camera = cam
    s.out_resolution = "preview"
    s.quality = "draft"
    s.use_gpu = False
    states.save_shot(scene, "Top")
    queue.add_job(scene, "STILL", shot="Top")
    s.queue[0].quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "q.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 300:
        time.sleep(1.0)
    queue.sync(scene)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 30))
    img = bpy.data.images.load(job.output)
    w, h = img.size
    px = np.array(img.pixels[:]).reshape(h, w, 4)[::-1, :, :3]       # row 0 at the top
    if os.environ.get("FRESING_KEEP_RENDER"):
        import shutil
        shutil.copy(job.output, os.environ["FRESING_KEEP_RENDER"])
    x = lambda m: int(w / 2 + (m - 0.2) / 0.42 * w)                   # noqa: E731  metres -> column
    y = int(h / 2)

    def colour(x0, x1):
        return px[y - 3:y + 3, x0:x1].mean(axis=(0, 1))

    red, blue = colour(x(0.06), x(0.10)), colour(x(0.14), x(0.18))
    assert red[0] > 0.4 and red[0] > 2 * red[2], red                  # the picture's left half
    assert blue[2] > 0.4 and blue[2] > 2 * blue[0], blue
    yellow = px[int(h * 0.62):int(h * 0.66), x(0.26):x(0.28)].mean(axis=(0, 1))
    assert yellow[0] > yellow[1] > yellow[2] and yellow[0] - yellow[2] > 0.15, yellow   # the sign's yellow
    grey = colour(x(0.005), x(0.02))
    assert abs(grey[0] - grey[2]) < 0.05                               # the panel itself
