"""Rigging gear (task 0232, Lifting lane L5): sling sets, shackles, spreader beams and frames – plain Python.

The built-in samples are invented, in size classes, with values in the range of public catalogues; they are made
here as files of the lifting library format (``core/lifting_library.py``, ``"sample": true``) and never written to
disk. The user's own gear is a file like a crane's, in the library folder "Lifting equipment": ``kind`` "sling",
"shackle", "spreader_beam" or "lifting_frame", ``wll`` (per leg for a sling set; per way of use allowed), ``mass``
(t, the item's own mass without its legs' length) and a table ``rigging``:

* sling set: ``material`` ("chain" grade 8 | "wire" | "round"), ``legs`` (1, 2, 3 or 4), ``length`` (m, each leg),
  ``mass_per_m`` (kg/m of one leg), ``diameter`` (mm, the chain's or rope's), ``modes`` (straight 1.0, choke 0.8,
  basket 2.0 – the factors on the leg WLL), ``colour`` (a round sling's colour by EN 1492-2), ``master_link`` (kg).
* shackle: ``pin`` (mm, its diameter), ``inside_width``, ``inside_length``, ``bow`` (mm, the bow's own bar diameter);
  the mass in ``mass`` (t).
* spreader beam / lifting frame: ``top`` and ``bottom``: its padeyes [x, y, z] (m) in its own frame (z up, the
  middle of the beam at 0), ``height`` (m, the beam's depth), ``cog`` [x, y, z] (m).

``gear_of(item)`` reads any of them into a :class:`Gear` (SI: kg, m). Units: the file's mass unit for ``wll`` and
``mass``; the lengths above are fixed (m, mm as named).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import lifting
from . import lifting_library as LL

KINDS = ("sling", "shackle", "spreader_beam", "lifting_frame")
MATERIALS = {"chain": "Chain sling, grade 8", "wire": "Wire rope sling", "round": "Round sling"}
# EN 1492-2: the colour of a round sling says its WLL straight (t)
ROUND_COLOURS = ((1.0, "violet"), (2.0, "green"), (3.0, "yellow"), (4.0, "grey"), (5.0, "red"), (6.0, "brown"),
                 (8.0, "blue"), (10.0, "orange"))
MODES_CHAIN = {"straight": 1.0, "choke": 0.8}
MODES_WIRE = {"straight": 1.0, "choke": 0.8, "basket": 2.0}
MODES_ROUND = {"straight": 1.0, "choke": 0.8, "basket": 2.0}
# grade 8 chain: diameter (mm) -> WLL of one leg (t) and mass (kg/m), the usual EN 818-4 table's size steps
CHAIN = ((7, 1.5, 1.1), (8, 2.0, 1.4), (10, 3.15, 2.2), (13, 5.3, 3.8), (16, 8.0, 5.7), (20, 12.5, 9.0),
         (22, 15.0, 10.9), (26, 21.2, 15.2), (32, 31.5, 22.9))
# wire rope legs (invented steps): diameter (mm), WLL (t), kg/m
WIRE = ((12, 1.5, 0.6), (16, 2.7, 1.0), (20, 4.2, 1.6), (26, 7.1, 2.7), (32, 10.8, 4.1), (40, 16.8, 6.4),
        (52, 28.4, 10.8))
# shackles (bow, safety pin): WLL (t) – dimensions scaled from the WLL (invented, the shape of public tables)
SHACKLES = (2.0, 3.25, 4.75, 6.5, 8.5, 9.5, 12.0, 13.5, 17.0, 25.0, 35.0, 55.0, 85.0, 120.0, 150.0)
DEFAULT_LENGTH = 3.0          # m: a sling set's legs when nothing else is said


def _sample(kind: str, cls: str, name: str, wll, mass_t: float, rigging: dict) -> dict:
    d = LL.new_item(kind, cls, name, "t", "m", wll=wll, mass=round(mass_t, 5), rigging=rigging,
                    source="invented sample – Fresing Render (task 0232)")
    d.pop("charts", None)
    d["sample"] = True
    return d


def _round_colour(wll: float) -> str:
    return next((c for w, c in ROUND_COLOURS if abs(w - wll) < 1e-6), "")


def builtin_data() -> list[dict]:
    """Every built-in sample as a library file's data."""
    out = []
    for legs in (1, 2, 4):
        word = {1: "1-leg", 2: "2-leg", 4: "4-leg"}[legs]
        for d, wll, kgm in CHAIN:
            if d < 10:
                continue
            out.append(_sample("sling", f"CH8-{legs}L-{d}", f"Chain grade 8, {word}, {wll:g} t per leg ({d} mm)",
                               wll, 0.0, {"material": "chain", "legs": legs, "length": DEFAULT_LENGTH,
                                          "mass_per_m": kgm, "diameter": d, "modes": MODES_CHAIN,
                                          "master_link": round(0.9 * wll * (1 + legs / 4), 2)}))
        for d, wll, kgm in WIRE:
            out.append(_sample("sling", f"WR-{legs}L-{d}", f"Wire rope sling, {word}, {wll:g} t per leg ({d} mm)",
                               wll, 0.0, {"material": "wire", "legs": legs, "length": DEFAULT_LENGTH,
                                          "mass_per_m": kgm, "diameter": d, "modes": MODES_WIRE,
                                          "master_link": round(0.6 * wll * (1 + legs / 4), 2)}))
        for wll, colour in ROUND_COLOURS:
            out.append(_sample("sling", f"RS-{legs}L-{wll:g}", f"Round sling, {word}, {wll:g} t ({colour})",
                               wll, 0.0, {"material": "round", "legs": legs, "length": DEFAULT_LENGTH,
                                          "mass_per_m": round(0.12 + 0.14 * wll, 3),
                                          "diameter": round(28 + 6 * wll, 1), "modes": MODES_ROUND,
                                          "colour": colour, "master_link": round(0.5 * wll * (legs > 1), 2)}))
    for wll in SHACKLES:
        pin = 9.8 * math.sqrt(wll)
        out.append(_sample("shackle", f"SH-{wll:g}", f"Bow shackle {wll:g} t", wll, 0.00012 * wll ** 1.55,
                           {"pin": round(pin, 1), "inside_width": round(1.6 * pin, 1),
                            "inside_length": round(3.9 * pin, 1), "bow": round(0.85 * pin, 1)}))
    for cls, span, wll, mass in (("SB-10", 4.0, 10.0, 0.35), ("SB-25", 6.0, 25.0, 1.1), ("SB-50", 8.0, 50.0, 2.6)):
        h = 0.06 * span + 0.12
        out.append(_sample("spreader_beam", cls, f"Spreader beam {cls}: {span:g} m, {wll:g} t", wll, mass,
                           {"top": [[-0.15 * span, 0.0, h / 2 + 0.08], [0.15 * span, 0.0, h / 2 + 0.08]],
                            "bottom": [[-span / 2, 0.0, -h / 2 - 0.08], [span / 2, 0.0, -h / 2 - 0.08]],
                            "height": round(h, 3), "cog": [0.0, 0.0, 0.0], "span": span}))
    # a 4-point frame for a 20 ft container (the bottom padeyes over its top corner castings, 5.853 x 2.259 m)
    out.append(_sample("lifting_frame", "LF-20", "Lifting frame LF-20 (20 ft container): 5.85 x 2.26 m, 30 t", 30.0,
                       1.4, {"top": [[-1.2, 0.0, 0.25], [1.2, 0.0, 0.25]],
                             "bottom": [[2.9265, 1.1295, -0.17], [-2.9265, 1.1295, -0.17],
                                        [-2.9265, -1.1295, -0.17], [2.9265, -1.1295, -0.17]],
                             "height": 0.3, "cog": [0.0, 0.0, 0.0], "span": 5.853}))
    return out


_BUILTIN: list = []


def builtins() -> list:
    """The built-in samples as library items (``path`` = "builtin:<class>")."""
    if not _BUILTIN:
        for d in builtin_data():
            it = LL.from_data(d, builtin=True)
            it.path = "builtin:" + d["class"]
            _BUILTIN.append(it)
    return list(_BUILTIN)


def is_rigging(item) -> bool:
    return item.kind in KINDS


def list_gear(user_items=()) -> list:
    """The user's own gear (from the library listing) first, then the built-ins."""
    return [it for it in user_items if is_rigging(it)] + builtins()


def find(path: str, user_items=()):
    """The item of a path ("builtin:<class>" or a file / folder of the user's library), or None."""
    for it in list_gear(user_items):
        if path and path in (it.path, it.folder):
            return it
    return None


@dataclass
class Gear:
    """One piece of rigging gear, SI."""
    name: str
    kind: str
    cls: str = ""
    wll: float | None = None          # kg (a sling: per leg)
    mass: float = 0.0                 # kg, own (fittings; a sling's legs come from their length)
    material: str = ""
    legs: int = 1
    length: float = DEFAULT_LENGTH    # m, each leg
    mass_per_m: float = 0.0           # kg/m of one leg
    diameter: float = 0.0             # m
    modes: dict = field(default_factory=dict)
    colour: str = ""
    master_link: float = 0.0          # kg
    pin: float = 0.0                  # m (shackle)
    inside_width: float = 0.0
    inside_length: float = 0.0
    bow: float = 0.0
    top: list = field(default_factory=list)       # m, spreader frame
    bottom: list = field(default_factory=list)
    height: float = 0.0
    cog: tuple = (0.0, 0.0, 0.0)
    sample: bool = False
    problems: list = field(default_factory=list)

    def sling_mass(self, lengths=None) -> float:
        """A sling set's mass (kg): its legs' lengths x mass per metre + the master link."""
        ls = list(lengths) if lengths is not None else [self.length] * self.legs
        return sum(ls) * self.mass_per_m + self.master_link


def _vecs(v) -> list:
    if not isinstance(v, list) or not all(isinstance(p, list) and len(p) == 3 and all(LL._num(x) for x in p)
                                          for p in v):
        raise LL.LibraryError("padeyes must be a list of [x, y, z] in metres")
    return [tuple(float(x) for x in p) for p in v]


def gear_of(item) -> Gear:
    """Read an item (library ``Item``) into a Gear; its problems (plain words) in ``Gear.problems``."""
    d = item.data if hasattr(item, "data") else item
    g = Gear(name=str(d.get("name", "")), kind=str(d.get("kind", "")), cls=str(d.get("class", "")))
    if getattr(item, "problems", None):
        g.problems = list(item.problems)
        return g
    if g.kind not in KINDS:
        g.problems.append(f"'{g.name}' is not rigging gear (kind '{g.kind}').")
        return g
    fm = lifting.MASS_UNITS[LL.units_of(d)[0]]
    g.sample = LL.is_sample(d)
    try:
        g.wll = LL.wll_of(item)
    except LL.LibraryError as e:
        g.problems.append(str(e))
    m = d.get("mass", 0.0)
    g.mass = float(m if not isinstance(m, dict) else sum(m.values())) * fm
    r = d.get("rigging") or {}
    if not isinstance(r, dict):
        g.problems.append("'rigging' must be a table.")
        return g
    try:
        if g.kind == "sling":
            g.material = str(r.get("material", "chain"))
            if g.material not in MATERIALS:
                g.problems.append(f"Unknown sling material '{g.material}': chain, wire or round.")
            g.legs = int(r.get("legs", 1))
            if g.legs not in (1, 2, 3, 4):
                g.problems.append("A sling set has 1, 2, 3 or 4 legs.")
            g.length = float(r.get("length", DEFAULT_LENGTH))
            if not g.length > 0:
                g.problems.append("The legs' length must be above 0.")
            g.mass_per_m = float(r.get("mass_per_m", 0.0))
            g.diameter = float(r.get("diameter", 16.0)) / 1000.0
            g.modes = dict(r.get("modes") or {"straight": 1.0})
            g.colour = str(r.get("colour", ""))
            g.master_link = float(r.get("master_link", 0.0))
        elif g.kind == "shackle":
            g.pin = float(r.get("pin", 20.0)) / 1000.0
            g.inside_width = float(r.get("inside_width", 1.6 * g.pin * 1000)) / 1000.0
            g.inside_length = float(r.get("inside_length", 3.9 * g.pin * 1000)) / 1000.0
            g.bow = float(r.get("bow", 0.85 * g.pin * 1000)) / 1000.0
        else:
            g.top = _vecs(r.get("top"))
            g.bottom = _vecs(r.get("bottom"))
            if not g.top or not g.bottom:
                g.problems.append("A spreader needs its top and bottom padeyes.")
            g.height = float(r.get("height", 0.3))
            g.cog = tuple(float(x) for x in r.get("cog", (0.0, 0.0, 0.0)))
    except (TypeError, ValueError, LL.LibraryError) as e:
        g.problems.append(f"'{g.name}': {e}")
    return g


def label(g: Gear) -> str:
    """A short name for a button: 'Chain 4-leg 8 t', 'Shackle 4.75 t', 'LF-20'."""
    t = f"{g.wll / 1000.0:g} t" if g.wll else ""
    if g.kind == "sling":
        word = {"chain": "Chain", "wire": "Wire rope", "round": "Round sling"}.get(g.material, "Sling")
        return f"{word} {g.legs}-leg {t}".strip()
    if g.kind == "shackle":
        return f"Shackle {t}".strip()
    return g.cls or g.name


def shackle_for(force_kg: float, user_items=()) -> object | None:
    """The smallest built-in shackle whose WLL covers a leg force (kg as a mass), or None."""
    best = None
    for it in builtins():
        if it.kind != "shackle":
            continue
        w = LL.wll_of(it)
        if w >= force_kg and (best is None or w < LL.wll_of(best)):
            best = it
    return best


def sling_for(force_kg: float, legs: int, material: str = "chain"):
    """The smallest built-in sling set of a material and leg count whose leg WLL covers a leg force, or None."""
    best = None
    for it in builtins():
        if it.kind != "sling":
            continue
        r = it.data["rigging"]
        if r["legs"] != legs or r["material"] != material:
            continue
        w = LL.wll_of(it)
        if w >= force_kg and (best is None or w < LL.wll_of(best)):
            best = it
    return best
