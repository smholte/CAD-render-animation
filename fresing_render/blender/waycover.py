"""Way covers (task 0034): telescopic covers that follow one slide axis.

What "Make it" builds: every section becomes an ordinary *slide joint* (the section's parts are its members,
its axis the same as the machine axis) that *follows* the axis joint with a ratio (task 0012 couplings):
section k of N follows k/N of the axis. So poses, Move joint, Run motor, G-code, saved scenes, built
animations and the render queue all move the covers, and everything works with scripts off. The panel
keeps only the list of sections (their names, their joint) and the travel / direction / counting settings.

Nothing here changes the joint code: it calls ``joints.create`` / ``set_follows`` / ``remove``.

Task 0035: a project holds a list of covers (``scene.fresing.waycovers``): one each side of the table, covers on
several axes, each with its own axis, sections and travel. Projects saved with one cover (``scene.fresing.waycover``,
0.2.28 …) open with it as the first item of the list (``migrate``, at load); until then that one counts as the only
cover. The last section may be the carriage itself (parts the axis joint moves): it takes share 1, counts in N and
gets no joint of its own.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from ..core import waycover as core
from . import build, joints

_BUSY = {"on": False}

def _has_content(c) -> bool:
    return bool(c.axis or len(c.sections))


def _legacy(scene):
    """The one cover of a project saved before task 0035 (still in use while the list is empty)."""
    return scene.fresing.waycover


def covers(scene) -> list:
    """Every way cover of the project."""
    s = scene.fresing
    if len(s.waycovers):
        return list(s.waycovers)
    return [s.waycover] if _has_content(s.waycover) else []


def settings(scene):
    """The chosen way cover (the one the panel shows). With no list yet: the project's single cover."""
    s = scene.fresing
    if len(s.waycovers):
        i = max(0, min(s.waycovers_index, len(s.waycovers) - 1))
        return s.waycovers[i]
    return s.waycover


def _copy(src, dst) -> None:
    dst["axis"] = src.axis                          # (item access: no update callbacks while copying)
    dst["total"] = src.total
    dst["flip"] = src.flip
    dst["housing_counts"] = src.housing_counts
    dst["drawn_at"] = src.drawn_at
    for sec in src.sections:
        d = dst.sections.add()
        d.name, d.joint, d.carriage, d.uids = sec.name, sec.joint, sec.carriage, sec.uids
        for p in sec.parts:
            d.parts.add().obj = p.obj
    dst.sections_index = src.sections_index


def migrate(scene) -> bool:
    """A project saved with one way cover: that cover becomes the first item of the list (joints untouched).
    True when something moved."""
    s = scene.fresing
    old = s.waycover
    if len(s.waycovers) or not _has_content(old):
        return False
    c = s.waycovers.add()
    c.name = "Way cover"
    _copy(old, c)
    old.sections.clear()
    old["axis"] = ""
    s.waycovers_index = 0
    return True


def add_cover(scene, name: str = ""):
    """A new, empty way cover at the end of the list; it becomes the chosen one."""
    migrate(scene)
    s = scene.fresing
    names = {c.name for c in s.waycovers}
    base = name or "Way cover"
    new = base
    n = 2
    while new in names:
        new = f"{base} {n}"
        n += 1
    c = s.waycovers.add()
    c.name = new
    s.waycovers_index = len(s.waycovers) - 1
    return c


def ensure_cover(scene):
    """The chosen cover, making the first one when the project has none (buttons call this)."""
    migrate(scene)
    s = scene.fresing
    if not len(s.waycovers):
        return add_cover(scene)
    return settings(scene)


def remove_cover(scene, index: int | None = None) -> int:
    """Take a whole way cover out: the joints it made go, its parts return to their CAD place. The axis joint and
    the carriage stay as they are. Returns the sections removed."""
    migrate(scene)
    s = scene.fresing
    if index is None:
        index = s.waycovers_index
    if not 0 <= index < len(s.waycovers):
        return 0
    n = remove_all(scene, s.waycovers[index])
    s.waycovers.remove(index)
    s.waycovers_index = max(0, min(s.waycovers_index, len(s.waycovers) - 1))
    return n


def cover_of_section(scene, sec):
    for c in covers(scene):
        if any(x == sec for x in c.sections):
            return c
    return None


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def label(ob) -> str:
    return ob.get(build.PROP_NAME, ob.name) if ob is not None else ""


def axis_joint(scene, cover=None):
    """The axis joint, or None (not picked, or gone)."""
    c = cover or settings(scene)
    return joints.find(scene, c.axis) if c.axis else None


def axis_problem(scene, cover=None) -> str:
    """'' when the picked axis can drive covers, else the reason (plain words)."""
    c = cover or settings(scene)
    if not c.axis:
        return "Pick the axis the covers follow"
    j = axis_joint(scene, c)
    if j is None:
        return f"There is no joint called '{c.axis}' (it was removed or renamed): pick the axis again"
    if not joints.is_valid(j):
        return f"'{j.name}' is broken (its arrow was deleted): remove it in 4 Motion first"
    if j.kind != "SLIDE":
        return f"'{j.name}' turns; a way cover follows a joint that slides. Pick a slide joint"
    return ""


def section_joint(scene, sec):
    return joints.find(scene, sec.joint) if sec.joint else None


def _chosen_parts(scene, sec) -> list:
    return [p.obj for p in sec.parts if p.obj is not None and p.obj.name in scene.objects]


def is_made(scene, sec) -> bool:
    """The section moves with the axis: its joint is there (or, on the carriage, its parts are)."""
    if sec.carriage:
        return bool(_chosen_parts(scene, sec))
    j = section_joint(scene, sec)
    return j is not None and joints.is_valid(j)


def parts_of(scene, sec) -> list:
    """The section's parts: what its joint moves once made, else the parts chosen so far."""
    if sec.carriage:
        return _chosen_parts(scene, sec)
    j = section_joint(scene, sec)
    if j is not None:
        return joints.members(j)
    return _chosen_parts(scene, sec)


def _holder(scene, ob, carriage: bool = False):
    """(section, cover) of the way cover that already has ``ob`` (or a part above it), else (None, None).
    ``carriage``: looking for room for a carriage section – the carriage sections of other covers are no
    conflict (a cover on each side may both end on the carriage)."""
    chain = []
    p = ob
    while p is not None:
        chain.append(p)
        p = build.logical_parent(p)
    for c in covers(scene):
        for sec in c.sections:
            if carriage and sec.carriage:
                continue
            for m in parts_of(scene, sec):
                if any(m is x for x in chain) or _inside(m, ob):
                    return sec, c
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


def on_carriage(scene, objs, cover=None) -> bool:
    """True when every one of ``objs`` moves with the cover's axis joint itself (the carriage)."""
    c = cover or settings(scene)
    if not objs or not c.axis:
        return False
    for ob in objs:
        j = _moving_joint(scene, ob)
        if j is None or j.name != c.axis:
            return False
    return True


def _carriage_index(c) -> int:
    """Index of the cover's carriage section, or -1."""
    for i, sec in enumerate(c.sections):
        if sec.carriage:
            return i
    return -1


def check_parts(scene, objs, own=None, cover=None) -> str:
    """'' when ``objs`` can make (or join) a way cover section, else the reason. ``own``: the section being
    changed (its own parts are no conflict)."""
    if not objs:
        return "Click the parts of one section first (any number of parts or subassemblies)"
    c = cover or settings(scene)
    carriage = on_carriage(scene, objs, c)
    if own is None and carriage:
        k = _carriage_index(c)
        if k >= 0:
            return (f"'{c.sections[k].name}' is the carriage already: a cover has one carriage section, the last "
                    "one")
    if own is None and not carriage and _carriage_index(c) >= 0:
        sec = c.sections[_carriage_index(c)]
        return (f"'{sec.name}' is on the carriage, so it must stay the last section (the moving end). Remove it, "
                "add this section, then add the carriage parts again")
    for ob in objs:
        if ob.get(build.PROP_KIND) not in build.MODEL_KINDS:
            return f"{ob.name} is not part of the model"
        sec, _cv = _holder(scene, ob, carriage)
        if sec is not None and (own is None or sec != own):
            return f"'{label(ob)}' is in section '{sec.name}' already: a part belongs to one section only"
        if carriage:
            continue
        j = _moving_joint(scene, ob)
        if j is not None and not (own is not None and j.name == own.joint):
            if j.follows:
                return (f"'{label(ob)}' moves with joint '{j.name}', which follows '{j.follows}' already. "
                        "A section needs parts that move by themselves: take them out of that joint first")
            if c.axis and j.name == c.axis:
                return (f"'{label(ob)}' moves with the axis joint '{j.name}' itself, the others you clicked do not. "
                        "Add the carriage parts on their own, as the last section")
            return (f"'{label(ob)}' moves with joint '{j.name}' already: take it out of that joint "
                    "(4 Motion > Joints) before using it in a way cover")
    if carriage:
        return ""
    ax = axis_joint(scene, c)
    base = ax.frame.parent if ax is not None and ax.frame is not None else None
    return joints.check_members(scene, [o for o in objs], base)


# ---------------------------------------------------------------------------
# changes
# ---------------------------------------------------------------------------

def _unique_section_name(c, base: str) -> str:
    names = {s.name for s in c.sections}
    if base not in names:
        return base
    n = 2
    while f"{base} {n}" in names:
        n += 1
    return f"{base} {n}"


def add_section(scene, objs, name: str = "", cover=None):
    """Add a section (not built yet) made of ``objs`` at the moving end of the row. Parts the axis joint itself
    moves become the carriage section (the last one; no joint of its own)."""
    c = cover or settings(scene)
    reason = check_parts(scene, objs, cover=c)
    if reason:
        raise RuntimeError(reason)
    carriage = on_carriage(scene, objs, c)
    sec = c.sections.add()
    base = name or f"Section {len(c.sections)}"
    sec.name = _unique_section_name(c, base)
    sec.carriage = carriage
    for ob in objs:
        sec.parts.add().obj = ob
    if carriage:
        sec.uids = "\n".join(ob.get(build.PROP_UID, "") for ob in objs)
    c.sections_index = len(c.sections) - 1
    refresh(scene)
    return sec


def remove_section(scene, index: int, cover=None) -> list[str]:
    """Take a section out: its joint goes (its parts go back to their CAD place), the others share anew.
    A carriage section has no joint: the carriage is left alone."""
    c = cover or settings(scene)
    if not 0 <= index < len(c.sections):
        return []
    sec = c.sections[index]
    freed = []
    j = None if sec.carriage else section_joint(scene, sec)
    if j is not None:
        freed = joints.remove(scene, j)
    c.sections.remove(index)
    c.sections_index = max(0, min(c.sections_index, len(c.sections) - 1))
    refresh(scene)
    return freed


def move_problem(c, index: int, delta: int) -> str:
    """'' when the section may move one place, else the reason (the carriage stays the last section)."""
    new = index + delta
    if not (0 <= index < len(c.sections) and 0 <= new < len(c.sections)):
        return "It is at the end of the row already"
    if c.sections[index].carriage or c.sections[new].carriage:
        k = index if c.sections[index].carriage else new
        return (f"'{c.sections[k].name}' is on the carriage: it stays the last section (the moving end), so the "
                "others cannot go below it")
    return ""


def move_section(scene, index: int, delta: int, cover=None) -> str:
    """Move a section one place; returns '' or the reason it cannot move."""
    c = cover or settings(scene)
    reason = move_problem(c, index, delta)
    if reason:
        return reason
    c.sections.move(index, index + delta)
    c.sections_index = index + delta
    refresh(scene)
    return ""


def remove_all(scene, cover=None) -> int:
    """Remove the cover's sections: the couplings and joints it made go, nothing else (the axis and the carriage
    stay). Returns the sections removed."""
    c = cover or settings(scene)
    n = len(c.sections)
    while len(c.sections):
        sec = c.sections[len(c.sections) - 1]
        j = None if sec.carriage else section_joint(scene, sec)
        if j is not None:
            joints.remove(scene, j)
        c.sections.remove(len(c.sections) - 1)
    c.sections_index = 0
    return n


def read_total(scene, cover=None) -> str:
    """Take the total travel from the axis joint's limits. Returns '' or the reason it cannot."""
    c = cover or settings(scene)
    reason = axis_problem(scene, c)
    if reason:
        return reason
    j = axis_joint(scene, c)
    if not j.use_limits:
        return (f"'{j.name}' has no limits. Tick Limits in its joint set-up (4 Motion), or type the "
                "total length of movement")
    total = abs(j.slide_max - j.slide_min)
    if total <= 0:
        return f"The limits of '{j.name}' are equal: set its Min and Max, or type the total length of movement"
    c.total = total
    return ""


def shares(scene, cover=None) -> list[float]:
    c = cover or settings(scene)
    return core.signed(core.shares(len(c.sections), c.housing_counts), c.flip)


def _limits_for(axis, share: float, total: float, drawn: float = 0.0) -> tuple[float, float]:
    """The section's slide limits (m). ``drawn``: the axis value the CAD file shows (task 0090): the section
    is at its CAD place there, so every value is ``share * (axis - drawn)``."""
    lo, hi = (axis.slide_min, axis.slide_max) if axis.use_limits else (0.0, total)
    a, b = share * (lo - drawn), share * (hi - drawn)
    return (min(a, b), max(a, b))


def _apply(scene, c, sec, share: float, axis) -> bool:
    """Make section ``sec``'s joint follow ``axis`` with ``share``; True when something changed."""
    j = section_joint(scene, sec)
    changed = False
    off = -share * c.drawn_at
    cur = j.couple_offset_dist
    if (j.follows != axis.name or abs(j.couple_ratio - share) > 1e-6 or abs(cur - off) > 1e-7):
        joints.set_follows(scene, j, axis.name, ratio=share, offset_value=off)
        changed = True
    lo, hi = _limits_for(axis, share, c.total, c.drawn_at)
    if (not j.use_limits or abs(j.slide_min - lo) > 1e-6 or abs(j.slide_max - hi) > 1e-6):
        joints._set_raw(j, use_limits=True, slide_min=lo, slide_max=hi)
        joints.apply_limits(j, joints._model_size(scene), clamp=False)
        changed = True
    return changed


def read_drawn(scene, cover=None) -> str:
    """Take "Drawn at" from the axis joint's current value (the axis posed where the CAD shows it)."""
    c = cover or settings(scene)
    reason = axis_problem(scene, c)
    if reason:
        return reason
    c.drawn_at = float(joints.get_value(axis_joint(scene, c)))
    return ""


def check_line(scene, cover=None) -> str:
    """A short line for the panel: where the sections stand at axis 0, or why a section would leave its housing."""
    c = cover or settings(scene)
    n = len(c.sections)
    if not n:
        return ""
    sh = shares(scene, c)
    at0 = [-s * c.drawn_at * 1000.0 for s in sh]
    text = " / ".join(f"{v:.0f}" if abs(v) > 0.05 else "0" for v in at0)
    line = f"At 0 mm: section 1 … {n} at {text} mm"
    ax = axis_joint(scene, c) if not axis_problem(scene, c) else None
    lo, hi = ((ax.slide_min, ax.slide_max) if ax is not None and ax.use_limits else (0.0, c.total))
    if c.drawn_at < min(lo, hi) - 1e-6 or c.drawn_at > max(lo, hi) + 1e-6:
        line += f" · Warning: {c.drawn_at * 1000:g} mm is outside the axis limits, so the sections would leave their housing"
    return line


def _refresh_one(scene, c) -> int:
    if not len(c.sections) or axis_problem(scene, c):
        return 0
    axis = axis_joint(scene, c)
    sh = shares(scene, c)
    n = 0
    for i, sec in enumerate(c.sections):
        if sec.carriage:
            continue
        if is_made(scene, sec):
            axis = axis_joint(scene, c)          # (set_follows may grow nothing, but look it up fresh anyway)
            n += 1 if _apply(scene, c, sec, sh[i], axis) else 0
    return n


def refresh(scene) -> int:
    """Give every made section of every cover the share its place in the row, the travel and the direction call
    for. Returns how many joints changed. Safe to call at any time (no axis / nothing made: does nothing)."""
    if _BUSY["on"]:
        return 0
    n = 0
    _BUSY["on"] = True
    try:
        for c in covers(scene):
            n += _refresh_one(scene, c)
        if n:
            joints._update(scene)
    finally:
        _BUSY["on"] = False
    return n


def make(scene, cover=None) -> tuple[int, list[str]]:
    """Build the joints of the sections that have none yet and make every section follow the axis.
    Returns (sections built now, problems)."""
    c = cover or settings(scene)
    reason = axis_problem(scene, c)
    if reason:
        raise RuntimeError(reason)
    if not len(c.sections):
        raise RuntimeError("Add at least one section first: click its parts, then 'Add section'")
    axis = axis_joint(scene, c)
    if c.total <= 0 and not axis.use_limits:
        raise RuntimeError("Set the total length of movement first (or give the axis limits and press "
                           "'Read from the axis')")
    if joints.follow_check(scene, axis, ""):
        raise RuntimeError(joints.follow_check(scene, axis, ""))
    problems, built = [], 0
    base = axis.frame.parent
    frame_world = axis.frame.matrix_world.copy()   # (the joint list grows below: keep no reference into it)
    axis = None
    cname = c.name
    for i in range(len(c.sections)):
        c = _cover_named(scene, cname, c)            # (the scene's lists may grow below)
        sec = c.sections[i]
        if sec.carriage:
            objs = _chosen_parts(scene, sec)
            if not objs:
                problems.append(f"Section '{sec.name}' has no parts (they were removed): add the section again")
            elif i != len(c.sections) - 1:
                problems.append(f"Section '{sec.name}' is on the carriage but not the last one: move it to the end")
            elif not on_carriage(scene, objs, c):
                problems.append(f"Section '{sec.name}': its parts no longer move with the axis '{c.axis}'")
            continue
        if is_made(scene, sec):
            continue
        objs = parts_of(scene, sec)
        if not objs:
            problems.append(f"Section '{sec.name}' has no parts (they were removed): add the section again")
            continue
        reason = check_parts(scene, objs, own=sec, cover=c)
        if reason:
            problems.append(f"Section '{sec.name}': {reason}")
            continue
        prefix = f"Way cover {sec.name}" if len(covers(scene)) < 2 else f"{c.name} {sec.name}"
        try:
            j = joints.create(scene, "SLIDE", objs, None, None, name=prefix, base=base,
                              ref=base, frame_world=frame_world)
        except RuntimeError as exc:
            problems.append(f"Section '{sec.name}': {exc}")
            continue
        c = _cover_named(scene, cname, c)
        sec = c.sections[i]
        sec.joint = j.name
        sec.parts.clear()
        built += 1
    refresh(scene)
    return built, problems


def _cover_named(scene, name: str, fallback):
    for c in covers(scene):
        if c.name == name:
            return c
    return fallback


# ---------------------------------------------------------------------------
# status text and the hooks other modules call
# ---------------------------------------------------------------------------

def state_counts(scene, cover=None) -> tuple[int, int]:
    """(sections, sections built) of one cover; with ``cover`` None and several covers: of all of them."""
    cs = [cover] if cover is not None else covers(scene)
    n = sum(len(c.sections) for c in cs)
    made = sum(1 for c in cs for s in c.sections if is_made(scene, s))
    return n, made


def status(scene, cover=None) -> str:
    """The cover's state: '5 sections · 100 mm each · follows 'Y axis''; '' when there is nothing."""
    c = cover or settings(scene)
    n, made = state_counts(scene, c)
    if not n:
        return ""
    if made < n:
        return f"{n} sections · {n - made} not made yet" if n != 1 else "1 section · not made yet"
    each = core.travel_each(c.total * 1000.0, n, c.housing_counts)
    word = "section" if n == 1 else "sections"
    return f"{n} {word} · {each:g} mm each · follows '{c.axis}'"


def joint_renamed(scene, old: str, new: str) -> None:
    """Hook for ``joints.rename``: the way covers keep following the same joints."""
    for c in covers(scene):
        if c.axis == old:
            c["axis"] = new
        for sec in c.sections:
            if sec.joint == old:
                sec.joint = new


def _carriage_parts_again(scene, sec, mapping, by_uid) -> None:
    """A model update replaced the parts: find the carriage section's parts again by their part IDs."""
    found = []
    for uid in [u for u in sec.uids.split("\n") if u]:
        ob = by_uid.get(uid) if by_uid is not None else None
        if ob is None:
            nu = (mapping or {}).get(uid, uid)
            ob = next((o for o in scene.objects if o.get(build.PROP_UID) == nu), None)
        if ob is not None:
            found.append(ob)
    sec.parts.clear()
    for ob in found:
        sec.parts.add().obj = ob
    sec.uids = "\n".join(ob.get(build.PROP_UID, "") for ob in found)


def after_joints_rebuilt(scene, mapping=None, by_uid=None) -> list[str]:
    """Hook for model updates: sections whose joint came back keep it; the others are told. Shares again.
    ``mapping`` / ``by_uid``: the model update's old part ID -> new part ID / new object (carriage sections)."""
    notes = []
    for c in covers(scene):
        for sec in c.sections:
            if sec.carriage:
                if sec.uids and (mapping is not None or by_uid is not None or not _chosen_parts(scene, sec)):
                    _carriage_parts_again(scene, sec, mapping, by_uid)
                if not _chosen_parts(scene, sec):
                    notes.append(f"Way cover section '{sec.name}' lost its carriage parts in the model update: "
                                 "add them again")
                continue
            if sec.joint and section_joint(scene, sec) is None:
                notes.append(f"Way cover section '{sec.name}' lost its joint in the model update: add its parts "
                             "again")
                sec.joint = ""
        if c.axis and axis_joint(scene, c) is None:
            notes.append(f"Way cover axis '{c.axis}' is gone after the model update: pick the axis again")
    refresh(scene)
    return notes


TEST_MODEL = "test_waycover_c.step"        # a cover each side of the carriage (tools/make_test_waycover.py --both-sides)


def set_up_test_model(scene, carriage: bool = True) -> list:
    """The two-cover test model as the owner would set it up: an X axis of 500 mm on the carriage, 'X left' and
    'X right' with five sections each. ``carriage``: the sections next to the carriage are bolted to it (members of
    the axis) and are each cover's carriage section. Returns the two covers."""
    from mathutils import Vector

    def ob(name):
        return next(o for o in scene.objects if o.get(build.PROP_NAME, "").split(" v")[0] == name)

    members = [ob("CARRIAGE")] + ([ob("COVER.L.5"), ob("COVER.R.5")] if carriage else [])
    j = joints.create(scene, "SLIDE", members, members[0].matrix_world.translation, Vector((1, 0, 0)),
                      name="X axis")
    j.use_limits = True
    j.slide_min, j.slide_max = 0.0, 0.5
    for side, name in (("L", "X left"), ("R", "X right")):
        c = add_cover(scene, name)
        c.axis = "X axis"
        reason = read_total(scene, c)
        if reason:
            raise RuntimeError(reason)
        for k in range(1, 6):
            add_section(scene, [ob(f"COVER.{side}.{k}")], cover=c)
        _built, problems = make(scene, c)
        if problems:
            raise RuntimeError("; ".join(problems))
    return list(scene.fresing.waycovers)


@persistent
def _on_load(_dummy=None):
    """Projects saved with one way cover open with it as the first item of the list."""
    try:
        for sc in bpy.data.scenes:
            if hasattr(sc, "fresing"):
                migrate(sc)
    except Exception:  # noqa: BLE001
        pass


def register():
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
