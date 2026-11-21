"""Learn as you go in the app (task 0208): what the question, the list and the quiet suggestion need from Blender.

``core/learning.py`` holds the rules and the part of 0181's usage file they live in. Here: the guide and the test tour
for a function, the function behind a right-clicked button, the suggestion of this session, the lines the list says once.
Nothing here reaches the network by itself: the guide is a file of the install; only when that is missing the guide's page
on GitHub is opened in the user's own browser.
"""

from __future__ import annotations

import os

import bpy

from ..core import functions as F
from ..core import learning as core
from . import usage

GUIDE_URL = "https://github.com/smholte/CAD-render-animation/blob/main/docs/USER-GUIDE.md"
_PEND = {"fid": ""}                      # a function to point at once its test-tour stop is set up


def state() -> dict:
    return core.part(usage.state())


def save() -> None:
    usage.changed()
    usage.save()


# ---------------------------------------------------------------------------
# the guide and the test tour
# ---------------------------------------------------------------------------

def open_guide(anchor: str) -> str:
    """Open the user guide at a section: the copy in the install when there is one, else the guide's page on GitHub
    (in the user's browser). Returns "file", "web" or "" (nothing to open)."""
    if not anchor:
        return ""
    from . import welcome
    if os.path.isfile(welcome.guide_file()):
        from . import files
        files.open_path(welcome.guide_link_file(anchor))
        return "file"
    try:
        bpy.ops.wm.url_open(url=f"{GUIDE_URL}#{anchor}")
    except Exception:  # noqa: BLE001
        return ""
    return "web"


def tour_state(scene) -> str:
    """"here" (a test tour project is open), "ready" (a tour of this version is made) or "none"."""
    from . import tour
    if tour.is_tour(scene):
        return "here"
    from . import ops_tour
    try:
        if tour.ready_path(tour.default_folder(), ops_tour._version()):
            return "ready"
    except Exception:  # noqa: BLE001
        pass
    return "none"


def show_in_tour(context, fid: str) -> str:
    """Show a function in the test tour: Go at the first of its stops, the button pointed at. Returns a sentence when it
    could not ("" = it works)."""
    from . import ops_tour, tour
    f = F.FUNCTIONS.get(fid)
    opts = core.options(fid)
    if f is None or not opts["tour"] or tour.find(opts["tour"]) is None:
        return opts["why_no_tour"] or "The Learning hub has no stop for this function"
    mode = tour_state(context.scene)
    if mode == "none":
        return "Make the Learning hub first: Fresing > Open the Learning hub"
    _PEND["fid"] = fid
    if mode == "here":
        _go(opts["tour"])
        after_go()
        return ""
    path = tour.ready_path(tour.default_folder(), ops_tour._version())
    ops_tour._PENDING["stop"] = opts["tour"]
    bpy.ops.wm.open_mainfile(filepath=path)
    return ""


def _go(stop: str) -> None:
    bpy.ops.fresing.tour_go("EXEC_DEFAULT", True, stop=stop)


def after_go() -> None:
    """The stop is set up: point at the function's button (the lesson highlight)."""
    fid, _PEND["fid"] = _PEND["fid"], ""
    if fid in F.FUNCTIONS:
        try:
            from . import highlight
            highlight.point_function(fid, open_panels=True)
        except Exception as exc:  # noqa: BLE001 - the stop is shown; only the pointer failed
            print("Fresing Render (learning): no pointer:", exc)


# ---------------------------------------------------------------------------
# the question, the right-click, the suggestion
# ---------------------------------------------------------------------------

def question(panel: str) -> dict:
    """What the declutter question offers for a panel: {"fid", "line", "guide", "tour", "why_no_tour", "can_hide"}."""
    s = usage.state()
    fid = core.target_of_panel(panel) if state()["teach"] else ""
    out = {"fid": fid, "line": core.one_line(fid) if fid else "", "can_hide": bool(s["declutter"]["on"])}
    out.update(core.options(fid) if fid else {"guide": "", "tour": "", "why_no_tour": ""})
    return out


def function_of_button(op_idname: str = "", prop: str = "") -> str:
    """The function a right-clicked button belongs to ('' = none)."""
    from ..core import usage as ucore
    if op_idname:
        fid = ucore.function_for(op_idname)
        if fid:
            return fid
    if prop:
        for f in F.FUNCTIONS.values():
            if f.prop == prop:
                return f.id
    return ""


def idname_of(class_name: str) -> str:
    """'FRESING_OT_sort_parts' -> 'fresing.sort_parts'."""
    head, sep, tail = class_name.partition("_OT_")
    return f"{head.lower()}.{tail}" if sep else ""


def suggestion(scene) -> str:
    """The quiet "next to learn" of this session ('' = none)."""
    if scene is None or getattr(scene, "fresing", None) is None or not usage.counting():
        return ""
    from . import workspaces
    shown = workspaces._state(scene)[1]
    if shown is None:
        return ""
    hidden = workspaces._state(scene)[0]
    return core.choose_next(usage.state(), set(shown), set(workspaces.used_functions(scene)), set(hidden))


def forget() -> None:
    _PEND["fid"] = ""
