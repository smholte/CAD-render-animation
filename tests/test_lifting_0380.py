"""Task 0349 takes task 0380's fix group F1 (bug hunt 9, the lift path): rows 1, 10, 11 and 25. Blender as a module.

* Row 1: Check along the path → Go there → Ctrl+Z crashed Blender: the use bar's redraw asked the cached checks, whose
  line pull held the crane that the undo had freed. Now undo / redo drop the caches and the line pull looks the crane
  up by name when it is asked; Go there has an undo step of its own.
* Row 10: the lifting example lifted to (−2, 4.5, 0): C5 said "outside its outriggers" from frame 261 while C1 said
  25–39 %. The cause was the AT-40's file (the carrier's centre of gravity past its front pads, task 0349 Part 2a):
  now no moment of that lift is outside, and the worst C5 moment agrees with a hand calculation.
* Row 11: a key of the path changed by hand dates the checks ("Changed since it was checked").
* Row 25: the luff / telescope pieces are numbered, the message counts steps and joint moves; removing the crane
  removes its proposed lift path.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_lifting_plan as TP  # noqa: E402

from fresing_render.core import lifting as core  # noqa: E402

registered = TP.registered


def _mods():
    from fresing_render.blender import animation, joints, lifting as BL, lifting_path as LP
    return BL, LP, joints, animation


def _example_lift():
    BL, LP, _j, _a = _mods()
    sc = TP._new(TP.CRANE)
    c, ld, a = BL.set_up_example(bpy.context)
    assert a.ok, a.reason
    pr = LP.propose(sc, point=(-2.0, 4.5, 0.0))
    assert pr.ok, pr.reason
    return sc, c, ld, pr


def test_row_1_the_caches_go_at_undo_and_the_line_pull_asks_for_the_crane_by_name():
    BL, LP, _j, _a = _mods()
    sc, c, ld, _pr = _example_lift()
    rows = LP.live_rows(sc, force=True)
    assert isinstance(rows, list) and LP._CHECKS
    ck = next(iter(LP._CHECKS.values()))[1]
    for h in ("undo_post", "redo_post", "load_post"):
        assert LP._load_post in getattr(bpy.app.handlers, h), h
    LP._load_post(sc, None)                             # what Ctrl+Z calls
    assert not LP._CHECKS and LP._LIVE["rows"] is None
    # a line pull made before holds no crane: with the crane gone it says so instead of reading freed memory
    BL.remove(sc, c)
    row = ck._c10(5000.0)
    assert row.status == core.NOT_CHECKED and "no longer in the plan" in row.words
    op = bpy.ops.fresing.lifting_path_go.get_rna_type()
    assert "UNDO" in bpy.types.FRESING_OT_lifting_path_go.bl_options and op is not None


def test_row_10_c5_agrees_with_c1_and_a_hand_calculation():
    BL, LP, _j, _a = _mods()
    sc, c, ld, _pr = _example_lift()
    out = LP.check(sc)
    at, _keys, (f0, f1) = LP.reader(sc, c)
    ck = LP.checks(sc, c, ld, clearance=False)
    for f in np.arange(f0, f1 + 0.5, 3.0):
        rows = {r.id: r for r in ck.at(at(float(f)))}
        assert "outside" not in rows["C5"].value, (f, rows["C1"].words, rows["C5"].words)
        if rows["C1"].status != core.RED:
            assert rows["C5"].status != core.RED, (f, rows["C5"].words)
    # the worst C5 moment by hand: the resultant of the file's masses (carrier fixed, the rest turned by the joints,
    # the gross load under the hook) against the outrigger base the file gives
    c5 = next(r for r in out["rows"] if r["id"] == "C5")
    v = at(c5["t"])
    items = ck.sup.items(v, ck.cw, ck.hanging_kg())
    m = sum(i[0] for i in items)
    x = sum(i[0] * i[1] for i in items) / m
    y = sum(i[0] * i[2] for i in items) / m
    o = ck.data["outriggers"]
    a, b = o["a"], LP.P.LR.outrigger_spread(ck.data, v) / 2.0
    assert abs(x - o["centre"][0]) < a and abs(y) < b
    r = core.outrigger_reactions(items, a, b, (o["centre"][0], 0.0))
    assert core.force_t(max(r.reactions)) == pytest.approx(c5["measure"], rel=1e-9)


def test_row_11_a_key_changed_by_hand_dates_the_checks():
    BL, LP, joints, _a = _mods()
    sc, c, ld, _pr = _example_lift()
    LP.check(sc)
    assert not LP.stale(sc)
    j = joints.find(sc, BL.prefix(c) + "Slew")
    from fresing_render.blender import paths
    fc = next(f for f in paths._fcurves(j.motion) if f.data_path == joints.COUPLING_PATH)
    k = fc.keyframe_points[-1]
    k.co[1] += 0.5
    fc.update()
    assert LP.stale(sc)


def test_row_25_numbered_pieces_and_the_path_goes_with_its_crane():
    BL, LP, _j, _a = _mods()
    sc, c, ld, pr = _example_lift()
    labels = [s.label for s in pr.steps]
    assert len(labels) == len(set(labels)), labels                   # every step its own name
    luff = [x for x in labels if x.startswith("Luff")]
    assert not luff or luff[-1].endswith(f"{len(luff)}/{len(luff)}"), luff
    L = BL.plan(sc)
    assert f"{len(pr.steps)} steps (" in L.message and "joint moves" in L.message
    a = LP.path_anim(sc)
    name = a.name
    gone = BL.remove(sc, c)
    assert gone["animations"] == 1 and sc.fresing.animations.get(name) is None
    assert L.path_anim == "" and L.path_result == ""
