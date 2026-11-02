"""Recognise standard parts (bolts, nuts, washers, pins...) from their names.

Works on names as they come out of Inventor Content Center, Fusion, McMaster
style descriptions, Misumi codes and hand-typed names in English, Dutch and
German. No CAD data is needed: only the part name.

    >>> info = parse("ISO 4017 M12 x 40 - 8.8 HDG")
    >>> (info.kind, info.size, info.length, info.property_class, info.finish)
    ('hex_bolt', 'M12', 40.0, '8.8', 'galvanized')
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache

# --------------------------------------------------------------------------
# Types and families
# --------------------------------------------------------------------------

KIND_LABELS = {
    "hex_bolt": "Hex bolt",
    "socket_cap": "Socket cap screw",
    "socket_low_head": "Low head socket screw",
    "countersunk_socket": "Countersunk socket screw",
    "button_socket": "Button head screw",
    "set_screw": "Set screw",
    "pan_head": "Pan head screw",
    "countersunk_head": "Countersunk screw",
    "cheese_head": "Cheese head screw",
    "flange_bolt": "Flange bolt",
    "eye_bolt": "Eye bolt",
    "t_bolt": "T-head bolt",
    "threaded_rod": "Threaded rod",
    "stud": "Stud bolt",
    "self_tapping": "Self-tapping screw",
    "bolt": "Bolt / screw",
    "hex_nut": "Hex nut",
    "thin_nut": "Thin nut",
    "lock_nut": "Lock nut",
    "flange_nut": "Flange nut",
    "cap_nut": "Cap nut",
    "castle_nut": "Castle nut",
    "square_nut": "Square nut",
    "t_slot_nut": "T-slot nut",
    "weld_nut": "Weld nut",
    "eye_nut": "Eye nut",
    "nut": "Nut",
    "washer": "Washer",
    "spring_washer": "Spring washer",
    "lock_washer": "Lock washer",
    "taper_washer": "Taper washer",
    "dowel_pin": "Dowel pin",
    "spring_pin": "Spring pin",
    "split_pin": "Split pin",
    "clevis_pin": "Clevis pin",
    "circlip": "Circlip",
    "key": "Parallel key",
    "rivet": "Rivet",
    "grease_nipple": "Grease nipple",
}

FAMILY = {k: "screw" for k in (
    "hex_bolt", "socket_cap", "socket_low_head", "countersunk_socket", "button_socket",
    "set_screw", "pan_head", "countersunk_head", "cheese_head", "flange_bolt", "eye_bolt",
    "t_bolt", "threaded_rod", "stud", "self_tapping", "bolt")}
FAMILY.update({k: "nut" for k in (
    "hex_nut", "thin_nut", "lock_nut", "flange_nut", "cap_nut", "castle_nut", "square_nut",
    "t_slot_nut", "weld_nut", "eye_nut", "nut")})
FAMILY.update({k: "washer" for k in ("washer", "spring_washer", "lock_washer", "taper_washer")})
FAMILY.update({k: "pin" for k in ("dowel_pin", "spring_pin", "split_pin", "clevis_pin", "circlip", "key", "rivet")})
FAMILY["grease_nipple"] = "other"

# Finish used when the name does not say. Socket screws and set screws are
# almost always black oxide; everything else stays unknown ("default" group).
TYPE_DEFAULT_FINISH = {
    "socket_cap": "black",
    "socket_low_head": "black",
    "countersunk_socket": "black",
    "button_socket": "black",
    "set_screw": "black",
}

FINISH_LABELS = {
    "black": "Black oxide",
    "galvanized": "Hot-dip galvanized",
    "zinc": "Zinc plated",
    "zinc_flake": "Zinc flake (Geomet/Delta)",
    "stainless": "Stainless steel",
    "brass": "Brass",
    "aluminium": "Aluminium",
    "plastic": "Plastic / nylon",
    "plain": "Bright steel",
}

# --------------------------------------------------------------------------
# Standards table: (body, number) -> kind
# --------------------------------------------------------------------------

_STD = {
    # hex bolts / screws
    ("DIN", "931"): "hex_bolt", ("DIN", "933"): "hex_bolt", ("DIN", "960"): "hex_bolt",
    ("DIN", "961"): "hex_bolt", ("DIN", "601"): "hex_bolt", ("DIN", "7990"): "hex_bolt",
    ("DIN", "6914"): "hex_bolt", ("ISO", "4014"): "hex_bolt", ("ISO", "4016"): "hex_bolt",
    ("ISO", "4017"): "hex_bolt", ("ISO", "4018"): "hex_bolt", ("ISO", "8765"): "hex_bolt",
    ("ISO", "8676"): "hex_bolt", ("EN", "14399"): "hex_bolt", ("EN", "15048"): "hex_bolt",
    ("EN", "24014"): "hex_bolt", ("EN", "24017"): "hex_bolt",
    # socket screws
    ("DIN", "912"): "socket_cap", ("ISO", "4762"): "socket_cap", ("ISO", "21269"): "socket_cap",
    ("DIN", "7984"): "socket_low_head", ("DIN", "6912"): "socket_low_head",
    ("DIN", "7991"): "countersunk_socket", ("ISO", "10642"): "countersunk_socket",
    ("ISO", "7380"): "button_socket", ("ISO", "7379"): "socket_cap",
    # set screws
    ("DIN", "913"): "set_screw", ("DIN", "914"): "set_screw", ("DIN", "915"): "set_screw",
    ("DIN", "916"): "set_screw", ("DIN", "417"): "set_screw", ("DIN", "551"): "set_screw",
    ("DIN", "553"): "set_screw", ("ISO", "4026"): "set_screw", ("ISO", "4027"): "set_screw",
    ("ISO", "4028"): "set_screw", ("ISO", "4029"): "set_screw", ("ISO", "4766"): "set_screw",
    ("ISO", "7434"): "set_screw", ("ISO", "7435"): "set_screw", ("ISO", "7436"): "set_screw",
    # other head types
    ("DIN", "7985"): "pan_head", ("ISO", "7045"): "pan_head", ("ISO", "1580"): "pan_head",
    ("ISO", "14583"): "pan_head", ("DIN", "965"): "countersunk_head", ("ISO", "7046"): "countersunk_head",
    ("DIN", "963"): "countersunk_head", ("ISO", "2009"): "countersunk_head", ("ISO", "14581"): "countersunk_head",
    ("DIN", "966"): "countersunk_head", ("ISO", "7047"): "countersunk_head",
    ("DIN", "84"): "cheese_head", ("ISO", "1207"): "cheese_head",
    ("DIN", "6921"): "flange_bolt", ("EN", "1665"): "flange_bolt", ("ISO", "4162"): "flange_bolt",
    ("ISO", "15071"): "flange_bolt",
    ("DIN", "444"): "eye_bolt", ("DIN", "580"): "eye_bolt", ("ISO", "3266"): "eye_bolt",
    ("DIN", "186"): "t_bolt", ("DIN", "188"): "t_bolt", ("DIN", "261"): "t_bolt", ("DIN", "787"): "t_bolt",
    ("DIN", "975"): "threaded_rod", ("DIN", "976"): "threaded_rod",
    ("DIN", "938"): "stud", ("DIN", "939"): "stud", ("DIN", "835"): "stud", ("DIN", "940"): "stud",
    ("DIN", "7981"): "self_tapping", ("DIN", "7982"): "self_tapping", ("DIN", "7983"): "self_tapping",
    ("DIN", "7500"): "self_tapping", ("DIN", "7504"): "self_tapping", ("ISO", "7049"): "self_tapping",
    ("ISO", "7050"): "self_tapping", ("ISO", "15480"): "self_tapping", ("ISO", "15481"): "self_tapping",
    # nuts
    ("DIN", "934"): "hex_nut", ("DIN", "555"): "hex_nut", ("DIN", "6915"): "hex_nut",
    ("ISO", "4032"): "hex_nut", ("ISO", "4033"): "hex_nut", ("ISO", "4034"): "hex_nut",
    ("ISO", "8673"): "hex_nut", ("ISO", "8674"): "hex_nut", ("EN", "24032"): "hex_nut",
    ("DIN", "439"): "thin_nut", ("DIN", "936"): "thin_nut", ("ISO", "4035"): "thin_nut", ("ISO", "8675"): "thin_nut",
    ("DIN", "985"): "lock_nut", ("DIN", "982"): "lock_nut", ("DIN", "980"): "lock_nut",
    ("ISO", "10511"): "lock_nut", ("ISO", "7040"): "lock_nut", ("ISO", "7042"): "lock_nut",
    ("ISO", "10512"): "lock_nut", ("ISO", "7719"): "lock_nut", ("DIN", "1804"): "lock_nut",
    ("DIN", "981"): "lock_nut",
    ("DIN", "6923"): "flange_nut", ("EN", "1661"): "flange_nut", ("ISO", "4161"): "flange_nut",
    ("DIN", "1587"): "cap_nut", ("DIN", "917"): "cap_nut", ("DIN", "986"): "cap_nut",
    ("DIN", "935"): "castle_nut", ("DIN", "937"): "castle_nut", ("DIN", "979"): "castle_nut",
    ("DIN", "557"): "square_nut", ("DIN", "562"): "square_nut", ("DIN", "508"): "t_slot_nut",
    ("DIN", "928"): "weld_nut", ("DIN", "929"): "weld_nut",
    ("DIN", "582"): "eye_nut",
    # washers
    ("DIN", "125"): "washer", ("DIN", "126"): "washer", ("DIN", "9021"): "washer", ("DIN", "433"): "washer",
    ("DIN", "7349"): "washer", ("DIN", "1440"): "washer", ("DIN", "988"): "washer", ("DIN", "7989"): "washer",
    ("DIN", "6916"): "washer", ("DIN", "6340"): "washer", ("DIN", "522"): "washer",
    ("ISO", "7089"): "washer", ("ISO", "7090"): "washer", ("ISO", "7091"): "washer",
    ("ISO", "7092"): "washer", ("ISO", "7093"): "washer", ("ISO", "7094"): "washer",
    ("EN", "14399"): "hex_bolt",
    ("DIN", "127"): "spring_washer", ("DIN", "128"): "spring_washer", ("DIN", "7980"): "spring_washer",
    ("DIN", "6796"): "spring_washer", ("DIN", "2093"): "spring_washer",
    ("DIN", "6797"): "lock_washer", ("DIN", "6798"): "lock_washer", ("DIN", "25201"): "lock_washer",
    ("DIN", "434"): "taper_washer", ("DIN", "435"): "taper_washer", ("DIN", "6918"): "taper_washer",
    # pins, clips, keys, rivets
    ("DIN", "7"): "dowel_pin", ("DIN", "6325"): "dowel_pin", ("ISO", "2338"): "dowel_pin",
    ("ISO", "8734"): "dowel_pin", ("ISO", "8735"): "dowel_pin", ("DIN", "1"): "dowel_pin",
    ("ISO", "2339"): "dowel_pin", ("ISO", "8733"): "dowel_pin",
    ("DIN", "1481"): "spring_pin", ("DIN", "7346"): "spring_pin", ("ISO", "8752"): "spring_pin",
    ("ISO", "13337"): "spring_pin", ("ISO", "8750"): "spring_pin", ("ISO", "8748"): "spring_pin",
    ("DIN", "94"): "split_pin", ("ISO", "1234"): "split_pin",
    ("DIN", "1444"): "clevis_pin", ("DIN", "1434"): "clevis_pin", ("ISO", "2341"): "clevis_pin",
    ("DIN", "1443"): "clevis_pin",
    ("DIN", "471"): "circlip", ("DIN", "472"): "circlip", ("DIN", "6799"): "circlip",
    ("DIN", "983"): "circlip", ("DIN", "984"): "circlip",
    ("DIN", "6885"): "key", ("DIN", "6888"): "key", ("ISO", "2491"): "key",
    ("DIN", "7337"): "rivet", ("ISO", "15977"): "rivet", ("ISO", "15983"): "rivet", ("DIN", "660"): "rivet",
    ("DIN", "661"): "rivet", ("DIN", "7338"): "rivet",
    ("DIN", "71412"): "grease_nipple", ("DIN", "3404"): "grease_nipple", ("DIN", "3405"): "grease_nipple",
}

# Keyword phrases (already upper case, words separated by single spaces).
# Checked in order: more specific phrases first.
_KEYWORDS: list[tuple[str, str]] = [
    # screws: head types first, so "flat head socket screw" is countersunk
    ("LOW HEAD", "socket_low_head"),
    ("BUTTON HEAD", "button_socket"), ("BHCS", "button_socket"), ("BOLKOP", "button_socket"),
    ("LINSENKOPF", "button_socket"),
    ("FLAT HEAD", "countersunk_socket"), ("FHCS", "countersunk_socket"), ("COUNTERSUNK", "countersunk_socket"),
    ("VERZONKEN", "countersunk_socket"), ("SENKKOPF", "countersunk_socket"), ("SENKSCHRAUBE", "countersunk_socket"),
    ("SET SCREW", "set_screw"), ("SETSCREW", "set_screw"), ("GRUB", "set_screw"), ("STELSCHROEF", "set_screw"),
    ("MADENSCHRAUBE", "set_screw"), ("GEWINDESTIFT", "set_screw"), ("SSS", "set_screw"),
    ("SOCKET HEAD CAP", "socket_cap"), ("SOCKET HEAD", "socket_cap"), ("SOCKET CAP", "socket_cap"),
    ("SOCKET SCREW", "socket_cap"), ("SHCS", "socket_cap"),
    ("INBUS", "socket_cap"), ("INBUSBOUT", "socket_cap"), ("INBUSSCHROEF", "socket_cap"),
    ("BINNENZESKANT", "socket_cap"), ("INNENSECHSKANT", "socket_cap"), ("CILINDERKOPSCHROEF", "socket_cap"),
    ("ZYLINDERSCHRAUBE", "socket_cap"), ("CAP SCREW", "socket_cap"), ("CAPSCREW", "socket_cap"),
    ("ALLEN", "socket_cap"),
    ("PAN HEAD", "pan_head"), ("CHEESE HEAD", "cheese_head"),
    ("FLANGE BOLT", "flange_bolt"), ("FLANGE SCREW", "flange_bolt"), ("FLENSBOUT", "flange_bolt"),
    ("EYE BOLT", "eye_bolt"), ("EYEBOLT", "eye_bolt"), ("OOGBOUT", "eye_bolt"), ("RINGSCHRAUBE", "eye_bolt"),
    ("HAMMERKOPF", "t_bolt"), ("T BOLT", "t_bolt"), ("HAMERKOPBOUT", "t_bolt"),
    ("THREADED ROD", "threaded_rod"), ("ALL THREAD", "threaded_rod"), ("DRAADEIND", "threaded_rod"),
    ("GEWINDESTANGE", "threaded_rod"), ("STUD BOLT", "stud"), ("STUD", "stud"), ("TAPEIND", "stud"),
    ("STIFTSCHRAUBE", "stud"), ("SELF TAPPING", "self_tapping"), ("PARKER", "self_tapping"),
    ("BLECHSCHRAUBE", "self_tapping"), ("HEX BOLT", "hex_bolt"), ("HEX SCREW", "hex_bolt"),
    ("HEX HEAD", "hex_bolt"), ("HHCS", "hex_bolt"), ("ZESKANTBOUT", "hex_bolt"), ("TAPBOUT", "hex_bolt"),
    ("SECHSKANTSCHRAUBE", "hex_bolt"), ("SECHSKANT SCHRAUBE", "hex_bolt"),
    # nuts (before generic nut / bolt)
    ("NYLOC", "lock_nut"), ("LOCKNUT", "lock_nut"), ("LOCK NUT", "lock_nut"), ("BORGMOER", "lock_nut"),
    ("SICHERUNGSMUTTER", "lock_nut"), ("STOPMOER", "lock_nut"), ("FLANGE NUT", "flange_nut"),
    ("FLENSMOER", "flange_nut"), ("BUNDMUTTER", "flange_nut"), ("CAP NUT", "cap_nut"), ("ACORN NUT", "cap_nut"),
    ("DOPMOER", "cap_nut"), ("HUTMUTTER", "cap_nut"), ("CASTLE NUT", "castle_nut"), ("KROONMOER", "castle_nut"),
    ("KRONENMUTTER", "castle_nut"), ("SQUARE NUT", "square_nut"), ("VIERKANTMOER", "square_nut"),
    ("T NUT", "t_slot_nut"), ("T SLOT NUT", "t_slot_nut"), ("TNUT", "t_slot_nut"), ("NUTENSTEIN", "t_slot_nut"),
    ("SLOT NUT", "t_slot_nut"), ("T MOER", "t_slot_nut"), ("WELD NUT", "weld_nut"), ("LASMOER", "weld_nut"),
    ("EYE NUT", "eye_nut"), ("OOGMOER", "eye_nut"), ("THIN NUT", "thin_nut"), ("JAM NUT", "thin_nut"),
    ("CONTRAMOER", "thin_nut"), ("HEX NUT", "hex_nut"), ("ZESKANTMOER", "hex_nut"), ("SECHSKANTMUTTER", "hex_nut"),
    # washers
    ("SPRING WASHER", "spring_washer"), ("SPLIT WASHER", "spring_washer"), ("VEERRING", "spring_washer"),
    ("FEDERRING", "spring_washer"), ("TELLERFEDER", "spring_washer"), ("DISC SPRING", "spring_washer"),
    ("NORD LOCK", "lock_washer"), ("NORDLOCK", "lock_washer"), ("LOCK WASHER", "lock_washer"),
    ("TOOTHED WASHER", "lock_washer"), ("TANDVEERRING", "lock_washer"), ("FAECHERSCHEIBE", "lock_washer"),
    ("TAPER WASHER", "taper_washer"), ("WIGGESCHEIBE", "taper_washer"), ("KEILSCHEIBE", "taper_washer"),
    ("WASHER", "washer"), ("SLUITRING", "washer"), ("VULRING", "washer"), ("ONDERLEGRING", "washer"),
    ("UNTERLEGSCHEIBE", "washer"), ("SCHEIBE", "washer"),
    # pins / clips / keys / rivets
    ("SPRING PIN", "spring_pin"), ("ROLL PIN", "spring_pin"), ("SPANSTIFT", "spring_pin"),
    ("SPANPEN", "spring_pin"), ("BUSSTIFT", "spring_pin"), ("SPLIT PIN", "split_pin"), ("COTTER PIN", "split_pin"),
    ("SPLITPEN", "split_pin"), ("SPLINT", "split_pin"), ("CLEVIS PIN", "clevis_pin"), ("BOLZEN", "clevis_pin"),
    ("DOWEL", "dowel_pin"), ("PASPEN", "dowel_pin"), ("ZYLINDERSTIFT", "dowel_pin"), ("PASSTIFT", "dowel_pin"),
    ("CIRCLIP", "circlip"), ("RETAINING RING", "circlip"), ("SNAP RING", "circlip"), ("SEEGER", "circlip"),
    ("BORGVEER", "circlip"), ("SICHERUNGSRING", "circlip"), ("E CLIP", "circlip"), ("SEEGERRING", "circlip"),
    ("PARALLEL KEY", "key"), ("FEATHER KEY", "key"), ("PASSFEDER", "key"), ("SPIE", "key"),
    ("BLIND RIVET", "rivet"), ("POP RIVET", "rivet"), ("RIVET", "rivet"), ("KLINKNAGEL", "rivet"),
    ("BLINDKLINKNAGEL", "rivet"), ("BLINDNIET", "rivet"), ("POPNAGEL", "rivet"),
    ("GREASE NIPPLE", "grease_nipple"), ("GREASE FITTING", "grease_nipple"), ("SMEERNIPPEL", "grease_nipple"),
    ("SCHMIERNIPPEL", "grease_nipple"),
    # generic last
    ("NUT", "nut"), ("MOER", "nut"), ("MUTTER", "nut"),
    ("BOLT", "bolt"), ("BOUT", "bolt"), ("SCREW", "bolt"), ("SCHROEF", "bolt"), ("SCHRAUBE", "bolt"),
]

# Words that look like a keyword but are not standard parts.
_NOT_FASTENER = {
    "BOLT HOLE", "NUT PLATE", "WASHER PLATE", "SCREW CONVEYOR", "BALL SCREW", "BALLSCREW", "LEAD SCREW",
    "LEADSCREW", "SCREW JACK", "KOGELOMLOOPSPINDEL", "KUGELGEWINDETRIEB", "NUT HOUSING", "NUT BRACKET",
    "SPINDLE NUT", "BALL NUT", "SCREW SUPPORT", "BOLT CIRCLE", "NUT RUNNER", "NUTRUNNER", "SCREW DRIVER",
    "SCREWDRIVER", "NUT DRIVER",
}

# Misumi style codes, e.g. CB6-20 (black oxide), SCB6-20 (stainless), CBM6-20
_MISUMI = [
    (re.compile(r"^(S?)CB(?:M|S|ST)?(\d{1,2})-(\d{1,3})\b"), "socket_cap"),
    (re.compile(r"^(S?)FB(\d{1,2})-(\d{1,3})\b"), "countersunk_socket"),
    (re.compile(r"^(S?)BB(\d{1,2})-(\d{1,3})\b"), "button_socket"),
    (re.compile(r"^(S?)HB(\d{1,2})-(\d{1,3})\b"), "hex_bolt"),
]

_ALLOWED_DECIMAL_SIZES = {"1.2", "1.4", "1.6", "1.7", "2.2", "2.3", "2.5", "2.6", "3.5", "4.5"}
_PROPERTY_CLASSES = ("12.9", "10.9", "9.8", "8.8", "6.8", "5.8", "5.6", "4.8", "4.6")

_FINISH_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("stainless", re.compile(
        r"(?<![A-Z0-9])(A[1-5](?:[- ]?(?:50|70|80|100))?|RVS|INOX|STAINLESS|SS|SUS\s?\d{3}L?|SST|"
        r"1\.4301|1\.4307|1\.4401|1\.4404|1\.4571|1\.4462|AISI\s?3\d\d|18[- ]8|EDELSTAHL|NIROSTA|V2A|V4A)(?![A-Z0-9])")),
    ("galvanized", re.compile(
        r"(?<![A-Z0-9])(HDG|TZN|THV|FZV|HOT[- ]?DIP|HOTDIP|GALV|GALVANI[SZ]ED|THERMISCH VERZINKT|"
        r"FEUERVERZINKT|TH\.? ?VERZ|DOMPELVERZINKT|SHERARDI[SZ]ED)(?![A-Z0-9])")),
    ("zinc_flake", re.compile(r"(?<![A-Z0-9])(GEOMET|DACROMET|DELTA[- ]?(?:TONE|PROTEKT|SEAL)|ZINC[- ]?FLAKE|ZNFLAKE|FLZN)(?![A-Z0-9])")),
    ("zinc", re.compile(
        r"(?<![A-Z0-9])(ZN|ZNNI|ZN[- ]?NI|FZB|FZY|FZN|GVZ|ELVZ|EL\.? ?VERZ|ZINC|ZINC[- ]?PLATED|ZINKED|"
        r"VERZINKT|VERZ|VZ|GALVANISCH VERZINKT|YELLOW ZINC|BLUE ZINC|BLAUW VERZINKT)(?![A-Z0-9])")),
    ("black", re.compile(
        r"(?<![A-Z0-9])(BLACK|BLK|ZWART|SCHWARZ|BRUENIERT|BRÜNIERT|GEBRUNEERD|BRUNIERT|BLACK[- ]?OXIDE|"
        r"BLACKENED|PHOSPHATED|GEFOSFATEERD|PHOSPHATIERT|ZNPHOS)(?![A-Z0-9])")),
    ("brass", re.compile(r"(?<![A-Z0-9])(BRASS|MESSING|CUZN\d*|MS58)(?![A-Z0-9])")),
    ("aluminium", re.compile(r"(?<![A-Z0-9])(ALUMINIUM|ALUMINUM|ALU)(?![A-Z0-9])")),
    ("plastic", re.compile(r"(?<![A-Z0-9])(NYLON|POLYAMIDE|PA6|PA66|PA 6|PA 66|PEEK|PVC|POM|PLASTIC|KUNSTSTOF)(?![A-Z0-9])")),
    ("plain", re.compile(r"(?<![A-Z0-9])(PLAIN|BRIGHT|UNPLATED|BLANK|BLANKE|ONBEHANDELD)(?![A-Z0-9])")),
]

_STD_RE = re.compile(r"(?<![A-Z])(DIN|ISO|EN|NEN|NF E|UNI)[ _\-.]*(\d{1,5})(?![\d])")
_SIZE_RE = re.compile(r"(?<![A-Z0-9])M\s?(\d{1,2})(?:[.,](\d))?(?![\d])")
_DIMS_AFTER_SIZE_RE = re.compile(r"^\s*[X×*]\s*(\d{1,4}(?:[.,]\d+)?)(?:\s*(?:MM)?\s*[X×*]\s*(\d{1,4}(?:[.,]\d+)?))?")
_LEN_SUFFIX_RE = re.compile(r"^[.\-_ ]\s*(\d{1,4})\s*(?:L|MM|LG)(?![A-Z0-9])")
_CLASS_RE = re.compile(r"(?<![\dA-Z.])(" + "|".join(re.escape(c) for c in _PROPERTY_CLASSES) + r")(?![\d])")


@dataclass
class FastenerInfo:
    kind: str
    family: str
    label: str
    standard: str | None = None
    size: str | None = None
    length: float | None = None
    property_class: str | None = None
    finish: str | None = None
    finish_source: str | None = None   # "name", "class", "type" or None
    matched_by: str = "keyword"         # "standard", "keyword" or "vendor"

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def finish_or_default(self) -> str:
        return self.finish or "default"


def _normalise(name: str) -> str:
    s = (name or "").upper()
    s = s.replace("Ü", "UE").replace("Ö", "OE").replace("Ä", "AE").replace("ß", "SS")
    return s


def _words(s: str) -> str:
    """'BOLT.M4.8L' -> ' BOLT M4 8L ' (for keyword phrase matching)."""
    return " " + " ".join(re.findall(r"[A-Z0-9]+", s)) + " "


def _find_standard(s: str):
    found = []
    for m in _STD_RE.finditer(s):
        body = m.group(1).replace(" ", "")
        if body == "NFE":
            body = "NF E"
        num = m.group(2)
        found.append((body, num))
    # prefer ISO, then EN, then DIN
    order = {"ISO": 0, "EN": 1, "DIN": 2}
    found.sort(key=lambda x: order.get(x[0], 9))
    for body, num in found:
        kind = _STD.get((body, num))
        if kind:
            return f"{body} {num}", kind
    return None, None


def _find_size_length(s: str):
    for m in _SIZE_RE.finditer(s):
        whole, dec = m.group(1), m.group(2)
        size = whole
        rest_start = m.end()
        if dec is not None:
            cand = f"{whole}.{dec}"
            if cand in _ALLOWED_DECIMAL_SIZES:
                size = cand
            else:
                # 'M4.8L' -> M4, then '.8L' is the length
                rest_start = m.start(2) - 1
        length = None
        rest = s[rest_start:]
        dm = _DIMS_AFTER_SIZE_RE.match(rest)
        if dm:
            first = float(dm.group(1).replace(",", "."))
            second = float(dm.group(2).replace(",", ".")) if dm.group(2) else None
            if second is not None:
                length = second            # M12 x 1.5 x 40: pitch, then length
            elif first < 4 and not first.is_integer():
                length = None              # M3 x 0.5: only the pitch
            else:
                length = first
        else:
            lm = _LEN_SUFFIX_RE.match(rest)
            if lm:
                length = float(lm.group(1))
        return f"M{size}", length
    return None, None


def _find_finish(s: str):
    for finish, pattern in _FINISH_PATTERNS:
        if pattern.search(s):
            return finish
    return None


def _find_class(s: str):
    m = _CLASS_RE.search(s)
    return m.group(1) if m else None


@lru_cache(maxsize=65536)
def parse(name: str) -> FastenerInfo | None:
    """Recognise a standard part from its name. Returns None if it is not one.

    Cached: an assembly repeats the same bolt name hundreds of times. Treat the
    result as read-only.
    """
    s = _normalise(name)
    if not s.strip():
        return None
    words = _words(s)
    for phrase in _NOT_FASTENER:
        if f" {phrase} " in words:
            return None

    standard, kind = _find_standard(s)
    matched_by = "standard" if kind else "keyword"

    misumi_stainless = False
    if kind is None:
        compact = s.strip().lstrip("~_ ")
        for pattern, k in _MISUMI:
            m = pattern.match(compact)
            if m:
                kind, matched_by = k, "vendor"
                misumi_stainless = bool(m.group(1))
                break

    if kind is None:
        for phrase, k in _KEYWORDS:
            if f" {phrase} " in words:
                kind = k
                break

    if kind is None:
        return None

    size, length = _find_size_length(s)
    if matched_by == "vendor" and size is None:
        m = re.search(r"(\d{1,2})-(\d{1,3})", s)
        if m:
            size, length = f"M{m.group(1)}", float(m.group(2))

    pclass = _find_class(s)
    finish = _find_finish(s)
    finish_source = "name" if finish else None
    if finish is None and misumi_stainless:
        finish, finish_source = "stainless", "name"
    if finish is None and matched_by == "vendor":
        finish, finish_source = "black", "type"
    if finish is None and pclass == "12.9":
        finish, finish_source = "black", "class"
    if finish is None and kind in TYPE_DEFAULT_FINISH:
        finish, finish_source = TYPE_DEFAULT_FINISH[kind], "type"

    return FastenerInfo(
        kind=kind,
        family=FAMILY.get(kind, "other"),
        label=KIND_LABELS.get(kind, kind),
        standard=standard,
        size=size,
        length=length,
        property_class=pclass,
        finish=finish,
        finish_source=finish_source,
        matched_by=matched_by,
    )


def describe(info: FastenerInfo | None) -> str:
    """Short human text, e.g. 'Hex bolt M12x40, 8.8, Hot-dip galvanized'."""
    if info is None:
        return "Not a standard part"
    bits = [info.label]
    size = info.size or ""
    if size and info.length:
        size += f"x{info.length:g}"
    if size:
        bits[0] += f" {size}"
    if info.standard:
        bits.append(info.standard)
    if info.property_class:
        bits.append(info.property_class)
    bits.append(FINISH_LABELS.get(info.finish, "finish not given") if info.finish else "finish not given")
    return ", ".join(bits)
