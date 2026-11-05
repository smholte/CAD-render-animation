"""Counts in plain English for the panels and messages: '1 part', '2 parts', '1 face set'.

No Blender here, so it can be tested on its own (tests/test_core.py).
"""

from __future__ import annotations


def plural(n: int, one: str, many: str | None = None) -> str:
    """The number and the word in the right form: plural(1, 'part') -> '1 part', plural(3, 'part') -> '3 parts'.

    `many` for words that do not just get an 's': plural(2, 'copy', 'copies') -> '2 copies'.
    Zero takes the plural, as in English ('0 parts').
    """
    return f"{n} {one if n == 1 else (many if many is not None else one + 's')}"


def verb(n: int, one: str, many: str) -> str:
    """The verb that goes with a count: verb(1, 'matches', 'match') -> 'matches'."""
    return one if n == 1 else many
