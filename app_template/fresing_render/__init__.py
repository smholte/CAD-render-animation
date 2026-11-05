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


# ---------------------------------------------------------------------------
# Help > Fresing Render user guide
# ---------------------------------------------------------------------------

GUIDE_FILE = "user_guide.html"


def guide_path() -> str:
    """The user guide shipped inside the installed extension (so it always matches the installed
    version); a copy in this template folder is the fallback. '' when there is none."""
    import addon_utils
    import os
    places = []
    for mod in addon_utils.modules():
        name = mod.__name__
        if name == "fresing_render" or name.endswith(".fresing_render"):
            places.append(os.path.join(os.path.dirname(mod.__file__), "guide", GUIDE_FILE))
    places.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "guide", GUIDE_FILE))
    return next((p for p in places if os.path.isfile(p)), "")


def open_path(path: str) -> None:
    """Open a file with the program Windows (or Linux) uses for it: the web browser for the guide."""
    import os
    import subprocess
    import sys
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606 - opening the user guide for the user
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


class FRESING_OT_user_guide(bpy.types.Operator):
    """Open the user guide in your web browser: what each section 1–7 is for and how to work through it,
    step by step, with pictures. Works without internet"""

    bl_idname = "fresing.user_guide"
    bl_label = "Fresing Render user guide"

    def execute(self, context):
        path = guide_path()
        if not path:
            self.report({"ERROR"}, "The user guide is missing: run Install.bat again")
            return {"CANCELLED"}
        try:
            open_path(path)
        except OSError as exc:
            self.report({"ERROR"}, f"Could not open the user guide ({exc}). It is here: {path}")
            return {"CANCELLED"}
        self.report({"INFO"}, "User guide opened in your web browser")
        return {"FINISHED"}


def _draw_help_menu(self, context):
    layout = self.layout
    layout.operator(FRESING_OT_user_guide.bl_idname, icon="HELP")
    layout.separator()


_HANDLERS = ((bpy.app.handlers.load_factory_startup_post, _setup_new_file),
             (bpy.app.handlers.load_factory_preferences_post, _set_preferences),
             (bpy.app.handlers.load_post, _after_load))


def register():
    for lst, fn in _HANDLERS:
        if fn not in lst:
            lst.append(fn)
    try:
        bpy.utils.register_class(FRESING_OT_user_guide)
    except ValueError:           # already registered (template loaded twice)
        pass
    bpy.types.TOPBAR_MT_help.remove(_draw_help_menu)
    bpy.types.TOPBAR_MT_help.prepend(_draw_help_menu)


def unregister():
    for lst, fn in _HANDLERS:
        while fn in lst:
            lst.remove(fn)
    bpy.types.TOPBAR_MT_help.remove(_draw_help_menu)
    try:
        bpy.utils.unregister_class(FRESING_OT_user_guide)
    except RuntimeError:
        pass
