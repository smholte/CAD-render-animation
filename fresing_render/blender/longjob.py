"""Shared bits of the long jobs that run step by step in a modal operator (web 3D export, House bake, clash check).

Bug hunt 0118 row 13: Ctrl+Z pressed while such a job runs passed through to Blender's undo. The web 3D export then
stopped with no file and no message, and a House bake put the weather and hiding it saved at its start back over
the undone scene (a mix of two states). While a job runs, its modal swallows undo and redo and says "Cancel first".
"""

from __future__ import annotations

UNDO_KEYS = {"Z", "Y"}       # Ctrl+Z undo, Ctrl+Shift+Z / Ctrl+Y redo (Blender's keymap on Windows)


def is_undo(event) -> bool:
    """True for a press of Ctrl+Z, Ctrl+Shift+Z or Ctrl+Y (Cmd on a Mac)."""
    return (event.type in UNDO_KEYS and event.value == "PRESS"
            and bool(getattr(event, "ctrl", False) or getattr(event, "oskey", False)))


def undo_note(what: str) -> str:
    return f"Undo is off while the {what} runs: press Cancel (or Esc) first, then undo"


def swallow_undo(op, context, event, what: str) -> bool:
    """In a long job's ``modal``: True when ``event`` is undo/redo, which is then kept from Blender and explained."""
    if not is_undo(event):
        return False
    note = undo_note(what)
    try:
        context.scene.fresing.last_message = note
    except Exception:  # noqa: BLE001
        pass
    op.report({"WARNING"}, note)
    return True
