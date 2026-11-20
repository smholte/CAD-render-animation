"""Reference code for a native tool: find the Toolbox folder, send a job, read the inbox, answer (FORMAT.md
sections 2, 6 and 7). Plain Python, no Blender. A tool may copy this file together with names.py and detect.py.

    root = toolbox_home(); ensure_folder(root); write_manifest(root, MY_MANIFEST)
    for folder in pending(root, MY_ID):                       # every 2 seconds
        try:
            job, files = take(root, MY_MANIFEST, folder)      # checked: names, sizes, types by content
        except JobProblem as p:
            write_status(root, MY_ID, folder.name, "failed", code=p.code, text=p.text)
            continue
        if not claim(root, MY_ID, job["job"], "working", fraction=0.0, text="Starting"):
            continue                                          # another copy of this tool took it
        ...                                                   # the action; write_status() as it goes
        send_reply(root, MY_MANIFEST, job, [result_path])     # writes the reply job, then the status "done"
    for folder in unfinished(root, MY_ID): ...                # once, at start: jobs an earlier run left (6.3)
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path

from .check import FINAL, FOLDER_FILE, JUNCTION, Report, check_manifest, look, parse_doc, read_doc
from .detect import detect, load_types
from .names import VERSION, is_job_id, is_tool_id, name_problem

DAY = 24 * 3600
ALIVE_FRESH = 30          # seconds: an alive.json older than this means "not watching"
MAX_SIZE = 2**53 - 1      # bytes: no file is larger; JavaScript cannot count further


class JobProblem(Exception):
    """a job this tool must not do; ``code`` and ``text`` go into status.json"""

    def __init__(self, code: str, text: str):
        super().__init__(text)
        self.code, self.text = code, text[:200]


# ---------------------------------------------------------------- the folder
def toolbox_home() -> Path:
    env = os.environ.get("TOOLBOX_HOME")
    return Path(env) if env else Path.home() / "Toolbox"


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_job_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


STALLED = 5 * 60          # seconds a "working" status is believed after its last update (6.4)


def _bytes(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_json(path: Path, doc: dict, tries: int = 5):
    """Whole or not at all: written beside the file, then moved over it. Windows refuses the move while another
    program has the file open, so it is tried a few times; after that the OSError is the caller's to catch, and the
    write is done again at its next look (FORMAT.md section 2)."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{secrets.token_hex(4)}.tmp")   # its own: copies write at once
    tmp.write_bytes(_bytes(doc))
    for n in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if n == tries - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(0.05)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise


def is_link(p: Path) -> bool:
    """a link, or on Windows a junction: never read as a job, never followed when cleaning up. Python 3.11 (the
    one in Blender) has no os.path.isjunction; the reparse tag of os.lstat tells it there."""
    if p.is_symlink() or getattr(os.path, "isjunction", lambda _p: False)(p):
        return True
    try:
        return getattr(os.lstat(p), "st_reparse_tag", 0) == JUNCTION
    except (OSError, ValueError):
        return False


def ensure_folder(root: Path):
    (root / "tools").mkdir(parents=True, exist_ok=True)
    if not (root / FOLDER_FILE).is_file():
        write_json(root / FOLDER_FILE, {"format": "toolbox-folder", "version": VERSION})


def write_manifest(root: Path, manifest: dict):
    d = root / "tools" / manifest["id"]
    (d / "inbox").mkdir(parents=True, exist_ok=True)
    write_json(d / "toolbox.json", manifest)


def read_tool(root: Path, tool_id: str) -> dict | None:
    """another tool's manifest, or None when it is missing, broken or of another version"""
    path = root / "tools" / tool_id / "toolbox.json"
    if not is_tool_id(tool_id) or not path.is_file():
        return None
    return check_manifest(path, Report(tool_id), load_types(), folder=tool_id, strict=False)


def all_types(root: Path) -> list[dict]:
    """the built-in types followed by every tool's own, as section 5.3 orders them"""
    own: dict[str, dict] = {}
    clash = set()
    tools = root / "tools"
    for d in sorted(tools.iterdir()) if tools.is_dir() else []:
        for t in (read_tool(root, d.name) or {}).get("types", []):
            if t["id"] in own and own[t["id"]] != t:
                clash.add(t["id"])
            own.setdefault(t["id"], t)
    return load_types() + [own[k] for k in sorted(own) if k not in clash]


def is_alive(root: Path, tool_id: str) -> bool:
    doc = read_doc(root / "tools" / tool_id / "alive.json", "alive-0", Report(""), "alive.json", strict=False) \
        if (root / "tools" / tool_id / "alive.json").is_file() else None
    try:
        seen = datetime.fromisoformat(doc["seen"].replace("Z", "+00:00"))
        return abs((datetime.now().astimezone() - seen).total_seconds()) <= ALIVE_FRESH
    except (TypeError, ValueError, KeyError):
        return False


def write_alive(root: Path, me: str, app_version: str | None = None):
    doc = {"format": "toolbox-alive", "version": VERSION, "seen": now()}
    if app_version:
        doc["app_version"] = app_version
    write_json(root / "tools" / me / "alive.json", doc)


def remove_alive(root: Path, me: str):
    (root / "tools" / me / "alive.json").unlink(missing_ok=True)


# ---------------------------------------------------------------- sending
def send(root: Path, sender: str, to: str, action: str, files: list[Path], ret: str | None = None,
         title: str | None = None, options: dict | None = None, reply_to: dict | None = None) -> str:
    """Write a job into ``to``'s inbox (section 6.2) and return its id. Raises ValueError when the receiver does
    not take it – nothing is written then."""
    tool = read_tool(root, to)
    if tool is None:
        raise ValueError(f"{to} has no readable manifest in the Toolbox folder")
    act = next((a for a in tool["actions"] if a["id"] == action), None)
    if act is None:
        raise ValueError(f"{to} has no action {action}")
    types = all_types(root)
    listed, seen = [], set()
    for f in files:
        why = name_problem(f.name) or ("is there twice (capitals do not count)" if f.name.lower() in seen else None)
        if why:
            raise ValueError(f"the file name {f.name!r} {why}")
        seen.add(f.name.lower())
        kind, _ = detect(f, types)
        if kind not in act["accepts"]:
            raise ValueError(f"{to} does not accept {kind} for {action} ({f.name})")
        listed.append({"name": f.name, "type": kind, "size": f.stat().st_size})
    job = new_job_id()
    folder = root / "tools" / to / "inbox" / job
    folder.mkdir(parents=True)
    for f in files:
        shutil.copyfile(f, folder / f.name)
    doc = {"format": "toolbox-job", "version": VERSION, "job": job, "created": now(), "from": sender, "to": to,
           "action": action, "files": listed}
    title = title[:120] if title else None             # at most 120 characters (6.1), as JavaScript shortens it
    for key, value in (("return", ret), ("reply_to", reply_to), ("title", title), ("options", options)):
        if value is not None:
            doc[key] = value
    write_json(folder / "job.json", doc)            # last: only now the job exists for the receiver
    return job


def read_status(root: Path, to: str, job: str) -> dict | None:
    """the status of a job this tool sent; None when there is none yet or the job is gone"""
    path = root / "tools" / to / "inbox" / job / "status.json"
    return read_doc(path, "status-0", Report(""), "status.json", strict=False) if path.is_file() else None


def cancel(root: Path, to: str, job: str):
    folder = root / "tools" / to / "inbox" / job
    if folder.is_dir():
        write_json(folder / "cancel.json", {"format": "toolbox-cancel", "version": VERSION, "job": job, "asked": now()})


# ---------------------------------------------------------------- receiving
def pending(root: Path, me: str) -> list[Path]:
    """the job folders of my inbox that have a job.json and no status.json yet, oldest first"""
    inbox = root / "tools" / me / "inbox"
    if not inbox.is_dir():
        return []
    found = [d for d in inbox.iterdir() if d.is_dir() and not is_link(d) and is_job_id(d.name)
             and (d / "job.json").is_file() and not (d / "status.json").exists()]
    return sorted(found, key=lambda d: d.name)


def unfinished(root: Path, me: str) -> list[tuple[Path, dict]]:
    """Jobs an earlier run left: those of my inbox whose status is waiting or working, as (folder, status). A tool
    looks once, at its start: waiting – ask again or start; working – end it as failed, or start it again (6.3)."""
    inbox = root / "tools" / me / "inbox"
    out = []
    for d in sorted(inbox.iterdir()) if inbox.is_dir() else []:
        if d.is_dir() and not is_link(d) and is_job_id(d.name) and (d / "status.json").is_file():
            st = read_doc(d / "status.json", "status-0", Report(""), "", strict=False)
            if st is not None and st["state"] not in FINAL:
                out.append((d, st))
    return out


def claim(root: Path, me: str, job: str, state: str = "waiting", **more) -> bool:
    """Take a job: create its status.json only if it is not there yet. False when another copy of this tool was
    first (6.3). ``more``: fraction, text, code as for write_status."""
    doc = {"format": "toolbox-status", "version": VERSION, "job": job, "state": state, "updated": now()}
    doc.update({k: (v[:200] if k == "text" else v) for k, v in more.items() if v is not None})
    try:
        with open(root / "tools" / me / "inbox" / job / "status.json", "xb") as fh:
            fh.write(_bytes(doc))
        return True
    except FileExistsError:
        return False


def is_stalled(status: dict | None, at: datetime | None = None) -> bool:
    """True when a working status has not been updated for 5 minutes: only then a sender may say that nothing has
    been heard (6.4). A busy tool cannot write, so a fresh "working" is believed whatever alive.json says."""
    if not status or status.get("state") != "working":
        return False
    try:
        seen = datetime.fromisoformat(status["updated"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return True
    return ((at or datetime.now().astimezone()) - seen).total_seconds() > STALLED


def take(root: Path, manifest: dict, folder: Path) -> tuple[dict, list[tuple[str, str, Path]]]:
    """Check a job of my inbox as section 6.3 says. Returns the job and its files as (name, type, path).
    Raises JobProblem; raises FileNotFoundError("…not complete…") when a file is still being written or cannot be
    read right now (another program holds it): try again at the next look (section 2)."""
    try:
        data = (folder / "job.json").read_bytes()
    except OSError as e:
        raise FileNotFoundError(f"job.json cannot be read right now ({e.strerror or e})") from None
    rep = Report("")
    job = parse_doc(data, "job-0", rep, "job.json", strict=False)
    if job is None:
        raise JobProblem("bad-job", rep.errors[0] if rep.errors else "job.json cannot be read")
    if job["job"] != folder.name or job["to"] != manifest["id"] or job["from"] == job["to"]:
        raise JobProblem("bad-job", "the job is not for this tool, or its id is not its folder's name")
    action = next((a for a in manifest["actions"] if a["id"] == job["action"]), None)
    if action is None:
        raise JobProblem("unknown-action", f"{manifest['name']} has no action {job['action']}")
    types, out, seen = all_types(root), [], set()
    for f in job["files"]:
        why = name_problem(f["name"])
        if why or f["name"].lower() in seen:
            raise JobProblem("bad-job", f"the file name {f['name']!r} {why or 'is listed twice'}")
        seen.add(f["name"].lower())
        if f["size"] > MAX_SIZE:
            raise JobProblem("bad-job", f"{f['name']}: no file has {f['size']} bytes")
        p = folder / f["name"]
        kind, size = look(p)
        if kind == "bad-name":
            raise JobProblem("bad-job", f"the file name {f['name']!r} cannot be used on this system")
        if kind in ("link", "not-file"):
            raise JobProblem("bad-job", f"{f['name']} is not a plain file")
        if kind == "unreadable":
            raise FileNotFoundError(f"{f['name']} cannot be read right now ({size})")
        if kind == "missing" or size < f["size"]:
            raise FileNotFoundError(f"{f['name']} is not complete yet")
        if size != f["size"]:
            raise JobProblem("bad-job", f"{f['name']} is larger than job.json says")
        try:
            kind, _ = detect(p, types)
        except OSError as e:
            raise FileNotFoundError(f"{f['name']} cannot be read right now ({e.strerror or e})") from None
        if kind != f["type"]:
            raise JobProblem("wrong-type", f"{f['name']} is {kind}, not {f['type']}")
        if kind not in action["accepts"]:
            raise JobProblem("wrong-type", f"{action['label']} does not accept {kind} ({f['name']})")
        out.append((f["name"], kind, p))
    return job, out


def write_status(root: Path, me: str, job: str, state: str, fraction: float | None = None, text: str | None = None,
                 code: str | None = None, reply: str | None = None):
    doc = {"format": "toolbox-status", "version": VERSION, "job": job, "state": state, "updated": now()}
    for key, value in (("fraction", fraction), ("text", text and text[:200]), ("code", code), ("reply", reply)):
        if value is not None:
            doc[key] = value
    write_json(root / "tools" / me / "inbox" / job / "status.json", doc)


def wants_cancel(root: Path, me: str, job: str) -> bool:
    return (root / "tools" / me / "inbox" / job / "cancel.json").is_file()


def send_reply(root: Path, manifest: dict, job: dict, files: list[Path], text: str | None = None) -> str | None:
    """Section 7.2: send the result back as a job when the first job asked for it and the sender can take it, then
    write the first job's status "done". Returns the reply job's id, or None when the result stays here."""
    me, reply = manifest["id"], None
    if "return" in job and files and (root / "tools" / job["from"]).is_dir():
        try:
            reply = send(root, me, job["from"], job["return"], files, title=job.get("title"),
                         reply_to={"tool": me, "job": job["job"]})
        except ValueError as e:
            text = f"Done, but the result could not be sent back: {e}"
    write_status(root, me, job["job"], "done", text=text, reply=reply)
    return reply


def clean(root: Path, me: str, at: float | None = None):
    """Section 7.4 for my own inbox: finished jobs after a day, anything after 30 days."""
    at = time.time() if at is None else at
    inbox = root / "tools" / me / "inbox"
    for d in list(inbox.iterdir()) if inbox.is_dir() else []:
        if not d.is_dir() or is_link(d) or not is_job_id(d.name):   # only real job folders; a link is never followed
            continue
        age = at - d.stat().st_mtime
        status = read_doc(d / "status.json", "status-0", Report(""), "", strict=False) \
            if (d / "status.json").is_file() else None
        final = status is not None and status["state"] in FINAL
        if final:
            try:
                age = (datetime.fromtimestamp(at).astimezone()
                       - datetime.fromisoformat(status["updated"].replace("Z", "+00:00"))) / timedelta(seconds=1)
            except ValueError:
                pass
        if age > 30 * DAY or (final and age > DAY):
            shutil.rmtree(d, ignore_errors=True)


def remove_job(root: Path, tool: str, job: str):
    """delete a job folder (a reply I took in; a job I sent whose final status I have read)"""
    folder = root / "tools" / tool / "inbox" / job
    if is_tool_id(tool) and is_job_id(job) and not is_link(folder):
        shutil.rmtree(folder, ignore_errors=True)       # what Windows will not let go now goes at the next look
