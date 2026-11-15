# 0141 – Study: why the demo's Build depends on the frame shown (cause of 0131 row 6, findings only)

**Who:** worker · **Status:** done 15 Nov (findings only: no app code changed; report below, scripts on the scratch branch) ·
**Branch:** `task/0141-demo-build-frame-study` (scratch only, never merged)
**Started by:** lead chat, 15 Nov 2026 (owner: a Fable task with the usage left) · **Model:** Fable · effort High ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** reading and running `paths*.py`, `demo.py`, `demo_model/`, `animation.py`, `riders` / let go / sea end code –
**no edits on `main` except this file and `tasks/img/0141_*`**. 0126 (CPS run) and later 0137 change these files:
do not push code; scratch scripts stay outside the repository or on the scratch branch pushed with `[skip ci]`.

## Goal

Find the exact cause of 0131's row 6 and write the fix plan, so task 0138 (Opus · High, after 0137) only has to
build it.

## Background

Row 6 of `tasks/0131-bug-hunt-4.md`: on the demo, Build at frame 1 gives exactly what Make demo saved; at frame 1803
24 objects differ; at the last frame (3206) the second end and its CPS / bend restrictors lie up to 73 m off (60–70 m
aft on the seabed from shot 9 on) and Build warns "98 m more cable than the water is deep… at frame 1651". Also with
vessel motion off. **Not** on the small `test_moving` model – so something the demo's second end adds (parts excluded
until shot 9, the CPS rider, the quadrant, let go) reads the pose shown. Proof script in the row.

## What to do

1. Repeat row 6 (Make demo once – about 9 min – then Build at frames 1 / 1803 / 3206 and compare).
2. Bisect the cause: which value read at Build differs with the frame shown (joint values, rider carry places, the
   excluded-until-shot-9 parts' places, the sea end's anchor, let-go frames, cached plans). Name the function and
   line.
3. Make the **smallest test model** that repeats it (an existing tour or test model plus a few steps, or a small maker
   in a scratch script) – the test 0138 will turn into a failing test first.
4. Check whether other stages or smaller models have the same pattern (riders, sequence, spool, tracks: Build at the
   last frame vs the first on their tour sets – quick check per set).
5. Write the fix plan: what to change, where, and why it is safe (Build reads at the animation's first frame or a fixed
   start pose), and what 0137 must not undo.

## Done when

- [x] Cause named (function, line, why); smallest repeat case described with its script (in the report or on the
      scratch branch); other places with the same pattern listed.
- [x] Fix plan for 0138 written in the report; 0138's brief left as it is (the lead updates it).
- [x] Report pushed to `main` touching only `tasks/` (no run); then check that `main` really contains your commit.

## Not in this task

The fix itself (0138); the other 0131 rows (0136, 0137, 0139, 0140).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 15 Nov 2026 (Fable · High). Measured on the web session's 4-core
machine, Blender 5.2.3 as a Python module, `main` at `e36c05c` (0.2.105) and `fb41205` (0.2.106: the same files).

**What changed:** nothing in the app. This report; the scripts on the scratch branch `task/0141-demo-build-frame-study`
(folder `scratch/0141/`, pushed with `[skip ci]`, never merged).

### The cause in one paragraph

Build applies the animation's **start scene**. A saved scene stores the water level, and putting that number back –
also when it is the same number – tells every cable into the sea "the water changed": the app then works out the
cable's **touch-down again, in the pose shown at the frame shown**. With frame 1 shown that gives the same touch-down
as before. With a later frame shown it does not, because two things in "the pose shown" follow the frame even after
Build has cleared its keys: **let go** (from its let-go frame on, an end or contact is put where it was let go – a
place kept in the seabed's coordinates, while the seabed itself is back at its start) and **the clock** (vessel
motion; a seabed that moves at Weather & time's vessel speed). The new, wrong touch-down is saved and every frame is
then built from it.

### 1. Row 6 repeated (step 1)

Demo made once (full: 261 s, small form: 230 s; 3,206 frames), opened, `frame_set(f)`, `animation.bake`, compared with
what Make demo saved (`scratch/0141/row6.py`):

| Frame shown at Build | Touch-down of "Second end" (`sea_mark`) | Build's warning | Second end's shapes |
| --- | --- | --- | --- |
| 1 | 221.12 m → 221.12 m | 0.13 m more cable … at frame 1810 (as made) | same |
| 1803 | → 221.35 m (+0.23 m; "Power cable" the same +0.23 m) | 0.37 m … at frame 1810 | up to 6.5 m off |
| 3206 (last) | → **335.39 m (+114.3 m)** | **98.23 m more cable than the water is deep … at frame 1651** | other point count; its CPS 114 m along the cable |

(Small form: +0.06 m at 1803, +113.8 m and "98.01 m" at 3206.) Row 6 as bug hunt 0131 wrote it.

### 2. The cause: function and line (step 2)

The call chain, logged with a stack at every new touch-down during a Build:

```
animation.bake                animation.py:623   warnings += states.apply_shot(scene, anim.start_shot)
states.apply_shot             states.py:422      apply_settings_json(scene, shot.world)
states.apply_settings_json    states.py:334      setattr(s, k, v)       # k = "water_level" (WORLD_KEYS, states.py:267)
props._sea_water_changed      props.py:147       paths_sea.water_changed(context.scene)   # fires on every assignment
paths_sea.water_changed       paths_sea.py:806   changed(scene, scene.fresing.cables[i])  # every sea cable
paths_sea.changed             paths_sea.py:816   anchor(scene, item)
paths_sea.anchor              paths_sea.py:728   rel = paths._rel_now(item, slots)[None]          # the pose shown
                              paths_sea.py:729   parts = paths._solve_parts(scene, item, rel, slots)   # first=None
paths._apply_let_go           paths.py:1952      frames = np.full(F, int(scene.frame_current))    # the frame shown
```

`anchor` then writes `sea_start`, `sea_mark` (paths_sea.py:741–744) and the sea's cut-away box (748).

What in the pose shown follows the frame (small demo, `scratch/0141/why.py`: the same steps up to the start scene,
under four variants):

| Frame shown | as it is | vessel motion at rest | let go ignored | both |
| --- | --- | --- | --- | --- |
| 1803 | +0.062 m | −0.081 m | +0.062 m | −0.081 m |
| 3206 | **+113.806 m** | +113.903 m | −0.143 m | −0.081 m |

- **Let go: the 114 m.** The second end's start and the D's gutter are let go at frame 2616. With frame 3206 shown the
  live solve puts them where they were let go, stored in the seabed's coordinates. By then the seabed had moved 154 m
  aft with 'Cable travel'; Clear keys (the first thing Build does) has put 'Cable travel' back to 0. So the D seems to
  lie far aft on the seabed and the touch-down is set for that.
- **The clock: centimetres on the demo** (vessel motion moves the hang-off), **metres where the seabed moves by the
  clock** (the test model sails at 3 kn: 17.8 m in 11.5 s).
- "Also with vessel motion off" (0131) fits: let go needs no vessel motion. "Not on `test_moving`" fits too: that model
  was tried without a start scene, so nothing set the water level.

**One frame is left** when the touch-down is kept during a Build (tried by patching `water_changed`): frame 2552 of the
second end, 30 mm, the same at 1803 and 3206. The places read are identical to the last digit; the cause is
`paths._solve_parts`, paths.py:1561, `scale = _scale(_world(item.part))`: the cable part's scale is read from its world
matrix at the frame shown, which vessel motion turns, so it differs in the 7th digit. At frame 2552 the D hangs 9 cm
over the seabed with the cable piled under it, and that digit picks another answer of the catenary. With the scale rounded the
shapes are identical at every frame (max 0.0).

Also written in the pose shown, harmless: `sea_info` (the panel's numbers, paths_sea.py:624) and the keep-tight speed
joints, which `paths.after_clear` → `_tight_now` sets for that pose (12 joints differ by ≤ 1.4e-6 afterwards).

### 3. The smallest repeat case (step 3)

`scratch/0141/repeat.py` (25 s for all cases): the shipped `tests/data/test_moving.step`, `paths.set_up_moving_model`,
and **one line more than the model's own tests: a saved scene as the animation's start scene**
(`states.save_shot(sc, "Start"); a.start_shot = "Start"`). Build with frame 1 shown, `frame_set(frame_end)` (289),
Build again:

| Case | Touch-down moved | New warning |
| --- | --- | --- |
| A as set up (clock seabed + let go) | **21.04 m** (`sea_mark` 80.18 → 90.29) | 21.93 m more cable than the water is deep … at frame 1 |
| B let go only (seabed stands still) | 3.44 m (mark → 88.52) | 2.56 m more cable … |
| C clock seabed only (nothing let go) | 17.78 m | 8.56 m more cable … |
| D neither | 0 | – |
| E no start scene (what 0131 tried) | 0 | – |
| F no start scene, but "Go to scene" clicked at the last frame, then Build | 21.04 m | 21.93 m …; **a Build with frame 1 shown does not put it right** |

In A–C a Build with frame 1 shown puts it right again. The shipped tour set "A cable on a moving part" is case A
(it has a start scene): its Build with the last frame shown also moves the sea's cut-away (3.3 m) and the hull foam.

### 4. Other places with the same pattern (step 4)

- **Every tour set with an animation** (31 sets, 39 animations; `scratch/0141/tourset.py`): built, then Build again
  with frame 1, 80 % and the last frame shown; compared every app-made mesh (cables, hoses, tracks, spools, trail
  lines, sea), every cable setting, every joint value and every key on joints, parts and cameras. **Only "A cable on a
  moving part" differs.** Same: the sea cable with its CPS rider, spool, tracks, cables over sheaves, hoses, drag
  chains, the three Assembly sequence sets, product video, vessel motion, weather, cylinder, mechanisms, way covers,
  G-code, tool changers, rotary axes, milling, the crane's seven animations. The other 7 sets have no animation.
- **The same function reached without Build** (`scratch/0141/caseg.py`, the test model, frame 289 shown): the same
  layback typed again → touch-down 21.04 m off (built) / 18.52 m (not built); the same water level set again → the
  same. So does "Go to scene" (case F), and a queued still of a saved scene (`queue.run_job`, queue.py:974 – read, not
  run). The root is that `anchor` always works in "the pose shown".
- **The render queue** builds with `animation.bake` (queue.py:1009) at the frame the project was saved at, with no
  frame change before it (read, not run): a demo saved at a late frame gives the wrong shots 9–12 in the queued video.
- Read, no fault found: `flex.read_places`, `trails.sample`, `clash.sample_times`, the sequence and spool bakes read
  the frames they step through and put the frame back.

### 5. Fix plan for 0138 (step 5)

**Step 1 – Build shows the first frame before it reads anything.** At the top of `animation.bake` (before
`sequence.end_preview` / `clear_keys`): `if scene.frame_current != 1 or scene.frame_subframe: scene.frame_set(1)`.
- Tried (a wrapper round `bake`): full demo, last frame shown → the same as made (warning "0.13 m … 1810" again);
  small demo at 1803 and 3206 → the same; the tour set at 231 and 289 → the same, also the one frame of 30 mm and
  `sea_info`.
- Why it is safe: Build already ends with `scene.frame_set(1)` (animation.py:1095), so the owner sees no new jump;
  Make demo, the tour and every test already build with frame 1 shown, so this is the path that is tested; it costs
  one frame change (demo: 40–90 ms). It also covers the queue, the restore pose (animation.py:616), the joints' start
  values (643) and the live solves inside Clear keys.

**Step 2 – the touch-down is never set in "the pose shown at the frame shown"** (cases F and G, which step 1 does not
reach):
- `paths_sea.water_changed`: after `sync_bed`, leave a cable alone when neither the waterline nor its seabed height
  changed (the seabed height it was set on is `sea_start[2]`: −14.976 on the test model, −29.96 on the demo – check
  in the code that it is `bottom_z` exactly; the waterline: the seabed empty's z before `sync_bed`). A saved scene with the same water level then changes nothing. (Or more general: let
  `states.apply_settings_json` skip a value that is already there – wider reach, so more to test.)
- `paths_sea.anchor`: work the touch-down out for the **animation's first frame**: with a built animation from the
  places read at Build – `paths._rel_at(scene, item, slots, int(scene.frame_start))` (paths.py:2174) instead of
  `_rel_now`; pass `first=int(scene.frame_start)` to `_solve_parts`, so let go counts as at the first frame; not
  built: take the clock out (show the first frame for the solve and put the frame back, as `queue.py:86–94` does for
  the floor, or take `v·t` out of the seabed slot).

**Step 3 – the 7th digit** (only needed for an "identical" test without step 1): the cable part's scale in
`paths._solve_parts` (paths.py:1561; also paths.py:1528, paths_riders.py:278 and 476) rounded to 6 digits or read from
the CAD matrix as paths.py:2001 and 2901 do.

**Tests, failing first:**
1. Cases A, B, C of `repeat.py` as tests next to `tests/test_paths_moving.py`: Build with the first and the last frame
   shown → `sea_start`, `sea_mark`, shapes and warnings equal (today 21.04 / 3.44 / 17.78 m).
2. Case F ("Go to scene" at the last frame) and the same layback typed again at frame 289, built and not built → the
   touch-down stays (today 21.04 / 21.04 / 18.52 m).
3. The demo, without one more Build: in `test_save_reopen_and_build_again_gives_the_same_keys`
   (tests/test_demo_project.py:249) show the last frame before its Build and compare "Second end"'s `sea_mark` and the
   warnings too (today +113.8 m and "98 m more cable" on the small form).

**What 0137 must not undo** (it works in the same files first; its row 7 "work a built sea cable out again after a
vessel or speed change"):
- Working a sea cable out again is **not** setting its touch-down again: a new hook must not call `paths_sea.anchor`
  or `paths_sea.changed` (which does) – only solve again from the places read. `sea_start` / `sea_mark` change only
  when the owner changes a sea setting or the water.
- Whatever it hooks onto vessel / weather / sea changes also runs inside Build's start scene (`apply_shot` →
  `world.apply`, the weather settings): it must do nothing while a Build runs (`paths._STATE["busy"]` is **not** set
  during `apply_shot`), or the Build depends on the frame shown again.
- If it routes every sea change through one function, step 2's first-frame rule belongs in `anchor` itself, so every
  route gets it.
- 0126 (running, `demo.py`): the demo sets its touch-downs at Make with frame 1 shown – keep that.

**Tested and measured** (4-core web machine, Blender as a module, no graphics card): demo full and small form, Build
at frames 1 / 1803 / 3206 as made, with the touch-down kept, and with step 1 tried (56–78 s per Build); `why.py`,
`third.py` on the small form; `repeat.py` (6 cases) and `caseg.py` (6 cases) on `test_moving.step`; 31 tour sets, 39
animations. No pytest run and no GitHub run (no app code changed); 0 runs used.

**Open points / follow-up tasks:**
- For the lead: 0138's brief can name step 1 (one line) and step 2; whether step 2 also goes into 0138 or 0137 is the
  lead's call – the files are the same. Until then the owner's way round: show frame 1, then Build.
- Not row 6, seen on the way: after Clear keys at a frame past a let-go frame, the live picture of a cable whose
  seabed moves with the payout shows the let-go parts where the seabed was (the demo: 154 m aft). It is the stored
  place used with the seabed back at its start; Build replaces it.
- Leftover: the scratch branch `task/0141-demo-build-frame-study` (the owner can delete it once 0138 is done).
