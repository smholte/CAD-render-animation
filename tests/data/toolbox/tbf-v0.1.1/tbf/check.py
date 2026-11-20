"""The checker: a list of problems in a Toolbox folder, a tool's manifest, a job or the type list (FORMAT.md
section 10).

``check(path) -> Report``. ERROR = a reader must refuse it (or that part of it); WARNING = it can be read, but
something is probably wrong.
"""
from __future__ import annotations

import errno
import json
import os
import re
import stat
from functools import lru_cache
from pathlib import Path

import jsonschema

from .detect import detect, load_types, type_problems
from .names import (JOB_FILES, TIME_FIELDS, VERSION, JsonError, is_job_id, is_tool_id, is_type_ref, load_json,
                    name_problem, time_problem)

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"
FOLDER_FILE = "toolbox-folder.json"
FINAL = ("done", "failed", "cancelled")
_ABSOLUTE = re.compile(r"([A-Za-z]:[\\/]|/)")
JUNCTION = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)    # a Windows junction, told by os.lstat


class Report:
    def __init__(self, name: str):
        self.name = name
        self.items: list[tuple[str, str]] = []

    def error(self, text: str):
        self.items.append(("ERROR", text))

    def warn(self, text: str):
        self.items.append(("WARNING", text))

    @property
    def errors(self):
        return [t for lv, t in self.items if lv == "ERROR"]

    @property
    def warnings(self):
        return [t for lv, t in self.items if lv == "WARNING"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        head = f"{self.name}: " + ("OK" if self.ok else f"{len(self.errors)} error(s)") + (
            f", {len(self.warnings)} warning(s)" if self.warnings else "")
        return "\n".join([head] + [f"  {lv}: {t}" for lv, t in self.items])


# ---------------------------------------------------------------- reading one JSON file
@lru_cache(maxsize=None)
def _schema(name: str):
    return jsonschema.Draft202012Validator(json.loads((SCHEMAS / f"{name}.schema.json").read_text("utf-8")))


def read_doc(path: Path, schema: str, rep: Report, where: str, strict: bool = True) -> dict | None:
    """the JSON file as an object when it is whole and of this version; None (and errors in ``rep``) otherwise.
    ``strict=False`` is for readers: a key written twice is not refused (the last counts, as in JavaScript)."""
    try:
        data = path.read_bytes()
    except OSError as e:
        rep.error(f"{where}: cannot be read ({e.strerror or e})")
        return None
    return parse_doc(data, schema, rep, where, strict)


def parse_doc(data: bytes, schema: str, rep: Report, where: str, strict: bool = True) -> dict | None:
    """read_doc for bytes already read"""
    try:
        doc = load_json(data, "refuse" if strict else "last")
    except JsonError as e:
        rep.error(f"{where}: {e}")
        return None
    v = doc.get("version")
    if isinstance(v, str) and re.fullmatch(r"[0-9]+\.[0-9]+", v) and v != VERSION:
        rep.error(f"{where}: is version {v}; this checker reads {VERSION} only (until 1.0 a reader takes its own "
                  "version and no other)")
        return None
    errors = sorted(_schema(schema).iter_errors(doc), key=lambda e: list(map(str, e.absolute_path)))
    for e in errors[:8]:
        at = "/".join(map(str, e.absolute_path))
        rep.error(f"{where}{': ' + at if at else ''}: {e.message}"[:400])
    if len(errors) > 8:
        rep.error(f"{where}: … and {len(errors) - 8} more")
    if errors:
        return None
    if doc["version"] != VERSION:               # the schema's \d also takes digits of other scripts
        rep.error(f"{where}: version {doc['version']!r} is not a version like {VERSION}")
        return None
    bad_time = False
    for k in TIME_FIELDS:                       # the schemas only say what a time looks like (3.4)
        why = time_problem(doc[k]) if k in doc else None
        if why:
            rep.error(f"{where}: {k} {why}")
            bad_time = True
    return None if bad_time else doc


def look(p: Path) -> tuple[str, int | str | None]:
    """what is at ``p``, without following a link: ("file", size), ("missing", None), ("link", None),
    ("not-file", None), ("bad-name", why) – a name this system cannot hold – or ("unreadable", why)"""
    try:
        st = os.lstat(p)
    except (FileNotFoundError, NotADirectoryError):
        return "missing", None
    except ValueError as e:                     # a name the system cannot take at all
        return "bad-name", str(e)
    except OSError as e:
        if e.errno in (errno.ENAMETOOLONG, errno.EINVAL, errno.EILSEQ):
            return "bad-name", e.strerror or str(e)
        return "unreadable", e.strerror or str(e)
    if stat.S_ISLNK(st.st_mode) or getattr(st, "st_reparse_tag", 0) == JUNCTION:
        return "link", None
    if not stat.S_ISREG(st.st_mode):
        return "not-file", None
    return "file", st.st_size


# ---------------------------------------------------------------- types.json
def check_types_file(path: Path, rep: Report) -> list[dict]:
    doc = read_doc(path, "types-0", rep, path.name)
    if doc is None:
        return []
    seen, exts, good = set(), {}, []
    for i, t in enumerate(doc["types"]):
        problems = type_problems(t, f"{path.name}: types/{i}", own=False)
        for m in problems:
            rep.error(m)
        if problems:
            continue
        if t["id"] in seen:
            rep.error(f"{path.name}: the type {t['id']} is there twice")
            continue
        seen.add(t["id"])
        for e in t["extensions"]:
            if e in exts and not (t.get("detect") and exts[e].get("detect")):
                rep.error(f"{path.name}: {e} belongs to both {exts[e]['id']} and {t['id']}, and they cannot be told "
                          "apart without a detect rule on each")
            exts.setdefault(e, t)
        good.append(t)
    return good


# ---------------------------------------------------------------- toolbox.json
def check_manifest(path: Path, rep: Report, builtin: list[dict], folder: str | None = None,
                   where: str | None = None, strict: bool = True) -> dict | None:
    where = where or path.name
    doc = read_doc(path, "tool-0", rep, where, strict)
    if doc is None:
        return None
    ok = True

    def bad(text):
        nonlocal ok
        ok = False
        rep.error(f"{where}: {text}")

    if folder is not None and doc["id"] != folder:
        bad(f"its id is {doc['id']} but its folder is named {folder}")
    names = {t["id"] for t in builtin}
    own = set()
    for i, t in enumerate(doc.get("types", [])):
        problems = type_problems(t, f"types/{i}", own=True)
        for m in problems:
            bad(m)
        if not problems:
            if t["id"] in own:
                bad(f"the type {t['id']} is there twice")
            own.add(t["id"])
    ids = [a["id"] for a in doc["actions"]]
    for a in sorted({x for x in ids if ids.count(x) > 1}):
        bad(f"the action {a} is there twice")

    def refs(lst, what):
        for t in lst:
            kind = is_type_ref(t, names)
            if kind is None:
                bad(f"{what}: {t!r} is not a type – not in the built-in list (types.json), not a tool's own type "
                    "(with dots) and not ext:<extension>")
            elif kind == "own" and t not in own:
                rep.warn(f"{where}: {what}: the type {t} is not defined in this manifest (another tool's?)")

    for a in doc["actions"]:
        refs(a["accepts"], f"action {a['id']} accepts")
        refs(a.get("returns", []), f"action {a['id']} returns")
    refs(doc.get("sends", []), "sends")
    if doc["kind"] == "web":
        if "start" in doc:
            bad("a web tool has no start (a page is not a program)")
    elif "url" in doc:
        bad("a native tool has no url (its web page goes in homepage)")
    if "start" in doc and not _ABSOLUTE.match(doc["start"]["program"]):
        bad("start.program must be the full path of the program on this PC")
    if "icon" in doc:
        why = name_problem(doc["icon"])
        if why:
            bad(f"icon: the file name {why}")
        elif not (path.parent / doc["icon"]).is_file():
            rep.warn(f"{where}: the icon {doc['icon']} is not next to the manifest")
    if doc["actions"] and "inbox" not in doc.get("handover", []):
        rep.warn(f"{where}: it has actions but no \"inbox\" in handover, so nothing can be sent to it yet")
    return doc if ok else None


# ---------------------------------------------------------------- a job folder
def check_job(folder: Path, rep: Report, types: list[dict], tool: dict | None = None,
              tools: dict[str, dict | None] | None = None, where: str | None = None):
    """``tool``: the manifest of the tool whose inbox the job is in; ``tools``: every manifest of the Toolbox
    folder by id (None for a broken one). Without them only the job itself is checked."""
    where = where or folder.name
    if not (folder / "job.json").is_file():
        rep.warn(f"{where}: no job.json – not ready yet, or left behind")
        return
    job = read_doc(folder / "job.json", "job-0", rep, f"{where}/job.json")
    if job is None:
        return
    at = f"{where}/job.json"
    if job["job"] != folder.name:
        rep.error(f"{at}: its job is {job['job']} but its folder is named {folder.name}")
    action = None
    if tool is not None:
        if job["to"] != tool["id"]:
            rep.error(f"{at}: it is for {job['to']} but lies in the inbox of {tool['id']}")
        action = next((a for a in tool["actions"] if a["id"] == job["action"]), None)
        if action is None:
            rep.error(f"{at}: {tool['id']} has no action {job['action']}")
    if job["from"] == job["to"]:
        rep.error(f"{at}: from and to are the same tool")
    if "reply_to" in job and job["reply_to"]["tool"] != job["from"]:
        rep.error(f"{at}: a reply comes from the tool that did the job: reply_to.tool is {job['reply_to']['tool']}, "
                  f"from is {job['from']}")
    if "reply_to" in job and "return" in job:
        rep.error(f"{at}: a reply job has no return")
    if tools is not None:
        sender = tools.get(job["from"])
        if job["from"] not in tools:
            rep.warn(f"{at}: the sender {job['from']} has no manifest in this Toolbox folder")
        elif sender is not None and "return" in job:
            back = next((a for a in sender["actions"] if a["id"] == job["return"]), None)
            if back is None:
                rep.error(f"{at}: return names the action {job['return']}, which the sender {job['from']} does not "
                          "have")
            elif action and action.get("returns") and not set(action["returns"]) & set(back["accepts"]):
                rep.warn(f"{at}: {job['action']} returns {', '.join(action['returns'])}, but the sender's "
                         f"{job['return']} accepts none of them")
    seen = set()
    for f in job["files"]:
        name = f["name"]
        why = name_problem(name)
        if why:
            rep.error(f"{at}: the file name {name!r} {why}")
            continue
        if name.lower() in seen:
            rep.error(f"{at}: the file {name} is listed twice (capitals do not count)")
            continue
        seen.add(name.lower())
        p = folder / name
        kind, size = look(p)
        if kind == "bad-name":
            rep.error(f"{at}: the file name {name!r} cannot be used on this system ({size})")
            continue
        if kind == "unreadable":
            rep.error(f"{where}: the file {name} cannot be read ({size})")
            continue
        if kind != "file":
            rep.error(f"{where}: the file {name} is missing" if kind == "missing" else
                      f"{where}: {name} is not a plain file (a link or a folder)")
            continue
        if size != f["size"]:
            rep.error(f"{where}/{name}: is {size} bytes, job.json says {f['size']} – not written to the end?")
            continue
        try:
            found, note = detect(p, types)
        except OSError as e:
            rep.error(f"{where}: the file {name} cannot be read ({e.strerror or e})")
            continue
        if found != f["type"]:
            rep.error(f"{where}/{name}: job.json calls it {f['type']}, but it is {found}"
                      + (f" ({note})" if note else ""))
        elif note:
            rep.warn(f"{where}/{name}: {note}")
        if action is not None and f["type"] not in action["accepts"]:
            rep.error(f"{at}: the action {action['id']} does not accept {f['type']} ({name})")
    for doc_name, schema in (("status.json", "status-0"), ("cancel.json", "cancel-0")):
        if (folder / doc_name).is_file():
            doc = read_doc(folder / doc_name, schema, rep, f"{where}/{doc_name}")
            if doc is None:
                continue
            if doc["job"] != job["job"]:
                rep.error(f"{where}/{doc_name}: is about the job {doc['job']}, not this one")
            if doc_name == "status.json":
                if "code" in doc and doc["state"] != "failed":
                    rep.warn(f"{where}/status.json: a code only says why a job failed; the state is {doc['state']}")
                if "reply" in doc and doc["state"] != "done":
                    rep.warn(f"{where}/status.json: a reply belongs to a job that is done; the state is {doc['state']}")
                if "reply" in doc and "return" not in job:
                    rep.warn(f"{where}/status.json: names a reply, but the job asked for none (no return)")
    for entry in sorted(folder.iterdir(), key=lambda e: e.name):
        if entry.name.lower() in seen or entry.name in JOB_FILES:
            continue
        rep.warn(f"{where}: {entry.name} is not named by job.json")


# ---------------------------------------------------------------- a whole Toolbox folder
def check_folder(root: Path, rep: Report):
    if read_doc(root / FOLDER_FILE, "folder-0", rep, FOLDER_FILE) is None:
        return
    builtin = load_types()
    tools_dir = root / "tools"
    for entry in sorted(root.iterdir(), key=lambda e: e.name):
        if entry.name not in (FOLDER_FILE, "tools"):
            rep.warn(f"{entry.name}: the format does not know this entry of the Toolbox folder")
    if not tools_dir.is_dir():
        return
    tools: dict[str, dict | None] = {}
    folders = []
    for d in sorted(tools_dir.iterdir(), key=lambda e: e.name):
        at = f"tools/{d.name}"
        if not d.is_dir():
            rep.warn(f"{at}: only tool folders belong in tools/")
            continue
        if not is_tool_id(d.name):
            rep.error(f"{at}: not a tool id (lower case, at least two parts with dots, like nl.fresing.render)")
            continue
        if not (d / "toolbox.json").is_file():
            rep.error(f"{at}: no toolbox.json")
            tools[d.name] = None
            continue
        tools[d.name] = check_manifest(d / "toolbox.json", rep, builtin, folder=d.name, where=f"{at}/toolbox.json")
        folders.append(d)
    own = {}
    for tid in sorted(tools):
        for t in (tools[tid] or {}).get("types", []):
            if t["id"] in own and own[t["id"]] != t:
                rep.error(f"tools/{tid}/toolbox.json: the type {t['id']} is defined differently by another tool")
            own.setdefault(t["id"], t)
    types = builtin + [own[k] for k in sorted(own)]
    for d in folders:
        at, tool = f"tools/{d.name}", tools[d.name]
        icon = (tool or {}).get("icon")
        for entry in sorted(d.iterdir(), key=lambda e: e.name):
            if entry.name not in ("toolbox.json", "alive.json", "inbox", icon):
                rep.warn(f"{at}/{entry.name}: the format does not know this entry of a tool's folder")
        if (d / "alive.json").is_file():
            read_doc(d / "alive.json", "alive-0", rep, f"{at}/alive.json")
        inbox = d / "inbox"
        if not inbox.is_dir():
            continue
        for j in sorted(inbox.iterdir(), key=lambda e: e.name):
            jat = f"{at}/inbox/{j.name}"
            if not j.is_dir():
                rep.warn(f"{jat}: only job folders belong in an inbox")
            elif not is_job_id(j.name):
                rep.error(f"{jat}: not a job id (8 to 64 of a–z, 0–9 and -)")
            elif tool is None:
                rep.warn(f"{jat}: not checked – the tool's manifest is broken")
            else:
                check_job(j, rep, types, tool=tool, tools=tools, where=jat)


# ---------------------------------------------------------------- anything
def check(path: Path | str) -> Report:
    """Check a Toolbox folder (holds toolbox-folder.json), a job folder (holds job.json), a toolbox.json or the
    type list (types.json)."""
    p = Path(path)
    rep = Report(str(path))
    try:
        if p.is_dir() and (p / FOLDER_FILE).is_file():
            check_folder(p, rep)
        elif p.is_dir() and (p / "job.json").is_file():
            check_job(p, rep, load_types())
        elif p.is_file() and p.name == "toolbox.json":
            check_manifest(p, rep, load_types())
        elif p.is_file() and p.name == "types.json":
            check_types_file(p, rep)
        elif not p.exists():
            rep.error("there is no such file or folder")
        else:
            rep.error("not a Toolbox folder (no toolbox-folder.json), not a job folder (no job.json), not a "
                      "toolbox.json and not types.json – use --type to ask which file type a file is")
    except OSError as e:                      # a folder that changes or cannot be read while it is checked
        rep.error(f"cannot be read ({e.strerror or e})")
    return rep
