"""A small picture of a made crane (task 0204) – OpenCascade's mesher and NumPy, no Blender, no Pillow.

The crane in its CAD pose, seen from the front left (as the built-in pictures), each part flat-shaded in its own colour
over a light grey ground. Every part is meshed coarsely once (parts placed many times share it), the triangles are
filled by sampling points on them into a depth buffer (``np.minimum.at``), and the PNG is written with ``zlib``. About
a second for a crawler crane of 500 parts on the web machine; the library shows it in 8 Lifting plan > Equipment.
"""

from __future__ import annotations

import math
import struct
import zlib

import numpy as np

from ..demo_model import geom as g
from ..demo_model.geom import Part

SIZE = (360, 240)
BACKGROUND = (0.86, 0.88, 0.90)
LIGHT = np.array([0.45, 0.25, 0.86])
VIEW = np.array([1.0, 0.85, 0.55])          # from the model towards the eye: front (+x) left (+y), above


def _mesh(shape, deflection: float):
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    BRepMesh_IncrementalMesh(shape, deflection, False, 0.6, False)
    tris = []
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            T = loc.Transformation()
            pts = []
            for i in range(1, tri.NbNodes() + 1):
                p = tri.Node(i).Transformed(T)
                pts.append((p.X(), p.Y(), p.Z()))
            pts = np.array(pts)
            rev = face.Orientation() == TopAbs_REVERSED
            for i in range(1, tri.NbTriangles() + 1):
                a, b, c = tri.Triangle(i).Get()
                tris.append(pts[[a - 1, c - 1, b - 1]] if rev else pts[[a - 1, b - 1, c - 1]])
        ex.Next()
    return np.array(tris, float).reshape(-1, 3, 3)


def triangles(root) -> tuple[np.ndarray, np.ndarray]:
    """(N, 3, 3) world triangles in mm and (N, 3) sRGB colours of every placed part."""
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    placed = []
    for node, _uid, W, _label, _path in g.walk(root):
        if isinstance(node, Part):
            placed.append((node, W))
    meshes: dict = {}
    for node, W in placed:
        if id(node) not in meshes:
            from OCP.Bnd import Bnd_Box
            from OCP.BRepBndLib import BRepBndLib
            b = Bnd_Box()
            BRepBndLib.Add_s(node.shape, b)
            p0, p1 = b.CornerMin(), b.CornerMax()
            x0, y0, z0, x1, y1, z1 = p0.X(), p0.Y(), p0.Z(), p1.X(), p1.Y(), p1.Z()
            d = max(x1 - x0, y1 - y0, z1 - z0)
            meshes[id(node)] = _mesh(node.shape, max(2.0, 0.08 * d))
    tris, cols = [], []
    for node, W in placed:
        t = meshes[id(node)]
        if not len(t):
            continue
        w = t @ W[:3, :3].T + W[:3, 3]
        tris.append(w)
        cols.append(np.tile(np.asarray(node.color or (0.6, 0.6, 0.6), float), (len(w), 1)))
        lo, hi = np.minimum(lo, w.reshape(-1, 3).min(0)), np.maximum(hi, w.reshape(-1, 3).max(0))
    if not tris:
        return np.zeros((0, 3, 3)), np.zeros((0, 3))
    return np.concatenate(tris), np.concatenate(cols)


def render(tris: np.ndarray, cols: np.ndarray, size=SIZE, margin: float = 0.06) -> np.ndarray:
    """(H, W, 3) uint8 sRGB: an orthographic view along ``VIEW``, flat-shaded, a depth buffer."""
    Wd, Hd = size
    img = np.empty((Hd, Wd, 3), float)
    img[:] = BACKGROUND
    if not len(tris):
        return (img * 255 + 0.5).astype(np.uint8)
    f = -VIEW / np.linalg.norm(VIEW)
    r = np.cross(f, [0.0, 0.0, 1.0])
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    P = np.stack([r, u, f])
    s = tris @ P.T                                             # (N, 3, 3): screen x, y, depth
    lo, hi = s[:, :, :2].reshape(-1, 2).min(0), s[:, :, :2].reshape(-1, 2).max(0)
    scale = min(Wd * (1 - 2 * margin) / max(hi[0] - lo[0], 1e-9), Hd * (1 - 2 * margin) / max(hi[1] - lo[1], 1e-9))
    cx, cy = (lo + hi) / 2
    px = (s[:, :, 0] - cx) * scale + Wd / 2
    py = Hd / 2 - (s[:, :, 1] - cy) * scale
    dz = s[:, :, 2]
    # shading: the triangle's normal against the light (both sides lit: the meshes are not all closed)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    ln = np.linalg.norm(n, axis=1)
    keep = ln > 1e-9
    n[keep] /= ln[keep, None]
    facing = np.sign(n @ (-f))
    facing[facing == 0] = 1.0
    n *= facing[:, None]
    L = LIGHT / np.linalg.norm(LIGHT)
    shade = 0.42 + 0.58 * np.clip(n @ L, 0.0, 1.0)
    lin = np.where(cols <= 0.04045, cols / 12.92, ((cols + 0.055) / 1.055) ** 2.4) * shade[:, None]
    colour = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, None), 1 / 2.4) - 0.055)
    # samples per triangle: a grid of m (m + 1) / 2 points, m from its size on screen
    edge = np.max(np.stack([np.hypot(px[:, i] - px[:, (i + 1) % 3], py[:, i] - py[:, (i + 1) % 3])
                            for i in range(3)]), axis=0)
    m = np.clip(np.ceil(edge * 1.5).astype(int), 1, 400)
    zbuf = np.full(Hd * Wd, np.inf)
    owner_z, owner_c = [], []
    for k in np.unique(m):
        idx = np.nonzero(m == k)[0]
        a, b = np.meshgrid(np.arange(k + 1), np.arange(k + 1), indexing="ij")
        ok = a + b <= k
        wa, wb = a[ok] / k, b[ok] / k
        wc = 1.0 - wa - wb
        for chunk in np.array_split(idx, max(1, len(idx) * len(wa) // 2_000_000 + 1)):
            X = px[chunk, 0, None] * wa + px[chunk, 1, None] * wb + px[chunk, 2, None] * wc
            Y = py[chunk, 0, None] * wa + py[chunk, 1, None] * wb + py[chunk, 2, None] * wc
            Z = dz[chunk, 0, None] * wa + dz[chunk, 1, None] * wb + dz[chunk, 2, None] * wc
            ix, iy = np.floor(X).astype(int), np.floor(Y).astype(int)
            inside = (ix >= 0) & (ix < Wd) & (iy >= 0) & (iy < Hd)
            pix = (iy * Wd + ix)[inside]
            z = Z[inside]
            tri = np.broadcast_to(chunk[:, None], X.shape)[inside]
            np.minimum.at(zbuf, pix, z)
            owner_z.append((pix, z, tri))
    flat = img.reshape(-1, 3)
    for pix, z, tri in owner_z:
        win = z <= zbuf[pix]
        flat[pix[win]] = colour[tri[win]]
    return (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)


def write_png(path: str, rgb: np.ndarray) -> None:
    """8-bit RGB PNG, no colour chunks."""
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[y].tobytes() for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def picture(root, path: str, size=SIZE) -> str:
    tris, cols = triangles(root)
    write_png(path, render(tris, cols, size))
    return path


__all__ = ["picture", "render", "triangles", "write_png", "math"]
