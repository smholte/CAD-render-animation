"""A part's mesh key (task 0324): the same key = the same mesh, so a model update can take the old cache's mesh.

No Blender, no OpenCascade: the reader hands in the part's shape as OpenCascade's own binary copy (``BinTools``, the
same bytes it sends to its meshing helpers) and everything else that decides the mesh. The key covers:

* the **whole shape**: every face, edge, point, surface and tolerance in the binary copy – one number off anywhere
  (a face moved 0.1 mm) and the key is another. The STEP file's entity numbers are not in it (they change between
  exports); the numbers are in the reader's millimetres, so a part drawn in another unit has other numbers;
* how it is meshed: the Detail (deflection, angle, the facets-by-size table), whether it counts as a standard part
  (bolts get fewer segments), the cache version;
* the faces' own colours and their appearance names (they are written into the mesh's face sets).

Not in the key (they live on the objects, not on the mesh): the part's name, its colour, its CAD material, where it
sits. Any doubt is "changed": a part without a binary copy gets no key and is meshed again.
"""

from __future__ import annotations

import hashlib
import json

DIGEST = 20                      # bytes; 160 bits – two different shapes never meet by chance


def part_key(blob: bytes, *, quality: str, lin_rel: float, ang: float, facets: dict | None, standard: bool,
             face_colours, colour_names, version: int) -> str:
    """The key of one unique part (hex). ``face_colours``: a colour (r, g, b) or None per face, or None;
    ``colour_names``: the appearance name of each colour of the part's palette (in palette order)."""
    if not blob:
        return ""
    head = {
        "v": int(version),
        "q": str(quality),
        "lin": repr(float(lin_rel)),
        "ang": repr(float(ang)),
        "facets": {k: repr(float(v)) for k, v in sorted((facets or {}).items())},
        "std": bool(standard),
        "fc": None if face_colours is None else [None if c is None else [repr(float(x)) for x in c]
                                                 for c in face_colours],
        "names": list(colour_names or []),
    }
    h = hashlib.blake2b(digest_size=DIGEST)
    h.update(json.dumps(head, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    h.update(b"\0")
    h.update(blob)
    return h.hexdigest()


def palette_of(face_colours) -> list:
    """The palette the mesher makes from a part's face colours: each colour once, in face order (as
    ``step_reader._mesh_shape``)."""
    out: list = []
    for c in face_colours or []:
        if c is not None and c not in out:
            out.append(c)
    return out


def blender_key(key: str, palette, part_colour) -> str:
    """The key of a Blender mesh made from a cache mesh: the reader's key plus what the build adds to the mesh. The
    part's colour (the most common colour of its copies) decides which face colours get a face set of their own, so it
    counts only for a part with coloured faces."""
    if not key:
        return ""
    if not palette:
        return key
    pc = None if part_colour is None else [repr(float(x)) for x in part_colour]
    return key + ":" + hashlib.blake2b(json.dumps(pc).encode("utf-8"), digest_size=8).hexdigest()
