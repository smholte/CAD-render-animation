"""Studio light looks, standard camera views, background blur with a sharp spot, one-click
turntable video (task 0017).

The light designs, the words, the blur and turntable numbers are checked without Blender; the rest
inside Blender: every look and light choice builds and renders a small CPU frame, every view frames
the model (all corners inside the picture), the sharp spot sets the focus distance from a click,
the turntable makes a valid animation that the background queue renders.
"""

import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import studio

HERE = os.path.dirname(__file__)
STEP = os.path.join(HERE, "data", "test_machine.step")
CRANE = os.path.join(HERE, "data", "test_crane_a.step")


# ---------------------------------------------------------------------------
# pure Python
# ---------------------------------------------------------------------------


def test_stored_light_numbers_never_change():
    """The Light setting is stored in project files by number: old projects keep Studio, 360° photo, Sky."""
    numbers = {it[0]: it[3] for it in studio.LIGHT_ITEMS}
    assert numbers["STUDIO"] == 0 and numbers["HDRI"] == 1 and numbers["SKY"] == 2
    assert len(set(numbers.values())) == len(numbers)
    assert {it[3] for it in studio.WEATHER_ITEMS} == {0, 1}
    assert {it[3] for it in studio.BLUR_ITEMS} == {0, 1, 2}


def _brightest_direction(px):
    """(azimuth, elevation) in degrees of the brightest pixel of a 360° light picture (rows bottom-up)."""
    lum = px[:, :, :3].mean(axis=2)
    y, x = np.unravel_index(np.argmax(lum), lum.shape)
    h, w = lum.shape
    lon = ((x + 0.5) / w - 0.5) * 360.0
    lat = ((y + 0.5) / h - 0.5) * 180.0
    return -lon, lat                          # Blender shows picture column lon at azimuth -lon


@pytest.mark.parametrize("kind", ["PRODUCT", "WHITE", "DARK"])
def test_light_pictures_put_the_main_light_where_the_words_say(kind):
    px = studio.env_pixels(kind, 512, 256)
    assert px.shape == (256, 512, 4) and np.isfinite(px).all() and px[:, :, 3].min() == 1.0
    d = studio.DESIGNS[kind]
    top = max(b.power for b in d.boxes if b.el < 70)
    strongest = [b for b in d.boxes if b.power == top]
    az, el = _brightest_direction(px)
    if kind != "WHITE":                      # white studio: the ceiling and the main light are about even
        assert any(abs(((az - b.az + 180) % 360) - 180) <= b.w / 2 + 2 for b in strongest), (kind, az, strongest)
    assert d.key is not None
    assert "front left" in studio.light_words(kind)


def test_dark_studio_is_dark_and_white_studio_is_bright():
    dark = studio.env_pixels("DARK", 256, 128)[:, :, :3]
    white = studio.env_pixels("WHITE", 256, 128)[:, :, :3]
    assert np.median(dark) < 0.02 < 0.5 < np.median(white)


def test_overcast_sky_is_brightest_overhead():
    px = studio.env_pixels("OVERCAST", 256, 128)[:, :, :3].mean(axis=2)
    zenith, horizon = px[-1].mean(), px[64].mean()
    assert zenith == pytest.approx(3 * horizon, rel=0.05)          # CIE overcast sky: 3 : 1
    assert np.ptp(px[100]) < 1e-6, "the same from every side: no sun"


def test_light_words():
    assert studio.light_words("PRODUCT") == "Main light from the front left, high · normal brightness"
    assert "from the back right" in studio.light_words("STUDIO")
    # turning the light moves the main light around the machine (clockwise seen from above)
    assert "from the front right" in studio.light_words("PRODUCT", rotation=-90)
    assert "Sun from the back" in studio.light_words("SKY", "SUN", 0.0, 1.0, 45.0)
    assert "low" in studio.light_words("SKY", "SUN", 0.0, 1.0, 5.0)
    assert studio.light_words("SKY", "OVERCAST").startswith("Soft light from the whole sky")
    assert studio.light_words("HDRI").startswith("Light from the 360° photo")
    assert studio.light_words("PRODUCT", strength=0.3).endswith("dim")
    assert studio.light_words("PRODUCT", strength=3.0).endswith("very bright")
    for az, words in ((-90, "front"), (0, "right"), (90, "back"), (180, "left"), (-135, "front left"),
                      (45, "back right"), (-180, "left"), (359, "right")):
        assert studio.side_words(az) == words, az


@pytest.mark.parametrize("lighting", ["PRODUCT", "WHITE", "DARK", "STUDIO", "SKY"])
@pytest.mark.parametrize("want", [-170, -115, -45, 0, 60, 135])
def test_rotation_for_puts_the_main_light_there(lighting, want):
    r = studio.rotation_for(lighting, want)
    assert -180 <= r <= 180
    az, _el = studio.main_light(lighting, "SUN", r, 30)
    assert abs(((az - want + 180) % 360) - 180) < 1e-6


def test_looks_set_what_they_say():
    for look in ("PRODUCT", "WHITE", "DARK"):
        v = studio.look_settings(look, "DECK")
        assert v["background"] == "COLOR" and v["lighting"] == look and v["floor"] == "SHADOW"
    assert studio.look_settings("WHITE", "COLOR")["background_color"] == (1.0, 1.0, 1.0)
    assert studio.look_settings("DARK", "COLOR")["background_color"] == (0.0, 0.0, 0.0)
    sun = studio.look_settings("SUN", "FACTORY")
    assert sun["background"] == "SKY" and sun["sky_weather"] == "SUN"
    az, _ = studio.main_light("SKY", "SUN", sun["light_rotation"], sun["sun_elevation"])
    assert studio.side_words(az) == "front left"
    # on the sea, the deck and the quay only the weather changes
    for bg in ("SEA", "DECK", "QUAY"):
        assert "background" not in studio.look_settings("OVERCAST", bg)
        assert studio.look_settings("OVERCAST", bg)["sky_weather"] == "OVERCAST"


@pytest.mark.parametrize("focus", [0.6, 3.0, 12.0, 60.0])
@pytest.mark.parametrize("lens", [24.0, 50.0, 135.0])
def test_blur_is_the_same_share_of_the_picture_at_any_size(focus, lens):
    for level in ("LITTLE", "STRONG"):
        n = studio.blur_fstop(level, lens, 36.0, focus)
        if studio.FSTOP_MIN < n < studio.FSTOP_MAX:
            far = studio.blur_share(n, lens, 36.0, focus, 1e9)
            assert far == pytest.approx(studio.BLUR[level], rel=1e-3), (level, n)
    assert studio.blur_fstop("STRONG", lens, 36, focus) < studio.blur_fstop("LITTLE", lens, 36, focus)
    assert studio.blur_fstop("NONE", lens, 36, focus) == studio.FSTOP_MAX


def test_a_little_blur_keeps_the_machine_sharp():
    """The far end of a machine framed by Fit (about 2× its size away) stays within 2 pixels of a
    1920-wide picture with 'A little'; 'Strong' visibly softens it."""
    size, dist = 6.0, 12.0
    for level, most in (("LITTLE", 2.0 / 1920), ("STRONG", 8.0 / 1920)):
        n = studio.blur_fstop(level, 50.0, 36.0, dist)
        far_end = studio.blur_share(n, 50.0, 36.0, dist, dist + size / 2)
        assert far_end < most, (level, far_end * 1920)


@pytest.mark.parametrize("seconds,fps", [(10, 25), (2, 24), (12.5, 30), (60, 60)])
def test_turntable_timing_loops_without_a_jump(seconds, fps):
    n, duration, angle = studio.turntable_timing(seconds, fps)
    assert n == round(seconds * fps)
    assert 1 + round(duration * fps) == n                    # the step's last frame is the video's last
    step = angle / (n - 1)
    assert step == pytest.approx(360.0 / n)
    assert angle + step == pytest.approx(360.0)              # one more step would be frame 1 again


# ---------------------------------------------------------------------------
# inside Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import build, cameras, logic, render, states, turntable, world  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def _scene(tmp_path, step=STEP):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    s = sc.fresing
    s.out_format = "custom"
    s.out_custom_w, s.out_custom_h = 64, 36
    s.use_gpu = False
    return sc


@pytest.fixture()
def scene(tmp_path):
    return _scene(tmp_path)


@pytest.fixture()
def crane(tmp_path):
    return _scene(tmp_path, CRANE)


def _pixels(path):
    img = bpy.data.images.load(path)
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    size = tuple(img.size)
    bpy.data.images.remove(img)
    return px.reshape(size[1], size[0], 4), size


def _corners(objs):
    pts = []
    for ob in objs:
        if ob.type == "MESH" and ob.visible_get():
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return pts


def _in_picture(scene, cam, pts, tol=1e-4):
    """(all inside, width share, height share) of the points in the camera's picture."""
    bpy.context.view_layer.update()
    co = np.array([tuple(world_to_camera_view(scene, cam, p)) for p in pts])
    inside = bool((co[:, :2] >= -tol).all() and (co[:, :2] <= 1 + tol).all() and (co[:, 2] > 0).all())
    return inside, float(np.ptp(co[:, 0])), float(np.ptp(co[:, 1]))


@pytest.mark.parametrize("look", list(studio.LOOKS))
def test_each_look_builds_and_renders(scene, look, tmp_path):
    s = scene.fresing
    assert bpy.ops.fresing.light_look(look=look) == {"FINISHED"}
    assert studio.look_matches(look, s)
    assert sum(studio.look_matches(other, s) for other in studio.LOOKS) == 1
    nt = scene.world.node_tree
    images = {n.image.name for n in nt.nodes if n.type == "TEX_ENVIRONMENT" and n.image}
    if look in ("PRODUCT", "WHITE", "DARK"):
        assert images == {world.LOOK_IMAGES[look][0]}
    elif look == "OVERCAST":
        assert images == {world.LOOK_IMAGES["OVERCAST"][0]}
    else:
        assert any(n.type == "TEX_SKY" for n in nt.nodes)
    path = str(tmp_path / f"{look}.png")
    render.render_still(scene, s, "draft", filepath=path)
    px, size = _pixels(path)
    assert size == (32, 18)
    rgb = px[:, :, :3]
    assert rgb.std() > 0.02, "the picture must not be one flat colour"
    mid = rgb[5:13, 10:22].mean()
    assert 0.03 < mid < 0.97, (look, mid)
    if look == "WHITE":                        # the endless white: exactly white away from the machine
        assert rgb[0, 0].min() > 0.995 and rgb[0, -1].min() > 0.995
    if look == "DARK":
        assert rgb[0, 0].max() < 0.01


@pytest.mark.parametrize("lighting", [it[0] for it in studio.LIGHT_ITEMS])
@pytest.mark.parametrize("weather", ["SUN", "OVERCAST"])
def test_every_light_choice_renders(scene, lighting, weather, tmp_path):
    s = scene.fresing
    s.background = "COLOR"
    s.lighting = lighting
    s.sky_weather = weather
    path = str(tmp_path / f"{lighting}_{weather}.png")
    render.render_still(scene, s, "draft", filepath=path)
    px, _ = _pixels(path)
    assert px[:, :, :3].std() > 0.01


def test_light_pictures_are_kept_in_the_project(scene, tmp_path):
    """A look's light picture is made once and saved inside the project file (with its bright softboxes)."""
    s = scene.fresing
    bpy.ops.fresing.light_look(look="PRODUCT")
    img = bpy.data.images[world.LOOK_IMAGES["PRODUCT"][0]]
    assert img.packed_file is not None
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    img = bpy.data.images[world.LOOK_IMAGES["PRODUCT"][0]]
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    assert px.max() > 5.0, "the softboxes keep their brightness"
    assert bpy.context.scene.fresing.lighting == "PRODUCT" and s is not None


def test_saved_scene_and_template_keep_the_weather(scene, tmp_path):
    s = scene.fresing
    bpy.ops.fresing.light_look(look="OVERCAST")
    states.save_shot(scene, "Grey day")
    bpy.ops.fresing.light_look(look="SUN")
    assert s.sky_weather == "SUN"
    states.apply_shot(scene, "Grey day")
    assert s.sky_weather == "OVERCAST" and s.background == "SKY"
    from fresing_render.blender import ops_main
    t = ops_main._template_from_scene(scene)
    assert t.background["sky_weather"] == "OVERCAST"
    bpy.ops.fresing.light_look(look="SUN")
    ops_main.apply_template(scene, t)
    assert s.sky_weather == "OVERCAST"


@pytest.mark.parametrize("view", list(cameras.VIEWS))
@pytest.mark.parametrize("shape", ["landscape", "portrait"])
def test_views_frame_the_model(crane, view, shape):
    s = crane.fresing
    s.out_custom_w, s.out_custom_h = (64, 36) if shape == "landscape" else (36, 64)
    render.apply_output(crane, s)
    s.view_space = "NORMAL"
    assert bpy.ops.fresing.camera_add(view=view) == {"FINISHED"}
    cam = crane.camera
    assert cam.name.startswith(cameras.VIEWS[view][0])
    assert (cam.data.type == "ORTHO") == (view in cameras.ORTHO_VIEWS)
    inside, w, h = _in_picture(crane, cam, _corners(build.iter_parts(crane)))
    assert inside, (view, shape)
    assert max(w, h) > 0.85, (view, shape, w, h)          # the model fills the picture (6 % space)


def test_views_frame_the_selection(crane):
    s = crane.fresing
    trolley = next(o for o in crane.objects if o.get("fr_name") == "TROLLEY.ASM")
    bpy.ops.object.select_all(action="DESELECT")
    trolley.select_set(True)                 # a subassembly: its parts count
    s.view_frame = "SELECTION"
    assert bpy.ops.fresing.camera_add(view="LOW") == {"FINISHED"}
    cam = crane.camera
    assert cam.name == "3/4 hero, low (selection)"
    parts = [d for d in logic.descendants(trolley, logic.Tree(crane)) if d.get("fr_kind") == "part"]
    inside, w, h = _in_picture(crane, cam, _corners(parts))
    assert inside and max(w, h) > 0.85, (w, h)
    whole, _, _ = _in_picture(crane, cam, _corners(build.iter_parts(crane)))
    assert not whole, "the trolley fills the picture: the rest of the crane does not fit"
    # nothing selected: the whole model
    bpy.ops.object.select_all(action="DESELECT")
    assert bpy.ops.fresing.camera_fit() == {"FINISHED"}
    assert _in_picture(crane, cam, _corners(build.iter_parts(crane)))[0]


def test_space_around(crane):
    s = crane.fresing
    sizes = {}
    for space in ("TIGHT", "NORMAL", "ROOMY"):
        s.view_space = space
        bpy.ops.fresing.camera_add(view="FRONT")
        inside, w, h = _in_picture(crane, crane.camera, _corners(build.iter_parts(crane)))
        assert inside
        sizes[space] = max(w, h)
    assert sizes["TIGHT"] > sizes["NORMAL"] > sizes["ROOMY"]
    assert sizes["TIGHT"] > 0.95 and sizes["ROOMY"] < 0.88


def test_new_camera_sees_the_horizon_on_the_sea(scene):
    from fresing_render.core import surroundings as env
    scene.fresing.background = "SEA"
    bpy.ops.fresing.camera_add(view="SIDE")
    assert scene.camera.data.clip_end >= env.SEA_RADIUS


def _click(scene, cam, part):
    """Where a click on the middle of ``part`` through the camera hits the model (like the eyedropper)."""
    bpy.context.view_layer.update()
    target = part.matrix_world @ (sum((Vector(c) for c in part.bound_box), Vector()) / 8)
    origin = cam.matrix_world.translation
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, _n, _i, ob, _m = scene.ray_cast(dg, origin, (target - origin).normalized())
    assert hit
    return getattr(ob, "original", ob), loc


def test_sharp_spot_sets_the_focus_distance_from_a_click(crane, tmp_path):
    s = crane.fresing
    cam = crane.camera
    assert s.camera_blur == "NONE" and not cam.data.dof.use_dof
    s.camera_blur = "LITTLE"
    assert cam.data.dof.use_dof
    middle = cam.data.dof.focus_distance
    trolley_part = next(o for o in crane.objects if o.get("fr_kind") == "part"
                        and "TROLLEY" in (o.parent.get("fr_name", "") if o.parent else ""))
    ob, loc = _click(crane, cam, trolley_part)
    cameras.set_focus(cam, crane, ob, loc)
    fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    expected = (loc - cam.matrix_world.translation).dot(fwd)
    assert cam.data.dof.focus_distance == pytest.approx(expected, abs=1e-4)
    assert abs(cam.data.dof.focus_distance - middle) > 0.01
    marker = cameras.focus_marker(cam)
    assert marker is not None and (marker.matrix_world.translation - loc).length < 1e-5
    assert cameras.focus_label(cam) == ob.get("fr_name", ob.name)
    little = cam.data.dof.aperture_fstop
    s.camera_blur = "STRONG"
    assert cam.data.dof.aperture_fstop < little
    assert cam.data.dof.aperture_fstop == pytest.approx(
        studio.blur_fstop("STRONG", cam.data.lens, cam.data.sensor_width, cam.data.dof.focus_distance))
    # the lens field of panel 5 keeps the blur the same look
    s.camera_lens = 85.0
    assert cam.data.lens == 85.0
    assert cam.data.dof.aperture_fstop == pytest.approx(
        studio.blur_fstop("STRONG", 85.0, cam.data.sensor_width, cam.data.dof.focus_distance))
    # the sharp spot moves with its part (a joint, a pose, an animation)
    top = ob
    while top.parent is not None and top.parent.get("fr_kind") in build.MODEL_KINDS:
        top = top.parent
    before = marker.matrix_world.translation.copy()
    ob.location.z += 0.25
    bpy.context.view_layer.update()
    assert (marker.matrix_world.translation - before).length == pytest.approx(0.25, abs=1e-4)
    ob.location.z -= 0.25
    # a render keeps it (and works in the queue: the camera carries everything)
    render.render_still(crane, s, "draft", filepath=str(tmp_path / "blur.png"))
    # back to the middle
    assert bpy.ops.fresing.focus_clear() == {"FINISHED"}
    assert cameras.focus_marker(cam) is None
    assert cam.data.dof.focus_distance == pytest.approx(cameras.focus_distance(cam, crane))
    assert not any(o.get(cameras.PROP_FOCUS) for o in bpy.data.objects)
    s.camera_blur = "NONE"
    assert not cam.data.dof.use_dof


def test_no_blur_without_perspective(crane):
    bpy.ops.fresing.camera_add(view="ISOMETRIC")
    cam = crane.camera
    crane.fresing.camera_blur = "STRONG"
    assert not cam.data.dof.use_dof
    assert not bpy.ops.fresing.focus_pick.poll()


def test_deleting_a_camera_deletes_its_sharp_spot(crane):
    cam = crane.camera
    ob, loc = _click(crane, cam, next(build.iter_parts(crane)))
    cameras.set_focus(cam, crane, ob, loc)
    assert bpy.ops.fresing.camera_remove(name=cam.name) == {"FINISHED"}
    assert not any(o.get(cameras.PROP_FOCUS) for o in bpy.data.objects)


def test_camera_with_old_blur_keeps_its_f_stop(scene):
    """A camera from before task 0017 with its own f-stop renders as before until the blur is changed."""
    cam = scene.camera
    del cam[cameras.PROP_BLUR]
    cam.data.dof.use_dof = True
    cam.data.dof.aperture_fstop = 2.8
    cam.data.dof.focus_distance = 1.234
    cameras.update_blur(cam, scene)
    bpy.ops.fresing.camera_fit()
    assert cam.data.dof.aperture_fstop == pytest.approx(2.8) and cameras.blur_level(cam) == "LITTLE"
    scene.fresing.camera_blur = "STRONG"
    assert cam.data.dof.aperture_fstop != pytest.approx(2.8)


def test_old_blur_button_still_works(scene):
    cam = scene.camera
    assert bpy.ops.fresing.camera_dof() == {"FINISHED"}
    assert cameras.blur_level(cam) == "LITTLE" and cam.data.dof.use_dof
    assert bpy.ops.fresing.camera_dof() == {"FINISHED"}
    assert cameras.blur_level(cam) == "NONE" and not cam.data.dof.use_dof


def test_turntable_makes_a_valid_animation(crane):
    from fresing_render.blender import animation
    s = crane.fresing
    s.turntable_seconds = 4.0
    s.turntable_height = "HIGH"
    s.camera_blur = "LITTLE"
    info = turntable.make(crane)
    a, cam = info["animation"], info["camera"]
    assert a.name == "Turntable" and a.start_shot == "Turntable" and a.tail == 0.0
    assert len(a.blocks) == 1
    b = a.blocks[0]
    assert (b.kind, b.camera_mode, b.easing) == ("CAMERA", "ORBIT", "LINEAR")
    n = info["frames"]
    assert n == 100 and animation.length_seconds(a) == pytest.approx((n - 1) / 25)
    # the camera looks at the turning axis, from the height asked for
    mn, mx = logic.update_bounds(crane)
    centre = Vector(((mn + mx) / 2).tolist())
    fwd = cam.matrix_world.to_3x3() @ Vector((0, 0, -1))
    p = cam.matrix_world.translation
    t = (centre.x - p.x) * fwd.x + (centre.y - p.y) * fwd.y
    on_axis = p + fwd * (t / max(1e-9, fwd.x ** 2 + fwd.y ** 2))
    assert math.hypot(on_axis.x - centre.x, on_axis.y - centre.y) < 1e-4
    assert math.degrees(math.asin(-fwd.z)) == pytest.approx(studio.TURNTABLE_HEIGHTS["HIGH"], abs=0.01)
    assert cam.data.dof.use_dof and cam.data.dof.focus_object is None
    # building it: the whole crane in the picture all the way round, the turn loops without a jump
    res = animation.bake(crane, a)
    assert res["frames"] == n and not res["warnings"]
    anim_cam = crane.camera
    assert anim_cam.get("fr_anim_camera")
    pts = _corners(build.iter_parts(crane))
    angles = []
    for f in (1, 2, n // 4, n // 2, 3 * n // 4, n):
        crane.frame_set(f)
        inside, w, h = _in_picture(crane, anim_cam, pts)
        assert inside, f
        q = anim_cam.matrix_world.translation
        angles.append(math.degrees(math.atan2(q.y - centre.y, q.x - centre.x)))
        assert anim_cam.data.dof.focus_distance == pytest.approx(cam.data.dof.focus_distance, rel=1e-4)
    step = (angles[1] - angles[0]) % 360
    assert step == pytest.approx(360.0 / n, abs=1e-3)
    assert (angles[0] - angles[-1]) % 360 == pytest.approx(step, abs=1e-3)
    animation.clear_keys(crane)
    # making it again updates the same camera, scene and animation
    info2 = turntable.make(crane)
    assert info2["animation"] == a and info2["camera"] == cam
    assert sum(1 for x in s.animations if x.get(turntable.TAG)) == 1
    assert sum(1 for c in cameras.fr_cameras(crane) if c.get("fr_turntable")) == 1


def test_turntable_starts_where_the_camera_looks_from(crane):
    bpy.ops.fresing.camera_add(view="SIDE")      # from the right: azimuth 0
    cam = turntable.make(crane)["camera"]
    mn, mx = logic.update_bounds(crane)
    p = cam.matrix_world.translation
    az = math.degrees(math.atan2(p.y - (mn[1] + mx[1]) / 2, p.x - (mn[0] + mx[0]) / 2))
    assert abs(az) < 1e-3


def test_turntable_says_halls_are_slower(scene):
    s = scene.fresing
    assert turntable.slow_note(s) == ""
    s.background = "CNC"
    s.env_detail = "DETAILED"
    assert "1.4 to 2.8 times" in turntable.slow_note(s) and "Simple" in turntable.slow_note(s)
    assert bpy.ops.fresing.env_simple() == {"FINISHED"}
    assert s.env_detail == "SIMPLE" and "Simple" not in turntable.slow_note(s)


def test_turntable_video_in_the_queue(crane, tmp_path):
    """One click puts the turntable in the background queue and starts it; the queue renders its frames
    (here: a time test, frame 1 and the middle frame, so the test stays short)."""
    from fresing_render.blender import queue
    s = crane.fresing
    s.turntable_seconds = 2.0
    s.turntable_quality = "draft"
    s.turntable_height = "LOW"
    a = turntable.make(crane)["animation"]
    a.out_resolution = "preview"
    a.out_format = "square"                  # 540 × 540: the smallest video
    a.video = "PNG"
    a.fps = "24"
    bpy.ops.fresing.light_look(look="PRODUCT")
    bpy.ops.wm.save_as_mainfile(filepath=str(tmp_path / "tt.blend"))
    assert bpy.ops.fresing.turntable() == {"FINISHED"}
    assert len(s.queue) == 1
    job = s.queue[0]
    assert (job.kind, job.animation, job.quality) == ("ANIMATION", "Turntable", "draft")
    assert queue.is_running(crane), "the button starts the queue"
    assert bpy.ops.fresing.turntable() == {"CANCELLED"}, "not twice while one waits or renders"
    queue.kill(crane)                        # 48 frames take minutes here: render a time test instead
    t0 = time.time()
    while queue.is_running(crane) and time.time() - t0 < 60:
        time.sleep(0.5)
    s.queue.remove(0)
    time.sleep(1.1)        # a queue started in the same second reuses the folder of the one just stopped
    queue.add_job(crane, "TEST", animation="Turntable")
    qdir = queue.start(bpy.context)
    t0 = time.time()
    while queue.is_running(crane) and time.time() - t0 < 900:
        time.sleep(1.0)
    queue.sync(crane)
    job = s.queue[0]
    assert job.status == "DONE", (job.message, queue.log_tail(qdir, 40))
    assert "for 48 frames" in job.message
    middle, size = _pixels(job.output)
    assert job.output.endswith("_frame_0024.png") and size == (540, 540)
    rgb = middle[:, :, :3]
    assert rgb[200:340, 200:340].std() > 0.02, "the machine is in the middle of the frame"
    # the light grey studio background of the look, put in exactly (0.8 = 0.906 on screen)
    assert abs(float(rgb[3, 3].mean()) - 0.906) < 0.02, rgb[3, 3]


def test_panel_5_draws(scene):
    from test_blender import FakeLayout
    from fresing_render.blender import ui
    from fresing_render.core import surroundings as env
    s = scene.fresing
    errors = []
    panels = (ui.FRESING_PT_scene, ui.FRESING_PT_camera, ui.FRESING_PT_turntable)
    cams = {"persp": scene.camera}
    bpy.ops.fresing.camera_add(view="ISOMETRIC")
    cams["ortho"] = scene.camera
    turntable.make(scene)

    def draw():
        for cls in panels:
            fake = type("P", (), {"layout": FakeLayout(errors)})()
            cls.draw(fake, bpy.context)
            if hasattr(cls, "draw_header_preset"):
                cls.draw_header_preset(fake, bpy.context)

    for look in studio.LOOKS:
        bpy.ops.fresing.light_look(look=look)
        draw()
    for bg in ("COLOR", "FACTORY", "SEA", "HDRI"):
        s.background = bg
        for lighting in [it[0] for it in studio.LIGHT_ITEMS]:
            s.lighting = lighting
            for weather in ("SUN", "OVERCAST"):
                s.sky_weather = weather
                draw()
    for kind, cam in cams.items():
        scene.camera = cam
        for blur in ("NONE", "LITTLE", "STRONG"):
            s.camera_blur = blur
            draw()
    scene.camera = None
    draw()
    assert not errors, errors
    assert env.HALL_KINDS


def test_tooltips_of_the_new_buttons_and_settings():
    """Every new button and setting says what it does; buttons that share an operator say it per button."""
    from fresing_render.blender import ops_main, ops_scene
    props = bpy.types.Scene.bl_rna.properties["fresing"].fixed_type.bl_rna.properties
    for k in ("sky_weather", "view_frame", "view_space", "camera_lens", "camera_blur", "turntable_seconds",
              "turntable_height", "turntable_quality", "lighting"):
        assert len(props[k].description) > 30, k
        for item in getattr(props[k], "enum_items", []):
            assert len(item.description) > 10, (k, item.identifier)
    for cls in ops_scene.CLASSES:
        assert cls.__doc__ and len(cls.__doc__.strip()) > 30, cls.__name__
    looks = {ops_scene.FRESING_OT_light_look.description(bpy.context, type("P", (), {"look": k})())
             for k in studio.LOOKS}
    assert len(looks) == len(studio.LOOKS) and all(len(t) > 40 for t in looks)
    views = {ops_main.FRESING_OT_camera_add.description(bpy.context, type("P", (), {"view": k})())
             for k in list(cameras.VIEWS) + ["VIEW"]}
    assert len(views) == len(cameras.VIEWS) + 1


def test_pictures_folder_is_asked_once():
    assert hasattr(render.pictures_dir, "cache_info")
    render.pictures_dir()
    render.pictures_dir()
    assert render.pictures_dir.cache_info().hits >= 1


def test_scenes_and_templates_from_before_the_weather_are_sunny(scene):
    """A saved scene or template made before task 0017 has no weather: it shows a sunny sky, whatever
    the weather is now (review finding)."""
    import json
    from fresing_render.blender import ops_main
    s = scene.fresing
    s.background = "SKY"
    shot = states.save_shot(scene, "Old sunny")
    old = json.loads(shot.world)
    del old["sky_weather"]
    shot.world = json.dumps(old)
    t = ops_main._template_from_scene(scene)
    del t.background["sky_weather"]
    bpy.ops.fresing.light_look(look="OVERCAST")
    states.apply_shot(scene, "Old sunny")
    assert s.sky_weather == "SUN"
    bpy.ops.fresing.light_look(look="OVERCAST")
    ops_main.apply_template(scene, t)
    assert s.sky_weather == "SUN"


def test_a_copied_camera_gets_its_own_sharp_spot(crane):
    """Shift+D copies a camera with its sharp-spot marker: picking or clearing a spot on one must not
    move or delete the other's (review finding)."""
    cam = crane.camera
    part = next(build.iter_parts(crane))
    ob, loc = _click(crane, cam, part)
    cameras.set_focus(cam, crane, ob, loc)
    copy = cam.copy()
    copy.data = cam.data.copy()
    cameras.collection(crane).objects.link(copy)
    shared = cameras.focus_marker(copy)
    assert shared is cameras.focus_marker(cam)
    crane.camera = copy
    cameras.set_focus(copy, crane, ob, loc + Vector((0.0, 0.0, 0.05)))
    assert cameras.focus_marker(copy) is not shared and cameras.focus_marker(cam) is shared
    assert (shared.matrix_world.translation - loc).length < 1e-5
    # back to sharing, then clearing one keeps the other's marker
    copy.data.dof.focus_object = shared
    cameras.clear_focus(copy, crane)
    assert cameras.focus_marker(cam) is shared and shared.name in bpy.data.objects


def test_turntable_keeps_a_scene_of_your_own_and_drops_old_jobs(crane):
    from fresing_render.blender import queue
    s = crane.fresing
    states.save_shot(crane, "Turntable")              # the user's own scene with that name
    mine = s.shots["Turntable"].world
    a = turntable.make(crane)["animation"]
    assert a.start_shot != "Turntable" and s.shots[a.start_shot].get(turntable.TAG)
    assert s.shots["Turntable"].world == mine
    assert turntable.make(crane)["shot"].name == a.start_shot           # made again: the same scene
    for status in ("STOPPED", "FAILED", "DONE"):
        queue.add_job(crane, "ANIMATION", animation=a.name).status = status
    turntable.drop_unfinished_jobs(crane, a)
    assert [j.status for j in s.queue] == ["DONE"]
