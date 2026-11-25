"""The material picker (task 0273) – Blender side: the entries (built-in, own / department / company, this project's
copies), their pictures as previews, this project's short list, using an entry for a group, saving a group's look or
a Blender material as an own material, and making pictures in a background Blender.

``core/material_files.py`` has the file format and the filters; the window is ``ops_material_picker.py`` +
``ui_material_picker.py``; the short list in 3 Looks' group box is ``ui_material_picker.draw_short_list``.

**Own materials are read in a helper thread** (``refresh_own``): the Materials folders of Fresing Settings >
Locations (task 0272) – a folder on a server that does not answer is never waited for (``locations.folders`` gives
only what can be reached); the window shows the last list until the new one comes.

**Using an entry** (``apply``) writes the entry's settings into the group's own fields at once (ID properties: one
rebuild of its material, not one per field) and keeps a copy of an own material in the project
(``project_materials``): the project renders on a PC without the material's folder. A Blender material is appended
("FRM <name>", fake user), never linked – a link would break on a PC without the folder.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import threading
import time

import bpy

from ..core import finishes as fin_core
from ..core import material_files as F
from ..core import materials_lib as ML

KIND = "materials"                     # the kind of folder in Fresing Settings > Locations (task 0272)
BADGE_PROJECT = "This project"
SOURCE_LEVEL = {"company": "company", "department": "department", "mine": "mine"}
OWN_TTL = 30.0                         # seconds a read of the Materials folders is used before it is read again
RUNNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "material_picture_runner.py")
PACKAGE = __package__.rsplit(".", 1)[0]
PACKAGE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHIP = 0.34                            # the colour chip: this share of the picture's side, in its lower right corner

_S: dict = {"previews": None, "icons": {}, "chips": {}, "chip_todo": [], "own": [], "own_time": -1e9,
            "own_gen": None, "own_busy": False, "own_result": None, "fresh": [], "jobs": [], "project": {}, "swatches": {}}


# ---------------------------------------------------------------------------------------------------------------------
# pictures

def previews():
    if _S["previews"] is None:
        from bpy.utils import previews as pv
        _S["previews"] = pv.new()
    return _S["previews"]


def _stamp(path: str) -> str:
    try:
        st = os.stat(path)
        return f"{path}|{st.st_mtime_ns}|{st.st_size}"
    except OSError:
        return ""


def _swatch_icon(rgb) -> int:
    """A plain square of a colour (an entry without a picture)."""
    rgb = tuple(round(float(c), 3) for c in (rgb or (0.6, 0.6, 0.6)))
    name = "swatch|%.3f|%.3f|%.3f" % rgb
    pc = previews()
    if name in pc:
        return pc[name].icon_id
    import numpy as np
    n = 64
    px = np.empty((n, n, 4), np.float32)
    px[..., :3] = rgb
    px[..., 3] = 1.0
    px[:3], px[-3:], px[:, :3], px[:, -3:] = 0.5, 0.5, 0.5, 0.5          # a thin frame
    px[..., 3] = 1.0
    p = pc.new(name)
    p.image_size = (n, n)
    p.image_pixels_float.foreach_set(px.ravel())
    return p.icon_id


def _rgb_of_entry(e) -> tuple:
    if e.is_blend:
        return (0.55, 0.55, 0.56)                     # its look is in its own file: a neutral grey until it is pictured
    rgb = F.rgb_of(e.changes.get("color", "")) if e.changes.get("color") else None
    if rgb:
        return rgb
    spec = ML.get(e.base)
    return F.rgb_of(F.PICTURE_COLOURS.get(e.base, F.DEFAULT_PICTURE_COLOUR)) if spec.get("needs_color") \
        else tuple(spec.get("base_color", (0.6, 0.6, 0.6)))


def icon(e) -> int:
    """The icon of an entry's picture (loaded once; again when the file changed), a plain swatch without one."""
    stamp = _stamp(e.picture) if e.picture else ""
    if not stamp:
        return _swatch_icon(_rgb_of_entry(e))
    pc = previews()
    if stamp not in pc:
        old = _S["icons"].get(e.picture)
        if old and old in pc:
            del pc[old]
        pc.load(stamp, e.picture, "IMAGE")
        _S["icons"][e.picture] = stamp
    return pc[stamp].icon_id


def chip_icon(e, colour: str) -> int:
    """The entry's picture with a chip of ``colour`` in its corner (an entry that takes the group's colour). Made a
    few at a time on a timer: until then the plain picture."""
    rgb = F.rgb_of(colour) if colour else None
    if not e.takes_colour or rgb is None or not e.picture:
        return icon(e)
    stamp = _stamp(e.picture)
    key = f"chip|{stamp}|{colour.strip().upper()}"
    pc = previews()
    if key in pc:
        return pc[key].icon_id
    if key not in [k for k, _p, _c in _S["chip_todo"]]:
        _S["chip_todo"].append((key, e, rgb))
        if not bpy.app.timers.is_registered(_make_chips):
            bpy.app.timers.register(_make_chips, first_interval=0.01)
    return icon(e)


def _make_chips():
    """Draw up to four chips, then come back (a picture is decoded on its first read: ~10–80 ms each)."""
    import numpy as np
    pc = previews()
    t0 = time.monotonic()
    while _S["chip_todo"] and time.monotonic() - t0 < 0.05:
        key, e, rgb = _S["chip_todo"].pop(0)
        try:
            src = pc[_S["icons"].get(e.picture) or ""] if _S["icons"].get(e.picture) in pc else None
            if src is None:
                icon(e)
                src = pc[_S["icons"][e.picture]]
            w, h = src.image_size
            if not w or not h:
                continue
            px = np.empty(w * h * 4, np.float32)
            src.image_pixels_float.foreach_get(px)
            px = px.reshape(h, w, 4)
            n = max(8, int(min(w, h) * CHIP))
            edge = max(2, n // 12)
            px[:n, w - n:, :3] = 1.0                          # rows go from the bottom: the lower right corner
            px[edge:n - edge, w - n + edge:w - edge, :3] = rgb
            px[:n, w - n:, 3] = 1.0
            p = pc.new(key)
            p.image_size = (w, h)
            p.image_pixels_float.foreach_set(px.ravel())
            _S["chips"][key] = p.icon_id
        except Exception as exc:  # noqa: BLE001 - the plain picture stays
            print("Fresing Render: colour chip not drawn:", exc)
    redraw()
    return 0.02 if _S["chip_todo"] else None


def redraw() -> None:
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        try:
            for area in win.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
        except (AttributeError, ReferenceError):
            continue


# ---------------------------------------------------------------------------------------------------------------------
# the entries

def folders() -> list:
    """[(path, source, badge)] of the Materials folders that can be read now."""
    from . import locations
    out, seen = [], []
    try:
        locs = locations.folders(KIND)
    except Exception as exc:  # noqa: BLE001 - no locations: no own materials
        print("Fresing Render: the Materials folders were not read:", exc)
        return out
    from ..core import locations as L
    for loc in locs:
        if not loc.reach or any(L.same_path(loc.path, p) for p in seen):
            continue
        seen.append(loc.path)
        out.append((loc.path, SOURCE_LEVEL.get(loc.level, "mine"), loc.badge))
    return out


def _read(dirs) -> list:
    out = []
    for path, source, badge in dirs:
        out += F.list_folder(path, source, badge)
    return F.unique_keys(out)


def refresh_own(force: bool = False, wait: bool = False) -> None:
    """Read the Materials folders again in a helper thread (``wait``: here and now – tests, a save)."""
    from . import locations
    gen = locations.generation()
    fresh = time.monotonic() - _S["own_time"] < OWN_TTL and _S["own_gen"] == gen
    if (fresh and not force) or (_S["own_busy"] and not wait):
        return
    dirs = folders()
    _S["own_gen"] = gen
    _S["own_time"] = time.monotonic()
    if wait or bpy.app.background:
        got = _read(dirs)
        have = {e.folder for e in got}
        _S["own"] = F.unique_keys(got + [e for e in _S["fresh"] if e.folder not in have and os.path.isdir(e.folder)])
        _S["fresh"] = []
        return
    _S["own_busy"] = True

    def work():
        try:
            _S["own_result"] = _read(dirs)
        except Exception as exc:  # noqa: BLE001
            print("Fresing Render: own materials not read:", exc)
            _S["own_result"] = None
        finally:
            _S["own_busy"] = False

    threading.Thread(target=work, daemon=True).start()
    if not bpy.app.timers.is_registered(_take_own):
        bpy.app.timers.register(_take_own, first_interval=0.1)


def _take_own():
    if _S["own_busy"]:
        return 0.1
    if _S["own_result"] is not None:
        got = _S["own_result"]
        have = {e.folder for e in got}
        # a material saved while this read was under way: kept (the read may have looked before it was there)
        _S["own"] = F.unique_keys(got + [e for e in _S["fresh"] if e.folder not in have])
        _S["fresh"] = [e for e in _S["fresh"] if e.folder not in have]
        _S["own_result"] = None
        redraw()
    return None


def own_entries() -> list:
    refresh_own()
    return list(_S["own"])


def project_entries(scene) -> list:
    """The project's copies of own materials (what renders when their folder is not there)."""
    out = []
    for pm in scene.fresing.project_materials:
        if not pm.data:
            continue
        hit = _S["project"].get(pm.data)
        if hit is None:
            try:
                data = json.loads(pm.data)
            except (ValueError, RecursionError, TypeError):
                data = None
            hit = F.entry_from_data(data, "project", BADGE_PROJECT)
            if len(_S["project"]) > 500:
                _S["project"].clear()
            _S["project"][pm.data] = hit
        out.append(hit)
    return out


def all_entries(scene) -> list:
    return F.merge(F.builtin_entries(), own_entries(), project_entries(scene))


def find(scene, key: str):
    """The entry of a key: a built-in, an own material in a folder, else the project's copy (None: unknown)."""
    if not key:
        return None
    if not key.startswith("own:"):
        return F.builtin(key)
    for e in _S["own"]:
        if e.key == key and e.ok:
            return e
    return next((e for e in project_entries(scene) if e.key == key), None)


def group_key(g) -> str:
    """The entry a group shows: the one it got from the picker, else the built-in of its material (and colour)."""
    if g.mat_key:
        return g.mat_key
    e = F.builtin_for(g.material, g.color)
    return e.key if e is not None else ""


def material_changed(g) -> None:
    """The group's Material drop-down changed: the link to an entry of another library material ends."""
    scene = g.id_data
    e = find(scene, g.mat_key)
    if e is None or F.values_of(e)["material"] != g.material:
        g["mat_key"] = ""


def current_group(context):
    s = context.scene.fresing if context is not None and context.scene is not None else None
    if s is None or not (0 <= s.groups_index < len(s.groups)):
        return None
    return s.groups[s.groups_index]


# ---------------------------------------------------------------------------------------------------------------------
# this project's materials

def _pm(scene, key: str, make: bool = True):
    pms = scene.fresing.project_materials
    pm = pms.get(key)
    if pm is None and make:
        pm = pms.add()
        pm.name = key
    return pm


def remember(scene, e, listed: bool | None = None):
    """Keep an entry in the project (an own material: its whole file; a Blender material: appended)."""
    pm = _pm(scene, e.key)
    pm.title = F.storable(e.name)
    if e.key.startswith("own:") and e.data:
        try:
            text = json.dumps(e.data, ensure_ascii=True, sort_keys=True)    # ASCII: always a storable text
        except (ValueError, TypeError, RecursionError):
            text = ""
        if pm.data != text:
            pm.data = text
    if e.is_blend and e.blend and os.path.isfile(e.blend):
        try:
            mat = append_blend(e)
        except (OSError, RuntimeError) as exc:
            raise ValueError(f"'{e.name}' could not be taken from its Blender file ({exc})") from exc
        if mat is not None:
            pm.blend_mat = mat.name
    if listed is not None:
        pm.listed = listed
    return pm


def append_blend(e):
    """The entry's Blender material appended into the project as "FRM <name>" (again when its file changed)."""
    stamp = _stamp(e.blend)
    for mat in bpy.data.materials:
        if mat.get("fr_own_key") == e.key and mat.get("fr_own_stamp") == stamp and mat.get("fr_material") is None:
            return mat
    from . import material_pictures
    mat = material_pictures.blend_material(e.blend, e.blend_material)
    if mat is None:
        return None
    for old in [m for m in bpy.data.materials if m.get("fr_own_key") == e.key and m != mat
                and m.get("fr_material") is None]:
        old.use_fake_user = False
        if old.users == 0:
            bpy.data.materials.remove(old)
    mat["fr_own_key"] = e.key
    mat["fr_own_stamp"] = stamp
    mat.use_fake_user = True
    mat.name = "FRM " + e.name
    return mat


def used_keys(scene) -> list:
    out = []
    for g in scene.fresing.groups:
        k = group_key(g)
        if k and k not in out:
            out.append(k)
    return out


def short_list(scene) -> list:
    """[(entry, listed, used)] of the project's short list: the listed entries in the order they were added, then the
    ones the groups use that are not listed (marked "in use")."""
    used = used_keys(scene)
    out, seen = [], set()
    for pm in scene.fresing.project_materials:
        if pm.listed:
            e = find(scene, pm.name)
            if e is not None:
                out.append((e, True, pm.name in used))
                seen.add(pm.name)
    for k in used:
        if k not in seen:
            e = find(scene, k)
            if e is not None:
                out.append((e, False, True))
    return out


def used_by_project(scene) -> set:
    """The keys the groups and the paint schemes use (their copies must stay in the project)."""
    s = scene.fresing
    return {g.mat_key for g in s.groups} | {lk.key for sch in s.schemes for lk in sch.looks}


def is_listed(scene, key: str) -> bool:
    pm = scene.fresing.project_materials.get(key)
    return bool(pm is not None and pm.listed)


def add_to_project(scene, e) -> None:
    remember(scene, e, listed=True)


def remove_from_project(scene, key: str) -> None:
    """Off the short list; the project's copy goes too when no group uses it."""
    pms = scene.fresing.project_materials
    pm = pms.get(key)
    if pm is None:
        return
    pm.listed = False
    if key not in used_by_project(scene):
        if pm.blend_mat:
            mat = bpy.data.materials.get(pm.blend_mat)
            if mat is not None and mat.get("fr_own_key") == key:
                mat.use_fake_user = False
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
        pms.remove(pms.find(key))


def from_template(scene, items: list) -> int:
    """A template's short list into the project (an own material with its file: it renders without the folder; its
    Blender material is appended when its folder is there). Returns how many were added."""
    n = 0
    for it in items:
        key = str(it.get("key", ""))
        if not key.startswith(("builtin:", "preset:", "own:")):
            continue
        if not key.startswith("own:") and F.builtin(key) is None:
            continue
        data = None
        if key.startswith("own:"):
            try:
                data = json.loads(str(it.get("data") or ""))
            except (ValueError, RecursionError, TypeError):
                data = None
            ident = data.get("id") if isinstance(data, dict) else None
            if ident != key[4:].split("@")[0]:
                continue                                  # no file, or another material's: left out
        pm = _pm(scene, key)
        pm.title = F.storable(str(it.get("title", ""))) or pm.title
        if data is not None:
            pm.data = json.dumps(data, ensure_ascii=True, sort_keys=True)
            e = find(scene, key)
            if e is not None and e.is_blend and e.blend and os.path.isfile(e.blend):
                try:
                    mat = append_blend(e)
                except (OSError, RuntimeError) as exc:     # a damaged Blender file: the material stays the stand-in
                    print(f"Fresing Render: '{e.name}' could not be taken from its Blender file:", exc)
                    mat = None
                if mat is not None:
                    pm.blend_mat = mat.name
        pm.listed = True
        n += 1
    return n


# ---------------------------------------------------------------------------------------------------------------------
# using an entry

def apply(context, g, e, full: bool = False) -> None:
    """Give group ``g`` the entry's look: its library material and settings (one rebuild of the group's material).
    A built-in keeps the group's colour (when it has none of its own), wear and rust; a finish of the same kind
    keeps the group's finish settings. ``full`` (Reset, task 0314): Wear, Rust and the finish's settings from the
    entry too."""
    if not e.ok:
        raise ValueError("; ".join(e.problems))
    scene = g.id_data
    v = F.values_of(e)
    if e.key.startswith("own:"):
        remember(scene, e)
        if e.is_blend and not (scene.fresing.project_materials.get(e.key).blend_mat
                               and bpy.data.materials.get(scene.fresing.project_materials.get(e.key).blend_mat)):
            raise ValueError(f"'{e.name}' could not be taken from its Blender file")
    same = v["material"] == g.material
    g["material"] = ML.UIDS[v["material"]]
    if v["color"] is not None:
        g["color"] = v["color"]
    ch = e.changes or {}
    if "wear" in ch or e.key.startswith("own:") or full:
        g["wear"] = v["wear"]
    if "rust" in ch or e.key.startswith("own:") or full:
        g["rust"] = v["rust"]
    fin = v["finish"]
    if fin is not None and not (same and "finish" not in ch and not full):
        g["fin_size"] = fin["size"]
        g["fin_angle"] = math.radians(fin["angle"])
        g["fin_amount"] = fin["amount"]
        g["fin_base"] = fin_core.BASES[fin["base"]][0] if fin["base"] in fin_core.BASES else 0
        g["fin_kind"] = fin_core.KINDS[fin["kind"]][0] if fin["kind"] in fin_core.KINDS else 0
        g["fin_of"] = fin_core.finish_id(v["material"])
    elif fin is not None:
        g["fin_of"] = fin_core.finish_id(v["material"])
    from . import look_adjust
    look_adjust.write(g, v["adjust"])               # task 0314: the entry's own Adjust values (built-ins: none)
    g["mat_key"] = e.key
    from . import props
    props._group_look_changed(g, context)
    forget_adjusted(g)


def reset(context, g) -> None:
    """Task 0314: the group's look back to its entry as made – the Adjust sliders, Wear, Rust and the finish's
    settings from the entry (a colour-taking entry keeps the group's colour). A group without an entry: the sliders."""
    from . import look_adjust
    e = find(g.id_data, group_key(g))
    if e is None or not e.ok or e.is_blend:
        look_adjust.write(g, {})
        from . import props
        props._group_look_changed(g, context)
        forget_adjusted(g)
        return
    apply(context, g, e, full=True)


def group_finish_dict(g) -> dict | None:
    if fin_core.get(g.material) is None:
        return None
    return {"size": float(g.fin_size), "angle": math.degrees(g.fin_angle), "amount": float(g.fin_amount),
            "base": g.fin_base, "kind": g.fin_kind}


# ---------------------------------------------------------------------------------------------------------------------
# saving own materials

def app_version() -> str:
    from .. import __version__
    return __version__


def author() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or ""


def save_from_group(context, g, name: str, description: str, root: str):
    """What the group shows now becomes an own material in ``root``; the group then uses it. Returns the entry."""
    scene = g.id_data
    if g.material == "blender_material":
        src = __import__(__package__ + ".materials", fromlist=["x"]).blend_source(g)
        if src is None:
            raise F.MaterialError("This group's Blender material is not in the project")
        return save_from_blender(context, src, name, description, root, group=g)
    from . import look_adjust
    data = F.new_material(name, g.material, F.changes_of(g.material, g.color, g.wear, g.rust, group_finish_dict(g),
                                                         look_adjust.values_of(g)),
                          description, author(), app_version())
    folder = F.save_new(root, data)
    e = F.read_folder(folder, *_level_of(root))
    _added(e)
    if e.ok:
        apply(context, g, e)
        remember(scene, e)
    make_picture(e)
    return e


def images_outside(mat, folder: str) -> list:
    """Image files a Blender material uses (also inside its node groups) that are not packed and not in ``folder``."""
    out, seen, stack = [], set(), [mat.node_tree] if mat.node_tree else []
    root = os.path.normcase(os.path.abspath(folder))
    while stack:
        nt = stack.pop()
        if nt is None or nt.name_full in seen:
            continue
        seen.add(nt.name_full)
        for node in nt.nodes:
            img = getattr(node, "image", None)
            if img is not None and img.source in ("FILE", "SEQUENCE", "TILED") and img.packed_file is None:
                p = os.path.abspath(bpy.path.abspath(img.filepath, library=img.library))
                if not os.path.normcase(p).startswith(root + os.sep) and p not in out:
                    out.append(p)
            sub = getattr(node, "node_tree", None)
            if sub is not None:
                stack.append(sub)
    return out


def save_from_blender(context, mat, name: str, description: str, root: str, group=None):
    """A material made in Blender's shader editor becomes an own material: ``material.blend`` (the material and what
    it uses; packed pictures stay packed) + ``material.json`` + a picture. Returns the entry."""
    if mat is None:
        raise F.MaterialError("Pick a material first.")
    folder = F.free_folder(root, name or mat.name)
    os.makedirs(folder, exist_ok=True)
    outside = images_outside(mat, folder)
    blend = os.path.join(folder, F.BLEND_NAME)
    bpy.data.libraries.write(blend, {mat}, fake_user=True, path_remap="ABSOLUTE", compress=True)
    data = F.new_material(name or mat.name, "paint_satin", {}, description, author(), app_version(),
                          blend={"material": mat.name, "images_outside": outside})
    F.write_json(folder, data)
    e = F.read_folder(folder, *_level_of(root))
    _added(e)
    if group is not None and e.ok:
        apply(context, group, e)
    make_picture(e)
    return e


def _level_of(root: str) -> tuple:
    """(source, badge) of a Materials folder."""
    from ..core import locations as L
    from . import locations
    for loc in locations.folders(KIND):
        if L.same_path(loc.path, root):
            return SOURCE_LEVEL.get(loc.level, "mine"), loc.badge
    return "mine", "Mine"


def _added(e) -> None:
    """A material just saved is in the list at once (the folders are read again later; a read under way keeps it)."""
    _S["own"] = F.unique_keys([x for x in _S["own"] if x.folder != e.folder] + [e])
    _S["fresh"] = [x for x in _S["fresh"] if x.folder != e.folder] + [e]


def blender_materials() -> list:
    """The project's own Blender materials a user may save (not the app's group materials "FR …", not ones made from
    an own material "FRM …", nothing linked from another file)."""
    return [m for m in bpy.data.materials
            if m.get("fr_material") is None and m.get("fr_own_key") is None and m.library is None
            and m.node_tree is not None and not m.is_grease_pencil
            and not m.name.startswith(("FR sheet", "FR picture", "FR sticker", "FR decal"))]


# ---------------------------------------------------------------------------------------------------------------------
# pictures of own materials, made in a background Blender

def runner_command(job: str) -> tuple:
    """(command, env) that runs the picture runner in a background Blender (in tests: this Python, bpy as a module)."""
    from .. import winexe
    exe = bpy.app.binary_path
    env = dict(os.environ)
    if exe and winexe.is_blender_program(exe):
        return [exe, "--background", "--python", RUNNER, "--", job, PACKAGE], env
    env["PYTHONPATH"] = os.pathsep.join(p for p in (os.path.dirname(PACKAGE_DIR), env.get("PYTHONPATH", "")) if p)
    return [sys.executable, RUNNER, job, os.path.basename(PACKAGE_DIR)], env


def picture_item(e) -> dict:
    out = os.path.join(e.folder, F.PICTURE_NAME)
    if e.is_blend:
        return {"out": out, "blend": e.blend, "material": e.blend_material}
    ch = dict(e.changes)
    if not ch.get("color") and ML.needs_color(e.base):
        ch["color"] = F.PICTURE_COLOURS.get(e.base, F.DEFAULT_PICTURE_COLOUR)
    return {"out": out, "base": e.base, "changes": ch}


def make_picture(e) -> bool:
    """Start making an own material's picture (the app does not wait). False when it cannot be made."""
    if not e.folder or not e.ok:
        return False
    work = tempfile.mkdtemp(prefix="fr_matpic_")
    job = os.path.join(work, "job.json")
    with open(job, "w", encoding="utf-8") as fh:
        json.dump({"items": [picture_item(e)]}, fh)
    cmd, env = runner_command(job)
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        with open(os.path.join(work, "log.txt"), "w", encoding="utf-8") as log:    # the child keeps its own handle
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=work, **kwargs)
    except OSError as exc:
        print("Fresing Render: the material picture was not started:", exc)
        return False
    _S["jobs"].append({"proc": proc, "key": e.key, "folder": e.folder, "dir": work, "name": e.name,
                       "started": time.monotonic()})
    if not bpy.app.timers.is_registered(_watch_jobs):
        bpy.app.timers.register(_watch_jobs, first_interval=0.5)
    return True


def busy_pictures() -> list:
    """The names of own materials whose picture is being made."""
    return [j["name"] for j in _S["jobs"]]


def picture_busy(key: str) -> bool:
    return any(j["key"] == key for j in _S["jobs"])


def wait_pictures(timeout: float = 300.0) -> None:
    """Tests: wait for the pictures being made."""
    end = time.monotonic() + timeout
    while _S["jobs"] and time.monotonic() < end:
        for j in list(_S["jobs"]):
            try:
                j["proc"].wait(timeout=max(0.1, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                break
        _watch_jobs()


def _watch_jobs():
    for j in list(_S["jobs"]):
        if j["proc"].poll() is None:
            continue
        _S["jobs"].remove(j)
        pic = os.path.join(j["folder"], F.PICTURE_NAME)
        for e in _S["own"]:
            if e.folder == j["folder"]:
                e.picture = pic if os.path.isfile(pic) else ""
        if j["proc"].returncode != 0:
            print(f"Fresing Render: the picture of '{j['name']}' was not made (log: {j['dir']})")
        else:
            import shutil
            shutil.rmtree(j["dir"], ignore_errors=True)
    redraw()
    return 0.5 if _S["jobs"] else None


# ---------------------------------------------------------------------------------------------------------------------
# task 0314: the large picture of an adjusted look, made again in the background 0.8 s after the last change

ADJUST_WAIT = 0.8


def window_open() -> bool:
    from .ops_setup import MATERIALS_MARK
    wm = getattr(bpy.context, "window_manager", None)
    for win in (wm.windows if wm is not None else ()):
        try:
            if win.screen.get(MATERIALS_MARK):
                return True
        except (AttributeError, ReferenceError):
            continue
    return False


def group_item(g, out: str) -> dict | None:
    """The picture runner's job for what a group shows now (None: a Blender material, not pictured here)."""
    if g.material in ("blender_material", "from_file"):
        return None
    from . import look_adjust
    ch = F.changes_of(g.material, g.color, g.wear, g.rust, group_finish_dict(g), look_adjust.values_of(g))
    if not ch.get("color") and ML.needs_color(g.material):
        ch["color"] = F.PICTURE_COLOURS.get(g.material, F.DEFAULT_PICTURE_COLOUR)
    return {"out": out, "base": g.material, "changes": ch, "samples": 24}


def look_stamp(g) -> str:
    it = group_item(g, "")
    return json.dumps(it, sort_keys=True) if it else ""


def adjusted(g) -> None:
    """A group's look changed while the Materials window may show it: its large picture is made again soon."""
    if bpy.app.background or not window_open():
        return
    a = _S.setdefault("adj", {})
    st = a.setdefault(g.name, {})
    st["due"] = time.monotonic() + ADJUST_WAIT
    st["stamp"] = look_stamp(g)
    st["scene"] = g.id_data.name
    if not bpy.app.timers.is_registered(_adjust_tick):
        bpy.app.timers.register(_adjust_tick, first_interval=0.2)


def forget_adjusted(g) -> None:
    _S.setdefault("adj", {}).pop(g.name, None)


def adjusted_icon(g) -> tuple:
    """(icon id or 0, busy): the latest picture of the group's adjusted look."""
    st = _S.setdefault("adj", {}).get(g.name)
    if not st:
        return 0, False
    busy = bool(st.get("proc") is not None or st.get("due"))
    return st.get("icon", 0), busy


def _adjust_tick():
    a = _S.setdefault("adj", {})
    now = time.monotonic()
    for name, st in list(a.items()):
        proc = st.get("proc")
        if proc is not None:
            if proc.poll() is None:
                continue
            st["proc"] = None
            pic = st.get("out", "")
            if proc.returncode == 0 and os.path.isfile(pic):
                pc = previews()
                k = "adj|" + _stamp(pic)
                if k not in pc:
                    pc.load(k, pic, "IMAGE")
                old = st.get("key")
                if old and old != k and old in pc:
                    del pc[old]
                st["key"], st["icon"] = k, pc[k].icon_id
            redraw()
        if st.get("due") and now >= st["due"] and st.get("proc") is None:
            sc = bpy.data.scenes.get(st.get("scene", ""))
            g = sc.fresing.groups.get(name) if sc is not None and hasattr(sc, "fresing") else None
            st["due"] = None
            if g is None:
                continue
            work = st.get("dir") or tempfile.mkdtemp(prefix="fr_adjust_")
            st["dir"] = work
            st["n"] = st.get("n", 0) + 1
            item = group_item(g, os.path.join(work, f"look_{st['n']}.png"))
            if item is None:
                continue
            job = os.path.join(work, "job.json")
            with open(job, "w", encoding="utf-8") as fh:
                json.dump({"items": [item]}, fh)
            cmd, env = runner_command(job)
            kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)} if sys.platform == "win32" else {}
            try:
                log = open(os.path.join(work, "log.txt"), "w", encoding="utf-8")
                st["proc"] = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env, cwd=work, **kwargs)
                log.close()
                st["out"] = item["out"]
            except OSError as exc:
                print("Fresing Render: the adjusted look's picture was not started:", exc)
    busy = any(st.get("proc") is not None or st.get("due") for st in a.values())
    return 0.25 if busy else None


# ---------------------------------------------------------------------------------------------------------------------

def forget() -> None:
    """A project was opened: the project's copies are read again (the folders' list stays)."""
    _S["project"].clear()


def unregister() -> None:
    for fn in (_make_chips, _take_own, _watch_jobs, _adjust_tick):
        if bpy.app.timers.is_registered(fn):
            bpy.app.timers.unregister(fn)
    if _S["previews"] is not None:
        from bpy.utils import previews as pv
        try:
            pv.remove(_S["previews"])
        except Exception:  # noqa: BLE001
            pass
    _S.update(previews=None, icons={}, chips={}, chip_todo=[], project={}, adj={})
