"""Copy and paste a model, a subassembly or parts with its joints and mechanisms (task 0293; the Place lane).

**Copy** (right-click > Copy, 2 Structure > Place > Copy, Ctrl+C outside Full access) remembers what is selected;
**Paste** (right-click > Paste here, Place > Paste, Ctrl+V) makes the copy – one undo step – puts it beside the
original (or, with Paste here, where the mouse was) and opens Place (0292) for it, with a line of what came along and
what was left out.

**What comes along** (all built again on the copy by the same code a model update uses):

* the parts – their meshes are *shared* with the original (linked data: the project hardly grows), their looks,
  groups, hidden / cleaned-up state and locks;
* joints whose moving parts are all in the copy, with their limits, values and couplings to joints that are also in
  the copy (``joints.to_specs`` -> ``joints.rebuild_from_specs`` with every part ID mapped to its copy's);
* cylinders whose barrel, rod and both pins' parts are in the copy; mechanisms whose links and base are in it;
* way covers whose axis and section joints came along; hoses and drag chains whose part and both ends are in the copy
  (read again from the copied part, as a model update does); labels on its parts; logos and stickers; welds whose
  two parts are both in the copy (task 0320; a weld with one part outside is left out and said).

**The rule for what reaches outside the copy** (said in the Place window after a paste): it is *left out* – the copy
moves by itself. A joint that also moves parts outside the copy, a cylinder or hose with a pin or end outside, and a
coupling to a joint outside the copy are not copied (the copied joint then moves by itself). A joint that sat on a
part or joint outside the copy sits on the copy itself. A cable read from CAD whose parts, wheels and ends are all in
the copy comes along with its drum (task 0374: read again on the copied parts); drawn cables, cables into the sea,
tracks, trail lines, animation steps and cameras stay with the original (add them again on the copy).

**Names**: the copy of a model, subassembly or parts is "<name> (2)", "(3)" …; so are its joints, cylinders,
mechanisms, way covers and hoses. Its part IDs get a scope of their own (``~N/…``, as a second import of the same STEP,
task 0056), so material rules and part-name rules treat it as the original.

**A model update** (the rule of the brief, point 3): a copy of a **whole model** is a second instance of the same
model: it keeps the original's STEP file and import (``fr_source``, ``fr_cache``), and when either of them is updated
to a new revision the others of its copy group (``GROUP``) are updated too, each keeping its own work and place. A
copy of a **subassembly or parts** becomes a model of its own (a new top row in 2 Structure) with its own parts: it is
*frozen* (``FROZEN``) – a model update of the original leaves it as it is, and it cannot be updated itself.
"""

from __future__ import annotations

import json
import re
import uuid

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

from ..core.words import plural
from . import build, joints, logic

CLIP = {"names": [], "uids": [], "scene": ""}   # what Copy remembered (object names, their part IDs)
LAST: dict = {}                        # the last paste's result (tests, the PC check, the Place window's note)
NOTE = [""]                            # the last Copy / Paste message
GROUP = "fr_copy_group"                # on model roots: a whole model and its copies (a model update updates them all)
FROZEN = "fr_copy_frozen"              # on the root of a copied subassembly / parts: frozen, no model update
COPY_OF = "fr_copy_of"                 # on a copy's root: the name of what it was copied from
_NUM = re.compile(r"^(.*?) \((\d+)\)$")

# object properties that tie an object to the original's set-up: never on a copy (made again where it comes along)
_STRIP = (build.PROP_CAD_PARENT, "fr_cable", "fr_track", "fr_spool", "fr_mill_hid", "fr_cnc_carry", "fr_cv_hide",
          "fr_place_frame")
_FLEX_TAGS = ("fr_flex", "fr_flex_local", "fr_flex_guide_a", "fr_flex_guide_b")   # kept where the hose comes along
_ROOT_STRIP = ("fr_lift_groups", "fr_lifting")


def remember(scene, objs) -> None:
    """Copy: remember these objects (by name) for Paste. Opening a project or a new one forgets them (``_on_load``),
    so a Paste never takes objects of the same name in another project; Ctrl+Z keeps them."""
    CLIP["names"] = [o.name for o in objs]
    CLIP["uids"] = [_uid(o) for o in objs]      # a model update makes new objects: found again by their part IDs
    CLIP["scene"] = scene.name


@persistent
def _on_load(_dummy=None):
    CLIP["names"], CLIP["uids"], CLIP["scene"] = [], [], ""
    LAST.clear()


def register():
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)


def _name(ob) -> str:
    return str(ob.get(build.PROP_NAME) or ob.name)


def _uid(ob) -> str:
    return str(ob.get(build.PROP_UID, "") or "")


def next_name(base: str, taken) -> str:
    """``base`` numbered: "Boom" -> "Boom (2)"; "Boom (2)" -> "Boom (3)" – the lowest number not in ``taken``."""
    m = _NUM.match(base or "")
    stem = m.group(1) if m else (base or "Copy")
    taken = set(taken)
    n = 2
    while f"{stem} ({n})" in taken:
        n += 1
    return f"{stem} ({n})"


# ---------------------------------------------------------------------------
# what is copied
# ---------------------------------------------------------------------------

def groups(scene, objs) -> list:
    """The chosen things per model: [{"root": the original's model root, "whole": a whole model, "top": the chosen
    objects}]. A whole model and parts of another model give two copies."""
    from . import remove
    top = remove.chosen(scene, [o for o in objs if o is not None])
    out: list = []
    for ob in top:
        root = build.model_root_of(ob)
        if root is None:
            continue
        if ob is root:
            out.append({"root": root, "whole": True, "top": [ob]})
            continue
        g = next((x for x in out if x["root"] is root and not x["whole"]), None)
        if g is None:
            g = {"root": root, "whole": False, "top": []}
            out.append(g)
        g["top"].append(ob)
    return out


def _objects(scene, g, tree) -> list:
    """Every model object of a group, parents before children."""
    out, seen = [], set()
    for t in g["top"]:
        for o in [t] + tree.descendants(t):
            if o.name not in seen and o.get(build.PROP_KIND) in build.MODEL_KINDS:
                seen.add(o.name)
                out.append(o)

    def depth(o):
        d, p = 0, build.logical_parent(o)
        while p is not None:
            d, p = d + 1, build.logical_parent(p)
        return d
    return sorted(out, key=depth)


def _refs(coll) -> list:
    return [r.obj for r in coll if getattr(r, "obj", None) is not None]


def _inside(ob, names) -> bool:
    """``ob`` is one of the copied objects (or a joint empty of a joint that comes along: never – those are made)."""
    return ob is not None and ob.name in names


def _select(scene, objs_in, names, out: dict) -> None:
    """Which items of the set-up come along (their names / indices in ``out``) and the lines of what is left out."""
    from . import cylinders, linkages
    s = scene.fresing
    left = out["left"]
    uids_in = {_uid(o) for o in objs_in if _uid(o)}
    remade = {it.name for it in s.cables if _cable_stays(it, uids_in) is None}       # (task 0374: read again)
    remade_j = {it.joint for it in s.cables if it.name in remade and it.joint}
    # joints: every moving part in the copy; a joint made by a cable or track belongs to it (not copied with it)
    j_in = []
    for j in s.joints:
        if not joints.is_valid(j):
            continue
        mem = joints.members(j)
        if not mem:
            continue
        inside = [m for m in mem if m.name in names]
        if len(inside) == len(mem):
            if j.motion is not None and (j.motion.get("fr_cable") or j.motion.get("fr_track")):
                if j.motion.get("fr_cable") not in remade:          # (a cable read again makes its own)
                    left.append(f"Joint '{j.name}' belongs to a cable or track, which is not copied")
                continue
            j_in.append(j.name)
        elif inside:
            left.append(f"Joint '{j.name}' also moves parts outside the copy: not copied (the copied "
                        f"{'part stands' if len(inside) == 1 else 'parts stand'} still)")
    changed = True                          # a joint that moves nothing itself but carries joints of the copy
    while changed:
        changed = False
        for j in s.joints:
            if j.name in j_in or joints.members(j) or not joints.is_valid(j):
                continue
            riders = joints.all_riders(scene, j)
            if riders and all(r.name in j_in for r in riders):
                j_in.append(j.name)
                changed = True
    out["_joints"] = [j.name for j in s.joints if j.name in j_in]          # in the list's order
    for name in out["_joints"]:
        j = joints.find(scene, name)
        if j.follows and j.follows not in j_in and j.follows not in remade_j:   # (a cable read again couples it)
            left.append(f"Joint '{name}' follows '{j.follows}', which is not in the copy: its copy moves by itself")
    # cylinders: barrel, rod, stages and both pins' parts in the copy
    cyl = []
    for c in s.cylinders:
        if not cylinders.is_valid(c):
            continue
        parts = cylinders.barrel_objs(c) + cylinders.rod_objs(c) + cylinders.stage_objs(c)
        carriers = [c.frame.parent, c.pin.parent]
        if parts and all(o.name in names for o in parts) and all(_inside(o, names) for o in carriers):
            cyl.append(c.name)
        elif any(o.name in names for o in parts) or any(_inside(o, names) for o in carriers):
            left.append(f"Cylinder '{c.name}' has a part or pin outside the copy: not copied")
    out["_cylinders"] = cyl
    mech = []
    for m in s.mechanisms:
        if not linkages.is_valid(m):
            continue
        objs = linkages.all_link_objs(m) + ([m.base] if m.base is not None else [])
        if objs and all(o.name in names for o in objs):
            mech.append(m.name)
        elif any(o.name in names for o in objs):
            left.append(f"Mechanism '{m.name}' has links outside the copy: not copied")
    out["_mechanisms"] = mech
    covers = []
    for i, w in enumerate(getattr(s, "waycovers", ())):
        secs = [sec.joint for sec in w.sections if sec.joint]
        carriage = [o for sec in w.sections if sec.carriage for o in _refs(sec.parts)]
        if w.axis and w.axis in j_in and secs and all(n in j_in for n in secs) and all(o.name in names
                                                                                       for o in carriage):
            covers.append(i)
        elif any(n in j_in for n in secs):
            left.append(f"Way cover '{w.name}': its axis or some sections are outside the copy: not copied")
    out["_covers"] = covers
    flex = []
    for i, it in enumerate(s.flex):
        parts = [it.part] if (it.kind == "HOSE" or it.made_links) else _refs(it.links)
        ends = [it.a_part, it.b_part]
        touch = [o for o in parts + ends if o is not None and o.name in names]
        if not touch:
            continue
        if not it.drawn and parts and all(_inside(o, names) for o in parts + ends):
            flex.append(i)
        else:
            left.append(f"{'Drag chain' if it.kind == 'CHAIN' else 'Hose'} '{it.name}': "
                        + ("drawn in the app – not copied" if it.drawn else "an end is outside the copy – not copied"))
    out["_flex"] = flex
    out["_labels"] = [i for i, c in enumerate(s.callouts) if c.part is not None and c.part.name in names]
    from . import welds                     # task 0320: welds whose two parts are both in the copy
    out["_welds"], weld_left = welds.for_copy(scene, names)
    left += weld_left
    uids = {_uid(o) for o in objs_in if _uid(o)}
    out["_cables"], out["_spools"] = [], []
    copied = set()
    for i, it in enumerate(s.cables):           # task 0374: a cable read from CAD comes along when all of it does
        why = _cable_stays(it, uids)
        if why is None:
            out["_cables"].append(i)
            copied.add(it.name)
        elif why:
            left.append(f"Cable '{it.name}' is not copied ({why}): add it again on the copy")
    for i, it in enumerate(s.spools):
        used = {it.part_uid, it.coil_uid} - {""}
        if not used & uids:
            continue
        if it.cable in copied and used <= uids:
            out["_spools"].append(i)
        else:
            left.append(f"Drum '{it.name}' is not copied ({'its cable stays' if it.cable not in copied else 'a part of it is outside the copy'}): add it again on the copy")
    for it in s.tracks:
        used = {getattr(it, "part_uid", ""), getattr(it, "chain_uid", "")}
        used |= {getattr(w, "part_uid", "") for w in getattr(it, "wheels", ())}
        if used & uids:
            left.append(f"Track '{it.name}' is not copied: add it again on the copy")


def _cable_stays(it, uids: set):
    """Why the cable ``it`` is not copied with parts ``uids`` (a few words), '' when it has nothing in the copy, None
    when it comes along: read from CAD, its part, every part it runs over and both ends' parts in the copy, not into
    the sea (task 0374)."""
    used = {it.part_uid} | {c.part_uid for c in it.contacts} | {it.a_uid, it.b_uid}
    used -= {""}
    if not used & uids:
        return ""
    if it.drawn:
        return "drawn in the app"
    if it.b_kind == "SEA":
        return "it hangs into the sea"
    if not it.part_uid or not used <= uids:
        return "a part it runs over or ends on is outside the copy"
    return None


def plan(scene, objs) -> dict:
    """What a paste of ``objs`` makes: per copy its name, parts and set-up, and the lines of what is left out."""
    tree = logic.Tree(scene)
    out = {"copies": [], "left": [], "parts": 0, "joints": 0, "cylinders": 0, "mechanisms": 0, "way_covers": 0,
           "hoses": 0, "labels": 0, "welds": 0, "cables": 0, "drums": 0}
    for g in groups(scene, objs):
        objs_in = _objects(scene, g, tree)
        names = {o.name for o in objs_in}
        one = {"left": [], "root": g["root"].name, "whole": g["whole"],
               "top": [o.name for o in g["top"]], "objects": [o.name for o in objs_in],
               "parts": sum(1 for o in objs_in if o.get(build.PROP_KIND) == "part" and o.type == "MESH")}
        if g["root"].get("fr_lifting"):
            out["left"].append(f"'{_name(g['root'])}' is a crane of the lifting plan: add another in 8 Lifting plan")
            continue
        _select(scene, objs_in, names, one)
        out["copies"].append(one)
        out["left"] += one["left"]
        out["parts"] += one["parts"]
        for k, key in (("joints", "_joints"), ("cylinders", "_cylinders"), ("mechanisms", "_mechanisms"),
                       ("way_covers", "_covers"), ("hoses", "_flex"), ("labels", "_labels"), ("welds", "_welds"),
                       ("cables", "_cables"), ("drums", "_spools")):
            out[k] += len(one[key])
    return out


def summary(p: dict) -> list:
    """The lines a paste says: what came along, what was left out (the rule) and that it moves by itself."""
    bits = [plural(p.get("parts", 0), "part")]
    for key, word in (("joints", "joint"), ("cylinders", "cylinder"), ("mechanisms", "mechanism"),
                      ("way_covers", "way cover"), ("hoses", "hose"), ("labels", "label"), ("welds", "weld"),
                      ("cables", "cable"), ("drums", "drum")):
        n = int(p.get(key, 0) or 0)
        if n:
            bits.append(plural(n, word))
    names = p.get("names") or [c.get("name", "") for c in p.get("copies", ())]
    head = f"Copied {', '.join(repr(n) for n in names[:2])}{' …' if len(names) > 2 else ''}: " if names else "Copy: "
    lines = [head + ", ".join(bits)]
    left = list(dict.fromkeys(p.get("left", ())))
    if left:
        lines.append("Left out (things that reach outside the copy – the copy moves by itself): " + "; ".join(left))
    if any(c.get("whole") for c in p.get("copies", ())):
        lines.append("A copy of a whole model follows a model update of the original (and the other way round)")
    if any(not c.get("whole") for c in p.get("copies", ())):
        lines.append("A copy of a subassembly or parts is a model of its own: a model update leaves it as it is")
    if p.get("built"):
        lines.append("The built animation was taken off: Build again")
    return lines


# ---------------------------------------------------------------------------
# making the copy
# ---------------------------------------------------------------------------

def _clean(c) -> None:
    """A copied object: nothing of the original's set-up on it (keys, constraints, the app's modifiers, tags)."""
    c.animation_data_clear()
    for con in list(c.constraints):
        c.constraints.remove(con)
    for mod in list(getattr(c, "modifiers", ())):
        if mod.name.startswith("FR "):
            c.modifiers.remove(mod)
    for k in _STRIP:
        if k in c:
            del c[k]


def _taken_names(scene) -> set:
    return {o.get(build.PROP_NAME, "") for o in scene.objects if o.get(build.PROP_ROOT)} | set(bpy.data.objects.keys())


def _make_objects(scene, g, objs_in, worlds: dict, scope: str, name: str) -> tuple:
    """The copied objects in the CAD pose. Returns (copy root, {original name: copy}, {original uid: copy uid})."""
    root = g["root"]
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    copies: dict = {}
    uids: dict = {}

    def new_uid(u: str) -> str:
        return build.scoped(build.unscoped(u), scope)

    if g["whole"]:
        new_root = None
    else:                                   # a model of its own round the copied subassemblies / parts
        new_root = bpy.data.objects.new(name, None)
        new_root.empty_display_type = "PLAIN_AXES"
        new_root.empty_display_size = 0.05
        col.objects.link(new_root)
        new_root[build.PROP_KIND] = "assembly"
        new_root[build.PROP_UID] = new_uid(_uid(root))
        new_root[build.PROP_NAME] = name
        new_root[build.PROP_INSTANCE] = ""
        new_root[build.PROP_COLOR] = ""
        new_root[build.PROP_CAD_MATERIAL] = ""
        new_root[build.PROP_ROOT] = True
        new_root[build.PROP_UID_SCOPE] = scope
        new_root[build.PROP_LOCKED] = True
        new_root[FROZEN] = True
        new_root[COPY_OF] = _name(root)
        for key in ("fr_up_axis",):
            if key in root:
                new_root[key] = root[key]
        for k in (build.PROP_CAD_BASIS, build.PROP_REST_BASIS):
            build.set_mat(new_root, k, Matrix.Identity(4))
        new_root.lock_location = new_root.lock_rotation = new_root.lock_scale = (True,) * 3
        uids[_uid(root)] = new_root[build.PROP_UID]
    for o in objs_in:
        c = o.copy()                        # shares the mesh: the project hardly grows
        _clean(c)
        c.parent = None
        col.objects.link(c)
        if o.hide_get():
            c.hide_set(True)
        copies[o.name] = c
        if _uid(o):
            c[build.PROP_UID] = new_uid(_uid(o))
            uids[_uid(o)] = c[build.PROP_UID]
    for o in objs_in:
        c = copies[o.name]
        p = build.logical_parent(o)
        if o is root:                       # a whole model: the root where the original stands
            basis = o.matrix_basis.copy()
            c.parent = None
        elif p is not None and p.name in copies:
            basis = build.cad_basis(o)
            c.parent = copies[p.name]
        else:                               # the top of a copied subassembly / part: its CAD place in the world
            basis = worlds[o.name]
            c.parent = new_root
            if place_file() in c:
                del c[place_file()]
        c.matrix_parent_inverse = Matrix.Identity(4)
        c.matrix_basis = basis
        if o is not root:
            build.set_mat(c, build.PROP_CAD_BASIS, basis)
            build.set_mat(c, build.PROP_REST_BASIS, basis)
        for d in getattr(c, "fresing_decals", ()):        # a decal on this copy only: its own key
            d.key = "d-" + uuid.uuid4().hex[:10]
    top = new_root if new_root is not None else copies[root.name]
    if g["whole"]:
        for k in _ROOT_STRIP:
            if k in top:
                del top[k]
        top[build.PROP_UID_SCOPE] = scope
        top[build.PROP_NAME] = name
        top[COPY_OF] = _name(root)
        group = root.get(GROUP) or uuid.uuid4().hex[:12]
        root[GROUP] = group
        top[GROUP] = group
        removed = root.get("fr_removed")
        if removed:
            try:
                top["fr_removed"] = json.dumps(sorted(new_uid(u) for u in json.loads(removed)))
            except ValueError:
                del top["fr_removed"]
    top.name = name
    return top, copies, uids


def place_file() -> str:
    from . import place
    return place.FILE


def _joint_specs(scene, one, uids) -> tuple:
    """The joints that come along as specs on the copy (read in the CAD pose): parts, names, what they sit on and
    follow mapped."""
    s = scene.fresing
    taken = {j.name for j in s.joints}
    names_j = {}
    for n in one["_joints"]:
        names_j[n] = next_name(n, taken)
        taken.add(names_j[n])
    out = []
    for sp in one["_jspecs"]:
        sp = dict(sp)
        sp["name"] = names_j[sp["name"]]
        sp["members"] = [uids.get(u, "@-") for u in sp["members"]]
        sp["base"] = uids.get(sp["base"]) if sp.get("base") else None
        if sp.get("base_joint"):
            sp["base_joint"] = names_j.get(sp["base_joint"])
        if sp.get("follows"):
            if sp["follows"] in names_j:
                sp["follows"] = names_j[sp["follows"]]
            else:
                sp["follows"] = ""
                sp["table_owner"], sp["table"] = "", None
        if sp.get("follows") and sp.get("table_owner") and sp.get("table"):
            sp["table_owner"] = next_name(sp["table_owner"], ())     # its own owner: the original's never rewrites it
        tags = dict(sp.get("tags") or {})
        tags.pop("fr_cable", None)
        tags.pop("fr_track", None)
        sp["tags"] = tags
        out.append(sp)
    return out, names_j


def paste(scene, objs, at=None) -> dict:
    """Copy ``objs`` (models, subassemblies, parts) with what comes along; each copy beside its original, or with its
    box's middle over the world point ``at`` (standing on it). Returns the plan with ``"roots"`` (the copies' root
    names), ``"names"`` and ``"notes"``. One undo step is the operator's. A paste that fails half-way takes back what it
    made and raises RuntimeError."""
    p = plan(scene, objs)
    p["roots"], p["names"], p["notes"] = [], [], []
    if not p["copies"]:
        return p
    before = _snapshot(scene, p)
    try:
        return _paste(scene, p, at)
    except Exception as exc:
        try:
            _roll_back(scene, before)
        except Exception as exc2:  # noqa: BLE001
            raise RuntimeError(f"the paste failed ({exc or type(exc).__name__}) and could not be undone "
                               f"({exc2 or type(exc2).__name__}): reopen the project without saving") from exc
        raise RuntimeError(f"the paste failed ({exc or type(exc).__name__}); nothing was added") from exc


def _snapshot(scene, p) -> dict:
    s = scene.fresing
    return {"objects": set(bpy.data.objects.keys()), "collections": set(bpy.data.collections.keys()),
            "joints": [j.name for j in s.joints], "cylinders": [c.name for c in s.cylinders],
            "mechanisms": [m.name for m in s.mechanisms], "flex": len(s.flex), "callouts": len(s.callouts),
            "waycovers": len(s.waycovers), "welds": [it.key for it in scene.fresing_welds.items],
            "cables": len(s.cables), "spools": len(s.spools),
            "groups": {c["root"]: bpy.data.objects[c["root"]].get(GROUP) for c in p["copies"]}}


def _roll_back(scene, before: dict) -> None:
    """A paste failed half-way: everything it made goes again (an operator that fails pushes no undo step)."""
    from . import cylinders, flex, linkages
    s = scene.fresing
    for c in [c for c in s.cylinders if c.name not in before["cylinders"]]:
        cylinders.remove(scene, cylinders.find(scene, c.name))
    for m in [m.name for m in s.mechanisms if m.name not in before["mechanisms"]]:
        linkages.remove(scene, linkages.find(scene, m))
    for name in reversed([j.name for j in s.joints if j.name not in before["joints"]]):
        j = joints.find(scene, name)
        if j is not None:
            joints.remove(scene, j)
    from . import paths, spool
    for i in reversed(range(before.get("spools", len(s.spools)), len(s.spools))):
        spool.remove(scene, i)
    for i in reversed(range(before.get("cables", len(s.cables)), len(s.cables))):
        paths.remove(scene, i)
    for i in reversed(range(before["flex"], len(s.flex))):
        flex.remove(scene, i)
    for coll, n in ((s.callouts, before["callouts"]), (s.waycovers, before["waycovers"])):
        for i in reversed(range(n, len(coll))):
            coll.remove(i)
    from . import welds
    for key in [it.key for it in welds.items(scene) if it.key not in before.get("welds", ())]:
        welds.remove(scene, welds.find_item(scene, key))
    new = [o for o in bpy.data.objects if o.name not in before["objects"]]
    if new:
        bpy.data.batch_remove(new)
    for c in [c for c in bpy.data.collections if c.name not in before["collections"]]:
        if not len(c.objects) and not len(c.children):
            bpy.data.collections.remove(c)
    for name, g in before["groups"].items():
        ob = bpy.data.objects.get(name)
        if ob is not None and not g and GROUP in ob:
            del ob[GROUP]
    _tidy(scene)


def _paste(scene, p, at) -> dict:
    from . import animation, cylinders, linkages, sequence, vessel_motion
    s = scene.fresing
    sequence.end_preview(scene)
    p["built"] = animation.has_keys(scene)
    animation.clear_keys(scene)
    build.ensure_bases(scene)
    tree = logic.Tree(scene)
    values = {j.name: joints.get_value(j) for j in s.joints}
    with vessel_motion.at_rest(scene):
        # 1. in the CAD pose: where the tops stand and the set-up as plain data
        with joints.cad_pose(scene):
            bpy.context.view_layer.update()
            for one in p["copies"]:
                one["_worlds"] = {n: bpy.data.objects[n].matrix_world.copy() for n in one["objects"]}
                one["_cspecs"] = [cylinders.to_spec(cylinders.find(scene, n)) for n in one["_cylinders"]]
                one["_mspecs"] = [linkages.to_spec(scene, linkages.find(scene, n)) for n in one["_mechanisms"]]
                one["_jspecs"] = joints.to_specs(scene, values, only=set(one["_joints"]))
        used = build.used_uids()
        for one in p["copies"]:
            root = bpy.data.objects[one["root"]]
            objs_in = [bpy.data.objects[n] for n in one["objects"]]
            g = {"root": root, "whole": one["whole"], "top": [bpy.data.objects[n] for n in one["top"]]}
            base = [build.unscoped(_uid(o)) for o in objs_in if _uid(o)] + [build.unscoped(_uid(root))]
            scope = build.free_scope(base, used)
            if one["whole"]:
                label = _name(root)
            elif len(g["top"]) == 1:
                label = _name(g["top"][0])
            else:
                label = f"Parts of {_name(root)}"
            name = next_name(label, _taken_names(scene))
            top, copies, uids = _make_objects(scene, g, objs_in, one["_worlds"], scope, name)
            used |= set(uids.values())
            bpy.context.view_layer.update()
            by_uid = joints.PartLookup({uids[_uid(o)]: copies[o.name] for o in objs_in if _uid(o)})
            if not one["whole"]:
                by_uid[top[build.PROP_UID]] = top
            notes = p["notes"]
            # 2. joints, mechanisms, cylinders on the copy (the model update's own code)
            jspecs, names_j = _joint_specs(scene, one, uids)
            one["names_j"] = names_j
            notes += joints.rebuild_from_specs(scene, jspecs, by_uid)
            taken = {m.name for m in s.mechanisms}
            mspecs = []
            for sp in one["_mspecs"]:
                sp = dict(sp)
                sp["name"] = next_name(sp["name"], taken)
                taken.add(sp["name"])
                sp["base"] = uids.get(sp["base"]) if sp.get("base") else None
                sp["links"] = [[uids.get(u, "@-") for u in ln] for ln in sp["links"]]
                sp["joint"] = names_j.get(sp.get("joint") or "", "")
                mspecs.append(sp)
            notes += linkages.rebuild_from_specs(scene, mspecs, by_uid)
            taken = {c.name for c in s.cylinders}
            cspecs = []
            for sp in one["_cspecs"]:
                sp = dict(sp)
                sp["name"] = next_name(sp["name"], taken)
                taken.add(sp["name"])
                for k in ("barrel", "rod", "stages"):
                    sp[k] = [uids.get(u, "@-") for u in sp.get(k, [])]
                for k in ("barrel_carrier", "rod_carrier"):
                    sp[k] = uids.get(sp[k]) if sp.get(k) else None
                cspecs.append(sp)
            notes += cylinders.rebuild_from_specs(scene, cspecs, by_uid)
            # 3. way covers, hoses and drag chains, labels, logos
            notes += _covers(scene, one, names_j, copies, uids)
            notes += _flex(scene, one, copies, uids, by_uid)
            _labels(scene, one, copies)
            _decals(copies)
            from . import welds             # task 0320: the welds on the copied parts
            one["weld_keys"] = welds.copy_to(scene, one.get("_welds", []), copies)
            one["copy_root"] = top.name
            one["name"] = name
            one["_map"] = {n: c.name for n, c in copies.items()}
            p["roots"].append(top.name)
            p["names"].append(name)
        try:
            vessel_motion.sync(scene)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: Paste: vessel motion not synced:", exc)
    logic.apply_rules(scene)
    _tidy(scene)
    # 4. beside the original (or where the mouse was); Back to where it was imported = here
    from . import place
    placed: list = []
    for one in p["copies"]:
        top = bpy.data.objects[one["copy_root"]]
        orig = [bpy.data.objects[n] for n in one["top"]]
        D = _landing(scene, top, orig, at, placed)
        if D is not None:
            place.move(scene, [top], D)
        build.set_mat(top, build.PROP_REST_BASIS, top.matrix_basis)
        placed.append(place.bounds(scene, top))
    # 5. cables and drums (task 0374): read again on the copied parts once the copy stands beside the original (the
    # reading looks for the round parts near the cable: on top of the original it would find the original's too)
    for one in p["copies"]:
        p["notes"] += _cables(scene, one, p)
    p["cables"], p["drums"] = p.get("cables_made", 0), p.get("drums_made", 0)
    _tidy(scene)
    LAST.clear()
    LAST.update(p)
    NOTE[0] = " ".join(summary(p))
    return p


def _covers(scene, one, names_j, copies, uids) -> list:
    s = scene.fresing
    taken = {w.name for w in s.waycovers}
    for i in one["_covers"]:
        dst = s.waycovers.add()                 # (an item held across add() is no longer valid: CLAUDE.md 8)
        src = s.waycovers[i]
        _copy_raw(src, dst)
        dst["name"] = next_name(src.name, taken)
        taken.add(dst.name)
        dst["axis"] = names_j.get(src.axis, src.axis)
        for sec in dst.sections:
            if sec.joint:
                sec["joint"] = names_j.get(sec.joint, sec.joint)
            for r in sec.parts:
                if r.obj is not None and r.obj.name in copies:
                    r.obj = copies[r.obj.name]
            if sec.uids:
                sec["uids"] = "\n".join(uids.get(u, u) for u in sec.uids.split("\n"))
        for r in getattr(dst, "parts", ()):
            if r.obj is not None and r.obj.name in copies:
                r.obj = copies[r.obj.name]
    return []


def _flex(scene, one, copies, uids, by_uid) -> list:
    """Hoses and drag chains: a copy of the item on the copied parts. The parts' shapes and the ends' places in their
    parts are the original's (shared meshes), so what was read stays true: only the parts change; the shapes are
    worked out again. A copied part whose hose did not come along shows its CAD shape."""
    from . import flex
    s = scene.fresing
    taken = {it.name for it in s.flex}
    keep = set()
    for i in one["_flex"]:
        dst = s.flex.add()                      # (an item held across add() is no longer valid: CLAUDE.md 8)
        src = s.flex[i]
        _copy_raw(src, dst)
        dst["name"] = next_name(src.name, taken)
        taken.add(dst["name"])
        for key in ("part", "a_part", "b_part"):
            ob = getattr(src, key)
            if ob is not None and ob.name in copies:
                dst[key] = copies[ob.name]
        for key in ("part_uid", "a_uid", "b_uid"):
            if dst.get(key):
                dst[key] = uids.get(dst[key], dst[key])
        if dst.get("link_uids"):
            dst["link_uids"] = "\n".join(uids.get(u, u) for u in dst["link_uids"].split("\n"))
        for r in dst.links:
            if r.obj is not None and r.obj.name in copies:
                r.obj = copies[r.obj.name]
        keep.update(o.name for o in flex.parts_of(scene, dst))
    for c in copies.values():
        if c.name not in keep and any(k in c for k in _FLEX_TAGS):
            flex._strip(c)
    if one["_flex"]:
        flex.forget()
        return flex._rebuild(scene) or []
    return []


def _cables(scene, one, p) -> list:
    """The cables and drums that come along (``_select``): made again on the copy with their own create functions –
    the cable read from its copied part (its own speed joint, sheaves' joints, couplings), its look, typed diameter
    and stripe pitch as the original's; a drum added on the copied barrel and coil. One that cannot be made is said."""
    if not one.get("_cables"):
        return []
    from . import paths, spool
    s = scene.fresing
    m = one.get("_map", {})

    def copy_of(ob):
        return bpy.data.objects.get(m.get(ob.name, "")) if ob is not None else None

    srcs = []
    for i in one["_cables"]:
        it = s.cables[i]
        srcs.append({"name": it.name, "part": copy_of(it.part), "look": it.look, "pitch": float(it.pitch),
                     "diameter": float(it.diameter), "cad": float(it.cad_diameter), "reverse": bool(it.reverse),
                     "enabled": bool(it.enabled)})
    drums = []
    for i in one.get("_spools", ()):
        sp = s.spools[i]
        drums.append({"name": sp.name, "kind": sp.kind, "cable": sp.cable, "part": copy_of(sp.part),
                      "coil": copy_of(sp.coil)})
    notes, new_names = [], {}
    taken = {it.name for it in s.cables}
    for d in srcs:
        if d["part"] is None:
            p["left"].append(f"Cable '{d['name']}' is not copied (its part did not come along): add it again on the copy")
            continue
        name = next_name(d["name"], taken)
        taken.add(name)
        try:
            item = paths.add_cable(scene, name)
            name = item.name
            with paths._quiet(item):
                item.look = d["look"]
                item.reverse = d["reverse"]
            item["look_was"] = d["look"]
            notes += paths.read_cad(scene, paths.find(scene, name), d["part"])
            item = paths.find(scene, name)
            with paths._quiet(item):
                if d["pitch"] > 0.0:
                    item.pitch = d["pitch"]
            if abs(d["diameter"] - d["cad"]) > paths.USER_CHANGE:
                item.diameter = d["diameter"]
            if not d["enabled"]:
                item.enabled = False
            new_names[d["name"]] = name
            p["cables_made"] = p.get("cables_made", 0) + 1
        except Exception as exc:  # noqa: BLE001 - a cable that cannot be read again never stops a paste
            it = paths.find(scene, name)
            if it is not None:
                paths.remove(scene, paths.index_of(scene, it))
            p["left"].append(f"Cable '{d['name']}' could not be copied ({exc}): add it again on the copy")
    taken = {sp.name for sp in s.spools}
    for d in drums:
        cable = new_names.get(d["cable"])
        if cable is None or d["part"] is None:
            p["left"].append(f"Drum '{d['name']}' is not copied (its cable did not come along): add it again on the copy")
            continue
        name = next_name(d["name"], taken)
        taken.add(name)
        try:
            spool.add(scene, d["kind"], d["part"], cable, name=name, coil=d["coil"])
            p["drums_made"] = p.get("drums_made", 0) + 1
        except Exception as exc:  # noqa: BLE001
            p["left"].append(f"Drum '{d['name']}' could not be copied ({exc}): add it again on the copy")
    return notes


def _labels(scene, one, copies) -> None:
    s = scene.fresing
    for i in one["_labels"]:
        dst = s.callouts.add()                  # (an item held across add() is no longer valid: CLAUDE.md 8)
        src = s.callouts[i]
        _copy_raw(src, dst)
        dst.part = copies[src.part.name]


def _decals(copies) -> None:
    from . import decals
    parts = [c for c in copies.values() if c.type == "MESH" and c.get(build.PROP_KIND) == "part"]
    try:
        decals.sync(parts)
    except Exception as exc:  # noqa: BLE001 - a logo that cannot be drawn never stops a paste
        print("Fresing Render: Paste: logos not drawn:", exc)


def _copy_raw(src, dst) -> None:
    """Every stored setting of a list item onto another, without update callbacks (nested lists too)."""
    for k in src.keys():
        v = src[k]
        if hasattr(v, "to_dict"):
            v = v.to_dict()
        elif hasattr(v, "to_list"):
            v = v.to_list()
        dst[k] = v


def _landing(scene, top, orig, at, placed) -> Matrix | None:
    """The move that puts the copy beside the original (+X, past the original and earlier copies, a gap between)
    or – ``at`` – its box's middle over that point, standing on it."""
    from . import place
    lo, hi = place.bounds(scene, top)
    if at is not None:
        at = Vector(at)
        mid = (lo + hi) / 2.0
        return Matrix.Translation(Vector((at.x - mid.x, at.y - mid.y, at.z - lo.z)))
    width = max(hi.x - lo.x, 0.01)
    gap = max(0.2 * width, 0.1)
    boxes = [place.bounds(scene, r) for r in build.model_roots(scene) if r is not top] + placed
    for k in range(1, 200):
        dx = k * (width + gap)
        a, b = lo + Vector((dx, 0, 0)), hi + Vector((dx, 0, 0))
        if not any(a.x < bh.x and b.x > bl.x and a.y < bh.y and b.y > bl.y and a.z < bh.z and b.z > bl.z
                   for bl, bh in boxes):
            return Matrix.Translation(Vector((dx, 0.0, 0.0)))
    return Matrix.Translation(Vector((width + gap, 0.0, 0.0)))


def _tidy(scene) -> None:
    from . import hover
    hover.clear()
    bpy.context.view_layer.update()
    logic.drop_tree_cache()
    logic.rebuild_tree(scene)
    logic.update_bounds(scene)
    scene.fresing.bounds_valid = False


# ---------------------------------------------------------------------------
# model updates (reimport.py)
# ---------------------------------------------------------------------------

def refused_update(root) -> str:
    """Why a model update of this root is refused ('' when it is not): a copy of a subassembly or parts is frozen."""
    if root is not None and root.get(FROZEN):
        return (f"'{_name(root)}' is a copy of a subassembly or parts: it has its own parts and does not follow "
                "model updates. Update the original, then copy it again")
    return ""


def carry_root(old_root, new_root) -> dict:
    """A model update of a copy (or of an original with copies): the new revision stays in the copy group and keeps
    the copy's name. Returns what to put back once the old root is gone (``after_root``)."""
    for k in (GROUP, COPY_OF):
        if old_root.get(k):
            new_root[k] = old_root[k]
    if old_root.get(COPY_OF):
        new_root[build.PROP_NAME] = old_root.get(build.PROP_NAME, new_root.get(build.PROP_NAME, ""))
        return {"name": old_root.name}
    return {}


def after_root(new_root, kept: dict) -> None:
    if kept.get("name") and kept["name"] not in bpy.data.objects:
        new_root.name = kept["name"]


def others(scene, root) -> list:
    """The other models of ``root``'s copy group (a whole model and its copies)."""
    g = root.get(GROUP) if root is not None else None
    if not g:
        return []
    return [r for r in build.model_roots(scene) if r is not root and r.get(GROUP) == g and not r.get(FROZEN)]
