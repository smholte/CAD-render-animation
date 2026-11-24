"""Fresing Render: photo-realistic renders of large STEP assemblies, built on Blender.

The package is split so the logic can be tested without Blender:
    core/      pure Python (fastener recognition, rules, materials, presets, templates)
    importer/  STEP reader (OpenCascade) that runs in its own process
    blender/   everything that talks to Blender (bpy)
"""

__version__ = "0.2.222"

_modules = []


def _classes():
    from .blender import (ops_callouts, ops_clash, ops_coolant, ops_cylinders, ops_decals, ops_doublearm, ops_fade, ops_gcode,
                          ops_import, ops_linkages, ops_machining, ops_main, ops_motion, ops_panels, ops_waycover,
                          ops_demo, ops_rule_sets, ops_scene, ops_surroundings, ops_toolpath, ops_tour, ops_video, prefs, ui, ui_callouts,
                          ui_clash, ui_coolant, ui_decals, ui_fade, ui_gcode, ui_header, ui_topbar, welcome, gpu_choice, editors, quiet, context_menu, ui_machining, ui_motion, ui_tour, ui_video,
                          ui_section, ui_waycover, updates)
    from .blender import ops_section                # task 0086: 3 Looks > Slice
    from .blender import ops_queue_schemes          # task 0074: 7 Render queue > Every paint scheme
    from .blender import ops_vessel_motion, ui_vessel_motion   # task 0085: 5 Scene & Render > Vessel motion
    from .blender import ops_vessel_work                # task 0154: 5 Scene & Render > Vessel at work
    from .blender import ops_flex, ui_flex          # task 0058: 4 Motion > Hoses and drag chains
    from .blender import ops_paths, ui_paths        # task 0078: 4 Motion > Cables and paths (after Hoses and drag chains)
    from .blender import ops_paths_sea              # task 0081: … > Into the sea, things on the cable
    from .blender import ops_drawn                  # task 0240: Draw hose / cable route / drag chain by clicking
    from .blender import ops_product_video       # task 0101: 6 Animation > Make a product video
    from .blender import ops_spool, ui_spool        # task 0080: 4 Motion > Drums and carousels (after Cables and paths)
    from .blender import ops_tracks, ui_tracks      # task 0079: 4 Motion > Tracks and belts (after Drums and carousels)
    from .blender import ops_web3d, ui_web3d     # task 0099: 5 Scene & Render > Web 3D model (after Turntable video)
    from .blender import ops_weather, ui_weather  # task 0109: 5 Scene & Render > Weather & time (after Vessel motion)
    from .blender import ops_house, ui_house      # task 0114: 5 Scene & Render > House from House Planner
    from .blender import ops_toolbox              # task 0217: Bake now / Not now of a job from the Toolbox folder
    from .blender import ops_people, ui_people    # task 0157: 6 Animation > People (before the Clash check)
    from .blender import ops_tc_person            # task 0156: the operator at a manual tool change
    from .blender import ops_lifting, ui_lifting  # task 0201: 8 Lifting plan
    from .blender import ops_lifting_rig  # task 0232: 8 Lifting plan > Rigging, Reeve the rope
    from .blender import ops_lifting_make, ui_lifting_make  # task 0204: 8 Lifting plan > Equipment > Make a crane…
    from .blender import ui_lesson                # task 0230: the Lesson panel (on top, under the test tour's)
    from .blender import ops_usage, ui_usage      # task 0181: the usage tracker, favourites bar, My usage
    from .blender import about                    # task 0206: About Fresing Render, the licence files
    from .blender import apptools                 # task 0212: Fresing > Tools and checks
    from .blender import ops_backups              # task 0246: Fresing > Restore a backup…, the start question
    from .blender import ui_left, ops_make        # task 0260: the left panel, the output windows of Make
    from .blender import ops_settings, ui_settings  # task 0271: the Fresing Settings window
    from .blender import ops_locations              # task 0272: Locations, Exports, Save to, set-up files
    from .blender import form_window                # task 0282: function windows (forms that stay open)
    from .blender import place                      # task 0307: G / R / S say why something cannot move
    from .blender import ops_place, ui_place        # task 0292: 2 Structure > Place, Remove…
    # 3 Looks > Logos & stickers (task 0024) right after Paint faces: sub-panels show in registration order
    looks = list(ui.CLASSES)
    at = looks.index(ui.FRESING_PT_structure) + 1
    looks[at:at] = ui_place.PANELS               # 2 Structure > Place (task 0292), before Clean-up
    at = looks.index(ui.FRESING_PT_faces) + 1
    looks[at:at] = ui_decals.PANELS
    at = looks.index(ui_decals.PANELS[-1]) + 1
    looks[at:at] = ui_fade.PANELS                # 3 Looks > X-ray look (task 0073)
    at = looks.index(ui_fade.PANELS[-1]) + 1
    looks[at:at] = ui_section.PANELS             # 3 Looks > Slice (task 0086)
    at = looks.index(ui.FRESING_PT_props) + 1
    looks[at:at] = ui_vessel_motion.CLASSES      # 5 Scene & Render > Vessel motion (task 0085), after Props
    at = looks.index(ui_vessel_motion.CLASSES[-1]) + 1
    looks[at:at] = ui_weather.CLASSES            # 5 Scene & Render > Weather & time (task 0109)
    at = looks.index(ui_weather.CLASSES[-1]) + 1
    looks[at:at] = ui_house.CLASSES              # 5 Scene & Render > House from House Planner (task 0114)
    # the update notice first: a panel registered first sits on top of the Fresing tab; then the test tour (task
    # 0059, only in a tour project)
    return (updates.CLASSES + ui_header.CLASSES + ui_topbar.CLASSES + editors.CLASSES + quiet.CLASSES + context_menu.CLASSES + place.CLASSES + ops_place.CLASSES + ui_place.CLASSES + welcome.CLASSES + gpu_choice.CLASSES + ui_tour.CLASSES + ui_lesson.CLASSES + ops_tour.CLASSES + prefs.CLASSES + ops_import.CLASSES + ops_main.CLASSES + ops_motion.CLASSES
            + ops_cylinders.CLASSES + ops_linkages.CLASSES + ops_panels.CLASSES + ops_rule_sets.CLASSES
            + ops_surroundings.CLASSES + ops_scene.CLASSES + ops_machining.CLASSES + ops_gcode.CLASSES
            + ops_doublearm.CLASSES + ops_coolant.CLASSES + ops_waycover.CLASSES + ops_flex.CLASSES + ops_drawn.CLASSES + ops_paths.CLASSES + ops_paths_sea.CLASSES + ops_spool.CLASSES + ops_tracks.CLASSES + ops_decals.CLASSES + ops_video.CLASSES
            + ops_callouts.CLASSES + ops_clash.CLASSES + ops_fade.CLASSES + ops_section.CLASSES + ui_section.CLASSES + ops_toolpath.CLASSES + ops_web3d.CLASSES + ops_product_video.CLASSES + tuple(looks) + ui_web3d.CLASSES + ui_motion.CLASSES + ui_machining.CLASSES
            + ui_gcode.CLASSES + ui_coolant.CLASSES + ui_waycover.CLASSES + ui_flex.CLASSES + ui_paths.CLASSES + ui_spool.CLASSES + ui_tracks.CLASSES + ui_video.CLASSES + ui_callouts.CLASSES
            + ops_people.CLASSES + ui_people.CLASSES + ui_clash.CLASSES + ui_fade.CLASSES + ops_queue_schemes.CLASSES + ops_vessel_motion.CLASSES + ops_vessel_work.CLASSES + ops_weather.CLASSES + ops_demo.CLASSES
            + ops_house.CLASSES + ops_toolbox.CLASSES + ops_tc_person.CLASSES + ops_lifting.CLASSES + ops_lifting_rig.CLASSES + ui_lifting.CLASSES
            + ui_lifting_make.CLASSES + ops_lifting_make.CLASSES
            + ops_usage.CLASSES + ui_usage.CLASSES + about.CLASSES + apptools.CLASSES + ops_backups.CLASSES
            + ui_left.CLASSES + ui_left.TOP + ui_left.HUB + ops_make.CLASSES + ops_settings.CLASSES + ui_settings.CLASSES
            + ops_locations.CLASSES + form_window.CLASSES)


def _all_classes():
    """Every class in the order it is registered (task 0062): the panels of the Fresing tab sorted the way the tab
    shows them – Make, tabs, then each section with its sub-panels in the order of ``core/places.py`` (a sub-panel
    shows in registration order) –, the panels of the left panel in their order (task 0260: Live preview and
    Build & play, update notice, Workspace, Learning hub, its stops, Lesson, Favourites, What's next), and each of
    them given the app's own title row and its ``poll`` (``panels.install``)."""
    import bpy

    from .blender import lock, ops_workspace, panels, ui_left, ui_top
    from .core import places
    classes = list(_classes())
    for extra in (ops_setup_classes(), ui_top.LEFT + ui_top.LEFT_END):
        classes += [c for c in extra if c not in classes]
    tab = [c for c in classes if isinstance(c, type) and issubclass(c, bpy.types.Panel)
           and getattr(c, "bl_region_type", "") == "UI" and getattr(c, "bl_category", "") == "Fresing"]
    left_order = ["FRESING_PT_left_quick", "FRESING_PT_update", "FRESING_PT_workspace", "FRESING_PT_hub",
                  "FRESING_PT_tour", "FRESING_PT_lesson", "FRESING_PT_favourites", "FRESING_PT_next"]
    left = sorted((c for c in classes if panels.is_left(c)),
                  key=lambda c: left_order.index(c.__name__) if c.__name__ in left_order else len(left_order))
    rest = [c for c in classes if c not in tab and c not in left]
    by_name = {c.__name__: c for c in tab}
    known = set(places.SECTIONS) | set(places.PLACES)
    top = [c for c in tab if c.__name__ not in known and not getattr(c, "bl_parent_id", "")]
    ordered = top + [c for c in ui_top.TOP if c not in top]

    def under(parent):
        for name in places.children(parent):
            if name in by_name:
                ordered.append(by_name[name])
                under(name)

    for sec in places.SECTIONS:
        if sec in by_name:
            ordered.append(by_name[sec])
            under(sec)
    ordered += [c for c in tab if c not in ordered]             # a panel core/places.py does not know yet: at the end
    late = [c for c in rest if c.__name__ in ("FRESING_PT_settings_window",   # task 0271: in the toolbar region too,
                                              "FRESING_PT_form_window")]      # (task 0282: a function window's page)
    rest = [c for c in rest if c not in late]                                 # after the left panel's parts
    out = (list(panels.CLASSES) + list(lock.CLASSES) + list(ops_workspace.CLASSES) + rest + left + ordered
           + list(ui_top.POPOVERS) + late)
    panels.install(out)
    return tuple(out)


def ops_setup_classes():
    """The Set-up window (ui_setup.py / ops_setup.py)."""
    try:
        from .blender import ops_setup, ops_setup_crane, ui_setup
    except ImportError:
        return ()
    return tuple(ops_setup.CLASSES) + tuple(ops_setup_crane.CLASSES) + tuple(ui_setup.CLASSES)


def register():
    import bpy

    from .blender import clash, coolant, decals, handlers, hover, linkages, machining, project_lock, props, updates
    from .blender import vessel_motion
    props.register()
    decals.register()
    from .blender import panels
    panels.register()                        # task 0062: the section tab's setting, before the panels that draw it
    for cls in _all_classes():
        if issubclass(cls, bpy.types.Operator) and cls.__doc__ and "\n" in cls.__doc__:
            # the docstring is the tooltip: Blender keeps its line breaks, so a docstring wrapped in the
            # source would show a sentence broken in the middle
            cls.__doc__ = " ".join(cls.__doc__.split())
        bpy.utils.register_class(cls)
    from .blender import settings_store
    settings_store.register()                # task 0283: every setting read from the app's own file, kept on change
    from .blender import locations
    locations.register()                     # task 0272: the folders per kind, set-ups, export places (after the settings)
    handlers.register()
    from .blender import lock, ui_top, workspaces
    from .blender import highlight
    highlight.register()                     # task 0062: what a lesson points with (nothing runs until one points)
    from .blender import lesson
    lesson.register()                        # task 0230: the lessons (nothing runs until one is started)
    lock.register()                          # task 0062: the Client view's lock (keys, new objects)
    workspaces.register()                    # the project's workspace after a load; the open sections at a save
    ui_top.register_header()                 # "Make" in the 3D view's header
    from .blender import ops_tour
    ops_tour.register_handlers()
    from .blender import ui_header
    ui_header.register_handlers()
    from .blender import ui_topbar, welcome
    ui_topbar.register_handlers()            # task 0199: the Fresing menu in the top bar
    from .blender import editors
    editors.register_handlers()              # task 0221: a 3D view drawn after Blender's column was closed / shown
    welcome.register_handlers()              # task 0199: the welcome and What's new at the start
    from .blender import gpu_choice
    gpu_choice.register_handlers()           # task 0296: the graphics card checked at the start, the calm notice
    from .blender import quiet
    quiet.register()                         # task 0241: the quiet window, decided at the start
    from .blender import context_menu
    context_menu.register()                  # task 0253: the right-click menu (switched with the quiet window)
    from .blender import ops_usage
    ops_usage.register()                     # task 0181: counting, the session, My usage in the Help menu
    from .blender import ops_settings
    ops_settings.register()                  # task 0271: the presence marks in the keymap (only real input counts)
    from .blender import form_window
    form_window.register()                   # task 0282: Esc / Return in a function window, close them at a load
    from .blender import about
    about.register()                         # task 0206: About Fresing Render in the Help menu
    project_lock.register()
    from .blender import ops_backups
    ops_backups.register()                   # task 0246: the backup timer, the start question
    machining.register()
    coolant.register()                       # after milling: the milled block's cut faces get the wet sheen too
    linkages.register()
    clash.register()
    from .blender import web3d
    web3d.register()                         # task 0189: the Web 3D panel's estimates kept until a change
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
    from .blender import people
    people.register()                        # people (task 0157): clash hook, the paths' overlay
    from .blender import tc_person
    tc_person.register()                     # the operator at a tool change (task 0156): clash hook
    from .blender import lifting
    lifting.register()                       # task 0201: the CoG symbol's draw handler, caches dropped on load
    from .blender import ops_setup_crane
    ops_setup_crane.register()               # task 0203: Set up a crane's name cache dropped on load
    from .blender import ui_lifting_make
    ui_lifting_make.register_props()         # task 0204: the Make a crane dialog's numbers (window manager)
    updates.register()
    from . import pccheck
    pccheck.register()                       # after updates: its Help entry goes under the update check
    try:
        from . import winexe
        winexe.output_to_file(bpy.app.binary_path)   # task 0177: a windowed program has no console to print to
    except Exception:  # noqa: BLE001 - never stop the app from starting
        pass
    try:
        from . import appicon
        appicon.startup()                    # task 0169: the Fresing icon on the windows, taskbar and shortcuts
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render (icon):", exc)
    from .blender import ops_house
    ops_house.register_menu()                # task 0114: File > Import > House Planner scene (.hpscene)
    from .blender import toolbox_inbox
    try:
        toolbox_inbox.register()             # task 0217: the Toolbox folder's manifest, the inbox's timer
    except Exception as exc:  # noqa: BLE001 - never stop the app from starting
        print("Fresing Render (Toolbox):", exc)
    from .blender import ops_import
    ops_import.register_menu()               # task 0117: File > Import > Mesh model (glTF, OBJ, FBX)


def unregister():
    import bpy

    from . import pccheck
    from .blender import clash, coolant, decals, handlers, hover, linkages, machining, project_lock, props, updates
    from .blender import ops_house, toolbox_inbox
    toolbox_inbox.unregister()
    from .blender import settings_store
    settings_store.unregister()              # task 0283: the last change written
    from .blender import locations
    locations.unregister()
    ops_house.unregister_menu()
    from .blender import ops_import
    ops_import.unregister_menu()
    pccheck.unregister()
    updates.unregister()
    from .blender import section
    section.unregister()
    hover.unregister()
    from .blender import people
    people.unregister()
    from .blender import tc_person
    tc_person.unregister()
    from .blender import lifting, ui_lifting
    lifting.unregister()
    from .blender import ops_setup_crane
    ops_setup_crane.unregister()
    ui_lifting.unregister_previews()
    from .blender import ops_lifting_make, ui_lifting_make
    ops_lifting_make.cancel_all()
    ui_lifting_make.unregister_props()
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
    from .blender import web3d
    web3d.unregister()
    from .blender import waycover
    waycover.unregister()
    linkages.unregister()
    coolant.unregister()
    machining.unregister()
    from .blender import ops_backups
    ops_backups.unregister()
    project_lock.unregister()
    handlers.unregister()
    from .blender import ops_tour
    ops_tour.unregister_handlers()
    from .blender import ui_header
    ui_header.unregister_handlers()
    from .blender import ui_topbar, welcome
    ui_topbar.unregister_handlers()
    from .blender import editors
    editors.unregister_handlers()
    welcome.unregister_handlers()
    from .blender import gpu_choice
    gpu_choice.unregister_handlers()
    from .blender import context_menu
    context_menu.unregister()                # task 0253: Blender's own right-click menu back
    from .blender import quiet
    quiet.unregister()                       # task 0241: Blender's own drawing back
    from .blender import form_window
    form_window.unregister()                 # task 0282: (after the classes go, its property groups go)
    from .blender import ops_settings
    ops_settings.unregister()
    from .blender import ops_usage
    ops_usage.unregister()
    from .blender import about
    about.unregister()
    from .blender import lock, panels, ui_top, workspaces
    ui_top.unregister_header()
    workspaces.unregister()
    lock.unregister()
    from .blender import lesson
    lesson.unregister()
    from .blender import highlight
    highlight.unregister()
    for cls in reversed(_all_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
    panels.unregister()
    decals.unregister()
    props.unregister()
