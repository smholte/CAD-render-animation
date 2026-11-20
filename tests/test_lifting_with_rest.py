"""Task 0214: the lifting plan used with the rest of the app (bug hunt 0209 groups B + C). Each test is a row's repeat
case and failed before the fix: a model update keeps the load (row 1), Build keeps the crane's plan pose (3), a crane's
model cannot be updated and a deleted crane is removed whole (4), place and box loads on a moving deck (11, 16), a crane
pose leaves hand-moved sub-assemblies (12), a renamed crane joint (14), a crane made again (15), past the chart (32), the
CoG symbol only where the plan shows (33), "an outrigger spread" (36). Blender as a Python module."""

from __future__ import annotations

import json
import math
import os
import shutil

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from mathutils import Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.core import lifting_library as LL, lifting_reach as LR  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "fresing_render", "data")
CRANE = os.path.join(DATA, "test_crane_a.step")


@pytest.fixture(scope="module", autouse=True)
def registered():
    mine = not hasattr(bpy.types.Scene, "fresing")
    if mine:
        fresing_render.register()
    yield
    if mine:
        bpy.ops.wm.read_homefile(use_empty=True)
        fresing_render.unregister()


def _BL():
    from fresing_render.blender import lifting as BL
    return BL


def _new(step=CRANE):
    BL = _BL()
    bpy.ops.wm.read_homefile(use_empty=True)
    from fresing_render.blender import workspaces
    workspaces.use_all(bpy.context.scene)
    sc = bpy.context.scene
    sc.fresing.out_folder = "/tmp/fr_lifting_rest_test"
    if step:
        assert bpy.ops.fresing.import_step(filepath=step, quality="draft") == {"FINISHED"}
    BL.forget()
    return sc


def _update():
    bpy.context.view_layer.update()


def _model_root(sc):
    from fresing_render.blender import build
    return next(r for r in build.model_roots(sc) if not r.get("fr_lifting"))


def _part(sc, name):
    from fresing_render.blender import build, logic
    return next(o for o in logic.descendants(_model_root(sc)) if o.get(build.PROP_NAME) == name)


def _close(a, b, tol=1e-4):
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float))) <= tol


def _vals_close(a: dict, b: dict, tol=1e-3):
    return a.keys() == b.keys() and all(abs(a[k] - b[k]) <= tol for k in a)


# ---------------------------------------------------------------------------------------------------------------------
# row 1: a model update keeps the load

def test_model_update_with_the_same_file_keeps_the_load():
    BL = _BL()
    sc = _new()
    c, ld, a = BL.set_up_example(bpy.context)
    assert a.ok, a.reason
    names0 = sorted(o.name for o in BL.load_parts(ld))
    cog0 = BL.cog_world(ld)
    use0 = BL.readout(sc, c, ld).use
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft", update_root=_model_root(sc).name) == {"FINISHED"}
    _update()
    BL.forget()
    ld = BL.plan(sc).loads[0]
    assert len(ld.parts) == 1 and all(r.obj is not None for r in ld.parts)
    assert len(BL.load_parts(ld)) == len(names0)
    assert BL.cog_world(ld) is not None and _close(BL.cog_world(ld), cog0, 1e-3), (BL.cog_world(ld), cog0)
    assert not BL.cog_by_hand(ld)
    assert BL.readout(sc, c, ld).use == pytest.approx(use0, abs=1e-6)
    # a CoG set by hand stays where it was set, and stays "by hand"
    mk = ld.marker
    M = mk.matrix_world.copy()
    M.translation = M.translation + Vector((0.1, 0.0, 0.0))
    mk.matrix_world = M
    _update()
    hand = BL.cog_world(ld)
    assert BL.cog_by_hand(ld)
    assert bpy.ops.fresing.import_step(filepath=CRANE, quality="draft", update_root=_model_root(sc).name) == {"FINISHED"}
    _update()
    ld = BL.plan(sc).loads[0]
    assert BL.cog_by_hand(ld)
    assert _close(BL.cog_world(ld), hand, 1e-3), (BL.cog_world(ld), hand)
    assert ld.marker.parent is not None and ld.marker.parent == ld.carrier


# ---------------------------------------------------------------------------------------------------------------------
# row 3: Build keeps the crane where the plan put it

def _hide_animation(sc):
    from fresing_render.blender import build
    a = sc.fresing.animations.add()
    a.name = "Hide"
    b = a.blocks.add()
    b.kind = "HIDE"
    b.target_uid = _part(sc, "BOOM.ASM").get(build.PROP_UID)
    b.start, b.duration = 0.0, 0.5
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    return a


@pytest.mark.parametrize("how", ["hook", "pose"])
def test_build_keeps_the_cranes_plan_pose(how):
    BL = _BL()
    from fresing_render.blender import animation
    sc = _new()
    c, ld, a = BL.set_up_example(bpy.context)
    anim = _hide_animation(sc)
    animation.bake(sc, anim)
    if how == "hook":
        p = BL.above_load(sc, ld) + np.array([0.0, 1.5, 0.5])
        assert BL.hook_to(sc, c, p, ld).ok
    else:
        assert BL.apply_pose(sc, c, "Working")
    want = BL.values(sc, c)
    animation.bake(sc, anim)
    sc.frame_set(1)
    _update()
    assert _vals_close(BL.values(sc, c), want), (BL.values(sc, c), want)
    animation.clear_keys(sc)
    assert _vals_close(BL.values(sc, c), want)


# ---------------------------------------------------------------------------------------------------------------------
# row 4: the crane's model is not updated; a crane whose model was deleted is removed whole

def test_crane_model_update_is_refused_and_a_deleted_crane_is_removed():
    BL = _BL()
    from fresing_render.blender import logic, reimport
    sc = _new(None)
    c = BL.place(bpy.context, os.path.join(LL.BUILTIN_DIR, "AT-40"))
    with pytest.raises(reimport.UpdateFailed, match="lifting plan"):
        reimport.update_model(bpy.context, c.root, "")
    assert BL.active_crane(sc) is not None
    p = BL.prefix(c)
    s = sc.fresing
    assert any(j.name.startswith(p) for j in s.joints) and c.reeved       # task 0232: the rope is reeved, not a cable
    for o in [c.root] + list(logic.descendants(c.root)):
        bpy.data.objects.remove(o, do_unlink=True)
    _update()
    assert BL.active_crane(sc) is None and BL.picked_crane(sc) is not None
    assert bpy.ops.fresing.lifting_remove("EXEC_DEFAULT") == {"FINISHED"}
    assert not BL.plan(sc).cranes
    assert not [j.name for j in s.joints if j.name.startswith(p)]
    assert not [x.name for x in s.poses if x.name.startswith(p)]
    assert not [x.name for x in s.cables if x.name.startswith(p)]
    assert not [x.name for x in s.cylinders if x.name.startswith(p)]
    assert BL.unique_name(sc, "AT-40") == "AT-40"


# ---------------------------------------------------------------------------------------------------------------------
# rows 11 + 16: a moving deck

def _deck_point(sc, xy):
    """The deck's top under ``xy`` as shown now (world)."""
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, *_ = sc.ray_cast(dg, Vector((xy[0], xy[1], 200.0)), Vector((0, 0, -1)))
    assert hit
    return np.array(loc)


def test_place_and_a_box_on_a_moving_deck_ride_with_it():
    import addon_utils
    BL = _BL()
    from fresing_render.blender import vessel_motion
    sc = _new()
    addon_utils.enable("cycles", default_set=True)
    s = sc.fresing
    s.background = "DECK"
    s.vessel.enabled = True
    _update()
    vessel_motion.sync(sc)
    assert vessel_motion.effective(sc) and vessel_motion.rig("pivot") is not None
    from fresing_render.blender import logic
    mn, mx = (np.asarray(v, float) for v in logic.update_bounds(sc))
    xy = (float(mx[0]) + 8.0, float(0.5 * (mn[1] + mx[1])))
    c = BL.place(bpy.context, os.path.join(LL.BUILTIN_DIR, "AT-40"), (xy[0], xy[1], 0.0), 0.0)
    sc.frame_set(60)
    _update()
    P = _deck_point(sc, (xy[0] + 3.0, xy[1]))       # a click on the deck beside the crane, as shown at frame 60
    BL.place_at(c, BL.rest_point(sc, P), 0.3)
    _update()
    got = np.array(c.root.matrix_world.translation)
    assert _close(got, P, 2e-3), (got, P)           # the crane stands where it was clicked (it was 0.34 m below)
    assert abs(BL.heading_of(c) - 0.3) < 1e-6
    # the box load at the 3D cursor, put on the deck at frame 60: it rides with the deck
    Q = _deck_point(sc, (xy[0] - 4.0, xy[1] + 2.0))
    sc.cursor.location = tuple(Q)
    ld = BL.new_box(sc, (1.0, 1.0, 1.0), 2.0)
    _update()
    box = ld.box
    assert any(con.name in vessel_motion.CONSTRAINTS for con in box.constraints)
    assert _close(box.matrix_world.translation, Q, 2e-3), (tuple(box.matrix_world.translation), Q)
    for f in (1, 30, 90, 150):
        sc.frame_set(f)
        _update()
        piv = np.array(vessel_motion.rig("pivot").matrix_world)
        rest = np.array(box.matrix_basis.translation)
        assert _close(box.matrix_world.translation, (piv @ np.r_[rest, 1.0])[:3], 1e-4), f


# ---------------------------------------------------------------------------------------------------------------------
# row 12: a crane pose used from 4 Motion > Poses or a Go to pose step leaves hand-moved sub-assemblies

def test_a_crane_pose_leaves_hand_moved_sub_assemblies():
    BL = _BL()
    from fresing_render.blender import animation, logic, states
    sc = _new()
    c = BL.place(bpy.context, os.path.join(LL.BUILTIN_DIR, "AT-40"), (12.0, 0.0, 0.0), math.pi)
    boom = _part(sc, "BOOM.ASM")
    logic.set_locked(boom, False)
    boom.location.x += 0.5
    _update()
    moved = np.array(boom.matrix_world.translation)
    assert states.apply_pose(sc, BL.prefix(c) + "Travel")
    _update()
    assert _close(boom.matrix_world.translation, moved), "Use pose moved the hand-moved boom back"
    a = sc.fresing.animations.add()
    a.name = "Go"
    b = a.blocks.add()
    b.kind, b.pose, b.start, b.duration = "POSE", BL.prefix(c) + "Working", 0.0, 0.5
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    animation.bake(sc, a)
    sc.frame_set(sc.frame_end)
    _update()
    assert _close(boom.matrix_world.translation, moved), "a Go to pose step moved the hand-moved boom back"
    # a pose saved in 4 Motion > Poses holds the free moves again
    p = states.save_pose(sc, BL.prefix(c) + "Travel")
    assert not p.joints_only


# ---------------------------------------------------------------------------------------------------------------------
# row 14: a renamed crane joint

def test_a_renamed_crane_joint_is_named_and_removed():
    BL = _BL()
    from fresing_render.blender import joints
    sc = _new()
    c, ld, a = BL.set_up_example(bpy.context)
    j = joints.find(sc, BL.prefix(c) + "Luff")
    j.name = "Luff"
    with pytest.raises(LR.ReachError, match="Luff"):
        BL.hook_to(sc, c, BL.above_load(sc, ld), ld)
    ro = BL.readout(sc, c, ld)
    assert isinstance(ro, str) and "Luff" in ro
    assert bpy.ops.fresing.lifting_hook_above() == {"CANCELLED"}
    BL.remove(sc, c)
    assert joints.find(sc, "Luff") is None


# ---------------------------------------------------------------------------------------------------------------------
# row 15: a crane made again with another hook block

def test_a_crane_made_again_is_noticed(tmp_path):
    BL = _BL()
    src = os.path.join(LL.BUILTIN_DIR, "AT-40")
    own = tmp_path / "AT-40"
    shutil.copytree(src, own)
    sc = _new(None)
    c = BL.place(bpy.context, str(own / "AT-40.json"), (0.0, 0.0, 0.0), 0.0)
    assert BL.file_changed(c) == ""
    p = BL.to_world(c, np.array([9000.0, 0.0, 3000.0]))
    data = json.loads((own / "AT-40.json").read_text(encoding="utf-8"))
    data["rig"]["hook"]["point"][2] = float(data["rig"]["hook"]["point"][2]) + 1000.0    # another hook block height
    (own / "AT-40.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.utime(own / "AT-40.json", (1e9 + 5, 1e9 + 5))
    BL.forget()
    assert "place it again" in BL.file_changed(c)
    with pytest.raises(LR.ReachError, match="place it again"):
        BL.hook_to(sc, c, p)
    assert isinstance(BL.readout(sc, c), str)


# ---------------------------------------------------------------------------------------------------------------------
# row 32: past the chart's longest radius

def test_hook_past_the_charts_radius_warns():
    BL = _BL()
    sc = _new(None)
    c = BL.place(bpy.context, os.path.join(LL.BUILTIN_DIR, "AT-40"), (0.0, 0.0, 0.0), 0.0)
    BL.apply_pose(sc, c, "Set up")
    longest = max(max(r for r in ch.radius if isinstance(r, (int, float))) for ch in BL.charts_of(c))
    got = None
    for extra in np.arange(0.5, 12.0, 0.5):
        for h in (-4.0, 0.0, 4.0, 8.0):
            a = BL.hook_to(sc, c, BL.to_world(c, np.array([(longest + extra) * 1000.0, 0.0, h * 1000.0])))
            if a.ok:
                got = a
                break
        if got:
            break
    if got is None:
        pytest.skip("the AT-40 does not reach past its chart")
    assert got.use is None and got.warning
    msg = BL.plan(sc).message
    assert "no crane use" in msg and "the crane's base" in msg, msg


# ---------------------------------------------------------------------------------------------------------------------
# row 33: the CoG symbol only where the plan shows

def test_cog_symbol_only_where_the_lifting_plan_shows():
    BL = _BL()
    from fresing_render.blender import workspaces
    sc = _new(None)
    workspaces.switch(sc, "Lifting plans")
    assert BL.cog_shown(sc)
    workspaces.switch(sc, "Client view")
    assert not BL.cog_shown(sc)
    workspaces.switch(sc, "CNC & machining")
    assert not BL.cog_shown(sc)
    workspaces.switch(sc, "All functions")
    assert BL.cog_shown(sc)


# ---------------------------------------------------------------------------------------------------------------------
# row 36: "an outrigger spread"

def test_an_outrigger_spread():
    it = LL.read_item(os.path.join(LL.BUILTIN_DIR, "AT-100"))
    charts = LL.charts_of(it)
    vals = LR.setup_values(charts)
    chart, note = LR.chart_for(charts, 30.0, {"outriggers": min(vals["outriggers"]) - 1.0})
    assert chart is None and "an outrigger spread" in note and "a outrigger" not in note
