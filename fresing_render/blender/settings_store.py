"""Every Fresing setting kept over a restart (task 0283).

Blender 5.2.3 forgets an extension's own preferences at every start while the app template is on (task 0278), so
the settings of ``prefs.py`` live in the app's own file ``<config>/fresing_settings.json`` (``core/settings_file.py``):

* **At the start** the file is read and its values are put into the registered preferences (``load``): everything
  that reads ``prefs.get().<name>`` keeps working, the Settings window included. The first start of this version
  finds no file and writes one with whatever Blender still had (e.g. a run without the template) – the move of the
  old values.
* **A change** – in the Settings window, by a button that remembers a choice (Live preview, the Settings tab, Play
  on …) or by a script – is written within a second by one timer (``sync``) that compares the ~25 values with what
  was written: nothing to save, no slowdown while a slider is dragged (one small write a second at most).
* The left panel's folds (``left_folded``, ``left_width``, ``next_folded``) stay in 0278's ``fresing_left.json``,
  together with each left section's fold, which is no preference (``ui_left.store``); the editors' column stays in
  ``fresing_layout.json``. They are left out here so each value has one file.

Nothing is read or written in a background Blender (queue, PC check, self-test, kit) unless ``FRESING_SETTINGS_FILE``
names a file (tests).
"""

from __future__ import annotations

import os

import bpy

from ..core import settings_file as sf

ENV = "FRESING_SETTINGS_FILE"
ELSEWHERE = ("left_folded", "left_width", "next_folded")     # kept in fresing_left.json (task 0278)
TICK = 1.0

_S: dict = {"loaded": False, "written": None, "extra": {}, "notes": [], "spec": None}


def path() -> str:
    return os.environ.get(ENV) or os.path.join(bpy.utils.user_resource("CONFIG"), sf.FILE_NAME)


def usable() -> bool:
    return bool(os.environ.get(ENV)) or not bpy.app.background


def _prefs():
    from . import prefs
    try:
        return prefs.get()
    except Exception:  # noqa: BLE001 - while Blender starts or quits
        return None


def spec() -> dict:
    """{name: Kind} of every setting of ``prefs.FRESING_AP_prefs``, read from the registered properties."""
    if _S["spec"] is None:
        from . import prefs
        out = {}
        for prop in prefs.FRESING_AP_prefs.bl_rna.properties:
            name = prop.identifier
            if name in ("rna_type", "bl_idname") or name in ELSEWHERE or prop.is_readonly:
                continue
            t = prop.type
            if t == "BOOLEAN":
                out[name] = sf.Kind("bool", bool(prop.default))
            elif t == "INT":
                out[name] = sf.Kind("int", int(prop.default), prop.hard_min, prop.hard_max)
            elif t == "FLOAT" and prop.array_length:
                out[name] = sf.Kind("colour", tuple(round(float(x), 6) for x in prop.default_array),
                                    prop.hard_min, prop.hard_max, size=prop.array_length)
            elif t == "FLOAT":
                out[name] = sf.Kind("float", float(prop.default), prop.hard_min, prop.hard_max)
            elif t == "STRING":
                out[name] = sf.Kind("str", str(prop.default))
            elif t == "ENUM":
                out[name] = sf.Kind("enum", prop.default, items=tuple(i.identifier for i in prop.enum_items))
        _S["spec"] = out
    return _S["spec"]


def current(p) -> dict:
    out = {}
    for name, kind in spec().items():
        v = getattr(p, name)
        out[name] = tuple(round(float(x), 6) for x in v) if kind.type == "colour" else v
    return out


def notes() -> list:
    """Plain notes from the last read (a damaged file, a value left out); shown in Settings > General."""
    return list(_S["notes"])


def load(p=None) -> bool:
    """Read the file into the preferences (or, with no file yet, write one from what Blender has). True when done."""
    p = p or _prefs()
    if p is None or not usable():
        return False
    res = sf.read(path(), spec())
    _S["notes"] = list(res.notes)
    _S["extra"] = dict(res.extra)
    for note in res.notes:
        print("Fresing Render:", note, f"({res.detail})" if res.detail else "")
    if res.found:
        for name, kind in spec().items():
            want = res.values.get(name, kind.default)
            try:
                if not sf.same(current_one(p, name, kind), want):
                    setattr(p, name, want)
            except Exception as exc:  # noqa: BLE001 - one odd value never stops the rest
                print(f"Fresing Render: setting {name} not restored:", exc)
    _S["loaded"] = True
    _S["written"] = None if (not res.found or res.notes) else current(p)
    save(p)                                   # no file yet / a damaged one: write what is in use now
    return True


def current_one(p, name, kind):
    v = getattr(p, name)
    return tuple(round(float(x), 6) for x in v) if kind.type == "colour" else v


def save(p=None) -> bool:
    """Write the file when a value differs from what was last written. True when it wrote."""
    p = p or _prefs()
    if p is None or not usable() or not _S["loaded"]:
        return False
    now = current(p)
    if _S["written"] is not None and all(sf.same(now[n], _S["written"].get(n)) for n in now):
        return False
    try:
        sf.write(path(), now, spec(), _S["extra"])
    except (OSError, ValueError) as exc:
        print("Fresing Render: could not save the settings:", exc)
        return False
    _S["written"] = now
    return True


def sync():
    """The timer: load once, then save what changed."""
    if not usable():
        return None
    try:
        if not _S["loaded"]:
            load()
        else:
            save()
    except Exception as exc:  # noqa: BLE001 - a timer that raises is dropped by Blender
        print("Fresing Render: settings not kept:", exc)
    return TICK


def forget() -> None:
    """Tests: as a new start (nothing loaded, nothing written)."""
    _S.update(loaded=False, written=None, extra={}, notes=[], spec=None)


def _at_exit() -> None:
    try:
        save()
    except Exception:  # noqa: BLE001 - Blender is going away
        pass


def register() -> None:
    forget()
    if not usable():
        return
    try:
        load()                                # as early as possible: start-up code reads the settings
    except Exception as exc:  # noqa: BLE001
        print("Fresing Render: settings not read yet:", exc)
    if not bpy.app.timers.is_registered(sync):
        bpy.app.timers.register(sync, first_interval=0.2, persistent=True)
    import atexit
    atexit.register(_at_exit)


def unregister() -> None:
    _at_exit()
    if bpy.app.timers.is_registered(sync):
        bpy.app.timers.unregister(sync)
    import atexit
    atexit.unregister(_at_exit)
