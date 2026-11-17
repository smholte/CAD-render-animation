# 0191 – Lifting L3: ready-rigged generic cranes (mobile telescopic, crawler, knuckle-boom) with sample charts

**Who:** worker · **Status:** open – can start · **Branch:** `task/0191-lifting-cranes`
**Started by:** lead chat, 17 Nov 2026 (study 0180, task split L3) · **Model:** Opus · effort High · **Place:** Claude Code on
the web, environment "CAD-render-animation"
**Area:** Lifting lane – new package `fresing_render/lifting_model/`, new `tools/make_lifting_cranes.py`, the built-in
files in `fresing_render/data/lifting/`, their tests. Runs beside 0190 (L2 library, `core/lifting_library.py`) – do not
edit that file.

## Goal

The app ships ready-rigged, invented cranes in size classes – the parts, the joints (slew, luff, telescope, hoist,
outriggers, tracks), their masses and centres of gravity, and a plausible **sample** load chart per configuration – so a
later task (L4) can drop one into a project and plan a lift with it.

## Background

- Study 0180's report: **section 2 "Equipment catalogue"** (the kinds, size classes, joints and data per item) and
  **"How the app makes them"** (one parametric maker per kind in `lifting_model/`, the pattern of
  `fresing_render/demo_model/`: params → shapes → STEP with one solid per part → a JSON sheet with joints, cylinders,
  poses in the sheet format `site/render_kit/projects.py` already applies). Section 4 is the equipment file format that
  0190 builds the reader for – write the built-ins in that format.
- **Kinds in this task (owner 17 Nov: onshore first):** mobile telescopic AT-40 / AT-100 / AT-250 / AT-500, crawler
  lattice CC-100 / CC-300 / CC-750 / CC-1600, knuckle-boom KB-20 / KB-50 / KB-100 / KB-200. **Not here:** offshore
  pedestal and heavy vessel cranes (with their Hs charts → L9), tower crane (later), workshop gear and rigging (L8).
- Charts: use `core/lifting.py` (0182) – `Chart`, `chart_to_dict`, `validate_charts`, `pick_chart`, `crane_use`. Every
  built-in chart must pass `validate_charts` with no refusals.
- What the app can already rig: joints / couplings (0011–0014), cylinders (0013), coupled slides (way-cover style k/N,
  0035) for telescope sections, cables and drums (0078 / 0080 / 0174) for the hoist, tracks (0079) for crawlers, the
  render-kit sheet reader (0112). The crane test model `tools/make_test_crane.py` (0122) is a small example.
- The one-solid-per-part rule and joint naming of the demo maker (0076) apply.

## What to build

1. One maker per kind (`lifting_model/mobile.py`, `crawler.py`, `knuckle.py` + shared `common.py`); a class is a
   parameter set. Detail in the style of the demo vessel (recognisable carrier, cab, boom sections, hook block, mats /
   pads), not more triangles than needed (report the counts; aim ≤ ~150 k triangles per crane at Normal).
2. Per class: the STEP, the equipment JSON (format of study section 4 / 0190: `kind`, `class`, `name`, `units`, masses
   + CoG per moving group, `rig`, `charts`, `hook_blocks`, `outriggers` / `tracks` / `axles`, `limits`,
   `"sample": true`, `source`: "invented sample – Fresing Render") and a small picture.
3. **Sample charts:** invented, plausible shape (capacity falling with radius, tip-load end, per boom length ×
   counterweight × outrigger spread; crawler per boom × jib × counterweight; knuckle by outreach). You may *read* 2–3
   public brochures per class to keep the magnitudes realistic – **never copy a maker's table, name, logo or model**,
   and do not put brochure files or their numbers in the repository (public repo, CLAUDE.md section 6: "no maker's load
   chart in the repository"). Say in the report which public pages you looked at.
4. Where the files live: built-ins under `fresing_render/data/lifting/<class>/` if all classes together stay ≤ ~10 MB;
   otherwise ship the maker and make each class on first use into the user's cache (report the sizes and the choice).
5. A tool `tools/make_lifting_cranes.py` that rebuilds every class (like `make_test_*.py`).

## Rules for this task

- Tests (Blender as a module): each class imports with the app's importer + sheet reader; every joint moves through its
  range without parts flying apart (slew 360°, luff min → max, telescope in → out with the sections coupled, outriggers
  in → out, hoist up/down, tracks run); the hook height and radius at two poses match the maker's own numbers within
  10 mm; every chart passes `validate_charts`; `crane_use` runs on each class at three radii. Keep the new tests inside
  the time rules of CLAUDE.md section 5 (one file ≤ ~10 min on GitHub; split if needed).
- A short independent review of the charts by a subagent (shape rules, units, the sample flag), not of the geometry.
- If 0190 is already on `main` when you merge: add a test that every built-in reads with `lifting_library` with no
  problems. If not, 0190 adds it.
- Nothing visible in the app yet (L4 puts the Lifting panel up): no tour stop, PC-check line or guide pictures in this
  task; one guide paragraph naming the built-in classes is enough.
- Normal finish (CLAUDE.md sections 2 and 7).

## Done when

- [ ] 12 classes (AT ×4, CC ×4, KB ×4) made by `lifting_model/`, each with STEP + JSON + picture, rigged and charted.
- [ ] The tests above pass locally and on GitHub; sizes and triangle counts in the report.
- [ ] No maker's data or name in the repository (say so in the report).
- [ ] Report below filled in; TASKS.md row moved to Done.

## Not in this task

The library reader (0190), the Lifting panel and placing a crane in a project (L4), rigging and the hang solver (L5),
offshore / vessel cranes (L9), forklifts, hoists, slings and spreaders (L8).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
