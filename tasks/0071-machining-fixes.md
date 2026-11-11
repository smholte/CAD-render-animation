# 0071 – Machining fixes from the bug hunt (0068 rows 6–11, 14–16, 18, 19a–c) + toolpath glow speed (0069 #5)

**Who:** worker · **Status:** open – start now (Wed 11 Nov); **merged before Thursday 12 Nov 08:00** (0061 starts in
this lane then, and builds on the tool copies fixed here) · **Branch:** own
**Started by:** lead chat, 11 Nov 2026 (from bug hunt 0068 and study 0069)
**Lane:** Machining – `blender/toolchange.py`, `gcode.py`, `ops_gcode.py`, `doublearm.py`, `machining.py`,
`coolant.py`, `rotary.py`, `air.py`; the joint specs in `blender/joints.py` (row 14 only) and `build.py:repair_uids`
(row 15 only); tests
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0070** (queue, updates, project lock, a `save_post` handler). Do not touch those files, nor
`animation.py` / `reimport.py` (0058 Thursday) except a one-line call if a row truly needs it (say so in the report).
Two releasing tasks at once: take the version number last; whoever finishes second merges `main` once and renumbers.
**If it cannot be green and merged by Wednesday 22:00:** push the branch, report, stop; the lead then decides whether
0061 goes first on Thursday.

## Goal

Every finding below is confirmed with a script in `tasks/0068-bug-hunt-2.md` – read its rows first. Fix them so that
an animation with two G-code steps, the double arm, coolant, rotary axes and a model update all show what the program
does – in the view and in the queue's video alike – and milling plays smoothly next to a big machine.

## What to fix

1. **Rows 6 + 7 (worst)** – two G-code steps in one animation: spindle copies made once per build and looked up per T
   (like the pocket copies); each step's copies hidden at its end; milling and chips read the copy that is **visible**
   in each time window; double-arm pot/arm copies reused across steps, keyed by T and pocket – no tool shown twice.
2. **Row 8** – the changer animation placed from the same start point `bake_step` uses (the joints' state at the
   step's start), so it plays in step with M6 after a joint step or a second program step; steps do not overlap.
3. **Row 9 + 18** – coolant hoses: update the view layer after `ensure_root` before `_layout` (first Build = second
   Build = the queue's video); after a model update re-parent the root and re-apply the wet look.
4. **Rows 10 + 11** – rotary: `auto` sign worked out with the outer axes turned back to 0 (C turns the right way when
   built with A at ≥ 90°); Check clears the keys **before** reading the pose, so it leaves the machine where it was.
5. **Rows 14 + 15** – a model update keeps the double arm's `fr_atc` tags (carry them in the joint specs, or tag again
   in `gcode.after_model_update`); `repair_uids` takes the CNC/tool/milling `*_uid` strings again from their objects.
6. **Row 16** – per-frame cost: keep the tool copies and wet parts in the runtime dict (cleared at Build / load /
   undo); check the motion signature on a depsgraph change, not at every frame. Measure on the Heavy machine + 5-axis
   model as 0068 did (motion only 8.3 ms; + milling 37.9; + coolant 57.2): aim **≤ 20 ms** with milling + chips +
   coolant (25 fps budget 40 ms). The cut must stay the same (compare meshes).
7. **Row 19 a–c** – `make_pots` checks all new pots before removing the old ones (and no half-made arm joint);
   the air cone on the tip of the tool actually in the spindle; `rotary.LAST_CHECK` cleared on load and when the
   A/B/C pick changes.
8. **Study 0069 #5** – the drawn toolpath (`gcode._material`) and the air cone (`air.py`) set
   `emission_sampling = "NONE"` like `surroundings.py` (measured 2.0–2.6 → 0.6 s per frame with many glowing
   triangles). Same look in the render.

## Done when

- [ ] A test per row that fails on 0.2.55 and passes now (0068's scripts as the start), including two G-code steps
      with manual, carousel and double-arm changes; the existing milling, tool-change, double-arm, coolant, rotary,
      toolpath tests green; tour and PC check green (the all-tour clash test still 0 rows).
- [ ] Per-frame numbers before/after in the report (Heavy machine + 5-axis model, the 0068 way).
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0071 done; 0068 rows marked fixed there.

## Not in this task

Queue rows (0070), clash and decal rows (0072). Tool marks (0061), the height-map cutter (0069 #8), acceleration
timing (0069 #16), chips on a moving 4th-axis table.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
