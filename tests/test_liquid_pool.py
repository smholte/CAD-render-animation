"""The coolant liquid's helper processes (task 0255, ``fresing_render/core/liquid_pool.py``): the liquid is the same
bit for bit with 0, 1, 2 and 4 helpers, a helper that dies stops the bake with a plain error, and closing leaves no
process and no shared memory behind."""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

import liquid_scenes as S
from fresing_render.core import liquid as L
from fresing_render.core import liquid_pool as LP

MM = 1e-3
FPS = 24


def _speed_run(helpers, seconds=3):
    """The speed scene's first seconds: a fingerprint of every frame (depths of both charts, drops, totals)."""
    out = []

    def each(fr, sim):
        out.append((sim.depth(0).tobytes(), sim.depth(1).tobytes(), fr.drops.tobytes(), fr.drop_vol.tobytes(),
                    tuple(sorted(fr.totals.items()))))
    S.speed_scene(helpers=helpers, pour_s=seconds, off_s=1, each=each)
    return out


def test_the_same_liquid_with_0_1_2_and_4_helpers():
    base = _speed_run(0)
    for h in (1, 2, 4):
        other = _speed_run(h)
        assert len(other) == len(base)
        for k, (a, b) in enumerate(zip(base, other)):
            assert a == b, f"frame {k + 1} differs with {h} helpers"


def _tilted_wall_run(helpers):
    """A rocking tank (the effective gravity differs per cell) with liquid behind a wall, a tool and a push: the
    per-cell path of the kernel."""
    cell = 1 * MM
    bed = np.zeros((120, 260))
    bed[:, 130] = 20 * MM
    bed[40:60, 20:60] = np.nan                              # a hole: liquid falls through it
    ch = L.Chart("tank", bed, cell, 0.0, 0.0)
    n = 2 * FPS + 2
    ang = np.radians(10 * np.sin(np.arange(n) / FPS * 2 * math.pi / 1.5))
    mats = np.stack([L.rot_y(a) @ L.rot_z(0.3 * a) for a in ang])
    under = L.Chart("tray", np.zeros((150, 300)), 2 * MM, -0.05, -0.05, open_edges=False)
    sim = L.Liquid([ch, under], [mats, L.translate(n, (0, 0, -0.1))], FPS, floor_z=-1, helpers=helpers)
    fill = np.zeros(bed.shape)
    fill[:, :130] = 6 * MM
    sim.fill(0, fill)
    tool = lambda f: L.Tool((0.2, 0.06, 1 * MM), (0.1, 0.0, 1.0), 4 * MM, 15 * MM, 9000)
    push = lambda f: {0: (np.full(bed.shape, 0.3), 0.0)}
    out = []
    for fr in sim.run(0, n - 2, tool=tool, push=push):
        out.append((sim.depth(0).tobytes(), sim.depth(1).tobytes(), fr.drops.tobytes(),
                    tuple(sorted(fr.totals.items()))))
    sim.close()
    return out


def test_the_same_liquid_with_helpers_when_every_cell_feels_its_own_gravity(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 500)               # small grids: make the helpers take work
    base = _tilted_wall_run(0)
    for h in (2, 4):
        assert _tilted_wall_run(h) == base


def test_runs_are_shared_out_by_cells():
    runs = [(0, 32, 0, 256), (32, 64, 0, 64), (64, 96, 0, 32)]
    parts = LP.Pool.split(runs, 4)
    assert len(parts) == 4 and all(parts)
    cells = sorted(sum((r[1] - r[0]) * (r[3] - r[2]) for r in p) for p in parts)
    assert sum(cells) == 32 * 256 + 32 * 64 + 32 * 32
    assert cells[-1] <= 2 * cells[0] + 32 * 128


def test_a_helper_that_dies_stops_the_bake_with_a_plain_error(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 500)
    ch = L.Chart("p", np.zeros((200, 200)), MM, 0, 0, open_edges=False)
    sim = L.Liquid([ch], [L.still(20)], FPS, floor_z=-1, helpers=2)
    sim.fill(0, np.full((200, 200), 3 * MM) + np.linspace(0, 1 * MM, 200)[None, :])
    sim.step(0)
    sim.pool.procs[0].kill()
    sim.pool.procs[0].wait()
    with pytest.raises(LP.HelperError):
        for f in range(1, 10):
            sim.step(f)
    sim.close()                                               # still closes cleanly
    assert sim.volume(0) > 0                                  # and the state can still be read


def test_closing_leaves_nothing_behind():
    ch = L.Chart("p", np.zeros((300, 300)), MM, 0, 0)
    sim = L.Liquid([ch], [L.still(5)], FPS, floor_z=-1, helpers=2)
    procs = list(sim.pool.procs)
    names = [shm.name for shm in sim.pool.shms]
    assert len(procs) == 2
    sim.fill(0, np.full((300, 300), 1 * MM))
    sim.step(0)
    sim.close()
    assert all(p.poll() is not None for p in procs)
    assert sim.depth(0).shape == (300, 300)                   # readable after closing
    if sys.platform.startswith("linux"):
        assert not any(os.path.exists("/dev/shm/" + n.lstrip("/")) for n in names)


def test_default_helpers():
    n = LP.default_helpers()
    assert n == 0 or 2 <= n <= LP.MAX_HELPERS


@pytest.mark.skipif(not hasattr(__import__("signal"), "SIGSTOP"), reason="needs SIGSTOP")
def test_a_helper_that_hangs_stops_the_bake_after_its_time_out(monkeypatch):
    import signal
    monkeypatch.setattr(LP, "MIN_CELLS", 500)
    monkeypatch.setattr(LP, "ANSWER_TIMEOUT", 2.0)
    ch = L.Chart("p", np.zeros((200, 200)), MM, 0, 0, open_edges=False)
    sim = L.Liquid([ch], [L.still(20)], FPS, floor_z=-1, helpers=2)
    sim.fill(0, np.full((200, 200), 3 * MM) + np.linspace(0, 1 * MM, 200)[None, :])
    sim.step(0)
    os.kill(sim.pool.procs[1].pid, signal.SIGSTOP)
    with pytest.raises(LP.HelperError, match="did not answer"):
        for f in range(1, 10):
            sim.step(f)
    with pytest.raises(LP.HelperError):                      # no going on alone with a half-stepped state
        sim.step(11)
    sim.close()


def test_a_failure_in_the_master_mid_frame_stops_the_bake(monkeypatch):
    monkeypatch.setattr(LP, "MIN_CELLS", 500)
    ch = L.Chart("p", np.zeros((200, 200)), MM, 0, 0, open_edges=False)
    sim = L.Liquid([ch], [L.still(20)], FPS, floor_z=-1, helpers=2)
    sim.fill(0, np.full((200, 200), 3 * MM) + np.linspace(0, 1 * MM, 200)[None, :])
    sim.step(0)
    kr = sim.kernels[0]
    real = kr.sub

    def broken(k):
        if k == 1:
            raise MemoryError("test")
        real(k)
    kr.sub = broken
    with pytest.raises(MemoryError):
        sim.step(1)
    kr.sub = real
    with pytest.raises(LP.HelperError):
        sim.step(2)
    sim.close()
