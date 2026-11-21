# 0258 – Study (findings only): is every test model, prop and person real size? A measured table, a proposed real size per model, and the model categories for the redo

**Who:** worker · **Status:** running · **Branch:** `task/0258-study-real-sizes`
**Started by:** lead, 21 Nov 2026 (owner 14:13, two screenshots of the test crane beside a person and an IBC on the
quay: "the demo crane used a lot of places should not be this small compared to other models. make sure that the scale
is realistic. and check the size of other objects as well." His pick 14:20: **study first, then one fix task per model
type**) · **Model:** Opus · effort Medium
**Area:** findings only – a report, a table and a few pictures in `tasks/0258-study-real-sizes.md` + `tasks/img/0258/`;
throw-away scripts stay on the branch. **No change to app code, test models, tests or the tour.** Commits `[skip ci]`;
at the end the `tasks/` files go to `main` (a tasks-only push starts no run).

## Why

The test models were made small to keep the tests fast (task 0011 on: the test crane's boom is 1.5 m, its boom pin
0.4 m high). Since 0155 the tour has life-size people (1.65 / 1.75 / 1.85 m) and real-size props (container, pallet,
IBC, gas rack, barrier, tool trolley), and since 0230–0235 the tour is the **users' learning environment** with real
surroundings (quay, deck, halls, sea). Next to those, a small model reads as a toy. The owner wants every model at a
realistic scale. The test crane is fixed at once in **0259** (owner's pick: ×5); this study measures everything else
and says what to fix.

## What to do

1. **List everything with a size** that a user sees in the tour, the lessons, the PC check pictures, the guide pictures
   and the public demo: every `tests/data/*.step` / `fresing_render/data/*` model a `@tour_set` or lesson uses, the
   mesh models (`make_test_mesh`), the Lifting cranes and loads, the props and people (`core/props_detail.py`,
   `core/surroundings.py`), the surroundings themselves (quay, deck, halls: door and ceiling heights, railings,
   bollards, workbench / stand props), the public demo's ship with its deck crane and the wind park.
2. **Measure** each: overall size (bounding box from the STEP with OCP – no Blender needed) and the 2–3 sizes that
   decide how big it reads (boom length and pin height, table / bed, arm length, drum Ø, door height …), and where it
   stands in its set (floor, deck, workbench).
3. **Say what it represents and its real size**: the kind of real machine or thing, and a typical real size range from
   public sources (standards, general handbooks, catalogue ranges – **no maker or model names in the report**). Note the
   source in one line per row.
4. **Verdict per row:** ok · too small · too big · "a desk-size test model on purpose" (only where the real thing is that
   small). Proposed real size (or factor) with one line why. Where a uniform factor would give silly parts (bolts,
   plate thickness, pins), say which parts should get real sizes instead.
5. **Cost of each fix:** how many test files, tour sets, PC-check lines, guide pictures and lessons read the model
   (grep, a count per model), and whether a bigger model changes the import's triangle count (the importer caps the
   facet gap in mm on big parts – `importer/step_reader.py` `FACETS`): measure one import at Normal before / after a
   plain ×k scale for the two biggest candidates (throw-away STEP files on the branch, not in `tests/data/`).
6. **Sort into categories for the redo** (the lead's to-do from the owner's 20 Nov 22:19 "redo all test-tour models,
   one task per model type"): e.g. cranes and lifting, hydraulics and mechanisms, winches / spools / sheaves, tracks,
   hoses and chains, vessels and sea, workshop machines (mills are already 0249 / 0250), studio objects (faces, decals),
   props and surroundings. Per category: which models, the proposed sizes, which tour sets it touches, a suggested order
   (most visible first), model · effort, and what must wait for what (0233–0235 own sets in `tour.py`; 0249 / 0250 the
   mills; 0259 the test crane).
7. **One line-up picture per category** (400–800 px, small Cycles or EEVEE render with Blender as a module): today's
   models standing beside a 1.75 m person and one real-size prop – test models only – plus the same line-up with the
   proposed sizes (a plain scale is fine for the picture). The owner judges by these.

## Done when

- [ ] Table: model / prop → represents → today's key sizes → real size (source) → verdict → proposed size → cost
      (tests, sets, lines, pictures) → category
- [ ] The two import measurements (triangles, time at Normal, web machine) before / after scaling
- [ ] Categories with order, waits, model · effort – ready for the lead to brief
- [ ] Line-up pictures in `tasks/img/0258/` (test models only)
- [ ] `tasks/` files on `main`; branch named in the report

## Not in this task

Any change to models, tests, the tour or the app. The test crane (0259 fixes it now). The mills (0249 / 0250). **Never
the cable-lay vessel's equipment** (private, CLAUDE.md section 6) and **never the Fresing 400** – no test model of its
size class either. The full demo (private).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
