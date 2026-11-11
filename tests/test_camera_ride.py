"""Camera steps that ride along a part, fly a path or keep a part in the middle (task 0087)."""

import json
import math
import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from bpy_extras.object_utils import world_to_camera_view  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, camera_path, cameras, joints  # noqa: E402
from fresing_render.core import camera_path as P  # noqa: E402

HERE = os.path.dirname(__file__)
CRANE_A = os.path.join(HERE, "data", "test_crane_a.step")
GOLDEN = os.path.join(HERE, "data", "camera_keys_0087.json")
PIVOT = Vector((0.1, 0.3, 0.4))


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
    assert bpy.ops.fresing.import_step(filepath=CRANE_A, quality="draft") == {"FINISHED"}
    return sc


def ob(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def boom(sc, axis=(0.0, 0.0, 1.0)):
    return joints.create(sc, "ROTATE", [ob(sc, "BOOM.ASM")], PIVOT, Vector(axis), ref=ob(sc, "BOOM.PIN"))


def anim_with_turn(sc, j, deg=80.0, dur=2.0):
    a = sc.fresing.animations.add()
    a.name = "Ride"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", j.name, 0.0, dur, "SMOOTH"
    b.use_from, b.to_angle = True, math.radians(deg)
    return a


def cam_step(a, mode, start=0.0, dur=2.0, **kw):
    b = a.blocks.add()
    b.kind, b.camera_mode, b.start, b.duration = "CAMERA", mode, start, dur
    for k, v in kw.items():
        setattr(b, k, v)
    return b


def pick(b, o, aim=False):
    uid, name = o.get(build.PROP_UID), o.get(build.PROP_NAME)
    if aim:
        b.aim_uid, b.aim_name = uid, name
    else:
        b.target_uid, b.target_name = uid, name


def at(sc, f):
    sc.frame_set(f)
    return sc.camera.matrix_world.copy()


def deg_between(a, b):
    return camera_path.angle_between(a, b)


def start_camera(sc):
    c = cameras.add_camera(sc, "ISO", name="Start")
    sc.camera = c
    bpy.context.view_layer.update()
    return c


# ---------------------------------------------------------------------------
# the path maths (no Blender)
# ---------------------------------------------------------------------------

def test_path_goes_through_its_points_and_measures_its_length():
    pts = [(0, 0, 0), (1, 0, 0), (2, 1, 0.5), (2, 3, 1), (2, 3, 1)]
    p = P.Path(pts)
    assert len(p.points) == 4                         # the repeated point is one point
    for s, q in zip(p.at_point, p.points):
        assert np.linalg.norm(p.point(s) - q) < 1e-9
    assert p.length > 1 + math.hypot(1, 1) + 2       # longer than the straight lines between them... almost
    with pytest.raises(ValueError):
        P.Path([(1, 1, 1), (1, 1, 1)])


def test_ramped_speed_is_even_between_the_ramps():
    up, down = 0.2, 0.3
    ps = np.linspace(0, 1, 1001)
    d = np.array([P.ramped(p, up, down) for p in ps])
    assert d[0] == 0 and abs(d[-1] - 1) < 1e-12 and np.all(np.diff(d) >= 0)
    v = np.diff(d)
    mid = v[(ps[1:] > up + 0.01) & (ps[1:] < 1 - down - 0.01)]
    assert mid.max() / mid.min() < 1.0001
    assert v[0] < mid.min() / 10 and v[-1] < mid.min() / 10         # slow start and stop
    assert P.ramp_shares("LINEAR", 1.0, 4.0) == (0.0, 0.0)
    assert P.ramp_shares("SMOOTH", 1.0, 4.0) == (0.25, 0.25)
    assert P.ramp_shares("EASE_IN", 3.0, 4.0) == (0.75, 0.0)


def test_locate_finds_the_distance_along_the_path():
    p = P.Path([(0, 0, 0), (1, 0, 0), (1, 1, 0)])
    for s in (0.0, 0.3, 0.77, 1.2, p.length):
        assert abs(p.locate(p.point(s)) - s) < 1e-9


def test_heading_of_a_turn():
    m = np.array(Matrix.Rotation(0.7, 3, "Z") @ Matrix.Rotation(0.2, 3, "X"))
    assert abs(P.heading(m) - 0.7) < 1e-6          # (mathutils keeps 32-bit numbers)


# ---------------------------------------------------------------------------
# Ride along
# ---------------------------------------------------------------------------

def test_riding_camera_is_the_part_times_the_start_offset(scene):
    j = boom(scene)
    start_camera(scene)
    a = anim_with_turn(scene, j)
    b = cam_step(a, "RIDE", 0.0, 2.0, cam_blend=0.0)
    part = ob(scene, "BOOM")
    pick(b, part)
    c0 = scene.camera.matrix_world.copy()
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    scene.frame_set(1)
    offset = part.matrix_world.inverted() @ c0
    worst_mm = worst_deg = 0.0
    for f in range(1, info["frames"] + 1, 3):
        cam = at(scene, f)
        want = part.matrix_world @ offset
        worst_mm = max(worst_mm, (cam.translation - want.translation).length * 1000)
        worst_deg = max(worst_deg, deg_between(cam, want))
    assert worst_mm < 0.01 and worst_deg < 0.01, (worst_mm, worst_deg)
    # it really moved with the boom
    assert (at(scene, 1).translation - at(scene, 51).translation).length > 0.5


def test_keep_level_stays_upright_on_a_tilting_part(scene):
    j = boom(scene, axis=(1.0, 0.0, 0.0))             # the boom lifts: the part tilts
    start_camera(scene)
    a = anim_with_turn(scene, j, deg=30.0)
    b = cam_step(a, "RIDE", 0.0, 2.0, cam_blend=0.0, ride_level=True)
    part = ob(scene, "BOOM")
    pick(b, part)
    c0 = scene.camera.matrix_world.copy()
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    scene.frame_set(1)
    offset = part.matrix_world.inverted() @ c0
    worst = worst_mm = 0.0
    for f in range(1, info["frames"] + 1, 2):
        cam = at(scene, f)
        worst = max(worst, deg_between(cam, c0))      # no turn at all: the lift is a pure tilt
        worst_mm = max(worst_mm, (cam.translation - (part.matrix_world @ offset).translation).length * 1000)
    assert worst < 0.01, worst
    assert worst_mm < 0.01, worst_mm                   # it still rides along
    # without Keep level the camera tilts with the boom
    b.ride_level = False
    animation.bake(scene, a)
    assert deg_between(at(scene, info["frames"]), c0) > 25


def test_keep_level_follows_the_heading(scene):
    j = boom(scene)
    start_camera(scene)
    a = anim_with_turn(scene, j, deg=50.0)
    b = cam_step(a, "RIDE", 0.0, 2.0, cam_blend=0.0, ride_level=True)
    pick(b, ob(scene, "BOOM"))
    c0 = scene.camera.matrix_world.copy()
    animation.bake(scene, a)
    end = at(scene, 51)
    want = Matrix.Rotation(math.radians(50), 4, "Z").to_3x3() @ c0.to_3x3()
    assert deg_between(end, want.to_4x4()) < 0.01
    up = end.to_3x3() @ Vector((0, 1, 0))
    up0 = c0.to_3x3() @ Vector((0, 1, 0))
    assert abs(math.degrees(up.angle(Vector((0, 0, 1)))) - math.degrees(up0.angle(Vector((0, 0, 1))))) < 0.01


def test_ride_from_a_saved_camera_blends_in_without_a_jump(scene):
    j = boom(scene)
    start = start_camera(scene)
    seat = cameras.add_camera(scene, "TOP", name="On the boom")
    scene.camera = start                              # (a new camera becomes the scene's camera)
    bpy.context.view_layer.update()
    a = anim_with_turn(scene, j, deg=60.0, dur=3.0)
    cam_step(a, "ORBIT", 0.0, 1.0, orbit_angle=math.radians(30), easing="LINEAR")
    b = cam_step(a, "RIDE", 1.0, 2.0, cam_blend=1.0, ride_camera=seat)
    pick(b, ob(scene, "BOOM"))
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    f0 = animation.frame_of(a, 1.0)
    pos = [at(scene, f).translation.copy() for f in range(1, info["frames"] + 1)]
    steps = [(pos[i + 1] - pos[i]).length for i in range(len(pos) - 1)]
    assert (pos[f0 - 1] - pos[f0 - 2]).length == pytest.approx(steps[f0 - 3], rel=0.2)   # the orbit's pace
    # the frame the ride starts is exactly where the orbit ended (place and view): no jump
    first = at(scene, f0)
    b.enabled = False
    scene.frame_set(1)                                # (an orbit's centre is read on the frame shown at Build)
    animation.bake(scene, a)
    orbit = at(scene, f0)                             # where the orbit ends without the ride
    b.enabled = True
    scene.frame_set(1)
    animation.bake(scene, a)
    assert (first.translation - orbit.translation).length < 1e-5 and deg_between(first, orbit) < 1e-3
    turns = [deg_between(at(scene, f), at(scene, f + 1)) for f in range(1, info["frames"])]
    assert max(steps) < 6 * (sum(steps) / len(steps)), steps
    assert max(turns) < 6 * (sum(turns) / len(turns)), turns
    # after the blend it rides exactly on the boom, in the saved camera's place on it
    part = ob(scene, "BOOM")
    scene.frame_set(1)
    offset = part.matrix_world.inverted() @ seat.matrix_world
    for f in (f0 + 30, info["frames"]):
        cam = at(scene, f)
        assert (cam.translation - (part.matrix_world @ offset).translation).length < 1e-5


# ---------------------------------------------------------------------------
# Fly a path
# ---------------------------------------------------------------------------

PTS = [(2.0, -2.0, 1.5), (2.5, 0.5, 1.2), (1.5, 2.5, 1.0), (-1.0, 2.0, 1.4)]


def test_path_start_end_through_points_and_even_speed(scene):
    start_camera(scene)
    a = scene.fresing.animations.add()
    b = cam_step(a, "PATH", 0.0, 4.0, easing="LINEAR", path_from_here=False, cam_blend=0.0, path_look="MODEL")
    for p in PTS:
        b.path_points.add().co = p
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    n = info["frames"]
    f1 = animation.frame_of(a, 4.0)
    pos = np.array([tuple(at(scene, f).translation) for f in range(1, f1 + 1)])
    assert np.linalg.norm(pos[0] - PTS[0]) < 1e-5 and np.linalg.norm(pos[-1] - PTS[-1]) < 1e-5
    for p in PTS[1:-1]:                     # every point is passed (between two frames)
        assert np.min(np.linalg.norm(pos - p, axis=1)) < 0.06
    along = np.array([P.Path(PTS).locate(p) for p in pos])        # speed measured along the path
    step = np.diff(along)
    assert step.max() / step.min() < 1.02, (step.min(), step.max())
    # it looks at the model all the way
    centre = (Vector(scene.fresing.bounds_min) + Vector(scene.fresing.bounds_max)) / 2
    for f in (1, n // 2, f1):
        m = at(scene, f)
        assert tuple(world_to_camera_view(scene, scene.camera, centre).xy) == pytest.approx((0.5, 0.5), abs=1e-3)
        assert m is not None


def test_path_with_ramps_is_even_in_the_middle_and_starts_where_the_camera_is(scene):
    c = start_camera(scene)
    a = scene.fresing.animations.add()
    b = cam_step(a, "PATH", 0.0, 4.0, easing="SMOOTH", ramp=0.8, path_look="AHEAD")
    for p in PTS:
        b.path_points.add().co = p
    c0 = c.matrix_world.translation.copy()
    animation.bake(scene, a)
    f1 = animation.frame_of(a, 4.0)
    pos = np.array([tuple(at(scene, f).translation) for f in range(1, f1 + 1)])
    assert np.linalg.norm(pos[0] - np.array(c0)) < 1e-5          # no jump: it starts where the camera was
    assert np.linalg.norm(pos[-1] - PTS[-1]) < 1e-5
    path = P.Path([tuple(c0)] + PTS)
    step = np.diff([path.locate(p) for p in pos])
    ramp_frames = int(0.8 * animation.fps_of(a)) + 2
    mid = step[ramp_frames:-ramp_frames]
    assert mid.max() / mid.min() < 1.02
    assert step[0] < mid.min() / 3 and step[-1] < mid.min() / 3
    # looking ahead: the view points along the way it flies
    m = at(scene, f1 // 2)
    fwd = m.to_3x3() @ Vector((0, 0, -1))
    way = Vector(pos[f1 // 2] - pos[f1 // 2 - 2])
    assert math.degrees(fwd.angle(way)) < 5


def test_path_from_saved_cameras_and_shown_only_in_the_view(scene):
    start_camera(scene)
    for v in ("FRONT", "SIDE", "TOP"):
        cameras.add_camera(scene, v, name=v)
    scene.camera = bpy.data.objects["Start"]
    bpy.context.view_layer.update()
    a = scene.fresing.animations.add()
    scene.fresing.animations_index = len(scene.fresing.animations) - 1
    b = cam_step(a, "PATH", 0.0, 3.0)
    a.blocks_index = len(a.blocks) - 1
    assert bpy.ops.fresing.path_from_cameras() == {"FINISHED"}
    saved = cameras.fr_cameras(scene)               # (the import made one too)
    assert len(b.path_points) == len(saved) == 5
    k = saved.index(bpy.data.objects["FRONT"])
    assert tuple(b.path_points[k].co) == pytest.approx(tuple(bpy.data.objects["FRONT"].matrix_world.translation))
    curve = b.path_obj
    assert curve is not None and curve.hide_render and curve.type == "CURVE"
    assert bpy.ops.fresing.path_remove_point() == {"FINISHED"}
    assert len(b.path_points) == 4
    assert bpy.ops.fresing.path_clear() == {"FINISHED"}
    assert len(b.path_points) == 0 and b.path_obj is None
    assert not [o for o in bpy.data.objects if o.get(camera_path.PROP_PATH)]


# ---------------------------------------------------------------------------
# Keep in middle
# ---------------------------------------------------------------------------

def test_keep_in_middle_holds_the_part_in_the_picture_middle(scene):
    j = boom(scene)
    start_camera(scene)
    a = anim_with_turn(scene, j, deg=90.0)
    b = cam_step(a, "AIM", 0.0, 2.0, cam_blend=0.0)
    part = ob(scene, "BOOM")
    pick(b, part, aim=True)
    cam_loc = scene.camera.matrix_world.translation.copy()
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    worst = 0.0
    for f in range(1, info["frames"] + 1, 2):
        scene.frame_set(f)
        mid = camera_path._middle(part)
        uv = world_to_camera_view(scene, scene.camera, mid)
        worst = max(worst, abs(uv.x - 0.5), abs(uv.y - 0.5))
        assert (scene.camera.matrix_world.translation - cam_loc).length < 1e-5     # it stays where it is
        up = scene.camera.matrix_world.to_3x3() @ Vector((1, 0, 0))
        assert abs(up.z) < 1e-5                                                    # upright: no roll
    assert worst < 0.01, worst


def test_ride_and_look_at_another_part(scene):
    j = boom(scene)
    start_camera(scene)
    a = anim_with_turn(scene, j, deg=60.0)
    b = cam_step(a, "RIDE", 0.0, 2.0, cam_blend=0.0, ride_look="PART")
    pick(b, ob(scene, "BOOM"))
    pick(b, ob(scene, "TROLLEY"), aim=True)
    info = animation.bake(scene, a)
    assert not info["warnings"], info
    for f in (1, 26, 51):
        scene.frame_set(f)
        uv = world_to_camera_view(scene, scene.camera, camera_path._middle(ob(scene, "TROLLEY")))
        assert tuple(uv.xy) == pytest.approx((0.5, 0.5), abs=0.01)


def test_focus_follows_the_watched_part(scene):
    j = boom(scene)
    c = start_camera(scene)
    cameras.set_blur(c, scene, "LITTLE")
    a = anim_with_turn(scene, j, deg=90.0)
    b = cam_step(a, "AIM", 0.0, 2.0, cam_blend=0.0)
    part = ob(scene, "BOOM")
    pick(b, part, aim=True)
    animation.bake(scene, a)
    for f in (1, 30, 51):
        scene.frame_set(f)
        want = (camera_path._middle(part) - scene.camera.matrix_world.translation).length
        assert scene.camera.data.dof.focus_distance == pytest.approx(want, abs=1e-3)


def test_missing_targets_warn(scene):
    start_camera(scene)
    a = scene.fresing.animations.add()
    cam_step(a, "RIDE", 0.0, 1.0)
    cam_step(a, "AIM", 1.0, 1.0)
    cam_step(a, "PATH", 2.0, 1.0, path_from_here=False)
    info = animation.bake(scene, a)
    w = " ".join(info["warnings"])
    assert "pick the part to ride on" in w and "pick the part to keep in the middle" in w and "the path needs" in w


# ---------------------------------------------------------------------------
# works with the rest
# ---------------------------------------------------------------------------

def _rides(scene):
    j = boom(scene)
    start_camera(scene)
    a = anim_with_turn(scene, j, deg=70.0, dur=3.0)
    b = cam_step(a, "RIDE", 0.0, 1.5, cam_blend=0.5, ride_level=True)
    pick(b, ob(scene, "BOOM"))
    p = cam_step(a, "PATH", 1.5, 1.5, path_look="PART")
    pick(p, ob(scene, "TROLLEY"), aim=True)
    for q in PTS[:2]:
        p.path_points.add().co = q
    return a


def _track(scene, frames):
    return [at(scene, f) for f in frames]


def test_no_drivers_keys_only(scene):
    a = _rides(scene)
    animation.bake(scene, a)
    cam = scene.camera
    assert cam.get("fr_anim_camera")
    for idb in (cam, cam.data):
        ad = idb.animation_data
        assert ad is None or len(ad.drivers) == 0           # plays with scripts off: plain keys only


def test_save_reopen_and_build_again_like_the_queue(scene, tmp_path):
    a = _rides(scene)
    info = animation.bake(scene, a)
    frames = list(range(1, info["frames"] + 1, 4))
    before = _track(scene, frames)
    scene.frame_set(37)                                     # saved on another frame than 1
    path = str(tmp_path / "ride.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    a = sc.fresing.animations["Ride"]
    assert [b.camera_mode for b in a.blocks if b.kind == "CAMERA"] == ["RIDE", "PATH"]
    assert len(a.blocks[2].path_points) == 2 and a.blocks[1].ride_level
    for m0, m1 in zip(before, _track(sc, frames)):         # as saved
        assert (m0.translation - m1.translation).length < 1e-6
    info2 = animation.bake(sc, a)                           # what the render queue does in its copy
    assert not info2["warnings"]
    for m0, m1 in zip(before, _track(sc, frames)):
        assert (m0.translation - m1.translation).length < 1e-6 and deg_between(m0, m1) < 1e-3


def test_old_camera_steps_keys_unchanged(scene):
    """Cut, Move to and Orbit give exactly the keys they gave before task 0087 (tests/camera_golden_0087.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("golden", os.path.join(HERE, "camera_golden_0087.py"))
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc, a = g.old_steps_scene()
    info = animation.bake(sc, a)
    assert not info["warnings"]
    with open(GOLDEN) as fh:
        want = json.load(fh)
    got = g.keys(sc)
    assert sorted(got) == sorted(want)
    for k in want:
        assert len(got[k]) == len(want[k]), k
        for (f0, v0), (f1, v1) in zip(want[k], got[k]):
            assert f0 == f1 and abs(v0 - v1) < 1e-6, (k, f0, v0, v1)


def test_step_labels():
    class B:
        kind, camera_mode, name = "CAMERA", "RIDE", ""
        target_name, aim_name, path_points = "BOOM", "HOOK", [1, 2, 3]
    b = B()
    assert animation.block_label(b) == "Ride on BOOM"
    b.camera_mode = "PATH"
    assert animation.block_label(b) == "Fly a path"
    b.camera_mode = "AIM"
    assert animation.block_label(b) == "Watch HOOK"
