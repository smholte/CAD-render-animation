"""Standard kinds, colours and sizes on hoses, cables and drag chains (task 0243). The tables: core/flex_kinds.py.

An item is a hose or drag chain of ``scene.fresing.flex`` (FRFlex, blender/flex.py) or a cable of
``scene.fresing.cables`` (FRCable, blender/paths.py). Its kind is ``hose_kind`` / ``chain_kind`` / ``cable_kind``
("NONE" = as before 0243: the CAD part's look, the numbers as typed), its colour ``kind_colour`` and its size
``size_id`` ("" = Custom), both ids of the kind's lists.

* **A kind** puts the part into the material group of its kind and colour ("Pneumatic tube, blue"; the offshore
  cable and the wire rope keep the groups of the cable looks, "Power cables", "Wire ropes" …), made with the kind's
  material when the group is new – one shared material per kind and colour, which 3 Looks, the web export and the
  render queue treat as any other group. Going back to "NONE" puts the part back where it was (``WAS``). A hose kind
  with a pattern writes ``fr_cable_look`` on the part (blender/cable_looks.py reads it with the tube's ``fr_cable``).
* **A size** writes the numbers at once (diameter + smallest bend; a chain's width, height, link length, the nearest
  of its bend radii and as many links as keep its length) and works the item out once. A number changed by hand
  sets the size to Custom (``edited``).
"""

from __future__ import annotations

import bpy

from ..core import flex_kinds as K

WAS = "fr_kind_group_was"            # on an FRFlex item: the manual group its part had before a kind was picked
PATTERN = "fr_cable_look"            # = cable_looks.LOOK
_ITEMS: dict = {}                    # enum items are kept alive here (Blender needs the strings to stay)


def is_cable(item) -> bool:
    return hasattr(item, "cable_kind")


def family(item) -> str:
    if is_cable(item):
        return "cable"
    return "chain" if item.kind == "CHAIN" else "hose"


def kind_id(item) -> str:
    if is_cable(item):
        k = item.cable_kind
    elif item.kind == "CHAIN":
        k = item.chain_kind
    else:
        k = item.hose_kind
    return "" if k == "NONE" else k


def can_size(item) -> bool:
    """A chain of CAD links keeps its links' own shape and pitch: no kind or size for it."""
    return is_cable(item) or item.kind != "CHAIN" or bool(item.made_links)


# ---- the two drop-downs whose lists depend on the kind -------------------------------------------------------------

def colour_items(item, _context=None):
    k = K.get(kind_id(item))
    key = ("colour", k.id if k else "")
    if key not in _ITEMS:
        _ITEMS[key] = ([(c.id, c.label, f"{k.label}, {c.label.lower()}", "", i)
                        for i, c in enumerate(k.colours)] if k else [("NONE", "–", "Pick a kind first", "", 0)])
    return _ITEMS[key]


def colour_get(item) -> int:
    k = K.get(kind_id(item))
    if k is None:
        return 0
    ids = [c.id for c in k.colours]
    return ids.index(item.kind_colour) if item.kind_colour in ids else 0


def colour_set(item, value: int) -> None:
    k = K.get(kind_id(item))
    if k is None or not 0 <= value < len(k.colours):
        return
    item.kind_colour = k.colours[value].id
    scene = _scene()
    if scene is not None:
        apply_look(scene, item)


def size_items(item, _context=None):
    k = K.get(kind_id(item))
    key = ("size", k.id if k else "")
    if key not in _ITEMS:
        rows = [("CUSTOM", "Custom", "Your own numbers: type them below", "", 0)]
        if k:
            rows = [(s.id, s.label, s.note or s.label, "", i + 1) for i, s in enumerate(k.sizes)] + rows
        _ITEMS[key] = rows
    return _ITEMS[key]


def size_get(item) -> int:
    k = K.get(kind_id(item))
    if k is None or not item.size_id:
        return 0
    ids = [s.id for s in k.sizes]
    return ids.index(item.size_id) + 1 if item.size_id in ids else 0


def size_set(item, value: int) -> None:
    k = K.get(kind_id(item))
    scene = _scene()
    if k is None or value <= 0 or value > len(k.sizes):
        item.size_id = ""
        return
    pick_size(scene, item, k.sizes[value - 1].id)


def _scene():
    try:
        return bpy.context.scene
    except AttributeError:
        return None


# ---- picks ---------------------------------------------------------------------------------------------------

def _raw(item, name: str, value) -> None:
    """Set a setting without its update callback (the item is worked out once afterwards)."""
    item[name] = value


def kind_changed(scene, item) -> None:
    """A kind was picked: the colour the item had when the new kind has it too, else the kind's first; the standard
    size nearest the item's numbers; its look and its numbers."""
    k = K.get(kind_id(item))
    if k is None:
        item.size_id = ""
        apply_look(scene, item)
        return
    if item.kind_colour not in [c.id for c in k.colours]:
        item.kind_colour = k.colours[0].id
    if not is_cable(item) and item.kind == "HOSE":
        if k.stiffness >= 0.0:
            _raw(item, "stiffness", k.stiffness)
        if k.sag >= 0.0:
            _raw(item, "sag", k.sag)
    if can_size(item):
        sz = K.nearest_size(k.id, od=float(item.diameter),
                            width=float(item.width) if family(item) == "chain" else 0.0)
        if sz is not None:
            pick_size(scene, item, sz.id, look=True)
            return
    apply_look(scene, item)
    _changed(scene, item)


def pick_size(scene, item, size_id: str, look: bool = False) -> None:
    """Write a standard size's numbers into the item and work it out once."""
    k = K.get(kind_id(item))
    sz = K.size(k.id, size_id) if k else None
    if sz is None or not can_size(item):
        item.size_id = ""
        return
    fam = family(item)
    if fam == "chain":
        old_len = float(item.pitch) * int(item.count)
        _raw(item, "width", sz.width)
        _raw(item, "height", sz.height)
        _raw(item, "pitch", sz.pitch)
        r = float(item.radius)
        _raw(item, "radius", K.nearest_radius(sz, r, at_most=r if item.drawn else 0.0))
        if item.made_links and old_len > 0.0:
            _raw(item, "count", max(2, int(round(old_len / sz.pitch))))
    elif fam == "cable":
        _raw(item, "diameter", sz.od)
        _raw(item, "mbr", sz.bend)
    else:
        _raw(item, "diameter", sz.od)
        _raw(item, "min_radius", sz.bend)
    item.size_id = sz.id
    if look:
        apply_look(scene, item)
    _changed(scene, item)


def edited(item) -> None:
    """A number of the size was changed by hand: the size is Custom now (``_kind_busy`` while a pick writes)."""
    if item.size_id and not item.get("_kind_busy"):
        item.size_id = ""


def _changed(scene, item) -> None:
    if scene is None:
        return
    if is_cable(item):
        from . import paths
        paths.changed(scene, item)
    else:
        from . import flex
        if item.kind == "HOSE" and item.drawn and item.cad_length > 0.0 and \
                abs(item.length - item.cad_length) <= 1e-6 * max(item.cad_length, 1.0):
            flex.default_size(scene, item)      # a drawn hose at its length as drawn: worked out for the new bend
        else:
            flex.changed(scene, item)
        if family(item) == "hose":
            _pattern(scene, item)


# ---- the look --------------------------------------------------------------------------------------------------

def cable_group(item):
    """(group name, material id, colour text) a cable's kind and colour put it in; None = the look's own group."""
    k = K.get(kind_id(item))
    if k is None:
        return None
    c = K.colour(k.id, item.kind_colour)
    return K.group_name(k.id, c.id), c.material, c.text


def apply_look(scene, item) -> None:
    """The item's part into the group of its kind and colour (or back where it was), the hose pattern written."""
    if scene is None:
        return
    if is_cable(item):
        k = K.get(kind_id(item))
        from . import paths
        if k is not None:
            c = K.colour(k.id, item.kind_colour)
            want = c.look or "PLAIN"
            if item.look != want:
                item["_busy"] = True
                try:
                    item.look = want
                finally:
                    del item["_busy"]
        paths.changed(scene, item)              # writes the look's numbers and the group (paths._group)
        return
    part = item.part
    if part is None:
        return
    k = K.get(kind_id(item)) if can_size(item) else None
    from . import logic
    s = scene.fresing
    cur = part.get("fr_group_manual", "") or ""
    if k is not None:
        c = K.colour(k.id, item.kind_colour)
        want = K.group_name(k.id, c.id)
        if cur != want:
            if WAS not in item:
                item[WAS] = cur
            new = s.groups.get(want) is None
            part["fr_group_manual"] = want
            g = logic.ensure_group(s, want)
            if new:
                g.material = c.material
                if c.text:
                    g.color = c.text
            logic.apply_rules(scene)
            logic.refresh_group_materials(scene)
    elif WAS in item:
        was = item[WAS]
        del item[WAS]
        if cur in _kind_groups():          # the user put it elsewhere since: it stays
            if was:
                part["fr_group_manual"] = was
            elif "fr_group_manual" in part:
                del part["fr_group_manual"]
            logic.apply_rules(scene)
            logic.refresh_group_materials(scene)
    _pattern(scene, item)


def _kind_groups() -> set:
    return {K.group_name(k.id, c.id) for k in K.KINDS for c in k.colours}


def _pattern(scene, item) -> None:
    """A hose kind with a pattern: ``fr_cable_look`` on the part from its diameter; else none."""
    from . import idprops
    part = item.part
    if part is None or is_cable(item):
        return
    k = K.get(kind_id(item)) if item.kind == "HOSE" else None
    look = K.pattern_look(k.id, float(item.diameter)) if k is not None else None
    try:
        if look:
            have = list(part[PATTERN]) if PATTERN in part else []
            if len(have) != 4 or any(abs(a - b) > 1e-9 for a, b in zip(have, look)):
                idprops.store_array(part, PATTERN, look)
                part.update_tag()
        elif PATTERN in part and part.get(WAS + "_pattern"):
            del part[PATTERN]
            part.update_tag()
        if look:
            part[WAS + "_pattern"] = True
        elif WAS + "_pattern" in part:
            del part[WAS + "_pattern"]
    except ReferenceError:
        pass


def summary(item) -> str:
    """'Pneumatic tube, blue, 8 x 5 mm' for a status line ('' with no kind)."""
    k = K.get(kind_id(item))
    if k is None:
        return ""
    c = K.colour(k.id, item.kind_colour)
    sz = K.size(k.id, item.size_id)
    return f"{k.label}, {c.label.lower()}, {sz.label if sz else 'custom size'}"
