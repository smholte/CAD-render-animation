# 0235 – Learning sets "Painted faces" and "Logos and stickers": real-looking test models

**Who:** worker · **Status:** open · **Branch:** `task/0235-learning-sets-faces-decals`
**Started by:** lead, 20 Nov 2026 (study 0224 package C; owner's answers 20 Nov: the tour is the learning environment,
each set its own fitting environment) · **Model:** Sonnet · effort Medium
**Area:** `tools/make_test_faces.py`, `tools/make_test_decals.py` (+ `tests/data/test_faces_a.step`,
`test_decals_a.step`, their `fresing_render/data/` copies, their maker tests), `blender/tour.py` – **only** the sets
`faces` and `decals` and their checks. No app code.

## Goal

The two sets 0122 did not reach get models that look like real machine parts – a housing with a painted face for
**Painted faces**, a panel / hydraulic tank with places for a logo and a warning sticker for **Logos and stickers** – in
a fitting environment (studio or a workshop hall), so they can be shown as they are.

## Background

- Study 0224: `faces` = coloured boxes, `decals` = a plate and two grey cylinders, both unchanged since 0.2.47. 0122
  (`tasks/0122-*`) made the other test models nicer – follow its style (invented, named parts, real proportions).
- **Keep the part names (and faces) the stops and tests read** so the checks stay; if a check must change, change it in
  the same commit and say why. Invented shapes only, no real makes or logos (the decal picture is the app's own test
  picture).
- Others in `tour.py` at the same time own their own sets (0230, 0231, 0233, 0234, 0229); the record file of
  `tools/tour_versions.py` is shared – merge `main` once at the end and re-run `--record`.

## Real size (added by the lead 21 Nov, study 0258 category G)

The decal model must be real size: its "barrels" (Ø0.12 × 0.30) read as drums, so make them real drums (200 l: Ø0.585 ×
0.88, ISO 15750-3, or 60 l: Ø0.40 × 0.60), the panel a machine door panel ~1.2 × 0.8, the box a real small part.
The painted-faces housing is small on purpose and right (0258). Line-up beside a 1.75 m person in `tasks/img/0235/`.

## What to do

1. New shapes in the two makers (both `.step` copies), maker tests.
2. The two sets: surroundings + camera that show the painted face and the decals clearly; stop texts if the picture
   changed; `changed=`, re-record; Go + checks pass; 0 clashes.
3. Before / after 400 px pictures in `tasks/img/0235/`.

## Done when

- [ ] Both models real-looking, names kept, maker tests green; both sets' checks pass; precheck green
- [ ] Full suite green; report filled in, merged, released

## Not in this task

Other sets and models; app code.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
