"""Saved states: poses, exploded views, visibility sets and scenes ("shots").

* Pose        joint values + free moves of subassemblies (by stable part ID)
* Visibility  which subassemblies / parts are hidden
* Scene       paint scheme + pose + visibility + camera + background + image size,
              switched in one click (stored as ``scene.fresing.shots``)

Free moves are stored as a matrix relative to the part's rest position, so they
survive re-parenting by joints and re-imports.
"""

from __future__ import annotations

import json

import bpy
from mathutils import Matrix, Vector

from . import build, joints, logic

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def by_uid(scene) -> dict:
    out = {}
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) in build.MODEL_KINDS:
            out.setdefault(ob.get(build.PROP_UID, ob.name), ob)
    return out


def _unique(collection, base: str) -> str:
    names = {x.name for x in collection}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


# ---------------------------------------------------------------------------
# poses
# ---------------------------------------------------------------------------


def capture_pose(scene, pose) -> None:
    """Store the current joint values and free moves into a pose item.

    Only joints that move by themselves: a joint that follows another one gets its place from it."""
    pose.joints.clear()
    pose.places.clear()
    for j in scene.fresing.joints:
        if j.follows:
            continue
        v = pose.joints.add()
        v.joint = j.name
        v.value = joints.get_value(j)
    objs = {ob.name: ob for ob in scene.objects}      # one pass: objects.get() searches every time
    for name, delta in joints.free_moves(scene).items():
        ob = objs.get(name)
        if ob is None:
            continue
        p = pose.places.add()
        p.uid = ob.get(build.PROP_UID, ob.name)
        p.matrix = build.mat_to_list(delta)


def save_pose(scene, name: str):
    s = scene.fresing
    pose = s.poses.get(name)
    if pose is None:
        pose = s.poses.add()
        pose.name = name
    capture_pose(scene, pose)
    s.poses_index = list(s.poses).index(pose)
    return pose


def pose_targets(scene, pose) -> tuple[dict, dict]:
    """(joint name -> value, object name -> delta matrix) for a pose."""
    values = {v.joint: v.value for v in pose.joints}
    uids = by_uid(scene)
    deltas = {}
    for p in pose.places:
        ob = uids.get(p.uid)
        if ob is not None:
            deltas[ob.name] = build.list_to_mat(p.matrix)
    return values, deltas


def apply_pose_data(scene, pose, joints_only: bool = False) -> None:
    values, deltas = pose_targets(scene, pose)
    for j in scene.fresing.joints:
        if j.name in values and not j.follows:       # (a pose saved before it followed another joint)
            joints.set_value(j, values[j.name])
    from . import linkages
    linkages.refresh_all(scene)                     # mechanisms follow their drive joint (also with no 3D view)
    if not joints_only:
        joints.apply_free_moves(scene, deltas, reset_others=True)
    scene.fresing.bounds_valid = False


def apply_pose(scene, name: str) -> bool:
    pose = scene.fresing.poses.get(name)
    if pose is None:
        return False
    apply_pose_data(scene, pose)
    return True


def reset_pose(scene) -> None:
    """Everything back where the CAD file has it."""
    joints.reset_all(scene)
    from . import linkages
    linkages.refresh_all(scene)
    joints.apply_free_moves(scene, {}, reset_others=True)
    scene.fresing.bounds_valid = False


# ---------------------------------------------------------------------------
# exploded views
# ---------------------------------------------------------------------------


def _centre(objs) -> Vector:
    mn, mx = build.world_bounds(objs)
    return Vector(((mn + mx) / 2).tolist())


def explode(scene, target, factor: float, direction: str = "RADIAL", level: str = "CHILDREN") -> int:
    """Move the pieces of ``target`` apart. Returns the number of pieces moved.

    level CHILDREN: the subassemblies/parts directly inside ``target``; PARTS: every part.
    direction RADIAL: away from the centre; X/Y/Z: only along that world axis.
    """
    tree = logic.Tree(scene)
    if level == "PARTS":
        pieces = [d for d in tree.descendants(target) if d.get(build.PROP_KIND) == "part"]
    else:
        pieces = [c for c in tree.children(target) if c.get(build.PROP_KIND) in build.MODEL_KINDS]
    pieces = [p for p in pieces if not p.get(build.PROP_EXCLUDED) and not logic.is_hidden(p)]
    if len(pieces) < 2:
        return 0
    bpy.context.view_layer.update()

    def parts_of(ob):
        if ob.get(build.PROP_KIND) == "part":
            return [ob]
        return [d for d in tree.descendants(ob) if d.get(build.PROP_KIND) == "part"]

    all_parts = [pt for p in pieces for pt in parts_of(p)]
    c0 = _centre(all_parts)
    moves = []
    for p in pieces:
        pts = parts_of(p)
        if not pts:
            continue
        off = (_centre(pts) - c0) * factor
        if direction in ("X", "Y", "Z"):
            axis = {"X": 0, "Y": 1, "Z": 2}[direction]
            off = Vector([off[i] if i == axis else 0.0 for i in range(3)])
        moves.append((p, Matrix.Translation(off) @ p.matrix_world))
    for p, world in moves:                         # all targets computed before anything moves
        parent_world = (p.parent.matrix_world @ p.matrix_parent_inverse) if p.parent else Matrix.Identity(4)
        p.matrix_basis = parent_world.inverted() @ world
    scene.fresing.bounds_valid = False
    return len(moves)


# ---------------------------------------------------------------------------
# visibility sets
# ---------------------------------------------------------------------------


def capture_visibility(scene, vis) -> None:
    """Store what is hidden now. In a built animation, Show/Hide steps hide parts by keys (``fr_anim_hide``), not
    by the ``fr_hidden`` flag: what the frame shows counts (bug hunt row 7). Only the top of a hidden branch is
    stored, as hiding it hides everything below."""
    vis.hidden.clear()
    hidden = []
    keyed = False
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            continue
        if ob.get("fr_anim_hide"):
            keyed = True
            if ob.hide_render:
                hidden.append(ob)
        elif logic.is_hidden(ob):
            hidden.append(ob)
    if keyed:
        names = {ob.name for ob in hidden}

        def covered(ob) -> bool:
            p, n = ob.parent, 0
            while p is not None and n < 256:
                if p.name in names:
                    return True
                p, n = p.parent, n + 1
            return False

        hidden = [ob for ob in hidden if not covered(ob)]
    for ob in hidden:
        vis.hidden.add().uid = ob.get(build.PROP_UID, ob.name)


def save_visibility(scene, name: str):
    s = scene.fresing
    vis = s.visibility_sets.get(name)
    if vis is None:
        vis = s.visibility_sets.add()
        vis.name = name
    capture_visibility(scene, vis)
    s.visibility_index = list(s.visibility_sets).index(vis)
    return vis


def show_all(scene) -> None:
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) in build.MODEL_KINDS and not ob.get(build.PROP_EXCLUDED):
            logic.set_visible_flags(ob, False)
            if ob.get("fr_hidden"):
                ob["fr_hidden"] = False
    scene.fresing.bounds_valid = False


def hidden_objects(scene, vis) -> list:
    uids = by_uid(scene)
    return [uids[h.uid] for h in vis.hidden if h.uid in uids]


def apply_visibility_data(scene, vis) -> None:
    show_all(scene)
    tree = logic.Tree(scene)
    for ob in hidden_objects(scene, vis):
        logic.set_hidden(ob, True, tree)
    scene.fresing.bounds_valid = False


def apply_visibility(scene, name: str) -> bool:
    vis = scene.fresing.visibility_sets.get(name)
    if vis is None:
        return False
    apply_visibility_data(scene, vis)
    return True


# ---------------------------------------------------------------------------
# scenes ("shots")
# ---------------------------------------------------------------------------

WORLD_KEYS = ("background", "background_color", "lighting", "hdri_path", "light_hdri_path", "light_rotation",
              "light_strength", "sun_elevation", "exposure", "floor", "floor_offset", "floor_use_own_color",
              "floor_color",
              # surroundings and props (task 0016)
              "env_detail", "sea_state", "sea_foam", "sea_moving", "water_level", "photo_ground", "photo_height",
              "props_visible",
              # weather of the sky (task 0017)
              "sky_weather")
OUTPUT_KEYS = ("out_format", "out_resolution", "out_orientation", "out_dpi", "out_use_bleed", "out_bleed_mm",
               "out_custom_w", "out_custom_h", "out_file_type", "quality")
CURRENT = "__current__"      # "use what the scene shows now" (stored inside the scene item)


def _plain(v):
    if isinstance(v, (int, float, str, bool)):
        return v
    try:
        return [float(x) for x in v]
    except TypeError:
        return str(v)


def settings_json(s, keys) -> str:
    return json.dumps({k: _plain(getattr(s, k)) for k in keys})


def apply_settings_json(scene, text: str) -> None:
    from . import render, world
    s = scene.fresing
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return
    if "background" in data and "sky_weather" not in data:
        data["sky_weather"] = "SUN"          # saved before the weather existed (task 0017): a sunny sky
    live = s.live_update
    s.live_update = False                    # one world rebuild, not one per setting
    try:
        for k, v in data.items():
            if hasattr(s, k):
                try:
                    setattr(s, k, v)
                except (TypeError, ValueError):
                    pass
    finally:
        s.live_update = live
    render.apply_output(scene, s)
    if any(k in data for k in WORLD_KEYS):
        world.apply(scene, s)
    if "props_visible" in data:
        from . import surroundings
        surroundings.set_props_visible(scene, s.props_visible)


def save_shot(scene, name: str, scheme: str = CURRENT, pose: str = CURRENT, visibility: str = CURRENT,
              camera=None):
    """Save the current look as a scene. CURRENT stores a copy inside the scene item.

    In a built animation the pose and visibility are those of the frame shown; the camera is the static one the
    animation started from (pass ``camera`` to store another, e.g. the queue's copy of the animation camera)."""
    s = scene.fresing
    shot = s.shots.get(name)
    if shot is None:
        shot = s.shots.add()
        shot.name = name
    shot.scheme = scheme
    shot.pose = pose
    shot.visibility = visibility
    cam = camera if camera is not None else scene.camera
    if camera is None and cam is not None and cam.get("fr_anim_camera"):   # never the camera an animation moves
        cam = bpy.data.objects.get(s.anim_restore_camera) or cam
    shot.camera = cam
    if scheme == CURRENT:
        shot.own_scheme.looks.clear()
        for g in s.groups:
            look = shot.own_scheme.looks.add()
            look.group, look.material, look.color = g.name, g.material, g.color
    if pose == CURRENT:
        capture_pose(scene, shot.own_pose)
    if visibility == CURRENT:
        capture_visibility(scene, shot.own_visibility)
    shot.world = settings_json(s, WORLD_KEYS)
    shot.output = settings_json(s, OUTPUT_KEYS)
    s.shots_index = list(s.shots).index(shot)
    return shot


def apply_shot(scene, name: str) -> list[str]:
    """Switch to a saved scene. Returns warnings (missing pose, camera...)."""
    from . import animation
    from . import logic as L
    s = scene.fresing
    shot = s.shots.get(name)
    warnings: list[str] = []
    if shot is None:
        return [f"No scene called '{name}'"]
    animation.clear_keys(scene)            # animation keys would override the scene's pose and visibility
    # looks
    if shot.scheme == CURRENT:
        for look in shot.own_scheme.looks:
            g = s.groups.get(look.group)
            if g is not None:
                g.material, g.color = look.material, look.color
        L.refresh_group_materials(scene)
    elif shot.scheme:
        if not L.apply_scheme(scene, shot.scheme):
            warnings.append(f"Paint scheme '{shot.scheme}' not found")
    # pose
    if shot.pose == CURRENT:
        apply_pose_data(scene, shot.own_pose)
    elif shot.pose:
        if not apply_pose(scene, shot.pose):
            warnings.append(f"Pose '{shot.pose}' not found")
    # visibility
    if shot.visibility == CURRENT:
        apply_visibility_data(scene, shot.own_visibility)
    elif shot.visibility:
        if not apply_visibility(scene, shot.visibility):
            warnings.append(f"Visibility set '{shot.visibility}' not found")
    # camera, background, size
    if shot.camera is not None and shot.camera.name in scene.objects:
        scene.camera = shot.camera
    elif shot.camera is None:
        warnings.append("This scene has no camera")
    else:
        warnings.append("The camera of this scene was deleted")
    apply_settings_json(scene, shot.output)
    apply_settings_json(scene, shot.world)
    s.active_shot = shot.name
    s.bounds_valid = False
    return warnings


def remap_uids(scene, mapping: dict) -> None:
    """After a re-import: point poses, visibility sets and scenes at the new part IDs."""
    s = scene.fresing

    def fix_pose(pose):
        for p in pose.places:
            if p.uid in mapping:
                p.uid = mapping[p.uid]

    def fix_vis(vis):
        for h in vis.hidden:
            if h.uid in mapping:
                h.uid = mapping[h.uid]

    for pose in s.poses:
        fix_pose(pose)
    for vis in s.visibility_sets:
        fix_vis(vis)
    for shot in s.shots:
        fix_pose(shot.own_pose)
        fix_vis(shot.own_visibility)
    for anim in s.animations:
        for b in anim.blocks:
            if b.target_uid in mapping:
                b.target_uid = mapping[b.target_uid]


def unique_pose_name(scene, base="Pose") -> str:
    return _unique(scene.fresing.poses, base)


def unique_visibility_name(scene, base="Visibility") -> str:
    return _unique(scene.fresing.visibility_sets, base)


def unique_shot_name(scene, base="Scene") -> str:
    return _unique(scene.fresing.shots, base)
