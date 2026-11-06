# 0025 – Labels pointing at parts, picture cards and music in videos

**Who:** worker · **Model:** Sonnet · effort Medium · **Status:** done (0.2.26), branch merge pending · **Branch:** `task/0025-callouts-pictures-music`
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

- [x] Tests: label line stays on its moving part through an animation (anchor projected per frame
      within 2 px), no overlap of two labels, label of a hidden part hidden; picture card at the
      right times; MP4 has an audio track of the right length with the fades; stills with labels
- [x] Real-app (written; runs on GitHub only, no Blender download here) click test step and screenshots checked
- [ ] Full suite passes, GitHub run green; report filled in; merged and released (see the report)

## Not in this task

- Decals on the model (0024). Voice-over, several animations edited into one film.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker (Claude Code on the web, Sonnet), 6 Nov 2026

**What changed:**
- `core/callouts.py` (no Blender): picture cards and where they go in the time line (a full-screen card stops
  the animation: `brand.Plan.inserts`, `video_frame()`; captions move with it), music span + smooth gain curve,
  label boxes (beside the machine, never overlapping, never on their own point, or placed by hand), the line
  drawn with numpy; `core/mp4.py` reads the tracks of an MP4 (used by tests and the PC check).
- `blender/callouts.py`: the clicked point is stored as part + point in the part's own coordinates, projected for
  every frame (`world_to_camera_view`), hidden when the part or a parent is hidden, behind the camera or outside the
  picture; one transparent picture of lines per frame (`<video folder>/_lines`), boxes + text as text strips
  (fade like captions). `video.py`: label strips, picture cards (full / corner), music, frames strip split where a
  full card is put in. `queue.py`: labels planned after the frames are rendered; MP4 with AAC sound when there is music.
  `render.py`: stills get their labels (lines folder removed again).
- Music: Blender does not evaluate animated strip volumes without a window (as in 0018), and fade pieces with fixed
  volumes gave small bumps at the joins, so the music is decoded with Blender's own mixdown, cut and faded with
  numpy (linear fades) and put in as one sound strip.
- UI: `ui_callouts.py` (Labels in panel 5, Pictures & music in panel 6), `ops_callouts.py` (Add label = click in the
  3D view like decals, Remove, Show the part, Add/Remove picture). New props `callouts`, `callout_size`,
  animation `cards` + `music_*`. Tooltips for all (report: 342 found, 0 missing). Guide chapters 5 and 6, changelog,
  PC-check line `video.labels` (31 full lines).

**Tested and measured** (4-core test machine, test crane and decals models):
- `tests/test_video_callouts.py`, 18 tests, 25 s: card time line and caption shift, music span and fades, boxes do not
  overlap and keep off the machine, line pixels; the label point of a moving part is within 2 px of an independent
  projection in every frame; hidden part / other step hides the label; picture cards at the right frames (pixels);
  labels + lines follow the point in rendered frames; a full card cuts the label; MP4 sound track 4.0 s for a 4.0 s
  video, 8 s of music cut; fades half way at the right times (mixdown); stills with labels; tooltips. `test_video.py`
  and `test_ci_tools.py` still pass (48).
- PC-check line run locally: OK (12 s).
- Not run here: the real-app test `tools/ui_test_callouts.py` (no Blender download, 403) - GitHub runs it; the full
  suite result and the GitHub run are in the commit notes below.

**Open points / follow-up tasks:**
- No guide pictures for the two new panels (they need the real app: `tools/guide_screens.py`); the guide text is
  there. A later docs/screenshot pass should add `panel_5_labels.png` and `panel_6_pictures.png` (the real-app test
  already writes `callout_panel_5/6.png` screenshots on GitHub).
- Hidden *behind another part* is not detected (only hidden parts); a label stays while something covers its spot.
- Boxes are fixed per video (placed from where the point is on average); a part that crosses the whole picture
  drags its line across the box. Dragging a box with the mouse is not done (two sliders instead).
- Only MP4 videos get labels, cards and music (like logo/watermark); not PNG frames.
- Owner test on his PC: a real video with labels on a moving part, a photo card and a music file (MP3 too).
