# 0375 – Sea and Vessel at work follow-ups: seabed square, spray made new, stale channels after Build

**Who:** worker · **Status:** running · **Branch:** `task/0375-sea-vessel-at-work`
**Started by:** lead, 28 Nov 2026 ("Lead review 20 Nov" Sea points in TASKS.md; 0202, 0192 open points) · **Model:** Opus ·
effort Medium
**Area:** Sea lane – `core/sea.py`, the sea in `surroundings.py`, `sea_view_cut.py`, the spray in `weather_fx.py`,
`blender/vessel_work.py`, `core/vessel_work.py`, `ops_vessel_work.py`, `vessel_motion*` only if needed, their tests.
**Not:** `paths_sea.py` and the cables (0374), web 3D files (0353), the sea-change-in-place path of 0195 A4 (later).

## Rows

- **A (0202)** Detailed + ground cut: the plain seabed square 6 cm under the rippled patch is one 2 km face that covers
  the ground cut in the view – split it (or cut it with the rest).
- **B (0202)** the spray group (weather, Beaufort ≥ 5.5) is made new at each sea change – change it in place.
- **C (0192 / 0154)** Vessel at work's `fr_vw_*` channels are keyed at Build and go stale when its panel changes after
  Build – re-key them on change, or show "Build again" the same way the app does for other build data.

## Done when

- [ ] A, B, C fixed with tests; a sea change with spray measured before / after (report)
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
