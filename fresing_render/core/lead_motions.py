"""Lead motions (task 0309): one slider per machine function, no Blender.

A **lead motion** ("Boom up", "Outriggers", "Table X travel") moves several joints from one slider, 0 … 100 %. Each of
its **rows** names a joint and says

* its value at 0 % and at 100 % (the joint's own units inside the app: radians for a rotate joint, metres for a slide),
* the **window** of the slider in which it moves (starts at %, ends at %): outside the window it stands at its start or
  end value, so one slider can do things in order (outriggers out over 0–40 %, then the boom up over 30–100 %),
* its **easing** inside that window (smooth, constant speed, slow start, slow stop – the same four as an animation step).

Everything here is plain numbers so the web page (task 0310) can play the same thing: ``to_data`` gives per lead motion
per joint the values at the slider positions, nothing that needs Blender to work out.

Rules (written down in the guide's "Lead motions"):

* **Two lead motions on one joint:** a joint may sit in several lead motions. The last one moved wins: moving a slider
  sets its joints, the other lead motion's slider stays where it was and the menu says "moved by …" next to it
  (``moved_by``).
* **Stages** ("Order the joints"): rows get a stage number 1, 2, 3 …; ``stage_windows`` gives stage k of n the window
  (k−1)/n … k/n of the slider, widened by an overlap so the stages flow into each other.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

EASINGS = ("SMOOTH", "LINEAR", "EASE_IN", "EASE_OUT")
SAME = 1e-6                   # rad or m: a joint "did not move" (a pose or a recording that differs by less)
SECONDS = 4.0                 # a play-through, when the lead motion names none


def ease(kind: str, p: float) -> float:
    """The share 0 … 1 of a move at progress p (0 … 1), as animation steps ease (``animation.ease``)."""
    p = min(max(p, 0.0), 1.0)
    if kind == "LINEAR":
        return p
    if kind == "EASE_IN":
        return 1.0 - math.cos(p * math.pi / 2)
    if kind == "EASE_OUT":
        return math.sin(p * math.pi / 2)
    return 0.5 - 0.5 * math.cos(math.pi * p)


@dataclass
class Row:
    joint: str
    v0: float                 # the joint's value at the window's start (rad / m)
    v1: float                 # … at its end
    start: float = 0.0        # the slider position (%) where this joint starts to move
    end: float = 100.0        # … where it has arrived
    easing: str = "SMOOTH"
    stage: int = 1


@dataclass
class LeadMotion:
    name: str
    rows: list = field(default_factory=list)
    seconds: float = SECONDS
    description: str = ""


def window(row: Row) -> tuple[float, float]:
    """The row's window in %, in order and inside 0 … 100."""
    a = min(max(float(row.start), 0.0), 100.0)
    b = min(max(float(row.end), 0.0), 100.0)
    return (a, b) if a <= b else (b, a)


def share(row: Row, pct: float) -> float:
    """How far the row's joint is between its 0 % and 100 % values (0 … 1) when the slider stands at ``pct``."""
    a, b = window(row)
    pct = min(max(float(pct), 0.0), 100.0)
    if b - a < 1e-9:                                   # a window of no width: a jump at that point
        return 1.0 if pct >= b else 0.0
    return ease(row.easing, (pct - a) / (b - a))


def value(row: Row, pct: float) -> float:
    """The joint's value (rad / m) at slider position ``pct`` (%)."""
    s = share(row, pct)
    return row.v0 + (row.v1 - row.v0) * s


def values(lm, pct: float) -> dict:
    """{joint: value} at slider position ``pct``. A joint named on two rows (two windows of one lead motion, e.g. out
    and back again) takes the row whose window started last before ``pct`` – the row further along wins."""
    out: dict = {}
    rows = sorted(_rows(lm), key=lambda r: window(r)[0])
    for r in rows:
        if r.joint in out and window(r)[0] > pct + 1e-9:
            continue                                   # a later window that has not started: the earlier row holds
        out[r.joint] = value(r, pct)
    return out


def _rows(lm):
    return lm.rows if hasattr(lm, "rows") else lm


def joints_of(lm) -> list:
    """The joint names a lead motion moves, in row order, each once."""
    seen: list = []
    for r in _rows(lm):
        if r.joint not in seen:
            seen.append(r.joint)
    return seen


def position_of(lm, current: dict, tol: float = 1e-5) -> float | None:
    """The slider position at which every joint of ``lm`` has the value in ``current`` ({joint: value}), or None when
    no position fits (another lead motion or a hand moved one of them since). Tried at 0.1 % steps, then refined."""
    names = [n for n in joints_of(lm) if n in current]
    if not names:
        return None

    def err(p):
        v = values(lm, p)
        return max(abs(v[n] - current[n]) for n in names)

    best = min((i / 10.0 for i in range(1001)), key=err)
    lo, hi = max(0.0, best - 0.1), min(100.0, best + 0.1)
    for _ in range(40):                                # golden-free refinement: a few bisections of the error
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if err(m1) <= err(m2):
            hi = m2
        else:
            lo = m1
    p = (lo + hi) / 2
    scale = max([1.0] + [abs(r.v1 - r.v0) for r in _rows(lm)])
    return p if err(p) <= tol * scale else None


def moved_by(lm_name: str, joint_names, last_moved: list) -> str:
    """The lead motion that moved one of these joints after ``lm_name`` (the newest first in ``last_moved``, a list of
    (lead motion name, its joints)), or ''."""
    mine = set(joint_names)
    for name, js in last_moved:
        if name == lm_name:
            return ""
        if mine & set(js):
            return name
    return ""


# ---------------------------------------------------------------------------
# making rows
# ---------------------------------------------------------------------------

def rows_between(start: dict, end: dict, order=None, tol: float = SAME) -> list:
    """Rows for every joint whose value differs between two states ({joint: value}): from two poses, or from a
    recording (Set start … Set end). ``order``: joint names in the order the rows should come (the joint list)."""
    names = [n for n in (order or sorted(set(start) | set(end))) if n in start or n in end]
    rows = []
    for n in names:
        a, b = float(start.get(n, 0.0)), float(end.get(n, 0.0))
        if abs(a - b) > tol:
            rows.append(Row(n, a, b))
    return rows


def stage_windows(stages, overlap: float = 10.0) -> list:
    """The windows (start %, end %) for rows in these stages (1, 2, 3 …; the numbers need not follow each other): the
    stages share the slider in order, each one ``overlap`` % into its neighbours so the motion flows on."""
    order = sorted(set(int(s) for s in stages))
    n = len(order)
    if n == 0:
        return []
    width = 100.0 / n
    out = []
    for s in stages:
        k = order.index(int(s))
        a = max(0.0, k * width - (overlap / 2 if k > 0 else 0.0))
        b = min(100.0, (k + 1) * width + (overlap / 2 if k < n - 1 else 0.0))
        out.append((round(a, 3), round(b, 3)))
    return out


# ---------------------------------------------------------------------------
# playing and animating
# ---------------------------------------------------------------------------

def play_target(position: float) -> float:
    """▶ plays to 100 %; at (or near) 100 % it plays back to 0 %."""
    return 0.0 if position >= 99.95 else 100.0


def play_position(p_from: float, p_to: float, seconds: float, t: float, easing: str = "LINEAR") -> float:
    """The slider position ``t`` seconds into a play-through from ``p_from`` to ``p_to`` over ``seconds`` (the full
    0 → 100 % takes ``seconds``; a shorter way less)."""
    span = abs(p_to - p_from) / 100.0 * max(1e-6, seconds)
    if span <= 1e-9:
        return p_to
    return p_from + (p_to - p_from) * ease(easing, t / span)


def step_position(p_from: float, p_to: float, easing: str, progress: float) -> float:
    """The slider position of a Lead motion step at progress 0 … 1 of its time."""
    return p_from + (p_to - p_from) * ease(easing, progress)


def step_values(lm, p_from: float, p_to: float, easing: str, progress: float) -> dict:
    """{joint: value} of a Lead motion step at progress 0 … 1: the same values the slider gives at that position."""
    return values(lm, step_position(p_from, p_to, easing, progress))


def show_every_function(names_and_seconds, start: float = 0.0, gap: float = 0.5) -> list:
    """The steps of "Show every function": each lead motion out (0 → 100 %) and back (100 → 0 %), one after another.
    Returns (name, from %, to %, start s, seconds)."""
    t = float(start)
    out = []
    for name, seconds in names_and_seconds:
        sec = max(0.1, float(seconds) or SECONDS)
        out.append((name, 0.0, 100.0, round(t, 3), sec))
        t += sec
        out.append((name, 100.0, 0.0, round(t, 3), sec))
        t += sec + gap
    return out


def samples(lm, n: int = 21) -> dict:
    """{joint: [value at 0 %, …, at 100 %]} at n even positions (the web page's clip, task 0310)."""
    n = max(2, int(n))
    out: dict = {j: [] for j in joints_of(lm)}
    for i in range(n):
        v = values(lm, 100.0 * i / (n - 1))
        for j in out:
            out[j].append(v[j])
    return out


def to_data(lm) -> dict:
    """A lead motion as plain data (saved next to a web export, task 0310)."""
    return {"name": lm.name, "seconds": float(lm.seconds), "description": getattr(lm, "description", ""),
            "rows": [{"joint": r.joint, "v0": r.v0, "v1": r.v1, "start": r.start, "end": r.end, "easing": r.easing,
                      "stage": int(r.stage)} for r in _rows(lm)]}


def from_data(d: dict) -> LeadMotion:
    rows = [Row(str(r["joint"]), float(r["v0"]), float(r["v1"]), float(r.get("start", 0.0)),
                float(r.get("end", 100.0)), str(r.get("easing", "SMOOTH")), int(r.get("stage", 1)))
            for r in d.get("rows", ())]
    return LeadMotion(str(d.get("name", "")), rows, float(d.get("seconds", SECONDS)), str(d.get("description", "")))


def end_labels(rows, unit_of) -> tuple[str, str]:
    """The slider's two end labels: the joint's own values when the lead motion moves one joint ("0°" … "35°"),
    else "0 %" / "100 %". ``unit_of(joint, value)`` writes a value in the joint's unit."""
    js = joints_of(rows)
    if len(js) == 1:
        r = [x for x in _rows(rows) if x.joint == js[0]]
        return unit_of(js[0], r[0].v0), unit_of(js[0], r[-1].v1)
    return "0 %", "100 %"
