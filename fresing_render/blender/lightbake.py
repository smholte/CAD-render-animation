"""Baked light (task 0107): Cycles bakes the light that falls on placed parts, per object, for the web 3D model and
for other lanes (the House lane calls ``bake`` on imported houses).

The three choices (names fixed – the house format uses them):

* ``LIVE`` "Live only" – nothing is baked.
* ``SOFT`` "Soft light baked, sun live" – the sky's light without its sun (direct + bounce) plus the bounce of the sun,
  and every lamp. Made of two passes: *direct* light with a copy of the world whose sky has no sun disc, plus
  *indirect* light with the world as it is.
* ``ALL`` "Everything baked" – sky, sun and lamps, direct + bounce, one pass.

What is baked is Cycles' ``DIFFUSE`` light without the surface colour: the colour a white matte surface shows in the
render (linear, before exposure and the view transform). ``Result.reference`` is the same light on an open, upward
surface (a probe quad far from everything): value / reference is the *light factor* the web page uses.

Every object gets its own result, also objects that share a mesh. Where light is stored per object:

* ``MAP``: a lightmap. ``uv="AUTO"``: the app unwraps each unique mesh once (``core/lightmap.unwrap``) and gives every
  copy its own place in shared atlases; ``uv="UV1"``: the mesh's second UV layer as it is, one image per object.
* ``VERTEX``: light per corner (and per vertex), for small parts with many copies where that is smaller.

Nothing in the project is changed: the bake runs in a copy of a Cycles scene (``web3d.Baker``) with new objects,
triangle-mesh copies (targets), world copies and material copies, all removed at the end – also on an error or Cancel.
"""

from __future__ import annotations

import math
import os
import tempfile
import time
from dataclasses import dataclass, field

import bpy
import numpy as np

from ..core import lightmap as lm
from ..core.web3d import Cancelled

CHOICES = (("LIVE", "Live only"), ("SOFT", "Soft light baked, sun live"), ("ALL", "Everything baked"))
_BY_LABEL = {label.lower(): key for key, label in CHOICES}
NAME = "FR light bake"
UV_NAME = "fr_light"
# Speed for the estimate, measured on the 4-core web machine (CPU), 13 Nov 2026: Cycles DIFFUSE bake, texel x sample
# per second per pass (demo vessel, Draft: 8.4 M texels x 16 samples x 2 passes in 31 s), plus a fixed cost per bake
# call (scene sync, read back) and per atlas (denoise ~1.9 s at 2048 px). The RTX 3090 figure is an estimate:
# GPU_FACTOR times faster than these 4 cores, labelled so in the panel.
RATE_CPU = 8.0e6
GPU_FACTOR = 20.0
CALL_SECONDS = 2.0
BYTES_PER_TEXEL = 0.32                 # JPEG of the atlases at quality 90 + vertex light (demo vessel, Draft: 0.32)
BATCH_TEXEL_SAMPLES = 6.0e7            # one bake call at most this many texel x samples (Cancel answers within ~30 s)


def choice_id(light) -> str:
    """'LIVE' | 'SOFT' | 'ALL' from an id or a label ('Soft light baked, sun live')."""
    s = str(light or "LIVE").strip()
    if s.upper() in ("LIVE", "SOFT", "ALL"):
        return s.upper()
    key = _BY_LABEL.get(s.lower())
    if key is None:
        raise ValueError(f"Unknown light choice {light!r}: use one of {[k for k, _ in CHOICES]}")
    return key


def label(light) -> str:
    return dict(CHOICES)[choice_id(light)]


@dataclass
class Item:
    """Baked light of one object (see the module text)."""
    id: str
    name: str
    kind: str                                # "MAP" | "VERTEX"
    texels_per_m: float = 0.0
    pixels: np.ndarray | None = None         # MAP: (h, w, 3) float32, row 0 at the bottom (shared by an atlas' items)
    uv: np.ndarray | None = None             # MAP, uv="AUTO": (loop triangles * 3, 2) float32 in 0..1 of ``pixels``
    loop_uv: np.ndarray | None = None        # MAP, uv="AUTO": (loops, 2) in Blender loop order (None if a loop has two)
    atlas: int = -1                          # MAP, uv="AUTO": which atlas (Result.atlases)
    values: np.ndarray | None = None         # VERTEX: (vertices, 3) float32, the mesh's vertex order
    corners: np.ndarray | None = None        # VERTEX: (loop triangles * 3, 3) float32, the mesh's loop-triangle order


@dataclass
class Result:
    light: str = "LIVE"
    items: dict = field(default_factory=dict)
    reference: tuple = (1.0, 1.0, 1.0)
    samples: int = 0
    texels_per_m: float = 0.0
    seconds: float = 0.0
    problems: list = field(default_factory=list)
    atlases: list = field(default_factory=list)     # (h, w, 3) float32 each, row 0 at the bottom
    sun_separate: bool = True                        # SOFT: False when the world has no sky sun (photo, studio)
    reference_sky: tuple = (1.0, 1.0, 1.0)           # the sky's light alone (no sun disc) on the open probe
    sun_ratio: float = 0.0                           # ALL: (reference - reference_sky) / reference_sky (luminance)
    atlas_size: int = 0                              # px of the (square) atlases
    texels: int = 0
    vertices: int = 0
    timing: dict = field(default_factory=dict)      # s per stage: plan, setup, bake, clean


# ---------------------------------------------------------------------------
# reading meshes
# ---------------------------------------------------------------------------

@dataclass
class _MeshData:
    points: np.ndarray        # (n, 3) float64
    tris: np.ndarray          # (m, 3) int32 vertex indices
    loops: np.ndarray         # (m*3,) int32 loop index of each corner
    normals: np.ndarray       # (m*3, 3) float32 corner normals
    mat: np.ndarray           # (m,) int32
    uvs: dict                 # name -> (m*3, 2) float32
    active_render: str
    area: float               # local m²
    unwrap: object = None


def _read_mesh(me) -> _MeshData:
    me.calc_loop_triangles() if hasattr(me, "calc_loop_triangles") else None
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
    co = co.reshape(-1, 3).astype(np.float64)
    cn = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", cn)
    cn = cn.reshape(-1, 3)
    uvs = {}
    render = ""
    for layer in me.uv_layers:
        u = np.empty(len(me.loops) * 2, np.float32)
        layer.data.foreach_get("uv", u)
        uvs[layer.name] = u.reshape(-1, 2)[loops]
        if layer.active_render:
            render = layer.name
    tris = cv[loops].reshape(-1, 3)
    p = co[tris]
    area = float(0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum()) if m else 0.0
    return _MeshData(co, tris, loops, cn[loops], mi, uvs, render, area)


def _world_area(md: _MeshData, mw) -> float:
    if not len(md.tris):
        return 0.0
    m3 = np.array([[mw[r][c] for c in range(3)] for r in range(3)], np.float64)
    p = (md.points @ m3.T)[md.tris]
    return float(0.5 * np.linalg.norm(np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0]), axis=1).sum())


def _scale(mw) -> float:
    return float(max(math.sqrt(sum(mw[r][c] ** 2 for r in range(3))) for c in range(3)))


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

class Bake:
    """One bake. ``estimate()`` before it starts; ``steps()`` yields 0 … 1 (``text`` says what it does);
    ``result`` at the end. ``bake()`` does it all at once."""

    def __init__(self, objects, light="SOFT", *, world=None, sky=None, occluders=(), lamps=None, ids=None,
                 uv="AUTO", quality="NORMAL", texels_per_m=None, samples=None, device="AUTO", progress=None,
                 scene=None, denoise=True):
        self.light = choice_id(light)
        self.objects = [ob for ob in objects if ob is not None and ob.type == "MESH" and ob.data is not None]
        self.scene = scene or (self.objects[0].users_scene[0] if self.objects and self.objects[0].users_scene
                               else bpy.context.scene)
        self.world = world if world is not None else self.scene.world
        self.sky = dict(sky) if sky else None
        self.occluders = [ob for ob in occluders if ob is not None and ob not in set(self.objects)]
        self.lamps = lamps
        self.ids = dict(ids or {})
        self.uv = str(uv).upper()
        if self.uv not in ("AUTO", "UV1", "VERTEX"):
            raise ValueError(f"uv must be AUTO, UV1 or VERTEX, not {uv!r}")
        self.quality = quality if quality in lm.QUALITY else "NORMAL"
        q = lm.QUALITY[self.quality]
        self.samples = int(samples or q["samples"])
        self.padding = int(q["padding"])
        self.tpm_wanted = texels_per_m
        self.device = device
        self.progress = progress
        self.denoise = denoise
        self.text = "Starting"
        self.result = Result(light=self.light, samples=self.samples)
        self._plan = None
        self._baker = None
        self._cancel = False

    # -- the plan: which object gets what
    def id_of(self, ob) -> str:
        if ob in self.ids:
            return str(self.ids[ob])
        if ob.name in self.ids:
            return str(self.ids[ob.name])
        v = ob.get("fr_id")
        return str(v) if v else ob.name

    def plan(self) -> dict:
        if self._plan is not None:
            return self._plan
        meshes: dict = {}
        rows = []
        problems = []
        clear = [ob for ob in self.objects if see_through(ob)]
        if clear:                                   # glass keeps live light on the page; it lets light through here
            self.occluders += [ob for ob in clear if ob not in self.occluders]
            self.objects = [ob for ob in self.objects if ob not in set(clear)]
        for ob in self.objects:
            key = ob.data.name_full
            if key not in meshes:
                meshes[key] = _read_mesh(ob.data)
            md = meshes[key]
            if not len(md.tris):
                continue
            rows.append({"ob": ob, "md": md, "area": _world_area(md, ob.matrix_world), "scale": _scale(ob.matrix_world)})
        total = sum(r["area"] for r in rows)
        budget = lm.QUALITY[self.quality]["budget"]
        tpm = float(self.tpm_wanted) if self.tpm_wanted else lm.texels_per_m(max(total, 1e-9), budget)
        tpm = float(np.clip(tpm, lm.MIN_TPM, lm.MAX_TPM))
        maps, verts, own = [], [], []
        for r in rows:
            md = r["md"]
            n_v = len(md.points)
            if self.uv == "VERTEX":
                r["kind"] = "VERTEX"
            elif self.uv == "UV1":
                names = list(md.uvs)
                if len(names) < 2:
                    problems.append(f"{r['ob'].name}: no 2nd UV layer – baked per vertex")
                    r["kind"] = "VERTEX"
                else:
                    r["kind"] = "OWN"
                    r["uv1"] = names[1]
            else:
                r["kind"] = ("VERTEX" if lm.prefer_vertex(n_v, r["area"], tpm, float(max(r["ob"].dimensions)))
                             else "MAP")
            (maps if r["kind"] == "MAP" else verts if r["kind"] == "VERTEX" else own).append(r)
        # app-made lightmap UVs: one unwrap per unique mesh, a place per copy
        sizes = []
        for r in maps:
            md = r["md"]
            if md.unwrap is None:
                md.unwrap = lm.unwrap(md.points, md.tris)
            r["tpm"] = tpm
            for _ in range(40):                         # all charts of one copy go in one atlas: shrink until they fit
                px = lm.chart_pixels(md.unwrap.size * r["scale"], r["tpm"], self.padding)
                if lm.fits(px, lm.ATLAS):
                    break
                r["tpm"] *= 0.85
            else:
                problems.append(f"{r['ob'].name}: too big for one light picture – its light is coarse")
            r["px"] = px
            sizes.append(px)
        atlas_px = lm.ATLAS
        places = lm.pack(sizes, lm.ATLAS) if sizes else []
        if places and max(int(pl[:, 0].max()) for pl in places) == 0:      # one atlas: as small as it can be
            for side in (256, 512, 1024):
                if all(lm.fits(px, side) for px in sizes):
                    try:
                        small = lm.pack(sizes, side)
                    except ValueError:
                        continue
                    if max(int(pl[:, 0].max()) for pl in small) == 0:
                        places, atlas_px = small, side
                        break
        n_atlas = 0
        for r, pl in zip(maps, places):
            r["places"] = pl
            n_atlas = max(n_atlas, int(pl[:, 0].max()) + 1)
        for r in own:
            md = r["md"]
            u = md.uvs[r["uv1"]].reshape(-1, 3, 2).astype(np.float64)
            e1, e2 = u[:, 1] - u[:, 0], u[:, 2] - u[:, 0]
            uv_area = float(np.clip(0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]).sum(), 1e-6, 1.0))
            r["size"] = lm.image_size(r["area"], uv_area, tpm)
            r["tpm"] = tpm
        texels = n_atlas * atlas_px * atlas_px if maps else 0
        texels += sum(w * h for w, h in (r["size"] for r in own))
        vertices = sum(len(r["md"].points) for r in verts)
        passes = 2 if self.light == "SOFT" and self._has_sky_sun() else 1
        self._plan = {"rows": rows, "maps": maps, "verts": verts, "own": own, "atlases": n_atlas, "tpm": tpm,
                      "texels": texels, "vertices": vertices, "passes": passes, "problems": problems, "atlas_px": atlas_px,
                      "area": total}
        return self._plan

    def estimate(self) -> dict:
        p = self.plan()
        calls = p["passes"] * (max(1, p["atlases"]) + len(p["own"]) + (1 if p["verts"] else 0))
        est = lm.estimate(p["texels"], p["vertices"], self.samples, p["passes"], RATE_CPU, GPU_FACTOR,
                          BYTES_PER_TEXEL)
        est["seconds_cpu"] += calls * CALL_SECONDS
        est["seconds_gpu"] += calls * CALL_SECONDS
        est.update(texels=p["texels"], vertices=p["vertices"], atlases=p["atlases"], texels_per_m=p["tpm"],
                   passes=p["passes"])
        return est

    def cancel(self) -> None:
        self._cancel = True

    def _tick(self, f: float, text: str) -> float:
        self.text = text
        if self._cancel or (self.progress is not None and self.progress(f, text) is False):
            raise Cancelled()
        return f

    # -- the world
    def _sky_nodes(self, world):
        if world is None or world.node_tree is None:
            return []
        return [n for n in world.node_tree.nodes if n.type == "TEX_SKY"]

    def _has_sky_sun(self) -> bool:
        return any(getattr(n, "sun_disc", False) for n in self._sky_nodes(self.world))

    def _world_copy(self, disc: bool):
        if self.world is None:
            return None
        w = self.world.copy()
        w.name = NAME
        self._baker.ids.append(w)
        for n in self._sky_nodes(w):
            if self.sky:
                if "sun_height" in self.sky:
                    n.sun_elevation = math.radians(float(self.sky["sun_height"]))
                if "sun_direction" in self.sky:
                    n.sun_rotation = math.radians(float(self.sky["sun_direction"]))
            if not disc and hasattr(n, "sun_disc"):
                n.sun_disc = False
        return w

    # -- the scene
    def _device(self, sc) -> None:
        want = self.device
        if want == "AUTO":
            want = self.scene.cycles.device if hasattr(self.scene, "cycles") else "CPU"
        sc.cycles.device = "GPU" if want == "GPU" else "CPU"

    def _material_with_image(self, mat, img, cache: dict):
        key = (mat.name_full if mat is not None else "", img.name)
        if key in cache:
            return cache[key]
        m = self._matte(mat, cache).copy()
        m.name = NAME
        self._baker.ids.append(m)
        nt = m.node_tree
        if nt is None:
            try:
                m.use_nodes = True
            except Exception:  # noqa: BLE001 - Blender 6 has nodes always
                pass
            nt = m.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.name = NAME
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node
        cache[key] = m
        return m

    def _matte(self, mat, cache: dict):
        """A copy of ``mat`` whose surface takes matte light: Metallic 0 (a metal has no matte light, so its baked
        light – and its reflections' shading on the page – would be black)."""
        key = ("matte", mat.name_full if mat is not None else "")
        if key in cache:
            return cache[key]
        m = bpy.data.materials.new(NAME) if mat is None else mat.copy()
        m.name = NAME
        self._baker.ids.append(m)
        if m.node_tree is not None:
            for n in m.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED" and "Metallic" in n.inputs:
                    sock = n.inputs["Metallic"]
                    for link in list(sock.links):
                        m.node_tree.links.remove(link)
                    sock.default_value = 0.0
        cache[key] = m
        return m

    def _joined(self, entries, colour: bool, material_of) -> list:
        """One bake object (world coordinates) of many placed copies; decals in a second one that casts no shadow.
        ``entries``: [(plan row, light UVs (corners, 2) or None)]. Returns [(object, {row index in
        p["verts"] or p["maps"] order: (first corner, end corner)})]."""
        from . import decals
        out = []
        plain = [(k, e) for k, e in enumerate(entries) if not decals.is_decal(e[0]["ob"])]
        marks = [(k, e) for k, e in enumerate(entries) if decals.is_decal(e[0]["ob"])]
        verts = self.plan()["verts"]
        for part, shadow in ((plain, True), (marks, False)):
            if not part:
                continue
            names: list = []
            for _k, (r, _uv) in part:
                for n in r["md"].uvs:
                    if n not in names:
                        names.append(n)
            pts, tris, nrm, mi, lights = [], [], [], [], []
            uvs = {n: [] for n in names}
            mats: list = []
            mat_ix: dict = {}
            ranges: dict = {}
            off = corner = 0
            for _k, (r, uv) in part:
                md, ob = r["md"], r["ob"]
                mw = np.array(ob.matrix_world, np.float64)
                m3 = mw[:3, :3]
                pts.append(md.points @ m3.T + mw[:3, 3])
                tris.append(md.tris + off)
                nm = np.linalg.inv(m3).T if abs(np.linalg.det(m3)) > 1e-12 else m3
                n = md.normals.astype(np.float64) @ nm.T
                n /= np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]
                nrm.append(n)
                slots = [sl.material for sl in ob.material_slots] or [None]
                local = []
                for m in slots:
                    key = m.name_full if m is not None else ""
                    if key not in mat_ix:
                        mat_ix[key] = len(mats)
                        mats.append(material_of(m))
                    local.append(mat_ix[key])
                local = np.asarray(local, np.int32)
                mi.append(local[np.clip(md.mat, 0, len(local) - 1)])
                n_c = len(md.tris) * 3
                for name in names:
                    uvs[name].append(md.uvs.get(name, np.zeros((n_c, 2), np.float32)))
                if uv is not None:
                    lights.append(np.asarray(uv, np.float32))
                if colour:
                    ranges[next(i for i, v in enumerate(verts) if v is r)] = (corner, corner + n_c)
                off += len(md.points)
                corner += n_c
            md0 = part[0][1][0]["md"]
            joined = _MeshData(np.concatenate(pts), np.concatenate(tris).astype(np.int32), None,
                               np.concatenate(nrm).astype(np.float32), np.concatenate(mi).astype(np.int32),
                               {n: np.concatenate(v) for n, v in uvs.items()}, md0.active_render, 0.0)
            me = self._mesh_from(joined, np.concatenate(lights) if lights else None, colour, mats)
            o = bpy.data.objects.new(NAME, me)
            for k, v in (("fr_ax_long", (1.0, 0.0, 0.0)), ("fr_ax_round", (1.0, 0.0, 0.0)),
                         ("fr_ax_centre", (0.0, 0.0, 0.0))):
                o[k] = v
            if not shadow:
                o.visible_shadow = False
            self._baker.scene.collection.objects.link(o)
            self._baker.ids.append(o)
            out.append((o, ranges))
        return out

    def _target_mesh(self, ob, md: _MeshData, uv: np.ndarray | None, colour: bool):
        """A triangle copy of ``ob``'s mesh (in its own coordinates) with its corner normals, UV layers and
        materials (+ the light UVs)."""
        mats = [slot.material for slot in ob.material_slots] or [None]
        return self._mesh_from(md, uv, colour, mats)

    def _mesh_from(self, md: _MeshData, uv: np.ndarray | None, colour: bool, materials: list):
        """A triangle copy of ``ob``'s mesh with its corner normals, UV layers and materials (+ the light UVs)."""
        me = bpy.data.meshes.new(NAME)
        self._baker.ids.append(me)
        n_v, n_t = len(md.points), len(md.tris)
        me.vertices.add(n_v)
        me.vertices.foreach_set("co", md.points.astype(np.float32).ravel())
        me.loops.add(n_t * 3)
        me.loops.foreach_set("vertex_index", md.tris.astype(np.int32).ravel())
        me.polygons.add(n_t)
        me.polygons.foreach_set("loop_start", np.arange(0, n_t * 3, 3, dtype=np.int32))
        me.polygons.foreach_set("material_index", md.mat)
        me.update(calc_edges=True)
        a = me.attributes.new("custom_normal", "FLOAT_VECTOR", "CORNER")
        a.data.foreach_set("vector", md.normals.astype(np.float32).ravel())
        for name, arr in md.uvs.items():
            layer = me.uv_layers.new(name=name)
            layer.data.foreach_set("uv", arr.astype(np.float32).ravel())
        if md.active_render and md.active_render in me.uv_layers:
            me.uv_layers[md.active_render].active_render = True
        if uv is not None:
            layer = me.uv_layers.new(name=UV_NAME)
            layer.data.foreach_set("uv", np.asarray(uv, np.float32).ravel())
            me.uv_layers.active = layer
            if md.active_render and md.active_render in me.uv_layers:
                me.uv_layers[md.active_render].active_render = True
        if colour:
            ca = me.color_attributes.new(UV_NAME, "FLOAT_COLOR", "CORNER")
            me.color_attributes.active_color = ca
        for m in materials:
            me.materials.append(m)
        return me

    def _object(self, me, mw, src):
        o = bpy.data.objects.new(NAME, me)
        o.matrix_world = mw
        if src is not None:
            from . import decals
            if decals.is_decal(src):              # a sticker lies 0.2 mm above its part: it casts no shadow
                o.visible_shadow = False
        self._baker.scene.collection.objects.link(o)
        self._baker.ids.append(o)
        return o

    def _lamps(self) -> list:
        if self.lamps is not None:
            return [ob for ob in self.lamps if ob is not None and ob.type == "LIGHT"]
        out = []
        for ob in self.scene.objects:
            if ob.type == "LIGHT" and not ob.hide_render:
                try:
                    if not ob.visible_get():
                        continue
                except RuntimeError:
                    continue
                out.append(ob)
        return out

    def steps(self):
        t0 = time.perf_counter()
        from . import web3d
        try:
            yield self._tick(0.0, "Planning the light bake")
            t = time.perf_counter()
            p = self.plan()
            self.result.timing["plan"] = time.perf_counter() - t
            t = time.perf_counter()
            res = self.result
            res.problems += p["problems"]
            res.texels_per_m = p["tpm"]
            if self.light == "LIVE" or not p["rows"]:
                res.seconds = time.perf_counter() - t0
                return
            self._baker = web3d.Baker(self.scene)
            sc = self._baker.scene
            sc.name = NAME
            sc.cycles.samples = self.samples
            sc.cycles.use_denoising = False
            self._device(sc)
            bk = sc.render.bake
            bk.margin = self.padding
            bk.margin_type = "EXTEND"
            bk.use_clear = True
            bk.use_pass_color = False
            yield self._tick(0.02, "Setting up the light bake")
            # images
            atlases = []
            A = p["atlas_px"]
            res.atlas_size = A
            for _ in range(p["atlases"]):
                img = bpy.data.images.new(NAME, A, A, alpha=True, float_buffer=True)
                img.colorspace_settings.name = "Non-Color"
                self._baker.ids.append(img)
                atlases.append(img)
            mat_cache: dict = {}
            # Cycles bakes one object at a time over its whole image (CLAUDE.md, task 0099): every atlas' copies go
            # into ONE bake object (world coordinates), decals into a second one that casts no shadow
            groups: list = [[] for _ in atlases]           # bake objects per atlas
            own_objs = []                                  # (row, object, image)
            per_atlas: list = [[] for _ in atlases]
            for r in p["maps"]:
                md = r["md"]
                uv, which = lm.place_uv(md.unwrap, r["tpm"] * r["scale"], r["places"], self.padding, A)
                r["uv"] = uv
                r["atlas"] = int(which[0]) if len(which) else 0
                per_atlas[r["atlas"]].append((r, uv))
            for a, entries in enumerate(per_atlas):
                for o, _rng in self._joined(entries, False,
                                            lambda m, a=a: self._material_with_image(m, atlases[a], mat_cache)):
                    groups[a].append(o)
            for r in p["own"]:
                w, h = r["size"]
                img = bpy.data.images.new(NAME, w, h, alpha=True, float_buffer=True)
                img.colorspace_settings.name = "Non-Color"
                self._baker.ids.append(img)
                md = r["md"]
                me = self._target_mesh(r["ob"], md, md.uvs[r["uv1"]], False)
                o = self._object(me, r["ob"].matrix_world, r["ob"])
                for k, m in enumerate(me.materials):
                    me.materials[k] = self._material_with_image(m, img, mat_cache)
                own_objs.append((r, o, img))
            vert_jobs = []                                 # (rows, [(object, {row index: corner range})])
            chunk, size = [], 0
            for k, r in enumerate(p["verts"]):
                chunk.append(k)
                size += len(r["md"].tris) * 3 * self.samples
                if size > BATCH_TEXEL_SAMPLES or k == len(p["verts"]) - 1:
                    entries = [(p["verts"][i], None) for i in chunk]
                    vert_jobs.append((list(chunk), self._joined(entries, True, lambda m: self._matte(m, mat_cache))))
                    chunk, size = [], 0
            for ob in self.occluders:
                me = ob.data if ob.type == "MESH" else None
                if me is None:
                    continue
                self._object(me, ob.matrix_world, None)
            for lamp in self._lamps():
                o = bpy.data.objects.new(NAME, lamp.data)
                o.matrix_world = lamp.matrix_world
                sc.collection.objects.link(o)
                self._baker.ids.append(o)
            # the probe: an open upward quad far from everything
            probe_img = bpy.data.images.new(NAME, 8, 8, alpha=True, float_buffer=True)
            probe_img.colorspace_settings.name = "Non-Color"
            self._baker.ids.append(probe_img)
            probe = self._probe(probe_img, mat_cache)
            # passes
            if self.light == "SOFT" and self._has_sky_sun():
                passes = [(self._world_copy(False), {"DIRECT"}, "sky"), (self._world_copy(True), {"INDIRECT"}, "bounce")]
            else:
                passes = [(self._world_copy(True), {"DIRECT", "INDIRECT"}, "light")]
                res.sun_separate = self.light != "SOFT"
                if self.light == "SOFT":
                    res.problems.append("The light has no separate sun (a 360° photo or studio light): all of it "
                                        "is baked")
            acc = [np.zeros((A, A, 3), np.float32) for _ in atlases]
            mask = [np.zeros((A, A), bool) for _ in atlases]
            own_acc = [np.zeros((img.size[1], img.size[0], 3), np.float32) for _r, _o, img in own_objs]
            own_mask = [np.zeros((img.size[1], img.size[0]), bool) for _r, _o, img in own_objs]
            vert_acc = [np.zeros((len(r["md"].tris) * 3, 3), np.float32) for r in p["verts"]]
            ref = np.zeros(3, np.float64)
            jobs = []                                   # (kind, index, objects)
            for a, grp in enumerate(groups):
                if grp:
                    jobs.append(("atlas", a, grp))
            for k, (_r, o, _img) in enumerate(own_objs):
                jobs.append(("own", k, [o]))
            for k, (_rows, parts) in enumerate(vert_jobs):
                jobs.append(("vert", k, [o for o, _rng in parts]))
            n_calls = len(passes) * (len(jobs) + 1)
            res.timing["setup"] = time.perf_counter() - t
            t = time.perf_counter()
            done = 0
            for world, pf, what in passes:
                sc.world = world
                bk.use_pass_direct = "DIRECT" in pf
                bk.use_pass_indirect = "INDIRECT" in pf
                self._bake_call(sc, [probe], "IMAGE_TEXTURES", pf)
                px = self._pixels(probe_img)
                ref += px[2:6, 2:6, :3].reshape(-1, 3).mean(axis=0)
                done += 1
                for kind, idx, objs in jobs:
                    yield self._tick(0.05 + 0.8 * done / n_calls,
                                     f"Baking the {what}: {done} of {n_calls}")
                    if kind == "vert":
                        self._bake_call(sc, objs, "VERTEX_COLORS", pf)
                        for o, rng in vert_jobs[idx][1]:
                            c = self._corner_colours(o)
                            for i, (lo, hi) in rng.items():
                                vert_acc[i] += c[lo:hi]
                    else:
                        self._bake_call(sc, objs, "IMAGE_TEXTURES", pf)
                        img = atlases[idx] if kind == "atlas" else own_objs[idx][2]
                        px = self._pixels(img)
                        tgt, msk = (acc[idx], mask[idx]) if kind == "atlas" else (own_acc[idx], own_mask[idx])
                        tgt += px[..., :3]
                        msk |= px[..., 3] > 0.5
                    done += 1
            res.reference = tuple(float(v) for v in ref)
            res.reference_sky = res.reference
            if self._has_sky_sun():                    # the sky alone on the probe: the page's balance of sun and sky
                sc.world = self._world_copy(False)
                bk.use_pass_direct = bk.use_pass_indirect = True
                self._bake_call(sc, [probe], "IMAGE_TEXTURES", {"DIRECT", "INDIRECT"})
                sky = self._pixels(probe_img)[2:6, 2:6, :3].reshape(-1, 3).mean(axis=0)
                res.reference_sky = tuple(float(v) for v in sky)
                lum = np.array([0.2126, 0.7152, 0.0722])
                if self.light == "ALL":
                    res.sun_ratio = max(0.0, float(ref @ lum) / max(float(sky @ lum), 1e-9) - 1.0)
            res.timing["bake"] = time.perf_counter() - t
            res.timing["calls"] = n_calls
            t = time.perf_counter()
            yield self._tick(0.86, "Cleaning up the baked light")
            for k, (a, m) in enumerate(list(zip(acc, mask)) + list(zip(own_acc, own_mask))):
                a[...] = self._clean(a, m)
                yield self._tick(0.86 + 0.12 * (k + 1) / max(1, len(acc) + len(own_acc)), "Cleaning up the baked light")
            res.atlases = acc
            res.timing["clean"] = time.perf_counter() - t
            for r in p["maps"]:
                it = Item(self.id_of(r["ob"]), r["ob"].name, "MAP", texels_per_m=r["tpm"], pixels=acc[r["atlas"]],
                          uv=r["uv"], atlas=r["atlas"])
                it.loop_uv = self._loop_uv(r["ob"].data, r["md"], r["uv"])
                res.items[it.id] = it
            for (r, _o, _img), a in zip(own_objs, own_acc):
                res.items[self.id_of(r["ob"])] = Item(self.id_of(r["ob"]), r["ob"].name, "MAP",
                                                      texels_per_m=r["tpm"], pixels=a)
            for r, c in zip(p["verts"], vert_acc):
                md = r["md"]
                n = len(md.points)
                vals = np.zeros((n, 3), np.float64)
                cnt = np.zeros(n, np.float64)
                np.add.at(vals, md.tris.ravel(), c)
                np.add.at(cnt, md.tris.ravel(), 1.0)
                vals /= np.maximum(cnt, 1.0)[:, None]
                res.items[self.id_of(r["ob"])] = Item(self.id_of(r["ob"]), r["ob"].name, "VERTEX",
                                                      values=vals.astype(np.float32), corners=c)
            res.texels = p["texels"]
            res.vertices = p["vertices"]
            res.seconds = time.perf_counter() - t0
            yield 1.0
        finally:
            self.close()

    def run(self) -> Result:
        for _ in self.steps():
            pass
        return self.result

    def close(self) -> None:
        if self._baker is not None:
            self._baker.close()
            self._baker = None

    # -- helpers
    def _probe(self, img, cache):
        p = self.plan()
        from . import build
        mn, mx = build.world_bounds([r["ob"] for r in p["rows"]])
        size = max(float(max(mx[i] - mn[i] for i in range(3))), 1.0)
        far = float(mx[0]) + 10.0 * size + 1000.0
        me = bpy.data.meshes.new(NAME)
        self._baker.ids.append(me)
        me.from_pydata([(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0)], [], [(0, 1, 2, 3)])
        uv = me.uv_layers.new(name=UV_NAME)
        uv.data.foreach_set("uv", [0, 0, 1, 0, 1, 1, 0, 1])
        me.materials.append(self._material_with_image(None, img, cache))
        o = bpy.data.objects.new(NAME, me)
        o.location = (far, float((mn[1] + mx[1]) / 2), float(mn[2]))
        self._baker.scene.collection.objects.link(o)
        self._baker.ids.append(o)
        return o

    def _bake_call(self, sc, objs, target, pf) -> None:
        vl = sc.view_layers[0]
        for o in sc.objects:
            o.select_set(False, view_layer=vl)
        for o in objs:
            o.select_set(True, view_layer=vl)
        vl.objects.active = objs[0]
        sc.render.bake.target = target
        with bpy.context.temp_override(scene=sc, view_layer=vl, active_object=objs[0], object=objs[0],
                                       selected_objects=objs, selected_editable_objects=objs):
            res = bpy.ops.object.bake(type="DIFFUSE", pass_filter=set(pf), margin=self.padding, margin_type="EXTEND",
                                      use_clear=True, target=target)
        if res != {"FINISHED"}:
            raise RuntimeError(f"baking the light failed ({res})")

    @staticmethod
    def _pixels(img) -> np.ndarray:
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        return px.reshape(h, w, 4)

    @staticmethod
    def _corner_colours(o) -> np.ndarray:
        ca = o.data.color_attributes[UV_NAME]
        c = np.empty(len(o.data.loops) * 4, np.float32)
        ca.data.foreach_get("color", c)
        return c.reshape(-1, 4)[:, :3]            # loops of the triangle copy = loop-triangle corners

    @staticmethod
    def _loop_uv(me, md: _MeshData, uv: np.ndarray):
        """The light UVs per loop of the original mesh (None when one loop would need two)."""
        out = np.full((len(me.loops), 2), np.nan, np.float32)
        out[md.loops] = uv
        again = np.zeros((len(me.loops), 2), np.float32)
        again[md.loops] = uv
        if np.isnan(out).any() or np.abs(out - again).max() > 1e-6:
            return None
        return out

    def _clean(self, acc: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if not mask.any():
            return acc
        out = acc
        if self.denoise:
            try:
                out = denoise(self._baker.scene, acc)
            except Exception as exc:  # noqa: BLE001 - a missing denoiser must not stop the bake
                print("Fresing Render: light denoise fallback:", exc)
                out = lm.smooth(acc, mask, 2)
        out = np.where(mask[..., None], out, acc)
        return lm.dilate(out, mask, self.padding).astype(np.float32)


def denoise(src_scene, pixels: np.ndarray) -> np.ndarray:
    """Blender's own denoiser (OpenImageDenoise in the compositor) on a (h, w, 3) float picture, in a scene of its
    own (a copy of a Cycles scene, one sample of nothing rendered under the compositor)."""
    h, w = pixels.shape[:2]
    had_result = "Render Result" in bpy.data.images
    sc = src_scene.copy()
    sc.name = NAME + " denoise"
    made = []
    try:
        for c in list(sc.collection.children):
            sc.collection.children.unlink(c)
        for o in list(sc.collection.objects):
            sc.collection.objects.unlink(o)
        sc.world = None
        sc.cycles.samples = 1
        sc.cycles.device = "CPU"
        sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = w, h, 100
        sc.render.use_compositing = True
        sc.render.film_transparent = False
        sc.view_settings.view_transform = "Standard"
        sc.render.image_settings.file_format = "OPEN_EXR"
        cam = bpy.data.objects.new(NAME, bpy.data.cameras.new(NAME))
        made += [cam, cam.data]
        sc.collection.objects.link(cam)
        sc.camera = cam
        img = bpy.data.images.new(NAME + " in", w, h, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        made.append(img)
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :3] = pixels
        img.pixels.foreach_set(rgba.ravel())
        ng = bpy.data.node_groups.new(NAME, "CompositorNodeTree")
        made.append(ng)
        sc.compositing_node_group = ng
        n_in = ng.nodes.new("CompositorNodeImage")
        n_in.image = img
        dn = ng.nodes.new("CompositorNodeDenoise")
        if "HDR" in dn.inputs:
            dn.inputs["HDR"].default_value = True
        out = ng.nodes.new("NodeGroupOutput")
        ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
        ng.links.new(n_in.outputs["Image"], dn.inputs["Image"])
        ng.links.new(dn.outputs["Image"], out.inputs[0])
        bpy.ops.render.render(scene=sc.name)
        fd, path = tempfile.mkstemp(suffix=".exr")
        os.close(fd)
        try:
            bpy.data.images["Render Result"].save_render(path, scene=sc)
            res = bpy.data.images.load(path)
            made.append(res)
            px = np.empty(w * h * 4, np.float32)
            res.pixels.foreach_get(px)
            return px.reshape(h, w, 4)[..., :3].copy()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    finally:
        for idb in reversed(made):
            try:
                if isinstance(idb, bpy.types.Object):
                    bpy.data.objects.remove(idb)
                elif isinstance(idb, bpy.types.Camera):
                    bpy.data.cameras.remove(idb)
                elif isinstance(idb, bpy.types.Image):
                    bpy.data.images.remove(idb)
                elif isinstance(idb, bpy.types.NodeTree):
                    bpy.data.node_groups.remove(idb)
            except ReferenceError:
                pass
        bpy.data.scenes.remove(sc)
        if not had_result and "Render Result" in bpy.data.images:
            bpy.data.images.remove(bpy.data.images["Render Result"])


def see_through(ob) -> bool:
    """Every material of ``ob`` lets light through (glass, a clear cover): such a part is not baked – the page keeps
    its live light – but it still lets the light through to the parts behind it."""
    mats = [s.material for s in ob.material_slots if s.material is not None]
    if not mats:
        return False
    for mat in mats:
        nt = mat.node_tree
        pr = [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"] if nt is not None else []
        if not pr:
            return False
        n = pr[0]
        tw = n.inputs.get("Transmission Weight")
        al = n.inputs.get("Alpha")
        clear = (tw is not None and not tw.is_linked and tw.default_value > 0.5) or \
                (al is not None and not al.is_linked and al.default_value < 0.5)
        if not clear:
            return False
    return True


def quick_estimate(objects, light, quality="NORMAL", texels_per_m=None, device="CPU") -> dict:
    """A fast estimate for the panel (no unwrap): {"seconds", "bytes", "texels_per_m", "gpu"}; areas from the
    meshes (each unique mesh read once)."""
    light = choice_id(light)
    if light == "LIVE":
        return {"seconds": 0.0, "bytes": 0, "texels_per_m": 0.0, "gpu": False}
    q = lm.QUALITY.get(quality, lm.QUALITY["NORMAL"])
    areas: dict = {}
    total = 0.0
    for ob in objects:
        if ob.type != "MESH" or ob.data is None:
            continue
        key = ob.data.name_full
        if key not in areas:
            areas[key] = sum(p.area for p in ob.data.polygons)
        s = _scale(ob.matrix_world)
        total += areas[key] * s * s
    tpm = float(texels_per_m) if texels_per_m else lm.texels_per_m(max(total, 1e-9), q["budget"])
    tpm = float(np.clip(tpm, lm.MIN_TPM, lm.MAX_TPM))
    texels = total * tpm * tpm / 0.6                      # charts fill about 60 % of an atlas
    atlases = max(1, math.ceil(texels / (lm.ATLAS * lm.ATLAS)))
    passes = 2 if light == "SOFT" else 1
    est = lm.estimate(int(atlases * lm.ATLAS * lm.ATLAS), 0, q["samples"], passes, RATE_CPU, GPU_FACTOR,
                      BYTES_PER_TEXEL)
    gpu = device == "GPU"
    sec = (est["seconds_gpu"] if gpu else est["seconds_cpu"]) + passes * (atlases + 1) * CALL_SECONDS
    return {"seconds": sec, "bytes": est["bytes"], "texels_per_m": tpm, "gpu": gpu}


def duration(seconds: float) -> str:
    """'about 40 s', 'about 3 min', 'about 1.5 h'."""
    if seconds < 90:
        return f"about {max(5, round(seconds / 5) * 5):.0f} s"
    if seconds < 5400:
        return f"about {seconds / 60:.0f} min"
    return f"about {seconds / 3600:.1f} h"


def bake(objects, light="SOFT", **kw) -> Result:
    """Bake the light of ``objects`` at once (see ``Bake`` and the module text); "LIVE" returns an empty result."""
    return Bake(objects, light, **kw).run()
