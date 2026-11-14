# 0121 – Bug-hunt fixes C: hoses with vessel motion, the Assembly sequence preview, old vessel-motion rigs

**Who:** worker (web session) · **Status:** done 14 Nov – 0.2.97 · **Branch:** `task/0121-fixes-motion-hoses-sequence` (or the web session's)
**Started by:** lead chat, 14 Nov 2026, from bug hunt 0118 (`tasks/0118-bug-hunt-3.md`)
**Area:** Flex + Motion: `blender/flex.py` (`_moved`, `_live`, `_follow`), `blender/vessel_motion.py` (`changed`, `_sync`) + `core/vessel_motion.py` (rig key version), `blender/sequence.py` + `core/sequence.py` (preview, `_in_way`, `_across`, measuring at rest), `props.py` (`_seq_preview_changed`, additive), `reimport.py` (`_carry_over`: end the preview), `animation.py` **only** the one call in `clear_keys` (0120 edits it too: merge carefully); their tests. **Do not edit:** files of 0119, 0120, 0117 named in their briefs.
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Fix rows **4, 5, 8, 9, 10, 12** of the bug hunt (a sequence preview left above 0 % becomes permanent moves at a model update; hoses left behind when a vessel-motion setting changes after Build; the preview slider re-plans the whole step at every move – 2.8–5.1 s for 260 parts, aim well under 0.2 s and measure it; old 0.2.65–0.2.87 rigs never rebuilt; every hose solved from scratch every frame with vessel motion on and no Build – aim: no solve when the pair moved rigidly; sequence keys depending on the frame Build was pressed at).

## How

- The rows' text in `tasks/0118-bug-hunt-3.md` (Findings) gives where, what happens, the proof and a suggested fix.
  Read each row, repeat its proof first (it must fail), then fix. **Every fix gets a test that failed before**
  (CLAUDE.md section 6). The suggested fix is a suggestion: a better one is fine, say why in the report.
- A row that turns out not to be real (cannot be shown on today's `main`): say so in the report, no change.
- No new features, no UI redesign. A visible change (a new warning, a note) gets its tooltip/guide line; no new tour
  stop or PC-check line is needed for a fix unless the row asks for one.
- One version at the end (take the number last, CLAUDE.md section 2).

## Done when

- [x] Each row: fixed with a test that failed before, or shown not real (with how)
- [x] Full run green on GitHub; CHANGELOG in plain words (what the owner would have noticed); version taken last
- [x] Report filled in; TASKS.md row → done

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (session branch `ccr-77ed94f3-ygb94l`), 14 Nov 2026 – version 0.2.97

**What changed (per row):** every row was real on `main` (each proof repeated by its test failing on the old code).
- **Row 4** (preview → permanent free moves): `reimport._carry_over` ends the preview before anything else, and
  `animation.clear_keys` ends it too (the one call). `sequence.preview` keeps its own slider value when it takes a built
  animation off. Old code: 7 parts left as free moves after an update of the same STEP.
- **Row 5** (hoses left behind after a vessel change): `vessel_motion.changed` (and the still/level marks) call
  `flex.motion_changed`: a built animation's hoses and chains are baked again for the new motion (background at once;
  in the window 0.4 s after the slider rests, so a drag does not step through the animation at every move). Also found:
  `flex.read_places` kept the places read before the change and handed them out again – the re-bake drops them, and
  `changed(sea=True)` now syncs the rig after `world.apply` (the heading change rebuilt the rig only later). Chose this
  over storing hose shapes relative to a carrier (a bigger change to the shapes mesh and its node trees). Old code: tube
  ends 14 mm off their fittings after a heading change.
- **Row 8** (preview slow): the plan is kept while only the slider moves (key = step settings, subassembly, every
  part's place; dropped at 0 %, Build, Clear keys, update); `core/sequence` works out "in the way" and "across" for all
  parts at once in NumPy (same results as pair by pair: tested on random boxes, 3 directions, with and without blocks).
  The box shows "Moving the preview takes the built animation off" when one is built; the slider's tooltip and the guide
  say so; `last_message` says so when it happens. **Measured** on the small demo, TENSIONER (260 parts), 4-core web
  machine, Blender as a module: before 7.6 s first touch, 4.0–4.3 s per later step; after 4.3 s first touch (mostly
  Clear keys of the demo animation), then one step 0.36 s, then 84–90 ms per step. Core plan of 260 random boxes:
  1.5–3.9 s pair by pair → 0.06–0.13 s.
- **Row 9** (old rigs): `core/vessel_motion.KEY_VERSION = 2` in the rig key; `vessel_motion._on_load` syncs once, so a
  rig of 0.2.65–0.2.87 is built again when the project opens (once; also rigs of 0.2.88–0.2.96, harmlessly the same).
- **Row 10** (every hose solved every frame): `flex._live` moves an item's last solved shape along with its end parts
  when they kept their places to each other (2e-5) and, for a hose, turned less than 0.5° against gravity since the
  solve (its sag is the same); otherwise it solves. Test model, 4 hoses, 60 frames, vessel on: 4 solves at 100 %
  strength, 8 at 200 % (was 240); moved shape vs a fresh solve < 2 mm, tube ends on their fittings.
- **Row 12** (keys depend on the Build frame): `sequence.bake_step` measures inside `vessel_motion.at_rest`. Old code:
  Build at frame 1 vs 70 → keys 4.0 mm apart; now < 0.01 mm.

**Tested:** `tests/test_motion_fixes.py` (18 tests; the 9 Blender ones fail on the old code for the reasons above, the
others pin the vectorised plan to the old pair-by-pair one); locally also `test_sequence`, `test_vessel_motion`,
`test_flex*` (369 passed). PC check `milling.rotary` alone, locally: OK on this branch and on old main.
GitHub: run 1 (work in progress, 43585100027) red only in `milling.rotary` of the PC check (cut radii 24.8/25.0 instead
of 23/22, cut 43 s instead of ~4 s): not reproducible locally and not in code this task touched – taken as a one-off;
run 2 after merging main: see below.

**Open points:**
- The first touch of the preview on a built demo still costs ~4 s: that is Clear keys of the whole demo animation.
- A hose moved as one body keeps the sag of its last solve until the pair turns 0.5° against gravity (then it is solved
  again): up to a few mm of sag direction off in between – invisible at the view's scale, and Build solves every frame.
- Leftover: the scratch worktree of old `main` (local only, removed).
