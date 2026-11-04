"""Sorting rules: decide which material group each part goes to.

A rule says: *if* a fact about the part matches, *then* the part goes to
``target``. Rules are checked top to bottom; the first one that matches wins.
Parts no rule matches go to the fallback group ("Unsorted").

Targets can use placeholders: {color}, {finish}, {kind}, {family}, {name}, {part_type},
{cad_material}.

Default order: fasteners (by finish) -> part type from the part-type library
(``part_types.py``) -> material or appearance name from the CAD file -> CAD colour ->
"Unsorted". The part-type library sits behind one rule, so the list stays short.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import asdict, dataclass, field

from . import cad_materials, fasteners, part_types

FIELDS = {
    "name": "Part name",
    "path": "Assembly path",
    "assembly": "Parent subassembly",
    "color": "CAD colour",
    "is_standard": "Is a standard part",
    "family": "Standard part family",
    "kind": "Standard part type",
    "finish": "Finish",
    "standard": "Standard (DIN/ISO)",
    "size": "Thread size",
    "property_class": "Property class",
    # appended at the end: Blender stores the position of each choice in saved projects
    "part_type": "Part type",
    "cad_material": "CAD material",
}

OPS = {
    "contains": "contains",
    "equals": "is",
    "starts": "starts with",
    "ends": "ends with",
    "glob": "matches pattern (* ?)",
    "regex": "matches regex",
    "any": "has any value",
    "none": "is empty",
}

FALLBACK_GROUP = "Unsorted"


@dataclass
class Rule:
    target: str
    field: str = "name"
    op: str = "contains"
    value: str = ""
    enabled: bool = True
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rule":
        known = {k: d[k] for k in ("target", "field", "op", "value", "enabled", "note") if k in d}
        return cls(**known)

    def describe(self) -> str:
        f = FIELDS.get(self.field, self.field)
        o = OPS.get(self.op, self.op)
        if self.op in ("any", "none"):
            return f"{f} {o} → {self.target}"
        return f"{f} {o} “{self.value}” → {self.target}"


@dataclass
class PartFacts:
    name: str
    path: str = ""
    assembly: str = ""
    color: str = ""                       # '#RRGGBB' or ''
    cad_material: str = ""                # material/appearance name from the CAD file, '' if unknown
    part_type: str = ""                   # group from the part-type library, '' if none
    fastener: fasteners.FastenerInfo | None = field(default=None, repr=False)

    def get(self, key: str) -> str:
        if key == "name":
            return self.name
        if key == "path":
            return self.path
        if key == "assembly":
            return self.assembly
        if key == "color":
            return self.color
        if key == "part_type":
            return self.part_type
        if key == "cad_material":
            return self.cad_material
        f = self.fastener
        if key == "is_standard":
            return "yes" if f else ""
        if f is None:
            return ""
        if key == "finish":
            return f.finish or ""
        value = getattr(f, key, "")
        return "" if value is None else str(value)

    def placeholders(self) -> dict:
        f = self.fastener
        return {
            "name": self.name,
            "color": self.color or "no colour",
            "finish": (f.finish if f and f.finish else "default"),
            "kind": (f.label if f else ""),
            "family": (f.family if f else ""),
            "part_type": self.part_type,
            "cad_material": part_types.cad_group(self.cad_material, self.color) or self.cad_material,
        }


def facts_for(name: str, path: str = "", color: str = "", assembly: str = "", cad_material: str = "") -> PartFacts:
    """Facts about one part. ``cad_material``: the material or appearance name the CAD file
    gives the part; only names the library knows are kept ("Default", "Generic" and unknown
    names count as no material, so the CAD colour still decides)."""
    cad = cad_material if cad_material and cad_materials.lookup(cad_material) else ""
    return PartFacts(name=name, path=path, assembly=assembly, color=color, cad_material=cad,
                     part_type=part_types.classify(name, path, assembly, cad, color),
                     fastener=fasteners.parse(name))


def _matches(rule: Rule, facts: PartFacts) -> bool:
    value = facts.get(rule.field)
    v = value.upper()
    want = (rule.value or "").upper()
    op = rule.op
    if op == "any":
        return bool(value)
    if op == "none":
        return not value
    if op == "contains":
        return bool(want) and want in v
    if op == "equals":
        return v == want
    if op == "starts":
        return bool(want) and v.startswith(want)
    if op == "ends":
        return bool(want) and v.endswith(want)
    if op == "glob":
        return fnmatch.fnmatchcase(v, want)
    if op == "regex":
        try:
            return re.search(rule.value, value, re.IGNORECASE) is not None
        except re.error:
            return False
    return False


def target_for(rule: Rule, facts: PartFacts) -> str:
    try:
        return rule.target.format(**facts.placeholders())
    except (KeyError, IndexError, ValueError):
        return rule.target


def classify_one(facts: PartFacts, rules: list[Rule], fallback: str = FALLBACK_GROUP):
    """Return (group name, index of the rule that matched or -1)."""
    for i, rule in enumerate(rules):
        if rule.enabled and _matches(rule, facts):
            return target_for(rule, facts), i
    return fallback, -1


def classify(parts: list[PartFacts], rules: list[Rule], fallback: str = FALLBACK_GROUP):
    """Classify many parts. Returns (groups, rule_counts, unmatched_indices)."""
    groups: list[str] = []
    counts = [0] * len(rules)
    unmatched: list[int] = []
    for idx, facts in enumerate(parts):
        group, ri = classify_one(facts, rules, fallback)
        groups.append(group)
        if ri >= 0:
            counts[ri] += 1
        else:
            unmatched.append(idx)
    return groups, counts, unmatched


def _fastener_rules() -> list[Rule]:
    return [
        Rule("Fasteners stainless", "finish", "equals", "stainless", note="A2/A4, RVS, INOX..."),
        Rule("Fasteners black", "finish", "equals", "black", note="black oxide, 12.9, socket screws"),
        Rule("Fasteners galvanized", "finish", "equals", "galvanized", note="HDG, tZn"),
        Rule("Fasteners zinc", "finish", "equals", "zinc", note="zinc plated"),
        Rule("Fasteners zinc flake", "finish", "equals", "zinc_flake", note="Geomet, Delta"),
        Rule("Fasteners default", "is_standard", "any", "", note="standard parts without a finish"),
    ]


def default_rules() -> list[Rule]:
    return _fastener_rules() + [
        Rule("{part_type}", "part_type", "any", "",
             note="part-type library: profiles, seals, cylinders, sensors, motors..."),
        Rule("{cad_material}", "cad_material", "any", "", note="material or appearance from the CAD file"),
        Rule("Colour {color}", "color", "any", "", note="one group per CAD colour"),
    ]


def old_default_rules() -> list[Rule]:
    """The default list before the part-type library (versions up to 0.2.6)."""
    return _fastener_rules() + [Rule("Colour {color}", "color", "any", "", note="one group per CAD colour")]


def upgraded_rules(rules: list[Rule]) -> list[Rule] | None:
    """The new default list when ``rules`` is still the untouched old default list, else None.
    For projects saved before the part-type library: the app can offer (or do) the upgrade
    without losing rules the user changed."""
    if rules_to_list(rules) == rules_to_list(old_default_rules()):
        return default_rules()
    return None


# Material that a new group starts with (library id, colour or '').
DEFAULT_GROUP_MATERIAL = {
    "Fasteners stainless": ("stainless_brushed", ""),
    "Fasteners black": ("black_oxide", ""),
    "Fasteners galvanized": ("galvanized", ""),
    "Fasteners zinc": ("zinc_plated", ""),
    "Fasteners zinc flake": ("zinc_flake", ""),
    "Fasteners default": ("zinc_plated", ""),
    FALLBACK_GROUP: ("paint_satin", "RAL 7035"),
}


def default_material_for_group(group: str) -> tuple[str, str]:
    """Starting material (library id, colour) for a new group: fasteners and Unsorted, groups
    of the part-type library, groups named after a CAD material, then a CAD colour in the name."""
    if group in DEFAULT_GROUP_MATERIAL:
        return DEFAULT_GROUP_MATERIAL[group]
    look = part_types.look_for_group(group) or part_types.cad_look_for_group(group)
    if look:
        return look
    m = re.search(r"#[0-9A-Fa-f]{6}", group)
    if m:
        return "paint_satin", m.group(0).upper()
    return "paint_satin", "RAL 7035"


def rules_to_list(rules: list[Rule]) -> list[dict]:
    return [r.to_dict() for r in rules]


def rules_from_list(items: list[dict]) -> list[Rule]:
    return [Rule.from_dict(d) for d in items]
