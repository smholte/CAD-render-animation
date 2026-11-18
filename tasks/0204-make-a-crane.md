# 0204 – Lifting L4c: "Make a crane…" – a parametric crane made in the app from the built-in makers, straight into the library

**Who:** worker · **Status:** open – **after 0201** (uses its Lifting plan section and Place) ·
**Branch:** `task/0204-make-a-crane`
**Started by:** lead chat, 18 Nov 2026 (owner: "pre-rigged models that are parametric", in the app, offline; owner's
order 18 Nov: straight after L4) · **Lane:** Lifting
**Area:** new `blender/ops_lifting_make.py` + `blender/ui_lifting_make.py` (the dialog and the background job),
`fresing_render/lifting_model/` (additive: `params.py` – each class's numbers with their limits, labels and units; a
`validate(params)` that names what does not fit; `make.py` takes a parameter file), their tests; additive:
`blender/ui_lifting.py` (one button "Make a crane…"), `props.py`, `core/functions.py`, the tour, the PC check, the guide.
Beside 0203 (Set up a crane): own files; `ui_lifting.py` gets one additive line from each; the second to merge updates
to `main`.
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

In 8 Lifting plan > Equipment the owner clicks **Make a crane…**, picks a type (mobile telescopic, crawler,
knuckle-boom), starts from the nearest built-in class, changes the numbers he cares about (boom sections and lengths,
outrigger spreads, counterweights, axles, track gauge, masses …), presses **Make**, and seconds later a fully rigged crane
with a SAMPLE chart is in his library and can be placed – offline, nothing to install.

## Background

- L3 (0191): `fresing_render/lifting_model/` – `classes.py` (dataclasses `Mobile`, `Crawler`, `Knuckle` with ~20–30
  numbers each, the 12 class parameter sets, `layout`, the hook's kinematics), `mobile.py` / `crawler.py` /
  `knuckle.py` (OpenCascade: the STEP, one solid per part), `charts.py` (SAMPLE charts from the invented rule: min(rated
  top, boom strength / radius, 75 % tipping over the outrigger / track edge)), `equipment.py` (the equipment JSON),
  `make.py` (command line; pictures separately by `tools/make_lifting_cranes.py --pictures`). Its tests check every joint
  against the maker's kinematics (`tests/lifting_rig.py`). Import of a made crane: 0.9–3 s (web machine).
- The demo's maker already runs as its own program with Blender's Python from the app (Help > Make demo project:
  progress, Cancel) – the same way here.
- L2's library: `write_item` (atomic, never into the built-ins), the SAMPLE mark and chart hash.

## What to build

1. **Parameters with limits** (`lifting_model/params.py`): for each type the numbers a user may change, each with label,
   unit (t, m, mm shown as m where natural), min / max, and the rules between them (sections fit inside each other,
   retracted < extended length, boom fits the carrier, counterweight steps rising, outrigger spreads full > middle >
   narrow, tracks long enough for the upper's tail …). `validate` names every rule that fails in plain words. Derived
   numbers (masses, CoG) offered from the class rule, changeable.
2. **The dialog** (popup or the Set-up window – the worker picks and says why): type, **Start from** (a built-in
   class), the numbers in folds (Boom, Carrier / Tracks / Truck, Outriggers / Stabilisers, Counterweight, Hoist & hook,
   Masses), a live line "fits" / what does not, the name (refuses a name already in the library unless "Replace"),
   **Make**.
3. **Make** runs the maker as a background program (progress, Cancel; never blocks the app): STEP + equipment JSON
   (rig, masses, CoG, the SAMPLE chart from `charts.py`'s rule for these numbers, `derived_from` the class) + a small
   picture, written into the user's library folder "Lifting equipment" through L2. Then **Place now?** (0201's Place).
4. **Charts:** always SAMPLE ("SAMPLE – not for real lifts …", study section 8), with the line "Enter the chart of your
   real crane" and a button to the chart entry (L2) – entering a real chart clears the mark by L2's rule.
5. **The usual parts:** tooltips; guide section "Make a crane from numbers" (types, limits, SAMPLE chart, the library);
   function entry (`since=`, `workspaces=("lifting", …)`); tour stop (an AT made with 5 sections instead of the class's
   6 – placed, Hook to here); PC-check line `lifting.make` (makes a small crane, times it); real-app test.

## Done when

- [ ] For each of the 12 classes: the class's own numbers through `params` + `make` give the same joints, poses, hook
      point, masses and charts as the shipped file (the STEP by counts and positions – the writer is not byte-stable).
- [ ] ≥ 20 random valid parameter sets per type: made, imported, rigged, every joint min → max checked against the
      maker's kinematics (0191's checks), clash check of the crane's own motion clean.
- [ ] Invalid numbers refused with the rule named (one test per rule); Cancel leaves nothing behind.
- [ ] Time to make one crane per type measured on the web machine (report); the app keeps redrawing while it runs.
- [ ] Real-app test: the dialog, Make, the item in the library, Place now; tooltips, guide section + picture, function
      entry, tour stop, PC-check line.
- [ ] GitHub green incl. Windows; merged, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Real (maker) charts – never generated, only entered by the user; your own STEP crane (0203); tower, gantry, forklift
makers (L8); offshore cranes (L9); the rope with several falls (L5).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
