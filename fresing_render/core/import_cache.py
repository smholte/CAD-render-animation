"""The import cache as a list (task 0289): every stored import, newest first, for the "Imported models" fold of 1 Import.

No Blender here. An import is stored as a folder ``<cache root>/<name>_<key>/`` holding ``tree.json`` (the head of it
says which file, its size and time, the detail, the counts) and ``meshes.npz`` (``importer/runner.py``). This module
only reads those folders, works out whether the file they came from is still there and unchanged, and removes one on
request. Reading a ``tree.json`` costs a few ms to a few hundred ms for a big model, so a folder is read once and kept
while its ``tree.json`` stays the same (``_SEEN``); the panel asks at every redraw.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field

OK = "ok"                    # the file is there and unchanged: Import again takes the stored copy, nothing is read
CHANGED = "changed"          # the file is there but changed since: Import again reads it again
MOVED = "moved"              # the file is gone (moved, renamed, deleted): Import again takes the stored copy
OLD = "old"                  # stored by an older version of the app: never used again (pruned at the next import)
SEARCH_FROM = 10             # the fold shows a search field from this many stored imports on


@dataclass
class Entry:
    folder: str                         # the folder's full path
    name: str                           # the model's name: the file's name without its ending
    source: str                         # the file it came from (full path, as it was when it was read)
    kind: str = "step"                  # "step" or "mesh"
    quality: str = "normal"             # draft / normal / fine; "mesh" for a mesh model
    options: dict = field(default_factory=dict)    # a mesh model's units, up, split as read
    stored: float = 0.0                 # when it was stored (the tree's time), seconds since 1970
    parts: int = 0                      # placed parts
    size: int = 0                       # bytes on disk
    state: str = OK
    version: int = 0

    @property
    def id(self) -> str:
        """The folder's own name: what the buttons carry."""
        return os.path.basename(self.folder)

    @property
    def file_name(self) -> str:
        return os.path.basename(self.source) or self.name


_SEEN: dict = {}             # folder -> ((tree mtime_ns, size), head dict, bytes on disk)


def _folder_size(folder: str) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(folder):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _head(folder: str):
    """(head of tree.json without its node and mesh lists, bytes on disk), or None when it is no stored import."""
    tree = os.path.join(folder, "tree.json")
    try:
        st = os.stat(tree)
    except OSError:
        return None
    if not os.path.isfile(os.path.join(folder, "meshes.npz")):
        return None
    stamp = (st.st_mtime_ns, st.st_size)
    seen = _SEEN.get(folder)
    if seen is not None and seen[0] == stamp:
        return seen[1], seen[2]
    try:
        with open(tree, encoding="utf-8") as fh:
            info = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(info, dict):
        return None
    head = {k: v for k, v in info.items() if k not in ("nodes", "meshes", "materials")}
    head["_stored"] = st.st_mtime
    size = _folder_size(folder)
    _SEEN[folder] = (stamp, head, size)
    return head, size


def file_state(head: dict, version: int) -> str:
    """OK, CHANGED, MOVED or OLD for one stored import's head."""
    if head.get("version") != version:
        return OLD
    src = head.get("source") or ""
    try:
        st = os.stat(src)
    except (OSError, ValueError):
        return MOVED
    if int(st.st_size) != int(head.get("source_size", -1)):
        return CHANGED
    if abs(float(st.st_mtime) - float(head.get("source_mtime", -1.0))) > 1e-3:
        return CHANGED
    from ..importer.runner import side_files_changed
    if side_files_changed(head):
        return CHANGED
    return OK


def entries(root: str, version: int | None = None) -> list:
    """Every stored import under ``root``, newest first. Half-written folders (``.partial-…``) are left out."""
    if version is None:
        from ..importer.step_reader import CACHE_VERSION
        version = CACHE_VERSION
    try:
        names = os.listdir(root)
    except OSError:
        return []
    out = []
    for n in names:
        if ".partial" in n:
            continue
        folder = os.path.join(root, n)
        if not os.path.isdir(folder):
            continue
        got = _head(folder)
        if got is None:
            continue
        head, size = got
        src = str(head.get("source") or "")
        stem = os.path.splitext(os.path.basename(src))[0] if src else n.rsplit("_", 1)[0]
        kind = "mesh" if head.get("source_kind") == "mesh" else "step"
        stats = head.get("stats") or {}
        try:
            version_of = int(head.get("version") or 0)
        except (TypeError, ValueError):
            version_of = 0
        out.append(Entry(folder=folder, name=stem, source=src, kind=kind, quality=str(head.get("quality") or "normal"),
                         options=dict(head.get("options") or {}), stored=float(head.get("_stored") or 0.0),
                         parts=int(stats.get("placed_parts") or 0), size=int(size),
                         state=file_state(head, version), version=version_of))
    out.sort(key=lambda e: (-e.stored, e.name.lower()))
    return out


def find(root: str, entry_id: str, version: int | None = None):
    """The stored import whose folder is called ``entry_id``, or None."""
    for e in entries(root, version):
        if e.id == entry_id:
            return e
    return None


def total_size(items) -> int:
    return sum(e.size for e in items)


def matches(e: Entry, text: str) -> bool:
    """The search field: every word in the model's name or its file's folder (case ignored)."""
    words = (text or "").lower().split()
    hay = f"{e.name} {e.source}".lower()
    return all(w in hay for w in words)


def remove(entry: Entry, root: str) -> bool:
    """Delete one stored import (never anything outside ``root``). True when it is gone."""
    folder = os.path.realpath(entry.folder)
    base = os.path.realpath(root)
    if os.path.dirname(folder) != base or not os.path.isdir(folder):
        return False
    shutil.rmtree(folder, ignore_errors=True)
    _SEEN.pop(entry.folder, None)
    return not os.path.exists(folder)


def size_text(n: int) -> str:
    """'820 KB', '12.4 MB', '1.3 GB'."""
    if n < 1024 * 1024:
        return f"{max(1, round(n / 1024))} KB"
    if n < 1024 ** 3:
        mb = n / 1024 / 1024
        return f"{mb:.1f} MB" if mb < 100 else f"{mb:.0f} MB"
    return f"{n / 1024 ** 3:.1f} GB"


def date_text(t: float, now: float | None = None) -> str:
    """'today 14:05', 'yesterday 09:12', '21 Nov 2026'."""
    if t <= 0:
        return ""
    now = time.time() if now is None else now
    lt, ln = time.localtime(t), time.localtime(now)
    if (lt.tm_year, lt.tm_yday) == (ln.tm_year, ln.tm_yday):
        return time.strftime("today %H:%M", lt)
    y = time.localtime(now - 86400)
    if (lt.tm_year, lt.tm_yday) == (y.tm_year, y.tm_yday):
        return time.strftime("yesterday %H:%M", lt)
    months = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    return f"{lt.tm_mday} {months[lt.tm_mon - 1]} {lt.tm_year}"


def state_text(e: Entry) -> str:
    return {OK: "", CHANGED: "file changed since", MOVED: "file moved", OLD: "older version of the app"}.get(e.state, "")
