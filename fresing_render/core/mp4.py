"""Reads the tracks of an MP4 file without ffmpeg (no Blender here): which kinds there are and how long each is."""

from __future__ import annotations

import struct


def _boxes(data: bytes, start: int, end: int):
    i = start
    while i + 8 <= end:
        size, kind = struct.unpack(">I4s", data[i:i + 8])
        header = 8
        if size == 1:
            size, header = struct.unpack(">Q", data[i + 8:i + 16])[0], 16
        elif size == 0:
            size = end - i
        if size < header:
            return
        yield kind.decode("latin1"), i + header, i + size
        i += size


def track_seconds(path: str) -> dict[str, float]:
    """{'vide': seconds, 'soun': seconds} of the tracks of an MP4 file ('vide' = picture, 'soun' = sound)."""
    with open(path, "rb") as fh:
        data = fh.read()
    out: dict[str, float] = {}
    for kind, a, b in _boxes(data, 0, len(data)):
        if kind != "moov":
            continue
        for k2, a2, b2 in _boxes(data, a, b):
            if k2 != "trak":
                continue
            handler, secs = "", 0.0
            for k3, a3, b3 in _boxes(data, a2, b2):
                if k3 != "mdia":
                    continue
                for k4, a4, _b4 in _boxes(data, a3, b3):
                    if k4 == "hdlr":
                        handler = data[a4 + 8:a4 + 12].decode("latin1")
                    elif k4 == "mdhd":
                        if data[a4] == 1:
                            scale, dur = struct.unpack(">IQ", data[a4 + 20:a4 + 32])
                        else:
                            scale, dur = struct.unpack(">II", data[a4 + 12:a4 + 20])
                        secs = dur / scale if scale else 0.0
            if handler:
                out[handler] = secs
    return out
