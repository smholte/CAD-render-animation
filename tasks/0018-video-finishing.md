# 0018 – Video finishing: logo, title and end card, captions, formats

**Who:** worker · **Model:** Sonnet · **Status:** done (0.2.23) · **Branch:** `task/0018-video-finishing`
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

**Chat / date:** worker chat (Sonnet), 5 Nov 2026

**What changed:**
- `core/brand.py` (no Blender): brand kit files (`<library>/Brand kits/<name>.json` + logo copy), the time line
  (title card + animation + end card), captions from labelled steps (min 1.5 s, never into the next one), logo box,
  watermark words. `blender/video.py`: everything is put on the pictures with the Video Sequencer in a throw-away
  scene (colour strips for the cards, text strips, image strip for the logo); also the logo/watermark on stills and the
  crop/extend camera framing. `queue.encode_mp4` calls it; `render.finish_still` adds logo + watermark.
- UI: sub-panels "Brand kit & logo" and "Watermark" in 5, "Finishing" in 6 (own files `ui_video.py`, `ops_video.py`;
  nothing in `ui_motion.py`). New animation settings `fin_*`, `shape_fit`; scene settings `brand_*`, `still_logo*`, `wm_*`;
  `FRQueueJob.watermark` (a job remembers it; the queue's job file carries it).
- Watermark and logo only go into MP4 videos and stills (the queue says so for PNG frames).
- "1 props deleted" -> `plural()` (the only count in this lane's messages).
- Tooltips: every new setting/button; report 290 found, 0 missing. User guide chapters 5 and 6 + 3 pictures.
- Found: Blender 5.2 does not evaluate animated strip properties when rendering without a window (a keyframed fade stayed
  at its stored value), and a *still* render of a later frame does not move the sequencer: fades are made of 3-4 strips
  with fixed opacity, tests render one-frame animations.
- Behaviour change: 9:16 videos used to show a narrow strip of the middle (Blender's auto fit); new animations start on
  "Extend" (whole width of the 16:9 picture). Old projects get the same default.

**Tested and measured** (2-core test machine, test crane):
- 33 new automated tests (`tests/test_video.py`, 2.5 min): kit save/load/list/delete, captions timing, logo corners in
  16:9/1:1/9:16, fade pieces without gaps; title card colour, caption box and letters at the step times and not before or after,
  logo red in the chosen corner only, watermark across the middle and not in the corners, see-through amount; stills (PNG and
  JPEG); queue job with and without watermark; a queued animation with every option -> square 540x540 MP4, 24 + frames + 24 long.
- Real app `tools/ui_test_video.py` (registered in `ci_real_app.py`, `video`): 14/14, 5.4 min (the queued video is most of it:
  6 frames Cycles draft on the processor). Screenshots of the three panels checked.
- Not measured: render time on the RTX 3090; the sequencer part itself is small (54 frames 540x540 in seconds on 2 cores).

**Open points / follow-up tasks:**
- Logo formats: only PNG and JPG (Blender cannot read SVG); brief said PNG/SVG.
- The project keeps the kit's settings but the logo is the library's file (path): when the library is not reachable and the file is
  gone, the logo is left out and the queue log says so. Embedding the logo in the project would fix it.
- Fonts: a font file path (the library does not copy fonts).
- Watermark/logo for PNG-frame videos: not done (MP4 and stills only).
- Cards fade their text with a few steps of opacity, there is no cross-fade between card and animation.
- Owner test on his PC: a real finished video (title card, captions, logo) and the watermark switch. Next in the lane: 0025.
