# 0229 – Stand-in tests on public models for what only the demo vessel's equipment proves today

**Who:** worker · **Status:** open · **Branch:** `task/0229-stand-ins-public-models`
**Started by:** lead, 20 Nov 2026 (study 0226 package 3; owner's answers 20 Nov) · **Model:** Opus · effort Medium
**Area:** tests (`test_spool*`, `test_tracks*`, `test_moving*`, `test_sea*`, `test_paths*`, `test_swivel*`,
`test_joint_batch*`, `test_clash*`, `test_demo_project_realism.py` only to re-home its two public checks),
`tools/make_test_tracks.py` + `tests/data/test_tracks.step` + its `fresing_render/data/` copy, the tour set **`tracks`**
(`changed=` + `tools/tour_versions.py --record`). App code only for a fault a stand-in finds (small, named in the report).

## Goal

Every function the demo vessel's equipment proves today "at size and together" gets its proof on a **public** test
model or a made-up case inside a test, so the equipment can leave the public repository (package 2) without losing a
check. Nothing is taken from the spread – no copied numbers, shapes or names.

## Background

Study 0226, report section 2 (the table's last column is the list) and section 1's test rows. Today only the demo
proves: a carousel's partly paid-out top layer on an even layer (CLAUDE.md section 8), Lebus climbs whose keys are
closer than 0.02 (`joints.table_keys` leader × 1000 – **no public test**), tracks on a frame that lifts and tilts, a load
lowered on a wire between open tracks with the clash check, the 38 kg/m catenary + Lay data checks, a wrap set by hand
kept through a model update, 400+ joints in a batch, the clash check with many turning parts.

## What to do

1. **Spool:** `test_spool`'s carousel – a case with an odd number of full layers + a partly paid-out top layer leaving
   at its innermost turn (the rule of CLAUDE.md section 8 holds). A test case, not a model change.
2. **Lebus climb keys:** `test_spool`'s drum as Lebus with climbs 7–8 mm of payout apart; after Build the drum's turn
   is within 0.1° of the table. A test case.
3. **Tracks:** `make_test_tracks.py` – the tensioner frame on a hinge with a cylinder that lifts and tilts it (made-up
   sizes); a test that the tracks and the cable follow the frame. **This changes the test model:** both `.step` copies,
   the `tracks` tour set (`changed=`, re-record), its stop check if needed. `test_tracks_core.py:15-125` `demo_pins` →
   the test model's own pins (`make_test_tracks.track_pins`).
4. **Lowering past a part:** on `test_moving`, its block lowered on a wire past a part it must clear, with the clash
   check (0 rows) – the part made **inside the test** (do not change `make_test_moving.py`: task 0234 owns it).
5. **Sea realism:** move the two public checks of `test_demo_project_realism.py` (38 kg/m catenary tension, Lay data
   label) onto `test_sea` (no change to `make_test_sea.py` – 0234 owns it); keep the demo's copies until package 2.
6. **Wrap by hand through an update:** `test_swivel` or `test_paths_a` – a wrap set by hand on a sheave on a moving
   part, model update with the same file, the wrap kept.
7. **Long cable read in pieces:** a made-up 300 m tube in a test through `core/paths.centreline` (no model).
8. **Joints at 400:** `test_joint_batch` with a made-up 400-joint scene (if it has no size case).
9. **Clash at size:** a made-up rim of 200 rollers on a plain deck in a test (not a model), turning, the clash check's
   result and time; the 4-window split keeps its own test on `test_clash.step`.
10. A stand-in that **fails** shows a real fault: fix it in the app if it is small (one module, with its test), else
    leave the test marked `xfail` with the reason and name it in the report for the lead.

## Done when

- [ ] Each row of study 0226 section 2's table has its stand-in (or a line in the report why none is needed)
- [ ] No stand-in reads anything from `demo_model/`, `blender/demo*.py` or the demo tests
- [ ] `tracks` set: `changed=`, re-recorded, its stop's check and `tests/test_tour_clash.py` at 0 clashes
- [ ] Full suite green on GitHub; report filled in (which stands-in found a fault, times added to the run)

## Not in this task

The demo and its tests (they stay until package 2); `make_test_sea.py`, `make_test_moving.py`, `make_test_thrusters.py`
(0234); other tour sets; the private repository (0228).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
