# 0056 – The same STEP imported twice: each copy gets its own part IDs

**Who:** worker · **Status:** done (0.2.44) · **Branch:**
`claude/epic-pasteur-rxl5c4`
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 row 11)
**Lane:** Looks (importer) – `importer/step_reader.py` (uid), `blender/states.py` (`by_uid`), `blender/reimport.py`
(uid mapping, additive); tests
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

Two cranes from the same STEP on one quay act as two cranes: hiding, poses, show/hide steps and model updates of one
never touch the other. Old projects keep their uids.

## Background (`tasks/0045-bug-hunt.md`, row 11)

The uid is the path of names, so both copies get `TEST.CRANE#1/...`; `states.by_uid` uses `setdefault`, so the
second copy's entries act on the first. Suggested: make `by_uid` per model root, or put a per-import token in the
uid scope; projects with one copy unchanged.

## Done when

- [x] The row's proof passes (second cover hidden, first shown); a model update of one copy leaves the other alone.
- [x] Old projects (one copy per model) open and update unchanged (test with a 0.2.30 project as in 0045).
- [x] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [x] Report filled in; `TASKS.md`: 0056 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code web session (branch `claude/epic-pasteur-rxl5c4`), 9 Nov 2026. Released as **0.2.44**.

**What changed:**
- `blender/build.py`: a model whose part IDs are already taken by a model in the project gets a scope in front of
  all its IDs (`~2/TEST.CRANE#1/COVER#1`, then `~3/` …), stored on its root (`fr_uid_scope`). First copy and every
  one-copy project: no scope, IDs as before. Not `@`: `joints.PartLookup` uses `@<name>` for parts of other models.
  `path_of` (what the rules match) drops the scope, so both copies sort alike. Helpers `scoped`, `unscoped`,
  `uid_scope`, `used_uids`, `free_scope`, `model_root_of`, `repair_uids`. Done in Blender, not in the importer: both
  copies share one import cache, so `CACHE_VERSION` is unchanged.
- `blender/reimport.py`: the new revision keeps the old one's scope (a new one only if those IDs are taken).
- `blender/handlers.py`: upgrade step "part IDs" (`build.repair_uids`): an old project with two copies sharing IDs
  gets a scope on every copy after the first, in scene order, i.e. the copy that `states.by_uid` found so far keeps its
  IDs, so saved sets/poses/steps act on what they acted on before. Returns at once when all IDs are unique.
- `blender/decals.py`: templates store the copy by its unscoped path (still match old scoped/unscoped values).
- PC check line `model.two_copies` (0.2.44), `MIN_LINES_FULL` 41 → 42. Guide chapter 1: "The same file twice".
- `states.by_uid` unchanged: with unique IDs `setdefault` no longer mixes copies.

**Tested and measured** (4-core Claude Code web session, bpy module, test crane):
- `tests/test_same_step_twice.py` (11 tests): IDs of 2nd/3rd copy and another model; the row's proof (visibility
  set hides the second cover, first shown); pose and Hide step on the second copy only; update of copy 2 to rev B and
  then copy 1, each leaves the other's IDs and sets alone; a joint on copy 2 survives its update; one-copy update keeps
  plain IDs; old two-copy project repaired on open (first copy keeps its IDs, old set still hides what it hid);
  unique-ID projects untouched by every upgrade step.
- Locally also green: test_model_update, test_phase2, test_decals, test_rule_sets, test_looks_fixes, test_blender,
  test_stacked_joints, test_pccheck, test_user_guide (190 tests).
- **0.2.30 projects** (made with the `v0.2.30` tag as bpy module, test crane A, a joint, a visibility set, a pose):
  one copy: opens with IDs unchanged, joint valid, set and pose apply, update to rev B: 11 kept / 1 new / 1 missing,
  joint kept, set still hides the cover. Two copies: opened → second copy gets `~2/`, joint, set, pose as before;
  updating the second copy leaves the first's IDs alone.
- PC check lines `model.two_copies`, `model.update`, `states.poses` run locally: 3 OK in 4 s.
- GitHub: 2 runs, no failures, no version clash. Branch run 42648019425 full, green in 14.6 min (test suites 1 and 4
  flagged SLOW: 7.7 / 8.9 min against 3.9 / 5.0 usual). `main` run 42650567025 reused that run and published, checked
  and offered 0.2.44.

**Open points / follow-up tasks:**
- In a 0.2.43-or-older project with two copies, a set/pose/step that the user made *for the second copy* acted on
  the first one; after the repair it still does (nothing can tell which copy was meant). Re-save such sets once.
- Leftover branch for the owner to delete on github.com: `claude/epic-pasteur-rxl5c4`.
