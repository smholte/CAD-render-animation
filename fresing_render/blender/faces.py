"""Face sets: faces of a part with a look of their own (task 0010).

A part is painted as a whole by default. A *face set* is a number of its CAD faces with another
material group: faces painted in the CAD file (they come in that way, from the face colours in
the import cache) or faces painted by hand in 3 Looks.

Where things are stored
-----------------------
* On the mesh (shared by every copy of the part):
  - ``fr_face_starts``: the first triangle of every CAD face, plus the number of triangles at the
    end (a CAD face is one block of triangles). A click on a triangle picks its whole CAD face.
  - ``fr_face_sets``: JSON list of the face sets; set ``k`` uses material slot ``k + 1``
    (slot 0 is the part itself) and the polygons' ``material_index``.
    Each set: ``key`` ("cad:#RRGGBB" or "hand:N"), ``kind`` ("cad"/"hand"), ``color`` and ``look``
    (CAD colour and appearance name, for the rules), ``group`` (the group chosen for every copy:
    '' = the rules decide, "=part" = looks like the rest of the part) and ``faces`` (CAD face
    numbers).
* On each object (copy): ``fr_face_copy``, JSON {set key: group} chosen for this copy only, and
  ``fr_face_groups``, JSON list with the group each set has on this copy after sorting.

Every material slot is linked to the object, so each copy can show a set in another group.
"""

from __future__ import annotations

import json

import bpy
import numpy as np

from ..core import ral
from ..core import rules as R
from . import build

PROP_STARTS = "fr_face_starts"
PROP_SETS = "fr_face_sets"
PROP_COPY = "fr_face_copy"
PROP_GROUPS = "fr_face_groups"
SAME_AS_PART = "=part"
COLOUR_TOLERANCE = 1.5 / 255


# ---------------------------------------------------------------------------
# stored data
# ---------------------------------------------------------------------------


def get_sets(me) -> list[dict]:
    if me is None or PROP_SETS not in me:
        return []
    try:
        return json.loads(me[PROP_SETS])
    except (TypeError, ValueError):
        return []


def _put_sets(me, sets: list[dict]) -> None:
    if sets:
        me[PROP_SETS] = json.dumps(sets)
    elif PROP_SETS in me:
        del me[PROP_SETS]


def get_copy(ob) -> dict:
    try:
        return json.loads(ob.get(PROP_COPY, "") or "{}")
    except (TypeError, ValueError):
        return {}


def _put_copy(ob, copy: dict) -> None:
    if copy:
        ob[PROP_COPY] = json.dumps(copy)
    elif PROP_COPY in ob:
        del ob[PROP_COPY]


def groups_on(ob) -> list[str]:
    """Group of each face set on this copy, as sorted by the last ``apply``."""
    try:
        return json.loads(ob.get(PROP_GROUPS, "") or "[]")
    except (TypeError, ValueError):
        return []


def has_sets(ob) -> bool:
    return ob.type == "MESH" and ob.data is not None and PROP_SETS in ob.data


def label(st: dict) -> str:
    if st.get("kind") == "cad":
        return st.get("look") or f"CAD colour {st.get('color', '')}"
    return "Painted by hand"


# ---------------------------------------------------------------------------
# CAD faces of a mesh
# ---------------------------------------------------------------------------


def _triangles(me) -> np.ndarray:
    n = len(me.polygons)
    loops = np.empty(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", loops)
    if len(loops) == n * 3:
        return loops.reshape(n, 3)
    starts = np.empty(n, dtype=np.int32)
    me.polygons.foreach_get("loop_start", starts)
    return loops[starts][:, None].repeat(3, axis=1)          # not triangles: one vertex each is enough


def _starts_from_shape(me) -> np.ndarray:
    """CAD faces of a mesh made before version 0.2.9 (no face list stored): the triangles of one
    CAD face share vertices, two faces never do, so each connected piece is one face."""
    tris = _triangles(me)
    n = len(tris)
    if n == 0:
        return np.zeros(1, dtype=np.int64)
    lab = np.arange(len(me.vertices), dtype=np.int64)
    while True:
        low = lab[tris].min(axis=1)
        new = lab.copy()
        for k in range(3):
            np.minimum.at(new, tris[:, k], low)
        while True:                                          # pointer jumping: follow labels to their root
            nxt = new[new]
            if np.array_equal(nxt, new):
                break
            new = nxt
        if np.array_equal(new, lab):
            break
        lab = new
    tri_label = lab[tris[:, 0]]
    cuts = np.flatnonzero(np.diff(tri_label)) + 1
    return np.concatenate(([0], cuts, [n])).astype(np.int64)


def face_starts(me) -> np.ndarray:
    """First triangle of every CAD face, plus the total (stored at import, else worked out once)."""
    if PROP_STARTS in me:
        arr = np.asarray(me[PROP_STARTS], dtype=np.int64)
        if len(arr) >= 2 and arr[-1] == len(me.polygons):
            return arr
    arr = _starts_from_shape(me)
    me[PROP_STARTS] = arr.tolist()
    return arr


def face_of_polygon(me, index: int) -> int:
    starts = face_starts(me)
    return int(np.searchsorted(starts, index, side="right") - 1)


def polygons_of_faces(starts: np.ndarray, faces) -> np.ndarray:
    faces = np.asarray(sorted(set(int(f) for f in faces if 0 <= int(f) < len(starts) - 1)), dtype=np.int64)
    if not len(faces):
        return np.zeros(0, dtype=np.int64)
    lo, hi = starts[faces], starts[faces + 1]
    lengths = hi - lo
    return np.repeat(lo - np.cumsum(np.concatenate(([0], lengths[:-1]))), lengths) + np.arange(lengths.sum())


def layout(me) -> tuple:
    """What a model update compares: the number of triangles of every CAD face."""
    return tuple(np.diff(face_starts(me)).tolist())


# ---------------------------------------------------------------------------
# writing face sets into the mesh
# ---------------------------------------------------------------------------


def _write(me, sets: list[dict]) -> None:
    """Polygon material indices and the number of material slots from the face sets."""
    sets = [st for st in sets if st.get("faces")]
    _put_sets(me, sets)
    n_poly = len(me.polygons)
    idx = np.zeros(n_poly, dtype=np.int32)
    if sets:
        starts = face_starts(me)
        for k, st in enumerate(sets, 1):
            idx[polygons_of_faces(starts, st["faces"])] = k
    old = np.empty(n_poly, dtype=np.int32)
    me.polygons.foreach_get("material_index", old)
    if not np.array_equal(old, idx):
        me.polygons.foreach_set("material_index", idx)
        me.update()
    while len(me.materials) < len(sets) + 1:
        me.materials.append(None)
    while len(me.materials) > len(sets) + 1:
        me.materials.pop()


def link_slots(ob) -> None:
    """Every material slot of a copy is its own (object-linked)."""
    for slot in ob.material_slots:
        if slot.link != "OBJECT":
            slot.link = "OBJECT"


def cad_sets(me, starts, tri_colours, palette, names, part_colour) -> int:
    """Face sets for faces painted in the CAD file (import). ``tri_colours``: palette index of
    every triangle (-1 = the part's colour); faces in the part's own colour need no set (some
    programs give every face the body colour). Returns the number of sets."""
    starts = np.asarray(starts, dtype=np.int64)
    me[PROP_STARTS] = starts.tolist()
    if tri_colours is None or not palette or len(tri_colours) != starts[-1]:
        return 0
    face_colour = np.asarray(tri_colours)[starts[:-1]]           # one colour per CAD face
    sets = []
    for pi, rgb in enumerate(palette):
        if part_colour is not None and all(abs(a - b) <= COLOUR_TOLERANCE for a, b in zip(rgb, part_colour)):
            continue
        faces = np.flatnonzero(face_colour == pi)
        if not len(faces):
            continue
        hexcol = ral.rgb_to_hex(rgb)
        sets.append({"key": f"cad:{hexcol}", "kind": "cad", "color": hexcol,
                     "look": (names[pi] if names and pi < len(names) else "") or "",
                     "group": "", "faces": faces.tolist()})
    if sets:
        _write(me, sets)
    return len(sets)


# ---------------------------------------------------------------------------
# sorting and materials
# ---------------------------------------------------------------------------


def plan(parts, rules: list, aliases: dict, part_group=None, rule_counts: list | None = None,
         by_rules: set | None = None) -> tuple[dict[str, list[str]], dict[str, int]]:
    """The group of every face set on every copy, without changing anything.

    Faces painted in CAD go through the rules like parts (see ``rules.face_facts``); a group
    chosen by hand wins, for all copies or for one. ``part_group(ob)`` gives the part's own group
    (default: the one it has now). Adds the rule hits to ``rule_counts``, the groups the rules gave
    to ``by_rules``, and returns ({object name: [group per face set]}, {group: number of face
    sets in it}) – sets that look like their part are not counted."""
    per_group: dict[str, int] = {}
    per_object: dict[str, list[str]] = {}
    by_look: dict[tuple, tuple] = {}
    for ob in parts:
        me = ob.data
        if me is None or PROP_SETS not in me:
            continue
        sets = get_sets(me)
        copy = get_copy(ob)
        out = []
        for st in sets:
            g = copy.get(st["key"]) or st.get("group") or ""
            if not g and st.get("kind") == "cad":
                look = (st.get("color", ""), st.get("look", ""))
                if look not in by_look:
                    g0, ri = R.classify_one(R.face_facts(*look), rules)
                    by_look[look] = (aliases.get(g0, g0), ri)
                g, ri = by_look[look]
                if ri >= 0 and rule_counts is not None:
                    rule_counts[ri] += 1
                if by_rules is not None and g != SAME_AS_PART:
                    by_rules.add(g)
            if not g:
                g = SAME_AS_PART
            if g == SAME_AS_PART:
                g = part_group(ob) if part_group else ob.get(build.PROP_GROUP, R.FALLBACK_GROUP)
            else:
                per_group[g] = per_group.get(g, 0) + 1
            out.append(g)
        per_object[ob.name] = out
    return per_object, per_group


def write_groups(parts, per_object: dict[str, list[str]]) -> None:
    """Store the face-set groups of ``plan`` on the copies (``fr_face_groups``)."""
    for ob in parts:
        out = per_object.get(ob.name)
        if out is None:
            if PROP_GROUPS in ob:
                del ob[PROP_GROUPS]
        else:
            text = json.dumps(out)
            if ob.get(PROP_GROUPS) != text:
                ob[PROP_GROUPS] = text


def sort(parts, rules: list, aliases: dict, rule_counts: list, by_rules: set | None = None) -> dict[str, int]:
    """Decide the group of every face set on every copy (stored in ``fr_face_groups``); see ``plan``.
    Returns {group: number of face sets in it}."""
    per_object, per_group = plan(parts, rules, aliases, rule_counts=rule_counts, by_rules=by_rules)
    write_groups(parts, per_object)
    return per_group


def assign(ob, mats: dict) -> None:
    """Materials of the face set slots of one copy (slot 0, the part, is done by the caller)."""
    if not has_sets(ob):
        return
    groups = groups_on(ob)
    while len(ob.material_slots) < len(groups) + 1:          # mesh changed since the last sort
        ob.data.materials.append(None)
    link_slots(ob)
    for k, g in enumerate(groups, 1):
        mat = mats.get(g)
        if mat is not None and ob.material_slots[k].material is not mat:
            ob.material_slots[k].material = mat


# ---------------------------------------------------------------------------
# painting by hand
# ---------------------------------------------------------------------------


def _users(me) -> list:
    return [ob for ob in bpy.data.objects if ob.data is me and ob.type == "MESH"]


def _new_key(sets: list[dict]) -> str:
    n = 1 + max((int(st["key"].split(":")[1]) for st in sets
                 if st.get("kind") == "hand" and st["key"].split(":")[1].isdigit()), default=0)
    return f"hand:{n}"


def paint(ob, faces, group: str, only_this_copy: bool = False) -> str:
    """Put CAD faces of ``ob``'s part in a face set of ``group``. Returns the set's key.

    For every copy, unless ``only_this_copy``: then the set looks like the rest of the part on
    the other copies. A face moves out of any set it was in."""
    me = ob.data
    face_starts(me)
    sets = get_sets(me)
    copy = get_copy(ob)
    if only_this_copy:
        target = next((st for st in sets if st.get("kind") == "hand" and st.get("group") == SAME_AS_PART
                       and copy.get(st["key"]) == group), None)
    else:
        target = next((st for st in sets if st.get("kind") == "hand" and st.get("group") == group), None)
    if target is None:
        target = {"key": _new_key(sets), "kind": "hand", "color": "", "look": "",
                  "group": SAME_AS_PART if only_this_copy else group, "faces": []}
        sets.append(target)
        if only_this_copy:
            copy[target["key"]] = group
            _put_copy(ob, copy)
    picked = {int(f) for f in faces}
    for st in sets:
        if st is not target:
            st["faces"] = [f for f in st["faces"] if f not in picked]
    target["faces"] = sorted(set(target["faces"]) | picked)
    _write(me, sets)
    _drop_stale_keys(me)
    return target["key"]


def unpaint(ob, faces) -> int:
    """These faces look like the rest of the part again (on every copy). Returns how many were painted."""
    me = ob.data
    picked = {int(f) for f in faces}
    sets = get_sets(me)
    n = 0
    for st in sets:
        before = len(st["faces"])
        st["faces"] = [f for f in st["faces"] if f not in picked]
        n += before - len(st["faces"])
    if n:
        _write(me, sets)
        _drop_stale_keys(me)
    return n


def set_group(ob, key: str, group: str, only_this_copy: bool = False) -> None:
    """Choose the group of a face set: on every copy, or on this copy only."""
    me = ob.data
    if only_this_copy:
        copy = get_copy(ob)
        copy[key] = group
        _put_copy(ob, copy)
        return
    sets = get_sets(me)
    for st in sets:
        if st["key"] == key:
            st["group"] = group
    _put_sets(me, sets)
    for user in _users(me):                      # "every copy" means every copy
        copy = get_copy(user)
        if copy.pop(key, None) is not None:
            _put_copy(user, copy)


def remove(ob, key: str, only_this_copy: bool = False) -> None:
    """Back to the whole part: the set goes (on every copy), or this copy shows it like its part."""
    if only_this_copy:
        set_group(ob, key, SAME_AS_PART, True)
        return
    me = ob.data
    _write(me, [st for st in get_sets(me) if st["key"] != key])
    _drop_stale_keys(me)


def _drop_stale_keys(me) -> None:
    keys = {st["key"] for st in get_sets(me)}
    for user in _users(me):
        copy = get_copy(user)
        kept = {k: v for k, v in copy.items() if k in keys}
        if kept != copy:
            _put_copy(user, kept)
        link_slots(user)


def rename_group(old: str, new: str) -> None:
    """A group was renamed: face sets that name it follow."""
    for me in bpy.data.meshes:
        if PROP_SETS in me:
            sets = get_sets(me)
            if any(st.get("group") == old for st in sets):
                for st in sets:
                    if st.get("group") == old:
                        st["group"] = new
                _put_sets(me, sets)
    for ob in bpy.data.objects:
        if PROP_COPY in ob:
            copy = get_copy(ob)
            if old in copy.values():
                _put_copy(ob, {k: (new if v == old else v) for k, v in copy.items()})


def forget_group(name: str) -> None:
    """A group was removed: face sets put in it by hand go back to the rules (CAD faces) or to
    the look of their part (faces painted by hand)."""
    for me in bpy.data.meshes:
        if PROP_SETS in me:
            sets = get_sets(me)
            if any(st.get("group") == name for st in sets):
                for st in sets:
                    if st.get("group") == name:
                        st["group"] = "" if st.get("kind") == "cad" else SAME_AS_PART
                _put_sets(me, sets)
    for ob in bpy.data.objects:
        if PROP_COPY in ob:
            copy = get_copy(ob)
            if name in copy.values():
                _put_copy(ob, {k: v for k, v in copy.items() if v != name})


# ---------------------------------------------------------------------------
# model update
# ---------------------------------------------------------------------------


def _worth_keeping(me, objs) -> bool:
    sets = get_sets(me)
    return any(st.get("kind") == "hand" or st.get("group") for st in sets) or any(PROP_COPY in o for o in objs)


def carry_over(pairs) -> list[str]:
    """After a model update: keep the face sets of parts whose faces did not change.

    ``pairs``: (old object, new object). Faces painted in CAD always come from the new file;
    groups chosen for them and faces painted by hand are kept when the part has the same CAD faces
    (same number of triangles on every face). Returns the names of parts that lost painted faces."""
    by_mesh: dict = {}
    for old, new in pairs:
        if old.type != "MESH" or new.type != "MESH" or old.data is None or new.data is None:
            continue
        by_mesh.setdefault(old.data.name, (old.data, new.data, []))[2].append((old, new))
    lost = []
    for old_me, new_me, obs in by_mesh.values():
        if not _worth_keeping(old_me, [o for o, _n in obs]):
            continue
        if layout(old_me) != layout(new_me):
            lost.append(obs[0][0].get(build.PROP_NAME, obs[0][0].name))
            continue
        old_sets = get_sets(old_me)
        new_sets = get_sets(new_me)
        by_key = {st["key"]: st for st in new_sets}
        for st in old_sets:
            if st.get("kind") == "cad" and st["key"] in by_key:
                by_key[st["key"]]["group"] = st.get("group", "")
        hand = [dict(st) for st in old_sets if st.get("kind") == "hand"]
        painted = {f for st in hand for f in st["faces"]}
        for st in new_sets:
            st["faces"] = [f for f in st["faces"] if f not in painted]
        _write(new_me, new_sets + hand)
        keys = {st["key"] for st in get_sets(new_me)}
        for old, new in obs:
            copy = {k: v for k, v in get_copy(old).items() if k in keys}
            _put_copy(new, copy)
            link_slots(new)
    return lost
