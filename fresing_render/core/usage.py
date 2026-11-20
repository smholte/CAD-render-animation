"""The usage tracker (task 0181): what this user uses, kept on his own PC only. No Blender here.

One small file in Blender's settings folder (``<config>/fresing_usage.json``, next to the start file of task 0199), so it
belongs to the Windows user and survives updates. **Nothing is ever sent anywhere**: this module and
``blender/usage.py`` import no network library (``tests/test_usage.py`` checks that).

What is kept (everything counted per function id of ``core/functions.py``, so counts survive renamed buttons):

* ``functions`` – {function id: [clicks, last session it was used]}: a click on a function's button. One click counts
  for one function: the one whose panel the button was in, picked further by the button's kind (``BY_PROP``);
* ``buttons`` – {operator id: clicks} (also buttons no function names);
* ``panels`` – {panel class name: [openings, last session]}: a click on a panel's title that opens it;
* ``sessions`` – app starts while tracking was on; ``stages`` – {stage: seconds} of active time (idle time, no input for
  ``IDLE`` seconds, is left out) counted to the stage of the last used function;
* ``saved`` – {function id: seconds} of estimated manual work its uses replaced (``manual_estimate``, never a
  measurement: the window always says "estimate" and how it is worked out);
* the user's choices: ``track``, the favourites bar (``bar``: on, size, pins, the order fixed at this start),
  declutter prompts (``declutter``: on, threshold, the functions asked about), the personal hides (``hidden``).

The favourites bar is **sorted only at the app's start** (``start_session``): buttons that move while you work are worse
than no bar. A declutter prompt asks about one panel at most per session, each panel once, never about a panel whose
functions the open project uses.
"""

from __future__ import annotations

import json
import os
import time

from . import functions as F
from . import learning as L

FILE_NAME = "fresing_usage.json"
MARKER = "fresing_render_usage"
VERSION = 1
IDLE = 120.0                       # seconds without input: idle, not counted
BAR_MIN, BAR_MAX, BAR_DEFAULT = 5, 8, 6
THRESHOLD_DEFAULT = 10             # sessions without a use before a panel is offered for hiding
MIN_CLICKS = 2                     # a function must have been used this often to earn a place on the bar
TEST_ENV = "FRESING_USAGE_TEST"    # real-app tests and the tests of this lane: count although events are simulated
OFF_ENV = "FRESING_NO_USAGE"       # tools that drive the app: count nothing

# The stages of the session heatmap (the owner's Import -> Rigging -> Environment -> Render), from the families.
STAGES = {
    "import": "Import & structure",
    "looks": "Looks",
    "rigging": "Motion & rigging",
    "scene": "Scene & surroundings",
    "animation": "Animation",
    "render": "Render & export",
}
STAGE_OF_FAMILY = {
    "import": "import", "looks": "looks",
    "motion": "rigging", "machines": "rigging", "cnc": "rigging", "milling": "rigging", "offshore": "rigging",
    "scene": "scene", "house": "scene", "lifting": "rigging",
    "animation": "animation", "video": "animation",
    "queue": "render", "web": "render",
}                                  # help and panel: no stage of their own (the time stays with the last one)

# A button that adds different things by its kind: (operator, property) -> {value: function id}.
BY_PROP = {
    ("fresing.block_add", "kind"): {
        "JOINT": "animation.joint_step", "MOTOR": "animation.motor", "GCODE": "cnc.gcode", "FADE_OUT": "animation.fade",
        "FADE_IN": "animation.fade", "SEQUENCE": "animation.sequence", "CAD": "animation.back_to_cad",
        "WEATHER": "animation.weather_step", "VESSEL": "animation.vessel_step"},
    ("fresing.queue_add", "kind"): {"STILL": "queue.still", "ANIMATION": "queue.video", "TEST": "queue.time_test"},
}
# Buttons no function names that still count for one (the section's main button does the function's work).
ALSO = {"fresing.apply_rules": "looks.materials"}
# Buttons that are not a use of anything: opening and folding is counted as a panel opening; the tracker's own buttons
# and the test tour's would count themselves.
NOT_COUNTED = {"fresing.panel_toggle", "fresing.panel_tab", "fresing.usage_go", "fresing.usage_pin",
               "fresing.usage_window", "fresing.usage_set", "fresing.usage_clear", "fresing.usage_reset",
               "fresing.usage_declutter", "fresing.usage_export", "fresing.usage_import", "fresing.usage_folder",
               "fresing.learn_show", "fresing.learn_add", "fresing.learn_add_new", "fresing.learn_done",
               "fresing.learn_remove", "fresing.learn_next", "fresing.learn_window", "fresing.learn_lesson",
               "fresing.learn_lessons", "fresing.learn_start", "fresing.learn_view",       # task 0230: lessons
               "fresing.lesson_next", "fresing.lesson_do", "fresing.lesson_back", "fresing.lesson_more",
               "fresing.lesson_mode", "fresing.lesson_resume", "fresing.lesson_stop"}
# Families never offered for hiding (there would be nothing to work with) and never on the bar (the panel's own
# switches, menu lines).
NEVER_ASK_FAMILIES = ("import", "help", "panel")
NOT_ON_BAR_FAMILIES = ("panel",)


# ---------------------------------------------------------------------------
# the state
# ---------------------------------------------------------------------------

def fresh() -> dict:
    return {MARKER: VERSION, "track": True, "sessions": 0, "first": "", "functions": {}, "buttons": {}, "panels": {},
            "stages": {}, "saved": {},
            "bar": {"on": True, "size": BAR_DEFAULT, "pins": [], "order": []},
            "declutter": {"on": True, "threshold": THRESHOLD_DEFAULT, "asked": [], "session": 0},
            "hidden": [], "learning": L.fresh()}


def _int(v, default=0, lo=0, hi=10 ** 9) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError, OverflowError):
        return default


def _num(v, default=0.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return default
    return x if x == x and abs(x) < 1e12 else default          # no NaN, no infinity


def _ids(v) -> list:
    return [str(x) for x in v if isinstance(x, str)] if isinstance(v, list) else []


def clean(data) -> dict:
    """A state from whatever a file held: wrong types become the defaults, so a hand-edited file never breaks the app."""
    out = fresh()
    if not isinstance(data, dict):
        return out
    out["track"] = bool(data.get("track", True))
    out["sessions"] = _int(data.get("sessions"))
    out["first"] = str(data.get("first") or "")[:10]
    for key in ("functions", "panels"):
        d = data.get(key)
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, list) and len(v) == 2:
                    out[key][str(k)] = [_int(v[0]), _int(v[1])]
    for key, conv in (("buttons", _int), ("stages", _num), ("saved", _num)):
        d = data.get(key)
        if isinstance(d, dict):
            out[key] = {str(k): conv(v) for k, v in d.items()}
    out["stages"] = {k: v for k, v in out["stages"].items() if k in STAGES}
    b = data.get("bar")
    if isinstance(b, dict):
        out["bar"].update(on=bool(b.get("on", True)), size=_int(b.get("size"), BAR_DEFAULT, BAR_MIN, BAR_MAX),
                          pins=_ids(b.get("pins")), order=_ids(b.get("order")))
    d = data.get("declutter")
    if isinstance(d, dict):
        out["declutter"].update(on=bool(d.get("on", True)),
                                threshold=_int(d.get("threshold"), THRESHOLD_DEFAULT, 1, 1000),
                                asked=_ids(d.get("asked")), session=_int(d.get("session")))
    out["hidden"] = _ids(data.get("hidden"))
    out["learning"] = L.clean(data.get("learning"))          # task 0208: an older file has none
    return out


def load(path: str) -> tuple:
    """(state, note). A missing file gives a fresh state; a broken file or one written by a newer version is kept
    beside it as a copy (``.broken`` / ``.newer``) and the app starts with a fresh state – never an error."""
    try:
        with open(path, encoding="utf-8-sig") as fh:
            text = fh.read()
    except FileNotFoundError:
        return fresh(), ""
    except OSError as exc:
        return fresh(), f"could not read {path}: {exc}"
    try:
        data = json.loads(text)
        if not isinstance(data, dict) or MARKER not in data:
            raise ValueError("not a usage file")
    except ValueError:
        return fresh(), _keep_copy(path, ".broken")
    if _int(data.get(MARKER), 0) > VERSION:
        return fresh(), _keep_copy(path, ".newer")
    return clean(data), ""


def _keep_copy(path: str, suffix: str) -> str:
    target = path + suffix
    try:
        os.replace(path, target)
    except OSError as exc:
        return f"could not keep a copy of {path}: {exc}"
    return f"kept a copy of the unreadable usage file as {target}"


def save(path: str, state: dict) -> None:
    """Write the state (a temporary file first: a crash never leaves half a file)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1, sort_keys=True)
    os.replace(tmp, path)


def clear(state: dict, with_list: bool = False) -> dict:
    """"Clear my usage data": counts, times, sessions and the prompts' answers go; the switches, pins and hides stay.
    The learning list stays too unless ``with_list`` (task 0208: the question asks)."""
    out = fresh()
    out["learning"] = L.clear(state, with_list)
    out["track"] = state.get("track", True)
    out["bar"].update(on=state["bar"]["on"], size=state["bar"]["size"], pins=list(state["bar"]["pins"]))
    out["declutter"].update(on=state["declutter"]["on"], threshold=state["declutter"]["threshold"])
    out["hidden"] = list(state.get("hidden", []))
    return out


def reset(state: dict) -> dict:
    """"Back to the workspace as it came": the personal hides and pins go; the counts stay."""
    state["hidden"] = []
    state["bar"]["pins"] = []
    state["bar"]["order"] = bar_order(state)
    return state


# ---------------------------------------------------------------------------
# counting
# ---------------------------------------------------------------------------

def function_for(op: str, panel: str = "", props: dict | None = None, funcs=None) -> str:
    """The one function a click on button ``op`` counts for ('' = none): picked by the button's kind (``BY_PROP``),
    then by the panel it was clicked in, then the first function in the list that names the button."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    if op in ALSO and ALSO[op] in funcs:
        return ALSO[op]
    for (bop, prop), table in BY_PROP.items():
        if bop == op and props and props.get(prop) in table and table[props[prop]] in funcs:
            return table[props[prop]]
    hits = [f for f in funcs.values() if f.button == op]
    if panel:
        here = [f for f in hits if f.panel == panel]
        if here:
            return here[0].id
    return hits[0].id if hits else ""


def stage_of(fid: str, funcs=None) -> str:
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    return STAGE_OF_FAMILY.get(f.family, "") if f is not None else ""


def panel_stage(panel: str, funcs=None) -> str:
    """The stage of a panel: of the first function that names it."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    for f in funcs.values():
        if f.panel == panel:
            return STAGE_OF_FAMILY.get(f.family, "")
    return ""


def count_click(state: dict, op: str, fid: str, saved_seconds: float = 0.0, today: str = "") -> list:
    """One click. Returns the learning-list items this use ticked by themselves (task 0208)."""
    state["buttons"][op] = state["buttons"].get(op, 0) + 1
    if fid:
        n, _last = state["functions"].get(fid, [0, 0])
        state["functions"][fid] = [n + 1, state["sessions"]]
        if saved_seconds > 0:
            state["saved"][fid] = state["saved"].get(fid, 0.0) + float(saved_seconds)
        return L.note_use(state, fid, today)
    return []


def count_panel(state: dict, panel: str) -> None:
    n, _last = state["panels"].get(panel, [0, 0])
    state["panels"][panel] = [n + 1, state["sessions"]]


class Clock:
    """Active time per stage: each sign of input adds the time since the one before, unless that gap was longer than
    ``IDLE`` (then the user was away: nothing is added). ``now`` is passed in so the tests can play time."""

    def __init__(self):
        self.last = None
        self.stage = ""

    def tick(self, state: dict, now: float | None = None, stage: str = "") -> None:
        now = time.monotonic() if now is None else now
        if self.last is not None and self.stage:
            gap = now - self.last
            if 0 < gap <= IDLE:
                state["stages"][self.stage] = state["stages"].get(self.stage, 0.0) + gap
        self.last = now
        if stage:
            self.stage = stage


# ---------------------------------------------------------------------------
# the favourites bar
# ---------------------------------------------------------------------------

def bar_candidates(funcs=None) -> list:
    funcs = F.FUNCTIONS if funcs is None else funcs
    return [f.id for f in funcs.values() if f.button and f.family not in NOT_ON_BAR_FAMILIES]


def ranking(state: dict, funcs=None) -> list:
    """Function ids by use, most used first (ties: the one used last first, then the function list's order)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    order = {fid: i for i, fid in enumerate(funcs)}
    rows = [(fid, v) for fid, v in state["functions"].items() if fid in order and v[0] >= MIN_CLICKS]
    rows.sort(key=lambda r: (-r[1][0], -r[1][1], order[r[0]]))
    return [fid for fid, _v in rows]


def bar_order(state: dict, funcs=None) -> list:
    """The bar's functions as worked out at a start: the pins first (in the order pinned), then the most used, at most
    ``size`` (more only when more are pinned)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    ok = set(bar_candidates(funcs))
    pins = [p for p in state["bar"]["pins"] if p in ok]
    size = max(state["bar"]["size"], len(pins))
    out = list(pins)
    for fid in ranking(state, funcs):
        if len(out) >= size:
            break
        if fid in ok and fid not in out:
            out.append(fid)
    return out


def start_session(state: dict, today: str = "") -> dict:
    """An app start: one more session (while tracking is on) and the bar sorted afresh – the only moment it is."""
    if state["track"]:
        state["sessions"] += 1
        if not state["first"] and today:
            state["first"] = today
    state["bar"]["order"] = bar_order(state)
    return state


def pin(state: dict, fid: str, on: bool) -> None:
    """Pin or unpin. A new pin shows at once (it is added at the end, nothing else moves); unpinning keeps the button
    where it is until the next start."""
    pins = state["bar"]["pins"]
    if on and fid not in pins:
        pins.append(fid)
        if fid not in state["bar"]["order"]:
            state["bar"]["order"].append(fid)
    elif not on and fid in pins:
        pins.remove(fid)


# ---------------------------------------------------------------------------
# declutter prompts
# ---------------------------------------------------------------------------

def panel_functions(panel: str, funcs=None) -> list:
    funcs = F.FUNCTIONS if funcs is None else funcs
    return [f.id for f in funcs.values() if f.panel == panel]


def last_use(state: dict, panel: str, funcs=None, children=None) -> int:
    """The last session the panel (or a function of it, or a panel under it) was used; 0 = never."""
    last = state["panels"].get(panel, [0, 0])[1]
    for fid in panel_functions(panel, funcs):
        last = max(last, state["functions"].get(fid, [0, 0])[1])
    for child in (children or {}).get(panel, ()):
        last = max(last, last_use(state, child, funcs, children))
    return last


def declutter_candidate(state: dict, shown: set, used: set, hidden_panels: set = frozenset(), funcs=None,
                        children=None, titles=None) -> str:
    """The panel to ask about now ('' = none). ``shown``: the function ids the project's workspace shows; ``used``: the
    ids the open project uses; ``children``: {panel: its sub-panels}; ``titles``: the panels the side panel has (others,
    and the seven sections, are never asked about). A panel qualifies when tracking has seen at least ``threshold``
    sessions, it was not used in the last ``threshold`` of them, all its functions show and none is used by the project,
    and it was not asked about before."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    d = state["declutter"]
    if not (state["track"] and (d["on"] or L.part(state)["teach"])):
        return ""
    n = d["threshold"]
    if state["sessions"] < n:
        return ""
    from . import places
    panels: dict = {}
    for f in funcs.values():
        if f.panel in F.MENUS or f.panel in places.SECTIONS:
            continue
        panels.setdefault(f.panel, []).append(f)
    for panel, items in panels.items():
        if titles is not None and panel not in titles:
            continue
        if panel in d["asked"] or panel in hidden_panels:
            continue
        if any(f.family in NEVER_ASK_FAMILIES for f in items):
            continue
        if not all(f.id in shown for f in items) or any(f.id in used for f in items):
            continue
        if any(f.id in state["hidden"] for f in items):
            continue
        last = last_use(state, panel, funcs, children)
        if last and state["sessions"] - last < n:
            continue
        return panel
    return ""


def answer_declutter(state: dict, panel: str, choice: str, funcs=None) -> None:
    """"hide": the panel's functions go into the personal hides; "later": not asked about this panel again;
    "never": no more prompts (switch them back on in My usage); "learn" (task 0208): the panel's function goes on the
    learning list, nothing is hidden."""
    d = state["declutter"]
    if panel and panel not in d["asked"]:
        d["asked"].append(panel)
    d["session"] = state["sessions"]
    if choice == "hide":
        for fid in panel_functions(panel, funcs):
            if fid not in state["hidden"]:
                state["hidden"].append(fid)
    elif choice == "never":
        d["on"] = False
        L.part(state)["teach"] = False
    elif choice == "learn":
        L.add(state, L.target_of_panel(panel, funcs), funcs)


def personal_hides(state: dict, used: set, funcs=None) -> tuple:
    """The personal hides that apply to the open project: never one the project uses."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    return tuple(sorted(h for h in state["hidden"] if h in funcs and h not in used))


# ---------------------------------------------------------------------------
# time saved (an estimate)
# ---------------------------------------------------------------------------

def estimate_seconds(fid: str, parts: int = 0, funcs=None) -> float:
    """Seconds of manual work one use of the function replaces, from its ``manual_estimate`` (0 = none given)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    est = getattr(f, "manual_estimate", ()) if f is not None else ()
    if not est:
        return 0.0
    per, seconds = est[0], float(est[1])
    return seconds * max(1, parts) if per == "part" else seconds


def basis(fid: str, funcs=None) -> str:
    """How the estimate is worked out, in words: "about 5 s per part by hand: pick the part, pick its material"."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    est = getattr(f, "manual_estimate", ()) if f is not None else ()
    if not est:
        return ""
    per, seconds, how = est[0], float(est[1]), est[2]
    return f"about {duration(seconds)} {'per part' if per == 'part' else 'each time'} by hand: {how}"


def duration(seconds: float) -> str:
    """'40 s', '12 min', '3.5 h'."""
    s = max(0.0, float(seconds))
    if s < 90:
        return f"{s:.0f} s"
    if s < 90 * 60:
        return f"{s / 60:.0f} min"
    h = s / 3600
    return f"{h:.1f} h" if h < 10 else f"{h:.0f} h"


def saved_rows(state: dict, funcs=None) -> list:
    """[(function id, seconds, uses)] of the estimated time saved, biggest first."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    rows = [(fid, s, state["functions"].get(fid, [0, 0])[0]) for fid, s in state["saved"].items()
            if fid in funcs and s > 0]
    rows.sort(key=lambda r: -r[1])
    return rows


def stage_rows(state: dict) -> list:
    """[(stage key, title, seconds, share 0..1)] in the order of the work, shares of the biggest."""
    top = max([state["stages"].get(k, 0.0) for k in STAGES] + [0.0])
    return [(k, t, state["stages"].get(k, 0.0), (state["stages"].get(k, 0.0) / top) if top else 0.0)
            for k, t in STAGES.items()]


# ---------------------------------------------------------------------------
# profiles: the own-workspace file with the bar and the hides (and, when ticked, the counts)
# ---------------------------------------------------------------------------

def profile_part(state: dict, with_counts: bool = False) -> dict:
    """What a profile adds to an own-workspace file: {"favourites": …, "usage": … (only when ticked)}."""
    out = {"favourites": {"on": bool(state["bar"]["on"]), "size": state["bar"]["size"],
                          "pins": list(state["bar"]["pins"])}}
    if with_counts:
        out["usage"] = {k: state[k] for k in ("sessions", "functions", "buttons", "panels", "stages", "saved")}
        out["usage"]["learning"] = L.profile_part(state, True)
    return out


def take_profile(state: dict, data: dict, with_counts: bool = False, funcs=None) -> dict:
    """A loaded profile's bar into the state (pins replaced; the order follows at once). Its counts are added only when
    ``with_counts`` (a team's profile should not change what you use)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    fav = data.get("favourites") if isinstance(data, dict) else None
    if isinstance(fav, dict):
        state["bar"]["on"] = bool(fav.get("on", True))
        state["bar"]["size"] = _int(fav.get("size"), BAR_DEFAULT, BAR_MIN, BAR_MAX)
        state["bar"]["pins"] = [p for p in _ids(fav.get("pins")) if p in funcs]
    u = data.get("usage") if isinstance(data, dict) else None
    if with_counts and isinstance(u, dict):
        other = clean(dict(u, **{MARKER: VERSION}))
        state["sessions"] = max(state["sessions"], other["sessions"])
        for key in ("functions", "panels"):
            for k, (n, last) in other[key].items():
                mine = state[key].get(k, [0, 0])
                state[key][k] = [mine[0] + n, max(mine[1], min(last, state["sessions"]))]
        for key in ("buttons", "stages", "saved"):
            for k, v in other[key].items():
                state[key][k] = state[key].get(k, 0) + v
        if isinstance(u.get("learning"), dict):
            mine = L.part(state)
            other_l = L.clean(u["learning"])
            for item in other_l["list"]:
                if L.find(state, item["id"]) is None and item["id"] in funcs:
                    mine["list"].append(item)
            for k, v in other_l["days"].items():
                mine["days"][k] = sorted(set(mine["days"].get(k, [])) | set(v))[-L.DAYS_KEPT:]
    state["bar"]["order"] = bar_order(state, funcs)
    return state
