"""Every built-in material of the picker has its picture, made from its current settings (task 0273).

A material's look changed (``materials_lib.MATERIALS``, its finish in ``core/finishes.py``, its picture colour, the
swatch's ``PICTURE_VERSION``) without a new picture: this fails and names the one command to run."""

import json
import os
import struct

from fresing_render.core import material_files as F

COMMAND = "python tools/material_pictures.py   (makes the missing and changed ones with the real Blender, ~4 s each)"


def _hashes():
    with open(os.path.join(F.PICTURES_DIR, F.HASHES), encoding="utf-8") as fh:
        return json.load(fh)


def _jpeg_size(path):
    with open(path, "rb") as fh:
        data = fh.read()
    assert data[:2] == b"\xff\xd8", path
    i = 2
    while i < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise AssertionError(f"no size in {path}")


def test_every_builtin_has_an_up_to_date_picture():
    h = _hashes()
    old = [k for k in F.builtin_keys() if h.get(k) != F.picture_hash(k)
           or not os.path.isfile(os.path.join(F.PICTURES_DIR, F.picture_name(k)))]
    assert not old, f"{len(old)} material picture(s) missing or old: {', '.join(old[:8])} … run: {COMMAND}"


def test_no_picture_left_over_and_all_256_px():
    want = {F.picture_name(k) for k in F.builtin_keys()}
    have = {n for n in os.listdir(F.PICTURES_DIR) if n.endswith(F.PICTURE_EXT)}
    assert have == want, f"left over: {sorted(have - want)} – run: {COMMAND}"
    assert set(_hashes()) == set(F.builtin_keys())
    for n in sorted(have):
        assert _jpeg_size(os.path.join(F.PICTURES_DIR, n)) == (F.PICTURE_SIZE, F.PICTURE_SIZE), n
    total = sum(os.path.getsize(os.path.join(F.PICTURES_DIR, n)) for n in have)
    assert total < 3 * 1024 * 1024, f"the pictures take {total / 1e6:.1f} MB (they ship in every update)"


def test_a_changed_material_asks_for_a_new_picture(monkeypatch):
    from fresing_render.core import materials_lib as ML
    before = F.picture_hash("builtin:chrome")
    monkeypatch.setitem(ML.MATERIALS, "chrome", dict(ML.MATERIALS["chrome"], roughness=0.3))
    assert F.picture_hash("builtin:chrome") != before
    monkeypatch.setattr(F, "PICTURE_VERSION", F.PICTURE_VERSION + 1)
    assert F.picture_hash("builtin:paint_satin") != _hashes()["builtin:paint_satin"]
