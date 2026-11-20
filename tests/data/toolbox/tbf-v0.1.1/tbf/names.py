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
TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?(Z|[+-]([01]\d|2[0-3]):[0-5]\d)", re.ASCII)
TIME_FIELDS = ("created", "updated", "asked", "seen")             # the times of the format's files

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


def _number(digits: str):
    """a whole number as JavaScript reads it when Python cannot hold it as text: more than 4000 digits become a
    float (Infinity), as JSON.parse gives (Python 3.11 refuses to read ints of more than 4300 digits)"""
    return int(digits) if len(digits) <= 4000 else float(digits)


def _text_problem(s: str) -> str | None:
    if any(ord(c) < 32 or ord(c) == 127 for c in s):
        return "holds a control character (line break, tab …)"
    if any(0xD800 <= ord(c) <= 0xDFFF for c in s):           # json.loads joins escaped pairs; what is left is alone
        return "is not UTF-8 text (an unpaired \\ud800–\\udfff escape)"
    return None


def _text_at(doc) -> tuple[str, str] | None:
    """(where, why) of the first key or text that breaks section 3.4, walking without recursion"""
    todo = [("", doc)]
    while todo:
        where, x = todo.pop()
        if isinstance(x, str):
            why = _text_problem(x)
            if why:
                return where, why
        elif isinstance(x, dict):
            for k, v in reversed(list(x.items())):
                why = _text_problem(k)
                if why:
                    return f"{where}/{k}", why
                todo.append((f"{where}/{k}", v))
        elif isinstance(x, list):
            todo.extend((f"{where}/{i}", v) for i, v in reversed(list(enumerate(x))))
    return None


def load_json(data: bytes, keys_twice: str = "refuse") -> dict:
    """a toolbox JSON file as an object, or JsonError: UTF-8 without a byte-order mark, one object, no key twice,
    no NaN or Infinity, no control characters and nothing that is not UTF-8 in any text (section 3.4).
    ``keys_twice="last"``: a key written twice is not refused but the last one counts, as in JavaScript – for
    readers, which need not notice it (3.4); the checker refuses it."""
    if len(data) > MAX_JSON:
        raise JsonError("is larger than 1 MiB")
    if data[:3] == b"\xef\xbb\xbf":
        raise JsonError("starts with a byte-order mark")
    try:
        doc = json.loads(data.decode("utf-8"), object_pairs_hook=_pairs if keys_twice == "refuse" else None,
                         parse_constant=_const, parse_int=_number)
    except UnicodeDecodeError:
        raise JsonError("is not UTF-8") from None
    except RecursionError:
        raise JsonError("is nested too deep") from None
    except json.JSONDecodeError as e:
        raise JsonError(f"is not JSON ({e.msg}, line {e.lineno})") from None
    if not isinstance(doc, dict):
        raise JsonError("is not a JSON object")
    hit = _text_at(doc)
    if hit is not None:
        raise JsonError(f"{hit[1]} at {hit[0] or '/'}")
    return doc
