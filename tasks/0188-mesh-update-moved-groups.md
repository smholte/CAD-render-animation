# 0188 – Fix: mesh model update keeps the work on a moved group without a name (bug hunt 6, row 5)

**Who:** worker · **Status:** done (0.2.144) · **Branch:** `task/0188-mesh-update-moved-groups`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Opus · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Import lane (`blender/reimport.py` `match` / `_made_assemblies` for made-name groups, its tests)

## Goal

A mesh model update (glTF/OBJ/FBX) keeps hides, steps and joints on a group that has no name in the file, also when
the new revision moves that group.

## Background

- Row 5 of 0183: glTF with groups A/B/C (B unnamed → "Node 4"), named parts B1, B2; work on B (Hide step, hidden in
  Structure, joint "B1 turn"); the revision moves B by 100 mm → "4 kept, 2 new, 2 missing", Hide target gone, hidden
  state lost, **joint deleted**. A named group: all kept. Same in 0.2.114. Also 0162's open point (only B left → "2
  kept, 4 missing").
- Suggested: a part with its own unique name inside a made-name group pairs by name with no place limit; a made-name
  group pairs through its parts' votes (or their common shift), not its origin.

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [x] The row's case keeps all 6 parts, the Hide step's target, the hidden state and the joint (on the moved place).
- [x] 0162's open point (only B left) keeps B's work.
- [x] STEP model updates behave exactly as before (their tests pass unchanged).
- [x] Tests that failed before for both cases.
- [x] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

The STEP reader; other 0183 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort Medium), 17 Nov 2026. Version 0.2.144.

**What changed** (`blender/reimport.py`):
- `match`, rule 3 (same name): a part with a name the file gave it (`made_self` is False), the only record of that
  name in old and new, inside a group whose name the reader made, pairs by name with no place limit (`_own_name`).
  Piece numbers ("W 2") and names that occur twice still need the same place.
- `_made_assemblies`: a made-name group pairs with the group its parts voted for when it is in the same place (as
  before) **or** moved by just as much as every voting part moved (their box middles), within 5 mm.
- `_made_root` (0162's open point): when the new root's name was made by the reader (only one group left), the old
  made-name group that holds most of the parts now right under the new root pairs with the new root too. Its eye,
  Hide/Show and sequence steps go to the new root.
- Guide: the mesh-update paragraph says so. The comment in `tests/test_seq_mesh_0162_independent.py` points to the
  new test.

**Tested and measured** (web session, 4 cores, made-up glTF models in `tmp_path`):
- New `tests/test_mesh_update_moved_groups.py` (7 tests): row 5 with B moved 100 mm by its node or by its boxes,
  unnamed and named (control); only B left, in place and moved; the name rule on records. Before the fix 3 failed
  (node-moved unnamed: "4 kept, 2 new, 2 missing", steps' target None; both only-B cases: steps' target None). After:
  all pass – "6 parts kept, 0 new, 0 missing", B hidden, the joint on B1 at its new place (x + 100 mm).
- Locally: model update (STEP), cables, mesh import, mesh fixes, mesh independent, 0162 independent, phase2: 222 pass.
  The first try of the name rule broke `test_match_a_made_name_needs_the_same_place` (a record without `made_self`
  paired by its piece name); the rule now needs `made_self` to be False outright.
- No independent tester (saving usage; one module, narrow rule).
- GitHub: 1 full run on the branch, green (run 44140496184, 35 min; demo 1 slow at 26 min, all OK). main had moved only by
  the task list: no second code run.

**Open points / follow-up tasks:**
- The reverse case is not handled: an old model with only one unnamed group (that group was the root) updated to a
  file with several groups – the old root's work goes to the new file-name root, not to the group.
- A group that is moved *and turned* pairs only if each of its parts' box middles moved by the same amount (a turn
  makes them differ): then it is still lost unless it stays in place. Not seen in a case; say so if it shows up.
