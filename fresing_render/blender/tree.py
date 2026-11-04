"""The structure list in 2 Structure: an explorer-like tree of subassemblies and parts.

* every assembly row opens and closes on its own (its open state is kept on the object);
* identical parts side by side are one row ("x 24"); identical subassemblies are told
  apart by their occurrence number (":2");
* a click on a row selects that subassembly/part in the view; a click in the view opens
  the tree down to what was clicked;
* "Show only" hides everything else until "Show all".
"""

from __future__ import annotations

import bpy

from . import build, logic

OPEN = "fr_tree_open"           # object property: this assembly row is open
ISO_HIDDEN = "fr_iso_hidden"    # object property: hidden by "Show only"

_STATE = {"from_view": False}   # the list index is being moved by a click in the view
_INDEX: dict = {}               # scene name -> (tree length, {object name: row})


# ---------------------------------------------------------------------------
# building the list
# ---------------------------------------------------------------------------


def _labelled(children: list) -> list:
    """(object, label) per child; identical names get their occurrence number."""
    names: dict[str, int] = {}
    for c in children:
        n = c.get(build.PROP_NAME, c.name)
        names[n] = names.get(n, 0) + 1
    seen: dict[str, int] = {}
    out = []
    for c in children:
        n = c.get(build.PROP_NAME, c.name)
        label = n
        if names[n] > 1:
            seen[n] = seen.get(n, 0) + 1
            inst = c.get(build.PROP_INSTANCE, "") or ""
            # Inventor's own occurrence name ("LEAK.TEST.MC.ASM:2") when the file has it
            label = inst if inst.startswith(n + ":") else f"{n} :{seen[n]}"
        out.append((c, label))
    return out


def rebuild(scene) -> None:
    s = scene.fresing
    keep = s.tree[s.tree_index].obj if 0 <= s.tree_index < len(s.tree) else None
    s.tree.clear()
    t = logic.Tree(scene)
    counts: dict[str, int] = {}

    def count(node) -> int:
        if node.name in counts:
            return counts[node.name]
        n = 0
        for c in t.children(node):
            n += 1 if c.get(build.PROP_KIND) == "part" else count(c)
        counts[node.name] = n
        return n

    def walk(node, depth: int, parent: int, label: str, same: int = 1) -> None:
        idx = len(s.tree)
        item = s.tree.add()
        item.obj = node
        item.depth = depth
        item.parent_index = parent
        item.label = label
        item.is_part = node.get(build.PROP_KIND) == "part"
        item.same = same
        if item.is_part:
            return
        item.parts = count(node)
        kids = t.children(node)
        subs = sorted((c for c in kids if c.get(build.PROP_KIND) == "assembly"),
                      key=lambda c: (c.get(build.PROP_NAME, c.name).lower(), c.get(build.PROP_UID, "")))
        parts = sorted((c for c in kids if c.get(build.PROP_KIND) == "part"),
                       key=lambda c: (c.get(build.PROP_NAME, c.name).lower(), c.get(build.PROP_UID, "")))
        item.has_kids = bool(subs or parts)
        item.expanded = bool(node.get(OPEN, depth == 0))
        for c, lab in _labelled(subs):
            walk(c, depth + 1, idx, lab)
        # identical parts next to each other: one row
        by_name: dict[str, list] = {}
        for c in parts:
            by_name.setdefault(c.get(build.PROP_NAME, c.name), []).append(c)
        for name, same_parts in by_name.items():
            walk(same_parts[0], depth + 1, idx, name, len(same_parts))

    roots = build.model_roots(scene)
    for root in roots:
        walk(root, 0, -1, root.get(build.PROP_NAME, root.name))
    s.model_count = len(roots)
    _INDEX.pop(scene.name, None)
    if keep is not None:
        row = row_of(scene, keep)
        if row is not None:
            _set_index_quietly(s, row)


def row_of(scene, ob) -> int | None:
    """Row of an object in the list (a part in a 'x 24' row gives that row)."""
    s = scene.fresing
    hit = _INDEX.get(scene.name)
    if hit is None or hit[0] != len(s.tree):
        rows: dict[str, int] = {}
        t = None
        for i, it in enumerate(s.tree):
            o = it.obj
            if o is None:
                continue
            rows[o.name] = i
            if it.is_part and it.same > 1 and 0 <= it.parent_index < len(s.tree):
                parent = s.tree[it.parent_index].obj
                name = o.get(build.PROP_NAME, o.name)
                if parent is not None:
                    t = t or logic.Tree(scene)          # one walk over the scene, not one per row
                    for c in t.children(parent):
                        if c.get(build.PROP_NAME, c.name) == name:
                            rows[c.name] = i
        hit = (len(s.tree), rows)
        _INDEX[scene.name] = hit
    return hit[1].get(ob.name)


def row_objects(scene, item, tree: logic.Tree | None = None) -> list:
    """Everything a row stands for: a subassembly with all below it, or the identical parts."""
    ob = item.obj
    if ob is None:
        return []
    t = tree or logic.Tree(scene)
    if item.is_part:
        s = scene.fresing
        if item.same > 1 and 0 <= item.parent_index < len(s.tree):
            parent = s.tree[item.parent_index].obj
            name = ob.get(build.PROP_NAME, ob.name)
            return [c for c in t.children(parent) if c.get(build.PROP_NAME, c.name) == name]
        return [ob]
    return [ob] + t.descendants(ob)


# ---------------------------------------------------------------------------
# open / close
# ---------------------------------------------------------------------------


def set_open(s, row: int, is_open: bool) -> None:
    it = s.tree[row]
    it.expanded = is_open
    if it.obj is not None:
        it.obj[OPEN] = is_open


def open_all(s, is_open: bool) -> None:
    for i, it in enumerate(s.tree):
        if it.has_kids:
            set_open(s, i, is_open or it.depth == 0)


def reveal(s, row: int) -> None:
    """Open every assembly above a row, so it shows in the list."""
    p = s.tree[row].parent_index
    while 0 <= p < len(s.tree):
        if not s.tree[p].expanded:
            set_open(s, p, True)
        p = s.tree[p].parent_index


def visible_rows(s, search: str = "") -> list[bool]:
    """Which rows the list shows: open branches, or the matches of a search with the rows above them."""
    n = len(s.tree)
    items = s.tree
    if search:
        needle = search.lower()
        show = [False] * n
        for i, it in enumerate(items):
            if needle in it.label.lower():
                j = i
                while 0 <= j and not show[j]:
                    show[j] = True
                    j = items[j].parent_index
        return show
    # read the two columns in one go (row by row is ~40 ms on 2,000 rows, at every redraw)
    parents = [0] * n
    opened = [False] * n
    items.foreach_get("parent_index", parents)
    items.foreach_get("expanded", opened)
    vis = [False] * n
    for i in range(n):
        p = parents[i]
        vis[i] = p < 0 or (vis[p] and opened[p])
    return vis


# ---------------------------------------------------------------------------
# selection: list -> view and view -> list
# ---------------------------------------------------------------------------


def _set_index_quietly(s, row: int) -> None:
    _STATE["from_view"] = True
    try:
        s.tree_index = row
    finally:
        _STATE["from_view"] = False


def follow_view(scene, ob) -> None:
    """A click in the view: open the tree down to it and make it the active row."""
    s = scene.fresing
    row = row_of(scene, ob)
    if row is None:
        return
    reveal(s, row)
    if s.tree_index != row:
        _set_index_quietly(s, row)


def select_objects(context, objs: list, extend: bool = False) -> None:
    """Select (highlight) these objects in the view; the first part becomes active."""
    from . import handlers
    vl = context.view_layer
    if not extend:
        for o in context.selected_objects:
            o.select_set(False)
    active = None
    for o in objs:
        if o.visible_get() and not o.hide_select:
            try:
                o.select_set(True)
            except RuntimeError:
                continue
            if active is None:
                active = o
    if active is not None:
        handlers.ignore_next(active)        # keep exactly this selection
        vl.objects.active = active


def on_index_changed(context) -> None:
    """A click on a row: highlight that subassembly or part in the view."""
    if _STATE["from_view"]:
        return
    scene = context.scene
    s = scene.fresing
    if not (0 <= s.tree_index < len(s.tree)):
        return
    try:
        select_objects(context, row_objects(scene, s.tree[s.tree_index]))
    except (AttributeError, RuntimeError):
        pass


def frame_selected(context) -> bool:
    """Zoom the 3D view onto the selection."""
    for area in getattr(context.screen, "areas", []) if context.screen else []:
        if area.type != "VIEW_3D":
            continue
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is None:
            continue
        with context.temp_override(area=area, region=region):
            bpy.ops.view3d.view_selected(use_all_regions=False)
        return True
    return False


# ---------------------------------------------------------------------------
# show only
# ---------------------------------------------------------------------------


def show_only(scene, keep: list, label: str) -> int:
    """Hide every model object except ``keep`` (and the assemblies above them). Returns how many were hidden."""
    end_show_only(scene)
    keep_names = set()
    for o in keep:
        keep_names.add(o.name)
        p = build.logical_parent(o)
        while p is not None and p.name not in keep_names:
            keep_names.add(p.name)
            p = build.logical_parent(p)
    n = 0
    for o in scene.objects:
        if o.get(build.PROP_KIND) not in build.MODEL_KINDS or o.name in keep_names:
            continue
        if o.hide_get() or o.hide_render:
            continue                         # already hidden by the user: leave it to them
        o[ISO_HIDDEN] = True
        logic.set_visible_flags(o, True)
        n += 1
    scene.fresing.isolated = label
    scene.fresing.bounds_valid = False
    return n


def end_show_only(scene) -> None:
    for o in scene.objects:
        if o.get(ISO_HIDDEN):
            del o[ISO_HIDDEN]
            if not o.get("fr_hidden") and not o.get(build.PROP_EXCLUDED):
                logic.set_visible_flags(o, False)
    scene.fresing.isolated = ""
    scene.fresing.bounds_valid = False
