"""Task 0121: bug-hunt rows 4, 5, 8, 9, 10, 12 of task 0118 (hoses with vessel motion, the Assembly sequence preview,
old vessel-motion rigs). Each test failed before its fix."""
from __future__ import annotations

import math
import os
import time

import numpy as np
import pytest

from fresing_render.core import sequence as core
from fresing_render.core import vessel_motion as core_vm

HERE = os.path.dirname(__file__)
SEQUENCE = os.path.join(HERE, "data", "test_sequence.step")
HOSES_A = os.path.join(HERE, "data", "test_flex_hoses_a.step")


# ---------------------------------------------------------------------------
# no Blender
# ---------------------------------------------------------------------------

def _boxes(n, seed):
    rng = np.random.default_rng(seed)
    out = []
    for k in range(n):
        lo = rng.uniform(-1.0, 1.0, 3)
        hi = lo + rng.uniform(0.02, 0.6, 3)
        c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        out.append(core.Part(f"p{k}", c, bool(rng.random() < 0.3), k))
    return out


def _plan_pairwise(parts, st, blocked=None):
    """The plan as 0.2.92 worked it out, pair by pair (the reference for the vectorised one)."""
    centre = core.centre_of(parts)
    dirs = core.directions(parts, st, centre)
    if blocked is not None:
        blocked.dirs = dirs
    by_tree = sorted(range(len(parts)), key=lambda i: parts[i].index)

    def out_key(i):
        if st.direction == "CENTRE":
            return float(np.linalg.norm(parts[i].centre - centre))
        return core._span(np.asarray(parts[i].corners) - centre, dirs[i])[0]
    key = {i: out_key(i) for i in by_tree}
    rank = {i: n for n, i in enumerate(by_tree)}
    fast = sorted((i for i in by_tree if parts[i].fastener), key=lambda i: (-key[i], rank[i]))
    rest = sorted((i for i in by_tree if not parts[i].fastener), key=lambda i: (-key[i], rank[i]))
    seq = fast + rest
    if blocked is not None:
        ahead = {i: [j for j in seq if j != i and core._in_way(parts[i].corners, parts[j].corners, dirs[i])]
                 for i in seq}
        left, out = list(seq), []
        while left:
            here = set(left)
            pick = next((i for i in left if not any(j in here and blocked(i, j) for j in ahead[i])), left[0])
            out.append(pick)
            left.remove(pick)
        seq = out
    base = core.base_distance(parts, st, centre)
    gap = max(core.MIN_GAP, core.GAP * base)
    travel = {}
    for r in range(len(seq) - 1, -1, -1):
        i = seq[r]
        u = dirs[i]
        t = base
        if st.direction != "CENTRE":
            lo_i, _ = core._span(parts[i].corners, u)
            for k in seq[r + 1:]:
                if float(np.dot(dirs[k], u)) < core.SAME_WAY or not core._across(parts[i].corners,
                                                                                 parts[k].corners, u):
                    continue
                t = max(t, core._span(parts[k].corners, u)[1] + travel[k] + gap - lo_i)
        travel[i] = t
    return [(parts[i].name, tuple(np.round(dirs[i] * travel[i], 12))) for i in seq]


class _Blocked:
    """A made-up ``blocked``: i is blocked by j when j is bigger and lies across i's way (deterministic)."""
    dirs = None

    def __init__(self, parts):
        self.vol = [float(np.prod(np.ptp(np.asarray(p.corners), axis=0))) for p in parts]

    def __call__(self, i, j):
        return self.vol[j] > self.vol[i]


@pytest.mark.parametrize("direction", ["UP", "AXIS", "CENTRE"])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_vectorised_plan_matches_the_pair_by_pair_one(direction, seed):
    parts = _boxes(60, seed)
    st = core.Settings(direction=direction, axis=(0.3, -0.2, 0.9), by_size=bool(seed % 2), distance=0.4)
    for blocked in (None, _Blocked(parts)):
        ref = _plan_pairwise(parts, st, _Blocked(parts) if blocked is not None else None)
        got = [(m.name, tuple(np.round(m.offset, 12))) for m in sorted(core.plan(parts, st, blocked),
                                                                     key=lambda m: m.rank)]
        assert [g[0] for g in got] == [r[0] for r in ref]
        assert np.allclose([g[1] for g in got], [r[1] for r in ref], atol=1e-9)


def test_plan_of_260_parts_is_quick():
    parts = _boxes(260, 7)
    st = core.Settings(direction="AXIS", axis=(0.0, 0.0, 1.0))
    t0 = time.perf_counter()
    core.plan(parts, st, _Blocked(parts))
    took = time.perf_counter() - t0
    assert took < 0.5, f"{took:.2f} s"            # pair by pair (0.2.92): 1.5–3.9 s on the web machine


def test_the_rig_key_has_a_version():
    """Row 9: a rig made before task 0109's waves has a key without a version: it is never equal to today's."""
    st = core_vm.Settings()
    k = core_vm.key(st)
    assert k.startswith(f"v{core_vm.KEY_VERSION}|")
    assert k.split("|", 1)[1] != k


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = pytest.importorskip("bpy")
import addon_utils  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import fresing_render  # noqa: E402
from fresing_render.blender import animation, build, flex, joints, sequence, vessel_motion  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def addon():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield
    fresing_render.unregister()


def update():
    bpy.context.view_layer.update()


def load(tmp_path, path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    flex.forget()
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    assert bpy.ops.fresing.import_step(filepath=path, quality="draft") == {"FINISHED"}
    return sc


def vessel_on(sc, background="DECK"):
    s = sc.fresing
    s.env_detail = "DETAILED"
    s.background = background
    s.vessel.enabled = True
    update()
    assert vessel_motion.rig("vessel") is not None


def named(sc, name):
    return next(o for o in sc.objects if o.get(build.PROP_NAME) == name)


def seq_step(sc, **kw):
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Sequence", 0.0, "25"
    sc.fresing.animations_index = len(sc.fresing.animations) - 1
    b = a.blocks.add()
    b.kind = "SEQUENCE"
    u = named(sc, "SPINDLE.UNIT")
    b.target_uid, b.target_name = u[build.PROP_UID], u[build.PROP_NAME]
    b.seq_id = "t1"
    for k, v in kw.items():
        setattr(b, k, v)
    sequence.count(sc, b)
    return a, b


def keys_of(sc) -> dict:
    out = {}
    for ob in sc.objects:
        cb = animation._channelbag(ob, "OBJECT") if ob.animation_data else None
        if cb is None:
            continue
        for fc in cb.fcurves:
            if fc.data_path in ("location", "rotation_euler", "rotation_quaternion"):
                out[(ob.name, fc.data_path, fc.array_index)] = [tuple(k.co) for k in fc.keyframe_points]
    return out


def test_preview_left_on_at_a_model_update_is_not_kept(tmp_path):
    """Row 4: the parts a preview moved became free moves of the new revision."""
    sc = load(tmp_path, SEQUENCE)
    _a, b = seq_step(sc)
    b.seq_preview = 50.0
    update()
    assert any(sequence.PREVIEW in o for o in sc.objects)
    root = next(iter(build.model_roots(sc)))
    assert bpy.ops.fresing.import_step(filepath=SEQUENCE, quality="draft", update_root=root.name) == {"FINISHED"}
    update()
    assert not joints.free_moves(sc), sorted(joints.free_moves(sc))
    assert not any(sequence.PREVIEW in o for o in sc.objects)
    assert sc.fresing.animations[0].blocks[0].seq_preview == 0.0


def test_clear_keys_ends_the_preview(tmp_path):
    sc = load(tmp_path, SEQUENCE)
    _a, b = seq_step(sc)
    b.seq_preview = 60.0
    animation.clear_keys(sc)
    assert b.seq_preview == 0.0 and not any(sequence.PREVIEW in o for o in sc.objects)
    assert not joints.free_moves(sc)


def test_preview_keeps_its_plan_while_the_slider_moves(tmp_path, monkeypatch):
    """Row 8: every step of the slider planned the whole step again; the first touch took a built animation off
    without a word."""
    sc = load(tmp_path, SEQUENCE)
    a, b = seq_step(sc)
    animation.bake(sc, a)
    assert sc.fresing.anim_baked
    calls = []
    real = sequence.plan_now
    monkeypatch.setattr(sequence, "plan_now", lambda *x, **k: calls.append(1) or real(*x, **k))
    parts = sequence.movers(sc, named(sc, "SPINDLE.UNIT")).parts
    home = {o.name: o.matrix_world.copy() for o in parts}
    b.seq_preview = 10.0
    assert not sc.fresing.anim_baked and "took the built animation off" in sc.fresing.last_message
    assert b.seq_preview == 10.0
    took = []
    for v in (20.0, 35.0, 50.0, 80.0, 100.0):
        t0 = time.perf_counter()
        b.seq_preview = v
        took.append(time.perf_counter() - t0)
    assert len(calls) == 1, "planned once for the whole drag"
    assert max(took) < 0.2, took
    # the same places as planned afresh at 100 %
    at_end = {o.name: o.matrix_world.copy() for o in parts}
    b.seq_preview = 0.0
    for o in parts:
        assert (o.matrix_world.translation - home[o.name].translation).length < 1e-6
    b.seq_preview = 100.0
    assert len(calls) == 2
    for o in parts:
        assert (o.matrix_world.translation - at_end[o.name].translation).length < 1e-6
    # a changed setting plans again
    b.seq_distance = b.seq_distance + 0.05
    b.seq_by_size = False
    b.seq_preview = 90.0
    assert len(calls) == 3
    b.seq_preview = 0.0


def test_sequence_keys_do_not_depend_on_the_frame_build_is_pressed_at(tmp_path):
    """Row 12: with vessel motion on, places, "up" and the rays were measured on the tilted world."""
    sc = load(tmp_path, SEQUENCE)
    vessel_on(sc)
    a, _b = seq_step(sc, seq_direction="UP", seq_by_size=False, seq_distance=0.3)
    got = []
    for frame in (1, 70):
        animation.clear_keys(sc)
        sc.frame_set(frame)
        r = animation.bake(sc, a)
        assert not [w for w in r["warnings"] if "runs into" not in w]
        got.append(keys_of(sc))
    assert got[0].keys() == got[1].keys() and got[0]
    worst = max(abs(p[1] - q[1]) for k in got[0] for p, q in zip(got[0][k], got[1][k]))
    assert worst < 1e-5, f"{worst * 1000:.3f} mm"


def test_an_old_rig_is_built_again_on_load(tmp_path):
    """Row 9: the key had no version, so a rig worked out from the waves before task 0109 was never rebuilt."""
    sc = load(tmp_path, SEQUENCE)
    vessel_on(sc)
    v = vessel_motion.rig("vessel")
    now = v["fr_key"]
    import json
    old = json.loads(now)
    old["m"] = old["m"].split("|", 1)[1]                  # the key as 0.2.65 – 0.2.87 wrote it
    v["fr_key"] = json.dumps(old, sort_keys=True)
    path = str(tmp_path / "old.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    assert vessel_motion.rig("vessel")["fr_key"] == now


def hoses_with_vessel(tmp_path):
    sc = load(tmp_path, HOSES_A)
    flex.set_up_test_hoses(sc)
    vessel_on(sc, "SEA")
    s = sc.fresing
    s.vessel.strength = 200.0          # big motion: shows any lag clearly
    update()
    return sc


def tube_end_error(sc) -> float:
    """The furthest a drawn tube's end lies from its fitting (m), as Blender draws them now."""
    dg = bpy.context.evaluated_depsgraph_get()
    worst = 0.0
    for it in sc.fresing.flex:
        if it.kind != "HOSE" or not it.enabled:
            continue
        e = it.part.evaluated_get(dg)
        me = e.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        w = np.array(e.matrix_world, dtype=float)
        co = co.reshape(-1, 3).astype(float) @ w[:3, :3].T + w[:3, 3]
        c = co.reshape(-1, flex.SIDES, 3).mean(axis=1)
        for end, part, point in ((c[0], it.a_part, it.a_point), (c[-1], it.b_part, it.b_point)):
            want = np.array(part.matrix_world @ Vector(point))
            worst = max(worst, float(np.linalg.norm(end - want)))
    return worst


def test_built_hoses_follow_a_vessel_motion_change(tmp_path):
    """Row 5: after Build, a vessel-motion setting changed: the fittings moved, the tube ends stayed."""
    sc = hoses_with_vessel(tmp_path)
    sc.fresing.vessel.strength = 100.0
    a = sc.fresing.animations.add()
    a.name, a.tail, a.fps = "Move", 0.0, "25"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.easing = "JOINT", "Luff", 0.0, 2.0, "LINEAR"
    b.use_from = True
    b.to_angle = math.radians(10.0)
    animation.bake(sc, a)
    assert sc.fresing.anim_baked
    sc.frame_set(30)
    assert tube_end_error(sc) < 0.5e-3
    for change in (lambda v: setattr(v, "strength", 200.0), lambda v: setattr(v, "heading", "BEAM")):
        change(sc.fresing.vessel)
        for frame in (10, 30, 45):
            sc.frame_set(frame)
            assert tube_end_error(sc) < 0.5e-3, (frame, tube_end_error(sc))
    assert sc.fresing.anim_baked


def test_hoses_moved_as_one_body_are_not_solved_again(tmp_path):
    """Row 10: with vessel motion on and no Build, every hose was solved from scratch at every frame."""
    sc = hoses_with_vessel(tmp_path)
    sc.frame_set(1)
    flex.refresh(sc, force=True)
    n = sum(1 for it in sc.fresing.flex if it.enabled)
    s0, r0 = flex._STATE["solves"], flex._STATE["moved_rigid"]
    worst = 0.0
    for frame in range(2, 62):
        sc.frame_set(frame)
        worst = max(worst, tube_end_error(sc))
    solves, rigid = flex._STATE["solves"] - s0, flex._STATE["moved_rigid"] - r0
    assert solves + rigid == 60 * n
    assert solves <= 60 * n // 4, f"{solves} solves for {60 * n} hose-frames"
    assert worst < 0.5e-3, f"tube end {worst * 1000:.2f} mm from its fitting"
    # moved, the shape is what a solve gives (the sag is the same while the pair turns < 0.5 deg against gravity)
    moved = {it.name: flex.shape_now(sc, it).copy() for it in sc.fresing.flex if it.kind == "HOSE"}
    flex.refresh(sc, force=True)
    for it in sc.fresing.flex:
        if it.kind == "HOSE":
            d = float(np.abs(flex.shape_now(sc, it) - moved[it.name]).max())
            assert d < 2e-3, f"{it.name}: {d * 1000:.2f} mm from a fresh solve"
    # a joint that moves one end only is solved again
    s1 = flex._STATE["solves"]
    joints.set_value(joints.find(sc, "Slide"), 0.05)
    update()
    flex.refresh(sc)
    assert flex._STATE["solves"] > s1
