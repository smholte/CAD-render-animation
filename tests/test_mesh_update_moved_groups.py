"""Task 0188 (bug hunt 6, row 5 + 0162's open point): a mesh model update keeps the work on a group that has no name
in the file ("Node 4") when the new revision moves that group, and when only that group is left (the reader then
makes it the model's root).

Three groups A, B, C, two boxes each (A1, A2, B1, B2 …); every group's first box has one shape, so only names and
places tell them apart. Work on B: the eye in 2 Structure, a Hide step and a sequence step on B, a joint on B1."""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
sys.path.insert(0, os.path.dirname(__file__))

bpy = pytest.importorskip("bpy")

import numpy as np  # noqa: E402

import make_test_mesh as maker  # noqa: E402
from fresing_render.blender import build  # noqa: E402
from test_mesh_import_fixes import fresh, update  # noqa: E402
from test_seq_mesh_0162_independent import X0, _check_work, _cx, _part, _work_on, addon  # noqa: E402,F401


def moved_glb(groups=("A", "B", "C"), named=False, node_move=None, box_move=None) -> bytes:
    """Groups of two boxes. ``node_move[G]``: G's own node is translated by it (the boxes keep their local
    coordinates, so the whole group moves); ``box_move[G]``: G's node stays at the origin, its boxes are drawn
    that far away (a mesh file whose nodes all sit at the model's origin). ``named``: the groups carry their
    letter as a name (the control: named groups were kept before)."""
    g = maker.Gltf()
    grey = g.material("Grey", (0.5, 0.5, 0.5))
    for name in groups:
        m = np.eye(4)
        m[:3, 3] = (node_move or {}).get(name, (0.0, 0.0, 0.0))
        grp = g.node(name if named else "", matrix=m)
        shift = np.array((box_move or {}).get(name, (0.0, 0.0, 0.0)), float)
        for k in (1, 2):
            s = maker.Shape()
            x = X0[name] + 0.3 * k
            lo = np.array((x, 0.0, 0.0)) + shift
            hi = np.array((x + 0.2, 0.25 + 0.05 * k, 0.2)) + shift
            s.box(tuple(lo), tuple(hi))
            nm = f"{name}{k}"
            g.node(nm, g.mesh(nm, [(s, grey)]), parent=grp)
    return g.glb()


def _parts(sc):
    return sorted(o.get(build.PROP_NAME) for o in sc.objects if o.get(build.PROP_KIND) == "part")


def _run(tmp_path, after, named=False, **kw):
    src = tmp_path / "g.glb"
    src.write_bytes(moved_glb(named=named))
    sc = fresh(tmp_path, src)
    b1 = _part(sc, "B1")
    hide, seq = _work_on(sc, build.logical_parent(b1), b1)
    src.write_bytes(moved_glb(after, named=named, **kw))
    update(sc, src)
    return sc, hide, seq


@pytest.mark.parametrize("named", [False, True], ids=["unnamed", "named"])
@pytest.mark.parametrize("how", ["node", "boxes"])
def test_a_moved_group_keeps_its_work(tmp_path, named, how):
    """Row 5: the revision moves group B by 100 mm (its node, or its boxes with the node at the origin). All six
    parts are kept (the same uids), the Hide and sequence steps still point at B, B is still hidden and the joint
    is still on B1 – in its new place."""
    move = {"B": (0.1, 0.0, 0.0)}
    kw = {"node_move": move} if how == "node" else {"box_move": move}
    sc, hide, seq = _run(tmp_path, ("A", "B", "C"), named=named, **kw)
    assert _parts(sc) == ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert sc.fresing.report_title == "Model updated: 6 parts kept, 0 new, 0 missing"
    assert _cx(_part(sc, "B1")) == pytest.approx(X0["B"] + 0.3 + 0.1 + 0.1, abs=1e-4)   # moved by 100 mm
    _check_work(sc, hide, seq, "B1")


@pytest.mark.parametrize("move", [False, True], ids=["in-place", "moved"])
def test_only_group_b_left_keeps_its_work(tmp_path, move):
    """0162's open point: the update leaves only B (A and C removed); the reader makes B the model's root. B's
    parts stay kept and the work on B goes to the new model's root (it is B now); also when B moved."""
    kw = {"node_move": {"B": (0.1, 0.0, 0.0)}} if move else {}
    sc, hide, seq = _run(tmp_path, ("B",), **kw)
    assert _parts(sc) == ["B1", "B2"]
    assert sc.fresing.report_title == "Model updated: 2 parts kept, 0 new, 4 missing"
    b1 = _part(sc, "B1")
    from fresing_render.blender import joints, logic, states
    grp = build.logical_parent(b1)
    by = states.by_uid(sc)
    assert by.get(hide.target_uid) == grp, ("hide step", by.get(hide.target_uid))
    assert by.get(seq.target_uid) == grp, ("sequence step", by.get(seq.target_uid))
    assert logic.is_hidden(grp)
    assert [o.name for o in joints.members(sc.fresing.joints["Work joint"])] == [b1.name]
