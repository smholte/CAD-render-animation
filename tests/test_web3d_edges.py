"""Task 0219: the CAD edges in the web 3D file's face data, no Blender – a block with a chamfer and a filleted hole
(tools/make_test_edges.py) meshed by the importer's own mesher, its edges found, fitted, packed, written and read back;
the line / circle fit on its own (a partial arc, an ellipse and a zig-zag left out)."""

import os
import sys

import numpy as np
import pytest

from fresing_render.core import web3d, web3d_faces as wf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))


def mesh_block(lin_rel=0.001, ang=0.5):
    """(points m, triangles, CAD face per triangle, rows) of the test block as the importer meshes it."""
    pytest.importorskip("OCP")
    import make_test_edges as mt
    from fresing_render.importer import step_reader as sr
    occ = sr._occ()
    ax, starts = sr._Axes(), []
    pos, _n, tri, _c, _p = sr._mesh_shape(occ, mt.shape(), lin_rel, ang, axes=ax, face_starts=starts)
    face = wf.face_of_triangles(len(tri), starts)
    rows = wf.classify(pos, tri, face, ax.axes, ax.faces)
    return pos, tri, face, rows


def summary(found):
    """Lines as (rounded ends in mm, sorted), circles as (centre mm, radius mm, degrees)."""
    lines, circles = [], []
    for _a, _b, kind, p1, p2, p3 in found:
        if kind == wf.LINE:
            lines.append(tuple(sorted([tuple(np.round(p1 * 1000, 2) + 0.0), tuple(np.round(p2 * 1000, 2) + 0.0)])))
        else:
            circles.append((tuple(np.round(p1 * 1000, 2) + 0.0), round(float(np.linalg.norm(p2 - p1)) * 1000, 3),
                            round(float(np.degrees(np.linalg.norm(p3))), 1)))
    return sorted(lines), sorted(circles)


@pytest.mark.parametrize("lin_rel,ang", [(0.001, 0.5), (0.01, 1.0)])          # fine and coarse facets
def test_the_test_blocks_edges(lin_rel, ang):
    pos, tri, face, rows = mesh_block(lin_rel, ang)
    found = wf.edges(pos, tri, face, rows)
    lines, circles = summary(found)
    # 12 box edges, one of them replaced by the chamfer's two (+ the chamfer's two short end edges) = 15 lines
    assert len(lines) == 15, lines
    assert ((0.0, 0.0, 25.0), (100.0, 0.0, 25.0)) in lines and ((0.0, 5.0, 30.0), (100.0, 5.0, 30.0)) in lines
    assert ((0.0, 0.0, 25.0), (0.0, 5.0, 30.0)) in lines                          # the chamfer's end: 5 x 5
    # the hole: its bottom rim Ø20 at z 0, the rounding meets the hole at z 27 (Ø20) and the top at z 30 (Ø26)
    assert circles == [((70.0, 30.0, 0.0), 10.0, 360.0), ((70.0, 30.0, 27.0), 10.0, 360.0),
                       ((70.0, 30.0, 30.0), 13.0, 360.0)], circles
    for a, b, *_ in found:
        assert a != b and (a in rows or b in rows)


def test_packed_written_and_read_back():
    pos, tri, face, rows = mesh_block()
    g = web3d.Gltf()
    look = g.material({"pbrMetallicRoughness": {"baseColorFactor": [0.6, 0.6, 0.6, 1.0]}})
    k = g.mesh("Block", pos, web3d.quantize_normals(np.tile([0.0, 0.0, 1.0], (len(pos), 1))), None, [(look, tri)],
               max_step=0.001)
    centre, step = g.dequantize[k] or (np.zeros(3), 1.0)
    runs, table = wf.pack([face], wf.to_written(rows, centre, step))
    et = wf.pack_edges(wf.edges_to_written(wf.edges(pos, tri, face, rows), centre, step), wf.row_numbers([face], rows))
    assert et.dtype == np.float32 and len(et) == 15 * 9 + 3 * 12          # records: a line 9 numbers, a circle 12
    added = wf.write(g, {k: (runs, table, et)})
    assert added == runs.nbytes + table.nbytes + et.nbytes
    data = g.glb()
    got = wf.read_edges(data)[k]
    assert got.shape == (18, wf.EROW) and np.array_equal(got, wf.unpack_edges(et))
    assert list(wf.read(data)) == [k]                                  # runs and rows read as before
    # every edge names the rows on its two sides; a round edge's rows: the hole (ROUND) or the rounding (AXIS)
    rows_back = wf.read(data)[k][1]
    for e in got:
        sides = [int(r) for r in e[1:3] if r >= 0]
        assert sides and all(0 <= r < len(rows_back) for r in sides)
        if int(e[0]) == wf.CIRCLE:
            assert {int(rows_back[r][0]) for r in sides} & {wf.ROUND, wf.AXIS}
            r = np.linalg.norm(e[6:9] - e[3:6]) * step                  # the radius back in metres
            assert min(abs(r - 0.010), abs(r - 0.013)) < 2e-6
    # a file without edges (an older export) reads as none
    g2 = web3d.Gltf()
    wf.write(g2, {0: (runs, table)})
    assert wf.read_edges(g2.glb()) == {}


def ring(r, n, sweep=2 * np.pi, z=0.0, centre=(0.0, 0.0, 0.0), closed=None):
    a = np.linspace(0.0, sweep, n, endpoint=closed is False or sweep < 2 * np.pi)
    pts = np.stack([r * np.cos(a), r * np.sin(a), np.full_like(a, z)], axis=1) + centre
    k = len(pts)
    seg = np.array([[i, i + 1] for i in range(k - 1)] + ([[k - 1, 0]] if sweep >= 2 * np.pi else []))
    return pts, seg


def test_fit_line_circle_arc_and_what_is_left_out():
    pts = np.array([[0, 0, 0], [0.1, 0, 0], [0.25, 0, 0]], float)
    kind, a, b, _ = wf.fit_edge(pts, np.array([[0, 1], [1, 2]]), 1e-6)
    assert kind == wf.LINE and {tuple(np.round(a, 9)), tuple(np.round(b, 9))} == {(0, 0, 0), (0.25, 0, 0)}
    p, s = ring(0.02, 32, centre=(1.0, 2.0, 3.0))
    kind, c, st, k = wf.fit_edge(p, s, 1e-6)
    assert kind == wf.CIRCLE and np.allclose(c, [1, 2, 3]) and abs(np.linalg.norm(st - c) - 0.02) < 1e-9
    assert abs(np.linalg.norm(k) - 2 * np.pi) < 1e-9
    # a quarter arc (a rounding's end): its angle, and it runs from its start the right way round the axis
    p, s = ring(0.005, 9, sweep=np.pi / 2)
    kind, c, st, k = wf.fit_edge(p[::-1].copy(), s, 1e-6)
    assert kind == wf.CIRCLE and abs(np.linalg.norm(k) - np.pi / 2) < 1e-9
    ax = k / np.linalg.norm(k)
    u = (st - c) / 0.005
    end = c + 0.005 * (u * np.cos(np.pi / 2) + np.cross(ax, u) * np.sin(np.pi / 2))
    assert min(np.linalg.norm(end - q) for q in (p[0], p[-1])) < 1e-9 and \
        min(np.linalg.norm(st - q) for q in (p[0], p[-1])) < 1e-9 and np.linalg.norm(end - st) > 1e-3
    # an ellipse (a cylinder cut by a tilted plane), a zig-zag, a bent line: not a line, not a circle
    a = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    ell = np.stack([0.02 * np.cos(a), 0.03 * np.sin(a), np.zeros_like(a)], axis=1)
    assert wf.fit_edge(ell, np.array([[i, (i + 1) % 40] for i in range(40)]), 1e-5) is None
    zig = np.array([[0, 0, 0], [0.01, 0.002, 0], [0.02, 0, 0], [0.03, 0.002, 0.001]], float)
    assert wf.fit_edge(zig, np.array([[0, 1], [1, 2], [2, 3]]), 1e-5) is None


def test_a_mesh_without_shared_edges_or_rows_gives_none():
    pts = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    assert wf.edges(pts, np.array([[0, 1, 2]]), np.array([0]), {0: [1.0] * 8}) == []
    assert wf.edges(pts, np.array([[0, 1, 2]]), np.array([0]), {}) == []
    assert wf.pack_edges([], {}) is None
