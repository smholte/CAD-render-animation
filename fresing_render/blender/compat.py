"""Compatibility kit, the Blender side (task 0352; plain rules in ``core/compat.py``).

* **Load** (``_on_load``, put FIRST in ``load_post`` – again at every ``load_pre``, so a handler registered later
  cannot get in front): reads the stamps of the local scenes. A project from a newer app (format above ``FORMAT``) is
  marked "look only" (``STATE["newer"]``) and says so in plain words; otherwise the chain's steps it needs run in order,
  once for the file (none before the baseline), and the scenes are stamped with the format reached in memory – the
  chain stops at a failing step, and a save keeps that format so a fixed version tries again. ``register`` looks at
  the open file too (the app template switches the app on during a load, behind our place in ``load_post``).
* **Save** (``_before_save``, first in ``save_pre``): every local scene gets ``fr_format`` + ``fr_saved_by`` – also
  an automatic backup and the render queue's copy; a stamp is never lowered (a newer one stays, and makes the project
  look-only). While look-only, any existing file a save is about to write over (the "Save changes?" question when
  closing, Save As onto the original, a script) is first kept aside as "<name> (Fresing Render 0.2.X).blend" – a
  copy, else a hard link, else moved – unless this app wrote it a moment ago (``_after_save``): nothing is lost. Blender cannot cancel a save
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
    "failed": [],           # ... and the one that failed (the chain stops there)
    "held": {},             # scene name -> the format its chain reached when a step failed (a save keeps it)
    "aside": {},            # (path, size, mtime) of a file written over while look-only -> where it was kept
    "ours": set(),          # (path, size, mtime) of files this app wrote while look-only: never kept aside again
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


def _refresh() -> None:
    """A newer stamp in memory that no load saw (the app switched on during a load, a scene appended from a newer
    project): the project is look-only from now on."""
    if STATE["newer"] is not None:
        return
    found, by = project_format()
    if core.is_newer(found):
        STATE["newer"] = {"format": found, "saved_by": by, "path": bpy.data.filepath,
                          "note": core.newer_note(by, _version())}


def blocked(scene=None) -> str:
    """The plain reason a write must not happen ("" = it may): the open project is from a newer app."""
    try:
        _refresh()
    except Exception:  # noqa: BLE001
        pass
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
    """Run the chain ONCE for the file, from its lowest stamp: each step gets the local scenes that are below its
    ``to_format`` (two scenes may be at different numbers; objects, meshes and materials they share are one datablock,
    so a step runs once and touches each once). The chain stops at a failing step – the later steps need it –, the
    scenes are stamped with what they reached in memory (a save keeps that, ``STATE["held"]``), and a fixed version
    tries again. Returns (done, failed) step names."""
    fmt = core.FORMAT if fmt is None else fmt
    resolve = resolve or _resolve
    stamped = [(sc, stamp_of(sc)[0]) for sc in local_scenes()]
    stamped = [(sc, f) for sc, f in stamped if f is not None]
    if not stamped:
        return [], []
    todo = core.plan(min(f for _sc, f in stamped), steps, fmt, baseline, use_baseline=use_baseline)
    if not todo:
        return [], []

    def call(step):
        scenes = [sc for sc, f in stamped if f < step.to_format]
        resolve(step)(scenes)
    done, failed = core.run(todo, call)
    reached = todo[len(done) - 1].to_format if done else todo[0].from_format
    for sc, f in stamped:
        if f >= fmt:
            continue
        new = max(f, reached)
        stamp(sc, new)
        if new < fmt:
            STATE["held"][sc.name] = new
    return done, failed


def check_open(path: str = "") -> None:
    """What ``_on_load`` does, callable from tests: newer → look only; else the chain."""
    STATE["newer"] = None
    STATE["ran"], STATE["failed"] = [], []
    STATE["held"] = {}
    found, by = project_format()
    if core.is_newer(found):
        STATE["newer"] = {"format": found, "saved_by": by, "path": path or bpy.data.filepath,
                          "note": core.newer_note(by, _version())}
        _say(STATE["newer"]["note"])
        _tell_later()
        return
    STATE["ran"], STATE["failed"] = run_chain()


def data_readable() -> bool:
    """Blender's data can be read now: not while add-ons are switched on at start or in a load (task 0371: there
    ``bpy.data`` is a ``_RestrictData`` without ``filepath``, which printed "the project's format could not be read"
    twice at every start). Our ``load_post`` handler looks at the project once its data is there."""
    return isinstance(getattr(bpy, "data", None), bpy.types.BlendData)


@persistent
def _on_load(filepath=None, *_args):
    if not data_readable():
        return
    try:
        check_open(filepath if isinstance(filepath, str) else "")
    except Exception as exc:  # noqa: BLE001 - the project opens whatever happens here
        print(f"Fresing Render: the project's format could not be read: {exc}")


@persistent
def _before_load(*_args):
    _front(("load_post", "save_pre", "save_post"))   # stay first, whatever registered after us (not load_pre: it runs now)


@persistent
def _before_save(filepath=None, *_args):
    try:
        save_hook(filepath if isinstance(filepath, str) else "")
    except Exception as exc:  # noqa: BLE001 - never stop a save
        print(f"Fresing Render: the project's format stamp was not written: {exc}")


def save_hook(filepath: str) -> str:
    """Stamp the local scenes – never lower a stamp (a scene above ``FORMAT`` keeps its number, one the chain could
    not carry all the way keeps where it got) – and, while the project is look-only, keep any file about to be
    written over aside first. Returns the aside path ("" = none)."""
    _refresh()
    for sc in local_scenes():
        f, _b = stamp_of(sc)
        if f is not None and f > core.FORMAT:
            continue
        if sc.name in STATE["held"]:
            stamp(sc, STATE["held"][sc.name])
        elif STATE["newer"]:                   # a scene of ours beside newer data: the file as a whole is newer
            stamp(sc, STATE["newer"]["format"], STATE["newer"]["saved_by"])
        else:
            stamp(sc)
    st = STATE["newer"]
    target = filepath or bpy.data.filepath
    if not st or not target or not os.path.isfile(target):
        return ""
    key = _file_key(target) or (target, 0, 0)
    if key in STATE["aside"]:
        return STATE["aside"][key]
    if key in STATE["ours"]:                   # what this app itself wrote a moment ago: nothing newer in it
        return ""
    aside = core.aside_name(target, st["saved_by"])
    kept = _keep_aside(target, aside)
    if not kept:
        print(f"Fresing Render: {os.path.basename(target)} could not be kept aside before the save")
        return ""
    STATE["aside"][key] = aside
    _say(f"This project was saved by Fresing Render {st['saved_by']}: the file as it was is kept as "
         f"{os.path.basename(aside)}")
    return aside


def _keep_aside(target: str, aside: str) -> bool:
    """Copy the file aside; when that fails (disk full, a held file) a hard link (no space needed), and as the last
    way move it aside (Blender then writes a new file under the old name)."""
    for how in (shutil.copy2, os.link, os.replace):
        try:
            how(target, aside)
            return True
        except OSError as exc:
            print(f"Fresing Render: keeping {os.path.basename(target)} aside ({how.__name__}): {exc}")
    return False


def _file_key(path: str):
    try:
        info = os.stat(path)
    except OSError:
        return None
    return (os.path.normcase(os.path.realpath(path)), info.st_size, info.st_mtime_ns)


@persistent
def _after_save(filepath=None, *_args):
    if STATE["newer"] and isinstance(filepath, str):
        key = _file_key(filepath)
        if key:
            STATE["ours"].add(key)


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
        if pid in _SKIP_TYPES or core.not_a_choice(owner.bl_rna.identifier, pid):
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


def _groups_of(idb, type_) -> dict:
    out = {}
    for p in _group_props(type_):
        try:
            out[p] = _value(type_.bl_rna.properties[p], getattr(idb, p), p, 0)
        except Exception:  # noqa: BLE001
            pass
    return out


def _camera(cam) -> dict:
    return {"type": cam.type, "lens": core.round_value(cam.lens), "ortho": core.round_value(cam.ortho_scale),
            "sensor": core.round_value(cam.sensor_width), "fit": cam.sensor_fit,
            "clip": core.round_value([cam.clip_start, cam.clip_end]),
            "shift": core.round_value([cam.shift_x, cam.shift_y]),
            "dof": [bool(cam.dof.use_dof), core.round_value(cam.dof.aperture_fstop),
                    core.round_value(cam.dof.focus_distance),
                    cam.dof.focus_object.name if cam.dof.focus_object else None]}


def _light(light) -> dict:
    return {"type": light.type, "energy": core.round_value(light.energy), "color": core.round_value(list(light.color))}


def summary(scenes=None) -> dict:
    """The stored choices of the open project (the saved-data list, task 0352 step 1): every local scene's app
    settings and custom properties, each object's place, visibility, materials, app settings and custom properties,
    its mesh's app settings (decals on every copy), a camera's lens / clip / depth of field, a light's strength; the
    materials' app properties. No datablock counts: a later version may make more derived datablocks."""
    scenes = local_scenes() if scenes is None else scenes
    out = {"scenes": {}}
    for sc in scenes:
        s = {"frame": [sc.frame_start, sc.frame_end, sc.render.fps], "camera": sc.camera.name if sc.camera else None,
             "settings": _groups_of(sc, bpy.types.Scene), "props": _id_props(sc), "objects": {}}
        for ob in sorted(sc.objects, key=lambda o: o.name):
            row = {"type": ob.type, "parent": ob.parent.name if ob.parent else None,
                   "basis": _matrix(ob.matrix_basis), "hide_render": bool(ob.hide_render),
                   "data": ob.data.name if ob.data is not None else None,
                   "materials": [sl.material.name if sl.material else None for sl in ob.material_slots],
                   "props": _id_props(ob)}
            row.update(_groups_of(ob, bpy.types.Object))
            if ob.type == "MESH" and ob.data is not None:
                mesh = _groups_of(ob.data, bpy.types.Mesh)
                if any(mesh.values()):
                    row["mesh"] = mesh
            elif ob.type == "CAMERA":
                row["camera"] = _camera(ob.data)
            elif ob.type == "LIGHT":
                row["light"] = _light(ob.data)
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

_LISTS = (("load_post", _on_load), ("save_pre", _before_save), ("save_post", _after_save), ("load_pre", _before_load))


def _front(names=("load_post", "save_pre", "save_post", "load_pre")) -> None:
    for name, fn in _LISTS:
        if name not in names:
            continue
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
        lst.insert(0, fn)


def register():
    _front()
    if not data_readable():
        return                                 # the load that follows runs _on_load, first
    try:                                       # switched on with a project open (the app template does it during a
        check_open(bpy.data.filepath)          # load, behind our place in load_post): look at it now
    except Exception as exc:  # noqa: BLE001
        print(f"Fresing Render: the project's format could not be read: {exc}")


def unregister():
    for name, fn in _LISTS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
    STATE["newer"] = None
