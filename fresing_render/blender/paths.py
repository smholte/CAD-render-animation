"""Cables and paths (task 0078) – placeholder until the module is written (see tasks/0078-cable-paths.md, Design)."""

from __future__ import annotations

TAG = "fr_cable"


def is_cable_joint(scene, j) -> bool:
    """True when ``j`` is the slide joint of a cable (its value = metres paid out)."""
    return any(c.joint == j.name for c in scene.fresing.cables)


def changed(scene, item) -> None:
    pass


def contact_changed(scene, contact) -> None:
    pass
