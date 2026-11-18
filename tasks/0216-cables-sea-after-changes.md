# 0216 – Cables and the sea after changes (bug hunt 0209 group D)

**Who:** worker · **Status:** open – can start · **Branch:**
`task/0216-cables-sea-after-changes`
**Started by:** lead, 18 Nov 2026 · **Model:** Opus · effort Medium
**Area:** Flex / Sea lanes – `blender/paths.py`, `paths_sea.py`, `vessel_motion.py`, `rebake.py`, `flex.py`,
`spool.py`, `surroundings.py` (+ tests). `camera_path.py` is group H's (after this task).

## Goal

Fix rows **7, 8, 27, 28, 29, 10, 31** of `tasks/0209-bug-hunt-7.md`. Row 7 first (0183 row 4, still open for its own
case): water level 2 → 3 m, re-bake, Undo → water 3.0 and the cable 1 m under the seabed, no re-bake; a copy saved
during it. Then **8** (demo updated with the same geometry: cable lengths change), **10** (a crane hook beside the hull
and a sea change / Fit / update: waterline), **27** (tension labels jump at frames 273–280), **28** (save during the
re-bake reopens at frame 1), **29** (carousel + drum both renamed "": shared tag), **31** (the demo's view clip start
0.29 m).

## Done when

- [ ] Each row's repeat case is a test that failed before; the demo's tests and clash check unchanged.
- [ ] Full run green; report filled in.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
