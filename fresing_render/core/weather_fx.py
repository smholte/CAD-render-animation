"""Rain, snow, splashes and the flag (task 0109): the numbers, in plain Python + NumPy (no Blender).

``blender/weather_fx.py`` draws these with Geometry Nodes that evaluate **the same formulas** at render time from
Scene Time (seconds = frame / fps), so every render of a frame is the same and nothing runs in Python per frame.
The tests compare the two.

Everything is seeded: a layout is a NumPy ``default_rng(seed)`` draw, made once and stored in a mesh.

Units: metres, seconds, m/s; drop sizes in mm.
"""

from __future__ import annotations

import math

import numpy as np

# ---------------------------------------------------------------------------
# falling rain and snow
# ---------------------------------------------------------------------------

SEED_RAIN, SEED_SNOW, SEED_SPLASH = 1091, 2091, 3091

# the box that holds the falling rain / snow: it travels with the active camera (centred a little in front of it),
# while the drops stay put in the world (their pattern repeats with the box's size); rain further away is fog
RAIN_BOX = (36.0, 36.0, 18.0)
SNOW_BOX = (22.0, 22.0, 12.0)
AHEAD = 0.35                       # the box's centre lies this share of its width in front of the camera

# streaks / flakes per cubic metre at amount 1 (a downpour; heavy snowfall). What a camera sees of rain is a streak
# per drop over its exposure; real drops are far denser (~1000 / m3 of all sizes) but only the big near ones show.
RAIN_DENSITY = 3.0
SNOW_DENSITY = 20.0
EXPOSURE = 1.0 / 50.0              # s: a streak is as long as a drop falls in this time (1/50 s, video)
VIEWPORT = 0.25                    # share of drops / flakes drawn in the 3D view (renders draw all)

SNOW_FALL = 1.0                    # m/s: a snowflake's fall speed (0.5 … 1.5 m/s, Locatelli & Hobbs 1974)
SNOW_WOBBLE = 0.35                 # m: flakes sway this far round their path
SNOW_OMEGA = 1.3                   # rad/s
FLAKE_MM = 12.0                    # a flake's size (diameter), mm: wet flakes clump to 5 … 15 mm


def fall_speed(drop_mm: float) -> float:
    """Terminal fall speed of a rain drop (m/s) from its diameter (mm): Atlas, Srivastava & Sekhon (1973),
    v = 9.65 - 10.3 exp(-0.6 D), a fit to Gunn & Kinzer (1949). 2 mm -> 6.5 m/s, 5 mm -> 9.1 m/s."""
    d = max(float(drop_mm), 0.2)
    return max(9.65 - 10.3 * math.exp(-0.6 * d), 0.5)


FALL_EXPR = "9.65 - 10.3 * exp(-0.6 * max(d, 0.2))"      # the same as a simple-expression driver (d: drop, mm)


def count(box, density: float) -> int:
    return int(round(box[0] * box[1] * box[2] * density))


def layout(seed: int, n: int) -> dict:
    """``n`` drops or flakes: ``u`` their place in the unit box (n, 3), ``r`` (n,) the amount at which each one
    appears (a drop shows while ``r < amount``, so more rain only adds drops), ``ph`` (n,) a phase 0 … 1, ``s`` (n,)
    a size factor 0.6 … 1.4. The same seed gives the same numbers every time."""
    rng = np.random.default_rng(int(seed))
    return {"u": rng.random((n, 3)), "r": rng.random(n), "ph": rng.random(n), "s": 0.6 + 0.8 * rng.random(n)}


def box_origin(eye, forward, box) -> np.ndarray:
    """The lowest corner of the box round what the camera at ``eye`` looking along ``forward`` sees."""
    e = np.asarray(eye, dtype=float)
    f = np.asarray(forward, dtype=float)
    b = np.asarray(box, dtype=float)
    return e + f * (AHEAD * b[0]) - 0.5 * b


def wrap(x, lo, hi):
    """Blender's vector math Wrap: ``x`` folded into [lo, hi) (per component)."""
    x, lo, hi = (np.asarray(v, dtype=float) for v in (x, lo, hi))
    r = hi - lo
    return np.where(r != 0.0, x - r * np.floor((x - lo) / np.where(r != 0.0, r, 1.0)), lo)


def wobble(t: float, ph) -> np.ndarray:
    """A snowflake's sway round its straight path (n, 3)."""
    a = SNOW_OMEGA * float(t) + 2.0 * math.pi * np.asarray(ph, dtype=float)
    return np.stack([SNOW_WOBBLE * np.sin(a), SNOW_WOBBLE * np.cos(1.3 * a), np.zeros_like(a)], axis=1)


def positions(u, box, origin, velocity, t: float, sway=None) -> np.ndarray:
    """Where the drops are at time ``t``: each starts at ``u * box`` (world, from 0), moves with ``velocity`` (m/s),
    plus ``sway`` (snow), and is folded into the box at ``origin`` – the pattern is fixed in the world, the box only
    chooses which copy of it is drawn."""
    b = np.asarray(box, dtype=float)
    raw = np.asarray(u, dtype=float) * b + np.asarray(velocity, dtype=float) * float(t)
    if sway is not None:
        raw = raw + sway
    o = np.asarray(origin, dtype=float)
    return wrap(raw, o, o + b)


def rain_velocity(drop_mm: float, wind_ms: float, wind_x: float, wind_y: float) -> tuple:
    """A drop falls at its fall speed and is carried sideways with the wind (it takes the wind's speed within a
    few metres of falling)."""
    return (wind_x * wind_ms, wind_y * wind_ms, -fall_speed(drop_mm))


def snow_velocity(wind_ms: float, wind_x: float, wind_y: float) -> tuple:
    return (wind_x * wind_ms, wind_y * wind_ms, -SNOW_FALL)


def streak(drop_mm: float, wind_ms: float = 0.0) -> tuple:
    """(radius, length) of a rain streak in metres: as long as the drop falls in the exposure, as thick as the
    drop (drawn a little thicker so drizzle still shows)."""
    v = math.hypot(fall_speed(drop_mm), wind_ms)
    return 0.5e-3 * max(float(drop_mm), 0.5) * 1.5, max(v * EXPOSURE, 0.02)


# ---------------------------------------------------------------------------
# splashes: where the rain lands (worked out once)
# ---------------------------------------------------------------------------

SPLASH_CELL = 0.3                  # m between spots
SPLASH_MAX = 60000                 # spots at most (the cell grows on big models)
SPLASH_PERIOD = 0.5                # s between two splashes of one spot (at full rain)
SPLASH_LIFE = 0.08                 # s a splash lives
SPLASH_UP = 0.3                    # a spot only where the surface faces up at least this much (normal z)


def top_heights(tris, x0: float, y0: float, cell: float, nx: int, ny: int, min_up: float = SPLASH_UP):
    """For each cell centre of a grid, the highest point of the triangles straight above or below it (a z-buffer
    from above). ``tris``: (n, 3, 3) world coordinates. Returns (heights (ny, nx), -inf where nothing; up (ny, nx),
    the normal's z of the triangle hit). Triangles facing up less than ``min_up`` (walls) are not counted, but a
    roof facing down hides what is below it all the same (its height counts, its ``up`` is negative)."""
    h = np.full(ny * nx, -np.inf)
    up = np.zeros(ny * nx)
    t = np.asarray(tris, dtype=np.float64).reshape(-1, 3, 3)
    if not len(t):
        return h.reshape(ny, nx), up.reshape(ny, nx)
    a, b, c = t[:, 0], t[:, 1], t[:, 2]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    keep = ln > 1e-12
    a, b, c, n, ln = a[keep], b[keep], c[keep], n[keep], ln[keep]
    nz = n[:, 2] / ln
    keep = np.abs(nz) > 1e-4                         # vertical walls cover no cell centre
    a, b, c, nz = a[keep], b[keep], c[keep], nz[keep]
    # cells whose centre may lie in each triangle
    lo_x = np.minimum(np.minimum(a[:, 0], b[:, 0]), c[:, 0])
    hi_x = np.maximum(np.maximum(a[:, 0], b[:, 0]), c[:, 0])
    lo_y = np.minimum(np.minimum(a[:, 1], b[:, 1]), c[:, 1])
    hi_y = np.maximum(np.maximum(a[:, 1], b[:, 1]), c[:, 1])
    ix0 = np.clip(np.ceil((lo_x - x0) / cell - 0.5), 0, nx).astype(int)
    ix1 = np.clip(np.floor((hi_x - x0) / cell - 0.5), -1, nx - 1).astype(int)
    iy0 = np.clip(np.ceil((lo_y - y0) / cell - 0.5), 0, ny).astype(int)
    iy1 = np.clip(np.floor((hi_y - y0) / cell - 0.5), -1, ny - 1).astype(int)
    wx, wy = ix1 - ix0 + 1, iy1 - iy0 + 1
    some = (wx > 0) & (wy > 0)
    span = np.maximum(wx, wy)
    flat = h  # (alias, written in place)

    def put(sel, s):
        if not np.any(sel):
            return
        A, B, C, Z = a[sel], b[sel], c[sel], nz[sel]
        X0, Y0, WX, WY = ix0[sel], iy0[sel], wx[sel], wy[sel]
        for chunk in range(0, len(A), max(1, 400000 // (s * s))):
            sl = slice(chunk, chunk + max(1, 400000 // (s * s)))
            Ac, Bc, Cc, Zc = A[sl], B[sl], C[sl], Z[sl]
            ox, oy = np.meshgrid(np.arange(s), np.arange(s))
            ox, oy = ox.ravel(), oy.ravel()
            gx = X0[sl, None] + ox[None, :]
            gy = Y0[sl, None] + oy[None, :]
            inside = (ox[None, :] < WX[sl, None]) & (oy[None, :] < WY[sl, None])
            px = x0 + (gx + 0.5) * cell
            py = y0 + (gy + 0.5) * cell
            # barycentric in xy
            v0x, v0y = (Bc - Ac)[:, 0:1], (Bc - Ac)[:, 1:2]
            v1x, v1y = (Cc - Ac)[:, 0:1], (Cc - Ac)[:, 1:2]
            v2x, v2y = px - Ac[:, 0:1], py - Ac[:, 1:2]
            den = v0x * v1y - v1x * v0y
            ok = np.abs(den) > 1e-18
            den = np.where(ok, den, 1.0)
            l1 = (v2x * v1y - v1x * v2y) / den
            l2 = (v0x * v2y - v2x * v0y) / den
            eps = -1e-9
            hit = inside & ok & (l1 >= eps) & (l2 >= eps) & (l1 + l2 <= 1.0 - eps)
            z = Ac[:, 2:3] + l1 * (Bc - Ac)[:, 2:3] + l2 * (Cc - Ac)[:, 2:3]
            idx = (gy * nx + gx)[hit]
            zz = z[hit]
            uu = np.broadcast_to(Zc[:, None], hit.shape)[hit]
            if not len(idx):
                continue
            order = np.lexsort((zz, idx))                 # per cell, the highest last
            idx, zz, uu = idx[order], zz[order], uu[order]
            last = np.r_[idx[1:] != idx[:-1], True]
            idx, zz, uu = idx[last], zz[last], uu[last]
            better = zz > flat[idx]
            flat[idx[better]] = zz[better]
            up[idx[better]] = uu[better]

    lo = 0
    for s in (1, 2, 4, 8, 16, 32, 64):
        put(some & (span > lo) & (span <= s), s)
        lo = s
    for i in np.nonzero(some & (span > lo))[0]:       # a few huge triangles (a deck plate): one by one
        sel = np.zeros(len(a), dtype=bool)
        sel[i] = True                                  # (in pieces of 64 x 64 cells)
        for yy in range(int(iy0[i]), int(iy1[i]) + 1, 64):
            for xx in range(int(ix0[i]), int(ix1[i]) + 1, 64):
                save = ix0[i], iy0[i], wx[i], wy[i]
                ix0[i], iy0[i] = xx, yy
                wx[i], wy[i] = min(64, int(save[0]) + int(save[2]) - xx), min(64, int(save[1]) + int(save[3]) - yy)
                put(sel, 64)
                ix0[i], iy0[i], wx[i], wy[i] = save
    return h.reshape(ny, nx), up.reshape(ny, nx)


def grid_for(lo, hi, cell: float = SPLASH_CELL, most: int = SPLASH_MAX) -> tuple:
    """(x0, y0, cell, nx, ny) of a grid over the box ``lo``…``hi`` (xy) with at most ``most`` cells."""
    w = max(float(hi[0] - lo[0]), cell)
    d = max(float(hi[1] - lo[1]), cell)
    cell = max(cell, math.sqrt(w * d / most))
    nx, ny = max(1, int(math.ceil(w / cell))), max(1, int(math.ceil(d / cell)))
    return float(lo[0]), float(lo[1]), cell, nx, ny


def splash_spots(heights, up, x0: float, y0: float, cell: float, water_z: float | None = None,
                 seed: int = SEED_SPLASH, min_up: float = SPLASH_UP) -> dict:
    """The spots where rain splashes: on every cell whose top faces up (``up`` ≥ ``min_up``), and on the water
    where nothing is above it (``water_z`` given). Jittered inside their cell (seeded). Returns ``p`` (m, 3),
    ``water`` (m,) 1 on the sea, ``r`` (m,), ``ph`` (m,)."""
    hh = np.asarray(heights, dtype=float)
    uu = np.asarray(up, dtype=float)
    ny, nx = hh.shape
    rng = np.random.default_rng(int(seed))
    jit = rng.random((ny, nx, 2)) - 0.5
    r = rng.random((ny, nx))
    ph = rng.random((ny, nx))
    gy, gx = np.mgrid[0:ny, 0:nx]
    px = x0 + (gx + 0.5 + 0.8 * jit[..., 0]) * cell
    py = y0 + (gy + 0.5 + 0.8 * jit[..., 1]) * cell
    solid = np.isfinite(hh) & (uu >= min_up)
    if water_z is not None:
        water = ~np.isfinite(hh) | (hh < water_z)
    else:
        water = np.zeros_like(solid)
    use = solid | water
    z = np.where(solid, hh, water_z if water_z is not None else 0.0)
    p = np.stack([px[use], py[use], z[use]], axis=1)
    return {"p": p, "water": (water & ~solid)[use].astype(float), "r": r[use], "ph": ph[use]}


def splash_age(t: float, ph, period: float = SPLASH_PERIOD):
    """How far through its cycle each spot is (0 … 1); a splash shows while age < LIFE / period."""
    return np.mod(float(t) / period + np.asarray(ph, dtype=float), 1.0)


# ---------------------------------------------------------------------------
# the flag
# ---------------------------------------------------------------------------

FLAG_NU, FLAG_NV = 24, 12          # points along the flag and up its hoist


def flag_size(model_size: float) -> tuple:
    """(pole height, flag length, flag height) in metres for a model of this size (its largest side)."""
    pole = min(max(0.06 * float(model_size), 2.5), 7.0)
    length = 0.42 * pole
    return pole, length, length * 2.0 / 3.0


def flag_lift(wind_ms: float) -> float:
    """0 = the flag hangs limp … 1 = it flies straight out (about Bft 5 and up)."""
    x = min(max((float(wind_ms) - 0.5) / (9.0 - 0.5), 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def flag_frequency(wind_ms: float, length: float) -> float:
    """Flapping frequency (Hz): grows with the wind, falls with the flag's length (Strouhal-like, f ≈ 0.25 U / L),
    between 0.2 and 4 Hz."""
    return min(max(0.25 * float(wind_ms) / max(length, 0.1), 0.2), 4.0)


def flag_points(u, v, t: float, wind_ms: float, length: float, height: float) -> np.ndarray:
    """The flag's points in its own frame at time ``t``: x along the flag towards where the wind blows, y sideways,
    z up; the hoist edge on the pole (x = 0), its top at z = 0. ``u`` 0 (hoist) … 1 (fly end), ``v`` 0 (bottom) …
    1 (top). A travelling wave grows towards the fly end; in little wind the flag droops along the pole."""
    u = np.asarray(u, dtype=float)
    v = np.asarray(v, dtype=float)
    s = flag_lift(wind_ms)
    theta = (1.0 - s) * math.radians(78.0)              # droop of each horizontal fibre
    f = flag_frequency(wind_ms, length)
    lam = 0.9 * length
    amp = (0.04 + 0.10 * s) * length
    a = amp * u ** 1.3
    phase = 2.0 * math.pi * (u * length / lam - f * float(t)) + 0.6 * v
    y = a * np.sin(phase) + 0.3 * a * np.sin(2.0 * math.pi * 0.37 * f * float(t) + 2.1 * u)
    along = u * length
    x = along * math.cos(theta)
    z = (v - 1.0) * height - along * math.sin(theta)
    return np.stack([x, y, z], axis=-1)


def flag_heading(wind_x: float, wind_y: float) -> float:
    """The flag's heading (radians about z): it flies towards where the wind blows."""
    return math.atan2(float(wind_y), float(wind_x))


def flag_grid(nu: int = FLAG_NU, nv: int = FLAG_NV) -> tuple:
    """(u, v, faces) of the flag's mesh: (nu+1)(nv+1) points, quads."""
    uu, vv = np.meshgrid(np.linspace(0.0, 1.0, nu + 1), np.linspace(0.0, 1.0, nv + 1))
    faces = []
    w = nu + 1
    for j in range(nv):
        for i in range(nu):
            k = j * w + i
            faces.append((k, k + 1, k + 1 + w, k + w))
    return uu.ravel(), vv.ravel(), faces


def flag_place(lo, hi, stern_x: bool) -> tuple:
    """(x, y) where the pole stands: at the stern (+x end, middle) of a vessel, else at the back (+y) right corner
    of the model's box, just inside it."""
    lo = np.asarray(lo, dtype=float)
    hi = np.asarray(hi, dtype=float)
    if stern_x:
        return float(hi[0] - 0.04 * (hi[0] - lo[0])), float(0.5 * (lo[1] + hi[1]))
    return float(hi[0] - 0.05 * (hi[0] - lo[0])), float(hi[1] - 0.05 * (hi[1] - lo[1]))


# ---------------------------------------------------------------------------
# lightning (task 0299)
# ---------------------------------------------------------------------------

SEED_FLASH, SEED_BOLT, SEED_HAIL = 4091, 5091, 6091
LIGHTNING_GAP = 3.0                # s: the mean time between two flashes at lightning 1 (it grows as 1 / lightning)
FLASH_MIN_GAP = 1.0                # s: two flashes never come closer than this
# One flash in steps of 0.04 s: a lightning flash is a few return strokes 40–60 ms apart down the same channel
# (Rakov & Uman, "Lightning", 2003: 3–5 strokes, ~60 ms apart); the light flickers and dies within ~0.2 s.
FLASH_SHAPE = (1.0, 0.3, 0.85, 0.25, 0.6, 0.12, 0.0)
FLASH_STEP = 0.04
FLASH_LIFE = FLASH_STEP * (len(FLASH_SHAPE) - 1)
N_BOLTS = 4                        # bolts in the sky; a flash shows one of them (the ``bolt`` channel)
BOLT_DISTANCE = 900.0              # m from the model: inside the storm's 4 km visibility, far enough to look far
BOLT_TOP = 650.0                   # m: where the bolt leaves the cloud base
BOLT_SPREAD = 32.0                 # degrees: the bolts stand within ±this of the camera's view


def flash_shape(seconds) -> np.ndarray:
    """A flash's brightness ``seconds`` after it began (0 before it and after FLASH_LIFE), linear between the steps."""
    t = np.asarray(seconds, dtype=float) / FLASH_STEP
    out = np.interp(t, np.arange(len(FLASH_SHAPE), dtype=float), np.asarray(FLASH_SHAPE, dtype=float),
                    left=0.0, right=0.0)
    return np.where(t < 0.0, 0.0, out)


def flash_moments(rate, fps: float, seed: int = SEED_FLASH) -> list:
    """The frames (index into ``rate``, from 0) where a random flash starts, and its strength. ``rate`` = the
    ``lightning`` channel per frame (0 … 1). A flash may start in a frame with probability rate / mean gap (a Poisson
    process thinned by the rate, so the flashes thin out as the lightning fades and stop where it is 0); never two
    closer than FLASH_MIN_GAP. Strength 0.55 … 1, higher with more lightning. Same rates, same seed: same flashes."""
    r = np.clip(np.asarray(rate, dtype=float), 0.0, 1.0)
    rng = np.random.default_rng(int(seed))
    draw = rng.random(len(r))
    amp = rng.random(len(r))
    dt = 1.0 / max(float(fps), 1.0)
    p = r * dt / LIGHTNING_GAP
    out = []
    last = -1.0e9
    for i in range(len(r)):
        if r[i] <= 0.0 or (i - last) * dt < FLASH_MIN_GAP:
            continue
        if draw[i] < p[i]:
            out.append((i, 0.55 + 0.45 * r[i] * (0.6 + 0.4 * amp[i])))
            last = i
    return out


def flash_track(rate, fps: float, fixed=(), seed: int = SEED_FLASH) -> tuple:
    """(flash, bolt) per frame: the brightness of the flash now (0 … 1) and which bolt it shows (0 … N_BOLTS-1, held
    until the next flash). ``rate``: lightning per frame; ``fixed``: frame indices where a flash is wanted (set
    moments, strength 1, whatever the rate)."""
    n = len(rate)
    fps = max(float(fps), 1.0)                       # (fps 0 gave NaN: the independent tester)
    flash = np.zeros(n)
    bolt = np.zeros(n)
    starts = [(i, a) for i, a in flash_moments(rate, fps, seed)]
    starts += [(int(i), 1.0) for i in fixed if 0 <= int(i) < n]
    starts.sort()
    rng = np.random.default_rng(int(seed) + 1)
    which = rng.integers(0, N_BOLTS, size=max(len(starts), 1))
    frames = np.arange(n, dtype=float)
    for k, (i, a) in enumerate(starts):
        flash = np.maximum(flash, a * flash_shape((frames - i) / float(fps)))
        bolt[i:] = which[k]
    return np.clip(flash, 0.0, 1.0), bolt


def bolt_path(seed: int, height: float = BOLT_TOP) -> list:
    """One bolt as polylines in its own frame (x sideways, z up; the channel from z = ``height`` at the cloud base
    down to z = 0): the main channel of ~70 pieces, a random walk that keeps heading down, and 2–4 branches that
    leave it and die out half way. Seeded: the same seed, the same bolt."""
    rng = np.random.default_rng(int(seed))
    n = 70
    seg = height / n
    pts = [np.array([0.0, 0.0, height])]
    heading = np.array([0.0, 0.0, -1.0])
    for _ in range(n):
        turn = rng.normal(0.0, 0.55, 3)
        turn[2] = 0.0
        d = heading + turn
        d[2] = -abs(d[2]) - 0.35                     # always on the way down
        d = d / np.linalg.norm(d)
        p = pts[-1] + d * seg * (0.6 + 0.8 * rng.random())
        pts.append(p)
        if p[2] <= 0.0:
            break
    main = np.array(pts)
    main[-1, 2] = 0.0
    lines = [main]
    for _ in range(int(rng.integers(2, 5))):
        k = int(rng.integers(4, max(5, len(main) // 2)))
        q = [main[k]]
        side = rng.choice((-1.0, 1.0))
        for _ in range(int(rng.integers(8, 20))):
            d = np.array([side * (0.6 + 0.6 * rng.random()), rng.normal(0.0, 0.4), -(0.4 + rng.random())])
            q.append(q[-1] + d / np.linalg.norm(d) * seg * (0.5 + 0.7 * rng.random()))
            if q[-1][2] <= 0.0:
                break
        lines.append(np.array(q))
    return lines


def bolt_places(centre, view_az: float, base_z: float, n: int = N_BOLTS, distance: float = BOLT_DISTANCE) -> list:
    """Where the bolts stand: (x, y, z of the foot, the azimuth they are seen at) round ``centre`` (x, y) in a fan of
    ±BOLT_SPREAD about ``view_az`` (scene azimuth the camera looks along, degrees), each a little further than the
    one before, their feet at ``base_z``."""
    out = []
    for i in range(n):
        az = float(view_az) + (-1.0 + 2.0 * i / max(n - 1, 1)) * BOLT_SPREAD
        d = distance * (0.85 + 0.12 * i)
        a = math.radians(az)
        out.append((float(centre[0]) + d * math.cos(a), float(centre[1]) + d * math.sin(a), float(base_z), az))
    return out


# ---------------------------------------------------------------------------
# hail (task 0299)
# ---------------------------------------------------------------------------

HAIL_MM = 8.0                      # a hail stone's size (mm): small hail and ice pellets 5 … 10 mm
HAIL_DENSITY = 4.0                 # falling stones per m3 at hail 1
HAIL_BOX = (30.0, 30.0, 16.0)
BOUNCE_PERIOD = 0.9                # s between two stones hopping on one spot (at full hail)
BOUNCE_LIFE = 0.4                  # s a stone hops (one bounce up and down again)
GRAVITY = 9.81


def hail_speed(mm: float = HAIL_MM) -> float:
    """Fall speed (m/s) of a hail stone of ``mm`` diameter: Matson & Huggins (1980), v = 11.45 D^0.5 (D in cm):
    6 mm → 8.9 m/s, 10 mm → 11.5 m/s."""
    return 11.45 * math.sqrt(max(float(mm), 1.0) / 10.0)


def bounce_height(life: float = BOUNCE_LIFE) -> float:
    """How high a stone hops when it is in the air ``life`` seconds: v0 = g life / 2, h = v0² / 2g."""
    v0 = GRAVITY * life / 2.0
    return v0 * v0 / (2.0 * GRAVITY)


def bounce_z(age_s) -> np.ndarray:
    """A hopping stone's height (m) over its spot ``age_s`` seconds into its hop (0 outside 0 … BOUNCE_LIFE)."""
    t = np.asarray(age_s, dtype=float)
    v0 = GRAVITY * BOUNCE_LIFE / 2.0
    z = v0 * t - 0.5 * GRAVITY * t * t
    return np.where((t >= 0.0) & (t <= BOUNCE_LIFE), np.maximum(z, 0.0), 0.0)
