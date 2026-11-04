"""Project templates: material groups, paint schemes and sorting rules as JSON.

A template lets the next machine start mostly set up. It is plain JSON so it
can live on a network share and be edited by hand if needed.

Since 0.2.10 a template names the rule set it uses and keeps a copy of it (``rule_set``, a
``rule_sets.RuleSet`` as a dict): loading it uses that rule set from the library, or the copy when
the library does not have it. ``rules`` is still written, for older versions of the app.
Templates without ``rule_set`` (older ones) load as before.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from . import rules as R

TEMPLATE_VERSION = 1


@dataclass
class GroupLook:
    material: str = "paint_satin"
    color: str = ""          # 'RAL 1003', '#F9A800' or '' for materials without colour


@dataclass
class Scheme:
    name: str
    looks: dict[str, GroupLook] = field(default_factory=dict)   # group name -> look


@dataclass
class Template:
    name: str = "Template"
    rules: list[R.Rule] = field(default_factory=R.default_rules)
    schemes: list[Scheme] = field(default_factory=list)
    background: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    rule_set: dict | None = None          # the rule set it uses (name + copy); None in older templates

    def to_dict(self) -> dict:
        d = {
            "fresing_render_template": TEMPLATE_VERSION,
            "name": self.name,
            "rules": R.rules_to_list(self.rules),
            "schemes": [
                {"name": s.name, "looks": {g: asdict(l) for g, l in s.looks.items()}} for s in self.schemes
            ],
            "background": self.background,
            "output": self.output,
        }
        if self.rule_set:
            d["rule_set"] = self.rule_set
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Template":
        if "fresing_render_template" not in d:
            raise ValueError("Not a Fresing Render template")
        schemes = []
        for s in d.get("schemes", []):
            looks = {g: GroupLook(**{k: v for k, v in l.items() if k in ("material", "color")})
                     for g, l in s.get("looks", {}).items()}
            schemes.append(Scheme(name=s.get("name", "Scheme"), looks=looks))
        return cls(
            name=d.get("name", "Template"),
            rules=R.rules_from_list(d.get("rules", [])),
            schemes=schemes,
            background=d.get("background", {}),
            output=d.get("output", {}),
            rule_set=d.get("rule_set") if isinstance(d.get("rule_set"), dict) else None,
        )

    def save(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str) -> "Template":
        with open(path, encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))
