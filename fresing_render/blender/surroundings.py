"""Surroundings around the machine and props for scale (task 0016).

Built-in surroundings (sea, vessel deck, quayside, factory halls, warehouse) and the ground of a
360° photo live in the collection "FR Surroundings", under one empty that sits under the model:
the floor is at the model's lowest point (minus the floor gap), centred on it. The model itself is
never moved, so joints, poses, cameras and animations stay exactly as they are.

The layouts come from ``core/surroundings.py``; everything is made in code (no image files).
A surrounding is rebuilt only when its settings change, so a render in the background queue uses
what was saved with the project.

Halls are seen from inside: walls and the roof are see-through from outside (a camera outside the
hall looks in), do not block the light and cast no shadows, so a hall renders about as fast as
the studio. The sea (task 0109, ``core/sea.py``) is a sum of waves from a wind-wave spectrum: geometry near the
machine in "Detailed", the same waves' slopes in the material to the horizon, white caps where the foam field of
``core/sea.py`` is high (as many as Monahan's relation gives for the wind), foam round the hull and a wake, spray
in strong wind.

Props for scale (person, container, pallet, barrier) are ordinary objects in "FR Props": they can
be moved and are hidden or shown in one click.
"""

from __future__ import annotations

import json
import math
import os
import random

import bpy
import numpy as np

from ..core import props_detail
from ..core import ral
from ..core import sea as sea_core
from ..core import surroundings as S
from ..core import weather as weather_core
from . import sea_view_cut as view_cut

COLLECTION = "FR Surroundings"
ROOT = "FR Surroundings"
PROPS_COLLECTION = "FR Props"
MAT_PREFIX = "FR_env "
TAG = "fr_env"                     # on every object made here (value: its role)
PROP_TAG = "fr_prop"               # on props (value: prop kind)
MAT_VERSION = 5                    # 4: the new sea (task 0109); 5: vessel at work (task 0154)
TRANSPARENT_STEPS = 128
CUT_ROLES = ("structure", "high", "lights", "contents")   # halls: what may stand in the camera's way
# materials of floors and walls: never between the camera and the machine (both are inside the hall,
# or the near wall is see-through from outside), so they get no cut-away nodes (they cost render time)
NEVER_IN_THE_WAY = ("floor_epoxy", "floor_epoxy_green", "floor_concrete", "concrete", "deck", "line_yellow",
                    "line_white", "rail_steel", "water", "wall_panel", "wall_panel_out", "wall_dado", "roof",
                    "door", "window", "skylight")
WAVES_GROUP = "FR_env waves"
PHOTO_DEFAULT_HEIGHT = 1.7

# ray visibility per role: camera, diffuse, glossy, transmission, shadow
_VISIBILITY = {
    "shell": (True, False, True, True, False),
    "lights": (True, False, True, True, False),
    "high": (True, True, True, True, False),
    "photo_dome": (True, False, True, True, False),
    "photo_ground": (True, True, True, True, False),
    "sea": (True, True, True, True, False),
}


# =============================================================================
# what is wanted now
# =============================================================================


def wanted(s) -> str:
    """'' (nothing), a built-in kind, or 'PHOTO' (the ground of a 360° photo)."""
    if s.background in S.BUILT:
        return s.background
    if s.background == "HDRI" and s.photo_ground and _photo_path(s):
        return "PHOTO"
    return ""


def _photo_path(s) -> str:
    path = bpy.path.abspath(s.hdri_path) if s.hdri_path else ""
    return path if path and os.path.isfile(path) else ""


def _settings_key(s, kind: str) -> dict:
    key = {"kind": kind, "v": MAT_VERSION}
    if kind in S.BUILT:
        key["detail"] = s.env_detail
    if kind in S.SEA_KINDS:
        key.update(sea=s.sea_state, foam=bool(s.sea_foam), moving=bool(s.sea_moving))
        if s.sea_state == "WIND":                # task 0109: the sea follows the wind of Weather & time
            bft, toward = sea_wind(s)
            key["wind"] = [round(bft, 2), round(toward, 1)]
        if _weather_on(s):                       # the white caps read the weather's foam channel; wake, spray
            key["wx"] = 1
            if getattr(s.weather, "bow", "AUTO") != "AUTO":
                key["bow"] = s.weather.bow           # task 0082: which way the wake and the bow spray go
            sw = _spray_wind(s)
            if sw is not None:
                key["spray"] = [round(sw[0], 2), round(sw[1][0], 3), round(sw[1][1], 3)]
        if _max_speed(s) > 0:                     # task 0154: the hull foam's reach (the speed itself: a channel)
            key["speed"] = round(_max_speed(s), 2)
        work = _work().sea_key(s.id_data)        # task 0154: the vessel sails / its thrusters run somewhere
        if work:
            key["work"] = work
        swell = _vessel().swell_key(s)        # vessel motion (task 0085): its swell; nothing when it is off
        if swell:
            key["swell"] = swell
    if kind == "SEA":
        key["water"] = round(s.water_level, 3)
        key["depth"] = round(float(s.sea_depth), 2)        # task 0081: the seabed (always on the open sea)
        if s.sea_cutaway:                                  # the cut-away's settings only when it is on
            key["cut"] = _cut_key(s)
    if kind == "PHOTO":
        key.update(photo=_photo_path(s), height=round(s.photo_height, 3))
    return key


def _vessel():
    from . import vessel_motion
    return vessel_motion


def _work():
    from . import vessel_work
    return vessel_work


def _models_key(scene) -> list:
    from . import build
    return [[r.name, r.get("fr_stats", "")] for r in build.model_roots(scene)]


def root_object():
    ob = bpy.data.objects.get(ROOT)
    return ob if ob is not None and ob.get(TAG) == "root" else None


def floor_height(scene) -> float:
    """World z of the floor the machine stands on (surroundings, else the model's lowest point)."""
    root = root_object()
    if root is not None and root.get("fr_kind"):
        return float(root.location.z)
    from . import logic
    mn, _mx = logic.cached_bounds(scene)
    return float(mn[2]) - scene.fresing.floor_offset


def far_clip(scene) -> float:
    """Camera clip distance the surroundings need (0 = nothing special)."""
    root = root_object()
    return float(root.get("fr_far", 0.0)) if root is not None and root.get("fr_kind") else 0.0


# =============================================================================
# entry point (called from world.apply)
# =============================================================================


def ensure(scene, s, replace: bool = False) -> None:
    """Make the surroundings match the settings. Cheap when nothing changed.

    ``replace``: read the model's size and position again (button 'Fit surroundings to the model')."""
    kind = wanted(s)
    root = root_object()
    if not kind:
        if root is not None and root.get("fr_kind"):
            clear(scene)
        _vessel().after_surroundings(scene)          # task 0085: no sea, no vessel motion
        return
    key = json.dumps(_settings_key(s, kind), sort_keys=True)
    models = json.dumps(_models_key(scene))
    stale = (root is None or root.get("fr_key") != key or root.get("fr_models") != models or replace
             or not _objects(scene))
    if stale and _only_added(root, key, models, replace, scene):
        _note_misfit(scene, root, models)        # task 0043: a later import leaves the surroundings where they are
        stale = False
    if stale:
        _build(scene, s, kind, key, models)
        root = root_object()
    _update_live(scene, s, root)
    _vessel().after_surroundings(scene)              # task 0085: the deck (maybe new) moves with the vessel
    from . import marine_looks
    marine_looks.sync(scene)                         # task 0136: marine growth follows the sea (water level, deck)


def _only_added(root, key: str, models: str, replace: bool, scene) -> bool:
    """True when the only change is that more models came in (every earlier model is as it was)."""
    if replace or root is None or not root.get("fr_kind") or root.get("fr_key") != key or not _objects(scene):
        return False
    try:
        old = json.loads(root.get("fr_models", "[]"))
        new = json.loads(models)
    except ValueError:
        return False
    return bool(old) and len(new) > len(old) and all(o in new for o in old)


def _note_misfit(scene, root, models: str) -> None:
    """Remember the new models and whether they stick out of the area the surroundings were laid for."""
    root["fr_models"] = models
    with _vessel().at_rest(scene):
        mn, mx = _model_box(scene)
    p0, p1 = np.array(root.get("fr_min", mn), float), np.array(root.get("fr_max", mx), float)
    pad = 0.1 * np.maximum(p1 - p0, 0.05)
    out = bool(np.any(mn < p0 - pad) or np.any(mx > p1 + pad))
    root["fr_misfit"] = out


def misfit(scene) -> bool:
    """A later import sticks out of the floor area / walls: the panel offers 'Fit surroundings to the model'."""
    root = root_object()
    return bool(root is not None and root.get("fr_kind") and root.get("fr_misfit"))


def clear(scene) -> None:
    """Remove the surroundings (props stay)."""
    objs = [ob for ob in bpy.data.objects if ob.get(TAG) and ob.get(TAG) != "root"]
    meshes = {ob.data for ob in objs if ob.type == "MESH" and ob.data is not None}
    if objs:
        bpy.data.batch_remove(objs)
    orphans = [m for m in meshes if m.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    # the spray (task 0109) is made only with weather: nothing of it stays when the weather goes
    groups = [g for g in bpy.data.node_groups if g.name.startswith(f"{WAVES_GROUP} spray") and g.users == 0]
    if groups:
        bpy.data.batch_remove(groups)
    spray = [m for m in bpy.data.materials if m.get("fr_env") == "spray" and m.users == 0]
    if spray:
        bpy.data.batch_remove(spray)
    root = root_object()
    if root is not None:
        for k in ("fr_kind", "fr_key", "fr_models", "fr_far", "fr_misfit", BOW_KEY):
            if k in root:
                del root[k]


def _objects(scene) -> list:
    col = bpy.data.collections.get(COLLECTION)
    return [ob for ob in col.objects if ob.get(TAG) and ob.get(TAG) != "root"] if col is not None else []


def _collection(scene, name: str = COLLECTION) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if col.name not in scene.collection.children:
        scene.collection.children.link(col)
    return col


def _root(scene) -> bpy.types.Object:
    root = root_object()
    if root is None:
        root = bpy.data.objects.new(ROOT, None)
        root[TAG] = "root"
        root.empty_display_size = 0.3
        root.hide_select = True
    col = _collection(scene)
    if root.name not in col.objects:
        col.objects.link(root)
    return root


def _model_box(scene) -> tuple[np.ndarray, np.ndarray]:
    """Size and place of the whole machine: every part except those removed in clean-up.

    Parts that are only hidden for now (Show only, a saved scene's visibility set) count too, so the
    floor stays where it is when a scene hides the machine's base or covers."""
    from . import build, logic
    try:
        bpy.context.view_layer.update()
    except Exception:
        pass
    parts = [ob for ob in build.iter_parts(scene) if not ob.get(build.PROP_EXCLUDED)]
    # task 0216 (bug hunt 7 row 10): a crane of a lifting plan (its model root has ``fr_lifting``) is not the machine
    # the sea and the deck are made round: one with its hook lowered beside the hull put the waterline 6.5 m lower and
    # the vessel's beam for the motion at 39 m instead of 27 m. (Load boxes are no parts.) Only cranes: they count.
    memo: dict = {}
    own = [ob for ob in parts if not _is_crane(build.model_root_of(ob, memo))]
    parts = own or parts
    if not parts:
        scene.fresing.bounds_valid = False
        return logic.cached_bounds(scene)
    return build.world_bounds(parts)


def _is_crane(root) -> bool:
    return root is not None and bool(root.get("fr_lifting"))


def _build(scene, s, kind: str, key: str, models: str) -> None:
    clear(scene)
    outline = None
    with _vessel().at_rest(scene):                  # task 0085: measured where it stands on a still sea
        mn, mx = _model_box(scene)
        size = np.maximum(mx - mn, 0.05)
        root = _root(scene)
        root["fr_min"] = [float(v) for v in mn]
        root["fr_max"] = [float(v) for v in mx]
        root.location = (float(mn[0] + mx[0]) / 2, float(mn[1] + mx[1]) / 2, float(mn[2]) - s.floor_offset)
        if kind != "PHOTO":
            lay = S.build(kind, tuple(float(v) for v in size), s.env_detail, s.water_level)
            if lay.water_level is not None and _wants_outline(s):
                # (task 0202: in the same still moment as the model's box – each such moment updates the scene twice)
                outline = _waterline(scene, s, kind, root, lay.water_level)
    col = _collection(scene)
    if kind == "PHOTO":
        far = _build_photo(scene, s, root, col, size)
    else:
        centre = (0.0, 0.0, s.floor_offset + float(size[2]) / 2)
        radius = float(np.linalg.norm(size)) / 2
        for role, shapes in lay.parts.items():
            if shapes:
                ob = _shapes_object(f"FR {S.KIND[kind].label}: {role}", role, shapes, col, root)
                if lay.hall is not None and role in CUT_ROLES:
                    ob["fr_cut_c"] = centre
                    ob["fr_cut_r"] = radius
                    if role in ("high", "lights") and lay.roof_z:
                        ob["fr_roof"] = lay.roof_z
        if lay.water_level is not None:
            _build_sea(s, col, root, lay.water_level, float(max(size[0], size[1])), kind, outline)
        far = lay.extent * 1.3
    root["fr_kind"] = kind
    # task 0125: the sea's build may have read the bow from the hull (the wind and the swell turn with it): the key of
    # what was built, so the next check does not build it again
    root["fr_key"] = json.dumps(_settings_key(s, kind), sort_keys=True) if root.get(BOW_KEY) is not None else key
    root["fr_models"] = models
    root["fr_far"] = far
    _show_in_view(scene, s)


def _update_live(scene, s, root) -> None:
    """Settings that need no rebuild: floor gap, photo turn and strength, cameras' clip distance."""
    if root is None:
        return
    mn = root.get("fr_min")
    if mn is not None:
        z = float(mn[2]) - s.floor_offset
        if abs(root.location.z - z) > 1e-6:
            root.location.z = z
    if root.get("fr_kind") == "PHOTO":
        _photo_update(s)
    if root.get("fr_kind") in S.HALL_KINDS:
        # a view ray may pass many cut-away beams and see-through walls: each is a step through
        # something transparent, and Cycles shows black when it runs out of them (default 8)
        c = getattr(scene, "cycles", None)
        if c is not None and getattr(c, "transparent_max_bounces", 999) < TRANSPARENT_STEPS:
            from . import render
            render._set(c, "transparent_max_bounces", TRANSPARENT_STEPS)
    far = float(root.get("fr_far", 0.0))
    if far > 0:
        fix_clip(scene, far)
    _update_under_water(scene, s, root)            # task 0081: the seabed's motion, the water's light
    if root.get("fr_kind") in S.SEA_KINDS:
        _work().sync(scene)                        # task 0154: the vessel's channels follow the panel
    _show_in_view(scene, s)


def scene_reach(scene) -> float:
    """How far what is drawn reaches from the origin (m): the surroundings' ``fr_far`` and the farthest object (the
    wind park too; task 0193). Not the cameras' clip ends (task 0216, bug hunt 7 row 31): the demo's cameras see 52 km
    while the farthest thing drawn is at 28 km, and the views' near clip came out 0.29 m – a close look was cut."""
    far = far_clip(scene)
    for ob in scene.objects:
        if ob.type in ("MESH", "EMPTY", "CURVE") and not ob.hide_viewport:
            p = ob.matrix_world.translation
            far = max(far, (float(p.x) ** 2 + float(p.y) ** 2 + float(p.z) ** 2) ** 0.5)
    return far


def view_clip_start(far: float) -> float:
    """The view's near clip for a scene of this reach: Blender's 0.01 m for ordinary scenes, 0.05 m
    from 10 km (end / start stays <= 200,000, no flicker between faces); never cuts a close look."""
    return 0.01 if far < 5000.0 else min(0.05 * far / 10000.0, 0.5)


def _app_start(sp) -> bool:
    """The view's near clip is one this app set for its far clip (``view_clip_start``), not the user's own."""
    want = view_clip_start(float(sp.clip_end))
    return want > 0.01 and abs(float(sp.clip_start) - want) < 1e-4 * max(1.0, want)


def fix_view_clip(scene=None, far: float | None = None) -> None:
    """Every 3D view (not camera views) sees as far as the scene reaches. Never lowers a larger far clip; a near clip
    is lowered only when the app set it for a farther reach (task 0216: 0.29 m on the demo, from its cameras)."""
    scene = scene or bpy.context.scene
    if scene is None:
        return
    far = scene_reach(scene) if far is None else far
    if far <= 0:
        return
    far = far * 1.1 + 10.0
    start = view_clip_start(far)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type != "VIEW_3D":
                    continue
                lower = sp.clip_start > start and _app_start(sp)
                if sp.clip_end < far or lower:     # (an app-set pair is set again as a pair: no flicker)
                    sp.clip_end = far
                if sp.clip_start < start or lower:
                    sp.clip_start = start


def fix_clip(scene, far: float | None = None) -> None:
    """Cameras must see as far as the surroundings reach (the sea goes to the horizon);
    the 3D views too (task 0193)."""
    far = far_clip(scene) if far is None else far
    if far <= 0:
        fix_view_clip(scene)
        return
    cams = [ob for ob in scene.objects if ob.type == "CAMERA"]
    for ob in cams:
        if ob.data.clip_end < far:
            ob.data.clip_end = far
    fix_view_clip(scene)


def _show_in_view(scene, s) -> None:
    hide = not s.env_show_in_view
    for ob in _objects(scene):
        if ob.hide_viewport != hide:
            ob.hide_viewport = hide


# =============================================================================
# meshes from shapes
# =============================================================================


def _frame(p0, p1):
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    a = p1 - p0
    n = np.linalg.norm(a)
    a = a / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])
    up = np.array([0.0, 0.0, 1.0]) if abs(a[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    side = np.cross(a, up)
    side /= np.linalg.norm(side)
    u = np.cross(a, side)                  # (side, u, a) is right-handed
    return p0, p1, side, u


_BOX_FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))


class _Mesh:
    def __init__(self):
        self.verts: list = []
        self.faces: list = []
        self.mats: list[int] = []
        self.smooth: list[bool] = []
        self.n = 0

    def _add(self, pts, faces, mat, smooth=False):
        base = self.n
        self.verts.append(np.asarray(pts, float))
        self.n += len(pts)
        if isinstance(faces, np.ndarray) and faces.ndim == 2:      # task 0202: many faces of one size at once
            self.faces.append(faces.astype(np.int64) + base)
            self.mats.extend([mat] * len(faces))
            self.smooth.extend([smooth] * len(faces))
            return
        for f in faces:
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(mat)
            self.smooth.append(smooth)

    def box8(self, corners, mat):
        self._add(corners, _BOX_FACES, mat)

    def shape(self, sh, mat):
        if isinstance(sh, S.Box):
            c, sn = math.cos(sh.rot), math.sin(sh.rot)
            pts = []
            for z in (0.0, sh.sz):
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    lx, ly = x * sh.sx / 2, y * sh.sy / 2
                    pts.append((sh.x + lx * c - ly * sn, sh.y + lx * sn + ly * c, sh.z + z))
            self.box8(pts, mat)
        elif isinstance(sh, S.Beam):
            p0, p1, side, u = _frame(sh.p0, sh.p1)
            pts = []
            for p in (p0, p1):
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    pts.append(p + side * x * sh.w / 2 + u * y * sh.h / 2)
            self.box8(pts, mat)
        elif isinstance(sh, S.Tube):
            p0, p1, side, u = _frame(sh.p0, sh.p1)
            n = max(3, sh.seg)
            ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
            ring = np.outer(np.cos(ang), side) + np.outer(np.sin(ang), u)
            pts = np.concatenate([p0 + ring * sh.r, p1 + ring * sh.r])
            faces = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
            self._add(pts, faces, mat, smooth=True)
            base = self.n - 2 * n
            for f in (tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))):     # caps: flat
                self.faces.append(tuple(base + i for i in f))
                self.mats.append(mat)
                self.smooth.append(False)
        elif isinstance(sh, S.Sphere):
            n, m = max(6, sh.seg), max(4, sh.seg // 2)
            c = np.asarray(sh.c, float)
            pts = [c + (0, 0, -sh.r)]
            for j in range(1, m):
                lat = -math.pi / 2 + math.pi * j / m
                for i in range(n):
                    lon = 2 * math.pi * i / n
                    pts.append(c + sh.r * np.array((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                                                     math.sin(lat))))
            pts.append(c + (0, 0, sh.r))
            top = len(pts) - 1
            faces = [(0, 1 + (i + 1) % n, 1 + i) for i in range(n)]
            for j in range(m - 2):
                a, b = 1 + j * n, 1 + (j + 1) * n
                faces += [(a + i, a + (i + 1) % n, b + (i + 1) % n, b + i) for i in range(n)]
            a = 1 + (m - 2) * n
            faces += [(a + i, a + (i + 1) % n, top) for i in range(n)]
            self._add(pts, faces, mat, smooth=True)
        elif isinstance(sh, S.Quad):
            self._add(sh.pts, [(0, 1, 2, 3)], mat)
        elif isinstance(sh, S.Loft):
            self.loft(sh, mat)

    def loft(self, sh, mat):
        """Rings stitched into quads (task 0155); closed rings get fan caps; faces turned to point outwards."""
        rings = np.asarray(sh.rings, float)
        m, n = rings.shape[0], rings.shape[1]
        if m < 2 or n < 2:
            return
        pts = rings.reshape(-1, 3)
        wrap = n if sh.closed else n - 1
        faces = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
                 for j in range(m - 1) for i in range(wrap)]
        caps = []
        if sh.closed and sh.caps:
            pts = np.concatenate([pts, rings[0].mean(0)[None], rings[-1].mean(0)[None]])
            c0, c1 = m * n, m * n + 1
            caps = [(c0, (i + 1) % n, i) for i in range(n)] + [(c1, (m - 1) * n + i, (m - 1) * n + (i + 1) % n)
                                                              for i in range(n)]
        if sh.closed:                       # outwards: the sum of (face centre - middle) · normal must be positive
            mid = pts[: m * n].mean(0)
            q = np.asarray(faces)
            a, b, c = pts[q[:, 0]], pts[q[:, 1]], pts[q[:, 2]]
            nrm = np.cross(b - a, c - b)
            if float(np.einsum("ij,ij->", nrm, (a + c) / 2 - mid)) < 0:
                faces = [f[::-1] for f in faces]
                caps = [f[::-1] for f in caps]
        base = self.n
        self.verts.append(pts)
        self.n += len(pts)
        for f in faces:
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(mat)
            self.smooth.append(bool(sh.smooth))
        for f in caps:
            self.faces.append(tuple(base + i for i in f))
            self.mats.append(mat)
            self.smooth.append(bool(sh.smooth))

    def to_mesh(self, name: str) -> bpy.types.Mesh:
        me = bpy.data.meshes.new(name)
        verts = np.concatenate(self.verts) if self.verts else np.zeros((0, 3))
        me.vertices.add(len(verts))
        me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
        sizes, loops, run = [], [], []

        def flush():
            if run:
                sizes.append(np.array([len(f) for f in run], dtype=np.int32))
                loops.append(np.fromiter((i for f in run for i in f), dtype=np.int32, count=int(sizes[-1].sum())))
                run.clear()
        for f in self.faces:
            if isinstance(f, np.ndarray):              # a block of faces of one size (``_add``)
                flush()
                sizes.append(np.full(len(f), f.shape[1], dtype=np.int32))
                loops.append(f.astype(np.int32).ravel())
            else:
                run.append(f)
        flush()
        sizes = np.concatenate(sizes) if sizes else np.zeros(0, np.int32)
        loops = np.concatenate(loops) if loops else np.zeros(0, np.int32)
        me.loops.add(len(loops))
        me.loops.foreach_set("vertex_index", loops)
        me.polygons.add(len(sizes))
        starts = np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(np.int32)
        me.polygons.foreach_set("loop_start", starts)
        me.polygons.foreach_set("material_index", np.array(self.mats, dtype=np.int32))
        me.update(calc_edges=True)
        me.polygons.foreach_set("use_smooth", np.array(self.smooth, dtype=bool))
        me.validate(clean_customdata=False)
        return me


def _new_object(name: str, me, role: str, col, parent) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.parent = parent
    ob[TAG] = role
    ob.hide_select = True
    vis = _VISIBILITY.get(role)
    if vis is not None:
        (ob.visible_camera, ob.visible_diffuse, ob.visible_glossy, ob.visible_transmission,
         ob.visible_shadow) = vis
    if role in ("shell", "photo_dome"):
        ob.display_type = "WIRE"           # the view stays clear when you look from outside
    return ob


def _shapes_object(name, role, shapes, col, parent) -> bpy.types.Object:
    keys = sorted({sh.mat for sh in shapes})
    index = {k: i for i, k in enumerate(keys)}
    m = _Mesh()
    for sh in shapes:
        m.shape(sh, index[sh.mat])
    me = m.to_mesh(name)
    for k in keys:
        me.materials.append(material(k))
    return _new_object(name, me, role, col, parent)


# =============================================================================
# materials (procedural)
# =============================================================================


def _ral(code: str):
    parsed = ral.parse_colour(code)
    srgb = parsed[1] if parsed else (0.7, 0.7, 0.7)
    return tuple(ral.srgb_to_linear(c) for c in srgb)


def _srgb(*rgb):
    return tuple(ral.srgb_to_linear(c) for c in rgb)


class _Mismatch(Exception):
    """A tree built again does not have the nodes / links its last build had: it is made new."""


def _same_value(old, v) -> bool:
    """``v`` is what a socket / setting already holds (numbers compared as the float32 Blender stores)."""
    try:
        if isinstance(v, (int, float, tuple, list)) and not isinstance(v, bool):
            a, b = np.asarray(old, np.float32), np.asarray(v, np.float32)
            return a.shape == b.shape and bool(np.array_equal(a, b))
        return old == v
    except (TypeError, ValueError):
        return False


class _ReplaySocket:
    """An input socket of a node of a tree built again: its value is written only when it differs (each write makes
    Blender look the whole project over: ~0.5 ms in the demo)."""

    __slots__ = ("_n",)

    def __init__(self, sock):
        object.__setattr__(self, "_n", sock)

    def __getattr__(self, k):
        return getattr(self._n, k)

    def __setattr__(self, k, v):
        if not _same_value(getattr(self._n, k), v):
            setattr(self._n, k, v)


class _ReplayInputs:
    __slots__ = ("_c",)

    def __init__(self, coll):
        self._c = coll

    def __getitem__(self, k):
        return _ReplaySocket(self._c[k])

    def __getattr__(self, k):
        return getattr(self._c, k)

    def __iter__(self):
        return (_ReplaySocket(s) for s in self._c)

    def __len__(self):
        return len(self._c)


class _ReplayNode:
    """A node of a tree built again (``_Replay``): reads go to the node; a setting (or an input's value) is written
    only when it differs; its place (``location``) is left where it is."""

    __slots__ = ("_n",)

    def __init__(self, node):
        object.__setattr__(self, "_n", node)

    def __getattr__(self, k):
        if k == "inputs":
            return _ReplayInputs(self._n.inputs)
        return getattr(self._n, k)

    def __setattr__(self, k, v):
        if k == "location":
            return
        if not _same_value(getattr(self._n, k), v):
            setattr(self._n, k, v)


class _Replay:
    """Stands in for a node tree while it is built (task 0202): the build code calls ``nt.nodes.new`` and
    ``nt.links.new`` as on a real tree.

    Record (``order`` None): the nodes are made as always, and the order they were made in is kept (``names``).
    Replay (``order`` = the names of the last build, in that order): no node is made – the n-th ``nodes.new`` hands out
    the n-th node of the last build (of the same kind, else ``_Mismatch``), and only the numbers the build writes
    into it change. The links are compared at the end (``finish``): the same links, no more, no fewer – else
    ``_Mismatch``, and the caller makes the tree new. Making ~700 shader nodes took ~4 s (the sea's water); writing
    their numbers takes a few hundredths of that."""

    def __init__(self, nt, order=None):
        self.tree = nt
        self.made = []
        self.wanted = {}                     # input socket (pointer) -> (output socket, input socket): links asked for
        self.order = None
        if order is not None:
            by_name = {n.name: n for n in nt.nodes}
            try:
                self.order = [by_name[name] for name in order]
            except KeyError:
                raise _Mismatch("a node of the last build is gone") from None
            if len(self.order) != len(nt.nodes):
                raise _Mismatch("the tree has other nodes too")
        self.nodes = _ReplayNodes(self)
        self.links = _ReplayLinks(self)

    @property
    def replaying(self) -> bool:
        return self.order is not None

    def __getattr__(self, k):
        return getattr(self.tree, k)

    def linked_from(self, sock):
        """The output linked into ``sock`` as this build has it (in a replay the tree still has the last build's)."""
        if self.order is not None:
            got = self.wanted.get(sock.as_pointer())
            return got[0] if got else None
        return sock.links[0].from_socket if sock.links else None

    def finish(self) -> None:
        if self.order is None:
            return
        if len(self.made) != len(self.order):
            raise _Mismatch("fewer nodes than the last build")
        have = {}
        for link in self.tree.links:
            have[link.to_socket.as_pointer()] = link.from_socket.as_pointer()
        want = {k: a.as_pointer() for k, (a, _b) in self.wanted.items()}
        if have != want:
            raise _Mismatch("other links than the last build")

    @property
    def names(self) -> list:
        return [n.name for n in self.made]


class _ReplayNodes:
    def __init__(self, rp: _Replay):
        self.rp = rp

    def new(self, kind):
        rp = self.rp
        if rp.order is None:
            n = rp.tree.nodes.new(kind)
            rp.made.append(n)
            return n
        i = len(rp.made)
        if i >= len(rp.order) or rp.order[i].bl_idname != kind:
            raise _Mismatch(f"node {i} is not a {kind}")
        rp.made.append(rp.order[i])
        return _ReplayNode(rp.order[i])

    def clear(self):
        if self.rp.order is None:
            self.rp.tree.nodes.clear()

    def __getattr__(self, k):
        return getattr(self.rp.tree.nodes, k)

    def __iter__(self):
        return iter(self.rp.tree.nodes)


class _ReplayLinks:
    def __init__(self, rp: _Replay):
        self.rp = rp

    def new(self, a, b):
        a, b = getattr(a, "_n", a), getattr(b, "_n", b)
        if self.rp.order is None:
            return self.rp.tree.links.new(a, b)
        self.rp.wanted[b.as_pointer()] = (a, b)          # (a later link into the same input replaces it, as in Blender)
        return None

    def __getattr__(self, k):
        return getattr(self.rp.tree.links, k)


ORDER_KEY = "fr_order"              # on a material / node group: its nodes' names in the order the build made them


def _build_tree(owner, nt, build) -> bool:
    """``build(tree)`` writes the nodes of ``nt`` (``owner``: the material or node group that keeps the order).
    When ``nt`` still has the nodes of its last build, they are kept and only their numbers set (``_Replay``); when
    the build asks for other nodes or links, the tree is made new. True when it was kept."""
    order = owner.get(ORDER_KEY)
    if order is not None and len(nt.nodes):
        try:
            rp = _Replay(nt, list(order))
            build(rp)
            rp.finish()
            return True
        except _Mismatch:
            pass
    nt.nodes.clear()
    rp = _Replay(nt)
    build(rp)
    owner[ORDER_KEY] = rp.names
    return False


class _NT:
    """Small helper to write node trees."""

    def __init__(self, mat, nt=None):
        self.nt = nt if nt is not None else mat.node_tree
        self.nt.nodes.clear()
        self.x = -1200

    def node(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 180
        for k, v in inputs.items():
            if k.startswith("_"):
                setattr(n, k[1:], v)
            else:
                self.set(n, k, v)
        return n

    def set(self, n, name, v):
        if hasattr(v, "bl_idname") or isinstance(v, bpy.types.NodeSocket):
            self.link(v, n.inputs[name])
        else:
            n.inputs[name].default_value = v

    def link(self, a, b):
        self.nt.links.new(a, b)


def _coords(t: _NT, scale=1.0):
    tc = t.node("ShaderNodeTexCoord")
    if scale == 1.0:
        return tc.outputs["Object"]
    vm = t.node("ShaderNodeVectorMath", _operation="SCALE", Vector=tc.outputs["Object"], Scale=scale)
    return vm.outputs["Vector"]


def _noise(t: _NT, scale, detail=4.0, roughness=0.55, vec=None):
    n = t.node("ShaderNodeTexNoise", Scale=scale, Detail=detail, Roughness=roughness)
    if vec is not None:
        t.link(vec, n.inputs["Vector"])
    return n.outputs["Fac"]


def _ramp(t: _NT, fac, a, b, pa=0.3, pb=0.7):
    r = t.node("ShaderNodeMapRange", Value=fac, **{"From Min": pa, "From Max": pb, "To Min": a, "To Max": b})
    return r.outputs["Result"]


def _mix_color(t: _NT, fac, a, b):
    """Colour a where fac = 0, b where fac = 1 (a and b: colours or colour sockets)."""
    m = t.node("ShaderNodeMix", _data_type="RGBA")
    for i, v in ((0, fac), (6, a), (7, b)):            # 0 factor, 6 colour A, 7 colour B
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, m.inputs[i])
        elif isinstance(v, tuple):
            m.inputs[i].default_value = (*v[:3], 1.0)
        else:
            m.inputs[i].default_value = v
    return m.outputs[2]


def _lines(t: _NT, pitch_x=0.0, pitch_y=0.0, width=0.01, axis_z=0.0):
    """1 on thin lines every ``pitch`` metres (seams, joints) along object x and/or y, else 0."""
    tc = t.node("ShaderNodeTexCoord")
    sep = t.node("ShaderNodeSeparateXYZ", Vector=tc.outputs["Object"])
    result = None
    for comp, pitch in (("X", pitch_x), ("Y", pitch_y), ("Z", axis_z)):
        if pitch <= 0:
            continue
        d = t.node("ShaderNodeMath", _operation="DIVIDE", Value=sep.outputs[comp])
        d.inputs[1].default_value = pitch
        f = t.node("ShaderNodeMath", _operation="FRACT", Value=d.outputs[0])
        c = t.node("ShaderNodeMath", _operation="PINGPONG", Value=f.outputs[0])
        c.inputs[1].default_value = 0.5
        lt = t.node("ShaderNodeMath", _operation="LESS_THAN", Value=c.outputs[0])
        lt.inputs[1].default_value = width / pitch / 2
        if result is None:
            result = lt.outputs[0]
        else:
            mx = t.node("ShaderNodeMath", _operation="MAXIMUM", Value=result)
            t.link(lt.outputs[0], mx.inputs[1])
            result = mx.outputs[0]
    return result


def _bump(t: _NT, height, strength=0.3, distance=0.02):
    b = t.node("ShaderNodeBump", Strength=strength, Distance=distance, Height=height)
    return b.outputs["Normal"]


def _principled(t: _NT, color, rough, metal=0.0, normal=None, **extra):
    p = t.node("ShaderNodeBsdfPrincipled")
    t.set(p, "Base Color", color if not isinstance(color, tuple) else (*color[:3], 1.0))
    t.set(p, "Roughness", rough)
    p.inputs["Metallic"].default_value = metal
    if normal is not None:
        t.link(normal, p.inputs["Normal"])
    for k, v in extra.items():
        t.set(p, k.replace("_", " "), v)
    return p.outputs["BSDF"]


def _emission(t: _NT, color, strength):
    e = t.node("ShaderNodeEmission", Color=(*color, 1.0), Strength=strength)
    return e.outputs["Emission"]


def _cutaway(t: _NT):
    """1 where this surface must not be seen by the camera, else 0 (halls only: see CUT_ROLES).

    The camera always sees the machine: everything inside a cone from the camera around the
    machine, nearer than the machine, is left out of the picture; so is the roof structure when
    the camera is above the roof. Only camera rays: light, shadows and reflections stay as they
    are. Objects without the 'fr_cut_r' property are never cut."""
    def sock(n, i, v):
        if isinstance(v, bpy.types.NodeSocket):
            t.link(v, n.inputs[i])
        else:
            n.inputs[i].default_value = v

    def vec(op, a, b=None):
        n = t.node("ShaderNodeVectorMath", _operation=op)
        sock(n, 0, a)
        if b is not None:
            sock(n, 1, b)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH") else n.outputs["Vector"]

    def scale(a, f):
        n = t.node("ShaderNodeVectorMath", _operation="SCALE")
        sock(n, 0, a)
        sock(n, "Scale", f)
        return n.outputs["Vector"]

    def math(op, a, b=None, c=None):
        n = t.node("ShaderNodeMath", _operation=op)
        for i, v in enumerate((a, b, c)):
            if v is not None:
                sock(n, i, v)
        return n.outputs[0]

    def attr(name, out):
        return t.node("ShaderNodeAttribute", _attribute_type="OBJECT", _attribute_name=name).outputs[out]

    centre = attr("fr_cut_c", "Vector")          # machine centre (object space)
    radius = attr("fr_cut_r", "Fac")             # machine radius; 0 = never cut
    roof = attr("fr_roof", "Fac")                # height of the roof structure; 0 = not roof structure
    p = t.node("ShaderNodeTexCoord").outputs["Object"]
    incoming = t.node("ShaderNodeNewGeometry").outputs["Incoming"]      # from the point to the camera
    dist = t.node("ShaderNodeCameraData").outputs["View Distance"]
    # the camera: back from the point along the view ray (also right after a see-through wall)
    c = vec("ADD", p, scale(incoming, dist))
    to_m = vec("SUBTRACT", centre, c)
    length = vec("LENGTH", to_m)
    # q = cos of the angle between the view ray and the line camera -> machine centre
    k = vec("DOT_PRODUCT", incoming, vec("NORMALIZE", to_m))         # = -q
    q = math("MULTIPLY", k, -1.0)
    sin = math("SQRT", math("MAXIMUM", math("MULTIPLY_ADD", q, k, 1.0), 0.0))
    # in the cone (half angle: atan((1.15 x radius + 0.3 m) / distance)) and nearer than the centre
    in_cone = math("LESS_THAN", math("MULTIPLY", sin, length),
                   math("MULTIPLY", math("MULTIPLY_ADD", radius, 1.15, 0.3), q))
    nearer = math("LESS_THAN", math("MULTIPLY", dist, q), length)
    sep = t.node("ShaderNodeSeparateXYZ")
    t.link(c, sep.inputs[0])
    above = math("MULTIPLY", math("GREATER_THAN", roof, 0.0), math("GREATER_THAN", sep.outputs["Z"], roof))
    cut = math("MAXIMUM", math("MULTIPLY", in_cone, nearer), above)
    camera_ray = t.node("ShaderNodeLightPath").outputs["Is Camera Ray"]
    return math("MULTIPLY", math("MULTIPLY", math("GREATER_THAN", radius, 0.0), camera_ray), cut)


def _output(t: _NT, shader, one_sided: bool = False, cutaway: bool = True):
    if one_sided:                   # seen from behind: see-through (halls seen from outside)
        geo = t.node("ShaderNodeNewGeometry")
        tr = t.node("ShaderNodeBsdfTransparent")
        mix = t.node("ShaderNodeMixShader", Fac=geo.outputs["Backfacing"])
        t.link(shader, mix.inputs[1])
        t.link(tr.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    if cutaway:
        tr = t.node("ShaderNodeBsdfTransparent")
        mix = t.node("ShaderNodeMixShader", Fac=_cutaway(t))
        t.link(shader, mix.inputs[1])
        t.link(tr.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])


def _paint(t, color, rough=0.45, var=0.04, scale=3.0, normal=None):
    """Painted surface with a little colour and gloss variation."""
    n = _noise(t, scale, 3.0, 0.5, _coords(t))
    col = _mix_color(t, _ramp(t, n, 0.0, 1.0), tuple(c * (1 - var) for c in color), tuple(min(1.0, c * (1 + var)) for c in color))
    return _principled(t, col, _ramp(t, n, rough * 0.85, rough * 1.15), normal=normal)


def _make(key: str, mat, nt=None) -> None:
    t = _NT(mat, nt)
    one_sided = False
    emission = False
    cutaway = True
    if key in ("floor_epoxy", "floor_epoxy_green"):
        base = _srgb(0.70, 0.71, 0.70) if key == "floor_epoxy" else _srgb(0.42, 0.52, 0.47)
        n = _noise(t, 0.6, 4.0, 0.6, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1), tuple(c * 0.93 for c in base), base)
        shader = _principled(t, col, _ramp(t, _noise(t, 2.0, 3.0, 0.5, _coords(t)), 0.14, 0.32),
                             Coat_Weight=0.3, Coat_Roughness=0.08)
    elif key in ("floor_concrete", "concrete"):
        base = _srgb(0.62, 0.61, 0.58) if key == "floor_concrete" else _srgb(0.6, 0.59, 0.56)
        n = _noise(t, 0.35, 6.0, 0.65, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1, 0.35, 0.65), tuple(c * 0.78 for c in base), base)
        joints = _lines(t, 6.0, 6.0, 0.012)
        col = _mix_color(t, joints, col, (0.12, 0.12, 0.12))
        if key == "concrete":            # wet and darker towards the water line
            sep = t.node("ShaderNodeSeparateXYZ", Vector=t.node("ShaderNodeTexCoord").outputs["Object"])
            wet = t.node("ShaderNodeMapRange", Value=sep.outputs["Z"], **{"From Min": -0.3, "From Max": -1.5,
                                                                          "To Min": 0.0, "To Max": 0.7})
            col = _mix_color(t, wet.outputs[0], col, (0.08, 0.085, 0.08))
        shader = _principled(t, col, _ramp(t, n, 0.55, 0.85), normal=_bump(t, joints, 0.4, 0.01))
    elif key == "deck":
        base = _srgb(0.33, 0.38, 0.36)
        n = _noise(t, 0.25, 6.0, 0.6, _coords(t))
        col = _mix_color(t, _ramp(t, n, 0, 1, 0.3, 0.75), tuple(c * 0.75 for c in base), base)
        seams = _lines(t, 6.0, 1.8, 0.02)
        grit = _noise(t, 60.0, 2.0, 0.5, _coords(t))
        h = t.node("ShaderNodeMath", _operation="MULTIPLY_ADD", Value=seams)
        h.inputs[1].default_value = 1.0
        t.link(grit, h.inputs[2])
        shader = _principled(t, col, 0.75, normal=_bump(t, h.outputs[0], 0.25, 0.01))
    elif key == "water":
        shader = _water_shader(t, mat)
        cutaway = False
    elif key in ("wall_panel", "wall_panel_out"):
        seams = _lines(t, 1.0, 1.0, 0.012)
        shader = _principled(t, _srgb(0.86, 0.87, 0.86), 0.5, normal=_bump(t, seams, 0.4, 0.01))
        one_sided = key == "wall_panel"
    elif key == "wall_dado":
        shader = _principled(t, _ral("RAL 7016"), 0.45)
        one_sided = True
    elif key == "roof":
        ribs = _lines(t, 0.0, 0.33, 0.06)
        shader = _principled(t, _srgb(0.7, 0.71, 0.71), 0.5, metal=0.5, normal=_bump(t, ribs, 0.5, 0.02))
        one_sided = True
    elif key == "door":
        slats = _lines(t, 0.0, 0.0, 0.015, axis_z=0.12)
        shader = _principled(t, _ral("RAL 9006"), 0.4, metal=0.6, normal=_bump(t, slats, 0.5, 0.01))
        one_sided = True
    elif key == "window":
        shader = _emission(t, (0.85, 0.92, 1.0), 1.6)
        one_sided = emission = True
    elif key == "skylight":
        shader = _emission(t, (0.95, 0.97, 1.0), 2.5)
        one_sided = emission = True
    elif key == "light":
        shader = _emission(t, (1.0, 0.97, 0.92), 6.0)
        emission = True
    elif key in ("galvanized", "rail_steel", "light_housing"):
        base = {"galvanized": (0.62, 0.64, 0.65), "rail_steel": (0.42, 0.42, 0.42),
                "light_housing": (0.8, 0.8, 0.8)}[key]
        n = _noise(t, 4.0, 4.0, 0.6, _coords(t))
        shader = _principled(t, base, _ramp(t, n, 0.25, 0.45), metal=1.0)
    elif key in ("container_blue", "container_red", "container_green", "container_white", "container_grey"):
        colour = {"container_blue": "RAL 5010", "container_red": "RAL 3009", "container_green": "RAL 6005",
                  "container_white": "RAL 9002", "container_grey": "RAL 7037"}[key]
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", _wave_profile="SIN",
                      Scale=3.6, Vector=_coords(t))
        shader = _paint(t, _ral(colour), 0.5, 0.06, 1.5, normal=_bump(t, wave.outputs["Fac"], 0.6, 0.03))
    elif key == "kerb" or key == "barrier":
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS",
                      _bands_direction="X" if key == "kerb" else "DIAGONAL", _wave_profile="SAW",
                      Scale=0.6 if key == "kerb" else 1.5, Vector=_coords(t))
        stripe = t.node("ShaderNodeMath", _operation="GREATER_THAN", Value=wave.outputs["Fac"])
        stripe.inputs[1].default_value = 0.5
        other = (0.02, 0.02, 0.02) if key == "kerb" else (0.85, 0.85, 0.85)
        first = _ral("RAL 1023") if key == "kerb" else _ral("RAL 3020")
        shader = _principled(t, _mix_color(t, stripe.outputs[0], first, other), 0.45)
    elif key == "wood":
        wave = t.node("ShaderNodeTexWave", _wave_type="BANDS", _bands_direction="X", Scale=6.0, Distortion=6.0,
                      Detail=3.0, Vector=_coords(t))
        col = _mix_color(t, _ramp(t, wave.outputs["Fac"], 0, 1, 0.2, 0.9), _srgb(0.56, 0.42, 0.26), _srgb(0.74, 0.6, 0.4))
        shader = _principled(t, col, 0.75)
    elif key == "hull":
        shader = _paint(t, _ral("RAL 5011"), 0.35)
    elif key == "hull_red":
        shader = _paint(t, _ral("RAL 3011"), 0.4)
    elif key == "glass_dark":
        shader = _principled(t, (0.01, 0.012, 0.014), 0.04, Specular_IOR_Level=0.6)
    elif key == "mannequin":
        shader = _principled(t, _srgb(0.68, 0.68, 0.69), 0.55)
    else:
        colours = {
            "steel_column": ("RAL 7035", 0.45), "crane_yellow": ("RAL 1003", 0.4), "rail_yellow": ("RAL 1003", 0.4),
            "line_yellow": ("RAL 1023", 0.5), "line_white": ("RAL 9016", 0.5), "bollard": ("RAL 9005", 0.5),
            "rubber": ("#1A1A1A", 0.85), "machine_body": ("RAL 7035", 0.35), "machine_dark": ("RAL 7016", 0.4),
            "machine_blue": ("RAL 5015", 0.35), "cabinet_grey": ("RAL 7035", 0.4), "cabinet_red": ("RAL 3000", 0.35),
            "rack_blue": ("RAL 5010", 0.4), "rack_orange": ("RAL 2004", 0.4), "cardboard": ("#A07A4E", 0.85),
            "wrap": ("#D8DCDF", 0.2), "bin_blue": ("RAL 5015", 0.35), "bench_top": ("#B08A5E", 0.5),
            "primer": ("RAL 3009", 0.6), "deckhouse": ("RAL 9010", 0.4), "lamp_head": ("RAL 7037", 0.45),
            "container_frame": ("RAL 7021", 0.5), "barrier_frame": ("RAL 1023", 0.4),
        }
        colour, rough = colours.get(key, ("RAL 7035", 0.5))
        shader = _paint(t, _ral(colour), rough)
    _output(t, shader, one_sided, cutaway and not one_sided and key not in NEVER_IN_THE_WAY)
    mat.use_backface_culling = one_sided
    if emission:
        for owner in (mat, getattr(mat, "cycles", None)):
            if owner is not None and hasattr(owner, "emission_sampling"):
                owner.emission_sampling = "NONE"     # looks bright, but does not light the scene (no extra noise)
                break


def material(key: str) -> bpy.types.Material:
    name = MAT_PREFIX + key
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    _make(key, mat)
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = key
    return mat


# =============================================================================
# the sea (task 0109: built from core/sea.py – a wind-wave spectrum, white caps from the wind)
# =============================================================================


def _sea_numbers(state: str) -> dict:
    """Today's two quick choices in numbers (``SEA``; the Web 3D page reads them): Beaufort, the significant wave
    height, the waves' amplitude sum and longest wavelengths, the white-cap threshold of ``core/sea.py``."""
    bft = sea_core.STATES[state]
    comps = sea_core.components(bft)
    lengths = sorted((2 * math.pi / c[3] for c in comps), reverse=True)[:6]
    return dict(bft=bft, hs=round(sea_core.hs(comps), 3), amp=round(sum(c[0] for c in comps), 3),
                lengths=tuple(round(v, 2) for v in lengths), foam=round(sea_core.foam_threshold(bft), 4),
                coverage=round(sea_core.whitecap_coverage(sea_core.bft_to_ms(bft)), 5),
                bump=OLD_BUMP[state], chop=OLD_CHOP[state], page_foam=OLD_FOAM[state])


OLD_BUMP = {"CALM": 0.12, "ROUGH": 0.35}     # the ripple strength the Web 3D page (task 0106) still draws its sea with
OLD_CHOP = {"CALM": 0.6, "ROUGH": 1.6}
OLD_FOAM = {"CALM": 0.82, "ROUGH": 0.55}    # (the page's white caps still follow the crest rule of before)
SEA = {state: _sea_numbers(state) for state in sea_core.STATES}
SPRAY_FROM = 5.5                   # Beaufort: spray starts (full at 9)
HULL_FOAM_LIFT = 0.04              # m: the hull foam lies this much above the water (no flicker)
RIPPLE = 0.18                      # bump strength of the small ripples near the camera


def sea_wind(s) -> tuple[float, float]:
    """(Beaufort, degrees from +x the waves run towards) of the sea: Calm / Rough fixed, From the wind = the wind
    of Weather & time (its strength and direction)."""
    if s.sea_state == "WIND":
        st = _weather_state(s)
        if st is not None:
            wx, wy = weather_core.wind_vector(st)
            return float(st.wind), math.degrees(math.atan2(wy, wx))
    return sea_core.STATES.get(s.sea_state, sea_core.STATES["CALM"]), sea_core.DEFAULT_TOWARD


def _weather_state(s):
    try:
        from . import weather
        return weather.state(s.id_data)
    except Exception:              # (an older project being read, or no weather settings)
        return None


def _weather_on(s) -> bool:
    w = getattr(s, "weather", None)
    return bool(w is not None and w.enabled)


def _spray_wind(s):
    """(Beaufort, unit wind x, y) when spray is wanted (Weather & time on, Spray ticked, Beaufort >= 5.5)."""
    if not _weather_on(s) or not s.weather.spray:
        return None
    st = _weather_state(s)
    if st is None or st.wind < SPRAY_FROM:
        return None
    return float(st.wind), weather_core.wind_vector(st)


def _speed(s) -> float:
    """Knots the vessel sails ahead (5 Scene & Render > Vessel at work, task 0154: the speed of Weather & time, also
    with Weather & time off)."""
    return _work().speed_now(s.id_data)


def _max_speed(s) -> float:
    """The fastest the vessel sails: now, or in a Vessel at work step of any animation (the hull foam's reach)."""
    v = _speed(s)
    for b in _work()._steps(s.id_data):
        if b.vw_mode == "AHEAD":
            v = max(v, float(b.vw_speed))
    return v


def _waves(state: str, swell=(), wind=None) -> list[tuple[float, float, float, float, float]]:
    """(amplitude, direction x, direction y, wave number, phase) of each wave of the sea (``core/sea.py``): Calm =
    Beaufort 3, Rough = Beaufort 6; WIND: ``wind`` = (Beaufort, degrees towards), or the current scene's wind.
    ``swell``: the long waves vessel motion adds (task 0085), after the sea's own."""
    if state == "WIND":
        if wind is None:
            scene = bpy.context.scene
            wind = sea_wind(scene.fresing) if scene is not None else (sea_core.STATES["CALM"], sea_core.DEFAULT_TOWARD)
        own = sea_core.components(*wind)
    else:
        own = sea_core.of_state(state)
    return list(own) + [tuple(float(v) for v in w) for w in swell]


def _sea_rings(detailed: bool, near: float) -> tuple[int, list[float]]:
    n = 256 if detailed else 48
    rings = []
    if detailed:
        r = 0.4
        step = 1 + 2 * math.pi / n
        while r < near * 1.6:
            rings.append(r)
            r *= step
    else:
        rings = [0.5]
    r = rings[-1]
    while r < S.SEA_RADIUS:
        r = min(S.SEA_RADIUS, r * 1.45)
        rings.append(r)
    return n, rings


def _sea_mesh(name: str, detailed: bool, near: float) -> bpy.types.Mesh:
    n, rings = _sea_rings(detailed, near)
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    R = np.array(rings)
    rim = np.clip((R - 0.75 * S.SEA_RADIUS) / (0.25 * S.SEA_RADIUS), 0, 1)
    z = S.SEA_RIM * rim * rim                     # the far edge rises: no gap below the horizon
    verts = [np.zeros((1, 3))]
    for r, zz in zip(R, z):
        verts.append(np.stack([r * np.cos(ang), r * np.sin(ang), np.full(n, zz)], axis=1))
    verts = np.concatenate(verts)
    i = np.arange(n)
    fan = np.stack([np.zeros(n, int), 1 + i, 1 + (i + 1) % n], axis=1)
    quads = np.concatenate([np.stack([1 + j * n + i, 1 + (j + 1) * n + i, 1 + (j + 1) * n + (i + 1) % n,
                                      1 + j * n + (i + 1) % n], axis=1) for j in range(len(rings) - 1)])
    m = _Mesh()
    m.verts.append(verts)                          # (the fan's triangles first, then the rings' quads, as before)
    m.n = len(verts)
    m.faces += [fan, quads]
    m.mats += [0] * (len(fan) + len(quads))
    m.smooth += [True] * (len(fan) + len(quads))
    return m.to_mesh(name)


def _time_driver(owner, path: str, scene, speed: float, index: int = -1) -> None:
    """``owner.path`` = the scene's time in seconds x ``speed`` (a simple expression: scripts off, any frame rate)."""
    fc = owner.driver_add(path, index) if index >= 0 else owner.driver_add(path)
    d = fc.driver
    d.type = "SCRIPTED"
    while d.variables:
        d.variables.remove(d.variables[0])
    for name, prop in (("fps", "render.fps"), ("b", "render.fps_base")):
        v = d.variables.new()
        v.name = name
        v.type = "SINGLE_PROP"
        v.targets[0].id_type = "SCENE"
        v.targets[0].id = scene
        v.targets[0].data_path = prop
    d.expression = f"frame * b / max(fps, 1) * {speed:.5f}"


def _rows_hash(*parts) -> str:
    import hashlib
    text = repr([[round(float(v), 6) for v in row] if isinstance(row, (tuple, list)) else row
                 for part in parts for row in (part if isinstance(part, (list, tuple)) else [part])])
    return hashlib.md5(text.encode()).hexdigest()[:8]


class _NB:
    """Writes math into a shader or a geometry node tree (the same Math / Vector Math nodes in both)."""

    def __init__(self, nt):
        self.nt = nt
        self.i = 0

    def new(self, kind, **props):
        n = self.nt.nodes.new(kind)
        for k, v in props.items():
            setattr(n, k, v)
        n.location = (-2400 + 200 * (self.i // 40), 300 - 40 * (self.i % 40))
        self.i += 1
        return n

    def put(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif v is not None:
            sock.default_value = v

    def math(self, op, a, b=None, c=None):
        n = self.new("ShaderNodeMath", operation=op)
        for i, v in enumerate((a, b, c)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def vec(self, op, a, b=None, c=None):
        n = self.new("ShaderNodeVectorMath", operation=op)
        for i, v in enumerate((a, b, c)):
            self.put(n.inputs[i], v)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def comb(self, x, y, z):
        n = self.new("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self.put(n.inputs[i], v)
        return n.outputs[0]

    def sep(self, v):
        n = self.new("ShaderNodeSeparateXYZ")
        self.put(n.inputs[0], v)
        return n.outputs

    def ramp(self, x, a, b, lo=0.0, hi=1.0, smooth=False):
        """lo at x <= a … hi at x >= b (a, b, lo, hi: numbers or sockets)."""
        n = self.new("ShaderNodeMapRange")
        if smooth:
            n.interpolation_type = "SMOOTHSTEP"
        n.clamp = True
        self.put(n.inputs["Value"], x)
        self.put(n.inputs["From Min"], a)
        self.put(n.inputs["From Max"], b)
        self.put(n.inputs["To Min"], lo)
        self.put(n.inputs["To Max"], hi)
        return n.outputs["Result"]

    def acc(self, total, v, f):
        """total + v * f (total None: v * f)."""
        return self.math("MULTIPLY", v, f) if total is None else self.math("MULTIPLY_ADD", v, f, total)

    def phase(self, P, kx, ky, wt, ph):
        return self.math("ADD", self.vec("DOT_PRODUCT", P, (kx, ky, wt)), ph)

    def term(self, P, tm):
        """cos of a foam-field term's angle (``core/sea.Term.angle``: with a streak's meander)."""
        p = self.phase(P, tm.kx, tm.ky, tm.wt, tm.phase)
        if tm.m_amp:
            p = self.math("MULTIPLY_ADD", self.math("SINE", self.phase(P, tm.m_kx, tm.m_ky, tm.m_wt, tm.m_phase)),
                          tm.m_amp, p)
        return self.math("COSINE", p)


def _height_sig(rows, near: float) -> str:
    """Which nodes ``_height_sum`` makes for these waves (task 0202: a kept node group is only given new numbers when
    its nodes are the same kind): per wave whether it is drawn and whether it fades out early."""
    flags = "".join("-" if 2 * math.pi / k < 1.0 else ("f" if 10 * math.pi / k < 1.6 * near else "w")
                    for _a, _dx, _dy, k, _ph in rows)
    return _rows_hash(flags)


def _height_sum(b: _NB, x, y, t, rows, near: float):
    """Height of the sea at (x, y) and time t (sockets): every wave of 1 m or longer, each faded out where the
    rings get too coarse for it, the whole faded out between ``near`` and 1.6 x near (the material's normals carry
    the waves on to the horizon)."""
    P = b.comb(x, y, t)
    r = b.vec("LENGTH", b.comb(x, y, 0.0))
    total = None
    for a, dx, dy, k, ph in rows:
        lam = 2 * math.pi / k
        if lam < 1.0:
            continue
        h = b.math("SINE", b.phase(P, k * dx, k * dy, -math.sqrt(sea_core.G * k), ph))
        if 5.0 * lam < 1.6 * near:
            h = b.math("MULTIPLY", h, b.ramp(r, 5.0 * lam, 8.0 * lam, 1.0, 0.0))
        total = b.acc(total, h, a)
    if total is None:
        return 0.0
    return b.math("MULTIPLY", total, b.ramp(r, near, 1.6 * near, 1.0, 0.0, smooth=True))


def _scene_seconds(b: _NB, moving: bool):
    if moving:
        return b.new("GeometryNodeInputSceneTime").outputs["Seconds"]
    return 0.0


def _waves_group(state: str, moving: bool, near: float, swell=(), wind=None) -> bpy.types.NodeTree:
    """Geometry nodes: the waves (a sum of travelling sine waves, ``core/sea.py``) near the machine, flat far
    away. ``swell``: the long waves of vessel motion (task 0085); they lift the sea but make no foam."""
    rows = _waves(state, swell, wind)
    name = f"{WAVES_GROUP} {state.lower()}{' moving' if moving else ''} {near:.0f} {_rows_hash(rows)}"
    ng = bpy.data.node_groups.get(name)
    if ng is not None:
        return ng
    # task 0202: a waves group no object uses any more (the sea was just made again) keeps its nodes, new numbers
    sig = f"{'m' if moving else 's'} {_height_sig(rows, near)}"
    ng = next((g for g in bpy.data.node_groups if g.get("fr_env") == "waves" and not g.users and g.library is None
               and g.get(ORDER_KEY) is not None and g.get("fr_sig") == sig), None)
    if ng is not None:
        ng.name = name
    else:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng["fr_env"] = "waves"
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    ng["fr_sig"] = sig

    def build(nt):
        b = _NB(nt)
        gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
        xyz = b.sep(b.new("GeometryNodeInputPosition").outputs[0])
        h = _height_sum(b, xyz["X"], xyz["Y"], _scene_seconds(b, moving), rows, near)
        setp = b.new("GeometryNodeSetPosition")
        b.put(setp.inputs["Geometry"], gin.outputs[0])
        b.put(setp.inputs["Offset"], b.comb(0.0, 0.0, h))
        b.put(gout.inputs[0], setp.outputs[0])
    _build_tree(ng, ng, build)
    return ng


# ---- the water's material ----------------------------------------------------


def _foam_threshold_socket(b: _NB, bft: float, weather: bool):
    """The white caps' threshold: the weather's ``foam`` channel (a View Layer attribute, so a Weather & time step
    can key it) when Weather & time is on, else the sea state's own (``core/sea.foam_threshold``)."""
    const = sea_core.foam_threshold(bft)
    if not weather:
        return const
    at = b.new("ShaderNodeAttribute", attribute_type="VIEW_LAYER", attribute_name=weather_core.prop("foam"))
    v = at.outputs["Fac"]
    missing = b.math("COMPARE", v, 0.0, 1e-7)           # no channel (yet): the sea state's own threshold
    return b.math("MULTIPLY_ADD", missing, const, v)


def _wake_shader(b: _NB, x, y, t):
    """Foam of the wake behind the stern (``core/sea.wake``): its place and the speed from the sea object."""
    w = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_wake").outputs["Vector"]
    v = _work().speed_socket(b)          # task 0154: the speed is a channel (a Vessel at work step keys it)
    ws = b.sep(w)
    stern, mid, hb = ws["X"], ws["Y"], ws["Z"]
    flip = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_wake_flip").outputs["Fac"]
    x = b.math("MULTIPLY", x, b.math("MULTIPLY_ADD", flip, -2.0, 1.0))      # task 0082: bow at +x (stern at min x)
    xb = b.math("SUBTRACT", x, stern)
    xp = b.math("MAXIMUM", xb, 0.0)
    ay = b.math("ABSOLUTE", b.math("SUBTRACT", y, mid))
    length = b.math("MULTIPLY_ADD", v, 12.0, 20.0)
    width = b.math("MULTIPLY", hb, b.math("MULTIPLY_ADD", b.math("SQRT", xp), 0.09, 0.85))
    fade = b.math("EXPONENT", b.math("DIVIDE", b.math("MULTIPLY", xp, -1.0), length))
    band = b.math("MULTIPLY", b.ramp(ay, b.math("MULTIPLY", width, 0.55), width, 1.0, 0.0, smooth=True), fade)
    arm_d = b.math("ABSOLUTE", b.math("SUBTRACT", ay, b.math("MULTIPLY_ADD", xp, math.tan(sea_core.KELVIN), hb)))
    arm_w = b.math("MULTIPLY_ADD", xp, 0.03, 1.5)
    arm_fade = b.math("EXPONENT", b.math("DIVIDE", b.math("MULTIPLY", xp, -1.0), b.math("MULTIPLY", length, 0.7)))
    arms = b.math("MULTIPLY", b.math("MULTIPLY", b.ramp(arm_d, 0.0, arm_w, 1.0, 0.0, smooth=True), arm_fade),
                  sea_core.ARMS)
    on = b.math("MULTIPLY", b.math("GREATER_THAN", xb, 0.0), b.ramp(v, 0.0, 2.0, 0.0, 1.0, smooth=True))
    wake = b.math("MULTIPLY", b.math("MAXIMUM", band, arms), on)
    # the foam flows away from the stern with the water (the vessel's speed)
    flow = b.comb(b.math("MULTIPLY_ADD", b.math("MULTIPLY", v, sea_core.KNOT), b.math("MULTIPLY", t, -1.0), x), y, 0.0)
    n = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
    n.inputs["Scale"].default_value = 0.22
    n.inputs["Detail"].default_value = 6.0
    n.inputs["Roughness"].default_value = 0.65
    b.put(n.inputs["Vector"], flow)
    b.put(n.inputs["W"], b.math("MULTIPLY", t, 0.12))
    # task 0154: further behind the foam breaks up into patches (the lace's threshold rises with the distance)
    late = b.ramp(xp, 0.0, b.math("MULTIPLY", length, 1.5), 0.0, 0.18)
    lace = b.ramp(n.outputs["Fac"], b.math("ADD", late, 0.36), b.math("ADD", late, 0.64), 0.0, 1.0)
    return b.math("MULTIPLY", b.ramp(wake, 0.0, 0.8, 0.0, 1.0), lace)


def _water_shader(t: _NT, mat):
    """Deep-water colour, Fresnel reflection of the sky (IOR 1.333), the waves' normals worked out from their
    slopes (no repeat, faded with distance where a wave is smaller than a pixel), small ripples near the camera,
    light through the crests, white caps from ``core/sea.py`` and the wake."""
    b = _NB(t.nt)
    rows = [tuple(r) for r in json.loads(mat.get("fr_waves", "[]"))]
    n_own = int(mat.get("fr_n_own", len(rows)))
    own, swell = rows[:n_own], rows[n_own:]
    bft = float(mat.get("fr_bft", 3.0))
    toward = float(mat.get("fr_toward", sea_core.DEFAULT_TOWARD))
    foam_on, weather, wake = bool(mat.get("fr_foam")), bool(mat.get("fr_sea_weather")), bool(mat.get("fr_wake"))
    co = b.new("ShaderNodeTexCoord").outputs["Object"]
    xyz = b.sep(co)
    x, y = xyz["X"], xyz["Y"]
    tv = b.new("ShaderNodeValue")
    tv.name = "fr_time"
    tv.outputs[0].default_value = 0.0
    time = tv.outputs[0]
    P = b.comb(x, y, time)
    dist = b.new("ShaderNodeCameraData").outputs["View Distance"]

    def fade(lam):                    # a wave smaller than about a pixel: its slope fades out (no sparkle, no moiré)
        # (one ramp per wave, task 0202: the same nodes whatever the sea, so a new sea state only sets numbers)
        lb = 2.0 ** (round(math.log2(max(lam, 0.05)) * 2) / 2)
        return b.ramp(dist, 150.0 * lb, 400.0 * lb, 1.0, 0.0)

    field = sea_core.foam_field(own, bft, toward) if (foam_on and own) else None
    grad, height, F = None, None, None
    for i, (a, dx, dy, k, ph) in enumerate(own + swell):
        p = b.phase(P, k * dx, k * dy, -math.sqrt(sea_core.G * k), ph)
        c = b.math("COSINE", p)
        g = b.vec("MULTIPLY", (a * k * dx, a * k * dy, 0.0), b.math("MULTIPLY", c, fade(2 * math.pi / k)))
        grad = g if grad is None else b.vec("ADD", grad, g)
        if i < n_own:
            s = b.math("SINE", p)
            height = b.acc(height, s, a)
            if field is not None:
                F = b.acc(F, s, field.terms[i].c_sin)
    if field is not None:
        for tm in field.terms[n_own:]:
            F = b.acc(F, b.term(P, tm), tm.c_cos)
    normal = b.vec("NORMALIZE", b.vec("SUBTRACT", (0.0, 0.0, 1.0), grad)) if grad is not None else None
    # small ripples near the camera (shorter than the waves above; Blender noise: only the look, never the foam)
    rip = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
    rip.inputs["Scale"].default_value = 1.3
    rip.inputs["Detail"].default_value = 4.0
    rip.inputs["Roughness"].default_value = 0.6
    b.put(rip.inputs["Vector"], co)
    b.put(rip.inputs["W"], b.math("MULTIPLY", time, 0.45))
    bump = b.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 0.06
    b.put(bump.inputs["Strength"], b.ramp(dist, 25.0, 250.0, RIPPLE, 0.0))
    b.put(bump.inputs["Height"], rip.outputs["Fac"])
    if normal is not None:
        b.put(bump.inputs["Normal"], normal)
    normal = bump.outputs["Normal"]
    # light through the thin top of a crest
    sig = math.sqrt(sum(r[0] ** 2 for r in own) / 2.0) if own else 1.0
    crest = b.ramp(height, 1.0 * sig, 3.0 * sig, 0.0, 0.55, smooth=True) if height is not None else 0.0
    deep = sea_core.DEEP
    lit = tuple(d + s for d, s in zip(deep, sea_core.SCATTER))
    col = _mix_color(t, crest, deep, lit)
    foam = None
    if F is not None:
        th = _foam_threshold_socket(b, bft, weather)
        caps = b.ramp(F, th, b.math("ADD", th, sea_core.EDGE), 0.0, 1.0, smooth=True)
        n = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
        n.inputs["Scale"].default_value = 0.45
        n.inputs["Detail"].default_value = 6.0
        n.inputs["Roughness"].default_value = 0.65
        b.put(n.inputs["Vector"], co)
        b.put(n.inputs["W"], b.math("MULTIPLY", time, 0.25))
        foam = b.math("MULTIPLY", caps, b.ramp(n.outputs["Fac"], 0.32, 0.68, 0.45, 1.0))
    if wake and foam_on:
        w = _wake_shader(b, x, y, time)
        foam = w if foam is None else b.math("MAXIMUM", foam, w)
    work = json.loads(mat.get("fr_vw", "") or "{}")
    if work and foam_on:                 # task 0154: the Kelvin waves, the thrusters' jets
        wf, wh = _work().water_nodes(b, x, y, time, dist, work)
        if wf is not None:
            foam = wf if foam is None else b.math("MAXIMUM", foam, wf)
        if wh is not None:
            bump2 = b.new("ShaderNodeBump")
            bump2.inputs["Distance"].default_value = 1.0
            bump2.inputs["Strength"].default_value = 1.0
            b.put(bump2.inputs["Height"], wh)
            b.put(bump2.inputs["Normal"], normal)
            normal = bump2.outputs["Normal"]
    rough = b.ramp(dist, 20.0, 3000.0, *sea_core.ROUGHNESS)
    if foam is not None:
        col = _mix_color(t, foam, col, sea_core.FOAM)
        rough = b.ramp(foam, 0.0, 1.0, rough, 0.6)
    p = _principled(t, col, rough, normal=normal, IOR=1.333)
    return p


def _water_sig(own, swell, bft: float, toward: float, foam: bool) -> str:
    """The kind of nodes the water's shader has for these waves (``_water_shader``): counts of waves, swell rows and
    white-cap terms (with a meander from about Beaufort 7)."""
    field = sea_core.foam_field(own, bft, toward) if (foam and own) else None
    terms = (len(field.terms), sum(1 for tm in field.terms if tm.m_amp)) if field is not None else (0, 0)
    return f"{len(own)} {len(swell)} {terms[0]} {terms[1]}"


def _spare_water(foam: bool, moving: bool, weather: bool, wake: bool, cut: bool, work: bool, sig: str):
    """A water material no object uses any more (the sea it was made for was just made again) with the same kind of
    nodes: kept and given the new numbers (task 0202), instead of making ~700 nodes again. None: none to spare."""
    want = (foam, moving, weather, wake, cut, work, sig)
    for mat in bpy.data.materials:
        if (mat.get("fr_env") != "water" or mat.users or mat.get(ORDER_KEY) is None
                or mat.get("fr_env_version") != MAT_VERSION or mat.library is not None):
            continue
        has = (bool(mat.get("fr_foam")), bool(mat.get("fr_moving")), bool(mat.get("fr_sea_weather")),
               bool(mat.get("fr_wake")), bool(mat.get("fr_seacut")), bool(mat.get("fr_vw")), mat.get("fr_sig"))
        if has == want:
            return mat
    return None


def _water_material(scene, state: str, foam: bool, moving: bool, wind=None, swell=(), weather: bool = False,
                    wake: bool = False, cut: bool = False, work: dict | None = None) -> bpy.types.Material:
    bft, toward = wind if wind is not None else (sea_core.STATES.get(state, 3.0), sea_core.DEFAULT_TOWARD)
    own = _waves(state, (), (bft, toward))
    rows = own + [tuple(float(v) for v in w) for w in swell]
    name = (f"{MAT_PREFIX}water {state.lower()}{f' b{bft:.1f} d{toward:.0f}' if state == 'WIND' else ''}"
            f"{' foam' if foam else ''}{' moving' if moving else ''}{' weather' if weather else ''}"
            f"{' wake' if wake else ''}{' swell ' + _rows_hash(swell) if swell else ''}"
            f"{' work ' + _rows_hash(_work().layout_json(work)) if work else ''}{' cut' if cut else ''}")
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        sig = _water_sig(own, swell, bft, toward, foam)
        mat = _spare_water(foam, moving, weather, wake, cut, bool(work), sig)
        if mat is not None:
            mat.name = name
        else:
            mat = bpy.data.materials.new(name)
    mat["fr_sea_state"] = state
    mat["fr_foam"] = foam
    mat["fr_bft"] = float(bft)
    mat["fr_toward"] = float(toward)
    mat["fr_sea_weather"] = bool(weather)
    mat["fr_wake"] = bool(wake)
    mat["fr_vw"] = _work().layout_json(work) if work else ""
    mat["fr_waves"] = json.dumps([[round(float(v), 7) for v in r] for r in rows])
    mat["fr_n_own"] = len(own)
    mat["fr_moving"] = bool(moving)
    mat["fr_sig"] = _water_sig(own, swell, bft, toward, foam)
    try:
        mat.use_nodes = True
    except Exception:
        pass

    def build(nt):
        _make("water", mat, nt)
        if cut:                                    # task 0081: see-through inside the cut-away box
            _add_box_cut(mat, from_below=True, nt=nt)
    mat["fr_replayed"] = _build_tree(mat, mat.node_tree, build)
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "water"
    node = mat.node_tree.nodes.get("fr_time")
    if node is not None:
        if moving:
            _time_driver(node.outputs[0], "default_value", scene, 1.0)
        else:
            node.outputs[0].default_value = 0.0
    return mat


# ---- hull foam ---------------------------------------------------------------


def _convex_hull(pts: np.ndarray) -> np.ndarray:
    """Corners of the convex hull of 2D points, anticlockwise (Andrew's monotone chain)."""
    pts = np.unique(np.round(pts, 2), axis=0)
    if len(pts) < 3:
        return pts
    order = np.lexsort((pts[:, 1], pts[:, 0]))
    p = pts[order]

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (q[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (q[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(tuple(q))
        return out
    lower, upper = half(p), half(p[::-1])
    return np.array(lower[:-1] + upper[:-1], float)


def _resample(poly: np.ndarray, step: float = 1.0) -> np.ndarray:
    """A closed polygon with points about ``step`` apart."""
    closed = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    total = float(seg.sum())
    if total <= 1e-6:
        return poly
    n = max(16, int(total / step))
    s = np.concatenate([[0.0], np.cumsum(seg)])
    u = np.linspace(0.0, total, n, endpoint=False)
    return np.stack([np.interp(u, s, closed[:, 0]), np.interp(u, s, closed[:, 1])], axis=1)


def _waterline(scene, s, kind: str, root, level: float):
    """The outline (x, y in the surroundings' frame, anticlockwise) where the hull meets the water: the Vessel
    deck's hull, or on the open sea the convex hull of the model's points within 0.6 m of the water (measured on
    a still sea). None: nothing touches the water."""
    if kind == "DECK":
        mn, mx = np.array(root["fr_min"]), np.array(root["fr_max"])
        lay = S.build("DECK", tuple(float(v) for v in np.maximum(mx - mn, 0.05)), s.env_detail, s.water_level)
        box = next((bx for bx in lay.parts.get("structure", []) if isinstance(bx, S.Box) and bx.mat == "hull"), None)
        if box is None:
            return None
        hx, hy = box.sx / 2, box.sy / 2
        return np.array([(box.x - hx, -hy), (box.x + hx, -hy), (box.x + hx, hy), (box.x - hx, hy)], float)
    if kind != "SEA":
        return None
    from . import build
    with _vessel().at_rest(scene):
        try:
            bpy.context.view_layer.update()
        except Exception:
            pass
        water = float(root.location.z) + level
        z0, z1 = water - 0.6, water + 0.6
        found, cache = [], {}
        for ob in build.iter_parts(scene):
            if ob.get(build.PROP_EXCLUDED) or ob.hide_render or ob.data is None:
                continue
            mw = np.array(ob.matrix_world)
            bb = np.array([list(c) + [1.0] for c in ob.bound_box]) @ mw.T
            if bb[:, 2].max() < z0 or bb[:, 2].min() > z1:
                continue
            got = cache.get(ob.data.name)
            if got is None:
                me = ob.data
                co = np.empty(len(me.vertices) * 3, np.float32)
                me.vertices.foreach_get("co", co)
                ed = np.empty(len(me.edges) * 2, np.int32)
                me.edges.foreach_get("vertices", ed)
                got = cache[me.name] = (co.reshape(-1, 3).astype(float), ed.reshape(-1, 2))
            co, ed = got
            w = co @ mw[:3, :3].T + mw[:3, 3]
            near = w[(w[:, 2] >= z0) & (w[:, 2] <= z1)]
            if len(near):
                found.append(near[:, :2])
            # where edges cross the water (a hull side drawn as one tall face has no point near it)
            za, zb = w[ed[:, 0], 2], w[ed[:, 1], 2]
            cross = (za - water) * (zb - water) < 0.0
            if np.any(cross):
                a, b = w[ed[cross, 0]], w[ed[cross, 1]]
                f = ((water - a[:, 2]) / (b[:, 2] - a[:, 2]))[:, None]
                found.append((a + (b - a) * f)[:, :2])
    if not found:
        return None
    pts = np.concatenate(found) - np.array(root.location)[:2]
    hull = _convex_hull(pts)
    if len(hull) < 3 or np.ptp(hull[:, 0]) < 0.3 or np.ptp(hull[:, 1]) < 0.3:
        return None
    return hull


def _hull_foam_mesh(name: str, outline: np.ndarray, width: float, bow_sign: float = -1.0) -> bpy.types.Mesh:
    """A strip round the waterline from 0.8 m inside the hull out to 1.8 x the foam's reach, with the point
    attribute ``fr_d`` = distance from the hull / the reach there (wider at the bow and the stern)."""
    ring = _resample(outline, 1.0)
    n = len(ring)
    nxt, prv = np.roll(ring, -1, axis=0), np.roll(ring, 1, axis=0)
    tang = nxt - prv
    out = np.stack([tang[:, 1], -tang[:, 0]], axis=1)              # anticlockwise: the right of the way is out
    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)
    cx = (ring[:, 0].min() + ring[:, 0].max()) / 2
    half = max((ring[:, 0].max() - ring[:, 0].min()) / 2, 1.0)
    end = np.abs(ring[:, 0] - cx) / half
    reach = width * (0.75 + 0.7 * end ** 6)
    rows = np.array([-0.8, -0.3, 0.0, 0.15, 0.32, 0.5, 0.7, 0.95, 1.25, 1.55, 1.8])
    verts, dvals = [], []
    for r in rows:
        off = np.where(r < 0, r, r * reach)
        verts.append(np.column_stack([ring + out * off[:, None], np.zeros(n)]))
        dvals.append(np.where(r < 0, r, r) * np.ones(n))
    verts = np.concatenate(verts)
    i = np.arange(n)
    faces = np.concatenate([np.stack([j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i],
                                     axis=1) for j in range(len(rows) - 1)])
    m = _Mesh()
    m._add(verts, faces, 0, smooth=True)
    me = m.to_mesh(name)
    at = me.attributes.new("fr_d", "FLOAT", "POINT")
    at.data.foreach_set("value", np.concatenate(dvals).astype(np.float32))
    # task 0154: along the hull, 0 at the stern … 1 at the bow (the bow wave)
    u = np.clip((ring[:, 0] - cx) / half * bow_sign * 0.5 + 0.5, 0.0, 1.0)
    at = me.attributes.new("fr_u", "FLOAT", "POINT")
    at.data.foreach_set("value", np.tile(u, len(rows)).astype(np.float32))
    return me


def _hull_foam_material(cut: bool = False) -> bpy.types.Material:
    """White foam where ``fr_d`` is small, broken up and moving; see-through elsewhere (and inside the cut-away box
    with ``cut``, task 0081)."""
    name = MAT_PREFIX + "hull foam" + (" cut" if cut else "")
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    b = _NB(t.nt)
    tv = b.new("ShaderNodeValue")
    tv.name = "fr_time"
    co = b.new("ShaderNodeTexCoord").outputs["Object"]
    d = b.new("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="fr_d").outputs["Fac"]
    edge = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
    edge.inputs["Scale"].default_value = 0.28
    edge.inputs["Detail"].default_value = 3.0
    b.put(edge.inputs["Vector"], co)
    b.put(edge.inputs["W"], b.math("MULTIPLY", tv.outputs[0], 0.35))
    reach = b.math("MULTIPLY_ADD", b.math("SUBTRACT", edge.outputs["Fac"], 0.5), 0.9, d)
    lace = b.new("ShaderNodeTexNoise", noise_dimensions="4D")
    lace.inputs["Scale"].default_value = 1.1
    lace.inputs["Detail"].default_value = 6.0
    lace.inputs["Roughness"].default_value = 0.7
    b.put(lace.inputs["Vector"], co)
    b.put(lace.inputs["W"], b.math("MULTIPLY", tv.outputs[0], 0.6))
    k = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_foam_k").outputs["Fac"]
    # task 0154: the bow wave and the wash along the sides grow with the speed (a channel); the strip was made for the
    # fastest speed (fr_foam_w), the foam reaches as far as the speed now makes it
    u = b.new("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="fr_u").outputs["Fac"]
    k, more = _work().hull_nodes(b, u, k)
    w0 = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_foam_w0").outputs["Fac"]
    wb = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_foam_w").outputs["Fac"]
    w_now = b.math("MULTIPLY_ADD", _work().speed_socket(b), 0.35, w0)
    scale = b.math("DIVIDE", wb, b.math("MAXIMUM", b.math("MULTIPLY", w_now, more), 0.1))
    has = b.math("GREATER_THAN", wb, 0.0)                     # (a strip without the numbers: as before)
    reach = b.math("MULTIPLY", reach, b.math("MULTIPLY_ADD", has, b.math("SUBTRACT", scale, 1.0), 1.0))
    band = b.ramp(reach, 0.3, 1.1, 1.0, 0.0, smooth=True)
    alpha = b.math("MULTIPLY", b.math("MULTIPLY", band, b.ramp(lace.outputs["Fac"], 0.28, 0.6, 0.3, 1.0)), k)
    foam = _principled(t, sea_core.FOAM, 0.6)
    clear = t.node("ShaderNodeBsdfTransparent")
    mix = t.node("ShaderNodeMixShader", Fac=alpha)
    t.link(clear.outputs[0], mix.inputs[1])
    t.link(foam, mix.inputs[2])
    out = t.node("ShaderNodeOutputMaterial")
    t.link(mix.outputs[0], out.inputs["Surface"])
    if cut:
        _add_box_cut(mat)
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "hull_foam"
    return mat


def _hull_foam_group(name: str, sea_ob, rows, moving: bool, near: float) -> bpy.types.NodeTree:
    """Geometry nodes of the hull foam: each point of the strip goes onto the water (the sea's own waves), wherever
    vessel motion has carried the strip; z in the sea's frame = the waves' height + HULL_FOAM_LIFT."""
    ng = bpy.data.node_groups.get(name)
    if ng is None or ng.get("fr_env") != "hull_foam" or ng.library is not None:
        ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
        ng["fr_env"] = "hull_foam"
        ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
        ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    # task 0202: the group is kept (its nodes get the new numbers) instead of made again at every new sea
    _build_tree(ng, ng, lambda nt: _hull_foam_nodes(nt, sea_ob, rows, moving, near))
    return ng


def _hull_foam_nodes(nt, sea_ob, rows, moving: bool, near: float) -> None:
    b = _NB(nt)
    gin, gout = b.new("NodeGroupInput"), b.new("NodeGroupOutput")
    me = b.new("GeometryNodeSelfObject")
    own = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    b.put(own.inputs["Object"], me.outputs[0])
    sea_info = b.new("GeometryNodeObjectInfo", transform_space="ORIGINAL")
    sea_info.inputs["Object"].default_value = sea_ob
    inv_sea = b.new("FunctionNodeInvertMatrix")
    b.put(inv_sea.inputs[0], sea_info.outputs["Transform"])
    inv_own = b.new("FunctionNodeInvertMatrix")
    b.put(inv_own.inputs[0], own.outputs["Transform"])
    to_sea = b.new("FunctionNodeMatrixMultiply")
    b.put(to_sea.inputs[0], inv_sea.outputs["Matrix"])
    b.put(to_sea.inputs[1], own.outputs["Transform"])
    back = b.new("FunctionNodeMatrixMultiply")
    b.put(back.inputs[0], inv_own.outputs["Matrix"])
    b.put(back.inputs[1], sea_info.outputs["Transform"])
    p_sea = b.new("FunctionNodeTransformPoint")
    b.put(p_sea.inputs["Vector"], b.new("GeometryNodeInputPosition").outputs[0])
    b.put(p_sea.inputs["Transform"], to_sea.outputs[0])
    xyz = b.sep(p_sea.outputs[0])
    h = _height_sum(b, xyz["X"], xyz["Y"], _scene_seconds(b, moving), rows, near)
    on_water = b.comb(xyz["X"], xyz["Y"], b.math("ADD", h, HULL_FOAM_LIFT) if not isinstance(h, float)
                      else HULL_FOAM_LIFT)
    p_own = b.new("FunctionNodeTransformPoint")
    b.put(p_own.inputs["Vector"], on_water)
    b.put(p_own.inputs["Transform"], back.outputs[0])
    setp = b.new("GeometryNodeSetPosition")
    b.put(setp.inputs["Geometry"], gin.outputs[0])
    b.put(setp.inputs["Position"], p_own.outputs[0])
    b.put(gout.inputs[0], setp.outputs[0])


def _build_hull_foam(scene, s, col, root, sea_ob, outline, bft: float, rows, near: float, detailed: bool,
                     cut: bool = False):
    width = sea_core.hull_foam_width(bft, _max_speed(s))
    me = _hull_foam_mesh("FR Sea: hull foam", outline, width, bow_sign=-float(stern_side(s, outline)))
    mat = _hull_foam_material(cut)
    me.materials.append(mat)
    ob = _new_object("FR Sea: hull foam", me, "hull_foam", col, root)
    ob["fr_foam_k"] = sea_core.hull_foam_strength(bft, 0.0)    # task 0154: the speed's share is a channel
    ob["fr_foam_w"] = float(width)
    ob["fr_foam_w0"] = float(sea_core.hull_foam_width(bft, 0.0))
    ob.location = sea_ob.location
    for attr in ("visible_diffuse", "visible_shadow", "visible_transmission"):
        setattr(ob, attr, False)
    _drive_time(mat, scene, bool(s.sea_moving))
    mod = ob.modifiers.new("On the water", "NODES")
    rows = rows if detailed else []
    # (one group per kind of nodes, task 0202: a new sea state finds the one it had and only sets its numbers)
    mod.node_group = _hull_foam_group(f"{WAVES_GROUP} hull foam {_height_sig(rows, near)}", sea_ob, rows,
                                      bool(s.sea_moving), near)
    return ob


def _drive_time(mat, scene, moving: bool) -> None:
    node = mat.node_tree.nodes.get("fr_time")
    if node is None:
        return
    if moving:
        _time_driver(node.outputs[0], "default_value", scene, 1.0)
    else:
        try:
            node.outputs[0].driver_remove("default_value")
        except Exception:
            pass
        node.outputs[0].default_value = 0.0


# ---- spray -------------------------------------------------------------------


def _spray_material() -> bpy.types.Material:
    name = MAT_PREFIX + "spray"
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    shader = _principled(t, sea_core.FOAM, 0.35, Alpha=0.75)
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "spray"
    return mat


def _random(b: _NB, kind: str, lo, hi, seed, ident=None):
    n = b.new("FunctionNodeRandomValue", data_type=kind)
    b.put(n.inputs["Min"], lo)                     # (Blender 5.2: one Min / Max / Value of the node's type)
    b.put(n.inputs["Max"], hi)
    b.put(n.inputs["Seed"], seed)
    b.put(n.inputs["ID"], ident if ident is not None else b.new("GeometryNodeInputIndex").outputs[0])
    return n.outputs["Value"]


def _spray_points(b: _NB, count: int, seed: int, life: tuple, t, spawn, velocity, size: float):
    """``count`` drops, each living ``life`` seconds again and again: ``spawn(b, cycle_seed, t0)`` gives its start
    (x, y, z sockets) and whether it flies this time (0/1), ``velocity(b, cycle_seed)`` its speed."""
    pts = b.new("GeometryNodePoints")
    pts.inputs["Count"].default_value = int(count)
    L = _random(b, "FLOAT", life[0], life[1], seed)
    o = b.math("MULTIPLY", _random(b, "FLOAT", 0.0, 1.0, seed + 1), L)
    tt = b.math("ADD", t, o)
    cycle = b.math("FLOOR", b.math("DIVIDE", tt, L))
    age = b.math("SUBTRACT", tt, b.math("MULTIPLY", cycle, L))
    t0 = b.math("SUBTRACT", t, age)
    cyc_seed = b.new("FunctionNodeFloatToInt")
    b.put(cyc_seed.inputs[0], b.math("MULTIPLY_ADD", cycle, 7.0, float(seed)))
    x0, y0, z0, keep = spawn(b, cyc_seed.outputs[0], t0)
    vx, vy, vz = velocity(b, cyc_seed.outputs[0])
    x = b.math("MULTIPLY_ADD", vx, age, x0)
    y = b.math("MULTIPLY_ADD", vy, age, y0)
    z = b.math("SUBTRACT", b.math("MULTIPLY_ADD", vz, age, z0), b.math("MULTIPLY", b.math("MULTIPLY", age, age), 4.905))
    setp = b.new("GeometryNodeSetPosition")
    b.put(setp.inputs["Geometry"], pts.outputs[0])
    b.put(setp.inputs["Position"], b.comb(x, y, z))
    alive = b.math("MULTIPLY", keep, b.math("GREATER_THAN", z, b.math("SUBTRACT", z0, 0.3)))
    rad = b.math("MULTIPLY", b.ramp(age, 0.0, b.math("MULTIPLY", L, 0.9), 1.0, 0.25), size)
    radius = b.new("GeometryNodeSetPointRadius")
    b.put(radius.inputs["Points"], setp.outputs[0])
    b.put(radius.inputs["Radius"], rad)
    drop = b.new("GeometryNodeDeleteGeometry", domain="POINT")
    b.put(drop.inputs["Geometry"], radius.outputs[0])
    b.put(drop.inputs["Selection"], b.math("LESS_THAN", alive, 0.5))
    return drop.outputs[0]


def _spray_group(name: str, own, bft_sea: float, toward: float, wind, outline, radius: float,
                 moving: bool, detailed: bool, mat, fwd: int = -1) -> bpy.types.NodeTree:
    """Spray (task 0109): drops blown off the white caps (where the foam field is high, ``core/sea.py``) and thrown
    up at the bow, seeded, the same at every frame of every render. From Beaufort 5.5, full at 9."""
    old = bpy.data.node_groups.get(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng["fr_env"] = "spray"
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    b = _NB(ng)
    gout = b.new("NodeGroupOutput")
    bft, (wx, wy) = wind
    u = sea_core.bft_to_ms(bft)
    amount = float(sea_core.smoothstep(SPRAY_FROM, 9.0, bft))
    t = _scene_seconds(b, moving)
    field = sea_core.foam_field(own, bft_sea, toward)
    th = sea_core.foam_threshold(bft) - 0.25

    def height_and_foam(b, x, y, tt):
        P = b.comb(x, y, tt)
        h, F = None, None
        for i, (a, dx, dy, k, ph) in enumerate(own):
            s = b.math("SINE", b.phase(P, k * dx, k * dy, -math.sqrt(sea_core.G * k), ph))
            h = b.acc(h, s, a)
            F = b.acc(F, s, field.terms[i].c_sin)
        for tm in field.terms[len(own):]:
            F = b.acc(F, b.term(P, tm), tm.c_cos)
        return h, F

    cache = {}

    def crest_spawn(b, cs, t0):
        xyz = b.sep(_random(b, "FLOAT_VECTOR", (-radius, -radius, 0.0), (radius, radius, 1.0), cs))
        h, F = height_and_foam(b, xyz["X"], xyz["Y"], t0)
        z0 = b.math("ADD", h, 0.15) if detailed and h is not None else 0.15
        return xyz["X"], xyz["Y"], z0, b.math("GREATER_THAN", F, th)

    def crest_velocity(b, cs):
        v = _random(b, "FLOAT_VECTOR", (0.25 * u, -0.6, 1.0), (0.55 * u, 0.6, 3.5), b.math("ADD", cs, 3.0))
        xyz = b.sep(v)
        along, side = xyz["X"], xyz["Y"]
        vx = b.math("SUBTRACT", b.math("MULTIPLY", along, wx), b.math("MULTIPLY", side, wy))
        vy = b.math("MULTIPLY_ADD", along, wy, b.math("MULTIPLY", side, wx))
        return vx, vy, xyz["Z"]

    parts = []
    n_crest = int(round(40000 * amount))
    if n_crest > 0 and own:
        parts.append(_spray_points(b, n_crest, 11, (0.8, 1.8), t, crest_spawn, crest_velocity, 0.08))
    if outline is not None and amount > 0:
        # task 0082: ``fwd`` is the bow's side (-1: at min x, as before)
        bow_x = float(outline[:, 0].min()) if fwd < 0 else float(outline[:, 0].max())
        at_bow = outline[np.abs(outline[:, 0] - bow_x) < 4.0]
        y_lo, y_hi = float(at_bow[:, 1].min()), float(at_bow[:, 1].max())
        tp = 2 * math.pi / math.sqrt(sea_core.G * 2 * math.pi / max(sea_core.peak_wavelength(own), 1.0))

        def bow_spawn(b, cs, t0):          # the bow digs into a wave: a burst once per wave period
            x0, x1 = (bow_x - 1.0, bow_x + 9.0) if fwd < 0 else (bow_x - 9.0, bow_x + 1.0)
            xyz = b.sep(_random(b, "FLOAT_VECTOR", (x0, y_lo - 0.5, 0.0), (x1, y_hi + 0.5, 1.0), cs))
            cache["bow"] = xyz["Y"]
            beat = b.math("SINE", b.math("MULTIPLY", t0, 2 * math.pi / max(tp * 0.85, 1.0)))
            return xyz["X"], xyz["Y"], 0.5, b.math("GREATER_THAN", beat, 0.55)

        def bow_velocity(b, cs):
            v = _random(b, "FLOAT_VECTOR", (-1.5, 2.0, 3.0), (0.5, 6.0, 4.0 + 6.0 * amount), b.math("ADD", cs, 5.0))
            xyz = b.sep(v)
            side = b.math("SIGN", b.math("SUBTRACT", cache["bow"], (y_lo + y_hi) / 2))
            vx = b.math("MULTIPLY_ADD", wx, 0.35 * u, xyz["X"])
            vy = b.math("MULTIPLY_ADD", side, xyz["Y"], wy * 0.35 * u)
            return vx, vy, xyz["Z"]

        parts.append(_spray_points(b, int(3000 * amount) + 200, 23, (0.9, 1.6), t, bow_spawn, bow_velocity, 0.1))
    if not parts:
        geo = b.new("GeometryNodePoints").outputs[0]
    elif len(parts) == 1:
        geo = parts[0]
    else:
        join = b.new("GeometryNodeJoinGeometry")
        for p in reversed(parts):
            b.put(join.inputs[0], p)
        geo = join.outputs[0]
    ico = b.new("GeometryNodeMeshIcoSphere")
    ico.inputs["Radius"].default_value = 1.0
    ico.inputs["Subdivisions"].default_value = 1
    inst = b.new("GeometryNodeInstanceOnPoints")
    b.put(inst.inputs["Points"], geo)
    b.put(inst.inputs["Instance"], ico.outputs["Mesh"])
    b.put(inst.inputs["Scale"], b.new("GeometryNodeInputRadius").outputs[0])
    setm = b.new("GeometryNodeSetMaterial")
    b.put(setm.inputs["Geometry"], inst.outputs[0])
    setm.inputs["Material"].default_value = mat
    b.put(gout.inputs[0], setm.outputs[0])
    return ng


def _build_spray(s, col, root, sea_ob, own, bft_sea, toward, outline, near, detailed):
    sw = _spray_wind(s)
    if sw is None:
        return None
    mat = _spray_material()
    me = bpy.data.meshes.new("FR Sea: spray")
    me.materials.append(mat)
    ob = _new_object("FR Sea: spray", me, "spray", col, root)
    ob.location = sea_ob.location
    ob.visible_shadow = False
    mod = ob.modifiers.new("Spray", "NODES")
    reach = min(max(near, 60.0), 160.0)
    mod.node_group = _spray_group(f"{WAVES_GROUP} spray", own, bft_sea, toward, sw, outline, reach,
                                  bool(s.sea_moving), detailed, mat, fwd=-stern_side(s, outline))
    return ob


# ---- the sea itself ----------------------------------------------------------


def _end_width(outline: np.ndarray, at_max: bool, reach: float = 3.0) -> float:
    """How wide the waterline is near one end (within ``reach`` m of its lowest or highest x)."""
    xs = outline[:, 0]
    end = xs.max() if at_max else xs.min()
    near = outline[np.abs(xs - end) <= reach]
    if len(near) < 2:
        return 0.0
    return float(near[:, 1].max() - near[:, 1].min())


BOW_KEY = "fr_bow_az"               # on the surroundings' root: the bow's azimuth read from the hull at the sea's build


def bow_az(scene) -> float:
    """Scene azimuth the vessel's bow points to (task 0125: one source for wind 'from the bow', the wake, the bow spray
    and the swell): Weather & time > Bow +x / -x as set; From the hull: what the sea's last build read from the
    waterline (``stern_side``); nothing read yet (an older project, no sea): -x, as before."""
    s = scene.fresing
    bow = getattr(getattr(s, "weather", None), "bow", "AUTO")
    if bow != "AUTO":
        return weather_core.bow_az(bow)
    root = root_object()
    v = root.get(BOW_KEY) if root is not None and root.get("fr_kind") in ("SEA", "DECK") else None
    return float(v) if v in (0.0, 180.0) else weather_core.BOW_AZ


def _need_bow(s) -> bool:
    """The bow must be read from the hull now: From the hull, and something the sea build uses depends on it (wind
    'from the bow', the swell of vessel motion)."""
    w = getattr(s, "weather", None)
    if getattr(w, "bow", "AUTO") != "AUTO":
        return False
    return bool((_weather_on(s) and w.wind_ref == "BOW") or (s.vessel.enabled and s.background in ("SEA", "DECK")))


def stern_side(s, outline) -> int:
    """+1: the stern is the waterline's end at the highest x (the wake trails to +x, the bow at -x – as before task
    0082); -1: the stern is at the lowest x. Weather & time > Bow: +x / -x as set; From the hull: the wider end is the
    stern (a bow narrows), a hull about as wide at both ends keeps +1."""
    bow = getattr(getattr(s, "weather", None), "bow", "AUTO")
    if bow == "POS_X":
        return -1
    if bow == "NEG_X" or outline is None or len(outline) < 3:
        return 1
    lo, hi = _end_width(outline, False), _end_width(outline, True)
    if lo > 1.15 * hi:
        return -1
    return 1


def _wants_outline(s) -> bool:
    """The sea needs the hull's waterline: hull foam, the bow spray, or the bow's direction."""
    return bool(s.sea_foam) or _spray_wind(s) is not None or _need_bow(s)


_UNSET = object()


def _build_sea(s, col, root, level: float, machine_size: float, kind: str, outline=_UNSET) -> bpy.types.Object:
    """``outline``: the hull's waterline when the caller measured it already (``_waterline``)."""
    scene = s.id_data
    detailed = s.env_detail == "DETAILED"
    near = max(40.0, 5.0 * machine_size)
    foam, moving, weather = bool(s.sea_foam), bool(s.sea_moving), _weather_on(s)
    speed = _speed(s)
    if outline is _UNSET:
        outline = _waterline(scene, s, kind, root, level) if _wants_outline(s) else None
    if outline is not None:                        # task 0125: the bow read once, for the wind, the wake and the swell
        az = weather_core.bow_az(getattr(s.weather, "bow", "AUTO"), stern_side(s, outline))
        if root.get(BOW_KEY) != az:
            root[BOW_KEY] = az
            root["fr_kind"] = kind                 # (read by bow_az while the rest is built)
    bft, toward = sea_wind(s)
    swell = _vessel().swell_rows(s)
    cut = kind == "SEA" and bool(s.sea_cutaway)          # task 0081: the cut-away behind the stern
    me = _sea_mesh("FR Sea", detailed, near)
    sail = _work().sea_key(scene)                         # task 0154: the vessel sails / its thrusters run somewhere
    work = None
    if foam and outline is not None and sail:
        work = _work().layout(scene, outline, bow_sign=-float(stern_side(s, outline)))
        work["ahead"] = bool(sail.get("ahead"))
        if not sail.get("thr"):
            work["thrusters"] = []
    me.materials.append(_water_material(scene, s.sea_state, foam, moving, (bft, toward), swell, weather,
                                        wake=foam and bool(sail.get("ahead")) and outline is not None, cut=cut,
                                        work=work))
    ob = _new_object("FR Sea", me, "sea", col, root)
    if work:
        ob[_work().LAYOUT_KEY] = _work().layout_json(work)
    _work().sync(scene)
    ob.location.z = level
    if kind == "QUAY":
        ob.location.y = 0.0
    if detailed:
        mod = ob.modifiers.new("Waves", "NODES")
        mod.node_group = _waves_group(s.sea_state, moving, near, swell, (bft, toward))
    own = _waves(s.sea_state, (), (bft, toward))
    if outline is not None:
        xs, ys = outline[:, 0], outline[:, 1]
        side = stern_side(s, outline)          # task 0082: +1 stern at max x (as before), -1 at min x
        stern = xs.max() if side > 0 else xs.min()
        aft = outline[np.abs(xs - stern) < 3.0]
        ob["fr_wake"] = (float(stern * side), float((aft[:, 1].min() + aft[:, 1].max()) / 2),
                         float(max((ys.max() - ys.min()) / 2, 0.5)))
        ob["fr_wake_flip"] = 0.0 if side > 0 else 1.0
        ob["fr_wake_v"] = float(speed)
        if foam:
            _build_hull_foam(scene, s, col, root, ob, outline, bft, own + list(swell), near, detailed, cut)
    _build_spray(s, col, root, ob, own, bft, toward, outline, near, detailed)
    if kind == "SEA":                              # task 0081: the seabed, the cut-away's water
        _build_under_water(s, col, root, ob, level, detailed, near, swell, (bft, toward))
    return ob


# =============================================================================
# under the water (task 0081): the seabed, the cut-away behind the stern, the water's clarity
# =============================================================================
#
# Only on the open sea (Background "Open sea"). The seabed is always there, ``sea_depth`` under the water: under
# the opaque water it is never seen, so a sea without the cut-away renders as before. With the cut-away a box of
# water behind the stern is taken away: the sea's surface, white caps, wake and hull foam are see-through inside it
# (their materials test the box, read from the object attributes ``fr_seacut_o`` (front middle, world), ``fr_seacut_u``
# (unit aft) and ``fr_seacut_s`` (length, half width) – no attribute: no cut), and a ring of water round the box (a
# volume that absorbs and glows in the water's colour, ``core/sea.py``) fades whatever is seen through its walls.

SEABED_MOTION = "FR seabed motion"         # the empty the seabed follows (made and driven by the sea cables: paths_sea)
UNDER_ROLES = ("seabed", "stones", "sea_cut", "soil")
CUT_ATTRS = ("fr_seacut_o", "fr_seacut_u", "fr_seacut_s")
STONES = 420
STONES_NEAR = 0.6                          # share of the stones within 12 m of the box (the rest within 250 m)
PATCH_MARGIN = 20.0                        # m: the rippled patch reaches this far round the box (Detailed)
PATCH_STEP = 0.3                           # m between its points
PATCH_MAX_POINTS = 250_000


def follow_seabed_motion(ob) -> bool:
    """``ob`` moves with the seabed: a Copy Location constraint "FR seabed motion" (offset, x and y only) on the empty
    of that name, which the sea cables drive (the vessel's advance). No empty: no constraint. True when it follows."""
    empty = bpy.data.objects.get(SEABED_MOTION)
    con = ob.constraints.get(SEABED_MOTION)
    if empty is None or empty == ob:
        if con is not None:
            ob.constraints.remove(con)
        return False
    if con is not None and con.type != "COPY_LOCATION":
        ob.constraints.remove(con)
        con = None
    if con is None:
        con = ob.constraints.new("COPY_LOCATION")
        con.name = SEABED_MOTION
    if con.target != empty:
        con.target = empty
    con.use_x, con.use_y, con.use_z = True, True, False
    con.use_offset = True
    con.target_space = con.owner_space = "WORLD"
    return True


def seabed_objects() -> list:
    """The seabed and its stones (they follow "FR seabed motion")."""
    return [ob for ob in bpy.data.objects if ob.get(TAG) in ("seabed", "stones")]


def refresh_seabed_motion() -> None:
    """Every seabed object follows "FR seabed motion" (made or removed since the seabed was built)."""
    for ob in seabed_objects():
        follow_seabed_motion(ob)


def waterline(scene=None) -> float | None:
    """World z of the water's surface (the "FR Sea" object), None without a sea."""
    for ob in bpy.data.objects:
        if ob.get(TAG) == "sea":
            return float(ob.matrix_world.translation.z)
    return None


def seabed_z(scene) -> float | None:
    """World z of the seabed (the water's surface minus the water depth), None without the open sea."""
    root = root_object()
    if root is None or root.get("fr_kind") != "SEA":
        return None
    w = waterline(scene)
    return None if w is None else w - float(scene.fresing.sea_depth)


def _cable_box(scene):
    """The box the sea cables ask for (``paths_sea.cut_box``), checked, or None."""
    try:
        from . import paths_sea
        box = paths_sea.cut_box(scene)
    except Exception as exc:                  # never stop the surroundings over this
        print("Fresing Render: cut-away box of the sea cable not read:", exc)
        return None
    if not box:
        return None
    try:
        ox, oy = (float(v) for v in tuple(box["origin"])[:2])
        ux, uy = (float(v) for v in tuple(box["dir"])[:2])
        length, width = float(box["length"]), float(box["width"])
    except (KeyError, TypeError, ValueError):
        return None
    n = math.hypot(ux, uy)
    if n < 1e-9 or length <= 0.0 or width <= 0.0 or not all(map(math.isfinite, (ox, oy, length, width))):
        return None
    return {"origin": (ox, oy), "dir": (ux / n, uy / n), "length": length, "width": width}


def _manual_box(s, mn, mx) -> dict:
    """The box from the panel's numbers: from the stern (the model's lowest x) backwards (-x)."""
    return {"origin": (float(mn[0]) - float(s.sea_cut_start), float(mn[1] + mx[1]) / 2 + float(s.sea_cut_side)),
            "dir": (-1.0, 0.0), "length": float(s.sea_cut_length), "width": float(s.sea_cut_width)}


def sea_cut_box(scene, cable: bool = True) -> dict | None:
    """Where the cut-away box is, in world: {"origin": front middle (x, y), "dir": unit aft (x, y), "length", "width"}
    – placed by the sea cable (``paths_sea.cut_box``) when "Place it by the cable" is on and a cable gives one, else
    from the panel's numbers. None when the open sea has no cut-away."""
    s = scene.fresing
    root = root_object()
    if not s.sea_cutaway or root is None or root.get("fr_kind") != "SEA":
        return None
    return _box_for(scene, s, root, cable)


def _box_for(scene, s, root, cable: bool = True) -> dict:
    box = _cable_box(scene) if (cable and s.sea_cut_auto) else None
    if box is None:
        mn, mx = root.get("fr_min"), root.get("fr_max")
        if mn is None or mx is None:
            mn, mx = _model_box(scene)
        box = _manual_box(s, mn, mx)
    return box


def ground_wanted(s) -> bool:
    """The cut-away also cuts the ground (task 0148): the soil section shows and the seabed is open in the box."""
    return bool(s.sea_cutaway) and bool(s.sea_cut_ground)


def ground_depth_now(root, level: float, depth: float) -> float:
    """How deep the soil section goes: ``core.sea.ground_depth`` from the model's lowest point and the seabed. ``level``
    is the water's height in the root's frame, whose z 0 lies ``floor_offset`` under the model's lowest point."""
    mn = root.get("fr_min")
    low = float(mn[2]) - float(root.location.z) if mn is not None else float(level) - float(depth)
    return sea_core.ground_depth(low, float(level) - float(depth))


def _cut_key(s) -> dict:
    """What decides the cut-away (only when it is on: a sea without it keeps its key)."""
    key = {"clarity": round(float(s.sea_clarity), 2)}
    if s.sea_cut_ground:                     # task 0148 (only when on: an old project keeps its key)
        key["ground"] = 1
    box = _cable_box(s.id_data) if s.sea_cut_auto else None
    if box is not None:
        key["box"] = [round(v, 2) for v in (*box["origin"], *box["dir"], box["length"], box["width"])]
    else:
        key["manual"] = [round(float(v), 2) for v in (s.sea_cut_length, s.sea_cut_width, s.sea_cut_start,
                                                      s.sea_cut_side)]
    return key


VIEW_CUT = view_cut.MOD                    # task 0196 / 0202: the modifier that opens the box in the 3D view


def _set_cut_attrs(ob, box) -> None:
    """The box test's numbers on an object whose material is cut (world coordinates)."""
    if box is None:
        for k in CUT_ATTRS:
            if k in ob:
                del ob[k]
        return
    ob["fr_seacut_o"] = (float(box["origin"][0]), float(box["origin"][1]), 0.0)
    ob["fr_seacut_u"] = (float(box["dir"][0]), float(box["dir"][1]), 0.0)
    ob["fr_seacut_s"] = (float(box["length"]), float(box["width"]) / 2.0, 0.0)


def _view_cuts(col, box, depth: float, pit: float | None, detailed: bool) -> None:
    """The box cut out of the meshes in the 3D view (``sea_view_cut``), on everything the render cuts: the sea and
    its hull foam; with the ground cut the seabed and its stones. What lies inside goes down under the bottom of what
    is seen there: the seabed (no ground cut) or the soil section's pit."""
    below = float(pit) + 1.0 if pit is not None else 1.0
    for ob in list(col.objects):
        role = ob.get(TAG)
        if ob.type != "MESH" or not all(k in ob for k in CUT_ATTRS):
            continue
        # band: about one face (the sea's rings ~0.025 x the distance from its middle; the hull foam's rows up to
        # 0.3 x its reach, the reach up to 1.45 x its width; the seabed's patch 0.3 m and more; stones ~1 m)
        # stored band: about one face (the sea's rings ~0.025 x the distance from its middle; the hull foam's rows up
        # to 0.3 x its reach, the reach up to 1.45 x its width)
        if role == "sea":
            view_cut.set_cut(ob, box, drop=depth + below, way=view_cut.STORED if detailed else view_cut.EXACT,
                             band=(1.0, 0.04))
        elif role == "hull_foam":
            view_cut.set_cut(ob, box, drop=depth + below, band=0.5 * float(ob.get("fr_foam_w", 4.0)) + 1.5)
        elif role == "seabed":                     # (it slides aft with the lay: worked out where it is now)
            view_cut.set_cut(ob, box, drop=below, way=view_cut.LIVE if detailed else view_cut.EXACT)
        elif role == "stones":
            view_cut.set_cut(ob, box, drop=below, way=view_cut.LIVE)


def refresh_view_cuts(scene) -> int:
    """Projects of 0.2.153 (task 0202): their view cut deleted faces at every frame; it is put on again the new way,
    from the box the surroundings were built with. Returns how many objects changed."""
    olds = view_cut.old_cut_objects()
    root = root_object()
    if not olds or root is None or root.get("fr_kind") != "SEA" or not root.get("fr_seacut_box"):
        return 0
    s = scene.fresing
    try:
        box = json.loads(root["fr_seacut_box"])
    except ValueError:
        return 0
    col = bpy.data.collections.get(COLLECTION)
    sea_ob = next((ob for ob in col.objects if ob.get(TAG) == "sea"), None) if col is not None else None
    if sea_ob is None:
        return 0
    level = float(sea_ob.location.z)               # (the water's height in the root's frame, as it was built)
    depth = float(s.sea_depth)
    pit = ground_depth_now(root, level, depth) if ground_wanted(s) else None
    _view_cuts(col, box, depth, pit, s.env_detail == "DETAILED")
    for name in (view_cut.OLD_GROUP,):
        old = bpy.data.node_groups.get(name)
        if old is not None and not old.users:
            bpy.data.node_groups.remove(old)
    return len(olds)


def _box_test(b: _NB):
    """1 inside the cut-away box (from above: the box reaches from the sky to the seabed), else 0."""
    def attr(name):
        return b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name=name).outputs["Vector"]
    p = b.new("ShaderNodeNewGeometry").outputs["Position"]           # world
    o, u, size = attr("fr_seacut_o"), attr("fr_seacut_u"), b.sep(attr("fr_seacut_s"))
    d = b.vec("SUBTRACT", p, o)
    along = b.vec("DOT_PRODUCT", d, u)
    side = b.math("ABSOLUTE", b.vec("DOT_PRODUCT", d, b.vec("CROSS_PRODUCT", u, (0.0, 0.0, 1.0))))
    inside = b.math("MULTIPLY", b.math("GREATER_THAN", along, 0.0), b.math("LESS_THAN", along, size["X"]))
    return b.math("MULTIPLY", inside, b.math("LESS_THAN", side, size["Y"]))


def _add_box_cut(mat, from_below: bool = False, nt=None) -> None:
    """The material is see-through inside the cut-away box (the shader before it is kept as it is). ``from_below``:
    also for light from under the water (the sea's surface: the seabed in the box gets the sky's light, as through
    real water, and its bounces skip the water's shader); the camera's own rays from below are never let through.
    ``nt``: the tree being built (a ``_Replay``, task 0202), else the material's own."""
    nt = nt if nt is not None else mat.node_tree
    out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
    if out is None:
        return
    sock = out.inputs["Surface"]
    shader = nt.linked_from(sock) if isinstance(nt, _Replay) else (sock.links[0].from_socket if sock.links else None)
    if shader is None:
        return
    b = _NB(nt)
    clear = b.new("ShaderNodeBsdfTransparent")
    mix = b.new("ShaderNodeMixShader")
    fac = _box_test(b)
    if from_below:
        lp = b.new("ShaderNodeLightPath")
        below = b.math("MULTIPLY", b.new("ShaderNodeNewGeometry").outputs["Backfacing"],
                       b.math("SUBTRACT", 1.0, lp.outputs["Is Camera Ray"]))
        fac = b.math("MAXIMUM", fac, below)
    b.put(mix.inputs["Fac"], fac)
    nt.links.new(shader, mix.inputs[1])
    nt.links.new(clear.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    mat["fr_seacut"] = True


# ---- the seabed --------------------------------------------------------------


def _ripples_socket(b: _NB, x, y):
    """``core.sea.seabed_ripples`` in nodes: (height, the ripple's sine)."""
    k = 2 * math.pi / sea_core.RIPPLE_LENGTH
    bend = b.math("MULTIPLY_ADD", b.math("SINE", b.math("MULTIPLY_ADD", y, 0.21, 0.4)), 0.9,
                  b.math("MULTIPLY", b.math("SINE", b.math("SUBTRACT", b.math("MULTIPLY", x, 0.13),
                                                           b.math("MULTIPLY", y, 0.07))), 0.5))
    ph = b.math("ADD", b.math("MULTIPLY", b.math("MULTIPLY_ADD", x, 0.96, b.math("MULTIPLY", y, 0.28)), k), bend)
    r = b.math("SINE", ph)
    swell = b.math("MULTIPLY", b.math("MULTIPLY", b.math("SINE", b.math("MULTIPLY_ADD", x, 0.23, 0.9)),
                                      b.math("SINE", b.math("MULTIPLY_ADD", y, 0.17, 0.3))), 0.12)
    return b.math("MULTIPLY_ADD", r, sea_core.RIPPLE_HEIGHT, swell), r


def _seabed_material(ground: bool = False) -> bpy.types.Material:
    """Sand and silt: patches of colour, silt in the ripples' troughs, the ripples (shading only where the mesh is
    flat: object attribute ``fr_seabed_bump`` 1) and a fine grain. ``ground`` (task 0148): see-through inside the
    cut-away box, where the soil section shows instead."""
    name = MAT_PREFIX + "seabed" + (" ground cut" if ground else "")
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    b = _NB(t.nt)
    co = b.new("ShaderNodeTexCoord").outputs["Object"]
    xyz = b.sep(co)
    h, r = _ripples_socket(b, xyz["X"], xyz["Y"])
    on = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_seabed_bump").outputs["Fac"]
    patches = _noise(t, 0.04, 4.0, 0.6, co)
    grain = _noise(t, 9.0, 3.0, 0.6, co)
    sand, silt = sea_core.SAND
    col = _mix_color(t, b.ramp(patches, 0.35, 0.7, 0.0, 1.0), silt, sand)
    col = _mix_color(t, b.ramp(r, -1.0, 0.2, 0.35, 0.0), col, tuple(c * 0.7 for c in silt))
    col = _mix_color(t, b.ramp(grain, 0.3, 0.7, 0.0, 0.25), col, tuple(c * 0.75 for c in sand))
    bump = b.new("ShaderNodeBump")
    bump.inputs["Distance"].default_value = 1.0
    b.put(bump.inputs["Strength"], on)
    b.put(bump.inputs["Height"], h)
    fine = b.new("ShaderNodeBump")
    fine.inputs["Strength"].default_value = 0.12
    fine.inputs["Distance"].default_value = 0.01
    b.put(fine.inputs["Height"], grain)
    b.put(fine.inputs["Normal"], bump.outputs["Normal"])
    shader = _principled(t, col, 0.92, normal=fine.outputs["Normal"])
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "seabed"
    if ground:
        _add_box_cut(mat)
    return mat


def _stone_material(ground: bool = False) -> bpy.types.Material:
    name = MAT_PREFIX + "seabed stones" + (" ground cut" if ground else "")
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    co = _coords(t)
    n = _noise(t, 2.5, 5.0, 0.6, co)
    col = _mix_color(t, _ramp(t, n, 0.0, 1.0, 0.3, 0.7), _srgb(0.30, 0.29, 0.26), _srgb(0.48, 0.45, 0.39))
    col = _mix_color(t, _ramp(t, _noise(t, 0.3, 2.0, 0.5, co), 0.0, 0.6), col, _srgb(0.36, 0.33, 0.27))
    shader = _principled(t, col, _ramp(t, n, 0.6, 0.9), normal=_bump(t, _noise(t, 6.0, 4.0, 0.6, co), 0.5, 0.02))
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "stones"
    if ground:
        _add_box_cut(mat)
    return mat


def _soil_material() -> bpy.types.Material:
    """The soil section the cut-away shows under the seabed (task 0148): layers from sand to clay by the depth under
    the seabed (``core.sea.SOIL_LAYERS``, boundaries wandering by ``SOIL_WOBBLE`` with a noise), a grain and a
    little bump. The seabed's world height comes from the object's property ``fr_soil_top``."""
    name = MAT_PREFIX + "soil section"
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    b = _NB(t.nt)
    pos = b.new("ShaderNodeNewGeometry").outputs["Position"]               # world
    top = b.new("ShaderNodeAttribute", attribute_type="OBJECT", attribute_name="fr_soil_top").outputs["Fac"]
    depth = b.math("SUBTRACT", top, b.sep(pos)["Z"])
    wob = b.math("MULTIPLY", b.math("SUBTRACT", _noise(t, 0.12, 3.0, 0.5, pos), 0.5), 2.0 * sea_core.SOIL_WOBBLE)
    d = b.math("ADD", depth, wob)
    col = sea_core.SOIL_LAYERS[0][1]
    for start, c in sea_core.SOIL_LAYERS[1:]:
        col = _mix_color(t, b.ramp(d, start - 0.12, start + 0.12), col, c)
    grain = _noise(t, 7.0, 4.0, 0.6, pos)
    col = _mix_color(t, b.ramp(grain, 0.3, 0.7, 0.0, 0.2), col, (0.0, 0.0, 0.0))
    shader = _principled(t, col, 0.95, normal=_bump(t, grain, 0.25, 0.05))
    out = t.node("ShaderNodeOutputMaterial")
    t.link(shader, out.inputs["Surface"])
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "soil"
    return mat


def _box_frame(box, offset_xy) -> tuple:
    """The box in the surroundings' frame: front middle o, unit aft u, unit side v (left of aft)."""
    o = np.array(box["origin"][:2], float) - np.asarray(offset_xy, float)[:2]
    u = np.array(box["dir"][:2], float)
    u /= max(float(np.linalg.norm(u)), 1e-9)
    v = np.array((-u[1], u[0]))
    return o, u, v


def _seabed_mesh(name: str, box, offset_xy, detailed: bool) -> bpy.types.Mesh:
    """A plain square ±``SEABED_EXTENT`` round the model; in Detailed (with the cut-away) also a rippled patch round
    the box (``core.sea.seabed_ripples``), the plain square ``SEABED_SINK`` under it."""
    e = sea_core.SEABED_EXTENT
    z0 = -sea_core.SEABED_SINK if detailed else 0.0
    m = _Mesh()
    m._add([(-e, -e, z0), (e, -e, z0), (e, e, z0), (-e, e, z0)], [(0, 1, 2, 3)], 0)
    if detailed and box is not None:
        o, u, v = _box_frame(box, offset_xy)
        length, width = float(box["length"]), float(box["width"])
        a0, a1 = -PATCH_MARGIN, length + PATCH_MARGIN
        b0, b1 = -width / 2 - PATCH_MARGIN, width / 2 + PATCH_MARGIN
        step = PATCH_STEP
        while ((a1 - a0) / step + 1) * ((b1 - b0) / step + 1) > PATCH_MAX_POINTS:
            step *= 1.25
        na, nb = int(math.ceil((a1 - a0) / step)) + 1, int(math.ceil((b1 - b0) / step)) + 1
        A, B = np.meshgrid(np.linspace(a0, a1, na), np.linspace(b0, b1, nb), indexing="ij")
        x = o[0] + A * u[0] + B * v[0]
        y = o[1] + A * u[1] + B * v[1]
        # the ripples, sinking to under the plain square over the patch's last 3 m (no seam)
        edge = np.minimum.reduce([A - a0, a1 - A, B - b0, b1 - B])
        keep = np.clip(edge / 3.0, 0.0, 1.0)
        z = sea_core.seabed_ripples(x, y) * keep - (1.0 - keep) * (sea_core.SEABED_SINK + 0.03)
        pts = np.stack([x, y, z], axis=-1).reshape(-1, 3)
        idx = np.arange(na * nb).reshape(na, nb)
        q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], axis=-1).reshape(-1, 4)
        if (u[0] * v[1] - u[1] * v[0]) < 0:                 # faces up
            q = q[:, ::-1]
        m._add(pts, q, 0, smooth=True)
    return m.to_mesh(name)


def _stones_mesh(name: str, box, offset_xy, seed: int = 81) -> bpy.types.Mesh:
    """A few hundred low stones on the sand round the box (most of them near it), a third sunk in."""
    rng = np.random.default_rng(seed)
    o, u, v = _box_frame(box, offset_xy)
    length, width = float(box["length"]), float(box["width"])
    n_near = int(STONES * STONES_NEAR)
    a = np.concatenate([rng.uniform(-12.0, length + 12.0, n_near),
                        rng.uniform(-250.0, length + 250.0, STONES - n_near)])
    b = np.concatenate([rng.uniform(-width / 2 - 12.0, width / 2 + 12.0, n_near),
                        rng.uniform(-width / 2 - 250.0, width / 2 + 250.0, STONES - n_near)])
    cx, cy = o[0] + a * u[0] + b * v[0], o[1] + a * u[1] + b * v[1]
    size = np.exp(rng.uniform(math.log(0.06), math.log(0.42), STONES))
    seg, rows = 8, 4
    lon = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    lat = np.linspace(-math.pi / 2, math.pi / 2, rows + 1)[1:-1]
    unit = np.array([(0.0, 0.0, -1.0)] + [(math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
                                          for la in lat for lo in lon] + [(0.0, 0.0, 1.0)])
    top = len(unit) - 1
    faces = [(0, 1 + (i + 1) % seg, 1 + i) for i in range(seg)]
    for j in range(rows - 2):
        p, q = 1 + j * seg, 1 + (j + 1) * seg
        faces += [(p + i, p + (i + 1) % seg, q + (i + 1) % seg, q + i) for i in range(seg)]
    p = 1 + (rows - 2) * seg
    faces += [(p + i, p + (i + 1) % seg, top) for i in range(seg)]
    ground = sea_core.seabed_ripples(cx, cy)
    m = _Mesh()
    for i in range(STONES):
        sx, sy = size[i] * rng.uniform(0.8, 1.3), size[i] * rng.uniform(0.6, 1.0)
        sz = size[i] * rng.uniform(0.3, 0.55)
        rot = rng.uniform(0, 2 * math.pi)
        c, sn = math.cos(rot), math.sin(rot)
        lump = 1.0 + rng.uniform(-0.18, 0.18, len(unit))[:, None]
        pts = unit * lump * (sx, sy, sz)
        pts = np.column_stack([pts[:, 0] * c - pts[:, 1] * sn, pts[:, 0] * sn + pts[:, 1] * c, pts[:, 2]])
        pts += (cx[i], cy[i], float(ground[i]) - 0.35 * sz)
        m._add(pts, faces, 0, smooth=True)
    return m.to_mesh(name)


# ---- the ring of water round the box -----------------------------------------


def _rect(o, u, v, length: float, width: float) -> list:
    """The four corners of a rectangle from o along u (``length``), ±width/2 along v, anticlockwise from above."""
    corners = [o - v * width / 2, o + u * length - v * width / 2, o + u * length + v * width / 2, o + v * width / 2]
    if (u[0] * v[1] - u[1] * v[0]) < 0:
        corners = corners[::-1]
    return corners


def _ring_mesh(name: str, box, offset_xy, clarity: float, depth: float, detailed: bool,
               under: float = 2.0) -> bpy.types.Mesh:
    """The water round the box: a closed ring (outer box = the box grown by ``CUT_GROW`` x the clarity, the box as
    its hole) from ``under`` m under the seabed to ``CUT_TOP`` under the water, normals out of the water. Point attribute
    ``fr_dtop`` = metres under the ring's top, face attribute ``fr_inner`` = 1 on the box's walls."""
    o, u, v = _box_frame(box, offset_xy)
    length, width = float(box["length"]), float(box["width"])
    g = sea_core.CUT_GROW * max(float(clarity), 0.5)
    inner = _rect(o, u, v, length, width)
    outer = _rect(o - u * g, u, v, length + 2 * g, width + 2 * g)
    loops_i, loops_o = [], []
    for k in range(4):                      # Detailed: a point every metre, so the top can follow the waves
        a, b = inner[k], inner[(k + 1) % 4]
        n = max(1, int(math.ceil(np.linalg.norm(b - a) / 1.0))) if detailed else 1
        f = np.linspace(0.0, 1.0, n, endpoint=False)[:, None]
        loops_i.append(a + (b - a) * f)
        a2, b2 = outer[k], outer[(k + 1) % 4]
        loops_o.append(a2 + (b2 - a2) * f)
    ri, ro = np.concatenate(loops_i), np.concatenate(loops_o)
    n = len(ri)
    top, bot = -sea_core.CUT_TOP, -float(depth) - under
    pts = np.concatenate([np.column_stack([ro, np.full(n, top)]), np.column_stack([ri, np.full(n, top)]),
                          np.column_stack([ro, np.full(n, bot)]), np.column_stack([ri, np.full(n, bot)])])
    OT, IT, OB, IB = 0, n, 2 * n, 3 * n
    faces, inner_flag = [], []
    for i in range(n):
        j = (i + 1) % n
        faces += [(OB + i, OB + j, OT + j, OT + i),        # outer wall: out
                  (IB + i, IT + i, IT + j, IB + j),        # the box's wall: into the box
                  (OT + i, OT + j, IT + j, IT + i),        # top: up
                  (OB + i, IB + i, IB + j, OB + j)]        # bottom: down
        inner_flag += [0.0, 1.0, 0.0, 0.0]
    m = _Mesh()
    m._add(pts, faces, 0)
    me = m.to_mesh(name)
    at = me.attributes.new("fr_dtop", "FLOAT", "POINT")
    at.data.foreach_set("value", np.concatenate([np.zeros(2 * n), np.full(2 * n, top - bot)]).astype(np.float32))
    fa = me.attributes.new("fr_inner", "FLOAT", "FACE")
    fa.data.foreach_set("value", np.array(inner_flag, np.float32))
    return me


def _soil_mesh(name: str, box, offset_xy, depth: float, pit: float) -> bpy.types.Mesh:
    """The soil section (task 0148): the box's four walls from ``GROUND_TOP`` over the seabed (its ripples) down to
    ``pit`` m under it and its floor, faces into the box. In the water ring's frame (z 0 = the water's surface)."""
    o, u, v = _box_frame(box, offset_xy)
    length, width = float(box["length"]), float(box["width"])
    c = _rect(o, u, v, length, width)
    z0, z1 = -float(depth) + sea_core.GROUND_TOP, -float(depth) - float(pit)
    pts = np.array([(*p, z) for z in (z0, z1) for p in c], float)            # 0..3 top, 4..7 bottom
    faces = [(4 + i, i, (i + 1) % 4, 4 + (i + 1) % 4) for i in range(4)]       # walls: into the box
    faces.append((4, 5, 6, 7))                                                  # floor: up (corners go anticlockwise)
    m = _Mesh()
    m._add(pts, faces, 0)
    return m.to_mesh(name)


def _cut_water_material(clarity: float, weather: bool) -> bpy.types.Material:
    """The ring's water: see-through surface with a thin bright line along the top of the box's walls; inside a
    homogeneous volume that absorbs (sigma = 3 / clarity) and glows in the water's colour x the light (so whatever
    lies behind a wall fades into the water's colour, ``core.sea.seen_through``). The light: Weather & time's
    ``day`` and ``clouds`` channels, else the Value node ``fr_light`` (set from the sky settings)."""
    sigma = sea_core.absorption(clarity)
    name = f"{MAT_PREFIX}sea cut water {float(clarity):.2f}{' weather' if weather else ''}"
    mat = bpy.data.materials.get(name)
    if mat is not None and mat.get("fr_env_version") == MAT_VERSION:
        return mat
    if mat is None:
        mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    t = _NT(mat)
    b = _NB(t.nt)
    if weather:
        def channel(n):
            return b.new("ShaderNodeAttribute", attribute_type="VIEW_LAYER",
                         attribute_name=weather_core.prop(n)).outputs["Fac"]
        day = b.math("MINIMUM", b.math("MAXIMUM", channel("day"), 0.0), 1.0)
        clouds = b.math("MINIMUM", b.math("MAXIMUM", channel("clouds"), 0.0), 1.0)
        light = b.math("MULTIPLY_ADD", day, b.math("MULTIPLY_ADD", clouds, -(1.0 - sea_core.OVERCAST_LIGHT), 1.0),
                       sea_core.NIGHT_LIGHT)
    else:
        lv = b.new("ShaderNodeValue")
        lv.name = "fr_light"
        lv.outputs[0].default_value = 1.0
        light = lv.outputs[0]
    # volume: absorption + glow (strength sigma x light): seen = behind T + colour (1 - T)
    absorb = b.new("ShaderNodeVolumeAbsorption")
    absorb.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    absorb.inputs["Density"].default_value = sigma
    glow = b.new("ShaderNodeEmission")
    glow.inputs["Color"].default_value = (*sea_core.UNDERWATER, 1.0)
    b.put(glow.inputs["Strength"], b.math("MULTIPLY", light, sigma))
    add = b.new("ShaderNodeAddShader")
    b.put(add.inputs[0], absorb.outputs[0])
    b.put(add.inputs[1], glow.outputs[0])
    # surface: clear, a thin bright line along the top of the box's walls (where the water was cut)
    dtop = b.new("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="fr_dtop").outputs["Fac"]
    inner = b.new("ShaderNodeAttribute", attribute_type="GEOMETRY", attribute_name="fr_inner").outputs["Fac"]
    line = b.math("MULTIPLY", b.ramp(dtop, 0.0, sea_core.CUT_EDGE, 0.85, 0.0, smooth=True),
                  b.math("GREATER_THAN", inner, 0.5))
    edge = b.new("ShaderNodeEmission")
    edge.inputs["Color"].default_value = (0.55, 0.80, 0.78, 1.0)
    b.put(edge.inputs["Strength"], b.math("MULTIPLY", light, 1.4))
    clear = b.new("ShaderNodeBsdfTransparent")
    # the walls darken with depth (less light down there): what lies behind them shows through, dimmer
    dark_k, dark_d = sea_core.CUT_DARK
    dim = b.math("MULTIPLY", b.ramp(dtop, 0.0, dark_d, 0.0, dark_k, smooth=True), b.math("GREATER_THAN", inner, 0.5))
    shade = b.new("ShaderNodeEmission")
    shade.inputs["Color"].default_value = (*(c * 0.25 for c in sea_core.UNDERWATER), 1.0)
    b.put(shade.inputs["Strength"], light)
    wall = b.new("ShaderNodeMixShader")
    b.put(wall.inputs["Fac"], dim)
    b.put(wall.inputs[1], clear.outputs[0])
    b.put(wall.inputs[2], shade.outputs[0])
    mix = b.new("ShaderNodeMixShader")
    b.put(mix.inputs["Fac"], line)
    b.put(mix.inputs[1], wall.outputs[0])
    b.put(mix.inputs[2], edge.outputs[0])
    out = b.new("ShaderNodeOutputMaterial")
    b.put(out.inputs["Surface"], mix.outputs[0])
    b.put(out.inputs["Volume"], add.outputs[0])
    try:
        mat.volume_intersection_method = "ACCURATE"          # EEVEE: the ring is not convex (it has a hole)
    except (AttributeError, TypeError):
        pass
    for owner in (mat, getattr(mat, "cycles", None)):
        if owner is not None and hasattr(owner, "emission_sampling"):
            owner.emission_sampling = "NONE"         # the glow is the water's colour, it lights nothing
            break
    mat["fr_env_version"] = MAT_VERSION
    mat["fr_env"] = "sea_cut"
    mat["fr_clarity"] = float(clarity)
    mat["fr_sigma"] = float(sigma)
    return mat


def _light_now(s) -> float:
    """The light under water without Weather & time (``core.sea.sky_light``)."""
    return sea_core.sky_light(float(s.light_strength), s.sky_weather == "OVERCAST", float(s.sun_elevation))


def _build_under_water(s, col, root, sea_ob, level: float, detailed: bool, near: float, swell, wind) -> None:
    """The seabed (always), with the cut-away the ring of water round the box (and in Detailed the rippled patch and
    the stones). Called at the end of ``_build_sea`` on the open sea."""
    scene = s.id_data
    depth = float(s.sea_depth)
    cut = bool(s.sea_cutaway)
    box = _box_for(scene, s, root) if cut else None
    offset = (float(root.location.x), float(root.location.y))
    rich = detailed and cut
    ground = ground_wanted(s) and cut
    me = _seabed_mesh("FR Sea: seabed", box, offset, rich)
    me.materials.append(_seabed_material(ground))
    bed = _new_object("FR Sea: seabed", me, "seabed", col, root)
    bed.location.z = level - depth
    bed["fr_seabed_bump"] = 0.0 if rich else 1.0
    follow_seabed_motion(bed)
    if rich:
        st = _new_object("FR Sea: stones", _stones_mesh("FR Sea: stones", box, offset), "stones", col, root)
        st.data.materials.append(_stone_material(ground))
        st.location.z = level - depth
        follow_seabed_motion(st)
    if not cut:
        return
    _set_cut_attrs(sea_ob, box)
    pit = ground_depth_now(root, level, depth) if ground else None
    if ground:                                    # task 0148: the cut goes on into the ground
        _set_cut_attrs(bed, box)
        if rich:
            _set_cut_attrs(st, box)
        sm = _soil_mesh("FR Sea: soil section", box, offset, depth, pit)
        sm.materials.append(_soil_material())
        soil = _new_object("FR Sea: soil section", sm, "soil", col, root)
        soil.location = sea_ob.location
        soil["fr_soil_top"] = float(root.location.z + level - depth)      # world z of the seabed
        soil["fr_soil_depth"] = float(pit)
    for ob in col.objects:
        if ob.get(TAG) == "hull_foam":
            _set_cut_attrs(ob, box)
    _view_cuts(col, box, depth, pit, detailed)
    ring = _new_object("FR Sea: cut-away water", _ring_mesh("FR Sea: cut-away water", box, offset, s.sea_clarity,
                                                            depth, detailed,
                                                            -sea_core.GROUND_TOP if ground else 2.0), "sea_cut", col, root)
    ring.data.materials.append(_cut_water_material(s.sea_clarity, _weather_on(s)))
    ring.location = sea_ob.location
    # only what the camera sees through the walls: no shadows, no light bounced off it
    (ring.visible_camera, ring.visible_diffuse, ring.visible_glossy, ring.visible_transmission,
     ring.visible_shadow) = (True, False, False, True, False)
    if hasattr(ring, "visible_volume_scatter"):
        ring.visible_volume_scatter = False
    if detailed:                                   # the walls' top follows the waves (the sea's own modifier)
        mod = ring.modifiers.new("Waves", "NODES")
        mod.node_group = _waves_group(s.sea_state, bool(s.sea_moving), near, swell, wind)
    root["fr_seacut_box"] = json.dumps(box)


def _update_under_water(scene, s, root) -> None:
    """Live (no rebuild): the seabed follows "FR seabed motion"; the water's light follows the sky settings."""
    if root is None or root.get("fr_kind") != "SEA":
        return
    refresh_seabed_motion()
    light = _light_now(s)
    for ob in _objects(scene):
        if ob.get(TAG) != "sea_cut" or ob.type != "MESH":
            continue
        for mat in ob.data.materials:
            node = mat.node_tree.nodes.get("fr_light") if mat is not None and mat.node_tree else None
            if node is not None and abs(node.outputs[0].default_value - light) > 1e-6:
                node.outputs[0].default_value = light


# =============================================================================
# the ground of a 360° photo
# =============================================================================


def _irradiance(img) -> tuple[float, float, float]:
    """Light falling on flat ground from the photo's upper half (per colour), at strength 1.

    The photo's ground is shown as a matte floor whose colour is photo × π / this, so where no
    shadow falls it looks exactly like the photo, and the machine's shadow darkens it."""
    key = f"{bpy.path.abspath(img.filepath)}|{img.size[0]}x{img.size[1]}"
    if img.get("fr_irr_key") == key:
        return tuple(img["fr_irr"])
    w, h = img.size
    work = img
    if w > 1024:
        work = img.copy()
        work.scale(1024, 512)
        w, h = 1024, 512
    px = np.empty(w * h * 4, dtype=np.float32)
    work.pixels.foreach_get(px)
    if work is not img:
        bpy.data.images.remove(work)
    px = px.reshape(h, w, 4)[:, :, :3].astype(np.float64)
    v = (np.arange(h) + 0.5) / h
    lat = (v - 0.5) * math.pi
    weight = np.where(lat > 0, np.sin(lat) * np.cos(lat), 0.0) * (math.pi / h) * (2 * math.pi / w)
    e = (px * weight[:, None, None]).sum(axis=(0, 1))
    e = tuple(float(max(x, 1e-4)) for x in e)
    img["fr_irr"] = e
    img["fr_irr_key"] = key
    return e


def _photo_direction(t: _NT, origin_z: float):
    """Direction from the photo's camera point (above the floor centre) to the shaded point."""
    geo = t.node("ShaderNodeNewGeometry")
    sub = t.node("ShaderNodeVectorMath", _operation="SUBTRACT", Vector=geo.outputs["Position"])
    sub.name = "fr_origin"
    sub.inputs[1].default_value = (0.0, 0.0, origin_z)
    norm = t.node("ShaderNodeVectorMath", _operation="NORMALIZE", Vector=sub.outputs["Vector"])
    mapping = t.node("ShaderNodeMapping", Vector=norm.outputs["Vector"])
    mapping.name = "fr_turn"
    env = t.node("ShaderNodeTexEnvironment")
    env.name = "fr_photo"
    t.link(mapping.outputs["Vector"], env.inputs["Vector"])
    return env


def _photo_materials(s, img):
    dome = bpy.data.materials.get(MAT_PREFIX + "photo dome") or bpy.data.materials.new(MAT_PREFIX + "photo dome")
    ground = bpy.data.materials.get(MAT_PREFIX + "photo ground") or bpy.data.materials.new(MAT_PREFIX + "photo ground")
    for mat in (dome, ground):
        try:
            mat.use_nodes = True
        except Exception:
            pass
    t = _NT(dome)
    env = _photo_direction(t, 0.0)
    em = t.node("ShaderNodeEmission")
    em.name = "fr_strength"
    t.link(env.outputs["Color"], em.inputs["Color"])
    _output(t, em.outputs[0], one_sided=True, cutaway=False)
    dome.use_backface_culling = True
    t = _NT(ground)
    env = _photo_direction(t, 0.0)
    scale = t.node("ShaderNodeVectorMath", _operation="MULTIPLY", Vector=env.outputs["Color"])
    scale.name = "fr_albedo"
    diff = t.node("ShaderNodeBsdfDiffuse")
    t.link(scale.outputs["Vector"], diff.inputs["Color"])
    _output(t, diff.outputs[0], cutaway=False)
    for mat in (dome, ground):
        mat["fr_env"] = "photo"
    return dome, ground


def _photo_update(s) -> None:
    """Photo, turn, strength and height in the dome and ground materials (no rebuild)."""
    path = _photo_path(s)
    if not path:
        return
    from . import world
    img = world._load_hdri(path)
    if img is None:
        return
    e = _irradiance(img)
    for name in ("photo dome", "photo ground"):
        mat = bpy.data.materials.get(MAT_PREFIX + name)
        if mat is None:
            continue
        nodes = mat.node_tree.nodes
        if nodes["fr_photo"].image != img:
            nodes["fr_photo"].image = img
        turn = (0.0, 0.0, math.radians(s.light_rotation))
        if tuple(nodes["fr_turn"].inputs["Rotation"].default_value) != turn:
            nodes["fr_turn"].inputs["Rotation"].default_value = turn
        origin = (0.0, 0.0, s.photo_height)
        if tuple(nodes["fr_origin"].inputs[1].default_value) != origin:
            nodes["fr_origin"].inputs[1].default_value = origin
        if "fr_strength" in nodes and nodes["fr_strength"].inputs["Strength"].default_value != s.light_strength:
            nodes["fr_strength"].inputs["Strength"].default_value = s.light_strength
        if "fr_albedo" in nodes:
            alb = tuple(math.pi / x for x in e)
            if tuple(nodes["fr_albedo"].inputs[1].default_value) != alb:
                nodes["fr_albedo"].inputs[1].default_value = alb


def _build_photo(scene, s, root, col, size) -> float:
    """A dome around the scene with the photo on it, its lower part flattened onto the floor."""
    from . import world
    img = world._load_hdri(_photo_path(s))
    radius = max(40.0, 3.0 * float(max(size)))
    h = max(0.05, s.photo_height)
    dome_mat, ground_mat = _photo_materials(s, img)
    # dome: the part of a sphere around the photo's camera point that is above the floor
    n, m = 64, 24
    c = np.array([0.0, 0.0, h])
    lat0 = math.asin(-h / radius)
    pts, faces = [], []
    for j in range(m + 1):
        lat = lat0 + (math.pi / 2 - lat0) * j / m
        for i in range(n):
            lon = 2 * math.pi * i / n
            pts.append(c + radius * np.array((math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon),
                                               math.sin(lat))))
    for j in range(m):
        a, b = j * n, (j + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]   # normals inwards
    mesh = _Mesh()
    mesh._add(pts, faces, 0, smooth=True)
    me = mesh.to_mesh("FR Photo dome")
    me.materials.append(dome_mat)
    _new_object("FR Photo dome", me, "photo_dome", col, root)
    # ground: a disc on the floor, out to where the dome meets it
    rg = radius * math.cos(lat0)
    rings = [0.0] + list(np.geomspace(0.5, rg, 24))
    pts = [np.zeros(3)]
    for r in rings[1:]:
        for i in range(n):
            lon = 2 * math.pi * i / n
            pts.append(np.array((r * math.cos(lon), r * math.sin(lon), 0.0)))
    faces = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
    for j in range(len(rings) - 2):
        a, b = 1 + j * n, 1 + (j + 1) * n
        faces += [(a + i, b + i, b + (i + 1) % n, a + (i + 1) % n) for i in range(n)]
    mesh = _Mesh()
    mesh._add(pts, faces, 0)
    me = mesh.to_mesh("FR Photo ground")
    me.materials.append(ground_mat)
    _new_object("FR Photo ground", me, "photo_ground", col, root)
    _photo_update(s)
    return radius * 2.5


# =============================================================================
# props for scale
# =============================================================================


def props(scene=None) -> list:
    col = bpy.data.collections.get(PROPS_COLLECTION)
    if col is None:
        return []
    return [ob for ob in col.objects if ob.get(PROP_TAG)]


def add_prop(scene, kind: str) -> bpy.types.Object:
    """Put a prop next to the machine (in a row along its right-hand side, on the floor)."""
    from . import logic, props_scale
    label = S.PROPS[kind][0]
    me = props_scale.make_mesh(kind, label, dict(props_detail.PERSON_DEFAULTS) if kind == "PERSON" else {})
    ob = bpy.data.objects.new(label, me)
    _collection(scene, PROPS_COLLECTION).objects.link(ob)
    ob[PROP_TAG] = kind
    ob[props_scale.VER_KEY] = props_scale.VERSION
    props_scale.ensure_modifier(ob, scene)      # task 0155: detailed near the camera, light far away
    mn, mx = logic.cached_bounds(scene)
    existing = props(scene)
    sizes = []
    for p in existing:
        sx, sy, _sz = _prop_size(p[PROP_TAG]) if p.get(PROP_TAG) in S.PROPS else (1.0, 1.0, 1.0)
        sizes.append((sx, sy))
    index_new = existing.index(ob)
    x, y = S.prop_spot(index_new, (float(mn[0]), float(mx[0]), float(mn[1]), float(mx[1])), sizes)
    ob.location = (x, y, floor_height(scene))
    show = scene.fresing.props_visible
    ob.hide_render = not show
    ob.hide_viewport = not show
    return ob


_SIZES: dict = {}


def _prop_size(kind):
    if kind not in _SIZES:
        _SIZES[kind] = S.prop_size(kind)
    return _SIZES[kind]


def set_props_visible(scene, visible: bool) -> None:
    for ob in props(scene):
        if ob.hide_render == visible:
            ob.hide_render = not visible
        if ob.hide_viewport == visible:
            ob.hide_viewport = not visible


def remove_props(scene) -> int:
    objs = props(scene)
    meshes = {ob.data for ob in objs if ob.data is not None}
    n = len(objs)
    if objs:
        bpy.data.batch_remove(objs)
    orphans = [me for me in meshes if me.users == 0]
    if orphans:
        bpy.data.batch_remove(orphans)
    return n


def put_props_on_floor(scene) -> None:
    z = floor_height(scene)
    for ob in props(scene):
        ob.location.z = z
