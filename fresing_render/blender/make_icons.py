"""The large icons of Make (task 0308): ``core/make_icons.py``'s drawings as Blender geometry icons.

Blender draws a geometry icon twice as large as an ordinary one, but it starts it where an ordinary 16 px icon would
start: in a button without text that is the middle, so the icon sticks out to the right (measured in 5.2.3). A button
with a text – one space is enough – puts its icon at its left edge, and a button about two icons wide then shows it
whole, in the middle. So the icon buttons get ``text=" "`` (``icon_button``).

The icons are made once at registration (``register``) and given back at ``unregister``. Where Blender cannot make
them (a background run without the icon system), every button falls back to Blender's own icon of the output.
"""

from __future__ import annotations

import bpy

from ..core import make_icons as drawings

_IDS: dict = {}


def register() -> None:
    unregister()
    for key in drawings.KEYS:
        try:
            _IDS[key] = bpy.app.icons.new_triangles((0, drawings.SIZE), *drawings.icon(key))
        except Exception as exc:  # noqa: BLE001 - Blender's own icons are used instead
            print(f"Fresing Render: the large Make icon '{key}' was not made:", exc)


def unregister() -> None:
    for icon_id in _IDS.values():
        try:
            bpy.app.icons.release(icon_id)
        except Exception:  # noqa: BLE001
            pass
    _IDS.clear()


def icon_id(key: str) -> int:
    """The large icon of output ``key``; 0 when there is none."""
    return int(_IDS.get(key, 0) or 0)


def icon_button(layout, operator: str, key: str, fallback: str, text: str = "", depress: bool = False):
    """A button with the large icon of output ``key`` (its text beside it when ``text`` is given); Blender's
    ``fallback`` icon when the large one is missing. Returns the operator's properties."""
    gid = icon_id(key)
    if gid:
        return layout.operator(operator, text=text or " ", icon_value=gid, depress=depress)
    return layout.operator(operator, text=text, icon=fallback, depress=depress)
