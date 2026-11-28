# 0379 – PC check: a Heavy line for weld speed, Stress memory with the import helpers, "Fresing Render" in Task Manager

**Who:** worker · **Status:** running · **Branch:** `task/0379-pc-check-lines`
**Started by:** lead, 28 Nov 2026 (open points of 0319 / 0368, 0315, 0178) · **Model:** Sonnet · effort High
**Area:** PC check lane – `fresing_render/pccheck/*` (you own the lines named here), `winexe.py` (row C), the
installer only if row C needs it, their tests, the guide's PC-check list. **Not:** the weld code (0372 changes
`weld_cad.py` this weekend – only call it), `installer/` beyond row C (0358 later).

## Rows

- **A (0319, 0368)** no Heavy line for weld speed: build an invented weld frame (~300 welds, like
  `tools/make_test_welds*`) at run time inside the PC check (`tools/` is not shipped) and time the weld finding at import
  and at a model update. One line, plain words, with the part and weld counts.
- **B (0315)** Stress's peak memory counts the app's own process only: add the import's helper processes (peak of the
  sum, sampled), and say which part is which in the line.
- **C (0178)** Task Manager still shows "Blender" for the app: give the Windows process the name / description
  "Fresing Render" (exe resources or the launcher) – Windows-only code, so an independent helper reviews it and the
  Windows CI job checks it.

## Done when

- [ ] Lines A and B in Heavy / Stress with numbers from the web machine in the report; C checked on Windows CI
- [ ] Tests added / updated; full suite passes (also on GitHub)
- [ ] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [ ] (Windows-only code) reviewed by a helper that did not write it
- [ ] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)
- [ ] **Owner's check** line: which PC-check mode and which lines to send to the lead

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
