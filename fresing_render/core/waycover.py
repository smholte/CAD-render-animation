"""Way covers (task 0034): the numbers, without Blender.

A telescopic way cover is a row of sections that slide into each other. When the machine axis moves
its full travel, section k of N moves k/N of it (relative to the fixed end), so every section slides the
same amount relative to its neighbour: 500 mm over 5 sections = 100, 200, 300, 400, 500 mm.

Two ways of counting, chosen in the panel:
* the sections are the *moving* covers (default): shares 1/N, 2/N … N/N;
* the *fixed housing counts as a section*: the first one never moves, the others share the travel
  over N-1 steps: 0, 1/(N-1) … 1 (5 sections over 500 mm = 0, 125, 250, 375, 500 mm).
"""

from __future__ import annotations

from . import cylinders


def shares(n: int, housing_counts: bool = False) -> list[float]:
    """How much of the axis travel each of ``n`` sections takes, from the fixed end to the moving end."""
    if n <= 0:
        return []
    if housing_counts:
        if n == 1:
            return [0.0]
        return [0.0] + _steps(n - 1)
    return cylinders.stage_shares(n - 1) + [1.0]


def _steps(m: int) -> list[float]:
    """k/m for k = 1 … m."""
    return cylinders.stage_shares(m - 1) + [1.0]


def signed(values: list[float], flip: bool) -> list[float]:
    """The shares with the sign of the direction: Flip opens the covers the other way."""
    return [-v if flip and v else v for v in values]


def travel_each(total_mm: float, n: int, housing_counts: bool = False) -> float:
    """How far each section slides relative to its neighbour (mm)."""
    steps = (n - 1) if housing_counts else n
    return abs(total_mm) / steps if steps > 0 else 0.0


def positions_mm(total_mm: float, n: int, housing_counts: bool = False, flip: bool = False) -> list[float]:
    """Where each section is (mm from its CAD place) when the axis has moved ``total_mm``."""
    return [s * total_mm for s in signed(shares(n, housing_counts), flip)]


def summary(n: int, total_mm: float, housing_counts: bool = False) -> str:
    """Plain words for the panel: 'Moving covers: 5 sections × 100 mm (100, 200, 300, 400, 500 mm)'."""
    if n <= 0:
        return "No sections yet"
    each = travel_each(total_mm, n, housing_counts)
    places = ", ".join(f"{abs(p):g}" for p in positions_mm(total_mm, n, housing_counts))
    kind = "The fixed housing counts as the first section" if housing_counts else "Sections are the moving covers"
    if n == 1 and housing_counts:
        return f"{kind}: one section, it does not move"
    word = "section" if n == 1 else "sections"
    return f"{kind}: {n} {word} × {each:g} mm ({places} mm)"
