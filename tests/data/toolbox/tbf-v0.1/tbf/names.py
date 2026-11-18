"""Ids, file names, times and strict JSON (FORMAT.md section 3)."""
from __future__ import annotations

import json
import re
from datetime import datetime

VERSION = "0.1"                       # the version this code reads; until 1.0 no other one (section 3.5)
MAX_JSON = 2**20                      # bytes of a toolbox JSON file

TOOL_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*(\.[a-z0-9]+(-[a-z0-9]+)*)+")
JOB_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,63}")
TYPE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,31}")
ACTION_ID = TYPE_ID
EXT = re.compile(r"\.[a-z0-9]{1,16}")
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?(Z|[+-]([01]\d|2[0-3]):[0-5]\d)")

JOB_FILES = ("job.json", "status.json", "cancel.json")          # the format's own files in a job folder
_WINDOWS = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
_BAD = set('<>:"/\\|?*')


def is_tool_id(s) -> bool:
    return isinstance(s, str) and len(s) <= 80 and TOOL_ID.fullmatch(s) is not None


def is_job_id(s) -> bool:
    return isinstance(s, str) and JOB_ID.fullmatch(s) is not None


def is_dotted_type(s) -> bool:
    """a tool's own type: two or more parts, as a tool id (section 5.1)"""
    return is_tool_id(s)


def is_type_ref(s, builtin: set[str]) -> str | None:
    """what kind of type name ``s`` is: 'builtin', 'own' (dotted), 'ext' – or None when it is none of them"""
    if not isinstance(s, str):
        return None
    if s.startswith("ext:"):
        return "ext" if re.fullmatch(r"[a-z0-9]{0,16}", s[4:]) else None
    if "." in s:
        return "own" if is_dotted_type(s) else None
    return "builtin" if s in builtin else None


def name_problem(name) -> str | None:
    """why ``name`` is not a file name every system and every tool can take (section 3.3); None when it is"""
    if not isinstance(name, str) or not name:
        return "is empty"
    if len(name) > 120:
        return "is longer than 120 characters"
    if any(ord(c) < 32 or ord(c) == 127 for c in name):
        return "holds a control character"
    bad = sorted(_BAD & set(name))
    if bad:
        return f"holds {bad[0]!r}"
    if name[0] in " ." or name[-1] in " .":
        return "starts or ends with a space or a dot"
    if name.split(".")[0].lower() in _WINDOWS:
        return "is a name Windows keeps for itself"
    if name.lower() in JOB_FILES:
        return "is one of the format's own files"
    return None


def extension(name: str) -> str:
    """the lower-case extension with its dot ('.step'), '' when the name has none"""
    i = name.rfind(".")
    return name[i:].lower() if i > 0 else ""


def time_problem(s) -> str | None:
    if not isinstance(s, str) or not TIME.fullmatch(s):
        return "is not a time like 2026-11-18T19:51:00+01:00"
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return "is not a real date and time"
    return None


class JsonError(Exception):
    pass


def _pairs(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise JsonError(f"the key {k!r} is there twice")
        out[k] = v
    return out


def _const(x):
    raise JsonError(f"{x} is not allowed in JSON")


def _control(x, where="") -> str | None:
    if isinstance(x, str):
        return where if any(ord(c) < 32 or ord(c) == 127 for c in x) else None
    if isinstance(x, dict):
        for k, v in x.items():
            hit = _control(k, f"{where}/{k}") or _control(v, f"{where}/{k}")
            if hit:
                return hit
    if isinstance(x, list):
        for i, v in enumerate(x):
            hit = _control(v, f"{where}/{i}")
            if hit:
                return hit
    return None


def load_json(data: bytes) -> dict:
    """a toolbox JSON file as an object, or JsonError: UTF-8 without a byte-order mark, one object, no key twice,
    no NaN or Infinity, no control characters in any text (section 3.4)"""
    if len(data) > MAX_JSON:
        raise JsonError("is larger than 1 MiB")
    if data[:3] == b"\xef\xbb\xbf":
        raise JsonError("starts with a byte-order mark")
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_const)
    except UnicodeDecodeError:
        raise JsonError("is not UTF-8") from None
    except RecursionError:
        raise JsonError("is nested too deep") from None
    except json.JSONDecodeError as e:
        raise JsonError(f"is not JSON ({e.msg}, line {e.lineno})") from None
    if not isinstance(doc, dict):
        raise JsonError("is not a JSON object")
    hit = _control(doc)
    if hit is not None:
        raise JsonError(f"holds a control character (line break, tab …) at {hit or '/'}")
    return doc
