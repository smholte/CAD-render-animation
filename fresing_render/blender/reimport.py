"""Update the model to a new revision of the STEP file and keep all work.

Parts of the old and the new model are matched:
    1. by occurrence name path (Inventor "Frame:1" names), when those are unique
    2. by part name path, the nearest copy first (repeated bolts)
    3. by part name anywhere, when the part only moved to another subassembly
Matched parts keep: manual material group, hidden / removed, unlocked, free moves,
joints (moving parts and the part they sit on), poses, visibility sets, scenes and
animation targets, and painted faces when the part's faces did not change. New and missing
parts, and parts that lost painted faces, are listed in a report.
"""

from __future__ import annotations

import re

import bpy
from mathutils import Matrix

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
            "kind": ob.get(build.PROP_KIND),
            "key_a": tuple(inst) if all(inst) else None,
            "key_b": tuple(_norm(c.get(build.PROP_NAME, c.name)) for c in chain),
            "leaf": _norm(ob.get(build.PROP_NAME, ob.name)),
            "pos": cad_matrix(ob).translation.copy(),
        })
    return out


def _candidates(olds: list[dict], news: list[dict], k: int = 8) -> list[tuple[float, int, int]]:
    """(distance, old index, new index) pairs, nearest first. Big groups (1,000 identical bolts)
    use a k-d tree and only the k nearest neighbours instead of every pair."""
    if len(olds) * len(news) <= 40000:
        return sorted(((o["pos"] - n["pos"]).length, i, j) for i, o in enumerate(olds) for j, n in enumerate(news))
    from mathutils.kdtree import KDTree
    tree = KDTree(len(news))
    for j, n in enumerate(news):
        tree.insert(n["pos"], j)
    tree.balance()
    cand = []
    for i, o in enumerate(olds):
        for _co, j, dist in tree.find_n(o["pos"], min(k, len(news))):
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

    # 2. name path, nearest first; 3. same name anywhere, only if it did not move
    for key, tol in ((lambda r: (r["kind"], r["key_b"]), None), (lambda r: (r["kind"], r["leaf"]), move_tolerance)):
        go = by(key, [r for r in old if id(r) not in used_old])
        gn = by(key, [r for r in new if id(r) not in used_new])
        for k, olds in go.items():
            news = gn.get(k, [])
            if not news:
                continue
            if tol is None and len(olds) == 1 and len(news) == 1:
                take(olds[0], news[0])
                continue
            while True:                      # repeat: the k-d tree only offers the nearest few
                rem_o = [o for o in olds if id(o) not in used_old]
                rem_n = [n for n in news if id(n) not in used_new]
                if not rem_o or not rem_n:
                    break
                progress = False
                for dist, i, j in _candidates(rem_o, rem_n):
                    o, n = rem_o[i], rem_n[j]
                    if id(o) in used_old or id(n) in used_new:
                        continue
                    if tol is not None and dist > tol:
                        break
                    take(o, n)
                    progress = True
                if not progress or tol is not None:
                    break
    return pairs


def _model_objects_of(root, tree) -> list:
    return [root] + [d for d in tree.descendants(root) if d.get(build.PROP_KIND) in build.MODEL_KINDS]


def update_model(context, old_root, cache_dir: str) -> dict:
    """Replace ``old_root`` by the model in ``cache_dir``, keeping all work. Returns a summary."""
    scene = context.scene
    s = scene.fresing
    from . import animation
    animation.clear_keys(scene)

    # 1. joints off (parts back in the CAD tree), remember free moves by part ID
    build.ensure_bases(scene)
    specs = joints.dissolve_all(scene, root=old_root)       # joints of other models stay
    tree = logic.Tree(scene)
    old_objs = _model_objects_of(old_root, tree)
    old_set = {ob.name for ob in old_objs}
    deltas = {bpy.data.objects[n].get(build.PROP_UID): d for n, d in joints.free_moves(scene).items()
              if n in old_set}
    old_meshes = {ob.data for ob in old_objs if ob.type == "MESH" and ob.data is not None}
    old_collections = list(old_root.users_collection)

    # 2. the new revision, placed where the old one was
    new_root = build.build(cache_dir)
    new_root.matrix_basis = old_root.matrix_basis.copy()
    build.set_mat(new_root, build.PROP_REST_BASIS, build.rest_basis(old_root))
    tree = logic.Tree(scene)
    new_objs = _model_objects_of(new_root, tree)
    for ob in new_objs:
        ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
        if ob.get(build.PROP_KIND) == "assembly":
            ob[build.PROP_LOCKED] = True

    # 3. match
    old_recs, new_recs = records(old_objs), records(new_objs)
    pairs = match(old_recs, new_recs)
    mapping = {old_root.get(build.PROP_UID): new_root.get(build.PROP_UID)}
    by_uid_new = {old_root.get(build.PROP_UID): new_root}
    for r in old_recs:                       # parts that are gone: their IDs must not hit a new part
        mapping[r["ob"].get(build.PROP_UID)] = "gone:" + r["ob"].get(build.PROP_UID, "")
    for o, n in pairs:
        mapping[o["ob"].get(build.PROP_UID)] = n["ob"].get(build.PROP_UID)
        by_uid_new[o["ob"].get(build.PROP_UID)] = n["ob"]

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
        if "fr_tree_open" in ob_old:             # open/closed rows in 2 Structure
            ob_new["fr_tree_open"] = ob_old["fr_tree_open"]
        d = deltas.get(ob_old.get(build.PROP_UID))
        if d is not None and ob_new is not new_root:
            ob_new.matrix_basis = build.rest_basis(ob_new) @ d
    if to_exclude:
        logic.exclude(to_exclude, True)
    for ob in to_hide:
        logic.set_hidden(ob, True, tree)
    lost_faces = faces.carry_over([(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"])

    matched_new = {id(n) for _o, n in pairs}
    matched_old = {id(o) for o, _n in pairs}
    new_parts = [r["ob"] for r in new_recs if id(r) not in matched_new and r["kind"] == "part"]
    missing = [(r["ob"].get(build.PROP_NAME, r["ob"].name), r["ob"].get(build.PROP_UID, ""))
               for r in old_recs if id(r) not in matched_old and r["kind"] == "part"]

    # 5. the old model goes
    old_name = old_collections[0].name if old_collections else None
    bpy.data.batch_remove([ob for ob in old_objs])
    for me in old_meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    for col in old_collections:
        if len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)
    if old_name and new_root.users_collection and old_name not in bpy.data.collections:
        new_root.users_collection[0].name = old_name
    bpy.context.view_layer.update()

    # 6. joints, saved states and the rest of the set-up
    notes = joints.rebuild_from_specs(scene, specs, by_uid_new)
    states.remap_uids(scene, mapping)
    logic.apply_rules(scene)
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    from . import world
    world.apply(scene, s)

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
    for name in lost_faces:
        s.report_notes.add().text = f"{name}: its faces changed, the faces painted on it are gone (paint them again)"
    kept = sum(1 for o, _n in pairs if o["kind"] == "part")
    s.report_title = f"Model updated: {plural(kept, 'part')} kept, {len(new_parts)} new, {len(missing)} missing"
    return {"kept": kept, "new": len(new_parts), "missing": len(missing), "notes": notes, "root": new_root}
