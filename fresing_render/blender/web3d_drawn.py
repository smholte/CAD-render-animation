"""Parts the app draws with modifiers, for the web 3D model (task 0142).

A cable, a wire rope or a hose (4 Motion > Cables and paths, Hoses and drag chains), the rope on a drum or carousel
(Drums and carousels), track links and pads (Tracks and belts), drag-chain links and things riding on a cable are
drawn by Geometry Nodes on the part itself (or, for a spool, on an object of its own). Before this task the web model
held the part's CAD shape, standing still. Here the export reads back what Blender draws – the *evaluated* mesh – at
the frame shown and, for an animation, at every frame, and sorts each part by what it is:

``RIGID``   the part's own mesh moved as one piece: the move is fitted from 4 points (``core.web3d_tubes.fit_rigid``)
            and goes into the part's place (plain glTF node animation).
``TUBE``    rings round a centre line: the ring centres, the first ring's turn, the length along the cable at the
            first ring, the metres paid out (the cable look's offset).
``SPOOL``   the rope on a spool: its whole wound path (the spool's shapes mesh, in the rope object's coordinates,
            which turn with the spool) once, the cut it shows at each frame (``fr_L`` of the first and last ring).
``SHAPE``   anything else a modifier changes: its evaluated mesh at the frame shown.
``HIDDEN``  nothing is drawn (the CAD coil a spool hides): left out.

Nothing here changes the project: the cable, flex, spool and track code is only read. The evaluated meshes kept for
the file are copies (``bpy.data.meshes.new_from_object``), removed by ``Drawn.close``.
"""

from __future__ import annotations

import numpy as np

import bpy

from ..core import web3d_tubes as T
from . import build, cable_looks

RIGID, TUBE, SPOOL, SHAPE, HIDDEN = "RIGID", "TUBE", "SPOOL", "SHAPE", "HIDDEN"
COPY = "FR web shape"                       # name of the evaluated copies (removed at the end)


def _spool_mod():
    from . import spool
    return spool.MOD, spool.KIND, spool.TAG


def _on(ob) -> bool:
    """A modifier of the object changes what is drawn (shown in renders)."""
    return any(m.show_render for m in ob.modifiers)


def spool_objects(scene) -> list:
    """The ropes and full-layer solids spools draw (kind ``spool``), shown now or shown by the animation: they are
    parts of the web model as well."""
    mod, kind, _tag = _spool_mod()
    out = []
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) != kind or ob.type != "MESH" or ob.get("fr_spool_role") not in ("rope", "solid"):
            continue
        try:
            if not ob.visible_get() or ob.hide_render:
                continue
        except RuntimeError:
            continue
        if ob.get("fr_spool_role") == "solid" and (ob.data is None or not len(ob.data.polygons)):
            continue
        out.append(ob)
    return out


def is_drawn(ob) -> bool:
    mod, kind, _tag = _spool_mod()
    return ob.type == "MESH" and (bool(len(ob.modifiers)) and _on(ob)) and not (
        ob.get(build.PROP_KIND) == kind and ob.get("fr_spool_role") == "solid")


def _vertices(me) -> np.ndarray:
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    if n:
        me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def _attr(me, name: str, kind: str = "FLOAT"):
    a = me.attributes.get(name)
    if a is None or a.domain != "POINT":
        return None
    if kind == "VEC":
        v = np.empty(len(me.vertices) * 3, np.float32)
        a.data.foreach_get("vector", v)
        return v.reshape(-1, 3)
    v = np.empty(len(me.vertices), np.float32)
    a.data.foreach_get("value", v)
    return v


def _pay(ev) -> float:
    try:
        v = ev.get(cable_looks.PAY)
    except (TypeError, ReferenceError):
        v = None
    return 0.0 if v is None else float(v) - cable_looks.PAY_BIAS


def _scale(ob) -> float:
    m = np.array(ob.matrix_world)[:3, :3]
    return float(np.cbrt(abs(np.linalg.det(m)))) or 1.0


def look_of(ob) -> dict | None:
    """The cable look the page draws on this tube: from its material (the look's nodes, ``cable_looks``) and the
    object's ``fr_cable_look``; None for a tube with a plain look."""
    from ..core import ral
    for slot in ob.material_slots:
        mat = slot.material
        nodes = cable_looks.nodes_of(mat) if mat is not None else {}
        if cable_looks.NODE_PATTERN not in nodes:
            continue
        kind = "ROPE" if cable_looks.NODE_WIRES in nodes else "POWER"
        look = ob.get(cable_looks.LOOK)
        look = [float(v) for v in look] if look is not None else None
        return T.look_for_page(kind, look, cable_looks.defaults(kind), ral.srgb_to_linear)
    return None


class Item:
    """One drawn object: its kind at the frame shown, what the file needs, what is read per frame."""

    def __init__(self, ob, kind: str):
        self.ob = ob
        self.name = ob.name
        self.kind = kind
        self.mesh = None                    # evaluated copy (TUBE, SPOOL, SHAPE)
        self.sides = 0
        self.radius = 0.0
        self.count = 0                      # ring count (TUBE)
        self.fit = None                     # point indices (RIGID)
        self.base = None                    # those points of the part's own mesh
        self.move = np.eye(4)               # RIGID at the frame shown
        self.look = None
        self.pay0 = 0.0
        self.frames: list = []              # per frame: TUBE (points (R, 3), n0, s0, pay); RIGID move; SPOOL (lo, hi, n0)
        self.held = 0                       # frames whose drawing did not fit (count changed …): the one before kept
        self.reach = 1.0                    # how far the part reaches from its origin (thinning a turn)
        self.spool_path = None              # SPOOL: (points (n, 3), s (n,)) the whole wound path
        self.wound = 0.0


class Drawn:
    """The drawn objects among ``obs`` (parts and spool objects), sorted at the frame shown."""

    def __init__(self, scene, obs: list):
        self.scene = scene
        self.items: dict = {}
        self.copies: list = []
        self.notes: list = []
        dg = bpy.context.evaluated_depsgraph_get()
        later = []
        for ob in obs:
            if not is_drawn(ob):
                continue
            try:
                shown = bool(ob.visible_get())
            except RuntimeError:
                shown = False
            if not shown:
                later.append(ob)               # shown later by the animation: sorted at a frame it is shown
                continue
            self.items[ob.name] = self._sort(ob, dg)
        if later:
            self._sort_later(later)

    # -- sorting
    def _copy(self, ob, dg):
        ev = ob.evaluated_get(dg)
        me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
        me.name = COPY
        self.copies.append(me)
        return me

    def _sort(self, ob, dg) -> Item:
        mod, _kind, _tag = _spool_mod()
        ev = ob.evaluated_get(dg)
        me = ev.data
        n = len(me.vertices) if me is not None else 0
        if n == 0:
            return Item(ob, HIDDEN)
        if ob.modifiers.get(mod) is not None:
            it = self._spool(ob, ev, dg)
            if it is not None:
                return it
        own = ob.data
        if own is not None and len(own.vertices) == n:
            base = _vertices(own).astype(np.float64)
            co = _vertices(me).astype(np.float64)
            idx = T.spread(base)
            m, _left = T.fit_rigid(base[idx], co[idx])
            size = float(np.linalg.norm(base.max(axis=0) - base.min(axis=0))) or 1.0
            moved = base @ m[:3, :3].T + m[:3, 3]
            if np.abs(moved - co).max() <= T.RIGID_TOL * max(size, 1.0):
                it = Item(ob, RIGID)
                it.fit, it.base, it.move = idx, base[idx], m
                it.reach = float(np.linalg.norm(base, axis=1).max()) * _scale(ob)
                return it
        rings = T.find_rings(_vertices(me))
        if rings is not None:
            c, first, rad, sides = rings
            it = Item(ob, TUBE)
            it.sides, it.radius, it.count = sides, rad, len(c)
            it.look = look_of(ob)
            it.mesh = self._copy(ob, dg)
            it.pay0 = _pay(ev)
            return it
        it = Item(ob, SHAPE)
        it.mesh = self._copy(ob, dg)
        return it

    def _spool(self, ob, ev, dg):
        mod, _kind, _tag = _spool_mod()
        m = ob.modifiers.get(mod)
        shapes = None
        try:
            for item in m.node_group.interface.items_tree:
                if getattr(item, "in_out", "") == "INPUT" and item.name == "Shapes":
                    shapes = getattr(m.properties.inputs, item.identifier).value
                    break
        except (AttributeError, KeyError, TypeError):
            shapes = None
        me = ev.data
        L = _attr(me, "fr_L")
        cab = _attr(me, cable_looks.ATTR, "VEC")
        rings = T.find_rings(_vertices(me))
        if shapes is None or shapes.data is None or L is None or cab is None or rings is None:
            return None
        sm = shapes.data
        pts = _vertices(sm).astype(np.float64)
        Ls = _attr(sm, "fr_L")
        if Ls is None or len(pts) < 2:
            return None
        c, first, rad, sides = rings
        it = Item(ob, SPOOL)
        it.sides, it.radius, it.count = sides, rad, len(c)
        it.wound = float(L[0] - cab[0, 2])           # s = L - wound
        it.spool_path = (pts, Ls.astype(np.float64) - it.wound)
        it.look = look_of(ob)
        it.mesh = self._copy(ob, dg)
        it.pay0 = _pay(ev)
        return it

    def _sort_later(self, obs: list) -> None:
        """Objects hidden at the frame shown: sorted at the first frame the animation shows them."""
        from . import web3d
        sc = self.scene
        first = {}
        for ob in obs:
            fc = web3d.visibility_curve(ob)
            if fc is None:
                continue
            for f in range(sc.frame_start, sc.frame_end + 1):
                if web3d.shown_at(fc, f):
                    first.setdefault(f, []).append(ob)
                    break
        if not first:
            return
        keep = sc.frame_current
        try:
            for f in sorted(first):
                sc.frame_set(f)
                dg = bpy.context.evaluated_depsgraph_get()
                for ob in first[f]:
                    self.items[ob.name] = self._sort(ob, dg)
        finally:
            sc.frame_set(keep)

    # -- per frame
    def read(self, dg, shown: dict) -> None:
        """Read every item at the frame now set; ``shown`` {name: bool}: an object hidden now keeps its last."""
        for name, it in self.items.items():
            if it.kind in (HIDDEN, SHAPE):
                continue
            if not shown.get(name, True):
                it.frames.append(it.frames[-1] if it.frames else None)
                continue
            ev = it.ob.evaluated_get(dg)
            me = ev.data
            got = None
            try:
                if it.kind == RIGID:              # its 4 points; the moves are fitted all at once (``moves``)
                    got = np.array([tuple(me.vertices[int(i)].co) for i in it.fit], np.float32)
                elif it.kind == TUBE:
                    got = self._tube_now(it, ev, me)
                elif it.kind == SPOOL:
                    got = self._spool_now(it, ev, me)
            except (IndexError, ValueError, AttributeError):
                got = None
            if got is None:
                it.held += 1
                got = it.frames[-1] if it.frames else None
            it.frames.append(got)

    def _tube_now(self, it: Item, ev, me):
        co = _vertices(me)
        if len(co) != it.count * it.sides:
            return None
        r = co.reshape(it.count, it.sides, 3).astype(np.float64)
        c = r.mean(axis=1)
        nr = r[:, 0] - c
        nr /= np.maximum(np.linalg.norm(nr, axis=1), 1e-300)[:, None]
        cab = _attr(me, cable_looks.ATTR, "VEC")
        s = cab.reshape(it.count, it.sides, 3)[:, 0, 2].copy() if cab is not None else np.zeros(it.count, np.float32)
        return (c.astype(np.float32), nr[0].copy(), s, _pay(ev), T.oct_encode(nr))

    def _spool_now(self, it: Item, ev, me):
        L = _attr(me, "fr_L")
        if L is None or len(L) < 2 * it.sides:
            return None
        co = np.array([tuple(me.vertices[k].co) for k in range(it.sides)], np.float64)
        c = co.mean(axis=0)
        n0 = co[0] - c
        n0 /= max(np.linalg.norm(n0), 1e-300)
        return (float(L[0]) - it.wound, float(L[-1]) - it.wound, n0, _pay(ev))

    def close(self) -> None:
        for me in self.copies:
            try:
                bpy.data.meshes.remove(me)
            except ReferenceError:
                pass
        self.copies = []


# ---------------------------------------------------------------------------
# what the export asks
# ---------------------------------------------------------------------------

def moves(it: Item) -> np.ndarray:
    """A RIGID item's move at every frame read (F, 4, 4), fitted from its 4 points."""
    pts = _filled(it.frames)
    if not pts or pts[0] is None:
        return np.tile(np.eye(4), (len(pts), 1, 1))
    return T.fit_rigid_many(it.base, np.stack(pts).astype(np.float64))


def _kind(self, ob) -> str:
    it = self.items.get(ob.name)
    return it.kind if it is not None else ""


def _mesh(self, ob):
    """The mesh the file shows for ``ob``: the evaluated copy of a tube, spool rope or shape, else its own."""
    it = self.items.get(ob.name)
    return it.mesh if it is not None and it.mesh is not None else ob.data


def _place(self, ob):
    """``ob``'s place for the file at the frame shown: a rigid item's own move on top of its world matrix."""
    from mathutils import Matrix
    it = self.items.get(ob.name)
    if it is not None and it.kind == RIGID:
        return ob.matrix_world @ Matrix([list(r) for r in it.move])
    return ob.matrix_world


def _counts(self) -> dict:
    out: dict = {}
    for it in self.items.values():
        out[it.kind] = out.get(it.kind, 0) + 1
    return out


Drawn.kind = _kind
Drawn.mesh = _mesh
Drawn.place = _place
Drawn.counts = _counts


def _filled(frames: list) -> list:
    """Frames read before the object was first shown take its first reading."""
    first = next((f for f in frames if f is not None), None)
    out, last = [], first
    for f in frames:
        last = f if f is not None else last
        out.append(last)
    return out


def tube_spec(gltf, it: Item, times) -> dict | None:
    """``extras.fr_tube`` of a TUBE or SPOOL item from its readings at ``times`` (s), its accessors written into
    ``gltf``. None when nothing was read, or a plain-looking tube that never moves (its evaluated mesh says it all)."""
    from ..core import web3d as core
    frames = _filled(it.frames)
    if not frames or frames[0] is None:
        return None
    times = np.asarray(times, np.float64)[:len(frames)]
    unit = _scale(it.ob)
    tol = T.POS_TOL / unit
    spec = {"v": T.VERSION, "sides": int(it.sides), "r": float(it.radius), "unit": unit}
    if it.look is not None:
        spec["look"] = it.look

    def acc(values, kind, ctype=core.FLOAT):
        return gltf.accessor(np.ascontiguousarray(values), kind, ctype)

    def channel(name, values, tol_, kind="SCALAR"):
        v = np.asarray(values, np.float64)
        keep = T.thin_frames(v.reshape(len(v), 1, -1), tol_, times) if len(v) > 1 else np.arange(1)
        if len(keep) == 1 or np.ptp(v, axis=0).max() <= 1e-9:
            spec[name] = [float(x) for x in np.atleast_1d(v[0])] if v.ndim > 1 else float(v[0])
            return
        spec[name + "_t"] = acc(times[keep].astype(np.float32), "SCALAR")
        spec[name] = acc(v[keep].astype(np.float32), kind)

    if it.kind == TUBE:
        pts = np.stack([f[0] for f in frames])                       # (F, n, 3) float32
        n0 = np.stack([f[1] for f in frames])
        sa = np.stack([f[2] for f in frames]).astype(np.float64)    # (F, n) the app's own lengths
        s0 = sa[:, 0]
        pay = np.array([f[3] for f in frames])
        still = (np.abs(pts - pts[:1]).max() <= 1e-7 and np.abs(n0 - n0[:1]).max() <= 1e-7
                 and np.abs(sa - sa[:1]).max() <= 1e-7)
        if it.look is None and still:
            return None
        # the length along the cable: s0 + chords, unless the app's own differs (a cable piled on the seabed)
        ch = np.concatenate([np.zeros((len(pts), 1)), np.cumsum(np.linalg.norm(np.diff(
            pts.astype(np.float64), axis=1), axis=2), axis=1)], axis=1) * unit
        own_s = it.look is not None and np.abs(sa - s0[:, None] - ch).max() > T.S_TOL
        del ch
        parts = [pts.astype(np.float64), (n0 * it.radius)[:, None],
                 np.c_[s0 / unit * (T.POS_TOL / T.S_TOL), np.zeros((len(s0), 2))][:, None]]
        if own_s:
            parts.append(np.stack([sa / unit * (T.POS_TOL / T.S_TOL), np.zeros_like(sa), np.zeros_like(sa)], axis=2))
        x = np.concatenate(parts, axis=1)
        del parts
        keep = T.thin_frames(x, tol, times) if len(frames) > 1 else np.arange(1)
        del x
        lo, step, slo, sstep, q = T.pack(pts[keep], sa[keep] if own_s else None)
        spec.update(n=int(pts.shape[1]), k=int(len(keep)))
        if len(keep) > 1:
            spec["times"] = acc(times[keep].astype(np.float32), "SCALAR")
            spec["step"] = acc(step, "SCALAR")
            # x, y, z (and s) as 16-bit numbers, moment after moment
            spec["q"] = gltf.accessor(q.reshape(-1, 4), "VEC4", core.USHORT, pack=True)
            spec["tmin"] = float(32.0 * float(step.max()))          # pieces shorter than that: looked past
        spec["lo"] = acc(lo, "VEC3")
        spec["n0"] = acc(n0[keep].astype(np.float32), "VEC3")
        spec["s0"] = acc(s0[keep].astype(np.float32), "SCALAR")
        if own_s:
            spec["slo"] = acc(slo, "SCALAR")
            if len(keep) > 1:
                spec["sstep"] = acc(sstep, "SCALAR")
        # the ring's turn: carried along by the page from the first one, unless that is more than TURN_TOL off
        # somewhere (a line with pieces shorter than its 16-bit points can carry the direction of: a cable piled on
        # the seabed); it only turns the looks' pattern round the cable
        back = T.unpack(lo, step, q, len(keep))
        tmin = float(spec.get("tmin", 0.0))
        tg = np.stack([T.tangents(b, tmin) for b in back])
        carried = T.transport_many(tg, n0[keep])
        own = T.oct_decode(np.stack([frames[i][4] for i in keep]))
        own -= tg * (own * tg).sum(axis=2, keepdims=True)
        own /= np.maximum(np.linalg.norm(own, axis=2, keepdims=True), 1e-300)
        off = float(np.linalg.norm(carried - own, axis=2).max())
        if off > T.TURN_TOL and it.look is not None:
            spec["nq"] = gltf.accessor(np.ascontiguousarray(np.stack([frames[i][4] for i in keep])).reshape(-1, 2),
                                       "VEC2", core.SHORT, pack=True)
        channel("pay", pay, T.S_TOL)
        return spec
    # SPOOL: the whole wound path once, its cut per frame
    pts, s = it.spool_path
    spec.update(n=int(len(pts)), k=1, spool=True)
    spec["lo"] = acc(pts.astype(np.float32), "VEC3")
    spec["s"] = acc(s.astype(np.float32), "SCALAR")
    spec["n0"] = acc(np.asarray(frames[0][2], np.float32)[None], "VEC3")
    spec["s0"] = acc(np.array([s[0]], np.float32), "SCALAR")
    trim = np.array([[f[0], f[1]] for f in frames], np.float64)
    tn0 = np.array([f[2] for f in frames], np.float64)
    x = np.concatenate([trim[:, :, None] / unit * np.array([1.0, 0.0, 0.0]) * (T.POS_TOL / T.S_TOL),
                        (tn0 * it.radius)[:, None]], axis=1)
    keep = T.thin_frames(x, tol, times) if len(frames) > 1 else np.arange(1)
    if len(keep) > 1:
        spec["trim_t"] = acc(times[keep].astype(np.float32), "SCALAR")
    spec["trim"] = acc(trim[keep].astype(np.float32), "VEC2")
    spec["trim_n0"] = acc(tn0[keep].astype(np.float32), "VEC3")
    channel("pay", np.array([f[3] for f in frames]), T.S_TOL)
    return spec
