# 0375 – Sea and Vessel at work follow-ups: seabed square, spray made new, stale channels after Build

**Who:** worker · **Status:** done (0.2.274) · **Branch:** `task/0375-sea-vessel-at-work`
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

- [x] A, B, C fixed with tests; a sea change with spray measured before / after (report)
- [x] Tests added / updated; full suite passes (also on GitHub)
- [x] (UI) screenshots checked with tools/ui_screens.py; every new button has a tooltip; the user guide, PC-check line,
      tour stop and function-list entry follow the change (`since=` / `changed=`)
- [x] (Windows-only code) reviewed by a helper that did not write it
- [x] Report below filled in (incl. **Open points** and an **Owner's check** line when he should try something), merged,
      released (CLAUDE.md section 7)

**Running beside it (weekend 28–29 Nov):** 0371 Demo · 0355 / 0356 Assets · 0372 Welds · 0347 Machining · 0349
Lifting · 0353 Web 3D + House · 0373 guide-picture tool · 0374 cable-lay line · 0375 Sea · 0377 Start & windows ·
0379 PC check · findings-only 0380 / 0381. Shared files only additively, each in its own spot: `props.py`, `tour.py`,
`core/functions.py`, `tools/guide_screens.py` (0373 owns its start-up code), `pccheck/checks.py` / `heavy.py` (0379
owns the lines it names). Whoever merges second updates its branch to `main`; versions: CLAUDE.md section 7 step 0.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (branch `task/0375-sea-vessel-at-work`), 28 Nov 2026. No subagents (no
Windows-only code; the changes are small and tested by broken-copy checks – the new tests fail without each fix).

**What changed:**
- **A – seabed square (view only).** In Detailed the plain square under the rippled patch is now a ring round a middle
  piece the box's shape (`surroundings._seabed_mesh`, point attribute `fr_plain` = end, side, kind). A new way of the
  view cut, **Hole** (`sea_view_cut.HOLE`, group "FR view cut 4"): the live way, then the ring's inner corners go onto
  the box's corners and the middle piece onto them and down under the pit – a hole exactly the box's shape that
  follows the box however far the seabed slid. In a render the middle piece fills the ring: one plain square, as
  before. First tried "cut the plain face exactly" (Separate + Boolean + Join): +3.6 ms a frame on the seabed – dropped.
- **B – spray kept.** `_spray_group` keeps its group and only sets its numbers (`_build_tree` / `_Replay` of 0202);
  `clear` no longer deletes the spray group and material while a sea with spray is still wanted. Other nodes (bow
  spray on/off, another number of waves) make it new as before.
- **C – Vessel at work after Build.** Build stores what of the panel its keys came from (`fr_vw_built`:
  `vessel_work.build_key` – the setting, plus the thruster rows when anything turns or a step changes it). A panel
  change that makes it differ (`vessel_work.changed`, reached from the panel, the thruster rows and Weather & time's
  vessel speed) takes the built animation off with a message – the app's usual "Build again". Setting the same value
  again, or a change while the vessel lies still with no step (Build keyed nothing of it), keeps the Build.
- Guide: Vessel at work ("change the panel after Build …") and the cut-away paragraph. CHANGELOG 0.2.274.

**Tested and measured** (4-core web machine, the invented vessel of `tests/test_sea_cutaway.py`):
- Sea change with spray (Weather & time on, Wind sea, Beaufort 7 → 7.5 / 8 / 8.5 …, 8 changes, median, the whole
  change from setting the wind to the end of `world.apply`): **Simple 0.87 s → 0.33 s, Detailed 1.05 s → 0.58 s**; the
  spray group alone 0.53 s → 0.07 s (the spray material is kept too).
- View cut of the seabed alone (Detailed + ground cut, 10 updates × 5, best): live way 0.70–0.95 ms, Hole 1.10–1.27 ms
  (+0.3 ms; the exact way's try 4.5–5.4 ms). `test_cost_of_the_view_cut` (bound 1.5 ms over the four cut objects): +0.1
  … +1.3 ms here over several runs (main: −0.2 … +1.4 – the noise of this machine).
- New tests: `test_sea_view_cut.py::test_the_plain_seabed_square_leaves_the_pit_open` (rays down into the box meet no
  seabed above the pit's bottom, outside they meet it at the seabed; again after a 150 m slide – fails with the live way),
  `test_sea_change.py::test_the_spray_is_kept_at_a_sea_change_and_equals_a_fresh_build` (Simple, Detailed: kept node
  for node equal to a fresh build; spray off removes it), `test_vessel_work.py::test_a_change_after_build_takes_the_old_keys_off`.
- GitHub: one run, green (46159633379, full).
- Locally: the sea, vessel, seabed-speed, surroundings, web 3D sea, marine looks, view clip, re-bake files (395) and the
  weather files (452) pass. GitHub: see below.

**Open points / follow-up tasks:**
- A sea change is still ~0.3–0.6 s on the test vessel and ~2 s on the demo (0202's numbers): ≤ 1.5 s on the demo needs
  0195 A4's change-in-place path (later, not this task).
- A Vessel at work **step**'s own settings changed after Build are the animation steps' business, as before (not
  looked at here).
- Projects from before keep their single seabed square (the live way) until the sea is made again – no upgrade (before
  the baseline).
