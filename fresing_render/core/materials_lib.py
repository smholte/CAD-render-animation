"""Material library: physically based definitions, independent of Blender.

Each entry describes a Principled BSDF set-up. The Blender side
(``blender/materials.py``) turns these into node trees. Colours are sRGB.

Entries with ``needs_color=True`` take their colour from the material group
(a RAL code or a hex value), e.g. paints and tinted plastics.
"""

from __future__ import annotations

CATEGORIES = ("Paint", "Metal", "Fastener finish", "Plastic & rubber", "Glass", "Light", "Other")

# Keys understood by the node builder:
#   base_color, metallic, roughness, coat, coat_roughness, transmission, ior,
#   emission, emission_strength, specular, anisotropic, needs_color,
#   variation: {scale, roughness_min, roughness_max, color_amount}
#   bump: {scale, strength}
MATERIALS: dict[str, dict] = {
    # ---- paints --------------------------------------------------------------
    "paint_gloss": dict(label="Paint, gloss", category="Paint", needs_color=True, roughness=0.16,
                        coat=0.5, coat_roughness=0.04, specular=0.5),
    "paint_satin": dict(label="Paint, satin", category="Paint", needs_color=True, roughness=0.36,
                        coat=0.15, coat_roughness=0.25, specular=0.5),
    "paint_matte": dict(label="Paint, matte", category="Paint", needs_color=True, roughness=0.62, specular=0.45),
    "powder_coat": dict(label="Powder coat (structure)", category="Paint", needs_color=True, roughness=0.48,
                        specular=0.5, bump=dict(scale=900.0, strength=0.06)),
    "paint_marine": dict(label="Marine paint system (epoxy/PU)", category="Paint", needs_color=True,
                         roughness=0.28, coat=0.3, coat_roughness=0.12,
                         variation=dict(scale=8.0, roughness_min=0.22, roughness_max=0.34, color_amount=0.03)),

    # ---- metals --------------------------------------------------------------
    "steel_machined": dict(label="Steel, machined", category="Metal", base_color=(0.63, 0.63, 0.64), metallic=1.0,
                           roughness=0.22),
    "steel_raw": dict(label="Steel, raw / mill scale", category="Metal", base_color=(0.30, 0.30, 0.31), metallic=0.85,
                      roughness=0.52, variation=dict(scale=12.0, roughness_min=0.4, roughness_max=0.65, color_amount=0.25)),
    "stainless_brushed": dict(label="Stainless, brushed", category="Metal", base_color=(0.72, 0.72, 0.73), metallic=1.0,
                              roughness=0.27, anisotropic=0.0),
    "stainless_polished": dict(label="Stainless, polished", category="Metal", base_color=(0.78, 0.78, 0.79),
                               metallic=1.0, roughness=0.06),
    "aluminium_machined": dict(label="Aluminium, machined", category="Metal", base_color=(0.91, 0.92, 0.93),
                               metallic=1.0, roughness=0.18),
    "aluminium_anodized": dict(label="Aluminium, anodized", category="Metal", base_color=(0.86, 0.87, 0.88),
                               metallic=1.0, roughness=0.34),
    "aluminium_anodized_color": dict(label="Aluminium, anodized colour", category="Metal", needs_color=True,
                                     metallic=1.0, roughness=0.32),
    "aluminium_profile": dict(label="Aluminium profile (matte anodized)", category="Metal",
                              base_color=(0.82, 0.83, 0.84), metallic=1.0, roughness=0.42),
    "cast_iron": dict(label="Cast iron", category="Metal", base_color=(0.26, 0.26, 0.27), metallic=0.6, roughness=0.72,
                      variation=dict(scale=40.0, roughness_min=0.6, roughness_max=0.85, color_amount=0.15)),
    "chrome": dict(label="Chrome", category="Metal", base_color=(0.95, 0.95, 0.96), metallic=1.0, roughness=0.03),
    "copper": dict(label="Copper", category="Metal", base_color=(0.955, 0.638, 0.538), metallic=1.0, roughness=0.25),
    "brass": dict(label="Brass", category="Metal", base_color=(0.91, 0.78, 0.42), metallic=1.0, roughness=0.24),
    "bronze": dict(label="Bronze", category="Metal", base_color=(0.80, 0.55, 0.35), metallic=1.0, roughness=0.32),

    # ---- fastener finishes ----------------------------------------------------
    "galvanized": dict(label="Hot-dip galvanized", category="Fastener finish", base_color=(0.60, 0.61, 0.62),
                       metallic=1.0, roughness=0.36,
                       variation=dict(scale=60.0, roughness_min=0.25, roughness_max=0.5, color_amount=0.12)),
    "zinc_plated": dict(label="Zinc plated", category="Fastener finish", base_color=(0.80, 0.81, 0.83), metallic=1.0,
                        roughness=0.22),
    "zinc_yellow": dict(label="Zinc plated, yellow", category="Fastener finish", base_color=(0.85, 0.74, 0.42),
                        metallic=1.0, roughness=0.24),
    "zinc_flake": dict(label="Zinc flake (Geomet/Delta)", category="Fastener finish", base_color=(0.55, 0.56, 0.57),
                       metallic=0.7, roughness=0.55),
    "black_oxide": dict(label="Black oxide", category="Fastener finish", base_color=(0.045, 0.045, 0.05),
                        metallic=0.9, roughness=0.36, coat=0.15, coat_roughness=0.3),

    # ---- plastic & rubber ------------------------------------------------------
    "rubber_black": dict(label="Rubber, black", category="Plastic & rubber", base_color=(0.02, 0.02, 0.02),
                         roughness=0.85, specular=0.3),
    "plastic_gloss": dict(label="Plastic, gloss", category="Plastic & rubber", needs_color=True, roughness=0.14),
    "plastic_matte": dict(label="Plastic, matte", category="Plastic & rubber", needs_color=True, roughness=0.5),
    "pom_white": dict(label="POM / PE, white", category="Plastic & rubber", base_color=(0.90, 0.90, 0.88),
                      roughness=0.38),
    "cable_black": dict(label="Cable / hose, black", category="Plastic & rubber", base_color=(0.025, 0.025, 0.025),
                        roughness=0.55),

    # ---- glass ---------------------------------------------------------------
    "glass_clear": dict(label="Glass, clear", category="Glass", base_color=(1.0, 1.0, 1.0), roughness=0.0,
                        transmission=1.0, ior=1.5),
    "polycarbonate_clear": dict(label="Polycarbonate, clear", category="Glass", base_color=(0.98, 0.98, 0.98),
                                roughness=0.02, transmission=1.0, ior=1.58),
    "glass_tinted": dict(label="Glass / PC, tinted", category="Glass", needs_color=True, roughness=0.02,
                         transmission=1.0, ior=1.55),
    "acrylic_frosted": dict(label="Acrylic, frosted", category="Glass", base_color=(0.95, 0.95, 0.95), roughness=0.35,
                            transmission=1.0, ior=1.49),

    # ---- light ---------------------------------------------------------------
    "emission_light": dict(label="Light / LED (glowing)", category="Light", needs_color=True, roughness=0.3,
                           emission=True, emission_strength=6.0),

    # ---- added for the part-type library (task 0008) ---------------------------
    "nickel_plated": dict(label="Nickel plated (brass fittings)", category="Metal", base_color=(0.80, 0.79, 0.76),
                          metallic=1.0, roughness=0.17),
    "aluminium_anodized_black": dict(label="Aluminium, black anodized", category="Metal",
                                     base_color=(0.035, 0.035, 0.04), metallic=1.0, roughness=0.36),
    "zinc_diecast": dict(label="Zinc die-cast", category="Metal", base_color=(0.70, 0.71, 0.72), metallic=1.0,
                         roughness=0.42),
    "belt_rubber": dict(label="Belt rubber (timing / flat belts)", category="Plastic & rubber",
                        base_color=(0.03, 0.03, 0.03), roughness=0.62, specular=0.35,
                        bump=dict(scale=400.0, strength=0.03)),
    "foam": dict(label="Foam", category="Plastic & rubber", base_color=(0.20, 0.20, 0.21), roughness=0.95,
                 specular=0.2, bump=dict(scale=300.0, strength=0.15)),
    "felt": dict(label="Felt", category="Plastic & rubber", base_color=(0.35, 0.35, 0.36), roughness=1.0,
                 specular=0.15, bump=dict(scale=800.0, strength=0.08)),
    "mannequin_matte": dict(label="Mannequin, matte", category="Plastic & rubber", base_color=(0.78, 0.74, 0.68),
                            roughness=0.55, specular=0.4),
    "wood": dict(label="Wood (pallets, plywood)", category="Other", base_color=(0.62, 0.46, 0.30), roughness=0.7,
                 variation=dict(scale=6.0, roughness_min=0.6, roughness_max=0.8, color_amount=0.2)),
    # a guard panel drawn as a plate: the material cuts the holes (25 mm mesh, 3 mm wire)
    "wire_mesh": dict(label="Wire mesh panel, powder coated (see-through)", category="Paint", needs_color=True,
                      roughness=0.48, specular=0.5, grid=dict(spacing=0.025, wire=0.003)),
}

# Fixed numbers stored in .blend files for each material. NEVER change or reuse a number;
# give new materials the next free number. (Blender saves enum choices as numbers.)
UIDS: dict[str, int] = {
    "paint_gloss": 1,
    "paint_satin": 2,
    "paint_matte": 3,
    "powder_coat": 4,
    "paint_marine": 5,
    "steel_machined": 6,
    "steel_raw": 7,
    "stainless_brushed": 8,
    "stainless_polished": 9,
    "aluminium_machined": 10,
    "aluminium_anodized": 11,
    "aluminium_anodized_color": 12,
    "aluminium_profile": 13,
    "cast_iron": 14,
    "chrome": 15,
    "copper": 16,
    "brass": 17,
    "bronze": 18,
    "galvanized": 19,
    "zinc_plated": 20,
    "zinc_yellow": 21,
    "zinc_flake": 22,
    "black_oxide": 23,
    "rubber_black": 24,
    "plastic_gloss": 25,
    "plastic_matte": 26,
    "pom_white": 27,
    "cable_black": 28,
    "glass_clear": 29,
    "polycarbonate_clear": 30,
    "glass_tinted": 31,
    "acrylic_frosted": 32,
    "emission_light": 33,
    "nickel_plated": 34,
    "aluminium_anodized_black": 35,
    "zinc_diecast": 36,
    "belt_rubber": 37,
    "foam": 38,
    "felt": 39,
    "mannequin_matte": 40,
    "wood": 41,
    "wire_mesh": 42,
}

DEFAULT_COLOR = "RAL 7035"


def get(material_id: str) -> dict:
    """Definition for an id (falls back to satin paint)."""
    return MATERIALS.get(material_id) or MATERIALS["paint_satin"]


def needs_color(material_id: str) -> bool:
    return bool(get(material_id).get("needs_color"))


def items_by_category():
    """[(category, [(id, label), ...]), ...] for menus."""
    out = []
    for cat in CATEGORIES:
        out.append((cat, [(k, v["label"]) for k, v in MATERIALS.items() if v["category"] == cat]))
    return out
