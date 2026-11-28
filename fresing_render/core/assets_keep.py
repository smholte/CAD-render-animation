"""What a project keeps of the Fresing assets pack – the plain rules (task 0355, study 0344 2.4–2.5). No Blender.

``blender/assets.py`` brings pack items into a project (append, pictures packed at the project quality) and keeps
exactly one copy per item and version; these are its rules in plain Python, so they are tested without Blender:

* **The stamp** ``fr_asset`` on every brought datablock (``stamp`` / ``read_stamp``) – the only stamp per datablock:
  ``{"id", "pack", "version", "contract", "sha"}`` (0354's ``Registry.stamp``) plus ``"name"`` (the datablock's name
  inside the pack file – what makes two items' shared parts one copy) and, on what came along with the item,
  ``"part"`` (the datablock collection) – a picture's ``"file"`` (its path in the pack) and ``"sha"`` (its file's).
* **The project's source** (``SOURCES``): ``""`` = made before the pack → counts as ``code``; ``pack``; ``code``.
* **The material's look source** ``fr_look_src`` (``look_src`` / ``parse_look_src``): ``code`` | ``pack:<version>``,
  compared by 0360's ``is_current``.
* **Pictures at the project quality** (``at_quality``): a picture under ``textures/4k/`` or named ``…_4k.exr`` is
  brought from its ``2k`` sibling when the pack has it (owner's pick 2: projects carry 2k, never the 4k files).
* **Which copy answers** when several versions of one id are in a project for a moment (``best``) and the version
  order (``version_key``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

STAMP = "fr_asset"                 # on every brought datablock
LOOK_SRC = "fr_look_src"           # on each group material (0360 compares it in is_current)
CODE, PACK = "code", "pack"
SOURCES = ("", PACK, CODE)         # the scene's assets_source: "" = made before the pack (counts as code)
KEYS = ("id", "pack", "version", "contract", "sha", "name", "part", "file")

_QUALITY_DIR = re.compile(r"(^|/)(1k|2k|4k)(/)")
_QUALITY_END = re.compile(r"_(1k|2k|4k)(\.[A-Za-z0-9]+)$")


# ---------------------------------------------------------------------------
# the stamp
# ---------------------------------------------------------------------------

def stamp(base: dict, name: str = "", part: str = "", file: str = "", sha: str = "") -> dict:
    """The ``fr_asset`` value of one brought datablock. ``base`` = ``Registry.stamp(choice)`` (id, pack, version,
    contract, sha of the item's file); ``name`` = its name in the pack file; ``part`` = the collection of a datablock
    that came along with the item (empty for the item itself); a picture adds its ``file`` and that file's ``sha``."""
    out = {k: base[k] for k in ("id", "pack", "version", "contract", "sha") if k in base}
    if name:
        out["name"] = name
    if part:
        out["part"] = part
    if file:
        out["file"] = file
    if sha:
        out["sha"] = sha
    return out


def read_stamp(value) -> dict:
    """A stamp read back as a plain dict of texts and numbers; {} when there is none or it is not ours (never
    raises). Takes the value as Blender gives it (a group of ID properties, a dict) or JSON text."""
    if value is None or value == "":
        return {}
    if hasattr(value, "to_dict"):
        try:
            value = value.to_dict()
        except Exception:  # noqa: BLE001
            return {}
    if isinstance(value, (str, bytes)):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return {}
    if not isinstance(value, dict):
        return {}
    out = {}
    for k in KEYS:
        v = value.get(k)
        if isinstance(v, (str, int)) and not isinstance(v, bool):
            out[k] = v
    if not isinstance(out.get("id"), str) or not out.get("id") or not isinstance(out.get("version"), str):
        return {}
    return out


def is_item(st: dict) -> bool:
    """The stamp of the item itself (what ``get`` answers with), not of something that came along with it."""
    return bool(st) and not st.get("part")


def share_key(coll: str, st: dict) -> tuple:
    """Two datablocks with the same key are one copy: a picture by its file's sha256 (shared across items and
    versions – the same bytes), anything else by pack, version, collection and its name in the pack."""
    if coll == "images" and st.get("sha"):
        return ("images", st["sha"])
    return (coll, st.get("pack", ""), st.get("version", ""), st.get("name", ""))


# ---------------------------------------------------------------------------
# versions, sources
# ---------------------------------------------------------------------------

def version_key(text) -> tuple:
    """'1.10.0' after '1.9.2'; anything unreadable first."""
    try:
        return tuple(int(p) for p in str(text).split("."))
    except ValueError:
        return ()


def best(stamps: list, want: str = "") -> int:
    """Index of the copy that answers among several of one id: the version ``want`` (the project's
    ``assets_version``) when there is one, else the newest. -1 for none."""
    if not stamps:
        return -1
    for i, st in enumerate(stamps):
        if want and st.get("version") == want:
            return i
    return max(range(len(stamps)), key=lambda i: version_key(stamps[i].get("version", "")))


def source_of(value) -> str:
    """The scene's ``assets_source`` as the app reads it: ``pack`` or ``code`` ("" and anything else = code)."""
    return PACK if value == PACK else CODE


def look_src(version: str = "") -> str:
    """``fr_look_src`` for a material: ``code`` or ``pack:<version>``."""
    return f"{PACK}:{version}" if version else CODE


def parse_look_src(text) -> tuple[str, str]:
    """(``code`` | ``pack``, version) of a ``fr_look_src`` value; missing or unreadable = code (made before)."""
    if isinstance(text, str) and text.startswith(PACK + ":") and version_key(text[len(PACK) + 1:]):
        return PACK, text[len(PACK) + 1:]
    return CODE, ""


# ---------------------------------------------------------------------------
# pictures at the project quality
# ---------------------------------------------------------------------------

def at_quality(rel: str, files, quality: str = "2k") -> str:
    """The pack path of the picture a project keeps for ``rel``: the same picture at ``quality`` when the pack lists
    it (``textures/4k/x.png`` → ``textures/2k/x.png``, ``hdri/a_4k.exr`` → ``hdri/a_2k.exr``), else ``rel``."""
    for pattern, repl in ((_QUALITY_DIR, rf"\g<1>{quality}\g<3>"), (_QUALITY_END, rf"_{quality}\g<2>")):
        if pattern.search(rel):
            other = pattern.sub(repl, rel, count=1)
            if other != rel and other in files:
                return other
    return rel


# ---------------------------------------------------------------------------
# what "update" would do
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Change:
    id: str                       # the pack id
    kind: str
    what: str                     # "newer": a copy of an older version; "code": a code look a plug-in would swap
    old: str = ""                 # the version in the project ("" for a code look)
    new: str = ""                 # the pack's version
    text: str = ""                # one plain line for the list (0359)


def newer_text(aid: str, old: str, new: str) -> str:
    return f"{aid}: {old} → {new}"


@dataclass
class Result:
    """What ``apply`` did. ``note`` = one plain line when it stopped or something was left as it was."""
    done: list = field(default_factory=list)       # Change rows made
    failed: list = field(default_factory=list)     # (id, why)
    backup: str = ""                               # the backup's path
    note: str = ""

    @property
    def ok(self) -> bool:
        return not self.note and not self.failed
