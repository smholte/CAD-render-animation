# 0090 – Way cover drawn at any axis position ("as drawn at … mm")

**Who:** worker · **Status:** done (0.2.66) · **Branch:** `task/0090-waycover-drawn-pose`
**Started by:** lead chat, 12 Nov 2026 (follow-up of 0035)
**Lane:** Way-cover – `blender/waycover.py`, `ops_waycover.py`, `ui_waycover.py`, `core/waycover.py`,
`tools/make_test_waycover.py`; additive: `blender/props.py` (one property per cover), `reimport.py` only if a model
update must carry it (additive, 0052 pattern); tests, guide, tour stop if cheap
**Model:** Sonnet · effort Medium (stuck: Opus) · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as 0077, 0085, 0089 and the Fable tasks 0058 and 0061; none of them touches way covers.

## Goal

A way cover works whatever position the axis had when the cover was drawn in CAD. The owner's own cover STEP is drawn
at mid-travel (376.5 mm); today it only fits when the CAD pose matches the axis zero, so for the 0035 demo the file had to
be re-posed by hand.

## What to build

- Per cover a setting **"Drawn at"** (mm, the axis value in the CAD file; default 0 = today). The sections' shares
  (k/N of the travel, housing counts) are then measured from that position: at axis = "Drawn at" every section stays
  exactly where CAD put it.
- **Read from the axis** button next to it: takes the axis joint's current value (the user poses the axis to where the
  CAD shows it). A short check line under it: "At 0 mm: section 1 … 5 at 0 / 75 / 150 … mm" or a warning when a section
  would leave its housing inside the axis limits.
- The carriage section (0035) is unaffected (share 1).
- Old projects: "Drawn at" = 0, joints, ratios and limits unchanged (test with a project saved by 0.2.64).

## Done when

- [ ] Test: the owner-like case – `test_waycover_a.step` with the sections drawn at mid-travel (make that variant with
      `tools/make_test_waycover.py`, not by hand) – builds with 0 warnings, every section at its k/N share at 4 axis
      positions, and at "Drawn at" every section on its CAD place within 0.01 mm; two covers with different "Drawn at".
- [ ] Old project opens unchanged; save + reopen + model update keep the setting.
- [ ] Panel: the setting and the button under the Covers list's details, tooltips, no cut-off labels; guide section
      Way covers updated (+ its picture if the panel changed); PC-check line `machining.waycover` extended or a new line.
- [ ] GitHub green; merged to `main` with the next free version; report filled in; `TASKS.md` updated.

## Not in this task

The "model copy moved by its root goes back at Build" bug (`fr_rest_basis`, found in 0035): it waits for 0085, which
moves the model about a pivot.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 12 Nov 2026

**What changed:** per cover `drawn_at` (props.py); each section's coupling gets offset `-share * drawn_at` and limits
`share * (axis limit - drawn_at)` (waycover.py `_apply`, `_limits_for`); `read_drawn`, `check_line`; button
"Drawn at: read from the axis" (ops/ui_waycover.py); `make_test_waycover.py --drawn-at MM` -> tests/data/test_waycover_d.step;
guide + panel picture; `machining.waycover` PC-check line extended (drawn at 200 mm); CHANGELOG 0.2.66.

**Tested and measured** (4-core web session, real Blender 5.2.3, no graphics card): tests/test_waycover.py 30 pass
(new: mid-travel model builds with 0 warnings, 5 axis positions at k/N, CAD place at "Drawn at" within 0.02 mm, two
covers with different values, save/reopen/model update, old project = 0 and unchanged offsets); real-app waycover 16/16;
GitHub run 43128694980 green (full, 11.2 min). Tolerance 0.02 mm (single precision), not 0.01. The old-project test
saves with the current code, not with a real 0.2.64 file.

**Open points / follow-up tasks:** none. The `fr_rest_basis` bug waits for 0085 (now merged). 1 run on the branch,
plus a docs-only run after merging `main` (0085's report).
