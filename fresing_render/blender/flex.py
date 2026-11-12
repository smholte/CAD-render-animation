"""Hoses, cables and drag chains that follow the motion (task 0058).

Skeleton: the functions the rest of the app calls (see "Design" in tasks/0058-hoses-cables-drag-chains.md). They do
nothing until a hose or chain exists.
"""

from __future__ import annotations

TAG = "fr_flex"
MOD = "FR flex"
SHAPES = "FR flex shapes"
COLLECTION = "Flex parts"


def items(scene):
    return scene.fresing.flex


def changed(scene, item) -> None:
    pass


def refresh(scene, force: bool = False) -> None:
    pass


def bake(scene, anim) -> list[str]:
    return []


def after_clear(scene) -> None:
    pass


def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]:
    return []


def register() -> None:
    pass


def unregister() -> None:
    pass
