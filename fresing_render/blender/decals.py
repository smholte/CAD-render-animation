"""Decals: logos, text, type plates and stickers on the model itself (task 0024).

Where things are stored
-----------------------
* A decal on every copy of a part: an item of ``Mesh.fresing_decals`` on the part's mesh (all
  copies share the mesh). A decal on one copy only: an item of ``Object.fresing_decals`` on that
  copy. Each item (``FRDecal``) holds what the decal shows and where it lies, in the part's own
  coordinates: the CAD face, a point on it (``anchor``), the face's ``normal`` there and the
  decal's ``up`` direction; moving (``offset_x/y``), turning (``angle``) and size come on top.
* What shows in the view and in renders: a *decal object* per copy and decal, a child of the
  part (it moves, turns and is exploded with it), ``fr_kind = "decal"``, not selectable (a click
  on it selects the part). Its mesh – the face cut to the decal's outline, lifted 0.2 mm, see
  ``core/decal_geometry.py`` – is shared by the copies.
* It hides with its part: drivers on ``hide_render`` / ``hide_viewport`` take the larger of the
  part's ``hide_render`` and the decal's own ``fr_off`` (switched off in the list). Plain MAX
  drivers: they work with "Auto Run Python Scripts" off, in the view, in animations and in the
  background render queue.
* The picture: an image file (packed into the project, so the queue and other PCs have it) or
  masks made in code (text, stickers, see ``core/decal_art.py``) that the material colours.
  The material is plain nodes.
"""

from __future__ import annotations

import os
import uuid

import bpy
import numpy as np
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty,
                       IntProperty, PointerProperty, StringProperty)
from mathutils import Matrix, Vector

from ..core import decal_art as A
from ..core import decal_geometry as G
from ..core.words import plural
from . import build, faces

KIND = "decal"                     # fr_kind of a decal object
PROP_KEY = "fr_decal"              # on a decal object: the key of its decal
PROP_OFF = "fr_off"                # on a decal object: 1 when the decal is switched off
LIBRARY_FOLDERS = ("Logos", "Stickers")
PICTURE_TYPES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".tga", ".exr")
MIN_SIZE = 0.001                   # m

KIND_ITEMS = [
    ("PICTURE", "Picture", "A logo or picture from a file (PNG, JPG…), e.g. from the library"),
    ("TEXT", "Text", "Text you type: a name, a serial number, a slogan"),
    ("STICKER", "Sticker", "A ready-made sticker: CE mark, warning signs, arrows, type plate"),
]
STICKER_ITEMS = [(s.key, s.label, s.description) for s in A.STICKERS]
FINISH_ITEMS = [
    ("MATT", "Matt", "Like a matt printed sticker: no shine"),
    ("SATIN", "Satin", "Like most vinyl stickers: a soft shine"),
    ("GLOSS", "Gloss", "Like a glossy sticker or a lacquered logo"),
    ("METAL", "Metal", "Like a printed aluminium plate (type plates)"),
]
FINISH = {"MATT": (0.0, 0.6, 0.0), "SATIN": (0.0, 0.35, 0.0), "GLOSS": (0.0, 0.15, 0.4), "METAL": (1.0, 0.32, 0.0)}


# =============================================================================
# what a decal is (stored in the project)
# =============================================================================

_GUARD: set = set()


def _changed(what: str):
    """Update callback: the decal's picture, shape or material must follow a changed setting."""
    def update(self, context):
        if self.key in _GUARD:
            return
        try:
            if what == "picture":
                remake_picture(self)
                rebuild(self)
            elif what == "shape":
                rebuild(self)
            elif what == "material":
                update_material(self)
            elif what == "visible":
                for ob in decal_objects_of(self):
                    ob[PROP_OFF] = 1 if self.hidden else 0
                    ob.update_tag()
        except Exception as exc:          # a setting must never break the panel
            print("Fresing decal:", exc)
    return update


def _width_changed(self, context):
    if self.key not in _GUARD and self.keep_ratio and self.aspect > 0:
        _set_quiet(self, "height", self.width * self.aspect)
    _changed("shape")(self, context)


def _height_changed(self, context):
    if self.key not in _GUARD and self.keep_ratio and self.aspect > 0:
        _set_quiet(self, "width", self.height / self.aspect)
    _changed("shape")(self, context)


def _ratio_changed(self, context):
    if self.key not in _GUARD and self.keep_ratio and self.aspect > 0:
        _set_quiet(self, "height", self.width * self.aspect)
        rebuild(self)


def _set_quiet(item, attr: str, value) -> None:
    """Set a setting without running its update (no endless width <-> height loop)."""
    _GUARD.add(item.key)
    try:
        setattr(item, attr, value)
    finally:
        _GUARD.discard(item.key)


def _name_changed(self, context):
    if self.key in _GUARD:
        return
    for ob in decal_objects_of(self):
        part = ob.parent
        ob.name = _object_name(self, part)


class FRDecal(bpy.types.PropertyGroup):
    # ---- identity ----
    name: StringProperty(name="Name", default="Decal", update=_name_changed,
                         description="Name of this decal in the lists (only for you: it is not shown on the model)")
    key: StringProperty()
    kind: EnumProperty(items=KIND_ITEMS, default="PICTURE")

    # ---- what it shows ----
    picture: PointerProperty(type=bpy.types.Image)
    source: StringProperty(
        name="Picture", subtype="FILE_PATH", update=_changed("picture"),
        description="The picture file this decal shows. Pick another file to change the picture: place, size and "
                    "turn stay. The picture is kept inside the project, so renders work without the file")
    text: StringProperty(
        name="Text", default="Text", update=_changed("picture"),
        description="The text on the decal. Type | where a new line should start, e.g. Fresing|CNC 400")
    font: StringProperty(
        name="Font file", subtype="FILE_PATH", update=_changed("picture"),
        description="The font of the text: a .ttf or .otf file. Empty: the app's own font. The button on the right "
                    "lists the fonts found on this PC")
    sticker: EnumProperty(name="Sticker", items=STICKER_ITEMS, update=_changed("picture"),
                          description="Which ready-made sticker this decal shows")
    plate_company: StringProperty(name="Company", default="Company", update=_changed("picture"),
                                  description="Top line of the type plate: the company that built the machine")
    plate_type: StringProperty(name="Type", default="Type 1", update=_changed("picture"),
                               description="Type or model name on the type plate")
    plate_serial: StringProperty(name="Serial no.", default="0001", update=_changed("picture"),
                                 description="Serial number on the type plate")
    plate_year: StringProperty(name="Year", default="2026", update=_changed("picture"),
                               description="Year of manufacture on the type plate")
    plate_weight: StringProperty(name="Weight", default="1,000 kg", update=_changed("picture"),
                                 description="Weight on the type plate, with its unit (e.g. 1,250 kg)")
    plate_ce: BoolProperty(name="CE mark on the plate", default=True, update=_changed("picture"),
                           description="Puts a small CE mark in the lower right corner of the type plate")

    # ---- colours and finish ----
    ink_color: FloatVectorProperty(
        name="Colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=A.hex_to_linear(A.BLACK),
        update=_changed("material"),
        description="Colour of the letters, the symbol or the mark")
    use_field: BoolProperty(name="Background", default=False, update=_changed("material"),
                            description="A coloured background behind the letters or symbol (off: see-through, "
                                        "only the letters show on the part)")
    field_color: FloatVectorProperty(
        name="Background colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=A.hex_to_linear(A.WHITE),
        update=_changed("material"), description="Colour of the background behind the letters or symbol")
    use_edge: BoolProperty(name="Border", default=False, update=_changed("material"),
                           description="A thin border round the edge of the decal")
    edge_color: FloatVectorProperty(
        name="Border colour", subtype="COLOR", size=3, min=0.0, max=1.0, default=A.hex_to_linear(A.BLACK),
        update=_changed("material"), description="Colour of the border (and of a type plate's line and rivets)")
    clear_white: BoolProperty(
        name="White see-through", default=False, update=_changed("material"),
        description="Makes the white background of a logo see-through (for JPG logos and PNGs without "
                    "transparency). Leave it off for logos that have white in them")
    see_through: FloatProperty(
        name="See-through", subtype="FACTOR", min=0.0, max=1.0, default=0.0, update=_changed("material"),
        description="How much of the part shows through the decal: 0 = solid sticker, 0.5 = half see-through")
    finish: EnumProperty(name="Finish", items=FINISH_ITEMS, default="SATIN", update=_changed("material"),
                         description="How the decal shines in renders")

    # ---- where it lies (part coordinates) ----
    face: IntProperty(default=-1)
    anchor: FloatVectorProperty(size=3)
    normal: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))
    up: FloatVectorProperty(size=3, default=(0.0, 0.0, 1.0))
    offset_x: FloatProperty(
        name="Right", unit="LENGTH", default=0.0, update=_changed("shape"),
        description="Moves the decal to the right (negative: left) on its face, from the spot you clicked")
    offset_y: FloatProperty(
        name="Up", unit="LENGTH", default=0.0, update=_changed("shape"),
        description="Moves the decal up (negative: down) on its face, from the spot you clicked")
    angle: FloatProperty(name="Turn", subtype="ANGLE", default=0.0, update=_changed("shape"),
                         description="Turns the decal on its face (counter-clockwise as you look at it)")
    width: FloatProperty(name="Width", unit="LENGTH", default=0.1, min=MIN_SIZE, soft_max=2.0, update=_width_changed,
                         description="Width of the decal on the part. With 'Keep proportions' the height follows")
    height: FloatProperty(name="Height", unit="LENGTH", default=0.1, min=MIN_SIZE, soft_max=2.0,
                          update=_height_changed,
                          description="Height of the decal on the part. With 'Keep proportions' the width follows")
    keep_ratio: BoolProperty(name="Keep proportions", default=True, update=_ratio_changed,
                             description="Width and height change together, so the picture is never stretched")
    aspect: FloatProperty(default=1.0)            # height / width of the picture
    mirror: BoolProperty(name="Mirror", default=False, update=_changed("shape"),
                         description="Shows the picture mirrored (left and right swapped), e.g. for the inside "
                                     "of a window")
    hidden: BoolProperty(name="Off", default=False, update=_changed("visible"),
                         description="Switches the decal off in the view and in renders (it is kept)")
    lost: BoolProperty(default=False)             # its face changed in a model update: place it again

    # ---- what shows it ----
    mesh: PointerProperty(type=bpy.types.Mesh)
    material: PointerProperty(type=bpy.types.Material)


class FRDecalSettings(bpy.types.PropertyGroup):
    """The 'Logos & stickers' fold: what the next decal shows, and which decal is open in the list."""
    kind: EnumProperty(name="What", items=KIND_ITEMS, default="PICTURE",
                       description="What the next decal shows: a picture file, text you type or a ready-made sticker")
    picture: StringProperty(
        name="Picture", subtype="FILE_PATH",
        description="The picture file for the next decal (PNG with transparency is best for logos). The button "
                    "on the right lists the logos and stickers in the library")
    text: StringProperty(name="Text", default="",
                         description="The text for the next decal. Type | where a new line should start")
    sticker: EnumProperty(name="Sticker", items=STICKER_ITEMS,
                          description="The ready-made sticker for the next decal")
    only_copy: BoolProperty(
        name="Only this copy", default=False,
        description="The decal goes on the copy you click only (e.g. a serial number). Off: on every copy of "
                    "that part (e.g. a type plate on a bought motor)")
    placing: BoolProperty(default=False)
    active: StringProperty()                      # key of the decal whose details are open
    count: IntProperty(default=0)                 # decals in the project (for the panel header)


CLASSES = (FRDecal, FRDecalSettings)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Mesh.fresing_decals = CollectionProperty(type=FRDecal)
    bpy.types.Object.fresing_decals = CollectionProperty(type=FRDecal)
    bpy.types.Scene.fresing_decal = PointerProperty(type=FRDecalSettings)


def unregister():
    for owner, attr in ((bpy.types.Scene, "fresing_decal"), (bpy.types.Object, "fresing_decals"),
                        (bpy.types.Mesh, "fresing_decals")):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass


# =============================================================================
# finding decals
# =============================================================================


def is_decal(ob) -> bool:
    return ob is not None and ob.get(build.PROP_KIND) == KIND


def on_all_copies(item) -> bool:
    return isinstance(item.id_data, bpy.types.Mesh)


MILLED_TAG = "fr_milled"          # machining.CUT_TAG: the mesh a milled workpiece shows (task 0027)


def cad_mesh(ob):
    """The part's CAD mesh. A milled workpiece shows a mesh of its own while milling; its decals stay on (and
    are placed from) the CAD mesh, which milling keeps untouched (bug hunt 0045 row 3, task 0051)."""
    me = ob.data if ob is not None else None
    if me is None or not me.get(MILLED_TAG):
        return me
    for sc in bpy.data.scenes:
        m = getattr(getattr(sc, "fresing", None), "milling", None)
        if m is not None and m.cut_mesh is me and m.stock_mesh is not None:
            return m.stock_mesh
    return me


def users(item) -> list:
    """The part copies this decal is on."""
    owner = item.id_data
    if isinstance(owner, bpy.types.Object):
        return [owner]
    return [ob for ob in bpy.data.objects if ob.type == "MESH" and ob.get(build.PROP_KIND) == "part"
            and ob.data is not None and (ob.data is owner or cad_mesh(ob) is owner)]


def part_mesh(item):
    owner = item.id_data
    return cad_mesh(owner) if isinstance(owner, bpy.types.Object) else owner


def items_of(part) -> list:
    """Decals on this copy: those on every copy first, then those on this copy only."""
    if part is None or part.type != "MESH" or part.data is None:
        return []
    return list(cad_mesh(part).fresing_decals) + list(part.fresing_decals)


def find(key: str, part=None):
    """The decal with this key (on ``part`` when given, else anywhere)."""
    if not key:
        return None
    if part is not None:
        return next((it for it in items_of(part) if it.key == key), None)
    for me in bpy.data.meshes:
        for it in me.fresing_decals:
            if it.key == key:
                return it
    for ob in bpy.data.objects:
        for it in ob.fresing_decals:
            if it.key == key:
                return it
    return None


def all_decals() -> list[tuple]:
    """(part copy to show it on, decal) for every decal in the file."""
    out = []
    first_user: dict = {}
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.get(build.PROP_KIND) == "part" and ob.data is not None:
            first_user.setdefault(cad_mesh(ob).name, ob)
            for it in ob.fresing_decals:
                out.append((ob, it))
    for me in bpy.data.meshes:
        if len(me.fresing_decals):
            ob = first_user.get(me.name)
            for it in me.fresing_decals:
                out.append((ob, it))
    return out


def decal_objects_of(item) -> list:
    return [ob for ob in bpy.data.objects if ob.get(PROP_KEY) == item.key and is_decal(ob)]


def count(scene=None) -> int:
    n = sum(len(me.fresing_decals) for me in bpy.data.meshes) + sum(len(ob.fresing_decals) for ob in bpy.data.objects)
    sc = scene or bpy.context.scene
    if sc is not None and hasattr(sc, "fresing_decal") and sc.fresing_decal.count != n:
        sc.fresing_decal.count = n
    return n


# =============================================================================
# the face a decal lies on
# =============================================================================


_ARRAYS: dict = {}
ARRAYS_SECONDS = 5.0           # moving a decal with the mouse reads the same big part again and again


def _mesh_arrays(me) -> tuple[np.ndarray, np.ndarray]:
    """Corner positions (P,3,3) and corner normals (P,3,3) of every triangle of a part mesh (kept
    a few seconds: a part of 600,000 triangles takes a noticeable moment to read)."""
    import time
    key = me.as_pointer()
    sig = (len(me.vertices), len(me.loops), len(me.polygons))
    hit = _ARRAYS.get(key)
    now = time.monotonic()
    if hit is not None and hit[0] == sig and now - hit[1] < ARRAYS_SECONDS:
        return hit[2], hit[3]
    pos, nrm = _read_arrays(me)
    _ARRAYS.clear()
    _ARRAYS[key] = (sig, now, pos, nrm)
    return pos, nrm


def _read_arrays(me) -> tuple[np.ndarray, np.ndarray]:
    n_v, n_l = len(me.vertices), len(me.loops)
    co = np.empty(n_v * 3, dtype=np.float32)
    me.vertices.foreach_get("co", co)
    loops = np.empty(n_l, dtype=np.int64)
    me.loops.foreach_get("vertex_index", loops)
    nrm = np.empty(n_l * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    co = co.reshape(-1, 3).astype(np.float64)
    if n_l != 3 * len(me.polygons):                   # not triangles (not made by the importer)
        me.calc_loop_triangles()
        tl = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("loops", tl)
        return co[loops[tl]].reshape(-1, 3, 3), nrm.reshape(-1, 3)[tl].reshape(-1, 3, 3).astype(np.float64)
    return co[loops].reshape(-1, 3, 3), nrm.reshape(-1, 3, 3).astype(np.float64)


def face_triangles(me, face: int) -> tuple[np.ndarray, np.ndarray]:
    pos, nrm = _mesh_arrays(me)
    starts = faces.face_starts(me)
    if not (0 <= face < len(starts) - 1):
        return pos[:0], nrm[:0]
    lo, hi = int(starts[face]), int(starts[face + 1])
    return pos[lo:hi], nrm[lo:hi]


def frame_of(item, pos: np.ndarray, nrm: np.ndarray) -> dict:
    cyl = G.fit_cylinder(pos.reshape(-1, 3), nrm.reshape(-1, 3)) if len(pos) else None
    return G.frame(tuple(item.anchor), tuple(item.normal), tuple(item.up), cyl)


# =============================================================================
# building what shows
# =============================================================================


def rebuild(item) -> int:
    """Make the decal's mesh again from its settings and its face. Returns its number of triangles."""
    me = part_mesh(item)
    if me is None:
        return 0
    if item.mesh is None:
        item.mesh = bpy.data.meshes.new(f"Decal {item.name}")
        item.mesh["fr_decal_mesh"] = True
    out = item.mesh
    tris = 0
    if not item.lost:
        pos, nrm = face_triangles(me, item.face)
        if len(pos):
            fr = frame_of(item, pos, nrm)
            data = G.build(pos, nrm, fr, (item.offset_x, item.offset_y), item.angle, item.width, item.height,
                           item.mirror)
            tris = len(data["triangles"])
    out.clear_geometry()
    if tris:
        pos, tri = data["positions"].astype(np.float32), data["triangles"].astype(np.int32)
        out.vertices.add(len(pos))
        out.vertices.foreach_set("co", pos.reshape(-1))
        out.loops.add(tris * 3)
        out.loops.foreach_set("vertex_index", tri.reshape(-1))
        out.polygons.add(tris)
        out.polygons.foreach_set("loop_start", np.arange(0, tris * 3, 3, dtype=np.int32))
        out.update(calc_edges=True)
        uv = out.uv_layers.new(name="UV")
        uv.data.foreach_set("uv", data["uv"][tri.reshape(-1)].astype(np.float32).reshape(-1))
        attr = out.attributes.new("custom_normal", "FLOAT_VECTOR", "POINT")    # smooth like the part under it
        attr.data.foreach_set("vector", data["normals"].astype(np.float32).reshape(-1))
    out.update()
    if item.material is not None:
        if not out.materials:
            out.materials.append(item.material)
        elif out.materials[0] is not item.material:
            out.materials[0] = item.material
    return tris


def _object_name(item, part) -> str:
    owner = part.get(build.PROP_NAME, part.name) if part is not None else "?"
    return f"{item.name} on {owner}"


def _add_hide_driver(ob, part, prop: str) -> None:
    try:
        ob.driver_remove(prop)
    except TypeError:
        pass
    drv = ob.driver_add(prop).driver
    drv.type = "MAX"
    for name, target, path in (("part", part, "hide_render"), ("off", ob, f'["{PROP_OFF}"]')):
        var = drv.variables.new()
        var.name = name
        var.type = "SINGLE_PROP"
        var.targets[0].id_type = "OBJECT"
        var.targets[0].id = target
        var.targets[0].data_path = path


def _new_object(item, part):
    ob = bpy.data.objects.new(_object_name(item, part), item.mesh)
    cols = list(part.users_collection) or [bpy.context.scene.collection]
    cols[0].objects.link(ob)
    ob.parent = part
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob[build.PROP_KIND] = KIND
    ob[PROP_KEY] = item.key
    ob[PROP_OFF] = 1 if item.hidden else 0
    ob.hide_select = True
    ob.lock_location = ob.lock_rotation = ob.lock_scale = (True,) * 3
    for attr in ("visible_shadow",):                 # a sticker casts no shadow on the part under it
        if hasattr(ob, attr):
            setattr(ob, attr, False)
    _add_hide_driver(ob, part, "hide_render")
    _add_hide_driver(ob, part, "hide_viewport")
    return ob


def sync(parts) -> None:
    """Decal objects of these part copies: one per decal, made, updated or removed as needed."""
    parts = [p for p in parts if p is not None]
    if not parts:
        return
    names = {p.name for p in parts}
    have: dict = {}
    for ob in bpy.data.objects:
        if is_decal(ob) and ob.parent is not None and ob.parent.name in names:
            have.setdefault(ob.parent.name, {})[ob.get(PROP_KEY)] = ob
        elif is_decal(ob) and ob.parent is None:
            bpy.data.objects.remove(ob)                 # its part is gone
    for part in parts:
        mine = have.get(part.name, {})
        wanted = {it.key: it for it in items_of(part) if not it.lost and it.mesh is not None}
        for key, ob in list(mine.items()):
            if key not in wanted:
                bpy.data.objects.remove(ob)
        for key, it in wanted.items():
            ob = mine.get(key)
            if ob is None:
                ob = _new_object(it, part)
            elif ob.data is not it.mesh:
                ob.data = it.mesh
            off = 1 if it.hidden else 0
            if ob.get(PROP_OFF) != off:
                ob[PROP_OFF] = off
    count()


def sync_item(item) -> None:
    sync(users(item))


# =============================================================================
# pictures
# =============================================================================


def glyph_source(font_path: str = ""):
    """Triangles of a line of text in a font (font units, baseline at 0): Blender's text curve,
    filled, as a mesh."""
    font = None
    if font_path:
        path = bpy.path.abspath(font_path)
        if os.path.isfile(path):
            font = bpy.data.fonts.load(path, check_existing=True)

    def glyphs(text: str) -> np.ndarray:
        cu = bpy.data.curves.new("fr_decal_text", "FONT")
        cu.body = text
        if font is not None:
            cu.font = font
        ob = bpy.data.objects.new("fr_decal_text", cu)
        bpy.context.scene.collection.objects.link(ob)
        try:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = ob.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            co = np.empty(len(me.vertices) * 3, dtype=np.float64)
            me.vertices.foreach_get("co", co)
            tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
            me.loop_triangles.foreach_get("vertices", tri)
            out = co.reshape(-1, 3)[tri.reshape(-1, 3)][..., :2]
            ev.to_mesh_clear()
        finally:
            bpy.data.objects.remove(ob)
            bpy.data.curves.remove(cu)
        return out
    return glyphs


def fonts_on_this_pc() -> list[tuple[str, str]]:
    """(name, file) of common fonts found on this PC, for the font menu."""
    found = []
    if os.name == "nt":
        folder = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        names = (("Arial", "arial.ttf"), ("Arial Bold", "arialbd.ttf"), ("Arial Black", "ariblk.ttf"),
                 ("Segoe UI", "segoeui.ttf"), ("Segoe UI Bold", "segoeuib.ttf"), ("Calibri", "calibri.ttf"),
                 ("Calibri Bold", "calibrib.ttf"), ("Verdana", "verdana.ttf"), ("Verdana Bold", "verdanab.ttf"),
                 ("Tahoma", "tahoma.ttf"), ("Bahnschrift", "bahnschrift.ttf"), ("Consolas", "consola.ttf"),
                 ("Impact", "impact.ttf"), ("Times New Roman", "times.ttf"))
    else:
        folder = "/usr/share/fonts/truetype/dejavu"
        names = (("DejaVu Sans", "DejaVuSans.ttf"), ("DejaVu Sans Bold", "DejaVuSans-Bold.ttf"),
                 ("DejaVu Sans Mono", "DejaVuSansMono.ttf"))
    for label, file in names:
        path = os.path.join(folder, file)
        if os.path.isfile(path):
            found.append((label, path))
    return found


def _art(item) -> A.Art:
    if item.kind == "TEXT":
        return A.text_art(glyph_source(item.font), item.text)
    fields = {"company": item.plate_company, "type": item.plate_type, "serial": item.plate_serial,
              "year": item.plate_year, "weight": item.plate_weight, "ce": item.plate_ce}
    return A.sticker_art(item.sticker, glyph_source(item.font) if item.sticker == "TYPE_PLATE" else None, fields)


def _mask_image(item, masks: np.ndarray):
    h, w = masks.shape[:2]
    img = item.picture if item.picture is not None and item.picture.get("fr_decal_masks") else None
    if img is not None and tuple(img.size) != (w, h):
        img.scale(w, h)
    if img is None:
        img = bpy.data.images.new(f"Decal {item.name}", w, h, alpha=False)
        img["fr_decal_masks"] = True
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = masks[::-1]                       # Blender's pictures start at the bottom row
    img.pixels.foreach_set(rgba.reshape(-1))
    img.update()
    img.file_format = "PNG"
    img.pack()
    return img


def remake_picture(item) -> None:
    """The decal's picture from its settings (text and stickers are drawn, files are loaded)."""
    if item.kind == "PICTURE":
        path = bpy.path.abspath(item.source) if item.source else ""
        if not path or not os.path.isfile(path):
            return
        old = item.picture
        img = bpy.data.images.load(path, check_existing=True)
        if img.packed_file is None:
            try:
                img.pack()
            except RuntimeError:
                pass
        img.alpha_mode = "STRAIGHT"
        item.picture = img
        if old is not None and old is not img and old.users == 0:
            bpy.data.images.remove(old)
        w, h = img.size
        aspect = h / w if w else 1.0
    else:
        art = _art(item)
        item.picture = _mask_image(item, art.masks)
        aspect = art.aspect
    _set_quiet(item, "aspect", aspect)
    if item.keep_ratio:
        _set_quiet(item, "height", item.width * aspect)
    if item.material is None:
        item.material = bpy.data.materials.new(f"Decal {item.name}")
        item.material["fr_decal_material"] = True
    build_material(item)


# =============================================================================
# the material
# =============================================================================


def _math(nt, op, a, b=None, x=0.0, y=0.0, label=""):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = (x, y)
    if label:
        n.label = n.name = label
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _mix_color(nt, factor, a, b, x, y):
    m = nt.nodes.new("ShaderNodeMix")
    m.data_type = "RGBA"
    m.location = (x, y)
    sock = {s.identifier: s for s in m.inputs}
    nt.links.new(factor, sock["Factor_Float"])
    nt.links.new(a, sock["A_Color"])
    nt.links.new(b, sock["B_Color"])
    return {s.identifier: s for s in m.outputs}["Result_Color"]


def _value(nt, name, value, x, y):
    n = nt.nodes.new("ShaderNodeValue")
    n.name = n.label = name
    n.outputs[0].default_value = value
    n.location = (x, y)
    return n.outputs[0]


def _rgb(nt, name, color, x, y):
    n = nt.nodes.new("ShaderNodeRGB")
    n.name = n.label = name
    n.outputs[0].default_value = (*color, 1.0)
    n.location = (x, y)
    return n.outputs[0]


def build_material(item) -> None:
    """Plain nodes (no scripts): picture -> colour and see-through, the settings in named nodes."""
    mat = item.material
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.name = "BSDF"
    bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.name = "Picture"
    tex.image = item.picture
    tex.extension = "CLIP"
    tex.interpolation = "Cubic" if item.kind == "PICTURE" else "Linear"
    tex.location = (-900, 0)
    opacity = _value(nt, "Opacity", 1.0, -300, -500)
    if item.kind == "PICTURE":
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-600, -250)
        nt.links.new(tex.outputs["Color"], sep.inputs[0])
        lowest = _math(nt, "MINIMUM", _math(nt, "MINIMUM", sep.outputs[0], sep.outputs[1], -400, -250),
                       sep.outputs[2], -250, -250)
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.location = (-100, -250)
        rng.clamp = True
        nt.links.new(lowest, rng.inputs["Value"])
        rng.inputs["From Min"].default_value = 0.70
        rng.inputs["From Max"].default_value = 0.93
        rng.inputs["To Min"].default_value = 1.0
        rng.inputs["To Max"].default_value = 0.0
        clear = _value(nt, "ClearWhite", 0.0, -100, -450)
        cut = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, rng.outputs[0], 100, -250), clear, 250, -300)
        keep = _math(nt, "SUBTRACT", 1.0, cut, 400, -300)
        alpha = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", tex.outputs["Alpha"], keep, 450, -150), opacity,
                      500, -400, "Alpha")
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        sep.location = (-700, 0)
        nt.links.new(tex.outputs["Color"], sep.inputs[0])
        ink, fld, edg = sep.outputs[0], sep.outputs[1], sep.outputs[2]
        a_f = _math(nt, "MULTIPLY", fld, _value(nt, "FieldOn", 0.0, -700, -300), -500, -200)
        a_e = _math(nt, "MULTIPLY", edg, _value(nt, "EdgeOn", 0.0, -700, -400), -500, -350)
        prod = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, a_f, -350, -200),
                     _math(nt, "SUBTRACT", 1.0, a_e, -350, -350), -200, -250)
        under = _math(nt, "SUBTRACT", 1.0, prod, -50, -250)
        total = _math(nt, "SUBTRACT", 1.0, _math(nt, "MULTIPLY", prod, _math(nt, "SUBTRACT", 1.0, ink, -200, -100),
                                                 -50, -120), 100, -150)
        f_edge = _math(nt, "DIVIDE", a_e, _math(nt, "MAXIMUM", under, 1e-4, 100, -350), 250, -350)
        f_ink = _math(nt, "DIVIDE", ink, _math(nt, "MAXIMUM", total, 1e-4, 250, -150), 400, -150)
        c_under = _mix_color(nt, f_edge, _rgb(nt, "Field", tuple(item.field_color), -200, 350),
                             _rgb(nt, "Edge", tuple(item.edge_color), -200, 200), 100, 250)
        colour = _mix_color(nt, f_ink, c_under, _rgb(nt, "Ink", tuple(item.ink_color), 100, 450), 350, 250)
        nt.links.new(colour, bsdf.inputs["Base Color"])
        alpha = _math(nt, "MULTIPLY", total, opacity, 450, -400, "Alpha")
    nt.links.new(alpha, bsdf.inputs["Alpha"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "DITHERED"
    update_material(item)


def update_material(item) -> None:
    """Colours, background, border, see-through and finish: node values only (instant)."""
    mat = item.material
    if mat is None or mat.node_tree is None:
        return
    nodes = mat.node_tree.nodes

    def put(name, value):
        n = nodes.get(name)
        if n is not None:
            n.outputs[0].default_value = value

    put("Opacity", 1.0 - item.see_through)
    put("ClearWhite", 1.0 if item.clear_white else 0.0)
    put("FieldOn", 1.0 if item.use_field else 0.0)
    put("EdgeOn", 1.0 if item.use_edge else 0.0)
    put("Ink", (*item.ink_color, 1.0))
    put("Field", (*item.field_color, 1.0))
    put("Edge", (*item.edge_color, 1.0))
    bsdf = nodes.get("BSDF")
    if bsdf is not None:
        metal, rough, coat = FINISH.get(item.finish, FINISH["SATIN"])
        bsdf.inputs["Metallic"].default_value = metal
        bsdf.inputs["Roughness"].default_value = rough
        if "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = coat
    # Solid view (no textures there): a see-through tint where the decal is
    shown = item.field_color if (item.kind != "PICTURE" and item.use_field) else (
        item.ink_color if item.kind != "PICTURE" else (0.8, 0.8, 0.8))
    mat.diffuse_color = (*shown, 0.55 * (1.0 - item.see_through))
    mat.roughness = FINISH.get(item.finish, FINISH["SATIN"])[1]


# =============================================================================
# adding, moving, removing
# =============================================================================


def _local_dir(part, v) -> Vector:
    return (part.matrix_world.to_3x3().inverted_safe() @ Vector(v)).normalized()


def _local_normal(part, v) -> Vector:
    return (part.matrix_world.to_3x3().inverted_safe().transposed() @ Vector(v)).normalized()


def up_hints(part, view_up=None) -> list:
    """Upright: world up laid on the face; on a face that looks (nearly) straight up or down, the
    top of the view instead, so the decal reads the right way from where you look."""
    hints = [tuple(_local_dir(part, (0.0, 0.0, 1.0)))]
    if view_up is not None:
        hints.append(tuple(_local_dir(part, view_up)))
    return hints


def _upright(normal_local, hints) -> tuple:
    n = np.asarray(normal_local, dtype=np.float64)
    z = np.asarray(hints[0])
    if abs(float(np.dot(G.unit(z), G.unit(n)))) > 0.9 and len(hints) > 1:
        hints = hints[1:] + hints[:1]
    _right, up = G.upright_axes(n, *hints)
    return tuple(up)


def unique_name(part, base: str) -> str:
    names = {it.name for it in items_of(part)}
    if base not in names:
        return base
    k = 2
    while f"{base} {k}" in names:
        k += 1
    return f"{base} {k}"


def surface_hit(ob, polygon: int, location, normal):
    """(part, CAD face, part-local point, part-local normal) of a ray hit on a part or on a decal
    (a decal lies on a known face of its part), or None."""
    if is_decal(ob):
        part = ob.parent
        item = find(ob.get(PROP_KEY), part)
        if part is None or item is None:
            return None
        n_local = _local_normal(part, normal)
        p_local = part.matrix_world.inverted_safe() @ Vector(location) - n_local * G.OFFSET
        return part, item.face, tuple(p_local), tuple(n_local)
    if ob is None or ob.get(build.PROP_KIND) != "part" or ob.type != "MESH" or ob.data is None:
        return None
    face = faces.face_of_polygon(ob.data, polygon)
    p_local = ob.matrix_world.inverted_safe() @ Vector(location)
    return ob, face, tuple(p_local), tuple(_local_normal(ob, normal))


def through(ob, polygon: int, location, normal):
    """A click that hit a decal counts as a click on the part under it: (object, polygon, location,
    normal) with the part, a triangle of the decal's face and the spot on the part's surface. Hits on
    anything else come back unchanged. For the clicks that pick faces, joint axes or the sharp spot."""
    if not is_decal(ob):
        return ob, polygon, location, normal
    spot = surface_hit(ob, polygon, location, normal)
    if spot is None:
        return ob, polygon, location, normal
    part, face, point, _n = spot
    starts = faces.face_starts(cad_mesh(part))
    tri = int(starts[face]) if 0 <= face < len(starts) - 1 else 0
    return part, tri, part.matrix_world @ Vector(point), normal


def add(part, face: int, point, normal, kind: str, *, picture: str = "", text: str = "", sticker: str = "CE",
        only_copy: bool = False, view_up=None):
    """A new decal on this face, centred on ``point`` (part coordinates), upright, a sensible size."""
    owner = part.fresing_decals if only_copy else cad_mesh(part).fresing_decals
    if kind == "PICTURE":
        base = os.path.splitext(os.path.basename(bpy.path.abspath(picture)))[0] or "Picture"
    elif kind == "TEXT":
        base = (text.split("|")[0].strip() or "Text")[:24]
    else:
        base = A.sticker(sticker).label
    name = unique_name(part, base)
    it = owner.add()
    key = "d-" + uuid.uuid4().hex[:10]
    it.key = key
    _GUARD.add(key)
    try:
        it.name = name
        it.kind = kind
        it.face = face
        it.anchor = point
        it.normal = normal
        it.up = _upright(normal, up_hints(part, view_up))
        if kind == "PICTURE":
            it.source = picture
        elif kind == "TEXT":
            it.text = text or "Text"
        else:
            it.sticker = sticker
            ink, fld, edge, it.use_field, it.use_edge = A.sticker_colours(sticker)
            it.ink_color, it.field_color, it.edge_color = (A.hex_to_linear(ink), A.hex_to_linear(fld),
                                                           A.hex_to_linear(edge))
            if sticker == "TYPE_PLATE":
                it.finish = "METAL"
    finally:
        _GUARD.discard(key)
    remake_picture(it)
    _first_size(it, kind, sticker)
    rebuild(it)
    sync_item(it)
    return it


def _first_size(item, kind: str, sticker: str) -> None:
    pos, nrm = face_triangles(part_mesh(item), item.face)
    if not len(pos):
        return
    fr = frame_of(item, pos, nrm)
    _shift, w_fit, _h = G.fit_to_face(pos, nrm, fr, 0.0, item.aspect, margin=1.0)
    w = 0.5 * w_fit if w_fit > 0 else 0.1
    if kind == "STICKER":
        w = min(A.sticker(sticker).width_mm / 1000.0, 0.9 * w_fit) if w_fit > 0 else A.sticker(sticker).width_mm / 1000
    w = max(w, MIN_SIZE)
    _set_quiet(item, "width", w)
    _set_quiet(item, "height", max(w * item.aspect, MIN_SIZE))


def fit(item) -> None:
    """As big as fits on its face (centred on it), at its turn, proportions kept."""
    pos, nrm = face_triangles(part_mesh(item), item.face)
    if not len(pos):
        return
    fr = frame_of(item, pos, nrm)
    shift, w, h = G.fit_to_face(pos, nrm, fr, item.angle, item.aspect if item.keep_ratio else item.height / item.width)
    if w <= 0:
        return
    for attr, v in (("offset_x", shift[0]), ("offset_y", shift[1]), ("width", max(w, MIN_SIZE)),
                    ("height", max(h, MIN_SIZE))):
        _set_quiet(item, attr, v)
    rebuild(item)


def make_upright(item, view_up=None) -> None:
    part = users(item)[0] if users(item) else None
    if part is None:
        return
    _set_quiet(item, "up", _upright(tuple(item.normal), up_hints(part, view_up)))
    _set_quiet(item, "angle", 0.0)
    rebuild(item)


def place(item, part, face: int, point, normal) -> None:
    """Put the decal's centre on another spot (also another face of its part); its turn on the face stays."""
    old_up = np.asarray(item.up, dtype=np.float64)
    n = np.asarray(normal, dtype=np.float64)
    _set_quiet(item, "face", face)
    _set_quiet(item, "anchor", point)
    _set_quiet(item, "normal", normal)
    _set_quiet(item, "offset_x", 0.0)
    _set_quiet(item, "offset_y", 0.0)
    if np.linalg.norm(old_up - np.dot(old_up, G.unit(n)) * G.unit(n)) < 0.2:
        _set_quiet(item, "up", _upright(normal, up_hints(part)))
    _set_quiet(item, "lost", False)
    rebuild(item)
    sync_item(item)


def remove(item) -> None:
    """The decal goes, with what shows it (meshes, pictures and materials no longer used)."""
    owner = item.id_data
    coll = owner.fresing_decals
    for ob in decal_objects_of(item):
        bpy.data.objects.remove(ob)
    me, mat, img = item.mesh, item.material, item.picture
    idx = next(i for i, it in enumerate(coll) if it.key == item.key)
    coll.remove(idx)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)
    if mat is not None and mat.users == 0:
        bpy.data.materials.remove(mat)
    if img is not None and img.users == 0:
        bpy.data.images.remove(img)
    count()


def copy_settings(src, dst) -> None:
    """Every setting of a decal onto another (what shows it is made again)."""
    _GUARD.add(dst.key or "")
    try:
        for p in src.bl_rna.properties:
            pid = p.identifier
            if pid in ("rna_type", "mesh", "key") or p.is_readonly:
                continue
            val = getattr(src, pid)
            if p.type in ("FLOAT", "INT", "BOOLEAN") and getattr(p, "array_length", 0):
                val = tuple(val)
            try:
                setattr(dst, pid, val)
            except (TypeError, AttributeError, ValueError):
                pass
    finally:
        _GUARD.discard(dst.key or "")


def set_scope(item, part, only_copy: bool):
    """Move a decal between 'every copy' and 'this copy only'. Returns the decal as it is now."""
    if only_copy == (not on_all_copies(item)):
        return item
    target = part.fresing_decals if only_copy else cad_mesh(part).fresing_decals
    new = target.add()
    new.key = "d-" + uuid.uuid4().hex[:10]
    copy_settings(item, new)
    new.material = item.material
    old_key = item.key
    item.material = None
    remove(find(old_key))
    rebuild(new)
    sync_item(new)
    return new


# =============================================================================
# model update and templates
# =============================================================================


def relocate(item, me) -> bool:
    """Find the decal's face again on a (new) part mesh. False when its spot is no longer on the part."""
    pos, _nrm = _mesh_arrays(me)
    tri = G.locate(pos, tuple(item.anchor), tuple(item.normal))
    if tri < 0:
        return False
    face = faces.face_of_polygon(me, tri)
    _set_quiet(item, "face", face)
    return True


def carry_over(pairs, old_objects) -> list[str]:
    """After a model update: decals of matched parts move to the new parts when their spot is still on
    the part (also when the part changed elsewhere); otherwise they are kept but switched off until
    placed again. Returns report lines."""
    notes = []
    old_names = {o.name for o in old_objects}
    stale = [ob for ob in bpy.data.objects if is_decal(ob) and ob.parent is not None and ob.parent.name in old_names]
    if stale:
        bpy.data.batch_remove(stale)
    done_meshes = set()
    touched = []
    for old, new in pairs:
        if old.type != "MESH" or new.type != "MESH" or old.data is None or new.data is None:
            continue
        sources = []
        if old.data.name not in done_meshes:
            done_meshes.add(old.data.name)
            sources += [(it, new.data.fresing_decals) for it in old.data.fresing_decals]
        sources += [(it, new.fresing_decals) for it in old.fresing_decals]
        for it, target in sources:
            n = target.add()
            n.key = it.key
            copy_settings(it, n)
            found = relocate(n, new.data)
            _set_quiet(n, "lost", not found)
            if not found:
                notes.append(f"{new.get(build.PROP_NAME, new.name)}: its face changed, decal '{n.name}' is off "
                             "until you place it again (3 Looks > Logos & stickers > Move with the mouse)")
            rebuild(n)
            touched.append(new)
    gone = {o.name for o, _n in pairs}
    for ob in old_objects:
        if ob.name in gone or ob.type != "MESH":
            continue
        lost = list(ob.fresing_decals) + (list(ob.data.fresing_decals) if ob.data is not None else [])
        for it in lost:
            notes.append(f"Decal '{it.name}' was on {ob.get(build.PROP_NAME, ob.name)}, which is not in the new "
                         "model: it is gone")
    # every copy of a new part (also copies whose old copy did not match)
    meshes = {p.data.name for p in touched}
    sync([ob for ob in bpy.data.objects if ob.type == "MESH" and ob.data is not None and ob.data.name in meshes
          and ob.get(build.PROP_KIND) == "part"])
    return notes


SIMPLE_KEYS = ("name", "kind", "text", "sticker", "plate_company", "plate_type", "plate_serial", "plate_year",
               "plate_weight", "plate_ce", "use_field", "use_edge", "clear_white", "see_through", "finish", "face",
               "offset_x", "offset_y", "angle", "width", "height", "keep_ratio", "aspect", "mirror", "hidden")
VECTOR_KEYS = ("ink_color", "field_color", "edge_color", "anchor", "normal", "up")


def to_template(scene) -> list[dict]:
    """Every decal as plain data (for templates): the part's name, which copy, the settings and the
    picture file. Text and stickers are drawn again when the template is used."""
    out = []
    for part, it in all_decals():
        if part is None:
            continue
        d = {k: getattr(it, k) for k in SIMPLE_KEYS}
        d.update({k: list(getattr(it, k)) for k in VECTOR_KEYS})
        d["part"] = part.get(build.PROP_NAME, part.name)
        d["copy"] = "" if on_all_copies(it) else part.get(build.PROP_INSTANCE, "") or part.get(build.PROP_UID, "")
        d["source"] = bpy.path.abspath(it.source) if it.source else ""
        out.append(d)
    return out


def from_template(scene, entries: list[dict]) -> tuple[int, list[str]]:
    """Put a template's decals on parts of the same name (where the spot is on the part). Returns
    (number placed, notes)."""
    placed, notes = 0, []
    by_name: dict = {}
    for ob in build.iter_parts(scene):
        by_name.setdefault(ob.get(build.PROP_NAME, ""), []).append(ob)
    for d in entries or []:
        parts = by_name.get(d.get("part", ""), [])
        if d.get("copy"):
            parts = [p for p in parts if d["copy"] in (p.get(build.PROP_INSTANCE, ""), p.get(build.PROP_UID, ""))]
        if not parts:
            continue
        part = parts[0]
        if d.get("kind") == "PICTURE" and not os.path.isfile(d.get("source", "")):
            notes.append(f"Decal '{d.get('name')}': its picture {d.get('source')} was not found")
            continue
        if any(it.name == d.get("name") for it in items_of(part)):
            continue                                          # already there (template used twice)
        target = part.fresing_decals if d.get("copy") else part.data.fresing_decals
        it = target.add()
        it.key = "d-" + uuid.uuid4().hex[:10]
        _GUARD.add(it.key)
        try:
            for k in SIMPLE_KEYS:
                if k in d:
                    setattr(it, k, d[k])
            for k in VECTOR_KEYS:
                if k in d:
                    setattr(it, k, tuple(d[k]))
            it.source = d.get("source", "")
        finally:
            _GUARD.discard(it.key)
        if not relocate(it, part.data):
            notes.append(f"Decal '{it.name}' does not fit on {d.get('part')} of this model (its spot is not on "
                         "the part): left off")
            remove(it)
            continue
        remake_picture(it)
        if it.keep_ratio:
            _set_quiet(it, "height", it.width * it.aspect)
        rebuild(it)
        sync_item(it)
        placed += 1
    return placed, notes


def describe(item) -> str:
    """One line for the list: what it is."""
    if item.kind == "TEXT":
        return f"Text: {item.text.replace('|', ' / ')}"
    if item.kind == "STICKER":
        return A.sticker(item.sticker).label
    return f"Picture: {os.path.basename(bpy.path.abspath(item.source)) if item.source else '?'}"


def size_text(item) -> str:
    return f"{item.width * 1000:.0f} × {item.height * 1000:.0f} mm"


def summary(scene) -> str:
    n = count(scene)
    return plural(n, "decal") if n else ""


def library_folders() -> list[str]:
    """Folders with logos and stickers: in the shared library, else under Documents\\Fresing Render."""
    from . import prefs, rule_sets
    p = prefs.get()
    lib = bpy.path.abspath(p.library_path) if p is not None and p.library_path else ""
    base = lib if lib and os.path.isdir(lib) else os.path.join(rule_sets.documents_dir(), "Fresing Render")
    return [os.path.join(base, sub) for sub in LIBRARY_FOLDERS]


def library_pictures() -> list[tuple[str, str]]:
    """(label, file) of every picture in the library folders."""
    out = []
    for folder in library_folders():
        if not os.path.isdir(folder):
            continue
        sub = os.path.basename(folder)
        for name in sorted(os.listdir(folder), key=str.lower):
            if name.lower().endswith(PICTURE_TYPES):
                out.append((f"{sub}: {os.path.splitext(name)[0]}", os.path.join(folder, name)))
    return out

