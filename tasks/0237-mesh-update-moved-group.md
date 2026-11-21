# 0237 – Fix from bug hunt 0209, group G: a mesh model update of a moved group whose part also changed

**Who:** worker · **Status:** done (0.2.186) · **Branch:** `task/0237-mesh-update-moved-group`
**Started by:** lead, 20 Nov 2026 (bug hunt 0209 row 5; after 0214) · **Model:** Opus · effort Medium
**Area:** Import lane – `blender/reimport.py` (`_made_assemblies` and the pairing of unnamed parts; nothing else in it),
`tools/make_test_mesh.py` only if a new test file is needed, tests (`tests/test_reimport*` / `test_mesh*`).

## Goal

Updating a mesh model (glTF / OBJ / FBX) where a group was moved **and** one of its parts changed keeps every step,
joint and hide that pointed at that group and its parts – today the update says "6 parts kept" but loses the Hide step's
target and the eye's hide, and with unnamed parts says "4 kept, 2 new, 2 missing" and deletes the joint (lost work).

## Background

Bug hunt 0209 row 5 (`tasks/0209-bug-hunt-7.md`): `reimport._made_assemblies` (~253) demands that **every** voting part's
box-middle shift equals the group's shift within 5 mm. Case: mesh (glTF) update, unnamed group B moved 100 mm and one of
its parts 20 mm wider → the wider part's box middle moves 110 mm, the vote fails. 0183 row 5's own case (move only)
holds (0187 / 0192 fixed it). Suggested fix: vote by median / majority shift (or part origins); pair unnamed parts by
shape + the group's common shift. Earlier mesh-update work: 0139 (rows 3, 4, 13, 15, 16b–e of 0131) – read its report
for how pairing works now. Running beside you: 0232 (Lifting L5) uses `lifting.after_model_update`, never `reimport.py`;
0229 adds a model-update test for a wrap set by hand (tests only).

## What to do

1. Reproduce with a test (glTF made in the test or by `make_test_mesh.py`): group B moved 100 mm, one part 20 mm wider;
   with named and with unnamed parts; a Hide step, an eye hide and a joint on group B. The test fails today.
2. Fix the vote (median / majority of the shifts, a part that changed shape does not veto; a real re-arrangement still
   counts as moved parts) and the unnamed pairing (shape + the group's common shift). Keep 0183 row 5's and 0139's cases.
3. The update report names what it did ("group B moved 100 mm; 1 part changed").
4. Speed: the update time of the test crane mesh and the EGR-sized case 0139 measured, before / after.

## Done when

- [x] Both cases keep the Hide step's target, the eye's hide and the joint; the report line is right
- [x] 0183 row 5's, 0139's and every reimport test green; update time not worse (numbers in the report)
- [x] Full suite green; report filled in, merged, released

## Not in this task

STEP updates (unchanged), lifting loads on updates (0214 done), other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 20 Nov 2026 – version 0.2.186.

**What changed** (`blender/reimport.py` only, plus tests and one guide paragraph):
- `_made_assemblies`: the vote no longer needs every part to move with the group. `_moved_along`: parts of unchanged
  shape vote (all parts when every one changed), more than half must have moved by the group's move – a widened part
  does not veto. A group whose paired parts (≥ 2) all went to one new group, and that group's all came from it, pairs
  even when its parts were re-arranged inside it.
- New `_shifted_made_parts` (runs before `_made_assemblies`): unnamed parts ("Node 7") left unpaired in an old/new
  group pair (not paired elsewhere, or paired with each other; no parts sent elsewhere) pair by shape at the shift most
  of them share (`_best_shift`: ≤ 64 candidate shifts from the rarest shapes, counted with one k-d tree per shape);
  then the only part of its shape on both sides (re-arranged); then a leftover whose box middle sits at the shift
  within 5 mm + half its size change per axis (the changed part). A pair must hold at least half of both groups'
  loose parts.
- `_group_notes`: one report line per reader-named group that moved: "Node 4 moved 100 mm; 1 part changed – its work
  is kept" (move = the median shift of its unchanged parts). STEP updates unchanged (only made-name records).
- Guide: one sentence in "Update to new revision…" (Mesh models). No new function, PC-check line or tour stop.

**Tested and measured** (4-core web machine, bpy module):
- New `tests/test_mesh_update_changed_group.py`, 13 tests: moved 100 mm + B1 or B2 20 mm wider × node moved / boxes
  drawn moved × named / unnamed parts (8; all failed before – named: Hide step + eye lost; unnamed: 4 kept, 2 new,
  2 missing, joint deleted), moved only (control; the unnamed-parts one failed before too), a re-arrangement with a
  move (both parts + the group's work kept), a removed group + a new group of other shapes elsewhere (not paired).
- Area tests (mesh import/reader/independent/fixes, 0188 moved groups, 0162, model update, phase2, stacked joints,
  hover): 305 passed.
- Update times, before → after: test mesh crane a→b 0.48 → 0.27 s, a→a 0.42 → 0.46 s (noise); 0139's N boxes same
  file 1,500: 7.4 → 7.6 s, 3,000: 21.8 → 22.9 s (noise level); 3,000 unnamed boxes in a group moved 100 mm (+ a fixed
  group): 23.4 → 23.3 s, and now 3,003 kept instead of 3 kept / 3,000 new / 3,000 missing; 1,000 identical unnamed
  boxes moved: 5.4 → 4.9 s, all kept (was 1,000 new / missing). The EGR model itself was not run (not on this machine).
- GitHub: 2 full runs, both green – run 44836081391 (the branch), run 44843341700 after merging main (0.2.185 had
  gone to task 0239 meanwhile: renumbered to 0.2.186); main fast-forwarded to that commit.

**Subagents / independent review:** none (skipped to save usage; the change is pure matching logic with its own tests).

**Open points / follow-up tasks:**
- A group where *every* part changed shape and the group moved: its unnamed parts are still new / missing (no shift
  to agree on).
- Old behaviour kept (not this task): unnamed parts whose nodes all sit at the model's origin pair by "Node n" name +
  origin, so a removed group and an added group of other shapes drawn elsewhere can pair (found while writing the
  control test; the test therefore moves the new group's node).
