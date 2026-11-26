"""Welds from the CAD file (task 0323): solid weld beads in a STEP found, split per weld and measured. No Blender.

**What CAD programs put in a STEP** (study of the brief, Autodesk's forum and help, PTC's help): Inventor's solid welds
(fillet, groove) are an assembly feature – a STEP export gives ALL beads of a weldment as one part / one body (several
solids); its cosmetic welds are graphics only and are not in the file. SolidWorks' weld beads are graphics (not in the
file). Creo 8+ exports each solid weld as a body of its own. Fusion and others: a bead, if any, is a body the user drew.

**Finding** (``find``): a *body* is a part the importer made – its mesh in world metres with the CAD face of every
triangle. A body named like welds (``weld_name``: Welds, Weld bead 3, Fillet weld, Lasnaad, Schweißnaht, Soudure …, never
Weld nut / Weldment / Welded frame) is split into its connected pieces (``components``); each piece is a bead. A body
with another name is a bead only by its shape (``maybe_bead`` first: thin for its surface; then the full check below),
said as "found by their shape – check them".

**Measuring one bead** (``_measure``):
1. *Contact*: the bead's CAD faces lying on another part (centre within ``CONTACT`` of its surface, facing it) – the
   parts it joins, most contact first. Two parts: a weld between them; one or three: kept, "joins N parts".
2. *Seams*: 0319's seam finder (``welds.find_seams``) between the two parts, with the faces the bead touches picked –
   so a fillet, an all-round ring, a bead round a square post's corners and a V-groove's root are found exactly as a
   weld placed in the app – then cut to where the bead lies on the line (``_trim``: the root lies on the bead).
3. *Kind*: fillet in a corner; a groove (butt) where the bead fills the corner faces up to their ends (``_ends``): its
   line goes up to the plates' faces, where 0319's butt weld lies (``_to_top``). No seam (a bead on one part, a shape
   the finder does not know): OTHER, kept with its own shape only.
4. *Size* (``_section``): in planes square to the seam, the legs z1 / z2 (how far the bead lies on each face from the
   root) and the throat a = min(z1, z2)·cos(θ/2), or the depth along the corner's middle when the bead is concave
   (ISO 2553: the largest isosceles triangle inside); rounded to 0.5 mm. A groove: the cap's width. Unequal legs are
   said ("legs 10 × 6").
5. *Intermittent*: pieces of one pair on one seam, of like length and spacing – one weld "n × l (e)" (``_merge``).
6. *Shape check* for beads found by their shape only: two parts, a seam, the bead lying along it (``ALONG``), small
   legs, and a section no fuller than a triangle (``FILL``: a square bar in a corner is twice a triangle).

**UVs** (``uvs``): per triangle corner u = metres along the seam, v = 0 at the toe on the first part … 1 at the toe on
the second – what 0319's bead materials read (ripples along u, the tint across v).
"""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np

from . import welds as core

CONTACT = 0.0003          # m: a bead face this close to a part lies on it (both meshes are faceted)
FACING = -0.7             # a bead face lies on a part only when it faces it (normals opposed)
MIN_CONTACT = 0.03        # share of the bead's surface on a part that counts as joining it (or MIN_AREA)
MIN_AREA = 4e-6           # m² (4 mm²)
COVER = 0.0006            # m: a seam point this close to the bead lies under it
LEG_MAX = 0.040           # m: a leg longer than this is no weld bead (by shape)
LEG_MIN = 0.0008          # m
FILL = 1.5                # section area / triangle of the legs: a fillet ~1.0–1.2, a square bar 2.0
FILL_GROOVE = 1.8         # … a groove: its V and its cap (the test groove 1.3; a flat strip in a corner 2.5)
MAX_FACES = 40            # by shape: a bead has few CAD faces (a fillet 5, a ring 4, round a square post 10)
SLENDER = 5.0             # by shape: a bead is at least this many times as long as its section is wide
SHAPE_BUDGET = 10.0       # s: at an import the search by shape stops after this (Find in CAD file: no limit)
LEGS_RATIO = 3.0          # by shape: legs more unequal than this are no weld (a strip 3 x 40 lying in a corner)
GAP_MAX = 0.008           # m: a square groove's root gap at most (task 0368; the plates' ends face each other)
GAP_CAP = (0.0002, 0.006)  # m: by shape, a square groove's cap stands this much over the plates (a flush bar: no weld)
ALONG = 0.6               # the seam under a bead (found by shape) covers this share of the bead's length at least
THIN = 0.006              # m: 2·volume / surface of a bead is ~z/3.4 (z: its legs) – a body thicker than this is no bead
#                            by shape (a plate: its thickness)
SAMPLES = 7               # sections per seam for the size
REGULAR = 0.15            # intermittent: piece lengths and gaps within 15 % of each other

KINDS = ("FILLET", "BUTT", "OTHER")

# ---------------------------------------------------------------------------
# names
# ---------------------------------------------------------------------------

_WELD_WORDS = {
    "WELD", "WELDS", "WELDBEAD", "WELDBEADS", "BEAD", "BEADS", "WELDSEAM", "WELDSEAMS", "LASNAAD", "LASNADEN",
    "SCHWEISSNAHT", "SCHWEISSNAEHTE", "SCHWEISSNAHTE", "SCHWEISSRAUPE", "SOUDURE", "SOUDURES", "CORDON",
    "SALDATURA", "SALDATURE", "SOLDADURA", "SOLDADURAS", "SVETS", "SVETSFOG", "SPAWANIE", "SPOINA",
}
# a bead word with one of these is a part made for welding, not a bead
_NOT_WORDS = {
    "NUT", "NUTS", "STUD", "STUDS", "BOLT", "BOLTS", "SCREW", "PIN", "NECK", "FLANGE", "PLATE", "PLATES", "ON",
    "HINGE", "HINGES", "WASHER", "BOSS", "SOCKET", "ELBOW", "TEE", "CAP", "TABLE", "FIXTURE", "JIG", "TORCH", "GUN",
    "WIRE", "HELMET", "MACHINE", "ROBOT", "CELL", "MUTTER", "MOER", "MOEREN", "BOUT", "BOLZEN", "MUTTERN", "ECROU",
    "GOUJON", "TAP", "SLEEVE", "NIPPLE", "BUSH", "BUSHING", "LUG", "LUGS", "BRACKET", "CLIP", "CLIPS",
}
_COMPOUNDS = ("SCHWEISSNAHT", "SCHWEISSNAEHT", "SCHWEISSRAUPE", "LASNAAD", "LASNADEN")


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", (name or "").upper().replace("ß", "SS").replace("Ä", "AE")
                              .replace("Ö", "OE").replace("Ü", "UE"))
    return "".join(c for c in s if not unicodedata.combining(c))


def weld_name(name: str) -> bool:
    """Is this a name CAD programs give solid welds? "Welds", "Weld Bead 3", "WELD_1", "Fillet Weld 2", "Groove weld",
    "Lasnaad", "Schweißnaht 2", "Soudure" – not "Weld nut M8", "Weldment1", "Welded frame", "Weld-on hinge"."""
    s = _norm(name)
    words = re.findall(r"[A-Z]+", s)
    if not words:
        return False
    if any(w in _NOT_WORDS for w in words):
        return False
    if any(w in _WELD_WORDS for w in words):
        if "BEAD" in words or "BEADS" in words:
            return "WELD" in words or "WELDS" in words
        return True
    return any(w.endswith(c) or w.startswith(c) for w in words for c in _COMPOUNDS)


# ---------------------------------------------------------------------------
# a mesh as the finder sees it
# ---------------------------------------------------------------------------

@dataclass
class Mesh:
    """One part from the importer: ``points`` (n, 3) world metres, ``tris`` (m, 3), ``face`` (m) the CAD face of each
    triangle (None: one face each). ``material``: its CAD material name ('' when none)."""
    key: str
    name: str
    points: np.ndarray
    tris: np.ndarray
    face: np.ndarray | None = None
    material: str = ""
    _side: object = field(default=None, repr=False)

    def __post_init__(self):
        self.points = np.asarray(self.points, np.float64).reshape(-1, 3)
        self.tris = np.asarray(self.tris, np.int64).reshape(-1, 3)
        if self.face is None:
            self.face = np.arange(len(self.tris))
        self.face = np.asarray(self.face, np.int64).reshape(-1)

    @property
    def lo(self):
        if getattr(self, "_lo", None) is None:
            self._lo = self.points.min(0) if len(self.points) else np.zeros(3)
        return self._lo

    @property
    def hi(self):
        if getattr(self, "_hi", None) is None:
            self._hi = self.points.max(0) if len(self.points) else np.zeros(3)
        return self._hi

    def side(self) -> core.Side:
        if self._side is None:
            self._side = core.Side(self.points, self.tris, self.face).prepare()
        return self._side


def components(points: np.ndarray, tris: np.ndarray, tol: float = 1e-5) -> list[np.ndarray]:
    """The connected pieces of a mesh (triangles sharing a point, points welded by place – the importer gives every CAD
    face its own points): a list of triangle-number arrays, biggest first."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    tris = np.asarray(tris, np.int64).reshape(-1, 3)
    if not len(tris):
        return []
    key = np.round(pts / tol).astype(np.int64)
    _u, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    parent = np.arange(len(_u))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    wt = inv[tris]
    for a, b in np.concatenate([wt[:, [0, 1]], wt[:, [1, 2]]]):
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[ra] = rb
    roots = np.array([root(i) for i in range(len(parent))])
    lab = roots[wt[:, 0]]
    out = [np.flatnonzero(lab == r) for r in np.unique(lab)]
    out.sort(key=lambda a: -len(a))
    return out


def _tri_geom(points, tris):
    v = points[tris]
    cr = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    area2 = np.linalg.norm(cr, axis=1)
    n = cr / np.maximum(area2, 1e-18)[:, None]
    return v, n, 0.5 * area2


def volume(points, tris) -> float:
    v = np.asarray(points, np.float64)[np.asarray(tris, np.int64)]
    c = v.reshape(-1, 3).mean(0)
    w = v - c
    return abs(float(np.einsum("ij,ij->i", w[:, 0], np.cross(w[:, 1], w[:, 2])).sum()) / 6.0)


_PART_WORDS = {
    "SCREW", "SCREWS", "BOLT", "BOLTS", "NUT", "NUTS", "WASHER", "WASHERS", "PIN", "PINS", "RIVET", "STUD", "KEY",
    "SPRING", "BEARING", "GEAR", "PULLEY", "CLIP", "SPACER", "BUSH", "BUSHING", "SHAFT", "AXLE", "SEAL", "ORING",
    "GASKET", "MAGNET", "SENSOR", "MOTOR", "CABLE", "HOSE", "BELT", "CHAIN", "INSERT", "SCHRAUBE", "MUTTER", "SCHEIBE",
    "STIFT", "BOUT", "MOER", "RING", "SLEEVE", "DOWEL", "THREAD", "PLUG", "CAP", "TUBE", "PIPE", "ROD", "BAR",
}


def known_part(name: str) -> bool:
    """A part the library knows by its name (a screw, a washer, a bearing, a plate …), or one named with a plain part
    word ("Screw010"): never a bead by its shape."""
    words = set(re.findall(r"[A-Z]+", _norm(name)))
    if words & _PART_WORDS:
        return True
    try:
        from . import fasteners, part_types
        if fasteners.parse(name) is not None:
            return True
        t = part_types.own_type(name)
        return t is not None and t != "weld_bead"
    except Exception:  # noqa: BLE001
        return False


def maybe_bead(mesh: Mesh) -> bool:
    """A quick look before the full check (a body found by its shape only): no part the library knows by its name, thin
    for its surface – 2·volume / surface is ~z / 3.4 for a fillet of legs z (a plate: its thickness) – and long for its
    section (``SLENDER``: a washer or a short pin is not)."""
    if len(mesh.tris) < 4 or len(mesh.tris) > 20000:
        return False
    if known_part(mesh.name):
        return False
    if len(np.unique(mesh.face)) > MAX_FACES:
        return False                                      # (a printed shell, a casting: hundreds of faces)
    _v, _n, ar = _tri_geom(mesh.points, mesh.tris)
    A = float(ar.sum())
    if A <= 0:
        return False
    vol = volume(mesh.points, mesh.tris)
    if 2.0 * vol / A > THIN:
        return False
    # a small section for its length (the legs' triangle at most LEG_MAX² / 2): a sheet-metal plate is not
    ext = _extent(mesh.points)
    if ext <= 0 or vol / ext > 0.5 * LEG_MAX ** 2:
        return False
    return ext >= SLENDER * math.sqrt(max(vol / ext, 1e-12))


# ---------------------------------------------------------------------------
# what was found
# ---------------------------------------------------------------------------

@dataclass(eq=False)
class Found:
    body: str                              # the source body's key
    tris: np.ndarray                       # its triangles in this weld (all pieces of an intermittent one)
    parts: list                            # keys of the parts it lies on, most contact first
    part_a: str | None = None
    part_b: str | None = None
    kind: str = "OTHER"
    how: str = "name"                      # "name" / "shape"
    seams: list = field(default_factory=list)      # welds.Seam, world metres
    size: float = 0.0                      # m: fillet throat a / groove cap width
    legs: tuple = (0.0, 0.0)               # m: z on the first part, on the second
    length: float = 0.0                    # m: along the seams (an intermittent weld: its pieces only)
    closed: bool = False                   # all round (one closed seam or seams round in a loop)
    intermittent: tuple | None = None      # (n, piece m, pitch m)
    note: str = ""
    metal: str = ""                        # from the CAD material ('' : from the parts)
    pieces: int = 1
    gap: float = 0.0                       # m: a square groove's root gap (task 0368)

    @property
    def joins(self) -> int:
        return len(self.parts)


def metal_of_material(name: str) -> str:
    """STEEL / STAINLESS / ALUMINIUM from a CAD material name ("Welded Steel Mild", "Welded Aluminum-6061",
    "Welded Stainless Steel", "1.4301", "AlMg3"); '' when it names no metal."""
    s = _norm(name)
    if not s.strip():
        return ""
    if "STAINLESS" in s or "INOX" in s or "RVS" in s.split() or "EDELSTAHL" in s or re.search(r"\b1\.4\d{3}\b", s) \
            or re.search(r"\b3[01]\dL?\b", s):
        return "STAINLESS"
    if "ALUMIN" in s or re.search(r"\bALMG|\bALSI|\b[56]0[0-9]{2}\b", s):
        return "ALUMINIUM"
    if "STEEL" in s or "STAAL" in s or "STAHL" in s or "ACIER" in s or re.search(r"\bS[23][3-5]5", s) or "IRON" in s:
        return "STEEL"
    return ""


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def _slice(v: np.ndarray, p, t) -> np.ndarray:
    """Points where the triangles (k, 3, 3) cross the plane through p square to t: (j, 3)."""
    if not len(v):
        return np.zeros((0, 3))
    h = (v - p) @ t
    out = []
    for i, j in ((0, 1), (1, 2), (2, 0)):
        a, b = h[:, i], h[:, j]
        m = (a * b < 0)
        if m.any():
            f = a[m] / (a[m] - b[m])
            out.append(v[m, i] + (v[m, j] - v[m, i]) * f[:, None])
        on = np.abs(a) < 1e-12
        if on.any():
            out.append(v[on, i])
    return np.concatenate(out) if out else np.zeros((0, 3))


def _segments(v: np.ndarray, p, t) -> np.ndarray:
    """The plane's cut through each triangle crossing it as a segment (j, 2, 3)."""
    if not len(v):
        return np.zeros((0, 2, 3))
    h = (v - p) @ t
    segs = []
    for k in range(len(v)):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            a, b = h[k, i], h[k, j]
            if abs(a) < 1e-12:
                pts.append(v[k, i])
            elif a * b < 0:
                pts.append(v[k, i] + (v[k, j] - v[k, i]) * (a / (a - b)))
        if len(pts) >= 2:
            segs.append((pts[0], pts[1]))
    return np.array(segs).reshape(-1, 2, 3)


def _arc(points: np.ndarray, closed: bool) -> np.ndarray:
    pts = np.concatenate([points, points[:1]]) if closed and len(points) > 2 else points
    return np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))])


def _resample(seam: core.Seam, step: float = 0.001):
    """(arc lengths, points) every ``step`` along a seam (its own points kept)."""
    pts = np.concatenate([seam.points, seam.points[:1]]) if seam.closed and len(seam.points) > 2 else seam.points
    L = _arc(seam.points, seam.closed)
    s = np.unique(np.concatenate([np.arange(0.0, L[-1], step), L]))
    out = np.empty((len(s), 3))
    for d in range(3):
        out[:, d] = np.interp(s, L, pts[:, d])
    return s, out


def _point_at(seam: core.Seam, s: float):
    pts = np.concatenate([seam.points, seam.points[:1]]) if seam.closed and len(seam.points) > 2 else seam.points
    cs = seam.corners + seam.corners[:1] if seam.closed and len(seam.points) > 2 else seam.corners
    L = _arc(seam.points, seam.closed)
    i = int(np.clip(np.searchsorted(L, s, side="right") - 1, 0, len(L) - 2))
    f = (s - L[i]) / max(L[i + 1] - L[i], 1e-12)
    f = min(max(f, 0.0), 1.0)
    p = pts[i] + (pts[i + 1] - pts[i]) * f
    t = core.unit(pts[i + 1] - pts[i])
    return p, t, core._interp_corner(cs[i], cs[i + 1], f)


def _cut(seam: core.Seam, s0: float, s1: float) -> core.Seam:
    """The piece of a seam from arc length s0 to s1 (an open seam; s0 > s1 on a closed one goes round its start)."""
    L = _arc(seam.points, seam.closed)[-1]
    if seam.closed and s1 < s0:
        rot = _cut(seam, s0, L)
        rest = _cut(seam, 0.0, s1)
        pts = np.concatenate([rot.points, rest.points[1:]])
        return core.Seam(pts, rot.corners + rest.corners[1:], False, seam.kind)
    pts, cs = core._cut_piece(seam.points, list(seam.corners), seam.closed, max(0.0, s0), min(L, s1))
    return core.Seam(pts, cs, False, seam.kind)


# ---------------------------------------------------------------------------
# finding
# ---------------------------------------------------------------------------

_BARY = np.array([[1 / 3, 1 / 3, 1 / 3], [2 / 3, 1 / 6, 1 / 6], [1 / 6, 2 / 3, 1 / 6], [1 / 6, 1 / 6, 2 / 3],
                  [0.45, 0.45, 0.1], [0.1, 0.45, 0.45], [0.45, 0.1, 0.45]])


def _nearest(side, pts, order):
    """``Side.nearest_local`` for points taken in ``order`` (near ones together: small boxes, few triangles each)."""
    d, _q, t = side.nearest_local(pts[order], CONTACT + 0.001)
    dd, tt = np.empty_like(d), np.empty_like(t)
    dd[order], tt[order] = d, t
    return dd, tt


def _touches(body: Mesh, parts: list, n: int = 96) -> int:
    """How many parts a body lies on, from the centres of some of its triangles (a quick look before the full
    ``_contacts``)."""
    v, nrm, ar = _tri_geom(body.points, body.tris)
    # the biggest triangles and some of every face (a ring's face on its tube is many thin triangles)
    pick = np.unique(np.concatenate([np.argsort(-ar)[:n // 2], np.linspace(0, len(ar) - 1, n).astype(int)]))
    cen, nn = v[pick].mean(1), nrm[pick]
    lo, hi = body.lo - 0.002, body.hi + 0.002
    hits = 0
    for p in parts:
        if np.any(p.lo > hi) or np.any(p.hi < lo):
            continue
        side = p.side()
        side.restrict(lo, hi)
        try:
            d, _q, t = side.nearest_local(cen, CONTACT + 0.001)
        finally:
            side.restrict()
        ok = (t >= 0) & (d <= CONTACT)
        if ok.any() and ((nn[ok] * side.n[t[ok]]).sum(1) <= FACING).any():
            hits += 1
            if hits >= 2:
                break
    return hits


def _contacts(bead: Mesh, tri_idx: np.ndarray, parts: list) -> dict:
    """{part key: (area m², bead triangles on it, part CAD faces touched)} of one bead piece. A big bead triangle is
    looked at in 7 points (it may lie on two parts, or reach past a part's end), a small one (≤ 5 mm) at its centre."""
    v, n, ar = _tri_geom(bead.points, bead.tris[tri_idx])
    edge = np.max(np.linalg.norm(v - np.roll(v, 1, axis=1), axis=2), axis=1)
    big = edge > 0.005
    k = len(_BARY)
    many = np.einsum("sk,tkj->tsj", _BARY, v[big]).reshape(-1, 3)
    pts = np.concatenate([many, v[~big].mean(1)])
    owner = np.concatenate([np.repeat(np.flatnonzero(big), k), np.flatnonzero(~big)])
    weight = np.concatenate([np.full(int(big.sum()) * k, 1.0 / k), np.ones(int((~big).sum()))])
    nn = n[owner]
    lo, hi = v.reshape(-1, 3).min(0) - 0.002, v.reshape(-1, 3).max(0) + 0.002
    g = np.floor(pts / 0.004).astype(np.int64)            # the points in little boxes, near ones together
    order = np.lexsort((g[:, 0], g[:, 1], g[:, 2]))
    out = {}
    taken = np.zeros(len(pts), bool)
    for p in parts:
        if np.any(p.lo > hi) or np.any(p.hi < lo):
            continue
        side = p.side()
        side.restrict(lo, hi)                             # only its triangles where the bead is
        try:
            d, t = _nearest(side, pts, order)
        finally:
            side.restrict()
        hit = (t >= 0) & (d <= CONTACT) & ~taken
        if not hit.any():
            continue
        hit[hit] = (nn[hit] * side.n[t[hit]]).sum(1) <= FACING
        if not hit.any():
            continue
        taken |= hit
        share = np.bincount(owner[hit], weights=weight[hit], minlength=len(tri_idx))
        on = share > 0
        out[p.key] = (float((ar * share).sum()), tri_idx[on], set(int(x) for x in side.face[t[hit]]))
    return out


def _trim(seam: core.Seam, piece: core.Side, closed_ok: bool = True) -> list:
    """The pieces of ``seam`` lying under the bead ``piece``: [(s0, s1)] in metres along it (the whole seam: [(0, L)]
    and closed kept)."""
    s, pts = _resample(seam)
    d, _q, _t = piece.nearest_local(pts, COVER + 0.001)
    on = d <= COVER
    L = s[-1]
    if not on.any():
        return []
    if on.all():
        return [(0.0, L)]
    runs = []
    i = 0
    n = len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            runs.append([i, j])
            i = j + 1
        else:
            i += 1

    # the ends: where the line leaves the bead (a little over how far the line lies off the bead inside it – both
    # are faceted – never the whole COVER, or every piece came out 2 x COVER long)
    end_tol = min(COVER, float(np.median(d[on])) + 0.00005)

    def edge(s_on, s_off):
        for _ in range(14):
            sm = 0.5 * (s_on + s_off)
            p, _t2, _c = _point_at(seam, sm)
            dm, _q2, _t3 = piece.nearest_local(p[None], COVER + 0.001)
            if dm[0] <= end_tol:
                s_on = sm
            else:
                s_off = sm
        return s_on
    out = []
    for a, b in runs:
        s0 = s[a] if a == 0 else edge(s[a], s[a - 1])
        s1 = s[b] if b == n - 1 else edge(s[b], s[b + 1])
        out.append([s0, s1])
    if seam.closed and len(out) > 1 and out[0][0] <= 1e-9 and out[-1][1] >= L - 1e-9:
        first = out.pop(0)
        out[-1][1] = first[1]                    # round the start: s1 < s0
    return [(a, b) for a, b in out if ((b - a) if b >= a else (L - a + b)) >= core.MIN_LEN]


def _section(bead_v, contact_a, contact_b, free, p, t, c: core.Corner, reach: float):
    """(z on A, z on B, depth along the middle) of the bead at p, from the bead's triangles on A, on B and free."""
    def pts_of(v):
        q = _slice(v, p, t)
        if not len(q):
            return q
        w = q - p
        keep = (np.linalg.norm(w, axis=1) <= reach) & (w @ c.na >= -0.0005) & (w @ c.nb >= -0.0005)
        return q[keep]
    qa, qb = pts_of(bead_v[contact_a]), pts_of(bead_v[contact_b])
    tol_a = 0.0003
    za = max([float((q - p) @ c.da) for q in qa if abs(float((q - p) @ c.na)) <= tol_a] or [0.0])
    zb = max([float((q - p) @ c.db) for q in qb if abs(float((q - p) @ c.nb)) <= tol_a] or [0.0])
    m = c.mid
    depth = math.inf
    segs = _segments(bead_v[free], p, t)
    for a, b in segs:
        if np.linalg.norm(a - p) > reach and np.linalg.norm(b - p) > reach:
            continue
        # ray p + s m against segment a + u (b - a), in the plane
        e = b - a
        M = np.array([[m @ m, -(m @ e)], [m @ e, -(e @ e)]])
        rhs = np.array([(a - p) @ m, (a - p) @ e])
        try:
            s_, u_ = np.linalg.solve(M, rhs)
        except np.linalg.LinAlgError:
            continue
        if s_ > 0 and -1e-6 <= u_ <= 1 + 1e-6:
            gap = np.linalg.norm(p + m * s_ - (a + e * u_))
            if gap < 0.0005:
                depth = min(depth, float(s_))
    return za, zb, depth


def _ends(side: core.Side, root, d, n, z) -> bool:
    """Does the part's face stop at the toe (a groove's bevel, covered to its end)? Looked for 1 mm past the toe."""
    q = np.asarray(root) + d * (z + 0.001) - n * 0.00005
    dd, _q, _t = side.nearest_local(q[None], 0.002)
    return bool(dd[0] > 0.0003)


def _to_top(seam: core.Seam, depth: float, width: float) -> core.Seam:
    """A groove's seam moved from its root up to the plates' faces, where 0319's butt weld lies: the corners there flat
    (180°), the toes ``width`` / 2 to each side."""
    pts, cs = [], []
    for p, c in zip(seam.points, seam.corners):
        u = core.unit(c.da + c.db)
        top = p + u * depth
        da = core.unit(c.da - u * float(c.da @ u))
        db = core.unit(c.db - u * float(c.db @ u))
        oa = top + da * 0.0
        ob = top + db * 0.0
        pts.append(top)
        cs.append(core.Corner("BUTT", 180.0, oa, da, u.copy(), c.ta, ob, db, u.copy(), c.tb))
    return core.Seam(np.array(pts), cs, seam.closed, "BUTT")


def _half(x: float) -> float:
    """m -> m rounded to 0.5 mm."""
    return round(x * 2000.0) / 2000.0


STOPPED = [False]          # the last ``find`` stopped its search by shape at SHAPE_BUDGET


def find(bodies: list, parts: list, named: set | None = None, progress=None,
         budget: float | None = SHAPE_BUDGET, pool=None) -> list[Found]:
    """The welds in ``bodies`` (Mesh): those whose key is in ``named`` are welds by their name (every piece a bead),
    the others only by their shape – looked at for ``budget`` seconds at most (None: all; ``STOPPED`` says so).
    ``pool`` (``core.weld_pool.Pool``): the pieces' contacts and measures shared out over helper processes – the same
    welds (task 0368)."""
    import time
    named = set(named or ())
    STOPPED[0] = False
    found: list[Found] = []
    pending = []                                       # (body, piece triangles, contacts)
    t0 = time.perf_counter()
    bodies = sorted(bodies, key=lambda b: b.key not in named)     # the named ones first: never cut short
    if pool is not None:
        pool.share("parts", [_plain(p) for p in parts])
    first = [b for b in bodies if b.key in named]        # the named ones: all their pieces' contacts in one go
    if pool is not None and first:
        cut = {}
        for body in first:
            cut[body.key] = _pieces(body)
        pool.share("cbodies", {b.key: _plain(b) for b in first})
        jobs = [(b.key, piece) for b in first for piece in cut[b.key]]
        cons = iter(pool.map("weld_cad.job_contacts", jobs))
        for body in first:
            for piece in cut[body.key]:
                pending.append((body, piece, next(cons), True))
        bodies = [b for b in bodies if b.key not in named]
    for bi, body in enumerate(bodies):
        if budget is not None and body.key not in named and time.perf_counter() - t0 > budget:
            STOPPED[0] = True                          # the search by shape stopped (said in the import's message)
            break
        others = [p for p in parts if p.key != body.key]
        if body.key not in named and _touches(body, others) < 2:
            continue                                      # by shape: it must lie on two parts (a quick look first)
        pieces = _pieces(body)
        if pool is not None:                              # (a piece's contacts read only its own triangles)
            pool.share("cbodies", {body.key: _plain(body)})
            cons = pool.map("weld_cad.job_contacts", [(body.key, piece) for piece in pieces])
        else:
            cons = [_contacts(body, piece, others) for piece in pieces]
        for piece, con in zip(pieces, cons):
            pending.append((body, piece, con, body.key in named))
        if progress:
            progress(bi / max(1, len(bodies)) * 0.4)
    # pairs: the seams of a pair are found once, with the faces all its beads touch picked
    by_key = {p.key: p for p in parts}
    pairs: dict = {}
    for k, (body, piece, con, is_named) in enumerate(pending):
        _v, _n, ar = _tri_geom(body.points, body.tris[piece])
        total = float(ar.sum())
        on = sorted(((a, key) for key, (a, _t, _f) in con.items() if a >= max(MIN_AREA, MIN_CONTACT * total)
                     or (a >= MIN_AREA and is_named)), reverse=True)
        keys = [key for _a, key in on]
        if len(keys) >= 2:
            a, b = _order(by_key[keys[0]], by_key[keys[1]])
            pairs.setdefault((a.key, b.key), []).append(k)
        pending[k] = (body, piece, con, is_named, keys, total)
    if progress:
        progress(0.7)
    if pool is not None:
        # one job per pair of parts (its seams are found once) and one per piece on no pair
        groups = [(pair, ks) for pair, ks in pairs.items()]
        in_pair = {k for _pair, ks in groups for k in ks}
        groups += [(None, [k]) for k in range(len(pending)) if k not in in_pair]
        bodies_by = {}
        for body, *_rest in pending:
            bodies_by.setdefault(body.key, body)
        pool.share("bodies", {key: _plain(b) for key, b in bodies_by.items()})
        jobs = [(pair, [(k, pending[k][0].key, pending[k][1], pending[k][2], pending[k][3], pending[k][4],
                         pending[k][5]) for k in ks]) for pair, ks in groups]
        results = [None] * len(pending)
        for got in pool.map("weld_cad.job_measure", jobs):
            for k, f in got:
                results[k] = f
    else:
        seams_of = _Pairs(pairs, pending, by_key)
        results = [_measure(body, piece, con, keys, is_named, by_key, seams_of)
                   for body, piece, con, is_named, keys, _total in pending]
    per_pair: dict = {}
    for f in results:
        if f is None:
            continue
        if f.part_a is not None and f.part_b is not None and f.seams:
            per_pair.setdefault((f.part_a, f.part_b), []).append(f)
        else:
            found.append(f)
    for pair, fs in per_pair.items():
        found.extend(_merge(fs))
    if progress:
        progress(1.0)
    return found


# ---- the jobs of the helper processes (task 0368, ``core/weld_pool.py``) -----------------------------------------

def _plain(m: Mesh) -> tuple:
    """A Mesh as plain data for a helper (its worked-out side stays here)."""
    return (m.key, m.name, m.points, m.tris, m.face, m.material)


def _shared_parts(shared: dict) -> list:
    if "_parts" not in shared or shared["_parts"][0] is not shared["parts"]:
        shared["_parts"] = (shared["parts"], [Mesh(*t) for t in shared["parts"]])
    return shared["_parts"][1]


def _shared_body(shared: dict, name: str = "body", key: str | None = None) -> Mesh:
    src = shared[name] if key is None else shared[name][key]
    cache = shared.setdefault("_bodies", {})
    if id(src) not in cache or cache[id(src)][0] is not src:
        cache[id(src)] = (src, Mesh(*src))
    return cache[id(src)][1]


def _pieces(body: Mesh) -> list:
    """The pieces of a body; an inside-out piece (a mirrored part) turned the right way (in ``body.tris``)."""
    pieces = components(body.points, body.tris)
    for piece in pieces:
        v = body.points[body.tris[piece]]
        c = v.reshape(-1, 3).mean(0)
        w = v - c
        if float(np.einsum("ij,ij->i", w[:, 0], np.cross(w[:, 1], w[:, 2])).sum()) < 0:
            body.tris = body.tris.copy()
            body.tris[piece] = body.tris[piece][:, ::-1]
    return pieces


def job_contacts(shared: dict, body_key: str, piece) -> dict:
    body = _shared_body(shared, "cbodies", body_key)
    return _contacts(body, piece, [p for p in _shared_parts(shared) if p.key != body.key])


def job_measure(shared: dict, pair, items) -> list:
    """The pieces of one pair of parts (or one piece on no pair) measured: [(k, Found or None)]."""
    by_key = {p.key: p for p in _shared_parts(shared)}
    pending = {}
    for k, body_key, piece, con, is_named, keys, total in items:
        pending[k] = (_shared_body(shared, "bodies", body_key), piece, con, is_named, keys, total)
    seams_of = _Pairs({pair: [k for k, *_r in items]} if pair is not None else {}, pending, by_key)
    out = []
    for k, (body, piece, con, is_named, keys, _total) in pending.items():
        out.append((k, _measure(body, piece, con, keys, is_named, by_key, seams_of)))
    return out


class _Pairs:
    """Per pair of parts, made when first asked: the two sides with the faces its beads touch picked, and 0319's seams
    between them (only for a bead whose root is not in its own mesh)."""

    def __init__(self, pairs, pending, by_key):
        self.pairs, self.pending, self.by_key = pairs, pending, by_key
        self._picked, self._seams = {}, {}

    def picked(self, ka, kb):
        if (ka, kb) not in self._picked:
            A, B = self.by_key[ka], self.by_key[kb]
            fa, fb = set(), set()
            for k in self.pairs.get((ka, kb), ()):
                con = self.pending[k][2]
                fa |= con[ka][2]
                fb |= con[kb][2]
            sa = core.Side(A.points, A.tris, A.face, np.isin(A.face, list(fa))).prepare()
            sb = core.Side(B.points, B.tris, B.face, np.isin(B.face, list(fb))).prepare()
            self._picked[(ka, kb)] = (sa, sb)
        return self._picked[(ka, kb)]

    def seams(self, ka, kb):
        if (ka, kb) not in self._seams:
            sa, sb = self.picked(ka, kb)
            try:
                self._seams[(ka, kb)] = core.find_seams(sa, sb)
            except Exception:  # noqa: BLE001 - a part the finder cannot read: its beads keep their own shape only
                self._seams[(ka, kb)] = []
        return self._seams[(ka, kb)]


def _sub(body, piece):
    """(points, triangles) of one piece of a body, with only its own points (a welds body holds hundreds of beads)."""
    used, inv = np.unique(body.tris[piece].ravel(), return_inverse=True)
    return body.points[used], inv.reshape(-1, 3)


def _root_seams(body, piece, tris_a, tris_b, sa, sb) -> list | None:
    """The seams of a bead read from its own mesh: the edges where a bead face on A meets one on B, chained into lines
    (split at sharp turns, the pieces joined for mitred ends), with 0319's corner at every point. None when there is no
    such edge or a point has no weld corner (the finder then looks)."""
    pts, tris = _sub(body, piece)
    key = np.round(pts / 1e-5).astype(np.int64)
    _u, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    wp = np.zeros((len(_u), 3))
    wp[inv] = pts
    wt = inv[tris]
    side = np.zeros(len(piece), np.int8)
    side[np.isin(piece, tris_a)] = 1
    side[np.isin(piece, tris_b)] |= 2
    e = np.concatenate([wt[:, [0, 1]], wt[:, [1, 2]], wt[:, [2, 0]]])
    t_of = np.tile(np.arange(len(wt)), 3)
    e = np.sort(e, axis=1)
    order = np.lexsort((e[:, 1], e[:, 0]))
    e, t_of = e[order], t_of[order]
    same = np.all(e[1:] == e[:-1], axis=1)
    root = []
    for i in np.flatnonzero(same):
        if i + 2 < len(e) and np.all(e[i + 2] == e[i]):
            continue                                      # non-manifold: not a clean edge
        s1, s2 = side[t_of[i]], side[t_of[i + 1]]
        if {s1, s2} == {1, 2}:
            root.append(tuple(e[i]))
    if not root:
        return None
    adj: dict = {}
    for a, b in root:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    if any(len(v) > 2 for v in adj.values()):
        return None                                       # a root that branches: let the finder sort it out
    lines, seen = [], set()
    for start in [v for v in adj if len(adj[v]) == 1] + list(adj):
        if start in seen:
            continue
        line = [start]
        seen.add(start)
        prev, cur = None, start
        while True:
            nxt = [v for v in adj[cur] if v != prev and v not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            line.append(cur)
            seen.add(cur)
        closed = len(line) > 2 and line[0] in adj.get(line[-1], []) and len(adj[line[0]]) == 2
        lines.append((wp[line], closed))
    out = []
    reach = core.GAP + 0.0005
    cos_s = math.cos(math.radians(core.SHARP))
    for p, closed in lines:
        if len(p) < 2:
            continue
        # split at sharp turns (a square post's corners): pieces joined end to end for mitres
        n = len(p)
        cuts = []
        for i in (range(n) if closed else range(1, n - 1)):
            a, b, c = p[(i - 1) % n], p[i % n], p[(i + 1) % n]
            if float(core.unit(b - a) @ core.unit(c - b)) < cos_s:
                cuts.append(i % n)
        if closed and cuts:
            p = np.roll(p, -cuts[0], axis=0)
            cuts = sorted((c - cuts[0]) % n for c in cuts)
            pieces = [p[a:b + 1] for a, b in zip(cuts, cuts[1:] + [n])]
            pieces[-1] = np.concatenate([pieces[-1][:-1], p[:1]]) if len(pieces[-1]) else pieces[-1]
            pieces[-1] = np.concatenate([p[cuts[-1]:], p[:1]])
            loop = True
        else:
            bounds = [0] + cuts + [n - 1]
            pieces = [p[a:b + 1] for a, b in zip(bounds, bounds[1:])]
            loop = False
        first = len(out)
        for k, q in enumerate(pieces):
            cs = []
            for j, pt in enumerate(q):
                t = core.unit(q[min(j + 1, len(q) - 1)] - q[max(j - 1, 0)])
                if closed and not cuts and len(q) > 2:
                    t = core.unit(q[(j + 1) % len(q)] - q[(j - 1) % len(q)])
                inset = 0.0 if (closed and not cuts) else min(5e-4, 0.1 * float(np.linalg.norm(q[-1] - q[0])))
                qq = pt + t * inset if j == 0 else (pt - t * inset if j == len(q) - 1 else pt)
                c = core.corners_at(sa, sb, qq, t, reach)
                if not c:
                    return None
                c = max(c, key=lambda x: x.theta)
                if qq is not pt:
                    c = core.Corner(c.kind, c.theta, c.oa + (pt - qq), c.da, c.na, c.ta, c.ob + (pt - qq), c.db, c.nb,
                                    c.tb)
                cs.append(c)
            seam = core.Seam(np.array(q, float), cs, bool(closed and not cuts), cs[0].kind)
            out.append(seam)
        m = len(out) - first
        if m > 1:
            for k in range(m):
                i = first + k
                if k + 1 < m or loop:
                    j = first + (k + 1) % m
                    out[i].joins[1] = (j, 0)
                    out[j].joins[0] = (i, 1)
    return out or None


def _order(p, q):
    """The first part of a weld (the bead moves with it): the bigger one – what the others are welded onto."""
    size_p = float(np.linalg.norm(p.hi - p.lo))
    size_q = float(np.linalg.norm(q.hi - q.lo))
    if abs(size_p - size_q) > 1e-6:
        return (p, q) if size_p > size_q else (q, p)
    return (p, q) if p.name <= q.name else (q, p)


def _measure(body, piece, con, keys, is_named, by_key, seams_of) -> Found | None:
    f = Found(body.key, piece, list(keys), how="name" if is_named else "shape")
    f.metal = metal_of_material(body.material)
    bead_side = core.Side(*_sub(body, piece)).prepare()
    vol = volume(body.points, body.tris[piece])
    if len(keys) != 2:
        f.part_a = keys[0] if keys else None
        f.note = f"joins {len(keys)} part" + ("" if len(keys) == 1 else "s")
        if not is_named:
            return None
        f.kind = "OTHER"
        f.length = _extent(body.points[np.unique(body.tris[piece])])
        return f
    A, B = _order(by_key[keys[0]], by_key[keys[1]])
    f.part_a, f.part_b = A.key, B.key
    side_a, side_b = A.side(), B.side()
    # the bead's root: where its faces on A meet its faces on B (a fillet, a groove without a root gap) – read from the
    # bead itself; else 0319's seam finder between the two parts, cut to where the bead lies
    got = []
    pa, pb = seams_of.picked(A.key, B.key)
    roots = _root_seams(body, piece, con[A.key][1], con[B.key][1], pa, pb)
    if not roots:                                         # task 0368: a square groove with a root gap
        sq = _square_groove(f, body, piece, con[A.key][1], con[B.key][1], is_named)
        if sq is not None:
            return sq if sq is not False else None
    if roots:
        got = [(-1, 0.0, _arc(s.points, s.closed)[-1], s) for s in roots]
    elif not is_named:
        return None                                       # by shape only: its root must be in its own mesh
    else:
        for si, s in enumerate(seams_of.seams(A.key, B.key)):
            for s0, s1 in _trim(s, bead_side):
                whole = s.closed and s0 <= 1e-9 and s1 >= _arc(s.points, True)[-1] - 1e-9
                got.append((si, s0, s1, s if whole else _cut(s, s0, s1)))
    extent = _extent(body.points[np.unique(body.tris[piece])])
    if not got:
        if not is_named:
            return None
        f.kind = "OTHER"
        f.length = extent
        f.note = "its line was not found – its own shape only"
        return f
    # the bead's triangles: on A, on B, free
    tri_a = np.isin(piece, con[A.key][1])
    tri_b = np.isin(piece, con[B.key][1])
    bead_v = body.points[body.tris[piece]]
    reach = 4.0 * math.sqrt(max(vol, 1e-12) / max(extent, 1e-6)) + 0.004
    za_l, zb_l, a_l, th_l, w_l = [], [], [], [], []
    groove_votes = []
    for _si, _s0, _s1, s in got:
        L = _arc(s.points, s.closed)[-1]
        for fr in np.linspace(0.1, 0.9, SAMPLES) if L > 0.004 else [0.5]:
            p, t, c = _point_at(s, fr * L)
            za, zb, depth = _section(bead_v, tri_a, tri_b, ~(tri_a | tri_b), p, t, c, reach)
            if za <= 0 or zb <= 0:
                continue
            za_l.append(za)
            zb_l.append(zb)
            th_l.append(c.theta)
            half = math.radians(min(c.theta, 170.0)) / 2
            a_l.append(min(min(za, zb) * math.cos(half), depth))
            groove_votes.append(_ends(side_a, p, c.da, c.na, za) and _ends(side_b, p, c.db, c.nb, zb))
            u = core.unit(c.da + c.db)
            w_l.append((p, t, c, za, zb, u))
    if not za_l:
        if not is_named:
            return None
        f.kind = "OTHER"
        f.length = extent
        f.note = "its size could not be read – its own shape only"
        return f
    za, zb, theta = float(np.median(za_l)), float(np.median(zb_l)), float(np.median(th_l))
    f.legs = (za, zb)
    groove = sum(groove_votes) > len(groove_votes) / 2
    seam_list = [s for _si, _s0, _s1, s in got]
    f.length = float(sum(_arc(s.points, s.closed)[-1] for s in seam_list))
    if groove:
        f.kind = "BUTT"
        # the cap: how wide the bead is across the plates' faces at the top
        widths, depths = [], []
        for p, t, c, za_, zb_, u in w_l:
            depth = max(za_ * float(c.da @ u), zb_ * float(c.db @ u))
            q = _slice(bead_v, p, t)
            q = q[np.linalg.norm(q - p, axis=1) <= reach]
            if not len(q):
                continue
            across = core.unit(c.da - u * float(c.da @ u))
            x = (q - p) @ across
            widths.append(float(x.max() - x.min()))
            depths.append(depth)
        width = float(np.median(widths)) if widths else za + zb
        depth = float(np.median(depths)) if depths else 0.0
        f.size = max(_half(width), 0.001)
        seam_list = [_to_top(s, depth, width) for s in seam_list]
        f.note = f"groove {round(theta):.0f}°"
    else:
        f.kind = "FILLET"
        f.size = max(_half(float(np.median(a_l))), 0.0005)
        if abs(za - zb) > 0.001:
            f.note = f"legs {za * 1000:.1f} × {zb * 1000:.1f} mm".replace(".0 ", " ").replace(".0×", "×")
            f.note = f"legs {_mm(za)} × {_mm(zb)} mm"
    if not is_named:
        # the shape check: a bead lies along its seam, small legs, a section no fuller than a triangle
        tri_area = 0.5 * za * zb * math.sin(math.radians(min(theta, 179.0)))
        if f.length < ALONG * extent or max(za, zb) > LEG_MAX or min(za, zb) < LEG_MIN:
            return None
        if max(za, zb) > LEGS_RATIO * min(za, zb):
            return None
        if (vol / max(f.length, 1e-9)) > (FILL if f.kind == "FILLET" else FILL_GROOVE) * tri_area:
            return None
        if f.length < 2.0 * max(za, zb):
            return None
    f.seams = seam_list
    f.closed = (len(seam_list) == 1 and seam_list[0].closed) or _loop(seam_list)
    if any(s.closed for s in seam_list) and len(seam_list) == 1:
        f.closed = True
    for s in f.seams:
        s.kind = f.kind
    return f


def _square_groove(f: Found, body, piece, tris_a, tris_b, is_named: bool):
    """A square groove with a root gap (task 0368): the plates' ends face each other a few mm apart and the bead fills
    the gap (its faces on A and on B opposite and parallel, no common edge). Its seam lies on the plates' top face in
    the middle of the gap (as 0319's butt weld), its cap width is the weld's size. Returns the Found filled in, None when
    the bead is no such groove (the other ways are tried), False when it looked like one but failed the shape check
    (by shape: no weld)."""
    v_all, n_all, ar_all = _tri_geom(body.points, body.tris[piece])
    on_a, on_b = np.isin(piece, tris_a), np.isin(piece, tris_b)
    if not on_a.any() or not on_b.any():
        return None
    na_, nb_ = n_all[on_a], n_all[on_b]
    # the gap faces: a bead face on A with one on B turned the other way (the cap's underside on both faces down)
    opp_a = (na_ @ nb_.T < -0.97).any(1)
    opp_b = (nb_ @ na_.T < -0.97).any(1)
    if not opp_a.any() or not opp_b.any():
        return None
    wa, wb = ar_all[on_a][opp_a], ar_all[on_b][opp_b]
    n = core.unit((na_[opp_a] * wa[:, None]).sum(0))       # out of the bead into A
    if float(core.unit((nb_[opp_b] * wb[:, None]).sum(0)) @ n) > -0.97:
        return None
    ca = v_all[on_a][opp_a].mean(1)                          # triangle centres
    cb = v_all[on_b][opp_b].mean(1)
    pa = (ca * wa[:, None]).sum(0) / wa.sum()
    pb = (cb * wb[:, None]).sum(0) / wb.sum()
    gap = float((pa - pb) @ n)
    if not (0.0003 <= gap <= GAP_MAX):
        return None
    # along the joint: the long way of the gap faces (a straight groove)
    pts = np.concatenate([v_all[on_a][opp_a].reshape(-1, 3), v_all[on_b][opp_b].reshape(-1, 3)])
    w = pts - pts.mean(0)
    w = w - np.outer(w @ n, n)
    _u, sv, vt = np.linalg.svd(w, full_matrices=False)
    if len(sv) < 2 or sv[0] < 2.0 * sv[1]:
        return None                                          # (a ring between pipe ends: not read yet)
    t = core.unit(vt[0] - n * float(vt[0] @ n))
    up = core.unit(np.cross(t, n))
    bead_pts = body.points[np.unique(body.tris[piece])]
    hu = pts @ up
    over_up = float((bead_pts @ up).max() - hu.max())
    over_down = float(hu.min() - (bead_pts @ up).min())
    if over_down > over_up:                                  # the cap is on the plates' top face
        up, over_up = -up, over_down
        t = -t
        hu = pts @ up
    top = float(hu.max())
    s = pts @ t
    s0, s1 = float(s.min()), float(s.max())
    mid_n = float(0.5 * (pa + pb) @ n)
    base = n * mid_n + up * top

    def at(x):
        return base + t * x

    # the cap: how wide the bead is across the plates' top at a few places
    bead_v = body.points[body.tris[piece]]
    widths = []
    for fr in np.linspace(0.1, 0.9, SAMPLES):
        p = at(s0 + fr * (s1 - s0))
        q = _slice(bead_v, p, t)
        q = q[(q - p) @ up >= -0.0002]
        if len(q):
            x = (q - p) @ n
            widths.append(float(x.max() - x.min()))
    width = float(np.median(widths)) if widths else gap
    length = s1 - s0
    if not is_named:
        # the shape check: a cap over the plates (a flush filler bar is no weld), no wider than a cap, long for its gap
        if not (GAP_CAP[0] <= over_up <= GAP_CAP[1]) or width < gap + 0.0005 or width > gap + 2 * LEG_MAX:
            return False
        if length < max(0.01, 5.0 * gap) or length < ALONG * _extent(bead_pts):
            return False
    corners = []
    pts_line = np.array([at(s0), at(s1)])
    for p in pts_line:
        corners.append(core.Corner("BUTT", 180.0, p + n * (0.5 * gap), n.copy(), up.copy(), 0,
                                   p - n * (0.5 * gap), -n, up.copy(), 0))
    seam = core.Seam(pts_line, corners, False, "BUTT")
    f.kind = "BUTT"
    f.seams = [seam]
    f.length = float(length)
    f.size = max(_half(width), 0.001)
    f.gap = float(gap)
    f.legs = (0.5 * width, 0.5 * width)
    f.closed = False
    f.note = f"square groove, gap {_mm(gap)} mm"
    return f


def _mm(x: float) -> str:
    v = round(x * 2000.0) / 2.0
    return f"{v:.0f}" if abs(v - round(v)) < 1e-9 else f"{v:.1f}"


def _extent(pts: np.ndarray) -> float:
    """How long a bead is: its longest side, or round a ring (the length of the loop through its points' middle)."""
    pts = np.asarray(pts, np.float64)
    if len(pts) < 2:
        return 0.0
    c = pts.mean(0)
    w = pts - c
    _u, s, vt = np.linalg.svd(w, full_matrices=False)
    x = w @ vt[0]
    return float(x.max() - x.min())


def _loop(seams: list) -> bool:
    """Seams that go round in a loop end to end (a bead round a square post)."""
    if len(seams) < 2:
        return False
    ends = []
    for s in seams:
        ends.append(s.points[0])
        ends.append(s.points[-1])
    ends = np.array(ends)
    for i in range(len(ends)):
        d = np.linalg.norm(ends - ends[i], axis=1)
        d[i] = np.inf
        d[i ^ 1] = np.inf
        if d.min() > 0.002:
            return False
    return True


def _merge(fs: list) -> list:
    """Beads of one pair lying one after the other on one straight line, with like lengths and gaps: one intermittent
    weld."""
    out = []
    single = [f for f in fs if len(f.seams) == 1 and not f.seams[0].closed and f.kind == "FILLET"]
    ids = {id(f) for f in single}
    out = [f for f in fs if id(f) not in ids]
    groups: list = []
    for f in single:
        s = f.seams[0]
        p0, p1 = s.points[0], s.points[-1]
        d = core.unit(p1 - p0)
        straight = float(np.max(np.linalg.norm(np.cross(s.points - p0, d), axis=1))) < 0.0005 if len(s.points) > 2 \
            else True
        for g in groups:
            q0, dq = g[0]
            if straight and abs(float(d @ dq)) > 0.999 and \
                    float(np.linalg.norm(np.cross(p0 - q0, dq))) < 0.0005 and float(np.linalg.norm(np.cross(p1 - q0, dq))) < 0.0005:
                g[1].append(f)
                break
        else:
            groups.append(((p0, d), [f]) if straight else ((p0, d), [f]))
    for (q0, dq), group in groups:
        if len(group) < 2:
            out.extend(group)
            continue
        for f in group:                                   # all pieces the same way along the line
            s = f.seams[0]
            if float((s.points[-1] - s.points[0]) @ dq) < 0:
                s.points = s.points[::-1].copy()
                s.corners = s.corners[::-1]
        group.sort(key=lambda f: float((f.seams[0].points[0] - q0) @ dq))
        ls = np.array([f.length for f in group])
        starts = np.array([float((f.seams[0].points[0] - q0) @ dq) for f in group])
        pitches = np.diff(starts)
        regular = (ls.max() - ls.min() <= REGULAR * ls.mean() and len(pitches)
                   and pitches.max() - pitches.min() <= REGULAR * pitches.mean() and pitches.min() > ls.max() + 0.001)
        if not regular:
            out.extend(group)
            continue
        first = group[0]
        n, piece, pitch = len(group), _half(float(ls.mean())), _half(float(pitches.mean()))
        line = _join(group[0].seams[0], group[-1].seams[0])
        w = Found(first.body, np.concatenate([f.tris for f in group]), first.parts, first.part_a, first.part_b,
                  "FILLET", first.how, [line], _half(float(np.median([f.size for f in group]))),
                  tuple(float(np.median([f.legs[i] for f in group])) for i in (0, 1)), n * piece, False,
                  (n, piece, pitch), first.note, first.metal, n)
        out.append(w)
    return out


def _join(a: core.Seam, b: core.Seam) -> core.Seam:
    """One straight seam from a's start to b's end (both pieces of one line), 0.05 mm longer at each end."""
    p0, p1 = a.points[0], b.points[-1]
    t = core.unit(p1 - p0)
    p0, p1 = p0 - t * 0.00005, p1 + t * 0.00005
    c0, c1 = a.corners[0], b.corners[-1]

    def moved(c, p, q):
        return core.Corner(c.kind, c.theta, c.oa + (q - p), c.da, c.na, c.ta, c.ob + (q - p), c.db, c.nb, c.tb)
    return core.Seam(np.array([p0, p1]), [moved(c0, a.points[0], p0), moved(c1, b.points[-1], p1)], False, a.kind)


# ---------------------------------------------------------------------------
# UVs on the CAD bead, seams into another frame
# ---------------------------------------------------------------------------

def uvs(points: np.ndarray, tris: np.ndarray, seams: list, kind: str, size: float) -> np.ndarray:
    """(m, 3, 2) per triangle corner: u = metres along the seams (one after the other), v = 0 at the toe on the first
    part … 1 at the toe on the second (a groove: across its cap ``size`` wide)."""
    pts = np.asarray(points, np.float64)[np.asarray(tris, np.int64)].reshape(-1, 3)
    m = len(pts)
    u = np.zeros(m)
    vv = np.full(m, 0.5)
    best = np.full(m, np.inf)
    base = 0.0
    loops = []
    for s in seams:
        sp = np.concatenate([s.points, s.points[:1]]) if s.closed and len(s.points) > 2 else s.points
        cs = s.corners + s.corners[:1] if s.closed and len(s.points) > 2 else s.corners
        L = _arc(s.points, s.closed)
        for i in range(len(sp) - 1):
            a, b = sp[i], sp[i + 1]
            ab = b - a
            l2 = max(float(ab @ ab), 1e-18)
            f = np.clip(((pts - a) @ ab) / l2, 0.0, 1.0)
            foot = a + np.outer(f, ab)
            d = np.linalg.norm(pts - foot, axis=1)
            take = d < best - 1e-9
            if not take.any():
                continue
            best[take] = d[take]
            u[take] = base + L[i] + f[take] * (L[i + 1] - L[i])
            c = core._interp_corner(cs[i], cs[i + 1], 0.5)
            w = pts[take] - foot[take]
            if kind == "BUTT":
                vv[take] = np.clip(0.5 + (w @ c.db) / max(size, 1e-6), 0.0, 1.0)
            else:
                t = core.unit(ab)
                db_perp = core.unit(c.db - c.da * float(c.db @ c.da)) if abs(float(c.db @ c.da)) < 0.999 \
                    else core.unit(np.cross(t, c.da))
                ang = np.arctan2(w @ db_perp, w @ c.da)
                vv[take] = np.clip(ang / max(math.radians(c.theta), 1e-3), 0.0, 1.0)
        if s.closed:
            loops.append((base, base + L[-1]))
        base += L[-1]
    if _loop(seams):                                      # seams round in a loop (a square post): one ring of u
        loops.append((0.0, base))
    uv = np.stack([u, vv], 1).reshape(-1, 3, 2)
    # a triangle across a closed seam's start: its corners on the same side of the wrap
    for lo, hi in loops:
        span = hi - lo
        uu = uv[:, :, 0]
        inside = ((uu >= lo - 1e-9) & (uu <= hi + 1e-9)).all(1)
        wide = inside & (uu.max(1) - uu.min(1) > 0.5 * span)
        if wide.any():
            fix = uu[wide]
            fix = np.where(fix < lo + 0.5 * span, fix + span, fix)
            uu[wide] = fix
    return uv


def transform(seams: list, M: np.ndarray) -> list:
    """Seams into another frame (a 4 x 4 matrix, rigid)."""
    R, T = M[:3, :3], M[:3, 3]
    out = []
    for s in seams:
        cs = [core.Corner(c.kind, c.theta, R @ c.oa + T, R @ c.da, R @ c.na, c.ta, R @ c.ob + T, R @ c.db, R @ c.nb,
                          c.tb, c.sa, c.sb) for c in s.corners]
        n = core.Seam(s.points @ R.T + T, cs, s.closed, s.kind)
        n.joins = list(s.joins)
        out.append(n)
    return out


def describe(f: Found) -> str:
    """'fillet a5, 200 mm' / 'groove (butt), cap 15.5 mm, 300 mm' / '4 × 30 (50)' – for messages and tests."""
    if f.kind == "BUTT":
        text = f"groove (butt), cap {_mm(f.size)} mm"
    elif f.kind == "FILLET":
        text = f"fillet a{_mm(f.size)}"
    else:
        text = "weld"
    if f.intermittent:
        n, l, e = f.intermittent
        text += f", {n} × {l * 1000:.0f} ({e * 1000:.0f})"
    else:
        text += f", {f.length * 1000:.0f} mm"
    if f.closed:
        text += ", all round"
    if f.note:
        text += f" ({f.note})"
    return text


def match(old: list, new: list, tol: float = 0.003) -> list:
    """Model update: [(old index, new index or None)] – a new bead in the same place as an old one (same parts, its
    seams' middle within ``tol`` of the old ones' or overlapping them) is that weld again. ``old`` / ``new``: lists of
    (part a, part b, points (k, 3) along the seams, world)."""
    out = []
    used = set()
    for i, (a, b, pts) in enumerate(old):
        best, bd = None, math.inf
        for j, (na, nb, npts) in enumerate(new):
            if j in used or {a, b} != {na, nb} or not len(pts) or not len(npts):
                continue
            # the share of the old line that the new one runs along (and the other way round)
            d_on = _near(pts, npts)
            d_back = _near(npts, pts)
            share = max(float((d_on <= tol).mean()), float((d_back <= tol).mean()))
            if share < 0.5:
                continue
            d = float(np.median(d_on))
            if d < bd:
                best, bd = j, d
        if best is not None:
            used.add(best)
        out.append((i, best))
    return out


def _near(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Distance from each point of p to the polyline q."""
    p, q = np.asarray(p, np.float64), np.asarray(q, np.float64)
    if len(q) == 1:
        return np.linalg.norm(p - q[0], axis=1)
    a, b = q[:-1], q[1:]
    ab = b - a
    l2 = np.maximum((ab * ab).sum(1), 1e-18)
    out = np.full(len(p), np.inf)
    for i in range(len(a)):
        f = np.clip(((p - a[i]) @ ab[i]) / l2[i], 0.0, 1.0)
        out = np.minimum(out, np.linalg.norm(p - (a[i] + np.outer(f, ab[i])), axis=1))
    return out


def line_points(seams: list, step: float = 0.002) -> np.ndarray:
    """Points every ``step`` along seams (for ``match``)."""
    out = []
    for s in seams:
        _s, p = _resample(s, step)
        out.append(p)
    return np.concatenate(out) if out else np.zeros((0, 3))
