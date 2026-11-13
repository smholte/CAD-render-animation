"""Update the model to a new revision of the STEP file and keep all work.

Parts of the old and the new model are matched:
    1. by occurrence name path (Inventor "Frame:1" names), when those are unique
    2. by part name path, the nearest copy first (repeated bolts)
    3. by part name anywhere, when the part only moved to another subassembly
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
        self.rebuilding = False
        self.pairs: list = []                  # (old object, new object)
        self.aside: list = []                  # old collections out of the scene: (collection, parents)


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


def update_model(context, old_root, cache_dir: str) -> dict:
    """Replace ``old_root`` by the model in ``cache_dir``, keeping all work. Returns a summary.

    Raises ``UpdateFailed`` when it could not be done; the project is then as it was."""
    scene = context.scene
    before = {"objects": _names(bpy.data.objects), "meshes": _names(bpy.data.meshes),
              "collections": _names(bpy.data.collections)}
    build.ensure_bases(scene)
    # 1. the new revision first: when it cannot be read or built, nothing has changed yet
    try:
        # the new revision keeps the old one's part-ID scope (task 0056: the second copy of a STEP stays itself)
        new_root = build.build(cache_dir, scope=build.uid_scope(old_root), taken=build.used_uids(but=old_root))
    except Exception as exc:
        _remove_new(before)
        raise UpdateFailed(f"the new revision could not be built ({exc or type(exc).__name__}). "
                           "Nothing was changed") from exc
    st = _State(old_root, new_root, before)
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
    return out


def _set_up_hooks():
    from . import cylinders, gcode, linkages, machining, waycover
    return cylinders, gcode, linkages, machining, waycover


def _take_apart(scene, root) -> tuple:
    """Everything that hangs on the parts of the model under ``root`` comes apart (parts back in the CAD
    tree); returns the specs (cylinders, mechanisms, joints) to build it again."""
    cylinders, gcode, linkages, machining, _waycover = _set_up_hooks()
    from . import section
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
                             "of renders. Pick its point again (5 Scene & Render > Labels)")
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
    from . import animation
    animation.clear_keys(scene)
    old_root, new_root = st.old_root, st.new_root

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

    # 2. the new revision (built first, in update_model), placed where the old one was
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
    by_uid_new = joints.PartLookup({old_root.get(build.PROP_UID): new_root})
    for r in old_recs:                       # parts that are gone: their IDs must not hit a new part
        mapping[r["ob"].get(build.PROP_UID)] = "gone:" + r["ob"].get(build.PROP_UID, "")
    for o, n in pairs:
        mapping[o["ob"].get(build.PROP_UID)] = n["ob"].get(build.PROP_UID)
        by_uid_new[o["ob"].get(build.PROP_UID)] = n["ob"]
    st.mapping = mapping

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
    from . import decals
    st.decals_moved = True
    decal_notes = decals.carry_over([(o["ob"], n["ob"]) for o, n in pairs if o["kind"] == "part"], old_objs)

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
    notes = _put_together(scene, st, by_uid_new, mapping)
    st.pairs = pairs_ob
    _repoint(scene, {o.name: n for o, n in pairs_ob}, notes)
    states.remap_uids(scene, mapping)

    # 6. the old model goes (from here on there is no way back)
    st.old_objs = None
    matched = {o.name for o, _n in pairs_ob}
    _repoint(scene, {o.name: None for o in old_objs if o.name not in matched}, notes)   # their part is gone
    old_name = old_collections[0].name if old_collections else None
    bpy.data.batch_remove([ob for ob in old_objs])
    for me in old_meshes:
        if me.users == 0:
            bpy.data.meshes.remove(me)
    aside, st.aside = st.aside, []
    for col in old_collections:
        if len(col.objects) == 0 and len(col.children) == 0:
            bpy.data.collections.remove(col)
    _put_back([(c, p) for c, p in aside if _alive(c)])       # not emptied (a child collection): back in place
    if old_name and new_root.users_collection and old_name not in bpy.data.collections:
        new_root.users_collection[0].name = old_name
    bpy.context.view_layer.update()
    logic.apply_rules(scene)
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    from . import section
    section.sync(scene)                          # cutaways (task 0086): groups are known only now
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
    for n in decal_notes:
        s.report_notes.add().text = n
    kept = sum(1 for o, _n in pairs if o["kind"] == "part")
    s.report_title = f"Model updated: {plural(kept, 'part')} kept, {len(new_parts)} new, {len(missing)} missing"
    return {"kept": kept, "new": len(new_parts), "missing": len(missing), "notes": notes, "root": new_root}
