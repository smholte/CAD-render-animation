"""Task 0079: the maths of tracks and belts without Blender (fresing_render/core/tracks.py)."""

import math
import os
import sys

import numpy as np
import pytest

from fresing_render.core import tracks as T

HERE = os.path.dirname(__file__)


def _maker():
    pytest.importorskip("OCP")
    sys.path.insert(0, os.path.join(HERE, "..", "tools"))
    import make_test_tracks as M
    return M


def model_pins(y=0.2):
    """The test model's bottom track (tools/make_test_tracks.py ``track_pins``, task 0229: was the demo's), in m, in
    the x-z plane at y: 22 pins 0.1 apart, sprockets of 10 teeth at x = ±0.3."""
    M = _maker()
    pins = M.track_pins("bottom") / 1000.0
    pins[:, 1] = y
    return pins, M.R / 1000.0, M.A_HALF / 1000.0, M.SPROCKET_Z["bottom"] / 1000.0


PITCH, TEETH, N = 0.1, 10, 22
SEAT = 0.06                     # a support roller's centre 60 mm inside the gripping run's pin line


def hinges_of(pins, shuffle=True, seed=1):
    n = len(pins)
    h = np.array([[pins[k], pins[(k + 1) % n]] for k in range(n)])
    if shuffle:
        h = h[np.random.default_rng(seed).permutation(n)]
        h[::2] = h[::2, ::-1]
    return h


def model_loop(with_roller=True):
    pins, R, a, zs = model_pins()
    cent = [(-a, 0.0, zs), (a, 0.5, zs)]
    axes = [(0, 1, 0), (0, -1, 0)]
    if with_roller:
        cent.append((0.05, 0.0, zs + R - SEAT))         # touches the top run from inside, between two pins
        axes.append((0, 1, 0))
    ch = T.chain_of(hinges_of(pins))
    return T.fit(ch, cent, axes, ["drive", "idler", "roller"][:len(cent)]), ch, pins, R


def test_chain_from_shuffled_links():
    pins, *_ = model_pins()
    ch = T.chain_of(hinges_of(pins))
    assert len(ch.pins) == N and ch.pitch == pytest.approx(PITCH)
    d = np.linalg.norm(np.diff(np.vstack([ch.pins, ch.pins[:1]]), axis=0), axis=1)
    assert np.allclose(d, PITCH)                                # neighbours in the order are one pitch apart
    for a, b in ch.link_pins:
        assert b == (a + 1) % N


def test_loop_of_the_test_model_track():
    loop, ch, pins, R = model_loop()
    assert loop.length == pytest.approx(N * PITCH, abs=1e-9)   # 2 runs of 6 links + 2 half turns of 5 teeth
    assert T.length_note(loop, N) == ""
    c, d = loop.locate(ch.pins)
    assert d.max() < 1e-9
    gaps = np.diff(np.sort(c))
    assert np.allclose(gaps, PITCH, atol=1e-9)                  # one pitch apart in c, on runs and on the sprockets
    by = {w.index: w for w in loop.wheels}
    assert by[0].wrapped and by[1].wrapped and not by[2].wrapped
    assert by[0].radius == pytest.approx(R) and by[2].radius == pytest.approx(SEAT)
    assert by[0].wrap == pytest.approx(math.pi) and by[2].wrap == pytest.approx(0.0, abs=1e-6)


def test_every_link_hinges_one_pitch_apart_on_the_loop():
    loop, *_ = model_loop()
    c = np.linspace(0.0, loop.length, 3001)
    A = loop.point(c)
    B = loop.point(loop.ahead(c))
    assert np.abs(np.linalg.norm(B - A, axis=1) - PITCH).max() < 1e-9
    assert loop.locate(B)[1].max() < 1e-9
    _A, X, Z = loop.frames(c)
    assert np.allclose(np.einsum("ij,ij->i", X, Z), 0.0) and np.allclose(np.linalg.norm(Z, axis=1), 1.0)


def test_outward_is_away_from_the_loop():
    loop, ch, pins, R = model_loop(False)
    c = np.linspace(0.0, loop.length, 200, endpoint=False)
    A, _X, Z = loop.frames(c)
    mid = np.array([0.0, 0.2, model_pins()[3]])
    assert ((A - mid) * Z).sum(axis=1).min() > 0.0


def test_sprockets_turn_one_tooth_per_link():
    loop, *_ = model_loop()
    by = {w.index: k for k, w in enumerate(loop.wheels)}
    rate = abs(loop.rate(by[0]))
    assert rate == pytest.approx((2 * math.pi / TEETH) / PITCH)  # 36° per 100 mm of chain, not 1 / R
    assert abs(loop.rate(by[2], 0.04)) == pytest.approx(1 / 0.04)


def test_refusals():
    pins, R, a, zs = model_pins()
    h = hinges_of(pins, shuffle=False)
    with pytest.raises(T.TrackError, match="open"):
        T.chain_of(h[1:])
    bad = h.copy()
    bad[3, 1] = bad[3, 0] + (bad[3, 1] - bad[3, 0]) * 1.02
    with pytest.raises(T.TrackError, match="one pitch"):
        T.chain_of(bad)
    ch = T.chain_of(h)
    with pytest.raises(T.TrackError, match="parallel"):
        T.fit(ch, [(-a, 0, zs), (a, 0, zs)], [(0, 1, 0), (0.1, 1, 0)])
    with pytest.raises(T.TrackError, match="loop"):             # the idler clicked in the wrong place
        T.fit(ch, [(-a, 0, zs), (a - 0.02, 0, zs)], [(0, 1, 0), (0, 1, 0)])
    with pytest.raises(T.TrackError, match="2 wheels"):
        T.fit(ch, [(-a, 0, zs)], [(0, 1, 0)])


def test_two_tracks_of_one_name_are_told_apart():
    pins, *_ = model_pins()
    other = pins + np.array([0.0, 2.0, 0.0])
    h = np.concatenate([hinges_of(pins), hinges_of(other, seed=4)])
    keep = T.loop_of(h, 40)
    assert len(keep) == N and all(k >= N for k in keep)
    with pytest.raises(T.TrackError, match="more than one loop"):
        T.chain_of(h)


def test_belt_round_three_wheels_from_the_test_model():
    M = _maker()
    b = M.NUMBERS["belt"]
    pins = np.array(b["pins"], dtype=float) / 1000.0
    ch = T.chain_of(hinges_of(pins))
    loop = T.fit(ch, [np.array(w["centre"]) / 1000.0 for w in b["wheels"]], [b["axis"]] * 3)
    assert loop.locate(ch.pins)[1].max() < 1e-6
    assert [round(w.radius, 6) for w in sorted(loop.wheels, key=lambda w: w.index)] == [0.12, 0.08, 0.05]
    assert abs(loop.length - b["N"] * b["pb"] / 1000.0) < 0.02 * b["pb"] / 1000.0


def test_drive_expression_keeps_to_the_loop():
    expr = T.drive_expression(-1.5, 0.25, 2.2, 2.0)
    for a in (-1000.0, -3.3, 0.0, 0.7, 12345.6):
        v = eval(expr, {"floor": math.floor, "a": a})
        u = -1.5 * a + 0.25
        assert 2.0 <= v < 4.2 and (v - 2.0) == pytest.approx(u - 2.2 * math.floor(u / 2.2), abs=1e-9)
