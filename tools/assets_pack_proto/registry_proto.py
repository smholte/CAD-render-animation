"""Task 0344 proof (study files only): the assets pack's ``pack.json`` check and the one registry every system asks.

Not part of the app. Plain Python, no Blender – the shape the build task P1 would give ``core/assets_pack.py`` and
``core/assets_registry.py``. Run its own checks:

    python3 tools/assets_pack_proto/registry_proto.py --selftest

Rules shown here (the report's section 1 and 2):
* a pack is a folder with ``pack.json``; reading it never raises: missing → no pack, damaged / not ours / newer
  format → no pack + ONE plain note (the technical reason for the console);
* the app version must be inside the pack's window (``app_min`` … ``app_max``), else no pack + a note;
* an asset whose ``contract`` (its node inputs / names the app wires) is newer than the app knows is skipped – that
  id falls back to the code look; a note counts them;
* ids are ``<kind>:<id>`` with today's code ids (``material:paint_satin``, ``light:PRODUCT``, ``weather:STORM`` …);
  an id never changes and is never reused; an asset that is NOT a stand-in for a code item names its ``fallback``;
* ``resolve`` answers pack or code; the project's own choice (``looks_source``) and the user's switch come first.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field

FORMAT = "fresing-assets"
FORMAT_VERSION = 1                       # the layout of pack.json this app reads
CONTRACTS = {"material": 1, "finish": 1, "world": 1, "environment": 1, "prop": 1, "person": 1, "project": 1,
             "texture": 1, "hdri": 1, "decal": 1, "cable_look": 1}
KINDS = tuple(CONTRACTS)
ID_RE = re.compile(r"^[a-z_]+:[A-Za-z0-9_.\-]{1,64}$")
MAX_PACK_JSON = 4 << 20                  # 4 MB: a pack.json larger than this is not read


def _ver(text: str) -> tuple:
    try:
        return tuple(int(x) for x in str(text).split("."))
    except ValueError:
        return ()


@dataclass
class Asset:
    id: str
    kind: str
    file: str
    datablock: tuple
    contract: int = 1
    fallback: str = ""                   # for a pack-only asset: the code id used without the pack
    sha256: str = ""
    picture: str = ""


@dataclass
class Pack:
    root: str
    id: str
    version: str
    assets: dict = field(default_factory=dict)       # id -> Asset
    skipped: list = field(default_factory=list)      # ids left out (contract too new, bad row)


@dataclass
class Found:
    pack: Pack | None
    note: str = ""                        # one plain line for Settings > Assets ("" = nothing to say)
    detail: str = ""                      # the technical reason, for the console only


def read_pack(root: str, app_version: str) -> Found:
    """Never raises. ``root`` = the pack folder (the one holding pack.json)."""
    path = os.path.join(root, "pack.json")
    if not os.path.isfile(path):
        return Found(None)                                            # no pack: nothing to say
    try:
        if os.path.getsize(path) > MAX_PACK_JSON:
            raise ValueError("pack.json larger than 4 MB")
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
        if not isinstance(data, dict) or data.get("format") != FORMAT:
            raise ValueError("not a Fresing assets pack")
        if not isinstance(data.get("format_version"), int):
            raise ValueError("no format_version")
        if data["format_version"] > FORMAT_VERSION:
            return Found(None, "The Fresing assets pack is newer than this app – update the app to use it. "
                               "The app uses its built-in looks.", f"format_version {data['format_version']}")
        lo, hi = _ver(data.get("app_min", "0")), _ver(data.get("app_max", "") or "9999")
        if not (lo <= _ver(app_version) <= hi):
            return Found(None, f"This Fresing assets pack ({data.get('version')}) is made for app versions "
                               f"{data.get('app_min')}–{data.get('app_max') or 'newer'}. The app uses its built-in "
                               "looks.", "app version outside the window")
        pack = Pack(root, str(data["id"]), str(data["version"]))
        for row in data.get("assets", []):
            try:
                a = Asset(id=row["id"], kind=row["kind"], file=row["file"], datablock=tuple(row["datablock"]),
                          contract=int(row.get("contract", data.get("contract", 1))),
                          fallback=row.get("fallback", ""), sha256=row.get("sha256", ""),
                          picture=row.get("picture", ""))
                if not ID_RE.match(a.id) or a.kind not in KINDS or not a.id.startswith(a.kind.split("_")[0]):
                    raise ValueError(f"bad id or kind: {a.id}")
                rel = os.path.normpath(a.file)
                if rel.startswith("..") or os.path.isabs(rel):
                    raise ValueError(f"file outside the pack: {a.file}")
                if a.contract > CONTRACTS[a.kind]:
                    pack.skipped.append(a.id)
                    continue
                pack.assets[a.id] = a
            except (KeyError, TypeError, ValueError) as e:
                pack.skipped.append(str(row.get("id", "?")) if isinstance(row, dict) else "?")
                print("pack row left out:", e)
        note = ""
        if pack.skipped:
            note = (f"{len(pack.skipped)} item(s) of the Fresing assets pack need a newer app; the app uses its "
                    "built-in looks for them.")
        return Found(pack, note)
    except (OSError, ValueError, KeyError, TypeError) as e:
        return Found(None, "The Fresing assets pack could not be read (damaged). The app uses its built-in looks.",
                     f"{type(e).__name__}: {e}")


@dataclass
class Choice:
    source: str                           # "pack" or "code"
    id: str                               # the id that answers (a pack-only asset falls back to its code id)
    asset: Asset | None = None


class Registry:
    """``code_ids``: what the app itself can make, per kind (from materials_lib, studio.LOOKS, weather.PRESETS …)."""

    def __init__(self, code_ids: dict, pack: Pack | None, use_pack: bool = True):
        self.code = {f"{k}:{i}" for k, ids in code_ids.items() for i in ids}
        self.pack = pack if use_pack else None

    def resolve(self, full_id: str, project_source: str = "pack") -> Choice:
        """``project_source``: the project's own choice – "code" for a project made before the pack (or after the
        user said no): it keeps today's looks until the user picks "Use the new Fresing looks"."""
        a = self.pack.assets.get(full_id) if (self.pack and project_source == "pack") else None
        if a is not None:
            return Choice("pack", full_id, a)
        if full_id in self.code:
            return Choice("code", full_id)
        a = self.pack.assets.get(full_id) if self.pack else None
        fb = a.fallback if a is not None else ""
        if fb in self.code:
            return Choice("code", fb)
        kind = full_id.split(":", 1)[0]
        return Choice("code", next((c for c in sorted(self.code) if c.startswith(kind + ":")), ""))

    def problems(self) -> list:
        """What the pack CI and the app's test check: every pack asset is a stand-in for a code item or names one."""
        out = []
        for a in (self.pack.assets.values() if self.pack else ()):
            if a.id not in self.code and a.fallback not in self.code:
                out.append(f"{a.id}: no code item with this id and no fallback")
        return out


# ---- self-test ------------------------------------------------------------------------------------------------------

def _selftest() -> int:
    code = {"material": ["paint_satin", "steel_machined"], "light": ["PRODUCT", "SUN"], "world": ["PRODUCT"]}
    ok = True

    def check(cond, text):
        nonlocal ok
        print(("ok   " if cond else "FAIL ") + text)
        ok = ok and cond

    with tempfile.TemporaryDirectory() as d:
        check(read_pack(d, "0.2.258").pack is None and read_pack(d, "0.2.258").note == "", "no pack: silent")
        p = os.path.join(d, "pack.json")
        for bad in ("{", "[]", '{"format": "other"}', '{"format": "fresing-assets"}', '{"x": NaN}', "﻿{"):
            with open(p, "w", encoding="utf-8") as f:
                f.write(bad)
            r = read_pack(d, "0.2.258")
            check(r.pack is None and "could not be read" in r.note, f"damaged {bad[:20]!r}: no pack, one note")
        base = {"format": FORMAT, "format_version": 1, "id": "fresing-assets", "version": "1.0.0",
                "app_min": "0.2.258", "app_max": "", "contract": 1, "assets": [
                    {"id": "material:paint_satin", "kind": "material", "file": "materials/paint_satin.blend",
                     "datablock": ["node_groups", "FRP paint_satin"]},
                    {"id": "material:concrete_floor", "kind": "material", "file": "materials/c.blend",
                     "datablock": ["materials", "FRP concrete_floor"], "fallback": "material:paint_satin"},
                    {"id": "material:future", "kind": "material", "file": "materials/f.blend",
                     "datablock": ["node_groups", "x"], "contract": 2},
                    {"id": "material:../evil", "kind": "material", "file": "../evil.blend", "datablock": ["a", "b"]},
                    {"id": "world:studio_new", "kind": "world", "file": "worlds/n.blend",
                     "datablock": ["worlds", "n"]}]}
        with open(p, "w", encoding="utf-8") as f:
            json.dump({**base, "format_version": 2}, f)
        check("newer than this app" in read_pack(d, "0.2.258").note, "newer format: no pack, one note")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({**base, "app_min": "0.3.0"}, f)
        check("made for app versions" in read_pack(d, "0.2.258").note, "app outside the window: no pack, one note")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(base, f)
        r = read_pack(d, "0.2.258")
        check(r.pack is not None and set(r.pack.assets) == {"material:paint_satin", "material:concrete_floor",
                                                             "world:studio_new"}, "good rows kept, bad rows left out")
        check(sorted(r.pack.skipped) == ["material:../evil", "material:future"] and "newer app" in r.note,
              "contract too new / bad id: skipped, one note")
        reg = Registry(code, r.pack)
        check(reg.resolve("material:paint_satin").source == "pack", "pack item answers its code id")
        check(reg.resolve("material:paint_satin", project_source="code").source == "code",
              "an old project keeps the code look")
        check(reg.resolve("material:steel_machined").source == "code", "no pack item: code look")
        c = reg.resolve("material:concrete_floor", project_source="code")
        check(c.source == "code" and c.id == "material:paint_satin", "pack-only item in a code project: its fallback")
        c = Registry(code, None).resolve("material:concrete_floor")
        check(c.source == "code" and c.id.startswith("material:") and c.id in Registry(code, None).code,
              "no pack at all: a pack-only id (stored in a project) still gives a code look of its kind")
        check(Registry(code, r.pack, use_pack=False).resolve("material:paint_satin").source == "code",
              "the switch 'Use Fresing assets' off: code")
        check(reg.problems() == ["world:studio_new: no code item with this id and no fallback"],
              "the pack check finds an asset without a code twin or fallback")
    print("ALL OK" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else 0)
