"""The Fresing assets pack: find it, read ``pack.json``, check it – never a crash (task 0354, study 0344 1.1–1.5).

No Blender. Nothing in the app calls this yet (bringing pack items into a project is task 0355).

**The pack** is a folder ``Fresing Assets`` holding ``pack.json``, its own licence and one file per asset::

    pack.json  LICENSE-ASSETS.txt  materials/<id>.blend  finishes/<id>.blend  lights/<KIND>.exr
    hdri/<id>_1k|2k.exr  textures/1k|2k|4k/<set>_<map>…  environments/<id>.blend  props/<id>.blend
    pictures/<kind>.<id>.jpg   (256 px picker pictures)

**pack.json** (``FORMAT`` / ``FORMAT_VERSION`` 1)::

    {"format": "fresing-assets", "format_version": 1,
     "id": "fresing-assets", "title": "Fresing assets", "version": "1.0.0",
     "app_min": "0.2.261", "app_max": "",                  # the app versions it fits ("" = no upper end)
     "contract": {"material": 1, ...},                     # per kind (a row may name its own "contract")
     "licence": "LICENSE-ASSETS.txt", "licence_id": "fresing-assets-1.0",
     "qualities": {"draft": "1k", "normal": "2k", "final": "4k"},
     "sets": {"paints": {"title": "Paints and coatings", "approved": "2026-12-01", "since": "1.0.0",
                         "budget_mb": 60}},
     "files": {"materials/paint_satin.blend": {"bytes": 123456, "sha256": "…"}, ...},   # EVERY file of the pack
     "assets": [{"id": "material:paint_satin", "kind": "material", "file": "materials/paint_satin.blend",
                 "datablock": ["node_groups", "FRP paint_satin"], "picture": "pictures/material.paint_satin.jpg",
                 "textures": ["textures/2k/paints_rough.png"], "set": "paints", "since": "1.0.0", "changed": "",
                 "contract": 1, "fallback": "", "size_m": 0.2, "cost": 1.08, "approved_slower": ""}, ...]}

**Reading never raises** (0344 1.5):

* no ``pack.json`` → no pack, nothing said (``state`` ``"none"``);
* damaged, not ours, a newer format, or this app outside ``app_min`` … ``app_max`` → no pack and ONE plain note (the
  technical reason in ``detail``, for the console);
* a bad row (its id, kind, file outside the pack, a file not in ``files``, a duplicate) or a row whose contract is newer
  than this app knows, or one more than ``SLOWER`` x slower than its code look without the owner's ``approved_slower``
  → that id is left out (the code look answers), one note counts them.

``verify`` checks every listed file's size and sha256: only after an install or a pack update (0356 / 0358), never at
every start. ``find`` looks in ``FRESING_ASSETS`` → the folder the caller passes (a company's shared pack) → the
install folder's ``Fresing Assets``; it works in a background Blender too (nothing here reads the settings file).
Call it from a helper thread: a company folder may be on a share that is slow to answer.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field

FORMAT = "fresing-assets"
FORMAT_VERSION = 1                     # the layout of pack.json this app reads
PACK_JSON = "pack.json"
FOLDER = "Fresing Assets"              # the pack's folder name beside the install's Tools\ folder
ENV = "FRESING_ASSETS"                 # tests, CI, developers: the pack folder (only this one is looked at)
INSTALLED_MARK = "installed.txt"       # Install.bat's mark in the install folder (as appicon.install_dir)

# One contract number per kind: the interface of what the app wires (node group sockets, the prop's mesh rules …).
# 0 = this app takes no pack items of that kind yet (their rows are left out as "needs a newer app"); a plug-in task
# raises it to 1 when it wires the kind. ``weather`` stays code for good (one physics with vessel motion and Web 3D).
CONTRACTS: dict[str, int] = {
    "material": 1, "finish": 1, "light": 1, "hdri": 1, "environment": 1, "prop": 1, "person": 1,
    "decal": 0, "cable_look": 0, "crane": 0, "project": 0, "weather": 0,
}
KINDS = tuple(CONTRACTS)

# What a row of each kind points at: a .blend with a datablock of these collections, or a picture file.
BLEND_KINDS = {"material": ("node_groups",), "finish": ("node_groups",), "environment": ("collections",),
               "prop": ("objects",), "person": ("objects", "collections"), "cable_look": ("node_groups",),
               "project": ("scenes",), "crane": ("collections",)}
PICTURE_KINDS = {"light": (".exr",), "hdri": (".exr", ".hdr"), "decal": (".png",)}
PICTURE_ENDINGS = (".jpg", ".jpeg", ".png")          # the 256 px picker pictures
TEXTURE_ENDINGS = (".jpg", ".jpeg", ".png", ".exr", ".tx")

# The node-group contract of 0344 2.3 (the build-side check of 0356 and the tests read it).
SOCKETS = {
    "material": dict(inputs=("Colour",), outputs=("Colour", "Metallic", "Roughness", "Normal"),
                     optional_outputs=("Coat Normal", "Tangent", "Anisotropic", "Alpha")),
    "finish": dict(inputs=("Colour", "Roughness", "Metallic"), outputs=("Colour", "Metallic", "Roughness", "Normal"),
                   optional_outputs=("Tangent", "Anisotropic", "Alpha")),
}
# Never inside a pack's node group: the app keeps its own BSDF and output (2.3); script nodes could run code (1.5).
FORBIDDEN_NODES = ("ShaderNodeBsdf", "ShaderNodeOutput", "ShaderNodeBevel", "ShaderNodeAmbientOcclusion",
                   "ShaderNodeScript", "ShaderNodeEmission", "ShaderNodeHoldout", "ShaderNodeMixShader",
                   "ShaderNodeAddShader", "ShaderNodeVolume", "ShaderNodeSubsurface", "ShaderNodeBackground")
FINISH_ATTRIBUTES = ("fr_fx_o", "fr_fx_d", "fr_fx_r", "fr_fx_k")     # FACE attributes a finish group reads
PIXEL_ATTRIBUTE = "fr_pixel_angle"                                    # View Layer attribute (core/finishes.py)

QUALITY_KEYS = ("draft", "normal", "final")
QUALITY_SIZES = ("1k", "2k", "4k")
DEFAULT_QUALITIES = {"draft": "1k", "normal": "2k", "final": "4k"}    # owner's pick 2: projects carry 2k
SLOWER = 1.3                         # owner's pick 10: a look may render at most 1.3 x its code twin unless approved
TOTAL_WARN_MB = 300                  # owner's pick 11: pack 1.0 ~300 MB – a warning number, not a hard stop

ID_RE = re.compile(r"^([a-z][a-z_]{0,31}):([A-Za-z0-9][A-Za-z0-9_.\-]{0,63})$")
PATH_RE = re.compile(r"^[A-Za-z0-9_.\-]+(/[A-Za-z0-9_.\-]+)*$")      # forward slashes, no spaces, no drive
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_PACK_JSON = 4 << 20              # a pack.json larger than 4 MB is not read
MAX_ROWS = 20000

# The notes (one plain line each; Settings > Assets shows it, 0357)
NOTE_DAMAGED = "The Fresing assets pack could not be read – it may be damaged. The app uses its built-in looks."
NOTE_NOT_OURS = "The folder of the Fresing assets pack holds something else. The app uses its built-in looks."
NOTE_NEWER = ("The Fresing assets pack is newer than this app – update Fresing Render to use it. Until then the app "
              "uses its built-in looks.")
NOTE_APP_OLD = ("The Fresing assets pack {version} needs Fresing Render {app_min} or newer – update the app. Until "
                "then the app uses its built-in looks.")
NOTE_APP_NEW = ("The Fresing assets pack {version} was made for Fresing Render up to {app_max} – get its newer "
                "version under Updates. Until then the app uses its built-in looks.")
NOTE_ROWS = ("{items} of the Fresing assets pack {verb} left out (a newer app is needed, or the pack's list is "
             "damaged there). The app uses its built-in looks for them.")


# ---------------------------------------------------------------------------
# what reading gives
# ---------------------------------------------------------------------------

@dataclass
class Asset:
    """One usable row of pack.json."""
    id: str                          # "<kind>:<code id>", e.g. "material:paint_satin"
    kind: str
    file: str                        # relative to the pack folder, forward slashes
    datablock: tuple = ()            # (collection, name) for a .blend; () for a picture file
    contract: int = 1
    fallback: str = ""               # a pack-only id: the code id that answers without the pack
    picture: str = ""
    textures: tuple = ()
    set: str = ""
    since: str = ""
    changed: str = ""
    size_m: float = 0.0
    cost: float = 0.0                # render time / its code twin's (0 = not timed)
    approved_slower: str = ""
    sha256: str = ""                 # of ``file``, from the pack's ``files`` table
    bytes: int = 0

    @property
    def code_id(self) -> str:
        """The part after the kind: today's code id."""
        return self.id.split(":", 1)[1]


@dataclass
class Pack:
    root: str                        # the folder holding pack.json
    id: str
    title: str
    version: str
    app_min: str
    app_max: str
    licence: str
    licence_id: str
    qualities: dict
    sets: dict
    files: dict                      # path -> (bytes, sha256)
    assets: dict = field(default_factory=dict)     # id -> Asset (usable rows only)
    left_out: list = field(default_factory=list)   # (id or "?", reason) – the code look answers
    contracts: dict = field(default_factory=dict)  # the pack's own contract per kind

    def path(self, rel: str) -> str:
        """The full path of a file of the pack ('' when it would lie outside the pack folder, e.g. by a link)."""
        return inside(self.root, rel)

    @property
    def bytes(self) -> int:
        return sum(b for b, _ in self.files.values())


@dataclass
class Found:
    pack: Pack | None = None
    state: str = "none"              # none · ok · damaged · not_ours · newer · app_old · app_new
    note: str = ""                   # ONE plain line for the user ("" = nothing to say)
    detail: str = ""                 # the technical reason, for the console only
    where: str = ""                  # the folder looked at ("" when none was found)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _version(text) -> tuple:
    from .updates import parse_version           # lazily: updates.py brings urllib with it
    return parse_version(str(text or ""))


def _is_version(text) -> bool:
    return isinstance(text, str) and bool(_version(text)[0])


def _no_constant(name):
    raise ValueError(f"{name} is not allowed in pack.json")


def _plural(n: int, one: str) -> str:
    from .words import plural
    return plural(n, one)


def _verb(n: int) -> str:
    from .words import verb
    return verb(n, "is", "are")


def split_id(full_id) -> tuple[str, str]:
    """("material", "paint_satin") for "material:paint_satin"; ("", "") for anything else."""
    m = ID_RE.match(full_id) if isinstance(full_id, str) else None
    return (m.group(1), m.group(2)) if m else ("", "")


def path_ok(rel) -> bool:
    """A file path inside the pack: relative, forward slashes, no '..', no drive, no empty or hidden parts."""
    if not isinstance(rel, str) or not rel or len(rel) > 240 or not PATH_RE.match(rel):
        return False
    return all(p not in (".", "..") and not p.startswith(".") for p in rel.split("/"))


def inside(root: str, rel: str) -> str:
    """The full path of ``rel`` in ``root``, or '' when it is not a pack path or resolves outside ``root`` (a link)."""
    if not path_ok(rel):
        return ""
    full = os.path.join(root, *rel.split("/"))
    try:
        r, f = os.path.realpath(root), os.path.realpath(full)
    except (OSError, ValueError):
        return ""
    return full if os.path.normcase(f).startswith(os.path.normcase(r.rstrip("\\/")) + os.sep) else ""


def install_folder(binary_path: str) -> str:
    """The install folder of Install.bat (Blender's folder lies in it, beside ``installed.txt``), '' otherwise –
    the same rule as ``appicon.install_dir``."""
    if not binary_path:
        return ""
    parent = os.path.dirname(os.path.dirname(os.path.abspath(binary_path)))
    return parent if os.path.isfile(os.path.join(parent, INSTALLED_MARK)) else ""


def places(folder: str = "", binary_path: str = "") -> list[str]:
    """Where a pack is looked for, in order: ``FRESING_ASSETS`` alone when it is set; else the caller's folder (the
    company's shared pack) and ``<install folder>/Fresing Assets``."""
    env = os.environ.get(ENV, "").strip()
    if env:
        return [env]
    out = [folder] if folder else []
    inst = install_folder(binary_path)
    if inst:
        out.append(os.path.join(inst, FOLDER))
    return out


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def find(app_version: str, folder: str = "", binary_path: str = "") -> Found:
    """The pack this app uses: the first place of ``places`` that holds a pack.json (read as ``read`` does).
    Never raises; ``Found()`` (state "none") when no place has one."""
    for where in places(folder, binary_path):
        try:
            there = os.path.isfile(os.path.join(where, PACK_JSON))
        except (OSError, ValueError):
            there = False
        if there:
            return read(where, app_version)
    return Found()


def read(root: str, app_version: str) -> Found:
    """Read and check ``<root>/pack.json``. Never raises."""
    try:
        return _read(root, app_version)
    except Exception as e:                      # noqa: BLE001 – a pack must never stop the app
        return Found(None, "damaged", NOTE_DAMAGED, f"{type(e).__name__}: {e}", root)


def _read(root: str, app_version: str) -> Found:
    path = os.path.join(root, PACK_JSON)
    if not os.path.isfile(path):
        return Found()
    try:
        if os.path.getsize(path) > MAX_PACK_JSON:
            raise ValueError(f"pack.json is larger than {MAX_PACK_JSON >> 20} MB")
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f, parse_constant=_no_constant)
    except (OSError, ValueError, UnicodeDecodeError, RecursionError) as e:
        return Found(None, "damaged", NOTE_DAMAGED, f"{type(e).__name__}: {e}", root)
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        return Found(None, "not_ours", NOTE_NOT_OURS, "pack.json is not a Fresing assets pack (format)", root)
    fv = data.get("format_version")
    if not isinstance(fv, int) or isinstance(fv, bool) or fv < 1:
        return Found(None, "damaged", NOTE_DAMAGED, f"format_version {fv!r} is not a whole number", root)
    if fv > FORMAT_VERSION:
        return Found(None, "newer", NOTE_NEWER, f"format_version {fv} > {FORMAT_VERSION}", root)
    try:
        head = _head(data)
    except ValueError as e:
        return Found(None, "damaged", NOTE_DAMAGED, str(e), root)
    version, app_min, app_max = head["version"], head["app_min"], head["app_max"]
    v = _version(app_version)
    if v < _version(app_min):
        return Found(None, "app_old", NOTE_APP_OLD.format(version=version, app_min=app_min),
                     f"app {app_version} < app_min {app_min}", root)
    if app_max and v > _version(app_max):
        return Found(None, "app_new", NOTE_APP_NEW.format(version=version, app_max=app_max),
                     f"app {app_version} > app_max {app_max}", root)
    pack = Pack(root=root, **head)
    rows = data.get("assets", [])
    if not isinstance(rows, list):
        return Found(None, "damaged", NOTE_DAMAGED, "'assets' is not a list", root)
    for row in rows[:MAX_ROWS]:
        try:
            a = _row(row, pack)
        except ValueError as e:
            rid = row.get("id") if isinstance(row, dict) and isinstance(row.get("id"), str) else "?"
            pack.left_out.append((rid[:80], str(e)))
            continue
        pack.assets[a.id] = a
    if len(rows) > MAX_ROWS:
        pack.left_out.append(("?", f"{len(rows) - MAX_ROWS} rows past the first {MAX_ROWS}"))
    found = Found(pack, "ok", "", "", root)
    found.note = rows_note(len(pack.left_out))
    found.detail = "; ".join(f"{i}: {why}" for i, why in pack.left_out[:20])
    return found


def rows_note(n: int) -> str:
    """The one note that counts the rows left out ('' for none)."""
    return NOTE_ROWS.format(items=_plural(n, "item"), verb=_verb(n)) if n else ""


def _text(data: dict, key: str, need: bool = True, limit: int = 200) -> str:
    v = data.get(key, "")
    if v is None:
        v = ""
    if not isinstance(v, str) or len(v) > limit or any(ord(c) < 32 for c in v):
        raise ValueError(f"'{key}' is not a short text")
    if need and not v:
        raise ValueError(f"'{key}' is missing")
    return v


def _head(data: dict) -> dict:
    """The pack-level fields, checked (raises ValueError: the pack is damaged)."""
    head = dict(id=_text(data, "id", limit=80), title=_text(data, "title", need=False),
                version=_text(data, "version", limit=40), app_min=_text(data, "app_min", limit=40),
                app_max=_text(data, "app_max", need=False, limit=40), licence=_text(data, "licence", need=False),
                licence_id=_text(data, "licence_id", need=False, limit=80))
    for key in ("version", "app_min") + (("app_max",) if head["app_max"] else ()):
        if not _is_version(head[key]):
            raise ValueError(f"'{key}' is not a version number: {head[key]!r}")
    if head["licence"] and not path_ok(head["licence"]):
        raise ValueError(f"'licence' is not a file of the pack: {head['licence']!r}")
    contract = data.get("contract", 1)
    if isinstance(contract, int) and not isinstance(contract, bool):
        contracts = {k: contract for k in KINDS}
    elif isinstance(contract, dict) and all(isinstance(v, int) and not isinstance(v, bool) for v in contract.values()):
        contracts = {str(k): int(v) for k, v in contract.items()}
    else:
        raise ValueError("'contract' is neither a number nor a number per kind")
    q = data.get("qualities", DEFAULT_QUALITIES)
    if not (isinstance(q, dict) and set(q) == set(QUALITY_KEYS) and all(v in QUALITY_SIZES for v in q.values())):
        raise ValueError(f"'qualities' must give {', '.join(QUALITY_KEYS)} as one of {', '.join(QUALITY_SIZES)}")
    sets = data.get("sets", {})
    if not isinstance(sets, dict) or not all(isinstance(s, dict) for s in sets.values()):
        raise ValueError("'sets' is not a table of sets")
    for name, s in sets.items():
        b = s.get("budget_mb", 0)
        if not isinstance(b, (int, float)) or isinstance(b, bool) or not 0 <= b < 1e6:
            raise ValueError(f"set {name!r}: 'budget_mb' is not a size in MB")
    files = data.get("files", {})
    if not isinstance(files, dict):
        raise ValueError("'files' is not a table of files")
    clean = {}
    for rel, info in files.items():
        if not path_ok(rel) or rel == PACK_JSON:
            raise ValueError(f"'files' names a path outside the pack: {rel!r}")
        n = info.get("bytes") if isinstance(info, dict) else None
        sha = info.get("sha256") if isinstance(info, dict) else None
        if not (isinstance(n, int) and not isinstance(n, bool) and n >= 0 and isinstance(sha, str)
                and SHA_RE.match(sha)):
            raise ValueError(f"'files' {rel!r}: needs bytes and a sha256")
        clean[rel] = (n, sha)
    head.update(qualities=dict(q), sets={str(k): dict(v) for k, v in sets.items()}, files=clean, contracts=contracts)
    return head


def _row(row, pack: Pack) -> Asset:
    """One row of 'assets', checked against this app (raises ValueError with the reason: the row is left out)."""
    if not isinstance(row, dict):
        raise ValueError("the row is not a table")
    full = row.get("id")
    kind, code = split_id(full)
    if not kind:
        raise ValueError(f"bad id {str(full)[:80]!r}")
    if row.get("kind", kind) != kind:
        raise ValueError(f"kind {row.get('kind')!r} differs from the id's")
    if kind not in CONTRACTS:
        raise ValueError(f"kind {kind!r} is not known to this app (a newer app is needed)")
    if full in pack.assets:
        raise ValueError("the id is listed twice")
    contract = row.get("contract", pack.contracts.get(kind, 1))
    if not isinstance(contract, int) or isinstance(contract, bool) or contract < 1:
        raise ValueError(f"contract {contract!r} is not a whole number")
    if contract > CONTRACTS[kind]:
        raise ValueError(f"contract {contract} of a {kind} is newer than this app's {CONTRACTS[kind]}")
    rel = row.get("file")
    if not path_ok(rel):
        raise ValueError(f"file {str(rel)[:80]!r} lies outside the pack")
    if rel not in pack.files:
        raise ValueError(f"file {rel!r} is not in the pack's 'files'")
    ext = os.path.splitext(rel)[1].lower()
    db = row.get("datablock") or ()
    if kind in BLEND_KINDS:
        if ext != ".blend":
            raise ValueError(f"a {kind} must be a .blend file")
        if not (isinstance(db, (list, tuple)) and len(db) == 2 and all(isinstance(x, str) and x for x in db)
                and db[0] in BLEND_KINDS[kind] and len(db[1]) <= 63):
            raise ValueError(f"datablock {db!r} is not one of {', '.join(BLEND_KINDS[kind])} by name")
        db = (db[0], db[1])
    else:
        if ext not in PICTURE_KINDS.get(kind, ()):
            raise ValueError(f"a {kind} must be a {' or '.join(PICTURE_KINDS.get(kind, ('?',)))} file")
        if db:
            raise ValueError(f"a {kind} is a picture file: no datablock")
        db = ()
    picture = row.get("picture", "") or ""
    if picture and (not path_ok(picture) or picture not in pack.files
                    or not picture.lower().endswith(PICTURE_ENDINGS)):
        raise ValueError(f"picture {str(picture)[:80]!r} is not a listed picture of the pack")
    textures = row.get("textures", []) or []
    if not isinstance(textures, list) or not all(
            path_ok(t) and t in pack.files and t.lower().endswith(TEXTURE_ENDINGS) for t in textures):
        raise ValueError("'textures' names a file that is not a listed picture of the pack")
    fallback = row.get("fallback", "") or ""
    if fallback and not split_id(fallback)[0]:
        raise ValueError(f"fallback {str(fallback)[:80]!r} is not an id")
    cost = row.get("cost", 0) or 0
    if not isinstance(cost, (int, float)) or isinstance(cost, bool) or not 0 <= cost < 1000:
        raise ValueError(f"cost {cost!r} is not a time ratio")
    approved = row.get("approved_slower", "") or ""
    if not isinstance(approved, str):
        raise ValueError("'approved_slower' is not a text")
    if cost > SLOWER and not approved:
        raise ValueError(f"renders {cost:g} x its code look (more than {SLOWER:g} x) without the owner's OK")
    size = row.get("size_m", 0) or 0
    if not isinstance(size, (int, float, list)) or isinstance(size, bool):
        raise ValueError("'size_m' is not a size")
    s = row.get("set", "") or ""
    if s and s not in pack.sets:
        raise ValueError(f"set {s!r} is not in the pack's 'sets'")
    n, sha = pack.files[rel]
    return Asset(id=full, kind=kind, file=rel, datablock=db, contract=contract, fallback=fallback, picture=picture,
                 textures=tuple(textures), set=s, since=_short(row, "since"), changed=_short(row, "changed"),
                 size_m=size if isinstance(size, (int, float)) else tuple(size), cost=float(cost),
                 approved_slower=approved, sha256=sha, bytes=n)


def _short(row: dict, key: str) -> str:
    v = row.get(key, "") or ""
    if not isinstance(v, str) or len(v) > 40:
        raise ValueError(f"'{key}' is not a version")
    return v


# ---------------------------------------------------------------------------
# checks that go further (Check the pack, the PC check, the pack's CI)
# ---------------------------------------------------------------------------

@dataclass
class Verified:
    ok: bool
    problems: list = field(default_factory=list)   # plain lines
    files: int = 0
    bytes: int = 0


def verify(pack: Pack, progress=None) -> Verified:
    """Every file the pack lists is there, inside the pack, with its size and sha256. Slow (reads every byte): only
    after an install or a pack update. ``progress(done_bytes, total_bytes)`` is called now and then. Never raises."""
    out = Verified(True)
    total = pack.bytes
    done = 0
    for rel, (n, sha) in sorted(pack.files.items()):
        out.files += 1
        full = pack.path(rel)
        try:
            if not full:
                raise ValueError("lies outside the pack folder")
            size = os.path.getsize(full)
            if size != n:
                raise ValueError(f"is {size} bytes, the list says {n}")
            h = hashlib.sha256()
            with open(full, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
                    done += len(chunk)
                    if progress is not None:
                        progress(done, total)
            if h.hexdigest() != sha:
                raise ValueError("has another content than the list says (sha256)")
            out.bytes += size
        except (OSError, ValueError) as e:
            why = "is missing" if isinstance(e, FileNotFoundError) else str(e)
            out.problems.append(f"{rel} {why}")
            out.ok = False
    return out


def size_problems(pack: Pack) -> list[str]:
    """Warnings, not stops: a set above its ``budget_mb``, the pack above ``TOTAL_WARN_MB`` (pick 11)."""
    out = []
    per_set: dict[str, set] = {}
    for a in pack.assets.values():
        if a.set:
            per_set.setdefault(a.set, set()).update((a.file, *a.textures, *((a.picture,) if a.picture else ())))
    for name, info in sorted(pack.sets.items()):
        budget = info.get("budget_mb", 0)
        mb = sum(pack.files[f][0] for f in per_set.get(name, ())) / 1e6
        if budget and mb > budget:
            out.append(f"Set {name!r} is {mb:.1f} MB, above its budget of {budget:g} MB")
    total = pack.bytes / 1e6
    if total > TOTAL_WARN_MB:
        out.append(f"The pack is {total:.0f} MB, above the planned {TOTAL_WARN_MB} MB")
    return out


def describe(found: Found) -> str:
    """One line for the console: where, what, why."""
    if found.pack is not None:
        p = found.pack
        return (f"Fresing assets pack {p.version} in {found.where}: {len(p.assets)} items"
                + (f", {len(p.left_out)} left out ({found.detail})" if p.left_out else ""))
    if found.state == "none":
        return "No Fresing assets pack"
    return f"Fresing assets pack in {found.where} not used ({found.state}): {found.detail}"
