"""Coolant liquid on the machine: a shallow-liquid height field (task 0255, study 0251 method a). No Blender here.

What it is
----------
The liquid lives on **charts**: a regular grid of cells laid over one surface (the cut part's top, the table, the chip
tray), in that surface's own frame, which rides with its carrier (the table, the cradle, the 4th axis' bar). Each cell
has a bed height (the surface) and a liquid depth. Between neighbouring cells flows a signed flux (the "virtual pipe"
model, O'Brien & Hodgins 1995, Mei et al. 2007, with the pipe's area = the depth on the face, so waves travel at
sqrt(g h) as in the shallow-water equations), braked by laminar wall friction 3 nu / h^2 and a Stokes-layer term
(a film on a slope runs off at the Nusselt rate, a slosh settles like water). Over a step down the flux is capped at
critical flow (else rings of waves at every rim). A film of 0.04 mm stays where liquid was (it does not flow).

Moving with the machine: every cell feels the **effective gravity** g - a (a = the cell's world acceleration, from three
places of its carrier's matrix), turned into the chart's frame. Its normal part presses the liquid onto the surface,
its tangential part drives it (a table that stops hard throws the liquid forward; a tilted cradle runs it to its low
side; a turning table flings it outwards). Where the normal part points away from the surface (upside down) the
liquid drips off.

Liquid that leaves a chart (over an open edge, or dripping off) becomes **drops** that fly (ballistic, world space)
and land on the first chart they meet or on the floor. **Drains** are orifices: Q = Cd a sqrt(2 g h). **Pours** add
liquid (a jet falling from a nozzle onto whatever lies under it, or straight onto a chart). The **spinning tool**
throws the liquid it touches off as drops, at about its surface speed, and turns the liquid round it. A **push** per
cell (m/s^2 along the chart) is the door for the air blast later.

Volume bookkeeping is exact: poured = on the charts + in flight + drained + on the floor (to rounding, ~1e-15).

Speed (the brief asks for a 10-minute program in minutes)
---------------------------------------------------------
* The charts are cut into **tiles** (32 x 32 cells). A frame steps only the tiles where something moves, and every tile
  next to one. A dry tile is skipped exactly (it would not change). A tile whose liquid has come to rest (over a whole
  frame every depth changed < 1 um and every speed < 1 mm/s) is **settled**: held still until something wakes it
  (liquid or drops arrive, the carrier accelerates, a push or the tool reaches it). Faces between a stepped and a held
  tile are closed for the frame. That is the only approximation the skipping adds.
* Every sub-step works on **windows** (a run of tiles + 2 cells all round) with element-wise NumPy operations only
  (+ - * / sqrt min max; no powers, no sums): every cell's result is the same bit for bit whichever window or helper
  process computes it. So the result does not depend on the skipping of dry tiles or on the number of helpers
  (``core/liquid_pool.py``: helper processes on shared memory).

Units: metres, seconds, m^3 inside; litres and l/min at the edges (``Pour.rate``, ``Frame.totals``). Frames: the caller
numbers them; ``mats[c][f]`` is chart c's world-from-chart matrix at frame f.

Use (task B hangs this on the machine)::

    charts = [Chart("table", bed, 0.002, x0, y0), Chart("tray", tbed, 0.002, ..., open_edges=False, drain=area)]
    sim = Liquid(charts, mats, fps=24, floor_z=-0.5, helpers=4)
    for fr in sim.run(0, frames - 1, pours=lambda f: [Pour(nozzle, 3.0)], tool=lambda f: Tool(...)):
        cache.add(fr.frame, [sim.depth(c) for c in range(len(charts))], fr.drops, fr.totals)
    sim.close()
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

G = 9.81
NU = 1.0e-6            # kinematic viscosity of a water-based emulsion, m^2/s
FILM = 0.04e-3         # this much stays on a wetted surface (it does not flow; the wet sheen shows it)
STOKES = math.sqrt(NU * 2 * math.pi)   # the wall's boundary layer in an oscillating flow (Stokes layer at ~1 Hz)
WEIR = 1.5             # critical flow over a step: q = 1.5 sqrt(g) h^1.5 per metre of edge
CD = 0.62              # orifice discharge coefficient (sharp-edged hole)
HMIN = 2e-5            # the friction's depth never below this (m)
DRIP_TIME = 0.15       # s: upside-down liquid drips off within about this
CFL = 0.6             # sub-step = CFL x cell / wave speed
TILE = 32              # cells per tile side
_FR_A = 3.0 * NU       # laminar friction 3 nu / h^2 ...
_FR_B = STOKES         # ... + the Stokes layer's STOKES / h (both x dt in the kernel)
SETTLE_DEPTH = 1e-6    # m: a tile is at rest when no depth changed more than this over a frame ...
SETTLE_SPEED = 1e-3    # m/s: ... and nothing moves faster than this
GRAVITY_TOL = 1e-3     # m/s^2: the effective gravity "changed" (float32 matrices give ~1e-4 of noise)
JET_R = 5e-3           # a jet's impact zone (m)
DROP_R = 1.5e-3        # a drop's splash (m)
FLIGHT_STEPS = 4       # drops fly a frame in this many pieces (gravity), each piece checked along its line
# the spinning tool
TOOL_VMAX = 6.0        # m/s: liquid leaves the tool at its surface speed, at most this (a D10 at 10,000 rpm: 5.2 m/s)
TOOL_TAU = 0.05        # s: the liquid the tool touches is thrown off within about this (at >= 1 m/s)
TOOL_GAP = 0.5e-3      # m: liquid this far below the tool's tip is still touched
TOOL_OUT = 0.25        # outward share of the thrown drops' speed
TOOL_UP = 0.10         # share up the flutes
TOOL_RING = 3.0        # the swirl reaches out to this many tool radii
SWIRL_SHARE = 0.3      # the swirl's speed at the tool's surface, as a share of the tool's surface speed ...
SWIRL_VMAX = 1.0       # ... at most this (m/s); it falls off as R / r
SWIRL_TIME = 0.3       # s: the time the swirl takes to spin a pool up (tangential push = speed / this)
SWIRL_AT_MAX = 4.0     # m/s^2: tangential push at most
SWIRL_AR_MAX = 2.0     # m/s^2: outward push (the pool climbs the walls) at most


# ---------------------------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------------------------

@dataclass
class Chart:
    """A grid of cells on one surface, in the surface's (carrier's) frame.

    ``bed``: (ny, nx) surface heights (m) at the cell centres, NaN = no surface there (an open edge: liquid leaves).
    Cell (j, i) has its centre at (x0 + i * cell, y0 + j * cell). ``open_edges``: liquid runs off where the surface
    ends (False: a tray with walls). ``drain``: (ny, nx) orifice area per cell (m^2), or None. ``catches``: drops and
    jets landing on it stay on it."""
    name: str
    bed: np.ndarray
    cell: float
    x0: float = 0.0
    y0: float = 0.0
    open_edges: bool = True
    drain: np.ndarray | None = None
    catches: bool = True

    def __post_init__(self):
        self.bed = np.array(self.bed, float)
        if self.bed.ndim != 2 or min(self.bed.shape) < 1:
            raise ValueError("a chart's bed is a 2-D grid")
        if not self.cell > 0:
            raise ValueError("a chart's cell size must be > 0")
        if self.drain is not None:
            self.drain = np.array(self.drain, float)
            if self.drain.shape != self.bed.shape:
                raise ValueError("the drain grid must have the bed's shape")

    @property
    def shape(self):
        return self.bed.shape


@dataclass
class Pour:
    """Liquid poured in during a frame: ``rate`` in l/min.

    World jet (``chart`` None): from ``point`` (world, m) along ``direction`` (default straight down) onto the first
    catching surface on its line (the floor if none). On a chart (``chart`` = its index): ``point`` = (x, y) in the
    chart's frame. Either way spread over a disc of ``radius`` where it lands."""
    point: tuple
    rate: float
    direction: tuple = (0.0, 0.0, -1.0)
    chart: int | None = None
    radius: float = JET_R


@dataclass
class Tool:
    """The milling bit during a frame: a cylinder from ``tip`` (world, m) along ``axis`` (world, pointing from the tip
    up the shank) of ``radius`` and ``flute`` length (m). ``rpm`` > 0 = M3 (clockwise seen from the spindle), < 0 = M4,
    0 = the spindle stands (the tool does nothing)."""
    tip: tuple
    axis: tuple
    radius: float
    flute: float
    rpm: float

    def omega(self) -> np.ndarray:
        """The angular velocity vector (rad/s, world): M3 turns clockwise seen from the spindle = -axis."""
        a = np.asarray(self.axis, float)
        a = a / max(float(np.linalg.norm(a)), 1e-300)
        return -float(self.rpm) * 2.0 * math.pi / 60.0 * a

    def surface_speed(self) -> float:
        """The speed liquid leaves the tool at (m/s): its surface speed, at most ``TOOL_VMAX``."""
        return min(abs(float(self.rpm)) * 2.0 * math.pi / 60.0 * float(self.radius), TOOL_VMAX)


def stress_push(stress, depth, density=1000.0):
    """A surface stress (Pa, e.g. the air's wall jet dragging the liquid's top) as the push the solver takes (m/s^2):
    a = stress / (density x depth). Where there is no liquid: 0."""
    depth = np.asarray(depth, float)
    return np.where(depth > FILM, np.asarray(stress, float) / (density * np.maximum(depth, FILM)), 0.0)


@dataclass
class Frame:
    """What one step gives: the state at ``frame``.

    ``drops``: (n, 3) places (world, m), ``drop_v`` (n, 3) velocities (m/s), ``drop_vol`` (n,) litres.
    ``totals`` (litres): poured, on_charts, in_flight, drained, floor; ``thrown`` (litres): what the tool threw off
    in this frame (it is in flight or landed again: not a separate pot). ``stepped`` cells stepped per chart,
    ``substeps`` per chart, ``held`` tiles held at rest per chart."""
    frame: int
    drops: np.ndarray
    drop_v: np.ndarray
    drop_vol: np.ndarray
    totals: dict
    thrown: float = 0.0
    stepped: list = field(default_factory=list)
    substeps: list = field(default_factory=list)
    held: list = field(default_factory=list)

    @property
    def settled(self) -> bool:
        """Nothing was stepped in this frame (every chart dry or at rest)."""
        return not any(self.stepped)


# ---------------------------------------------------------------------------------------------------------------
# the arrays of a chart and the kernel (shared by the master and the helper processes)
# ---------------------------------------------------------------------------------------------------------------

# name, shape kind ('c' cells, 'x' x-faces, 'y' y-faces), dtype
ARRAYS = (
    ("valid", "c", "f8"), ("bed0", "c", "f8"), ("cz", "c", "f8"), ("drain", "c", "f8"),
    ("wlx", "x", "f8"), ("wrx", "x", "f8"), ("bx", "x", "f8"), ("olx", "x", "f8"), ("orx", "x", "f8"),
    ("wly", "y", "f8"), ("wry", "y", "f8"), ("by", "y", "f8"), ("oly", "y", "f8"), ("ory", "y", "f8"),
    ("frozen", "c", "f8"), ("rain", "c", "f8"), ("px", "c", "f8"), ("py", "c", "f8"),
    ("d0", "c", "f8"), ("d1", "c", "f8"), ("qx0", "x", "f8"), ("qx1", "x", "f8"), ("qy0", "y", "f8"), ("qy1", "y", "f8"),
    ("lost", "c", "f8"), ("dripped", "c", "f8"), ("drained", "c", "f8"),
)


def array_shape(kind, NY, NX):
    return {"c": (NY, NX), "x": (NY, NX - 1), "y": (NY - 1, NX)}[kind]


def tile_box(tj, ti, NY, NX, T=TILE):
    return tj * T, min((tj + 1) * T, NY), ti * T, min((ti + 1) * T, NX)


class Kernel:
    """Steps windows of one chart. ``A``: dict of the chart's arrays (plain or shared memory), ``meta``: cell, NY, NX,
    xs, ys (cell centre coordinates of the padded grid). Used in the master and in every helper."""

    def __init__(self, A, meta):
        self.A = A
        self.l = float(meta["cell"])
        self.NY, self.NX = int(meta["NY"]), int(meta["NX"])
        self.xs = np.asarray(meta["xs"], float)
        self.ys = np.asarray(meta["ys"], float)
        cap = meta.get("wave_depth")
        self.cap = float(cap) if cap else None      # (task 0346) the faces' depth for the waves at most this
        self.runs = []
        self.cache = []
        self.start = []

    # --- a frame -----------------------------------------------------------------------------------------------
    def frame(self, runs, n, dt, gc, gb, uniform, push, rain):
        """Set up a frame: ``runs`` = list of (r0, r1, c0, c1) cores (cells); gravity g_local(p) = gc + gb @ p.

        Bit-for-bit rule: within one chart and frame every face and cell is worked out with the same formula in every
        window. Terms a window leaves out are exact zeros or ones there (x + 0 = x, x * 1 = x)."""
        A, l = self.A, self.l
        self.runs = runs
        self.n = n
        self.dt = dt
        self.uniform = bool(uniform)
        self.cache = []
        self.start = []
        g = np.asarray(gc, float)
        B = np.asarray(gb, float)
        dtl = dt * l
        for r0, r1, c0, c1 in runs:
            R0, R1, C0, C1 = max(r0 - 2, 0), min(r1 + 2, self.NY), max(c0 - 2, 0), min(c1 + 2, self.NX)
            w = (slice(R0, R1), slice(C0, C1))
            wx = (slice(R0, R1), slice(C0, C1 - 1))
            wy = (slice(R0, R1 - 1), slice(C0, C1))
            fz = A["frozen"][w]
            if fz.any():
                fx = (1.0 - fz[:, :-1]) * (1.0 - fz[:, 1:])
                fy = (1.0 - fz[:-1, :]) * (1.0 - fz[1:, :])
            else:
                fx = fy = None
            if uniform:
                gx, gy, gn = g[0], g[1], -g[2]
            else:
                X = self.xs[C0:C1][None, :]
                Y = self.ys[R0:R1][:, None]
                Z = A["cz"][w]
                gx = g[0] + B[0, 0] * X + B[0, 1] * Y + B[0, 2] * Z
                gy = g[1] + B[1, 0] * X + B[1, 1] * Y + B[1, 2] * Z
                gn = -(g[2] + B[2, 0] * X + B[2, 1] * Y + B[2, 2] * Z)
            # the weir's gravity (task 0347): the pressing one, or the sliding one where that is larger – a chart
            # turned on its side (the 4th axis' bar) has almost no pressing gravity, and capped by it nothing could
            # run along it: the flood stood 3-4 cm high there. Up to 45 deg of tilt nothing changes.
            gwq = np.maximum(np.maximum(gn, 0.0), np.sqrt(gx * gx + gy * gy))
            if push:
                gx = gx + A["px"][w]
                gy = gy + A["py"][w]
            gnp = np.maximum(gn, 0.0)
            # per face: the pressing gravity / cell (x dt l), the driving gravity (x dt l), the weir's factor
            if uniform:
                a_x = a_y = float(gnp) * (1.0 / l) * dtl
                gq = WEIR * l * math.sqrt(float(gwq))
                gq_x = gq_y = None
            else:
                a_x = 0.5 * (gnp[:, :-1] + gnp[:, 1:]) * (1.0 / l) * dtl
                a_y = 0.5 * (gnp[:-1, :] + gnp[1:, :]) * (1.0 / l) * dtl
                gq_x = (WEIR * l) * np.sqrt(0.5 * (gwq[:, :-1] + gwq[:, 1:]))
                gq_y = (WEIR * l) * np.sqrt(0.5 * (gwq[:-1, :] + gwq[1:, :]))
                gq = None
            b_x = (gx * dtl) if np.ndim(gx) == 0 else 0.5 * (gx[:, :-1] + gx[:, 1:]) * dtl
            b_y = (gy * dtl) if np.ndim(gy) == 0 else 0.5 * (gy[:-1, :] + gy[1:, :]) * dtl
            valid = A["valid"][w]
            all_valid = bool(valid.all())
            down = (np.broadcast_to(gn, valid.shape) <= 0.05 * G) & (valid > 0)
            down = down.astype(float) if down.any() else None
            dr = A["drain"][w]
            dcoef = (CD * dr * np.sqrt(2.0 * np.broadcast_to(gnp, dr.shape))) if dr.any() else None
            rn = A["rain"][w]
            rsub = (rn / n) if rain and rn.any() else None
            face = {}
            for ax, sl, f_ in (("x", wx, fx), ("y", wy, fy)):
                wl, wr, both, ol, orr = (A[k + ax][sl] for k in ("wl", "wr", "b", "ol", "or"))
                opn = both + ol + orr
                if f_ is not None:
                    wl, wr, opn = wl * f_, wr * f_, opn * f_
                face[ax] = dict(wl=wl, wr=wr, both=None if both.all() else both,
                                ol=ol if ol.any() else None, orr=orr if orr.any() else None,
                                opn=None if opn.all() else opn)
            h, wdt = R1 - R0, C1 - C0
            self.cache.append(dict(
                win=(R0, R1, C0, C1), core=(r0, r1, c0, c1), valid=None if all_valid else valid, bed0=A["bed0"][w],
                crest=self._crest(A["cz"][w], a_x, a_y, b_x, b_y, l),
                fx=face["x"], fy=face["y"], a_x=a_x, a_y=a_y, b_x=b_x, b_y=b_y, gq=gq, gq_x=gq_x, gq_y=gq_y,
                down=down, dcoef=dcoef, rsub=rsub,
                buf=dict(out=np.empty((h, wdt)), dd=np.empty((h, wdt)), lost=np.empty((h, wdt)))))
            self.start.append(np.array(A["d0"][r0:r1, c0:c1]))

    @staticmethod
    def _crest(cz, a_x, a_y, b_x, b_y, l):
        """(task 0346) The crest each face's outflow must rise over, from either side: the higher bed, less / more
        the half cell the liquid's surface rises along the driving gravity (a tilted chart: the surface is sloped in
        the chart's frame). (left of x-faces, right of x-faces, below y-faces, above y-faces)."""
        cx = np.maximum(cz[:, :-1], cz[:, 1:])
        cy = np.maximum(cz[:-1, :], cz[1:, :])
        sx = np.clip(0.5 * np.divide(b_x, np.maximum(a_x, 1e-12)), -l, l)
        sy = np.clip(0.5 * np.divide(b_y, np.maximum(a_y, 1e-12)), -l, l)
        return cx - sx, cx + sx, cy - sy, cy + sy

    def sub(self, k):
        """Sub-step k of the frame for every run: read buffer k % 2, write buffer (k + 1) % 2."""
        A = self.A
        src, dst = k % 2, (k + 1) % 2
        d_in, qx_in, qy_in = A[f"d{src}"], A[f"qx{src}"], A[f"qy{src}"]
        d_out, qx_out, qy_out = A[f"d{dst}"], A[f"qx{dst}"], A[f"qy{dst}"]
        for cw in self.cache:
            self._window(cw, d_in, qx_in, qy_in, d_out, qx_out, qy_out)

    def _window(self, cw, d_in, qx_in, qy_in, d_out, qx_out, qy_out):
        A = self.A
        l, dt = self.l, self.dt
        l2 = l * l
        R0, R1, C0, C1 = cw["win"]
        r0, r1, c0, c1 = cw["core"]
        d = d_in[R0:R1, C0:C1]
        if cw["rsub"] is not None:
            d = d + cw["rsub"]
        valid = cw["valid"]
        he = d - FILM
        np.maximum(he, 0.0, out=he)
        if valid is not None:
            he *= valid
        E = cw["bed0"] + d
        # critical flow over the crest (task 0346): the head that drives a face's flow out of a cell is its liquid
        # above the higher of the two beds – a full pocket stops spilling once it is down to its rim (it went on by
        # momentum and emptied itself below it)
        Ef = E - FILM
        cxL, cxR, cyL, cyR = cw["crest"]
        wxL = np.minimum(he[:, :-1], np.maximum(Ef[:, :-1] - cxL, 0.0))
        wxR = np.minimum(he[:, 1:], np.maximum(Ef[:, 1:] - cxR, 0.0))
        wyL = np.minimum(he[:-1, :], np.maximum(Ef[:-1, :] - cyL, 0.0))
        wyR = np.minimum(he[1:, :], np.maximum(Ef[1:, :] - cyR, 0.0))
        for w_ in (wxL, wxR, wyL, wyR):
            w_ *= np.sqrt(w_)
        if self.uniform:
            gq = cw["gq"]
            wxL *= gq
            wxR *= gq
            wyL *= gq
            wyR *= gq
        else:
            wxL *= cw["gq_x"]
            wxR *= cw["gq_x"]
            wyL *= cw["gq_y"]
            wyR *= cw["gq_y"]
        Qx = self._faces(qx_in[R0:R1, C0:C1 - 1], he[:, :-1], he[:, 1:], wxL, wxR, E[:, :-1], E[:, 1:], cw["fx"],
                         cw["a_x"], cw["b_x"])
        Qy = self._faces(qy_in[R0:R1 - 1, C0:C1], he[:-1, :], he[1:, :], wyL, wyR, E[:-1, :], E[1:, :], cw["fy"],
                         cw["a_y"], cw["b_y"])
        buf = cw["buf"]
        # never more out of a cell than it holds above its film (per sub-step)
        Px, Nx = np.maximum(Qx, 0.0), np.minimum(Qx, 0.0)
        Py, Ny = np.maximum(Qy, 0.0), np.minimum(Qy, 0.0)
        out = buf["out"]
        out.fill(0.0)
        out[:, :-1] += Px
        out[:, 1:] -= Nx
        out[:-1, :] += Py
        out[1:, :] -= Ny
        out *= dt
        K = he * l2
        K /= np.maximum(out, 1e-300, out=out)
        np.minimum(K, 1.0, out=K)
        Px *= K[:, :-1]
        Nx *= K[:, 1:]
        Qx = np.add(Px, Nx, out=Px)
        Py *= K[:-1, :]
        Ny *= K[1:, :]
        Qy = np.add(Py, Ny, out=Py)
        # what crosses a face into no surface leaves the chart (drops); the rest moves between cells
        fx, fy = cw["fx"], cw["fy"]
        lost = None
        if fx["ol"] is not None or fx["orr"] is not None or fy["ol"] is not None or fy["orr"] is not None:
            lost = buf["lost"]
            lost.fill(0.0)
            if fx["ol"] is not None:
                lost[:, :-1] += Qx * fx["ol"]
            if fx["orr"] is not None:
                lost[:, 1:] -= Qx * fx["orr"]
            if fy["ol"] is not None:
                lost[:-1, :] += Qy * fy["ol"]
            if fy["orr"] is not None:
                lost[1:, :] -= Qy * fy["orr"]
        dd = buf["dd"]
        dd.fill(0.0)
        dd[:, :-1] -= Qx
        dd[:, 1:] += Qx
        dd[:-1, :] -= Qy
        dd[1:, :] += Qy
        dd *= dt / l2
        dn = d + dd
        if valid is not None:
            dn *= valid
        dw = None
        if cw["down"] is not None:               # upside down: it drips off within ~DRIP_TIME (the film stays)
            dw = dn - FILM
            np.maximum(dw, 0.0, out=dw)
            dw *= cw["down"]
            dw *= min(1.0, dt / DRIP_TIME)
            dn -= dw
        q = None
        if cw["dcoef"] is not None:              # drains: orifices
            q = np.sqrt(np.maximum(dn, 0.0))
            q *= cw["dcoef"]
            q *= dt
            np.minimum(q, dn * l2, out=q)
            np.maximum(q, 0.0, out=q)
            dn -= q / l2
        np.maximum(dn, 0.0, out=dn)
        # write the core back
        a, b, c, e = r0 - R0, r1 - R0, c0 - C0, c1 - C0
        d_out[r0:r1, c0:c1] = dn[a:b, c:e]
        fx0 = max(c0 - 1, 0)
        qx_out[r0:r1, fx0:c1 - 1] = Qx[a:b, fx0 - C0:c1 - 1 - C0]
        fy0 = max(r0 - 1, 0)
        qy_out[fy0:r1 - 1, c0:c1] = Qy[fy0 - R0:r1 - 1 - R0, c:e]
        if lost is not None:
            A["lost"][r0:r1, c0:c1] += lost[a:b, c:e] * dt
        if dw is not None:
            A["dripped"][r0:r1, c0:c1] += dw[a:b, c:e] * l2
        if q is not None:
            A["drained"][r0:r1, c0:c1] += q[a:b, c:e]

    def _faces(self, Q0, hL, hR, wL, wR, EL, ER, fc, a, b):
        """New fluxes on one direction's faces, before the "not more than it holds" scaling. ``wL``/``wR``: the weir
        limits of the upstream cell (critical flow), ``a`` = pressing gravity x dt l / cell, ``b`` = driving
        gravity x dt l."""
        hf = fc["wl"] * hL
        hf += fc["wr"] * hR
        if self.cap is not None:                 # deep pools: waves no faster than sqrt(g cap) (fewer sub-steps)
            np.minimum(hf, self.cap, out=hf)
        dE = EL - ER
        if fc["both"] is not None:
            dE *= fc["both"]
        if fc["ol"] is not None:
            dE += fc["ol"] * hL
        if fc["orr"] is not None:
            dE -= fc["orr"] * hR
        dE *= a
        dE += b
        dE *= hf
        Q = Q0 + dE
        hh = np.maximum(hf, HMIN)
        fr = _FR_A / hh
        fr += _FR_B
        fr /= hh
        fr *= self.dt
        fr += 1.0
        Q /= fr
        # never more than critical flow over a weir from the upstream cell (else rings at every rim)
        np.minimum(Q, wL, out=Q)
        np.maximum(Q, -wR, out=Q)
        if fc["opn"] is not None:
            Q *= fc["opn"]
        return Q

    # --- the end of a frame ---------------------------------------------------------------------------------------
    def report(self, tiles):
        """Per tile of the runs: (tj, ti, state, hmax, lost cells, drained). state 0 dry, 1 active, 2 at rest.
        Lost cells: (global j, i, edge volume, dripped volume). Clears the per-frame sums."""
        A, l = self.A, self.l
        d, qx, qy = A["d0"], A["qx0"], A["qy0"]
        out = []
        for (r0, r1, c0, c1), start in zip((cw["core"] for cw in self.cache), self.start):
            for tj, ti in tiles(r0, r1, c0, c1):
                a0, a1, b0, b1 = tile_box(tj, ti, self.NY, self.NX)
                dt_ = d[a0:a1, b0:b1]
                v = A["valid"][a0:a1, b0:b1]
                he = np.maximum(dt_ - FILM, 0.0) * v
                fx0, fy0 = max(b0 - 1, 0), max(a0 - 1, 0)
                qxt = qx[a0:a1, fx0:b1 - 1]
                qyt = qy[fy0:a1 - 1, b0:b1]
                dr = A["drain"][a0:a1, b0:b1]
                wet = bool((he > 0).any())
                moving = bool(qxt.any() or qyt.any())
                draining = bool(((dr > 0) & (dt_ > 0)).any())
                hmax = float(dt_.max()) if dt_.size else 0.0
                if not wet and not moving and not draining:
                    state = 0
                else:
                    st = start[a0 - r0:a1 - r0, b0 - c0:b1 - c0]
                    still = float(np.abs(dt_ - st).max()) < SETTLE_DEPTH
                    if still and not draining:
                        hx = np.maximum(0.5 * (he[:, :-1] + he[:, 1:]), 1e-5) if he.shape[1] > 1 else None
                        hy = np.maximum(0.5 * (he[:-1, :] + he[1:, :]), 1e-5) if he.shape[0] > 1 else None
                        u = 0.0
                        # the tile's own faces inside it (its border faces are its neighbours' or the chart's edge)
                        if hx is not None:
                            u = max(u, float((np.abs(qx[a0:a1, b0:b1 - 1]) / (l * hx)).max()))
                        if hy is not None:
                            u = max(u, float((np.abs(qy[a0:a1 - 1, b0:b1]) / (l * hy)).max()))
                        state = 2 if u < SETTLE_SPEED else 1
                    else:
                        state = 1
                lo = A["lost"][a0:a1, b0:b1]
                dp = A["dripped"][a0:a1, b0:b1]
                js, is_ = np.nonzero((lo > 0) | (dp > 0))
                cells = (js + a0, is_ + b0, lo[js, is_].copy(), dp[js, is_].copy()) if len(js) else None
                dsum = float(A["drained"][a0:a1, b0:b1].sum())
                lo[:] = 0.0
                dp[:] = 0.0
                A["drained"][a0:a1, b0:b1] = 0.0
                out.append((tj, ti, state, hmax, cells, dsum))
        self.cache = []
        self.start = []
        return out


def tiles_of(r0, r1, c0, c1, T=TILE):
    """The tiles a core (whole tiles) covers, row by row."""
    return [(tj, ti) for tj in range(r0 // T, (r1 - 1) // T + 1) for ti in range(c0 // T, (c1 - 1) // T + 1)]


# ---------------------------------------------------------------------------------------------------------------
# the solver
# ---------------------------------------------------------------------------------------------------------------

class _Grid:
    """A chart as the solver keeps it: padded with a ring of one 'no surface' cell, tiles, states."""

    def __init__(self, chart: Chart, A):
        self.chart = chart
        self.A = A
        ny, nx = chart.shape
        self.NY, self.NX = ny + 2, nx + 2
        self.l = float(chart.cell)
        self.xs = chart.x0 + (np.arange(self.NX) - 1) * self.l
        self.ys = chart.y0 + (np.arange(self.NY) - 1) * self.l
        self.TJ = (self.NY + TILE - 1) // TILE
        self.TI = (self.NX + TILE - 1) // TILE
        self.state = np.zeros((self.TJ, self.TI), np.int8)
        self.hmax = np.zeros((self.TJ, self.TI))
        self.held = np.zeros((self.TJ, self.TI), bool)     # tiles held (frozen) in the current frame
        self.woken = np.zeros((self.TJ, self.TI), bool)
        self.rain_tiles = np.zeros((self.TJ, self.TI), bool)
        self.push_tiles = np.zeros((self.TJ, self.TI), bool)
        self.landed = np.zeros((self.NY, self.NX))          # drops landed in the flight, arrive next frame
        self.landed_tiles = np.zeros((self.TJ, self.TI), bool)
        self.g_prev = None
        self.drained = 0.0
        self.set_bed(chart.bed, first=True)
        self.held[:] = True
        A["frozen"][:] = 1.0

    @property
    def interior(self):
        return slice(1, self.NY - 1), slice(1, self.NX - 1)

    def set_bed(self, bed, first=False):
        """(Re)build the static arrays from a bed; returns the volume (m^3) that lost its surface."""
        A = self.A
        bed = np.asarray(bed, float)
        ny, nx = bed.shape
        if (ny + 2, nx + 2) != (self.NY, self.NX):
            raise ValueError("a new bed must have the chart's shape")
        full = np.full((self.NY, self.NX), np.nan)
        full[1:-1, 1:-1] = bed
        valid = np.isfinite(full)
        spill = 0.0
        if not first:
            lost = (A["valid"] > 0) & ~valid
            spill = float(A["d0"][lost].sum() * self.l ** 2)
            for k in ("d0", "d1"):
                A[k][lost] = 0.0
            changed = (A["valid"] > 0) != valid
            changed |= valid & (A["bed0"] != np.where(valid, full, 0.0))
            for tj, ti in zip(*np.nonzero(_tiles_any(changed, self.TJ, self.TI))):
                self.woken[tj, ti] = True
        A["valid"][:] = valid
        A["bed0"][:] = np.where(valid, full, 0.0)
        fill = float(np.nanmin(full)) if valid.any() else 0.0
        A["cz"][:] = np.where(valid, full, fill)
        if self.chart.drain is not None:
            A["drain"][1:-1, 1:-1] = np.where(np.isfinite(bed), self.chart.drain, 0.0)
        vL, vR = valid[:, :-1], valid[:, 1:]
        vU, vD = valid[:-1, :], valid[1:, :]
        open_ = self.chart.open_edges
        for (a, b), names in (((vL, vR), ("wlx", "wrx", "bx", "olx", "orx")),
                              ((vU, vD), ("wly", "wry", "by", "oly", "ory"))):
            both = a & b
            ol = (a & ~b) if open_ else np.zeros_like(both)
            orr = (~a & b) if open_ else np.zeros_like(both)
            A[names[0]][:] = np.where(both, 0.5, np.where(ol, 1.0, 0.0))
            A[names[1]][:] = np.where(both, 0.5, np.where(orr, 1.0, 0.0))
            A[names[2]][:] = both
            A[names[3]][:] = ol
            A[names[4]][:] = orr
        # the direction a drop leaves an edge cell by: towards its neighbours with no surface (chart frame)
        ox = np.zeros((self.NY, self.NX))
        oy = np.zeros((self.NY, self.NX))
        ox[:, :-1] += ~vR & vL
        ox[:, 1:] -= ~vL & vR
        oy[:-1, :] += ~vD & vU
        oy[1:, :] -= ~vU & vD
        n = np.hypot(ox, oy)
        self.outdir = np.stack([np.where(n > 0, ox / np.maximum(n, 1e-300), 0), np.where(n > 0, oy / np.maximum(n, 1e-300), 0)], -1)
        self.valid = valid
        cz = A["cz"]
        self.cz_lo, self.cz_hi = float(cz.min()), float(cz.max())
        self.bed_lo = float(A["bed0"][valid].min()) if valid.any() else 0.0
        self.bed_hi = float(A["bed0"][valid].max()) if valid.any() else 0.0
        self.extent = max(abs(self.xs[0]), abs(self.xs[-1]), abs(self.ys[0]), abs(self.ys[-1]), 1e-3) + \
            max(abs(self.cz_lo), abs(self.cz_hi))
        return spill

    def tile_slices(self, tj, ti):
        a0, a1, b0, b1 = tile_box(tj, ti, self.NY, self.NX)
        return slice(a0, a1), slice(b0, b1)

    def cell_index(self, x, y):
        """Padded (j, i) of the cells holding chart-frame points, and whether they are on the grid's interior."""
        i = np.round((np.asarray(x, float) - self.xs[0]) / self.l).astype(np.int64)
        j = np.round((np.asarray(y, float) - self.ys[0]) / self.l).astype(np.int64)
        ok = (i >= 1) & (j >= 1) & (i <= self.NX - 2) & (j <= self.NY - 2)
        return j, i, ok


def _tiles_any(mask, TJ, TI, T=TILE):
    """(TJ, TI): any cell of the tile set."""
    NY, NX = mask.shape
    m = np.zeros((TJ * T, TI * T), bool)
    m[:NY, :NX] = mask
    return m.reshape(TJ, T, TI, T).any(axis=(1, 3))


def _dilate(m, k):
    """Grow a tile mask by k tiles (8 neighbours)."""
    for _ in range(k):
        g = m.copy()
        g[1:, :] |= m[:-1, :]
        g[:-1, :] |= m[1:, :]
        h = g.copy()
        h[:, 1:] |= g[:, :-1]
        h[:, :-1] |= g[:, 1:]
        m = h
    return m


class Liquid:
    """The liquid on a set of charts that move with their carriers.

    ``mats[c]``: (frames, 4, 4) world-from-chart matrices of chart c (m); ``fps``; ``floor_z``: world height of the
    floor (what falls below it is gone). ``helpers``: helper processes (0 = all in this process; the result is the
    same bit for bit). ``hold``: hold tiles at rest (False: step every wet tile every frame)."""

    def __init__(self, charts, mats, fps, floor_z, helpers=0, hold=True, python=None, wave_depth=None):
        self.charts = list(charts)
        # (task 0346) a face's depth counts at most this for the flow: waves in deep pools (a T-slot, a deep pocket)
        # travel at sqrt(g wave_depth) and the sub-steps follow that; levels, volumes and the drains are unchanged,
        # a deep pool only sloshes slower. None: no cap (task 0255's tests)
        self.wave_depth = float(wave_depth) if wave_depth else None
        self.mats = [np.asarray(m, float) for m in mats]
        if len(self.mats) != len(self.charts):
            raise ValueError("one matrix track per chart")
        self.frames_n = min(m.shape[0] for m in self.mats) if self.mats else 0
        self.fps = float(fps)
        if not self.fps > 0:
            raise ValueError("fps must be > 0")
        self.floor_z = float(floor_z)
        self.hold = bool(hold)
        self.P = np.zeros((0, 3))
        self.V = np.zeros((0, 3))
        self.vol = np.zeros(0)
        self.src = np.zeros(0, np.int64)
        self.floor = 0.0
        self.poured = 0.0
        self.thrown = 0.0
        self.pool = None
        self.grids = []
        metas = []
        arrays = []
        for ch in self.charts:
            NY, NX = ch.shape[0] + 2, ch.shape[1] + 2
            arrays.append({n: (kind, dt) for n, kind, dt in ARRAYS})
            metas.append((NY, NX))
        if helpers and helpers > 0:
            try:
                from . import liquid_pool
            except ImportError:                 # this file imported on its own (tests, a helper)
                import liquid_pool
            self.pool = liquid_pool.Pool(int(helpers), python=python)
            As = [self.pool.allocate(c, NY, NX) for c, (NY, NX) in enumerate(metas)]
        else:
            As = [{n: np.zeros(array_shape(kind, NY, NX), dt) for n, kind, dt in ARRAYS} for NY, NX in metas]
        for ch, A in zip(self.charts, As):
            self.grids.append(_Grid(ch, A))
        self.kernels = [Kernel(g.A, self._meta(g)) for g in self.grids]
        if self.pool is not None:
            self.pool.start([self._meta(g) for g in self.grids])
        self._touched_rain = [[] for _ in self.grids]
        self._touched_push = [[] for _ in self.grids]

    def _meta(self, g):
        return dict(cell=g.l, NY=g.NY, NX=g.NX, xs=g.xs, ys=g.ys, wave_depth=self.wave_depth)

    # --- set-up and reading ---------------------------------------------------------------------------------------
    def fill(self, c, depth):
        """Put liquid on chart c (depth (ny, nx), m) before the run; it counts as poured."""
        g = self.grids[c]
        depth = np.where(g.valid[1:-1, 1:-1], np.maximum(np.asarray(depth, float), 0.0), 0.0)
        for k in ("d0", "d1"):
            g.A[k][1:-1, 1:-1] += depth
        self.poured += float(depth.sum()) * g.l * g.l
        g.woken |= _tiles_any(np.pad(depth > 0, 1), g.TJ, g.TI)
        g.hmax = np.maximum(g.hmax, float(g.A["d0"].max()))

    def set_bed(self, c, bed):
        """The surface of chart c changed (the cut went deeper): keeps the liquid where there still is a surface; what
        lost its surface falls (counted as a drop from the chart). Returns that volume (litres)."""
        g = self.grids[c]
        before = g.A["d0"].copy()
        spill = g.set_bed(bed)
        if spill > 0:
            lost = (before > 0) & ~g.valid
            js, is_ = np.nonzero(lost)
            self._spawn_cells(c, g, js, is_, before[js, is_] * g.l * g.l, np.zeros(len(js)), self._last_f)
        return spill * 1e3

    def depth(self, c) -> np.ndarray:
        """Chart c's liquid depths (ny, nx), m: a view, valid until the next step."""
        g = self.grids[c]
        return g.A["d0"][1:-1, 1:-1]

    def velocity(self, c) -> np.ndarray:
        """Chart c's liquid speed per cell (ny, nx, 2), m/s along the chart's x / y: the mean of the fluxes on the
        cell's two faces in each direction / (cell x depth above the film); 0 where there is no flowing liquid.
        (For chips carried by the liquid, later.)"""
        g = self.grids[c]
        A, l = g.A, g.l
        he = np.maximum(A["d0"] - FILM, 0.0) * A["valid"]
        qx = np.zeros((g.NY, g.NX + 1))
        qx[:, 1:-1] = A["qx0"]
        qy = np.zeros((g.NY + 1, g.NX))
        qy[1:-1, :] = A["qy0"]
        ux = 0.5 * (qx[:, :-1] + qx[:, 1:])
        uy = 0.5 * (qy[:-1, :] + qy[1:, :])
        den = l * np.maximum(he, 1e-300)
        u = np.where(he > 0, ux / den, 0.0)
        v = np.where(he > 0, uy / den, 0.0)
        return np.stack([u, v], -1)[1:-1, 1:-1]

    def flux(self, c):
        """Chart c's face fluxes (m^3/s): qx (ny, nx + 1) on the faces between columns (and the two edges), qy
        (ny + 1, nx)."""
        g = self.grids[c]
        return g.A["qx0"][1:-1, :].copy(), g.A["qy0"][:, 1:-1].copy()

    def volume(self, c) -> float:
        """Liquid on chart c (litres)."""
        g = self.grids[c]
        return float(g.A["d0"].sum()) * g.l * g.l * 1e3

    def totals(self) -> dict:
        """The bookkeeping in litres: poured = on_charts + in_flight + drained + floor."""
        on = 0.0
        for g in self.grids:
            on += (float(g.A["d0"].sum()) + float(g.landed.sum())) * g.l * g.l
        return dict(poured=self.poured * 1e3, on_charts=on * 1e3, in_flight=float(self.vol.sum()) * 1e3,
                    drained=sum(g.drained for g in self.grids) * 1e3, floor=self.floor * 1e3)

    def close(self):
        """Stop the helpers. The state stays readable (copied out of the shared memory first)."""
        if self.pool is not None:
            for g, kr in zip(self.grids, self.kernels):
                g.A = {k: np.array(v) for k, v in g.A.items()}
                kr.A = g.A
                kr.cache = []
                kr.start = []
            self.pool.close()
            self.pool = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # --- motion ----------------------------------------------------------------------------------------------------
    def mat(self, c, f):
        f = min(max(int(f), 0), self.frames_n - 1)
        return self.mats[c][f]

    def gravity(self, c, f):
        """Chart c's effective gravity at frame f in the chart's frame as g(p) = gc + gb @ p (p = (x, y, z) in the
        chart's frame): (gc, gb). Zero acceleration at the first and last frames."""
        h = 1.0 / self.fps
        M1 = self.mat(c, f)
        R1 = M1[:3, :3]
        g = np.array([0.0, 0.0, -G])
        if 0 < f < self.frames_n - 1:
            M0, M2 = self.mat(c, f - 1), self.mat(c, f + 1)
            Aa = (M2[:3, :3] - 2 * R1 + M0[:3, :3]) / (h * h)
            a0 = (M2[:3, 3] - 2 * M1[:3, 3] + M0[:3, 3]) / (h * h)
        else:
            Aa = np.zeros((3, 3))
            a0 = np.zeros(3)
        gc = R1.T @ (g - a0)
        gb = -(R1.T @ Aa)
        return gc, gb

    def velocity_at(self, c, f, pts_local):
        h = 1.0 / self.fps
        A, B = self.mat(c, f), self.mat(c, f + 1)
        pa = pts_local @ A[:3, :3].T + A[:3, 3]
        pb = pts_local @ B[:3, :3].T + B[:3, 3]
        return (pb - pa) / h

    # --- running ---------------------------------------------------------------------------------------------------
    def run(self, f0, f1, pours=None, tool=None, push=None):
        """Step from frame f0 to f1; yields a ``Frame`` for every frame f0 + 1 … f1. ``pours(f)`` → list of ``Pour``,
        ``tool(f)`` → ``Tool`` or None, ``push(f)`` → {chart: (ax, ay)} (m/s^2 along the chart, scalars or (ny, nx)) –
        the inputs during the step from f to f + 1."""
        for f in range(int(f0), int(f1)):
            yield self.step(f, pours(f) if pours else None, tool(f) if tool else None, push(f) if push else None)

    _last_f = 0

    def step(self, f, pours=None, tool=None, push=None) -> Frame:
        """Advance from frame f to f + 1 with the inputs of frame f; returns the state at f + 1."""
        self._last_f = f
        T = 1.0 / self.fps
        thrown0 = self.thrown
        # rain and push of the last frame are gone
        for c, g in enumerate(self.grids):
            for tj, ti in self._touched_rain[c]:
                g.A["rain"][g.tile_slices(tj, ti)] = 0.0
            self._touched_rain[c] = []
            for tj, ti in self._touched_push[c]:
                s = g.tile_slices(tj, ti)
                g.A["px"][s] = 0.0
                g.A["py"][s] = 0.0
            self._touched_push[c] = []
            g.rain_tiles[:] = False
            g.push_tiles[:] = False
        # what landed during the last frame's flight arrives now
        for c, g in enumerate(self.grids):
            for tj, ti in zip(*np.nonzero(g.landed_tiles)):
                s = g.tile_slices(tj, ti)
                g.A["rain"][s] += g.landed[s]
                g.landed[s] = 0.0
            g.rain_tiles |= g.landed_tiles
            g.landed_tiles[:] = False
        for p in pours or []:
            self._pour(p, f, T)
        if tool is not None:
            self._tool(tool, f, T)
        if push:
            for c, (ax, ay) in push.items():
                g = self.grids[c]
                ax = np.broadcast_to(np.asarray(ax, float), g.chart.shape)
                ay = np.broadcast_to(np.asarray(ay, float), g.chart.shape)
                g.A["px"][1:-1, 1:-1] += ax
                g.A["py"][1:-1, 1:-1] += ay
                m = np.pad((ax != 0) | (ay != 0), 1)
                g.push_tiles |= _tiles_any(m, g.TJ, g.TI)
        for c, g in enumerate(self.grids):
            for tj, ti in zip(*np.nonzero(g.rain_tiles)):
                self._touched_rain[c].append((int(tj), int(ti)))
            for tj, ti in zip(*np.nonzero(g.push_tiles)):
                self._touched_push[c].append((int(tj), int(ti)))
        stepped, subs, held = [], [], []
        for c, g in enumerate(self.grids):
            s, n, h = self._step_chart(c, g, f, T)
            stepped.append(s)
            subs.append(n)
            held.append(h)
        self._fly(f + 1, T)
        tot = self.totals()
        return Frame(frame=f + 1, drops=self.P.copy(), drop_v=self.V.copy(), drop_vol=self.vol * 1e3, totals=tot,
                     thrown=(self.thrown - thrown0) * 1e3, stepped=stepped, substeps=subs, held=held)

    def _step_chart(self, c, g, f, T):
        A = g.A
        gc, gb = self.gravity(c, f)
        uniform = bool(np.abs(gb).max() < 1e-9)
        if uniform:
            gb = np.zeros((3, 3))
        changed = g.g_prev is None or not (np.abs(gc - g.g_prev[0]).max() < GRAVITY_TOL
                                           and np.abs(gb - g.g_prev[1]).max() * self._extent(g) < GRAVITY_TOL)
        g.g_prev = (gc, gb)
        has_push = bool(g.push_tiles.any())
        # sub-steps from the deepest liquid and the strongest pressing gravity
        gn_max = self._gn_max(g, gc, gb, uniform)
        hmax = float(g.hmax.max())
        if g.rain_tiles.any() or g.woken.any():
            hmax = max(hmax, float(A["d0"].max()))
        c_wave = math.sqrt(max(gn_max, 1.0) * max(min(hmax, self.wave_depth or hmax), 1e-4))
        n = max(1, math.ceil(T / (CFL * g.l / c_wave)))
        n += n % 2
        # which tiles to step
        act = (g.state == 1) | g.woken | g.rain_tiles | (g.push_tiles & (g.state > 0))
        if changed or not self.hold:
            act |= g.state == 2
        k = -(-n // TILE)
        step = _dilate(act, k) if act.any() else act
        g.woken[:] = False
        newly_held = step.copy()
        newly_held[:] = ~step & ~g.held
        newly_free = step & g.held
        # tiles held from now on: at rest (fluxes 0) and both buffers the same
        for tj, ti in zip(*np.nonzero(newly_held)):
            s = g.tile_slices(tj, ti)
            a0, a1, b0, b1 = tile_box(tj, ti, g.NY, g.NX)
            if g.state[tj, ti] == 2:
                A["qx0"][a0:a1, max(b0 - 1, 0):b1 - 1] = 0.0
                A["qy0"][max(a0 - 1, 0):a1 - 1, b0:b1] = 0.0
            A["d1"][s] = A["d0"][s]
            A["qx1"][a0:a1, max(b0 - 1, 0):b1 - 1] = A["qx0"][a0:a1, max(b0 - 1, 0):b1 - 1]
            A["qy1"][max(a0 - 1, 0):a1 - 1, b0:b1] = A["qy0"][max(a0 - 1, 0):a1 - 1, b0:b1]
            A["frozen"][s] = 1.0
        for tj, ti in zip(*np.nonzero(newly_free)):
            A["frozen"][g.tile_slices(tj, ti)] = 0.0
        g.held = ~step
        if not step.any():
            return 0, 0, int((g.state == 2).sum())
        runs = self._runs(g, step)
        dt = T / n
        cells = sum((r1 - r0) * (c1 - c0) for r0, r1, c0, c1 in runs)
        rain = bool(g.rain_tiles.any())
        if self.pool is not None and self.pool.broken:
            raise self.pool.HelperError(self.pool.broken)   # the state is half stepped: no going on alone
        if self.pool is not None and self.pool.worth(cells):
            reports = self.pool.frame(c, runs, n, dt, gc, gb, uniform, has_push, rain, self.kernels[c])
        else:
            kr = self.kernels[c]
            kr.frame(runs, n, dt, gc, gb, uniform, has_push, rain)
            for kk in range(n):
                kr.sub(kk)
            reports = kr.report(tiles_of)
        reports.sort(key=lambda r: (r[0], r[1]))
        js_all, is_all, lo_all, dp_all = [], [], [], []
        for tj, ti, state, hm, cells_, dsum in reports:
            g.state[tj, ti] = state
            g.hmax[tj, ti] = hm
            g.drained += dsum
            if cells_ is not None:
                js_all.append(cells_[0]); is_all.append(cells_[1]); lo_all.append(cells_[2]); dp_all.append(cells_[3])
        if js_all:
            self._spawn_cells(c, g, np.concatenate(js_all), np.concatenate(is_all), np.concatenate(lo_all),
                              np.concatenate(dp_all), f)
        return cells, n, int(((g.state == 2) & g.held).sum())

    @staticmethod
    def _extent(g):
        return g.extent

    @staticmethod
    def _gn_max(g, gc, gb, uniform):
        if uniform:
            return float(-gc[2])
        zs = (g.cz_lo, g.cz_hi)
        best = -1e300
        for x in (g.xs[0], g.xs[-1]):
            for y in (g.ys[0], g.ys[-1]):
                for z in zs:
                    best = max(best, -(gc[2] + gb[2, 0] * x + gb[2, 1] * y + gb[2, 2] * z))
        return best

    @staticmethod
    def _runs(g, step, max_tiles=8):
        """Neighbouring stepped tiles of one tile row as cores (cells), at most ``max_tiles`` long."""
        runs = []
        for tj in range(g.TJ):
            row = step[tj]
            ti = 0
            while ti < g.TI:
                if not row[ti]:
                    ti += 1
                    continue
                t0 = ti
                while ti < g.TI and row[ti] and ti - t0 < max_tiles:
                    ti += 1
                a0, a1, _, _ = tile_box(tj, t0, g.NY, g.NX)
                _, _, b0, _ = tile_box(tj, t0, g.NY, g.NX)
                _, _, _, b1 = tile_box(tj, ti - 1, g.NY, g.NX)
                runs.append((a0, a1, b0, b1))
        return runs

    # --- pours, the tool, drops --------------------------------------------------------------------------------------
    def _rain(self, g, j, i, vol, radius):
        """Spread landed volumes (m^3) at padded cells (j, i) over discs of ``radius``, onto cells with a surface;
        lands in the next sub-steps of this frame (or the next frame when called during the flight)."""
        if not len(vol):
            return
        r = max(1, int(round(radius / g.l)))
        dj, di = np.mgrid[-r:r + 1, -r:r + 1]
        k = (dj ** 2 + di ** 2) <= r * r + 0.5
        dj, di = dj[k], di[k]
        w = np.exp(-(dj ** 2 + di ** 2) / max(r * r / 2.0, 0.5))
        J = np.clip(np.asarray(j)[:, None] + dj[None], 0, g.NY - 1)
        I = np.clip(np.asarray(i)[:, None] + di[None], 0, g.NX - 1)
        W = w[None] * g.valid[J, I]
        tot = W.sum(1, keepdims=True)
        none = tot[:, 0] <= 0
        if none.any():                        # nowhere with a surface: gone to the floor
            self.floor += float(np.asarray(vol)[none].sum())
        W = np.where(tot > 0, W / np.maximum(tot, 1e-300), 0.0)
        target = g.landed if self._flying else g.A["rain"]
        np.add.at(target, (J.ravel(), I.ravel()), (W * np.asarray(vol)[:, None]).ravel() / (g.l * g.l))
        tiles = np.zeros((g.TJ, g.TI), bool)
        tiles[J[W > 0] // TILE, I[W > 0] // TILE] = True
        if self._flying:
            g.landed_tiles |= tiles
        else:
            g.rain_tiles |= tiles

    _flying = False

    def _pour(self, p: Pour, f, T):
        vol = float(p.rate) / 1000.0 / 60.0 * T
        if vol <= 0:
            return
        self.poured += vol
        if p.chart is not None:
            if not 0 <= int(p.chart) < len(self.grids):
                raise ValueError(f"a pour names chart {p.chart}, there are {len(self.grids)}")
            g = self.grids[int(p.chart)]
            j, i, ok = g.cell_index(p.point[0], p.point[1])
            if not ok or not g.valid[j, i]:
                self.floor += vol
                return
            self._rain(g, np.array([j]), np.array([i]), np.array([vol]), p.radius)
            return
        pt, dr = np.asarray(p.point, float), np.asarray(p.direction, float)
        if not (np.isfinite(pt).all() and np.isfinite(dr).all()) or not np.any(dr):
            self.floor += vol                   # nowhere to aim: it is not lost from the bookkeeping
            return
        hit = self._ray(pt, dr, f)
        if hit is None:
            self.floor += vol
            return
        c, j, i = hit
        self._rain(self.grids[c], np.array([j]), np.array([i]), np.array([vol]), p.radius)

    def _ray(self, p, u, f, smax=5.0):
        """The first catching chart cell the line p + s u (world, s >= 0) meets: (chart, j, i) or None."""
        u = u / max(float(np.linalg.norm(u)), 1e-300)
        if u[2] < 0:
            smax = min(smax, (p[2] - self.floor_z) / -u[2])
        best = None
        for c, g in enumerate(self.grids):
            if not g.chart.catches or not g.valid.any():
                continue
            Mi = np.linalg.inv(self.mat(c, f))
            q0 = Mi[:3, :3] @ p + Mi[:3, 3]
            v = Mi[:3, :3] @ u
            # the part of the line over the chart's box
            lo = np.array([g.xs[0], g.ys[0], g.bed_lo])
            hi = np.array([g.xs[-1], g.ys[-1], g.bed_hi + max(float(g.hmax.max()), 0.05)])
            s0, s1 = 0.0, smax
            for a in range(3):
                if abs(v[a]) < 1e-12:
                    if not (lo[a] - g.l <= q0[a] <= hi[a] + g.l):
                        s1 = -1.0
                    continue
                t0, t1 = (lo[a] - g.l - q0[a]) / v[a], (hi[a] + g.l - q0[a]) / v[a]
                s0, s1 = max(s0, min(t0, t1)), min(s1, max(t0, t1))
            if s1 < s0:
                continue
            ns = int(min(max(math.ceil((s1 - s0) / (0.5 * g.l)), 1), 20000)) + 1
            s = np.linspace(s0, s1, ns)
            q = q0[None] + s[:, None] * v[None]
            j, i, ok = g.cell_index(q[:, 0], q[:, 1])
            jj, ii = np.where(ok, j, 0), np.where(ok, i, 0)
            top = g.A["bed0"][jj, ii] + g.A["d0"][jj, ii]
            under = ok & g.valid[jj, ii] & (q[:, 2] <= top)
            if under.any():
                k = int(np.argmax(under))
                if best is None or s[k] < best[0]:
                    best = (s[k], c, int(jj[k]), int(ii[k]))
        return None if best is None else best[1:]

    def _tool(self, t: Tool, f, T):
        """The spinning tool throws off the liquid it touches and turns the liquid round it."""
        if not t.rpm or not t.radius > 0 or not np.isfinite(
                np.concatenate([np.ravel(t.tip), np.ravel(t.axis), [t.radius, t.flute, t.rpm]]).astype(float)).all():
            return                              # a standing spindle, or no sensible tool: nothing
        a = np.asarray(t.axis, float)
        a = a / max(float(np.linalg.norm(a)), 1e-300)
        tip = np.asarray(t.tip, float)
        R = float(t.radius)
        v = t.surface_speed()
        Om = t.omega()
        spin = -1.0 if t.rpm > 0 else 1.0                    # turning sense about +axis
        share = (1.0 - math.exp(-T / TOOL_TAU)) * min(1.0, v / 1.0)
        reach = TOOL_RING * R
        for c, g in enumerate(self.grids):
            M = self.mat(c, f)
            Mi = np.linalg.inv(M)
            # the tool's box in the chart's frame (cylinder of radius 3R from tip - gap to tip + flute)
            ends = np.array([tip - a * TOOL_GAP, tip + a * float(t.flute)])
            le = ends @ Mi[:3, :3].T + Mi[:3, 3]
            pad = reach + g.l
            lo, hi = le.min(0) - pad, le.max(0) + pad
            i0 = max(int(math.floor((lo[0] - g.xs[0]) / g.l)), 1)
            i1 = min(int(math.ceil((hi[0] - g.xs[0]) / g.l)), g.NX - 2)
            j0 = max(int(math.floor((lo[1] - g.ys[0]) / g.l)), 1)
            j1 = min(int(math.ceil((hi[1] - g.ys[0]) / g.l)), g.NY - 2)
            if i1 < i0 or j1 < j0:
                continue
            sj, si = slice(j0, j1 + 1), slice(i0, i1 + 1)
            A = g.A
            val = g.valid[sj, si]
            if not val.any():
                continue
            X, Y = np.meshgrid(g.xs[si], g.ys[sj])
            bed = A["bed0"][sj, si]
            d = A["d0"][sj, si]
            Rm = M[:3, :3]
            bot = np.stack([X, Y, bed], -1) @ Rm.T + M[:3, 3]
            top = np.stack([X, Y, bed + d], -1) @ Rm.T + M[:3, 3]
            rel = bot - tip
            s_bot = rel @ a
            s_top = (top - tip) @ a
            radial = rel - s_bot[..., None] * a
            r = np.linalg.norm(radial, axis=-1)
            lo_s = np.minimum(s_bot, s_top)
            hi_s = np.maximum(s_bot, s_top)
            reach_ax = (hi_s >= -TOOL_GAP) & (lo_s <= float(t.flute)) & val
            # thrown off: liquid inside the tool's circle, the part of its column the tool spans
            he = np.maximum(d - FILM, 0.0)
            over = np.clip(np.minimum(hi_s, float(t.flute)) - np.maximum(lo_s, -TOOL_GAP), 0.0, None)
            span = np.maximum(hi_s - lo_s, 1e-300)
            touch = reach_ax & (r <= R + 0.5 * g.l) & (he > 0)
            if touch.any():
                take = np.where(touch, share * he * np.clip(over / span, 0.0, 1.0), 0.0)
                jj, ii = np.nonzero(take > 0)
                if len(jj):
                    vol = take[jj, ii] * g.l * g.l
                    A["d0"][j0 + jj, i0 + ii] -= take[jj, ii]
                    A["d1"][j0 + jj, i0 + ii] = A["d0"][j0 + jj, i0 + ii]
                    g.woken[(j0 + jj) // TILE, (i0 + ii) // TILE] = True
                    rh = radial[jj, ii]
                    rn = r[jj, ii]
                    # a cell on the axis: leave along the chart's x
                    xdir = Rm[:, 0] - (Rm[:, 0] @ a) * a
                    xdir = xdir / max(float(np.linalg.norm(xdir)), 1e-300)
                    rh = np.where(rn[:, None] > 1e-9, rh / np.maximum(rn, 1e-300)[:, None], xdir[None])
                    tang = spin * np.cross(a[None], rh)
                    sl = np.clip(s_top[jj, ii], 0.0, float(t.flute)) + min(float(t.flute), 1e-3)
                    pos = tip[None] + sl[:, None] * a[None] + (R + 0.5e-3) * rh
                    vel = v * (tang + TOOL_OUT * rh + TOOL_UP * a[None])
                    self.thrown += float(vol.sum())
                    self._spawn(pos, vel, vol, np.full(len(vol), -2))
            # the swirl: a push in the turning sense round the tool (and a little outwards)
            ring = reach_ax & (r > R) & (r < reach) & ((d - FILM) > 0)
            if ring.any() and v > 0:
                rr = np.maximum(r, R)
                us = min(SWIRL_SHARE * v, SWIRL_VMAX) * R / rr
                taper = np.clip((reach - rr) / max(reach - R, 1e-300), 0.0, 1.0)
                at = np.minimum(us / SWIRL_TIME, SWIRL_AT_MAX) * taper
                ar = np.minimum(us * us / rr, SWIRL_AR_MAX) * taper
                rh = radial / rr[..., None]
                tang = spin * np.cross(a[None, None], rh)
                pw = at[..., None] * tang + ar[..., None] * rh                  # world
                pl = pw @ Rm                                                    # chart frame (R^T p per row)
                pl[~ring] = 0.0
                A["px"][sj, si] += pl[..., 0]
                A["py"][sj, si] += pl[..., 1]
                jj, ii = np.nonzero(ring)
                g.push_tiles[(j0 + jj) // TILE, (i0 + ii) // TILE] = True

    def _spawn(self, p, v, vol, src):
        self.P = np.vstack([self.P, p])
        self.V = np.vstack([self.V, v])
        self.vol = np.concatenate([self.vol, vol])
        self.src = np.concatenate([self.src, np.asarray(src, np.int64)])

    def _spawn_cells(self, c, g, js, is_, lost, dripped, f):
        """Liquid that left chart c at padded cells (js, is_) during the step f -> f + 1 becomes one drop per cell."""
        vol = lost + dripped
        keep = vol > 0
        js, is_, lost, dripped, vol = js[keep], is_[keep], lost[keep], dripped[keep], vol[keep]
        if not len(vol):
            return
        A = g.A
        loc = np.stack([g.xs[is_], g.ys[js], A["bed0"][js, is_] + 0.5 * A["d0"][js, is_]], -1)
        drip = dripped > lost
        off = g.outdir[js, is_] * (0.6 * g.l)
        loc[~drip, :2] += off[~drip]
        M = self.mat(c, f + 1)
        wp = loc @ M[:3, :3].T + M[:3, 3]
        wv = self.velocity_at(c, f, loc)
        od = np.zeros_like(loc)
        od[:, :2] = g.outdir[js, is_]
        wv += (od @ M[:3, :3].T) * 0.05 * (~drip)[:, None]
        self._spawn(wp, wv, vol, np.full(len(vol), c))

    def _fly(self, f, T):
        """All drops fly one frame; a drop whose path goes under a catching chart's liquid top lands there (at the
        last cell it was above: a drop flying into a wall falls at its foot)."""
        if not len(self.vol):
            return
        alive = np.ones(len(self.vol), bool)
        boxes = []
        for c, g in enumerate(self.grids):
            if not g.chart.catches or not g.valid.any():
                boxes.append(None)
                continue
            M = self.mat(c, f)
            top = g.bed_hi + float(g.hmax.max()) + 0.01
            corners = np.array([[x, y, z] for x in (g.xs[0], g.xs[-1]) for y in (g.ys[0], g.ys[-1])
                                for z in (g.bed_lo, top)])
            w = corners @ M[:3, :3].T + M[:3, 3]
            boxes.append((w.min(0) - g.l, w.max(0) + g.l, np.linalg.inv(M)))
        cmin = min(g.l for g in self.grids) if self.grids else 1e-3
        self._flying = True
        try:
            h = T / FLIGHT_STEPS
            for _ in range(FLIGHT_STEPS):
                P0 = self.P.copy()
                self.V[:, 2] -= G * h
                self.P = self.P + self.V * h
                seg = np.linalg.norm(self.P - P0, axis=1)
                ns = np.clip(np.ceil(seg / (0.5 * cmin)).astype(np.int64), 1, 64)
                lo_seg = np.minimum(P0, self.P)
                hi_seg = np.maximum(P0, self.P)
                n_all = len(self.vol)
                best_k = np.full(n_all, np.iinfo(np.int64).max)
                best_c = np.full(n_all, -1)
                best_j = np.zeros(n_all, np.int64)
                best_i = np.zeros(n_all, np.int64)
                for c, g in enumerate(self.grids):
                    if boxes[c] is None:
                        continue
                    blo, bhi, Mi = boxes[c]
                    near = alive & (self.src != c) & (hi_seg >= blo).all(1) & (lo_seg <= bhi).all(1)
                    idx = np.nonzero(near)[0]
                    if not len(idx):
                        continue
                    cnt = ns[idx]
                    owner = np.repeat(idx, cnt)
                    first = np.repeat(np.cumsum(cnt) - cnt, cnt)
                    k = np.arange(len(owner)) - first + 1
                    t1 = (k / cnt.repeat(cnt))[:, None]
                    t0 = ((k - 1) / cnt.repeat(cnt))[:, None]
                    d = (self.P - P0)[owner]
                    S1 = P0[owner] + d * t1
                    S0 = P0[owner] + d * t0
                    q = S1 @ Mi[:3, :3].T + Mi[:3, 3]
                    j, i, ok = g.cell_index(q[:, 0], q[:, 1])
                    jj, ii = np.where(ok, j, 0), np.where(ok, i, 0)
                    ok &= g.valid[jj, ii]
                    top = g.A["bed0"][jj, ii] + g.A["d0"][jj, ii] + g.landed[jj, ii]
                    hit = ok & (q[:, 2] <= top)
                    if not hit.any():
                        continue
                    hs = np.nonzero(hit)[0]
                    o = owner[hs]
                    firsts = np.ones(len(hs), bool)
                    firsts[1:] = o[1:] != o[:-1]
                    hs, o = hs[firsts], o[firsts]
                    qp = S0[hs] @ Mi[:3, :3].T + Mi[:3, 3]
                    jp, ip, okp = g.cell_index(qp[:, 0], qp[:, 1])
                    jpp, ipp = np.where(okp, jp, 0), np.where(okp, ip, 0)
                    okp &= g.valid[jpp, ipp]
                    better = k[hs] < best_k[o]
                    o = o[better]
                    best_k[o] = k[hs][better]
                    best_c[o] = c
                    best_j[o] = np.where(okp, jpp, jj[hs])[better]
                    best_i[o] = np.where(okp, ipp, ii[hs])[better]
                for c, g in enumerate(self.grids):
                    o = np.nonzero(best_c == c)[0]
                    if len(o):
                        self._rain(g, best_j[o], best_i[o], self.vol[o], DROP_R)
                        alive[o] = False
                low = alive & (self.P[:, 2] < self.floor_z)
                self.floor += float(self.vol[low].sum())
                alive &= ~low
        finally:
            self._flying = False
        self.P, self.V, self.vol, self.src = self.P[alive], self.V[alive], self.vol[alive], self.src[alive]


# ---------------------------------------------------------------------------------------------------------------
# small helpers for set-ups and tests
# ---------------------------------------------------------------------------------------------------------------

def still(frames):
    """(frames, 4, 4) identity matrices."""
    return np.repeat(np.eye(4)[None], int(frames), 0)


def translate(frames, xyz):
    m = still(frames)
    m[:, :3, 3] = np.asarray(xyz, float)
    return m


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1.0]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1.0]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1.0]])
