"""Real-app helper of ``ui_test_left.py`` (task 0278): the app started again in the same settings folder. Writes
which sections of the left panel are open (as the user left them before the restart) to $FR_LEFT_RESTART_OUT, then
quits. Not a test of its own: ``ui_test_left.py`` starts it and checks what it wrote."""

import json
import os

import bpy

OUT = os.environ.get("FR_LEFT_RESTART_OUT", "")
NAMES = ("FRESING_PT_favourites", "FRESING_PT_hub", "FRESING_PT_workspace", "FRESING_PT_lesson")
T = {"n": 0}


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def look():
    T["n"] += 1
    name = pkg()
    if name is None and T["n"] < 40:
        return 0.5
    data = {"pkg": name}
    try:
        import importlib
        panels = importlib.import_module(name + ".blender.panels")
        data["open"] = {n: panels.is_open(n) for n in NAMES}
        ui_left = importlib.import_module(name + ".blender.ui_left")
        data["store"] = ui_left.store()
        data["next_folded"] = ui_left.next_folded()
        data["favourites_poll"] = bool(bpy.types.FRESING_PT_favourites.poll(bpy.context))
    except Exception as exc:  # noqa: BLE001
        data["error"] = repr(exc)
    if OUT:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(data, f)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(look, first_interval=4.0, persistent=True)
