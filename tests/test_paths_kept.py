"""Task 0137: the cable set-up survives rewrites, renames, vessel changes and old projects (rows 2, 5, 7, 14, 16a of
bug hunt 0131, each row's proof as a test), in Blender (as a Python module).

Models: the swivel scene of tests/test_paths_swivel.py (made in the test) and tests/data/test_moving.step set up by
``paths.set_up_moving_model`` (the cable into the sea, let go at 9.2 s, the vessel sailing at 3 kn).
"""

import json
import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
MODEL = os.path.join(HERE, "data", "test_moving.step")

import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, flex, joints, paths, paths_sea, paths_swivel,  # noqa: E402
                                    vessel_motion)

import test_paths_swivel as sw  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("kept"))


def update(times=2):
    for _ in range(times):
        bpy.context.view_layer.update()


def moving_scene(folder, settle=None):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft") == {"FINISHED"}
    paths.set_up_moving_model(sc)
    if settle is not None:
        paths.find(sc, paths.MOVING_CABLE).sea_settle = settle
    return sc


def cable(sc):
    return paths.find(sc, paths.MOVING_CABLE)


def build_it(sc):
    return animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])["warnings"]


def sheave_index(it) -> int:
    return next(i for i, c in enumerate(it.contacts) if c.name == "SHEAVE")


# ---------------------------------------------------------------------------
# row 2: Swivel and Let go frame kept whenever the contact list is rewritten
# ---------------------------------------------------------------------------

def test_from_cad_again_keeps_swivel_and_let_go():
    sc = sw.make_scene()
    it = paths.find(sc, "Wire")
    it.contacts[0].let_go_frame = 40
    assert it.contacts[0].swivel == "Swivel"
    paths.read_cad(sc, it, sc.objects["WIRE"])
    it = paths.find(sc, "Wire")
    assert (it.contacts[0].swivel, it.contacts[0].let_go_frame) == ("Swivel", 40)
    it.contacts[0].user = True                  # a contact the user changed goes through the other branch of the merge
    paths.read_cad(sc, it, sc.objects["WIRE"])
    it = paths.find(sc, "Wire")
    assert (it.contacts[0].swivel, it.contacts[0].let_go_frame) == ("Swivel", 40)


def test_rows_and_snapshots_carry_swivel_and_let_go():
    """What Add contact (``_row_of`` -> ``_write_contact`` for every other contact) and a refused change
    (``_snapshot`` -> ``_restore``) do to the contacts."""
    sc = sw.make_scene()
    it = paths.find(sc, "Wire")
    it.contacts[0].let_go_frame = 40
    memo = {}
    rows = [paths._row_of(c, memo) for c in it.contacts]
    with paths._quiet(it):
        it.contacts.clear()
        for d in rows:
            paths._write_contact(it.contacts.add(), d, memo)
    it = paths.find(sc, "Wire")
    assert (it.contacts[0].swivel, it.contacts[0].let_go_frame) == ("Swivel", 40)
    snap = paths._snapshot(it)
    with paths._quiet(it.contacts[0]):
        it.contacts[0].swivel, it.contacts[0].let_go_frame = "", -1
    paths._restore(it, snap)
    it = paths.find(sc, "Wire")
    assert (it.contacts[0].swivel, it.contacts[0].let_go_frame) == ("Swivel", 40)


def test_a_model_update_keeps_the_let_go(folder):
    sc = moving_scene(folder)
    it = cable(sc)
    k = sheave_index(it)
    f0 = int(it.contacts[k].let_go_frame)
    assert f0 > 0
    root = build.model_roots(sc)[0]
    assert bpy.ops.fresing.import_step(filepath=MODEL, quality="draft", update_root=root.name) == {"FINISHED"}
    it = cable(sc)
    assert int(it.contacts[sheave_index(it)].let_go_frame) == f0
    warnings = build_it(sc)
    assert not [t for t in warnings if paths.MOVING_CABLE in t], warnings


# ---------------------------------------------------------------------------
# row 5: joint renames carried into the cable data
# ---------------------------------------------------------------------------

def test_renaming_the_swivel_and_the_sheaves_joint():
    sc = sw.make_scene()
    it = paths.find(sc, "Wire")
    turn = joints.find(sc, it.contacts[0].joint)
    joints.find(sc, "Swivel").name = "Head turn"
    turn.name = "Sheave turn"
    it = paths.find(sc, "Wire")
    assert it.contacts[0].swivel == "Head turn" and it.contacts[0].joint == "Sheave turn"
    speed = joints.find(sc, it.joint)
    speed.name = "Wire paid out"
    assert paths.find(sc, "Wire").joint == "Wire paid out"
    sw.set_side(sc, 2.0)                        # the head still turns to its wire
    assert sw.tilt(sc) < sw.TOL_DEG
    assert abs(joints.get_value(joints.find(sc, "Head turn"))) > 0.1


def test_renaming_the_leader_while_built():
    sc = sw.make_scene()
    joints.set_follows(sc, sw.swivel(sc), "Lead", ratio=1.0, offset_value=0.05)
    update()
    sw.bake(sc, sc.fresing.animations[sw.ANIM])
    assert paths_swivel.WAS in sw.swivel(sc).motion
    joints.find(sc, "Lead").name = "Leader"
    assert json.loads(sw.swivel(sc).motion[paths_swivel.WAS])["follows"] == "Leader"
    animation.clear_keys(sc)
    assert sw.swivel(sc).follows == "Leader"


# ---------------------------------------------------------------------------
# row 7: a built sea cable worked out again after a change of vessel or seabed motion
# ---------------------------------------------------------------------------

def _end_on_bed(sc, frames):
    out = []
    for f in frames:
        sc.frame_set(f)
        inv = np.linalg.inv(np.array(paths_sea.bed(sc).matrix_world))
        p = paths.shape_now(sc, cable(sc))[-1]
        out.append(inv[:3, :3] @ p + inv[:3, 3])
    return np.array(out)


def test_vessel_speed_after_build_works_the_cable_out_again(folder):
    sc = moving_scene(folder)
    build_it(sc)
    frames = [sc.frame_start, sc.frame_end // 2, sc.frame_end]
    sc.fresing.weather.vessel_speed = 6.0       # the user, after Build (the update callback's route)
    got = _end_on_bed(sc, frames)
    assert np.abs(got - got[0]).max() < 0.05, got        # the end lies still on the seabed: worked out for 6 kn
    animation.bake(sc, sc.fresing.animations[paths.MOVING_ANIMATION])
    want = _end_on_bed(sc, frames)
    assert np.abs(got - want).max() < 1e-3


def test_one_route_only_works_out_again_when_the_motion_changed(folder, monkeypatch):
    sc = moving_scene(folder)
    build_it(sc)
    calls = []
    monkeypatch.setattr(paths, "_bake", lambda scene: calls.append(scene.name) or [])
    vessel_motion.follow(sc, force=False)       # the surroundings checked, nothing changed
    assert calls == []
    sc.fresing.weather["vessel_speed"] = 5.0    # (no callback)
    vessel_motion.after_surroundings(sc)        # the sea built again (sea state, bow, preset …)
    assert calls == [sc.name]
    vessel_motion.follow(sc, force=False)
    assert calls == [sc.name]                   # remembered: once is enough
    assert sc[paths.MOTION_KEY] == vessel_motion.motion_key(sc)


# ---------------------------------------------------------------------------
# row 14: let-go sea cables of older projects stay where they were let go
# ---------------------------------------------------------------------------

def test_an_older_project_keeps_its_let_go_cable_still(folder, tmp_path):
    sc = moving_scene(folder)
    it = cable(sc)
    del it["sea_settle"]                        # as saved by 0.2.95 … 0.2.102: never set
    del sc[paths.SETTLE_STAMP]
    assert it.sea_settle == pytest.approx(4.0)
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    assert cable(sc).sea_settle == 0.0 and sc.get(paths.SETTLE_STAMP)
    cable(sc).sea_settle = 3.0                  # set by the user now: kept at the next opening
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert cable(bpy.context.scene).sea_settle == pytest.approx(3.0)


def test_versioning_leaves_set_values_and_cables_not_let_go(folder):
    sc = moving_scene(folder)
    it = cable(sc)
    del sc[paths.SETTLE_STAMP]
    assert paths.version_settle(sc) == 0        # set by the set-up (2 s): kept
    assert it.sea_settle == pytest.approx(paths.MOVING_SETTLE)
    del sc[paths.SETTLE_STAMP]
    del it["sea_settle"]
    for w in ("a", "b"):
        setattr(it, w + "_let_go_frame", -1)
    for c in it.contacts:
        c.let_go_frame = -1
    assert paths.version_settle(sc) == 0        # nothing let go: the default stays
    assert it.sea_settle == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# row 16a and 0136's guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("gap", [1, 2, 5])
def test_ramp_steps_with_changes_close_together(gap):
    F, k = 80, 30
    trend = 0.02 * np.arange(F)
    v = trend.copy()
    v[k:] += 0.5                                # the free length jumps twice, ``gap`` frames apart
    v[k + gap:] += 0.3
    hang = np.zeros(F, dtype=int)
    hang[k:] = 1
    hang[k + gap:] = 2
    out = paths.ramp_steps(v, hang, 10)

    def ramp(at, size):                         # each step spread over the 10 frames after it (smoothstep)
        t = np.clip((np.arange(F) - at + 1) / 10.0, 0.0, 1.0) * (np.arange(F) >= at)
        return size * t * t * (3.0 - 2.0 * t)
    want = trend + ramp(k, 0.5) + ramp(k + gap, 0.3)
    assert np.abs(out - want).max() < 1e-9, np.abs(out - want).max()


def test_follow_skips_a_bake_copy(folder, monkeypatch):
    sc = moving_scene(folder)
    calls = []
    monkeypatch.setattr(paths, "_live", lambda scene, force=False: calls.append(scene.name) or False)
    sc["fr_bake"] = True
    paths._follow(sc)
    assert calls == []
    del sc["fr_bake"]
    paths._follow(sc)
    assert calls == [sc.name]
