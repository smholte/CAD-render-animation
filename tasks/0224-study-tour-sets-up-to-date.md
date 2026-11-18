# 0224 – Study (findings only): every test-tour set brought up to the newest app

**Who:** worker · **Status:** open – can start (study, no code – no lane) · **Branch:** `task/0224-study-tour-up-to-date`
**Started by:** lead, 19 Nov 2026 (owner, 00:16, after the milling sets: "all test tours should get updated / most")
· **Model:** Opus · effort Medium
**Area:** this file only (+ small pictures under `tasks/img/0224/`, test models only)

## Goal

The test tour is where the owner – and later new users and his employer – see what the app can do. Most sets were last
changed at 0.2.101 or earlier (see `@tour_set(..., changed=)` in `blender/tour.py`), ~70 versions ago. This study goes
through **every set except the machining ones** (task 0223 does those) on the newest `main` and lists, per set, what
it shows today against what the app can do now, so the lead can brief the updates by lane.

## For each set and its stops

- **Works?** Go, the check, the animation: anything wrong, missing or ugly (a picture where it helps).
- **Up to date?** Newer functions or looks the set's subject now has that it does not use (examples to check: the
  better materials and marine looks, served cables and full spools, people and props for scale, weather and time of
  day, the sea and its cut-away / view cut, the new side panel and workspaces, Slice instead of Cutaway (0220),
  lifting plans, the Make list). Only what belongs to the set's subject – a set stays small and quick to build.
- **Looks good enough to show a client?** Model detail, materials, camera, light.
- **Proposal** (S / M / L): what to change, which lane's files it touches (tour sets share `tour.py`: group the
  changes so no two fix tasks edit the same set at once).

## Also

- Sets or stops that test the same thing twice; functions that have **no** stop yet (`core/functions.py` entries
  without `tour=`), and whether they need one.
- How long making the whole tour takes now (the owner's PC numbers are not known; measure on the web machine) and
  what a refresh adds.

## Done when

- [ ] A table: every non-machining set – works / up to date / client-ready / proposal / size / lane
- [ ] 2–5 fix packages for the lead, each with its sets, model · effort and lane, in the order that gives the owner
      the most for the least
- [ ] Short questions for the owner at the end
- [ ] No code changed; report merged to `main` (no release)

## Not in this task

The machining sets (0223). Fixing anything. The Cutaway → Slice rename (0220) – note only what it leaves.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**Findings:**

**Packages proposed:**

**Questions for the owner:**
