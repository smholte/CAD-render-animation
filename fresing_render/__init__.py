"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.2.42"

_modules = []


def _classes():
    from .blender import (ops_callouts, ops_cylinders, ops_decals, ops_gcode, ops_import, ops_linkages, ops_machining,
                          ops_main, ops_motion, ops_panels, ops_waycover, ops_rule_sets, ops_scene, ops_surroundings,
                          ops_video, prefs, ui, ui_callouts, ui_decals, ui_gcode, ui_machining, ui_motion, ui_video,
                          ui_waycover, updates)
    # 3 Looks > Logos & stickers (task 0024) right after Paint faces: sub-panels show in registration order
    looks = list(ui.CLASSES)
    at = looks.index(ui.FRESING_PT_faces) + 1
    looks[at:at] = ui_decals.PANELS
    # the update notice first: a panel registered first sits on top of the Fresing tab
    return (updates.CLASSES + prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ops_motion.CLASSES
            + ops_cylinders.CLASSES + ops_linkages.CLASSES + ops_panels.CLASSES + ops_rule_sets.CLASSES
            + ops_surroundings.CLASSES + ops_scene.CLASSES + ops_machining.CLASSES + ops_gcode.CLASSES
            + ops_waycover.CLASSES + ops_decals.CLASSES + ops_video.CLASSES + ops_callouts.CLASSES + tuple(looks)
            + ui_motion.CLASSES + ui_machining.CLASSES + ui_gcode.CLASSES + ui_waycover.CLASSES + ui_video.CLASSES
            + ui_callouts.CLASSES)


def register():
    import bpy

    from .blender import decals, handlers, linkages, machining, project_lock, props, updates
    props.register()
    decals.register()
    for cls in _classes():
        if issubclass(cls, bpy.types.Operator) and cls.__doc__ and "\n" in cls.__doc__:
            # the docstring is the tooltip: Blender keeps its line breaks, so a docstring wrapped in the
            # source would show a sentence broken in the middle
            cls.__doc__ = " ".join(cls.__doc__.split())
        bpy.utils.register_class(cls)
    handlers.register()
    project_lock.register()
    machining.register()
    linkages.register()
    updates.register()
    from . import pccheck
    pccheck.register()                       # after updates: its Help entry goes under the update check


def unregister():
    import bpy

    from . import pccheck
    from .blender import decals, handlers, linkages, machining, project_lock, props, updates
    pccheck.unregister()
    updates.unregister()
    linkages.unregister()
    machining.unregister()
    project_lock.unregister()
    handlers.unregister()
    for cls in reversed(_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    decals.unregister()
    props.unregister()
