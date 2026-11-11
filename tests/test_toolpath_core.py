"""Task 0029: the app makes the toolpath - core/toolpath.py, no Blender.

The drop-cutter against shapes worked out by hand (a sphere, a slope, a step) for flat, ball and bull-nose tools;
roughing levels, leave stock and ramps; finishing never in the part; the program reads with our own reader; the
undercut and the hole of the test model (tools/make_test_toolpath.py) are left alone.
"""

import math

import numpy as np
import pytest

from fresing_render.core import gcode, tools
from fresing_render.core import toolpath as tp

pytest.importorskip("OCP")

import toolpath_shapes  # noqa: E402

MM = 0.001


# ---------------------------------------------------------------------------
# hand-made shapes
# ---------------------------------------------------------------------------

def sphere(r=20.0, n=96):
    """A sphere round the origin, its corners on the sphere (so the mesh lies inside it)."""
    th = np.linspace(0, math.pi, n // 2 + 1)
    ph = np.linspace(0, 2 * math.pi, n + 1)
    P = np.stack([np.outer(np.sin(th), np.cos(ph)), np.outer(np.sin(th), np.sin(ph)),
                  np.outer(np.cos(th), np.ones_like(ph))], axis=-1) * r
    tris = []
    for i in range(len(th) - 1):
        for j in range(len(ph) - 1):
            a, b, c, d = P[i, j], P[i, j + 1], P[i + 1, j + 1], P[i + 1, j]
            tris += [(a, b, c), (a, c, d)]
    return np.array(tris)


def box(x0, y0, z0, x1, y1, z1):
    v = np.array([[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)], float)
    f = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3), (0, 4, 6),
         (0, 6, 2), (1, 3, 7), (1, 7, 5)]
    return v[np.array(f)]


def slope(angle_deg, half=60.0):
    t = math.tan(math.radians(angle_deg))
    a = [-half, -half, -half * t]
    b = [half, -half, half * t]
    c = [half, half, half * t]
    d = [-half, half, -half * t]
    return np.array([[a, b, c], [a, c, d]], float)


SHAPES = {"FLAT": tp.Shape(5.0, 0.0), "BALL": tp.Shape(5.0, 5.0), "BULL": tp.Shape(5.0, 1.5)}


def on_sphere(sh: tp.Shape, rs: float, d: float) -> float:
    """Tip height of a tool above the top of a sphere of radius rs, its axis ``d`` from the centre."""
    a = sh.R - sh.c                          # radius of the ring the corner's centre runs on
    if d <= a:
        return rs
    if sh.c <= 0:                            # flat: its rim's edge on the sphere
        return math.sqrt(max(rs * rs - (d - sh.R) ** 2, 0.0)) if d - sh.R < rs else -1e30
    return math.sqrt((rs + sh.c) ** 2 - (d - a) ** 2) - sh.c


@pytest.mark.parametrize("kind", ["FLAT", "BALL", "BULL"])
def test_drop_cutter_on_a_sphere(kind):
    sh = SHAPES[kind]
    rs = 20.0
    dc = tp.DropCutter(tp.Mesh(sphere(rs)), sh)
    d = np.array([0.0, 2.0, 3.4, 7.0, 12.0, 18.0, 21.0, 23.0])
    pts = np.stack([d * math.cos(0.3), d * math.sin(0.3)], axis=1)
    z = dc.z(pts)
    want = np.array([on_sphere(sh, rs, x) for x in d])
    ok = want > -1e29
    # the mesh lies inside the sphere: never higher than the true answer, and close to it
    assert np.all(z[ok] <= want[ok] + 1e-6), (z, want)
    assert np.all(want[ok] - z[ok] < 0.06), (z, want)


@pytest.mark.parametrize("kind", ["FLAT", "BALL", "BULL"])
@pytest.mark.parametrize("angle", [0.0, 20.0, 45.0, 70.0])
def test_drop_cutter_on_a_slope(kind, angle):
    sh = SHAPES[kind]
    t = math.tan(math.radians(angle))
    dc = tp.DropCutter(tp.Mesh(slope(angle)), sh)
    x = np.linspace(-20, 20, 9)
    z = dc.z(np.stack([x, np.full_like(x, 3.0)], axis=1))
    a = sh.R - sh.c
    want = (x + a) * t + sh.c / math.cos(math.radians(angle)) - sh.c
    assert np.allclose(z, want, atol=1e-6), (z, want)


@pytest.mark.parametrize("kind", ["FLAT", "BALL", "BULL"])
def test_drop_cutter_at_a_step(kind):
    """A block x -50..0 with its top at 10: beside it the tool goes down only where its end clears the edge."""
    sh = SHAPES[kind]
    dc = tp.DropCutter(tp.Mesh(box(-50, -50, -20, 0, 50, 10)), sh)
    x = np.array([-10.0, 0.0, 1.0, 2.5, 3.5, 4.0, 4.9, 5.1, 8.0])
    z = dc.z(np.stack([x, np.zeros_like(x)], axis=1))
    a = sh.R - sh.c
    want = []
    for v in x:
        if v <= a:
            want.append(10.0)
        elif v < sh.R:
            want.append(10.0 - sh.c + math.sqrt(sh.c ** 2 - (v - a) ** 2))
        else:
            want.append(tp.NEG)
    assert np.allclose(z, want, atol=1e-6), (z, want)


def test_leave_stock_is_a_bigger_tool():
    sh = SHAPES["FLAT"]
    m = tp.Mesh(slope(30.0))
    z0 = tp.DropCutter(m, sh).z([[0.0, 0.0]])[0]
    z1 = tp.DropCutter(m, sh, leave=0.3).z([[0.0, 0.0]])[0]
    # the tip lifts by more than 0.3 on a slope (0.3 measured square to the face)
    assert z1 - z0 > 0.3
    # along the slope's level line, 0.01 below the leave-stock height: clear of the part, 0.01 into the stock left
    path = [tp.Move(False, (0, -10, z1 - 0.01)), tp.Move(False, (0, 10, z1 - 0.01))]
    flat = tools.default("FLAT", 1)
    assert tp.gouge(path, slope(30.0), flat) == 0.0
    assert 0.0 < tp.gouge(path, slope(30.0), flat, leave=0.3) <= 0.01


def test_scallop_stepover():
    ball = tp.Shape(5.0, 5.0)
    w = tp.scallop_stepover(ball, 0.01, 1.0)
    assert w == pytest.approx(2 * math.sqrt(2 * 5 * 0.01 - 0.0001), rel=1e-9)
    bull = tp.Shape(5.0, 1.0)
    assert tp.scallop_stepover(bull, 0.01, 1.0) == pytest.approx(8.0 + 2 * math.sqrt(0.02 - 0.0001))
    assert tp.scallop_stepover(tp.Shape(5.0, 0.0), 0.01, 3.0) == 3.0


def test_tools_allowed():
    for k in ("FLAT", "BALL", "BULL", "FACE"):
        tp.shape_of(tools.default(k, 1))
    for k in ("DRILL", "VEE", "THREAD", "SLOT"):
        with pytest.raises(tp.ToolpathError):
            tp.shape_of(tools.default(k, 1))
    face = tools.default("FACE", 3)
    face.diameter, face.lead_angle = 0.05, 45.0
    assert tp.shape_of(face).R > 25.0               # a 45° face mill is wider above its tip


# ---------------------------------------------------------------------------
# the test model
# ---------------------------------------------------------------------------

def _specs():
    r = tools.default("FLAT", 1)
    r.diameter, r.flute_length, r.stick_out = 10 * MM, 30 * MM, 45 * MM
    f = tools.default("BALL", 2)
    f.diameter, f.flute_length, f.stick_out = 10 * MM, 25 * MM, 40 * MM
    return r, f


@pytest.fixture(scope="module")
def model():
    part, stock = toolpath_shapes.model()
    r, f = _specs()
    res = tp.run(part, stock, r, f, tp.Settings(detail="DRAFT"))
    return part, stock, r, f, res


def test_roughing_levels_and_leave_stock(model):
    part, _stock, r, _f, res = model
    rough = res.passes[0]
    lv = rough.levels
    assert lv == sorted(lv, reverse=True)
    assert max(a - b for a, b in zip(lv, lv[1:])) <= 3.0 + 1e-6
    leave = 0.3 + tp.ROUGH_MARGIN
    for face in (-5.0, -15.0, -23.0):                # boss top, base top, pocket floor: a level each
        assert any(abs(z - (face + leave)) < 1e-3 for z in lv), (face, lv)
    assert min(lv) == pytest.approx(-23.0 + leave, abs=1e-3)
    # never into the part + leave stock
    assert tp.gouge(rough.moves, part, r, step=0.2, leave=0.3) == 0.0


def test_roughing_ramps_into_material(model):
    """No straight plunge into material: a downward feed move steeper than the ramp only comes down through air
    (the last CLEAR + 0.2 mm above the material)."""
    rough = model[4].passes[0]
    prev = None
    ramps = 0
    for m in rough.moves:
        if prev is not None and not m.rapid and m.p[2] < prev[2] - 1e-6:
            run = math.hypot(m.p[0] - prev[0], m.p[1] - prev[1])
            drop = prev[2] - m.p[2]
            if run < 1e-9 or math.degrees(math.atan2(drop, run)) > tp.RAMP_DEG + 0.01:
                assert drop <= tp.CLEAR + 1e-6, (prev, m.p)
            else:
                ramps += 1
        prev = m.p
    assert ramps > 20


def test_finishing_never_in_the_part(model):
    part, _stock, _r, f, res = model
    worst = []
    depth = tp.gouge(res.passes[1].moves, part, f, step=0.1, worst=worst)
    assert depth <= 0.01, worst[:3]


def test_undercut_and_hole_left(model):
    part, _stock, _r, _f, res = model
    assert res.undercut["faces"] > 0 and res.undercut["area"] > 100
    assert "Undercut" in res.text
    # program coordinates: the work zero is the top centre of the stock (z = 70 in the model)
    cap_top = 64.0 - 70.0
    base_top = 55.0 - 70.0
    for p in res.passes:
        for m in p.moves:
            x, y, z = m.p
            if 17 < x < 39 and 14 < y < 30:              # over the mushroom's cap: never below its top
                assert z >= cap_top - 1e-6, m.p
            if math.hypot(x - 52, y - 30) < 5:           # over the through hole: never below the face round it
                assert z >= base_top - 1e-6, m.p


def test_program_reads_with_our_reader(model):
    res = model[4]
    text = res.text
    for need in ("G21 G90 G17 G54 G94", "T1 M6", "\nT2\n", "T2 M6", "M8", "M9", "M30", "S", "F"):
        assert need in text, need
    assert text.index("\nT2\n") < text.index("T2 M6")         # the next tool named early (double arm)
    prog = gcode.read(text)
    assert not prog.problems, [p.describe() for p in prog.problems]
    assert prog.ended
    assert prog.tool_numbers() == [1, 2]
    assert sorted(prog.tools) == [1, 2] and prog.tools[2].kind == "BALL"
    assert any(t == 2 for _k, t, _line in prog.t_events)
    # every move is where the passes say
    pts = [m.b for m in prog.moves if m.moving]
    ours = [mv.p for p in res.passes for mv in p.moves]
    assert len(pts) >= len(ours) - 4
    lo, hi = np.min(ours, axis=0), np.max(ours, axis=0)
    assert np.all(np.min(pts, axis=0) >= lo - 1e-3) and np.all(np.max(pts, axis=0) <= hi + 5.001)


def test_coolant_and_speeds():
    r, f = _specs()
    alu = tp.cutting(r, "ALU")
    steel = tp.cutting(r, "STEEL")
    assert alu.rpm > steel.rpm and alu.feed > steel.feed
    assert alu.rpm <= tp.MAX_RPM
    assert tp.cutting(r, "ALU", rpm=8000, feed=1234).rpm == 8000
    st = tp.Settings(coolant="AIR", air_on=101, air_off=102)
    assert tp.coolant_codes(st) == ("M101", "M102")
    assert tp.coolant_codes(tp.Settings(coolant="NONE")) == ("", "")


def test_part_outside_the_stock():
    with pytest.raises(tp.ToolpathError):
        tp.run(box(100, 100, 0, 110, 110, 10), box(0, 0, 0, 20, 20, 20), *_specs(), tp.Settings())
