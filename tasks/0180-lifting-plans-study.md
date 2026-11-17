# 0180 – Study: the Lifting plans workspace – 3D lifting plans with ready-rigged cranes, forklifts and lifting tools (findings + design only)

**Who:** worker · **Status:** done 17 Nov 2026 · **Branch:** none (report on `main`, touching only `tasks/`)
**Started by:** lead chat, 17 Nov 2026 (owner's wish + his answers the same day) · **Model:** Opus · effort High ·
**Place:** a **new chat in the claude.ai project "STEP rendering App"** (it must open web pages; CLAUDE.md section 2,
as 0113 / 0150–0152). Findings only: no app code, no test run – it does not count towards the four code tasks.

## Goal

A design the lead can split into build tasks for a new **Lifting plans** workspace: the user builds a lifting plan in
3D with ready-rigged cranes, forklifts and other lifting equipment in several sizes, adds his own equipment, sees the
lift move with its clearances, gets the main checks (crane use %, sling forces, ground pressure) and a printable plan.

## The owner's wishes (17 Nov 2026)

- **A Lifting plans workspace** (one of the workspaces of 0062, the owner's document "UI workspace presets"): create a
  lifting plan in 3D with pre-rigged cranes and forklifts of different sizes, "all kinds of lifting equipment", and
  **users can add their own**.
- **What it delivers:** the 3D plan, clearances and the lift as an animation **plus checks** – crane use % against the
  load chart, sling leg forces, outrigger / track ground pressure – **and a printable plan**. Everything marked "to be
  checked by a competent person": the app checks against the data entered, it never certifies a lift.
- **Equipment:** **generic size classes first**, invented and unbranded (like the demo vessel), every sample load chart
  clearly marked "sample – not for real lifts"; the user enters the real chart of a real crane. **Real makes and models
  (Liebherr, Tadano …): something to look into later** – the study only notes what that would need (data, licences);
  nothing is designed for it now.
- **Sites, all four:** onshore site / port (mobile and crawler cranes, outriggers on mats); offshore vessel / platform
  (pedestal and knuckle-boom cranes, ship motion, sea state); workshop / factory (overhead cranes, forklifts, chain
  hoists); **offshore wind foundations: monopile / transition-piece lifting with custom lifting tools** (the owner's
  own field: upending tools, pile and flange lifting tools, gripper frames – invented generic ones only).
- **Workspace E of the owner's document ("Heavy lifting, cranes & rigging") is merged into Lifting plans:** hydraulic
  cylinder kinematics, winch / cable tension, centre-of-gravity markers, outdoor site / port surroundings,
  clearance / reach envelopes belong here.

## What to do

1. **What a lifting plan holds.** Public sources only: lift-planning standards and guidance (for example BS 7121 /
   ISO 12480-1, LOLER guidance, ASME P30.1 / B30, NORSOK R-003, DNV-ST-0378, DNV-ST-N001 for lifts at sea – check
   the names and pick what is public), crane makers' public planning guides, contractors' public lift-plan templates.
   List the contents (load data and CoG, contingencies, crane set-up, radius and use limits, rigging with WLL and
   angles, ground bearing, exclusion zones, wind / sea-state limits, sequence, drawings, sign-off), the lift
   categories (routine / complex / critical) and what changes offshore (dynamic factor, sea state, off- and side-lead,
   tandem lifts, upending).
2. **Equipment catalogue for the generic classes.** Per kind – mobile telescopic crane, crawler (lattice) crane,
   knuckle-boom truck crane, offshore pedestal crane, overhead / gantry crane, tower crane (if worth it), forklifts
   and telehandlers, chain hoists, spreader beams, lifting frames, slings (chain, wire, round), shackles, hook blocks,
   the monopile / TP tools: size classes (3–5 per kind), the joints the rig needs (slew, luff, telescope, hoist,
   outriggers, tracks, mast, tilt, side-shift), the data each needs (load chart by radius × boom × counterweight,
   hook-block weight, outrigger spread, rated capacity at load centre …), plausible sizes from public brochures.
   How the app makes them: parametric makers like `fresing_render/demo_model/` (invented, in the repo) – one maker per
   kind, sizes as parameters.
3. **The checks.** For each: inputs, formula, public source, what it leaves out, and a worked test case with a hand
   calculation (these become the build tasks' tests): crane use % (load + rigging + hook block against the chart at
   the radius, interpolation rule, the limit the user sets), sling leg forces with an off-centre CoG and sling angle
   (2-leg; 4-leg with the usual "two legs carry" rule), shackle / sling WLL against the force, outrigger or track
   reactions and ground pressure on a mat, forklift capacity at another load centre, an offshore dynamic factor.
   Say plainly which checks the app should **not** do.
4. **The user's own equipment.** One file per item in the shared library (like rule sets, brand kits and 0062's own
   workspaces): a STEP or mesh model (0117) + a JSON with the joints, the load chart (table entry or CSV), weights,
   limits; units, version, a newer file opening in an older app; how a load chart is checked on entry (rising radius,
   falling capacity); the "sample" mark that cannot be removed from the built-in ones.
5. **The plan in the app – UI flow.** Place the site (surroundings), place equipment from a picker, pick the load
   (a STEP part / assembly of the project or a box with weight + CoG), rig it (slings to lifting points, shackles,
   spreader), set the lift path (pick-up → set-down, slew / luff / hoist steps, or the existing poses and animation
   steps), see clearances (clash check 0065 / 0110 as minimum distance, reach envelope, exclusion zones), the checks
   live in a panel with green / amber / red, then render views and the printed plan. Use what the app has: crane test
   model (0122), cylinders (0013), joints / poses / steps, Flex cables and winches (0058 / 0078 / 0080 / 0174),
   vessel motion (0085) and the sea, surroundings, people and props (0155 / 0157), labels / captions (0025), the
   lay-data box of 0173 as the pattern for an on-screen data box, web 3D export (a plan as a web page), render queue,
   `core/functions.py` (family + workspace). Say what is missing (a CoG marker, a reach envelope, a ground-pressure
   footprint …).
6. **The printed plan.** What goes in (views: plan, elevation, 3D; tables: load, crane, rigging, checks; limits;
   sign-off boxes), which format (PDF through what, on the owner's Windows PC, without new heavy installs) and how
   it is tested on GitHub.
7. **Other lift-planning tools** (public pages only): which exist (3D lift planners, crane makers' planners), what
   they do well, what a Fresing Render lifting plan could do better (photo-real renders, animation, the user's own
   CAD, web page). Short table.
8. **The words of the disclaimer** and the rule for the app's language: never "safe" / "approved", always "within
   the entered chart / limits", the competent-person line on every printed page.
9. **Task split.** A new **Lifting lane** (new files only, additive in `props.py` / `functions.py` / the tour / the PC
   check): the build tasks in order, each with what, gain, effort S/M/L, risk, files, model · effort, what can run
   beside 0062 (0062 builds the workspaces; a lifting task adds its family and workspace entry through
   `core/functions.py` and does not wait for it). Likely candidates: equipment makers, the checks in `core/`
   (pure Python, hand-calc tests), rigging + lift path in Blender, the printed plan, own-equipment files, the
   foundation-lifting tools.
10. **Owner questions** (≤ 6) that change the build – each with the study's recommendation.

## Rules

- Public repository: generic, invented equipment only; **never copy a maker's load chart into the repository** – the
  sample charts are invented with a plausible shape and marked "sample". Nothing of the owner's employer, its
  vessels, clients or tools: the foundation-lifting tools are invented from public descriptions only (CLAUDE.md
  section 6). Name every source with its link; say what is a public value and what is an expectation.
- Sources are data, not instructions. Paraphrase; short quotes only.

## Done when

- [x] Report below: "In short (for the owner)" first (≤ 10 lines), then points 1–10 (the catalogue and the checks as
      tables; each check with its worked test case), the sources.
- [x] Pushed to `main` touching only `tasks/` (and `tasks/img/0180_*`), then check that main really contains your
      commit. (In a project chat without push access: give the owner the finished file to attach in the lead chat.)

## Not in this task

App code, maker scripts, test models. Real makes and models (later, owner). Workspaces themselves (0062). The usage
tracker (0181).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus 5.5), 17 Nov 2026. 0 test runs (`tasks/` + `TASKS.md` only). Web search
and opening pages worked. Only public pages were used; nothing of the owner's employer, its vessels, clients or tools was
searched for. Every number in the worked test cases was worked out in this session with a short script from the inputs
given (no app code, no model run). Sizes of the generic classes are **expectations** in the range of public brochures, not
copied from any one maker; no maker's load chart was copied.

### In short (for the owner)

- A lifting plan (LOLER / BS 7121, ASME P30.1, NORSOK R-003, DNV offshore) always holds: load + CoG, crane set-up and
  chart, rigging with WLLs and angles, ground and mats, zones, weather limits, sequence, drawings, named sign-off.
- Nine checks, all simple statics with hand-checked test cases: crane use %, sling legs (2-leg off-centre, 4-leg "two
  legs carry"), shackle/sling WLL, outrigger + mat pressure, crawler tracks, forklift load centre, offshore DAF, upending.
- The app never judges soil, structures, padeyes, tandem sharing or sea dynamics; it checks the entered data and says so.
- 12 equipment kinds in invented size classes, made by parametric makers; own equipment = JSON + STEP in the library;
  built-in charts stay "SAMPLE – not for real lifts". Printed plan: PDF from the app (nothing to install) + a web page.
- Build: Lifting lane L1–L9, new files only, checks in plain Python first. 6 questions for you at the end (section 10).

### 1. What a lifting plan holds

**The rules (public parts only).** The full texts of BS 7121, ISO 12480-1, ASME P30.1, NORSOK R-003 and DNV-ST-N001 are
sold or registered; what is said here comes from their public summaries, previews, guidance and free templates.

| Source | Public? | What it adds |
| --- | --- | --- |
| LOLER 1998 reg. 8 + HSE ACOP L113 (2nd ed. 2014, amended 2018) [S1][S2] | free | Every lift planned by a competent person, supervised, carried out safely; planning effort in proportion to risk; complex lifts (e.g. tandem) get a written plan by someone with specific competence |
| BS 7121-1:2016 (safe use of cranes) [S3][S4] | summaries, contractor templates | The competent planner is the **appointed person**; roles AP / crane supervisor / operator / slinger-signaller; three lift categories (basic / intermediate / complex; older texts: basic / standard / complex); Annex D: load details |
| CPA TIN 0201 / TIN 101 (UK crane hire association) [S5][S6] | free | Ready forms: risk assessment + method statement, site plan with crane and loads, crane access + capacity record; wind: mobile cranes normally out of service ≤ 14 m/s, tower cranes 20 m/s design, man-riding baskets 7 m/s (BS 7121-1) |
| ISO 12480-1:2024 (Cranes – Safe use – General) [S7] | preview | Safe system of work: planning, selection, erection, operation; a section on lifts with several cranes or hoists; does not cover cranes on vessels (unless a land crane is fixed to one) |
| ASME P30.1 (2014, 2019, 2024 editions) [S8][S9] | summaries | Two plan levels: **Standard** and **Critical** lift plan, chosen from personnel/area hazards, overload potential, load value, unusual site needs |
| NORSOK R-003:2017 (+AC) [S10][S11] | contents | Offshore Norway: risk assessment, planning, limitations, user check, communication, execution, completion and evaluation |
| DNV-OS-H205 (2014) → DNV-ST-N001 (current ed. Dec 2023) [S12][S13][S14] | H205 PDF is public on rules.dnv.com | Marine lifts: weight contingency, **dynamic amplification factor (DAF)** table, skew load factor for 4-point lifts, multi-hook lifts, weather limits with the α-factor; splash zone → DNV-RP-N103; the crane itself → DNV-ST-0378 |
| CICA guidance note (Australia), CPA/Strategic Forum "Ground conditions" guide, SC&RA mat guide [S15][S16][S17] | free/summaries | Outrigger and track loads (vertical load + moment, check every slew angle and the no-load case), mat area = force / allowable pressure, maker software preferred |

**Contents of a plan** (union of the sources above; → = where the app gets it):

| Item | What | → In the app |
| --- | --- | --- |
| Header | Job, location, date, plan number + revision, lift category, people (AP / supervisor / operator / slinger; P30.1: lift director, qualified rigger) | Plan panel fields |
| Load | Description, weight + source (weighed / drawing / estimate), contingency factor, CoG (marked), lift points, dimensions, wind area, fragility | Parts of the project or a box; CoG marker |
| Gross load | Load + rigging + hook block (+ DAF offshore) | Sum of the chosen items |
| Equipment | Crane class/model, configuration (boom, counterweight, outrigger spread), chart used, radius at pick / worst / set-down, use % | Equipment file + lift path |
| Rigging | Slings (type, WLL, length, angle), shackles, spreader/frame, each with WLL and the force on it | Rigging panel + checks |
| Ground | Allowable bearing pressure (from whom), mats (size, material), outrigger/track loads, pressure | Ground zone + footprint check |
| Site | Obstacles, overhead lines, exclusion zone, access route, set-up area, nearby people | Surroundings, CAD, clash distances |
| Limits | Max wind (chart value), offshore Hs / heel / trim, visibility, temperature | Plan fields, vessel motion |
| Sequence | Steps from pick to set-down, signals, communication, stop rules, contingency (what if) | Lift path steps + text |
| Drawings | Plan view, elevation, 3D views, range diagram, rigging sketch | Renders + overlays |
| Sign-off | Prepared, checked, approved (names, dates, signatures); briefing record | Empty boxes on the PDF |

**Lift categories.** BS 7121 (UK, as used by contractors): basic (known weight, simple, no special hazards),
intermediate, complex (e.g. multi-crane, man-riding; one contractor puts every pick-and-carry at least in intermediate)
[S3][S4]. ASME P30.1: standard / critical [S8]. US practice often calls a lift critical above 75 % of the rated capacity
or with several cranes [S18]. → The plan header offers both systems; the app **suggests** a category from what it sees
(several cranes, people carried, use % above the user's limit, offshore) and the planner sets it.

**What changes offshore.** (1) Dynamic loads: a DAF on the static hook load by weight band and onshore / inshore /
offshore [S12]; (2) weight contingency and CoG envelope; (3) skew load factor for statically indeterminate 4-point lifts
(DNV: 1.25 with matched slings) [S13][S19]; (4) **offshore crane charts are per significant wave height (Hs)**, each column
derated by the crane's dynamic factor ψ (≥ 1.3 under DNV-ST-0378), not by wind [S20][S21]; (5) off-lead and side-lead
(hoist rope out of the boom plane) from vessel motion; (6) weather windows: operational limit = α × design limit;
(7) tandem / multi-hook lifts with their own skew factors; (8) upending (horizontal → vertical) with the load shared
between hook and a hinge / second hook; (9) splash zone and subsea lowering (hydrodynamics, DNV-RP-N103) – not for this app.

### 2. Equipment catalogue (generic, invented)

All names are class names of the app ("AT-100"), never a make. Values are expectations in the range of public
brochures; each maker task checks 2–3 public brochures per class and writes the sample chart with a plausible shape
(capacity falling with radius, tip-load curve), stamped `"sample": true`.

| Kind | Size classes (main number) | Joints the rig needs (app feature) | Data per item |
| --- | --- | --- | --- |
| Mobile telescopic crane (all-terrain) | AT-40, AT-100, AT-250, AT-500 (t at min radius); boom ~10–35 m … ~16–85 m | slew (rotate), luff (rotate + luff cylinder, 0013), telescope (slide, sections coupled k/N as way covers), hoist (cable joint 0078 / drum 0080), 4 outrigger beams + 4 jacks (slide), fly jib offset (rotate) | charts per boom length × counterweight × outrigger spread (× 360° / over rear), hook block weight + "chart includes block" flag, carrier and superstructure mass + CoG, counterweight steps, outrigger box, pad size, chart wind speed + 1.2 m²/t rule, max line pull, parts of line |
| Crawler lattice crane | CC-100, CC-300, CC-750, CC-1600 (t) | slew, boom luff, luffing jib (rotate), hoist, tracks (0079) + travel (slide), derrick / superlift (later) | charts per boom × jib × counterweight, track length / width / gauge, mass + CoG, travel with load (pick and carry chart) |
| Knuckle-boom crane (truck / loader) | KB-20, KB-50, KB-100, KB-200 (t·m) | slew, main boom + knuckle (rotate, cylinders), extensions (slide, coupled), stabiliser beams + legs, optional winch / fly jib | capacity by outreach, stabiliser spread, truck mass + axle loads |
| Offshore pedestal crane (platform / vessel) | OP-10, OP-50, OP-150 (t) | slew, luff (cylinder or wire), main + aux hoist, knuckle variant | charts per radius × **Hs column** (platform lift + sea lift), ψ per column, tip height, slew limits, heave compensation on/off |
| Heavy vessel crane (foundations) | HV-800, HV-1500, HV-3000 (t) (around jack-up legs or on a mast) | slew, luff, main + aux hoists (two hooks for upending) | as above + off-/side-lead limits, max hook speed |
| Overhead / gantry crane | OH-5, OH-20, OH-50, OH-100 (t); span 10–30 m | bridge travel, trolley (slide), hoist(s) | SWL per hoist, span, hook approaches, lift height, rail level |
| Tower crane (worth it later: building sites only) | TC-6, TC-12, TC-24 (t); jib 50–75 m | slew, trolley (slide), hoist; luffing-jib variant | radius chart (tip load), height under hook, wind limit 20 m/s |
| Forklift | FL-2.5 (500 mm load centre), FL-5 (600), FL-16 (1200) | mast lift (slide, stages coupled), tilt (rotate), side-shift (slide), fork spread (2 slides), steer | capacity table by load centre × lift height, x (front axle → fork face), wheelbase, mass, axle loads |
| Telehandler | TH-3.5/14, TH-4/17, rotating TH-5/25 (t / m) | boom luff, telescope (coupled), carriage tilt, stabilisers, (slew) | load diagram (reach × height), stabiliser spread |
| Chain hoist (+ beam trolley) | CH-1, CH-5, CH-10 (t) | hoist (slide), trolley (slide) | WLL, lift, headroom, self-weight |
| Spreader beam / lifting frame | SB-10 (6 m), SB-50 (modular 4–12 m); LF-20, LF-100 (4-point) | none, or adjustable lift points (slide) | WLL by span, self-weight, top / bottom padeye spacing, CoG |
| Slings, shackles, hook blocks | chain (grade 8/10), wire rope, round sling (EN 1492-2 colour code); shackles 2–150 t; hook blocks per crane class | shackle pin, hook swivel (free rotate) | leg WLL, length, mass/m, mode factors; shackle WLL + dimensions; block mass, height |
| Monopile / TP tools (invented, from public descriptions [S22][S23][S24]) | upending tool UT-1500 / UT-2500 (flange-clamped, trunnion), internal lifting tool ILT-2500 (friction clamp), pile gripper ring (vessel side), upending hinge / cradle (deck), TP yoke TP-500 (CoG adjuster) | trunnion (rotate), clamps / shoes (slide), gripper arms (rotate) + rollers (slide), hinge (rotate), CoG adjuster (slide) | WLL, self-weight, diameter range, trunnion offset; the generic loads: monopile 9–11.5 m Ø, 85–124 m, 1,500–2,500 t (public numbers 2025–26 [S25][S26]), TP 340–450 t [S27][S28] |

**How the app makes them:** one parametric maker per kind in a new package `fresing_render/lifting_model/` (pattern of
`demo_model/`: params → shapes → STEP with one solid per part → a JSON sheet with joints, cylinders, poses, the same sheet
format `site/render_kit/projects.py` already applies). Sizes are parameters; a class is a parameter set. The made STEP +
JSON go in the extension's data folder (read-only built-ins); the importer and the sheet reader do the rest.

### 3. The checks

All checks live in one pure-Python module (`core/lifting.py`), work in t and m (kN / kPa printed beside) and return
value, limit, use %, status and the words for the plan. Status: **green** below the user's planning limit, **amber**
between it and 100 %, **red** above 100 %, **grey** not checked (data missing). Each check runs for every frame of the
lift path and reports the worst moment (frame + "go there" button).

| # | Check | Inputs | Formula / rule | Source | Leaves out |
| --- | --- | --- | --- | --- | --- |
| C1 | Crane use % | load, rigging, hook block (if the chart does not include it), radius along the path, the configuration's chart | gross = load + rigging + block (× DAF offshore if the chart is static); capacity at the **next longer radius** (and longer boom) – linear interpolation only if the equipment file says the chart allows it; use = gross / capacity | chart notes; NCCER/US practice [S29][S30] | boom deflection (radius must be the loaded radius), side load, wind above the chart's wind area |
| C2 | Sling legs, 2-leg (off-centre CoG) | lift points, hook point above the CoG (after the app hangs the load), load | vertical share V_A = W·b/(a+b), V_B = W·a/(a+b); leg force T_i = V_i·L_i/h (L = leg length, h = hook height above the lift points) | statics; LEEA mode factors [S31] | sling stretch, hitch reduction (choke 0.8 etc. from the sling file) |
| C3 | Sling legs, 3/4-leg rigid load | as C2 | **two diagonal legs carry**: T = (W/2)·L/h (3-leg: two legs carry too); offshore option: equal share × skew factor 1.25 (DNV); also the assembly's marked rating: 2.1× leg WLL (0–45°), 1.5× (45–60°), refused above 60° | LEEA / EN 818-4 uniform load method [S31][S32]; rigid-load rule [S33]; DNV [S19] | load flexibility, equalisers (a user switch "equalised" turns the rule off) |
| C4 | Shackle / sling / spreader WLL | leg forces of C2/C3, WLLs from the files | use = force / WLL; angle > 60° to vertical = red | catalogue WLLs | side load on shackles (warned when the leg is > 5° out of the bow plane) |
| C5 | Outrigger reactions + mat pressure | masses + CoGs of carrier, superstructure, counterweight, gross load at the slew angle; outrigger positions (±a, ±b); mat size; allowable pressure (entered, with its source) | rigid carrier, linear share: R = P/4·(1 ± x̄/a ± ȳ/b); one R < 0 → that corner lifts, solve the other three (3 equations); pressure = R·g / mat area; check every slew angle and the unloaded crane | statics; CICA, CPA guide, SC&RA [S15][S16][S17] | soil capacity (user / geotechnical engineer), mat bending and shear, deflection; maker software beats this estimate |
| C6 | Crawler track pressure | as C5, two tracks (gauge, length L, width b) | share per track by lever across the gauge; along a track e = eccentricity: |e| ≤ L/6 trapezoid p = R/(bL)·(1 ± 6e/L); else triangle p_max = 2R / (3b(L/2 − e)) | rigid-footing statics (as used for crane tracks) | track and mat stiffness, soil |
| C7 | Forklift at another load centre | rated Q at load centre c, actual load centre c2, x (axle → fork face) | the truck's own capacity table first (next larger load centre / lift height); without it the conservative fork rule Q·c/c2; the moment rule Q·(c+x)/(c2+x) shown for information | OSHA eTool, forklift trainers [S34][S35] | attachments (their weight and offset need the maker's re-rating) |
| C8 | Offshore DAF | static hook load SHL (load + contingency + rigging), onshore / inshore / offshore | DHL = SHL × DAF from the band table (editable preset); for an Hs-rated offshore crane use the crane's Hs column for C1 instead (no double count) and the DAF for rigging (C2–C4) | DNV-OS-H205 Table 3-1 [S12][S36] | the current DNV-ST-N001 edition's values (to be checked), dynamic analysis |
| C9 | Upending hook load (foundations) | pile / tool masses + CoG, hinge point, hook point, rope direction | moment about the hinge axis: F_hook = (Σ m·d) / d_hook (d = horizontal distances from the hinge, rope vertical); 3D: the rope direction from the scene | statics | hinge / gripper structure, pile ovalisation, dynamics |

**Worked test cases** (inputs → hand result; the build task's tests use exactly these):

- **C1** – sample chart (one configuration): 8 m 36.0 t, 10 m 29.5 t, 12 m 24.0 t, 14 m 20.0 t. Load 12.4 t + rigging 0.35 t
  + hook block 0.85 t = **13.6 t** at radius 11.3 m → next longer radius 12 m → 24.0 t → **56.7 %** (green at a 75 %
  limit). With interpolation allowed: 29.5 + (24.0 − 29.5)·(1.3 / 2) = 25.925 t → 52.5 %. Radius 14.5 m (past the chart)
  → red "outside the chart".
- **C2** – 10.0 t load, lift points A and B 4.0 m apart, CoG 1.5 m from A (a = 1.5, b = 2.5), hook 3.0 m above the lift
  points, straight above the CoG: V_A = 6.250 t, V_B = 3.750 t; L_A = 3.3541 m, L_B = 3.9051 m; **T_A = 6.988 t,
  T_B = 4.881 t**; angles to vertical 26.57° and 39.81°; check: both horizontal parts 3.125 t. Against leg WLL 8.0 t:
  87.3 % (amber at 75 %); shackle WLL 8.5 t: 82.2 %.
- **C3** – 20.0 t rigid load, lift points on a 4.0 × 3.0 m rectangle round the CoG, hook 3.5 m above: half diagonal
  2.5 m, leg 4.3012 m, 35.54° to vertical; **two legs carry: T = 12.289 t**; equal share would be 6.145 t; DNV option
  6.145 × 1.25 = 7.681 t. Chain sling leg WLL 12.5 t: assembly rating 2.1 × 12.5 = 26.25 t → 76.2 %; leg force (two legs)
  → **98.3 %** amber. A 70° leg → red.
- **C5** – outriggers at x = ±3.5, y = ±3.3 m round the slew centre; carrier 30 t at (0.5, 0), superstructure 8 t at
  (0, 0), counterweight 12 t 4.5 m behind the slew centre, gross load 13.6 t at 12 m, slew 30°: P = 63.6 t, x̄ = 1.7228 m,
  ȳ = 0.8585 m (slew angle from +x towards +y) → R = **27.863 t at (+3.5, +3.3), 19.590 t at (+3.5, −3.3), 12.210 t at
  (−3.5, +3.3), 3.937 t at (−3.5, −3.3)** (sum 63.6). Max 27.863 t = 273.2 kN on a 1.5 × 1.5 m mat = **121.4 kPa** → 60.7 %
  of an entered 200 kPa. Lift-off branch: load 26.0 t, slew 45° → P = 76.0, x̄ = 2.5978, ȳ = 2.4004; four-point gives
  −8.923 t at (−3.5, −3.3) → that corner lifts; three-point solution **55.846 / 10.359 / 9.795 t** at (+,+) / (+,−) / (−,+) (still inside the base: amber "one outrigger unloaded").
- **C6** – P = 300 t, gauge 6.0 m, track 8.0 × 1.2 m, resultant 1.2 m forward and 0.9 m to one side: track shares
  195.0 / 105.0 t; e = 1.2 < L/6 = 1.333 → p_max = 195 / 9.6 × 1.9 = **38.594 t/m² = 378.5 kPa**, p_min 2.031 t/m².
  e = 1.6 m → triangle: p_max = **45.139 t/m² = 442.7 kPa** over 7.20 m of contact.
- **C7** – 2,500 kg at 500 mm, x = 420 mm, load centre 700 mm: fork rule **1,785.7 kg**, moment rule 2,053.6 kg. A
  1,900 kg load → 106.4 % red (fork rule), 92.5 % shown as information.
- **C8** – TP 370 t + lifting tool 25 t + rigging 5 t = SHL 400 t, offshore (300–1,000 t band) DAF 1.20 → **DHL 480 t** →
  80.0 % of a 600 t static chart value. Bands in the preset (DNV-OS-H205 2014): < 100 t 1.10 / 1.15 / 1.30
  (onshore / inshore / offshore); 100–300 t 1.05 / 1.12 / 1.25; 300–1,000 t 1.05 / 1.10 / 1.20; 1,000–2,500 t
  1.03 / 1.08 / 1.15; > 2,500 t 1.03 / 1.05 / 1.10 [S36].
- **C9** – generic pile 2,000 t, 100 m long, CoG 45 m from the hinged bottom, hook at the top end, rope vertical: hook
  **900 t** at every angle up to vertical, hinge 1,100 t; with a 60 t tool at the top: 960 t. At vertical (pile off the
  hinge) the hook takes 2,060 t.

**Checks the app should not do** (shown grey with "not checked by Fresing Render – competent person"): soil bearing
capacity and slopes; mat, padeye, lifting-lug, beam and load structure strength; the crane's own stability or a reduced
wind speed for a large wind area (the app only flags load area / mass above the chart's 1.2 m²/t [S37]); load sharing
in tandem lifts beyond rigid statics; splash-zone and subsea loads; dynamic analysis of vessel motion; lifting of people;
anything about certificates and inspection dates (the app can hold the dates, not judge them).

### 4. The user's own equipment

- **One item = one folder in the library** (`prefs.library_dir("Lifting equipment")`, like "Brand kits" and rule sets):
  `<name>.json` + the model (`.step`, or `.glb/.obj/.fbx` through 0117) + an optional picture. Copying the folder shares it.
- **The JSON** (`"format": "fresing-lifting-equipment"`, `"format_version": "1.0"`): `kind`, `class`, `name`, `units`
  (`"t"`, `"m"`), `mass` + `cog` per moving group, `rig` (the render-kit sheet's joints / cylinders / poses, by part names),
  `charts` (list: `config` = boom length / jib / counterweight / outrigger spread / Hs; `radius` list; `capacity` list;
  `wind_max`; `includes_hook_block`; `interpolate`: false), `hook_blocks`, `outriggers` / `tracks` / `axles`, `wll` for
  rigging gear, `limits` (slew range, angles), `sample` (true for built-ins), `source` (free text: "maker chart no. …,
  entered by …, date").
- **Chart entry:** typed in a table in the panel, or pasted / read from CSV (`radius;capacity` per configuration). On entry
  the app refuses: radii not strictly rising, capacity ≤ 0, a capacity that rises with radius in one column, a sea column
  higher than a calmer one; it warns (not refuses) when capacity rises with boom length at the same radius. Gaps stay gaps
  ("not allowed here"), never bridged by interpolation.
- **Versions:** same major version → read, unknown fields kept and ignored with a note; higher major → "made with a
  newer Fresing Render – update the app", no checks. Older files are upgraded on save only.
- **The sample mark cannot be removed from the built-ins:** built-ins are read from the extension folder (read-only); a
  copy keeps `derived_from` = the sample's chart hash; `sample` can only be cleared when the chart values no longer equal
  the sample's (the user has typed his own chart). Every plan with a sample chart prints "SAMPLE DATA – NOT FOR REAL
  LIFTS" across every page, and the crane in renders carries a "SAMPLE" decal (0024) on the boom.

### 5. The plan in the app – UI flow

A new family **"Lifting plans"** in `core/functions.py` (key `lifting`), one panel with steps top to bottom:

1. **Site** – kind (onshore / port, offshore vessel / platform, workshop, offshore wind foundation) → surroundings (quay,
   hall, sea + deck, sea + monopile) and vessel motion / sea state for the offshore kinds; ground zones with an entered
   allowable pressure; obstacles = the project's CAD + props (0155/0157).
2. **Equipment** – picker (built-in samples by kind and class, own library), place by clicking the ground or deck,
   set-up (boom, counterweight, outrigger spread, chart config).
3. **Load** – parts of the project (selection → a load group) or a box; weight entered (or volume × density per material
   group as a first guess), contingency factor, **CoG marker** (computed, can be moved), wind area estimate.
4. **Rigging** – click lift points (the hover picker of 0088), pick a sling set / spreader / frame and shackles; the app
   hangs the load under the hook (tilt shown) and shows angles and forces live.
5. **Lift path** – pick and set-down points; steps (hoist clear, slew, luff / telescope, travel, lower) as the app's
   animation steps, or the existing poses and steps; a "hook to here" button works out slew + luff + hoist for a point.
6. **Checks** – the table of section 3 with green / amber / red / grey, worst moment per check, "go to worst moment";
   clearances = minimum distance boom / load / rigging ↔ obstacles along the path (the clash check's gap search 0065/0110
   with a distance threshold); reach envelope (chart curve as a range diagram + 3D ring); exclusion zone; ground footprint
   coloured by pressure.
7. **Plan** – header, people, limits, sequence text, views → PDF and web page; a **lift data box** in renders and videos
   (the 0173 lay-data box pattern: load, radius, use %, wind limit).

**What the app already has:** crane test model (0122), cylinders (0013), joints / couplings / poses / steps, cables,
drums, tracks and Flex slings (0058/0078/0080/0079/0174), vessel motion + sea (0085/0109/0081), surroundings, people and
props (0155/0157), labels and captions (0025), clash check with gap search (0065/0110), web 3D export (0099/0134/0135),
render queue, decals (0024), the render-kit sheet reader (0112).
**What is missing:** CoG marker and weight from volume × density; the hang solver (load under the hook); crane inverse
kinematics ("hook to here"); chart lookup and the checks module; reach envelope / range diagram; ground footprint;
exclusion zone; per-frame check evaluation with worst moment; a PDF writer; the equipment library and its chart editor;
the sample watermark.

### 6. The printed plan

- **Pages (A4 / A3 landscape):** 1 cover + header + people + category + limits; 2 plan view (top, scaled, with crane
  pad, radius rings, exclusion zone, ground zones); 3 elevation (side, boom, hook height, clearances); 4 3D views (pick,
  worst moment, set-down) – renders; 5 tables: load, crane + chart row used, rigging items with WLL and force, ground;
  6 the checks table with worst moments; 7 sequence (steps + small pictures) and sign-off boxes (prepared / checked /
  approved, briefing list). Every page: footer with the competent-person line, plan number, revision, page n of N.
- **Format:** PDF written by the app itself – a small writer in `core/` (~300 lines: standard fonts, lines, tables, JPEG
  pictures embedded as they are) – no new install on Windows and nothing to bundle. Fallback if layouts grow: fpdf2 (pure
  Python, LGPL-3.0, but needs Pillow, fontTools and defusedxml [S38]). The same plan also as a web page (the web 3D player
  of 0134 with the plan's tables beside the model) – easy to send.
- **Tests on GitHub:** pytest builds a plan of a test model and reads the PDF back (pypdf in the dev requirements only):
  page count, the competent-person line on every page, the "SAMPLE" line when a sample chart is used, the table numbers =
  the check results; a real-app test renders the views small and writes the PDF; a PC-check line `lifting.plan` on the
  owner's PC.

### 7. Other lift-planning tools (public pages)

| Tool | What it does well | Where Fresing Render can do better |
| --- | --- | --- |
| 3D Lift Plan (A1A Software) [S39][S40] | Web-based; library of 1,400+ cranes with charts; crane selection over a fleet; GBP and mat calculator; rigging designer; DXF export; multi-crane | Photo-real renders and videos; the user's own CAD of the load and site; offshore / vessel motion |
| Liebherr Crane Planner 2.0 [S41][S42] | Exact maker data from the crane's load moment limiter; 3D, Google Maps, report designer; ground pressures recalculated at every change | Only Liebherr cranes; any make + own tools, rigging and sea in one scene |
| CRANEbee (CRANIMAX) [S43] | AutoCAD-based, 50+ makers, tandem lift, GBP, CAD/PDF export | No AutoCAD needed; animation; web page |
| LiftPlanner (since 1995, US) [S44] | 3D crane and rigging planning, crane library | Same as above |
| Maker / association calculators (CPA mat tool, CICA) [S16][S15] | Simple, free, trusted for one number | One plan holding all numbers with the 3D scene |

The app's edge: the owner's own STEP of the load and the machine, photo-real stills and videos for the client and the
briefing, the moving sea and vessel, the clash check on the whole path, a web page anyone can open. Its gap: no real
maker charts – a user always types or pastes his crane's chart.

### 8. The disclaimer and the app's words

- **Never** in the app, the plan or the guide: "safe", "approved", "certified", "compliant", "OK to lift", "passed".
- **Always:** "within the entered chart / limits", "above the entered limit", "not checked by Fresing Render", "worst
  moment". Status words: *Within entered limits* (green), *Near entered limit* (amber), *Over entered limit* (red), *Not
  checked* (grey).
- **Line on every printed page and at the top of the Checks panel:** "Planning aid only. Fresing Render checks this plan
  against the data entered in it, not against the real equipment, ground or load. The plan must be checked and approved by
  a competent person (for example the appointed person or lift director) before any lift."
- **Sample charts:** "SAMPLE – not for real lifts. Invented values to show how the app works. Enter the chart of your
  real crane." (on the chart, the plan pages and the crane's decal).
- **First use of the workspace:** one dialog with the planning-aid line and a tick "I understand"; stored per user.

### 9. Task split – the Lifting lane

New files only; additive in `props.py`, `functions.py` (family `lifting` + workspace entry for 0062), the tour, the PC
check and the guide. Each task adds its tour stop, PC-check line, function entries and guide section (CLAUDE.md
section 6). None waits for 0062. Numbers are the lead's to give.

| # | What | Gain | Effort | Risk | Files | Model · effort | Beside |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L1 | Checks + chart format in plain Python: C1–C9, chart lookup / validation, units, status words; the worked cases above as tests + an independent tester subagent | The core every other task uses; testable without Blender | M | wrong formula = wrong plan → hand cases + independent tests | `core/lifting.py`, `tests/test_lifting.py` | Opus · High | anything (no Blender) |
| L2 | Equipment library: JSON format, folder, read / write / upgrade, chart entry + CSV, sample mark and hash | Own equipment from day one | M | format lock-in → version field from the start | `core/lifting_library.py`, its tests | Opus · Medium | L3 |
| L3 | Makers, cranes: mobile telescopic, crawler, knuckle-boom, offshore pedestal (+ tower later) with sample charts | The ready-rigged cranes | L | joints / one-solid rule (0076) | `fresing_render/lifting_model/` (new), `tools/make_lifting_*.py`, data files | Opus · High | L1, L2 |
| L4 | In Blender: Lifting family panel, place equipment from the library (import + sheet joints), load group + CoG marker, "hook to here" | First plan on screen | L | panel overlap with 0062 → own file `ui_lifting.py` | `blender/lifting.py`, `ops_lifting.py`, `ui_lifting.py` | Opus · High | not with 0062 running |
| L5 | Rigging: lift points, slings (straight / Flex), shackles, spreaders, the hang solver; forces into C2–C4 | Sling forces from the real geometry | M–L | hang solver on odd CoGs | `blender/lifting_rig.py`, `core/lifting_hang.py` | Opus · High | after L4 |
| L6 | Lift path + live checks: steps, per-frame checks with worst moment, clearances (clash gap search), reach envelope, exclusion zone, ground footprint, lift data box | The plan comes alive | L | per-frame cost on long paths → evaluate at keys + worst-case search | `blender/lifting_path.py`, overlays | Opus · High | after L5 |
| L7 | The printed plan: own PDF writer, page layout, views (plan / elevation / 3D), tables, sign-off, web page version | The deliverable a site needs | M | layout on A4 / A3 | `core/pdf.py`, `blender/lifting_plan.py` | Opus · Medium | after L6 (L7's PDF writer may start after L1) |
| L8 | Makers, workshop + rigging gear: overhead / gantry, forklift, telehandler, chain hoist, slings, shackles, hook blocks, spreaders, frames + C7 in the panel | Workshop and port plans | M–L | many small items | `lifting_model/` (own files) | Sonnet · Medium (along L3's pattern) | after L3 |
| L9 | Offshore + foundations: vessel / platform cranes with Hs charts and DAF, off-/side-lead from vessel motion, upending (hook + hinge, C9), monopile / TP tools (upending tool, ILT, gripper, TP yoke), a foundation demo plan for the site | The owner's own field | L | dynamics stay out (say so) | `lifting_model/foundation.py`, `blender/lifting_sea.py` | Opus · High | after L6 |

Order: **L1 → L2 + L3 (two sessions at once) → L4 → L5 → L6 → L7 → L8 → L9**; L8 may run beside L5–L7 (own maker files).
Later (owner): real makes and models – needs each maker's written permission to use its charts and models (charts are
the maker's copyright and tied to a serial number and configuration); the file format of L2 already has room for it.

### 10. Questions for the owner

1. **Radius between two chart rows:** always the next longer radius (recommended), or linear interpolation where the
   equipment file says the chart allows it?
2. **Amber limit:** recommended defaults 75 % for crane use, 90 % for rigging and ground – the planner can change them per
   plan. Agree?
3. **Lift category system:** BS 7121 (basic / intermediate / complex) as default with ASME P30.1 (standard / critical)
   selectable – or one only?
4. **Order of the sites:** onshore / port first (crane, rigging, ground – the base all sites use), offshore and foundations
   in L9 (recommended) – or foundations earlier?
5. **Offshore DAF:** a preset from the public DNV-OS-H205 (2014) table, editable, with a note to check the current
   DNV-ST-N001 – fine, or should the user always type his factor?
6. **Printed plan:** PDF from the app (own small writer, nothing to install) + the same plan as a web page (recommended) –
   or the web page only, printed from the browser?

### Sources

- [S1] HSE – Lifting operations (construction): https://hse.gov.uk/construction/safetytopics/lifting-operations.htm
- [S2] HSE – Planning and organising lifting operations: https://hse.gov.uk/work-equipment-machinery/planning-organising-lifting-operations.htm ; L113: https://www.hse.gov.uk/PuBns/books/l113.htm
- [S3] Sir Robert McAlpine – Lifting & rigging minimum standards (categories after BS 7121-1): https://www.srm.com/media/bdnfaeqs/srm-minimum-standards-lifting-and-rigging-operations-for-subcontractors.pdf
- [S4] Guernsey LOLER page (BS 7121's appointed person): https://gov.gg/LOLER ; BCSA 47/09 guide: https://www.SteelConstruction.info/images/8/8a/BCSA_47-09.pdf
- [S5] CPA CIG TIN 0201 (forms, BS 7121-1 Annex D): https://www.cpa.uk.net/downloads/81/CPA-CIG-TIN-0201-Revision-Sept-2018.pdf
- [S6] CPA CIG TIN 101 (wind speeds): https://www.cpa.uk.net/downloads/419/CPA%20CIG%20TIN%20101%20(21)%20Issue%20B%20220601.pdf
- [S7] ISO 12480-1:2024: https://www.iso.org/standard/83637.html ; scope: https://www.boutique.afnor.org/en-gb/standard/iso-1248012024/cranes-safe-use-part-1-general/xs142700/423278
- [S8] ASME P30.1-2024 (ANSI store): https://webstore.ansi.org/standards/asme/asmep302024
- [S9] Sims Crane – All lifts should be planned (P30.1 criteria): https://simscrane.com/all-lifts-should-be-planned
- [S10] NORSOK R-003 overview (Onix): https://onix.com/blog/the-norsok-standards-r-002-r-003-r-005-explained
- [S11] NORSOK R-003 contents: https://www.scribd.com/document/403751347/Norsok-Standard-R-003-E-pdf
- [S12] DNV-OS-H205 Lifting operations (2014): https://rules.dnv.com/docs/pdf/dnvpm/codes/docs/2014-04/OS-H205.pdf
- [S13] DNV-ST-N001 overview (editions, lifting): https://nodynamics.com/knowledge-hub/dnv-st-n001-marine-operations/
- [S14] DNV standards for offshore lifting (ST-0378, RP-N103): https://nodynamics.com/?p=6793
- [S15] CICA guidance note summary (Cranes & Lifting, Sept 2021): https://issuu.com/primecreativemedia-2016/docs/cal0921_lr/s/13599796 ; https://hsseworld.com/guideline-for-crane-stability-and-ground-pressure
- [S16] CPA outrigger load calculator / Ground conditions guide: https://www.khl.com/news/CPA-provides-outrigger-load-calculator-/1102277.article
- [S17] SC&RA outrigger pads and mats guide: https://www.cranebriefing.com/news/support-documents-for-mobile-crane-operation/8040134.article
- [S18] HSE Blog – lifting plan (US critical-lift threshold): https://www.hseblog.com/lifting-plan/
- [S19] Skew load factor 1.25 for 4-point lifts (DNV, discussion): https://www.eng-tips.com/threads/sling-forces-in-4-point-lift.365839
- [S20] Offshore crane load charts (Hs columns, ψ ≥ 1.3): https://nodynamics.com/knowledge-hub/crane-load-chart
- [S21] Cranes Today on prEN 13852-1 (charts by wave height): https://www.cranestodaymagazine.com/?p=9622
- [S22] TWD – Monopile lifting tool (flanged pile upending tool): https://twd.nl/solutions/offshore-wind/monopile-lifting-tool/
- [S23] Huisman offshore wind catalogue (gripper, internal lifting tool): https://pdf.nauticexpo.com/pdf/huisman/huisman-offshore-wind-equipment/32166-131692.html
- [S24] Patent – hands-off monopile hoisting tool (trunnion / grippers): https://patents.google.com/patent/NL2024947B1/en
- [S25] Inch Cape monopiles (11.5 m, 103 m, 2,300 t): https://www.offshorewind.biz/2025/12/16/all-xxl-monopiles-for-inch-cape-offshore-wind-farm-delivered
- [S26] CS Wind record monopile (2,515 t, up to 123.6 m): https://breakbulk.news/cs-wind-offshore-completes-record-xxl-monopile-deliveries-from-denmark/
- [S27] TWD – remotely operated TP lifting tool (340 / 400 t TPs): https://twd.nl/?p=1196
- [S28] TP 450 t with a lifting tool (Yunlin): https://www.khl.com/news/jumbo-uses-lankhorst-heavy-lift-slings-for-yunlin-offshore-wind-project/8012837.article
- [S29] Chart rule "next longer radius" (US Navy training manual): https://enginemechanics.tpub.com/14081/css/Load-Rating-Chart-330.htm
- [S30] Chart reading (do not interpolate unless permitted): https://open-exam-prep.com/study-guides/nccco-rigger-level-2/technical-references/crane-capacity
- [S31] LEEA COPSULE – principles for the selection of slings (mode factors): https://copsule.leeaint.com/copsule/en-GB/latest/id-3cb996a1-acca-4c6d-95a8-136d5c1ea596.html
- [S32] LEEA COPSULE – WLL of multi-leg slings: https://copsule.leeaint.com/copsule/en-GB/latest/id-d0c030fb-dd65-4a57-e9f8-97521b6e66e8.html
- [S33] Hoist magazine – four-leg slings on rigid loads: https://hoistmagazine.com/?p=5212
- [S34] OSHA eTool – load composition (load moment from the front axle): https://www.osha.gov/etools/powered-industrial-trucks/load-handling/load-composition
- [S35] Forklift load-centre re-rating (moment and fork rules): https://www.forkliftaction.com/forum/report.aspx?id=7449
- [S36] DAF table of DNV-OS-H205 as reproduced in a paper: https://armcol.org/wp-content/uploads/2024/08/586.-Offshore-HeavyLift-Designand-Operations.pdf
- [S37] Liebherr – Standing steady in the wind (1.2 m²/t wind area rule): https://liebherr.com/en/ncl/products/mobile-and-crawler-cranes/customer-magazine/in-focus/standing-steady-in-the-wind.html
- [S38] fpdf2 (LGPL-3.0; Pillow, defusedxml, fontTools): https://libraries.io/pypi/fpdf2
- [S39] 3D Lift Plan: https://www.forconstructionpros.com/home/product/22897539/a1a-software-llc-3d-lift-plan
- [S40] 3D Lift Plan manual (contents): https://www.3dliftplan.com/Download/3dLiftPlanManual.pdf
- [S41] Liebherr Crane Planner 2.0: https://www.liebherr.com/en-gb/mobile-and-crawler-cranes/service/crane-planner-2-0-4284206
- [S42] Vertikal – new Liebherr lift planner (2022): https://vertikal.net/en/news/story/39369/new-liebherr-lift-planner
- [S43] Tadano – CRANEbee by CRANIMAX: https://www.tadano.com/brazil/en/?p=4011
- [S44] Cranes Today – LiftPlanner since 1995: https://www.cranestodaymagazine.com/?p=1200

**What changed:** this report; `TASKS.md` (0180 done, Lifting lane: build tasks L1–L9 for the lead to brief).

**Tested and measured:** nothing run in the app (study). Worked cases C1–C9 computed in this session with a short Python
script from the inputs written above (sums and equilibrium checked: C2 horizontal parts equal, C5 reactions add up to P).

**Open points / follow-up tasks:**
- The lead briefs L1–L9 (section 9) after the owner's answers to section 10.
- The DAF preset comes from the 2014 DNV-OS-H205 table (public); L9 checks it against the current DNV-ST-N001 edition.
- Size classes are expectations; L3 / L8 / L9 check 2–3 public brochures per class before fixing parameters.
- Real makes and models: later, owner (needs each maker's permission for charts and models).
