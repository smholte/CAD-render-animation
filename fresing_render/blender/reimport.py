"""Update the model to a new revision of the STEP file and keep all work.

Parts of the old and the new model are matched:
    1. by occurrence name path (Inventor "Frame:1" names), when those are unique
    2. by part name path, the nearest copy first (repeated bolts)
    3. by part name anywhere, when the part only moved to another subassembly
    4. by shape (triangles, size) in the same place: a renamed part (task 0117), named in the report
Matched parts keep: manual material group, hidden / removed, unlocked, free moves,
joints (moving parts and the part they sit on), poses, visibility sets, scenes and
animation targets, painted faces when the part's faces did not change, and decals whose spot is
still on the part (task 0024), labels and the camera's sharp spot (task 0052). Joints, cylinders and
mechanisms that link this model to another one stay (task 0052). New and missing parts, parts that lost
painted faces, decals that must be placed again and labels whose part is gone are listed in a report.

All or nothing (task 0052): the new revision is built first; the old model is deleted only when everything
was carried over. When a step fails, what was made on the new model is taken apart again, the new model is
deleted and the set-up is rebuilt on the old model: the project is as it was, and ``UpdateFailed`` says why.
"""

from __future__ import annotations

import json
import re
import time

import bpy
from mathutils import Matrix, Vector

from ..core import places
from ..core.words import plural
from . import build, faces, joints, logic, states

_VERSION_SUFFIX = re.compile(r"\s+v\d+$", re.I)       # Fusion: "Bracket v12"
_COUNT_SUFFIX = re.compile(r"[:#]\d+$")               # Inventor: "Frame:1"


def _norm(name: str) -> str:
    n = _COUNT_SUFFIX.sub("", name or "").strip()
    return _VERSION_SUFFIX.sub("", n).strip().lower()


def _chain(ob, parent_of) -> list:
    out = []
    p = ob
    while p is not None:
        out.append(p)
        p = parent_of(p)
    out.reverse()
    return out[1:]        # without the model root (its name follows the file name)


def records(objs) -> list[dict]:
    """Matching keys and CAD-pose positions for model objects."""
    memo: dict[str, Matrix] = {}

    def cad_matrix(ob) -> Matrix:
        if ob.name in memo:
            return memo[ob.name]
        p = build.logical_parent(ob)
        m = Matrix.Identity(4) if p is None else cad_matrix(p) @ build.cad_basis(ob)
        memo[ob.name] = m
        return m

    out = []
    for ob in objs:
        if build.logical_parent(ob) is None:
            continue                            # roots are matched to each other directly
        chain = _chain(ob, build.logical_parent)
        inst = [c.get(build.PROP_INSTANCE, "") for c in chain]
        inst = ["" if i.startswith("=>[") else i for i in inst]      # OpenCascade placeholders
        out.append({
            "ob": ob,
            "shape": _shape(ob),
            "kind": ob.get(build.PROP_KIND),
            "key_a": tuple(inst) if all(inst) else None,
            "made": any(c.get(build.PROP_MADE_NAME) for c in chain),     # a name the mesh reader made (task 0139)
            "made_self": bool(ob.get(build.PROP_MADE_NAME)),
            "key_b": tuple(_norm(c.get(build.PROP_NAME, c.name)) for c in chain),
            "leaf": _norm(ob.get(build.PROP_NAME, ob.name)),
            "pos": cad_matrix(ob).translation.copy(),
            "centre": _centre(ob, cad_matrix(ob)),
        })
    return out


def _centre(ob, m: Matrix):
    """The middle of a part's box in the CAD pose (its origin for an assembly): a mesh file's nodes mostly all have
    their origin at the model's origin, so "the same place" is the place of the part itself (task 0162)."""
    if ob.type != "MESH" or ob.data is None or not len(ob.data.vertices):
        return m.translation.copy()
    lo = [min(c[k] for c in ob.bound_box) for k in range(3)]
    hi = [max(c[k] for c in ob.bound_box) for k in range(3)]
    return m @ Vector(tuple((a + b) / 2.0 for a, b in zip(lo, hi)))


def _shape(ob):
    """A part's shape as numbers (triangles, size in 0.1 mm): a part renamed in a new revision is found by its shape
    and place (task 0117: a mesh file's renamed node). None for assemblies."""
    if ob.type != "MESH" or ob.data is None or not len(ob.data.polygons):
        return None
    lo = [min(c[k] for c in ob.bound_box) for k in range(3)]
    hi = [max(c[k] for c in ob.bound_box) for k in range(3)]
    return (len(ob.data.polygons),) + tuple(round((b - a) * 10000) for a, b in zip(lo, hi))


def _candidates(olds: list[dict], news: list[dict], k: int = 8, at: str = "pos") -> list[tuple[float, int, int]]:
    """(distance, old index, new index) pairs, nearest first. Big groups (1,000 identical bolts)
    use a k-d tree and only the k nearest neighbours instead of every pair. ``at``: which place is compared."""
    def p(r):
        return r.get(at, r["pos"])
    if len(olds) * len(news) <= 40000:
        return sorted(((p(o) - p(n)).length, i, j) for i, o in enumerate(olds) for j, n in enumerate(news))
    from mathutils.kdtree import KDTree
    tree = KDTree(len(news))
    for j, n in enumerate(news):
        tree.insert(p(n), j)
    tree.balance()
    cand = []
    for i, o in enumerate(olds):
        for _co, j, dist in tree.find_n(p(o), min(k, len(news))):
            cand.append((dist, i, j))
    cand.sort()
    return cand


def match(old: list[dict], new: list[dict], move_tolerance: float = 0.005) -> list[tuple[dict, dict]]:
    """Pair old and new records. Returns [(old, new)]."""
    pairs: list[tuple[dict, dict]] = []
    used_old: set[int] = set()
    used_new: set[int] = set()

    def take(o, n):
        pairs.append((o, n))
        used_old.add(id(o))
        used_new.add(id(n))

    # 1. occurrence names
    def by(key, recs):
        g: dict = {}
        for r in recs:
            k = key(r)
            if k is not None:
                g.setdefault(k, []).append(r)
        return g

    ga = by(lambda r: (r["kind"], r["key_a"]) if r["key_a"] else None, old)
    gb = by(lambda r: (r["kind"], r["key_a"]) if r["key_a"] else None, new)
    for k, olds in ga.items():
        news = gb.get(k, [])
        if len(olds) == 1 and len(news) == 1:
            take(olds[0], news[0])

    # 1b. names the mesh reader made (piece numbers, "Node 3") shift when a piece is added or removed: those match
    #     by shape and place first (task 0139, 0131 row 3); their assemblies by their parts (``_made_assemblies``)
    #     A part with a name of its own inside a made group ("B1" in "Node 5") keeps that name in the key, and the
    #     place compared is the middle of its box, not its origin (all at the model's origin; task 0162)
    made = (lambda r: (r["kind"], r["shape"], "made", "" if r.get("made_self") else r["leaf"])
            if r.get("made") and r.get("shape") else None)
    # 2. name path, nearest first (a made name only in the same place); 3. same name anywhere, only if it did not
    #    move; 4. renamed: the same shape in the same place (task 0117), reported
    renamed = (lambda r: (r["kind"], r["shape"]) if r.get("shape") else None)

    def free(recs, used):
        # an assembly whose own name the reader made ("Node 5") says nothing by its name, and its origin is mostly
        # the model's: "the same place" paired the wrong groups once one was added or removed (0147 row 3). Those
        # pair only through their parts (``_made_assemblies``).
        return [r for r in recs if id(r) not in used and not (r.get("made_self") and r["kind"] != "part")]
    def by_leaf(r):
        return (r["kind"], r["leaf"])
    leaf_old = _leaf_counts(old)
    leaf_new = _leaf_counts(new)
    for key, tol in ((made, move_tolerance), (lambda r: (r["kind"], r["key_b"]), None),
                     (by_leaf, move_tolerance), (renamed, move_tolerance)):
        go = by(key, free(old, used_old))
        gn = by(key, free(new, used_new))
        for k, olds in go.items():
            news = gn.get(k, [])
            if not news:
                continue
            t = tol
            if t is None and any(r.get("made") for r in olds + news):
                t = move_tolerance               # a made name says nothing on its own: the place must agree
            if t is None and len(olds) == 1 and len(news) == 1:
                take(olds[0], news[0])
                continue
            if key is by_leaf and len(olds) == 1 and len(news) == 1 and _own_name(olds[0], leaf_old) \
                    and _own_name(news[0], leaf_new):
                # a part with a name of its own, the only one so called, inside a group whose name the reader made:
                # its name says who it is, wherever the group went (task 0188, 0183 row 5)
                take(olds[0], news[0])
                continue
            while True:                      # repeat: the k-d tree only offers the nearest few
                rem_o = [o for o in olds if id(o) not in used_old]
                rem_n = [n for n in news if id(n) not in used_new]
                if not rem_o or not rem_n:
                    break
                progress = False
                for dist, i, j in _candidates(rem_o, rem_n, at="centre" if key is made else "pos"):
                    o, n = rem_o[i], rem_n[j]
                    if id(o) in used_old or id(n) in used_new:
                        continue
                    if t is not None and dist > t:
                        break
                    take(o, n)
                    if key is renamed and o["leaf"] != n["leaf"] and not (o.get("made") and n.get("made")):
                        o["renamed"] = True
                    progress = True
                if not progress or t is not None:
                    break
    _shifted_made_parts(old, new, pairs, take, used_old, used_new, move_tolerance)
    _made_assemblies(old, new, pairs, take, used_old, used_new, move_tolerance)
    if _groups_by_place(old, new, pairs, take, used_old, used_new):
        _made_assemblies(old, new, pairs, take, used_old, used_new, move_tolerance)
    return pairs


def _leaf_counts(recs) -> dict:
    out: dict = {}
    for r in recs:
        out[(r["kind"], r["leaf"])] = out.get((r["kind"], r["leaf"]), 0) + 1
    return out


def _own_name(r, counts) -> bool:
    """A part named in the file ("B1"), the only record so called, inside a group whose name the reader made. Only
    when the record says outright that its own name is the file's (a piece number "W 2" never pairs by name)."""
    return (r["kind"] == "part" and bool(r.get("made")) and r.get("made_self") is False and bool(r["leaf"])
            and counts.get((r["kind"], r["leaf"])) == 1)


def _made_assemblies(old, new, pairs, take, used_old, used_new, tol) -> None:
    """An assembly with a name the mesh reader made ("Node 3") that no rule matched: it pairs with the new assembly
    that holds the most of its matched parts, in the same place (task 0139) – or moved by just as much as those parts
    moved (task 0188: the revision moved the whole group). Level by level, from the parts up."""
    rec_of = {r["ob"].name: r for r in old + new if "ob" in r}
    if not rec_of:
        return
    while True:
        votes: dict = {}
        shifts: dict = {}
        for o, n in pairs:
            po, pn = build.logical_parent(o["ob"]), build.logical_parent(n["ob"])
            ro, rn = (rec_of.get(po.name) if po else None), (rec_of.get(pn.name) if pn else None)
            if ro is None or rn is None or id(ro) in used_old or id(rn) in used_new:
                continue
            if not (ro.get("made") or rn.get("made")) or ro["kind"] != rn["kind"]:
                continue
            votes[(id(ro), id(rn))] = votes.get((id(ro), id(rn)), 0) + 1
            shifts.setdefault((id(ro), id(rn)), []).append(
                (n["centre"] - o["centre"], o.get("shape") == n.get("shape")))
        only: dict = {}                           # the groups each group's paired parts went to / came from
        for io, jn in votes:
            only.setdefault(io, set()).add(jn)
            only.setdefault(jn, set()).add(io)
        ranked = sorted(votes.items(), key=lambda kv: -kv[1])
        by_id = {id(r): r for r in old + new}
        progress = False
        for (io, jn), count in ranked:
            ro, rn = by_id[io], by_id[jn]
            if id(ro) in used_old or id(rn) in used_new:
                continue
            moved = rn["pos"] - ro["pos"]
            if moved.length > tol and not _moved_along(moved, shifts[(io, jn)], tol) \
                    and not (count >= 2 and only.get(io) == {jn} and only.get(jn) == {io}):
                continue                          # not in the same place, its parts did not move with it, and
                #                                   they did not all stay together (task 0237: re-arranged)
            take(ro, rn)
            progress = True
        if not progress:
            return


def _groups_by_place(old, new, pairs, take, used_old, used_new) -> bool:
    """A group with no name in the file whose parts ALL changed shape (task 0325, bug hunt 0328 row 23): no rule pairs
    any of its parts (no shape is left to compare), so nothing pairs the group either. It is the same node of the
    tree when it sits at the same place in it: the reader's own id (``fr_uid``: the path of made names, "Node 4#1",
    from the root) is the same, its parent is the same (both under the model's root, or paired with each other) and
    it holds as many parts, each again at the same place (same id, same kind) and of about the same size (no side
    more than twice or half as long, give or take 50 mm). Then the group and its parts pair; the parts as changed.
    Only when none of the group's parts paired on either side: a group with one part left as it was pairs through
    that part (``_shifted_made_parts``, ``_made_assemblies``). Returns whether it paired anything."""
    rec_of = {r["ob"].name: r for r in old + new if "ob" in r}
    if not rec_of:
        return False
    paired = {id(o): id(n) for o, n in pairs}

    def parent(r):
        p = build.logical_parent(r["ob"])
        return rec_of.get(p.name) if p is not None else None

    def kids(recs):
        out: dict = {}
        for r in recs:
            p = parent(r) if "ob" in r else None
            if p is not None:
                out.setdefault(id(p), []).append(r)
        return out

    def uid(r):
        return r["ob"].get(build.PROP_UID, "")

    def alike(a, b) -> bool:
        if a.get("shape") is None or b.get("shape") is None:
            return a.get("shape") is None and b.get("shape") is None
        for x, y in zip(a["shape"][1:], b["shape"][1:]):                    # sizes in 0.1 mm
            lo, hi = sorted((x, y))
            if hi > 2 * lo + 500:
                return False
        return True

    kids_o, kids_n = kids(old), kids(new)
    groups_n = {uid(r): r for r in new if r["kind"] == "assembly" and r.get("made_self") and id(r) not in used_new
                and uid(r)}
    found = False
    for ro in old:
        if ro["kind"] != "assembly" or not ro.get("made_self") or id(ro) in used_old or not uid(ro):
            continue
        rn = groups_n.get(uid(ro))
        if rn is None or id(rn) in used_new:
            continue
        po, pn = parent(ro), parent(rn)
        if (po is None) != (pn is None) or (po is not None and paired.get(id(po)) != id(pn)):
            continue
        ko, kn = kids_o.get(id(ro), []), kids_n.get(id(rn), [])
        if not ko or len(ko) != len(kn) or any(id(k) in used_old for k in ko) or any(id(k) in used_new for k in kn):
            continue
        by_uid = {uid(k): k for k in kn}
        twins = [(k, by_uid.get(uid(k))) for k in ko]
        if any(n is None or n["kind"] != o["kind"] or not alike(o, n) for o, n in twins):
            continue
        take(ro, rn)
        paired[id(ro)] = id(rn)
        for o, n in twins:
            take(o, n)
            if o["kind"] == "part" and o.get("shape") != n.get("shape"):
                o["changed"] = True
        found = True
    return found


def _moved_along(moved, shifts, tol) -> bool:
    """Did a group's parts move with the group (task 0237, 0209 row 5)? ``shifts``: (the part's box-middle shift,
    its shape unchanged). A part whose shape changed has another box middle and does not veto: the parts of
    unchanged shape vote (all parts when every one changed), and more than half of them must have moved by just as
    much as the group. A real re-arrangement (most parts elsewhere in the group) still fails."""
    voters = [d for d, same in shifts if same] or [d for d, _same in shifts]
    agree = sum(1 for d in voters if (d - moved).length <= tol)
    return 2 * agree > len(voters)


def _shifted_made_parts(old, new, pairs, take, used_old, used_new, tol) -> None:
    """Parts with no name in the file ("Node 7") inside a group the revision moved (task 0237, 0209 row 5): the
    name rules and "same shape in the same place" leave them all unpaired. Per pair of groups (an old and a new
    group not yet paired elsewhere, or already paired with each other), the shift most of their same-shaped unpaired
    parts share is the group's move: those parts pair by shape at that shift; then a part that is the only one of
    its shape on both sides (re-arranged inside the group); then a part left over on both sides whose box middle
    sits where the move puts it, give or take half its change in size, is the same part changed (``changed``)."""
    rec_of = {r["ob"].name: r for r in old + new if "ob" in r}
    if not rec_of:
        return

    def parent(r):
        p = build.logical_parent(r["ob"]) if "ob" in r else None
        return rec_of.get(p.name) if p is not None else None

    def loose(recs, used):
        out: dict = {}
        for r in recs:
            if id(r) in used or r["kind"] != "part" or not r.get("made_self") or not r.get("shape"):
                continue
            p = parent(r)
            if p is not None:
                out.setdefault(id(p), []).append(r)
        return out
    by_parent_o, by_parent_n = loose(old, used_old), loose(new, used_new)
    if not by_parent_o or not by_parent_n:
        return
    # where the groups' paired parts went: a group pair is only a candidate when neither sent parts elsewhere
    went: dict = {}
    for o, n in pairs:
        po, pn = parent(o), parent(n)
        if po is not None and pn is not None:
            went.setdefault(("o", id(po)), set()).add(id(pn))
            went.setdefault(("n", id(pn)), set()).add(id(po))
    paired = {id(o): id(n) for o, n in pairs}
    paired_n = {id(n): id(o) for o, n in pairs}
    by_id = {id(r): r for r in old + new}

    def fits(io, jn) -> bool:
        po, pn = by_id[io], by_id[jn]
        if po["kind"] != pn["kind"]:
            return False
        if io in paired or jn in paired_n:
            return paired.get(io) == jn
        return went.get(("o", io), {jn}) == {jn} and went.get(("n", jn), {io}) == {io}

    parents_of_shape: dict = {}                   # only group pairs that share a shape are looked at
    for jn, ns in by_parent_n.items():
        for n in ns:
            parents_of_shape.setdefault(n["shape"], set()).add(jn)
    ranked = []
    for io, os_ in by_parent_o.items():
        for jn in set().union(*(parents_of_shape.get(o["shape"], set()) for o in os_)):
            if not fits(io, jn):
                continue
            ns = by_parent_n[jn]
            count, shift = _best_shift(os_, ns, tol)
            if count and 2 * count >= max(len(os_), len(ns)):    # else most of their parts went elsewhere
                ranked.append((count, io, jn, shift))
    ranked.sort(key=lambda t: -t[0])
    done_o: set = set()
    done_n: set = set()
    for _count, io, jn, shift in ranked:
        if io in done_o or jn in done_n:
            continue
        done_o.add(io)
        done_n.add(jn)
        os_ = [o for o in by_parent_o[io] if id(o) not in used_old]
        ns = [n for n in by_parent_n[jn] if id(n) not in used_new]
        trees = _shape_trees(ns)
        for o in os_:
            hit = trees.get(o["shape"])
            if hit is None:
                continue
            tree, recs = hit
            for _co, j, _dist in tree.find_range(o["centre"] + shift, tol):
                if id(recs[j]) not in used_new:
                    take(o, recs[j])
                    break
        os_ = [o for o in os_ if id(o) not in used_old]
        ns = [n for n in ns if id(n) not in used_new]
        # a part re-arranged inside the group: the only one of its shape on both sides is the same part
        so = _counts(o["shape"] for o in os_)
        sn = _counts(n["shape"] for n in ns)
        for o in os_:
            if so[o["shape"]] == 1 and sn.get(o["shape"]) == 1:
                take(o, next(n for n in ns if n["shape"] == o["shape"]))
        os_ = [o for o in os_ if id(o) not in used_old]
        ns = [n for n in ns if id(n) not in used_new]
        if not os_ or not ns or len(os_) * len(ns) > 40000:
            continue
        cand = []
        for i, o in enumerate(os_):
            for j, n in enumerate(ns):
                off = n["centre"] - o["centre"] - shift
                grow = [abs(a - b) / 20000.0 for a, b in zip(o["shape"][1:], n["shape"][1:])]   # half, in m
                if all(abs(off[k]) <= tol + grow[k] for k in range(3)):
                    cand.append((off.length, i, j))
        for _dist, i, j in sorted(cand):
            if id(os_[i]) not in used_old and id(ns[j]) not in used_new:
                take(os_[i], ns[j])
                os_[i]["changed"] = True


def _shape_trees(recs) -> dict:
    """{shape: (k-d tree of the box middles, the records)}."""
    from mathutils.kdtree import KDTree
    groups: dict = {}
    for r in recs:
        groups.setdefault(r["shape"], []).append(r)
    out = {}
    for shape, rs in groups.items():
        tree = KDTree(len(rs))
        for j, r in enumerate(rs):
            tree.insert(r["centre"], j)
        tree.balance()
        out[shape] = (tree, rs)
    return out


def _best_shift(os_, ns, tol, tries: int = 64) -> tuple:
    """(how many of ``os_`` have a same-shaped part of ``ns`` at that shift, the shift) for the shift most of them
    share. The shifts tried come from the rarest shapes first (a bolt of 1,000 says little), at most ``tries``;
    each is counted with one k-d tree per shape, so 3,000 parts cost milliseconds, not every pair."""
    trees = _shape_trees(ns)
    olds: dict = {}
    for o in os_:
        if o["shape"] in trees:
            olds.setdefault(o["shape"], []).append(o)
    if not olds:
        return 0, None
    tried: list = []
    for shape in sorted(olds, key=lambda k: len(olds[k]) * len(trees[k][1])):
        for o in olds[shape]:
            for n in trees[shape][1]:
                d = n["centre"] - o["centre"]
                if not any((d - e).length <= tol for e in tried):
                    tried.append(d)
                if len(tried) >= tries:
                    break
            if len(tried) >= tries:
                break
        if len(tried) >= tries:
            break
    best = (0, None)
    for d in tried:
        count = 0
        for shape, os_s in olds.items():
            tree = trees[shape][0]
            for o in os_s:
                dist = tree.find(o["centre"] + d)[2]
                count += dist is not None and dist <= tol
        if count > best[0]:
            best = (count, d)
    return best


def _counts(items) -> dict:
    out: dict = {}
    for k in items:
        out[k] = out.get(k, 0) + 1
    return out


def _group_notes(pairs, tol) -> list[str]:
    """One line per group with a name the mesh reader made that the revision moved (task 0237): "Node 4 moved
    100 mm; 1 part changed – its work is kept"."""
    by_parent: dict = {}
    for o, n in pairs:
        if o["kind"] != "part" or "ob" not in o:
            continue
        po, pn = build.logical_parent(o["ob"]), build.logical_parent(n["ob"])
        if po is not None and pn is not None:
            by_parent.setdefault((po.name, pn.name), []).append((o, n))
    out = []
    for o, n in pairs:
        if o["kind"] != "assembly" or not o.get("made_self") or "ob" not in o or "pos" not in n:
            continue
        kids = by_parent.get((o["ob"].name, n["ob"].name), [])
        same = [b["centre"] - a["centre"] for a, b in kids if a.get("shape") == b.get("shape")]
        if not same:                                       # every part changed (task 0325): the move of the side of
            same = [_side_move(a, b) for a, b in kids if a.get("shape") and b.get("shape")]   # each box that kept
        if not same:                                       # its place against the others
            continue
        same.sort(key=lambda d: d.length)
        moved = same[len(same) // 2]                       # the median part's move
        if moved.length <= tol:
            continue
        changed = sum(1 for a, b in kids if a.get("shape") != b.get("shape"))
        line = f"{o['ob'].get(build.PROP_NAME, o['ob'].name)} moved {moved.length * 1000:.0f} mm"
        if changed:
            line += f"; {plural(changed, 'part')} changed"
        out.append(line + " – its work is kept")
    return out


def _side_move(a, b):
    """How far a part whose box changed size moved (task 0325): per axis the move of the side of its box that moved
    least (a box made 20 mm wider on one side keeps the other side where the group's move puts it)."""
    d = b["centre"] - a["centre"]
    out = []
    for k in range(3):
        half = (b["shape"][k + 1] - a["shape"][k + 1]) / 20000.0          # half the change in size, m
        out.append(min((d[k] - half, d[k] + half), key=abs))
    return Vector(out)


def _made_root(old_recs, new_root, pairs) -> list[tuple[dict, dict]]:
    """0162's open point (task 0188): when a mesh revision leaves one group whose name the reader made ("Node 4"), the
    reader makes that group the model's root, and the root pairs with the old root. Its work (the eye, steps aimed at
    it) belongs to the old group that held most of the parts now directly under the new root: pair that group with
    the new root as well. Only for a root whose name the reader made; STEP roots never are."""
    if not new_root.get(build.PROP_MADE_NAME):
        return []
    paired = {id(o) for o, _n in pairs}
    rec_of = {r["ob"].name: r for r in old_recs}
    votes: dict = {}
    under = 0
    for o, n in pairs:
        if build.logical_parent(n["ob"]) is not new_root:
            continue
        under += 1
        po = build.logical_parent(o["ob"])
        ro = rec_of.get(po.name) if po is not None else None
        if ro is not None and ro.get("made_self") and ro["kind"] == "assembly" and id(ro) not in paired:
            votes[id(ro)] = votes.get(id(ro), 0) + 1
    if not votes:
        return []
    best, count = max(votes.items(), key=lambda kv: kv[1])
    if 2 * count <= under:
        return []                          # the new root's parts came from many groups: none of them is it
    ro = next(r for r in old_recs if id(r) == best)
    return [(ro, {"ob": new_root, "kind": "assembly"})]


def _model_objects_of(root, tree) -> list:
    return [root] + [d for d in tree.descendants(root) if d.get(build.PROP_KIND) in build.MODEL_KINDS]


class _Clock:
    """Seconds per stage of an update (task 0324): ``lap(name)`` adds the time since the last lap to ``name``."""

    def __init__(self):
        self.t0 = self.t = time.perf_counter()
        self.laps: dict = {}

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.laps[name] = self.laps.get(name, 0.0) + now - self.t
        self.t = now

    def table(self) -> dict:
        out = {k: round(v, 2) for k, v in self.laps.items()}
        out["total"] = round(time.perf_counter() - self.t0, 2)
        return out


class UpdateFailed(RuntimeError):
    """The model update did not happen; the message says why (and whether the project is unchanged)."""


def _names(coll) -> set:
    return {x.name for x in coll}


class _State:
    """What an update has done so far, for putting it back when a later step fails."""

    def __init__(self, old_root, new_root, before):
        self.old_root, self.new_root, self.before = old_root, new_root, before
        self.cyl_specs = self.mech_specs = self.specs = None
        self.old_objs: list = []
        self.mapping: dict = {}
        self.decals_moved = False
        self.welds_undo = None                    # task 0319: puts the welds back on the old parts
        self.rebuilding = False
        self.pairs: list = []                  # (old object, new object)
        self.aside: list = []                  # old collections out of the scene: (collection, parents)
        self.clock = _Clock()


def _set_aside(scene, old_collections, old_names: set) -> list:
    """While the set-up is rebuilt on the new model, the old one stays (for a way back) but leaves the scene,
    so scene updates and walks over the scene's objects see one model, not two. Only collections that hold
    nothing but the old model. Returns what to put back (``_put_back``)."""
    cols = [c for c in old_collections if all(o.name in old_names for o in c.all_objects)]
    out = []
    for col in cols:
        parents = [p for p in [scene.collection] + list(bpy.data.collections) if col.name in p.children]
        for p in parents:
            p.children.unlink(col)
        out.append((col, parents))
    return out


def _alive(idb) -> bool:
    try:
        idb.name
        return True
    except ReferenceError:
        return False


def _put_back(aside: list) -> None:
    for col, parents in aside:
        for p in parents:
            if col.name not in p.children:
                p.children.link(col)
    aside.clear()


def _remove_new(before: dict, root=None) -> None:
    """Delete what the update made (the new model and anything left over), never what was there before."""
    obs = []
    if root is not None:
        try:
            obs = [root] + list(root.children_recursive)
        except ReferenceError:
            obs = []
    obs += [ob for ob in bpy.data.objects if ob.name not in before["objects"]]
    seen, unique = set(), []
    for ob in obs:
        if ob.as_pointer() not in seen:
            seen.add(ob.as_pointer())
            unique.append(ob)
    if unique:
        bpy.data.batch_remove(unique)
    meshes = [me for me in bpy.data.meshes if me.name not in before["meshes"] and me.users == 0]
    if meshes:
        bpy.data.batch_remove(meshes)
    for col in [c for c in bpy.data.collections if c.name not in before["collections"]]:
        if len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)


def _both(first, second):
    """Two undo functions as one (the welds of 0319, then those from the CAD file, task 0323)."""
    def undo():
        if second is not None:
            second()
        if first is not None:
            first()
    return undo


def update_model(context, old_root, cache_dir: str, copies: bool = True) -> dict:
    """Replace ``old_root`` by the model in ``cache_dir``, keeping all work. Returns a summary.

    Task 0293: a whole model that was copied (or a copy of one) updates the other models of its copy group too
    (``copies``), each keeping its own work and place; a copy of a subassembly or parts is refused (it is frozen).

    Raises ``UpdateFailed`` when it could not be done; the project is then as it was."""
    scene = context.scene
    from . import compat
    if compat.blocked(scene):                    # task 0352: never write an older app's model into a newer project
        raise UpdateFailed(compat.blocked(scene))
    if old_root.get("fr_lifting"):               # task 0214 (0209 row 4): a crane is rigged from its equipment file
        raise UpdateFailed("this is a crane of the lifting plan: Remove it in 8 Lifting plan and place it again")
    from . import copy as copy_mod
    why = copy_mod.refused_update(old_root)
    if why:
        raise UpdateFailed(why)
    followers = [r.name for r in copy_mod.others(scene, old_root)] if copies else []
    removed = old_root.get("fr_removed", "")   # task 0292: parts Remove took out of this model
    before = {"objects": _names(bpy.data.objects), "meshes": _names(bpy.data.meshes),
              "collections": _names(bpy.data.collections)}
    build.ensure_bases(scene)
    clock = _Clock()
    # 1. the new revision first: when it cannot be read or built, nothing has changed yet
    try:
        # the new revision keeps the old one's part-ID scope (task 0056: the second copy of a STEP stays itself)
        from ..importer.runner import update_full
        pool = None if update_full() else build.mesh_pool(_model_objects_of(old_root, logic.Tree(scene)))
        new_root = build.build(cache_dir, scope=build.uid_scope(old_root), taken=build.used_uids(but=old_root),
                               reuse=pool, link=False)     # in the scene once the old model is taken apart (0324)
    except Exception as exc:
        _remove_new(before)
        raise UpdateFailed(f"the new revision could not be built ({exc or type(exc).__name__}). "
                           "Nothing was changed") from exc
    clock.lap("build new")
    st = _State(old_root, new_root, before)
    st.clock = clock
    from . import vessel_motion
    with vessel_motion.at_rest(scene):           # task 0085: joints are rebuilt from world places on a still sea
        try:
            out = _carry_over(context, st)
        except Exception as exc:
            if st.old_objs is None:            # past the point of no return (the old model is deleted)
                raise UpdateFailed(f"it failed after the old model was replaced ({exc or type(exc).__name__}). "
                                   "Check the model, or reopen the project without saving") from exc
            try:
                _roll_back(scene, st)
            except Exception as exc2:
                raise UpdateFailed(f"it failed ({exc or type(exc).__name__}) and could not be undone "
                                   f"({exc2 or type(exc2).__name__}). Reopen the project without saving") from exc
            raise UpdateFailed(f"it failed ({exc or type(exc).__name__}). The project is as it was before") from exc
    for n in vessel_motion.after_model_update(scene, st.mapping or {}):   # the new model moves with the vessel
        scene.fresing.report_notes.add().text = n
        out["notes"].append(n)
    if removed:                                  # task 0292: what Remove took out stays out
        from . import remove
        for n in remove.after_update(scene, removed, out.get("root")):
            scene.fresing.report_notes.add().text = n
            out["notes"].append(n)
    clock.lap("after")
    out["stages"] = clock.table()
    if out.get("root") is not None:
        out["root"]["fr_update_stats"] = json.dumps(out["stages"])
    title = scene.fresing.report_title
    for name in followers:                       # task 0293: the copies of a whole model follow it
        other = bpy.data.objects.get(name)
        if other is None:
            continue
        label = other.get(build.PROP_NAME, other.name)
        keep = [(x.text, x.uid) for x in scene.fresing.report_new], [(x.text, x.uid) for x in scene.fresing.report_missing], \
            [x.text for x in scene.fresing.report_notes]
        try:
            update_model(context, other, cache_dir, copies=False)
            n = f"The copy '{label}' was updated too"
        except UpdateFailed as exc:
            n = f"The copy '{label}' could not follow: {exc}"
        s = scene.fresing                        # the report stays the first model's, with a line per copy
        s.report_new.clear()
        s.report_missing.clear()
        s.report_notes.clear()
        for text, uid in keep[0]:
            line = s.report_new.add()
            line.text, line.uid = text, uid
        for text, uid in keep[1]:
            line = s.report_missing.add()
            line.text, line.uid = text, uid
        for text in keep[2]:
            s.report_notes.add().text = text
        s.report_notes.add().text = n
        s.report_title = title
        out["notes"].append(n)
    return out


def _set_up_hooks():
    from . import cylinders, gcode, linkages, machining, waycover
    return cylinders, gcode, linkages, machining, waycover


def _take_apart(scene, root) -> tuple:
    """Everything that hangs on the parts of the model under ``root`` comes apart (parts back in the CAD
    tree); returns the specs (cylinders, mechanisms, joints) to build it again."""
    cylinders, gcode, linkages, machining, _waycover = _set_up_hooks()
    from . import paths, section
    paths.before_model_update(scene, root)       # cables (task 0192): is it the same model that comes back?
    section.before_model_update(scene, root)     # cutaways (task 0086): their slide joints come off first
    machining.before_model_update(scene)         # milling (task 0027): the workpiece gets its CAD mesh back
    gcode.before_model_update(scene)             # CNC machine (task 0026): its marker and toolpath hang on parts
    # cylinders (task 0013) first: their pins hang on parts the joints move
    cyl_specs = cylinders.before_model_update(scene, root=root)
    mech_specs = linkages.before_model_update(scene, root=root)   # mechanisms (task 0014): links back in place
    specs = joints.dissolve_all(scene, root=root)       # joints of other models stay
    return cyl_specs, mech_specs, specs


def _put_together(scene, st, by_uid, mapping) -> list[str]:
    """Build joints, mechanisms and cylinders from the specs on the parts in ``by_uid``; the rest of the
    set-up follows. Returns notes for the report."""
    cylinders, gcode, linkages, machining, waycover = _set_up_hooks()
    notes = joints.rebuild_from_specs(scene, st.specs or [], by_uid)
    notes += linkages.rebuild_from_specs(scene, st.mech_specs or [], by_uid)  # after the joints: their input joint
    notes += cylinders.rebuild_from_specs(scene, st.cyl_specs or [], by_uid)  # after the joints: drive mode needs them
    notes += machining.after_model_update(scene, mapping, by_uid)
    notes += gcode.after_model_update(scene, mapping, by_uid)
    notes += waycover.after_joints_rebuilt(scene, mapping, by_uid)           # way covers (task 0034, 0035)
    from . import trails
    notes += trails.after_model_update(scene, by_uid, mapping)               # trail lines (task 0073)
    from . import section
    notes += section.after_model_update(scene, by_uid, mapping)              # cutaways (task 0086)
    from . import flex
    notes += flex.after_model_update(scene, by_uid, mapping)                 # hoses and drag chains (task 0058)
    from . import spool
    notes += spool.after_model_update(scene, by_uid, mapping)                # drums and carousels (task 0080)
    from . import paths
    notes += paths.after_model_update(scene, by_uid, mapping)                # cables and paths (task 0078)
    from . import tracks
    notes += tracks.after_model_update(scene, by_uid, mapping)               # tracks and belts (task 0079)
    from . import weather_sky
    notes += weather_sky.after_model_update(scene, mapping, by_uid)          # work lights (task 0109)
    from . import lifting
    notes += lifting.after_model_update(scene, by_uid, mapping)              # lifting loads (task 0214)
    return notes


def _roll_back(scene, st) -> None:
    """A step failed: take apart what was built on the new model, delete it, rebuild on the old model."""
    if st.rebuilding:
        _take_apart(scene, st.new_root)
        _repoint(scene, {n.name: o for o, n in st.pairs}, [])     # labels and sharp spots back
    _remove_new(st.before, st.new_root)
    _put_back(st.aside)
    bpy.context.view_layer.update()
    old = [ob for ob in st.old_objs]
    by_uid = joints.PartLookup()
    for o_uid, n_uid in st.mapping.items():          # settings that already took the new part's ID
        if not str(n_uid).startswith("gone:"):
            ob = next((x for x in old if x.get(build.PROP_UID) == o_uid), None)
            if ob is not None:
                by_uid[n_uid] = ob
    for ob in old:
        by_uid[ob.get(build.PROP_UID)] = ob
    if st.specs is not None or st.cyl_specs is not None or st.mech_specs is not None:
        _put_together(scene, st, by_uid, {})
    if st.decals_moved:
        from . import decals
        decals.sync([ob for ob in old if ob.type == "MESH" and ob.get(build.PROP_KIND) == "part"])
    if st.welds_undo is not None:
        st.welds_undo()
    logic.rebuild_tree(scene)


def _repoint(scene, by_name: dict, notes: list[str]) -> None:
    """Labels and cameras' sharp spots on parts of the old model go to the matching new part (task 0052)."""
    from . import cameras
    for sc in bpy.data.scenes:
        for c in sc.fresing.callouts:
            part = c.part
            if part is None or part.name not in by_name:
                continue
            new = by_name[part.name]
            if new is not None:
                c.part = new
            else:
                c.part = None
                notes.append(f"Label '{c.text.strip() or 'Label'}': its part "
                             f"'{part.get(build.PROP_NAME, part.name)}' is not in the new model, so it is left out "
                             f"of renders. Pick its point again ({places.where('labels')})")
    for ob in bpy.data.objects:
        if not ob.get(cameras.PROP_FOCUS):
            continue
        for con in list(ob.constraints):
            if con.type != "CHILD_OF" or con.target is None or con.target.name not in by_name:
                continue
            new = by_name[con.target.name]
            if new is not None:
                con.target = new
            else:                                   # the spot stays where it is now
                world = ob.matrix_world.copy()
                part = con.target.get(build.PROP_NAME, con.target.name)
                ob.constraints.remove(con)
                ob.matrix_world = world
                if cameras.PROP_FOCUS_PART in ob:
                    del ob[cameras.PROP_FOCUS_PART]
                notes.append(f"Sharp spot '{ob.name}': its part '{part}' is not in the new model; the spot stays "
                             "where it was (pick it again in 5 Scene & Render > Camera)")


def _carry_over(context, st) -> dict:
    scene = context.scene
    s = scene.fresing
    from . import animation, sequence
    sequence.end_preview(scene)          # parts an Assembly sequence preview moved are not free moves (0121)
    animation.clear_keys(scene)
    old_root, new_root = st.old_root, st.new_root
    lap = st.clock.lap
    lap("before")

    # 1. joints off (parts back in the CAD tree), remember free moves by part ID
    tree = logic.Tree(scene)
    old_objs = _model_objects_of(old_root, tree)
    st.old_objs = old_objs
    st.cyl_specs, st.mech_specs, st.specs = _take_apart(scene, old_root)
    old_set = {ob.name for ob in old_objs}
    deltas = {bpy.data.objects[n].get(build.PROP_UID): d for n, d in joints.free_moves(scene).items()
              if n in old_set}
    old_meshes = {ob.data for ob in old_objs if ob.type == "MESH" and ob.data is not None}
    old_collections = list(old_root.users_collection)
    lap("take apart")

    # 2. the new revision (built first, in update_model, outside the scene: taking the old model apart updates the
    #    scene again and again, and need not work out 10,000 new objects each time), placed where the old one was
    for col in new_root.users_collection:
        if col is not scene.collection and col.name not in scene.collection.children:
            scene.collection.children.link(col)
    new_root.matrix_basis = old_root.matrix_basis.copy()
    from . import copy as copy_mod
    kept_root = copy_mod.carry_root(old_root, new_root)     # task 0293: a copy keeps its group and name
    build.set_mat(new_root, build.PROP_REST_BASIS, build.rest_basis(old_root))
    tree = logic.Tree(scene)
    new_objs = _model_objects_of(new_root, tree)
    for ob in new_objs:
        ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
        if ob.get(build.PROP_KIND) == "assembly":
            ob[build.PROP_LOCKED] = True

    lap("place new")
    # 3. match
    old_recs, new_recs = records(old_objs), records(new_objs)
    lap("records")
    pairs = match(old_recs, new_recs)
    pairs += _made_root(old_recs, new_root, pairs)
    renamed = [f"{o['ob'].get(build.PROP_NAME, '')} is now called {n['ob'].get(build.PROP_NAME, '')}: same shape "
               "and place, it kept its work" for o, n in pairs if o.get("renamed")]      # task 0117
    renamed += _group_notes(pairs, 0.005)                                       # task 0237
    mapping = {old_root.get(build.PROP_UID): new_root.get(build.PROP_UID)}
    by_uid_new = joints.PartLookup({old_root.get(build.PROP_UID): new_root})
    for r in old_recs:                       # parts that are gone: their IDs must not hit a new part
        mapping[r["ob"].get(build.PROP_UID)] = "gone:" + r["ob"].get(build.PROP_UID, "")
    for o, n in pairs:
        mapping[o["ob"].get(build.PROP_UID)] = n["ob"].get(build.PROP_UID)
        by_uid_new[o["ob"].get(build.PROP_UID)] = n["ob"]
    st.mapping = mapping
    lap("match")

    # 4. carry over per-part settings
    pairs_ob = [(o["ob"], n["ob"]) for o, n in pairs] + [(old_root, new_root)]
    to_hide, to_exclude = [], []
    for ob_old, ob_new in pairs_ob:
        manual = ob_old.get("fr_group_manual")
        if manual:
            ob_new["fr_group_manual"] = manual
        if ob_old.get(build.PROP_EXCLUDED):
            to_exclude.append(ob_new)
        elif logic.is_hidden(ob_old):
            to_hide.append(ob_new)
        if ob_old.get(build.PROP_KIND) == "assembly" and not ob_old.get(build.PROP_LOCKED, True):
            logic.set_locked(ob_new, False, tree)
        if ob_old.get(build.BOUNDS_CAD):         # the model's size counts its CAD shape (a cable into the sea, a
            ob_new[build.BOUNDS_CAD] = True      # rider): lost, the sea and the cameras measured another model (0192)
        if "fr_tree_open" in ob_old:             # open/closed rows in 2 Structure
            ob_new["fr_tree_open"] = ob_old["fr_tree_open"]
        if ob_new is not new_root:
            from . import place                  # task 0292: a placed part stays placed in the new revision
            place.carry_over(ob_old, ob_new)
        d = deltas.get(ob_old.get(build.PROP_UID))
        if d is not None and ob_new is not new_root:
            ob_new.matrix_basis = build.rest_basis(ob_new) @ d
    if to_exclude:
        logic.exclude(to_exclude, True)
    for ob in to_hide:
        logic.set_hidden(ob, True, tree)
    lap("settings")
    lost_faces = faces.carry_over([(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"])
    from . import decals
    st.decals_moved = True
    decal_notes = decals.carry_over([(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"], old_objs)
    from . import welds                          # task 0319: welds find their faces again on the new parts
    weld_notes, st.welds_undo = welds.carry_over(scene, [(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"])
    from . import weld_cad                       # task 0323: welds from the CAD file follow the new model's beads
    cad_notes, cad_undo = weld_cad.carry_over(scene, [(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"],
                                              new_root)
    weld_notes = list(weld_notes) + cad_notes
    st.welds_undo = _both(st.welds_undo, cad_undo)
    lap("faces, decals, welds")

    matched_new = {id(n) for _o, n in pairs}
    matched_old = {id(o) for o, _n in pairs}
    new_parts = [r["ob"] for r in new_recs if id(r) not in matched_new and r["kind"] == "part"]
    missing = [(r["ob"].get(build.PROP_NAME, r["ob"].name), r["ob"].get(build.PROP_UID, ""))
               for r in old_recs if id(r) not in matched_old and r["kind"] == "part"]

    # 5. joints, mechanisms, cylinders and the rest of the set-up on the new model (the old one is still
    #    there: when this fails, it gets its set-up back)
    st.rebuilding = True
    st.aside = _set_aside(scene, old_collections, old_set)
    bpy.context.view_layer.update()
    lap("set aside")
    notes = _put_together(scene, st, by_uid_new, mapping)
    lap("joints and set-up")
    st.pairs = pairs_ob
    _repoint(scene, {o.name: n for o, n in pairs_ob}, notes)
    states.remap_uids(scene, mapping)
    lap("repoint")

    # 6. the old model goes (from here on there is no way back)
    st.old_objs = None
    matched = {o.name for o, _n in pairs_ob}
    _repoint(scene, {o.name: None for o in old_objs if o.name not in matched}, notes)   # their part is gone
    old_name = old_collections[0].name if old_collections else None
    bpy.data.batch_remove([ob for ob in old_objs])
    bpy.data.batch_remove([me for me in old_meshes if me.users == 0])  # one by one was quadratic (0131 row 15)
    from . import hover, mesh_import
    mesh_import.release_materials()              # the old revision's file materials (0131 row 4)
    hover.clear()                                # its meshes' names may come back on new meshes (0131 row 16c)
    aside, st.aside = st.aside, []
    for col in old_collections:
        if len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)
    _put_back([(c, p) for c, p in aside if _alive(c)])       # not emptied (a child collection): back in place
    if old_name and new_root.users_collection and old_name not in bpy.data.collections:
        new_root.users_collection[0].name = old_name
    copy_mod.after_root(new_root, kept_root)
    bpy.context.view_layer.update()
    lap("remove old")
    logic.apply_rules(scene)
    lap("sort")
    logic.rebuild_tree(scene)
    lap("structure list")
    logic.update_bounds(scene)
    from . import section
    section.sync(scene)                          # cutaways (task 0086): groups are known only now
    from . import world
    world.apply(scene, s)
    lap("bounds, surroundings")

    # 7. report
    s.report_new.clear()
    s.report_missing.clear()
    s.report_notes.clear()
    for ob in new_parts:
        line = s.report_new.add()
        line.text, line.uid = ob.get(build.PROP_NAME, ob.name), ob.get(build.PROP_UID, "")
    for name, uid in missing:
        line = s.report_missing.add()
        line.text, line.uid = name, uid
    for n in notes:
        s.report_notes.add().text = n
    for n in renamed:
        s.report_notes.add().text = n
    for name in lost_faces:
        s.report_notes.add().text = f"{name}: its faces changed, the faces painted on it are gone (paint them again)"
    for n in decal_notes:
        s.report_notes.add().text = n
    for n in weld_notes:
        s.report_notes.add().text = n
    kept = sum(1 for o, _n in pairs if o["kind"] == "part")
    s.report_title = f"Model updated: {plural(kept, 'part')} kept, {len(new_parts)} new, {len(missing)} missing"
    return {"kept": kept, "new": len(new_parts), "missing": len(missing), "notes": notes, "root": new_root}
