"""Lead motions (task 0309): one slider per machine function, in Blender.

A lead motion lives in ``scene.fresing.lead_motions`` (``props.FRLeadMotion``: name, description, seconds, position,
rows). Its slider (``position``, 0 … 100 %) sets the values of the joints its rows name – through
``joints.set_value``, as the joint box does – so whatever follows a joint today (couplings, tables, cylinders,
mechanisms, hoses, cables) follows here too: their own depsgraph handlers do that live; in a background run (tests,
the queue) ``apply`` refreshes them itself, as Go to pose does. Only the joints of that one lead motion are touched.

The numbers (the value of each joint at a slider position, windows, easing, stages) are worked out in plain Python by
``core/lead_motions.py``; this file reads the rows into it and writes the joints.

Rules (also in the guide's "Lead motions"):

* **Two lead motions on one joint:** the last one moved wins. The other one's slider stays where it was and the menu
  says "moved by <the other one>" next to it (``status``). A joint moved by hand since: "moved by hand".
* **A joint that is gone** (removed in a model update, deleted) leaves its row, marked "missing" in red; the rest of
  the lead motion still works. A renamed joint is followed (``joint_renamed``, called by ``joints.rename``).
* **A joint that follows another joint** is never set (its leader decides): its row is marked "follows …".
* **Lead motion steps** (6 Animation) bake to the same joint keys a Move joint step makes – one per frame, worked out
  by the same numbers as the slider (``bake_step``). A Lead motion step and another step that move the same joint at
  the same time: the later-starting step wins from its start (the rule every step already follows), with the Build
  warning "Two steps move … at the same time".
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import bpy

from ..core import lead_motions as core
from . import joints

LAST_KEEP = 20                       # how many "moved last" lead motions are remembered (for "moved by …")
_QUIET = [0]                         # >0: rows are being made: a row change does not move the model
TIMING = {"last_ms": 0.0, "count": 0}    # the last slider change's time (tests, the PC check, the report)


@contextmanager
def quiet():
    """Rows changed inside this block do not move the model (making a lead motion from poses, a recording)."""
    _QUIET[0] += 1
    try:
        yield
    finally:
        _QUIET[0] -= 1


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def find(scene, name: str):
    return scene.fresing.lead_motions.get(name) if name else None


def active(scene):
    s = scene.fresing
    if 0 <= s.lead_index < len(s.lead_motions):
        return s.lead_motions[s.lead_index]
    return None


def owner_of(item):
    """The lead motion a row belongs to (from the row's path: fresing.lead_motions[3].rows[0])."""
    scene = item.id_data
    try:
        path = item.path_from_id()
    except (ValueError, AttributeError):
        return None
    if not path.startswith("fresing.lead_motions["):
        return None
    i = int(path[len("fresing.lead_motions["):].split("]", 1)[0])
    lms = scene.fresing.lead_motions
    return lms[i] if 0 <= i < len(lms) else None


def scene_of(lm):
    return lm.id_data


def to_core(lm) -> core.LeadMotion:
    rows = [core.Row(r.joint, float(r.v0), float(r.v1), float(r.start), float(r.end), r.easing, int(r.stage))
            for r in lm.rows]
    return core.LeadMotion(lm.name, rows, float(lm.seconds), lm.description)


def row_problem(scene, r) -> str:
    """'' when the row's joint can be moved; else a short reason in plain words (shown in red)."""
    if not r.joint:
        return "pick a joint"
    j = joints.find(scene, r.joint)
    if j is None or j.motion is None:
        return "missing"
    if j.follows:
        return f"follows {j.follows}"
    return ""


def usable(scene, lm) -> list:
    """The rows' joints that can be moved: [(row, joint)]."""
    out = []
    for r in lm.rows:
        if row_problem(scene, r):
            continue
        out.append((r, joints.find(scene, r.joint)))
    return out


def free_joints(scene) -> list:
    """The joints a lead motion can list: every joint that does not follow another one."""
    return [j for j in scene.fresing.joints if not j.follows and j.motion is not None]


def current(scene, names=None) -> dict:
    """{joint: value} of the free joints now (all, or those named)."""
    out = {}
    for j in free_joints(scene):
        if names is None or j.name in names:
            out[j.name] = joints.get_value(j)
    return out


def unit_text(scene, joint: str, v: float) -> str:
    import math
    j = joints.find(scene, joint)
    if j is not None and j.kind == "SLIDE":
        return f"{v * 1000.0:.0f} mm"
    return f"{math.degrees(v):.0f}°"


# ---------------------------------------------------------------------------
# moving the model
# ---------------------------------------------------------------------------

def values_at(lm, pct: float) -> dict:
    """{joint: value} of this lead motion at slider position ``pct`` (missing joints included: callers filter)."""
    return core.values(to_core(lm), pct)


def apply(scene, lm, pct: float | None = None, refresh: bool | None = None) -> int:
    """Set the joints of ``lm`` to their values at ``pct`` (default: its slider). Returns how many joints were set.
    ``refresh``: work out mechanisms, hoses and cables now (default: in a background run; in the app their own
    handlers follow the joints live)."""
    import time
    t0 = time.perf_counter()
    pct = float(lm.position) if pct is None else float(pct)
    vals = values_at(lm, pct)
    n = 0
    for r, j in usable(scene, lm):
        if r.joint in vals:
            joints.set_value(j, vals[r.joint])
            n += 1
    _moved(scene, lm)
    if refresh is None:
        refresh = bpy.app.background
    if refresh and n:
        follow(scene)
    if n and scene.fresing.bounds_valid:          # (a scene setting written only when it changes: a write costs an
        scene.fresing.bounds_valid = False        # update of the scene on a big model)
    TIMING["last_ms"] = (time.perf_counter() - t0) * 1000.0
    TIMING["count"] += 1
    return n


def follow(scene) -> None:
    """Mechanisms, hoses and cables follow the joints now (as Go to pose does; also with no 3D view)."""
    from . import flex, linkages, paths
    linkages.refresh_all(scene)
    flex.refresh(scene)
    paths.refresh(scene)


def set_position(lm, pct: float, move: bool = True) -> None:
    """Put the slider at ``pct``; ``move`` = also move the model (else only the slider)."""
    pct = min(max(float(pct), 0.0), 100.0)
    if move:
        lm.position = pct                          # (its update moves the joints)
    else:
        lm["position"] = pct


def position_changed(lm) -> None:
    """The slider moved (a drag, ▶, a script): the joints follow."""
    if _QUIET[0]:
        return
    try:
        apply(scene_of(lm), lm)
    except Exception as exc:  # noqa: BLE001 – never break a slider drag
        print("Fresing Render: lead motion:", exc)


def row_changed(row) -> None:
    """A row's joint, values, window or easing changed: the model follows where the slider stands."""
    if _QUIET[0]:
        return
    lm = owner_of(row)
    if lm is None:
        return
    try:
        apply(scene_of(lm), lm)
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: lead motion:", exc)


def back_to_start(scene) -> int:
    """Every lead motion to 0 %, in reverse order of the list (so the first one's start values win at the end)."""
    n = 0
    for lm in reversed(list(scene.fresing.lead_motions)):
        lm["position"] = 0.0
        n += apply(scene, lm, 0.0, refresh=False)
    if n and bpy.app.background:
        follow(scene)
    return n


# ---------------------------------------------------------------------------
# "moved by …"
# ---------------------------------------------------------------------------

def _last(scene) -> list:
    try:
        data = json.loads(scene.fresing.lead_last or "[]")
        return [str(x) for x in data if isinstance(x, str)]
    except (ValueError, TypeError):
        return []


def _moved(scene, lm) -> None:
    last = _last(scene)
    if last and last[0] == lm.name:
        return
    last = [lm.name] + [n for n in last if n != lm.name]
    scene.fresing.lead_last = json.dumps(last[:LAST_KEEP])


def status(scene, lm) -> str:
    """'' when the model stands where the slider says; else "moved by <lead motion>" or "moved by hand"."""
    rows = usable(scene, lm)
    if not rows:
        return ""
    want = values_at(lm, lm.position)
    for r, j in rows:
        if abs(joints.get_value(j) - want.get(r.joint, 0.0)) > 1e-5 * max(1.0, abs(r.v1 - r.v0)):
            break
    else:
        return ""
    s = scene.fresing
    pairs = [(n, core.joints_of(to_core(s.lead_motions[n]))) for n in _last(scene) if n in s.lead_motions]
    who = core.moved_by(lm.name, [r.joint for r, _j in rows], pairs)
    return f"moved by {who}" if who else "moved by hand"


# ---------------------------------------------------------------------------
# making a lead motion
# ---------------------------------------------------------------------------

def unique_name(scene, base: str = "Lead motion") -> str:
    names = {lm.name for lm in scene.fresing.lead_motions}
    if base not in names:
        return base
    i = 2
    while f"{base} {i}" in names:
        i += 1
    return f"{base} {i}"


def add(scene, name: str = "", rows=(), seconds: float = core.SECONDS, description: str = ""):
    """A new lead motion at the end of the list (its slider at 0 %); ``rows``: core.Row items. Becomes the active one."""
    s = scene.fresing
    with quiet():
        lm = s.lead_motions.add()
        lm.name = unique_name(scene, name.strip() or "Lead motion")
        lm["_old_name"] = lm.name
        lm.seconds = seconds
        lm.description = description
        set_rows(lm, rows)
    s.lead_index = len(s.lead_motions) - 1
    return lm


def set_rows(lm, rows) -> None:
    """Replace the rows (core.Row items) without moving the model."""
    with quiet():
        lm.rows.clear()
        for r in rows:
            x = lm.rows.add()
            x.joint = r.joint
            x["v0"], x["v1"] = float(r.v0), float(r.v1)
            x.start, x.end, x.easing, x.stage = float(r.start), float(r.end), r.easing, int(r.stage)


def _order(scene) -> list:
    return [j.name for j in scene.fresing.joints]


def from_poses(scene, lm, pose_a: str, pose_b: str) -> int:
    """Rows from two saved poses: every free joint whose value differs between them. The model goes to the start
    pose's values (the slider at 0 %). Returns the number of rows; raises RuntimeError with a plain reason."""
    from . import states
    s = scene.fresing
    a, b = s.poses.get(pose_a), s.poses.get(pose_b)
    if a is None or b is None:
        raise RuntimeError("Pick a start pose and an end pose (4 Motion > Poses saves them)")
    if a == b:
        raise RuntimeError("Pick two different poses: the start and the end")
    va, _da = states.pose_targets(scene, a)
    vb, _db = states.pose_targets(scene, b)
    free = {j.name for j in free_joints(scene)}
    va = {k: v for k, v in va.items() if k in free}
    vb = {k: v for k, v in vb.items() if k in free}
    for k in set(va) ^ set(vb):                   # a joint only one pose names: it stays where it is in the other
        j = joints.find(scene, k)
        (vb if k in va else va).setdefault(k, joints.get_value(j))
    rows = core.rows_between(va, vb, _order(scene))
    if not rows:
        raise RuntimeError(f"'{pose_a}' and '{pose_b}' have every joint in the same place: nothing would move")
    set_rows(lm, rows)
    set_position(lm, 0.0, move=True)
    return len(rows)


def record_start(scene) -> int:
    """Record, step 1: remember where every joint is now. Returns how many joints."""
    vals = current(scene)
    scene.fresing.lead_rec = json.dumps(vals)
    return len(vals)


def recording(scene) -> bool:
    return bool(scene.fresing.lead_rec)


def record_end(scene, lm) -> int:
    """Record, step 2: the joints that moved since Set start become the rows (start → now). The slider stands at
    100 % (where the model is). Returns the number of rows; raises RuntimeError with a plain reason."""
    try:
        start = json.loads(scene.fresing.lead_rec or "")
    except ValueError:
        raise RuntimeError("Press Set start first, with the machine where the motion starts") from None
    end = current(scene)
    start = {k: float(v) for k, v in start.items() if k in end}
    rows = core.rows_between(start, end, _order(scene))
    if not rows:
        raise RuntimeError("No joint moved since Set start: move the joints to where the motion ends, then Set end")
    set_rows(lm, rows)
    set_position(lm, 100.0, move=False)
    scene.fresing.lead_rec = ""
    return len(rows)


def add_row(scene, lm, joint_name: str):
    """A row for one joint: from where it is now to its upper limit (or 45° / 500 mm on). Returns the row."""
    import math
    j = joints.find(scene, joint_name)
    if j is None:
        raise RuntimeError("Pick a joint from the list")
    if j.follows:
        raise RuntimeError(f"'{j.name}' follows '{j.follows}' and moves with it: add '{j.follows}' instead")
    v0 = joints.get_value(j)
    if j.use_limits:
        lo, hi = joints.limits(j)
        v1 = hi if abs(hi - v0) > 1e-9 else lo
    else:
        v1 = v0 + (math.radians(45) if j.kind == "ROTATE" else 0.5)
    with quiet():
        r = lm.rows.add()
        r.joint = j.name
        r["v0"], r["v1"] = float(v0), float(v1)
    lm.rows_index = len(lm.rows) - 1
    return r


def apply_stages(lm, overlap: float = 10.0) -> None:
    """Order by stages: every row's window from its stage (stage 1 first …), each stage ``overlap`` % into the next."""
    wins = core.stage_windows([r.stage for r in lm.rows], overlap)
    with quiet():
        for r, (a, b) in zip(lm.rows, wins):
            r.start, r.end = a, b
    row_changed(lm.rows[0]) if len(lm.rows) else None


def joint_renamed(scene, old: str, new: str) -> None:
    """``joints.rename``: rows follow the joint's new name."""
    with quiet():
        for lm in scene.fresing.lead_motions:
            for r in lm.rows:
                if r.joint == old:
                    r.joint = new


# ---------------------------------------------------------------------------
# animation steps
# ---------------------------------------------------------------------------

def _active_anim(scene):
    s = scene.fresing
    if 0 <= s.animations_index < len(s.animations):
        return s.animations[s.animations_index]
    return None


def add_step(scene, anim, lm, p_from: float = 0.0, p_to: float = 100.0, start: float | None = None,
             seconds: float | None = None, use_from: bool = False, label: str = ""):
    """A Lead motion step in ``anim``: at the end of its steps (or at ``start``)."""
    from . import animation
    if start is None:
        start = max((animation.block_end(b) for b in anim.blocks), default=0.0)
    b = anim.blocks.add()
    b.kind = "LEAD"
    b.lead = lm.name
    b.start = round(float(start), 2)
    b.duration = float(seconds if seconds is not None else lm.seconds)
    b.lead_use_from = use_from
    b.lead_from, b.lead_to = float(p_from), float(p_to)
    b.easing = "SMOOTH"
    if label:
        b.name = label
    anim.blocks_index = len(anim.blocks) - 1
    return b


def show_every_function(scene, anim) -> int:
    """One step per lead motion out (0 → 100 %) and back, one after another, at the end of the animation; with
    captions on, the way out gets the lead motion's name (its description when it has one) as its label."""
    from . import animation
    lms = [lm for lm in scene.fresing.lead_motions if usable(scene, lm)]
    start = max((animation.block_end(b) for b in anim.blocks), default=0.0)
    plan = core.show_every_function([(lm.name, lm.seconds) for lm in lms], start)
    for name, a, b, t, sec in plan:
        lm = scene.fresing.lead_motions[name]
        label = (lm.description.strip() or lm.name) if (anim.fin_captions and a < b) else ""
        add_step(scene, anim, lm, a, b, start=t, seconds=sec, label=label)
    return len(plan)


def step_label(b) -> str:
    a = "where it is" if b.lead_use_from else f"{b.lead_from:.0f} %"
    return f"{b.lead or 'Lead motion'}: {a} → {b.lead_to:.0f} %"


def bake_step(scene, anim, b, f0: int, f1: int, jstate: dict, jkeys: dict, busy_until: dict, warnings: list,
              merge, lead_pos: dict) -> None:
    """Keys for a Lead motion step: the slider position eases from → to over the step, every joint of the lead
    motion gets its value on every frame – the same numbers the slider gives (``core.values``). ``lead_pos`` keeps
    each lead motion's slider position along the animation (From where it is)."""
    from . import animation
    lm = find(scene, b.lead)
    label = animation.block_label(b)
    if lm is None:
        warnings.append(f"'{label}': lead motion '{b.lead}' not found" if b.lead else f"'{label}': pick a lead motion")
        return
    rows = usable(scene, lm)
    for r in lm.rows:
        why = row_problem(scene, r)
        if why:
            warnings.append(f"'{label}': the row '{r.joint or '?'}' of '{lm.name}' is left out ({why})")
    if not rows:
        return
    c = to_core(lm)
    p0 = lead_pos.get(lm.name, float(lm.position)) if b.lead_use_from else float(b.lead_from)
    p1 = float(b.lead_to)
    span = max(1, f1 - f0)
    names = []
    for _r, j in rows:
        if j.name not in names and j.name in jstate:
            names.append(j.name)
    start_vals = core.values(c, p0)
    for n in names:
        if busy_until.get(n, 0) > f0:
            warnings.append(f"Two steps move '{n}' at the same time; the later one takes over")
        busy_until[n] = max(f1, f0 + 1)
        if abs(start_vals[n] - jstate[n]) > 1e-5:
            warnings.append(f"'{label}': '{n}' is not where '{lm.name}' has it at {p0:.0f} %: it jumps there when "
                            "the step starts")
    per_frame = {n: [] for n in names}
    for f in range(f0, f0 + span + 1):
        v = core.step_values(c, p0, p1, b.easing, (f - f0) / span)
        for n in names:
            per_frame[n].append((f, v[n]))
    for n in names:
        rows_n = per_frame[n]
        keys = jkeys.setdefault(n, [(1, jstate[n], "CONSTANT", "AUTO")])
        last = len(rows_n) - 1
        for i, (f, v) in enumerate(rows_n):
            # a frame between two equal values adds nothing: one key at each end of a still part is enough
            if 0 < i < last and abs(rows_n[i - 1][1] - v) < 1e-12 and abs(rows_n[i + 1][1] - v) < 1e-12:
                continue
            merge(keys, f, v, "LINEAR" if i < last else "CONSTANT")
        jstate[n] = rows_n[-1][1]
    lead_pos[lm.name] = p1
