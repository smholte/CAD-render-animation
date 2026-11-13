"""One parameter set for the whole demo model (tasks 0076, 0084). Millimetres; x towards the bow, y to port, z up.

The stern (transom) is at x = 0, the bow at x = L; the waterline is z = 0 (the app's sea). The cable is laid towards
the stern. Change ``cable_d`` (50 … 500 mm): the minimum bend radius, every bend of the route, the lanes, the sheaves
on it, the carousel core, the tensioner opening and the pads' squeeze follow.

Deck layout (task 0084, as the owner works): two side lanes of raised roller highways – side A on starboard (y < 0),
side B on port (y > 0) – and the quadrant's middle lane with rails between them; a lower path beside and 1–1.5 m below
side A's highway. Task 0102: the side lanes' cable lines lie on the D-quadrant's curve (y = +- its radius): the cable runs
straight from the two tensioners round the D's gutter, one smooth U, no S-bends; the D travels aft between the
tensioners with its sides passing through their lines (they open: lift, then tilt outboard). The cable makes an oval:
coil -> arch -> down the tower -> lower path aft -> stern turn (180°) ->
forward on side B through tensioner 1 -> round the quadrant (180°) -> aft on side A through tensioner 2 -> horn A.
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
    carousel_x: float = 60000.0
    carousel_d: float = 24000.0     # outer Ø
    rim_h: float = 5000.0
    turntable_t: float = 400.0
    coil_layers: int = 15           # full flat layers of cable in the carousel (the top layer is partly paid out)
    coil_r: float = 8000.0          # radius where the cable leaves the coil (the arch's guide, rest pose)

    # cable line
    low_h: float = 800.0            # lower path: cable centre above the deck (more for a thick cable)
    arch_h: float = 14000.0         # cable centre over the top of the loading arch (above the waterline)
    lower_off: float = 2500.0       # the lower path lies this much outboard of side A's highway (clear of tensioner 2)
    chute_drop_x: float = -1500.0   # where the cable leaves horn A vertically (aft of the transom)
    sea_end_z: float = -1500.0      # the route ends here, under water

    # quadrant handler (hinged at the transom)
    hinge_x: float = 600.0

    # tensioner
    pad_pitch: float = 300.0
    sprocket_teeth: int = 8
    links_per_run: int = 14         # gripping run between the sprockets: 14 x 300 = 4.2 m (pads per track 2 x 14 + 8)
    pad_v_deg: float = 160.0        # the pads' V (included angle)

    # roller spacing on the straights
    roller_step: float = 1500.0

    # Lebus drum
    lebus_crossover_deg: float = 35.0

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
        # the arch's hanging guide (a bend radius out from where the cable lifts off) must stay inside the rim
        self.carousel_d = max(self.carousel_d, 2.0 * (core + 3000.0 + self.bend_r + 700.0))
        self.coil_r = core + 0.5 * (self.carousel_d / 2.0 - 300.0 - core)
        # the lanes and the lower path must fit the beam (a thick cable widens the vessel)
        self.beam = max(self.beam, 2.0 * (self.lane_y + self.lower_off + 2300.0), self.carousel_d + 3000.0)

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
    def quadrant_r(self) -> float:
        """The D-quadrant's curve: the cable's centre radius round it."""
        return self.bend_r

    @property
    def lane_y(self) -> float:
        """Side lanes' cable lines at y = -lane_y (side A, starboard) and +lane_y (side B, port): on the D-quadrant's
        curve (task 0102), so the cable runs straight from the lanes round the D's gutter."""
        return self.quadrant_r

    @property
    def low_z(self) -> float:
        """Lower path (and the stern turn under the rails): cable centre."""
        return self.deck_z + self.low_h + max(0.0, self.cable_r - 100.0)

    @property
    def rail_z(self) -> float:
        """Top of the quadrant's rails: the rail girders bridge the stern turn's cable."""
        return self.low_z + self.cable_r + 50.0 + 450.0

    @property
    def line_z(self) -> float:
        """Side lanes' highways (and the cable round the quadrant): cable centre."""
        return self.rail_z + 350.0 + 300.0 + self.cable_r

    @property
    def line_h(self) -> float:
        return self.line_z - self.deck_z

    @property
    def coil_top_z(self) -> float:
        """Top of the full layers (the top layer, partly paid out, lies on it)."""
        return self.turntable_t + self.coil_layers * self.cable_d

    @property
    def pad_v_half_angle(self) -> float:
        """Half the pads' V-groove angle (80° for a 160° V)."""
        return math.radians(self.pad_v_deg / 2.0)

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
