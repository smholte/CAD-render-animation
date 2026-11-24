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
    # task 0318
    "TWILL": (13, "2x2 twill", "The usual carbon look: each tow goes over two and under two, one tow on per row, so the "
                               "weave shows diagonal lines", dict(twill=1.0)),
    "PLAIN": (14, "Plain weave", "Each tow goes over one and under one: a calm chequer, no diagonal", dict(twill=0.0)),
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
    "carbon_fibre": dict(
        n=17, kind="carbon", faces=True, pat=dict(tow=0.002, roughness=0.3, anisotropic=0.75, gloss=1.0, twill=1.0),
        size=("Tow width", "tow", 0.002, 0.001, 0.008), amount=("Gloss", 1.0, "gloss"), kinds=("TWILL", "PLAIN"),
        web="average", far_rough=0.05, period=lambda p: p["tow"],
        what="carbon fibre: a 2x2 twill or plain weave under a clear coat (Gloss 1 = glossy, 0 = matte), each tow's "
             "highlight along its fibres; the weave follows every CAD face – round the round ones, draped over domes, "
             "on across folds – so it has no seam a real part would not have"),
    "perlage": dict(
        n=27, kind="perlage", faces=True, pat=dict(spacing=0.004, roughness=0.2, anisotropic=0.85),
        size=("Spot size", "spacing", 0.004, 0.0015, 0.012), bases=("STAINLESS", "ALUMINIUM", "BRASS"),
        web="average", far_rough=0.06, period=lambda p: p["spacing"],
        what="perlage (engine turning): overlapping brushed circles laid row after row, each later spot over the "
             "earlier ones, each with its own swirl of fine scratches and its own highlight"),
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

    def ok(v):
        return v is not None and isinstance(v, (int, float)) and not math.isnan(v)     # inf: held at a limit
    size, angle, amount = (v if ok(v) else None for v in (size, angle, amount))
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
    largest on that axis line) and k = 1 (outside) or -1 (inside: a bore, the normals point to the axis). A sphere
    (task 0318: a domed cap, a cup; its points all one distance from a centre on the axis, over more than
    ``SPHERE_SPAN``) gets k = 3 (outside) or -3 (inside), ``o`` = its centre, ``d`` = the axis towards the face's
    middle (its pole), ``r`` = the sphere's radius. Every other
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
    axes = np.asarray(axes, np.float64).ravel()
    axes = axes[:len(axes) // 7 * 7].reshape(-1, 7)            # a list of the wrong length: its whole entries
    axf = np.asarray(axis_faces, np.int64).ravel()
    axf = axf[:len(axf) // 3 * 3].reshape(-1, 3)
    bounds = [int(x) for x in starts] if len(starts) else [0]
    if bounds[-1] != P:
        bounds = [x for x in bounds if x < P] + [P]
    has_axis = np.zeros(P, bool)
    for t0, n, idx in axf:                                     # round faces: their own axis, their own radius
        t0, t1 = int(t0), int(min(t0 + n, P))
        if t0 < 0 or t1 <= t0 or not (0 <= idx < len(axes)):
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
        # the triangles' middles too: a cylinder has points only at its two ends, all one distance from its middle
        sph = _sphere(np.vstack([co[vid], cen[sl]]), oo, dd, _circumcentres(a[sl], b[sl], c[sl]),
                      nrm[sl]) if len(vid) >= 6 else None
        if sph is not None:                                    # task 0318: a sphere (a domed cap, a cup)
            c_s, R_s = sph
            dd_s = dd if float(((cen[sl] - c_s) @ dd) @ area[sl]) >= 0 else -dd     # the pole: the cap's middle
            out = float(np.sum(np.einsum("ij,ij->i", nrm[sl], cen[sl] - c_s) * area[sl])) >= 0
            o[sl], d[sl], r[sl], k[sl] = c_s, dd_s, R_s, (3.0 if out else -3.0)
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
            if np.linalg.norm(nm) < 0.5:                         # a closed face: its normals cancel out
                nm = np.array([0.0, 0.0, 1.0])
            o[sl], d[sl], k[sl] = cm, nm, 0.0
    return o, d, r, k


#: a round face is a sphere when its points lie within this share of the radius of one centre on its axis, and much
#: closer to that sphere than to any cone or cylinder round the axis (a straight line in the (z, rho) profile: a
#: chamfer or a short band of a cylinder fits a sphere too)
SPHERE_TOL = 0.02
SPHERE_VS_CONE = 0.25


def _circumcentres(a, b, c):
    """The centre of each triangle's circumscribed circle (a, b, c: (n, 3) corners)."""
    import numpy as np
    u, v = b - a, c - a
    w = np.cross(u, v)
    ww = np.maximum(np.einsum("ij,ij->i", w, w), 1e-30)
    num = np.einsum("i,ij->ij", np.einsum("ij,ij->i", u, u), np.cross(v, w)) + \
        np.einsum("i,ij->ij", np.einsum("ij,ij->i", v, v), np.cross(w, u))
    return a + num / (2.0 * ww[:, None])


def _sphere(pts, o, d, cen=None, nrm=None):
    """(centre, radius) of the sphere centred on the axis (o, d) that the points lie on, or None.

    |p - o|^2 = R^2 - t^2 + 2 t z with c = o + t d and z = (p - o).d: a least-squares line in z gives t. It is a
    sphere when the points' distances from c vary much less than their distances from the best straight profile line
    rho = a + b z (a cone; b = 0 a cylinder). With the triangles' circumcentres ``cen`` and normals ``nrm`` (the
    importer's meshes) the facets must also face the centre: the normal of a flat facet cut from a sphere, through its
    circumcentre, passes through the sphere's centre exactly; a cone's facets cross the axis all along it (independent
    review of task 0318: chamfers were read as spheres)."""
    import numpy as np
    pts = np.asarray(pts, float).reshape(-1, 3)
    if len(pts) < 4:
        return None
    pc = pts - o
    z = pc @ d
    q = np.einsum("ij,ij->i", pc, pc)
    if not np.all(np.isfinite(q)) or np.ptp(z) < 1e-12:
        return None
    A = np.vstack([np.ones_like(z), z]).T
    (_a0, a1), *_ = np.linalg.lstsq(A, q, rcond=None)
    t = a1 / 2.0
    c = o + d * t
    dist = np.linalg.norm(pts - c, axis=1)
    R = float(np.median(dist))
    rho = np.sqrt(np.maximum(q - z * z, 0.0))
    (b0, b1), *_ = np.linalg.lstsq(A, rho, rcond=None)
    line_dev = float(np.max(np.abs(rho - (b0 + b1 * z))))
    s_dev = float(np.max(np.abs(dist - R)))
    if not np.isfinite(R) or R <= 0 or s_dev > SPHERE_TOL * R or s_dev > SPHERE_VS_CONE * line_dev:
        return None
    if cen is not None and nrm is not None and len(cen):
        w0 = np.asarray(cen, float).reshape(-1, 3) - o
        n = np.asarray(nrm, float).reshape(-1, 3)
        bd = n @ d
        nn = np.einsum("ij,ij->i", n, n)
        ok = ((1.0 - bd * bd) > 1e-4) & (np.abs(nn - 1.0) < 1e-3) & np.all(np.isfinite(w0), axis=1)
        # (facets at the pole face along the axis: any point; slivers have no normal)
        if ok.any():
            tt = ((w0 @ d) - bd * np.einsum("ij,ij->i", n, w0))[ok] / (1.0 - bd[ok] ** 2)
            if float(np.max(np.abs(tt - t))) > max(0.05 * float(np.ptp(z)), 1e-9):
                return None
    return c, R


def teeth(radius: float, pitch: float, angle_deg: float = 0.0) -> int:
    """Whole teeth round a face of this radius (the knurl has no seam): round(2 pi r cos(angle) / pitch)."""
    v = 2 * math.pi * radius * math.cos(math.radians(angle_deg)) / max(pitch, 1e-12)
    return int(round(v)) if math.isfinite(v) else 0


# ---------------------------------------------------------------------------------------------------------------
# the weave's frame per face (task 0318: carbon fibre without a seam a real part would not have)
# ---------------------------------------------------------------------------------------------------------------

#: a face's own weave coordinates (metres), from its kind ``k`` of ``face_frames``:
#:   plane (k 0, 2):   (p.u, p.w) in the face's own plane – u, w from its normal ``d`` (``plane_basis``), measured
#:                     from the part's origin, so faces in one plane continue each other
#:   round (k +-1):    (theta r, z) round the face's axis – theta from ``theta0`` (the middle of the face's gap, so an
#:                     open bend has no jump); a closed ring gets a whole number of tows round it in the shader
#:   sphere (k +-3):   (s cos theta, s sin theta), s = r x the angle from the pole: a dome draped from its middle
#: then turned / mirrored and shifted (``weave_frames``) so that a face continues the weave of a neighbour it shares an
#: edge with (a fold of a sheet, a bend into a flat): the weave runs on across the edge as a draped ply would.
#: Closed rings and spheres keep their own frame (they are seamless on their own); where a face cannot continue its
#: neighbour (the end of a tube against its round side), the weave meets it as at a ply joint.
WEAVE_FIT = 2e-5          # m: a face continues its neighbour when their weaves meet within this along the edge
SMOOTH_EDGE = math.cos(math.radians(20.0))   # … and their normals along it differ by less than this angle


def plane_basis(d):
    """(u, w) of a face with normal / axis ``d`` – the same formula as the shader (``blender/finishes.F.cyl``)."""
    import numpy as np
    d = np.asarray(d, float)
    ref = np.array([1.0, 0.0, 0.0]) if abs(d[2]) > 0.9 else np.array([0.0, 0.0, 1.0])
    u = np.cross(d, ref)
    u /= max(np.linalg.norm(u), 1e-12)
    return u, np.cross(d, u)


def _theta(pc, d):
    """theta 0 … 2 pi round the axis d of points pc (relative to a point on it), as the shader works it out."""
    import numpy as np
    u, w = plane_basis(d)
    rad = pc - np.outer(pc @ d, d)
    return np.arctan2(rad @ w, rad @ u) + math.pi


def _native(kind: int, pts, o, d, r, theta0):
    """A face's own weave coordinates of ``pts`` (n, 3) -> (n, 2), metres."""
    import numpy as np
    if abs(kind) == 3:
        pc = pts - o
        z = pc @ d
        rho = np.linalg.norm(pc - np.outer(z, d), axis=1)
        s = r * np.arctan2(rho, z)
        th = _theta(pc, d)
        return np.stack([s * np.cos(th), s * np.sin(th)], 1)
    if abs(kind) == 1:
        pc = pts - o
        th = np.mod(_theta(pc, d) - max(theta0, 0.0), 2 * math.pi)
        return np.stack([th * r, pc @ d], 1)
    u, w = plane_basis(d)
    return np.stack([pts @ u, pts @ w], 1)


def _fit(b, g, det: float):
    """The turn (c, s) and shift that put the 2-D points ``b`` on ``g`` (``b`` mirrored first when det < 0), and the
    largest miss. None when the points do not fix it (fewer than two apart)."""
    import numpy as np
    if len(b) < 2:
        return None
    b = np.array(b, float)
    if det < 0:
        b[:, 1] = -b[:, 1]
    bc, gc = b.mean(0), g.mean(0)
    B, G = b - bc, g - gc
    if float(np.max(np.linalg.norm(B, axis=1))) < 1e-6:
        return None
    sxx = float(np.sum(B[:, 0] * G[:, 0] + B[:, 1] * G[:, 1]))
    sxy = float(np.sum(B[:, 0] * G[:, 1] - B[:, 1] * G[:, 0]))
    ang = math.atan2(sxy, sxx)
    c, s = math.cos(ang), math.sin(ang)
    Rb = np.stack([c * B[:, 0] - s * B[:, 1], s * B[:, 0] + c * B[:, 1]], 1)
    off = gc - np.array([c * bc[0] - s * bc[1], s * bc[0] + c * bc[1]])
    miss = float(np.max(np.linalg.norm(Rb - G, axis=1)))
    return c, s, off, miss


def weave_frames(co, tri, o, d, r, k, starts=()):
    """Per triangle (a (n, 3), b (n, 3)): a = (cos, sin, mirror) of the turn of the face's own weave coordinates, b =
    (shift u, shift v, theta0). The shader: (U, V) = R(turn) (Un, mirror Vn) + shift.

    ``o, d, r, k``: ``face_frames``; ``starts`` the CAD faces' first triangles. Faces are visited largest first; a face
    that shares an edge with one already placed continues its weave when the edge's points meet within ``WEAVE_FIT``
    (a fold, a bend, a face split in two) – turned, and mirrored when its own frame is the other way round."""
    import numpy as np
    co = np.asarray(co, np.float64).reshape(-1, 3)
    tri = np.asarray(tri, np.int64).reshape(-1, 3)
    P = len(tri)
    A = np.zeros((P, 3))
    A[:, 0] = 1.0
    A[:, 2] = 1.0
    Bv = np.zeros((P, 3))
    if P == 0 or len(co) == 0:
        return A, Bv
    bounds = [int(x) for x in starts] if len(starts) else [0]
    bounds = sorted({x for x in bounds if 0 <= x < P} | {0}) + [P]
    faces = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]
    o, d, r, k = (np.asarray(x, np.float64) for x in (o, d, r, k))
    tri = np.clip(tri, 0, len(co) - 1)
    a_, b_, c_ = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
    area = np.linalg.norm(np.cross(b_ - a_, c_ - a_), axis=1) / 2
    info = []
    key_faces: dict = {}
    scale = 1e6                                                   # points the same within a micrometre are one
    tn = np.cross(b_ - a_, c_ - a_)
    tn /= np.maximum(np.linalg.norm(tn, axis=1), 1e-30)[:, None]
    # round faces on one axis with one radius are one surface: a tube stored as two half faces is still closed
    rings: dict = {}
    for fi, (t0, t1) in enumerate(faces):
        if abs(int(round(float(k[t0])))) == 1:
            key = (tuple(np.round(o[t0], 6)), tuple(np.round(d[t0], 5)), round(float(r[t0]), 6))
            th = _theta(co[np.unique(tri[t0:t1].ravel())] - o[t0], d[t0])
            rings.setdefault(key, []).append(th)
    ring_closed = {}
    for key, ths in rings.items():
        th = np.sort(np.concatenate(ths))
        gaps = np.diff(np.concatenate([th, th[:1] + 2 * math.pi]))
        ring_closed[key] = len(th) > 0 and float(np.max(gaps)) < math.radians(30.0)
    for fi, (t0, t1) in enumerate(faces):
        vid = np.unique(tri[t0:t1].ravel())
        kind = int(round(float(k[t0])))
        oo, dd, rr = o[t0], d[t0], float(r[t0])
        th0, closed = 0.0, False
        if abs(kind) == 1 and len(vid):
            th = np.sort(_theta(co[vid] - oo, dd))
            gaps = np.diff(np.concatenate([th, th[:1] + 2 * math.pi]))
            g = int(np.argmax(gaps))
            closed = ring_closed.get((tuple(np.round(oo, 6)), tuple(np.round(dd, 5)), round(rr, 6)), False)
            th0 = -1.0 if closed else float(np.mod(th[g] + gaps[g] / 2, 2 * math.pi))   # -1: closed
        anchor = abs(kind) == 3 or closed
        hand = 1.0 if kind in (0, 2) else float(np.sign(kind) or 1.0)
        keys = np.round(co[vid] * scale).astype(np.int64)
        kv = {tuple(x): int(v) for x, v in zip(keys, vid)}
        # the face's normal at each of its points (the mean of its triangles there): only smooth edges are joined
        vn = np.zeros((len(co), 3))
        np.add.at(vn, tri[t0:t1].ravel(), np.repeat(tn[t0:t1], 3, axis=0))
        vnk = {kk: vn[v] / max(np.linalg.norm(vn[v]), 1e-30) for kk, v in kv.items()}
        for kk in kv:
            key_faces.setdefault(kk, []).append(fi)
        info.append(dict(t=(t0, t1), kind=kind, o=oo, d=dd, r=rr, th0=th0, anchor=anchor, hand=hand, keys=kv,
                         vn=vnk, area=float(area[t0:t1].sum())))
    nb: dict = {}
    for kk, fs in key_faces.items():
        if len(fs) > 1:
            for f1 in fs:
                for f2 in fs:
                    if f1 != f2:
                        nb.setdefault(f1, {}).setdefault(f2, []).append(kk)
    placed = [None] * len(info)                                   # (c, s, det, off)
    for root in sorted(range(len(info)), key=lambda i: -info[i]["area"]):
        if placed[root] is not None:
            continue
        placed[root] = (1.0, 0.0, 1.0, np.zeros(2))
        queue = [root]
        while queue:
            fa = queue.pop(0)
            ia = info[fa]
            ca, sa, da, offa = placed[fa]
            for fb, kks in sorted(nb.get(fa, {}).items()):
                ib = info[fb]
                if placed[fb] is not None or ib["anchor"] or len(kks) < 2:
                    continue
                # a smooth edge only (a bend into a flat, a face split in two): across a sharp edge – a sheet's cut
                # edge, a corner – a real layup has a ply joint (independent review: the folded panel's end faces)
                if min(float(ia["vn"][kk] @ ib["vn"][kk]) for kk in kks) < SMOOTH_EDGE:
                    continue
                pts = np.array([co[ia["keys"][kk]] for kk in kks])
                na = _native(ia["kind"], pts, ia["o"], ia["d"], ia["r"], ia["th0"])
                na[:, 1] *= da
                ga = np.stack([ca * na[:, 0] - sa * na[:, 1], sa * na[:, 0] + ca * na[:, 1]], 1) + offa
                nbp = _native(ib["kind"], pts, ib["o"], ib["d"], ib["r"], ib["th0"])
                det = da * ia["hand"] * ib["hand"]
                got = _fit(nbp, ga, det)
                if got is None or got[3] > WEAVE_FIT:
                    continue
                placed[fb] = (got[0], got[1], det, got[2])
                queue.append(fb)
    for fi, inf in enumerate(info):
        t0, t1 = inf["t"]
        c, s, det, off = placed[fi]
        A[t0:t1] = (c, s, det)
        Bv[t0:t1] = (off[0], off[1], inf["th0"])
    return A, Bv
