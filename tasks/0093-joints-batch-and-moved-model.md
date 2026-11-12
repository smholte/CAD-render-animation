# 0093 – Joints made in a batch: fast and right; a model moved by its root keeps its place

**Who:** worker · **Status:** running · **Branch:** `claude/sleepy-archimedes-jo86od` (the web session's branch)
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

- [x] One scene update per batch (or per level of stacking), not per joint; the demo's joints measured before/after
      (target well under 10 s on the web machine) and the whole Make demo project time.
- [x] Test: a base and a joint stacked on it made in one batch – the stacked axis equals the one made in two steps
      (< 0.01 mm, < 0.01°); the demo's work-round removed and its tests still green.
- [x] Test: a model root moved and turned by hand, then Build, a pose, a saved scene, the start scene, a model update –
      it stays; a part moved by hand inside it still goes back; two copies of one STEP placed apart stay apart.
- [x] Every joint test file green (`test_stacked_joints`, `test_couplings`, `test_cylinders`, `test_linkages`,
      `test_waycover`, `test_model_update`, `test_demo_project`); GitHub green; merged with the next free version;
      report filled in; `TASKS.md` updated.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 12 Nov 2026. Branch `claude/sleepy-archimedes-jo86od`
(the session's own branch, not `task/0093-…`). GitHub runs: 2 – the first (43205137419) failed only because the
new test file, counted 30 s, moved test_fade.py and test_section.py (one EEVEE skip each) into one group; its
measured 5.9 s is now in `tools/ci_times.json` (the file is also sorted now, no other value changed).

**What changed:**
- `joints._batch` updates the scene once on the way in (the CAD pose) and once on the way out; `create` and
  `set_follows` skip their own updates inside it. New `joints.world_of(scene, ob)`: a joint empty made earlier in the
  same batch gets its place from its parents (its `matrix_world` is the identity until the update); everything else is
  in the evaluated CAD pose and keeps its world place when a joint takes it over. `create` and `rebuild_from_specs`
  read every place through it (the update before a stacked rebuild is gone). `_local_axis`/`_world_axis` take an
  Object or a matrix (cylinders unchanged).
- Demo (`demo.make_joints`): the `_update` work-round is out, and the couplings are made inside the same batch.
- A model's root is never a free move: `free_moves` and `apply_free_moves` skip objects with `fr_root` (also an old
  saved delta on a root does nothing). Parts inside a model are free moves as before. No change to `reimport.py`,
  `animation.py`, `handlers.py`: the model update already copies the old root's `matrix_basis` to the new root.
  Old projects open unchanged (nothing is written on load).
- User guide (1 Import, "The same file twice": placing a copy; 4 Motion: Everything back), CLAUDE.md section 8,
  CHANGELOG 0.2.69.

**Tested and measured** (4-core web machine, small demo = the PC check's form, Blender as a module):
- Demo joints stage: **67.0 s → 2.1 s** (with the profiler on); whole small "Make demo project": **160 s → 90 s**
  (the rest is the model writer, 64–71 s, and the import, 14–15 s).
- New `tests/test_joint_batch.py` (7 tests; 5 failed before the fix): stacked joint in one batch = two steps
  (< 0.01 mm, < 0.01°, on a moved and turned model, base implicit and explicit) and it moves the same; no scene
  update inside a batch of 4 joints + 3 couplings; a stack rebuilt by a model update on a moved model; a moved root
  stays through reset, pose, saved scene, CAD pose, a built animation with a start scene, clear keys and a model
  update, while a part moved inside it goes back; two copies placed apart stay apart; an old root delta is ignored.
- Locally green: test_joint_batch, test_stacked_joints, test_couplings, test_cylinders, test_linkages,
  test_waycover, test_model_update, test_doublearm (164 passed), test_demo_project (13 passed, 7 min).

**Open points / follow-up tasks:**
- No PC-check line or tour stop added: this is a fix of existing functions (speed + place), nothing new to see;
  the PC check Heavy demo line already reports the joints stage (metric "joints"), so the owner sees the speed-up on his PC.
- A whole model moved by its root can no longer be keyed by a free-move animation step (it never is a free move
  now); moving a whole machine in a video would be a motion-path task.
- Merge conflict risk with 0091 (also in `demo.py`): only `make_joints` changed here.
