"""Bake a House Planner house and write the bake package (task 0114; FORMAT.md sections 8 and 10).

Per moment of the recipe:

* 0109's weather for it (``house_import.moment_state``): clouds, haze, the season's wet and snow, and House Planner's
  sun – handed to 0107 as ``sky={"sun_height", "sun_direction"}`` (the sky texture's ``sun_rotation`` in degrees,
  ``house_scene.sun_rotation_deg``) and set on 0109's channels the same way, so both agree;
* the moment's lamps (their light objects, children of the fittings) – and at night 0109's moonlight;
* 0107's ``lightbake.bake`` once for the surfaces: ``uv="UV1"`` with ``sizes`` = each surface's ``uv1_px`` (a
  surface without a UV set 1 comes back per vertex, which is what the ``VERTEX`` surfaces want); ``NO`` surfaces and
  everything else shown only take part (occluders); bare trees leave their leaves out;
* each storey of ``open_storeys`` again, everything of a higher level left out, that storey's surfaces only;
* the season's snow layers (``core/house_snow.py``: new meshes by 0109's rule), per vertex, the house as occluders.

``SOFT`` at night is baked as ``ALL``: without a sun both are the same light (FORMAT 7.5), and 0109's moonlight (a
Sun lamp) then counts as light, not as a sun. ``sun_light`` (SOFT by day) comes from a tiny extra bake with the sun:
its open probe minus the sky alone.

Photos and turntable videos of the recipe are rendered with Cycles at their moment, with 0109's falling rain, snow and
wind and its wet and snow material layer. Everything the bake changes in the project (weather, camera, render
settings, what is shown) is put back at the end – also after Cancel or an error.
"""

from __future__ import annotations

import math
import os
import tempfile
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

from ..core import house_scene as hs
from ..core import house_snow
from ..core import weather as wcore
from ..core.web3d import Cancelled
from . import house_import as hi
from . import lightbake

NAME = "FR house bake"
PHOTO_SAMPLES = {"DRAFT": 32, "NORMAL": 128, "FINE": 512}
PRESETS = ("DRAFT", "NORMAL", "FINE")


def default_path(scene) -> str:
    """``<house title>.hpbake`` next to the project (a project not saved: next to the house's files)."""
    h = hi.settings(scene)
    base = os.path.dirname(bpy.data.filepath) if bpy.data.filepath else os.path.dirname(h.folder or tempfile.gettempdir())
    return os.path.join(base, hi.safe_name(h.title) + ".hpbake")


def app_version() -> str:
    from .. import __version__
    return str(__version__)


def to_blender(v) -> Vector:
    return Vector((float(v[0]), -float(v[2]), float(v[1])))


def camera_matrix(position_g, target_g) -> Matrix:
    """A camera at ``position`` looking at ``target`` (glTF points), up = world up."""
    p, t = to_blender(position_g), to_blender(target_g)
    q = (t - p).to_track_quat("-Z", "Y")
    return Matrix.Translation(p) @ q.to_matrix().to_4x4()


class HouseBake:
    """One bake of the imported house. ``steps()`` yields 0 … 1 (``text`` says what it does); ``result`` at the end
    ({"path", "seconds", "problems", "moments", "per_moment"}). ``run()`` does it all at once.

    ``moments``: ids to bake (None = every moment of the recipe); ``photos`` / ``videos``: render them too;
    ``samples``: overrides the recipe's (tests, the PC check); ``path``: where the package goes."""

    def __init__(self, scene, path: str | None = None, *, moments=None, photos=True, videos=True, samples=None,
                 photo_samples=None, device="AUTO"):
        self.scene = scene
        self.path = path or default_path(scene)
        self.house = hi.house(scene)
        rec = self.house.recipe
        self.moment_ids = [m.id for m in rec.moments if moments is None or m.id in set(moments)]
        self.photos = photos
        self.videos = videos
        self.samples = int(samples or rec.samples)
        self.quality = rec.preset if rec.preset in PRESETS else "NORMAL"
        self.photo_samples = int(photo_samples or PHOTO_SAMPLES[self.quality])
        self.device = device
        self.text = "Starting"
        self.result: dict = {}
        self.problems: list = []
        self._temp: list = []               # objects / meshes / cameras made here (removed at the end)
        self._saved = None

    # ------------------------------------------------------------------ the objects
    def _objects(self):
        objs = hi.by_id(self.scene)
        missing = [sid for sid, sf in self.house.surfaces.items() if sf.mesh is not None and sid not in objs]
        if missing:
            self.problems.append(f"{len(missing)} surfaces of the export are not in the project (e.g. '{missing[0]}')"
                                 " – they have no result; import the house again")
        return objs

    def _level(self, storey) -> int | None:
        return hs.storey_level(self.house, storey) if storey is not None else None

    # ------------------------------------------------------------------ saving and putting back
    def _save(self) -> None:
        from . import weather
        sc = self.scene
        r = sc.render
        self._saved = {
            "state": weather.state(sc), "enabled": sc.fresing.weather.enabled, "background": sc.fresing.background,
            "hide": {ob.name: (ob.hide_render, ob.hide_viewport) for ob in hi.parts(sc) + hi.lights(sc)},
            "shadow": {ob.name: ob.visible_shadow for ob in hi.parts(sc)},
            "camera": sc.camera, "res": (r.resolution_x, r.resolution_y, r.resolution_percentage),
            "filepath": r.filepath, "format": (r.image_settings.file_format, r.image_settings.color_mode,
                                               r.image_settings.color_depth),
            "frames": (sc.frame_start, sc.frame_end, sc.frame_current, r.fps, r.fps_base),
            "samples": sc.cycles.samples if hasattr(sc, "cycles") else None,
            "denoise": sc.cycles.use_denoising if hasattr(sc, "cycles") else None,
            "transparent": r.film_transparent, "engine": r.engine, "moment": hi.settings(sc).moment,
        }

    def _restore(self) -> None:
        sv = self._saved
        if sv is None:
            return
        self._saved = None
        sc = self.scene
        if self._temp:
            datas = [ob.data for ob in self._temp if isinstance(ob, bpy.types.Object) and ob.data is not None]
            obs = [ob for ob in self._temp if isinstance(ob, bpy.types.Object)]
            try:
                bpy.data.batch_remove(obs)
                left = [d for d in datas if d.users == 0]
                if left:
                    bpy.data.batch_remove(left)
            except ReferenceError:
                pass
            self._temp = []
        r = sc.render
        r.resolution_x, r.resolution_y, r.resolution_percentage = sv["res"]
        r.filepath = sv["filepath"]
        r.image_settings.file_format, r.image_settings.color_mode, r.image_settings.color_depth = sv["format"]
        sc.frame_start, sc.frame_end, cur, r.fps, r.fps_base = sv["frames"]
        sc.frame_set(cur)
        if sv["samples"] is not None:
            sc.cycles.samples = sv["samples"]
            sc.cycles.use_denoising = sv["denoise"]
        r.film_transparent = sv["transparent"]
        if r.engine != sv["engine"]:
            r.engine = sv["engine"]
        sc.camera = sv["camera"]
        for name, v in sv["shadow"].items():
            ob = bpy.data.objects.get(name)
            if ob is not None:
                ob.visible_shadow = v
        for name, (hr, hv) in sv["hide"].items():
            ob = bpy.data.objects.get(name)
            if ob is not None:
                ob.hide_render, ob.hide_viewport = hr, hv
        from . import weather, world
        s = sc.fresing
        live = s.live_update
        s.live_update = False
        try:
            weather.put_state(sc, sv["state"])
            s.weather.enabled = sv["enabled"]
            s.background = sv["background"]
        finally:
            s.live_update = live
        if sv["enabled"]:
            weather.write_channels(sc, weather.channels(sc))
        world.apply(sc, s)
        hi.settings(sc).moment = sv["moment"]

    # ------------------------------------------------------------------ one bake call
    def _bake(self, objects, light, *, uv, occluders, lamps, sky, ids, sizes=None, f0=0.0, f1=1.0, what=""):
        b = lightbake.Bake(objects, light, sky=sky, occluders=occluders, lamps=lamps, ids=ids, uv=uv,
                           quality=self.quality, samples=self.samples, device=self.device, scene=self.scene,
                           sizes=sizes)
        for f in b.steps():
            self.text = f"{what}: {b.text}"
            yield f0 + (f1 - f0) * float(f)
        return b.result

    def _sky(self, moment) -> dict:
        el, az = hs.sun_angles(moment.direction)
        return {"sun_height": el, "sun_direction": hs.sun_rotation_deg(az)}

    def _set_moment(self, moment, falling=None) -> tuple:
        st, off = hi.moment_state(self.house, moment, falling)
        if off > 0.5:
            self.problems.append(f"Moment '{moment.id}': Fresing Render's sky could not put its sun closer than "
                                 f"{off:.1f}° to House Planner's")
        hi.set_weather(self.scene, st)
        ch = wcore.derive(st)
        el, az = hs.sun_angles(moment.direction)
        got = hi._angle(el, az, float(self.scene.get(wcore.prop("sun_el"), ch["sun_el"])),
                        float(self.scene.get(wcore.prop("sun_az"), ch["sun_az"])))
        if got > 0.5 and off <= 0.5:
            self.problems.append(f"Moment '{moment.id}': the sky's sun is {got:.1f}° from House Planner's")
        return st, ch

    def _moon(self, ch) -> list:
        if ch.get("moon", 0.0) <= 0.0:
            return []
        return [ob for ob in self.scene.objects if ob.type == "LIGHT" and ob.get("fr_weather") == "moon"]

    # ------------------------------------------------------------------ one object per light-map page
    def _page_objects(self, objects, variant: str, ids: dict) -> list:
        """The MAP surfaces ``objects`` joined into one object per page of the package's layout (``BakeWriter``'s
        rects for ``variant``: "" = the whole house, a storey id = its open results): world coordinates, the
        surfaces' own materials and texture UVs, and as UV set 1 each surface's UV set 1 moved into its rect on the
        page. Returns [(object, (page width, page height), [(id, x, y, w, h)])]. A surface whose UV set 1 is
        missing is left out (a problems line); one whose map size does not fit its UV set 1 gets 0107's line."""
        surf = self.house.surfaces
        rects, pages = self.writer.rects, self.writer.pages
        by_page: dict = {}
        for ob in objects:
            sid = ids[ob]
            hit = rects.get((variant, sid))
            if hit is None:
                continue                          # (too big for a page: the writer said so)
            if len(ob.data.uv_layers) < 2:
                self.problems.append(f"{sid}: no UV set 1 in the project – it has no baked light")
                continue
            md = lightbake._read_mesh(ob.data)
            why = lightbake.size_problem(md, list(md.uvs)[1], surf[sid].uv1_px, ob.matrix_world)
            if why:
                self.problems.append(f"{sid}: {why}")
            by_page.setdefault(hit[0], []).append((ob, md, hit[1], hit[2]))
        out = []
        for k, rows in sorted(by_page.items()):
            pw, ph = pages[k]
            pts, tris, nrm, uv0, uvp, mi, mats, cuts = [], [], [], [], [], [], [], []
            mat_ix: dict = {}
            off = 0
            for ob, md, x, y in rows:
                sid = ids[ob]
                w, h = surf[sid].uv1_px
                mw = np.array(ob.matrix_world, np.float64)
                m3 = mw[:3, :3]
                pts.append(md.points @ m3.T + mw[:3, 3])
                tris.append(md.tris + off)
                nm = np.linalg.inv(m3).T
                n = md.normals.astype(np.float64) @ nm.T
                nrm.append(n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None])
                names = list(md.uvs)
                uv0.append(md.uvs[md.active_render or names[0]])
                u = md.uvs[names[1]].astype(np.float64)             # Blender: v = 1 - glTF v
                uvp.append(np.stack([(x + u[:, 0] * w) / pw, (ph - y - h + u[:, 1] * h) / ph], axis=1))
                local = []
                for sl in ob.material_slots or [None]:
                    mat = sl.material if sl is not None else None
                    key = mat.name_full if mat is not None else ""
                    if key not in mat_ix:
                        mat_ix[key] = len(mats)
                        mats.append(mat)
                    local.append(mat_ix[key])
                local = np.asarray(local, np.int32)
                mi.append(local[np.clip(md.mat, 0, len(local) - 1)])
                cuts.append((sid, x, y, w, h))
                off += len(md.points)
            P, T = np.concatenate(pts), np.concatenate(tris).astype(np.int32)
            me = bpy.data.meshes.new(NAME)
            me.vertices.add(len(P))
            me.vertices.foreach_set("co", P.astype(np.float32).ravel())
            me.loops.add(T.size)
            me.loops.foreach_set("vertex_index", T.ravel())
            me.polygons.add(len(T))
            me.polygons.foreach_set("loop_start", np.arange(0, T.size, 3, dtype=np.int32))
            me.polygons.foreach_set("material_index", np.concatenate(mi))
            me.update(calc_edges=True)
            a = me.attributes.new("custom_normal", "FLOAT_VECTOR", "CORNER")
            a.data.foreach_set("vector", np.concatenate(nrm).astype(np.float32).ravel())
            for name, data in (("UVMap", uv0), ("fr_page", uvp)):
                layer = me.uv_layers.new(name=name)
                layer.data.foreach_set("uv", np.concatenate(data).astype(np.float32).ravel())
            me.uv_layers["UVMap"].active_render = True
            for mat in mats:
                me.materials.append(mat)
            po = bpy.data.objects.new(NAME, me)
            self.scene.collection.objects.link(po)
            po.hide_render = po.hide_viewport = True
            self._temp.append(po)
            out.append((po, (pw, ph), cuts))
        return out

    def _drop(self, objs) -> None:
        """Remove temporary objects now (and their meshes)."""
        objs = [o for o in objs if o in self._temp]
        if not objs:
            return
        for o in objs:
            self._temp.remove(o)
        datas = [o.data for o in objs]
        bpy.data.batch_remove(objs)
        left = [d for d in datas if d.users == 0]
        if left:
            bpy.data.batch_remove(left)

    # ------------------------------------------------------------------ snow
    def _snow_objects(self, season, objects: bool = True) -> list:
        """The season's snow layer meshes (core/house_snow.py), written to the package and made as temporary
        objects to bake their light per vertex. Returns [(layer, object)]."""
        sources, blockers = house_snow.sources_from_glb(self.house.glb, season.foliage)
        layers = house_snow.build_layers(sources, float(season.snow_cover), blockers)
        if not layers:
            return []
        self.writer.add_snow(season.id, house_snow.layers_glb(layers), sources=sources)
        out = []
        if not objects:                        # LIVE: the layers go into the package, nothing is baked on them
            return out
        for ly in layers:
            me = bpy.data.meshes.new(NAME)
            pos = np.asarray(ly.positions, np.float64)
            pb = np.stack([pos[:, 0], -pos[:, 2], pos[:, 1]], axis=1).astype(np.float32)
            tris = np.asarray(ly.indices, np.int32).reshape(-1, 3)
            me.vertices.add(len(pb))
            me.vertices.foreach_set("co", pb.ravel())
            me.loops.add(tris.size)
            me.loops.foreach_set("vertex_index", tris.ravel())
            me.polygons.add(len(tris))
            me.polygons.foreach_set("loop_start", np.arange(0, tris.size, 3, dtype=np.int32))
            me.update(calc_edges=True)
            ob = bpy.data.objects.new(NAME, me)
            ob["fr_house_snow"] = ly.id
            self.scene.collection.objects.link(ob)
            ob.hide_render = ob.hide_viewport = True
            self._temp.append(ob)
            out.append((ly, ob))
        return out

    # ------------------------------------------------------------------ the whole bake
    def steps(self):
        t_all = time.perf_counter()
        sc = self.scene
        rec = self.house.recipe
        self.writer = hs.BakeWriter(self.house, light=rec.light, samples=self.samples, denoised=True,
                                    app_version=app_version())
        objs = self._objects()
        surf = self.house.surfaces
        moments = [m for m in rec.moments if m.id in self.moment_ids]
        photos = [p for p in rec.photos if self.photos and p.get("moment") in self.moment_ids]
        videos = [v for v in rec.videos if self.videos and v.get("moment") in self.moment_ids]
        n_work = max(1, len(moments) * 10 + len(photos) * 3 + len(videos) * 8)
        done = [0.0]

        def span(units):
            a = done[0] / n_work
            done[0] += units
            return a, done[0] / n_work

        self._save()
        per_moment = {}
        try:
            yield 0.0
            snow: dict = {}
            for season in rec.seasons:           # (also LIVE: it bakes "only snow, photos, videos", FORMAT 7.1)
                if season.snow_cover > 0 and any(m.season == season.id for m in moments):
                    self.text = f"Snow layers for {season.label or season.id}"
                    snow[season.id] = self._snow_objects(season, objects=rec.light != "LIVE")
                    yield done[0] / n_work
            for m in moments if rec.light != "LIVE" else []:
                t0 = time.perf_counter()
                season = hi.season_of(self.house, m)
                hidden = hi.hidden_in(self.house, season)
                st, ch = self._set_moment(m)
                el, _az = hs.sun_angles(m.direction)
                night = el < 0.0
                light = "ALL" if rec.light == "SOFT" and night else rec.light
                lamps = hi.lamps_of(sc, m) + (self._moon(ch) if night else [])
                sky = self._sky(m)
                shown = {sid: ob for sid, ob in objs.items() if sid not in hidden}
                ids = {ob: sid for sid, ob in shown.items()}
                maps, opens = {}, {}
                # a lamp's light sits inside its fitting: the fitting must not shadow its own light (FORMAT 4.4)
                fittings = {sid for sid, ob in shown.items() if any(c.type == "LIGHT" for c in ob.children)}
                fit_obs = {shown[sid] for sid in fittings}

                def targets(pick):
                    t, o, extra = [], [], []
                    for sid, ob in pick.items():
                        if sid in fittings:               # baked on their own (below): they never block a lamp
                            continue
                        b = surf[sid].bake
                        if b == "MAP":
                            t.append(ob)
                        elif b == "VERTEX":
                            (extra if len(ob.data.uv_layers) >= 2 else t).append(ob)
                        else:
                            o.append(ob)
                    return t, o, extra

                def collect(res, into):
                    for sid, it in res.items.items():
                        if sid not in surf:
                            continue
                        want = surf[sid].bake
                        if it.kind == "MAP" and want == "MAP":
                            into[sid] = it.pixels
                        elif it.kind == "VERTEX" and want == "VERTEX":
                            into[sid] = it.values
                        elif want == "MAP":
                            self.problems.append(f"'{sid}': no light map could be baked (no UV set 1) – it has no "
                                                 "baked light")
                    for p in res.problems:
                        if "no 2nd UV layer" in p and any(surf.get(k) is not None and surf[k].bake == "VERTEX"
                                                          and p.startswith(k) for k in surf):
                            continue
                        if p not in self.problems:
                            self.problems.append(p)

                def call(pick, others, into, what, f0, f1, variant=""):
                    t, o, extra = targets(pick)
                    occl = [ob for ob in others if ob not in fit_obs] + o
                    fits = [ob for sid, ob in pick.items() if sid in fittings and surf[sid].bake == "VERTEX"]
                    flat = [ob for ob in t if surf[ids[ob]].bake == "MAP"]
                    vert = [ob for ob in t if surf[ids[ob]].bake != "MAP"]
                    # every page's MAP surfaces as ONE object (0107 bakes each UV1 object in a call of its own:
                    # 100 calls were 65 s of a 95 s moment on the sample); cut back out by their rects
                    pages = self._page_objects(flat, variant, ids)
                    sizes = {po: (pw, ph) for po, (pw, ph), _cuts in pages}
                    pid = {po: f"fr-page-{k}" for k, (po, _size, _cuts) in enumerate(pages)}
                    res = None
                    mid = f0 + (f1 - f0) * (0.85 if extra or fits else 1.0)
                    try:
                        if pages or vert:
                            res = yield from self._bake([po for po, _s, _c in pages] + vert, light, uv="UV1",
                                                        sizes=sizes, occluders=occl + extra, lamps=lamps, sky=sky,
                                                        ids={**ids, **pid}, f0=f0, f1=mid, what=what)
                            for po, (pw, ph), cuts in pages:
                                it = res.items.get(pid[po])
                                if it is None or it.pixels is None:
                                    continue
                                for sid, x, y, w, h in cuts:      # PNG rect (top-down) -> Blender rows (bottom-up)
                                    into[sid] = np.array(it.pixels[ph - y - h:ph - y, x:x + w], np.float32)
                            collect(res, into)
                        if extra:
                            r2 = yield from self._bake(extra, light, uv="VERTEX", occluders=occl + t, lamps=lamps,
                                                       sky=sky, ids=ids, f0=mid, f1=f1, what=what)
                            collect(r2, into)
                            res = res or r2
                        if fits:                          # a lamp's fitting: light per vertex, the rest as occluders
                            r3 = yield from self._bake(fits, light, uv="VERTEX", occluders=occl + t + extra,
                                                       lamps=lamps, sky=sky, ids=ids, f0=mid, f1=f1, what=what)
                            collect(r3, into)
                            res = res or r3
                    finally:
                        self._drop([po for po, _s, _c in pages])
                    return res

                label = m.label or m.id
                a, b = span(5)
                main = yield from call(shown, [], maps, f"{label}: the house", a, b)
                for storey in rec.open_storeys:
                    lv = self._level(storey)
                    if lv is None:                    # (the reader refuses this; never a crash here)
                        self.problems.append(f"Open storey '{storey}' is not a storey of the house – skipped")
                        continue
                    keep = {sid: ob for sid, ob in shown.items()
                            if surf[sid].storey is None or self._level(surf[sid].storey) is None
                            or self._level(surf[sid].storey) <= lv}
                    mine = {sid: ob for sid, ob in keep.items() if surf[sid].storey == storey}
                    rest = [ob for sid, ob in keep.items() if sid not in mine]
                    opens[storey] = {}
                    a, b = span(3 / max(1, len(rec.open_storeys)))
                    yield from call(mine, rest, opens[storey], f"{label}: {storey} open", a, b, storey)
                layers = snow.get(m.season, [])
                a, b = span(1)
                if layers:
                    so = [ob for _ly, ob in layers]
                    res = yield from self._bake(so, light, uv="VERTEX", occluders=list(shown.values()), lamps=lamps,
                                                sky=sky, ids={ob: ly.id for ly, ob in layers}, f0=a, f1=b,
                                                what=f"{label}: snow")
                    for ly, _ob in layers:
                        it = res.items.get(ly.id)
                        if it is not None and it.values is not None:
                            maps[ly.id] = it.values
                a, b = span(1)
                sun_light = None
                if rec.light == "SOFT" and not night and main is not None and main.sun_separate:
                    sun_light = yield from self._sun_light(light, lamps, sky, a, b, label)
                reference = tuple(float(v) for v in (main.reference if main is not None else (0.0, 0.0, 0.0)))
                self.writer.add_moment(m.id, maps, opens, reference=reference,
                                       exposure=float(wcore.exposure_for(el, float(m.clouds))), sun_light=sun_light)
                per_moment[m.id] = time.perf_counter() - t0
                yield done[0] / n_work
            for p in photos:
                a, b = span(3)
                yield from self._photo(p, a, b)
            for v in videos:
                a, b = span(8)
                yield from self._video(v, a, b)
            self.text = "Writing the bake package"
            for x in self.problems:
                self.writer.problem(x)
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            self.writer.write(self.path)
            self.result = {"path": self.path, "seconds": time.perf_counter() - t_all,
                           "problems": list(self.writer.problems), "moments": len(per_moment),
                           "per_moment": per_moment}
            yield 1.0
        finally:
            self._restore()

    def _sun_light(self, light, lamps, sky, f0, f1, label):
        """The sun's direct light on a white matte surface facing it, in L: a tiny bake with the sun (``ALL``) –
        its open probe minus the sky alone (0107's ``reference`` - ``reference_sky``)."""
        me = bpy.data.meshes.new(NAME)
        me.from_pydata([(0, 0, 0), (0.1, 0, 0), (0, 0.1, 0)], [], [(0, 1, 2)])
        ob = bpy.data.objects.new(NAME, me)
        self.scene.collection.objects.link(ob)
        ob.hide_render = ob.hide_viewport = True
        self._temp.append(ob)
        b = lightbake.Bake([ob], "ALL", sky=sky, occluders=[], lamps=[], uv="VERTEX", quality=self.quality,
                           samples=64, device=self.device, scene=self.scene)    # (an 8 px probe: cheap)
        for f in b.steps():
            self.text = f"{label}: the sun's strength"
            yield f0 + (f1 - f0) * float(f)
        res = b.result
        sun = [max(0.0, float(a) - float(s)) for a, s in zip(res.reference, res.reference_sky)]
        # (the probe faces up: the sun's light on a surface facing it is that over sin(elevation))
        el = float(sky["sun_height"])
        k = 1.0 / max(math.sin(math.radians(max(el, 0.5))), 1e-3)
        return [v * k for v in sun]

    # ------------------------------------------------------------------ photos and videos
    def _camera(self, cam: dict):
        data = bpy.data.cameras.new(NAME)
        data.sensor_fit = "VERTICAL"
        data.angle_y = math.radians(float(cam.get("fov", 50.0)))
        data.clip_start = 0.05
        data.clip_end = 5000.0
        ob = bpy.data.objects.new(NAME, data)
        self.scene.collection.objects.link(ob)
        ob.matrix_world = camera_matrix(cam["position"], cam["target"])
        self._temp.append(ob)
        return ob

    def _show_moment(self, m, falling) -> None:
        st, _ch = self._set_moment(m, falling)
        on = set(hi.lamps_of(self.scene, m))
        for ob in hi.lights(self.scene):
            ob.hide_render = ob not in on
            if ob.parent is not None and ob.parent.type == "MESH":
                ob.parent.visible_shadow = False         # the fitting must not shadow its own light
        hide = hi.hidden_in(self.house, hi.season_of(self.house, m))
        for sid, ob in hi.by_id(self.scene).items():
            ob.hide_render = sid in hide
        from . import weather_look
        weather_look.add_objects(self.scene, hi.parts(self.scene))     # 0109's wet / snow look on the house

    def _render_setup(self, size, samples) -> None:
        sc = self.scene
        r = sc.render
        if r.engine != "CYCLES":
            r.engine = "CYCLES"
        r.resolution_x, r.resolution_y = int(size[0]), int(size[1])
        r.resolution_percentage = 100
        r.film_transparent = False
        sc.cycles.samples = int(samples)
        sc.cycles.use_denoising = True

    def _photo(self, p, f0, f1):
        rec = self.house.recipe
        m = hi.moment_of(self.house, p["moment"])
        cam = rec.cameras.get(p["camera"])
        if m is None or cam is None:
            self.problems.append(f"Photo '{p.get('id')}': its moment or camera is missing – skipped")
            return
        self.text = f"Photo '{p.get('label') or p['id']}'"
        yield f0
        cd = {"position": list(cam.position), "target": list(cam.target), "fov": float(cam.fov)}
        self._show_moment(m, p.get("falling"))
        sc = self.scene
        sc.camera = self._camera(cd)
        self._render_setup(p["size"], self.photo_samples)
        r = sc.render
        r.image_settings.file_format = "PNG"
        r.image_settings.color_mode = "RGB"
        r.image_settings.color_depth = "8"
        fd, out = tempfile.mkstemp(suffix=".png", prefix="fr_house_")
        os.close(fd)
        try:
            r.filepath = out
            bpy.ops.render.render(write_still=True, scene=sc.name)
            with open(out, "rb") as fh:
                data = fh.read()
        finally:
            if os.path.exists(out):
                os.remove(out)
        self.writer.add_photo(p["id"], data, "png", list(p["size"]), m.id, cd)
        yield f1

    def _video(self, v, f0, f1):
        rec = self.house.recipe
        m = hi.moment_of(self.house, v["moment"])
        cam = rec.cameras.get(v["camera"])
        if m is None or cam is None or v.get("kind", "turntable") != "turntable":
            self.problems.append(f"Video '{v.get('id')}': skipped (its moment, camera or kind is not known)")
            return
        self.text = f"Video '{v.get('label') or v['id']}'"
        yield f0
        cd = {"position": list(cam.position), "target": list(cam.target), "fov": float(cam.fov)}
        self._show_moment(m, v.get("falling"))
        sc = self.scene
        fps = int(v.get("fps", 25) or 25)
        frames = max(2, int(round(float(v.get("seconds", 8)) * fps)))
        # the turntable: the camera rides on an empty at the target that turns once round (linear, no ease)
        pivot = bpy.data.objects.new(NAME, None)
        sc.collection.objects.link(pivot)
        self._temp.append(pivot)
        pivot.location = to_blender(cam.target)
        camob = self._camera(cd)
        camob.parent = pivot
        camob.matrix_parent_inverse = Matrix.Translation(-to_blender(cam.target))
        pivot.rotation_euler = (0.0, 0.0, 0.0)
        pivot.keyframe_insert("rotation_euler", index=2, frame=1)
        pivot.rotation_euler = (0.0, 0.0, 2.0 * math.pi * frames / (frames + 1))
        pivot.keyframe_insert("rotation_euler", index=2, frame=frames)
        for fc in pivot.animation_data.action.fcurves if hasattr(pivot.animation_data.action, "fcurves") else []:
            for k in fc.keyframe_points:
                k.interpolation = "LINEAR"
        sc.camera = camob
        self._render_setup(v["size"], self.photo_samples)
        r = sc.render
        r.fps, r.fps_base = fps, 1.0
        sc.frame_start, sc.frame_end = 1, frames
        r.image_settings.file_format = "FFMPEG"
        r.ffmpeg.format = "MPEG4"
        r.ffmpeg.codec = "H264"
        r.ffmpeg.audio_codec = "NONE"
        d = tempfile.mkdtemp(prefix="fr_house_video_")
        r.filepath = os.path.join(d, "video")
        try:
            bpy.ops.render.render(animation=True, scene=sc.name)
            files = [f for f in os.listdir(d) if f.lower().endswith(".mp4")]
            if not files:
                raise RuntimeError("the video was not written")
            with open(os.path.join(d, files[0]), "rb") as fh:
                data = fh.read()
        finally:
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
            os.rmdir(d)
        self.writer.add_video(v["id"], data, "mp4", list(v["size"]), m.id, cd, float(v.get("seconds", 8)), fps)
        yield f1

    def run(self) -> dict:
        for _ in self.steps():
            pass
        return self.result


def bake(scene, path=None, **kw) -> dict:
    """Bake the house and write the package at once (see ``HouseBake``)."""
    return HouseBake(scene, path, **kw).run()


def estimate(scene) -> dict:
    """A quick estimate of the whole bake for the panel: {"seconds", "gpu", "moments"} (0107's ``quick_estimate``
    for the house's surfaces, times the moments and the open storeys)."""
    h = hi.house(scene)
    rec = h.recipe
    obs = [ob for sid, ob in hi.by_id(scene).items() if h.surfaces.get(sid) is not None
           and h.surfaces[sid].bake in ("MAP", "VERTEX")]
    gpu = scene.cycles.device == "GPU" if hasattr(scene, "cycles") else False
    if rec.light == "LIVE" or not obs:
        return {"seconds": 0.0, "gpu": gpu, "moments": len(rec.moments)}
    q = rec.preset if rec.preset in PRESETS else "NORMAL"
    one = lightbake.quick_estimate(obs, rec.light, q, rec.texels_per_m, "GPU" if gpu else "CPU")
    factor = len(rec.moments) * (1.0 + 0.5 * len(rec.open_storeys)) * (rec.samples / lightbake.lm.QUALITY[q]["samples"])
    return {"seconds": float(one["seconds"]) * factor, "gpu": gpu, "moments": len(rec.moments)}


__all__ = ["HouseBake", "bake", "default_path", "estimate", "Cancelled"]
