"""The coolant liquid's six stand-alone checks (study 0251's T1–T6, task 0347 D) as data the app can run. No Blender.

Each **case** is a small invented rig of height-field charts (``core/liquid.py``): its charts, the world-from-chart
matrices of every frame, what is poured in (as a function of the frame), what is filled in before the run, the number
of frames (24 fps) and the case's **number** worked out from the run – the same numbers ``tests/test_liquid.py``
checks (``tests/liquid_scenes.py`` builds its tests from here):

1. ``pocket`` – a closed pocket fills and holds its volume (within 2 %),
2. ``slot``   – an open slot drains at its end (< 15 % left, half gone < 1 s after the pour stops),
3. ``tilt``   – a plate tilted 0 -> 30° spills at atan(d / w) (within 1.5°),
4. ``tray``   – a sloped tray empties down its drain (95 % within 30 s after the pour stops),
5. ``slosh``  – a box stopped hard sloshes at its period 2L / sqrt(g h) (within 0.1 s),
6. ``wall``   – nothing leaks through a one-cell wall (0.000 cm³).

``offset`` moves a whole rig (charts, pours, floor) in the world, so the six can stand side by side in one scene
(``lab``); the liquid does the same in every place (only the rounding of the last bits can differ).

Use::

    for case in lab():
        sim = case.liquid()
        for fr in case.steps(sim):
            ...                         # sim.depth(c), fr.drops: the state at frame fr.frame
        res = case.result(sim)          # the numbers; case.number(res) -> (value, within its limit, plain text)
        sim.close()
"""

from __future__ import annotations

import math

import numpy as np

from . import liquid as L

MM = 1e-3
FPS = 24
GAP = 0.3                       # m between two rigs of the lab
IDS = ("pocket", "slot", "tilt", "tray", "slosh", "wall")


def lmin(q_m3_s):
    """m^3/s -> l/min."""
    return q_m3_s * 1000.0 * 60.0


def balance(sim):
    """(|poured - everything held|, the totals) in litres."""
    t = sim.totals()
    held = t["on_charts"] + t["in_flight"] + t["drained"] + t["floor"]
    return abs(held - t["poured"]), t


class Case:
    """One rig. Subclasses set the class fields and ``_build`` (charts, matrices in the rig's own frame)."""
    id = ""
    title = ""
    limit = ""                  # the check's limit, in plain words
    frames = 0                  # the run goes from frame 0 to this frame
    floor_z = -0.3              # the floor in the rig's own frame (m): what falls below it is gone
    best = 0                    # the frame that shows the case best (0 … frames)

    def __init__(self, offset=(0.0, 0.0, 0.0)):
        self.offset = np.asarray(offset, float).reshape(3)
        self.charts, local = self._build()
        self.mats = []
        for m in local:
            m = np.array(m, float)
            m[:, :3, 3] += self.offset
            self.mats.append(m)
        self.fills = {}
        self._reset()

    # --- what a subclass gives ---------------------------------------------------------------------------------
    def _build(self):
        raise NotImplementedError

    def _pours(self, f):
        """The pours during the step from frame f, in the rig's own frame (world jets)."""
        return []

    def _reset(self):
        pass

    def see_frame(self, sim, fr):
        """Called after every frame of the run (the case keeps what its number needs)."""

    def result(self, sim) -> dict:
        raise NotImplementedError

    def number(self, res) -> tuple:
        """(the value, True when it is within the limit, a short text)."""
        raise NotImplementedError

    # --- running -------------------------------------------------------------------------------------------------
    @property
    def world_floor(self) -> float:
        return self.floor_z + float(self.offset[2])

    def pours(self, f):
        """The pours during the step from frame f, placed with the rig."""
        out = []
        for p in self._pours(f):
            if p.chart is None:
                pt = tuple(float(a) + float(b) for a, b in zip(p.point, self.offset))
                p = L.Pour(pt, p.rate, p.direction, None, p.radius)
            out.append(p)
        return out

    def liquid(self, helpers=0, hold=True) -> L.Liquid:
        """A new solver for this case with its fills put in (the case's own numbers start afresh)."""
        self._reset()
        sim = L.Liquid(self.charts, self.mats, FPS, floor_z=self.world_floor, helpers=helpers, hold=hold)
        for c, d in self.fills.items():
            sim.fill(c, d)
        self.v0 = [sim.volume(c) for c in range(len(self.charts))]
        return sim

    def steps(self, sim):
        """Run the case: yields every frame 1 … ``frames`` (``core.liquid.Frame``) after the case has seen it."""
        for fr in sim.run(0, self.frames, pours=self.pours):
            self.see_frame(sim, fr)
            yield fr

    def run(self, helpers=0, hold=True):
        """The whole run at once: (numbers, frames)."""
        sim = self.liquid(helpers, hold)
        try:
            frames = list(self.steps(sim))
            res = self.result(sim)
        finally:
            sim.close()
        return res, frames

    # --- where it stands -------------------------------------------------------------------------------------------
    def corners(self, c) -> np.ndarray:
        """The 4 corners of chart c (its cells' outer edges) in the chart's frame, z = 0."""
        ch = self.charts[c]
        ny, nx = ch.shape
        h = ch.cell / 2
        xs = (ch.x0 - h, ch.x0 + (nx - 1) * ch.cell + h)
        ys = (ch.y0 - h, ch.y0 + (ny - 1) * ch.cell + h)
        return np.array([(x, y, 0.0) for x in xs for y in ys])

    def box(self) -> tuple:
        """(lo, hi) world box the rig's charts sweep over the whole run (beds' heights included)."""
        lo = np.full(3, np.inf)
        hi = np.full(3, -np.inf)
        for c, ch in enumerate(self.charts):
            p = self.corners(c)
            b = ch.bed[np.isfinite(ch.bed)]
            pts = np.concatenate([p + (0, 0, float(b.min())), p + (0, 0, float(b.max()))])
            M = self.mats[c]
            w = np.einsum("fij,pj->fpi", M[:, :3, :3], pts) + M[:, None, :3, 3]
            lo = np.minimum(lo, w.reshape(-1, 3).min(0))
            hi = np.maximum(hi, w.reshape(-1, 3).max(0))
        return lo, hi


# ---------------------------------------------------------------------------------------------------------------
# the six cases
# ---------------------------------------------------------------------------------------------------------------

class Pocket(Case):
    """T1: a closed pocket 40 x 40 x 8 mm in a 100 mm plate, filled from a jet for 2 s with twice its volume."""
    id = "pocket"
    title = "Liquid: closed pocket"
    limit = "held within 2 % of the pocket's volume"
    frames = 14 * FPS
    floor_z = -0.2
    best = 18                   # (0.75 s: the pocket three quarters full under the jet)
    PK = (slice(30, 70), slice(30, 70))
    V = 40 * MM * 40 * MM * 8 * MM

    def _build(self):
        bed = np.zeros((100, 100))
        bed[self.PK] = -8 * MM
        return [L.Chart("plate", bed, 1 * MM, -50 * MM, -50 * MM)], [L.still(14 * FPS + 2)]

    def _pours(self, f):
        q = 2 * self.V / 2.0
        return [L.Pour((0.0, 0.0, 0.03), lmin(q))] if f < 2 * FPS else []

    def result(self, sim):
        d = sim.depth(0)
        held = float(np.minimum(d[self.PK], 8 * MM + L.FILM).sum() * MM * MM)
        err, t = balance(sim)
        return dict(pocket_cm3=self.V * 1e6, poured_cm3=t["poured"] * 1e3, held_cm3=held * 1e6,
                    error_pct=100 * (held - self.V) / self.V, ran_off_cm3=t["floor"] * 1e3, balance_l=err)

    def number(self, res):
        v = res["error_pct"]
        return v, abs(v) <= 2.0, (f"{res['held_cm3']:.2f} cm³ held of the pocket's {res['pocket_cm3']:.2f} cm³ "
                                  f"({v:+.1f} %; limit ±2 %)")


class Slot(Case):
    """T2: an open slot 10 wide, 6 deep, 90 long, open at its +x end; poured into for 2 s."""
    id = "slot"
    title = "Liquid: open slot drains"
    limit = "< 15 % left, half gone < 1 s after the pour stops"
    frames = 12 * FPS
    floor_z = -0.2
    best = 2 * FPS
    V = 10 * MM * 90 * MM * 6 * MM

    def _build(self):
        bed = np.zeros((40, 100))
        bed[15:25, 0:90] = -6 * MM
        return [L.Chart("plate", bed, 1 * MM, -50 * MM, -20 * MM)], [L.still(12 * FPS + 2)]

    def _pours(self, f):
        return [L.Pour((30 * MM, 0.0, 0.03), lmin(self.V / 2.0))] if f < 2 * FPS else []

    def _reset(self):
        self.vols = []

    def see_frame(self, sim, fr):
        self.vols.append(fr.totals["on_charts"])

    def result(self, sim):
        vols = self.vols
        stop = 2 * FPS - 1
        peak = max(vols[: stop + 1])
        half = next((k for k in range(stop, len(vols)) if vols[k] < 0.5 * peak), None)
        err, t = balance(sim)
        return dict(slot_cm3=self.V * 1e6, poured_cm3=t["poured"] * 1e3, peak_cm3=peak * 1e3, left_cm3=vols[-1] * 1e3,
                    left_pct=100 * vols[-1] / t["poured"], half_s=None if half is None else (half - stop) / FPS,
                    balance_l=err)

    def number(self, res):
        v, h = res["left_pct"], res["half_s"]
        ok = v < 15.0 and h is not None and h < 1.0
        hs = "never" if h is None else f"{h:.2f} s"
        return v, ok, f"{v:.1f} % left, half gone {hs} after the pour stops (limits 15 %, 1 s)"


def left_at(deg, width_mm, depth_mm):
    """The cross-section (m^2) a pocket of this width and depth still holds when tilted by ``deg``."""
    t = math.tan(math.radians(deg))
    W, D = width_mm * MM, depth_mm * MM
    if W * t <= D:
        return W * D - 0.5 * W * W * t
    return 0.5 * D * D / t


class Tilt(Case):
    """T3: a pocket 40 wide, 10 deep, half full, tilted from 0 to 30° over 10 s (from 1 s on)."""
    id = "tilt"
    title = "Liquid: tilted plate spills"
    limit = "spills at atan(5 / 20) = 14.0° ± 1.5°"
    frames = 12 * FPS
    floor_z = -0.3
    best = int(6.5 * FPS)
    PK = (slice(20, 60), slice(20, 60))

    def _build(self):
        bed = np.zeros((80, 80))
        bed[self.PK] = -10 * MM
        n = self.frames + 2
        self.ang = np.radians(np.clip((np.arange(n) / FPS - 1.0) / 10.0, 0, 1) * 30.0)
        mats = np.stack([L.rot_y(a) for a in self.ang])
        fill = np.zeros_like(bed)
        fill[self.PK] = 5 * MM
        self._fill = fill
        return [L.Chart("plate", bed, 1 * MM, -40 * MM, -40 * MM)], [mats]

    def __init__(self, offset=(0.0, 0.0, 0.0)):
        super().__init__(offset)
        self.fills = {0: self._fill}

    def _reset(self):
        self.vols = []
        self.spill = None

    def see_frame(self, sim, fr):
        v0 = float(self._fill.sum()) * MM * MM
        self.vols.append(float(sim.depth(0)[self.PK].sum() * MM * MM))
        if self.spill is None and self.vols[-1] < 0.99 * v0:
            self.spill = math.degrees(self.ang[fr.frame])

    def result(self, sim):
        expect = math.degrees(math.atan((10 - 5) / 20.0))
        err, t = balance(sim)
        return dict(expected_deg=expect, spilled_at_deg=self.spill,
                    error_deg=None if self.spill is None else self.spill - expect,
                    left_at_30deg_cm3=self.vols[-1] * 1e6,
                    expected_left_at_30deg_cm3=left_at(30, 40, 10) * 40 * MM * 1e6, balance_l=err)

    def number(self, res):
        if res["spilled_at_deg"] is None:
            return None, False, "it never spilled"
        e = res["error_deg"]
        return res["spilled_at_deg"], abs(e) <= 1.5, (f"spilled at {res['spilled_at_deg']:.1f}° (expected "
                                                      f"{res['expected_deg']:.1f}° ± 1.5°)")


class Tray(Case):
    """T4: a tray 400 x 300 mm with walls, 2° down to a Ø20 drain at its -x end and a V towards its middle; 2 l/min
    for 10 s."""
    id = "tray"
    title = "Liquid: tray runs to its drain"
    limit = "95 % gone within 30 s after the pour stops"
    frames = 40 * FPS
    floor_z = -0.3
    best = 8 * FPS

    def _build(self):
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
        return [ch], [L.still(40 * FPS + 2)]

    def _pours(self, f):
        q = 2.0 / 1000 / 60
        return [L.Pour((300 * MM, 150 * MM, 0.05), lmin(q))] if f < 10 * FPS else []

    def _reset(self):
        self.vols = []
        self.last = None

    def see_frame(self, sim, fr):
        self.vols.append(fr.totals["on_charts"] + fr.totals["in_flight"])
        self.last = fr

    def result(self, sim):
        vols = self.vols
        stop = 10 * FPS - 1
        poured = self.last.totals["poured"]
        empty = next((k for k in range(stop, len(vols)) if vols[k] < 0.05 * poured), None)
        err, t = balance(sim)
        return dict(poured_l=poured, drained_l=t["drained"], peak_in_tray_cm3=max(vols) * 1e3,
                    empty_95pct_s_after_stop=None if empty is None else (empty - stop) / FPS,
                    left_cm3=vols[-1] * 1e3, balance_l=err)

    def number(self, res):
        v = res["empty_95pct_s_after_stop"]
        if v is None:
            return None, False, "not 95 % gone by the end"
        return v, v <= 30.0, f"95 % gone {v:.1f} s after the pour stops (limit 30 s)"


class Slosh(Case):
    """T5: a closed box 200 x 50 mm with 10 mm of liquid, moved at ``speed`` m/s and stopped hard at 0.5 s."""
    id = "slosh"
    title = "Liquid: box stopped sloshes"
    limit = "period within 0.1 s of 2L / sqrt(g h)"
    frames = 10 * FPS
    floor_z = -0.3
    best = 20

    def __init__(self, offset=(0.0, 0.0, 0.0), speed=0.25):
        self.speed = speed
        super().__init__(offset)
        self.fills = {0: np.full(self.charts[0].shape, 10 * MM)}

    def _build(self):
        cell = 2 * MM
        bed = np.zeros((25, 100))
        ch = L.Chart("box", bed, cell, 0.0, 0.0, open_edges=False)
        n = self.frames + 2
        t = np.arange(n) / FPS
        mats = L.still(n)
        mats[:, 0, 3] = np.minimum(t, 0.5) * self.speed
        return [ch], [mats]

    def _reset(self):
        self.end = []

    def see_frame(self, sim, fr):
        self.end.append(float(sim.depth(0)[:, -3:].mean()))

    def result(self, sim):
        e = np.array(self.end) - 10 * MM
        after = int(0.55 * FPS)
        s = e[after:] - e[after:].mean()
        F = np.abs(np.fft.rfft(s * np.hanning(len(s)), 8192))
        fr_ = np.fft.rfftfreq(8192, 1 / FPS)
        period = float(1 / fr_[F[1:].argmax() + 1])
        first = float(np.max(np.abs(e[after:after + 2 * FPS])))
        late = float(np.max(np.abs(e[after + 5 * FPS:after + 6 * FPS])))
        expect = 2 * 0.2 / math.sqrt(L.G * 0.01)
        v0 = self.v0[0]
        return dict(expected_period_s=expect, period_s=period, first_wave_mm=first * 1e3, after_5s_mm=late * 1e3,
                    volume_change=abs(sim.volume(0) - v0) / v0)

    def number(self, res):
        v = res["period_s"]
        return v, abs(v - res["expected_period_s"]) < 0.1, (f"sloshes every {v:.2f} s (expected "
                                                            f"{res['expected_period_s']:.2f} s ± 0.1 s)")


class Wall(Case):
    """T6: a closed tank 120 x 40 mm, a wall one cell thick (20 mm high) across its middle, 8 mm of liquid on one side,
    rocked ±12° with a period of 2 s."""
    id = "wall"
    title = "Liquid: no leak through a wall"
    limit = "0.000 cm³ behind the wall"
    frames = 10 * FPS
    floor_z = -0.3
    best = 12

    def __init__(self, offset=(0.0, 0.0, 0.0)):
        super().__init__(offset)
        fill = np.zeros(self.charts[0].shape)
        fill[:, :60] = 8 * MM
        self.fills = {0: fill}

    def _build(self):
        cell = 1 * MM
        bed = np.zeros((40, 120))
        bed[:, 60] = 20 * MM
        ch = L.Chart("tank", bed, cell, 0.0, 0.0, open_edges=False)
        n = self.frames + 2
        ang = np.radians(12 * np.sin(np.arange(n) / FPS * 2 * math.pi / 2.0))
        return [ch], [np.stack([L.rot_y(a) for a in ang])]

    def _reset(self):
        self.worst = 0.0

    def see_frame(self, sim, fr):
        self.worst = max(self.worst, float(sim.depth(0)[:, 61:].sum() * MM * MM))

    def result(self, sim):
        v0 = self.v0[0]
        return dict(worst_behind_wall_cm3=self.worst * 1e6, volume_change=abs(sim.volume(0) - v0) / v0)

    def number(self, res):
        v = res["worst_behind_wall_cm3"]
        return v, v == 0.0, f"{v:.3f} cm³ ever behind the wall (limit 0.000)"


CASES = {c.id: c for c in (Pocket, Slot, Tilt, Tray, Slosh, Wall)}


def case(case_id: str, offset=(0.0, 0.0, 0.0), **kw) -> Case:
    return CASES[case_id](offset, **kw)


def lab(gap: float = GAP) -> list:
    """The six rigs side by side along x (``gap`` m between their boxes), centred on y = 0, each lifted so its floor
    is the world's z = 0."""
    out = []
    x = 0.0
    for cid in IDS:
        c = CASES[cid]()
        lo, hi = c.box()
        off = (x - lo[0], -(lo[1] + hi[1]) / 2, -c.floor_z)
        out.append(CASES[cid](off))
        x += (hi[0] - lo[0]) + gap
    return out
