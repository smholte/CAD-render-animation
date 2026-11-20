"""Standard kinds, colours and sizes of hoses, cables and drag chains (task 0243). No Blender.

Every hose, cable or drag chain may get a **kind** (hydraulic hose, pneumatic tube, wire rope, open chain …), a
**colour** of that kind and a **size** from the kind's list. The kind brings the look (a material of the library,
``core/materials_lib.py``, and its colour), the size brings the numbers: a hose's or cable's outer diameter and its
smallest bend radius, a chain's outer width and height, its link pitch and its bend radii. "Custom" (size id "")
leaves the numbers as the user typed them.

Units: metres (the tables below are written in mm and converted once).

Sources of the sizes (owner's rule: public standards where one exists, checked at a source; makers' data sheets that
quote a paywalled standard are named as such). Checked on 20 Nov 2026 through web search results of these pages –
the standards themselves are paywalled and were not read:

* Hydraulic rubber hose, EN 853 type 2SN (= SAE J517 100R2AT, two steel-wire braids): outer diameter (the middle of
  the range the data sheets give) and smallest bend radius per DN, as quoted by the data sheets
  hoseworld.com/acatalog/144.pdf, hiparts.co.za "2 SN.pdf", tubes-international.com "hydraulic_rubber_hoses.pdf"
  and the bend series 100 … 630 mm of EN 853:2015's preview (standards.iteh.ai). Steel-braided hose takes the same
  sizes (the task's choice: "steel-braided like hydraulic").
* Pneumatic polyurethane tube, metric outer diameter 4 / 6 / 8 / 10 / 12 / 16 mm: inner diameter and smallest bend
  radius are one maker's typical values (SMC series TU, content2.smcetech.com/pdf/TU.pdf); no standard for the
  sizes was found. 16 mm: the bend radius is not in that sheet – here 3.5 x the outer diameter (invented, as 12 mm).
* Steel wire rope: nominal diameters of the series makers list under EN 12385-4 (the standard's own tables were not
  read); the smallest bend = half the sheave diameter for ISO 4308-1 / FEM 1.001 sheave factor h2 = 20 (group M5,
  D >= 20 d, values quoted by kinocranes.com's sheave calculator) – the radius to the middle of the rope = 10 d.
* No standard: machine (drag-chain) cables, power cables, the offshore power cable, protective sleeves and drag
  chains. Their series below are **invented**, generic round numbers – no maker's names, part numbers or catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MM = 0.001
CUSTOM = ""                      # the size id of "Custom": the numbers as the user typed them
FAMILIES = ("hose", "cable", "chain")


@dataclass(frozen=True)
class Colour:
    id: str
    label: str
    srgb: tuple                  # for the swatch (0 … 1)
    material: str                # a material id of core/materials_lib.py
    text: str = ""               # the colour text the material takes (needs_color materials), e.g. "#2060B0"
    look: str = ""               # cables of blender/paths.py: the cable look it goes with ("POWER", "SERVED", "ROPE")
    group: str = ""              # the material group's name; "" = "<kind label>, <colour label>"


@dataclass(frozen=True)
class Size:
    id: str
    label: str
    od: float = 0.0              # m: hose / cable outer diameter
    bend: float = 0.0            # m: smallest bend radius (to the middle of the hose / cable)
    note: str = ""               # e.g. "DN 12, 1/2 inch"
    # drag chain
    width: float = 0.0           # m: outer width across the chain
    height: float = 0.0          # m: outer height of one run
    pitch: float = 0.0           # m: pin to pin
    radii: tuple = ()            # m: the bend radii this size comes with (to the pins)


@dataclass(frozen=True)
class Kind:
    id: str
    family: str                  # "hose" | "cable" | "chain"
    number: int                  # fixed number stored in .blend files: NEVER change or reuse
    label: str
    description: str
    colours: tuple
    sizes: tuple
    pattern: str = ""            # a cable-look pattern drawn along it (blender/cable_looks.py): "HOSE", "BRAID", "SLEEVE"
    stiffness: float = -1.0      # a hose's stiffness / sag the kind starts with (-1 = leave it)
    sag: float = -1.0
    links: str = ""              # chains: the link shape of core/flex_chain.link_mesh
    extra: dict = field(default_factory=dict)


def _hex(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _c(cid: str, label: str, hexv: str, material: str, **kw) -> Colour:
    return Colour(cid, label, _hex(hexv), material, text=kw.pop("text", "#" + hexv.lstrip("#").upper()), **kw)


def _round(cid: str, label: str, od_mm: float, bend_mm: float, note: str = "") -> Size:
    return Size(cid, label, od=od_mm * MM, bend=bend_mm * MM, note=note)


# ---- hoses ----------------------------------------------------------------------------------------------------
# EN 853 2SN / SAE 100R2AT: (DN, inch, outer diameter mm, smallest bend mm) – see the module's docstring
_EN853_2SN = ((6, "1/4", 15.4, 100), (8, "5/16", 17.0, 115), (10, "3/8", 19.0, 130), (12, "1/2", 22.6, 180),
              (16, "5/8", 25.8, 200), (19, "3/4", 29.7, 240), (25, "1", 38.5, 300), (31, "1 1/4", 48.9, 420),
              (38, "1 1/2", 55.5, 500), (51, "2", 68.2, 630))
HYDRAULIC_SIZES = tuple(_round(f"DN{dn}", f"DN {dn} ({inch} in)", od, bend, f"EN 853 2SN, DN {dn}, {inch} inch")
                        for dn, inch, od, bend in _EN853_2SN)
# metric PU tube: (outer, inner, smallest bend) mm – SMC TU's typical values; 16 mm bend invented (module docstring)
_PU = ((4, 2.5, 10), (6, 4.0, 15), (8, 5.0, 20), (10, 6.5, 27), (12, 8.0, 35), (16, 11.0, 56))
PNEUMATIC_SIZES = tuple(_round(f"OD{od}", f"{od} x {inner:g} mm", od, bend, f"outer {od} mm, inner {inner:g} mm")
                        for od, inner, bend in _PU)
# protective spiral sleeve (invented): outer diameter, smallest bend 4 x
SLEEVE_SIZES = tuple(_round(f"S{od}", f"Sleeve {od} mm", od, 4 * od) for od in (16, 20, 25, 32, 40, 50, 63))

# ---- cables ---------------------------------------------------------------------------------------------------
# invented: drag-chain cable, smallest bend 7.5 x its diameter (a usual figure for cables made to move)
MACHINE_SIZES = tuple(_round(f"M{od:g}", f"{od:g} mm", od, 7.5 * od) for od in (6, 8, 10, 12, 14, 18, 22, 28))
# invented: fixed power cable, smallest bend 10 x
POWER_SIZES = tuple(_round(f"P{od}", f"{od} mm", od, 10 * od) for od in (10, 14, 18, 24, 32, 40, 50, 60))
# invented: offshore export / array cable, smallest bend 20 x
OFFSHORE_SIZES = tuple(_round(f"O{od}", f"{od} mm", od, 20 * od) for od in (100, 120, 150, 180, 200, 250, 300))
# wire rope: nominal diameters (EN 12385-4 series as makers list it), smallest bend 10 d (sheave D = 20 d, M5)
ROPE_SIZES = tuple(_round(f"R{d}", f"{d} mm", d, 10 * d, "sheave at least 20 x d (ISO 4308-1, M5)")
                   for d in (6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64))


# ---- drag chains (invented series) ------------------------------------------------------------------------------
def _chain(inner_h: int, inner_w: int, outer_h: int, outer_w: int, pitch: int, radii: tuple) -> Size:
    return Size(f"C{inner_h}x{inner_w}", f"Chain {inner_h} x {inner_w}", width=outer_w * MM, height=outer_h * MM,
                pitch=pitch * MM, radii=tuple(r * MM for r in radii), bend=radii[0] * MM,
                note=f"inside {inner_h} x {inner_w} mm, outside {outer_h} x {outer_w} mm, link {pitch} mm")


PLASTIC_CHAIN_SIZES = (
    _chain(10, 15, 14, 23, 15, (18, 28, 38)),
    _chain(15, 25, 21, 35, 20, (28, 38, 48, 75)),
    _chain(20, 38, 28, 50, 30, (48, 75, 100)),
    _chain(25, 50, 35, 64, 35, (75, 100, 125)),
    _chain(35, 75, 48, 95, 50, (100, 125, 150, 200)),
    _chain(45, 100, 60, 125, 60, (150, 200, 250)),
    _chain(60, 150, 80, 180, 80, (200, 250, 300)),
)
STEEL_CHAIN_SIZES = (
    _chain(50, 100, 75, 140, 90, (150, 200, 300)),
    _chain(75, 150, 105, 200, 125, (200, 300, 400)),
    _chain(100, 200, 135, 260, 175, (300, 400, 500)),
)

_PLASTIC = (_c("BLACK", "Black", "#1A1A1A", "plastic_matte"), _c("GREY", "Grey", "#7E8186", "plastic_matte"),
            _c("ORANGE", "Orange", "#E8650E", "plastic_matte"))

KINDS: tuple = (
    # hoses
    Kind("HYDRAULIC", "hose", 1, "Hydraulic hose", "Black rubber hose with two steel-wire braids inside (EN 853 2SN), "
         "a printed line along it", (_c("BLACK", "Black", "#111111", "hose_hydraulic"),
                                     _c("GREY", "Grey", "#5A5C5F", "hose_hydraulic")),
         HYDRAULIC_SIZES, pattern="HOSE", stiffness=0.8, sag=0.4),
    Kind("BRAIDED", "hose", 2, "Steel-braided hose", "A hose with a woven stainless-steel braid on the outside",
         (_c("STAINLESS", "Stainless steel", "#B8BBBE", "hose_braided", text=""),),
         HYDRAULIC_SIZES, pattern="BRAID", stiffness=0.85, sag=0.3),
    Kind("PNEUMATIC", "hose", 3, "Pneumatic tube", "A matte polyurethane air tube (metric outer diameter)",
         (_c("BLUE", "Blue", "#1F5FA8", "plastic_matte"), _c("BLACK", "Black", "#1A1A1A", "plastic_matte"),
          _c("CLEAR", "Clear", "#DDE6EA", "pu_tube_clear", text=""), _c("RED", "Red", "#B0201C", "plastic_matte"),
          _c("YELLOW", "Yellow", "#E8B600", "plastic_matte"), _c("GREEN", "Green", "#2E8B3D", "plastic_matte"),
          _c("SILVER", "Silver", "#A9ADB1", "plastic_matte")),
         PNEUMATIC_SIZES, stiffness=0.35, sag=0.3),
    Kind("SLEEVE", "hose", 4, "Protective sleeve", "A spiral wrap round a hose, the hose showing in its gaps",
         (_c("BLACK", "Black", "#1E1E1E", "hose_sleeve"), _c("ORANGE", "Orange", "#E8650E", "hose_sleeve"),
          _c("YELLOW", "Yellow", "#E8B600", "hose_sleeve")),
         SLEEVE_SIZES, pattern="SLEEVE", stiffness=0.8, sag=0.4),
    # cables (MACHINE and POWER also on a hose item: a cable between two ends)
    Kind("MACHINE", "cable", 11, "Machine cable", "A PUR cable made to move in a drag chain",
         (_c("GREY", "Grey", "#6E7176", "plastic_matte"), _c("ORANGE", "Orange", "#E8650E", "plastic_matte"),
          _c("BLACK", "Black", "#1A1A1A", "plastic_matte"), _c("GREEN", "Green", "#2E8B3D", "plastic_matte")),
         MACHINE_SIZES, stiffness=0.3, sag=0.5),
    Kind("POWER", "cable", 12, "Power cable", "A fixed power cable with a smooth sheath",
         (_c("BLACK", "Black", "#121212", "cable_black", text=""), _c("GREY", "Grey", "#6E7176", "plastic_matte")),
         POWER_SIZES, stiffness=0.6, sag=0.5),
    Kind("OFFSHORE", "cable", 13, "Offshore power cable", "A large export or array cable: black with yellow "
         "stripes, or a served yarn cover with marker spirals",
         (Colour("STRIPES", "Black, yellow stripes", _hex("#F0B400"), "cable_power", look="POWER",
                 group="Power cables"),
          Colour("SERVED", "Served yarn, yellow spirals", _hex("#2A2A2A"), "cable_served", look="SERVED",
                 group="Served cables")),
         OFFSHORE_SIZES),
    Kind("ROPE", "cable", 14, "Wire rope", "Steel wire rope, six strands",
         (Colour("BRIGHT", "Bright", _hex("#C8CACC"), "wire_rope", look="ROPE", group="Wire ropes"),
          Colour("GALVANISED", "Galvanised", _hex("#8E9194"), "wire_rope_galv", look="ROPE",
                 group="Wire ropes, galvanised")),
         ROPE_SIZES),
    # drag chains
    Kind("OPEN", "chain", 21, "Open chain", "Side links and a crossbar at the top and bottom of every link: the "
         "cables show", _PLASTIC, PLASTIC_CHAIN_SIZES, links="OPEN"),
    Kind("CLOSED", "chain", 22, "Closed chain", "Side links with lids at the top and bottom: a closed tube",
         _PLASTIC, PLASTIC_CHAIN_SIZES, links="CLOSED"),
    Kind("HALF", "chain", 23, "Half-open chain", "A lid on the outside of the bend, crossbars on the inside",
         _PLASTIC, PLASTIC_CHAIN_SIZES, links="HALF"),
    Kind("STEEL", "chain", 24, "Steel chain", "Heavy-duty steel side plates with round crossbar tubes",
         (_c("STEEL", "Steel", "#9A9EA2", "galvanized", text=""),), STEEL_CHAIN_SIZES, links="STEEL"),
)

BY_ID = {k.id: k for k in KINDS}
HOSE_ITEM_KINDS = ("HYDRAULIC", "BRAIDED", "PNEUMATIC", "SLEEVE", "MACHINE", "POWER")   # a hose item of flex.py
CABLE_ITEM_KINDS = ("MACHINE", "POWER", "OFFSHORE", "ROPE")                             # a cable of paths.py
CHAIN_ITEM_KINDS = ("OPEN", "CLOSED", "HALF", "STEEL")


def get(kind_id: str) -> Kind | None:
    return BY_ID.get(kind_id or "")


def kinds(family: str) -> list:
    return [k for k in KINDS if k.family == family]


def enum_items(ids, none_label: str, none_text: str) -> list:
    """(id, label, description, icon, number) for an EnumProperty; "NONE" (0) first = as before (the CAD look)."""
    out = [("NONE", none_label, none_text, "", 0)]
    out += [(k.id, k.label, k.description, "", k.number) for k in (BY_ID[i] for i in ids)]
    return out


def colour(kind_id: str, colour_id: str = "") -> Colour | None:
    """The colour of a kind by id; the kind's first colour when the id is not one of its own."""
    k = get(kind_id)
    if k is None:
        return None
    for c in k.colours:
        if c.id == colour_id:
            return c
    return k.colours[0]


def size(kind_id: str, size_id: str) -> Size | None:
    """The size of a kind by id; None for Custom or an id the kind does not have."""
    k = get(kind_id)
    if k is None or not size_id:
        return None
    return next((s for s in k.sizes if s.id == size_id), None)


def nearest_size(kind_id: str, od: float = 0.0, width: float = 0.0) -> Size | None:
    """The kind's standard size nearest a diameter (hoses, cables) or a chain's outer width (by ratio)."""
    k = get(kind_id)
    if k is None or not k.sizes:
        return None
    want = width if k.family == "chain" else od
    if not want or want <= 0.0:
        return k.sizes[len(k.sizes) // 2]
    import math
    key = (lambda s: abs(math.log(s.width / want))) if k.family == "chain" else (lambda s: abs(math.log(s.od / want)))
    return min(k.sizes, key=key)


def nearest_radius(sz: Size, radius: float, at_most: float = 0.0) -> float:
    """A chain size's bend radius nearest ``radius`` (its first when ``radius`` is 0). ``at_most`` > 0 (a chain
    whose brackets are that far from its bend's middle: half their gap): only radii up to it (+ 1 mm); when the size
    has none that small, ``radius`` stays – a bigger bend could not come back to the moving bracket."""
    if not sz.radii:
        return radius
    if not radius or radius <= 0.0:
        radius = sz.radii[0]
    radii = [r for r in sz.radii if not at_most or r <= at_most + 0.001]
    if not radii:
        return radius
    return min(radii, key=lambda r: abs(r - radius))


def group_name(kind_id: str, colour_id: str = "") -> str:
    """The material group a kind-and-colour puts its part in: one shared material per kind and colour."""
    k, c = get(kind_id), colour(kind_id, colour_id)
    if k is None or c is None:
        return ""
    return c.group or f"{k.label}, {c.label.lower()}"


def matches(sz: Size, family: str, od: float = 0.0, bend: float = 0.0, width: float = 0.0, height: float = 0.0,
            pitch: float = 0.0, tol: float = 1e-6) -> bool:
    """The numbers are still the size's (else the size reads as Custom)."""
    if family == "chain":
        return all(abs(a - b) <= tol for a, b in ((sz.width, width), (sz.height, height), (sz.pitch, pitch)))
    return abs(sz.od - od) <= tol and abs(sz.bend - bend) <= tol


# ---- the patterns drawn along a hose (blender/cable_looks.py kinds 4 … 6) ---------------------------------------
PATTERNS = {"HOSE": 4.0, "BRAID": 5.0, "SLEEVE": 6.0}


def pattern_look(kind_id: str, diameter: float) -> list | None:
    """The 4 numbers of ``fr_cable_look`` for a hose kind with a pattern: ``[pitch m, starts, width share, kind]``;
    None when the kind draws none.

    HOSE (the printed line): pitch = one print repeat along the hose (a block of "letters" and a gap), width = the
    share of a repeat that is print. BRAID: pitch = the braid's lay length (one full turn of a carrier), starts =
    carriers each way (more on a thicker hose). SLEEVE: pitch = from one turn of the spiral wrap to the next (about
    the hose's diameter), width = the share the wrap covers (the rest is the gap where the hose shows)."""
    k = get(kind_id)
    if k is None or not k.pattern:
        return None
    d = max(float(diameter), 0.001)
    if k.pattern == "HOSE":
        return [max(0.12, 8.0 * d), 0.0, 0.55, PATTERNS["HOSE"]]
    if k.pattern == "BRAID":
        carriers = 12 if d < 0.012 else 16 if d < 0.025 else 24
        return [3.2 * d, float(carriers), 0.5, PATTERNS["BRAID"]]
    return [0.9 * d, 1.0, 0.78, PATTERNS["SLEEVE"]]
