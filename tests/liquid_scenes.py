"""Invented test set-ups for the coolant liquid (task 0255; study 0251's stand-alone tests T1–T6 and scene S).

Each function builds a small model as height-field charts, runs ``core/liquid.py`` and returns its numbers (SI, cm^3
where a volume is named ``_cm3``). Used by ``tests/test_liquid*.py``; ``python tests/liquid_scenes.py`` prints them.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fresing_render.core import liquid as L  # noqa: E402

MM = 1e-3
FPS = 24


def lmin(q_m3_s):
    """m^3/s -> l/min."""
    return q_m3_s * 1000.0 * 60.0


def balance(sim):
    t = sim.totals()
    held = t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"]
    return abs(held - t["poured"]), t


def run(sim, frames, pours=None, tool=None, push=None, each=None):
    t0 = time.perf_counter()
    out = []
    for fr in sim.run(0, frames, pours=pours, tool=tool, push=push):
        out.append(fr)
        if each:
            each(fr)
    return out, time.perf_counter() - t0


# --- T1 a closed pocket fills to its volume and holds it ---------------------------------------------------------
def t1_pocket(helpers=0, hold=True):
    bed = np.zeros((100, 100))
    pk = (slice(30, 70), slice(30, 70))
    bed[pk] = -8 * MM
    ch = L.Chart("plate", bed, 1 * MM, -50 * MM, -50 * MM)
    vpocket = 40 * MM * 40 * MM * 8 * MM
    q = 2 * vpocket / 2.0
    sim = L.Liquid([ch], [L.still(14 * FPS + 2)], FPS, floor_z=-0.2, helpers=helpers, hold=hold)
    frames, secs = run(sim, 14 * FPS, pours=lambda f: [L.Pour((0.0, 0.0, 0.03), lmin(q))] if f < 2 * FPS else [])
    d = sim.depth(0)
    held = float(np.minimum(d[pk], 8 * MM + L.FILM).sum() * MM * MM)
    err, t = balance(sim)
    res = dict(pocket_cm3=vpocket * 1e6, poured_cm3=t["poured"] * 1e3, held_cm3=held * 1e6,
               error_pct=100 * (held - vpocket) / vpocket, ran_off_cm3=t["floor"] * 1e3, balance_l=err,
               seconds=secs, frames=len(frames), settled_frames=sum(fr.settled for fr in frames))
    sim.close()
    return res, frames, d.copy()


# --- T2 an open slot drains out at its end ---------------------------------------------------------------------
def t2_slot(helpers=0):
    bed = np.zeros((40, 100))
    sl = (slice(15, 25), slice(0, 90))
    bed[sl] = -6 * MM
    ch = L.Chart("plate", bed, 1 * MM, -50 * MM, -20 * MM)
    vslot = 10 * MM * 90 * MM * 6 * MM
    q = vslot / 2.0
    sim = L.Liquid([ch], [L.still(12 * FPS + 2)], FPS, floor_z=-0.2, helpers=helpers)
    frames, secs = run(sim, 12 * FPS, pours=lambda f: [L.Pour((30 * MM, 0.0, 0.03), lmin(q))] if f < 2 * FPS else [])
    vols = [fr.totals["on_charts"] for fr in frames]
    stop = 2 * FPS - 1
    peak = max(vols[: stop + 1])
    half = next((k for k in range(stop, len(vols)) if vols[k] < 0.5 * peak), None)
    err, t = balance(sim)
    res = dict(slot_cm3=vslot * 1e6, poured_cm3=t["poured"] * 1e3, peak_cm3=peak * 1e3, left_cm3=vols[-1] * 1e3,
               left_pct=100 * vols[-1] / t["poured"], half_s=None if half is None else (half - stop) / FPS,
               balance_l=err, seconds=secs)
    sim.close()
    return res


def _left_at(deg, width_mm, depth_mm):
    t = math.tan(math.radians(deg))
    W, D = width_mm * MM, depth_mm * MM
    if W * t <= D:
        return W * D - 0.5 * W * W * t
    return 0.5 * D * D / t


# --- T3 a plate tilted 0 -> 30 deg spills at the right angle ----------------------------------------------------
def t3_tilt(helpers=0):
    bed = np.zeros((80, 80))
    pk = (slice(20, 60), slice(20, 60))
    bed[pk] = -10 * MM
    ch = L.Chart("plate", bed, 1 * MM, -40 * MM, -40 * MM)
    secs_total = 12
    n = secs_total * FPS + 2
    ang = np.radians(np.clip((np.arange(n) / FPS - 1.0) / 10.0, 0, 1) * 30.0)
    mats = np.stack([L.rot_y(a) for a in ang])
    sim = L.Liquid([ch], [mats], FPS, floor_z=-0.3, helpers=helpers)
    fill = np.zeros_like(bed)
    fill[pk] = 5 * MM
    sim.fill(0, fill)
    v0 = float(fill.sum()) * MM * MM
    spill = None
    vols = []
    t0 = time.perf_counter()
    for fr in sim.run(0, secs_total * FPS):
        vols.append(float(sim.depth(0)[pk].sum() * MM * MM))
        if spill is None and vols[-1] < 0.99 * v0:
            spill = math.degrees(ang[fr.frame])
    secs = time.perf_counter() - t0
    expect = math.degrees(math.atan((10 - 5) / 20.0))
    err, t = balance(sim)
    res = dict(expected_deg=expect, spilled_at_deg=spill, error_deg=None if spill is None else spill - expect,
               left_at_30deg_cm3=vols[-1] * 1e6, expected_left_at_30deg_cm3=_left_at(30, 40, 10) * 40 * MM * 1e6,
               balance_l=err, seconds=secs)
    sim.close()
    return res


# --- T4 a tray with a slope empties down its drain ----------------------------------------------------------------
def t4_tray(helpers=0):
    cell = 4 * MM
    nx, ny = 100, 75
    X, Y = np.meshgrid(np.arange(nx) * cell, np.arange(ny) * cell)
    slope = math.radians(2.0)
    bed = X * math.tan(slope) + 0.3 * (np.abs(Y - 150 * MM) * math.tan(slope))
    drain = np.zeros_like(bed)
    r = 10 * MM
    hole = (X - 2 * MM) ** 2 + (Y - 150 * MM) ** 2 <= (r + cell / 2) ** 2
    drain[hole] = math.pi * r * r / hole.sum()
    ch = L.Chart("tray", bed, cell, 0.0, 0.0, open_edges=False, drain=drain)
    q = 2.0 / 1000 / 60
    sim = L.Liquid([ch], [L.still(40 * FPS + 2)], FPS, floor_z=-0.3, helpers=helpers)
    frames, secs = run(sim, 40 * FPS, pours=lambda f: [L.Pour((300 * MM, 150 * MM, 0.05), lmin(q))]
                       if f < 10 * FPS else [])
    vols = [fr.totals["on_charts"] + fr.totals["in_flight"] for fr in frames]
    stop = 10 * FPS - 1
    poured = frames[-1].totals["poured"]
    empty = next((k for k in range(stop, len(vols)) if vols[k] < 0.05 * poured), None)
    err, t = balance(sim)
    res = dict(poured_l=poured, drained_l=t["drained"], peak_in_tray_cm3=max(vols) * 1e3,
               empty_95pct_s_after_stop=None if empty is None else (empty - stop) / FPS,
               left_cm3=vols[-1] * 1e3, balance_l=err, seconds=secs,
               settled_frames=sum(fr.settled for fr in frames))
    sim.close()
    return res


# --- T5 a box moved and stopped hard sloshes and settles ----------------------------------------------------------
def t5_slosh(helpers=0, speed=0.25):
    cell = 2 * MM
    bed = np.zeros((25, 100))
    ch = L.Chart("box", bed, cell, 0.0, 0.0, open_edges=False)
    secs_total = 10
    n = secs_total * FPS + 2
    t = np.arange(n) / FPS
    mats = L.still(n)
    mats[:, 0, 3] = np.minimum(t, 0.5) * speed
    sim = L.Liquid([ch], [mats], FPS, floor_z=-0.3, helpers=helpers)
    sim.fill(0, np.full(bed.shape, 10 * MM))
    v0 = sim.volume(0)
    end = []
    t0 = time.perf_counter()
    for fr in sim.run(0, secs_total * FPS):
        end.append(float(sim.depth(0)[:, -3:].mean()))
    secs = time.perf_counter() - t0
    e = np.array(end) - 10 * MM
    after = int(0.55 * FPS)
    s = e[after:] - e[after:].mean()
    F = np.abs(np.fft.rfft(s * np.hanning(len(s)), 8192))
    fr_ = np.fft.rfftfreq(8192, 1 / FPS)
    period = float(1 / fr_[F[1:].argmax() + 1])
    first = float(np.max(np.abs(e[after:after + 2 * FPS])))
    late = float(np.max(np.abs(e[after + 5 * FPS:after + 6 * FPS])))
    expect = 2 * 0.2 / math.sqrt(L.G * 0.01)
    res = dict(expected_period_s=expect, period_s=period, first_wave_mm=first * 1e3, after_5s_mm=late * 1e3,
               volume_change=abs(sim.volume(0) - v0) / v0, seconds=secs)
    sim.close()
    return res


# --- T6 nothing leaks through a wall --------------------------------------------------------------------------------
def t6_wall(helpers=0):
    cell = 1 * MM
    bed = np.zeros((40, 120))
    bed[:, 60] = 20 * MM
    ch = L.Chart("tank", bed, cell, 0.0, 0.0, open_edges=False)
    n = 10 * FPS + 2
    ang = np.radians(12 * np.sin(np.arange(n) / FPS * 2 * math.pi / 2.0))
    mats = np.stack([L.rot_y(a) for a in ang])
    sim = L.Liquid([ch], [mats], FPS, floor_z=-0.3, helpers=helpers)
    fill = np.zeros_like(bed)
    fill[:, :60] = 8 * MM
    sim.fill(0, fill)
    v0 = sim.volume(0)
    worst = 0.0
    t0 = time.perf_counter()
    for fr in sim.run(0, 10 * FPS):
        worst = max(worst, float(sim.depth(0)[:, 61:].sum() * cell * cell))
    secs = time.perf_counter() - t0
    res = dict(worst_behind_wall_cm3=worst * 1e6, volume_change=abs(sim.volume(0) - v0) / v0, seconds=secs)
    sim.close()
    return res


ALL = [t1_pocket, t2_slot, t3_tilt, t4_tray, t5_slosh, t6_wall]


def main():
    if "--speed" in sys.argv:
        for h in [int(x) for x in sys.argv[sys.argv.index("--speed") + 1].split(",")]:
            r = speed_scene(helpers=h)
            r.pop("per")
            print("speed helpers", h, json.dumps(r, default=float))
        return
    if "--s" in sys.argv:
        tot, secs, cells = scene_s()
        print("scene S", round(secs, 1), "s", round(1000 * secs / len(tot), 1), "ms a frame", cells, "cells")
        for f in (0, 48, 63, 72, 96, 120, 150, len(tot) - 1):
            print(f + 1, {k: round(v * 1e3, 2) for k, v in tot[f].items()})
        return
    for fn in ALL:
        r = fn()
        if isinstance(r, tuple):
            r = r[0]
        print(fn.__name__, json.dumps(r, default=float))


# --- the speed scene: a 1200 x 500 table with T-slots + a sloped tray under it, 2 mm cells (~255,000 cells) -----
def speed_charts(cell=2 * MM):
    """The table (1200 x 500 mm, three T-slot openings 18 wide and 12 deep along X, open at both ends; top at z = 0)
    and the chip tray under it (1400 x 300 mm, 2 deg towards +x and a V towards y = 0, a drain of 50 mm at the low
    end, walls all round; 300 mm lower)."""
    nx, ny = int(round(1.2 / cell)), int(round(0.5 / cell))
    x0, y0 = -0.6 + cell / 2, -0.25 + cell / 2
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell)
    bed = np.zeros((ny, nx))
    for ys in (-0.125, 0.0, 0.125):
        bed[np.abs(Y - ys) <= 9 * MM] = -12 * MM
    table = L.Chart("table", bed, cell, x0, y0)
    tnx, tny = int(round(1.4 / cell)), int(round(0.3 / cell))
    tx0, ty0 = -0.7 + cell / 2, -0.15 + cell / 2
    TX, TY = np.meshgrid(tx0 + np.arange(tnx) * cell, ty0 + np.arange(tny) * cell)
    t = math.tan(math.radians(2.0))
    tbed = (0.7 - TX) * t + 0.4 * np.abs(TY) * t
    drain = np.zeros_like(tbed)
    hole = (TX - 0.67) ** 2 + TY ** 2 <= (25 * MM + cell / 2) ** 2
    drain[hole] = math.pi * (25 * MM) ** 2 / hole.sum()
    tray = L.Chart("tray", tbed, cell, tx0, ty0, open_edges=False, drain=drain)
    return [table, tray]


def speed_scene(helpers=0, pour_s=60, off_s=30, cell=2 * MM, each=None, hold=True):
    """3 l/min poured into the middle slot, moving along it at 25 mm/s (back and forth over +-375 mm) for ``pour_s``,
    then ``off_s`` with the flow off. Returns numbers (ms per frame, settled share, bookkeeping)."""
    charts = speed_charts(cell)
    frames = int((pour_s + off_s) * FPS)
    mats = [L.still(frames + 2), L.translate(frames + 2, (0.0, 0.0, -0.3))]

    def pours(f):
        t = f / FPS
        if t >= pour_s:
            return []
        s = (t * 0.025) % 1.5                        # 0 .. 1.5 m of travel, back and forth over 0.75 m
        x = -0.375 + (s if s < 0.75 else 1.5 - s)
        return [L.Pour((x, 0.0, 0.1), 3.0)]

    sim = L.Liquid(charts, mats, FPS, floor_z=-1.0, helpers=helpers, hold=hold)
    per = []
    t0 = time.perf_counter()
    settled = 0
    stepped = 0
    for fr in sim.run(0, frames, pours=pours):
        tt = time.perf_counter()
        per.append(tt - t0)
        t0 = tt
        settled += fr.settled
        stepped += sum(fr.stepped)
        if each:
            each(fr, sim)
    err, tot = balance(sim)
    cells = sum(c.bed.size for c in charts)
    res = dict(cells=cells, frames=frames, ms_per_frame=1000 * float(np.mean(per)),
               ms_pour=1000 * float(np.mean(per[: pour_s * FPS])), ms_off=1000 * float(np.mean(per[pour_s * FPS:])),
               settled_share=settled / frames, stepped_share=stepped / (frames * cells),
               seconds=float(np.sum(per)), balance_l=err, totals=tot,
               per=per)
    sim.close()
    return res


# --- scene S of study 0251: a block with a pocket and an open slot on a moving plate, a jet, a tray with a drain ----
S_PLATE = (300 * MM, 160 * MM, 15 * MM)
S_BLOCK = (120 * MM, 80 * MM, 30 * MM)
S_POCKET = (-45 * MM, -5 * MM, -15 * MM, 15 * MM, 8 * MM)
S_SLOT = (10 * MM, 60 * MM, -5 * MM, 5 * MM, 6 * MM)
S_GROOVE = (55 * MM, 14 * MM, 12 * MM)
S_PLATE_Z = 0.10
S_TRAY = (-0.25, 0.25, -0.15, 0.15, 2.0)
S_DRAIN = (-0.23, 0.0, 10 * MM)
S_JET = ((-25 * MM, 0.0, S_PLATE_Z + 0.10), 2.0, 0.2, 3.0)       # world point, l/min, from, to (s)


def scene_s(helpers=0, cell=1.5 * MM, tray_cell=4 * MM, seconds=8):
    """Study 0251's comparison scene S (still 3 s, then the plate +60 mm at 0.15 m/s and back; 2 l/min from 0.2 to
    3.0 s; 8 s). Returns (totals per frame, seconds, cells)."""
    nx, ny = int(round(S_PLATE[0] / cell)), int(round(S_PLATE[1] / cell))
    x0, y0 = -S_PLATE[0] / 2 + cell / 2, -S_PLATE[1] / 2 + cell / 2
    X, Y = np.meshgrid(x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell)
    bed = np.zeros((ny, nx))
    gy, gw, gd = S_GROOVE
    bed[np.abs(Y - gy) <= gw / 2] = -gd
    blk = (np.abs(X) <= S_BLOCK[0] / 2) & (np.abs(Y) <= S_BLOCK[1] / 2)
    bed[blk] = S_BLOCK[2]
    a, b, c, d, dep = S_POCKET
    bed[(X >= a) & (X <= b) & (Y >= c) & (Y <= d)] = S_BLOCK[2] - dep
    a, b, c, d, dep = S_SLOT
    bed[(X >= a) & (X <= b + cell) & (Y >= c) & (Y <= d) & blk] = S_BLOCK[2] - dep
    plate = L.Chart("plate", bed, cell, x0, y0)
    tx0, tx1, ty0, ty1, slope = S_TRAY
    tnx, tny = int(round((tx1 - tx0) / tray_cell)), int(round((ty1 - ty0) / tray_cell))
    cx, cy = tx0 + tray_cell / 2, ty0 + tray_cell / 2
    TX, TY = np.meshgrid(cx + np.arange(tnx) * tray_cell, cy + np.arange(tny) * tray_cell)
    t = math.tan(math.radians(slope))
    tbed = (TX - tx0) * t + 0.4 * np.abs(TY - S_DRAIN[1]) * t
    drain = np.zeros_like(tbed)
    dx, dy, r = S_DRAIN
    hole = (TX - dx) ** 2 + (TY - dy) ** 2 <= (r + tray_cell / 2) ** 2
    drain[hole] = math.pi * r * r / hole.sum()
    tray = L.Chart("tray", tbed, tray_cell, cx, cy, open_edges=False, drain=drain)
    frames = seconds * FPS
    tt = np.arange(frames + 2) / FPS
    m = L.still(frames + 2)
    m[:, 0, 3] = np.clip(tt - 3.0, 0, 0.4) * 0.15 - np.clip(tt - 4.4, 0, 0.4) * 0.15
    m[:, 2, 3] = S_PLATE_Z

    def pours(f):
        p, q, a_, b_ = S_JET
        return [L.Pour(p, q)] if a_ <= f / FPS < b_ else []

    sim = L.Liquid([plate, tray], [m, L.still(frames + 2)], FPS, floor_z=-0.05, helpers=helpers)
    out, secs = run(sim, frames - 1, pours=pours)
    sim.close()
    return [fr.totals for fr in out], secs, plate.bed.size + tray.bed.size


if __name__ == "__main__":
    main()
