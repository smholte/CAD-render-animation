"""Compatibility kit, the Blender side (task 0352; plain rules in ``core/compat.py``).

* **Load** (``_on_load``, put FIRST in ``load_post`` – again at every ``load_pre``, so a handler registered later
  cannot get in front): reads the stamps of the local scenes. A project from a newer app (format above ``FORMAT``) is
  marked "look only" (``STATE["newer"]``) and says so in plain words; otherwise the chain's steps it needs run in order
  (none before the baseline) and the scenes are stamped with ``FORMAT`` in memory.
* **Save** (``_before_save``, first in ``save_pre``): every local scene gets ``fr_format`` + ``fr_saved_by`` – also
  an automatic backup and the render queue's copy. A look-only project keeps its newer stamp, and when anything (the
  "Save changes?" question when closing, Update now, a script) writes over the newer file itself, the newer file is
  first copied aside as "<name> (Fresing Render 0.2.X).blend": nothing in it is lost. Blender cannot cancel a save
  from ``save_pre``; the app's Save (``project_name.FRESING_OT_save``) refuses before it starts (``refuse_save``).
* **Look only** also keeps out: automatic backups (``backups.wait_reason``), the render queue (``queue.start``) and a
  model update (``reimport.update_model``) – each asks ``blocked()``.
* ``summary`` / ``picture`` / ``read_picture``: the test projects' stored choices and small reference picture
  (``tools/make_compat_project.py``, ``tests/test_compat_projects.py``).
"""

from __future__ import annotations

import os
import shutil

import bpy
from bpy.app.handlers import persistent

from ..core import compat as core

STATE: dict = {
    "newer": None,          # {"format", "saved_by", "path", "note"} while a project from a newer app is open
    "ran": [],              # names of the chain steps the last load ran
    "failed": [],           # ... and of those that failed
    "aside": {},            # newer file's path -> where its copy was put aside this session
}


def _version() -> str:
    from .. import __version__
    return __version__


def local_scenes():
    """The scenes this file owns (a scene linked from a library is that library's)."""
    return [sc for sc in bpy.data.scenes if getattr(sc, "library", None) is None]


def stamp_of(scene):
    """(format or None, app version) of one scene."""
    try:
        return core.as_format(scene.get(core.STAMP)), str(scene.get(core.STAMP_APP, "") or "")
    except Exception:  # noqa: BLE001
        return None, ""


def project_format():
    """(format, saved_by) of the open file: the highest stamp of its local scenes; (None, "") = made before the kit."""
    best, by = None, ""
    for sc in local_scenes():
        f, b = stamp_of(sc)
        if f is not None and (best is None or f > best):
            best, by = f, b
    return best, by


def stamp(scene, fmt: int | None = None, saved_by: str | None = None) -> bool:
    """Put the stamp on one scene; False when it cannot be written (a linked scene)."""
    if getattr(scene, "library", None) is not None:
        return False
    try:
        scene[core.STAMP] = int(core.FORMAT if fmt is None else fmt)
        scene[core.STAMP_APP] = str(_version() if saved_by is None else saved_by)
        return True
    except Exception:  # noqa: BLE001 - e.g. a scene whose data cannot be written
        return False


def newer():
    """The look-only state ({"format", "saved_by", "path", "note"}) or None."""
    return STATE["newer"]


def blocked(scene=None) -> str:
    """The plain reason a write must not happen ("" = it may): the open project is from a newer app."""
    st = STATE["newer"]
    return st["note"] if st else ""


def _say(text: str) -> None:
    print("Fresing Render:", text)
    for sc in local_scenes():
        try:
            if getattr(sc, "fresing", None) is not None:
                sc.fresing.last_message = text
        except Exception:  # noqa: BLE001
            pass


def refuse_save(op=None) -> bool:
    """The app's Save: True (and the message) when the open project must not be saved over itself."""
    note = blocked()
    if not note:
        return False
    if op is not None:
        try:
            op.report({"WARNING"}, note)
        except Exception:  # noqa: BLE001
            pass
    _say(note)
    return True


def _resolve(step: core.Step):
    import importlib
    mod, _, fn = step.function.partition(":")
    return getattr(importlib.import_module(f"{__package__}.{mod}"), fn)


def run_chain(steps=None, *, use_baseline: bool = True, baseline=None, fmt: int | None = None,
              resolve=None) -> tuple[list, list]:
    """Run the chain on every local scene by its own stamp (two scenes may be at different numbers); a scene that
    went through it is stamped with ``fmt`` in memory, so it is never run twice. Returns (done, failed) names."""
    fmt = core.FORMAT if fmt is None else fmt
    resolve = resolve or _resolve
    done_all, failed_all = [], []
    for sc in local_scenes():
        found, _by = stamp_of(sc)
        todo = core.plan(found, steps, fmt, baseline, use_baseline=use_baseline)
        if not todo:
            continue
        done, failed = core.run(todo, lambda s, sc=sc: resolve(s)(sc))
        done_all += [f"{sc.name}: {n}" for n in done]
        failed_all += [f"{sc.name}: {n}" for n in failed]
        stamp(sc, fmt)
    return done_all, failed_all


def check_open(path: str = "") -> None:
    """What ``_on_load`` does, callable from tests: newer → look only; else the chain."""
    STATE["newer"] = None
    STATE["ran"], STATE["failed"] = [], []
    found, by = project_format()
    if core.is_newer(found):
        STATE["newer"] = {"format": found, "saved_by": by, "path": path or bpy.data.filepath,
                          "note": core.newer_note(by, _version())}
        _say(STATE["newer"]["note"])
        _tell_later()
        return
    STATE["ran"], STATE["failed"] = run_chain()


@persistent
def _on_load(filepath=None, *_args):
    try:
        check_open(filepath if isinstance(filepath, str) else "")
    except Exception as exc:  # noqa: BLE001 - the project opens whatever happens here
        print(f"Fresing Render: the project's format could not be read: {exc}")


@persistent
def _before_load(*_args):
    _front(("load_post", "save_pre"))          # stay first, whatever registered after us (not load_pre: it runs now)


@persistent
def _before_save(filepath=None, *_args):
    try:
        save_hook(filepath if isinstance(filepath, str) else "")
    except Exception as exc:  # noqa: BLE001 - never stop a save
        print(f"Fresing Render: the project's format stamp was not written: {exc}")


def save_hook(filepath: str) -> str:
    """Stamp the scenes (look only: keep the newer stamp) and, when the newer file itself is about to be written over,
    copy it aside first. Returns the aside path ("" = none)."""
    st = STATE["newer"]
    if not st:
        for sc in local_scenes():
            stamp(sc)
        return ""
    for sc in local_scenes():                  # never claim the older format for data a newer app wrote
        f, _b = stamp_of(sc)
        if f is None or f < st["format"]:
            stamp(sc, st["format"], st["saved_by"])
    target = filepath or bpy.data.filepath
    orig = st["path"]
    if not (target and orig and core.same_path(target, orig) and os.path.isfile(orig)):
        return ""
    if orig in STATE["aside"]:
        return STATE["aside"][orig]
    aside = core.aside_name(orig, st["saved_by"])
    try:
        shutil.copy2(orig, aside)
    except OSError as exc:
        print(f"Fresing Render: the newer project could not be copied aside before the save: {exc}")
        return ""
    STATE["aside"][orig] = aside
    _say(f"This project was saved by Fresing Render {st['saved_by']}: the file as that version saved it is kept as "
         f"{os.path.basename(aside)}")
    return aside


def _tell_later() -> None:
    """A small window with the message once the project is open (not in a background Blender)."""
    if bpy.app.background:
        return

    def show():
        note = blocked()
        if not note:
            return None
        try:
            wm = bpy.context.window_manager
            win = wm.windows[0] if wm and wm.windows else None
            if win is None:
                return None

            def draw(menu, _context):
                col = menu.layout.column()
                for part in note.split(". "):
                    col.label(text=part.rstrip(".") + ".")
            with bpy.context.temp_override(window=win, screen=win.screen):
                wm.popup_menu(draw, title="A project from a newer Fresing Render", icon="INFO")
        except Exception as exc:  # noqa: BLE001
            print(f"Fresing Render: {exc}")
        return None
    try:
        bpy.app.timers.register(show, first_interval=1.0)
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# the summary of stored choices, and the reference picture (test projects)
# ---------------------------------------------------------------------------

_SKIP_TYPES = {"rna_type"}


def _walk(owner, group: str = "", depth: int = 0):
    """A property group's stored settings as plain data (choices only: ``core.NOT_CHOICES`` left out)."""
    out = {}
    if owner is None or depth > 12:
        return out
    for prop in owner.bl_rna.properties:
        pid = prop.identifier
        if pid in _SKIP_TYPES or pid in core.NOT_CHOICES or f"{group}.{pid}" in core.NOT_CHOICES:
            continue
        if pid.endswith("_index"):                  # the selected row of a list: UI state
            continue
        if getattr(prop, "is_skip_save", False):
            continue
        if prop.is_readonly and prop.type not in ("POINTER", "COLLECTION"):
            continue                                # worked out by a getter, never stored
        try:
            val = getattr(owner, pid)
        except Exception:  # noqa: BLE001
            continue
        out[pid] = _value(prop, val, f"{group}.{pid}" if group else pid, depth)
    return out


def _value(prop, val, path: str, depth: int):
    t = prop.type
    if t == "POINTER":
        if val is None:
            return None
        if isinstance(val, bpy.types.ID):
            return val.name
        return _walk(val, path, depth + 1)
    if t == "COLLECTION":
        items = []
        for it in val:
            items.append(it.name if isinstance(it, bpy.types.ID) else _walk(it, path, depth + 1))
        return items
    if t == "ENUM" and getattr(prop, "is_enum_flag", False):
        return sorted(val)
    if t in ("FLOAT", "INT", "BOOLEAN") and getattr(prop, "array_length", 0):
        try:
            return core.round_value([x for x in val])
        except TypeError:
            return core.round_value([list(r) for r in val])
    return core.round_value(val)


def _group_props(type_):
    """The app's own property groups registered on a Blender type (Scene.fresing, Object.fresing_person …)."""
    return sorted(p.identifier for p in type_.bl_rna.properties
                  if p.identifier.startswith("fresing") and p.type in ("POINTER", "COLLECTION"))


def _id_props(idb) -> dict:
    """The app's plain custom properties ("fr_…") on a datablock: numbers and short texts by value, arrays and long
    texts by their length (big arrays are derived data – face starts, matrices of a bake)."""
    out = {}
    for k in sorted(idb.keys()):
        if not k.startswith("fr_") or k in (core.STAMP, core.STAMP_APP):
            continue
        v = idb[k]
        if isinstance(v, (bool, int, float)):
            out[k] = core.round_value(v)
        elif isinstance(v, str):
            out[k] = v if len(v) <= 200 else f"text:{len(v)}"
        else:
            try:
                out[k] = f"items:{len(v)}"
            except TypeError:
                out[k] = type(v).__name__
    return out


def _matrix(m) -> list:
    return [core.round_value(round(x, 5)) for row in m for x in row]


COUNTED = ("objects", "meshes", "materials", "cameras", "lights", "actions", "node_groups", "images", "collections",
           "curves", "worlds", "texts")


def summary(scenes=None) -> dict:
    """The stored choices of the open project (the saved-data list, task 0352 step 1): every local scene's app
    settings, each object's place and app settings, the materials' app properties, the datablock counts."""
    scenes = local_scenes() if scenes is None else scenes
    out = {"scenes": {}, "counts": {k: len(getattr(bpy.data, k)) for k in COUNTED}}
    for sc in scenes:
        s = {"frame": [sc.frame_start, sc.frame_end, sc.render.fps], "camera": sc.camera.name if sc.camera else None,
             "settings": {p: _value(sc.bl_rna.properties[p], getattr(sc, p), p, 0) for p in _group_props(bpy.types.Scene)},
             "props": _id_props(sc), "objects": {}}
        for ob in sorted(sc.objects, key=lambda o: o.name):
            row = {"type": ob.type, "parent": ob.parent.name if ob.parent else None,
                   "basis": _matrix(ob.matrix_basis), "hide_render": bool(ob.hide_render),
                   "data": ob.data.name if ob.data is not None else None,
                   "materials": [sl.material.name if sl.material else None for sl in ob.material_slots],
                   "props": _id_props(ob)}
            for p in _group_props(bpy.types.Object):
                try:
                    row[p] = _value(bpy.types.Object.bl_rna.properties[p], getattr(ob, p), p, 0)
                except Exception:  # noqa: BLE001
                    pass
            s["objects"][ob.name] = row
        out["scenes"][sc.name] = s
    out["materials"] = {m.name: _id_props(m) for m in sorted(bpy.data.materials, key=lambda m: m.name)
                        if m.library is None}
    return out


PICTURE_SIZE = (80, 60)


def picture(scene, path: str, samples: int = 4) -> bool:
    """A tiny Cycles picture on the processor of the scene's camera at its first frame (False: no camera). Changes
    render settings in memory only: call it after saving."""
    if scene.camera is None:
        return False
    r = scene.render
    r.engine = "CYCLES"
    r.resolution_x, r.resolution_y = PICTURE_SIZE
    r.resolution_percentage = 100
    r.film_transparent = False
    r.use_border = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_depth = "8"
    r.image_settings.color_mode = "RGB"
    c = scene.cycles
    c.device = "CPU"
    c.samples = samples
    c.use_denoising = False
    c.seed = 0
    c.use_adaptive_sampling = False
    try:
        scene.render.use_compositing = False
        scene.render.use_sequencer = False
    except AttributeError:
        pass
    scene.frame_set(scene.frame_start)
    r.filepath = path
    with bpy.context.temp_override(scene=scene):
        bpy.ops.render.render(write_still=True, scene=scene.name)
    return os.path.isfile(path)


def read_picture(path: str):
    """A PNG as numbers 0 … 1 (rows × columns × RGB)."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size
        px = np.empty(w * h * img.channels, dtype=np.float32)
        img.pixels.foreach_get(px)
        return px.reshape(h, w, img.channels)[:, :, :3].copy()
    finally:
        bpy.data.images.remove(img)


# ---------------------------------------------------------------------------
# registration: our handlers come first
# ---------------------------------------------------------------------------

_LISTS = (("load_post", _on_load), ("save_pre", _before_save), ("load_pre", _before_load))


def _front(names=("load_post", "save_pre", "load_pre")) -> None:
    for name, fn in _LISTS:
        if name not in names:
            continue
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
        lst.insert(0, fn)


def register():
    _front()


def unregister():
    for name, fn in _LISTS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
    STATE["newer"] = None
