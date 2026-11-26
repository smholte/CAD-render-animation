"""Web 3D model (task 0099): a single ``.glb`` of the machine with its looks baked to textures, and a viewer page.

No Blender here: the glTF 2.0 writer and reader, the box-projected UVs, welding corners into vertices, seamless tiles,
the size words and the one-file viewer page. ``blender/web3d.py`` reads the project and bakes the looks.

Units: metres, Blender's Z-up axes inside the meshes and nodes; one root node turns the whole model to glTF's Y-up.
UVs: in tiles of ``TILE_M`` (a 0.2 m square of the look), so a texture lands at the scale of the renders.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import os
import struct
import zlib

import numpy as np

from . import meshopt, web3d_keys

TILE_M = 0.2                       # one texture tile covers this square of a part (metres)
SIZES = (512, 1024, 2048)          # Texture size choices (pixels per tile side)
DEFAULT_SIZE = 1024
ATLAS_MAX = 2048                   # largest bake image (pixels per side): 4 tiles of 1024, 1 of 2048 (task 0105: 4096
                                   # needed 5.5 GB on the demo vessel at 2048 px)
FLAT = 1.5 / 255                   # a tile whose values spread less than this is one number (a glTF factor)
POS_STEP = 0.00005                 # m: 16-bit points in steps of at most 0.05 mm (a decal floats 0.2 mm above its face)
POS_STEP_BIG = 0.001               # m: ... and of at most 1 mm on a big part that carries no decal (a 65 m hull)
POS_STEP_PACKED = POS_STEP           # m: compressed files: points in steps of at least 0.05 mm, not 1/65000 of the part
                                   # (finer steps are bigger numbers to pack; Heavy 17.9 MB at 0.02 mm, 17.2 at 0.05)
UV_Q = 128                         # 16-bit UVs: steps of 1/128 tile (1.6 mm); the looks scale them back
UV_TRANSFORM = {"KHR_texture_transform": {"scale": [1.0 / UV_Q, 1.0 / UV_Q]}}
JPG_QUALITY = {"color": 86, "orm": 86, "normal": 92}
WEBP_QUALITY = {"color": 86, "orm": 86, "normal": 92, "light": 92}   # task 0175 (0149: q86 looks, q92 light)
WEBP = "EXT_texture_webp"
MV_VERSION = "4.4.0"               # model-viewer, vendored in fresing_render/web/
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
MV_FILE = "model-viewer-umd.min.js"
MESHOPT = "EXT_meshopt_compression"
COMPRESS_FROM = 200_000            # triangles: "Smaller file" is ticked by itself from this many (task 0105)

# Blender (Z up) -> glTF (Y up): a turn of -90° about X, as a quaternion (x, y, z, w)
Z_UP_TO_Y_UP = (-math.sqrt(0.5), 0.0, 0.0, math.sqrt(0.5))

# glTF numbers
FLOAT, BYTE, UBYTE, SHORT, USHORT, UINT = 5126, 5120, 5121, 5122, 5123, 5125
ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER = 34962, 34963
REPEAT, CLAMP, LINEAR, LINEAR_MIPMAP_LINEAR = 10497, 33071, 9729, 9987
_COMPONENTS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_SIZES = {FLOAT: 4, BYTE: 1, UBYTE: 1, SHORT: 2, USHORT: 2, UINT: 4}
_NP = {FLOAT: np.float32, BYTE: np.int8, UBYTE: np.uint8, SHORT: np.int16, USHORT: np.uint16, UINT: np.uint32}


class Cancelled(Exception):
    """The export was cancelled: nothing was written."""


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------

def mb(n: int) -> str:
    """File size in words: '0.4 MB', '12 MB'."""
    if n < 10e6:
        return f"{n / 1e6:.1f} MB"
    return f"{n / 1e6:.0f} MB"


# -- looks baked on a part's own UVs (task 0161, 0147 row 10) ---------------------------------------------------
OWN_PADDING = 4                    # px round each chart of a part's own bake (2 x this between two charts)
OWN_MARGIN = 6                     # px the bake extends each chart's edge (JPG blocks and mipmaps stay in its colour)
OWN_FILL = 0.5                     # first guess: the charts fill this share of the picture
OWN_DETAIL_MM = 10.0               # coarser than this per pixel: the marine looks' fine streaks and barnacles are lost
OWN_M = 1.0                        # texels per metre of a part's own bake = texture size / this (1024 -> 1 mm)
OWN_BUDGET = 8_000_000             # texels of all parts' own bakes together, per channel (two pictures of 2048 px)
# task 0165: "Marine detail" per export. Fine = pictures of 4096 px for these own bakes only (every other bake stays
# at ATLAS_MAX), four times the texels, charts packed tighter. Normal is today's numbers, bit for bit.
MARINE_DETAILS = ("NORMAL", "FINE")
OWN_BUDGETS = {"NORMAL": OWN_BUDGET, "FINE": 4 * OWN_BUDGET}
OWN_MAX_PX = {"NORMAL": ATLAS_MAX, "FINE": 2 * ATLAS_MAX}
OWN_FILLS = {"NORMAL": OWN_FILL, "FINE": 0.75}
OWN_BYTES_PER_TEXEL = 0.12         # file bytes per texel, all channels (measured on a plain growth tower: 0.10; streaks cost more)
OWN_SECONDS_PER_MTEXEL = 8.0       # bake seconds per million texels, all channels (measured: 146 s for 16.8 M, 4 cores)
OWN_SECONDS_PER_BAKE = 2.0         # task 0189: and per part baked (measured: 142 s for 69 bakes, small demo)


def own_tpm(texture_size: int, area_m2: float, detail: str = "NORMAL") -> float:
    """Texels per metre for the parts baked on their own: the texture size's (``OWN_M``), fewer when their surface
    together (``area_m2``, world m²) would take more than the budget of ``detail`` (``OWN_BUDGETS``)."""
    tpm = float(texture_size) / OWN_M
    if area_m2 > 0:
        tpm = min(tpm, math.sqrt(OWN_BUDGETS.get(detail, OWN_BUDGET) / float(area_m2)))
    return tpm


def own_estimate(area_m2: float, texture_size: int, detail: str = "NORMAL", longest_m: float = 0.0,
                 bakes: int = 0, unique_area: float | None = None) -> dict:
    """The panel's estimate before the export (task 0165): the marine looks' pixel size, file size and bake time for
    ``area_m2`` of world surface. Picture sizes only: parts whose charts leave gaps come out a little bigger. Task
    0189 (0183 row 9): ``bakes`` parts are baked (copies share one bake), ``unique_area`` m² of them – the pictures
    and the file count only those, and every bake costs ``OWN_SECONDS_PER_BAKE`` besides its pixels."""
    tpm = own_tpm(texture_size, area_m2, detail)
    fill = OWN_FILLS.get(detail, OWN_FILL)
    max_px = OWN_MAX_PX.get(detail, ATLAS_MAX)
    tpm = min(tpm, math.sqrt(fill * max_px * max_px / max(float(area_m2), 1e-12)))
    if detail != "FINE" and longest_m > 0:           # Normal keeps a long chart whole: it must fit one picture
        tpm = min(tpm, (max_px - 10) / longest_m)
    texels = min(float(area_m2) * tpm * tpm / max(fill, 0.1), float(OWN_BUDGETS.get(detail, OWN_BUDGET)) * 2.0)
    if unique_area is not None and area_m2 > 0:
        texels *= min(1.0, max(float(unique_area), 0.0) / float(area_m2))
    return {"mm": 1000.0 / tpm, "bytes": int(texels * OWN_BYTES_PER_TEXEL),
            "seconds": texels / 1e6 * OWN_SECONDS_PER_MTEXEL + max(int(bakes), 0) * OWN_SECONDS_PER_BAKE,
            "bakes": max(int(bakes), 0)}


def cut_charts(un, max_m: float):
    """Task 0165: a chart longer than ``max_m`` (a tower's whole strip, 90 m) is cut across its long side into equal
    pieces, so a picture of 4096 px holds it at the pixel size its surface allows, not at 4096 / its length. The
    triangles keep their corners (each has its own UV), so the cut runs along triangle edges; the bake's margin covers
    the seam. Returns a new ``lightmap.Unwrap``."""
    from . import lightmap as lm
    size = np.asarray(un.size, np.float64).reshape(-1, 2)
    if not len(size) or float(size.max()) <= max_m:
        return un
    m = len(un.chart)
    uv = np.asarray(un.uv, np.float64).reshape(m, 3, 2)
    chart = un.chart.astype(np.int64)
    new_id = np.zeros(m, np.int64)
    base = 0
    for c in range(len(size)):
        t = np.nonzero(chart == c)[0]
        if not len(t):
            continue
        axis = int(np.argmax(size[c]))
        n = max(1, int(math.ceil(size[c][axis] / max_m)))
        pos = uv[t, :, axis].mean(1) / max(size[c][axis], 1e-12)
        new_id[t] = base + np.minimum((pos * n).astype(np.int64), n - 1)
        base += n
    ids, inv = np.unique(new_id, return_inverse=True)       # drop empty pieces
    inv = inv.ravel()
    k = len(ids)
    corner = np.repeat(inv, 3)
    flat = uv.reshape(-1, 2)
    lo = np.full((k, 2), np.inf)
    hi = np.full((k, 2), -np.inf)
    np.minimum.at(lo, corner, flat)
    np.maximum.at(hi, corner, flat)
    return lm.Unwrap(flat - lo[corner], inv.astype(np.int32), hi - lo, un.area)


def own_atlas(sizes_m: np.ndarray, area_m2: float, wanted_tpm: float, max_px: int = ATLAS_MAX,
              padding: int = OWN_PADDING, fill: float = OWN_FILL) -> tuple[float, int, np.ndarray]:
    """The picture of one part's own bake: ``sizes_m`` (k, 2) its charts in metres (``lightmap.unwrap``), ``area_m2``
    its surface, ``wanted_tpm`` texels per metre asked for. Returns (texels per metre, side in px – a power of two
    up to ``max_px`` –, places (k, 3) from ``lightmap.pack``). A part too big for ``wanted_tpm`` in ``max_px`` gets
    fewer texels per metre (the caller says so)."""
    from . import lightmap as lm
    sizes_m = np.asarray(sizes_m, np.float64).reshape(-1, 2)
    if not len(sizes_m):
        return float(wanted_tpm), 16, np.zeros((0, 3), np.int64)
    tpm = float(min(wanted_tpm, math.sqrt(fill * max_px * max_px / max(float(area_m2), 1e-12))))
    longest = float(sizes_m.max())
    if longest > 0:                                  # one chart longer than the picture: as long as it may be
        tpm = min(tpm, (max_px - 2 * padding - 2) / longest)
    for _ in range(200):
        px = lm.chart_pixels(sizes_m, tpm, padding)
        if lm.fits(px, max_px):
            break
        tpm *= 0.92
    else:
        raise ValueError("a part's charts do not fit one picture")
    side = 16
    while side < max_px and not lm.fits(px, side):
        side *= 2
    return tpm, side, lm.pack([px], side)[0]


def own_line(parts: int, finest_mm: float, coarsest_mm: float, detail: str = "NORMAL", bakes: int | None = None) -> str:
    """The export line's words for the parts baked on their own (marine looks); ``bakes``: how many were baked
    (task 0189: copies share one)."""
    from .words import plural
    if parts <= 0:
        return ""
    if abs(coarsest_mm - finest_mm) < 0.05 * max(coarsest_mm, 1e-9):
        size = f"{coarsest_mm:.0f} mm" if coarsest_mm >= 1.5 else f"{coarsest_mm:.1f} mm"
    else:
        size = f"{finest_mm:.1f}–{coarsest_mm:.0f} mm"
    text = f"marine looks baked on {plural(parts, 'part')} ({size} per pixel"
    if bakes is not None and 0 < bakes < parts:
        text += f"; copies share: {plural(bakes, 'bake')}"
    if coarsest_mm > OWN_DETAIL_MM:
        text += ("; the largest are too big for the fine streaks and barnacles at this size"
                 + ("; Marine detail Fine makes them finer" if detail != "FINE" else ""))
    return text + ")"


def result_line(size: int, triangles: int, textures: int, seconds: float, compressed: bool = False) -> str:
    from .words import plural
    tri = f"{triangles:,} triangle" + ("" if triangles == 1 else "s")
    return f"{mb(size)}{' compressed' if compressed else ''} · {tri} · {plural(textures, 'texture')} · {seconds:.1f} s"


def surroundings_line(extra: int) -> str:
    """What the surroundings (task 0106) add to the page: 'surroundings +0.4 MB' (three.js is smaller than
    model-viewer, so a page without pictures can come out smaller: 'surroundings −0.2 MB')."""
    tenths = round(extra / 1e5)
    return f"surroundings {'+' if tenths >= 0 else '−'}{abs(tenths) / 10:.1f} MB"


def light_line(light: str, extra: int, seconds: float) -> str:
    """'soft light baked (+1.2 MB, 45 s)' (task 0107)."""
    what = {"SOFT": "soft light baked", "ALL": "all light baked"}.get(light, "light baked")
    return f"{what} (+{mb(extra)}, {seconds:.0f} s)"


def header(size: int) -> str:
    """The panel header's state: the last file's size, '' before the first export."""
    return mb(size) if size else ""


def safe_name(text: str, fallback: str = "Model") -> str:
    """A file name from a project name: no characters Windows refuses."""
    out = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in (text or "")).strip(" .")
    return out or fallback


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------

def box_uv(pos: np.ndarray, tri: np.ndarray, tile: float = TILE_M) -> np.ndarray:
    """UVs per corner, projected onto the box side each triangle faces most (``pos`` (n, 3) metres, ``tri`` (m, 3)
    vertex indices) -> (m, 3, 2) in tiles. Every side is right-handed: U x V points out of the side."""
    p = pos[tri].astype(np.float64)                                  # (m, 3, 3)
    fn = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    a = np.argmax(np.abs(fn), axis=1)                                # the side's axis
    s = np.where(fn[np.arange(len(a)), a] < 0, -1.0, 1.0)
    b, c = (a + 1) % 3, (a + 2) % 3
    rows = np.arange(len(a))[:, None]
    u = p[rows, np.arange(3)[None, :], b[:, None]] * s[:, None]
    v = p[rows, np.arange(3)[None, :], c[:, None]]
    return (np.stack([u, v], axis=-1) / tile).astype(np.float32)


def quantize_normals(nrm: np.ndarray) -> np.ndarray:
    """Unit normals (n, 3) -> int8 (n, 3), as KHR_mesh_quantization stores them (normalized bytes)."""
    n = np.asarray(nrm, np.float64)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    n = np.where(ln > 1e-12, n / np.maximum(ln, 1e-12), [0.0, 0.0, 1.0])
    return np.clip(np.round(n * 127.0), -127, 127).astype(np.int8)


def weld(corner_vert: np.ndarray, corner_nrm: np.ndarray, corner_uv: np.ndarray | None,
         extra_uv: np.ndarray | None = None, corners: bool = False):
    """Corners -> glTF vertices: corners with the same point, (quantized) normal and UV become one vertex.

    Returns (vertex index of each new vertex in the original points, int8 normals (k, 3), UVs (k, 2) or None,
    index of every corner into the new vertices). ``extra_uv`` (corners, 2): a second UV set that must also be the
    same (the baked light's, task 0107); ``corners``: also return the first corner of each new vertex."""
    qn = quantize_normals(corner_nrm)
    cols = [np.asarray(corner_vert, np.int64)[:, None], qn.astype(np.int64)]
    if corner_uv is not None:
        cols.append(np.round(np.asarray(corner_uv, np.float64) * 65536.0).astype(np.int64))
    if extra_uv is not None:
        cols.append(np.round(np.asarray(extra_uv, np.float64) * 1048576.0).astype(np.int64))
    key = np.ascontiguousarray(np.concatenate(cols, axis=1))
    view = key.view(np.dtype((np.void, key.dtype.itemsize * key.shape[1]))).ravel()
    _, first, inverse = np.unique(view, return_index=True, return_inverse=True)
    uv = None if corner_uv is None else np.asarray(corner_uv, np.float32)[first]
    out = (np.asarray(corner_vert)[first], qn[first], uv, inverse.astype(np.int64).ravel())
    return (*out, first) if corners else out


# ---------------------------------------------------------------------------
# pictures
# ---------------------------------------------------------------------------

def seamless(tile: np.ndarray) -> np.ndarray:
    """Make a baked tile repeat without a seam: cross-fade it with a copy shifted by half a tile, first across, then
    down (each pass keeps the other direction seamless). The spread lost where two copies mix is given back, so
    noise keeps its strength. ``tile`` (h, w, c) floats."""
    out = np.asarray(tile, np.float32)
    for axis in (1, 0):
        n = out.shape[axis]
        t = (np.arange(n, dtype=np.float32) + 0.5) / n
        w = 1.0 - np.abs(2.0 * t - 1.0)                      # 0 at the edges, 1 in the middle
        shape = [1, 1, 1]
        shape[axis] = n
        w = w.reshape(shape)
        shifted = np.roll(out, n // 2, axis=axis)
        mean = out.mean(axis=(0, 1), keepdims=True)
        mix = out * w + shifted * (1.0 - w)
        gain = 1.0 / np.sqrt(w * w + (1.0 - w) ** 2)
        out = mean + (mix - mean) * gain
    return out


# ---------------------------------------------------------------------------
# welds (task 0369): a strip per weld look, baked along the weld's own UVs (u = metres along the seam)
# ---------------------------------------------------------------------------

WELD_STRIP_M = 0.064               # m along the seam one weld strip covers (a whole number of ripples, see weld_strip)
WELD_STRIP_PX = 1024               # px along the strip at most (16 px per mm; at 512 px: 8 px per mm)
WELD_ACROSS = 4                    # the strip is this many times longer (px) than it is wide


def weld_strip(pitch: float, size: int) -> tuple[float, int, int]:
    """(metres along, px along, px across) of one weld look's strip: an even number of ripples of ``pitch`` m in about
    ``WELD_STRIP_M`` (so the strip repeats without a jump in the ripples, also at half its length – ``seamless_along``),
    as many px along as the export's tile size (at most ``WELD_STRIP_PX``)."""
    pitch = max(float(pitch), 1e-4)
    n = max(2, 2 * int(round(WELD_STRIP_M / pitch / 2.0)))
    w = int(min(max(int(size), 64), WELD_STRIP_PX))
    w -= w % 2
    return n * pitch, w, max(16, w // WELD_ACROSS)


def seamless_along(tile: np.ndarray, band: float = 0.125) -> np.ndarray:
    """A weld strip repeats along u (axis 1) only: near each end it is faded into the copy shifted by half a strip,
    whose middle meets itself across the end. Across (axis 0) nothing changes – the bead's two toes and the heat zone's
    inner and outer edge are not one place. No gain: the ripples are in step in both copies (``weld_strip``); the
    mottle loses a little contrast in the narrow bands only."""
    out = np.asarray(tile, np.float32)
    n = out.shape[1]
    t = (np.arange(n, dtype=np.float32) + 0.5) / n
    w = np.clip(np.minimum(t, 1.0 - t) / max(band, 1e-6), 0.0, 1.0)
    shape = [1] * out.ndim
    shape[1] = n
    w = w.reshape(shape)
    return out * w + np.roll(out, n // 2, axis=1) * (1.0 - w)


def is_flat(values: np.ndarray, tol: float = FLAT) -> bool:
    """True when a baked tile is one number (or one colour) everywhere."""
    v = np.asarray(values, np.float32)
    if v.size == 0:
        return True
    lo = np.percentile(v.reshape(-1, v.shape[-1]) if v.ndim == 3 else v.ravel(), 0.5, axis=0)
    hi = np.percentile(v.reshape(-1, v.shape[-1]) if v.ndim == 3 else v.ravel(), 99.5, axis=0)
    return bool(np.all(hi - lo < tol))


def normal_flat(n: np.ndarray, tol: float = 3.0 / 255) -> bool:
    """True when a normal map (unit vectors, (h, w, 3)) tilts the surface by less than about 0.7° almost everywhere:
    an 8-bit normal map cannot show it (one step of 8 bits is 0.45°)."""
    xy = np.linalg.norm(np.asarray(n, np.float32)[..., :2], axis=-1)
    return bool(np.percentile(xy, 99.0) < tol) if xy.size else True


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(np.asarray(x, np.float32), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def to_bytes(x: np.ndarray) -> np.ndarray:
    """0 … 1 floats -> 0 … 255 bytes."""
    return np.clip(np.round(np.asarray(x, np.float32) * 255.0), 0, 255).astype(np.uint8)


def png(pixels: np.ndarray) -> bytes:
    """A PNG file of (h, w, c) bytes, c = 1, 3 or 4; row 0 at the top."""
    a = np.ascontiguousarray(pixels, np.uint8)
    if a.ndim == 2:
        a = a[:, :, None]
    h, w, c = a.shape
    kind = {1: 0, 2: 4, 3: 2, 4: 6}[c]
    raw = b"".join(b"\x00" + a[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, kind, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def is_webp(data: bytes) -> bool:
    return data[:4] == b"RIFF" and data[8:12] == b"WEBP"


def image_size(data: bytes) -> tuple[int, int]:
    """(width, height) of a PNG, JPG or WebP file's bytes; (0, 0) if unknown."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if is_webp(data) and len(data) >= 30:
        kind = data[12:16]
        if kind == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if kind == b"VP8L":
            b = int.from_bytes(data[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
        if kind == b"VP8X":
            return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            size = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + size
    return 0, 0


# ---------------------------------------------------------------------------
# motion
# ---------------------------------------------------------------------------

def decompose(m: np.ndarray):
    """4x4 matrices (f, 4, 4) -> translation (f, 3), rotation quaternions (f, 4) as x, y, z, w, scale (f, 3).
    Quaternions keep one sign from frame to frame (no flips half-way)."""
    m = np.asarray(m, np.float64).reshape(-1, 4, 4)
    t = m[:, :3, 3]
    r = m[:, :3, :3]
    s = np.linalg.norm(r, axis=1)                                    # length of each column
    det = np.linalg.det(r)
    s[:, 0] *= np.where(det < 0, -1.0, 1.0)
    r = r / np.where(np.abs(s) > 1e-12, s, 1.0)[:, None, :]
    q = np.empty((len(m), 4))
    for k, a in enumerate(r):
        tr = a[0, 0] + a[1, 1] + a[2, 2]
        if tr > 0:
            w = math.sqrt(tr + 1.0) * 2
            q[k] = ((a[2, 1] - a[1, 2]) / w, (a[0, 2] - a[2, 0]) / w, (a[1, 0] - a[0, 1]) / w, 0.25 * w)
        elif a[0, 0] > a[1, 1] and a[0, 0] > a[2, 2]:
            w = math.sqrt(1.0 + a[0, 0] - a[1, 1] - a[2, 2]) * 2
            q[k] = (0.25 * w, (a[0, 1] + a[1, 0]) / w, (a[0, 2] + a[2, 0]) / w, (a[2, 1] - a[1, 2]) / w)
        elif a[1, 1] > a[2, 2]:
            w = math.sqrt(1.0 + a[1, 1] - a[0, 0] - a[2, 2]) * 2
            q[k] = ((a[0, 1] + a[1, 0]) / w, 0.25 * w, (a[1, 2] + a[2, 1]) / w, (a[0, 2] - a[2, 0]) / w)
        else:
            w = math.sqrt(1.0 + a[2, 2] - a[0, 0] - a[1, 1]) * 2
            q[k] = ((a[0, 2] + a[2, 0]) / w, (a[1, 2] + a[2, 1]) / w, 0.25 * w, (a[1, 0] - a[0, 1]) / w)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    for k in range(1, len(q)):
        if np.dot(q[k], q[k - 1]) < 0:
            q[k] = -q[k]
    return t, q, s


def quat_to_matrix(q) -> np.ndarray:
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


# ---------------------------------------------------------------------------
# the glTF file
# ---------------------------------------------------------------------------

class Gltf:
    """Collects a glTF 2.0 scene and writes it as one binary ``.glb``.

    ``compress``: points, normals, UVs and triangle lists go in meshopt-compressed (``EXT_meshopt_compression``,
    ``core/meshopt.py``): about half the file on a big model. Every view then also names its place in a second
    buffer without data (the "fallback" the extension asks for), so the file stays valid glTF."""

    def __init__(self, generator: str = "Fresing Render", compress: bool = False):
        self.compress = bool(compress)
        self._fallback = 0                     # bytes of the data-less second buffer (compressed views' raw size)
        self.doc: dict = {"asset": {"version": "2.0", "generator": generator}, "scene": 0, "scenes": [{"nodes": []}],
                          "nodes": [], "meshes": [], "materials": [], "accessors": [], "bufferViews": [],
                          "buffers": [], "images": [], "textures": [], "samplers": []}
        self._bin = bytearray()
        self._used: set = set()
        self._required: set = set()
        self._samplers: dict = {}
        self.image_bytes = 0
        self.dequantize: list = []             # per mesh: (centre, step) of its 16-bit points, or None
        self.order: list = []                  # per mesh: the vertices passed in, in the order written (None = as passed)
        self._seen_mesh: dict = {}             # task 0175: content -> mesh index (exact duplicates written once)
        self.duplicates = 0

    # -- low level
    def _view(self, data: bytes, target: int | None = None, stride: int | None = None) -> int:
        while len(self._bin) % 4:
            self._bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self._bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        if stride:
            view["byteStride"] = stride
        self._bin.extend(data)
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def _packed_view(self, data: np.ndarray, target: int, stride: int | None, filt: str = "") -> int:
        """A meshopt-compressed view of ``data`` (count, element bytes); ``filt``: the meshopt filter the bytes were
        written with (task 0175: "EXPONENTIAL", "QUATERNION")."""
        count, elem = data.shape
        if target == ELEMENT_ARRAY_BUFFER:
            enc, mode = meshopt.encode_triangles(data.view({2: np.uint16, 4: np.uint32}[elem]).ravel())
        else:
            enc = meshopt.encode_vertex_buffer(data)
            mode = "ATTRIBUTES"
        while len(self._bin) % 4:
            self._bin.append(0)
        ext = {"buffer": 0, "byteOffset": len(self._bin), "byteLength": len(enc), "byteStride": elem,
               "count": int(count), "mode": mode}
        if filt:
            ext["filter"] = filt
        self._bin.extend(enc)
        self._fallback = (self._fallback + 3) // 4 * 4
        view = {"buffer": 1, "byteOffset": self._fallback, "byteLength": count * elem, "extensions": {MESHOPT: ext}}
        if target:
            view["target"] = target
        if stride:
            view["byteStride"] = stride
        self._fallback += count * elem
        self.use(MESHOPT, required=True)
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, values: np.ndarray, kind: str, ctype: int = FLOAT, normalized: bool = False,
                 target: int | None = None, minmax: bool = False, pack: bool = False, filt: str = "",
                 filtered: np.ndarray | None = None) -> int:
        """``pack``: meshopt-compressed in a compressed file also when it is no vertex data (animation, the moving
        cables' centre lines, task 0142); its elements must be a multiple of 4 bytes. ``filt`` + ``filtered``
        (task 0175): in a compressed file the bytes written are ``filtered`` (the same count, the meshopt filter
        ``filt`` turns them back into ``values``); ``values`` are what a reader gets (min / max from them)."""
        a = np.ascontiguousarray(np.asarray(values).astype(_NP[ctype], copy=False))
        n_comp = _COMPONENTS[kind]
        count = len(a) if a.ndim > 1 or n_comp == 1 else len(a) // n_comp
        a2 = a.reshape(count, n_comp)
        stride = None
        data = a2
        elem = n_comp * _SIZES[ctype]
        if target == ARRAY_BUFFER and elem % 4:            # vertex attributes start on 4 bytes each
            pad = (4 - elem % 4) // _SIZES[ctype]
            data = np.concatenate([a2, np.zeros((count, pad), a2.dtype)], axis=1)
            stride = data.shape[1] * _SIZES[ctype]
        if self.compress and count and filt and filtered is not None:
            f = np.ascontiguousarray(filtered)
            raw = f.view(np.uint8).reshape(count, -1)
            view = self._packed_view(raw, target, stride, filt)
        elif self.compress and count and (target in (ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER) or (pack and elem % 4 == 0)):
            raw = np.ascontiguousarray(data).view(np.uint8).reshape(count, -1)
            view = self._packed_view(raw, target, stride)
        else:
            view = self._view(np.ascontiguousarray(data).tobytes(), target, stride)
        acc = {"bufferView": view,
               "componentType": ctype, "count": int(count), "type": kind}
        if normalized:
            acc["normalized"] = True
        if minmax and count:
            acc["min"] = [float(v) if ctype == FLOAT else int(v) for v in a2.min(axis=0)]
            acc["max"] = [float(v) if ctype == FLOAT else int(v) for v in a2.max(axis=0)]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def use(self, ext: str, required: bool = False) -> None:
        self._used.add(ext)
        if required:
            self._required.add(ext)

    # -- pictures
    def sampler(self, wrap=REPEAT) -> int:
        """``wrap``: one wrap mode for both directions, or (wrapS, wrapT) (task 0369: a weld's strip repeats along
        the seam and stops at its edges)."""
        ws, wt = wrap if isinstance(wrap, tuple) else (wrap, wrap)
        if wrap not in self._samplers:
            self.doc["samplers"].append({"magFilter": LINEAR, "minFilter": LINEAR_MIPMAP_LINEAR,
                                         "wrapS": ws, "wrapT": wt})
            self._samplers[wrap] = len(self.doc["samplers"]) - 1
        return self._samplers[wrap]

    def texture(self, data: bytes, name: str = "", wrap=REPEAT) -> int:
        """A picture (PNG, JPG or WebP bytes). A WebP picture is named only by ``EXT_texture_webp`` (task 0175; a
        required extension: no second copy as a fallback, every current browser reads WebP)."""
        webp = is_webp(data)
        mime = "image/webp" if webp else "image/png" if data[:4] == b"\x89PNG" else "image/jpeg"
        img = {"bufferView": self._view(data), "mimeType": mime}
        if name:
            img["name"] = name
        self.doc["images"].append(img)
        self.image_bytes += len(data)
        k = len(self.doc["images"]) - 1
        if webp:
            self.use(WEBP, required=True)
            self.doc["textures"].append({"extensions": {WEBP: {"source": k}}, "sampler": self.sampler(wrap)})
        else:
            self.doc["textures"].append({"source": k, "sampler": self.sampler(wrap)})
        return len(self.doc["textures"]) - 1

    # -- scene
    def material(self, mat: dict) -> int:
        self.doc["materials"].append(mat)
        for ext in (mat.get("extensions") or {}):
            self.use(ext)
        if "KHR_texture_transform" in json.dumps(mat):
            self.use("KHR_texture_transform", required=True)
        return len(self.doc["materials"]) - 1

    def mesh(self, name: str, pos: np.ndarray, nrm_i8: np.ndarray, uv: np.ndarray | None,
             groups: list[tuple[int, np.ndarray]], quantize: bool = True, max_step: float = POS_STEP,
             tiled_uv: bool = False) -> int:
        """One mesh: shared points, normals (int8), UVs (Blender's V) and one primitive per (material, triangle corner
        indices).

        ``quantize``: points as 16-bit whole numbers in steps of at most ``max_step`` (half the bytes); the node that
        shows the mesh then needs ``dequantize(mesh)`` as its own place (``place_mesh`` does it). A part too big for
        that step keeps 32-bit points. ``tiled_uv``: UVs in tiles of a repeating look, stored as 16-bit numbers of
        1/``UV_Q`` tile; its materials scale them back (``UV_TRANSFORM`` on their pictures).

        Task 0175: a mesh exactly like one written before (points, normals, UVs, triangles, materials – e.g. two
        Blender meshes "SHACKLE" and "SHACKLE.001") is not written again: its index is returned."""
        pos = np.asarray(pos, np.float64)
        h = hashlib.blake2b(digest_size=20)
        for a in (pos, nrm_i8, uv if uv is not None else np.zeros(0)):
            a = np.ascontiguousarray(a)
            h.update(str(a.shape).encode() + str(a.dtype).encode())
            h.update(a.tobytes())
        for mat, idx in groups:
            h.update(f"|{mat}|".encode())
            h.update(np.ascontiguousarray(np.asarray(idx, np.int64)).tobytes())
        h.update(f"{quantize}{max_step}{tiled_uv}".encode())
        sig = h.digest()
        if sig in self._seen_mesh:
            self.duplicates += 1
            return self._seen_mesh[sig]
        order = None
        if self.compress and len(pos):         # points in the order the triangles first use them: small steps
            pos, nrm_i8, uv, groups, order = first_use_order(pos, nrm_i8, uv, groups, with_order=True)
        dq = None
        if quantize and len(pos):
            lo, hi = pos.min(0), pos.max(0)
            step = max(float((hi - lo).max()) / 65000.0, POS_STEP_PACKED if self.compress else 1e-9)
            if step <= max_step:
                centre = (lo + hi) / 2
                q = np.round((pos - centre) / step).astype(np.int16)
                dq = ([float(v) for v in centre], step)
        if dq is not None:
            attrs = {"POSITION": self.accessor(q, "VEC3", SHORT, target=ARRAY_BUFFER, minmax=True)}
        else:
            attrs = {"POSITION": self.accessor(pos.astype(np.float32), "VEC3", FLOAT, target=ARRAY_BUFFER,
                                               minmax=True)}
        attrs["NORMAL"] = self.accessor(nrm_i8, "VEC3", BYTE, normalized=True, target=ARRAY_BUFFER)
        self.use("KHR_mesh_quantization", required=True)
        if uv is not None:
            gl_uv = np.asarray(uv, np.float64).copy()
            gl_uv[:, 1] = 1.0 - gl_uv[:, 1]                              # glTF's V runs down the picture
            if tiled_uv:
                self.use("KHR_texture_transform", required=True)
                if len(gl_uv):
                    gl_uv -= np.floor(gl_uv.mean(0))                     # whole tiles: the look repeats
                q = np.round(gl_uv * UV_Q)
                if len(q) == 0 or np.abs(q).max() <= 32767:
                    attrs["TEXCOORD_0"] = self.accessor(q.astype(np.int16), "VEC2", SHORT, target=ARRAY_BUFFER)
                else:                                                    # over 100 m: 32-bit, same scale
                    attrs["TEXCOORD_0"] = self.accessor(q.astype(np.float32), "VEC2", FLOAT, target=ARRAY_BUFFER)
            else:
                attrs["TEXCOORD_0"] = self.accessor(gl_uv.astype(np.float32), "VEC2", FLOAT, target=ARRAY_BUFFER)
        prims = []
        n = len(pos)
        ctype = USHORT if n < 65536 else UINT
        for mat, idx in groups:
            if len(idx) == 0:
                continue
            p = {"attributes": attrs, "indices": self.accessor(np.asarray(idx).ravel(), "SCALAR", ctype,
                                                               target=ELEMENT_ARRAY_BUFFER), "mode": 4}
            if mat is not None and mat >= 0:
                p["material"] = int(mat)
            prims.append(p)
        self.doc["meshes"].append({"name": name, "primitives": prims})
        self.dequantize.append(dq)
        self.order.append(order)
        self._seen_mesh[sig] = len(self.doc["meshes"]) - 1
        return len(self.doc["meshes"]) - 1

    def vertex_attribute(self, mesh: int, values: np.ndarray, kind: str, ctype: int, normalized: bool = True) -> int:
        """An accessor of per-vertex ``values`` given in the order the vertices were passed to ``mesh`` (it follows
        the order they were written in)."""
        order = self.order[mesh]
        v = np.asarray(values)
        if order is not None:
            v = v[order]
        return self.accessor(v, kind, ctype, normalized=normalized, target=ARRAY_BUFFER)

    def mesh_variant(self, mesh: int, attributes: dict, materials: dict | None = None, name: str = "") -> int:
        """A copy of ``mesh`` that shares its accessors and adds ``attributes`` {name: accessor} (a placed copy's
        own baked light, task 0107); ``materials`` {old index: new index} swaps the primitives' materials."""
        src = self.doc["meshes"][mesh]
        prims = []
        for p in src["primitives"]:
            q = dict(p)
            q["attributes"] = {**p["attributes"], **attributes}
            if materials and p.get("material") in materials:          # (None: a primitive without a material)
                q["material"] = int(materials[p.get("material")])
            prims.append(q)
        self.doc["meshes"].append({"name": name or src.get("name", ""), "primitives": prims})
        self.dequantize.append(self.dequantize[mesh])
        self.order.append(self.order[mesh])
        return len(self.doc["meshes"]) - 1

    def place_mesh(self, node: dict, mesh: int, parent: int | None = None) -> int:
        """Add a part's node showing ``mesh``: the mesh itself, or a child that turns its 16-bit points back into
        metres."""
        dq = self.dequantize[mesh]
        if dq is None:
            node["mesh"] = mesh
            return self.node(node, parent)
        k = self.node(node, parent)
        self.node({"mesh": mesh, "translation": dq[0], "scale": [dq[1]] * 3}, k)
        return k

    def node(self, node: dict, parent: int | None = None) -> int:
        self.doc["nodes"].append(node)
        k = len(self.doc["nodes"]) - 1
        if parent is None:
            self.doc["scenes"][0]["nodes"].append(k)
        else:
            self.doc["nodes"][parent].setdefault("children", []).append(k)
        return k

    def animation(self, name: str, times: np.ndarray, tracks: list[tuple[int, str, np.ndarray]]) -> int | None:
        """``tracks``: (node, "translation" | "rotation" | "scale", values (f, 3|4)[, interpolation[, times[, how]]]):
        LINEAR unless a fourth item says "STEP" (a part shown and hidden by its scale, task 0111); a fifth item is
        the track's own times (its kept moments, task 0142), else ``times``. Equal time lists share one accessor.
        ``how`` (task 0175, ``web3d_keys.node_track``): "short" = ``values`` are normalised 16-bit rotations, "quat" =
        QUATERNION-filter numbers, "exp" = EXPONENTIAL-filter numbers (the last two: a compressed file only). In a compressed file the times are on the EXPONENTIAL grid too."""
        if not tracks:
            return None
        inputs: dict = {}
        end = float(np.max(np.asarray(times, np.float64))) if len(times) else 0.0

        def time_input(tm):
            tm = np.asarray(tm, np.float64)
            if self.compress and len(tm):          # the same numbers as ``web3d_keys.file_times``
                enc = web3d_keys.exp_encode(tm[:, None], web3d_keys.EXP_TIME, end)
                a = web3d_keys.exp_decode(enc)[:, 0]
            else:
                enc, a = None, tm.astype(np.float32)
            key = (len(a), a.tobytes())
            if key not in inputs:
                if enc is not None:
                    inputs[key] = self.accessor(a, "SCALAR", FLOAT, minmax=True, pack=True, filt="EXPONENTIAL",
                                                filtered=enc)
                else:
                    inputs[key] = self.accessor(a, "SCALAR", FLOAT, minmax=True, pack=True)
            return inputs[key]

        anim = {"name": name, "samplers": [], "channels": []}
        for track in tracks:
            node, path, values = track[:3]
            kind = "VEC4" if path == "rotation" else "VEC3"
            src = time_input(track[4] if len(track) > 4 and track[4] is not None else times)
            how = track[5] if len(track) > 5 else ""
            if how == "quat" and self.compress:
                filt = np.asarray(values, np.int16)
                out = self.accessor(web3d_keys.quat_decode(filt), kind, SHORT, normalized=True, pack=True,
                                    filt="QUATERNION", filtered=filt)
            elif how == "short":
                out = self.accessor(np.asarray(values, np.int16), kind, SHORT, normalized=True)
            elif how == "exp":
                enc = np.asarray(values, np.uint32)
                out = self.accessor(web3d_keys.exp_decode(enc), kind, FLOAT, pack=True, filt="EXPONENTIAL",
                                    filtered=enc)
            else:
                out = self.accessor(np.asarray(values, np.float32), kind, FLOAT, pack=True)
            anim["samplers"].append({"input": src, "interpolation": track[3] if len(track) > 3 else "LINEAR",
                                     "output": out})
            anim["channels"].append({"sampler": len(anim["samplers"]) - 1, "target": {"node": node, "path": path}})
        self.doc.setdefault("animations", []).append(anim)
        return len(self.doc["animations"]) - 1

    # -- out
    def glb(self) -> bytes:
        doc = dict(self.doc)
        while len(self._bin) % 4:
            self._bin.append(0)
        doc["buffers"] = [{"byteLength": len(self._bin)}]
        if self._fallback:
            doc["buffers"].append({"byteLength": self._fallback, "extensions": {MESHOPT: {"fallback": True}}})
        for key in ("images", "textures", "samplers", "materials", "meshes"):
            if not doc[key]:
                del doc[key]
        if self._used:
            doc["extensionsUsed"] = sorted(self._used)
        if self._required:
            doc["extensionsRequired"] = sorted(self._required)
        js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(self._bin)
        return (struct.pack("<III", 0x46546C67, 2, total) + struct.pack("<II", len(js), 0x4E4F534A) + js
                + struct.pack("<II", len(self._bin), 0x004E4942) + bytes(self._bin))


def first_use_order(pos, nrm, uv, groups, with_order: bool = False):
    """The same mesh with its vertices numbered in the order the triangles (all groups, one after the other) first
    use them; vertices no triangle uses are left out. Neighbouring vertices then sit next to each other in the
    file, which is what meshopt packs well."""
    allidx = np.concatenate([np.asarray(i).ravel() for _m, i in groups]) if groups else np.zeros(0, np.int64)
    n = len(pos)
    if not len(allidx):
        return (pos, nrm, uv, groups, None) if with_order else (pos, nrm, uv, groups)
    _u, first = np.unique(allidx, return_index=True)
    order = _u[np.argsort(first)]                              # old index of each new vertex
    new = np.full(n, -1, np.int64)
    new[order] = np.arange(len(order))
    pos = np.asarray(pos)[order]
    nrm = np.asarray(nrm)[order]
    uv = None if uv is None else np.asarray(uv)[order]
    out = (pos, nrm, uv, [(m, new[np.asarray(i)]) for m, i in groups])
    return (*out, order) if with_order else out


def read_glb(data: bytes) -> tuple[dict, bytes]:
    """(the JSON part, the binary part) of a ``.glb``. Raises ValueError when it is not one."""
    magic, version, total = struct.unpack("<III", data[:12])
    if magic != 0x46546C67 or version != 2 or total != len(data):
        raise ValueError("not a glTF 2.0 binary file")
    jlen, jtype = struct.unpack("<II", data[12:20])
    if jtype != 0x4E4F534A:
        raise ValueError("the first part is not JSON")
    doc = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    if len(rest) >= 8:
        blen, btype = struct.unpack("<II", rest[:8])
        if btype != 0x004E4942:
            raise ValueError("the second part is not binary")
        return doc, rest[8:8 + blen]
    return doc, b""


def texture_image(doc: dict, tex: int) -> int:
    """The image a texture shows: its ``source`` or its ``EXT_texture_webp`` source (task 0175)."""
    t = doc["textures"][tex]
    if "source" in t:
        return t["source"]
    return t["extensions"][WEBP]["source"]


def view_bytes(doc: dict, binary: bytes, k: int) -> bytes:
    """The bytes of buffer view ``k``; a meshopt-compressed view is decoded (and kept in ``doc`` for the next)."""
    view = doc["bufferViews"][k]
    ext = (view.get("extensions") or {}).get(MESHOPT)
    if ext is None:
        start = view.get("byteOffset", 0)
        return binary[start:start + view["byteLength"]]
    cache = doc.setdefault("_decoded", {})
    if k not in cache:
        src = binary[ext.get("byteOffset", 0):ext.get("byteOffset", 0) + ext["byteLength"]]
        filt = ext.get("filter", "NONE")
        if filt not in ("NONE", "EXPONENTIAL", "QUATERNION"):
            raise ValueError(f"meshopt filter {ext['filter']} is not read here")
        if ext["mode"] == "ATTRIBUTES":
            out = meshopt.decode_vertex_buffer(src, ext["count"], ext["byteStride"])
            if filt == "EXPONENTIAL":          # task 0175
                out = web3d_keys.exp_decode(out.copy().view(np.uint32))
            elif filt == "QUATERNION":
                out = web3d_keys.quat_decode(out.copy().view(np.int16).reshape(-1, 4))
            out = np.ascontiguousarray(out).tobytes()
        elif ext["mode"] in ("INDICES", "TRIANGLES"):
            fn = meshopt.decode_index_sequence if ext["mode"] == "INDICES" else meshopt.decode_index_buffer
            out = fn(src, ext["count"]).astype({2: np.uint16, 4: np.uint32}[ext["byteStride"]]).tobytes()
        else:
            raise ValueError(f"meshopt mode {ext['mode']} is not read here")
        cache[k] = out
    return cache[k]


def accessor_array(doc: dict, binary: bytes, k: int) -> np.ndarray:
    """The numbers of accessor ``k`` as an array (count, components)."""
    acc = doc["accessors"][k]
    view = doc["bufferViews"][acc["bufferView"]]
    n = _COMPONENTS[acc["type"]]
    dt = np.dtype(_NP[acc["componentType"]])
    stride = view.get("byteStride") or n * dt.itemsize
    start = acc.get("byteOffset", 0)
    raw = np.frombuffer(view_bytes(doc, binary, acc["bufferView"]), np.uint8, count=stride * acc["count"],
                        offset=start)
    a = raw.reshape(acc["count"], stride)[:, :n * dt.itemsize].copy().view(dt).reshape(acc["count"], n)
    if acc.get("normalized"):
        a = a.astype(np.float32) / float(np.iinfo(dt).max)
    return a


def problems(data: bytes) -> list[str]:
    """What is wrong with a ``.glb`` by the rules of the glTF 2.0 spec that matter to a viewer ([] = fine)."""
    out = []
    try:
        doc, binary = read_glb(data)
    except Exception as exc:  # noqa: BLE001
        return [str(exc)]
    views = doc.get("bufferViews", [])
    buffers = doc.get("buffers", [])
    used = set(doc.get("extensionsUsed", []))
    for b, buf in enumerate(buffers[1:], 1):
        if "uri" not in buf and not ((buf.get("extensions") or {}).get(MESHOPT) or {}).get("fallback"):
            out.append(f"buffer {b} has no data")
    for k, v in enumerate(views):
        b = v.get("buffer", 0)
        size = len(binary) if b == 0 else (buffers[b]["byteLength"] if b < len(buffers) else -1)
        if v.get("byteOffset", 0) + v["byteLength"] > size:
            out.append(f"buffer view {k} runs past the end")
        ext = (v.get("extensions") or {}).get(MESHOPT)
        if ext is not None:
            if MESHOPT not in used:
                out.append(f"buffer view {k}: {MESHOPT} not in extensionsUsed")
            if ext.get("buffer", 0) != 0 or ext.get("byteOffset", 0) + ext["byteLength"] > len(binary):
                out.append(f"buffer view {k}: its compressed data runs past the end")
            if ext["count"] * ext["byteStride"] != v["byteLength"]:
                out.append(f"buffer view {k}: compressed count x stride is not its length")
            if ext["mode"] == "ATTRIBUTES" and (ext["byteStride"] % 4 or ext["byteStride"] > 256):
                out.append(f"buffer view {k}: compressed stride {ext['byteStride']}")
        if v.get("byteOffset", 0) % 4:
            out.append(f"buffer view {k} does not start on 4 bytes")
        if v.get("byteStride") and (v["byteStride"] % 4 or not 4 <= v["byteStride"] <= 252):
            out.append(f"buffer view {k}: stride {v['byteStride']}")
    for k, a in enumerate(doc.get("accessors", [])):
        v = views[a["bufferView"]]
        elem = _COMPONENTS[a["type"]] * _SIZES[a["componentType"]]
        stride = v.get("byteStride") or elem
        if a.get("byteOffset", 0) + stride * (a["count"] - 1) + elem > v["byteLength"]:
            out.append(f"accessor {k} runs past its view")
    for m, mesh in enumerate(doc.get("meshes", [])):
        for p in mesh["primitives"]:
            attrs = p["attributes"]
            n = doc["accessors"][attrs["POSITION"]]["count"]
            pos = doc["accessors"][attrs["POSITION"]]
            if "min" not in pos or "max" not in pos:
                out.append(f"mesh {m}: POSITION without min/max")
            for name, a in attrs.items():
                if doc["accessors"][a]["count"] != n:
                    out.append(f"mesh {m}: {name} has another count")
            if "indices" in p:
                try:
                    idx = accessor_array(doc, binary, p["indices"])
                except ValueError as exc:
                    out.append(f"mesh {m}: indices cannot be read ({exc})")
                    continue
                if idx.size and int(idx.max()) >= n:
                    out.append(f"mesh {m}: an index points past the last vertex")
                if idx.size % 3:
                    out.append(f"mesh {m}: indices are not whole triangles")
            if "material" in p and p["material"] >= len(doc.get("materials", [])):
                out.append(f"mesh {m}: no such material")
            elif "material" in p:
                occ = doc["materials"][p["material"]].get("occlusionTexture")
                if occ and f"TEXCOORD_{occ.get('texCoord', 0)}" not in attrs:
                    out.append(f"mesh {m}: its material reads TEXCOORD_{occ.get('texCoord', 0)}, which it has not")
            for name in attrs:
                if not name.startswith("_") and name.split("_")[0] not in (
                        "POSITION", "NORMAL", "TANGENT", "TEXCOORD", "COLOR", "JOINTS", "WEIGHTS"):
                    out.append(f"mesh {m}: attribute {name} must start with _ (an application's own)")
    for k, node in enumerate(doc.get("nodes", [])):
        if "mesh" in node and node["mesh"] >= len(doc.get("meshes", [])):
            out.append(f"node {k}: no such mesh")
        for c in node.get("children", []):
            if c >= len(doc["nodes"]):
                out.append(f"node {k}: no such child")
    for ext in doc.get("extensionsRequired", []):
        if ext not in used:
            out.append(f"{ext} is required but not used")
    for k, mat in enumerate(doc.get("materials", [])):
        for ext in (mat.get("extensions") or {}):
            if ext not in used:
                out.append(f"material {k}: {ext} not in extensionsUsed")
    return out


def summary(data: bytes) -> dict:
    """Numbers of a ``.glb``: size, triangles (as shown: every copy counted), meshes, parts (nodes with a mesh),
    textures, materials, animations, names of the nodes."""
    doc, _ = read_glb(data)
    tri_of_mesh = []
    for mesh in doc.get("meshes", []):
        tri_of_mesh.append(sum(doc["accessors"][p["indices"]]["count"] // 3 for p in mesh["primitives"]))
    nodes = doc.get("nodes", [])
    shown = sum(tri_of_mesh[n["mesh"]] for n in nodes if "mesh" in n)
    parts = sum(1 for n in nodes if n.get("name") and ("mesh" in n or any(
        "mesh" in nodes[c] and not nodes[c].get("name") for c in n.get("children", []))))
    return {"size": len(data), "triangles": shown, "unique_triangles": sum(tri_of_mesh),
            "meshes": len(doc.get("meshes", [])), "parts": parts,
            "textures": len(doc.get("images", [])), "materials": len(doc.get("materials", [])),
            "animations": len(doc.get("animations", [])), "names": [n["name"] for n in nodes if n.get("name")],
            "extensions": doc.get("extensionsUsed", []), "compressed": MESHOPT in doc.get("extensionsUsed", [])}


# ---------------------------------------------------------------------------
# the viewer page
# ---------------------------------------------------------------------------

def viewer_script() -> str:
    """model-viewer's one-file build (three.js and lit inside), shipped with the extension."""
    with open(os.path.join(WEB_DIR, MV_FILE), encoding="utf-8") as fh:
        return fh.read()


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --ink: #252E36; --muted: #5B6670; --bg: #F1F3F5; --accent: #2F6A1B; }}
  html, body {{ margin: 0; height: 100%; background: var(--bg); color: var(--ink);
               font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; }}
  header {{ position: absolute; left: 0; right: 0; top: 0; padding: 14px 18px; display: flex;
            justify-content: space-between; align-items: baseline; gap: 12px; pointer-events: none; z-index: 1; }}
  h1 {{ margin: 0; font-size: 18px; font-weight: 600; }}
  .hint {{ font-size: 13px; color: var(--muted); }}
  model-viewer {{ width: 100%; height: 100%; --poster-color: transparent; background: radial-gradient(#ffffff, var(--bg)); }}
  .note {{ position: absolute; left: 18px; bottom: 12px; font-size: 12px; color: var(--muted); }}
  .note a {{ color: var(--accent); }}
  #fail {{ display: none; position: absolute; inset: 0; align-items: center; justify-content: center; padding: 24px;
           text-align: center; }}
</style>
</head>
<body>
<header><h1>{title}</h1><span class="hint">Drag to turn · scroll or pinch to zoom · right-drag to move</span></header>
<model-viewer id="model" camera-controls touch-action="pan-y" shadow-intensity="0.6" exposure="1.0"
  environment-image="neutral" tone-mapping="neutral" interaction-prompt="none" camera-orbit="45deg 65deg auto"{autoplay}{src}
  alt="{alt}"></model-viewer>
<div class="note">{note}</div>
<div id="fail">This page needs a browser with WebGL (Edge, Chrome, Firefox or Safari of the last few years).</div>
{script}
{model}
</body>
</html>
"""


# meshopt (task 0105): model-viewer carries the decoder itself and switches it on once a "decoder location" script has
# loaded; an empty inline script loads at once, also offline: nothing is fetched from the internet. It goes right
# after the viewer script and before the model is named (the model's ``src`` is set by a script after it, never as
# an attribute: a viewer that starts loading first throws "setMeshoptDecoder must be called before …").
MESHOPT_SETUP = ("\n<script>\ncustomElements.get('model-viewer').meshoptDecoderLocation = 'data:text/javascript,';\n"
                 "</script>")


def viewer_html(title: str, glb: bytes | None = None, src: str = "", script_src: str = "", note: str = "",
                animated: bool = False, script_text: str | None = None) -> str:
    """The viewer page. With ``glb`` the model is inside the page (base64): one file that opens offline, also from
    an e-mail. With ``src`` the page loads that file (the website). The viewer script is inlined unless
    ``script_src`` names a file next to the page."""
    title_h = html.escape(title or "3D model", quote=True)
    if script_src:
        script = f'<script src="{html.escape(script_src, quote=True)}"></script>'
    else:
        text = viewer_script() if script_text is None else script_text
        script = "<script>\n" + text.replace("</script", "<\\/script") + "\n</script>"
    script += MESHOPT_SETUP
    model = ""
    src_attr = ""
    if glb is not None:
        b64 = base64.b64encode(glb).decode("ascii")
        model += ("<script type=\"application/octet-stream\" id=\"glb\">" + b64 + "</script>\n<script>\n"
                  "(function () {\n"
                  "  var s = document.getElementById('glb').textContent.trim(), b = atob(s), a = new Uint8Array(b.length);\n"
                  "  for (var i = 0; i < b.length; i++) a[i] = b.charCodeAt(i);\n"
                  "  var url = URL.createObjectURL(new Blob([a], {type: 'model/gltf-binary'}));\n"
                  "  document.getElementById('model').src = url;\n"
                  "})();\n</script>")
    elif src:                            # the website: the viewer is named first, then given its file
        src_attr = f' data-src="{html.escape(src, quote=True)}"'
        model += "<script>\nvar m = document.getElementById('model');\nm.src = m.dataset.src;\n</script>"
    model += ("\n<script>\n(function () {\n  var c = document.createElement('canvas');\n"
              "  if (!(c.getContext('webgl2') || c.getContext('webgl'))) document.getElementById('fail').style.display = 'flex';\n"
              "})();\n</script>")
    return _PAGE.format(title=title_h, alt=title_h, autoplay=" autoplay" if animated else "", src=src_attr,
                        note=note, script=script, model=model)
