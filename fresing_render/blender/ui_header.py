"""The app's window stays the app's window (task 0198).

* Every project the app opens (File > Open, a test tour set, the demo, Revert, an older version's project) gets the
  side panel shown on the Fresing tab and Blender's toolbar folded. Nothing else of the project's own view changes
  (camera, shading, sizes, the far clip of task 0193).
* Live preview keeps the user's last choice (stored in the extension's preferences) through the test tour and the
  demo; a project of his own opens as it was saved.
* Task 0221: Blender's Outliner and Properties column follows the user's choice (``editors.py``, hidden by default).
* A "Fresing" button at the right of the 3D view's header brings a hidden side panel back (``fresing.show_panel``).
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

from .panels import side_window

TAB = "Fresing"


# ---------------------------------------------------------------------------
# finding the views
# ---------------------------------------------------------------------------

def _view_areas():
    """The 3D views of the app's windows – not the Set-up window (task 0062): its side panel shows the tab
    "Set-up" and must keep it when a project opens."""
    wm = bpy.context.window_manager
    for win in wm.windows:
        if side_window(win):           # task 0260: the output windows of Make too
            continue
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                yield win, area


def _ui_region(area):
    return next((r for r in area.regions if r.type == "UI"), None)


def panel_visible(area) -> bool:
    """True when this 3D view shows the side panel on the Fresing tab."""
    space = area.spaces.active
    if not getattr(space, "show_region_ui", False):
        return False
    region = _ui_region(area)
    if region is None:
        return True
    try:
        return region.active_panel_category == TAB
    except (AttributeError, TypeError):
        return True


def show_panel(area) -> bool:
    """Show the side panel of a 3D view and open its Fresing tab. False when the tab could not be chosen yet."""
    space = area.spaces.active
    space.show_region_ui = True
    if not space.show_region_toolbar:         # task 0260: the left panel comes back with it
        space.show_region_toolbar = True
    region = _ui_region(area)
    ok = False
    if region is not None:
        try:
            region.active_panel_category = TAB
            ok = True
        except (AttributeError, TypeError, ValueError):
            pass
    area.tag_redraw()
    return ok


# ---------------------------------------------------------------------------
# Live preview
# ---------------------------------------------------------------------------

def apply_preview(scene, space, on: bool) -> None:
    """Live preview on or off in one 3D view, with the draft settings of the button."""
    from . import render, world
    if on:
        render.apply_quality(scene, "draft", scene.fresing.use_gpu)
        world.apply(scene, scene.fresing)
        scene.cycles.preview_samples = 64
        scene.cycles.use_preview_denoising = True
    space.shading.type = "RENDERED" if on else "SOLID"


def remember_preview(on: bool) -> None:
    from . import prefs
    p = prefs.get()
    if p is not None and p.live_preview != on:
        p.live_preview = on


def _restore_preview() -> None:
    """A test tour set or the demo opens with Live preview as the user last chose it."""
    from . import demo, prefs, tour
    scene = bpy.context.scene
    if scene is None or not (tour.is_tour(scene) or demo.is_demo(scene)):
        return
    p = prefs.get()
    if p is None:
        return
    for _win, area in _view_areas():
        space = area.spaces.active
        if (space.shading.type == "RENDERED") != bool(p.live_preview):
            try:
                apply_preview(scene, space, bool(p.live_preview))
            except Exception as exc:  # noqa: BLE001 - never break loading over the preview
                print("Fresing Render: Live preview not restored:", exc)
        break


# ---------------------------------------------------------------------------
# the layout of every load
# ---------------------------------------------------------------------------

def put_layout_right() -> bool:
    """Side panel shown on the Fresing tab and the left panel at its width (task 0260; before it: the toolbar folded),
    in every 3D view. True when every tab was set."""
    from . import editors
    if not editors.settled():             # task 0221: an area was just closed beside it – after the next draw
        return False
    from . import ui_left
    done = True
    for _win, area in _view_areas():
        done = ui_left.ensure(area) and done      # task 0260: the left panel (the toolbar region) shown, its width
        done = show_panel(area) and done
    return done


@persistent
def _on_load(_dummy=None):
    if bpy.app.background:
        return
    try:
        put_layout_right()
        _restore_preview()
    except Exception as exc:  # noqa: BLE001 - never break loading
        print("Fresing Render: layout not tidied:", exc)
    try:                                   # task 0221: Blender's right-hand column as the user chose (hidden)
        from . import editors
        editors.on_load()
    except Exception as exc:  # noqa: BLE001 - never break loading
        print("Fresing Render: Blender's editors not tidied:", exc)
    try:                                   # task 0062: a Set-up window saved with the project is back on its tab
        from . import ops_setup
        ops_setup.restore_tabs()
    except Exception:  # noqa: BLE001 - no Set-up window code, or none open
        pass
    tries = {"n": 0}

    def _tab():                       # the side panel's region exists only after the first redraw
        tries["n"] += 1
        try:
            return None if put_layout_right() or tries["n"] > 20 else 0.3
        except Exception:  # noqa: BLE001
            return None

    bpy.app.timers.register(_tab, first_interval=0.3)


# ---------------------------------------------------------------------------
# the button and the operator
# ---------------------------------------------------------------------------

class FRESING_OT_show_panel(bpy.types.Operator):
    """Shows the Fresing side panel again (all the steps 1–8) when it is hidden or another tab is open.
    Same as View > Sidebar, then the Fresing tab"""

    bl_idname = "fresing.show_panel"
    bl_label = "Show the Fresing panel"

    def execute(self, context):
        area = context.area if context.area and context.area.type == "VIEW_3D" else None
        if area is None:
            area = next((a for _w, a in _view_areas()), None)
        if area is None:
            self.report({"WARNING"}, "There is no 3D view in this window: pick a workspace with one "
                                     "(Layout, at the top)")
            return {"CANCELLED"}
        show_panel(area)
        return {"FINISHED"}


def _draw_header(self, context):
    area = context.area
    if area is None or area.type != "VIEW_3D" or (panel_visible(area) and area.spaces.active.show_region_toolbar):
        return
    self.layout.operator("fresing.show_panel", text="Fresing", icon="PREFERENCES")


CLASSES = (FRESING_OT_show_panel,)


def register_handlers():
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    bpy.types.VIEW3D_HT_header.remove(_draw_header)
    bpy.types.VIEW3D_HT_header.append(_draw_header)


def unregister_handlers():
    while _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    bpy.types.VIEW3D_HT_header.remove(_draw_header)
