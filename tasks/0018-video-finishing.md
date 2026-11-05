# 0018 – Video finishing: logo, title and end card, captions, formats

**Who:** worker · **Model:** Sonnet · **Status:** waiting (0017) · **Branch:** `task/0018-video-finishing`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Scene & Render · **Area:** `blender/render.py`,
`blender/queue.py` and `queue_runner.py` (video assembly only), new `blender/video.py`, the 5 Scene
& Render part of `blender/ui.py`, `blender/props.py` (additive), `tests/`.
**Shared:** a new fold "Finishing" at the end of panel 6 Animation (`ui_motion.py`, Motion lane)
is allowed as one additive block; update the branch to `main` right before merging.

## Goal

Videos come out ready to post or send: the company logo in a corner, a title card at the start and
an end card with logo and contact line, captions taken from the names of the animation steps, and
the right shape for LinkedIn/website (16:9, 1:1, 9:16).

## Background

- Builds on 0016/0017; read their reports. Animations are rendered by the background queue
  (`queue.py`, `queue_runner.py`) to frames and MP4. Each animation step has a label (`name`),
  shown as a timeline marker – a natural caption text.
- Blender's Video Sequencer can put text strips, image strips (logo) and colour strips (cards)
  over rendered frames and write the MP4; no Python needed when the file is played back.
- The owner works for his own company and for others: a **brand kit** (logo file, colours, font,
  contact line) per company, stored in the shared library like the rule sets of task 0015.

## What to build

1. Brand kits in the library (logo PNG/SVG, two colours, font, contact line); one picked per project.
2. Per animation: logo corner on/off, title card (title, subtitle, seconds), end card (seconds),
   captions on/off (from step labels, timed with the steps, with a fade), output shape 16:9 / 1:1 /
   9:16 (camera framing kept: crop or extend, the owner chooses).
3. Still images: optional logo corner too.
4. **Watermark** (owner, 5 Nov 2026): "DRAFT", "CONFIDENTIAL" or own text, across stills and
   videos, size and see-through amount adjustable; on/off per render job, so a draft can be sent
   and the final rendered clean without changing the project.
5. Tooltips for every new button and setting; user guide chapter for all of it.

6. Small, from task 0023: "1 props deleted" (`ops_surroundings.py`) and any other count in this
   lane's messages: use `core/words.plural()`.

## Done when

- [ ] Tests: a queued animation with all options produces an MP4 of the right size and length
      (title + animation + end card), captions appear at their step times (check frames), logo
      in the chosen corner; still with logo; brand kit saved/loaded from the library
- [ ] Real-app click test step and screenshots checked
- [ ] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Labels pointing at parts, picture cards between steps, music: task 0025 (next in this lane).
- Logos, text and pictures on the model itself (decals): task 0024 (Looks lane).
- Voice-over, editing several animations into one film (possible follow-ups).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
