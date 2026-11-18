"""The crane classes of the Lifting lane (task 0191): parameters, the layout in the model's frame, the joints and the
forward kinematics of the hook – plain Python, no OpenCascade, no Blender.

Model frame (every kind): STEP in mm, Z up, the ground at z = 0, the slew axis is the z axis, the boom points along +x
in the CAD pose (y across). Joint values are 0 in the CAD pose; degrees and mm, as the render-kit sheet writes them
(``site/render_kit/projects.py``). A joint that ``rides_on`` another moves with it (its axis is carried); a joint that
``follows`` another takes ``ratio`` x that joint's value – the app's own rules (4 Motion > Joints).

The numbers are invented, in the range of public brochures for each size class (study 0180 section 2), never one
maker's. Masses in t; the makers work out where each mass group's centre of gravity is from its solids.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

KINDS = {"AT": "mobile_crane", "CC": "crawler_crane", "KB": "knuckle_boom_crane"}
KIND_WORDS = {"AT": "mobile telescopic crane (all-terrain)", "CC": "crawler lattice-boom crane",
              "KB": "knuckle-boom crane (truck-mounted loader crane)"}
UP = (0.0, 0.0, 1.0)
DOWN = (0.0, 0.0, -1.0)
LUFF_AXIS = (0.0, -1.0, 0.0)     # about -y: a positive angle raises a boom that points along +x


# ---------------------------------------------------------------------------------------------------------------------
# Parameter sets

@dataclass(frozen=True)
class Mobile:
    """Mobile telescopic crane (all-terrain): carrier on axles, 4 outriggers, slewing superstructure, box boom of N
    sections (section 1 = base), luff cylinder, hook block on the hoist rope."""
    name: str
    rated: float                  # t at the shortest radius (the class number)
    axles: int
    wheel_r: float                # mm
    width: float                  # carrier width, mm
    sections: int                 # boom sections, base included
    L0: float                     # boom retracted: luff pin -> head sheave centre along the boom, mm
    Lmax: float                   # boom fully out, mm
    boom_w: float                 # base section outside width x height, mm
    boom_h: float
    wall: float                   # box wall, mm
    gap: float                    # gap between nested sections, mm
    spread: tuple                 # outrigger spreads across (pad centre to pad centre), mm: (full, middle, narrow)
    span_x: float                 # front -> rear outrigger pads, mm
    counterweights: tuple         # t, the chart steps; the model carries the largest
    cw_x: float                   # mm behind the slew axis: the counterweight's centre
    mass_carrier: float           # t, with the outriggers
    mass_upper: float             # t, superstructure without counterweight and boom
    mass_boom: float              # t, every section + head
    hook_mass: float              # t
    hook_falls: int
    line_pull: float              # t per fall (the hoist's max line pull)
    block_h: float                # hook block height (top of its sheaves -> hook saddle), mm
    luff_max: float = 82.0        # deg
    wind_max: float = 9.8         # m/s, the charts' wind speed (3 s gust at the boom head)
    kind: str = "AT"


@dataclass(frozen=True)
class Crawler:
    """Crawler lattice-boom crane: two tracks (links + shoes), carbody, slewing upper works with counterweight and
    gantry, lattice boom luffed by pendants (drawn as two pendant bars that slide), optional luffing jib."""
    name: str
    rated: float
    boom_cad: float               # model's main boom: foot pin -> head sheave centre, mm
    boom_lengths: tuple           # main boom lengths of the charts, m
    boom_w: float                 # lattice section (square), chord centre to chord centre, mm
    jib_cad: float = 0.0          # model's luffing jib, mm (0 = none)
    jib_lengths: tuple = ()       # m, jib charts (with the boom at jib_boom)
    jib_boom: float = 0.0         # m, main boom of the jib charts (= boom_cad / 1000)
    pitch: float = 250.0          # track link pitch, mm
    teeth: int = 12               # sprocket teeth
    run_links: int = 30           # links on the ground run
    shoe_w: float = 1000.0        # mm
    gauge: float = 6000.0         # track centre to track centre, mm
    counterweights: tuple = ()    # t (largest in the model)
    cw_x: float = 6000.0          # mm behind the slew axis
    mass_lower: float = 0.0       # t, carbody + tracks
    mass_upper: float = 0.0       # t, without counterweight
    mass_boom: float = 0.0        # t, the model's boom
    mass_jib: float = 0.0
    hook_mass: float = 0.0
    hook_falls: int = 6
    line_pull: float = 12.0
    block_h: float = 1800.0
    luff_cad: float = 60.0        # deg: the boom's angle in the CAD pose
    luff_min: float = 30.0
    luff_max: float = 84.0
    jib_angle: float = -20.0      # deg: the jib against the boom's line in the CAD pose
    wind_max: float = 9.8
    kind: str = "CC"


@dataclass(frozen=True)
class Knuckle:
    """Knuckle-boom (loader) crane on a truck: column (slew), main boom + cylinder, outer boom + cylinder at the
    knuckle, hydraulic extensions, 4 stabilisers, a small winch and hook."""
    name: str
    moment: float                 # t·m, the class number (gross lifting moment)
    axles: int
    wheel_r: float
    width: float
    main_len: float               # column pin -> knuckle pin, mm
    outer_len: float              # knuckle pin -> tip (extensions in), mm
    extensions: int
    ext_stroke: float             # mm per extension
    boom_w: float                 # main boom box width x height, mm
    boom_h: float
    spread: tuple                 # stabiliser spreads (full, narrow), mm
    mass_truck: float             # t
    mass_column: float            # t (column + base)
    mass_main: float              # t
    mass_outer: float             # t (outer boom + extensions)
    hook_mass: float
    block_h: float
    line_pull: float              # t, the winch (one fall)
    max_cap: float                # t at the shortest outreach
    main_cad: float = 20.0        # deg: main boom angle in the CAD pose
    main_range: tuple = (0.0, 75.0)
    knuckle_cad: float = -40.0    # deg: outer boom relative to the main boom (0 = in line, negative = folded down)
    knuckle_range: tuple = (-90.0, 0.0)
    wind_max: float = 12.5
    kind: str = "KB"


CLASSES: dict = {}


def _add(c):
    CLASSES[c.name] = c
    return c


# Mobile: GVW AT-40 ~36 t (3 axles), AT-100 ~60 t (5), AT-250 ~72 t (6), AT-500 ~96 t (8)
_add(Mobile("AT-40", 40.0, 3, 600.0, 2550.0, 4, 10800.0, 34000.0, 600.0, 800.0, 10.0, 20.0,
            (6000.0, 4600.0, 3400.0), 5400.0, (0.0, 4.0, 8.0), 2900.0, 22.0, 6.0, 8.0, 0.45, 4, 4.5, 900.0))
_add(Mobile("AT-100", 100.0, 5, 690.0, 2750.0, 7, 12800.0, 60000.0, 850.0, 1150.0, 12.0, 25.0,
            (7600.0, 5800.0, 4200.0), 7200.0, (0.0, 15.0, 30.0), 3700.0, 33.0, 10.0, 17.0, 1.0, 8, 6.5, 1400.0))
_add(Mobile("AT-250", 250.0, 6, 690.0, 3000.0, 7, 15200.0, 70000.0, 1050.0, 1450.0, 14.0, 30.0,
            (8800.0, 6600.0, 4800.0), 8400.0, (0.0, 40.0, 80.0), 4400.0, 40.0, 12.0, 20.0, 2.3, 12, 8.5, 2000.0))
_add(Mobile("AT-500", 500.0, 8, 690.0, 3000.0, 8, 16500.0, 84000.0, 1250.0, 1700.0, 16.0, 30.0,
            (10000.0, 7600.0, 5400.0), 9400.0, (0.0, 80.0, 165.0), 5100.0, 52.0, 16.0, 28.0, 4.5, 16, 10.0, 2600.0))

# Crawler: base machine (no counterweight) CC-100 ~ 75 t, CC-300 ~ 160 t, CC-750 ~ 330 t, CC-1600 ~ 650 t
_add(Crawler("CC-100", 100.0, 36000.0, (18, 24, 30, 36, 42, 48, 54, 60), 1500.0, pitch=200.0, teeth=12, run_links=28,
             shoe_w=800.0, gauge=4300.0, counterweights=(20.0, 38.0), cw_x=4600.0, mass_lower=36.0, mass_upper=26.0,
             mass_boom=11.0, hook_mass=1.3, hook_falls=8, line_pull=8.0, block_h=1500.0))
_add(Crawler("CC-300", 300.0, 54000.0, (24, 30, 36, 42, 48, 54, 60, 72, 84), 2100.0, pitch=250.0, teeth=12,
             run_links=30, shoe_w=1000.0, gauge=5900.0, counterweights=(60.0, 100.0), cw_x=6200.0, mass_lower=78.0,
             mass_upper=52.0, mass_boom=28.0, hook_mass=3.2, hook_falls=14, line_pull=12.0, block_h=2100.0))
_add(Crawler("CC-750", 750.0, 72000.0, (36, 48, 60, 72, 84, 96, 108, 120), 2800.0, jib_cad=42000.0,
             jib_lengths=(30, 42, 54), jib_boom=72.0, pitch=300.0, teeth=12, run_links=31, shoe_w=1200.0,
             gauge=7300.0, counterweights=(160.0, 240.0), cw_x=7800.0, mass_lower=165.0, mass_upper=110.0,
             mass_boom=70.0, mass_jib=24.0, hook_mass=7.5, hook_falls=20, line_pull=17.0, block_h=2800.0))
_add(Crawler("CC-1600", 1600.0, 96000.0, (48, 60, 72, 84, 96, 108, 120, 132, 144), 3600.0, jib_cad=54000.0,
             jib_lengths=(42, 54, 66), jib_boom=96.0, pitch=350.0, teeth=12, run_links=32, shoe_w=1500.0,
             gauge=9100.0, counterweights=(360.0, 520.0), cw_x=9800.0, mass_lower=330.0, mass_upper=220.0,
             mass_boom=150.0, mass_jib=48.0, hook_mass=15.0, hook_falls=28, line_pull=25.0, block_h=3400.0))

# Knuckle-boom: truck + crane; outreach with every extension out ~10.5 / 16 / 21 / 26 m
_add(Knuckle("KB-20", 20.0, 2, 520.0, 2500.0, 3300.0, 2600.0, 3, 1550.0, 260.0, 340.0, (5200.0, 2600.0), 9.5,
             0.7, 0.6, 0.9, 0.05, 450.0, 1.2, 8.0))
_add(Knuckle("KB-50", 50.0, 3, 540.0, 2550.0, 4300.0, 3400.0, 5, 1700.0, 340.0, 440.0, (6400.0, 3200.0), 15.0,
             1.4, 1.3, 2.2, 0.1, 600.0, 2.0, 16.0))
_add(Knuckle("KB-100", 100.0, 4, 540.0, 2550.0, 5300.0, 4200.0, 6, 1950.0, 420.0, 540.0, (8600.0, 4300.0), 26.0,
             2.6, 2.4, 4.2, 0.25, 750.0, 3.5, 30.0))
_add(Knuckle("KB-200", 200.0, 4, 560.0, 2550.0, 6300.0, 5000.0, 7, 2250.0, 520.0, 680.0, (10200.0, 5100.0), 32.0,
             4.4, 4.2, 7.6, 0.4, 900.0, 5.0, 52.0))


def kind_of(name: str) -> str:
    return CLASSES[name].kind


def names(kind: str | None = None) -> list[str]:
    return [n for n, c in CLASSES.items() if kind is None or c.kind == kind]


# ---------------------------------------------------------------------------------------------------------------------
# Geometry helpers (mm)

def rot(axis, deg: float) -> np.ndarray:
    """3 x 3 rotation about a unit axis (right hand)."""
    a = np.asarray(axis, float)
    a = a / np.linalg.norm(a)
    t = math.radians(deg)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def M4(R=None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    M = np.eye(4)
    if R is not None:
        M[:3, :3] = R
    M[:3, 3] = t
    return M


def about(point, axis, deg: float) -> np.ndarray:
    """4 x 4: a turn of ``deg`` about the line through ``point`` along ``axis``."""
    p = np.asarray(point, float)
    R = rot(axis, deg)
    return M4(R, p - R @ p)


def along(axis, dist: float) -> np.ndarray:
    a = np.asarray(axis, float)
    return M4(None, a / np.linalg.norm(a) * dist)


def boom_dir(deg: float) -> np.ndarray:
    """A boom's direction in the x-z plane at an angle above horizontal."""
    t = math.radians(deg)
    return np.array([math.cos(t), 0.0, math.sin(t)])


def boom_up(deg: float) -> np.ndarray:
    """Square to ``boom_dir`` in the x-z plane, pointing up."""
    t = math.radians(deg)
    return np.array([-math.sin(t), 0.0, math.cos(t)])


def fit_cylinder(pivot, barrel_pin, rod_pin, angles, axis=LUFF_AXIS, rod_r=100.0, barrel_r=140.0) -> dict:
    """Pin-to-pin length of a cylinder whose rod pin turns about ``pivot`` with a joint (``angles`` = the joint's range
    relative to the CAD pose, deg) while its barrel pin stays; the barrel and rod lengths that keep the rod in the barrel
    over the whole range (an overlap of 2 barrel radii at full stroke, the rod's end clear of the barrel's eye when
    closed). Raises ValueError when no cylinder fits (the range is too large for the pins)."""
    pv, b, r = (np.asarray(v, float) for v in (pivot, barrel_pin, rod_pin))
    ds = []
    for a in np.linspace(angles[0], angles[1], 61):
        q = (about(pv, axis, a) @ np.r_[r, 1.0])[:3]
        ds.append(float(np.linalg.norm(q - b)))
    dmin, dmax = min(ds), max(ds)
    eye, cap, overlap, gap = 1.5 * rod_r, 1.5 * barrel_r, 2.0 * barrel_r, 0.25 * rod_r
    barrel_len = dmin - eye - gap                   # from the barrel pin to its gland (clear of the rod's eye)
    rod_len = (dmax - dmin) + eye + gap + overlap   # from the rod pin into the barrel: overlap left at full stroke
    if dmin - rod_len < cap:
        raise ValueError(f"no cylinder fits: {dmin:.0f} … {dmax:.0f} mm pin to pin (ratio {dmax / dmin:.2f})")
    return {"dmin": dmin, "dmax": dmax, "cad": float(np.linalg.norm(r - b)), "rod_len": rod_len,
            "barrel_len": barrel_len, "rod_r": rod_r, "barrel_r": barrel_r, "stroke": dmax - dmin}


# ---------------------------------------------------------------------------------------------------------------------
# Layouts: every point the makers, the rig and the kinematics share (mm, CAD pose)

@dataclass
class Layout:
    c: object
    pts: dict = field(default_factory=dict)        # named points / numbers
    joints: list = field(default_factory=list)     # the sheet's joints (render-kit form)
    cylinders: list = field(default_factory=list)  # {"name", "barrel", "rod", "barrel_pin", "rod_pin", fit}
    hook_asm: str = "HOOK BLOCK.ASM"
    hook_point: tuple = (0.0, 0.0, 0.0)            # CAD pose: the hook's saddle (where the sling goes)
    poses: list = field(default_factory=list)

    def joint(self, name: str) -> dict:
        return next(j for j in self.joints if j["name"] == name)


def _j(name, kind, parts, point, direction, limits=None, rides_on=None, follows=None, ratio=None, **extra):
    d = {"name": name, "kind": kind, "parts": list(parts), "point": [round(float(v), 4) for v in point],
         "direction": [round(float(v), 6) for v in direction], "rides_on": rides_on,
         "limits": None if limits is None else [round(float(limits[0]), 4), round(float(limits[1]), 4)]}
    if follows:
        d["follows"], d["ratio"] = follows, float(ratio)
    d.update(extra)
    return d


def _axle_xs(front: float, out_x, n: int, r: float) -> list:
    """Axle positions: the front half from the front back, the rear half from just ahead of the rear outrigger box
    forward, 2r + 270 apart; never closer than r + 350 to an outrigger box."""
    step = 2 * r + 270.0
    nf = (n + 1) // 2
    xs = [front - 1.6 * r - 700.0 - k * step for k in range(nf)]
    xs += [out_x[1] + r + 420.0 + k * step for k in range(n - nf)]
    xs = sorted(xs)
    for x in xs:
        for k in out_x:
            if abs(x - k) < r + 350.0:
                raise ValueError(f"axle at {x:.0f} too close to the outrigger box at {k:.0f}")
    for x0, x1 in zip(xs, xs[1:]):
        if x1 - x0 < 2 * r + 150.0:
            raise ValueError(f"axles at {x0:.0f} and {x1:.0f} overlap")
    return xs


STAGES = 2           # outrigger / stabiliser beams: two stages, each moving half the stroke


def _outrigger_joints(J, part, lead, word, leg_part, leg_lead, leg_word, out_x, beam_w, beam_z, pad_in, out_ext,
                      pad_z0):
    """Four two-stage beams and their jacks: the front-left beam's first stage leads (``lead``), every other stage
    follows it with ratio 1 along its own outward direction; the front-left jack leads its three."""
    stroke = out_ext / STAGES
    for fr in ("F", "R"):
        for side in ("L", "R"):
            x = (out_x[0] if fr == "F" else out_x[1]) + (0.5 if side == "L" else -0.5) * beam_w
            yd = 1.0 if side == "L" else -1.0
            first = fr == "F" and side == "L"
            name = lead if first else f"{word} {fr}{side}"
            J.append(_j(name, "SLIDE", [f"{part} BEAM {fr}{side}.ASM"], (x, 0, beam_z), (0, yd, 0), (0.0, stroke),
                        **({} if first else {"follows": lead, "ratio": 1.0})))
            J.append(_j(f"{word} {fr}{side} 2", "SLIDE", [f"{part} BEAM {fr}{side} 2.ASM"], (x, 0, beam_z),
                        (0, yd, 0), (0.0, stroke), rides_on=name, follows=lead, ratio=1.0))
            jn = leg_lead if first else f"{leg_word} {fr}{side}"
            J.append(_j(jn, "SLIDE", [f"{leg_part} {fr}{side}.ASM"], (x, yd * pad_in, beam_z), DOWN, (0.0, pad_z0),
                        rides_on=f"{word} {fr}{side} 2", **({} if first else {"follows": leg_lead, "ratio": 1.0})))


def mobile_layout(c: Mobile) -> Layout:
    L = Layout(c)
    p = L.pts
    deck = 2 * c.wheel_r + 140.0                       # chassis top
    cab_top = deck + 1650.0
    zp = cab_top + c.boom_h / 2 + 140.0                # luff pin: the boom rests just above the carrier cab
    xp = -0.075 * c.L0                                 # luff pin behind the slew axis
    turn_top = deck + 260.0
    n = c.sections
    s = (c.Lmax - c.L0) / (n - 1)                      # stroke of every telescopic section
    rs = 0.34 * (c.boom_h - 2 * (n - 1) * (c.wall + c.gap))     # head sheave radius (fits the tip section)
    sheave = np.array([xp + c.L0, 0.0, zp])
    d0 = rs + 700.0 + c.block_h                        # sheave centre -> hook saddle at hoist 0
    block_w = 0.5 * c.boom_w + 250.0
    front = sheave[0] - block_w / 2 - 450.0            # the hook block hangs in front of the bumper
    a = c.span_x / 2
    out_x = (a, -a)                                    # front / rear outrigger boxes
    rear = min(-c.cw_x - 900.0, -a - 750.0)
    axles = _axle_xs(front, out_x, c.axles, c.wheel_r)
    pad_in = c.width / 2 + 180.0                       # pad centre across, outriggers in
    out_ext = c.spread[0] / 2 - pad_in
    if out_ext <= 300:
        raise ValueError(f"{c.name}: outrigger stroke {out_ext:.0f} mm")
    pad_z0 = 0.62 * c.wheel_r                          # pad underside above the ground, jacks up
    beam_z = deck - 420.0
    p.update(deck=deck, cab_top=cab_top, xp=xp, zp=zp, turn_top=turn_top, stroke=s, sheave=sheave.tolist(),
             sheave_r=rs, d0=d0, block_w=block_w, front=front, rear=rear, axles=axles, out_x=out_x, pad_in=pad_in,
             out_ext=out_ext, pad_z0=pad_z0, beam_z=beam_z, beam_w=0.16 * c.width + 60.0)
    # the boom: section k (1 = base) – outside size, its span along the boom (a = 0 at the luff pin)
    a_front = c.L0 - rs - 250.0
    secs = []
    for k in range(1, n + 1):
        sh = 2 * (k - 1) * (c.wall + c.gap)
        front_k = a_front + (k - 1) * 45.0
        rear_k = -0.06 * c.L0 if k == 1 else 450.0 + (k - 2) * 25.0
        secs.append({"k": k, "w": c.boom_w - sh, "h": c.boom_h - sh, "a0": rear_k, "a1": front_k})
    p["sections"] = secs
    # the hoist winch behind the boom's foot, low on the superstructure; moved back where the base section's rear end
    # would swing into it while the boom luffs (task 0204: found by the clash check of a made crane's own motion)
    frame_top = turn_top + 300.0
    wr = 0.22 * c.boom_h + 120.0
    l_cw = 0.45 * c.cw_x + 600.0
    wx = (-c.cw_x + l_cw / 2 + xp) / 2
    wz = frame_top + wr + 60.0
    sweep = math.hypot(-secs[0]["a0"], c.boom_h / 2) + wr + 80.0
    if math.hypot(wx - xp, wz - zp) < sweep and zp - wz < sweep:
        wx = min(wx, xp - math.sqrt(sweep ** 2 - (zp - wz) ** 2))
    if wx - wr < -c.cw_x + l_cw / 2 + 40.0:
        raise ValueError(f"{c.name}: no room for the hoist winch between the counterweight and the boom's foot")
    p["winch"] = (wx, wz, wr)
    for sct in secs[1:]:
        over = sct["a1"] - sct["a0"] - s
        if over < 0.15 * (sct["a1"] - sct["a0"]):
            raise ValueError(f"{c.name}: section {sct['k']} keeps only {over:.0f} mm in the one below at full stroke")
    # the luff cylinder: barrel pin low on the superstructure, rod pin under the base section
    a_q = 0.40 * c.L0
    rod_pin = np.array([xp + a_q, 0.0, zp - c.boom_h / 2 - 200.0])
    barrel_pin = np.array([xp + 0.07 * c.L0, 0.0, turn_top + 600.0])
    rr = 0.07 * c.boom_w + 40.0
    fit = fit_cylinder((xp, 0, zp), barrel_pin, rod_pin, (0.0, c.luff_max), rod_r=rr, barrel_r=1.45 * rr)
    L.cylinders.append({"name": "Luff cylinder", "barrel": ["LUFF CYLINDER BARREL"], "rod": ["LUFF CYLINDER ROD"],
                        "barrel_pin": {"point": barrel_pin.tolist(), "axis": [0.0, 1.0, 0.0],
                                       "carrier": "SUPERSTRUCTURE.ASM"},
                        "rod_pin": {"point": rod_pin.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "BOOM BASE.ASM"},
                        "fit": fit})
    hmax = zp + c.Lmax - d0 + 3000.0
    # joints
    J = L.joints
    J.append(_j("Slew", "ROTATE", ["SUPERSTRUCTURE.ASM"], (0, 0, turn_top), UP, (-180.0, 180.0)))
    J.append(_j("Luff", "ROTATE", ["BOOM BASE.ASM"], (xp, 0, zp), LUFF_AXIS, (0.0, c.luff_max), rides_on="Slew"))
    J.append(_j("Telescope", "SLIDE", ["BOOM SECTION 2.ASM"], (xp, 0, zp), (1, 0, 0), (0.0, s), rides_on="Luff"))
    for k in range(3, n + 1):
        J.append(_j(f"Telescope {k}", "SLIDE", [f"BOOM SECTION {k}.ASM"], (xp, 0, zp), (1, 0, 0), (0.0, s),
                    rides_on="Telescope" if k == 3 else f"Telescope {k - 1}", follows="Telescope", ratio=1.0))
    tip = "Telescope" if n == 2 else f"Telescope {n}"
    J.append(_j("Hook swing", "ROTATE", ["HOOK SWING.ASM"], sheave, LUFF_AXIS, None, rides_on=tip, follows="Luff",
                ratio=-1.0))
    J.append(_j("Hoist", "SLIDE", ["HOOK BLOCK.ASM"], sheave, DOWN, (0.0, hmax), rides_on="Hook swing"))
    _outrigger_joints(J, "OUTRIGGER", "Outriggers", "Outrigger", "JACK", "Jacks", "Jack", out_x, p["beam_w"],
                      beam_z, pad_in, out_ext, pad_z0)
    L.hook_point = (float(sheave[0]), 0.0, float(sheave[2] - d0))
    p["hmax"] = hmax
    # named poses (render-kit form: joints not named stay 0)
    tele_half = round(s / 2, 1)
    L.poses = [
        {"name": "Travel", "values": {}},
        {"name": "Set up", "values": {"Outriggers": out_ext / STAGES, "Jacks": pad_z0}},
        {"name": "Working", "values": {"Outriggers": out_ext / STAGES, "Jacks": pad_z0, "Luff": 60.0, "Telescope": tele_half,
                                       "Hoist": round(0.35 * hmax, 1)}},
        {"name": "Long reach", "values": {"Outriggers": out_ext / STAGES, "Jacks": pad_z0, "Luff": 35.0, "Telescope": s,
                                          "Slew": 90.0, "Hoist": round(0.25 * hmax, 1)}},
    ]
    return L


def crawler_track(c: Crawler) -> dict:
    """The track's loop (local x-z, track centre y = 0): pin centres one pitch apart, as ``demo_model.machines``."""
    R = c.pitch / (2 * math.sin(math.pi / c.teeth))
    hh = 0.32 * c.pitch                                # link plates reach this far in and out of the pin line
    shoe_t = 0.22 * c.pitch + 20.0                     # shoe plate + grouser under the link
    z_pin = hh + shoe_t                                # bottom run's pin line (shoes on the ground)
    zs = z_pin + R                                     # sprocket centres
    a = c.run_links * c.pitch / 2
    pins = [(-a + k * c.pitch, zs - R) for k in range(c.run_links)]          # ground run, towards +x
    step = 2 * math.pi / c.teeth
    for k in range(c.teeth // 2):                                            # round the front idler, upwards
        t = -math.pi / 2 + k * step
        pins.append((a + R * math.cos(t), zs + R * math.sin(t)))
    pins += [(a - k * c.pitch, zs + R) for k in range(c.run_links)]          # top run, back
    for k in range(c.teeth // 2):                                            # round the rear sprocket, down
        t = math.pi / 2 + k * step
        pins.append((-a + R * math.cos(t), zs + R * math.sin(t)))
    return {"R": R, "hh": hh, "shoe_t": shoe_t, "z_pin": z_pin, "zs": zs, "a": a, "pins": pins,
            "contact": c.run_links * c.pitch}


def crawler_layout(c: Crawler) -> Layout:
    L = Layout(c)
    p = L.pts
    tr = crawler_track(c)
    top = tr["zs"] + tr["R"] + tr["hh"] + 80.0         # carbody top: over the tracks' top run
    turn_top = top + 0.06 * c.boom_w + 260.0
    xp = 0.42 * c.boom_w + 500.0
    zp = turn_top + 0.45 * c.boom_w + 400.0
    W = c.boom_w
    rs = 0.30 * W
    p.update(track=tr, top=top, turn_top=turn_top, xp=xp, zp=zp, sheave_r=rs)
    th0 = c.luff_cad
    u, n_up = boom_dir(th0), boom_up(th0)
    pv = np.array([xp, 0.0, zp])
    head = pv + c.boom_cad * u
    p["boom_head"] = head.tolist()
    J = L.joints
    J.append(_j("Travel", "SLIDE", ["CRANE.ASM"], (0, 0, 0), (1, 0, 0), (-30000.0, 30000.0)))
    J.append(_j("Slew", "ROTATE", ["UPPER WORKS.ASM"], (0, 0, turn_top), UP, (-180.0, 180.0), rides_on="Travel"))
    J.append(_j("Luff", "ROTATE", ["LATTICE BOOM.ASM"], pv, LUFF_AXIS, (c.luff_min - th0, c.luff_max - th0),
                rides_on="Slew"))
    # gantry top (the pendants' upper pins) and the boom tip lugs (their lower pins)
    gantry = np.array([-0.55 * c.cw_x, 0.0, zp + 0.9 * W + 2600.0])
    tip_lug = pv + (c.boom_cad - 0.75 * W) * u + (0.5 * W + 0.06 * W + 150.0) * n_up
    p.update(gantry=gantry.tolist(), tip_lug=tip_lug.tolist())
    pend_y = 0.5 * W + 0.1 * W + 140.0
    pr = max(40.0, 0.025 * W)
    for side, y in (("L", pend_y), ("R", -pend_y)):
        b, r = gantry + (0, y, 0), tip_lug + (0, y, 0)
        fit = fit_cylinder(pv, b, r, (c.luff_min - th0, c.luff_max - th0), rod_r=pr, barrel_r=1.5 * pr)
        L.cylinders.append({"name": f"Boom pendant {side}", "barrel": [f"BOOM PENDANT BAR {side}"],
                            "rod": [f"BOOM PENDANT ROD {side}"],
                            "barrel_pin": {"point": b.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "UPPER WORKS.ASM"},
                            "rod_pin": {"point": r.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "LATTICE BOOM.ASM"},
                            "fit": fit})
    if c.jib_cad > 0:
        Wj = 0.55 * W
        jp = head - 0.42 * W * n_up                    # jib foot pin under the boom head
        ju = boom_dir(th0 + c.jib_angle)
        jib_tip = jp + c.jib_cad * ju
        rsj = 0.30 * Wj
        p.update(jib_pin=jp.tolist(), jib_tip=jib_tip.tolist(), jib_w=Wj, jib_sheave_r=rsj)
        jib_rng = (-55.0 - c.jib_angle, 5.0 - c.jib_angle)      # jib from 55° below the boom's line to 5° above it
        J.append(_j("Jib", "ROTATE", ["LUFFING JIB.ASM"], jp, LUFF_AXIS, jib_rng, rides_on="Luff"))
        strut = head + (0.9 * W + 0.12 * c.jib_cad) * n_up - 0.6 * W * u          # the jib strut's top (on the boom)
        jlug = jp + (c.jib_cad - 0.75 * Wj) * ju + (0.5 * Wj + 120.0) * boom_up(th0 + c.jib_angle)
        p.update(strut=strut.tolist(), jib_lug=jlug.tolist())
        jy = 0.5 * Wj + 0.1 * Wj + 120.0
        for side, y in (("L", jy), ("R", -jy)):
            b, r = strut + (0, y, 0), jlug + (0, y, 0)
            fit = fit_cylinder(jp, b, r, jib_rng, rod_r=0.8 * pr, barrel_r=1.2 * pr)
            L.cylinders.append({"name": f"Jib pendant {side}", "barrel": [f"JIB PENDANT BAR {side}"],
                                "rod": [f"JIB PENDANT ROD {side}"],
                                "barrel_pin": {"point": b.tolist(), "axis": [0.0, 1.0, 0.0],
                                               "carrier": "LATTICE BOOM.ASM"},
                                "rod_pin": {"point": r.tolist(), "axis": [0.0, 1.0, 0.0],
                                            "carrier": "LUFFING JIB.ASM"},
                                "fit": fit})
        sheave = jib_tip
        rs = rsj
        J.append(_j("Hook swing", "ROTATE", ["HOOK SWING.ASM"], sheave, LUFF_AXIS, None, rides_on="Jib",
                    follows="Luff", ratio=-1.0))
        J.append(_j("Hook swing 2", "ROTATE", ["HOOK SWING 2.ASM"], sheave, LUFF_AXIS, None, rides_on="Hook swing",
                    follows="Jib", ratio=-1.0))
        last = "Hook swing 2"
        reach = c.boom_cad + c.jib_cad
    else:
        sheave = head
        J.append(_j("Hook swing", "ROTATE", ["HOOK SWING.ASM"], sheave, LUFF_AXIS, None, rides_on="Luff",
                    follows="Luff", ratio=-1.0))
        last = "Hook swing"
        reach = c.boom_cad
    d0 = rs + 1200.0 + c.block_h
    hmax = zp + reach - d0 + 3000.0
    J.append(_j("Hoist", "SLIDE", ["HOOK BLOCK.ASM"], sheave, DOWN, (0.0, hmax), rides_on=last))
    p.update(sheave=sheave.tolist(), hook_sheave_r=rs, d0=d0, hmax=hmax)
    L.hook_point = (float(sheave[0]), 0.0, float(sheave[2] - d0))
    L.poses = [{"name": "Working", "values": {"Hoist": round(0.4 * hmax, 1)}},
               {"name": "Steep", "values": {"Luff": c.luff_max - th0 - 4.0, "Hoist": round(0.6 * hmax, 1)}},
               {"name": "Long reach", "values": {"Luff": c.luff_min - th0 + 5.0, "Slew": -60.0,
                                                 "Hoist": round(0.3 * hmax, 1), "Travel": 4000.0}}]
    if c.jib_cad > 0:
        L.poses[1]["values"]["Jib"] = 15.0
        L.poses[2]["values"]["Jib"] = -20.0
    return L


def knuckle_layout(c: Knuckle) -> Layout:
    L = Layout(c)
    p = L.pts
    deck = 2 * c.wheel_r + 280.0                       # truck frame top
    col_top = deck + 1350.0 + 0.6 * c.boom_h
    p1 = np.array([0.0, 0.0, col_top])                 # main boom pin (on the column's top, over the slew axis)
    a0, k0 = c.main_cad, c.knuckle_cad
    um, nm = boom_dir(a0), boom_up(a0)
    p2 = p1 + c.main_len * um                          # knuckle pin
    uo, no = boom_dir(a0 + k0), boom_up(a0 + k0)
    tip = p2 + c.outer_len * uo                        # the outer boom's tip (extensions in): the hook sheave
    rs = 0.30 * (c.boom_h - 2 * (c.extensions + 1) * 22.0)
    d0 = rs + 450.0 + c.block_h
    p.update(deck=deck, col_top=col_top, p1=p1.tolist(), p2=p2.tolist(), tip=tip.tolist(), sheave_r=rs, d0=d0)
    J = L.joints
    J.append(_j("Slew", "ROTATE", ["COLUMN.ASM"], (0, 0, deck + 300.0), UP, (-200.0, 200.0)))
    J.append(_j("Main boom", "ROTATE", ["MAIN BOOM.ASM"], p1, LUFF_AXIS,
                (c.main_range[0] - a0, c.main_range[1] - a0), rides_on="Slew"))
    J.append(_j("Knuckle", "ROTATE", ["OUTER BOOM.ASM"], p2, LUFF_AXIS,
                (c.knuckle_range[0] - k0, c.knuckle_range[1] - k0), rides_on="Main boom"))
    J.append(_j("Extension", "SLIDE", ["EXTENSION 1.ASM"], p2, uo, (0.0, c.ext_stroke), rides_on="Knuckle"))
    for k in range(2, c.extensions + 1):
        J.append(_j(f"Extension {k}", "SLIDE", [f"EXTENSION {k}.ASM"], p2, uo, (0.0, c.ext_stroke),
                    rides_on="Extension" if k == 2 else f"Extension {k - 1}", follows="Extension", ratio=1.0))
    last_ext = "Extension" if c.extensions == 1 else f"Extension {c.extensions}"
    J.append(_j("Hook swing", "ROTATE", ["HOOK SWING.ASM"], tip, LUFF_AXIS, None, rides_on=last_ext,
                follows="Main boom", ratio=-1.0))
    J.append(_j("Hook swing 2", "ROTATE", ["HOOK SWING 2.ASM"], tip, LUFF_AXIS, None, rides_on="Hook swing",
                follows="Knuckle", ratio=-1.0))
    hmax = 0.75 * (col_top + c.main_len + c.outer_len + c.extensions * c.ext_stroke)
    J.append(_j("Hoist", "SLIDE", ["HOOK BLOCK.ASM"], tip, DOWN, (0.0, hmax), rides_on="Hook swing 2"))
    # cylinders: main (column -> under the main boom), knuckle (on top of the main boom -> the outer boom's lever)
    q1 = p1 + 0.42 * c.main_len * um - (c.boom_h / 2 + 200.0) * nm
    b1 = np.array([0.45 * c.boom_w, 0.0, deck + 600.0])
    rr = 0.16 * c.boom_w + 15.0
    fit1 = fit_cylinder(p1, b1, q1, (c.main_range[0] - a0, c.main_range[1] - a0), rod_r=rr, barrel_r=1.45 * rr)
    b2 = p1 + 0.40 * c.main_len * um + (c.boom_h / 2 + 0.6 * c.boom_h) * nm
    q2 = p2 + 1.5 * c.boom_h * no                     # on the outer boom's lever, straight over the knuckle pin
    fit2 = fit_cylinder(p2, b2, q2, (c.knuckle_range[0] - k0, c.knuckle_range[1] - k0), rod_r=0.85 * rr,
                        barrel_r=1.25 * rr)
    p.update(b1=b1.tolist(), q1=q1.tolist(), b2=b2.tolist(), q2=q2.tolist(), hmax=hmax)
    L.cylinders.append({"name": "Main boom cylinder", "barrel": ["MAIN CYLINDER BARREL"], "rod": ["MAIN CYLINDER ROD"],
                        "barrel_pin": {"point": b1.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "COLUMN.ASM"},
                        "rod_pin": {"point": q1.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "MAIN BOOM.ASM"},
                        "fit": fit1})
    L.cylinders.append({"name": "Knuckle cylinder", "barrel": ["KNUCKLE CYLINDER BARREL"],
                        "rod": ["KNUCKLE CYLINDER ROD"],
                        "barrel_pin": {"point": b2.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "MAIN BOOM.ASM"},
                        "rod_pin": {"point": q2.tolist(), "axis": [0.0, 1.0, 0.0], "carrier": "OUTER BOOM.ASM"},
                        "fit": fit2})
    # stabilisers: front pair behind the column, rear pair at the bed's end
    rear = c.main_len * 0.25 + c.outer_len + 1500.0
    p["rear"] = rear
    out_x = (0.0, rear - 650.0)                       # front pair under the column, rear pair at the bed's end
    pad_in = c.width / 2 + 160.0
    out_ext = c.spread[0] / 2 - pad_in
    pad_z0 = 0.55 * c.wheel_r
    beam_z = deck - 330.0
    p.update(out_x=out_x, pad_in=pad_in, out_ext=out_ext, pad_z0=pad_z0, beam_z=beam_z, beam_w=0.08 * c.width + 60.0)
    cab_len = 2300.0
    front = -cab_len - 450.0
    axles = [front + 1250.0]
    step = 2 * c.wheel_r + 300.0
    if c.axles == 3:
        axles = [front + 1250.0, rear - 1500.0 - step / 2, rear - 1500.0 + step / 2]
    elif c.axles == 4:
        axles = [front + 1250.0, front + 1250.0 + step, rear - 1500.0 - step / 2, rear - 1500.0 + step / 2]
    else:
        axles = [front + 1250.0, rear - 1500.0]
    p.update(front=front, cab_len=cab_len, axles=axles)
    _outrigger_joints(J, "STABILISER", "Stabilisers", "Stabiliser", "STABILISER LEG", "Legs", "Leg", out_x,
                      p["beam_w"], beam_z, pad_in, out_ext, pad_z0)
    L.hook_point = (float(tip[0]), 0.0, float(tip[2] - d0))
    L.poses = [{"name": "Travel", "values": {}},
               {"name": "Set up", "values": {"Stabilisers": out_ext / STAGES, "Legs": pad_z0}},
               {"name": "Working", "values": {"Stabilisers": out_ext / STAGES, "Legs": pad_z0, "Main boom": 25.0,
                                              "Knuckle": 15.0, "Extension": round(0.5 * c.ext_stroke, 1),
                                              "Hoist": 1500.0}},
               {"name": "Long reach", "values": {"Stabilisers": out_ext / STAGES, "Legs": pad_z0, "Main boom": -15.0,
                                                 "Knuckle": 35.0, "Extension": c.ext_stroke, "Slew": -90.0,
                                                 "Hoist": 1000.0}}]
    return L


def layout(name_or_cls) -> Layout:
    c = CLASSES[name_or_cls] if isinstance(name_or_cls, str) else name_or_cls
    return {"AT": mobile_layout, "CC": crawler_layout, "KB": knuckle_layout}[c.kind](c)


# ---------------------------------------------------------------------------------------------------------------------
# Forward kinematics (the app's joint rules, in plain NumPy)

def joint_values(L: Layout, values: dict) -> dict:
    """Every joint's value: the given ones (deg / mm), followers ``ratio`` x their leader, the rest 0."""
    out = {}
    for j in L.joints:
        if j.get("follows"):
            out[j["name"]] = j["ratio"] * float(values.get(j["follows"], 0.0))
        else:
            out[j["name"]] = float(values.get(j["name"], 0.0))
    return out


def motions(L: Layout, values: dict) -> dict:
    """Joint name -> 4 x 4 world motion (mm) of what it moves, relative to the CAD pose."""
    vals = joint_values(L, values)
    by = {j["name"]: j for j in L.joints}
    out: dict = {}

    def m(name):
        if name in out:
            return out[name]
        j = by[name]
        base = m(j["rides_on"]) if j.get("rides_on") else np.eye(4)
        v = vals[name]
        local = about(j["point"], j["direction"], v) if j["kind"] == "ROTATE" else along(j["direction"], v)
        out[name] = base @ local
        return out[name]
    for j in L.joints:
        m(j["name"])
    return out


def moved_by(L: Layout, asm: str) -> str | None:
    """The joint whose motion carries a sub-assembly (its own joint, else the nearest one it sits in)."""
    for j in L.joints:
        if asm in j["parts"]:
            return j["name"]
    return None


def hook_point(L: Layout, values: dict) -> np.ndarray:
    """The hook's saddle in the model frame (mm) for joint values (deg / mm)."""
    M = motions(L, values)["Hoist"]
    return (M @ np.r_[np.asarray(L.hook_point, float), 1.0])[:3]


def hook_radius_height(L: Layout, values: dict) -> tuple[float, float]:
    """(radius from the slew axis, height above the ground) of the hook, m. A crawler's radius is from its slew axis
    where it stands (after Travel)."""
    p = hook_point(L, values)
    centre = motions(L, values)["Slew"] @ np.array([0.0, 0.0, 0.0, 1.0])
    return float(math.hypot(p[0] - centre[0], p[1] - centre[1]) / 1000.0), float(p[2] / 1000.0)


def boom_length(L: Layout, values: dict) -> float:
    """Mobile: pin -> head sheave (m); crawler: the model's boom; knuckle: column pin -> tip along the booms."""
    c = L.c
    v = joint_values(L, values)
    if c.kind == "AT":
        return (c.L0 + (c.sections - 1) * v["Telescope"]) / 1000.0
    if c.kind == "CC":
        return c.boom_cad / 1000.0
    return (c.main_len + c.outer_len + c.extensions * v["Extension"]) / 1000.0
