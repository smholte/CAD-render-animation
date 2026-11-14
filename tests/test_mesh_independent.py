"""Task 0117: the independent tester's tests of the mesh import (written by an agent that did not write the reader).

Odd glTF / OBJ files, the face split on facetted shapes in odd places, loose parts, the job runner and a few app-side
checks. Every file is made here, under tmp_path; nothing is downloaded.

Tests marked ``xfail(strict=True, reason="FINDING n: ...")`` show a fault found by the tester: they fail now and pass
once it is fixed (then remove the mark).
"""

from __future__ import annotations

import base64
import json
import math
import os
import shutil
import struct
import sys
import time
import urllib.parse

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import make_test_mesh as maker  # noqa: E402
from fresing_render.core import mesh_faces  # noqa: E402
from fresing_render.importer import mesh_reader, runner  # noqa: E402

DATA = os.path.join(HERE, "data")
CRANE = os.path.join(DATA, "test_mesh_crane.glb")
CRANE_B = os.path.join(DATA, "test_mesh_crane_b.glb")


# =====================================================================================================================
# helpers: a small glTF writer that can write the odd things real files have
# =====================================================================================================================

FLOAT, U8, U16, U32, I8, I16 = 5126, 5121, 5123, 5125, 5120, 5122
_DT = {FLOAT: np.float32, U8: np.uint8, U16: np.uint16, U32: np.uint32, I8: np.int8, I16: np.int16}
_KIND = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}


class G:
    """A glTF document in the making (file coordinates: Y up, metres)."""

    def __init__(self, scenes=True):
        self.doc = {"asset": {"version": "2.0"}, "nodes": [], "meshes": [], "accessors": [], "bufferViews": [],
                    "buffers": [{"byteLength": 0}]}
        if scenes:
            self.doc["scene"] = 0
            self.doc["scenes"] = [{"nodes": []}]
        self.bin = bytearray()

    def view(self, data: bytes, stride=None) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        v = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if stride:
            v["byteStride"] = stride
        self.bin += data
        self.doc["bufferViews"].append(v)
        return len(self.doc["bufferViews"]) - 1

    def acc(self, arr, comp=FLOAT, normalized=False, **extra) -> int:
        a = np.asarray(arr)
        a2 = a.reshape(len(a), -1) if a.ndim > 1 else a.reshape(-1, 1)
        data = np.ascontiguousarray(a2.astype(_DT[comp])).tobytes()
        acc = {"bufferView": self.view(data), "componentType": comp, "count": len(a2), "type": _KIND[a2.shape[1]]}
        if normalized:
            acc["normalized"] = True
        if comp == FLOAT and a2.shape[1] == 3:
            acc["min"] = [float(x) for x in a2.min(0)]
            acc["max"] = [float(x) for x in a2.max(0)]
        acc.update(extra)
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def prim(self, pos=None, tri=None, nrm=None, uv=None, mode=None, material=None, icomp=U32, **attrs) -> dict:
        a = dict(attrs)
        if pos is not None:
            a["POSITION"] = self.acc(pos)
        if nrm is not None:
            a["NORMAL"] = self.acc(nrm)
        if uv is not None:
            a["TEXCOORD_0"] = self.acc(uv)
        p = {"attributes": a}
        if tri is not None:
            p["indices"] = self.acc(np.asarray(tri).reshape(-1), icomp)
        if mode is not None:
            p["mode"] = mode
        if material is not None:
            p["material"] = material
        return p

    def mesh(self, prims, name=None) -> int:
        m = {"primitives": list(prims)}
        if name is not None:
            m["name"] = name
        self.doc["meshes"].append(m)
        return len(self.doc["meshes"]) - 1

    def node(self, name=None, mesh=None, parent=None, root=True, **kw) -> int:
        nd = dict(kw)
        if name is not None:
            nd["name"] = name
        if mesh is not None:
            nd["mesh"] = mesh
        self.doc["nodes"].append(nd)
        k = len(self.doc["nodes"]) - 1
        if parent is not None:
            self.doc["nodes"][parent].setdefault("children", []).append(k)
        elif root and "scenes" in self.doc:
            self.doc["scenes"][0]["nodes"].append(k)
        return k

    def material(self, **m) -> int:
        self.doc.setdefault("materials", []).append(m)
        return len(self.doc["materials"]) - 1

    def glb(self, path) -> str:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        js = json.dumps(self.doc, ensure_ascii=False).encode("utf-8")
        js += b" " * (-len(js) % 4)
        body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(self.bin), 0x004E4942) + self.bin
        with open(path, "wb") as fh:
            fh.write(struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body)
        return str(path)

    def gltf(self, path, bin_name=None) -> str:
        """A .gltf with the buffer as a data: URI, or as an external file ``bin_name`` (URL-encoded in the uri)."""
        doc = json.loads(json.dumps(self.doc))
        doc["buffers"][0]["byteLength"] = len(self.bin)
        if bin_name is None:
            doc["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(
                bytes(self.bin)).decode()
        else:
            doc["buffers"][0]["uri"] = urllib.parse.quote(bin_name)
            with open(os.path.join(os.path.dirname(str(path)), bin_name), "wb") as fh:
                fh.write(bytes(self.bin))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False)
        return str(path)


def tri_quad():
    """A unit square in the file's XY plane (z = 0), two triangles, facing +Z (glTF)."""
    pos = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], np.float32)
    return pos, np.array([[0, 1, 2], [0, 2, 3]], np.uint32)


def box(lo=(0, 0, 0), hi=(1, 1, 1)):
    """A closed box, 12 triangles, outward winding, shared corners."""
    x0, y0, z0 = lo
    x1, y1, z1 = hi
    p = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], np.float64)
    t = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                  [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]], np.int64)
    return p, t


def read(path, tmp_path, name="out", **kw):
    out = str(tmp_path / name)
    info = mesh_reader.read_mesh(str(path), out, **kw)
    return info, np.load(os.path.join(out, "meshes.npz")), out


def parts(info):
    return [n for n in info["nodes"] if n["kind"] == "part"]


def by_name(info, name, k=0):
    hits = [n for n in info["nodes"] if n["name"] == name]
    assert len(hits) > k, (name, [n["name"] for n in info["nodes"]])
    return hits[k]


def world(info, node):
    k = info["nodes"].index(node)
    m = np.eye(4)
    while k >= 0:
        n = info["nodes"][k]
        m = (np.array(n["matrix"]) if n["matrix"] else np.eye(4)) @ m
        k = n["parent"]
    return m


def world_points(info, arr, node):
    """A part's corners in the app's world (metres, Z up), in the order of its mesh."""
    m = world(info, node)
    p = arr[f"p{node['mesh']}"].astype(np.float64)
    return p @ m[:3, :3].T + m[:3, 3]


def world_tris(info, arr, node):
    """A part's triangles as (m, 3, 3) world corners, with the winding as the app shows them (a mirrored part's
    triangles turned round, as Blender does for an object with a negative determinant)."""
    m = world(info, node)
    p = world_points(info, arr, node)
    t = arr[f"t{node['mesh']}"]
    w = p[t]
    if np.linalg.det(m[:3, :3]) < 0:
        w = w[:, ::-1]
    return w


def app(v):
    """glTF (x, y, z) -> the app's (x, -z, y)."""
    v = np.asarray(v, np.float64)
    return np.stack((v[..., 0], -v[..., 2], v[..., 1]), axis=-1)


def same_point_set(a, b, tol=1e-5):
    a = np.unique(np.round(np.asarray(a) / tol).astype(np.int64), axis=0)
    b = np.unique(np.round(np.asarray(b) / tol).astype(np.int64), axis=0)
    return a.shape == b.shape and (a == b).all()


# =====================================================================================================================
# glTF: attributes, accessors, primitive modes
# =====================================================================================================================

def test_no_normals_gives_flat_normals_and_y_up_to_z_up(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("Q", g.mesh([g.prim(pos, tri)]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    q = by_name(info, "Q")
    w = world_points(info, arr, q)
    assert same_point_set(w, app(pos))
    n = arr[f"n{q['mesh']}"]
    assert np.allclose(n, [0, -1, 0], atol=1e-6)            # glTF +Z faces the app's -Y


@pytest.mark.parametrize("bad", ["zero", "nan"])
def test_broken_normals_are_mended(tmp_path, bad):
    g = G()
    pos, tri = tri_quad()
    nrm = np.zeros_like(pos) if bad == "zero" else np.full_like(pos, np.nan)
    nrm[0] = (0, 0, 1)
    g.node("Q", g.mesh([g.prim(pos, tri, nrm=nrm)]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    n = arr[f"n{by_name(info, 'Q')['mesh']}"]
    assert np.isfinite(n).all()
    assert np.allclose(np.linalg.norm(n, axis=1), 1.0, atol=1e-5)
    assert np.allclose(n, [0, -1, 0], atol=1e-5)


def test_interleaved_buffer_with_byte_stride(tmp_path):
    g = G()
    pos, tri = tri_quad()
    pos = pos + np.float32([5, 0, 0])
    nrm = np.tile(np.float32([0, 0, 1]), (4, 1))
    inter = np.hstack((pos, nrm)).astype(np.float32).tobytes()            # 24 bytes per corner
    v = g.view(inter, stride=24)
    g.doc["accessors"].append({"bufferView": v, "componentType": FLOAT, "count": 4, "type": "VEC3",
                               "min": pos.min(0).tolist(), "max": pos.max(0).tolist()})
    g.doc["accessors"].append({"bufferView": v, "byteOffset": 12, "componentType": FLOAT, "count": 4, "type": "VEC3"})
    p = {"attributes": {"POSITION": 0, "NORMAL": 1}, "indices": g.acc(tri.reshape(-1), U16)}
    g.node("I", g.mesh([p]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    q = by_name(info, "I")
    assert same_point_set(world_points(info, arr, q), app(pos))
    assert np.allclose(arr[f"n{q['mesh']}"], [0, -1, 0], atol=1e-6)


def test_sparse_accessor_moves_one_corner(tmp_path):
    g = G()
    pos, tri = tri_quad()
    base = g.acc(pos)
    iv = g.view(np.array([2], np.uint16).tobytes())
    vv = g.view(np.array([[3, 3, 0]], np.float32).tobytes())
    g.doc["accessors"][base]["sparse"] = {"count": 1, "indices": {"bufferView": iv, "componentType": U16},
                                          "values": {"bufferView": vv}}
    g.node("S", g.mesh([{"attributes": {"POSITION": base}, "indices": g.acc(tri.reshape(-1), U16)}]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    w = world_points(info, arr, by_name(info, "S"))
    want = pos.astype(np.float64).copy()
    want[2] = (3, 3, 0)
    assert same_point_set(w, app(want))


def test_sparse_accessor_without_buffer_view(tmp_path):
    g = G()
    pos, tri = tri_quad()
    iv = g.view(np.array([0, 1, 2, 3], np.uint8).tobytes())
    vv = g.view(pos.tobytes())
    g.doc["accessors"].append({"componentType": FLOAT, "count": 4, "type": "VEC3", "min": [0, 0, 0], "max": [1, 1, 0],
                               "sparse": {"count": 4, "indices": {"bufferView": iv, "componentType": U8},
                                          "values": {"bufferView": vv}}})
    g.node("S", g.mesh([{"attributes": {"POSITION": 0}, "indices": g.acc(tri.reshape(-1), U8)}]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert same_point_set(world_points(info, arr, by_name(info, "S")), app(pos))


@pytest.mark.parametrize("comp, top", [(U16, 65535), (U8, 255), (I16, 32767), (I8, 127)])
def test_quantized_positions_with_node_scale(tmp_path, comp, top):
    """KHR_mesh_quantization: normalised integer positions, the node's scale makes them metres."""
    g = G()
    g.doc["extensionsUsed"] = g.doc["extensionsRequired"] = ["KHR_mesh_quantization"]
    q = np.array([[0, 0, 0], [top, 0, 0], [top, top, 0], [0, top, 0]])
    pa = g.acc(q, comp, normalized=True, min=[0, 0, 0], max=[top, top, 0])
    g.node("Q", g.mesh([{"attributes": {"POSITION": pa}, "indices": g.acc([0, 1, 2, 0, 2, 3], U8)}]),
           scale=[2, 4, 1], translation=[1, 0, 0])
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    w = world_points(info, arr, by_name(info, "Q"))
    want = app(np.array([[1, 0, 0], [3, 0, 0], [3, 4, 0], [1, 4, 0]]))
    assert same_point_set(w, want, tol=1e-4)


def _geom_normals(w):
    n = np.cross(w[:, 1] - w[:, 0], w[:, 2] - w[:, 0])
    return n / np.linalg.norm(n, axis=1, keepdims=True)


@pytest.mark.parametrize("mode", [5, 6])
def test_strips_and_fans_keep_one_winding(tmp_path, mode):
    g = G()
    if mode == 5:                                   # a strip of 6 corners along x: 4 triangles, all facing +Z
        pos = np.array([[0, 0, 0], [0, 1, 0], [1, 0, 0], [1, 1, 0], [2, 0, 0], [2, 1, 0]], np.float32)
        order = [1, 0, 3, 2, 5, 4]                  # (0,1,0) (0,0,0) (1,1,0): counter-clockwise seen from +Z
        pos = pos[order]
    else:                                           # a fan round the centre of a hexagon
        a = np.radians(np.arange(7) * 60.0)
        pos = np.vstack(([[0, 0, 0]], np.stack((np.cos(a), np.sin(a), 0 * a), 1))).astype(np.float32)
    g.node("M", g.mesh([g.prim(pos, np.arange(len(pos)), mode=mode, icomp=U8)]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    nd = by_name(info, "M")
    w = world_tris(info, arr, nd)
    assert len(w) == (4 if mode == 5 else 6)
    n = _geom_normals(w)
    assert np.allclose(n, [0, -1, 0], atol=1e-6), n          # glTF +Z = the app's -Y, every triangle


@pytest.mark.parametrize("icomp", [U8, U16, U32, None])
def test_index_types_and_no_indices(tmp_path, icomp):
    g = G()
    pos, tri = tri_quad()
    if icomp is None:
        g.node("Q", g.mesh([g.prim(pos[tri.reshape(-1)])]))
    else:
        g.node("Q", g.mesh([g.prim(pos, tri, icomp=icomp)]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    q = by_name(info, "Q")
    assert len(arr[f"t{q['mesh']}"]) == 2
    assert same_point_set(world_points(info, arr, q), app(pos))


def test_points_and_lines_beside_triangles(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("Mixed", g.mesh([g.prim(pos, np.arange(4), mode=0), g.prim(pos, [0, 1, 1, 2], mode=1),
                            g.prim(pos, tri), g.prim(pos, [0, 1, 2, 3], mode=3)]))
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert len(parts(info)) == 1
    assert any("points or lines" in n for n in info["notes"])


def test_only_lines_says_no_faces(tmp_path):
    g = G()
    pos, _ = tri_quad()
    g.node("L", g.mesh([g.prim(pos, [0, 1, 1, 2], mode=1)]))
    with pytest.raises(mesh_reader.MeshError, match="no faces"):
        read(g.glb(tmp_path / "a.glb"), tmp_path)


def test_empty_nodes_and_cameras_only_say_no_faces(tmp_path):
    g = G()
    g.doc["cameras"] = [{"type": "perspective", "perspective": {"yfov": 0.8, "znear": 0.1}}]
    k = g.node("Rig")
    g.node("Cam", parent=k, camera=0)
    with pytest.raises(mesh_reader.MeshError, match="no faces"):
        read(g.glb(tmp_path / "a.glb"), tmp_path)


# =====================================================================================================================
# glTF: the node tree
# =====================================================================================================================

def test_no_scenes_array_takes_the_nodes_no_one_holds(tmp_path):
    g = G(scenes=False)
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    a = g.node("A")
    g.node("B", m, parent=a)
    g.node("C", m)
    info, _, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert sorted(n["uid"] for n in info["nodes"]) == ["A#1", "A#1/B#1", "C#1"]


def test_several_scenes_reads_the_default_scene(tmp_path):
    g = G()
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    g.node("In scene 0", m)
    k = g.node("In scene 1", m, root=False)
    g.doc["scenes"].append({"nodes": [k]})
    g.doc["scene"] = 1
    info, _, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert [n["name"] for n in info["nodes"]] == ["In scene 1"]


def _trs_matrix(t, q, s):
    x, y, z, w = q
    r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                  [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                  [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = r * np.asarray(s)
    m[:3, 3] = t
    return m


def test_trs_and_matrix_nodes_land_in_the_same_place(tmp_path):
    t, q, s = [1.0, 2.0, 3.0], [0.0, math.sin(0.35), 0.0, math.cos(0.35)], [1.0, 2.0, 0.5]
    m = _trs_matrix(t, q, s)
    g = G()
    p, tr = box()
    mesh = g.mesh([g.prim(p, tr)])
    g.node("TRS", mesh, translation=t, rotation=q, scale=s)
    g.node("MAT", mesh, matrix=[float(x) for x in m.T.reshape(-1)])
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    a = world_points(info, arr, by_name(info, "TRS"))
    b = world_points(info, arr, by_name(info, "MAT"))
    assert np.allclose(a, b, atol=1e-6)
    assert same_point_set(a, app(p @ m[:3, :3].T + m[:3, 3]), tol=1e-4)


def test_mirrored_child_under_a_moved_parent_lands_right(tmp_path):
    """Negative scale (a mirrored wheel) under a turned and moved parent: the cache's matrices put every corner
    where glTF puts it, turned to Z up, and the faces still face outwards."""
    g = G()
    p, tr = box((0.5, 0, 0), (1.5, 1, 1))
    mesh = g.mesh([g.prim(p, tr)])
    q = [0.0, 0.0, math.sin(0.4), math.cos(0.4)]
    par = g.node("P", translation=[10, 0, 0], rotation=q)
    g.node("R", mesh, parent=par, scale=[-1, 1, 1], translation=[0, 2, 0])
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    nd = by_name(info, "R")
    want = p * [-1, 1, 1] + [0, 2, 0]
    pm = _trs_matrix([10, 0, 0], q, [1, 1, 1])
    want = want @ pm[:3, :3].T + pm[:3, 3]
    assert same_point_set(world_points(info, arr, nd), app(want), tol=1e-4)
    w = world_tris(info, arr, nd)
    centre = app(want).mean(0)
    outward = np.einsum("ij,ij->i", _geom_normals(w), w.mean(1) - centre)
    assert (outward > 0).all()


def test_node_in_two_parents_and_a_cycle_do_not_hang(tmp_path):
    g = G()
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    a = g.node("A")
    b = g.node("B", parent=a)
    c = g.node("C", m, parent=b)
    g.doc["nodes"][c].setdefault("children", []).append(a)      # a cycle C -> A
    g.doc["nodes"][a]["children"].append(c)                    # C under A as well
    t0 = time.time()
    info, _, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert time.time() - t0 < 10
    assert len(parts(info)) == 1
    assert len({n["uid"] for n in info["nodes"]}) == len(info["nodes"])


def test_one_mesh_on_many_nodes_is_stored_once(tmp_path):
    g = G()
    p, tr = box()
    mesh = g.mesh([g.prim(p, tr)], name="Bolt")
    for k in range(5):
        g.node(None, mesh, translation=[k * 2.0, 0, 0])
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path, split="on")
    ps = parts(info)
    assert len(ps) == 5 and len({n["mesh"] for n in ps}) == 1
    assert len(info["meshes"]) == 1
    assert len({n["uid"] for n in ps}) == 5                    # named after the mesh, numbered
    assert all(n["name"] == "Bolt" for n in ps)


def test_node_with_mesh_and_children(tmp_path):
    g = G()
    p, tr = box()
    mesh = g.mesh([g.prim(p, tr)])
    a = g.node("Arm", mesh)
    g.node("Hand", mesh, parent=a, translation=[0, 2, 0])
    info, arr, _ = read(g.glb(tmp_path / "a.glb"), tmp_path)
    assert len(parts(info)) == 2
    arm = by_name(info, "Arm")
    assert arm["kind"] == "assembly"
    hand = by_name(info, "Hand")
    assert world_points(info, arr, hand)[:, 2].min() == pytest.approx(2.0)


def test_several_primitives_one_part_each_named_by_material(tmp_path):
    g = G()
    pos, tri = tri_quad()
    red = g.material(name="Red", pbrMetallicRoughness={"baseColorFactor": [1, 0, 0, 1]})
    blue = g.material(name="Blue", pbrMetallicRoughness={"baseColorFactor": [0, 0, 1, 1]})
    g.node("Two", g.mesh([g.prim(pos, tri, material=red), g.prim(pos + 2, tri, material=blue),
                          g.prim(pos + 4, tri, material=red)]))
    info, _, _ = read(g.glb(tmp_path / "a.glb"), tmp_path, split="off")
    names = sorted(n["name"] for n in parts(info))
    assert names == ["Blue", "Red", "Red"]
    assert len({n["uid"] for n in info["nodes"]}) == len(info["nodes"])


# =====================================================================================================================
# glTF: buffers, images, materials
# =====================================================================================================================

def test_data_uri_buffer(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("D", g.mesh([g.prim(pos, tri)]))
    info, arr, _ = read(g.gltf(tmp_path / "d.gltf"), tmp_path)
    assert same_point_set(world_points(info, arr, by_name(info, "D")), app(pos))


def test_external_bin_and_image_with_spaces_and_accents(tmp_path):
    g = G()
    pos, tri = tri_quad()
    png = maker.checker(8, 2)
    folder = tmp_path / "Modèle 3D ö"
    folder.mkdir()
    (folder / "tëxture 1.png").write_bytes(png)
    g.doc["images"] = [{"uri": urllib.parse.quote("tëxture 1.png")}]
    g.doc["textures"] = [{"source": 0}]
    mat = g.material(name="Tex", pbrMetallicRoughness={"baseColorTexture": {"index": 0}})
    g.node("Ä node", g.mesh([g.prim(pos, tri, uv=pos[:, :2], material=mat)]))
    path = g.gltf(folder / "módel ü.gltf", bin_name="dáta ü 1.bin")
    info, arr, out = read(path, tmp_path)
    m = info["materials"][0]
    assert "base_texture" in m and open(os.path.join(out, m["base_texture"]), "rb").read() == png
    nd = by_name(info, "Ä node")
    assert f"u{nd['mesh']}" in arr


def test_missing_bin_says_which_file(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("D", g.mesh([g.prim(pos, tri)]))
    path = g.gltf(tmp_path / "m.gltf", bin_name="gone data.bin")
    os.remove(tmp_path / "gone data.bin")
    with pytest.raises(mesh_reader.MeshError, match="gone data.bin"):
        read(path, tmp_path)


def test_missing_image_is_a_note_not_an_error(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.doc["images"] = [{"uri": "nowhere.png"}]
    g.doc["textures"] = [{"source": 0}]
    mat = g.material(name="Tex", pbrMetallicRoughness={"baseColorTexture": {"index": 0},
                                                       "baseColorFactor": [0.5, 0.5, 0.5, 1]})
    g.node("N", g.mesh([g.prim(pos, tri, uv=pos[:, :2], material=mat)]))
    info, _, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    assert "base_texture" not in info["materials"][0]
    assert any("nowhere" in n and "missing" in n for n in info["notes"])


def test_a_licence_file_next_to_the_model_gives_the_credit(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("Q", g.mesh([g.prim(pos, tri)]))
    (tmp_path / "m").mkdir()
    p = g.glb(tmp_path / "m" / "m.glb")
    (tmp_path / "m" / "license.txt").write_text(
        "Model Information:\n* title: Tug\n\nThis work is based on \"Tug\" by Someone (https://example.org) "
        "licensed under CC-BY-4.0\n", encoding="utf-8")
    info, _, _ = read(p, tmp_path)
    assert "licensed under CC-BY-4.0" in info["credit"]


# FINDING 12 of the independent tester: fixed (task 0117)
def test_an_unrelated_readme_is_not_the_credit(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("Q", g.mesh([g.prim(pos, tri)]))
    (tmp_path / "m").mkdir()
    p = g.glb(tmp_path / "m" / "m.glb")
    (tmp_path / "m" / "README.md").write_text("# Shopping list\n\n- milk\n- bread\n", encoding="utf-8")
    info, _, _ = read(p, tmp_path)
    assert "Shopping" not in info["credit"]


def test_spec_gloss_material_takes_the_diffuse_colour(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.doc["extensionsUsed"] = ["KHR_materials_pbrSpecularGlossiness"]
    mat = g.material(name="Old", extensions={"KHR_materials_pbrSpecularGlossiness": {
        "diffuseFactor": [0.2, 0.4, 0.6, 1.0], "glossinessFactor": 0.25}})
    g.node("N", g.mesh([g.prim(pos, tri, material=mat)]))
    info, _, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    m = info["materials"][0]
    assert np.allclose(m["color"], [mesh_reader._srgb(c) for c in (0.2, 0.4, 0.6)], atol=1e-4)
    assert m["roughness"] == pytest.approx(0.75)
    assert by_name(info, "N")["material"] == "Old"


def test_base_colour_texture_on_texcoord_1(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.doc["images"] = [{"uri": "data:image/png;base64," + base64.b64encode(maker.checker(8, 2)).decode()}]
    g.doc["textures"] = [{"source": 0}]
    mat = g.material(name="T1", pbrMetallicRoughness={"baseColorTexture": {"index": 0, "texCoord": 1}})
    uv0 = np.zeros((4, 2), np.float32)
    uv1 = np.array([[0, 0], [0.5, 0], [0.5, 0.25], [0, 0.25]], np.float32)
    p = g.prim(pos, tri, uv=uv0, material=mat, TEXCOORD_1=g.acc(uv1))
    g.node("N", g.mesh([p]))
    info, arr, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    u = arr[f"u{by_name(info, 'N')['mesh']}"]
    assert sorted({float(x) for x in np.round(u[:, 0], 4)}) == [0, 0.5]
    assert sorted({float(x) for x in np.round(u[:, 1], 4)}) == [0.75, 1.0]   # Blender's v = 1 - glTF's v


# FINDING 1 of the independent tester: fixed (task 0117)
def test_draco_without_a_converter_says_it_is_compressed(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.doc["extensionsUsed"] = g.doc["extensionsRequired"] = ["KHR_draco_mesh_compression"]
    g.node("N", g.mesh([g.prim(pos, tri)]))
    with pytest.raises(mesh_reader.MeshError) as e:
        read(g.glb(tmp_path / "m.glb"), tmp_path)
    msg = str(e.value)
    assert "Draco" in msg or "compress" in msg, msg


def _glb_bytes(tmp_path):
    g = G()
    p, tr = box()
    g.node("B", g.mesh([g.prim(p, tr)]))
    return open(g.glb(tmp_path / "full.glb"), "rb").read()


def test_glb_cut_in_its_binary_part_says_cut_off(tmp_path):
    data = _glb_bytes(tmp_path)
    p = tmp_path / "cut.glb"
    p.write_bytes(data[:-40])
    with pytest.raises(mesh_reader.MeshError, match="cut off"):
        read(p, tmp_path)


def _broken(kind):
    """A small good file with one thing broken (as found in the wild or by a cut-off download)."""
    def f(g):
        if kind == "bufferView index":
            g.doc["accessors"][0]["bufferView"] = 99
        elif kind == "buffer index":
            g.doc["bufferViews"][0]["buffer"] = 5
        elif kind == "asset not an object":
            g.doc["asset"] = "2.0"
        elif kind == "scene nodes null":
            g.doc["scenes"][0]["nodes"] = None
        elif kind == "matrix of 3 numbers":
            g.doc["nodes"][0]["matrix"] = [1, 0, 0]
        elif kind == "POSITION is VEC2":
            g.doc["accessors"][0]["type"] = "VEC2"
        elif kind == "sparse past its buffer":
            g.doc["accessors"][0]["sparse"] = {"count": 1000000, "indices": {"bufferView": 0, "componentType": U32},
                                               "values": {"bufferView": 0}}
        elif kind == "sparse index past the corners":
            g.doc["accessors"][0]["sparse"] = {
                "count": 1,
                "indices": {"bufferView": g.view(np.array([50], np.uint32).tobytes()), "componentType": U32},
                "values": {"bufferView": g.view(np.zeros(3, np.float32).tobytes())}}
        elif kind == "primitives null":
            g.doc["meshes"][0]["primitives"] = None
        elif kind == "mode as text":
            g.doc["meshes"][0]["primitives"][0]["mode"] = "TRIANGLES"
        elif kind == "metallicFactor as text":
            g.doc["materials"] = [{"pbrMetallicRoughness": {"metallicFactor": "x"}}]
            g.doc["meshes"][0]["primitives"][0]["material"] = 0
    return f


# FINDING 2 of the independent tester: fixed (task 0117)
@pytest.mark.parametrize("kind", ["GLB cut inside its JSON", "bufferView index", "buffer index", "asset not an object",
                                  "scene nodes null", "matrix of 3 numbers", "POSITION is VEC2",
                                  "sparse past its buffer", "sparse index past the corners", "primitives null",
                                  "mode as text", "metallicFactor as text"])
def test_broken_files_say_why(tmp_path, kind):
    if kind == "GLB cut inside its JSON":
        data = _glb_bytes(tmp_path)
        p = tmp_path / "cut.glb"
        p.write_bytes(data[:60])
    else:
        g = G()
        pos, tri = tri_quad()
        g.node("Q", g.mesh([g.prim(pos, tri)]))
        _broken(kind)(g)
        p = g.glb(tmp_path / "b.glb")
    with pytest.raises(mesh_reader.MeshError):
        read(p, tmp_path)


def test_huge_count_in_an_accessor_with_a_buffer_view_is_refused_fast(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("H", g.mesh([g.prim(pos, tri)]))
    g.doc["accessors"][0]["count"] = 4_000_000_000
    t0 = time.time()
    with pytest.raises(mesh_reader.MeshError, match="cut off|past the end"):
        read(g.glb(tmp_path / "m.glb"), tmp_path)
    assert time.time() - t0 < 5


# FINDING 3 of the independent tester: fixed (task 0117)
def test_huge_count_in_an_accessor_without_a_buffer_view_is_refused(tmp_path):
    g = G()
    pos, tri = tri_quad()
    g.node("H", g.mesh([g.prim(pos, tri)]))
    acc = g.doc["accessors"][0]
    del acc["bufferView"]
    acc["count"] = 10 ** 15          # 12 PB: past any address space, so np.zeros fails at once (never fills RAM)
    with pytest.raises(mesh_reader.MeshError):
        read(g.glb(tmp_path / "m.glb"), tmp_path)


def test_index_past_the_corners_says_broken(tmp_path):
    g = G()
    pos, _ = tri_quad()
    g.node("B", g.mesh([g.prim(pos, [0, 1, 9])]))
    with pytest.raises(mesh_reader.MeshError, match="broken"):
        read(g.glb(tmp_path / "m.glb"), tmp_path)


# =====================================================================================================================
# names and uids
# =====================================================================================================================

def test_names_with_control_characters_emoji_and_length(tmp_path):
    g = G()
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    g.node("Tab\there\nnew\x00line\x7f", m)
    g.node("Kran 🚢 Öl", m)
    g.node("L" * 5000, m)
    g.node("", m)
    info, _, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    names = [n["name"] for n in info["nodes"]]
    assert all(all(ch >= " " and ch != "\x7f" for ch in n) for n in names)
    assert "Kran 🚢 Öl" in names
    assert max(len(n) for n in names) <= 120
    assert all(names)
    json.dumps(info)                                       # tree.json stays writable


def test_duplicate_sibling_names_get_unique_uids(tmp_path):
    g = G()
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    par = g.node("Frame")
    for _ in range(3):
        g.node("Bolt", m, parent=par)
    g.node("Bolt ", m, parent=par)                        # the same after trimming
    g.node("Bolt\x01", m, parent=par)                     # the same after the control character is dropped
    info, _, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    uids = [n["uid"] for n in info["nodes"]]
    assert len(set(uids)) == len(uids) == 6


# FINDING 4 of the independent tester: fixed (task 0117)
def test_names_with_slashes_do_not_make_uids_collide(tmp_path):
    g = G()
    pos, tri = tri_quad()
    m = g.mesh([g.prim(pos, tri)])
    a = g.node("A")
    g.node("B#1/C", m, parent=a)
    b = g.node("B", parent=a)
    g.node("C", m, parent=b, translation=[0, 0, 3])
    info, _, _ = read(g.glb(tmp_path / "m.glb"), tmp_path)
    uids = [n["uid"] for n in info["nodes"]]
    assert len(set(uids)) == len(uids), uids


# =====================================================================================================================
# OBJ / MTL
# =====================================================================================================================

def write(path, text, encoding="utf-8", bom=False, crlf=False):
    if crlf:
        text = text.replace("\n", "\r\n")
    data = text.encode(encoding)
    if bom:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as fh:
        fh.write(data)
    return str(path)


CUBE_V = "".join(f"v {x} {y} {z}\n" for x, y, z in box((0, 0, 0), (2, 2, 2))[0])
CUBE_QUADS = "f 1 4 3 2\nf 5 6 7 8\nf 1 2 6 5\nf 2 3 7 6\nf 3 4 8 7\nf 4 1 5 8\n"


def test_obj_quads_ngons_slashes_negative_indices(tmp_path):
    text = ("o Cube\n" + CUBE_V +
            "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nvn 0 0 -1\n"
            "f 1/1 4/2 3/3 2/4\n"                              # v/vt
            "f 5//1 6//1 7//1 8//1\n"                          # v//vn
            "f -7/-4/-1 -6/-3/-1 -2/-2/-1 -3/-1/-1\n"           # negative indices: 2 3 7 6 ... counted back from v 8
            "f 1 2 6 5\nf 3 4 8 7\nf 4 1 5 8\n"
            "o Hex\n"
            + "".join(f"v {5 + math.cos(a):.6f} {math.sin(a):.6f} 0\n" for a in np.radians(np.arange(6) * 60.0))
            + "f -6 -5 -4 -3 -2 -1\n")
    info, arr, _ = read(write(tmp_path / "q.obj", text), tmp_path, units="m", up="z")
    cube = by_name(info, "Cube")
    t = arr[f"t{cube['mesh']}"]
    assert len(t) == 12
    w = np.round(world_points(info, arr, cube), 6)[t]                     # closed: every edge on two triangles
    edges = np.sort(np.stack((w, np.roll(w, -1, axis=1)), axis=2).reshape(-1, 6).reshape(-1, 2, 3), axis=1)
    _u, cnt = np.unique(edges.reshape(-1, 6), axis=0, return_counts=True)
    assert (cnt == 2).all()
    hexa = by_name(info, "Hex")
    t = arr[f"t{hexa['mesh']}"]
    assert len(t) == 4
    w = world_points(info, arr, hexa)
    assert w[:, 0].min() == pytest.approx(4.0, abs=1e-6)


def test_obj_out_of_range_indices_are_dropped(tmp_path):
    text = "v 0 0 0\nv 1 0 0\nv 1 1 0\nf 1 2 3\nf 1 2 99\nf 0 1 2\n"
    info, arr, _ = read(write(tmp_path / "r.obj", text), tmp_path, units="m")
    assert len(arr[f"t{parts(info)[0]['mesh']}"]) == 1


def test_obj_faces_before_any_object_and_groups_only(tmp_path):
    text = ("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\n"
            "f 1 2 3\n"
            "g Left\nf 1 3 4\n"
            "g Right\nf 2 3 4\n")
    info, _, _ = read(write(tmp_path / "g.obj", text), tmp_path, units="m", split="off")
    assert sorted(n["name"] for n in parts(info)) == ["Left", "Mesh", "Right"]


def test_obj_usemtl_back_and_forth_in_one_object(tmp_path):
    write(tmp_path / "m.mtl", "newmtl Red\nKd 1 0 0\nnewmtl Blue\nKd 0 0 1\n")
    text = ("mtllib m.mtl\no Plate\n" + CUBE_V +
            "usemtl Red\nf 1 4 3 2\nusemtl Blue\nf 5 6 7 8\nusemtl Red\nf 1 2 6 5\nusemtl Blue\nf 2 3 7 6\n")
    info, arr, _ = read(write(tmp_path / "u.obj", text), tmp_path, units="m", split="off")
    plate = by_name(info, "Plate")
    kids = [n for n in info["nodes"] if n["parent"] == info["nodes"].index(plate)]
    assert sorted(k["name"] for k in kids) == ["Blue", "Red"]
    assert all(len(arr[f"t{k['mesh']}"]) == 4 for k in kids)


def test_obj_missing_mtl_still_reads(tmp_path):
    text = "mtllib nope.mtl\nusemtl Steel\n" + CUBE_V + CUBE_QUADS
    info, _, _ = read(write(tmp_path / "n.obj", text), tmp_path, units="m")
    assert any("nope.mtl" in n for n in info["notes"])
    assert len(parts(info)) == 1


def test_obj_map_options_and_texture_names_with_spaces(tmp_path):
    png = maker.checker(8, 2)
    (tmp_path / "my tex 1.png").write_bytes(png)
    (tmp_path / "bump map.png").write_bytes(png)
    write(tmp_path / "t.mtl", "newmtl A\nKd 1 1 1\nmap_Kd -s 1 1 1 -o 0 0 0 my tex 1.png\n"
                              "map_Bump -bm 0.5 -clamp on bump map.png\n")
    text = "mtllib t.mtl\nvt 0 0\nvt 1 0\nvt 1 1\nusemtl A\nv 0 0 0\nv 1 0 0\nv 1 1 0\nf 1/1 2/2 3/3\n"
    info, _, out = read(write(tmp_path / "t.obj", text), tmp_path, units="m")
    m = info["materials"][0]
    assert open(os.path.join(out, m["base_texture"]), "rb").read() == png
    assert "normal_texture" in m and m.get("normal_is_bump") is True


# FINDING 13 of the independent tester: fixed (task 0117)
def test_obj_texture_with_the_authors_absolute_path(tmp_path):
    png = maker.checker(8, 2)
    (tmp_path / "tile.png").write_bytes(png)
    write(tmp_path / "a.mtl", "newmtl A\nKd 1 1 1\nmap_Kd C:\\Users\\someone\\Desktop\\tile.png\n"
                              "newmtl B\nKd 1 1 1\nmap_Kd /home/someone/models/tile.png\n")
    text = ("mtllib a.mtl\nvt 0 0\nvt 1 0\nvt 1 1\nv 0 0 0\nv 1 0 0\nv 1 1 0\no A\nusemtl A\nf 1/1 2/2 3/3\n"
            "o B\nusemtl B\nf 1/1 3/3 2/2\n")
    info, _, out = read(write(tmp_path / "a.obj", text), tmp_path, units="m")
    for m in info["materials"]:
        assert "base_texture" in m, (m, info["notes"])


def test_obj_bom_crlf_continuation_and_vertex_colours(tmp_path):
    text = ("# made up\no Tri\nv 0 0 0 1 0 0\nv 1 0 0 0 1 0\nv 1 1 \\\n 0 0 0 1\nf 1 2 \\\n3\n")
    info, arr, _ = read(write(tmp_path / "b.obj", text, bom=True, crlf=True), tmp_path, units="m", up="z")
    nd = by_name(info, "Tri")
    assert same_point_set(world_points(info, arr, nd), [[0, 0, 0], [1, 0, 0], [1, 1, 0]])


# FINDING 5 of the independent tester: fixed (task 0117)
def test_obj_tab_separated_lines(tmp_path):
    text = "o T\nv\t0 0 0\nv\t1 0 0\nv\t1 1 0\nf\t1 2 3\n"
    info, arr, _ = read(write(tmp_path / "tab.obj", text), tmp_path, units="m", up="z")
    assert len(parts(info)) == 1


@pytest.mark.parametrize("side, unit", [(499.0, "m"), (500.0, "mm")])
def test_obj_units_guess_at_the_edge(tmp_path, side, unit):
    text = "".join(f"v {x} {y} {z}\n" for x, y, z in box((0, 0, 0), (side, 1, 1))[0]) + CUBE_QUADS
    info, arr, _ = read(write(tmp_path / "u.obj", text), tmp_path)
    assert info["options"]["units"] == unit
    w = world_points(info, arr, parts(info)[0])
    assert np.ptp(w[:, 0]) == pytest.approx(side * mesh_reader.UNITS[unit])


def test_obj_up_z_and_y(tmp_path):
    text = "v 0 0 0\nv 1 0 0\nv 0 2 0\nv 0 0 3\nf 1 2 3\nf 1 3 4\n"
    p = write(tmp_path / "a.obj", text)
    info, arr, _ = read(p, tmp_path, "y", units="m")
    w = world_points(info, arr, parts(info)[0])
    assert np.allclose(w.max(0), [1, 0, 2]) and np.allclose(w.min(0), [0, -3, 0])   # Y up: (x, y, z) -> (x, -z, y)
    info, arr, _ = read(p, tmp_path, "z", units="m", up="z")
    w = world_points(info, arr, parts(info)[0])
    assert np.allclose(np.ptp(w, axis=0), [1, 2, 3])


def _polygon_area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


# FINDING 6 of the independent tester: fixed (task 0117)
def test_obj_concave_ngon_keeps_its_shape(tmp_path):
    # an L: the fan from the first corner (2, 0) crosses the notch
    L = np.array([[2, 0], [2, 1], [1, 1], [1, 2], [0, 2], [0, 0]], float)
    text = "".join(f"v {x} {y} 0\n" for x, y in L) + "f 1 2 3 4 5 6\n"
    info, arr, _ = read(write(tmp_path / "l.obj", text), tmp_path, units="m", up="z")
    nd = parts(info)[0]
    w = world_points(info, arr, nd)[arr[f"t{nd['mesh']}"]]
    area = 0.5 * np.linalg.norm(np.cross(w[:, 1] - w[:, 0], w[:, 2] - w[:, 0]), axis=1)
    assert area.sum() == pytest.approx(_polygon_area(L))            # 3 m²; the fan's triangles overlap / stick out
    n = _geom_normals(w)
    assert np.allclose(n, n[0], atol=1e-6)                           # no triangle turned over


# FINDING 7 of the independent tester: fixed (task 0117)
def test_obj_two_objects_with_one_name_stay_two_parts(tmp_path):
    text = ("o Bolt\n" + CUBE_V + CUBE_QUADS +
            "o Bolt\n" + "".join(f"v {x + 5} {y} {z}\n" for x, y, z in box((0, 0, 0), (2, 2, 2))[0]) +
            "f -8 -5 -6 -7\nf -4 -3 -2 -1\nf -8 -7 -3 -4\nf -7 -6 -2 -3\nf -6 -5 -1 -2\nf -5 -8 -4 -1\n")
    info, _, _ = read(write(tmp_path / "d.obj", text), tmp_path, units="m", split="off")
    assert len(parts(info)) == 2


# =====================================================================================================================
# split by loose parts
# =====================================================================================================================

def test_pieces_touching_at_one_corner_are_one_piece():
    a, ta = box((0, 0, 0), (1, 1, 1))
    b, tb = box((1, 1, 1), (2, 2, 2))                    # shares the corner (1, 1, 1) only
    pos = np.vstack((a, b))
    lab = mesh_faces.loose_parts(pos, np.vstack((ta, tb + 8)))
    assert lab.max() == 0                                # the design: a shared corner joins (reported, not a fault)


def test_two_shells_sharing_positions_not_indices_are_one_piece():
    """Split normals: every triangle its own corners; the pieces are still found by position."""
    p, t = box()
    q = p[t].reshape(-1, 3)
    lab = mesh_faces.loose_parts(q, np.arange(len(q)).reshape(-1, 3))
    assert lab.max() == 0
    p2 = np.vstack((q, q + [3, 0, 0]))
    lab = mesh_faces.loose_parts(p2, np.arange(len(p2)).reshape(-1, 3))
    assert lab.max() == 1 and (lab[:12] == 0).all() and (lab[12:] == 1).all()


def _boxes_glb(tmp_path, sizes, name="many.glb", gap=3.0):
    g = G()
    ps, ts = [], []
    off = 0
    for k, s in enumerate(sizes):
        p, t = box((k * gap, 0, 0), (k * gap + s, s, s))
        ps.append(p)
        ts.append(t + off)
        off += len(p)
    g.node("Lump", g.mesh([g.prim(np.vstack(ps), np.vstack(ts))]))
    return g.glb(tmp_path / name)


def test_more_than_max_pieces_keep_the_small_ones_together(tmp_path, monkeypatch):
    monkeypatch.setattr(mesh_reader, "MAX_PIECES", 3)
    info, _, _ = read(_boxes_glb(tmp_path, [1.0, 0.9, 0.8, 0.7, 0.6]), tmp_path)
    assert [n["name"] for n in parts(info)] == ["Lump 1", "Lump 2", "Lump small pieces"]


# FINDING 8 of the independent tester: fixed (task 0117)
def test_exactly_max_pieces_are_all_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(mesh_reader, "MAX_PIECES", 3)
    info, _, _ = read(_boxes_glb(tmp_path, [1.0, 0.9, 0.8]), tmp_path)
    assert [n["name"] for n in parts(info)] == ["Lump 1", "Lump 2", "Lump 3"]
    assert not any("small pieces" in n for n in info["notes"])


# FINDING 9 of the independent tester: fixed (task 0117)
def test_piece_names_follow_the_piece_not_its_rank(tmp_path):
    a, _, _ = read(_boxes_glb(tmp_path, [1.0, 0.8], "a.glb"), tmp_path, "a")
    b, ab, _ = read(_boxes_glb(tmp_path, [1.0, 1.2], "b.glb"), tmp_path, "b")
    # the first box did not change: it keeps its name
    name_a = next(n["name"] for n in parts(a) if n["mesh"] >= 0 and a["meshes"][n["mesh"]]["bbox"][0][0] < 0.5)
    name_b = next(n["name"] for n in parts(b) if b["meshes"][n["mesh"]]["bbox"][0][0] < 0.5)
    assert name_a == name_b


# =====================================================================================================================
# the face split
# =====================================================================================================================

def _rot(axis):
    """A rotation taking Z to ``axis``."""
    z = np.array([0.0, 0.0, 1.0])
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    v = np.cross(z, a)
    s, c = np.linalg.norm(v), float(np.dot(z, a))
    if s < 1e-12:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]]) / s
    ang = math.atan2(s, c)
    return np.eye(3) + math.sin(ang) * k + (1 - math.cos(ang)) * k @ k


def cylinder(r, h, sides, axis=(0, 0, 1), centre=(0, 0, 0), caps=True, phase=0.0):
    s = maker.Shape()
    if caps:
        s.cylinder(r, 0.0, h, sides)
    else:
        s.wall(r, 0.0, h, sides)
    p = np.array(s.p, float)
    if phase:
        c, si = math.cos(phase), math.sin(phase)
        p = p @ np.array([[c, -si, 0], [si, c, 0], [0, 0, 1]]).T
    R = _rot(axis)
    return p @ R.T + np.asarray(centre, float), np.array(s.t, np.int64)


def round_faces(fs):
    out = []
    for k in range(0, len(fs.axis_faces), 3):
        s, n, a = fs.axis_faces[k: k + 3]
        out.append((s, n, fs.axes[a]))
    return out


def check_axis(fs, r, axis, centre, ang_deg=0.5, rel=0.005):
    rf = round_faces(fs)
    assert rf, "no round face"
    axis = np.asarray(axis, float) / np.linalg.norm(axis)
    best = None
    for _s, _n, ax in rf:
        d = np.asarray(ax[3:6])
        o = np.asarray(ax[:3])
        ang = math.degrees(math.acos(min(1.0, abs(float(np.dot(d, axis))))))
        off = np.asarray(centre, float) - o
        dist = np.linalg.norm(off - d * np.dot(off, d))
        err = abs(ax[6] - r) / r
        if best is None or (ang, err) < best[:2]:
            best = (ang, err, dist)
    ang, err, dist = best
    assert ang < ang_deg and err < rel and dist < 0.005 * r, best


def check_faces(fs, m):
    assert sorted(fs.order.tolist()) == list(range(m))                  # a permutation
    assert fs.starts[0] == 0 and fs.starts[-1] == m and (np.diff(fs.starts) > 0).all()
    assert len(fs.kinds) == len(fs.starts) - 1
    starts = list(fs.starts)
    for s, n, a in round_faces(fs):
        f = starts.index(s)
        assert fs.starts[f + 1] - s == n and fs.kinds[f] == mesh_faces.KIND_CYLINDER
        assert 0 <= fs.axes.index(a) < len(fs.axes)
    assert len(fs.axes) <= mesh_faces.MAX_AXES


@pytest.mark.parametrize("r, h, sides, axis, centre", [
    (0.05, 0.2, 32, (0, 0, 1), (0, 0, 0)),
    (0.0005, 0.002, 24, (1, 2, 3), (0.1, -0.2, 0.3)),               # a 1 mm pin
    (50.0, 20.0, 64, (0, 1, 0), (100.0, 0, -30.0)),                 # 50 m
    (0.2, 1.0, 12, (1, 1, 0), (2.0, 3.0, 4.0)),                     # 12 sides
    (0.3, 0.5, 256, (0.3, -0.2, 1.0), (0, 0, 0)),                   # 256 sides
    (0.05, 0.2, 32, (0, 0, 1), (1e5, 2e5, 0)),                      # far from the origin
    (0.02, 0.1, 32, (0, 1, 0), (120.0, 35.0, 8.0)),                 # 120 m out, as float32 (a ship's pin)
])
def test_facetted_cylinders_give_their_axis(r, h, sides, axis, centre):
    p, t = cylinder(r, h, sides, axis, centre)
    if centre[0] == 120.0:
        p = p.astype(np.float32).astype(np.float64)
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    check_axis(fs, r, axis, centre)


@pytest.mark.xfail(strict=True, reason="FINDING 14: a facetted cylinder stored as float32 a few hundred metres from "
                                       "the origin (a vessel's corners in world coordinates) breaks into 2-6 round "
                                       "faces "
                                       "and its radius is up to 0.8 % off - 10x the float32 rounding")
@pytest.mark.parametrize("off, r", [(300.0, 0.05), (200.0, 0.05), (1000.0, 0.1)])
def test_float32_cylinder_far_out_is_one_round_face(off, r):
    p, t = cylinder(r, 4 * r, 32, axis=(0, 1, 0), centre=(off, 0.3 * off, 3.0))
    p = p.astype(np.float32).astype(np.float64)                 # what a glTF file holds
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    assert len(round_faces(fs)) == 1
    check_axis(fs, r, (0, 1, 0), (off, 0.3 * off, 3.0))


def test_two_coaxial_cylinders_share_one_axis():
    a, ta = cylinder(0.1, 0.3, 32)
    b, tb = cylinder(0.05, 0.3, 32, centre=(0, 0, 0.3))
    fs = mesh_faces.split(np.vstack((a, b)), np.vstack((ta, tb + len(a))))
    check_faces(fs, len(ta) + len(tb))
    assert len(round_faces(fs)) == 2 and len(fs.axes) == 1
    assert fs.axes[0][6] == pytest.approx(0.1, rel=0.005)


def test_cylinder_with_a_seam_and_split_normals():
    p, t = cylinder(0.1, 0.4, 40, axis=(1, 0, 0))          # maker's wall has a seam (corners doubled at angle 0)
    q = p[t].reshape(-1, 3)                                 # and here every triangle its own corners
    fs = mesh_faces.split(q, np.arange(len(q)).reshape(-1, 3))
    check_faces(fs, len(t))
    check_axis(fs, 0.1, (1, 0, 0), (0, 0, 0))
    assert sum(1 for k in fs.kinds if k == mesh_faces.KIND_CYLINDER) == 1


def _sliver_cylinder(r, h, n, tjunctions=False):
    """A facetted cylinder whose every facet is two fans of 8 slivers (as some exporters cut long facets). With
    ``tjunctions`` each facet has 9 corners on one long edge and 2 on the other (its neighbour's edge has 9)."""
    pts, tris = [], []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        c0 = np.array([r * math.cos(a0), r * math.sin(a0)])
        c1 = np.array([r * math.cos(a1), r * math.sin(a1)])
        k = len(pts)
        zs = np.linspace(0, h, 9)
        pts += [[*c0, z] for z in zs]                       # k .. k+8
        if tjunctions:
            pts += [[*c1, 0.0], [*c1, h]]                   # k+9, k+10
            tris += [(k + j, k + 9, k + j + 1) for j in range(8)] + [(k + 8, k + 9, k + 10)]
        else:
            pts += [[*c1, z] for z in zs]                   # k+9 .. k+17
            tris += [(k + j, k + 9, k + j + 1) for j in range(8)]
            tris += [(k + 8, k + 9 + j + 1, k + 9 + j) for j in range(8)]
    p = np.array(pts)
    t = np.array(tris)
    w = p[t]
    nn = np.cross(w[:, 1] - w[:, 0], w[:, 2] - w[:, 0])
    out = np.einsum("ij,ij->i", nn, np.c_[w.mean(1)[:, :2], np.zeros(len(w))])
    t[out < 0] = t[out < 0][:, ::-1]                        # every sliver wound outwards
    return p, t


def test_cylinder_with_thin_triangles_on_its_facets():
    p, t = _sliver_cylinder(0.1, 1.0, 32)
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    check_axis(fs, 0.1, (0, 0, 1), (0, 0, 0))


@pytest.mark.xfail(strict=True, reason="FINDING 11: a facetted cylinder whose facets meet in T-junctions (9 corners on "
                                       "one long edge, 2 on its neighbour's: a non-conforming export) has no round "
                                       "face")
def test_cylinder_with_t_junctions_on_its_facets():
    p, t = _sliver_cylinder(0.1, 1.0, 32, tjunctions=True)
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    check_axis(fs, 0.1, (0, 0, 1), (0, 0, 0))


def test_hexagonal_bar_is_flat_faces():
    """What a 6-sided bar gives (reported): six flat sides and two ends, no round face (a hexagon is not taken for
    a cylinder)."""
    p, t = cylinder(0.02, 0.2, 6)
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    assert not round_faces(fs)
    assert len(fs.starts) - 1 == 8


def test_cone_and_sphere_do_not_crash():
    # a cone: apex on top
    n = 32
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    p = np.vstack((np.stack((np.cos(a), np.sin(a), 0 * a), 1), [[0, 0, 1.5], [0, 0, 0]]))
    t = np.array([(i, (i + 1) % n, n) for i in range(n)] + [((i + 1) % n, i, n + 1) for i in range(n)])
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))
    # a UV sphere
    u, v = np.meshgrid(np.linspace(0, 2 * math.pi, 25)[:-1], np.linspace(0.1, math.pi - 0.1, 12))
    sp = np.stack((np.sin(v) * np.cos(u), np.sin(v) * np.sin(u), np.cos(v)), -1).reshape(-1, 3)
    tt = []
    for i in range(11):
        for j in range(24):
            a0, a1 = i * 24 + j, i * 24 + (j + 1) % 24
            tt += [(a0, a1, a1 + 24), (a0, a1 + 24, a0 + 24)]
    fs = mesh_faces.split(sp, np.array(tt))
    check_faces(fs, len(tt))


def test_box_gives_six_flat_faces():
    p, t = box((10, 10, 10), (10.3, 10.2, 10.1))
    fs = mesh_faces.split(p, t)
    check_faces(fs, 12)
    assert len(fs.starts) - 1 == 6 and (fs.kinds == mesh_faces.KIND_FLAT).all()


@pytest.mark.parametrize("kind", ["line", "point", "zero_area"])
def test_degenerate_input_does_not_crash(kind):
    if kind == "line":
        p = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], float)
        t = np.array([[0, 1, 2], [1, 2, 3], [0, 2, 3]])
    elif kind == "point":
        p = np.zeros((3, 3))
        t = np.array([[0, 1, 2], [0, 0, 0]])
    else:
        p, t = box()
        t = np.vstack((t, [[0, 0, 1], [2, 2, 2], [0, 1, 0]]))
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))


def test_nan_corners_do_not_crash_the_split():
    p, t = box()
    p[3] = np.nan
    fs = mesh_faces.split(p, t)
    check_faces(fs, len(t))


def test_split_is_deterministic():
    a, ta = cylinder(0.1, 0.3, 48, axis=(1, 1, 1), centre=(1, 2, 3))
    b, tb = box((-1, -1, -1), (0, 0, 0))
    p, t = np.vstack((a, b)), np.vstack((ta, tb + len(a)))
    f1, f2 = mesh_faces.split(p, t), mesh_faces.split(p.copy(), t.copy())
    assert np.array_equal(f1.order, f2.order) and np.array_equal(f1.starts, f2.starts)
    assert f1.axes == f2.axes and f1.axis_faces == f2.axis_faces and np.array_equal(f1.kinds, f2.kinds)


def test_reader_axes_are_in_the_parts_own_frame_for_a_mirrored_node(tmp_path):
    """A facetted shaft placed by a mirroring node: its axis in the cache is in the part's own (mesh) frame, and the
    world axis follows the node."""
    g = G()
    p, t = cylinder(0.05, 0.4, 32, axis=(0, 1, 0), centre=(0.3, 0, 0))   # glTF Y = up
    g.node("Shaft", g.mesh([g.prim(p.astype(np.float32), t.astype(np.uint32))]),
           scale=[-1, 1, 1], translation=[2, 0, 0])
    info, arr, _ = read(g.glb(tmp_path / "s.glb"), tmp_path)
    nd = by_name(info, "Shaft")
    meta = info["meshes"][nd["mesh"]]
    assert meta["axes"], "no axis"
    ax = np.array(meta["axes"][0])
    assert ax[6] == pytest.approx(0.05, rel=0.005)
    m = world(info, nd)
    o = m[:3, :3] @ ax[:3] + m[:3, 3]
    d = m[:3, :3] @ ax[3:6]
    d = d / np.linalg.norm(d)
    assert abs(abs(d[2]) - 1) < 1e-4                                          # app Z up
    assert np.allclose(o[:2], [2 - 0.3, 0], atol=1e-4)


# =====================================================================================================================
# the job runner
# =====================================================================================================================

def run_job(job, timeout=120):
    job.start()
    t0 = time.time()
    while not job.poll():
        time.sleep(0.05)
        assert time.time() - t0 < timeout
    return job


def test_cancel_while_running_removes_its_folder(tmp_path):
    src = tmp_path / "big.glb"
    g = G()
    p, t = cylinder(0.1, 1.0, 64)
    m = g.mesh([g.prim(p.astype(np.float32), t.astype(np.uint32))])
    for k in range(40):
        g.node(f"S{k}", m, translation=[k, 0, 0])
    g.glb(src)
    root = str(tmp_path / "cache")
    job = runner.ImportJob(str(src), "mesh", root)
    job.start()
    t0 = time.time()
    while not os.path.isdir(job.tmp_dir) and time.time() - t0 < 20:
        time.sleep(0.01)
    job.cancel()
    assert job.done and job.error == "Cancelled"
    assert not os.path.exists(job.tmp_dir) and not os.path.exists(job.cache_dir)
    assert job.proc.poll() is not None


def test_two_imports_with_different_options_at_once_both_finish(tmp_path):
    root = str(tmp_path / "cache")
    shutil.copy(os.path.join(DATA, "test_mesh_parts.obj"), tmp_path / "p.obj")
    shutil.copy(os.path.join(DATA, "test_mesh_parts.mtl"), tmp_path / "test_mesh_parts.mtl")
    shutil.copy(os.path.join(DATA, "test_mesh_tile.png"), tmp_path / "test_mesh_tile.png")
    jobs = [runner.ImportJob(str(tmp_path / "p.obj"), "mesh", root, {"units": u}) for u in ("mm", "m")]
    for j in jobs:
        j.start()
    t0 = time.time()
    while not all(j.poll() for j in jobs):
        time.sleep(0.05)
        assert time.time() - t0 < 120
    assert all(j.error is None for j in jobs)
    assert not any(".partial" in n for n in os.listdir(root))


def test_a_changed_source_file_is_read_again(tmp_path):
    src = tmp_path / "m.glb"
    shutil.copy(CRANE, src)
    root = str(tmp_path / "cache")
    a = run_job(runner.ImportJob(str(src), "mesh", root))
    assert a.error is None
    shutil.copy(CRANE_B, src)
    os.utime(src, (time.time() + 3, time.time() + 3))
    b = runner.ImportJob(str(src), "mesh", root)
    assert not b.cached and b.cache_dir != a.cache_dir


# FINDING 10 of the independent tester: fixed (task 0117)
def test_a_same_size_change_in_the_same_second_is_read_again(tmp_path):
    src = tmp_path / "m.gltf"
    g = G()
    p, t = box()
    g.node("B", g.mesh([g.prim(p, t)]))
    g.gltf(src)
    st = os.stat(src)
    root = str(tmp_path / "cache")
    run_job(runner.ImportJob(str(src), "mesh", root))
    text = src.read_text(encoding="utf-8").replace('"name": "B"', '"name": "C"')
    src.write_text(text, encoding="utf-8")
    os.utime(src, (st.st_atime, int(st.st_mtime) + 0.5))
    assert os.path.getsize(src) == st.st_size
    assert not runner.ImportJob(str(src), "mesh", root).cached


# =====================================================================================================================
# the app (Blender as a Python module)
# =====================================================================================================================

@pytest.fixture(scope="module")
def app_on():
    bpy = pytest.importorskip("bpy")
    import addon_utils
    import fresing_render
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    fresing_render.register()
    yield bpy
    fresing_render.unregister()


def fresh_project(bpy, tmp_path):
    import addon_utils
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("cycles", default_set=True)
    sc = bpy.context.scene
    sc.fresing.out_folder = str(tmp_path)
    return sc


def test_app_two_copies_of_one_mesh_model(app_on, tmp_path):
    bpy = app_on
    from fresing_render.blender import build, mesh_import
    sc = fresh_project(bpy, tmp_path)
    for _ in range(2):
        assert bpy.ops.fresing.import_mesh(filepath=CRANE) == {"FINISHED"}
    roots = build.model_roots(sc)
    assert len(roots) == 2 and all(mesh_import.is_mesh_model(r) for r in roots)
    assert len({r.get(build.PROP_UID_SCOPE, "") for r in roots}) == 2
    uids = [o.get(build.PROP_UID) for o in sc.objects if o.get(build.PROP_UID)]
    assert len(uids) == len(set(uids))
    # each copy's parts show their own file material, and the credits name both copies
    for r in roots:
        boom = next(o for o in r.children_recursive if o.get(build.PROP_NAME) == "BOOM")
        assert boom.material_slots[0].material.name.startswith(mesh_import.MAT_PREFIX + "Yellow paint")
    assert bpy.data.texts[mesh_import.CREDITS_TEXT].as_string().count("Mesh crane (test model)") == 2


def test_app_packed_textures_outlive_the_cache(app_on, tmp_path):
    bpy = app_on
    from fresing_render.blender import build
    sc = fresh_project(bpy, tmp_path)
    src = tmp_path / "own copy.glb"
    shutil.copy(CRANE, src)
    assert bpy.ops.fresing.import_mesh(filepath=str(src)) == {"FINISHED"}
    imgs = [im for im in bpy.data.images if im.name.startswith("FR file")]
    assert imgs and all(im.packed_file is not None for im in imgs)
    for im in imgs:                                   # the cache's texture files are gone (cache cleared)
        f = bpy.path.abspath(im.filepath)
        if os.path.isfile(f):
            os.remove(f)
    path = str(tmp_path / "p.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    bpy.ops.wm.open_mainfile(filepath=path)
    sc = bpy.context.scene
    base = next(o for o in sc.objects if o.get(build.PROP_NAME) == "BASE")
    tex = [n for n in base.material_slots[0].material.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"]
    assert tex and tex[0].image.packed_file is not None and tuple(tex[0].image.size) == (64, 64)
    assert tex[0].image.pixels[0] > 0.0


def test_app_model_update_keeps_a_look_picked_by_hand_and_from_file_still_works(app_on, tmp_path):
    bpy = app_on
    from fresing_render.blender import build, mesh_import
    sc = fresh_project(bpy, tmp_path)
    src = tmp_path / "crane.glb"
    shutil.copy(CRANE, src)
    assert bpy.ops.fresing.import_mesh(filepath=str(src)) == {"FINISHED"}
    base = next(o for o in sc.objects if o.get(build.PROP_NAME) == "BASE")
    g_base = sc.fresing.groups[base[build.PROP_GROUP]]
    g_base.material = "paint_gloss"
    root = build.model_roots(sc)[0]
    shutil.copy(CRANE_B, src)
    os.utime(src, (time.time() + 5, time.time() + 5))
    assert bpy.ops.fresing.import_mesh(filepath=str(src), update_root=root.name) == {"FINISHED"}
    base = next(o for o in sc.objects if o.get(build.PROP_NAME) == "BASE")
    assert sc.fresing.groups[base[build.PROP_GROUP]].material == "paint_gloss"
    assert not base.material_slots[0].material.name.startswith(mesh_import.MAT_PREFIX)
    main = next(o for o in sc.objects if o.get(build.PROP_NAME) == "MAIN BOOM")
    g_main = sc.fresing.groups[main[build.PROP_GROUP]]
    if g_main.material != mesh_import.FROM_FILE:
        g_main.material = mesh_import.FROM_FILE
    mat = main.material_slots[0].material
    assert mat is not None and mat.name.startswith(mesh_import.MAT_PREFIX + "Yellow paint")
    hook = next(o for o in sc.objects if o.get(build.PROP_NAME) == "HOOK BLOCK")
    assert mesh_import.file_material(hook) is not None


# FINDING 15 of the independent tester: decided (task 0117) – groups decide looks for every model alike. A mesh part
# that joins a group an earlier model made takes that group's look (documented in the guide); groups made by the
# mesh import start with "From file", and "From file" picked for any group shows each part's own file material.
def test_app_mesh_model_after_a_step_model_keeps_its_file_looks(app_on, tmp_path):
    pytest.importorskip("OCP")
    bpy = app_on
    from fresing_render.blender import build, mesh_import
    sc = fresh_project(bpy, tmp_path)
    assert bpy.ops.fresing.import_step(filepath=os.path.join(DATA, "test_crane_a.step")) == {"FINISHED"}
    assert bpy.ops.fresing.import_mesh(filepath=CRANE) == {"FINISHED"}
    root = next(r for r in build.model_roots(sc) if mesh_import.is_mesh_model(r))
    pin = next(o for o in root.children_recursive if o.get(build.PROP_NAME) == "BOOM PIN")
    g = sc.fresing.groups[pin[build.PROP_GROUP]]
    assert g.material != mesh_import.FROM_FILE                  # the STEP model's group keeps its look
    g.material = mesh_import.FROM_FILE                          # picked by hand: every part shows its own material
    for ob in root.children_recursive:
        if ob.type == "MESH" and ob.get(build.PROP_GROUP) == g.name:
            assert ob.material_slots[0].material == mesh_import.file_material(ob), ob.get(build.PROP_NAME)
