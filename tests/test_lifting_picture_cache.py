"""Task 0349 (0204's open point): the library's picture after Make a crane… with Replace. The picture cache was keyed
on the path, so the panel showed the replaced crane's old picture until Blender was restarted; it is keyed on the
path, the change time and the size now. Blender as a Python module."""

from __future__ import annotations

import os

import numpy as np
import pytest

bpy = pytest.importorskip("bpy")


def _png(path, size, colour):
    img = bpy.data.images.new("fr_pic_test", size, size)
    px = np.tile(np.array(colour + (1.0,), np.float32), size * size)
    img.pixels.foreach_set(px)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def test_a_replaced_picture_is_loaded_again(tmp_path):
    from fresing_render.blender import ui_lifting as U
    path = str(tmp_path / "Crane.png")
    _png(path, 8, (1.0, 0.0, 0.0))
    k1 = U.picture_key(path)
    i1 = U._icon_of(path)
    assert U._icon_of(path) == i1                         # loaded once while the file stays the same
    st = os.stat(path)
    _png(path, 16, (0.0, 0.0, 1.0))                       # Make a crane… with Replace writes the picture again
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 10_000_000))
    k2 = U.picture_key(path)
    assert k2 != k1
    U._icon_of(path)
    assert k2 in U._PREVIEWS["coll"] and k1 in U._PREVIEWS["coll"]
    assert U.picture_key(str(tmp_path / "missing.png")) == "" and U._icon_of(str(tmp_path / "missing.png")) == 0
    U.unregister_previews()
