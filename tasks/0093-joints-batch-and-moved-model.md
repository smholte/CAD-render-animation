# 0093 – Joints made in a batch: fast and right; a model moved by its root keeps its place

**Who:** worker · **Status:** open – can start · **Branch:** `task/0093-joints-batch-moved-model`
**Started by:** lead chat, 12 Nov 2026 (0077's and 0035's open points)
**Lane:** Motion – `blender/joints.py`, `blender/build.py`, `blender/logic.py`, `blender/states.py` if needed; tests.
**Not** `animation.py`, `handlers.py`, `reimport.py` (0058 adds hooks there today): if the fix needs them, stop and say so.
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Making many joints by script (the demo's 415, a later "joints from Inventor/Fusion") takes seconds, not a minute, and a
stacked joint made in the same batch as its base lands on the right axis. A whole model moved by hand (its root dragged in
the view, e.g. the second copy of the same STEP) stays where the user put it after Build, poses and saved scenes.

## Background

- 0077: `joints.create` and `set_follows` each update the whole scene (about 0.1 s on the demo): **69 s for 415 joints**
  of the 148 s "Make demo project". Inside `joints._batch`, a stacked joint's axis is computed from its base before the
  update: a base made in the same batch has no world matrix yet (the demo's tensioner tilt hinge landed metres off; the
  demo works round it – take the work-round out once fixed).
- 0035: moving a whole model copy by its root (`matrix_basis`) without updating `fr_rest_basis` puts it back at the next
  Build. `build.rest_basis` is the "no free move" place; a root turned by the app (`logic.py` line ~386) already resets
  it. Decide with care: parts moved by hand inside a model are a free move today (they go back) – keep that; only the
  **root** of a model (and of each copy) keeps a hand move. Old projects must open unchanged.

## Done when

- [ ] One scene update per batch (or per level of stacking), not per joint; the demo's joints measured before/after
      (target well under 10 s on the web machine) and the whole Make demo project time.
- [ ] Test: a base and a joint stacked on it made in one batch – the stacked axis equals the one made in two steps
      (< 0.01 mm, < 0.01°); the demo's work-round removed and its tests still green.
- [ ] Test: a model root moved and turned by hand, then Build, a pose, a saved scene, the start scene, a model update –
      it stays; a part moved by hand inside it still goes back; two copies of one STEP placed apart stay apart.
- [ ] Every joint test file green (`test_stacked_joints`, `test_couplings`, `test_cylinders`, `test_linkages`,
      `test_waycover`, `test_model_update`, `test_demo_project`); GitHub green; merged with the next free version;
      report filled in; `TASKS.md` updated.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
