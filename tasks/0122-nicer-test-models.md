# 0122 – Nicer test models: better looking, more detail, more functions per model

**Who:** worker · **Status:** waiting – starts when 0119, 0120 and 0121 are done (they change tests that read
`test_spool`, `test_tracks`, `test_flex_*`, `test_sequence`); not at the same time as 0062 · **Branch:**
`task/0122-nicer-test-models`
**Started by:** lead chat, 14 Nov 2026 (owner's wish) · **Lane:** Test models (new): `tools/make_test_*.py`,
`tests/data/*.step` + their copies in `fresing_render/data/`, the set builds in `blender/tour.py` (only the sets of the
models it changes), the expected numbers in the tests that read those models, guide pictures that show a changed model
**Model:** Opus · effort High (subagents, see CLAUDE.md section 2) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

## Goal

The test models are what people see first: in the test tour, in the PC check report, in guide pictures, and soon in
the interactive learning modes (study 0123) and on the website. Today they are plain blocks and tubes. The owner wants
them **visually nicer, with more detail, and each showing more of the app's functions**, while every automatic test
keeps working.

## Background

- 23 makers in `tools/make_test_*.py` write 27 models (`fresing_render/data/`, copies checked by a test). The test tour
  (`blender/tour.py`, 37 sets, 61 stops) builds one small project per model; the PC check and many pytest and real-app
  tests read them; guide pictures use the test crane.
- They are invented models: free to change, free to show anywhere (GPL repository). **Never** anything of the owner's
  employer, its clients, or the Fresing 400 (CLAUDE.md section 6).
- Rules that bind every test model: each part one solid (`fuse`; several solids lose their colour – section 8),
  AP214/AP242 with colours, names the part-type library sorts the intended way, every tour animation gives 0 clashes
  (`test_every_tour_animation_has_no_clash`), the whole tour builds in about 2 minutes, GitHub's full run stays about
  12 minutes.
- Study 0123 (interactive learning) runs before or beside this task. If its report is on `main` when this task starts,
  read its "lesson per test model" section: it may ask for parts or names the lessons need.

## What to do

1. **Look first, one stop for the owner.** Make an inventory: per model what it shows, which tests read it and what
   they assume (part names, counts, places, joint axes, numbers in checks). Then upgrade **one** model (the test crane
   is the obvious one) and render before/after stills (Cycles, the tour's own shot, small). Propose per model: what
   gets added (real-looking shapes: fillets/chamfers, bolts and nuts at joints, hydraulic hoses, plates with holes,
   ribs, handrails, decals, a name plate, paint schemes; machine-like proportions), and which **extra functions** it
   could show (e.g. the crane with labels, a decal and a hose; the mill with a way cover and coolant). Show the owner
   the stills and the list in one message and **wait for his pick** (the one stop in this task).
2. **Build in batches** after his pick. Keep the geometry the tests rely on (joint pivots, travel, pocket places, the
   faces the pickers find) or change the expected numbers on purpose and say so in the report – never loosen a check
   to make it pass. Details are real parts with sensible names (they must sort right in the part-type library and not
   create clashes).
3. **Budget:** at most ~2 × the triangles of each model at Normal, the tour build ≤ ~2.5 min, no GitHub job longer than
   before by more than ~10 %. Measure before/after (import time, tour build, the jobs' times) and put them in the
   report.
4. Tour stops: update the "what you should see" texts and checks of changed sets; a model that now shows an extra
   function gets that function's stop in its set (or the stop moves to it) – keep `MIN_LINES_TOUR` / `MIN_CHECKS` right.
5. Guide pictures that show a changed model: re-make them (`tools/guide_screens.py`).

Subagents (section 2): one per batch of makers + an independent tester who runs the tour, the clash test and the
model-reading tests against the new models. Shared files (`tour.py`, version files, CHANGELOG, `TASKS.md`) stay with
the worker.

## Done when

- [ ] Owner's pick from step 1 in the report.
- [ ] The picked models upgraded; each still one solid per part, colours kept, sorted as intended, 0 clash rows on
      every tour animation.
- [ ] Every test passes without loosening; changed expected numbers listed in the report with the reason.
- [ ] Before/after numbers: triangles, import time, tour build time, GitHub run time.
- [ ] Tour texts and checks current; guide pictures of changed models re-made; PC check still all OK.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

New app functions. The learning modes themselves (0123 and after). The site's own models (Thor, CEB press, turbine,
the demo vessel). Old test models that only exist for an old-project test (`old_app_template`, `test_crane_inv_*`):
leave them.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
