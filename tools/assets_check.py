"""Check a Fresing assets pack before it is uploaded, and again after (task 0356, study 0344 1.5–1.6, section 6).

    ~/venv/bin/python tools/assets_check.py <pack folder | FresingAssets-<version>.zip>
        [--app-version 0.2.270] [--blender <blender>] [--no-render] [--no-blender]
    ~/venv/bin/python tools/assets_check.py --pin installer/assets_pin.json     # CI: the pin as key=value lines
    ~/venv/bin/python tools/assets_check.py --fetch assets-1.0.0 [--into <folder>]   # a published release's zip

ONE set of pack checks, all in the public repository (owner's pick 12: no private CI): the worker runs this in its
session before it uploads a pack, GitHub's "Real pack" job (tests.yml) and the by-hand workflow "Check an assets
pack" (assets-check.yml) run it on the published download. Output: ``OK – …`` or one line per problem (``PROBLEM:``)
and per warning (``WARNING:``); exit code 1 when there is a problem.

What it checks:

* **zip** – one top folder ``Fresing Assets/``, no path outside it, no links, its name ``FresingAssets-<version>.zip``
  with the version of its pack.json;
* **pack.json** – read by the app's own ``core/assets_pack.py``: no note allowed (damaged, not ours, newer, outside the
  app window, a row left out – each with its reason);
* **files** – every listed file there with its size and sha256 (``assets_pack.verify``), no file the list does not
  name, data files only (no program file of any kind);
* **licence** – ``LICENSE-ASSETS.txt`` inside, listed, not empty, named by pack.json;
* **code twins** – every id has today's code look with the same id, or (kinds that allow it) a ``fallback``
  (``core/assets_registry.py``);
* **pictures** – every item has its 256 px picker picture; pictures fit the size their folder or name says (1k / 2k /
  4k), every 1k / 4k picture has its 2k variant (projects carry 2k, pick 2), 4k only for 360° photos (pick 11); light
  pictures and 360° photos 2:1;
* **sizes** – each set within its ``budget_mb`` (a problem), the pack above ~300 MB (a warning, pick 11);
* **render time** – every look with a code twin says its ``cost`` against it (≤ 1.3 x, or the owner's
  ``approved_slower``, pick 10);
* **in Blender 5.2** (a child process: Blender as a Python module, or ``--blender``) – every ``.blend`` holds its listed
  datablock and is **data only** (no Text datablock, no Python driver beyond simple expressions, no OSL Script node, no
  link to another file, pictures as relative files of the pack); the contract of its kind (0344 2.3: node-group
  sockets, no BSDF / Output inside, the finish's face data, the prop's ``fr_lod`` levels and floor at z = 0, …); it
  appends into an empty project with its pictures readable; and **a small render of every item (at least one per
  kind) – no pink (a missing picture), no black**.

**The pin** (``installer/assets_pin.json``, written by task 0358 – the pack version an app release was tested with)::

    {"version": "1.0.0", "tag": "assets-1.0.0", "file": "FresingAssets-1.0.0.zip",
     "url": "https://github.com/smholte/CAD-render-animation/releases/download/assets-1.0.0/FresingAssets-1.0.0.zip",
     "sha256": "…64 hex…", "bytes": 251234567, "licence_id": "fresing-assets-1.0"}

``--pin`` checks it and prints ``version=…``, ``tag=…``, ``file=…``, ``url=…``, ``sha256=…``, ``bytes=…`` (the CI step
appends them to ``$GITHUB_OUTPUT``).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from fresing_render.core import assets_pack as ap  # noqa: E402
from fresing_render.core import assets_registry as reg  # noqa: E402

REPO = "smholte/CAD-render-animation"
ZIP_RE = re.compile(r"^FresingAssets-(\d+\.\d+\.\d+)\.zip$")
TAG_PREFIX = "assets-"
LICENCE_FILE = "LICENSE-ASSETS.txt"
DATA_ENDINGS = (".blend", ".exr", ".hdr", ".png", ".jpg", ".jpeg", ".tx", ".txt")   # nothing else in a pack
PICKER_PX = 256
QUALITY_PX = {"1k": 1024, "2k": 2048, "4k": 4096}
FOUR_K_KINDS = ("hdri",)                         # pick 11: 4k only for the 360° photos
EQUIRECT_KINDS = ("light", "hdri")
MAX_ZIP_FILES = 20000
MAX_ZIP_BYTES = 4 << 30                          # 4 GiB unpacked: a pack is ~300 MB
DEFAULT_BLENDERS = (os.path.expanduser("~/blender-5.2.3/blender-5.2.3-linux-x64/blender"),
                    os.path.expanduser("~/blender/blender-5.2.3-linux-x64/blender"))
RENDER_KINDS = ("material", "finish", "light", "hdri", "prop", "environment", "person")


class Report:
    def __init__(self):
        self.problems: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def bad(self, line: str):
        self.problems.append(line)

    def warn(self, line: str):
        self.warnings.append(line)

    @property
    def ok(self) -> bool:
        return not self.problems

    def lines(self) -> list[str]:
        return [f"PROBLEM: {p}" for p in self.problems] + [f"WARNING: {w}" for w in self.warnings]


def app_version() -> str:
    with open(os.path.join(ROOT, "fresing_render", "__init__.py"), encoding="utf-8") as f:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', f.read(), re.M)
    return m.group(1) if m else "0.0.0"


# ---------------------------------------------------------------------------------------------- the zip

def unpack(zip_path: str, into: str, rep: Report) -> str:
    """Unpack a pack zip safely into ``into``; returns the pack folder ('' when it cannot be used)."""
    name = os.path.basename(zip_path)
    m = ZIP_RE.match(name)
    if not m:
        rep.bad(f"zip: its name {name!r} is not FresingAssets-<version>.zip")
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        rep.bad(f"zip: cannot be opened ({e})")
        return ""
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_FILES:
            rep.bad(f"zip: {len(infos)} entries, more than {MAX_ZIP_FILES}")
            return ""
        total = 0
        for i in infos:
            n = i.filename
            parts = n.rstrip("/").split("/")
            if n.startswith("/") or "\\" in n or ":" in n or ".." in parts or parts[0] != ap.FOLDER:
                rep.bad(f"zip: {n!r} lies outside the top folder '{ap.FOLDER}/'")
                return ""
            if stat.S_ISLNK(i.external_attr >> 16):
                rep.bad(f"zip: {n!r} is a link – a pack holds plain files only")
                return ""
            total += i.file_size
        if total > MAX_ZIP_BYTES:
            rep.bad(f"zip: {total / 1e9:.1f} GB unpacked, more than {MAX_ZIP_BYTES / 1e9:.0f} GB")
            return ""
        try:
            zf.extractall(into)
        except (OSError, zipfile.BadZipFile, ValueError) as e:
            rep.bad(f"zip: cannot be unpacked ({e})")
            return ""
    root = os.path.join(into, ap.FOLDER)
    if m:
        try:
            with open(os.path.join(root, ap.PACK_JSON), encoding="utf-8-sig") as f:
                v = json.load(f).get("version")
        except (OSError, ValueError, AttributeError):
            v = None
        if v is not None and v != m.group(1):
            rep.bad(f"zip: its name says version {m.group(1)}, its pack.json {v}")
    return root


# ---------------------------------------------------------------------------------------------- pictures

def picture_size(path: str):
    """(width, height) of a PNG, JPEG or OpenEXR file read from its header; None for other kinds or a bad header."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 16)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR":
        return struct.unpack(">II", head[16:24])
    if head[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(head):
            if head[i] != 0xFF:
                return None
            marker = head[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", head[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", head[i + 5:i + 9])
                return w, h
            i += 2 + seg
        return None
    if head[:4] == b"\x76\x2f\x31\x01":
        i = 8
        while i < len(head) and head[i] != 0:
            end = head.find(b"\0", i)
            name = head[i:end]
            tend = head.find(b"\0", end + 1)
            size = struct.unpack("<i", head[tend + 1:tend + 5])[0]
            val = head[tend + 5:tend + 5 + size]
            if name == b"dataWindow" and size == 16:
                x0, y0, x1, y1 = struct.unpack("<iiii", val)
                return x1 - x0 + 1, y1 - y0 + 1
            i = tend + 5 + size
        return None
    return None


def _quality(rel: str) -> str:
    """'1k' / '2k' / '4k' from a folder (textures/2k/…) or a name ending (…_2k.exr); '' when it says none."""
    parts = rel.split("/")
    for p in parts[:-1]:
        if p in QUALITY_PX:
            return p
    m = re.search(r"_(1k|2k|4k)\.[A-Za-z]+$", parts[-1])
    return m.group(1) if m else ""


def _variant(rel: str, q: str) -> str:
    parts = rel.split("/")
    if any(p in QUALITY_PX for p in parts[:-1]):
        return "/".join(q if p in QUALITY_PX else p for p in parts[:-1]) + "/" + parts[-1]
    return re.sub(r"_(1k|2k|4k)(\.[A-Za-z]+)$", rf"_{q}\2", rel)


# ---------------------------------------------------------------------------------------------- plain checks

def check_plain(root: str, version: str, rep: Report):
    """Everything that needs no Blender. Returns the read pack (None when it cannot be read at all)."""
    found = ap.read(root, version)
    if found.pack is None:
        if found.state == "none":
            rep.bad(f"pack.json: there is none in {root}")
        else:
            rep.bad(f"pack.json: {found.note} ({found.state}: {found.detail})")
        return None
    pack = found.pack
    for rid, why in pack.left_out:
        rep.bad(f"pack.json: the row {rid} is left out by the app: {why}")

    # files: the list against the folder
    v = ap.verify(pack)
    for line in v.problems:
        rep.bad(f"files: {line}")
    for base, dirs, names in os.walk(root):
        for d in list(dirs):
            if os.path.islink(os.path.join(base, d)):
                rep.bad(f"files: {os.path.relpath(os.path.join(base, d), root)} is a link – plain files only")
                dirs.remove(d)
        for n in names:
            full = os.path.join(base, n)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == ap.PACK_JSON:
                continue
            if os.path.islink(full):
                rep.bad(f"files: {rel} is a link – plain files only")
            if rel not in pack.files:
                rep.bad(f"files: {rel} is in the pack but not in pack.json's 'files'")
    for rel in pack.files:
        if not rel.lower().endswith(DATA_ENDINGS):
            rep.bad(f"data only: {rel} is no data file of a pack ({', '.join(DATA_ENDINGS)})")

    # licence
    if pack.licence != LICENCE_FILE:
        rep.bad(f"licence: pack.json names {pack.licence!r} as its licence, not {LICENCE_FILE}")
    if LICENCE_FILE not in pack.files:
        rep.bad(f"licence: {LICENCE_FILE} is not in the pack")
    else:
        full = pack.path(LICENCE_FILE)
        if not full or not os.path.isfile(full) or os.path.getsize(full) < 20:
            rep.bad(f"licence: {LICENCE_FILE} is missing or empty")
    if not pack.licence_id:
        rep.bad("licence: pack.json has no 'licence_id'")

    # code twins (or a named fallback)
    registry = reg.Registry.build(found)
    for rid, why in registry.refused:
        rep.bad(f"code twin: {rid} {why}")
    code = reg.code_ids()

    # pictures, sizes, render times
    for a in sorted(pack.assets.values(), key=lambda x: x.id):
        if not a.picture:
            rep.bad(f"picture: {a.id} has no {PICKER_PX} px picker picture")
        else:
            size = picture_size(pack.path(a.picture))
            if size is None:
                rep.bad(f"picture: {a.picture} ({a.id}) cannot be read")
            elif max(size) != PICKER_PX:
                rep.bad(f"picture: {a.picture} ({a.id}) is {size[0]} x {size[1]} px, not {PICKER_PX} px")
        twin = a.code_id in code.get(a.kind, ())
        if twin and a.cost <= 0:
            rep.bad(f"render time: {a.id} says no 'cost' against its code look (pick 10: at most {ap.SLOWER:g} x)")
        pics = [a.file] + list(a.textures) if a.kind in ap.PICTURE_KINDS else list(a.textures)
        qualities = {_quality(p) for p in pics}
        for p in pics:
            q = _quality(p)
            size = picture_size(pack.path(p))
            if q == "4k" and a.kind not in FOUR_K_KINDS:
                rep.bad(f"picture size: {p} ({a.id}) is a 4k picture – 4k only for 360° photos (pick 11)")
            if size and q and max(size) > QUALITY_PX[q]:
                rep.bad(f"picture size: {p} ({a.id}) is {size[0]} x {size[1]} px, more than its {q}")
            if q in ("1k", "4k") and _variant(p, "2k") not in pics:
                rep.bad(f"picture size: {p} ({a.id}) has no 2k variant ({_variant(p, '2k')}) – projects carry 2k")
            if a.kind in EQUIRECT_KINDS and p.lower().endswith(".exr") and size and size[0] != 2 * size[1]:
                rep.bad(f"picture size: {p} ({a.id}) is {size[0]} x {size[1]} px, not 2:1 (equirectangular)")
        if a.kind in EQUIRECT_KINDS and len(qualities - {""}) and "2k" not in qualities:
            rep.bad(f"picture size: {a.id} has no 2k picture")

    for line in ap.size_problems(pack):
        if line.startswith("Set "):
            rep.bad(f"size: {line}")
        else:
            rep.warn(f"size: {line} (pick 11)")
    rep.info.append(f"{pack.id} {pack.version}: {len(pack.assets)} items, {len(pack.files)} files, "
                    f"{pack.bytes / 1e6:.1f} MB")
    return pack


# ---------------------------------------------------------------------------------------------- in Blender

CHILD = r'''
import json, math, os, sys
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
repo, root, job_path, out_path = argv[:4]
sys.path.insert(0, repo)
import bpy
import numpy as np
from mathutils import Matrix, Vector
from fresing_render.core import assets_pack as ap

job = json.load(open(job_path, encoding="utf-8"))
out = {"problems": [], "renders": {}, "blender": bpy.app.version_string}
def bad(s):
    out["problems"].append(s)
if tuple(bpy.app.version[:2]) != (5, 2):
    bad(f"blender: the checks need Blender 5.2, this is {bpy.app.version_string}")
files = set(job["files"])
real_root = os.path.realpath(root)

ID_COLLS = ("objects", "meshes", "materials", "node_groups", "worlds", "lights", "cameras", "scenes", "shape_keys",
            "curves", "armatures", "textures", "images", "collections", "particles", "volumes", "pointclouds",
            "hair_curves", "grease_pencils", "linestyles", "actions", "speakers", "lattices", "metaballs")

def ids():
    for c in ID_COLLS:
        for idb in getattr(bpy.data, c, ()):
            yield idb
            nt = getattr(idb, "node_tree", None)
            if nt is not None:
                yield nt

def trees():
    for g in bpy.data.node_groups:
        yield g.name, g
    for c in ("materials", "worlds", "lights", "linestyles"):
        for idb in getattr(bpy.data, c, ()):
            nt = getattr(idb, "node_tree", None)
            if nt is not None:
                yield f"{idb.name} ({c[:-1]})", nt

def rel_of(img, blend):
    p = img.filepath
    if not p.startswith("//"):
        return None
    full = os.path.normpath(os.path.join(os.path.dirname(blend), p[2:].replace("\\", "/")))
    real = os.path.realpath(full)
    if not real.startswith(real_root + os.sep):
        return ""
    return os.path.relpath(real, real_root).replace(os.sep, "/")

def data_only(rel, path, rows):
    if len(bpy.data.texts):
        bad(f"data only: {rel} holds a Text datablock ({bpy.data.texts[0].name!r}) – a pack holds no scripts")
    for lib in bpy.data.libraries:
        bad(f"data only: {rel} links to another file ({lib.filepath})")
    for idb in ids():
        ad = getattr(idb, "animation_data", None)
        for d in (ad.drivers if ad else ()):
            if d.driver.type == "SCRIPTED" and not d.driver.is_simple_expression:
                bad(f"data only: {rel} has a Python driver on {idb.name} {d.data_path} "
                    f"({d.driver.expression!r}) – simple expressions only")
    for name, nt in trees():
        for nd in nt.nodes:
            if nd.bl_idname == "ShaderNodeScript":
                bad(f"data only: {rel} has an OSL Script node in {name}")
    allowed = set()
    for a in rows:
        allowed.update(a["textures"])
    for img in bpy.data.images:
        if img.source not in ("FILE", "SEQUENCE", "TILED"):
            continue
        if img.packed_file is not None:
            bad(f"pictures: {rel} packs the picture {img.name!r} inside – a pack's pictures are its own files")
            continue
        r = rel_of(img, path)
        if r is None:
            bad(f"pictures: {rel} reads {img.name!r} by an absolute path ({img.filepath}) – relative paths only")
        elif r == "" or r not in files:
            bad(f"pictures: {rel} reads {img.filepath!r}, which is not a listed file of the pack")
        elif r not in allowed:
            bad(f"pictures: {rel} reads {r}, which its row's 'textures' does not name")

def contract(a, rel):
    kind = a["kind"]
    coll, name = a["datablock"]
    if kind in ap.SOCKETS:
        ng = bpy.data.node_groups.get(name)
        if ng is None or ng.bl_idname != "ShaderNodeTree":
            bad(f"contract: {a['id']}: {name!r} is not a shader node group")
            return
        spec = ap.SOCKETS[kind]
        ins = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "INPUT"]
        outs = [s.name for s in ng.interface.items_tree if getattr(s, "in_out", "") == "OUTPUT"]
        miss = [s for s in spec["inputs"] if s not in ins] + [s for s in spec["outputs"] if s not in outs]
        if miss:
            bad(f"contract: {a['id']}: the group lacks the socket(s) {', '.join(miss)}")
        extra = [s for s in outs if s not in spec["outputs"] + spec["optional_outputs"]]
        if extra:
            bad(f"contract: {a['id']}: the group has outputs the app does not wire: {', '.join(extra)}")
        seen = set()
        def walk(nt):
            if nt.name in seen:
                return
            seen.add(nt.name)
            for nd in nt.nodes:
                if nd.bl_idname.startswith(ap.FORBIDDEN_NODES):
                    bad(f"contract: {a['id']}: a {nd.bl_idname} node inside – the app keeps its own BSDF and output")
                if nd.bl_idname == "ShaderNodeGroup" and nd.node_tree:
                    walk(nd.node_tree)
        walk(ng)
        if kind == "finish":
            attrs = set()
            for t in seen:
                for nd in bpy.data.node_groups[t].nodes:
                    if nd.bl_idname == "ShaderNodeAttribute":
                        attrs.add((nd.attribute_type, nd.attribute_name))
            if not any(t == "GEOMETRY" and n in ap.FINISH_ATTRIBUTES for t, n in attrs):
                bad(f"contract: {a['id']}: the finish reads none of its face data ({', '.join(ap.FINISH_ATTRIBUTES)})")
            if ("VIEW_LAYER", ap.PIXEL_ATTRIBUTE) not in attrs:
                bad(f"contract: {a['id']}: the finish does not read the pixel angle ({ap.PIXEL_ATTRIBUTE})")
    elif kind == "prop":
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != "MESH":
            bad(f"contract: {a['id']}: {name!r} is not a mesh object")
            return
        lod = ob.data.attributes.get("fr_lod")
        vals = set()
        if lod is not None:
            arr = np.zeros(len(lod.data), np.int64)
            try:
                lod.data.foreach_get("value", arr)
                vals = set(int(x) for x in np.unique(arr))
            except Exception:
                vals = set()
        if lod is None or lod.domain != "FACE" or vals != {1, 2}:
            bad(f"contract: {a['id']}: the mesh needs both levels as the FACE attribute fr_lod (1 and 2)")
        zs = [v.co.z for v in ob.data.vertices]
        if zs and abs(min(zs)) > 1e-3:
            bad(f"contract: {a['id']}: its lowest point is at z = {min(zs):.4f} m, not on the floor (z = 0)")
    elif kind in ("environment", "crane") or (kind == "person" and coll == "collections"):
        col = bpy.data.collections.get(name)
        if col is None or not col.all_objects:
            bad(f"contract: {a['id']}: the collection {name!r} holds no objects")

# ---- render helpers
def empty_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.data.scenes[0] if bpy.data.scenes else bpy.data.scenes.new("Scene")
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.cycles.use_adaptive_sampling = False
    sc.render.resolution_x = sc.render.resolution_y = 64
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("check world")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.25, 0.25, 0.25, 1)
    sc.world = w
    return sc

def add_sun(sc):
    sun = bpy.data.lights.new("check sun", "SUN")
    sun.energy = 3.0
    ob = bpy.data.objects.new("check sun", sun)
    ob.rotation_euler = (math.radians(40), math.radians(20), math.radians(30))
    sc.collection.objects.link(ob)

def camera(sc, loc, target, ortho=0.0):
    cam = bpy.data.cameras.new("check cam")
    if ortho:
        cam.type = "ORTHO"
        cam.ortho_scale = ortho
    cam.clip_end = 10000
    ob = bpy.data.objects.new("check cam", cam)
    d = Vector(target) - Vector(loc)
    ob.matrix_world = Matrix.Translation(loc) @ d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
    sc.collection.objects.link(ob)
    sc.camera = ob

def render(sc, tag, kind, aid, transparent):
    sc.render.film_transparent = transparent
    path = os.path.join(job["tmp"], f"render_{tag}.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=sc.name)
    img = bpy.data.images.load(path)
    px = np.zeros(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    seen = px[px[:, 3] > 0.5] if transparent else px
    if len(seen) == 0:
        bad(f"render: {aid} ({kind}) shows nothing in its test render")
        return
    r, g, b = seen[:, 0], seen[:, 1], seen[:, 2]
    lo = np.minimum(r, b)
    pink = float(np.mean((lo > 0.15) & (g < 0.35 * lo) & (np.abs(r - b) < 0.4 * np.maximum(r, b))))
    mean = float(np.mean(seen[:, :3]))
    out["renders"][aid] = {"kind": kind, "pink": round(pink, 4), "mean": round(mean, 4), "pixels": int(len(seen))}
    if pink > 0.02:
        bad(f"render: {aid} ({kind}) renders pink in {pink:.0%} of its picture – a picture is missing")
    if mean < 0.01:
        bad(f"render: {aid} ({kind}) renders black (mean {mean:.4f})")

def render_group(sc, a, ng):
    me = bpy.data.meshes.new("check plane")
    me.from_pydata([(-0.2, -0.2, 0), (0.2, -0.2, 0), (0.2, 0.2, 0), (-0.2, 0.2, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("check plane", me)
    sc.collection.objects.link(ob)
    mat = bpy.data.materials.new("check material")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = ng
    for name, val in (("Colour", (0.5, 0.5, 0.5, 1.0)), ("Roughness", 0.5), ("Metallic", 0.0)):
        s = grp.inputs.get(name)
        if s is not None and hasattr(s, "default_value"):
            try:
                s.default_value = val
            except (TypeError, ValueError):
                pass
    for o, i in (("Colour", "Base Color"), ("Metallic", "Metallic"), ("Roughness", "Roughness"),
                 ("Normal", "Normal"), ("Alpha", "Alpha")):
        if grp.outputs.get(o) is not None and bsdf.inputs.get(i) is not None:
            nt.links.new(grp.outputs[o], bsdf.inputs[i])
    me.materials.append(mat)
    add_sun(sc)
    camera(sc, (0, 0, 1), (0, 0, 0), ortho=0.3)
    render(sc, a["id"].replace(":", "_"), a["kind"], a["id"], False)

def render_objects(sc, a, obs):
    pts = [o.matrix_world @ Vector(c) for o in obs if o.type == "MESH" for c in o.bound_box]
    if not pts:
        bad(f"render: {a['id']} ({a['kind']}) has no mesh to show")
        return
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c, rad = (lo + hi) / 2, max((hi - lo).length / 2, 0.01)
    add_sun(sc)
    camera(sc, c + Vector((1.0, -1.4, 0.9)).normalized() * rad * 3.2, c)
    render(sc, a["id"].replace(":", "_"), a["kind"], a["id"], True)

def render_world(sc, a, path):
    w = sc.world
    env = w.node_tree.nodes.new("ShaderNodeTexEnvironment")
    img = bpy.data.images.load(path)
    if img.size[0] == 0:
        bad(f"render: {a['id']} ({a['kind']}): {a['file']} cannot be read by Blender")
    env.image = img
    w.node_tree.links.new(env.outputs["Color"], w.node_tree.nodes["Background"].inputs["Color"])
    camera(sc, (0, 0, 1.5), (1, 0, 1.6))
    render(sc, a["id"].replace(":", "_"), a["kind"], a["id"], False)

by_file = {}
for a in job["assets"]:
    by_file.setdefault(a["file"], []).append(a)
for rel in sorted(by_file):
    rows = by_file[rel]
    path = os.path.join(root, *rel.split("/"))
    if not rel.endswith(".blend"):
        continue
    try:
        with bpy.data.libraries.load(path) as (src, _dst):
            listed = {c: set(getattr(src, c)) for c in ("node_groups", "objects", "collections", "scenes")}
    except Exception as e:
        bad(f"blend: {rel} cannot be opened by Blender ({e})")
        continue
    for a in rows:
        coll, name = a["datablock"]
        if name not in listed.get(coll, ()):
            bad(f"blend: {rel} holds no {coll[:-1].replace('_', ' ')} named {name!r} ({a['id']})")
    try:
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
    except Exception as e:
        bad(f"blend: {rel} cannot be opened by Blender ({e})")
        continue
    data_only(rel, path, rows)
    for a in rows:
        if a["datablock"][1] in listed.get(a["datablock"][0], ()):
            contract(a, rel)
    # append into an empty project, then a small render of each item
    for a in rows:
        coll, name = a["datablock"]
        if name not in listed.get(coll, ()):
            continue
        sc = empty_scene()
        try:
            with bpy.data.libraries.load(path, link=False) as (_src, dst):
                setattr(dst, coll, [name])
        except Exception as e:
            bad(f"append: {a['id']} cannot be appended into an empty project ({e})")
            continue
        got = getattr(bpy.data, coll).get(name)
        if got is None or got.library is not None:
            bad(f"append: {a['id']} did not arrive in an empty project")
            continue
        for img in bpy.data.images:
            if img.source == "FILE" and img.packed_file is None and tuple(img.size) == (0, 0):
                bad(f"append: {a['id']}: its picture {img.filepath!r} cannot be read after the append")
        if not job["render"] or a["kind"] not in job["render_kinds"]:
            continue
        try:
            if coll == "node_groups":
                render_group(sc, a, got)
            elif coll == "objects":
                sc.collection.objects.link(got)
                render_objects(sc, a, [got])
            elif coll == "collections":
                sc.collection.children.link(got)
                render_objects(sc, a, list(got.all_objects))
        except Exception as e:
            bad(f"render: {a['id']} ({a['kind']}) could not be rendered ({type(e).__name__}: {e})")
for a in job["assets"]:
    if a["file"].endswith(".blend") or not job["render"] or a["kind"] not in job["render_kinds"]:
        continue
    try:
        render_world(empty_scene(), a, os.path.join(root, *a["file"].split("/")))
    except Exception as e:
        bad(f"render: {a['id']} ({a['kind']}) could not be rendered ({type(e).__name__}: {e})")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f)
'''


def blender_command(script: str, args: list[str], blender: str = "") -> list[str] | None:
    """How to run the child: a given Blender, else Blender as a Python module in this Python, else a known Blender."""
    if blender:
        return [blender, "-b", "--factory-startup", "--python-exit-code", "1", "--python", script, "--", *args]
    import importlib.util
    if importlib.util.find_spec("bpy") is not None:
        return [sys.executable, script, *args]
    for b in (os.environ.get("FRESING_BLENDER", ""), *DEFAULT_BLENDERS):
        if b and os.path.isfile(b):
            return blender_command(script, args, b)
    return None


def check_blender(pack, rep: Report, tmp: str, blender: str = "", render: bool = True, timeout: float = 1800):
    assets = [dict(id=a.id, kind=a.kind, file=a.file, datablock=list(a.datablock), textures=list(a.textures))
              for a in sorted(pack.assets.values(), key=lambda x: x.id)]
    job = {"assets": assets, "files": sorted(pack.files), "render": render, "render_kinds": list(RENDER_KINDS),
           "tmp": tmp}
    script, job_path, out_path = (os.path.join(tmp, n) for n in ("assets_child.py", "job.json", "out.json"))
    with open(script, "w", encoding="utf-8") as f:
        f.write(CHILD)
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f)
    cmd = blender_command(script, [ROOT, pack.root, job_path, out_path], blender)
    if cmd is None:
        rep.bad("blender: no Blender 5.2 found for the .blend checks – pass --blender <path>")
        return
    env = dict(os.environ)
    env.pop(ap.ENV, None)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        rep.bad(f"blender: the .blend checks did not finish ({type(e).__name__}: {e})")
        return
    if p.returncode != 0 or not os.path.isfile(out_path):
        tail = (p.stdout + p.stderr).strip().splitlines()[-12:]
        rep.bad("blender: the .blend checks stopped with an error: " + " | ".join(tail))
        return
    with open(out_path, encoding="utf-8") as f:
        got = json.load(f)
    for line in got["problems"]:
        rep.bad(line)
    kinds: dict[str, int] = {}
    for v in got["renders"].values():
        kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
    shown = ", ".join(f"{n} {k}" for k, n in sorted(kinds.items()))
    rep.info.append(f"Blender {got['blender']}: {len(got['renders'])} small renders, none pink or black – {shown}"
                    if rep.ok else f"Blender {got['blender']}: {len(got['renders'])} small renders – {shown}")


# ---------------------------------------------------------------------------------------------- the pin

PIN_KEYS = ("version", "tag", "file", "url", "sha256", "bytes", "licence_id")


def read_pin(path: str) -> tuple[dict, list[str]]:
    """The pin, checked: (pin, problems)."""
    try:
        with open(path, encoding="utf-8") as f:
            pin = json.load(f, parse_constant=ap._no_constant)
    except (OSError, ValueError) as e:
        return {}, [f"pin: {path} cannot be read ({e})"]
    if not isinstance(pin, dict):
        return {}, [f"pin: {path} is not a table"]
    problems = [f"pin: '{k}' is missing" for k in PIN_KEYS if k not in pin]
    if problems:
        return pin, problems
    v = pin["version"]
    if not (isinstance(v, str) and re.fullmatch(r"\d+\.\d+\.\d+", v)):
        problems.append(f"pin: version {v!r} is not like 1.0.0")
        return pin, problems
    if pin["tag"] != TAG_PREFIX + v:
        problems.append(f"pin: tag {pin['tag']!r} is not {TAG_PREFIX}{v}")
    if pin["file"] != f"FresingAssets-{v}.zip":
        problems.append(f"pin: file {pin['file']!r} is not FresingAssets-{v}.zip")
    want = f"https://github.com/{REPO}/releases/download/{TAG_PREFIX}{v}/FresingAssets-{v}.zip"
    if not isinstance(pin["url"], str) or pin["url"].lower() != want.lower():
        problems.append(f"pin: url is not the pack's release download ({want})")
    if not (isinstance(pin["sha256"], str) and ap.SHA_RE.match(pin["sha256"])):
        problems.append("pin: sha256 is not 64 small hex digits")
    if not (isinstance(pin["bytes"], int) and not isinstance(pin["bytes"], bool) and 0 < pin["bytes"] < 2 << 30):
        problems.append("pin: bytes is not a size below 2 GiB")
    return pin, problems


# ---------------------------------------------------------------------------------------------- a release

RELEASE_TAG_RE = re.compile(r"^assets-(\d+\.\d+\.\d+)$")


def _get(url: str, binary: bool = False):
    """GET from GitHub (public; a token in GITHUB_TOKEN / GH_TOKEN only raises the rate limit)."""
    import urllib.request
    headers = {"User-Agent": "fresing-assets-check", "Accept": "application/octet-stream" if binary
               else "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=600) as r:
        return r.read() if binary else json.loads(r.read().decode("utf-8"))


def fetch(tag: str, into: str, get=_get) -> tuple[str, list[str]]:
    """The pack zip of the release ``tag`` (``assets-1.0.0``), downloaded into ``into``: (zip path, problems).
    Checks what the release itself must hold (study 0344 1.6): a pre-release, ``FresingAssets-<version>.zip``,
    ``LICENSE-ASSETS.txt`` readable before the download, and – when it is there – that ``assets.json`` names this zip
    with its size and sha256."""
    import hashlib
    m = RELEASE_TAG_RE.match(tag or "")
    if not m:
        return "", [f"release: {tag!r} is not a pack's tag like assets-1.0.0"]
    v = m.group(1)
    problems = []
    try:
        rel = get(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}")
    except Exception as e:                                    # noqa: BLE001 – one line, not a traceback
        return "", [f"release: {tag} cannot be read on GitHub ({e})"]
    if not rel.get("prerelease"):
        problems.append(f"release: {tag} is not a pre-release – a pack's release must never become \"latest\"")
    files = {a.get("name"): a for a in rel.get("assets", [])}
    name = f"FresingAssets-{v}.zip"
    if LICENCE_FILE not in files:
        problems.append(f"release: {tag} has no {LICENCE_FILE} beside the zip (readable before the download)")
    if name not in files:
        return "", problems + [f"release: {tag} has no {name}"]
    os.makedirs(into, exist_ok=True)
    path = os.path.join(into, name)
    try:
        data = get(files[name]["browser_download_url"], binary=True)
    except Exception as e:                                    # noqa: BLE001
        return "", problems + [f"release: {name} cannot be downloaded ({e})"]
    with open(path, "wb") as f:
        f.write(data)
    sha = hashlib.sha256(data).hexdigest()
    if "assets.json" in files:
        try:
            listing = get(files["assets.json"]["browser_download_url"], binary=True)
            listing = json.loads(listing.decode("utf-8"))
        except Exception as e:                                # noqa: BLE001
            listing = None
            problems.append(f"release: its assets.json cannot be read ({e})")
        if isinstance(listing, dict):
            for key, want in (("version", v), ("file", name), ("sha256", sha), ("bytes", len(data))):
                if listing.get(key) != want:
                    problems.append(f"release: assets.json says {key} {listing.get(key)!r}, the zip has {want!r}")
    print(f"downloaded {name}: {len(data)} bytes, sha256 {sha}")
    return path, problems


# ---------------------------------------------------------------------------------------------- main

def check(target: str, version: str = "", blender: str = "", render: bool = True, use_blender: bool = True) -> Report:
    """Every check on a pack folder or zip. Never raises for a bad pack: the report says what is wrong."""
    rep = Report()
    version = version or app_version()
    tmp = tempfile.mkdtemp(prefix="assets_check_")
    try:
        if os.path.isfile(target) and target.lower().endswith(".zip"):
            root = unpack(target, os.path.join(tmp, "unpacked"), rep)
        elif os.path.isdir(target):
            root = target
        else:
            rep.bad(f"{target} is neither a pack folder nor a zip")
            root = ""
        if not root:
            return rep
        pack = check_plain(root, version, rep)
        if pack is not None and use_blender:
            work = os.path.join(tmp, "blender")
            os.makedirs(work)
            check_blender(pack, rep, work, blender, render)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rep


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("target", nargs="?", help="the pack folder (holding pack.json) or FresingAssets-<version>.zip")
    a.add_argument("--app-version", default="", help="the app version to read the pack for (default: this checkout's)")
    a.add_argument("--blender", default="", help="a Blender 5.2 binary (default: Blender as a Python module)")
    a.add_argument("--no-render", action="store_true", help="skip the small renders")
    a.add_argument("--no-blender", action="store_true", help="only the checks that need no Blender")
    a.add_argument("--pin", default="", help="check the pin file and print it as key=value lines")
    a.add_argument("--fetch", default="", help="a pack's release tag (assets-1.0.0): download its zip, then check it")
    a.add_argument("--into", default="", help="with --fetch: the folder for the zip (default: a temporary one)")
    args = a.parse_args(argv)
    if args.fetch:
        into = args.into or tempfile.mkdtemp(prefix="assets_fetch_")
        path, problems = fetch(args.fetch, into)
        for p in problems:
            print(f"PROBLEM: {p}")
        if not path:
            return 1
        print(f"zip={path}")
        args.target = path
        rep_problems = len(problems)
    else:
        rep_problems = 0
    if args.pin:
        pin, problems = read_pin(args.pin)
        for p in problems:
            print(f"PROBLEM: {p}")
        if problems:
            return 1
        for k in PIN_KEYS[:-1]:
            print(f"{k}={pin[k]}")
        return 0
    if not args.target:
        a.error("give a pack folder or zip (or --pin)")
    t0 = time.perf_counter()
    rep = check(args.target, args.app_version, args.blender, not args.no_render, not args.no_blender)
    for line in rep.lines():
        print(line)
    for line in rep.info:
        print(f"  {line}")
    secs = time.perf_counter() - t0
    if rep.ok and not rep_problems:
        print(f"OK – every pack check passed ({secs:.0f} s){' – WITHOUT the Blender checks' if args.no_blender else ''}")
        return 0
    n = len(rep.problems) + rep_problems
    print(f"FAILED – {n} problem{'s' if n != 1 else ''} ({secs:.0f} s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
