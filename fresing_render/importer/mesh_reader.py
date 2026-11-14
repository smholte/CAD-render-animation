"""Read a mesh model (glTF / GLB, OBJ; FBX through Blender) and write the same render cache as the STEP reader.

Task 0117. This module never imports bpy. It runs in its own process (Blender's own Python, started by
``runner.ImportJob``) and writes, in ``out_dir``, exactly what ``step_reader`` writes – ``tree.json`` (one node per
assembly / part) and ``meshes.npz`` (one triangle mesh per unique part: ``p``, ``n``, ``t``, ``f`` = the first
triangle of every face) – so everything after it (build, faces, joints, hover, decals, rules, model update) works
unchanged. A mesh has no CAD faces: ``core/mesh_faces.py`` splits it into flat, round and other faces and finds the
axes of the round ones (``axes`` / ``axis_faces``, as STEP stores them).

New in the cache, all optional (a STEP cache has none of them):
    u<mid>              float32 (n, 2): UVs, Blender's v (glTF's v turned over)
    meshes[mid]["file_material"]   index into info["materials"]
    info["materials"]   the file's materials: name, color (sRGB), metallic, roughness, alpha, base_texture /
                        normal_texture / mr_texture (files in out_dir/textures, relative paths)
    info["credit"], info["credit_text"]   the file's credit line and its full licence text ('' when none)
    info["source_kind"] = "mesh", info["options"], info["notes"]

The cache is in metres with Z up, whatever the file had: glTF is metres, Y up; OBJ has no units (``units``: Auto
guesses, see ``guess_units``) and is Y up by default; FBX and glTF files this reader cannot read itself (Draco or
meshopt compressed) are converted to a plain GLB by Blender's own importer and exporter in a background Blender
(``convert_blender.py``) and then read as glTF.

    python mesh_reader.py model.glb out_dir [--units auto|m|cm|mm|in|ft] [--up auto|y|z] [--split auto|on|off]
                                            [--convert-with <blender or a Python with bpy>]
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import urllib.parse

import numpy as np

try:                                   # inside the package (tests, Blender)
    from . import step_reader
    from ..core import mesh_faces
except ImportError:                    # run as a script by the import job
    _here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _here)
    sys.path.insert(0, os.path.join(_here, "..", "core"))
    import step_reader                 # noqa: E402
    import mesh_faces                  # noqa: E402

emit = step_reader.emit
CACHE_VERSION = step_reader.CACHE_VERSION
EXTENSIONS = (".glb", ".gltf", ".obj", ".fbx")
UNITS = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}
SPLIT_AUTO_MESHES = 5        # Split by loose parts "Auto": on when the file has fewer meshes than this
MAX_PIECES = 1000            # loose pieces of one mesh that become parts; the rest are one part "small pieces"
GUESS_MM_FROM = 500.0        # OBJ, units Auto: a biggest side of at least this many units is read as mm
CREDIT_MAX = 4000
CONVERTER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convert_blender.py")
# glTF extensions this reader reads itself (or may leave out without changing the shape)
_KNOWN = {"KHR_mesh_quantization", "KHR_materials_pbrSpecularGlossiness", "KHR_texture_transform",
          "KHR_materials_emissive_strength", "KHR_materials_ior", "KHR_materials_specular",
          "KHR_materials_transmission", "KHR_materials_volume", "KHR_materials_clearcoat", "KHR_materials_sheen",
          "KHR_materials_unlit", "KHR_lights_punctual", "KHR_materials_variants", "KHR_texture_basisu",
          "EXT_texture_webp", "KHR_materials_anisotropy", "KHR_materials_iridescence",
          "KHR_materials_dispersion", "EXT_mesh_gpu_instancing"}
_CONVERT = {"KHR_draco_mesh_compression", "EXT_meshopt_compression", "KHR_meshopt_compression"}


class MeshError(RuntimeError):
    """A file this reader cannot read (the message says why, in plain words)."""


class NeedsBlender(MeshError):
    """A file only Blender's own importer reads (FBX, compressed glTF)."""


# ---------------------------------------------------------------------------
# the model in between: file coordinates, any units
# ---------------------------------------------------------------------------

class Geom:
    """One triangle mesh with one material (a glTF primitive, an OBJ object's faces of one material)."""

    def __init__(self, name, pos, tri, nrm=None, uv=None, material=-1):
        self.name = name
        self.pos = np.asarray(pos, np.float64).reshape(-1, 3)
        self.tri = np.asarray(tri, np.int64).reshape(-1, 3)
        self.nrm = None if nrm is None else np.asarray(nrm, np.float64).reshape(-1, 3)
        self.uv = None if uv is None else np.asarray(uv, np.float64).reshape(-1, 2)
        self.material = material


class Model:
    def __init__(self):
        self.nodes: list[dict] = []        # name, parent, matrix (4x4, file coords), geoms [ids], instance
        self.geoms: list[Geom] = []
        self.materials: list[dict] = []
        self.images: list[dict] = []       # {"name", "data" (bytes) | "path", "ext"}
        self.credit = ""
        self.credit_text = ""
        self.notes: list[str] = []
        self.up = "y"                      # the file's up axis
        self.unit = 1.0                    # metres per file unit

    def node(self, name, parent=-1, matrix=None, geoms=(), instance=""):
        self.nodes.append({"name": name, "parent": parent, "matrix": np.eye(4) if matrix is None else matrix,
                           "geoms": list(geoms), "instance": instance})
        return len(self.nodes) - 1


def _note(model: Model, text: str) -> None:
    if text not in model.notes:
        model.notes.append(text)


def _clean_name(name, fallback: str) -> str:
    name = "".join(ch for ch in str(name or "") if ch >= " " and ch != "\x7f").strip()
    return name[:120] or fallback


# ---------------------------------------------------------------------------
# glTF / GLB
# ---------------------------------------------------------------------------

_COMP = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_SIZE = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}
_NORM = {5120: 127.0, 5121: 255.0, 5122: 32767.0, 5123: 65535.0}


def _load_gltf(path: str):
    """(json document, [buffer bytes]) of a .gltf or .glb file."""
    with open(path, "rb") as fh:
        data = fh.read()
    binary = None
    if data[:4] == b"glTF":
        if len(data) < 20:
            raise MeshError("the GLB file is cut off")
        version, length = struct.unpack_from("<II", data, 4)
        if version != 2:
            raise MeshError(f"glTF version {version}: only glTF 2.0 can be read (export it again as glTF 2.0)")
        pos, doc = 12, None
        while pos + 8 <= min(length, len(data)):
            size, kind = struct.unpack_from("<II", data, pos)
            chunk = data[pos + 8: pos + 8 + size]
            if kind == 0x4E4F534A and doc is None:
                doc = json.loads(chunk.decode("utf-8"))
            elif kind == 0x004E4942 and binary is None:
                binary = chunk
            pos += 8 + size + (-size % 4)
        if doc is None:
            raise MeshError("the GLB file has no JSON part")
    else:
        try:
            doc = json.loads(data.decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise MeshError(f"not a glTF file ({exc})") from exc
    if not isinstance(doc, dict):
        raise MeshError("not a glTF file")
    version = str(doc.get("asset", {}).get("version", "2.0"))
    if not version.startswith("2"):
        raise MeshError(f"glTF version {version}: only glTF 2.0 can be read (export it again as glTF 2.0)")
    buffers = []
    for k, buf in enumerate(doc.get("buffers", [])):
        uri = buf.get("uri")
        if uri is None:
            buffers.append(binary if (k == 0 and binary is not None) else b"")
            continue
        try:
            buffers.append(_read_uri(path, uri))
        except OSError as exc:
            raise MeshError(f"the file's data '{urllib.parse.unquote(uri)[:80]}' is missing next to it "
                            f"({exc.strerror or exc})") from exc
    return doc, buffers


def _read_uri(path: str, uri: str) -> bytes:
    if uri.startswith("data:"):
        head, _, body = uri.partition(",")
        return base64.b64decode(body) if head.endswith(";base64") else urllib.parse.unquote_to_bytes(body)
    full = os.path.join(os.path.dirname(os.path.abspath(path)), urllib.parse.unquote(uri))
    with open(full, "rb") as fh:
        return fh.read()


def _accessor(doc, buffers, index, cache: dict) -> np.ndarray:
    """An accessor as a float64 (count, size) array (normalised integers to 0..1 / -1..1)."""
    if index in cache:
        return cache[index]
    try:
        acc = doc["accessors"][index]
        comp = _COMP[acc["componentType"]]
        size = _SIZE[acc["type"]]
        count = int(acc["count"])
    except (KeyError, IndexError, TypeError) as exc:
        raise MeshError(f"accessor {index} is broken ({exc})") from exc
    item = np.dtype(comp).itemsize * size
    if "bufferView" in acc:
        view = doc["bufferViews"][acc["bufferView"]]
        buf = buffers[view.get("buffer", 0)]
        start = int(view.get("byteOffset", 0)) + int(acc.get("byteOffset", 0))
        stride = int(view.get("byteStride", 0) or item)
        need = start + stride * (count - 1) + item if count else start
        if need > len(buf):
            raise MeshError(f"accessor {index} reaches past the end of its buffer (the file is cut off)")
        if count == 0:
            arr = np.zeros((0, size), comp)
        elif stride == item:
            arr = np.frombuffer(buf, comp, count * size, start).reshape(count, size)
        else:
            raw = np.frombuffer(buf, np.uint8, stride * (count - 1) + item, start)
            rows = np.lib.stride_tricks.as_strided(raw, (count, item), (stride, 1))
            arr = np.ascontiguousarray(rows).view(comp).reshape(count, size)
    else:
        arr = np.zeros((count, size), comp)
    out = arr.astype(np.float64)
    if acc.get("normalized") and acc["componentType"] in _NORM:
        out = np.maximum(out / _NORM[acc["componentType"]], -1.0)
    sparse = acc.get("sparse")
    if sparse:
        n = int(sparse["count"])
        iv = doc["bufferViews"][sparse["indices"]["bufferView"]]
        ic = _COMP[sparse["indices"]["componentType"]]
        idx = np.frombuffer(buffers[iv.get("buffer", 0)], ic, n,
                            int(iv.get("byteOffset", 0)) + int(sparse["indices"].get("byteOffset", 0)))
        vv = doc["bufferViews"][sparse["values"]["bufferView"]]
        vals = np.frombuffer(buffers[vv.get("buffer", 0)], comp, n * size,
                             int(vv.get("byteOffset", 0)) + int(sparse["values"].get("byteOffset", 0)))
        vals = vals.reshape(n, size).astype(np.float64)
        if acc.get("normalized") and acc["componentType"] in _NORM:
            vals = np.maximum(vals / _NORM[acc["componentType"]], -1.0)
        out = out.copy()
        out[idx.astype(np.int64)] = vals
    cache[index] = out
    return out


def _node_matrix(nd: dict) -> np.ndarray:
    if "matrix" in nd:
        m = np.array(nd["matrix"], np.float64).reshape(4, 4).T
        return m
    t = np.array(nd.get("translation", (0, 0, 0)), np.float64)
    x, y, z, w = (float(v) for v in nd.get("rotation", (0, 0, 0, 1)))
    s = np.array(nd.get("scale", (1, 1, 1)), np.float64)
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * s
    m[:3, 3] = t
    return m


def _srgb(c: float) -> float:
    c = min(max(float(c), 0.0), 1.0)
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _image_ext(data: bytes, mime: str = "", name: str = "") -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    ext = os.path.splitext(name)[1].lower()
    if ext:
        return ext
    return {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")


def read_gltf(path: str) -> Model:
    doc, buffers = _load_gltf(path)
    model = Model()
    model.up, model.unit = "y", 1.0
    used = set(doc.get("extensionsUsed", [])) | set(doc.get("extensionsRequired", []))
    if used & _CONVERT:
        raise NeedsBlender(f"the file is compressed ({', '.join(sorted(used & _CONVERT))})")
    unknown = sorted(set(doc.get("extensionsRequired", [])) - _KNOWN)
    if unknown:
        raise MeshError(f"the file needs glTF extensions this app cannot read: {', '.join(unknown)}")
    if "KHR_texture_transform" in used:
        _note(model, "texture offsets / repeats (KHR_texture_transform) are left out")
    if doc.get("skins"):
        _note(model, "the model's bones (skin) are left out: it is read in the pose it was saved in")
    if doc.get("animations"):
        _note(model, "the file's own animations are left out (make the motion with joints)")
    _credit_gltf(model, doc)

    # images and materials
    images = doc.get("images", [])
    textures = doc.get("textures", [])

    def texture_image(info) -> int:
        """The image index of a texture reference, or -1."""
        if not isinstance(info, dict) or "index" not in info:
            return -1
        try:
            tex = textures[info["index"]]
        except (IndexError, TypeError):
            return -1
        src = tex.get("source")
        for ext in ("EXT_texture_webp", "KHR_texture_basisu"):
            src = tex.get("extensions", {}).get(ext, {}).get("source", src)
        return src if isinstance(src, int) and 0 <= src < len(images) else -1

    img_out: dict[int, int] = {}

    def image(k: int) -> int:
        if k < 0:
            return -1
        if k in img_out:
            return img_out[k]
        im = images[k]
        name = _clean_name(im.get("name") or os.path.basename(urllib.parse.unquote(im.get("uri", ""))), f"image{k}")
        try:
            if "bufferView" in im:
                view = doc["bufferViews"][im["bufferView"]]
                buf = buffers[view.get("buffer", 0)]
                off = int(view.get("byteOffset", 0))
                data = bytes(buf[off: off + int(view["byteLength"])])
            elif "uri" in im:
                data = _read_uri(path, im["uri"])
            else:
                raise OSError("no data")
        except (OSError, KeyError, IndexError, ValueError) as exc:
            _note(model, f"texture '{name}' is missing ({getattr(exc, 'strerror', None) or exc}): "
                         "its material shows its colour only")
            img_out[k] = -1
            return -1
        if not data:
            img_out[k] = -1
            return -1
        model.images.append({"name": os.path.splitext(name)[0], "data": data,
                             "ext": _image_ext(data, im.get("mimeType", ""), name)})
        img_out[k] = len(model.images) - 1
        return img_out[k]

    tex_coord: dict[int, int] = {}
    for k, m in enumerate(doc.get("materials", [])):
        pbr = m.get("pbrMetallicRoughness", {})
        sg = m.get("extensions", {}).get("KHR_materials_pbrSpecularGlossiness")
        factor = pbr.get("baseColorFactor", [1, 1, 1, 1])
        base_tex = pbr.get("baseColorTexture")
        metallic = float(pbr.get("metallicFactor", 1.0))
        rough = float(pbr.get("roughnessFactor", 1.0))
        if sg and "baseColorFactor" not in pbr and "baseColorTexture" not in pbr:
            factor = sg.get("diffuseFactor", [1, 1, 1, 1])
            base_tex = sg.get("diffuseTexture")
            metallic, rough = 0.0, 1.0 - float(sg.get("glossinessFactor", 1.0))
        factor = (list(factor) + [1, 1, 1, 1])[:4]
        alpha = float(factor[3]) if m.get("alphaMode", "OPAQUE") != "OPAQUE" else 1.0
        mat = {"name": _clean_name(m.get("name"), f"Material {k + 1}"),
               "color": [round(_srgb(c), 5) for c in factor[:3]], "linear": [float(c) for c in factor[:3]],
               "metallic": min(max(metallic, 0.0), 1.0), "roughness": min(max(rough, 0.0), 1.0),
               "alpha": min(max(alpha, 0.0), 1.0), "double_sided": bool(m.get("doubleSided", False))}
        if isinstance(base_tex, dict):
            tex_coord[k] = int(base_tex.get("texCoord", 0))
        for key, info in (("base_texture", base_tex), ("normal_texture", m.get("normalTexture")),
                          ("mr_texture", pbr.get("metallicRoughnessTexture"))):
            im = image(texture_image(info))
            if im >= 0:
                mat[key] = im
        model.materials.append(mat)

    # meshes -> geoms (one per primitive), cached per (mesh, primitive)
    acc_cache: dict = {}
    mesh_geoms: dict[int, list[int]] = {}
    lines_left = [0]

    def geoms_of(mi: int) -> list[int]:
        if mi in mesh_geoms:
            return mesh_geoms[mi]
        out = []
        try:
            mesh = doc["meshes"][mi]
        except (IndexError, TypeError):
            mesh_geoms[mi] = out
            return out
        mname = _clean_name(mesh.get("name"), f"Mesh {mi + 1}")
        for pk, prim in enumerate(mesh.get("primitives", [])):
            g = _primitive(doc, buffers, prim, acc_cache, mname, tex_coord)
            if g is None:
                lines_left[0] += 1
                continue
            model.geoms.append(g)
            out.append(len(model.geoms) - 1)
        mesh_geoms[mi] = out
        return out

    nodes = doc.get("nodes", [])
    scenes = doc.get("scenes", [])
    scene = doc.get("scene", 0)
    if scenes and isinstance(scene, int) and 0 <= scene < len(scenes):
        roots = list(scenes[scene].get("nodes", []))
    else:
        children = {c for nd in nodes for c in nd.get("children", [])}
        roots = [k for k in range(len(nodes)) if k not in children]
    seen: set = set()
    stack = [(k, -1) for k in reversed(roots)]
    while stack:
        k, parent = stack.pop()
        if not isinstance(k, int) or not 0 <= k < len(nodes) or k in seen:
            continue                                       # a node used twice (not allowed in glTF) or a cycle
        seen.add(k)
        nd = nodes[k]
        geoms = geoms_of(nd["mesh"]) if isinstance(nd.get("mesh"), int) else []
        if nd.get("extensions", {}).get("EXT_mesh_gpu_instancing"):
            _note(model, "GPU instances (EXT_mesh_gpu_instancing) are read once, at their node")
        name = _clean_name(nd.get("name") or (doc["meshes"][nd["mesh"]].get("name") if geoms else ""),
                           f"Node {k + 1}")
        idx = model.node(name, parent, _node_matrix(nd), geoms)
        for c in reversed(nd.get("children", [])):
            stack.append((c, idx))
    if lines_left[0]:
        _note(model, f"{lines_left[0]} part(s) drawn as points or lines are left out")
    return model


def _primitive(doc, buffers, prim, cache, name, tex_coord) -> Geom | None:
    mode = int(prim.get("mode", 4))
    if mode not in (4, 5, 6):
        return None
    attrs = prim.get("attributes", {})
    if "POSITION" not in attrs:
        return None
    if prim.get("extensions", {}).keys() & _CONVERT:
        raise NeedsBlender("the file is compressed")
    pos = _accessor(doc, buffers, attrs["POSITION"], cache)[:, :3]
    nrm = _accessor(doc, buffers, attrs["NORMAL"], cache)[:, :3] if "NORMAL" in attrs else None
    mat = prim.get("material", -1)
    mat = mat if isinstance(mat, int) and 0 <= mat < len(doc.get("materials", [])) else -1
    uv_set = f"TEXCOORD_{tex_coord.get(mat, 0)}"
    if uv_set not in attrs:
        uv_set = "TEXCOORD_0"
    uv = _accessor(doc, buffers, attrs[uv_set], cache)[:, :2] if uv_set in attrs else None
    if "indices" in prim:
        idx = _accessor(doc, buffers, prim["indices"], cache)[:, 0].astype(np.int64)
    else:
        idx = np.arange(len(pos), dtype=np.int64)
    if mode == 4:
        tri = idx[: len(idx) // 3 * 3].reshape(-1, 3)
    elif mode == 5:                                        # strip: every other triangle turned round
        if len(idx) < 3:
            return None
        a, b, c = idx[:-2], idx[1:-1], idx[2:]
        odd = np.arange(len(a)) % 2 == 1
        tri = np.stack((np.where(odd, b, a), np.where(odd, a, b), c), axis=1)
    else:                                                  # fan
        if len(idx) < 3:
            return None
        tri = np.stack((np.full(len(idx) - 2, idx[0]), idx[1:-1], idx[2:]), axis=1)
    if len(tri) and (tri.min() < 0 or tri.max() >= len(pos)):
        raise MeshError(f"'{name}' points at corners it does not have (the file is broken)")
    if uv is not None:
        uv = uv.copy()
        uv[:, 1] = 1.0 - uv[:, 1]                         # glTF's v runs down, Blender's up
    return Geom(name, pos, tri, nrm, uv, mat)


def _credit_gltf(model: Model, doc: dict) -> None:
    """The credit line from ``asset.extras`` (Sketchfab: title, author, license, source) and ``asset.copyright``."""
    asset = doc.get("asset", {}) if isinstance(doc.get("asset"), dict) else {}
    ex = asset.get("extras") if isinstance(asset.get("extras"), dict) else {}
    title, author, lic, src = (str(ex.get(k, "") or "").strip() for k in ("title", "author", "license", "source"))
    head = f"“{title}”" if title else ""
    if author:
        head = f"{head} by {author}" if head else f"By {author}"
    line = ", ".join(p for p in (head, lic, src) if p)
    copyright_ = str(asset.get("copyright", "") or "").strip()
    if copyright_ and copyright_ not in line:
        line = f"{line} – {copyright_}" if line else copyright_
    model.credit = _one_line(line)
    model.credit_text = line[:CREDIT_MAX]


def _one_line(text: str) -> str:
    return re.sub(r"\s+", " ", "".join(ch if ch >= " " or ch in "\n\t" else " " for ch in text)).strip()[:300]


def read_credit_files(model: Model, path: str) -> None:
    """A licence text next to the file (Sketchfab's license.txt, LICENSE*, README*): the credit's full text, and
    its line when the file itself has none."""
    folder = os.path.dirname(os.path.abspath(path))
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return
    pick = [n for n in names if re.match(r"(?i)^(license|licence|copying|credits?|readme|attribution)[^/]*\.(txt|md)$", n)
            or re.match(r"(?i)^(license|licence)$", n)]
    pick.sort(key=lambda n: (0 if n.lower().startswith(("license", "licence")) else 1, n.lower()))
    for name in pick[:1]:
        try:
            with open(os.path.join(folder, name), "rb") as fh:
                text = fh.read(CREDIT_MAX * 4).decode("utf-8", "replace")
        except OSError:
            continue
        text = "".join(ch for ch in text if ch >= " " or ch in "\n\t").strip()
        if not text:
            continue
        full = f"{model.credit_text}\n\n{name}:\n{text}" if model.credit_text else text
        model.credit_text = full[:CREDIT_MAX]
        line = _credit_line_from_text(text)
        has_licence = re.search(r"(?i)licen[cs]|CC[- ]BY|creative commons", model.credit or "")
        if not model.credit or (not has_licence and re.search(r"(?i)licen[cs]ed under", line)):
            model.credit = line                      # Sketchfab's own attribution line names the licence


def _credit_line_from_text(text: str) -> str:
    """One line from a licence text: Sketchfab's "<title> by <author> is licensed under <licence>" when there,
    else the first line that names a licence or an author, else the first line."""
    lines = [ln.strip(" -*#\t") for ln in text.splitlines() if ln.strip(" -*#\t")]
    for pattern in (r"(?i)licen[cs]ed under", r"(?i)\bby\b.*\bCC\b|creative commons|CC[- ]BY"):
        for ln in lines:
            if re.search(pattern, ln):
                return _one_line(ln)
    for ln in lines:
        if re.search(r"(?i)author|licen[cs]e|copyright|©", ln):
            return _one_line(ln)
    return _one_line(lines[0]) if lines else ""


# ---------------------------------------------------------------------------
# OBJ / MTL
# ---------------------------------------------------------------------------

def _text_lines(path: str) -> list[str]:
    with open(path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("utf-8", "replace") if not raw.startswith(b"\xef\xbb\xbf") else raw[3:].decode("utf-8", "replace")
    text = text.replace("\\\r\n", " ").replace("\\\n", " ")
    return text.splitlines()


def _floats(rows: list[str], width: int) -> np.ndarray:
    """'v 1 2 3' style rows (without the keyword) -> (n, width) floats; short rows are filled with 0."""
    if not rows:
        return np.zeros((0, width))
    out = np.zeros((len(rows), width))
    for i, r in enumerate(rows):
        vals = r.split()[:width]
        try:
            out[i, :len(vals)] = [float(v) for v in vals]
        except ValueError:
            out[i] = 0.0
    return out


def read_mtl(path: str, model: Model, by_name: dict) -> None:
    try:
        lines = _text_lines(path)
    except OSError:
        _note(model, f"material file {os.path.basename(path)} is missing: parts get a grey look")
        return
    folder = os.path.dirname(path)
    cur = None
    for line in lines:
        parts = line.strip().split(None, 1)
        if not parts or parts[0].startswith("#"):
            continue
        key, rest = parts[0], (parts[1].strip() if len(parts) > 1 else "")
        low = key.lower()
        if low == "newmtl":
            cur = {"name": _clean_name(rest, f"Material {len(model.materials) + 1}"), "color": [0.8, 0.8, 0.8],
                   "linear": [0.6, 0.6, 0.6], "metallic": 0.0, "roughness": 0.5, "alpha": 1.0, "double_sided": False}
            model.materials.append(cur)
            by_name[rest] = len(model.materials) - 1
        elif cur is None:
            continue
        elif low == "kd":
            v = _floats([rest], 3)[0]
            cur["linear"] = [float(min(max(c, 0.0), 1.0)) for c in v]
            cur["color"] = [round(_srgb(c), 5) for c in cur["linear"]]
        elif low == "d":
            cur["alpha"] = float(min(max(_floats([rest], 1)[0][0], 0.0), 1.0))
        elif low == "tr":
            cur["alpha"] = float(min(max(1.0 - _floats([rest], 1)[0][0], 0.0), 1.0))
        elif low == "ns":
            ns = float(_floats([rest], 1)[0][0])
            cur["roughness"] = round(float(min(max(1.0 - math.sqrt(max(ns, 0.0) / 1000.0), 0.0), 1.0)), 4)
        elif low == "pm":
            cur["metallic"] = float(min(max(_floats([rest], 1)[0][0], 0.0), 1.0))
        elif low == "pr":
            cur["roughness"] = float(min(max(_floats([rest], 1)[0][0], 0.0), 1.0))
        elif low in ("map_kd", "map_bump", "bump", "norm", "map_norm"):
            file = _map_file(rest)
            if not file:
                continue
            full = os.path.join(folder, file.replace("\\", os.sep))
            try:
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError:
                _note(model, f"texture '{file}' is missing: its material shows its colour only")
                continue
            model.images.append({"name": os.path.splitext(os.path.basename(file))[0], "data": data,
                                 "ext": _image_ext(data, "", file)})
            cur["base_texture" if low == "map_kd" else "normal_texture"] = len(model.images) - 1
            if low != "map_kd":
                cur["normal_is_bump"] = low in ("map_bump", "bump")


def _map_file(rest: str) -> str:
    """The file name of an MTL map line ('-bm 0.5 -s 1 1 tex.png' -> 'tex.png'); names may contain spaces."""
    toks = rest.split()
    takes = {"-blendu": 1, "-blendv": 1, "-bm": 1, "-boost": 1, "-cc": 1, "-clamp": 1, "-imfchan": 1, "-mm": 2,
             "-o": 3, "-s": 3, "-t": 3, "-texres": 1, "-type": 1}
    i = 0
    while i < len(toks) and toks[i].startswith("-") and toks[i].lower() in takes:
        n = takes[toks[i].lower()]
        i += 1
        while n and i < len(toks):
            try:
                float(toks[i])
            except ValueError:
                if toks[i - 1].lower() not in ("-blendu", "-blendv", "-cc", "-clamp", "-imfchan", "-type"):
                    break
            i += 1
            n -= 1
    return " ".join(toks[i:]).strip().strip('"')


def read_obj(path: str) -> Model:
    model = Model()
    model.up = "y"
    lines = _text_lines(path)
    v_rows, vt_rows, vn_rows = [], [], []
    groups: list[list] = []                 # [object name, material name, face corner lists]
    by_key: dict = {}
    mtl_by_name: dict[str, int] = {}
    obj_name, grp_name, mat_name = "", "", ""
    any_o = any(ln.lstrip().startswith("o ") for ln in lines)
    cur = None
    n_v = n_vt = n_vn = 0

    def target():
        nonlocal cur
        key = ((obj_name if any_o else grp_name) or "Mesh", mat_name)
        cur = by_key.get(key)
        if cur is None:
            cur = [key[0], mat_name, []]
            by_key[key] = cur
            groups.append(cur)
        return cur

    for line in lines:
        s = line.strip()
        if not s or s[0] == "#":
            continue
        head, _, rest = s.partition(" ")
        if head == "v":
            v_rows.append(rest)
            n_v += 1
        elif head == "vt":
            vt_rows.append(rest)
            n_vt += 1
        elif head == "vn":
            vn_rows.append(rest)
            n_vn += 1
        elif head == "f":
            corners = []
            for tok in rest.split():
                ids = tok.split("/")
                try:
                    vi = int(ids[0])
                    ti = int(ids[1]) if len(ids) > 1 and ids[1] else 0
                    ni = int(ids[2]) if len(ids) > 2 and ids[2] else 0
                except ValueError:
                    continue
                vi = vi + n_v + 1 if vi < 0 else vi                # negative = counted back from here
                ti = ti + n_vt + 1 if ti < 0 else ti
                ni = ni + n_vn + 1 if ni < 0 else ni
                corners.append((vi - 1, ti - 1, ni - 1))
            if len(corners) >= 3:
                (cur if cur is not None and cur[0] == ((obj_name if any_o else grp_name) or "Mesh")
                 and cur[1] == mat_name else target())[2].append(corners)
        elif head == "o":
            obj_name = _clean_name(rest, "Mesh")
            cur = None
        elif head == "g":
            grp_name = _clean_name(rest, "Mesh")
            cur = None
        elif head == "usemtl":
            mat_name = rest.strip()
            cur = None
        elif head == "mtllib":
            for name in _mtl_names(rest, os.path.dirname(path)):
                read_mtl(os.path.join(os.path.dirname(path), name), model, mtl_by_name)
    v = _floats(v_rows, 3)
    vt = _floats(vt_rows, 2)
    vn = _floats(vn_rows, 3)
    if not len(v):
        raise MeshError("the OBJ file has no corners (v lines)")
    names_used: dict[str, int] = {}
    part_nodes: dict[str, int] = {}
    for oname, mname, faces in groups:
        if not faces:
            continue
        g = _obj_geom(oname, faces, v, vt, vn)
        if g is None:
            continue
        g.material = mtl_by_name.get(mname, -1)
        if mname and g.material < 0 and mname not in names_used:
            _note(model, f"material '{mname}' is not in the material file: grey")
        names_used[mname] = 1
        model.geoms.append(g)
        part_nodes.setdefault(oname, [])
        part_nodes[oname].append(len(model.geoms) - 1)
    for oname, gl in part_nodes.items():
        model.node(oname, -1, None, gl)
    if not model.geoms:
        raise MeshError("the OBJ file has no faces")
    return model


def _mtl_names(rest: str, folder: str) -> list[str]:
    """mtllib names (several allowed, a name may contain spaces when the whole line is one file)."""
    if os.path.isfile(os.path.join(folder, rest.strip())):
        return [rest.strip()]
    return rest.split()


def _obj_geom(name, faces, v, vt, vn) -> Geom | None:
    """The faces of one object and material: fans of triangles; corners (v, vt, vn) made unique."""
    tris = []
    for f in faces:
        a = f[0]
        for k in range(1, len(f) - 1):
            tris.append((a, f[k], f[k + 1]))
    corners = np.array(tris, np.int64).reshape(-1, 3)                     # (3 m, 3): v, vt, vn per corner
    bad = (corners[:, 0] < 0) | (corners[:, 0] >= len(v))
    if bad.any():
        keep = ~bad.reshape(-1, 3).any(axis=1)
        corners = corners.reshape(-1, 3, 3)[keep].reshape(-1, 3)
    if not len(corners):
        return None
    corners[(corners[:, 1] < 0) | (corners[:, 1] >= len(vt)), 1] = -1
    corners[(corners[:, 2] < 0) | (corners[:, 2] >= len(vn)), 2] = -1
    uniq, inv = np.unique(corners, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    pos = v[uniq[:, 0]]
    has_uv = (uniq[:, 1] >= 0).any()
    has_n = (uniq[:, 2] >= 0).all()
    uv = np.where(uniq[:, 1:2] >= 0, vt[np.maximum(uniq[:, 1], 0)], 0.0) if has_uv and len(vt) else None
    nrm = vn[np.maximum(uniq[:, 2], 0)] if has_n and len(vn) else None
    return Geom(name, pos, inv.reshape(-1, 3), nrm, uv)


# ---------------------------------------------------------------------------
# FBX and compressed glTF: Blender's own importer -> a plain GLB
# ---------------------------------------------------------------------------

def convert_with_blender(path: str, out_dir: str, converter: str | None) -> str:
    """Convert ``path`` to a GLB in ``out_dir`` with Blender's importer and exporter. ``converter``: Blender's own
    program (the app passes ``bpy.app.binary_path``) or a Python that has the bpy module (tests)."""
    if not converter:
        raise MeshError("this file needs Blender's own importer, and no Blender was given to the reader")
    glb = os.path.join(out_dir, "converted.glb")
    if "blender" in os.path.basename(converter).lower():
        cmd = [converter, "-b", "--factory-startup", "--python", CONVERTER, "--", path, glb]
    else:
        cmd = [converter, CONVERTER, path, glb]
    env = dict(os.environ)
    for var in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONPATH"):
        env.pop(var, None)              # the app's search path (set for this reader) holds Blender's scripts' bpy
    kwargs: dict = {}
    job = None
    if os.name == "nt":
        kwargs["creationflags"] = 0x08000000                         # CREATE_NO_WINDOW
        try:
            job, assign = step_reader._kill_on_close_job()           # Blender ends when the reader ends
        except Exception:
            job, assign = None, None
    else:
        kwargs["preexec_fn"] = step_reader._die_with_parent
    emit("convert", 5, "Reading the file with Blender's own importer")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            env=env, text=True, encoding="utf-8", errors="replace", **kwargs)
    if os.name == "nt" and job is not None:
        try:
            assign(proc)
        except Exception:
            pass
    tail: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if line.startswith("FRCONVERT "):
            emit("convert", 15, line[10:])
        elif line:
            tail.append(line)
            del tail[:-20]
    proc.wait()
    if proc.returncode != 0 or not os.path.isfile(glb):
        why = next((ln[len("FRERROR "):] for ln in reversed(tail) if ln.startswith("FRERROR ")), "")
        raise MeshError(f"Blender could not read the file{': ' + why if why else ''} "
                        f"({' / '.join(tail[-3:]) if not why else 'code ' + str(proc.returncode)})")
    return glb


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------

def _flat(g: Geom) -> Geom:
    """No normals in the file: flat normals (glTF's rule), each triangle its own corners."""
    p = g.pos[g.tri].reshape(-1, 3)
    uv = g.uv[g.tri].reshape(-1, 2) if g.uv is not None else None
    a, b, c = p[0::3], p[1::3], p[2::3]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.where(ln > 0, n / np.where(ln > 0, ln, 1.0), np.array([0.0, 0.0, 1.0]))
    return Geom(g.name, p, np.arange(len(p)).reshape(-1, 3), np.repeat(n, 3, axis=0), uv, g.material)


def _clean_normals(nrm: np.ndarray, pos: np.ndarray, tri: np.ndarray) -> np.ndarray:
    """Normals of length ~1; broken ones (0, NaN) from the triangles around the corner."""
    nrm = np.where(np.isfinite(nrm), nrm, 0.0)
    ln = np.linalg.norm(nrm, axis=1)
    bad = ln < 0.5
    nrm = nrm / np.where(ln > 0, ln, 1.0)[:, None]
    if bad.any() and len(tri):
        v0, v1, v2 = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
        fn = np.cross(v1 - v0, v2 - v0)
        acc = np.zeros_like(pos)
        for k in range(3):
            np.add.at(acc, tri[:, k], fn)
        al = np.linalg.norm(acc, axis=1, keepdims=True)
        acc = np.where(al > 0, acc / np.where(al > 0, al, 1.0), np.array([0.0, 0.0, 1.0]))
        nrm[bad] = acc[bad]
    return nrm


def guess_units(size: float) -> str:
    """OBJ without units: a biggest side of ``GUESS_MM_FROM`` units or more is mm, else metres."""
    return "mm" if size >= GUESS_MM_FROM else "m"


def _axes_matrix(up: str) -> np.ndarray:
    """File axes -> the app's (Z up). Y up: (x, y, z) -> (x, -z, y)."""
    if up == "y":
        return np.array([[1.0, 0, 0], [0, 0, -1.0], [0, 1.0, 0]])
    return np.eye(3)


def _world_size(model: Model) -> float:
    """The biggest side of the whole model in file units (with the node transforms)."""
    world: list[np.ndarray] = []
    mats: list[np.ndarray] = []
    for nd in model.nodes:
        m = nd["matrix"] if nd["parent"] < 0 else mats[nd["parent"]] @ nd["matrix"]
        mats.append(m)
        for gi in nd["geoms"]:
            p = model.geoms[gi].pos
            if len(p):
                lo, hi = p.min(axis=0), p.max(axis=0)
                corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
                world.append(corners @ m[:3, :3].T + m[:3, 3])
    if not world:
        return 0.0
    w = np.concatenate(world)
    w = w[np.isfinite(w).all(axis=1)]
    return float((w.max(axis=0) - w.min(axis=0)).max()) if len(w) else 0.0


def _pieces(g: Geom, max_pieces: int) -> list[np.ndarray]:
    """The triangle sets of ``g``'s loose pieces, biggest (area) first; past ``max_pieces`` the rest is one set."""
    if len(g.tri) == 0:
        return [np.arange(0)]
    lab = mesh_faces.loose_parts(g.pos, g.tri)
    k = int(lab.max()) + 1 if len(lab) else 0
    if k <= 1:
        return [np.arange(len(g.tri))]
    a, b, c = g.pos[g.tri[:, 0]], g.pos[g.tri[:, 1]], g.pos[g.tri[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    size = np.bincount(lab, weights=area, minlength=k)
    rank = np.lexsort((np.arange(k), -size))                      # biggest first, then file order
    order = np.argsort(lab, kind="stable")
    bounds = np.searchsorted(lab[order], np.arange(k + 1))
    sets = [order[bounds[r]: bounds[r + 1]] for r in rank]
    if len(sets) > max_pieces:
        sets = sets[: max_pieces - 1] + [np.sort(np.concatenate(sets[max_pieces - 1:]))]
    return sets


def _sub(g: Geom, tris: np.ndarray, name: str) -> Geom:
    t = g.tri[tris]
    used, inv = np.unique(t.reshape(-1), return_inverse=True)
    return Geom(name, g.pos[used], inv.reshape(-1, 3),
                None if g.nrm is None else g.nrm[used], None if g.uv is None else g.uv[used], g.material)


# ---------------------------------------------------------------------------
# model -> cache
# ---------------------------------------------------------------------------

def read_model(path: str, out_dir: str, converter: str | None = None) -> Model:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        try:
            model = read_gltf(path)
        except NeedsBlender as exc:
            glb = convert_with_blender(path, out_dir, converter)
            model = read_gltf(glb)
            _note(model, f"read through Blender's own glTF importer: {exc}")
            os.remove(glb)
    elif ext == ".obj":
        model = read_obj(path)
    elif ext == ".fbx":
        glb = convert_with_blender(path, out_dir, converter)
        model = read_gltf(glb)
        model.credit = model.credit_text = ""               # Blender's exporter wrote its own asset text
        _note(model, "FBX: read with Blender's own FBX importer (units and axes from the file's header)")
        os.remove(glb)
    else:
        raise MeshError(f"'{ext}' files cannot be read: glTF (.glb, .gltf), OBJ and FBX can")
    read_credit_files(model, path)
    return model


def read_mesh(path: str, out_dir: str, units: str = "auto", up: str = "auto", split: str = "auto",
              converter: str | None = None) -> dict:
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    emit("read", 2, "Reading mesh file")
    model = read_model(path, out_dir, converter)
    ext = os.path.splitext(path)[1].lower()
    t_read = time.time() - t0

    # units and up axis
    size = _world_size(model)
    if ext == ".obj":
        unit_name = units if units in UNITS else guess_units(size)
        if units not in UNITS:
            _note(model, f"units guessed: {unit_name} (the model's biggest side is {size:,.4g} units, "
                         f"{size * UNITS[unit_name]:,.4g} m) – pick the units in the import dialog if this is wrong")
        model.unit = UNITS[unit_name]
        model.up = up if up in ("y", "z") else "y"
    else:
        unit_name = "m"
        if units in UNITS and units != "m":
            _note(model, f"{ext[1:].upper()} files are in metres: the units choice ({units}) is not used")
        if up in ("y", "z") and up != "y":
            _note(model, f"{ext[1:].upper()} files are Y up: the up axis choice is not used")
    axes = _axes_matrix(model.up)
    s = model.unit
    conv = np.eye(4)
    conv[:3, :3] = axes * s
    conv_inv = np.linalg.inv(conv)

    # split by loose parts
    n_meshes = len({tuple(nd["geoms"]) for nd in model.nodes if nd["geoms"]})
    do_split = split == "on" or (split == "auto" and n_meshes < SPLIT_AUTO_MESHES)
    emit("structure", 20, "Building the parts")

    # cache meshes: (geom, piece) -> mesh id
    mesh_meta: list[dict] = []
    arrays: dict[str, np.ndarray] = {}
    geom_pieces: dict[int, list[tuple[int, str]]] = {}         # geom -> [(mesh id, " 2" / " small pieces")]
    used_geoms = [gi for nd in model.nodes for gi in nd["geoms"]]
    order_geoms = list(dict.fromkeys(used_geoms))
    total_tris = sum(len(model.geoms[gi].tri) for gi in order_geoms) or 1
    done_tris = 0
    t1 = time.time()
    pieces_note = 0
    for gi in order_geoms:
        g = model.geoms[gi]
        if g.nrm is None or len(g.nrm) != len(g.pos):
            g = _flat(g)
        pos = g.pos @ conv[:3, :3].T
        ok = np.isfinite(pos).all(axis=1)
        if not ok.all():
            bad_t = ~ok[g.tri].all(axis=1)
            g = Geom(g.name, g.pos, g.tri[~bad_t], g.nrm, g.uv, g.material)
            pos = np.where(ok[:, None], pos, 0.0)
            _note(model, f"'{g.name}': corners with no number (NaN) are left out")
        g = Geom(g.name, pos, g.tri, g.nrm @ axes.T if g.nrm is not None else None, g.uv, g.material)
        sets = _pieces(g, MAX_PIECES) if do_split else [np.arange(len(g.tri))]
        if len(sets) > 1 and len(sets) == MAX_PIECES:
            pieces_note += 1
        out = []
        for k, ts in enumerate(sets):
            sub = _sub(g, ts, g.name) if len(sets) > 1 else g
            mid = len(mesh_meta)
            small = len(sets) == MAX_PIECES and k == len(sets) - 1
            suffix = "" if len(sets) == 1 else (" small pieces" if small else f" {k + 1}")
            mesh_meta.append(_store_mesh(arrays, mid, sub, g.name + suffix))
            out.append((mid, suffix))
        geom_pieces[gi] = out
        done_tris += len(g.tri)
        emit("mesh", 20 + 70 * done_tris / total_tris, f"Finding faces: {done_tris:,} of {total_tris:,} triangles")
    if pieces_note:
        _note(model, f"more than {MAX_PIECES - 1} loose pieces in one mesh: the smallest are one part 'small pieces'")
    t_mesh = time.time() - t1

    # nodes
    nodes: list[dict] = []
    idx_of: dict[int, int] = {}
    has_geom = _subtree_has_geom(model)
    kids: dict[int, list[int]] = {}
    for c, cn in enumerate(model.nodes):
        kids.setdefault(cn["parent"], []).append(c)
    counts: dict = {}

    def add(name, parent, matrix, kind, mesh=-1, color=None, material="", instance=""):
        key = (parent, name)
        counts[key] = counts.get(key, 0) + 1
        puid = nodes[parent]["uid"] if parent >= 0 else ""
        uid = f"{puid}/{name}#{counts[key]}" if puid else f"{name}#{counts[key]}"
        node = {"uid": uid, "name": name, "instance": instance, "parent": parent,
                "matrix": matrix, "kind": kind, "mesh": mesh, "color": color}
        if material:
            node["material"] = material
        nodes.append(node)
        return len(nodes) - 1

    def part_of(gi, parent, matrix, name):
        """One geom under ``parent``: a part, or an assembly of its loose pieces."""
        pieces = geom_pieces[gi]
        mat = model.materials[model.geoms[gi].material] if model.geoms[gi].material >= 0 else None
        colour = mat["color"] if mat else None
        mname = mat["name"] if mat else ""
        if len(pieces) == 1:
            return add(name, parent, matrix, "part", pieces[0][0], colour, mname)
        asm = add(name, parent, matrix, "assembly")
        for mid, suffix in pieces:
            add(name + suffix, asm, None, "part", mid, colour, mname)
        return asm

    for k, nd in enumerate(model.nodes):
        if not has_geom[k]:
            continue
        parent = idx_of.get(nd["parent"], -1)
        m = conv @ nd["matrix"] @ conv_inv
        mat = _rows(m)
        geoms = nd["geoms"]
        children = any(has_geom[c] for c in kids.get(k, ()))
        if len(geoms) == 1 and not children:
            idx_of[k] = part_of(geoms[0], parent, mat, nd["name"])
            continue
        idx_of[k] = add(nd["name"], parent, mat, "assembly")
        for gi in geoms:
            g = model.geoms[gi]
            mname = model.materials[g.material]["name"] if g.material >= 0 else ""
            part_of(gi, idx_of[k], None, (mname if len(geoms) > 1 and mname else nd["name"]))
    if not any(n["kind"] == "part" for n in nodes):
        raise MeshError("the file has no faces to show (only points, lines, cameras or lights)")

    # textures
    tex_dir = os.path.join(out_dir, "textures")
    img_files: dict[int, str] = {}
    for k, im in enumerate(model.images):
        if not any(m.get(key) == k for m in model.materials for key in ("base_texture", "normal_texture", "mr_texture")):
            continue
        os.makedirs(tex_dir, exist_ok=True)
        safe = re.sub(r"[^\w.-]+", "_", im["name"])[:40] or "texture"
        rel = f"textures/{k:03d}_{safe}{im['ext']}"
        with open(os.path.join(out_dir, rel), "wb") as fh:
            fh.write(im["data"])
        img_files[k] = rel
    materials = []
    for m in model.materials:
        out = {key: m[key] for key in ("name", "color", "metallic", "roughness", "alpha", "double_sided") if key in m}
        for key in ("base_texture", "normal_texture", "mr_texture"):
            if m.get(key, -1) in img_files:
                out[key] = img_files[m[key]]
        if m.get("normal_is_bump"):
            out["normal_is_bump"] = True
        materials.append(out)

    emit("write", 96, "Writing cache")
    np.savez(os.path.join(out_dir, "meshes.npz"), **arrays)
    n_parts = sum(1 for n in nodes if n["kind"] == "part")
    tri_total = sum(m["tris"] for m in mesh_meta)
    info = {
        "version": CACHE_VERSION,
        "source": os.path.abspath(path),
        "source_size": os.path.getsize(path),
        "source_mtime": os.path.getmtime(path),
        "source_kind": "mesh",
        "quality": "mesh",
        "units": "m",
        "options": {"units": unit_name, "up": model.up, "split": bool(do_split), "format": ext[1:]},
        "credit": model.credit,
        "credit_text": model.credit_text,
        "notes": model.notes,
        "materials": materials,
        "nodes": nodes,
        "meshes": mesh_meta,
        "stats": {
            "unique_parts": len(mesh_meta),
            "placed_parts": n_parts,
            "triangles_unique": int(tri_total),
            "seconds_read": round(t_read, 1),
            "seconds_faces": round(t_mesh, 1),
            "faces": int(sum(m.get("faces", 0) for m in mesh_meta)),
            "round_faces": int(sum(len(m["axis_faces"]) // 3 for m in mesh_meta)),
            "seconds_total": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(out_dir, "tree.json"), "w", encoding="utf-8") as fh:
        json.dump(info, fh)
    emit("done", 100, "Import finished", stats=info["stats"])
    return info


def _rows(m: np.ndarray) -> list:
    return [[float(x) for x in row] for row in m]


def _subtree_has_geom(model: Model) -> list[bool]:
    has = [bool(nd["geoms"]) for nd in model.nodes]
    for k in range(len(model.nodes) - 1, -1, -1):           # children come after their parent
        p = model.nodes[k]["parent"]
        if has[k] and p >= 0:
            has[p] = True
    return has


def _store_mesh(arrays: dict, mid: int, g: Geom, name: str) -> dict:
    """One cache mesh: faces found, triangles ordered per face, axes of the round faces."""
    pos, tri = g.pos, g.tri
    nrm = _clean_normals(g.nrm, pos, tri) if g.nrm is not None else np.zeros_like(pos)
    meta = {"name": name, "tris": int(len(tri)), "palette": [], "bbox": None, "axes": [], "axis_faces": []}
    if g.material >= 0:
        meta["file_material"] = int(g.material)
    if len(tri):
        fs = mesh_faces.split(pos, tri, nrm)
        tri = tri[fs.order]
        meta["axes"] = [[float(v) for v in ax] for ax in fs.axes]
        meta["axis_faces"] = [int(v) for v in fs.axis_faces]
        meta["faces"] = int(len(fs.starts) - 1)
        if len(fs.starts) >= 2:
            arrays[f"f{mid}"] = np.asarray(fs.starts, np.int32)
    arrays[f"p{mid}"] = pos.astype(np.float32)
    arrays[f"n{mid}"] = nrm.astype(np.float32)
    arrays[f"t{mid}"] = tri.astype(np.int32)
    if g.uv is not None and len(g.uv) == len(pos):
        arrays[f"u{mid}"] = np.where(np.isfinite(g.uv), g.uv, 0.0).astype(np.float32)
    if len(pos):
        meta["bbox"] = [pos.min(axis=0).tolist(), pos.max(axis=0).tolist()]
    return meta


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    step_reader._no_crash_dialog()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path")
    ap.add_argument("out_dir")
    ap.add_argument("--units", default="auto", choices=["auto"] + sorted(UNITS))
    ap.add_argument("--up", default="auto", choices=["auto", "y", "z"])
    ap.add_argument("--split", default="auto", choices=["auto", "on", "off"])
    ap.add_argument("--convert-with", default="")
    args = ap.parse_args(argv)
    try:
        read_mesh(args.path, args.out_dir, args.units, args.up, args.split, args.convert_with or None)
    except MeshError as exc:
        emit("error", 100, str(exc))
        return 1
    except Exception as exc:                       # never a bare traceback for the user: say what and where
        emit("error", 100, f"Could not read the mesh file: {exc.__class__.__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
