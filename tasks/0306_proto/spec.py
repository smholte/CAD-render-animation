"""Study 0306 – the two invented test vehicles: sizes, masses, springs and suspension hard points. No Blender.

Shared by the STEP maker (``make_vehicles.py``), the suspension kinematics (``kin.py``) and the ride solve
(``ride.py``). Everything is invented and generic (no real make or model).

Vehicle frame: x forward, y left, z up, metres in the solve (the STEP is in mm: ``mm()``). Origin on the ground,
under the middle of the FRONT axle, in the CAD pose (the vehicle standing at its design ride height, laden as
given by ``mass``). Hard points are given for the LEFT side (y > 0); the right side is the mirror (y -> -y).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Axle:
    name: str
    x: float                     # m, axle line (front axle 0, rear axles negative)
    track: float                 # m, wheel-centre to wheel-centre (twin tyres: the middle of the pair)
    kind: str                    # DOUBLE_WISHBONE / MACPHERSON / TRAILING_ARM / SOLID_LEAF / SOLID_COIL / MULTILINK
    steered: bool
    wheel_r: float               # m, loaded radius of the tyre
    tyre_w: float                # m, tyre width
    rim_r: float                 # m
    twin: bool = False           # twin tyres on each side
    unsprung: float = 50.0       # kg per side (a solid axle: half the axle)
    k_spring: float = 30e3       # N/m at the wheel (wheel rate)
    c_damp: float = 3.0e3        # N s/m at the wheel
    k_tyre: float = 250e3        # N/m per side
    k_arb: float = 0.0           # N/m anti-roll bar, at the wheel (left-right difference)
    travel: tuple = (-0.09, 0.09)  # m, wheel travel rebound / bump from the CAD pose (bump stops)
    # hard points of the LEFT side, (x, y, z) in m, vehicle frame – see each kind below
    points: dict = field(default_factory=dict)


@dataclass
class Vehicle:
    name: str
    mass: float                  # kg, whole vehicle
    cog_h: float                 # m, centre of mass height above the ground
    i_pitch: float               # kg m^2 sprung mass about y
    i_roll: float                # kg m^2 sprung mass about x
    axles: list
    max_steer: float             # rad, inner wheel at full lock
    a_lat: float                 # m/s^2 comfortable lateral acceleration (speed profile)
    a_acc: float                 # m/s^2 accelerating
    a_brake: float               # m/s^2 braking
    v_max: float                 # m/s
    body: dict = field(default_factory=dict)   # outline for the maker: length, width, height, overhangs

    @property
    def wheelbase(self) -> float:
        xs = [a.x for a in self.axles]
        steer = [a.x for a in self.axles if a.steered]
        rear = [a.x for a in self.axles if not a.steered]
        return (sum(steer) / len(steer)) - (sum(rear) / len(rear)) if steer and rear else max(xs) - min(xs)

    @property
    def rear_x(self) -> float:
        """The x of the turning centre's line (the middle of the unsteered axles)."""
        rear = [a.x for a in self.axles if not a.steered]
        return sum(rear) / len(rear)

    @property
    def sprung(self) -> float:
        return self.mass - sum(2 * a.unsprung for a in self.axles)

    @property
    def min_radius(self) -> float:
        """Turning radius of the rear axle's middle at full lock (outer wheels a little more)."""
        import math
        a = self.axles[0]
        # inner wheel at max_steer: R_in = L / tan(d); the middle lies track/2 further out
        return self.wheelbase / math.tan(self.max_steer) + a.track / 2


def mm(v):
    """Metres -> millimetres for the STEP maker."""
    if isinstance(v, (tuple, list)):
        return tuple(1000.0 * x for x in v)
    return 1000.0 * v


# ---------------------------------------------------------------------------------------------------------------
# Test car: an invented mid-size SUV. Front double wishbone (steered), rear trailing arm.
# ---------------------------------------------------------------------------------------------------------------
#
# DOUBLE_WISHBONE points (left side, front view at the axle; x = 0 except the steering points):
#   wheel        wheel centre
#   lca_in_f, lca_in_r   lower arm's two inner pivots on the body (front / rear bush)
#   lca_out      lower ball joint (on the upright)
#   uca_in_f, uca_in_r   upper arm's inner pivots
#   uca_out      upper ball joint
#   spring_low   coil-over's lower eye (on the lower arm)
#   spring_top   coil-over's top mount (on the body)
#   tie_in       tie rod's inner end (on the steering rack)
#   tie_out      tie rod's outer end (on the upright's steering arm)
# TRAILING_ARM points (left side, side view):
#   wheel, arm_pivot (on the body; the arm turns about y), spring_low (on the arm), spring_top (body)

CAR = Vehicle(
    name="Test car",
    mass=1850.0, cog_h=0.62, i_pitch=2600.0, i_roll=650.0,
    max_steer=0.62,               # 35.5 deg inner wheel
    a_lat=3.0, a_acc=2.0, a_brake=3.5, v_max=25.0,
    body=dict(front=0.95, rear=1.05, width=1.90, height=1.70, floor=0.42, roof=1.70),
    axles=[
        Axle("Front", x=0.0, track=1.62, kind="DOUBLE_WISHBONE", steered=True,
             wheel_r=0.36, tyre_w=0.235, rim_r=0.24, unsprung=48.0,
             k_spring=32e3, c_damp=3.4e3, k_tyre=260e3, k_arb=12e3, travel=(-0.09, 0.08),
             points=dict(
                 wheel=(0.0, 0.81, 0.36),
                 lca_in_f=(0.18, 0.36, 0.20), lca_in_r=(-0.20, 0.36, 0.20), lca_out=(0.0, 0.72, 0.17),
                 uca_in_f=(0.12, 0.47, 0.55), uca_in_r=(-0.12, 0.47, 0.55), uca_out=(0.0, 0.69, 0.56),
                 spring_low=(0.0, 0.60, 0.20), spring_top=(0.0, 0.55, 0.78),
                 tie_in=(-0.14, 0.38, 0.30), tie_out=(-0.14, 0.70, 0.30),
             )),
        Axle("Rear", x=-2.85, track=1.62, kind="TRAILING_ARM", steered=False,
             wheel_r=0.36, tyre_w=0.235, rim_r=0.24, unsprung=45.0,
             k_spring=36e3, c_damp=3.2e3, k_tyre=260e3, k_arb=6e3, travel=(-0.10, 0.09),
             points=dict(
                 wheel=(-2.85, 0.81, 0.36),
                 arm_pivot=(-2.40, 0.70, 0.40),
                 spring_low=(-2.70, 0.56, 0.36), spring_top=(-2.70, 0.56, 0.72),
             )),
    ],
)

# ---------------------------------------------------------------------------------------------------------------
# Test truck: an invented 2-axle rigid truck, ~18 t. Solid axles on leaf springs; twin tyres at the rear.
# ---------------------------------------------------------------------------------------------------------------
#
# SOLID_LEAF points (left side):
#   wheel        wheel centre (twin: middle of the pair)
#   kingpin      a point on the kingpin axis at wheel-centre height (steered axle only)
#   leaf_front   front eye of the leaf (pin on the frame bracket)
#   leaf_rear    rear eye (on the shackle)
#   shackle_top  the shackle's pin on the frame
#   leaf_seat    where the axle sits on the leaf (U-bolts)

TRUCK = Vehicle(
    name="Test truck",
    mass=18000.0, cog_h=1.45, i_pitch=95000.0, i_roll=14000.0,
    max_steer=0.70,               # 40 deg inner wheel
    a_lat=1.8, a_acc=0.8, a_brake=2.5, v_max=22.0,
    body=dict(front=1.45, rear=2.40, width=2.50, height=3.70, frame_h=1.05, frame_w=0.86,
              cab_len=2.20, box_len=6.40),
    axles=[
        Axle("Front", x=0.0, track=2.05, kind="SOLID_LEAF", steered=True,
             wheel_r=0.52, tyre_w=0.385, rim_r=0.29, unsprung=420.0,
             k_spring=300e3, c_damp=18e3, k_tyre=1.0e6, k_arb=0.0, travel=(-0.10, 0.09),
             points=dict(
                 wheel=(0.0, 1.025, 0.52), kingpin=(0.0, 0.88, 0.52),
                 leaf_front=(0.80, 0.43, 0.86), leaf_rear=(-0.80, 0.43, 0.86), shackle_top=(-0.80, 0.43, 1.00),
                 leaf_seat=(0.0, 0.43, 0.66),
             )),
        Axle("Rear", x=-4.80, track=1.82, kind="SOLID_LEAF", steered=False,
             wheel_r=0.52, tyre_w=0.315, rim_r=0.29, twin=True, unsprung=650.0,
             k_spring=650e3, c_damp=30e3, k_tyre=2.0e6, k_arb=0.0, travel=(-0.10, 0.10),
             points=dict(
                 wheel=(-4.80, 0.91, 0.52),
                 leaf_front=(-3.95, 0.43, 0.86), leaf_rear=(-5.65, 0.43, 0.86), shackle_top=(-5.65, 0.43, 1.00),
                 leaf_seat=(-4.80, 0.43, 0.68),
             )),
    ],
)

VEHICLES = {"car": CAR, "truck": TRUCK}
