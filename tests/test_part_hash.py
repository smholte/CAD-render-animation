"""Task 0324: the mesh key of a part (core/part_hash.py) – everything that decides the mesh is in it, nothing else."""
from fresing_render.core import part_hash as H

BASE = dict(quality="normal", lin_rel=0.0015, ang=0.30, facets={"cap_mm": 0.5, "small_mm": 200.0, "small_gap": 0.25,
                                                               "small_ang": 0.63},
            standard=False, face_colours=None, colour_names=[], version=8)


def key(blob=b"shape", **kw):
    args = dict(BASE)
    args.update(kw)
    return H.part_key(blob, **args)


def test_same_input_same_key():
    assert key() == key()
    assert len(key()) == 2 * H.DIGEST


def test_one_byte_of_the_shape_changes_the_key():
    assert key(b"shape") != key(b"shapf")
    assert key(b"shape") != key(b"shape\0")


def test_how_it_is_meshed_is_in_the_key():
    k = key()
    assert key(quality="fine") != k
    assert key(lin_rel=0.0006) != k
    assert key(ang=0.18) != k
    assert key(facets=dict(BASE["facets"], cap_mm=0.2)) != k
    assert key(facets=None) != k
    assert key(standard=True) != k
    assert key(version=9) != k


def test_face_colours_and_their_names_are_in_the_key():
    k = key(face_colours=[None, (1.0, 0.0, 0.0)], colour_names=[""])
    assert k != key()
    assert key(face_colours=[None, (1.0, 0.0, 0.001)], colour_names=[""]) != k
    assert key(face_colours=[(1.0, 0.0, 0.0), None], colour_names=[""]) != k     # another face
    assert key(face_colours=[None, (1.0, 0.0, 0.0)], colour_names=["Red RAL 3000"]) != k


def test_no_shape_no_key():
    assert key(b"") == ""


def test_palette_in_face_order():
    assert H.palette_of([None, (1, 0, 0), (0, 1, 0), (1, 0, 0)]) == [(1, 0, 0), (0, 1, 0)]
    assert H.palette_of(None) == []


def test_blender_key_counts_the_part_colour_only_with_coloured_faces():
    k = key()
    assert H.blender_key(k, [], (0.5, 0.5, 0.5)) == k == H.blender_key(k, [], None)
    a = H.blender_key(k, [(1.0, 0.0, 0.0)], (0.5, 0.5, 0.5))
    assert a != k and a.startswith(k)
    assert H.blender_key(k, [(1.0, 0.0, 0.0)], (0.5, 0.5, 0.6)) != a
    assert H.blender_key("", [(1.0, 0.0, 0.0)], None) == ""
