"""Scene logic used by operators and tests (no UI code here)."""

from __future__ import annotations

import math

import bpy
from mathutils import Matrix

from ..core import rules as R
from . import build, faces, materials

# ---------------------------------------------------------------------------
# rules <-> scene
# ---------------------------------------------------------------------------


def rules_from_scene(s) -> list[R.Rule]:
    return [R.Rule(r.target, r.field, r.op, r.value, r.enabled, r.note) for r in s.rules]


def load_rules_into_scene(s, rules: list[R.Rule]) -> None:
    s.rules.clear()
    for r in rules:
        item = s.rules.add()
        item.target, item.field, item.op, item.value, item.enabled, item.note = (
            r.target, r.field, r.op, r.value, r.enabled, r.note)
    s.rules_index = 0


def ensure_default_rules(s) -> bool:
    """For projects without a rule set (made before 0.2.13): default rules when there are none;
    a rule list that is still the untouched default of a version before 0.2.8 gets the new default
    list (part types, CAD materials). True if changed. A project with a rule set keeps its rules,
    also none at all (a rule set started empty)."""
    if getattr(s, "rule_set", ""):
        return False
    if len(s.rules) == 0:
        load_rules_into_scene(s, R.default_rules())
        return True
    new = R.upgraded_rules(rules_from_scene(s))
    if new is not None:
        load_rules_into_scene(s, new)
        return True
    return False


def facts_for_object(ob) -> R.PartFacts:
    asm = build.parent_assembly(ob)
    return R.facts_for(
        ob.get(build.PROP_NAME, ob.name),
        path=build.path_of(ob),
        color=ob.get(build.PROP_COLOR, ""),
        assembly=asm.get(build.PROP_NAME, asm.name) if asm else "",
        cad_material=ob.get(build.PROP_CAD_MATERIAL, ""),
    )


def start_look(s, name: str) -> tuple[str, str]:
    """The look a new group starts with: the one the project's rule set lists for it, else the
    built-in look for its name."""
    from . import rule_sets
    look = rule_sets.saved_looks(s).get(name)
    return look if look else R.default_material_for_group(name)


def ensure_group(s, name: str):
    g = s.groups.get(name)
    if g is None:
        g = s.groups.add()
        g.name = name
        g["_old_name"] = name
        mat_id, color = start_look(s, name)
        g.material = mat_id
        g.color = color
    return g


def sort_plan(scene, rules: list[R.Rule], aliases: dict, parts=None) -> dict:
    """Where the rules would put every part and face set, without changing anything.

    Returns {'parts': [...], 'groups': [group per part, hand choices included], 'counts': hits per
    rule, 'unmatched': n, 'per_group': {group: parts}, 'face_groups': {object name: [group per face
    set]}, 'per_face_group': {group: face sets}, 'by_rules': groups the rules fill (not by hand)}."""
    parts = list(build.iter_parts(scene)) if parts is None else parts
    facts = [facts_for_object(ob) for ob in parts]
    groups, counts, unmatched = R.classify(facts, rules)
    out: list[str] = []
    per_group: dict[str, int] = {}
    by_rules: set[str] = set()
    for ob, g in zip(parts, groups):
        g = aliases.get(g, g)                # groups the user renamed keep their new name
        manual = ob.get("fr_group_manual")
        if manual:
            g = manual
        else:
            by_rules.add(g)
        out.append(g)
        per_group[g] = per_group.get(g, 0) + 1
    new_group = {ob.name: g for ob, g in zip(parts, out)}
    face_groups, per_face_group = faces.plan(parts, rules, aliases, part_group=lambda ob: new_group[ob.name],
                                             rule_counts=counts, by_rules=by_rules)
    return {"parts": parts, "groups": out, "counts": counts, "unmatched": len(unmatched), "per_group": per_group,
            "face_groups": face_groups, "per_face_group": per_face_group, "by_rules": by_rules}


def apply_rules(scene) -> dict:
    """Sort every part into a material group and assign the group materials."""
    from . import rule_sets
    s = scene.fresing
    rule_sets.ensure(scene)
    plan = sort_plan(scene, rules_from_scene(s), {a.source: a.target for a in s.group_aliases})
    parts, counts, by_rules = plan["parts"], plan["counts"], plan["by_rules"]
    per_group, per_face_group = plan["per_group"], plan["per_face_group"]
    s.unmatched = plan["unmatched"]
    for ob, g in zip(parts, plan["groups"]):
        ob[build.PROP_GROUP] = g
    faces.write_groups(parts, plan["face_groups"])           # faces with a look of their own
    for i, c in enumerate(counts):
        s.rules[i].count = c
    for name in list(per_group) + list(per_face_group):
        ensure_group(s, name)
    for g in s.groups:
        g.count = per_group.get(g.name, 0)
        g.faces = per_face_group.get(g.name, 0)
        if g.by_rules != (g.name in by_rules):
            g.by_rules = g.name in by_rules
    mats = {g.name: materials.ensure_material(g.name, g.material, g.color, g.wear) for g in s.groups}
    for ob in parts:
        materials.assign(ob, mats[ob[build.PROP_GROUP]])
        faces.assign(ob, mats)
    return {"parts": len(parts), "groups": len(set(per_group) | set(per_face_group)),
            "unmatched": plan["unmatched"], "face_sets": sum(per_face_group.values())}


def refresh_group_materials(scene) -> None:
    s = scene.fresing
    mats = {g.name: materials.ensure_material(g.name, g.material, g.color, g.wear) for g in s.groups}
    for ob in build.iter_parts(scene):
        g = ob.get(build.PROP_GROUP)
        if g in mats:
            materials.assign(ob, mats[g])
        faces.assign(ob, mats)


def upgrade_looks(scene) -> int:
    """Rebuild the group materials made by an older version (task 0046: new looks), keeping every group's
    material, colour and wear. Returns how many were rebuilt."""
    s = scene.fresing
    old = 0
    for g in s.groups:
        mat = bpy.data.materials.get(materials.material_name(g.name))
        if mat is not None and not materials.is_current(mat, g.material, g.color, g.wear):
            old += 1
    if old:
        refresh_group_materials(scene)
    return old


def parts_in_group(scene, group: str):
    return [ob for ob in build.iter_parts(scene) if ob.get(build.PROP_GROUP) == group]


# ---------------------------------------------------------------------------
# paint schemes
# ---------------------------------------------------------------------------


def save_scheme(s, name: str):
    sch = s.schemes.get(name) or s.schemes.add()
    sch.name = name
    sch.looks.clear()
    for g in s.groups:
        look = sch.looks.add()
        look.group, look.material, look.color = g.name, g.material, g.color
    return sch


def apply_scheme(scene, name: str) -> int:
    s = scene.fresing
    sch = s.schemes.get(name)
    if sch is None:
        return 0
    n = 0
    for look in sch.looks:
        g = s.groups.get(look.group)
        if g is None:
            continue
        g.material = look.material
        g.color = look.color
        n += 1
    refresh_group_materials(scene)
    return n


# ---------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------


class Tree:
    """Parent -> children map built in one pass.

    ``Object.children`` scans every object in the file on each call, so walking a
    5,000-part assembly with it is quadratic. Build one Tree per operation instead.
    """

    def __init__(self, scene=None):
        scene = scene or bpy.context.scene
        self.kids: dict[str, list] = {}
        for ob in scene.objects:
            if ob.get(build.PROP_KIND) in build.JOINT_KINDS or ob.get(build.PROP_KIND) in ("decal", "cnc", "spool"):
                continue                       # joints, decals (0024), the CNC set-up's objects (0026), spools' (0080)
            p = build.logical_parent(ob)
            if p is not None:
                self.kids.setdefault(p.name, []).append(ob)

    def children(self, ob):
        return self.kids.get(ob.name, [])

    def descendants(self, ob):
        out = []
        stack = list(self.children(ob))
        while stack:
            c = stack.pop()
            out.append(c)
            stack.extend(self.children(c))
        return out


def descendants(ob, tree: Tree | None = None):
    return (tree or Tree()).descendants(ob)


def part_count(ob, tree: Tree | None = None) -> int:
    return sum(1 for d in descendants(ob, tree) if d.get(build.PROP_KIND) == "part")


def top_level(root, tree: Tree | None = None):
    """Skip single-child chains (e.g. a wrapper assembly around the whole machine)."""
    tree = tree or Tree()
    top = root
    while True:
        kids = tree.children(top)
        asm_children = [c for c in kids if c.get(build.PROP_KIND) == "assembly"]
        part_children = [c for c in kids if c.get(build.PROP_KIND) == "part"]
        if len(asm_children) == 1 and not part_children:
            top = asm_children[0]
        else:
            return top


def root_of(ob):
    while True:
        p = build.logical_parent(ob)
        if p is None:
            return ob
        ob = p


def subassembly_for_pick(ob, tree: Tree | None = None):
    """The subassembly a click on part ``ob`` should select (Inventor-like 'component priority')."""
    root = root_of(ob)
    top = top_level(root, tree)
    node = ob
    while node is not None:
        # walk the CAD chain part ... top ... root; pick the child of `top` on it
        p = build.logical_parent(node)
        if p is top:
            return node
        node = p
    return ob


def rebuild_tree(scene) -> None:
    """Rebuild the structure list (2 Structure): see tree.py."""
    from . import tree as tree_mod
    tree_mod.rebuild(scene)


def update_bounds(scene):
    """Recompute and cache the size of the visible model (used by the floor)."""
    s = scene.fresing
    try:
        bpy.context.view_layer.update()      # world matrices of freshly placed parts
    except Exception:
        pass
    parts = [ob for ob in build.iter_parts(scene) if ob.visible_get()] or list(build.iter_parts(scene))
    mn, mx = build.world_bounds(parts)
    s.bounds_min, s.bounds_max = mn.tolist(), mx.tolist()
    s.bounds_valid = bool(parts)
    return mn, mx


def cached_bounds(scene):
    import numpy as np
    s = scene.fresing
    if not s.bounds_valid:
        return update_bounds(scene)
    return np.array(s.bounds_min), np.array(s.bounds_max)


def set_locked(ob, locked: bool, tree: Tree | None = None) -> None:
    ob[build.PROP_LOCKED] = locked
    for target in [ob] + descendants(ob, tree):
        if target is not ob and target.get(build.PROP_KIND) == "assembly":
            continue  # children keep their own lock state
        target.lock_location = (locked,) * 3
        target.lock_rotation = (locked,) * 3
        target.lock_scale = (True,) * 3


def lock_all(scene) -> None:
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) in ("assembly", "part"):
            ob.lock_location = (True,) * 3
            ob.lock_rotation = (True,) * 3
            ob.lock_scale = (True,) * 3
            if ob.get(build.PROP_KIND) == "assembly":
                ob[build.PROP_LOCKED] = True


def set_visible_flags(ob, hidden: bool) -> None:
    """Hide/show in the view and the render. ``hide_set`` is slow on big scenes: only call it on a change."""
    try:
        if ob.hide_get() != hidden:
            ob.hide_set(hidden)
    except RuntimeError:
        pass
    if ob.hide_render != hidden:
        ob.hide_render = hidden


def set_hidden(ob, hidden: bool, tree: Tree | None = None) -> None:
    for target in [ob] + descendants(ob, tree):
        if target.get(build.PROP_EXCLUDED) and not hidden:
            continue
        set_visible_flags(target, hidden)
    ob["fr_hidden"] = hidden


def is_hidden(ob) -> bool:
    return bool(ob.get("fr_hidden", False))


def exclude(objs, excluded: bool = True) -> int:
    n = 0
    tree = Tree()
    seen = set()
    for ob in objs:
        targets = [ob] + tree.descendants(ob)
        for t in targets:
            if t.get(build.PROP_KIND) not in ("part", "assembly") or t.name in seen:
                continue
            seen.add(t.name)
            t[build.PROP_EXCLUDED] = excluded
            set_visible_flags(t, excluded)
            t.hide_select = excluded
            n += 1
    return n


def restore_excluded(scene) -> int:
    objs = [ob for ob in scene.objects if ob.get(build.PROP_EXCLUDED)]
    for ob in objs:
        ob[build.PROP_EXCLUDED] = False
        ob.hide_select = False
        set_visible_flags(ob, False)
    return len(objs)


def small_parts(scene, max_mm: float):
    limit = max_mm / 1000.0
    out = []
    for ob in build.iter_parts(scene):
        dims = ob.dimensions
        if max(dims) <= limit:
            out.append(ob)
    return out


def set_up_axis(root, axis: str) -> None:
    """Rotate the model root so the CAD 'up' axis points up in Blender."""
    if axis == "Y":
        root.matrix_basis = Matrix.Rotation(math.radians(90), 4, "X") @ root.matrix_basis
    build.set_mat(root, build.PROP_REST_BASIS, root.matrix_basis)   # turning the model is not a "free move"
