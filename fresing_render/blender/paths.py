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


def refresh(scene, force: bool = False) -> None:
    pass


def bake(scene, anim) -> list:
    return []


def after_clear(scene) -> None:
    pass


def after_model_update(scene, by_uid: dict, mapping: dict) -> list:
    return []


def register() -> None:
    pass


def unregister() -> None:
    pass
