"""Coolant liquid on the machine (task 0346, study 0251 method a, solver ``core/liquid.py`` of task 0255).

The coolant of 0042 / 0257 pours onto the part: it fills the cut pockets and slots, spills onto the table, runs along
the T-slots and off the table's ends into the chip tray, and goes down the drain. Settings: 4 Motion > CNC machine >
Coolant, "Liquid on the machine" (``scene.fresing.coolant.liquid_on``, off by default), Detail, the EEVEE look.

* **Charts** (``gather``): two height fields, made by rays straight down.
  - "table" rides with the workpiece's mover (riding space = the world at the motion's first frame, as the chips):
    every riding part (table with its T-slots, clamps, bolts, motor) and the **cut block**. Its matrices per frame are
    the workpiece's places read by ``machining.sample`` (``fr_wp_m``).
  - "tray" stands still: the parts that do not move (chip tray, bed, drain, tank) round where the table goes. The part
    named ``COOLANT DRAIN``: the cells over its hole get the floor's height round it and an orifice.
  The cut block's top is read from the milling timeline (``mesh_at``) whenever cutting moves ran since the last read
  (every ``CUT_EVERY`` frames at most), cast again only where the tools went; every change is kept (``Beds``).
* **Inputs**: pours while flood flows (``fr_spans`` of the coolant), Flow x ``FULL_FLOW`` l/min, at the tool from one
  point per hose; the spinning tool (tip / axis from the bits' paths, radius / flute from the cut items, rpm from the
  coolant's ``fr_rpm``).
* **The bake** (``steps``: a generator of progress 0 … 1) runs in the window as a modal job with progress + Cancel
  (``ops_liquid.py``), in the background (render queue, tests, PC check) at once (``bake_now``). Cache: a
  ``core/liquid_cache.py`` file (8-bit steps of 0.05 mm where wet) + ``.beds.npz`` (the block's top over time), next
  to the project, keyed on a fingerprint of everything that goes in (``fingerprint``): an unchanged Build reads it.
* **Drawing** (``show``): one sheet per chart over the wet cells, drops as little spheres; a frame handler of its own
  draws from the cache only – the same frame gives the same liquid whatever was shown before. Material "FR coolant
  liquid": a Cycles output and an EEVEE output (the EEVEE look: Clear / Milky / Blended), light grey in Solid view.
"""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import tempfile
import threading
import time

import bpy
import numpy as np
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

from ..core import coolant as ccore
from ..core import liquid as core
from ..core import liquid_cache, liquid_pool
from . import build, coolant, machining

VERSION = 1                          # of the bake: a change here bakes old projects' liquid again
COLLECTION = "FR Coolant liquid"
OBJ_TABLE = "FR coolant liquid (table)"
OBJ_TRAY = "FR coolant liquid (tray)"
OBJ_DROPS = "FR coolant liquid drops"
MAT = "FR coolant liquid"
TAG = "fr_liquid"                    # on everything made here (value: its role)
CACHE_PROP = "fr_liquid_cache"       # on the scene: the bake's file (absolute: the render queue's copy finds it)
FULL_FLOW = 20.0                     # l/min at Flow 1 (a VMC's flood pump; Flow 0.7 = 14 l/min)
#: cell sizes (m): the table with the block, the tray
DETAIL = {"DRAFT": (4e-3, 10e-3), "NORMAL": (2e-3, 5e-3)}
SHOW = 0.1e-3                        # a cell shows liquid from this depth (the 0.04 mm film is the wet sheen)
LIFT = 0.05e-3                       # the sheet a hair over the surface (no flicker on the bed)
WAVE_DEPTH = 0.01                    # m: deep pools (T-slots, pockets) carry waves as if 10 mm deep (core: wave_depth)
CUT_EVERY = 4                        # frames: the cut block's top is read again at most this often while it is cut
TRAY_REACH = 0.15                    # m round where the table goes: the still parts there are the tray chart
TRAY_WORDS = ("TRAY", "DRAIN")       # still parts named so are taken whole into the tray chart (the drain may lie
                                     # beyond where the table goes)
HOSE_GAP = 2e-3                      # m: the poured liquid lands this far outside the tool
DRAIN_NAME = "COOLANT DRAIN"
DRAIN_DEEP = 0.015                   # m: a ray this far below the drain's top went into its hole
MM = 0.001
TICK = 0.15                          # s of bake work between two redraws (the modal job)

EEVEE_ITEMS = [("CLEAR", "Clear", "See-through with ray-traced refraction (the closest to the Cycles look; may be "
                                  "grainy at few samples)"),
               ("MILKY", "Milky", "Milky white without refraction: smooth at any sample count, the bed does not "
                                  "show through"),
               ("BLENDED", "Blended", "See-through drawn blended: smooth, the bed shows through faintly")]

_STATE: dict = {"guard": 0, "running": False, "cancel": False, "progress": 0.0, "scene": "", "pending": False}
_RT: dict = {}                        # scene name -> runtime: fingerprint memo, reader, beds, status, declined


def runtime(scene) -> dict:
    return _RT.setdefault(scene.name, {})


def forget() -> None:
    for rt in _RT.values():
        _close_reader(rt)
    _RT.clear()


def settings(scene):
    return scene.fresing.coolant


def rate(scene) -> float:
    """The flood's flow in l/min (0042's Flow slider: 0.1 … 1 -> 2 … 20 l/min)."""
    return float(settings(scene).flow) * FULL_FLOW


def asked(scene) -> bool:
    """The user ticked "Liquid on the machine" (and coolant is on)."""
    s = settings(scene)
    return bool(s.enabled and getattr(s, "liquid_on", False))


def problem(scene) -> str:
    """Why the liquid cannot be worked out now ('' when it can)."""
    if not asked(scene):
        return ""
    if not machining.is_active(scene):
        return "The liquid needs Milling (4 Motion > Milling): it fills what the bit cuts"
    r = coolant.root()
    if r is None or "fr_spans" not in r:
        return "Press Build & play: the liquid follows the coolant of the built program"
    if "fr_wp_m" not in machining.settings(scene):
        return "Waiting for the motion to be read"
    return ""


def wanted(scene) -> bool:
    return asked(scene) and not problem(scene)


def running() -> bool:
    return bool(_STATE["running"])


def progress() -> float:
    return float(_STATE["progress"])


# ---------------------------------------------------------------------------
# fingerprint and cache files
# ---------------------------------------------------------------------------

def _bytes(owner, key) -> bytes:
    if owner is None or key not in owner:
        return b""
    return np.array(owner[key], dtype=np.float64).round(6).tobytes()


def fingerprint(scene) -> str:
    """Everything the bake depends on, as one text: the milling motion, the block and the cutting tools, the coolant
    of the Build, the liquid settings, the frames, the parts it lies on and where they are."""
    s = settings(scene)
    m = machining.settings(scene)
    wp = machining.workpiece(scene)
    r = coolant.root()
    h = hashlib.sha1()
    h.update(repr((VERSION, m.path_sig, m.detail, bool(m.fast_map), s.liquid_detail, round(rate(scene), 4),
                   int(s.auto_count) if s.source == "AUTO" else len(s.nozzles), scene.render.fps,
                   round(scene.render.fps_base, 6), scene.frame_start, scene.frame_end)).encode())
    if wp is not None:
        h.update(repr(machining._stock_key(m, wp)).encode())
    for c in machining.cut_items(scene):
        h.update(repr(c.key()).encode())
    for k in ("fr_spans", "fr_rpm", "fr_tools", "fr_cut"):
        h.update(_bytes(r, k))
    h.update(_bytes(m, "fr_wp_m"))
    from . import chips
    cache = {}
    for ob in _parts(scene):                          # where each part sits on what moves it (not the frame's place)
        if ob is wp:                                  # (its mesh is the cut at the frame shown: the stock key counts)
            continue
        mv = chips.mover(ob, cache)
        rel = Matrix.Identity(4)
        p = ob
        while p is not None and p.name != mv:         # its own and its parents' places up to what moves it (exact,
            rel = p.matrix_parent_inverse @ p.matrix_basis @ rel if p.parent is not None else \
                p.matrix_basis @ rel                  # the same at every frame)
            p = p.parent
        h.update(ob.name.encode())
        h.update(np.array(rel, dtype=np.float64).round(5).tobytes())
        h.update(str(len(ob.data.vertices)).encode())
    return h.hexdigest()


def _memo_fingerprint(scene) -> str:
    """The fingerprint, worked out again only when one of the cheap signs changed (it walks the parts)."""
    rt = runtime(scene)
    s = settings(scene)
    m = machining.settings(scene)
    r = coolant.root()
    sign = (m.path_sig, s.liquid_detail, round(rate(scene), 4), s.source, int(s.auto_count), len(s.nozzles),
            scene.frame_start, scene.frame_end, scene.render.fps, len(m.get("fr_wp_m", ())),
            hashlib.sha1(_bytes(r, "fr_spans") + _bytes(r, "fr_rpm")).hexdigest())
    if rt.get("fp_sign") != sign or "fp" not in rt:
        rt["fp_sign"], rt["fp"] = sign, fingerprint(scene)
    return rt["fp"]


def cache_path(scene) -> str:
    """Where a new bake goes: a folder next to the project ("<project>_liquid"), or the temp folder if it is not
    saved yet."""
    name = bpy.path.clean_name(scene.name) + ".frliquid"
    if bpy.data.filepath:
        folder = os.path.splitext(bpy.data.filepath)[0] + "_liquid"
    else:
        folder = os.path.join(tempfile.gettempdir(), "fresing_liquid")
    return os.path.join(folder, name)


def _beds_path(path: str) -> str:
    return path + ".beds.npz"


def _close_reader(rt) -> None:
    rd = rt.pop("reader", None)
    if rd is not None:
        try:
            rd.close()
        except Exception:
            pass
    rt.pop("beds", None)


def _open(scene):
    """(reader, beds) of the bake made for this project as it is now, or (None, None)."""
    rt = runtime(scene)
    fp = _memo_fingerprint(scene)
    if rt.get("reader") is not None and rt.get("reader_fp") == fp:
        return rt["reader"], rt["beds"]
    _close_reader(rt)
    for path in (scene.get(CACHE_PROP, ""), cache_path(scene)):
        if not path or not os.path.isfile(path) or not os.path.isfile(_beds_path(path)):
            continue
        rd = liquid_cache.Reader.open(path, fp)
        if rd is None:
            continue
        try:
            beds = Beds.load(_beds_path(path), fp)
        except Exception:
            beds = None
        if beds is None:
            rd.close()
            continue
        rt.update(reader=rd, beds=beds, reader_fp=fp, path=path)
        return rd, beds
    return None, None


def is_baked(scene) -> bool:
    return wanted(scene) and _open(scene)[0] is not None


# ---------------------------------------------------------------------------
# the beds over time (the cut block's top changes)
# ---------------------------------------------------------------------------

class Beds:
    """Each chart's bed (m, NaN = no surface) at any frame: the first bed + the changes (frame, box, heights)."""

    def __init__(self, base: list, changes: list, fingerprint: str = "", geom=()):
        self.base = [np.asarray(b, np.float64) for b in base]
        self.geom = [tuple(float(x) for x in g) for g in geom]   # per chart (cell, x0, y0), m
        self.changes = sorted(changes, key=lambda x: x[0])      # (frame, chart, j0, i0, heights (h, w))
        self.frames = np.array([c[0] for c in self.changes], np.int64)
        self.fingerprint = fingerprint
        self._at = {}                                            # chart -> (number of changes applied, bed)

    def at(self, chart: int, frame: int) -> np.ndarray:
        """Chart ``chart``'s bed at ``frame`` (a copy kept; do not change it)."""
        n = int(np.searchsorted(self.frames, int(frame), side="right"))
        k, bed = self._at.get(chart, (0, None))
        if bed is None or k > n:
            k, bed = 0, self.base[chart].copy()
        for fr, c, j0, i0, hts in self.changes[k:n]:
            if c == chart:
                bed[j0:j0 + hts.shape[0], i0:i0 + hts.shape[1]] = hts
        self._at[chart] = (n, bed)
        return bed

    def save(self, path: str) -> None:
        d = {"fingerprint": np.array(self.fingerprint), "n_base": np.array(len(self.base)),
             "geom": np.array(self.geom, np.float64).reshape(-1, 3)}
        for c, b in enumerate(self.base):
            d[f"base{c}"] = b.astype(np.float32)
        meta = np.array([(fr, c, j0, i0, h.shape[0], h.shape[1]) for fr, c, j0, i0, h in self.changes],
                        np.int64).reshape(-1, 6)
        d["meta"] = meta
        d["heights"] = (np.concatenate([h.reshape(-1) for *_r, h in self.changes]).astype(np.float32)
                        if self.changes else np.zeros(0, np.float32))
        tmp = path + ".part.npz"
        np.savez_compressed(tmp, **d)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str, fingerprint: str | None = None):
        with np.load(path, allow_pickle=False) as z:
            fp = str(z["fingerprint"])
            if fingerprint is not None and fp != fingerprint:
                return None
            base = [z[f"base{c}"].astype(np.float64) for c in range(int(z["n_base"]))]
            meta, flat = z["meta"], z["heights"]
            geom = z["geom"].tolist()
        changes, pos = [], 0
        for fr, c, j0, i0, hh, ww in meta:
            n = int(hh * ww)
            changes.append((int(fr), int(c), int(j0), int(i0), flat[pos:pos + n].reshape(int(hh), int(ww))
                            .astype(np.float64)))
            pos += n
        return cls(base, changes, fp, geom)


# ---------------------------------------------------------------------------
# the charts from the machine
# ---------------------------------------------------------------------------

def _skip_names(scene) -> set:
    m = machining.settings(scene)
    skip = {ob.name for _it, ob in machining.bits(scene)}
    skip |= {ob.name for ob in machining._copies(scene)}
    if m.finished is not None:
        skip.add(m.finished.name)
    return skip


def _parts(scene) -> list:
    """The parts the liquid can lie on: shown, not excluded, not a bit or the finished-part reference."""
    skip = _skip_names(scene)
    out = []
    for ob in build.iter_parts(scene):
        if ob.get(build.PROP_EXCLUDED) or ob.name in skip or ob.hide_render or ob.data is None \
                or not len(ob.data.polygons):
            continue
        out.append(ob)
    return out


def _tris(me, M) -> tuple:
    me.calc_loop_triangles()
    v = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", v)
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int32)
    me.loop_triangles.foreach_get("vertices", t)
    M = np.asarray(M, np.float64)
    return v.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3], t.reshape(-1, 3)


def _bvh(meshes: list):
    vs, ts, off = [], [], 0
    for v, t in meshes:
        if not len(t):
            continue
        vs.append(v)
        ts.append(t + off)
        off += len(v)
    if not vs:
        return None
    return BVHTree.FromPolygons(np.concatenate(vs).tolist(), np.concatenate(ts).tolist(), all_triangles=True)


def _cast(bvh, xs, ys, z_from: float) -> np.ndarray:
    """Heights (len(ys), len(xs)) where rays straight down from ``z_from`` first hit; NaN where they miss."""
    out = np.full((len(ys), len(xs)), np.nan)
    if bvh is None:
        return out
    d = Vector((0.0, 0.0, -1.0))
    o = Vector((0.0, 0.0, z_from))
    rc = bvh.ray_cast
    for j, y in enumerate(ys):
        o.y = float(y)
        row = out[j]
        for i, x in enumerate(xs):
            o.x = float(x)
            hit = rc(o, d)[0]
            if hit is not None:
                row[i] = hit.z
    return out


def _box(objs, m_of) -> tuple:
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for ob in objs:
        mm = np.array(m_of(ob))
        bb = np.array([list(c) + [1.0] for c in ob.bound_box])
        w = (mm @ bb.T).T[:, :3]
        lo, hi = np.minimum(lo, w.min(axis=0)), np.maximum(hi, w.max(axis=0))
    return lo, hi


def _grid(lo, hi, cell) -> tuple:
    """Cell centres (xs, ys) covering lo … hi (x, y)."""
    nx = max(1, int(math.ceil((hi[0] - lo[0]) / cell)))
    ny = max(1, int(math.ceil((hi[1] - lo[1]) / cell)))
    x0 = 0.5 * (lo[0] + hi[0]) - 0.5 * (nx - 1) * cell
    y0 = 0.5 * (lo[1] + hi[1]) - 0.5 * (ny - 1) * cell
    return x0 + np.arange(nx) * cell, y0 + np.arange(ny) * cell


class Setup:
    """What the bake needs, read from the scene once (``gather``)."""

    def __init__(self):
        self.charts = []          # core.Chart
        self.roles = []           # "table" / "tray"
        self.mats = []            # (n, 4, 4) world-from-chart per frame
        self.f0 = 0
        self.n = 0
        self.fps = 24.0
        self.floor_z = -1.0
        self.m0 = np.eye(4)       # the workpiece's world matrix at the first frame
        self.base = None          # the table chart's bed without the block
        self.foot = None          # (j0, j1, i0, i1): the block's cells in the table chart
        self.tools = []           # (t, o (n, 3) riding, d (n, 3) riding, radius, flute)
        self.flood = np.zeros((0, 2))
        self.rpm = np.zeros((0, 2))
        self.hoses = 2
        self.rate = 14.0
        self.timeline = None
        self.cuts = np.zeros((0, 2))   # (t0, t1) frames of cutting segments
        self.drain_cells = 0


def gather(scene) -> Setup:
    """The charts, their motion and the inputs of the bake from the scene as it is (after Build and the motion read)."""
    st = Setup()
    s = settings(scene)
    m = machining.settings(scene)
    wp = machining.workpiece(scene)
    cell_t, cell_s = DETAIL.get(s.liquid_detail, DETAIL["NORMAL"])
    ms = np.array(m["fr_wp_m"], dtype=np.float64).reshape(-1, 4, 4)
    st.f0 = int(m.get("fr_wp_f0", scene.frame_start))
    st.n = len(ms)
    st.fps = scene.render.fps / (scene.render.fps_base or 1.0)
    st.m0 = ms[0]
    carry = ms @ np.linalg.inv(ms[0])
    M0 = Matrix([list(r) for r in st.m0])
    # which parts ride with the workpiece, which stand still (as the chips: ``chips.mover``)
    from . import chips
    cache = {}
    wp_mover = chips.mover(wp, cache)
    parts = _parts(scene)
    riding, still = [], []
    for ob in parts:
        if ob is wp:
            continue
        mv = chips.mover(ob, cache)
        if wp_mover and mv == wp_mover:
            riding.append(ob)
        elif not mv:
            still.append(ob)
    moving = bool(wp_mover)
    if not moving:                                    # the block stands still: one chart of what is round it
        riding, still = still, []
    to_ride = M0 @ wp.matrix_world.inverted()
    # the block's box in riding space
    sv, _st = _tris(m.stock_mesh or wp.data, st.m0)
    blo, bhi = sv.min(axis=0), sv.max(axis=0)
    all_parts = parts + ([wp] if wp not in parts else [])
    st.floor_z = float(build.world_bounds(all_parts)[0][2]) - 0.01 if all_parts else -1.0
    # --- the table chart: riding parts round the block (all of them on a moving table; within 0.5 m when still)
    # a part that lies inside the block (a finished-part reference not picked in Milling) is no surface
    inside = lambda o: bool(np.all(_box([o], lambda q: to_ride @ q.matrix_world)[0] >= blo - MM) and  # noqa: E731
                            np.all(_box([o], lambda q: to_ride @ q.matrix_world)[1] <= bhi + MM))
    riding = [ob for ob in riding if not inside(ob)]
    if moving:
        near = riding
    else:
        near = [ob for ob in riding if _overlap(ob, lambda o: to_ride @ o.matrix_world, blo[:2] - 0.5, bhi[:2] + 0.5)]
    meshes = [_tris(ob.data, to_ride @ ob.matrix_world) for ob in near]
    lo, hi = _box(near, lambda o: to_ride @ o.matrix_world) if near else (blo, bhi)
    lo, hi = np.minimum(lo, blo), np.maximum(hi, bhi)
    xs, ys = _grid(lo - cell_t, hi + cell_t, cell_t)
    z_from = float(max(hi[2], bhi[2])) + 0.02
    base = _cast(_bvh(meshes), xs, ys, z_from)
    st.base = base
    j0 = max(0, int(np.floor((blo[1] - ys[0]) / cell_t)) - 1)
    j1 = min(len(ys), int(np.ceil((bhi[1] - ys[0]) / cell_t)) + 2)
    i0 = max(0, int(np.floor((blo[0] - xs[0]) / cell_t)) - 1)
    i1 = min(len(xs), int(np.ceil((bhi[0] - xs[0]) / cell_t)) + 2)
    st.foot = (j0, j1, i0, i1)
    st.z_from = z_from
    st.xs, st.ys = xs, ys
    st.charts.append(core.Chart("table", base.copy(), cell_t, float(xs[0]), float(ys[0]), open_edges=True))
    st.roles.append("table")
    st.mats.append(carry if moving else core.still(st.n))
    # --- the tray: still parts round where the table goes
    if moving and still:
        corners = np.array([[x, y, z, 1.0] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        pts = np.einsum("fij,cj->fci", carry, corners)[:, :, :3].reshape(-1, 3)
        slo, shi = pts.min(axis=0)[:2] - TRAY_REACH, pts.max(axis=0)[:2] + TRAY_REACH
        near_s = [ob for ob in still if _overlap(ob, lambda o: o.matrix_world, slo, shi)]
        whole = [ob for ob in near_s if any(w in str(ob.get(build.PROP_NAME, ob.name)).upper() for w in TRAY_WORDS)]
        if whole:                                 # the chip tray and its drain: all of them
            wlo, whi = _box(whole, lambda o: o.matrix_world)
            slo, shi = np.minimum(slo, wlo[:2]), np.maximum(shi, whi[:2])
            near_s = [ob for ob in still if _overlap(ob, lambda o: o.matrix_world, slo, shi)]
        if near_s:
            plo, phi = _box(near_s, lambda o: o.matrix_world)
            slo, shi = np.maximum(slo, plo[:2]), np.minimum(shi, phi[:2])
            txs, tys = _grid(slo, shi, cell_s)
            tz = float(phi[2]) + 0.02
            # (the drain itself is no surface: its flange under the floor reaches past the tray's wall)
            surf = [ob for ob in near_s if DRAIN_NAME not in str(ob.get(build.PROP_NAME, ob.name)).upper()]
            tbed = _cast(_bvh([_tris(ob.data, ob.matrix_world) for ob in surf]), txs, tys, tz)
            drain = _drain(scene, near_s, tbed, txs, tys, cell_s)
            st.drain_cells = int((drain > 0).sum()) if drain is not None else 0
            st.charts.append(core.Chart("tray", tbed, cell_s, float(txs[0]), float(tys[0]), open_edges=False,
                                        drain=drain))
            st.roles.append("tray")
            st.mats.append(core.still(st.n))
    # --- the inputs
    for c in machining.cut_items(scene):
        p = c.path
        o = p.o @ st.m0[:3, :3].T + st.m0[:3, 3]
        d = p.d @ st.m0[:3, :3].T
        st.tools.append((np.asarray(p.t, float), o, d, float(c.tool.radius), float(max(c.tool.length, 0.01))))
    r = coolant.root()
    sp = coolant.spans(r)
    st.flood = sp[sp[:, 2] == ccore.FLOOD][:, :2] if len(sp) else np.zeros((0, 2))
    st.rpm = (np.array(r.get("fr_rpm", ()), dtype=np.float64).reshape(-1, 2) if r is not None
              else np.zeros((0, 2)))
    st.hoses = int(s.auto_count) if s.source == "AUTO" else max(1, len(s.nozzles))
    st.rate = rate(scene)
    st.timeline = machining._timeline(scene)
    if st.timeline is not None:
        st.cuts = np.array([(sg.t0, sg.t1) for sg in st.timeline.segs if sg.cuts], np.float64).reshape(-1, 2)
    return st


def _overlap(ob, m_of, lo, hi) -> bool:
    blo, bhi = _box([ob], m_of)
    return bool(bhi[0] >= lo[0] and blo[0] <= hi[0] and bhi[1] >= lo[1] and blo[1] <= hi[1])


def _drain(scene, objs, bed, xs, ys, cell) -> np.ndarray | None:
    """The drain's orifice per tray cell (m^2): the cells over the hole of the part named COOLANT DRAIN. Those cells
    get the height of the drain's top (the tray's floor round the hole); the bed is changed in place."""
    dr = next((ob for ob in objs if DRAIN_NAME in str(ob.get(build.PROP_NAME, ob.name)).upper()), None)
    if dr is None:
        return None
    lo, hi = _box([dr], lambda o: o.matrix_world)
    cx, cy = 0.5 * (lo[0] + hi[0]), 0.5 * (lo[1] + hi[1])
    rad = 0.5 * min(hi[0] - lo[0], hi[1] - lo[1])
    X, Y = np.meshgrid(xs, ys)
    r = np.hypot(X - cx, Y - cy)
    inside = r <= rad
    ring = (r > rad) & (r <= rad + 4 * cell) & np.isfinite(bed)
    top = float(np.min(bed[ring])) if ring.any() else float(hi[2])        # the floor round it, at its lowest
    deep = inside & np.isfinite(bed) & (bed < top - DRAIN_DEEP)   # rays down the hole (NaN: outside the tray)
    if not deep.any():                                     # no hole seen: the middle cell
        j, i = np.unravel_index(np.argmin(np.where(inside, r, np.inf)), X.shape)
        deep = np.zeros_like(inside)
        deep[j, i] = True
    hole = float(r[deep].max()) + cell                     # the hole's edge: a little below the floor round it
    low = (r <= hole) & np.isfinite(bed) & (bed < top - 0.002)
    top -= 0.002                                           # (a hole's edge: everything round it runs in)
    bed[low | deep] = top
    out = np.zeros_like(bed)
    out[deep] = cell * cell
    return out


# ---------------------------------------------------------------------------
# inputs per frame
# ---------------------------------------------------------------------------

def _tool_at(st: Setup, f: float):
    """(radius, flute, tip riding, axis riding) of the tool cutting at frame f, or None."""
    for t, o, d, rad, flute in st.tools:
        if len(t) and t[0] - 1e-6 <= f <= t[-1] + 1e-6:
            tip = np.array([np.interp(f, t, o[:, k]) for k in range(3)])
            ax = np.array([np.interp(f, t, d[:, k]) for k in range(3)])
            n = float(np.linalg.norm(ax))
            ax = ax / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])
            return rad, flute, tip, ax
    return None


def _rpm(st: Setup, f: float) -> float:
    if not len(st.rpm):
        return 0.0
    k = int(np.searchsorted(st.rpm[:, 0], f + 1e-6, side="right")) - 1
    return float(st.rpm[k, 1]) if k >= 0 else 0.0


def _flooding(st: Setup, f: float) -> bool:
    return bool(len(st.flood) and np.any((st.flood[:, 0] <= f + 1e-6) & (f < st.flood[:, 1] - 1e-6)))


def _world(st: Setup, k: int, p) -> np.ndarray:
    M = st.mats[0][min(max(k, 0), st.n - 1)]
    return M[:3, :3] @ np.asarray(p, float) + M[:3, 3]


def inputs(st: Setup, k: int) -> tuple:
    """(pours, tool) during the step from frame index k (frame f0 + k) to k + 1."""
    f = st.f0 + k
    t = _tool_at(st, f)
    pours, tool = [], None
    if t is not None:
        rad, flute, tip_r, ax_r = t
        M = st.mats[0][min(max(k, 0), st.n - 1)]
        tip = _world(st, k, tip_r)
        ax = M[:3, :3] @ ax_r
        rpm = _rpm(st, f)
        if rpm:
            tool = core.Tool(tuple(tip), tuple(ax), rad, flute, rpm)
        if _flooding(st, f) and st.rate > 0:
            # one jet per hose, landing just outside the tool (the jets run down it and drop off round its tip)
            a = ax / max(float(np.linalg.norm(ax)), 1e-12)
            u = np.cross(a, [1.0, 0.0, 0.0])
            if np.linalg.norm(u) < 1e-6:
                u = np.cross(a, [0.0, 1.0, 0.0])
            u /= np.linalg.norm(u)
            v = np.cross(a, u)
            n = max(1, st.hoses)
            for h in range(n):
                ang = 2.0 * math.pi * (h + 0.25) / n
                p = tip + (rad + HOSE_GAP) * (math.cos(ang) * u + math.sin(ang) * v) + 0.02 * a
                pours.append(core.Pour(tuple(p), st.rate / n, tuple(-a), radius=2.5 * MM))
    return pours, tool


# ---------------------------------------------------------------------------
# the cut block's top
# ---------------------------------------------------------------------------

class _Cut:
    """Reads the cut block's top into the table chart's bed, only where the tools went since the last read."""

    def __init__(self, st: Setup):
        self.st = st
        self.last = None              # frame of the last read
        j0, j1, i0, i1 = st.foot
        self.box = (j0, j1, i0, i1)
        self.bed = st.base.copy()

    def _mesh(self, T):
        tl = self.st.timeline
        out = tl.mesh_at(float(T))
        v, t = out[0], out[1]
        M = self.st.m0
        return v @ M[:3, :3].T + M[:3, 3], np.asarray(t, np.int64).reshape(-1, 3)

    def changed(self, T) -> bool:
        if self.last is None:
            return True
        c = self.st.cuts
        return bool(len(c) and np.any((c[:, 0] < T + 1e-9) & (c[:, 1] > self.last + 1e-9)))

    def _swept(self, T):
        """(j0, j1, i0, i1) of the table cells the tools went over between the last read and T."""
        st = self.st
        j0, j1, i0, i1 = self.box
        if self.last is None:
            return j0, j1, i0, i1
        pts, rmax = [], 0.0
        for t, o, _d, rad, _fl in st.tools:
            sel = (t >= self.last - 1.0) & (t <= T + 1.0)
            if sel.any():
                pts.append(o[sel])
                rmax = max(rmax, rad)
        if not pts:
            return None
        p = np.concatenate(pts)
        cell = st.charts[0].cell
        m = rmax + 3 * cell
        a0 = max(j0, int(np.floor((p[:, 1].min() - m - st.ys[0]) / cell)))
        a1 = min(j1, int(np.ceil((p[:, 1].max() + m - st.ys[0]) / cell)) + 1)
        b0 = max(i0, int(np.floor((p[:, 0].min() - m - st.xs[0]) / cell)))
        b1 = min(i1, int(np.ceil((p[:, 0].max() + m - st.xs[0]) / cell)) + 1)
        if a1 <= a0 or b1 <= b0:
            return None
        return a0, a1, b0, b1

    def read(self, T):
        """The new bed if the block changed since the last read: (bed, (j0, i0, heights)) or None."""
        if self.st.timeline is None or not self.changed(T):
            return None
        box = self._swept(T)
        self.last = float(T)
        if box is None:
            return None
        v, t = self._mesh(T)
        bvh = _bvh([(v, t)])
        a0, a1, b0, b1 = box
        st = self.st
        hits = _cast(bvh, st.xs[b0:b1], st.ys[a0:a1], st.z_from)
        base = st.base[a0:a1, b0:b1]
        new = np.where(np.isfinite(hits), np.where(np.isfinite(base), np.fmax(hits, base), hits), base)
        old = self.bed[a0:a1, b0:b1]
        same = (np.isnan(new) & np.isnan(old)) | (np.abs(np.nan_to_num(new) - np.nan_to_num(old)) < 1e-7)
        if same.all():
            return None
        self.bed[a0:a1, b0:b1] = new
        return self.bed, (a0, b0, new.copy())


# ---------------------------------------------------------------------------
# the bake
# ---------------------------------------------------------------------------

def steps(scene, notes: list | None = None, helpers: int | None = None):
    """The bake as a generator: yields the progress 0 … 1; the cache file is whole only at the end. ``notes`` gets
    the bake's numbers (one dict)."""
    t_start = time.perf_counter()
    fp = fingerprint(scene)
    st = gather(scene)
    t_gather = time.perf_counter() - t_start
    yield 0.02
    path = cache_path(scene)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    names = [(ch.name, ch.shape) for ch in st.charts]
    if helpers is None:
        cells = sum(int(np.isfinite(ch.bed).sum()) for ch in st.charts)
        helpers = liquid_pool.default_helpers() if cells > 40000 else 0
    cut = _Cut(st)
    changes = []
    first = cut.read(st.f0)
    if first is not None:
        st.charts[0].bed = first[0].copy()
    base_beds = [ch.bed.copy() for ch in st.charts]
    sim = core.Liquid(st.charts, st.mats, st.fps, st.floor_z, helpers=helpers, wave_depth=WAVE_DEPTH)
    writer = liquid_cache.Writer(path, fp, names, st.fps)
    ok = False
    t_solve = 0.0
    settled = stepped = subs = 0
    try:
        writer.add(st.f0, [np.zeros(ch.shape) for ch in st.charts], np.zeros((0, 3)), np.zeros(0), sim.totals())
        last = time.perf_counter()
        for k in range(st.n - 1):
            f = st.f0 + k
            if k % CUT_EVERY == 0 and k:
                got = cut.read(f)
                if got is not None:
                    sim.set_bed(0, got[0])
                    a0, b0, hts = got[1]
                    changes.append((f, 0, a0, b0, hts))
            pours, tool = inputs(st, k)
            t0 = time.perf_counter()
            fr = sim.step(k, pours, tool)
            t_solve += time.perf_counter() - t0
            settled += bool(fr.settled)
            stepped += sum(fr.stepped)
            subs += max(fr.substeps) if fr.substeps else 0
            # (the 0.04 mm film is the wet sheen: only what shows goes into the file)
            writer.add(f + 1, [np.where(d > SHOW, d, 0.0) for d in (sim.depth(c) for c in range(len(st.charts)))],
                       fr.drops, fr.drop_vol, fr.totals)
            if time.perf_counter() - last > 0.05:
                last = time.perf_counter()
                yield 0.03 + 0.96 * (k + 1) / max(1, st.n - 1)
        Beds(base_beds, changes, fp, [(ch.cell, ch.x0, ch.y0) for ch in st.charts]).save(_beds_path(path))
        writer.close()
        ok = True
        tot = sim.totals()
    finally:
        sim.close()
        if not ok:
            writer.abort()
            try:
                os.remove(_beds_path(path))
            except OSError:
                pass
    scene[CACHE_PROP] = path
    rt = runtime(scene)
    _close_reader(rt)
    info = dict(frames=st.n, cells=[int(np.isfinite(ch.bed).sum()) for ch in st.charts],
                cell_mm=[ch.cell * 1000 for ch in st.charts], seconds=time.perf_counter() - t_start,
                gather_s=t_gather, solve_s=t_solve, settled=settled, helpers=helpers, drain_cells=st.drain_cells,
                cut_reads=len(changes), stepped=stepped / max(1, st.n - 1), substeps=subs / max(1, st.n - 1),
                mb=os.path.getsize(path) / 1e6, totals=tot)
    rt["info"] = info
    rt.pop("declined", None)
    if notes is not None:
        notes.append(info)
    yield 1.0


def bake_now(scene, helpers: int | None = None) -> dict | None:
    """Work the liquid out at once (background, render queue, tests): its numbers, or None when it is not wanted.
    An unchanged project reads its bake (no work)."""
    if not wanted(scene):
        return None
    if _open(scene)[0] is not None:
        return runtime(scene).get("info") or {"reused": True}
    notes = []
    _STATE["guard"] += 1
    try:
        for _p in steps(scene, notes, helpers=helpers):
            pass
    finally:
        _STATE["guard"] -= 1
    show(scene)
    return notes[0] if notes else None


def prepare(scene) -> None:
    """Before rendering (the render queue, F12 in the background): the liquid baked for the animation as it is."""
    try:
        if wanted(scene):
            bake_now(scene)
            show(scene)
        else:
            hide(scene)
    except Exception as exc:                          # the render goes on without the liquid
        runtime(scene)["status"] = f"The liquid could not be worked out: {exc}"
        print("Fresing Render: liquid failed:", exc)


def cancelled(scene) -> None:
    """The user stopped the bake: not started again by itself until something changes (or Work out the liquid)."""
    rt = runtime(scene)
    rt["declined"] = _memo_fingerprint(scene)
    rt["status"] = "Stopped: press Work out the liquid to start again"


def status(scene) -> str:
    rt = runtime(scene)
    if not asked(scene):
        return ""
    why = problem(scene)
    if why:
        return why
    if running() and _STATE.get("scene") == scene.name:
        return f"Working it out: {100.0 * progress():.0f} %"
    rd, _beds = _open(scene)
    if rd is None:
        if rt.get("declined") == _memo_fingerprint(scene):
            return rt.get("status") or "Stopped"
        return "Not worked out for this Build yet"
    info = rt.get("info")
    n = len(rd.frames)
    if info and "cells" in info:
        return (f"Worked out: {n:,} frames, {sum(info['cells']):,} cells, {info['seconds']:.0f} s")
    return f"Worked out: {n:,} frames"


# ---------------------------------------------------------------------------
# starting the bake in the window
# ---------------------------------------------------------------------------

def request(scene=None) -> None:
    """Start the bake in the window soon if the liquid is wanted and not worked out (after Build, a setting)."""
    if bpy.app.background or _STATE["pending"]:
        return
    _STATE["pending"] = True
    bpy.app.timers.register(_start_timer, first_interval=0.4)


def _start_timer():
    _STATE["pending"] = False
    if running():
        return None
    try:
        wm = bpy.context.window_manager
        for scene in bpy.data.scenes:
            if not hasattr(scene, "fresing") or not wanted(scene):
                continue
            if _open(scene)[0] is not None:
                continue
            if runtime(scene).get("declined") == _memo_fingerprint(scene):
                continue
            win = next((w for w in wm.windows if w.scene == scene), None)
            if win is None:
                continue
            with bpy.context.temp_override(window=win):
                bpy.ops.fresing.liquid_bake("INVOKE_DEFAULT")
            break
    except Exception as exc:                          # never break the app over the liquid
        print("Fresing Render: the liquid could not start:", exc)
    return None


# ---------------------------------------------------------------------------
# drawing
# ---------------------------------------------------------------------------

def _collection(scene):
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        col[TAG] = "collection"
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _object(scene, name: str, role: str):
    ob = bpy.data.objects.get(name)
    if ob is None or ob.get(TAG) != role or ob.type != "MESH":
        me = bpy.data.meshes.new(name)
        me[TAG] = role
        ob = bpy.data.objects.new(name, me)
        ob[TAG] = role
        ob.hide_select = True
    col = _collection(scene)
    if ob.name not in col.objects:
        col.objects.link(ob)
    return ob


def material(scene=None) -> bpy.types.Material:
    """The liquid's material: Cycles output = the coolant's look (milky emulsion or clear oil), EEVEE output = the
    EEVEE look chosen in the Coolant panel; light grey in Solid view."""
    s = settings(scene) if scene is not None else None
    kind = s.liquid if s is not None else "EMULSION"
    ev = getattr(s, "liquid_eevee", "MILKY") if s is not None else "MILKY"
    look = ccore.LIQUIDS.get(kind, ccore.LIQUIDS["EMULSION"])
    sig = repr((1, kind, ev, look))
    mat = bpy.data.materials.get(MAT)
    if mat is not None and mat.get(TAG) == sig:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(MAT)
    mat[TAG] = sig
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    # Cycles: see-through and milky as the jets, a little rougher (a pool's surface ripples)
    cy = nt.nodes.new("ShaderNodeBsdfPrincipled")
    cy.location = (-300, 200)
    cy.inputs["Base Color"].default_value = (*look.colour, 1.0)
    cy.inputs["Roughness"].default_value = look.roughness
    cy.inputs["IOR"].default_value = look.ior
    cy.inputs["Transmission Weight"].default_value = look.transmission
    if look.milky:
        cy.inputs["Subsurface Weight"].default_value = look.milky
        cy.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
        cy.inputs["Subsurface Scale"].default_value = 0.002
    out_c = nt.nodes.new("ShaderNodeOutputMaterial")
    out_c.target = "CYCLES"
    out_c.location = (100, 200)
    nt.links.new(cy.outputs[0], out_c.inputs["Surface"])
    # EEVEE: one of three looks (the owner judges them on his graphics card)
    ee = nt.nodes.new("ShaderNodeBsdfPrincipled")
    ee.location = (-300, -300)
    ee.inputs["Base Color"].default_value = (*look.colour, 1.0)
    ee.inputs["IOR"].default_value = look.ior
    method, refract = "DITHERED", False
    if ev == "CLEAR":
        ee.inputs["Roughness"].default_value = look.roughness
        ee.inputs["Transmission Weight"].default_value = look.transmission
        refract = True
    elif ev == "BLENDED":
        ee.inputs["Roughness"].default_value = 0.05
        ee.inputs["Alpha"].default_value = 0.72 if kind == "EMULSION" else 0.45
        ee.inputs["Coat Weight"].default_value = 0.6
        method = "BLENDED"
    else:                                             # MILKY
        ee.inputs["Roughness"].default_value = 0.12
        ee.inputs["Subsurface Weight"].default_value = 0.35 if kind == "EMULSION" else 0.0
        ee.inputs["Subsurface Radius"].default_value = (1.0, 1.0, 1.0)
        ee.inputs["Subsurface Scale"].default_value = 0.002
        ee.inputs["Coat Weight"].default_value = 1.0
        ee.inputs["Coat Roughness"].default_value = 0.02
    out_e = nt.nodes.new("ShaderNodeOutputMaterial")
    out_e.target = "EEVEE"
    out_e.location = (100, -300)
    nt.links.new(ee.outputs[0], out_e.inputs["Surface"])
    mat.diffuse_color = (0.82, 0.84, 0.86, 1.0)        # Solid view: a light grey sheet
    mat.roughness = 0.2
    for attr, val in (("surface_render_method", method), ("use_raytrace_refraction", refract),
                      ("thickness_mode", "SLAB")):
        try:
            setattr(mat, attr, val)
        except (AttributeError, TypeError):
            pass
    return mat


def sheet(depth, bed, cell, x0, y0) -> tuple:
    """The liquid's top over the wet cells as a mesh in the chart's frame: (verts (n, 3), quads (m, 4)).
    Corners at the mean top of the wet cells round them; cells shallower than ``SHOW`` are left out."""
    d = np.asarray(depth, np.float64)
    b = np.nan_to_num(np.asarray(bed, np.float64), nan=0.0)
    wet = (d > SHOW) & np.isfinite(np.asarray(bed, np.float64))
    if not wet.any():
        return np.zeros((0, 3), np.float32), np.zeros((0, 4), np.int32)
    top = np.where(wet, b + d + LIFT, 0.0)
    ny, nx = d.shape
    S = np.zeros((ny + 2, nx + 2))
    W = np.zeros((ny + 2, nx + 2))
    S[1:-1, 1:-1] = top
    W[1:-1, 1:-1] = wet
    cs = S[:-1, :-1] + S[:-1, 1:] + S[1:, :-1] + S[1:, 1:]          # corner (j, i) = lower-left of cell (j, i)
    cw = W[:-1, :-1] + W[:-1, 1:] + W[1:, :-1] + W[1:, 1:]
    used = cw > 0
    idx = np.full(used.shape, -1, np.int64)
    idx[used] = np.arange(int(used.sum()))
    jj, ii = np.nonzero(used)
    verts = np.stack([x0 + (ii - 0.5) * cell, y0 + (jj - 0.5) * cell, cs[used] / cw[used]], -1)
    wj, wi = np.nonzero(wet)
    quads = np.stack([idx[wj, wi], idx[wj, wi + 1], idx[wj + 1, wi + 1], idx[wj + 1, wi]], -1)
    return verts.astype(np.float32), quads.astype(np.int32)


def _write_sheet(me, verts, quads) -> None:
    if not len(verts) and not len(me.vertices):
        return
    me.clear_geometry()
    if len(verts):
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", np.ascontiguousarray(verts, np.float32).reshape(-1))
        me.loops.add(len(quads) * 4)
        me.loops.foreach_set("vertex_index", np.ascontiguousarray(quads, np.int32).reshape(-1))
        me.polygons.add(len(quads))
        me.polygons.foreach_set("loop_start", np.arange(0, len(quads) * 4, 4, dtype=np.int32))
        me.polygons.foreach_set("use_smooth", np.ones(len(quads), bool))
    me.update()


def _set_material(ob, mat) -> None:
    me = ob.data
    if not me.materials:
        me.materials.append(mat)
    elif me.materials[0] is not mat:
        me.materials[0] = mat


def show(scene, T: float | None = None) -> bool:
    """Draw the liquid at frame T (default: the current frame) from the bake. True when drawn."""
    rt = runtime(scene)
    if not wanted(scene):
        hide(scene)
        return False
    rd, beds = _open(scene)
    if rd is None:
        hide(scene)
        return False
    if T is None:
        T = float(scene.frame_current)
    frames = rd.frames
    f = int(math.floor(T + 1e-6))
    f = min(max(f, int(frames[0])), int(frames[-1]))
    depths, drops, vols, _tot = rd.read(f)
    mat = material(scene)
    s_m = machining.settings(scene)
    m0 = np.array(s_m["fr_wp_m"][:16], dtype=np.float64).reshape(4, 4)
    wp = machining.workpiece(scene)
    names = rd.names
    shown = 0
    for c, d in enumerate(depths):
        role = names[c] if c < len(names) else "tray"
        bed = beds.at(c, f)
        cell, x0, y0 = beds.geom[c]
        v, q = sheet(d, bed, cell, x0, y0)
        if role == "table":
            ob = _object(scene, OBJ_TABLE, "table")
            inv = np.linalg.inv(m0)
            if len(v):
                v = (v.astype(np.float64) @ inv[:3, :3].T + inv[:3, 3]).astype(np.float32)
            from .chips import _follow
            if wp is not None:
                _follow(ob, wp)
        else:
            ob = _object(scene, OBJ_TRAY, "tray")
        _write_sheet(ob.data, v, q)
        _set_material(ob, mat)
        shown += len(q)
        if ob.hide_render or ob.hide_viewport:
            ob.hide_render = ob.hide_viewport = False
    dob = _object(scene, OBJ_DROPS, "drops")
    mod = dob.modifiers.get("Drops")
    if mod is None:
        mod = dob.modifiers.new("Drops", "NODES")
    ng = coolant._drops_group()
    if mod.node_group is not ng:
        mod.node_group = ng
    size = np.cbrt(np.maximum(np.asarray(vols, np.float64), 0.0) * 1e-3 * 3.0 / (4.0 * math.pi))
    coolant._write_points(dob.data, np.asarray(drops, np.float64), np.maximum(size, 0.1 * MM))
    if dob.hide_render or dob.hide_viewport:
        dob.hide_render = dob.hide_viewport = False
    rt["shown"] = (f, shown, len(vols))
    return True


def hide(scene) -> None:
    """No liquid in the picture: the objects stay, empty."""
    for name in (OBJ_TABLE, OBJ_TRAY, OBJ_DROPS):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG) and ob.data is not None and len(ob.data.vertices):
            ob.data.clear_geometry()
            ob.data.update()
    runtime(scene)["shown"] = None


def remove(scene) -> None:
    """Take everything made here out (the liquid switched off)."""
    for name in (OBJ_TABLE, OBJ_TRAY, OBJ_DROPS):
        ob = bpy.data.objects.get(name)
        if ob is not None and ob.get(TAG):
            me = ob.data
            bpy.data.objects.remove(ob)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
    col = bpy.data.collections.get(COLLECTION)
    if col is not None and col.get(TAG) and not len(col.objects):
        bpy.data.collections.remove(col)


def objects() -> list:
    return [ob for ob in (bpy.data.objects.get(n) for n in (OBJ_TABLE, OBJ_TRAY, OBJ_DROPS))
            if ob is not None and ob.get(TAG)]


# ---------------------------------------------------------------------------
# settings changed, frames, files
# ---------------------------------------------------------------------------

def settings_changed(scene) -> None:
    """The tick, the detail or the EEVEE look changed."""
    if not asked(scene):
        remove(scene)
        return
    material(scene)
    if wanted(scene):
        if not show(scene):
            request(scene)


def _off_main_thread() -> bool:
    return threading.current_thread() is not threading.main_thread()


def _draw(scene) -> None:
    if _STATE["guard"] or scene is None or not hasattr(scene, "fresing"):
        return
    try:
        if not asked(scene):
            if objects() and runtime(scene).get("shown") is not None:
                hide(scene)
            return
        if not bpy.app.background and _off_main_thread() and not scene.render.use_lock_interface:
            return
        _STATE["guard"] += 1
        try:
            if not show(scene) and not bpy.app.background and not _off_main_thread() and not running():
                if wanted(scene) and runtime(scene).get("declined") != _memo_fingerprint(scene):
                    request(scene)
        finally:
            _STATE["guard"] -= 1
    except Exception as exc:
        print("Fresing Render: liquid frame update failed:", exc)


@persistent
def _on_frame_pre(scene, _depsgraph=None):
    _draw(scene)


@persistent
def _on_load(_dummy=None):
    forget()


@persistent
def _on_save(_dummy=None):
    """A project saved for the first time: its bake moves from the temp folder next to it."""
    try:
        for scene in bpy.data.scenes:
            path = scene.get(CACHE_PROP, "")
            if not path or not os.path.isfile(path) or not bpy.data.filepath:
                continue
            want = cache_path(scene)
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(want)):
                continue
            if os.path.dirname(os.path.abspath(path)) != os.path.join(tempfile.gettempdir(), "fresing_liquid"):
                continue                                # (a bake next to another project stays where it is)
            os.makedirs(os.path.dirname(want), exist_ok=True)
            _close_reader(runtime(scene))
            shutil.move(path, want)
            shutil.move(_beds_path(path), _beds_path(want))
            scene[CACHE_PROP] = want
    except Exception as exc:
        print("Fresing Render: the liquid's bake could not be moved next to the project:", exc)


def register():
    bpy.app.handlers.frame_change_pre.append(_on_frame_pre)
    bpy.app.handlers.load_post.append(_on_load)
    bpy.app.handlers.save_post.append(_on_save)


def unregister():
    for lst, fn in ((bpy.app.handlers.frame_change_pre, _on_frame_pre), (bpy.app.handlers.load_post, _on_load),
                    (bpy.app.handlers.save_post, _on_save)):
        if fn in lst:
            lst.remove(fn)
    forget()
