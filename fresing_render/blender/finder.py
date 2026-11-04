"""3 Looks: find parts by name, put them in a group, turn a search into a rule, suggest words.

A search is one or more words; a part name must contain all of them (any case). A word may
hold * for "any text" (``M6*20``). Results are one row per part name with the number of placed
parts that carry it, so 24 identical O-rings are one tick.
"""

from __future__ import annotations

import fnmatch
import re

from ..core import rules as R
from . import build, logic

MAX_RESULTS = 400
STOP_WORDS = {
    "ASM", "ASSY", "ASSEMBLY", "PART", "PARTS", "UNIT", "IPT", "IAM", "STP", "STEP", "COPY", "NEW",
    "THE", "AND", "FOR", "WITH", "LEFT", "RIGHT", "TOP", "BOTTOM", "TYPE", "VER", "REV", "DWG", "SET",
    "DIN", "ISO", "MIRROR", "MIR", "FRONT", "BACK", "REAR", "SIDE", "BODY", "COMPONENT", "SUB",
}


def terms_of(text: str) -> list[str]:
    return [t for t in text.upper().split() if t.strip("*")]


def name_matches(name: str, terms: list[str]) -> bool:
    up = name.upper()
    for t in terms:
        if "*" in t:
            if not fnmatch.fnmatchcase(up, f"*{t}*"):
                return False
        elif t not in up:
            return False
    return True


def scope_row(s):
    """The subassembly row 'Only inside' means: the selected row, or the one above a selected part."""
    i = s.tree_index
    if 0 <= i < len(s.tree) and s.tree[i].is_part:
        i = s.tree[i].parent_index
    return s.tree[i] if 0 <= i < len(s.tree) else None


def scope_parts(scene) -> list:
    """All parts, or only those in the subassembly selected in 2 Structure."""
    s = scene.fresing
    parts = list(build.iter_parts(scene))
    item = scope_row(s) if s.find_in_selected else None
    if item is not None:
        from . import tree as tree_mod
        inside = {o.name for o in tree_mod.row_objects(scene, item)}
        parts = [p for p in parts if p.name in inside]
    return parts


def run_search(scene) -> int:
    """Fill the result list. Returns the number of part names found."""
    s = scene.fresing
    s.found.clear()
    terms = terms_of(s.find_text)
    if not terms:
        return 0
    by_name: dict[str, list] = {}
    for ob in scope_parts(scene):
        name = ob.get(build.PROP_NAME, ob.name)
        if name_matches(name, terms):
            by_name.setdefault(name, []).append(ob)
    for name in sorted(by_name, key=str.lower)[:MAX_RESULTS]:
        obs = by_name[name]
        it = s.found.add()
        it.part_name = name
        it.count = len(obs)
        groups = sorted({o.get(build.PROP_GROUP, "") for o in obs})
        it.groups = ", ".join(g for g in groups if g) or "-"
        it.use = True
    s.found_index = 0
    return len(by_name)


def ticked_parts(scene) -> list:
    s = scene.fresing
    names = {it.part_name for it in s.found if it.use}
    return [ob for ob in scope_parts(scene) if ob.get(build.PROP_NAME, ob.name) in names]


def put_in_group(scene, objs, group: str) -> int:
    """Put parts in a group by hand (the rules leave them there) and repaint."""
    s = scene.fresing
    logic.ensure_group(s, group)
    n = 0
    for ob in objs:
        if ob.get(build.PROP_KIND) == "part" and ob.type == "MESH":
            ob["fr_group_manual"] = group
            n += 1
    logic.apply_rules(scene)
    s.groups_index = next((i for i, g in enumerate(s.groups) if g.name == group), s.groups_index)
    return n


def group_name_for(text: str) -> str:
    words = [w.strip("*") for w in text.split() if w.strip("*")]
    name = " ".join(words) or "New group"
    return name[:1].upper() + name[1:]


def unique_group_name(s, name: str) -> str:
    base, i, out = name, 2, name
    while s.groups.get(out):
        out = f"{base} {i}"
        i += 1
    return out


# ---------------------------------------------------------------------------
# rules made from a search or a subassembly
# ---------------------------------------------------------------------------


def rule_for_search(text: str) -> tuple[str, str, str]:
    """(field, op, value) of a sorting rule that matches the same names as this search."""
    terms = terms_of(text)
    if len(terms) == 1 and "*" not in terms[0]:
        return "name", "contains", terms[0]
    parts = []
    for t in terms:
        parts.append("(?=.*" + ".*".join(re.escape(x) for x in t.split("*")) + ")")
    return "name", "regex", "^" + "".join(parts)


def add_rule_on_top(s, target: str, field: str, op: str, value: str, note: str = "") -> None:
    """A rule the user made: checked before the built-in ones, so it wins."""
    r = s.rules.add()
    r.target, r.field, r.op, r.value, r.enabled, r.note = target, field, op, value, True, note
    s.rules.move(len(s.rules) - 1, 0)
    s.rules_index = 0


# ---------------------------------------------------------------------------
# suggestions for unsorted parts
# ---------------------------------------------------------------------------

_SUGGEST = {"key": None, "words": []}


def _words(name: str) -> set[str]:
    out = set()
    for tok in re.split(r"[^A-Za-z]+", name.upper()):
        if len(tok) >= 3 and tok not in STOP_WORDS:
            out.add(tok)
    return out


def suggestions(scene, limit: int = 12) -> list[tuple[str, int]]:
    """Most common words in the names of unsorted parts, with how many parts have them."""
    s = scene.fresing
    key = (s.unmatched, len(s.groups), tuple(g.count for g in s.groups))
    if _SUGGEST["key"] == key:
        return _SUGGEST["words"][:limit]
    counts: dict[str, int] = {}
    for ob in build.iter_parts(scene):
        if ob.get(build.PROP_GROUP) != R.FALLBACK_GROUP:
            continue
        for w in _words(ob.get(build.PROP_NAME, ob.name)):
            counts[w] = counts.get(w, 0) + 1
    words = sorted(((w, n) for w, n in counts.items() if n >= 2), key=lambda x: (-x[1], x[0]))
    _SUGGEST["key"] = key
    _SUGGEST["words"] = words[:40]
    return words[:limit]


def unsorted_parts(scene) -> list:
    return [ob for ob in build.iter_parts(scene) if ob.get(build.PROP_GROUP) == R.FALLBACK_GROUP]


# ---------------------------------------------------------------------------
# ready-made machine materials (one click for a group)
# ---------------------------------------------------------------------------

PRESETS = [
    # id, label, library material, colour
    ("profile", "Aluminium profile", "aluminium_profile", ""),
    ("alu", "Aluminium, anodised", "aluminium_anodized", ""),
    ("alu_black", "Aluminium, black anodised", "aluminium_anodized_color", "RAL 9005"),
    ("alu_machined", "Aluminium, machined", "aluminium_machined", ""),
    ("stainless", "Stainless, brushed", "stainless_brushed", ""),
    ("steel", "Steel, machined", "steel_machined", ""),
    ("chrome", "Chrome (piston rods)", "chrome", ""),
    ("galvanized", "Galvanised", "galvanized", ""),
    ("zinc", "Zinc plated", "zinc_plated", ""),
    ("black_oxide", "Black oxide", "black_oxide", ""),
    ("brass", "Brass", "brass", ""),
    ("copper", "Copper", "copper", ""),
    ("cast_iron", "Cast iron", "cast_iron", ""),
    ("rubber", "Rubber, black (seals, O-rings)", "rubber_black", ""),
    ("pom", "POM / PE, white", "pom_white", ""),
    ("plastic_black", "Plastic, black matte", "plastic_matte", "RAL 9005"),
    ("cable", "Cable / hose, black", "cable_black", ""),
    ("pc_clear", "Polycarbonate, clear (guards)", "polycarbonate_clear", ""),
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
]
