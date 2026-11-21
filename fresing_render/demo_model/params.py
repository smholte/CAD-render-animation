"""The parameters of the demo's ship and its cable (tasks 0076, 0153; task 0247: the ship alone). Millimetres; x towards
the bow, y to port, z up.

The stern (transom) is at x = 0, the bow at x = L; the waterline is z = 0 (the app's sea). The cable is the power
cable that lies on the seabed of the wind park (``park.py``): its Ø gives its minimum bend radius and the radius of its
bends onto the scour rock.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MBR_PER_D = 17.5            # minimum bend radius / cable Ø (3.5 m at Ø200; a usual figure for power cables)
BEND_MARGIN = 1.15          # every bend of the cable lies this much above the MBR


def up50(v: float) -> float:
    """Round up to the next 50 mm."""
    return 50.0 * math.ceil(v / 50.0 - 1e-9)


@dataclass
class ShipParams:
    """The ship (a fixed length and beam) and the power cable on the seabed."""
    cable_d: float = 200.0          # power cable Ø (50 … 500)
    mbr: float = 0.0                # minimum bend radius; 0 = MBR_PER_D x cable_d
    length: float = 120000.0
    beam: float = 27000.0
    deck_z: float = 3000.0          # freeboard 3 m
    keel_z: float = -6000.0

    def __post_init__(self):
        if not 50.0 <= self.cable_d <= 500.0:
            raise ValueError("cable Ø must be 50 … 500 mm")
        if self.mbr <= 0:
            self.mbr = MBR_PER_D * self.cable_d

    @property
    def cable_r(self) -> float:
        return self.cable_d / 2.0

    @property
    def bend_r(self) -> float:
        """Radius of every bend of the cable (at least the MBR)."""
        return up50(self.mbr * BEND_MARGIN)


@dataclass
class ParkParams:
    """The wind park round the vessel (task 0166), in the park's own coordinates (``park.py``): mm, origin = where the
    first end's CAD piece meets the seabed lay line, +x along the lay line towards the vessel, z 0 the waterline."""
    water_depth: float = 30000.0        # the demo's sea depth (demo.SEA_DEPTH)
    along: float = 1200000.0            # turbines 1.2 km apart along a row …
    across: float = 1500000.0           # … rows 1.5 km apart
    rows: int = 3
    cols: int = 3
    first: tuple = (1, 1)               # (row, col) of turbine A (the cable's first end goes up its J-tube)
    b_off: float = -42000.0             # turbine B (the next one along A's row) lies this far to port (+) / starboard (-)
    #                                     of the lay line: the rows run at a small angle to it
    substation: tuple = (0.5, 0.5)      # the substation's place in grid steps from turbine A (along, across)
    wind_from: float = 180.0            # compass in the park's frame (0 = +y): from starboard, so the rotors' planes
    #                                     lie along the lay line, never over the vessel
    rpm: float = 7.5                    # rotor speed in video time (the IEA turbine's rated 7.56)
    b_end: float = 45000.0              # planned: the second end is laid this far from turbine B's J-tube bell-mouth
    join_run: float = 1500.0            # the CAD piece runs this straight on the seabed before it meets the app's cable
