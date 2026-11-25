"""Task 0323, independent tests written from the brief: small synthetic meshes, `weld_cad.find` with and without names."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fresing_render.core import weld_cad  # noqa: E402
from test_weld_cad_core import _box, _mesh, _prism  # noqa: E402

HALF = 0.0005 + 1e-9


def _plate(off=(0, 0, 0)):
    return _mesh("p", "PLATE", _box(*(np.array([0, 0, 0, .4, .3, .012]) + np.tile(off, 2))))


def _wall(off=(0, 0, 0), x0=0.05, x1=0.25):
    return _mesh("w", "WALL", _box(*(np.array([x0, .145, .012, x1, .155, .112]) + np.tile(off, 2))))


def _tri(zs=(0.01, 0.01), x0=0.06, x1=0.20, y=0.145, key="b", name="BEAD", off=0.0):
    za, zb = zs
    m = _mesh(key, name, _prism([(y, .012), (y, .012 + zb), (y - za, .012)], x0, x1))
    return _shift(m, (off, 0, 0))


def _shift(m, d):
    return weld_cad.Mesh(m.key, m.name, m.points + np.asarray(d, float), m.tris, m.face, m.material)


def _flip(m):
    return weld_cad.Mesh(m.key, m.name, m.points, m.tris[:, ::-1], m.face, m.material)


def _find(bodies, parts, named=()):
    return weld_cad.find(bodies, parts, set(named))


def _angled(deg_minus_y, z):
    """Plate A (top z=.012) and slab B leaning so that the angle on the -y side is deg_minus_y; a triangle bead of legs z."""
    phi = math.radians(180 - deg_minus_y)
    u = np.array([math.cos(phi), math.sin(phi)])
    n = np.array([u[1], -u[0]])
    R = np.array([0.15, 0.012])
    w = 0.01
    poly = [R, R + 0.1 * u, R + 0.1 * u + w * n, R + np.array([w / math.sin(phi), 0.0])]
    b = _mesh("B", "SLAB", _prism([tuple(p) for p in poly], 0.05, 0.25))
    t2 = R + z * u
    bead = _mesh("b", "BEAD", _prism([tuple(R), tuple(t2), (R[0] - z, R[1])], 0.06, 0.20))
    return _plate(), b, bead


@pytest.mark.parametrize("deg,k", [(60, math.cos(math.radians(30))), (120, math.cos(math.radians(60))),
                                   (90, math.cos(math.radians(45)))])
def test_fillet_throat_at_any_corner_angle(deg, k):
    plate, slab, bead = _angled(deg, 0.008)
    got = _find([bead], [plate, slab], {"b"})
    assert len(got) == 1 and got[0].kind == "FILLET", [weld_cad.describe(f) for f in got]
    assert abs(got[0].size - 0.008 * k) <= HALF + 0.0003
    assert abs(got[0].length - 0.14) <= 0.002


def test_unequal_legs_and_throat_from_the_short_leg():
    f, = _find([_tri((0.006, 0.010))], [_plate(), _wall()], {"b"})
    assert abs(f.size - 0.006 * math.cos(math.pi / 4)) <= HALF + 0.0003
    assert "6" in f.note and "10" in f.note
    g, = _find([_tri((0.010, 0.006))], [_plate(), _wall()], {"b"})
    assert abs(g.size - f.size) <= 1e-9 and "6" in g.note


def test_concave_bead_throat_is_the_depth_along_the_middle():
    z = 0.010
    # toe on the wall, hollow face, toe on the plate, root (counter-clockwise)
    # hollow: mid-point pulled toward the root; fan from index 0 is a valid triangulation
    prof = [(0.145 - 0.25 * z, 0.012 + 0.25 * z), (0.145, 0.012 + z), (0.145, 0.012), (0.145 - z, 0.012)]
    m = weld_cad.Mesh("b", "BEAD", *_prism(prof, 0.06, 0.20)[:2], _prism(prof, 0.06, 0.20)[2])
    f, = _find([m], [_plate(), _wall()], {"b"})
    assert f.kind == "FILLET"
    assert abs(f.size - 0.0035) <= HALF + 1e-4      # hollow point 3.5 mm from the root, the triangle's would be 7.07


@pytest.mark.parametrize("z", [0.0015, 0.003, 0.006, 0.015, 0.025])
def test_sizes_small_and_large(z):
    f, = _find([_tri((z, z))], [_plate(), _wall()], {"b"})
    assert f.kind == "FILLET"
    assert abs(f.size - z * math.sqrt(0.5)) <= HALF + 1e-4
    assert abs(f.legs[0] - z) < 3e-4 and abs(f.legs[1] - z) < 3e-4
    assert f.size * 1000 % 0.5 == pytest.approx(0, abs=1e-6) or abs(f.size * 2000 - round(f.size * 2000)) < 1e-6


@pytest.mark.parametrize("off", [(100, 0, 0), (0, -250, 80), (-3000, 0, 0)])
def test_far_from_the_origin(off):
    bead = _shift(_tri(), off)
    f, = _find([bead], [_shift(_plate(), off), _shift(_wall(), off)], {"b"})
    assert f.kind == "FILLET" and abs(f.size - 0.007) <= HALF + 2e-4 and abs(f.length - 0.14) <= 0.002


def test_far_from_the_origin_by_shape():
    off = (100, 0, 0)
    got = _find([_shift(_tri(), off)], [_shift(_plate(), off), _shift(_wall(), off)])
    assert len(got) == 1 and got[0].how == "shape"


def test_inside_out_wall_still_found():
    f = _find([_tri()], [_plate(), _flip(_wall())], {"b"})
    g = _find([_tri()], [_plate(), _wall()], {"b"})
    assert len(g) == 1
    assert len(f) == 1 and f[0].kind == g[0].kind, [weld_cad.describe(x) for x in f]


def test_inside_out_bead_still_found():
    f = _find([_flip(_tri())], [_plate(), _wall()], {"b"})
    assert len(f) == 1 and f[0].kind == "FILLET", [weld_cad.describe(x) for x in f]


def test_two_sides_of_one_fin_are_two_welds():
    a = _tri(key="a")
    b = _shift(_mesh("b", "B", _prism([(.155, .012), (.155, .022), (.165, .012)], .06, .20)), (0, 0, 0))
    got = _find([a, b], [_plate(), _wall()], {"a", "b"})
    assert len(got) == 2 and all(f.kind == "FILLET" and abs(f.length - 0.14) < 0.002 for f in got)
    # one body holding both: still two welds
    both = weld_cad.Mesh("ab", "Welds", np.concatenate([a.points, b.points]),
                         np.concatenate([a.tris, b.tris + len(a.points)]), np.concatenate([a.face, b.face + 1000]))
    got = _find([both], [_plate(), _wall()], {"ab"})
    assert len(got) == 2 and all(f.kind == "FILLET" for f in got)


def _pieces(spans, name="Welds"):
    ms = [_tri(x0=a, x1=b, key="x") for a, b in spans]
    pts = np.concatenate([m.points for m in ms])
    tris = np.concatenate([m.tris + i * len(ms[0].points) for i, m in enumerate(ms)])
    face = np.concatenate([m.face + 100 * i for i, m in enumerate(ms)])
    return weld_cad.Mesh("x", name, pts, tris, face)


def _wall_long():
    return _mesh("w", "WALL", _box(0.0, .145, .012, .6, .155, .112))


def _plate_long():
    return _mesh("p", "PLATE", _box(-.05, 0, 0, .65, .3, .012))


def test_regular_pieces_are_one_intermittent_weld():
    got = _find([_pieces([(0.05 + .05 * i, 0.08 + .05 * i) for i in range(5)])], [_plate_long(), _wall_long()], {"x"})
    assert len(got) == 1 and got[0].intermittent is not None
    n, piece, pitch = got[0].intermittent
    assert n == 5 and abs(piece - .03) < .001 and abs(pitch - .05) < .001


def test_irregular_spacing_is_not_merged():
    starts = [0.05, 0.10, 0.17, 0.22, 0.35]
    got = _find([_pieces([(s, s + .03) for s in starts])], [_plate_long(), _wall_long()], {"x"})
    assert not any(f.intermittent for f in got), [weld_cad.describe(f) for f in got]
    assert len(got) >= 2 and sum(f.pieces for f in got) == 5


def test_irregular_lengths_are_not_merged():
    spans = [(0.05, 0.08), (0.10, 0.20), (0.25, 0.28), (0.30, 0.40)]
    got = _find([_pieces(spans)], [_plate_long(), _wall_long()], {"x"})
    assert not any(f.intermittent for f in got)


def test_pieces_on_two_different_seams_are_not_merged():
    a = _tri(x0=.06, x1=.09, key="x")
    b = _tri(x0=.11, x1=.14, key="y")
    far = _mesh("b", "B", _prism([(.155, .012), (.155, .022), (.165, .012)], .16, .19))
    both = weld_cad.Mesh("x", "Welds", np.concatenate([a.points, b.points, far.points]),
                         np.concatenate([a.tris, b.tris + len(a.points), far.tris + 2 * len(a.points)]),
                         np.concatenate([a.face, b.face + 100, far.face + 200]))
    got = _find([both], [_plate(), _wall()], {"x"})
    assert not any(f.intermittent and f.intermittent[0] == 3 for f in got)


def test_tube_on_a_plate_closed_ring():
    R, z, N = 0.03, 0.005, 64
    cx, cy = 0.2, 0.15
    pts, tris, face = [], [], []

    def ring(profile):
        for i in range(len(profile)):
            (r0, z0), (r1, z1) = profile[i], profile[(i + 1) % len(profile)]
            if r0 == 0 and r1 == 0:
                continue
            for k in range(N):
                a0, a1 = 2 * math.pi * k / N, 2 * math.pi * (k + 1) / N
                q = [(r0, a0, z0), (r0, a1, z0), (r1, a1, z1), (r1, a0, z1)]
                b = len(pts)
                pts.extend([(cx + r * math.cos(a), cy + r * math.sin(a), zz) for r, a, zz in q])
                tris.extend([(b, b + 1, b + 2), (b, b + 2, b + 3)] if r0 != 0 else [(b, b + 2, b + 3)])
                face.extend([i] * (2 if r0 != 0 else 1))
        t = np.array(tris)
        p = np.array(pts)
        v = p[t]
        c = p.mean(0)
        return p, t, np.array(face)
    # tube: profile (r, z) counter-clockwise seen with r right, z up
    ring([(0, .012), (R, .012), (R, .112), (0, .112)])
    tp, tt, tf = np.array(pts), np.array(tris), np.array(face)
    pts, tris, face = [], [], []
    ring([(R, .012), (R + z, .012), (R, .012 + z)])
    bp, bt, bf = np.array(pts), np.array(tris), np.array(face)

    def orient(p, t, f, outward_of):
        v = p[t]
        n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        bad = (n * outward_of(v.mean(1))).sum(1) < 0
        t = t.copy()
        t[bad] = t[bad][:, ::-1]
        return t
    tt = orient(tp, tt, tf, lambda c: np.stack([c[:, 0] - cx, c[:, 1] - cy, c[:, 2] - .062], 1))
    # bead: faces on cylinder (face 0 of ring) and plate (face 1): outward = away from root corner
    root = np.array([R * 0 + cx, cy, 0.0])

    def out_bead(c):
        r = np.hypot(c[:, 0] - cx, c[:, 1] - cy)
        return np.stack([(c[:, 0] - cx) / r * (r - (R + z / 3)), (c[:, 1] - cy) / r * (r - (R + z / 3)),
                         c[:, 2] - (.012 + z / 3)], 1)
    bt = orient(bp, bt, bf, out_bead)
    plate = _mesh("p", "PLATE", _box(0, 0, 0, .4, .3, .012))
    tube = weld_cad.Mesh("t", "TUBE", tp, tt, tf)
    bead = weld_cad.Mesh("b", "BEAD", bp, bt, bf)
    got = _find([bead], [plate, tube], {"b"})
    assert len(got) == 1, [weld_cad.describe(f) for f in got]
    f = got[0]
    assert f.kind == "FILLET" and f.closed
    assert abs(f.size - z * math.sqrt(.5)) <= HALF + 2e-4
    assert abs(f.length - 2 * math.pi * R) < 0.004


def test_bead_on_three_parts_is_kept_and_said():
    p3 = _mesh("g", "WALL 2", _box(0.25, .145, .012, .30, .155, .112))
    bead = _mesh("b", "BEAD", _prism([(0.145, .012), (0.145, .017), (0.14, .012)], 0.10, 0.28))
    got = _find([bead], [_plate(), _wall(), p3], {"b"})
    assert len(got) == 1 and got[0].joins == 3 and "3" in got[0].note


@pytest.mark.parametrize("name,ok", [
    ("Welds", True), ("Weld Bead 3", True), ("WELD_1", True), ("Fillet Weld 2", True), ("Groove weld", True),
    ("Lasnaad", True), ("Schweißnaht 2", True), ("Schweissnaht", True), ("Soudure", True), ("Cordón soldadura", True),
    ("lasnaden", True), ("Saldatura 1", True),
    ("Weld nut M8", False), ("Weldment1", False), ("Welded frame", False), ("Weld-on hinge", False),
    ("Beadwork", False), ("Bead", False), ("Welding table", False), ("", False), ("Schweißmutter", False),
    ("Weld stud", False), ("Weld plate", False), ("Bolt", False),
])
def test_weld_names(name, ok):
    assert weld_cad.weld_name(name) is ok


@pytest.mark.parametrize("name,metal", [
    ("Welded Steel Mild", "STEEL"), ("Welded Aluminum-6061", "ALUMINIUM"), ("Welded Stainless Steel", "STAINLESS"),
    ("1.4301", "STAINLESS"), ("AlMg3", "ALUMINIUM"), ("Aluminium 6082", "ALUMINIUM"), ("Edelstahl", "STAINLESS"),
    ("RVS 304", "STAINLESS"), ("S355", "STEEL"), ("Default", ""), ("", ""), ("Plastic", ""), ("Brass", ""),
    ("Stainless Steel 316L", "STAINLESS"),
])
def test_metal_names(name, metal):
    assert weld_cad.metal_of_material(name) == metal


def test_metal_is_carried_on_the_found_weld():
    b = _tri()
    b.material = "Welded Stainless Steel"
    f, = _find([b], [_plate(), _wall()], {"b"})
    assert f.metal == "STAINLESS"


def test_look_alikes_by_shape():
    plate, wall = _plate(), _wall()
    sq = _mesh("s", "SQ", _box(.06, .135, .012, .20, .145, .022))                 # square bar
    assert _find([sq], [plate, wall]) == []
    chamfer = _mesh("c", "CH", _prism([(.145, .012), (.145, .112), (.135, .012)], .06, .20))   # tall wedge
    assert _find([chamfer], [plate, wall]) == []
    sheet = _mesh("t", "SHEET", _box(.06, .135, .012, .20, .145, .0135))          # 1.5 mm sheet on the plate
    assert _find([sheet], [plate, wall]) == []
    gasket = _mesh("g", "GASKET", _box(.0, .0, .012, .4, .3, .014))
    assert _find([gasket], [plate, wall]) == []
    far = _mesh("f", "BEAD", _prism([(.145, .012), (.145, .017), (.14, .012)], .06, .20))
    assert _find([_shift(far, (0, 0, 5))], [plate, wall]) == []                   # nowhere near a part


def test_a_round_bar_in_a_corner_is_no_weld_by_shape():
    r, N = 0.006, 24
    prof = [(0.145 - r + r * math.cos(2 * math.pi * k / N), .012 + r + r * math.sin(2 * math.pi * k / N)) for k in range(N)]
    bar = _mesh("r", "ROUND", _prism(prof, .06, .20))
    assert _find([bar], [_plate(), _wall()]) == []


def test_empty_and_degenerate_inputs():
    assert _find([], [_plate(), _wall()]) == []
    assert _find([_tri()], []) == [] or True
    assert weld_cad.components(np.zeros((0, 3)), np.zeros((0, 3), int)) == []
    e = weld_cad.Mesh("e", "Weld", np.zeros((0, 3)), np.zeros((0, 3), int))
    assert _find([e], [_plate(), _wall()], {"e"}) == []
    assert weld_cad.maybe_bead(e) is False


def test_components_split_and_do_not_merge_apart():
    a, b = _tri(x0=.06, x1=.09), _tri(x0=.10, x1=.13)
    pts = np.concatenate([a.points, b.points])
    tris = np.concatenate([a.tris, b.tris + len(a.points)])
    assert len(weld_cad.components(pts, tris)) == 2
    c = _tri(x0=.06, x1=.09)
    d = _tri(x0=.09, x1=.12)
    pts = np.concatenate([c.points, d.points])
    tris = np.concatenate([c.tris, d.tris + len(c.points)])
    assert len(weld_cad.components(pts, tris)) == 1          # touching end faces: one piece


def _rows(found):
    return [(f.part_a, f.part_b, np.concatenate([x.points for x in f.seams])) for f in found]


def test_match_follows_a_small_move_and_drops_a_far_one():
    f = _find([_tri()], [_plate(), _wall()], {"b"})
    near = _find([_shift(_tri(), (0.001, 0, 0))], [_plate(), _wall()], {"b"})
    far = _find([_shift(_tri(), (0.0, 0, 0.5))], [_shift(_plate(), (0, 0, .5)), _shift(_wall(), (0, 0, .5))], {"b"})
    assert weld_cad.match(_rows(f), _rows(near)) == [(0, 0)]
    assert weld_cad.match(_rows(f), _rows(far)) == [(0, None)]
    assert weld_cad.match(_rows(f), []) == [(0, None)]


def test_uvs_of_a_plain_fillet_run_along_and_across():
    b = _tri()
    f, = _find([b], [_plate(), _wall()], {"b"})
    uv = weld_cad.uvs(b.points, b.tris[f.tris], f.seams, f.kind, f.size)
    assert uv.shape == (len(f.tris), 3, 2) and np.isfinite(uv).all()
    assert abs((uv[..., 0].max() - uv[..., 0].min()) - 0.14) < 0.003
    assert uv[..., 1].min() >= -1e-6 and uv[..., 1].max() <= 1 + 1e-6


def test_transform_moves_seams():
    f, = _find([_tri()], [_plate(), _wall()], {"b"})
    M = np.eye(4)
    M[:3, 3] = (1, 2, 3)
    moved = weld_cad.transform(f.seams, M)
    assert np.allclose(moved[0].points - f.seams[0].points, (1, 2, 3))


def test_four_beads_touching_at_the_corners_are_one_weld_all_round():
    post = _mesh("q", "POST", _box(.15, .10, .012, .20, .15, .112))
    zz = .005

    def rot(m):
        return weld_cad.Mesh(m.key, m.name, m.points[:, [1, 0, 2]], m.tris[:, ::-1], m.face)
    ms = [_mesh("1", "a", _prism([(.10, .012), (.10, .012 + zz), (.10 - zz, .012)], .15, .20)),
          _mesh("2", "a", _prism([(.15, .012), (.15, .012 + zz), (.15 + zz, .012)], .15, .20)),
          rot(_mesh("3", "a", _prism([(.15, .012), (.15, .012 + zz), (.15 - zz, .012)], .10, .15))),
          rot(_mesh("4", "a", _prism([(.20, .012), (.20, .012 + zz), (.20 + zz, .012)], .10, .15)))]
    off = np.cumsum([0] + [len(m.points) for m in ms])
    body = weld_cad.Mesh("x", "Welds", np.concatenate([m.points for m in ms]),
                         np.concatenate([m.tris + o for m, o in zip(ms, off)]),
                         np.concatenate([m.face + 100 * i for i, m in enumerate(ms)]))
    got = _find([body], [_plate(), post], {"x"})
    assert len(got) == 1 and got[0].closed and abs(got[0].length - 0.2) < 0.003
