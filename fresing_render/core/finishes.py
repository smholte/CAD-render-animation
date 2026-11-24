"""The finishes of task 0274 (study 0270): knurls, spun and faced ends, honed bores, moulded textures, fabric, plate
patterns, blasted metal, paints and grains – no Blender here.

A finish is a ready-made material of ``core/materials_lib.py`` with a ``finish`` key; its nodes are built by
``blender/finishes.py``. This module holds what the two sides share and what the tests check without Blender:

* ``FINISHES`` – per finish: its pattern numbers, the settings a group shows (Size, Angle, Strength, Metal, Kind),
  the metal bases and kinds it offers, what the web 3D model keeps of it, its pattern's period (for the fade).
* ``key`` / ``parse`` – a group's settings as one short text, stored on the material (it is rebuilt when they change).
* ``pattern`` / ``base`` – the numbers the node builder gets.
* ``face_frames`` – the face data: for every triangle the CAD face's own axis (a point ``o``, a direction ``d``), the
  face's own radius ``r`` and its kind ``k`` (1 round outside, -1 bore, 2 end face on an axis, 0 other), from the
  importer's round-face axes. Every copy of a part shares its mesh, so every copy looks the same; a model update reads
  the same STEP faces and gets the same numbers.
* ``shown`` – how much of a pattern shows at a distance (the far-away fade): a pattern whose period covers fewer than
  ~2 pixels is drawn as its average, so it cannot shimmer.

Units: metres and radians inside (the settings' angles are degrees in ``key`` / ``parse``); colours sRGB."""

from __future__ import annotations

import math

#: radians per pixel of a 1920 px picture through a 50 mm lens on a 36 mm sensor (the app's default camera)
PIXEL_ANGLE = 36.0 / 50.0 / 1920.0
#: the scene property the camera code keeps up to date (``blender/cameras.update_pixel_angle``); the materials read it
#: with an Attribute node (View Layer: the view layer, then the scene)
PIXEL_PROP = "fr_pixel_angle"
#: the fade: 1 while a period covers at least FADE_HI pixels, 0 below FADE_LO
FADE_LO, FADE_HI = 1.5, 4.0
#: the web 3D model's tile (core/web3d.TILE): box-axis patterns are drawn at a period that divides it
TILE = 0.2

# ---------------------------------------------------------------------------------------------------------------
# metal bases and kinds (the numbers are stored in project files: never change or reuse one)
# ---------------------------------------------------------------------------------------------------------------

#: id: (number, label, sRGB colour, metallic, roughness added to the finish's own)
BASES: dict[str, tuple] = {
    "STEEL": (1, "Steel", (0.63, 0.63, 0.64), 1.0, 0.0),
    "STAINLESS": (2, "Stainless steel", (0.72, 0.72, 0.73), 1.0, -0.02),
    "ALUMINIUM": (3, "Aluminium", (0.91, 0.92, 0.93), 1.0, 0.0),
    "BRASS": (4, "Brass", (0.91, 0.78, 0.42), 1.0, -0.02),
    "GALVANIZED": (5, "Galvanized steel", (0.62, 0.63, 0.64), 1.0, 0.06),
    "TITANIUM": (6, "Titanium", (0.62, 0.59, 0.55), 1.0, 0.02),
    "CAST_IRON": (7, "Cast iron", (0.42, 0.42, 0.43), 1.0, 0.04),
}

#: id: (number, label, tooltip, pattern numbers it changes)
KINDS: dict[str, tuple] = {
    "FINE": (1, "Fine", "Fine glass beads: small, shallow dimples (about 0.07 mm)", dict(grain=14000.0, depth=0.00002)),
    "MEDIUM": (2, "Medium", "Medium glass beads (about 0.1 mm): the usual bead-blasted look",
               dict(grain=9000.0, depth=0.00003)),
    "COARSE": (3, "Coarse", "Coarse beads or sand (about 0.2 mm): a duller, grainier surface",
               dict(grain=5000.0, depth=0.00005, roughness_add=0.06)),
    "ROUND": (4, "Round holes", "Round holes on a 60° grid (as Rv 5-8: holes Ø 5 mm, 8 mm apart)", dict(slot=0.0)),
    "SLOTTED": (5, "Slotted holes", "Slots five times as long as they are wide, in staggered rows (as Lv 4x20)",
                dict(slot=5.0)),
    "VDI24": (6, "VDI 24", "VDI 3400 class 24 (Ra 1.6 µm): a fine satin texture", dict(roughness=0.38, grain=22000.0)),
    "VDI27": (7, "VDI 27", "VDI 3400 class 27 (Ra 2.2 µm)", dict(roughness=0.44, grain=18000.0)),
    "VDI30": (8, "VDI 30", "VDI 3400 class 30 (Ra 3.2 µm): the usual matte housing texture",
              dict(roughness=0.5, grain=14000.0)),
    "VDI33": (9, "VDI 33", "VDI 3400 class 33 (Ra 4.5 µm)", dict(roughness=0.57, grain=11000.0)),
    "VDI36": (10, "VDI 36", "VDI 3400 class 36 (Ra 6.3 µm): a coarse, dull texture",
              dict(roughness=0.64, grain=8000.0)),
    "CAST_AL": (11, "Aluminium", "Sand-cast aluminium: light grey, a fine sand grain and soft blotches",
                dict(color=(0.62, 0.62, 0.62), metallic=0.9, roughness=0.62)),
    "CAST_FE": (12, "Iron", "Sand-cast iron: dark grey, a little coarser and duller",
                dict(color=(0.30, 0.30, 0.31), metallic=0.75, roughness=0.72, grain=0.0008)),
}

STEELS = ("STEEL", "STAINLESS", "ALUMINIUM", "BRASS")

# ---------------------------------------------------------------------------------------------------------------
# the finishes
#   kind: the node builder (blender/finishes.BUILDERS)
#   n: the study's number (0270)
#   pat: the builder's numbers (metres)
#   size: (setting label, pattern key, default m, min m, max m) – the group's "Size" setting, or None
#   angle: (label, default degrees, min, max) or None;  amount: (label, default, pattern key) or None
#   bases / kinds: the choices of the group's "Metal" / "Kind" setting (first = default)
#   web: "average" (the web model gets the far-away numbers) or "tile" (baked as a 0.2 m tile)
#   period: the pattern's period in m (a function of the pattern numbers) – where it fades far away
#   far_rough: what the pattern adds to the roughness once it has faded (its average)
#   faces: True where it needs the face data (the CAD faces' own axes)
#   see_through: it cuts holes (Alpha)
# ---------------------------------------------------------------------------------------------------------------

FINISHES: dict[str, dict] = {
    "knurl_diamond": dict(
        n=1, kind="knurl", faces=True, pat=dict(pitch=0.0008, angle=30.0, diamond=True, roughness=0.28),
        size=("Pitch", "pitch", 0.0008, 0.0003, 0.003), angle=("Angle", 30.0, 15.0, 45.0), bases=STEELS,
        web="average", far_rough=0.14, period=lambda p: p["pitch"],
        what="two crossing grooves round the round faces (diamond pyramids, DIN 82 RGE), a whole number of teeth "
             "round each face; spun rings on the end faces"),
    "knurl_straight": dict(
        n=2, kind="knurl", faces=True, pat=dict(pitch=0.001, angle=0.0, diamond=False, roughness=0.26),
        size=("Pitch", "pitch", 0.001, 0.0003, 0.003), bases=STEELS, web="average", far_rough=0.14,
        period=lambda p: p["pitch"], what="straight grooves along the round faces (DIN 82 RAA); spun rings on the "
                                          "end faces"),
    "rubber_grip": dict(
        n=26, kind="knurl", faces=True,
        pat=dict(pitch=0.003, angle=45.0, diamond=True, roughness=0.7, spun_ends=False, flat_tops=1.6),
        size=("Pitch", "pitch", 0.003, 0.001, 0.008), web="average", far_rough=0.06, period=lambda p: p["pitch"],
        what="moulded flat-topped pyramids round a handle's round faces; flat faces stay plain"),
    "spun": dict(
        n=3, kind="spun", faces=True, pat=dict(ring_k=20000.0, anisotropic=0.8, roughness=0.18),
        amount=("Strength", 0.8, "anisotropic"), bases=("ALUMINIUM", "STAINLESS", "BRASS"), web="average",
        far_rough=0.0, period=lambda p: 8.0 / p["ring_k"],
        what="fine rings round the face's own centre: the radial highlight that moves round as the light moves"),
    "faced": dict(
        n=4, kind="faced", faces=True, pat=dict(feed=0.00025, anisotropic=0.6, roughness=0.22),
        size=("Feed", "feed", 0.00025, 0.00005, 0.002), bases=("STEEL", "ALUMINIUM", "BRASS"), web="average",
        far_rough=0.03, period=lambda p: p["feed"],
        what="the faced end of a turned part: one spiral groove per turn round the face's centre; turned rings on the "
             "round faces"),
    "honed": dict(
        n=24, kind="honed", faces=True, pat=dict(angle=50.0, k=2500.0, roughness=0.18),
        angle=("Angle", 50.0, 20.0, 80.0), bases=("STEEL", "CAST_IRON"), web="average", far_rough=0.08,
        period=lambda p: 4.0 / p["k"],
        what="two families of fine helical scratches inside bores (the honing cross-hatch), turned rings outside"),
    "crosshatch": dict(
        n=5, kind="crosshatch", pat=dict(pitch=0.0009, line=0.2, height=0.00012, roughness=0.42, angle=45.0),
        size=("Pitch", "pitch", 0.0009, 0.0003, 0.004), angle=("Angle", 45.0, 0.0, 90.0), web="tile",
        far_rough=0.06, period=lambda p: p["pitch"],
        what="a fine raised grid moulded into a plastic shell; it follows curved shells (a blend of three "
             "projections in the part's own axes)"),
    "fabric": dict(
        n=6, kind="fabric", pat=dict(pitch=0.0005, roughness=0.85),
        size=("Thread size", "pitch", 0.0005, 0.0002, 0.003), web="average", far_rough=0.0,
        far_color=0.7, period=lambda p: p["pitch"], what="a plain weave of threads with a fabric sheen"),
    "grille": dict(
        n=7, kind="grille", see_through=True, pat=dict(hole=0.0011, pitch=0.0016, roughness=0.45),
        size=("Hole size", "hole", 0.0011, 0.0004, 0.004), web="tile", far_rough=0.0,
        period=lambda p: p["pitch"], what="round holes on a 60° grid, see-through; far away its open share"),
    "soft_touch": dict(
        n=8, kind="soft_touch", pat=dict(grain=40000.0, roughness=0.62), web="average", far_rough=0.0,
        period=lambda p: 3.0 / p["grain"], what="no pattern: a soft sheen and a micro grain seen only up close"),
    "bead_blasted": dict(
        n=9, kind="blasted", pat=dict(grain=9000.0, depth=0.00003, roughness=0.46, color_var=0.05, rough_var=0.08),
        bases=("ALUMINIUM", "STAINLESS", "STEEL", "TITANIUM"), kinds=("MEDIUM", "FINE", "COARSE"), web="average",
        far_rough=0.0, period=lambda p: 2.0 / p["grain"], what="isotropic dimples of glass beads, a dull even sheen"),
    "shot_blasted": dict(
        n=10, kind="blasted",
        pat=dict(grain=3500.0, depth=0.00008, roughness=0.62, color_var=0.25, rough_var=0.12,
                 color=(0.42, 0.42, 0.43), metallic=0.9),
        web="average", far_rough=0.0, period=lambda p: 2.0 / p["grain"],
        what="steel after grit blasting to Sa 2½ (ready for paint): grey, dull, a coarse grain"),
    "hammertone": dict(
        n=11, kind="hammertone", pat=dict(cell=0.005, roughness=0.3, metallic=0.45),
        size=("Mark size", "cell", 0.005, 0.002, 0.015), web="tile", far_rough=0.0, period=lambda p: p["cell"],
        what="round hammer marks with metal flakes under a thin clear coat"),
    "wrinkle": dict(
        n=12, kind="wrinkle", pat=dict(size=0.001, roughness=0.55),
        size=("Wrinkle size", "size", 0.001, 0.0004, 0.004), web="tile", far_rough=-0.04,
        period=lambda p: 1.5 * p["size"], what="worm-like ridges of a wrinkle finish"),
    "antiskid": dict(
        n=13, kind="antiskid", pat=dict(grit=0.0012, roughness=0.78, cover=0.5),
        size=("Grit size", "grit", 0.0012, 0.0004, 0.004), web="tile", far_rough=0.08, period=lambda p: p["grit"],
        what="grit in the paint, about half the surface covered (walkways, decks)"),
    "tread": dict(
        n=14, kind="tread", pat=dict(pitch=0.025, roughness=0.34),
        size=("Pitch", "pitch", 0.025, 0.01, 0.05), bases=("ALUMINIUM", "GALVANIZED", "STEEL"), web="tile",
        far_rough=-0.03, period=lambda p: p["pitch"], tile=True,
        what="raised lenses on a square grid, each at 90° to its neighbours (relief, flat in silhouette)"),
    "perforated": dict(
        n=15, kind="perforated", see_through=True, pat=dict(hole=0.005, roughness=0.36, slot=0.0),
        size=("Hole size", "hole", 0.005, 0.0015, 0.03), bases=("GALVANIZED", "STAINLESS", "ALUMINIUM"),
        kinds=("ROUND", "SLOTTED"), web="tile", far_rough=0.0, period=lambda p: 1.6 * p["hole"], tile=True,
        what="round holes on a 60° grid or slots in staggered rows, see-through"),
    "expanded": dict(
        n=16, kind="expanded", see_through=True, pat=dict(lwd=0.043, roughness=0.42),
        size=("Opening length", "lwd", 0.043, 0.01, 0.1), bases=("GALVANIZED", "STEEL"), web="tile",
        far_rough=0.0, period=lambda p: 0.314 * p["lwd"], tile=True,
        what="diamond openings in a staggered grid, strands that lean, see-through"),
    "vdi": dict(
        n=18, kind="vdi", pat=dict(grain=14000.0, roughness=0.5), kinds=("VDI30", "VDI24", "VDI27", "VDI33", "VDI36"),
        web="average", far_rough=0.0, period=lambda p: 2.0 / p["grain"],
        what="the spark-eroded texture of a moulded housing; the class sets the crater size and the roughness"),
    "leather": dict(
        n=19, kind="leather", pat=dict(cell=0.0016, roughness=0.5),
        size=("Grain size", "cell", 0.0016, 0.0005, 0.005), web="tile", far_rough=0.05, period=lambda p: p["cell"],
        what="a moulded leather grain: creases between cells, fine pores"),
    "spangle": dict(
        n=20, kind="spangle", pat=dict(cell=0.009, rough_min=0.22, rough_max=0.5, roughness=0.35),
        size=("Crystal size", "cell", 0.009, 0.002, 0.03), web="tile", far_rough=0.0, period=lambda p: p["cell"],
        what="the large zinc crystals of hot-dip galvanizing, each with its own brightness and grain"),
    "as_cast": dict(
        n=22, kind="as_cast", pat=dict(grain=0.0006, wave=0.03, roughness=0.62),
        kinds=("CAST_AL", "CAST_FE"), web="tile", far_rough=0.0, period=lambda p: p["grain"],
        what="a sand-cast surface: sand grain, a soft waviness, darker blotches"),
    "scraped": dict(
        n=25, kind="scraped", pat=dict(cell=0.012, roughness=0.2),
        size=("Cell size", "cell", 0.012, 0.005, 0.03), bases=("STEEL", "CAST_IRON"), web="tile", far_rough=0.05,
        period=lambda p: p["cell"], tile=True,
        what="the half-moon flaking of scraped machine ways, every second cell turned 90°"),
}

SETTING_NAMES = ("size", "angle", "amount", "base", "kind")


def get(material_id: str) -> dict | None:
    """The finish of a library material, or None."""
    from . import materials_lib
    spec = materials_lib.MATERIALS.get(material_id)
    fid = spec.get("finish") if spec else None
    return FINISHES.get(fid) if fid else None


def finish_id(material_id: str) -> str:
    from . import materials_lib
    spec = materials_lib.MATERIALS.get(material_id)
    return (spec or {}).get("finish", "")


def needs_faces(material_id: str) -> bool:
    f = get(material_id)
    return bool(f and f.get("faces"))


def defaults(material_id: str) -> dict:
    """The settings a group starts with when it gets this material: {size m, angle deg, amount, base, kind}."""
    f = get(material_id) or {}
    return dict(size=float(f["size"][2]) if f.get("size") else 0.0,
                angle=float(f["angle"][1]) if f.get("angle") else 0.0,
                amount=float(f["amount"][1]) if f.get("amount") else 0.0,
                base=(f.get("bases") or ("",))[0], kind=(f.get("kinds") or ("",))[0])


def settings_of(material_id: str) -> list[str]:
    """The names of the settings this finish shows, in their order."""
    f = get(material_id) or {}
    return [n for n, k in (("base", "bases"), ("kind", "kinds"), ("size", "size"), ("angle", "angle"),
                           ("amount", "amount")) if f.get(k)]


def clean(material_id: str, size=None, angle=None, amount=None, base=None, kind=None) -> dict:
    """The settings, missing or impossible values replaced by the defaults, sizes kept inside their limits."""
    f = get(material_id)
    d = defaults(material_id)
    if f is None:
        return {}
    out = dict(d)
    if f.get("size") and size is not None and size > 0:
        out["size"] = min(max(float(size), f["size"][3]), f["size"][4])
    if f.get("angle") and angle is not None:
        out["angle"] = min(max(float(angle), f["angle"][2]), f["angle"][3])
    if f.get("amount") and amount is not None:
        out["amount"] = min(max(float(amount), 0.0), 1.0)
    if base in (f.get("bases") or ()):
        out["base"] = base
    if kind in (f.get("kinds") or ()):
        out["kind"] = kind
    return out


def key(material_id: str, size=None, angle=None, amount=None, base=None, kind=None) -> str:
    """One short text of the settings this finish uses ("" for any other material): stored on the material, which is
    rebuilt when it changes."""
    if get(material_id) is None:
        return ""
    c = clean(material_id, size, angle, amount, base, kind)
    used = settings_of(material_id)
    parts = []
    for n in SETTING_NAMES:
        if n not in used:
            continue
        v = c[n]
        if n == "size":
            parts.append(f"size={v * 1000:.4g}")         # mm
        elif n in ("angle", "amount"):
            parts.append(f"{n}={v:.4g}")
        else:
            parts.append(f"{n}={v}")
    return ";".join(parts) or "-"


def parse(material_id: str, text: str) -> dict:
    """The settings of a ``key`` text (size back in metres), cleaned."""
    got: dict = {}
    for part in (text or "").split(";"):
        if "=" not in part:
            continue
        n, v = part.split("=", 1)
        n = n.strip()
        if n == "size":
            try:
                got["size"] = float(v) / 1000.0
            except ValueError:
                pass
        elif n in ("angle", "amount"):
            try:
                got[n] = float(v)
            except ValueError:
                pass
        elif n in ("base", "kind"):
            got[n] = v.strip()
    return clean(material_id, **got)


def snap(period: float, tile: float = TILE) -> float:
    """The period nearest to ``period`` that divides the web model's tile (a box-axis pattern then repeats seamlessly
    in it and looks the same in the renders and on the web page)."""
    if period <= 0:
        return period
    return tile / max(1, round(tile / period))


def pattern(material_id: str, settings: dict | None = None) -> dict:
    """The numbers the node builder gets for this finish with these settings (metres, degrees)."""
    f = get(material_id)
    if f is None:
        return {}
    s = clean(material_id, **(settings or {}))
    p = dict(f["pat"])
    if f.get("size"):
        p[f["size"][1]] = s["size"]
    if f.get("angle"):
        p["angle"] = s["angle"]
    if f.get("amount"):
        p[f["amount"][2]] = s["amount"]
    if s.get("kind"):
        p.update(KINDS[s["kind"]][3])
    kind = f["kind"]
    if kind == "grille":
        p["pitch"] = p["hole"] * 1.6 / 1.1
    elif kind == "perforated":
        if p.get("slot"):
            p["slot"] = p["hole"] * 5.0                # a slot 5 x as long as wide (Lv 4x20)
            p["pitch"] = p["hole"] * 2.0               # web between rows and slot ends
        else:
            p["pitch"] = p["hole"] * 1.6               # Rv 5-8
    elif kind == "expanded":
        p["swd"] = p["lwd"] * 0.314
        p["strand"] = p["lwd"] * 0.051
    elif kind == "tread":
        p["pitch"] = snap(p["pitch"])
        p["length"], p["width"], p["height"] = 0.88 * p["pitch"], 0.24 * p["pitch"], 0.048 * p["pitch"]
    elif kind == "scraped":
        p["cell"] = snap(p["cell"])
    elif kind == "crosshatch":
        p["line"] = p["pitch"] * 0.2
    return p


def base(material_id: str, settings: dict | None = None) -> dict:
    """What the finish changes in the library material: base_color, metallic, roughness (sRGB colour)."""
    from . import materials_lib
    f = get(material_id)
    spec = materials_lib.MATERIALS.get(material_id) or {}
    if f is None:
        return {}
    s = clean(material_id, **(settings or {}))
    p = pattern(material_id, s)
    out = {"roughness": float(p.get("roughness", spec.get("roughness", 0.4)))}
    if "metallic" in p:
        out["metallic"] = float(p["metallic"])
    if "color" in p and not spec.get("needs_color"):
        out["base_color"] = tuple(p["color"])
    if s.get("base"):
        _n, _label, col, metal, radd = BASES[s["base"]]
        out["base_color"], out["metallic"] = tuple(col), float(metal)
        out["roughness"] = min(1.0, max(0.0, out["roughness"] + radd))
    out["roughness"] = min(1.0, max(0.0, out["roughness"] + float(p.get("roughness_add", 0.0))))
    return out


def period(material_id: str, settings: dict | None = None) -> float:
    f = get(material_id)
    return float(f["period"](pattern(material_id, settings))) if f else 0.0


def open_share(material_id: str, settings: dict | None = None) -> float:
    """The share of a see-through finish that is open (0 for the others)."""
    f = get(material_id)
    if f is None or not f.get("see_through"):
        return 0.0
    p = pattern(material_id, settings)
    if f["kind"] == "grille":
        rh = p["hole"] / 2
        return math.pi * rh * rh / (p["pitch"] ** 2 * math.sqrt(3) / 2)
    if f["kind"] == "perforated":
        rh = p["hole"] / 2
        if p.get("slot"):
            return (math.pi * rh * rh + (p["slot"] - 2 * rh) * 2 * rh) / ((p["slot"] + p["pitch"]) * p["pitch"])
        return math.pi * rh * rh / (p["pitch"] ** 2 * math.sqrt(3) / 2)
    if f["kind"] == "expanded":
        return (1.0 - 2.0 * p["strand"] / p["swd"]) ** 2
    return 0.0


def far(material_id: str, settings: dict | None = None) -> dict:
    """The finish as one set of numbers – what it fades to far away and what the web model gets for an "average"
    finish: {roughness, metallic, color (sRGB), alpha}."""
    from . import materials_lib
    f = get(material_id)
    if f is None:
        return {}
    spec = {**materials_lib.MATERIALS.get(material_id, {}), **base(material_id, settings)}
    col = tuple(spec.get("base_color", (0.8, 0.8, 0.8)))
    if f.get("far_color"):
        col = tuple(c * f["far_color"] for c in col)
    return dict(roughness=min(1.0, max(0.0, float(spec.get("roughness", 0.4)) + f.get("far_rough", 0.0))),
                metallic=float(spec.get("metallic", 0.0)), color=col, alpha=1.0 - open_share(material_id, settings))


def web_mode(material_id: str) -> str:
    """"average", "tile" or "" (not a finish)."""
    f = get(material_id)
    return f["web"] if f else ""


def shown(period_m: float, distance: float, pixel_angle: float = PIXEL_ANGLE) -> float:
    """How much of a pattern of this period shows at this distance from the camera (0 … 1): the same smooth step as
    the materials' far-away fade (``blender/finishes.F.lod``)."""
    px = float(period_m) / max(float(distance) * float(pixel_angle), 1e-12)
    t = min(max((px - FADE_LO) / (FADE_HI - FADE_LO), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def pixel_angle(width_px: int, lens_mm: float = 50.0, sensor_mm: float = 36.0) -> float:
    """Radians per pixel of a picture ``width_px`` wide through this lens (horizontal sensor fit)."""
    return float(sensor_mm) / max(float(lens_mm), 1e-6) / max(int(width_px), 1)


# ---------------------------------------------------------------------------------------------------------------
# face data
# ---------------------------------------------------------------------------------------------------------------

def face_frames(co, tri, axes=(), axis_faces=(), starts=(), part_centre=None, part_round=None):
    """Per triangle: (o (n, 3), d (n, 3), r (n,), k (n,)) – the CAD face's own axis, its own radius and its kind.

    ``co`` (v, 3) points, ``tri`` (n, 3) the triangles (the importer's meshes are triangles, one block of triangles
    per CAD face); ``axes`` the importer's ``fr_axes`` (7 numbers per axis: point, direction, radius);
    ``axis_faces`` its ``fr_axis_faces`` (start, count, axis per round face); ``starts`` its ``fr_face_starts`` (the
    first triangle of every CAD face, plus the end); ``part_centre`` / ``part_round`` the part's box centre and round
    axis (``materials.part_axes``) for faces with no axis of their own.

    Round faces keep their axis and get their own radius (the median distance of their points: the stored radius is the
    largest on that axis line) and k = 1 (outside) or -1 (inside: a bore, the normals point to the axis). Every other
    CAD face whose mean normal lies along an axis of the part and whose centre lies on it is an end face (k = 2,
    radius = its farthest point). The rest: k = 0, the face's own centre and normal."""
    import numpy as np
    co = np.asarray(co, np.float64).reshape(-1, 3)
    tri = np.asarray(tri, np.int64).reshape(-1, 3)
    P = len(tri)
    o = np.zeros((P, 3))
    d = np.zeros((P, 3))
    r = np.zeros(P)
    k = np.zeros(P)
    if P == 0:
        return o, d, r, k
    a, b, c = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    cen = (a + b + c) / 3
    cr = np.cross(b - a, c - a)
    ln = np.linalg.norm(cr, axis=1)
    area = ln / 2
    nrm = cr / np.maximum(ln, 1e-20)[:, None]
    axes = np.asarray(axes, np.float64).reshape(-1, 7)
    axf = np.asarray(axis_faces, np.int64).reshape(-1, 3)
    bounds = [int(x) for x in starts] if len(starts) else [0]
    if bounds[-1] != P:
        bounds = [x for x in bounds if x < P] + [P]
    has_axis = np.zeros(P, bool)
    for t0, n, idx in axf:                                     # round faces: their own axis, their own radius
        t0, t1 = int(t0), int(min(t0 + n, P))
        if t1 <= t0 or not (0 <= idx < len(axes)):
            continue
        sl = slice(t0, t1)
        ax = axes[idx]
        oo, dd = ax[:3], ax[3:6] / max(np.linalg.norm(ax[3:6]), 1e-12)
        vid = np.unique(tri[sl].ravel())
        pc = co[vid] - oo
        rad = pc - np.outer(pc @ dd, dd)
        rr = float(np.median(np.linalg.norm(rad, axis=1))) if len(vid) else 0.0
        pcf = cen[sl] - oo
        radf = pcf - np.outer(pcf @ dd, dd)
        inside = float(np.sum(np.einsum("ij,ij->i", nrm[sl], radf) * area[sl])) < 0
        o[sl], d[sl], r[sl], k[sl] = oo, dd, rr, (-1.0 if inside else 1.0)
        has_axis[sl] = True
    cand = [(ax[:3], ax[3:6] / max(np.linalg.norm(ax[3:6]), 1e-12)) for ax in axes]
    if part_centre is not None and part_round is not None:
        lo, hi = co.min(0), co.max(0)
        pr = np.asarray(part_round, float)
        across = (hi - lo)[pr < 0.5]                           # the two box sides square to the round axis
        if len(across) == 2 and across.min() / max(across.max(), 1e-12) > 0.9:
            cand.append((np.asarray(part_centre, float), pr / max(np.linalg.norm(pr), 1e-12)))
    for f in range(len(bounds) - 1):                           # every other CAD face: an end face on an axis?
        f0, f1 = bounds[f], min(bounds[f + 1], P)
        if f1 <= f0 or has_axis[f0:f1].any():
            continue
        sl = slice(f0, f1)
        w = area[sl]
        if w.sum() <= 0:
            o[sl], d[sl] = cen[sl], nrm[sl]
            continue
        nm = (nrm[sl] * w[:, None]).sum(0)
        nm /= max(np.linalg.norm(nm), 1e-12)
        cm = (cen[sl] * w[:, None]).sum(0) / w.sum()
        vid = np.unique(tri[sl].ravel())
        span = float(np.linalg.norm(np.ptp(co[vid], 0)))
        best = None
        for oo, dd in cand:
            if abs(float(nm @ dd)) < 0.9:
                continue
            pc = cm - oo
            off = float(np.linalg.norm(pc - dd * (pc @ dd)))
            if off < 0.15 * span + 1e-6 and (best is None or off < best[0]):
                best = (off, oo, dd)
        if best is not None:
            o[sl], d[sl], k[sl] = best[1], best[2] * (np.sign(float(nm @ best[2])) or 1.0), 2.0
            pc = co[vid] - best[1]
            r[sl] = float(np.max(np.linalg.norm(pc - np.outer(pc @ best[2], best[2]), axis=1)))
        else:
            o[sl], d[sl], k[sl] = cm, nm, 0.0
    return o, d, r, k


def teeth(radius: float, pitch: float, angle_deg: float = 0.0) -> int:
    """Whole teeth round a face of this radius (the knurl has no seam): round(2 pi r cos(angle) / pitch)."""
    return int(round(2 * math.pi * radius * math.cos(math.radians(angle_deg)) / max(pitch, 1e-12)))
