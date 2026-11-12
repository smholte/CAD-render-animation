"""Task 0058: drag chains without Blender (core/flex_chain.py), against geometry worked out independently.

The chain of the tests: pitch 40 mm, bend radius 80 mm (as the links of the test gantry), in metres. Chain
coordinates: pin 0 at the origin, u along the fixed run, v towards the moving run, w across.

What is checked: every pin exactly one pitch from the next, the ends exact, the bend's pins on the circle, the
bend at half the moving end's speed, no pops over a whole stroke, GLIDE, out of reach without NaN, the links'
frames, the fit from CAD links (round trip through shuffled, moved, two-kind chains and back for another pose),
a chain drawn as one solid, and the speed.
"""

import math
import time

import numpy as np
import pytest

from fresing_render.core import flex_chain as fc

P, R, N = 0.04, 0.08, 60
SPEC = fc.ChainSpec(P, N, R)
LONG = fc.ChainSpec(P, 120, R, "GLIDE")           # a long chain whose upper run lies on the lower one
REST = 0.03                                       # ... 30 mm above it (pin to pin)


def chords(pins):
    return np.linalg.norm(np.diff(pins, axis=-2), axis=-1)


def stroke(lo, hi, steps, v=2 * R, w=0.0):
    u = np.linspace(lo, hi, steps)
    return np.stack([u, np.full(steps, v), np.full(steps, w)], axis=1)


def off_path(pins, bend_u, moving, radius=R):
    """How far each pin (in the plane) is from the STRAIGHT path, worked out another way: the line v = 0 up to
    the bend, the circle, or a line through the moving end that touches the circle."""
    u, v = pins[:, 0], pins[:, 1]
    on_run = np.where(u <= bend_u + 1e-12, np.abs(v), np.inf)
    on_circle = np.abs(np.hypot(u - bend_u, v - radius) - radius)
    du, dv = moving[0] - u, moving[1] - v
    far = np.hypot(du, dv)
    safe = np.where(far > 1e-12, far, 1.0)
    # the distance from the circle's centre to the line through this pin and the moving end
    on_tangent = np.where(far > 1e-12, np.abs(np.abs(du * (radius - v) - dv * (bend_u - u)) / safe - radius), 0.0)
    return np.minimum(np.minimum(on_run, on_circle), on_tangent)


# ---------------------------------------------------------------------------
# the shape
# ---------------------------------------------------------------------------

def test_two_runs_and_half_a_circle():
    moving = np.array([0.5, 2 * R, 0.0])
    chain = fc.chain_pins(SPEC, moving)
    pins, c = chain.pins[0], float(chain.bend_u[0])
    assert pins.shape == (N + 1, 3) and not chain.short[0]
    assert np.array_equal(pins[0], np.zeros(3)) and np.array_equal(pins[-1], moving)
    assert np.abs(chords(pins) - P).max() < 1e-12
    assert np.abs(pins[:, 2]).max() == 0.0
    # where the bend is: a chain without thickness would have it at (length - half a circle + moving end) / 2
    assert abs(c - 0.5 * (N * P - math.pi * R + 0.5)) < P / 10
    u, v = pins[:, 0], pins[:, 1]
    fixed = np.arange(N + 1) <= math.floor(c / P)
    assert np.abs(v[fixed]).max() == 0.0 and np.allclose(u[fixed], np.arange(fixed.sum()) * P, atol=1e-12)
    bend = u > c + 1e-9                                 # beyond the circle's centre there is only the circle
    assert bend.sum() >= math.floor(math.pi * R / P) - 1
    assert np.abs(np.hypot(u[bend] - c, v[bend] - R) - R).max() < 1e-12
    upper = ~fixed & ~bend
    assert upper.sum() > 10 and np.abs(v[upper] - 2 * R).max() < 1e-12
    assert np.all(np.diff(u[upper]) < 0)                # the upper run comes back
    # on the bend every link turns by the same angle
    turn = 2 * math.asin(P / (2 * R))
    angle = np.arctan2(u[bend] - c, R - v[bend])
    assert np.allclose(np.diff(angle), turn, atol=1e-12)


def test_every_pin_one_pitch_from_the_next_whatever_the_chain():
    rng = np.random.default_rng(58)
    worst = 0.0
    for trial in range(60):
        pitch = rng.uniform(0.01, 0.1)
        radius = pitch * rng.uniform(1.0, 6.0)
        links = int(rng.integers(8, 200))
        spec = fc.ChainSpec(pitch, links, radius, "GLIDE" if trial % 2 else "STRAIGHT",
                            glide_angle=math.radians(rng.uniform(5, 30)))
        b = 200
        moving = np.stack([rng.uniform(-1.2, 1.2, b) * links * pitch,
                           2 * radius * (rng.uniform(0.1, 1.3, b) if trial % 3 else np.ones(b)),
                           np.zeros(b)], axis=1)
        chain = fc.chain_pins(spec, moving)
        assert np.isfinite(chain.pins).all() and np.isfinite(chain.bend_u).all()
        assert np.abs(chain.pins[:, 0]).max() == 0.0
        worst = max(worst, np.abs(chords(chain.pins) - pitch).max() / pitch)
        ok = ~chain.short
        assert 0 < ok.sum() < b                         # some in reach, some not
        assert np.array_equal(chain.pins[ok, -1], moving[ok])
        assert np.all((chain.bend_u >= 0.0) & (chain.bend_u <= links * pitch))
        if spec.mode == "STRAIGHT":
            for i in np.nonzero(ok)[0][:40]:
                assert off_path(chain.pins[i], chain.bend_u[i], moving[i], radius).max() < 1e-9   # measured 1.4e-12
    assert worst < 1e-9                                 # asked: 1e-9; measured 2e-12 x pitch


def test_moving_end_a_little_off_is_met_exactly():
    """Higher, lower, sideways: the run after the bend is the tangent to it, w rises evenly after the bend."""
    for v, w in ((2 * R + 0.01, 0.0), (2 * R - 0.02, 0.0), (2 * R, 0.012), (2 * R - 0.005, -P)):
        moving = np.array([0.4, v, w])
        chain = fc.chain_pins(SPEC, moving)
        pins, c = chain.pins[0], float(chain.bend_u[0])
        assert not chain.short[0] and np.array_equal(pins[-1], moving)
        assert np.abs(chords(pins) - P).max() < 1e-6 * P        # asked: 1e-6 pitch with |w| <= pitch
        assert np.abs(chords(pins) - P).max() < 1e-12           # ... it is exact
        assert off_path(pins, c, moving).max() < 1e-9
        n0 = math.floor(c / P)
        assert np.abs(pins[:n0 + 1, 2]).max() == 0.0            # the fixed run stays in the plane
        rise = np.diff(pins[n0 + 1:, 2])
        assert np.allclose(rise, w / (N - c / P), atol=1e-12)   # evenly from where the bend starts
        if w:
            assert np.all(np.diff(np.abs(pins[n0:, 2])) > 0)
    # sideways further than the links can go: out of reach, still one pitch apart
    chain = fc.chain_pins(fc.ChainSpec(P, 6, R), (0.0, 2 * R, 5 * P))
    assert chain.short[0] and np.abs(chords(chain.pins) - P).max() < 1e-12


def test_bend_moves_at_half_the_speed():
    moving = stroke(0.0, 1.2, 2001)
    chain = fc.chain_pins(SPEC, moving)
    assert not chain.short.any()
    c = chain.bend_u
    off = np.abs((c - c[0]) - 0.5 * (moving[:, 0] - moving[0, 0])).max()
    assert off < P / 10                                 # asked: 4 mm
    assert off < 5e-5                                   # measured: 0.008 mm
    assert np.all(np.diff(c) > 0)
    assert np.allclose(chords(chain.pins).sum(axis=1), N * P, atol=1e-11)      # the chain never changes length
    # the upper run moves with the moving end, the fixed run does not move at all
    assert np.abs(chain.pins[:, :10, :] - chain.pins[0, :10, :]).max() == 0.0
    assert np.allclose(chain.pins[:, -5:, 0] - moving[:, :1], chain.pins[0, -5:, 0] - moving[0, 0], atol=1e-11)


@pytest.mark.parametrize("spec, v, w, lo, hi", [
    (SPEC, 2 * R, 0.0, -0.6, 1.6),
    (SPEC, 2 * R - 0.03, 0.0, -0.6, 1.6),
    (SPEC, 2 * R, 0.03, -0.6, 1.6),
    (LONG, REST, 0.0, -1.0, 3.2),                       # from "no room to come down" to a long run lying flat
    (fc.ChainSpec(P, 120, R, "GLIDE", rest_v=0.05), REST, 0.0, -1.0, 3.2),
    (fc.ChainSpec(0.05, 40, 0.06), 0.12, 0.0, -0.4, 1.4),       # a tight bend: 2.4 links round half a turn
])
def test_no_pops_over_a_whole_stroke(spec, v, w, lo, hi):
    moving = stroke(lo, hi, 2001, v, w)
    chain = fc.chain_pins(spec, moving)
    assert not chain.short.any()
    step = (hi - lo) / 2000
    jump = np.linalg.norm(np.diff(chain.pins, axis=0), axis=2).max()
    assert jump < 1.1 * step                            # no pin moves faster than the end; measured 1.001 - 1.019
    assert np.abs(chords(chain.pins) - spec.pitch).max() < 1e-11


def test_a_tiny_move_of_the_end_is_a_tiny_move_of_every_pin():
    rng = np.random.default_rng(7)
    for spec, v in ((SPEC, 2 * R), (LONG, REST), (SPEC, 2 * R - 0.04)):
        length = spec.links * spec.pitch
        moving = np.stack([rng.uniform(-0.25, 0.65, 300) * length, np.full(300, v),
                           rng.uniform(-0.01, 0.01, 300)], axis=1)
        nudge = rng.normal(size=(300, 3))
        nudge *= 1e-6 / np.linalg.norm(nudge, axis=1, keepdims=True)
        a, b = fc.chain_pins(spec, moving), fc.chain_pins(spec, moving + nudge)
        assert not (a.short | b.short).any()
        assert np.linalg.norm(a.pins - b.pins, axis=2).max() < 3e-6      # asked: 1e-4; measured 1.01e-6


def test_glide_comes_down_and_lies_on_the_lower_run():
    moving = np.array([0.3, REST, 0.0])
    chain = fc.chain_pins(LONG, moving)
    pins, c = chain.pins[0], float(chain.bend_u[0])
    assert not chain.short[0] and np.array_equal(pins[-1], moving)
    assert np.abs(chords(pins) - P).max() < 1e-12
    a = LONG.glide_angle
    u, v = pins[:, 0], pins[:, 1]
    leave = np.array([c - R * math.sin(a), R * (1 + math.cos(a))])       # where the slope leaves the circle
    foot_u = leave[0] - (leave[1] - REST) / math.tan(a)
    assert foot_u - 0.3 > 20 * P                        # a long flat run in this pose
    number = np.arange(len(pins))
    after = number > number[np.argmax(u)]               # past the bend's far side
    flat = after & (u < foot_u)
    assert flat.sum() >= 20 and np.abs(v[flat] - REST).max() < 1e-12
    slope = after & (u > foot_u) & (u < leave[0])
    assert slope.sum() >= 10
    line = (v[slope] - leave[1]) * math.cos(a) - (u[slope] - leave[0]) * math.sin(a)
    assert np.abs(line).max() < 1e-12                   # on the line that comes down at 12 degrees
    bend = ~flat & ~slope & (number > math.floor(c / P))
    assert np.abs(np.hypot(u[bend] - c, v[bend] - R) - R).max() < 1e-12
    assert v[bend].max() > 2 * R - 0.01 and np.all(v[:math.floor(c / P) + 1] == 0.0)
    # with the upper run 30 mm above the lower one the two never cross
    assert np.all(v[after] >= REST - 1e-12)


def test_glide_without_room_is_the_straight_tangent():
    short_chain = fc.ChainSpec(P, 37, R, "GLIDE")
    moving = stroke(0.25, 0.6, 30, REST)
    glide = fc.chain_pins(short_chain, moving)
    straight = fc.chain_pins(fc.ChainSpec(P, 37, R), moving)
    assert not glide.short.any()
    assert np.abs(glide.pins - straight.pins).max() < 1e-12
    # a rest height at or under the moving end's changes nothing; a higher one is where the run comes down to
    low = fc.chain_pins(fc.ChainSpec(P, 120, R, "GLIDE", rest_v=0.01), (0.3, REST, 0.0))
    assert np.abs(low.pins - fc.chain_pins(LONG, (0.3, REST, 0.0)).pins).max() == 0.0
    high = fc.chain_pins(fc.ChainSpec(P, 120, R, "GLIDE", rest_v=0.06), (0.3, REST, 0.0))
    assert not high.short[0] and np.abs(chords(high.pins) - P).max() < 1e-12
    assert np.array_equal(high.pins[0, -1], [0.3, REST, 0.0])
    after = high.pins[0, int(np.argmax(high.pins[0, :, 0])):, 1]         # from the bend's far side on
    assert after.min() >= REST - 1e-12 and np.all(np.diff(after[8:]) < 0)   # down the slope, then straight to the end
    foot = int(np.argmax(np.abs(np.diff(after[8:], 2)))) + 9             # the pin where the slope ends
    assert abs(after[foot] - 0.06) < 0.005


def test_out_of_reach_is_said_and_never_nan():
    length = N * P
    # too far ahead: the chain lies pulled straight towards the end
    ahead = np.array([length + 0.3, 2 * R, 0.0])
    chain = fc.chain_pins(SPEC, ahead)
    assert chain.short[0] and np.isfinite(chain.pins).all() and chain.bend_u[0] < 1e-9
    assert np.abs(chords(chain.pins) - P).max() < 1e-12 and np.array_equal(chain.pins[0, 0], np.zeros(3))
    miss = np.linalg.norm(chain.pins[0, -1] - ahead)
    assert miss < np.linalg.norm(ahead) - length + 0.02         # as near as a straight chain gets, within 20 mm
    # too far back: there is no fixed run left, the bend starts at pin 0
    back = np.array([-length, 2 * R, 0.0])
    chain = fc.chain_pins(SPEC, back)
    assert chain.short[0] and chain.bend_u[0] == 0.0 and np.isfinite(chain.pins).all()
    assert np.abs(chords(chain.pins) - P).max() < 1e-12
    assert np.abs(chain.pins[0, -1, 1] - 2 * R) < 1e-9 and chain.pins[0, -1, 0] < -1.0
    # the limits themselves: a chain without thickness reaches from -(length - half a circle) to almost its length
    limits = stroke(-(length - math.pi * R) + 0.01, math.hypot(length, 0.0) - 0.02, 400)
    assert not fc.chain_pins(SPEC, limits).short.any()
    beyond = np.vstack([stroke(-length - 1.0, -(length - math.pi * R) - 0.01, 50), stroke(length + 0.01, 9.0, 50)])
    assert fc.chain_pins(SPEC, beyond).short.all()
    # where no path leads: under the bend, below the fixed run, not a number
    odd = np.array([[1.0, 0.02, 0.0], [1.05, 0.05, 0.0], [2.0, -0.05, 0.0], [math.nan, 0.16, 0.0],
                    [0.3, math.inf, 0.0], [0.0, 0.0, 0.0], [1.2, R, 0.0]])
    chain = fc.chain_pins(SPEC, odd)
    assert np.isfinite(chain.pins).all() and np.isfinite(chain.bend_u).all()
    assert np.abs(chords(chain.pins) - P).max() < 1e-9
    assert chain.short[[3, 4]].all()
    for i in np.nonzero(~chain.short)[0]:
        assert np.array_equal(chain.pins[i, -1], odd[i])
    # rows in reach are not disturbed by rows out of reach
    mixed = np.vstack([ahead, [0.5, 2 * R, 0.0], back])
    assert np.abs(fc.chain_pins(SPEC, mixed).pins[1] - fc.chain_pins(SPEC, (0.5, 2 * R, 0.0)).pins[0]).max() < 1e-12


def test_pure_function_and_batch_equals_one_by_one():
    rng = np.random.default_rng(3)
    moving = np.stack([rng.uniform(-0.5, 2.0, 80), rng.uniform(0.1, 0.2, 80), rng.uniform(-0.02, 0.02, 80)], axis=1)
    for spec in (SPEC, fc.ChainSpec(P, N, R, "GLIDE")):
        both = fc.chain_pins(spec, moving)
        again = fc.chain_pins(spec, moving[::-1])
        assert np.array_equal(both.pins, fc.chain_pins(spec, moving).pins)
        assert np.abs(both.pins - again.pins[::-1]).max() < 1e-12
        for i in range(0, 80, 7):
            one = fc.chain_pins(spec, moving[i])
            assert one.pins.shape == (1, N + 1, 3) and one.short[0] == both.short[i]
            assert np.abs(one.pins[0] - both.pins[i]).max() < 1e-12
        # frames in the chain's plane next to frames that go sideways
        level = moving.copy()
        level[::2, 2] = 0.0
        mixed = fc.chain_pins(spec, level)
        for i in range(0, 80, 6):
            assert np.abs(fc.chain_pins(spec, level[i]).pins[0] - mixed.pins[i]).max() < 1e-12


def test_bad_chain_is_refused_and_a_too_small_radius_is_widened():
    for bad in (fc.ChainSpec(0.0, 10, R), fc.ChainSpec(P, 0, R), fc.ChainSpec(P, 10, -1.0),
                fc.ChainSpec(P, 10, R, "WAVY")):
        with pytest.raises(ValueError):
            fc.chain_pins(bad, (0.1, 0.16, 0.0))
    with pytest.raises(ValueError):
        fc.chain_pins(SPEC, np.zeros((2, 2)))
    tight = fc.chain_pins(fc.ChainSpec(P, 30, 0.001), (0.3, 2 * fc.MIN_RADIUS * P, 0.0))
    assert not tight.short[0] and np.abs(chords(tight.pins) - P).max() < 1e-12


def test_speed():
    moving = stroke(0.0, 1.2, 250)
    fc.chain_pins(SPEC, moving)
    times = []
    for _ in range(20):
        start = time.perf_counter()
        fc.chain_pins(SPEC, moving)
        times.append(time.perf_counter() - start)
    batch = sorted(times)[len(times) // 2]
    times = []
    for i in range(40):
        start = time.perf_counter()
        fc.chain_pins(SPEC, moving[i])
        times.append(time.perf_counter() - start)
    one = sorted(times)[len(times) // 2]
    print(f"\n250 frames x 60 links: {batch * 1e3:.2f} ms; one frame: {one * 1e3:.2f} ms")
    assert batch < 0.050                                # web machine, 4 cores: 1.2 ms (asked: 5 ms)
    assert one < 0.010                                  # web machine: 0.45 ms (asked: 1 ms)


# ---------------------------------------------------------------------------
# the links on their pins
# ---------------------------------------------------------------------------

def test_link_frames():
    chain = fc.chain_pins(SPEC, stroke(0.0, 1.0, 5, w=0.02))
    origin, x, z = fc.link_frames(chain.pins)
    assert origin.shape == x.shape == z.shape == (5, N, 3)
    assert np.array_equal(origin, chain.pins[:, :-1])
    assert np.allclose(origin + P * x, chain.pins[:, 1:], atol=1e-12)
    assert np.allclose(np.linalg.norm(z, axis=2), 1.0, atol=1e-12)
    assert np.abs(np.einsum("bli,bli->bl", x, z)).max() < 1e-12
    assert z[:, :, 2].min() > 0.99                      # across the chain, also where the chain goes sideways
    # of all unit vectors square to x it is the one nearest to w
    assert np.allclose(z[:, :, 2], np.sqrt(1.0 - x[:, :, 2] ** 2), atol=1e-12)
    mats = fc.pin_matrices(chain.pins)
    assert mats.shape == (5, N, 4, 4)
    assert np.allclose(mats[..., :3, 0], x) and np.allclose(mats[..., :3, 2], z)
    assert np.allclose(mats[..., :3, 1], np.cross(z, x)) and np.allclose(mats[..., :3, 3], origin)
    assert np.allclose(np.linalg.det(mats[..., :3, :3]), 1.0, atol=1e-12)
    assert np.allclose(mats[..., 3, :], [0, 0, 0, 1])
    # one chain: (links + 1, 3) -> (links, 3); in the plane z is w itself and y points to the moving run
    flat = fc.chain_pins(SPEC, (0.5, 2 * R, 0.0)).pins[0]
    origin, x, z = fc.link_frames(flat)
    assert origin.shape == (N, 3) and np.array_equal(z, np.tile([0.0, 0.0, 1.0], (N, 1)))
    assert np.allclose(np.cross(z, x)[0], [0, 1, 0]) and np.allclose(np.cross(z, x)[-1], [0, -1, 0])
    # a link pointing straight across still gets a frame
    _o, x, z = fc.link_frames(np.array([[0.0, 0, 0], [0, 0, 1.0]]))
    assert np.isfinite(z).all() and abs(float(x[0] @ z[0])) < 1e-12


# ---------------------------------------------------------------------------
# the chain read from its CAD links
# ---------------------------------------------------------------------------

def rigid(rng, size=1.0):
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    if np.linalg.det(q) < 0:
        q[:, 0] *= -1
    m = np.eye(4)
    m[:3, :3], m[:3, 3] = q, rng.normal(size=3) * size
    return m


def cad_links(spec, moving, world, own, kinds):
    """Link matrices as a CAD file has them: each link rigid on its two pins, its own origin anywhere."""
    pins = fc.chain_pins(spec, moving).pins[0]
    return world @ fc.pin_matrices(pins) @ own[kinds]


CENTRE = np.array([0.5 * P, 0.004, 0.003, 1.0])        # a link's mesh centre in its pin frame


def centres_of(spec, moving, world):
    pins = fc.chain_pins(spec, moving).pins[0]
    return (world @ fc.pin_matrices(pins) @ CENTRE)[:, :3]


@pytest.mark.parametrize("mode, links, v", [("STRAIGHT", 37, 2 * R), ("GLIDE", 80, REST), ("STRAIGHT", 37, 0.15)])
@pytest.mark.parametrize("n_kinds", [1, 2])
@pytest.mark.parametrize("with_centres", [True, False])
def test_fit_links_round_trip(mode, links, v, n_kinds, with_centres):
    rng = np.random.default_rng(links + n_kinds)
    spec = fc.ChainSpec(P, links, R, mode)
    world = rigid(rng)
    own = np.stack([rigid(rng, 0.02), rigid(rng, 0.02)])         # origin not on a pin, turned any way
    if not with_centres:
        own[:, :3, 3] = [[0.02, 0.003, 0.0], [0.018, -0.002, 0.0]]     # origins near the links' middles
    kinds = np.arange(links) % n_kinds
    drawn = np.array([0.3, v, 0.0])
    mats = cad_links(spec, drawn, world, own, kinds)
    centres = centres_of(spec, drawn, world)
    mix = rng.permutation(links)
    fit = fc.fit_links(mats[mix], centres[mix] if with_centres else None, kinds[mix] + 5)
    assert fit.ok and fit.problem == ""
    assert np.array_equal(mix[fit.order], np.arange(links))     # the fixed run is the longer one: end A as built
    assert fit.links == links and fit.mode == mode
    assert abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-6 and fit.residual < 1e-9
    assert np.abs(fit.moving[:2] - drawn[:2]).max() < 1e-9
    assert fit.pose_error < 1e-9                         # chain_pins draws the CAD pose again
    assert fit.local.shape == (links, 4, 4) and fit.pins.shape == (links + 1, 3)
    assert np.abs(fit.frame[:3, :3] - world[:3, :3]).max() < 1e-9      # u, v, w of the chain as built
    assert np.abs(chords(fit.pins) - P).max() < 1e-9
    # the CAD pose again, link by link
    assert np.abs(fc.link_matrices(fit.pins_chain(), fit.local, fit.frame) - mats[mix][fit.order]).max() < 1e-9
    # another pose: the links exactly where building them there puts them
    # (sideways only where the links' origins are on the pins' level: with centres given the pins are put on the
    # centres' level, 3 mm further across, and a link that goes sideways then stands 0.03 mm differently)
    for other in ((0.55, v, 0.0), (-0.1, v, 0.0), (0.4, v + 0.004, 0.0 if with_centres else 0.006)):
        direct = cad_links(spec, other, world, own, kinds)
        moving = fit.moving + np.array(other) - drawn
        pins = fc.chain_pins(fit.spec(), moving)
        assert not pins.short[0]
        assert np.abs(fc.link_matrices(pins.pins[0], fit.local, fit.frame) - direct).max() < 1e-6
    # the other end as the fixed one: complete and consistent
    rev = fit.reversed()
    assert rev.ok and np.array_equal(rev.order, fit.order[::-1]) and np.array_equal(rev.pins, fit.pins[::-1])
    assert rev.pitch == fit.pitch and rev.radius == fit.radius and rev.links == links
    assert np.allclose(rev.frame[:3, 3], fit.pins[-1]) and np.allclose(rev.frame @ np.append(rev.moving, 1.0),
                                                                        np.append(fit.pins[0], 1.0))
    assert np.abs(fc.link_matrices(rev.pins_chain(), rev.local, rev.frame) - mats[mix][rev.order]).max() < 1e-9
    twice = rev.reversed()
    assert np.allclose(twice.frame, fit.frame, atol=1e-9) and np.allclose(twice.local, fit.local, atol=1e-9)
    assert np.allclose(twice.moving, fit.moving, atol=1e-9) and twice.mode == fit.mode
    if mode == "STRAIGHT" and v == 2 * R:
        # two runs and half a circle look the same from both ends: the reversed fit draws the same links
        assert np.allclose(rev.moving, [-0.3, 2 * R, 0.0], atol=1e-9) and rev.pose_error < 1e-9
        direct = cad_links(spec, (0.55, v, 0.0), world, own, kinds)
        frame_now = rev.frame.copy()
        frame_now[:3, 3] += world[:3, 0] * 0.25         # the old moving end went 250 mm along u
        pins = fc.chain_pins(rev.spec(), rev.moving - [0.25, 0.0, 0.0]).pins[0]
        assert np.abs(fc.link_matrices(pins, rev.local, frame_now) - direct[::-1]).max() < 1e-6


def test_fit_links_takes_the_longer_run_as_the_fixed_one():
    rng = np.random.default_rng(11)
    world, own = rigid(rng), rigid(rng, 0.02)[None]
    spec = fc.ChainSpec(P, 40, R)
    drawn = np.array([-0.6, 2 * R, 0.0])                # 6 links on the fixed run, 27 on the moving run
    mats = cad_links(spec, drawn, world, own, np.zeros(40, dtype=int))
    fit = fc.fit_links(mats)
    assert fit.ok and np.array_equal(fit.order, np.arange(40)[::-1])
    assert np.allclose(fit.moving, [0.6, 2 * R, 0.0], atol=1e-9)
    assert abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-6
    back = fit.reversed()
    assert np.array_equal(back.order, np.arange(40)) and np.allclose(back.moving, drawn, atol=1e-9)
    assert np.allclose(back.frame[:3, :3], world[:3, :3], atol=1e-9)        # the frame as built ...
    shift = back.frame[:3, 3] - world[:3, 3]                                # ... its origin moved across the chain only
    assert np.allclose(shift, world[:3, 2] * float(shift @ world[:3, 2]), atol=1e-9)


def test_fit_links_sideways_offset_and_scaled_links():
    """A CAD pose with the moving end 8 mm out of the plane; link matrices that carry a scale (mm parts)."""
    rng = np.random.default_rng(12)
    world, own = rigid(rng), rigid(rng, 0.02)[None]
    spec = fc.ChainSpec(P, 37, R)
    mats = cad_links(spec, (0.3, 2 * R, 0.008), world, own, np.zeros(37, dtype=int))
    fit = fc.fit_links(mats)
    assert fit.ok and fit.problem == "" and abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-4
    # links that go sideways tilt the plane read from them a little: the moving end to 2 mm, the pose to 1.5 mm
    assert np.allclose(fit.moving, [0.3, 2 * R, 0.008], atol=2e-3) and fit.pose_error < 1.5e-3
    assert np.abs(fc.link_matrices(fit.pins_chain(), fit.local, fit.frame) - mats[fit.order]).max() < 1e-9
    scale = np.diag([0.001, 0.001, 0.001, 1.0])
    mats = cad_links(spec, (0.3, 2 * R, 0.0), world, own, np.zeros(37, dtype=int)) @ scale
    fit = fc.fit_links(mats)
    assert fit.ok and fit.problem == "" and abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-6
    direct = cad_links(spec, (0.6, 2 * R, 0.0), world, own, np.zeros(37, dtype=int)) @ scale
    pins = fc.chain_pins(fit.spec(), fit.moving + [0.3, 0.0, 0.0]).pins[0]
    assert np.abs(fc.link_matrices(pins, fit.local, fit.frame) - direct).max() < 1e-6


def test_fit_links_end_pieces_and_a_link_the_other_way_round():
    rng = np.random.default_rng(13)
    world = rigid(rng)
    own = np.stack([rigid(rng, 0.02), rigid(rng, 0.02), rigid(rng, 0.02)])
    spec = fc.ChainSpec(P, 37, R)
    kinds = np.zeros(37, dtype=int)
    kinds[0], kinds[-1] = 1, 2                          # a bracket link of its own at each end
    drawn = (0.3, 2 * R, 0.0)
    mats, centres = cad_links(spec, drawn, world, own, kinds), centres_of(spec, drawn, world)
    mix = rng.permutation(37)
    fit = fc.fit_links(mats[mix], centres[mix], kinds[mix])
    assert fit.ok and fit.problem == "" and np.array_equal(mix[fit.order], np.arange(37))
    assert abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-6 and fit.pose_error < 1e-9
    direct = cad_links(spec, (0.6, 2 * R, 0.0), world, own, kinds)
    pins = fc.chain_pins(fit.spec(), fit.moving + [0.3, 0.0, 0.0]).pins[0]
    assert np.abs(fc.link_matrices(pins, fit.local, fit.frame) - direct).max() < 1e-6
    # one kind of link, the 9th and the 25th put in turned end for end (about the middle between their pins)
    kinds = np.zeros(37, dtype=int)
    turned = np.eye(4)
    turned[:3, :3] = np.diag([-1.0, -1.0, 1.0])
    turned[0, 3] = P
    extra = np.tile(np.eye(4), (37, 1, 1))
    extra[[8, 24]] = turned
    pose = lambda moving: world @ fc.pin_matrices(fc.chain_pins(spec, moving).pins[0]) @ extra @ own[0]   # noqa: E731
    mats = pose(drawn)
    fit = fc.fit_links(mats[mix], centres[mix])
    assert fit.ok and fit.problem == "" and np.array_equal(mix[fit.order], np.arange(37))
    assert abs(fit.pitch - P) < 1e-9 and abs(fit.radius - R) < 1e-6 and fit.residual < 1e-9
    pins = fc.chain_pins(fit.spec(), fit.moving + [0.3, 0.0, 0.0]).pins[0]
    assert np.abs(fc.link_matrices(pins, fit.local, fit.frame) - pose((0.6, 2 * R, 0.0))).max() < 1e-6


def test_fit_links_bend_of_three_links_and_rounded_numbers():
    rng = np.random.default_rng(17)
    world, own = rigid(rng), rigid(rng, 0.02)[None]
    # a bend so tight that only three pins are on it: no two links turn by the same angle, the runs say the radius
    tight = fc.ChainSpec(P, 37, 1.1 * P)
    mats = cad_links(tight, (0.3, 2.2 * P, 0.0), world, own, np.zeros(37, dtype=int))
    fit = fc.fit_links(mats)
    assert fit.ok and fit.problem == "" and abs(fit.radius - 1.1 * P) < 1e-9 and fit.pose_error < 1e-9
    # matrices as Blender keeps them (32-bit), and a pose rounded to 0.01 mm: still the chain, to that precision
    spec = fc.ChainSpec(P, 37, R)
    exact = cad_links(spec, (0.3, 2 * R, 0.0), world, own, np.zeros(37, dtype=int))
    fit = fc.fit_links(exact.astype(np.float32).astype(float))
    assert fit.ok and fit.problem == "" and abs(fit.pitch - P) < 1e-7 and abs(fit.radius - R) < 1e-6
    assert fit.residual < 1e-6 and fit.pose_error < 1e-6            # measured 3e-8, 5e-8
    rough = exact.copy()
    rough[:, :3, 3] += rng.normal(size=(37, 3)) * 1e-5
    fit = fc.fit_links(rough)
    assert fit.ok and fit.problem == "" and abs(fit.pitch - P) < 1e-5 and abs(fit.radius - R) < 0.002 * R
    assert fit.residual < 1e-4 and fit.pose_error < 1e-4            # measured 2e-5, 3e-5


def test_fit_links_that_do_not_hinge_are_placed_by_their_centres():
    """Links whose matrices say nothing (all the same turn: the shape is baked into each mesh)."""
    spec = fc.ChainSpec(P, 37, R)
    pins = fc.chain_pins(spec, (0.3, 2 * R, 0.0)).pins[0]
    mats = np.tile(np.eye(4), (37, 1, 1))
    mats[:, :3, 3] = 0.5 * (pins[:-1] + pins[1:])
    fit = fc.fit_links(mats)
    assert fit.ok and "centres" in fit.problem
    assert fit.links == 37 and abs(fit.pitch - P) < 1e-3 * P and abs(fit.radius - R) < 0.05 * R
    assert np.allclose(fit.pins[1:-1], 0.5 * (mats[:-1, :3, 3] + mats[1:, :3, 3]))
    assert np.abs(fc.link_matrices(fit.pins_chain(), fit.local, fit.frame) - mats[fit.order]).max() < 1e-9
    assert np.allclose(fit.moving[:2], [0.3, 2 * R], atol=0.03)


def test_fit_links_says_what_is_wrong():
    rng = np.random.default_rng(14)
    world, own = rigid(rng), rigid(rng, 0.02)[None]
    spec = fc.ChainSpec(P, 37, R)
    mats = cad_links(spec, (0.3, 2 * R, 0.0), world, own, np.zeros(37, dtype=int))
    few = fc.fit_links(mats[:3])
    assert not few.ok and "4 links" in few.problem and few.reversed().ok is False
    # a link missing in the middle; the links of two chains
    gap = fc.fit_links(np.delete(mats, 12, axis=0))
    assert not gap.ok and "not one chain" in gap.problem
    second = mats.copy()
    second[:, :3, 3] += world[:3, 2] * 0.5
    two = fc.fit_links(np.vstack([mats, second]))
    assert not two.ok and "not one chain" in two.problem
    # drawn straight: no bend to read, but the pitch is known
    line = np.tile(np.eye(4), (12, 1, 1))
    line[:, 0, 3] = np.arange(12) * P
    straight = fc.fit_links(world @ line @ own[0])
    assert not straight.ok and "straight" in straight.problem and "radius" in straight.problem
    assert abs(straight.pitch - P) < 1e-9 and straight.links == 12
    with pytest.raises(ValueError):
        fc.fit_links(np.zeros((5, 3, 3)))
    bad = mats.copy()
    bad[4, 0, 3] = math.nan
    assert not fc.fit_links(bad).ok


# ---------------------------------------------------------------------------
# a chain drawn as one solid
# ---------------------------------------------------------------------------

def u_band(run_low, run_high, radius, height, width, sides=24):
    """Mesh points of a U-shaped band: lower run from u = -run_low, upper run from u = -run_high, bend at u > 0."""
    angle = np.linspace(-0.5 * math.pi, 0.5 * math.pi, sides + 1)
    flat = []
    for rad in (radius + 0.5 * height, radius - 0.5 * height):
        flat += [(rad * math.cos(a), radius + rad * math.sin(a)) for a in angle]
        flat += [(-run_low, radius - rad), (-run_high, radius + rad)]
    flat = np.array(flat)
    return np.vstack([np.column_stack([flat, np.full(len(flat), z)]) for z in (-0.5 * width, 0.5 * width)])


def test_fit_solid_reads_a_u_band():
    rng = np.random.default_rng(15)
    world = rigid(rng)
    height, width = 0.025, 0.06
    verts = u_band(0.9, 0.4, R, height, width) @ world[:3, :3].T + world[:3, 3]
    fit = fc.fit_solid(verts)
    assert fit.ok and fit.problem == ""
    assert abs(fit.radius - R) < 1e-6 and abs(fit.height - height) < 1e-6 and abs(fit.width - width) < 1e-6
    assert abs(fit.pitch - 1.6 * height) < 1e-9 and fit.local.shape == (0, 4, 4)
    length = 0.9 + 0.4 + math.pi * R
    assert fit.links == round(length / fit.pitch) and fit.pins.shape == (fit.links + 1, 3)
    assert np.allclose(fit.moving, [0.5, 2 * R, 0.0], atol=1e-6)        # the longer (lower) run is the fixed one
    # the frame: origin in the middle of the fixed run's end, u along the run, v to the other run
    assert np.allclose(fit.frame[:3, 3], (world @ [-0.9, 0.0, 0.0, 1.0])[:3], atol=1e-6)
    assert np.allclose(fit.frame[:3, 0], world[:3, 0], atol=1e-6)
    assert np.allclose(fit.frame[:3, 1], world[:3, 1], atol=1e-6)
    assert np.allclose(np.cross(fit.frame[:3, 0], fit.frame[:3, 1]), fit.frame[:3, 2], atol=1e-9)
    assert np.allclose(fit.pins[0], fit.frame[:3, 3])
    assert np.allclose(fit.pins[-1], (world @ [-0.4, 2 * R, 0.0, 1.0])[:3], atol=1e-6)
    assert np.abs(chords(fit.pins) - fit.pitch).max() < 1e-12
    assert fit.residual < 1e-6
    # the pitch given; the upper run the longer one; the other end
    fit = fc.fit_solid(u_band(0.3, 1.1, R, height, width), pitch=P)
    assert fit.ok and fit.pitch == P and fit.links == round((1.4 + math.pi * R) / P)
    assert np.allclose(fit.moving, [0.8, 2 * R, 0.0], atol=1e-6)
    assert np.allclose(fit.frame[:3, 3], [-1.1, 2 * R, 0.0], atol=1e-6)
    assert np.allclose(fit.frame[:3, 1], [0, -1, 0], atol=1e-6)
    rev = fit.reversed()
    assert rev.ok and rev.width == fit.width and rev.height == fit.height and rev.radius == fit.radius
    assert np.allclose(rev.frame[:3, 3], [-0.3, 0.0, 0.0], atol=1e-6)
    assert np.allclose(rev.moving, [-0.8, 2 * R, 0.0], atol=1e-6)


def test_fit_solid_does_not_guess():
    rng = np.random.default_rng(16)
    box = rng.uniform(-1, 1, size=(400, 3)) * [0.5, 0.1, 0.03]
    assert not fc.fit_solid(box).ok and fc.fit_solid(box).problem
    corners = np.array([[x, y, z] for x in (0, 1.0) for y in (0, 0.03) for z in (0, 0.06)])
    bar = np.vstack([corners, corners + [0.0, 0.0, 0.0]])
    assert not fc.fit_solid(bar).ok                      # a straight bar: no bend
    assert not fc.fit_solid(np.zeros((3, 3))).ok
    assert not fc.fit_solid(u_band(0.9, 0.4, R, 0.025, 0.06), pitch=0.5).ok      # links longer than the bend allows
    # an L-shaped band (a quarter turn) is not a drag chain's U
    angle = np.linspace(-0.5 * math.pi, 0.0, 13)
    flat = []
    for rad in (R + 0.0125, R - 0.0125):
        flat += [(rad * math.cos(a), R + rad * math.sin(a)) for a in angle]
        flat += [(-0.6, R - rad), (rad, R + 0.5)]
    flat = np.array(flat)
    ell = np.vstack([np.column_stack([flat, np.full(len(flat), z)]) for z in (-0.03, 0.03)])
    assert not fc.fit_solid(ell).ok


def test_open_row_tells_a_drag_chain_from_a_loop():
    """A drag chain's links lie in one open row; a chain running round in a loop is not one (found by the panel's
    review: a tensioner's track was offered as a drag chain)."""
    def at(x, y, a):
        m = np.eye(4)
        m[:2, :2] = [[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]
        m[:2, 3] = x, y
        return m
    loop = np.array([at(np.cos(a), np.sin(a), a) for a in np.arange(24) * 2 * np.pi / 24])
    chain = np.array([at(0.04 * k, 0.0, 0.0) for k in range(9)]
                     + [at(0.32 + 0.08 * np.sin(a), 0.08 - 0.08 * np.cos(a), a) for a in np.pi * np.arange(1, 6) / 6]
                     + [at(0.04 * k, 0.16, np.pi) for k in range(8, -1, -1)])
    assert not flex_chain_module().open_row(loop)
    assert flex_chain_module().open_row(chain)
    assert not flex_chain_module().open_row(chain[:2])


def flex_chain_module():
    from fresing_render.core import flex_chain
    return flex_chain
