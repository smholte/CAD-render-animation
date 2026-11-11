# 0073 – Fade step, X-ray look and trail line (study 0069 #2 and #13)

**Who:** worker · **Status:** open – start now (Wed 11 Nov), next to 0072; **merged before Thursday 12 Nov 08:00**
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

**Chat / date:**

**What changed:**

**Tested and measured:**

**Open points / follow-up tasks:**
