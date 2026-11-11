# 0086 – Cutaway / section view (study 0069 #1)

**Who:** worker · **Status:** running · **Branch:** `claude/serene-noether-vmu9y5`
**Started by:** lead chat, 11 Nov 2026 (lead's pick from the improvement study; the owner can change it)
**Lane:** new **Cutaway lane** – new files `blender/section.py`, `blender/ops_section.py`, `blender/ui_section.py` (a
sub-panel of 3 Looks in its own file), `core/section.py` if useful (no Blender); the material hook next to the Fade
group (`blender/fade.py`, `blender/materials.py` `build_nodes` re-wrap – Looks lane is free); additive only:
`blender/props.py`, `blender/reimport.py` (carry cuts over), `blender/joints.py` only if the app-made cut joint needs a
hook (see 3); tests, tour stop, PC-check line, guide
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation"

Runs at the same time as **0085** (vessel motion: `vessel_motion*.py`, the sea), **0087** (camera rides / flies:
`cameras.py`, the camera part of `animation.py`, `ui_motion.py` camera settings) and, from Thursday 08:00, **0058**
(Flex parts: `flex*.py`, hooks in `handlers.py`, `animation.py`, `reimport.py`) and **0061** (Machining: tool marks on
cut faces). **Do not edit `animation.py`, `ui_motion.py` or any machining, coolant, chips, air, G-code or toolchange
file.** Several releasing tasks at once: take the version number last; whoever finishes later merges `main` once and
renumbers (CLAUDE.md section 2).

## Goal

Show the inside of a machine in one click: a cutting plane (or box) through chosen subassemblies, the cut faces filled
with a cap colour, and the cut can move in an animation ("the housing opens up"). For a winch gearbox, a tensioner, a
spindle – and the cut-away hull of the cable-lay demo video (0083 shot list, shots 9 and 10).

## Read first

`tasks/0069-improvement-study.md` row 1; `tasks/0073-fade-xray-trail.md` report (how the Fade group wraps every material
of a part and reads *object* attributes, so shared materials stay per part); `blender/surroundings.py` `_cutaway`
(the halls' cut-away, a shader trick that already works).

## What to build

1. **3 Looks > Cutaway:** *Add cut* → pick what it cuts (groups, subassemblies, or the whole model), shape **Plane**
   (Flip) or **Box** (a corner cut away / a quarter cut), place it by moving its handle in the view or by numbers,
   **cap colour** (default a strong red, editable; optional hatch lines), on/off per cut, several cuts per project,
   kept with the project, in saved scenes and through a model update. Header state ("2 cuts · 1 on").
2. **The way it renders – the shader way first:** a node group in every material of the cut parts (composed with the
   Fade group: a part can be cut *and* fade), switched per object by an object attribute, cutting by the position in
   the cut object's space (Texture Coordinate > Object); the inside seen through the hole (back faces) drawn in the cap
   colour and lit as if it faced out of the cut. Fast with thousands of parts, Cycles and EEVEE alike, scripts off,
   the render queue. Light passes through the hole as it would through a real cut. Decals, painted faces, glass,
   X-ray and the milled cut-face look keep working; a material rebuilt by a look change is wrapped again (the 0073
   way) – for materials the machining files make, do it generically without editing those files, and report anything
   not covered. Known limit: caps are right only for closed solids – say how many parts of the test models and the
   0076 demo hull are open shells, and how they look. An exact boolean cut only if the shader way fails in a case that
   matters (measure and say).
3. **Moving the cut:** prefer making the cut's place an **app-made slide joint** (as the double arm's joints, 0064, and
   0075's virtual "cable" joint), so the existing *Move joint* step, poses and the queue move it – no new step kind and no
   change in `animation.py`. If that cannot work, stop and write in the report what is needed (the lead plans the step
   after 0058 and 0087 are merged).
4. The clash check ignores cuts (geometry is unchanged); labels and the sharp spot keep their parts.
5. Every button a tooltip; guide section in chapter 3; PC-check line `looks.cutaway` (a picture of a cut model + the
   render time); tour stop "Cutaway" on a test model with something inside (your pick, say which); `CHANGELOG.md`.

## Done when

- [ ] Tests: a closed box cut in half renders the remaining half and the cap colour in the right pixels (small Cycles
      and EEVEE renders); Flip; Box cut; a part of the same material not in the cut renders as before; cut + fade
      together; the cut moved by a Move joint step lands at the right place at sampled frames; scripts off; queue-runner
      frame = view frame; save/reopen; model update keeps the cut's parts; an old project renders as before.
- [ ] Render time per frame with a cut vs without (Cycles Draft, a test model; and the PC check Heavy model scaled
      down) in the report – a cut must not make every frame much slower.
- [ ] The all-tour clash test still 0 rows; tour stop, PC-check line, guide, tooltips strict; GitHub green incl.
      Windows; merged to `main` with the next free version, released.
- [ ] Report filled in; `TASKS.md`: 0086 done.

## Not in this task

A new animation step kind (see 3), cut-away of the sea / underwater views (0081), section lines on technical
drawings, measuring tools.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
