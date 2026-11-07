"""Storing arrays in ID properties without breaking Blender's memory (task 0038).

Blender 5.2.3 corrupts its memory when an array ID property that already exists gets a NumPy array of
another length: ``scene["x"] = np.zeros(250)`` and later ``scene["x"] = np.zeros(2000)`` ends in
"free(): invalid size" or a segfault a little later, wherever the next big allocation happens. Deleting the
key first and then assigning is safe (a new property is made). Every array that goes into an ID property goes
through ``store_array``.
"""

from __future__ import annotations

import numpy as np


def store_array(owner, key: str, values, dtype=np.float64) -> None:
    """Store ``values`` (any sequence or NumPy array) as a flat array property ``owner[key]``.

    The old property is deleted first, so its length never changes in place."""
    arr = np.ascontiguousarray(np.asarray(values, dtype=dtype).reshape(-1))
    if key in owner:
        del owner[key]
    owner[key] = arr
