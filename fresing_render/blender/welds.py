"""Welds (task 0319): a bead laid where two picked sets of faces meet, kept with the parts through everything.

Where things are stored
-----------------------
* ``scene.fresing_welds`` (``FRWeldSettings``): ``items`` – one ``FRWeld`` per weld –, the picker's state and its
  preview seams (``preview``).
* ``FRWeld``: the two parts (object pointers; a model update points them at the new parts), the picked CAD faces of each
  (``faces_a`` / ``faces_b``, JSON lists; empty with ``whole`` = the whole part, the quick way) and their prints
  (``prints_a`` / ``prints_b``: centre, area, mean normal in the part's own coordinates – a model update finds the faces
  again by them, ``core.welds.match_faces``), the seams found (``seams``: tick, length, kind, closed, middle point in
  the first part's coordinates – a seam unticked stays unticked when the seams are found again), the settings
  (size, kind, intermittent, metal, process, finish, paint, rust …), ``lost`` and ``note``.
* Per weld two objects, children of the first part (they move, hide, fade and are cut with it): ``Weld <name>``
  (kind ``weld``: the bead, UV map ``fr_weld``) and ``Weld <name> heat`` (kind ``weld_heat``: the heat-zone strips,
  UV maps ``fr_weld`` + ``fr_weld_end``). Both hide when either part is hidden (MAX drivers on the parts'
  ``hide_render``, as decals do: no scripts) or the weld is switched off (``fr_off``).

The seams are found in the first part's own coordinates with the second part where it is now (``find``), kept in
memory (``_CACHE``) while nothing changed, so ticking a seam or changing a size rebuilds only the bead (milliseconds).
After opening a project they are found again on the first change.

Not parts: the bead objects are never in ``build.iter_parts`` – the clash check, sorting rules and the structure tree
leave them out; the web 3D export takes the beads (``web_objects``) but not the heat zones (see the task report).
"""

from __future__ import annotations

import json
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from bpy.types import PropertyGroup
from mathutils import Matrix, Vector

from ..core import materials_lib
from ..core import web3d_faces
from ..core import welds as core
from ..core.words import plural
from . import build

KIND = "weld"
HEAT_KIND = "weld_heat"
KINDS = (KIND, HEAT_KIND)
PROP_KEY = "fr_weld"
PROP_OFF = "fr_off"

_CACHE: dict = {}                    # weld key -> (signature, seams in part A's coordinates)
_BUSY = [False]                      # a rebuild is running: settings written by it do not rebuild again


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

def _changed(self, context):
    if _BUSY[0]:
        return
    item = self if isinstance(self, FRWeld) else owner_of_seam(self)
    if item is not None:
        rebuild(item)
    else:                                     # a preview seam of the picker: only its line changes colour
        try:
            for win in bpy.context.window_manager.windows:
                for area in win.screen.areas:
                    if area.type == "VIEW_3D":
                        area.tag_redraw()
        except Exception:  # noqa: BLE001
            pass


def _gap_changed(self, context):
    if not _BUSY[0]:
        refind(self)


def _name_changed(self, context):
    if _BUSY[0]:
        return
    for ob in objects_of(self):
        ob.name = _object_name(self, ob.get(build.PROP_KIND) == HEAT_KIND)


def _hidden_changed(self, context):
    for ob in objects_of(self):
        ob[PROP_OFF] = 1 if self.hidden else 0
        ob.update_tag()


KIND_ITEMS = [("AUTO", "As found", "Fillet in a corner, butt where two faces lie flush – as the seams were found"),
              ("FILLET", "Fillet", "A fillet weld in the corner between the two parts (size a = its throat)"),
              ("BUTT", "Butt", "A butt weld: a low cap with a small crown across the joint (size = its width)")]
METAL_ITEMS = [("AUTO", "From the parts", "Steel, stainless or aluminium as the parts' looks say"),
               ("STEEL", "Steel", "Carbon steel: grey-blue oxide, even ripples; rusts when bare"),
               ("STAINLESS", "Stainless", "Stainless steel: fine ripples, heat tint bands beside the bead"),
               ("ALUMINIUM", "Aluminium", "Aluminium: bright stacked ripples, never rusts")]
PROCESS_ITEMS = [("AUTO", "From the metal", "MAG for steel, TIG for stainless, MIG for aluminium (TIG below 4 mm)"),
                 ("MAG", "MAG", "Gas-shielded wire welding of steel: even ripples, a blue-grey oxide"),
                 ("TIG", "TIG", "Tungsten welding: fine, regular ripples (stainless, thin aluminium)"),
                 ("MIG", "MIG", "Gas-shielded wire welding of aluminium: wide 'stacked coins' and a sooty band"),
                 ("STICK", "Stick", "Stick electrode (steel): coarse ripples, darker, slag cleaned off")]
FINISH_ITEMS = [("AS_WELDED", "As welded", "The bead as it came from the torch, with its heat tint"),
                ("PAINTED", "Painted", "The bead and its heat zone take the paint of a part; the ripples show through"),
                ("GROUND", "Ground flush", "Ground smooth: no ripples, a brushed band")]
SIDE_ITEMS = [("A", "First part", "The paint of the first part you picked"),
              ("B", "Second part", "The paint of the second part you picked")]


class FRWeldSeam(PropertyGroup):
    enabled: BoolProperty(name="Weld this seam", default=True, update=_changed,
                          description="Untick to leave this seam without a bead (e.g. one side of a fillet)")
    length: FloatProperty(name="Length", unit="LENGTH", description="How long this seam is")
    kind: StringProperty(name="Kind", description="Fillet or butt, as found")
    closed: BoolProperty(name="All round", description="The seam goes all the way round (a tube in a plate)")
    angle: FloatProperty(name="Corner", description="The corner's opening in degrees (90 = a plate on a plate)")
    mid: FloatVectorProperty(name="Middle", size=3, description="Its middle point in the first part's coordinates")


class FRWeld(PropertyGroup):
    key: StringProperty()
    name: StringProperty(name="Name", default="Weld", update=_name_changed, description="The weld's name in the list")
    part_a: PointerProperty(type=bpy.types.Object, name="First part", description="The part whose faces were picked first; the bead moves with it")
    part_b: PointerProperty(type=bpy.types.Object, name="Second part", description="The part welded to the first")
    faces_a: StringProperty(default="[]")
    faces_b: StringProperty(default="[]")
    prints_a: StringProperty(default="{}")
    prints_b: StringProperty(default="{}")
    whole: BoolProperty(default=False, description="Made from two whole parts (the quick way)")
    gap: FloatProperty(name="Gap up to", unit="LENGTH", default=core.GAP, min=0.0, soft_max=0.006, step=0.05,
                       update=_gap_changed,
                       description="Faces this close count as meeting: a root gap or a loose fit in the CAD model. "
                                   "Larger finds more seams")
    kind: EnumProperty(name="Kind", items=KIND_ITEMS, default="AUTO", update=_changed,
                       description="Fillet or butt weld (As found: what the corner is)")
    size: FloatProperty(name="Size a", unit="LENGTH", default=0.005, min=0.001, soft_max=0.03, step=0.05,
                        update=_changed,
                        description="Fillet: the throat a (the height of the triangle in the corner, as on a drawing "
                                    "'a5'); starts at half the thinner plate")
    butt_width: FloatProperty(name="Cap width", unit="LENGTH", default=0.012, min=0.002, soft_max=0.05, step=0.05,
                              update=_changed, description="Butt weld: how wide the cap is across the joint")
    craters: BoolProperty(name="End craters", default=False, update=_changed,
                          description="A small dip where the bead starts and stops, as a welder leaves it")
    intermittent: BoolProperty(name="Intermittent", default=False, update=_changed,
                               description="Short pieces with gaps between them instead of one bead")
    length: FloatProperty(name="Piece", unit="LENGTH", default=0.05, min=0.005, soft_max=0.5, update=_changed,
                          description="Intermittent: how long each piece is")
    pitch: FloatProperty(name="Pitch", unit="LENGTH", default=0.15, min=0.01, soft_max=1.0, update=_changed,
                         description="Intermittent: from the start of one piece to the start of the next")
    metal: EnumProperty(name="Metal", items=METAL_ITEMS, default="AUTO", update=_changed,
                        description="What the bead is made of (From the parts: their looks decide)")
    process: EnumProperty(name="Process", items=PROCESS_ITEMS, default="AUTO", update=_changed,
                          description="How it was welded: the ripples and the colour follow it")
    finish: EnumProperty(name="Finish", items=FINISH_ITEMS, default="AS_WELDED", update=_changed,
                         description="As welded, painted over with a part's paint, or ground flush")
    paint_from: EnumProperty(name="Paint of", items=SIDE_ITEMS, default="A", update=_changed,
                             description="Painted: whose paint goes over the bead")
    pickled: BoolProperty(name="Pickled", default=False, update=_changed,
                          description="Stainless cleaned after welding: no heat tint, a matt bead, no tea stain")
    heat_tint: BoolProperty(name="Heat tint", default=True, update=_changed,
                            description="The tint the heat leaves on the parts beside the bead")
    spatter: BoolProperty(name="Spatter", default=False, update=_changed,
                          description="Small drops of metal beside a MAG or stick weld")
    rust: FloatProperty(name="Rust", default=0.0, min=0.0, max=1.0, subtype="FACTOR", update=_changed,
                        description="How rusty: a bare steel bead and its heat zone rust first, a painted one only "
                                    "where Wear took the paint off; stainless only gets a faint tea stain, aluminium "
                                    "never rusts")
    zinc_sprayed: BoolProperty(name="Zinc sprayed after welding", default=False, update=_changed,
                               description="Galvanised parts: the burnt zinc was sprayed again, so the weld does not "
                                           "rust")
    hidden: BoolProperty(name="Hidden", default=False, update=_hidden_changed,
                         description="Hide this weld (it stays in the list)")
    lost: BoolProperty(default=False)
    note: StringProperty(default="")
    seams: CollectionProperty(type=FRWeldSeam)
    seam_index: IntProperty(default=0)
    found_metal: StringProperty(default="")      # what the looks said when the weld was made (shown in the panel)
    seam_data: StringProperty(default="")        # the seams where they were found (core.welds.pack_seams)
    rel: FloatVectorProperty(size=16, default=(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1))
    #                                            the second part in the first part's coordinates when they were found
    # task 0323: a weld whose bead came in the CAD file (blender/weld_cad.py)
    from_cad: BoolProperty(default=False)
    cad_shape: BoolProperty(name="CAD shape", default=True, update=_changed,
                            description="Keep the bead's own shape from the CAD file (its exact size), with the app's "
                                        "looks on it. Off: the app's bead is laid on the same seam")
    cad_mesh: PointerProperty(type=bpy.types.Mesh)        # the CAD bead in the first part's coordinates (UV fr_weld)
    cad_source: PointerProperty(type=bpy.types.Object)    # the CAD part it came from (left out: its beads are welds)
    cad_how: StringProperty(default="")                  # "name" / "shape": how it was found
    cad_kind: StringProperty(default="")                 # FILLET / BUTT / OTHER, as measured
    cad_note: StringProperty(default="")                 # "legs 10 × 6 mm", "joins 3 parts" …
    cad_closed: BoolProperty(default=False)               # all round (also seams round in a loop)
    cad_parts: IntProperty(default=2)                     # how many parts it lies on
    cad_legs: FloatVectorProperty(size=2, default=(0.0, 0.0))
    cad_length: FloatProperty(default=0.0)
    cad_gap: FloatProperty(default=0.0)                  # task 0368: a square groove's root gap (m; 0: none)
    cad_metal: StringProperty(default="")                # the CAD material's metal ('' : from the parts)


def _symbols_changed(self, context):
    try:
        from . import weld_symbols
        weld_symbols.redraw()
    except Exception:  # noqa: BLE001
        pass


class FRWeldSettings(PropertyGroup):
    items: CollectionProperty(type=FRWeld)
    symbols: BoolProperty(name="Weld symbols", default=False, update=_symbols_changed,
                          description="Shows an ISO 2553 weld symbol beside each weld in the view (arrow, reference "
                                      "line, a5, length, all round, both sides, the process number). Off: no symbols")
    symbols_render: BoolProperty(name="Show in renders", default=False, update=_symbols_changed,
                                 description="Puts the weld symbols into rendered pictures and videos too, as labels "
                                             "pointing at the seams. Off: they show only in the view")
    index: IntProperty(name="Weld", default=0, description="The weld whose settings show below the list")
    picking: StringProperty(default="")          # "" / "A" / "B" / "PARTS": the picker's step
    preview: CollectionProperty(type=FRWeldSeam)
    count: IntProperty(default=0)


CLASSES = (FRWeldSeam, FRWeld, FRWeldSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.fresing_welds = PointerProperty(type=FRWeldSettings)
    from . import weld_symbols
    weld_symbols.register()                  # task 0320: the symbols' draw handler (does nothing while they are off)
    for lst, fn in ((bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.depsgraph_update_post, _depsgraph)):
        if fn not in lst:
            lst.append(fn)


def unregister():
    from . import weld_symbols
    weld_symbols.unregister()
    for lst, fn in ((bpy.app.handlers.load_post, _after_load), (bpy.app.handlers.depsgraph_update_post, _depsgraph)):
        while fn in lst:
            lst.remove(fn)
    if hasattr(bpy.types.Scene, "fresing_welds"):
        del bpy.types.Scene.fresing_welds
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def settings(scene=None):
    scene = scene or bpy.context.scene
    return scene.fresing_welds


def items(scene=None):
    return settings(scene).items


def find_item(scene, key: str):
    for it in items(scene):
        if it.key == key:
            return it
    return None


def owner_of_seam(seam):
    path = seam.path_from_id()
    scene = seam.id_data
    if not path.startswith("fresing_welds.items["):
        return None
    try:
        i = int(path.split("[", 1)[1].split("]", 1)[0])
        return scene.fresing_welds.items[i]
    except (ValueError, IndexError):
        return None


def active(scene=None):
    s = settings(scene)
    return s.items[s.index] if 0 <= s.index < len(s.items) else None


def is_weld(ob) -> bool:
    return ob is not None and ob.get(build.PROP_KIND) in KINDS


_INDEX: list = [None]     # task 0368: {weld key: [objects]} while many welds are made at once (``indexed``)


def objects_of(item) -> list:
    idx = _INDEX[0]
    if idx is not None:
        out = []
        for ob in idx.get(item.key, ()):
            try:
                if ob.get(build.PROP_KIND) in KINDS and ob.get(PROP_KEY) == item.key:
                    out.append(ob)
            except ReferenceError:                    # removed meanwhile
                pass
        return out
    return [ob for ob in bpy.data.objects if ob.get(build.PROP_KIND) in KINDS and ob.get(PROP_KEY) == item.key]


class indexed:
    """``with welds.indexed():`` – the weld objects are looked up in a table made once, not in every object of the
    file per weld (300 welds on a 2,000-object model: 2 s). Objects made meanwhile go into it (``_ensure_object``)."""

    def __enter__(self):
        if _INDEX[0] is None:
            idx: dict = {}
            for ob in bpy.data.objects:
                if ob.get(build.PROP_KIND) in KINDS:
                    idx.setdefault(ob.get(PROP_KEY), []).append(ob)
            _INDEX[0] = idx
            self.own = True
        else:
            self.own = False
        return self

    def __exit__(self, *exc):
        if self.own:
            _INDEX[0] = None
        return False


def web_objects(scene) -> list:
    """The beads the web 3D export takes (shown ones; not the heat zones)."""
    out = []
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) == KIND and ob.type == "MESH" and ob.data is not None and len(ob.data.polygons):
            try:
                if ob.visible_get():
                    out.append(ob)
            except RuntimeError:
                pass
    return out


def count(scene=None) -> int:
    s = settings(scene)
    n = len(s.items)
    if s.count != n:
        s.count = n
    return n


def part_name(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else "?"


def _faces(text: str) -> list:
    try:
        return [int(x) for x in json.loads(text or "[]")]
    except (TypeError, ValueError):
        return []


def describe(item) -> str:
    """'Plate – Fin · 2 seams · 0.41 m' for the list and the panel."""
    on = [s for s in item.seams if s.enabled]
    total = sum(s.length for s in on)
    return (f"{part_name(item.part_a)} – {part_name(item.part_b)} · {plural(len(on), 'seam')} · "
            f"{total * 1000:.0f} mm")


# ---------------------------------------------------------------------------
# finding the seams on real parts
# ---------------------------------------------------------------------------

def _np(m) -> np.ndarray:
    return np.array([list(r) for r in m], np.float64)


def mesh_tables(me):
    """(points (n, 3) part coordinates, triangles (m, 3), CAD face of each triangle)."""
    from . import hover
    _n, starts, tris, co = hover._mesh(me)
    face = web3d_faces.face_of_triangles(len(tris), starts)
    return np.asarray(co, np.float64), np.asarray(tris, np.int64), face


def side_of(ob, faces: list | None, to_a: np.ndarray) -> core.Side:
    pts, tris, face = mesh_tables(ob.data)
    pts = pts @ to_a[:3, :3].T + to_a[:3, 3]
    if np.linalg.det(to_a[:3, :3]) < 0:                      # a mirrored placement: the faces turned back the right way
        tris = tris[:, ::-1]
    picked = None if not faces else np.isin(face, faces)
    return core.Side(pts, tris, face, picked)


def _signature(item, faces_a, faces_b, whole, gap) -> tuple:
    a, b = item.part_a, item.part_b
    rel = _np(a.matrix_world.inverted() @ b.matrix_world)
    return (a.name, b.name, a.data.name, b.data.name, len(a.data.vertices), len(b.data.vertices), tuple(faces_a),
            tuple(faces_b), bool(whole), round(float(gap), 6), tuple(np.round(rel, 6).ravel()))


def find_raw(part_a, faces_a, part_b, faces_b, gap: float = core.GAP):
    """The seams between the picked faces (all faces when a list is empty), in part A's own coordinates, and the two
    sides."""
    to_a = _np(part_a.matrix_world.inverted() @ part_b.matrix_world)
    sa = side_of(part_a, faces_a, np.eye(4))
    sb = side_of(part_b, faces_b, to_a)
    seams = core.find_seams(sa, sb, gap=gap)
    return seams, sa, sb


def find(item, force: bool = False, prepare: bool = True):
    """(seams, side A, side B) of a weld: the seams kept in the project (``seam_data``) with the second part where it
    was when they were found (``rel``) – never where it happens to stand now (an exploded view, a pose). ``force`` or no
    kept seams: found now and kept (``refind``). ``prepare`` False: kept seams come with sides not yet prepared (a
    helper process prepares them, task 0368; nothing is kept for the next call)."""
    fa, fb = _faces(item.faces_a), _faces(item.faces_b)
    if item.from_cad and item.seam_data:
        force = False                         # task 0323: a CAD weld's seams are where its bead lies, never refound
    if force or not item.seam_data:
        rel = _np(item.part_a.matrix_world.inverted() @ item.part_b.matrix_world)
        got = find_raw(item.part_a, None if item.whole else fa, item.part_b, None if item.whole else fb, item.gap)
        _keep(item, got[0], rel)
        return got
    sig = (item.seam_data, item.part_a.data.name, item.part_b.data.name, len(item.part_a.data.vertices),
           len(item.part_b.data.vertices), tuple(fa), tuple(fb), item.whole)
    hit = _CACHE.get(item.key)
    if hit is not None and hit[0] == sig:
        return hit[1]
    rel = np.array(item.rel, np.float64).reshape(4, 4)
    sa = side_of(item.part_a, None if item.whole else fa, np.eye(4))
    sb = side_of(item.part_b, None if item.whole else fb, rel)
    if not prepare:
        return core.unpack_seams(item.seam_data), sa, sb
    sa.prepare()
    sb.prepare()
    got = (core.unpack_seams(item.seam_data), sa, sb)
    _CACHE[item.key] = (sig, got)
    return got


def _keep(item, seams, rel) -> None:
    was = _BUSY[0]
    _BUSY[0] = True
    try:
        item.seam_data = core.pack_seams(seams)
        item.rel = tuple(float(x) for x in np.asarray(rel).ravel())
    finally:
        _BUSY[0] = was
    _CACHE.pop(item.key, None)


def store_seams(coll, seams, keep=None) -> None:
    """Write found seams into a collection of ``FRWeldSeam``; ``keep``: earlier [(mid, kind, enabled)] – a seam within
    2 mm of an unticked one stays unticked."""
    coll.clear()
    for s in seams:
        it = coll.add()
        it.length, it.kind, it.closed, it.angle = s.length, s.kind, s.closed, s.angle()
        it.mid = tuple(float(x) for x in s.mid)
        if keep:
            for mid, kind, enabled in keep:
                if kind == s.kind and np.linalg.norm(np.asarray(mid) - s.mid) < 0.002:
                    it.enabled = enabled
                    break


# ---------------------------------------------------------------------------
# metals and defaults
# ---------------------------------------------------------------------------

def part_material(ob):
    if ob is None or ob.type != "MESH" or not ob.material_slots:
        return None
    return ob.material_slots[0].material


def metal_kind(ob) -> str:
    """``core.welds.metal_of`` of a part's look."""
    mat = part_material(ob)
    mid = mat.get("fr_material", "") if mat is not None else ""
    if mat is not None and mat.get("fr_src_material"):
        mid = mat["fr_src_material"]
    cat = materials_lib.get(mid).get("category", "") if mid else ""
    return core.metal_of(mid, cat)


def _thickness_mm(seams, sa, sb) -> float:
    ts = []
    for s in seams[:3]:
        c = s.corners[len(s.corners) // 2]
        for side, o, d, n in ((sa, c.oa, c.da, c.na), (sb, c.ob, c.db, c.nb)):
            t = core.thickness(side, o + d * 0.002, n)
            if t > 0:
                ts.append(t)
    return min(ts) * 1000.0 if ts else 0.0


def resolved(item) -> dict:
    """The metal, process and the rest the bead is built with (AUTO settings worked out)."""
    ka, kb = metal_kind(item.part_a), metal_kind(item.part_b)
    metal = item.metal if item.metal != "AUTO" else core.base_metal(ka)
    process = item.process
    if process == "AUTO":
        process = {"STEEL": "MAG", "STAINLESS": "TIG", "ALUMINIUM": "MIG"}[metal]
    zinc = "GALVANISED" in (ka, kb)
    src = item.part_a if item.paint_from == "A" else item.part_b
    wear = 0.0
    mat = part_material(src)
    if mat is not None:
        wear = float(mat.get("fr_wear", 0.0) or 0.0)
    group_rust = float(mat.get("fr_rust", 0.0) or 0.0) if mat is not None else 0.0   # 0318's Rust slider, when there
    rust = max(item.rust, min(1.0, group_rust))
    r = core.rust_of(metal, item.finish, rust, wear, zinc, item.zinc_sprayed, item.pickled)
    return {"metal": metal, "process": process, "finish": item.finish, "rust": r, "wear": wear, "zinc": zinc,
            "group_rust": group_rust,
            "paint_src": mat if item.finish == "PAINTED" else None, "kinds": (ka, kb)}


def warning(item) -> str:
    if item.part_a is None or item.part_b is None:
        return ""
    return core.warning(metal_kind(item.part_a), metal_kind(item.part_b))


# ---------------------------------------------------------------------------
# the objects
# ---------------------------------------------------------------------------

def _object_name(item, heat: bool) -> str:
    return f"Weld {item.name}" + (" heat" if heat else "")


def _hide_driver(ob, parts, prop: str) -> None:
    try:
        ob.driver_remove(prop)
    except TypeError:
        pass
    drv = ob.driver_add(prop).driver
    drv.type = "MAX"
    for k, (target, path) in enumerate([(p, "hide_render") for p in parts] + [(ob, f'["{PROP_OFF}"]')]):
        var = drv.variables.new()
        var.name = f"v{k}"
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = target
        var.targets[0].data_path = path


def _object(item, heat: bool):
    kind = HEAT_KIND if heat else KIND
    for ob in objects_of(item):
        if ob.get(build.PROP_KIND) == kind:
            return ob
    return None


def _ensure_object(item, heat: bool, me):
    part = item.part_a
    ob = _object(item, heat)
    if ob is not None and ob.parent is not part:
        bpy.data.objects.remove(ob)
        ob = None
    if ob is None:
        ob = bpy.data.objects.new(_object_name(item, heat), me)
        cols = list(part.users_collection) or [bpy.context.scene.collection]
        cols[0].objects.link(ob)
        ob.parent = part
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = Matrix.Identity(4)
        ob[build.PROP_KIND] = HEAT_KIND if heat else KIND
        ob[PROP_KEY] = item.key
        if _INDEX[0] is not None:
            _INDEX[0].setdefault(item.key, []).append(ob)
        ob.hide_select = True
        ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
        if heat and hasattr(ob, "visible_shadow"):
            ob.visible_shadow = False
    elif ob.data is not me:
        old = ob.data
        ob.data = me
        if old is not None and old.users == 0:
            bpy.data.meshes.remove(old)
    ob[PROP_OFF] = 1 if item.hidden else 0
    for prop in ("hide_render", "hide_viewport"):
        _hide_driver(ob, [item.part_a, item.part_b], prop)
    return ob


def _write_mesh(name: str, verts, faces, uvs, ends=None, smooth: bool = True):
    me = bpy.data.meshes.new(name)
    v = np.asarray(verts, np.float32).reshape(-1, 3)
    me.vertices.add(len(v))
    me.vertices.foreach_set("co", v.ravel())
    sizes = np.array([len(f) for f in faces], np.int32)
    loops = np.array([i for f in faces for i in f], np.int32)
    me.loops.add(len(loops))
    me.loops.foreach_set("vertex_index", loops)
    me.polygons.add(len(faces))
    starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32) if len(sizes) else np.zeros(0, np.int32)
    me.polygons.foreach_set("loop_start", starts)
    me.update(calc_edges=True)
    if len(faces):
        uv = me.uv_layers.new(name="fr_weld")
        uv.data.foreach_set("uv", np.asarray(uvs, np.float32).ravel())
        if ends is not None:
            ue = me.uv_layers.new(name="fr_weld_end")
            ue.data.foreach_set("uv", np.asarray(ends, np.float32).ravel())
        me.uv_layers.active = uv
        me.polygons.foreach_set("use_smooth", np.full(len(faces), smooth, bool))
    me.validate(clean_customdata=False)
    return me


def look_of(item, seam_kind: str = "FILLET") -> core.Look:
    r = resolved(item)
    kind = item.kind
    size = item.butt_width if (kind == "BUTT" or (kind == "AUTO" and seam_kind == "BUTT")) else item.size
    heat = core.heat_width(r["metal"], item.size)
    return core.Look(size=size, kind=kind, finish=item.finish, craters=item.craters, intermittent=item.intermittent,
                     length=item.length, pitch=item.pitch, heat=heat)


def _materials(item):
    """The bead's and the heat zone's materials for the weld's settings and its parts' looks (wear, group Rust)."""
    from . import weld_looks
    r = resolved(item)
    item["fr_rust_seen"] = round(float(r.get("group_rust", 0.0)), 4)
    if item.finish == "PAINTED":
        bead_mat = weld_looks.painted(r["paint_src"], r["process"], r["rust"])
    else:
        bead_mat = weld_looks.bead_material(weld_looks.bead_look(r["metal"], r["process"], item.finish,
                                                                 item.pickled, item.heat_tint, r["rust"]))
    heat_mat = weld_looks.heat_material(weld_looks.heat_look(
        r["metal"], r["process"], item.finish, item.pickled, item.heat_tint, item.spatter, r["rust"],
        core.heat_width(r["metal"], item.size), r["wear"]))
    return bead_mat, heat_mat


def restyle(item) -> bool:
    """Task 0318: only the materials again (the group's Rust slider moved): the bead's shape stays."""
    if item.lost:
        return False
    bead_mat, heat_mat = _materials(item)
    done = False
    for heat, mat in ((False, bead_mat), (True, heat_mat)):
        ob = _object(item, heat)
        if ob is not None and ob.data is not None:
            if ob.data.materials:
                ob.data.materials[0] = mat
            else:
                ob.data.materials.append(mat)
            done = True
    return done


def follow_rust(scene) -> int:
    """Task 0318: welds whose part's group Rust changed since their materials were made get them again."""
    n = 0
    for it in items(scene):
        if it.lost:
            continue
        want = round(float(resolved(it).get("group_rust", 0.0)), 4)
        if abs(float(it.get("fr_rust_seen", 0.0)) - want) > 1e-4 and restyle(it):
            n += 1
    return n


def rebuild(item, refind_seams: bool = False) -> bool:
    """Make the weld's bead and heat zone again from its seams and settings. False when it cannot (lost)."""
    plan = _rebuild_plan(item, refind_seams)
    if plan is None:
        return False
    return _rebuild_write(item, plan, [core.bead(*job) for job in plan["jobs"]])


def rebuild_many(scene, keys, pool=None) -> int:
    """``rebuild`` of the welds with these keys; with ``pool`` (``core.weld_pool.Pool``) their beads and heat zones
    are worked out in helper processes (the same meshes, task 0368). Returns how many were made."""
    plans = []
    for key in keys:
        it = find_item(scene, key)
        plan = _rebuild_plan(it, False, prepare=False) if it is not None else None
        if plan is not None:
            plans.append((key, plan))
    if pool is not None:
        results = pool.map("welds.job_beads", [(plan["jobs"],) for _k, plan in plans])
    else:
        results = [core.job_beads({}, plan["jobs"]) for _k, plan in plans]
    made = 0
    for (key, plan), meshes in zip(plans, results):
        it = find_item(scene, key)
        if it is not None and _rebuild_write(it, plan, meshes):
            made += 1
    return made


def _rebuild_plan(item, refind_seams: bool, prepare: bool = True):
    """The first half of ``rebuild``: the checks, the seams and the jobs for ``core.bead`` – or None (lost)."""
    t0 = time.perf_counter()
    if item.part_a is None or item.part_b is None or item.part_a.data is None or item.part_b.data is None:
        _set_lost(item, "One of its parts is not in the model any more: pick its faces again")
        return None
    if item.lost:
        return None
    try:
        seams, sa, sb = find(item, force=refind_seams, prepare=prepare)
    except Exception as exc:  # noqa: BLE001 - a broken mesh must never break the panel
        _set_lost(item, f"Its seams could not be found ({exc})")
        return None
    _BUSY[0] = True
    try:
        if len(item.seams) != len(seams):                 # (an older or damaged list: the ticks follow the seams)
            keep = [(tuple(s.mid), s.kind, s.enabled) for s in item.seams]
            store_seams(item.seams, seams, keep)
    finally:
        _BUSY[0] = False
    ticked = [t.enabled for t in item.seams]
    other = item.from_cad and item.cad_kind == "OTHER"          # task 0323: a CAD bead with no seam: its shape only
    jobs = []
    for s, tick in zip(seams, item.seams):
        if not tick.enabled or other:
            continue
        ends = tuple(seams[j[0]].corners[0 if j[1] == 0 else -1]
                     if j is not None and j[0] < len(seams) and ticked[j[0]] else None for j in s.joins)
        jobs.append((s, look_of(item, s.kind), sa, sb, ends))
    return {"t0": t0, "jobs": jobs, "other": other}


def _rebuild_write(item, plan, meshes) -> bool:
    """The second half of ``rebuild``: the bead's and heat zone's objects from the worked-out meshes."""
    t0, other = plan["t0"], plan["other"]
    _BUSY[0] = True
    try:
        verts_b, faces_b, uv_b = [], [], []
        verts_h, faces_h, uv_h, end_h = [], [], [], []
        length = 0.0
        for m in meshes:
            length += m.length
            k = 0
            remap_b, remap_h = {}, {}
            for f, mat in zip(m.faces, m.mat):
                corners = m.uv[k:k + len(f)]
                ends = m.end[k:k + len(f)]
                k += len(f)
                if mat == 0:
                    vb, ff, uu = verts_b, faces_b, uv_b
                    rm = remap_b
                else:
                    vb, ff, uu = verts_h, faces_h, uv_h
                    rm = remap_h
                    end_h.extend(ends)
                idx = []
                for i in f:
                    if i not in rm:
                        rm[i] = len(vb)
                        vb.append(m.verts[i])
                    idx.append(rm[i])
                ff.append(idx)
                uu.extend(corners)
        if item.from_cad:                                 # task 0323: the bead's own shape from the CAD file
            from . import weld_cad
            got = weld_cad.bead_geometry(item)
            if got is not None:
                verts_b, faces_b, uv_b = got
            if got is not None or other:
                length = item.cad_length
        bead_mat, heat_mat = _materials(item)
        for heat, (vv, ff, uu) in ((False, (verts_b, faces_b, uv_b)), (True, (verts_h, faces_h, uv_h))):
            ob = _object(item, heat)
            if not ff:
                if ob is not None:
                    me = ob.data
                    bpy.data.objects.remove(ob)
                    if me is not None and me.users == 0:
                        bpy.data.meshes.remove(me)
                continue
            me = _write_mesh(_object_name(item, heat), vv, ff, uu, end_h if heat else None)
            me.materials.append(heat_mat if heat else bead_mat)
            ob = _ensure_object(item, heat, me)
        item.note = ""
        item["fr_ms"] = (time.perf_counter() - t0) * 1000.0
        item["fr_length"] = length
    finally:
        _BUSY[0] = False
    _sync_cut_and_fade(item)
    return True


def _sync_cut_and_fade(item) -> None:
    """A cut or faded first part: its new weld objects are cut / faded too (their materials wrapped, the part's fade
    and X-ray values copied)."""
    part = item.part_a
    if part is None:
        return
    try:
        if any(k.startswith("fr_cut_") for k in part.keys()):
            from . import section
            section.sync(bpy.context.scene)
        from . import fade
        if fade.FADE in part:
            fade.prepare(part)
            for ob in objects_of(item):
                for k in (fade.FADE, fade.LOOK, fade.XRAY, fade.XCOLOR, fade.XSTRENGTH):
                    if k in part:
                        ob[k] = part[k]
                ob.update_tag()
    except Exception:  # noqa: BLE001 - a look must never stop a weld
        pass


def _set_lost(item, why: str) -> None:
    _BUSY[0] = True
    try:
        item.lost = True
        item.note = why
    finally:
        _BUSY[0] = False
    for ob in objects_of(item):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def refind(item) -> bool:
    """Find the seams again (the gap changed, a part moved): the ticks of seams that are still there are kept."""
    if item.part_a is None or item.part_b is None or item.from_cad:
        return rebuild(item)
    _CACHE.pop(item.key, None)
    seams, _sa, _sb = find(item, force=True)
    keep = [(tuple(s.mid), s.kind, s.enabled) for s in item.seams]
    _BUSY[0] = True
    try:
        store_seams(item.seams, seams, keep)
    finally:
        _BUSY[0] = False
    return rebuild(item)


def _new_key(scene) -> str:
    have = {it.key for it in items(scene)}
    n = 1
    while f"w{n}" in have:
        n += 1
    return f"w{n}"


def _unique_name(scene, base: str) -> str:
    have = {it.name for it in items(scene)}
    if base not in have:
        return base
    n = 2
    while f"{base} {n}" in have:
        n += 1
    return f"{base} {n}"


def make(scene, part_a, faces_a, part_b, faces_b, whole: bool = False, ticks=None, gap: float = core.GAP):
    """A new weld between ``part_a``'s picked faces and ``part_b``'s (``whole``: the two whole parts). ``ticks``: which
    seams to weld (default all). Returns the item; raises ValueError with a plain reason."""
    if part_a is None or part_b is None or part_a == part_b:
        raise ValueError("Pick faces on two different parts")
    for p in (part_a, part_b):
        if p.type != "MESH" or p.data is None or p.get(build.PROP_KIND) != "part":
            raise ValueError(f"'{part_name(p)}' is not a part of the model")
    faces_a = sorted(set(int(f) for f in (faces_a or [])))
    faces_b = sorted(set(int(f) for f in (faces_b or [])))
    if not whole and (not faces_a or not faces_b):
        raise ValueError("Pick at least one face on each part")
    seams, sa, sb = find_raw(part_a, None if whole else faces_a, part_b, None if whole else faces_b, gap)
    if not seams:
        raise ValueError(f"'{part_name(part_a)}' and '{part_name(part_b)}' do not meet there (not even with a gap "
                         f"of {gap * 1000:.1f} mm): pick faces that touch")
    s = settings(scene)
    item = s.items.add()
    _BUSY[0] = True
    try:
        item.key = _new_key(scene)
        item.name = _unique_name(scene, f"{part_name(part_a)} – {part_name(part_b)}")
        item.part_a, item.part_b = part_a, part_b
        item.whole = whole
        item.gap = gap
        item.faces_a, item.faces_b = json.dumps(faces_a), json.dumps(faces_b)
        pa, ta, fa = mesh_tables(part_a.data)
        pb, tb, fb = mesh_tables(part_b.data)
        item.prints_a = json.dumps(core.face_prints(pa, ta, fa, faces_a if not whole else []))
        item.prints_b = json.dumps(core.face_prints(pb, tb, fb, faces_b if not whole else []))
        ka, kb = metal_kind(part_a), metal_kind(part_b)
        d = core.defaults(ka, kb, _thickness_mm(seams, sa, sb))
        item.size = d["size"] / 1000.0
        item.butt_width = d["butt_width"] / 1000.0
        item.finish = d["finish"]
        item.paint_from = d["paint_from"]
        item.found_metal = d["metal"]
        store_seams(item.seams, seams)
        if ticks is not None:
            for it, on in zip(item.seams, ticks):
                it.enabled = bool(on)
    finally:
        _BUSY[0] = False
    _keep(item, seams, _np(part_a.matrix_world.inverted() @ part_b.matrix_world))
    s.index = len(s.items) - 1
    count(scene)
    rebuild(item)
    return item


def remove(scene, item) -> None:
    if item.from_cad:
        from . import weld_cad
        weld_cad.remove_mesh(item)
    for ob in objects_of(item):
        me = ob.data
        bpy.data.objects.remove(ob)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    _CACHE.pop(item.key, None)
    s = settings(scene)
    for i, it in enumerate(s.items):
        if it.key == item.key:
            s.items.remove(i)
            break
    s.index = min(s.index, len(s.items) - 1)
    count(scene)
    from . import weld_looks
    weld_looks.unused_cleanup()


def set_faces(item, faces_a, faces_b, part_a=None, part_b=None) -> None:
    """Pick again: new faces (and parts) for a weld; its settings stay."""
    _BUSY[0] = True
    try:
        if part_a is not None:
            item.part_a = part_a
        if part_b is not None:
            item.part_b = part_b
        item.whole = False
        item.faces_a, item.faces_b = json.dumps(sorted(faces_a)), json.dumps(sorted(faces_b))
        pa, ta, fa = mesh_tables(item.part_a.data)
        pb, tb, fb = mesh_tables(item.part_b.data)
        item.prints_a = json.dumps(core.face_prints(pa, ta, fa, faces_a))
        item.prints_b = json.dumps(core.face_prints(pb, tb, fb, faces_b))
        item.lost = False
        item.note = ""
    finally:
        _BUSY[0] = False
    for ob in objects_of(item):
        if ob.parent is not item.part_a:
            bpy.data.objects.remove(ob)
    refind(item)


# ---------------------------------------------------------------------------
# copies (task 0320): a pasted copy takes the welds whose two parts are both in it
# ---------------------------------------------------------------------------

def for_copy(scene, names) -> tuple[list, list]:
    """Which welds a copy of the objects ``names`` takes along: (weld keys, lines of what is left out). A weld whose
    two parts are both in the copy comes along; one with only one part inside is left out (said)."""
    keys, left = [], []
    for it in items(scene):
        a = it.part_a.name if it.part_a is not None else None
        b = it.part_b.name if it.part_b is not None else None
        ina, inb = a in names, b in names
        if ina and inb:
            keys.append(it.key)
        elif ina or inb:
            out = part_name(it.part_b if ina else it.part_a)
            left.append(f"Weld '{it.name}': '{out}' is outside the copy – not copied")
    return keys, left


def copy_to(scene, keys, copies: dict) -> list:
    """Copies of the welds ``keys`` on the copied parts (``copies``: original object name -> copy). The parts share
    their meshes with the originals, so the picked faces, the seams kept where they were found (``seam_data``, ``rel``)
    and every setting stay true: only the parts change. Returns the new weld keys."""
    s = settings(scene)
    new = []
    for key in keys:
        src = find_item(scene, key)
        if src is None or src.part_a is None or src.part_b is None:
            continue
        a, b = copies.get(src.part_a.name), copies.get(src.part_b.name)
        if a is None or b is None:
            continue
        nk = _new_key(scene)
        name = _copy_name(scene, src.name)
        dst = s.items.add()                 # (an item held across add() is no longer valid: CLAUDE.md 8)
        src = find_item(scene, key)
        _BUSY[0] = True
        try:
            for k in src.keys():
                v = src[k]
                if hasattr(v, "to_dict"):
                    v = v.to_dict()
                elif hasattr(v, "to_list"):
                    v = v.to_list()
                dst[k] = v
            dst.key, dst.name = nk, name
            dst.part_a, dst.part_b = a, b
            if src.get("fr_rust_seen") is not None:
                dst["fr_rust_seen"] = src["fr_rust_seen"]
        finally:
            _BUSY[0] = False
        new.append(nk)
    for nk in new:
        it = find_item(scene, nk)
        if not it.lost:
            rebuild(it)
    count(scene)
    return new


def _copy_name(scene, base: str) -> str:
    """'Plate – Fin' -> 'Plate – Fin (2)' (the copy's own number, as copied parts and joints are named)."""
    from . import copy
    return copy.next_name(base, {it.name for it in items(scene)})


# ---------------------------------------------------------------------------
# motion: welded parts that move apart
# ---------------------------------------------------------------------------

def mover(ob):
    """The joint motion empty nearest above ``ob`` (what moves it), or None (it stands on the model's base)."""
    p = ob.parent if ob is not None else None
    while p is not None:
        if p.get(build.PROP_KIND) == "joint":
            return p
        p = p.parent
    return None


def moves_apart(item) -> bool:
    if item.part_a is None or item.part_b is None:
        return False
    return mover(item.part_a) is not mover(item.part_b)


def move_as_one(scene, item) -> str:
    """Make the second part move with the first: into the first part's joint, or out of its own joint when the first
    part has none. Returns what was done (words)."""
    from . import joints
    ma = mover(item.part_a)
    jb = joints.joint_of_object(scene, item.part_b)
    if ma is not None:
        ja = None
        for j in scene.fresing.joints:
            if j.motion is ma:
                ja = j
                break
        if ja is None:
            raise RuntimeError("The first part's joint was not found")
        joints.add_members(scene, ja, [item.part_b])
        return f"'{part_name(item.part_b)}' now moves with joint '{ja.name}'"
    if jb is not None:
        joints.remove_members(scene, jb, [item.part_b])
        return f"'{part_name(item.part_b)}' left joint '{jb.name}': it stands with the first part now"
    raise RuntimeError("The second part is moved by a joint further up the model: take it out there (4 Motion)")


# ---------------------------------------------------------------------------
# model update, load, paint
# ---------------------------------------------------------------------------

def carry_over(scene, pairs) -> tuple[list, object]:
    """After a model update: welds of matched parts point at the new parts and find their faces again by their
    prints; a weld whose part or faces are gone is listed ('lost its faces – pick again'), never dropped. Returns
    (report lines, undo) – ``undo()`` puts every weld back on the old parts (the update failed later)."""
    by_name = {o.name: n for o, n in pairs}
    updated = {build.model_root_of(o) for o, _n in pairs} - {None}   # the models being updated (task 0320)

    def new_of(ob):
        """The part's new revision; the part itself when it belongs to a model that is not updated now (another
        model, a copy that is not in this update); None when it is gone."""
        if ob is None:
            return None
        if ob.name in by_name:
            return by_name[ob.name]
        return None if build.model_root_of(ob) in updated else ob

    before = []
    notes = []
    for it in items(scene):
        before.append((it, it.part_a, it.part_b, it.faces_a, it.faces_b, it.lost, it.note))
    for it in items(scene):
        if it.from_cad:
            continue                                      # task 0323: blender/weld_cad.carry_over follows its bead
        if not ((it.part_a is not None and it.part_a.name in by_name)
                or (it.part_b is not None and it.part_b.name in by_name)
                or (it.part_a is not None and build.model_root_of(it.part_a) in updated)
                or (it.part_b is not None and build.model_root_of(it.part_b) in updated)):
            continue                                      # a weld of another model: left as it is (task 0320)
        for ob in objects_of(it):                         # the old beads go; the new parts get new ones
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
        _CACHE.pop(it.key, None)
        if it.lost:
            continue
        na, nb = new_of(it.part_a), new_of(it.part_b)
        if na is None or nb is None:
            gone = part_name(it.part_a if na is None else it.part_b)
            _BUSY[0] = True
            it.lost, it.note = True, f"Weld lost its faces – pick again ('{gone}' is not in the new model)"
            _BUSY[0] = False
            notes.append(f"Weld '{it.name}': '{gone}' is not in the new model – pick its faces again (3 Looks > Welds)")
            continue
        new_faces = []
        ok = True
        for ob, text in ((na, it.prints_a), (nb, it.prints_b)):
            prints = {int(k): v for k, v in json.loads(text or "{}").items()}
            if it.whole:
                new_faces.append([])
                continue
            p, t, f = mesh_tables(ob.data)
            got = core.match_faces(prints, p, t, f)
            if not got or any(v is None for v in got.values()):
                ok = False
                break
            new_faces.append(sorted(got.values()))
        _BUSY[0] = True
        try:
            it.part_a, it.part_b = na, nb
            if ok:
                it.faces_a, it.faces_b = json.dumps(new_faces[0]), json.dumps(new_faces[1])
            else:
                it.lost, it.note = True, "Weld lost its faces – pick again (its faces changed in the new model)"
        finally:
            _BUSY[0] = False
        if not ok:
            notes.append(f"Weld '{it.name}': its faces changed in the new model – pick them again (3 Looks > Welds)")
            continue
        n_before = sum(1 for s in it.seams if s.enabled)
        if refind(it) and sum(1 for s in it.seams if s.enabled) != n_before:
            notes.append(f"Weld '{it.name}': its parts meet differently now ({plural(len(it.seams), 'seam')}) – "
                         "check its seams (3 Looks > Welds)")

    def undo():
        for it, a, b, fa, fb, lost, note in before:
            try:
                _BUSY[0] = True
                it.part_a, it.part_b, it.faces_a, it.faces_b, it.lost, it.note = a, b, fa, fb, lost, note
            except ReferenceError:
                continue
            finally:
                _BUSY[0] = False
            _CACHE.pop(it.key, None)
            if not lost:
                rebuild(it)
    return notes, undo


def rebuild_all(scene) -> int:
    n = 0
    for it in items(scene):
        if not it.lost and rebuild(it):
            n += 1
    return n


def sync_paint(scene) -> int:
    """Painted welds whose part's look changed (paint scheme, colour, wear): their bead material is made again."""
    from . import weld_looks
    n = 0
    for it in items(scene):
        if it.lost or it.finish != "PAINTED":
            continue
        ob = _object(it, False)
        if ob is None or ob.data is None or not ob.data.materials:
            continue
        cur = ob.data.materials[0]
        src = part_material(it.part_a if it.paint_from == "A" else it.part_b)
        if cur is None or cur.get(weld_looks.SRC) != weld_looks.source_signature(src):
            rebuild(it)
            n += 1
    return n


def lost_parts(scene) -> int:
    """Welds whose part was removed (2 Structure > Remove, a model update) are marked lost. Returns how many changed."""
    n = 0
    for it in items(scene):
        if not it.lost and (it.part_a is None or it.part_b is None
                            or it.part_a.name not in scene.objects or it.part_b.name not in scene.objects):
            _set_lost(it, "Weld lost its faces – pick again (one of its parts was removed)")
            n += 1
    return n


@persistent
def _after_load(_dummy=None):
    _CACHE.clear()


_LAST = {"t": 0.0}


@persistent
def _depsgraph(scene, depsgraph):
    """A painted weld follows its part's paint: checked when materials changed (cheap: a few string compares)."""
    if _BUSY[0] or not getattr(scene, "fresing_welds", None) or not len(scene.fresing_welds.items):
        return
    try:
        if not depsgraph.id_type_updated("MATERIAL"):
            return
    except Exception:  # noqa: BLE001
        return
    now = time.monotonic()
    if now - _LAST["t"] < 0.2:
        return
    _LAST["t"] = now
    try:
        with indexed():                          # task 0368: one look through the objects, not one per weld
            sync_paint(scene)
            follow_rust(scene)                   # task 0318: the group's Rust slider
    except Exception:  # noqa: BLE001 - never break an update
        pass


def stats(scene=None) -> dict:
    """Numbers for the panel, the PC check and tests: welds, seams welded, metres, triangles."""
    s = settings(scene)
    seams = sum(1 for it in s.items for x in it.seams if x.enabled)
    tris = 0
    for ob in bpy.data.objects:
        if ob.get(build.PROP_KIND) in KINDS and ob.data is not None:
            tris += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return {"welds": len(s.items), "seams": seams, "metres": sum(float(it.get("fr_length", 0.0)) for it in s.items),
            "lost": sum(1 for it in s.items if it.lost), "triangles": tris}


# ---------------------------------------------------------------------------
# the test weldment (tour stop, PC check, guide pictures, tests): one set-up for all
# ---------------------------------------------------------------------------

def part_named(scene, name: str):
    return next((o for o in build.iter_parts(scene) if o.get(build.PROP_NAME) == name), None)


def face_at(ob, point, normal) -> int:
    """The CAD face of ``ob`` through this world point (m) facing this way (-1: none)."""
    p, t, f = mesh_tables(ob.data)
    m = _np(ob.matrix_world)
    w = p @ m[:3, :3].T + m[:3, 3]
    v = w[t]
    n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-18)
    q = np.asarray(point, float)
    ok = (n @ np.asarray(normal, float) > 0.99) & (np.abs(((q - v[:, 0]) * n).sum(1)) < 1e-4)
    return int(np.bincount(f[ok]).argmax()) if ok.any() else -1


def pick_test_weld(scene):
    """The test weldment's base plate top + the fin's +y side, picked as a user picks them (``ops_welds.Picker``):
    one fillet 200 mm long. Returns the weld."""
    from . import ops_welds
    base, fin = part_named(scene, "BASE PLATE"), part_named(scene, "FIN")
    if base is None or fin is None:
        raise RuntimeError("the test weldment is not in the project")
    pk = ops_welds.start(scene)
    try:
        for ob, pt, nrm in ((base, (0.10, 0.10, 0.012), (0, 0, 1)), (fin, (0.15, 0.155, 0.05), (0, 1, 0))):
            why = pk.click(ob, face_at(ob, pt, nrm))
            if why:
                raise RuntimeError(why)
            why = pk.next()
            if why:
                raise RuntimeError(why)
        return pk.item
    finally:
        ops_welds.finish(scene)


TEST_WELDS = (   # (first part, second part, settings): every look once
    ("BASE PLATE", "FIN", {"finish": "PAINTED"}),
    ("BASE PLATE", "GUSSET", {"finish": "AS_WELDED", "spatter": True}),
    ("FIN", "GUSSET", {"finish": "AS_WELDED", "rust": 0.6}),
    ("BASE PLATE", "POST", {"finish": "AS_WELDED", "metal": "STAINLESS"}),
    ("BASE PLATE", "BRANCH", {"finish": "AS_WELDED", "metal": "STAINLESS", "pickled": True}),
    ("BRANCH", "MAIN TUBE", {"finish": "AS_WELDED", "metal": "ALUMINIUM"}),
    ("BASE PLATE", "EXTENSION PLATE", {"finish": "GROUND"}),
)


def set_up_test_model(scene) -> list:
    """Every joint of the test weldment welded the quick way, each with another look (``TEST_WELDS``). Returns the
    weld keys in that order."""
    keys = []
    for a, b, _kw in TEST_WELDS:
        keys.append(make(scene, part_named(scene, a), [], part_named(scene, b), [], whole=True).key)
    for key, (_a, _b, kw) in zip(keys, TEST_WELDS):
        it = find_item(scene, key)
        for k, v in kw.items():
            setattr(it, k, v)
    return keys
