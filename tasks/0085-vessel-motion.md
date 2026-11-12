# 0085 – Vessel motion at sea (study 0069 #4)

**Who:** worker · **Status:** running · **Branch:** `claude/kind-lovelace-yk40cq`
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study; the owner can change it)
**Lane:** new **Sea lane** – new files `core/vessel_motion.py` (no Blender), `blender/vessel_motion.py`,
`blender/ops_vessel_motion.py`, `blender/ui_vessel_motion.py` (a sub-panel of 5 Scene & Render in its own file); additive
only: `blender/props.py` (new property group), `blender/reimport.py` (carry the setting over), `blender/surroundings.py`
(read the sea's wave list; a new swell only when vessel motion is on, see 1); tests, tour stop, PC-check line, guide
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0086** (cutaway: `section*.py`, `materials.py`, `fade.py`), **0087** (camera rides / flies:
`cameras.py`, the camera part of `animation.py`, `ops_scene.py`, camera settings in `ui.py` / `ui_motion.py`) and,
from Thursday 08:00, **0058** (Flex parts: `flex*.py`, hooks in `handlers.py`, `animation.py`, `reimport.py`) and
**0061** (Machining). Do not touch their files beyond the additive lines named above. Several releasing tasks at once:
take the version number last; whoever finishes later merges `main` once and renumbers (CLAUDE.md section 2).

## Goal

The machine really works on a moving ship: the deck and everything on it heave, pitch and roll gently with the sea,
while the sea, the sky and the camera stay put. It is shot 1 of the cable-lay demo video (0083 shot list: "the vessel
on a calm sea, gentle roll") and the base for 0081 (cable into the sea) and the demo project 0077.

## Read first

`tasks/0083-cable-lay-reference-study.md` section **"9. Vessel motion"** (numbers for the video) and
`tasks/0069-improvement-study.md` row 4. `blender/surroundings.py` "the sea" (`SEA`, `_waves`, `_time_driver`,
`_waves_group`): the visible sea is a sum of travelling sine waves.

## What to build

1. **The motion** (`core/vessel_motion.py`, no Blender): heave, pitch and roll over time from a sea state, the
   vessel's length and beam (read from the model's box, editable) and its heading to the waves (Head / Bow quarter /
   Beam / Stern quarter / Following). Long waves move the ship, short ones do not (a 124 m vessel ignores 13 m
   ripples); roll has its own natural period (default 11 s) so it dominates in beam seas. **Calm** gives 0083's numbers:
   roll ±1–1.5° at 10–12 s, pitch ±0.3–0.6° at 6–8 s, heave ±0.2–0.4 m at 7–9 s, mixed and non-repeating, the stern
   moving the most; **Rough** clearly more (say what you chose and why). A **Strength** slider 0–200 %.
   The ship should rise when a crest of the visible sea passes under it: build it from the same wave components and
   phases as the sea. If the sea's own wavelengths (13–55 m at Calm) cannot give those periods, add a long, low swell to
   the sea **only when vessel motion is on** – a project without vessel motion must render exactly as before.
2. **What moves:** every model root, the *Vessel deck* surroundings and props, about a pivot (default: at the
   waterline under the model's middle; or a clicked point). The sea, sky, halls and the Animation camera stay in the
   world (a drone's view; riding on board comes with 0087, see 5). Joints, cylinders, mechanisms, decals, labels,
   way covers, fades and trails keep working on top of it. Must work with **scripts off** and in the render queue:
   simple-expression drivers on the frame (as the sea's waves) or keys over the whole animation – your choice, say why.
   Mind the small-value driver bug (CLAUDE.md section 8, `joints.BIAS`).
3. **Stays still (if it fits, else a follow-up):** pick subassemblies that keep their place in the world – "Still"
   (all motion taken out) or "Level" (roll and pitch taken out, heave kept) – the classic motion-compensated gangway or
   hook shot. Say in the report how it combines with joints on those parts.
4. **Panel:** 5 Scene & Render > **Vessel motion** (shown for Open sea and Vessel deck; a note for other surroundings):
   On, Sea state (follows the surroundings), Strength, Heading, Vessel length / beam, Roll period, Pivot (Auto / Pick),
   header state ("Off" / "Calm · roll ±1.2°"). Plays in the view with the timeline. Kept with the project, through Save,
   model update and saved scenes.
5. **Camera on board:** not in this task. 0087 (running now) adds "Ride along a part"; whoever of the two merges
   second makes the vessel a ride target and tests it.
6. Every button a tooltip; guide section in chapter 5; PC-check line `scene.vessel_motion` (a picture + the measured
   amplitudes); tour stop "Vessel motion" (a test model on the Vessel deck, Calm, beam sea); `CHANGELOG.md`.

## Done when

- [ ] Tests: amplitudes and periods measured from the evaluated result over 120 s match the chosen table (report it);
      every part moves with its root (world positions vs the root's motion < 0.01 mm at sampled frames); the sea and
      the camera do not move; Strength 0 % = no motion; scripts off (control-driver proof as in
      `tools/coupling_check_noscripts.py`); queue-runner frames = view frames; save/reopen; model update keeps it;
      an old project and a project with vessel motion off render as before (sea mesh and materials unchanged).
- [ ] Render time per frame with vessel motion on vs off (Cycles Draft, test crane on Vessel deck) and per-frame
      evaluation time on the PC check Heavy model, in the report.
- [ ] The all-tour clash test still 0 rows; tour stop, PC-check line, guide, tooltips strict; GitHub green incl.
      Windows; merged to `main` with the next free version, released.
- [ ] Report filled in; `TASKS.md`: 0085 done.

## Not in this task

Cable catenary into the sea (0081), the camera riding the vessel (0087), motion blur (study #6), real hydrodynamics
(RAOs from a hull form), yaw/surge/sway, spray and wakes.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web (session branch `claude/kind-lovelace-yk40cq`), 11 Nov 2026 · version 0.2.64

**What changed:**
- `core/vessel_motion.py` (no Blender): each wave of the sea (a, direction, k, phase) → heave = its height averaged
  over the hull rectangle (sinc along × sinc across), pitch / roll = slope of the best-fitting plane along / across.
  Heave follows the sea directly (rises with the crest); pitch is a damped oscillator (6.5 s, ζ 0.25); roll a lightly
  damped one at the **roll period** (default 11 s, ζ 0.03), so roll dominates near its own period. The sea's own
  waves (13–55 m, 3–6 s) cannot give 7–12 s motion, so with vessel motion on the sea gets a **long, low swell** of
  eight waves (6.3–14.5 s, spread up to ±70° round the heading; mix tuned by a search so the table holds for a 64 m
  and a 124 m hull). **Each channel is scaled so the vessel at the reference heading (Bow quarter) has the sea state's
  numbers** (peak over 10 min), for any vessel size; the heading then shares it out (beam rolls more, head pitches
  more). Why scaled: a physical size effect alone made the 64 m Vessel deck pitch ~6× more than a 124 m vessel at
  "Calm" – outside 0083's numbers. Consequence: a small vessel does not move more by itself (use Strength).
- **The table** (peak over every 120 s stretch of the first 10 min, mean period by zero up-crossings), Bow quarter:
  Calm roll 1.0–1.5° at 10–12 s, pitch 0.3–0.6° at 6–8 s, heave 0.2–0.4 m at 7–9 s (= 0083). **Rough** (my
  choice): roll 3.0–4.2°, pitch 1.0–1.6°, heave 0.8–1.3 m, same periods – about three times Calm, a sea near the
  working limit of a motion-compensated vessel (Hs ~3.5 m, 0083 section 9); its numbers stay below the roll at
  which pipelay/cable work stops in a beam sea being shown as "normal". Calm beam sea: roll ±1.4–1.8° (≤ 2°, the old
  pipelay limit); head/following: roll ±0.3–0.5°.
- `blender/vessel_motion.py`: rig "FR Vessel" (on the pivot: heave in z, roll x, pitch y) + child "FR Vessel pivot"
  (−pivot): its world matrix = T(p+h)·Ry(pitch)·Rx(roll)·T(−p). **Each channel = a driver whose simple expression
  gives the time in seconds (`frame * b / f + 10`, fps and fps_base as variables, like the sea) + built-in
  sine modifiers (one per wave) + a Generator for the constant.** Why not one expression: a driver expression holds
  255 characters (30 sines don't fit). Why not keys: they would have to be baked again whenever the animation's
  length or frame rate changes. This way: no Python (scripts off), the queue copy evaluates the same file, any fps,
  in step with the sea's own scene time. The +10 s keeps the driver result away from small numbers (CLAUDE.md
  section 8); the modifiers' result itself is no driver result (checked: 5e-5 stays 5e-5).
- What moves: model roots, the Vessel deck's objects (not the sea) and props get a **Child Of "FR vessel motion"**
  on the pivot empty (identity inverse; **`set_inverse_pending` switched off** – Blender sets it on a new Child Of
  and pinned the model where it was at the first update; found by the tests, now in CLAUDE.md section 8). Joints,
  cylinders, mechanisms, decals, labels, way covers, fades and trails hang on the parts and keep working. Sea, sky,
  halls, cameras: nothing.
- **Stays still (done in this task):** "Still" = Child Of on an inverse rig (V⁻¹), "Level" = T(heave)·V⁻¹. The
  constraint goes on the top of each marked subassembly *in Blender's own tree* (a part a joint from outside moves
  hangs under that joint's empty and gets its own; nested marks: the outer wins). **With joints:** the marked parts
  behave as on a still vessel – a joint whose base is outside the mark still moves them, relative to where its base
  would be on a still sea (test: a still boom still turns 20° with its joint and ends where it would at rest). Marks
  are kept by part ID (model update remaps them; a part gone → a note). A depsgraph check (only while marks exist:
  model count, props, joints and their member counts) re-applies the constraints when joints change.
- `at_rest(scene)`: mutes the constraints while the surroundings measure the model (`_build`, `_note_misfit`) and
  while a model update rebuilds joints from world places (`reimport.update_model`), so a frame mid-roll never ends up
  in the model. Additive lines only in `surroundings.py` (swell key, `_waves(state, swell)`, the swell lifts the sea
  but makes no foam, hooks), `reimport.py`, `props.py` (`FRVessel`, `FRVesselStill`, `scene.fresing.vessel`).
- Panel 5 Scene & Render > **Vessel motion** (after Props for scale; `ui_vessel_motion.py`, `ops_vessel_motion.py`):
  Move with the sea, Sea (the same setting as the surroundings), Waves from, Strength, the line of measured numbers,
  folds Vessel (Size from the model / Length / Beam, Roll period, Turns about Auto / Picked point + pipette) and
  Stays still (Still / Level for the selection, list, ×). Header "Off" / "Calm · roll ±1.5°". Other surroundings: a
  note. Pivot Auto: Vessel deck = the hull's middle at the waterline (the crane stands aft, so it moves more than the
  middle: "the stern moves the most"); Open sea = under the model's middle (the model is the vessel). A clicked
  point on the moving deck is taken back to its place on a still sea.
- Kept: Save, model update, saved scenes (applying one rebuilds the surroundings, the deck follows again). It is one
  project setting, **not stored per saved scene** (`states.py` is not this lane's file) – a follow-up if the owner
  wants scene A with and scene B without.
- Tour stop "Vessel motion at sea" (new set `vessel`: the crane on the Vessel deck, Calm, beam sea, boom + trolley
  joints, 8 s animation); PC-check lines `scene.vessel_motion` (Full: picture + roll/pitch/heave measured over 2 min)
  and `heavy.vessel` (Heavy: ms per frame off/on); real-app test `tools/ui_test_vessel.py` (group scenes; scripts off
  with `blender -Y` via `tools/vessel_check_noscripts.py`); tooltip check reads the new panel; guide section in
  chapter 5 + picture; CHANGELOG 0.2.64.

**Tested and measured** (Claude Code web session, 4 cores, no graphics card; test crane `test_crane_a.step`):
- `tests/test_vessel_motion.py`, 29 tests: the table for Calm and Rough at 124×28 m and 64×18.3 m (every 120 s
  stretch of 10 min), headings, long/short waves, crest → rise (correlation > 0.9 on the 64 m deck, every heading),
  roll period 8/11/14 s followed within 12 %, Strength 0/1/2, never repeats; in Blender: the rig = the maths
  (< 2e-5) and every part = rig × its rest place (< 0.01 mm) at frames 1–2999; **measured from the evaluated scene
  over 120 s (Vessel deck, Calm, Bow quarter): roll ±1.23° every 10.7 s, pitch ±0.47° every 7.1 s, heave ±0.26 m
  every 8.3 s**; sea and camera do not move; Strength 0 % = no motion; off / never on = the same sea mesh (vertex for
  vertex), material and modifiers, no rig, no constraints; Factory hall / Open sea switching; save/reopen + saved
  scene; props; Still / Level / a joint on a still part / remove; model update A → B mid-roll (root follows, mark
  remapped, root's rest place unchanged); pivot Auto / Pick / back to rest; 25 vs 50 fps = the same moment; **the
  queue's background copy** (opens the saved file, builds the animation again) shows the same frames (1e-6).
- Real-app test 15/15 (18 s): header, the crane moves 104 mm between frames 1 and 90, sea + camera stay, deck
  follows, beam 1.55° vs head 0.35°, pick, still / remove, **scripts off (`blender -Y`): identical positions (worst
  0.0), the Python control driver refused**, reopen.
- `tests/test_tour.py` (Go + check of the new stop) and the all-tour clash test: 0 rows (my set first had the boom
  turning through the trolley – the trolley now rides on the boom, as in the hub set).
- PC check `scene.vessel_motion`: roll ±1.6° every 11 s, pitch ±0.44°, heave ±0.26 m (Calm beam sea), rendered in
  2.4 s.
- **Render time** (Cycles Draft, processor, 640×360, crane on the Vessel deck Detailed, beam sea, 3 frames × 2):
  **2.27 s per frame off, 2.25 s on** – no difference.
- **Per frame on the PC-check Heavy model** (2,992 parts, Open sea, 240 frames, bpy module): **4.5 ms off,
  10.4 ms on (+6 ms)** – every part's place changes each frame.
- Locally also: test_surroundings, test_model_update, test_panels, test_pccheck, test_user_guide, test_ci_tools,
  test_tour (266 tests); tooltip check strict 572/572.
- GitHub: RUNS

**Open points / follow-up tasks:**
- **0087 (camera rides along) – done here:** 0087 merged first (0.2.62), so this task made the vessel a ride target:
  a Ride along step on the model root (or any part on deck) rides the vessel – no new code needed, the root carries
  the motion. Test `test_camera_rides_on_the_vessel`: camera = root × seat at every frame (< 0.01 mm, < 0.01°), it
  rolls with the vessel; Keep level keeps the camera upright within 0.01° while it rides. A hint in the panel and the
  guide. A riding camera is baked at Build: after changing the sea or heading, Build again (said in the guide).
- Vessel motion is one project setting, not per saved scene (would need `states.WORLD_KEYS` + the vessel keys).
- The swell is only seen with Detail "Detailed" (as all geometric waves) and fades out 40–64 m from the machine like
  the sea's own waves; a 124 m hull reaches past that.
- A small vessel moves as much as a big one at the same sea state (scaled to the table); Strength adjusts it.
- Not checked on the owner's PC: playback speed in the view with the RTX 3090 and a real offshore model (PC check
  Heavy line `heavy.vessel` measures it there).
