# 0237 – Fix from bug hunt 0209, group G: a mesh model update of a moved group whose part also changed

**Who:** worker · **Status:** running · **Branch:** `task/0237-mesh-update-moved-group`
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

- [ ] Both cases keep the Hide step's target, the eye's hide and the joint; the report line is right
- [ ] 0183 row 5's, 0139's and every reimport test green; update time not worse (numbers in the report)
- [ ] Full suite green; report filled in, merged, released

## Not in this task

STEP updates (unchanged), lifting loads on updates (0214 done), other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
