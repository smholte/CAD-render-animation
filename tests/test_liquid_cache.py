"""The coolant liquid's bake on disk (task 0255, ``fresing_render/core/liquid_cache.py``): 8-bit steps of 0.05 mm
where wet, a round trip, random access, the fingerprint, a broken file, and a frame read in < 2 ms."""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

from fresing_render.core import liquid as L
from fresing_render.core import liquid_cache as C

MM = 1e-3


def test_depths_round_trip_in_steps_of_0_05_mm():
    rng = np.random.RandomState(3)
    d = rng.rand(37, 53) * 3 * MM
    d[rng.rand(37, 53) < 0.6] = 0.0                    # mostly dry
    d[5, 5] = 0.02 * MM                                # thinner than half a step: dry
    d[6, 6] = 0.04 * MM                                # the film: one step
    d[7, 7] = 30 * MM                                  # deeper than 255 steps: the overflow list
    back, pos = C.decode_depth(C.encode_depth(d), d.shape)
    assert back.dtype == np.float32 and back.shape == d.shape
    assert np.abs(back - d).max() <= C.STEP / 2 + 1e-9
    assert back[5, 5] == 0.0 and back[6, 6] == pytest.approx(C.STEP)
    assert back[7, 7] == pytest.approx(30 * MM, abs=C.STEP / 2)
    assert np.array_equal(back > 0, np.rint(d / C.STEP) > 0)


def test_a_bake_round_trip_with_random_access(tmp_path):
    path = str(tmp_path / "liquid.bin")
    shapes = [("table", (40, 60)), ("tray", (20, 30))]
    frames = {}
    with C.Writer(path, "abc123", shapes, 24) as w:
        for f in (3, 1, 2, 0):                         # any order
            d = [np.full((40, 60), f * 0.1 * MM), np.full((20, 30), f * MM)]
            P = np.array([[f, 0.5, -0.25]] * f, float).reshape(-1, 3)
            V = np.full(f, 1e-6 * (f + 1))
            t = dict(poured=float(f), on_charts=0.5 * f, in_flight=0.1, drained=0.2, floor=0.0)
            w.add(f, d, P, V, t)
            frames[f] = (d, P, V, t)
    r = C.Reader.open(path, "abc123")
    assert r is not None and r.frames == [0, 1, 2, 3] and r.names == ["table", "tray"] and r.fps == 24
    for f in (2, 0, 3, 1):
        d, P, V, t = r.read(f)
        assert np.allclose(d[0], frames[f][0][0], atol=C.STEP / 2) and np.allclose(d[1], frames[f][0][1], atol=C.STEP / 2)
        assert np.allclose(P, frames[f][1]) and np.allclose(V, frames[f][2], rtol=1e-6)
        assert t == frames[f][3]
    r.close()


def test_a_bake_for_another_fingerprint_or_a_broken_file_is_not_used(tmp_path):
    path = str(tmp_path / "liquid.bin")
    with C.Writer(path, "one", [("p", (10, 10))], 24) as w:
        w.add(0, [np.zeros((10, 10))])
    assert C.Reader.open(path, "two") is None
    assert C.Reader.open(path, "one") is not None
    assert C.Reader.open(str(tmp_path / "missing.bin")) is None
    data = open(path, "rb").read()
    open(path, "wb").write(data[:-5])                 # cut off
    assert C.Reader.open(path) is None
    open(path, "wb").write(b"rubbish" * 10)
    assert C.Reader.open(path) is None


def test_a_bake_stopped_half_way_leaves_no_file(tmp_path):
    path = str(tmp_path / "liquid.bin")
    with pytest.raises(RuntimeError):
        with C.Writer(path, "x", [("p", (4, 4))], 24) as w:
            w.add(0, [np.zeros((4, 4))])
            raise RuntimeError("cancelled")
    assert not os.path.exists(path) and not os.path.exists(path + ".part")


def test_wrong_shapes_are_refused(tmp_path):
    with C.Writer(str(tmp_path / "x.bin"), "x", [("p", (4, 4))], 24) as w:
        with pytest.raises(ValueError):
            w.add(0, [np.zeros((4, 5))])
        with pytest.raises(ValueError):
            w.add(0, [np.zeros((4, 4)), np.zeros((4, 4))])


def test_a_frame_of_250000_cells_reads_in_under_2_ms(tmp_path):
    """The speed scene's charts with the liquid of a busy frame (a quarter wet, a deep slot)."""
    rng = np.random.RandomState(1)
    a = np.zeros((250, 600))
    b = np.zeros((150, 700))
    a[100:150, :] = 12 * MM + rng.rand(50, 600) * MM
    a[rng.rand(250, 600) < 0.1] = 0.05 * MM
    b[:, 400:] = rng.rand(150, 300) * 2 * MM
    path = str(tmp_path / "big.bin")
    with C.Writer(path, "f", [("table", a.shape), ("tray", b.shape)], 24) as w:
        for f in range(5):
            w.add(f, [a, b])
    r = C.Reader.open(path, "f")
    times = []
    for _ in range(25):
        t0 = time.perf_counter()
        d, _, _, _ = r.read(2)
        times.append(time.perf_counter() - t0)
    r.close()
    assert np.abs(d[0] - a).max() <= C.STEP / 2 + 1e-9
    assert float(np.median(times)) < 2e-3, np.median(times)
    assert os.path.getsize(path) < 5 * 120_000           # well under 16-bit depths of every cell


def test_a_real_bake_round_trip(tmp_path):
    """The solver's frames into the cache and back: what is read is what was baked, to half a step."""
    bed = np.zeros((50, 80))
    bed[20:30, 10:70] = -5 * MM
    ch = L.Chart("plate", bed, MM, 0, 0)
    sim = L.Liquid([ch], [L.still(30)], 24, floor_z=-1)
    path = str(tmp_path / "bake.bin")
    kept = {}
    with C.Writer(path, "fp", [(ch.name, ch.shape)], 24) as w:
        for fr in sim.run(0, 24, pours=lambda f: [L.Pour((40 * MM, 25 * MM, 0.05), 0.5)]):
            w.add(fr.frame, [sim.depth(0)], fr.drops, fr.drop_vol, fr.totals)
            kept[fr.frame] = (sim.depth(0).copy(), fr.drops.copy(), fr.totals)
    r = C.Reader.open(path, "fp")
    for f, (d, P, t) in kept.items():
        dd, PP, VV, tt = r.read(f)
        assert np.abs(dd[0] - d).max() <= C.STEP / 2 + 1e-7
        assert np.allclose(PP, P, atol=1e-6)
        assert tt == pytest.approx(t)
    r.close()
