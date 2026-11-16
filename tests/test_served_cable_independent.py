"""Independent attack on the served cable look (task 0158), written from the spec by a tester who did not write it."""

import math
import sys
from types import SimpleNamespace

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")

from fresing_render.blender import cable_looks as CL  # noqa: E402
from fresing_render.blender import paths  # noqa: E402
from fresing_render.core import ral  # noqa: E402

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from test_cable_looks import H, PI, W, Tube, fresh, render  # noqa: E402

LOOK = [1.25, 0.0, 0.035, 3.0]
PAIR = [2.0, 0.03, 0.3, 0.0]


@pytest.fixture()
def scene():
    return fresh()


# ---- pure formula ------------------------------------------------------------------------------------------------

def test_bands_are_periodic_far_out_and_for_negative_s():
    rng = np.random.default_rng(1)
    s = rng.uniform(-50, 50, 4000)
    look = [0.1, 0, 0.012, 3.0]
    base = CL.bands(s, 0.0, look, PAIR)
    for k in (-3, 7, 1000, -100000):
        shifted = CL.bands(s + k * 0.1, 0.0, look, PAIR)
        assert (shifted != base).mean() < 2e-3, k
    # negative paid-out length moves the pattern the other way, by exactly that length
    assert (CL.bands(s - 3.7, -3.7, look, PAIR) != base).mean() < 2e-3


def test_band_width_gap_and_distance_extremes():
    s = np.linspace(0, 5, 1_000_001) + 1.234567e-7
    full = CL.bands(s, 0.0, [0.05, 0, 0.05, 3.0], PAIR)               # width == distance: paint everywhere
    assert full.min() == 1.0
    wide = CL.served_props(0.2, 0.05, 0.5)[CL.LOOK]                    # width > distance is clamped
    assert wide[2] == pytest.approx(0.05) and CL.bands(s, 0.0, wide, PAIR).min() == 1.0
    none = CL.bands(s, 0.0, [0.5, 0, 0.0, 3.0], [1.0, 0.0, 0.3, 0.0])  # width 0: no paint
    assert none.max() == 0.0
    # gap 0: the pair is one band of 2 w
    touch = CL.bands(s, 0.0, [0.5, 0, 0.04, 3.0], [2.0, 0.0, 0.3, 0.0])
    assert abs(touch.mean() - 0.08 / 0.5) < 1e-3
    # a pair that is longer than the distance wraps into the next period and overlaps the first band
    over = CL.bands(s, 0.0, [0.05, 0, 0.03, 3.0], [2.0, 0.02, 0.3, 0.0])
    assert abs(over.mean() - 0.6) < 2e-3


def test_first_band_includes_its_left_edge():
    """The docstring says the first band covers [0, w): the point x = 0 itself is paint."""
    assert CL.bands(0.0, 0.0, LOOK, PAIR) == 1.0
    assert CL.bands(2.5, 0.0, LOOK, PAIR) == 1.0
    assert CL.bands(0.0, 0.0, [0.05, 0, 0.05, 3.0], PAIR) == 1.0          # a band as wide as the distance: no holes


def test_big_lengths_keep_the_edges_in_float64():
    for paid in (1e4, -1e4, 123456.789):
        s = paid + np.array([0.0005, 0.0175, 0.0345, 0.0355, 0.6])
        got = CL.bands(s, paid, LOOK, [1.0, 0.03, 0.3, 0.0])
        assert list(got) == [1.0, 1.0, 1.0, 0.0, 0.0], paid


def test_served_fallbacks_for_missing_zero_and_short_properties():
    d = CL.defaults("SERVED")
    lib = CL._served()
    assert lib["distance"] == d["pitch"] and lib["count"] == 2 and lib["gap"] == d["gap"]
    assert lib["starts"] == CL.yarn_starts(d["diameter"], d["yarn_pitch"], d["lay_angle"])
    assert CL._served([0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]) == lib
    assert CL._served([1.0, 0.0], [0.003, 5, 0.1], [1.0, 0.1]) == lib                      # too short: ignored
    v = CL._served([2.0, 0, 5.0, 3], [0.004, 4.6, 0.0, 7.0], [1.4, -3.0, 5.0, 0])
    assert v["width"] == 2.0 and v["starts"] == 5 and v["radius"] == lib["radius"] and v["wear"] == 1.0
    assert v["count"] == 1 and v["gap"] == 0.0 and v["band_wear"] == 1.0
    assert CL._served(band=[1.5, 0.01, 0.2, 0])["count"] == 2
    assert CL._served(yarn=[0.004, -4.5, 0.1, 0.2])["starts"] == -4                         # floor(x + 0.5)


def test_served_props_odd_arguments():
    p = CL.served_props(-1.0, -2.0, -1.0, 0, -0.5, -1.0, None, None, None)
    d = CL.defaults("SERVED")
    assert p[CL.LOOK] == [d["pitch"], 0.0, 0.0, 3.0]
    assert p[CL.BAND][0] == 1.0 and p[CL.BAND][1] == 0.0
    assert p[CL.YARN][0] == d["yarn_pitch"] and p[CL.YARN][2] == pytest.approx(0.5 * d["diameter"])
    assert CL.served_props(0.2, count=7)[CL.BAND][0] == 2.0
    lin = CL.served_props(0.2)[CL.BAND_RGB]
    assert lin == pytest.approx([ral.srgb_to_linear(c) for c in d["band"]])


def test_lay_angle_edges():
    # a lay angle of 0 is a strand along the cable: as many strands as we draw, like the power cable's stripes
    assert CL.stripes(0.3, 0.0025, 0.0) == CL.STARTS_MAX
    assert CL.yarn_starts(0.3, 0.0025, 0.0) == CL.YARN_STARTS_MAX, "lay angle 0 gives rings instead of strands"
    assert CL.yarn_starts(0.3, 0.0025, 1e-12) == CL.YARN_STARTS_MAX
    assert CL.yarn_starts(0.3, 0.0025, -1e-12) == -CL.YARN_STARTS_MAX
    assert CL.yarn_starts(0.3, 0.0025, PI / 2) == 0
    assert CL.yarn_starts(0.3, 0.0025, -math.radians(82)) == -CL.yarn_starts(0.3, 0.0025, math.radians(82))
    assert CL.yarn_starts(0.3, 0.0025, math.radians(82)) == math.floor(PI * 0.3 / (0.0025 * math.tan(math.radians(82))) + .5)


def test_yarn_phase_is_continuous_once_round():
    for n in (-37, -1, 0, 1, 5, 4096):
        y = [0.0025, float(n), 0.15, 0.3]
        for s0 in (0.0, 3.3, 9999.7):
            d = CL.yarn_phase(s0, PI, 0.0, y) - CL.yarn_phase(s0, -PI, 0.0, y)
            assert d == pytest.approx(n, abs=1e-6), (n, s0)
    # rings: the height does not depend on the angle
    h = CL.yarn(3.3, np.linspace(-PI, PI, 50), 0.0, [0.0025, 0.0, 0.15, 0.3])
    assert np.ptp(h) < 1e-12
    # a different hand mirrors the phase in the angle
    a = CL.yarn_phase(5.0, 0.7, 0.0, [0.003, 6.0, 0.1, 0.0]) - 5.0 / 0.003
    b = CL.yarn_phase(5.0, 0.7, 0.0, [0.003, -6.0, 0.1, 0.0]) - 5.0 / 0.003
    assert a == pytest.approx(-b)


def test_paths_look_props_for_a_cable_item():
    item = SimpleNamespace(look="SERVED", diameter=0.12, pitch=1.25, band_width=0.035, band_count="PAIR",
                           band_gap=0.03, yarn_pitch=0.0025, yarn_angle=math.radians(82), wear=0.35,
                           band_wear=0.35, yarn_color=(0.0045, 0.0045, 0.0049), band_color=(0.879, 0.546, 0.0),
                           band_style="SPIRAL", band_hand="RIGHT")
    p = paths.look_props(item)
    assert set(p) == set(CL.PROPS) and paths.look_of(item) == p[CL.LOOK]
    assert p[CL.YARN][1] < 0 and p[CL.BAND][0] == 2.0
    assert p[CL.YARN_RGB] == pytest.approx([0.0045, 0.0045, 0.0049])
    assert p[CL.BAND][3] == -1.0                                   # task 0164: right-hand spiral
    item.band_hand = "LEFT"
    assert paths.look_props(item)[CL.BAND][3] == 1.0
    item.band_style = "RINGS"
    assert paths.look_props(item)[CL.BAND][3] == 0.0
    item.band_count = "SINGLE"
    assert paths.look_props(item)[CL.BAND][0] == 1.0
    item.look = "POWER"
    item.stripe = 0.3
    item.angle = math.radians(45)
    assert set(paths.look_props(item)) == {CL.LOOK} and paths.look_props(item)[CL.LOOK][3] == 1.0
    item.look = "PLAIN"
    assert paths.look_props(item) == {} and paths.look_of(item) == []
    assert paths._usual_pitch("SERVED", 0.01) == paths._usual_pitch("SERVED", 5.0) == CL.defaults("SERVED")["pitch"]


# ---- the nodes ---------------------------------------------------------------------------------------------------

def served_tube(pay=0.0, **kw):
    props = CL.served_props(0.12, **kw)
    t = Tube("cable_served", props[CL.LOOK], pay=pay)
    for k, v in props.items():
        t.ob[k] = v
    return t, props


@pytest.mark.parametrize("angle,pay", [(-70.0, -7.3), (90.0, 123.4), (70.0, 0.0)])
def test_nodes_equal_the_formula_for_hands_rings_and_negative_pay(scene, tmp_path, angle, pay):
    t, props = served_tube(pay=pay, distance=0.25, width=0.04, gap=0.025, yarn_pitch=0.03,
                           lay_angle=math.radians(angle))
    assert (props[CL.YARN][1] < 0) == (angle < 0) and (props[CL.YARN][1] == 0) == (angle == 90.0)
    for view in (PI / 2, PI):
        t.camera(view)
        s, phi = t.seen()
        t.probe(CL.NODE_PATTERN)
        got = render(tmp_path / "b.exr", samples=16)[:, :, 0]
        want = CL.bands(s, pay, props[CL.LOOK], props[CL.BAND], phi=phi).mean(axis=2)
        clear = (want == 0.0) | (want == 1.0)
        assert np.abs(got - want)[clear].max() < 0.06, (angle, pay, view)
        t.probe(CL.NODE_YARN)
        got = render(tmp_path / "y.exr", samples=16)[:, :, 0]
        want = CL.yarn(s, phi, pay, props[CL.YARN]).mean(axis=2)
        assert np.abs(got - want).mean() < 0.03, (angle, pay, view, np.abs(got - want).mean())


def _strand_noise_rows(t, tmp_path, view):
    nt = t.mat.node_tree
    wn = [n for n in nt.nodes if n.bl_idname == "ShaderNodeTexWhiteNoise"][0]       # the strand's shade
    wn.name = "strandnoise"
    t.camera(view)
    t.probe("strandnoise")
    px = render(tmp_path / "n.exr", samples=1)[:, :, 0]
    a, b = px[H // 2 - 2], px[H // 2 + 1]
    return float((np.abs(a - b) > 0.02).mean())


def test_strand_identity_has_no_seam_where_the_angle_jumps(scene, tmp_path):
    t, _ = served_tube(pay=0.0, distance=0.25, yarn_pitch=0.03, lay_angle=math.radians(70))
    smooth = _strand_noise_rows(t, tmp_path, PI / 2)
    seam = _strand_noise_rows(t, tmp_path, PI)
    assert seam < smooth + 0.1, (seam, smooth)


def test_missing_colour_properties_give_the_librarys_colours(scene, tmp_path):
    """Yarn and band settings given, their colours not (an older file / a hand-made part): library colours."""
    t, props = served_tube(distance=0.25, width=0.04, gap=0.025)
    del t.ob[CL.BAND_RGB]
    del t.ob[CL.YARN_RGB]
    t.camera(PI / 2)
    s, phi = t.seen()
    px = render(tmp_path / "c.exr", samples=16)
    want = CL.bands(s, 0.0, props[CL.LOOK], props[CL.BAND], phi=phi).mean(axis=2)
    mid = slice(H // 2 - 6, H // 2 + 6)
    q = (px[:, :, 0] - px[:, :, 2])[mid]
    assert q[want[mid] == 1.0].mean() > 0.2, q[want[mid] == 1.0].mean()


def test_no_attribute_shows_the_plain_base(scene, tmp_path):
    t = Tube("cable_served", [1.25, 0, 0.035, 3.0], attr=False)
    t.camera(PI / 2)
    t.probe(CL.NODE_PATTERN)
    assert render(tmp_path / "p.exr", samples=4)[:, :, 0].max() < 0.01
    t.probe(CL.NODE_YARN)
    px = render(tmp_path / "p.exr", samples=4)
    assert px.max() >= 0.0


def test_paint_edges_with_pay_at_a_period_boundary(scene, tmp_path):
    """The paid-out length puts a band edge exactly on a pixel border and on a period boundary: no hole, no double."""
    t, props = served_tube(pay=0.25, distance=0.25, width=0.04, gap=0.025)
    t.camera(PI / 2)
    s, phi = t.seen()
    t.probe(CL.NODE_PATTERN)
    got = render(tmp_path / "e.exr", samples=16)[:, :, 0]
    want = CL.bands(s, 0.25, props[CL.LOOK], props[CL.BAND], phi=phi).mean(axis=2)
    assert np.abs(got - want).mean() < 0.02


# ---- the page's numbers --------------------------------------------------------------------------------------------

def test_look_for_page_equals_what_blender_uses(scene):
    from fresing_render.blender import web3d_drawn
    t, props = served_tube(distance=0.3, width=0.04, gap=0.02, yarn_pitch=0.004, lay_angle=math.radians(-75),
                           wear=0.6, band_wear=0.1, yarn_rgb=(0.2, 0.1, 0.05), band_rgb=(0.9, 0.8, 0.1))
    got = web3d_drawn.look_of(t.ob)
    v = CL._served(props[CL.LOOK], props[CL.YARN], props[CL.BAND])
    assert got["kind"] == "SERVED" and got["pitch"] == v["distance"] and got["width"] == v["width"]
    assert got["count"] == v["count"] and got["gap"] == v["gap"] and got["yarn_pitch"] == v["yarn_pitch"]
    assert got["yarn_starts"] == v["starts"] < 0 and got["radius"] == v["radius"]
    assert got["wear"] == v["wear"] and got["band_wear"] == v["band_wear"]
    assert got["yarn"] == pytest.approx([0.2, 0.1, 0.05]) and got["band"] == pytest.approx([0.9, 0.8, 0.1])
    # a part given the material by hand, no properties at all: the library's numbers, the same as the nodes use
    bare = Tube("cable_served", None, pay=None, name="bare")
    lib = web3d_drawn.look_of(bare.ob)
    d = CL.defaults("SERVED")
    w = CL._served()
    assert lib["pitch"] == d["pitch"] and lib["yarn_starts"] == w["starts"] and lib["count"] == 2
    assert lib["band"] == pytest.approx([ral.srgb_to_linear(c) for c in d["band"]], abs=1e-5)
    assert lib["yarn"] == pytest.approx([ral.srgb_to_linear(c) for c in d["yarn"]], abs=1e-5)
    # yarn / band given without colours: the library's colours (as the page and the nodes should agree)
    for k in (CL.YARN_RGB, CL.BAND_RGB):
        del t.ob[k]
    nocol = web3d_drawn.look_of(t.ob)
    assert nocol["band"] == pytest.approx([ral.srgb_to_linear(c) for c in d["band"]], abs=1e-5)
