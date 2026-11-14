"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.2.95"

_modules = []


def _classes():
    from .blender import (ops_callouts, ops_clash, ops_coolant, ops_cylinders, ops_decals, ops_doublearm, ops_fade, ops_gcode,
                          ops_import, ops_linkages, ops_machining, ops_main, ops_motion, ops_panels, ops_waycover,
                          ops_demo, ops_rule_sets, ops_scene, ops_surroundings, ops_toolpath, ops_tour, ops_video, prefs, ui, ui_callouts,
                          ui_clash, ui_coolant, ui_decals, ui_fade, ui_gcode, ui_machining, ui_motion, ui_tour, ui_video,
                          ui_section, ui_waycover, updates)
    from .blender import ops_section                # task 0086: 3 Looks > Cutaway
    from .blender import ops_queue_schemes          # task 0074: 7 Render queue > Every paint scheme
    from .blender import ops_vessel_motion, ui_vessel_motion   # task 0085: 5 Scene & Render > Vessel motion
    from .blender import ops_flex, ui_flex          # task 0058: 4 Motion > Hoses and drag chains
    from .blender import ops_paths, ui_paths        # task 0078: 4 Motion > Cables and paths (after Hoses and drag chains)
    from .blender import ops_paths_sea              # task 0081: … > Into the sea, things on the cable
    from .blender import ops_product_video       # task 0101: 6 Animation > Make a product video
    from .blender import ops_spool, ui_spool        # task 0080: 4 Motion > Drums and carousels (after Cables and paths)
    from .blender import ops_tracks, ui_tracks      # task 0079: 4 Motion > Tracks and belts (after Drums and carousels)
    from .blender import ops_web3d, ui_web3d     # task 0099: 5 Scene & Render > Web 3D model (after Turntable video)
    from .blender import ops_weather, ui_weather  # task 0109: 5 Scene & Render > Weather & time (after Vessel motion)
    from .blender import ops_house, ui_house      # task 0114: 5 Scene & Render > House from House Planner
    # 3 Looks > Logos & stickers (task 0024) right after Paint faces: sub-panels show in registration order
    looks = list(ui.CLASSES)
    at = looks.index(ui.FRESING_PT_faces) + 1
    looks[at:at] = ui_decals.PANELS
    at = looks.index(ui_decals.PANELS[-1]) + 1
    looks[at:at] = ui_fade.PANELS                # 3 Looks > X-ray look (task 0073)
    at = looks.index(ui_fade.PANELS[-1]) + 1
    looks[at:at] = ui_section.PANELS             # 3 Looks > Cutaway (task 0086)
    at = looks.index(ui.FRESING_PT_props) + 1
    looks[at:at] = ui_vessel_motion.CLASSES      # 5 Scene & Render > Vessel motion (task 0085), after Props
    at = looks.index(ui_vessel_motion.CLASSES[-1]) + 1
    looks[at:at] = ui_weather.CLASSES            # 5 Scene & Render > Weather & time (task 0109)
    at = looks.index(ui_weather.CLASSES[-1]) + 1
    looks[at:at] = ui_house.CLASSES              # 5 Scene & Render > House from House Planner (task 0114)
    # the update notice first: a panel registered first sits on top of the Fresing tab; then the test tour (task
    # 0059, only in a tour project)
    return (updates.CLASSES + ui_tour.CLASSES + ops_tour.CLASSES + prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ops_motion.CLASSES
            + ops_cylinders.CLASSES + ops_linkages.CLASSES + ops_panels.CLASSES + ops_rule_sets.CLASSES
            + ops_surroundings.CLASSES + ops_scene.CLASSES + ops_machining.CLASSES + ops_gcode.CLASSES
            + ops_doublearm.CLASSES + ops_coolant.CLASSES + ops_waycover.CLASSES + ops_flex.CLASSES + ops_paths.CLASSES + ops_paths_sea.CLASSES + ops_spool.CLASSES + ops_tracks.CLASSES + ops_decals.CLASSES + ops_video.CLASSES
            + ops_callouts.CLASSES + ops_clash.CLASSES + ops_fade.CLASSES + ops_section.CLASSES + ui_section.CLASSES + ops_toolpath.CLASSES + ops_web3d.CLASSES + ops_product_video.CLASSES + tuple(looks) + ui_web3d.CLASSES + ui_motion.CLASSES + ui_machining.CLASSES
            + ui_gcode.CLASSES + ui_coolant.CLASSES + ui_waycover.CLASSES + ui_flex.CLASSES + ui_paths.CLASSES + ui_spool.CLASSES + ui_tracks.CLASSES + ui_video.CLASSES + ui_callouts.CLASSES
            + ui_clash.CLASSES + ui_fade.CLASSES + ops_queue_schemes.CLASSES + ops_vessel_motion.CLASSES + ops_weather.CLASSES + ops_demo.CLASSES
            + ops_house.CLASSES)


def register():
    import bpy

    from .blender import clash, coolant, decals, handlers, hover, linkages, machining, project_lock, props, updates
    from .blender import vessel_motion
    props.register()
    decals.register()
    for cls in _classes():
        if issubclass(cls, bpy.types.Operator) and cls.__doc__ and "\n" in cls.__doc__:
            # the docstring is the tooltip: Blender keeps its line breaks, so a docstring wrapped in the
            # source would show a sentence broken in the middle
            cls.__doc__ = " ".join(cls.__doc__.split())
        bpy.utils.register_class(cls)
    handlers.register()
    from .blender import ops_tour
    ops_tour.register_handlers()
    project_lock.register()
    machining.register()
    coolant.register()                       # after milling: the milled block's cut faces get the wet sheen too
    linkages.register()
    clash.register()
    from .blender import section
    section.register()                       # cutaways (task 0086): new materials of cut parts get wrapped
    hover.register()
    from .blender import waycover
    waycover.register()                      # task 0035: one-cover projects open with it in the list
    vessel_motion.register()
    from .blender import flex
    flex.register()                          # hoses and drag chains (task 0058): live shapes, clash hook
    from .blender import paths
    paths.register()                         # cables and paths (task 0078): live shapes, clash hook
    from .blender import spool
    spool.register()                         # drums and carousels (task 0080): clash hook, caches
    from .blender import tracks
    tracks.register()                        # tracks and belts (task 0079): clash hook, caches
    updates.register()
    from . import pccheck
    pccheck.register()                       # after updates: its Help entry goes under the update check
    from .blender import ops_house
    ops_house.register_menu()                # task 0114: File > Import > House Planner scene (.hpscene)
    from .blender import ops_import
    ops_import.register_menu()               # task 0117: File > Import > Mesh model (glTF, OBJ, FBX)


def unregister():
    import bpy

    from . import pccheck
    from .blender import clash, coolant, decals, handlers, hover, linkages, machining, project_lock, props, updates
    from .blender import ops_house
    ops_house.unregister_menu()
    from .blender import ops_import
    ops_import.unregister_menu()
    pccheck.unregister()
    updates.unregister()
    from .blender import section
    section.unregister()
    hover.unregister()
    from .blender import tracks
    tracks.unregister()
    from .blender import spool
    spool.unregister()
    from .blender import paths
    paths.unregister()
    from .blender import flex
    flex.unregister()
    from .blender import vessel_motion
    vessel_motion.unregister()
    clash.unregister()
    from .blender import waycover
    waycover.unregister()
    linkages.unregister()
    coolant.unregister()
    machining.unregister()
    project_lock.unregister()
    handlers.unregister()
    from .blender import ops_tour
    ops_tour.unregister_handlers()
    for cls in reversed(_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    decals.unregister()
    props.unregister()
