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
from fresing_render.core import liquid_lab as LAB  # noqa: E402

MM = 1e-3
FPS = 24


lmin = LAB.lmin
balance = LAB.balance


def run(sim, frames, pours=None, tool=None, push=None, each=None):
    t0 = time.perf_counter()
    out = []
    for fr in sim.run(0, frames, pours=pours, tool=tool, push=push):
        out.append(fr)
        if each:
            each(fr)
    return out, time.perf_counter() - t0


# --- study 0251's six stand-alone tests: the rigs live in core/liquid_lab.py (the test tour shows them too) -------
def _timed(case, helpers=0, hold=True):
    sim = case.liquid(helpers, hold)
    t0 = time.perf_counter()
    frames = list(case.steps(sim))
    secs = time.perf_counter() - t0
    return sim, frames, secs


# --- T1 a closed pocket fills to its volume and holds it ---------------------------------------------------------
def t1_pocket(helpers=0, hold=True):
    c = LAB.case("pocket")
    sim, frames, secs = _timed(c, helpers, hold)
    res = c.result(sim)
    res.update(seconds=secs, frames=len(frames), settled_frames=sum(fr.settled for fr in frames))
    d = sim.depth(0).copy()
    sim.close()
    return res, frames, d


def _plain(case_id, helpers=0, **kw):
    c = LAB.case(case_id, **kw)
    sim, frames, secs = _timed(c, helpers)
    res = c.result(sim)
    res["seconds"] = secs
    if case_id == "tray":
        res["settled_frames"] = sum(fr.settled for fr in frames)
    sim.close()
    return res


# --- T2 an open slot drains out at its end ---------------------------------------------------------------------
def t2_slot(helpers=0):
    return _plain("slot", helpers)


_left_at = LAB.left_at


# --- T3 a plate tilted 0 -> 30 deg spills at the right angle ----------------------------------------------------
def t3_tilt(helpers=0):
    return _plain("tilt", helpers)


# --- T4 a tray with a slope empties down its drain ----------------------------------------------------------------
def t4_tray(helpers=0):
    return _plain("tray", helpers)


# --- T5 a box moved and stopped hard sloshes and settles ----------------------------------------------------------
def t5_slosh(helpers=0, speed=0.25):
    return _plain("slosh", helpers, speed=speed)


# --- T6 nothing leaks through a wall --------------------------------------------------------------------------------
def t6_wall(helpers=0):
    return _plain("wall", helpers)


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
