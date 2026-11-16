"""Task 0160, bug hunt 0147 row 2: renaming a drum's joint, its follower's joint, a track's speed joint or a drum's
cable keeps the drum, its level wind / arm and the track's pulleys turning after a model update and Build – with
exactly the values of the same set-up never renamed (in Blender as a Python module).

Models: tests/data/test_spool.step (``spool.set_up_test_model``: "Drum" with "Level wind", "Carousel" with
"Arm slew", the animation "Spooling") and tests/data/test_tracks.step (``tracks.set_up_test_model``: the track
"Belt" with its own speed joint "Track Belt" and three pulleys).
"""

import os

import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, joints, paths, spool, tracks  # noqa: E402

HERE = os.path.dirname(__file__)
SPOOL = os.path.join(HERE, "data", "test_spool.step")
TRACKS = os.path.join(HERE, "data", "test_tracks.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("renames"))


def _fresh(folder, model):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft") == {"FINISHED"}
    return sc


def _update_and_build(sc, model, anim):
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=model, quality="draft", update_root=root.name) == {"FINISHED"}
    out = animation.bake(sc, sc.fresing.animations[anim])
    sc.frame_set(sc.frame_end)
    bpy.context.view_layer.update()
    return out["warnings"]


def _spool_values(sc):
    out = {}
    for sp in sc.fresing.spools:
        j = joints.find(sc, sp.joint)
        out[sp.name] = (sp.enabled, None if j is None else round(joints.get_value(j), 6),
                        [None if joints.find(sc, f.joint) is None else round(joints.get_value(joints.find(sc, f.joint)),
                                                                              6) for f in sp.followers])
    return out


@pytest.fixture(scope="module")
def spool_ref(folder):
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    _update_and_build(sc, SPOOL, spool.TEST_ANIMATION)
    got = _spool_values(sc)
    assert abs(got["Drum"][1]) > 1.0 and abs(got["Drum"][2][0]) > 0.01, got      # the drum turns, the wind moves
    return got


def test_renamed_drum_and_follower_joints_keep_turning_after_a_model_update(folder, spool_ref):
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    drum, car = spool.find(sc, "Drum"), spool.find(sc, "Carousel")
    joints.find(sc, drum.joint).name = "Drum turns"
    joints.find(sc, drum.followers[0].joint).name = "Wind slide"
    joints.find(sc, car.followers[0].joint).name = "Arm swing"
    drum = spool.find(sc, "Drum")
    assert drum.joint == "Drum turns" and drum.followers[0].joint == "Wind slide"
    assert spool.find(sc, "Carousel").followers[0].joint == "Arm swing"
    warnings = _update_and_build(sc, SPOOL, spool.TEST_ANIMATION)
    assert not [w for w in warnings if "Drum" in w or "Carousel" in w], warnings
    got = _spool_values(sc)
    assert got["Drum"] == spool_ref["Drum"] and got["Carousel"] == spool_ref["Carousel"], (got, spool_ref)
    assert len([o for o in bpy.data.objects if o.name.startswith("FR spool")]) >= 2         # the rope objects stay


def test_a_renamed_cable_keeps_its_drum(folder, spool_ref):
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    drum = spool.find(sc, "Drum")
    it = paths.find(sc, drum.cable)
    made = [j.name for j in sc.fresing.joints if j.motion is not None and j.motion.get(paths.TAG) == it.name]
    it.name = "Main wire"
    assert spool.find(sc, "Drum").cable == "Main wire"
    assert all(joints.find(sc, n).motion.get(paths.TAG) == "Main wire" for n in made)
    assert spool.status(sc, spool.find(sc, "Drum"))[1] != "ERROR" if hasattr(spool, "status") else True
    _update_and_build(sc, SPOOL, spool.TEST_ANIMATION)
    got = _spool_values(sc)
    assert got["Drum"] == spool_ref["Drum"], (got, spool_ref)
    it = paths.find(sc, "Main wire")                    # renamed back: the drum follows again
    it.name = "Wire"
    assert spool.find(sc, "Drum").cable == "Wire"


def test_an_older_cable_without_its_name_kept_is_found_when_renamed(folder):
    """A cable of a scene from before 0.2.121 knows no ``name_was``; opening the file sets it (load_post), and a
    scene that skipped that (appended) still finds the one drum whose cable is gone."""
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    for c in sc.fresing.cables:
        c["name_was"] = ""
    paths.find(sc, spool.find(sc, "Drum").cable).name = "Main wire"
    assert spool.find(sc, "Drum").cable == "Main wire"
    path = os.path.join(folder, "old_names.blend")
    for c in sc.fresing.cables:
        c["name_was"] = ""
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert all(c.name_was == c.name for c in sc.fresing.cables)


def _track_values(sc):
    it = tracks.find(sc, "Belt")
    return it.joint, [round(joints.get_value(joints.find(sc, w.joint)), 6) for w in it.wheels]


def test_a_renamed_track_speed_joint_keeps_the_pulleys_turning(folder):
    sc = _fresh(folder, TRACKS)
    tracks.set_up_test_model(sc)
    _update_and_build(sc, TRACKS, tracks.TEST_ANIMATION)
    ref = _track_values(sc)
    assert all(abs(v) > 1.0 for v in ref[1]), ref

    sc = _fresh(folder, TRACKS)
    tracks.set_up_test_model(sc)
    before = {j.name for j in sc.fresing.joints}
    joints.find(sc, tracks.find(sc, "Belt").joint).name = "Belt speed"
    assert tracks.find(sc, "Belt").joint == "Belt speed"
    _update_and_build(sc, TRACKS, tracks.TEST_ANIMATION)
    got = _track_values(sc)
    assert got == ("Belt speed", ref[1]), (got, ref)
    assert {j.name for j in sc.fresing.joints} == (before - {ref[0]}) | {"Belt speed"}     # no new "Track Belt"


def test_a_renamed_wheel_joint_stays_the_tracks(folder):
    sc = _fresh(folder, TRACKS)
    tracks.set_up_test_model(sc)
    it = tracks.find(sc, "Belt")
    old = it.wheels[0].joint
    joints.find(sc, old).name = "Pulley A turns"
    assert tracks.find(sc, "Belt").wheels[0].joint == "Pulley A turns"
    assert tracks.status(sc, tracks.find(sc, "Belt"))[1] == "OK", tracks.status(sc, tracks.find(sc, "Belt"))


def test_a_new_cable_never_takes_over_a_drum_whose_cable_was_removed(folder):
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    drum = spool.find(sc, "Drum")
    gone = drum.cable
    paths.remove(sc, paths.index_of(sc, paths.find(sc, gone)))
    assert spool.find(sc, "Drum").cable == gone
    paths.add_cable(sc, "Hose line")
    assert spool.find(sc, "Drum").cable == gone


def test_a_cable_renamed_to_another_cables_name_gets_a_free_one(folder):
    sc = _fresh(folder, SPOOL)
    spool.set_up_test_model(sc)
    drum, car = spool.find(sc, "Drum").cable, spool.find(sc, "Carousel").cable
    paths.find(sc, car).name = drum
    names = [c.name for c in sc.fresing.cables]
    assert len(set(names)) == len(names) and f"{drum} 2" in names
    assert spool.find(sc, "Carousel").cable == f"{drum} 2" and spool.find(sc, "Drum").cable == drum
    paths.find(sc, f"{drum} 2").name = car
    assert spool.find(sc, "Carousel").cable == car and spool.find(sc, "Drum").cable == drum
