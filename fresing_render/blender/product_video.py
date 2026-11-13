"""One-click product video (task 0101).

Builds (or updates) the animation "Product video" from what the project already has, with ordinary steps the owner
can change in 6 Animation: title card -> one turn round the machine -> the machine's joints (each to its far limit and
back, a camera that watches the moving part) -> saved poses -> an Assembly sequence (take apart, hold, put together)
on one subassembly -> close-ups from saved cameras -> end card. Pieces the project has no material for are left out,
and the status line says which and why. The animation is tagged ``fr_product_video``; pressing again replaces its
steps (the operator asks first when the owner changed them: ``changed``). No other animation is touched.
"""

from __future__ import annotations

import math

from ..core import presets, sequence as seq_core
from . import animation, build, cameras, joints, logic, sequence, states

TAG = "fr_product_video"
NAME = "Product video"
CAM_TAG = "fr_product_video_cam"
SIG = "fr_pv_sig"

LENGTHS = (30, 60, 90)
MIN_PARTS = 5                 # a subassembly worth taking apart
CARD_S = 3.0
HOLD_S = 1.5                  # the sequence stands apart this long


def find_animation(scene):
    return next((a for a in scene.fresing.animations if a.get(TAG)), None)


# ---------------------------------------------------------------------------
# what the project has
# ---------------------------------------------------------------------------

def _uid(ob) -> str:
    return ob.get(build.PROP_UID, ob.name)


def pick_subassembly(scene, tree=None):
    """The subassembly with the most parts (at least MIN_PARTS) that is not the whole model, else None."""
    tree = tree or logic.Tree(scene)
    roots = build.model_roots(scene)
    total = sum(logic.part_count(r, tree) for r in roots)
    skip = set()
    for r in roots:
        skip.add(r.name)
        skip.add(logic.top_level(r, tree).name)
    best, best_n = None, 0
    for ob in scene.objects:
        if ob.get(build.PROP_KIND) != "assembly" or ob.name in skip:
            continue
        n = logic.part_count(ob, tree)
        if n >= MIN_PARTS and n < total and n > best_n:
            best, best_n = ob, n
    return best


def chosen_subassembly(scene, tree=None):
    """(object or None, why not) for the option 'Take apart'."""
    s = scene.fresing
    if s.pv_sub == "NONE":
        return None, "you chose no subassembly to take apart"
    if s.pv_sub == "SELECTED":
        i = s.tree_index
        ob = s.tree[i].obj if 0 <= i < len(s.tree) else None
        if ob is None or ob.get(build.PROP_KIND) != "assembly":
            return None, "no subassembly is selected in the structure list"
        return ob, ""
    ob = pick_subassembly(scene, tree)
    if ob is None:
        return None, f"no subassembly with {MIN_PARTS} or more parts (apart from the whole model)"
    return ob, ""


def _span(j, diag: float) -> float:
    """How far a joint can travel, as a share of a full effort (to sort the longest first)."""
    lo, hi = joints.limits(j)
    if j.kind == "ROTATE":
        return (hi - lo) / math.pi if j.use_limits else 0.5
    return (hi - lo) / max(diag, 1e-6) if j.use_limits else 0.2


def usable_joints(scene, diag: float) -> list:
    """Joints worth showing: they move parts, are not followers, motors or cables; longest travel first."""
    from . import paths
    out = []
    for j in scene.fresing.joints:
        if j.motion is None or j.follows or joints.is_motor(j) or not len(j.members):
            continue
        if paths.is_cable_joint(scene, j) or j.get("fr_atc"):
            continue
        if not any(m.obj is not None for m in j.members):
            continue
        if j.use_limits and _span(j, diag) <= 1e-6:
            continue
        out.append(j)
    out.sort(key=lambda j: -_span(j, diag))
    return out


def saved_cameras(scene) -> list:
    return [c for c in cameras.fr_cameras(scene)
            if not c.get("fr_anim_camera") and not c.get(CAM_TAG) and not c.get("fr_turntable")]


# ---------------------------------------------------------------------------
# the plan: a list of steps (plain dicts), made before anything is written
# ---------------------------------------------------------------------------

def plan(scene, seconds: int | None = None) -> dict:
    """Works out the steps. Returns {"steps": [...], "left_out": [reasons], "sub": object|None, "seconds": float}."""
    s = scene.fresing
    total = float(seconds or int(s.pv_seconds))
    cards = (CARD_S if s.pv_title_on else 0.0) + (CARD_S if s.pv_end_on else 0.0)
    body = max(6.0, total - cards)
    left: list[str] = []
    mn, mx = logic.update_bounds(scene)
    diag = float(math.dist(mn, mx)) or 1.0
    tree = logic.Tree(scene)

    js = usable_joints(scene, diag)[:max(0, s.pv_motions)] if s.pv_motions else []
    if not js:
        left.append("the machine's motions (no joint with a range to show)" if s.pv_motions
                    else "the machine's motions (you chose none)")
    poses = list(s.poses)[:max(0, s.pv_motions)] if s.pv_motions else []
    sub, why = chosen_subassembly(scene, tree)
    parts = []
    if sub is not None:
        parts = sequence.movers(scene, sub, tree).parts
        if len(parts) < 2:
            sub, why = None, "its parts would not move (hoses and chain links are drawn by the app)"
    if sub is None:
        left.append(f"the take-apart ({why})")
    closeups = saved_cameras(scene)[:2]
    if not closeups:
        left.append("close-ups (no saved cameras)")

    # shares of the body time, then re-scaled to the pieces that exist
    shares = {"orbit": 0.22}
    if js or poses:
        shares["motion"] = 0.36
    if sub is not None:
        shares["seq"] = 0.32
    if closeups:
        shares["close"] = 0.10
    k = 1.0 / sum(shares.values())
    t = {name: body * v * k for name, v in shares.items()}

    steps: list[dict] = []
    clock = 0.0

    def add(**kw):
        kw.setdefault("start", clock)
        steps.append(kw)

    add(kind="CAMERA", label="Round the machine", camera_mode="ORBIT", angle=360.0, duration=t["orbit"],
        easing="LINEAR")
    clock += t["orbit"]

    if js or poses:
        n = len(js) + len(poses)
        each = t["motion"] / n
        for j in js:
            lo, hi = joints.limits(j)
            now = joints.get_value(j)
            far = hi if (hi - now) >= (now - lo) else lo
            if not j.use_limits:
                far = now + (math.radians(45) if j.kind == "ROTATE" else 0.1 * diag)
            if abs(far - now) < 1e-6:
                continue
            m = next(m.obj for m in j.members if m.obj is not None)
            half = each / 2
            for way, (a, b) in (("", (now, far)), (" back", (far, now))):
                add(kind="JOINT", label=f"{j.name}{way}", joint=j.name, from_value=a, to_value=b, duration=half,
                    easing="SMOOTH")
                if not way:
                    add(kind="CAMERA", label="", camera_mode="AIM", aim_uid=_uid(m), aim_name=m.name,
                        duration=each, start=clock)
                clock += half
        for p in poses:
            add(kind="POSE", label=f"Pose {p.name}", pose=p.name, duration=each, easing="SMOOTH")
            clock += each

    if sub is not None:
        n = len(parts)
        hold = min(HOLD_S, t["seq"] * 0.15)
        per_run = (t["seq"] - hold) / 2
        one = seq_core.duration(n, 1.0, 0.5)
        per_part = max(0.05, per_run / one) if one > 0 else 1.0
        add(kind="CAMERA", label="", camera_mode="MOVE", camera_for=sub.name, duration=min(2.0, per_run / 2),
            easing="SMOOTH")
        for mode, label in (("APART", f"Take {sub.get(build.PROP_NAME, sub.name)} apart"),
                            ("TOGETHER", "Put it together")):
            add(kind="SEQUENCE", label=label, seq_mode=mode, uid=_uid(sub), name=sub.get(build.PROP_NAME, sub.name),
                per_part=per_part, duration=per_run, easing="SMOOTH")
            clock += per_run + (hold if mode == "APART" else 0.0)

    if closeups:
        each = t["close"] / len(closeups)
        for c in closeups:
            add(kind="CAMERA", label=c.name, camera_mode="MOVE", camera_obj=c.name, duration=each, easing="SMOOTH")
            clock += each

    return {"steps": steps, "left_out": left, "sub": sub, "seconds": clock + cards, "body": clock}


# ---------------------------------------------------------------------------
# writing it
# ---------------------------------------------------------------------------

def _sig(a) -> str:
    rows = []
    for b in a.blocks:
        rows.append(f"{b.kind}|{b.name}|{b.joint}|{b.pose}|{b.camera_mode}|{b.target_uid}|{b.enabled}|"
                    f"{b.start:.3f}|{b.duration:.3f}|{b.to_angle:.4f}|{b.to_dist:.4f}|{getattr(b.camera, 'name', '')}")
    return "\n".join(rows)


def changed(scene) -> bool:
    """True when the owner changed the steps of the existing Product video since it was made."""
    a = find_animation(scene)
    return a is not None and a.get(SIG) is not None and a.get(SIG) != _sig(a)


def _drop_old_cameras(scene) -> None:
    for c in list(cameras.fr_cameras(scene)):
        if c.get(CAM_TAG):
            data = c.data
            bpy_remove(c, data)


def bpy_remove(ob, data) -> None:
    import bpy
    bpy.data.objects.remove(ob, do_unlink=True)
    if data is not None and data.users == 0:
        bpy.data.cameras.remove(data)


def _frame_camera(scene, name: str, points, view: str = "ISO", margin: float = 1.5):
    cam = cameras.add_camera(scene, view, name=name, points=points, margin=margin)
    cam[CAM_TAG] = True
    cam.hide_viewport = False
    return cam


def _bounds_points(objs):
    import numpy as np
    mn, mx = build.world_bounds([o for o in objs if o.type == "MESH"])
    return np.array([mn, mx], dtype=float)


def make(scene) -> dict:
    """Make or update the animation. Returns {animation, plan, seconds, left_out}."""
    s = scene.fresing
    if animation.has_keys(scene):
        animation.clear_keys(scene)
    info = plan(scene)
    tree = logic.Tree(scene)

    a = find_animation(scene)
    if a is None:
        a = s.animations.add()
        a.name = animation.unique_name(scene, NAME)
        a[TAG] = True
    _drop_old_cameras(scene)

    # the start: the machine as it is, seen from a camera that frames all of it
    model_pts = cameras._points(scene)
    r = scene.render
    size = presets.compute(a.out_format, a.out_resolution, "auto", 300, 0.0, 1920, 1080)
    r.resolution_x, r.resolution_y = size.width, size.height
    r.pixel_aspect_x = r.pixel_aspect_y = 1.0
    from . import render
    try:
        cam0 = _frame_camera(scene, f"{NAME} start", model_pts, "ISO", cameras.SPACE.get(s.view_space, 1.06) + 0.1)
        cam_sub = None
        if info["sub"] is not None:
            sub_objs = logic.descendants(info["sub"], tree)
            cam_sub = _frame_camera(scene, f"{NAME} {info['sub'].name}", _bounds_points(sub_objs), "ISO", 1.9)
    finally:
        render.apply_output(scene, s)

    keep = s.shots_index
    shot = next((x for x in s.shots if x.get(TAG)), None)
    shot = states.save_shot(scene, shot.name if shot is not None else states.unique_shot_name(scene, NAME),
                            camera=cam0)
    shot[TAG] = True
    s.shots_index = keep if keep < len(s.shots) else s.shots_index

    a.start_shot = shot.name
    a.tail = 1.0
    a.blocks.clear()
    for st in info["steps"]:
        b = a.blocks.add()
        b.kind = st["kind"]
        b.name = st["label"]
        b.start = st["start"]
        b.duration = st["duration"]
        b.easing = st.get("easing", "SMOOTH")
        if st["kind"] == "JOINT":
            j = s.joints[st["joint"]]
            b.joint = j.name
            b.use_from = False
            if j.kind == "ROTATE":
                b.from_angle, b.to_angle = st["from_value"], st["to_value"]
            else:
                b.from_dist, b.to_dist = st["from_value"], st["to_value"]
        elif st["kind"] == "POSE":
            b.pose = st["pose"]
        elif st["kind"] == "SEQUENCE":
            b.target_uid, b.target_name = st["uid"], st["name"]
            b.seq_id = __import__("uuid").uuid4().hex[:12]
            b.seq_mode = st["seq_mode"]
            b.seq_part_time = st["per_part"]
            b.seq_overlap = 50.0
            b.duration = st["duration"]
        elif st["kind"] == "CAMERA":
            b.camera_mode = st["camera_mode"]
            if st["camera_mode"] == "ORBIT":
                b.orbit_angle = math.radians(st["angle"])
            elif st["camera_mode"] == "AIM":
                b.aim_uid, b.aim_name = st["aim_uid"], st["aim_name"]
            elif st.get("camera_for"):
                b.camera = cam_sub
            else:
                b.camera = scene.objects.get(st["camera_obj"])
    # the sequence steps' length follows from their parts: keep what the plan set (count() would re-set it)
    for b in a.blocks:
        if b.kind == "SEQUENCE":
            sequence.count(scene, b)

    # cards and captions
    a.fin_title_on = bool(s.pv_title_on)
    a.fin_title = s.pv_title.strip() or _project_name(scene)
    a.fin_title_seconds = CARD_S
    a.fin_end_on = bool(s.pv_end_on)
    a.fin_end_seconds = CARD_S
    a.fin_captions = bool(s.pv_captions)
    a[SIG] = _sig(a)
    s.animations_index = list(s.animations).index(a)
    info["animation"] = a
    info["seconds"] = animation.length_seconds(a) + (CARD_S if a.fin_title_on else 0.0) + \
        (CARD_S if a.fin_end_on else 0.0)
    return info


def _project_name(scene) -> str:
    import bpy
    n = bpy.path.display_name_from_filepath(bpy.data.filepath) if bpy.data.filepath else ""
    if n:
        return n
    roots = build.model_roots(scene)
    return str(roots[0].get(build.PROP_NAME, roots[0].name)) if roots else "Product video"


def status(info: dict) -> str:
    text = f"About {info['seconds']:.0f} s, {len(info['animation'].blocks)} steps."
    if info["left_out"]:
        text += " Left out: " + "; ".join(info["left_out"]) + "."
    return text
