"""Picture headers (PNG, JPEG, KTX2) and a tiny PNG writer – plain Python."""
from __future__ import annotations

import struct
import zlib

PNG_SIG = b"\x89PNG\r\n\x1a\n"
KTX2_SIG = b"\xabKTX 20\xbb\r\n\x1a\n"


def picture_info(data: bytes) -> tuple[str, int, int] | None:
    """(kind, width, height) of a PNG, JPEG or KTX2 file, or None when it is none of them."""
    if data[:8] == PNG_SIG and len(data) >= 24 and data[12:16] == b"IHDR":
        w, h = struct.unpack(">II", data[16:24])
        return ("png", w, h)
    if data[:12] == KTX2_SIG and len(data) >= 28:
        w, h = struct.unpack_from("<II", data, 20)
        return ("ktx2", w, h)
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                if i + 9 <= len(data):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return ("jpeg", w, h)
                return None
            i += 2 + seg
    return None


COLOUR_CHUNKS = (b"gAMA", b"iCCP", b"sRGB", b"cHRM", b"cICP", b"mDCV", b"cLLI", b"tRNS")


def page_png_problem(data: bytes) -> str | None:
    """Why a PNG is not a light-map page (FORMAT.md 8.3): 8-bit RGB, not interlaced, no colour chunks (a browser
    would colour-convert the stored values)."""
    if data[:8] != PNG_SIG:
        return "not a PNG"
    pos = 8
    first = True
    while pos + 8 <= len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        if first:
            if kind != b"IHDR" or n != 13:
                return "no IHDR first"
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", data[pos + 8:pos + 21])
            if (depth, ctype) != (8, 2):
                return f"{depth}-bit colour type {ctype} – pages are 8-bit RGB (colour type 2) without alpha"
            if inter:
                return "interlaced"
            first = False
        if kind in COLOUR_CHUNKS:
            return f"it has a {kind.decode()} chunk – pages carry no colour information (browsers would convert)"
        if kind == b"IEND":
            return None
        pos += 12 + n
    return "cut off (no IEND)"


def png_rgb(width: int, height: int, rows: list[bytes]) -> bytes:
    """An 8-bit RGB PNG from ``height`` rows of ``width * 3`` bytes (row 0 = the top). Deterministic."""
    assert len(rows) == height and all(len(r) == width * 3 for r in rows)

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + r for r in rows)
    return (PNG_SIG + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def png_read_rgb(data: bytes) -> tuple[int, int, list[bytes]]:
    """Rows of an 8-bit RGB, non-interlaced PNG (what ``png_rgb`` writes; enough for tests and the checker)."""
    if data[:8] != PNG_SIG:
        raise ValueError("not a PNG")
    pos, idat = 8, b""
    w = h = 0
    while pos < len(data):
        n = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, inter = struct.unpack(">IIBBBBB", body)
            if (depth, ctype, inter) != (8, 2, 0):
                raise ValueError("only 8-bit RGB, non-interlaced PNGs are read here")
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * 3
    rows, prev = [], bytearray(stride)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for x in range(stride):
            a = line[x - 3] if x >= 3 else 0
            b = prev[x]
            c = prev[x - 3] if x >= 3 else 0
            if f == 1:
                line[x] = (line[x] + a) & 255
            elif f == 2:
                line[x] = (line[x] + b) & 255
            elif f == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return w, h, rows
