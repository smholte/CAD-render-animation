# 0073 – Fade step, X-ray look and trail line (study 0069 #2 and #13)

**Who:** worker · **Status:** done (0.2.59, 11 Nov)
(0058 starts in `animation.py` then) · **Branch:** own
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study – the owner can change it afterwards)
**Lane:** Motion + Looks – `blender/animation.py` (the new step kind, next to SHOW/HIDE), `ops_motion.py`,
`ui_motion.py`, `props.py` (additive); the X-ray look in `blender/materials.py` / 3 Looks panel; a new
`blender/trails.py` (+ its UI in 6 Animation); tests, tour stop, PC-check line, guide
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0072** (clash files, `decals.py`, crane/cylinder test models). Do not touch those, nor the
machining, G-code, queue or update files. Two releasing tasks at once: take the version number last; whoever finishes
second merges `main` once and renumbers. **If it cannot be green and merged by Wednesday 23:00:** push the branch,
report, stop.

## Goal

The most common shot in machine videos: the housing **fades** away to show the mechanism working inside, then comes
back. Today Show/Hide steps are instant. Add a fade, a see-through "X-ray" look, and a line that draws the path a
point of the machine takes (hook, tool tip, carriage) – all three for stills and videos, with scripts off.

## What to build

1. **Fade step** (6 Animation, next to Show / Hide): "Fade out subassembly" / "Fade in subassembly", duration (default
   1 s), ease; down to fully hidden at the end (so a faded part costs nothing in later frames and does not cast
   shadows), optional "stop at" % (e.g. 20 % = ghost stays). Per object, not per material (materials are shared by
   groups): e.g. the object's colour alpha read by the material, or another way you choose – say why. Same look in
   Cycles and EEVEE, view = queue's video; works with milling, decals, painted faces and the cut-face look; an old
   project unchanged.
2. **X-ray look** (3 Looks, a look for a group or a picked subassembly): see-through with brighter edges (fresnel),
   one colour (default light blue), strength slider; parts behind stay visible; in the Fade step a choice "fade to
   X-ray" (the housing turns X-ray instead of vanishing).
3. **Trail line** (6 Animation > Trail lines): pick a part (+ a point on it: its origin, a clicked point, or the tool
   tip), colour, thickness, "draw as it goes" or whole path, show in renders on/off; reuse the toolpath tubes
   (`gcode._node_group`, emission sampling off as 0071 did); updates at Build; several trails per project.
4. Every button a tooltip; guide sections; PC-check line `motion.fade`; tour stop "Fade, X-ray and trail" (a cover
   fading to X-ray over a turning part, the hook/carriage trail); `CHANGELOG.md`.

## Done when

- [ ] Tests: fade timing (alpha at start/middle/end frames), hidden at the end, "stop at" %, fade to X-ray, both
      engines' materials set up, queue-runner steps on the saved copy give the same frames; trail points match the
      part's path at sampled frames (< 0.01 mm); save/reopen; scripts off; an old project unchanged.
- [ ] Render time of a fading frame vs not (Cycles, Draft) in the report – the fade must not make every frame slower.
- [ ] Tour stop, PC-check line, guide, tooltips strict; the all-tour clash test still 0 rows; GitHub green incl.
      Windows; merged to `main`, next free version, released – before Thursday 08:00.
- [ ] Report filled in; `TASKS.md`: 0073 done.

## Not in this task

Cutaway / section views (study #1, later), the assembly sequence step (#9), motion blur (#6).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 11 Nov 2026.

**What changed:**
- **Fade out / Fade in steps** (`animation.py`, new `fade.py`): per *object*, not per material. Every material of a
  faded part gets one node group "FR fade" between its shader and each output (Cycles and EEVEE outputs of glass
  too); the group reads four object attributes (`fr_fade`, `fr_xray`, `fr_xray_color`, `fr_xray_strength`) –
  custom properties of the part's object. Why: materials are shared by a group; object attributes are read by both
  engines, keyed like any custom property (no driver, scripts off), and an object without them reads 0 = unchanged,
  so other parts of the same group and old projects render exactly as before. Only materials of faded/X-ray parts
  are wrapped; a material rebuilt by a look change is wrapped again (`materials.build_nodes`). Keys go into the
  shared visibility actions (one action per timing, as Show/Hide). Stop at 0 % (not X-ray) also hides the parts
  from the last fade frame (no render cost, no shadow); Fade in at 0 % hides a shown part until the step starts.
  Decals fade with their part (own fade keys; their visibility still follows the part's drivers). Clear keys puts
  the props back (an X-ray look of 3 Looks stays). The glow does not make the material a light (`no_light`).
- **X-ray look** (3 Looks > X-ray look, `ui_fade.py`, `ops_fade.py`): X-ray the selected subassembly/part or the
  selected group; colour + strength sliders restyle every X-ray part; Back to normal / All back. Stored on the
  objects (kept in the project and the queue's copy).
- **Trail lines** (6 Animation > Trail lines, new `trails.py`): part + point (origin, clicked point, tool tip of a
  milling bit / CNC tool / `fr_tip`), animation (empty = all), colour, thickness, draw as it goes, in renders,
  several per project. Read at the end of every Build at every frame and every G-code corner
  (`clash.sample_times`, milling/coolant guard, GN objects hidden while reading), stored as an edge mesh with
  `fr_frame`; a Geometry Nodes tree per trail (Delete Geometry after the current frame when growing, Mesh to Curve,
  Curve to Mesh, Set Material) – the toolpath's way; the material is emission with `gcode.no_light`. Each trail has
  its own node tree because Blender 5.2's modifier input API (`mod[identifier]`) is gone. Shown only while its
  animation is built; hidden by Clear keys. Model update re-finds the part by uid.
- Tour stop "Fade, X-ray and trail" (Motion, after the stacked joints) (crane hub, animation "Fade and trail": boom up + trolley out, cover fades to
  X-ray, green trail of the trolley's centre); PC-check line `motion.fade` (Full). Guide: 6 Animation (step list,
  "Fade a housing away", "Trail lines"), 3 Looks > X-ray look, 3 new panel pictures. CHANGELOG.

**Tested and measured:**
- New `tests/test_fade.py` (15 tests): fade timing (linear: 0 / 0.5 / hidden at the end; smooth middle; stop at 20 %
  ghost, not hidden; fade in from the ghost; fade in of a shown part hidden before), fade to X-ray (never hidden,
  colour/strength, whole subassembly), both engines' outputs wrapped once, wrap kept after a material rebuild,
  emission sampling off, Cycles and EEVEE renders half see-through half way, save/reopen + bake again on the
  opened copy (as the queue runner) gives the same fade values and the same trail points, trail points = part path
  at sampled frames (< 0.01 mm; measured < 1e-5 m), grow/whole path, in renders, other animation hides it, several
  trails + removal, tool tip, operators, X-ray look kept after Build/Clear and save/reopen, decals go along, no drivers
  (scripts off), a project/animation without fades unchanged (no node group, no wrapped material, no props).
- Render time (Cycles, Draft, processor, 320 × 180, this 4-core machine, PC check line): fading frame 1.7 s vs the
  same frame without the fade 1.9 s (0.90 ×, i.e. within noise) – the fade does not make frames slower.
- PC check `motion.fade` locally: OK (also renders the fading frame in EEVEE). The EEVEE render test runs in a
  child process: Blender as a Python module aborts on EEVEE without a GL context (GitHub's runners), there it skips.
- GitHub runs: run 1 red – the real-app jobs could not install packages (runner network outage, apt could not
  resolve the Ubuntu mirror) and the EEVEE render test aborted pytest group 7; run 2 (EEVEE test fixed): all pytest
  groups and Windows green, real-app jobs again red on apt (re-run of the failed jobs: same); run 3: fallback to
  archive.ubuntu.com – also unresolvable; run 4: `tests.yml` now falls back to `mirrors.edge.kernel.org` when the
  install fails – all 20 jobs green (16.1 min). `main` fast-forwarded to that commit (mode reuse). 4 runs + 1 re-run,
  all extra ones from the runner outage and the EEVEE abort.
- The CI fallback mirror stays in `tests.yml` (only used when the normal install fails). Precheck and `tooltip_report.py --strict` (553 ok) pass.

**Open points / follow-up tasks:**
- The solid (grey) viewport does not show see-through parts; the guide says to look in rendered view.
- A model update keeps trails; the X-ray look lives on the part objects and is not carried to a new revision's parts
  (re-apply with one click).
- A part in a Fade step and in the X-ray look of 3 Looks: the step decides during the animation.
