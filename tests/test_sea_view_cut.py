"""The sea cut-away in the 3D view (tasks 0196, 0202: ``blender/sea_view_cut.py``).

In a render the cut-away is a shader effect; Solid view draws no materials, so the box is cut out of the meshes by a
viewport-only Geometry Nodes modifier. Task 0202 measured 0.2.153's way (delete the faces inside: +6.2 ms a frame on the
demo's Detailed sea) and replaced it: the points inside the box are let down under what lies beneath them, and the
points round the box are put onto its walls (a straight edge, a straight wall: no spikes); a Simple surface of a few
big faces gets a thin slab cut by the box. Tested on the evaluated viewport meshes; renders are not touched.
"""

import json
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from test_sea_cutaway import _apply, _camera, _env, _render, addon, scene  # noqa: E402,F401
from fresing_render.blender import sea_view_cut, surroundings  # noqa: E402

MOD = sea_view_cut.MOD


def _world(ob):
    """The evaluated (viewport) mesh: points in world, and the faces as lists of point indices."""
    deps = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        a = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", a)
        pts = a.reshape(-1, 3).astype(float)
        n = np.empty(len(me.polygons), np.int32)
        me.polygons.foreach_get("loop_total", n)
        loops = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", loops)
        faces = np.split(loops, np.cumsum(n)[:-1]) if len(n) else []
        m = np.array(ev.matrix_world)
        return pts @ m[:3, :3].T + m[:3, 3], faces
    finally:
        ev.to_mesh_clear()


def _box_coords(points, box):
    o = np.array([*box["origin"][:2]])
    u = np.array([*box["dir"][:2]])
    u = u / np.linalg.norm(u)
    v = np.array([-u[1], u[0]])
    d = points[:, :2] - o
    return d @ u, d @ v


def _inside(points, box, margin=0.0):
    along, side = _box_coords(points, box)
    return (along > margin) & (along < box["length"] - margin) & (np.abs(side) < box["width"] / 2 - margin)


def _to_edge(points, box):
    """How far each point lies from the box's outline (in x, y)."""
    along, side = _box_coords(points, box)
    L, W = box["length"], box["width"] / 2
    inside = (along >= 0) & (along <= L) & (np.abs(side) <= W)
    d_in = np.minimum.reduce([along, L - along, W - np.abs(side)])
    da = np.maximum(np.maximum(-along, along - L), 0.0)
    ds = np.maximum(np.abs(side) - W, 0.0)
    return np.where(inside, d_in, np.hypot(da, ds))


def _build(scene, detailed, ground=True):
    s = scene.fresing
    s.sea_cutaway = True
    s.sea_cut_ground = ground
    s.sea_foam = True
    s.env_detail = "DETAILED" if detailed else "SIMPLE"
    s.sea_moving = True
    _apply(scene)
    bpy.context.view_layer.update()
    return surroundings.sea_cut_box(scene)


def _bottom(scene, ground=True):
    """World z under which nothing may be seen in the box: the seabed, or the bottom of the soil section's pit."""
    bed = surroundings.seabed_z(scene)
    if not ground:
        return bed
    soil = _env("soil")[0]
    return bed - float(soil["fr_soil_depth"])


@pytest.mark.parametrize("detailed", [False, True])
def test_nothing_of_the_sea_is_seen_in_the_box(scene, detailed):
    box = _build(scene, detailed)
    bottom = _bottom(scene)
    roles = ["sea", "hull_foam", "seabed"] + (["stones"] if detailed else [])
    for role in roles:
        obs = _env(role)
        assert obs, role
        ob = obs[0]
        mod = ob.modifiers[MOD]
        assert mod.show_viewport and not mod.show_render, role
        assert list(ob.modifiers)[-1].name == MOD, role              # after the waves
        exact = role in ("sea", "seabed") and not detailed
        assert mod.node_group.name == sea_view_cut.GROUP
        pts, faces = _world(ob)
        inner = pts[_inside(pts, box, margin=0.5)]
        if exact:
            assert len(inner) == 0, role                               # cut away (slab + Boolean)
        else:
            assert len(inner) > 0 and inner[:, 2].max() < bottom - 0.5, (role, inner[:, 2].max(), bottom)
    level = surroundings.waterline(scene)
    pts, _ = _world(_env("sea")[0])
    near = np.hypot(*(pts[:, :2] - np.array(box["origin"][:2])).T) < 200.0     # (far out the rim rises, by design)
    outer = pts[~_inside(pts, box, margin=-5.0) & near]
    assert len(outer) > 100 and np.abs(outer[:, 2] - level).max() < 8.0      # the sea outside is still there


def test_the_plain_seabed_square_leaves_the_pit_open(scene):
    """Task 0375 (0202's open point): in Detailed the plain seabed square 6 cm under the rippled patch is one face 2 km
    wide with no point in the box: letting points down left it over the ground cut's pit in the 3D view. It is cut
    exactly now; rays straight down into the box meet no seabed above the pit's bottom, outside it they do."""
    from mathutils import Vector
    box = _build(scene, True)
    bottom = _bottom(scene)
    bed = _env("seabed")[0]
    assert bed.data.attributes.get(sea_view_cut.PLAIN) is not None
    assert bed.modifiers[MOD].node_group.name == sea_view_cut.GROUP
    deps = bpy.context.evaluated_depsgraph_get()
    ev = bed.evaluated_get(deps)
    inv = ev.matrix_world.inverted()
    o = np.array(box["origin"][:2])
    u = np.array(box["dir"][:2]) / np.linalg.norm(box["dir"][:2])
    v = np.array([-u[1], u[0]])
    L, W = float(box["length"]), float(box["width"]) / 2

    def hit_z(a, b):
        p = o + a * u + b * v
        start = inv @ Vector((p[0], p[1], 500.0))
        down = (inv.to_3x3() @ Vector((0.0, 0.0, -1.0))).normalized()
        ok, loc, _n, _i = ev.ray_cast(start, down, depsgraph=deps)
        return (ev.matrix_world @ loc).z if ok else None
    level = surroundings.seabed_z(scene)

    def check():
        for a in np.linspace(0.1, 0.9, 5) * L:
            for b in np.linspace(-0.8, 0.8, 5) * W:
                z = hit_z(a, b)
                assert z is None or z < bottom - 0.5, (a, b, z, bottom)
        for a, b in ((-30.0, 0.0), (L + 30.0, 0.0), (0.5 * L, W + 30.0), (-400.0, 300.0)):
            z = hit_z(a, b)
            assert z is not None and abs(z - level) < 0.5, (a, b, z, level)     # the seabed outside is still there
    check()
    # the seabed slides aft with the lay, far past its rippled patch: the hole stays with the box
    mover = bpy.data.objects.get(surroundings.SEABED_MOTION)
    if mover is None:
        mover = bpy.data.objects.new(surroundings.SEABED_MOTION, None)
        scene.collection.objects.link(mover)
    surroundings.follow_seabed_motion(bed)
    mover.location = (float(u[0]) * 150.0, float(u[1]) * 150.0, 0.0)
    bpy.context.view_layer.update()
    deps.update()
    ev = bed.evaluated_get(deps)
    inv = ev.matrix_world.inverted()
    assert (np.array(ev.matrix_world.translation)[:2] @ u) > 100.0
    check()


def test_the_edge_is_straight_and_the_wall_stands_on_it(scene):
    """No spikes: every face that reaches from the surface down into the box has all its corners on the box's outline
    (the points round the box are put onto its walls), and no face at the surface reaches into the box."""
    box = _build(scene, True)
    level = surroundings.waterline(scene)
    for role in ("sea", "hull_foam"):                                 # (the seabed is let down where it is now)
        pts, faces = _world(_env(role)[0])
        top = pts[:, 2].max() if role == "seabed" else level
        walls = 0
        near = np.hypot(*(pts[:, :2] - np.array(box["origin"][:2])).T) < 200.0
        for f in faces:
            if not near[f].all():                                    # (far out the sea's rim rises, by design)
                continue
            z = pts[f, 2]
            if z.max() - z.min() > 3.0:                               # a wall face
                walls += 1
                assert _to_edge(pts[f], box).max() < 2e-3, (role, _to_edge(pts[f], box))
            elif z.min() > top - 2.5 and role != "seabed":           # a face at the surface
                assert not _inside(pts[f].mean(axis=0)[None], box, margin=1e-3)[0], role
        assert walls > 10, role


def test_outside_the_box_the_sea_is_what_it_was(scene):
    box = _build(scene, True)
    sea = _env("sea")[0]
    a, _ = _world(sea)
    sea.modifiers[MOD].show_viewport = False
    bpy.context.view_layer.update()
    b, _ = _world(sea)
    assert a.shape == b.shape
    far = ~_inside(b, box, margin=-8.0)                               # (the points next to the box go onto its edge)
    assert np.allclose(a[far], b[far], atol=1e-4)
    assert (np.abs(a - b).max(axis=1) > 1.0).sum() > 100              # and the box's points moved


def test_box_follows_the_panels_numbers(scene):
    s = scene.fresing
    _build(scene, True)
    s.sea_cut_auto = False
    s.sea_cut_length, s.sea_cut_width, s.sea_cut_start = 30.0, 12.0, 10.0
    _apply(scene)
    box2 = surroundings.sea_cut_box(scene)
    assert box2["length"] == pytest.approx(30.0) and box2["width"] == pytest.approx(12.0)
    bottom = _bottom(scene)
    for role in ("sea", "seabed"):
        pts, _ = _world(_env(role)[0])
        inner = pts[_inside(pts, box2, margin=0.5)]
        assert len(inner) and inner[:, 2].max() < bottom - 0.5


def test_without_ground_the_seabed_is_left_alone(scene):
    box = _build(scene, True, ground=False)
    sea, bed = _env("sea")[0], _env("seabed")[0]
    assert MOD in sea.modifiers and MOD not in bed.modifiers and MOD not in _env("stones")[0].modifiers
    pts, _ = _world(bed)
    assert len(pts[_inside(pts, box, margin=2.0)]) > 0
    inner, _ = _world(sea)
    inner = inner[_inside(inner, box, margin=0.5)]
    assert inner[:, 2].max() < surroundings.seabed_z(scene) - 0.5          # under the seabed: never seen


def test_off_without_the_cut_away(scene):
    s = scene.fresing
    _build(scene, True)
    s.sea_cutaway = False
    _apply(scene)
    for role in ("sea", "seabed", "hull_foam"):
        for ob in _env(role):
            assert MOD not in ob.modifiers


def test_cost_of_the_view_cut(scene):
    """The view cut adds no measurable time when the waves move (task 0202: 0.2.153's face deleting cost +6.2 ms a
    frame on the demo's Detailed sea, ~+3 ms on this vessel's). Only the cut objects are worked out again, with and
    without the modifier, interleaved, the best of several runs: generous bound, so it cannot grow unnoticed."""
    _build(scene, True)
    obs = [ob for role in ("sea", "hull_foam", "seabed", "stones") for ob in _env(role)]
    mods = [ob.modifiers[MOD] for ob in obs]
    deps = bpy.context.evaluated_depsgraph_get()
    best = {True: 1e9, False: 1e9}
    for rep in range(8):
        for state in ((True, False) if rep % 2 == 0 else (False, True)):
            for m in mods:
                m.show_viewport = state
            deps.update()
            t = 0.0
            for f in range(1, 21):
                scene.frame_set(f)
                for ob in obs:
                    ob.update_tag()
                t0 = time.perf_counter()
                deps.update()
                t += time.perf_counter() - t0
            best[state] = min(best[state], t / 20 * 1000)
    print(f"view cut: {best[True]:.2f} ms with, {best[False]:.2f} ms without")
    assert best[True] - best[False] < 1.5


@pytest.mark.parametrize("detailed", [False, True])
def test_a_render_is_the_same_with_and_without_the_view_cut(scene, tmp_path, detailed):
    """The cut is for the 3D view only: a Cycles picture straight down into the box, and one across the sea, equal
    to the last digit whether the modifiers are there or not."""
    box = _build(scene, detailed)
    water, floor = surroundings.waterline(scene), surroundings.seabed_z(scene)
    mid = (box["origin"][0] + box["dir"][0] * box["length"] / 2, box["origin"][1] + box["dir"][1] * box["length"] / 2)
    shots = (((mid[0], mid[1], water + 40.0), (mid[0], mid[1] + 0.001, floor)),
             ((70.0, -10.0, water + 10.0), (mid[0], mid[1], water - 5.0)))
    obs = [ob for ob in bpy.data.objects if MOD in ob.modifiers]
    assert len(obs) >= 3
    for n, (eye, at) in enumerate(shots):
        _camera(scene, eye, at, lens=60.0)
        with_cut = _render(scene, tmp_path / f"a{n}.exr")
        for ob in obs:
            ob.modifiers[MOD].show_viewport = False
        without = _render(scene, tmp_path / f"b{n}.exr")
        for ob in obs:
            ob.modifiers[MOD].show_viewport = True
        assert np.array_equal(with_cut, without), n


def test_a_0_2_153_project_gets_the_new_view_cut(scene):
    """0.2.153 put a face-deleting group "FR view cut" on the sea: opening such a project puts the new one on."""
    box = _build(scene, True)
    sea = _env("sea")[0]
    old = bpy.data.node_groups.new(sea_view_cut.OLD_GROUP, "GeometryNodeTree")
    old.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    old.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    sea.modifiers[MOD].node_group = old
    assert sea_view_cut.old_cut_objects() == [sea]
    assert surroundings.refresh_view_cuts(scene) == 1
    assert sea.modifiers[MOD].node_group.name == sea_view_cut.GROUP
    assert sea_view_cut.OLD_GROUP not in bpy.data.node_groups
    bpy.context.view_layer.update()
    pts, _ = _world(sea)
    inner = pts[_inside(pts, box, margin=0.5)]
    assert inner[:, 2].max() < _bottom(scene) - 0.5
    assert json.loads(surroundings.root_object()["fr_seacut_box"])["length"] == pytest.approx(box["length"])
