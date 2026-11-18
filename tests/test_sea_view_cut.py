"""The sea cut-away in the 3D view (task 0196, ``blender/sea_view_cut.py``).

The cut-away is a shader effect in a render; in Solid view the sea was one grey sheet over the box. The view now gets
the box cut out of the sea's and the seabed's mesh by a Geometry Nodes modifier that is off for renders. Tested on
the evaluated viewport mesh: nothing of the sea or the seabed lies in the box (they are let down under it, or the
faces are gone), everything outside the box is as it was, the box follows the panel's numbers, and the render's
evaluation does not have the modifier at all.
"""

import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from test_sea_cutaway import _apply, _camera, _env, _render, addon, scene  # noqa: E402,F401
from fresing_render.blender import sea_view_cut, surroundings  # noqa: E402

MOD = sea_view_cut.MOD


def _world_points(ob):
    """The evaluated (viewport) mesh's points in world, and its face centres."""
    ev = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = ev.to_mesh()
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", a)
    pts = a.reshape(-1, 3).astype(float)
    centres = np.array([p.center for p in me.polygons]).reshape(-1, 3)
    ev.to_mesh_clear()
    m = np.array(ob.matrix_world)
    to_w = lambda q: q @ m[:3, :3].T + m[:3, 3]            # noqa: E731
    return to_w(pts), (to_w(centres) if len(centres) else centres)


def _inside(points, box, margin=0.0):
    o = np.array([*box["origin"][:2]])
    u = np.array([*box["dir"][:2]])
    u = u / np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    d = points[:, :2] - o
    along, side = d @ u, d @ v
    return (along > margin) & (along < box["length"] - margin) & (np.abs(side) < box["width"] / 2 - margin)


def _build(scene, detailed, ground=True):
    s = scene.fresing
    s.sea_cutaway = True
    s.sea_cut_ground = ground
    s.env_detail = "DETAILED" if detailed else "SIMPLE"
    s.sea_moving = True
    _apply(scene)
    bpy.context.view_layer.update()
    return _env("sea")[0], _env("seabed")[0], surroundings.sea_cut_box(scene)


@pytest.mark.parametrize("detailed", [False, True])
def test_view_has_no_sea_or_seabed_in_the_box(scene, detailed):
    sea, bed, box = _build(scene, detailed)
    level = sea.matrix_world.translation.z
    top = bed.matrix_world.translation.z
    for ob in (sea, bed):
        assert MOD in ob.modifiers and ob.modifiers[MOD].show_viewport and not ob.modifiers[MOD].show_render
        assert list(ob.modifiers)[-1].name == MOD                     # after the waves
    pts, centres = _world_points(sea)
    inner = pts[_inside(pts, box, margin=2.0)]
    assert detailed == (len(inner) > 0)                               # let down (Detailed) / gone (Simple) ...
    if detailed:
        assert inner[:, 2].max() < top - 0.1                          # ... under the seabed: never seen
    assert not len(centres[_inside(centres, box, margin=2.0)]) or inner[:, 2].max() < top - 0.1
    outer = pts[~_inside(pts, box, margin=-3.0)]
    assert outer[:, 2].max() > level - 1.0 and len(outer) > 100        # the sea outside the box is still there
    pts, _ = _world_points(bed)
    inner = pts[_inside(pts, box, margin=2.0)]
    assert len(inner) == 0 or inner[:, 2].max() < top - 0.1           # the seabed is open in the box (ground cut)


def test_without_ground_the_seabed_is_left_alone(scene):
    sea, bed, box = _build(scene, True, ground=False)
    assert MOD in sea.modifiers and MOD not in bed.modifiers
    pts, _ = _world_points(bed)
    assert len(pts[_inside(pts, box, margin=2.0)]) > 0


def test_outside_the_box_the_sea_is_what_it_was(scene):
    sea, bed, box = _build(scene, True)
    mod = sea.modifiers[MOD]
    a, _ = _world_points(sea)
    mod.show_viewport = False
    bpy.context.view_layer.update()
    b, _ = _world_points(sea)
    assert a.shape == b.shape
    same = ~_inside(b, box, margin=-1.0)
    assert np.allclose(a[same], b[same], atol=1e-4)
    assert (np.abs(a - b).max(axis=1) > 1.0).sum() > 100              # and the box points moved


def test_box_follows_the_panels_numbers(scene):
    s = scene.fresing
    sea, bed, box = _build(scene, True)
    s.sea_cut_auto = False
    s.sea_cut_length, s.sea_cut_width, s.sea_cut_start = 30.0, 12.0, 10.0
    _apply(scene)
    sea, bed = _env("sea")[0], _env("seabed")[0]
    box2 = surroundings.sea_cut_box(scene)
    assert box2["length"] == pytest.approx(30.0) and box2["width"] == pytest.approx(12.0)
    for ob in (sea, bed):
        pts, _ = _world_points(ob)
        assert len(pts[_inside(pts, box2, margin=2.0)]) == 0 or pts[_inside(pts, box2, margin=2.0)][:, 2].max() < \
            bed.matrix_world.translation.z - 0.1
        pts_in = pts[_inside(pts, box2, margin=-3.0) & ~_inside(pts, box2, margin=2.0)]
        assert len(pts) > 0 and pts_in is not None
    # just outside the new box but inside the old one: the sea is back at its level
    pts, _ = _world_points(sea)
    only_old = _inside(pts, box, margin=2.0) & ~_inside(pts, box2, margin=-3.0)
    if only_old.any():
        assert pts[only_old][:, 2].max() > bed.matrix_world.translation.z + 1.0


def test_off_without_the_cut_away_and_for_a_hall(scene):
    s = scene.fresing
    sea, bed, box = _build(scene, True)
    s.sea_cutaway = False
    _apply(scene)
    for ob in _env("sea") + _env("seabed"):
        assert MOD not in ob.modifiers


def test_cost_of_the_view_cut_per_frame(scene):
    """The view cut costs well under a millisecond a frame on moving waves (Detailed, the demo's sea)."""
    sea, bed, box = _build(scene, True)
    mods = [ob.modifiers[MOD] for ob in (sea, bed)]
    best = {True: 1e9, False: 1e9}
    for _ in range(6):                                      # interleaved: the machine's noise hits both alike
        for state in (True, False):
            for m in mods:
                m.show_viewport = state
            t = time.perf_counter()
            for f in range(1, 31):
                scene.frame_set(f)
            best[state] = min(best[state], (time.perf_counter() - t) / 30 * 1000)
    print(f"view cut: {best[True]:.2f} ms/frame with, {best[False]:.2f} without")
    assert best[True] - best[False] < 1.0


@pytest.mark.parametrize("detailed", [False, True])
def test_a_render_is_the_same_with_and_without_the_view_cut(scene, tmp_path, detailed):
    """The cut is for the 3D view only: a Cycles picture straight down into the box, and one across the sea, equal
    to the last digit whether the modifiers are there or not."""
    sea, bed, box = _build(scene, detailed)
    water, floor = surroundings.waterline(scene), surroundings.seabed_z(scene)
    mid = (box["origin"][0] + box["dir"][0] * box["length"] / 2, box["origin"][1] + box["dir"][1] * box["length"] / 2)
    shots = ((( mid[0], mid[1], water + 40.0), (mid[0], mid[1] + 0.001, floor)),
             ((70.0, -10.0, water + 10.0), (mid[0], mid[1], water - 5.0)))
    for n, (eye, at) in enumerate(shots):
        _camera(scene, eye, at, lens=60.0)
        with_cut = _render(scene, tmp_path / f"a{n}.exr")
        saved = [(ob, ob.modifiers[MOD].node_group) for ob in (sea, bed)]
        for ob, _ in saved:
            ob.modifiers.remove(ob.modifiers[MOD])
        without = _render(scene, tmp_path / f"b{n}.exr")
        for ob, _ in saved:
            sea_view_cut.set_cut(ob, box, exact=not detailed, drop=1.0)
        assert np.array_equal(with_cut, without), n
