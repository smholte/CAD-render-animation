"""Versions of the test tour's sets and stops (task 0199): what is new and what changed, so What's new after an update
can offer the tour of only the new and changed test models.

Every ``@tour_set(...)`` in ``fresing_render/blender/tour.py`` carries ``added=`` and ``changed=``; every ``stop(...)``
``since=`` (the version it came in) and, when it was changed, ``changed=``. Writing these by hand is easy to forget, so
this tool records a **fingerprint** per set in ``tests/data/tour_versions.json``: its build function, the stops of the
set, the helper functions only this set uses (all as source without comments and without the version words) and the
git hashes of its test models. The precheck (``tools/ci_precheck.py``) compares:

* a set whose fingerprint differs from the one recorded on ``main`` must have ``changed=`` (or ``added=``, when the set
  is new) raised to the branch's new version – its message gives the line to write;
* the file must match the tree (``python3 tools/tour_versions.py --record`` writes it again);
* every stop has ``since=``.

    python3 tools/tour_versions.py              # what changed since the record (no writing)
    python3 tools/tour_versions.py --record     # write tests/data/tour_versions.json
    python3 tools/tour_versions.py --history    # replay the git tags: when each set / stop came and last changed

No Blender: plain Python 3.10+ (the precheck runs it).
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOUR = "fresing_render/blender/tour.py"
DATA = "fresing_render/data"
RECORD = "tests/data/tour_versions.json"
VERSION_WORDS = ("added", "changed", "since")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")


# ---------------------------------------------------------------------------
# reading tour.py
# ---------------------------------------------------------------------------

def _const(node, names: dict):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return names.get(node.id)
    return None


def _kw(call: ast.Call, names: dict) -> dict:
    return {k.arg: _const(k.value, names) for k in call.keywords if k.arg}


def _norm(src: str, node, drop=()) -> str:
    """The source of ``node`` as tokens without comments, blank lines or the keyword arguments in ``drop`` (the
    version words: raising ``changed=`` must not change the fingerprint). Stable across Python versions."""
    lines = src.encode("utf-8").splitlines(keepends=True)      # ast's columns count bytes, not characters
    base = sum(len(x) for x in lines[:node.lineno - 1])
    whole = b"".join(lines)
    seg = whole[base:sum(len(x) for x in lines[:node.end_lineno - 1]) + node.end_col_offset]
    for k in sorted(drop, key=lambda k: (k.lineno, k.col_offset), reverse=True):   # blank name=value
        a = sum(len(x) for x in lines[:k.lineno - 1]) + k.col_offset - base
        b = sum(len(x) for x in lines[:k.end_lineno - 1]) + k.end_col_offset - base
        if 0 <= a <= b <= len(seg):
            seg = seg[:a] + b" " * (b - a) + seg[b:]
    seg = seg.decode("utf-8", errors="replace")
    seg = "\n".join(x.lstrip() for x in seg.split("\n"))        # indentation says nothing here
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(seg).readline):
            if tok.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                            tokenize.ENDMARKER):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        out = seg.split()
    text = " ".join(out)
    while True:                                      # commas left by a blanked keyword
        new = re.sub(r",\s*,", ",", text)
        new = re.sub(r",\s*\)", ")", new)
        if new == text:
            return text
        text = new


def _refs(node) -> set:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def parse(src: str) -> dict:
    """{"sets": {id: {...}}, "stops": {id: {...}}} read from tour.py's source."""
    tree = ast.parse(src)
    names, funcs = {}, {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            names[node.targets[0].id] = node.value.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) \
                and isinstance(node.value, ast.Name) and node.value.id == "GROUPS":
            pass
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[node.name] = node
    sets, stops = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", "") == "tour_set" and d.args:
                    sid = _const(d.args[0], names)
                    if sid is None:
                        continue
                    kw = _kw(d, names)
                    sets[sid] = {"build": node, "deco": d, "title": _const(d.args[1], names) if len(d.args) > 1 else "",
                                 "models": [m for m in (_const(a, names) for a in d.args[2:]) if m],
                                 "added": kw.get("added") or "", "changed": kw.get("changed") or ""}
        call = node.value if isinstance(node, ast.Expr) else None
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "stop" and len(call.args) >= 3:
            st = _const(call.args[0], names)
            if st is None:
                continue
            kw = _kw(call, names)
            stops[st] = {"call": call, "set": _const(call.args[2], names) or "",
                         "since": kw.get("since") or "", "changed": kw.get("changed") or ""}
    return {"sets": sets, "stops": stops, "funcs": funcs, "names": names}


def _closure(start: set, funcs: dict) -> set:
    seen, todo = set(), [n for n in start if n in funcs]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo += [m for m in _refs(funcs[n]) if m in funcs and m not in seen]
    return seen


def fingerprints(src: str, blob_of) -> dict:
    """{set id: {"fp", "added", "changed", "models", "stops": {stop id: {"fp", "since", "changed"}}}}.

    ``blob_of(model file name)`` gives the model's git blob hash ('' when it is missing)."""
    p = parse(src)
    sets, stops, funcs = p["sets"], p["stops"], p["funcs"]
    reach = {}
    for sid, s in sets.items():
        start = _refs(s["build"]) - {s["build"].name}
        for st in stops.values():
            if st["set"] == sid:
                start |= _refs(st["call"])
        reach[sid] = _closure(start, funcs) - {s["build"].name}
    count: dict = {}
    for r in reach.values():
        for n in r:
            count[n] = count.get(n, 0) + 1
    out = {}
    for sid, s in sets.items():
        own = sorted(n for n in reach[sid] if count[n] == 1)
        parts = ["build " + _norm(src, s["build"]).split(":", 1)[-1]]
        st_out = {}
        for stid, st in stops.items():
            if st["set"] != sid:
                continue
            drop = [k for k in st["call"].keywords if k.arg in VERSION_WORDS]
            text = _norm(src, st["call"], drop)
            parts.append("stop " + text)
            st_out[stid] = {"fp": hashlib.sha256(text.encode()).hexdigest()[:16], "since": st["since"],
                            "changed": st["changed"]}
        parts += ["helper " + _norm(src, funcs[n]) for n in own]
        models = {m: blob_of(m) for m in s["models"]}
        parts += [f"model {m} {h}" for m, h in sorted(models.items())]
        out[sid] = {"fp": hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16], "added": s["added"],
                    "changed": s["changed"], "models": sorted(models), "helpers": own, "stops": st_out}
    return out


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def tree_blob_of(root: str = ROOT):
    def blob_of(name: str) -> str:
        try:
            with open(os.path.join(root, DATA, name), "rb") as fh:
                data = fh.read()
        except OSError:
            return ""
        if b"\r\n" in data and name.lower().endswith((".step", ".stp", ".json", ".hpscene")):
            pass
        return git_blob(data)
    return blob_of


def current(root: str = ROOT) -> dict:
    with open(os.path.join(root, TOUR), encoding="utf-8") as fh:
        return fingerprints(fh.read(), tree_blob_of(root))


def as_record(fps: dict) -> dict:
    return {"comment": "Written by tools/tour_versions.py --record (task 0199): one fingerprint per test tour set. "
                       "Do not edit by hand.",
            "sets": {k: {"fp": v["fp"], "added": v["added"], "changed": v["changed"]} for k, v in sorted(fps.items())}}


def read_record(text: str) -> dict:
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data.get("sets", {}) if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# the precheck's rule
# ---------------------------------------------------------------------------

def vtuple(v: str) -> tuple:
    return tuple(int(x) for x in v.split(".")) if v and VERSION.match(v) else ()


def check(fps: dict, record: dict, main_record: dict | None, *, version: str, raised: bool) -> tuple[list, list]:
    """(problems, notes) for the tour's version fields.

    ``record``: tests/data/tour_versions.json of this tree; ``main_record``: the same file on main (None: not there
    yet – the first record); ``version``: this tree's version; ``raised``: the branch has raised the version (else the
    branch is still being built and a missing ``changed=`` is only a note)."""
    problems, notes = [], []
    rec_cmd = "python3 tools/tour_versions.py --record"
    for sid, f in fps.items():
        for word in ("added", "changed"):
            if f[word] and not VERSION.match(f[word]):
                problems.append(f"test tour set '{sid}': {word}='{f[word]}' is not a version like 0.2.47")
        if not f["added"]:
            problems.append(f"test tour set '{sid}': write added=\"{version}\" in its @tour_set(...) in "
                            f"{TOUR} (the version it comes in), then run {rec_cmd}")
        for stid, st in f["stops"].items():
            if not st["since"]:
                problems.append(f"test tour stop '{stid}': write since=\"{version}\" in its stop(...) in {TOUR} (the "
                                "version it comes in)")
            elif not VERSION.match(st["since"]):
                problems.append(f"test tour stop '{stid}': since='{st['since']}' is not a version like 0.2.47")
            if st["changed"] and not VERSION.match(st["changed"]):
                problems.append(f"test tour stop '{stid}': changed='{st['changed']}' is not a version like 0.2.47")
    if main_record is not None:
        for sid, f in fps.items():
            old = main_record.get(sid)
            if old is not None and old.get("fp") == f["fp"]:
                continue
            word = "added" if old is None else "changed"
            have = f[word]
            if vtuple(have) and vtuple(have) >= vtuple(version) and (raised or vtuple(have) > vtuple(old.get(word, "")
                                                                                                if old else "")):
                continue
            what = "is new" if old is None else "changed (its build, its stops, a helper only it uses or its test model)"
            text = (f"test tour set '{sid}' {what} on this branch: write {word}=\"{version}\" in its "
                    f"@tour_set(\"{sid}\", ...) in {TOUR} – the version this branch brings – then run {rec_cmd}")
            if raised:
                problems.append(text)
            else:
                notes.append(text + " (needed once the version is raised)")
    stale = sorted(sid for sid in set(fps) | set(record)
                   if sid not in record or sid not in fps or record[sid].get("fp") != fps[sid]["fp"]
                   or record[sid].get("added") != fps[sid]["added"] or record[sid].get("changed") != fps[sid]["changed"])
    if stale:
        text = (f"{RECORD} is out of date for {', '.join(stale[:8])}{' …' if len(stale) > 8 else ''}: "
                f"run {rec_cmd} and commit it")
        (problems if raised else notes).append(text)
    return problems, notes


# ---------------------------------------------------------------------------
# history (the backfill of task 0199)
# ---------------------------------------------------------------------------

def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, errors="replace").stdout


def history() -> dict:
    """Replay every release tag: {"sets": {id: [first, last changed]}, "stops": {id: [first, last changed]}}."""
    tags = sorted((t for t in _git("tag").split() if re.fullmatch(r"v\d+\.\d+\.\d+", t)),
                  key=lambda t: vtuple(t[1:]))
    seen_sets, seen_stops, prev = {}, {}, None
    for tag in tags:
        src = _git("show", f"{tag}:{TOUR}")
        if not src.strip():
            continue

        def blob_of(name, tag=tag):
            return _git("rev-parse", f"{tag}:{DATA}/{name}").strip()

        try:
            fps = fingerprints(src, blob_of)
        except SyntaxError:
            continue
        v = tag[1:]
        for sid, f in fps.items():
            if sid not in seen_sets:
                seen_sets[sid] = [v, ""]
            elif prev and sid in prev and prev[sid]["fp"] != f["fp"]:
                seen_sets[sid][1] = v
            for stid, st in f["stops"].items():
                old = next((p["stops"][stid] for p in (prev or {}).values() if stid in p["stops"]), None)
                if stid not in seen_stops:
                    seen_stops[stid] = [v, ""]
                elif old is not None and old["fp"] != st["fp"]:
                    seen_stops[stid][1] = v
        prev = fps
    return {"sets": seen_sets, "stops": seen_stops}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--record", action="store_true", help=f"write {RECORD}")
    ap.add_argument("--history", action="store_true", help="replay the release tags (needs the tags fetched)")
    args = ap.parse_args(argv)
    if args.history:
        print(json.dumps(history(), indent=1))
        return 0
    fps = current()
    path = os.path.join(ROOT, RECORD)
    if args.record:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(as_record(fps), fh, indent=1, sort_keys=True)
            fh.write("\n")
        print(f"recorded {len(fps)} test tour sets in {RECORD}")
        return 0
    try:
        rec = read_record(open(path, encoding="utf-8").read())
    except OSError:
        rec = {}
    changed = sorted(k for k in fps if rec.get(k, {}).get("fp") != fps[k]["fp"])
    print("changed since the record: " + (", ".join(changed) or "nothing"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
