"""Web 3D model (task 0099): export the machine as one ``.glb`` with its looks baked to textures, plus a viewer page.

How a look becomes a glTF material
----------------------------------
Every material of a visible part has one Principled BSDF. Each of its inputs Base Color, Alpha, Roughness, Metallic,
Normal and Coat Normal is either a number (-> a glTF factor) or fed by nodes. A fed input is a *source*; its
*signature* is a hash of the nodes upstream. Sources with the same signature are baked once (every satin paint shares
one orange-peel normal map). All sources go as quads of **one** bake object into one atlas image (Cycles bakes an
object over the whole image, so one object is much faster than one per look), each quad a 0.2 m square of the look
with the source wired into an Emission shader (the normal as n * 0.5 + 0.5). A tile whose values hardly vary becomes
a factor again; the rest are made seamless and saved as JPG (PNG where the colour has holes).
Parts get box-projected UVs in their own axes (``core.web3d.box_uv``), so the texture has the renders' scale and moves
with the part. Decals are baked one by one on their own UVs.

The project is not changed: the bake uses its own scene, object, materials and image, removed at the end; meshes are
read, never given a UV layer.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time

import bpy
import numpy as np

from ..core import web3d as core
from . import build, decals

SOCKETS = {"color": "Base Color", "alpha": "Alpha", "rough": "Roughness", "metal": "Metallic", "normal": "Normal",
           "coat_normal": "Coat Normal"}
KIND = {"color": "color", "alpha": "value", "rough": "value", "metal": "value", "normal": "normal",
        "coat_normal": "normal"}
BAKE_SAMPLES = 4
PROBE = 48                     # px of the quick first bake that finds the inputs that are one number
BAKE_NAME = "FR web bake"
LIGHT_JPG = 90                 # JPG quality of the baked-light atlases (task 0107)
_RUN: dict = {}
_SKIP_PROPS = {"name", "label", "location", "location_absolute", "width", "height", "dimensions", "select",
               "show_options", "show_preview", "hide", "show_texture", "color", "use_custom_color", "parent",
               "is_active_output", "color_tag", "warning_propagation", "bl_idname", "bl_label", "bl_description",
               "bl_icon", "bl_static_type", "bl_width_default", "bl_width_min", "bl_width_max",
               "bl_height_default", "bl_height_min", "bl_height_max", "type", "internal_links", "rna_type",
               "inputs", "outputs", "image_user", "texture_mapping", "color_mapping"}


def runtime(scene) -> dict:
    return _RUN.setdefault(scene.name, {})


def settings(scene):
    return scene.fresing.web3d


# ---------------------------------------------------------------------------
# what goes in
# ---------------------------------------------------------------------------

def _visible(ob) -> bool:
    try:
        return bool(ob.visible_get())
    except RuntimeError:                       # not in the view layer
        return False


def objects(scene) -> tuple[list, list]:
    """(parts, decal objects) shown in the view: hidden parts and Show only are respected."""
    parts = [ob for ob in build.iter_parts(scene)
             if _visible(ob) and ob.data is not None and len(ob.data.polygons)]
    marks = [ob for ob in scene.objects
             if decals.is_decal(ob) and ob.type == "MESH" and _visible(ob) and ob.data is not None
             and len(ob.data.polygons) and ob.data.uv_layers]
    return parts, marks


def can_export(scene) -> str:
    """'' when an export can start, else why not (plain words)."""
    if runtime(scene).get("running"):
        return "An export is running"
    parts, _ = objects(scene)
    if not parts:
        return "No part is shown: show the model (2 Structure) first"
    return ""


def default_path(scene) -> str:
    from . import render
    s = scene.fresing
    folder = bpy.path.abspath(s.out_folder) if s.out_folder else render.default_output_dir()
    stem = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    if not stem:
        roots = build.model_roots(scene)
        src = roots[0].get(build.PROP_SOURCE, "") if roots else ""
        stem = os.path.splitext(os.path.basename(src))[0] or "Model"
    return os.path.join(folder, core.safe_name(stem) + " web 3D.glb")


# ---------------------------------------------------------------------------
# looks
# ---------------------------------------------------------------------------

def principled(mat):
    if mat is None or mat.node_tree is None:
        return None
    nodes = [n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"]
    return nodes[0] if nodes else None


def _value(v):
    if isinstance(v, (str, set, frozenset)):
        return str(sorted(v)) if isinstance(v, (set, frozenset)) else v
    try:
        return tuple(round(float(x), 6) for x in v)
    except TypeError:
        try:
            return round(float(v), 6)
        except (TypeError, ValueError):
            return str(v)
    except ValueError:
        return str(v)


def _node_text(node) -> str:
    parts = [node.bl_idname]
    for p in node.bl_rna.properties:
        ident = p.identifier
        if ident in _SKIP_PROPS or p.type == "COLLECTION":
            continue
        try:
            v = getattr(node, ident)
        except AttributeError:
            continue
        if p.type == "POINTER":
            v = getattr(v, "name_full", None) if isinstance(v, bpy.types.ID) else None
            if v is None:
                continue
        parts.append(f"{ident}={_value(v)}")
    if node.type == "GROUP" and node.node_tree is not None:
        parts.append(f"tree={signature_tree(node.node_tree)}")
    return "|".join(parts)


def signature_tree(nt) -> str:
    text = ";".join(sorted(_node_text(n) + ">" + ",".join(f"{l.from_node.name}.{l.from_socket.identifier}"
                                                          for i in n.inputs for l in i.links)
                           for n in nt.nodes))
    return hashlib.sha1(text.encode()).hexdigest()[:16]


def signature(sock, memo: dict | None = None) -> str:
    """A hash of everything that feeds this output socket: equal hashes give equal pictures."""
    memo = {} if memo is None else memo
    key = (sock.node.name, sock.identifier)
    if key in memo:
        return memo[key]
    node = sock.node
    parts = [_node_text(node), "out=" + sock.identifier]
    for inp in node.inputs:
        if not inp.enabled and not inp.is_linked:
            continue
        if inp.is_linked:
            link = inp.links[0]
            parts.append(f"{inp.identifier}<{signature(link.from_socket, memo)}")
        elif hasattr(inp, "default_value"):
            parts.append(f"{inp.identifier}={_value(inp.default_value)}")
    h = hashlib.sha1("\n".join(parts).encode()).hexdigest()[:20]
    memo[key] = h
    return h


class Look:
    """One Blender material read for the web: each channel a number or a source to bake."""

    def __init__(self, mat, decal: bool = False):
        self.mat = mat
        self.decal = decal
        self.bsdf = principled(mat)
        self.const: dict = {}
        self.src: dict = {}                    # channel -> tile key
        self.extra: dict = {}
        b = self.bsdf
        if b is None:
            c = tuple(mat.diffuse_color) if mat is not None else (0.8, 0.8, 0.8, 1.0)
            self.const = {"color": c[:3], "alpha": c[3], "rough": float(getattr(mat, "roughness", 0.5)),
                          "metal": float(getattr(mat, "metallic", 0.0))}
            return
        memo: dict = {}
        for ch, name in SOCKETS.items():
            sock = b.inputs.get(name)
            if sock is None:
                continue
            if sock.is_linked:
                link = sock.links[0]
                if not link.is_muted:
                    self.src[ch] = ("decal:" + mat.name if decal else "") + KIND[ch] + ":" + \
                        signature(link.from_socket, memo)
                    continue
            if ch in ("normal", "coat_normal"):
                continue
            v = sock.default_value
            self.const[ch] = tuple(v)[:3] if ch == "color" else float(v)

        def num(name, default=0.0):
            s = b.inputs.get(name)
            return float(s.default_value) if s is not None and not s.is_linked else default

        self.extra = {"coat": num("Coat Weight"), "coat_rough": num("Coat Roughness", 0.03),
                      "transmission": num("Transmission Weight"), "ior": num("IOR", 1.5),
                      "emission_strength": num("Emission Strength")}
        ec = b.inputs.get("Emission Color")
        self.extra["emission"] = tuple(ec.default_value)[:3] if ec is not None and not ec.is_linked else (0, 0, 0)

    def sockets(self) -> dict:
        """tile key -> (channel, input socket name)"""
        return {key: (ch, SOCKETS[ch]) for ch, key in self.src.items()}


# ---------------------------------------------------------------------------
# baking
# ---------------------------------------------------------------------------

def _prune(nt, keep_from) -> None:
    keep = set()
    stack = [keep_from]
    while stack:
        nd = stack.pop()
        if nd.name in keep:
            continue
        keep.add(nd.name)
        for i in nd.inputs:
            for l in i.links:
                stack.append(l.from_node)
    for nd in list(nt.nodes):
        if nd.name not in keep:
            nt.nodes.remove(nd)


def _flatten_shape_nodes(nt) -> None:
    """Edge wear and corner dirt come from the part's own shape (Bevel, Ambient Occlusion): on a flat bake tile
    they give nothing but would see the tile's own edges, and they are slow to trace. Give them their flat values:
    the surface's own normal, no occlusion."""
    geo = None
    for nd in list(nt.nodes):
        if nd.type not in ("BEVEL", "AMBIENT_OCCLUSION"):
            continue
        for out in nd.outputs:
            for link in list(out.links):
                to = link.to_socket
                if nd.type == "BEVEL":
                    if geo is None:
                        geo = nt.nodes.new("ShaderNodeNewGeometry")
                    nt.links.new(geo.outputs["Normal"], to)
                else:
                    nt.links.remove(link)
                    if hasattr(to, "default_value"):
                        try:
                            to.default_value = (1.0, 1.0, 1.0, 1.0) if out.name == "Color" else 1.0
                        except (TypeError, ValueError):
                            pass
        nt.nodes.remove(nd)


def _bake_material(src_mat, socket_name: str, kind: str, image) -> bpy.types.Material:
    """A copy of the look that shows one input as light (Emission), for an Emit bake into ``image``."""
    m = src_mat.copy()
    m.name = BAKE_NAME
    nt = m.node_tree
    b = principled(m)
    from_sock = b.inputs[socket_name].links[0].from_socket
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.target = "ALL"
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    if kind == "normal":
        vm = nt.nodes.new("ShaderNodeVectorMath")
        vm.operation = "MULTIPLY_ADD"
        vm.inputs[1].default_value = (0.5, 0.5, 0.5)
        vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        nt.links.new(from_sock, vm.inputs[0])
        nt.links.new(vm.outputs[0], em.inputs["Color"])
    else:
        nt.links.new(from_sock, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    _prune(nt, out)
    _flatten_shape_nodes(nt)
    out.is_active_output = True
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    nt.nodes.active = tex
    return m


class Baker:
    """A scene of its own with one bake object; removed by ``close``."""

    def __init__(self, scene=None):
        # Setting a scene's engine to Cycles makes Blender wait for running material-preview renders, which need
        # Python, while this code holds it: the app froze (found in the real app). A copy of a scene that already
        # renders with Cycles has no engine to switch; its objects and collections are taken off (only the copy).
        src = scene if scene is not None and scene.render.engine == "CYCLES" else None
        if src is None:
            src = next((s for s in bpy.data.scenes if s.render.engine == "CYCLES"), None)
        if src is not None:
            sc = src.copy()
            sc.name = BAKE_NAME
            for c in list(sc.collection.children):
                sc.collection.children.unlink(c)
            for o in list(sc.collection.objects):
                sc.collection.objects.unlink(o)
            sc.world = None
        else:                                   # nothing renders with Cycles yet: no preview can be running with it
            sc = bpy.data.scenes.new(BAKE_NAME)
            sc.render.engine = "CYCLES"
        sc.cycles.samples = BAKE_SAMPLES
        sc.cycles.device = "CPU"
        sc.cycles.use_denoising = False
        sc.render.bake.margin = 0
        sc.render.bake.use_clear = True
        self.scene = sc
        self.ids: list = []

    def _run(self, ob) -> None:
        vl = self.scene.view_layers[0]
        for o in self.scene.objects:
            o.select_set(o is ob, view_layer=vl)
        vl.objects.active = ob
        with bpy.context.temp_override(scene=self.scene, view_layer=vl, active_object=ob, object=ob,
                                       selected_objects=[ob], selected_editable_objects=[ob]):
            res = bpy.ops.object.bake(type="EMIT", margin=0, use_clear=True)
        if res != {"FINISHED"}:
            raise RuntimeError(f"baking the looks failed ({res})")

    def _image(self, w: int, h: int):
        img = bpy.data.images.new(BAKE_NAME, w, h, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        self.ids.append(img)
        return img

    def _object(self, me):
        ob = bpy.data.objects.new(BAKE_NAME, me)
        ob[build.PROP_KIND] = "bake"
        for k, v in (("fr_ax_long", (1.0, 0.0, 0.0)), ("fr_ax_round", (1.0, 0.0, 0.0)), ("fr_ax_centre", (0.0, 0.0, 0.0))):
            ob[k] = v
        self.scene.collection.objects.link(ob)
        self.ids.append(ob)
        return ob

    def tiles(self, jobs: list, size: int, full: int | None = None) -> dict:
        """``jobs``: (key, material, socket name, kind). Bakes them as quads of one object into one atlas.
        Returns key -> (size, size, 4) floats, row 0 at the bottom (Blender's order).
        ``full``: a quick look at ``size`` px for a bake of ``full`` px: colours and numbers over the whole tile,
        normals over a patch at the full bake's pixel size (a bump's strength depends on the pixel size)."""
        n = len(jobs)
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)
        img = self._image(cols * size, rows * size)
        verts, faces = [], []
        for k in range(n):
            x = (k % 8) * 0.5
            y = (k // 8) * 0.5
            o = len(verts)
            d = core.TILE_M * size / full if full and jobs[k][3] == "normal" else core.TILE_M
            verts += [(x, y, 0.0), (x + d, y, 0.0), (x + d, y + d, 0.0), (x, y + d, 0.0)]
            faces.append((o, o + 1, o + 2, o + 3))
        me = bpy.data.meshes.new(BAKE_NAME)
        self.ids.append(me)
        me.from_pydata(verts, [], faces)
        uv = me.uv_layers.new(name="atlas")
        corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
        for k, poly in enumerate(me.polygons):
            i, j = k % cols, k // cols
            for li, (a, b) in zip(poly.loop_indices, corners):
                uv.data[li].uv = ((i + a) / cols, (j + b) / rows)
        for k, (key, mat, sock, kind) in enumerate(jobs):
            bm = _bake_material(mat, sock, kind, img)
            self.ids.append(bm)
            me.materials.append(bm)
            me.polygons[k].material_index = k
        ob = self._object(me)
        self._run(ob)
        px = np.empty(cols * size * rows * size * 4, np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(rows * size, cols * size, 4)
        out = {}
        for k, (key, *_rest) in enumerate(jobs):
            i, j = k % cols, k // cols
            out[key] = px[j * size:(j + 1) * size, i * size:(i + 1) * size].copy()
        return out

    def decal(self, ob, look: Look, size: int) -> dict:
        """Colour and alpha of one decal on its own UVs: {"color": (h, w, 3), "alpha": (h, w)} (row 0 at the
        bottom); a channel that is a number is left out."""
        dims = sorted(ob.dimensions, reverse=True)
        ratio = dims[1] / dims[0] if dims[0] > 1e-9 else 1.0
        w = min(size, 1024)
        h = max(32, int(round(w * min(1.0, ratio))))
        out = {}
        for ch in ("color", "alpha"):
            if ch not in look.src:
                continue
            img = self._image(w, h)
            bm = _bake_material(look.mat, SOCKETS[ch], KIND[ch], img)
            self.ids.append(bm)
            tmp = self._object(ob.data)
            tmp.material_slots[0].link = "OBJECT"
            tmp.material_slots[0].material = bm
            self._run(tmp)
            px = np.empty(w * h * 4, np.float32)
            img.pixels.foreach_get(px)
            px = px.reshape(h, w, 4)
            out[ch] = px[..., :3] if ch == "color" else px[..., 0]
            self.scene.collection.objects.unlink(tmp)
        return out

    def close(self) -> None:
        for idb in reversed(self.ids):
            try:
                if isinstance(idb, bpy.types.Object):
                    bpy.data.objects.remove(idb)
                elif isinstance(idb, bpy.types.Material):
                    bpy.data.materials.remove(idb)
                elif isinstance(idb, bpy.types.Mesh):
                    bpy.data.meshes.remove(idb)
                elif isinstance(idb, bpy.types.Image):
                    bpy.data.images.remove(idb)
                elif isinstance(idb, bpy.types.World):          # task 0107: the light bake's world copies
                    bpy.data.worlds.remove(idb)
            except ReferenceError:
                pass
        self.ids = []
        if self.scene is not None:
            try:
                bpy.data.scenes.remove(self.scene)
            except ReferenceError:
                pass
            self.scene = None


def finish_tile(tile: np.ndarray, kind: str, decal: bool = False):
    """A baked tile -> its values, or None when it is one number (or colour). ``color``: linear RGB (h, w, 3);
    ``value``: (h, w); ``normal``: unit vectors (h, w, 3)."""
    if kind == "color":
        t = tile[..., :3]
    elif kind == "value":
        t = tile[..., :1]
    else:
        t = tile[..., :3] * 2.0 - 1.0
    if core.is_flat(t) if kind != "normal" else core.normal_flat(t):
        return None
    if not decal:
        t = core.seamless(t)
    if kind == "normal":
        t = t / np.maximum(np.linalg.norm(t, axis=-1, keepdims=True), 1e-6)
    return t[..., 0] if kind == "value" else t


def pack_tile(t: np.ndarray, kind: str) -> np.ndarray:
    """A finished tile as the 8-bit pixels its picture gets (task 0105: a 2048 px colour tile is 12 MB so, 50 MB as
    floats; all tiles wait in memory until the looks are written). ``color``: sRGB (h, w, 3); ``value``: (h, w);
    ``normal``: n * 0.5 + 0.5 (h, w, 3)."""
    if kind == "color":
        return core.to_bytes(core.linear_to_srgb(t))
    if kind == "normal":
        return core.to_bytes(t * 0.5 + 0.5)
    return core.to_bytes(t)


def flat_value(tile: np.ndarray, kind: str):
    if kind == "color":
        return tuple(float(v) for v in tile[..., :3].reshape(-1, 3).mean(0))
    return float(tile[..., 0].mean())


# ---------------------------------------------------------------------------
# pictures into the file
# ---------------------------------------------------------------------------

def jpeg(pixels: np.ndarray, quality: int) -> bytes:
    """A JPG file of (h, w, 3) bytes, row 0 at the bottom (Blender's order), saved by Blender as they are."""
    h, w = pixels.shape[:2]
    img = bpy.data.images.new(BAKE_NAME, w, h, alpha=False)
    try:
        img.colorspace_settings.name = "Non-Color"
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :3] = pixels[..., :3].astype(np.float32) / 255.0
        img.pixels.foreach_set(rgba.ravel())
        img.file_format = "JPEG"
        fd, path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            img.save(filepath=path, quality=int(quality))
            with open(path, "rb") as fh:
                return fh.read()
        finally:
            os.remove(path)
    finally:
        bpy.data.images.remove(img)


def encode(pixels: np.ndarray, kind: str) -> bytes:
    """(h, w, 3 or 4) bytes, row 0 at the bottom -> JPG, or PNG when there is an alpha channel with holes."""
    if pixels.shape[2] == 4 and int(pixels[..., 3].min()) < 255:
        return core.png(np.flipud(pixels))
    return jpeg(pixels[..., :3], core.JPG_QUALITY[kind])


# ---------------------------------------------------------------------------
# meshes
# ---------------------------------------------------------------------------

def _textured(mat: dict) -> bool:
    pbr = mat.get("pbrMetallicRoughness", {})
    return bool("baseColorTexture" in pbr or "metallicRoughnessTexture" in pbr or "normalTexture" in mat
                or "clearcoatNormalTexture" in (mat.get("extensions", {}).get("KHR_materials_clearcoat") or {}))


def mesh_arrays(me, own_uv: bool = False, uv: bool = True):
    """(points (n, 3), corner vertex (m*3), corner normals (m*3, 3), corner UVs (m*3, 2) or None, material index of
    each triangle (m))."""
    lt = me.loop_triangles
    m = len(lt)
    loops = np.empty(m * 3, np.int32)
    lt.foreach_get("loops", loops)
    mi = np.empty(m, np.int32)
    lt.foreach_get("material_index", mi)
    cv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", cv)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    cn = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    vert = cv[loops]
    want_uv, uv = uv, None
    if not want_uv:
        pass
    elif own_uv:
        layer = me.uv_layers.get("UV") or me.uv_layers.active
        if layer is not None:
            u = np.empty(len(me.loops) * 2, np.float32)
            layer.data.foreach_get("uv", u)
            uv = u.reshape(-1, 2)[loops]
    else:
        uv = core.box_uv(co, vert.reshape(-1, 3)).reshape(-1, 2)
    return co, vert, cn[loops], uv, mi


# ---------------------------------------------------------------------------
# the export
# ---------------------------------------------------------------------------

def meshopt_paths() -> list:
    """Where Blender keeps its meshopt library (task 0105): the glTF add-on's bridge (Windows: next to the add-on;
    Linux: Blender's ``lib`` folder), or ``libmeshoptimizer`` next to Blender as a Python module (the tests)."""
    out = []
    try:
        import io_scene_gltf2  # noqa: F401  (dll_path looks the add-on up in sys.modules)
        from io_scene_gltf2.io.com.library import dll_path
        p = dll_path("bf_intern_meshopt_bridge", "MeshOptimizer")
        if p is not None:
            out.append(str(p))
    except Exception:  # noqa: BLE001 - another Blender: look in the usual places below
        pass
    names = {"win32": ("meshoptimizer.dll",), "darwin": ("libmeshoptimizer.dylib",)}.get(
        __import__("sys").platform, ("libmeshoptimizer.so",))
    local = bpy.utils.resource_path("LOCAL") or ""
    for base in (os.path.join(os.path.dirname(local), "lib") if local else "",
                 os.path.dirname(bpy.app.binary_path or "")):
        for n in names if base else ():
            out.append(os.path.join(base, n))
    return out


def meshopt_native():
    """Blender's meshopt library, loaded once (None: the NumPy codec packs the triangle lists, a little bigger)."""
    from ..core import meshopt
    return meshopt.native() or meshopt.use_native(meshopt_paths())


def _matrix_list(m) -> list:
    return [float(m[r][c]) for c in range(4) for r in range(4)]


def _is_identity(m) -> bool:
    return all(abs(m[r][c] - (1.0 if r == c else 0.0)) < 1e-9 for r in range(4) for c in range(4))


class Job:
    """One export. ``steps()`` yields the progress (0 … 1) and sets ``text``; ``finish()`` writes the files.
    ``run()`` does it all at once (scripts, tests, PC check)."""

    def __init__(self, scene, path: str, size: int = core.DEFAULT_SIZE, hide_names: bool = True,
                 animation: bool = False, page: bool = True, compress: bool | None = None,
                 surroundings: dict | None = None, light: str = "LIVE", light_quality: str = "NORMAL",
                 light_texels: float = 0.0, light_samples: int = 0):
        from . import lightbake
        self.scene = scene
        self.light = lightbake.choice_id(light)  # task 0107: LIVE | SOFT | ALL
        self.light_quality = light_quality
        self.light_texels = float(light_texels or 0.0)
        self.light_samples = int(light_samples or 0)
        self._lit = None                       # the bake's Result
        self._bake = None
        self._light_bytes = 0
        self._light_info = None
        self.surroundings = surroundings       # task 0106: the fold's choice (web3d_env.choice); None = today's page
        self.path = os.path.abspath(bpy.path.abspath(path))
        if not self.path.lower().endswith(".glb"):
            self.path += ".glb"
        self.size = int(size)
        self.hide_names = bool(hide_names)
        self.animation = bool(animation)
        self.page = bool(page)
        self.compress = compress               # None: from core.COMPRESS_FROM triangles on (the panel's tick)
        self.text = "Starting"
        self.t0 = time.perf_counter()
        self.gltf = core.Gltf()
        self.result: dict = {}
        self._baker = None

    # -- names
    def _name(self, ob, k: int, what: str = "Part") -> str:
        if self.hide_names:
            return f"{what} {k}"
        return str(ob.get(build.PROP_NAME) or ob.name)

    def steps(self):
        rest = None
        try:
            if self.surroundings is not None:  # task 0106: the parts where they stand on a still sea; the page moves them
                from . import vessel_motion
                if vessel_motion.effective(self.scene):
                    rest = vessel_motion.at_rest(self.scene)
                    rest.__enter__()
            for f in self._steps():
                if self.light == "LIVE":
                    yield f
                elif isinstance(f, tuple):     # the light bake: 30 … 80 %
                    yield 0.3 + 0.5 * f[1]
                else:                          # the looks before it (0 … 0.5 -> 0 … 30 %), the parts after it
                    yield f * 0.6 if f <= 0.5 else 0.8 + (f - 0.5) * 0.4
        finally:
            if self._bake is not None:
                self._bake.close()
                self._bake = None
            if self._baker is not None:
                self._baker.close()
                self._baker = None
            if rest is not None:
                rest.__exit__(None, None, None)

    def _steps(self):
        scene = self.scene
        self.text = "Reading the model"
        parts, marks = objects(scene)
        if not parts:
            raise RuntimeError("No part is shown: nothing to export")
        self._modes = {}
        if self.surroundings is None and self.light != "LIVE":    # task 0107: the plain page, the project's light
            from . import surroundings
            self._floor = surroundings.floor_height(scene)
            mn, mx = build.world_bounds(parts)
            self._bounds = ([float(v) for v in mn], [float(v) for v in mx])
        if self.surroundings is not None:
            from . import surroundings, web3d_env
            self._floor = surroundings.floor_height(scene)
            self._modes = web3d_env.vessel_modes(scene) if self.surroundings.get("vessel") else {}
            parts = parts + web3d_env.deck_objects(scene, self.surroundings)
            mn, mx = build.world_bounds(parts)            # the deck too: the page frames the whole vessel
            self._bounds = ([float(v) for v in mn], [float(v) for v in mx])
        yield 0.02

        # -- looks
        looks: dict = {}
        for ob in parts:
            for slot in ob.material_slots:
                if slot.material is not None and slot.material.name not in looks:
                    looks[slot.material.name] = Look(slot.material)
        decal_looks = {}
        for ob in marks:
            mat = ob.material_slots[0].material if ob.material_slots else None
            if mat is not None:
                decal_looks[ob.name] = Look(mat, decal=True)
        jobs, seen = [], set()
        for lk in looks.values():
            for key, (ch, sock) in lk.sockets().items():
                if key not in seen:
                    seen.add(key)
                    jobs.append((key, lk.mat, sock, KIND[ch]))
        tiles: dict = {}
        flat: dict = {}
        if jobs or decal_looks:
            self._baker = Baker(scene)
        if jobs:                       # a quick look first: inputs that come out as one number need no full bake
            self.text = f"Looking at {len(jobs)} baked inputs"
            yield 0.04
            small = {}
            for start in range(0, len(jobs), 256):
                small.update(self._baker.tiles(jobs[start:start + 256], PROBE, self.size))
            keep = []
            for job in jobs:
                key, kind = job[0], job[3]
                probe = small[key]
                t = probe[..., :3] if kind != "value" else probe[..., :1]
                if core.is_flat(t) if kind != "normal" else core.normal_flat(t * 2.0 - 1.0):
                    flat[key] = flat_value(probe, kind)
                else:
                    keep.append(job)
            jobs = keep
        per_atlas = max(1, (core.ATLAS_MAX // self.size) ** 2)
        n_bakes = math.ceil(len(jobs) / per_atlas) + len(decal_looks)
        done = 0
        for start in range(0, len(jobs), per_atlas):
            batch = jobs[start:start + per_atlas]
            self.text = f"Baking looks {start + 1}–{start + len(batch)} of {len(jobs)}"
            yield 0.05 + 0.45 * done / max(n_bakes, 1)
            baked = self._baker.tiles(batch, self.size)
            for key, mat, sock, kind in batch:
                tile = baked.pop(key)
                t = finish_tile(tile, kind)
                if t is None:
                    flat[key] = flat_value(tile, kind)
                else:
                    tiles[key] = pack_tile(t, kind)
            del baked
            done += 1
        decal_tiles: dict = {}
        for k, ob in enumerate(marks):
            lk = decal_looks.get(ob.name)
            if lk is None:
                continue
            self.text = f"Baking decal {k + 1} of {len(marks)}"
            yield 0.05 + 0.45 * done / max(n_bakes, 1)
            got = self._baker.decal(ob, lk, self.size)
            for ch, arr in got.items():
                kind = KIND[ch]
                t = finish_tile(arr[..., None] if kind == "value" else arr, kind, decal=True)
                key = lk.src[ch]
                if t is None:
                    flat[key] = flat_value(arr[..., None] if kind == "value" else arr, kind)
                else:
                    tiles[key] = pack_tile(t, kind)
            done += 1
        if self._baker is not None:
            self._baker.close()
            self._baker = None

        # -- baked light (task 0107)
        if self.light != "LIVE":
            yield from self._bake_light(parts, marks)

        # -- materials
        self.text = "Writing the looks"
        yield 0.5
        mat_index: dict = {}
        cache: dict = {}
        for k, (name, lk) in enumerate(list(looks.items()) + [(f"decal:{n}", lk) for n, lk in decal_looks.items()]):
            label = (f"Look {k + 1}" if self.hide_names else
                     (name[3:] if name.startswith("FR ") else name).replace("decal:", "Decal "))
            mat = self._material(lk, label, tiles, flat, cache)
            same = json.dumps({k: v for k, v in mat.items() if k != "name"}, sort_keys=True)
            if self.hide_names and same in cache:          # two groups that look alike: one material
                mat_index[name] = cache[same]
                continue
            if self.hide_names:
                mat["name"] = f"Look {len(self.gltf.doc['materials']) + 1}"
            mat_index[name] = cache[same] = self.gltf.material(mat)
        light = self._light_textures() if self._lit is not None else None
        self._light_info = light

        # -- meshes and parts
        unique = {}
        for ob in parts + marks:
            unique.setdefault(ob.data.name_full, ob.data)
        tri_total = sum(len(me.loop_triangles) for me in unique.values())
        packed = tri_total >= core.COMPRESS_FROM if self.compress is None else bool(self.compress)
        self.gltf.compress = packed
        if packed:
            meshopt_native()
        self.result["compressed"] = packed
        root = self.gltf.node({"name": "Model", "rotation": list(core.Z_UP_TO_Y_UP)})
        self._decal_meshes = {ob.parent.data.name_full for ob in marks
                              if ob.parent is not None and ob.parent.type == "MESH" and ob.parent.data is not None}
        mesh_of: dict = {}
        self._welded: dict = {}                # mesh -> (first corner of each vertex, vertex of each corner)
        self._nodes = []                       # (object, node index)
        triangles = 0
        everything = [(ob, False) for ob in parts] + [(ob, True) for ob in marks]
        for k, (ob, is_decal) in enumerate(everything):
            me = ob.data
            if is_decal:
                mats = (mat_index.get(f"decal:{ob.name}", -1),)
            else:
                mats = tuple(mat_index.get(s.material.name, -1) if s.material is not None else -1
                             for s in ob.material_slots) or (-1,)
            key = (me.name_full, mats, is_decal)
            if key not in mesh_of:
                need_uv = is_decal or any(_textured(self.gltf.doc["materials"][m]) for m in mats if m >= 0)
                mesh_of[key] = self._mesh(me, mats, is_decal, need_uv, len(mesh_of) + 1,
                                          light["first_uv"].get(me.name_full) if light else None)
            mesh, tris = mesh_of[key]
            if light is not None:
                mesh = self._lit_mesh(ob, mesh, light)
            triangles += tris
            mw = ob.matrix_world
            node = {"name": self._name(ob, k + 1, "Decal" if is_decal else "Part")}
            if not _is_identity(mw):
                node["matrix"] = _matrix_list(mw)
            mode = self._modes.get(ob.name)
            if mode:                           # task 0106: stays still / level while the vessel moves
                node["extras"] = {"fr_vm": mode}
            self._nodes.append((ob, self.gltf.place_mesh(node, mesh, root)))
            if k % 20 == 0:
                self.text = f"Writing part {k + 1} of {len(everything)}"
                yield 0.5 + 0.4 * k / max(len(everything), 1)

        # -- motion
        anim = False
        if self.animation:
            from . import animation
            if animation.has_keys(scene):
                anim = yield from self._motion()
        self.result.update(triangles=triangles, parts=len(parts), decals=len(marks), animated=anim)
        yield 1.0

    def _material(self, lk: Look, label: str, tiles: dict, flat: dict, cache: dict) -> dict:
        def get(ch, default):
            key = lk.src.get(ch)
            if key is not None:
                if key in tiles:
                    return tiles[key]
                return flat.get(key, default)
            return lk.const.get(ch, default)

        color = get("color", (0.8, 0.8, 0.8))
        alpha = get("alpha", 1.0)
        rough = get("rough", 0.5)
        metal = get("metal", 0.0)
        normal = get("normal", None)
        coat_n = get("coat_normal", None)
        pbr: dict = {}
        mat: dict = {"name": label, "pbrMetallicRoughness": pbr, "doubleSided": True}
        wrap = core.CLAMP if lk.decal else core.REPEAT

        def tex_info(index):                    # tiled looks: the parts' UVs are 16-bit, in 1/UV_Q tile
            info = {"index": index}
            if not lk.decal:
                info["extensions"] = json.loads(json.dumps(core.UV_TRANSFORM))
            return info

        c_tex = isinstance(color, np.ndarray)
        a_tex = isinstance(alpha, np.ndarray)
        if c_tex or a_tex:
            key = ("color", lk.src.get("color"), lk.src.get("alpha"), None if c_tex else color,
                   None if a_tex else alpha)
            if key not in cache:
                h, w = (color if c_tex else alpha).shape[:2]          # tiles are 8-bit already (pack_tile)
                rgb = color if c_tex else np.full((h, w, 3), 255, np.uint8)
                px = rgb
                if a_tex:
                    px = np.concatenate([rgb, alpha[..., None]], axis=2)
                cache[key] = self.gltf.texture(encode(px, "color"), wrap=wrap)
            pbr["baseColorTexture"] = tex_info(cache[key])
            fac = [1.0, 1.0, 1.0] if c_tex else [float(x) for x in color]
            pbr["baseColorFactor"] = fac + [1.0 if a_tex else float(alpha)]
        else:
            pbr["baseColorFactor"] = [float(x) for x in color] + [float(alpha)]
        if a_tex:
            mat["alphaMode"] = "BLEND" if lk.decal else "MASK"
            if not lk.decal:
                mat["alphaCutoff"] = 0.5
        elif float(alpha) < 0.999:
            mat["alphaMode"] = "BLEND"
        r_tex, m_tex = isinstance(rough, np.ndarray), isinstance(metal, np.ndarray)
        if r_tex or m_tex:
            key = ("orm", lk.src.get("rough"), lk.src.get("metal"))
            if key not in cache:
                h, w = (rough if r_tex else metal).shape[:2]
                px = np.zeros((h, w, 3), np.uint8)
                px[..., 0] = 255
                px[..., 1] = rough if r_tex else 255
                px[..., 2] = metal if m_tex else 255
                cache[key] = self.gltf.texture(encode(px, "orm"), wrap=wrap)
            pbr["metallicRoughnessTexture"] = tex_info(cache[key])
        pbr["roughnessFactor"] = 1.0 if r_tex else float(np.clip(rough, 0.0, 1.0))
        pbr["metallicFactor"] = 1.0 if m_tex else float(np.clip(metal, 0.0, 1.0))

        def normal_texture(arr, src_key):
            key = ("normal", src_key)
            if key not in cache:
                cache[key] = self.gltf.texture(encode(arr, "normal"), wrap=wrap)
            return tex_info(cache[key])

        if isinstance(normal, np.ndarray):
            mat["normalTexture"] = normal_texture(normal, lk.src["normal"])
        ext: dict = {}
        if lk.extra.get("coat", 0.0) > 0.0:
            cc = {"clearcoatFactor": float(lk.extra["coat"]), "clearcoatRoughnessFactor": float(lk.extra["coat_rough"])}
            if isinstance(coat_n, np.ndarray):
                cc["clearcoatNormalTexture"] = normal_texture(coat_n, lk.src["coat_normal"])
            ext["KHR_materials_clearcoat"] = cc
        if lk.extra.get("transmission", 0.0) > 0.0:
            ext["KHR_materials_transmission"] = {"transmissionFactor": float(lk.extra["transmission"])}
            ext["KHR_materials_ior"] = {"ior": float(lk.extra["ior"])}
        strength = lk.extra.get("emission_strength", 0.0)
        if strength > 0.0 and max(lk.extra.get("emission", (0, 0, 0))) > 0.0:
            mat["emissiveFactor"] = [float(min(1.0, c)) for c in lk.extra["emission"]]
            if strength != 1.0:
                ext["KHR_materials_emissive_strength"] = {"emissiveStrength": float(strength)}
        if ext:
            mat["extensions"] = ext
        return mat

    def _mesh(self, me, mats: tuple, is_decal: bool, need_uv: bool, number: int,
              light_uv: np.ndarray | None = None) -> tuple[int, int]:
        co, vert, nrm, uv, mi = mesh_arrays(me, own_uv=is_decal, uv=need_uv)
        vidx, qn, uvw, inverse, first = core.weld(vert, nrm, uv, light_uv, corners=True)
        tri = inverse.reshape(-1, 3)
        groups = []
        for slot in sorted(set(mi.tolist())):
            m = mats[slot] if 0 <= slot < len(mats) else mats[0]
            groups.append((m, tri[mi == slot]))
        name = f"Mesh {number}" if self.hide_names else me.name
        step = core.POS_STEP if (is_decal or me.name_full in self._decal_meshes) else core.POS_STEP_BIG
        k = self.gltf.mesh(name, co[vidx], qn, uvw, groups, max_step=step, tiled_uv=not is_decal)
        self._welded[k] = (first, inverse)
        return k, len(tri)

    # -- baked light (task 0107)
    def _bake_light(self, parts, marks):
        from . import lightbake
        targets = [ob for ob in parts + marks if not len(ob.modifiers)]
        live = [ob for ob in parts if len(ob.modifiers)]       # hoses and cables drawn by modifiers stay live
        ch = self.surroundings or {}
        sky = None
        if ch.get("sky_source") == "TIME":
            sky = {"sun_height": float(ch["sun_height"]), "sun_direction": float(ch["sun_direction"])}
        self._bake = lightbake.Bake(targets, self.light, sky=sky, occluders=live, quality=self.light_quality,
                                    texels_per_m=self.light_texels or None, samples=self.light_samples or None,
                                    scene=self.scene)
        for f in self._bake.steps():
            self.text = self._bake.text
            yield ("light", f)
        self._lit = self._bake.result
        self._bake = None

    def _light_textures(self) -> dict:
        """The atlases as pictures and the scale of the light factors: {"scale", "atlas" (texture index per
        atlas), "lit" {(material, atlas): material}, "first_uv" {mesh name: a copy's light UVs}, "ref"}."""
        from ..core import lightmap as lm
        res = self._lit
        ref = np.maximum(np.asarray(res.reference, np.float64), 1e-6)
        factors = [a / ref for a in res.atlases]
        factors += [it.corners / ref for it in res.items.values() if it.kind == "VERTEX"]
        scale = lm.scale_of(factors) if factors else 1.0
        before = self.gltf.image_bytes
        atlas = []
        for a in res.atlases:
            atlas.append(self.gltf.texture(jpeg(lm.encode(a / ref, scale), LIGHT_JPG), wrap=core.CLAMP))
        first_uv = {}
        by_name = {it.name: it for it in res.items.values()}
        for ob in self.scene.objects:
            it = by_name.get(ob.name)
            if it is not None and it.kind == "MAP" and it.uv is not None and ob.data is not None:
                first_uv.setdefault(ob.data.name_full, it.uv)
        self._light_bytes = self.gltf.image_bytes - before
        return {"scale": scale, "atlas": atlas, "lit": {}, "first_uv": first_uv, "ref": ref, "by_name": by_name}

    def _lit_mesh(self, ob, mesh: int, light: dict) -> int:
        """The mesh a baked copy shows: ``mesh`` plus its own light UVs or light per vertex."""
        from ..core import lightmap as lm
        it = light["by_name"].get(ob.name)
        if it is None:
            return mesh
        first, inverse = self._welded[mesh]
        start = len(self.gltf._bin)
        if it.kind == "MAP" and it.uv is not None:
            uv = np.asarray(it.uv, np.float64)[first]
            uv[:, 1] = 1.0 - uv[:, 1]                    # glTF's V runs down the picture
            q = np.clip(np.round(uv * 65535.0), 0, 65535).astype(np.uint16)
            acc = self.gltf.vertex_attribute(mesh, q, "VEC2", core.USHORT)
            swap = {}
            for p in self.gltf.doc["meshes"][mesh]["primitives"]:
                m = p.get("material")
                if m is None:
                    continue
                key = (m, it.atlas)
                if key not in light["lit"]:
                    mat = json.loads(json.dumps(self.gltf.doc["materials"][m]))
                    mat["occlusionTexture"] = {"index": light["atlas"][it.atlas], "texCoord": 1}
                    mat["name"] = f"{mat.get('name', 'Look')} · light {it.atlas + 1}"
                    light["lit"][key] = self.gltf.material(mat)
                swap[m] = light["lit"][key]
            k = self.gltf.mesh_variant(mesh, {"TEXCOORD_1": acc}, swap)
        elif it.kind == "VERTEX" and it.corners is not None:
            n = len(first)
            v = np.zeros((n, 3), np.float64)
            c = np.zeros(n, np.float64)
            np.add.at(v, inverse, it.corners)
            np.add.at(c, inverse, 1.0)
            f = v / np.maximum(c, 1.0)[:, None] / light["ref"]
            acc = self.gltf.vertex_attribute(mesh, lm.encode(f, light["scale"]), "VEC3", core.UBYTE)
            k = self.gltf.mesh_variant(mesh, {"_FR_LIGHT": acc})
        else:
            return mesh
        self._light_bytes += len(self.gltf._bin) - start
        return k

    def _motion(self):
        scene = self.scene
        fps = scene.render.fps / scene.render.fps_base
        frames = list(range(scene.frame_start, scene.frame_end + 1))
        if len(frames) < 2:
            return False
        keep = scene.frame_current
        obs = [ob for ob, _ in self._nodes]
        mats = np.empty((len(frames), len(obs), 4, 4), np.float32)
        try:
            for i, f in enumerate(frames):
                scene.frame_set(f)
                for j, ob in enumerate(obs):
                    mats[i, j] = np.array(ob.matrix_world)
                if i % 10 == 0:
                    self.text = f"Reading the motion: frame {f} of {frames[-1]}"
                    yield 0.9 + 0.08 * i / len(frames)
        finally:
            scene.frame_set(keep)
        moving = np.where(np.abs(mats - mats[:1]).max(axis=(0, 2, 3)) > 1e-6)[0]
        if not len(moving):
            return False
        tracks = []
        for j in moving:
            ob, node = self._nodes[j]
            t, q, s = core.decompose(mats[:, j])
            nd = self.gltf.doc["nodes"][node]
            nd.pop("matrix", None)
            here = frames.index(keep) if keep in frames else 0
            nd["translation"] = [float(v) for v in t[here]]
            nd["rotation"] = [float(v) for v in q[here]]
            if np.abs(s - 1.0).max() > 1e-5:
                nd["scale"] = [float(v) for v in s[here]]
            tracks.append((node, "translation", t))
            tracks.append((node, "rotation", q))
            if np.abs(s - s[:1]).max() > 1e-5:
                tracks.append((node, "scale", s))
        times = (np.array(frames, np.float64) - frames[0]) / fps
        self.gltf.animation(scene.fresing.anim_baked or "Animation", times, tracks)
        return True

    def finish(self) -> dict:
        """Writes ``<name>.glb`` (and ``<name>.html``) next to each other; returns the numbers."""
        data = self.gltf.glb()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".part"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, self.path)
        page = os.path.splitext(self.path)[0] + ".html"
        extra = 0
        if self.page:
            title = os.path.splitext(os.path.basename(self.path))[0]
            text = core.viewer_html(title, glb=data, animated=bool(self.result.get("animated")),
                                    note="Made with Fresing Render")
            if self.surroundings is not None or self._lit is not None:  # 0106: three.js page; 0107: baked light
                from ..core import web3d_env as env
                from . import web3d_env
                plain = len(text.encode("utf-8"))
                ch = self.surroundings if self.surroundings is not None else web3d_env.plain_choice(self.scene)
                st, pictures = web3d_env.block(self.scene, ch, *self._bounds, self._floor)
                if self._lit is not None:
                    st["light"] = env.light_block({"light": self.light, "scale": float(self._light_info["scale"]),
                                                   "curve": 2.0, "sun": float(self._lit.sun_ratio)})
                    if self.surroundings is None:
                        st["plain"] = True
                text = env.page_html(title, data, st, pictures, note="Made with Fresing Render",
                                     animated=bool(self.result.get("animated")))
                extra = len(text.encode("utf-8")) - plain
                self.result.update(env_items=env.items_text(st), env_bytes=extra,
                                   env_pictures=sum(len(b) for _m, b in pictures.values()))
            with open(page + ".part", "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(page + ".part", page)
        seconds = time.perf_counter() - self.t0
        textures = len(self.gltf.doc["images"])
        self.result.update(path=self.path, html=page if self.page else "", size=len(data), textures=textures,
                           texture_bytes=self.gltf.image_bytes, seconds=seconds,
                           text=core.result_line(len(data), self.result.get("triangles", 0), textures, seconds,
                                                 compressed=self.gltf.compress))
        if self.surroundings is not None and self.page:
            self.result["text"] += " · " + core.surroundings_line(extra)
        if self._lit is not None:
            from . import lightbake
            lit = self._lit
            self.result.update(light=self.light, light_label=lightbake.label(self.light),
                               light_seconds=lit.seconds, light_bytes=int(self._light_bytes),
                               light_atlases=len(lit.atlases), light_texels=lit.texels,
                               light_items=len(lit.items), light_problems=list(lit.problems))
            self.result["text"] += " · " + core.light_line(self.light, int(self._light_bytes), lit.seconds)
        return self.result

    def run(self) -> dict:
        for _ in self.steps():
            pass
        return self.finish()


def light_targets(scene) -> list:
    """The objects whose light an export bakes (task 0107): the shown parts and decals that no modifier draws."""
    parts, marks = objects(scene)
    return [ob for ob in parts + marks if not len(ob.modifiers)]


def light_estimate(scene) -> dict:
    """The panel's estimate of the bake, kept while the shown parts and the settings stay the same."""
    from . import lightbake
    w = settings(scene)
    obs = light_targets(scene)
    key = (w.light, w.light_quality, round(float(w.light_texels), 1), len(obs),
           sum(len(ob.data.polygons) for ob in obs[:2000]), scene.cycles.device if hasattr(scene, "cycles") else "")
    rt = runtime(scene)
    if rt.get("estimate_key") != key:
        rt["estimate_key"] = key
        rt["estimate"] = lightbake.quick_estimate(obs, w.light, w.light_quality, w.light_texels or None,
                                                  key[-1])
    return rt["estimate"]


def needs_light_question(scene) -> bool:
    """Everything baked while the export moves: an animation in the file or vessel motion on the page."""
    w = settings(scene)
    if w.light != "ALL":
        return False
    from . import animation, vessel_motion
    moving = w.animation and animation.has_keys(scene)
    return bool(moving or (w.env_mode == "PROJECT" and w.env_vessel and vessel_motion.effective(scene)))


def remember(scene, out: dict) -> None:
    """The last export's line and files, shown in the panel."""
    w = settings(scene)
    w.last_path = out.get("path", "")
    w.last_html = out.get("html", "")
    w.last_text = out.get("text", "")
    w.last_size = int(out.get("size", 0))


def export(scene, path: str, **kw) -> dict:
    """Export at once (no progress): scripts, tests, PC check and tour."""
    out = Job(scene, path, **kw).run()
    remember(scene, out)
    return out
