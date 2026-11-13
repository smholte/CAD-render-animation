# 0078 – Cable paths: one cable speed, the cable over rollers, sheaves and chutes, with a look that moves

**Who:** worker · **Status:** running (13 Nov 2026) · **Branch:** `ccr-6b47eb16-zabyzg` (the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's main goal: the cable-lay line; design in `tasks/0075-motion-paths-design.md`,
owner's answers at its end)
**Lane:** Flex parts (after 0058) – new files `core/paths.py` (no Blender), `blender/paths.py`, `blender/ops_paths.py`,
`blender/ui_paths.py` (4 Motion > **Cables and paths**, next to Hoses and drag chains), `blender/cable_looks.py` (the two
cable looks, registered into the materials list additively – do not rework `materials.py`), `tools/make_test_paths.py`,
`tests/test_paths*.py`; reuse `blender/flex.py` (shapes mesh, node tree pattern, Build hook) – small additive changes
there are fine (this lane). **Demo models lane** too: a new demo stage `cable` in `blender/demo.py`, the demo test.
Additive: `props.py`, `ui.py`, `animation.py` (the bake hook), `reimport.py`, `clash.py` HOOKS, `part_types_data.py`
(Sheave, Roller, Chute if missing), the tour, the PC check, the guide.
**Model:** **Fable · effort High**, split over subagents (CLAUDE.md "Subagents in a worker session") · **Place:** Claude
Code on the web, environment "CAD-render-animation"

## Design (worker, 13 Nov 2026 – the subagents' brief; keep it current)

Units everywhere: **metres, radians, world coordinates, Blender's axes (Z up)**; `core/` is NumPy only (float64, no
`bpy`, no SciPy, no Pillow). Angles shown to the user in degrees, lengths in mm, the cable speed in m/min.

### What a cable path is

A cable's centreline is a chain of **straight runs and circular arcs** that meet without a kink. Every arc lies on a
**wheel**: a circle (a point on its axis, the axis, the radius to the cable's *middle*, the side the cable goes round).
A wheel is a sheave (turns), a chute (a part, does not turn) or a **bend** (no single part carries it: the big bends of
a power cable over many small rollers). Between two wheels the cable runs straight, tangent to both. **Rollers** the
cable only rests on or runs past (a roller highway, V-cradle pairs, guide rollers along a bend) do not shape the path:
they are *touch contacts* that only turn. So one list of **contacts**, in order along the cable:

| Kind | Shapes the path | Turns | Its ratio |
| --- | --- | --- | --- |
| `SHEAVE` | arc, radius = groove bottom + cable radius | yes | 360 / (π · 2 · radius) ° per mm (the cable's middle) |
| `ROLLER` | no (touch) | yes | 360 / (π · 2 · surface) ° per mm (the cable's skin on the roller's surface) |
| `CHUTE` | arc on a part that is not round all the way (or the user says "does not turn") | no | – |
| `BEND` | arc as drawn in CAD, no part | no | – |

**Side** = +1 when the cable goes round the wheel turning about +axis (right hand), −1 about −axis:
`side = sign(((p − c) × t) · axis)` with p a point of the cable on the wheel, c the centre, t the cable's direction
(start → end). A wheel turned by the cable has angular velocity `ω = side · v / r` about +axis for the cable moving
start → end at speed v; the joint's coupling ratio takes the sign of `side · (axis · joint axis)` and of `reverse`.

**Ends.** `FIXED`: a point in a part's coordinates (the part the end touches; a free end: a point on the last
contact's carrier, `free` metres straight on). `WHEEL`: the cable starts on its first wheel at a fixed point of that
wheel's circle (a cable that comes off a drum: the drum is contact 0, the start does not turn with it).

**Moving.** Every wheel and end has a **carrier** (the object whose coordinates hold its centre/axis/point: a turning
part's joint arrow `joint.frame`, else the part itself, a bend: the cable part's parent). The path is solved from the
carriers' places; the result is stored **in the cable part's own coordinates** (so vessel motion and moving the whole
model cost nothing). Carriers that all move alike (`flex._movers`) → one shape, drawn once (`moving` off, no Scene
Time node). Else live while posing (a depsgraph handler, the flex pattern) and **Build** solves every frame into the
cable's shapes mesh (`frames × points`, the same number of points every frame: `core.paths.point_counts`).

**The cable speed** is a slide joint (value = metres paid out, no members, `allow_empty`, no limits): made by Add
cable ("Cable <name>") or taken (the demo's "Cable travel"). Turning contacts follow it (`joints.set_follows`, ratio in
° per mm). An app-made rotate joint is tagged `motion["fr_cable"] = <cable name>` (add `"fr_cable"` to
`joints.SPEC_TAGS`). A contact whose part already has a rotate joint on that axis keeps it: not yet following → the
app couples it (`coupled`); following the cable joint already → left alone, a ratio more than 0.5 % off the app's is
reported in `note`; following something else → left alone, `note` says so.

**The look moves by a driver, not by geometry** (prototype, web machine: a 32,000-point tube, 0 ms per frame, the
stripes in a Cycles render moved exactly by the paid-out length). The tube carries a point attribute
`fr_cable` (FLOAT_VECTOR) = (cos φ, sin φ, s): φ the angle round the cable, s the length along the path from its start
in metres. The cable part has two custom properties:
- `fr_cable_pay` (float): **paid-out metres × direction + `PAY_BIAS` (2.0)**, written by a simple-expression driver
  `a * k + 2.0` on the cable joint's `motion["fr_value"]` (k = +1, or −1 with `reverse`); never near 0 (the 5.2.3
  small-number driver bug). The material subtracts the bias.
- `fr_cable_look` (float array of 4): `[pitch m, starts, width share, kind]`, kind 1 = power cable, 2 = wire rope.
  `starts` (signed whole number) = how many stripes (strands) go round the cable; the sign is the hand.
A material reads them with Attribute nodes (GEOMETRY `fr_cable`, OBJECT `fr_cable_pay`, `fr_cable_look`):
`phase = (s − (pay − 2.0)) / pitch + starts · φ / 2π`; power cable: yellow where `fract(phase) < width`.
**Wire rope** (as L made it): its pitch is the lay length (one full turn of a strand), so
`phase = |starts| · (s − paid) / pitch + starts · φ / 2π`; `starts > 0` lets φ get smaller along a strand as s grows –
B checks which sign gives the usual right-hand lay with its φ and uses that (`look_values("ROPE", …)`: −6 for a
negative angle). A mark at s₀ when nothing is paid out is at s₀ + paid-out later. A part without `fr_cable` (length of (x, y) < 0.5)
shows the plain base (black / plain steel): the look may be given to a whole group.
The two looks are materials-library entries `cable_power` and `wire_rope` (spec key `cable`), built by a hook in
`materials.build_nodes` → `cable_looks.apply`. The cable's Look setting puts the cable *part* into the manual group
"Power cables" / "Wire ropes" with that material (the app's own grouping: paint schemes, fades keep working); Plain
takes it out again.

### Files and owners

| File | Owner | What |
| --- | --- | --- |
| `core/paths.py` + `tests/test_paths_core.py` | **A** | the path maths: solver, fixed point counts, reading a CAD centreline, the surface a cable rests on |
| `tools/make_test_paths.py`, `tests/data/test_paths_a.step` / `_b.step` (+ copies in `fresing_render/data/`), `tests/test_paths_model.py` | **C** | the test model (two revisions) and the test that its numbers are what its docstring says |
| `blender/cable_looks.py`, the two entries in `core/materials_lib.py`, the hook in `materials.build_nodes`, `tests/test_cable_looks.py` | **L** | the two looks |
| `blender/paths.py` + `tests/test_paths.py`; the `FRCable*` classes in `props.py`; small additive changes in `blender/flex.py` (helpers made usable from outside) | **B** | everything with bpy |
| `blender/ops_paths.py`, `blender/ui_paths.py`, `tools/ui_test_paths.py`, `tests/test_paths_panel.py` | **D** | operators, panel, tooltips, real-app test |
| `tests/test_paths_independent.py` + a written review | **E** | independent tests from the brief (wrote none of the code) |
| guide chapter + pictures | **F** | `docs/USER-GUIDE.md` "Cables and paths", `docs/img/` |
| `props.py` (rest), `ui.py`, `ui_motion.py`, `__init__.py`, `animation.py`, `states.py`, `reimport.py`, `joints.py`, `demo.py`, `tour.py`, `pccheck/`, CI lists, version, CHANGELOG, `TASKS.md`, CLAUDE.md | **worker** | |

### `core/paths.py` (A)

```python
@dataclass
class Wheel:
    centre: np.ndarray        # (3,) a point on the axis (any; the solver uses the plane through the cable)
    axis: np.ndarray          # (3,) unit
    radius: float             # axis -> the cable's middle
    side: int                 # +1 / -1 (above)

@dataclass
class Path:
    ok: bool; problem: str    # '' or a plain reason: "contact 3 lies behind contact 2", "contacts 4 and 5 overlap" …
    bad: int                  # index of the wheel the problem is about (-1: none)
    points: np.ndarray        # (n, 3) the polyline: start, per wheel its arc points (tangent-in … tangent-out), end
    s: np.ndarray             # (n,) length along the path from the start (exact arc lengths, not chord sums)
    first: np.ndarray         # (W,) index in points of each wheel's tangent-in point; its arc has counts[i] points
    wrap: np.ndarray          # (W,) rad >= 0
    length: float

def solve(start, wheels: list[Wheel], end, start_on_wheel=False, end_on_wheel=False,
          counts: list[int] | None = None, step: float = math.radians(4.0)) -> Path
    # start / end: (3,) points. *_on_wheel: the point lies on the first / last wheel's circle (projected on it)
    # and the arc starts / ends there (no straight run on that side). counts: points per arc (default: from step,
    # at least 2). No wheels: a straight line. Tangent points by alternating over the wheels (0075 B) until they
    # move < 1e-12 m: exact in a plane, and with a fleet angle. An arc whose in and out points are not in one plane
    # square to the axis is drawn as a helix on the wheel (angle and axial place linear).
    # Refuses (ok False, never a broken shape): a neighbour inside a wheel's circle, a wrap beyond 350°, a wheel
    # that would be passed on the wrong side with a wrap going backwards (> 180° where CAD had < 90° is fine –
    # only geometry that has no tangent), NaN.

def solve_frames(starts, centres, axes, radii, sides, ends, start_on_wheel=False, end_on_wheel=False,
                 counts=None) -> dict   # arrays over F frames: starts (F,3), centres (F,W,3), axes (F,W,3), radii (W,),
    # sides (W,), ends (F,3) -> {"points": (F,n,3), "s": (F,n), "wrap": (F,W), "ok": (F,), "problems": {frame: text},
    # "bad": (F,)}; vectorised over the frames (250 frames x 12 wheels well under 0.1 s)

def point_counts(wrap_max, step=math.radians(4.0), least=2) -> list[int]

def tightest(wheels, wrap, least_wrap=math.radians(1.0)) -> tuple[int, float]    # (index, radius) of the tightest bend

# ---- reading a CAD cable ----
@dataclass
class Round:                  # a round face axis of a part near the cable (from the mesh's fr_axes), world
    key: object               # whatever the caller wants back (object name, axis index)
    centre: np.ndarray; axis: np.ndarray
    verts: np.ndarray; tris: np.ndarray       # the part's mesh, world
    full: bool | None = None  # round all the way (may turn)? None: work it out (is_round)

@dataclass
class Contact:
    kind: str                 # "WRAP" | "TOUCH" | "BEND"
    key: object               # the Round's key (None for a BEND)
    centre: np.ndarray        # on the axis, in the plane of the cable there
    axis: np.ndarray
    radius: float             # WRAP: seat radius (surface + cable radius, from the mesh); BEND: fitted; TOUCH: axis -> centreline
    surface: float            # the part's surface radius where the cable touches (BEND: 0)
    side: int
    s: float                  # where along the centreline (the middle of the contact)
    wrap: float               # rad
    gap: float                # CAD centreline distance - (surface + cable radius): + drawn apart, - drawn into the part
    full: bool                # the part is round all the way

@dataclass
class Reading:
    ok: bool; problem: str
    contacts: list[Contact]   # in order along the centreline
    start: np.ndarray; end: np.ndarray
    start_on_wheel: bool; end_on_wheel: bool
    path: Path                # solve() of the WRAP and BEND contacts
    deviation: float          # the farthest the CAD centreline is from that path (m)

def read_cable(points, radius, rounds: list[Round], touch_tol=None) -> Reading
    # points: (n, 3) the CAD centreline (flex_fit.tube_centreline(...).points: equally spaced, facet noise ~0.1 mm,
    # possibly thousands of points for a 300 m cable). Cuts it into straights and arcs (curvature; least-squares
    # circles); an arc on a Round's axis (parallel within 2°, centres within tolerance, radius = seat ± tolerance)
    # is a WRAP on it (exact centre, axis and seat radius come from the part, not the fit); another arc is a BEND.
    # A Round whose axis the centreline passes at surface + cable radius (± touch_tol, default max(2 mm,
    # 0.25 x cable radius)), square to the axis within 20°, and that is no WRAP, is a TOUCH.
    # A stretch that is neither straight nor an arc (a spline, a helix): ok False with a plain reason.

def seat(verts, tris, centre, axis, at, rope_radius, search=None) -> tuple[float, float]
    # (place along the axis, radius axis -> cable middle) where a cable of rope_radius rests on the part near the
    # axial place ``at`` (m from centre along axis): the smallest radius it can sink to (groove bottom + rope
    # radius in a round groove, on both flanks in a V groove, surface + rope radius on a plain roller).
    # search: how far along the axis it may slide to find it (default rope_radius). 0.1 mm on 0075's sheave.

def surface_radius(verts, tris, centre, axis, at, width) -> float     # the part's outer radius near an axial place
def is_round(verts, centre, axis) -> bool        # the mesh is a body of revolution about this axis (all the way round)
def wheel_ratio(radius, side, axis, joint_axis, reverse=False) -> float   # degrees per mm of cable, signed
def stripes(diameter, pitch, angle) -> int       # starts: round(pi * d / (pitch * tan(angle))), 90 deg -> 0 (rings)
def stripe_angle(diameter, pitch, starts) -> float
```

**As made by A (differences from the above; B reads this):** `solve(..., held=None)` / `solve_frames(..., held=None)`:
`held=True` keeps every arc in the plane through its wheel's `centre` (use it for sheaves, bends and every cable whose
contacts move; a straight leaving that plane meets the arc with a kink of the fleet angle), `held=False` is the tight
string on cylinders (helix), `None` picks held unless a straight leaves a plane by more than 0.1°. `read_cable(points,
radius, rounds, touch_tol=None, fit_tol=None)` solves held. **`centreline(verts, tris, spacing=None)` → `flex_fit.Tube`
replaces `flex_fit.tube_centreline` for cables** (that one is 462 mm off on a 300 m cable; this one 0.15 mm, 2.7 s).
`Path.counts`; with `*_on_wheel` there is no separate end point (`points[0]` is the arc's first point). TOUCH only for
parts round all the way. **A roller's ratio is taken at `contact.radius − cable radius`** (where CAD drew the cable's
skin: matches the demo's joint sheet within 0.28 %; the part's own surface is up to 13 % off on the demo's waisted
rollers, which the maker draws the cable into). Demo cable: 14 bends, 218 touching rollers, read in 3.9 s (+1.8 s
centreline), path within 0.54 mm of the CAD centreline.

### `blender/cable_looks.py` (L)

```python
PAY = "fr_cable_pay"; LOOK = "fr_cable_look"; ATTR = "fr_cable"; PAY_BIAS = 2.0
KINDS = {"POWER": 1.0, "ROPE": 2.0}; MATERIALS = {"POWER": "cable_power", "ROPE": "wire_rope"}
def apply(b, bsdf, spec: dict, color, metallic, rough, normal) -> tuple   # called by materials.build_nodes when the
    # library entry has ``cable`` (dict: kind "POWER" | "ROPE", colours, defaults); returns (color, metallic, rough, normal)
def look_values(kind, diameter, pitch, angle, width) -> list[float]       # the 4 numbers of fr_cable_look
def pattern(kind, s, phi, paid_out, look) -> float                        # plain Python: what the nodes draw
    # (power: 1.0 = yellow, 0.0 = black; rope: the height 0 … 1 of the strand surface) – the tests compare renders with it
```
Power cable: black sheath (as `cable_black`), yellow stripes (RAL 1023-like), a slight raised edge is not needed.
Steel wire rope: 6 strands round the rope, each strand of wires laid the other way, galvanised grey, a little grease
dark in the valleys; bump from the strand height. Both in Cycles and EEVEE (shader nodes only, no image, no script).

### `blender/paths.py` (B) – what the others call

```python
TAG = "fr_cable"; MOD = "FR cable"; SHAPES = "FR cable shapes"       # + the cable's name
class PathError(RuntimeError)                                        # plain words for the owner
def items(scene); def active(scene); def find(scene, name); def index_of(scene, item); def label(item) -> str
def add_cable(scene, name="", joint="") -> item                      # joint: take this slide joint; '' = make "Cable <name>"
def read_cad(scene, item, part) -> list[str]                         # "From CAD cable": centreline, diameter, contacts, ends;
                                                                     # turns everything, draws the cable; notes for the report
def add_contact(scene, item, ob, hit=None) -> int                    # a clicked part joins the path (its place by the order along it)
def remove_contact(scene, item, index) -> None
def flip_contact(scene, item, index) -> None                         # the other side of the wheel
def set_end(scene, item, end: str, ob=None) -> None                  # end "A" | "B" on a part (None: free end)
def remove(scene, index) -> None                                     # the CAD shape shows again; app-made joints go, its couplings are released
def changed(scene, item); def contact_changed(scene, contact)        # a setting changed (props.py calls them)
def refresh(scene, force=False) -> None                              # live: solve for where the carriers are now
def bake(scene, anim) -> list[str]                                   # at the end of Build animation, after flex.bake
def after_clear(scene) -> None
def shape_now(scene, item) -> np.ndarray                             # (n, 3) world, the drawn centreline at the current frame
def wheels_now(scene, item) -> list                                  # core.paths.Wheel per shaping contact, world, now
def status(scene, item) -> tuple[str, str]                           # (text, "OK" | "WARN" | "ERROR")
def is_cable_joint(scene, j) -> bool
def cable_of_joint(scene, j)                                          # the cable item or None
def parts_of(scene, item) -> list                                    # the cable part (clash hook: left out, as flex parts)
def candidates(scene) -> list                                        # parts that look like a cable or wire rope and are no cable yet
def after_model_update(scene, by_uid, mapping) -> list[str]
def register(); def unregister()
def set_up_test_model(scene) -> dict                                 # test_paths_a.step: the cable read, the luff joint, an animation
```

### Test model (C) – `tools/make_test_paths.py out.step [A|B]`

`test_paths_a.step` (invented, every part one solid, mm, Z up; small file): a `BASE FRAME`; a `WINCH DRUM` (plain
barrel with flanges, axis along Y) on two bearing blocks; an `A-FRAME.ASM` hinged on the base about Y (the luff axis,
named so the test can make the joint) carrying `SHEAVE 1` at its top and `SHEAVE 2` lower on a cross beam – both
with a real round groove for the rope, each on its own pin; a `V CRADLE.ASM` (two plain `V ROLLER` solids at ±35–45°
on a stand) on the base; a `CHUTE` (a quarter-round trough, not a full revolve) at the end of the base; and
`WIRE ROPE` Ø 24 mm, one solid swept along lines and arcs: on the drum's barrel for a quarter turn or more → up to
sheave 1 (wrap) → down to sheave 2 (wrap the other way, so the two sides differ) → level over the V-cradle (resting in
the V, touching both rollers) → over the chute (arc on its trough) → straight on 0.5 m (free end). The rope touches
each surface exactly (gap 0). Revision B: one more part and the parts in another order (model-update test).
The maker's docstring lists every axis, radius (groove bottom, seat radius), tangent point, wrap angle and the rope's
length – the numbers the tests need.

## Goal

The owner sees his cable-lay spread work: one cable speed (m/min) moves a cable – power cable black with yellow angled
stripes, or a steel wire rope – visibly along its whole route over rollers, sheaves, guide wheels and chutes, and every
roller and sheave it touches turns at exactly the right speed. In the demo project ("Cable-lay vessel") the cable on the
roller highways and over the chute moves at 10 m/min. Tensioner tracks (0079), carousel/drum spooling (0080), the cable
into the sea (0081) and the quadrant operations (0082) build on this task, so its pieces must be reusable.

## Background (read)

- **0075** sections A (the cable and its speed), F (one speed drives it all) and the summary (points 1–3): the cable is a
  **virtual slide joint** (value = metres paid out; `joints.create(..., allow_empty=True)`), animated by the existing
  Motor / Joint steps; rollers and sheaves are **followers** with ratio 360/(π·D_contact) °/mm (`RATIO_UNITS[("SLIDE",
  "ROTATE")]`); the rope marks move by **simple-expression drivers** on the same joint (scripts off, queue, any fps);
  shapes that change per frame (a sheave on a part that moves) are **baked at Build** and picked per frame by Geometry
  Nodes – live only while posing. The groove is read from the mesh's radial profile (groove bottom + rope radius, 0.1 mm
  in 0075's test; no cache change).
- **0058** (done, 0.2.78) built exactly that mechanism for hoses: one `FR flex shapes` mesh, a `FR flex` modifier that
  replaces a part's CAD geometry by the app-made tube, live handler, `flex.bake` at the end of Build, model update by
  part IDs, clash HOOKS. Read its Design section and `blender/flex.py`; **reuse, do not copy** (a shared helper module is
  fine if both need it). Its report's "Ideas for later": "a rope is a polyline with a tube like a hose".
- **Owner's answers (0075 end):** cable Ø 50–500 mm; speed in **m/min**, lay speed about **10 m/min**; real grooves in his
  sheaves; looks: **steel wire rope** = the typical winch-wire look; **power cable** = **black with yellow angled stripes**;
  **the texture must visibly move along the path**.
- **Demo (0077, 0084, 0091, 0095, 0097):** `demo.py` has the slide joint **"Cable travel"** (m paid out towards the sea)
  that every cable-turned roller already follows (joint sheet `"by": "cable"`, `deg_per_mm` from the contact radius); the
  cable is one static CAD solid `CABLE` along the main route (`demo_model/layout.py`, `route_solid`), diameter, MBR and
  bend radius in the route sheet (`layout.py` "cable"). The demo test leaves the static cable out of its clash check
  (0097: drop that once the cable rests on its rollers). The A&R and tipping wires (0095) are demo-only drivers and
  constraints – not an app function.
- The owner draws cables in his Inventor models too (a swept solid along the route): **reading a CAD cable** is the
  main way in for him; clicking contacts one by one is the fallback.
- Repository public: invented models only; never the Fresing 400 or the employer's work (CLAUDE.md section 6).

## Scope

1. **Cable item** (4 Motion > Cables and paths > **Add cable**): name, diameter (read from the CAD cable or the first
   groove, can be typed), look (Power cable / Steel wire rope / Plain), stripe or lay pitch, MBR (minimum bend radius,
   warn when a path bends tighter). Makes (or takes – the demo's "Cable travel") its virtual slide joint. A Motor step on
   a cable joint shows and takes the speed in **m/min**.
2. **Path from a CAD cable** (**From CAD cable**: pick the solid): centreline with 0058's `flex_fit`, then find the round
   parts it touches (rollers, sheaves, guide wheels, V-cradle pairs, chutes as fixed bends) and fit the path to them:
   straight runs between tangent points, arcs on each wheel on the right side (the side the cable lies on), the groove
   radius from the mesh. The list under the panel shows each contact (name, Ø at the rope centre, wrap angle, side) and
   lets the owner remove, add (click a part – the hover highlight of 0088), flip the side. A cable start and end: a part
   (fixed point) or "free end" (straight on for a set length – the sea's catenary is 0081, the coil 0080).
3. **Everything it touches turns:** each contact without a joint gets an app-made rotate joint on its axis (tagged, like
   0064's) following the cable at 360/(π·D_contact); a contact with an existing joint gets the coupling (the demo's
   followers stay as they are when their ratio is already right – check, report differences).
4. **The cable drawn on the path:** the CAD cable part's geometry replaced by the app-made tube (0058's way: visibility,
   paint schemes, fades, hide-with-subassembly keep working; item off → the CAD shape). Paths whose contacts all stay put
   are drawn once (no per-frame cost); contacts that move against each other (a sheave on the tilting quadrant handler, a
   luffing A-frame) → solved per frame at Build into the shapes mesh, live while posing.
5. **Looks that move** (`cable_looks.py`): power cable black, yellow stripes at an angle (pitch and angle settable), steel
   wire rope (strands with their lay, metallic); the pattern runs along the cable by the paid-out length through a
   simple-expression driver (UV along the length in metres) – exact at any fps, in Cycles and EEVEE, scripts off, queue.
6. **Clash:** a cable resting on its contacts gives no rows against them (HOOKS, as 0058).
7. **Demo stage `cable`** (after `joints`): the demo's `CABLE` becomes a cable path over its rollers and chute, power-cable
   look, on "Cable travel"; the roller-highways shot (4) shows it moving at 10 m/min with the rollers turning; the static
   cable's clash leave-out dropped where the check is clean. Optional if cheap: the A&R and tipping wires (0095) become
   app cable paths with the steel-wire look (else an open point for 0082).
8. Tour stop "Cable over sheaves" (new test model `tools/make_test_paths.py` → `test_paths.step`: a drum, an A-frame with a
   luff joint and 2 sheaves, a V-roller cradle, a chute, a CAD cable swept along them; invented), PC-check line
   `motion.paths`, guide chapter "Cables and paths" with pictures, model update keeps paths, old projects open.

## Accuracy and speed (tests)

- Cable centre on the groove's rope circle within 0.5 mm; no kinks: direction change at every tangent point < 0.1°.
- Every turned contact's surface speed = cable speed within 0.1 % (over a 100 m Motor step); texture offset = paid-out
  length within 1 mm at frame 1,000.
- Bend tighter than MBR → a warning naming the contact; impossible paths (contacts in a line that cannot be wrapped,
  a contact behind another) → a plain refusal, never a broken shape.
- Cost per frame on the demo vessel (1,250 parts) with the cable on: static path ≤ +1 ms; with moving contacts the
  0058 budget (≤ +5 ms). Build time of the demo with the stage: say before/after (0.2.71: 90 s).

## Split with subagents (the worker fixes the interfaces first, writes them under "Design" here, then spawns ≤ 3)

Suggested: **A** `core/paths.py` + tests (tangent runs, wraps, chute arcs, contacts from a centreline, groove profile);
**B** `blender/paths.py` + `cable_looks.py` (items, joints/couplings, the tube via 0058's mechanism, drivers, bake,
model update); **C** test model + **independent tests written from this brief** (did not write A/B); later **D** panel +
operators + real-app test, **F** guide and pictures (Sonnet). The worker owns the shared files, the demo stage, the tour,
the PC check, version, CHANGELOG, `TASKS.md`.

## Done when

- [ ] Scope 1–8 work in the real app (screenshot of the panel checked), every button with a tooltip.
- [ ] The tests above pass; independent tests and a written review (C) in the report.
- [ ] Demo: Help > Make demo project shows the moving cable in shot 4 (and the chute), 0 clash rows in shot 7, time
      measured; a Cycles still of the stripes on the rollers in `tasks/img/` (invented model only).
- [ ] Guide chapter, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

Tensioner tracks and pads (0079), carousel/drum spooling incl. spiral groove and Lebus (0080), the catenary into the sea,
water clarity, CPS (0081), quadrant operations (0082), cable stiffness / dynamics, fleet angle on the drum (0080), motion
blur of moving shapes (study #6), the web 3D export of cables (0099 leaves app-made objects out).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Fable, effort High; 4 cores, no graphics card), 13 Nov 2026, branch
`ccr-6b47eb16-zabyzg` (the web session's branch). Released as **0.2.80**.

**What changed:**
- **4 Motion > Cables and paths** (`ui_paths.py`, `ops_paths.py`): Add cable (from the selected part, or a click picker
  with the hover highlight), Add all found by name, the list of cables, the status line, Cable speed + "Add a Run motor
  step", Look (Power cable: stripe distance / angle / width; Steel wire rope: lay length; Plain), From CAD cable again,
  **What it touches** (kind, Ø, wrap, side, Turns with the cable; Add by a click, Remove, Flip side), start / end on a
  part or free, and under More: Diameter, Min. bend (MBR), free lengths, Runs the other way, Stays as drawn. Tooltips on
  everything (668 items, 0 missing).
- **How it works** (Design above; `blender/paths.py`): a cable = its CAD part + a slide joint whose value is the metres
  paid out + the contacts in order (sheave / roller / chute / bend). The CAD part gets a Geometry Nodes modifier that
  draws the cable through the points of its own hidden mesh (in the part's own coordinates, so vessel motion costs
  nothing). Rollers and sheaves follow the cable joint with 360/(π·D) ° per mm; joints they already had are kept. A
  cable whose contacts all stand still is drawn once; contacts that move against each other: live while posing, every
  frame at Build (in the same pass through the frames as the hoses). Hooks: `animation.bake` / `clear_keys`, poses,
  model update, the clash hook (a drawn cable is left out, as hoses are).
- **A Run motor step on a cable's joint takes m/min** (`FRAnimBlock.speed_mmin`, kept as mm/s; old projects unchanged).
- **The path maths** (`core/paths.py`, no Blender): the tight string over wheels (closed-form tangents, alternated;
  arcs held in their wheel's plane; a wheel the cable leaves is "lifted", never a loop), the same over all frames at
  once, reading a CAD cable (long tubes read in pieces; straights and arcs; an arc on a round part = a wrap, another
  arc = a bend, rollers it rests on = touch), the seat of a cable in a groove from the mesh, "round all the way".
- **Two looks that move** (`cable_looks.py`, materials `cable_power` and `wire_rope`): shader nodes reading the tube's
  attribute (angle round the cable, length along it) and the paid-out length from a simple-expression driver on the
  cable part – no geometry changes per frame, works with scripts off, in the queue, Cycles and EEVEE.
- **Demo project:** stage `cable` (after `joints`): the vessel's `CABLE` on its path on "Cable travel" – 218 rollers
  (all with their own joints from the sheet, none changed), 12 bends, 2 chutes, Ø 200, 188.06 m; shot 4 is now real
  time: a Run motor step at 10 m/min. The clash test no longer leaves the cable out by hand. Stills:
  `tasks/img/0078_cable_on_rollers.jpg`, `tasks/img/0078_cable_round_a_bend.jpg` (Cycles, processor).
- **Test model** `test_paths_a.step` / `_b` (`tools/make_test_paths.py`: winch drum, luffing A-frame with two grooved
  sheaves, V-roller cradle, chute, wire rope Ø 24; invented). Tour stop "Cable over sheaves and rollers" (set
  `cables`), PC-check line `motion.paths`, guide chapter "Cables and paths" with four pictures, CLAUDE.md (files, five
  lessons, two subagent rules).
- **Fixed on the way:** a joint that moves nothing (the demo's "Cable travel") was dropped by a model update with every
  coupling to it (`joints.rebuild_from_specs`).

**Subagents** (all in their own worktree, merged by the worker): **A** the path maths (2 rounds), **C** the test model,
**L** the two looks, **B** the Blender side (2 rounds), **D** panel + operators + real-app test (continued after a
container restart), **E** independent tests and review of the path maths (wrote none of it), **F** the guide chapter
and its pictures (Sonnet). The worker: design, settings, hooks, `joints.py`, demo stage, tour, PC check, the panel
picture, merging, release. Re-done after E's review (by A): the centreline of a cable that turns back over a sheave
(the task's own test rope could not be read), lift-off instead of loops, round parts with a hole or flat, thin clean
ropes refused, readings centimetres off accepted; then B: lift-off warnings, loop warnings, quieter ratio notes, a
sheave dragged by hand, one pass through the frames with the hoses.

**Tested and measured** (web machine, 4 cores, no graphics card, bpy module unless said):
- Tests: `test_paths_core.py` 95, `test_paths_independent.py` 106 (E), `test_paths_model.py` 14, `test_cable_looks.py`
  20, `test_paths.py` 37, `test_paths_panel.py` 12, real-app `ui_test_paths.py` 36 checks (real clicks, undo/redo, save
  + open), the tour stop, the PC-check line, the demo's cable test.
- **Accuracy, test model:** the drawn cable's middle on the seat circles to 0.15 mm (limit 0.5); direction change at
  tangent points 0.0000° (limit 0.1°); seat radii from the meshes +0.09 mm (sheaves) / +0.15 mm (chute); wraps within
  0.03°; length 7,022.85 mm against the maker's 7,022.21. Luffing −15…+15°, built: within 0.15 mm at every 5th frame;
  live and built agree to 0.0000 mm; frames in any order identical.
- **Speed of what turns:** 100 m at 10 m/min: every rim ran 100 m within 0.1 %, right sign; the look's offset = the
  joint's value within 1 mm at frame 1,000 (render test: 0.16 mm); every driver a simple expression.
- **The looks in a Cycles render:** stripe edges within 0.34 mm (0.17 px) of the formula at three paid-out lengths; no
  seam; rope crowns 4.4 × brighter than its valleys; EEVEE the same picture.
- **Cost per frame:** test model + 1,000 parts: still cable +0.01 ms, moving +0.5 ms. Demo vessel (1,261 parts):
  3.62 ms with the cable drawn against 3.61 ms with its modifier off, 0 re-evaluations of the cable.
- **Demo:** `read_cad` 2.6–3.4 s (Draft), 5.6 s (Normal); the drawn cable at most 1.0 mm (Draft) / 0.55 mm (Normal)
  off the CAD centreline; roller ratios against the sheet's joints: at Normal all within 0.28 %, at Draft 81 between
  0.5 and 1.1 % (facet noise; one summary note). Small form built in 62 s in all (model 38, import 9, joints 1.3,
  **cable 3.4**, Build 5.1). The brief's "before" (0.2.71: 90 s) was the full form on another day; the full form was
  not timed again. `test_no_clash_in_the_animation`: 0 rows without the cable's leave-out.
- **Path maths alone:** 250 frames × 12 wheels 7 ms (54 ms with every axis askew); a 300 m cable (137,000 triangles)
  read in 2.7 s + 0.8 s; the demo's cable: 14 arcs, radii within 0.11 %.
- **Independent review (E):** 11 findings; 1–5, 7, 9 and the small ones fixed by A, 2 and 10 handled on the Blender
  side (lift-off and loop warnings). Left as they are: `held=None` switching at 0.1° (the app always passes held),
  free mode with centres moved along their axes, the touch tolerance (the demo's rollers need 0.155 × radius).
- GitHub runs: see "Runs" below.

**Open points / follow-up tasks:**
- **For the owner's PC:** the cable in the real view while dragging a joint; a GPU render of the demo's shot 4; one of
  his own CAD cables (Inventor sweep along lines, arcs – a spline stretch is refused with the reason).
- **The demo's cable stays as drawn** (`still`): its turn round the D-quadrant's gutter would travel with the quadrant
  in shot 7; 0082 decides. The A&R and tipping wires are still the demo's own drivers (not app cables): 0082.
- A cable whose route has a helix or spline stretch is refused (lines and arcs only). The rope's relief is a bump (round
  outline). A fleet angle shows as a kink of that angle where the cable meets a sheave (arcs stay in the sheave's plane).
- While posing, a sheave jumped far beyond the cable in one step draws a loop with the "check its side" warning
  instead of "lifted off" (dragging through, or Build, is right). A sheave with a drawn wrap over 180° that lifted off
  and returns in one jump stays "lifted" until anything re-solves the cable.
- Renaming a cable leaves its joint and hidden mesh under the old name (works; cosmetic). A start made free by the
  user is read from CAD again at "From CAD cable again". The panel cannot take an existing slide joint as the cable's
  speed yet (the demo does it by script): a small addition for 0079.
- One of six local real-app runs printed "Python context internal state bug" lines after the second import (36/36
  still; not reproduced). Not tested: Windows beyond GitHub's install run, the real render queue runner with a cable
  (a queue copy is: open, build, render – the drivers and shapes are in the file), two scenes in one file.
- No Heavy PC-check line (the cost does not grow with the model: +0.0 ms on the demo vessel).
- Branches the owner can delete on github.com: `ccr-6b47eb16-zabyzg`.
