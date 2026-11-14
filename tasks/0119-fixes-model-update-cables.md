# 0119 – Bug-hunt fixes A: a model update keeps drums, carousels, riders and tracks

**Who:** worker · **Status:** open – can start · **Branch:** `task/0119-fixes-model-update-cables` (or the web session's)
**Started by:** lead chat, 14 Nov 2026, from bug hunt 0118 (`tasks/0118-bug-hunt-3.md`)
**Area:** Flex parts lane (model-update code only): `blender/spool.py` (`after_model_update`), `blender/paths_riders.py` (`after_model_update`), `blender/tracks.py` (`after_model_update`), the flex items' reading in `blender/flex.py` only where row 3 needs it; their tests. **Do not edit:** `reimport.py`, `sequence.py`, `vessel_motion.py` (0121), `queue.py`, `animation.py` (0120), `importer/`, `build.py`, `faces.py` (0117).
**Model:** **Sonnet · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Fix rows **2, 3, 7, 17** of the bug hunt (lost work at a model update: other models' spools undone, a drum whose ID changed, a rider part that is gone, track pads/plates and a wheel's coupled flag).

## How

- The rows' text in `tasks/0118-bug-hunt-3.md` (Findings) gives where, what happens, the proof and a suggested fix.
  Read each row, repeat its proof first (it must fail), then fix. **Every fix gets a test that failed before**
  (CLAUDE.md section 6). The suggested fix is a suggestion: a better one is fine, say why in the report.
- A row that turns out not to be real (cannot be shown on today's `main`): say so in the report, no change.
- No new features, no UI redesign. A visible change (a new warning, a note) gets its tooltip/guide line; no new tour
  stop or PC-check line is needed for a fix unless the row asks for one.
- One version at the end (take the number last, CLAUDE.md section 2).

## Done when

- [ ] Each row: fixed with a test that failed before, or shown not real (with how)
- [ ] Full run green on GitHub; CHANGELOG in plain words (what the owner would have noticed); version taken last
- [ ] Report filled in; TASKS.md row → done

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 14 Nov 2026

**What changed (per row):**
- **Row 2** (`spool.after_model_update`): only spools whose part or coil is in the updated model (`mapping` / `by_uid`) are
  taken apart and set up again; other models' drums and carousels stay. Real: confirmed by the new test.
- **Row 3**: `part_uid` / `coil_uid` are written from the new objects, so a second update finds the drum.
- **Row 7** (`paths_riders.after_model_update`, now gets `mapping`): a part of the updated model that is gone is dropped
  with a note ("N of its parts are gone in the new revision"); the old object is used only for parts in neither table
  (another model). Not done through `by_uid.get(...)` alone, because a gone part's ID is in `mapping` as `gone:`.
- **Row 17** (`tracks.after_model_update`): a note for pads/plates that are gone; the "coupled" flag is compared through
  `mapping` (the wheel's new ID).

**Tested:** new `tests/test_model_update_cables.py` (4 tests, all failed before the fix, pass after); `test_spool.py`,
`test_tracks.py`, `test_paths_sea.py` pass locally (36). Rows 3, 7, 17 call the update hooks with the tables a real update
hands them; row 2 is a real update of a second model (crane A to B). GitHub run: see below.

**Open points:** none. No subagents. Runs: 1 (no version clash).
