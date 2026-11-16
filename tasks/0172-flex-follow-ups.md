# 0172 – Flex follow-ups from 0125: shot 11's bend past the gutter, lifted sheaves stand still, the D's depth right before Build, a swivel to test

**Who:** worker · **Status:** open · **Branch:** `task/0172-flex-follow-ups` (a web session may name its own)
**Started by:** lead chat, 16 Nov 2026 (open points 3–6 of task 0125) · **Model:** Opus · effort High · **Place:** Claude
Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Flex parts lane: `core/paths.py`, `core/catenary.py`, `blender/paths*.py` (`paths_sea.py`, `paths_rollers.py`,
`paths_swivel.py`), `ui_paths.py` (only the cables panel), their tests; the demo's sea/quadrant stages in
`blender/demo.py` (`set_down_depth` and the check after Build, shot 11); Test models lane additively: one new test
model maker + its `tests/data/` and `fresing_render/data/` copies, one new tour set; the tour, the PC check, the
function list and the guide sections `#swivel` / the quadrant chapter.
**Do not edit:** the Machining lane (0167 runs: `core/heightmap.py`, `core/machining.py`, milling tests), the CI files
of 0170/0171 (`tools/ci_precheck.py`, `tools/ci_times.json`, `.github/`, the Windows script); only the MIN counts in
`tools/ci_check_pccheck.py` and `MIN_CHECKS` / the lightest group in `tools/ci_real_app.py` (additive). Leave 0152's
demo realism (cable weight in water, lay-data box, ROV) to the next Demo task (0173): it comes after this one.

## Goal

The cable-lay demo's quadrant shots look right to the end: in shot 11 the cable no longer wraps round the gutter's end
in a big free bend, sheaves the cable has left stand still, the D is set down at the right depth with one Build (Make
demo faster), and the swivel head (0.2.103) gets a test model, a tour stop and a PC-check line like every other function.

## Background

Read the report of `tasks/0125-quadrant-sea-follow-ups.md` (Design table, "What changed", open points 3–6). Numbers there
are from the 4-core web machine.

1. **Shot 11 (open point 6).** While the D, tipped flat, comes down its last ~10 m (frames ~2514–2560), the cable has
   to go round past the gutter's end and back down. Since 0125 it does so in a free bend of the gutter's radius of up
   to ~180° (before: a hard kink back). The right behaviour: the hang-off comes off the gutter's **other end** once the
   cable's way down lies beyond it, or the cable lies off the D – decided by the geometry in the solver, not by a
   demo-only rule (a real cable does not wrap round the end of a chute it is not held in).
2. **Lifted sheaves (open point 5).** 0125's `paths_rollers.after_bake` stops ROLLERS the cable has left; a lifted
   SHEAVE that the cable runs past still turns with its coupling (subagent R's note).
3. **The D's depth before Build (open point 4).** The depth `set_down_depth` works out before Build differs from the
   built animation by 0.38 m; the check after Build corrects it with a **second Build: +55 s on Make demo**. Cause not
   found. Since then 0138 (Build starts from frame 1), 0159 (one-moment catenary on plain numbers) and 0160 (re-bake
   reads as Build reads, `catenary.hang_off_steady`, no warm start from the last Build) changed what Build reads – the
   gap may have moved or gone: measure first.
4. **Swivel (open point 3).** `FRCableContact.swivel` (0125, `blender/paths_swivel.py`) has no tour stop and no
   PC-check line: no test model has a swivel head. Its function-list entry `offshore.swivel` names neither.

## What to do

1. **Shot 11:** the cable leaves the gutter at the end where its way down lies; no bend outside the gutter of more than
   the gutter's own arc per point; no frame without a path; no step where the hang-off changes end (measure the
   cable's points over frames 2500–2600 before/after: largest direction change per point and between frames). Check
   shots 9–10 and 12 stay as 0125 left them (0125's numbers: kink at the leave point, D 16 mm over the seabed, pull
   head 3 cm over it).
2. **Lifted sheaves:** a sheave the cable has left (lifted, or no drawn cable touches it at a frame) stands still at
   Build, as rollers do; its own coupling put aside and restored by `after_clear`. Test on a small test model and on
   the demo (name the sheaves that now stand still).
3. **The D's depth:** find why the estimate before Build missed (or show it no longer does), fix it so one Build gives
   the D within `SET_DOWN_TOL` of the seabed, and drop the second Build. Make demo time before/after (same machine).
   Keep the check after Build as a test (it must not fire).
4. **Swivel test model + stop + line:** a small invented test model with a sheave on a swivel head and a wire that
   changes direction (e.g. a davit that slews while the wire runs to a fixed point): maker in `tools/make_test_*.py`,
   copies in `tests/data/` and `fresing_render/data/`, a tour set with a stop "The sheave turns to follow its wire"
   (what you should see, a number `check`, 0 clashes in `test_tour_clash.py`), a PC-check Full line, the function-list
   entry names both; raise the MIN counts (CLAUDE.md section 6).

## Rules

- New behaviour gets a test; a test that fails before the fix for 1, 2 and 3. Nothing loosened; the demo's tests and
  every tour set stay 0 clashes.
- Speed: Build on the demo (`tools/measure_cables.py`) and Make demo before/after, machine named. Build must not get
  slower by more than a few %.
- An **independent tester** (a subagent that did not write the change) tries to break 1–3: a gutter tipped at other
  angles, a D lowered on the other side, a sheave lifted and touched again, a swivel turning past ±180°.
- Guide: the quadrant chapter (shot 11) and `#swivel` get the new behaviour and the tour stop; tooltips if a setting
  changes. CHANGELOG + version last (section 7). Old projects open looking the same (test with a 0.2.103-style
  project if the stored data changes).

## Done when

- [ ] 1–4 done, before/after numbers in the report (bend per point in shot 11, sheaves standing still, D's depth
      after one Build, Make demo time)
- [ ] Swivel test model, tour stop, PC-check line, function-list entry; MIN counts raised
- [ ] Tests added/updated; GitHub run green; merged; version; report filled in

## Not in this task

0152's demo realism (cable weight in water ~38 kg/m at Ø 200, lay-data box + ROV in shot 8, handler tilt caption) →
0173 after this task. Older Flex open points: a cable with a spline/helix stretch (refused), the fleet angle's kink at
a sheave (0078), cables and hoses swaying in wind, tracks' playback cost (0159), the re-bake's 16 s final solve (0160).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
