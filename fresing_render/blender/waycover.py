"""Way covers (task 0034): telescopic covers that follow one slide axis.

What "Make it" builds: every section becomes an ordinary *slide joint* (the section's parts are its members,
its axis the same as the machine axis) that *follows* the axis joint with a ratio (task 0012 couplings):
section k of N follows k/N of the axis. So poses, Move joint, Run motor, G-code, saved scenes, built
animations and the render queue all move the covers, and everything works with scripts off. The panel
keeps only the list of sections (their names, their joint) and the travel / direction / counting settings.

Nothing here changes the joint code: it calls ``joints.create`` / ``set_follows`` / ``remove``.
"""

from __future__ import annotations

import bpy

from ..core import waycover as core
from . import build, joints

_BUSY = {"on": False}


def settings(scene):
    return scene.fresing.waycover


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def label(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def axis_joint(scene):
    """The axis joint, or None (not picked, or gone)."""
    c = settings(scene)
    return joints.find(scene, c.axis) if c.axis else None


def axis_problem(scene) -> str:
    """'' when the picked axis can drive covers, else the reason (plain words)."""
    c = settings(scene)
    if not c.axis:
        return "Pick the axis the covers follow"
    j = axis_joint(scene)
    if j is None:
        return f"There is no joint called '{c.axis}' (it was removed or renamed): pick the axis again"
    if not joints.is_valid(j):
        return f"'{j.name}' is broken (its arrow was deleted): remove it in 4 Motion first"
    if j.kind != "SLIDE":
        return f"'{j.name}' turns; a way cover follows a joint that slides. Pick a slide joint"
    return ""


def section_joint(scene, sec):
    return joints.find(scene, sec.joint) if sec.joint else None


def is_made(scene, sec) -> bool:
    j = section_joint(scene, sec)
    return j is not None and joints.is_valid(j)


def parts_of(scene, sec) -> list:
    """The section's parts: what its joint moves once made, else the parts chosen so far."""
    j = section_joint(scene, sec)
    if j is not None:
        return joints.members(j)
    return [p.obj for p in sec.parts if p.obj is not None and p.obj.name in scene.objects]


def _holder(scene, ob):
    """(section, joint) of the way cover that already has ``ob`` (or a part above it), else (None, None)."""
    c = settings(scene)
    chain = []
    p = ob
    while p is not None:
        chain.append(p)
        p = build.logical_parent(p)
    for sec in c.sections:
        mine = parts_of(scene, sec)
        for m in mine:
            if any(m is x for x in chain) or _inside(m, ob):
                return sec, section_joint(scene, sec)
    return None, None


def _inside(top, ob) -> bool:
    """True when ``ob`` is below ``top`` in the CAD structure."""
    p = build.logical_parent(ob)
    while p is not None:
        if p is top:
            return True
        p = build.logical_parent(p)
    return False


def _moving_joint(scene, ob):
    """The joint that moves ``ob`` directly or through a subassembly above it, else None."""
    p = ob
    while p is not None:
        j = joints.joint_of_object(scene, p)
        if j is not None:
            return j
        p = build.logical_parent(p)
    return None


def check_parts(scene, objs, own=None) -> str:
    """'' when ``objs`` can make (or join) a way cover section, else the reason. ``own``: the section being
    changed (its own parts are no conflict)."""
    if not objs:
        return "Click the parts of one section first (any number of parts or subassemblies)"
    c = settings(scene)
    for ob in objs:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            return f"{ob.name} is not part of the model"
        sec, _j = _holder(scene, ob)
        if sec is not None and (own is None or sec.name != own.name):
            return f"'{label(ob)}' is in section '{sec.name}' already: a part belongs to one section only"
        j = _moving_joint(scene, ob)
        if j is not None and not (own is not None and j.name == own.joint):
            if j.follows:
                return (f"'{label(ob)}' moves with joint '{j.name}', which follows '{j.follows}' already. "
                        "A section needs parts that move by themselves: take them out of that joint first")
            if c.axis and j.name == c.axis:
                return (f"'{label(ob)}' moves with the axis joint '{j.name}' itself. The covers are separate "
                        "parts: pick the parts of the covers, not the carriage")
            return (f"'{label(ob)}' moves with joint '{j.name}' already: take it out of that joint "
                    "(4 Motion > Joints) before using it in a way cover")
    ax = axis_joint(scene)
    base = ax.frame.parent if ax is not None and ax.frame is not None else None
    return joints.check_members(scene, [o for o in objs], base)


# ---------------------------------------------------------------------------
# changes
# ---------------------------------------------------------------------------

def _unique_section_name(scene, base: str) -> str:
    names = {s.name for s in settings(scene).sections}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def add_section(scene, objs, name: str = ""):
    """Add a section (not built yet) made of ``objs`` at the moving end of the row."""
    reason = check_parts(scene, objs)
    if reason:
        raise RuntimeError(reason)
    c = settings(scene)
    sec = c.sections.add()
    sec.name = _unique_section_name(scene, name or f"Section {len(c.sections)}")
    for ob in objs:
        sec.parts.add().obj = ob
    c.sections_index = len(c.sections) - 1
    refresh(scene)
    return sec


def remove_section(scene, index: int) -> list[str]:
    """Take a section out: its joint goes (its parts go back to their CAD place), the others share anew."""
    c = settings(scene)
    if not 0 <= index < len(c.sections):
        return []
    sec = c.sections[index]
    freed = []
    j = section_joint(scene, sec)
    if j is not None:
        freed = joints.remove(scene, j)
    c.sections.remove(index)
    c.sections_index = max(0, min(c.sections_index, len(c.sections) - 1))
    refresh(scene)
    return freed


def move_section(scene, index: int, delta: int) -> None:
    c = settings(scene)
    new = index + delta
    if 0 <= index < len(c.sections) and 0 <= new < len(c.sections):
        c.sections.move(index, new)
        c.sections_index = new
        refresh(scene)


def remove_all(scene) -> int:
    """Remove the way cover: the couplings and joints it made go, nothing else. Returns the sections removed."""
    c = settings(scene)
    n = len(c.sections)
    while len(c.sections):
        sec = c.sections[len(c.sections) - 1]
        j = section_joint(scene, sec)
        if j is not None:
            joints.remove(scene, j)
        c.sections.remove(len(c.sections) - 1)
    c.sections_index = 0
    return n


def read_total(scene) -> str:
    """Take the total travel from the axis joint's limits. Returns '' or the reason it cannot."""
    reason = axis_problem(scene)
    if reason:
        return reason
    j = axis_joint(scene)
    if not j.use_limits:
        return (f"'{j.name}' has no limits. Tick Limits in its joint set-up (4 Motion), or type the "
                "total length of movement")
    total = abs(j.slide_max - j.slide_min)
    if total <= 0:
        return f"The limits of '{j.name}' are equal: set its Min and Max, or type the total length of movement"
    settings(scene).total = total
    return ""


def shares(scene) -> list[float]:
    c = settings(scene)
    return core.signed(core.shares(len(c.sections), c.housing_counts), c.flip)


def _limits_for(axis, share: float, total: float) -> tuple[float, float]:
    lo, hi = (axis.slide_min, axis.slide_max) if axis.use_limits else (0.0, total)
    a, b = lo * share, hi * share
    return (min(a, b), max(a, b))


def _apply(scene, sec, share: float, axis) -> bool:
    """Make section ``sec``'s joint follow ``axis`` with ``share``; True when something changed."""
    j = section_joint(scene, sec)
    c = settings(scene)
    changed = False
    if j.follows != axis.name or abs(j.couple_ratio - share) > 1e-6:
        joints.set_follows(scene, j, axis.name, ratio=share)
        changed = True
    lo, hi = _limits_for(axis, share, c.total)
    if (not j.use_limits or abs(j.slide_min - lo) > 1e-6 or abs(j.slide_max - hi) > 1e-6):
        joints._set_raw(j, use_limits=True, slide_min=lo, slide_max=hi)
        joints.apply_limits(j, joints._model_size(scene), clamp=False)
        changed = True
    return changed


def refresh(scene) -> int:
    """Give every made section the share its place in the row, the travel and the direction call for.
    Returns how many joints changed. Safe to call at any time (no axis / nothing made: does nothing)."""
    if _BUSY["on"]:
        return 0
    c = settings(scene)
    if not len(c.sections) or axis_problem(scene):
        return 0
    axis = axis_joint(scene)
    sh = shares(scene)
    n = 0
    _BUSY["on"] = True
    try:
        for i, sec in enumerate(c.sections):
            if is_made(scene, sec):
                n += 1 if _apply(scene, sec, sh[i], axis) else 0
        if n:
            joints._update(scene)
    finally:
        _BUSY["on"] = False
    return n


def make(scene) -> tuple[int, list[str]]:
    """Build the joints of the sections that have none yet and make every section follow the axis.
    Returns (sections built now, problems)."""
    reason = axis_problem(scene)
    if reason:
        raise RuntimeError(reason)
    c = settings(scene)
    if not len(c.sections):
        raise RuntimeError("Add at least one section first: click its parts, then 'Add section'")
    axis = axis_joint(scene)
    if c.total <= 0 and not axis.use_limits:
        raise RuntimeError("Set the total length of movement first (or give the axis limits and press "
                           "'Read from the axis')")
    if joints.follow_check(scene, axis, ""):
        raise RuntimeError(joints.follow_check(scene, axis, ""))
    problems, built = [], 0
    base = axis.frame.parent
    frame_world = axis.frame.matrix_world.copy()   # (the joint list grows below: keep no reference into it)
    axis = None
    for sec in c.sections:
        if is_made(scene, sec):
            continue
        objs = parts_of(scene, sec)
        if not objs:
            problems.append(f"Section '{sec.name}' has no parts (they were removed): add the section again")
            continue
        reason = check_parts(scene, objs, own=sec)
        if reason:
            problems.append(f"Section '{sec.name}': {reason}")
            continue
        try:
            j = joints.create(scene, "SLIDE", objs, None, None, name=f"Way cover {sec.name}", base=base,
                              ref=base, frame_world=frame_world)
        except RuntimeError as exc:
            problems.append(f"Section '{sec.name}': {exc}")
            continue
        sec.joint = j.name
        sec.parts.clear()
        built += 1
    refresh(scene)
    return built, problems


# ---------------------------------------------------------------------------
# status text and the hooks other modules call
# ---------------------------------------------------------------------------

def state_counts(scene) -> tuple[int, int]:
    """(sections, sections built)."""
    c = settings(scene)
    return len(c.sections), sum(1 for s in c.sections if is_made(scene, s))


def status(scene) -> str:
    """The panel header: '5 sections · 100 mm each · follows 'Y axis''; '' when there is nothing."""
    c = settings(scene)
    n, made = state_counts(scene)
    if not n:
        return ""
    if made < n:
        return f"{n} sections · {n - made} not made yet" if n != 1 else "1 section · not made yet"
    each = core.travel_each(c.total * 1000.0, n, c.housing_counts)
    word = "section" if n == 1 else "sections"
    return f"{n} {word} · {each:g} mm each · follows '{c.axis}'"


def joint_renamed(scene, old: str, new: str) -> None:
    """Hook for ``joints.rename``: the way cover keeps following the same joints."""
    c = settings(scene)
    if c.axis == old:
        c["axis"] = new
    for sec in c.sections:
        if sec.joint == old:
            sec.joint = new


def after_joints_rebuilt(scene) -> list[str]:
    """Hook for model updates: sections whose joint came back keep it; the others are told. Shares again."""
    notes = []
    c = settings(scene)
    for sec in c.sections:
        if sec.joint and section_joint(scene, sec) is None:
            notes.append(f"Way cover section '{sec.name}' lost its joint in the model update: add its parts again")
            sec.joint = ""
    if c.axis and axis_joint(scene) is None:
        notes.append(f"Way cover axis '{c.axis}' is gone after the model update: pick the axis again")
    refresh(scene)
    return notes


def register():
    pass


def unregister():
    pass
