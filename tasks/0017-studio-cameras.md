# 0017 – Studio lighting, camera views, focus and one-click turntable

**Who:** worker · **Status:** waiting (0016) · **Branch:** `task/0017-studio-cameras`
**Started by:** lead chat, 4 Nov 2026 · **Lane:** Scene & Render · **Area:** `blender/world.py`
(lighting), `blender/cameras.py`, `blender/render.py` (depth of field), the 5 Scene & Render part
of `blender/ui.py`, `blender/ops_main.py` (camera/light operators), `blender/props.py`
(additive), `tests/`.

## Goal

Product-photo quality without knowing Blender: pick a lighting look, pick a standard view, click
where the focus should be, and make a 360° turntable video with one click.

## Background

- Builds on 0016 (surroundings); read its report first.
- Cameras today: saved cameras ("shots"), size presets for output (`core/presets.py`), camera
  gizmos sized to the model. Animations have a camera "Orbit" step (`animation.py`, Motion lane –
  **use it, do not change it**).

## What to build

1. **Lighting looks:** product studio (key/fill/rim softboxes), white infinite background
   (cyclorama with soft floor shadow), dark studio (black background, rim lights), outdoor sun,
   overcast. Light rotation and strength in plain words.
2. **Standard views:** isometric, front, side, top, 3/4 hero (low and high), each framing the
   whole model or the selection with a margin; saved as a camera in one click.
3. **Focus:** click a point on the model to focus there; "Background blur: none / a little /
   strong" instead of f-stops. Works in the queue.
4. **Turntable video in one click:** makes an animation with one camera Orbit step (360°, length
   in seconds, height), using the existing animation data and functions; puts it in the render
   queue. No change to `animation.py` or `ui_motion.py`.
5. Tooltips for every new button and setting, and the Scene & Render rows of
   `docs/TOOLTIPS-TODO.md` (25), deleted when done. User guide chapter 5 and its pictures.
6. Small, from task 0015's review: `render.pictures_dir()` makes a new ctypes structure type per
   call – cache it like `core/rule_sets.documents_dir`.
7. Halls render 1.4–2.8× slower than the studio on the processor (task 0016's report): when a
   hall is the background, the turntable and the "Time test" should say so and offer Simple.

## Done when

- [ ] Tests: each lighting look and view builds and renders a small CPU frame; views frame the
      model (all corners inside the image); focus distance set from a click; turntable creates a
      valid animation that the queue renders
- [ ] Real-app click test step and screenshots of panel 5 checked
- [ ] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Logo, titles, captions, video formats (0018). Panels 4, 6, 7 (Motion lane).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
