# 0141 – Study: why the demo's Build depends on the frame shown (cause of 0131 row 6, findings only)

**Who:** worker · **Status:** open – can start now (findings only: no app code pushed, starts no test run) ·
**Branch:** `task/0141-demo-build-frame-study` (scratch only, never merged)
**Started by:** lead chat, 15 Nov 2026 (owner: a Fable task with the usage left) · **Model:** Fable · effort High ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area:** reading and running `paths*.py`, `demo.py`, `demo_model/`, `animation.py`, `riders` / let go / sea end code –
**no edits on `main` except this file and `tasks/img/0141_*`**. 0126 (CPS run) and later 0137 change these files:
do not push code; scratch scripts stay outside the repository or on the scratch branch pushed with `[skip ci]`.

## Goal

Find the exact cause of 0131's row 6 and write the fix plan, so task 0138 (Opus · High, after 0137) only has to
build it.

## Background

Row 6 of `tasks/0131-bug-hunt-4.md`: on the demo, Build at frame 1 gives exactly what Make demo saved; at frame 1803
24 objects differ; at the last frame (3206) the second end and its CPS / bend restrictors lie up to 73 m off (60–70 m
aft on the seabed from shot 9 on) and Build warns "98 m more cable than the water is deep… at frame 1651". Also with
vessel motion off. **Not** on the small `test_moving` model – so something the demo's second end adds (parts excluded
until shot 9, the CPS rider, the quadrant, let go) reads the pose shown. Proof script in the row.

## What to do

1. Repeat row 6 (Make demo once – about 9 min – then Build at frames 1 / 1803 / 3206 and compare).
2. Bisect the cause: which value read at Build differs with the frame shown (joint values, rider carry places, the
   excluded-until-shot-9 parts' places, the sea end's anchor, let-go frames, cached plans). Name the function and
   line.
3. Make the **smallest test model** that repeats it (an existing tour or test model plus a few steps, or a small maker
   in a scratch script) – the test 0138 will turn into a failing test first.
4. Check whether other stages or smaller models have the same pattern (riders, sequence, spool, tracks: Build at the
   last frame vs the first on their tour sets – quick check per set).
5. Write the fix plan: what to change, where, and why it is safe (Build reads at the animation's first frame or a fixed
   start pose), and what 0137 must not undo.

## Done when

- [ ] Cause named (function, line, why); smallest repeat case described with its script (in the report or on the
      scratch branch); other places with the same pattern listed.
- [ ] Fix plan for 0138 written in the report; 0138's brief left as it is (the lead updates it).
- [ ] Report pushed to `main` touching only `tasks/` (no run); then check that `main` really contains your commit.

## Not in this task

The fix itself (0138); the other 0131 rows (0136, 0137, 0139, 0140).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
