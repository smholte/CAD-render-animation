# 0373 – Guide pictures: the per-panel modes stop making blank / wrong pictures; Coolant and Spools pictures redone

**Who:** worker · **Status:** open – can start · **Branch:** `task/0373-guide-pictures-tool`
**Started by:** lead, 28 Nov 2026 (open points of 0346, 0348, 0368) · **Model:** Sonnet · effort Medium
**Area:** Docs lane – `tools/guide_screens.py` (its start-up / mode set-up: you own it this weekend), the pictures it
makes in `docs/img/`, the guide text only where a picture changes, its tests. **Not:** app code (`fresing_render/`).

## Goal

Every per-panel mode of `tools/guide_screens.py` makes the right picture on a fresh machine, with no hand-set
environment variable – and the pictures that came out wrong are made again.

## Background – three reports, one fault

- **0346:** the panel modes (coolant, air) picture Blender's **Item tab (Transform)** with a fresh settings folder, so
  `docs/img/panel_4_coolant.png` was not remade and still lacks the liquid rows.
- **0348:** pictures are blank unless `FRESING_WORKSPACE_START="All functions"` is set **before** Blender starts – the
  tool's own `setdefault` comes too late.
- **0368:** the other per-panel modes have the same empty-picture fault (`spools_panel` checked: empty) – they need
  `workspaces.use_all` too.
- 0367 (0.2.270) hid Blender's Item / Tool / View tabs outside Full access – check the tool after it.

## What to do

1. Find the root cause once (environment and workspace before Blender's start; which workspace / access each mode
   needs) and fix it in one place, so no mode needs a hand-set variable.
2. Run every mode; list each picture as OK / was wrong / changed in a table in the report. Remake the wrong ones
   (at least the Coolant panel with the liquid rows and the Spools panel).
3. A check that cannot pass on a blank or Item-tab picture (e.g. a minimum detail level and the Fresing tab's title
   row found), run by the tool and by a test on a few modes.
4. Other tasks this weekend (0347, 0349, 0374) may add their own modes in their own spots – don't reorder the file.

## Done when

- [ ] All modes run on a fresh settings folder with no extra variables; the table in the report
- [ ] Wrong pictures remade; the blank / wrong-tab check in place
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
