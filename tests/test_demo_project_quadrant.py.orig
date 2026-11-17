"""Task 0145 (split from ``test_demo_project.py``): the demo's quadrant operation – shots 10 to 12, its wires,
its parts hidden until shot 9.

The demo project is made once per run and shared by these files (``tests/demo_made.py``, task 0145: the single file
had grown to ~35 min on GitHub); each file opens the saved project itself.
"""

import json  # noqa: F401
import math  # noqa: F401
import os  # noqa: F401
import shutil  # noqa: F401
import sys
import time  # noqa: F401

import numpy as np  # noqa: F401
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)                          # (demo_made: the made demo project, task 0145; demo_cps_check, 0126)

bpy = pytest.importorskip("bpy")
pytest.importorskip("OCP")

from demo_made import (VERSION, _cps_shot, _dense, _first_steps, _keys, _scene, _solved, _t9,  # noqa: E402,F401
                       animation_frame, made, paths_riders_parts)
from fresing_render.blender import demo  # noqa: E402


def test_the_quadrant_operation_shots_10_to_12(made):
    """Task 0082, the owner's steps 8–15: the handler tilts on to LOWER_TILT and the D hangs plumb (the sheet's hang
    tip); the A&R winch lowers it to 1.5 m over the seabed with the vessel creeping on; it tips towards flat and is
    set down on the seabed (task 0125: its lowest point, heaving with the vessel, never more than 5 cm into the seabed
    – measured on its mesh); as the hoist begins the second end is let go (its start and the gutter's turn) and settles
    onto the seabed; it comes back up, tilts back, travels back, the tensioners close and the cradles rise.
    Every frame from shot 9 on: the second end is exactly as long as it is (its sea end keeps it: nothing is paid out
    from shot 9 on; exactly in the solver's own measure, within 1 m – 0.5 % – along the drawn points' chords), with a
    path at every frame (task 0125: the D's gutter over horn A lets the horn go); where it leaves the gutter no point
    turns more than the gutter's own arc does (task 0125: no kink); the bend round the D's gutter never tighter than
    its MBR; the second end's CPS rides at its start, the pull head at the D's bar end, and on the seabed (not under
    it) once settled."""
    from mathutils import Vector

    from fresing_render.blender import animation, build, joints, paths, paths_sea
    sc = _scene()
    s = sc.fresing
    a = s.animations[demo.ANIM]
    said = animation.bake(sc, a)["warnings"]
    # task 0125: no "piles up 0.00 m", nothing about a wire that only comes onto its pulley later, no lost path
    assert not [w for w in said if "0.00 m" in w or "no longer touches 'HANDLER TOP PULLEY'" in w
                or "cannot go round" in w], said
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    q = d.sheet("route")["quadrant"]
    ids = [x.id for x in demo.STAGES]
    assert ids.index("shot_sea") < ids.index("quadrant_ops") < ids.index("shot_cps") < ids.index("shot_quadrant") \
        < ids.index("shot_lower") \
        < ids.index("shot_tip") < ids.index("shot_back") < ids.index("finish")
    steps = [b for b in a.blocks if b.kind == "JOINT"]
    t9 = _t9(a)
    tilts = [math.degrees(b.to_angle) for b in steps if b.joint == demo.TILT]
    assert tilts == pytest.approx([100.0, q["lower_tilt"], 0.0])
    lowers = [b.to_dist for b in sorted((b for b in steps if b.joint == demo.LOWER), key=lambda b: b.start)]
    assert lowers[0] > 25.0 and lowers[1] > lowers[0] and lowers[-1] == 0.0
    tips = [math.degrees(b.to_angle) for b in sorted((b for b in steps if b.joint == demo.TIP), key=lambda b: b.start)]
    assert tips[0] == pytest.approx(q["hang_tip"]) and tips[1] == pytest.approx(-q["lower_tilt"]) and tips[-1] == 0.0
    # from shot 9 on 'Cable travel' stands still: the second end follows it, nothing of it is paid out
    assert not [b for b in a.blocks if b.joint == demo.CABLE and b.start + b.duration > t9]
    assert sum(1 for b in a.blocks if "(x " in b.name) >= 4                 # the time-lapse captions
    se = paths.find(sc, demo.SECOND_ITEM)
    assert se.b_kind == "SEA" and paths.let_go_frame(se, "a") > 0
    let_go = paths.let_go_frame(se, "a")
    gutter = [i for i, c in enumerate(se.contacts) if c.part is not None and c.part.get(build.PROP_NAME) == "QUADRANT GUTTER"
              and c.kind != "ROLLER"]
    assert gutter and all(paths.let_go_frame(se, str(i)) == let_go for i in gutter)
    # the length, the path, the MBR round the gutter: every second frame from shot 9 on
    f9 = animation.frame_of(a, t9) + 1
    res, first = _solved(sc, se)
    bad = sorted(k + first for k in res["problems"] if k + first >= f9)
    assert not bad, bad
    # no kink where it leaves the gutter (or horn A) for the sea: the turn between neighbouring points within 3 m of
    # where the catenary starts is never more than the gutter's own arc's (a point every ~1.4°)
    sea_ = res["sea"]
    scale = res["scale"]
    worst_turn = 0.0
    # (shot 10 and shot 11 until the D tips flat; the D tipped flat over the seabed: open point of task 0125)
    lw_ = sorted((b for b in steps if b.joint == demo.LOWER), key=lambda b: b.start)
    tp_ = sorted((b for b in steps if b.joint == demo.TIP), key=lambda b: b.start)
    f_lo, f_tip = animation.frame_of(a, lw_[0].start) - 60, animation.frame_of(a, tp_[1].start)
    for k in range(f_lo - first, f_tip - first, 3):
        if not res["ok"][k]:
            continue
        P = np.asarray(res["points"][k]) * scale
        sk = np.asarray(res["s"][k]) * scale
        if float(sea_["h"][k]) < 0.5:                            # (the D at the seabed: the cable lies there)
            continue
        sT = sk[int(np.argmin(np.linalg.norm(P - np.asarray(sea_["T_part"][k]) * scale, axis=1)))]
        bend = float(sea_["kink"][k]) * 4.05                     # (the free bend's length, on the gutter's radius)
        near = np.flatnonzero((sk > sT - bend - 2.0) & (sk < sT + min(2.0, 0.3 * float(sea_["h"][k]))))
        Q = P[near]
        dv = np.diff(Q, axis=0)
        ln = np.linalg.norm(dv, axis=1)
        u = dv[ln > 1e-6] / ln[ln > 1e-6, None]
        if len(u) > 1:
            worst_turn = max(worst_turn, float(np.degrees(np.arccos(np.clip((u[1:] * u[:-1]).sum(1), -1, 1))).max()))
    assert worst_turn < 1.5, worst_turn                          # (the gutter's own arc: ~1.4° a point)
    # the solver's own length (its arc length along the drawn points) is the cable's: its sea end's mark + paid out
    # (from the D's travel's end on nothing is paid out; task 0126: while it travels the second end is hauled in)
    trav = next(b for b in a.blocks if b.kind == "JOINT" and b.joint == demo.TRAVEL and b.to_dist > 0)
    f_on = animation.frame_of(a, trav.start + trav.duration) + 1
    sc.frame_set(f_on)
    want = se.sea_mark + paths_sea.payout(sc, se)
    good = [k for k in range(f_on - first, len(res["ok"])) if res["ok"][k]]
    assert np.abs(np.asarray(res["length"])[good] - want).max() < 0.001
    quad = d.uid(q["uid"])
    arc = d.sheet("route")["second_end"]["route"]["segments"][0]
    sc.frame_set(1)                                              # the D in its CAD place: model -> its own frame
    to_quad = np.linalg.inv(np.array(quad.matrix_world)) @ np.array(d.root().matrix_world)
    worst_len, worst_r = 0.0, 1e9
    bed = paths_sea.bottom_z(sc, se)
    for f in range(f9, int(sc.frame_end) + 1, 2):
        sc.frame_set(f)
        P = paths.shape_now(sc, se)
        assert np.isfinite(P).all()
        L = float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())
        worst_len = max(worst_len, abs(L - (se.sea_mark + paths_sea.payout(sc, se))))
        if f < let_go:                                           # round the gutter: its circle, carried by the D
            W = np.array(quad.matrix_world) @ to_quad
            c = W @ np.r_[np.array(arc["centre"]) / 1000.0, 1.0]
            n = W[:3, :3] @ np.array(arc["normal"])
            rel = P - c[:3]
            h = rel @ n
            on = (np.abs(np.linalg.norm(rel - np.outer(h, n), axis=1) - arc["radius"] / 1000.0) < 0.05) & \
                (np.abs(h) < 0.05)
            if len(P) >= 3:                                      # three points in a row along the cable, all on it
                A_, B_, C_ = P[:-2], P[1:-1], P[2:]
                area = 0.5 * np.linalg.norm(np.cross(B_ - A_, C_ - A_), axis=1)
                ab, bc, ca = (np.linalg.norm(x, axis=1) for x in (B_ - A_, C_ - B_, A_ - C_))
                # the turn round the gutter, less its last 0.6 m towards the sea: where the cable leaves the gutter for
                # the sea the catenary may leave out of the gutter's plane at the start of the lowering (the hang-off's
                # own kink – an open point of the sea end, not the bend round the gutter)
                inner = on.copy()
                ends = np.flatnonzero(on & ~np.r_[on[1:], False])                 # the last point of each run
                s_on = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
                for e in ends:
                    inner &= ~((s_on > s_on[e] - 0.6) & (s_on <= s_on[e]))
                keep = inner[:-2] & inner[1:-1] & inner[2:] & (area > 1e-9) & (np.minimum(ab, bc) > 0.05)
                if keep.any():
                    worst_r = min(worst_r, float((ab * bc * ca / (4 * area))[keep].min()))
        if f >= let_go + int(math.ceil(se.sea_settle * 25)) + 1:   # settled: its start lies on the seabed
            inv = np.linalg.inv(np.array(paths_sea.bed(sc).matrix_world))
            z0 = float((inv[:3, :3] @ P[0] + inv[:3, 3])[2])
            lift = paths._rider_lift(sc, se)                       # (its CPS rests on the seabed: it lies higher)
            assert lift > 0.05 and abs(z0 - (bed + lift)) < 0.02, (f, z0, bed, lift)
    assert worst_len < 1.0, worst_len                        # (the drawn points' chords: within 0.5 %)
    assert worst_r >= 0.98 * se.mbr, (worst_r, se.mbr)
    # the CPS rides at its start: the pull head at the D's bar end, where the second end starts, at shot 9's start
    sc.frame_set(f9)
    head = next(p.part for r in se.riders for p in r.parts
                if p.part is not None and p.part.get(build.PROP_NAME) == "PULL HEAD")
    P = paths.shape_now(sc, se)
    mid = sum((head.matrix_world @ Vector(v) for v in head.bound_box), Vector()) / 8.0
    assert (mid - Vector(P[0])).length < 1.5
    # shot 11: the D set down on the seabed, heaving with the vessel – never more than 5 cm into it (its mesh); once
    # settled the pull head lies on the seabed, not under it
    seabed = paths_sea.waterline(sc) - demo.SEA_DEPTH
    lw = sorted((b for b in steps if b.joint == demo.LOWER), key=lambda b: b.start)
    f_set, f_up = animation.frame_of(a, lw[1].start), animation.frame_of(a, lw[2].start + lw[2].duration)
    dparts = demo.lowered_parts(sc)                              # (what 'Quadrant lower' carries: the D)
    assert len(dparts) > 10
    lowest = 1e9
    for f in range(f_set, f_up + 1, 2):
        sc.frame_set(f)
        for o in dparts:
            co = np.empty(len(o.data.vertices) * 3)
            o.data.vertices.foreach_get("co", co)
            M = np.array(o.matrix_world)
            lowest = min(lowest, float((co.reshape(-1, 3) @ M[2, :3] + M[2, 3]).min()))
    assert seabed - 0.05 < lowest < seabed + 0.3, (lowest, seabed)
    # task 0172: the depth worked out before Build is the built one – one Build (no correction): the D's lowest point
    # (every mesh point, every frame from the set-down step to SET_DOWN_AFTER into the hoist) within SET_DOWN_TOL of
    # SET_DOWN_CLEAR over the seabed
    off = d.set_down_error(lw[1].start, lw[2].start + demo.SET_DOWN_AFTER)
    assert abs(off) <= demo.SET_DOWN_TOL, off
    note = next(n for n in made["out"]["notes"] if n.startswith("shot 11: the D set down at"))
    assert f"{lw[1].to_dist:.3f} m" in note, (note, lw[1].to_dist)          # (the step as worked out: not corrected)
    sc.frame_set(let_go + int(math.ceil(se.sea_settle * 25)) + 5)
    hz = [(head.matrix_world @ Vector(v)).z for v in head.bound_box]
    assert min(hz) > seabed - 0.05 and min(hz) < seabed + 0.5, (min(hz), seabed)
    # the D comes back to its stationary place, the tensioners close, the cradles rise, the wires are taken off
    sc.frame_set(int(sc.frame_end))
    for jn in (demo.TRAVEL, demo.TILT, demo.LOWER, demo.TIP):
        assert joints.get_value(s.joints[jn]) == pytest.approx(0.0, abs=1e-4), jn
    for name in demo.TENSIONERS:
        assert joints.get_value(s.joints[f"{name}: Top track lift"]) == pytest.approx(0.0, abs=1e-4)
    assert all(paths.find(sc, n).part.hide_render for _k, n in demo.TIP_ITEMS)
    sc.frame_set(1)


def test_the_wires_of_the_quadrant_operation(made):
    """Task 0082: the A&R wire and the tipping wires are cables of 4 Motion > Cables and paths, each kept tight by its
    winch (none skipped). The A&R wire is spooled on its drum (the drum follows it by table) and runs straight to the
    D's eye while the D travels; from ~10° of tilt it bears on the handler's top pulley, and over the lowering it
    runs over it. The tipping wires' winch drums and foot sheaves follow their wires' speed joints, the head sheaves
    turn with the wires; while connected (shots 9–12) the wires never run through the handler, the stern or the horns.
    Every frame after shot 8 has a path for each wire."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    from fresing_render.blender import animation, build, joints, paths
    sc = _scene()
    s = sc.fresing
    a = s.animations[demo.ANIM]
    animation.bake(sc, a)
    ar = paths.find(sc, demo.AR_ITEM)
    assert ar.keep_tight and paths.tight_skipped(sc, ar) == "" and ar.a_kind == "SPOOL"
    assert s.joints[demo.AR_DRUM].couple_table == f"spool:{demo.AR_SPOOL}"
    for key, name in demo.TIP_ITEMS:
        it = paths.find(sc, name)
        assert it.keep_tight and paths.tight_skipped(sc, it) == "", name
        for jn in (f"QUADRANT SYSTEM: Swivel sheave {key} foot sheave turn",
                   f"QUADRANT SYSTEM: TIPPING WINCH {key.upper()}: Drum turn", f"QUADRANT SYSTEM: Swivel sheave {key} turn"):
            assert s.joints[jn].follows == it.joint, jn
        # task 0125: the head sheave turns to the wire (Swivel), no longer with the handler's tilt by a ratio
        head = [c for c in it.contacts if c.kind == "SHEAVE"]
        assert len(head) == 1 and head[0].swivel == f"QUADRANT SYSTEM: Swivel sheave {key} swivel"
    t9 = _t9(a)
    f9 = animation.frame_of(a, t9)
    for it in [ar] + [paths.find(sc, n) for _k, n in demo.TIP_ITEMS]:
        res, first = _solved(sc, it)
        assert not [k for k in res["problems"] if k + first >= f9], it.name
    # the A&R wire: off the pulley while the D travels, over it from ~10° of tilt to the end of the lowering
    res, first = _solved(sc, ar)
    k = [i for i, c in enumerate(paths._wheels(ar)) if c.part is not None
         and c.part.get(build.PROP_NAME) == "HANDLER TOP PULLEY"][0]
    tilt = s.joints[demo.TILT]
    theta0 = demo.ar_contact_tilt(demo.Demo(sc, made["folder"], VERSION, small=True))
    seen = 0
    for f in range(f9, int(sc.frame_end) + 1, 5):
        sc.frame_set(f)
        th = math.degrees(joints.get_value(tilt))
        w = float(res["wrap"][f - first, k])
        if th < theta0 - 3.0:
            assert w == 0.0, (f, th, w)
        elif th > theta0 + 3.0:
            assert w > 0.05, (f, th, w)
            seen += 1
    assert seen > 20
    # the tipping wires never through steel while they are shown
    names = {"HANDLER FRAME", "QUADRANT RAIL", "HINGE BRACKET", "HINGE PIN", "CHUTE", "HULL", "HULL BOTTOM",
             "MAIN DECK", "BULWARK", "HANDLER TOP PULLEY", "PISTON ROD", "CYLINDER BRACKET"}
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [(o, BVHTree.FromObject(o, dg)) for o in build.iter_parts(sc) if o.get(build.PROP_NAME) in names]
    assert len(trees) >= 10
    near, shown = [], 0
    for f in range(f9, int(sc.frame_end) + 1, 10):
        sc.frame_set(f)
        for _key, name in demo.TIP_ITEMS:
            it = paths.find(sc, name)
            if it.part.hide_render:
                continue
            shown += 1
            r = 0.5 * it.diameter
            P = _dense(paths.shape_now(sc, it))
            for o, t in trees:
                Mi = o.matrix_world.inverted()
                for q in P:
                    hit = t.find_nearest(Mi @ Vector(q))
                    if hit[0] is not None and (o.matrix_world @ hit[0] - Vector(q)).length < r - 0.002:
                        near.append((f, name, o.get(build.PROP_NAME)))
                        break
    assert shown > 20 and not near, near[:5]
    # task 0125: while shown, each tipping wire leaves its head sheave in the sheave's plane (the swivel turns to it)
    worst = 0.0
    for f in range(f9, int(sc.frame_end) + 1, 7):
        sc.frame_set(f)
        for _key, name in demo.TIP_ITEMS:
            it = paths.find(sc, name)
            if it.part.hide_render:
                continue
            sheave = [w for w, c in zip(paths.wheels_now(sc, it), paths._wheels(it)) if c.kind == "SHEAVE"][0]
            P = paths.shape_now(sc, it)
            run = P[-1] - P[-2]
            run = run / np.linalg.norm(run)
            worst = max(worst, math.degrees(math.asin(min(1.0, abs(float(run @ sheave.axis))))))
    assert worst < 1.0, worst
    sc.frame_set(1)


def test_the_quadrant_operations_parts_are_hidden_until_shot_9(made):
    """Task 0082: the model's A&R wire, tipping wires, the cable's second end and its CPS set are hidden where the
    animation starts (Show steps bring them in from shot 9) and were kept out (excluded) while the lay cable was read,
    so none of them is a contact of it; they are cables (the CPS a rider) now, so the clash check leaves them out.
    0095's constraint and driver wires are gone; the joints of the quadrant: 'Quadrant lower' rides on the travel and
    the tip on it, the handler tilts to LOWER_TILT, and the A&R winch's drum follows its wire by table."""
    from fresing_render.blender import animation, build, joints, logic, paths, paths_riders
    sc = _scene()
    animation.bake(sc, sc.fresing.animations[demo.ANIM])
    sc.frame_set(1)
    d = demo.Demo(sc, made["folder"], VERSION, small=True)
    objs = demo.quadrant_ops_parts(d)
    names = sorted(o.get(build.PROP_NAME) for o in objs)
    assert names == ["A&R WIRE", "CABLE END", "CPS SET", "TIPPING WIRE", "TIPPING WIRE"], names
    parts = [t for o in objs for t in [o] + list(logic.descendants(o)) if t.get(build.PROP_KIND) == "part"]
    assert all(t.hide_render and not t.get(build.PROP_EXCLUDED) for t in parts)
    cables = {o.name for o in paths.cable_parts(sc)} | {o.name for o in paths_riders.rider_parts(sc)}
    assert all(t.name in cables for t in parts)
    assert not bpy.data.collections.get("FR demo wires")
    assert not [o for o in sc.objects if o.get("fr_demo_wire")]
    # the lay cable's contacts: nothing of the quadrant operation's own parts
    it = paths.find(sc, demo.CABLE_ITEM)
    held = {t.name for t in parts}
    assert not [c.part.name for c in it.contacts if c.part is not None and c.part.name in held]
    s = sc.fresing
    low = s.joints["QUADRANT SYSTEM: Quadrant lower"]
    assert joints.rides_on(sc, low).name == demo.TRAVEL
    assert joints.rides_on(sc, s.joints[demo.TIP]).name == low.name
    assert math.degrees(s.joints[demo.TILT].rot_max) == pytest.approx(110.0, abs=1e-3)
    assert s.joints[demo.AR_DRUM].couple_table == f"spool:{demo.AR_SPOOL}"
    assert "QUADRANT SYSTEM: QUADRANT HANDLING WINCH: Drum turn on tilt" not in s.joints


def test_shot_11_the_cable_leaves_the_flat_d_at_its_far_end(made):
    """Task 0172 (0125's open point 6): shot 11, from the D's tip to the let-go, as the D tips flat and comes down
    onto the seabed, the second end stays in the D's gutter to its far end – the end that points the way the cable
    lies on the seabed – and goes on from there in a free bend down to the seabed: no point between its start and the
    seabed turns more than the gutter's own arc does (~1.4° a point; before: up to 62°, where the bend was left out
    near the seabed), the leave point never changes end (before: it went from the end to the gutter's middle and
    back, 0.56 m in a frame) and no point jumps between frames (before: 5.2 m), every frame has a path."""
    from fresing_render.blender import animation, paths, paths_sea
    sc = _scene()
    a = sc.fresing.animations[demo.ANIM]
    if not sc.fresing.anim_baked:
        animation.bake(sc, a)
    steps = [b for b in a.blocks if b.kind == "JOINT"]
    tp = sorted((b for b in steps if b.joint == demo.TIP), key=lambda b: b.start)
    se = paths.find(sc, demo.SECOND_ITEM)
    res, first = _solved(sc, se)
    sea, scale = res["sea"], res["scale"]
    gutter = paths._wheels(se)[0]
    wmax = paths_sea._wrap_max(se, gutter)
    bed = paths_sea.bottom_z(sc, se)
    _w, slots, *_ = paths._inputs_of(se)
    rel = paths._stored_places(sc, se, slots)[0]
    k_bed = paths_sea._roles(slots)["sea_bed"]
    f_tip, f_go = animation.frame_of(a, tp[1].start), paths.let_go_frame(se, "a")
    worst, worst_at, jump, prev = 0.0, 0, 0.0, None
    for f in range(f_tip, f_go):
        k = f - first
        assert res["ok"][k], f
        P = np.asarray(res["points"][k], dtype=float)
        inv = np.linalg.inv(rel[min(k, len(rel) - 1), k_bed])
        z = (P @ inv[2, :3] + inv[2, 3]) * scale - bed                 # over the seabed
        down = np.flatnonzero(z < 0.05)
        Q = P[: int(down[0]) + 1 if len(down) else len(P)] * scale     # from its start to where it reaches the seabed
        d = np.diff(Q, axis=0)
        n = np.linalg.norm(d, axis=1)
        u = d[n > 1e-6] / n[n > 1e-6, None]
        turn = float(np.degrees(np.arccos(np.clip((u[1:] * u[:-1]).sum(1), -1.0, 1.0))).max())
        if turn > worst:
            worst, worst_at = turn, f
        if prev is not None and len(prev) >= len(Q):
            jump = max(jump, float(np.linalg.norm(Q - prev[: len(Q)], axis=1).max()))
        prev = P * scale
        if f >= f_tip + 100:                                           # tipped flat: it leaves the gutter's far end
            assert math.degrees(float(sea["psi"][k])) > math.degrees(wmax) - 6.0, (f, float(sea["psi"][k]))
    print(f"\nshot 11: worst turn per point {worst:.2f}° at frame {worst_at}, largest move between frames "
          f"{jump:.3f} m")
    assert worst < 1.5, (worst, worst_at)                              # (the gutter's own arc: ~1.4° a point)
    assert jump < 0.4, jump                                            # (the D comes down ~0.12 m a frame)
