# 0104 – Joints from Inventor constraints: design study (findings only, no app code)

**Who:** worker · **Status:** running · **Branch:** `task/0104-inventor-constraints-study`
**Started by:** lead chat, 13 Nov 2026 (study 0069 #10; owner 12 Nov: his assemblies mostly use **constraints**, not
joints)
**Lane:** none – a study. It writes only this task file, `tasks/img/0104_*` if useful, and draft scripts under
`tools/inventor/` (new folder: an Inventor iLogic rule / VBA macro and, if cheap, a Fusion script – not part of the app,
not run by any test). No app code, so it runs beside everything.
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

A tested design (and a draft Inventor script the owner can run) for bringing the motion the owner already set up in
Inventor into Fresing Render: after a STEP import (and after every model update) the app makes the joints – turn axes,
slides, their limits – that the assembly's constraints leave free, instead of the owner clicking holes again.

## Background

- **STEP carries no joints or constraints** (0069 #10, sources [22]–[25] in its report). The app matches parts to
  Inventor occurrences by their names (`fr_instance`, e.g. "Frame:1"; the path of subassemblies in the tree), so a
  side file next to the STEP can name them.
- **The owner uses classic constraints**: Mate, Flush, Angle, Tangent, **Insert**, Transitional, Symmetry, and
  sometimes assembly joints. Typical: a pin in a hole by **Insert** (leaves a turn); two Mate/Flush pairs (leave a
  slide); an Angle constraint as a driven angle or with limits; a hydraulic cylinder made of two parts with Mate axis +
  a free slide. Constraint **limits** (Inventor's "Use limits" on Mate/Angle) may hold the travel.
- The Inventor API has more than the constraint list: e.g. `ComponentOccurrence.GetDegreesOfFreedom` (counts and
  vectors of the translations and rotations left, plus a DOF centre) – **check whether it gives exactly the axes the
  app needs** (point + direction, and which parts move together: a subassembly that is rigid / flexible, parts fixed to
  each other by fully constraining). Also `AssemblyConstraint` types, `AssemblyJoint` for joints, the occurrence path
  (`OccurrencePath`), and units (cm inside the API). Fusion: `Joint`, `AsBuiltJoint`, `jointMotion`, limits. Look it up
  with web search; most pages may not open in a web session – say which sources were used and what is unconfirmed.
- The app's side: `joints.create` (kind, members, point, direction, limits, base part, stacked joints riding on another
  – task 0011), couplings, cylinders (task 0013: barrel/rod pins), model update by part IDs (0052), batch creation fast
  (0093). The demo's joint sheet (`demo_joints.json`, task 0077) is an existing JSON format for joints by part path –
  reuse it if it fits.
- **Nothing of the employer's or clients' models** may be used or committed. The owner tests the draft script on an
  assembly he makes himself for it (generic: a hinge, a slide, a pin with a cylinder) or on his own Fresing parts
  that are cleared for it – **never the Fresing 400 in the repository** (CLAUDE.md section 6).

## What to do

1. **Map constraints to joints:** for each common pattern (Insert; Mate axis–axis; Mate/Flush plane pairs; Angle with
   and without limits; Tangent on a cam; Transitional; a cylinder's two parts; a flexible subassembly; a fully
   constrained part; joints in Inventor 2027) say what joint the app should make: kind, axis (point + direction in the
   STEP's coordinates), members (which occurrences move together), base, limits, and what is left out. Decide whether
   the remaining-DOF route (`GetDegreesOfFreedom`) or reading constraints one by one is better – or both.
2. **Side-file format:** JSON next to the STEP (name, version, units mm, the STEP's coordinate frame vs Inventor's
   assembly frame, occurrence paths as the importer names them, joints with limits and "drives" – an Angle constraint
   driven in Inventor could become a motor or a pose), with a version number; how a model update uses it.
3. **Draft script** in `tools/inventor/` (iLogic rule or VBA, plain and commented for a non-programmer): walks the
   assembly, writes the JSON; numbered steps for the owner to run it (where to paste it, which button). If cheap, the
   same for Fusion (Python API).
4. **Matching to the import:** check against the importer how occurrence names and paths arrive (`importer/step_reader.py`,
   `fr_instance`, AP214/AP242 exports from Inventor 2027) – including patterns, mirrored parts, the same part many
   times, suppressed parts, and Inventor's "v8" name suffix (CLAUDE.md section 8). A small invented test assembly as
   STEP + a hand-written JSON (no Inventor here) to show the app side could read it: what `joints.create` calls would
   come out (a prototype in a scratch script is fine; no app change).
5. **Proposed task(s)** for the lead: the app's side (Import with "Joints from Inventor file", a model update keeps /
   refreshes them), model and effort, risks; and **questions for the owner** (with suggested defaults).

## Not in this task

Changing the app; joints from STEP AP242 kinematics; anything that needs the owner's or his employer's files in the
repository.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 13 Nov 2026. Branch `task/0104-inventor-constraints-study`.

**In short:** the motion in an Inventor assembly *can* come over: an iLogic rule writes every constraint, assembly joint
and occurrence (with the geometry each constraint uses, in mm in the STEP's coordinates) to `<assembly>.fresing.json`
next to the STEP; the app works out from that, in plain Python, which motions the constraints leave free and makes the
joints, the cylinder and the couplings with its own calls. A prototype does it end to end on an invented test assembly
with the app's real code (Blender as a module): 7 joints, 1 hydraulic cylinder, 1 gear coupling, the right axes and
limits, the parts move as the constraints allow (23 of 23 checks). **Not tested: the Inventor and Fusion scripts
themselves** (no Inventor here; Autodesk's help pages could not be opened from this machine) – the owner's first run
is the real test of the reading side.

### Findings

**1. Constraints, not "remaining DOF": read the constraints with their geometry; use Inventor's DOF only as a check.**
- `ComponentOccurrence.GetDegreesOfFreedom(tCount, tVectors, rCount, rVectors, DOFCenter)` gives per occurrence only the
  *directions* left free and one display centre (not a point on each axis), and it counts each part with the parts it
  is constrained to held still. It says nothing about which parts move together or what a part hangs on, and its
  centre is not guaranteed to lie on the axis. Not enough to make a joint – but a good **check**: the count the app
  works out from the file must equal Inventor's (the rule writes it for every part that has constraints).
- Each constraint holds a known set of small motions between its two parts. Written as rows of a 6-column matrix
  (turn ω, move v; a point x of part two moves by v + ω × x) the free motions between two groups of parts are the null
  space of their rows: nothing left → one rigid group; one turn → a rotate joint with its exact axis (point + direction
  from the geometry, no picking); one move → a slide; turn + move on one axis → a cylinder pair. This works for any mix
  of Mate / Flush / Insert / Angle / joints, also when the owner over- or under-constrains a pair, and needs no list of
  "patterns". (Rows per type: `prototype/motion_plan.py`, `constraint_rows`.)
- The hidden `RigidBodyAnalysis` (used by the Synthesis robot exporter) would hand over rigid groups and joints
  directly, but it is undocumented and unsupported: kept as a fallback only.

**2. What each pattern becomes** (all in the prototype, all checked in Blender except where marked):

| Inventor | App |
| --- | --- |
| Insert (pin in a hole) | rotate joint on the hole's axis; with "Lock rotation": rigid |
| Mate axis–axis + Mate/Flush face (a hinge) | rotate joint |
| Two Mate/Flush plane pairs (a slide) | slide joint along the line both planes allow |
| Mate / Flush **with limits** ("Use limits") on the third pair | the slide's limits: Inventor's offset → joint mm (0 = CAD pose) |
| Angle **with limits** | the turn's limits (deg). The value is measured from the file's geometry while the joint moves a little, so Inventor's sign conventions cannot turn a limit round; if the measured value differs from Inventor's, the limits are left off with a note |
| Angle / Mate offset **without** limits | holds the part (a fixed angle is design, not motion) – **owner question 3** |
| Mate axis–axis alone (2 free: turn + slide) | barrel/rod pair: see cylinder; alone: a slide (the spin of a round part is not shown) |
| Barrel + rod (axis–axis) whose eyes each turn on another group | the app's **cylinder** (barrel pin, rod pin, carriers) – the loop closes through the cylinder's drive; barrel = the name with barrel/cylinder/huis/Zylinder…, else the first |
| Round part that only spins (pin, bolt, washer, roller on a frame) | no joint: rides with the part it sits in (round from the mesh, `core/paths.is_round`); a gear or a part with limits keeps its joint – **owner question 1** |
| Rotate–Rotate / Rotate–Translate motion constraint | a coupling (`set_follows`, ratio; reverse = −) |
| Rigid subassembly | one part at its parent's level; its own constraints give joints *inside* it that ride on whatever moves it (stacked joints) – **owner question 2** |
| Flexible subassembly | opened up: its parts and constraints join the parent's level |
| Fully constrained part | merged into the group it is fixed to (no joint) |
| No constraints at all | stays put (rides with its CAD parent) – common for fasteners, and right |
| Constraint to the assembly's own origin planes | counts as "held still" (grounded) |
| Inventor assembly joints (Rotational, Slide; Cylindrical, Planar, Ball) | rows of the same kind; their limits and position directly |
| Tangent, Transitional (cams), Symmetry, Translate–Translate, pin-slot | left out, listed ("a cam contact – not a joint") |
| Any other closed loop (four-bar) | listed as a mechanism (made by hand in 4 Motion > Mechanisms; a later task could make it) |
| Suppressed constraint / occurrence, unhealthy constraint | left out, listed |

**3. Matching the file to the import: by occurrence names, as the model update already does.**
- Three real Inventor STEP files (AP214; Inventor 2013 and 2023, found on GitHub) carry the **occurrence name** in the
  `NEXT_ASSEMBLY_USAGE_OCCURRENCE` ("MagToolChanger_Motor:1") and the **Part Number** iProperty as the product name. The
  importer already keeps the occurrence name (`fr_instance`) per object, the model update matches by the chain of these
  names, then by the name path and nearest place (`reimport.match`). The prototype reuses `reimport.match` unchanged
  with records made from the file: **16 of 16** occurrences found by name, and **16 of 16 again with all names
  removed** (by part number path + place – two identical bolts told apart by place).
- Fusion writes "Section 1 v8:1" both as the occurrence name and into the STEP (seen in `tests/data/test_waycover_a.step`,
  from Autodesk's translator), so the "v8" needs no special care when the file and the STEP are written together; an
  older STEP is matched by the name path without the version (`reimport._norm`) and the place.
- Patterns: their elements are ordinary occurrences (`IsPatternElement`), names "Bolt:5"; mirrored parts are their own
  part files. Suppressed occurrences are written with `suppressed: true` and left out (they are not in the STEP).
  Not seen in a real file yet: pattern and mirror names in STEP (unconfirmed).
- **The rule also saves the STEP** (optional, default Yes), so file and STEP always match. A stale file is caught by
  the checks below (constraints that no longer hold, places that differ).

**4. Units and frames.** Inventor's API: cm and radians; a subassembly's constraints and their geometry are in that
subassembly's own coordinates. The rule converts to mm / degrees and to the top assembly's coordinates (= the STEP's)
by multiplying the occurrence matrices down the path itself. Numbers are written with a decimal point whatever the
Windows language (a Dutch Windows writes commas otherwise). The app then places the axes with the model root's matrix
(as the demo's joint sheet does).

**5. Two checks catch a wrong reading** (both in the prototype, both tried):
- *every constraint must hold in the file's geometry* (axes on axes, planes at their offset, the angle): a subassembly
  matrix left out shows as "Mate:5 … the axes are 699.21 mm apart – read wrongly?"; a direction from the wrong frame
  as "the two directions are not parallel". No false alarm on the clean file.
- *Inventor's DOF count* per part against the count from the file.

**6. Speed** (this 4-core web machine, one core): the plan for 3,001 parts (1,500 rigidly fixed plates + 1,500
inserted bolts) takes 4.9 s, 400 parts 0.2 s. (A first version that re-collected all pairs after every merge took 2 s
for 400 parts and grew with the square; merging all rigid pairs of a pass at once is exact, since a pair held fully
stays held when more is added.)

### Design (for the app task)

**Side file** `<STEP name>.fresing.json` next to the STEP (the example: `tools/inventor/prototype/example.fresing.json`):

```
format "fresing-cad-motion", version 1, written_by {app, app_version, script, time}, document {name, step_file},
units {length "mm", angle "deg"}, frame "top assembly (= the STEP file's coordinates)",
occurrences: [{path ["Arm assembly:1","Arm:1"], kind part|assembly, file, part_number, grounded, suppressed,
               visible, excluded, flexible, pattern, adaptive, matrix [16, row-major, mm],
               dof {translations [[x,y,z]…], rotations […], centre}}],
constraints: [{name, type mate|flush|angle|insert|tangent|transitional|symmetry|rotate_rotate|rotate_translate,
               assembly [path of the assembly that holds it; [] = top], suppressed, healthy,
               one/two {occurrence [path of the part whose face/edge it is; [] = the assembly's own planes],
                        geometry {type plane|cylinder|cone|circle|line|point|sphere|torus|other, point, direction,
                                  radius}, inferred line|point|plane},
               value (mm or deg), limits {min, max} | null (either end may be null), solution, reference_geometry,
               opposed, lock_rotation, ratio, forward, distance}],
joints: [{name, type rotational|slide|cylindrical|planar|ball|rigid|pin_slot, assembly, suppressed, locked,
          one/two {occurrence, origin {point, z, x}}, angle, linear, angle_limits, linear_limits}],
problems: ["what the rule could not read"]
```

The rule writes **raw facts only, no decisions**: all logic is in the app, in Python, where it is tested; a
non-programmer never has to change the rule, and a new rule version only adds fields (the app ignores unknown ones).

**The plan** (`motion_plan.py` → `core/cad_motion.py`): output in the demo joint sheet's form (task 0077:
name, type, parts, axis point/direction in mm, limits, rides_on, drive.follows/ratio) plus cylinders, couplings, notes
and a "left out" list – so `demo.make_joints`' loop (`joints.create` in a `joints._batch`, limits, `set_follows`) is the
app side almost as it is, plus `cylinders.create` for the cylinders. Base of a top joint = a part of the group it hangs
on (not the root), so a model moved by its root keeps its joints.

**Model update.** The importer looks for the file next to the new STEP; each made joint, cylinder and coupling gets a key
(the occurrence paths of its moving group and of the group it hangs on) and the values it was made with. At an update
the existing model update keeps every joint as now (by part matching); then a "refresh from the CAD file" step compares
the new plan by key: axis or limits changed in Inventor and not touched in the app → updated; touched in the app → kept,
noted (**owner question 5**); new → added; gone → listed, not deleted silently.

### Prototype (what ran here)

- `tools/inventor/prototype/make_example.py` – the invented assembly "FR motion test" (frame, door + hinge pin, carriage
  + lid on an Inventor joint, a rigid arm subassembly with a sliding gripper, a flexible cylinder subassembly, two
  gears with a motion constraint, two bolts, a type plate, a cam contact, a suppressed constraint and occurrence) as
  STEP + its side file, from the same numbers.
- `motion_plan.py` – the plan, pure NumPy. On the example: Door turn 0…100°, Carriage slide −20…320 mm (Mate offset 20,
  limits 0…340), Lid turn −90…0° riding on the carriage, Arm assembly turn −5…60°, Gripper slide −140…120 mm riding on
  the arm, both wheels with the big one following ×−0.5, Barrel + Rod as one cylinder; the hinge pin and the bolts
  ride along, the cam contact is listed.
- `try_in_blender.py` – Blender 5.2.3 as a module: imports the STEP with the app's importer, matches (16/16, also
  without names), plans (round parts from the meshes), makes everything with `joints.create` / `set_follows` /
  `cylinders.create`, then moves it: door at 90° (far edge where it should be, pin turning in place), carriage at the
  end of its travel, lid opening on the moved carriage, arm up 30° (rod eye stays on the arm's pin, barrel eye on the
  frame's, cylinder 128 → 231.5 mm), gripper sliding along the lifted arm, big wheel −45° for +90°, no joints on bolts
  and the plate. **23 of 23 checks pass** (run: `~/venv/bin/python tools/inventor/prototype/try_in_blender.py`, ~1 min).

### Sources and what is unconfirmed

Autodesk's help, forum and blog sites did not open from this machine (DNS refused); facts come from: the InventorBridge
type-library dump of Inventor 2024+ (github.com/gustacassel/InventorBridge, docs/reference: AssemblyConstraint,
MateConstraint, AngleConstraint, InsertConstraint, ConstraintLimits, AssemblyJointDefinition, ComponentOccurrence…),
the ObjectTypeEnum list of InventorCode/iLogicRules, Autodesk's official Fusion C++ API headers
(github.com/AutodeskFusion360/FusionAPIReference: Joint, AsBuiltJoint, JointGeometry, JointLimits, the joint motions,
Occurrence), public exporters (fusion2urdf, Petasos_URDF_Exporter, HiceS/InventorRobotExporter = Synthesis,
zerodamage/URDF-converter), three Inventor STEP files on GitHub, and search summaries of the Autodesk pages.

**Unconfirmed, to be settled by the owner's first run** (the rule writes what it reads, and the checks show a wrong
reading): (a) that `GeometryOne/Two` of a constraint in a subassembly document are in that subassembly's coordinates
and `OccurrencePath` relative to it; (b) the sign conventions of Inventor's Mate/Flush offset and directed Angle (the
app measures from geometry, so only the note "Inventor says …" would show a difference); (c) the Rotate–Rotate ratio's
direction (turns of the second per turn of the first, assumed) and "forward"; (d) the STEP translator's id
`{90AF7F40-…}` and that it keeps the last-used options; (e) the menu names for adding an external rule in 2027;
(f) Fusion's joint origin of the second side (sometimes local, per fusion2urdf: the script writes side one's).

### Independent review of the scripts

(see below – filled in after the review)

### Proposed tasks and questions for the owner

**Order:** owner tries the draft rule (no chat) → a short worker fix of the rule from his file → the app task.

1. **Owner, on his PC (15–30 min):** build the generic test assembly of `tools/inventor/README.md` (or any of his own
   cleared parts – never a client's model or the Fresing 400), run the rule (steps in the README), send the
   `.fresing.json` and any error. Then the same with the door at 30°.
2. **Proposed task A – Inventor rule fixes from the owner's file** – worker, **Sonnet · Medium**, Claude Code on the web: read his
   file, run `motion_plan.py` on it (the checks name a misread constraint), fix the rule, ask for one more run. Only if
   his run shows problems; Windows-only, so an independent read of the change before it goes back to him.
3. **Proposed task B – Joints from the Inventor file** – worker, **Opus · High**, Motion lane (+ the importer's panel, additive
   `reimport.py`), runs alone in its lane. `core/cad_motion.py` from the prototype with its own tests (the example,
   one test per row of the table above, a big file for speed, the checks); `tools/make_test_cad_motion.py` +
   `tests/data/test_cad_motion.step/.fresing.json`; at import, when the file is next to the STEP: a tick "Make joints
   from the Inventor file" (default on) and a result list (joints, cylinders, couplings, left out, checks) in
   4 Motion; the update step of "Model update" above; the rule shipped with the app (Help > "Inventor motion export
   rule…" opens its folder) and a guide chapter with the README's steps; PC-check line and tour stop (the test model).
   Risks: Inventor conventions that differ from the assumptions (mitigated by measuring from geometry and the two
   checks); large assemblies with thousands of constraints (measured 4.9 s for 3,000 parts here); owner-edited joints
   at an update (question 5).
4. **Later, if wanted:** closed loops → the app's mechanisms (four-bar, scissor); symmetry → couplings; Inventor
   "Drive constraint" settings → an animation step (**question 6**); Fusion via the same file (the script is here).

**Questions for the owner** (suggested answer first):

1. **Round parts that only spin** (pins, bolts, rollers on a frame): *no joint, they ride along* – a tick "Turn round
   parts too" for conveyors? Rollers turned by a cable already get theirs from the cable function.
2. **Motion inside a rigid subassembly** (e.g. a cylinder subassembly you left rigid): *make it anyway* (the app does not
   know "rigid" vs "flexible" as a choice for showing motion), or only in flexible ones?
3. **Angle / Mate offset without limits:** *a fixed setting (no joint)*; only "Use limits" means "this moves". Or would
   you rather mark moving constraints by name (for example "M: …")?
4. **One click for both files:** *the rule saves the STEP too* (Yes by default). OK?
5. **Model update:** a joint the file made and you changed in the app (limits, axis): *keep your change* and note it,
   or take Inventor's?
6. Do you use Inventor's **Drive** (start/end of a constraint) or Studio animations you would like to come over as
   animation steps? *Not now.*
7. **Model states / positional representations:** *the rule reads the active one* – the same one the STEP is saved from.

**Subagents:** two ran. A research agent (web search; read type-library dumps, Fusion headers, exporters and Inventor
STEP files on GitHub) gave the API facts above. An independent reviewer read both scripts against those facts and the
planner (results above). The prototype itself was written and run in this session. GitHub runs: see below.
