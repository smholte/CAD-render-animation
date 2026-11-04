"""Part-type library: recognise what a part is from its name, and how it should look.

    >>> classify("_MGPM32-75Z_ROD")
    'Chrome rods & linear shafts'
    >>> classify("O-RING 20X2 NBR")
    'Seals & O-rings'
    >>> classify("FRAME")
    ''

``classify`` returns the material group for a part, or "" when the library has nothing to
say (then the CAD material, the CAD colour or "Unsorted" decide). It looks at

* the part's own name: keywords (English, Dutch, German, common misspellings) and vendor
  part numbers (SMC, Festo, igus, SKF, HIWIN, Sick, Rittal...);
* its parent assemblies: a part called "BODY" inside an assembly "CDQ2B32-50DZ" is part of
  a pneumatic cylinder;
* a material in the name ("PLATE RVS", "BLOCK POM BLACK");
* the CAD material and CAD colour: generic shapes (plates, shafts, covers...) give way to a
  known CAD material; paint-type groups take the CAD colour ("Covers & panels #1F4E79").

The data lives in ``part_types_data.py``; this module only matches.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from . import cad_materials
from . import part_types_data as D

LEVELS = ("product", "component", "shape")


@dataclass(frozen=True)
class PartType:
    id: str
    group: str
    level: str
    order: int
    roles: dict = field(default_factory=dict, compare=False, hash=False)
    absorb: str = "shape"


TYPES: dict[str, PartType] = {}
for _i, _t in enumerate(D.TYPES):
    TYPES[_t["id"]] = PartType(_t["id"], _t["group"], _t["level"], _i, dict(_t["roles"]), _t["absorb"])


# --------------------------------------------------------------------------------------------
# keyword index
# --------------------------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Upper case with umlauts spelled out; camelCase split ("BearingHousing" -> "BEARING HOUSING")."""
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text or "")
    s = s.upper().replace("Ä", "AE").replace("Ö", "OE").replace("Ü", "UE").replace("ß", "SS")
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _split_words(spec: str) -> list[str]:
    return [w.strip() for w in spec.split("|") if w.strip()]


class _Index:
    """Keyword lookup for one table: phrases by first word, suffixes and prefixes by 3 letters."""

    def __init__(self):
        self.phrases: dict[str, list] = {}
        self.suffixes: dict[str, list] = {}
        self.prefixes: dict[str, list] = {}

    def add(self, keyword: str, value, order: int) -> None:
        kw = _norm(keyword).strip()
        if kw.startswith("*") and kw.endswith("*"):
            raise ValueError(f"keyword {keyword!r}: use *END or START*, not both")
        if kw.startswith("*"):
            core = kw[1:]
            if len(core) < 3 or not core.isalpha():
                raise ValueError(f"suffix keyword {keyword!r} must be 3+ letters")
            self.suffixes.setdefault(core[-3:], []).append((core, value, order))
        elif kw.endswith("*"):
            core = kw[:-1]
            if len(core) < 3 or not core.isalpha():
                raise ValueError(f"prefix keyword {keyword!r} must be 3+ letters")
            self.prefixes.setdefault(core[:3], []).append((core, value, order))
        else:
            words = tuple(re.findall(r"[A-Z]+|[0-9]+", kw))
            if not words:
                raise ValueError(f"empty keyword {keyword!r}")
            self.phrases.setdefault(words[0], []).append((words, value, order))

    def hits(self, tokens: list):
        """Yield (end, length, order, value) for every keyword found in the tokens.

        ``tokens``: [(word, start, end)] with character positions in the normalised name."""
        words = [t[0] for t in tokens]
        for i, (w, start, end) in enumerate(tokens):
            for phrase, value, order in self.phrases.get(w, ()):
                n = len(phrase)
                if tuple(words[i:i + n]) == phrase:
                    last = tokens[i + n - 1]
                    yield last[2], last[2] - start, order, value
            if len(w) >= 3 and w.isalpha():
                for core, value, order in self.suffixes.get(w[-3:], ()):
                    if len(w) >= len(core) and w.endswith(core):
                        yield end, len(core), order, value
                for core, value, order in self.prefixes.get(w[:3], ()):
                    if len(w) > len(core) and w.startswith(core):
                        yield start + len(core), len(core), order, value


_TYPE_INDEX = _Index()
_CODES: list[tuple[re.Pattern, str, int]] = []
for _t in D.TYPES:
    _order = TYPES[_t["id"]].order
    for _kw in _split_words(_t["words"]):
        _TYPE_INDEX.add(_kw, _t["id"], _order)
    for _c in _t["codes"]:
        _CODES.append((re.compile(_c), _t["id"], _order))

_MAT_INDEX = _Index()
_MAT_CODES: list[tuple[re.Pattern, str, int]] = []
for _i, (_cls, (_words, _codes)) in enumerate(D.MATERIAL_WORDS.items()):
    for _kw in _split_words(_words):
        _MAT_INDEX.add(_kw, _cls, _i)
    for _c in _codes:
        _MAT_CODES.append((re.compile(_c), _cls, _i))

_COLOUR_INDEX = _Index()
for _i, (_name, (_words, _ral)) in enumerate(D.COLOUR_WORDS.items()):
    for _kw in _split_words(_words):
        _COLOUR_INDEX.add(_kw, _name, _i)

_MODULE_INDEX = _Index()
for _kw in _split_words(D.MODULE_WORDS):
    _MODULE_INDEX.add(_kw, "module", 0)

_QUAL_INDEX = _Index()
for _kw in _split_words(D.QUALIFIERS):
    _QUAL_INDEX.add(_kw, "qualifier", 0)

_NOT = [tuple(re.findall(r"[A-Z]+|[0-9]+", _norm(p))) for p in D.NOT_PART_TYPE]
_FILLER = {"AS", "ASM", "ASSY", "ASY", "ASSEMBLY", "SUBASSY", "SUBASSEMBLY", "SUB", "PRT", "PART", "IPT", "IAM",
           "SLDPRT", "SLDASM", "STP", "REV", "LH", "RH", "LEFT", "RIGHT", "COPY", "NEW", "OLD", "MIRROR", "MIR",
           "SAMENSTELLING", "BAUGRUPPE", "ZB", "BG", "SST"}
_WEAK = {_norm(w) for w in D.WEAK_MATERIAL_WORDS}
_PROFILE_SIZE = re.compile(D.PROFILE_SIZE)


# --------------------------------------------------------------------------------------------
# one name
# --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class NameInfo:
    best: str | None = None              # type of the best hit (keyword or code)
    code_product: str | None = None      # a product named by a vendor code in the name
    kw_product: str | None = None        # a product named by a keyword (not the best hit)
    material: str | None = None          # material class named in the name
    colour: str | None = None            # colour word ("black", ...)
    profile_size: bool = False           # "40x40" and nothing else
    module: bool = False                 # names a machine module or station ("...UNIT", "...SYSTEM")
    module_head: bool = False            # ... as its last word ("O-RING FITTING UNIT", not "DRIVE SHAFT")


def _code_text(text: str) -> str:
    """Upper case for vendor codes: like _norm, but without splitting camelCase ("M-20iA")."""
    s = (text or "").upper().replace("Ä", "AE").replace("Ö", "OE").replace("Ü", "UE").replace("ß", "SS")
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _pick_best(hits: list, code_hits: list = ()):
    """The hit that names the part (``hits``: keywords, ``code_hits``: vendor part numbers).

    1. A keyword inside a longer one does not count on its own ("SHAFT" in "SHAFT SEAL").
    2. A generic shape beats a bought product named next to it, in either word order:
       "SENSOR BRACKET" and "BRACKET SENSOR" are both brackets, "FLANGE MOTOR" is a flange.
    3. A vendor part number names a bought component exactly: it beats a word for another
       component or product next to it ("LMUW20 BUSHING" is a Misumi linear bushing, not a plain
       bushing; "MCKL20-5-10 MOTOR SIDE" a coupling). A generic shape word still counts (rule 4).
    4. Otherwise the hit that ends furthest right wins (English and German/Dutch compounds
       put the noun last), then the longest, then the type listed first."""
    everything = list(hits) + list(code_hits)
    keep = [h for h in everything
            if not any(o[1] > h[1] and o[0] - o[1] <= h[0] - h[1] and h[0] <= o[0] for o in everything)]
    levels = {TYPES[h[3]].level for h in keep}
    if "shape" in levels and "product" in levels:
        keep = [h for h in keep if TYPES[h[3]].level != "product"]
    # "PROFILE" next to a bought part names what the part is for ("ANGLE BRACKET PROFILE 45")
    if any(h[3] == "alu_profile" for h in keep) and any(
            h[3] != "alu_profile" and TYPES[h[3]].level != "shape" for h in keep):
        keep = [h for h in keep if h[3] != "alu_profile"]
    codes = {id(h) for h in code_hits}
    if any(id(h) in codes and TYPES[h[3]].level == "component" for h in keep):
        keep = [h for h in keep if id(h) in codes or TYPES[h[3]].level == "shape"]
    return max(keep, key=lambda h: (h[0], h[1], -h[2]))


def _tokens(norm: str) -> list:
    return [(m.group(0), m.start(), m.end()) for m in re.finditer(r"[A-Z]+|[0-9]+", norm)]


def _contains(words: list, phrase: tuple) -> bool:
    n = len(phrase)
    return any(tuple(words[i:i + n]) == phrase for i in range(len(words) - n + 1))


@lru_cache(maxsize=65536)
def analyse(name: str) -> NameInfo:
    """Everything the library can read from one name (no parents, no CAD data)."""
    norm = _norm(name)
    tokens = _tokens(norm)
    words = [t[0] for t in tokens]
    if not words or any(_contains(words, p) for p in _NOT):
        return NameInfo()

    # words that only describe the part ("4-PIN", "2-JAW", "WITH BRAKE") hide the keywords inside them
    quals = [(e - n, e) for e, n, _o, _v in _QUAL_INDEX.hits(tokens)]

    def described(h) -> bool:
        return any(a <= h[0] - h[1] and h[0] <= b for a, b in quals)

    hits = [h for h in _TYPE_INDEX.hits(tokens) if not described(h)]
    code_hits = []
    ctext = _code_text(name)
    for pattern, tid, order in _CODES:
        for m in pattern.finditer(ctext):
            if m.end() > m.start():
                # positions in the code text and the keyword text differ only after a camelCase
                # split; scale to the keyword text so "rightmost" still compares fairly
                end = round(m.end() * len(norm) / max(1, len(ctext)))
                code_hits.append((end, end - round(m.start() * len(norm) / max(1, len(ctext))), order, tid))
    best = None
    best_span = (0, 0)
    if hits or code_hits:
        top = _pick_best(hits, code_hits)
        best, best_span = top[3], (top[0] - top[1], top[0])
    # a module word that is not part of a keyword ("O-RING FITTING UNIT", not "BEARING UNIT")
    spans = [(h[0] - h[1], h[0]) for h in hits + code_hits] + quals
    module_ends = [end for end, length, _o, _v in _MODULE_INDEX.hits(tokens)
                   if not any(a <= end - length and end <= b for a, b in spans)]
    # the last real word: assembly/file suffixes and side or revision letters do not count
    last_word_end = max((t[2] for t in tokens if t[0].isalpha() and len(t[0]) > 1 and t[0] not in _FILLER),
                        default=-1)
    module = bool(module_ends)
    module_head = last_word_end in module_ends

    code_product = None
    products = [h for h in code_hits if TYPES[h[3]].level == "product"]
    if products:
        code_product = max(products, key=lambda h: (h[1], -h[2]))[3]
    kw_product = None
    for h in sorted(hits, key=lambda h: (-h[0], -h[1])):
        if TYPES[h[3]].level == "product" and h[3] != best and not (best_span[0] <= h[0] - h[1] and
                                                                     h[0] <= best_span[1]):
            kw_product = h[3]
            break

    # material named in the name (a weak word like "SS" or "AL" needs another word next to it)
    mats = []
    for end, length, order, cls in _MAT_INDEX.hits(tokens):
        word = norm[end - length:end]
        if word in _WEAK and len([w for w in words if w.isalpha()]) < 2:
            continue
        mats.append((order, cls))
    for pattern, cls, order in _MAT_CODES:
        if pattern.search(ctext):
            mats.append((order, cls))
    material = min(mats)[1] if mats else None
    colours = sorted((h[2], h[3]) for h in _COLOUR_INDEX.hits(tokens))
    colour = colours[0][1] if colours else None

    return NameInfo(best=best, code_product=code_product, kw_product=kw_product, material=material,
                    colour=colour, profile_size=bool(_PROFILE_SIZE.search(ctext)), module=module,
                    module_head=module_head)


@lru_cache(maxsize=65536)
def own_type(name: str) -> str | None:
    """The type a name gives on its own (a vendor code makes generic words part of the product)."""
    info = analyse(name)
    own = info.best
    if info.module_head and not (own and TYPES[own].level == "product"):
        return None                                         # "O-RING FITTING UNIT": a station, not an O-ring
    product = info.code_product or info.kw_product          # a product named in the same name
    if own and product and own != product and own in TYPES[product].roles:
        return TYPES[product].roles[own]                    # "CYLINDER ROD", "_MGPM32-75Z_ROD"
    if own and TYPES[own].level != "shape":
        return own
    if info.code_product:                                   # "_MGPM32-75Z_PLATE": part of the product
        return info.code_product
    if own:
        return own
    if info.profile_size and info.material in (None, "aluminium", "anodised"):
        return "alu_profile"
    return None


def ancestors_of(path: str, assembly: str = "") -> tuple:
    """Names of the parent assemblies, nearest first, from a UID path "Top#1/Sub#2/Part#1"."""
    if path:
        parts = re.split(r"#\d+/", path)
        names = [re.sub(r"#\d+$", "", p) for p in parts[:-1]]
        return tuple(reversed(names))
    return (assembly,) if assembly else ()


@lru_cache(maxsize=65536)
def context_of(ancestors: tuple) -> str | None:
    """The product or bought multi-part item a part sits in: the nearest parent assembly with a
    type. A parent that is a generic shape ("MOTOR.BRACKET.ASSY"), a machine module
    ("INFEED.SYSTEM") or a mechanism named after a part ("BELT DRIVE ASSY") gives no context."""
    for name in ancestors[:8]:
        if analyse(name).module:
            return None
        t = own_type(name)
        if t is None:
            continue
        if TYPES[t].level == "product" or t in D.CONTEXT_COMPONENTS:
            return t
        return None
    return None


def type_of(name: str, path: str = "", assembly: str = "") -> str | None:
    """The part type id for a part (its name in the light of its parent assemblies)."""
    info = analyse(name)
    mine = own_type(name)
    ctx = context_of(ancestors_of(path, assembly))
    if ctx is not None and mine != ctx:
        c = TYPES[ctx]
        role = c.roles.get(info.best) or c.roles.get(mine)
        if role:
            return role
        if mine is None or TYPES[mine].level == "shape" or c.absorb == "all":
            return ctx
    return mine


# --------------------------------------------------------------------------------------------
# groups
# --------------------------------------------------------------------------------------------

def _hex(color: str) -> str:
    return color.upper() if color and re.fullmatch(r"#[0-9A-Fa-f]{6}", color) else ""


def material_group(cls: str, colour_word: str | None = None, color: str = "") -> str:
    group = D.MATERIAL_GROUPS[cls]
    paint = D.GROUPS[group][2]
    if paint:
        if colour_word and D.COLOUR_WORDS[colour_word][1]:
            return f"{group}, {colour_word}"
        if _hex(color):
            return f"{group} {_hex(color)}"
    return group


def group_for_type(tid: str, color: str = "") -> str:
    group = TYPES[tid].group
    if D.GROUPS[group][2] and _hex(color):
        return f"{group} {_hex(color)}"
    return group


@lru_cache(maxsize=65536)
def classify(name: str, path: str = "", assembly: str = "", cad_material: str = "", color: str = "") -> str:
    """Material group for a part from the library, or "" when the library does not know it.

    ``cad_material``: material/appearance name from the CAD file (only names that
    ``cad_materials.lookup`` knows count). ``color``: CAD colour '#RRGGBB' or ''."""
    info = analyse(name)
    tid = type_of(name, path, assembly)
    cad_known = bool(cad_material) and cad_materials.lookup(cad_material) is not None
    if tid is not None and TYPES[tid].level != "shape":
        return group_for_type(tid, color)
    # a generic shape, or nothing: a material in the name, then the CAD material decide
    if info.material:
        return material_group(info.material, info.colour, color)
    if cad_known:
        return ""
    if tid is not None:
        return group_for_type(tid, color)
    return ""


def look_for_group(group: str):
    """(material id, colour) for a group the library makes, or None."""
    if group in D.GROUPS:
        m, c, _ = D.GROUPS[group]
        return m, c
    m = re.fullmatch(r"(.*) (#[0-9A-Fa-f]{6})", group)
    if m and m.group(1) in D.GROUPS and D.GROUPS[m.group(1)][2]:
        return D.GROUPS[m.group(1)][2], m.group(2).upper()
    m = re.fullmatch(r"(.*), ([a-z]+)", group)
    if m and m.group(1) in D.GROUPS and D.GROUPS[m.group(1)][2] and m.group(2) in D.COLOUR_WORDS:
        ral = D.COLOUR_WORDS[m.group(2)][1]
        if ral:
            return D.GROUPS[m.group(1)][2], ral
    return None


# --------------------------------------------------------------------------------------------
# CAD material groups
# --------------------------------------------------------------------------------------------

def cad_group(cad_material: str, color: str = "") -> str:
    """Group name for a part sorted by its CAD material: the CAD name itself, plus the CAD
    colour for paints and coloured plastics ("ABS Plastic #1A1A1A"). "" for unknown names."""
    hit = cad_materials.lookup(cad_material) if cad_material else None
    if not hit:
        return ""
    if cad_materials.takes_cad_colour(hit[0]) and _hex(color):
        return f"{cad_material} {_hex(color)}"
    return cad_material


def cad_look_for_group(group: str):
    """(material id, colour) for a group made by ``cad_group``, or None."""
    m = re.fullmatch(r"(.*) (#[0-9A-Fa-f]{6})", group)
    base, hexcol = (m.group(1), m.group(2).upper()) if m else (group, "")
    hit = cad_materials.lookup(base)
    if not hit:
        return None
    mat, colour = hit
    if not cad_materials.takes_cad_colour(mat):
        return mat, ""
    if hexcol:
        return mat, hexcol
    # "Paint - Enamel Glossy (Red)" without a CAD colour: the colour word in the name
    for h in sorted(_COLOUR_INDEX.hits(_tokens(_norm(base))), key=lambda h: h[2]):
        ral = D.COLOUR_WORDS[h[3]][1]
        if ral:
            return mat, ral
    return mat, colour


def describe(name: str, path: str = "", assembly: str = "") -> str:
    """Short text for the UI: what the library thinks the part is."""
    tid = type_of(name, path, assembly)
    return TYPES[tid].group if tid else "No part type"
