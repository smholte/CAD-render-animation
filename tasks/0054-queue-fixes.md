# 0054 – Render queue and video fixes from the bug hunt

**Who:** worker · **Status:** running (9 Nov) · **Branch:**
`claude/friendly-cerf-hn6s1i` (the session's branch)
**Started by:** lead chat, 9 Nov 2026 (bug hunt 0045 rows 7, 8, 9, 10, 17, 18, 20b)
**Lane:** Motion (panel 7 Render queue) – `blender/queue.py`, `blender/ops_motion.py` (queue operators),
`blender/states.py` (`save_shot`), `blender/animation.py` (`CamState.of`, `bake`); additive `blender/callouts.py`
(row 20b only); tests; guide "Render queue"
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

What the queue renders is what the owner sees, an overnight queue stays in its own project, stopped jobs never mix
old frames into a new video, and videos keep the sharp spot on a moving part.

## Background (proof and suggested fixes: `tasks/0045-bug-hunt.md`)

- **Row 7** – "Add image" while scrubbed in a built animation queues a different picture (visibility and camera).
- **Row 8** – a stopped or failed animation job reuses old frames, even past the new end (fingerprint + encode only
  `frame_0001 … frame_<end>`).
- **Row 9** – a running queue leaks into any project opened afterwards (key the runtime state by the project file).
- **Row 10** – videos use a stale sharp distance when the sharp-spot part moved.
- **Row 17 a–e** – five small queue faults (remove while running, hidden "Queue …" scenes, rename drops
  "(with watermark)", deleted saved scene, runner dies before status.json).
- **Row 18** – paths typed as `//…` break in the queue's copy (360° photo, logo, font, music, picture cards). The
  G-code file and tool table were done in 0051.
- **Row 20b** – the labels pass reads every part's box on every frame (50 ms per frame on the Heavy machine).

Owner's later wish 0050 ("Start queue in …") is in the same panel; it may be added here only if the owner asks
before this task starts.

## Done when

- [ ] Every row fixed with a test from its proof (17c–e and 18 may be by reading + test).
- [ ] Row 20b: frame time with labels on the Heavy machine before/after.
- [ ] Guide "Render queue"; tooltips if anything visible changed.
- [ ] Tests; GitHub green; merged to `main`, next free version, released (CLAUDE.md section 7).
- [ ] Report filled in; `TASKS.md`: 0054 done.

## Not in this task

Tool changes (0041). Milling (0051). Model update (0052).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
