"""Surroundings and props for scale (task 0016).

The layouts are checked without Blender (sizes, nothing in the machine's space or in the
camera's view); the rest inside Blender: every surrounding builds and renders a small CPU frame,
the machine stands on the floor, saved scenes / templates / the background queue keep it.
"""

import math
import os
import random
import time

import pytest

from fresing_render.core import surroundings as S

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")


# ---------------------------------------------------------------------------
# layouts (pure Python)
# ---------------------------------------------------------------------------

SIZES = [(1.0, 0.6, 0.18), (6.4, 2.4, 2.0), (25.0, 8.0, 14.0)]


def test_stored_numbers_never_change():
    """The Background setting is stored in project files by number: old projects must keep theirs."""
    numbers = {k.id: k.number for k in S.KINDS}
    assert numbers["COLOR"] == 0 and numbers["HDRI"] == 1 and numbers["SKY"] == 2 and numbers["TRANSPARENT"] == 3
    assert len(set(numbers.values())) == len(numbers)
    ids = [it[0] for it in S.enum_items() if it]
    assert ids.count("") == 4                      # four headings: studio, photo, offshore, workshop
    assert set(ids) - {""} == set(numbers)


@pytest.mark.parametrize("kind", S.BUILT)
@pytest.mark.parametrize("detail", ["SIMPLE", "DETAILED"])
@pytest.mark.parametrize("size", SIZES)
def test_layout_keeps_machine_space_and_view_free(kind, detail, size):
    lay = S.build(kind, size, detail)
    kx, ky, kh = lay.keepout
    assert kx > size[0] / 2 and ky > size[1] / 2 and kh > size[2]
    for role, shapes in lay.parts.items():
        for sh in shapes:
            if role != "floor":
                assert not S.overlaps_keepout(sh, lay.keepout), (role, sh)
            if role == "contents":
                assert not S.blocks_view(sh, lay), (role, sh)
    # floors are at z = 0 (top) and big enough for the machine and its space
    tops = [S.footprint(sh)[5] for sh in lay.parts.get("floor", []) if sh.mat not in ("line_yellow", "rail_steel")]
    if kind != "SEA":                              # the open sea's floor is the water itself
        assert tops and all(abs(t) < 1e-6 for t in tops), tops
    if kind in S.HALL_KINDS:
        hx, hy, hh = lay.hall
        assert hx > kx and hy > ky and hh > kh
    if kind in S.SEA_KINDS:
        assert lay.water_level is not None and lay.extent >= S.SEA_RADIUS
    else:
        assert lay.water_level is None


def test_detailed_has_more_than_simple():
    for kind in ("DECK", "QUAY", "FACTORY", "CNC", "ASSEMBLY", "WAREHOUSE"):
        n = {d: sum(1 for _ in S.build(kind, (6.4, 2.4, 2.0), d).all_shapes()) for d in ("SIMPLE", "DETAILED")}
        assert n["DETAILED"] > n["SIMPLE"], (kind, n)


def test_layouts_are_the_same_every_time():
    a = [(type(s).__name__, s.mat, S.footprint(s)) for s in S.build("WAREHOUSE", (5, 3, 3), "DETAILED").all_shapes()]
    b = [(type(s).__name__, s.mat, S.footprint(s)) for s in S.build("WAREHOUSE", (5, 3, 3), "DETAILED").all_shapes()]
    assert a == b


def test_halls_grow_with_the_machine():
    small = S.hall_size("ASSEMBLY", 2, 1, 1)
    big = S.hall_size("ASSEMBLY", 30, 10, 16)
    assert big[0] > small[0] and big[1] > small[1] and big[2] >= 16 + 2.5


def test_prop_sizes():
    w, d, h = S.prop_size("PERSON")
    assert 1.75 < h < 1.85 and w < 0.7 and d < 0.4
    w, d, h = S.prop_size("CONTAINER")
    assert abs(w - 6.058) < 0.1 and abs(d - 2.438) < 0.05 and abs(h - 2.591) < 0.01
    w, d, h = S.prop_size("PALLET")
    assert abs(w - 1.2) < 0.01 and abs(d - 0.8) < 0.01 and h > S.PALLET_H
    w, d, h = S.prop_size("BARRIER")
    assert 1.9 < w < 2.1 and 0.9 < h < 1.1


def test_props_line_up_beside_the_machine():
    machine = (-1.0, 1.0, -0.5, 0.5)
    sizes = [S.prop_size(k)[:2] for k in ("PERSON", "CONTAINER", "PALLET", "BARRIER")]
    boxes = []
    for i, (sx, sy) in enumerate(sizes):
        x, y = S.prop_spot(i, machine, sizes)
        boxes.append((x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2))
    for i, a in enumerate(boxes):
        assert a[0] > machine[1], "props stand beside the machine, not in it"
        for b in boxes[i + 1:]:
            assert a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2], "props must not overlap"


def test_place_turns_and_moves():
    box = S.Box("x", 1.0, 0.0, 0.0, 2.0, 1.0, 1.0)
    moved = S.place([box], 10.0, 0.0, 0.5, math.pi / 2)[0]
    assert abs(moved.x - 10.0) < 1e-9 and abs(moved.y - 1.0) < 1e-9 and moved.z == 0.5
    x0, x1, y0, y1, *_ = S.footprint(moved)
    assert abs((x1 - x0) - 1.0) < 1e-9 and abs((y1 - y0) - 2.0) < 1e-9


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
import numpy as np  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, logic, render, states, surroundings, world  # noqa: E402


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
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=STEP, quality="draft") == {"FINISHED"}
    s = sc.fresing
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 64, 36
    s.use_gpu = False
    return sc


def _env_objects(sc, role=None):
    return [ob for ob in surroundings._objects(sc) if role is None or ob[surroundings.TAG] == role]


def _top_of(ob) -> float:
    mw = np.array(ob.matrix_world)
    bb = np.array([list(c) + [1.0] for c in ob.bound_box])
    return float((mw @ bb.T).T[:, 2].max())


def _pixels(path):
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    size = tuple(img.size)
    bpy.data.images.remove(img)
    return px.reshape(size[1], size[0], 4), size


@pytest.mark.parametrize("kind", S.BUILT)
def test_each_surrounding_builds_and_renders(scene, kind, tmp_path):
    s = scene.fresing
    mn, mx = logic.cached_bounds(scene)
    for detail in ("SIMPLE", "DETAILED"):
        s.env_detail = detail
        s.background = kind
        objs = _env_objects(scene)
        assert objs, f"{kind} {detail}: nothing built"
        root = surroundings.root_object()
        assert root["fr_kind"] == kind
        # the machine stands on the floor, centred
        assert abs(root.location.z - mn[2]) < 1e-5
        assert abs(root.location.x - (mn[0] + mx[0]) / 2) < 1e-5
        floors = _env_objects(scene, "floor")
        if floors:
            assert abs(_top_of(floors[0]) - mn[2]) < 0.006       # floor top (painted lines are 5 mm)
        if kind in S.SEA_KINDS:
            sea = _env_objects(scene, "sea")[0]
            assert sea.data.materials[0].name.startswith(surroundings.MAT_PREFIX + "water")
            if detail == "DETAILED":
                assert sea.modifiers and sea.modifiers[0].type == "NODES"
            assert scene.camera.data.clip_end >= S.SEA_RADIUS, "the camera must see to the horizon"
        # no picture files needed: every image used is made in code or the studio light
        for img in bpy.data.images:
            assert img.filepath == "" or os.path.isfile(bpy.path.abspath(img.filepath)), img.name
        # the old floor is not shown under the surroundings
        floor = bpy.data.objects.get(world.FLOOR_NAME)
        assert floor is None or floor.hide_render
        path = str(tmp_path / f"{kind}_{detail}.png")
        render.render_still(scene, s, "draft", filepath=path)
        px, size = _pixels(path)
        assert size == (32, 18)                     # draft: half size
        assert px[:, :, :3].std() > 0.01, "the picture must not be one flat colour"
        assert px[:, :, 3].min() > 0.99, "surroundings fill the background"


def test_rebuilt_only_when_settings_change(scene):
    s = scene.fresing
    s.background = "FACTORY"
    first = {ob.name: ob.as_pointer() for ob in _env_objects(scene)}
    world.apply(scene, s)                         # what a render or the queue does
    s.light_strength = 1.5
    s.exposure = 0.5
    assert {ob.name: ob.as_pointer() for ob in _env_objects(scene)} == first
    s.env_detail = "DETAILED"                     # a real change: rebuilt
    assert {ob.name: ob.as_pointer() for ob in _env_objects(scene)} != first
    s.background = "COLOR"                        # back to the studio: everything removed
    assert not _env_objects(scene)
    assert not [m for m in bpy.data.meshes if m.users == 0 and m.name.startswith("FR ")]


def test_floor_gap_and_put_on_floor_again(scene):
    s = scene.fresing
    s.background = "WAREHOUSE"
    mn, mx = logic.cached_bounds(scene)
    s.floor_offset = 0.25
    root = surroundings.root_object()
    assert abs(root.location.z - (mn[2] - 0.25)) < 1e-5
    s.floor_offset = 0.0
    # the machine is moved (another model revision would do this): the button follows it
    root_model = build.model_roots(scene)[0]
    root_model.location.z += 2.0
    bpy.context.view_layer.update()
    assert bpy.ops.fresing.env_place() == {"FINISHED"}
    assert abs(surroundings.root_object().location.z - (mn[2] + 2.0)) < 1e-4


def test_saved_scene_and_template_keep_the_surroundings(scene, tmp_path):
    from fresing_render.blender.ops_main import _template_from_scene, apply_template
    from fresing_render.core.template import Template
    s = scene.fresing
    s.background = "DECK"
    s.sea_state = "ROUGH"
    s.env_detail = "DETAILED"
    states.save_shot(scene, "On the vessel")
    path = str(tmp_path / "tpl.json")
    _template_from_scene(scene).save(path)
    s.background = "COLOR"
    s.sea_state = "CALM"
    assert not _env_objects(scene)
    states.apply_shot(scene, "On the vessel")
    assert s.background == "DECK" and s.sea_state == "ROUGH" and s.env_detail == "DETAILED"
    assert surroundings.root_object()["fr_kind"] == "DECK" and _env_objects(scene, "sea")
    s.background = "COLOR"
    apply_template(scene, Template.load(path))
    assert s.background == "DECK" and _env_objects(scene, "sea")


def test_waves_move_in_animations(scene, tmp_path):
    s = scene.fresing
    s.env_detail = "DETAILED"
    s.background = "SEA"
    sea = _env_objects(scene, "sea")[0]

    def heights(frame):
        scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        me = sea.evaluated_get(dg).to_mesh()
        z = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", z)
        sea.evaluated_get(dg).to_mesh_clear()
        return z.reshape(-1, 3)[:2000, 2]

    a, b = heights(1), heights(25)
    assert np.abs(a).max() > 0.02, "waves near the machine"
    assert np.abs(a - b).max() > 0.01, "the waves move"
    s.sea_moving = False
    sea = _env_objects(scene, "sea")[0]           # rebuilt
    a, b = heights(1), heights(25)
    assert np.allclose(a, b), "still sea: the same in every frame"
    scene.frame_set(1)


def test_props_for_scale(scene):
    s = scene.fresing
    mn, mx = logic.cached_bounds(scene)
    for kind in S.PROPS:
        assert bpy.ops.fresing.prop_add(kind=kind) == {"FINISHED"}
    props = surroundings.props(scene)
    assert [p[surroundings.PROP_TAG] for p in props] == list(S.PROPS)
    for p in props:
        assert abs(p.location.z - mn[2]) < 1e-5, "props stand on the floor"
        assert p.location.x > mx[0], "beside the machine"
        assert not p.hide_select and not p.lock_location[0], "props can be moved"
    person = props[0]
    assert 1.75 < person.dimensions.z < 1.85
    s.props_visible = False
    assert all(p.hide_render and p.hide_viewport for p in props)
    states.save_shot(scene, "Without props")
    s.props_visible = True
    assert not any(p.hide_render for p in props)
    states.apply_shot(scene, "Without props")
    assert all(p.hide_render for p in props)
    # surroundings come and go, props stay
    s.background = "QUAY"
    s.background = "COLOR"
    assert len(surroundings.props(scene)) == 4
    # props stand on the surroundings' floor when it is lowered
    s.background = "FACTORY"
    s.floor_offset = 0.5
    assert bpy.ops.fresing.env_place() == {"FINISHED"}
    assert all(abs(p.location.z - (mn[2] - 0.5)) < 1e-5 for p in surroundings.props(scene))
    assert surroundings.remove_props(scene) == 4 and not surroundings.props(scene)


def _write_hdr(path, sky=(0.9, 1.0, 1.2), ground=(0.35, 0.25, 0.15)):
    w, h = 128, 64
    px = np.zeros((h, w, 4), np.float32)
    px[h // 2:, :, :3] = sky             # rows go bottom-up: the top half is the sky
    px[: h // 2, :, :3] = ground
    px[:, :, 3] = 1.0
    img = bpy.data.images.new("test_hdr", w, h, alpha=False, float_buffer=True)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "HDR"
    img.save()
    bpy.data.images.remove(img)


def test_photo_ground_looks_like_the_photo(scene, tmp_path):
    """The machine stands on the photo's ground: away from the machine the ground shows exactly the
    photo's colour; under it, its shadow."""
    s = scene.fresing
    hdr = str(tmp_path / "test.hdr")
    _write_hdr(hdr)
    s.hdri_path = hdr
    s.background = "HDRI"
    assert surroundings.root_object()["fr_kind"] == "PHOTO"
    assert _env_objects(scene, "photo_dome") and _env_objects(scene, "photo_ground")
    img = next(i for i in bpy.data.images if i.filepath and os.path.samefile(bpy.path.abspath(i.filepath), hdr))
    e = surroundings._irradiance(img)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    sky = px.reshape(img.size[1], img.size[0], 4)[img.size[1] // 2:, :, :3].mean(axis=(0, 1))
    assert np.allclose(e, sky * math.pi, rtol=0.02), (e, sky)      # an even sky gives π × its brightness
    # look straight down at the ground beside the machine
    cam = scene.camera
    mn, mx = logic.cached_bounds(scene)
    cam.location = ((mn[0] + mx[0]) / 2 + 20.0, (mn[1] + mx[1]) / 2, mn[2] + 3.0)
    cam.rotation_mode = "XYZ"
    cam.rotation_euler = (0.0, 0.0, 0.0)
    path = str(tmp_path / "photo.png")
    s.out_custom_w, s.out_custom_h = 32, 32
    render.render_still(scene, s, "preview", filepath=path)
    px, _ = _pixels(path)
    centre = px[12:20, 12:20, :3].mean(axis=(0, 1))
    # same as the photo's ground colour shown straight (tone mapped the same way as the dome)
    s.photo_ground = False
    s.floor = "NONE"
    path2 = str(tmp_path / "photo_plain.png")
    render.render_still(scene, s, "preview", filepath=path2)
    plain = _pixels(path2)[0][12:20, 12:20, :3].mean(axis=(0, 1))
    assert np.allclose(centre, plain, atol=0.04), (centre, plain)
    assert not _env_objects(scene), "photo ground off: dome removed"


def test_panel_draws_for_every_background(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui
    s = scene.fresing
    surroundings.add_prop(scene, "PERSON")
    errors = []
    for kind in [k.id for k in S.KINDS]:
        s.background = kind
        for lighting in ("STUDIO", "HDRI", "SKY"):
            s.lighting = lighting
            for cls in (ui.FRESING_PT_scene, ui.FRESING_PT_props):
                fake = type("P", (), {"layout": FakeLayout(errors)})()
                cls.draw(fake, bpy.context)
                cls.draw_header_preset(fake, bpy.context)
    assert not errors, errors


def test_tooltips_in_panel_5():
    """Every setting and button of panel 5 says what it does (CLAUDE.md: tooltips)."""
    from fresing_render.blender import ops_main, ops_surroundings
    props = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties
    keys = states.WORLD_KEYS + states.OUTPUT_KEYS + ("use_gpu", "out_folder", "env_show_in_view")
    for k in keys:
        assert len(props[k].description) > 20, k
    for cls in ops_surroundings.CLASSES + (
            ops_main.FRESING_OT_pick_hdri, ops_main.FRESING_OT_camera_add, ops_main.FRESING_OT_camera_activate,
            ops_main.FRESING_OT_camera_fit, ops_main.FRESING_OT_camera_remove, ops_main.FRESING_OT_camera_dof,
            ops_main.FRESING_OT_preview, ops_main.FRESING_OT_render, ops_main.FRESING_OT_open_folder):
        assert cls.__doc__ and len(cls.__doc__.strip()) > 30, cls.__name__


def test_queue_renders_the_surroundings(scene, tmp_path):
    """A still and a short animation of a saved scene on a vessel deck, in the background queue."""
    from fresing_render.blender import queue
    s = scene.fresing
    s.background = "DECK"
    s.env_detail = "DETAILED"
    s.quality = "draft"
    s.out_resolution = "preview"
    s.out_format = "presentation"
    states.save_shot(scene, "Deck")
    s.background = "COLOR"                        # the queue must switch to the deck itself
    a = s.animations.add()
    a.name = "Waves"
    a.tail = 0.08
    a.out_resolution = "preview"
    a.quality = "draft"
    a.start_shot = "Deck"
    queue.add_job(scene, "STILL", shot="Deck")
    queue.add_job(scene, "ANIMATION", animation="Waves")
    for job in s.queue:
        job.quality = "draft"
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "q.blend"))
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(scene) and time.time() - t0 < 900:
        time.sleep(1.0)
    queue.sync(scene)
    st = [(x.label, x.status, x.message) for x in s.queue]
    assert all(x.status == "DONE" for x in s.queue), (st, queue.log_tail(qdir, 40))
    still = s.queue[0].output
    px, size = _pixels(still)
    assert px[:, :, 3].min() > 0.99 and px[:, :, :3].std() > 0.02
    frames = os.path.splitext(s.queue[1].output)[0]
    names = sorted(os.listdir(frames))
    assert len(names) >= 2
    first, _ = _pixels(os.path.join(frames, names[0]))
    last, _ = _pixels(os.path.join(frames, names[-1]))
    assert np.abs(first - last).max() > 0.02, "the sea moves between frames"
