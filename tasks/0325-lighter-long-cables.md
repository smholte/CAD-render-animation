# 0325 – Lighter long cables (+ 0328 row 23, two small notes)

**Who:** worker · **Status:** running · **Branch:** `task/0325-lighter-long-cables`
**Started by:** lead, 25 Nov 2026 (from 0315's slow place 2 and the owner's Stress run on his PC) · **Model:** Opus · effort High
**Area:** Import lane – `importer/step_reader.py` (meshing of long thin faces), `importer/runner.py` (the prune note only),
`blender/reimport.py` (row 23 only), `tools/make_test_stress.py` (README words), `pccheck/stress.py` (limits only), their
tests, guide, CHANGELOG.
**Not:** `pccheck/checks.py` (0332 and 0333 change it), `blender/build.py` and the face colours (0340, after you), the
importer popup (0340 / 0342), study 0301's Blender build speed-ups (own task later).
**Must be merged before 0340 starts (Monday 30 Nov)** – 0340 changes the same reader. If you cannot finish by then, say so
in a "WAITING FOR YOU:" line early.

## Goal

A long cable or hose from CAD comes in light: about a tenth of today's triangles, and it looks the same at any distance a
user renders it. Big models import, turn in the view, render and export faster because of that.

## Background

- 0315 (`tasks/0315-stress-model-10k-parts.md`, "Ranked for the lead", item 2): a 30 m B-spline cable meshes to
  ~127,000 triangles at Normal (0.5 mm cap); the Stress model's 48 cables are ~8 of its 13.9 M triangles and most of the
  meshing time. A real Inventor cable harness will do the same.
- **The owner's Stress run, 25 Nov 21:06, 0.2.257** (Ryzen 9 9900X, 24 cores, 47 GB, RTX 3090):
  import Draft 48.8 s (4.13 M triangles), import Normal 55.3 s (13.9 M, from cache 16.3 s), **Solid view turning 1.13
  pictures/s**, Live first picture 4.90 s, render 17.6 s, web 3D export 46.8 s / 28.7 MB, model update 70.2 s.
  Draft is almost as slow as Normal, so most import time is the one-core read, not the meshing; the cables still cost
  most of the triangles, and with them the view, render and export.
- The faces are swept circles along long B-splines: the 0.5 mm chord cap makes many rings along the length and many
  segments round a small diameter. A cable needs few segments round (by its diameter) and rings only where it bends.

## What to do

1. **Measure first** on `tools/make_test_stress.py`'s cables: triangles per cable, rings along, segments round, meshing
   seconds. Find how the reader can tell a long thin swept face (or part) from an ordinary one – shape, not names.
2. **Mesh them by their own rule:** segments round from the diameter (a Ø20 mm cable needs about 12–16, not 60+),
   rings along from the bend (straight runs: few). Proposal welcome; say in the report what you chose and why. Draft /
   Normal / Fine keep their order. Other parts mesh exactly as before (same triangle counts in the existing tests).
3. **Pictures** to prove the look: one cable close up (about 0.5 m away, 4K still) and the cable tray at a normal distance,
   before / after, smooth shading on. No visible facets in the close-up.
4. **Row 23 of 0328** (`tasks/0328-bug-and-friction-hunt-8.md`): a mesh update of an unnamed group whose parts all
   changed pairs the group by its tree place, so its step, eye and joint stay. Repeat case and proposed fix are in the row.
5. **Small:** the prune note of 0328 (text under its "Rows" table, "Seen in passing": `prune_old_caches` must never
   touch a `.partial-…` folder, as its docstring says); the stress README words of 0328 row 32 ("1 Model > Import
   STEP" → the app's real words); the Stress lines' limits in `pccheck/stress.py` set from the owner's numbers above
   (0315 open point: they were from the 4-core machine).

## Done when

- [ ] A 30 m Stress cable at Normal ≤ about 15,000 triangles (was ~127,000); the Stress model at Normal well under
      half of 13.9 M triangles; numbers before / after in the report (web machine), import seconds too
- [ ] Close-up and normal-distance pictures before / after in the report (`tasks/img/0325_*`), no visible facets
- [ ] Every other test model meshes as before (existing triangle counts unchanged, or each change explained)
- [ ] Row 23's repeat case keeps step, eye and joint (a test); the `.partial` folder is never pruned (a test)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] Guide (Import detail words if they change), CHANGELOG; the owner's re-check in the report: "PC check > Stress once
      more – compare Solid view, import Normal, render and web 3D lines"
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
