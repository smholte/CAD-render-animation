# 0085 – Vessel motion at sea (study 0069 #4)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0085-vessel-motion` (or the session's own branch)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
