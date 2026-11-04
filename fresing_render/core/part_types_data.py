"""The part-type library: which part names mean which kind of part, and how that looks.

Data only; the matching is in ``part_types.py``. Everything here is plain Python so it
can carry comments and is packaged with the extension without extra files.

How to add a part type or a word
--------------------------------
* ``words``: keywords separated by ``|``. Matching is case-insensitive and word-aware:
  ``ROD`` matches "PISTON_ROD" and "ROD-12" but never "PRODUCT".
  - ``O RING``   several words in a row ("O-RING", "O.RING", "o ring")
  - ``*LAGER``   end of one word, for German/Dutch compounds ("KUGELLAGER")
  - ``DICHT*``   start of one word ("DICHTUNGSSATZ")
  Umlauts are spelled out (Ä -> AE), so write ``GEHAEUSE`` and, when names are often typed
  without the umlaut, also ``GEHAUSE``. Letters and digits are separate words ("PE500" is
  "PE 500"), so keywords hold letters only; use ``codes`` for anything with digits.
* ``codes``: regular expressions for vendor part numbers, searched in the upper-case name
  with its separators kept ("_MGPM32-75Z_ROD", "CDQ2B32-50DZ"). Start them with
  ``(?<![A-Z0-9])`` so they only match at the start of a code.
* ``level``:
  - ``product``   a bought component (cylinder, motor, sensor...). Parts *inside* a product
                  assembly with generic names (BODY, COVER, PLATE...) belong to the product.
  - ``component`` a specific part (seal, bearing, spring...): always itself.
  - ``shape``     a generic shape (plate, shaft, cover...): a material in the name ("RVS",
                  "POM") or a known CAD material decides instead; inside a product it becomes
                  part of the product.
* ``roles`` (products): a generic part type inside this product that becomes another type,
  e.g. a ROD inside a cylinder is the chrome piston rod.
* ``absorb`` (products): ``"all"`` makes every part inside the product part of it (a motor
  stays one colour); the default ``"shape"`` lets seals, sensors, fittings... keep their own.

When two keywords match, the one that ends further right wins ("SENSOR BRACKET" is a bracket,
"BRACKET SENSOR" a sensor: the last word of a name is usually the noun), then the longer one
("PROFILE CAP" beats "PROFILE").

Groups
------
``GROUPS``: group name -> (material without a CAD colour, its colour, material used with the
CAD colour or ""). With a material for the CAD colour, every CAD colour gets its own group
("Covers & panels #1F4E79"); "" means the group ignores CAD colours (metals, rubber, clear).
"""

from __future__ import annotations

R = r"(?<![A-Z0-9])"          # start of a code
E = r"(?![A-Z0-9])"           # end of a code

# --------------------------------------------------------------------------------------------
# Groups and how they look
# --------------------------------------------------------------------------------------------

GROUPS: dict[str, tuple[str, str, str]] = {
    # aluminium profile systems
    "Aluminium profiles": ("aluminium_profile", "", ""),
    "Profile caps & covers": ("plastic_matte", "RAL 9005", "plastic_matte"),
    "Profile connectors & brackets": ("zinc_diecast", "", ""),
    # generic shapes
    "Plates, blocks & brackets": ("aluminium_machined", "", "paint_satin"),
    "Shafts, pins & spacers": ("steel_machined", "", ""),
    "Chrome rods & linear shafts": ("chrome", "", ""),
    "Covers & panels": ("paint_satin", "RAL 7035", "paint_satin"),
    "Sheet metal parts": ("powder_coat", "RAL 7035", "powder_coat"),
    "Welded frames & structures": ("paint_satin", "RAL 7035", "paint_satin"),
    "Wear strips": ("pom_white", "", "plastic_matte"),
    # pneumatics and hydraulics
    "Pneumatic cylinders & grippers": ("aluminium_anodized", "", ""),
    "Linear actuators & rotary tables": ("aluminium_anodized", "", ""),
    "Hydraulic cylinders": ("paint_satin", "RAL 9005", "paint_satin"),
    "Gas springs & shock absorbers": ("black_oxide", "", ""),
    "Valves & valve terminals": ("plastic_matte", "RAL 7021", "plastic_matte"),
    "Ball valves & taps": ("nickel_plated", "", ""),
    "Hydraulic components": ("paint_satin", "RAL 9005", "paint_satin"),
    "Fittings": ("nickel_plated", "", ""),
    "Hoses & tubing": ("cable_black", "", "plastic_matte"),
    "Pipes": ("stainless_brushed", "", "paint_satin"),
    "Pipe & hose clamps": ("zinc_plated", "", ""),
    "Vacuum cups": ("rubber_black", "", ""),
    # motion
    "Linear guides & ball screws": ("steel_machined", "", ""),
    "Bearings": ("steel_machined", "", ""),
    "Bearing housings & units": ("cast_iron", "", "paint_satin"),
    "Bushings & plain bearings": ("bronze", "", ""),
    "Plastic plain bearings": ("plastic_matte", "RAL 7016", "plastic_matte"),
    "Couplings & brakes": ("steel_machined", "", ""),
    "Gears & sprockets": ("steel_machined", "", ""),
    "Pulleys": ("aluminium_machined", "", ""),
    "Chains": ("steel_raw", "", ""),
    "Belts": ("belt_rubber", "", "plastic_matte"),
    "Springs": ("steel_machined", "", ""),
    "Rod ends & clevises": ("zinc_plated", "", ""),
    "Conveyor rollers": ("zinc_plated", "", ""),
    # rubber
    "Seals & O-rings": ("rubber_black", "", ""),
    "Rubber parts": ("rubber_black", "", ""),
    # electrical
    "Cables": ("cable_black", "", "plastic_matte"),
    "Cable chains": ("plastic_matte", "RAL 9005", "plastic_matte"),
    "Cable glands": ("plastic_matte", "RAL 7001", "plastic_matte"),
    "Wiring ducts": ("plastic_matte", "RAL 7030", "plastic_matte"),
    "Cable trays & DIN rails": ("galvanized", "", ""),
    "Sensors & switches": ("plastic_matte", "RAL 7021", "plastic_matte"),
    "Motors & gearboxes": ("paint_satin", "RAL 7016", "paint_satin"),
    "Electrical enclosures": ("powder_coat", "RAL 7035", "powder_coat"),
    "Electrical components": ("plastic_matte", "RAL 7035", "plastic_matte"),
    "Push buttons & selectors": ("plastic_gloss", "RAL 9005", "plastic_gloss"),
    "Emergency stops": ("plastic_gloss", "RAL 3020", "plastic_gloss"),
    "Signal towers & lamps": ("plastic_gloss", "RAL 9003", "plastic_gloss"),
    "Robots": ("paint_satin", "RAL 9016", "paint_satin"),
    # operator parts and machine furniture
    "Handles & knobs": ("plastic_matte", "RAL 9005", "plastic_matte"),
    "Levelling feet": ("zinc_plated", "", ""),
    "Casters & wheels": ("rubber_black", "", "plastic_matte"),
    "Hinges & latches": ("zinc_diecast", "", ""),
    "Windows & clear parts": ("polycarbonate_clear", "", ""),
    "Wire mesh & fences": ("wire_mesh", "RAL 9005", "wire_mesh"),
    "Gratings, stairs & railings": ("galvanized", "", "paint_satin"),
    "Labels & signs": ("plastic_gloss", "RAL 9016", "plastic_gloss"),
    "Mannequins": ("mannequin_matte", "", ""),
    "Tool holders & tools": ("steel_machined", "", ""),
    # offshore / lifting
    "Lifting gear & wire ropes": ("galvanized", "", ""),
    "Winch drums & sheaves": ("paint_marine", "RAL 7035", "paint_marine"),
    # materials named in the part name (see MATERIAL_GROUPS)
    "Stainless steel parts": ("stainless_brushed", "", ""),
    "Aluminium parts": ("aluminium_machined", "", ""),
    "Anodised aluminium parts": ("aluminium_anodized", "", ""),
    "Black anodised parts": ("aluminium_anodized_black", "", ""),
    "Brass parts": ("brass", "", ""),
    "Bronze parts": ("bronze", "", ""),
    "Copper parts": ("copper", "", ""),
    "Chrome parts": ("chrome", "", ""),
    "Galvanized parts": ("galvanized", "", ""),
    "Zinc plated parts": ("zinc_plated", "", ""),
    "Steel parts": ("steel_machined", "", "paint_satin"),
    "Cast iron parts": ("cast_iron", "", "paint_satin"),
    "POM parts": ("pom_white", "", "plastic_matte"),
    "PE parts": ("pom_white", "", "plastic_matte"),
    "PA parts": ("plastic_matte", "#E8E0CC", "plastic_matte"),
    "PEEK parts": ("plastic_matte", "#C8B48C", "plastic_matte"),
    "PTFE parts": ("plastic_matte", "#F2F2EF", "plastic_matte"),
    "PVC parts": ("plastic_matte", "RAL 7011", "plastic_matte"),
    "PP parts": ("plastic_matte", "RAL 7035", "plastic_matte"),
    "Plastic parts": ("plastic_matte", "RAL 9005", "plastic_matte"),
    "Glass parts": ("glass_clear", "", ""),
    "Foam parts": ("foam", "", ""),
    "Felt parts": ("felt", "", ""),
    "Wood parts": ("wood", "", ""),
}


def T(id, group, level, words="", codes=(), roles=None, absorb="shape"):
    return dict(id=id, group=group, level=level, words=words, codes=tuple(codes), roles=roles or {},
                absorb=absorb)


# --------------------------------------------------------------------------------------------
# Part types
# --------------------------------------------------------------------------------------------

TYPES = [
    # ---- aluminium profile systems -------------------------------------------------------------
    T("alu_profile", "Aluminium profiles", "component",
      "PROFILE|PROFIEL|PROFIL|*PROFIEL|*PROFIL|ALU PROFILE|ALUMINIUM PROFILE|ALUMINUM PROFILE|EXTRUSION|"
      "STRUT PROFILE|SLOT PROFILE|SYSTEM PROFILE|CONSTRUCTION PROFILE|ITEM PROFILE|BOSCH PROFILE|"
      "BOSCHPROFIEL|ITEMPROFIEL|NUTPROFIL|SYSTEMPROFIL|STRANGPRESSPROFIL|FRAMING|T SLOT|TSLOT",
      codes=[R + r"0\.0\.\d{3}\.\d{2}" + E,                        # item  0.0.026.23
             R + r"3842\s?\d{3}\s?\d{3}" + E,                       # Bosch Rexroth 3842 990 720
             R + r"K?[HNG]FS[A-Z]{0,2}\d{1,2}-\d{4}",               # Misumi HFS5-2020-500, KHFS5-2040-…
             ]),
    T("profile_cap", "Profile caps & covers", "shape",
      "END CAP|ENDCAP|PROFILE CAP|ABDECKKAPPE|EINDKAP|AFDEKKAP|EINDDOP|AFDEKDOP|COVER CAP|SLOT COVER|"
      "COVER STRIP|COVER PROFILE|NUTABDECKUNG|NUTABDECKPROFIL|AFDEKPROFIEL|ABDECKPROFIL|AFDEKSTRIP|"
      "ABDECKLEISTE|CLIP STRIP|END COVER|PROFIELDOP|CAP PROFILE|END CAP PROFILE|AFDEKKAP PROFIEL|"
      "EINDKAP PROFIEL|ABDECKKAPPE PROFIL",
      codes=[R + r"(?:HFC|HFCL|GFC)\d-\d{4}", R + r"HFC\d{2}[A-Z]\d" + E]),                       # Misumi HFC5-2020, HFC30A5
    T("profile_connector", "Profile connectors & brackets", "component",
      "ANGLE BRACKET|CORNER BRACKET|HOEKVERBINDER|HOEKBEUGEL|HOEKSTEUN|WINKEL|*WINKEL|NUTENWINKEL|"
      "PROFILE CONNECTOR|PROFIELVERBINDER|PROFILVERBINDER|NUTVERBINDER|CENTRAL CONNECTOR|AUTOMATIC FASTENER|"
      "STANDARD FASTENER|ANGLE FASTENER|UNIVERSAL FASTENER|CORNER CUBE|CUBE CONNECTOR|GUSSET|KNOTENBLECH|"
      "CONNECTION SET|VERBINDUNGSSATZ|WINKELSATZ|BUTT FASTENER|STOOTVERBINDER|T CONNECTOR|L CONNECTOR",
      codes=[R + r"HBL[A-Z]{1,5}\d",
             R + r"HNT[A-Z]{1,4}\d{1,2}(?:-\d{1,2})?" + E,                  # Misumi slot nuts HNTT5-5, PACK-HNTA6-6
             ]),

    # ---- generic shapes ----------------------------------------------------------------------------
    T("plate", "Plates, blocks & brackets", "shape",
      "PLATE|PLAAT|PLATTE|*PLATTE|*PLAAT|BASEPLATE|BASE PLATE|GRONDPLAAT|GRUNDPLATTE|MOUNTING PLATE|"
      "MONTAGEPLAAT|MONTAGEPLATTE|ADAPTER PLATE|ADAPTERPLATTE|TOP PLATE|SIDE PLATE|END PLATE|CLAMP PLATE|"
      "BLOCK|BLOK|*BLOCK|*BLOK|BRACKET|BRACKETS|BRKT|BRAKCET|BRACKED|BRACKT|BEUGEL|*BEUGEL|HOLDER|HOUDER|*HOUDER|HALTER|*HALTER|"
      "HALTERUNG|*HALTERUNG|CONSOLE|KONSOLE|STEUN|*STEUN|SUPPORT|SUPPORTS|LUG|CLEAT|MOUNT|MOUNTING|"
      "FLANGE|FLENS|FLANSCH|*FLANSCH|*FLENS|HOUSING|BEHUIZING|GEHAEUSE|GEHAUSE|*GEHAEUSE|*GEHAUSE|"
      "SHIM|VULPLAAT|PASSBLECH|SPACER PLATE|CLAMP|KLEM|KLEMSTUK|KLEMMSTUECK|KLEMMSTUCK|CLAMPING BLOCK|"
      "STOP|STOPPER|AANSLAG|*AANSLAG|ANSCHLAG|*ANSCHLAG|LEVER|HEBEL|*HEBEL|HENDEL|ARM|"
      "FLAT BAR|STRIP|FLACHSTAB|LASCHE|*LASCHE|STRIP PLATE|GUIDE|GELEIDER|GELEIDING|FUEHRUNG|FUHRUNG|"
      "*FUEHRUNG|SIDE GUIDE|ZIJGELEIDER|SEITENFUEHRUNG|JAW|BEK|BACKE|*BACKE|FINGER|FINGERS|"
      "MANIFOLD|VERTEILER|VERDEELBLOK|ADAPTER|ADAPTOR|BALKJE|RIB|RIBBE|RIPPE|"
      "TAB|BOSS|NAAF|HUB|NABE|*NABE|WEDGE|WIG|KEIL|CARRIER|DRAGER|TRAEGERPLATTE|SLIDE|SLEDE|SCHLITTEN|"
      "TABLE|TAFEL|TISCH|TABLE TOP|TAFELBLAD|TISCHPLATTE",
      codes=[  # Misumi configurable plates, ribs, shims, adjusting blocks, belt clamp plates
             R + r"(?:RBBW|AJSLCM|AJSL)\d{1,3}-\d", R + r"ASFFR-A\d", R + r"TBCR-S\d",
             ]),
    T("rod", "Shafts, pins & spacers", "shape",
      "SHAFT|SHAFTS|AXLE|WELLE|*WELLE|AXE|ROD|RODS|STANG|STANGE|STAAF|ROUND BAR|RONDSTAAF|RUNDSTAB|PIN|PINS|"
      "PEN|STIFT|*STIFT|KEY|SHAFT KEY|SPACER|SPACERS|DISTANCE|DISTANCE PIECE|DISTANCE BUSH|AFSTANDSBUS|"
      "AFSTANDHOUDER|AFSTANDSSTUK|AFSTANDSRING|DISTANZHUELSE|DISTANZHULSE|DISTANZSTUECK|DISTANZSTUCK|"
      "DISTANZ|DISTANZBOLZEN|STANDOFF|STAND OFF|SLEEVE|HULS|HUELSE|HULSE|*HUELSE|*HULSE|RING|COLLAR|"
      "SET COLLAR|STELRING|STELLRING|ADJUSTING RING|SHAFT COLLAR|KLEMRING|KLEMMRING|AXIS PIN|PIVOT|"
      "SPINDLE|SPIL|SPINDEL|TRUNNION|BOLT PIN|HINGE PIN|SCHARNIERPEN|PLUNGER|DRUKSTUK|DRUCKSTUECK|"
      "DRUCKSTUCK|SPRING PLUNGER|BALL PLUNGER",
      codes=[  # Misumi: set collars PSCS10-10, SCSPJ10-6, SSCC20
             R + r"(?:[PS]?SCS(?:PJ|[JWAPM])?|[PS]?SCC|SCCN)\d{1,2}(?:-\d{1,3})?" + E,
             # spacers, posts and collars PLSBG7-120-M4-N3, SASPL6-30, NCLC20-30-20, CLJJ5-12-13.0
             R + r"[PS]?LSB[A-Z]{0,3}\d{1,2}-\d", R + r"(?:SASPL|SBSPO|PDSPO|PETGS|STNQ)\d{1,2}-\d",
             R + r"(?:NCL[CBM]|CLBU|CLBPS|CLJJ|CLJHM|FCLJH|SGPW)\d{1,2}-\d",
             # pins: dowel MSTH5-10, locating JPLR6-P8.5, hinge/pivot CLBRU10-66.0, stop SSTEH8
             R + r"(?:MSTM|MSTH|MST|MSC|MS)\d{1,2}-\d{1,3}" + E,
             R + r"(?:JP[A-Z]{1,4}|FPT|ELANA|G?SLP[A-Z]{1,5}|FSP[A-Z]{1,3}|STPASU)\s?(?:[A-Z]{1,2}\s)?\d{0,2}(?:\.\d)?[A-Z]?"
                 r"-(?:[A-Z]\d|\d)",
             R + r"(?:CLBRU|PCLBGHNU|CLKGH|SCCG|FCBDR)\d{1,2}-\d", R + r"(?:SSTEH|STEHN)\d{1,2}" + E,
             # ball and spring plungers BPJ16, PJL8-10; stopper bolts UST5-25, ANS4-25; keys KESS5-16
             R + r"(?:BPJLS|BPJL|BPRJ|BPJ|BPU|TBPJ|PJL)\d{1,2}[A-Z]?(?:-\d{1,3})?" + E,
             R + r"(?:UST|PUSS|STRC|UNAHM|UNBH|ANS|SANH|STBBS)\d{1,2}-\d{1,3}" + E, R + r"KESS?\d{1,2}-\d{1,3}" + E,
             ]),
    T("linear_shaft", "Chrome rods & linear shafts", "component",
      "PISTON ROD|PISTONROD|ZUIGERSTANG|KOLBENSTANGE|GUIDE ROD|GUIDE SHAFT|LINEAR SHAFT|LINEAR ROD|"
      "GELEIDEAS|FUEHRUNGSWELLE|FUHRUNGSWELLE|PRAEZISIONSWELLE|PRECISION SHAFT|CHROME ROD|CHROMED ROD|"
      "VERCHROOMDE AS|CYLINDER ROD|PLUNJER|LINEARWELLE|*LINEARWELLE|LINEAIRE AS",
      codes=[R + r"P?S?SF[JGHMRWTLUXDZKAN]{0,4}\d{1,2}-\d{2,4}",    # Misumi PSFJ20-300, SFJ16-200, PSFGD20-69
             R + r"(?:SAFS|SFRX|PSFRZ|PSFHKRW)\d{1,2}-\d{2,4}"]),         # Misumi shafts, rotary shafts
    T("cover", "Covers & panels", "shape",
      "COVER|COVERS|AFDEKKING|AFDEKPLAAT|ABDECKUNG|*ABDECKUNG|ABDECKPLATTE|ABDECKBLECH|COVER PLATE|"
      "PANEL|PANELS|PANEEL|PANEELEN|*PANEEL|PANEL SIDE|SIDE PANEL|ZIJPANEEL|SEITENWAND|WAND|WALL|"
      "KAP|*KAP|HOOD|HAUBE|*HAUBE|LID|DEKSEL|DECKEL|*DECKEL|DOOR|DOORS|DEUR|DEUREN|TUER|TUR|*TUER|"
      "HATCH|LUIK|KLAPPE|*KLAPPE|GUARD|GUARDING|AFSCHERMING|*AFSCHERMING|BESCHERMKAP|SCHUTZABDECKUNG|"
      "SHIELD|SPLASH GUARD|SPATSCHERM|SPRITZSCHUTZ|CASING|OMKASTING|OMMANTELING|VERKLEIDUNG|"
      "BEKLEDING|CLADDING|FAIRING|CANOPY|ROOF|DAK|DACH|SKIRT|SCHORT|FASCIA|FRONT PANEL|FRONTPLATTE|"
      "BACK PANEL|RUECKWAND|RUCKWAND|ACHTERWAND|CAP"),
    T("sheet", "Sheet metal parts", "shape",
      "SHEET|SHEET METAL|SHEETMETAL|BLECH|*BLECH|BLECHTEIL|KANTWERK|ZETWERK|PLAATWERK|PLAATDEEL|"
      "BENT PLATE|BENT SHEET|FOLDED SHEET|ABKANTTEIL|KANTDEEL|GEZET|GEKANT|TRAY|TRAYS|LEKBAK|DRIP TRAY|"
      "AUFFANGWANNE|WANNE|*WANNE|CHUTE|GOOT|*GOOT|HOPPER|TRECHTER|TRICHTER|*TRICHTER|BIN|BAK|DUCT|"
      "KANAAL|KANAL|CHANNEL SHEET|SKIN|HUID"),
    T("frame_weld", "Welded frames & structures", "shape",
      "WELDMENT|WELDMENTS|WELDED|WELDING ASSY|WELDED FRAME|WELDED ASSEMBLY|WELDED PART|LASCONSTRUCTIE|"
      "LASSAMENSTELLING|LASDEEL|LASWERK|GELAST|GELASTE|SCHWEISSKONSTRUKTION|SCHWEISSTEIL|SCHWEISSBAUGRUPPE|"
      "SCHWEISSGRUPPE|*SCHWEISSTEIL|*SCHWEISSKONSTRUKTION|CHASSIS|BASE FRAME|BASEFRAME|MAIN FRAME|MAINFRAME|"
      "SUBFRAME|SUB FRAME|MACHINE FRAME|MACHINEFRAME|MACHINEFRAME|ONDERSTEL|UNTERGESTELL|GESTELL|*GESTELL|"
      "MASCHINENGESTELL|MACHINEFRAME|FRAMEWORK|STEEL STRUCTURE|STAALCONSTRUCTIE|STAHLBAU|STAHLKONSTRUKTION|"
      "STRUCTURE|CONSTRUCTIE|SKID|PEDESTAL|BOOM|JIB|GIEK|AUSLEGER|MAST|TOWER|TOREN|GANTRY|PORTAL|PORTAAL|"
      "BEAM|BEAMS|BALK|BALKEN|TRAEGER|TRAGER|*TRAEGER|GIRDER|LIGGER|COLUMN|KOLOM|SAEULE|STAND|STELLAGE|"
      "SEAFASTENING|SEA FASTENING|ZEEVASTZETTING|GRILLAGE|GRILLAGES|RACK FRAME|TABLE FRAME|TAFELFRAME|TISCHGESTELL|CRADLE|WIEG|SADDLE|ZADEL|FOUNDATION|FUNDATIE|"
      "I BEAM|H BEAM|U PROFILE|L PROFILE|C PROFILE|Z PROFILE|U PROFIEL|L PROFIEL|C PROFIEL|U PROFIL|"
      "L PROFIL|HOEKPROFIEL|HOEKSTAAL|HOEKIJZER|WINKELPROFIL|WINKELSTAHL|U STAAL|U STAHL|KOKER|KOKERPROFIEL|"
      "VIERKANTROHR|RECHTECKROHR|VIERKANTBUIS|SQUARE TUBE|RECTANGULAR TUBE|BOX SECTION|HOLLOW SECTION|"
      "RHS|SHS|CHS|ANGLE|ANGLE IRON|CHANNEL|FLAT STEEL|FLACHSTAHL|STRIPSTAAL|PLATSTAAL|STRIP STEEL",
      codes=[R + r"(?:HE[ABM]|IPE|IPN|INP|UNP|UPN|UPE|HD|UAP)\s?-?\d{2,4}" + E,       # HEA200, IPE 160
             R + r"(?:RHS|SHS|CHS)\s?\d{2,3}\s?[X*]\s?\d", R + r"L\s?\d{2,3}\s?[X*]\s?\d{2,3}\s?[X*]\s?\d{1,2}" + E,
             R + r"YSBP\d{3}-"]),                                                                 # Misumi welded stands
    T("wear_strip", "Wear strips", "component",
      "WEAR STRIP|WEARSTRIP|SLIJTSTRIP|SLIJTLIJST|GLEITLEISTE|GLEITPROFIL|WEAR PLATE|SLIJTPLAAT|"
      "VERSCHLEISSPLATTE|CHAIN GUIDE|KETTINGGELEIDER|KETTENFUEHRUNG|KETTENFUHRUNG|SLIDE STRIP|GLIJSTRIP|"
      "GLIJLIJST|GLIDE STRIP|GLIJPROFIEL|GUIDE STRIP|CHAIN GUIDE STRIP|WEAR PAD|WEARPAD|SLIJTBLOK|GLIJBLOK|"
      "SLIDING PAD|SLIDE PAD|GLEITKLOTZ|GLEITSTUECK"),

    # ---- pneumatics ------------------------------------------------------------------------------
    T("pneumatic_cylinder", "Pneumatic cylinders & grippers", "product",
      "CYLINDER|CILINDER|ZYLINDER|*ZYLINDER|*CILINDER|PNEUMATIC CYLINDER|AIR CYLINDER|GUIDED CYLINDER|"
      "COMPACT CYLINDER|COMPACTCILINDER|KOMPAKTZYLINDER|RODLESS CYLINDER|STANGLOZE|SLIDE TABLE|SLEDECILINDER|"
      "ROTARY ACTUATOR|SWIVEL MODULE|DRAAICILINDER|SCHWENKANTRIEB|GRIPPER|GRIJPER|GREIFER|*GREIFER|"
      "PARALLEL GRIPPER|ANGULAR GRIPPER|CLAMP CYLINDER|SPANNZYLINDER|STOPPER CYLINDER|STOP CYLINDER|"
      "PNEUMATIEKCILINDER|PNEUMATIKZYLINDER|LUCHTCILINDER|AIRCYLINDER|TOOL CHANGER|WISSELSYSTEEM|CYL|CYLIDNER|"
      "CYLINER|CILINDRE|CYLINDRE|CYLNDER|2 JAW|3 JAW|TWO JAW|THREE JAW|2 FINGER|3 FINGER",
      codes=[  # SMC
             R + r"(?:CQ2|CQS|CQM|CDQ2|CDQS|CDQM|MGG|MGP|MGQ|MGJ|MGC|MGF|MGT|"
                 r"MXS|MXQ|MXH|MXP|MXJ|MXW|MXF|MXY|CXS|CXT|CXW|CY1|CY3|CYP|MY1|MY2|MY3|CJ1|CJ2|CJP|CM2|CM3|"
                 r"CG1|CG3|MB1?|CA2|C85|C95|C96|CP95|CP96|CS1|CS2|MKB?|CKQ|CU|CUJ|CQU|MU|MHZ2|MHZJ2|MHZL2|"
                 r"MHF2|MHS[234]|MHC2|MHY2|MHT2|MHK2|MHL2|MHW2|MSQ|CRB1|CRBU2|CRA1|CRQ2|MSU|MRQ|CLK2|MLGP|"
                 r"MLGC|CLQ|MIW|MIS|CDJ2|CDM2|CDG1|CDU|CDBX|CLJ2|CLM2|CNG|CNA|MGPM|MGPL|MGGM|MGGL|MXQR|"
                 r"MDB|MDBB|CDQ2B|CQ2B|CDQ2A|NCDJ2|NCDMB|NCJ2|NCM|C76|CD76|CD85|ZCDU)"
                 r"[A-Z]{0,4}\d{1,3}[A-Z]{0,4}-\d{1,4}",
             R + r"_?(?:MHZ2|MHZJ2|MHF2|MHS[234]|MHC2|MHY2|MHT2|MHK2|MHL2|CRB1|MSQ[AB]?)-?\d{1,3}",
             # Festo
             R + r"(?:DSNU|ESNU|ADN|AEN|ADVU|AEVU|ADVC|AEVC|ADNGF|DSBC|DSBG|DSBF|DNC|DNCB|DNCT|DNG|DGSL|DFM|"
                 r"DGC|DGP|DGPL|DSM|DRVS|DRQD|DFPD|HGPT|HGPL|HGPP|HGPC|HGDT|DHPS|DHDS|DHRS|DHPC|DPDM|DPZ|DPZJ|"
                 r"DMM|DZF|DZH|CDC|SLT|SLS|SLF|DGST|DPRE|ADNH|AND|VZWP|DFST|DFSP|EGP)-\d{1,3}",
             # Schunk, Zimmer, Gimatic, Afag
             R + r"(?:PGN|PGN-PLUS|JGP|PZN|PZN-PLUS|PGL|PGF|SRU|SWS|EGP|EGK|GSM|PSH|GEP|GPP|GPD|MGW|MPPM|"
                 r"GH|SCHUNK)[- ]?(?:PLUS[- ])?\d{2,3}",
             ],
      roles={"rod": "cylinder_rod", "linear_shaft": "cylinder_rod", "pipe": "pneumatic_cylinder"}),
    T("cylinder_rod", "Chrome rods & linear shafts", "component", ""),
    T("linear_actuator", "Linear actuators & rotary tables", "product",
      "LINEAR ACTUATOR|LINEAR AXIS|LINEAR MODULE|LINEAR UNIT|LINEARACHSE|LINEAREINHEIT|LINEAIRE AS|"
      "LINEAIRE UNIT|LINEAIRE MODULE|ELECTRIC CYLINDER|ELEKTRISCHE CILINDER|ELEKTROZYLINDER|SPINDLE AXIS|"
      "BELT AXIS|TOOTHED BELT AXIS|ZAHNRIEMENACHSE|SPINDELACHSE|PORTAL AXIS|ROTARY TABLE|INDEXING TABLE|"
      "DRAAITAFEL|RUNDSCHALTTISCH|DREHTISCH|DREHMODUL|ROTARY MODULE|ROTARY INDEXER|LIFT MODULE|HUBMODUL",
      codes=[R + r"(?:EGC|EGSK|EGSP|ELGA|ELGC|ELGS|ELGR|EPCO|ESBF|EMMS|EGSC|ERMO|EHMB|ELGD|DGE|EGSA)-"
                 r"(?:[A-Z]{1,3}-)?\d{2,3}",
             R + r"LE(?:F|FS|FB|Y|YG|J|JS|JB|S|SH|H|HF|HZ|HZJ|PY|PS|R|RU|MB|MC|MH|L|KFS)\d{1,2}[A-Z]{0,3}\d{0,3}"
                 r"[A-Z]{0,3}-\d{1,4}",                                   # SMC electric actuators
             R + r"(?:RCP\d|RCA\d?|RCS\d|ISB|ISPB|IXA|ICSA|ERC\d)-[A-Z0-9]",  # IAI
             ]),
    T("hydraulic_cylinder", "Hydraulic cylinders", "product",
      "HYDRAULIC CYLINDER|HYDRAULIEKCILINDER|HYDRAULIEK CILINDER|HYDRAULIKZYLINDER|HYDR CYLINDER|"
      "HYD CYLINDER|HYDCYL|HYDRO CYLINDER|RAM|JACK CYLINDER|PLUNGER CYLINDER|PLUNJERCILINDER|"
      "LIFTING CYLINDER|HEFCILINDER|LUFFING CYLINDER|TOPCILINDER|TELESCOPIC CYLINDER|TELESCOOPCILINDER|"
      "LUFFING CYL|HYD CYL|HYDR CYL|HYDRAULIC CYL|HEAVE CYLINDER|HEAVE COMP CYLINDER|HEAVE COMPENSATOR CYLINDER|"
      "COMPENSATOR CYLINDER|TENSIONER CYLINDER|KNUCKLE CYLINDER|SLEW CYLINDER|FOLDING CYLINDER",
      roles={"rod": "cylinder_rod", "linear_shaft": "cylinder_rod", "pipe": "hydraulic_cylinder"}),
    T("gas_spring", "Gas springs & shock absorbers", "product",
      "GAS SPRING|GASSPRING|GASVEER|GASDRUKVEER|GASFEDER|GASDRUCKFEDER|GAS STRUT|SHOCK ABSORBER|"
      "SCHOKBREKER|SCHOKDEMPER|STOSSDAEMPFER|STOSSDAMPFER|STOSDEMPER|INDUSTRIAL DAMPER|DAMPER|DEMPER|"
      "DAEMPFER|DAMPFER|*DAEMPFER|*DAMPFER|*DEMPER|DASHPOT|OIL DAMPER|VELOCITY CONTROLLER",
      codes=[R + r"RBC?Q?\d{4}" + E,                                   # SMC RB
             R + r"(?:MC|SC|MA|PMCN)\d{2,4}(?:EUM|M)(?:-\d)?" + E,          # ACE
             R + r"STABILUS" + E,
             R + r"MAK[CS]\d{3,4}[A-Z]{0,2}" + E, R + r"(?:C-|M)AC\d{4}[A-Z]{0,2}" + E],  # Misumi MAKC1008L, C-AC1210S
      roles={"rod": "cylinder_rod", "linear_shaft": "cylinder_rod"}),
    T("valve", "Valves & valve terminals", "product",
      "VALVE|VALVES|VENTIEL|VENTIELEN|VENTIL|*VENTIL|*VENTIEL|KLEP|*KLEP|SOLENOID VALVE|MAGNEETVENTIEL|"
      "MAGNETVENTIL|VALVE TERMINAL|VALVE ISLAND|VENTIELEILAND|VENTILINSEL|VALVE MANIFOLD UNIT|"
      "FILTER REGULATOR|AIR PREPARATION|SERVICE UNIT|LUCHTBEHANDELING|WARTUNGSEINHEIT|DRUCKREGLER|"
      "PRESSURE REGULATOR|REDUCEERVENTIEL|DRUKREGELAAR|REGULATOR|FRL|LUBRICATOR|OLER|OELER|"
      "SPEED CONTROLLER|FLOW CONTROL|SMOORVENTIEL|DROSSELVENTIL|DROSSELRUECKSCHLAGVENTIL|CHECK VALVE|"
      "EJECTOR|VACUUM GENERATOR|VACUUMGENERATOR|VAKUUMERZEUGER|EJEKTOR|SOFT START|SLOW START|"
      "AIR FILTER|LUCHTFILTER|DRUCKLUFTFILTER|PILOT VALVE|QUICK EXHAUST|SNELONTLUCHTER|SCHNELLENTLUEFTUNG|SHUT OFF VALVE|AFSLUITER",
      codes=[R + r"(?:SY|SYJ|SYA|JSY|VQ|VQC|VQZ|VQD|VF|VFS|VFR|VP|VPA|VX|VXD|VXZ|VT|VTA|"
                 r"VV5Q|VV5QC|SS5Y|SS5J|SS5V|ITV|IRV|VHS|VHK|ASP|ASR|ASQ|AS|ZH|ZK2|ZU|ZX|ZQ|AW|AWM|AR|ARM|"
                 r"AF|AFM|AFD|AV|AMG|AMH|AMD)\d{2,5}[A-Z]{0,3}-",                 # SMC
             R + r"(?:SY|SYJ|VQ|VQC|VF|JSY)\d{3,4}" + E,
             R + r"(?:VUVG|VUVS|VUVB|VUWG|VSVA|VSNC|VZWF|VZWM|VZWD|VMPA|VMPAL|VTUG|VTUB|VTUS|VTSA|VTEM|CPX|CPE|"
                 r"MPA|MPAL|MPA-L|MHE|MHA|MHP|VUVE|VAD|VN|OVEM|OVEL|VADM|VAK|LFR|LFRS|LFMA|LFMB|"
                 r"MSB[46]|FRC|LOE|HE|HEE|GRLA|GRLO|GRLZ|GRXA|GRO|VBQF|VFOF|VZQA|VZBA|VZPR)-[A-Z]{0,2}\d",  # Festo
             R + r"MS[46912]-[A-Z]",                                            # Festo MS6-LFR (MS6-10: Misumi pin)
             R + r"(?:CPV|CPX|VTSA|VTUG|MPA)\d{0,2}-",
             R + r"(?:AV03|AV05|HF0[234]|CL03)" + E,                         # Aventics, Norgren
             ],
      absorb="all"),
    T("ball_valve", "Ball valves & taps", "product",
      "BALL VALVE|BALLVALVE|KOGELKRAAN|KUGELHAHN|KUGELVENTIL|GATE VALVE|SCHUIFAFSLUITER|SCHIEBER|"
      "BUTTERFLY VALVE|VLINDERKLEP|ABSPERRKLAPPE|NEEDLE VALVE|NAALDVENTIEL|NADELVENTIL|TAP|KRAAN|HAHN|"
      "*HAHN|*KRAAN|STOPCOCK|GLOBE VALVE|PLUG VALVE|DRAIN VALVE|AFTAPKRAAN|ABLASSHAHN|SAFETY VALVE|"
      "VEILIGHEIDSKLEP|SICHERHEITSVENTIL|PRESSURE RELIEF VALVE"),
    T("hydraulic", "Hydraulic components", "product",
      "HYDRAULIC PUMP|PUMP|POMP|PUMPE|*PUMPE|*POMP|HYDRAULIC MOTOR|HYDROMOTOR|HYDRAULIKMOTOR|HYDRAULIEKMOTOR|"
      "ORBIT MOTOR|ACCUMULATOR|HYDROSPEICHER|DRUKVAT|HYDRAULIC VALVE|HYDRAULIC BLOCK|HYDRAULIC MANIFOLD|"
      "POWER PACK|POWERPACK|POWER UNIT|HYDRAULIC UNIT|HYDRAULIC POWER UNIT|HPU|AGGREGAAT|HYDRAULIKAGGREGAT|"
      "AGGREGAT|OIL COOLER|OLIEKOELER|OELKUEHLER|RETURN FILTER|PRESSURE FILTER|HYDRAULIC FILTER|"
      "OIL FILTER|OLIEFILTER|OELFILTER|FILTER|FILTERS|LINE FILTER|RETURN LINE FILTER|PRESSURE LINE FILTER|"
      "FILTER ELEMENT|FILTERELEMENT|HYDRAULIC MANIFOLD BLOCK|MANIFOLD BLOCK HYDRAULIC|BREATHER|BELUCHTINGSFILTER|SIGHT GLASS|OLIEPEILGLAS|"
      "OIL TANK|HYDRAULIC TANK|RESERVOIR|OLIETANK|OELTANK|COUNTERBALANCE VALVE|LOAD HOLDING VALVE|"
      "DIRECTIONAL VALVE|PROPORTIONAL VALVE|CONTROL BLOCK|STUURBLOK|STEUERBLOCK|MOTOR VALVE",
      codes=[R + r"(?:4WE|4WEH|4WRA|4WRE|4WRPE|DBD|DBDS|DBW|Z2FS|Z2S|Z2DB|ZDR|3DREP|4WMM|"
                 r"A10VSO|A10VO|A4VG|A4VSO|A2FM|A6VM|PVG|PVB|OMP|OMR|OMS|OMT|OMV|EPMM|BMR|BMP|PGP|PGF)"
                 r"\s?-?\d{1,3}",
             R + r"(?:PVG|OMR|OMP|OMS|OMT|OMV)\s?\d{2,3}" + E],
      absorb="all"),
    T("fitting", "Fittings", "component",
      "FITTING|FITTINGS|PUSH IN|PUSH IN FITTING|PUSHIN|INSTEEKKOPPELING|INSTEEKFITTING|STECKVERSCHRAUBUNG|"
      "STECKANSCHLUSS|STECKVERBINDER|VERSCHRAUBUNG|*VERSCHRAUBUNG|ROHRVERSCHRAUBUNG|WINKELVERSCHRAUBUNG|"
      "SCHROEFKOPPELING|SCHROEFVERBINDING|KOPPELSTUK|ELBOW|ELLEBOOG|BOCHT|KNIE|WINKELSTUECK|TEE|T STUK|"
      "T STUECK|T PIECE|UNION|VERLOOP|REDUCER FITTING|REDUCTIENIPPEL|REDUZIERNIPPEL|NIPPLE|NIPPEL|*NIPPEL|"
      "HOSE NIPPLE|SLANGPILAAR|SCHLAUCHTUELLE|SCHLAUCHTULLE|BANJO|BANJO BOLT|HOLSCHROEF|HOHLSCHRAUBE|"
      "SILENCER|MUFFLER|GELUIDDEMPER|SCHALLDAEMPFER|SCHALLDAMPFER|QUICK COUPLING|QUICK COUPLER|SNELKOPPELING|"
      "SNELKOPPELINGEN|KUPPLUNGSSTECKER|KUPPLUNGSDOSE|SCHNELLKUPPLUNG|PLUG FITTING|BLIND PLUG|BLINDSTOP|"
      "VERSCHLUSSSCHRAUBE|BULKHEAD|SCHOTDOORVOER|DISTRIBUTOR|VERDEELSTUK|NOZZLE|SPUITMOND|DUESE|DUSE|"
      "*DUESE|SPROEIER|COUPLING NUT|WARTELMOER|MUFFE|MOF|SOK|CROSS FITTING|KRUISSTUK|Y FITTING|Y STUK|JIC|ORFS|BSPP|BSPT|NPT|DKO|SWIVEL ADAPTOR|"
      "SWIVEL ADAPTER|ADAPTOR FITTING|ADAPTER FITTING|SAE FLANGE|SAE FLENS|SAE FLANSCH|CODE 61|CODE 62|"
      "SPLIT FLANGE|FLANGE HALF|TEST POINT|MEETPUNT|MESSANSCHLUSS|MINIMESS",
      codes=[R + r"(?:KQ2|KQB2|KQG2|KQ|KJ|KJH|KJL|KJS|KQ2H|KQ2L|KQ2T|KQ2U|KQ2S|KQ2V|KQ2Y|KQ2ZD|KQ2P|KFG2|"
                 r"KFH|KPQ|KPG|KPH|AN|ANA|ANB|ASN)[A-Z]{0,4}\d{1,3}",
             R + r"KQ2[A-Z]{1,3}\d{2}-",                                   # SMC push-in KQ2H06-01AS
             R + r"(?:QS|QSL|QSLL|QSLV|QSY|QSM|QSML|QSMY|QSF|QST|QSTF|QSK|QSKL|NPQH|NPQM|NPQP|NPQR|QSS|"
                 r"QSRL|QSW|QSX|QSYL|U|UC|UOS|AMTE|NPFC|NPHS|NPCK|NPFV|KD\d|KS\d|KDS)-[A-Z0-9]",   # Festo
             R + r"(?:GE|WE|EW|EL|ET|TEE|WEE|RED|GZ|SV|WSV|EGE|GAI|XGE|RI|KOR|TRI|VKA|LR|RL)\s?\d{1,2}\s?(?:LL|L|S)"
                 r"(?:R|M|ED|OMD|71)?" + E,                                # DIN 2353 / ISO 8434 fittings
             R + r"SS-\d{3,4}-",                                           # Swagelok
             ]),
    T("hose", "Hoses & tubing", "component",
      "HOSE|HOSES|SLANG|SLANGEN|*SLANG|SCHLAUCH|*SCHLAUCH|TUBING|AIR HOSE|AIR TUBE|AIR LINE|"
      "PNEUMATIC TUBE|PNEUMATIC HOSE|PNEUMATIC LINE|LUCHTSLANG|LUCHTLEIDING|DRUCKLUFTSCHLAUCH|PU TUBE|PUR TUBE|"
      "PE TUBE|PA TUBE|NYLON TUBE|POLY TUBE|POLYURETHANE TUBE|PLASTIC TUBE|HYDRAULIC HOSE|HYDRAULIEKSLANG|"
      "HYDRAULIKSCHLAUCH|HOSE ASSY|HOSE ASSEMBLY|SLANGSET|FLEXIBLE|FLEXIBLE HOSE|FLEX HOSE|WATER HOSE|"
      "COOLANT HOSE|SPIRAL HOSE|SPIRAALSLANG|SPIRALSCHLAUCH|CORRUGATED TUBE|CORRUGATED HOSE|RIBBELBUIS|"
      "WELLROHR|FLEXIBLE CONDUIT|INSTALLATIEBUIS",
      codes=[R + r"(?:TU|TUS|TUH|TUZ|TRB|TRBU|TUL|TCU|TIUB|TIA|TISA|TPH)\d{4}",              # SMC tubing
             R + r"(?:PUN|PUN-H|PAN|PLN|PEN|PFAN|PUN-V0|PUN-CM|PUN-DUO|PUN-S|PU)-\d{1,2}X\d",          # Festo
             R + r"(?:[12]SN|[12]ST|[12]SC|4SH|4SP|R1AT|R2AT)-?\d{1,2}" + E,   # hydraulic hose specs (2SN-12)
             ]),
    T("pipe", "Pipes", "component",
      "PIPE|PIPES|PIJP|PIJPEN|PIPING|LEIDING|LEIDINGEN|*LEIDING|ROHRLEITUNG|ROHR|*ROHR|BUIS|BUIZEN|*BUIS|TUBE|"
      "TUBES|HYDRAULIC TUBE|HYDRAULIC PIPE|HYDRAULIEKLEIDING|HYDRAULIKROHR|PRECISION TUBE|PRECISIEBUIS|"
      "PRAEZISIONSROHR|STAINLESS TUBE|RVS BUIS|ROUND TUBE|RONDE BUIS|PIPE SPOOL|SPOOL|STANDPIPE|DRAIN PIPE"),
    T("pipe_clamp", "Pipe & hose clamps", "component",
      "HOSE CLAMP|HOSE CLIP|SLANGKLEM|SCHLAUCHSCHELLE|SCHLAUCHKLEMME|PIPE CLAMP|TUBE CLAMP|BUISKLEM|PIJPKLEM|"
      "PIJPBEUGEL|ROHRSCHELLE|ROHRHALTER|SCHELLE|*SCHELLE|CABLE CLAMP|KABELKLEM|KABELSCHELLE|P CLIP|PCLIP|"
      "SADDLE CLAMP|U BOLT CLAMP|STAUFF|CLAMP HALF|KLEMSCHAAL|SPANNBACKE ROHR|TUBE HOLDER|PIPE SUPPORT|"
      "PIJPOPHANGING|ROHRHALTERUNG|HOSE HOLDER|SLANGHOUDER|SCHLAUCHHALTER|CLIPS",
      codes=[R + r"STAUFF" + E]),
    T("vacuum_cup", "Vacuum cups", "component",
      "SUCTION CUP|SUCTIONCUP|VACUUM CUP|VACUUM PAD|VACUUMCUP|ZUIGNAP|ZUIGNAPPEN|SAUGER|*SAUGER|SAUGNAPF|"
      "VAKUUMSAUGER|SAUGGREIFER|VACUUM GRIPPER PAD|SUCKER|BELLOWS CUP|BALGSAUGER|FLAT CUP|FLACHSAUGER",
      codes=[R + r"ZP[23]?[A-Z]?\d{2,3}[A-Z]{0,3}" + E, R + r"ZP[23][A-Z]?-[A-Z]?\d{2}", R + r"(?:ESS|ESG|VASB|VAS|OGGB)-\d{1,3}",
             R + r"(?:SPB\d|SPF|FSG|SAB|FGA|SGPN|SFF|PFYN|PFG)\s?-?\d{1,3}"]),

    # ---- linear motion, bearings, power transmission ----------------------------------------------
    T("linear_guide", "Linear guides & ball screws", "component",
      "LINEAR GUIDE|LINEAR RAIL|LINEAR BEARING|LINEAR BUSHING|LINEAR BALL BEARING|LINEARFUEHRUNG|"
      "LINEARFUHRUNG|LINEAIRE GELEIDING|LINEAIRGELEIDING|GUIDE RAIL|GELEIDERAIL|FUEHRUNGSSCHIENE|"
      "FUHRUNGSSCHIENE|PROFILSCHIENE|PROFILE RAIL|RAIL|RAILS|SCHIENE|*SCHIENE|CARRIAGE|CARRIAGES|"
      "GUIDE BLOCK|LINEAR BLOCK|RUNNER BLOCK|RUNNERBLOCK|BALL RUNNER BLOCK|SLIDE BLOCK|BEARING BLOCK|"
      "KUGELWAGEN|FUEHRUNGSWAGEN|FUHRUNGSWAGEN|LAUFWAGEN|GELEIDEWAGEN|GELEIDEBLOK|SLEDE BLOK|WAGEN|"
      "LM GUIDE|MINIATURE GUIDE|KOGELBUS|KOGELBUSSEN|LINEARKUGELLAGER|KUGELBUECHSE|KUGELBUCHSE|"
      "BALL SCREW|BALLSCREW|BALL SCREWS|KOGELOMLOOPSPINDEL|KOGELOMLOOP|KUGELGEWINDETRIEB|KUGELGEWINDESPINDEL|"
      "*GEWINDESPINDEL|*GEWINDETRIEB|LEAD SCREW|LEADSCREW|TRAPEZOIDAL SCREW|TRAPEZ SCREW|TRAPEZIUMSPINDEL|"
      "TRAPEZSPINDEL|TRAPEZGEWINDESPINDEL|ACME SCREW|BALL NUT|BALLNUT|SPINDLE NUT|SPINDELMUTTER|"
      "KOGELMOER|FLANGE NUT SCREW|SCREW SUPPORT|SUPPORT UNIT|SPINDLE SUPPORT|LOSLAGER|FESTLAGER|"
      "VASTE LAGERING|LOSSE LAGERING|SUPPORTED RAIL|SHAFT SUPPORT|SHAFT HOLDER|ASSTEUN|WELLENBOCK|"
      "WELLENHALTER|WELLENUNTERSTUETZUNG",
      codes=[R + r"(?:HGR|HGH|HGW|HGL|MGN|MGW|MGR|EGR|EGH|EGW|RGR|RGH|RGW|QHH|QHW|QEH|QEW|WER|WEH|WEW|AGH|"
                 r"CGH|CGW|PGH|HG|EG|RG|MG)\d{1,2}(?:[A-Z]{1,3}\d{0,5}[A-Z]{0,2})?" + E,  # HIWIN
             R + r"(?:SHS|SSR|HSR|HRW|RSR|SRS|NRS|SHW|SVR|SVS|SNR|SNS|SRG|SRN|SPR|EPF|GSR|"
                 r"CSR|HCR|NSR|SRW)\d{1,2}(?!X\d)[A-Z]{0,3}\d?" + E,                     # THK
             R + r"R(?:16\d{2}|18\d{2}|20\d{2}|19\d{2})\s?\d{3}\s?\d{2}" + E,           # Bosch Rexroth R1651...
             R + r"(?:KUVE|KWVE|KUSE|TKVD|TKSD|TSX|RUE|KWEM|TKDU|KUME|RWU)\d{2}",       # INA / Schaeffler
             R + r"(?:NH|NS|LH|LS|LU|PU|PE|SH|SS|VH|RA|RB)\d{2}\s?\d{3,4}\s?[A-Z]{1,3}\d?" + E,  # NSK
             R + r"(?:SSEB|SSEBV|SSELB|SVR|SV2R|SXR|SRX|SSE2B|SEB|SEBS|SE2B|SSEBZ|LX|KUX|LBF|LBH|LTB|KUA|SRS)"
                 r"[A-Z]?\d{1,2}[A-Z]?-\d{2,4}",                                         # Misumi
             R + r"L(?:M|MK|MF|ME|MH|ML|HF|HFR|HFRW|HSF|HCF|HFC|HFS|HFRP|HFTP|HFKR|HMF|HMG|BF|BH)\d{1,2}"
                 r"(?:UU|L|LUU|OP|AJ)?" + E,                                             # linear bushings
             R + r"(?:SBR|SBRB|SBRS|TBR|SFU|SFI|SFK|SFE|DFU|DFI|BSS|BSSR|BSST|BSB|BSBR|BSSE|MTSBR|MTSRW|"
                 r"MTSKR|MTSTR|MTW|MTWK)\d{2,4}(?:[A-Z]{0,4})?(?:-\d{1,4})?" + E,         # ball screws, rails
             R + r"(?:BK|BF|FK|FF|EK|EF|WBK|WBF)\d{2}" + E,                              # screw support units
             R + r"R\d{2}-\d{1,2}[A-Z]\d" + E,                                           # HIWIN ball screw R16-5T3
             # Misumi shaft supports SHA20, SHFTL16, STHCN20; linear bushings LMUW20, LHFRW-MX16, C-LHBB10;
             # ball and lead screws BSX1605, MTSRX16-456; support units BSW12
             R + r"SH(?:FTL?|FML?|FSSL?|FDL?|FL?|AKD|AKS?|ASSN?|ATN?|AMN?|AN?|FR|FC|FB|FS|BS|KCS)\d{1,2}(?!\d)",
             R + r"(?:STH[A-Z]{1,4}|SHT[A-Z]{1,3}|SHST[A-Z]{1,3})\d{1,2}(?!\d)",
             R + r"S?L(?:MU[WTD]?|MKW|HI?F[RSC]W?|HI[RS]W|HMRW|HFRD|HRK|HKRL|HKMSLF|HSS|HG[SW]|HBBW?F?)\d{1,2}(?!\d)",
             R + r"LH[A-Z]{2,4}-MX\d{1,2}", R + r"SX2[A-Z]{1,4}\d{2}-\d", R + r"(?:BSX\d{4}|MTS[A-Z]{1,4}\d{2}-\d)", R + r"(?:BSW|BRW|BUN|BUR)\d{2}" + E,
             R + r"(?:SHS|SSR|HSR|SR|NR|SHW|HRW|RSR|SRS)\d{2}[A-Z]{1,3}\d?[A-Z0-9]*\+\d{3,4}L",      # THK rail + length
             ],
      roles={"bushing": "linear_guide"}),          # the BUSHING inside a linear bushing housing (LHFRW20)
    T("bearing", "Bearings", "component",
      "BEARING|BEARINGS|BALL BEARING|ROLLER BEARING|NEEDLE BEARING|THRUST BEARING|SPHERICAL BEARING|"
      "ANGULAR CONTACT BEARING|TAPERED ROLLER BEARING|DEEP GROOVE|KOGELLAGER|ROLLAGER|NAALDLAGER|TAATSLAGER|"
      "LAGER|LAGERS|*LAGER|KUGELLAGER|ROLLENLAGER|NADELLAGER|WAELZLAGER|WALZLAGER|AXIALLAGER|GELENKLAGER|"
      "PENDELLAGER|SPHERICAL PLAIN BEARING|CAM FOLLOWER|TRACK ROLLER|KURVENROLLE|LAUFROLLE|NOKVOLGER|"
      "STUD TYPE TRACK ROLLER|SLEWING RING|SLEWING BEARING|SLEW RING|DRAAIKRANS|DREHKRANZ|DREHVERBINDUNG|"
      "SWING BEARING|TURNTABLE BEARING|CROSSED ROLLER|KRUISROLLENLAGER|KREUZROLLENLAGER|INSERT BEARING|"
      "BEARRING|BEARIGN|BAERING|ANGULAR CONTACT|SCHRAEGKUGELLAGER|HOEKCONTACTLAGER",
      codes=[R + r"(?:SKF|FAG|INA|NSK|NTN|KOYO|TIMKEN|NACHI|ZKL|SNR|IKO|RHP|NKE|JTEKT|EZO|MINEBEA|"
                 r"KAYDON|ROTHE ERDE|LIEBHERR ROTATION)" + E,
             R + r"(?:6[0-4]\d|16\d|618|619|62|63|60|7[0-3]|1[23]|22|23|21|24|32|30|31|33|51|52|53|81|29)\d{2,3}"
                 r"(?:[-_ ]?(?:2RS1?|2RSH|2RSR|2RS|2Z|ZZ|RS|Z|DDU|LLU|LLB|VV|2RSL|ETN9|EC|ECP|ECJ|CC|CA|J2|C3|"
                 r"BE|BEP|ACD|NR|BECBP|2Z/C3|P5|P6|TN9|CCK|EK|EAE4|CA/W33))+" + E,
             R + r"(?:(?:NU|NJ|NUP|NN|NNU|NA|NK|NKI|NKX|NKIS|RNA|RNAO|NKS|NATR|NATV|NUTR|PWTR|QJ|QJF|AXK|STO|"
                 r"NUKR|NART)\s?|(?:HK|KR|KRV|CF|CFH|KRE|GE|GEG|GEH|GS|WS))\d{2,4}"
                 r"(?:[-_ ]?(?:2RS|2RSR|PP|PPA|ECP|ECJ|EC|E|ES|DO|UK|2RS|ZZ|X|PP|VUU|UU|-2RS|DO-2RS|C3|LLU|TN))*"
                 r"(?:[- ]?[A-Z]{0,3})?" + E,
             R + r"2[1-4]\d{3}\s?(?:E|EK|EJA|CC|CCK|CA|CAK|MB|MBK)(?:/W33|/C3)?" + E,   # spherical roller
             R + r"(?:RKS|RD|RA|RB|RE|RU|CRBH|CRBC|CRBF|XU|XR|KRB|YRT|YRTS|ZKLF|ZKLN|SX|RTS|VSU|VSA|VSI|KD|KH|KX|"
                 r"KA|XSU|XSA|XSI|MTO|MTE|MT)\d{3,6}" + E,                                  # slewing/crossed roller
             R + r"(?:B|FL)(?:6[0-4]\d{1,2}|6[7-9]\d{2})(?:ZZ|VV|DDU?|LLU|LLB|2RS|RS|Z)" + E,  # Misumi B6206ZZ, FL608ZZ
             ]),
    T("bearing_housing", "Bearing housings & units", "component",
      "PILLOW BLOCK|PLUMMER BLOCK|BEARING HOUSING|BEARING UNIT|BEARING UNITS|FLANGE BEARING|FLANGED BEARING|"
      "FLANGE UNIT|TAKE UP UNIT|STEHLAGER|FLANSCHLAGER|LAGERHUIS|LAGERBLOK|LAGERBLOCK|LAGERGEHAEUSE|"
      "LAGERGEHAUSE|LAGERBOCK|STAANDE LAGER|FLENSLAGER|STEHLAGERGEHAEUSE|LAGEREINHEIT|LAGERUNIT|"
      "BEARING SUPPORT|BEARING BLOCK HOUSING|SPANNLAGER",
      codes=[R + r"UC(?:P|F|FL|FC|T|PA|FA|FB|HA|PH|FX|PX|TX|K|FU|FS|PE)\s?\d{3}" + E,
             R + r"(?:SY|FY|FYJ|FYTB|FYT|FYK|FYC|SYJ|SYK|SYF|FYTJ|TU|SYE)\s?\d{2}\s?(?:TF|FM|WF|TR|KF|TDW|WDW|LF|FX|"
                 r"WR|RM|TF/VA|TDT|TDR|M|KF)" + E,                                           # SKF Y-units
             R + r"(?:SNL|SNV|SAF|SNH|SD|SOFN|FNL|SE|SNG|SONL|SYNT|FYNT|BND|RCJ|RASE|RSAO|RME|PASE|PCJ|TCJ|"
                 r"GRAE|GYE|GE|RCJT|RHE|PCJT|PB|PHE|PSHE|RAK)\s?\d{3,5}" + E,
             R + r"(?:BGRBB|BGRBS|BGSBB|BGHBB|BGFAB|BGCHB|BGFAC|BGHC|BGRR|BGCBB)\d{2,4}",
             R + r"(?:PASE|RASE|RCJT?|PCJT?|TCJ|RSAO|RME|GRAE|GYE|RHE|PHE|PSHE|RAK)\d{2}-",          # INA PASE30-XL
             R + r"HDH\d{2}" + E]),                                                       # Misumi bearing holders
    T("rod_end", "Rod ends & clevises", "component",
      "ROD END|RODEND|ROD ENDS|ROD END BEARING|GELENKKOPF|*GELENKKOPF|STANGENKOPF|STANGKOP|KOGELGEWRICHT|"
      "KOGELKOP|BALL JOINT|KUGELGELENK|*KUGELGELENK|WINKELGELENK|AXIAL JOINT|AXIALGELENK|CLEVIS|CLEVISES|"
      "GAFFELKOP|GAFFEL|GABELKOPF|*GABELKOPF|FORK HEAD|FORKHEAD|FLOATING JOINT|AUSGLEICHSKUPPLUNG|"
      "ZWEVENDE KOPPELING|ROD CLEVIS|CLEVIS BRACKET|PIVOT BRACKET|SCHARNIERBOCK|"
      "TRUNNION MOUNTING|SWIVEL FLANGE|SCHWENKBEFESTIGUNG|SCHARNIERBEVESTIGING",
      codes=[R + r"(?:SI|SA|SIL|SAL|GIR|GAR|GIKR|GAKR|GIKL|GAKL|GIXSR|GIXSL|PHS|POS|PHSA|NHS|NOS|SIKAC|SAKAC|"
                 r"SIJK|SAJK|SIQG|SIRT)\s?\d{1,2}(?:\s?[A-Z]{1,3}){0,2}" + E,         # rod ends
             R + r"(?:JA|JAH|JB|JC|JT|JS)\d{2,3}-\d",                                   # SMC floating joints
             R + r"(?:SGS|SGA|CRSGS|SG|FK|CRFK|SGM|LBG|LNG|SNC|SNCB|SNCL|SNCS|SNGB|SNGL|SNG|SNL|SBN|SBS|"
                 r"DAMD|LQG|CRLNG)-(?:M\d|\d{2})"]),                                      # Festo mountings
    T("bushing", "Bushings & plain bearings", "component",
      "BUSHING|BUSHINGS|BUSH|BUSHES|BUS|BUSSEN|BUCHSE|BUECHSE|BUCHSEN|*BUCHSE|*BUECHSE|GLIJLAGER|GLIJLAGERS|"
      "GLEITLAGER|GLEITBUCHSE|LAGERBUCHSE|LAGERBUS|GLIJBUS|PLAIN BEARING|SLIDING BEARING|SLEEVE BEARING|"
      "SINTERED BUSH|SINTERBUCHSE|DU BUSH|DU BUSHING|BRONZE BUSH|BRONZEBUS|COLLAR BUSH|FLANGED BUSHING|"
      "KRAAGBUS|BUNDBUCHSE|DRILL BUSH|BOORBUS|BOHRBUCHSE|GUIDE BUSH|GELEIDEBUS|FUEHRUNGSBUCHSE|FUHRUNGSBUCHSE",
      codes=[R + r"PCM\d{6}" + E, R + r"(?:PAP|PRM|MB)\s?\d{4,6}\s?(?:P10|P14|P20|DU|DX)" + E,
             R + r"(?:MPBZ|MPBZB|LFZ|LFB|LFDS|BZ|OCR|BUSHB)\d{1,3}-\d{1,3}",
             R + r"(?:MPFZU?|MPBZU|JZB|SMZF?|JBAFS|JBAM|JBA|JBHN)\d{1,2}-[A-Z0-9]",            # Misumi MPFZU8-10, JBA10-15
             R + r"SOB-?\d{2}-\d{2}-\d{2}" + E,                                        # Sankyo Oilless
             R + r"(?:\d{2,3}F-\d{4}|SPB-\d{4,6}|500SP\d?-)"]),                        # Oiles 80F-3840, #500SP
    T("plastic_bearing", "Plastic plain bearings", "product",
      "IGLIDUR|IGUBAL|DRYLIN|IGUS BEARING|KUNSTSTOFFGLEITLAGER|KUNSTSTOF GLIJLAGER|PLASTIC BUSHING|"
      "PLASTIC BEARING|POLYMER BEARING|POLYMER BUSHING|POM BUSH|NYLON BUSH|GLEITLAGER KUNSTSTOFF|"
      "KUNSTSTOF GLIJLAGER|GLIJLAGER KUNSTSTOF|PLASTIC BUSH",
      codes=[R + r"(?:GFM|GSM|JFM|JSM|XFM|XSM|WFM|WSM|MFM|MSM|PSM|PFM|TSM|TFM|AFM|ASM|HSM|HFM|LFM|LSM|"
                 r"RSM|RFM|ZSM|ZFM|KSTM|EFOM|EGLM|KGLM|KGLM|EGFM|EGZM|EFSM|KBRM|WTM|J4FM|J4SM)-\d{3,4}-\d{2,3}" + E,
             R + r"(?:DRYLIN|IGUBAL|IGLIDUR|IGLIDUR[- ]?[A-Z]\d{0,3})" + E],
      roles={"bearing": "plastic_bearing", "bearing_housing": "plastic_bearing", "bushing": "plastic_bearing",
             "linear_guide": "plastic_bearing"}),
    T("coupling", "Couplings & brakes", "component",
      "COUPLING|COUPLINGS|KOPPELING|KOPPELINGEN|KUPPLUNG|*KUPPLUNG|JAW COUPLING|BELLOWS COUPLING|"
      "BEAM COUPLING|OLDHAM|OLDHAM COUPLING|DISC COUPLING|GEAR COUPLING|FLEXIBLE COUPLING|KLAUENKUPPLUNG|"
      "BALGKUPPLUNG|ROTEX|SPIDER|TANDKRANS|ZAHNKRANZ|SHRINK DISC|KRIMPSCHIJF|SCHRUMPFSCHEIBE|LOCKING ELEMENT|"
      "SPANNSATZ|KLEMBUS|TAPER BUSH|TAPERLOCK|TAPER LOCK|KEGELBUS|KONUSBUCHSE|CLAMPING HUB|TORQUE LIMITER|"
      "RUTSCHKUPPLUNG|SLIPKOPPELING|SAFETY COUPLING|BRAKE|BRAKES|REM|REMMEN|BREMSE|*BREMSE|DISC BRAKE|"
      "SCHIJFREM|SCHEIBENBREMSE|BRAKE DISC|REMSCHIJF|BREMSSCHEIBE|BRAKE CALIPER|REMKLAUW|BREMSZANGE|CLUTCH|"
      "UNIVERSAL JOINT|CARDAN|CARDANAS|KARDANWELLE|KARDANGELENK|KRUISKOPPELING|KREUZGELENK|DRIVESHAFT",
      codes=[R + r"(?:ROTEX|GERWAH|RADEX|BOWEX|TOOLFLEX|ROTEX GS|POLY NORM|N EUPEX|EUPEX|RUPEX|ARPEX|FLENDER|"
                 r"BIPEX)" + E,
             R + r"(?:CPU|CPS|CPE|MCO|MCOC|MCS|MCSC|SCPW|SCXW|MCGS|MCKS|MCSS|SCJ|SJC|XGT|XGS|MFC|MSTS|MOR|"
                 r"MCL|MCLC|MCGL|SFC|SFS|SRB|XHW|XBW)\d{2}[A-Z]{0,3}-\d",
             R + r"(?:SFC|SFS|SFF|SFM|SFH|CHP|ALS|XGL)-\d{3}",                                  # Miki Pulley
             # Misumi couplings with two bores: MCKL20-5-10, CPDW40-16-19, SCOC25-8-10; NBK MJC-30CS
             R + r"(?:MC[A-Z]{1,6}|CP[A-Z]{2,4}|SCOC)\d{2}-\d{1,2}(?:\.\d{1,2})?-\d{1,2}", R + r"MJC-\d{2}"]),
    T("gear", "Gears & sprockets", "component",
      "GEAR|GEARS|GEAR WHEEL|GEARWHEEL|SPUR GEAR|HELICAL GEAR|BEVEL GEAR|RING GEAR|PINION|RONDSEL|TANDWIEL|"
      "TANDWIELEN|*TANDWIEL|ZAHNRAD|*ZAHNRAD|ZAHNRAEDER|ZAHNRADER|STIRNRAD|KEGELRAD|*KEGELRAD|RITZEL|"
      "GEAR RACK|TOOTHED RACK|TANDHEUGEL|ZAHNSTANGE|*ZAHNSTANGE|WORM|WORM WHEEL|WORM GEAR|WORMWIEL|"
      "SCHNECKENRAD|SCHNECKE|SPROCKET|SPROCKETS|KETTINGWIEL|KETTINGWIELEN|KETTENRAD|*KETTENRAD|CHAIN WHEEL|"
      "IDLER SPROCKET|SPANNKETTENRAD|KETTENSPANNER|CHAIN TENSIONER|KETTINGSPANNER",
      codes=[R + r"(?:GEMSG|GEA[A-Z]{1,3}|GSS|GSSF|MSGA|MSGB|SSA|SSAY|SSY|SSG|SUS|SUW|KHG|"
                 r"KRG|SRFD|SRO|SRF)\d\.?\d?-\d{2,3}",                                   # KHK / Misumi gears
             R + r"(?:\d{2}B-[123]|ASA\s?\d{2,3}-?[123]?)\s?(?:Z|T)\s?\d{1,3}" + E,        # sprockets 08B-1 Z15
             R + r"SP(?:25|35|40|41|50|60|80)[AB]\d{2}",                                  # Misumi SP40B13
             ]),
    T("pulley", "Pulleys", "component",
      "PULLEY|PULLEYS|TIMING PULLEY|BELT PULLEY|IDLER|IDLER PULLEY|POELIE|POELIES|RIEMSCHIJF|RIEMSCHIJVEN|"
      "RIEMENSCHEIBE|ZAHNRIEMENSCHEIBE|ZAHNRIEMENRAD|*RIEMENSCHEIBE|TANDRIEMSCHIJF|TANDRIEMWIEL|"
      "SPANROL|SPANNROLLE|UMLENKROLLE|KEERROL|KEERWIEL|TENSION PULLEY|DEFLECTION PULLEY|V PULLEY|"
      "KEILRIEMENSCHEIBE|V SNAARSCHIJF",
      codes=[R + r"(?:HTPA|HTPB|HTPK|HTPT|HTPN|TPA|TPB|GPA|GPB|ATP|MTPA|MTPB|HTPAB|PBA|PBB|PTA|STPA|"
                 r"RTPA|TTPA|BTPA|GTPA|TTPB|HTPHK)\d{2,3}[A-Z]{1,4}\d{0,3}",
             R + r"(?:HTCPA|AHTFW?|HTPL|HTLA|MTPL)\d{2,3}-?[A-Z]"]),                                      # Misumi HTCPA40, AHTFW28
    T("chain", "Chains", "component",
      "CHAIN|CHAINS|KETTING|KETTINGEN|KETTE|KETTEN|*KETTE|ROLLER CHAIN|ROLLENKETTE|ROLKETTING|"
      "LIFTING CHAIN|HIJSKETTING|HEBEKETTE|ANCHOR CHAIN|ANKERKETTING|CONVEYOR CHAIN|TRANSPORTKETTING|"
      "FOERDERKETTE|FORDERKETTE|LEAF CHAIN|FLAT TOP CHAIN|CHAIN LINK|KETTINGSCHAKEL|KETTENGLIED|LINK",
      codes=[R + r"(?:\d{2}B|ASA\s?\d{2,3})-[123]" + E, R + r"(?:RS|RF)\d{2,3}-\d" + E]),
    T("belt", "Belts", "component",
      "BELT|BELTS|TIMING BELT|TOOTHED BELT|TANDRIEM|TANDRIEMEN|ZAHNRIEMEN|*RIEMEN|*RIEM|RIEM|RIEMEN|"
      "V BELT|VBELT|V SNAAR|SNAAR|KEILRIEMEN|FLAT BELT|PLATTE RIEM|FLACHRIEMEN|POLY V|CONVEYOR BELT|"
      "TRANSPORTBAND|TRANSPORTBANDEN|FOERDERBAND|FORDERBAND|FOERDERGURT|BAND|BANDEN|GURT|*GURT|BELTING|"
      "MODULAR BELT|MATTOP|MAT TOP|ROUND BELT|RONDSNAAR|RUNDRIEMEN",
      codes=[R + r"\d{3,5}\s?-?\s?(?:[2358]M|14M|XL|AT\d{1,2}|T\d{1,2})\s?-?\s?\d{1,3}" + E,  # 1200-8M-30
             R + r"(?:HTD|GT2|GT3|GT5|RPP|STD)\s?-?\d{3,5}",
             R + r"(?:SPZ|SPA|SPB|SPC|XPZ|XPA|XPB|XPC)\s?\d{3,5}(?:\s?(?:LW|LD|LI|LA|MM))?" + E,
             R + r"HTBN\d{3,4}[A-Z]{0,2}\d?M"]),                                          # Misumi HTBN1350S5M-250
    T("spring", "Springs", "component",
      "SPRING|SPRINGS|COMPRESSION SPRING|TENSION SPRING|EXTENSION SPRING|TORSION SPRING|VEER|VEREN|*VEER|"
      "DRUKVEER|TREKVEER|TORSIEVEER|SCHROEFVEER|FEDER|FEDERN|*FEDER|DRUCKFEDER|ZUGFEDER|SCHENKELFEDER|"
      "SPIRALFEDER|SCHRAUBENFEDER|COIL SPRING|LEAF SPRING|BLADVEER|BLATTFEDER|WAVE SPRING|GOLFVEER|WELLFEDER|"
      "DIE SPRING|MATRIJSVEER|BEDEPEER|SPRING STEEL|VERENSTAAL|FEDERSTAHL",
      codes=[R + r"(?:SWF|SWM|SWL|SWH|SWB|AWF|AWM|AWL|AWH|AWB|SWR|SWY|SWU|UL|UF|UM|UH|UB|WF|WM|WL|WH|WB|WR|"
                 r"WY)\d{1,2}-\d{2,3}" + E,                                          # Misumi die springs
             R + r"(?:LC|LE|LS|LP|LT|LG|LSR|CI|CIV)\s?\d{3}[A-Z]\s?\d{2}" + E]),     # Lee Spring
    T("seal", "Seals & O-rings", "component",
      "SEAL|SEALS|SEALING|*SEAL|SEALRING|SEAL RING|SEALING RING|SEAL KIT|O RING|ORING|ORINGS|O RINGS|OR RING|"
      "QUAD RING|QUADRING|X RING|XRING|V RING|VRING|BACKUP RING|BACK UP RING|STEUNRING|STUETZRING|STUTZRING|"
      "GASKET|GASKETS|GASCKET|GASKIT|GASKETT|PAKKING|PAKKINGEN|*PAKKING|DICHTING|DICHTINGEN|*DICHTING|"
      "AFDICHTING|AFDICHTRING|DICHTRING|*DICHTRING|DICHTUNG|DICHTUNGEN|*DICHTUNG|DICHTUNGSRING|"
      "FLACHDICHTUNG|PROFILDICHTUNG|WIPER|WIPERS|WIPER RING|SCRAPER|SCRAPER RING|ABSTREIFER|*ABSTREIFER|"
      "AFSTREPER|SCHRAPER|SCHRAAPRING|LIP SEAL|LIPSEAL|SHAFT SEAL|OIL SEAL|OILSEAL|ROTARY SEAL|RADIAL SEAL|"
      "SIMMERRING|*SIMMERRING|KEERRING|KEERRINGEN|ASAFDICHTING|WELLENDICHTRING|RADIALWELLENDICHTRING|"
      "ROD SEAL|PISTON SEAL|STANGENDICHTUNG|KOLBENDICHTUNG|ZUIGERAFDICHTING|STANGAFDICHTING|GUIDE RING|"
      "WEAR RING|GLEITRING|FUEHRUNGSRING|PACKING|PACKINGS|GLAND PACKING|PAKKINGBUS|DOOR SEAL|DEURRUBBER|"
      "DOOR GASKET|EDGE SEAL|SEALING STRIP|AFDICHTSTRIP|DICHTPROFIL|DICHTSTREIFEN|SEALING PROFILE|TOCHTSTRIP|"
      "BELLOWS SEAL|LABYRINTH|LABYRINTHDICHTUNG|MECHANICAL SEAL|GLIJRINGAFDICHTING|GLEITRINGDICHTUNG",
      codes=[R + r"O-?RING\s?\d", R + r"OR\s?\d{1,3}(?:[.,]\d{1,2})?\s?X\s?\d", R + r"(?:BA|BASL|BAU|BABSL|WA|WAS)"
             r"\s?\d{1,3}\s?X\s?\d{1,3}\s?X\s?\d{1,2}" + E,
             R + r"(?:HMSA|HMS|CRWA|CRWH|CRW|HDW)\d{1,2}" + E]),
    T("rubber", "Rubber parts", "component",
      "RUBBER BUFFER|BUFFER|BUFFERS|BUMPER|BUMPERS|BUMP STOP|STOP RUBBER|RUBBER STOP|AANSLAGRUBBER|"
      "ANSCHLAGPUFFER|PUFFER|*PUFFER|GUMMIPUFFER|RUBBER MOUNT|RUBBERMOUNT|RUBBER FOOT|RUBBERVOET|GUMMIFUSS|"
      "VIBRATION MOUNT|VIBRATION DAMPER|ANTI VIBRATION|TRILLINGSDEMPER|SCHWINGMETALL|SCHWINGUNGSDAEMPFER|"
      "SILENTBLOC|SILENT BLOCK|SILENTBLOK|RUBBER BUSH|RUBBERBUS|GROMMET|GROMMETS|DOORVOERRUBBER|"
      "KABELDOORVOER|KABELTUELLE|KABELTULLE|DURCHFUEHRUNGSTUELLE|EDGE PROTECTION|EDGE PROTECTOR|EDGE TRIM|"
      "KANTBESCHERMING|KANTENSCHUTZ|KANTENSCHUTZPROFIL|KEDER|BELLOWS|BALG|*BALG|FALTENBALG|VOUWBALG|"
      "HARMONICABALG|GAITER|BOOT|STOFHOES|SCHUTZBALG|RUBBER STRIP|RUBBERSTRIP|GUMMISTREIFEN|RUBBER SHEET|"
      "RUBBERMAT|GUMMIMATTE|RUBBER MAT|FENDER|FENDERS|STOOTRUBBER|STOOTBUFFER|STOSSPUFFER|BRUSH|BRUSHES|"
      "BORSTEL|BORSTELS|BUERSTE|BURSTE|BUERSTENLEISTE|BRUSH STRIP|BORSTELSTRIP|DEFLECTOR RUBBER",
      codes=[R + r"(?:AXFH|CXF|AAFS)-?[A-Z]?\d", R + r"(?:USBYS|UPWH|USLH)\d{1,2}(?:-|$)"]),                 # Misumi urethane bumpers

    # ---- electrical -------------------------------------------------------------------------------
    T("cable", "Cables", "component",
      "CABLE|CABLES|KABEL|KABELS|*KABEL|WIRE|WIRES|DRAAD|LITZE|ADER|WIRING|BEDRADING|VERDRAHTUNG|HARNESS|"
      "WIRE HARNESS|KABELBOOM|KABELBAUM|CORD|SNOER|LEITUNG|*LEITUNG|STEUERLEITUNG|POWER CABLE|SERVO CABLE|"
      "MOTOR CABLE|SENSOR CABLE|SIGNAL CABLE|ENCODER CABLE|PATCH CABLE|ETHERNET CABLE|NETWORK CABLE|"
      "CONNECTION CABLE|AANSLUITKABEL|ANSCHLUSSKABEL|ANSCHLUSSLEITUNG|EXTENSION CABLE|VERLENGKABEL|"
      "VERLAENGERUNGSKABEL|CHAINFLEX|OELFLEX|OLFLEX|UNITRONIC|TRAILING CABLE|SLEEPKABEL|FLEX CABLE|"
      "CABLE TIE|CABLE TIES|TIE WRAP|TIEWRAP|TYRAP|TY RAP|KABELBINDER|BINDBAND|BUNDELBANDJE|EARTH WIRE|"
      "AARDDRAAD|ERDUNGSKABEL|GROUND STRAP|AARDINGSBAND|BUSBAR|BUS BAR|RAILS COPPER|STROMSCHIENE|KOPERRAIL",
      codes=[R + r"(?:CF\d{1,3}\.\d{2}\.\d{2}|CFBUS|CFROBOT\d?|CFSPECIAL)" + E,              # igus chainflex
             R + r"(?:EVC|EVF|EVT)\d{3,4}" + E, R + r"E1\d{4}" + E,                                 # ifm
             R + r"(?:YF2A|YG2A|YM2A|YF2B|YG2B)\d{2}-\d{3}", R + r"(?:DOL|DSL|STL|STE)-\d{4}",    # Sick
             R + r"(?:\d{1,2}G\d{1,3}(?:[.,]\d{1,2})?|\d{1,2}\s?X\s?\d{1,3}(?:[.,]\d{1,2})?\s?MM2)" + E,  # 4G1.5
             R + r"(?:6XV|6ES7\s?901|6FX\d{4})-?\d", R + r"(?:TRVVP|AVVR)-\d"]),            # Misumi cables
    T("cable_chain", "Cable chains", "product",
      "CABLE CHAIN|CABLECHAIN|ENERGY CHAIN|ENERGYCHAIN|E CHAIN|ECHAIN|DRAG CHAIN|DRAGCHAIN|CABLE CARRIER|"
      "CABLE TRACK|ENERGIEKETTE|ENERGIEFUEHRUNGSKETTE|SCHLEPPKETTE|KABELSCHLEPP|KABELSLEPKETTING|"
      "SLEPKETTING|ENERGIEKETTING|KABELRUPS|RUPSKETTING|TRIFLEX|ZIPPER|READYCHAIN|E KETTE|EKETTE|TRAXLINE|"
      "MICROFLIZZ|E SPOOL|E TUBE|ETUBE",
      codes=[R + r"E[2346]\.?\d{1,3}\.\d{2,3}(?:\.\d{2,3})?(?:\.\d)?" + E, R + r"E[2346]/\d{3}",
             R + r"(?:B|Z|TRE|TRC|TRL|E2C|E2K)\d{2,3}\.\d{2,3}(?:\.\d{2,4})?" + E,
             R + r"(?:UNIFLEX|QUANTUM|PROTUM|MICROTRAX|EASYTRAX|TKP|TKR|TKHD)\s?\d{2,4}",       # Kabelschlepp
             R + r"IGUS[_ -]?\d{2,4}\.\d{2}\.\d{2,3}",                                       # igus 2400.05.075
             R + r"(?:MPU|MSU)\d{2}-\d{2}-\d{2}"],                                             # Misumi C-MPU10-10-18
      absorb="all"),
    T("cable_gland", "Cable glands", "component",
      "CABLE GLAND|CABLEGLAND|GLAND|GLANDS|WARTEL|WARTELS|KABELWARTEL|KABELVERSCHRAUBUNG|*KABELVERSCHRAUBUNG|"
      "SKINTOP|CABLE ENTRY|KABELEINFUEHRUNG|KABELEINFUHRUNG|CABLE ENTRY PLATE|KDL|KEL|CABLE FEEDTHROUGH",
      codes=[R + r"(?:PG|M)\s?\d{1,2}(?:X1[.,]5)?\s?(?:GLAND|WARTEL|SKINTOP|MS|KV)",
             R + r"SKINTOP" + E, R + r"(?:KEL|KDL|KDP|KEL-ER|KEL-DP|KEL-U|KEL-QUICK)\s?\d{1,2}" + E]),
    T("wiring_duct", "Wiring ducts", "component",
      "WIRING DUCT|WIRE DUCT|CABLE DUCT|KABELGOOT|KABELGOTEN|BEDRADINGSGOOT|VERDRAHTUNGSKANAL|KABELKANAL|"
      "*KABELKANAL|LEITUNGSKANAL|SLOTTED DUCT|PANDUIT|TRUNKING|INSTALLATIEKANAAL|CONDUIT|BEDRADINGSKOKER|KABELKOKER|VERDRAHTUNGSKOKER"),
    T("cable_tray", "Cable trays & DIN rails", "component",
      "CABLE TRAY|CABLE LADDER|KABELBAAN|KABELBANEN|KABELLADDER|KABELRINNE|KABELPRITSCHE|KABELTRAY|WIRE TRAY|"
      "GITTERRINNE|DIN RAIL|DINRAIL|TOP HAT RAIL|MONTAGERAIL|MONTAGESCHIENE|TRAGSCHIENE|HUTSCHIENE|C RAIL|"
      "CRAIL|G RAIL|STRUT CHANNEL|UNISTRUT|INSTALLATIONSSCHIENE|MOUNTING RAIL",
      codes=[R + r"(?:TS|NS)\s?35(?:/7[.,]5|/15|X7[.,]5|X15)?" + E]),
    T("sensor", "Sensors & switches", "product",
      "SENSOR|SENSORS|SENSOREN|*SENSOR|PROXIMITY|PROXIMITY SENSOR|PROXIMITY SWITCH|PROX|INDUCTIVE|INDUKTIV|"
      "INDUCTIEF|INDUCTIEVE|CAPACITIVE|KAPAZITIV|CAPACITIEF|PHOTOELECTRIC|PHOTO SENSOR|PHOTOCELL|FOTOCEL|"
      "LICHTSCHRANKE|*LICHTSCHRANKE|LIGHT BARRIER|REFLEX SENSOR|REFLECTOR|REFLEKTOR|LIMIT SWITCH|LIMITSWITCH|"
      "EINDSCHAKELAAR|ENDSCHALTER|*ENDSCHALTER|POSITIONSSCHALTER|REED SWITCH|REEDSCHAKELAAR|REEDSCHALTER|"
      "CYLINDER SWITCH|AUTO SWITCH|AUTOSWITCH|SAFETY SWITCH|VEILIGHEIDSSCHAKELAAR|SICHERHEITSSCHALTER|"
      "INTERLOCK|DOOR SWITCH|DEURSCHAKELAAR|TUERSCHALTER|TURSCHALTER|*SCHALTER|SCHAKELAAR|*SCHAKELAAR|"
      "SWITCH|SWITCHES|MICROSWITCH|MICRO SWITCH|MIKROSCHALTER|ENCODER|ENCODERS|DREHGEBER|DRAAIGEVER|"
      "RESOLVER|PRESSURE SWITCH|DRUKSCHAKELAAR|DRUCKSCHALTER|PRESSURE SENSOR|DRUKSENSOR|DRUCKSENSOR|"
      "PRESSURE TRANSMITTER|DRUCKTRANSMITTER|LEVEL SENSOR|LEVEL SWITCH|NIVEAUSCHAKELAAR|NIVEAUSCHALTER|"
      "FLOW SENSOR|FLOW SWITCH|FLOWSENSOR|STROEMUNGSSCHALTER|TEMPERATURE SENSOR|TEMPERATUURSENSOR|PT100|"
      "THERMOCOUPLE|THERMOKOPPEL|CAMERA|CAMERAS|KAMERA|VISION|VISION SENSOR|SCANNER|LASER SCANNER|LASERSCANNER|"
      "BARCODE|BARCODE READER|BARCODESCANNER|RFID|RFID READER|LIGHT CURTAIN|LIGHTCURTAIN|LICHTSCHERM|"
      "LICHTGITTER|LICHTVORHANG|SAFETY LIGHT CURTAIN|LIGHT GRID|INITIATOR|NAEHERUNGSSCHALTER|NAHERUNGSSCHALTER|"
      "BENADERINGSSCHAKELAAR|DISTANCE SENSOR|AFSTANDSSENSOR|ABSTANDSSENSOR|LASER SENSOR|LASERSENSOR|"
      "ULTRASONIC|ULTRASOON|ULTRASCHALL|LOAD CELL|LOADCELL|WEEGCEL|WAEGEZELLE|WAGEZELLE|KRACHTOPNEMER|"
      "STRAIN GAUGE|GAUGE|GAUGES|MANOMETER|PRESSURE GAUGE|DRUKMETER|THERMOMETER|INCLINOMETER|HELLINGMETER|"
      "NEIGUNGSSENSOR|TILT SENSOR|ACCELEROMETER|VIBRATION SENSOR|SAFETY MAT|SCHAKELMAT|SCHALTMATTE|"
      "SAFETY EDGE|SCHAKELLIJST|SCHALTLEISTE|RADAR|LIDAR|MAGNETIC SWITCH|MAGNETSCHALTER|COLOUR SENSOR|"
      "COLOR SENSOR|KLEURENSENSOR|FARBSENSOR|FIBRE OPTIC|FIBER OPTIC|LICHTLEITER|LOAD PIN|LOADPIN|LASTMESSBOLZEN|KRACHTMEETPEN|LOAD SHACKLE|LOAD LINK|"
      "TENSIOMETER|CABLE TENSION METER",
      codes=[R + r"(?:IF|IG|IE|II|IM|KG|KI|KQ|MK|PN|PI|SA|SI|SU|TN|LR|LMT|VSE|VSA)\d{4}" + E,     # ifm
             R + r"I[FGEIM][A-Z]\d{4}-[A-Z]{2,5}",                                               # ifm IGA3008-BPKG
             R + r"(?:IFS|IFT|IGS|IGT|IGC|IFC|IEC|IIS|IIT|MFS|MFT|MGS|O[1-8]D|O[4-8]H|OGP|OGH|OGT|OGS|OID|RVP)"
                 r"\d{3}" + E,
             R + r"(?:IME|IMF|IMB|IMI|IMS|IQ|IQB|IQG|MZT|MZC|RZT|RZC|WTB|WTT|WTS|WTF|WTL|WTE|WLL|WLG|WSE|GTB|"
                 r"GTE|GSE|GRTB|GRL|GRSE|VTB|VTE|VTF|KTM|KTS|CSM|UM30|UC30|DT20|DT35|DT50|DL50|DX35|DFS|DFV|DBS|"
                 r"AFS|AFM|AHS|AHM|ARS|SRS|SRM|SKS|SKM|TIM|LMS|MRS|S300|S3000|C2000|C4000|M4000|DELTAC|"
                 r"MICROSCAN|RE11|RE13|RE27|RE300|STR1|TR4|TR10|TR110|FLOWSIC|PBS|LFP|LFH|LFV|CLV|LECTOR|"
                 r"INSPECTOR|PICO)\d{0,4}[A-Z]?-[0-9A-Z]{2,}",                                   # Sick
             R + r"(?:BES|BOS|BKT|BMF|BTL|BIS|BCS|BAW|BLE|BLS|BOD|BNI|BCC|BHS|BSI|BSE|BSP|BFB)\s?-?"
                 r"(?:\d{2}|[A-Z]\d{2})",                                                         # Balluff
             R + r"(?:NBB|NBN|NJ|NCB|NCN|NEB|NMB|OBT|OBE|OBD|OBS|OBG|OBR|OBK|OMH|OMT|UB|UC|UDC|VDM|OCV|OMD|"
                 r"PMI|IQT|IUT|IVM|ENI|ENA|RVI|RHI|PGV|PCV|NRB|NRN)\d{1,4}[A-Z0-9.,-]*",          # Pepperl+Fuchs
             R + r"(?:LR-[A-Z]{1,2}\d|PZ-[A-Z]\d|PZ2-|FS-N\d|FS-V|FU-\d|IL-\d{3}|IL-S\d|GT2-|IV-|IV2-|IV3-|"
                 r"SR-\d{3,4}|BL-\d{3,4}|LV-N\d|LV-S\d|LV-H|CZ-V|GV-|LK-G|LJ-|CV-X|XG-|AP-V|EM-\d{3}|EV-\d{3}|"
                 r"PR-[A-Z]\d|PJ-|SZ-V|SL-V|GL-R|OP-\d{5})",                                     # Keyence
             R + r"(?:E2E|E2B|E2A|E2EQ|E2EW|E2FM|E3Z|E3FA|E3FB|E3FC|E3S|E3T|E3X|E3NX|E3JK|E3JM|E3H2|E32|E6B2|"
                 r"E6C3|E6F|E6H|D4N|D4NS|D4NL|D4B|D4C|D4E|D4SL|D2SW|D2VW|D5B|D40A|D40Z|F3SG|F3SJ|F3SN|F3ET|"
                 r"F39|E5CC|E52|D2F|D2FC|D3V|E3NC)-[A-Z0-9]",                                        # Omron
             R + r"(?:AZM\s?\d{3}|BNS\s?\d{2,3}|RSS\s?\d{2,3}|PSEN|CES-|CET-|CEM-|MGB-|STP\d|STM\d|"
                 r"SRB\s?\d{3}|TESZ|MAZ\s?\d{2})",                                              # safety switches
             R + r"D-(?:M9|A9|F9|Y5|Y6|Y7|Z7|Z8|J7|J5|J79|G5|K5|B5|B6|C7|C8|H7|M5|P3|P4|P5|R7|S7|T7|F7|F8|A7|A8|"
                 r"A5|A6|E7|E8|G39|K39|A3|A4|A44|A59|A79|A93|A96|A90|M9B|M9N|M9P|Y59|Y69|Z73|Z76)",  # SMC switches
             R + r"(?:SME|SMT|SMEO|SMTO|SIEN|SIES|SIED|SIEF|SIEH|SDBT|SDAT|SPAN|SPAB|SPAU|SDE|SDE1|SDE3|SDE5|"
                 r"SPTE|SPTW|SOEG|SOEC|SOOE|SFAB|SFAM|SFAH|SRBC|SRBP|SDAP|SMH)-\d",       # Festo sensors
             R + r"(?:BI|NI|BIM|BC|NC)\d{1,2}U?-[A-Z]",                                           # Turck
             R + r"(?:Q4X|QS18|QS30|LE550|LE250|MINIBEAM|WORLD-BEAM|EZ-SCREEN|DF-G|SM30|LTF|L-GAGE|U-GAGE|"
                 r"IVU|PRESENCEPLUS)",                                                              # Banner
             R + r"(?:6DR|7ME|7MF|7ML|7MH|3SE|3SE5|3SE6|3SE7|6GK7|6GF|6GT)\d"],          # Siemens sensors
      absorb="all"),
    T("motor", "Motors & gearboxes", "product",
      "MOTOR|MOTORS|MOTOREN|*MOTOR|ELECTRIC MOTOR|ELECTROMOTOR|ELEKTROMOTOR|SERVO|SERVOMOTOR|SERVO MOTOR|"
      "STEPPER|STEPPER MOTOR|STAPPENMOTOR|SCHRITTMOTOR|GEARMOTOR|GEAR MOTOR|GEARED MOTOR|GETRIEBEMOTOR|"
      "MOTOREDUCTOR|MOTORREDUCTOR|GEARBOX|GEARBOXES|GEAR BOX|REDUCER|REDUCTOR|REDUCTOREN|*REDUCTOR|"
      "TANDWIELKAST|VERTRAGINGSKAST|GETRIEBE|*GETRIEBE|PLANETARY GEARBOX|PLANETARY|PLANETENGETRIEBE|"
      "PLANETAIRE|WORM GEARBOX|SCHNECKENGETRIEBE|WORMWIELKAST|BEVEL GEARBOX|KEGELRADGETRIEBE|ANGLE GEARBOX|"
      "HAAKSE OVERBRENGING|WINKELGETRIEBE|DRIVE UNIT|AANDRIJFEENHEID|ANTRIEBSEINHEIT|DIRECT DRIVE|"
      "TORQUE MOTOR|LINEAR MOTOR|LINEAIRMOTOR|LINEARMOTOR|SPINDLE MOTOR|SPINDELMOTOR|ELECTROSPINDLE|"
      "ELEKTROSPINDEL|DRUM MOTOR|TROMMELMOTOR|WINCH MOTOR|ACTUATOR MOTOR|BRAKE MOTOR|REMMOTOR|BREMSMOTOR|"
      "FAN MOTOR|VIBRATOR|UNBALANCE MOTOR|TRILMOTOR|UNWUCHTMOTOR|HARMONIC DRIVE|CYCLOID|CYCLO|RV REDUCER",
      codes=[R + r"(?:1FK7|1FK2|1FT7|1FT2|1LE1|1LE5|1LA7|1LA9|1PH8|1PH1|1FL6|1FW6|1FN3|1FE1|1LG6|2KJ\d|1FK)"
             r"\d{0,3}-?",                                                                # Siemens / Flender
             R + r"(?:R|RF|RX|RXF|RM|F|FF|FA|FAF|FH|K|KF|KA|KAF|KH|KT|S|SF|SA|SAF|W|WF|WA|WAF)\d{2,3}[A-Z]{0,2}\s?"
                 r"(?:DR[NSEM]?|DT|DV|DRN|DRS|DRE|DRP|CMP|CM|CMPZ|EDR|MOVIMOT|DRL)\s?\d{2,3}",  # SEW gear motors
             R + r"(?:DRN|DRS|DRE|DRP|DRL|DRM|CMP|CMPZ|CFM|EDR|EDRN|MGF|MOVIGEAR)\d{2,3}[A-Z]{0,2}\d?" + E,
             R + r"(?:MSK|MSM|MS2N|MAD|MAF|MKE|MSE|MS2E|MBT|MBS|MAP|MSN|MCL|MLF|MKD|MHD|MDD|MAC)\d{3}[A-Z]" + E,
             R + r"(?:AM8\d{3}|AM3\d{3}|AM2\d{3}|AM31\d{2}|AM81\d{2}|AA3\d{3}|AL2\d{3}|AL8\d{3}|AS1\d{3}|AS2\d{3}|"
                 r"AG2\d{3}|AG3\d{3})" + E,                                              # Beckhoff
             R + r"(?:MCS|MCA|MQA|MDFMA|MDFQA|MCM|MDSKS|MDXMA|GST|GSS|GFL|GKR|GKS)\s?\d{2,3}",      # Lenze
             R + r"(?:SGM7|SGMG|SGMJ|SGMAV|SGMGV|SGMJV|SGMAS|HG-KR|HG-SR|HG-MR|HG-JR|HF-KP|HF-SP|HF-KN|"
                 r"HC-SFS|HC-KFS|R88M|R88MK|AKM|MPL|MPM|VPL|VPC|MPAR|BMH|BSH|SH3|EMMT|EMME|EMMS|EMMB|"
                 r"MTR-DCI|ECMA|ECMC)[A-Z0-9]{0,2}[- ]?[A-Z0-9]{2,}",                         # servo motors
             R + r"(?:PLE|PLN|PLFE|PLFN|PLPE|PLQE|PLHE|WPLE|WPLN|WGN|WPLPE|PLS|PSN|PSBN|PSFN)\s?\d{2,3}" + E,
             R + r"(?:SP|TP|LP|LPB|SPK|XP|RP|SPC|TPC|HG)\+\s?\d{3}" + E,                    # Wittenstein
             R + r"(?:LP|NP|NPR|NPL|NPS|NPT|NPLK|NPRK)\s?0\d{2}" + E,                         # planetary gearboxes
             R + r"NEMA\s?\d{2}" + E, R + r"(?:\d{2}HS|\d{2}HD|\d{2}HM|\d{2}HY|\d{2}BYGH|\d{2}STH|\d{2}CM)\d{2,4}",
             ],
      absorb="all"),
    T("enclosure", "Electrical enclosures", "product",
      "ENCLOSURE|ENCLOSURES|ELECTRICAL ENCLOSURE|CABINET|CONTROL CABINET|ELECTRICAL CABINET|ELECTRICAL BOX|"
      "SWITCH CABINET|SCHAKELKAST|SCHAKELKASTEN|SCHALTSCHRANK|*SCHALTSCHRANK|SCHALTKASTEN|STEUERSCHRANK|"
      "CONTROL BOX|CONTROLBOX|BEDIENKAST|BEDIENKASTEN|BEDIENGEHAEUSE|BEDIENGEHAUSE|JUNCTION BOX|"
      "TERMINAL BOX|AANSLUITKAST|AANSLUITDOOS|KLEMMENKASTEN|KLEMKAST|KLEMMENDOSE|VERDEELKAST|VERTEILERKASTEN|"
      "VERTEILERSCHRANK|LASDOOS|ABZWEIGDOSE|ENCLOSURE DOOR|COMPACT ENCLOSURE|KOMPAKTGEHAEUSE|WALL BOX|"
      "PUSHBUTTON BOX|DRUKKNOPKAST|PENDANT STATION|BEDIENSTATION|OPERATOR STATION|CONTROL DESK|"
      "BEDIENPULT|LESSENAAR|CONSOLE BOX|MCC|SWITCHBOARD|SCHAKELBORD",
      codes=[R + r"(?:AE|AX|KL|KX|KE|EB|BG|TS|TS8|VX|VX25|SE|SE8|CM|CP|DK|SZ|SV|TE|TE8|CS|IW)\s?\d{4}\.\d{3}"
             + E,                                                                          # Rittal AE 1060.500
             R + r"(?:RITTAL|FIBOX|SPELSBERG|HAMMOND|BOPLA|ELDON|SAREL|ENSTO|EUROMAS|POLYCASE|ROLEC)" + E],
      absorb="shape"),
    T("electrical", "Electrical components", "product",
      "PLC|PLCS|CPU MODULE|IO MODULE|I O MODULE|IO BLOCK|IO LINK|IOLINK|IO LINK MASTER|REMOTE IO|BUS COUPLER|"
      "BUSKOPPLER|BUSKOPPELAAR|FIELDBUS|PROFINET|ETHERCAT|TERMINAL BLOCK|TERMINAL BLOCKS|TERMINAL|TERMINALS|"
      "KLEMMEN|KLEMME|*KLEMME|REIHENKLEMME|RIJGKLEM|RIJGKLEMMEN|AANSLUITKLEM|RELAY|RELAYS|RELAIS|SAFETY RELAY|"
      "VEILIGHEIDSRELAIS|SICHERHEITSRELAIS|CONTACTOR|CONTACTORS|MAGNEETSCHAKELAAR|SCHUETZ|SCHUTZE|"
      "*SCHUETZ|CIRCUIT BREAKER|BREAKER|MCB|RCD|AUTOMAAT|INSTALLATIEAUTOMAAT|LEITUNGSSCHUTZSCHALTER|"
      "MOTOR PROTECTION|MOTORBEVEILIGING|MOTORSCHUTZSCHALTER|MOTOR STARTER|MOTORSTARTER|SOFTSTARTER|"
      "POWER SUPPLY|POWERSUPPLY|PSU|VOEDING|VOEDINGEN|NETZTEIL|NETZGERAET|STROMVERSORGUNG|TRANSFORMER|"
      "TRAFO|TRANSFORMATOR|INVERTER|FREQUENCY INVERTER|FREQUENCY CONVERTER|FREQUENTIEREGELAAR|"
      "FREQUENZUMRICHTER|UMRICHTER|*UMRICHTER|VFD|SERVO DRIVE|SERVODRIVE|SERVO AMPLIFIER|SERVOVERSTAERKER|"
      "SERVOREGELAAR|SERVOREGLER|DRIVE CONTROLLER|MOTION CONTROLLER|CONTROLLER|CONTROLLERS|STEUERUNG|"
      "BESTURING|HMI|HMI PANEL|HMI SCREEN|TOUCH PANEL|TOUCHPANEL|TOUCHSCREEN|TOUCH SCREEN|OPERATOR PANEL|BEDIENPANEEL|BEDIENPANEL|"
      "DISPLAY|DISPLAYS|BEELDSCHERM|MONITOR|MONITORS|INDUSTRIAL PC|IPC|PANEL PC|KEYBOARD|TOETSENBORD|"
      "TASTATUR|MOUSE|ROUTER|ETHERNET SWITCH|NETWORK SWITCH|NETWERKSWITCH|MODEM|ANTENNA|ANTENNE|"
      "CONNECTOR|CONNECTORS|CONNECTOREN|STEKKER|STEKKERS|STECKER|*STECKER|PLUG|PLUGS|SOCKET|SOCKETS|"
      "CONTACTDOOS|WANDCONTACTDOOS|STECKDOSE|*STECKDOSE|HARTING|HAN|M12 CONNECTOR|M8 CONNECTOR|"
      "FUSE|FUSES|ZEKERING|ZEKERINGEN|SICHERUNG|FUSE HOLDER|ZEKERINGHOUDER|MAIN SWITCH|HOOFDSCHAKELAAR|"
      "HAUPTSCHALTER|ISOLATOR|ISOLATOR SWITCH|WERKSCHAKELAAR|REPARATURSCHALTER|LASTTRENNSCHALTER|"
      "BATTERY|BATTERIES|ACCU|ACCUMULATEUR|AKKU|UPS|FAN|FANS|VENTILATOR|VENTILATOREN|LUEFTER|LUFTER|"
      "FILTER FAN|FILTERLUEFTER|COOLING UNIT|KOELUNIT|KUEHLGERAET|AIRCO|AIR CONDITIONER|HEATER|VERWARMING|"
      "HEIZUNG|THERMOSTAT|HYGROSTAT|SLIP RING|SLIPRING|SLEEPRING|SCHLEIFRING|ROTARY JOINT|DRAAIDOORVOER|"
      "DREHDURCHFUEHRUNG|SPEAKER|LUIDSPREKER|LAUTSPRECHER|HORN|HOORN|BUZZER|ZOEMER|SUMMER|SIRENE|SIREN|"
      "PCB|PRINTPLAAT|LEITERPLATTE|ELECTRONICS|ELEKTRONIK|ELEKTRONICA|SAFETY CONTROLLER|SAFETY PLC|"
      "ENERGY METER|KWH METER|ENERGIEZAEHLER|CURRENT TRANSFORMER|STROOMTRAFO|STROMWANDLER|SURGE PROTECTION|"
      "OVERSPANNINGSBEVEILIGING|UEBERSPANNUNGSSCHUTZ|RECTIFIER|GELIJKRICHTER|GLEICHRICHTER|CHARGER|LADER|"
      "LADEGERAET",
      codes=[R + r"(?:6ES7|6EP|6EP1|6EP3|6SL3|6SE6|6AV2|6AV6|6AG1|6GK5|6GK1|3RT|3RV|3RH|3RW|3RF|3RB|3RA|3RK|"
                 r"3TK|3SK|3RS|3RP|3RQ|3VA|3VL|3VM|3KD|3KA|3LD|3NA|3NW|3NP|5SY|5SL|5SV|5SM|5ST|8WA|8WH|8US|"
                 r"7KM|7KT|7SR|6SL|6SN)\s?\d",                                         # Siemens
             R + r"(?:EL|EK|EP|EPP|KL|BK|BC|BX|CX|CP|CU|AX|ELM|ELX|EPX)\d{4}(?:-\d{4})?" + E,    # Beckhoff
             R + r"(?:750|753|2002|2004|221|222|224|787|788|789|857|858|859|280|281|282|283|284|285|2273)"
                 r"-\d{3,4}" + E,                                                                   # Wago
             R + r"(?:UT|UK|UKK|USLKG|PTFIX|PTTB|STTB|UKKB|URTK|PTIO|MSTB|MCVR|PTV|UTTB|QTC|PTRV|D-ST|D-UT|"
                 r"D-PT|SB-ST)\s?\d",
             R + r"(?:QUINT\d?|TRIO|STEP|UNO|MINI)-PS", R + r"(?:PLC-R|PLC-O|PSR-|REL-|MACX|CONTACTRON)",  # Phoenix
             R + r"(?:LC1D|LC1F|LP1|LAD|LRD|LR2|GV2|GV3|GV4|GV7|ATV|LXM|TM221|TM241|TM251|TM262|BMX|BMEP|XPSU|"
                 r"RXM|RXG|RM22|RM35|RE22|A9F|A9N|A9R|A9L|A9K|NSX|IC60|VW3|HMIG|HMIST|HMIGTO|HMIS|HMIP|HMIDT|"
                 r"XUB|XUK|XUM|XUY|XUX|XUZ|XUE|XUF|XMLB|XMLR|TSX)(?=[A-Z]{0,3}\d)[A-Z0-9]{1,8}" + E,  # Schneider
             R + r"(?:PNOZ|PNOZMULTI|PSS|PITM|PITGATE|PDP|PSWZ|PMCPROTEGO|PSSU|PZE|PZEX|S1EN|S1UM|S1SW)"
                 r"\s?[A-Z0-9]",                                                                    # Pilz
             R + r"(?:WDU|WPE|ZDU|ZPE|WDK|ZDK|WTR|ZTR|WAP|ZAP|WQV|ZQV|SAK|SAKDU|WTL|WFF|A2C|A4C|ACT20|DRM|MCZ)"
                 r"\s?\d",                                                                         # Weidmuller
             R + r"(?:HAN-MODULAR|HAN-E|HAN-Q|HAN-K|HAN-D|HAN-B|HAN-EEE|HAN-COM|HAN-YELLOCK)" + E,
             R + r"HAN\s?\d{1,2}\s?[A-Z]{0,2}" + E,                                               # Harting
             R + r"(?:S200|S201|S202|S203|S204|F200|F202|F204|DS201|DS202|MS116|MS132|MS165|MO132|MO165|"
                 r"ACS\d{3}|PSTX|AC500|TMAX|EMAX|1SVR|1SAR|1SFA|1SBL|1SDA|1SNA|1SNK|1SNL|1STQ|2CDS|2CSF|2CDE|"
                 r"3AUA|1SAJ|1SDF|1SFL|1SFB|1SVM)\s?-?\d{2,}"],                                   # ABB
      absorb="all"),
    T("estop", "Emergency stops", "product",
      "EMERGENCY STOP|EMERGENCY STOPS|E STOP|ESTOP|EMERGENCYSTOP|EMERGENCY BUTTON|EMERGENCY SWITCH|NOODSTOP|"
      "NOODSTOPPEN|NOOD STOP|NOODSTOPKNOP|NOODSTOPSCHAKELAAR|NOT AUS|NOTAUS|NOT HALT|NOTHALT|NOTHALTTASTER|"
      "NOTAUSTASTER|NOT AUS TASTER|NOT HALT TASTER|NOTHALT TASTER|NOTAUS SCHALTER|PILZTASTER|MUSHROOM|MUSHROOM BUTTON|PADDESTOEL|"
      "PADDENSTOEL|PADDENSTOELKNOP|PULL WIRE|PULL CORD|PULL WIRE SWITCH|PULL CORD SWITCH|ROPE PULL SWITCH|TREKKOORDSCHAKELAAR|SEILZUGSCHALTER|"
      "SEILZUGNOTSCHALTER|ROPE PULL|ROPE SWITCH|STOP BUTTON|STOPKNOP|STOPTASTER",
      codes=[R + r"(?:XB4BS|XB5AS|XB4BT|XB5AT|XALK|XAPJ|ZB4BS|ZB5AS|3SU1\d{2}0-1[BH]|3SB3\d{3}-1[HA]|M22-PV|"
                 r"M22-PVT|A22NE|A22E|A165E|AVLW)[- ]?[A-Z0-9]{2,}"],
      absorb="all"),
    T("push_button", "Push buttons & selectors", "product",
      "PUSH BUTTON|PUSHBUTTON|PUSH BUTTONS|DRUKKNOP|DRUKKNOPPEN|DRUKTOETS|DRUCKTASTER|DRUCKKNOPF|TASTER|"
      "*TASTER|BUTTON|BUTTONS|KNOP|SELECTOR SWITCH|SELECTOR|KEUZESCHAKELAAR|WAHLSCHALTER|KEY SWITCH|"
      "KEYSWITCH|SLEUTELSCHAKELAAR|SCHLUESSELSCHALTER|PILOT LIGHT|INDICATOR LIGHT|"
      "MELDELEUCHTE|LEUCHTMELDER|INDICATOR|INDICATOR LAMP|JOYSTICK|JOYSTICKS|POTENTIOMETER|POTMETER|"
      "FOOT SWITCH|FOOTSWITCH|VOETSCHAKELAAR|FUSSSCHALTER|FUSSTASTER|TWO HAND|TWEEHANDBEDIENING|"
      "ZWEIHANDBEDIENUNG|ENABLING SWITCH|ZUSTIMMTASTER|HANDHELD|HANDTERMINAL|PENDANT|BEDIENELEMENT|"
      "COMMAND DEVICE|CONTROL UNIT BUTTON|ROTARY SWITCH|DRAAISCHAKELAAR|DREHSCHALTER|NOCKENSCHALTER|"
      "CAM SWITCH|NOKKENSCHAKELAAR|TOGGLE SWITCH|TUIMELSCHAKELAAR|KIPPSCHALTER",
      codes=[R + r"(?:3SU1|3SB3|3SB5|3SB6|XB4|XB5|XB7|ZB4|ZB5|XA2|RMQ|RAFIX|RAFIX22|HW1B|HW1L|HW1E|HW1S|"
                 r"HW1F|XW1E|XA1E|YW1B|YW1L|YW1S|HA1E|HE1B|HS1E|HS5E)[- ]?[A-Z0-9]{2,}",
             R + r"(?:M22|M22S|M16|A22N?[ELSW]?|A30N|A165|A16|SL22|SB22|AR22|AR30|SB30|LW7|AL6|CW1|CW2)-[A-Z0-9]",
             R + r"EAO\s?(?:\d{2})?" + E],
      absorb="all"),
    T("signal_tower", "Signal towers & lamps", "product",
      "SIGNAL TOWER|SIGNALTOWER|SIGNAL COLUMN|STACK LIGHT|STACKLIGHT|TOWER LIGHT|TOWERLIGHT|SIGNAALZUIL|"
      "SIGNAALTOREN|SIGNAALPAAL|SIGNALSAEULE|SIGNALSAULE|LEUCHTSAEULE|LEUCHTSAULE|SIGNALLEUCHTE|SIGNAL LIGHT|"
      "WARNING LIGHT|WARNINGLIGHT|WARNLEUCHTE|BEACON|BEACONS|FLASHING LIGHT|FLITSLICHT|BLITZLEUCHTE|"
      "ROTATING LIGHT|ZWAAILICHT|ZWAAILAMP|RUNDUMLEUCHTE|DREHSPIEGELLEUCHTE|LAMP|LAMPS|LAMPE|*LAMPE|*LAMP|"
      "LIGHT|LIGHTS|LED|LEDS|LED STRIP|LEDSTRIP|LED BAR|LEDBAR|LICHTBALK|LEUCHTE|*LEUCHTE|ARMATUUR|"
      "WORK LIGHT|WORKLIGHT|WERKLAMP|ARBEITSLEUCHTE|MASCHINENLEUCHTE|MACHINE LIGHT|MACHINELAMP|SPOTLIGHT|"
      "SPOT|FLOODLIGHT|SCHIJNWERPER|SCHEINWERFER|NAVIGATION LIGHT|NAVIGATIELICHT|POSITIONSLAMPE|"
      "OBSTRUCTION LIGHT|LUMINAIRE|LIGHT FITTING|LIGHTING|VERLICHTING|BELEUCHTUNG|TL BUIS|TUBE LIGHT|"
      "STROBE|SIGNALGEBER|SIGNAL DEVICE|SIGNALEERLAMP|INDICATOR TOWER|ANDON",
      codes=[R + r"(?:WERMA|KOMPAKT\s?\d{2}|LR[4-7]-|LME-|LU[57]-|LD-|LKEH|LA6-|TL50|TL70|K50L|K30L|WLS15|"
                 r"WLS27|WLS28|PSD-S|SIRENA|QLIGHT|PATLITE|PFANNENBERG|8WD4|8WD44|8WD53|8WD56|XVB|XVC|XVR|XVE|"
                 r"XVM|XVP|XVGB|XVDLS|XVDS|XVUC|XVBL)[A-Z0-9-]{0,10}"],
      absorb="all"),
    T("robot", "Robots", "product",
      "ROBOT|ROBOTS|ROBOTARM|ROBOT ARM|INDUSTRIAL ROBOT|INDUSTRIEROBOT|INDUSTRIEROBOTER|*ROBOTER|COBOT|"
      "COBOTS|SCARA|DELTA ROBOT|ROBOTIC ARM|MANIPULATOR|PICK AND PLACE ROBOT",
      codes=[R + r"(?:KR\s\d{1,4}|LBR|IRB\s?\d{3,4}|CRB\s?\d{4}|GOFA|YUMI|SWIFTI|M-\d{1,4}I[ABCDF]|"
                 r"LR\s?MATE|CRX-\d{1,2}I[AL]|R-2000I[ABCD]|ARC MATE|UR\d{1,2}E?|TX2-\d{2}|TS2-\d{2}|COBOTTA|"
                 r"RV-\d{1,2}F|RH-\d{1,2}F|EPSON\s?[CGLNST]\d|FANUC|KUKA|STAUBLI|DENSO|YASKAWA|MOTOMAN|COMAU|"
                 r"KAWASAKI|DOOSAN|TECHMAN|FRANKA|IIWA|AGILUS|QUANTEC|FORTEC)" + E],
      absorb="all"),

    # ---- operator parts and machine furniture ---------------------------------------------------
    T("foot", "Levelling feet", "component",
      "LEVELLING FOOT|LEVELING FOOT|LEVELLING FEET|LEVELING FEET|LEVELLING PAD|LEVELING PAD|LEVELLING ELEMENT|"
      "LEVELING ELEMENT|LEVELLING MOUNT|ADJUSTABLE FOOT|MACHINE FOOT|MACHINE FEET|MACHINEVOET|STELVOET|"
      "STELVOETEN|STELPOOT|STELPOTEN|NIVELLEERVOET|NIVELLIERFUSS|NIVELLIERFUESSE|NIVELLIERELEMENT|"
      "MASCHINENFUSS|STELLFUSS|STELLFUESSE|GELENKFUSS|SCHARNIERVOET|SWIVEL FOOT|FOOT|FEET|VOET|VOETEN|"
      "POOT|POTEN|FUSS|FUESSE|*FUSS|BODENPLATTE FUSS|ANCHOR FOOT|VLOERVOET",
      codes=[R + r"LV\.F" + E, R + r"LV\.[A-Z]-?\d{2}", R + r"(?:GN\s?343|GN\s?344|GN\s?345|GN\s?348|GN\s?338|GN\s?339|GN\s?340|"
             r"GN\s?346)(?:\.\d)?" + E,
             R + r"(?:ADP|ADJF|ADJS|ADJB|ADJH|ADJW|ADPG|LEFS|LEFM|LEMS|LEML|LEPS|LEPM)\d{1,2}-",
             R + r"(?:LEMNT|LEMN|HNFJR|NFJN|FJGN)\d{2,3}(?!\d)"]),                                # Misumi levelling mounts
    T("caster", "Casters & wheels", "component",
      "CASTER|CASTERS|CASTOR|CASTORS|SWIVEL CASTER|FIXED CASTER|WHEEL|WHEELS|WIEL|WIELEN|*WIEL|ZWENKWIEL|"
      "ZWENKWIELEN|BOKWIEL|BOKWIELEN|ZWENKROL|LENKROLLE|LENKROLLEN|BOCKROLLE|BOCKROLLEN|TRANSPORTROLLE|"
      "RAD|RAEDER|RADER|*RAD|LAUFRAD|LAUFRAEDER|TROLLEY WHEEL|LOOPWIEL|TRACK WHEEL|KRAANWIEL|KRANRAD|"
      "TYRE|TIRE|BAND WIEL|BANDEN WIEL|REIFEN|ROLLER WHEEL|POLYURETHANE WHEEL|PU WHEEL|NYLON WHEEL",
      codes=[R + r"(?:TENTE|BLICKLE|COLSON|GUITEL|WICKE|ROLLCO)" + E, R + r"(?:HCFTF|CAZL|AFCLA)\d{2,3}"]),
    T("roller", "Conveyor rollers", "component",
      "CONVEYOR ROLLER|CONVEYORROLLER|TRANSPORT ROLLER|TRANSPORTROL|TRANSPORTROLLEN|ROLLENBAAN|ROLLERBAAN|"
      "ROL|ROLLEN|*ROL|ROLLER|ROLLERS|ROLLE|*ROLLE|TRAGROLLE|FOERDERROLLE|FORDERROLLE|DRIVE ROLLER|AANDRIJFROL|"
      "ANTRIEBSROLLE|IDLER ROLLER|MOTOR ROLLER|MOTORROLLER|MOTORROL|BALL TRANSFER|KOGELROL|KUGELROLLE|"
      "KUGELROLLER|BALL TRANSFER UNIT|GUIDE ROLLER|GELEIDEROL|FUEHRUNGSROLLE|PRESSURE ROLLER|DRUKROL|"
      "ANDRUCKROLLE|SUPPORT ROLLER|STEUNROL|STUETZROLLE|NIP ROLLER|DRUM ROLLER",
      codes=[R + r"(?:INTERROLL|ROLLEX|ITOH DENKI|RULMECA|VAN DER GRAAF)" + E, R + r"(?:EC5000|EC310)" + E,
             R + r"(?:RORPOS|UMHS)\d{2}"]),                                                # Misumi rollers
    T("hinge", "Hinges & latches", "component",
      "HINGE|HINGES|SCHARNIER|SCHARNIEREN|*SCHARNIER|DOOR HINGE|DEURSCHARNIER|TUERSCHARNIER|BAND SCHARNIER|"
      "PIANO HINGE|PIANOSCHARNIER|STANGENSCHARNIER|LATCH|LATCHES|SLUITING|*SLUITING|VERSCHLUSS|*VERSCHLUSS|"
      "SPANNVERSCHLUSS|SPANSLUITING|LATCH CLAMP|DRAW LATCH|DOOR LOCK|DEURSLOT|TUERSCHLOSS|TURSCHLOSS|LOCK|LOCKS|SLOT|SLOTEN|SCHLOSS|*SCHLOSS|QUARTER TURN|"
      "KWARTSLAGSLUITING|DREHRIEGEL|VRIEGEL|RIEGEL|GRENDEL|*GRENDEL|BOLT LATCH|SCHUIFGRENDEL|SCHIEBERIEGEL|"
      "MAGNETIC CATCH|MAGNEETSLUITING|MAGNETSCHNAEPPER|BALL CATCH|KOGELSNAPPER|KUGELSCHNAEPPER|SNAPPER|"
      "DOOR STAY|DEURSTOP|TUERFESTSTELLER|DOOR HOLDER|DEURHOUDER|TUERHALTER|COMPRESSION LATCH|"
      "SPANNSCHLOSS SCHRANK|CAM LOCK|CAMLOCK|PADLOCK|HANGSLOT|VORHAENGESCHLOSS|STRIKER|SLUITPLAAT|SCHLIESSBLECH",
      codes=[R + r"(?:GN\s?7\d{3}|GN\s?115|GN\s?119|GN\s?161|GN\s?237|GN\s?337|GN\s?7233)(?:\.\d)?" + E,
             R + r"(?:SOUTHCO|DIRAK|EMKA)" + E, R + r"(?:HHPM|HHPN|HHPS|HHPE|HHSS|HHSL)\d{2}",
             # Misumi hinges HHPSN6, HHS25, E-HNG90; magnet catches MGCST30, HMEN-T; hinge bases HKPB6
             R + r"(?:HHPSN|HHSN|HHS|HHKS|HHMU|HNG|MGCST|MGCC|MGCEJ|HKPB|HGCNB|PKWSA|PKWS|PKBSL)\d{1,3}(?!\d)",
             R + r"HMEN-"]),
    T("handle", "Handles & knobs", "component",
      "HANDLE|HANDLES|HANDLE BAR|HANDLEBAR|BOW HANDLE|PULL HANDLE|TUBULAR HANDLE|HANDGREEP|HANDGREPEN|GREEP|GREPEN|*GREEP|"
      "TREKGREEP|BEUGELGREEP|GRIFF|GRIFFE|*GRIFF|BUEGELGRIFF|BUGELGRIFF|HANDGRIFF|ROHRGRIFF|MULDENGRIFF|"
      "GRIP|HANDGRIP|KNOB|KNOBS|STAR KNOB|STERKNOP|STERGREEP|STERNGRIFF|KNEBEL|KNEBELSCHRAUBE|DRAAIKNOP|"
      "DREHKNOPF|KNOPF|CLAMPING LEVER|ADJUSTABLE HANDLE|KLEMHENDEL|SPANHENDEL|KLEMMHEBEL|SPANNHEBEL|"
      "HANDWHEEL|HAND WHEEL|HANDWIEL|HANDRAD|*HANDRAD|CRANK|CRANK HANDLE|SLINGER|KURBEL|*KURBEL|INDEXING PLUNGER|"
      "INDEX PLUNGER|INDEXBOLZEN|ARRETIERBOLZEN|ARRETEERPEN|VERGRENDELPEN|TOGGLE CLAMP|SNELSPANNER|"
      "SCHNELLSPANNER|*SPANNER|KNIEHEBELSPANNER|"
      "CONTROL KNOB|BEDIENKNOP|DRAAIGREEP|T HANDLE|THANDLE|L HANDLE|FOLDING HANDLE|KLAPGREEP|KLAPPGRIFF|"
      "RECESSED HANDLE|INBOUWGREEP|ELESA|GANTER|NORELEM|KIPP|HEINRICH KIPP|WDS",
      codes=[R + r"GN\s?(?!34[0-8]|33[89]|115|119|161|237|337)\d{3}(?:\.\d)?" + E,             # Ganter (not feet, hinges)
             R + r"GN\s?(?!34[0-8]|33[89]|115|119|161|237|337)\d{3}(?:\.\d)?-\d",
             R + r"(?:M\.\d{3}|MPR|ERX|ECX|EBR|EWX|EBP|EBL|EWB|ERD|VCT|VDS|IZN|IZD|IZR)[.\-+]?\d{1,3}",  # Elesa
             R + r"K\d{4}\.\d{2,4}" + E,                                                       # Kipp
             # Misumi handles UWANS10-120, GRAMS12; knobs NKBC6-16, NOOS8; handwheels PHSN; indexing plungers PXSL20
             R + r"(?:UWANS|UWAPN|USANS|UHFSN|GRAMS|GRAM|HHDS|UGFN|HFHDL|NKBC|NKBB|NKSM|NOOS|NMM|SKN|LKNB[A-Z]{0,3}|"
                 r"UPCN|PHSN|AHSN|PHSM|AHSK)\d{1,3}(?!\d)",
             R + r"PX[A-Z]{2,4}\d{1,2}", R + r"(?:SXPP|SXNA)\d{1,2}",
             R + r"(?:GN|DIN)\s?633[5-7]" + E]),                                       # star and cross knobs
    T("window", "Windows & clear parts", "component",
      "WINDOW|WINDOWS|VENSTER|VENSTERS|*VENSTER|FENSTER|*FENSTER|SICHTFENSTER|KIJKVENSTER|KIJKGLAS|KIJKRUIT|"
      "SCHAUGLAS|VIEWING WINDOW|VIEW WINDOW|INSPECTION WINDOW|INSPECTIEVENSTER|RUIT|RUITEN|*RUIT|SCHEIBE GLAS|"
      "GLAZING|BEGLAZING|VERGLASUNG|GLASS PANEL|GLASPANEEL|GLASSCHEIBE|SAFETY GLASS|VEILIGHEIDSGLAS|"
      "SICHERHEITSGLAS|WINDSCREEN|WINDSHIELD|VOORRUIT|WINDSCHUTZSCHEIBE|SIGHT GLASS PANEL|CLEAR PANEL|"
      "CLEAR COVER|CLEAR GUARD|TRANSPARENT COVER|TRANSPARANTE KAP|TRANSPARENT PANEL|VISOR|VIZIER|"
      "PC PLATE|PC PANEL|PC SHEET|PC PLAAT|PMMA PLATE|LEXAN PLATE|PLEXIPLAAT|PLEXIGLASPLAAT|POLYCARB",
      codes=[R + r"ACA-\d{2,4}-\d{2,4}-\d"]),                                                # Misumi acrylic plates
    T("wire_mesh", "Wire mesh & fences", "component",
      "WIRE MESH|WIREMESH|MESH|MESH PANEL|MESHPANEL|GAAS|GAASPANEEL|GAASPANELEN|DRAADGAAS|GAASWERK|GITTER|"
      "*GITTER|DRAHTGITTER|GITTERPANEEL|GITTERELEMENT|FENCE|FENCES|FENCING|HEK|HEKKEN|HEKWERK|*HEKWERK|"
      "ZAUN|*ZAUN|SCHUTZZAUN|SAFETY FENCE|MACHINE GUARD FENCE|MACHINEHEK|AFSCHERMHEK|PERIMETER GUARD|"
      "GUARD FENCE|FENCE PANEL|FENCE POST|HEKPAAL|ZAUNPFOSTEN|PERFORATED|GEPERFOREERD|LOCHBLECH|PERFORATED SHEET|"
      "PERFORATED PLATE|PONSPLAAT|STRECKMETALL|EXPANDED METAL|STREKMETAAL|WOVEN MESH|WEEFSEL|SIEB|ZEEF|"
      "SCREEN MESH|INSECT SCREEN",
      codes=[R + r"(?:AXELENT|TROAX|SATECH|X-GUARD|XGUARD|X-STORE|ST20|ST30|ST20XL|SMART FIX|RAPID FIX|"
                 r"ROLL OVER|GUARD-IT)" + E]),
    T("grating", "Gratings, stairs & railings", "component",
      "GRATING|GRATINGS|FLOOR GRATING|GRATING PANEL|ROOSTER|ROOSTERS|VLOERROOSTER|LOOPROOSTER|ROOSTERVLOER|"
      "GITTERROST|GITTERROSTE|*ROST|PRESSROST|SCHWEISSPRESSROST|WALKWAY|WALKWAYS|LOOPBRUG|LOOPPAD|LAUFSTEG|"
      "BORDES|PLATFORM|PLATFORMS|PODIUM|BUEHNE|BUHNE|ARBEITSBUEHNE|STAIR|STAIRS|STAIRCASE|STAIRWAY|TRAP|"
      "TRAPPEN|TREPPE|*TREPPE|TREPPENSTUFE|STAIR STEP|STEP PLATE|TREDE|TREDEN|STUFE|STUFEN|*STUFE|LADDER|LADDERS|"
      "LEITER|*LEITER|STEIGLEITER|KOOILADDER|CAGE LADDER|HANDRAIL|HANDRAILS|HAND RAIL|LEUNING|LEUNINGEN|"
      "TRAPLEUNING|HANDLAUF|RAILING|RAILINGS|BALUSTRADE|GELAENDER|GELANDER|*GELAENDER|GUARDRAIL|GUARD RAIL|"
      "KICKPLATE|KICK PLATE|SCHOPRAND|FUSSLEISTE|TOE BOARD|TOEBOARD|CHECKER PLATE|CHEQUER PLATE|"
      "TREAD PLATE|TRAANPLAAT|RIFFELBLECH|TRAENENBLECH|TRANENBLECH|ANTISLIP|ANTI SLIP|STAIR TREAD|"
      "TRAPTREDE|GITTERROSTSTUFE|SELF CLOSING GATE|SWING GATE|POORTJE|ACCESS GATE|STANCHION|RELINGSTUETZE",
      codes=[R + r"(?:MW|MWB|SP|SPR)\s?\d{2}\s?X\s?\d{2}\s?-\s?\d{2}\s?X\s?\d" + E]),
    T("label", "Labels & signs", "component",
      "LABEL|LABELS|STICKER|STICKERS|NAMEPLATE|NAME PLATE|TYPE PLATE|TYPEPLATE|TYPEPLAAT|TYPENSCHILD|"
      "TYPEPLATEJE|RATING PLATE|SERIAL PLATE|IDENTIFICATION PLATE|SCHILD|*SCHILD|WARNSCHILD|HINWEISSCHILD|"
      "SIGN|SIGNS|WARNING SIGN|WAARSCHUWINGSBORD|BORD|BORDJE|PICTOGRAM|PIKTOGRAMM|DECAL|DECALS|LOGO|LOGOS|"
      "EMBLEM|EMBLEEM|MARKING|MARKERING|KENNZEICHNUNG|AUFKLEBER|ETIKET|ETIKETTEN|ETIKETT|SAFETY SIGN|"
      "CE PLATE|CE LABEL|CE MARK|ARROW|PIJL|PFEIL|SCALE|SCHAAL|SKALA|LINEAAL|MASSSTAB|RULER|"
      "TEXT PLATE|TEKSTPLAATJE|TAG|TAGS"),
    T("mannequin", "Mannequins", "product",
      "MANNEQUIN|MANNEQUINS|MANIKIN|HUMAN|HUMANS|HUMAN BODY|HUMAN FIGURE|PERSON|PERSONS|PEOPLE|OPERATOR|"
      "OPERATORS|WORKER|WORKERS|ERGONOMICS|ERGONOMIC FIGURE|ERGO MAN|ERGOMAN|MENS|MENSEN|MENSCH|MENSCHEN|"
      "PUPPE|POP|POPPETJE|POPPETJES|ARBEITER|WERKNEMER|BEDIENER|BEDIENERS|DUMMY HUMAN|HUMAN DUMMY|"
      "MAN STANDING|MAN SITTING|WOMAN|HUMAN MALE|HUMAN FEMALE|PERCENTILE|PERSOON|PERSONEN|ANTHROPOMETRIC|FIGURINE|AVATAR|SILHOUETTE",
      codes=[R + r"(?:P\d{2}|\d{1,2}TH)\s?PERCENTILE", R + r"(?:HUMAN|MANNEQUIN)_"],
      absorb="all"),
    T("tooling", "Tool holders & tools", "component",
      "TOOL HOLDER|TOOLHOLDER|TOOL HOLDERS|GEREEDSCHAPHOUDER|WERKZEUGHALTER|COLLET|COLLETS|SPANTANG|"
      "SPANTANGEN|SPANNZANGE|*SPANNZANGE|COLLET CHUCK|SPANTANGHOUDER|SPANNZANGENFUTTER|CHUCK|CHUCKS|"
      "KLAUWPLAAT|BOORKOP|BOHRFUTTER|SPANNFUTTER|*FUTTER|END MILL|ENDMILL|MILLING CUTTER|FREES|FREZEN|"
      "SCHAAFFREES|FRAESER|FRASER|*FRAESER|*FRASER|DRILL|DRILLS|DRILL BIT|BOOR|BOREN|SPIRAALBOOR|BOHRER|"
      "*BOHRER|SPIRALBOHRER|TAP DRILL|THREAD TAP|DRAADTAP|GEWINDEBOHRER|REAMER|RUIMER|REIBAHLE|INSERT HOLDER|"
      "WISSELPLAAT|WENDESCHNEIDPLATTE|CUTTING INSERT|SAW BLADE|ZAAGBLAD|SAEGEBLATT|SAGEBLATT|GRINDING WHEEL|"
      "SLIJPSCHIJF|SCHLEIFSCHEIBE|PULL STUD|TREKBOUT|ANZUGSBOLZEN|TOOL|TOOLS|GEREEDSCHAP|WERKZEUG|*WERKZEUG",
      codes=[R + r"ER\s?(?:8|11|16|20|25|32|40|50)" + E, R + r"(?:HSK|SK|BT|CAT)\s?-?(?:[A-F]\s?)?(?:25|30|32|"
             r"40|50|63|80|100)[A-F]?" + E, R + r"(?:DIN\s?69871|DIN\s?69893|MAS\s?403)" + E]),
    T("lifting", "Lifting gear & wire ropes", "component",
      "WIRE ROPE|WIRE ROPES|WIREROPE|STAALKABEL|STAALKABELS|STAALDRAADKABEL|DRAHTSEIL|STAHLSEIL|STAHLDRAHTSEIL|"
      "SEIL|*SEIL|ROPE|ROPES|TOUW|TOUWEN|LIJN|TROSS|HAWSER|MOORING LINE|MEERTROS|SLING|SLINGS|HIJSBAND|"
      "HIJSBANDEN|HEBEBAND|RUNDSCHLINGE|ROUNDSLING|CHAIN SLING|KETTINGSTROP|STROP|STROPPEN|SHACKLE|SHACKLES|"
      "SLUITING HIJS|HARP SHACKLE|D SHACKLE|SCHAEKEL|SCHAKEL|SCHAECKEL|HOOK|HOOKS|HAAK|HAKEN|*HAKEN|"
      "LASTHAKEN|KRANHAKEN|CRANE HOOK|HIJSHAAK|SWIVEL|SWIVELS|SWIVEL HOOK|WIRBEL|SWIVEL EYE|LIFTING EYE|"
      "HIJSOOG|HEBEOESE|ANSCHLAGPUNKT|LIFTING POINT|HIJSPUNT|LIFTING LUG|PAD EYE|PADEYE|PADEYES|HIJSPLAAT|"
      "TURNBUCKLE|SPANSCHROEF|SPANNSCHLOSS|THIMBLE|KAUSCH|KOUS|WIRE ROPE CLIP|SEILKLEMME|KABELKLEM STAAL|"
      "SOCKET ROPE|SEILSCHLOSS|SPELTER SOCKET|VERGIETKOP|FERRULE|PERSKLEM|PRESSKLEMME|SPREADER BEAM|"
      "HIJSJUK|TRAVERSE|LIFTING BEAM|BLOCK AND TACKLE|TAKEL|KETTINGTAKEL|KETTENZUG|HOIST|HOISTS|"
      "HIJSWERKTUIG|HEBEZEUG|CHAIN HOIST|LIFTING CLAMP|HIJSKLEM|HEBEKLEMME|HOOK BLOCK|HAKENBLOK|HAKENFLASCHE|MASTER LINK|MOERSCHAKEL|"
      "AUFHAENGEGLIED|BOLLARD|BOLDER|POLLER|CLEAT MOORING|KIKKER|FAIRLEAD|VERHAALKLAMP|ANCHOR|ANKER|*ANKER",
      codes=[R + r"(?:G-209|G-2130|G-2140|G-2150|G-213|S-209|S-322|S-320|G-416|G-421|G-450|S-4320|"
                 r"G-2160|CROSBY|GUNNEBO|PEWAG|THIELE|VAN BEEST|GREEN PIN)" + E,
             R + r"\d{1,2}\s?X\s?(?:7|19|25|26|31|36|37|41|49)\s?(?:IWRC|FC|WSC|WS|FW|SES)" + E]),
    T("winch", "Winch drums & sheaves", "component",
      "WINCH|WINCHES|LIER|LIEREN|ANKERLIER|MEERLIER|SLEEPLIER|WINDE|SEILWINDE|ANKERWINDE|ANKERSPILL|"
      "CAPSTAN|KAAPSTANDER|DRUM|DRUMS|*DRUM|LIERDRUM|LEBUS|LEBUS SLEEVE|LEBUS SHELL|WINCH DRUM|LIERTROMMEL|TROMMEL|*TROMMEL|SEILTROMMEL|KABELTROMMEL|"
      "CABLE DRUM|REEL|REELS|HASPEL|*HASPEL|KABELHASPEL|CABLE REEL|HOSE REEL|SLANGHASPEL|SCHLAUCHTROMMEL|"
      "SHEAVE|SHEAVES|SCHIJF KABEL|KABELSCHIJF|SEILSCHEIBE|SEILROLLE|BLOCK SHEAVE|SNATCH BLOCK|"
      "KATROL|KATROLLEN|TENSIONER|CABLE TENSIONER|KABELSPANNER|SPOOLING GEAR|SPOELINRICHTING|"
      "SPULVORRICHTUNG|LEVEL WIND|LEVELWIND|CAROUSEL|KAROUSEL|KARUSSELL|TURNTABLE|DRAAISCHIJF|"
      "OVERBOARDING CHUTE|CHUTE SHEAVE|QUADRANT|ROLLER BOX|ROLBOX|STINGER|A FRAME|AFRAME|DAVIT|"
      "LAUNCH AND RECOVERY|LARS|TOWING PIN|SLEEPPEN|SHARK JAW|SHARKJAW"),
]

# Names that look like a known type but are not (checked as whole phrases).
NOT_PART_TYPE = {
    "PRODUCT INFO", "PART INFO", "INFO", "DRAWING", "TEKENING", "ZEICHNUNG", "SKETCH", "SCHETS", "SKIZZE",
    "REFERENCE", "REFERENTIE", "ORIGIN", "WORK PLANE", "WORKPLANE", "WORK AXIS", "WERKVLAK", "ARBEITSEBENE",
    "CONSTRUCTION LINE", "HULPLIJN", "COORDINATE SYSTEM", "UCS",
}

# Words for machine modules and stations. An assembly called "O-RING.FITTING.UNIT" or
# "INFEED.SYSTEM" is a station of the machine, not a bought O-ring or conveyor: it never
# passes its type on to the parts inside it, and a part named like that gets no type either
# (unless the word belongs to the keyword itself, as in "BEARING UNIT" or "DRIVE UNIT").
MODULE_WORDS = ("UNIT|UNITS|STATION|STATIONS|SYSTEM|SYSTEMS|MODULE|MODULES|MACHINE|MACHINES|LINE|LINES|CELL|"
                "CELLS|MECHANISM|DEVICE|DEVICES|EQUIPMENT|INSTALLATION|FIXTURE|FIXTURES|JIG|FEEDER|MAGAZINE|"
                "INSPECTION|INSP|TESTER|TEST BENCH|WORKSTATION|EENHEID|EENHEDEN|MODUL|MASCHINE|ANLAGE|"
                "INSTALLATIE|VORRICHTING|VORRICHTUNG|MECHANISME|MECHANISMUS|EINHEIT|*EINHEIT|LIJN|LINIE|ZELLE|"
                "CEL|APPARAAT|OPSTELLING|AUFBAU|SKID UNIT|TEST RIG|TESTOPSTELLING|PRUEFSTAND|PROEFSTAND|DRIVE|"
                "DRIVES|AANDRIJVING|ANTRIEB|PRESS|PERS|PRESSE|TEST|MC|MACH|ROBOTCEL|GRIPPER HEAD|LOADER|"
                "UNLOADER|STACKER|BUFFER STATION|TRANSFER|LIFTER|ELEVATOR|LIFT|HEFTAFEL|HUBTISCH")

# Component types whose assemblies are bought multi-part items ("UCP205" = housing + insert
# bearing, a caster = wheel + fork + plate). Parts inside them with generic names belong to
# them. Other component words in an assembly name usually describe a mechanism of the machine
# ("BELT DRIVE ASSY", "CHAIN.CONVEYOR", "SEAL.PRESS"), so they pass nothing down.
CONTEXT_COMPONENTS = {
    "bearing", "bearing_housing", "linear_guide", "coupling", "cable_gland", "fitting", "caster", "handle", "foot",
    "hinge", "rod_end", "lifting", "roller", "bushing", "pulley", "winch", "profile_connector",
}

# Qualifiers: words that describe a part without naming it ("CABLE M12 4-PIN", "GRIPPER 2-JAW",
# "CASTER WITH BRAKE", "VALVE TERMINAL 8 STATIONS"). Keywords inside them do not count.
QUALIFIERS = ("|".join(f"{n} PIN|{n} POL|{n} POLIG|{n} JAW|{n} STATIONS|{n} STATION|{n} WAY|{n} WEGE"
                       for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16, 17, 19, 24, 25, 32))
              + "|WITH BRAKE|MET REM|MIT BREMSE|MIT FESTSTELLER|WITH LOCK|MET VERGRENDELING|WITH SPRING|MET VEER|"
                "MIT FEDER|WITH SEAL|MET AFDICHTING|MIT DICHTUNG|WITH CABLE|MET KABEL|MIT KABEL|WITH HANDLE|"
                "MET HANDGREEP|MIT GRIFF|FOR PROFILE|VOOR PROFIEL|FUER PROFIL|FUR PROFIL")

# --------------------------------------------------------------------------------------------
# Materials named in the part name
# --------------------------------------------------------------------------------------------

# class -> (keywords, codes on the upper-case name)
MATERIAL_WORDS: dict[str, tuple[str, tuple]] = {
    "stainless": ("STAINLESS|INOX|RVS|EDELSTAHL|NIROSTA|ROESTVAST|ROESTVRIJ|ROSTFREI|SST|SS|DUPLEX|SUPERDUPLEX|"
                  "STAINLESS STEEL|STAINLESSSTEEL|V2A|V4A|RVS*|INOX*",
                  (R + r"1\.4[3-5]\d{2}" + E, R + r"(?:AISI|SUS)\s?-?3\d\d[L]?" + E, R + r"3(?:04|16|21)L" + E,
                   R + r"(?:SS|INOX)\s?-?3\d\d" + E)),
    "anodised_black": ("BLACK ANODISED|BLACK ANODIZED|ZWART GEANODISEERD|SCHWARZ ELOXIERT|ZWARTGEANODISEERD|"
                       "ELOXIERT SCHWARZ|GEANODISEERD ZWART|ANODISED BLACK|ANODIZED BLACK", ()),
    "anodised": ("ANODISED|ANODIZED|GEANODISEERD|ELOXIERT|ELOXAL|ANO", ()),
    "aluminium": ("ALU|ALU*|ALUMINIUM|ALUMINUM|ALLUMINIUM|ALLUMINUM|ALUMINIO|ALMG|ALMGSI|ALZNMGCU|DURAL|AL",
                  (R + r"(?:EN\s?AW-?)?(?:6061|6063|6082|7075|5083|5754|2007|2017|2024)(?:\s?-?T\d{1,3})?" + E,
                   R + r"AL\s?MG\s?\d" + E, R + r"ALMGSI\d?" + E)),
    "brass": ("BRASS|MESSING", (R + r"CU\s?ZN\s?\d{2}" + E, R + r"MS\s?58" + E, R + r"CW6\d{2}[NR]" + E)),
    "bronze": ("BRONZE|BRONS|BRONSE|ROTGUSS", (R + r"CU\s?SN\s?\d{1,2}" + E, R + r"RG\s?[57]" + E)),
    "copper": ("COPPER|KOPER|KUPFER|ECU|CU", (R + r"CW00\d[A-Z]" + E,)),
    "chrome": ("CHROME|CHROMED|VERCHROOMD|VERCHROMT|HARDCHROOM|HARTVERCHROMT|CHROMIUM", ()),
    "galvanized": ("GALVANISED|GALVANIZED|GALV|HDG|THV|THERMISCH VERZINKT|FEUERVERZINKT|DOMPELVERZINKT|"
                   "HOT DIP|HOTDIP|SENDZIMIR|SENDZIMIRVERZINKT", ()),
    "zinc": ("VERZINKT|ZINC PLATED|ZINKED|GVZ|ELVZ|ELEKTROLYTISCH VERZINKT|GALVANISCH VERZINKT", ()),
    "steel": ("STEEL|STAAL|STAHL", (R + r"S\s?(?:235|275|355|420|460|690)(?:\s?J[R0-2]|\s?MC|\s?ML|\s?N|\s?QL?)?"
                                        + E, R + r"(?:ST\s?37|ST\s?52|C\s?45|C\s?35|C\s?15|42\s?CR\s?MO\s?4|"
                                        r"34\s?CR\s?NI\s?MO\s?6|11\s?SMN\s?PB\s?30|9SMNPB28|16\s?MN\s?CR\s?5|"
                                        r"100\s?CR\s?6|DC0[1-6]|DX5[1-4]D|HARDOX\s?\d{3}|WELDOX\s?\d{3}|"
                                        r"STRENX\s?\d{3}|DOMEX\s?\d{3})" + E)),
    "cast_iron": ("CAST IRON|GIETIJZER|GUSSEISEN|GRAUGUSS|SPHAEROGUSS|NODULAR|GGG|GG|GJL|GJS|GUSS",
                  (R + r"(?:EN-?)?GJ[LS]\s?-?\d{3}" + E, R + r"GGG?\s?-?\d{2}" + E)),
    "pom": ("POM|POMC|POMH|DELRIN|ACETAL|HOSTAFORM|ERTACETAL|TECAFORM|POLYACETAL|POLYOXYMETHYLENE", ()),
    "pe": ("PE|HDPE|LDPE|UHMW|UHMWPE|UHMPE|POLYETHYLENE|POLYETHYLEEN|POLYETHYLEN|POLYSTONE|ROBALON|TIVAR",
           (R + r"PE\s?-?(?:300|500|1000|HD|HMW|UHMW)" + E,)),
    "pa": ("PA|NYLON|POLYAMIDE|POLYAMID|ERTALON|TECAMID|TECAST|NYLATRON|GLASS FILLED NYLON|PA GF",
           (R + r"PA\s?-?(?:6|66|12|46|6G|6C|6GF\d{2}|66GF\d{2})" + E,)),
    "peek": ("PEEK|KETRON|TECAPEEK", ()),
    "ptfe": ("PTFE|TEFLON|FLUON|HOSTAFLON", ()),
    "pvc": ("PVC|PVCU|HARD PVC|HART PVC|TROVIDUR|POLYVINYLCHLORIDE", ()),
    "pp": ("PP|POLYPROPYLENE|POLYPROPYLEEN|POLYPROPYLEN|PPH|PPC", ()),
    "plastic": ("PLASTIC|PLASTICS|KUNSTSTOF|KUNSTSTOFF|ABS|POLYMER|PU|PUR|POLYURETHANE|POLYURETHAAN|VULKOLLAN|"
                "PET|PETP|PBT|PEI|PSU|PPS|PMMI|BAKELITE|PERTINAX|HPL|GFK|GRP|FIBERGLASS|GLASVEZEL|EPOXY|"
                "CARBON FIBRE|CARBON FIBER|CFRP|CFK|SILICONE", ()),
    "clear": ("POLYCARBONATE|POLYCARBONAAT|POLYCARBONAT|LEXAN|MAKROLON|PLEXI|PLEXIGLAS|PLEXIGLASS|PERSPEX|"
              "ACRYLIC|ACRYL|ACRYLGLAS|PMMA|CLEAR|TRANSPARENT|TRANSPARANT|DOORZICHTIG|PETG", ()),
    "glass": ("GLASS|GLAS|TEMPERED GLASS|GEHARD GLAS|GEHAERTETES GLAS|ESG|VSG|LAMINATED GLASS", ()),
    "rubber": ("RUBBER|GUMMI|EPDM|NBR|FKM|VITON|NEOPRENE|NEOPREEN|CR RUBBER|SBR|NR RUBBER|HNBR|ELASTOMER|"
               "SILICONE RUBBER|SILIKON|SILICONENRUBBER|BUNA", ()),
    "foam": ("FOAM|SCHUIM|SCHUIMRUBBER|SCHAUM|SCHAUMSTOFF|SPONGE|ARMAFLEX|PU FOAM|PE FOAM|CELLULAR RUBBER|"
             "MOOSGUMMI|ZELLKAUTSCHUK|INSULATION|ISOLATIE|ISOLIERUNG|ROCKWOOL|STEENWOL|MINERAL WOOL", ()),
    "felt": ("FELT|VILT|FILZ|NONWOVEN|VLIES", ()),
    "wood": ("WOOD|WOODEN|HOUT|HOUTEN|HOLZ|*HOLZ|MULTIPLEX|PLYWOOD|TRIPLEX|SPERRHOLZ|MDF|OSB|SPAANPLAAT|"
             "SPANPLATTE|HARDWOOD|HARDHOUT|BEECH|BEUKEN|BUCHE|OAK|EIKEN|EICHE|PINE|GRENEN|KIEFER|PALLET|PALLETS|"
             "EUROPALLET|EURO PALLET|EUROPALETTE|PALETTE|*PALETTE|PALLETKIST|CRATE|KRAT|KIST|HOLZKISTE|HOLZ*",
             ()),
}

# class -> group (looks are in GROUPS)
MATERIAL_GROUPS: dict[str, str] = {
    "stainless": "Stainless steel parts",
    "anodised_black": "Black anodised parts",
    "anodised": "Anodised aluminium parts",
    "aluminium": "Aluminium parts",
    "brass": "Brass parts",
    "bronze": "Bronze parts",
    "copper": "Copper parts",
    "chrome": "Chrome parts",
    "galvanized": "Galvanized parts",
    "zinc": "Zinc plated parts",
    "steel": "Steel parts",
    "cast_iron": "Cast iron parts",
    "pom": "POM parts",
    "pe": "PE parts",
    "pa": "PA parts",
    "peek": "PEEK parts",
    "ptfe": "PTFE parts",
    "pvc": "PVC parts",
    "pp": "PP parts",
    "plastic": "Plastic parts",
    "clear": "Windows & clear parts",
    "glass": "Glass parts",
    "rubber": "Rubber parts",
    "foam": "Foam parts",
    "felt": "Felt parts",
    "wood": "Wood parts",
}

# Short material words that only count next to another word of the name (not as the whole
# name, where "SS" or "AL" are more likely initials or codes).
WEAK_MATERIAL_WORDS = {"SS", "AL", "CU", "PE", "PA", "PP", "PU", "ANO", "GG", "GUSS", "ECU",
                       "SST", "ESG", "VSG", "OSB", "PET", "PEI", "PSU", "PPS", "HPL", "GRP", "SBR", "PPC", "PPH",
                       "CLEAR", "TRANSPARENT"}

# Colour words that give a coloured plastic its colour ("POM BLACK", "PE500 GROEN").
COLOUR_WORDS: dict[str, tuple[str, str]] = {
    "black": ("BLACK|ZWART|SCHWARZ|BLK|SW|ZW", "RAL 9005"),
    "white": ("WHITE|WIT|WEISS|WEIS|WHT", "RAL 9016"),
    "red": ("RED|ROOD|ROT", "RAL 3020"),
    "blue": ("BLUE|BLAUW|BLAU", "RAL 5015"),
    "green": ("GREEN|GROEN|GRUEN|GRUN", "RAL 6018"),
    "yellow": ("YELLOW|GEEL|GELB", "RAL 1023"),
    "orange": ("ORANGE|ORANJE", "RAL 2004"),
    "grey": ("GREY|GRAY|GRIJS|GRAU", "RAL 7035"),
    "natural": ("NATURAL|NATUREL|NATUR|NATURE", ""),
}

# Plain profile sizes ("40x40-500", "30X30 L=450"): an aluminium profile when nothing else matches.
PROFILE_SIZE = (R + r"(?:15|20|25|30|40|45|50|60|80|90)\s?[X×*]\s?(?:15|20|25|30|40|45|50|60|80|90|120|160|180)"
                r"(?!\s?[X×*]\s?\d)(?![\d.,])")
