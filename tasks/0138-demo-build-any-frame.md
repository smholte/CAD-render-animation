# 0138 – Fix: the demo's Build gives a different result depending on the frame shown

**Who:** worker · **Status:** waiting – starts after 0137 is merged (same files) · **Branch:** `task/0138-demo-build-any-frame`
**Started by:** lead chat, 15 Nov 2026 (rows of bug hunt 0131, report in `tasks/0131-bug-hunt-4.md`) ·
**Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Flex parts lane / Demo models lane):** what the second end, its CPS, the riders and let go read at Build (`paths*.py`, `demo.py` stages only if the cause is there), their tests.
**Do not edit:** the Web 3D lane (0134/0135), the Import lane (0139), `sequence.py` (0140).

## Goal

Build gives the same animation whatever frame is shown when the owner presses it – today shots 9–12 of the demo go wrong (second end and CPS up to 73 m off) when he Builds at a later frame.

## Background

The rows below are from bug hunt 0131 (report on `main`): each row has the place in the code, how to repeat it
("Proof") and a suggested fix. Read those rows first; repeat each one before fixing it.

- **Row 6:** built at frame 1 = what Make demo saved; at 1803 24 objects differ; at 3206 the second end and CPS lie up to 73 m off and Build warns "98 m more cable than the water is deep". Not on the small `test_moving` model – something the demo's second end adds (parts excluded until shot 9, CPS rider, quadrant, let go) reads the pose shown. Find it; Build reads everything at the animation's first frame (or a fixed start pose). Test: the demo (or a small model that repeats it) built at the first and the last frame → identical.

## Done when

- [ ] Every row above fixed, each with a test that failed before the fix (the row's proof as a test).
- [ ] Tooltips, guide sentence where the owner sees a change, function list / PC-check / tour stop only if something
      visible changes; GitHub run green; merged; version (CLAUDE.md section 7); report (short list for the owner).

## Not in this task

Other rows of 0131 (they have their own tasks: 0136–0140); the files of running tasks named above.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
