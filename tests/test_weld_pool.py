"""Task 0368: the welds' work shared out over helper processes (``core/weld_pool.py``) and the faster nearest-point
search (``core.welds.Side.nearest_local``) – the same welds, bit for bit, whatever the number of helpers."""

from __future__ import annotations

import copy
import os
import sys

import numpy as np
import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "tools"))

from fresing_render.core import weld_cad, weld_pool, welds  # noqa: E402

import weld_cad_models as models  # noqa: E402


def _old_nearest_local(side, pts, reach, chunk=24):
    """``nearest_local`` as it was before task 0368: each run of points against the triangles near it."""
    pts = np.asarray(pts, np.float64).reshape(-1, 3)
    d = np.full(len(pts), np.inf)
    q = np.zeros((len(pts), 3))
    t = np.full(len(pts), -1, np.int64)
    for s in range(0, len(pts), chunk):
        c = pts[s:s + chunk]
        idx = side.near(c.min(0), c.max(0), reach)
        if len(idx):
            d[s:s + chunk], q[s:s + chunk], t[s:s + chunk] = side.distance(c, idx)
    return d, q, t


def test_nearest_local_gives_the_same_numbers_as_before():
    rng = np.random.default_rng(7)
    for trial in range(120):
        m = int(rng.integers(1, 300))
        pts = rng.random((m * 3, 3)) * rng.choice([0.01, 0.1, 1.0])
        if trial % 3 == 0:
            pts = np.round(pts, 2)                        # ties: the lowest triangle wins, as before
        tris = np.arange(m * 3).reshape(-1, 3) if trial % 4 else rng.integers(0, m * 3, (m, 3))
        side = welds.Side(pts, tris).prepare()
        if trial % 5 == 0 and len(side.v):
            side.restrict(side.lo[0], side.hi[0] + 0.3)
        P = np.cumsum(rng.normal(0, 0.01, (int(rng.integers(1, 200)), 3)), 0) + 0.3
        reach = float(rng.choice([0.001, 0.01, 0.2]))
        a = _old_nearest_local(side, P, reach)
        b = side.nearest_local(P, reach, batch=int(rng.choice([7, 1000, 120000])))
        for x, y in zip(a, b):
            assert np.array_equal(x, y), trial


def _sig(found):
    out = []
    for f in found:
        seams = [(s.points.tolist(), s.closed, s.kind,
                  [(c.kind, c.theta, c.oa.tolist(), c.da.tolist(), c.na.tolist(), c.ta, c.ob.tolist(), c.db.tolist(),
                    c.nb.tolist(), c.tb, c.sa, c.sb) for c in s.corners]) for s in (f.seams or [])]
        out.append((f.body, f.part_a, f.part_b, f.kind, f.how, f.size, tuple(f.legs), f.length, f.closed,
                    f.intermittent, f.note, f.metal, f.gap, np.asarray(f.tris).tolist(), seams))
    return repr(out)


def _find(meshes, pool):
    ms = copy.deepcopy(meshes)
    named = {m.key for m in ms if weld_cad.weld_name(m.name)}
    bodies = [m for m in ms if m.key in named or weld_cad.maybe_bead(m)]
    parts = [m for m in ms if m.key not in named]
    return weld_cad.find(bodies, parts, named, budget=None, pool=pool)


@pytest.mark.parametrize("kind", ["inventor", "unnamed"])
def test_helpers_find_the_same_welds(kind, tmp_path):
    ms, _by = models.meshes(kind, str(tmp_path))
    alone = _find(ms, None)
    with weld_pool.Pool(n=2, min_jobs=1) as pool:
        shared = _find(ms, pool)
        assert pool.stats["helpers"] >= 1 and pool.stats["by_helpers"] > 0, pool.stats
        assert not pool.stats["errors"], pool.stats["errors"]
    assert len(alone) == 6 and _sig(alone) == _sig(shared)


def test_helpers_make_the_same_beads(tmp_path):
    ms, _by = models.meshes("inventor", str(tmp_path))
    found = _find(ms, None)
    by = {m.key: m for m in ms}
    jobs = []
    for f in found:
        if not f.seams:
            continue
        sa = welds.Side(by[f.part_a].points, by[f.part_a].tris, by[f.part_a].face)
        sb = welds.Side(by[f.part_b].points, by[f.part_b].tris, by[f.part_b].face)
        look = welds.Look(size=max(f.size, 0.003), kind=f.kind)
        jobs.append(([(s, look, sa, sb, (None, None)) for s in f.seams],))
    alone = [welds.job_beads({}, *copy.deepcopy(j)) for j in jobs]
    with weld_pool.Pool(n=2, min_jobs=1) as pool:
        shared = pool.map("welds.job_beads", jobs)
    for a, b in zip(alone, shared):
        for x, y in zip(a, b):
            assert np.array_equal(x.verts, y.verts) and x.faces == y.faces and x.uv == y.uv and x.mat == y.mat
            assert x.end == y.end and x.length == y.length


def test_a_failing_job_is_done_by_the_master():
    """A job that fails in a helper (``_test_job`` fails there on purpose for an odd number) is worked out by the master; a helper
    that stops does not stop the work."""
    with weld_pool.Pool(n=2, min_jobs=1) as pool:
        assert pool.map("weld_pool._test_job", []) == []
        got = pool.map("weld_pool._test_job", [(i,) for i in range(40)])
        assert got == [i * i for i in range(40)]
        assert pool.stats["helpers"] == 2 and any("test" in e for e in pool.stats["errors"])
        pool.procs[0].kill()                              # a helper gone: its jobs go to the others / the master
        got = pool.map("weld_pool._test_job", [(i,) for i in range(40)])
        assert got == [i * i for i in range(40)]


def test_few_jobs_start_no_helper():
    with weld_pool.Pool(n=3) as pool:
        assert pool.map("weld_pool._test_job", [(i,) for i in range(5)]) == [0, 1, 4, 9, 16]
        assert pool.stats["helpers"] == 0 and not pool.started


def test_the_helper_count_follows_the_setting(monkeypatch):
    monkeypatch.setenv("FRESING_WELD_HELPERS", "0")
    assert weld_pool.default_helpers() == 0
    monkeypatch.setenv("FRESING_WELD_HELPERS", "99")
    assert weld_pool.default_helpers() == weld_pool.MAX_HELPERS


def test_no_answer_of_an_earlier_call_is_taken():
    """A call that ends in an error leaves helpers' answers on the way: the next call never takes them (review)."""
    with weld_pool.Pool(n=2, min_jobs=1) as pool:
        with pytest.raises(ValueError):
            pool.map("weld_pool._test_job", [(i, "raise") for i in range(12)])
        assert pool.map("weld_pool._test_job", [(i, "sleep", 0) for i in range(12)]) == [i * i for i in range(12)]


def test_a_job_that_cannot_be_sent_is_done_by_the_master():
    with weld_pool.Pool(n=2, min_jobs=1) as pool:
        jobs = [(i, "sleep", 0, (lambda: 0) if i == 2 else None) for i in range(10)]
        assert pool.map("weld_pool._test_job", jobs) == [i * i for i in range(10)]


def test_a_hanging_helper_with_big_jobs_does_not_stop_the_master(monkeypatch):
    """Big jobs (more than a pipe holds) to a helper that hangs: the master goes on and does its jobs (review)."""
    import time
    monkeypatch.setattr(weld_pool, "ANSWER_TIMEOUT", 2.0)
    big = np.zeros(400_000)                               # 3.2 MB a job
    with weld_pool.Pool(n=1, min_jobs=1) as pool:
        t0 = time.perf_counter()
        got = pool.map("weld_pool._test_job", [(i, "sleep", 60.0, big) for i in range(6)])
        assert got == [i * i for i in range(6)]
        assert time.perf_counter() - t0 < 20 and any("hangs" in e for e in pool.stats["errors"])
