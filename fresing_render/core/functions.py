"""One list of the app's functions (task 0123 study – PROTOTYPE on branch task/0123-learning-study, not on main).

Every function the owner can see is ONE entry here. The others read it instead of keeping their own lists:

* the side panel sets of task 0062 (``family``),
* the lessons (``panel`` / ``fold`` / ``button`` / ``prop``: where the lesson points; ``lesson``: the step that teaches it),
* the user guide (``guide``: the anchor ``<a id="...">`` in docs/USER-GUIDE.md),
* the test tour (``tour``: the stop ids) and the PC check (``pccheck``: line ids),
* the website (``media.json`` names function ids: ``"functions": ["joints.rotate", ...]`` → a guide link each).

No Blender here: the precheck and the website build read it with plain Python.

This prototype holds the entries the crane lesson needs; the build task fills in the rest (about 120).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 0062's function families: the panel sets a project can show ("show only what this project needs").
FAMILIES = {
    "import": "Import & structure",
    "looks": "Looks",
    "motion": "Motion",
    "machines": "Machine motion (cylinders, mechanisms, way covers, tracks)",
    "cnc": "CNC machine",
    "milling": "Milling",
    "offshore": "Cables, drums & sea",
    "scene": "Scene & render",
    "animation": "Animation & video",
    "queue": "Render queue",
    "web": "Web 3D model",
    "house": "Houses",
}


@dataclass(frozen=True)
class Function:
    id: str                  # "joints.rotate": area.name, never changes (the website and lessons keep it)
    title: str               # what the owner calls it
    family: str              # one key of FAMILIES
    panel: str               # bl_idname of the side panel it lives in
    fold: str = ""           # the fold (ui.fold idname) inside that panel, "" = the panel body
    button: str = ""         # the operator a lesson points at ...
    text: str = ""           # ... and its button text when that operator is drawn more than once in the panel
    prop: str = ""           # or the property ("background")
    guide: str = ""          # docs/USER-GUIDE.md anchor
    tour: tuple = ()         # test-tour stop ids that show it
    pccheck: tuple = ()      # PC-check line ids that test it
    lesson: str = ""         # "crane:2" = lesson crane, its step 2
    since: str = ""          # the version it came in


FUNCTIONS: dict[str, Function] = {}


def fn(**kw) -> Function:
    f = Function(**kw)
    FUNCTIONS[f.id] = f
    return f


# ----- the entries the crane lesson uses (prototype) -----
fn(id="import.step", title="Import a STEP file", family="import", panel="FRESING_PT_import",
   button="fresing.import_step", guide="import", pccheck=("import.crane",), lesson="crane:1", since="0.1.0")
fn(id="looks.light_look", title="Light look", family="scene", panel="FRESING_PT_scene",
   button="fresing.light_look", text="Product studio", guide="light-look", tour=("looks",), pccheck=("scene.looks",),
   lesson="crane:2", since="0.2.17")
fn(id="joints.rotate", title="Rotate joint", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_pick_axis", text="Add rotate joint", guide="motion", tour=("joint",),
   pccheck=("joints.rotate",), lesson="crane:3", since="0.2.10")
fn(id="joints.stack", title="Joint on a joint (stacked)", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_pick_axis", text="Add slide joint", guide="motion", tour=("stack",),
   pccheck=("joints.stack",), lesson="crane:4", since="0.2.10")
fn(id="scene.camera", title="Camera view", family="scene", panel="FRESING_PT_camera",
   button="fresing.camera_add", text="3/4 hero, high", guide="camera", tour=("blur",), pccheck=("scene.views",), lesson="crane:5",
   since="0.2.12")
fn(id="scene.save", title="Saved scene", family="scene", panel="FRESING_PT_shots",
   button="fresing.shot_save", guide="saved-scenes", tour=("still",), pccheck=("states.poses",), lesson="crane:6",
   since="0.2.12")
fn(id="animation.add", title="Animation", family="animation", panel="FRESING_PT_animation",
   button="fresing.anim_add", guide="animation", tour=("joint",), lesson="crane:7", since="0.2.10")
fn(id="animation.joint_step", title="Joint step", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="animation", tour=("joint",), lesson="crane:8", since="0.2.10")
fn(id="animation.build", title="Build & play", family="animation", panel="FRESING_PT_animation",
   button="fresing.anim_build", guide="animation", tour=("joint",), lesson="crane:9", since="0.2.10")
fn(id="poses.explode", title="Exploded view", family="motion", panel="FRESING_PT_poses",
   button="fresing.explode", guide="poses", tour=("explode",), pccheck=("states.poses",), lesson="crane:10",
   since="0.2.18")
fn(id="queue.still", title="Render queue: a picture", family="queue", panel="FRESING_PT_queue",
   button="fresing.queue_add", guide="queue", tour=("queue",), pccheck=("queue.frame_shown",), lesson="crane:11",
   since="0.2.12")


# ---------------------------------------------------------------------------
# keeping the lists in step (the precheck runs this; no Blender)
# ---------------------------------------------------------------------------

ID = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+\Z")


def guide_anchors(text: str) -> set:
    """The anchors of docs/USER-GUIDE.md (``<a id="..."></a>`` lines)."""
    return set(re.findall(r'<a id="([a-z0-9-]+)"></a>', text))


def problems(functions=None, anchors=None, stops=None, lessons=None, lines=None) -> list:
    """Plain sentences, one per thing out of step; [] = all fine.

    anchors: the guide's anchors; stops: the tour's stop ids; lessons: {"crane": number of steps}; lines: PC-check ids.
    Any argument left None is not checked (the prototype's test passes what it has)."""
    out = []
    for f in (functions or FUNCTIONS).values():
        if not ID.match(f.id):
            out.append(f"{f.id}: an id is area.name in small letters")
        if f.family not in FAMILIES:
            out.append(f"{f.id}: family '{f.family}' is not one of {sorted(FAMILIES)}")
        if not (f.button or f.prop):
            out.append(f"{f.id}: no button or setting for a lesson to point at")
        if anchors is not None and f.guide not in anchors:
            out.append(f"{f.id}: the guide has no anchor '{f.guide}' (add <a id=\"{f.guide}\"></a> above its section)")
        if stops is not None:
            for t in f.tour:
                if t not in stops:
                    out.append(f"{f.id}: no tour stop '{t}'")
        if lines is not None:
            for p in f.pccheck:
                if p not in lines:
                    out.append(f"{f.id}: no PC-check line '{p}'")
        if lessons is not None:
            name, _, k = f.lesson.partition(":")
            if not f.lesson:
                out.append(f"{f.id}: no lesson teaches it (a step in a lesson of its test model)")
            elif name not in lessons or not k.isdigit() or not 1 <= int(k) <= lessons[name]:
                out.append(f"{f.id}: lesson step '{f.lesson}' does not exist")
    return out


def guide_link(fid: str, base: str = "guide/") -> str:
    """The website's link for a function id in media.json (``functions: [...]``)."""
    f = FUNCTIONS[fid]
    return f"{base}#{f.guide}"
