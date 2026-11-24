"""Task 0319: an independent tester's checks of the welds (core/welds.py and blender/welds.py, ops_welds.py).

Written from the brief by someone who did not write the code, to break it. A test whose docstring starts with
"FAULT:" fails on purpose: it shows a fault found in the code as it was handed over (the docstring says what is wrong).
The other tests pass and pin behaviour that was checked and found right.

Shapes: ``weld_shapes.py`` (each CAD face its own points, as the importer makes them) plus a few made here (a prism
over any polygon: plates at an angle). Metres."""

import json
import math

import numpy as np
import pytest

from fresing_render.core import welds as W

from weld_shapes import box, cylinder, plate_with_hole

PLATE = ((0, 0, 0), (0.3, 0.2, 0.01))
FIN = ((0.05, 0.095, 0.01), (0.25, 0.105, 0.11))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def side(mesh, picked=None):
    p, t, f = mesh
    return W.Side(p, t, f, None if picked is None else np.isin(f, picked))


def summary(seams):
    return sorted((s.kind, round(s.length, 4), s.closed) for s in seams)


def prism(poly_yz, x0, x1):
    """A prism along x over a convex polygon in (y, z); every face its own points, outward normals."""
    P = np.asarray(poly_yz, float)
    area = 0.5 * sum(P[i, 0] * P[(i + 1) % len(P), 1] - P[(i + 1) % len(P), 0] * P[i, 1] for i in range(len(P)))
    if area < 0:
        P = P[::-1]
    pts, tris, face = [], [], []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        base = len(pts)
        pts += [[x0, a[0], a[1]], [x1, a[0], a[1]], [x1, b[0], b[1]], [x0, b[0], b[1]]]
        tris += [[base, base + 3, base + 2], [base, base + 2, base + 1]]
        face += [i, i]
    for f, x, sgn in ((n, x0, -1), (n + 1, x1, 1)):
        base = len(pts)
        for q in P:
            pts.append([x, q[0], q[1]])
        for i in range(1, n - 1):
            t = [base, base + i, base + i + 1]
            tris.append(t[::-1] if sgn < 0 else t)
            face.append(f)
    return np.array(pts, float), np.array(tris), np.array(face)


def outward(mesh) -> bool:
    p, t, _f = mesh
    v = p[t]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    return bool((((v.mean(1) - p.mean(0)) * n).sum(1) > 0).all())


def turned(mesh, deg, about):
    p, t, f = mesh
    a = math.radians(deg)
    R = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    c = np.asarray(about, float)
    return (p - c) @ R.T + c, t, f


def moved(mesh, off):
    p, t, f = mesh
    return p + np.asarray(off, float), t, f


def hollow(ro, wall, z0, z1, n=40):
    """A tube: outer face 0, bore 1, end rings 2 (z0) and 3 (z1)."""
    out_ = cylinder(ro, z0, z1, n, caps=False)
    bore = cylinder(ro - wall, z0, z1, n, inside=True, caps=False)
    a = np.linspace(0, 2 * np.pi, n, endpoint=False)
    P, T, F = [out_[0], bore[0]], [out_[1], bore[1] + len(out_[0])], [out_[2], bore[2] + 1]
    off = len(out_[0]) + len(bore[0])
    for f, z, up in ((2, z0, False), (3, z1, True)):
        pts = [[r * math.cos(x), r * math.sin(x), z] for r in (ro, ro - wall) for x in a]
        tr = []
        for i in range(n):
            j = (i + 1) % n
            t1, t2 = [i, j, n + j], [i, n + j, n + i]
            tr += [t1, t2] if up else [t1[::-1], t2[::-1]]
        P.append(np.array(pts))
        T.append(np.array(tr) + off)
        F.append(np.full(len(tr), f))
        off += len(pts)
    return np.concatenate(P), np.concatenate(T), np.concatenate(F)


def t_joint(t_plate, t_fin, gap=W.GAP):
    plate = box((0, 0, 0), (0.3, 0.2, t_plate))
    fin = box((0.05, 0.1 - t_fin / 2, t_plate), (0.25, 0.1 + t_fin / 2, t_plate + 0.1))
    return W.find_seams(side(plate), side(fin), gap=gap)


# ---------------------------------------------------------------------------
# core: the finder on shapes the author's tests do not have
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("deg", [60.0, 120.0])
def test_plate_standing_at_an_angle(deg):
    """A 10 mm plate leaning at 60° (or 120°) on a plate: two long fillets, one of 60°, one of 120°, plus its ends."""
    h = 0.1
    dy = h / math.tan(math.radians(deg))
    fin = prism([(0.095, 0.01), (0.105, 0.01), (0.105 + dy, 0.01 + h), (0.095 + dy, 0.01 + h)], 0.05, 0.25)
    assert outward(fin)
    s = W.find_seams(side(box(*PLATE)), side(fin))
    long = sorted((x for x in s if x.length > 0.1), key=lambda x: x.angle())
    assert len(long) == 2 and all(x.kind == "FILLET" for x in long)
    assert [round(x.angle()) for x in long] == [60, 120]
    assert all(x.length == pytest.approx(0.2, abs=1e-4) for x in long)


def test_shallow_plate_only_the_open_side():
    """A plate leaning at 30°: its 30° side is too sharp to weld (below 35°), the 150° side is a fillet."""
    h, deg = 0.05, 30.0
    dy = h / math.tan(math.radians(deg))
    t = 0.01 / math.sin(math.radians(deg))
    fin = prism([(0.02, 0.01), (0.02 + t, 0.01), (0.02 + t + dy, 0.01 + h), (0.02 + dy, 0.01 + h)], 0.05, 0.25)
    s = [x for x in W.find_seams(side(box(*PLATE)), side(fin)) if x.length > 0.1]
    assert len(s) == 1 and round(s[0].angle()) == 150


@pytest.mark.parametrize("deg", [17.0, 30.0, 45.0, 73.0])
def test_fin_turned_about_z(deg):
    plate = box((-0.1, -0.1, 0), (0.4, 0.3, 0.01))
    fin = turned(box(*FIN), deg, (0.15, 0.1, 0.0))
    for a, b in ((plate, fin), (fin, plate)):
        s = W.find_seams(side(a), side(b))
        assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2


@pytest.mark.parametrize("off", [(100.0, -100.0, 100.0), (1000.0, 0.0, 0.0)])
def test_far_from_the_origin_in_float32(off):
    """A model 100 m / 1 km from the origin, its points rounded to 32 bits as Blender stores them."""
    def f32(m):
        p, t, f = moved(m, off)
        return p.astype(np.float32).astype(np.float64), t, f
    s = W.find_seams(side(f32(box(*PLATE))), side(f32(box(*FIN))))
    assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2


def test_big_parts():
    """A 5 m plate with a 4 m fin, 20 mm thick: four seams, in well under a few seconds."""
    import time
    t0 = time.perf_counter()
    s = W.find_seams(side(box((0, 0, 0), (5, 4, 0.03))), side(box((0.5, 1.99, 0.03), (4.5, 2.01, 1.0))))
    assert summary(s) == [("FILLET", 0.02, False)] * 2 + [("FILLET", 4.0, False)] * 2
    assert time.perf_counter() - t0 < 10.0


def test_meshes_without_cad_faces_and_with_shared_points():
    """No CAD face data (face -1 everywhere) and a mesh whose faces share points: edges come from the fold angle."""
    def noface(m):
        p, t, _f = m
        return p, t, np.full(len(t), -1)

    def shared_box(lo, hi):
        lo, hi = np.array(lo, float), np.array(hi, float)
        P = np.array([[(lo, hi)[i][0], (lo, hi)[j][1], (lo, hi)[k][2]] for i in (0, 1) for j in (0, 1) for k in (0, 1)])
        ix = lambda i, j, k: i * 4 + j * 2 + k  # noqa: E731
        quads = [[ix(0, 0, 0), ix(0, 1, 0), ix(1, 1, 0), ix(1, 0, 0)], [ix(0, 0, 1), ix(1, 0, 1), ix(1, 1, 1), ix(0, 1, 1)],
                 [ix(0, 0, 0), ix(1, 0, 0), ix(1, 0, 1), ix(0, 0, 1)], [ix(0, 1, 0), ix(0, 1, 1), ix(1, 1, 1), ix(1, 1, 0)],
                 [ix(0, 0, 0), ix(0, 0, 1), ix(0, 1, 1), ix(0, 1, 0)], [ix(1, 0, 0), ix(1, 1, 0), ix(1, 1, 1), ix(1, 0, 1)]]
        T, F = [], []
        for f, q in enumerate(quads):
            T += [[q[0], q[1], q[2]], [q[0], q[2], q[3]]]
            F += [f, f]
        return P, np.array(T), np.array(F)

    want = [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2
    assert summary(W.find_seams(side(noface(box(*PLATE))), side(noface(box(*FIN))))) == want
    assert summary(W.find_seams(side(noface(shared_box(*PLATE))), side(noface(shared_box(*FIN))))) == want
    s = W.find_seams(side(noface(plate_with_hole(0.1, 0.03, 0, 0.01, 48))), side(noface(cylinder(0.03, -0.05, 0.1, 48))))
    assert len(s) == 2 and all(x.closed for x in s)


def test_degenerate_and_non_manifold_triangles_keep_the_real_seams():
    p, t, f = box(*FIN)
    n = len(p)
    p2 = np.concatenate([p, [[0.1, 0.095, 0.05], [0.1, 0.095, 0.05], [0.12, 0.095, 0.05]]])
    t2 = np.concatenate([t, [[n, n + 1, n + 2], [n, n, n]]])               # a zero-area and a one-point triangle
    s = W.find_seams(side(box(*PLATE)), side((p2, t2, np.concatenate([f, [2, 2]]))))
    assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2
    p3 = np.concatenate([p, [[0.05, 0.095, 0.01], [0.25, 0.095, 0.01], [0.15, 0.1, 0.06]]])
    s = W.find_seams(side(box(*PLATE)), side((p3, np.concatenate([t, [[n, n + 1, n + 2]]]), np.concatenate([f, [6]]))))
    long = [x for x in s if x.length > 0.1]
    assert len(long) == 2                                                 # a stray inner triangle: the long seams stay


def test_parts_touching_at_one_point_give_nothing():
    assert W.find_seams(side(box((0, 0, 0), (0.1, 0.1, 0.1))), side(box((0.1, 0.1, 0.1), (0.2, 0.2, 0.2)))) == []


def test_gap_just_inside_and_just_outside():
    def at(z):
        return W.find_seams(side(box(*PLATE)), side(box((0.05, 0.095, z), (0.25, 0.105, 0.11))))
    assert len(at(0.0119)) == 4
    assert at(0.01201) == []


def test_gap_of_exactly_the_tolerance_counts():
    """'Gap up to 2.0 mm': a 2.0 mm root gap is found (floating point must not push it out)."""
    s = W.find_seams(side(box(*PLATE)), side(box((0.05, 0.095, 0.012), (0.25, 0.105, 0.11))))
    assert len(s) == 4


def test_gap_of_exactly_the_tolerance_in_32_bit_numbers():
    """FAULT (low): as Blender hands them over – mesh points and the weld's 'Gap up to' are 32-bit floats – a root gap of
    exactly 2.0 mm (plate top z = 10 mm, fin foot z = 12 mm) gives NO seam with the default gap of 2.0 mm (float32
    0.010 and 0.012 are 2.0000003 mm apart, the gap 2.0000001 mm). The panel says 'Gap up to 2.0 mm'. Needs a small
    allowance (e.g. 1 µm) in the comparison."""
    def f32(m):
        p, t, f = m
        return p.astype(np.float32).astype(np.float64), t, f
    g = float(np.float32(W.GAP))
    s = W.find_seams(side(f32(box(*PLATE))), side(f32(box((0.05, 0.095, 0.012), (0.25, 0.105, 0.11)))), gap=g)
    assert len(s) == 4


@pytest.mark.parametrize("mk", ["lap", "hole", "saddle", "angle"])
def test_order_of_the_parts_does_not_matter(mk):
    if mk == "lap":
        a, b = box(*PLATE), box((0.2, 0.05, 0.01), (0.4, 0.15, 0.02))
    elif mk == "hole":
        a, b = plate_with_hole(0.1, 0.03, 0.0, 0.01, 48), cylinder(0.03, -0.05, 0.1, 48)
    elif mk == "saddle":
        from weld_shapes import along_y
        a, b = along_y(*cylinder(0.0445, -0.2, 0.2, 64)), cylinder(0.024, 0.0, 0.15, 48)
    else:
        dy = 0.1 / math.tan(math.radians(60))
        a, b = box(*PLATE), prism([(0.095, 0.01), (0.105, 0.01), (0.105 + dy, 0.11), (0.095 + dy, 0.11)], 0.05, 0.25)
    s1 = W.find_seams(side(a), side(b))
    s2 = W.find_seams(side(b), side(a))
    assert sorted((s.kind, round(s.length, 3), s.closed) for s in s1) == \
        sorted((s.kind, round(s.length, 3), s.closed) for s in s2)


# --- faults of the finder ---------------------------------------------------

@pytest.mark.parametrize("t_plate, t_fin", [(0.010, 0.002), (0.010, 0.0015), (0.002, 0.010), (0.002, 0.002)])
def test_thin_sheet_t_joint(t_plate, t_fin):
    """FAULT: sheet metal (a part 2 mm thick or less) breaks the finder. A 2 mm fin on a 10 mm plate gives NO seam at
    all (want 2 x 200 mm + 2 ends); a 10 mm fin on a 2 mm plate gives one fillet + a false 'BUTT' 10 mm; 2 mm on 2 mm a
    single false 'BUTT' 200 mm. Cause: ``corners_at`` looks ``reach`` = gap + 0.5 mm = 2.5 mm round the line and treats
    every face found there as passing through the line – the far side of a thin part (its other face) becomes a ray
    of the corner. 3 mm works. Bad: thin sheet weldments (covers, brackets, 1.5–2 mm) are common."""
    s = t_joint(t_plate, t_fin)
    long = [x for x in s if x.length > 0.1]
    assert len(long) == 2 and all(x.kind == "FILLET" and round(x.angle()) == 90 for x in long)
    assert all(x.kind == "FILLET" for x in s)


@pytest.mark.parametrize("wall", [0.002, 0.0015])
def test_thin_wall_tube_in_a_hole_is_all_round(wall):
    """FAULT: a Ø60 tube with a 2 mm (or 1.5 mm) wall through a plate's hole gives two OPEN seams of 94 mm instead of two
    closed all-round seams of 188 mm – half of each weld is missing. Same cause as the thin sheet (the bore 2 mm behind
    the outer face is taken as a face at the line). 3 mm walls work."""
    s = W.find_seams(side(plate_with_hole(0.1, 0.03, 0.0, 0.012, 40)), side(hollow(0.03, wall, -0.02, 0.15, 40)))
    assert len(s) == 2 and all(x.closed for x in s)
    assert all(x.length == pytest.approx(0.1883, abs=0.001) for x in s)


def test_fin_overhanging_the_plate_edge_is_welded_underneath():
    """FAULT: a 10 mm fin running across a plate and past both its ends: the 90° corner between the plate's end face
    and the fin's underside (10 mm long, at x = 0 and x = 0.3) is not found, although ``corners_at`` gives a FILLET at
    every point of it. The plate's edge is the only candidate there, sampled at its two ends only (14 mm < STEP 20 mm),
    and both ends lie 2 mm (the gap) outside the fin, so no sample ever sees the corner. A 30 mm fin gets them. The
    same fin with gap 0 finds pieces of them. Medium: short seams up to ~16 mm (any plate up to 16 mm thick crossing
    an edge) are silently missed."""
    a, b = side(box(*PLATE)), side(box((-0.05, 0.095, 0.01), (0.35, 0.105, 0.11)))
    a.prepare(), b.prepare()
    for x in (0.0, 0.3):
        assert W.corners_at(a, b, (x, 0.1, 0.01), (0, 1, 0), 0.0025)        # the corner is there
    s = W.find_seams(a, b)
    under = [x for x in s if np.allclose(x.points[:, 2], 0.01, atol=1e-6) and np.ptp(x.points[:, 0]) < 1e-6]
    assert len(under) == 2 and all(x.length == pytest.approx(0.01, abs=2e-4) for x in under)


def test_gap_zero_touching_only():
    """FAULT: 'Gap up to' 0 mm (the panel allows it, min 0) – meant as 'touching only' – breaks the seams of parts that
    DO touch: the plain T-joint gives one piece of 49 mm instead of 2 x 200 + 2 x 10 mm, the tube in a hole three open
    pieces instead of two closed rings. Cause: ``d <= gap`` with d a floating-point distance (~1e-17 on the surface)."""
    s = W.find_seams(side(box(*PLATE)), side(box(*FIN)), gap=0.0)
    assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2
    s = W.find_seams(side(plate_with_hole(0.1, 0.03, 0, 0.01, 48)), side(cylinder(0.03, -0.05, 0.1, 48)), gap=0.0)
    assert len(s) == 2 and all(x.closed for x in s)


def test_square_tube_on_a_plate_is_welded_round_its_corners():
    """FAULT (design) found by the independent tester: a square post on a plate gave four open seams, each tapered at
    both ends – a notch at every outside corner. The author's answer (task 0319): the four seams stay separate (each
    side can still be unticked) but are joined at the corners – mitred ends, no taper – so the bead runs round the
    corner without a gap."""
    a, b = side(box(*PLATE)), side(box((0.1, 0.05, 0.01), (0.15, 0.1, 0.2)))
    s = W.find_seams(a, b)
    assert len(s) == 4 and sum(x.length for x in s) == pytest.approx(0.2, abs=1e-3)
    assert all(x.joins[0] is not None and x.joins[1] is not None for x in s)
    look = W.Look(size=0.004)
    meshes = []
    for x in s:
        ends = tuple(s[j[0]].corners[0 if j[1] == 0 else -1] for j in x.joins)
        meshes.append(W.bead(x, look, ends=ends))
    # at each corner of the post the end rings of the two beads are the same points (watertight)
    k = look.across
    for i, x in enumerate(s):
        for e in (0, 1):
            j, f = x.joins[e]
            mine = meshes[i].verts[:k] if e == 0 else meshes[i].verts[-k:]
            theirs = meshes[j].verts[:k] if f == 0 else meshes[j].verts[-k:]
            assert np.abs(mine - theirs[::-1]).max() < 1e-6 or np.abs(mine - theirs).max() < 1e-6
    # and no bead pokes out past the mitre: the toe on the plate reaches the corner's diagonal
    allv = np.concatenate([m.verts for m in meshes])
    z = 0.004 / math.cos(math.radians(45))
    assert allv[:, 0].min() == pytest.approx(0.1 - z, abs=3e-4)


def test_two_corners_on_one_line_are_both_welded():
    """FAULT (low): two blocks touching only along one edge (an outside-corner joint) leave two 90° air corners on the
    same line; ``corners_at`` returns both, but ``find_seams`` takes only ``cs[0]`` of a new run – one side is lost
    (1 seam of 100 mm instead of 2)."""
    a, b = side(box((0, 0, 0), (0.1, 0.1, 0.1))), side(box((0.1, 0.1, 0), (0.2, 0.2, 0.1)))
    a.prepare(), b.prepare()
    assert len(W.corners_at(a, b, (0.1, 0.1, 0.05), (0, 0, 1), 0.0025)) == 2
    assert summary(W.find_seams(a, b)) == [("FILLET", 0.1, False)] * 2


def test_mirrored_placement():
    """FAULT (low): a part placed mirrored (a matrix with negative determinant – a negative scale in Blender, or a
    mirrored STEP instance) comes into ``side_of`` with its points mirrored but its triangles' winding not turned back,
    so its normals point inwards: the T-joint gives 2 seams instead of 4 (B mirrored) or two false BUTTs (A mirrored).
    Here the mirrored placement of a symmetric fin, which must give the same seams."""
    p, t, f = box(*FIN)
    pm = p.copy()
    pm[:, 1] = 0.2 - pm[:, 1]                                         # mirrored about the fin's own mid-plane
    s = W.find_seams(side(box(*PLATE)), side((pm, t, f)))
    assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2


# ---------------------------------------------------------------------------
# core: the bead
# ---------------------------------------------------------------------------

def _t_seam():
    a, b = side(box(*PLATE), [1]), side(box(*FIN), [2])
    return W.find_seams(a, b)[0], a, b


def test_intermittent_pitch_not_longer_than_the_piece_is_continuous():
    seam, a, b = _t_seam()
    m = W.bead(seam, W.Look(size=0.004, intermittent=True, length=0.05, pitch=0.03), a, b)
    assert m.length == pytest.approx(0.2)
    assert np.isfinite(m.verts).all()


@pytest.mark.parametrize("length, pitch", [(0.04, 0.2), (0.199, 0.2), (0.3, 0.5)])
def test_intermittent_odd_numbers(length, pitch):
    seam, a, b = _t_seam()
    look = W.Look(size=0.004, intermittent=True, length=length, pitch=pitch)
    m = W.bead(seam, look, a, b)
    assert np.isfinite(m.verts).all() and len(m.faces)
    assert m.length == pytest.approx(min(length, 0.2), abs=1e-9)
    assert len(m.uv) == sum(len(f) for f in m.faces) == len(m.end)


def test_closed_seam_intermittent():
    a, b = side(plate_with_hole(0.1, 0.03, 0, 0.01, 48)), side(cylinder(0.03, -0.05, 0.1, 48))
    seam = W.find_seams(a, b)[0]
    m = W.bead(seam, W.Look(size=0.004, intermittent=True, length=0.03, pitch=0.05), a, b)
    assert m.length == pytest.approx(0.12)
    assert np.isfinite(m.verts).all()


def test_closed_seam_with_one_intermittent_piece():
    """FAULT: an all-round seam (188 mm) set intermittent with pieces of 100 mm every 150 mm gets ONE piece (0–100 mm)
    from ``pieces_of`` – but ``bead`` then takes 'one piece on a closed seam' for the whole ring and welds all 188 mm
    (``whole = len(pieces) == 1 and closed``). The length reported is 188 mm, not 100. Low–medium: the user sees a
    full ring where they asked for a stitch."""
    a, b = side(plate_with_hole(0.1, 0.03, 0, 0.01, 48)), side(cylinder(0.03, -0.05, 0.1, 48))
    seam = W.find_seams(a, b)[0]
    assert W.pieces_of(seam.length, W.Look(intermittent=True, length=0.1, pitch=0.15), True) == [(0.0, 0.1)]
    m = W.bead(seam, W.Look(size=0.004, intermittent=True, length=0.1, pitch=0.15))
    assert m.length == pytest.approx(0.1)


def test_seam_shorter_than_the_taper():
    """A 4 mm and a 10 mm seam with an 8 mm weld: the tapers are cut to the seam, everything finite."""
    pa, pb = side(box(*PLATE)).prepare(), side(box((0.1, 0.1, 0.01), (0.104, 0.11, 0.05))).prepare()
    for s in W.find_seams(pa, pb):
        m = W.bead(s, W.Look(size=0.008, craters=True), pa, pb)
        assert np.isfinite(m.verts).all() and len(m.faces)
        bead_v = m.verts[[i for f, k in zip(m.faces, m.mat) if k == 0 for i in f]]
        assert np.ptp(bead_v, axis=0).max() < s.length + 0.02


def test_closed_seam_with_few_points():
    """A 12-sided post: the fewest facets that still make one closed seam; its bead is one closed band."""
    pa, pb = side(box((-0.1, -0.1, -0.01), (0.1, 0.1, 0))).prepare(), side(cylinder(0.03, 0, 0.1, 12)).prepare()
    s = W.find_seams(pa, pb)
    assert len(s) == 1 and s[0].closed
    m = W.bead(s[0], W.Look(size=0.004), pa, pb)
    nb = sum(1 for k in m.mat if k == 0)
    assert nb == (sum(1 for k in m.mat if k == 0) // 8) * 8 and np.isfinite(m.verts).all()


def test_forced_kinds_on_any_corner_stay_finite():
    seam, a, b = _t_seam()
    for kind in ("FILLET", "BUTT"):
        for finish in ("AS_WELDED", "GROUND", "PAINTED"):
            m = W.bead(seam, W.Look(size=0.006, kind=kind, finish=finish, craters=True), a, b)
            assert np.isfinite(m.verts).all() and len(m.faces)


# ---------------------------------------------------------------------------
# core: finding faces again after a model update
# ---------------------------------------------------------------------------

def test_match_faces_renumbered_reordered_and_retriangulated():
    p, t, f = box(*FIN)
    prints = W.face_prints(p, t, f, range(6))
    rng = np.random.default_rng(1)
    perm = rng.permutation(len(p))
    p2, t2 = p[perm], np.argsort(perm)[t]
    order = rng.permutation(len(t2))
    new_no = np.array([3, 5, 0, 1, 4, 2])
    assert W.match_faces(prints, p2, t2[order], new_no[f[order]]) == {k: int(new_no[k]) for k in range(6)}
    t3 = t.copy()                                                        # the other diagonal of every quad
    for k in range(0, len(t), 2):
        a, b, c = t[k]
        d = t[k + 1][2]
        t3[k], t3[k + 1] = [a, b, d], [b, c, d]
    assert W.match_faces(prints, p, t3, f) == {k: k for k in range(6)}


def test_match_faces_mirrored_part():
    """A part mirrored in the new revision: its -y face is where the +y face was – matched to that one (right for a
    symmetric part); nothing crashes."""
    p, t, f = box(*FIN)
    prints = W.face_prints(p, t, f, [2, 3])
    pm = p.copy()
    pm[:, 1] = 0.2 - pm[:, 1]
    assert W.match_faces(prints, pm, t[:, ::-1], f) == {2: 3, 3: 2}


def test_match_faces_round_faces():
    cp, ct, cf = cylinder(0.03, 0, 0.1, 32)
    pr = W.face_prints(cp, ct, cf, [0, 1, 2])
    assert W.match_faces(pr, *cylinder(0.03, 0, 0.1, 48)) == {0: 0, 1: 1, 2: 2}       # finer facets
    assert W.match_faces(pr, *cylinder(0.035, 0, 0.1, 32)) == {0: None, 1: None, 2: None}   # another tube
    assert W.match_faces(pr, np.zeros((0, 3)), np.zeros((0, 3), int), np.zeros(0, int)) == {0: None, 1: None, 2: None}


# ---------------------------------------------------------------------------
# Blender
# ---------------------------------------------------------------------------

bpy = None
try:
    import bpy  # noqa: F811
except ImportError:  # pragma: no cover
    pass

if bpy is not None:
    import os

    import addon_utils

    import fresing_render
    from fresing_render.blender import build, ops_welds, welds

    WELDMENT = os.path.join(os.path.dirname(__file__), "data", "test_weldment.step")

    @pytest.fixture(scope="module")
    def addon():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        addon_utils.enable("cycles", default_set=True)
        fresing_render.register()
        yield
        fresing_render.unregister()

    @pytest.fixture()
    def scene(addon):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        addon_utils.enable("cycles", default_set=True)
        assert bpy.ops.fresing.import_step(filepath=WELDMENT, quality="draft") == {"FINISHED"}
        return bpy.context.scene

    def part(sc, name):
        return next(o for o in build.iter_parts(sc) if o[build.PROP_NAME] == name)

    def beads(item):
        return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.KIND]

    def heat(item):
        return [o for o in welds.objects_of(item) if o.get(build.PROP_KIND) == welds.HEAT_KIND]

    def plate_fin(sc):
        return welds.make(sc, part(sc, "BASE PLATE"), [], part(sc, "FIN"), [], whole=True)

    def ticks(item):
        return [(round(s.length * 1000), s.enabled) for s in item.seams]

    def hidden_now(ob):
        bpy.context.view_layer.update()
        return ob.evaluated_get(bpy.context.evaluated_depsgraph_get()).hide_render

    def by_key(sc, key):
        return welds.find_item(sc, key)


needs_bpy = pytest.mark.skipif(bpy is None, reason="bpy not installed")


@needs_bpy
def test_two_welds_on_the_same_pair_and_renaming(scene):
    k1 = plate_fin(scene).key
    k2 = plate_fin(scene).key
    w1, w2 = by_key(scene, k1), by_key(scene, k2)
    assert w1.name != w2.name and len(beads(w1)) == len(beads(w2)) == 1
    by_key(scene, k2).name = by_key(scene, k1).name                       # the same name twice: allowed, kept apart
    assert {o.name for o in welds.objects_of(by_key(scene, k2))}.isdisjoint(
        {o.name for o in welds.objects_of(by_key(scene, k1))})
    by_key(scene, k1).name = "Frame weld"
    assert beads(by_key(scene, k1))[0].name == "Weld Frame weld"
    by_key(scene, k1).size = 0.007                                        # rebuilt after the rename: the same objects
    assert len(welds.objects_of(by_key(scene, k1))) == 2 and len(welds.objects_of(by_key(scene, k2))) == 2
    welds.remove(scene, by_key(scene, k1))
    assert by_key(scene, k1) is None and len(beads(by_key(scene, k2))) == 1
    k3 = plate_fin(scene).key                                             # a key used before may come back
    assert len(welds.objects_of(by_key(scene, k3))) == 2 and len(welds.objects_of(by_key(scene, k2))) == 2


@needs_bpy
def test_many_welds_looked_up_by_key(scene):
    """Collection items move in memory when the list grows: every weld still finds its own objects by key."""
    keys = [plate_fin(scene).key for _ in range(12)]
    assert len(set(keys)) == 12
    for k in keys:
        it = by_key(scene, k)
        assert len(beads(it)) == 1 and beads(it)[0].get(welds.PROP_KEY) == k
    assert welds.stats(scene)["welds"] == 12


@needs_bpy
def test_removing_the_first_part_marks_the_weld_lost(scene):
    key = plate_fin(scene).key
    bpy.data.objects.remove(part(scene, "BASE PLATE"))
    assert welds.lost_parts(scene) == 1
    it = by_key(scene, key)
    assert it.lost and "pick again" in it.note and welds.objects_of(it) == []
    assert welds.lost_parts(scene) == 0
    assert welds.rebuild(it) is False                                     # a lost weld does not come back by itself


@needs_bpy
def test_weld_on_a_hidden_or_excluded_part(scene):
    from fresing_render.blender import logic
    fin = part(scene, "FIN")
    logic.exclude([fin], True)
    it = welds.make(scene, fin, [], part(scene, "BASE PLATE"), [], whole=True)   # the first part is excluded
    b = beads(it)[0]
    assert hidden_now(b)
    logic.exclude([fin], False)
    assert not hidden_now(b)
    logic.set_hidden(part(scene, "BASE PLATE"), True)
    assert hidden_now(b)


@needs_bpy
def test_picker_refuses_what_is_not_a_part_face(scene):
    pk = ops_welds.start(scene)
    base = part(scene, "BASE PLATE")
    it = plate_fin(scene)
    assert pk.click(None, 0) != ""
    assert pk.click(base, -1) != ""
    assert pk.click(beads(it)[0], 0) != ""                                # a bead is not a part
    assert pk.click(build.model_roots(scene)[0], 0) != ""
    assert pk.next() != ""                                               # nothing picked yet
    assert pk.click(base, 99999) == ""                                    # a face the mesh does not have …
    assert pk.next() == ""
    assert pk.click(part(scene, "FIN"), 0) == ""
    assert pk.seams == [] and pk.next() != ""                             # … meets nothing
    ops_welds.finish(scene)


@needs_bpy
def test_carry_over_with_one_part_missing_and_undo(scene):
    it = plate_fin(scene)
    key = it.key
    fin = part(scene, "FIN")
    notes, undo = welds.carry_over(scene, [(fin, fin)])                   # the base plate is not in the new model
    it = by_key(scene, key)
    assert it.lost and "BASE PLATE" in it.note and welds.objects_of(it) == []
    assert len(notes) == 1 and "BASE PLATE" in notes[0]
    undo()
    it = by_key(scene, key)
    assert not it.lost and it.part_a == part(scene, "BASE PLATE") and len(beads(it)) == 1


@needs_bpy
def test_carry_over_same_parts_keeps_picked_faces_and_ticks(scene):
    pk = ops_welds.start(scene)
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    pk.click(base, welds.face_at(base, (0.10, 0.10, 0.012), (0, 0, 1)))
    pk.next()
    pk.click(fin, welds.face_at(fin, (0.15, 0.155, 0.05), (0, 1, 0)))
    pk.click(fin, welds.face_at(fin, (0.15, 0.145, 0.05), (0, -1, 0)), add=True)
    welds.settings(scene).preview[0].enabled = False
    assert pk.next() == ""
    key = pk.item.key
    ops_welds.finish(scene)
    before = (by_key(scene, key).faces_a, by_key(scene, key).faces_b, ticks(by_key(scene, key)))
    notes, _undo = welds.carry_over(scene, [(base, base), (fin, fin)])
    it = by_key(scene, key)
    assert notes == [] and not it.lost
    assert (it.faces_a, it.faces_b, ticks(it)) == before
    assert len(beads(it)) == 1


@needs_bpy
def test_move_as_one_when_both_parts_move_on_different_joints(scene):
    from fresing_render.blender import joints
    it = plate_fin(scene)
    key = it.key
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    joints.create(scene, "SLIDE", [base], (0, 0, 0), (1, 0, 0), name="Table")
    joints.create(scene, "ROTATE", [fin], (0.05, 0.15, 0.012), (1, 0, 0), name="Fin hinge")
    assert welds.moves_apart(by_key(scene, key))
    words = welds.move_as_one(scene, by_key(scene, key))
    assert "Table" in words
    assert not welds.moves_apart(by_key(scene, key))
    bpy.context.view_layer.update()
    rel0 = (base.matrix_world.inverted() @ fin.matrix_world).translation.copy()
    w0 = fin.matrix_world.translation.copy()
    j = next(j for j in scene.fresing.joints if j.name == "Table")
    joints.set_value(j, 0.1)
    bpy.context.view_layer.update()
    assert (fin.matrix_world.translation - w0).length > 0.05                # the fin rides on the table now …
    assert ((base.matrix_world.inverted() @ fin.matrix_world).translation - rel0).length < 1e-6   # … with the plate
    assert len(beads(by_key(scene, key))) == 1


@needs_bpy
def test_save_reopen_with_an_unticked_seam(scene, tmp_path):
    it = plate_fin(scene)
    key = it.key
    it.seams[2].enabled = False
    want = ticks(by_key(scene, key))
    path = str(tmp_path / "weld ticks.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    it = by_key(sc, key)
    assert ticks(it) == want
    it.size = 0.006
    assert ticks(by_key(sc, key)) == want and len(beads(by_key(sc, key))) == 1
    it.gap = 0.0015                                                       # finds the seams again: ticks kept by place
    assert ticks(by_key(sc, key)) == want


@needs_bpy
def test_changing_a_setting_while_the_parts_are_exploded(scene):
    """FAULT: the seams are found again 'with the second part where it is now' at ANY rebuild – also a plain change of
    the size, a tick, or a paint change of the group (``sync_paint`` from the depsgraph handler). In an exploded view
    (or any pose where a joint moved one part) the parts do not meet: the rebuild finds 0 seams, CLEARS the weld's seam
    list (``store_seams`` when the count differs), deletes the bead and heat zone without marking the weld lost or
    saying anything; back in the CAD pose the next change finds the seams again but every seam the user had unticked
    is ticked again (the ticks were thrown away with the list). Brief item 6: 'Exploded views …: the bead stays with
    its part'. Medium–high: silent loss of the user's choices; the bead vanishes from a posed animation frame."""
    from fresing_render.blender import states
    it = plate_fin(scene)
    key = it.key
    it.seams[0].enabled = False
    want = ticks(by_key(scene, key))
    assert len(beads(by_key(scene, key))) == 1
    root = build.model_roots(scene)[0]
    assert states.explode(scene, root, 1.0, level="PARTS") >= 2
    bpy.context.view_layer.update()
    by_key(scene, key).size = 0.006                                       # a plain size change in the exploded view
    it = by_key(scene, key)
    seen_exploded = (len(it.seams), len(beads(it)))
    states.reset_pose(scene)
    bpy.context.view_layer.update()
    by_key(scene, key).size = 0.007
    it = by_key(scene, key)
    assert ticks(it) == want, f"ticks before {want}, after exploding and back {ticks(it)}"
    assert seen_exploded == (4, 1), f"exploded: {seen_exploded[0]} seams, {seen_exploded[1]} bead"


@needs_bpy
def test_changing_a_setting_while_a_joint_holds_the_parts_apart(scene):
    """FAULT: as above, with a joint: the fin on a hinge turned 30°, then the weld's size changed – the weld loses its
    seams and bead (no note, not 'lost'); turned back, the unticked seam comes back ticked."""
    from fresing_render.blender import joints
    it = plate_fin(scene)
    key = it.key
    it.seams[0].enabled = False
    want = ticks(by_key(scene, key))
    j = joints.create(scene, "ROTATE", [part(scene, "FIN")], (0.05, 0.15, 0.012), (1, 0, 0), name="Fin hinge")
    jname = j.name
    joints.set_value(next(x for x in scene.fresing.joints if x.name == jname), math.radians(30))
    bpy.context.view_layer.update()
    by_key(scene, key).size = 0.006
    it = by_key(scene, key)
    seen_posed = (len(it.seams), len(beads(it)), it.lost, it.note)
    joints.set_value(next(x for x in scene.fresing.joints if x.name == jname), 0.0)
    bpy.context.view_layer.update()
    by_key(scene, key).size = 0.007
    assert ticks(by_key(scene, key)) == want, f"ticks before {want}, after the pose and back {ticks(by_key(scene, key))}"
    assert seen_posed[:2] == (4, 1), f"posed: {seen_posed}"


@needs_bpy
def test_clicking_next_to_a_weld_reaches_the_part(scene):
    """FAULT (low–medium): the face picker's ray (``hover.cast``) stops at the first object it hits; the heat-zone strip
    of an existing weld lies 0.05 mm above the part's face, up to ~16 mm wide beside the bead (the bead itself fills
    the corner). A click on the base plate's top 8 mm beside the FIN's bead hits the strip, and the picker says 'Click
    a face of a part' – a second weld (or picking again) on a face next to a weld needs clicks away from it. (Decals
    are looked through by ``decals.through``; welds are not.)"""
    from mathutils import Vector
    from fresing_render.blender import hover
    it = plate_fin(scene)
    base = part(scene, "BASE PLATE")
    h = heat(it)[0]
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    co = np.array([list(h.matrix_world @ v.co) for v in h.data.vertices])
    # the strip on the plate's top beside the long +y side of the fin (y 155 mm): straight, so only end rows
    on_top = co[(np.abs(co[:, 2] - 0.012) < 1e-3) & (co[:, 1] > 0.157)]
    assert len(on_top)
    y = float(np.median(on_top[:, 1]))                                    # about 8 mm beside the fin
    ob, idx, _loc, _n = hover.cast(scene, dg, Vector((0.10, y, 0.5)), Vector((0, 0, -1)))
    assert ob == base and idx >= 0, f"hit {ob.name if ob else None}, polygon {idx}"


@needs_bpy
def test_hiding_a_weld_and_showing_it_again(scene):
    it = plate_fin(scene)
    key = it.key
    b = beads(it)[0]
    by_key(scene, key).hidden = True
    assert hidden_now(b)
    by_key(scene, key).size = 0.006                                       # rebuilt while hidden: stays hidden
    b = beads(by_key(scene, key))[0]
    assert hidden_now(b)
    by_key(scene, key).hidden = False
    assert not hidden_now(beads(by_key(scene, key))[0])


@needs_bpy
def test_pick_again_with_the_parts_the_other_way_round(scene):
    """A weld made plate -> fin, picked again fin -> plate: the bead moves to the fin, one bead, the seam 200 mm."""
    it = plate_fin(scene)
    key = it.key
    base, fin = part(scene, "BASE PLATE"), part(scene, "FIN")
    pk = ops_welds.start(scene, key)
    assert pk.click(fin, welds.face_at(fin, (0.15, 0.155, 0.05), (0, 1, 0))) == ""
    assert pk.next() == ""
    assert pk.click(base, welds.face_at(base, (0.10, 0.10, 0.012), (0, 0, 1))) == ""
    assert pk.next() == ""
    ops_welds.finish(scene)
    it = by_key(scene, key)
    assert len(welds.items(scene)) == 1 and not it.lost and it.part_a == fin
    assert [round(s.length * 1000) for s in it.seams] == [200]
    assert len(beads(it)) == 1 and beads(it)[0].parent == fin
    assert not [c for c in base.children if welds.is_weld(c)]
