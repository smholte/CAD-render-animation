# 0326 – Faster joint drag with many parts

**Who:** worker · **Status:** open · **Branch:** `task/0326-faster-joint-drag`
**Started by:** lead, 25 Nov 2026 (0315's slow place 3, the owner's Stress run on his PC) · **Model:** Opus · effort High
**Area:** Motion lane – `blender/joints.py`, `blender/handlers.py` (what runs after a joint moves), and the per-move
hooks they call (hover, cables that follow, live clash, lead motions' "moved by") only where the profile points; their tests,
CHANGELOG.
**Not:** `pccheck/checks.py` and `pccheck/stress.py` (0332 / 0333 / 0325 change them – measure with the existing
`stress.drag` line, do not change it), `ui_motion.py` and `ui_lead_motions.py` (0333 changes them), the clash check itself
(0327), the importer.

## Goal

On a big model, a joint follows the mouse smoothly: the crane slews as you drag, though 11,000 other parts stand still.

## Background

- 0315 (`tasks/0315-stress-model-10k-parts.md`, item 3): 78 ms per step on the 4-core web machine.
- **The owner's Stress run, 25 Nov 21:06, 0.2.257** (Ryzen 9 9900X, RTX 3090): `stress.drag` **51.4 ms per step**, slowest
  57.9 ms – about 19 steps a second; playback of the built animation 13.6 ms/frame on the same model. So moving a
  joint by hand costs about 4× a played frame: something runs per drag step that playback does not need.
- `stress.drag` = `joints.set_value` + a view-layer update, 40 times (`pccheck/stress.py`, "stress.drag").

## What to do

1. **Profile first** (cProfile + a timer per handler) one drag step on the Stress model (`tools/make_test_stress.py`):
   our handlers vs Blender's own depsgraph update. Put the split in the report.
2. Fix what is ours: e.g. handlers that walk every object on each update, work that can wait until the drag ends
   (mouse up), work only for parts the joint moves. If most of it is Blender's own, say which part and what would help.
3. Keep behaviour: cables / hoses that follow, live clash colouring, lock, undo (one step per drag), lead motions'
   "moved by" and the Client view all work as before (their tests stay green).

## Done when

- [ ] `stress.drag` ≤ about 25 ms per step on the web machine (was 78), the profile split before / after in the report
- [ ] A drag on the demo project and the crane test model works as before (tests for followers, clash colour, undo)
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] CHANGELOG; the owner's re-check line in the report ("PC check > Stress – the drag line", target ≤ about 16 ms
      on his PC)
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
