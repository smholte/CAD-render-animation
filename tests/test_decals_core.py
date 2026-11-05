"""Decals (task 0024), the parts without Blender: where a decal lies on a flat or round face, fit
to face, finding the face again, and the pictures made in code (text, CE, warnings, type plate)."""

import math

import numpy as np
import pytest

from fresing_render.core import decal_art as A
from fresing_render.core import decal_geometry as G


# ---------------------------------------------------------------------------
# faces to put decals on
# ---------------------------------------------------------------------------


def plate(w=0.2, h=0.1):
    """A flat face in the XY plane (z = 0) facing +Z: two triangles, w × h metres, centred at 0."""
    a, b, c, d = (-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)
    pos = np.array([[a, b, c], [a, c, d]], dtype=float)
    nrm = np.tile([0.0, 0.0, 1.0], (2, 3, 1))
    return pos, nrm


def barrel(r=0.06, length=0.3, n=64, axis="Z"):
    """The round face of a cylinder (axis along Z or X, through the origin), n segments."""
    ang = np.linspace(0, 2 * math.pi, n + 1)
    pos, nrm = [], []
    for a0, a1 in zip(ang[:-1], ang[1:]):
        p = [(r * math.cos(a), r * math.sin(a), z) for a in (a0, a1) for z in (0.0, length)]
        q = [(math.cos(a), math.sin(a), 0.0) for a in (a0, a1) for _z in (0, 1)]
        pos += [[p[0], p[2], p[3]], [p[0], p[3], p[1]]]
        nrm += [[q[0], q[2], q[3]], [q[0], q[3], q[1]]]
    pos, nrm = np.array(pos), np.array(nrm)
    if axis == "X":                       # lying down: z -> x, x -> y, y -> z
        pos, nrm = pos[..., [2, 0, 1]], nrm[..., [2, 0, 1]]
    return pos, nrm


def area(mesh):
    p, t = mesh["positions"], mesh["triangles"]
    return 0.5 * np.linalg.norm(np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]]), axis=1).sum()


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------


def test_upright_axes_read_left_to_right_from_the_front():
    right, up = G.upright_axes((0, -1, 0), (0, 0, 1))         # a face looking at someone standing at -Y
    assert np.allclose(up, (0, 0, 1)) and np.allclose(right, (1, 0, 0))
    right, up = G.upright_axes((0, 0, 1), (0, 0, 1), (0, 1, 0))   # a top face: the second hint decides
    assert np.allclose(up, (0, 1, 0)) and np.allclose(right, (1, 0, 0))


def test_flat_decal_is_cut_to_its_rectangle():
    pos, nrm = plate()
    fr = G.frame((0, 0, 0), (0, 0, 1), (0, 1, 0))
    m = G.build(pos, nrm, fr, width=0.05, height=0.02)
    assert area(m) == pytest.approx(0.05 * 0.02, rel=1e-9)
    assert np.allclose(m["positions"][:, 2], G.OFFSET)              # lifted off the face
    p = m["positions"]
    assert p[:, 0].min() == pytest.approx(-0.025) and p[:, 0].max() == pytest.approx(0.025)
    assert p[:, 1].min() == pytest.approx(-0.01) and p[:, 1].max() == pytest.approx(0.01)
    # UV 0..1 across the picture, u to the right, v up
    uv = m["uv"]
    assert uv.min() == pytest.approx(0) and uv.max() == pytest.approx(1)
    right = p[:, 0] > 0.02
    assert (uv[right, 0] > 0.9).all()
    mirrored = G.build(pos, nrm, fr, width=0.05, height=0.02, mirror=True)
    assert (mirrored["uv"][mirrored["positions"][:, 0] > 0.02, 0] < 0.1).all()


def test_move_turn_and_size_by_numbers():
    pos, nrm = plate()
    fr = G.frame((0, 0, 0), (0, 0, 1), (0, 1, 0))
    m = G.build(pos, nrm, fr, shift=(0.03, 0.01), width=0.04, height=0.02)
    p = m["positions"]
    assert (p[:, 0].min() + p[:, 0].max()) / 2 == pytest.approx(0.03) and p[:, 1].min() == pytest.approx(0.0)
    turned = G.build(pos, nrm, fr, angle=math.radians(90), width=0.04, height=0.02)["positions"]
    assert np.ptp(turned[:, 0]) == pytest.approx(0.02) and np.ptp(turned[:, 1]) == pytest.approx(0.04)
    # off the edge: only the part on the face is kept
    half_off = G.build(pos, nrm, fr, shift=(0.1, 0.0), width=0.04, height=0.02)
    assert area(half_off) == pytest.approx(0.02 * 0.02, rel=1e-9)
    assert len(G.build(pos, nrm, fr, shift=(0.5, 0.0), width=0.04, height=0.02)["triangles"]) == 0


def test_round_face_is_recognised():
    pos, nrm = barrel()
    cyl = G.fit_cylinder(pos.reshape(-1, 3), nrm.reshape(-1, 3))
    assert cyl is not None and cyl["radius"] == pytest.approx(0.06, rel=1e-6)
    assert abs(cyl["axis"] @ (0, 0, 1)) == pytest.approx(1)
    flat_pos, flat_nrm = plate()
    assert G.fit_cylinder(flat_pos.reshape(-1, 3), flat_nrm.reshape(-1, 3)) is None
    # a sphere-like face (normals pointing every way) is not a cylinder
    rng = np.random.default_rng(1)
    v = G.unit(rng.normal(size=(60, 3)))
    assert G.fit_cylinder(0.05 * v, v) is None


def test_decal_wraps_round_a_barrel_like_a_sticker():
    pos, nrm = barrel()
    cyl = G.fit_cylinder(pos.reshape(-1, 3), nrm.reshape(-1, 3))
    anchor = (0.06, 0.0, 0.15)
    fr = G.frame(anchor, (1, 0, 0), (0, 0, 1), cyl)
    m = G.build(pos, nrm, fr, width=0.1, height=0.04)
    p = m["positions"]
    radius = np.hypot(p[:, 0], p[:, 1])
    # every point lies on the barrel's surface (a chord of it), just outside
    assert radius.max() == pytest.approx(0.06 + G.OFFSET, rel=1e-4) and radius.min() > 0.0599
    angles = np.arctan2(p[:, 1], p[:, 0])
    assert np.ptp(angles) == pytest.approx(0.1 / 0.06, rel=1e-3)        # 100 mm of arc
    assert np.ptp(p[:, 2]) == pytest.approx(0.04)
    assert area(m) == pytest.approx(0.1 * 0.04 * (0.06 + G.OFFSET) / 0.06, rel=1e-3)   # unrolled: no stretching
    # a decal longer than half the circumference still wraps (no projection limit)
    long = G.build(pos, nrm, fr, width=0.25, height=0.04)
    assert np.ptp(np.arctan2(long["positions"][:, 1], long["positions"][:, 0])) > math.pi
    # a lying barrel: text runs along it, upright (up = world Z wraps round it)
    pos_x, nrm_x = barrel(axis="X")
    cyl_x = G.fit_cylinder(pos_x.reshape(-1, 3), nrm_x.reshape(-1, 3))
    fr_x = G.frame((0.15, -0.06, 0.0), (0, -1, 0), (0, 0, 1), cyl_x)
    side = G.build(pos_x, nrm_x, fr_x, width=0.12, height=0.03)
    assert np.ptp(side["positions"][:, 0]) == pytest.approx(0.12)
    right = side["positions"][:, 0] > 0.15 + 0.05
    assert (side["uv"][right, 0] > 0.9).all()                            # seen from -Y, +X is right


def test_fit_to_face_and_default_size():
    pos, nrm = plate(0.2, 0.1)
    fr = G.frame((0.05, 0.02, 0), (0, 0, 1), (0, 1, 0))
    shift, w, h = G.fit_to_face(pos, nrm, fr, aspect=0.5)
    assert shift == pytest.approx((-0.05, -0.02), abs=1e-9)              # centred on the face again
    assert (w, h) == pytest.approx((0.9 * 0.2, 0.9 * 0.1), rel=1e-6)
    turned_shift, tw, th = G.fit_to_face(pos, nrm, fr, angle=math.radians(90), aspect=0.5)
    assert turned_shift == pytest.approx((-0.05, -0.02), abs=1e-9) and tw == pytest.approx(0.9 * 0.1, rel=1e-6)
    # a round disc: the square must lie inside the circle, not its outline box
    ang = np.linspace(0, 2 * math.pi, 97)
    disc = np.array([[(0, 0, 0), (0.05 * math.cos(a0), 0.05 * math.sin(a0), 0), (0.05 * math.cos(a1), 0.05 * math.sin(a1), 0)]
                     for a0, a1 in zip(ang[:-1], ang[1:])])
    dn = np.tile([0.0, 0.0, 1.0], (len(disc), 3, 1))
    _s, dw, dh = G.fit_to_face(disc, dn, G.frame((0, 0, 0), (0, 0, 1), (0, 1, 0)), aspect=1.0)
    assert dw <= 0.9 * 0.1 / math.sqrt(2) + 1e-6 and dw > 0.8 * 0.9 * 0.1 / math.sqrt(2)


def test_locate_finds_the_face_again_or_says_it_moved():
    pos, nrm = plate()
    assert G.locate(pos, (0.05, 0.0, 0.0), (0, 0, 1)) == 0
    assert G.locate(pos, (-0.05, 0.03, 0.0002), (0, 0, 1)) == 1
    assert G.locate(pos, (0.05, 0.03, 0.005), (0, 0, 1)) == -1           # the face moved 5 mm
    assert G.locate(pos, (0.05, 0.03, 0.0), (0, 0, -1)) == -1            # facing the other way
    assert G.locate(pos, (0.3, 0.0, 0.0), (0, 0, 1)) == -1               # off the face


# ---------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------


def fake_glyphs(text):
    """One box per letter (0.6 wide, 0.7 high), as a font would give triangles."""
    tris = []
    for i, ch in enumerate(text):
        if ch == " ":
            continue
        x0, x1 = 0.65 * i, 0.65 * i + 0.6
        tris += [[(x0, 0), (x1, 0), (x1, 0.7)], [(x0, 0), (x1, 0.7), (x0, 0.7)]]
    return np.array(tris, dtype=float).reshape(-1, 3, 2)


def test_filled_shapes_cover_the_right_area():
    sq = A.coverage([A.rect(10, 10, 30, 20)], 40, 40)
    assert sq.sum() == pytest.approx(200, abs=1e-3)
    assert sq[15, 20] == 1.0 and sq[5, 5] == 0.0
    half = A.coverage([A.rect(10.5, 10, 20, 20)], 40, 40)
    assert half[15, 10] == pytest.approx(0.5)                             # a pixel half covered
    c = A.coverage([A.circle(50, 50, 30, 256)], 100, 100)
    assert c.sum() == pytest.approx(math.pi * 900, rel=2e-3)
    # overlapping shapes: the union, whichever way round they are drawn
    two = A.coverage([A.rect(0, 0, 20, 20), A.rect(10, 0, 30, 20)[::-1]], 40, 40)
    assert two.sum() == pytest.approx(600, abs=1e-3)


def test_text_art_lines_and_plate():
    one = A.text_art(fake_glyphs, "ABC")
    two = A.text_art(fake_glyphs, "ABC|DEFG")
    assert two.height > 1.8 * one.height * 0.9 and two.width > one.width
    assert one.masks[..., A.INK].max() == 1.0
    # the field covers the picture, the border lies just inside its edge
    f = one.masks[..., A.FIELD]
    assert f[one.height // 2, one.width // 2] == 1.0
    e = one.masks[..., A.EDGE]
    assert e[one.height // 2, :one.width // 20].max() == 1.0 and e[one.height // 2, one.width // 2] == 0.0
    assert not one.use_field and not one.use_edge                         # both off at first


def test_every_sticker_is_drawn():
    for st in A.STICKERS:
        art = A.sticker_art(st.key, fake_glyphs, {"company": "ACME", "type": "T1", "serial": "1", "year": "2026",
                                                  "weight": "5 kg"})
        ink = art.masks[..., A.INK]
        assert 0.03 < ink.mean() < 0.6, st.key
        assert art.masks.dtype == np.float32 and 0.3 < art.aspect < 1.2, st.key
    warn = A.sticker_art("WARN_ELECTRIC")
    assert warn.use_field and warn.field == A.YELLOW
    centre = warn.masks[int(warn.height * 0.62), warn.width // 2 - 150]
    assert centre[A.FIELD] == 1.0                                         # yellow inside the triangle
    with pytest.raises(ValueError):
        A.sticker_art("TYPE_PLATE")                                       # its text needs a font


def test_type_plate_shows_its_fields():
    empty = A.sticker_art("TYPE_PLATE", fake_glyphs, {"company": "ACME"})
    full = A.sticker_art("TYPE_PLATE", fake_glyphs, {"company": "ACME", "type": "T-1", "serial": "SN 42",
                                                     "year": "2026", "weight": "1,250 kg"})
    assert full.masks[..., A.INK].sum() > empty.masks[..., A.INK].sum() * 1.3


def test_hex_to_linear():
    assert A.hex_to_linear("#FFFFFF") == pytest.approx((1, 1, 1))
    assert A.hex_to_linear("#808080")[0] == pytest.approx(0.2158, abs=1e-3)
