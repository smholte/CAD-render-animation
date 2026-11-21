"""Where each side-panel panel sits: ONE table for every text that names a place (task 0062).

A tooltip, a hint or a tour stop that says "6 Animation > Labels" asks ``where("FRESING_PT_labels")`` instead of
writing it out: when a sub-panel moves (0062 moved Brand kit & logo, Labels and Watermark from 5 Scene & Render to
6 Animation), only this table changes. ``tests/test_places.py`` compares it with the registered panels (parent and
title), so it cannot go out of step. No Blender here: ``props.py``, the tour and the precheck read it.
"""

from __future__ import annotations

# the sections, in order (task 0201 added 8 Lifting plan): class name -> title as written in texts ("4 Motion": one space)
SECTIONS = {
    "FRESING_PT_import": "1 Import",
    "FRESING_PT_structure": "2 Structure",
    "FRESING_PT_looks": "3 Looks",
    "FRESING_PT_motion": "4 Motion",
    "FRESING_PT_scene": "5 Scene & Render",
    "FRESING_PT_animation": "6 Animation",
    "FRESING_PT_queue": "7 Render queue",
    "FRESING_PT_lifting": "8 Lifting plan",          # task 0201
}

# sub-panel -> (parent panel, title), in the order they show under their parent
PLACES = {
    # 2 Structure
    "FRESING_PT_cleanup": ("FRESING_PT_structure", "Clean-up"),
    "FRESING_PT_visibility": ("FRESING_PT_structure", "Visibility sets"),
    # 3 Looks
    "FRESING_PT_faces": ("FRESING_PT_looks", "Paint faces"),
    "FRESING_PT_decals": ("FRESING_PT_looks", "Logos & stickers"),
    "FRESING_PT_xray": ("FRESING_PT_looks", "X-ray look"),
    "FRESING_PT_cutaway": ("FRESING_PT_looks", "Slice"),
    "FRESING_PT_find": ("FRESING_PT_looks", "Find & sort parts"),
    "FRESING_PT_rules": ("FRESING_PT_looks", "Sorting rules"),
    "FRESING_PT_schemes": ("FRESING_PT_looks", "Paint schemes & templates"),
    # 4 Motion
    "FRESING_PT_cylinders": ("FRESING_PT_motion", "Cylinders"),
    "FRESING_PT_mechanisms": ("FRESING_PT_motion", "Mechanisms"),
    "FRESING_PT_poses": ("FRESING_PT_motion", "Poses & exploded views"),
    "FRESING_PT_milling": ("FRESING_PT_motion", "Milling"),
    "FRESING_PT_milling_chips": ("FRESING_PT_milling", "Chips"),
    "FRESING_PT_milling_toolpath": ("FRESING_PT_milling", "Make a toolpath"),
    "FRESING_PT_cnc": ("FRESING_PT_motion", "CNC machine"),
    "FRESING_PT_cnc_rotary": ("FRESING_PT_cnc", "Rotary axes"),
    "FRESING_PT_cnc_tools": ("FRESING_PT_cnc", "Tools"),
    "FRESING_PT_cnc_changes": ("FRESING_PT_cnc", "Tool changes"),
    "FRESING_PT_cnc_coolant": ("FRESING_PT_cnc", "Coolant"),
    "FRESING_PT_waycover": ("FRESING_PT_motion", "Way covers"),
    "FRESING_PT_flex": ("FRESING_PT_motion", "Hoses and drag chains"),
    "FRESING_PT_cables": ("FRESING_PT_motion", "Cables and paths"),
    "FRESING_PT_spools": ("FRESING_PT_motion", "Drums and carousels"),
    "FRESING_PT_tracks": ("FRESING_PT_motion", "Tracks and belts"),
    # 5 Scene & Render, in the order the work goes (0062): surroundings, camera, saved scenes, outputs
    "FRESING_PT_weather": ("FRESING_PT_scene", "Weather & time"),
    "FRESING_PT_vessel_motion": ("FRESING_PT_scene", "Vessel motion"),
    "FRESING_PT_vessel_work": ("FRESING_PT_scene", "Vessel at work"),
    "FRESING_PT_props": ("FRESING_PT_scene", "Props for scale"),
    "FRESING_PT_house": ("FRESING_PT_scene", "House from House Planner"),
    "FRESING_PT_camera": ("FRESING_PT_scene", "Camera"),
    "FRESING_PT_shots": ("FRESING_PT_scene", "Saved scenes"),
    "FRESING_PT_output": ("FRESING_PT_scene", "Image size & render"),
    "FRESING_PT_turntable": ("FRESING_PT_scene", "Turntable video"),
    "FRESING_PT_web3d": ("FRESING_PT_scene", "Web 3D model"),
    # 6 Animation: the video finishing group together (0062 moved the last three here from 5)
    "FRESING_PT_people": ("FRESING_PT_animation", "People"),
    "FRESING_PT_clash": ("FRESING_PT_animation", "Clash check"),
    "FRESING_PT_trails": ("FRESING_PT_animation", "Trail lines"),
    "FRESING_PT_finishing": ("FRESING_PT_animation", "Finishing"),
    "FRESING_PT_cards": ("FRESING_PT_animation", "Pictures"),
    "FRESING_PT_music": ("FRESING_PT_animation", "Music"),
    "FRESING_PT_brand": ("FRESING_PT_animation", "Brand kit & logo"),
    "FRESING_PT_labels": ("FRESING_PT_animation", "Labels"),
    "FRESING_PT_watermark": ("FRESING_PT_animation", "Watermark"),
    # 8 Lifting plan (task 0201), in the order the work goes
    "FRESING_PT_lifting_equipment": ("FRESING_PT_lifting", "Equipment"),
    "FRESING_PT_lifting_load": ("FRESING_PT_lifting", "Load"),
    "FRESING_PT_lifting_rigging": ("FRESING_PT_lifting", "Rigging"),
    "FRESING_PT_lifting_hook": ("FRESING_PT_lifting", "Hook & capacity"),
}

# panels of the Fresing tab that are no section and no sub-panel of one (above 1 Import, or their own tab / popover)
OTHER = {
    "FRESING_PT_update": "Update available",
    "FRESING_PT_tour": "Learning hub",
    "FRESING_PT_lesson": "Lesson",
    "FRESING_PT_workspace": "Workspace",
    "FRESING_PT_favourites": "Favourites",
    "FRESING_PT_next": "What's next",
    "FRESING_PT_tabs": "Sections",
    "FRESING_PT_make": "Make",
    "FRESING_PT_make_header": "Make",
    "FRESING_PT_make_anim": "Animation video",
    "FRESING_PT_make_product": "Product video",
    "FRESING_PT_setup": "Set-up",
}


def section_of(panel: str) -> str:
    """The section (class name) a panel belongs to: itself for a section, '' for a panel outside the seven."""
    seen = set()
    while panel in PLACES and panel not in seen:
        seen.add(panel)
        panel = PLACES[panel][0]
    return panel if panel in SECTIONS else ""


def number_of(panel: str) -> int:
    """1 … 7 for a panel of a section, 0 for the others."""
    sec = section_of(panel)
    return list(SECTIONS).index(sec) + 1 if sec else 0


def chain(panel: str) -> list:
    """The titles from the section down to the panel: ["6 Animation", "Labels"]."""
    out = []
    seen = set()
    while panel in PLACES and panel not in seen:
        seen.add(panel)
        out.append(PLACES[panel][1])
        panel = PLACES[panel][0]
    if panel in SECTIONS:
        out.append(SECTIONS[panel])
    elif panel in OTHER:
        out.append(OTHER[panel])
    return out[::-1]


def where(panel: str, fold: str = "") -> str:
    """"6 Animation > Labels" (and "… > Library" for a fold inside it). ``panel`` with or without "FRESING_PT_"."""
    if not panel.startswith("FRESING_PT_"):
        panel = "FRESING_PT_" + panel
    parts = chain(panel)
    if not parts:
        raise KeyError(f"{panel} is not in core/places.py")
    return " > ".join(parts + ([fold] if fold else []))


def children(panel: str) -> list:
    """The sub-panels directly under a panel, in order."""
    return [name for name, (parent, _t) in PLACES.items() if parent == panel]
