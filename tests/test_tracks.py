"""Task 0079: tracks and belts on the test model (tests/data/test_tracks.step, tools/make_test_tracks.py).

Blender as a Python module. Positions are read from the evaluated meshes (what the Geometry Nodes modifiers draw),
numbers from the maker (mm there, metres here)."""

import math
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, tracks  # noqa: E402

MODEL = os.path.join(HERE, "data", "test_tracks.step")


@pytest.fixture(scope="module")
def made(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path_factory.mktemp("tracks"))
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal") == {"FINISHED"}
    out = tracks.set_up_test_model(sc)
    yield out
    fresing_render.unregister()


def _sc():
    return bpy.context.scene


def update():
    bpy.context.view_layer.update()
    bpy.context.view_layer.update()


def cable_joint():
    sc = _sc()
    return joints.find(sc, paths.find(sc, tracks.TEST_CABLE).joint)


def pose(cable=None, lift=None, belt=None):
    sc = _sc()
    if cable is not None:
        joints.set_value(cable_joint(), cable)
    if lift is not None:
        joints.set_value(joints.find(sc, tracks.TEST_LIFT), lift, use_limits=False)
    if belt is not None:
        joints.set_value(joints.find(sc, tracks.find(sc, "Belt").joint), belt)
    update()


def evaluated(ob) -> np.ndarray:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
    finally:
        ev.to_mesh_clear()
    return co.reshape(-1, 3).astype(float) @ np.array(ob.matrix_world)[:3, :3].T + np.array(ob.matrix_world)[:3, 3]


def loop_now(it):
    """The loop's points (world) as the hidden table has them, carried by the carrier now."""
    A, _X, _Z = tracks.table_of(_sc(), it)
    C = np.array(it.carrier.matrix_world)
    return A @ C[:3, :3].T + C[:3, 3]


def dist_to_loop(points, loop):
    """Distance of each point to the closed polyline ``loop``."""
    a, b = loop, np.roll(loop, -1, axis=0)
    seg = b - a
    out = []
    for p in np.atleast_2d(points):
        t = np.clip(((p - a) * seg).sum(1) / (seg * seg).sum(1), 0.0, 1.0)
        out.append(np.linalg.norm(a + seg * t[:, None] - p, axis=1).min())
    return np.array(out)


def link_hinges_now(it):
    sc = _sc()
    out = []
    for ob in tracks.parts_of(sc, it):
        if ob.get(tracks.ROLE) == "link":
            out.append(tracks.hinge_world(sc, it, ob))
    return np.array(out)


def check_on_loop(it, what):
    h = link_hinges_now(it)
    loop = loop_now(it)
    d = dist_to_loop(h.reshape(-1, 3), loop)
    chord = np.abs(np.linalg.norm(h[:, 1] - h[:, 0], axis=1) - it.pitch)
    assert d.max() < 1e-4, (it.name, what, d.max())
    assert chord.max() < 5e-5, (it.name, what, chord.max())
    return d.max(), chord.max()


def test_set_up(made):
    sc = _sc()
    names = [it.name for it in tracks.items(sc)]
    assert names == list(tracks.TEST_TRACKS)
    bot, top, belt = (tracks.find(sc, n) for n in tracks.TEST_TRACKS)
    for it, links, parts in ((bot, 22, 44), (top, 22, 44), (belt, 58, 58)):
        assert (it.links, it.parts) == (links, parts) and tracks.status(sc, it)[1] == "OK", tracks.status(sc, it)
        assert len(tracks.parts_of(sc, it)) == parts
    assert bot.joint == top.joint == cable_joint().name           # the cable runs between them: their speed
    assert belt.joint == "Track Belt" and belt.made_joint
    assert bot.pitch == pytest.approx(0.1) and belt.pitch == pytest.approx(0.04)
    assert bot.length == pytest.approx(2.2, abs=1e-6)             # 22 links of 100 mm (kept in 32 bits)
    wr = {w.name: w for w in bot.wheels}
    assert wr["DRIVE SPROCKET"].wrapped and not wr["SUPPORT ROLLER"].wrapped
    assert wr["DRIVE SPROCKET"].radius == pytest.approx(0.0161803 * 10, abs=1e-6)
    assert wr["SUPPORT ROLLER"].radius == pytest.approx(0.06, abs=1e-6)


def test_hinges_on_the_loop_live(made):
    sc = _sc()
    for v in (0.0, 0.0371, 0.73, -1.9, 37.3):
        pose(cable=v, belt=v * 0.7)
        for it in tracks.items(sc):
            check_on_loop(it, v)
    pose(cable=0.0, belt=0.0)


def test_parts_stay_as_drawn_at_zero(made):
    sc = _sc()
    pose(cable=0.0, lift=0.0, belt=0.0)
    for it in tracks.items(sc):
        for ob in tracks.parts_of(sc, it)[::5]:
            me = ob.data
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            W = np.array(ob.matrix_world)
            cad = co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3]
            assert np.abs(evaluated(ob) - cad).max() < 2e-5, ob.name


def test_pads_on_the_gripping_run_move_with_the_cable_over_100_m(made):
    """Over a 100 m run the gripping pads keep the cable's speed: 5 mm of cable at 0, 25, 50, 75, 100 m moves the pad
    in the middle of the gripping run 5 mm along +X (the cable's way), within 0.1 %."""
    sc = _sc()
    for it in (tracks.find(sc, "Bottom track"), tracks.find(sc, "Top track")):
        for v in (0.0, 25.0, 50.0, 75.0, 100.0):
            pose(cable=v)
            pads = [o for o in tracks.parts_of(sc, it) if o.get(build.PROP_NAME) == "TRACK PAD"]
            mids = {o.name: evaluated(o).mean(axis=0) for o in pads}
            name = min(mids, key=lambda n: abs(mids[n][0]) + (0 if abs(mids[n][2] - 1.0) < 0.06 else 9))
            pose(cable=v + 0.005)
            moved = evaluated(bpy.data.objects[name]).mean(axis=0) - mids[name]
            assert moved[0] == pytest.approx(0.005, rel=1e-3), (it.name, v, moved)
            assert abs(moved[1]) < 1e-6 and abs(moved[2]) < 1e-6
    pose(cable=0.0)


def test_sprocket_notches_stay_on_the_pins(made):
    """A sprocket turns one tooth per link: after any length of cable, every pin on its wrap sits in a notch."""
    sc = _sc()
    it = tracks.find(sc, "Bottom track")
    spr = next(w.part for w in it.wheels if w.name == "DRIVE SPROCKET")
    axes = tracks._axes(spr)
    centre_local, d, _r = tracks.wheel_axis(spr)
    notches = axes[np.abs(np.linalg.norm(np.cross(axes[:, :3] - centre_local, d), axis=1) - 0.0) > 0.05]
    assert len(notches) == 10
    for v in (0.0, 0.05, 0.731, 37.3):
        pose(cable=v)
        W = np.array(spr.matrix_world)
        pts = notches[:, :3] @ W[:3, :3].T + W[:3, 3]
        h = link_hinges_now(it).reshape(-1, 3)
        c = centre_local @ W[:3, :3].T + W[:3, 3]
        on_wrap = h[np.abs(np.linalg.norm((h - c)[:, [0, 2]], axis=1) - 0.1618034) < 1e-4]
        assert len(on_wrap) >= 5
        for p in on_wrap:
            gap = np.linalg.norm((pts - p)[:, [0, 2]], axis=1).min()
            assert gap < 5e-4, (v, gap)
    pose(cable=0.0)


def test_the_top_track_lifts_and_squeezes_with_its_pads_running(made):
    sc = _sc()
    top = tracks.find(sc, "Top track")
    pose(cable=0.0, lift=0.0)
    before = {o.name: evaluated(o).mean(axis=0) for o in tracks.parts_of(sc, top)[::7]}
    pose(lift=0.15)
    for name, p in before.items():
        assert evaluated(bpy.data.objects[name]).mean(axis=0) - p == pytest.approx([0, 0, 0.15], abs=1e-6)
    pose(cable=0.42, lift=0.15)
    check_on_loop(top, "lifted")
    pose(lift=-0.002)
    check_on_loop(top, "squeezed")
    pose(cable=0.0, lift=0.0)


def test_drivers_need_no_python(made):
    """One driver per track (on its run object), a simple expression; the parts have none."""
    sc = _sc()
    for it in tracks.items(sc):
        fcs = list(it.run.animation_data.drivers)
        assert len(fcs) == 1 and fcs[0].driver.is_simple_expression, it.name
        for ob in tracks.parts_of(sc, it):
            assert ob.animation_data is None or not len(ob.animation_data.drivers), ob.name
    assert joints.couplings_simple(sc)


def test_build_animation_frames_1_250_1000(made):
    """A 50 s Run motor step at 10 m/min (1,250 frames): the hinges on the loop at frames 1, 250, 1,000, and the
    clash check leaves the track parts out."""
    from fresing_render.blender import clash
    sc = _sc()
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Long run", 0.0, "25"
    for it in (tracks.find(sc, "Bottom track"), tracks.find(sc, "Belt")):
        b = a.blocks.add()
        b.kind, b.joint, b.start, b.duration, b.easing = "MOTOR", it.joint, 0.0, 50.0, "LINEAR"
        b.speed_mmin = 10.0
    animation.bake(sc, a)
    for f in (1, 250, 1000):
        sc.frame_set(f)
        update()
        assert joints.get_value(cable_joint()) == pytest.approx((f - 1) / 25.0 * 10.0 / 60.0, abs=1e-4)
        for it in tracks.items(sc):
            check_on_loop(it, f)
    add, leave = tracks._clash_hook(sc)
    assert not add and len(leave) == 146
    assert all(fn in clash.HOOKS for fn in (tracks._clash_hook,))
    animation.clear_keys(sc)
    sc.fresing.animations.remove(len(sc.fresing.animations) - 1)
    sc.frame_set(1)
    pose(cable=0.0, belt=0.0)


def test_off_shows_the_cad_and_on_again(made):
    sc = _sc()
    it = tracks.find(sc, "Belt")
    pose(belt=0.3)
    ob = tracks.parts_of(sc, it)[3]
    moved = evaluated(ob)
    it.enabled = False
    update()
    me = ob.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    W = np.array(ob.matrix_world)
    assert np.abs(evaluated(ob) - (co.reshape(-1, 3) @ W[:3, :3].T + W[:3, 3])).max() < 1e-6
    assert tracks.status(sc, it)[1] == "OFF"
    tracks.find(sc, "Belt").enabled = True
    update()
    assert np.abs(evaluated(ob) - moved).max() < 1e-6
    pose(belt=0.0)


def test_reverse_and_speed_from_a_wheel(made):
    sc = _sc()
    it = tracks.find(sc, "Belt")
    ob = tracks.parts_of(sc, it)[0]
    pose(belt=0.0)
    p0 = evaluated(ob).mean(axis=0)
    pose(belt=0.01)
    fwd = evaluated(ob).mean(axis=0) - p0
    assert tracks.travel_now(sc, it) == pytest.approx(0.01, abs=1e-6)
    it.reverse = True
    update()
    it = tracks.find(sc, "Belt")
    assert tracks.travel_now(sc, it) == pytest.approx(it.length - 0.01, abs=1e-6)
    back = evaluated(ob).mean(axis=0) - p0
    assert np.linalg.norm(fwd) > 0.009 and np.linalg.norm(back) > 0.009 and float(fwd @ back) < 0.0
    tracks.find(sc, "Belt").reverse = False
    # the belt run by pulley A's own turn: a turn of one radian moves the chain 1 / rate metres
    it = tracks.find(sc, "Belt")
    wa = next(w for w in it.wheels if w.name == "BELT PULLEY A")
    old = it.joint
    it.joint = wa.joint
    assert tracks.status(sc, tracks.find(sc, "Belt"))[1] == "OK"
    it = tracks.find(sc, "Belt")
    joints.set_value(joints.find(sc, wa.joint), 0.2)
    update()
    assert tracks.travel_now(sc, it) == pytest.approx((0.2 / abs(wa.rate)) % it.length, abs=1e-6) or \
        tracks.travel_now(sc, it) == pytest.approx((-0.2 / abs(wa.rate)) % it.length, abs=1e-6)
    check_on_loop(it, "by its pulley")
    joints.set_value(joints.find(sc, wa.joint), 0.0)
    it.joint = old
    pose(belt=0.0)


def test_refusals(made):
    sc = _sc()
    base = "TEST.TRACKS#1/BOTTOM TRACK.ASM#1/"

    def uid(u):
        return next(o for o in sc.objects if o.get(build.PROP_UID) == base + u)
    n = len(sc.fresing.tracks)
    with pytest.raises(tracks.TrackError, match="part of a track|twice|already"):
        tracks.add(sc, [uid("DRIVE SPROCKET#1"), uid("DRIVE SPROCKET#1")], uid("TRACK CHAIN LINK#1"))
    with pytest.raises(tracks.TrackError, match="hinge|already"):
        tracks.add(sc, [uid("DRIVE SPROCKET#1"), uid("IDLER SPROCKET#1")], uid("TRACK PAD#1"))
    with pytest.raises(tracks.TrackError, match="2 wheels"):
        tracks.add(sc, [uid("DRIVE SPROCKET#1")], uid("TRACK CHAIN LINK#1"))
    assert len(sc.fresing.tracks) == n


def test_speed_from_joint_in_add_cable(made):
    """0078's follow-up: Add cable can take an existing slide joint as its speed."""
    sc = _sc()
    root = build.model_roots(sc)[0]
    with joints._batch(sc):
        j = joints.create(sc, "SLIDE", [], root.matrix_world.translation.copy(), root.matrix_world.to_3x3().col[0],
                          name="Spare speed", base=root, allow_empty=True)
    sc.fresing.cable_speed = j.name
    it = paths.add_cable(sc, "Second", joint="Spare speed")
    assert it.joint == "Spare speed" and not it.made_joint
    paths.remove(sc, paths.index_of(sc, it))
    assert joints.find(sc, "Spare speed") is not None            # (a joint the user made stays)
    with pytest.raises(paths.PathError, match="rotate joint"):
        paths.add_cable(sc, "Third", joint=tracks.find(sc, "Belt").wheels[0].joint)


def test_model_update_keeps_the_tracks(made):
    sc = _sc()
    tracks.find(sc, "Belt").reverse = True
    old = {o.name for o in tracks.track_parts(sc)}
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="normal", update_root=root.name) == {"FINISHED"}
    update()
    assert [i.name for i in tracks.items(sc)] == list(tracks.TEST_TRACKS)
    assert not (old & {o.name for o in tracks.track_parts(sc)}) and len(tracks.track_parts(sc)) == 146
    assert tracks.find(sc, "Belt").reverse and tracks.find(sc, "Belt").joint == "Track Belt"
    assert tracks.find(sc, "Bottom track").joint == cable_joint().name
    pose(cable=0.37, belt=0.2)
    for it in tracks.items(sc):
        assert tracks.status(sc, it)[1] == "OK", tracks.status(sc, it)
        check_on_loop(it, "updated")
    pose(cable=0.0, belt=0.0)


def test_a_renamed_track_keeps_its_parts(made):
    sc = _sc()
    it = tracks.find(sc, "Belt")
    n = len(tracks.parts_of(sc, it))
    it.name = "Conveyor"
    it = tracks.find(sc, "Conveyor")
    assert len(tracks.parts_of(sc, it)) == n and tracks.status(sc, it)[1] == "OK"
    it.name = "Belt"


def test_remove_puts_the_parts_back(made):
    sc = _sc()
    it = tracks.find(sc, "Belt")
    parts = tracks.parts_of(sc, it)
    made_joints = [w.joint for w in it.wheels if w.made_joint] + [it.joint]
    assert len(made_joints) == 4 and all(joints.find(sc, n) is not None for n in made_joints)   # (also after the update)
    tracks.remove(sc, tracks.index_of(sc, it))
    assert all(tracks.MOD not in o.modifiers and tracks.TAG not in o for o in parts)
    assert all(joints.find(sc, n) is None for n in made_joints)
    assert [i.name for i in tracks.items(sc)] == ["Bottom track", "Top track"]
    assert all(joints.find(sc, w.joint) is not None for w in tracks.find(sc, "Bottom track").wheels)
