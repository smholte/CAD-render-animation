"""The surface hash ``hp-hash/1`` of the house scene format (task 0114; FORMAT.md section 5 of
github.com/smholte/house-scene-format, tag v1.0). No Blender.

Source: the function ``surface_hash`` of ``hsf/surface.py`` at tag ``v1.0`` (commit 52c0352), written here with NumPy
over arrays instead of a glTF reader, so the importer, the snow layers (``core/house_snow.py``) and the bake writer
(``core/house_scene.py``) share one copy. ``tests/test_house_scene.py`` compares it with the pinned checker's own
function on every surface of the sample.

    h = SHA-256 of "hp-hash/1" + one zero byte, then per primitive:
        "P" + uint32 vertex count + int32 x, y, z per vertex = round(coordinate x 1000)        (millimetres)
        "U" + uint16 u, v per vertex = clamp(round(TEXCOORD_1 x 65535), 0, 65535)    when TEXCOORD_1 is there
        "N"                                                                          when it is not
            + uint32 index count + uint32 each index           (0, 1, 2 … when the primitive has no indices)
    then for a MAP surface only "S" + uint32 W + uint32 H;  hash = the first 32 hex digits.

All numbers little-endian; ``round`` is half away from zero.
"""

from __future__ import annotations

import hashlib

import numpy as np

HASH_NAME = "hp-hash/1"
INT32 = 2**31 - 1


def round_half_away(x):
    """Round to the nearest whole number, halves away from zero (JavaScript: ``Math.sign(x) * Math.floor(Math.abs(x)
    + 0.5)``) – a float for a float, an array of float64 for an array."""
    a = np.asarray(x, np.float64)
    out = np.sign(a) * np.floor(np.abs(a) + 0.5)
    return float(out) if out.ndim == 0 else out


def hash_primitives(prims, uv1_px=None) -> str:
    """``hp-hash/1`` of a mesh given as its primitives, in order. Each primitive: a dict with ``positions`` (n, 3)
    (float32 as stored in the .glb), ``uv1`` (n, 2) or None (TEXCOORD_1), ``indices`` (k,) or None.
    ``uv1_px`` (W, H) for a MAP surface, else None. Raises ValueError for numbers that are not finite or too far."""
    h = hashlib.sha256(HASH_NAME.encode() + b"\0")
    for prim in prims:
        pos = np.asarray(prim["positions"], np.float32).reshape(-1, 3)
        if not np.isfinite(pos).all():
            raise ValueError("a position is not a finite number")
        mm = round_half_away(pos.astype(np.float64) * 1000.0)
        if mm.size and np.abs(mm).max() > INT32:
            raise ValueError("a position lies more than 2,147 km from the origin")
        h.update(b"P" + np.uint32(len(pos)).astype("<u4").tobytes() + mm.astype("<i4").tobytes())
        uv = prim.get("uv1")
        if uv is not None:
            uv = np.asarray(uv, np.float32).reshape(-1, 2)
            if len(uv) != len(pos):
                raise ValueError(f"TEXCOORD_1 has {len(uv)} values for {len(pos)} vertices")
            if not np.isfinite(uv).all():
                raise ValueError("a light-map UV is not a finite number")
            q = np.clip(round_half_away(uv.astype(np.float64) * 65535.0), 0, 65535)
            h.update(b"U" + q.astype("<u2").tobytes())
        else:
            h.update(b"N")
        idx = prim.get("indices")
        idx = np.arange(len(pos)) if idx is None else np.asarray(idx).ravel()
        h.update(np.uint32(len(idx)).astype("<u4").tobytes() + idx.astype("<u4").tobytes())
    if uv1_px is not None:
        h.update(b"S" + np.array([int(uv1_px[0]), int(uv1_px[1])], "<u4").tobytes())
    return h.hexdigest()[:32]


def scene_hash(pairs: dict) -> str:
    """One hash for a whole export: SHA-256 of the lines "<id> <hash>\\n" sorted by id (UTF-8), first 32 hex."""
    text = "".join(f"{k} {pairs[k]}\n" for k in sorted(pairs))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]
