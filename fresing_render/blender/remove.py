"""Remove a model, a subassembly or parts (task 0292): 2 Structure > Place > Remove…, the 2 Structure box's Remove…,
the right-click menu's Remove… and – outside Full access – the Delete and X keys open the same window. It lists what
goes (``plan``); Remove takes it all out in one undo step (``remove``). Clean-up is something else: it only takes parts
out of the render and can bring them back (Restore all).

**How it works** – the model update's own path (``reimport.py``), with the chosen things as the parts that are
"gone":

1. Things that live on a part that goes are taken off first, by their own Remove (still with every object there):
   hoses and drag chains, cables, drums and carousels, tracks, trail lines, labels, logos and stickers.
2. Animation steps that only move what goes (a joint, cylinder or mechanism that goes; Show / Hide / Fade / Take
   apart / Back to CAD of a part that goes) are taken off. A pose step, a Back to CAD of everything and a joint
   that keeps other parts stay – they lose only that part.
3. Per model that loses something: its joints, cylinders and mechanisms come apart (``reimport._take_apart``); what
   goes leaves the scene but stays alive; the set-up is built again on what stays (``reimport._put_together`` with
   every part that goes mapped to "gone:"); labels and sharp spots let go of it, poses and saved scenes keep working
   (their entries of the gone parts are kept as "gone:" and do nothing); then the objects are deleted.

The import cache stays: 1 Import > Imported models can bring a removed model back. Undo (Ctrl+Z) brings everything
back as it was (one step: the operator's).
"""

from __future__ import annotations

import bpy

from ..core import place as core
from ..core.words import plural
from . import build, logic

LAST: dict = {}                    # the last remove's result (tests, the PC check)


def _uid(ob) -> str:
    return str(ob.get(build.PROP_UID, "") or "")


def chosen(scene, objs) -> list:
    """The model objects chosen, without the ones below another chosen one (in the CAD structure)."""
    objs = [o for o in objs if o is not None and o.get(build.PROP_KIND) in build.MODEL_KINDS
            and o.name in scene.objects]
    names = {o.name for o in objs}
    out = []
    for ob in objs:
        p = build.logical_parent(ob)
        while p is not None and p.name not in names:
            p = build.logical_parent(p)
        if p is None and ob not in out:
            out.append(ob)
    return out


def gone_objects(scene, objs, tree=None) -> list:
    """Every model object that goes: the chosen ones and everything below them in the CAD structure."""
    tree = tree or logic.Tree(scene)
    out, seen = [], set()
    for ob in chosen(scene, objs):
        for o in [ob] + tree.descendants(ob):
            if o.name not in seen and o.get(build.PROP_KIND) in build.MODEL_KINDS:
                seen.add(o.name)
                out.append(o)
    return out


def _refs(coll) -> list:
    return [r.obj for r in coll if getattr(r, "obj", None) is not None]


# ---------------------------------------------------------------------------
# what goes (the window's list)
# ---------------------------------------------------------------------------

def plan(scene, objs) -> dict:
    """What a Remove of ``objs`` takes with it: counts under the keys of ``core.place.GOES``, the indices of the items
    to take off (``"_flex"`` …), the names of the joints / cylinders / mechanisms that go, and the lines of what only
    loses something (``"loses"``)."""
    from . import joints
    s = scene.fresing
    tree = logic.Tree(scene)
    top = chosen(scene, objs)
    gone = gone_objects(scene, top, tree)
    names = {o.name for o in gone}
    uids = {_uid(o) for o in gone if _uid(o)}
    out: dict = {"names": [o.get(build.PROP_NAME, o.name) for o in top], "objects": [o.name for o in top],
                 "models": sum(1 for o in top if o.get(build.PROP_ROOT)),
                 "subassemblies": sum(1 for o in top if not o.get(build.PROP_ROOT)
                                      and o.get(build.PROP_KIND) == "assembly"),
                 "parts": sum(1 for o in gone if o.get(build.PROP_KIND) == "part" and o.type == "MESH"),
                 "loses": [], "gone_names": sorted(names), "gone_uids": sorted(uids)}
    roots = []
    for o in top:
        r = build.model_root_of(o)
        if r is not None and r not in roots:
            roots.append(r)
    out["roots"] = [r.name for r in roots]

    # joints
    j_gone, loses = [], out["loses"]
    for j in s.joints:
        mem = joints.members(j)
        if not mem:
            continue
        inside = [m for m in mem if m.name in names]
        if len(inside) == len(mem):
            j_gone.append(j.name)
        elif inside:
            loses.append(f"Joint '{j.name}' keeps moving {plural(len(mem) - len(inside), 'other part')} "
                         f"({plural(len(inside), 'part')} of it {'goes' if len(inside) == 1 else 'go'})")
    out["joints"], out["_joints"] = len(j_gone), j_gone

    def all_gone(objs_) -> bool:
        return bool(objs_) and all(o.name in names for o in objs_)

    def any_gone(objs_) -> bool:
        return any(o.name in names for o in objs_)

    cyl = [c.name for c in s.cylinders if all_gone(_refs(c.barrel)) or all_gone(_refs(c.rod))]
    for c in s.cylinders:
        if c.name not in cyl and (any_gone(_refs(c.barrel)) or any_gone(_refs(c.rod))):
            loses.append(f"Cylinder '{c.name}' loses some of its parts")
    out["cylinders"], out["_cylinders"] = len(cyl), cyl
    mech = [m.name for m in s.mechanisms if any(any_gone(_refs(lk.objs)) for lk in m.links)]
    out["mechanisms"], out["_mechanisms"] = len(mech), mech
    covers = []
    for i, w in enumerate(getattr(s, "waycovers", ())):
        secs = [sec.joint for sec in getattr(w, "sections", ()) if getattr(sec, "joint", "")]
        if secs and all(n in j_gone for n in secs):
            covers.append(i)
    out["way_covers"], out["_covers"] = len(covers), covers

    def by_uid(coll, *fields) -> list:
        idx = []
        for i, it in enumerate(coll):
            for f in fields:
                v = getattr(it, f, "")
                if v and v in uids:
                    idx.append(i)
                    break
        return idx

    out["_flex"] = by_uid(s.flex, "part_uid")
    for i, it in enumerate(s.flex):          # a drawn hose (task 0240): the app's own object, between two parts
        if i not in out["_flex"] and getattr(it, "drawn", False) and (
                getattr(it, "a_uid", "") in uids or getattr(it, "b_uid", "") in uids):
            out["_flex"].append(i)
    out["hoses"] = len(out["_flex"])
    out["_cables"] = by_uid(s.cables, "part_uid")
    out["cables"] = len(out["_cables"])
    out["_spools"] = by_uid(s.spools, "part_uid")
    out["spools"] = len(out["_spools"])
    tracks = []
    for i, t in enumerate(s.tracks):
        used = {getattr(t, "chain_uid", "")} | {getattr(w, "part_uid", "") for w in getattr(t, "wheels", ())}
        if used & uids:
            tracks.append(i)
    out["_tracks"], out["tracks"] = tracks, len(tracks)
    out["_trails"] = by_uid(s.trails, "part_uid")
    labels = [i for i, c in enumerate(s.callouts) if c.part is not None and c.part.name in names]
    out["_labels"], out["labels"] = labels, len(labels)
    decals = [o.name for o in scene.objects if o.get(build.PROP_KIND) == "decal" and o.parent is not None
              and o.parent.name in names]
    out["_decals"], out["decals"] = decals, len(decals)

    # animation steps
    steps = []
    for a, anim in enumerate(s.animations):
        for b, blk in enumerate(anim.blocks):
            if _step_goes(blk, j_gone, cyl, mech, uids):
                steps.append((a, b))
            elif blk.kind == "CAMERA" and (blk.target_uid in uids or blk.aim_uid in uids):
                loses.append(f"Camera step '{blk.name or anim.name}' looked at or rode on it: pick its part again")
    out["_steps"], out["steps"] = steps, len(steps)
    return out


def _step_goes(blk, j_gone, cyl, mech, uids) -> bool:
    k = blk.kind
    if k in ("JOINT", "MOTOR"):
        return bool(blk.joint) and blk.joint in j_gone
    if k == "CYLINDER":
        return bool(blk.cylinder) and blk.cylinder in cyl
    if k == "MECHANISM":
        return bool(blk.mechanism) and blk.mechanism in mech
    if k in ("SHOW", "HIDE", "FADE_IN", "FADE_OUT", "SEQUENCE"):
        return bool(blk.target_uid) and blk.target_uid in uids
    if k == "CAD":
        return not blk.cad_whole and bool(blk.target_uid) and blk.target_uid in uids
    return False


def lines(p: dict) -> list:
    """The window's lines (``core.place.summary``) and what stays."""
    out = core.summary(p)
    out.append("Saved poses and scenes keep working. The import stays: 1 Import > Imported models brings a model "
               "back. Ctrl+Z undoes it")
    return out


# ---------------------------------------------------------------------------
# the remove itself
# ---------------------------------------------------------------------------

def _take_off_items(scene, p: dict) -> None:
    """Step 1: what lives on a part that goes, by its own Remove (highest index first: the lists shift)."""
    from . import flex, paths, spool, tracks, trails
    for module, key in ((flex, "_flex"), (paths, "_cables"), (spool, "_spools"), (tracks, "_tracks"),
                        (trails, "_trails")):
        for i in sorted(p.get(key, ()), reverse=True):
            try:
                module.remove(scene, i)
            except Exception as exc:  # noqa: BLE001 - one item that cannot come off never stops the rest
                print(f"Fresing Render: Remove: {module.__name__} item {i} not taken off:", exc)
    from . import waycover
    for i in sorted(p.get("_covers", ()), reverse=True):
        try:
            waycover.remove_cover(scene, i)
        except Exception as exc:  # noqa: BLE001
            print(f"Fresing Render: Remove: way cover {i} not taken off:", exc)
    s = scene.fresing
    for i in sorted(p.get("_labels", ()), reverse=True):
        if i < len(s.callouts):
            s.callouts.remove(i)
    s.callouts_index = max(0, min(s.callouts_index, len(s.callouts) - 1))
    decals = [bpy.data.objects[n] for n in p.get("_decals", ()) if n in bpy.data.objects]
    if decals:
        bpy.data.batch_remove(decals)
    by_anim: dict = {}
    for a, b in p.get("_steps", ()):
        by_anim.setdefault(a, []).append(b)
    for a, bs in by_anim.items():
        if a < len(s.animations):
            anim = s.animations[a]
            for b in sorted(bs, reverse=True):
                if b < len(anim.blocks):
                    anim.blocks.remove(b)
            anim.blocks_index = max(0, min(anim.blocks_index, len(anim.blocks) - 1))


def _out_of_scene(objs) -> object:
    """Take objects out of every collection of the scene but keep them alive (in a collection of their own that is
    in no scene): the set-up is built again on what stays while hooks may still read them."""
    hold = bpy.data.collections.new("FR removing")
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        hold.objects.link(o)
    return hold


def remove(scene, objs) -> dict:
    """Remove ``objs`` (models, subassemblies, parts) with everything that lives on them. Returns the plan with
    ``"notes"`` (what the rebuild said)."""
    from . import animation, joints, reimport, sequence, states, vessel_motion
    p = plan(scene, objs)
    if not p["objects"]:
        return p
    sequence.end_preview(scene)
    animation.clear_keys(scene)
    _take_off_items(scene, p)
    notes: list = []
    tree = logic.Tree(scene)
    gone_names = set(p["gone_names"])
    mapping_all: dict = {}
    cols_before = {c.name for c in bpy.data.collections}
    with vessel_motion.at_rest(scene):
        for root_name in p["roots"]:
            root = bpy.data.objects.get(root_name)
            if root is None:
                continue
            model = reimport._model_objects_of(root, tree)
            st = reimport._State(root, root, None)
            st.cyl_specs, st.mech_specs, st.specs = reimport._take_apart(scene, root)
            kept = [o for o in model if o.name not in gone_names]
            goners = [o for o in model if o.name in gone_names]
            mapping = {_uid(o): _uid(o) for o in kept if _uid(o)}
            mapping.update({_uid(o): "gone:" + _uid(o) for o in goners if _uid(o)})
            by_uid = joints.PartLookup({_uid(o): o for o in kept if _uid(o)})
            cols = list(root.users_collection) if root.name in gone_names else []
            hold = _out_of_scene(goners)
            bpy.context.view_layer.update()
            notes += reimport._put_together(scene, st, by_uid, mapping)
            reimport._repoint(scene, {o.name: None for o in goners}, notes)
            states.remap_uids(scene, mapping)
            meshes = {o.data for o in goners if o.type == "MESH" and o.data is not None}
            others = [o for o in bpy.data.objects if o.parent is not None and o.parent in set(goners)
                      and o not in set(goners) and o.get(build.PROP_KIND) == "decal"]
            bpy.data.batch_remove(goners + others)
            orphans = [me for me in meshes if me.users == 0]
            if orphans:
                bpy.data.batch_remove(orphans)
            bpy.data.collections.remove(hold)
            for c in cols:
                try:
                    if len(c.objects) == 0 and len(c.children) == 0:
                        bpy.data.collections.remove(c)
                except ReferenceError:
                    pass
            mapping_all.update(mapping)
    for c in [c for c in bpy.data.collections if c.name not in cols_before]:
        if c.name.startswith("FR removing") and not len(c.objects):
            bpy.data.collections.remove(c)
    notes += vessel_motion.after_model_update(scene, mapping_all) or []
    _tidy(scene)
    p["notes"] = notes
    LAST.clear()
    LAST.update(p)
    return p


def _tidy(scene) -> None:
    """What a model update does at its end: the tree, the bounds, cutaways, the surroundings."""
    from . import hover, mesh_import, section, world
    try:
        mesh_import.release_materials()
    except Exception:  # noqa: BLE001
        pass
    hover.clear()
    bpy.context.view_layer.update()
    logic.drop_tree_cache()
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    try:
        section.sync(scene)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: Remove: cutaways not synced:", exc)
    world.apply(scene, scene.fresing)
    scene.fresing.bounds_valid = False
