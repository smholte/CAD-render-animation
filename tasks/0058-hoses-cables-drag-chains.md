# 0058 – Hoses, cables and drag chains that follow the motion

**Who:** worker · **Status:** running (12 Nov; split over subagents, see below) · **Branch:**
`claude/sleepy-mccarthy-3zpzfu` (the web session's branch)
**Started by:** lead chat, 9 Nov 2026 (owner's priority 1 of the big features, 9 Nov)
**Lane:** new **Flex parts** lane – new files `core/flex.py` (no Blender: shapes, lengths, solver),
`blender/flex.py`, `blender/ops_flex.py`, `ui_flex.py` (sub-panel of 4 Motion in its own file); small hooks only in
`blender/handlers.py` (frame + load), `blender/animation.py` (`bake`), `blender/reimport.py` (carry over, the 0052
pattern), `blender/props.py` (new property groups, additive), `core/part_types_data.py` (recognise hoses / chains,
additive); tests; guide chapter "Hoses and drag chains"; PC-check line
**Model:** **Fable · effort High** (the owner's "Fable day") · **Place:** Claude Code on the web, environment
"CAD-render-animation"

Runs at the same time as 0061 tool marks (Machining lane, Fable day): do not touch machining, coolant, chips, air, G-code, toolchange
files. If it needs a change in `gcode.py` (drag chains following the axes during a G-code run), keep it to a hook
and say so in the report.


## Split with subagents (owner, 12 Nov 2026 – CLAUDE.md "Subagents in a worker session")

Suggested split (the worker may change it; write the final plan under "Design" first):
- **Worker:** the design and the interfaces (`core/flex.py` ↔ `blender/flex.py`: centreline points, frame
  attribute, bake format), the hooks in `handlers.py`, `animation.py`, `reimport.py`, `props.py`, integration, tests
  on GitHub, release.
- **A – solver** (`core/flex.py` + `tests/test_flex_core.py`, no Blender): hose shape (fixed length, bend stiffness,
  sag, minimum radius, exact ends) and drag-chain shape (runs + bend, links re-laid by pitch).
- **B – Blender side** (`blender/flex.py`): centreline + diameter read from a tube mesh, tube builder, the one bake mesh
  per animation + Geometry Nodes slice (0075's decision), live-posing path.
- **C – test models** (`tools/make_test_flex*.py`, `tests/data/`): gantry with a link-part chain per axis, arm with a
  hose across a joint, cylinder with two hoses, soft cable between two moving parts.
- **Then:** D – panel/operators/tooltips/part-type rule (`ui_flex.py`, `ops_flex.py`); E – **independent tests and
  review of the solver** by an agent that wrote none of it (the brief's accuracy list); F – tour stops, PC-check
  line, guide chapter + pictures (worker or a `sonnet` subagent).

## Design (worker, 12 Nov 2026 – the subagents' brief; keep it current)

Units everywhere: **metres, world coordinates, Blender's axes (Z up)**; the core is unit-free NumPy (float64).
`core/` files never import `bpy`; Blender's Python has NumPy but **no SciPy and no Pillow**.

### How a flex part is drawn (decided with a prototype, web machine, 4 cores, bpy module, 3,000 moving parts)

- **No new model objects.** The hose *part itself* gets a Geometry Nodes modifier `FR flex` that replaces its CAD
  geometry with the app-made tube; every CAD *link* of a drag chain gets one that moves the link's own geometry to its
  place on the chain. So visibility, materials (object slot 0), paint schemes, selection, fades and "hide with the
  subassembly" keep working. Item off → modifier off → the CAD shape as imported.
- **One shapes mesh per scene**, object + mesh `FR flex shapes` in a hidden collection `Flex parts` (hidden objects
  referenced by a modifier *are* evaluated; checked at 3 frames): `frames × per_frame` vertices in world coordinates,
  frame after frame; point attributes `fr_x`, `fr_z` (FLOAT_VECTOR: a link's X and Z axes in the world). Each
  modifier has the inputs `Shapes` (object), `First` (frame of slice 0), `Frames`, `Per frame`, `Offset`, `Count`,
  `Radius`; index of point i = `clamp(round(frame - First), 0, Frames - 1) * Per frame + Offset + i`
  (Scene Time → Sample Index). **Live = the same with Frames = 1.** Positions are world: the node tree brings them
  into the part's own space with the inverse of its Self Object transform (Object Info "Original" + Invert Matrix +
  Transform Point – *not* Object Info "Relative", which copies the whole shapes mesh per hose: 0.37 ms instead of
  0.055 ms per hose).
- Measured: baseline 9.8 ms per frame; + 20 hoses (33 points, 12-sided tube) **+1.1 ms**; + 120 links (2,700
  triangles each, Transform Geometry by matrix) **+3.3 ms**; all **+4.5 ms** (budget 20 ms).
- Blender 5.2: a modifier input is `mod.properties.inputs.<identifier>.value`; nodes used and present:
  SampleIndex, ObjectInfo, SelfObject, InvertMatrix, MatrixMultiply, CombineTransform, AxesToRotation, TransformPoint,
  Transform (Mode "Matrix"), MeshLine, SetPosition, MeshToCurve, CurveToMesh (has `Scale`, `Fill Caps`),
  SetShadeSmooth, InstanceOnPoints, RealizeInstances.

### Files and owners

| File | Owner | What |
| --- | --- | --- |
| `core/flex.py` + `tests/test_flex_core.py` | **A1** | hose solver |
| `core/flex_chain.py` + `tests/test_flex_chain_core.py` | **A2** | drag-chain shape, link places, fit from the CAD links |
| `core/flex_fit.py` + `tests/test_flex_fit.py`, `tools/make_test_flex.py`, `tests/data/test_flex_*.step` (+ copies in `fresing_render/data/`) | **C** | tube mesh → centreline; the two test models |
| `blender/flex.py` + `tests/test_flex.py` | **B** | everything with bpy: items, ends, node trees, live, bake, model update |
| `blender/ops_flex.py`, `blender/ui_flex.py`, `tools/ui_test_flex.py`, `tests/test_flex_panel.py` | **D** | operators, panel, tooltips, real-app test |
| `tests/test_flex_independent.py` + a written review | **E** | independent tests and review of `core/flex*.py` (wrote none of it) |
| guide chapter + pictures | **F** | `docs/USER-GUIDE.md` chapter "Hoses and drag chains", `docs/img/` |
| `props.py` (done: `FRFlex`, `scene.fresing.flex`, `flex_index`), `__init__.py`, hooks in `animation.py`, `states.py`, `reimport.py`, `tour.py`, `pccheck/`, version, CHANGELOG, `TASKS.md`, CLAUDE.md | **worker** | |

### `core/flex.py` – hoses (A1)

```python
@dataclass
class Hoses:                 # arrays over the batch B
    points: np.ndarray       # (B, n, 3) centreline; points[:, 0] == p0 and points[:, -1] == p1 exactly
    short: np.ndarray        # (B,) bool: the ends are further apart than the hose can reach
    need: np.ndarray         # (B,) the shortest length that reaches (>= length when short)
    min_radius: np.ndarray   # (B,) the tightest bend along the hose (np.inf when straight)
    tight: np.ndarray        # (B,) bool: a limit was asked (> 0) and min_radius is under it (beyond 1 %)

def solve_hoses(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0.0, 0.0, -1.0), n=33) -> Hoses
def solve_hose(p0, t0, p1, t1, length, stiff, sag=1.0, min_radius=0.0, gravity=(0, 0, -1), n=33) -> Hoses  # B = 1
def stiff_length(diameter, stiffness) -> float      # the slider 0 … 1 → the bending length below
def polyline_length(points) -> float | np.ndarray   # (..., n, 3) → (...)
def resample(points, n) -> np.ndarray               # (m, 3) → n points equally spaced along the polyline
```

- `p0, p1` (B, 3) the ends; `t0, t1` (B, 3) unit vectors, **both pointing along the hose from end 0 to end 1**
  (t0 = the direction the hose leaves end 0, t1 = the direction it arrives at end 1). `length`, `stiff`, `sag`,
  `min_radius` scalars or (B,).
- The model: an inextensible elastic rod (no twist) under its own weight. `stiff` is the **bending length**
  ℓ = (EI / weight per length)^(1/3) in metres: energy per unit weight = (ℓ³/2)·∫κ² ds + sag·∫ height ds;
  `sag` 0 … 1 scales the weight (0 = pure bending). `stiff_length(d, s) = d · 4 · 16**s` (s = 0: 4 diameters, a soft
  cable; s = 1: 64 diameters, a stiff hydraulic hose).
- The result: `n` points, the `n - 1` segments all exactly `length / (n - 1)` long (so the length is exact), the
  first segment along `t0`, the last along `t1`, the ends exact.
- **A pure function**: no state between calls, no randomness, nothing taken from a previous frame; solving a batch
  gives the same as solving each hose alone (1e-9); a fixed number of steps from a start that depends only on the
  inputs, so the shape changes smoothly when the ends move (no jumps between frames).
- Suggested method (A1 may do better): unknowns are the unit segment directions d_i (d_0 = t0, d_last = t1 fixed);
  repeat a fixed number of times: an implicit bending-smoothing + gravity step on d (a constant matrix per (n, ℓ, h),
  applied with matmul over the batch), then put back the constraints exactly: d_i = normalize(b_i + λ) with λ ∈ R³
  from a damped Newton on the convex problem Σ d_i(λ)·h = p1 − p0 (3 × 3, batched). With ℓ → 0 this gives the
  catenary in one step. Start: a smooth curve from the inputs alone.
- `min_radius` > 0: the solver keeps to it where the ends allow (stiffen where the bend is too tight, or clamp the
  angle between segments and restore the constraints); `tight` says where it could not.
- `short`: the ends (with their first/last segment) cannot be joined by a hose of this length → the points are the
  straight line from p0 to p1 (stretched; ends still exact), `need` = the length that would just reach.
- Speed (n = 33): ≤ 0.25 ms per hose in batches of ≥ 20, ≤ 5 ms for one; a batch of 5,000 (20 hoses × 250 frames)
  in ≤ 3 s. Measure and report.

### `core/flex_chain.py` – drag chains (A2)

Chain coordinates: origin = the **fixed end's pin** (pin 0), **u** = along the fixed run towards the bend, **v** =
from the fixed run towards the moving run, **w** = u × v (across the chain). A chain of `links` links has pins
0 … links, every neighbour pair exactly `pitch` apart (chord), link i goes from pin i to pin i + 1.

```python
@dataclass
class ChainSpec:
    pitch: float; links: int; radius: float          # radius: the circle the pins lie on in the bend
    mode: str = "STRAIGHT"                           # or "GLIDE"
    glide_angle: float = math.radians(12.0)          # GLIDE: how steeply the run comes down after the bend
    rest_v: float | None = None                      # GLIDE: v of the run lying on the fixed run (default: the moving end's v)

@dataclass
class Chain:                 # arrays over the batch B (frames)
    pins: np.ndarray         # (B, links + 1, 3) in chain coordinates (u, v, w); pins[:, 0] == 0, pins[:, -1] == moving
    short: np.ndarray        # (B,) bool: the moving end is out of reach (too far, or no room for the bend)
    bend_u: np.ndarray       # (B,) u of the bend's centre

def chain_pins(spec, moving) -> Chain        # moving (B, 3) or (3,): the moving end's pin in chain coordinates
def link_frames(pins) -> tuple[np.ndarray, np.ndarray, np.ndarray]   # origin (B, L, 3) = pin i, x (B, L, 3) = unit(pin i+1 − pin i), z (B, L, 3) ⟂ x, near w
def fit_links(matrices, centres=None, types=None) -> ChainFit        # the CAD pose → what the chain is
def fit_solid(verts) -> ChainFit                                     # a chain drawn as one solid (lower priority)

@dataclass
class ChainFit:
    ok: bool; problem: str                    # plain words when it is not a chain
    order: np.ndarray                         # indices of the given links, end A first
    frame: np.ndarray                         # (4, 4) chain coordinates → the coordinates the links were given in
    pins: np.ndarray                          # (links + 1, 3) the CAD pins in the given coordinates
    local: np.ndarray                         # (links, 4, 4) each link's matrix in its own pin frame: world_i = pin_frame_i @ local_i
    pitch: float; radius: float; links: int; moving: np.ndarray   # (3,) the moving end in chain coordinates
    mode: str; residual: float                # how well the CAD pins fit pitch + radius (same unit)
    def reversed(self) -> "ChainFit"          # the other end is the fixed one
```

- Shape, mode STRAIGHT: the fixed run along +u from pin 0, the bend (pins on a circle of `radius` whose centre is at
  v = radius), then a straight run to the moving end. With the moving end at v = 2·radius this is the classic two
  runs + half circle, and the bend moves at half the moving end's speed. A moving end a little off (v ≠ 2·radius,
  w ≠ 0) is still met exactly: the run after the bend is the tangent line to it, w is spread evenly over the pins
  after the bend's start. GLIDE: after the bend the run comes down at `glide_angle` and then lies at `rest_v`.
- **Exact:** every chord = pitch (1e-9), pins[:, -1] == moving (1e-9) unless `short`, bend pins on the circle
  (1e-9), closed forms + a 1-D solve for the bend's place, vectorised over frames (no Python loop over pins per
  frame). Pure function, continuous in `moving`.
- `link_frames`: the pin frame of link i (4 × 4 = columns x, y = z × x, z, origin). A CAD link's world matrix at
  any frame = `pin_frame_i @ fit.local[i]`.
- `fit_links(matrices (K, 4, 4) link object matrices, centres (K, 3) the links' mesh centres, types (K,) ints: same
  number = same mesh)`: order the links along the chain (nearest neighbours from the centres); find the two pin
  points in each link type's own coordinates (unknown a, b with `M_i·b = M_{i+1}·a` for neighbours: linear least
  squares; the part along the turning axis is free – take the smallest); from the pins: plane, u, v, pitch, radius
  (from the turn per link in the bend: R = pitch / (2 sin(φ/2))), which run is which, the moving end. When the
  links do not fit one rigid pattern (residual large): fall back to pins half-way between neighbouring centres.
  A chain drawn straight (no bend in the CAD pose) is not a fit: `ok = False`, problem says to pick the radius.

### `core/flex_fit.py` – a tube mesh's centreline (C)

```python
@dataclass
class Tube:
    ok: bool; problem: str
    points: np.ndarray       # (n, 3) the centreline from end 0 to end 1, equally spaced
    radius: float            # the outer radius
    length: float            # along the centreline
    t0: np.ndarray; t1: np.ndarray    # unit, along the centreline from end 0 to end 1 at each end
def tube_centreline(verts, tris, n=65) -> Tube      # verts (V, 3) float, tris (T, 3) int; not welded is fine
```

Works for a bent tube in 3D, hollow or solid, coarse facets (8 sides), a hex ferrule fused on an end; the ends are
the centres of the end faces. Not a tube (a box, a plate, a ring) → `ok = False` with a plain reason.

### `blender/flex.py` (B) – what the others call

```python
TAG = "fr_flex"; MOD = "FR flex"; SHAPES = "FR flex shapes"; COLLECTION = "Flex parts"
def items(scene); def active(scene); def find(scene, name); def label(item) -> str
def add_hose(scene, part, soft: bool = False) -> tuple[item, list[str]]         # reads the centreline, ends, diameter, length; finds the part each end touches
def add_chain(scene, links: list, part=None) -> tuple[item, list[str]]          # CAD links (any order); or part = one solid → the app draws links
def remove(scene, index: int) -> None                                            # the CAD shape shows again
def fit_to_cad(scene, item) -> list[str]                                         # reset: length, ends, pitch, radius … from the CAD pose
def set_end_part(scene, item, end: str, ob) -> None                              # end "A" | "B" sits on another part (same world place now)
def swap_ends(scene, item) -> None                                               # chain: the other end is the fixed one
def changed(scene, item) -> None                                                 # a setting changed (props.py calls it)
def refresh(scene, force: bool = False) -> None                                  # live: solve for where the parts are now
def bake(scene, anim) -> list[str]                                               # at the end of Build animation; returns warnings
def after_clear(scene) -> None                                                   # Clear keys: live again
def shape_now(scene, item) -> np.ndarray                                         # (n, 3) world: hose centreline / chain pins as drawn at the current frame (read from the shapes mesh)
def status(scene, item) -> tuple[str, str]                                       # (text, "OK" | "WARN" | "ERROR") for the list and the panel
def candidates(scene) -> list                                                    # [(object, "HOSE" | "CHAIN")] parts whose part type says hose / cable / cable chain and that are no flex part yet
def parts_of(scene, item) -> list                                                # the model parts it draws (hose part, links)
def after_model_update(scene, by_uid: dict, mapping: dict) -> list[str]          # as trails.after_model_update
def register(); def unregister()                                                 # handlers; clash.HOOKS (leave flex parts out)
```

- **Ends.** Hose: `a_point` / `a_dir` (and b) are the centreline's end and its direction (A → B) in `a_part`'s
  coordinates; the end's world place at any time = `a_part.matrix_world @ a_point`. `a_part` = the model part the end
  touches (fitting, block; nearest mesh within about one radius, never the hose or another flex part), else the
  hose part's parent. Chain: `frame` in `a_part`'s coordinates, `b_point` = the last pin in `b_part`'s.
- **Live** (no built animation): a `depsgraph_update_post` handler looks whether an end moved (matrix compare), solves
  those items and writes the shapes mesh (Frames = 1); the linkages pattern (busy flag, a one-shot timer to redraw).
  With a built animation it returns at once. `states.py` calls `flex.refresh(scene)` after a pose (also in the
  background, where no handler helps).
- **Bake** (`animation.bake` calls it last; `clear_keys` calls `after_clear`): read every item's end frames at
  every frame (step the frames as `trails.sample` does: `clash._Guard`, shy Geometry Nodes objects hidden), solve all
  frames in one batch, write the shapes mesh, set every modifier's inputs. Keeps the sampled end frames (with the
  project) so a setting changed later re-solves without stepping frames. Warnings name the item and the first frame:
  "Hose 'X' is too short at frame 120 (it needs 12 mm more)", "… bends tighter than 60 mm at frame 80".
- Model update: by part IDs as `trails.after_model_update`; settings kept, modifiers on the new parts.

### Test models (C) – `tools/make_test_flex.py hoses|chains out.step [A|B]`

- `test_flex_hoses_a.step` (+ `_b`: a revision with one more part and the hoses placed in another order): BASE with a
  valve block, an ARM.ASM that turns about Y on a post, a CYL (barrel + rod, pins as in `make_test_cylinder.py`) that
  luffs it, a SLIDE.ASM that slides along X; fittings as separate small parts. Hoses, each one solid (a pipe swept
  along a 3-D path, drawn bent): `HYDRAULIC HOSE ARM` (Ø20, valve block → arm, across the arm's joint),
  `HYDRAULIC HOSE CYL A` / `B` (Ø16, valve block → the barrel's ports), `CABLE` (Ø10, hangs in an arc between a gland
  on the arm and one on the slide).
- `test_flex_chains_a.step`: a gantry as `make_test_gantry.py` (BED, Y.ASM, X.ASM, Z.ASM, SPINDLE, a tool, so a
  short G-code program can drive it) with three drag chains of identical `CHAIN LINK` solids (frame-shaped, pitch
  40, bend radius 80, the solid's origin *not* on a pin), each with a `CHAIN BRACKET` on the fixed part and one on
  the moving part: X (plane X–Z, on the beam), Y (lying on its side beside the bed, plane X–Y), Z (standing, on
  the carriage). Links never touch each other or another part in the CAD pose (the tour's 0-clash rule).
- Every part one solid, generic shapes, small files; the maker's docstring lists names, places, axes and the
  numbers the tests need (lengths, diameters, pitch, radius, link counts, travel).

## Goal

When a machine moves, its hydraulic hoses, cables and drag chains (energy chains) move with it like the real thing:
both ends stay on their parts, the length stays the same, they bend smoothly and sag under their own weight, and
a drag chain rolls over its own bend radius. Today they stay stiff in the CAD pose, so they stretch, float or pass
through parts in every animation – on the owner's mill (drag chains on the axes) and on offshore cranes and
cylinders (hydraulic hoses).

## What the owner works with

- STEP from Inventor and Fusion. Hoses are usually one solid per hose (tube along a path) with fittings as separate
  parts; cables often too. Drag chains are either many identical link parts (igus-style, one part per link, as
  bought-in STEP) or one simplified solid.
- Motion comes from joints, stacked joints, cylinders, mechanisms (0011–0014) and G-code runs (0026/0041).
- Renders: Cycles stills, EEVEE/Cycles videos, the render queue in the background (no window), turntables.

## Scope

1. **Hose / cable between two ends.** The user picks the hose part (or the app finds it: part-type rule "Hoses &
   cables", names like hose, slang, schlauch, kabel, cable). The app reads its centreline and diameter from the mesh
   (a tube's skeleton; works for bent CAD hoses) and its two ends: each end belongs to the part it touches (the
   fitting), with the end's direction. Length = the CAD centreline length (can be changed). Each frame the shape is
   solved from the ends' positions and directions: fixed length, bending stiffness (stiff hydraulic hose ↔ soft
   cable – one slider), gravity sag, minimum bend radius. The CAD solid is hidden and replaced by an app-made tube
   (same diameter, the hose part's material; optional braid/rubber look via the 0046 materials).
2. **Drag chain (energy chain).** Fixed end on one part, moving end on another, travel along one axis (from the
   joint that moves it). Shape: two straight runs + a half-circle with the chain's bend radius, the upper run lying
   on the lower run (or hanging/self-supporting – setting), the bend moves at half the speed of the moving end.
   If the CAD has the chain's links as separate identical parts, the app re-lays those link parts along the shape
   (pitch from the CAD); otherwise it builds links from a simple profile (width, height, pitch, bend radius, colour).
   Vertical and side-mounted chains too (chain plane from the CAD).
3. **Panel** 4 Motion > **Hoses and drag chains**: list, Add hose (pick part), Add drag chain (pick links or the
   chain part, then fixed end, moving end), per item: on/off, stiffness, sag, bend radius, length, "Fit to the CAD
   pose" (reset), a warning when the motion needs more length than the hose has or a bend tighter than allowed
   ("Hose 'X' is too short at frame 120"). Tooltips on every button.
4. **Everywhere the motion shows:** scrubbing, playback, Build animation, the render queue in the background, stills
   in saved poses, turntables, G-code runs, cylinders driven by stroke. Deterministic: the same frame gives the same
   shape whatever frame came before (no simulation that needs earlier frames, or a cached one that is rebuilt on
   change) – the queue renders frames out of order.
5. **Model update** keeps hoses and chains (by part IDs, as joints in 0052); old projects open unchanged (nothing
   added until the user adds a hose or chain).
6. Not now: hoses touching and pushing other parts (collision); cables over sheaves and winch drums (that is the later
   "motion paths" task); hoses with three or more ends; cable bundles. Write ideas into the report.

## Lead's decisions from the motion paths study 0075 (11 Nov)

Read the report of `tasks/0075-motion-paths-design.md` (Summary points 2 and 4, the numbers table, the Blender 5.2
lessons) before designing the per-frame part.
- **Bake at Build, not a frame handler, for renders.** Writing curves/meshes in a frame handler costs ~6 ms per frame on
  3,000 parts whatever the solver (20 hoses in one handler: +8.3 ms), also in the queue. So: *Build animation* solves
  every frame's shape once and writes all hoses/chains of an animation into one hidden "bake" mesh (a frame attribute
  per point); Geometry Nodes picks the current frame's slice (Scene Time → Sample Index). Deterministic, works in the
  queue and with scripts off. The frame handler is only for **live posing** (no built animation, or the user drags a
  joint) and is not used while a built animation plays or renders.
- **Reusable for motion paths:** keep the tube builder (centreline → tube with diameter + material), the bake/slice
  module and the handler hook generic in `blender/flex.py` / `core/flex.py`, so the later motion-paths tasks (rope over
  sheaves, catenary) only add to them. Part types Sheave / Winch drum / Track pad are **not** in this task (they come
  with motion-paths task 1).
- Motion paths go in this lane (Flex parts) after 0058.

## Accuracy and speed (tests)

- Ends exact (< 0.1 mm, direction < 1°); hose length within 0.5 %; no bend under the minimum radius (or the
  warning); drag chain: length constant within one pitch, links never overlap, the bend radius exact, the moving end
  exactly on its part over the whole stroke.
- Speed: the Heavy machine (`pccheck/heavy_scene.py`) with 20 hoses and 3 drag chains (test parts added by the test):
  frame change ≤ 20 ms extra; Cycles still render time not more than the extra geometry costs.
- Generic test models made by the worker in the repository (the repository is public – no owner models): a gantry
  with a drag chain on each axis (link parts as separate solids), an arm with a hydraulic hose across a joint, a
  cylinder with two hoses on its barrel, a soft cable hanging between two moving parts. Pictures of each in the report
  (Cycles, small).

## Done when

- [ ] Hoses/cables and drag chains as above, in the panel, recognised by part type where possible.
- [ ] Works in view, Build animation, queue (background), stills, turntable, G-code run (the test gantry driven by a
      short program), cylinders by stroke; deterministic frames (test: render frame 50 after frame 10 and after 90 →
      same shape).
- [ ] Model update keeps them; save/reopen; old projects (0.2.30, 0.2.45) unchanged.
- [ ] The tests above, the speed numbers in the report; an independent review by a helper agent of the solver
      (`core/flex.py`) (CLAUDE.md section 2).
- [ ] Guide chapter "Hoses and drag chains" with pictures; PC-check line `motion.flex`; tooltips.
- [ ] Tour stops "Hoses" and "Drag chains" in the test tour (0059, `blender/tour.py`).
      How (0059 is on `main`): a `stop(...)` entry in its group in `blender/tour.py`, set up in a set's build function
      (`_shot(b, "@<stop id>")` or an animation with `animation=`), a number `check`; raise `MIN_LINES_TOUR`
      (`tools/ci_check_pccheck.py`) and `MIN_CHECKS["tour"]` (`tools/ci_real_app.py`); `pytest tests/test_tour.py`.
- [ ] GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0058 done; what the owner should check on his own mill and crane.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 12 Nov 2026, branch `claude/sleepy-mccarthy-3zpzfu`.

**State (for a session that has to continue this task; delete when done):** design committed (section "Design");
`props.py` has `FRFlex` / `scene.fresing.flex`; `blender/flex.py` is a do-nothing skeleton with the hooks in
`animation.py` (bake, clear_keys), `states.py` (poses), `reimport.py`, `__init__.py` already calling it. Wave 1 of
subagents (A1 hose solver, A2 chain geometry, C centreline reader + test models) was cut off once by the usage limit
(5-hour limit, 12 Nov) and restarted. **On the branch now:** A2 `core/flex_chain.py` (38 tests), C `core/flex_fit.py`,
`tools/make_test_flex.py`, the three `test_flex_*.step` models (88 tests). **Not yet:** A1 `core/flex.py` (running), B
`blender/flex.py` (running, started before A1 landed). Still to do after
them: B `blender/flex.py`, D operators + panel, E independent tests + review, tour stops, PC-check line, guide, release.

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
