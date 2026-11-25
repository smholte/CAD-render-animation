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

**Chat / date:** Claude Code on the web (Opus), 25 Nov 2026. Version **0.2.260**.

**What changed:**
- **New `importer/tube_mesh.py`** (no bpy): a long cable / hose is meshed as a grid instead of by OpenCascade.
  *Recognised by shape only:* every face is a tube face (not plane / cylinder / cone / sphere / torus, closed round one
  direction, round by its own curvature – 1/curvature round within 10 % of the median on ≥ 75 % of the face, along at
  most half that, no crease –, ends straight across) or a flat cap on a tube's end (area within 3 %); the part ≥ 20
  diameters long; faces of a tube in a row are chained. Anything else (hollow hose with ring caps, slanted cut end,
  square duct, short tube, any doubt or error) → `None` → OpenCascade as before.
  *Rule I chose:* one gap per Detail, `FACETS[...]["tube_gap"]` = 0.6 / 0.2 / 0.08 mm (Draft / Normal / Fine). Round:
  segments so the sag ≤ gap (Ø20: 10 / 16 / 25), raised where the kept rows need it (rows slanted across the tube, a
  lumpy stretch); along: a dense look every half radius, rows kept greedily while every dense row lies within the gap
  of the mesh's cross-section there, measured square to the tube on all n lines (bends, wobble and twist between rows
  all count). Normals are the surface's own (smooth shading exact); caps are fans on the tube's own end points; a chain
  shares its rings → closed mesh. Why one gap for both: it keeps Draft < Normal < Fine and puts the triangles where the
  shape needs them; the old 0.5 mm cap in mm with a 0.3 rad angle gave 60+ segments and a ring every few mm on the
  B-spline's knots.
- `step_reader._mesh_shape` asks `tube_mesh.plan` first (only with `facets`, i.e. every real import) and skips
  OpenCascade for such a part; everything downstream (face ranges for picking, colours, axes, cache) is unchanged.
  `CACHE_VERSION` 9 (meshes differ; older caches are read again once, model-update mesh reuse starts afresh once).
- **Row 23 of 0328** (`reimport._groups_by_place`): an unnamed group none of whose parts paired (all changed shape)
  pairs with the group of the same reader id (`fr_uid`), same parent, same number of parts, each again at the same id
  and kind and of about the same size; its parts pair as "changed". `_group_notes` reports such a group's move from
  the side of each box that kept its place ("moved 100 mm; 2 parts changed").
- **Prune note:** `prune_old_caches` skips every `.partial…` name (it deleted a half-written folder with its tree.json).
- **Stress:** limits / expected from the owner's run 25 Nov 21:06 (about twice his numbers): Draft 50/100 s, Normal
  70/150, Solid 15/60 (only the turning was given: 12 pictures at 1.13/s ≈ 10.6 s), Live 5/15, clash 40/80 (0327's
  37.9 s), render 20/40, web 3D 50/100, update 70/150. Lines without an owner number keep 0315's limits. The README /
  release notes say "1 Import > Import STEP…".
- Guide: Import > Detail has a paragraph on long cables and hoses. CHANGELOG.

**Tested and measured** (web machine, 4 cores, no graphics card):
- *Stress model, full size* (11,228 placed / 1,995 unique parts), the reader alone (`step_reader.py`, 3 helpers):

  | Detail | triangles placed before → after | the 48 cables (unique) | reader s before → after | meshing s |
  | --- | --- | --- | --- | --- |
  | Draft | 4.13 M → 2.12 M | 1.91 M → 0.13 M | 66.5 → 68.2 | 17.0 → 17.0 |
  | Normal | **13.91 M → 4.14 M** (30 %) | **9.25 M → 0.39 M** | **127.0 → 79.0** | 75.8 → 27.2 |
  | Fine | 34.71 M → 8.95 M | 24.46 M → 1.03 M | 262.0 → 88.0 | 211.8 → 29.4 |

  Largest cable at Normal 221,286 → 10,092 triangles; the 32 wiring looms are light too. Draft's time is the one-core
  read (46 s), as the owner's numbers said.
- *One 30 m Stress cable per kind* at Normal: 4,826–8,528 triangles (was 30,610–185,794), meshed in ~0.1 s (was
  0.5–3.5 s); 36 m ones 5,054–10,092. Each new mesh is closed (every edge twice), normals agree with every triangle, its
  area is 99.5–99.9 % of the CAD surface's; 20,000 random points of the CAD surface lie on average 0.14 mm, at most
  0.4 mm (lumpy stretches up to 1.2 mm) from the mesh (Blender's BVH). **The old mesh was worse than it looked:**
  OpenCascade's mesh of these long sweeps had only 56–82 % of the surface's area (flattened stretches) with 17–80
  edges shared by 3+ triangles, and was 3–11 mm off on average.
- *Hoses and cables that follow the motion can now read such a cable:* `flex_fit.tube_centreline` on the old mesh of a
  30 m Stress cable said "The part is made of separate pieces" (the broken mesh); on the new one it reads radius 14.0 /
  26.0 mm and a 15.6 / 27.6 m centreline in 0.1 s (`paths.centreline` too).
- *Every other test model meshes as before:* no solid of the 57 STEP models in `tests/data`, their shipped copies or the
  lifting cranes is recognised (their hoses, cables and ropes are cylinders and tori); `tests/test_tube_mesh.py` checks six of them,
  boxes, a long cylinder rod, a short tube, a hollow hose, a square duct and a slanted end (same triangle count as
  without the rule). The existing facet / importer / update tests pass (two of them only name
  `CACHE_VERSION` 9 now).
- *Pictures* (Cycles, CPU, 48 samples, glossy black cable, smooth shading = the cache's normals), tray scene from the
  Stress model's own tray run (722,556 → 91,824 triangles, cables 680,036 → 49,304):
  `tasks/img/0325_close_before.jpg` / `_after.jpg` (rendered 3840 × 2160, 0.5 m from the cable's bend, shown at 1600
  px), `0325_close_crop_100pct.jpg` (a 1200 × 700 crop at 100 %, before above after: no facets in either; the old mesh's
  outline differs a little where it was flattened), `0325_tray_before.jpg` / `_after.jpg` (1920 × 1080 → 1280 px). The
  pictures differ by 2.1 % RMS (close-up) and 0.4 % (tray).
- Tests: new `tests/test_tube_mesh.py` (18), `tests/test_cache_prune.py` (1, fails on the old prune), a row-23 test
  in `tests/test_mesh_update_changed_group.py` (4 variants; failed before: 1 lost its work, 3 had no report line);
  locally the importer / facets / meta / part hash / update-reuse / mesh-update / model-update / flex-fit / stress /
  tree-cache files: 271 + 34 passed.
- GitHub: see below.

**Open points / follow-up tasks:**
- **The owner's re-check:** PC check > Stress once more – compare the Solid view, import Normal, render and web 3D
  lines with the run of 25 Nov 21:06 (expected: Normal about 4.1 M triangles instead of 13.9 M).
- A cable from a real Inventor harness is untested here (no such file in the repository). If one comes in heavy, its
  faces are not what the rule expects (e.g. a hollow jacket, a moulded end): a STEP of one cable is enough to tell.
- Projects imported before keep their heavy cables until **Update to new revision…**.
- **Private demo kit:** its cables are its own copies of the old demo model; if any is a B-spline sweep it now comes in
  as a grid (lighter, closed). The kit hook and every function in `kit.json` `uses` are unchanged, but the lead may want
  the owner to run the private workflow by hand once.
- Not done (other tasks): study 0301's build speed-ups; the import popup (0340 / 0342).
- No helper agents ran (an importer change with a strict shape test and a fallback on any doubt; the usage rule).
