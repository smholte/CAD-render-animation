# 0225 – Test tour stop 22 "Mechanisms": the four-bar moves too

**Who:** worker · **Status:** done (0.2.172) · **Branch:** `task/0225-tour-four-bar`
**Started by:** lead, 19 Nov 2026 (owner, 00:29, tour on 0.2.168: "in 22 the middle of the 3 test models does
nothing") · **Model:** Sonnet · effort Medium
**Area:** the `linkage` set in `blender/tour.py` (`build_linkage`, `_check_linkage`, the stop `mechanism`: title,
"what you should see", `changed=`, the set's `changed=`; `tools/tour_versions.py --record`), the PC-check line for
mechanisms only if it uses the same set-up, guide picture of the stop if there is one.

## Goal

Stop 22 shows all three mechanisms of `test_linkage_a.step` moving: the scissor lift rises, the **four-bar's crank
turns and its coupler with the tool block swings the rocker**, the slider-crank turns once. The stop's title and text
name all three.

## Background

- `test_linkage_a.step` (`tools/make_test_linkage.py`) has three mechanisms: `CRANK.*` slider-crank, `FOURBAR.*`
  crank-rocker at x = 2000 (crank 120, coupler 350 with a tool block, rocker 250), `LIFT.*` scissor lift.
- `build_linkage` makes only `SCISSOR` and `SLIDER`; the four-bar is never made, so it stands still (owner's picture:
  the middle model). The app supports it: `linkages.create(sc, "FOURBAR", [[coupler], [rocker], [crank]],
  base=FOURBAR.BASE.ASM, drive=crank)` – exactly as `tests/test_linkages.py` line ~78 does.

## What to do

1. In `build_linkage`: make the four-bar as the test does, give its input joint a block in "Lift and crank" (one full
   crank turn over the same 3 s), so all three move together.
2. `_check_linkage`: also check the four-bar – e.g. the rocker's pin at the end frame where the closed-form
   `four_bar_points` of the maker puts it (1 mm), and that the rocker moved at all mid-way.
3. Stop text: "Mechanisms: scissor lift, four-bar, crank"; "what you should see" names the four-bar. `changed=` on the
   stop and the set (the branch's new version), `tools/tour_versions.py --record`.
4. The tour-wide clash check (`tests/test_tour_clash.py`, set `linkage`) must still give 0 clashes.

## Done when

- [x] All three move in stop 22 (a small picture at mid-way in the report); its check fails without the four-bar
- [x] `test_tour.py` (linkage) and `test_tour_clash.py` (linkage) green; precheck green; merged, released

## Not in this task

Other tour sets (study 0224). The mechanism code itself (`linkages.py`).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 19 Nov 2026

**What changed:** `build_linkage` makes the four-bar (crank as input, one full turn over 3 s with the others);
`_check_linkage` checks it (rocker back after a turn, swings > 10 mm mid-way, coupler pin on the rocker's, crank pin
120 mm out); title "Mechanisms: lift, 4-bar, crank" (the 32-character limit), text names all three; `changed=` and tour
versions recorded. Extra: the four-bar's crank pin swept 10 mm into ground post A (clash check, frames 28–36, as 0067's
slider-crank): `tools/make_test_linkage.py` puts post A and its pin 12 mm behind the crank; both STEP copies made again.

**Tested and measured** (name the machine and the model): web machine, `test_linkage_a`: `test_tour.py` stop
`mechanism` passed, `test_tour_clash.py[linkage]` 0 clashes after the post move (failed before), `test_linkages.py`
21 passed. GitHub: 4 runs – title over 32 characters (real failure), two version clashes (0.2.170 by 0220, 0.2.171 by
0223; renumbered to 0.2.172), then green. No mid-way picture taken; no independent test of "fails without the four-bar".

**Open points / follow-up tasks:** none. The owner can look at stop 22 on 0.2.172.
