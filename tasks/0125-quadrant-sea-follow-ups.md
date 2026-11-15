# 0125 – Quadrant and sea follow-ups: the D on the seabed, no lost path, no kink, the bow the right way

**Who:** worker · **Status:** open · **Branch:** `task/0125-quadrant-sea-follow-ups` (or the web session's branch)
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort High
**Area (Flex parts lane + Demo models lane + the bow in the Scene & Render lane):** `fresing_render/core/paths.py`,
`core/catenary.py`, `blender/paths*.py` (incl. `paths_sea.py`, `paths_riders.py`), `blender/flex.py` only if needed,
`blender/spool.py` only if the keep-tight payout needs it, `blender/demo.py` (stages `sea` and the quadrant stages of
0082), `fresing_render/demo_model/` if a demo part must move, `core/weather.py` (`BOW_AZ`) and the places that read it,
their tests. **Do not edit:** `blender/sequence.py`, `core/sequence.py`, `ui_motion.py` beyond the cable boxes (task
0129); `tools/site_projects/`, `site/` (task 0128); the CPS run (task 0126 comes after this one in the Demo lane).

## Goal

Demo shots 9–12 (the second end over the stern, lowered, tipped, let go, back) look right: the D stands on the seabed
instead of in it, the cable never loses its path, no kink where it leaves the gutter, the wires and swivels follow
what pulls them, and "wind from the bow" / the wake agree with the way the vessel actually points.

## Background

All from the report of task 0082 (`tasks/0082-quadrant-operations.md`, open points 1–7) and 0081 (open points):
1. **The D sinks 0.76 m into the seabed in shot 11** (done so that the cable round its gutter lies on the seabed at
   the let-go); the pull head lies 0.4 m below the seabed line (vessel heave is in the stored let-go places).
   Wanted: let go **at** the seabed and let the cable settle onto it – an app ability: **a let-go cable (or the stretch
   of it that is no longer held) sinks onto the seabed** over a short time and lies there (seabed from 0081).
2. **Frames 1924–1927 of the second end have no path** ("'QUADRANT GUTTER' and 'Bend 1' overlap"; the last good
   shape is kept). Horn A is read as a bend, not a chute.
3. A **~6 cm kink** where the catenary leaves the gutter at the start of the lowering (out of the gutter's plane).
4. The **tipping-wire swivels** follow the handler tilt by ratio (0095), not the wire; a keep-tight sea cable gets a
   **step in its payout** when its hang-off changes.
5. Build warnings that should not show: "Second end piles up 0.00 m"; "A&R wire no longer touches the pulley at
   frame 1" (by design, hidden then – say nothing, or say it only when the wire is visible).
6. 0081: **rollers after a horn's hang-off keep turning** with the cable though it left the horn before them.
7. **The bow:** `core/weather.BOW_AZ = 180` (bow at −x, as the Vessel deck surroundings) drives "wind from the bow";
   the demo vessel (and 0081/0082) have the bow at +x. 0082 made the wake follow the bow; the wind did not follow.
   Make one source of truth for which way the bow points (the vessel's heading / the model) and read it everywhere
   (wind from the bow, wake, anything else that assumes −x). Old projects keep how they look (test with a 0.2.88
   and a 0.2.95 project if the bow source changes saved data).

Rules that bite here: CLAUDE.md section 8 – Blender merges keys closer than 0.01 frame (also on driver F-curves),
float32 joint values, `screw_between` false rows when something turns slowly (0091: the demo clash test runs with the
sea at rest), the demo's clash check is split in windows (`tests/test_demo_clash.py`).

## Done when

- [ ] Shot 11: the D rests **on** the seabed (no part of it more than 5 cm below the seabed line at any frame,
      measured on the D's mesh, with vessel heave on); the pull head on the seabed, not under it; the cable round the
      gutter settles onto the seabed after the let-go (new ability, tested on a small test model too – not only the
      demo).
- [ ] Every frame of the second end has a path (no "overlap" fallback; a test walks frames 1900–1950 of the demo
      animation, or the same moment on a small model); horn A is a chute where it is one.
- [ ] Where the catenary leaves the gutter the cable is smooth: direction change < 1° between neighbouring points, no
      step out of the gutter's plane (measured, before/after in the report).
- [ ] The tipping-wire swivels point along their wires (angle between swivel and wire < 1° over shots 9–12); a
      keep-tight cable's payout has no step at a hang-off change.
- [ ] No "piles up 0.00 m" warning; the A&R pulley note only when the wire is shown.
- [ ] Rollers the cable has left (after a hang-off) stand still.
- [ ] One bow direction used by wind, wake and the rest; the demo's "wind from the bow" blows from +x, the Vessel
      deck surroundings unchanged; old projects open looking the same (test).
- [ ] Demo: 0 clash rows (`test_demo_clash.py`), Make demo time and per-frame cost before/after in the report (no more
      than +1 ms per frame).
- [ ] The new settle ability: tooltip, guide paragraph + anchor, function-list entry (`core/functions.py`), tour stop
      or an extended existing one, PC-check line (CLAUDE.md section 6).
- [ ] Tests added; full GitHub run green; report filled in, with a short owner's check list (shots 10–12 on the RTX
      3090).

## Not in this task

The CPS run from the rack (task 0126, after this one). 0081's touch-down drifting with the deck path length (owner
may prefer re-anchoring – leave as is). Glowing markers, sun rays, sediment specks. The site, the turbine, the
assembly sequence.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
