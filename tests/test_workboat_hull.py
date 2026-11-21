"""Task 0234: the invented workboat hull of the sea, moving-part and thrusters test models (tools/workboat_hull.py).

What the sets and the app read from the hull: its lowest point is the flat bottom (the water level is measured from
it), the working deck is flat where the deck gear stands, the bow is narrower than the transom (the app's "Bow: from
the hull" then finds the stern at x = 0), and ``half_at`` is the solid's half breadth (the thrusters' tunnel lining
is sized by it)."""
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_sea as sea  # noqa: E402
import make_test_thrusters as thr  # noqa: E402
import workboat_hull as H  # noqa: E402
from make_test_paths import box, gap, solids, volume  # noqa: E402
from OCP.Bnd import Bnd_Box  # noqa: E402
from OCP.BRepAlgoAPI import BRepAlgoAPI_Common  # noqa: E402
from OCP.BRepBndLib import BRepBndLib  # noqa: E402

BIG = 1e6


def bounds(shape):
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape, b, False, False)
    lo, hi = b.CornerMin(), b.CornerMax()
    return lo.X(), lo.Y(), lo.Z(), hi.X(), hi.Y(), hi.Z()


def slab(shape, x0, x1, z0=-BIG, z1=BIG, y=BIG):
    """The part of ``shape`` between x0 and x1 (and z0, z1, |y| < y), or None when nothing is there."""
    got = BRepAlgoAPI_Common(shape, box(x0, -y, z0, x1, y, z1)).Shape()
    return got if volume(got) > 1.0 else None


def width(shape, x, z):
    """The hull's breadth at (x, z), measured on the solid (a thin slab)."""
    got = slab(shape, x - 1.0, x + 1.0, z - 1.0, z + 1.0)
    if got is None:
        return 0.0
    _x0, y0, _z0, _x1, y1, _z1 = bounds(got)
    return y1 - y0


HULLS = {"sea": lambda: sea.hull_numbers(12000.0), "moving": lambda: sea.hull_numbers(14000.0),
         "thrusters": thr.hull_numbers}


@pytest.fixture(scope="module", params=["sea", "thrusters"])
def hull(request):
    h = HULLS[request.param]()
    return h, h.solid()


@pytest.mark.parametrize("name", list(HULLS))
def test_the_app_finds_the_bow_at_plus_x(name):
    """``blender/surroundings.stern_side``: the stern is the waterline's end that is more than 1.15 x as wide within
    3 m of it. The waterline (model z 0: the sets' water level) of each hull: the bow's end clearly the narrower."""
    h = HULLS[name]()
    xs = [i * h.length / 2000 for i in range(2001)]
    on = [(x, 2 * h.half_at(x, 0.0)) for x in xs if h.half_at(x, 0.0) > 0.0]
    x0, x1 = on[0][0], on[-1][0]
    stern = max(w for x, w in on if x <= x0 + 3000.0)
    bow = max(w for x, w in on if x >= x1 - 3000.0)
    assert x0 == pytest.approx(0.0) and bow < 0.8 * stern, (name, bow, stern)


def test_one_solid_whose_lowest_point_is_the_flat_bottom(hull):
    h, s = hull
    assert solids(s) == 1
    x0, y0, z0, x1, y1, z1 = bounds(s)
    assert z0 == pytest.approx(h.bottom, abs=1.0) and z1 == pytest.approx(h.bow_top, abs=1.0)
    assert x0 == pytest.approx(0.0, abs=1.0) and x1 == pytest.approx(h.length, abs=1.0)
    assert y1 - y0 == pytest.approx(2 * h.half, abs=1.0)
    # the bottom is flat across the parallel body, inside the bilges
    flat = h.half - h.flare - h.bilge
    for x in (100.0, h.bow_start / 2, h.bow_start - 100.0):
        assert width(s, x, h.bottom + 2.0) == pytest.approx(2 * flat, abs=60.0)       # (the bilge's first step)


def test_half_at_is_the_solids_half_breadth(hull):
    h, s = hull
    for t in (0.0, 0.3, 0.6, 0.9):
        x = h.bow_start + t * (h.length - h.bow_start) if t else h.bow_start / 2
        for z in (h.bottom + 0.5 * (h.bow_top - h.bottom), h.bow_top - 50.0):
            want = h.half_at(x, z)
            got = width(s, x, z) / 2
            assert got == pytest.approx(want, rel=0.04, abs=40.0), (x, z, got, want)    # (a smooth loft between
    assert h.half_at(h.length / 2, h.bottom - 10.0) == 0.0                                 # the stations)


def test_the_bow_narrows_and_its_forefoot_rises(hull):
    h, s = hull
    near = h.length - 1000.0
    assert width(s, near, h.bow_top - 50.0) < 0.75 * width(s, 1000.0, h.top - 50.0)
    # the app reads the waterline's width within 3 m of each end: the stern (x 0) clearly the wider one
    z = 0.0
    assert width(s, h.length - 1500.0, z) < 0.6 * width(s, 1500.0, z)
    keel = [bounds(slab(s, x - 5.0, x + 5.0))[2] for x in (h.bow_start + 100.0, (h.bow_start + h.length) / 2,
                                                            h.length - 300.0)]
    assert keel == sorted(keel) and keel[-1] > h.bottom + 0.6 * h.stem_rise * (h.bow_top - h.bottom)


def test_the_working_deck_is_flat_and_the_forecastle_higher():
    deck = sea.deck_shape(12000.0, ())
    top = sea.DECK_TOP
    for x in (500.0, 6000.0, 11500.0):                # flat between the bulwarks
        got = slab(deck, x - 5.0, x + 5.0, top - 50.0, top + 50.0, y=2000.0)
        assert got is not None and bounds(got)[5] == pytest.approx(top, abs=1e-3)
    fc = slab(deck, 12100.0, 12200.0)
    assert bounds(fc)[5] == pytest.approx(top + sea.BULWARK_H + 40.0, abs=1.0)
    house = slab(deck, 12000.0 + sea.HOUSE[0] + 100.0, 12000.0 + sea.HOUSE[1] - 100.0)
    assert bounds(house)[5] > top + sea.BULWARK_H + sea.HOUSE[3]               # (its roof)


def test_the_thrusters_sit_on_the_hull_and_the_tunnel_lining_inside_it():
    root = thr.model()
    thr.check(root)
    from make_test_paths import placed
    by = {}
    for name, _path, shape in placed(root):
        by.setdefault(name, []).append(shape)
    hull = by["HULL"][0]
    for housing in by["THRUSTER HOUSING"]:
        assert gap(housing, hull) < 1e-3, "an azimuth's housing hangs under the flat bottom"
        assert volume(BRepAlgoAPI_Common(housing, hull).Shape()) < 1.0
    lining = by["TUNNEL LINING"][0]
    assert volume(BRepAlgoAPI_Common(lining, hull).Shape()) < 1.0, "the lining cuts into the hull"
    _x0, y0, _z0, _x1, y1, _z1 = bounds(lining)
    assert 2000.0 < y1 < thr.hull_numbers().half_at(thr.TEST["bow_x"], thr.TEST["bow_z"])
    assert y0 == pytest.approx(-y1, abs=1.0)
    for prop in by["PROPELLER"]:
        assert gap(prop, hull) > 50.0
    assert gap(by["WHEELHOUSE"][0], hull) < 1e-3 and volume(BRepAlgoAPI_Common(by["WHEELHOUSE"][0], hull).Shape()) < 1.0
    assert math.isclose(thr.BOW_START, 33500.0) and thr.TEST["bow_x"] + thr.TEST["tunnel_r"] < thr.BOW_START
