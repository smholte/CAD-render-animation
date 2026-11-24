"""Task 0319: welds without Blender – the seam finder, the bead, the rules (core/welds.py).

Shapes from ``weld_shapes.py`` (each CAD face its own points, as the importer makes them; metres)."""

import math

import numpy as np
import pytest

from fresing_render.core import welds as W

from weld_shapes import along_y, box, cylinder, plate_with_hole, tube_coped

PLATE = ((0, 0, 0), (0.3, 0.2, 0.01))
FIN = ((0.05, 0.095, 0.01), (0.25, 0.105, 0.11))           # 10 mm plate standing on PLATE, 200 mm long


def side(mesh, picked=None):
    p, t, f = mesh
    return W.Side(p, t, f, None if picked is None else np.isin(f, picked))


def summary(seams):
    return sorted((s.kind, round(s.length, 4), s.closed) for s in seams)


# ---------------------------------------------------------------------------
# finding the seams
# ---------------------------------------------------------------------------

def test_t_joint_two_parts_gives_both_sides_and_the_ends():
    s = W.find_seams(side(box(*PLATE)), side(box(*FIN)))
    assert summary(s) == [("FILLET", 0.01, False)] * 2 + [("FILLET", 0.2, False)] * 2
    for x in s:
        assert x.angle() == pytest.approx(90.0, abs=1.0)
        assert np.allclose(x.points[:, 2], 0.01, atol=1e-6)


def test_t_joint_picked_faces_give_only_that_line():
    """Inventor's way: the plate's top face and one side of the fin -> one seam, on that side."""
    s = W.find_seams(side(box(*PLATE), [1]), side(box(*FIN), [2]))       # top, -y side
    assert summary(s) == [("FILLET", 0.2, False)]
    assert np.allclose(s[0].points[:, 1], 0.095, atol=1e-6)
    assert s[0].faces(side(box(*PLATE), [1]).prepare(), "A") == {1}


def test_faces_that_do_not_meet_give_nothing():
    s = W.find_seams(side(box(*PLATE), [0]), side(box(*FIN), [2]))       # the plate's bottom face
    assert s == []
    far = ((0.05, 0.095, 0.02), (0.25, 0.105, 0.11))                     # 10 mm above the plate
    assert W.find_seams(side(box(*PLATE)), side(box(*far))) == []


def test_small_gap_counts_and_a_larger_one_does_not():
    gap1 = ((0.05, 0.095, 0.0115), (0.25, 0.105, 0.11))                 # 1.5 mm root gap
    assert len(W.find_seams(side(box(*PLATE)), side(box(*gap1)))) == 4
    assert W.find_seams(side(box(*PLATE)), side(box(*gap1)), gap=0.001) == []


def test_butt_joint_both_faces():
    s = W.find_seams(side(box(*PLATE)), side(box((0.3, 0, 0), (0.5, 0.2, 0.01))))
    long = [x for x in s if x.length > 0.1]
    assert len(long) == 2 and all(x.kind == "BUTT" for x in long)
    assert sorted(round(float(x.points[0, 2]), 4) for x in long) == [0.0, 0.01]
    assert all(x.angle() == pytest.approx(180.0, abs=1.0) for x in long)


def test_lap_joint_overhang_both_corners_full_length():
    s = W.find_seams(side(box(*PLATE)), side(box((0.2, 0.05, 0.01), (0.4, 0.15, 0.02))))
    assert summary(s) == [("FILLET", 0.1, False)] * 4                  # three edges of the top plate + the overhang


def test_seam_ends_where_the_joint_ends():
    """A piece of edge that leaves the other part: the seam stops at the other part's edge, not a sample early."""
    s = W.find_seams(side(box(*PLATE)), side(box((0.2, 0.05, 0.01), (0.4, 0.15, 0.02))))
    xs = [x for x in s if np.allclose(x.points[:, 1], 0.05, atol=1e-6)]
    assert xs and xs[0].points[:, 0].max() == pytest.approx(0.3, abs=1e-4)


def test_tube_in_a_hole_is_two_closed_all_round_seams():
    s = W.find_seams(side(plate_with_hole(0.1, 0.03, 0.0, 0.01, 48)), side(cylinder(0.03, -0.05, 0.1, 48)))
    assert len(s) == 2 and all(x.closed for x in s)
    circle = 2 * 48 * 0.03 * math.sin(math.pi / 48)
    assert all(x.length == pytest.approx(circle, rel=1e-3) for x in s)
    assert sorted(round(float(x.points[0, 2]), 4) for x in s) == [0.0, 0.01]


def test_tube_pushed_through_a_plate_without_a_hole_is_a_crossing():
    s = W.find_seams(side(box((-0.1, -0.1, 0), (0.1, 0.1, 0.01))), side(cylinder(0.03, -0.05, 0.1, 48)))
    assert len(s) == 2 and all(x.closed and x.kind == "FILLET" for x in s)
    assert all(x.length == pytest.approx(2 * math.pi * 0.03, rel=0.01) for x in s)


def test_saddle_coped_and_uncoped():
    R, r = 0.0445, 0.024
    main = side(along_y(*cylinder(R, -0.2, 0.2, 64)))
    for branch in (tube_coped(r, R, 0.15, 48), cylinder(r, 0.0, 0.15, 48)):
        s = W.find_seams(main, side(branch))
        assert len(s) == 1 and s[0].closed and s[0].kind == "FILLET"
        assert 0.14 < s[0].length < 0.17                              # the saddle is longer than the circle 0.151
        th = [c.theta for c in s[0].corners]
        assert 80 < min(th) and max(th) < 135                          # 90° at the crown, opening at the flanks


def test_contact_faces_are_not_a_crossing():
    """Two plates lying on each other (a tiny overlap) give their edges, never a line inside the contact."""
    s = W.find_seams(side(box(*PLATE)), side(box((0.1, 0.05, 0.00999), (0.2, 0.15, 0.03))))
    assert len(s) == 4
    for x in s:
        inside = (0.1 + 1e-4 < x.points[:, 0]).all() & (x.points[:, 0] < 0.2 - 1e-4).all() \
            & (0.05 + 1e-4 < x.points[:, 1]).all() & (x.points[:, 1] < 0.15 - 1e-4).all()
        assert not inside


def test_seams_do_not_depend_on_which_part_is_first():
    a, b = box(*PLATE), box(*FIN)
    s1 = summary(W.find_seams(side(a), side(b)))
    s2 = summary(W.find_seams(side(b), side(a)))
    assert s1 == s2


# ---------------------------------------------------------------------------
# the bead
# ---------------------------------------------------------------------------

def _t_seam():
    a, b = side(box(*PLATE), [1]), side(box(*FIN), [2])
    return W.find_seams(a, b)[0], a, b


def test_fillet_bead_size_and_place():
    seam, a, b = _t_seam()
    m = W.bead(seam, W.Look(size=0.004))
    assert set(m.mat) == {0}
    z = 0.004 / math.cos(math.radians(45))
    assert m.verts[:, 2].max() == pytest.approx(0.01 + z, abs=2e-4)      # the toe on the fin
    assert m.verts[:, 1].min() == pytest.approx(0.095 - z, abs=2e-4)     # the toe on the plate
    assert m.verts[:, 0].min() < 0.05 and m.verts[:, 0].max() > 0.25     # the ends taper past the seam
    assert m.length == pytest.approx(0.2)
    assert len(m.uv) == 4 * len(m.faces)
    # a straight seam is light: rings only at its ends (and the tapers)
    assert len(m.verts) <= 9 * 8


def test_butt_bead_is_a_low_crown():
    s = [x for x in W.find_seams(side(box(*PLATE)), side(box((0.3, 0, 0), (0.5, 0.2, 0.01)))) if x.length > 0.1]
    top = max(s, key=lambda x: x.points[0, 2])
    m = W.bead(top, W.Look(size=0.012))
    assert m.verts[:, 0].min() == pytest.approx(0.3 - 0.006, abs=3e-4)
    assert m.verts[:, 0].max() == pytest.approx(0.3 + 0.006, abs=3e-4)
    crown = m.verts[:, 2].max() - 0.01
    assert 0.0005 < crown < 0.002
    flush = W.bead(top, W.Look(size=0.012, finish="GROUND"))
    assert flush.verts[:, 2].max() - 0.01 < 1e-4


def test_heat_zone_lies_on_the_parts():
    for mesh_a, mesh_b in ((box(*PLATE), box(*FIN)),
                           (plate_with_hole(0.1, 0.03, 0.0, 0.01, 48), cylinder(0.03, -0.05, 0.1, 48))):
        a, b = side(mesh_a), side(mesh_b)
        seam = W.find_seams(a, b)[0]
        m = W.bead(seam, W.Look(size=0.005, heat=0.012), a, b)
        idx = np.unique([i for f, k in zip(m.faces, m.mat) if k == 1 for i in f])
        assert len(idx)
        hv = m.verts[idx]
        da, _q, _t = a.distance(hv)
        db, _q, _t = b.distance(hv)
        assert np.minimum(da, db).max() == pytest.approx(W.LIFT, abs=2e-5)


def test_intermittent_and_craters():
    seam, a, b = _t_seam()
    look = W.Look(size=0.004, intermittent=True, length=0.04, pitch=0.07)
    assert np.allclose(W.pieces_of(0.2, look, False), [(0.01, 0.05), (0.08, 0.12), (0.15, 0.19)])
    m = W.bead(seam, look)
    assert m.length == pytest.approx(0.12)
    # continuous when the pitch is not longer than a piece
    assert W.pieces_of(0.2, W.Look(intermittent=True, length=0.05, pitch=0.05), False) == [(0.0, 0.2)]
    plain = W.bead(seam, W.Look(size=0.004))
    cr = W.bead(seam, W.Look(size=0.004, craters=True))
    assert len(cr.verts) == len(plain.verts)
    assert not np.allclose(cr.verts, plain.verts)                         # the end rings dip


def test_end_distance_fades_the_heat_zone():
    seam, a, b = _t_seam()
    m = W.bead(seam, W.Look(size=0.004, heat=0.01), a, b)
    assert len(m.end) == len(m.uv)
    assert {(round(a, 6), round(b, 6)) for a, b in m.end} == {(0.0, 0.2)}


def test_closed_seam_bead_has_no_ends():
    s = W.find_seams(side(plate_with_hole(0.1, 0.03, 0.0, 0.01, 48)), side(cylinder(0.03, -0.05, 0.1, 48)))
    m = W.bead(s[0], W.Look(size=0.004))
    assert set(m.end) == {(-1000.0, 1000.0)}
    # every ring joins the next and the last joins the first: one closed band
    n_rings = len(m.verts) // 9
    assert len(m.faces) == n_rings * 8


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mid, cat, want", [
    ("stainless_brushed", "Metal", "STAINLESS"), ("aluminium_machined", "Metal", "ALUMINIUM"),
    ("galvanized", "Fastener finish", "GALVANISED"), ("paint_satin", "Paint", "PAINTED"),
    ("powder_coat", "Paint", "PAINTED"), ("steel_raw", "Metal", "STEEL"), ("steel_machined", "Metal", "STEEL"),
    ("rubber_black", "Plastic & rubber", "OTHER"), ("brass", "Metal", "OTHER")])
def test_metal_of(mid, cat, want):
    assert W.metal_of(mid, cat) == want


def test_defaults_from_the_looks_and_the_plate():
    d = W.defaults("PAINTED", "STEEL", 10.0)
    assert d["metal"] == "STEEL" and d["process"] == "MAG" and d["finish"] == "PAINTED" and d["paint_from"] == "A"
    assert d["size"] == 5.0
    d = W.defaults("STEEL", "PAINTED", 10.0)
    assert d["paint_from"] == "B"
    assert W.defaults("STAINLESS", "STAINLESS", 3.0)["process"] == "TIG"
    assert W.defaults("ALUMINIUM", "ALUMINIUM", 8.0)["process"] == "MIG"
    assert W.defaults("ALUMINIUM", "ALUMINIUM", 2.0)["process"] == "TIG"
    assert W.defaults("STEEL", "STEEL", 2.0)["size"] == 2.0                # never below 2 mm
    assert W.defaults("GALVANISED", "STEEL", 6.0)["zinc"]


def test_warning_only_for_two_metals():
    assert W.warning("STEEL", "PAINTED") == ""
    assert W.warning("STEEL", "GALVANISED") == ""
    assert "aluminium" in W.warning("STEEL", "ALUMINIUM")
    assert W.warning("STEEL", "OTHER")


def test_rust_where_it_is_logical():
    bare = W.rust_of("STEEL", "AS_WELDED", 0.5, 0.0, False, False, False)
    assert bare["bead"] > 0.5 and bare["heat"] > 0.5                       # more than the plate's 0.5
    painted = W.rust_of("STEEL", "PAINTED", 0.5, 0.0, False, False, False)
    assert painted == {"bead": 0.0, "heat": 0.0, "toes": 0.0, "tea": 0.0}   # no wear: no rust
    assert W.rust_of("STEEL", "PAINTED", 0.5, 0.4, False, False, False)["toes"] > 0
    assert W.rust_of("STEEL", "AS_WELDED", 0.5, 0.0, True, True, False)["bead"] == 0.0     # zinc sprayed after
    assert W.rust_of("STEEL", "AS_WELDED", 0.5, 0.0, True, False, False)["bead"] > 0        # zinc burnt off
    st = W.rust_of("STAINLESS", "AS_WELDED", 1.0, 0.0, False, False, False)
    assert st["bead"] == 0 and 0 < st["tea"] < 0.5
    assert W.rust_of("STAINLESS", "AS_WELDED", 1.0, 0.0, False, False, True)["tea"] == 0
    assert set(W.rust_of("ALUMINIUM", "AS_WELDED", 1.0, 1.0, False, False, False).values()) == {0.0}


def test_thickness():
    a = side(box(*PLATE)).prepare()
    assert W.thickness(a, (0.1, 0.05, 0.01), (0, 0, 1)) == pytest.approx(0.01, abs=1e-5)
    assert W.thickness(a, (0.1, 0.05, 0.01), (0, 0, -1)) == 0.0


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------

def test_faces_found_again_after_renumbering():
    p, t, f = box(*FIN)
    prints = W.face_prints(p, t, f, [2, 3])
    order = np.array([5, 4, 3, 2, 1, 0])                                   # the new revision numbers its faces anew
    assert W.match_faces(prints, p, t, order[f]) == {2: 3, 3: 2}


def test_faces_lost_when_they_changed():
    p, t, f = box(*FIN)
    prints = W.face_prints(p, t, f, [2])
    p2, t2, f2 = box((0.05, 0.095, 0.01), (0.25, 0.105, 0.15))              # 40 mm taller: the side face is bigger
    assert W.match_faces(prints, p2, t2, f2) == {2: None}
    p3 = p + 0.0002                                                         # moved 0.2 mm: still found
    assert W.match_faces(prints, p3, t, f) == {2: 2}


def test_hollow_tube_in_a_hole_its_bore_does_not_count():
    """A tube with a bore 5 mm inside its outer face: the bore is near the line but never 'touches' it (found by the
    test weldment: the bore cut the rim seam into pieces)."""
    out_ = cylinder(0.03015, -0.02, 0.15, 40, caps=False)
    bore = cylinder(0.02515, -0.02, 0.15, 36, inside=True, caps=False)
    p = np.concatenate([out_[0], bore[0]])
    t = np.concatenate([out_[1], bore[1] + len(out_[0])])
    f = np.concatenate([out_[2], bore[2] + 1])
    s = W.find_seams(side(plate_with_hole(0.1, 0.03015, 0.0, 0.012, 48)), side((p, t, f)))
    assert len(s) == 2 and all(x.closed for x in s)


def test_heat_zone_never_dips_under_a_curved_part():
    """A flat strip between two rows cuts under a round, faceted face (seen as streaks in a render): more rows there."""
    a, b = side(plate_with_hole(0.1, 0.03, 0.0, 0.01, 24)), side(cylinder(0.03, -0.05, 0.1, 24))
    seam = W.find_seams(a, b)[0]
    m = W.bead(seam, W.Look(size=0.004, heat=0.012), a, b)
    for k, f in enumerate(m.faces):
        if m.mat[k] != 1:
            continue
        v = m.verts[list(f)]
        mid = v.mean(0)
        for side_ in (a, b):
            d, q, t = side_.distance(mid[None])
            if d[0] < 0.002:
                assert float((mid - q[0]) @ side_.n[t[0]]) > -1e-6
