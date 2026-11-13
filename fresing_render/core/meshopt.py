"""meshopt compression of glTF buffers (``EXT_meshopt_compression``, task 0105) in plain NumPy.

Why this one (and not Draco): model-viewer 4.4.0, which the web page already carries, has the meshopt decoder built in
(WebAssembly inside its one file), so the page stays one offline file with no extra download; the decoder is MIT and
decodes at memory speed, also on a phone; and the encoder below needs nothing but NumPy (Draco's encoder is a 5 MB
compiled wheel per platform).

Two codecs of the format (the spec: github.com/KhronosGroup/glTF/tree/main/extensions/2.0/Vendor/EXT_meshopt_compression):

* **ATTRIBUTES** (vertex data, version 0, first byte ``0xa0``): each byte of an element is stored as the difference to
  the same byte of the element before (zigzag), in groups of 16 elements packed with 0, 2, 4 or 8 bits per byte.
  16-bit points that lie next to each other differ by small numbers, so most bytes take 2 or 4 bits.
* **TRIANGLES** (``0xe1``, index codec version 1): triangle lists by the edges and corners they share with the
  triangles just before – about 2.5 bytes a triangle on CAD meshes. It is a sequential state machine (too slow in
  Python), so it is written by **Blender's own meshopt library** (``Native``: the library Blender 5.2's glTF add-on
  ships, or ``libmeshoptimizer`` next to Blender as a Python module), loaded with ctypes when it is there.
* **INDICES** (``0xd1``): each index as the zigzag difference to the index before, as a variable-length number
  (LEB128); the NumPy fallback when the library is not found (about 4 bytes a triangle).

``decode_*`` read the data back (the file reader and the tests).
"""

from __future__ import annotations

import ctypes
import os

import numpy as np

VERTEX_HEADER = 0xA0
SEQUENCE_HEADER = 0xD1
TRIANGLES_HEADER = 0xE1
TAIL_MIN = 32                      # the decoder wants at least this many bytes after the blocks
SEQUENCE_TAIL = 4                  # ... and exactly this many after an index sequence


def _zigzag8(d: np.ndarray) -> np.ndarray:
    """Byte differences (uint8, wrapping) -> zigzag codes (uint8): 0, -1, 1, -2 … -> 0, 1, 2, 3 …"""
    s = d.view(np.int8).astype(np.int16)
    return (((s << 1) ^ (s >> 7)) & 0xFF).astype(np.uint8)


def _block_elements(stride: int) -> int:
    return min((0x2000 // stride) & ~0x0F, 0x100)


def _encode_blocks(z: np.ndarray) -> np.ndarray:
    """``z`` (blocks, groups * 16, stride) zigzag codes of blocks of the same size -> the bytes of those blocks."""
    nb, ne, stride = z.shape
    ng = ne // 16
    hb = (ng + 3) // 4
    g = z.transpose(0, 2, 1).reshape(nb, stride, ng, 16)              # per block, per byte: the groups
    rows = g.reshape(-1, 16)
    n = len(rows)
    size1 = 4 + (rows >= 3).sum(1)
    size2 = 8 + (rows >= 15).sum(1)
    zero = ~rows.any(1)
    sizes = np.stack([np.where(zero, 0, 99), size1, size2, np.full(n, 16)], axis=1)
    mode = np.argmin(sizes, axis=1).astype(np.uint8)                  # the smallest; 0 only when all are 0
    length = sizes[np.arange(n), mode]
    buf = np.zeros((n, 36), np.uint8)
    for m, bits, sentinel in ((1, 2, 3), (2, 4, 15)):
        sel = np.nonzero(mode == m)[0]
        if not len(sel):
            continue
        r = rows[sel]
        code = np.minimum(r, sentinel).astype(np.uint8)
        per = 8 // bits                                                # codes per byte
        code = code.reshape(len(sel), 16 // per, per)
        shifts = (8 - bits * (np.arange(per) + 1)).astype(np.uint8)    # first code in the high bits
        packed = np.bitwise_or.reduce(code << shifts, axis=2)
        head = 16 // per
        buf[sel, :head] = packed
        out = r >= sentinel
        pos = head + np.cumsum(out, axis=1) - 1
        ri, ci = np.nonzero(out)
        buf[sel[ri], pos[ri, ci]] = r[ri, ci]
    sel = np.nonzero(mode == 3)[0]
    buf[sel, :16] = rows[sel]
    # headers: 2 bits per group, group 0 in the low bits
    m = mode.reshape(nb, stride, ng)
    mp = np.zeros((nb, stride, hb * 4), np.uint8)
    mp[..., :ng] = m
    mp = mp.reshape(nb, stride, hb, 4)
    header = (mp[..., 0] | (mp[..., 1] << 2) | (mp[..., 2] << 4) | (mp[..., 3] << 6)).astype(np.uint8)
    # one row per segment: [header][group 0] … [group ng-1] for every (block, byte)
    seg = np.zeros((nb, stride, 1 + ng, 36), np.uint8)
    seg[:, :, 0, :hb] = header
    seg[:, :, 1:, :] = buf.reshape(nb, stride, ng, 36)
    seg_len = np.empty((nb, stride, 1 + ng), np.int64)
    seg_len[:, :, 0] = hb
    seg_len[:, :, 1:] = length.reshape(nb, stride, ng)
    seg = seg.reshape(-1, 36)
    keep = np.arange(36)[None, :] < seg_len.reshape(-1, 1)
    return seg[keep]


def encode_vertex_buffer(data: np.ndarray) -> bytes:
    """``data`` (count, stride) bytes (stride a multiple of 4, as glTF wants) -> ATTRIBUTES-mode bytes."""
    a = np.ascontiguousarray(data, np.uint8)
    count, stride = a.shape
    if stride % 4 or stride > 256:
        raise ValueError(f"meshopt: element size {stride} must be a multiple of 4 up to 256")
    prev = np.empty_like(a)
    if count:
        prev[0] = a[0]                                                 # the tail holds the first element
        prev[1:] = a[:-1]
    z = _zigzag8((a.astype(np.int16) - prev).astype(np.uint8))
    per = _block_elements(stride)
    parts = [np.array([VERTEX_HEADER], np.uint8)]
    full = count // per
    if full:
        parts.append(_encode_blocks(z[:full * per].reshape(full, per, stride)))
    rest = count - full * per
    if rest:
        ne = (rest + 15) // 16 * 16
        last = np.zeros((1, ne, stride), np.uint8)
        last[0, :rest] = z[full * per:]
        parts.append(_encode_blocks(last))
    tail = np.zeros(max(TAIL_MIN, stride), np.uint8)
    if count:
        tail[-stride:] = a[0]
    parts.append(tail)
    return np.concatenate(parts).tobytes()


def _leb128(v: np.ndarray) -> np.ndarray:
    """Whole numbers (uint64) -> their LEB128 bytes, one after the other."""
    v = np.asarray(v, np.uint64)
    n = np.ones(len(v), np.int64)
    t = v >> np.uint64(7)
    while t.any():
        n += t > 0
        t >>= np.uint64(7)
    width = int(n.max()) if len(v) else 1
    k = np.arange(width, dtype=np.uint64)
    byte = ((v[:, None] >> (np.uint64(7) * k)) & np.uint64(0x7F)).astype(np.uint8)
    more = np.arange(width)[None, :] < (n[:, None] - 1)
    byte |= (more * 0x80).astype(np.uint8)
    return byte[np.arange(width)[None, :] < n[:, None]]


def encode_index_sequence(idx: np.ndarray) -> bytes:
    """Indices -> INDICES-mode bytes: each index as the zigzag difference to the index before (baseline 0 of the
    two the format has)."""
    i = np.asarray(idx, np.int64).ravel()
    if not len(i):
        return bytes([SEQUENCE_HEADER]) + bytes(SEQUENCE_TAIL)
    d = i - np.concatenate([[0], i[:-1]])
    zz = np.where(d < 0, ((-d) << 1) - 1, d << 1).astype(np.uint64)  # zigzag (32-bit range)
    v = zz << np.uint64(1)                                              # bit 0: baseline 0
    return bytes([SEQUENCE_HEADER]) + _leb128(v).tobytes() + bytes(SEQUENCE_TAIL)


# ---------------------------------------------------------------------------
# Blender's meshopt library (triangle lists)
# ---------------------------------------------------------------------------

class Native:
    """The meshopt C library through ctypes: Blender's glTF bridge (``encodeIndexBuffer`` …) or ``libmeshoptimizer``
    itself (``meshopt_encodeIndexBuffer`` …). Only the triangle codec is used from it."""

    def __init__(self, path: str):
        self.path = path
        lib = ctypes.CDLL(path)
        pre = "" if hasattr(lib, "encodeIndexBuffer") else "meshopt_"
        self._version = getattr(lib, pre + "encodeIndexVersion")
        self._version.argtypes = [ctypes.c_int]
        self._version.restype = None
        self._bound = getattr(lib, pre + "encodeIndexBufferBound")
        self._bound.argtypes = [ctypes.c_size_t, ctypes.c_size_t]
        self._bound.restype = ctypes.c_size_t
        self._encode = getattr(lib, pre + "encodeIndexBuffer")
        self._encode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
        self._encode.restype = ctypes.c_size_t
        self._decode = getattr(lib, pre + "decodeIndexBuffer")
        self._decode.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
        self._decode.restype = ctypes.c_int
        self.lib = lib

    def encode_index_buffer(self, idx: np.ndarray) -> bytes:
        i = np.ascontiguousarray(np.asarray(idx).ravel(), np.uint32)
        if len(i) % 3:
            raise ValueError("meshopt: a triangle list has 3 indices a triangle")
        bound = self._bound(len(i), int(i.max()) + 1 if len(i) else 0)
        out = np.empty(bound, np.uint8)
        self._version(1)
        n = self._encode(out.ctypes.data, bound, i.ctypes.data, len(i))
        if n == 0:
            raise RuntimeError("meshopt: the triangle list could not be packed")
        return out[:n].tobytes()

    def decode_index_buffer(self, src: bytes, count: int) -> np.ndarray:
        buf = np.frombuffer(bytes(src), np.uint8).copy()
        out = np.empty(count, np.uint32)
        res = self._decode(out.ctypes.data, count, 4, buf.ctypes.data, len(buf))
        if res != 0:
            raise ValueError(f"meshopt: malformed triangle list ({res})")
        return out.astype(np.int64)


_NATIVE: dict = {}


def use_native(paths) -> Native | None:
    """Loads the first of ``paths`` that is a meshopt library (kept for the next calls); None when none is."""
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        if p in _NATIVE:
            return _NATIVE[p]
        try:
            _NATIVE[p] = Native(p)
        except (OSError, AttributeError):
            continue
        _NATIVE["last"] = _NATIVE[p]
        return _NATIVE[p]
    return None


def native() -> Native | None:
    """The library ``use_native`` found last, or None."""
    return _NATIVE.get("last")


def encode_triangles(idx: np.ndarray) -> tuple[bytes, str]:
    """A triangle list -> (bytes, mode): TRIANGLES with the library, INDICES without."""
    lib = native()
    if lib is not None:
        return lib.encode_index_buffer(idx), "TRIANGLES"
    return encode_index_sequence(idx), "INDICES"


# ---------------------------------------------------------------------------
# decoding (reader, tests)
# ---------------------------------------------------------------------------

_SENT2 = np.array([sum(((b >> s) & 3) == 3 for s in (0, 2, 4, 6)) for b in range(256)], np.int64)
_SENT4 = np.array([((b >> 4) == 15) + ((b & 15) == 15) for b in range(256)], np.int64)


def decode_vertex_buffer(src: bytes, count: int, stride: int) -> np.ndarray:
    """ATTRIBUTES-mode bytes -> (count, stride) uint8. Raises ValueError on a malformed buffer."""
    s = np.frombuffer(bytes(src), np.uint8)
    if not len(s) or s[0] != VERTEX_HEADER:
        raise ValueError("meshopt: not a version 0 vertex buffer")
    if len(s) < 1 + max(TAIL_MIN, stride):
        raise ValueError("meshopt: vertex buffer too short")
    sb = bytes(s)
    per = _block_elements(stride)
    end = len(s) - max(TAIL_MIN, stride)
    pos = 1
    starts, modes = [], []                     # per group, in stream order: (data offset, mode)
    order = []                                 # per group: (element of its first value, byte)
    base = 0
    while base < count:
        ne = min(count - base, per)
        ng = (ne + 15) // 16
        hb = (ng + 3) // 4
        for byte in range(stride):
            head = sb[pos:pos + hb]
            pos += hb
            for gi in range(ng):
                m = (head[gi >> 2] >> ((gi & 3) << 1)) & 3
                starts.append(pos)
                modes.append(m)
                order.append((base + gi * 16, byte))
                if m == 1:
                    pos += 4 + int(_SENT2[sb[pos]] + _SENT2[sb[pos + 1]] + _SENT2[sb[pos + 2]] + _SENT2[sb[pos + 3]])
                elif m == 2:
                    pos += 8 + int(sum(_SENT4[sb[pos + k]] for k in range(8)))
                elif m == 3:
                    pos += 16
                if pos > end:
                    raise ValueError("meshopt: vertex buffer runs past its end")
        base += ne
    ng_all = len(starts)
    deltas = np.zeros((ng_all, 16), np.uint8)
    st = np.array(starts, np.int64)
    md = np.array(modes, np.int64)
    pad = np.concatenate([s, np.zeros(40, np.uint8)])
    for m, bits, sentinel in ((1, 2, 3), (2, 4, 15)):
        sel = np.nonzero(md == m)[0]
        if not len(sel):
            continue
        per_b = 8 // bits
        head = 16 // per_b
        packed = pad[st[sel, None] + np.arange(head)[None, :]]
        shifts = (8 - bits * (np.arange(per_b) + 1)).astype(np.uint8)
        code = ((packed[:, :, None] >> shifts) & ((1 << bits) - 1)).reshape(len(sel), 16)
        out = code == sentinel
        extra = st[sel, None] + head + np.cumsum(out, axis=1) - 1
        vals = np.where(out, pad[np.where(out, extra, 0)], code)
        deltas[sel] = vals
    sel = np.nonzero(md == 3)[0]
    deltas[sel] = pad[st[sel, None] + np.arange(16)[None, :]]
    # undo the zigzag and add up per byte
    dz = deltas.astype(np.int16)
    signed = np.where(dz & 1, ~(dz >> 1), dz >> 1).astype(np.int16)
    out = np.zeros((count, stride), np.int64)
    od = np.array(order, np.int64).reshape(-1, 2)
    el = od[:, :1] + np.arange(16)[None, :]
    ok = el < count
    out[el[ok], np.broadcast_to(od[:, 1:], el.shape)[ok]] = signed[ok]
    first = s[len(s) - stride:].astype(np.int64)
    return ((np.cumsum(out, axis=0) + first[None, :]) & 0xFF).astype(np.uint8)


def decode_index_sequence(src: bytes, count: int) -> np.ndarray:
    """INDICES-mode bytes -> ``count`` indices (int64)."""
    s = np.frombuffer(bytes(src), np.uint8)
    if not len(s) or s[0] != SEQUENCE_HEADER:
        raise ValueError("meshopt: not an index sequence")
    b = s[1:len(s) - SEQUENCE_TAIL]
    ends = np.nonzero(b < 0x80)[0]
    if len(ends) < count:
        raise ValueError("meshopt: index sequence too short")
    ends = ends[:count]
    begins = np.concatenate([[0], ends[:-1] + 1])
    width = int((ends - begins).max()) + 1 if count else 1
    k = np.arange(width)
    take = begins[:, None] + k[None, :]
    valid = take <= ends[:, None]
    vals = np.where(valid, b[np.minimum(take, len(b) - 1)].astype(np.uint64) & np.uint64(0x7F), np.uint64(0))
    v = (vals << (np.uint64(7) * k.astype(np.uint64))[None, :]).sum(axis=1, dtype=np.uint64)
    v &= np.uint64(0xFFFFFFFF)
    which = (v & np.uint64(1)).astype(np.int64)
    z = (v >> np.uint64(1)).astype(np.int64)
    delta = np.where(z & 1, -((z + 1) >> 1), z >> 1)
    out = np.empty(count, np.int64)
    last = [0, 0]
    if which.any():                          # two baselines: walk (not written by this encoder; other files)
        for j in range(count):
            w = int(which[j])
            last[w] = (last[w] + int(delta[j])) & 0xFFFFFFFF
            out[j] = last[w]
        return out
    return np.cumsum(delta) & 0xFFFFFFFF


def _dezig(v: int) -> int:
    return ~(v >> 1) if v & 1 else v >> 1


def decode_index_buffer(src: bytes, count: int) -> np.ndarray:
    """TRIANGLES-mode bytes -> ``count`` indices (int64): with the library when it is there, else in Python (the
    reference decoder of the format, one triangle at a time – fine for small files)."""
    lib = native()
    if lib is not None:
        return lib.decode_index_buffer(src, count)
    s = bytes(src)
    if not s or s[0] != TRIANGLES_HEADER:
        raise ValueError("meshopt: not a version 1 triangle list")
    if count % 3 or len(s) < 1 + count // 3 + 16:
        raise ValueError("meshopt: triangle list too short")
    tri = count // 3
    code_at, data_at, aux_at = 1, 1 + tri, len(s) - 16
    out = np.empty(count, np.int64)
    edges = [0] * 32
    verts = [0] * 16
    nxt = last = 0

    def push(fifo, v):
        fifo.insert(0, v)
        fifo.pop()

    def leb():
        nonlocal data_at
        n = shift = 0
        while True:
            b = s[data_at]
            data_at += 1
            n |= (b & 0x7F) << shift
            if b < 0x80:
                return n
            shift += 7

    for t in range(tri):
        code = s[code_at]
        code_at += 1
        b0, b1 = code >> 4, code & 0x0F
        if b0 < 0x0F:
            a, b = edges[b0 * 2], edges[b0 * 2 + 1]
            if b1 == 0:
                c = nxt
                nxt += 1
                push(verts, c)
            elif b1 < 0x0D:
                c = verts[b1]
            elif b1 == 0x0D:
                last -= 1
                c = last
                push(verts, c)
            elif b1 == 0x0E:
                last += 1
                c = last
                push(verts, c)
            else:
                last += _dezig(leb())
                c = last
                push(verts, c)
            for v in (b, c, c, a):
                push(edges, v)
        else:
            if b1 < 0x0E:
                e = s[aux_at + b1]
                z, w = e >> 4, e & 0x0F
                a = nxt
                nxt += 1
                if z == 0:
                    b = nxt
                    nxt += 1
                else:
                    b = verts[z - 1]
                if w == 0:
                    c = nxt
                    nxt += 1
                else:
                    c = verts[w - 1]
                push(verts, a)
                if z == 0:
                    push(verts, b)
                if w == 0:
                    push(verts, c)
            else:
                e = s[data_at]
                data_at += 1
                if e == 0:
                    nxt = 0
                z, w = e >> 4, e & 0x0F
                if b1 == 0x0E:
                    a = nxt
                    nxt += 1
                else:
                    last += _dezig(leb())
                    a = last
                if z == 0:
                    b = nxt
                    nxt += 1
                elif z == 0x0F:
                    last += _dezig(leb())
                    b = last
                else:
                    b = verts[z - 1]
                if w == 0:
                    c = nxt
                    nxt += 1
                elif w == 0x0F:
                    last += _dezig(leb())
                    c = last
                else:
                    c = verts[w - 1]
                push(verts, a)
                if z in (0, 0x0F):
                    push(verts, b)
                if w in (0, 0x0F):
                    push(verts, c)
            for v in (a, b, b, c, c, a):
                push(edges, v)
        out[3 * t:3 * t + 3] = (a, b, c)
    return out & 0xFFFFFFFF
