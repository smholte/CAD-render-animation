# 0229 – Stand-in tests on public models for what only the demo vessel's equipment proves today

**Who:** worker · **Status:** done (0.2.177) · **Branch:** `claude/loving-babbage-gn6leq` (the web session's branch)
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

## Owner's correction (20 Nov 17:02)

The ship with its deck crane and the wind park **stay public** (the public demo "Vessel in a wind park" keeps vessel
at work, vessel motion, the park and a re-bake). Only the equipment goes private – **the list below is the whole job**;
an earlier note that added items 11–13 is withdrawn.

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

## Design (worker, 20 Nov – the split over subagents)

Each stand-in is a **new test file** (one owner per file); nothing reads `demo_model/`, `blender/demo*.py` or the demo
tests. App code only for a fault a stand-in finds, and then only after the worker agrees (it stays with the worker).

| Who | Items | Files it owns |
| --- | --- | --- |
| worker | 3 tracks on a hinge + cylinder; 7 (already public: `test_paths_core.py::test_centreline_of_a_300_m_cable`, a made-up 300 m tube read in pieces – no new test) | `tools/make_test_tracks.py`, both `test_tracks.step`, `tests/test_tracks*.py`, `blender/tracks.py` set-up, `tour.py`, `tour_versions` |
| subagent A (spool) | 1 carousel odd full layers + partly paid-out top layer leaving at its innermost turn; 2 Lebus drum, climbs 7–8 mm of payout apart, drum within 0.1° after Build (`joints.table_keys`) | `tests/test_spool_standins.py` |
| subagent B (motion / sea / update) | 4 `test_moving` block lowered on a wire past a part made in the test, clash check 0 rows; 5 the 38 kg/m catenary tension + Lay data label on `test_sea`; 6 a wrap set by hand on a sheave on a moving part (`test_swivel`'s davit or `test_paths_a`), update with the same file, wrap kept | `tests/test_moving_lowering.py`, `tests/test_sea_realism.py`, `tests/test_paths_wrap_moving.py` |
| subagent C (size) | 8 a made-up 400-joint scene in one `joints._batch` (time, one update in / one out, every joint where it should be); 9 a made-up rim of 200 rollers turning on a plain deck, the clash check's result (0 rows, rollers held still) and time | `tests/test_joint_batch_size.py`, `tests/test_clash_rim.py` |

Test times: each new file aims at < 2 min on the 4-core web machine (they join a pytest group by themselves).

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

**Chat / date:** Claude Code on the web, branch `claude/loving-babbage-gn6leq` (the session's branch), 20 Nov 2026.
Items 11–13 of the owner's 16:55 note were withdrawn by the 17:02 correction; the rotors of item 13 were already in
item 9's file and stay (they cost ~5 s).

**What changed – one stand-in per row of study 0226 section 2:**

| Row | Stand-in | File |
| --- | --- | --- |
| Carousel spooling | core: odd/even full layers + 60 % top layer, leave radius moves outwards when paid out from the innermost turn (and the converse), one diameter per turn, the climb's quarter turn | `tests/test_spool_standins.py` |
| Lebus drum with climbs | test_spool's drum as Lebus, first layer r 0.180 m: climb pieces 7.0–8.5 mm, `table_keys` k = 1000, no key lost after `fc.update()`; Build through two climbs: worst 0.0009° (limit 0.1°); a control that Blender merges 7.7 mm keys (20 → 10) | same |
| Tensioner tracks (lift + tilt) | `make_test_tracks.py`: TILT FOUNDATION, TILT PIN, TILT CYLINDER BARREL / ROD (made up); the set-up's joint "Tensioner tilt" driven by "Tilt cylinder", the cable's ends on the BASE FRAME; animation tilts 6° and back. Test: track parts, rollers and cable follow as one body to 0.02 mm, links on their loops while tilted, running and lifted, the cylinder's length right to 0.1 mm. `test_tracks_core.py` now on the model's own pins (no demo numbers) | `tests/test_tracks.py`, `tests/test_tracks_core.py` |
| Cable over rollers, long cable | already public: `test_paths_core.py::test_centreline_of_a_300_m_cable` (a made-up 300 m tube read in pieces) – no new test | – |
| Chute / sea, 38 kg/m, Lay data | on `test_sea`: own catenary vs the app to 1e-4 (bottom 5.18 kN, top 11.54 kN, 63.4°), 19 kg/m halves them, the drawn line within 5 cm; the Lay data label: every row = the cable's numbers, inside 1920×1080 and 3840×2160 | `tests/test_sea_realism.py` |
| Load lowered past a part | on `test_moving` (built once): a guide slot made in the test, 3 cm clear: 0 rows; moved 5 cm into the way: only slot rows, 1.5–3 cm deep | `tests/test_moving_lowering.py` |
| Wrap by hand through an update | on `test_swivel`: wrap set by hand on the sheave under Swivel → Slew, same-file update: kept; also slewed +30° / -40° first (sheave > 1 m from its CAD place): wrap, slew and place kept | `tests/test_paths_wrap_moving.py` |
| Joints in a batch | 400 parts, 400 joints (100 stacked) in one `_batch`: 0.6 s, 2 scene updates (0 inside), 18 sampled parts where the maths puts them | `tests/test_joint_batch_size.py` |
| Clash at size | 200 rollers + shafts on a deck: 0 rows, 400 held, 4.3 s; + 3 rotors 40 m and 2 propellers: blades not held, 0 rows; controls: a block 5 mm into the rollers (19 rows) and a blade tip through a post (3 rows) found | `tests/test_clash_rim.py` |
| Vessel motion, re-bake, ROV | stay public (owner's correction) / none needed (study) | – |

No stand-in reads `demo_model/`, `blender/demo*.py` or the demo tests (`make_test_tracks.py` still uses the shared
shape helpers `demo_model/geom.py`, as before).

**Faults found:**
- **Tracks animation (pre-existing since 0079/0122):** its second lift step started "from 0" (`use_from` off), so the
  top track jumped 150 mm down in ONE frame at 4 s. Found by the tilt step doing the same (a 0.7 mm clash row at frames
  150–151). Fixed: every step of the test model's animation starts from where its joint is (`tracks.set_up_test_model`).
- **Clash check, not fixed (design):** parts that stand still against each other are one body and never checked: a
  roller modelled 5 mm into a fixed deck, or a post through a held roller, gives no row (subagent C). For the lead.
- The cable read from the CAD bar had both ends on the model root (they touch nothing), so it did not tilt with the
  frame; the set-up puts them on the BASE FRAME (`paths.set_end`), as a user would.

**Tested and measured** (4-core web machine): the new files 21 tests in 91 s (lowering 56 s of it); `test_tracks*`
70 tests; tour stop `tracks` Go + check; `test_tour_clash.py[tracks]` 0 rows (13 s). The maker writes the model in
14 s (184 parts, 661 KB; tilted 10°: 5 mm clear, rod 213 mm in its barrel). GitHub: 3 full runs – 44772003370 green (as 0.2.176); 0231 took 0.2.176 meanwhile, so merge + renumber to 0.2.177: 44776685998, its Windows A job failed once in the app-icon code ("Smart App Control off again": a rename of `Fresing Render.exe` hit file-not-found – not this task's code; `main`'s run of the same tests was green) and was green on one re-run of that job; then a docs run for the merge of 0231's report.

**Subagents:** A (spool, `test_spool_standins.py`), B (`test_moving_lowering.py`, `test_sea_realism.py`,
`test_paths_wrap_moving.py`), C sonnet (`test_joint_batch_size.py`, `test_clash_rim.py`, then the rotors), D (items
11–12) stopped at the owner's correction before writing anything. The worker did item 3 and merged; nothing re-done.

**Open points / follow-up tasks:**
- Static overlaps inside one rigid body are not reported by the clash check (above).
- Flaky on Windows (for 0242 or a follow-up): `tools/appicon_test.py` "Smart App Control off again: copy and shortcut back" – WinError 2 renaming `Fresing Render.exe` to `Fresing Render.old.exe` (run 44776685998, first attempt).
- The guide's tracks picture was not made again (the panel did not change; the model only gained the tilt parts).
