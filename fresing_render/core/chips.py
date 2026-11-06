"""Chips: what flies off the bit while it cuts (task 0028). No Blender here.

How it works
------------
* **Presets**: one per workpiece material (aluminium, steel, stainless, brass/bronze, cast iron, plastic,
  wood/MDF) and bit type (end mill, ball end mill, face mill, drill, engraving/V-bit): the chip's shape,
  size, colour, how many come off per mm³ of removed material and how they fly.
* **Shapes** are made here as small meshes: ribbons along a curve (aluminium curls, steel commas, drill
  spirals, plastic ribbons, wood shavings) and lumps (brass and cast-iron crumbs, dust, coolant drops).
  Six variants of each, so no two neighbours look the same.
* **Where material comes off**: a height field of the workpiece seen from above (cells of about 0.5 mm).
  The bits' paths are stamped into it in time order; every cell that gets lower is a *change* (cell, time,
  old and new height). So the removed volume per frame is known, and the spot it came from. A chip starts
  at the bit's edge facing that spot and is thrown off in the spindle's turning direction.
* **Flight**: gravity, air drag (dust floats), bounces. Chips land on the workpiece as it is cut at that
  moment (and bounce off pocket walls), on the parts that move with it (the table), on the parts that
  stand still (the machine bed) and on the floor. Resting chips pile up (a pile height per cell); chips
  lying on the workpiece are gone when the bit cuts there. Too many chips: the oldest resting ones fade.
* **Deterministic**: every random number comes from one generator with a fixed seed, drawn in a fixed
  order, and the flight is worked out once from start to end and stored per frame. The same set-up
  gives the same chips on every run and every PC, whatever frame is shown or rendered first.

Coordinates: *riding* space is the world as it is at the first frame, carried along with the
workpiece (a table that slides takes its chips along); *world* space is the world. A chip that falls
off everything that moves with the workpiece changes to world space and lands on the machine bed or
the floor. Units: metres, seconds for physics, frames for time.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

MM = 0.001
G = 9.81
SUBSTEPS = 4                      # physics steps per frame
REST_SPEED = 0.12                 # m/s: a chip that bounces up slower than this lies still
MAX_BOUNCES = 3
BULK = 6.0                        # a pile of loose chips takes this many times their own volume
RETIRE_FADE = 0.16                # s: too many chips - the oldest shrink away in this time
VARIANTS = 6

AMOUNTS = {
    "NONE": {"label": "None", "factor": 0.0, "cap": 0, "births": 0},
    "FEW": {"label": "Few", "factor": 0.12, "cap": 3000, "births": 12000},
    "REALISTIC": {"label": "Realistic", "factor": 1.0, "cap": 25000, "births": 60000},
}

# ---------------------------------------------------------------------------
# materials and bit types
# ---------------------------------------------------------------------------

FAMILIES = {
    "ALU": "Aluminium",
    "STEEL": "Steel",
    "STAINLESS": "Stainless steel",
    "BRASS": "Brass / bronze / copper",
    "CAST_IRON": "Cast iron",
    "PLASTIC": "Plastic (POM, PE, nylon, acrylic)",
    "WOOD": "Wood / MDF",
}

BIT_KINDS = {
    "END": "End mill",
    "BALL": "Ball end mill",
    "FACE": "Face mill",
    "DRILL": "Drill",
    "ENGRAVE": "Engraving / V-bit",
}

FACE_MILL_DIAMETER = 25 * MM      # a flat cutter this wide or wider is a face mill

# words in part, group and material names (English, Dutch, German), checked as whole words or prefixes
_WORDS = (
    ("STAINLESS", ("stainless", "rvs", "inox", "edelstahl", "nirosta", "1.4301", "1.4404", "1.4571", "aisi",
                   "304", "304l", "316", "316l", "v2a", "v4a")),
    ("ALU", ("alu", "aluminium", "aluminum", "almg", "almgsi", "alzn", "6061", "6082", "7075", "5083", "2024",
             "en-aw", "aw-6082", "aw-5083", "aw-7075", "dural", "zamak", "zinc die")),
    ("BRASS", ("brass", "messing", "ms58", "cuzn", "bronze", "brons", "rg7", "cusn", "copper", "koper", "kupfer",
               "cu-etp")),
    ("CAST_IRON", ("cast iron", "gietijzer", "grauguss", "gusseisen", "gg25", "gg-25", "gjl", "en-gjl", "gjs",
                   "en-gjs", "ggg40", "nodular")),
    ("PLASTIC", ("pom", "delrin", "acetal", "hostaform", "pe", "hdpe", "pe500", "pe1000", "uhmw", "nylon", "pa6",
                 "pa66", "polyamide", "polyamid", "pvc", "abs", "pmma", "acryl", "acrylic", "plexiglas", "perspex",
                 "pc", "polycarbonate", "polycarbonaat", "peek", "ptfe", "teflon", "pp", "petg", "plastic",
                 "kunststof", "kunststoff", "ertalon", "ertacetal")),
    ("WOOD", ("wood", "hout", "holz", "mdf", "hdf", "multiplex", "plywood", "triplex", "spaanplaat", "osb", "beech",
              "beuken", "oak", "eiken", "pine", "grenen", "birch", "berken")),
    ("STEEL", ("steel", "staal", "stahl", "s235", "s275", "s355", "c45", "ck45", "42crmo4", "16mncr5", "st37", "st52",
               "1.0038", "1.0503", "1.7225", "tool steel", "gereedschapsstaal", "werkzeugstahl", "hardox")),
)

# the app's ready-made materials (core/materials_lib.py) -> chip family
_MATERIAL_KEYS = {
    "aluminium_machined": "ALU", "aluminium_anodized": "ALU", "aluminium_anodized_color": "ALU",
    "aluminium_profile": "ALU", "aluminium_anodized_black": "ALU", "zinc_diecast": "ALU",
    "steel_machined": "STEEL", "steel_raw": "STEEL", "galvanized": "STEEL", "zinc_plated": "STEEL",
    "zinc_yellow": "STEEL", "zinc_flake": "STEEL", "black_oxide": "STEEL", "chrome": "STEEL",
    "nickel_plated": "BRASS",
    "stainless_brushed": "STAINLESS", "stainless_polished": "STAINLESS",
    "brass": "BRASS", "bronze": "BRASS", "copper": "BRASS",
    "cast_iron": "CAST_IRON",
    "pom_white": "PLASTIC", "plastic_gloss": "PLASTIC", "plastic_matte": "PLASTIC", "rubber_black": "PLASTIC",
    "cable_black": "PLASTIC", "belt_rubber": "PLASTIC", "foam": "PLASTIC", "felt": "PLASTIC",
    "glass_clear": "PLASTIC", "polycarbonate_clear": "PLASTIC", "glass_tinted": "PLASTIC",
    "acrylic_frosted": "PLASTIC", "mannequin_matte": "PLASTIC",
    "wood": "WOOD",
}

DEFAULT_FAMILY = "ALU"


def _tokens(text: str) -> list:
    t = "".join(c.lower() if (c.isalnum() or c in ".-") else " " for c in text or "")
    return t.split()


# words that also count at the start of a longer word ("aluplaat", "staalprofiel", "houten"); short ones like
# "pe" or "pom" only count as a word of their own ("pomp" is a pump)
_PREFIXES = ("alu", "almg", "aluminium", "aluminum", "stainless", "edelstahl", "messing", "brass", "bronze",
             "brons", "copper", "koper", "kupfer", "steel", "staal", "stahl", "gietijzer", "grauguss", "gusseisen",
             "wood", "hout", "holz", "multiplex", "plywood", "kunststof", "plastic", "delrin", "acetal", "acryl",
             "nylon", "polyamid", "polycarbona", "plexiglas", "hostaform", "ertalon", "ertacetal")


def family_from_names(names) -> str | None:
    """A chip family from words in names (part, group): 'BLOCK AlMg3' -> ALU, 'Plaat RVS 316' -> STAINLESS."""
    for text in names:
        toks = _tokens(text)
        low = " " + " ".join(toks) + " "
        tset = set(toks)
        for fam, words in _WORDS:
            for w in words:
                if " " in w:
                    if f" {w} " in low:
                        return fam
                elif w in tset or (w in _PREFIXES and any(t.startswith(w) for t in toks)):
                    return fam
    return None


def family_for(names, material_key: str = "") -> tuple[str, str]:
    """(family, why) for a workpiece: words in its names first, then its group's material, else aluminium."""
    fam = family_from_names(names)
    if fam:
        return fam, "name"
    fam = _MATERIAL_KEYS.get(material_key or "")
    if fam:
        return fam, "material"
    return DEFAULT_FAMILY, "default"


def bit_kind(kind: str, radius: float) -> str:
    """The chip type of a bit from its shape (core.machining.Tool.kind) and size."""
    if kind == "DRILL":
        return "DRILL"
    if kind == "VEE":
        return "ENGRAVE"
    if kind == "BALL":
        return "BALL"
    if kind == "FLAT" and 2 * radius >= FACE_MILL_DIAMETER - 1e-9:
        return "FACE"
    return "END"


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

SHAPES = ("CURL", "HELIX", "COMMA", "RIBBON", "FLAKE", "CRUMB", "DUST", "DROP")


@dataclass(frozen=True)
class Look:
    """How a chip family looks: colour ramp stops (position, linear RGB), metal, roughness."""
    stops: tuple
    metallic: float = 1.0
    roughness: float = 0.25
    transmission: float = 0.0


LOOKS = {
    "ALU": Look(((0.0, (0.80, 0.81, 0.83)), (1.0, (0.93, 0.94, 0.95))), 1.0, 0.16),
    # steel chips come off hot: silver, straw, brown, purple and blue temper colours
    "STEEL": Look(((0.0, (0.62, 0.63, 0.64)), (0.35, (0.72, 0.56, 0.30)), (0.6, (0.45, 0.26, 0.24)),
                   (0.8, (0.30, 0.22, 0.50)), (1.0, (0.18, 0.30, 0.62))), 1.0, 0.28),
    "STAINLESS": Look(((0.0, (0.72, 0.72, 0.73)), (0.7, (0.74, 0.70, 0.60)), (1.0, (0.70, 0.58, 0.40))), 1.0, 0.24),
    "BRASS": Look(((0.0, (0.80, 0.62, 0.30)), (1.0, (0.93, 0.80, 0.44))), 1.0, 0.30),
    "CAST_IRON": Look(((0.0, (0.16, 0.16, 0.17)), (1.0, (0.36, 0.36, 0.37))), 0.55, 0.72),
    "PLASTIC": Look(((0.0, (0.86, 0.86, 0.84)), (1.0, (0.92, 0.92, 0.90))), 0.0, 0.42),
    "WOOD": Look(((0.0, (0.50, 0.36, 0.22)), (1.0, (0.74, 0.60, 0.42))), 0.0, 0.80),
    "MIST": Look(((0.0, (0.95, 0.97, 1.0)), (1.0, (1.0, 1.0, 1.0))), 0.0, 0.05, 1.0),
}


@dataclass(frozen=True)
class Preset:
    family: str
    bit: str
    shape: str
    length: float                 # m: the chip's longest size
    width: float                  # m (ribbons) - lumps use length only
    thick: float                  # m
    per_mm3: float                # chips per mm³ of removed material ("Realistic")
    speed: float                  # m/s when thrown off
    tangent: float = 0.85         # direction mix: along the turning direction ...
    radial: float = 0.3           # ... away from the bit ...
    up: float = 0.35              # ... and up the flutes
    spread: float = 0.35          # random part of the direction
    spin: float = 25.0            # turns per second while flying
    drag: float = 0.3             # 1/s: air slows the chip (dust floats)
    bounce: float = 0.35          # how much of its speed a chip keeps when it hits something
    life: float = 0.0             # s: 0 = stays (only coolant mist fades by itself)
    note: str = ""

    @property
    def label(self) -> str:
        return f"{FAMILIES.get(self.family, self.family)}, {BIT_KINDS.get(self.bit, self.bit).lower()}"


def _p(family, bit, shape, length, width, thick, per_mm3, speed, **kw) -> Preset:
    return Preset(family, bit, shape, length * MM, width * MM, thick * MM, per_mm3, speed, **kw)


# how chips leave the bit: mostly along the turning direction, a bit outwards and up the flutes; small chips
# slow down quickly in the air (drag), so most land on the table and the machine bed, a few fly further
_END = {"drag": 2.5}
_DRILL = {"tangent": 0.35, "radial": 0.25, "up": 1.0, "spread": 0.25, "spin": 6.0, "drag": 2.0}
_FACE = {"tangent": 0.95, "radial": 0.45, "up": 0.12, "drag": 2.0}
_ENGRAVE = {"tangent": 0.5, "radial": 0.6, "up": 0.5, "spread": 0.6, "drag": 6.0, "bounce": 0.0, "spin": 10.0}
_HEAVY = {"bounce": 0.4, "drag": 1.6}

PRESETS = {p.family + "/" + p.bit: p for p in (
    # aluminium: bright curls; long spirals from a drill; fine dust from an engraving bit
    _p("ALU", "END", "CURL", 5.0, 1.6, 0.10, 0.45, 1.9, **_END, note="shiny curls"),
    _p("ALU", "BALL", "COMMA", 2.5, 1.0, 0.08, 1.2, 1.6, **_END, note="small commas"),
    _p("ALU", "FACE", "COMMA", 4.0, 2.0, 0.10, 0.4, 2.4, **_FACE, note="flat commas, thrown far"),
    _p("ALU", "DRILL", "HELIX", 14.0, 0.9, 0.10, 0.08, 0.7, **_DRILL, note="long spirals out of the hole"),
    _p("ALU", "ENGRAVE", "DUST", 0.35, 0, 0, 40.0, 1.0, **_ENGRAVE, note="fine shiny dust"),
    # steel: hot chips with temper colours (silver, straw, brown, blue)
    _p("STEEL", "END", "COMMA", 3.0, 1.2, 0.18, 0.6, 1.6, **_HEAVY, note="blue-brown commas"),
    _p("STEEL", "BALL", "COMMA", 2.0, 0.8, 0.12, 1.5, 1.4, **_HEAVY),
    _p("STEEL", "FACE", "COMMA", 3.5, 1.6, 0.20, 0.4, 2.2, **{**_FACE, **_HEAVY}),
    _p("STEEL", "DRILL", "HELIX", 10.0, 1.0, 0.15, 0.1, 0.6, **_DRILL, note="spirals out of the hole"),
    _p("STEEL", "ENGRAVE", "DUST", 0.3, 0, 0, 40.0, 0.9, **_ENGRAVE),
    # stainless: tough, longer commas, slightly golden
    _p("STAINLESS", "END", "COMMA", 3.5, 1.2, 0.16, 0.5, 1.5, **_HEAVY),
    _p("STAINLESS", "BALL", "COMMA", 2.2, 0.8, 0.12, 1.3, 1.3, **_HEAVY),
    _p("STAINLESS", "FACE", "COMMA", 4.0, 1.6, 0.18, 0.35, 2.0, **{**_FACE, **_HEAVY}),
    _p("STAINLESS", "DRILL", "HELIX", 12.0, 1.0, 0.14, 0.08, 0.6, **_DRILL),
    _p("STAINLESS", "ENGRAVE", "DUST", 0.3, 0, 0, 40.0, 0.9, **_ENGRAVE),
    # brass, bronze, copper: small crumbs that break off
    _p("BRASS", "END", "CRUMB", 1.0, 0, 0, 3.0, 1.2, bounce=0.3, spin=30.0, drag=2.0, note="small crumbs"),
    _p("BRASS", "BALL", "CRUMB", 0.7, 0, 0, 6.0, 1.0, bounce=0.3, spin=30.0, drag=2.5),
    _p("BRASS", "FACE", "CRUMB", 1.2, 0, 0, 2.0, 1.6, **{**_FACE, "bounce": 0.3, "spin": 30.0}),
    _p("BRASS", "DRILL", "COMMA", 2.0, 0.8, 0.12, 1.0, 0.6, **_DRILL),
    _p("BRASS", "ENGRAVE", "DUST", 0.3, 0, 0, 40.0, 0.9, **_ENGRAVE),
    # cast iron: grey crumbs and dust
    _p("CAST_IRON", "END", "CRUMB", 0.8, 0, 0, 5.0, 1.0, bounce=0.2, drag=3.0, note="grey crumbs"),
    _p("CAST_IRON", "BALL", "CRUMB", 0.5, 0, 0, 10.0, 0.9, bounce=0.2, drag=3.5),
    _p("CAST_IRON", "FACE", "CRUMB", 1.0, 0, 0, 3.0, 1.4, **{**_FACE, "bounce": 0.2, "drag": 3.0}),
    _p("CAST_IRON", "DRILL", "CRUMB", 0.8, 0, 0, 5.0, 0.6, **{**_DRILL, "bounce": 0.2, "drag": 3.0}),
    _p("CAST_IRON", "ENGRAVE", "DUST", 0.3, 0, 0, 40.0, 0.8, **_ENGRAVE),
    # plastics: long light ribbons
    _p("PLASTIC", "END", "RIBBON", 16.0, 1.4, 0.15, 0.12, 1.4, drag=3.0, bounce=0.15, spin=8.0,
       note="long ribbons in the workpiece's colour"),
    _p("PLASTIC", "BALL", "RIBBON", 8.0, 1.0, 0.12, 0.35, 1.2, drag=3.0, bounce=0.15, spin=8.0),
    _p("PLASTIC", "FACE", "RIBBON", 10.0, 2.0, 0.15, 0.15, 1.8, **{**_FACE, "drag": 3.0, "bounce": 0.15,
                                                                   "spin": 8.0}),
    _p("PLASTIC", "DRILL", "HELIX", 20.0, 1.0, 0.15, 0.05, 0.5, **{**_DRILL, "spin": 4.0}),
    _p("PLASTIC", "ENGRAVE", "RIBBON", 3.0, 0.4, 0.08, 4.0, 0.7, drag=4.0, bounce=0.1, spin=6.0),
    # wood and MDF: shavings and dust
    _p("WOOD", "END", "FLAKE", 3.0, 2.2, 0.12, 0.5, 1.5, drag=3.5, bounce=0.1, spin=12.0, note="shavings and dust"),
    _p("WOOD", "BALL", "DUST", 0.5, 0, 0, 25.0, 1.2, drag=5.0, bounce=0.0),
    _p("WOOD", "FACE", "FLAKE", 4.0, 3.0, 0.15, 0.3, 2.0, **{**_FACE, "drag": 3.5, "bounce": 0.1, "spin": 12.0}),
    _p("WOOD", "DRILL", "FLAKE", 3.0, 2.0, 0.12, 0.5, 0.6, **{**_DRILL, "drag": 3.0, "bounce": 0.1}),
    _p("WOOD", "ENGRAVE", "DUST", 0.4, 0, 0, 30.0, 0.8, **_ENGRAVE),
)}

MIST = _p("MIST", "MIST", "DROP", 0.5, 0, 0, 0.0, 1.4, tangent=0.5, radial=1.0, up=0.3, spread=0.8, drag=5.0,
          bounce=0.0, spin=0.0, life=0.7)
MIST_PER_SECOND = 600.0           # coolant drops per second while a bit cuts ("Realistic")

# wood: dust comes along with the shavings (an extra preset, same family)
WOOD_DUST = _p("WOOD", "DUST", "DUST", 0.4, 0, 0, 6.0, 1.2, **_ENGRAVE)


def preset(family: str, bit: str) -> Preset:
    return PRESETS.get(f"{family}/{bit}") or PRESETS[f"{DEFAULT_FAMILY}/{bit}"]


def presets_for(family: str, bit: str) -> list:
    """The presets one bit emits (wood end mills throw dust along with the shavings)."""
    p = [preset(family, bit)]
    if family == "WOOD" and bit in ("END", "FACE", "DRILL"):
        p.append(WOOD_DUST)
    return p


def chip_volume(p: Preset) -> float:
    """m³ of material in one chip of this preset (at scale 1)."""
    if p.shape in ("CRUMB",):
        return 0.30 * p.length ** 3
    if p.shape in ("DUST", "DROP"):
        return 0.25 * p.length ** 3
    return p.length * p.width * p.thick


def throw_reach(presets) -> float:
    """How far (m) chips of these presets can fly sideways, roughly: for the size of the catch areas."""
    r = 0.1
    for p in presets:
        v = p.speed * 1.3
        r = max(r, (v * v / G) * (1.0 / (1.0 + p.drag)) * 1.6 + 0.05)
    return float(min(r, 1.5))


# ---------------------------------------------------------------------------
# shapes
# ---------------------------------------------------------------------------

def _ribbon(c: np.ndarray, side: np.ndarray, width, thick) -> tuple:
    """A strip of the given width and thickness along the centre line ``c`` (n, 3); ``side`` is the
    width direction at each point. Returns (verts, tris)."""
    n = len(c)
    width = np.broadcast_to(np.asarray(width, float), (n,))
    thick = np.broadcast_to(np.asarray(thick, float), (n,))
    tan = np.gradient(c, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    side = side - (side * tan).sum(axis=1, keepdims=True) * tan
    side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-12)
    nrm = np.cross(tan, side)
    corners = [(+0.5, +0.5), (-0.5, +0.5), (-0.5, -0.5), (+0.5, -0.5)]
    v = np.empty((n, 4, 3))
    for k, (a, b) in enumerate(corners):
        v[:, k] = c + side * (a * width)[:, None] + nrm * (b * thick)[:, None]
    tris = []
    for i in range(n - 1):
        for k in range(4):
            a, b = i * 4 + k, i * 4 + (k + 1) % 4
            c2, d2 = a + 4, b + 4
            tris += [(a, b, d2), (a, d2, c2)]
    last = (n - 1) * 4
    tris += [(0, 2, 1), (0, 3, 2), (last, last + 1, last + 2), (last, last + 2, last + 3)]
    return v.reshape(-1, 3), np.array(tris, dtype=np.int32)


def _lump(n_dirs: int, size: float, rng, flat: float = 0.6) -> tuple:
    """A small irregular lump (crumb, dust grain, drop): an octahedron or icosahedron with random radii."""
    if n_dirs <= 6:
        d = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float)
        tris = [(0, 2, 4), (2, 1, 4), (1, 3, 4), (3, 0, 4), (2, 0, 5), (1, 2, 5), (3, 1, 5), (0, 3, 5)]
    else:
        t = (1 + 5 ** 0.5) / 2
        d = np.array([(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t),
                      (0, 1, -t), (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)], float)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        tris = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
                (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5),
                (2, 4, 11), (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    r = rng.uniform(0.65, 1.0, len(d)) * size / 2
    v = d * r[:, None]
    v[:, 2] *= flat
    return v, np.array(tris, dtype=np.int32)


def shape_mesh(p: Preset, variant: int) -> tuple:
    """(verts (n, 3) float32, tris (m, 3) int32) of one chip, lying as it would on a table: centred in X/Y,
    its lowest point at z = 0."""
    rng = np.random.default_rng(1000 + SHAPES.index(p.shape) * 97 + variant)
    L, W, T = p.length, max(p.width, 1e-5), max(p.thick, 1e-6)
    if p.shape == "CURL":                  # a short coil, wound tighter towards its end
        turns = rng.uniform(0.9, 1.5)
        n = 30
        th = np.linspace(0, 2 * math.pi * turns, n)
        r0 = L / (2 * math.pi * turns * 0.75)
        r = r0 * (1 - 0.5 * th / th[-1])
        c = np.stack([r * np.cos(th), r * np.sin(th), W * 1.15 * th / (2 * math.pi)], axis=1)
        side = np.tile([0.0, 0.0, 1.0], (n, 1))
        v, t = _ribbon(c, side, W, T * np.linspace(1.0, 0.6, n))
        v = v @ _rot_x(math.pi / 2 * rng.integers(0, 2)).T          # half of them lie on their side
    elif p.shape == "HELIX":               # a spring out of a drilled hole, lying on its side
        turns = rng.uniform(3.0, 5.0)
        n = 70
        th = np.linspace(0, 2 * math.pi * turns, n)
        rad = L * 0.12 * np.linspace(1.0, 0.75, n)
        c = np.stack([rad * np.cos(th), rad * np.sin(th), np.linspace(0, L, n)], axis=1)
        side = np.stack([np.cos(th), np.sin(th), np.full(n, 0.6)], axis=1)
        v, t = _ribbon(c, side, W, T)
        v = v @ _rot_y(math.pi / 2).T
    elif p.shape == "COMMA":               # a short curved piece, thinner at one end
        ang = math.radians(rng.uniform(100, 220))
        n = 16
        th = np.linspace(0, ang, n)
        rho = L / ang
        c = np.stack([rho * np.cos(th), rho * np.sin(th), np.zeros(n)], axis=1)
        side = np.tile([0.0, 0.0, 1.0], (n, 1))
        v, t = _ribbon(c, side, W * np.linspace(1.0, 0.7, n), T * np.linspace(1.0, 0.35, n))
        v = v @ _rot_x(rng.uniform(-0.4, 0.4)).T
    elif p.shape == "RIBBON":              # a long thin strip, gently wavy and twisted
        n = 36
        s = np.linspace(0, 1, n)
        k1, k2, tw = rng.uniform(1.0, 2.5), rng.uniform(0.5, 1.5), rng.uniform(-math.pi, math.pi)
        c = np.stack([s * L, 0.12 * L * np.sin(k1 * math.pi * s), 0.06 * L * np.sin(k2 * math.pi * s + 0.7)], axis=1)
        side = np.stack([np.zeros(n), np.cos(tw * s), np.sin(tw * s) * 0.5], axis=1)
        v, t = _ribbon(c, side, W, T)
    elif p.shape == "FLAKE":               # a wood shaving: a wide thin curl
        ang = math.radians(rng.uniform(150, 300))
        n = 16
        th = np.linspace(0, ang, n)
        rho = L / ang
        c = np.stack([np.zeros(n), rho * np.cos(th), rho * np.sin(th)], axis=1)
        side = np.tile([1.0, 0.0, 0.0], (n, 1))
        v, t = _ribbon(c, side, W * np.linspace(1.0, 0.8, n), T)
    elif p.shape == "CRUMB":
        v, t = _lump(6, L, rng, flat=0.55)
    elif p.shape == "DUST":
        v, t = _lump(6, L, rng, flat=0.5)
    else:                                  # DROP
        v, t = _lump(12, L, rng, flat=1.0)
    v = np.asarray(v, float)
    lo, hi = v.min(axis=0), v.max(axis=0)
    v = v - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    return v.astype(np.float32), np.asarray(t, np.int32)


def _rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# ---------------------------------------------------------------------------
# quaternions (w, x, y, z), as Blender stores them
# ---------------------------------------------------------------------------

def q_mul(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    aw, ax, ay, az = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bw, bx, by, bz = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], axis=-1)


def q_from_rotvec(r: np.ndarray) -> np.ndarray:
    ang = np.linalg.norm(r, axis=-1)
    half = 0.5 * ang
    k = np.where(ang > 1e-12, np.sin(half) / np.maximum(ang, 1e-12), 0.5)
    return np.concatenate([np.cos(half)[..., None], r * k[..., None]], axis=-1)


def q_from_matrix(m: np.ndarray) -> np.ndarray:
    """Quaternion of a 3x3 rotation matrix."""
    t = m[0, 0] + m[1, 1] + m[2, 2]
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        q = [0.25 * s, (m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        q = [(m[2, 1] - m[1, 2]) / s, 0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s]
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        q = [(m[0, 2] - m[2, 0]) / s, (m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s]
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        q = [(m[1, 0] - m[0, 1]) / s, (m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s]
    q = np.array(q)
    return q / np.linalg.norm(q)


# ---------------------------------------------------------------------------
# height fields
# ---------------------------------------------------------------------------

@dataclass
class Grid:
    """Heights on a regular grid seen from above (z up): ``h[iy, ix]`` at cell centres; -inf: nothing."""
    x0: float
    y0: float
    cell: float
    h: np.ndarray

    @property
    def nx(self) -> int:
        return self.h.shape[1]

    @property
    def ny(self) -> int:
        return self.h.shape[0]

    def centres(self) -> tuple:
        xs = self.x0 + (np.arange(self.nx) + 0.5) * self.cell
        ys = self.y0 + (np.arange(self.ny) + 0.5) * self.cell
        return xs, ys

    def index(self, x, y) -> tuple:
        ix = np.floor((np.asarray(x) - self.x0) / self.cell).astype(np.int64)
        iy = np.floor((np.asarray(y) - self.y0) / self.cell).astype(np.int64)
        ok = (ix >= 0) & (ix < self.nx) & (iy >= 0) & (iy < self.ny)
        return ix, iy, ok

    def sample(self, x, y, arr: np.ndarray | None = None) -> np.ndarray:
        a = self.h if arr is None else arr
        ix, iy, ok = self.index(x, y)
        out = np.full(np.shape(ok), -np.inf)
        out[ok] = a[iy[ok], ix[ok]]
        return out


def grid_for(lo, hi, cell: float, max_cells: int = 420) -> Grid:
    """An empty grid over the box lo..hi (x, y); the cell grows so neither side has more than max_cells."""
    size = np.maximum(np.asarray(hi[:2], float) - np.asarray(lo[:2], float), cell)
    cell = max(cell, float(size.max()) / max_cells)
    nx, ny = int(math.ceil(size[0] / cell)), int(math.ceil(size[1] / cell))
    return Grid(float(lo[0]), float(lo[1]), cell, np.full((ny, nx), -np.inf))


def profile_height(profile: list, radius: float):
    """z above the tip of the bit's lowest surface at distance r from its axis (a function of r)."""
    prof = [(float(z), float(r)) for z, r in profile] or [(0.0, radius)]
    z0, r0 = prof[0]
    pts = [(z0, 0.0)] if r0 > 1e-9 else [(z0, r0)]        # a flat bottom reaches the axis
    if r0 > 1e-9:
        pts.append((z0, r0))
    for z, r in prof[1:]:
        if r > pts[-1][1] + 1e-12:                         # the lower outline only: radius growing
            pts.append((z, min(r, radius)))
        if r >= radius - 1e-12:
            break
    if len(pts) == 1:
        pts.append((pts[0][0], max(radius, 1e-9)))
    zs = np.array([p[0] for p in pts])
    rs = np.array([p[1] for p in pts])

    def f(r):
        return np.interp(r, rs, zs)
    return f


class WorkField:
    """The workpiece as a height field that the bits cut into, and a record of every change."""

    def __init__(self, top: Grid, bottom: np.ndarray, floor: np.ndarray | None = None):
        self.grid = top
        self.h0 = top.h.copy()
        self.bottom = bottom
        self.floor = floor
        self.cur = top.h.copy()
        self._parts = []
        self.cells = np.zeros(0, np.int64)
        self.t = np.zeros(0)
        self.h_old = np.zeros(0)
        self.h_new = np.zeros(0)
        self.dh = np.zeros(0)
        self.bit = np.zeros(0, np.int32)

    def stamp(self, prof, radius: float, pa, pb, ta: float, tb: float, bit: int) -> None:
        """The bit (lowest surface ``prof(r)``) moves straight from tip ``pa`` to ``pb`` (time ta..tb)."""
        g = self.grid
        pa, pb = np.asarray(pa, float), np.asarray(pb, float)
        lo = np.minimum(pa[:2], pb[:2]) - radius
        hi = np.maximum(pa[:2], pb[:2]) + radius
        ix0 = max(0, int(math.floor((lo[0] - g.x0) / g.cell)))
        ix1 = min(g.nx, int(math.ceil((hi[0] - g.x0) / g.cell)) + 1)
        iy0 = max(0, int(math.floor((lo[1] - g.y0) / g.cell)))
        iy1 = min(g.ny, int(math.ceil((hi[1] - g.y0) / g.cell)) + 1)
        if ix0 >= ix1 or iy0 >= iy1:
            return
        cur = self.cur[iy0:iy1, ix0:ix1]
        if not np.isfinite(cur).any():
            return
        zlow = min(pa[2], pb[2])
        if np.nanmax(np.where(np.isfinite(cur), cur, -np.inf)) <= zlow + 1e-9:
            return                                       # the bit is below everything here: nothing to cut
        xs = g.x0 + (np.arange(ix0, ix1) + 0.5) * g.cell
        ys = g.y0 + (np.arange(iy0, iy1) + 0.5) * g.cell
        X, Y = np.meshgrid(xs, ys)
        ab = pb[:2] - pa[:2]
        L2 = float(ab @ ab)
        if L2 > 1e-18:
            s = np.clip(((X - pa[0]) * ab[0] + (Y - pa[1]) * ab[1]) / L2, 0.0, 1.0)
        else:
            s = np.ones_like(X) if pb[2] <= pa[2] else np.zeros_like(X)
        cx, cy = pa[0] + s * ab[0], pa[1] + s * ab[1]
        r = np.hypot(X - cx, Y - cy)
        z = np.where(r <= radius, pa[2] + s * (pb[2] - pa[2]) + prof(np.minimum(r, radius)), np.inf)
        for q in (pa, pb):                               # the ends of a ramp can reach lower
            rq = np.hypot(X - q[0], Y - q[1])
            z = np.minimum(z, np.where(rq <= radius, q[2] + prof(np.minimum(rq, radius)), np.inf))
        if self.floor is not None:
            z = np.maximum(z, self.floor[iy0:iy1, ix0:ix1])
        bot = self.bottom[iy0:iy1, ix0:ix1]
        new = np.where(z <= bot + 1e-7, -np.inf, z)      # cut through: nothing left in this column
        hit = np.isfinite(cur) & (new < cur - 1e-7)
        if not hit.any():
            return
        iy, ix = np.nonzero(hit)
        old = cur[iy, ix]
        nv = new[iy, ix]
        dh = old - np.maximum(nv, bot[iy, ix])
        cur[iy, ix] = nv
        cells = (iy + iy0) * g.nx + (ix + ix0)
        t = ta + s[iy, ix] * (tb - ta)
        self._parts.append((cells, t, old, nv, dh, np.full(len(cells), bit, np.int32)))

    def finish(self) -> None:
        """Put the changes in time order (and the field back to the uncut state for replaying)."""
        if self._parts:
            cols = [np.concatenate([p[k] for p in self._parts]) for k in range(6)]
            order = np.argsort(cols[1], kind="stable")
            self.cells, self.t, self.h_old, self.h_new, self.dh, self.bit = (c[order] for c in cols)
        self._parts = []
        self.cur = self.h0.copy()

    def removed(self) -> float:
        """m³ removed in all (from the changes)."""
        return float(self.dh.sum() * self.grid.cell ** 2)

    def removed_per_frame(self, f0: int, f1: int) -> np.ndarray:
        """m³ removed between frame f-1 and f, for f in f0..f1."""
        out = np.zeros(f1 - f0 + 1)
        if len(self.t):
            k = np.clip(np.ceil(self.t - 1e-9).astype(np.int64) - f0, 0, f1 - f0)
            np.add.at(out, k, self.dh * self.grid.cell ** 2)
        return out


def stamp_paths(work: WorkField, bits: list) -> None:
    """Stamp every bit's path (``BitIn``) into the field, all bits together in time order."""
    events = []
    for b, bit in enumerate(bits):
        for i in range(len(bit.t) - 1):
            events.append((bit.t[i + 1], b, i))
    events.sort()
    for _t, b, i in events:
        bit = bits[b]
        work.stamp(bit.prof, bit.radius, bit.o[i], bit.o[i + 1], bit.t[i], bit.t[i + 1], b)
    work.finish()


# ---------------------------------------------------------------------------
# the simulation
# ---------------------------------------------------------------------------

@dataclass
class BitIn:
    """One bit for the chips: its path in riding space (tip ``o``, axis ``d`` at times ``t`` in frames)."""
    t: np.ndarray
    o: np.ndarray
    d: np.ndarray
    radius: float
    length: float
    profile: list
    presets: list
    spin: float = 1.0             # +1: clockwise seen from above (M3), -1: counter-clockwise (M4)

    def __post_init__(self):
        self.t = np.asarray(self.t, float)
        self.o = np.asarray(self.o, float).reshape(-1, 3)
        self.d = np.asarray(self.d, float).reshape(-1, 3)
        self.prof = profile_height(self.profile, self.radius)

    def at(self, t) -> tuple:
        t = np.asarray(t, float)
        o = np.stack([np.interp(t, self.t, self.o[:, k]) for k in range(3)], axis=-1)
        d = np.stack([np.interp(t, self.t, self.d[:, k]) for k in range(3)], axis=-1)
        d /= np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-12)
        return o, d


@dataclass
class SimIn:
    fps: float
    f0: int
    f1: int
    bits: list
    work: WorkField
    ride: Grid                    # what moves with the workpiece (riding space); -inf: nothing
    static: Grid | None           # what stands still (world space)
    floor_z: float                # world z of the floor (the lowest point of the machine)
    carry: np.ndarray | None = None   # (f1 - f0 + 1, 4, 4): riding space -> world at every frame
    amount: str = "FEW"
    mist: bool = False
    seed: int = 28


@dataclass
class Bake:
    """Every chip from birth to rest, ready to show at any frame."""
    shapes: list                  # (Preset, variant) per instance index
    lift: np.ndarray              # per shape: z of its lowest point below its origin (0 here; kept for clarity)
    born: np.ndarray              # frames
    rest_t: np.ndarray            # frames (inf: never rests)
    end_t: np.ndarray             # frames (inf: stays)
    fade: np.ndarray              # frames it takes to fade before end_t
    rest_p: np.ndarray
    rest_q: np.ndarray
    rest_space: np.ndarray        # 0 riding, 1 world
    slot: np.ndarray              # instance index
    scale: np.ndarray
    tint: np.ndarray
    f0: int
    frame_start: np.ndarray       # CSR: flying chips at frame f are rows fly_* [frame_start[f - f0]: ...[f - f0 + 1]]
    fly_id: np.ndarray
    fly_p: np.ndarray
    fly_q: np.ndarray
    fly_space: np.ndarray
    volume: np.ndarray            # m³ removed per frame (f0..f1)
    stats: dict = field(default_factory=dict)

    @property
    def count(self) -> int:
        return int(len(self.born))

    def at(self, T: float) -> dict:
        """Chips to show at frame ``T``: for space 0 (riding) and 1 (world): position, rotation, shape,
        scale and tint."""
        f = int(math.floor(T + 0.5))
        k = f - self.f0
        resting = (self.rest_t <= f + 1e-9) & (f < self.end_t - 1e-9)
        ids_r = np.nonzero(resting)[0]
        if 0 <= k < len(self.frame_start) - 1:
            a, b = int(self.frame_start[k]), int(self.frame_start[k + 1])
        else:
            a = b = 0
        ids_f = self.fly_id[a:b]
        keep = f < self.end_t[ids_f] - 1e-9
        ids_f = ids_f[keep]
        pos = np.concatenate([self.rest_p[ids_r], self.fly_p[a:b][keep].astype(float)])
        rot = np.concatenate([self.rest_q[ids_r], self.fly_q[a:b][keep].astype(float)])
        space = np.concatenate([self.rest_space[ids_r], self.fly_space[a:b][keep]])
        ids = np.concatenate([ids_r, ids_f]).astype(np.int64)
        sc = self.scale[ids].astype(float)
        fin = np.isfinite(self.end_t[ids])
        if fin.any():
            left = (self.end_t[ids] - f) / np.maximum(self.fade[ids], 1e-6)
            sc = np.where(fin, sc * np.clip(left, 0.0, 1.0), sc)
        out = {}
        for sp in (0, 1):
            m = (space == sp) & (sc > 1e-6)
            out[sp] = {"pos": pos[m], "rot": rot[m], "slot": self.slot[ids[m]], "scale": sc[m],
                       "tint": self.tint[ids[m]], "id": ids[m]}
        return out

    def alive_at(self, T: float) -> int:
        a = self.at(T)
        return int(len(a[0]["pos"]) + len(a[1]["pos"]))


def _plan(inp: SimIn, rng) -> dict:
    """Which chips are born, when, where (the change they come from) and their random make-up."""
    am = AMOUNTS.get(inp.amount, AMOUNTS["FEW"])
    w = inp.work
    area = w.grid.cell ** 2
    per = []                                        # (bit, preset, change indices)
    for b, bit in enumerate(inp.bits):
        sel = np.nonzero(w.bit == b)[0]
        if not len(sel):
            continue
        cum = np.cumsum(w.dh[sel] * area) * 1e9      # mm³
        for p in bit.presets:
            rate = p.per_mm3 * am["factor"]
            n = int(math.floor(cum[-1] * rate + rng.uniform()))
            per.append([b, p, sel, cum, rate, n])
    total = sum(x[5] for x in per)
    thin = min(1.0, am["births"] / total) if total > am["births"] else 1.0
    out = {"bit": [], "preset": [], "change": [], "t": []}
    for b, p, sel, cum, rate, n in per:
        n = int(math.floor(n * thin))
        if n <= 0:
            continue
        pos = (np.arange(n) + rng.uniform(size=n)) / (rate * thin)     # cumulative mm³ at each chip
        j = np.minimum(np.searchsorted(cum, pos, side="left"), len(sel) - 1)
        ch = sel[j]
        out["bit"].append(np.full(n, b, np.int32))
        out["preset"].append([p] * n)
        out["change"].append(ch)
        out["t"].append(w.t[ch])
    mist = None
    if inp.mist and am["factor"] > 0:
        mist = _plan_mist(inp, rng, am)
    if out["t"]:
        t = np.concatenate(out["t"])
        order = np.argsort(t, kind="stable")
        presets = [p for lst in out["preset"] for p in lst]
        plan = {"t": t[order], "bit": np.concatenate(out["bit"])[order],
                "change": np.concatenate(out["change"])[order],
                "preset": [presets[i] for i in order], "thin": thin, "mist": mist}
    else:
        plan = {"t": np.zeros(0), "bit": np.zeros(0, np.int32), "change": np.zeros(0, np.int64), "preset": [],
                "thin": thin, "mist": mist}
    return plan


def _plan_mist(inp: SimIn, rng, am) -> dict | None:
    """Coolant drops: a steady stream at the bit while it cuts."""
    vol = inp.work.removed_per_frame(inp.f0, inp.f1)
    cutting = np.nonzero(vol > 0)[0]
    if not len(cutting):
        return None
    per_frame = MIST_PER_SECOND / inp.fps * am["factor"]
    n = rng.poisson(per_frame, len(cutting))
    t = np.repeat(cutting + inp.f0 - 1.0, n) + rng.uniform(size=int(n.sum()))
    w = inp.work
    bit = np.zeros(len(t), np.int32)
    if len(inp.bits) > 1 and len(w.t):              # the bit that cut nearest in time
        j = np.clip(np.searchsorted(w.t, t), 0, len(w.t) - 1)
        bit = w.bit[j]
    return {"t": t, "bit": bit}


class _Sim:
    """The time-stepped flight of every chip (all chips in flight move together, in numpy)."""

    def __init__(self, inp: SimIn, plan: dict, rng):
        self.inp = inp
        self.w = inp.work
        self.g = self.w.grid
        self.fps = float(inp.fps)
        self.h = 1.0 / SUBSTEPS                       # frames per step
        self.dt = self.h / self.fps                    # seconds per step
        mist = plan["mist"]
        n_c = len(plan["t"])
        n_m = len(mist["t"]) if mist else 0
        n = n_c + n_m
        self.n = n
        presets = list(plan["preset"]) + [MIST] * n_m
        # shapes: (preset, variant) -> instance index
        keys = sorted({(p.family, p.bit) for p in presets})
        self.shapes = [(PRESETS.get(f"{fam}/{bit}") or (MIST if fam == "MIST" else WOOD_DUST), v)
                       for fam, bit in keys for v in range(VARIANTS)]
        base = {k: i * VARIANTS for i, k in enumerate(keys)}
        self.born = np.concatenate([plan["t"], mist["t"] if mist else np.zeros(0)])
        self.bit = np.concatenate([plan["bit"], mist["bit"] if mist else np.zeros(0, np.int32)]).astype(np.int64)
        self.change = np.concatenate([plan["change"], np.full(n_m, -1, np.int64)])
        self.is_mist = np.concatenate([np.zeros(n_c, bool), np.ones(n_m, bool)])
        self.pre_speed = np.array([p.speed for p in presets])
        self.pre_drag = np.array([p.drag for p in presets])
        self.pre_bounce = np.array([p.bounce for p in presets])
        self.pre_mix = np.array([(p.tangent, p.radial, p.up, p.spread) for p in presets]).reshape(-1, 4)
        self.pre_spin = np.array([p.spin for p in presets])
        self.pre_life = np.array([p.life for p in presets])
        self.vol = np.array([chip_volume(p) for p in presets])
        # random make-up, drawn in one fixed order
        self.slot = np.array([base[(p.family, p.bit)] for p in presets], np.int64) + rng.integers(0, VARIANTS, n)
        self.scale = rng.uniform(0.7, 1.3, n)
        self.tint = rng.uniform(0.0, 1.0, n)
        self.u_speed = rng.uniform(0.65, 1.3, n)
        self.u_spread = rng.normal(size=(n, 3))
        self.u_spin = rng.normal(size=(n, 3))
        self.u_angle = rng.uniform(0, 2 * math.pi, n)
        self.u_yaw = rng.uniform(0, 2 * math.pi, n)
        self.u_tilt = rng.normal(scale=0.12, size=(n, 2))
        self.u_q0 = rng.normal(size=(n, 4))
        self.u_q0 /= np.linalg.norm(self.u_q0, axis=1, keepdims=True)
        self.u_life = rng.uniform(0.6, 1.2, n)
        self.u_misc = rng.uniform(size=n)
        # results
        self.rest_t = np.full(n, np.inf)
        self.end_t = np.where(self.is_mist, self.born + self.pre_life * self.u_life * self.fps, np.inf)
        self.fade = np.where(self.is_mist, self.pre_life * self.u_life * self.fps * 0.4, 1.0)
        self.rest_p = np.zeros((n, 3))
        self.rest_q = np.tile([1.0, 0.0, 0.0, 0.0], (n, 1))
        self.rest_space = np.zeros(n, np.int8)
        self.rest_cell = np.full(n, -1, np.int64)     # the workpiece cell a chip lies on (-1: not on it)
        self.rest_pile = np.full(n, -1, np.int64)    # the pile cell it added to (riding or world; -1: none)
        self.fly = {"id": [], "p": [], "q": [], "s": []}
        self.frame_rows = {}
        # catch areas
        self.ride = inp.ride
        self.pile_r = np.zeros_like(self.ride.h)
        # below this a chip that has nothing under it has fallen off the table (and the workpiece)
        tops = self.ride.h[np.isfinite(self.ride.h)]
        wb = self.w.bottom[np.isfinite(self.w.bottom)]
        self.level = min(float(tops.min()) if len(tops) else np.inf, float(wb.min()) if len(wb) else np.inf)
        if not np.isfinite(self.level):
            self.level = 0.0
        self.static = inp.static
        self.pile_s = np.zeros_like(inp.static.h) if inp.static is not None else None
        self.floor_z = float(inp.floor_z)
        self.pile_cell_r = self.ride.cell ** 2
        self.pile_cell_s = inp.static.cell ** 2 if inp.static is not None else 1.0
        self.change_i = 0
        self.rest_order = []                         # chips in the order they came to rest (for the cap)
        self.rest_i = 0
        am = AMOUNTS.get(inp.amount, AMOUNTS["FEW"])
        self.cap = am["cap"]
        self.alive = 0
        self.max_alive = 0
        self.carry = inp.carry

    # -- surfaces ----------------------------------------------------------------

    def surf_ride(self, x, y):
        """Height of whatever moves with the workpiece under (x, y): the workpiece as cut now, the table, piles."""
        g, r = self.g, self.ride
        out = np.full(len(x), -np.inf)
        ix = ((x - g.x0) / g.cell).astype(np.int64)
        iy = ((y - g.y0) / g.cell).astype(np.int64)
        ok = (x >= g.x0) & (y >= g.y0) & (ix < g.nx) & (iy < g.ny)
        out[ok] = self.w.cur[iy[ok], ix[ok]]
        jx = ((x - r.x0) / r.cell).astype(np.int64)
        jy = ((y - r.y0) / r.cell).astype(np.int64)
        ok = (x >= r.x0) & (y >= r.y0) & (jx < r.nx) & (jy < r.ny)
        jx, jy = jx[ok], jy[ok]
        base = np.maximum(out[ok], r.h[jy, jx])
        out[ok] = base + np.where(np.isfinite(base), self.pile_r[jy, jx], 0.0)
        return out

    def surf_world(self, x, y):
        out = np.full(len(x), self.floor_z)
        st = self.static
        if st is not None:
            jx = ((x - st.x0) / st.cell).astype(np.int64)
            jy = ((y - st.y0) / st.cell).astype(np.int64)
            ok = (x >= st.x0) & (y >= st.y0) & (jx < st.nx) & (jy < st.ny)
            jx, jy = jx[ok], jy[ok]
            out[ok] = np.maximum(st.h[jy, jx], self.floor_z) + self.pile_s[jy, jx]
        return out

    def carry_at(self, t: float) -> np.ndarray:
        if self.carry is None or not len(self.carry):
            return np.eye(4)
        x = min(max(t - self.inp.f0, 0.0), len(self.carry) - 1.0)
        i = int(math.floor(x))
        j = min(i + 1, len(self.carry) - 1)
        f = x - i
        m = self.carry[i] * (1 - f) + self.carry[j] * f
        u, _s, vt = np.linalg.svd(m[:3, :3])             # keep it a rotation
        m = m.copy()
        m[:3, :3] = u @ vt
        return m

    # -- the workpiece being cut -------------------------------------------------

    def apply_changes(self, until: float) -> None:
        w = self.w
        i0 = self.change_i
        i1 = int(np.searchsorted(w.t, until, side="right"))
        if i1 <= i0:
            return
        cells = w.cells[i0:i1]
        w.cur.reshape(-1)[cells] = w.h_new[i0:i1]
        self.change_i = i1
        # chips lying on cells that are cut now are gone (the bit takes them along); piles there too
        on = np.nonzero(self.rest_cell >= 0)[0]
        if len(on):
            ucells, first = np.unique(cells, return_index=True)
            hit = np.isin(self.rest_cell[on], ucells)
            if hit.any():
                ids = on[hit]
                tt = w.t[i0:i1][first[np.searchsorted(ucells, self.rest_cell[ids])]]
                later = tt >= self.rest_t[ids] - 1e-9
                ids, tt = ids[later], tt[later]
                ok = np.isfinite(self.rest_t[ids]) & ~np.isfinite(self.end_t[ids])
                ids, tt = ids[ok], tt[ok]
                self.end_t[ids] = tt + 1.0
                self.fade[ids] = 1.0
                self._unpile(ids)
                self.rest_cell[ids] = -1
                self.alive -= len(ids)
        g = self.g
        iy, ix = np.divmod(cells, g.nx)
        x = g.x0 + (ix + 0.5) * g.cell
        y = g.y0 + (iy + 0.5) * g.cell
        rx, ry, ok = self.ride.index(x, y)
        self.pile_r[ry[ok], rx[ok]] = 0.0

    def _unpile(self, ids) -> None:
        if not len(ids):
            return
        ids = ids[self.rest_pile[ids] >= 0]
        sp = self.rest_space[ids]
        amt = BULK * self.vol[ids] * self.scale[ids] ** 3
        for val, pile, area in ((0, self.pile_r, self.pile_cell_r), (1, self.pile_s, self.pile_cell_s)):
            m = sp == val
            if m.any() and pile is not None:
                np.subtract.at(pile.reshape(-1), self.rest_pile[ids[m]], amt[m] / area)
                np.maximum(pile, 0.0, out=pile)
        self.rest_pile[ids] = -1

    # -- birth ---------------------------------------------------------------------

    def born_now(self, ids: np.ndarray, t: float) -> dict:
        """Start position and speed of chips born at time t (riding space)."""
        n = len(ids)
        w = self.w
        g = self.g
        o = np.zeros((n, 3))
        d = np.zeros((n, 3))
        R = np.zeros(n)
        flute = np.zeros(n)
        spin = np.ones(n)
        for b, bit in enumerate(self.inp.bits):
            m = self.bit[ids] == b
            if m.any():
                o[m], d[m] = bit.at(self.born[ids[m]])
                R[m], flute[m], spin[m] = bit.radius, bit.length, bit.spin
        ch = self.change[ids]
        has = ch >= 0
        rv = np.zeros((n, 3))
        if has.any():
            iy, ix = np.divmod(w.cells[ch[has]], g.nx)
            cx = g.x0 + (ix + 0.5) * g.cell
            cy = g.y0 + (iy + 0.5) * g.cell
            rv[has, 0] = cx - o[has, 0]
            rv[has, 1] = cy - o[has, 1]
        rv -= (rv * d).sum(axis=1, keepdims=True) * d
        ln = np.linalg.norm(rv, axis=1)
        e1 = np.cross(d, np.where(np.abs(d[:, :1]) < 0.9, [[1.0, 0, 0]], [[0, 1.0, 0]]))
        e1 /= np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-12)
        e2 = np.cross(d, e1)
        a = self.u_angle[ids]
        fallback = e1 * np.cos(a)[:, None] + e2 * np.sin(a)[:, None]
        rhat = np.where((ln > 1e-7)[:, None], rv / np.maximum(ln, 1e-12)[:, None], fallback)
        pos = o + rhat * (R * 0.97)[:, None]
        # height: where the chip leaves the cut - the old surface of the cell, or the rim of the hole
        z_old = o[:, 2] + R * 0.5
        if has.any():
            z_old = np.where(has, w.h_old[np.maximum(ch, 0)] if len(w.h_old) else z_old, z_old)
        rim_xy = o + rhat * (R * 1.3)[:, None]
        rim = g.sample(rim_xy[:, 0], rim_xy[:, 1], w.cur)
        z = np.maximum(z_old, np.where(np.isfinite(rim), rim, -np.inf))
        z = np.minimum(z, o[:, 2] + np.maximum(flute, 1e-4))
        z = np.where(np.isfinite(z), z, o[:, 2])
        pos[:, 2] = np.where(self.is_mist[ids], o[:, 2] + R * 0.5, z + 0.3 * MM)
        tang = np.cross(-d, rhat) * spin[:, None]
        mix = self.pre_mix[ids]
        sp = self.u_spread[ids]
        sp /= np.maximum(np.linalg.norm(sp, axis=1, keepdims=True), 1e-12)
        vdir = (tang * mix[:, :1] + rhat * mix[:, 1:2] + d * mix[:, 2:3] + sp * mix[:, 3:4])
        vdir /= np.maximum(np.linalg.norm(vdir, axis=1, keepdims=True), 1e-12)
        v = vdir * (self.pre_speed[ids] * self.u_speed[ids])[:, None]
        w_spin = self.u_spin[ids] * (self.pre_spin[ids] * 2 * math.pi / math.sqrt(3))[:, None]
        return {"p": pos, "v": v, "w": w_spin}

    # -- the main loop ---------------------------------------------------------------

    def run(self, progress=None) -> None:
        inp = self.inp
        n = self.n
        if n == 0:
            return
        order = np.argsort(self.born, kind="stable")
        bi = 0
        # flying chips
        fid = np.zeros(0, np.int64)
        P = np.zeros((0, 3))
        V = np.zeros((0, 3))
        W = np.zeros((0, 3))
        Q = np.zeros((0, 4))
        TQ = np.zeros(0)
        SP = np.zeros(0, np.int8)
        NB = np.zeros(0, np.int64)
        t = float(math.ceil(self.born[order[0]] - 1e-9) - 1)
        t_end = float(inp.f1) + 1.0
        steps = 0
        last_report = time.perf_counter()
        while t <= t_end:
            if not len(fid) and bi < n:                  # nothing in the air: jump to the next birth
                nxt = float(math.ceil(self.born[order[bi]] - 1e-9) - 1)
                if nxt > t:
                    t = nxt
            if not len(fid) and bi >= n:
                break
            t_new = t + self.h
            self.apply_changes(t_new)
            # births: once per frame, every chip that comes off during the coming frame (a chip is first
            # shown at the end of the frame it comes off in, so it starts at most one frame early)
            bj = bi
            if abs(t - round(t)) < 1e-9:
                while bj < n and self.born[order[bj]] <= t + 1.0 + 1e-9:
                    bj += 1
            if bj > bi:
                ids = order[bi:bj]
                bi = bj
                st = self.born_now(ids, t_new)
                fid = np.concatenate([fid, ids])
                P = np.concatenate([P, st["p"]])
                V = np.concatenate([V, st["v"]])
                W = np.concatenate([W, st["w"]])
                Q = np.concatenate([Q, self.u_q0[ids]])
                TQ = np.concatenate([TQ, np.full(len(ids), t_new)])
                SP = np.concatenate([SP, np.zeros(len(ids), np.int8)])
                NB = np.concatenate([NB, np.zeros(len(ids), np.int64)])
                self.alive += int((~self.is_mist[ids]).sum())
            if len(fid):
                drag = np.exp(-self.pre_drag[fid] * self.dt)
                V = V * drag[:, None]
                V[:, 2] -= G * self.dt
                P_new = P + V * self.dt
                hit_rest = np.zeros(len(fid), bool)
                gone = np.zeros(len(fid), bool)
                ride = SP == 0
                surf = np.empty(len(fid))
                if ride.any():
                    surf[ride] = self.surf_ride(P_new[ride, 0], P_new[ride, 1])
                if not ride.all():
                    surf[~ride] = self.surf_world(P_new[~ride, 0], P_new[~ride, 1])
                below = P_new[:, 2] < surf
                if below.any():
                    idx = np.nonzero(below)[0]
                    s_new = surf[idx]
                    tol = 0.5 * MM + np.abs(V[idx, 2]) * self.dt
                    from_above = P[idx, 2] >= s_new - tol
                    mist = self.is_mist[fid[idx]]            # coolant: gone at the first touch
                    gone[idx[mist]] = True
                    self.end_t[fid[idx[mist]]] = t_new
                    sel = from_above & ~mist
                    fl = idx[sel]
                    wl = idx[~from_above & ~mist]
                    if len(fl):
                        P_new[fl, 2] = s_new[sel]
                        e = self.pre_bounce[fid[fl]]
                        V[fl, 2] = -V[fl, 2] * e
                        V[fl, :2] *= 0.55
                        Q[fl] = self._q_at(Q[fl], W[fl], TQ[fl], t_new)
                        TQ[fl] = t_new
                        W[fl] *= 0.5
                        NB[fl] += 1
                        still = (np.abs(V[fl, 2]) < REST_SPEED) | (NB[fl] >= MAX_BOUNCES) | (e <= 0.0)
                        hit_rest[fl[still]] = True
                    if len(wl):                             # a wall: back to where it was, bounce sideways
                        P_new[wl, :2] = P[wl, :2]
                        V[wl, :2] *= -0.4
                        W[wl] *= 0.7
                # off everything that moves with the workpiece: on to world space (machine bed, floor)
                off = ride & ~below & ~np.isfinite(surf) & (P_new[:, 2] < self.level)
                if off.any():
                    sw = np.nonzero(off)[0]
                    C = self.carry_at(t_new)
                    Rm = C[:3, :3]
                    Q[sw] = q_mul(np.broadcast_to(q_from_matrix(Rm), (len(sw), 4)),
                                  self._q_at(Q[sw], W[sw], TQ[sw], t_new))
                    TQ[sw] = t_new
                    P_new[sw] = P_new[sw] @ Rm.T + C[:3, 3]
                    V[sw] = V[sw] @ Rm.T
                    W[sw] = W[sw] @ Rm.T
                    SP[sw] = 1
                P = P_new
                # mist that lived its life
                lived = self.is_mist[fid] & (t_new >= self.end_t[fid])
                gone |= lived
                # come to rest
                if hit_rest.any():
                    self._rest(fid[hit_rest], P[hit_rest], SP[hit_rest], t_new)
                drop = hit_rest | gone
                if drop.any():
                    keep = ~drop
                    fid, P, V, W, Q, TQ, SP, NB = (fid[keep], P[keep], V[keep], W[keep], Q[keep], TQ[keep],
                                                   SP[keep], NB[keep])
                # too many chips: the oldest resting ones fade away
                if self.cap and self.alive > self.cap * 1.02:
                    self._retire(self.alive - int(self.cap * 0.98), t_new)
                self.max_alive = max(self.max_alive, self.alive)
            # a whole frame: remember where the flying chips are
            if abs(t_new - round(t_new)) < 1e-9 and len(fid):
                f = int(round(t_new))
                if inp.f0 <= f <= inp.f1:
                    self.frame_rows[f] = len(fid)
                    self.fly["id"].append(fid.astype(np.int32))
                    self.fly["p"].append(P.astype(np.float32))
                    self.fly["q"].append(self._q_at(Q, W, TQ, t_new).astype(np.float16))
                    self.fly["s"].append(SP.copy())
            t = t_new
            steps += 1
            if progress is not None and time.perf_counter() - last_report > 0.25:
                last_report = time.perf_counter()
                progress(min(1.0, (t - inp.f0) / max(1.0, inp.f1 - inp.f0)))
        # whatever is still in the air at the end stays where it is
        if len(fid):
            nm = ~self.is_mist[fid]
            self._rest(fid[nm], P[nm], SP[nm], t)
        self.steps = steps
        self.apply_changes(np.inf)

    def _q_at(self, Q, W, TQ, t) -> np.ndarray:
        dq = q_from_rotvec(W * ((t - TQ) / self.fps)[:, None])
        q = q_mul(dq, Q)
        return q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-12)

    def _rest(self, ids, P, SP, t) -> None:
        if not len(ids):
            return
        ids = np.asarray(ids)
        self.rest_t[ids] = t
        self.rest_space[ids] = SP
        yaw = self.u_yaw[ids]
        tilt = self.u_tilt[ids]
        qy = np.stack([np.cos(yaw / 2), np.zeros_like(yaw), np.zeros_like(yaw), np.sin(yaw / 2)], axis=1)
        qt = q_from_rotvec(np.stack([tilt[:, 0], tilt[:, 1], np.zeros(len(ids))], axis=1))
        self.rest_q[ids] = q_mul(qy, qt)
        p = P.copy()
        self.rest_p[ids] = p
        amt = BULK * self.vol[ids] * self.scale[ids] ** 3
        r = SP == 0
        if r.any():
            ix, iy, ok = self.ride.index(p[r, 0], p[r, 1])
            cell = np.where(ok, iy * self.ride.nx + ix, -1)
            self.rest_pile[ids[r]] = cell
            np.add.at(self.pile_r.reshape(-1), cell[ok], amt[r][ok] / self.pile_cell_r)
            # lying on the workpiece (not on the table beside it): gone when the bit cuts there
            hw = self.g.sample(p[r, 0], p[r, 1], self.w.cur)
            hr = self.ride.sample(p[r, 0], p[r, 1])
            gx, gy, _gok = self.g.index(p[r, 0], p[r, 1])
            on_wp = np.isfinite(hw) & (hw >= hr - 1e-9)
            self.rest_cell[ids[r]] = np.where(on_wp, gy * self.g.nx + gx, -1)
        s = SP == 1
        if s.any() and self.static is not None:
            ix, iy, ok = self.static.index(p[s, 0], p[s, 1])
            cell = np.where(ok, iy * self.static.nx + ix, -1)
            self.rest_pile[ids[s]] = cell
            np.add.at(self.pile_s.reshape(-1), cell[ok], amt[s][ok] / self.pile_cell_s)
        self.rest_order.append(ids[np.argsort(ids)])

    def _retire(self, k: int, t: float) -> None:
        done = 0
        while done < k and self.rest_i < len(self.rest_order):
            batch = self.rest_order[self.rest_i]
            live = batch[~np.isfinite(self.end_t[batch])]
            take = live[:k - done]
            if len(take):
                self.end_t[take] = t + RETIRE_FADE * self.fps
                self.fade[take] = RETIRE_FADE * self.fps
                self._unpile(take)
                self.rest_cell[take] = -1
                done += len(take)
                self.alive -= len(take)
            if len(take) == len(live):
                self.rest_i += 1
            else:
                self.rest_order[self.rest_i] = batch[~np.isin(batch, take)]


def simulate(inp: SimIn, progress=None) -> Bake:
    """Work out every chip of the set-up, start to end. Same input -> same output, bit for bit."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(inp.seed)
    plan = _plan(inp, rng)
    sim = _Sim(inp, plan, rng)
    sim.run(progress)
    nf = inp.f1 - inp.f0 + 1
    counts = np.zeros(nf + 1, np.int64)
    for f, c in sim.frame_rows.items():
        counts[f - inp.f0 + 1] = c
    starts = np.cumsum(counts)
    if sim.fly["id"]:
        fly = {k: np.concatenate(v) for k, v in sim.fly.items()}
    else:
        fly = {"id": np.zeros(0, np.int32), "p": np.zeros((0, 3), np.float32), "q": np.zeros((0, 4), np.float16),
               "s": np.zeros(0, np.int8)}
    vol = inp.work.removed_per_frame(inp.f0, inp.f1)
    stats = {"chips": int(sim.n), "mist": int(sim.is_mist.sum()), "max_alive": int(sim.max_alive),
             "thinned": float(plan["thin"]), "steps": int(getattr(sim, "steps", 0)),
             "seconds": time.perf_counter() - t0, "removed_mm3": float(vol.sum() * 1e9)}
    return Bake(shapes=sim.shapes, lift=np.zeros(len(sim.shapes)), born=sim.born, rest_t=sim.rest_t,
                end_t=sim.end_t, fade=sim.fade, rest_p=sim.rest_p, rest_q=sim.rest_q, rest_space=sim.rest_space,
                slot=sim.slot, scale=sim.scale.astype(np.float32), tint=sim.tint.astype(np.float32), f0=inp.f0,
                frame_start=starts, fly_id=fly["id"], fly_p=fly["p"], fly_q=fly["q"], fly_space=fly["s"],
                volume=vol, stats=stats)


def describe(bake: Bake | None) -> str:
    if bake is None:
        return ""
    s = bake.stats
    n = s.get("chips", 0) - s.get("mist", 0)
    return f"{n:,} chips worked out in {s.get('seconds', 0.0):.1f} s"
