"""meshopt compression (task 0105), no Blender: the NumPy vertex and index codecs, the Python reader of the triangle
codec, and Blender's own meshopt library when it is there (Blender as a Python module ships libmeshoptimizer)."""

import importlib.util
import os

import numpy as np
import pytest

from fresing_render.core import meshopt as mo

# 20 elements of 4 bytes: the library itself (meshopt_encodeVertexBuffer, version 0) must read what NumPy writes.
REF_DATA = np.array([[i, (i * 7) % 256, 255 - i, i // 3] for i in range(20)], np.uint8)


def _canon(idx):
    """Triangles with their smallest corner first (the triangle codec may turn a triangle, never flip it)."""
    t = np.asarray(idx).reshape(-1, 3)
    r = np.argmin(t, axis=1)
    return np.stack([t[np.arange(len(t)), (r + k) % 3] for k in range(3)], axis=1)


def _grid(n=40):
    """A triangulated n x n grid: indices in the order a CAD mesher writes them, points as 16-bit numbers."""
    y, x = np.mgrid[0:n, 0:n]
    pos = np.stack([x.ravel() * 37, y.ravel() * 41, (x * y).ravel() % 97], axis=1).astype(np.int16)
    k = (y[:-1, :-1] * n + x[:-1, :-1]).ravel()
    tri = np.concatenate([np.stack([k, k + 1, k + n], 1), np.stack([k + 1, k + n + 1, k + n], 1)], axis=1)
    return pos, tri.reshape(-1)


@pytest.mark.parametrize("count,stride", [(0, 4), (1, 4), (15, 8), (16, 4), (17, 12), (255, 8), (256, 8),
                                          (257, 8), (1025, 8), (5000, 4), (3000, 32)])
def test_vertex_buffer_round_trip(count, stride):
    rng = np.random.default_rng(count + stride)
    walk = np.cumsum(rng.integers(-40, 40, (count, stride // 2)), axis=0).astype(np.int16)
    a = walk.view(np.uint8).reshape(count, stride)
    for data in (a, rng.integers(0, 256, (count, stride)).astype(np.uint8), np.zeros((count, stride), np.uint8)):
        enc = mo.encode_vertex_buffer(data)
        assert enc[0] == mo.VERTEX_HEADER
        assert np.array_equal(mo.decode_vertex_buffer(enc, count, stride), data)


def test_vertex_buffer_packs_neighbouring_points():
    pos, _ = _grid()
    raw = np.concatenate([pos, np.zeros((len(pos), 1), np.int16)], axis=1).view(np.uint8)   # 8-byte elements
    enc = mo.encode_vertex_buffer(raw)
    assert len(enc) < 0.6 * raw.nbytes
    with pytest.raises(ValueError):
        mo.encode_vertex_buffer(np.zeros((4, 6), np.uint8))           # glTF wants a multiple of 4 bytes


def test_vertex_buffer_is_read_by_the_library():
    """meshopt's own decoder reads the NumPy encoder's bytes, and they are no longer than its own encoder's (the two
    may choose differently where two packings are the same size)."""
    import ctypes
    lib = _library()
    pos, _ = _grid()
    for data in (REF_DATA, np.concatenate([pos, np.zeros((len(pos), 1), np.int16)], axis=1).view(np.uint8)):
        data = np.ascontiguousarray(data)
        enc = mo.encode_vertex_buffer(data)
        assert enc[-data.shape[1]:] == data[0].tobytes() and len(enc) >= 1 + 32      # tail: the first element last
        if lib is None or not hasattr(lib.lib, "meshopt_encodeVertexBuffer"):
            continue
        L = lib.lib
        L.meshopt_encodeVertexVersion.argtypes = [ctypes.c_int]
        L.meshopt_encodeVertexVersion(0)
        L.meshopt_encodeVertexBuffer.restype = ctypes.c_size_t
        L.meshopt_encodeVertexBuffer.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t,
                                                 ctypes.c_size_t]
        out = np.zeros(len(enc) * 2 + 4096, np.uint8)
        n = L.meshopt_encodeVertexBuffer(out.ctypes.data, len(out), data.ctypes.data, len(data), data.shape[1])
        assert len(enc) <= n
        L.meshopt_decodeVertexBuffer.restype = ctypes.c_int
        L.meshopt_decodeVertexBuffer.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_void_p,
                                                 ctypes.c_size_t]
        back = np.zeros_like(data)
        src = np.frombuffer(enc, np.uint8).copy()
        assert L.meshopt_decodeVertexBuffer(back.ctypes.data, len(data), data.shape[1], src.ctypes.data, len(src)) == 0
        assert np.array_equal(back, data)


def test_malformed_vertex_buffers_are_refused():
    enc = mo.encode_vertex_buffer(np.arange(400, dtype=np.uint8).reshape(100, 4))
    with pytest.raises(ValueError):
        mo.decode_vertex_buffer(b"\x00" + enc[1:], 100, 4)
    with pytest.raises(ValueError):
        mo.decode_vertex_buffer(enc[:20], 100, 4)


def test_index_sequence_round_trip():
    _, tri = _grid()
    for idx in (tri, np.array([0, 70000, 3, 2 ** 30 - 1, 0]), np.zeros(0, np.int64)):
        enc = mo.encode_index_sequence(idx)
        assert enc[0] == mo.SEQUENCE_HEADER and enc[-mo.SEQUENCE_TAIL:] == bytes(mo.SEQUENCE_TAIL)
        assert np.array_equal(mo.decode_index_sequence(enc, len(idx)), idx)
    assert len(mo.encode_index_sequence(tri)) < 2 * len(tri)
    with pytest.raises(ValueError):
        mo.encode_index_sequence(np.array([0, 2 ** 31]))              # under 2 bytes an index on a mesh


def _library():
    """Blender's libmeshoptimizer next to the bpy module, when it is installed (the pytest machines have it)."""
    spec = importlib.util.find_spec("bpy")
    if spec is None or not spec.origin:
        return None
    base = os.path.dirname(spec.origin)
    paths = [os.path.join(base, "lib", "libmeshoptimizer.so"), os.path.join(base, "lib", "meshoptimizer.dll")]
    return mo.use_native(paths)


def test_triangle_codec_with_blenders_library_and_the_python_reader():
    lib = _library()
    _, tri = _grid()
    if lib is None:                         # no library: the NumPy codec packs triangle lists
        mo._NATIVE.clear()
        enc, mode = mo.encode_triangles(tri)
        assert mode == "INDICES"
        assert np.array_equal(mo.decode_index_sequence(enc, len(tri)), tri)
        return
    enc, mode = mo.encode_triangles(tri)
    assert mode == "TRIANGLES" and enc[0] == mo.TRIANGLES_HEADER
    assert len(enc) < 0.5 * len(mo.encode_index_sequence(tri))           # much tighter than the sequence codec
    back = lib.decode_index_buffer(enc, len(tri))
    assert np.array_equal(_canon(back), _canon(tri))                     # same triangles, same winding
    keep = dict(mo._NATIVE)
    mo._NATIVE.clear()
    try:
        assert np.array_equal(mo.decode_index_buffer(enc, len(tri)), back)   # the Python reader agrees
        with pytest.raises(ValueError):
            mo.decode_index_buffer(enc[:10], len(tri))
    finally:
        mo._NATIVE.update(keep)
    with pytest.raises(ValueError):
        lib.encode_index_buffer(np.arange(4))                              # not whole triangles


def test_no_library_found():
    keep = dict(mo._NATIVE)
    try:
        mo._NATIVE.clear()
        assert mo.use_native(["", "/nowhere/libmeshoptimizer.so", __file__]) is None
        assert mo.native() is None
    finally:
        mo._NATIVE.update(keep)
