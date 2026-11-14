"""Vessel motion at sea (task 0085): heave, pitch and roll of a vessel from the waves of the sea (no Blender).

The visible sea is a sum of travelling sine waves (``blender/surroundings.py``): each wave has an amplitude ``a``
(m), a direction (dx, dy), a wave number ``k`` (2π / wavelength) and a phase; its height at a point of the sea is

    a * sin(k * (dx * x + dy * y) + phase - omega * t),   omega = sqrt(g * k)  (deep water)

The vessel lies along x (the stern at +x, the bow at -x, as on the Vessel deck) and feels each wave the way a hull
of length L and beam B does (``excitation``):

* **heave** = the wave's height averaged over the hull's rectangle: a sinc factor along and across, so a wave much
  shorter than the vessel averages out (a 124 m vessel ignores 13 m ripples) and a long swell lifts it whole;
* **pitch** = the slope of the best-fitting plane along the hull, **roll** = the same across it; the vessel lies on
  that plane (bow up when the sea rises towards the bow).

Heave and pitch follow the averaged sea directly (the vessel rises when a crest passes under it). Roll is a lightly
damped oscillator with its own natural period (default 11 s): waves near that period rock the vessel much more, so
roll dominates in a beam sea, as on a real vessel. Every channel stays a sum of sines of the sea's own waves, with
the sea's own phases, so the Blender side can play it with built-in sine modifiers (no Python: works with scripts
off and in the render queue).

The sea's own waves (13–55 m at Calm, periods 3–6 s) are too short to move a ship: with vessel motion on, the sea
gets a **long, low swell** (``swell``): eight waves of 6–15 s from the heading's side, spread up to ±70°
(the mix was tuned so the table below holds for a 64 m and a 124 m hull). Without vessel
motion nothing is added, so a project without it looks exactly as before.

**Sea states.** CALM and ROUGH have tables; the sea state WIND (task 0109: the sea follows the wind of Weather & time)
takes its numbers between them by its Beaufort force (``level``: Beaufort 3 = Calm, 6 = Rough, held at the ends).
Since task 0109 the sea's own waves come from a wind-wave spectrum (``core/sea.py``); at Calm and Rough they run
along the vessel from the bow.

**Sizes.** A sea state's numbers (``TARGETS``, peak over ten minutes, at the reference heading Bow quarter) hold for
every vessel: the raw motion of *this* vessel at the reference heading is worked out and each channel is scaled to
the state's number (``scales``). The heading then decides how the motion is shared: a beam sea rolls more, a head sea
pitches more. Calm follows the cable-lay reference study (0083, section 9): roll ±1–1.5° at 10–12 s, pitch
±0.3–0.6° at 6–8 s, heave ±0.2–0.4 m at 7–9 s. Rough is about three times that: roll ±4°, pitch ±1.5°, heave ±1.2 m
(a sea near the working limit of a motion-compensated vessel, Hs about 3.5 m). ``Strength`` scales it all (0–200 %).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import numpy as np

G = 9.81
T0 = 10.0                        # s added to the time the Blender driver gives (never a small number)

# heading of the vessel to the waves: (label, direction the swell travels in, degrees from +x, description)
# the bow points to -x, the starboard side to +y; "from the starboard bow" travels towards +x and -y
HEADINGS = {
    "HEAD": ("Head sea", 0.0, "The waves come straight at the bow: the vessel pitches, hardly rolls"),
    "BOW": ("Bow quarter", -45.0, "The waves come in at 45° on the bow: pitch and roll together (the usual "
                                  "working heading)"),
    "BEAM": ("Beam sea", -90.0, "The waves come from the side: the vessel rolls the most"),
    "STERN": ("Stern quarter", -135.0, "The waves come in at 45° on the stern: roll and some pitch"),
    "FOLLOWING": ("Following sea", 180.0, "The waves come from behind: the vessel pitches gently, hardly rolls"),
}
REFERENCE_HEADING = "BOW"

# peak over ten minutes at the reference heading, for every vessel size: degrees, degrees, metres
TARGETS = {
    "CALM": dict(roll=1.25, pitch=0.45, heave=0.30),
    "ROUGH": dict(roll=4.0, pitch=1.5, heave=1.2),
}
# what the motion is checked against (tests, PC check): peak over 120 s and the mean period (zero up-crossings)
TABLE = {
    "CALM": dict(roll=(1.0, 1.5), pitch=(0.3, 0.6), heave=(0.2, 0.4),
                 roll_s=(10.0, 12.0), pitch_s=(6.0, 8.0), heave_s=(7.0, 9.0)),
    "ROUGH": dict(roll=(3.0, 4.2), pitch=(1.0, 1.6), heave=(0.8, 1.3),
                  roll_s=(10.0, 12.0), pitch_s=(6.0, 8.0), heave_s=(7.0, 9.0)),
}
REFERENCE_SIZE = (124.0, 28.0)   # m: the cable-lay vessel of the reference study
MIN_LENGTH, MIN_BEAM = 20.0, 8.0

# the swell added to the sea when vessel motion is on: periods (s), share of the height, spread of the direction
SWELL_PERIODS = (6.3, 7.0, 7.8, 8.7, 9.7, 10.9, 12.4, 14.5)
SWELL_SHARE = (0.06, 1.29, 2.0, 0.30, 0.24, 0.52, 0.10, 0.55)
SWELL_SPREAD = (-50.0, 69.0, -23.0, 51.0, -27.0, -1.0, 25.0, -34.0)   # degrees from the heading's direction
SWELL_HEIGHT = {"CALM": 0.30, "ROUGH": 1.2}       # m: about the largest swell crest above the mean
ROLL_DAMPING = 0.03              # share of critical damping: a lightly damped roll
PITCH_PERIOD, PITCH_DAMPING = 6.5, 0.25   # pitch: a well damped oscillator (a 60-130 m hull)
WINDOW = 600.0                   # s: the peak a sea state's number stands for
SMALL = 0.004                    # a wave whose share of a channel is below this is left out


@dataclass(frozen=True)
class Wave:
    amp: float                   # m
    dx: float
    dy: float
    k: float                     # 1/m
    phase: float                 # rad

    @property
    def omega(self) -> float:
        return math.sqrt(G * self.k)

    @property
    def period(self) -> float:
        return 2 * math.pi / self.omega

    def as_tuple(self) -> tuple:
        return (self.amp, self.dx, self.dy, self.k, self.phase)


@dataclass
class Channel:
    """value(t) = base + sum(amp * sin(phase - omega * t))"""
    base: float = 0.0
    terms: list = field(default_factory=list)      # (amp, omega, phase)

    def value(self, t):
        t = np.asarray(t, float)
        v = np.full(t.shape, self.base, float)
        for a, w, p in self.terms:
            v += a * np.sin(p - w * t)
        return v

    def scaled(self, f: float, base: float | None = None) -> "Channel":
        return Channel(self.base if base is None else base, [(a * f, w, p) for a, w, p in self.terms])

    def trimmed(self, small: float = SMALL) -> "Channel":
        """Leave out waves whose share is too small to see (fewer modifiers in Blender)."""
        total = sum(abs(a) for a, _w, _p in self.terms)
        if total <= 0:
            return Channel(self.base, [])
        return Channel(self.base, [t for t in self.terms if abs(t[0]) >= small * total])


@dataclass
class Motion:
    """Heave (m), roll (rad, about x: starboard up) and pitch (rad, about y: the stern down) over time."""
    heave: Channel
    roll: Channel
    pitch: Channel

    def sample(self, t) -> dict:
        return {"heave": self.heave.value(t), "roll": self.roll.value(t), "pitch": self.pitch.value(t)}


def level(state: str, bft: float | None = None) -> float:
    """0 = Calm, 1 = Rough; the sea state WIND lies between by its Beaufort force (3 -> 0, 6 -> 1, held outside)."""
    if state == "WIND" and bft is not None:
        return min(max((float(bft) - 3.0) / 3.0, 0.0), 1.0)
    return 1.0 if state == "ROUGH" else 0.0


def targets(state: str, bft: float | None = None) -> dict:
    """The peaks the vessel moves with (``TARGETS``; WIND between Calm and Rough)."""
    if state in TARGETS:
        return TARGETS[state]
    f = level(state, bft)
    return {k: TARGETS["CALM"][k] + (TARGETS["ROUGH"][k] - TARGETS["CALM"][k]) * f for k in TARGETS["CALM"]}


def swell_height(state: str, bft: float | None = None) -> float:
    if state in SWELL_HEIGHT:
        return SWELL_HEIGHT[state]
    f = level(state, bft)
    return SWELL_HEIGHT["CALM"] + (SWELL_HEIGHT["ROUGH"] - SWELL_HEIGHT["CALM"]) * f


def waves_from_tuples(rows) -> list[Wave]:
    return [Wave(*map(float, r)) for r in rows]


def swell(state: str, heading: str, bft: float | None = None) -> list[Wave]:
    """The long, low swell that moves the vessel (added to the sea only when vessel motion is on)."""
    head = math.radians(HEADINGS.get(heading, HEADINGS[REFERENCE_HEADING])[1])
    rng = random.Random(85)
    share = np.array(SWELL_SHARE, float)
    amps = swell_height(state, bft) * share / share.sum() * 2.2
    out = []
    for T, a, spread in zip(SWELL_PERIODS, amps, SWELL_SPREAD):
        w = 2 * math.pi / T
        k = w * w / G
        ang = head + math.radians(spread)
        out.append(Wave(float(a), math.cos(ang), math.sin(ang), k, rng.uniform(0, 2 * math.pi)))
    return out


def _sinc(x):
    x = np.asarray(x, float)
    return np.where(np.abs(x) < 1e-6, 1.0 - x * x / 6.0, np.sin(x) / np.where(np.abs(x) < 1e-6, 1.0, x))


def _slope_fit(u):
    """Slope of the least-squares line through sin(u x / l) on -l … l, as a share of the slope at 0 (1 for u = 0)."""
    u = np.asarray(u, float)
    small = np.abs(u) < 1e-3
    us = np.where(small, 1.0, u)
    return np.where(small, 1.0 - u * u / 10.0, 3.0 * (np.sin(us) - us * np.cos(us)) / us ** 3)


def oscillator(omega: float, period: float, damping: float) -> tuple[float, float]:
    """Gain and phase lag (rad, >= 0) of a damped oscillator with natural ``period`` driven at ``omega``."""
    r = omega * period / (2 * math.pi)
    re, im = 1.0 - r * r, 2.0 * damping * r
    return 1.0 / math.hypot(re, im), math.atan2(im, re)


def raw(waves: list[Wave], length: float, beam: float, centre=(0.0, 0.0), roll_period: float = 11.0) -> Motion:
    """The vessel's motion from the waves, before a sea state's scale. ``centre`` = the hull's middle in the sea's
    own coordinates (x, y), so the phases match what the sea shows there."""
    L, B = max(length, 1.0) / 2, max(beam, 0.5) / 2
    heave, roll, pitch = Channel(), Channel(), Channel()
    cx, cy = centre
    for wv in waves:
        kx, ky = wv.k * wv.dx, wv.k * wv.dy
        phi = kx * cx + ky * cy + wv.phase
        w = wv.omega
        sx, sy = float(_sinc(kx * L)), float(_sinc(ky * B))
        heave.terms.append((wv.amp * sx * sy, w, phi))
        # slopes are cos(phi - w t) = sin(phi + pi/2 - w t)
        slope_x = wv.amp * kx * float(_slope_fit(kx * L)) * sy
        slope_y = wv.amp * ky * float(_slope_fit(ky * B)) * sx
        gain_p, lag_p = oscillator(w, PITCH_PERIOD, PITCH_DAMPING)
        pitch.terms.append((-slope_x * gain_p, w, phi + math.pi / 2 + lag_p))   # sea higher at the stern: it rises
        gain, lag = oscillator(w, roll_period, ROLL_DAMPING)
        roll.terms.append((slope_y * gain, w, phi + math.pi / 2 + lag))
    return Motion(heave, roll, pitch)


def peak(values) -> float:
    v = np.asarray(values, float)
    return float(np.max(np.abs(v - v.mean()))) if v.size else 0.0


def mean_period(values, dt: float) -> float:
    """Mean period from the zero up-crossings (s); 0 when it never crosses."""
    v = np.asarray(values, float)
    v = v - v.mean()
    ups = np.nonzero((v[:-1] < 0) & (v[1:] >= 0))[0]
    if len(ups) < 2:
        return 0.0
    return float((ups[-1] - ups[0]) * dt / (len(ups) - 1))


def measure(motion: Motion, seconds: float = 120.0, dt: float = 0.04, start: float = 0.0) -> dict:
    """Peaks (roll and pitch in degrees, heave in m) and mean periods (s) over ``seconds``."""
    t = start + np.arange(0.0, seconds, dt)
    s = motion.sample(t)
    return {"roll": math.degrees(peak(s["roll"])), "pitch": math.degrees(peak(s["pitch"])), "heave": peak(s["heave"]),
            "roll_s": mean_period(s["roll"], dt), "pitch_s": mean_period(s["pitch"], dt),
            "heave_s": mean_period(s["heave"], dt)}


def scales(state: str, sea_waves: list[Wave], length: float, beam: float, roll_period: float = 11.0,
           bft: float | None = None) -> dict:
    """Factor per channel so that this vessel at the reference heading moves as the state's numbers say."""
    target = targets(state, bft)
    ref = raw(sea_waves + swell(state, REFERENCE_HEADING, bft), length, beam, (0.0, 0.0), roll_period)
    m = measure(ref, WINDOW, 0.05)
    return {ch: (target[ch] / m[ch] if m[ch] > 1e-9 else 0.0) for ch in ("roll", "pitch", "heave")}


@dataclass
class Settings:
    state: str = "CALM"
    heading: str = REFERENCE_HEADING
    strength: float = 1.0        # 0 … 2
    length: float = REFERENCE_SIZE[0]
    beam: float = REFERENCE_SIZE[1]
    roll_period: float = 11.0
    centre: tuple = (0.0, 0.0)   # the hull's middle in the sea's coordinates
    bft: float | None = None     # the wind's Beaufort force (sea state WIND only)


def motion(st: Settings, sea_waves: list[Wave]) -> Motion:
    """The vessel's motion in a sea state: the sea's own waves + the swell, scaled to the state's numbers."""
    length, beam = max(st.length, MIN_LENGTH), max(st.beam, MIN_BEAM)
    f = scales(st.state, sea_waves, length, beam, st.roll_period, st.bft)
    m = raw(sea_waves + swell(st.state, st.heading, st.bft), length, beam, st.centre, st.roll_period)
    k = max(0.0, float(st.strength))
    return Motion(m.heave.scaled(f["heave"] * k).trimmed(), m.roll.scaled(f["roll"] * k).trimmed(),
                  m.pitch.scaled(f["pitch"] * k).trimmed())


def summary(state: str, strength: float, roll_deg: float) -> str:
    """Panel header: 'Calm · roll ±1.2°'."""
    name = {"CALM": "Calm", "ROUGH": "Rough", "WIND": "From the wind"}.get(state, state.title())
    if strength <= 0:
        return f"{name} · still"
    return f"{name} · roll ±{roll_deg:.1f}°"


KEY_VERSION = 2              # of the motion's maths: 2 = the waves of task 0109 (an older rig is built again, 0121)


def key(st: Settings) -> str:
    """What the motion depends on (rebuild when it changes)."""
    k = (f"v{KEY_VERSION}|{st.state}|{st.heading}|{st.strength:.4f}|{st.length:.3f}|{st.beam:.3f}|{st.roll_period:.3f}|"
         f"{st.centre[0]:.3f}|{st.centre[1]:.3f}")
    return k + (f"|{st.bft:.3f}" if st.state == "WIND" and st.bft is not None else "")
