# 0100 – Assembly sequence step: take a subassembly apart (or put it together) part by part (study 0069 #9)

**Who:** worker · **Status:** running · **Branch:** `ccr-b270b448-9405yw` (the web session's branch)
**Started by:** lead chat, 13 Nov 2026 (owner's pick from study 0069: #9)
**Lane:** Motion – a new step kind in `props.py` (step list, additive) and `animation.py` (its bake), a new
`core/sequence.py` (no Blender: order, directions, distances, timing) and `blender/sequence.py`, its settings in
6 Animation (`ui.py`/`ui_motion.py` – the step's own box only); tour, PC check, guide. 0078 (Flex lane) adds a bake hook in
`animation.py` at the same time: keep your change additive, whoever merges second updates its branch.
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

"How it is built" videos in one step: pick a subassembly, and its parts fly out one after another (staggered) to an
exploded place – or come in from there and assemble – with optional trail lines, instead of many Show / Hide / Pose
steps set up by hand. The owner uses it for product videos ("what's inside the spindle head") and assembly instructions.

## Background

- Study 0069 #9 (Inventor Presentations auto-explode + trails, Fusion auto-explode, KeyShot exploded animation). Today:
  Go to pose (one exploded pose), Show / Hide, Fade in / out (0073), trail lines (0073); no staggered sequence.
- Parts can be joints' members, free-moved subassemblies (`joints.free_moves`) or fasteners (0030). Fasteners usually go
  first when taking apart. A part that is a joint's member moves with the joint: the step must work with the place the
  part has at that moment (the step's start), and leave every joint as it is.

## Scope

1. Step kind **Assembly sequence** (6 Animation > Add step): subassembly (pick in the tree), **Take apart** / **Put
   together**, order (**Tree order** / **Outside in** – fasteners first, then the parts nearest the outside / **Reverse**),
   direction per part (**Away from the centre** / **Along an axis** X/Y/Z of the subassembly / **Up**), distance (mm, or
   "by size"), time per part and overlap (staggering), Hide at the end (parts disappear after flying out) / Fade, trail
   lines tick (reuse 0073's).
2. Put together = the exact reverse of take apart, ending at the parts' real places (0.0 mm).
3. A preview without building (scrub the step in the view, like the other steps), and Build bakes keys like every step;
   a later Pose / Joint step still works (the parts are back where the joints expect them).
4. Rigid parts only: decals ride along; hoses (0058) of a moved part follow their end parts; flex parts themselves and
   app-made objects (tool copies, chips) are left out of the sequence (say so in the panel).
5. Tour stop "Assembly sequence" on a test model with a subassembly of ≥ 8 parts incl. fasteners; PC-check line
   `animation.sequence`; guide section with a picture.

## Done when

- [ ] Take apart and Put together on the test model: every part ends within 0.01 mm of its target; the order and the
      stagger as set (test reads the keys); fasteners first with Outside in.
- [ ] Works after a joint moved the subassembly (the step starts from where the parts are), with paint schemes, queue
      and scripts off; Build twice gives the same keys.
- [ ] Clash check: a sequence along the chosen direction gives no rows on the test model (parts fly out, not through).
- [ ] Tooltips, guide, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

The one-click product video (#18 – uses this step later), automatic collision-free directions (only the simple rules
above; a part blocked in its direction is reported, not solved), AR/web export of sequences.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
