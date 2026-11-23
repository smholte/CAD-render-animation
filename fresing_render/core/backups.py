"""Automatic project backups (task 0246) – the rules, no Blender.

A backup is a copy of the open project saved every few minutes while something changed. It lies in a folder
``Backups`` next to the project file; a project that was never saved gets its backups in one app folder
(``Documents\\Fresing Render\\Backups\\Unsaved projects``). File names::

    <project name> backup YYYY-MM-DD HH-MM.blend          (seconds added when that minute's name is taken)

The cleaning deletes only files of exactly that pattern for that project in that folder: never anything else, never
the project itself. What is kept: the newest ``keep_last`` backups, plus the newest backup of each of the last
``days`` calendar days (today counts as one of them).

A backup keeps the project's relative paths as they are in the project (saved without remapping): it stands in for
the project file at the project's own place. Restore copies it there; opening it from the Backups folder by hand
may miss pictures or cache files that the project names relative to its own folder.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

FOLDER = "Backups"                       # next to the project
UNSAVED = "Unsaved projects"             # under <Documents>/Fresing Render/Backups
UNSAVED_NAME = "Unsaved project"         # the "project name" of a project never saved
RECOVERED = "Recovered projects"         # where an unsaved project's backup opens as a new file
APP_PARTS = ("Fresing Render", "Backups")
WORD = " backup "
EXT = ".blend"
STATE_FILE = "fresing_backups.json"      # in Blender's config folder: unsaved backups already opened / turned down

DEFAULT_MINUTES = 5
DEFAULT_KEEP = 5
DEFAULT_DAYS = 7
RANGE_MINUTES = (1, 60)
RANGE_KEEP = (1, 50)
RANGE_DAYS = (0, 60)
RETRY_SECONDS = 30                       # a backup that had to wait (a long job, a render …) is tried again then
FREE_FACTOR = 2.0                        # free space needed: twice the project's size
NEWER_MARGIN = 2.0                       # seconds: a backup counts as newer than the saved project only beyond this
UNSAVED_HOURS = 24                       # an unsaved project's backup is offered at the start for this long

_STAMP = re.compile(r"(\d{4})-(\d{2})-(\d{2}) (\d{2})-(\d{2})(?:-(\d{2}))?")


@dataclass(frozen=True)
class Backup:
    path: str
    when: datetime                       # from the name (local time)
    size: int                            # bytes
    mtime: float                         # the file's own time (seconds since the epoch)

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


# ---------------------------------------------------------------------------
# names
# ---------------------------------------------------------------------------

def project_name(project_path: str) -> str:
    """The name backups of this project carry: the project file's name without ``.blend``."""
    if not project_path:
        return UNSAVED_NAME
    base = os.path.basename(project_path)
    return base[:-len(EXT)] if base.lower().endswith(EXT) else base


def backup_name(name: str, when: datetime, seconds: bool = False) -> str:
    stamp = when.strftime("%Y-%m-%d %H-%M-%S" if seconds else "%Y-%m-%d %H-%M")
    return f"{name}{WORD}{stamp}{EXT}"


def free_name(folder: str, name: str, when: datetime) -> str:
    """A file name in ``folder`` that is not taken yet: the minute, else the second, else the second and a count."""
    path = os.path.join(folder, backup_name(name, when))
    if not os.path.exists(path):
        return path
    path = os.path.join(folder, backup_name(name, when, seconds=True))
    n = 2
    while os.path.exists(path):          # (the count is not part of the pattern: only a burst within a second)
        when = when + timedelta(seconds=1)
        path = os.path.join(folder, backup_name(name, when, seconds=True))
        n += 1
        if n > 120:
            break
    return path


def parse(file_name: str, name: str) -> datetime | None:
    """The time in a backup's file name, or None when the file is not a backup of the project ``name``."""
    prefix = f"{name}{WORD}"
    if not (file_name.startswith(prefix) and file_name.endswith(EXT)):
        return None
    m = _STAMP.fullmatch(file_name[len(prefix):-len(EXT)])
    if m is None:
        return None
    y, mo, d, h, mi, s = (int(g) if g is not None else 0 for g in m.groups())
    try:
        return datetime(y, mo, d, h, mi, s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# folders
# ---------------------------------------------------------------------------

def folder_next_to(project_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(project_path)), FOLDER)


def app_folder(documents: str) -> str:
    return os.path.join(documents, *APP_PARTS)


def unsaved_folder(documents: str) -> str:
    return os.path.join(app_folder(documents), UNSAVED)


MAX_PATH = 259                           # Windows' usual limit for a path (without the long-path switch)


def place_key(project_path: str) -> str:
    """8 hex digits of the project's place (case ignored on Windows): two projects of the same name in different
    folders never share a fallback folder."""
    import hashlib
    where = os.path.normcase(os.path.abspath(project_path))
    return hashlib.sha1(where.encode("utf-8", "surrogatepass")).hexdigest()[:8]


def fallback_folder(documents: str, project_path: str) -> str:
    """Where a project's backups go when the folder next to it cannot be written (a read-only share, a path too
    long, a colleague has the project open): one folder per project PLACE, not per name."""
    return os.path.join(app_folder(documents), "Projects", f"{project_name(project_path)} {place_key(project_path)}")


def recovered_folder(documents: str) -> str:
    return os.path.join(documents, "Fresing Render", RECOVERED)


def folders(project_path: str, documents: str) -> list[str]:
    """Every folder that may hold this project's backups, the usual one first."""
    if not project_path:
        return [unsaved_folder(documents)]
    return [folder_next_to(project_path), fallback_folder(documents, project_path)]


def listing(folder: str, name: str) -> list[Backup]:
    """The backups of the project ``name`` in ``folder``, newest first. Other files are not looked at."""
    out = []
    try:
        entries = list(os.scandir(folder))
    except OSError:
        return out
    for e in entries:
        when = parse(e.name, name)
        if when is None:
            continue
        try:
            if not e.is_file():
                continue
            st = e.stat()
        except OSError:
            continue
        out.append(Backup(e.path, when, st.st_size, st.st_mtime))
    out.sort(key=lambda b: (b.when, b.mtime), reverse=True)
    return out


def all_backups(project_path: str, documents: str) -> list[Backup]:
    out = []
    name = project_name(project_path)
    for f in folders(project_path, documents):
        out += listing(f, name)
    out.sort(key=lambda b: (b.when, b.mtime), reverse=True)
    return out


def total_size(backups) -> int:
    return sum(b.size for b in backups)


def size_text(n: int) -> str:
    if n >= 1024 ** 3:
        return f"{n / 1024 ** 3:.1f} GB"
    if n >= 1024 ** 2:
        return f"{n / 1024 ** 2:.0f} MB"
    if n >= 1024:
        return f"{n / 1024:.0f} kB"
    return f"{n} bytes"


# ---------------------------------------------------------------------------
# the keep rule
# ---------------------------------------------------------------------------

def keep(backups, keep_last: int, days: int, today: date) -> set:
    """Paths kept: the newest ``keep_last`` backups, plus the newest backup of each of the ``days`` calendar days
    up to ``today`` (``days`` = 0: none for the days). Backups dated after ``today`` (a clock put back) are kept."""
    items = sorted(backups, key=lambda b: (b.when, b.mtime), reverse=True)
    kept = {b.path for b in items[:max(0, keep_last)]}
    first_day = today - timedelta(days=max(0, days) - 1)
    seen_days = set()
    for b in items:
        d = b.when.date()
        if d > today:
            kept.add(b.path)
            continue
        if days > 0 and first_day <= d <= today and d not in seen_days:
            seen_days.add(d)
            kept.add(b.path)
    return kept


def to_delete(backups, keep_last: int, days: int, today: date) -> list:
    kept = keep(backups, keep_last, days, today)
    return [b for b in backups if b.path not in kept]


def clean(folder: str, name: str, keep_last: int, days: int, today: date, remove=os.remove) -> list[str]:
    """Delete the backups of ``name`` in ``folder`` the keep rule lets go. Returns the deleted paths. Only files whose
    name is a backup of this project are ever deleted (``listing``)."""
    gone = []
    for b in to_delete(listing(folder, name), keep_last, days, today):
        if parse(os.path.basename(b.path), name) is None or os.path.dirname(b.path) != folder:
            continue                                   # (never: listing gives only these)
        try:
            remove(b.path)
            gone.append(b.path)
        except OSError:
            pass
    return gone


# ---------------------------------------------------------------------------
# decisions
# ---------------------------------------------------------------------------

def due(now: float, since: float, minutes: float) -> bool:
    """Has ``minutes`` gone by since the last backup, save or open (all in seconds since the epoch)?"""
    return now - since >= minutes * 60.0


def enough_space(free: int, project_size: int) -> bool:
    """Is there room for a backup: at least twice the project's size free?"""
    return free >= FREE_FACTOR * max(0, project_size)


def newer_than_saved(backup: Backup | None, saved_mtime: float) -> bool:
    """Is this backup newer than the saved project file (Blender or the PC stopped before a save)?"""
    return backup is not None and backup.mtime > saved_mtime + NEWER_MARGIN


def newest_newer(backups, saved_mtime: float, handled=()) -> Backup | None:
    """The newest backup newer than the saved project that was not dealt with (``handled``: file names – task 0316:
    the copy kept by "Update without saving", whose changes the user chose not to keep)."""
    handled = set(handled or ())
    for b in backups:                                  # newest first
        if newer_than_saved(b, saved_mtime) and b.name not in handled:
            return b
    return None


def unsaved_offer(backups, now: float, handled) -> Backup | None:
    """At the start: the newest backup of an unsaved project from the last ``UNSAVED_HOURS`` that was never opened,
    turned down or saved as a project (``handled``: file names)."""
    handled = set(handled or ())
    for b in backups:
        if now - b.mtime > UNSAVED_HOURS * 3600:
            return None
        if b.name not in handled:
            return b
    return None


def clamp(value: int, rng: tuple) -> int:
    return max(rng[0], min(rng[1], int(value)))


# ---------------------------------------------------------------------------
# the small state file (unsaved backups already dealt with)
# ---------------------------------------------------------------------------

def load_state(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    handled = data.get("handled")
    data["handled"] = [str(x) for x in handled] if isinstance(handled, list) else []
    return data


def save_state(path: str, data: dict) -> None:
    data = dict(data)
    data["handled"] = list(dict.fromkeys(data.get("handled", [])))[-500:]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def mark_handled(path: str, names) -> None:
    data = load_state(path)
    data["handled"] = data["handled"] + [os.path.basename(n) for n in names]
    save_state(path, data)


def offer_text(backup: Backup, saved_mtime: float | None) -> str:
    """The start question's first line."""
    at = datetime.fromtimestamp(backup.mtime)
    t = at.strftime("%H:%M") if at.date() == date.today() else at.strftime("%d %b %H:%M")
    if saved_mtime is None:
        return f"Work that was never saved, from {t}."
    s = datetime.fromtimestamp(saved_mtime)
    st = s.strftime("%H:%M") if s.date() == at.date() else s.strftime("%d %b %H:%M")
    return f"A backup from {t} is newer than your saved project ({st})."
