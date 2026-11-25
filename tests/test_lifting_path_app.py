"""Task 0348 (Lifting L6a): the lift path and the checks along it in the app – Blender as a Python module.

An AT-40 (mobile, outriggers) with the pump skid hung on its hook, and a CC-100 (crawler, tracks) from the library:
Propose writes ordinary "Move joint" steps that land the load on the clicked point; Check along the path finds the same
worst moment as every frame (fewer moments worked out); Go there; out of date after a change; the lift data box; the
time of a joint drag with the plan and without; an old lifting project (0.2.192) opens and works with no path."""

from __future__ import annotations

import math
import os
import statistics
import sys
import time

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lifting_rigging as T  # noqa: E402

from fresing_render.core import lifting as core  # noqa: E402

registered = T.registered                     # the module fixture (register once, read_homefile at the end)
OLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "old_lifting_0_2_192.blend")


def _mods():
    from fresing_render.blender import animation, joints, lifting as BL, lifting_path as LP, lifting_rig as RG
    return BL, RG, LP, joints, animation


def _skid_on_at40():
    BL, RG, LP, _j, _a = _mods()
    sc = T._new()
    c = T._crane(sc)
    ld = T._skid(sc)
    T._above(sc, c, ld, 4.6 - ld.clearance)
    RG.hang(sc, c, ld)
    L = BL.plan(sc)
    L.allowable_kpa, L.mat_size = 250.0, (1.2, 1.2)
    return sc, c, ld


def test_propose_check_go_there_and_the_data_box():
    BL, RG, LP, joints, animation = _mods()
    sc, c, ld = _skid_on_at40()
    hook = BL.hook_world(sc, c)
    pt = np.array((hook[0] + 3.0, hook[1] - 5.0, 0.0))
    pr = LP.propose(sc, point=tuple(pt))
    assert pr.ok, pr.reason
    a = LP.path_anim(sc)
    assert a is not None and LP.is_proposed(a)
    assert [b.kind for b in a.blocks] == ["JOINT"] * len(a.blocks)
    labels = [b.name for b in a.blocks]
    assert labels[0] == "Lift · Hoist clear" and labels[-1] == "Lift · Lower" and "Lift · Slew" in labels
    out = LP.check(sc, reference=True)
    ids = [r["id"] for r in out["rows"]]
    assert ids[:4] == ["C1", "C10", "SETUP", "C5"] and "C3" in ids and "C4" in ids and "BACK" in ids
    # the search finds every check's worst moment of the frame-by-frame reference, with far fewer moments
    every = {r["id"]: r for r in out["every"]["rows"]}
    for r in out["rows"]:
        e = every[r["id"]]
        if e["use"] is not None:
            assert r["use"] >= e["use"] - 1e-6, (r["id"], r["use"], e["use"])
        assert core.worst_status([r["status"], e["status"]]) == r["status"]
    assert out["evaluations"] * 5 < out["every"]["evaluations"]
    print(f"\nsearch {out['evaluations']} moments {out['seconds'] * 1000:.0f} ms; every frame "
          f"{out['every']['evaluations']} moments {out['every']['seconds'] * 1000:.0f} ms")
    # the load stands on the set-down point at the end
    sc.frame_set(int(out["frames"][1]))
    assert abs(LP.load_bottom(ld) - pt[2]) < 0.01
    cog = BL.cog_world(ld)
    assert np.linalg.norm(cog[:2] - pt[:2]) < 0.02
    # Go there: the frame of the worst crane use
    c1 = next(r for r in out["rows"] if r["id"] == "C1")
    assert LP.go_to(sc, "C1") == pytest.approx(c1["t"])
    assert sc.frame_current == int(c1["t"])
    assert not LP.stale(sc)
    # the lift data box: a label on the hook block with the numbers at the frame shown
    BL.plan(sc).data_box = True
    lab = LP.data_box_label(sc)
    assert lab is not None and sc.fresing.callouts_on
    from fresing_render.blender import callouts
    rows = callouts.label_text(sc, lab).split("\n")
    ro = BL.readout(sc, c, ld)
    assert rows[0] == "Lift data" and rows[2] == f"Radius {ro.radius:.1f} m"
    assert rows[3] == f"Crane use {ro.use * 100:.0f} %" and rows[4].startswith("Worst so far: ")
    BL.plan(sc).data_box = False
    assert LP.data_box_label(sc) is None
    # out of date after a change of the ground or the path
    BL.plan(sc).allowable_kpa = 200.0
    assert LP.stale(sc)
    LP.check(sc)
    assert not LP.stale(sc)
    a.blocks[1].duration += 1.0
    assert LP.stale(sc)


def test_red_jacks_up_in_the_path_and_counterweight_above_the_chart():
    BL, RG, LP, joints, animation = _mods()
    sc, c, ld = _skid_on_at40()
    c.counterweight = 10.0                          # the AT-40's charts go to 8 t
    jack = joints.find(sc, c.name + " · Jacks")
    joints.set_value(jack, 0.0)                     # jacks up: on its wheels
    BL._update()
    rows = {r.id: r for r in LP.live_rows(sc, force=True)}
    assert rows["SETUP"].status == core.RED and "jacks are up" in rows["SETUP"].words
    assert rows["BACK"].status != core.NOT_CHECKED and "more than the chart's 8.00 t" in rows["BACK"].words
    assert "the chart is for 8.00 t" in rows["C1"].words


def test_own_animation_as_the_path():
    BL, RG, LP, joints, animation = _mods()
    sc, c, ld = _skid_on_at40()
    s = sc.fresing
    a = s.animations.add()
    a.name = "My lift"
    b = a.blocks.add()
    b.kind, b.joint, b.start, b.duration, b.use_from = "JOINT", c.name + " · Slew", 0.0, 4.0, True
    b.to_angle = math.radians(90.0)
    LP.use_animation(sc, "My lift")
    assert not LP.is_proposed(a)
    out = LP.check(sc)
    assert out["anim"] == "My lift" and out["rows"]


def test_crawler_from_the_library_tracks():
    BL, RG, LP, joints, animation = _mods()
    sc = T._new()
    c = T._crane(sc, "CC-100", (0.0, 20.0, 0.0))
    ld = T._box_load(sc, 4.0, (2.0, 1.0, 1.0))
    T._above(sc, c, ld)
    BL.plan(sc).allowable_kpa = 300.0
    hook = BL.hook_world(sc, c)
    pr = LP.propose(sc, point=(hook[0] - 6.0, hook[1] + 4.0, 0.0))
    assert pr.ok, pr.reason
    out = LP.check(sc)
    ids = [r["id"] for r in out["rows"]]
    assert "C6" in ids and "C5" not in ids and "SETUP" not in ids
    c6 = next(r for r in out["rows"] if r["id"] == "C6")
    assert c6["use"] is not None and "kPa" in c6["words"]
    assert next(r for r in out["rows"] if r["id"] == "C2")["status"] == core.NOT_CHECKED     # the box is not hung


def test_drag_is_no_slower_with_the_plan():
    """A joint dragged: set_value + a view-layer update per step (as pccheck's stress.drag), plus what a redraw of
    the plan asks for (the use bar beside the hook: live rows, at most every LIVE_EVERY s). With the path checked and
    the data box on against the same scene without them."""
    BL, RG, LP, joints, animation = _mods()
    sc, c, ld = _skid_on_at40()
    j = joints.find(sc, c.name + " · Slew")
    hook = BL.hook_world(sc, c)
    assert LP.propose(sc, point=(hook[0] + 3.0, hook[1] - 5.0, 0.0)).ok
    LP.check(sc)
    animation.clear_keys(sc)

    def drag(plan: bool, n=40):
        t0 = time.perf_counter()
        for i in range(n):
            joints.set_value(j, math.radians(i * 0.5))
            bpy.context.view_layer.update()
            if plan:
                LP.bar_numbers(sc)                      # what one redraw does
            time.sleep(0.008)                           # the time between two mouse moves (125 per second)
        return (time.perf_counter() - t0) / n * 1000.0

    BL.plan(sc).data_box = True
    with_, without = [], []
    for _ in range(5):
        without.append(drag(False))
        with_.append(drag(True))
    w, wo = statistics.median(with_), statistics.median(without)
    print(f"\ndrag step (with 8 ms between mouse moves): {wo:.2f} ms without the plan, {w:.2f} ms with it "
          f"(live rows worked out {LP._LIVE['count']} times)")
    assert w <= wo * 1.05


def test_old_lifting_project_opens_with_no_path():
    BL, RG, LP, joints, animation = _mods()
    bpy.ops.wm.open_mainfile(filepath=OLD)
    sc = bpy.context.scene
    L = BL.plan(sc)
    assert len(L.cranes) == 1 and len(L.loads) == 1
    assert L.path_anim == "" and L.path_result == "" and not L.data_box and LP.result(sc) is None
    assert not LP.stale(sc)
    rows = LP.live_rows(sc, force=True)
    assert isinstance(rows, list) and {r.id for r in rows} >= {"C1", "C5", "SETUP", "C3"}
    c, ld = L.cranes[0], L.loads[0]
    assert ld.rig_state == "HUNG"
    hook = BL.hook_world(sc, c)
    pr = LP.propose(sc, point=(hook[0] + 2.0, hook[1] - 4.0, 0.0))
    assert pr.ok, pr.reason
    assert LP.check(sc)["rows"]
