"""Map material and appearance names from CAD files to library materials.

STEP files from Autodesk (Fusion, Inventor) and from OpenCascade carry a material name
per part ("Aluminum 6061", "Rubber", "Steel, Mild") and Autodesk files also the
appearance name ("Aluminum - Satin", "Paint - Enamel Glossy (Red)", "Rubber - Soft").
This module turns such a name into (library material id, colour), or None when the name
says nothing useful ("Default", "Generic", or an unknown name).

Pure Python with no imports from the package: the STEP reader (a separate process) loads
it straight from this folder.

    >>> lookup("Aluminum - Satin")
    ('aluminium_machined', '')
    >>> lookup("Paint - Enamel Glossy (Red)")
    ('paint_gloss', '')
    >>> lookup("Default") is None
    True
"""

from __future__ import annotations

import re
import unicodedata

# Names that mean "no material chosen".
PLACEHOLDERS = {
    "", "DEFAULT", "GENERIC", "MATERIAL", "DEFAULT MATERIAL", "NONE", "UNKNOWN", "UNDEFINED", "STANDARD",
    "AS MATERIAL", "BY MATERIAL", "NO MATERIAL", "UNNAMED", "COLOR", "COLOUR", "DEFAULT APPEARANCE",
    "GENERIC MATERIAL", "STANDARD MATERIAL", "MATERIAL 1", "N A", "NA", "TBD", "VARIOUS",
}

# (pattern on the normalised name, material id, colour when the material needs one and the
# CAD file gives none). First match wins: specific finishes before base metals.
_P = [
    # ---- explicit paint / coating appearances --------------------------------------------
    (r"\bPOWDER ?COAT", "powder_coat", "RAL 7035"),
    (r"\b(PAINT|ENAMEL|LACQUER|LAK|LACK|GELAKT|LACKIERT)\b.*\b(GLOSS|GLOSSY|GLANS|GLAENZEND)\b|"
     r"\b(GLOSS|GLOSSY)\b.*\b(PAINT|ENAMEL|LACQUER)\b", "paint_gloss", "RAL 7035"),
    (r"\b(PAINT|ENAMEL|LACQUER|LAK|LACK|GELAKT|LACKIERT)\b.*\b(MATTE|MAT|FLAT)\b", "paint_matte", "RAL 7035"),
    (r"\b(PAINT|ENAMEL|LACQUER|LAK|LACK|GELAKT|LACKIERT|PRIMER|RAL ?\d{4})\b", "paint_satin", "RAL 7035"),
    # ---- clear and tinted materials --------------------------------------------------------
    (r"\bFROSTED\b|\bSATINATED\b|\bMATTE? (ACRYLIC|PLEXI|GLASS)", "acrylic_frosted", ""),
    (r"\b(TINTED|SMOKED|GETINT)\b", "glass_tinted", "#5A6470"),
    (r"\b(POLYCARBONATE?|POLYCARBONAAT|POLYCARBONAT|LEXAN|MAKROLON|ACRYLIC|ACRYL|PLEXI\w*|PERSPEX|PMMA)\b",
     "polycarbonate_clear", ""),
    (r"\bGLASS?\b|\bCLEAR\b|\bTRANSPARENT\b|\bGLAS\b", "glass_clear", ""),
    # ---- metals ----------------------------------------------------------------------------
    (r"\bCHROM(E|IUM|ED)?\b|\bVERCHROOMD\b|\bVERCHROMT\b", "chrome", ""),
    (r"\bSTAINLESS.*\bPOLISHED\b|\bPOLISHED\b.*\bSTAINLESS\b|\bMIRROR\b", "stainless_polished", ""),
    (r"\bSTAINLESS\b|\bINOX\b|\bRVS\b|\bEDELSTAHL\b|\bNIROSTA\b|\bSUS ?3\d\d|\bAISI ?3\d\d|\b1 4[3-5]\d\d\b|"
     r"\b(304|316|303|321)L?\b.*\bSTEEL\b|\bDUPLEX\b|\bROESTVAST\b", "stainless_brushed", ""),
    (r"\bTITANIUM\b|\bTITAN\b", "stainless_brushed", ""),
    (r"\bANODI[SZ]ED\b.*\bBLACK\b|\bBLACK\b.*\bANODI[SZ]ED\b|\bSCHWARZ ELOXIERT\b|\bZWART GEANODISEERD\b",
     "aluminium_anodized_black", ""),
    (r"\bANODI[SZ]ED\b.*\b(RED|BLUE|GREEN|GOLD|ORANGE|PURPLE|VIOLET|YELLOW|BRONZE|CHAMPAGNE)\b",
     "aluminium_anodized_color", "#3A5A8C"),
    (r"\bANODI[SZ]ED\b|\bELOXIERT\b|\bELOXAL\b|\bGEANODISEERD\b", "aluminium_anodized", ""),
    (r"\bALUMIN(I?UM|IO)\b|\bALU\b|\bAL (MG|SI|ZN|CU)\b|\bEN ?AW\b|\b(6061|6063|6082|7075|5083|5754|2024)\b",
     "aluminium_machined", ""),
    (r"\bBRASS\b|\bMESSING\b|\bCU ZN\b|\bMS ?58\b", "brass", ""),
    (r"\bBRONZE\b|\bBRONS\b|\bCU SN\b|\bRG ?7\b", "bronze", ""),
    (r"\bCOPPER\b|\bKOPER\b|\bKUPFER\b", "copper", ""),
    (r"\bNICKEL\b|\bVERNIKKELD\b|\bVERNICKELT\b", "nickel_plated", ""),
    (r"\bGALVANI[SZ]ED\b|\bHOT DIP\b|\bHDG\b|\bFEUERVERZINKT\b|\bTHERMISCH VERZINKT\b", "galvanized", ""),
    (r"\bZINC\b|\bZINK\b|\bVERZINKT\b|\bZN\b", "zinc_plated", ""),
    (r"\bCAST IRON\b|\bIRON CAST\b|\bGUSSEISEN\b|\bGIETIJZER\b|\bGJ[LS]\b|\bGG ?\d\d\b|\bGGG ?\d\d\b|\bDUCTILE\b",
     "cast_iron", ""),
    (r"\bBLACK OXIDE\b|\bBRUENIERT\b|\bGEBRUNEERD\b", "black_oxide", ""),
    (r"\bSTEEL\b|\bSTAAL\b|\bSTAHL\b|\bS ?235\w*|\bS ?355\w*|\bC ?45\b|\bST ?37\b|\bST ?52\b|\b42 CR MO 4\b|\bIRON\b",
     "steel_machined", ""),
    (r"\bGOLD\b", "brass", ""),
    (r"\bSILVER\b|\bPLATINUM\b", "chrome", ""),
    # ---- rubber, foam, felt, wood ----------------------------------------------------------
    (r"\bFOAM\b|\bSPONGE\b|\bSCHUIM\w*|\bSCHAUM\w*|\bARMAFLEX\b", "foam", ""),
    (r"\bFELT\b|\bVILT\b|\bFILZ\b", "felt", ""),
    (r"\bRUBBER\b|\bGUMMI\b|\bEPDM\b|\bNBR\b|\bFKM\b|\bVITON\b|\bNEOPRENE?\b|\bSILICONE?\b|\bELASTOMER\b|\bBUNA\b",
     "rubber_black", ""),
    (r"\bWOOD\b|\bOAK\b|\bPINE\b|\bBIRCH\b|\bBEECH\b|\bMAPLE\b|\bPLYWOOD\b|\bMDF\b|\bHOUT\b|\bHOLZ\b|\bMULTIPLEX\b",
     "wood", ""),
    # ---- plastics (coloured: take the CAD colour) -----------------------------------------
    (r"\bPOM\b|\bACETAL\b|\bDELRIN\b|\bHOSTAFORM\b", "pom_white", ""),
    (r"\bPTFE\b|\bTEFLON\b", "plastic_matte", "#F2F2EF"),
    (r"\bPEEK\b", "plastic_matte", "#C8B48C"),
    (r"\b(UHMW|HDPE|LDPE|PE ?\d{3,4}|POLYETHYLENE|POLYETHYLEEN)\w*", "pom_white", ""),
    (r"\bCARBON FIBRE\b|\bCARBON FIBER\b|\bCFRP\b|\bCFK\b", "plastic_gloss", "RAL 9005"),
    (r"\bPLASTIC\w*|\bABS\b|\bNYLON\b|\bPOLYAMIDE?\b|\bPA ?\d{1,2}\b|\bPOLYPROPYLENE?\b|\bPVC\b|\bPOLYURETHANE\b|"
     r"\bPU\b|\bPBT\b|\bPET\b|\bPOLYSTYRENE\b|\bKUNSTSTOFF?\b|\bRESIN\b|\bHARS\b", "plastic_matte", "RAL 9005"),
]

_COMPILED = [(re.compile(p), m, c) for p, m, c in _P]

# Materials whose look comes from the CAD colour (paints and coloured plastics).
COLOURED = {"paint_gloss", "paint_satin", "paint_matte", "powder_coat", "plastic_matte", "plastic_gloss",
            "glass_tinted", "aluminium_anodized_color", "pom_white"}

# Finishes inside an appearance name that switch a plastic to gloss.
_GLOSS = re.compile(r"\b(GLOSS|GLOSSY|SHINY|POLISHED)\b")


def normalise(name: str) -> str:
    """Upper case, umlauts spelled out, accents dropped, words separated by single spaces."""
    s = (name or "").upper()
    s = s.replace("Ä", "AE").replace("Ö", "OE").replace("Ü", "UE").replace("ß", "SS")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[A-Z]+|[0-9]+", s))


def is_placeholder(name: str) -> bool:
    return normalise(name) in PLACEHOLDERS


def lookup(name: str):
    """(material id, colour) for a CAD material or appearance name, or None."""
    s = normalise(name)
    if s in PLACEHOLDERS:
        return None
    for pattern, material, colour in _COMPILED:
        if pattern.search(s):
            if material == "plastic_matte" and _GLOSS.search(s):
                material = "plastic_gloss"
            return material, colour
    return None


def takes_cad_colour(material: str) -> bool:
    return material in COLOURED


def pick(appearance: str, material: str) -> str:
    """The name that decides the look of a part: its appearance when that is a known
    material or finish, else its material, else whichever name there is."""
    if appearance and lookup(appearance):
        return appearance
    if material and lookup(material):
        return material
    if appearance and not is_placeholder(appearance):
        return appearance
    return "" if is_placeholder(material) else material
