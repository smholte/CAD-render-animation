# 0025 – Labels pointing at parts, picture cards and music in videos

**Who:** worker · **Model:** Sonnet · effort Medium · **Status:** done (0.2.26) · **Branch:** `task/0025-callouts-pictures-music`
**Started by:** lead chat, 5 Nov 2026 · **Lane:** Scene & Render · **Area:** `blender/video.py`
(from 0018), new `blender/callouts.py`, `blender/render.py`, `queue.py` / `queue_runner.py` (video
assembly only), the 5 Scene & Render part of `blender/ui.py`, `blender/props.py` (additive),
`docs/USER-GUIDE.md`, `tests/`. **Shared:** as in 0018, one additive fold in panel 6 Animation
(`ui_motion.py`, Motion lane) for the per-step settings; update the branch to `main` right before
merging.

## Goal

Brochure and explainer quality: labels with a line from a part to a text ("Gripper",
"Cylinder Ø63", "Max. 25 t"), a photo or diagram shown for a few seconds between animation
steps, and music under the video.

## Background

- Builds on 0018 (brand kit, title/end cards, captions, video assembly in the Video Sequencer);
  read its report first.
- Parts move in animations: a label's line must stay on its part (anchor point on the part,
  picked with a click like joint axes), in stills and in every frame of a video.

## What to build

1. **Labels (callouts):** click a point on a part, type the text; the label box sits beside the
   model with a thin line to the point; style from the brand kit (font, colours), size in plain
   words; place automatically (no overlaps, outside the machine's outline where possible) or drag.
   Show in stills and videos; per animation step "show these labels" (fade in/out). Labels that
   would point at a hidden part are hidden too.
2. **Picture cards:** an image (from the library or a file) shown full-screen or as a picture in
   the corner for N seconds, between steps or over a step, with a fade; optional caption.
3. **Music:** an audio file (the owner's own; a note that he needs the rights) under the whole
   video: start offset, volume, fade in/out, cut to the video length; MP4 with sound.
4. Tooltips; user guide chapter.

## Done when

- [ ] Tests: label line stays on its moving part through an animation (anchor projected per frame
      within 2 px), no overlap of two labels, label of a hidden part hidden; picture card at the
      right times; MP4 has an audio track of the right length with the fades; stills with labels
- [ ] Real-app click test step and screenshots checked
- [ ] Full suite passes, GitHub run green; report filled in; merged and released

## Not in this task

- Decals on the model (0024). Voice-over, several animations edited into one film.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker (Claude Code on the web, Sonnet), 6 Nov 2026

**What changed:**
- `core/callouts.py` (no Blender): fades, box placing, the line, picture-card frames, music plan. `blender/callouts.py`:
  the point (part + local position) is projected per frame with the camera matrices; hidden parts hide their label;
  `ops_callouts.py`, `ui_callouts.py` (5 Scene & Render > Labels; 6 Animation > Pictures, Music; nothing in `ui_motion.py`).
- `video.py`: label lines (one transparent picture per stretch of equal frames) and boxes (text strips with box), picture
  cards, a sound strip with keyframed volume; `queue.py` works out the labels after the frames and encodes AAC audio.
  Stills get labels through `finish_picture`.
- PC check line `video.labels`; real-app test `tools/ui_test_callouts.py`; guide chapters; changelog 0.2.26.

**Tested and measured** (4-core test machine, test crane, no graphics card):
- `tests/test_video_labels.py`, 18 tests: point within 2 px of Blender's own projection in every frame of a moving boom, no
  overlapping boxes, hidden part hides its label, step fade, stills, picture at its frames, box and line in video frames,
  queued MP4 with title card + picture + music: audio as long as the video, quiet start, fade out. ~4 min.
- Tooltip check: 363 found, 0 missing.
- Not run here: the real-app test and the screenshots (Blender download blocked); GitHub runs the test.

**Open points / follow-up tasks:**
- Pictures of the new panels for the user guide are missing (needs real Blender: `tools/guide_screens.py`; the test also writes
  `callouts_panel_5/6.png`). The guide text has no pictures for them yet.
- Click-to-add in the real 3D view was not tried (the script path was).
- Labels do not check whether the spot is hidden behind another part. Long labels are not wrapped.
- "Between steps" = leave a gap and start the picture there (no automatic pause of the animation).
- Tests that draw text run in their own process (`fresh_process`) because of a Blender-as-module quirk.
- Owner test on his PC: a real video with labels, a picture card and music.
