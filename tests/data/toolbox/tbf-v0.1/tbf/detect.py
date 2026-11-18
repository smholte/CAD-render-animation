"""File types: the rules that recognise a file, and which type a file is (FORMAT.md section 5).

``load_types()`` reads the built-in list (types.json); ``detect(path, types)`` names a file's type.
Written to be copied: the same steps in JavaScript give the same answer (section 5.3 says how).
"""
from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

from .names import EXT, TYPE_ID, JsonError, extension, is_dotted_type, load_json

HEAD = 65536                 # bytes of a file a rule may look at
ZIP_JSON_MAX = 2**20         # a JSON file inside a zip a rule may read
MAX_DEPTH = 4                # all / any / not inside each other
MAX_PATTERN = 200
TYPES_FILE = Path(__file__).resolve().parent.parent / "types.json"
_SPACE = b" \t\r\n"


# ---------------------------------------------------------------- the rules themselves
def pattern_problem(p) -> str | None:
    """why a head_matches pattern is not one JavaScript and Python read alike (section 5.2); None when it is"""
    if not isinstance(p, str) or not p:
        return "is empty"
    if len(p) > MAX_PATTERN:
        return f"is longer than {MAX_PATTERN} characters"
    if any(ord(c) < 32 or ord(c) > 126 for c in p):
        return "holds a character outside plain ASCII"
    i, in_class, counted = 0, False, False       # counted: the last thing was a count (* + ? {n,m})
    while i < len(p):
        c = p[i]
        was, counted = counted, False
        if c == "\\":
            nxt = p[i + 1:i + 2]
            if not nxt:
                return "ends with a backslash"
            if nxt.isalnum() and nxt not in "sSdDwW":
                return f"uses \\{nxt} (only \\s \\S \\d \\D \\w \\W and escaped signs are allowed)"
            i += 2
            continue
        if in_class:
            in_class = c != "]"
        elif c == "[":
            in_class = True
            if p[i + 1:i + 2] == "^":
                i += 1
            if p[i + 1:i + 2] == "]":
                return "has an empty [] group"
        elif c in "^$":
            return f"uses {c} (say where the file starts with starts_with instead)"
        elif c == ".":
            return "uses a bare . (it means different things in JavaScript and Python; write a set like [^\\n])"
        elif c == "(" and p[i + 1:i + 2] == "?":
            return "uses a (?…) group"
        elif c == "{":
            m = re.match(r"\{\d+(,\d*)?\}", p[i:])
            if not m:
                return "has a { that is not a count like {2}, {2,} or {2,5}"
            i += m.end() - 1
            counted = True
        elif c in "*+":
            if was:
                return f"has {c} right after another count"
            counted = True
        elif c == "?":
            counted = not was                   # a ? after a count makes it lazy; it is not a count itself
        i += 1
    if in_class:
        return "has a [ that is never closed"
    try:
        re.compile(p, re.ASCII)
    except re.error as e:
        return f"is not a pattern ({e})"
    return None


def rule_problems(rule, where: str, depth: int = 1) -> list[str]:
    """what is wrong with a detect rule (an empty list when nothing is)"""
    if not isinstance(rule, dict) or len(rule) != 1:
        return [f"{where}: a rule is an object with exactly one key"]
    (key, v), = rule.items()
    if key in ("all", "any"):
        if depth >= MAX_DEPTH:
            return [f"{where}: rules are nested deeper than {MAX_DEPTH}"]
        if not isinstance(v, list) or not v:
            return [f"{where}/{key}: needs a list of at least one rule"]
        return [m for i, r in enumerate(v) for m in rule_problems(r, f"{where}/{key}/{i}", depth + 1)]
    if key == "not":
        if depth >= MAX_DEPTH:
            return [f"{where}: rules are nested deeper than {MAX_DEPTH}"]
        return rule_problems(v, f"{where}/not", depth + 1)
    if key == "starts_with":
        ok = isinstance(v, str) and 0 < len(v) <= 64 and all(32 < ord(c) < 127 for c in v)
        return [] if ok else [f"{where}/starts_with: 1 to 64 plain ASCII characters without spaces"]
    if key == "starts_with_hex":
        ok = isinstance(v, str) and re.fullmatch(r"([0-9a-f]{2}){1,64}", v)
        return [] if ok else [f"{where}/starts_with_hex: 1 to 64 bytes as lower-case hex"]
    if key == "head_matches":
        why = pattern_problem(v)
        return [f"{where}/head_matches: the pattern {why}"] if why else []
    if key in ("zip_has", "zip_json"):
        want = {"file"} if key == "zip_has" else {"file", "field", "equals"}
        if not isinstance(v, dict) or set(v) != want or not all(isinstance(x, str) and x for x in v.values()):
            return [f"{where}/{key}: needs exactly {', '.join(sorted(want))} (texts)"]
        f = v["file"]
        if f.startswith("/") or "\\" in f or any(part in ("", ".", "..") for part in f.split("/")):
            return [f"{where}/{key}: {f!r} is not a plain path inside a zip"]
        return []
    return [f"{where}: {key!r} is not a rule this version knows"]


def type_problems(t, where: str, own: bool) -> list[str]:
    """what is wrong with one type of a list (types.json, or the types of a tool's manifest when ``own``)"""
    if not isinstance(t, dict):
        return [f"{where}: a type is an object"]
    out = []
    extra = set(t) - {"id", "name", "extensions", "detect", "by_content"}
    if extra:
        out.append(f"{where}: unknown field(s) {', '.join(sorted(extra))}")
    tid = t.get("id")
    if own:
        if not is_dotted_type(tid):
            out.append(f"{where}/id: a tool's own type is named like a tool, with dots (com.example.widget) – "
                       "short names belong to the built-in list")
    elif not (isinstance(tid, str) and TYPE_ID.fullmatch(tid)):
        out.append(f"{where}/id: a built-in type is 1 to 32 of a–z, 0–9 and -")
    if not (isinstance(t.get("name"), str) and 0 < len(t["name"]) <= 60):
        out.append(f"{where}/name: a name of 1 to 60 characters")
    exts = t.get("extensions")
    if not (isinstance(exts, list) and exts and all(isinstance(e, str) and EXT.fullmatch(e) for e in exts)
            and len(set(exts)) == len(exts)):
        out.append(f"{where}/extensions: at least one extension like \".step\" (lower case, with its dot), none twice")
    if "detect" in t:
        out += rule_problems(t["detect"], f"{where}/detect")
    if "by_content" in t and not isinstance(t["by_content"], bool):
        out.append(f"{where}/by_content: true or false")
    if t.get("by_content") and "detect" not in t:
        out.append(f"{where}: by_content needs a detect rule")
    return out


def load_types(path: Path | str | None = None) -> list[dict]:
    """the built-in types, in the order of the list (raises JsonError / ValueError when the list is broken)"""
    doc = load_json(Path(path or TYPES_FILE).read_bytes())
    problems = [m for i, t in enumerate(doc.get("types") or [{}]) for m in type_problems(t, f"types/{i}", own=False)]
    if problems:
        raise ValueError("; ".join(problems))
    return doc["types"]


# ---------------------------------------------------------------- reading a zip (section 5.2, "A zip is read like this")
ZIP_TAIL = 65557             # an end record and the longest comment
ZIP_DIR_MAX = 64 * 2**20


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def _u64(b, o):
    return struct.unpack_from("<Q", b, o)[0]


def zip_index(fh, size: int) -> dict[str, dict] | None:
    """the list of a zip: name -> entry, or None when the file is not a zip these steps can read"""
    try:
        tail_len = min(size, ZIP_TAIL)
        fh.seek(size - tail_len)
        tail = fh.read(tail_len)
        e = tail.rfind(b"PK\x05\x06", 0, max(len(tail) - 22, -1) + 4)
        if e < 0:
            return None
        pos = size - tail_len + e
        count, cd_size, cd_off, shift = _u16(tail, e + 10), _u32(tail, e + 12), _u32(tail, e + 16), 0
        if count == 0xFFFF or cd_size == 0xFFFFFFFF or cd_off == 0xFFFFFFFF:
            loc = e - 20
            if loc < 0 or tail[loc:loc + 4] != b"PK\x06\x07":
                return None
            fh.seek(_u64(tail, loc + 8))
            r = fh.read(56)
            if len(r) < 56 or r[:4] != b"PK\x06\x06":
                return None
            count, cd_size, cd_off = _u64(r, 32), _u64(r, 40), _u64(r, 48)
        else:
            shift = pos - cd_size - cd_off          # bytes put in front of the zip
            if shift < 0:
                return None
            cd_off += shift
        if cd_off + cd_size > size or cd_size > ZIP_DIR_MAX:
            return None
        fh.seek(cd_off)
        cd = fh.read(cd_size)
        out, p = {}, 0
        for _ in range(count):
            if p + 46 > len(cd) or cd[p:p + 4] != b"PK\x01\x02":
                return None
            flags, name_len, extra_len, comment_len = _u16(cd, p + 8), _u16(cd, p + 28), _u16(cd, p + 30), _u16(cd, p + 32)
            ent = {"flags": flags, "method": _u16(cd, p + 10), "crc": _u32(cd, p + 16), "csize": _u32(cd, p + 20),
                   "usize": _u32(cd, p + 24), "offset": _u32(cd, p + 42) + shift}
            if p + 46 + name_len + extra_len + comment_len > len(cd):
                return None
            raw = cd[p + 46:p + 46 + name_len]
            name = raw.decode("utf-8", "replace") if flags & 0x800 else raw.decode("latin-1")
            x, end = p + 46 + name_len, p + 46 + name_len + extra_len
            while x + 4 <= end:                     # zip64 sizes
                ident, length = _u16(cd, x), _u16(cd, x + 2)
                if ident == 1:
                    q = x + 4
                    if ent["usize"] == 0xFFFFFFFF:
                        ent["usize"] = _u64(cd, q)
                        q += 8
                    if ent["csize"] == 0xFFFFFFFF:
                        ent["csize"] = _u64(cd, q)
                        q += 8
                    if ent["offset"] == 0xFFFFFFFF + shift:
                        ent["offset"] = _u64(cd, q) + shift
                x += 4 + length
            out[name] = ent
            p += 46 + name_len + extra_len + comment_len
        return out
    except (struct.error, OSError, OverflowError, ValueError):
        return None


def zip_read(fh, size: int, ent: dict) -> bytes | None:
    """the bytes of one entry (stored or deflated, not encrypted, CRC checked), or None"""
    try:
        if ent["flags"] & 1 or ent["method"] not in (0, 8):
            return None
        fh.seek(ent["offset"])
        h = fh.read(30)
        if len(h) < 30 or h[:4] != b"PK\x03\x04":
            return None
        start = ent["offset"] + 30 + _u16(h, 26) + _u16(h, 28)
        if start + ent["csize"] > size:
            return None
        fh.seek(start)
        packed = fh.read(ent["csize"])
        if len(packed) != ent["csize"]:
            return None
        if ent["method"] == 0:
            data = packed
        else:
            d = zlib.decompressobj(-15)
            data = d.decompress(packed, ent["usize"] + 1)
            if len(data) > ent["usize"] or not d.eof or d.unused_data or d.unconsumed_tail:
                return None
        return data if len(data) == ent["usize"] and zlib.crc32(data) == ent["crc"] else None
    except (struct.error, OSError, OverflowError, ValueError, zlib.error, MemoryError):
        return None


# ---------------------------------------------------------------- looking at a file
class Sniff:
    """what the rules may see of one file: its first bytes, and when it is a zip, its list of names"""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        with open(self.path, "rb") as fh:
            self.head = fh.read(HEAD)
        self._zip: dict | None | bool = False       # False = not looked yet, None = not a zip

    @property
    def text(self) -> str:
        """the head as text for head_matches: every byte of 0x80 and up reads as '?' (section 5.2)"""
        return "".join(chr(b) if b < 0x80 else "?" for b in self.head)

    def starts_with(self, want: bytes, skip: bool) -> bool:
        head = self.head
        if skip:
            if head[:3] == b"\xef\xbb\xbf":
                head = head[3:]
            head = head.lstrip(_SPACE)
        return head.startswith(want)

    def names(self) -> dict | None:
        if self._zip is False:
            try:
                with open(self.path, "rb") as fh:
                    self._zip = zip_index(fh, self.path.stat().st_size)
            except OSError:
                self._zip = None
        return self._zip

    def zip_json(self, name: str):
        entries = self.names()
        if not entries or name not in entries or entries[name]["usize"] > ZIP_JSON_MAX:
            return None
        try:
            with open(self.path, "rb") as fh:
                data = zip_read(fh, self.path.stat().st_size, entries[name])
            return None if data is None else load_json(data)
        except (OSError, JsonError):
            return None


def matches(rule: dict, f: Sniff) -> bool:
    (key, v), = rule.items()
    if key == "all":
        return all(matches(r, f) for r in v)
    if key == "any":
        return any(matches(r, f) for r in v)
    if key == "not":
        return not matches(v, f)
    if key == "starts_with":
        return f.starts_with(v.encode("ascii"), skip=True)
    if key == "starts_with_hex":
        return f.starts_with(bytes.fromhex(v), skip=False)
    if key == "head_matches":
        return re.search(v, f.text, re.ASCII) is not None
    if key == "zip_has":
        return v["file"] in (f.names() or {})
    if key == "zip_json":
        doc = f.zip_json(v["file"])
        return doc is not None and doc.get(v["field"]) == v["equals"]
    return False


def detect(path: Path | str, types: list[dict], name: str | None = None) -> tuple[str, str | None]:
    """(type id, note) of a file – section 5.3. ``types``: the built-in list followed by the tools' own types.
    ``name``: the name to take the extension from, when it is not the path's. The note says when the content
    and the extension do not agree."""
    f = Sniff(path)
    ext = extension(name if name is not None else f.path.name)
    for t in types:                                             # 1. what the content says
        if t.get("by_content") and matches(t["detect"], f):
            note = None if ext in t["extensions"] else (
                f"its content is {t['name']} ({t['id']}) but its name ends in {ext or 'no extension'}")
            return t["id"], note
    failed = None
    for t in types:                                             # 2. what the extension says
        if ext in t["extensions"]:
            if "detect" not in t or matches(t["detect"], f):
                return t["id"], None
            failed = failed or t
    note = f"its name ends in {ext} but its content is not {failed['name']}" if failed else None
    return "ext:" + ext[1:], note                               # 3. nobody knows it
