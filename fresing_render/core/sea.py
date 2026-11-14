"""The sea (task 0109): waves from a wind-wave spectrum, white caps from the wind, the water's colours. No Blender.

This is the **one place** the sea is defined: ``blender/surroundings.py`` turns these numbers into Geometry Nodes
(the waves near the machine) and the water shader (normals to the horizon, white caps), the vessel motion of task
0085 reads the same waves, and a later Web 3D task can copy the formulas to the web page. Every function here gives
exactly what the shader computes (apart from the lacy texture inside a white cap, which only changes its brightness).

**Waves.** The sea is a sum of travelling sine waves ("components"), each a tuple ``(amp, dx, dy, k, phase)`` – the
same tuple ``surroundings._waves`` always returned::

    height(x, y, t) = sum  amp * sin(k * (dx * x + dy * y) + phase - omega * t),   omega = sqrt(g * k)  (deep water)

The amplitudes come from a wind-wave **spectrum**:

* JONSWAP (Hasselmann et al. 1973, "Measurements of wind-wave growth and swell decay during the Joint North Sea
  Wave Project", Dt. Hydrogr. Z. A8(12)) for a sea limited by its fetch (``FETCH`` = 100 km, a typical North Sea
  fetch): alpha = 0.076 X^-0.22, omega_p = 22 (g / U10) X^-0.33, X = g F / U10^2, peak enhancement gamma = 3.3;
* Pierson–Moskowitz (Pierson & Moskowitz 1964, J. Geophys. Res. 69(24)) once the sea is fully developed:
  alpha = 0.0081, omega_p = 0.877 g / U19.5, gamma = 1; U19.5 = 1.026 U10 (Stewart 2008, "Introduction to Physical
  Oceanography", ch. 16). Its significant wave height is Hs = 0.21 U19.5^2 / g.

  gamma eases from 3.3 to 1 as the fetch-limited peak approaches the fully developed one (our choice, so the height
  grows smoothly with the wind instead of jumping where the two forms meet).

The directions spread round the wind with the cos-2s law of Mitsuyasu et al. (1975, J. Phys. Oceanogr. 5(4)):
D(theta) ~ cos^(2s)((theta - theta_wind) / 2), s = 10 (omega / omega_p)^5 below the peak and 10 (omega /
omega_p)^-2.5 above it (s_max = 10: wind waves, as Goda recommends) – the waves near the peak run with the wind,
short ones go every way, so crests are short and nothing lines up into stripes. ``N_COMPONENTS`` = 28 frequencies
between 0.6 and 5 times the peak, each at a random place in its band, a random direction drawn from the spreading
law and a random phase (seeded: the same sea every time). The bands follow 70 % sqrt(S) + 30 % even in log: most
components sit near the peak, so no two or three waves carry the height (about 16 equal waves' worth), and the
short ones are close enough together that none carries more than a tenth of the slope (a single short wave showed
as parallel ripples). The field's correlation with itself 124 m or 1 km away stays low (``correlation``); no
visible repeat from any height. Ripples shorter than the shortest component are the shader's (a noise bump near
the camera; not part of the height or the foam).

At Calm (Beaufort 3, 4.4 m/s) this gives Hs 0.43 m and 17 m waves (the sea is fully developed); at Rough
(Beaufort 6, 12.3 m/s) Hs 2.4 m and 66 m waves – today's Rough sea had Hs ~2.3 m and 70 m waves; Beaufort 9 gives
Hs 4.2 m. (The WMO's "probable" heights for open ocean are 0.6, 3 and 7 m: a 100 km fetch is a smaller sea.)

**White caps.** The share of the sea covered by white caps follows Monahan & O'Muircheartaigh (1980, "Optimal
power-law description of oceanic whitecap coverage dependence on wind speed", J. Phys. Oceanogr. 10(12),
2094-2099): W = 3.84e-6 U10^3.41 (W as a fraction; about 0.06 % at Beaufort 3, 2 % at Beaufort 6, 16 % at
Beaufort 9). Where on the sea they are is a **foam field** F(x, y, t), roughly a standard normal variable:

    F = (w_q q + w_c c + w_p P + w_s S) / N

* q = height / sigma_height – the crests of the waves;
* c = downward acceleration / sigma (sum amp min(omega, 2.5 omega_p)^2 sin(...)) – steep, sharp crests (a wave
  breaks when its crest accelerates downward faster than a fraction of g: Longuet-Higgins 1969; Snyder & Kennedy
  1983 built whitecap models on it); this term carries the shorter waves riding on the long crests (capped at 2.5 x
  the peak frequency: a ripple's sharpness does not make a white cap, and the shortest waves would draw dashes);
* P = a patch field: six slow cosines of 0.5–1.8 wavelengths that drift with the wind (3 % of the wind speed, the
  foam's drift) and change in 5–10 s – groups of breaking crests appear, live a few seconds and fade;
* S = streaks along the wind (four cosines whose crests lie within ±10° of the wind, 6–27 m apart, each wandering
  sideways – its phase bent by a slow sine along the wind – so the lines meander and break up), weight 0 below
  Beaufort 6.5 rising to 0.6 at Beaufort 8 (wind streaks are a gale's mark on the Beaufort scale);
* N makes F's variance 1 (q and c are correlated: their covariance is in N).

No Blender noise is used in F: Python and the shader give the same numbers. A point is white where
``foam = smoothstep(threshold, threshold + EDGE, F)`` and "covered" where foam >= 0.5;
:func:`foam_threshold` is calibrated by sampling F over 3 km x 3 km and ten minutes so the covered share equals
Monahan's W. The shader multiplies the white by a lacy texture (brightness only).
"""

from __future__ import annotations

import functools
import math
import random
from dataclasses import dataclass

import numpy as np

G = 9.81
STATES = {"CALM": 3.0, "ROUGH": 6.0}       # the sea's two quick choices as Beaufort forces
DEFAULT_TOWARD = 0.0                       # degrees from +x the wind sea runs towards at Calm / Rough: from the bow
#                                            (a working vessel keeps its bow into the weather; the vessel lies along x)
FETCH = 100_000.0                          # m
N_COMPONENTS = 28
SEED = 107                                  # (the vessel motion tables of task 0085 hold with it: tests)
OMEGA_LO, OMEGA_HI = 0.6, 5.0              # the components' range, x the peak frequency
EVEN_SHARE = 0.3                           # share of the bands spread evenly in log (the rest follows sqrt(S))
S_MAX = 10.0                               # cos-2s spreading at the peak
U195 = 1.026                               # U19.5 / U10
ALPHA_PM = 0.0081
GAMMA_J = 3.3

# white caps
MONAHAN_A, MONAHAN_B = 3.84e-6, 3.41
EDGE = 0.35                                # soft edge of a white cap, in units of F
W_Q, W_C, W_P = 0.75, 0.6, 0.8             # weights of crest height, crest sharpness, patches
CREST_CAP = 2.5                            # crest sharpness counts waves up to this x the peak frequency
PATCH_N = 6
PATCH_LENGTHS = (0.5, 0.65, 0.85, 1.1, 1.4, 1.8)     # x the peak wavelength
PATCH_PERIODS = (5.0, 6.3, 7.1, 8.2, 9.0, 10.0)      # s: how fast a patch changes
DRIFT = 0.03                               # foam drifts at 3 % of the wind speed
STREAK_SPACING = (6.0, 10.0, 17.0, 27.0)   # m between wind streaks
STREAK_MEANDER = (45.0, 90.0)              # m: a streak wanders sideways over this length along the wind
STREAK_MAX = 0.6                           # the streaks' weight in F at full strength
STREAK_FROM, STREAK_FULL = 6.5, 8.0        # Beaufort
THRESHOLD_MAX = 8.0                        # no white caps at all

# colours (linear RGB)
DEEP = (0.0045, 0.020, 0.028)              # deep water seen from above: dark blue-green (the North Sea)
SCATTER = (0.016, 0.085, 0.075)            # light through the thin top of a crest (added, scaled by the crest)
FOAM = (0.80, 0.83, 0.85)                  # white caps, hull foam and the wake
ROUGHNESS = (0.02, 0.09)                   # the water's gloss near the camera … at 3 km (smaller waves average out)


# ---------------------------------------------------------------------------
# wind
# ---------------------------------------------------------------------------

def bft_to_ms(bft: float) -> float:
    from .weather import bft_to_ms as f
    return f(bft)


# ---------------------------------------------------------------------------
# the spectrum
# ---------------------------------------------------------------------------

def peak(u10: float, fetch: float | None = FETCH) -> tuple[float, float, float]:
    """(omega_p rad/s, alpha, gamma) of the sea in a wind of ``u10`` m/s; ``fetch`` None: fully developed."""
    u = max(float(u10), 0.3)
    wp_pm = 0.877 * G / (U195 * u)
    if fetch is None:
        return wp_pm, ALPHA_PM, 1.0
    x = G * float(fetch) / (u * u)
    wp_j = 22.0 * G / u * x ** -0.33
    if wp_j <= wp_pm:
        return wp_pm, ALPHA_PM, 1.0
    alpha = max(0.076 * x ** -0.22, ALPHA_PM)
    ease = min(max((wp_j / wp_pm - 1.0) / 0.5, 0.0), 1.0)
    return wp_j, alpha, 1.0 + (GAMMA_J - 1.0) * ease


def spectrum(omega, u10: float, fetch: float | None = FETCH):
    """Energy spectrum S(omega) (m^2 s) of the sea in a wind of ``u10`` m/s."""
    w = np.maximum(np.asarray(omega, float), 1e-6)
    wp, alpha, gamma = peak(u10, fetch)
    sig = np.where(w <= wp, 0.07, 0.09)
    r = np.exp(-((w - wp) ** 2) / (2.0 * sig * sig * wp * wp))
    return alpha * G * G * w ** -5 * np.exp(-1.25 * (wp / w) ** 4) * gamma ** r


def hs_pm(u10: float) -> float:
    """Significant wave height of a fully developed sea (Pierson–Moskowitz): 0.21 U19.5^2 / g."""
    return 4.0 * math.sqrt(ALPHA_PM / 1.25 / 4.0 / 0.877 ** 4) * (U195 * u10) ** 2 / G


def hs_spectrum(u10: float, fetch: float | None = FETCH) -> float:
    """Hs = 4 sqrt(m0) of the continuous spectrum."""
    wp = peak(u10, fetch)[0]
    w = np.geomspace(0.3 * wp, 40.0 * wp, 20000)
    return 4.0 * math.sqrt(float(np.trapezoid(spectrum(w, u10, fetch), w)))


def spreading_s(omega: float, wp: float) -> float:
    r = omega / wp
    return S_MAX * (r ** 5 if r < 1.0 else r ** -2.5)


def _draw_direction(rng: random.Random, s: float) -> float:
    """An angle (rad, from the mean direction) drawn from cos^(2s)(theta / 2) by its inverse cumulative sum."""
    th = np.linspace(-math.pi, math.pi, 721)
    d = np.cos(th / 2.0) ** (2.0 * max(s, 0.05))
    cdf = np.cumsum(d)
    cdf /= cdf[-1]
    return float(np.interp(rng.random(), cdf, th))


def _bands(u: float, fetch: float | None, n: int) -> np.ndarray:
    """Band edges between 0.6 and 5 x the peak: each holds the same share of a density that is 70 % sqrt(S) and
    30 % even in log (most bands near the peak, yet short waves close enough together)."""
    wp = peak(u, fetch)[0]
    w = np.geomspace(OMEGA_LO * wp, OMEGA_HI * wp, 4000)
    d1 = np.sqrt(spectrum(w, u, fetch))
    d2 = 1.0 / w
    d = (1.0 - EVEN_SHARE) * d1 / np.trapezoid(d1, w) + EVEN_SHARE * d2 / np.trapezoid(d2, w)
    cdf = np.concatenate([[0.0], np.cumsum((d[1:] + d[:-1]) / 2.0 * np.diff(w))])
    return np.interp(np.linspace(0.0, 1.0, n + 1), cdf / cdf[-1], w)


@functools.lru_cache(maxsize=64)
def _components(wind_bft: float, toward_deg: float, seed: int, n: int, fetch: float | None) -> tuple:
    u = bft_to_ms(wind_bft)
    if u <= 0.05:
        return ()
    wp, _alpha, _gamma = peak(u, fetch)
    rng = random.Random(seed)
    edges = _bands(u, fetch, n)
    base = math.radians(toward_deg)
    out = []
    for i in range(n):
        lo, hi = edges[i], edges[i + 1]
        w = lo + (hi - lo) * rng.random()
        amp = math.sqrt(2.0 * float(spectrum(w, u, fetch)) * (hi - lo))
        ang = base + _draw_direction(rng, spreading_s(w, wp))
        ph = rng.uniform(0.0, 2.0 * math.pi)
        out.append((amp, math.cos(ang), math.sin(ang), w * w / G, ph))
    return tuple(out)


def components(wind_bft: float, toward_deg: float = DEFAULT_TOWARD, seed: int = SEED, n: int = N_COMPONENTS,
               fetch: float | None = FETCH) -> list[tuple[float, float, float, float, float]]:
    """The sea's waves in a wind of Beaufort ``wind_bft`` blowing towards ``toward_deg`` (degrees from +x):
    ``n`` tuples (amp m, dx, dy, k 1/m, phase rad), longest first. The same arguments give the same sea."""
    return list(_components(round(float(wind_bft), 4), round(float(toward_deg), 4) % 360.0, int(seed), int(n),
                            None if fetch is None else float(fetch)))


def of_state(state: str, wind_bft: float | None = None, toward_deg: float | None = None) -> list[tuple]:
    """The waves of a sea state: CALM / ROUGH (fixed: Beaufort 3 / 6, the default direction) or WIND (the given
    strength and direction)."""
    if state == "WIND" and wind_bft is not None:
        return components(wind_bft, DEFAULT_TOWARD if toward_deg is None else toward_deg)
    return components(STATES.get(state, STATES["CALM"]), DEFAULT_TOWARD)


def correlation(comps, lag_x: float, lag_y: float) -> float:
    """The sea's height correlated with itself ``(lag_x, lag_y)`` metres away (same moment): 1 = the same."""
    e = sum(a * a for a, *_ in comps)
    if e <= 0.0:
        return 0.0
    return sum(a * a * math.cos(k * (dx * lag_x + dy * lag_y)) for a, dx, dy, k, _ph in comps) / e


def omega(k: float) -> float:
    return math.sqrt(G * k)


def hs(comps) -> float:
    """Significant wave height 4 sigma of a set of components."""
    return 4.0 * math.sqrt(sum(a * a for a, *_ in comps) / 2.0)


def peak_wavelength(comps) -> float:
    """Wavelength (m) of the component with the most energy."""
    if not comps:
        return 0.0
    a, _dx, _dy, k, _ph = max(comps, key=lambda c: c[0] * c[0] / max(c[3], 1e-9) ** 0.5)
    return 2.0 * math.pi / k


def mean_direction(comps) -> tuple[float, float]:
    """Energy-weighted direction the waves run in (unit x, y); +x without waves."""
    vx = sum(a * a * dx for a, dx, dy, k, ph in comps)
    vy = sum(a * a * dy for a, dx, dy, k, ph in comps)
    n = math.hypot(vx, vy)
    return (vx / n, vy / n) if n > 1e-12 else (1.0, 0.0)


# ---------------------------------------------------------------------------
# height and slope
# ---------------------------------------------------------------------------

def _phase(x, y, t, c):
    a, dx, dy, k, ph = c
    return k * (dx * x + dy * y) + ph - math.sqrt(G * k) * t


def height(x, y, t, comps):
    """Height of the sea (m) at (x, y) (m, the sea's own coordinates) and time t (s)."""
    x, y, t = (np.asarray(v, float) for v in (x, y, t))
    h = np.zeros(np.broadcast(x, y, t).shape)
    for c in comps:
        h += c[0] * np.sin(_phase(x, y, t, c))
    return h


def slope(x, y, t, comps):
    """(dh/dx, dh/dy) at (x, y, t). The water's normal is (-dh/dx, -dh/dy, 1) normalised."""
    x, y, t = (np.asarray(v, float) for v in (x, y, t))
    sx = np.zeros(np.broadcast(x, y, t).shape)
    sy = np.zeros_like(sx)
    for c in comps:
        a, dx, dy, k, ph = c
        cs = a * k * np.cos(_phase(x, y, t, c))
        sx += cs * dx
        sy += cs * dy
    return sx, sy


def acceleration(x, y, t, comps):
    """Downward acceleration of the surface (m/s^2): positive at crests, large at sharp ones (every wave; the foam
    field caps it, see ``foam_field``)."""
    x, y, t = (np.asarray(v, float) for v in (x, y, t))
    out = np.zeros(np.broadcast(x, y, t).shape)
    for c in comps:
        out += c[0] * G * c[3] * np.sin(_phase(x, y, t, c))
    return out


# ---------------------------------------------------------------------------
# white caps
# ---------------------------------------------------------------------------

def whitecap_coverage(u10: float) -> float:
    """Share of the sea covered by white caps (0 … 1) in a wind of ``u10`` m/s at 10 m: Monahan &
    O'Muircheartaigh (1980), W = 3.84e-6 U10^3.41."""
    u = max(float(u10), 0.0)
    return min(MONAHAN_A * u ** MONAHAN_B, 1.0)


def streak_weight(bft: float) -> float:
    b = (float(bft) - STREAK_FROM) / (STREAK_FULL - STREAK_FROM)
    b = min(max(b, 0.0), 1.0)
    return STREAK_MAX * b * b * (3.0 - 2.0 * b)


@dataclass(frozen=True)
class Term:
    """value = c_sin * sin(p) + c_cos * cos(p),  p = kx x + ky y + wt t + phase
    + m_amp * sin(m_kx x + m_ky y + m_wt t + m_phase)   (a streak's meander; 0 for the rest)"""
    kx: float
    ky: float
    wt: float
    phase: float
    c_sin: float
    c_cos: float
    m_amp: float = 0.0
    m_kx: float = 0.0
    m_ky: float = 0.0
    m_wt: float = 0.0
    m_phase: float = 0.0

    def angle(self, x, y, t):
        p = self.kx * x + self.ky * y + self.wt * t + self.phase
        if self.m_amp:
            p = p + self.m_amp * np.sin(self.m_kx * x + self.m_ky * y + self.m_wt * t + self.m_phase)
        return p


@dataclass(frozen=True)
class FoamField:
    terms: tuple            # Term rows: the sea's components first (sin), then patches and streaks (cos)
    sigma: float            # sigma of the height
    sigma_acc: float
    norm: float
    toward: tuple           # unit (x, y) the wind blows towards
    bft: float


def foam_field(comps, wind_bft: float, toward=None, seed: int = SEED) -> FoamField:
    """The foam field F of a sea (its terms; see the module's text). ``toward``: unit (x, y) of the wind, or a
    direction in degrees; None = the waves' own mean direction."""
    comps = list(comps)
    if toward is None:
        tx, ty = mean_direction(comps)
    elif isinstance(toward, (int, float)):
        tx, ty = math.cos(math.radians(toward)), math.sin(math.radians(toward))
    else:
        n = math.hypot(*toward) or 1.0
        tx, ty = toward[0] / n, toward[1] / n
    sig = math.sqrt(sum(a * a for a, *_ in comps) / 2.0) or 1.0
    k_cap = (CREST_CAP ** 2) * 2.0 * math.pi / max(peak_wavelength(comps), 0.1)      # (2.5 omega_p)^2 / g
    sharp = [G * min(k, k_cap) for _a, _dx, _dy, k, _ph in comps]                      # omega^2, capped
    sig_c = math.sqrt(sum((a * w2) ** 2 for (a, *_), w2 in zip(comps, sharp)) / 2.0) or 1.0
    cov = sum(a * a * w2 for (a, *_), w2 in zip(comps, sharp)) / 2.0 / (sig * sig_c)
    ws = streak_weight(wind_bft)
    norm = math.sqrt(W_Q * W_Q + W_C * W_C + 2.0 * W_Q * W_C * cov + W_P * W_P + ws * ws)
    terms = []
    for (a, dx, dy, k, ph), w2 in zip(comps, sharp):
        e = a * (W_Q / sig + W_C * w2 / sig_c) / norm
        terms.append(Term(k * dx, k * dy, -math.sqrt(G * k), ph, e, 0.0))
    u = bft_to_ms(wind_bft)
    vx, vy = DRIFT * u * tx, DRIFT * u * ty
    lam = max(peak_wavelength(comps), 4.0)
    rng = random.Random(seed + 1)
    cp = W_P * math.sqrt(2.0 / PATCH_N) / norm
    for i in range(PATCH_N):
        ang = rng.uniform(0.0, 2.0 * math.pi)
        kk = 2.0 * math.pi / (PATCH_LENGTHS[i] * lam)
        kx, ky = kk * math.cos(ang), kk * math.sin(ang)
        nu = 2.0 * math.pi / PATCH_PERIODS[i] * (1.0 if rng.random() < 0.5 else -1.0)
        terms.append(Term(kx, ky, -(kx * vx + ky * vy) - nu, rng.uniform(0.0, 2.0 * math.pi), 0.0, cp))
    if ws > 0.0:
        cs = ws * math.sqrt(2.0 / len(STREAK_SPACING)) / norm
        for d in STREAK_SPACING:
            ang = math.atan2(ty, tx) + math.pi / 2.0 + math.radians(rng.uniform(-10.0, 10.0))
            kk = 2.0 * math.pi / d
            kx, ky = kk * math.cos(ang), kk * math.sin(ang)
            km = 2.0 * math.pi / rng.uniform(*STREAK_MEANDER)
            mx, my = km * tx, km * ty
            terms.append(Term(kx, ky, -(kx * vx + ky * vy), rng.uniform(0.0, 2.0 * math.pi), 0.0, cs,
                              rng.uniform(1.2, 2.2), mx, my, -(mx * vx + my * vy), rng.uniform(0.0, 2.0 * math.pi)))
    return FoamField(tuple(terms), sig, sig_c, norm, (tx, ty), float(wind_bft))


def foam_value(x, y, t, field: FoamField):
    """F at (x, y, t): about a standard normal variable; high on steep crests in a patch."""
    x, y, t = (np.asarray(v, float) for v in (x, y, t))
    f = np.zeros(np.broadcast(x, y, t).shape)
    for tm in field.terms:
        p = tm.angle(x, y, t)
        if tm.c_sin:
            f += tm.c_sin * np.sin(p)
        if tm.c_cos:
            f += tm.c_cos * np.cos(p)
    return f


def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def foam(x, y, t, wind_bft: float, comps, toward=None, threshold: float | None = None):
    """White caps 0 … 1 at (x, y, t) – exactly the shader's coverage (before its lacy texture)."""
    field = foam_field(comps, wind_bft, toward)
    th = foam_threshold(wind_bft) if threshold is None else threshold
    return smoothstep(th, th + EDGE, foam_value(x, y, t, field))


def _sample_points(n: int, seed: int, size: float = 3000.0, seconds: float = 600.0):
    r = np.random.default_rng(seed)
    return r.uniform(0.0, size, n), r.uniform(0.0, size, n), r.uniform(0.0, seconds, n)


def _normal_quantile(p: float) -> float:
    """x with P(Z > x) = p for a standard normal Z (bisection on erfc: no SciPy)."""
    lo, hi = -10.0, 40.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if 0.5 * math.erfc(mid / math.sqrt(2.0)) > p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


CALIBRATION_SAMPLES = 120_000


@functools.lru_cache(maxsize=256)
def _threshold(bft: float) -> float:
    w = whitecap_coverage(bft_to_ms(bft))
    if w <= 0.0:
        return THRESHOLD_MAX
    comps = components(bft)
    if not comps:
        return THRESHOLD_MAX
    field = foam_field(comps, bft)
    f = np.sort(foam_value(*_sample_points(CALIBRATION_SAMPLES, 7), field))
    n = len(f)
    floor = 30.0 / n                         # below this the sample's tail is too thin: go on as a normal tail
    if w >= floor:
        q = float(np.quantile(f, 1.0 - w))
    else:
        q = float(np.quantile(f, 1.0 - floor)) + _normal_quantile(w) - _normal_quantile(floor)
    return min(q - EDGE / 2.0, THRESHOLD_MAX)


def foam_threshold(bft: float) -> float:
    """The foam field's threshold at Beaufort ``bft``: the share of the sea with foam >= 0.5 is Monahan's
    coverage. Lower = more foam (``core/weather.derive`` writes it into the ``foam`` channel)."""
    return _threshold(round(min(max(float(bft), 0.0), 12.0), 2))


def coverage(bft: float, comps=None, threshold: float | None = None, n: int = 60_000, seed: int = 21) -> float:
    """The share of the sea with foam >= 0.5, measured on ``n`` random points (other points than the calibration's)."""
    comps = components(bft) if comps is None else comps
    if not comps:
        return 0.0
    field = foam_field(comps, bft)
    th = foam_threshold(bft) if threshold is None else threshold
    f = foam_value(*_sample_points(n, seed, 2500.0, 900.0), field)
    return float(np.mean(f >= th + EDGE / 2.0))


# ---------------------------------------------------------------------------
# hull foam and the wake (the shader's rules, for the web page and the tests)
# ---------------------------------------------------------------------------

KNOT = 0.514444                            # m/s
KELVIN = math.radians(19.47)               # half angle of a ship's wave pattern
ARMS = 0.22                                # how white the Kelvin arms are (the turbulent wake: 1)


def hull_foam_width(bft: float, speed_knots: float = 0.0) -> float:
    """How far (m) foam reaches out from the hull at the waterline: a little in a calm sea, more in wind and at
    speed."""
    return 0.6 + 0.55 * max(float(bft), 0.0) + 0.35 * max(float(speed_knots), 0.0)


def hull_foam_strength(bft: float, speed_knots: float = 0.0) -> float:
    """How white the hull foam is (0 … 1): faint in a calm sea, full from Beaufort 7 or at 6 knots."""
    return float(0.3 + 0.7 * max(smoothstep(1.5, 7.0, bft), smoothstep(0.0, 6.0, speed_knots)))


def wake(xb, y, half_beam: float, speed_knots: float):
    """Foam of the wake (0 … 1, before the texture) at ``xb`` metres behind the stern and ``y`` from the middle
    line: a turbulent band as wide as the hull that spreads and fades, and faint Kelvin arms at 19.5°."""
    xb, y = np.asarray(xb, float), np.abs(np.asarray(y, float))
    v = max(float(speed_knots), 0.0)
    if v <= 0.0:
        return np.zeros(np.broadcast(xb, y).shape)
    length = 12.0 * v + 20.0
    behind = xb > 0.0
    xp = np.maximum(xb, 0.0)
    w = half_beam * (0.85 + 0.09 * np.sqrt(xp))
    band = (1.0 - smoothstep(0.55 * w, w, y)) * np.exp(-xp / length)
    arm_d = np.abs(y - (half_beam + xp * math.tan(KELVIN)))
    arms = ARMS * (1.0 - smoothstep(0.0, 1.5 + 0.03 * xp, arm_d)) * np.exp(-xp / (0.7 * length))
    on = smoothstep(0.0, 2.0, v)
    return np.where(behind, np.maximum(band, arms) * on, 0.0)


# ---------------------------------------------------------------------------
# under the water (task 0081): the seabed, the water's clarity, the cut-away behind the stern
# ---------------------------------------------------------------------------
#
# The cut-away takes a box of water away behind the stern (air: the camera sees the cable and the seabed clearly).
# Round it lies a ring of water as a volume: whatever is seen through one of the box's walls – the hull below the
# waterline, the seabed further away, the cable beyond the box – fades into the water's own colour with its distance
# behind the wall. The volume only absorbs and glows (no scattering): a homogeneous medium, which Cycles works out in
# one step (no ray marching, no noise):
#
#     seen = behind * T + colour * (1 - T),   T = exp(-sigma * d),   sigma = 3 / clarity
#
# "Clarity" is the distance at which a thing behind water has faded to 5 % (e^-3) – roughly how far a diver sees.

CLARITY_RANGE = (2.0, 40.0)                # m: very murky … very clear (the slider's range)
CLARITY_FADED = 3.0                        # sigma * clarity: 5 % left at the clarity's distance
CUT_GROW = 4.0                             # the water ring reaches this x the clarity out from the box (e^-12: gone)
CUT_TOP = 0.08                             # m: the ring's top lies this much under the water's surface
CUT_EDGE = 0.12                            # m: the bright line along the top of the box's walls
CUT_DARK = (0.35, 40.0)                    # the box's walls darken with depth: this much at this depth (m)
SEABED_EXTENT = 1000.0                     # m round the model
SEABED_SINK = 0.06                         # m: in Detailed the plain seabed lies this much under the rippled patch
# the water's colour under water in full daylight (linear RGB, radiance): what a thing far behind a wall turns into.
# A North Sea green-blue; lighter than DEEP (the sea seen from above, mostly the sky's reflection on dark water).
UNDERWATER = (0.028, 0.115, 0.125)        # (task 0081, after the first demo pictures: clearer than the sea seen from
#                                           above – a cut-away shows the water as an illustration does)
NIGHT_LIGHT = 0.003                        # what is left of the light at night (the moon; the camera opens up)
OVERCAST_LIGHT = 0.45                      # a grey sky gives this share of a clear day's light
SAND = ((0.21, 0.175, 0.12), (0.11, 0.10, 0.075))   # the seabed: wet sand … silt (linear RGB)
RIPPLE_LENGTH = 0.9                        # m between sand ripples
RIPPLE_HEIGHT = 0.03                       # m: their amplitude (Detailed: real geometry; Simple: only the shading)


def absorption(clarity: float) -> float:
    """Absorption sigma (per metre) of water with this clarity (m): a thing at the clarity's distance has 5 % left."""
    c = min(max(float(clarity), 0.1), 1000.0)
    return CLARITY_FADED / c


def transmittance(distance, clarity: float):
    """What is left of a thing ``distance`` metres behind water: e^(-sigma d)."""
    return np.exp(-absorption(clarity) * np.maximum(np.asarray(distance, float), 0.0))


def fade(distance, clarity: float):
    """How far a thing ``distance`` metres behind water has faded into the water's colour: 1 - e^(-sigma d)."""
    return 1.0 - transmittance(distance, clarity)


def light_level(day: float = 1.0, clouds: float = 0.0) -> float:
    """The light under water, 1 = a clear day: ``day`` 0 (night) … 1 and the cloud cover (Weather & time's channels
    ``day`` and ``clouds``; the material works out the same formula from them)."""
    day = min(max(float(day), 0.0), 1.0)
    clouds = min(max(float(clouds), 0.0), 1.0)
    return day * (1.0 - (1.0 - OVERCAST_LIGHT) * clouds) + NIGHT_LIGHT


def sky_light(strength: float = 1.0, overcast: bool = False, elevation_deg: float = 45.0) -> float:
    """The same without Weather & time: the panel's Light strength, Sun or Overcast and the sun's height."""
    el = math.radians(min(max(float(elevation_deg), 0.0), 90.0))
    return max(float(strength), 0.0) * (OVERCAST_LIGHT if overcast else 1.0) * (0.3 + 0.7 * math.sin(el)) / (
        0.3 + 0.7 * math.sin(math.radians(45.0)))


def underwater_colour(light: float = 1.0) -> tuple[float, float, float]:
    """The water's colour (linear radiance) at this light level: dark at night."""
    return tuple(c * max(float(light), 0.0) for c in UNDERWATER)


def seen_through(behind, distance, clarity: float, light: float = 1.0):
    """What the camera sees of a thing (its own radiance ``behind``, RGB) ``distance`` metres behind a wall of the
    cut-away: behind * T + the water's colour * (1 - T)."""
    t = transmittance(distance, clarity)
    behind = np.asarray(behind, float)
    return behind * t + np.asarray(underwater_colour(light)) * (1.0 - t)


def seabed_ripples(x, y):
    """Height (m) of the sand ripples at (x, y) in the seabed's own coordinates (the shader's and the Detailed mesh's
    formula): crests across the current, slightly bent, longer swells of sand under them."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    k = 2 * math.pi / RIPPLE_LENGTH
    bend = 0.9 * np.sin(0.21 * y + 0.4) + 0.5 * np.sin(0.13 * x - 0.07 * y)
    r = np.sin(k * (0.96 * x + 0.28 * y) + bend)
    swell = 0.12 * np.sin(0.23 * x + 0.9) * np.sin(0.17 * y + 0.3)
    return RIPPLE_HEIGHT * r + swell
