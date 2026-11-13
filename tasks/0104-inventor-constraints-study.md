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

**Chat / date:**

**Findings:**

**Proposed tasks and questions for the owner:**
