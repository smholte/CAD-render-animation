# 0186 – Fix: Fast 3-axis leaves a square hole through the workpiece (bug hunt 6, row 2)

**Who:** worker · **Status:** running · **Branch:** `task/0186-fast-3axis-hole`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Opus · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Machining lane (`core/machining.py` `_MapSide._below` / `_piece`, its tests)

## Goal

A milling animation with **Fast 3-axis** (on by default) never shows a hole that the program did not cut.

## Background

- Row 2 of 0183: tour set "toolpath", the toolpath's own default settings (4,480 moves), Detail Normal, Fast 3-axis
  on, Build → at frames 241 and 251 one 6.4 × 6.4 mm map tile is dropped: its mesh is not manifold
  (`Error.NotManifold`, 821 vertices), `Manifold(mesh)` is empty, `t.solid ^ below` is empty. `_column` already checks
  the status and falls back to a box; `_below` does not. New in 0.2.134 (0167); 0.2.125 has no hole. Deterministic.

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [ ] `_below` (and any other place that builds a `Manifold` from a map tile) checks the status: not NoError or empty →
      the tile's 0146 right-triangle mesh, else a box as `_column` does; say in the report which tiles took which way.
- [ ] Test: on the row's case a ray from above through every map tile meets a face at every frame of the cut (the
      exact cut has 0 such columns). Plus a unit test with a made non-manifold tile.
- [ ] The height-map tests of 0146/0167 still pass; KNOWN FAULT markers unchanged unless fixed (say which).
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

The other 0183 rows; tool marks; the toolpath maker.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
