"""Task 0013: cylinder geometry without Blender, checked against independent calculations.

The numbers are those of the generic test luffer (tools/make_test_cylinder.py), in mm: arm pivot
(100, 600), barrel pin (500, 150), rod pin (800, 450) in the XZ plane, pins along Y.
"""

import math

import numpy as np
import pytest

from fresing_render.core import cylinders as C

PIVOT = np.array([100.0, 600.0])
BARREL_PIN = np.array([500.0, 150.0])
ROD_PIN = np.array([800.0, 450.0])


def rot2(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1]])


def luffer_drive(sign=1.0):
    """The luffer in the joint's frame: the joint turns about +Y world; its frame's X = world X,
    Y = world -Z... any right-handed frame with Z along the pin axis will do: here (x, -z) -> (X, Y)."""
    b = BARREL_PIN - PIVOT
    r = ROD_PIN - PIVOT
    return C.Drive("ROTATE", (b[0], sign * -b[1], 0.0), (r[0], sign * -r[1], 0.0))


def length_by_rotation(phi, sign=1.0):
    """Independent: rotate the rod pin about the pivot (in the joint frame) and measure."""
    b = BARREL_PIN - PIVOT
    r = ROD_PIN - PIVOT
    bj = np.array([b[0], sign * -b[1]])
    rj = rot2(np.array([r[0], sign * -r[1]]), phi)
    return float(np.linalg.norm(rj - bj))


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_rotate_forward_matches_rotation(sign):
    d = luffer_drive(sign)
    assert d.length_at(0.0) == pytest.approx(math.hypot(300.0, 300.0), abs=1e-9)
    for deg in (-30, -10, 0, 5, 20, 40):
        phi = math.radians(deg)
        assert d.length_at(phi) == pytest.approx(length_by_rotation(phi, sign), abs=1e-9)


@pytest.mark.parametrize("sign", [1.0, -1.0])
def test_rotate_inverse_law_of_cosines_by_hand(sign):
    """Stroke -> arm angle, against the law of cosines written out by hand."""
    d = luffer_drive(sign)
    a = math.hypot(400.0, 450.0)              # pivot - barrel pin
    c = math.hypot(700.0, 150.0)              # pivot - rod pin
    l0 = math.hypot(300.0, 300.0)
    angle0 = math.acos((a * a + c * c - l0 * l0) / (2 * a * c))
    for length in (380.0, 424.0, 470.0, 520.0, 600.0):
        angle = math.acos((a * a + c * c - length * length) / (2 * a * c))
        phi = d.value_for(length)
        # the arm opens (angle at the pivot grows) when the cylinder gets longer
        assert abs(phi) == pytest.approx(abs(angle - angle0), abs=1e-9)
        assert length_by_rotation(phi, sign) == pytest.approx(length, abs=1e-9)
        assert d.length_at(phi) == pytest.approx(length, abs=1e-9)


def test_rotate_keeps_the_cad_side():
    """Of the two arm angles for one length, the one on the CAD pose's side is used: continuous through
    the CAD pose and never through the cylinder's line."""
    d = luffer_drive()
    lengths = np.linspace(300.0, 900.0, 61)
    phis = [d.value_for(x) for x in lengths]
    assert d.value_for(d.length_at(0.0)) == pytest.approx(0.0, abs=1e-9)
    assert all(abs(p2 - p1) < math.radians(15) for p1, p2 in zip(phis, phis[1:]))
    assert all(x2 >= x1 for x1, x2 in zip(phis, phis[1:])) or all(x2 <= x1 for x1, x2 in zip(phis, phis[1:]))


def test_rotate_unreachable_length_gives_the_nearest():
    d = luffer_drive()
    lo, hi = d.reach()
    assert lo == pytest.approx(abs(math.hypot(400, 450) - math.hypot(700, 150)), abs=1e-9)
    assert hi == pytest.approx(math.hypot(400, 450) + math.hypot(700, 150), abs=1e-9)
    assert d.length_at(d.value_for(hi + 500)) == pytest.approx(hi, abs=1e-6)
    assert d.length_at(d.value_for(0.0)) == pytest.approx(lo, abs=1e-6)


def test_rotate_pins_out_of_plane_keep_their_offset():
    d = C.Drive("ROTATE", (400.0, 450.0, 20.0), (700.0, 150.0, 20.0 + 35.0))
    for phi in (-0.3, 0.0, 0.4):
        length = d.length_at(phi)
        assert d.value_for(length) == pytest.approx(phi, abs=1e-9)


def test_slide_against_bisection():
    """A cylinder pushing a carriage along a slide (the joint's Z): a quadratic."""
    b, r0 = (0.0, -0.2, 0.0), (0.05, 0.1, 0.4)
    d = C.Drive("SLIDE", b, r0)

    def length(t):
        return math.dist(b, (r0[0], r0[1], r0[2] + t))

    for target in (0.45, 0.5, 0.6, 0.8):
        lo, hi = -0.3, 1.0                    # the CAD side: the carriage stays on the +Z side
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if length(mid) < target else (lo, mid)
        assert d.value_for(target) == pytest.approx(lo, abs=1e-9)
        assert d.length_at(d.value_for(target)) == pytest.approx(target, abs=1e-9)
    assert d.value_for(length(0.0)) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("kind,b,r,word", [
    ("ROTATE", (0.0, 0.0, 0.0), (1.0, 1.0, 0.0), "pivot axis"),
    ("ROTATE", (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), "straight at"),
    ("SLIDE", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), "right angles"),
])
def test_impossible_drives_say_why(kind, b, r, word):
    with pytest.raises(ValueError, match=word):
        C.Drive(kind, b, r)


def test_axis_frame_and_plane():
    x, y, z = C.axis_frame((0.5, 0.0, 0.15), (0.8, 0.07, 0.45), (0.0, 1.0, 0.0))
    assert np.allclose(z, (0, 1, 0))
    assert np.allclose(x, np.array([0.3, 0, 0.3]) / math.hypot(0.3, 0.3))
    assert np.allclose(np.cross(x, y), z)
    assert np.allclose(C.into_plane((0.8, 0.07, 0.45), (0.5, 0.0, 0.15), (0, -1, 0)), (0.8, 0.0, 0.45))
    assert C.parallel((0, 1, 0), (0, -1, 0.01))
    assert not C.parallel((0, 1, 0), (0, 1, 0.05))


def test_stage_shares():
    assert C.stage_shares(1) == [0.5]
    assert C.stage_shares(2) == pytest.approx([1 / 3, 2 / 3])


# --- the travel estimate, on a cylinder made of triangles -------------------------------------------

def tube(x0, x1, r, n=32):
    """Side of a cylinder along X."""
    a = np.linspace(0, 2 * math.pi, n + 1)
    tris = []
    for i in range(n):
        p = [(x, r * math.cos(t), r * math.sin(t)) for x, t in ((x0, a[i]), (x1, a[i]), (x1, a[i + 1]), (x0, a[i + 1]))]
        tris += [(p[0], p[1], p[2]), (p[0], p[2], p[3])]
    return np.array(tris)


def ring(x, r_in, r_out, n=32):
    """Flat ring (disc when r_in is 0) at right angles to X."""
    a = np.linspace(0, 2 * math.pi, n + 1)
    tris = []
    for i in range(n):
        p = [(x, r * math.cos(t), r * math.sin(t)) for r, t in ((r_in, a[i]), (r_out, a[i]), (r_out, a[i + 1]),
                                                               (r_in, a[i + 1]))]
        tris += [(p[0], p[1], p[2]), (p[0], p[2], p[3])]
    return np.array(tris)


def solid(x0, x1, r_in, r_out):
    parts = [tube(x0, x1, r_out), ring(x0, r_in, r_out), ring(x1, r_in, r_out)]
    if r_in > 0:
        parts.append(tube(x0, x1, r_in))
    return np.concatenate(parts)


L = 0.42426                           # pin to pin in the CAD pose (m)
MM = 0.001


def barrel_tris():
    return np.concatenate([solid(20 * MM, 40 * MM, 0, 50 * MM),          # end cap
                           solid(40 * MM, 260 * MM, 40 * MM, 50 * MM),   # tube
                           solid(260 * MM, 290 * MM, 16 * MM, 50 * MM)])  # gland


def rod_tris():
    return np.concatenate([solid(100 * MM, 130 * MM, 0, 39 * MM),         # piston
                           solid(130 * MM, L - 30 * MM, 0, 15 * MM),      # rod
                           solid(L - 30 * MM, L + 30 * MM, 0, 30 * MM)])  # rod eye (wide)


def test_travel_from_piston_and_barrel_faces():
    t = C.estimate_travel(barrel_tris(), rod_tris(), L)
    assert t.measured
    # in: piston back (100) to the end cap's inner face (40) = 60 mm; out: piston front (130) to the
    # gland (260) = 130 mm
    assert t.closed == pytest.approx(L - 60 * MM, abs=1e-5)
    assert t.full == pytest.approx(190 * MM, abs=1e-5)


def test_travel_guess_without_piston():
    rod = np.concatenate([solid(100 * MM, L, 0, 15 * MM)])
    barrel = solid(40 * MM, 260 * MM, 40 * MM, 50 * MM)          # an open tube: nothing to stop the rod
    t = C.estimate_travel(barrel, rod, L)
    assert not t.measured
    assert t.closed == pytest.approx(L - 60 * MM, abs=1e-5)     # rod end back to the tube's end (40)
    assert t.full == pytest.approx(220 * MM, abs=1e-5)          # ... and out to its front end (260)
