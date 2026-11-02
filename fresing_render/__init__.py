"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.1.0"

_modules = []


def _get_modules():
    from .blender import ops_import, ops_main, prefs, props, ui
    return props, prefs, ops_import, ops_main, ui


def register():
    import bpy

    from .blender import handlers
    props, prefs, ops_import, ops_main, ui = _get_modules()
    props.register()
    for cls in prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ui.CLASSES:
        bpy.utils.register_class(cls)
    handlers.register()


def unregister():
    import bpy

    from .blender import handlers
    props, prefs, ops_import, ops_main, ui = _get_modules()
    handlers.unregister()
    for cls in reversed(prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ui.CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    props.unregister()
