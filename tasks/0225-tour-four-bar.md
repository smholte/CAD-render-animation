# 0225 – Test tour stop 22 "Mechanisms": the four-bar moves too

**Who:** worker · **Status:** open – can start · **Branch:** `task/0225-tour-four-bar`
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

- [ ] All three move in stop 22 (a small picture at mid-way in the report); its check fails without the four-bar
- [ ] `test_tour.py` (linkage) and `test_tour_clash.py` (linkage) green; precheck green; merged, released

## Not in this task

Other tour sets (study 0224). The mechanism code itself (`linkages.py`).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
