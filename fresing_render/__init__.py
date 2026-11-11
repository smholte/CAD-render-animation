"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.2.61"

_modules = []


def _classes():
    from .blender import (ops_callouts, ops_clash, ops_coolant, ops_cylinders, ops_decals, ops_doublearm, ops_fade, ops_gcode,
                          ops_import, ops_linkages, ops_machining, ops_main, ops_motion, ops_panels, ops_waycover,
                          ops_rule_sets, ops_scene, ops_surroundings, ops_toolpath, ops_tour, ops_video, prefs, ui, ui_callouts,
                          ui_clash, ui_coolant, ui_decals, ui_fade, ui_gcode, ui_machining, ui_motion, ui_tour, ui_video,
                          ui_waycover, updates)
    from .blender import ops_queue_schemes          # task 0074: 7 Render queue > Every paint scheme
    # 3 Looks > Logos & stickers (task 0024) right after Paint faces: sub-panels show in registration order
    looks = list(ui.CLASSES)
    at = looks.index(ui.FRESING_PT_faces) + 1
    looks[at:at] = ui_decals.PANELS
    at = looks.index(ui_decals.PANELS[-1]) + 1
    looks[at:at] = ui_fade.PANELS                # 3 Looks > X-ray look (task 0073)
    # the update notice first: a panel registered first sits on top of the Fresing tab; then the test tour (task
    # 0059, only in a tour project)
    return (updates.CLASSES + ui_tour.CLASSES + ops_tour.CLASSES + prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ops_motion.CLASSES
            + ops_cylinders.CLASSES + ops_linkages.CLASSES + ops_panels.CLASSES + ops_rule_sets.CLASSES
            + ops_surroundings.CLASSES + ops_scene.CLASSES + ops_machining.CLASSES + ops_gcode.CLASSES
            + ops_doublearm.CLASSES + ops_coolant.CLASSES + ops_waycover.CLASSES + ops_decals.CLASSES + ops_video.CLASSES
            + ops_callouts.CLASSES + ops_clash.CLASSES + ops_fade.CLASSES + ops_toolpath.CLASSES + tuple(looks) + ui_motion.CLASSES + ui_machining.CLASSES
            + ui_gcode.CLASSES + ui_coolant.CLASSES + ui_waycover.CLASSES + ui_video.CLASSES + ui_callouts.CLASSES
            + ui_clash.CLASSES + ui_fade.CLASSES + ops_queue_schemes.CLASSES)


def register():
    import bpy

    from .blender import clash, coolant, decals, handlers, linkages, machining, project_lock, props, updates
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
    from .blender import waycover
    waycover.register()                      # task 0035: one-cover projects open with it in the list
    updates.register()
    from . import pccheck
    pccheck.register()                       # after updates: its Help entry goes under the update check


def unregister():
    import bpy

    from . import pccheck
    from .blender import clash, coolant, decals, handlers, linkages, machining, project_lock, props, updates
    pccheck.unregister()
    updates.unregister()
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
