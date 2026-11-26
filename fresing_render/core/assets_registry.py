"""One registry every system asks: a Fresing assets pack item, or today's built-in (code) look? (task 0354, study
0344 2.1–2.2). No Blender. Nothing in the app calls this yet (0355 brings items; the plug-in tasks 0360 … ask).

**Ids** are ``<kind>:<today's code id>`` (``material:paint_satin``, ``light:PRODUCT``, ``environment:FACTORY``) – never
changed, never reused. The code ids are read from the modules where they live (``code_ids``), so a new code look is
never missed. **Every pack id has a code twin** with the same id; only kinds that are no enum in a project (``hdri`` …)
may instead name a ``fallback`` code id (a new 360° photo → ``light:OVERCAST``). A pack-only id with neither is
refused (one note counts it). Materials and finishes must have a twin: a group's material is an enum.

**How a system asks** (2.2), in this order:

1. the project already holds a copy (a datablock whose ``fr_asset`` id matches ``Choice.id``) → use it. That is the
   Blender side's job (0355): ``Choice`` gives it the id, pack version and sha256 to compare (``stamp``);
2. the project's source is ``"pack"``, the user's switch is on, the pack has the id and its contract fits → ``"pack"``;
3. otherwise today's code builds it (a pack-only id: its fallback).

Answers come from memory: ``current()`` reads the pack's list once and keeps it until ``forget()`` (after a pack
update is put in place, and in tests). Nothing a hot path calls touches the disk.
"""

from __future__ import annotations

import ast
import os
import pkgutil
import threading
from dataclasses import dataclass, field

from . import assets_pack as ap

# Kinds whose project setting is an enum of today's ids: a pack item must be a twin (no fallback).
TWIN_ONLY = ("material", "finish")

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)


# ---------------------------------------------------------------------------
# today's code ids, read where they live
# ---------------------------------------------------------------------------

def _materials():
    from . import materials_lib
    return materials_lib.UIDS


def _finishes():
    from . import finishes
    return finishes.FINISHES


def _lights():
    from . import studio
    return studio.LOOKS


def _environments():
    from . import surroundings
    return [k.id for k in surroundings.KINDS]


def _props():
    from . import surroundings
    return surroundings.PROPS


def _people():
    from . import props_detail          # a pack person replaces an outfit's figure (on the rig contract, 2.3)
    return props_detail.OUTFITS


def _decals():
    from . import decal_art
    return decal_art.STICKER_KEYS


def _cable_looks():
    from ..blender import cable_looks   # no bpy at its top (it says so)
    return cable_looks.KINDS


def _cranes():
    from ..lifting_model import classes
    return classes.CLASSES


def _weather():
    from . import weather
    return weather.PRESETS


def tour_sets(path: str = "") -> list[str]:
    """The test tour's set ids, read from ``blender/tour.py`` without running it (it needs Blender): every
    ``@tour_set(<id>, …)`` whose id is a text or a module-level name holding one."""
    path = path or os.path.join(_PKG, "blender", "tour.py")
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    names = {t.id: n.value.value for n in tree.body if isinstance(n, ast.Assign)
             and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)
             for t in n.targets if isinstance(t, ast.Name)}
    out = []
    for node in ast.walk(tree):
        for d in getattr(node, "decorator_list", ()):
            if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tour_set" and d.args:
                a = d.args[0]
                v = a.value if isinstance(a, ast.Constant) else names.get(getattr(a, "id", ""))
                if isinstance(v, str):
                    out.append(v)
    return out


def _projects():
    lessons = [m.name for m in pkgutil.iter_modules([os.path.join(_PKG, "blender", "lessons")])]
    return list(dict.fromkeys(tour_sets() + lessons))       # a lesson is named after its tour set


READERS = {"material": _materials, "finish": _finishes, "light": _lights, "hdri": lambda: (),
           "environment": _environments, "prop": _props, "person": _people, "decal": _decals,
           "cable_look": _cable_looks, "crane": _cranes, "project": _projects, "weather": _weather}

_CODE: dict = {}
_LOCK = threading.Lock()


def code_ids() -> dict[str, frozenset]:
    """{kind: today's code ids} – read once from the code modules (``READERS``)."""
    with _LOCK:
        if not _CODE:
            for kind in ap.KINDS:
                _CODE[kind] = frozenset(str(i) for i in READERS[kind]())
        return dict(_CODE)


def code_full_ids() -> frozenset:
    """Every code id as ``<kind>:<id>``."""
    return frozenset(f"{k}:{i}" for k, ids in code_ids().items() for i in ids)


# ---------------------------------------------------------------------------
# the answers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Choice:
    source: str                      # "pack" or "code"
    id: str                          # the id that answers ('' when neither the pack nor the code knows it)
    asset: ap.Asset | None = None    # the pack's row (source "pack")
    pack_version: str = ""

    @property
    def code_id(self) -> str:
        return self.id.split(":", 1)[1] if self.id else ""


@dataclass
class Registry:
    """Built from what ``assets_pack.find`` found and today's code ids. Answers only from memory."""
    found: ap.Found = field(default_factory=ap.Found)
    code: frozenset = field(default_factory=frozenset)
    usable: dict = field(default_factory=dict)       # id -> Asset the app may bring
    refused: list = field(default_factory=list)      # (id, reason): pack-only without a twin or a fallback

    @classmethod
    def build(cls, found: ap.Found | None = None, code: frozenset | None = None) -> "Registry":
        reg = cls(found or ap.Found(), code if code is not None else code_full_ids())
        pack = reg.found.pack
        for aid, a in (pack.assets.items() if pack else ()):
            why = reg._why_refused(a)
            if why:
                reg.refused.append((aid, why))
            else:
                reg.usable[aid] = a
        return reg

    def _why_refused(self, a: ap.Asset) -> str:
        if a.id in self.code:
            return ""
        if a.kind in TWIN_ONLY:
            return f"a {a.kind} needs a built-in look with the same id"
        if not a.fallback:
            return "no built-in look with this id and no fallback"
        if a.fallback not in self.code:
            return f"its fallback {a.fallback} is not a built-in look"
        return ""

    # -- what the pack is ------------------------------------------------------------------------------------------

    @property
    def pack(self) -> ap.Pack | None:
        return self.found.pack

    @property
    def version(self) -> str:
        return self.pack.version if self.pack else ""

    @property
    def note(self) -> str:
        """ONE plain line for the user: the pack-level reason, or how many items are left out."""
        if self.pack is None:
            return self.found.note
        return ap.rows_note(len(self.pack.left_out) + len(self.refused))

    def items(self, kind: str) -> list[ap.Asset]:
        """The pack's usable items of one kind (pickers, Settings)."""
        return [a for a in self.usable.values() if a.kind == kind]

    def has(self, full_id: str) -> bool:
        return full_id in self.usable

    # -- the question ------------------------------------------------------------------------------------------------

    def resolve(self, full_id: str, source: str = "pack", use_pack: bool = True) -> Choice:
        """Pack item or code look for ``full_id``.

        ``source`` is the project's own choice: ``"pack"`` (made with the pack, or after "Use the new Fresing
        looks"), ``"code"`` or ``""`` (made before the pack: it keeps today's looks). ``use_pack`` is the user's
        switch (Settings > Assets, 0357). Step 1 of 2.2 – the project's own copy – is asked first by the Blender
        side; then this. Never raises; ``Choice("code", "")`` when nobody knows the id (the caller's default)."""
        if not isinstance(full_id, str):
            return Choice("code", "")
        a = self.usable.get(full_id)
        if a is not None and use_pack and source == "pack":
            return Choice("pack", full_id, a, self.version)
        if full_id in self.code:
            return Choice("code", full_id)
        a = a or (self.pack.assets.get(full_id) if self.pack else None)
        if a is not None and a.fallback in self.code and a.kind not in TWIN_ONLY:
            return Choice("code", a.fallback)
        return Choice("code", "")

    def stamp(self, choice: Choice) -> dict:
        """What a project stores on a brought datablock (``fr_asset``, 2.5): enough to find its source again."""
        a = choice.asset
        if choice.source != "pack" or a is None:
            return {}
        return {"id": a.id, "pack": self.pack.id, "version": self.version, "contract": a.contract,
                "sha": a.sha256}

    def problems(self) -> list[str]:
        """Plain lines for Settings > Assets ("Check the pack", 0357) and the PC check: the pack-level reason, rows left
        out, items refused, sizes above their budget. [] = nothing to say."""
        out = []
        if self.pack is None:
            if self.found.note:
                out.append(self.found.note)
            return out
        out += [f"{i}: left out – {why}" for i, why in self.pack.left_out]
        out += [f"{i}: left out – {why}" for i, why in self.refused]
        out += ap.size_problems(self.pack)
        return out


# ---------------------------------------------------------------------------
# read once
# ---------------------------------------------------------------------------

_CURRENT: dict = {}


def current(app_version: str, folder: str = "", binary_path: str = "") -> Registry:
    """The registry of this app: the pack is looked for and read ONCE (``assets_pack.find``); later calls answer from
    memory, whatever they pass, until ``forget()``. Call it first from a helper thread at start."""
    with _LOCK:
        reg = _CURRENT.get("reg")
    if reg is not None:
        return reg
    found = ap.find(app_version, folder, binary_path)
    reg = Registry.build(found)
    with _LOCK:
        return _CURRENT.setdefault("reg", reg)


def forget() -> None:
    """Read the pack again at the next ``current()`` (a pack update put in place; tests)."""
    with _LOCK:
        _CURRENT.clear()
