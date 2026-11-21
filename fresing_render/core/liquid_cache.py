"""The coolant liquid's bake on disk (task 0255). No Blender here.

One file per bake. Every frame keeps, per chart, the liquid's depth in **8-bit steps of 0.05 mm, only where wet**
(a packed bit per cell says where; depths of 255 steps = 12.75 mm and more go into a short overflow list of 16-bit
steps), the drops in flight (16-bit places would be too coarse for a 2 m machine: 32-bit) and the bookkeeping; each
frame zlib-compressed. An index at the end gives every frame's place in the file, so any frame is read on its own
(< 2 ms for 250,000 cells).

The file is keyed by a fingerprint the caller makes (task B: what the bake depends on – charts, motion, pours, tool);
``Reader.open(path, fingerprint)`` gives None when the file is missing, damaged or made for another fingerprint.

Layout: b"FRLQ" + u32 version + u32 head length + head (JSON: fingerprint, charts [name, shape], fps, step) + frame
records + index (JSON: frame -> [offset, length]) + u64 index offset + u32 index length + b"FRLQ".
"""

from __future__ import annotations

import json
import os
import struct
import zlib

import numpy as np

MAGIC = b"FRLQ"
VERSION = 1
STEP = 0.05e-3                  # m per 8-bit step
_U32 = struct.Struct("<I")
_TAIL = struct.Struct("<QI4s")


def encode_depth(d: np.ndarray) -> bytes:
    """One chart's depths (m) -> bytes: n wet (u32), the wet mask (packed bits), the 8-bit steps of the wet cells,
    n overflow (u32), their places in the wet list (u32) and 16-bit steps."""
    q = np.rint(np.asarray(d, np.float64).ravel() / STEP)
    np.clip(q, 0, 65535, out=q)
    q = q.astype(np.uint16)
    wet = q > 0
    vals = q[wet]
    over = np.nonzero(vals >= 255)[0].astype(np.uint32)
    parts = [_U32.pack(len(vals)), np.packbits(wet).tobytes(), np.minimum(vals, 255).astype(np.uint8).tobytes(),
             _U32.pack(len(over)), over.tobytes(), vals[over].astype(np.uint16).tobytes()]
    return b"".join(parts)


def decode_depth(buf: bytes, shape, pos: int = 0):
    """bytes -> (depths float32 (shape), m; the position after them)."""
    size = int(np.prod(shape))
    (nw,) = _U32.unpack_from(buf, pos)
    pos += 4
    nb = (size + 7) // 8
    wet = np.unpackbits(np.frombuffer(buf, np.uint8, nb, pos), count=size).view(bool)
    pos += nb
    vals = np.frombuffer(buf, np.uint8, nw, pos).astype(np.float32)
    pos += nw
    (no,) = _U32.unpack_from(buf, pos)
    pos += 4
    if no:
        idx = np.frombuffer(buf, np.uint32, no, pos)
        pos += 4 * no
        vals[idx] = np.frombuffer(buf, np.uint16, no, pos)
        pos += 2 * no
    out = np.zeros(size, np.float32)
    out[wet] = vals * np.float32(STEP)
    return out.reshape(shape), pos


_TOTALS = ("poured", "on_charts", "in_flight", "drained", "floor")


class Writer:
    """Write a bake: ``add`` every frame (any order), then ``close`` (or use as a context manager)."""

    def __init__(self, path, fingerprint: str, charts, fps: float, level: int = 1):
        """``charts``: [(name, (ny, nx))]."""
        self.path = path
        self.shapes = [tuple(int(v) for v in s) for _, s in charts]
        self.level = level
        self.index = {}
        self.tmp = path + ".part"
        self.f = open(self.tmp, "wb")
        head = json.dumps(dict(fingerprint=str(fingerprint), charts=[[n, list(s)] for n, s in zip(
            [c[0] for c in charts], self.shapes)], fps=float(fps), step=STEP)).encode()
        self.f.write(MAGIC + _U32.pack(VERSION) + _U32.pack(len(head)) + head)

    def add(self, frame: int, depths, drops=None, drop_vol=None, totals=None):
        """``depths``: per chart (ny, nx) m; ``drops`` (n, 3) m, ``drop_vol`` (n,) litres; ``totals`` dict (litres)."""
        if len(depths) != len(self.shapes):
            raise ValueError("one depth grid per chart")
        parts = []
        for d, shp in zip(depths, self.shapes):
            if tuple(np.shape(d)) != shp:
                raise ValueError("a depth grid has the wrong shape")
            parts.append(encode_depth(d))
        P = np.zeros((0, 3), np.float32) if drops is None else np.asarray(drops, np.float32).reshape(-1, 3)
        V = np.zeros(len(P), np.float32) if drop_vol is None else np.asarray(drop_vol, np.float32).ravel()
        if len(V) != len(P):
            raise ValueError("one volume per drop")
        parts += [_U32.pack(len(P)), P.tobytes(), V.tobytes()]
        t = totals or {}
        parts.append(np.array([float(t.get(k, 0.0)) for k in _TOTALS], np.float64).tobytes())
        blob = zlib.compress(b"".join(parts), self.level)
        self.index[int(frame)] = (self.f.tell(), len(blob))
        self.f.write(blob)

    def close(self):
        if self.f is None:
            return
        idx = json.dumps({str(k): list(v) for k, v in sorted(self.index.items())}).encode()
        off = self.f.tell()
        self.f.write(idx)
        self.f.write(_TAIL.pack(off, len(idx), MAGIC))
        self.f.close()
        self.f = None
        os.replace(self.tmp, self.path)          # a bake stopped half way leaves no file that looks whole

    def abort(self):
        if self.f is not None:
            self.f.close()
            self.f = None
            try:
                os.remove(self.tmp)
            except OSError:
                pass

    def __enter__(self):
        return self

    def __exit__(self, kind, *a):
        if kind is None:
            self.close()
        else:
            self.abort()


class Reader:
    """Read frames of a bake. ``Reader.open(path, fingerprint)`` → Reader or None."""

    def __init__(self, path):
        self.f = open(path, "rb")
        try:
            magic = self.f.read(4)
            (ver,) = _U32.unpack(self.f.read(4))
            if magic != MAGIC or ver != VERSION:
                raise ValueError("not a liquid bake of this version")
            (hl,) = _U32.unpack(self.f.read(4))
            head = json.loads(self.f.read(hl))
            self.fingerprint = head["fingerprint"]
            self.names = [c[0] for c in head["charts"]]
            self.shapes = [tuple(c[1]) for c in head["charts"]]
            self.fps = head["fps"]
            self.f.seek(-_TAIL.size, os.SEEK_END)
            off, ln, tail = _TAIL.unpack(self.f.read(_TAIL.size))
            if tail != MAGIC:
                raise ValueError("the bake is not complete")
            self.f.seek(off)
            self.index = {int(k): tuple(v) for k, v in json.loads(self.f.read(ln)).items()}
        except Exception:
            self.f.close()
            raise

    @classmethod
    def open(cls, path, fingerprint=None):
        """The bake at ``path`` if it is whole and (when given) made for ``fingerprint``; else None."""
        try:
            r = cls(path)
        except (OSError, ValueError, KeyError, struct.error, json.JSONDecodeError):
            return None
        if fingerprint is not None and r.fingerprint != str(fingerprint):
            r.close()
            return None
        return r

    @property
    def frames(self):
        return sorted(self.index)

    def read(self, frame: int):
        """(depths: list of float32 (ny, nx) in m, drops (n, 3) float32, drop volumes (n,) litres, totals dict)."""
        off, ln = self.index[int(frame)]
        self.f.seek(off)
        buf = zlib.decompress(self.f.read(ln))
        pos = 0
        depths = []
        for shp in self.shapes:
            d, pos = decode_depth(buf, shp, pos)
            depths.append(d)
        (n,) = _U32.unpack_from(buf, pos)
        pos += 4
        P = np.frombuffer(buf, np.float32, 3 * n, pos).reshape(n, 3).copy()
        pos += 12 * n
        V = np.frombuffer(buf, np.float32, n, pos).copy()
        pos += 4 * n
        t = np.frombuffer(buf, np.float64, len(_TOTALS), pos)
        return depths, P, V, dict(zip(_TOTALS, (float(x) for x in t)))

    def close(self):
        if self.f is not None:
            self.f.close()
            self.f = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
