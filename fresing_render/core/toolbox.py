"""The Toolbox folder (task 0217): how Fresing Render takes jobs from other tools on this PC and sends results back.

The format is ``smholte/toolbox-format`` tag v0.1.1 (pinned in ``tests/data/toolbox/tbf-v0.1.1``; read its FORMAT.md). In
short: a folder ``Toolbox`` in the user's home folder (``TOOLBOX_HOME`` overrides it); each tool has a manifest
``tools/<id>/toolbox.json`` and an inbox; a hand-over is a *job* = a folder in the receiver's inbox with the files and
``job.json`` (written last); the receiver writes ``status.json``; a result goes back as a new job in the sender's inbox.

Plain Python, no Blender (``blender/toolbox_inbox.py`` drives it). What it never does, whatever a job says: follow a
link, read a file whose name, size or type (by content, ``tbf/detect.py`` of the tag) is not right, write outside the
Toolbox folder, or raise out of :meth:`Inbox.look`. Windows refuses to replace or delete a file another program has
open: such a write or delete is tried again at the next look (FORMAT.md section 2).

The checks of the JSON files follow the tag's schemas field by field (no ``jsonschema`` in Blender's Python);
``tests/test_toolbox.py`` compares them with the tag's own checker on the samples and on broken copies.
"""

from __future__ import annotations

import errno
import json
import os
import re
import secrets
import shutil
import stat
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .tbf import detect as _detect
from .tbf import names as _names

VERSION = _names.VERSION                 # "0.1": the only version this code reads (FORMAT.md 3.5)
ME = "nl.fresing.render"
NAME = "Fresing Render"
FOLDER_FILE = "toolbox-folder.json"
FINAL = ("done", "failed", "cancelled")
CODES = ("bad-job", "unknown-action", "wrong-type", "busy", "error")
DAY = 24 * 3600
SHORT_WAIT = 60.0          # s a file that is still short may get before the job is refused (6.3 step 4)
ALIVE_EVERY = 10.0         # s between two alive.json (6.4)
PROGRESS_GAP = 1.0         # s: status.json at most once a second (7.1)
CLEAN_EVERY = 60.0         # s between two clean-ups of the inbox (7.4)
MAX_SIZE = 2**53 - 1       # bytes: no file is larger, JavaScript cannot count further (toolbox-format 0.1.1)
HOMEPAGE = "https://smholte.github.io/CAD-render-animation/"
ACTIONS = [
    {"id": "import-step", "label": "Import STEP", "accepts": ["step"]},
    {"id": "bake-house", "label": "Bake house scene", "accepts": ["hpscene"], "returns": ["hpbake"]},
]
PROMPT = {"bake-house": "Bake now", "import-step": "Import now"}


class Bad(Exception):
    """A JSON file of the format that must be refused; the text is one plain sentence."""


class JobProblem(Exception):
    """A job this tool must not do: ``code`` and ``text`` go into its status.json."""

    def __init__(self, code: str, text: str):
        super().__init__(text)
        self.code, self.text = code, one_line(text)


class NotReady(Exception):
    """A file of the job is still shorter than job.json says: look again later."""


def one_line(text, limit: int = 200) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[:limit - 1] + "…"


# ---------------------------------------------------------------------------
# the folder
# ---------------------------------------------------------------------------

def home() -> Path:
    """The Toolbox folder: ``TOOLBOX_HOME`` when set, else ``Toolbox`` in the user's home folder (FORMAT.md 2)."""
    env = os.environ.get("TOOLBOX_HOME")
    if env:
        return Path(env)
    base = os.environ.get("USERPROFILE") if os.name == "nt" else None
    return Path(base or Path.home()) / "Toolbox"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_job_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def to_bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def is_link(p: Path) -> bool:
    """A link, or on Windows a junction or any other reparse point: never read, never followed, never deleted
    through (FORMAT.md 7.4, 10)."""
    try:
        st = os.lstat(p)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    if getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
        # a junction, a mount point, a symbolic link: the "name surrogate" kinds. OneDrive's files on demand and
        # deduplicated files are reparse points too, but plain files and folders (independent review, task 0217)
        if getattr(st, "st_reparse_tag", 0) & 0x20000000:
            return True
    return bool(getattr(os.path, "isjunction", lambda _p: False)(p))


def is_plain_dir(p: Path) -> bool:
    return not is_link(p) and p.is_dir()


def is_plain_file(p: Path) -> bool:
    return not is_link(p) and p.is_file()


def write_json(path: Path, doc: dict) -> None:
    """Whole or not at all: written beside the file, then moved over it. Raises OSError when Windows refuses the move
    (another program has the file open); the caller tries again at its next look."""
    data = to_bytes(doc)
    tmp = path.with_name(f".{path.name}.{secrets.token_hex(3)}.tmp")
    try:
        with open(tmp, "xb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _no_links(*paths: Path) -> None:
    for p in paths:
        if is_link(p):
            raise OSError(f"{p} is a link, not a folder")


def ensure_folder(root: Path) -> None:
    """Make the Toolbox folder with its mark and ``tools/`` when they are missing (only a native tool does this)."""
    _no_links(root, root / "tools")
    (root / "tools").mkdir(parents=True, exist_ok=True)
    mark = root / FOLDER_FILE
    if not mark.exists():
        write_json(mark, {"format": "toolbox-folder", "version": VERSION})


def manifest(app_version: str, program: str = "", args=None) -> dict:
    """Fresing Render's toolbox.json (FORMAT.md 4). ``program``: what the Desktop shortcut starts (left out when it
    is not a full path, e.g. in tests)."""
    doc = {"format": "toolbox-tool", "version": VERSION, "id": ME, "name": NAME,
           "app_version": one_line(app_version, 40) or "0",
           "description": "Photo-realistic renders and animations of STEP assemblies; bakes light for House Planner.",
           "homepage": HOMEPAGE, "kind": "native"}
    if program and re.match(r"([A-Za-z]:[\\/]|/)", program) and len(program) <= 400:
        doc["start"] = {"program": program.replace("\\", "/")}
        if args:
            doc["start"]["args"] = [str(a) for a in args][:40]
    doc["actions"] = [dict(a) for a in ACTIONS]
    doc["handover"] = ["inbox"]
    return doc


HOUSE_PLANNER = "nl.fresing.house-planner"


def house_planner_standin() -> dict:
    """House Planner's manifest as the toolbox-format sample has it: the test tour, the PC check and
    ``tools/toolbox_send.py`` play House Planner's side with it until House Planner writes its own."""
    return {"format": "toolbox-tool", "version": VERSION, "id": HOUSE_PLANNER, "name": "House Planner",
            "app_version": "0.0.0-standin", "description": "Plan a house in 2D and 3D.",
            "homepage": "https://smholte.github.io/house-planner/", "kind": "web",
            "url": "https://smholte.github.io/house-planner/",
            "actions": [{"id": "import-bake", "label": "Import baked light", "accepts": ["hpbake"]}],
            "sends": ["hpscene"], "handover": ["inbox"]}


def play_house_planner(root: Path, hpscene: Path, title: str = "Sample house") -> str:
    """Send a house the way House Planner will (FORMAT.md 8, step 2): its manifest written when it has none, the job
    with ``return`` = import-bake. Returns the job id."""
    d = root / "tools" / HOUSE_PLANNER
    if not (d / "toolbox.json").exists():
        (d / "inbox").mkdir(parents=True, exist_ok=True)
        write_json(d / "toolbox.json", house_planner_standin())
    return send(root, HOUSE_PLANNER, ME, "bake-house", [Path(hpscene)], title=title, ret="import-bake")


def install(root: Path, app_version: str, program: str = "", args=None) -> Path:
    """The folder made when missing and the manifest written again (installer and every start). Returns its path."""
    ensure_folder(root)
    d = root / "tools" / ME
    _no_links(root, root / "tools", d, d / "inbox")
    (d / "inbox").mkdir(parents=True, exist_ok=True)
    write_json(d / "toolbox.json", manifest(app_version, program, args))
    return d / "toolbox.json"


def uninstall(root: Path) -> bool:
    """Remove ``tools/nl.fresing.render/`` – only that folder, only when it is a real folder. True when it is gone."""
    d = root / "tools" / ME
    if is_link(root) or is_link(root / "tools") or is_link(d):
        return False
    if d.is_dir():
        _remove_tree(d)
    return not d.exists()


def _remove_tree(d: Path) -> bool:
    """Delete a folder of plain files and folders; anything that is a link is left alone (and so is its folder).
    True when it is gone; what Windows will not let go now goes at the next look."""
    ok = True
    try:
        entries = list(os.scandir(d))
    except OSError:
        return False
    for e in entries:
        p = Path(e.path)
        if is_link(p):
            ok = False
        elif e.is_dir(follow_symlinks=False):
            ok = _remove_tree(p) and ok
        else:
            try:
                os.unlink(p)
            except OSError:
                ok = False
    if ok:
        try:
            os.rmdir(d)
        except OSError:
            ok = False
    return ok


# ---------------------------------------------------------------------------
# strict JSON, field by field as the tag's schemas say
# ---------------------------------------------------------------------------

_JOB = _names.JOB_ID.pattern
_ACTION = _names.ACTION_ID.pattern
_TYPE_REF = re.compile(r"(ext:[a-z0-9]{0,16}|[a-z0-9][a-z0-9-]{0,31}|[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)+)")
_VERSION = re.compile(r"\d+\.\d+")


def _s(pattern=None, maxlen=None, minlen=0, prefix=None):
    rx = re.compile(pattern) if isinstance(pattern, str) else pattern

    def check(v):
        if not isinstance(v, str):
            return "is not a text"
        if len(v) < minlen:
            return "is empty" if minlen == 1 else f"is shorter than {minlen} characters"
        if maxlen is not None and len(v) > maxlen:
            return f"is longer than {maxlen} characters"
        if rx is not None and not rx.fullmatch(v):
            return "is not of the right form"
        if prefix and not v.startswith(prefix):
            return f"does not start with {prefix}"
        return None
    return check


def _time(v):
    return _names.time_problem(v)


def _enum(*values):
    return lambda v: None if (isinstance(v, str) and v in values) else f"is not one of {', '.join(values)}"


def _const(value):
    return lambda v: None if v == value else f"is not {value}"


def _int(v):
    ok = (isinstance(v, int) and not isinstance(v, bool)) or (isinstance(v, float) and v.is_integer())
    return None if ok and v >= 0 else "is not a whole number ≥ 0"       # (5.0 counts, as JSON Schema counts it)


def _fraction(v):
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1
    return None if ok else "is not a number from 0 to 1"


def _obj(spec_fields, required):
    def check(v):
        if not isinstance(v, dict):
            return "is not an object"
        return _fields(v, spec_fields, required)
    return check


def _list(item, minn=0, maxn=None, unique=False):
    def check(v):
        if not isinstance(v, list):
            return "is not a list"
        if len(v) < minn:
            return "is empty" if minn == 1 else f"has fewer than {minn} items"
        if maxn is not None and len(v) > maxn:
            return f"has more than {maxn} items"
        if unique and len({json.dumps(x, sort_keys=True) for x in v}) != len(v):
            return "has an item twice"
        for i, x in enumerate(v):
            why = item(x)
            if why:
                return f"/{i} {why}"
        return None
    return check


def _fields(doc: dict, spec: dict, required) -> str | None:
    for k in required:
        if k not in doc:
            return f"has no {k}"
    for k, v in doc.items():
        if k not in spec:
            return f"has a field the format does not know: {k}"
        why = spec[k](v)
        if why:
            return f"{k} {why}" if not why.startswith("/") else f"{k}{why}"
    return None


_TOOL_ID = _s(_names.TOOL_ID, 80)
_FILE = _obj({"name": _s(None, 120, 1), "type": _s(_TYPE_REF, 80), "size": _int}, ("name", "type", "size"))
SPECS = {
    "folder": ({"format": _const("toolbox-folder"), "version": _s(_VERSION)}, ("format", "version")),
    "job": ({"format": _const("toolbox-job"), "version": _s(_VERSION), "job": _s(_JOB), "created": _time,
             "from": _TOOL_ID, "to": _TOOL_ID, "action": _s(_ACTION), "files": _list(_FILE, 1, 100),
             "return": _s(_ACTION),
             "reply_to": _obj({"tool": _TOOL_ID, "job": _s(_JOB)}, ("tool", "job")),
             "title": _s(None, 120), "options": lambda v: None if isinstance(v, dict) else "is not an object"},
            ("format", "version", "job", "created", "from", "to", "action", "files")),
    "status": ({"format": _const("toolbox-status"), "version": _s(_VERSION), "job": _s(_JOB), "updated": _time,
                "state": _enum("waiting", "working", "done", "failed", "cancelled"), "fraction": _fraction,
                "text": _s(None, 200), "code": _s(_ACTION), "reply": _s(_JOB)},
               ("format", "version", "job", "updated", "state")),
    "cancel": ({"format": _const("toolbox-cancel"), "version": _s(_VERSION), "job": _s(_JOB), "asked": _time},
               ("format", "version", "job", "asked")),
    "alive": ({"format": _const("toolbox-alive"), "version": _s(_VERSION), "seen": _time,
               "app_version": _s(None, 40, 1)}, ("format", "version", "seen")),
    "tool": ({"format": _const("toolbox-tool"), "version": _s(_VERSION), "id": _TOOL_ID, "name": _s(None, 60, 1),
              "app_version": _s(None, 40, 1), "description": _s(None, 300), "homepage": _s(None, 300, prefix="https://"),
              "kind": _enum("native", "web"), "url": _s(None, 300, prefix="https://"), "icon": _s(None, 120, 1),
              "start": _obj({"program": _s(None, 400, 1), "args": _list(_s(None, 400), 0, 40)}, ("program",)),
              "types": _list(lambda v: None if isinstance(v, dict) else "is not an object", 0, 50),
              "actions": _list(_obj({"id": _s(_ACTION), "label": _s(None, 60, 1),
                                     "accepts": _list(_s(_TYPE_REF, 80), 1, 100, unique=True),
                                     "returns": _list(_s(_TYPE_REF, 80), 0, 100, unique=True)},
                                    ("id", "label", "accepts")), 0, 50),
              "sends": _list(_s(_TYPE_REF, 80), 0, 100, unique=True),
              "handover": _list(_enum("inbox"), 0, None, unique=True)},
             ("format", "version", "id", "name", "kind", "actions")),
}
WHAT = {"job": "This job", "status": "This status", "cancel": "This cancel note", "alive": "This alive note",
        "tool": "This manifest", "folder": "This Toolbox folder"}


def version_note(kind: str, v: str) -> str:
    """The clear sentence of FORMAT.md 3.5 for a file of another version."""
    try:
        newer = tuple(int(x) for x in v.split(".")) > tuple(int(x) for x in VERSION.split("."))
    except ValueError:
        newer = True
    what = WHAT.get(kind, "This file").replace("This ", "")
    if newer:
        return (f"This {what} was written by a newer tool (toolbox format {v}). Update Fresing Render to read it.")
    return (f"This {what} was written by an older tool (toolbox format {v}); Fresing Render reads {VERSION}. "
            "Update the tool that sent it.")


def check_doc(doc: dict, kind: str) -> None:
    """Raise :class:`Bad` when ``doc`` is not a right ``kind`` file of version 0.1."""
    v = doc.get("version")
    if isinstance(v, str) and _VERSION.fullmatch(v) and v != VERSION:
        raise Bad(version_note(kind, v))
    spec, required = SPECS[kind]
    why = _fields(doc, spec, required)
    if why:
        raise Bad(f"{kind}.json {why}" if kind not in ("tool", "folder") else
                  f"{'toolbox.json' if kind == 'tool' else FOLDER_FILE} {why}")


def read_doc(path: Path, kind: str) -> dict:
    """A JSON file of the format, read strictly (FORMAT.md 3.4, 3.5). Raises :class:`Bad`; OSError when it cannot be
    read now (missing, being replaced) – try again at the next look."""
    if is_link(path):
        raise Bad(f"{path.name} is a link, not a file")
    if path.is_dir():
        raise Bad(f"{path.name} is a folder, not a file")
    with open(path, "rb") as fh:
        data = fh.read(_names.MAX_JSON + 1)
    if not data:
        raise OSError(f"{path.name} is empty (still being written?)")
    try:
        doc = _names.load_json(data, "last")      # a key written twice: the last counts, as in JavaScript (0.1.1)
    except _names.JsonError as e:
        raise Bad(f"{path.name} {e}") from None
    check_doc(doc, kind)
    return doc


# ---------------------------------------------------------------------------
# other tools and file types
# ---------------------------------------------------------------------------

def builtin_types() -> list[dict]:
    return _detect.load_types()


def read_tool(root: Path, tool_id: str) -> dict | None:
    """Another tool's manifest, or None when it is missing, a link, broken or of another version."""
    if not _names.is_tool_id(tool_id):
        return None
    d = root / "tools" / tool_id
    if not is_plain_dir(d):
        return None
    try:
        doc = read_doc(d / "toolbox.json", "tool")
    except (OSError, Bad):
        return None
    if doc["id"] != tool_id:
        return None
    ids = [a["id"] for a in doc["actions"]]
    if len(set(ids)) != len(ids):
        return None
    for t in doc.get("types", []):
        if _detect.type_problems(t, "types", own=True):
            return None
    return doc


def all_types(root: Path) -> list[dict]:
    """The built-in types followed by every tool's own, as FORMAT.md 5.3 orders them; a type two tools define
    differently is used by neither."""
    own: dict[str, dict] = {}
    clash = set()
    tools = root / "tools"
    try:
        names = sorted(e.name for e in os.scandir(tools)) if is_plain_dir(tools) else []
    except OSError:
        names = []
    for name in names:
        for t in (read_tool(root, name) or {}).get("types", []):
            if t["id"] in own and own[t["id"]] != t:
                clash.add(t["id"])
            own.setdefault(t["id"], t)
    return builtin_types() + [own[k] for k in sorted(own) if k not in clash]


KNOWN = {"nl.fresing.house-planner": "House Planner"}     # names to show when a tool's manifest cannot be read


def tool_name(root: Path, tool_id: str) -> str:
    doc = read_tool(root, tool_id)
    return doc["name"] if doc else KNOWN.get(tool_id, tool_id)


def detect(path: Path, types: list[dict]) -> str:
    return _detect.detect(path, types)[0]


# ---------------------------------------------------------------------------
# a job of my inbox
# ---------------------------------------------------------------------------

@dataclass
class Job:
    """A job this copy of Fresing Render holds (``waiting`` or ``working``)."""
    id: str
    folder: Path
    doc: dict
    files: list                      # [(name, type, Path)]
    state: str = "waiting"
    text: str = ""
    sender: str = ""                 # the sender's name as people read it
    cancel_asked: bool = False
    note: str = ""                   # what the app shows under the job (busy, …)
    data: dict = field(default_factory=dict)       # the app's own (scene name, temp folder …)

    @property
    def action(self) -> str:
        return self.doc["action"]

    @property
    def title(self) -> str:
        return self.doc.get("title") or (self.files[0][0] if self.files else self.id)

    def headline(self) -> str:
        return f"From {self.sender or self.doc['from']}: {self.title}"


def take(root: Path, me: dict, folder: Path, types: list[dict] | None = None) -> tuple[dict, list]:
    """Check a job of my inbox as FORMAT.md 6.3 says (before anything opens a file of it). Returns the job and its
    files as (name, type, path). Raises :class:`JobProblem`; :class:`NotReady` when a file is still short; OSError
    when job.json cannot be read just now."""
    try:
        job = read_doc(folder / "job.json", "job")
    except Bad as e:
        raise JobProblem("bad-job", str(e)) from None
    if job["job"] != folder.name:
        raise JobProblem("bad-job", f"the job's id {job['job']} is not its folder's name {folder.name}")
    if job["to"] != me["id"]:
        raise JobProblem("bad-job", f"the job is for {job['to']}, not for {me['id']}")
    if job["from"] == job["to"]:
        raise JobProblem("bad-job", "the job comes from the tool it is for")
    if "reply_to" in job and job["reply_to"]["tool"] != job["from"]:
        raise JobProblem("bad-job", "reply_to names another tool than the one that sent the job")
    if "reply_to" in job and "return" in job:
        raise JobProblem("bad-job", "a reply job has no return")
    action = next((a for a in me["actions"] if a["id"] == job["action"]), None)
    if action is None:
        raise JobProblem("unknown-action", f"{me['name']} has no action {job['action']}")
    types = types if types is not None else all_types(root)
    out, seen = [], set()
    for f in job["files"]:
        why = _names.name_problem(f["name"])
        try:
            f["name"].encode("utf-8")
        except UnicodeError:
            why = why or "is not a name this PC can write"
        if why:
            raise JobProblem("bad-job", f"the file name {f['name']!r} {why}")
        if f["name"].lower() in seen:
            raise JobProblem("bad-job", f"the file {f['name']} is listed twice")
        seen.add(f["name"].lower())
    for f in job["files"]:
        if f["size"] > MAX_SIZE:
            raise JobProblem("bad-job", f"{f['name']}: no file has {f['size']} bytes")
        p = folder / f["name"]
        try:
            os.lstat(p)
        except (FileNotFoundError, NotADirectoryError):
            pass
        except ValueError:
            raise JobProblem("bad-job", f"the file name {f['name']!r} cannot be used on this PC") from None
        except OSError as e:
            if e.errno in (errno.ENAMETOOLONG, errno.EINVAL, errno.EILSEQ):
                raise JobProblem("bad-job", f"the file name {f['name']!r} cannot be used on this PC") from None
            raise                                      # held by another program just now: the next look
        if is_link(p) or (p.exists() and not p.is_file()):
            raise JobProblem("bad-job", f"{f['name']} is not a plain file")
        if not p.is_file():
            raise NotReady(f"{f['name']} is not there yet")
        size = p.stat().st_size
        if size < f["size"]:
            raise NotReady(f"{f['name']} is not complete yet")
        if size != f["size"]:
            raise JobProblem("bad-job", f"{f['name']} is {size} bytes, job.json says {f['size']}")
    for f in job["files"]:
        p = folder / f["name"]
        kind = detect(p, types)
        if kind != f["type"]:
            raise JobProblem("wrong-type", f"{f['name']} is {kind}, not {f['type']}")
        if kind not in action["accepts"]:
            raise JobProblem("wrong-type", f"{action['label']} does not take {kind} ({f['name']})")
        out.append((f["name"], kind, p))
    return job, out


def status_doc(job: str, state: str, *, fraction=None, text=None, code=None, reply=None) -> dict:
    doc = {"format": "toolbox-status", "version": VERSION, "job": job, "state": state, "updated": now()}
    if fraction is not None:
        doc["fraction"] = round(min(1.0, max(0.0, float(fraction))), 4)
    if text:
        doc["text"] = one_line(text)
    if code is not None:
        doc["code"] = code
    if reply is not None:
        doc["reply"] = reply
    return doc


def claim(folder: Path, doc: dict) -> bool:
    """Take a job: create its status.json only if it is not there yet (an exclusive create, FORMAT.md 6.3). False when
    another copy was first."""
    try:
        with open(folder / "status.json", "xb") as fh:
            fh.write(to_bytes(doc))
        return True
    except OSError:          # it exists (another copy was first), or Windows refused: the next look tries again
        return False


def send(root: Path, me: str, to: str, action: str, files: list[Path], *, title: str | None = None,
         reply_to: dict | None = None, ret: str | None = None, options: dict | None = None,
         types: list[dict] | None = None) -> str:
    """Write a job into ``to``'s inbox (FORMAT.md 6.2) and return its id. Raises ValueError when the receiver does not
    take it (nothing is written then), OSError when the folder cannot be written (what was written is removed)."""
    tool = read_tool(root, to)
    if tool is None:
        raise ValueError(f"{to} has no readable manifest in the Toolbox folder")
    act = next((a for a in tool["actions"] if a["id"] == action), None)
    if act is None:
        raise ValueError(f"{tool['name']} has no action {action}")
    types = types if types is not None else all_types(root)
    listed, seen = [], set()
    for f in files:
        why = _names.name_problem(f.name)
        if why:
            raise ValueError(f"the file name {f.name!r} {why}")
        if f.name.lower() in seen:
            raise ValueError(f"two files are named {f.name} (capitals do not count)")
        seen.add(f.name.lower())
        kind = detect(f, types)
        if kind not in act["accepts"]:
            raise ValueError(f"{tool['name']} does not take {kind} for {action} ({f.name})")
        listed.append({"name": f.name, "type": kind, "size": f.stat().st_size})
    inbox = root / "tools" / to / "inbox"
    if is_link(inbox):
        raise ValueError(f"the inbox of {tool['name']} is a link")
    inbox.mkdir(exist_ok=True)
    for _ in range(5):
        job = new_job_id()
        folder = inbox / job
        try:
            folder.mkdir()
            break
        except FileExistsError:
            continue
    else:
        raise OSError("no new job id could be made")
    try:
        for f in files:
            shutil.copyfile(f, folder / f.name)
        doc = {"format": "toolbox-job", "version": VERSION, "job": job, "created": now(), "from": me, "to": to,
               "action": action, "files": listed}
        for key, value in (("return", ret), ("reply_to", reply_to), ("title", title and one_line(title, 120)),
                           ("options", options)):
            if value is not None:
                doc[key] = value
        write_json(folder / "job.json", doc)        # last: only now the job exists for the receiver
    except BaseException:
        _remove_tree(folder)
        raise
    return job


# ---------------------------------------------------------------------------
# the inbox, looked at every 2 seconds
# ---------------------------------------------------------------------------

WAITING_TEXT = {"bake-house": "Waiting for you in Fresing Render: press Bake now",
                "import-step": "Waiting for you in Fresing Render: press Import now"}
CLOSED_TEXT = "Fresing Render was closed while it worked on this"


def busy_text(action: str, busy: str) -> str:
    thing = "house" if action == "bake-house" else "file"
    return f"Fresing Render is busy ({busy}); the {thing} waits"


class Inbox:
    """Fresing Render's side of the Toolbox folder, for one copy of the app. ``look()`` is called every 2 seconds
    (the app's timer); it never raises. ``jobs`` are the jobs this copy holds; ``notes`` what it refused lately."""

    def __init__(self, root: Path, app_version: str = "0", program: str = "", args=None,
                 keep_dir: Path | None = None, clock=time.time):
        self.root = Path(root)
        self.app_version = app_version
        self.program, self.args = program, args
        self.keep_dir = Path(keep_dir) if keep_dir else Path.home() / "Documents" / "Fresing Render" / "House bakes"
        self.clock = clock
        self.me = manifest(app_version, program, args)
        self.jobs: dict[str, Job] = {}
        self.notes: list[str] = []            # one line each, newest last (the panel shows the last)
        self.problem = ""                     # the folder cannot be used: one line for the panel
        self.started = False
        self._later: dict[Path, dict] = {}    # status writes Windows refused, tried at the next look
        self._wrote: dict[str, float] = {}    # job -> when its status was last written
        self._short: dict[str, float] = {}    # job -> when a short file was first seen
        self._alive_at = -1e9
        self._alive_bytes: bytes | None = None
        self._clean_at = -1e9
        self._done_files: set[Path] = set()   # final jobs whose files are still to delete
        self._other_at = -1e9                 # when another copy's alive.json was last seen fresh
        self._adopted = False

    # ---- paths
    @property
    def inbox(self) -> Path:
        return self.root / "tools" / ME / "inbox"

    def folder(self, job: str) -> Path:
        return self.inbox / job

    # ---- start
    def start(self) -> bool:
        """The folder and the manifest; then the jobs an earlier run left (FORMAT.md 6.3). False (and ``problem``)
        when the folder cannot be used: the app works as without it."""
        try:
            install(self.root, self.app_version, self.program, self.args)
        except OSError as e:
            self.problem = one_line(f"The Toolbox folder {self.root} cannot be used ({e.strerror or e}): houses from "
                                    "House Planner do not arrive by themselves")
            return False
        self.problem = ""
        self.started = True
        self._watch_others()
        if not self._others():
            self._adopt()
        return True

    def _watch_others(self) -> None:
        """Another copy of Fresing Render is watching when alive.json is fresh and not the one this copy wrote."""
        path = self.root / "tools" / ME / "alive.json"
        try:
            data = path.read_bytes() if is_plain_file(path) else None
        except OSError:
            data = None
        if data is None or data == self._alive_bytes:
            return
        try:
            seen = datetime.fromisoformat(read_doc(path, "alive")["seen"].replace("Z", "+00:00")).timestamp()
        except (OSError, Bad, ValueError):
            return
        if abs(time.time() - seen) <= 30:
            self._other_at = self.clock()

    def _others(self) -> bool:
        return self.clock() - self._other_at <= 35.0

    def _adopt(self) -> None:
        """Jobs an earlier run left (FORMAT.md 6.3) – only while no other copy of the app is watching: its jobs are
        its own (the review's 4b: two windows)."""
        self._adopted = True
        for d in self._job_folders():
            sp = d / "status.json"
            if not sp.exists():
                continue
            try:
                st = read_doc(sp, "status")
            except (OSError, Bad):
                continue
            if st["state"] in FINAL or d.name in self.jobs:
                continue
            if st["state"] == "working":
                if os.path.lexists(d / "cancel.json"):      # it was asked to stop, and it did stop
                    self._write(d.name, "cancelled", text=f"Cancelled; {CLOSED_TEXT}")
                else:
                    self._write(d.name, "failed", text=CLOSED_TEXT, code="error")
                self._done_files.add(d)
                continue
            try:                                             # waiting: ask again
                job, files = take(self.root, self.me, d)
            except OSError:
                continue                                     # held by another program now: still waiting
            except (JobProblem, NotReady) as e:
                code = e.code if isinstance(e, JobProblem) else "bad-job"
                self._write(d.name, "failed", text=getattr(e, "text", str(e)), code=code)
                self._done_files.add(d)
                continue
            self.jobs[d.name] = Job(d.name, d, job, files, "waiting", st.get("text", ""),
                                    tool_name(self.root, job["from"]))

    # ---- one look
    def look(self, busy: str = "") -> list[str]:
        """Everything of one look; returns what happened (lines for the app's status bar). Never raises."""
        events: list[str] = []
        try:
            if not self.started:
                if not self.start():
                    return events
            t = self.clock()
            self._flush()
            self._watch_others()
            if not self._adopted and not self._others():
                self._adopt()
            if not all(is_plain_dir(p) for p in (self.root, self.root / "tools", self.inbox.parent, self.inbox)):
                # deleted while the app ran (make again) – or a link put in its place (refused: problem)
                self.started = False
                if not self.start():
                    return events
            events += self._new_jobs(busy)
            events += self._held(busy)
            if t - self._alive_at >= ALIVE_EVERY:
                self.write_alive()
            if t - self._clean_at >= CLEAN_EVERY:
                self._clean_at = t
                self.clean()
            self._delete_done_files()
        except Exception as e:  # noqa: BLE001 - a look never breaks the app
            self.notes.append(one_line(f"The Toolbox inbox could not be read: {e}"))
        return events

    def _job_folders(self) -> list[Path]:
        try:
            entries = sorted(os.scandir(self.inbox), key=lambda e: e.name)
        except OSError:
            return []
        out = []
        for e in entries:
            p = Path(e.path)
            if _names.is_job_id(e.name) and e.is_dir(follow_symlinks=False) and not is_link(p):
                out.append(p)
        return out

    def _new_jobs(self, busy: str) -> list[str]:
        events = []
        types = None
        for d in self._job_folders():
            if d.name in self.jobs or (d / "status.json").exists() or os.path.lexists(d / "status.json"):
                continue
            if not os.path.lexists(d / "job.json"):
                continue                                 # not written yet (6.3 step 1)
            if types is None:
                types = all_types(self.root)
            try:
                job, files = take(self.root, self.me, d, types)
            except NotReady as e:
                first = self._short.setdefault(d.name, self.clock())
                if self.clock() - first < SHORT_WAIT:
                    continue
                self._refuse(d, "bad-job", f"{e}: a file of the job was still not complete after a minute")
                events.append(self.notes[-1])
                continue
            except JobProblem as p:
                if self._refuse(d, p.code, p.text):
                    events.append(self.notes[-1])
                continue
            except OSError:
                continue                                 # job.json just being written: next look
            except Exception as e:  # noqa: BLE001 - one odd job never stops the look at the others
                if self._refuse(d, "bad-job", f"the job cannot be read ({e})"):
                    events.append(self.notes[-1])
                continue
            self._short.pop(d.name, None)
            action = job["action"]
            text = busy_text(action, busy) if busy else WAITING_TEXT[action]
            if not claim(d, status_doc(d.name, "waiting", text=text)):
                continue                                 # another copy of Fresing Render took it
            self._wrote[d.name] = self.clock()
            j = Job(d.name, d, job, files, "waiting", text, tool_name(self.root, job["from"]))
            j.note = text if busy else ""
            self.jobs[d.name] = j
            events.append(f"{j.headline()} – {PROMPT[action]} in 5 Scene & Render")
        return events

    def _refuse(self, d: Path, code: str, text: str) -> bool:
        self._short.pop(d.name, None)
        if not claim(d, status_doc(d.name, "failed", text=text, code=code)):
            return False
        self._done_files.add(d)
        sender = ""
        try:
            sender = tool_name(self.root, read_doc(d / "job.json", "job")["from"])
        except (OSError, Bad):
            pass
        self.notes.append(one_line(f"A job{' from ' + sender if sender else ''} was refused: {text}"))
        del self.notes[:-20]
        return True

    def _held(self, busy: str) -> list[str]:
        events = []
        for jid, j in list(self.jobs.items()):
            if not j.folder.is_dir():                    # the sender took it back
                self.jobs.pop(jid, None)
                continue
            asked = os.path.lexists(j.folder / "cancel.json")
            if j.state == "working":
                if asked and not j.cancel_asked:
                    j.cancel_asked = True
                    events.append(f"{j.sender or 'The sender'} asked to stop: {j.title}")
                continue
            # waiting: did another copy take it, or did the sender cancel it?
            try:
                st = read_doc(j.folder / "status.json", "status")
                if st["state"] != "waiting":
                    self.jobs.pop(jid, None)
                    continue
            except (OSError, Bad):
                pass
            if asked:
                self.finish(jid, "cancelled", f"Cancelled by {j.sender or j.doc['from']} before it started")
                events.append(f"{j.headline()} was cancelled by its sender")
                continue
            want = busy_text(j.action, busy) if busy else WAITING_TEXT[j.action]
            if want != j.text:
                if self._write(jid, "waiting", text=want):
                    j.text = want
                j.note = want if busy else ""
        return events

    # ---- status
    def _write(self, jid: str, state: str, **kw) -> bool:
        """status.json of a job, whole. Windows may refuse while another program reads it: kept and written at the next
        look (a newer write of the same job replaces a kept one). True when it is on disk now."""
        path = self.folder(jid) / "status.json"
        doc = status_doc(jid, state, **kw)
        self._later.pop(path, None)
        try:
            if is_link(path) or is_link(path.parent):
                return False
            write_json(path, doc)
            self._wrote[jid] = self.clock()
            return True
        except OSError:
            if path.parent.is_dir():
                self._later[path] = doc
            return False

    def _flush(self) -> None:
        for path, doc in list(self._later.items()):
            try:
                if not path.parent.is_dir():
                    self._later.pop(path, None)
                    continue
                doc = dict(doc, updated=now())
                write_json(path, doc)
                self._later.pop(path, None)
            except OSError:
                pass

    def progress(self, jid: str, fraction: float, text: str) -> bool:
        """``working`` with how far it is, at most once a second (FORMAT.md 7.1)."""
        j = self.jobs.get(jid)
        if j is None:
            return False
        if self.clock() - self._wrote.get(jid, -1e9) < PROGRESS_GAP:
            return False
        j.text = one_line(text)
        return self._write(jid, "working", fraction=fraction, text=text)

    def begin(self, jid: str, text: str) -> str:
        """The user pressed Bake now / Import now: ``working``. Returns '' or why it cannot start."""
        j = self.jobs.get(jid)
        if j is None:
            return "This job is no longer there"
        if j.state != "waiting":
            return "This job is already being worked on"
        try:
            st = read_doc(j.folder / "status.json", "status")
            if st["state"] != "waiting":
                self.jobs.pop(jid, None)
                return "Another Fresing Render window took this job"
        except (OSError, Bad):
            pass
        if os.path.lexists(j.folder / "cancel.json"):
            self.finish(jid, "cancelled", f"Cancelled by {j.sender or j.doc['from']} before it started")
            return "The sender cancelled this job"
        try:                                              # the files again: they may have changed meanwhile
            j.doc, j.files = take(self.root, self.me, j.folder)
        except OSError:              # a virus scanner or the sender holds a file for a moment (Windows): not a fault
            return "A file of this job is busy just now: try again in a moment"
        except (JobProblem, NotReady) as e:
            self.finish(jid, "failed", getattr(e, "text", str(e)), code=getattr(e, "code", "bad-job"))
            return getattr(e, "text", str(e))
        j.state, j.text = "working", text
        self._write(jid, "working", fraction=0.0, text=text)
        return ""

    def finish(self, jid: str, state: str, text: str = "", *, code=None, reply=None) -> None:
        """A final status; the job's files are deleted (not job.json and status.json: FORMAT.md 7.4, review 3)."""
        j = self.jobs.pop(jid, None)
        folder = j.folder if j is not None else self.folder(jid)
        if state == "failed" and code is None:
            code = "error"
        self._write(jid, state, text=text, code=code if state == "failed" else None, reply=reply)
        self._done_files.add(folder)
        self._delete_done_files()

    def not_now(self, jid: str) -> None:
        self.finish(jid, "cancelled", "You said not now in Fresing Render")

    def _delete_done_files(self) -> None:
        for folder in list(self._done_files):
            if not is_plain_dir(folder):
                self._done_files.discard(folder)
                continue
            left = False
            try:
                entries = list(os.scandir(folder))
            except OSError:
                continue
            for e in entries:
                if e.name in ("job.json", "status.json", "cancel.json") or e.name.startswith(".status.json."):
                    continue
                p = Path(e.path)
                if is_link(p) or e.is_dir(follow_symlinks=False):
                    continue                              # never followed, never deleted through
                try:
                    os.unlink(p)
                except OSError:
                    left = True
            if not left:
                self._done_files.discard(folder)

    # ---- the reply
    def reply(self, jid: str, results: list[Path], done_text: str) -> tuple[str | None, str]:
        """FORMAT.md 7.2: the results back to the sender as a new job, then this job ``done`` (reply first, status
        second). When the sender cannot take it, the results are kept in ``keep_dir`` and the text says where.
        Returns (reply job id or None, the status text)."""
        j = self.jobs.get(jid)
        doc = j.doc if j is not None else read_doc(self.folder(jid) / "job.json", "job")
        rid, text = None, done_text
        why = ""
        if "return" not in doc:
            why = "no reply was asked for"
        elif not results:
            why = "there was nothing to send"
        else:
            try:
                rid = send(self.root, ME, doc["from"], doc["return"], results, title=doc.get("title"),
                           reply_to={"tool": ME, "job": jid})
            except (ValueError, OSError) as e:
                why = str(e)
        if rid is None and results:
            sender = tool_name(self.root, doc["from"])
            try:
                kept = self.keep(results)
            except OSError as e:
                self.finish(jid, "failed", f"{done_text}, but it could not be sent back ({why}) nor kept ({e})",
                            code="error")
                return None, ""
            text = one_line(f"{done_text}; kept as {kept} – {sender} could not take it ({why})")
        elif rid is not None:
            text = f"{done_text}; sent back to {tool_name(self.root, doc['from'])}"
        self.finish(jid, "done", text, reply=rid)
        return rid, text

    def keep(self, results: list[Path]) -> str:
        """Copy results into Fresing Render's own folder (never into the Toolbox folder); returns where."""
        self.keep_dir.mkdir(parents=True, exist_ok=True)
        out = []
        for f in results:
            stem, ext = os.path.splitext(f.name)
            dest = self.keep_dir / f.name
            n = 2
            while dest.exists():
                dest = self.keep_dir / f"{stem} ({n}){ext}"
                n += 1
            shutil.copyfile(f, dest)
            out.append(str(dest))
        return ", ".join(out)

    # ---- alive.json
    def write_alive(self) -> None:
        path = self.root / "tools" / ME / "alive.json"
        try:
            there = path.read_bytes() if is_plain_file(path) else b""
        except OSError:
            there = b""
        at = datetime.now().astimezone()
        for _ in range(5):           # thousandths, and never the bytes already there: whose file it is stays clear
            doc = {"format": "toolbox-alive", "version": VERSION, "seen": at.isoformat(timespec="milliseconds"),
                   "app_version": self.me["app_version"]}
            if to_bytes(doc) != there:
                break
            at += timedelta(milliseconds=1)
        try:
            write_json(path, doc)
            self._alive_bytes = to_bytes(doc)
            self._alive_at = self.clock()
        except OSError:
            pass

    def remove_alive(self) -> bool:
        """On closing: delete alive.json only when this copy wrote the newest one (FORMAT.md 6.4)."""
        path = self.root / "tools" / ME / "alive.json"
        try:
            if self._alive_bytes is not None and not is_link(path) and path.read_bytes() == self._alive_bytes:
                path.unlink()
                return True
        except OSError:
            pass
        return False

    # ---- cleaning up (FORMAT.md 7.4)
    def clean(self, at: float | None = None) -> int:
        """My inbox: a job a day after its status became final, anything after 30 days. Only real folders of plain
        files are deleted; a link is never followed nor deleted through. Returns how many folders went."""
        at = time.time() if at is None else at
        gone = 0
        for d in self._job_folders():
            if d.name in self.jobs:
                continue
            try:
                age = at - d.stat().st_mtime
            except OSError:
                continue
            final = False
            try:
                st = read_doc(d / "status.json", "status")
                if st["state"] in FINAL:
                    final = True
                    age = at - datetime.fromisoformat(st["updated"].replace("Z", "+00:00")).timestamp()
            except (OSError, Bad, ValueError):
                pass
            if age > 30 * DAY or (final and age > DAY):
                gone += bool(_remove_tree(d))
        return gone


__all__ = ["Inbox", "Job", "JobProblem", "NotReady", "Bad", "ME", "home", "install", "uninstall", "manifest",
           "read_doc", "send", "take", "claim", "status_doc", "read_tool", "all_types"]
