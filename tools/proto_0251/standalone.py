"""Prototype 0251: the stand-alone fluid tests (no machine), each proving one thing with a number.

Run: ``python3 tools/proto_0251/standalone.py [out.json]`` (or pytest on test_standalone.py). Each test builds a small
invented test model as a height-field chart, runs the liquid (liquid.py) and returns its numbers; ``frames`` holds the
depth per frame for the pictures (render_standalone.py).
"""

from __future__ import annotations

import json
import math
import sys
import time

import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import liquid as L  # noqa: E402

MM = 1e-3
FPS = 24


def plate(nx, ny, cell=1 * MM):
    return np.zeros((ny, nx)), cell


def run(world, frames, keep=None, every=1):
    """Run ``frames`` frames; keep[c] = list of depth copies per frame for chart c."""
    store = {c: [] for c in (keep or [])}
    t0 = time.perf_counter()
    hist = []
    for f in range(frames):
        world.run_frame(f)
        hist.append(world.totals())
        if f % every == 0:
            for c in store:
                store[c].append(world.charts[c].depth.astype(np.float32).copy())
    return store, hist, time.perf_counter() - t0


def balance(h):
    t = h[-1]
    held = t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"]
    return abs(held - t["poured"]) / max(t["poured"], 1e-12)


# --- T1 a closed pocket fills to its volume and holds it -------------------------------------------------------
def t1_pocket():
    bed, c = plate(100, 100)
    pk = (slice(30, 70), slice(30, 70))
    bed[pk] = -8 * MM
    ch = L.Chart("plate", bed, c, -50 * MM, -50 * MM)
    vpocket = 40 * MM * 40 * MM * 8 * MM
    q = 2 * vpocket / 2.0                      # twice the pocket in 2 s
    w = L.World([ch], [L.still(14 * FPS + 2)], FPS, floor_z=-0.2,
                sources=lambda f: [((0.0, 0.0, 0.03), q)] if f < 2 * FPS else [])
    store, h, secs = run(w, 14 * FPS, keep=[0], every=2)
    in_pocket = float(ch.depth[pk].sum() * c * c)
    # what stands above the pocket's rim inside the pocket (a meniscus of liquid that is still flowing out) is not
    # part of "what it holds": count the pocket up to its rim
    held = float(np.minimum(ch.depth[pk], 8 * MM + L.FILM).sum() * c * c)
    return dict(name="Closed pocket fills and holds", pocket_cm3=vpocket * 1e6, poured_cm3=w.poured * 1e6,
                held_cm3=held * 1e6, in_pocket_cm3=in_pocket * 1e6, error_pct=100 * (held - vpocket) / vpocket,
                ran_off_cm3=w.floor * 1e6, balance=balance(h), seconds=secs, frames=14 * FPS,
                cells=ch.bed.size, _store=store[0], _bed=bed, _cell=c)


# --- T2 an open slot drains out at its end ---------------------------------------------------------------------
def t2_slot():
    bed, c = plate(100, 40)
    sl = (slice(15, 25), slice(0, 90))          # 10 mm wide, open at x = 0 (the plate's edge), closed at x = 90
    bed[sl] = -6 * MM
    ch = L.Chart("plate", bed, c, -50 * MM, -20 * MM)
    vslot = 10 * MM * 90 * MM * 6 * MM
    q = vslot / 2.0
    w = L.World([ch], [L.still(12 * FPS + 2)], FPS, floor_z=-0.2,
                sources=lambda f: [((30 * MM, 0.0, 0.03), q)] if f < 2 * FPS else [])
    store, h, secs = run(w, 12 * FPS, keep=[0], every=2)
    vols = [x["on_charts"] for x in h]
    stop = 2 * FPS
    peak = max(vols[: stop + 1])
    half = next((k for k in range(stop, len(vols)) if vols[k] < 0.5 * peak), None)
    return dict(name="Open slot drains at its end", slot_cm3=vslot * 1e6, poured_cm3=w.poured * 1e6,
                peak_cm3=peak * 1e6, left_cm3=vols[-1] * 1e6, left_pct=100 * vols[-1] / w.poured,
                half_s=None if half is None else (half - stop) / FPS, ran_off_cm3=w.floor * 1e6,
                balance=balance(h), seconds=secs, frames=12 * FPS, cells=ch.bed.size,
                _store=store[0], _bed=bed, _cell=c)


# --- T3 a plate tilted 0 -> 30 deg spills at the right angle ----------------------------------------------------
def t3_tilt():
    bed, c = plate(80, 80)
    pk = (slice(20, 60), slice(20, 60))         # 40 x 40, 10 deep
    bed[pk] = -10 * MM
    ch = L.Chart("plate", bed, c, -40 * MM, -40 * MM)
    secs_total = 12
    n = secs_total * FPS + 2
    ang = np.radians(np.clip((np.arange(n) / FPS - 1.0) / 10.0, 0, 1) * 30.0)   # 0 for 1 s, then 3 deg/s
    mats = np.stack([L.rot_y(a) for a in ang])
    ch.depth[pk] = 5 * MM                     # half full
    v0 = ch.volume()
    w = L.World([ch], [mats], FPS, floor_z=-0.3)
    w.poured = v0
    spill = None
    vols = []
    store = []
    t0 = time.perf_counter()
    for f in range(secs_total * FPS):
        w.run_frame(f)
        vols.append(float(ch.depth[pk].sum() * c * c))
        if f % 2 == 0:
            store.append(ch.depth.astype(np.float32).copy())
        if spill is None and vols[-1] < 0.99 * v0:
            spill = math.degrees(ang[f])
    secs = time.perf_counter() - t0
    expect = math.degrees(math.atan((10 - 5) / 20.0))
    return dict(name="Tilted plate spills at the right angle", expected_deg=expect, spilled_at_deg=spill,
                error_deg=None if spill is None else spill - expect, left_at_30deg_cm3=vols[-1] * 1e6,
                expected_left_at_30deg_cm3=_left_at(30, 40, 10) * 40 * MM * 1e6,
                balance=balance([w.totals()]), seconds=secs, frames=secs_total * FPS, cells=ch.bed.size,
                _store=store, _bed=bed, _cell=c, _angles=[float(math.degrees(a)) for a in ang[: secs_total * FPS:2]])


def _left_at(deg, width_mm, depth_mm):
    """Cross-section (m^2) a pocket ``width`` wide and ``depth`` deep still holds when tilted by ``deg`` after
    spilling (the surface through the low rim)."""
    t = math.tan(math.radians(deg))
    W, D = width_mm * MM, depth_mm * MM
    if W * t <= D:
        return W * D - 0.5 * W * W * t
    return 0.5 * D * D / t


# --- T4 a tray with a slope empties down its drain in a measured time -------------------------------------------
def t4_tray():
    cell = 4 * MM
    nx, ny = 100, 75                              # 400 x 300 mm
    x = (np.arange(nx) * cell)
    y = (np.arange(ny) * cell)
    X, Y = np.meshgrid(x, y)
    slope = math.radians(2.0)
    bed = (X * math.tan(slope)) + 0.3 * (np.abs(Y - 150 * MM) * math.tan(slope))   # falls to x = 0, to the middle
    drain = np.zeros_like(bed)
    r = 10 * MM
    hole = (X - 2 * MM) ** 2 + (Y - 150 * MM) ** 2 <= (r + cell / 2) ** 2
    drain[hole] = math.pi * r * r / hole.sum()
    ch = L.Chart("tray", bed, cell, 0.0, 0.0, open_edges=False, drain=drain)
    q = 2.0 / 1000 / 60                           # 2 l/min for 10 s
    w = L.World([ch], [L.still(40 * FPS + 2)], FPS, floor_z=-0.3,
                sources=lambda f: [((300 * MM, 150 * MM, 0.05), q)] if f < 10 * FPS else [])
    store, h, secs = run(w, 40 * FPS, keep=[0], every=4)
    vols = [x["on_charts"] + x["in_flight"] for x in h]
    stop = 10 * FPS
    empty = next((k for k in range(stop, len(vols)) if vols[k] < 0.05 * w.poured), None)
    film = float(np.minimum(ch.depth, L.FILM).sum() * cell * cell)
    return dict(name="Sloped tray empties down its drain", poured_l=w.poured * 1e3, drained_l=sum(
        c.drained for c in w.charts) * 1e3, peak_in_tray_cm3=max(vols) * 1e6,
        empty_95pct_s_after_stop=None if empty is None else (empty - stop) / FPS,
        film_left_cm3=film * 1e6, left_cm3=vols[-1] * 1e6, balance=balance(h), seconds=secs, frames=40 * FPS,
        cells=ch.bed.size, _store=store[0], _bed=bed, _cell=cell)


# --- T5 a box moved and stopped hard sloshes and settles ----------------------------------------------------------
def t5_slosh(speed=0.25):
    cell = 2 * MM
    nx, ny = 100, 25                              # 200 x 50 mm, walls all round
    bed = np.zeros((ny, nx))
    ch = L.Chart("box", bed, cell, 0.0, 0.0, open_edges=False)
    ch.depth[:] = 10 * MM
    v0 = ch.volume()
    secs_total = 10
    n = secs_total * FPS + 2
    t = np.arange(n) / FPS
    # moving at ``speed`` with the liquid at rest in the box, then stopped within one frame at 0.5 s
    xs = np.minimum(t, 0.5) * speed
    mats = L.still(n)
    mats[:, 0, 3] = xs
    w = L.World([ch], [mats], FPS, floor_z=-0.3)
    w.poured = v0
    end = []
    store = []
    t0 = time.perf_counter()
    for f in range(secs_total * FPS):
        w.run_frame(f)
        end.append(float(ch.depth[:, -3:].mean()))
        if f % 2 == 0:
            store.append(ch.depth.astype(np.float32).copy())
    secs = time.perf_counter() - t0
    e = np.array(end) - 10 * MM
    after = int(0.55 * FPS)
    s = e[after:] - e[after:].mean()
    F = np.abs(np.fft.rfft(s * np.hanning(len(s)), 8192))
    fr = np.fft.rfftfreq(8192, 1 / FPS)
    period = float(1 / fr[F[1:].argmax() + 1])
    first = float(np.max(np.abs(e[after:after + 2 * FPS])))
    late = float(np.max(np.abs(e[after + 5 * FPS:after + 6 * FPS])))
    expect = 2 * 0.2 / math.sqrt(L.G * 0.01)
    return dict(name="Box stopped hard sloshes and settles", speed_m_s=speed, expected_period_s=expect,
                period_s=period, first_wave_mm=first * 1e3, after_5s_mm=late * 1e3,
                settle_pct=100 * late / max(first, 1e-12),
                balance=abs(ch.volume() - v0) / v0, seconds=secs, frames=secs_total * FPS, cells=ch.bed.size,
                _store=store, _bed=bed, _cell=cell, _x=[float(x) for x in xs[: secs_total * FPS:2]], _end=e.tolist())


# --- T6 nothing leaks through a wall --------------------------------------------------------------------------------
def t6_wall():
    cell = 1 * MM
    nx, ny = 120, 40
    bed = np.zeros((ny, nx))
    bed[:, 60] = 20 * MM                          # a wall ONE cell (1 mm) thick, 20 mm high
    ch = L.Chart("tank", bed, cell, 0.0, 0.0, open_edges=False)
    ch.depth[:, :60] = 8 * MM
    v0 = ch.volume()
    n = 10 * FPS + 2
    ang = np.radians(12 * np.sin(np.arange(n) / FPS * 2 * math.pi / 2.0))   # rocked +-12 deg, 2 s period
    mats = np.stack([L.rot_y(a) for a in ang])
    w = L.World([ch], [mats], FPS, floor_z=-0.3)
    w.poured = v0
    worst = 0.0
    store = []
    t0 = time.perf_counter()
    for f in range(10 * FPS):
        w.run_frame(f)
        worst = max(worst, float(ch.depth[:, 61:].sum() * cell * cell))
        if f % 2 == 0:
            store.append(ch.depth.astype(np.float32).copy())
    secs = time.perf_counter() - t0
    return dict(name="Nothing leaks through a wall", start_cm3=v0 * 1e6, worst_behind_wall_cm3=worst * 1e6,
                volume_change=abs(ch.volume() - v0) / v0, seconds=secs, frames=10 * FPS, cells=ch.bed.size,
                _store=store, _bed=bed, _cell=cell, _angles=[float(math.degrees(a)) for a in ang[: 10 * FPS:2]])


def t7_same_frame():
    """0042's rule: the bake gives the same liquid at a frame however often it is made."""
    a = t1_pocket()["_store"]
    b = t1_pocket()["_store"]
    return dict(name="Same frame, same liquid", identical=all(np.array_equal(x, y) for x, y in zip(a, b)))


ALL = [t1_pocket, t2_slot, t3_tilt, t4_tray, t5_slosh, t6_wall]


def main(out=None):
    res = []
    for t in ALL:
        r = t()
        res.append(r)
        print(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, default=float))
    r = t7_same_frame()
    print(json.dumps(r))
    if out:
        np.savez_compressed(out.replace(".json", ".npz"), **{
            f"t{i + 1}_{k[1:]}": np.asarray(v) for i, r in enumerate(res) for k, v in r.items() if k.startswith("_")})
        json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in res] + [r], open(out, "w"),
                  indent=1, default=float)
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
