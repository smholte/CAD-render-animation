"""Read and write binary glTF 2.0 (.glb) – only what the house scene format needs. Plain Python, no NumPy.

Reading: ``Glb.parse(data)`` → ``.json`` (the glTF document) and ``.accessor(i)`` → a list of tuples (or of numbers
for SCALAR accessors), normalised integers turned into floats as glTF says.
Writing: ``GlbWriter`` collects buffer views and accessors and ``to_bytes()`` gives the file.
"""
from __future__ import annotations

import json
import math
import struct

MAGIC = 0x46546C67  # "glTF"
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMPONENT = {  # componentType -> (struct code, bytes, normalised divisor)
    5120: ("b", 1, 127.0),
    5121: ("B", 1, 255.0),
    5122: ("h", 2, 32767.0),
    5123: ("H", 2, 65535.0),
    5125: ("I", 4, None),
    5126: ("f", 4, None),
}
COUNT = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


class GlbError(ValueError):
    pass


class Glb:
    def __init__(self, doc: dict, binary: bytes):
        self.json = doc
        self.bin = binary

    @classmethod
    def parse(cls, data: bytes) -> "Glb":
        if len(data) < 20:
            raise GlbError("too short for a .glb file")
        magic, version, length = struct.unpack_from("<III", data, 0)
        if magic != MAGIC:
            raise GlbError("not a .glb file (no glTF header)")
        if version != 2:
            raise GlbError(f"glTF version {version}, expected 2")
        if length != len(data):
            raise GlbError(f"header says {length} bytes, the file has {len(data)}")
        pos, doc, binary = 12, None, b""
        while pos < len(data):
            if pos + 8 > len(data):
                raise GlbError("cut-off chunk header")
            clen, ctype = struct.unpack_from("<II", data, pos)
            body = data[pos + 8: pos + 8 + clen]
            if len(body) != clen:
                raise GlbError("cut-off chunk")
            if ctype == CHUNK_JSON and doc is None:
                try:
                    doc = json.loads(body.decode("utf-8"), parse_constant=_no_constant)
                except (UnicodeDecodeError, ValueError) as e:
                    raise GlbError(f"its JSON chunk is not valid JSON: {e}") from None
            elif ctype == CHUNK_BIN and not binary:
                binary = bytes(body)
            pos += 8 + clen
        if not isinstance(doc, dict):
            raise GlbError("no JSON chunk with a glTF object")
        return cls(doc, binary)

    # ---- accessors ----
    def accessor(self, index: int) -> list:
        """The accessor's values: tuples for VEC/MAT types, plain numbers for SCALAR."""
        try:
            acc = self.json["accessors"][index]
        except (KeyError, IndexError, TypeError):
            raise GlbError(f"accessor {index} does not exist") from None
        ctype = acc.get("componentType")
        if ctype not in COMPONENT:
            raise GlbError(f"accessor {index}: unknown componentType {ctype}")
        code, size, div = COMPONENT[ctype]
        n = COUNT.get(acc.get("type"))
        if n is None:
            raise GlbError(f"accessor {index}: unknown type {acc.get('type')}")
        count = acc.get("count", 0)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise GlbError(f"accessor {index}: count {count!r} is not a whole number")
        if not isinstance(acc.get("bufferView", 0), int):
            raise GlbError(f"accessor {index}: bufferView is not a number")
        if "bufferView" not in acc:  # all zeros (glTF allows it)
            zero = (0.0,) * n
            return [zero[0] if n == 1 else zero for _ in range(count)]
        try:
            view = self.json["bufferViews"][acc["bufferView"]]
        except (KeyError, IndexError):
            raise GlbError(f"accessor {index}: its bufferView does not exist") from None
        if view.get("buffer", 0) != 0:
            raise GlbError(f"accessor {index}: only the .glb's own buffer is allowed")
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or n * size
        end_needed = start + (count - 1) * stride + n * size if count else start
        view_end = view.get("byteOffset", 0) + view.get("byteLength", 0)
        if end_needed > view_end or view_end > len(self.bin):
            raise GlbError(f"accessor {index} reads past the end of its data")
        norm = acc.get("normalized", False) and div is not None
        fmt = "<" + code * n
        out = []
        if stride == n * size:
            flat = struct.unpack_from("<" + code * (n * count), self.bin, start)
            if norm:
                flat = [max(v / div, -1.0) for v in flat]
            if n == 1:
                return list(flat)
            return [tuple(flat[i:i + n]) for i in range(0, len(flat), n)]
        for i in range(count):
            v = struct.unpack_from(fmt, self.bin, start + i * stride)
            if norm:
                v = tuple(max(x / div, -1.0) for x in v)
            out.append(v[0] if n == 1 else v)
        return out

    # ---- nodes ----
    def world_matrices(self) -> dict[int, list[float]]:
        """Node index -> its world matrix (column-major, 16 numbers) for every node reached from the default scene
        (``scene``, else scene 0). Raises GlbError for a node tree that is not a tree."""
        nodes = self.json.get("nodes", [])
        scenes = self.json.get("scenes", [])
        if not isinstance(nodes, list) or not isinstance(scenes, list) or not scenes:
            raise GlbError("no scene")
        si = self.json.get("scene", 0)
        if not isinstance(si, int) or not (0 <= si < len(scenes)) or not isinstance(scenes[si], dict):
            raise GlbError(f"scene {si!r} does not exist")
        parents: dict[int, int] = {}
        for i, n in enumerate(nodes):
            if not isinstance(n, dict):
                raise GlbError(f"node {i} is not an object")
            for c in n.get("children", []):
                if not isinstance(c, int) or not (0 <= c < len(nodes)):
                    raise GlbError(f"node {i}: child {c!r} does not exist")
                if c in parents:
                    raise GlbError(f"node {c} has two parents")
                parents[c] = i
        out: dict[int, list[float]] = {}
        roots = scenes[si].get("nodes", [])
        for r in roots:
            if not isinstance(r, int) or not (0 <= r < len(nodes)):
                raise GlbError(f"the scene's node {r!r} does not exist")
            if r in parents:
                raise GlbError(f"node {r} is a root of the scene and also a child")
        stack = [(r, IDENTITY) for r in roots]
        while stack:
            i, parent = stack.pop()
            if i in out:
                raise GlbError(f"node {i} is reached twice (a loop or a node listed twice)")
            m = local_matrix(nodes[i])
            if len(m) != 16 or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in m):
                raise GlbError(f"node {i}: its transform is not 16 finite numbers")
            m = mat_mul(parent, m)
            out[i] = m
            for c in nodes[i].get("children", []):
                stack.append((c, m))
        return out


IDENTITY = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0]


def _no_constant(name):
    raise ValueError(f"{name} is not allowed in JSON")


def is_rigid(m: list[float], eps: float = 1e-4) -> bool:
    """True when the matrix only turns and moves (no scale, no shear, no mirror)."""
    cols = [m[0:3], m[4:7], m[8:11]]
    for i in range(3):
        for j in range(3):
            d = sum(a * b for a, b in zip(cols[i], cols[j]))
            if abs(d - (1.0 if i == j else 0.0)) > eps:
                return False
    det = (cols[0][0] * (cols[1][1] * cols[2][2] - cols[1][2] * cols[2][1])
           - cols[1][0] * (cols[0][1] * cols[2][2] - cols[0][2] * cols[2][1])
           + cols[2][0] * (cols[0][1] * cols[1][2] - cols[0][2] * cols[1][1]))
    return det > 0


def local_matrix(node: dict) -> list[float]:
    if "matrix" in node:
        return [float(x) for x in node["matrix"]]
    t = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    r = [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w),
         2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w),
         2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)]
    return [r[0] * s[0], r[1] * s[0], r[2] * s[0], 0,
            r[3] * s[1], r[4] * s[1], r[5] * s[1], 0,
            r[6] * s[2], r[7] * s[2], r[8] * s[2], 0,
            t[0], t[1], t[2], 1.0]


def mat_mul(a: list[float], b: list[float]) -> list[float]:
    """a @ b for column-major 4x4 matrices."""
    return [sum(a[k * 4 + r] * b[c * 4 + k] for k in range(4)) for c in range(4) for r in range(4)]


def is_identity(m: list[float], eps: float = 1e-9) -> bool:
    return all(abs(x - y) <= eps for x, y in zip(m, IDENTITY))


def pack(doc: dict, binary: bytes) -> bytes:
    """A .glb from a glTF document and its binary chunk (as read by ``Glb.parse``)."""
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary = bytes(binary) + b"\0" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + (8 + len(binary) if binary else 0)
    out = struct.pack("<III", MAGIC, 2, total) + struct.pack("<II", len(js), CHUNK_JSON) + js
    if binary:
        out += struct.pack("<II", len(binary), CHUNK_BIN) + binary
    return out


class GlbWriter:
    """Builds a .glb: add data with ``accessor(...)``, then fill ``doc`` (meshes, nodes …) and call ``to_bytes``."""

    def __init__(self, generator: str):
        self.doc: dict = {"asset": {"version": "2.0", "generator": generator},
                          "buffers": [{"byteLength": 0}], "bufferViews": [], "accessors": []}
        self.bin = bytearray()

    def _view(self, data: bytes, target: int | None) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        self.doc["bufferViews"].append(view)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, values: list, type_: str, component: int = 5126, *, normalized: bool = False,
                 target: int | None = 34962, minmax: bool = False) -> int:
        n = COUNT[type_]
        code = COMPONENT[component][0]
        flat = [x for v in values for x in (v if n > 1 else (v,))]
        data = struct.pack("<" + code * len(flat), *flat)
        acc = {"bufferView": self._view(data, target), "componentType": component, "count": len(values),
               "type": type_}
        if normalized:
            acc["normalized"] = True
        if minmax and values:
            cols = list(zip(*[(v if n > 1 else (v,)) for v in values]))
            acc["min"] = [min(c) for c in cols]
            acc["max"] = [max(c) for c in cols]
        self.doc["accessors"].append(acc)
        return len(self.doc["accessors"]) - 1

    def image(self, data: bytes, mime: str) -> int:
        self.doc.setdefault("images", []).append({"bufferView": self._view(data, None), "mimeType": mime})
        return len(self.doc["images"]) - 1

    def to_bytes(self) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"][0]["byteLength"] = len(self.bin)
        js = json.dumps(self.doc, separators=(",", ":"), ensure_ascii=False, sort_keys=False).encode("utf-8")
        js += b" " * (-len(js) % 4)
        total = 12 + 8 + len(js) + (8 + len(self.bin) if self.bin else 0)
        out = bytearray(struct.pack("<III", MAGIC, 2, total))
        out += struct.pack("<II", len(js), CHUNK_JSON) + js
        if self.bin:
            out += struct.pack("<II", len(self.bin), CHUNK_BIN) + self.bin
        return bytes(out)
