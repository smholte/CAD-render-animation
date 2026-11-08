# 0043 – Second import keeps the surroundings in place; less memory while making a 4K MP4

**Who:** worker · **Status:** open – can start · **Branch:** `task/0043-hall-relay-mp4-memory`
**Started by:** lead chat, 8 Nov 2026 · **Lane:** Scene & Render – `blender/surroundings.py` (and the call that
re-lays it after an import), `blender/queue.py` `encode_mp4` / `blender/video.py` (the encode only); tests; CHANGELOG
**Model:** Sonnet · effort Medium · **Environment:** "CAD-render-animation" (real Blender at start, CLAUDE.md section 4)

Runs next to 0040 (tool library, Machining lane). Do **not** change the STEP importer itself, G-code, milling or
the tool files – if the fix seems to need them, stop and write it in the report.

## Goal

1. Importing a second model into a project with surroundings (hall, deck, quay …) leaves the surroundings where
   they are, unless the owner asks to fit them again.
2. Making the MP4 of a 4K queued render does not hold gigabytes of frames in memory.

## Background

- `tasks/0037-owner-mill-gcode-demo.md`, problem 5: "Import STEP of a second model re-laid the surroundings (hall
  moved ~0.3 m in X and Y, its high part ~0.36 m up)". The owner's mill project has a CNC hall; adding a part (a
  vise, a new tool, the workpiece) must not move the hall under the machine.
- Same report, line ~158: while encoding, the sequencer keeps every 4K frame in its cache (+33 MB per frame up to
  the 4 GB cache limit), inside the runner that still holds the whole project. Fine on the owner's 47 GB, risky on
  smaller PCs and next to long renders. The owner's 4K video: 501 frames.

## What to build

1. Find why an import re-lays the surroundings (likely: surroundings are fitted to the bounding box of all parts
   after every import). New behaviour: after the **first** import surroundings are laid as now; after later imports
   they stay put. If the new model sticks out of the floor area or through a wall, show a note in the Surroundings
   panel with a button **Fit surroundings to the model** (tooltip). Model update (re-import of the same model)
   behaves as before.
2. MP4 encode: turn off or limit the sequencer's frame cache for the throw-away encode scene (and/or encode from the
   frames in a lighter process if that is simpler and not slower). Measure peak memory and time for a 4K encode of
   ~250 frames before/after; the output must be identical in look (same codec settings, frames, finishing).
3. CHANGELOG entry in plain words; guide line in Surroundings about the new button; PC-check line only if cheap.

## Done when

- [ ] Test: project with a hall + model A, import model B → hall position/size unchanged (to 0.1 mm); the note and
      **Fit surroundings to the model** work; first import as before; model update as before.
- [ ] 4K encode: peak memory and time before/after in the report (the brief expects at most a few hundred MB extra
      over the project); MP4 plays, frame count right, finishing (titles, captions, watermark) unchanged.
- [ ] Tooltip check 0 missing; tests; GitHub green; merged and released; `TASKS.md` updated; report filled in.

## Not in this task

Other 0037 problems (Motor tick, "//" path – after 0041; two way covers per axis – 0035). Faster encoding.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 8 Nov 2026

**What changed:** A later import leaves the surroundings alone when only models were added (`surroundings.ensure`:
`_only_added`); if the new model sticks out more than 10 % past the old box, `fr_misfit` is set and panel 5 shows a
note plus the button **Fit surroundings to the model** (the old "Put on the floor again", renamed). First import and
model update behave as before. The MP4 encode scene turns the sequencer frame caches off (`queue._no_frame_cache`).
Version 0.2.35, CHANGELOG, SURROUNDINGS.md and guide line updated.

**Tested and measured** (4-core Linux web session): new test `test_second_import_leaves_the_hall_in_place`
(hall unchanged to 0.1 mm, note, button, tooltip check 0 missing) and `test_mp4_encode_scene_keeps_no_frame_cache`.
4K encode, 250 frames of 3840x2160: peak memory 5,718 MB -> 1,684 MB, time 93 s -> 88 s, output file the same size
(51,441,141 bytes both). GitHub run on the branch: green (full, 12.3 min). 1 run needed.

**Open points / follow-up tasks:** Not merged to `main` and not released: this session was told to work only on
branch `claude/happy-franklin-5c4rl3` (same commit as `task/0043-hall-relay-mp4-memory`); the owner decides on the merge.
No PC-check line (not cheap to show). Leftover branch for the owner to delete later: one of the two above.
