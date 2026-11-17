# 0188 – Fix: mesh model update keeps the work on a moved group without a name (bug hunt 6, row 5)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0188-mesh-update-moved-groups`
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

- [ ] The row's case keeps all 6 parts, the Hide step's target, the hidden state and the joint (on the moved place).
- [ ] 0162's open point (only B left) keeps B's work.
- [ ] STEP model updates behave exactly as before (their tests pass unchanged).
- [ ] Tests that failed before for both cases.
- [ ] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

The STEP reader; other 0183 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
