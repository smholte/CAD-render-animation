"""Task 0189 (bug hunt 0183, row 6): the cable into the sea on a web page without vessel motion. The export reads the
parts where they stand on a still sea; the cable was solved with the vessel moving, in its part's coordinates. Without
vessel motion on the page the laid cable dipped 0.78 m into the seabed or floated 0.85 m above it. Now its points on
the seabed lie where the app lays them and its top stays on the vessel at rest; with vessel motion on the page the
page's own motion puts it back, and the page has no switch to stop it (the cable would leave the seabed)."""

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, paths, paths_sea, surroundings, vessel_motion, web3d, web3d_env  # noqa: E402
from fresing_render.core import web3d as core, web3d_env as env, web3d_tubes as T  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SEA_STEP = os.path.join(HERE, "data", "test_sea.step")
KEYS = ("times", "lo", "step", "q", "n0", "s0", "pay_t", "pay", "trim_t", "trim", "trim_n0", "s", "slo", "sstep", "nq")


@pytest.fixture(scope="module", autouse=True)
def _unregister_at_end():
    yield
    try:
        fresing_render.unregister()
    except Exception:  # noqa: BLE001
        pass


def _make(sea_depth):
    try:                                        # the other fixture's registration (module-scoped, still alive)
        fresing_render.unregister()
    except Exception:  # noqa: BLE001
        pass
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    assert bpy.ops.fresing.import_step(filepath=SEA_STEP, quality="draft") == {"FINISHED"}
    scene = bpy.context.scene
    s = scene.fresing
    s.background, s.env_detail, s.sea_state, s.water_level = "SEA", "SIMPLE", "ROUGH", 2.0
    s.sea_depth = sea_depth
    s.vessel.enabled = True
    out = paths_sea.set_up_test_model(scene)
    info = animation.bake(scene, s.animations[out["animation"]])
    assert not info["warnings"], info["warnings"]
    assert vessel_motion.effective(scene)
    return scene, out


@pytest.fixture(scope="module")
def made():
    yield _make(15.0)


@pytest.fixture(scope="module")
def made_deep():
    """Task 0215 (0209 row 30): a sea 30 m deep, the cable's own depth 15 m."""
    yield _make(30.0)


def _arrays(doc, binary, spec) -> dict:
    a = {}
    for k in KEYS:
        v = spec.get(k)
        if isinstance(v, int) and not isinstance(v, bool):
            a[k] = core.accessor_array(doc, binary, v)
    for k in ("times", "step", "s0", "pay_t", "pay", "trim_t", "s", "slo", "sstep"):
        if k in a:
            a[k] = a[k].reshape(-1)
    return a


def _page_cable(scene, path, vessel: bool, animated: bool, t: float = 0.0):
    """(the page's cable points in Blender's world at ``t`` s of its animation, the page's settings)."""
    w = scene.fresing.web3d
    w.env_mode = "PROJECT"
    ch = dict(web3d_env.choice(scene), vessel=vessel)
    job = web3d.Job(scene, str(path), size=256, hide_names=False, surroundings=ch, animation=animated)
    out = job.run()
    data = open(out["path"], "rb").read()
    doc, binary = core.read_glb(data)
    cable = paths.find(scene, paths_sea.TEST_CABLE).part.name
    node = next(k for ob, k in job._nodes if ob.name == cable)
    nd = doc["nodes"][node]
    spec = nd["extras"]["fr_tube"]
    m = np.array(nd.get("matrix", list(np.eye(4).ravel())), np.float64).reshape(4, 4).T     # glTF: column by column
    arrays = _arrays(doc, binary, spec)

    def world(tt):
        pts = T.at(spec, arrays, tt)["points"]
        return pts @ m[:3, :3].T + m[:3, 3]
    if t is None:                                             # the moments of an animated page
        return world
    with open(out["html"], encoding="utf-8") as fh:
        st = env.page_settings(fh.read())
    return world(t), st


def _app_cable(scene, frame):
    """The app's cable ring centres in the world at ``frame`` (vessel moving) and the vessel rig's matrix."""
    scene.frame_set(frame)
    scene.frame_set(frame)
    ob = paths.find(scene, paths_sea.TEST_CABLE).part
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    rings = T.find_rings(co.reshape(-1, 3).astype(np.float64))
    c = rings[0]
    M = np.array(ob.matrix_world, np.float64)
    return c @ M[:3, :3].T + M[:3, 3], np.array(vessel_motion.rig("pivot").matrix_world, np.float64)


def test_without_vessel_motion_the_cable_lies_on_the_seabed(made, tmp_path):
    scene, _out = made
    scene.frame_set(scene.frame_start + 40)                   # a moment the vessel has pitched and rolled
    frame = scene.frame_current
    app, V = _app_cable(scene, frame)
    page, st = _page_cable(scene, tmp_path / "still.glb", vessel=False, animated=False)
    assert "vessel" not in st or not st.get("vessel")
    assert len(page) == len(app)
    bed, water = surroundings.seabed_z(scene), surroundings.waterline(scene)
    on_bed = app[:, 2] < bed + 0.3
    assert on_bed.sum() > 5
    # on the seabed: where the app lays it (it was up to 0.78 m into the seabed or 0.85 m over it)
    assert np.linalg.norm(page[on_bed] - app[on_bed], axis=1).max() < 0.02
    # above the water: on the vessel at rest (the app's place taken back by the vessel's motion)
    Vi = np.linalg.inv(V)
    rest = app @ Vi[:3, :3].T + Vi[:3, 3]
    up = app[:, 2] > water + 0.2
    assert up.sum() > 5
    assert np.linalg.norm(page[up] - rest[up], axis=1).max() < 0.02
    # no jump along the cable where it goes from the vessel to the seabed
    gap = np.linalg.norm(np.diff(page, axis=0), axis=1)
    app_gap = np.linalg.norm(np.diff(app, axis=0), axis=1)
    assert np.abs(gap - app_gap).max() < 0.1, np.abs(gap - app_gap).max()


def test_with_vessel_motion_the_page_keeps_it_on(made, tmp_path):
    scene, _out = made
    scene.frame_set(scene.frame_start)
    app, V = _app_cable(scene, scene.frame_start)
    page, st = _page_cable(scene, tmp_path / "moving.glb", vessel=True, animated=False)
    assert st["vessel"] and st["vessel"]["keep"] is True       # the page leaves out the switch
    # the page moves the cable's part by the vessel's motion at its first moment: where the app has it
    Vp = env.vessel_matrix(st["vessel"], scene.frame_start * scene.render.fps_base / scene.render.fps)
    moved = page @ Vp[:3, :3].T + Vp[:3, 3]
    assert np.linalg.norm(moved - app, axis=1).max() < 0.02


def test_an_animated_page_without_vessel_motion(made, tmp_path):
    """The same along the animation: each moment's points are put back with that moment's vessel motion."""
    scene, _out = made
    fps = scene.render.fps / scene.render.fps_base
    scene.frame_set(scene.frame_start)
    bed = surroundings.seabed_z(scene)
    at = _page_cable(scene, tmp_path / "anim.glb", vessel=False, animated=True, t=None)
    for f in (scene.frame_start + 60, scene.frame_start + 150):
        page = at((f - scene.frame_start) / fps)
        app, _V = _app_cable(scene, f)
        on_bed = app[:, 2] < bed + 0.3
        assert on_bed.sum() > 5
        # the page thins its moments (a few cm): on the seabed within that, not 0.8 m
        assert np.linalg.norm(page[on_bed] - app[on_bed], axis=1).max() < 0.06, f


def test_a_cable_with_its_own_depth_lies_on_its_own_bottom(made_deep, tmp_path):
    """Task 0215 (0209 row 30): the page blended a cable's points between the seabed of the sea (30 m) and the water,
    not the cable's own bottom (15 m): it lay 0.17–0.65 m off where the app lays it."""
    scene, _out = made_deep
    item = paths.find(scene, paths_sea.TEST_CABLE)
    assert item.sea_depth == 15.0 and scene.fresing.sea_depth == 30.0
    water = surroundings.waterline(scene)
    bed = water + paths_sea.bottom_z(scene, item)
    fps = scene.render.fps / scene.render.fps_base
    at = _page_cable(scene, tmp_path / "deep.glb", vessel=False, animated=True, t=None)
    for f in (scene.frame_start + 60, scene.frame_start + 150):
        page = at((f - scene.frame_start) / fps)
        app, _V = _app_cable(scene, f)
        on_bed = app[:, 2] < bed + 0.3
        assert on_bed.sum() > 5
        assert np.linalg.norm(page[on_bed] - app[on_bed], axis=1).max() < 0.06, f
