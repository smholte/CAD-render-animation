"""Rule sets: one naming scheme (a company's, a client's) kept as a file.

A rule set is a name plus
* the sorting rules (``rules.Rule``, checked top to bottom),
* the looks of its material groups (group name -> material and colour),
* group renames (the name a rule gives -> the name shown, e.g. "Fasteners stainless" -> "Bolts RVS").

Files live in the "Rule sets" folder of the shared library, one JSON file per rule set, so
colleagues and every project use the same ones. A project keeps its own copy, so it opens
without the library. The built-in "Standard" (fasteners + part-type library + CAD material +
CAD colour) is read-only; a copy of it can be changed.

Looks: a group the rule set lists gets that look; any other group starts with the built-in look
for its name (``rules.default_material_for_group``). Two rule sets are the same when their rules,
renames and their looks *apart from the built-in ones* are the same.

No Blender here (see ``blender/rule_sets.py`` for the project side).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache

from . import materials_lib
from . import rules as R

RULE_SET_VERSION = 1
MARKER = "fresing_render_rule_set"
STANDARD = "Standard"
FROM_PROJECT = "From this project"
FOLDER = "Rule sets"
MAX_NAME = 60

STANDARD_NOTE = ("Built in: fasteners by finish, the part-type library, CAD material names and CAD colours. "
                 "Read-only: copy it to make your own.")


def look_key(material: str, color: str) -> tuple[str, str]:
    """A look as it matters: the colour only counts for materials that take one."""
    material = material or "paint_satin"
    try:
        takes_color = materials_lib.needs_color(material)
    except KeyError:
        takes_color = True
    return material, (color or "").strip() if takes_color else ""


@lru_cache(maxsize=4096)
def default_look(group: str) -> tuple[str, str]:
    """The built-in look of a group with this name (as ``look_key``)."""
    return look_key(*R.default_material_for_group(group))


def is_default_look(group: str, material: str, color: str) -> bool:
    return look_key(material, color) == default_look(group)


@dataclass
class RuleSet:
    name: str
    rules: list[R.Rule] = field(default_factory=list)
    looks: dict[str, tuple[str, str]] = field(default_factory=dict)    # group -> (material id, colour)
    renames: dict[str, str] = field(default_factory=dict)              # name from the rules -> shown name
    note: str = ""

    @property
    def builtin(self) -> bool:
        return self.name == STANDARD

    # ---- comparing --------------------------------------------------------------------

    def own_looks(self) -> dict[str, tuple[str, str]]:
        """Looks that differ from the built-in look for the group's name."""
        out = {}
        for g, (mat, col) in self.looks.items():
            if not is_default_look(g, mat, col):
                out[g] = look_key(mat, col)
        return out

    def content(self) -> dict:
        """What decides how parts are sorted and painted (the name and note do not)."""
        return {"rules": R.rules_to_list(self.rules), "looks": self.own_looks(),
                "renames": {k: v for k, v in sorted(self.renames.items()) if k != v}}

    def same_content(self, other: "RuleSet") -> bool:
        return self.content() == other.content()

    # ---- file ---------------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            MARKER: RULE_SET_VERSION,
            "name": self.name,
            "note": self.note,
            "rules": R.rules_to_list(self.rules),
            "groups": {g: {"material": m, "color": c} for g, (m, c) in sorted(self.looks.items())},
            "renames": dict(sorted(self.renames.items())),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RuleSet":
        """Read a rule set; anything that is not a rule set (or is damaged) raises ValueError."""
        if not isinstance(d, dict) or MARKER not in d:
            raise ValueError("Not a Fresing Render rule set")
        groups, renames, rules = d.get("groups") or {}, d.get("renames") or {}, d.get("rules") or []
        if not isinstance(groups, dict) or not isinstance(renames, dict) or not isinstance(rules, list):
            raise ValueError("Damaged rule set file")
        looks = {}
        for g, look in groups.items():
            if isinstance(look, dict):
                looks[str(g)] = (str(look.get("material") or "paint_satin"), str(look.get("color") or ""))
        try:
            rule_list = [_rule(r) for r in rules]
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Damaged rule in the rule set file: {exc}") from None
        return cls(name=str(d.get("name") or "Rule set"), rules=rule_list, looks=looks,
                   renames={str(k): str(v) for k, v in renames.items() if k and v},
                   note=str(d.get("note") or ""))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=False)

    @classmethod
    def from_json(cls, text: str) -> "RuleSet":
        return cls.from_dict(json.loads(text))

    def save(self, path: str) -> None:
        """Write the file in one go (a temporary file first), so a network hiccup never leaves half a file."""
        folder = os.path.dirname(os.path.abspath(path))
        os.makedirs(folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=folder)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    @classmethod
    def load(cls, path: str) -> "RuleSet":
        with open(path, encoding="utf-8-sig") as fh:       # -sig: Notepad's "UTF-8 with BOM" too
            return cls.from_dict(json.load(fh))

    def copy(self, name: str | None = None) -> "RuleSet":
        return RuleSet.from_dict({**self.to_dict(), "name": name or self.name})


def _rule(d) -> R.Rule:
    """One rule from a file, with the types the sorting expects (a hand-edited file may differ)."""
    if not isinstance(d, dict) or "target" not in d:
        raise ValueError("a rule without a group")
    out = {k: str(d[k]) for k in ("target", "field", "op", "value", "note") if k in d and d[k] is not None}
    if "enabled" in d:
        out["enabled"] = bool(d["enabled"])
    return R.Rule.from_dict(out)


def standard() -> RuleSet:
    """The built-in rule set: the default rules, every group with its built-in look."""
    return RuleSet(STANDARD, R.default_rules(), {}, {}, STANDARD_NOTE)


def empty(name: str) -> RuleSet:
    """No rules: every part lands in "Unsorted" until rules are added."""
    return RuleSet(name, [], {}, {}, "")


# ---------------------------------------------------------------------------
# what changed
# ---------------------------------------------------------------------------


def differences(saved: RuleSet, now: RuleSet) -> dict:
    """How ``now`` differs from ``saved``: {'rules': n, 'looks': n, 'renames': n} (0 = same)."""
    a, b = R.rules_to_list(saved.rules), R.rules_to_list(now.rules)
    rules = 0
    if a != b:
        rest = list(b)
        gone = 0
        for r in a:
            if r in rest:
                rest.remove(r)
            else:
                gone += 1
        rules = max(gone, len(rest)) or 1          # same rules, other order: counts as one change
    la, lb = saved.own_looks(), now.own_looks()
    looks = sum(1 for g in set(la) | set(lb) if la.get(g) != lb.get(g))
    ra = {k: v for k, v in saved.renames.items() if k != v}
    rb = {k: v for k, v in now.renames.items() if k != v}
    renames = sum(1 for k in set(ra) | set(rb) if ra.get(k) != rb.get(k))
    return {"rules": rules, "looks": looks, "renames": renames}


def describe_differences(diff: dict) -> str:
    """'2 rules, 1 group look' – for the panel."""
    parts = []
    for key, one, many in (("rules", "rule", "rules"), ("looks", "group look", "group looks"),
                           ("renames", "group name", "group names")):
        n = diff.get(key, 0)
        if n:
            parts.append(f"{n} {one if n == 1 else many}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# names and files
# ---------------------------------------------------------------------------

_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def clean_name(name: str) -> str:
    return " ".join((name or "").split())[:MAX_NAME]


def name_problem(name: str, existing: list[str] | tuple = ()) -> str:
    """Why this name cannot be used for a new rule set ('' = fine)."""
    name = clean_name(name)
    if not name:
        return "Give the rule set a name"
    if name.casefold() == STANDARD.casefold():
        return "'Standard' is the built-in rule set: pick another name"
    if any(name.casefold() == e.casefold() for e in existing):
        return f"There is already a rule set called '{name}': pick another name"
    if not any(ch.isalnum() for ch in name):
        return "Use letters or digits in the name"
    return ""


def file_name(name: str) -> str:
    """A file name that works on Windows and network shares (the real name is inside the file)."""
    base = _BAD_CHARS.sub("_", clean_name(name)).rstrip(". ")
    if base.upper() in _RESERVED:
        base = "_" + base
    return (base or "Rule set") + ".json"


def scan(folder: str) -> dict[str, tuple[str, RuleSet]]:
    """{name: (path, rule set)} of the rule sets in a folder; other or damaged files are skipped.
    Two files with the same rule set inside (a copy made in Explorer): the one whose file name
    belongs to the name counts."""
    found: dict[str, tuple[str, RuleSet]] = {}
    if not folder or not os.path.isdir(folder):
        return found
    try:
        names = sorted(os.listdir(folder), key=str.casefold)
    except OSError:
        return found
    for f in names:
        if not f.lower().endswith(".json") or f.startswith("."):
            continue
        path = os.path.join(folder, f)
        try:
            rs = RuleSet.load(path)
        except Exception:             # unreadable, damaged or not a rule set: one bad file never stops the rest
            continue
        if rs.builtin:
            continue                  # 'Standard' is always the built-in one
        if rs.name in found and f.casefold() != file_name(rs.name).casefold():
            continue
        found[rs.name] = (path, rs)
    return found


def _same_file(a: str, b: str) -> bool:
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def free_path(folder: str, name: str, own: str = "") -> str:
    """A file for rule set ``name`` that holds no other file: 'Name.json', else 'Name (2).json'...
    (different names can give the same file name, e.g. 'A/B' and 'A_B'). ``own``: its current file."""
    base = file_name(name)[:-5]
    k = 1
    while True:
        path = os.path.join(folder, f"{base}.json" if k == 1 else f"{base} ({k}).json")
        if not os.path.exists(path) or (own and _same_file(path, own)):
            return path
        k += 1


def path_for(folder: str, name: str, known: dict | None = None) -> str:
    """Where the rule set ``name`` is (or would be) saved in ``folder``."""
    known = scan(folder) if known is None else known
    hit = known.get(name)
    return hit[0] if hit else free_path(folder, name)


def save_in(folder: str, rs: RuleSet) -> str:
    if rs.builtin:
        raise ValueError("'Standard' is built in and cannot be changed")
    path = path_for(folder, rs.name)
    rs.save(path)
    return path


def rename_in(folder: str, old: str, new: str) -> str:
    known = scan(folder)
    if old not in known:
        raise FileNotFoundError(f"'{old}' is not in the library")
    problem = name_problem(new, [n for n in known if n != old])
    if problem:
        raise ValueError(problem)
    path, rs = known[old]
    rs.name = clean_name(new)
    target = free_path(folder, rs.name, own=path)
    rs.save(target)
    if not _same_file(target, path):
        os.remove(path)
    return target


def delete_in(folder: str, name: str) -> None:
    if name == STANDARD:
        raise ValueError("'Standard' is built in and cannot be deleted")
    known = scan(folder)
    if name not in known:
        raise FileNotFoundError(f"'{name}' is not in the library")
    os.remove(known[name][0])
