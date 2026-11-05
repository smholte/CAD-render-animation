"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.2.13"

_modules = []


def _classes():
    from .blender import (ops_import, ops_main, ops_motion, ops_panels, ops_rule_sets, ops_surroundings, prefs, ui,
                          ui_motion)
    return (prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ops_motion.CLASSES + ops_panels.CLASSES
            + ops_rule_sets.CLASSES + ops_surroundings.CLASSES + ui.CLASSES + ui_motion.CLASSES)


def register():
    import bpy

    from .blender import handlers, project_lock, props
    props.register()
    for cls in _classes():
        if issubclass(cls, bpy.types.Operator) and cls.__doc__ and "\n" in cls.__doc__:
            # the docstring is the tooltip: Blender keeps its line breaks, so a docstring wrapped in the
            # source would show a sentence broken in the middle
            cls.__doc__ = " ".join(cls.__doc__.split())
        bpy.utils.register_class(cls)
    handlers.register()
    project_lock.register()


def unregister():
    import bpy

    from .blender import handlers, project_lock, props
    project_lock.unregister()
    handlers.unregister()
    for cls in reversed(_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    props.unregister()
