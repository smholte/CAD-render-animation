"""Task 0156, independent tests in Blender (written from the brief and the Design by an agent that did not write the
code): the tour set "operator" (the test mill in its cabinet, tests/data/test_mill_cabinet.step) is built and its
animation baked once; the tests then read the result. The last tests change the project (operator hidden, Clear keys,
a Build with the hand, saving and opening) and run in this file's order.

Contact rule for "the person never passes through the machine": the evaluated (posed) person mesh is checked against
every shown mesh of the scene in world space (``BVHTree.overlap``) at every 2nd frame of the change and every 10th
frame of the walk. Left out: the tool copies (the hand holds them on purpose), the floor helper and the trolley
(its own test). Each overlapping person face is put on its nearest bone (the rig's posed bones); the only contact
allowed is the right hand with the door's own parts (the members of the door joint) while a door move runs
(``to_door`` … ``let_go`` and ``to_close`` … ``let_go2``, ±2 frames): that is the hand holding the handle.

Tests marked ``xfail(strict=True)`` show a fault found in the code (their reason says what).
"""

import collections
import math

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, clash, gcode, joints, machining, person_rig, tc_person, tour  # noqa: E402
from fresing_render.core import toolchange as TC  # noqa: E402
from fresing_render.core.tc_person import CRADLE as T_CRADLE  # noqa: E402  # noqa: E402

SID = "operator"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    folder = str(tmp_path_factory.mktemp("tour_operator"))
    out = tour.build_all(folder, "9.9.9", only=(SID,))
    assert not out["errors"], out["errors"]
    tour.open_set(folder, "9.9.9", SID)
    sc = bpy.context.scene
    a = sc.fresing.animations[tour.OPERATOR_ANIM]
    res = animation.bake(sc, a)
    info = {"scene": sc, "anim": a, "result": res, "folder": folder, "tmp": tmp_path_factory.mktemp("saved")}
    yield info
    fresing_render.unregister()


def _scene():
    return bpy.context.scene


def _timing(sc):
    v = list(gcode.settings(sc)["fr_op_times"])
    t0, length = v[0], v[1]
    door = tc_person.door_time(sc)
    keys = TC.person_keys(t0, length, door)
    return t0, length, door, keys


def _frame(sc, t):
    return 1.0 + t * sc.render.fps


def _span(sc):
    _t0, _l, _d, keys = _timing(sc)
    return {n: (a, b) for a, b, n in keys}


def _hidden_at(ob, f):
    """Whether the object is hidden for renders at frame ``f`` (its keys, else its flag)."""
    for fc in machining._fcurves(ob):
        if fc.data_path == "hide_render":
            return fc.evaluate(f) > 0.5
    return bool(ob.hide_render)


def _np4(M):
    return np.array([list(r) for r in M], float)


def _world_mesh(ob, dg):
    eo = ob.evaluated_get(dg)
    me = eo.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    M = _np4(eo.matrix_world)
    p = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    polys = [tuple(pp.vertices) for pp in me.polygons]
    eo.to_mesh_clear()
    return p, polys


def _copies(tag):
    return {int(o[tag]): o for o in bpy.data.objects if tag in o}


# ---------------------------------------------------------------------------
# the Build
# ---------------------------------------------------------------------------

def test_the_build_has_no_warnings(built):
    assert built["result"]["warnings"] == []


def test_the_operator_is_built_and_keyed(built):
    sc = _scene()
    ob = tc_person.operator(sc)
    assert ob is not None and ob.type == "MESH"
    assert tc_person._built(ob)
    rig = person_rig.rig_of(ob)
    assert rig is not None and machining._fcurves(rig), "the rig has no keys"
    assert tc_person.COLLECTION in {c.name for c in ob.users_collection}
    t0, length, door, keys = _timing(sc)
    assert length == pytest.approx(TC.person_min(door))      # the pause grew from 1 s to what the person needs
    assert door > 0
    assert tc_person.words(sc).startswith("The operator takes")
    # it walks from the start spot to the stand spot and stands there during the change
    stand = list(gcode.settings(sc)["fr_op_stand"])
    start = list(gcode.settings(sc)["fr_op_start"])
    sc.frame_set(1)
    assert np.allclose(np.array(ob.matrix_world.translation)[:2], start[:2], atol=0.03)
    sc.frame_set(int(round(_frame(sc, t0 + length / 2))))
    assert np.allclose(np.array(ob.matrix_world.translation)[:2], stand[:2], atol=0.03)
    assert not ob.hide_render


def test_carried_copies_are_shown_only_while_carried(built):
    sc = _scene()
    sp = _span(sc)
    t0, length, door, _k = _timing(sc)
    out_t, in_t = TC.person_events(t0, length, door)
    carried = _copies(tc_person.CARRY)
    assert set(carried) == {1, 2}
    when = {1: (out_t, sp["set"][1]), 2: (sp["take"][1], in_t)}
    for n, ob in carried.items():
        a, b = (_frame(sc, x) for x in when[n])
        shown = [f for f in range(1, sc.frame_end + 1) if not _hidden_at(ob, f)]
        assert shown, f"T{n} is never shown in the hand"
        assert a - 1 <= shown[0] and shown[-1] <= b + 1, (n, shown[0], shown[-1], a, b)
        assert len(shown) >= int(b - a) - 1
    # the spindle's own copies swap at the same moments
    t1, t2 = _in_spindle(1), _in_spindle(2)
    assert not _hidden_at(t1, _frame(sc, out_t) - 1) and _hidden_at(t1, _frame(sc, out_t) + 1)
    assert _hidden_at(t2, _frame(sc, in_t) - 1) and not _hidden_at(t2, _frame(sc, in_t) + 1)


def _in_spindle(n):
    """What shows tool n in the spindle (worker: since the review T1 is the model's own tool in its holder, not a
    drawn copy "FR tool T1"; the carried copy names it)."""
    return bpy.data.objects[_copies(tc_person.CARRY)[n]["fr_cnc_src"]]


def _at(sc, f):
    sc.frame_set(int(f))
    return bpy.context.evaluated_depsgraph_get()


def test_carried_copies_go_from_spindle_to_trolley_and_back(built):
    sc = _scene()
    carried = _copies(tc_person.CARRY)
    lying = _copies(tc_person.ON_TROLLEY)
    spindle = {1: _in_spindle(1), 2: _in_spindle(2)}
    for n in (1, 2):
        ob = carried[n]
        shown = [f for f in range(1, sc.frame_end + 1) if not _hidden_at(ob, f)]
        first, last = shown[0], shown[-1]
        src, dst = (spindle[n], lying[n]) if n == 1 else (lying[n], spindle[n])
        _at(sc, first)
        A = _np4(ob.matrix_world)
        S = _np4(tc_person._world(src))
        assert np.linalg.norm(A[:3, 3] - S[:3, 3]) < 0.012, f"T{n} at its first frame in the hand"
        assert np.allclose(A[:3, :3], S[:3, :3], atol=0.02)
        _at(sc, last)
        B = _np4(ob.matrix_world)
        D = _np4(tc_person._world(dst))
        assert np.linalg.norm(B[:3, 3] - D[:3, 3]) < 0.012, f"T{n} at its last frame in the hand"
        assert np.allclose(B[:3, :3], D[:3, :3], atol=0.02)


def test_the_tools_lie_on_the_trolley_s_top(built):
    sc = _scene()
    sp = _span(sc)
    tr = tc_person.trolley(sc)
    assert tr is not None and not tr.hide_render
    top = tc_person._trolley_top(sc, tr, 0.0)
    lying = _copies(tc_person.ON_TROLLEY)
    assert set(lying) == {1, 2}
    f_set, f_take = _frame(sc, sp["set"][1]), _frame(sc, sp["take"][1])
    assert _hidden_at(lying[1], 1) and _hidden_at(lying[1], f_set - 2) and not _hidden_at(lying[1], f_set + 2)
    assert not _hidden_at(lying[2], 1) and not _hidden_at(lying[2], f_take - 2) and _hidden_at(lying[2], f_take + 2)
    assert not _hidden_at(lying[1], sc.frame_end)
    dg = _at(sc, f_set + 3)
    pts = []
    for n, ob in lying.items():
        p, _ = _world_mesh(ob, dg)
        # (worker: on cradles since the review's fault 3, its lowest point CRADLE above the top)
        gap = p[:, 2].min() - top - T_CRADLE
        assert -0.001 <= gap <= 0.006, f"T{n}: {1000 * (p[:, 2].min() - top):.1f} mm above the top"
        pts.append(p)
    # the two tools do not lie in each other
    b1 = BVHTree.FromPolygons([Vector(v) for v in pts[0]], _world_mesh(lying[1], dg)[1])
    b2 = BVHTree.FromPolygons([Vector(v) for v in pts[1]], _world_mesh(lying[2], dg)[1])
    assert not b1.overlap(b2)


def test_the_tools_do_not_hang_over_the_trolley_s_edge(built):
    sc = _scene()
    sp = _span(sc)
    tr = tc_person.trolley(sc)
    dg = _at(sc, _frame(sc, sp["set"][1]) + 3)
    inv = np.linalg.inv(_np4(tr.matrix_world))
    tp, _ = _world_mesh(tr, dg)
    tl = tp @ inv[:3, :3].T + inv[:3, 3]
    top = tc_person._trolley_top(sc, tr, 0.0)
    deck = tl[tl[:, 2] > top - 0.01 - _np4(tr.matrix_world)[2, 3]]          # the top's own points
    lo, hi = deck.min(0), deck.max(0)
    for n, ob in _copies(tc_person.ON_TROLLEY).items():
        p, _ = _world_mesh(ob, dg)
        loc = p @ inv[:3, :3].T + inv[:3, 3]
        out = np.maximum(lo[:2] - loc[:, :2], loc[:, :2] - hi[:2]).max()
        assert out <= 0.005, f"T{n} reaches {out * 1000:.0f} mm over the trolley's edge"


def test_the_door_opens_and_closes(built):
    sc = _scene()
    sp = _span(sc)
    j = tc_person.door_joint(sc)
    assert j is not None and j.name == "Door"
    door = bpy.data.objects["SLIDING DOOR"]

    def value(t):
        sc.frame_set(int(round(_frame(sc, t))))
        return joints.get_value(j), door.matrix_world.translation.x

    v0, x0 = value(sp["open"][0] - 0.3)
    v1, x1 = value(sp["open"][1] + 0.1)
    v2, x2 = value(sp["close"][0] - 0.1)
    v3, x3 = value(sp["close"][1] + 0.1)
    assert v0 == pytest.approx(0.0, abs=1e-4) and v3 == pytest.approx(0.0, abs=1e-4)
    assert v1 == pytest.approx(0.53, abs=1e-4) and v2 == pytest.approx(0.53, abs=1e-4)
    assert x1 - x0 == pytest.approx(0.53, abs=1e-3) and x3 == pytest.approx(x0, abs=1e-4)
    assert value(sp["reach"][1])[0] == pytest.approx(0.53, abs=1e-4)          # open while the tool is changed


def _bones(rig, dg):
    er = rig.evaluated_get(dg)
    M = er.matrix_world
    return {pb.name: (np.array(M @ pb.head), np.array(M @ pb.tail)) for pb in er.pose.bones}


def _nearest_bone(p, bones):
    best = (math.inf, None)
    for n, (h, t) in bones.items():
        d = t - h
        u = float(np.clip(np.dot(p - h, d) / max(1e-12, float(np.dot(d, d))), 0.0, 1.0))
        dist = float(np.linalg.norm(h + d * u - p))
        if dist < best[0]:
            best = (dist, n)
    return best[1]


def _contacts(sc, frames, others):
    """{(object, bone): [frames]} where the posed person mesh overlaps a shown object."""
    ob = tc_person.operator(sc)
    rig = person_rig.rig_of(ob)
    hits = collections.defaultdict(list)
    for f in frames:
        dg = _at(sc, f)
        pp, ppoly = _world_mesh(ob, dg)
        lo, hi = pp.min(0) - 0.02, pp.max(0) + 0.02
        bp = BVHTree.FromPolygons([Vector(v) for v in pp], ppoly)
        bones = None
        for o in others:
            if o.hide_render or o.hide_viewport:
                continue
            eo = o.evaluated_get(dg)
            bb = np.array([tuple(eo.matrix_world @ Vector(c)) for c in eo.bound_box])
            if (bb.max(0) < lo).any() or (bb.min(0) > hi).any():
                continue
            q, qpoly = _world_mesh(o, dg)
            ov = bp.overlap(BVHTree.FromPolygons([Vector(v) for v in q], qpoly))
            if ov:
                bones = bones or _bones(rig, dg)
                for bn in {_nearest_bone(pp[list(ppoly[i])].mean(0), bones) for i, _j in ov}:
                    hits[(o.name, bn)].append(f)
    return hits


def _check_frames(sc):
    t0, length, _d, _k = _timing(sc)
    f_lo, f_hi = int(_frame(sc, t0 - 0.5)), int(_frame(sc, t0 + length + 0.5))
    return sorted(set(range(f_lo, f_hi + 1, 2)) | {f for f in range(1, sc.frame_end + 1, 10)})


def test_the_person_does_not_pass_through_the_machine(built):
    sc = _scene()
    ob = tc_person.operator(sc)
    tr = tc_person.trolley(sc)
    others = [o for o in sc.objects if o.type == "MESH" and o is not ob and o is not tr and not o.get("fr_helper")
              and o.get(gcode.TAG) != "tool"]
    door_parts = {o.name for o in tc_person._members(tc_person.door_joint(sc))}
    assert "SLIDING DOOR" in door_parts
    _t0, _l, _d, keys = _timing(sc)
    door_frames = [(_frame(sc, a) - 2, _frame(sc, b) + 2) for a, b, n in keys if n in tc_person.core.DOOR_MOVES]
    # (worker: the right hand may also touch the tool it holds while it is still in the spindle – T1 is a part of the
    # model since the review, from its grip until it comes out)
    held = _in_spindle(1).name
    sp = {n: (a, b) for a, b, n in keys}
    out_t, _in = TC.person_events(*_timing(sc)[:3])
    hold_frames = [(_frame(sc, sp["reach"][1]) - 2, _frame(sc, out_t) + 2)]
    hits = _contacts(sc, _check_frames(sc), others)
    bad = {}
    for (name, bone), frames in hits.items():
        if name in door_parts and bone == "r_hand":
            frames = [f for f in frames if not any(a <= f <= b for a, b in door_frames)]
        if name == held and bone == "r_hand":
            frames = [f for f in frames if not any(a <= f <= b for a, b in hold_frames)]
        if frames:
            bad[(name, bone)] = frames[:4]
    assert not bad, bad


def test_the_hand_stays_out_of_the_trolley(built):
    sc = _scene()
    tr = tc_person.trolley(sc)
    hits = _contacts(sc, _check_frames(sc), [tr])
    assert not hits, {k: v[:4] for k, v in hits.items()}


def test_the_fist_closes_on_the_tool(built):
    sc = _scene()
    sp = _span(sc)
    f = int(round(_frame(sc, sp["grip"][1])))
    dg = _at(sc, f)
    t1 = _in_spindle(1)
    assert not t1.hide_render
    q, _ = _world_mesh(t1, dg)
    W = _np4(t1.matrix_world)
    axis = W[:3, 2] / np.linalg.norm(W[:3, 2])
    centre = q.mean(0)
    pp, _ = _world_mesh(tc_person.operator(sc), dg)
    rel = pp - centre
    along = rel @ axis
    rad = np.linalg.norm(rel - np.outer(along, axis), axis=1)
    fist = pp[rad < 0.03]                                   # the fingers and palm round the tool's axis
    assert len(fist) > 20, "no hand round the tool's axis"
    fa = (fist - centre) @ axis
    tq = (q - centre) @ axis
    share = float(np.mean((fa >= tq.min()) & (fa <= tq.max())))
    assert share > 0.5, (f"only {share:.0%} of the fist ({fa.min() * 1000:.0f} … {fa.max() * 1000:.0f} mm) is "
                         f"along the tool ({tq.min() * 1000:.0f} … {tq.max() * 1000:.0f} mm along its axis)")
    # and what it holds shows below the spindle (the holder, not a stub of cutter inside the spindle's nose)
    sp_ob = bpy.data.objects["SPINDLE"]
    sq, _ = _world_mesh(sp_ob, dg)
    nose = float(((sq - centre) @ axis).min())
    assert float(np.median(fa)) < nose - 0.01


def test_the_clash_check_finds_nothing(built):
    sc = _scene()
    rows = clash.check(sc, store=False).rows
    assert not rows, [r.a + " / " + r.b for r in rows[:5]]
    add, _leave = tc_person._clash_hook(sc)
    assert tc_person.operator(sc) in add                     # the check did look at the operator


# ---------------------------------------------------------------------------
# the tests below change the project (in this order)
# ---------------------------------------------------------------------------

def _operator_things(sc):
    obs = [tc_person.operator(sc), tc_person.trolley(sc)]
    obs += list(_copies(tc_person.CARRY).values()) + list(_copies(tc_person.ON_TROLLEY).values())
    return [o for o in obs if o is not None]


def test_the_operator_can_be_hidden_for_a_shot(built):
    sc = _scene()
    sp = _span(sc)
    f_carry = int(round(_frame(sc, (sp["pull"][0] + sp["pull"][1]) / 2)))
    sc.fresing.operator_visible = False
    try:
        for f in (1, f_carry, int(_frame(sc, sp["take"][1])) + 3, sc.frame_end):
            sc.frame_set(f)
            shown = [o.name for o in _operator_things(sc) if not o.hide_render or not o.hide_viewport]
            assert not shown, (f, shown)
        add, _leave = tc_person._clash_hook(sc)
        assert not add
    finally:
        sc.fresing.operator_visible = True
    sc.frame_set(f_carry)
    assert not tc_person.operator(sc).hide_render
    assert not tc_person.trolley(sc).hide_render
    assert not _copies(tc_person.CARRY)[1].hide_render


def test_clear_keys_puts_the_operator_back(built):
    sc = _scene()
    ob = tc_person.operator(sc)
    home = list(ob[tc_person.HOME])
    animation.clear_keys(sc)
    ob = tc_person.operator(sc)
    assert ob is not None
    assert tc_person.HOME not in ob
    assert np.allclose(tuple(ob.location), home[:3], atol=1e-5)
    assert ob.rotation_euler.z == pytest.approx(home[3], abs=1e-5)
    rig = person_rig.rig_of(ob)
    assert not machining._fcurves(rig), "the rig still has keys"
    j = tc_person.door_joint(sc)
    assert joints.get_value(j) == pytest.approx(0.0, abs=1e-6)
    for n, o in _copies(tc_person.CARRY).items():
        assert o.hide_render, f"T{n}'s hand copy is shown after Clear keys"


def test_a_build_with_the_hand_hides_the_operator(built):
    sc = _scene()
    a = sc.fresing.animations[tour.OPERATOR_ANIM]
    blk = next(b for b in a.blocks if b.kind == "GCODE")
    blk.gcode_operator = "HAND"
    try:
        res = animation.bake(sc, a)
        assert res["warnings"] == []
        assert bpy.data.objects.get("FR hand") is not None
        for f in (1, sc.frame_end // 2, sc.frame_end):
            sc.frame_set(f)
            shown = [o.name for o in _operator_things(sc) if not o.hide_render]
            assert not shown, (f, shown)
        assert not tc_person._clash_hook(sc)[0]
    finally:
        blk.gcode_operator = "PERSON"


def _bake_with(**settings):
    sc = _scene()
    c = gcode.settings(sc)
    old = {k: getattr(c, k) for k in settings}
    for k, v in settings.items():
        setattr(c, k, v)
    try:
        return animation.bake(sc, sc.fresing.animations[tour.OPERATOR_ANIM])
    finally:
        for k, v in old.items():
            setattr(c, k, v)


def test_other_settings_build_without_warnings(built):
    for kw in ({"op_height": "1.65"}, {"op_button": False}, {"op_door": ""}, {"op_helmet": True}):
        res = _bake_with(**kw)
        assert res["warnings"] == [], kw
        assert not clash.check(_scene(), store=False).rows, kw
    _bake_with(op_door="")                               # no door: the change takes the person's time without one
    length = list(gcode.settings(_scene())["fr_op_times"])[1]
    assert length == pytest.approx(TC.person_min(0.0))


def test_a_tall_operator_builds_without_warnings(built):
    assert _bake_with(op_height="1.85")["warnings"] == []


def test_save_and_open_keeps_the_operator(built):
    sc = _scene()
    a = sc.fresing.animations[tour.OPERATOR_ANIM]
    res = animation.bake(sc, a)
    assert res["warnings"] == []
    sp = _span(sc)
    f_carry = int(round(_frame(sc, (sp["pull"][0] + sp["pull"][1]) / 2)))
    sc.frame_set(f_carry)
    before = np.array(tc_person.operator(sc).matrix_world.translation)
    path = str(built["tmp"] / "operator_saved.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = _scene()
    ob = tc_person.operator(sc)
    assert ob is not None and tc_person._built(ob)
    assert sc.fresing.animations[tour.OPERATOR_ANIM].blocks[0].gcode_operator == "PERSON"
    sc.frame_set(f_carry)
    assert np.allclose(np.array(ob.matrix_world.translation), before, atol=1e-5)
    assert not _copies(tc_person.CARRY)[1].hide_render
    res = animation.bake(sc, sc.fresing.animations[tour.OPERATOR_ANIM])
    assert res["warnings"] == []
    assert len([o for o in bpy.data.objects if o.get(tc_person.TAG) == "person"]) == 1     # not a second one
    assert len([o for o in bpy.data.objects if o.get(tc_person.TAG) == "trolley"]) == 1
    assert len(_copies(tc_person.CARRY)) == 2
