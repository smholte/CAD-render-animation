# 0100 – Assembly sequence step: take a subassembly apart (or put it together) part by part (study 0069 #9)

**Who:** worker · **Status:** done (0.2.79) · **Branch:** `ccr-b270b448-9405yw` (the web session's branch)
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

- [x] Take apart and Put together on the test model: every part ends within 0.01 mm of its target; the order and the
      stagger as set (test reads the keys); fasteners first with Outside in.
- [x] Works after a joint moved the subassembly (the step starts from where the parts are), with paint schemes, queue
      and scripts off; Build twice gives the same keys.
- [x] Clash check: a sequence along the chosen direction gives no rows on the test model (parts fly out, not through).
- [x] Tooltips, guide, tour stop, PC-check line; GitHub green; report filled in; merge to main and release.

## Not in this task

The one-click product video (#18 – uses this step later), automatic collision-free directions (only the simple rules
above; a part blocked in its direction is reported, not solved), AR/web export of sequences.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 13 Nov 2026 · branch `ccr-b270b448-9405yw` (the
session's own branch; no `task/0100-…` branch) · version 0.2.79

**What changed:**
- New step kind **Assembly sequence** (`props.BLOCK_KINDS` "SEQUENCE", settings `FRAnimBlock.seq_*`, additive):
  Take apart / Put together; order Outside in / Tree order / Reverse; direction Along an axis (+X … -Z of the
  subassembly – one way, not "to the side the part lies on": that sent the lower half of a stack down through the
  housing) / Up / Away from the centre; distance by size or set; Per part (s) + Overlap (the step's length follows,
  like a G-code step's); At the end Stay / Hide / Fade; Trail lines; Preview slider (moves the parts without keys,
  stored on the parts as `fr_seq_preview`, put back at 0 % and at the start of every Build).
- `core/sequence.py` (no Blender): order, directions, distance, stacking, times. Two rules learned on the test model:
  (1) **stacking runs from the last part out**: the last to leave goes the set distance, each earlier one ends beyond
  the later ones across its way – the first version stacked the other way and the clash check found the housing
  flying through the parts already out; (2) **Outside in asks Blender's rays** whether a part still in place blocks
  the way (`blender/sequence.Rays`), so a ring in a cup leaves before the cup going up and after it going down (boxes
  alone cannot tell). Fasteners still go first unless a part physically sits on them.
- `blender/sequence.py`: movers (hoses / chain links left out, parts a joint puts on another mover ride along), the
  world at the step's start (`_WorldAt` sets the earlier steps' joint values and free moves for a moment), keys as
  Go to pose writes them (`rest @ delta`), so a later Pose/Joint step still works; Put together returns to the place
  a Take apart step took the part from; hide/fade through Build's own visibility/fade keys; a trail line per part
  (`FRTrail.seq_owner`, removed when the step or its tick goes); a blocked way → a warning at Build.
- `animation.py`: 6 additive lines (end preview, prepare, tidy trails, `seq_home`, the bake branch, the label).
  `ops_motion.py`: Add step / Use selected / Duplicate / Remove know the step. `ui_motion.py`: the step's box.
- Test model `tools/make_test_sequence.py` → `test_sequence.step` (spindle unit: 12 parts, 5 fasteners, on a base
  plate; also in `fresing_render/data/`). Tour set + stop "Assembly sequence"; PC-check line `animation.sequence`
  (MIN_LINES_FULL 61, MIN_LINES_TOUR 47, MIN_CHECKS pccheck 40 / tour 47); guide section "Take a subassembly apart"
  + `docs/img/panel_6_sequence.png` (on the crane's boom).

**Tested and measured** (web session, 4 cores, no graphics card):
- `tests/test_sequence.py` 15 tests: core (times, stagger, orders, stacking, minus axis, centre, reverse); in Blender:
  every part within 0.01 mm of its planned target (take apart) and of its place (put together), order and stagger
  read from the keys (starts 12–13 frames apart at 0.5 s, 25 fps), nut + 4 bolts first, housing last; apart then
  together with Hide/Fade; Build twice = identical keys; after a joint turned the unit 30° the parts fly along its
  turned +X and come back to where the joint had put them; **clash check: 0 rows** (apart along +Z, together up);
  a blocked way (-Z, tree order) is reported; trail lines 12, not doubled, removed with the tick; Preview and back.
- Build of the test model's step: 0.05–0.07 s. PC-check line locally: OK, 2.2 s (incl. clash check).
- Tour: `test_go_sets_the_stop_up_and_its_check_passes[sequence]` passes; tooltip report 640 ok, 0 missing.
- Scripts off: the step writes only plain keyframes (no drivers). Paint schemes / queue: the queue builds again in
  its background Blender like every step (not run separately for this step).
- GitHub: 1 full run on the branch, green (run 43346308506, 13.5 min); main fast-forwarded to that commit, reuse run
  43352459125 published v0.2.79, the old-version update check and the offer to the apps green. No version clash.

**Open points / follow-up tasks:**
- Parts outside the subassembly are not in the blocked-way check (only parts of the subassembly); a frame round it
  shows up only in the Clash check.
- A part that rides on another mover (a joint on a part) only rides along; it does not fly on its own.
- Away from the centre does not stack: parts going nearly the same way can end close together.
- No independent review agent (saving usage: no Windows-only code; the clash check served as the independent test).
