"""Real-app helper of ``ui_test_settings.py`` (task 0283): the app started again in the same settings folder, with
the app template. Writes the settings it started with (the names in $FR_SETTINGS_NAMES), the notes of the settings
file and whether the Fresing tab is there to $FR_SETTINGS_RESTART_OUT, then quits. Not a test of its own:
``ui_test_settings.py`` starts it and checks what it wrote."""

import json
import os

import bpy

OUT = os.environ.get("FR_SETTINGS_RESTART_OUT", "")
NAMES = json.loads(os.environ.get("FR_SETTINGS_NAMES", "[]"))
T = {"n": 0}


def pkg():
    import addon_utils
    return next((m.__name__ for m in addon_utils.modules() if m.__name__.endswith("fresing_render")), None)


def look():
    T["n"] += 1
    name = pkg()
    if name is None and T["n"] < 40:
        return 0.5
    data = {"pkg": name, "template": bpy.context.preferences.app_template}
    try:
        import importlib
        prefs = importlib.import_module(name + ".blender.prefs").get()
        store = importlib.import_module(name + ".blender.settings_store")
        values = {}
        for n in NAMES:
            v = getattr(prefs, n)
            values[n] = [round(float(x), 4) for x in v] if n == "lesson_colour" else v
        data["values"] = values
        data["notes"] = store.notes()
        data["path"] = store.path()
        data["started"] = hasattr(bpy.types, "FRESING_OT_settings")
        lock = importlib.import_module(name + ".blender.lock")          # task 0295: the changed key in the keymap
        data["measure_keys"] = [[kmi.type, kmi.ctrl == 1, kmi.alt == 1] for _km, kmi in lock._KEYMAPS
                                if kmi.idname == "fresing.measure"]
    except Exception as exc:  # noqa: BLE001
        data["error"] = repr(exc)
    if OUT:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(data, f)
    bpy.ops.wm.quit_blender()
    return None


bpy.app.timers.register(look, first_interval=4.0, persistent=True)
