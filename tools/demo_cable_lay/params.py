"""One parameter set for the whole demo model (task 0076). Millimetres; x towards the bow, y to port, z up.

The stern (transom) is at x = 0, the bow at x = L; the waterline is z = 0 (the app's sea). The cable is laid towards
the stern (-x). Change ``cable_d`` (50 … 500 mm): the minimum bend radius, every bend of the route, the sheaves on it,
the carousel core, the tensioner opening and the pads' squeeze follow.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

MBR_PER_D = 17.5            # minimum bend radius / cable Ø (3.5 m at Ø200; a usual figure for power cables)
BEND_MARGIN = 1.15          # every bend of the route lies this much above the MBR


def up50(v: float) -> float:
    """Round up to the next 50 mm."""
    return 50.0 * math.ceil(v / 50.0 - 1e-9)


@dataclass
class Params:
    cable_d: float = 200.0          # power cable Ø (50 … 500)
    mbr: float = 0.0                # minimum bend radius; 0 = MBR_PER_D x cable_d

    # vessel
    length: float = 120000.0
    beam: float = 27000.0
    deck_z: float = 3000.0          # freeboard 3 m
    keel_z: float = -6000.0

    # carousel (on the vessel, in its well amidships)
    carousel_x: float = 66000.0
    carousel_d: float = 24000.0     # outer Ø
    rim_h: float = 5000.0
    turntable_t: float = 400.0
    coil_h: float = 3200.0          # stored cable height on the turntable
    coil_r: float = 8000.0          # radius where the cable leaves the coil (loading arm's guide, rest pose)

    # cable line
    line_h: float = 1800.0          # cable centre above the deck through the tensioners
    arm_h: float = 14000.0          # cable centre along the loading arm (above the waterline)
    tower_x: float = 45000.0        # loading tower's slewing axis (moved forward when the bends need it)
    tensioner_x: tuple = (30500.0, 20500.0)   # at least here; further forward when the chute needs room
    chute_drop_x: float = -1500.0   # where the cable leaves the chute vertically (aft of the transom)
    sea_end_z: float = -1500.0      # the route ends here, under water

    # quadrant lane (starboard)
    quadrant_y: float = -7000.0
    quadrant_hinge: tuple = (-400.0, 1000.0)     # hinge (x, z): on brackets at the transom

    # tensioner
    pad_pitch: float = 300.0
    sprocket_teeth: int = 8
    links_per_run: int = 20         # straight run between the sprockets (pads per track = 2 x this + teeth)

    # wire ropes
    handling_rope_d: float = 48.0
    quadrant_rope_d: float = 56.0
    tipping_rope_d: float = 36.0

    extras: dict = field(default_factory=dict)

    def __post_init__(self):
        if not 50.0 <= self.cable_d <= 500.0:
            raise ValueError("cable Ø must be 50 … 500 mm")
        if self.mbr <= 0:
            self.mbr = MBR_PER_D * self.cable_d
        # a big cable needs a bigger carousel core: grow the carousel so the coil keeps its width
        core = self.core_r
        if self.carousel_d / 2.0 - core < 3000.0:
            self.carousel_d = 2.0 * (core + 3000.0)
        self.coil_r = core + 0.5 * (self.carousel_d / 2.0 - 300.0 - core)

    # ---- what follows ---------------------------------------------------------------------------------
    @property
    def cable_r(self) -> float:
        return self.cable_d / 2.0

    @property
    def bend_r(self) -> float:
        """Radius of every bend of the cable route (at least the MBR)."""
        return up50(self.mbr * BEND_MARGIN)

    @property
    def core_r(self) -> float:
        """Carousel inner core: its Ø is at least 2 x MBR (the innermost turn of the coil)."""
        return up50(max(4000.0, self.mbr + 500.0))

    @property
    def line_z(self) -> float:
        return self.deck_z + self.line_h

    @property
    def coil_top_z(self) -> float:
        return self.turntable_t + self.coil_h

    @property
    def pad_v_half_angle(self) -> float:
        """The pads' V-groove: 120° included, so the cable's centre is r / sin(60°) above the V's bottom."""
        return math.radians(60.0)

    def squeeze_h(self, d: float | None = None) -> float:
        """Height of the cable centre above the bottom of a pad's V-groove, for cable Ø d."""
        return (self.cable_r if d is None else d / 2.0) / math.sin(self.pad_v_half_angle)

    @property
    def sprocket_r(self) -> float:
        return self.pad_pitch / (2.0 * math.sin(math.pi / self.sprocket_teeth))

    @property
    def pads_per_track(self) -> int:
        return 2 * self.links_per_run + self.sprocket_teeth

    @property
    def chute_r(self) -> float:
        return self.bend_r

    @property
    def quadrant_r(self) -> float:
        return self.bend_r
