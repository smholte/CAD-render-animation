# The app template as it was in version 0.2.10 (before the Help-menu entry for the user guide).
# Test data for task 0020: an in-app update must replace it with the current template.
"""Fresing Render application template.

Blender opens straight into a clean set-up for rendering CAD models:
an empty scene, millimetres, Cycles, and the Fresing side panel open.
"""

import bpy
from bpy.app.handlers import persistent


def _tidy_screens():
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.show_region_ui = True          # the side panel with the Fresing tab
                space.show_region_toolbar = False    # no modelling tools
                space.shading.type = "SOLID"
                space.shading.color_type = "MATERIAL"
                space.shading.light = "STUDIO"
                space.overlay.show_floor = True
                space.overlay.show_relationship_lines = False    # no dotted parent lines across the model
                space.clip_start = 0.01              # 10 mm..1 km: no flicker on touching CAD faces
                space.clip_end = 1000.0
            for region in area.regions:
                if region.type == "UI" and hasattr(region, "active_panel_category"):
                    try:
                        region.active_panel_category = "Fresing"
                    except (AttributeError, TypeError):
                        pass


@persistent
def _setup_new_file(_dummy=None):
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "MILLIMETERS"
    scene.view_settings.view_transform = "AgX"
    _tidy_screens()


@persistent
def _set_preferences(_dummy=None):
    prefs = bpy.context.preferences
    prefs.view.show_splash = True
    prefs.view.show_tooltips_python = False
    prefs.filepaths.use_relative_paths = True


def _enable_fresing_render() -> str:
    """Blender keeps a separate list of enabled add-ons for every app template, so the
    template switches the Fresing Render extension on itself (and keeps it in that list)."""
    import addon_utils
    prefs = bpy.context.preferences
    for mod in addon_utils.modules():
        name = mod.__name__
        if name == "fresing_render" or name.endswith(".fresing_render"):
            if name not in prefs.addons:
                addon_utils.enable(name, default_set=True, persistent=True)
            return name
    print("Fresing Render: the extension is not installed (run Install.bat again)")
    return ""


def _show_fresing_tab():
    """Open the side panel on the Fresing tab (the tab only exists once the extension is on)."""
    done = False
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type == "UI":
                    try:
                        region.active_panel_category = "Fresing"
                        done = True
                    except (AttributeError, TypeError, ValueError):
                        pass
    return None if done else 0.5            # timer: try again until the panel has been drawn


@persistent
def _after_load(_dummy=None):
    # runs once the start-up file is read and the extension system is ready
    # (too early in register(): the template's add-on list is set up after it)
    try:
        _enable_fresing_render()
    except Exception as exc:  # never stop Blender from starting
        print("Fresing Render: could not enable the extension:", exc)
    if not bpy.app.background and not bpy.data.filepath:     # a new project: start on the Fresing tab
        tries = {"n": 0}

        def _tab():
            tries["n"] += 1
            res = _show_fresing_tab()
            return None if res is None or tries["n"] > 20 else res

        bpy.app.timers.register(_tab, first_interval=0.3)


_HANDLERS = ((bpy.app.handlers.load_factory_startup_post, _setup_new_file),
             (bpy.app.handlers.load_factory_preferences_post, _set_preferences),
             (bpy.app.handlers.load_post, _after_load))


def register():
    for lst, fn in _HANDLERS:
        if fn not in lst:
            lst.append(fn)


def unregister():
    for lst, fn in _HANDLERS:
        while fn in lst:
            lst.remove(fn)
