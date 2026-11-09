# 0056 – The same STEP imported twice: each copy gets its own part IDs

**Who:** worker · **Status:** open – can start (lead, 9 Nov: 0055 done; 0054 waits for 0041, so `states.py` is free – finish before 0054 starts) · **Branch:**
`task/0056-same-step-twice`
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

- [ ] The row's proof passes (second cover hidden, first shown); a model update of one copy leaves the other alone.
- [ ] Old projects (one copy per model) open and update unchanged (test with a 0.2.30 project as in 0045).
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0056 done.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
