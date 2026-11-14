"""Write the mesh-import test models (task 0117; generic, invented, no downloads).

    python tools/make_test_mesh.py [out folder]     default tests/data; then copy the shipped ones (SHIPPED) to
                                                     fresing_render/data/ (a test checks they are the same)

Every model is built here in the app's coordinates (metres, Z up) and written the way its format has it: glTF in
metres with Y up ((x, y, z) -> (x, z, -y)), OBJ in millimetres with Y up. The files are byte for byte the same at
every run.

  test_mesh_crane.glb     a small crane, the tour's and the PC check's model:
    MESH CRANE              root node (no mesh)
      BASE                  a 2.0 x 2.0 x 0.4 m box, its base colour a checker TEXTURE ("Base steel", UVs)
      SLEWING RING          a facetted ring of 48 sides about the vertical axis through (0, 0): outer radius 0.80,
                            inner 0.60, z 0.40 .. 0.55 ("Ring grey")
      TURRET                a node (no mesh) the turret's parts hang under
        CAB                 one mesh of TWO primitives: the cab box ("Yellow paint") and its window ("Glass")
        BOOM                a 3.0 m box, tilted up 20 degrees ("Yellow paint")
        BOOM PIN            a facetted shaft of 24 sides along Y through the boom's foot (0.45, *, 1.05), r 0.06
      WHEEL FL/FR/RL/RR     four nodes sharing ONE mesh (instancing): a facetted wheel of 32 sides, axis along Y,
                            r 0.25, width 0.18 ("Black rubber"); RL and RR turned over (negative scale on Y)
    asset.copyright "Fresing test models (invented), CC BY 4.0", asset.extras title / author / license / source
  test_mesh_crane_b.glb   its next revision: HOOK BLOCK added under TURRET, BOOM renamed "MAIN BOOM", the cab
                          1 cm higher, everything else the same
  test_mesh_single.glb    ONE node with ONE mesh holding five loose pieces (a plate 1.2 x 0.8 x 0.05 m, a facetted
                          shaft r 0.04 of 16 sides standing on it, three blocks); the mesh has no normals (glTF: flat)
  test_mesh_parts.obj     an OBJ + test_mesh_parts.mtl + test_mesh_tile.png, millimetres, Y up: objects "Frame"
                          (quads), "Cover" (an ngon top, usemtl twice: "Blue" and "Tile" with a texture), "Pipe"
                          (a facetted tube of 20 sides, r 50 mm); biggest side 1,200 units (Auto guesses mm)
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHIPPED = ("test_mesh_crane.glb",)

CREDIT = {"title": "Mesh crane (test model)", "author": "Fresing test models",
          "license": "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
          "source": "tools/make_test_mesh.py"}

# numbers the tests check against
RING = {"centre": (0.0, 0.0), "outer": 0.80, "inner": 0.60, "z": (0.40, 0.55), "sides": 48}
BOOM_PIN = {"centre": (0.45, 1.05), "r": 0.06, "sides": 24, "axis": (0.0, 1.0, 0.0)}
WHEEL = {"r": 0.25, "width": 0.18, "sides": 32}
WHEELS = {"WHEEL FL": (0.75, 1.10, 0.25, 1), "WHEEL FR": (-0.75, 1.10, 0.25, 1),
          "WHEEL RL": (0.75, -1.10, 0.25, -1), "WHEEL RR": (-0.75, -1.10, 0.25, -1)}
SINGLE_SHAFT = {"centre": (0.3, 0.1), "r": 0.04, "sides": 16, "z": (0.05, 0.45)}
OBJ_PIPE = {"r_mm": 50.0, "sides": 20}


# ---------------------------------------------------------------------------
# shapes (app coordinates: metres, Z up); each returns positions, normals, UVs, triangles
# ---------------------------------------------------------------------------

class Shape:
    def __init__(self):
        self.p, self.n, self.uv, self.t = [], [], [], []

    def quad(self, a, b, c, d, n=None, uv=((0, 0), (1, 0), (1, 1), (0, 1))):
        """A flat quad a-b-c-d (counter-clockwise seen from outside); own vertices (sharp edges)."""
        a, b, c, d = (np.asarray(v, float) for v in (a, b, c, d))
        if n is None:
            n = np.cross(b - a, d - a)
            n = n / (np.linalg.norm(n) or 1.0)
        k = len(self.p)
        for v, w in zip((a, b, c, d), uv):
            self.p.append(v)
            self.n.append(np.asarray(n, float))
            self.uv.append(w)
        self.t += [(k, k + 1, k + 2), (k, k + 2, k + 3)]

    def box(self, lo, hi, uv_scale=1.0):
        x0, y0, z0 = lo
        x1, y1, z1 = hi
        s = uv_scale
        self.quad((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0), uv=((0, 0), (0, s), (s, s), (s, 0)))
        self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), uv=((0, 0), (s, 0), (s, s), (0, s)))
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1))
        self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1))
        self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1))
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1))

    def wall(self, r, z0, z1, sides, inward=False):
        """The side wall of a facetted cylinder about Z through (0, 0): smooth normals, a seam at angle 0."""
        k = len(self.p)
        for i in range(sides + 1):
            a = 2 * math.pi * i / sides
            c, s = math.cos(a), math.sin(a)
            nn = (-c, -s, 0.0) if inward else (c, s, 0.0)
            for z in (z0, z1):
                self.p.append(np.array((r * c, r * s, z)))
                self.n.append(np.array(nn))
                self.uv.append((i / sides, 0.0 if z == z0 else 1.0))
        for i in range(sides):
            a, b, c, d = k + 2 * i, k + 2 * i + 2, k + 2 * i + 3, k + 2 * i + 1
            self.t += [(a, c, b), (a, d, c)] if inward else [(a, b, c), (a, c, d)]

    def disc(self, r_out, r_in, z, sides, up=True):
        """A flat ring (or a disc when r_in == 0) at height z, facing up or down."""
        k = len(self.p)
        nn = (0.0, 0.0, 1.0 if up else -1.0)
        for i in range(sides):
            a = 2 * math.pi * i / sides
            for r in (r_out, r_in):
                self.p.append(np.array((r * math.cos(a), r * math.sin(a), z)))
                self.n.append(np.array(nn))
                self.uv.append((0.5 + 0.5 * math.cos(a) * r / r_out, 0.5 + 0.5 * math.sin(a) * r / r_out))
        for i in range(sides):
            j = (i + 1) % sides
            o0, i0, o1, i1 = k + 2 * i, k + 2 * i + 1, k + 2 * j, k + 2 * j + 1
            tris = [(o0, o1, i1)] + ([(o0, i1, i0)] if r_in > 0 else [])
            if r_in == 0:
                tris = [(o0, o1, i0)]
            self.t += tris if up else [(a, c, b) for a, b, c in tris]

    def cylinder(self, r, z0, z1, sides):
        self.wall(r, z0, z1, sides)
        self.disc(r, 0.0, z1, sides, up=True)
        self.disc(r, 0.0, z0, sides, up=False)

    def ring(self, r_out, r_in, z0, z1, sides):
        self.wall(r_out, z0, z1, sides)
        self.wall(r_in, z0, z1, sides, inward=True)
        self.disc(r_out, r_in, z1, sides, up=True)
        self.disc(r_out, r_in, z0, sides, up=False)

    def moved(self, m):
        """The shape with a 4x4 matrix applied (positions and normals)."""
        out = Shape()
        p = np.array(self.p)
        n = np.array(self.n)
        out.p = list(p @ m[:3, :3].T + m[:3, 3])
        nn = n @ np.linalg.inv(m[:3, :3])
        out.n = list(nn / np.linalg.norm(nn, axis=1, keepdims=True))
        out.uv, out.t = list(self.uv), list(self.t)
        return out

    def arrays(self):
        return (np.array(self.p, np.float32), np.array(self.n, np.float32), np.array(self.uv, np.float32),
                np.array(self.t, np.uint32))


def rot_x(deg):
    a = math.radians(deg)
    m = np.eye(4)
    m[1:3, 1:3] = [[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]]
    return m


def rot_y(deg):
    a = math.radians(deg)
    m = np.eye(4)
    m[0, 0], m[0, 2], m[2, 0], m[2, 2] = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return m


def move(x, y, z):
    m = np.eye(4)
    m[:3, 3] = (x, y, z)
    return m


# ---------------------------------------------------------------------------
# a PNG (8-bit RGB, no colour chunks) without Pillow
# ---------------------------------------------------------------------------

def png(pixels: np.ndarray) -> bytes:
    h, w, _ = pixels.shape
    raw = b"".join(b"\x00" + pixels[y].astype(np.uint8).tobytes() for y in range(h))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def checker(size=64, cells=8, a=(150, 150, 155), b=(90, 92, 100)) -> bytes:
    y, x = np.mgrid[0:size, 0:size]
    on = ((x * cells // size) + (y * cells // size)) % 2 == 0
    img = np.where(on[..., None], np.array(a), np.array(b))
    return png(img)


# ---------------------------------------------------------------------------
# glTF writer
# ---------------------------------------------------------------------------

def to_gltf(v):
    """App (x, y, z), Z up -> glTF (x, z, -y), Y up."""
    v = np.asarray(v)
    return np.stack((v[..., 0], v[..., 2], -v[..., 1]), axis=-1)


def gltf_matrix(m):
    """An app 4x4 (row-major, Z up) as a glTF node matrix (column-major list, Y up)."""
    c = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)   # app -> glTF
    g = c @ m @ np.linalg.inv(c)
    return [round(float(x), 9) for x in g.T.reshape(-1)]


class Gltf:
    def __init__(self):
        self.doc = {"asset": {"version": "2.0", "generator": "Fresing test models (tools/make_test_mesh.py)"},
                    "scene": 0, "scenes": [{"nodes": []}], "nodes": [], "meshes": [], "materials": [],
                    "buffers": [{"byteLength": 0}], "bufferViews": [], "accessors": []}
        self.bin = bytearray()

    def _view(self, data: bytes, target=None) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, arr: np.ndarray, kind: str, target=None, bounds=False) -> int:
        comp = {np.dtype(np.float32): 5126, np.dtype(np.uint32): 5125, np.dtype(np.uint16): 5123}[arr.dtype]
        acc = {"bufferView": self._view(np.ascontiguousarray(arr).tobytes(), target), "componentType": comp,
               "count": int(len(arr) if kind != "SCALAR" else arr.size), "type": kind}
        if bounds:
            acc["min"] = [float(x) for x in arr.min(axis=0)]
            acc["max"] = [float(x) for x in arr.max(axis=0)]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def material(self, name, rgb=None, texture: bytes | None = None, metallic=0.0, rough=0.6, alpha=1.0) -> int:
        pbr = {"metallicFactor": metallic, "roughnessFactor": rough}
        if rgb is not None:
            pbr["baseColorFactor"] = [round(c, 4) for c in rgb] + [alpha]
        mat = {"name": name, "pbrMetallicRoughness": pbr}
        if alpha < 1.0:
            mat["alphaMode"] = "BLEND"
        if texture is not None:
            img = len(self.doc.setdefault("images", []))
            self.doc["images"].append({"name": "steel checker", "mimeType": "image/png",
                                       "bufferView": self._view(texture)})
            self.doc.setdefault("samplers", [{"magFilter": 9729, "minFilter": 9987}])
            self.doc.setdefault("textures", []).append({"sampler": 0, "source": img})
            pbr["baseColorTexture"] = {"index": len(self.doc["textures"]) - 1}
        self.doc["materials"].append(mat)
        return len(self.doc["materials"]) - 1

    def mesh(self, name, prims, normals=True) -> int:
        out = []
        for shape, mat in prims:
            p, n, uv, t = shape.arrays()
            attrs = {"POSITION": self.accessor(to_gltf(p).astype(np.float32), "VEC3", 34962, bounds=True)}
            if normals:
                attrs["NORMAL"] = self.accessor(to_gltf(n).astype(np.float32), "VEC3", 34962)
            uv = uv.copy()
            uv[:, 1] = 1.0 - uv[:, 1]                       # glTF's v runs down
            attrs["TEXCOORD_0"] = self.accessor(uv, "VEC2", 34962)
            idx = t.reshape(-1).astype(np.uint16 if len(p) < 65536 else np.uint32)
            out.append({"attributes": attrs, "indices": self.accessor(idx, "SCALAR", 34963), "material": mat})
        self.doc["meshes"].append({"name": name, "primitives": out})
        return len(self.doc["meshes"]) - 1

    def node(self, name, mesh=None, matrix=None, children=(), parent=None) -> int:
        nd = {"name": name}
        if mesh is not None:
            nd["mesh"] = mesh
        if matrix is not None and not np.allclose(matrix, np.eye(4)):
            nd["matrix"] = gltf_matrix(matrix)
        self.doc["nodes"].append(nd)
        k = len(self.doc["nodes"]) - 1
        if parent is None:
            self.doc["scenes"][0]["nodes"].append(k)
        else:
            self.doc["nodes"][parent].setdefault("children", []).append(k)
        return k

    def glb(self) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        js = json.dumps(self.doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        js += b" " * (-len(js) % 4)
        body = struct.pack("<II", len(js), 0x4E4F534A) + js + struct.pack("<II", len(self.bin), 0x004E4942) + self.bin
        return struct.pack("<III", 0x46546C67, 2, 12 + len(body)) + body


# ---------------------------------------------------------------------------
# the models
# ---------------------------------------------------------------------------

def crane(revision: str = "a") -> bytes:
    g = Gltf()
    g.doc["asset"]["copyright"] = "Fresing test models (invented), CC BY 4.0"
    g.doc["asset"]["extras"] = dict(CREDIT)
    steel = g.material("Base steel", (1.0, 1.0, 1.0), texture=checker(), metallic=0.3, rough=0.5)
    grey = g.material("Ring grey", (0.35, 0.36, 0.38), metallic=0.8, rough=0.35)
    yellow = g.material("Yellow paint", (0.85, 0.55, 0.02), rough=0.4)
    glass = g.material("Glass", (0.2, 0.3, 0.35), rough=0.05, alpha=0.4)
    rubber = g.material("Black rubber", (0.02, 0.02, 0.02), rough=0.9)

    root = g.node("MESH CRANE")
    base = Shape()
    base.box((-1.0, -1.0, 0.0), (1.0, 1.0, 0.4), uv_scale=2.0)
    g.node("BASE", g.mesh("Base", [(base, steel)]), parent=root)
    ring = Shape()
    ring.ring(RING["outer"], RING["inner"], RING["z"][0], RING["z"][1], RING["sides"])
    g.node("SLEWING RING", g.mesh("Ring", [(ring, grey)]), parent=root)
    turret = g.node("TURRET", parent=root)
    lift = 0.01 if revision == "b" else 0.0
    cab, window = Shape(), Shape()
    cab.box((-0.5, -0.45, 0.56), (0.3, 0.45, 1.35))           # 1 cm above the ring: it turns freely
    window.quad((-0.51, -0.35, 0.95), (-0.51, 0.35, 0.95), (-0.51, 0.35, 1.25), (-0.51, -0.35, 1.25),
                n=(-1.0, 0.0, 0.0))
    g.node("CAB", g.mesh("Cab", [(cab, yellow), (window, glass)]), matrix=move(0, 0, lift), parent=turret)
    boom = Shape()
    boom.box((0.0, -0.12, -0.1), (3.0, 0.12, 0.1))
    g.node("MAIN BOOM" if revision == "b" else "BOOM", g.mesh("Boom", [(boom, yellow)]),
           matrix=move(BOOM_PIN["centre"][0], 0.0, BOOM_PIN["centre"][1]) @ rot_y(-20), parent=turret)
    pin = Shape()
    pin.cylinder(BOOM_PIN["r"], -0.2, 0.2, BOOM_PIN["sides"])
    g.node("BOOM PIN", g.mesh("Pin", [(pin, grey)]),
           matrix=move(BOOM_PIN["centre"][0], 0.0, BOOM_PIN["centre"][1]) @ rot_x(90), parent=turret)
    if revision == "b":
        hook = Shape()
        hook.box((-0.1, -0.1, -0.2), (0.1, 0.1, 0.0))
        g.node("HOOK BLOCK", g.mesh("Hook", [(hook, grey)]), matrix=move(3.2, 0.0, 1.6), parent=turret)
    wheel = Shape()
    wheel.cylinder(WHEEL["r"], -WHEEL["width"] / 2, WHEEL["width"] / 2, WHEEL["sides"])
    wm = g.mesh("Wheel", [(wheel, rubber)])
    for name, (x, y, z, side) in WHEELS.items():
        m = move(x, y, z) @ rot_x(-90)                     # the wheel's axis (its Z) along the app's Y
        if side < 0:
            m = m @ np.diag((1.0, 1.0, -1.0, 1.0))         # turned over by a negative scale (mirrored wheel)
        g.node(name, wm, matrix=m, parent=root)
    return g.glb()


def single() -> bytes:
    g = Gltf()
    g.doc["asset"]["copyright"] = "Fresing test models (invented)"
    grey = g.material("Machined", (0.6, 0.6, 0.62), metallic=1.0, rough=0.3)
    s = Shape()
    s.box((-0.6, -0.4, 0.0), (0.6, 0.4, 0.05))
    shaft = Shape()
    shaft.cylinder(SINGLE_SHAFT["r"], SINGLE_SHAFT["z"][0], SINGLE_SHAFT["z"][1], SINGLE_SHAFT["sides"])
    shaft = shaft.moved(move(SINGLE_SHAFT["centre"][0], SINGLE_SHAFT["centre"][1], 0.0))
    for piece in [shaft]:
        k = len(s.p)
        s.p += piece.p
        s.n += piece.n
        s.uv += piece.uv
        s.t += [(a + k, b + k, c + k) for a, b, c in piece.t]
    for x in (-0.4, -0.15, 0.1):
        s.box((x, -0.3, 0.05), (x + 0.1, -0.2, 0.15))
    g.node("WELDMENT", g.mesh("Weldment", [(s, grey)], normals=False))
    return g.glb()


def obj_files() -> dict:
    """The OBJ, its MTL and its texture (mm, Y up)."""
    lines = ["# Fresing test model (invented), millimetres, Y up", "mtllib test_mesh_parts.mtl"]
    v_count = [0]
    vt_count = [0]

    def y_up(p):                                         # app (x, y, z) in metres -> OBJ mm, Y up
        return (p[0] * 1000.0, p[2] * 1000.0, -p[1] * 1000.0)

    def put_vertices(points):
        for p in points:
            x, y, z = y_up(p)
            lines.append(f"v {x:.3f} {y:.3f} {z:.3f}")
        first = v_count[0] + 1
        v_count[0] += len(points)
        return first

    lines += ["o Frame", "usemtl Steel"]
    s = Shape()
    s.box((-0.6, -0.1, 0.0), (0.6, 0.1, 0.4))
    first = put_vertices(s.p)
    for q in range(0, len(s.t), 2):                      # the box as quads (each quad = 2 triangles in Shape)
        a, b, c = s.t[q]
        _a, _c, d = s.t[q + 1]
        lines.append(f"f {a + first} {b + first} {c + first} {d + first}")
    lines += ["o Cover", "usemtl Blue"]
    hexagon = [(0.3 * math.cos(math.radians(60 * i)), 0.3 * math.sin(math.radians(60 * i)), 0.45) for i in range(6)]
    first = put_vertices(hexagon)
    lines.append("f " + " ".join(str(first + i) for i in range(6)))           # an ngon (6 corners)
    lines.append("usemtl Tile")
    square = [(-0.2, -0.2, 0.46), (0.2, -0.2, 0.46), (0.2, 0.2, 0.46), (-0.2, 0.2, 0.46)]
    first = put_vertices(square)
    for u, v in ((0, 0), (1, 0), (1, 1), (0, 1)):
        lines.append(f"vt {u} {v}")
    vt0 = vt_count[0] + 1
    vt_count[0] += 4
    lines.append("vn 0 1 0")
    lines.append("f " + " ".join(f"{first + i}/{vt0 + i}/-1" for i in range(4)))   # v/vt/vn, a negative index
    lines += ["o Pipe", "usemtl Steel"]
    pipe = Shape()
    pipe.wall(OBJ_PIPE["r_mm"] / 1000.0, 0.0, 0.3, OBJ_PIPE["sides"])
    pipe = pipe.moved(move(0.45, 0.0, 0.4))
    first = put_vertices(pipe.p)
    for a, b, c in pipe.t:
        lines.append(f"f {a + first} {b + first} {c + first}")
    mtl = ["# Fresing test materials", "newmtl Steel", "Kd 0.55 0.56 0.58", "Ns 250", "d 1",
           "newmtl Blue", "Kd 0.05 0.2 0.6", "Ns 90",
           "newmtl Tile", "Kd 1 1 1", "map_Kd test_mesh_tile.png"]
    return {"test_mesh_parts.obj": ("\n".join(lines) + "\n").encode("utf-8"),
            "test_mesh_parts.mtl": ("\n".join(mtl) + "\n").encode("utf-8"),
            "test_mesh_tile.png": checker(32, 4, (200, 60, 40), (240, 230, 220))}


def files() -> dict:
    out = {"test_mesh_crane.glb": crane("a"), "test_mesh_crane_b.glb": crane("b"),
           "test_mesh_single.glb": single()}
    out.update(obj_files())
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = argv[0] if argv else os.path.join(ROOT, "tests", "data")
    os.makedirs(out, exist_ok=True)
    for name, data in files().items():
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(data)
        print(f"{name}: {len(data):,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
