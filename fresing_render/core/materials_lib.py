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
#   sheen, sheen_roughness, variation: {scale, roughness_min, roughness_max, color_amount}
#   bump: {scale, strength}   a fine noise relief (scale = features per metre)
#   thin_film: {thickness, ior}   an oxide / passivation film (nm): colours that change with the angle (task 0318)
#   peel: {scale, strength}   orange peel of sprayed paint (also under the clear coat)
#   marks: {kind, scale, rough, bump, along}   machining marks without UV maps (task 0046), read from the
#       part's own axes (``blender/materials.part_axes``), so every copy of a part looks the same:
#       ground / brushed = straight lines along the part's longest side, turned = rings round its round axis,
#       milled = faint face-milling arcs. ``scale``: marks per metre across them (4000 = 0.25 mm);
#       ``along``: how much the lines vary along their length (per metre); ``rough``: how much the
#       roughness changes over the marks; ``bump``: their relief. ``anisotropic`` then follows the marks.
#   cable: {kind, pitch, starts, width, …}   a cable look whose pattern moves along the cable (task 0078):
#       kind "POWER" (black sheath, yellow stripes at an angle) or "ROPE" (steel wire rope: strands with their
#       lay). Drawn where the mesh has the ``fr_cable`` attribute, the plain material elsewhere; pitch (m), starts
#       and width are the look of a cable that gives none. ``blender/cable_looks.py`` has the nodes and every key.
#   finish: id of core/finishes.FINISHES   a finish of task 0274 (knurl, spun, cross-hatch, tread plate, blasted …):
#       its pattern, settings (Size, Angle, Strength, Metal, Kind) and web export are there, its nodes in
#       blender/finishes.py. A finish has no marks / variation / bump of its own.
#   marine: {kind, …}   weathering of steel at sea (task 0116), drawn over the paint by ``blender/marine_looks.py``:
#       kind "GROWTH" (marine growth below the waterline, a splash zone with slime and thin rust streaks above it;
#       the waterline is a WORLD height: the scene's ``fr_waterline_z``, 0 when it has none) "STREAKS" (light
#       run-down streaks of dirt and rust, vertical in the world) or "EROSION" (a wind turbine blade's worn
#       leading edge, task 0128). ``marine_looks.DEFAULTS`` has every key.
# Every look is clean by default (marketing stills); wear is a separate per-group slider.
MATERIALS: dict[str, dict] = {
    # ---- paints --------------------------------------------------------------
    "paint_gloss": dict(label="Paint, gloss", category="Paint", needs_color=True, roughness=0.16,
                        coat=0.5, coat_roughness=0.04, specular=0.5, peel=dict(scale=650.0, strength=0.05)),
    "paint_satin": dict(label="Paint, satin", category="Paint", needs_color=True, roughness=0.36,
                        coat=0.15, coat_roughness=0.25, specular=0.5, peel=dict(scale=650.0, strength=0.04)),
    "paint_matte": dict(label="Paint, matte", category="Paint", needs_color=True, roughness=0.62, specular=0.45),
    "powder_coat": dict(label="Powder coat (structure)", category="Paint", needs_color=True, roughness=0.48,
                        specular=0.5, bump=dict(scale=1100.0, strength=0.1),
                        variation=dict(scale=300.0, roughness_min=0.43, roughness_max=0.55, color_amount=0.0)),
    "paint_marine": dict(label="Marine paint system (epoxy/PU)", category="Paint", needs_color=True,
                         roughness=0.28, coat=0.3, coat_roughness=0.12, peel=dict(scale=450.0, strength=0.06),
                         variation=dict(scale=8.0, roughness_min=0.22, roughness_max=0.34, color_amount=0.03)),

    # ---- metals --------------------------------------------------------------
    "steel_machined": dict(label="Steel, machined", category="Metal", base_color=(0.63, 0.63, 0.64), metallic=1.0,
                           roughness=0.24, marks=dict(kind="milled", scale=1500.0, rough=0.035, bump=0.008)),
    "steel_raw": dict(label="Steel, raw / mill scale", category="Metal", base_color=(0.30, 0.30, 0.31), metallic=0.85,
                      roughness=0.52, variation=dict(scale=12.0, roughness_min=0.4, roughness_max=0.65, color_amount=0.25)),
    "stainless_brushed": dict(label="Stainless, brushed", category="Metal", base_color=(0.72, 0.72, 0.73), metallic=1.0,
                              roughness=0.3, anisotropic=0.65,
                              marks=dict(kind="brushed", scale=3500.0, along=25.0, rough=0.09, bump=0.02)),
    "stainless_polished": dict(label="Stainless, polished", category="Metal", base_color=(0.78, 0.78, 0.79),
                               metallic=1.0, roughness=0.06),
    "aluminium_machined": dict(label="Aluminium, machined", category="Metal", base_color=(0.91, 0.92, 0.93),
                               metallic=1.0, roughness=0.2,
                               marks=dict(kind="milled", scale=1200.0, rough=0.05, bump=0.008)),
    # anodising: a thin clear oxide on the metal, a soft satin sheen (a rough clear coat over satin metal)
    "aluminium_anodized": dict(label="Aluminium, anodized", category="Metal", base_color=(0.86, 0.87, 0.88),
                               metallic=1.0, roughness=0.38, coat=0.35, coat_roughness=0.3,
                               variation=dict(scale=2500.0, roughness_min=0.34, roughness_max=0.42, color_amount=0.0)),
    "aluminium_anodized_color": dict(label="Aluminium, anodized colour", category="Metal", needs_color=True,
                                     metallic=1.0, roughness=0.36, coat=0.35, coat_roughness=0.3,
                                     variation=dict(scale=2500.0, roughness_min=0.32, roughness_max=0.4,
                                                    color_amount=0.0)),
    "aluminium_profile": dict(label="Aluminium profile (matte anodized)", category="Metal",
                              base_color=(0.82, 0.83, 0.84), metallic=1.0, roughness=0.44, coat=0.25,
                              coat_roughness=0.45, anisotropic=0.2,
                              marks=dict(kind="brushed", scale=2500.0, along=4.0, rough=0.05, bump=0.006)),
    # task 0318: a casting is metal with a dull oxide skin, not half plastic: lighter, more metallic
    "cast_iron": dict(label="Cast iron", category="Metal", base_color=(0.31, 0.31, 0.32), metallic=0.75, roughness=0.72,
                      variation=dict(scale=25.0, roughness_min=0.62, roughness_max=0.88, color_amount=0.22),
                      bump=dict(scale=1500.0, strength=0.14)),
    # task 0318: chrome a darker, slightly blue mirror than polished stainless (its measured reflectance); copper, brass
    # and bronze had their measured linear reflectances written as sRGB (too dark, too orange): now between the
    # measurement and a little more colour (a studio has none of the warm reflections a workshop gives them)
    "chrome": dict(label="Chrome", category="Metal", base_color=(0.80, 0.81, 0.83), metallic=1.0, roughness=0.015),
    "copper": dict(label="Copper", category="Metal", base_color=(0.96, 0.74, 0.63), metallic=1.0, roughness=0.25),
    "brass": dict(label="Brass", category="Metal", base_color=(0.94, 0.84, 0.57), metallic=1.0, roughness=0.24),
    "bronze": dict(label="Bronze", category="Metal", base_color=(0.84, 0.66, 0.46), metallic=1.0, roughness=0.32),

    # ---- fastener finishes ----------------------------------------------------
    "galvanized": dict(label="Hot-dip galvanized", category="Fastener finish", base_color=(0.60, 0.61, 0.62),
                       metallic=1.0, roughness=0.38,
                       variation=dict(scale=70.0, roughness_min=0.24, roughness_max=0.55, color_amount=0.16),
                       bump=dict(scale=600.0, strength=0.04)),
    "zinc_plated": dict(label="Zinc plated", category="Fastener finish", base_color=(0.80, 0.81, 0.83), metallic=1.0,
                        roughness=0.22),
    # task 0318: yellow passivation is a thin film on bright zinc: gold-green with a rainbow sheen at an angle
    "zinc_yellow": dict(label="Zinc plated, yellow", category="Fastener finish", base_color=(0.86, 0.80, 0.56),
                        metallic=1.0, roughness=0.24, thin_film=dict(thickness=300.0, ior=1.55)),
    "zinc_flake": dict(label="Zinc flake (Geomet/Delta)", category="Fastener finish", base_color=(0.55, 0.56, 0.57),
                       metallic=0.7, roughness=0.55),
    "black_oxide": dict(label="Black oxide", category="Fastener finish", base_color=(0.045, 0.045, 0.05),
                        metallic=0.9, roughness=0.36, coat=0.15, coat_roughness=0.3),

    # ---- plastic & rubber ------------------------------------------------------
    # rubber is never pure black: a soft sheen at grazing angles, a little dust in the roughness
    "rubber_black": dict(label="Rubber, black", category="Plastic & rubber", base_color=(0.04, 0.04, 0.042),
                         roughness=0.72, specular=0.35, sheen=0.35, sheen_roughness=0.5,
                         variation=dict(scale=400.0, roughness_min=0.64, roughness_max=0.82, color_amount=0.08)),
    "plastic_gloss": dict(label="Plastic, gloss", category="Plastic & rubber", needs_color=True, roughness=0.08,
                          specular=0.55),
    "plastic_matte": dict(label="Plastic, matte", category="Plastic & rubber", needs_color=True, roughness=0.5,
                          bump=dict(scale=2500.0, strength=0.06)),
    "pom_white": dict(label="POM / PE, white", category="Plastic & rubber", base_color=(0.90, 0.90, 0.88),
                      roughness=0.38),
    "cable_black": dict(label="Cable / hose, black", category="Plastic & rubber", base_color=(0.035, 0.035, 0.037),
                        roughness=0.5, sheen=0.2, sheen_roughness=0.4),

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
                                     base_color=(0.035, 0.035, 0.04), metallic=1.0, roughness=0.4, coat=0.4,
                                     coat_roughness=0.3,
                                     variation=dict(scale=2500.0, roughness_min=0.36, roughness_max=0.44,
                                                    color_amount=0.0)),
    "zinc_diecast": dict(label="Zinc die-cast", category="Metal", base_color=(0.70, 0.71, 0.72), metallic=1.0,
                         roughness=0.42),
    "belt_rubber": dict(label="Belt rubber (timing / flat belts)", category="Plastic & rubber",
                        base_color=(0.035, 0.035, 0.037), roughness=0.62, specular=0.35, sheen=0.25,
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

    # ---- task 0046: machined surfaces, castings, hydraulics -------------------------
    "steel_ground": dict(label="Steel, ground (ways, shafts)", category="Metal", base_color=(0.66, 0.66, 0.67),
                         metallic=1.0, roughness=0.17, anisotropic=0.5,
                         marks=dict(kind="ground", scale=6000.0, along=8.0, rough=0.07, bump=0.012)),
    "steel_turned": dict(label="Steel, turned", category="Metal", base_color=(0.64, 0.64, 0.65), metallic=1.0,
                         roughness=0.21, anisotropic=0.6,
                         marks=dict(kind="turned", scale=4000.0, rough=0.08, bump=0.015)),
    "cast_iron_painted": dict(label="Cast iron, painted", category="Paint", needs_color=True, roughness=0.42,
                              coat=0.12, coat_roughness=0.3, specular=0.5, bump=dict(scale=180.0, strength=0.1),
                              variation=dict(scale=900.0, roughness_min=0.38, roughness_max=0.48, color_amount=0.0)),
    "chrome_rod": dict(label="Hydraulic chrome rod", category="Metal", base_color=(0.80, 0.81, 0.83), metallic=1.0,
                       roughness=0.045, anisotropic=0.3,
                       marks=dict(kind="ground", scale=9000.0, along=10.0, rough=0.02, bump=0.0)),

    # ---- task 0051: raw stock for milling (the block's outside; cut faces get a fresh-cut look) -------------
    # rolled plate cut to size: duller than machined, faint rolling lines along the plate's longest side
    "aluminium_sawn": dict(label="Aluminium, sawn plate", category="Metal", base_color=(0.80, 0.81, 0.82),
                           metallic=1.0, roughness=0.42, anisotropic=0.25,
                           variation=dict(scale=30.0, roughness_min=0.38, roughness_max=0.47, color_amount=0.05),
                           marks=dict(kind="brushed", scale=1800.0, along=3.0, rough=0.04, bump=0.004)),
    "pom_black": dict(label="POM, black", category="Plastic & rubber", base_color=(0.03, 0.03, 0.032),
                      roughness=0.36, specular=0.5),

    # ---- task 0078: cables whose pattern moves along them (blender/cable_looks.py) ---------------------------
    # the sheath as "cable_black"; the stripes RAL 1023 traffic yellow, 0.5 m apart, a quarter of the sheath
    "cable_power": dict(label="Power cable, black with yellow stripes", category="Plastic & rubber",
                        base_color=(0.035, 0.035, 0.037), roughness=0.5, sheen=0.2, sheen_roughness=0.4,
                        cable=dict(kind="POWER", pitch=0.5, starts=1, width=0.25)),
    # bright galvanised wires, 6 strands; pitch = the lay length (one full turn of a strand)
    "wire_rope": dict(label="Steel wire rope", category="Metal", base_color=(0.62, 0.63, 0.64), metallic=1.0,
                      roughness=0.4, cable=dict(kind="ROPE", pitch=0.16, starts=6, width=0.0)),
    # task 0158: a large export / array cable's outer serving: black polypropylene yarn served almost square to the
    # cable (fibres, a slight sheen along the strands, dust), pairs of yellow bands painted on it every 1.25 m
    "cable_served": dict(label="Served cable, black yarn with yellow marker spirals", category="Plastic & rubber",
                         base_color=(0.032, 0.032, 0.034), roughness=0.82, sheen=0.5, sheen_roughness=0.35,
                         cable=dict(kind="SERVED", pitch=1.0, starts=0, width=0.035)),

    # ---- task 0243: hose kinds (core/flex_kinds.py); patterns drawn along the hose by blender/cable_looks.py ----
    # hydraulic rubber hose: rubber of the given colour (black by default), a fine grain, a printed line along it
    "hose_hydraulic": dict(label="Hydraulic hose, rubber with a printed line", category="Plastic & rubber",
                           needs_color=True, roughness=0.7, specular=0.35, sheen=0.3, sheen_roughness=0.5,
                           variation=dict(scale=400.0, roughness_min=0.62, roughness_max=0.8, color_amount=0.06),
                           cable=dict(kind="HOSE")),
    # a woven stainless-steel braid (no geometry: colour and bump)
    "hose_braided": dict(label="Steel-braided hose", category="Metal", base_color=(0.72, 0.73, 0.74), metallic=1.0,
                         roughness=0.32, cable=dict(kind="BRAID")),
    # a spiral wrap of the given colour; the gaps show a black hose underneath
    "hose_sleeve": dict(label="Protective spiral sleeve", category="Plastic & rubber", needs_color=True,
                        roughness=0.45, specular=0.5, cable=dict(kind="SLEEVE")),
    # a clear polyurethane air tube: see-through, a slight blue-grey tint
    "pu_tube_clear": dict(label="Polyurethane tube, clear", category="Plastic & rubber",
                          base_color=(0.86, 0.9, 0.92), roughness=0.18, transmission=0.92, ior=1.5),
    # galvanised wire rope: duller and darker than the bright rope
    "wire_rope_galv": dict(label="Steel wire rope, galvanised", category="Metal", base_color=(0.5, 0.51, 0.52),
                           metallic=1.0, roughness=0.55, cable=dict(kind="ROPE", pitch=0.16, starts=6, width=0.0)),

    # ---- task 0116: offshore structures (wind turbine foundations, J-tubes, boat landings) --------------------
    # cast concrete: light warm grey, matte, a calm tone variation over metres, fine pores
    "concrete": dict(label="Concrete", category="Other", base_color=(0.60, 0.585, 0.55), roughness=0.86,
                     specular=0.4, bump=dict(scale=1800.0, strength=0.12),
                     variation=dict(scale=0.7, roughness_min=0.8, roughness_max=0.93, color_amount=0.1)),
    # a mesh model's own materials (task 0117): every part shows the material its file gave it (colour, texture,
    # roughness); a part without one gets this group's colour as satin paint
    "from_file": dict(label="From file (the model's own look)", category="Other", needs_color=True, roughness=0.4,
                      specular=0.5),
    # the marine paint system with what the sea does to it: growth below the waterline, a splash zone above
    "paint_marine_growth": dict(label="Marine paint, growth below the waterline", category="Paint",
                                needs_color=True, roughness=0.28, coat=0.3, coat_roughness=0.12,
                                peel=dict(scale=450.0, strength=0.06),
                                variation=dict(scale=8.0, roughness_min=0.22, roughness_max=0.34,
                                               color_amount=0.03),
                                marine=dict(kind="GROWTH")),
    "paint_marine_streaks": dict(label="Marine paint, run-down streaks", category="Paint", needs_color=True,
                                 roughness=0.28, coat=0.3, coat_roughness=0.12, peel=dict(scale=450.0, strength=0.06),
                                 variation=dict(scale=8.0, roughness_min=0.22, roughness_max=0.34,
                                                color_amount=0.03),
                                 marine=dict(kind="STREAKS")),
    # a wind turbine blade's paint with a worn leading edge (task 0128)
    "paint_blade_eroded": dict(label="Marine paint, worn leading edge (blades)", category="Paint", needs_color=True,
                               roughness=0.4, coat=0.1, coat_roughness=0.25,   # a blade's satin finish
                               peel=dict(scale=450.0, strength=0.06),
                               variation=dict(scale=8.0, roughness_min=0.22, roughness_max=0.34,
                                              color_amount=0.03),
                               marine=dict(kind="EROSION")),
    # ---- task 0274: finishes of study 0270 (blender/finishes.py builds them, core/finishes.py has their settings) --
    # face-axis finishes: the pattern follows each CAD face's own axis (knurls, spun / faced ends, honed bores)
    "knurl_diamond": dict(label="Knurled, diamond (knobs, handles)", category="Metal", base_color=(0.63, 0.63, 0.64),
                          metallic=1.0, roughness=0.28, finish="knurl_diamond"),
    "knurl_straight": dict(label="Knurled, straight", category="Metal", base_color=(0.63, 0.63, 0.64), metallic=1.0,
                           roughness=0.26, finish="knurl_straight"),
    "rubber_grip": dict(label="Rubber, moulded grip pattern", category="Plastic & rubber", needs_color=True,
                        roughness=0.7, specular=0.35, sheen=0.35, sheen_roughness=0.5, finish="rubber_grip"),
    "spun": dict(label="Spun metal (rings round the centre)", category="Metal", base_color=(0.91, 0.92, 0.93),
                 metallic=1.0, roughness=0.18, finish="spun"),
    "faced": dict(label="Faced end, spiral (turned parts)", category="Metal", base_color=(0.63, 0.63, 0.64),
                  metallic=1.0, roughness=0.22, finish="faced"),
    "honed": dict(label="Honed bore (cross-hatch)", category="Metal", base_color=(0.63, 0.63, 0.64), metallic=1.0,
                  roughness=0.18, finish="honed"),
    # box-axis finishes: a pattern in the part's own axes
    "crosshatch": dict(label="Plastic, moulded cross-hatch", category="Plastic & rubber", needs_color=True,
                       roughness=0.42, specular=0.5, finish="crosshatch"),
    "fabric": dict(label="Fabric, woven (speaker cloth)", category="Plastic & rubber", needs_color=True,
                   roughness=0.85, specular=0.3, sheen=0.8, sheen_roughness=0.35, finish="fabric"),
    "grille": dict(label="Plastic grille, fine holes (see-through)", category="Plastic & rubber", needs_color=True,
                   roughness=0.45, specular=0.5, finish="grille"),
    "tread": dict(label="Tread plate (lens pattern)", category="Metal", base_color=(0.91, 0.92, 0.93), metallic=1.0,
                  roughness=0.34, finish="tread"),
    "perforated": dict(label="Perforated sheet (see-through)", category="Metal", base_color=(0.62, 0.63, 0.64),
                       metallic=1.0, roughness=0.36, finish="perforated"),
    "expanded": dict(label="Expanded metal (see-through)", category="Metal", base_color=(0.62, 0.63, 0.64),
                     metallic=1.0, roughness=0.42, finish="expanded"),
    "scraped": dict(label="Scraped machine ways", category="Metal", base_color=(0.63, 0.63, 0.64), metallic=1.0,
                    roughness=0.2, finish="scraped"),
    # grain finishes: a 3-D grain in the part's own space
    "soft_touch": dict(label="Plastic, soft-touch", category="Plastic & rubber", needs_color=True, roughness=0.62,
                       specular=0.32, sheen=0.45, sheen_roughness=0.3, finish="soft_touch"),
    "bead_blasted": dict(label="Bead-blasted metal", category="Metal", base_color=(0.91, 0.92, 0.93), metallic=1.0,
                         roughness=0.46, finish="bead_blasted"),
    "shot_blasted": dict(label="Steel, shot-blasted (Sa 2½, before paint)", category="Metal",
                         base_color=(0.42, 0.42, 0.43), metallic=0.9, roughness=0.62, finish="shot_blasted"),
    "hammertone": dict(label="Paint, hammertone", category="Paint", needs_color=True, metallic=0.45, roughness=0.3,
                       coat=0.3, coat_roughness=0.15, finish="hammertone"),
    "wrinkle": dict(label="Paint, wrinkle finish", category="Paint", needs_color=True, roughness=0.55, specular=0.45,
                    finish="wrinkle"),
    "antiskid": dict(label="Paint, anti-skid (decks, walkways)", category="Paint", needs_color=True, roughness=0.78,
                     specular=0.4, finish="antiskid"),
    "vdi": dict(label="Plastic, spark-eroded texture (VDI 3400)", category="Plastic & rubber", needs_color=True,
                roughness=0.5, specular=0.45, finish="vdi"),
    "leather": dict(label="Plastic, leather grain", category="Plastic & rubber", needs_color=True, roughness=0.5,
                    specular=0.4, sheen=0.25, sheen_roughness=0.5, finish="leather"),
    "spangle": dict(label="Hot-dip galvanized, spangle", category="Fastener finish", base_color=(0.78, 0.79, 0.80),
                    metallic=1.0, roughness=0.35, finish="spangle"),
    "as_cast": dict(label="As-cast (sand-cast aluminium / iron)", category="Metal", base_color=(0.62, 0.62, 0.62),
                    metallic=0.9, roughness=0.62, finish="as_cast"),
    # ---- task 0318: carbon fibre (the weave follows each CAD face) and perlage --------------------------------------
    "carbon_fibre": dict(label="Carbon fibre (twill / plain weave)", category="Other", base_color=(0.022, 0.022, 0.025),
                         roughness=0.3, specular=0.6, coat=1.0, coat_roughness=0.03,
                         finish="carbon_fibre"),
    "perlage": dict(label="Perlage (engine-turned spots)", category="Metal", base_color=(0.72, 0.72, 0.73),
                    metallic=1.0, roughness=0.2, finish="perlage"),
    # ---- task 0273: a group whose look is a material made in Blender's own shader editor (an own material's
    # material.blend, appended into the project): blender/materials.own_blend_material copies it; this entry is only
    # its name in the Material drop-down and a plain grey stand-in when the appended material is missing
    "blender_material": dict(label="Own Blender material (pick it in Materials)", category="Other",
                             base_color=(0.6, 0.6, 0.6), roughness=0.5),
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
    "steel_ground": 43,
    "steel_turned": 44,
    "cast_iron_painted": 45,
    "chrome_rod": 46,
    "aluminium_sawn": 47,
    "pom_black": 48,
    "cable_power": 49,
    "wire_rope": 50,
    "concrete": 51,
    "paint_marine_growth": 52,
    "paint_marine_streaks": 53,
    "from_file": 54,
    "paint_blade_eroded": 55,
    "cable_served": 56,
    "hose_hydraulic": 57,
    "hose_braided": 58,
    "hose_sleeve": 59,
    "pu_tube_clear": 60,
    "wire_rope_galv": 61,
    "knurl_diamond": 62,
    "knurl_straight": 63,
    "rubber_grip": 64,
    "spun": 65,
    "faced": 66,
    "honed": 67,
    "crosshatch": 68,
    "fabric": 69,
    "grille": 70,
    "tread": 71,
    "perforated": 72,
    "expanded": 73,
    "scraped": 74,
    "soft_touch": 75,
    "bead_blasted": 76,
    "shot_blasted": 77,
    "hammertone": 78,
    "wrinkle": 79,
    "antiskid": 80,
    "vdi": 81,
    "leather": 82,
    "spangle": 83,
    "as_cast": 84,
    "carbon_fibre": 85,
    "perlage": 86,
    "blender_material": 87,
}

DEFAULT_COLOR = "RAL 7035"

#: task 0273: library materials the material picker does not list (they are chosen another way)
NOT_PICKED = ("blender_material",)

# The ready-made materials of before (the "Ready-made material…" menu, now entries of the material picker):
# id, label, library material, colour. Those with a colour are listed in the picker as entries of their own
# (key "preset:<id>"); those without are the library material itself.
PRESETS = [
    ("profile", "Aluminium profile", "aluminium_profile", ""),
    ("alu", "Aluminium, anodised", "aluminium_anodized", ""),
    ("alu_black", "Aluminium, black anodised", "aluminium_anodized_black", ""),
    ("alu_machined", "Aluminium, machined", "aluminium_machined", ""),
    ("stainless", "Stainless, brushed", "stainless_brushed", ""),
    ("steel", "Steel, machined", "steel_machined", ""),
    ("steel_ground", "Steel, ground (ways, shafts)", "steel_ground", ""),
    ("steel_turned", "Steel, turned", "steel_turned", ""),
    ("chrome", "Chrome", "chrome", ""),
    ("chrome_rod", "Hydraulic chrome rod (piston rods)", "chrome_rod", ""),
    ("galvanized", "Galvanised", "galvanized", ""),
    ("zinc", "Zinc plated", "zinc_plated", ""),
    ("black_oxide", "Black oxide", "black_oxide", ""),
    ("brass", "Brass", "brass", ""),
    ("copper", "Copper", "copper", ""),
    ("cast_iron", "Cast iron, as cast", "cast_iron", ""),
    ("cast_iron_painted", "Cast iron, painted RAL 7035", "cast_iron_painted", "RAL 7035"),
    ("rubber", "Rubber, black (seals, O-rings)", "rubber_black", ""),
    ("pom", "POM / PE, white", "pom_white", ""),
    ("plastic_black", "Plastic, black matte", "plastic_matte", "RAL 9005"),
    ("cable", "Cable / hose, black", "cable_black", ""),
    ("pc_clear", "Polycarbonate, clear (guards)", "polycarbonate_clear", ""),
    ("wire_mesh", "Wire mesh panel, black (see-through)", "wire_mesh", "RAL 9005"),
    ("glass_tinted", "Glass / PC, tinted grey", "glass_tinted", "RAL 7016"),
    ("paint_7035", "Paint RAL 7035 light grey", "paint_satin", "RAL 7035"),
    ("paint_7016", "Paint RAL 7016 anthracite", "paint_satin", "RAL 7016"),
    ("paint_9005", "Paint RAL 9005 black", "paint_satin", "RAL 9005"),
    ("paint_9010", "Paint RAL 9010 white", "paint_satin", "RAL 9010"),
    ("paint_5010", "Paint RAL 5010 blue", "paint_satin", "RAL 5010"),
    ("paint_3020", "Paint RAL 3020 red", "paint_satin", "RAL 3020"),
    ("paint_1003", "Paint RAL 1003 yellow", "paint_satin", "RAL 1003"),
    ("paint_6018", "Paint RAL 6018 green", "paint_satin", "RAL 6018"),
    ("led", "Light / LED (glowing)", "emission_light", "RAL 9010"),
    # task 0274: finishes (their own settings – pitch, metal, kind … – are under the material in the group box)
    ("knurl", "Knurled knob, diamond (steel)", "knurl_diamond", ""),
    ("spun", "Spun aluminium (caps, discs)", "spun", ""),
    ("tread", "Tread plate, aluminium", "tread", ""),
    ("perforated", "Perforated sheet, galvanised (see-through)", "perforated", ""),
    ("shot_blasted", "Steel, shot-blasted (before paint)", "shot_blasted", ""),
    ("hammertone", "Paint, hammertone RAL 7031 blue grey", "hammertone", "RAL 7031"),
    ("crosshatch", "Plastic housing, moulded cross-hatch, black", "crosshatch", "RAL 9005"),
    ("antiskid", "Deck paint, anti-skid RAL 7040 grey", "antiskid", "RAL 7040"),
    # task 0318
    ("carbon", "Carbon fibre, 2x2 twill, glossy", "carbon_fibre", ""),
    ("perlage", "Perlage, stainless (engine-turned spots)", "perlage", ""),
]


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


# ---- task 0318: where a group's Rust slider is logical ------------------------------------------------------------
#: bare carbon steel and cast iron: they rust all over
RUST_BARE = {"steel_machined", "steel_raw", "steel_ground", "steel_turned", "cast_iron", "black_oxide", "shot_blasted"}
#: zinc on steel: red rust only where the zinc is worn, white rust on the zinc
#: (``wire_rope``: its wires are bright galvanised, see its entry; ``wire_rope_galv`` the duller, heavier coat)
RUST_ZINC = {"galvanized", "zinc_plated", "zinc_yellow", "zinc_flake", "spangle", "wire_rope", "wire_rope_galv"}
#: a hard plating on steel: red rust only where it is worn
RUST_PLATED = {"chrome", "chrome_rod"}       # nickel_plated is on brass (fittings): no red rust
#: painted, but not on steel
PAINT_NOT_STEEL = {"paint_blade_eroded"}
#: a finish's metal base -> its rust kind
RUST_OF_BASE = {"STEEL": "BARE", "CAST_IRON": "BARE", "GALVANIZED": "ZINC"}
#: why a material never gets red rust (shown in the group instead of the slider)
NO_RUST_WHY = {"STAINLESS": "Stainless steel does not rust", "ALUMINIUM": "Aluminium does not rust (it only greys)",
               "BRASS": "Brass and bronze turn brown or green, not red", "TITANIUM": "Titanium does not rust",
               "COPPER": "Copper turns brown or green, not red", "NONMETAL": "Only steel and iron rust",
               "PLASTIC": "Plastic, rubber and glass do not rust", "FILE": "Uses the model's own look"}


def rust_kind(material_id: str, base: str = "", kind: str = "") -> str:
    """How a group of this material rusts: "BARE", "PAINTED", "ZINC", "PLATED" or "" (never: stainless, aluminium,
    brass, plastics …). ``base`` / ``kind``: a finish's Metal / Kind setting (a steel knurl rusts, a stainless one
    does not; sand-cast iron rusts, sand-cast aluminium does not)."""
    spec = MATERIALS.get(material_id)
    if spec is None:
        return ""
    if base:
        return RUST_OF_BASE.get(base, "")
    if material_id == "as_cast":
        return "BARE" if kind == "CAST_FE" else ""
    if material_id in RUST_BARE:
        return "BARE"
    if material_id in RUST_ZINC:
        return "ZINC"
    if material_id in RUST_PLATED:
        return "PLATED"
    if spec.get("category") == "Paint" and material_id not in PAINT_NOT_STEEL:
        return "PAINTED"
    return ""


def no_rust_why(material_id: str, base: str = "", kind: str = "") -> str:
    """Why a material has no Rust slider ("" when it has one)."""
    if rust_kind(material_id, base, kind):
        return ""
    if base in NO_RUST_WHY:
        return NO_RUST_WHY[base]
    if material_id == "from_file":
        return NO_RUST_WHY["FILE"]
    if material_id.startswith("stainless") or material_id == "hose_braided":
        return NO_RUST_WHY["STAINLESS"]
    if material_id.startswith("aluminium") or (material_id == "as_cast" and kind != "CAST_FE"):
        return NO_RUST_WHY["ALUMINIUM"]
    if material_id in ("brass", "bronze", "nickel_plated"):
        return NO_RUST_WHY["BRASS"]
    if material_id == "copper":
        return NO_RUST_WHY["COPPER"]
    if get(material_id).get("category") in ("Plastic & rubber", "Glass"):
        return NO_RUST_WHY["PLASTIC"]
    return NO_RUST_WHY["NONMETAL"]


# ---------------------------------------------------------------------------------------------------------------------
# Task 0273: tags and one-line descriptions for the Materials window (filters Material / Colour / Look).
# TAGS[id] = (kind, colour family, looks). "any" = the group's own colour is used (every ``needs_color`` material);
# clear glass and plastic count as "white" (nearly colourless), mill-scale / cast iron / concrete as "grey".
# ---------------------------------------------------------------------------------------------------------------------

KINDS = ("Paint", "Steel", "Stainless", "Aluminium", "Other metals", "Fastener finish", "Plastic", "Rubber",
         "Glass & clear", "Light", "Fabric", "Other")

COLOURS = ("any", "white", "grey", "black", "red", "orange", "yellow", "green", "blue", "purple", "brown", "metal")

COLOUR_LABELS = {
    "any": "Any colour (the group's)", "white": "White", "grey": "Grey", "black": "Black", "red": "Red",
    "orange": "Orange", "yellow": "Yellow", "green": "Green", "blue": "Blue", "purple": "Purple", "brown": "Brown",
    "metal": "Metal-coloured",
}

LOOKS = ("gloss", "satin", "matte", "brushed", "machined", "polished", "textured", "patterned", "see-through",
         "glowing", "weathered")

LOOK_LABELS = {
    "gloss": "Gloss", "satin": "Satin", "matte": "Matte", "brushed": "Brushed", "machined": "Machined / turned",
    "polished": "Polished", "textured": "Textured", "patterned": "Knurled / patterned", "see-through": "See-through",
    "glowing": "Glowing", "weathered": "Weathered",
}

TAGS: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "paint_gloss": ("Paint", "any", ("gloss",)),
    "paint_satin": ("Paint", "any", ("satin",)),
    "paint_matte": ("Paint", "any", ("matte",)),
    "powder_coat": ("Paint", "any", ("satin", "textured")),
    "paint_marine": ("Paint", "any", ("satin",)),
    "steel_machined": ("Steel", "metal", ("satin", "machined")),
    "steel_raw": ("Steel", "grey", ("matte", "weathered")),
    "stainless_brushed": ("Stainless", "metal", ("satin", "brushed")),
    "stainless_polished": ("Stainless", "metal", ("gloss", "polished")),
    "aluminium_machined": ("Aluminium", "metal", ("satin", "machined")),
    "aluminium_anodized": ("Aluminium", "metal", ("satin",)),
    "aluminium_anodized_color": ("Aluminium", "any", ("satin",)),
    "aluminium_profile": ("Aluminium", "metal", ("matte", "brushed")),
    "cast_iron": ("Steel", "grey", ("matte", "textured")),
    "chrome": ("Other metals", "metal", ("gloss", "polished")),
    "copper": ("Other metals", "metal", ("satin",)),
    "brass": ("Other metals", "metal", ("satin",)),
    "bronze": ("Other metals", "metal", ("satin",)),
    "galvanized": ("Fastener finish", "metal", ("satin", "textured")),
    "zinc_plated": ("Fastener finish", "metal", ("satin",)),
    "zinc_yellow": ("Fastener finish", "yellow", ("satin",)),
    "zinc_flake": ("Fastener finish", "grey", ("matte",)),
    "black_oxide": ("Fastener finish", "black", ("satin",)),
    "rubber_black": ("Rubber", "black", ("matte",)),
    "plastic_gloss": ("Plastic", "any", ("gloss",)),
    "plastic_matte": ("Plastic", "any", ("matte", "textured")),
    "pom_white": ("Plastic", "white", ("satin",)),
    "cable_black": ("Plastic", "black", ("matte",)),
    "glass_clear": ("Glass & clear", "white", ("gloss", "see-through")),
    "polycarbonate_clear": ("Glass & clear", "white", ("gloss", "see-through")),
    "glass_tinted": ("Glass & clear", "any", ("gloss", "see-through")),
    "acrylic_frosted": ("Glass & clear", "white", ("satin", "see-through")),
    "emission_light": ("Light", "any", ("glowing",)),
    "nickel_plated": ("Other metals", "metal", ("gloss", "polished")),
    "aluminium_anodized_black": ("Aluminium", "black", ("satin",)),
    "zinc_diecast": ("Other metals", "metal", ("satin",)),
    "belt_rubber": ("Rubber", "black", ("matte", "textured")),
    "foam": ("Rubber", "grey", ("matte", "textured")),
    "felt": ("Fabric", "grey", ("matte", "textured")),
    "mannequin_matte": ("Plastic", "white", ("matte",)),
    "wood": ("Other", "brown", ("matte", "textured")),
    "wire_mesh": ("Paint", "any", ("satin", "patterned", "see-through")),
    "steel_ground": ("Steel", "metal", ("gloss", "brushed")),
    "steel_turned": ("Steel", "metal", ("satin", "machined")),
    "cast_iron_painted": ("Paint", "any", ("satin", "textured")),
    "chrome_rod": ("Other metals", "metal", ("gloss", "polished")),
    "aluminium_sawn": ("Aluminium", "metal", ("matte", "brushed")),
    "pom_black": ("Plastic", "black", ("satin",)),
    "cable_power": ("Plastic", "black", ("matte", "patterned")),
    "wire_rope": ("Steel", "metal", ("satin", "patterned")),
    "cable_served": ("Plastic", "black", ("matte", "textured", "patterned")),
    "hose_hydraulic": ("Rubber", "any", ("matte", "patterned")),
    "hose_braided": ("Stainless", "metal", ("satin", "patterned")),
    "hose_sleeve": ("Plastic", "any", ("satin", "patterned")),
    "pu_tube_clear": ("Plastic", "white", ("gloss", "see-through")),
    "wire_rope_galv": ("Steel", "metal", ("matte", "patterned")),
    "concrete": ("Other", "grey", ("matte", "textured")),
    "from_file": ("Other", "any", ("satin",)),
    "paint_marine_growth": ("Paint", "any", ("satin", "weathered")),
    "paint_marine_streaks": ("Paint", "any", ("satin", "weathered")),
    "paint_blade_eroded": ("Paint", "any", ("satin", "weathered")),
    "knurl_diamond": ("Steel", "metal", ("satin", "machined", "patterned")),
    "knurl_straight": ("Steel", "metal", ("satin", "machined", "patterned")),
    "rubber_grip": ("Rubber", "any", ("matte", "patterned")),
    "spun": ("Aluminium", "metal", ("gloss", "machined", "patterned")),
    "faced": ("Steel", "metal", ("satin", "machined", "patterned")),
    "honed": ("Steel", "metal", ("gloss", "machined", "patterned")),
    "crosshatch": ("Plastic", "any", ("satin", "patterned")),
    "fabric": ("Fabric", "any", ("matte", "patterned")),
    "grille": ("Plastic", "any", ("satin", "patterned", "see-through")),
    "tread": ("Aluminium", "metal", ("satin", "patterned")),
    "perforated": ("Steel", "metal", ("satin", "patterned", "see-through")),
    "expanded": ("Steel", "metal", ("satin", "patterned", "see-through")),
    "scraped": ("Steel", "metal", ("gloss", "machined", "patterned")),
    "soft_touch": ("Plastic", "any", ("matte", "textured")),
    "bead_blasted": ("Aluminium", "metal", ("matte", "textured")),
    "shot_blasted": ("Steel", "grey", ("matte", "textured")),
    "hammertone": ("Paint", "any", ("satin", "textured")),
    "wrinkle": ("Paint", "any", ("matte", "textured")),
    "antiskid": ("Paint", "any", ("matte", "textured")),
    "vdi": ("Plastic", "any", ("matte", "textured")),
    "leather": ("Plastic", "any", ("satin", "textured")),
    "spangle": ("Fastener finish", "metal", ("satin", "textured")),
    "as_cast": ("Steel", "grey", ("matte", "textured")),
    "carbon_fibre": ("Other", "black", ("gloss", "patterned")),
    "perlage": ("Stainless", "metal", ("satin", "patterned")),
    "blender_material": ("Other", "any", ("matte",)),
}

DESCRIPTIONS: dict[str, str] = {
    "paint_gloss": "Smooth glossy paint in the group's colour: housings, covers, painted machine bodies",
    "paint_satin": "Semi-gloss paint in the group's colour: the usual look of painted machines and frames",
    "paint_matte": "Flat paint with almost no shine in the group's colour: dull covers, primer, military looks",
    "powder_coat": "Powder coating with a fine orange-peel structure: cabinets, guards, frames",
    "paint_marine": "Tough glossy epoxy / polyurethane paint system: ship hulls, decks, offshore steelwork",
    "steel_machined": "Bright milled steel with fine tool lines: machined blocks, plates, brackets",
    "steel_raw": "Dark steel with mill scale and a little rust-brown: raw plate, welded frames before painting",
    "stainless_brushed": "Stainless steel with long brushed lines: covers, kitchen and food machines, trim",
    "stainless_polished": "Mirror-like stainless steel: shafts, hygienic parts, decorative trim",
    "aluminium_machined": "Light, bright aluminium with milling lines: machined housings, plates, brackets",
    "aluminium_anodized": "Natural anodized aluminium, calm and slightly satin: covers, enclosures, profiles",
    "aluminium_anodized_color": "Anodized aluminium dyed in the group's colour: knobs, covers, design parts",
    "aluminium_profile": "Matte anodized aluminium extrusion with long brushed lines: frame profiles, rails",
    "cast_iron": "Dark grey cast iron with a fine sand texture: machine beds, gearbox housings",
    "chrome": "Mirror-bright chromium plating: trim, handles, decorative parts",
    "copper": "Warm reddish copper: busbars, pipes, electrical parts, heat exchangers",
    "brass": "Yellow brass with a soft shine: fittings, valves, bushings, nameplates",
    "bronze": "Darker golden bronze: bearings, bushings, gears, ship fittings",
    "galvanized": "Hot-dip zinc coating, dull grey and slightly uneven: steel frames, grating, outdoor steel",
    "zinc_plated": "Bright silver zinc plating: bolts, nuts, washers, small brackets",
    "zinc_yellow": "Yellow-gold zinc plating with a rainbow shimmer: bolts and nuts, pressed parts",
    "zinc_flake": "Matte dark-silver zinc flake coating: high-strength bolts, automotive and offshore fasteners",
    "black_oxide": "Dark black oxide on steel with a light oily sheen: screws, pins, tools",
    "rubber_black": "Black rubber, matte with a faint sheen: seals, bumpers, feet, mats",
    "plastic_gloss": "Smooth glossy plastic in the group's colour: housings, caps, covers",
    "plastic_matte": "Matte moulded plastic with a fine grain in the group's colour: enclosures, guards, knobs",
    "pom_white": "White engineering plastic (POM / PE), slightly waxy: sliders, gears, wear strips",
    "cable_black": "Black plastic jacket, slightly satin: power cables, signal cables, hoses",
    "glass_clear": "Clear window glass: windows, sight glasses, doors, covers",
    "polycarbonate_clear": "Clear, tough polycarbonate sheet: machine guards, safety windows, lenses",
    "glass_tinted": "Glass or polycarbonate tinted in the group's colour: coloured windows, smoked guards",
    "acrylic_frosted": "Frosted white acrylic that lets light through: light covers, diffusers, panels",
    "emission_light": "Glowing surface in the group's colour: LEDs, indicator lamps, signal lights, displays",
    "nickel_plated": "Bright pale nickel plating, slightly warmer than chrome: brass fittings, connectors",
    "aluminium_anodized_black": "Black anodized aluminium: camera and instrument housings, covers, dark trim",
    "zinc_diecast": "Grey die-cast zinc with a dull satin finish: small housings, handles, hardware",
    "belt_rubber": "Black rubber with a fine texture: timing belts, flat belts, conveyor belts",
    "foam": "Dark grey open foam, very matte and slightly rough: padding, insulation, filters",
    "felt": "Grey felt, completely matte and fibrous: wipers, pads, sound damping",
    "mannequin_matte": "Matte beige figure material: people and mannequins for scale",
    "wood": "Light brown wood with a soft grain: pallets, plywood, crates, workbenches",
    "wire_mesh": "Powder-coated wire grid with open gaps, in the group's colour: guard fences, safety panels",
    "steel_ground": "Bright ground steel with very fine long lines: machine ways, shafts, guide rails",
    "steel_turned": "Steel with fine circular lathe marks: turned shafts, pins, bushings",
    "cast_iron_painted": "Painted cast iron with a slightly rough surface: machine columns, pump housings, gearboxes",
    "chrome_rod": "Hydraulic piston rod, hard chrome with faint axial lines: cylinders, guide rods",
    "aluminium_sawn": "Aluminium plate with faint saw and brush lines: cut plate, base plates, fixtures",
    "pom_black": "Black engineering plastic (POM), slightly satin: gears, sliders, bushings",
    "cable_power": "Black power cable with yellow spiral stripes: motor and mains cables",
    "wire_rope": "Bright steel wire rope with visible strands: cranes, winches, lifting slings",
    "cable_served": "Black woven-yarn cable cover with yellow marker spirals: subsea and umbilical cables",
    "hose_hydraulic": "Rubber hose in the group's colour with a printed line: hydraulic and air lines",
    "hose_braided": "Hose covered in braided stainless steel wire: hydraulic lines, flexible connections",
    "hose_sleeve": "Plastic spiral protection sleeve in the group's colour: bundled cables and hoses",
    "pu_tube_clear": "Clear flexible polyurethane tube, slightly cloudy: pneumatic air lines",
    "wire_rope_galv": "Dull galvanized steel wire rope: stays, lashings, crane and mooring ropes",
    "concrete": "Pale grey concrete with a rough surface: floors, foundations, walls, quays",
    "from_file": "Keeps the colours and look the model brought along from its CAD file",
    "paint_marine_growth": "Marine paint with sea growth below the waterline: ship hulls and foundations in the water",
    "paint_marine_streaks": "Marine paint with rust run-down streaks above the waterline: hulls and towers at sea",
    "paint_blade_eroded": "Painted blade surface with a worn, eroded leading edge: wind turbine blades",
    "knurl_diamond": "Diamond-pattern knurled metal: knobs, handles, grip rings on turned parts",
    "knurl_straight": "Straight-ridged knurled metal: adjusting knobs, thumb screws, handles",
    "rubber_grip": "Moulded rubber grip pattern in the group's colour: handles, grips, hand wheels",
    "spun": "Bright metal with circular lines round the centre: spun covers, caps, round lids",
    "faced": "Turned end face with a spiral cutting pattern: ends of shafts, flanges, bushings",
    "honed": "Shiny bore with a fine cross-hatch: cylinder barrels, hydraulic tubes",
    "crosshatch": "Moulded plastic with a crossed-line pattern in the group's colour: housings, panels",
    "fabric": "Woven cloth in the group's colour: speaker covers, seats, curtains, filter cloth",
    "grille": "Plastic grille with fine holes in the group's colour: fan guards, speaker and vent grilles",
    "tread": "Aluminium tread plate with a raised lens pattern: floors, steps, walkways, truck beds",
    "perforated": "Metal sheet with round holes: guards, ventilation covers, filters, screens",
    "expanded": "Expanded metal mesh with diamond openings: guards, walkway grating, fences",
    "scraped": "Machine ways with flaked scraping marks: sliding surfaces of machine tools",
    "soft_touch": "Soft-touch coated plastic in the group's colour, velvety and matte: grips, device housings",
    "bead_blasted": "Fine matte sand-blasted metal: aluminium housings, instrument cases",
    "shot_blasted": "Grey shot-blasted steel, rough and dull: steel prepared for painting",
    "hammertone": "Hammered metallic paint in the group's colour: control boxes, old-style machine covers",
    "wrinkle": "Wrinkle-finish paint with a fine crinkled pattern: instrument and electronics housings",
    "antiskid": "Rough grit paint in the group's colour: decks, walkways, steps",
    "vdi": "Fine spark-eroded plastic texture in the group's colour: moulded housings, car interiors",
    "leather": "Plastic with a leather grain in the group's colour: seats, grips, dashboards",
    "spangle": "Hot-dip galvanized with a visible crystal pattern: sheet metal, ducts, outdoor frames",
    "as_cast": "Rough sand-cast metal surface, dull grey: untreated castings, pump and gearbox housings",
    "carbon_fibre": "Black woven carbon fibre under clear lacquer: light structures, covers, trim",
    "perlage": "Stainless steel with overlapping engine-turned spots: decorative plates, instrument faces",
    "blender_material": "A material you built yourself in Blender's shader editor",
}


def tags(material_id: str) -> tuple:
    """(kind, colour family, looks) of a material; a plain default for an unknown id."""
    return TAGS.get(material_id, ("Other", "any", ("matte",)))


def describe(material_id: str) -> str:
    """The material's one-line description (its label when it has none)."""
    text = DESCRIPTIONS.get(material_id)
    if text:
        return text
    return MATERIALS.get(material_id, {}).get("label", material_id)
