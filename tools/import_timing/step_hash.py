"""Prototype measurement (task 0301): which parts of a new STEP revision are unchanged, without OpenCascade?

    python tools/import_timing/step_hash.py old.step new.step

Reads each file's DATA section as text, and gives every part's shape representation a hash of everything it is made
of (a Merkle hash: an entity's hash = its type + its own numbers + the hashes of the entities it points at, so the
entity numbers – which change between exports – do not count). A part of the new file whose hash is in the old file
is unchanged: a model update could take its mesh from the old cache instead of turning it into a shape and meshing
it again. Prints the time per file and how many parts match. Measures only.
"""

from __future__ import annotations

import hashlib
import re
import sys
import time

ENTITY = re.compile(rb"#(\d+)\s*=\s*(.*?);\s*(?=#\d+\s*=|ENDSEC)", re.S)
REF = re.compile(rb"#(\d+)")
SHAPE_REPS = (b"ADVANCED_BREP_SHAPE_REPRESENTATION", b"MANIFOLD_SURFACE_SHAPE_REPRESENTATION",
              b"FACETED_BREP_SHAPE_REPRESENTATION")
SKIP_TEXT = re.compile(rb"'[^']*'")          # names and ids inside the entities are left out of the hash


def entities(path: str) -> dict:
    data = open(path, "rb").read()
    start = data.index(b"DATA;") + 5
    out = {}
    for m in ENTITY.finditer(data, start):
        out[int(m.group(1))] = re.sub(rb"\s+", b"", m.group(2))
    return out


def hashes(ents: dict) -> dict:
    memo: dict = {}

    def h(i: int) -> bytes:
        if i in memo:
            return memo[i]
        stack = [i]
        while stack:
            j = stack[-1]
            if j in memo:
                stack.pop()
                continue
            body = ents.get(j, b"")
            refs = [int(r) for r in REF.findall(body)]
            todo = [r for r in refs if r not in memo and r != j]
            if todo:
                stack.extend(todo)
                continue
            stack.pop()
            text = SKIP_TEXT.sub(b"''", body)
            text = REF.sub(lambda m: memo.get(int(m.group(1)), b"?").hex().encode(), text)
            memo[j] = hashlib.blake2b(text, digest_size=16).digest()
        return memo[i]

    return {i: h(i) for i, body in ents.items() if body.startswith(SHAPE_REPS)}


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    res = []
    for p in argv[:2]:
        t = time.time()
        e = entities(p)
        t1 = time.time()
        hs = hashes(e)
        t2 = time.time()
        res.append(hs)
        print(f"{p}: {len(e)} entities, parse {t1 - t:.1f} s, hash {t2 - t1:.1f} s, {len(hs)} part shapes")
    if len(res) == 2:
        old = set(res[0].values())
        same = sum(1 for v in res[1].values() if v in old)
        print(f"new file: {same} of {len(res[1])} part shapes unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
