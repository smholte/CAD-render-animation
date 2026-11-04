"""Material and appearance names per part, read straight from the STEP file text.

Why not through OpenCascade: its STEP reader does read material names (XCAF materials), but
in the Python binding (OCP 8.0) looking up which part a material belongs to crashes the
process (``FindAttribute`` with the material reference node), and the appearance names
are not kept at all (XCAF gets colours only, no visual materials from STEP). So this module
reads the few entities it needs itself and maps them to products by name.

What is read
------------
* Material names, written by Autodesk (Fusion, Inventor) and by OpenCascade as
  ``PROPERTY_DEFINITION('material property','material name',#product_definition)`` with a
  ``REPRESENTATION('material name',(DESCRIPTIVE_REPRESENTATION_ITEM('Rubber',...)))``, and
  ``MATERIAL_DESIGNATION('Aluminium',(...))`` (AP214/AP242).
* Appearance names: the name of the surface style on a part's body
  (``STYLED_ITEM`` -> ``FILL_AREA_STYLE('Aluminum - Satin',...)``). Autodesk writes its
  appearance names there; most other programs leave them empty.
* Appearance names of single faces (a style on one face of a body, e.g. a Fusion appearance
  dragged onto a face): OpenCascade gives the colour of such a face but not the name, so the
  names are returned by colour (``faces``); a colour used with two names is left out.

AP203 files (``CONFIG_CONTROL_DESIGN``) carry neither; the scan then stops after a quick
look at the file.

    >>> read("model.step")                                         # doctest: +SKIP
    {'Component1': {'material': 'Rubber', 'appearance': 'Rubber - Soft'}, ...}
"""

from __future__ import annotations

import re
from collections import Counter

# entity types this module needs
_WANTED = (
    "PRODUCT", "PRODUCT_DEFINITION_FORMATION", "PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE",
    "PRODUCT_DEFINITION", "PRODUCT_DEFINITION_WITH_ASSOCIATED_DOCUMENTS", "PRODUCT_DEFINITION_SHAPE",
    "SHAPE_DEFINITION_REPRESENTATION", "SHAPE_REPRESENTATION_RELATIONSHIP",
    "PROPERTY_DEFINITION", "PROPERTY_DEFINITION_REPRESENTATION", "REPRESENTATION",
    "DESCRIPTIVE_REPRESENTATION_ITEM", "MATERIAL_DESIGNATION",
    "STYLED_ITEM", "OVER_RIDING_STYLED_ITEM", "PRESENTATION_STYLE_ASSIGNMENT", "PRESENTATION_STYLE_BY_CONTEXT",
    "SURFACE_STYLE_USAGE",
    "SURFACE_SIDE_STYLE", "SURFACE_STYLE_FILL_AREA", "FILL_AREA_STYLE", "FILL_AREA_STYLE_COLOUR", "COLOUR_RGB",
)
# longest names first, so the alternation never stops at a shorter prefix ("PRODUCT" in "PRODUCT_DEFINITION")
_ENTITY = re.compile(
    r"#(\d+)\s*=\s*(" + "|".join(sorted(_WANTED, key=len, reverse=True)) + r"|[A-Z_]*SHAPE_REPRESENTATION)\s*\(")
_STYLE_NAME = re.compile(rb"\s*\(\s*'[^']")


def _worth_reading(data: bytes) -> bool:
    """Quick check (plain byte searches, ~0.1 s for 80 MB): does the file name materials or styles?"""
    if any(data.find(k) >= 0 for k in (b"MATERIAL_DESIGNATION", b"'material", b"'Material", b"'MATERIAL")):
        return True
    for key in (b"COLOUR_RGB", b"FILL_AREA_STYLE", b"SURFACE_SIDE_STYLE"):
        pos = data.find(key)
        tries = 0
        while pos >= 0 and tries < 2000:              # unnamed styles are all alike: a sample is enough
            if _STYLE_NAME.match(data, pos + len(key)):
                return True
            pos = data.find(key, pos + len(key))
            tries += 1
    return False
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[Ee][-+]?\d+)?")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_DIGITS = re.compile(r"\d+")


# --------------------------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------------------------

class Ref(int):
    """An entity reference (#123)."""


def decode(text: str) -> str:
    """A STEP string (between the quotes) as Python text: '' quotes, \\X2\\ and \\X\\ escapes,
    and raw UTF-8 bytes (written by some programs although the standard says ISO 8859-1)."""
    s = text.replace("''", "'")
    if "\\" in s:
        s = re.sub(r"\\X2\\((?:[0-9A-Fa-f]{4})+)\\X0\\", lambda m: bytes.fromhex(m.group(1)).decode("utf-16-be"), s)
        s = re.sub(r"\\X4\\((?:[0-9A-Fa-f]{8})+)\\X0\\", lambda m: bytes.fromhex(m.group(1)).decode("utf-32-be"), s)
        s = re.sub(r"\\X\\([0-9A-Fa-f]{2})", lambda m: chr(int(m.group(1), 16)), s)
        s = re.sub(r"\\S\\(.)", lambda m: chr(ord(m.group(1)) + 128), s)
        s = s.replace("\\\\", "\\")
    try:
        s = s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return s


def parse_args(text: str, pos: int):
    """Parse the parameter list that starts at ``text[pos] == '('``.

    Returns (list, position after the closing parenthesis). Strings become str, references
    Ref, numbers float, lists list, $ and * None, enumerations their name, typed values
    ("POSITIVE_RATIO_MEASURE(930.)") their inner list."""
    assert text[pos] == "("
    stack: list[list] = [[]]
    i = pos + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "'":
            j = i + 1
            while True:
                j = text.index("'", j)
                if j + 1 < n and text[j + 1] == "'":
                    j += 2
                    continue
                break
            stack[-1].append(decode(text[i + 1:j]))
            i = j + 1
        elif c == "#":
            m = _DIGITS.match(text, i + 1)
            stack[-1].append(Ref(int(m.group(0))))
            i = m.end()
        elif c == "(":
            stack.append([])
            i += 1
        elif c == ")":
            done = stack.pop()
            if not stack:
                return done, i + 1
            stack[-1].append(done)
            i += 1
        elif c in "$*":
            stack[-1].append(None)
            i += 1
        elif c == ".":
            if i + 1 < n and text[i + 1].isdigit():
                m = _NUMBER.match(text, i)
                stack[-1].append(float(m.group(0)))
                i = m.end()
            else:
                j = text.index(".", i + 1)
                stack[-1].append(text[i + 1:j])
                i = j + 1
        elif c in "+-" or c.isdigit():
            m = _NUMBER.match(text, i)
            stack[-1].append(float(m.group(0)))
            i = m.end()
        elif c.isalpha() or c == "_":
            m = _WORD.match(text, i)              # typed value: KEYWORD( ... )
            i = m.end()
            while i < n and text[i] in " \t\r\n":
                i += 1
            if i < n and text[i] == "(":
                inner, i = parse_args(text, i)
                stack[-1].append(inner[0] if len(inner) == 1 else inner)
        else:                                     # commas, white space, line breaks
            i += 1
    raise ValueError("unterminated parameter list")


def _entities(text: str):
    """Yield (id, type, args) for the wanted simple entities (not complex '#n=(A()B())' ones)."""
    for m in _ENTITY.finditer(text):
        if m.group(2) == "CONTEXT_DEPENDENT_SHAPE_REPRESENTATION":
            continue                              # an assembly placement, not a part's geometry
        try:
            args, _end = parse_args(text, m.end() - 1)
        except (ValueError, AttributeError, IndexError):
            continue
        yield int(m.group(1)), m.group(2), args


# --------------------------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------------------------

def _text_of(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _refs(value) -> list:
    if isinstance(value, Ref):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, Ref)]
    return []


def read(path: str, faces: dict | None = None) -> dict:
    """{product name: {"material": name or "", "appearance": name or ""}} for the products in
    a STEP file that carry a material or an appearance name. Products whose name is used by
    several products with different materials are left out (no guessing).

    ``faces``: if given, filled with {(r, g, b): appearance name} for styles on single faces
    (sRGB 0-1, rounded to 3 decimals)."""
    with open(path, "rb") as fh:
        data = fh.read()
    if not _worth_reading(data):
        return {}
    return read_text(data.decode("latin-1"), faces)


def read_text(text: str, faces: dict | None = None) -> dict:
    product: dict[int, str] = {}           # PRODUCT -> name (or id when the name is empty)
    formation: dict[int, int] = {}         # formation -> PRODUCT
    pdef: dict[int, int] = {}              # PRODUCT_DEFINITION -> formation
    pds: dict[int, int] = {}               # PRODUCT_DEFINITION_SHAPE -> definition
    rep_items: dict[int, list] = {}        # representation -> items
    rep_of_pds: list[tuple[int, int]] = [] # (PRODUCT_DEFINITION_SHAPE, representation)
    rep_links: list[tuple[int, int]] = []  # plain SHAPE_REPRESENTATION_RELATIONSHIP
    propdef: dict[int, tuple] = {}         # PROPERTY_DEFINITION -> (name, description, definition)
    pdr: list[tuple[int, int]] = []        # (PROPERTY_DEFINITION, representation)
    dri: dict[int, tuple] = {}             # DESCRIPTIVE_REPRESENTATION_ITEM -> (name, description)
    designations: list[tuple] = []         # (material name, [items])
    styled: list[tuple] = []               # ([style assignments], item)
    psa: dict[int, list] = {}
    ssu: dict[int, int] = {}
    sss: dict[int, tuple] = {}
    ssfa: dict[int, int] = {}
    fas: dict[int, tuple] = {}
    fasc: dict[int, tuple] = {}
    rgb: dict[int, str] = {}
    rgb_values: dict[int, tuple] = {}

    for eid, etype, a in _entities(text):
        try:
            if etype == "PRODUCT":
                product[eid] = _text_of(a[1]) or _text_of(a[0])
            elif etype.startswith("PRODUCT_DEFINITION_FORMATION"):
                formation[eid] = a[2]
            elif etype.startswith("PRODUCT_DEFINITION_WITH") or etype == "PRODUCT_DEFINITION":
                pdef[eid] = a[2]
            elif etype == "PRODUCT_DEFINITION_SHAPE":
                pds[eid] = a[2]
            elif etype == "SHAPE_DEFINITION_REPRESENTATION":
                rep_of_pds.append((a[0], a[1]))
            elif etype == "SHAPE_REPRESENTATION_RELATIONSHIP":
                rep_links.append((a[2], a[3]))
            elif etype.endswith("SHAPE_REPRESENTATION") or etype == "REPRESENTATION":
                rep_items[eid] = _refs(a[1])
            elif etype == "PROPERTY_DEFINITION":
                propdef[eid] = (_text_of(a[0]), _text_of(a[1]), a[2])
            elif etype == "PROPERTY_DEFINITION_REPRESENTATION":
                pdr.append((a[0], a[1]))
            elif etype == "DESCRIPTIVE_REPRESENTATION_ITEM":
                dri[eid] = (_text_of(a[0]), _text_of(a[1]))
            elif etype == "MATERIAL_DESIGNATION":
                designations.append((_text_of(a[0]), _refs(a[1])))
            elif etype.endswith("STYLED_ITEM"):
                styled.append((_refs(a[1]), a[2]))
            elif etype.startswith("PRESENTATION_STYLE"):
                psa[eid] = _refs(a[0])
            elif etype == "SURFACE_STYLE_USAGE":
                ssu[eid] = a[1]
            elif etype == "SURFACE_SIDE_STYLE":
                sss[eid] = (_text_of(a[0]), _refs(a[1]))
            elif etype == "SURFACE_STYLE_FILL_AREA":
                ssfa[eid] = a[0]
            elif etype == "FILL_AREA_STYLE":
                fas[eid] = (_text_of(a[0]), _refs(a[1]))
            elif etype == "FILL_AREA_STYLE_COLOUR":
                fasc[eid] = (_text_of(a[0]), a[1])
            elif etype == "COLOUR_RGB":
                rgb[eid] = _text_of(a[0])
                if all(isinstance(v, float) for v in a[1:4]):
                    rgb_values[eid] = (round(a[1], 3), round(a[2], 3), round(a[3], 3))
        except (IndexError, TypeError):
            continue                              # a damaged or unusual entity: skip it

    def name_of_pd(pd: int) -> str:
        return product.get(formation.get(pdef.get(pd, -1), -1), "")

    def pd_of(ref) -> int | None:
        """A product definition from a reference to it or to its PRODUCT_DEFINITION_SHAPE."""
        if ref in pdef:
            return ref
        if ref in pds and pds[ref] in pdef:
            return pds[ref]
        return None

    # ---- materials ------------------------------------------------------------------------------
    materials: dict[int, str] = {}
    for prop, rep in pdr:
        if prop not in propdef:
            continue
        pname, pdesc, definition = propdef[prop]
        label = f"{pname} {pdesc}".lower()
        if "material" not in label or "density" in label:
            continue
        pd = pd_of(definition)
        if pd is None:
            continue
        for item in rep_items.get(rep, ()):
            if item in dri:
                name, desc = dri[item]
                value = name or desc
                if value:
                    materials.setdefault(pd, value)
                    break
    for name, items in designations:
        if not name:
            continue
        for item in items:
            pd = pd_of(item)
            if pd is None and item in propdef:
                pd = pd_of(propdef[item][2])
            if pd is not None:
                materials.setdefault(pd, name)

    # ---- appearances ---------------------------------------------------------------------------
    pd_of_rep: dict[int, int] = {}
    for p, rep in rep_of_pds:
        pd = pd_of(p)
        if pd is not None:
            pd_of_rep.setdefault(rep, pd)
    for r1, r2 in rep_links:                      # a part's SHAPE_REPRESENTATION -> its B-rep
        if r1 in pd_of_rep and r2 not in pd_of_rep:
            pd_of_rep[r2] = pd_of_rep[r1]
        elif r2 in pd_of_rep and r1 not in pd_of_rep:
            pd_of_rep[r1] = pd_of_rep[r2]
    pd_of_item: dict[int, int] = {}
    for rep, items in rep_items.items():
        pd = pd_of_rep.get(rep)
        if pd is not None:
            for item in items:
                pd_of_item.setdefault(item, pd)

    def style_name(assignment: int) -> str:
        for usage in psa.get(assignment, ()):
            side = ssu.get(usage)
            if side not in sss:
                continue
            side_name, elements = sss[side]
            for el in elements:
                fill = ssfa.get(el)
                if fill in fas:
                    fill_name, colours = fas[fill]
                    names = [fill_name, side_name]
                    for c in colours:
                        if c in fasc:
                            names += [fasc[c][0], rgb.get(fasc[c][1], "")]
                    for n in names:
                        if n:
                            return n
            if side_name:
                return side_name
        return ""

    def style_colour(assignment: int):
        for usage in psa.get(assignment, ()):
            side = ssu.get(usage)
            for el in sss.get(side, ("", ()))[1]:
                fill = ssfa.get(el)
                for c in fas.get(fill, ("", ()))[1]:
                    if c in fasc and fasc[c][1] in rgb_values:
                        return rgb_values[fasc[c][1]]
        return None

    looks: dict[int, Counter] = {}
    face_names: dict[tuple, set] = {}
    for assignments, item in styled:
        pd = pd_of_item.get(item)
        for a in assignments:
            n = style_name(a)
            if not n:
                continue
            if pd is not None:
                looks.setdefault(pd, Counter())[n] += 1
            elif faces is not None:              # a style on one face (or another sub-item)
                c = style_colour(a)
                if c is not None:
                    face_names.setdefault(c, set()).add(n)
            break
    if faces is not None:
        for c, names in face_names.items():
            if len(names) == 1:
                faces[c] = next(iter(names))

    # ---- per product name ----------------------------------------------------------------------
    out: dict[str, dict] = {}
    clash: set[str] = set()
    for pd in set(materials) | set(looks):
        name = name_of_pd(pd)
        if not name:
            continue
        entry = {"material": materials.get(pd, ""),
                 "appearance": looks[pd].most_common(1)[0][0] if pd in looks else ""}
        if name in out and out[name] != entry:
            clash.add(name)
        out.setdefault(name, entry)
    for name in clash:
        del out[name]
    return out
