"""Task 0237 (bug hunt 0209 row 5): a mesh model update where a group with no name in the file ("Node 4") moved AND
one of its parts changed shape keeps the work on that group and its parts.

Three unnamed groups A, B, C, two boxes each (as in tests/test_mesh_update_moved_groups.py). The revision moves B by
100 mm and makes one of its boxes 20 mm wider. Work on B: the eye, a Hide step and a sequence step on B, a joint on
B1. With named parts ("B1", "B2") and with unnamed parts (the reader names them "Node 7" …)."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))

bpy = pytest.importorskip("bpy")

import numpy as np  # noqa: E402

import make_test_mesh as maker  # noqa: E402
from fresing_render.blender import build, joints, logic, states  # noqa: E402
from test_mesh_import_fixes import fresh, update  # noqa: E402
from test_seq_mesh_0162_independent import X0, _cx, _work_on, addon  # noqa: E402,F401

MOVE = 0.1          # B moves 100 mm along x
WIDER = 0.02        # one of B's boxes gets 20 mm wider (along x)


def glb(node_move=None, box_move=None, wider=(), part_names=True, swap=None) -> bytes:
    """Groups A, B, C of two boxes. ``node_move[G]``: G's node translated; ``box_move[G]``: G's boxes drawn that far
    away (the node stays at the origin); ``wider``: the boxes ("B1") that are 20 mm wider; ``part_names``: the boxes
    carry "B1" … as names (else no name: the reader makes "Node n"); ``swap[G]``: G's two boxes trade places (a real
    re-arrangement)."""
    g = maker.Gltf()
    grey = g.material("Grey", (0.5, 0.5, 0.5))
    for name in ("A", "B", "C"):
        m = np.eye(4)
        m[:3, 3] = (node_move or {}).get(name, (0.0, 0.0, 0.0))
        grp = g.node("", matrix=m)
        shift = np.array((box_move or {}).get(name, (0.0, 0.0, 0.0)), float)
        for k in (1, 2):
            s = maker.Shape()
            slot = (3 - k) if (swap or {}).get(name) else k
            x = X0[name] + 0.3 * slot
            nm = f"{name}{k}"
            lo = np.array((x, 0.0, 0.0)) + shift
            hi = np.array((x + 0.2 + (WIDER if nm in wider else 0.0), 0.25 + 0.05 * k, 0.2)) + shift
            s.box(tuple(lo), tuple(hi))
            g.node(nm if part_names else "", g.mesh(nm if part_names else "", [(s, grey)]), parent=grp)
    return g.glb()


def _parts(sc):
    return [o for o in sc.objects if o.get(build.PROP_KIND) == "part"]


def _at(sc, x):
    """The part whose box middle is nearest x."""
    return min(_parts(sc), key=lambda o: abs(_cx(o) - x))


def _middle(name, moved, wide=False):
    k = int(name[1])
    return X0[name[0]] + 0.3 * k + 0.1 + (MOVE if moved else 0.0) + (WIDER / 2 if wide else 0.0)


def _run(tmp_path, part_names, how, wider, **extra):
    src = tmp_path / "g.glb"
    src.write_bytes(glb(part_names=part_names))
    sc = fresh(tmp_path, src)
    b1 = _at(sc, _middle("B1", False))
    uids = {o[build.PROP_UID]: _cx(o) for o in _parts(sc)}
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    move = {"B": (MOVE, 0.0, 0.0)}
    kw = {"node_move": move} if how == "node" else {"box_move": move}
    kw.update(extra)
    src.write_bytes(glb(part_names=part_names, wider=wider, **kw))
    update(sc, src)
    return sc, hide, seq, uids


def _check(sc, hide, seq, uids, wider):
    b1 = _at(sc, _middle("B1", True, "B1" in wider))
    grp = build.logical_parent(b1)
    by = states.by_uid(sc)
    assert by.get(hide.target_uid) == grp, ("hide step", by.get(hide.target_uid))
    assert by.get(seq.target_uid) == grp, ("sequence step", by.get(seq.target_uid))
    hidden = sorted(o.name for o in sc.objects if o.get(build.PROP_KIND) == "assembly" and logic.is_hidden(o))
    assert hidden == [grp.name], ("eye", hidden, grp.name)
    assert [o.name for o in joints.members(sc.fresing.joints["Work joint"])] == [b1.name]
    # every part kept: the same uids as before (a part that changed stays the same part)
    assert sorted(o[build.PROP_UID] for o in _parts(sc)) == sorted(uids)


@pytest.mark.parametrize("part_names", [True, False], ids=["named-parts", "unnamed-parts"])
@pytest.mark.parametrize("how", ["node", "boxes"])
@pytest.mark.parametrize("wider", [("B2",), ("B1",)], ids=["B2-wider", "B1-wider"])
def test_a_moved_group_with_a_changed_part_keeps_its_work(tmp_path, part_names, how, wider):
    """Row 5: B moved 100 mm and one of its boxes 20 mm wider. All six parts kept, the Hide and sequence steps still
    on B, B still hidden, the joint still on B1; the report says what happened."""
    sc, hide, seq, uids = _run(tmp_path, part_names, how, wider)
    assert sc.fresing.report_title == "Model updated: 6 parts kept, 0 new, 0 missing"
    _check(sc, hide, seq, uids, wider)
    notes = [n.text for n in sc.fresing.report_notes]
    assert any("moved 100 mm" in n and "1 part changed" in n for n in notes), notes


@pytest.mark.parametrize("part_names", [True, False], ids=["named-parts", "unnamed-parts"])
def test_a_moved_group_without_changes_still_keeps_its_work(tmp_path, part_names):
    """The control (0183 row 5's case): B only moved."""
    sc, hide, seq, uids = _run(tmp_path, part_names, "node", ())
    assert sc.fresing.report_title == "Model updated: 6 parts kept, 0 new, 0 missing"
    _check(sc, hide, seq, uids, ())


@pytest.mark.parametrize("part_names", [True, False], ids=["named-parts", "unnamed-parts"])
def test_a_real_rearrangement_keeps_both_parts(tmp_path, part_names):
    """B moved 100 mm and its two boxes traded places (each its own shape): a re-arrangement, not a veto. Both parts
    are kept (they show moved), the work stays on B and on B1 – wherever B1 now is."""
    src = tmp_path / "g.glb"
    src.write_bytes(glb(part_names=part_names))
    sc = fresh(tmp_path, src)
    b1 = _at(sc, _middle("B1", False))
    uids = {o[build.PROP_UID] for o in _parts(sc)}
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(glb(part_names=part_names, node_move={"B": (MOVE, 0.0, 0.0)}, swap={"B": True}))
    update(sc, src)
    assert sc.fresing.report_title == "Model updated: 6 parts kept, 0 new, 0 missing"
    assert sorted(o[build.PROP_UID] for o in _parts(sc)) == sorted(uids)
    new_b1 = _at(sc, _middle("B2", True))                 # B1 now sits where B2 was (+ the move)
    grp = build.logical_parent(new_b1)
    assert [o.name for o in joints.members(sc.fresing.joints["Work joint"])] == [new_b1.name]
    assert states.by_uid(sc).get(hide.target_uid) == grp
    assert logic.is_hidden(grp)


def test_a_removed_group_and_another_added_elsewhere_do_not_pair(tmp_path):
    """C removed and a new group D of other shapes added 1 m further (its node moved, so no part has C's origin):
    nothing of C pairs with D (2 new, 2 missing)."""
    g = maker.Gltf
    src = tmp_path / "g.glb"
    src.write_bytes(glb(part_names=False))
    sc = fresh(tmp_path, src)
    after = g()
    grey = after.material("Grey", (0.5, 0.5, 0.5))
    for name in ("A", "B", "D"):
        m = np.eye(4)
        m[0, 3] = 1.0 if name == "D" else 0.0
        grp = after.node("", matrix=m)
        for k in (1, 2):
            s = maker.Shape()
            x = X0["C" if name == "D" else name] + 0.3 * k
            tall = 0.4 if name == "D" else 0.0
            s.box((x, 0.0, 0.0), (x + 0.2, 0.25 + 0.05 * k + tall, 0.2))
            after.node("", after.mesh("", [(s, grey)]), parent=grp)
    src.write_bytes(after.glb())
    update(sc, src)
    assert sc.fresing.report_title == "Model updated: 4 parts kept, 2 new, 2 missing"


@pytest.mark.parametrize("part_names", [True, False], ids=["named-parts", "unnamed-parts"])
@pytest.mark.parametrize("how", ["node", "boxes"])
def test_a_moved_group_whose_parts_all_changed_keeps_its_work(tmp_path, part_names, how):
    """Task 0325 (bug hunt 0328 row 23): B moved 100 mm and BOTH its boxes 20 mm wider. No part of B keeps its shape,
    so nothing pairs B's parts by shape; the group is the same node of the tree (the second unnamed group under the
    root, between A and C, which kept their places): it pairs by that place, and its parts pair as changed parts. All
    six parts kept, the Hide and sequence steps still on B, B still hidden, the joint still on B1."""
    sc, hide, seq, uids = _run(tmp_path, part_names, how, ("B1", "B2"))
    assert sc.fresing.report_title == "Model updated: 6 parts kept, 0 new, 0 missing"
    _check(sc, hide, seq, uids, ("B1", "B2"))
    notes = [n.text for n in sc.fresing.report_notes]
    assert any("moved 100 mm" in n and "2 parts changed" in n for n in notes), notes
