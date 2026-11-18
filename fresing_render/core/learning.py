"""Learn as you go (task 0208): a function a user never uses may be one he does not know, not one he does not want.

The rules of the personal learning list and the one quiet "next to learn", kept in the usage file of task 0181 under
``learning`` (``core/usage.py`` holds the file; this module only works on that part of its state). No Blender, and no
network library: nothing here can send anything (``tests/test_learning.py`` checks that).

What is kept:

* ``list`` – the learning list, in the order it was filled: ``{"id": function id, "added": session, "done": bool,
  "auto": bool}`` (``auto``: ticked by itself because the function was used on ``need_days`` different days);
* ``days`` – {function id: [the last ``DAYS_KEPT`` dates it was used on]} (only dates, never a time of day);
* ``declined`` – function ids the user said "Not interested" to; ``told`` – ids learned by themselves that the list has
  not yet said so about (it says so once);
* ``teach`` – the declutter question also offers to teach; ``need_days`` – days of use that count as learned;
  ``next_on`` – the quiet suggestion is on; ``next`` – {"session": the session it was chosen in, "id": it}.
"""

from __future__ import annotations

from . import functions as F

DAYS_DEFAULT = 3
DAYS_KEPT = 30
NEVER_TEACH_FAMILIES = ("help", "panel")      # menus and the side panel's own switches: nothing to learn by a tour


def fresh() -> dict:
    return {"list": [], "days": {}, "declined": [], "told": [], "teach": True, "need_days": DAYS_DEFAULT,
            "next_on": True, "next": {"session": 0, "id": ""}}


def _int(v, default, lo, hi) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError, OverflowError):
        return default


def _ids(v) -> list:
    return [str(x) for x in v if isinstance(x, str)] if isinstance(v, list) else []


def clean(data) -> dict:
    """A learning part from whatever a file held (an older file has none: all defaults)."""
    out = fresh()
    if not isinstance(data, dict):
        return out
    seen = set()
    for item in data.get("list") if isinstance(data.get("list"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in seen:
            seen.add(item["id"])
            out["list"].append({"id": item["id"], "added": _int(item.get("added"), 0, 0, 10 ** 9),
                                "done": bool(item.get("done")), "auto": bool(item.get("auto"))})
    days = data.get("days")
    if isinstance(days, dict):
        for k, v in days.items():
            got = sorted({d[:10] for d in _ids(v) if len(d) >= 10})[-DAYS_KEPT:]
            if got:
                out["days"][str(k)] = got
    out["declined"] = _ids(data.get("declined"))
    out["told"] = _ids(data.get("told"))
    out["teach"] = bool(data.get("teach", True))
    out["next_on"] = bool(data.get("next_on", True))
    out["need_days"] = _int(data.get("need_days"), DAYS_DEFAULT, 1, 365)
    n = data.get("next")
    if isinstance(n, dict):
        out["next"] = {"session": _int(n.get("session"), 0, 0, 10 ** 9), "id": str(n.get("id") or "")}
    return out


def part(state: dict) -> dict:
    """The state's learning part (made when an older state has none)."""
    if "learning" not in state:
        state["learning"] = fresh()
    return state["learning"]


# ---------------------------------------------------------------------------
# what can be taught
# ---------------------------------------------------------------------------

def teachable(fid: str, funcs=None) -> bool:
    """A function the user can be shown: it has a guide section or a test-tour stop and is not a menu line or the
    side panel's own switch."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    return bool(f is not None and f.family not in NEVER_TEACH_FAMILIES and (f.guide or f.tour))


def target_of_panel(panel: str, funcs=None) -> str:
    """The function a question about a panel teaches: the first function of the panel that has a button or a setting
    and can be taught ('' = none)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    items = [f for f in funcs.values() if f.panel == panel and teachable(f.id, funcs)]
    items.sort(key=lambda f: (not (f.button or f.prop), not f.tour))
    return items[0].id if items else ""


def options(fid: str, funcs=None) -> dict:
    """What the question can offer for a function: {"guide": anchor or "", "tour": first stop id or "",
    "why_no_tour": the reason the tour button is greyed}."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    if f is None:
        return {"guide": "", "tour": "", "why_no_tour": "There is no such function"}
    return {"guide": f.guide, "tour": f.tour[0] if f.tour else "",
            "why_no_tour": "" if f.tour else "The test tour has no stop for this function yet: use the guide"}


def one_line(fid: str, funcs=None) -> str:
    """What the function does, in a few words (its title in the function list)."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    return f.title if f is not None else fid


# ---------------------------------------------------------------------------
# the list
# ---------------------------------------------------------------------------

def find(state: dict, fid: str):
    for item in part(state)["list"]:
        if item["id"] == fid:
            return item
    return None


def add(state: dict, fid: str, funcs=None) -> bool:
    """Put a function on the list (False: unknown, not teachable or there already). A function the user turned down
    comes back when he asks for it himself."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    p = part(state)
    if fid not in funcs or find(state, fid) is not None:
        return False
    p["list"].append({"id": fid, "added": state.get("sessions", 0), "done": False, "auto": False})
    if fid in p["declined"]:
        p["declined"].remove(fid)
    if state.get("functions", {}).get(fid, [0, 0])[0] and len(p["days"].get(fid, ())) >= p["need_days"]:
        _learned(p, find(state, fid))
    return True


def add_many(state: dict, fids, funcs=None) -> int:
    return sum(1 for fid in fids if add(state, fid, funcs))


def remove(state: dict, fid: str) -> bool:
    p = part(state)
    n = len(p["list"])
    p["list"] = [i for i in p["list"] if i["id"] != fid]
    return len(p["list"]) != n


def set_done(state: dict, fid: str, done: bool = True) -> None:
    item = find(state, fid)
    if item is not None:
        item["done"], item["auto"] = bool(done), False


def open_items(state: dict) -> list:
    return [i["id"] for i in part(state)["list"] if not i["done"]]


def _learned(p: dict, item: dict) -> None:
    item["done"], item["auto"] = True, True
    if item["id"] not in p["told"]:
        p["told"].append(item["id"])


def note_use(state: dict, fid: str, today: str) -> list:
    """One use of a function on ``today`` (an ISO date): remembered by day; an item on the list used on ``need_days``
    different days is ticked by itself. Returns the ids ticked by this use."""
    if not fid or not today:
        return []
    p = part(state)
    days = p["days"].setdefault(fid, [])
    if today[:10] not in days:
        days.append(today[:10])
        days.sort()
        del days[:-DAYS_KEPT]
    item = find(state, fid)
    if item is not None and not item["done"] and len(days) >= p["need_days"]:
        _learned(p, item)
        return [fid]
    return []


def take_told(state: dict) -> list:
    """The ids learned by themselves that the list has not said so about yet; the list says it once."""
    p = part(state)
    out, p["told"] = list(p["told"]), []
    return out


def say_learned(fid: str, funcs=None) -> str:
    return f"You've got the hang of {one_line(fid, funcs)}"


def new_since(since: str, funcs=None) -> list:
    """Function ids that are teachable and came (or were improved) after version ``since`` – What's new's "Add the new
    functions to my learning list"."""
    funcs = F.FUNCTIONS if funcs is None else funcs

    def key(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return ()
    ref = key(since)
    out = []
    for f in funcs.values():
        if not teachable(f.id, funcs):
            continue
        v = key(f.changed or f.since)
        if v and ref and v > ref:
            out.append(f.id)
    return out


# ---------------------------------------------------------------------------
# next to learn
# ---------------------------------------------------------------------------

def decline(state: dict, fid: str) -> None:
    p = part(state)
    if fid and fid not in p["declined"]:
        p["declined"].append(fid)
    if p["next"]["id"] == fid:
        p["next"]["id"] = ""


def candidates(state: dict, shown, used, hidden_panels=frozenset(), funcs=None) -> list:
    """[(function id, family)] the quiet suggestion may pick from, in the order it would pick: functions of the
    families the user works in (most used first), in the function list's order, that he never used, that this
    workspace shows, the open project does not use, he did not hide, turn down or already list."""
    funcs = F.FUNCTIONS if funcs is None else funcs
    p = part(state)
    uses: dict = {}
    for fid, v in state.get("functions", {}).items():
        f = funcs.get(fid)
        if f is not None and v and v[0] > 0 and f.family not in NEVER_TEACH_FAMILIES:
            uses[f.family] = uses.get(f.family, 0) + v[0]
    out = []
    for fam in sorted(uses, key=lambda k: -uses[k]):
        for f in funcs.values():
            if f.family != fam or f.panel in F.MENUS or not teachable(f.id, funcs):
                continue
            if f.id not in shown or f.id in used or f.panel in hidden_panels:
                continue
            if state.get("functions", {}).get(f.id, [0, 0])[0] or f.id in state.get("hidden", ()):
                continue
            if f.id in p["declined"] or find(state, f.id) is not None:
                continue
            out.append((f.id, fam))
    return out


def why(fid: str, funcs=None) -> str:
    funcs = F.FUNCTIONS if funcs is None else funcs
    f = funcs.get(fid)
    fam = F.FAMILIES.get(f.family, f.family) if f is not None else ""
    return f"you work with {fam}, and have not tried this yet"


def choose_next(state: dict, shown, used, hidden_panels=frozenset(), funcs=None) -> str:
    """The one suggestion of this session ('' = none): chosen once per session, then kept for it; never one that was
    answered since."""
    p = part(state)
    if not (state.get("track", True) and p["next_on"]):
        return ""
    sess = state.get("sessions", 0)
    n = p["next"]
    if n["session"] == sess and sess:
        keep = n["id"]
        if keep and keep not in p["declined"] and find(state, keep) is None and keep not in used:
            return keep
        return ""
    n["session"] = sess
    cands = candidates(state, shown, used, hidden_panels, funcs)
    n["id"] = cands[0][0] if cands else ""
    return n["id"]


def answer_next(state: dict, fid: str, choice: str, funcs=None) -> None:
    """"learn": on the list (the quiet card goes); "no": turned down for good."""
    if choice == "learn":
        add(state, fid, funcs)
    else:
        decline(state, fid)
    part(state)["next"]["id"] = ""


def clear(state: dict, with_list: bool) -> dict:
    """"Clear my usage data" keeps the list unless asked: day counts go (they are usage), the settings stay."""
    p = part(state)
    keep = fresh()
    keep.update(teach=p["teach"], need_days=p["need_days"], next_on=p["next_on"])
    if with_list:
        return keep
    keep["list"] = [dict(i, auto=False) for i in p["list"]]
    keep["declined"] = list(p["declined"])
    return keep


def profile_part(state: dict, with_counts: bool) -> dict:
    """What an exported profile holds: the list and the settings only when the usage counts are included."""
    if not with_counts:
        return {}
    p = part(state)
    return {"list": [dict(i) for i in p["list"]], "days": {k: list(v) for k, v in p["days"].items()},
            "declined": list(p["declined"]), "teach": p["teach"], "need_days": p["need_days"],
            "next_on": p["next_on"]}
