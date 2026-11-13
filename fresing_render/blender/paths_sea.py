"""A cable into the sea (task 0081): the catenary from its last contact down to the seabed, the cable lying on the
seabed behind it, and things fitted on the cable (CPS sets, bend restrictors) riding along. Being written."""

from __future__ import annotations


def changed(scene, item) -> None:
    """A sea-end setting changed."""


def rider_changed(scene, rider) -> None:
    """A rider setting changed."""


def cut_box(scene):
    """The cut-away box placed by the sea cables, or None (see the Design in tasks/0081)."""
    return None
