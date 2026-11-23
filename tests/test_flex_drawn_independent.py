"""Task 0240, independent tests: hoses, cables and drag chains drawn by clicking (blender/drawn.py, flex.draw_hose,
flex.draw_chain, paths.draw_cable, ops_drawn's picker) – written from the brief by a tester who did not write the code,
to break it: odd clicks, parts that go or move away, replacing, save / open, Build, nothing left behind.

Clicks are rays cast as the pickers cast them (``hover.cast`` -> ``drawn.spot``) on the generic test models of
tools/make_test_flex.py and tools/make_test_paths.py.
"""

import math
import os
import sys
import types

import numpy as np
import pytest

from fresing_render.core import flex as HS

HERE = os.path.dirname(__file__)
MM = 0.001
END_TOL = 0.1 * MM


# ---------------------------------------------------------------------------
# core/flex.py: no Blender
# ---------------------------------------------------------------------------



@pytest.mark.parametrize("p1,t1", [
    pytest.param((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),      # both ends on one point, same way
    pytest.param((0.0, 0.0, 0.0), (-1.0, 0.0, 0.0)),     # one point, back the way it left
    pytest.param((-0.5, 0.0, 0.0), (-1.0, 0.0, 0.0)),    # end B behind end A, in line: a U-turn
    ((0.0, 0.0, 0.3), (0.0, 0.0, -1.0)),           # straight above, arriving downwards: against its leaving direction
    ((1e-7, 0.0, 0.0), (0.0, 1.0, 0.0)),           # ends a fraction of a micrometre apart
])
def test_natural_length_odd_ends_give_a_finite_line_that_keeps_the_bend(p1, t1):
    least = 0.05
    length, line = HS.natural_length((0, 0, 0), (1, 0, 0), p1, t1, least_radius=least)
    assert np.isfinite(length) and length > 0.0
    assert np.all(np.isfinite(line))
    assert np.allclose(line[0], (0, 0, 0), atol=1e-9) and np.allclose(line[-1], p1, atol=1e-9)
    assert length >= float(np.linalg.norm(np.asarray(p1))) - 1e-12
    assert HS.bend_radius(line) >= least * 0.999, HS.bend_radius(line)


def test_shares_never_negative_and_join_of_one_piece_is_that_piece():
    s = HS.shares([-1.0, 2.0, 2.0])
    assert (s >= 0).all() and s.sum() == pytest.approx(1.0)
    one = np.arange(12, dtype=float).reshape(4, 3)
    assert np.array_equal(HS.join([one]), one)
    assert HS.segment_points(0, 35) == 0 and HS.join([]).shape == (0, 3)


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
import fresing_render  # noqa: E402
from fresing_render.blender import (animation, build, clash, drawn, flex, hover, joints, logic,  # noqa: E402
                                    ops_drawn, paths, web3d)

HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")
HOSES_B = os.path.join(HERE, "data", "test_flex_hoses_b.step")
CHAINS = os.path.join(HERE, "data", "test_flex_chains_a.step")
PATHS_A = os.path.join(HERE, "data", "test_paths_a.step")
CAD_HOSES = ("HYDRAULIC HOSE ARM", "HYDRAULIC HOSE CYL A", "HYDRAULIC HOSE CYL B", "CABLE")


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return str(tmp_path_factory.mktemp("drawn_ind"))


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
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert index >= 0, f"the ray from {origin} hits no part"
    if want is not None:
        assert ob.get(build.PROP_NAME) == want, ob.get(build.PROP_NAME)
    return drawn.spot(ob, index, loc, normal)


def hit(sc, origin, direction, want):
    """A wheel click for draw_cable: (part, the point clicked, flip=False)."""
    ob, _i, loc, _n = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector(origin), Vector(direction))
    assert ob is not None and ob.get(build.PROP_NAME) == want, ob and ob.get(build.PROP_NAME)
    return ob, np.array(loc), False


def set_joint(sc, name, value):
    joints.set_value(joints.find(sc, name), value)
    update()
    flex.refresh(sc)
    paths.refresh(sc)


def snapshot(sc):
    """Everything a draw can leave behind."""
    col = bpy.data.collections.get(drawn.COLLECTION)
    return {
        "flex": [it.name for it in sc.fresing.flex],
        "cables": [it.name for it in sc.fresing.cables],
        "joints": sorted(j.name for j in sc.fresing.joints),
        "objects": sorted(o.name for o in bpy.data.objects),
        "meshes": len(bpy.data.meshes),
        "drawn": [o.name for o in sc.objects if drawn.is_drawn(o)],
        "in_collection": sorted(o.name for o in col.objects) if col is not None else [],
        "excluded": sorted(o.name for o in sc.objects if o.get(build.PROP_EXCLUDED)),
    }


def stops_now(item):
    out = [drawn.world_spot(item.a_part, item.a_point, item.a_dir)[0]]
    out += [drawn.world_spot(c.part, c.point, c.dir)[0] for c in item.clips]
    return out + [drawn.world_spot(item.b_part, item.b_point, item.b_dir)[0]]


def passes_stops(sc, item, tol=END_TOL):
    line = flex.shape_now(sc, item)
    assert len(line) and np.all(np.isfinite(line)), "the hose's line is empty or not finite"
    for k, p in enumerate(stops_now(item)):
        assert np.linalg.norm(line - p, axis=1).min() < tol, (k, np.linalg.norm(line - p, axis=1).min())
    return line


@pytest.fixture()
def hoses(folder):
    """The hoses model: joints with the maker's travel as limits, the CAD hoses out of the list and hidden (they lie
    on the fittings, as the picker hides the part it replaces)."""
    sc = load(folder, HOSES_A)
    flex.set_up_test_hoses(sc)
    while len(sc.fresing.flex):
        flex.remove(sc, 0)
    luff, slide = joints.find(sc, "Luff"), joints.find(sc, "Slide")
    luff.rot_min, luff.rot_max, luff.use_limits = math.radians(-20), math.radians(20), True
    slide.slide_min, slide.slide_max, slide.use_limits = -0.45, 0.45, True
    for n in CAD_HOSES:
        logic.set_visible_flags(named(sc, n), True)
    update()
    return sc


def valve_c_top(sc):
    return click(sc, (1.292, -0.209, 1.0), (0, 0, -1), "FITTING VALVE C")


def fitting_arm(sc):
    return click(sc, (3.002, -0.9, 1.8), (0, 1, 0), "FITTING ARM")


# ---------------------------------------------------------------------------
# clicks
# ---------------------------------------------------------------------------

def test_a_click_on_something_that_is_no_part_is_refused_in_words(hoses):
    sc = hoses
    empty = bpy.data.objects.new("Just an empty", None)
    sc.collection.objects.link(empty)
    for ob in (None, empty, joints.find(sc, "Luff").motion):
        with pytest.raises(drawn.DrawError):
            drawn.spot(ob, 0, (0, 0, 0), (0, 0, 1))


def test_the_same_small_face_clicked_twice_at_two_points_is_one_click_and_nothing_stays(hoses):
    sc = hoses
    before = snapshot(sc)
    a1 = valve_c_top(sc)
    a2 = click(sc, (1.286, -0.215, 1.0), (0, 0, -1), "FITTING VALVE C")         # same face, 8 mm away
    assert np.allclose(a1["point"], a2["point"], atol=1e-6)                       # (a small face: its middle)
    with pytest.raises(flex.FlexError):
        flex.draw_hose(sc, [a1, a2])
    assert snapshot(sc) == before


def test_two_ends_on_one_big_face_make_an_arch(hoses):
    sc = hoses
    a = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    b = click(sc, (2.55, -0.36, 2.5), (0, 0, -1), "BASE")
    item, _n = flex.draw_hose(sc, [a, b])
    assert np.isfinite(item.length) and item.length > 0.9
    line = passes_stops(sc, item)
    assert line[:, 2].max() > 0.3 + 0.02                                          # it rises off the base
    assert flex.status(sc, item)[1] == "OK"


def test_a_clip_behind_end_b_and_a_clip_on_the_fitting_itself(hoses):
    sc = hoses
    a, b = valve_c_top(sc), fitting_arm(sc)
    behind = click(sc, (3.45, -0.36, 2.5), (0, 0, -1), "BASE")                   # past end B along x
    side = click(sc, (1.29, -0.9, 0.61), (0, 1, 0), "FITTING VALVE C")           # end A's own fitting, its side
    before = snapshot(sc)
    for spots in ([a, behind, b], [a, side, b]):
        try:
            item, _n = flex.draw_hose(sc, spots)
        except flex.FlexError:
            assert snapshot(sc) == before                                         # refused: nothing stays
            continue
        assert np.isfinite(item.length) and len(item.clips) == 1
        assert np.all(np.isfinite(np.array(item["shares"]))) and (np.array(item["shares"]) > 0).all()
        for luff in (0.0, math.radians(15)):
            set_joint(sc, "Luff", luff)
            passes_stops(sc, item)
        set_joint(sc, "Luff", 0.0)
        flex.remove(sc, flex.index_of(sc, item))
        assert snapshot(sc) == before


def test_a_clip_on_a_round_face_runs_along_its_axis(hoses):
    sc = hoses
    gland = click(sc, (1.07, 1.05, 2.5), (0, 0, -1), "SLIDE GLAND")              # a round stub along +X
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), gland, fitting_arm(sc)])
    assert len(item.clips) == 1
    p, d = drawn.world_spot(item.clips[0].part, item.clips[0].point, item.clips[0].dir)
    assert np.allclose(p, (1.075, 1.05, 1.86), atol=0.0005)                       # on its axis, at its end
    assert abs(d[0]) == pytest.approx(1.0, abs=1e-6)
    for slide in (0.0, 0.36):
        set_joint(sc, "Slide", slide)
        line = passes_stops(sc, item)
        k = int(np.argmin(np.linalg.norm(line - drawn.world_spot(item.clips[0].part, item.clips[0].point,
                                                                   item.clips[0].dir)[0], axis=1)))
        t = line[min(k + 1, len(line) - 1)] - line[max(k - 1, 0)]
        assert abs(t[0]) / np.linalg.norm(t) > 0.99                               # it passes along the axis


def test_end_b_back_on_the_fitting_of_end_a_after_a_clip(hoses):
    sc = hoses
    a = valve_c_top(sc)
    clip = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    before = snapshot(sc)
    try:
        item, _n = flex.draw_hose(sc, [a, clip, dict(a)])
    except flex.FlexError:
        assert snapshot(sc) == before
        return
    assert np.isfinite(item.length) and item.length > 0.0
    passes_stops(sc, item)


def test_a_fitting_on_a_part_that_moves_out_of_reach_says_too_short(hoses):
    sc = hoses
    slide = joints.find(sc, "Slide")
    slide.use_limits = False
    a = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    b = click(sc, (0.84, 0.96, 1.5), (0, 0, -1), "SLIDE CARRIAGE")
    item, notes = flex.draw_hose(sc, [a, b])
    assert any("limits" in n for n in notes), notes                               # the brief: no limits -> said
    length = item.length
    set_joint(sc, "Slide", 9.0)                                                   # 9 m away: far out of reach
    words, level = flex.status(sc, item)
    assert level == "WARN" and "short" in words.lower(), (words, level)
    line = flex.shape_now(sc, item)
    assert np.all(np.isfinite(line))
    assert item.length == length                                                  # it never stretches itself
    set_joint(sc, "Slide", 0.0)
    assert flex.status(sc, item) == ("follows the motion", "OK")


def test_the_length_typed_too_short_warns_and_stays_finite(hoses):
    sc = hoses
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)])
    item.length = 0.6                                                             # ends ~1.65 m apart
    flex.refresh(sc, force=True)
    words, level = flex.status(sc, item)
    assert level == "WARN" and "short" in words.lower(), (words, level)
    assert np.all(np.isfinite(flex.shape_now(sc, item)))


# ---------------------------------------------------------------------------
# parts that go
# ---------------------------------------------------------------------------

def test_the_part_an_end_or_clip_sits_on_deleted_by_the_user(hoses):
    sc = hoses
    clip = click(sc, (0.84, 0.96, 1.5), (0, 0, -1), "SLIDE CARRIAGE")
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), clip, fitting_arm(sc)])
    name, obj = item.name, item.part.name
    bpy.data.objects.remove(named(sc, "SLIDE CARRIAGE"), do_unlink=True)
    update()
    flex.refresh(sc)
    item = flex.find(sc, name)
    words, level = flex.status(sc, item)
    assert level == "ERROR" and "clip" in words, words
    set_joint(sc, "Luff", math.radians(10))                                       # no crash while posing
    bpy.data.objects.remove(named(sc, "FITTING ARM"), do_unlink=True)
    update()
    set_joint(sc, "Luff", math.radians(-10))
    item = flex.find(sc, name)
    assert flex.status(sc, item)[1] == "ERROR"
    ob = bpy.data.objects.get(obj)                                                # it keeps its last place
    assert ob is not None and len(ob.data.vertices) > 0
    assert flex.default_size(sc, item)                                            # says why, never raises
    flex.remove(sc, flex.index_of(sc, item))
    assert obj not in bpy.data.objects and not len(sc.fresing.flex)


def test_the_drawn_object_deleted_by_the_user_then_removed_shows_the_cad_hose(hoses):
    sc = hoses
    cad = named(sc, "HYDRAULIC HOSE ARM")
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)], replace=cad)
    assert cad.get(build.PROP_EXCLUDED)
    name = item.name
    bpy.data.objects.remove(item.part, do_unlink=True)                            # Delete in the 3D view
    update()
    flex.refresh(sc)
    set_joint(sc, "Luff", math.radians(5))
    item = flex.find(sc, name)
    assert flex.status(sc, item)[1] == "ERROR"
    flex.remove(sc, flex.index_of(sc, item))
    assert not cad.get(build.PROP_EXCLUDED) and not cad.hide_render and drawn.REPLACED not in cad


# ---------------------------------------------------------------------------
# replacing
# ---------------------------------------------------------------------------

def test_a_cad_hose_excluded_before_stays_hidden_when_the_drawn_one_goes(hoses):
    sc = hoses
    cad = named(sc, "HYDRAULIC HOSE ARM")
    logic.exclude([cad], True)                                                    # the user hid it for good
    item, notes = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)], replace=cad)
    assert not notes and cad.get(drawn.REPLACED) == item.name
    flex.remove(sc, flex.index_of(sc, item))
    assert cad.get(build.PROP_EXCLUDED) and cad.hide_render and not cad.visible_get()
    assert drawn.REPLACED not in cad and drawn.WAS_EXCLUDED not in cad


def test_two_drawn_hoses_cannot_both_replace_one_cad_hose(hoses):
    sc = hoses
    cad = named(sc, "HYDRAULIC HOSE ARM")
    one, _n = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)], replace=cad)
    one_name = one.name
    a2 = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    b2 = click(sc, (2.55, -0.36, 2.5), (0, 0, -1), "BASE")
    two, notes = flex.draw_hose(sc, [a2, b2], replace=cad)
    assert notes and "already" in notes[0]
    assert not len(two.replaces) and cad.get(drawn.REPLACED) == one_name
    flex.remove(sc, flex.index_of(sc, two))                                       # not its to show again
    assert cad.get(build.PROP_EXCLUDED)
    flex.remove(sc, flex.index_of(sc, flex.find(sc, one_name)))
    assert not cad.get(build.PROP_EXCLUDED)


def test_replacing_a_drawn_object_is_refused_in_a_note(hoses):
    sc = hoses
    one, _n = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)])
    a2 = click(sc, (1.8, -0.36, 2.5), (0, 0, -1), "BASE")
    b2 = click(sc, (2.55, -0.36, 2.5), (0, 0, -1), "BASE")
    _two, notes = flex.draw_hose(sc, [a2, b2], replace=one.part)
    assert notes
    assert not one.part.get(build.PROP_EXCLUDED) and drawn.REPLACED not in one.part


# ---------------------------------------------------------------------------
# keeping it: save / open, model update, Build, undo
# ---------------------------------------------------------------------------

def test_save_and_open_keeps_the_clips_on_their_moving_parts(hoses, tmp_path):
    sc = hoses
    c1 = click(sc, (0.84, 0.96, 1.5), (0, 0, -1), "SLIDE CARRIAGE")              # a clip that slides
    c2 = click(sc, (1.8, -1.5, 1.86), (0, 1, 0), "ARM")                           # a clip that luffs
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), c1, c2, fitting_arm(sc)])
    name, shares, length = item.name, list(item["shares"]), item.length
    path = str(tmp_path / "clips.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    item = flex.find(sc, name)
    assert item is not None and len(item.clips) == 2 and item.length == pytest.approx(length)
    assert np.allclose(list(item["shares"]), shares)
    assert [c.part.get(build.PROP_NAME) for c in item.clips] == ["SLIDE CARRIAGE", "ARM"]
    for luff, slide in ((math.radians(12), 0.3), (math.radians(-12), -0.3)):
        joints.set_value(joints.find(sc, "Luff"), luff)
        set_joint(sc, "Slide", slide)
        line = passes_stops(sc, item)
        assert HS.polyline_length(line) == pytest.approx(length, rel=0.003)


def test_model_update_where_an_end_part_is_gone_keeps_the_hose_and_says_so(folder):
    sc = load(folder, HOSES_B)
    flex.set_up_test_hoses(sc)
    while len(sc.fresing.flex):
        flex.remove(sc, 0)
    for n in CAD_HOSES:
        logic.set_visible_flags(named(sc, n), True)
    update()
    lamp = click(sc, (3.6, 0.6, 3.0), (0, 0, -1), "ARM.LAMP")                     # only in revision B
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), lamp], soft=True, name="Lamp cable")
    obj, radius = item.part.name, 0.5 * item.diameter
    shown = HS.resample(flex.shape_now(sc, item), 4000)                           # what showed before the update
    root = next(r for r in build.model_roots(sc))
    assert bpy.ops.fresing.import_step(filepath=HOSES_A, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    item = flex.find(sc, "Lamp cable")
    assert item is not None, "the drawn cable was dropped by the model update"
    words, level = flex.status(sc, item)
    assert level == "ERROR" and "B" in words, words
    assert item.a_part.get(build.PROP_NAME) == "FITTING VALVE C"
    ob = bpy.data.objects.get(obj)
    assert ob is not None and len(ob.data.vertices)
    co = np.array([v.co for v in ob.data.vertices], dtype=float) @ np.array(ob.matrix_world)[:3, :3].T \
        + np.array(ob.matrix_world)[:3, 3]
    far = max(float(np.linalg.norm(shown - p, axis=1).min()) for p in co)
    assert far < radius + 0.002, far                                              # its last place
    set_joint(sc, "Luff", math.radians(8))                                        # no crash


def test_build_of_a_hose_whose_clip_slides(hoses):
    sc = hoses
    clip = click(sc, (0.84, 0.96, 1.5), (0, 0, -1), "SLIDE CARRIAGE")
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), clip, fitting_arm(sc)])
    anim = sc.fresing.animations.add()
    anim.name, anim.tail, anim.fps = "Slide", 0.0, "25"
    for j, start, to in (("Slide", 0.0, 0.36), ("Luff", 1.0, math.radians(-15))):
        blk = anim.blocks.add()
        blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", j, start, 1.0, "LINEAR"
        blk.use_from = True
        if j == "Slide":
            blk.to_dist = to
        else:
            blk.to_angle = to
    r = animation.bake(sc, anim)
    assert not r["warnings"], r["warnings"]
    seen = []
    for f in (1, 14, 26, 40, 51):
        sc.frame_set(f)
        passes_stops(sc, item)
        seen.append(stops_now(item)[1][0])
    assert max(seen) - min(seen) > 0.3                                            # the clip did move with the slide


def test_undo_after_a_draw(hoses):
    sc = hoses
    try:
        bpy.ops.ed.undo_push(message="before")
    except RuntimeError as exc:
        pytest.skip(f"no undo stack in Blender as a module: {exc}")
    item, _n = flex.draw_hose(sc, [valve_c_top(sc), fitting_arm(sc)])
    bpy.ops.ed.undo_push(message="drawn")
    try:
        r = bpy.ops.ed.undo()
    except RuntimeError as exc:
        pytest.skip(f"ed.undo cannot run in Blender as a module: {exc}")
    if r != {"FINISHED"}:
        pytest.skip(f"ed.undo did nothing in Blender as a module: {r}")
    sc = bpy.context.scene
    assert not len(sc.fresing.flex) and not drawn.drawn_objects(sc)
    assert bpy.ops.ed.redo() == {"FINISHED"}                                      # and back again: it still works
    sc = bpy.context.scene
    flex.forget()
    item = flex.find(sc, "Hose 1")
    assert item is not None and drawn.is_drawn(item.part) and len(drawn.drawn_objects(sc)) == 1
    set_joint(sc, "Luff", math.radians(12))
    assert flex.status(sc, item) == ("follows the motion", "OK")
    passes_stops(sc, item)


# ---------------------------------------------------------------------------
# the picker's own steps (no 3D view needed)
# ---------------------------------------------------------------------------

def test_the_picker_refuses_in_words_when_a_clicked_part_was_deleted_before_enter(hoses):
    sc = hoses
    ob, index, loc, normal = hover.cast(sc, bpy.context.evaluated_depsgraph_get(), Vector((0.84, 0.96, 1.5)),
                                        Vector((0, 0, -1)))
    a = valve_c_top(sc)
    fake = types.SimpleNamespace(_clicks=[(a["part"].name, *hover.cast(sc, bpy.context.evaluated_depsgraph_get(),
                                                                         Vector((1.292, -0.209, 1.0)),
                                                                         Vector((0, 0, -1)))[1:]),
                                          (ob.name, index, tuple(loc), tuple(normal))])
    assert len(ops_drawn._Picker._spots(fake, sc)) == 2
    bpy.data.objects.remove(ob, do_unlink=True)
    with pytest.raises(drawn.DrawError):
        ops_drawn._Picker._spots(fake, sc)


# ---------------------------------------------------------------------------
# drag chains
# ---------------------------------------------------------------------------

@pytest.fixture()
def chains(folder):
    sc = load(folder, CHAINS)
    flex.set_up_test_chains(sc)
    while len(sc.fresing.flex):
        flex.remove(sc, 0)
    x = joints.find(sc, "X")
    x.slide_min, x.slide_max, x.use_limits = -0.15, 0.15, True
    links = [o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM")]
    logic.exclude(links, True)
    update()
    return sc


def test_chain_brackets_on_one_part_or_on_one_line_are_refused_and_nothing_stays(chains):
    sc = chains
    before = snapshot(sc)
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")
    with pytest.raises(flex.FlexError):
        flex.draw_chain(sc, a, dict(a))
    with pytest.raises(flex.FlexError):                                            # same part, another point
        flex.draw_chain(sc, a, click(sc, (-0.06, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED"))
    beam = click(sc, (-0.5, -1, 0.6), (0, 1, 0), "BEAM")                          # front faces at one height,
    carriage = click(sc, (0.04, -1, 0.6), (0, 1, 0), "CARRIAGE")                  # one line along the travel
    with pytest.raises(flex.FlexError):
        flex.draw_chain(sc, beam, carriage)
    assert snapshot(sc) == before


def test_a_chain_drawn_before_the_axis_has_its_joint_says_so_and_draws(folder):
    sc = load(folder, CHAINS)                                                     # no joints made yet
    logic.exclude([o for o in build.iter_parts(sc) if build.logical_parent(o) == named(sc, "CHAIN X.ASM")], True)
    update()
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")       # the brackets of the X chain,
    b = click(sc, (-0.01, -1, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING")       # clicked as the author's test does
    item, notes = flex.draw_chain(sc, a, b)
    assert notes and "slide joint" in notes[0]                                    # the note the code has for this
    assert item.radius == pytest.approx(0.5 * (0.83 - 0.661), abs=0.002)
    pins = flex.pins_now(sc, item)
    assert len(pins) and np.all(np.isfinite(pins))


def test_flip_and_swap_twice_give_the_chain_back(chains):
    sc = chains
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")
    b = click(sc, (-0.01, -1, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING")
    item, _n = flex.draw_chain(sc, a, b)
    set_joint(sc, "X", 0.07)
    pins0 = flex.pins_now(sc, item).copy()
    frame0, parts0 = list(item.frame), (item.a_part.name, item.b_part.name)
    flex.flip_bend(sc, item)
    flex.flip_bend(sc, item)
    assert np.allclose(list(item.frame), frame0, atol=1e-6)
    flex.swap_ends(sc, item)
    flex.swap_ends(sc, item)
    assert (item.a_part.name, item.b_part.name) == parts0
    flex.refresh(sc, force=True)
    assert np.allclose(flex.pins_now(sc, item), pins0, atol=1e-5)


def test_build_of_a_drawn_chain_and_its_moving_bracket_dragged_too_far(chains):
    sc = chains
    a = click(sc, (-0.07, -1, 0.661), (0, 1, 0), "CHAIN BRACKET X FIXED")
    b = click(sc, (-0.01, -1, 0.83), (0, 1, 0), "CHAIN BRACKET X MOVING")
    item, _n = flex.draw_chain(sc, a, b)
    anim = sc.fresing.animations.add()
    anim.name, anim.tail, anim.fps = "Run X", 0.0, "25"
    blk = anim.blocks.add()
    blk.kind, blk.joint, blk.start, blk.duration, blk.easing = "JOINT", "X", 0.0, 1.0, "LINEAR"
    blk.use_from, blk.to_dist = True, 0.14
    r = animation.bake(sc, anim)
    assert not r["warnings"], r["warnings"]
    for f in (1, 13, 26):
        sc.frame_set(f)
        pins = flex.pins_now(sc, item)
        assert np.allclose(np.linalg.norm(np.diff(pins, axis=0), axis=1), item.pitch, atol=1e-6), f
        end = drawn.world_spot(item.b_part, item.b_point, (1, 0, 0))[0]
        assert np.linalg.norm(pins[-1] - end) < END_TOL, f
    animation.clear_keys(sc)
    joints.find(sc, "X").use_limits = False
    set_joint(sc, "X", 0.8)                                                       # far past its 12 links
    assert joints.get_value(joints.find(sc, "X")) == pytest.approx(0.8)
    words, level = flex.status(sc, item)
    assert level in ("WARN", "ERROR") and words != "follows the motion"
    assert np.all(np.isfinite(flex.pins_now(sc, item)))


# ---------------------------------------------------------------------------
# a cable route
# ---------------------------------------------------------------------------

@pytest.fixture()
def winch(folder):
    sc = load(folder, PATHS_A)
    logic.exclude([named(sc, "WIRE ROPE")], True)
    update()
    return sc


def sheave(sc, n):
    if n == 1:
        return hit(sc, (1.9104, 0.0, 3.0), (0, 0, -1), "SHEAVE 1")
    return hit(sc, (1.5, 0.0, 0.5), (0, 0, 1), "SHEAVE 2")


def drum(sc):
    return click(sc, (0.0, 0.0, 0.45), (1, 0, 0), "WINCH DRUM")


def contact_side(item, name):
    return [int(c.side) for c in item.contacts if c.part.get(build.PROP_NAME) == name]


def test_a_cable_with_the_same_sheave_clicked_twice_goes_round_its_other_side(winch):
    sc = winch
    start, s1, s2 = drum(sc), sheave(sc, 1), sheave(sc, 2)          # (clicked before: the drawn cable hides them)
    once, _n = paths.draw_cable(sc, start, [s1, s2], None, name="Once")
    side_once = contact_side(once, "SHEAVE 1")
    assert len(side_once) == 1 and paths.broken(sc, once) == ""
    before = snapshot(sc)
    try:
        twice, _n = paths.draw_cable(sc, start, [s1, s1, s2], None, name="Twice")
    except paths.PathError:
        assert snapshot(sc) == before                                             # refused in words: nothing stays
        return
    side_twice = contact_side(twice, "SHEAVE 1")
    assert len(side_twice) == 1 and side_twice[0] == -side_once[0], (side_once, side_twice)
    assert paths.broken(sc, twice) == ""


def deck(sc, y=0.0):
    return click(sc, (2.33, y, 1.0), (0, 0, -1), "BASE FRAME")                   # the deck's top, before the cradle


def test_a_cable_ending_on_a_flat_face_ends_there_and_follows_a_luff(winch):
    sc = winch
    end = deck(sc)
    item, _n = paths.draw_cable(sc, drum(sc), [sheave(sc, 1), sheave(sc, 2)], end, name="To the deck",
                                diameter=0.02)
    assert item.drawn and paths.broken(sc, item) == "" and paths.status(sc, item)[1] == "OK"
    want = np.asarray(end["point"]) + np.asarray(end["dir"]) * 0.01                # one radius off the face
    line = paths.shape_now(sc, item)
    assert len(line) and np.all(np.isfinite(line))
    assert min(np.linalg.norm(line[0] - want), np.linalg.norm(line[-1] - want)) < 0.002
    luff = joints.create(sc, "ROTATE", [named(sc, "A-FRAME.ASM")], Vector((1.5, 0.0, 0.73)), Vector((0, 1, 0)),
                         name="Luff")
    set_joint(sc, luff.name, math.radians(-8))
    item = paths.find(sc, "To the deck")
    assert paths.status(sc, item)[1] == "OK"
    line = paths.shape_now(sc, item)
    assert min(np.linalg.norm(line[0] - want), np.linalg.norm(line[-1] - want)) < 0.002     # the deck stays


def test_a_cable_ending_a_little_beside_the_sheave_plane(winch):
    sc = winch
    before = snapshot(sc)
    try:
        item, _n = paths.draw_cable(sc, drum(sc), [sheave(sc, 1)], deck(sc, 0.05), name="Beside")
    finally:
        if len(sc.fresing.cables) == 0:
            assert snapshot(sc) == before                                         # (refused: nothing stays)
    assert paths.broken(sc, item) == ""


def test_refused_cable_routes_leave_nothing_behind(winch):
    sc = winch
    before = snapshot(sc)
    rail_end = click(sc, (2.0, 0.33, 1.0), (0, 0, -1), "BASE FRAME")
    rail = hit(sc, (1.0, 0.33, 1.0), (0, 0, -1), "BASE FRAME")
    chute = hit(sc, (2.7, 0.0, 1.5), (0, 0, -1), "CHUTE")
    for wheels, e in (([rail], rail_end),                                         # a flat rail as a wheel
                      ([sheave(sc, 1), sheave(sc, 2), chute], deck(sc))):          # the end inside the chute's circle
        with pytest.raises(paths.PathError):
            paths.draw_cable(sc, drum(sc), wheels, e, replace=named(sc, "WIRE ROPE"))
        assert snapshot(sc) == before
    # refused after it was drawn (the drawn tube cannot be read): nothing stays either. (Until the fix of finding 3
    # an end beside the sheave's plane did this; now that is drawn, so the read is made to fail here.)
    real = paths.read_cad

    def refuse(*_a, **_k):
        raise paths.PathError("cannot be read")
    paths.read_cad = refuse
    try:
        with pytest.raises(paths.PathError):
            paths.draw_cable(sc, drum(sc), [sheave(sc, 1)], rail_end, replace=named(sc, "WIRE ROPE"))
    finally:
        paths.read_cad = real
    assert snapshot(sc) == before
    with pytest.raises(paths.PathError):
        paths.draw_cable(sc, None, [sheave(sc, 1)], rail_end)
    assert snapshot(sc) == before


def test_the_cable_picker_takes_a_click_on_a_flat_rail_top_as_the_end(winch):
    sc = winch
    dg = bpy.context.evaluated_depsgraph_get()
    d_ob, d_i, d_loc, d_n = hover.cast(sc, dg, Vector((0.0, 0.0, 0.45)), Vector((1, 0, 0)))
    s_ob, s_i, s_loc, s_n = hover.cast(sc, dg, Vector((1.9104, 0.0, 3.0)), Vector((0, 0, -1)))
    r_ob, r_i, r_loc, r_n = hover.cast(sc, dg, Vector((1.0, 0.33, 1.0)), Vector((0, 0, -1)))
    assert r_ob.get(build.PROP_NAME) == "BASE FRAME"
    assert drawn.spot(r_ob, r_i, r_loc, r_n)["round"] is False                    # the hover calls it flat
    fake = types.SimpleNamespace(_clicks=[(d_ob.name, d_i, tuple(d_loc), tuple(d_n)),
                                          (s_ob.name, s_i, tuple(s_loc), tuple(s_n))], _ended=False,
                                 _status=lambda *_a: None, _next_prompt=lambda *_a: "",
                                 _finish=lambda *_a: {"FINISHED"})
    try:
        ops_drawn.FRESING_OT_cable_draw._click(fake, bpy.context, r_ob, r_i, tuple(r_loc), tuple(r_n))
    except TypeError:                                                             # (went on to the wheel branch)
        pass
    assert fake._ended, "the rail's flat top was taken as a wheel, not as the cable's end"


def test_removing_a_drawn_cable_leaves_no_joint_or_object(winch):
    sc = winch
    before = snapshot(sc)
    item, _n = paths.draw_cable(sc, drum(sc), [sheave(sc, 1), sheave(sc, 2)], None, name="Free end",
                                replace=named(sc, "WIRE ROPE"))
    assert len(sc.fresing.joints) > len(before["joints"])
    paths.remove(sc, paths.index_of(sc, item))
    after = snapshot(sc)
    assert after["joints"] == before["joints"] and after["drawn"] == [] and after["cables"] == []
    assert named(sc, "WIRE ROPE").get(build.PROP_EXCLUDED)                        # excluded before: stays so
