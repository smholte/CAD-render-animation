# 0182 – Lifting plans L1: the checks and the load-chart format in plain Python

**Who:** worker · **Status:** running · **Branch:** `task/0182-lifting-checks`
**Started by:** lead chat, 17 Nov 2026 (study 0180, task L1; owner's answers the same day) · **Lane:** Lifting (new files
only: `fresing_render/core/lifting.py`, `tests/test_lifting.py`, `tests/test_lifting_independent.py`; nothing in `blender/`)
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The core every later Lifting task uses: the nine checks C1–C9 of study 0180 (crane use %, sling legs, shackle / sling
WLL, outrigger + mat pressure, crawler tracks, forklift load centre, offshore DAF, upending), the load-chart format with
its lookup and validation, units and the status words – pure Python, no Blender, proven by the study's worked cases.

## Read first

`tasks/0180-lifting-plans-study.md`: section 3 (the checks, formulas, **the worked test cases – use exactly these**, the
checks the app must not do), section 4 (chart format, sample mark), section 8 (the words), section 9 row L1.

## The owner's answers (17 Nov 2026, section 10 of the study)

1. **Radius between two chart rows: the next longer radius** (never interpolate; a radius past the last row = no
   capacity, red). Keep the chart's data model open for interpolation later, but do not offer it.
2. **Amber limits: 75 % crane use, 90 % rigging and ground** – defaults the planner can change per plan. Green below,
   amber up to 100 %, red above.
3. **Lift categories: BS 7121 (basic / intermediate / complex) by default, ASME P30.1 (standard / critical) selectable**
   – the plan stores which system; L1 gives the names and the plain rules the study lists, nothing more.
4. **Offshore DAF: a preset from the public DNV-OS-H205 (2014) table, editable**, with the note "check against the
   current DNV-ST-N001". (Questions 4 and 6 – onshore first, PDF + web page – go with the study's recommendation.)

## Rules

- Every result carries its inputs, the formula's name and a status (`ok` / `amber` / `red` / `not_checked`), so the
  panel and the printed plan can show how it was worked out. Units SI inside (kg, m, N, Pa), conversions at the edges.
- The words of section 8: never "safe" or "approved"; "within the entered chart / limits"; the competent-person line is
  a constant the plan uses on every page.
- Built-in sample charts are not in this task (L2/L3); the tests use small invented charts.
- **An independent tester** (a subagent that did not write `lifting.py`) writes `tests/test_lifting_independent.py`
  from section 3 and this brief only; send its findings back to the author (CLAUDE.md section 2).
- No tour stop, PC-check line or guide section yet (nothing the owner can see; the first visible Lifting task, L4,
  adds them). Say so in the report.

## Done when

- [ ] C1–C9 + chart lookup / validation (rising radius, falling capacity, units) + status + limits in `core/lifting.py`.
- [ ] Every worked case of section 3 passes to the study's digits; the independent tests pass.
- [ ] Full GitHub run green (put `[full run]` in the last code commit – no version raise, nothing visible); merged to
      `main`; report filled in; `TASKS.md`.

## Not in this task

Blender code, panels, equipment files and makers (L2/L3), the hang solver (L5), the printed plan (L7).

## Design (the interface – written before the code; the independent tester's brief)

One module `fresing_render/core/lifting.py`, plain Python (only `math`, `dataclasses`), no Blender, no NumPy.

**Units inside: SI.** Masses in kg (loads, chart capacities, WLLs, forklift ratings, SHL/DHL), lengths in m, forces in
N, pressures in Pa, angles in degrees at the interface. A WLL or chart capacity is a *mass* rating: a force F in N is
compared with it as `F / (wll * G)`. `G = 9.80665`. Edge helpers: `kg(t)` (t → kg), `tonnes(kg)`, `newton(kg)` (kg →
N), `force_t(N)` (N → t), `kN(N)`, `kPa(Pa)`; `MASS_UNITS = {"kg": 1, "t": 1000, "lb": 0.45359237}`,
`LENGTH_UNITS = {"m": 1, "mm": 0.001, "ft": 0.3048}`.

**Status.** `OK, AMBER, RED, NOT_CHECKED = "ok", "amber", "red", "not_checked"`. `status_of(use, amber_at)`: `use is
None` → not_checked; `use > 1` → red; `use >= amber_at` → amber (up to and including 100 %); else ok (use compared after
rounding to 1e-9). `STATUS_WORDS = {ok: "Within entered limits", amber: "Near entered limit", red: "Over entered
limit", not_checked: "Not checked"}`. `worst_status(statuses)`: red > amber > not_checked > ok (empty → ok).

**Limits.** `@dataclass Limits(crane=0.75, rigging=0.90, ground=0.90)` (owner 17 Nov 2026; per plan). `crane` is used
for the equipment's own rating (C1, C7, C8, C9), `rigging` for slings / shackles / spreaders (C2–C4), `ground` for
outrigger mats and tracks (C5, C6). `DEFAULT_LIMITS = Limits()`.

**Result** (every check returns one): `@dataclass Result` with `check` ("C1" …), `title`, `formula` (its name in
words), `inputs` (dict, SI), `value` (the checked quantity, SI, or None), `limit` (what it is compared with, SI, or
None), `use` (value / limit, a fraction, or None), `amber_at`, `status`, `words` (= STATUS_WORDS[status]), `message`
(one plain sentence with t / kN / kPa), `details` (dict of further numbers, SI), `notes` (list of str), `parts` (list
of sub-Results; `status` is the worst of its own and its parts'), `leaves_out` (the study's "Leaves out" text for the
check). `Result.to_dict()` → plain JSON-able dict. `worst(results)` → the index of the worst Result in a list (status
rank, then use; for "the worst moment" of a lift path).

**Words** (section 8): `PLANNING_AID` (the competent-person line, exact text of the study), `SAMPLE_MARK` ("SAMPLE –
not for real lifts. …"), `NOT_CHECKED_BY_APP = "not checked by Fresing Render – competent person"`, `NOT_DONE` (list
of the checks the app must not do, each a short text), `FORBIDDEN_WORDS = ("safe", "approved", "certified",
"compliant", "OK to lift", "passed")` – no message, word or note of the module contains one (whole words, any case).

**Lift categories.** `CATEGORY_SYSTEMS = {"BS 7121": ("basic", "intermediate", "complex"), "ASME P30.1":
("standard", "critical")}`, `DEFAULT_CATEGORY_SYSTEM = "BS 7121"`. `suggest_category(system=DEFAULT…, cranes=1,
people=False, crane_use=None, crane_limit=0.75, offshore=False, pick_and_carry=False)` → `(category, reasons)`:
BS 7121: several cranes or people → complex; else use above the limit, offshore or pick-and-carry → intermediate; else
basic. ASME P30.1: several cranes, people, use above the limit or offshore → critical; else standard. Only a
suggestion; the planner sets it. Unknown system → ValueError.

**Load chart.** `@dataclass Chart(radius: list[float] (m), capacity: list[float | None] (kg; None = a gap, "not
allowed here"), config: dict = {} (e.g. "boom" m, "jib" m, "counterweight" kg, "outriggers" m, "hs" m), name="",
includes_hook_block=False, interpolate=False, wind_max=None (m/s), sample=False)`. `interpolate` is stored for later
and never used by a check (owner: always the next longer radius).
- `chart_from_dict(d, mass_unit="t", length_unit="m")` / `chart_to_dict(chart, mass_unit="t", length_unit="m")` – the
  equipment file's chart (`config`, `radius`, `capacity`, `wind_max`, `includes_hook_block`, `interpolate`, `sample`,
  `name`); converts radius and the config's length keys (`boom`, `jib`, `outriggers`) and mass keys
  (`counterweight`) at the edge; `hs` and `wind_max` stay m and m/s. Unknown unit → ValueError.
- `validate_chart(chart)` → `(errors, warnings)` (lists of plain sentences). Errors: no rows; radius and capacity lists
  of different length; a radius not a finite number > 0; radii not strictly rising; a capacity not a finite number
  > 0 (None allowed = gap); a capacity that rises with radius (compared over the non-gap rows; equal is allowed).
  Warning: `interpolate` set ("not offered: the next longer radius is used").
- `validate_charts(charts)` → `(errors, warnings)`: each chart's, plus: two charts with the same config (error); charts
  equal but for `hs`: a column for a higher Hs with more capacity than a calmer one at the same radius (error); charts
  equal but for `boom`: capacity rising with boom length at the same radius (warning only).
- `lookup(chart, radius)` → `Lookup(capacity, row_radius, reason)`: the first row whose radius ≥ the asked radius
  (1e-9 m tolerance) – **the next longer radius, never interpolated**. Past the last row → capacity None, reason
  "outside the chart"; shorter than the first row → None, "closer than the chart's shortest radius"; the row found
  is a gap → None, "not allowed here (gap in the chart)"; an invalid chart → None, reason = its first error.
- `capacity_interpolated(chart, radius)` → kg or None: linear between the two rows round the radius (only the worked
  case's number; no check calls it, nothing offers it).
- `pick_chart(charts, boom=None, hs=None, **config)` → `(chart or None, note)`: charts whose config equals every given
  `config` key; of those, with `boom` the shortest boom ≥ the boom asked (the next longer boom), with `hs` the lowest
  Hs ≥ the Hs asked; none → None and a plain note.

**The checks.** Every function takes `limits: Limits = DEFAULT_LIMITS` as a keyword.
- **C1** `crane_use(load, radius, chart, rigging=0.0, hook_block=0.0, daf=1.0, wind_area=None, limits=…)`: gross =
  (load + rigging + hook_block if not chart.includes_hook_block) × daf – the daf is *not* applied when the chart has an
  `hs` in its config (an Hs column is already dynamic: note "no double count"); capacity from `lookup`; value = gross
  (kg), limit = capacity (kg), use = gross / capacity, `amber_at = limits.crane`. No capacity → red, message says the
  lookup's reason. `wind_area` (m²) above 1.2 m² per t of load → a note ("wind area above 1.2 m²/t … competent
  person"), status unchanged. details: gross, capacity, row_radius, daf_applied.
- **C2** `two_leg(weight, point_a, point_b, hook, leg_wll=None, shackle_wll=None, limits=…)`: points (x, y, z) m,
  weight kg; the legs run from the lift points to the hook (hook above the CoG after the load hangs). Statics:
  T_A·u_A + T_B·u_B = W·g·ẑ solved in the vertical plane through A and B (the plan offset of the hook from line AB goes
  to a note when > 1 mm). details: `vertical` (N, per leg), `force` (N, per leg), `length` (m), `angle` (° to
  vertical), `horizontal` (N). value = the larger leg force (N). Parts: one `wll_use` per leg for `leg_wll` and for
  `shackle_wll` (each when given). No WLL given → status not_checked (the forces are still there).
- **C3** `multi_leg(weight, points, hook, leg_wll=None, mode="rigid", limits=…)`: 3 or 4 points (else ValueError).
  mode "rigid" (default): two legs carry – each leg's force T_i = (W·g/2)·L_i/h_i, value = the largest; "equalised":
  equal share W·g/n·L_i/h_i (a user switch: equalisers fitted); "dnv": equal share × `SKEW_FACTOR_DNV = 1.25`.
  details: `force` (N per leg), `length`, `angle` (°), `equal_share` (N per leg), `dnv_share` (N per leg). With
  `leg_wll` two parts: the leg force against the leg WLL (`wll_use`), and the assembly against its marked rating
  `ASSEMBLY_FACTOR` × leg WLL: 2.1 for the largest leg angle 0–45°, 1.5 for 45–60° – value = W (kg), limit = rating
  (kg). A leg more than 60° from vertical → red ("above 60°: not rated") on the assembly part and the check.
- **C4** `wll_use(force, wll, item="sling", angle=None, mode_factor=1.0, side_angle=None, limits=…)`: force N, wll kg;
  limit = wll × mode_factor (kg, e.g. choke 0.8); use = force / (limit·G); `angle` (° to vertical) > 60 → red;
  `side_angle` (° out of the shackle's bow plane) > 5 → a note (side load: maker's reduction), status unchanged.
- **C5** `outrigger_reactions(items, a, b, centre=(0, 0))` → `Reactions(P, x, y, corners, reactions, lifted)`: items
  = [(mass kg, x, y)] in the carrier's frame (m); outriggers at centre ± a, ± b; corners in the order (+a,+b), (+a,−b),
  (−a,+b), (−a,−b); reactions in N; rigid carrier, linear share R = P·g/4·(1 ± x̄/a ± ȳ/b); one R < 0 → that corner
  lifts (`lifted` = its index) and the other three carry (three equations); a resultant outside the base → reactions
  None, `lifted` = "tips".
  `crane_items(carrier, upper, load_mass, load_radius, slew)`: carrier = [(m, x, y)] fixed; upper = [(m, r, side)]
  turning with the slew (r along the boom direction, + = towards the load; side to its left); the load at
  `load_radius` along the boom; slew in degrees from +x towards +y → items for `outrigger_reactions`.
  `outriggers(items, a, b, mat=None, allowable=None, centre=(0, 0), limits=…)` → Result: value = the largest
  pressure (Pa) = R_max / mat area (mat = (length, width) m; one mat size for all four), limit = allowable (Pa,
  entered with its source); details: P, x, y, reactions, lifted. One corner lifted → at least amber, note "one
  outrigger unloaded"; tips → red. No mat or no allowable → status not_checked (reactions still given).
  `outriggers_sweep(carrier, upper, load_mass, load_radius, a, b, mat=None, allowable=None, step=1.0, limits=…)` →
  the worst Result over every slew angle (0 … 360 in `step`) and the unloaded crane (details: `slew`, `loaded`).
- **C6** `tracks(mass, x, y, gauge, length, width, allowable=None, limits=…)`: mass kg with its resultant x (along the
  tracks, from the middle) and y (across, from the middle, + towards track 1); shares by lever across the gauge
  (track 1 = P·(gauge/2 + y)/gauge); along a track e = |x|: e ≤ L/6 trapezoid p = R/(bL)·(1 ± 6e/L); e > L/6 triangle
  p_max = 2R / (3b(L/2 − e)) over 3(L/2 − e) of contact; |y| > gauge/2 or e ≥ L/2 → red (outside the tracks). details:
  `share` (N per track), `p_max`, `p_min` (Pa per track), `contact` (m per track). value = the largest p_max (Pa).
- **C7** `forklift(load, rated, centre, actual_centre, axle_to_face, table=None, lift_height=None, limits=…)`: kg and
  m. With `table` = [(load centre m, lift height m, capacity kg)]: the row with the next larger load centre (≥ actual)
  and next higher lift height (≥ asked; any when None) – smallest such centre, then height; none → red. Without it the
  fork rule rated·centre/actual_centre (no rise for a shorter centre: min(rated, …)); the moment rule
  rated·(centre + x)/(actual + x) in details only ("for information"). value = load, limit = capacity.
- **C8** `DAF_DNV_OS_H205_2014` = list of bands (upper SHL kg inclusive, or None for the last; onshore, inshore,
  offshore): ≤ 100 t 1.10 / 1.15 / 1.30; ≤ 300 t 1.05 / 1.12 / 1.25; ≤ 1,000 t 1.05 / 1.10 / 1.20; ≤ 2,500 t
  1.03 / 1.08 / 1.15; above 1.03 / 1.05 / 1.10. `DAF_NOTE` = "Preset from DNV-OS-H205 (2014) – check against the
  current DNV-ST-N001". `static_hook_load(load, rigging=0, tool=0, contingency=1.0)` = load·contingency + rigging + tool
  (kg). `daf_for(shl, site, table=DAF_DNV_OS_H205_2014)`, site in ("onshore", "inshore", "offshore") else ValueError.
  `dynamic_load(shl, site, chart_capacity=None, hs_rated=False, daf=None, table=…, limits=…)`: DHL = SHL × DAF (`daf`
  overrides the table); with `chart_capacity` (kg, static chart) use = DHL / capacity at `limits.crane`; `hs_rated` →
  the crane is checked with its Hs column in C1 instead (use None, note), the DAF stays for the rigging. details: shl,
  daf, dhl.
- **C9** `upending(items, hook_s, angle, rope=(0.0, 1.0), off_hinge=False, capacity=None, limits=…)`: items = [(mass
  kg, s m along the pile from the hinge)], the hook at `hook_s` along the pile, the pile `angle`° above horizontal,
  `rope` = the rope's direction (horizontal along the pile's plan direction, up) in the vertical plane; moment about the
  hinge: F = Σ m·g·s·cos θ / (hook_s·(cos θ·r_up − sin θ·r_h)) (rope vertical: F = Σ m·g·s / hook_s at every angle);
  hinge = the rest (vector). At vertical with a vertical rope (no lever) or `off_hinge=True` → the hook takes all, note.
  details: `hook` (N), `hinge` (N, size), `hinge_vector` (N, (h, up)). With `capacity` (kg) use = F / (capacity·G) at
  `limits.crane`; else not_checked.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
