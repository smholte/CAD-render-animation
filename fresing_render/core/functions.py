"""One list of the app's functions (task 0124; format from study 0123).

Every function the owner can see is ONE entry here. The others read it instead of keeping their own lists:

* the side panel sets of task 0062 (``family``, ``panel``, ``fold``: 0062 sorts the panels by them),
* the lessons (``panel`` / ``fold`` / ``button`` / ``prop`` + ``text``: where a lesson points; ``lesson``: the step
  that teaches it – empty until the lessons task),
* the user guide (``guide``: the anchor ``<a id="...">`` in docs/USER-GUIDE.md),
* the test tour (``tour``: the stop ids) and the PC check (``pccheck``: Full line ids),
* the website (``site/media/media.json`` names function ids per picture: ``"functions": ["joints.rotate"]`` →
  "How it's done" links to the guide, written by ``tools/build_site.py``).

A new function adds its entry here and a guide anchor; ``problems()`` (run by the precheck, ``read_repo`` gives it what
it checks against) says in plain words what is not linked. No Blender here: the precheck and the website build read it
with plain Python.
"""

from __future__ import annotations

import ast
import glob
import os
import re
from dataclasses import dataclass

# 0062's function families: the panel sets a project can show ("show only what this project needs").
FAMILIES = {
    "import": "Import & structure",
    "looks": "Looks",
    "motion": "Motion",
    "machines": "Machine motion (cylinders, mechanisms, way covers, hoses, tracks)",
    "cnc": "CNC machine",
    "milling": "Milling",
    "offshore": "Cables, drums & sea",
    "scene": "Scene & render",
    "animation": "Animation & video",
    "queue": "Render queue",
    "web": "Web 3D model",
    "house": "Houses",
    "help": "Help, updates and checks",
}

# Places outside the side panel (a function reached from a menu).
MENUS = {
    "TOPBAR_MT_help": "Help menu",
    "TOPBAR_MT_file_import": "File > Import",
}

# Guide sections that are only reading (no function of their own): no entry needs to name them.
READING = {
    "layout", "start", "install", "navigate", "first-render", "scene", "tips", "inventor-export", "faster-renders",
    "troubleshooting", "self-test", "updates-not-arriving", "renders-folder", "panel-gone", "import-problems",
    "render-problems",
}


@dataclass(frozen=True)
class Function:
    id: str                  # "joints.rotate": area.name, never changes (the website and lessons keep it)
    title: str               # what the owner calls it
    family: str              # one key of FAMILIES
    panel: str               # the side panel's class name (FRESING_PT_…), or a menu of MENUS
    fold: str = ""           # the fold (ui.fold idname) inside that panel, "" = the panel body
    button: str = ""         # the operator a lesson points at ...
    text: str = ""           # ... and its button text when that operator is drawn more than once
    prop: str = ""           # or the setting (property name as the panel draws it)
    guide: str = ""          # docs/USER-GUIDE.md anchor
    tour: tuple = ()         # test-tour stop ids that show it
    pccheck: tuple = ()      # PC-check (Full) line ids that test it
    lesson: str = ""         # "crane:2" = lesson crane, its step 2 (the lessons task fills these in)
    since: str = ""          # the version it came in


FUNCTIONS: dict[str, Function] = {}


def fn(**kw) -> Function:
    f = Function(**kw)
    if f.id in FUNCTIONS:
        DUPLICATES.append(f.id)
    FUNCTIONS[f.id] = f
    return f


DUPLICATES: list = []

# ----- 1 Import, 2 Structure -----
fn(id="import.step", title="Import a STEP file", family="import", panel="FRESING_PT_import",
   button="fresing.import_step", guide="import",
   pccheck=("import.crane", "import.machine", "import.materials", "project.reopen"), since="0.1.0")
fn(id="import.mesh", title="Import a mesh model (glTF, OBJ, FBX)", family="import", panel="FRESING_PT_import",
   button="fresing.import_mesh", text="Import mesh model…", guide="mesh-models", tour=("mesh_import",),
   pccheck=("import.mesh", "import.mesh_fbx"), since="0.2.99")
fn(id="import.update", title="Model update to a new revision", family="import", panel="FRESING_PT_import",
   button="fresing.import_step", text="Update to new revision…", guide="update-model", tour=("update",),
   pccheck=("model.update", "model.update_safe"), since="0.2.0")
fn(id="import.two_copies", title="The same STEP twice", family="import", panel="FRESING_PT_import",
   button="fresing.import_step", guide="import", tour=("copies",), pccheck=("model.two_copies",), since="0.2.44")
fn(id="structure.tree", title="Structure: find, select, hide and lock parts", family="import",
   panel="FRESING_PT_structure", button="fresing.hide_selected", text="Hide", guide="structure", since="0.1.0")
fn(id="structure.cleanup", title="Clean-up: small parts, remove for good", family="import",
   panel="FRESING_PT_cleanup", button="fresing.select_small", guide="cleanup", since="0.2.0")
fn(id="structure.visibility", title="Visibility sets", family="import", panel="FRESING_PT_visibility",
   button="fresing.vis_save", guide="visibility", pccheck=("states.poses",), since="0.2.12")

# ----- 3 Looks -----
fn(id="looks.materials", title="Material groups and ready-made materials", family="looks", panel="FRESING_PT_looks",
   button="fresing.group_preset", guide="looks", tour=("materials",), pccheck=("looks.materials",), since="0.2.8")
fn(id="looks.marine", title="Marine looks: growth, streaks, concrete", family="looks", panel="FRESING_PT_looks",
   button="fresing.group_preset", guide="looks", tour=("marine",), pccheck=("looks.marine",), since="0.2.94")
fn(id="looks.rule_sets", title="Rule sets", family="looks", panel="FRESING_PT_looks",
   button="fresing.rule_set_switch", guide="rule-sets", pccheck=("rules.switch",), since="0.2.13")
fn(id="looks.faces", title="Paint faces", family="looks", panel="FRESING_PT_faces", button="fresing.paint_faces",
   guide="faces", tour=("faces",), pccheck=("faces.painted",), since="0.2.9")
fn(id="looks.decals", title="Logos & stickers", family="looks", panel="FRESING_PT_decals",
   button="fresing.decal_add", guide="decals", tour=("decals",), pccheck=("decals.add",), since="0.2.21")
fn(id="looks.xray", title="X-ray look", family="looks", panel="FRESING_PT_xray", button="fresing.xray_selected",
   guide="xray", tour=("fade",), pccheck=("motion.fade",), since="0.2.59")
fn(id="looks.cutaway", title="Cutaway", family="looks", panel="FRESING_PT_cutaway", button="fresing.cut_add",
   guide="cutaway", tour=("cutaway",), pccheck=("looks.cutaway",), since="0.2.64")
fn(id="looks.find", title="Find & sort parts", family="looks", panel="FRESING_PT_find", button="fresing.find_word",
   guide="find", since="0.2.8")
fn(id="looks.rules", title="Sorting rules", family="looks", panel="FRESING_PT_rules", button="fresing.rule_add",
   guide="rules", since="0.2.8")
fn(id="looks.schemes", title="Paint schemes & templates", family="looks", panel="FRESING_PT_schemes",
   button="fresing.scheme_save", guide="schemes", since="0.2.13")

# ----- 4 Motion: joints, poses -----
fn(id="joints.rotate", title="Rotate joint", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_pick_axis", text="Add rotate joint", guide="motion", tour=("joint",),
   pccheck=("joints.rotate",), since="0.2.0")
fn(id="joints.stack", title="Joint on a joint (stacked)", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_pick_axis", text="Add slide joint", guide="motion", tour=("stack",),
   pccheck=("joints.stack",), since="0.2.10")
fn(id="joints.hover", title="Hover highlight when picking an axis", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_pick_axis", text="Add rotate joint", guide="motion", pccheck=("motion.hover",),
   since="0.2.63")
fn(id="joints.couplings", title="Couplings and motors", family="motion", panel="FRESING_PT_motion",
   button="fresing.joint_follow", guide="couplings", pccheck=("couplings.motor",), since="0.2.18")
fn(id="poses.pose", title="Poses", family="motion", panel="FRESING_PT_poses", button="fresing.pose_save",
   guide="poses", pccheck=("states.poses",), since="0.2.12")
fn(id="poses.explode", title="Exploded view", family="motion", panel="FRESING_PT_poses", button="fresing.explode",
   guide="poses", tour=("explode",), pccheck=("states.poses",), since="0.2.18")

# ----- 4 Motion: machine parts -----
fn(id="machines.cylinder", title="Cylinders", family="machines", panel="FRESING_PT_cylinders",
   button="fresing.cylinder_add", guide="cylinders", tour=("cylinder",), pccheck=("joints.cylinder",),
   since="0.2.25")
fn(id="machines.mechanism", title="Mechanisms: scissor lift, crank", family="machines",
   panel="FRESING_PT_mechanisms", button="fresing.mechanism_add", guide="mechanisms", tour=("mechanism",),
   pccheck=("joints.mechanism",), since="0.2.26")
fn(id="machines.waycover", title="Way covers", family="machines", panel="FRESING_PT_waycover",
   button="fresing.waycover_make", guide="way-covers", tour=("waycover",), pccheck=("machining.waycover",),
   since="0.2.28")
fn(id="machines.waycover_two", title="Two way covers on one axis", family="machines", panel="FRESING_PT_waycover",
   button="fresing.waycover_cover_add", guide="way-covers", tour=("waycover2",),
   pccheck=("machining.waycover_two",), since="0.2.61")
fn(id="machines.hoses", title="Hoses and cables that follow the motion", family="machines", panel="FRESING_PT_flex",
   button="fresing.flex_add_hose", guide="hoses", tour=("hoses",), pccheck=("motion.flex",), since="0.2.78")
fn(id="machines.chains", title="Drag chains", family="machines", panel="FRESING_PT_flex",
   button="fresing.flex_add_chain", guide="hoses", tour=("chains",), pccheck=("motion.flex",), since="0.2.78")
fn(id="machines.tracks", title="Tracks and belts", family="machines", panel="FRESING_PT_tracks",
   button="fresing.track_add", guide="tracks", tour=("tracks",), pccheck=("motion.tracks",), since="0.2.87")

# ----- 4 Motion: cables, drums; the sea -----
fn(id="offshore.cables", title="Cables and paths", family="offshore", panel="FRESING_PT_cables",
   button="fresing.cable_add", guide="cables", tour=("cables",), pccheck=("motion.paths",), since="0.2.80")
fn(id="offshore.served_cable", title="Served cable look: yarn and marker spirals", family="offshore",
   panel="FRESING_PT_cables", prop="look", guide="served-cable", tour=("served",),
   pccheck=("looks.served_cable",), since="0.2.116")
fn(id="offshore.sea_cable", title="Cable into the sea", family="offshore", panel="FRESING_PT_cables",
   fold="fr_cables_sea", button="fresing.cable_sea_add", guide="into-the-sea", tour=("sea_cable",),
   pccheck=("motion.sea_cable",), since="0.2.91")
fn(id="offshore.moving_cable", title="A cable on a moving part", family="offshore", panel="FRESING_PT_cables",
   button="fresing.cable_let_go", guide="moving-cable", tour=("moving_cable",), pccheck=("motion.moving_cable",),
   since="0.2.95")
fn(id="offshore.settle", title="A let-go cable settles onto the seabed", family="offshore", panel="FRESING_PT_cables",
   fold="fr_cables_sea", prop="sea_settle", guide="settle", tour=("moving_cable",), pccheck=("motion.moving_cable",),
   since="0.2.103")
fn(id="offshore.swivel", title="A sheave on a swivel turns to its wire", family="offshore", panel="FRESING_PT_cables",
   prop="swivel", guide="swivel", since="0.2.103")
fn(id="offshore.spool", title="Drums and carousels", family="offshore", panel="FRESING_PT_spools",
   button="fresing.spool_add", guide="drums", tour=("spool",), pccheck=("motion.spool",), since="0.2.85")
fn(id="offshore.vessel_motion", title="Vessel motion at sea", family="offshore", panel="FRESING_PT_vessel_motion",
   prop="enabled", guide="vessel-motion", tour=("vessel",), pccheck=("scene.vessel_motion",), since="0.2.65")
fn(id="offshore.vessel_work", title="Vessel at work: wake, waves, thruster jets", family="offshore",
   panel="FRESING_PT_vessel_work", prop="mode", guide="vessel-work", tour=("vessel_work",),
   pccheck=("scene.vessel_work",), since="0.2.127")
fn(id="offshore.thrusters", title="The vessel's thrusters", family="offshore", panel="FRESING_PT_vessel_work",
   fold="fr_vessel_thrusters", button="fresing.vessel_thrusters_find", guide="vessel-work", since="0.2.127")

# ----- 4 Motion: CNC machine -----
fn(id="cnc.machine", title="CNC machine set-up", family="cnc", panel="FRESING_PT_cnc", button="fresing.cnc_find_axes",
   guide="cnc", since="0.2.30")
fn(id="cnc.gcode", title="Run a G-code program", family="cnc", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="run-gcode", tour=("gcode",), pccheck=("motion.gcode",), since="0.2.30")
fn(id="cnc.acceleration", title="Speed up and slow down (acceleration)", family="cnc", panel="FRESING_PT_cnc",
   fold="fr_cnc_machine", prop="use_accel", guide="cnc", tour=("accel",), pccheck=("gcode.acceleration",),
   since="0.2.83")
fn(id="cnc.tools", title="Tools", family="cnc", panel="FRESING_PT_cnc_tools", button="fresing.cnc_tool_add",
   guide="tools", tour=("tools",), pccheck=("milling.tools",), since="0.2.36")
fn(id="cnc.toolchange_hand", title="Tool change by hand", family="cnc", panel="FRESING_PT_cnc_changes",
   prop="change_mode", guide="tool-changes", tour=("hand",), pccheck=("motion.toolchange",), since="0.2.45")
fn(id="cnc.atc", title="Tool changer with pockets", family="cnc", panel="FRESING_PT_cnc_changes",
   button="fresing.cnc_pocket_click", guide="tool-changes", tour=("atc",), pccheck=("motion.toolchange",),
   since="0.2.45")
fn(id="cnc.doublearm", title="Double-arm tool changer", family="cnc", panel="FRESING_PT_cnc_changes",
   button="fresing.cnc_arm_hub", guide="tool-changes", tour=("doublearm",), pccheck=("motion.doublearm",),
   since="0.2.51")
fn(id="cnc.rotary4", title="4th axis", family="cnc", panel="FRESING_PT_cnc_rotary", button="fresing.cnc_rotary_check",
   guide="rotary-axes", tour=("rotary4",), pccheck=("milling.rotary",), since="0.2.52")
fn(id="cnc.rotary5", title="5th axis: the tool follows the part", family="cnc", panel="FRESING_PT_cnc_rotary",
   prop="kinematics", guide="rotary-axes", tour=("rotary5",), pccheck=("milling.rotary",), since="0.2.52")
fn(id="cnc.air", title="Air blast", family="cnc", panel="FRESING_PT_cnc", fold="fr_cnc_air",
   button="fresing.cnc_air_nozzle", guide="air-blast", tour=("air",), pccheck=("milling.air",), since="0.2.34")
fn(id="cnc.coolant", title="Coolant", family="cnc", panel="FRESING_PT_cnc_coolant",
   button="fresing.cnc_coolant_nozzle", guide="coolant", tour=("coolant",), pccheck=("milling.coolant",),
   since="0.2.48")

# ----- 4 Motion: milling -----
fn(id="milling.cut", title="Milling: material disappears where the bit cuts", family="milling",
   panel="FRESING_PT_milling", button="fresing.mill_add_bit", guide="milling", pccheck=("milling.cut",),
   since="0.2.19")
fn(id="milling.cut_look", title="Cut faces and raw stock", family="milling", panel="FRESING_PT_milling",
   prop="cut_look", guide="milling", tour=("cut_look",), pccheck=("milling.cut_look",), since="0.2.43")
fn(id="milling.marks", title="Tool marks on cut faces", family="milling", panel="FRESING_PT_milling", prop="marks",
   guide="tool-marks", tour=("marks",), pccheck=("milling.marks",), since="0.2.73")
fn(id="milling.fast_map", title="Fast 3-axis: long programs as a height map", family="milling",
   panel="FRESING_PT_milling", prop="fast_map", guide="milling-fast", tour=("toolpath",),
   pccheck=("milling.fast_map",), since="0.2.117")
fn(id="milling.chips", title="Chips", family="milling", panel="FRESING_PT_milling_chips", prop="chips",
   guide="chips", tour=("chips",), pccheck=("milling.chips",), since="0.2.22")
fn(id="milling.toolpath", title="Make a toolpath", family="milling", panel="FRESING_PT_milling_toolpath",
   button="fresing.toolpath_make", guide="toolpath", tour=("toolpath",), pccheck=("milling.toolpath",),
   since="0.2.55")

# ----- 5 Scene & Render -----
fn(id="looks.light_look", title="Light look", family="scene", panel="FRESING_PT_scene", button="fresing.light_look",
   text="Product studio", guide="light-look", tour=("looks",), pccheck=("scene.looks",), since="0.2.17")
fn(id="scene.surroundings", title="Background & surroundings", family="scene", panel="FRESING_PT_scene",
   prop="background", guide="surroundings", tour=("sea",), pccheck=("scene.sea", "scene.hall"), since="0.2.12")
fn(id="scene.light", title="Light", family="scene", panel="FRESING_PT_scene", prop="lighting", guide="light",
   since="0.2.12")
fn(id="scene.props", title="Props for scale", family="scene", panel="FRESING_PT_props", button="fresing.prop_add",
   guide="props", tour=("props",), pccheck=("scene.props",), since="0.2.17")
fn(id="animation.people", title="People walk, carry and meet", family="animation", panel="FRESING_PT_people",
   button="fresing.person_add", guide="people", tour=("people",), pccheck=("people.walk",), since="0.2.128")
fn(id="scene.props_detail", title="Props: detail by distance", family="scene", panel="FRESING_PT_props",
   prop="props_detail", guide="props-detail", since="0.2.124")
fn(id="scene.sea_ground", title="Sea cut-away shows the ground", family="scene", panel="FRESING_PT_scene",
   prop="sea_cut_ground", guide="sea-ground", pccheck=("scene.sea_ground",), since="0.2.115")
fn(id="scene.weather", title="Weather & time", family="scene", panel="FRESING_PT_weather", prop="enabled",
   guide="weather", tour=("weather",),
   pccheck=("weather.time", "weather.rain", "weather.snow", "weather.fog", "weather.sea"), since="0.2.88")
fn(id="scene.start_scene_save", title="Save into start scene", family="scene", panel="FRESING_PT_weather",
   button="fresing.save_into_start_scene", guide="start-scene", tour=("start_scene",), since="0.2.125")
fn(id="scene.night", title="Night shift and work lights", family="scene", panel="FRESING_PT_weather",
   button="fresing.work_light_add", guide="weather", tour=("night",), since="0.2.88")
fn(id="scene.camera", title="Camera views", family="scene", panel="FRESING_PT_camera", button="fresing.camera_add",
   text="3/4 hero, high", guide="camera", tour=("blur",), pccheck=("scene.views",), since="0.2.12")
fn(id="scene.blur", title="Background blur and sharp spot", family="scene", panel="FRESING_PT_camera",
   button="fresing.focus_pick", guide="camera", tour=("blur",), pccheck=("scene.blur",), since="0.2.17")
fn(id="scene.turntable", title="Turntable video", family="scene", panel="FRESING_PT_turntable",
   button="fresing.turntable", guide="turntable", tour=("turntable",), pccheck=("scene.turntable",), since="0.2.17")
fn(id="scene.still", title="Render a picture", family="scene", panel="FRESING_PT_output", button="fresing.render",
   guide="image-size", tour=("still",), pccheck=("render.gpu", "render.cpu", "render.eevee", "gpu.device"),
   since="0.1.0")
fn(id="scene.shapes", title="Upright 9:16 and square 1:1 pictures", family="scene", panel="FRESING_PT_output",
   prop="out_orientation", guide="image-size", tour=("shapes",), since="0.2.23")
fn(id="scene.save", title="Saved scenes", family="scene", panel="FRESING_PT_shots", button="fresing.shot_save",
   guide="saved-scenes", tour=("still",), pccheck=("states.poses",), since="0.2.12")

# ----- House, web 3D -----
fn(id="house.import", title="House from House Planner", family="house", panel="FRESING_PT_house",
   button="fresing.house_import", guide="house", tour=("house",), pccheck=("house.bake",), since="0.2.92")
fn(id="web.export", title="Web 3D model", family="web", panel="FRESING_PT_web3d", button="fresing.web3d_export",
   guide="web3d", tour=("web3d",), pccheck=("web3d.export",), since="0.2.77")
fn(id="web.surroundings", title="Web 3D model with surroundings", family="web", panel="FRESING_PT_web3d",
   prop="env_mode", guide="web3d-surroundings", tour=("web3d_env",), pccheck=("web3d.surroundings",),
   since="0.2.86")
fn(id="web.marine_detail", title="Web 3D model: Marine detail Normal / Fine", family="web", panel="FRESING_PT_web3d",
   prop="marine_detail", guide="web3d-marine", tour=("web3d",), pccheck=("web3d.export",), since="0.2.126")
fn(id="web.light", title="Web 3D model with baked light", family="web", panel="FRESING_PT_web3d", prop="light",
   guide="web3d-light", tour=("web3d_light",), pccheck=("web3d.bake",), since="0.2.89")
fn(id="web.moving", title="Web 3D model: cables, ropes, hoses and tracks move with their looks", family="web",
   panel="FRESING_PT_web3d", prop="animation", guide="web3d-moving", pccheck=("web3d.moving",), since="0.2.114")
fn(id="web.under", title="Web 3D model under the sea: seabed, sea cut-away, camera under water", family="web",
   panel="FRESING_PT_web3d", prop="env_mode", guide="web3d-under", pccheck=("web3d.under",), since="0.2.129")
fn(id="web.player", title="Web 3D page: settings, playback, saved views", family="web", panel="FRESING_PT_web3d",
   button="fresing.web3d_export", guide="web3d-player", tour=("web3d",), pccheck=("web3d.export",), since="0.2.112")
fn(id="web.tools", title="Web 3D page: part info, measure, cutaway, fade the rest", family="web",
   panel="FRESING_PT_web3d", prop="measure_faces", guide="web3d-tools", tour=("web3d",), pccheck=("web3d.export",),
   since="0.2.130")

# ----- 6 Animation -----
fn(id="animation.add", title="Animation", family="animation", panel="FRESING_PT_animation", button="fresing.anim_add",
   guide="animation", tour=("joint",), since="0.2.10")
fn(id="animation.joint_step", title="Move joint step", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="animation", tour=("joint",), since="0.2.10")
fn(id="animation.build", title="Build & play", family="animation", panel="FRESING_PT_animation",
   button="fresing.anim_build", guide="animation", tour=("joint",), since="0.2.10")
fn(id="animation.motor", title="Run motor step", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="run-motor", pccheck=("couplings.motor",), since="0.2.18")
fn(id="animation.camera_path", title="Camera rides along, flies a path, watches a part", family="animation",
   panel="FRESING_PT_animation", button="fresing.path_add_view", guide="camera-path", tour=("camera",),
   pccheck=("camera.path",), since="0.2.62")
fn(id="animation.fade", title="Fade out and fade in", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="fade", tour=("fade",), pccheck=("motion.fade",), since="0.2.59")
fn(id="animation.trails", title="Trail lines", family="animation", panel="FRESING_PT_trails",
   button="fresing.trail_add", guide="trails", tour=("fade",), pccheck=("motion.fade",), since="0.2.59")
fn(id="animation.sequence", title="Assembly sequence", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="sequence", tour=("sequence", "sequenceframe"),
   pccheck=("animation.sequence", "animation.sequence_frame"), since="0.2.79")
fn(id="animation.back_to_cad", title="Back to CAD step", family="animation", panel="FRESING_PT_animation",
   button="fresing.block_add", guide="back-to-cad", tour=("backtocad",), pccheck=("animation.back_to_cad",),
   since="0.2.102")
fn(id="animation.weather_step", title="Weather & time step", family="animation", panel="FRESING_PT_animation",
   prop="wx_preset", guide="weather", tour=("weather_step",), pccheck=("weather.step",), since="0.2.88")
fn(id="animation.vessel_step", title="Vessel at work step", family="animation", panel="FRESING_PT_animation",
   prop="vw_mode", guide="vessel-work-step", tour=("vessel_work",), since="0.2.127")
fn(id="animation.finishing", title="Video finishing: title, end card, captions", family="animation",
   panel="FRESING_PT_finishing", prop="fin_title_on", guide="finishing", tour=("finishing",), since="0.2.23")
fn(id="animation.cards", title="Picture cards in a video", family="animation", panel="FRESING_PT_cards",
   button="fresing.card_add", guide="pictures-music", since="0.2.27")
fn(id="animation.music", title="Music under a video", family="animation", panel="FRESING_PT_music",
   prop="music_on", guide="pictures-music", pccheck=("video.labels",), since="0.2.27")
fn(id="animation.labels", title="Labels with lines", family="animation", panel="FRESING_PT_labels",
   button="fresing.callout_add", guide="labels", tour=("labels",), pccheck=("video.labels",), since="0.2.27")
fn(id="animation.brand", title="Brand kit & logo", family="animation", panel="FRESING_PT_brand",
   button="fresing.brand_save", guide="brand-kit", tour=("finishing",), pccheck=("video.finishing",),
   since="0.2.23")
fn(id="animation.watermark", title="Watermark", family="animation", panel="FRESING_PT_watermark", prop="wm_on",
   guide="watermark", pccheck=("video.finishing",), since="0.2.23")
fn(id="animation.clash", title="Clash check", family="animation", panel="FRESING_PT_clash",
   button="fresing.clash_check", guide="clash", tour=("clash",), pccheck=("animation.clash",), since="0.2.53")
fn(id="animation.product_video", title="One-click product video", family="animation", panel="FRESING_PT_animation",
   fold="fr_product_video", button="fresing.product_video", guide="product-video", tour=("productvideo",),
   pccheck=("animation.product_video",), since="0.2.81")

# ----- 7 Render queue -----
fn(id="queue.still", title="Render queue: a picture", family="queue", panel="FRESING_PT_queue",
   button="fresing.queue_add", guide="queue", tour=("queue",), pccheck=("queue.frame_shown",), since="0.2.12")
fn(id="queue.video", title="Render queue: a video", family="queue", panel="FRESING_PT_queue",
   button="fresing.queue_add", guide="queue", tour=("queue",), pccheck=("queue.video", "queue.eevee"),
   since="0.2.0")
fn(id="queue.time_test", title="Time test", family="queue", panel="FRESING_PT_queue", button="fresing.queue_add",
   text="Time test (2 frames)", guide="queue", pccheck=("queue.time_test",), since="0.2.4")
fn(id="queue.start_later", title="Start the queue later", family="queue", panel="FRESING_PT_queue",
   button="fresing.queue_start_later", guide="queue", tour=("startlater",), since="0.2.49")
fn(id="queue.schemes", title="Every paint scheme", family="queue", panel="FRESING_PT_queue", fold="fr_queue_schemes",
   button="fresing.queue_schemes", guide="queue", tour=("schemes",), pccheck=("queue.schemes",), since="0.2.60")

# ----- Help menu -----
fn(id="help.updates", title="Updates", family="help", panel="TOPBAR_MT_help", button="fresing.update_check",
   guide="updates", pccheck=("updates.check", "updates.safe"), since="0.2.16")
fn(id="help.pc_check", title="PC check", family="help", panel="TOPBAR_MT_help", button="fresing.pc_check",
   guide="pc-check", pccheck=("app.start",), since="0.2.24")
fn(id="help.tour", title="Test tour", family="help", panel="TOPBAR_MT_help", button="fresing.tour_make",
   guide="tour", pccheck=("tour.make",), since="0.2.47")
fn(id="help.demo", title="Demo project: cable-lay vessel", family="help", panel="TOPBAR_MT_help",
   button="fresing.demo_make", guide="demo", tour=("demo",), since="0.2.68")


# ---------------------------------------------------------------------------
# keeping the lists in step (the precheck runs this; no Blender)
# ---------------------------------------------------------------------------

ID = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")


def guide_anchors(text: str) -> list:
    """The anchors of docs/USER-GUIDE.md (``<a id="..."></a>``), in order (a duplicate shows twice)."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)        # the notes for the chats are not the guide
    return re.findall(r'<a id="([^"]+)"></a>', text)


def problems(functions=None, *, anchors=None, stops=None, lines=None, panels=None, folds=None, operators=None,
             props=None, texts=None, lessons=None, duplicates=None) -> list:
    """Plain sentences, one per thing out of step; [] = all fine.

    anchors: the guide's anchors; stops: the tour's stop ids; lines: the PC check's Full line ids; panels: the side
    panels' class names; folds: the fold ids; operators: the operator ids; props: the property names the panels draw;
    texts: the source the button texts must appear in; lessons: {"crane": number of steps}. An argument left None is
    not checked (``read_repo`` gives them all)."""
    funcs = FUNCTIONS if functions is None else functions
    items = list(funcs.values()) if isinstance(funcs, dict) else list(funcs)
    out = []
    seen = set()
    for d in (DUPLICATES if duplicates is None else duplicates):
        out.append(f"{d}: two entries have this id in fresing_render/core/functions.py (ids must be unique)")
    for f in items:
        if f.id in seen:
            out.append(f"{f.id}: two entries have this id in fresing_render/core/functions.py (ids must be unique)")
        seen.add(f.id)
        if not ID.match(f.id):
            out.append(f"{f.id}: an id is area.name in small letters (like joints.rotate)")
        if f.family not in FAMILIES:
            out.append(f"{f.id}: family '{f.family}' is not one of {', '.join(FAMILIES)}")
        if not f.title:
            out.append(f"{f.id}: give it a title (the owner's word for it)")
        if f.since and not VERSION.match(f.since):
            out.append(f"{f.id}: since '{f.since}' is not a version like 0.2.47")
        if not (f.button or f.prop):
            out.append(f"{f.id}: no button or setting for a lesson to point at (button= or prop=)")
        if panels is not None and f.panel not in panels and f.panel not in MENUS:
            out.append(f"{f.id}: unknown panel '{f.panel}' (a FRESING_PT_… class in blender/ui*.py, or "
                       f"{' / '.join(MENUS)})")
        if folds is not None and f.fold and f.fold not in folds:
            out.append(f"{f.id}: unknown fold '{f.fold}' (the idname of a fold(...) in blender/ui*.py)")
        if operators is not None and f.button and f.button not in operators:
            out.append(f"{f.id}: unknown button '{f.button}' (no operator has this bl_idname)")
        if props is not None and f.prop and f.prop not in props:
            out.append(f"{f.id}: unknown setting '{f.prop}' (no panel draws a property of this name)")
        if texts is not None and f.text and f'"{f.text}"' not in texts:
            out.append(f"{f.id}: the button text '{f.text}' is not in the app's code (copy it from the panel)")
        if anchors is not None:
            if not f.guide:
                out.append(f"{f.id}: no guide anchor (guide=; add <a id=\"…\"></a> above its section in "
                           "docs/USER-GUIDE.md)")
            elif f.guide not in anchors:
                out.append(f"{f.id}: the guide has no anchor '{f.guide}' (add <a id=\"{f.guide}\"></a> above its "
                           "section in docs/USER-GUIDE.md)")
        if stops is not None:
            out += [f"{f.id}: no tour stop '{t}'" for t in f.tour if t not in stops]
        if lines is not None:
            out += [f"{f.id}: no PC-check Full line '{p}'" for p in f.pccheck if p not in lines]
        if lessons is not None and f.lesson:
            name, _, k = f.lesson.partition(":")
            if name not in lessons or not k.isdigit() or not 1 <= int(k) <= lessons[name]:
                out.append(f"{f.id}: lesson step '{f.lesson}' does not exist")
    if stops is not None:
        named = {t for f in items for t in f.tour}
        out += [f"tour stop '{s}' is named by no entry: add it to the tour=() of its function in "
                "fresing_render/core/functions.py" for s in stops if s not in named]
    if lines is not None:
        named = {p for f in items for p in f.pccheck}
        out += [f"PC-check line '{p}' is named by no entry: add it to the pccheck=() of its function in "
                "fresing_render/core/functions.py" for p in lines if p not in named]
    if anchors is not None:
        anchors = list(anchors)
        for a in sorted({a for a in anchors if anchors.count(a) > 1}):
            out.append(f"the guide has the anchor '{a}' twice (docs/USER-GUIDE.md): give one another id")
        named = {f.guide for f in items}
        out += [f"guide section '{a}' is named by no entry: add one in fresing_render/core/functions.py (or add it "
                "to READING there if it is only reading)" for a in dict.fromkeys(anchors)
                if a not in named and a not in READING]
    return out


def guide_link(fid: str, base: str = "guide/") -> str:
    """The website's link for a function id in media.json (``functions: [...]``)."""
    return f"{base}#{FUNCTIONS[fid].guide}"


# ---------------------------------------------------------------------------
# what the list is checked against, read from the repository (no Blender)
# ---------------------------------------------------------------------------

def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _strings(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def read_repo(root: str) -> dict:
    """Everything ``problems`` checks against, read from a checkout: the keyword arguments of ``problems``."""
    pkg = os.path.join(root, "fresing_render")
    out = {"anchors": guide_anchors(_src(os.path.join(root, "docs", "USER-GUIDE.md")))}
    tour = os.path.join(pkg, "blender", "tour.py")
    out["stops"] = re.findall(r'^stop\(\s*"([^"]+)"', _src(tour), re.M) if os.path.isfile(tour) else []
    lines = []
    for name in ("checks.py", "heavy.py"):
        path = os.path.join(pkg, "pccheck", name)
        if not os.path.isfile(path):
            continue
        for node in ast.walk(ast.parse(_src(path))):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for d in node.decorator_list:
                if not (isinstance(d, ast.Call) and getattr(d.func, "id", "") == "line" and d.args):
                    continue
                modes = d.args[3] if len(d.args) >= 4 else None
                for k in d.keywords:
                    if k.arg == "modes":
                        modes = k.value
                names = {n.id for n in ast.walk(modes) if isinstance(n, ast.Name)} if modes is not None else {"F"}
                if "F" in names and _strings(d.args[0]):
                    lines.append(_strings(d.args[0]))
    out["lines"] = lines
    panels, folds, operators, props, texts = set(), set(), set(), set(), []
    for path in sorted(glob.glob(os.path.join(pkg, "**", "*.py"), recursive=True)):
        src = _src(path)
        texts.append(src)
        tree = ast.parse(src)
        ui = os.path.basename(path).startswith("ui")
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                if ui and node.name.startswith("FRESING_PT_"):
                    panels.add(node.name)
                for s in node.body:
                    if (isinstance(s, ast.Assign) and len(s.targets) == 1
                            and getattr(s.targets[0], "id", "") == "bl_idname"):
                        v = _strings(s.value)
                        if v and v.startswith("fresing."):
                            operators.add(v)
            elif ui and isinstance(node, ast.Call):
                name = getattr(node.func, "id", "") or getattr(node.func, "attr", "")
                if name == "fold" and len(node.args) >= 2 and _strings(node.args[1]):
                    folds.add(_strings(node.args[1]))
                elif name in ("prop", "prop_search") and len(node.args) >= 2 and _strings(node.args[1]):
                    props.add(_strings(node.args[1]))
    out.update(panels=panels, folds=folds, operators=operators, props=props, texts="\n".join(texts))
    return out
