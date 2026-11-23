"""Task 0240: hoses, cables and drag chains drawn in the app by clicking points (blender/drawn.py, flex.draw_hose,
flex.draw_chain, paths.draw_cable) – and the pure part in core/flex.py (natural_length, shares, join).

The clicks are rays cast as the pickers cast them (``hover.cast``), on the generic test models of
tools/make_test_flex.py and tools/make_test_paths.py (their numbers are in the makers' docstrings).
"""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import flex as HS

HERE = os.path.dirname(__file__)
MM = 0.001
END_TOL = 0.1 * MM


# ---------------------------------------------------------------------------
# core/flex.py: no Blender
# ---------------------------------------------------------------------------

def test_natural_length_keeps_the_bend_and_adds_the_slack():
    # two fittings 0.5 m apart, both pointing up: a U
    length, line = HS.natural_length((0, 0, 0), (0, 0, 1), (0.5, 0, 0), (0, 0, -1), least_radius=0.05)
    assert np.allclose(line[0], (0, 0, 0)) and np.allclose(line[-1], (0.5, 0, 0))
    assert HS.bend_radius(line) >= 0.05
    assert length == pytest.approx(HS.polyline_length(line) * (1 + HS.SLACK))
    # a wider limit gives a longer hose
    longer, line2 = HS.natural_length((0, 0, 0), (0, 0, 1), (0.5, 0, 0), (0, 0, -1), least_radius=0.2)
    assert longer > length and HS.bend_radius(line2) >= 0.2 - 1e-9
    # in line, pointing at each other: straight, the slack only
    straight, _ = HS.natural_length((0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 0))
    assert straight == pytest.approx(1.0 * (1 + HS.SLACK))


def test_natural_length_leaves_and_arrives_along_the_end_directions():
    _length, line = HS.natural_length((0, 0, 0), (0, 1, 0), (0.3, 0.2, 0.1), (1, 0, 0), least_radius=0.02, n=201)
    first, last = line[1] - line[0], line[-1] - line[-2]
    assert np.allclose(first / np.linalg.norm(first), (0, 1, 0), atol=0.02)          # (the first chord)
    assert np.allclose(last / np.linalg.norm(last), (1, 0, 0), atol=0.02)


def test_shares_and_join():
    assert np.allclose(HS.shares([1.0, 3.0]), (0.25, 0.75))
    assert np.allclose(HS.shares([0.0, 0.0, 0.0]), (1 / 3, 1 / 3, 1 / 3))
    assert HS.segment_points(1, 35) == 35 and HS.segment_points(3, 35) == 103
    a = np.zeros((2, 4, 3))
    b = np.ones((2, 4, 3))
    j = HS.join([a, b])
    assert j.shape == (2, 7, 3) and np.array_equal(j[:, :4], a) and np.array_equal(j[:, 4:], b[:, 1:])


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, clash, drawn, flex, hover, joints, logic, paths,  # noqa: E402
                                    web3d)

HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")
HOSES_B = os.path.join(HERE, "data", "test_flex_hoses_b.step")
CHAINS = os.path.join(HERE, "data", "test_flex_chains_a.step")
PATHS_A = os.path.join(HERE, "data", "test_paths_a.step")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("drawn"))


def load(folder, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    paths.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = folder
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


def update():
    bpy.context.view_layer.update()


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def click(sc, origin, direction, want=None):
    """A click as the pickers make it: the ray, the part it hits, the spot it means."""
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert index >= 0, f"the ray from {origin} hits no part"
    if want is not None:
        assert ob.get(build.PROP_NAME) == want, ob.get(build.PROP_NAME)
    return drawn.spot(ob, index, loc, normal)


def set_joint(sc, name, value):
    joints.set_value(joints.find(sc, name), value)
    update()
    flex.refresh(sc)


@pytest.fixture()
def hoses(folder):
    """The hoses model with its joints; the CAD hoses are not in the list (drawn ones are what is tested)."""
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    while len(sc.fresing.flex):
        flex.remove(sc, 0)
    luff, slide = joints.find(sc, "Luff"), joints.find(sc, "Slide")      # the travel the maker checked
    luff.rot_min, luff.rot_max, luff.use_limits = math.radians(-20), math.radians(20), True
    slide.slide_min, slide.slide_max, slide.use_limits = -0.45, 0.45, True
    update()
    return sc


def hose_ab(sc):
    """End A on FITTING VALVE C's top (its middle: a small flat face), end B on FITTING ARM's end face. The CAD
    hose between them lies on both faces: hidden while clicking, as the picker does for the part it replaces."""
    cad = named(sc, "HYDRAULIC HOSE ARM")
    logic.set_visible_flags(cad, True)
    update()
    a = click(sc, (1.292, -0.209, 1.0), (0, 0, -1), "FITTING VALVE C")
    b = click(sc, (3.002, -0.9, 1.8), (0, 1, 0), "FITTING ARM")
    logic.set_visible_flags(cad, False)
    update()
    return a, b


def stops_now(item):
    out = [drawn.world_spot(item.a_part, item.a_point, item.a_dir)[0]]
    out += [drawn.world_spot(c.part, c.point, c.dir)[0] for c in item.clips]
    return out + [drawn.world_spot(item.b_part, item.b_point, item.b_dir)[0]]


def test_a_spot_on_a_round_face_is_on_its_axis_at_its_end(hoses):
    sc = hoses
    # SLIDE GLAND: a round stub Ø22 on the post along +X, its end face at (375, 350, 620); clicked on its side
    sp = click(sc, (1.07, 1.05, 2.5), (0, 0, -1), "SLIDE GLAND")
    assert sp["round"] and sp["diameter"] == pytest.approx(0.022, abs=0.0005)
    assert np.allclose(sp["point"], (1.075, 1.05, 1.86), atol=0.0005)
    assert np.allclose(sp["dir"], (1, 0, 0), atol=1e-6)
    # a small flat face: its middle, along its normal
    a, b = hose_ab(sc)
    assert not a["round"] and np.allclose(a["point"], (1.29, -0.21, 0.62), atol=1e-4)
    assert np.allclose(a["dir"], (0, 0, 1), atol=1e-6)
    assert np.allclose(b["point"], (3.0, 0.42, 1.8), atol=1e-4) and np.allclose(b["dir"], (0, -1, 0), atol=1e-6)


def test_a_hose_drawn_with_two_clicks_follows_like_a_cad_hose(hoses):
    sc = hoses
    a, b = hose_ab(sc)
    item, notes = flex.draw_hose(sc, [a, b], replace=named(sc, "HYDRAULIC HOSE ARM"))
    assert not notes and item.drawn and item.kind == "HOSE" and item.name == "Hose 1"
    assert drawn.is_drawn(item.part) and item.part.get(build.PROP_KIND) == "part" and item.part.parent is None
    assert item.diameter == pytest.approx(flex.DRAWN_DIAMETER[False])        # no round face: the usual 20 mm
    assert item.a_part.get(build.PROP_NAME) == "FITTING VALVE C" and item.b_part.get(build.PROP_NAME) == "FITTING ARM"
    assert flex.status(sc, item) == ("follows the motion", "OK")
    length = item.length
    for luff, slide in ((0.0, 0.0), (math.radians(-15), 0.3), (math.radians(18), -0.3)):     # three poses
        set_joint(sc, "Luff", luff)
        set_joint(sc, "Slide", slide)
        line = flex.shape_now(sc, item)
        ends = stops_now(item)
        assert np.linalg.norm(line[0] - ends[0]) < END_TOL and np.linalg.norm(line[-1] - ends[-1]) < END_TOL
        assert HS.polyline_length(line) == pytest.approx(length, rel=0.002)              # its length is kept
        assert item.length == length
    # the replaced CAD hose is hidden for good: view, render, clash check, web export
    cad = named(sc, "HYDRAULIC HOSE ARM")
    assert cad.get(build.PROP_EXCLUDED) and cad.hide_render and not cad.visible_get()
    assert cad.name not in {o.name for o in clash.objects(sc)}
    assert cad.name not in {o.name for o in web3d.objects(sc)[0]}
    assert item.part.name in {o.name for o in web3d.objects(sc)[0]}            # the drawn one is in the web model
    assert item.part.name not in {o.name for o in clash.objects(sc)}           # (bends on purpose, as CAD hoses)
    # removed: its object goes, the CAD hose shows again
    name = item.part.name
    flex.remove(sc, flex.index_of(sc, item))
    assert name not in bpy.data.objects
    assert not cad.get(build.PROP_EXCLUDED) and not cad.hide_render and drawn.REPLACED not in cad


def test_a_hose_through_two_clips_passes_them_at_every_pose_and_in_a_build(hoses):
    sc = hoses
    a, b = hose_ab(sc)
    c1 = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    c2 = click(sc, (2.55, -0.36, 2.5), (0, 0, -1), "BASE")
    logic.exclude([named(sc, "HYDRAULIC HOSE ARM")], True)
    item, _notes = flex.draw_hose(sc, [a, c1, c2, b])
    assert len(item.clips) == 2 and item.points == HS.segment_points(3, flex.DRAWN)
    shares = np.array(item["shares"])
    assert shares.sum() == pytest.approx(1.0) and (shares > 0).all()
    # a clip on a flat face: the hose lies on it (its middle one radius above), along it
    stops = stops_now(item)
    assert stops[1][2] == pytest.approx(0.3 + 0.5 * item.diameter, abs=1e-6)
    d1 = drawn.world_spot(item.clips[0].part, item.clips[0].point, item.clips[0].dir)[1]
    assert abs(d1[2]) < 1e-6 and d1[0] > 0.9
    length = item.length
    for luff in (0.0, math.radians(-12), math.radians(16)):
        set_joint(sc, "Luff", luff)
        line = flex.shape_now(sc, item)
        assert len(line) == 3 * (flex.POINTS - 1) + 1
        for k, p in enumerate(stops_now(item)):                  # A, both clips, B: on the line exactly
            assert np.linalg.norm(line - p, axis=1).min() < END_TOL, k
        assert HS.polyline_length(line) == pytest.approx(length, rel=0.003)
    # a built animation: every frame passes the clips and ends on the fittings
    set_joint(sc, "Luff", 0.0)
    anim = sc.fresing.animations.add()
    anim.name, anim.tail, anim.fps = "Move", 0.0, "25"
    blk = anim.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", "Luff", 0.0, 1.0, "LINEAR"
    blk.use_from, blk.to_angle = True, math.radians(15)
    r = animation.bake(sc, anim)
    assert not r["warnings"], r["warnings"]
    for f in (1, 13, 26):
        sc.frame_set(f)
        line = flex.shape_now(sc, item)
        for p in stops_now(item):
            assert np.linalg.norm(line - p, axis=1).min() < END_TOL, f


def test_a_part_gone_and_save_and_open(hoses, tmp_path):
    sc = hoses
    a, b = hose_ab(sc)
    item, _n = flex.draw_hose(sc, [a, b], soft=True)
    assert item.name == "Cable 1" and item.stiffness == pytest.approx(0.2)
    assert item.part.get(build.PROP_GROUP) == "Cables" and item.part.material_slots[0].material is not None
    set_joint(sc, "Luff", math.radians(10))
    path = str(tmp_path / "drawn.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    item = flex.find(sc, "Cable 1")
    assert item is not None and item.drawn and drawn.is_drawn(item.part)
    set_joint(sc, "Luff", math.radians(-10))
    line = flex.shape_now(sc, item)
    assert np.linalg.norm(line[-1] - stops_now(item)[-1]) < END_TOL
    # renamed: its object follows
    item.name = "Lamp cable"
    assert item.part.name == "Lamp cable" and item.part.get(build.PROP_NAME) == "Lamp cable"


def test_the_queue_copy_builds_the_drawn_hose_again(hoses, tmp_path):
    """The render queue opens a copy of the project and builds again: the drawn hose (with a clip) is drawn the same."""
    sc = hoses
    a, b = hose_ab(sc)
    clip = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    flex.draw_hose(sc, [a, clip, b])
    anim = sc.fresing.animations.add()
    anim.name, anim.tail, anim.fps = "Queue", 0.0, "25"
    blk = anim.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", "Luff", 0.0, 1.0, "LINEAR"
    blk.use_from, blk.to_angle = True, math.radians(14)
    assert not animation.bake(sc, anim)["warnings"]
    sc.frame_set(20)
    want = flex.shape_now(sc, flex.find(sc, "Hose 1"))
    path = str(tmp_path / "queue copy.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    r = animation.bake(sc, sc.fresing.animations["Queue"])
    assert not r["warnings"], r["warnings"]
    sc.frame_set(20)
    got = flex.shape_now(sc, flex.find(sc, "Hose 1"))
    assert got.shape == want.shape and np.abs(got - want).max() < 1e-6


def test_model_update_keeps_a_drawn_hose_on_its_parts(hoses):
    sc = hoses
    a, b = hose_ab(sc)
    item, _n = flex.draw_hose(sc, [a, b], replace=named(sc, "HYDRAULIC HOSE ARM"))
    item.stiffness = 0.8
    length, part = item.length, item.part.name
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=HOSES_B, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    item = flex.find(sc, "Hose 1")
    assert item is not None and item.part.name == part and item.length == length and item.stiffness == pytest.approx(0.8)
    assert item.a_part.get(build.PROP_NAME) == "FITTING VALVE C" and item.b_part.get(build.PROP_NAME) == "FITTING ARM"
    assert flex.status(sc, item) == ("follows the motion", "OK")
    cad = named(sc, "HYDRAULIC HOSE ARM")                       # the new revision's CAD hose: still replaced
    assert cad.get(build.PROP_EXCLUDED) and cad.get(drawn.REPLACED) == "Hose 1"
    set_joint(sc, "Luff", math.radians(12))
    line = flex.shape_now(sc, item)
    assert np.linalg.norm(line[-1] - stops_now(item)[-1]) < END_TOL


def test_odd_clicks_are_refused_in_words(hoses):
    sc = hoses
    a, b = hose_ab(sc)
    with pytest.raises(flex.FlexError):
        flex.draw_hose(sc, [a])
    with pytest.raises(flex.FlexError):
        flex.draw_hose(sc, [a, dict(a)])                         # the same place twice is one click
    item, _n = flex.draw_hose(sc, [a, dict(a), b])               # … and does not count as a clip
    assert len(item.clips) == 0
    with pytest.raises(drawn.DrawError):                         # a drawn hose is no fitting
        drawn.spot(item.part, 0, item.part.data.vertices[0].co, (0, 0, 1))
    assert len(sc.fresing.flex) == 1


# ---------------------------------------------------------------------------
# drag chains
# ---------------------------------------------------------------------------

def test_a_drawn_drag_chain_rolls_with_its_axis_and_replaces_the_cad_chain(folder):
    sc = load(folder, CHAINS)
    flex.set_up_test_chains(sc)
    i = next(k for k, it in enumerate(sc.fresing.flex) if it.name == "CHAIN X.ASM")
    flex.remove(sc, i)
    link = next(o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM"))
    # the CAD links are in the way of the brackets' clicks: hidden while clicking, as the picker does
    logic.exclude([o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM")], True)
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")
    b = click(sc, (-0.01, -1, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING")
    logic.exclude([o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM")], False)
    item, notes = flex.draw_chain(sc, a, b, replace=link)
    assert not notes and item.drawn and item.made_links and item.kind == "CHAIN"
    rows = {r.obj.name for r in item.replaces}
    assert len(rows) == 24                                       # one link clicked: the whole row of 24
    assert all(named(sc, "CHAIN X.ASM") == build.logical_parent(sc.objects[n]) for n in rows)
    # the runs lie along X (the slide joint that moves the moving bracket), the bend radius = half the gap
    frame = np.array(item.a_part.matrix_world) @ np.array(item.frame).reshape(4, 4)
    assert abs(frame[0, 0]) == pytest.approx(1.0, abs=1e-6)
    assert item.radius == pytest.approx(0.5 * (0.83 - 0.661), abs=1e-4)
    for x in (-0.375, 0.0, 0.375):
        set_joint(sc, "X", x)
        assert flex.status(sc, item) == ("follows the motion", "OK"), x
        pins = flex.pins_now(sc, item)
        gaps = np.linalg.norm(np.diff(pins, axis=0), axis=1)
        assert np.allclose(gaps, item.pitch, atol=1e-6)          # links one pitch apart
        end = drawn.world_spot(item.b_part, item.b_point, (1, 0, 0))[0]
        assert np.linalg.norm(pins[-1] - end) < END_TOL          # the last pin on the moving bracket
    checked = {o.name for o in clash.objects(sc)}
    assert not rows & checked and item.part.name not in checked
    assert not rows & {o.name for o in web3d.objects(sc)[0]}
    # flip the bend: still reaches; swap ends: the other bracket is fixed
    flex.flip_bend(sc, item)
    set_joint(sc, "X", 0.05)
    assert flex.pins_now(sc, item).shape[0] == item.count + 1
    flex.swap_ends(sc, item)
    assert item.a_part.get(build.PROP_NAME) == "CHAIN BRACKET X MOVING"
    set_joint(sc, "X", -0.05)
    pins = flex.pins_now(sc, item)
    assert np.allclose(np.linalg.norm(np.diff(pins, axis=0), axis=1), item.pitch, atol=1e-6)
    assert np.linalg.norm(pins[-1] - drawn.world_spot(item.b_part, item.b_point, (1, 0, 0))[0]) < END_TOL


# ---------------------------------------------------------------------------
# a cable route
# ---------------------------------------------------------------------------

def test_a_cable_route_drawn_over_three_sheaves_from_the_drum_runs_like_the_cad_cable(folder):
    sc = load(folder, PATHS_A)
    rope = named(sc, "WIRE ROPE")
    logic.exclude([rope], True)
    update()
    start = click(sc, (0.0, 0.0, 0.45), (1, 0, 0), "WINCH DRUM")
    hits = []
    for name, o, d in (("SHEAVE 1", (1.9104, 0.0, 3.0), (0, 0, -1)), ("SHEAVE 2", (1.5, 0.0, 0.5), (0, 0, 1)),
                       ("CHUTE", (2.7, 0.0, 1.5), (0, 0, -1))):
        ob, _i, loc, _n = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(o), Vector(d))
        assert ob.get(build.PROP_NAME) == name
        hits.append((ob, np.array(loc), False))
    logic.exclude([rope], False)
    item, notes = paths.draw_cable(sc, start, hits, None, name="Drawn rope", diameter=0.024, replace=rope)
    assert item.drawn and drawn.is_drawn(item.part) and paths.broken(sc, item) == ""
    kinds = [(c.part.get(build.PROP_NAME), c.kind) for c in item.contacts]
    assert kinds == [("WINCH DRUM", "SHEAVE"), ("SHEAVE 1", "SHEAVE"), ("SHEAVE 2", "SHEAVE"), ("V ROLLER", "ROLLER"),
                     ("V ROLLER", "ROLLER"), ("CHUTE", "CHUTE")]                     # as the CAD rope reads
    assert rope.get(build.PROP_EXCLUDED) and rope.name not in {o.name for o in clash.objects(sc)}
    assert item.diameter == pytest.approx(0.024, abs=2e-4)
    # it turns its wheels: each turning one follows the cable's speed joint
    lead = joints.find(sc, item.joint)
    for c in item.contacts:
        if c.kind in ("SHEAVE", "ROLLER"):
            j = joints.find(sc, c.joint)
            assert j is not None and j.follows == lead.name, c.name
    # it pays out: 1 m of cable turns sheave 1 by 1 m / its seat radius
    s1 = next(c for c in item.contacts if c.part.get(build.PROP_NAME) == "SHEAVE 1")
    j1 = joints.find(sc, s1.joint)
    joints.set_value(lead, 1.0)
    update()
    assert abs(joints.get_value(j1)) == pytest.approx(1.0 / 0.25, rel=0.01)
    joints.set_value(lead, 0.0)
    # luffed, the route is laid anew and still has its six contacts
    luff = joints.create(sc, "ROTATE", [named(sc, "A-FRAME.ASM")], Vector((1.5, 0.0, 0.73)), Vector((0, 1, 0)),
                         name="Luff")
    joints.set_value(joints.find(sc, luff.name), math.radians(10))
    update()
    paths.refresh(sc)
    assert paths.status(sc, paths.find(sc, "Drawn rope"))[1] == "OK"
    # removed: the CAD rope shows again
    paths.remove(sc, paths.index_of(sc, paths.find(sc, "Drawn rope")))
    assert not rope.get(build.PROP_EXCLUDED) and not any(drawn.is_drawn(o) for o in sc.objects)


def test_a_cable_route_without_wheels_or_with_the_same_place_is_refused(folder):
    sc = load(folder, PATHS_A)
    start = click(sc, (0.5, 0.33, 1.0), (0, 0, -1), "BASE FRAME")     # a rail's top: no drum
    with pytest.raises(paths.PathError):
        paths.draw_cable(sc, start, [], None)                             # no wheel and no end
    with pytest.raises(paths.PathError):
        paths.draw_cable(sc, start, [], dict(start))                      # the end where it starts
    assert not len(sc.fresing.cables) and not any(drawn.is_drawn(o) for o in sc.objects)
    assert not [j for j in sc.fresing.joints if j.name.startswith("Cable")]                  # nothing left behind
