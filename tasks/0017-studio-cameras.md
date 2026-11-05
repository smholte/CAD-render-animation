# 0017 – Studio lighting, camera views, focus and one-click turntable

**Who:** worker · **Status:** done (0.2.17) · **Branch:** `task/0017-studio-cameras`
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
   hall is the background, the turntable button says so and offers Simple (the "Time test" is
   in panel 6, Motion lane: leave it).

## Done when

- [x] Tests: each lighting look and view builds and renders a small CPU frame; views frame the
      model (all corners inside the image); focus distance set from a click; turntable creates a
      valid animation that the queue renders
- [x] Real-app click test step and screenshots of panel 5 checked
- [x] Full suite passes; report filled in; merged and released (`CLAUDE.md` sections 2 and 7)

## Not in this task

- Logo, titles, captions, video formats (0018). Panels 4, 6, 7 (Motion lane).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker chat, 5 Nov 2026. Version 0.2.17 (no installer: "Saving usage" rule).

**What changed:**
- `core/studio.py` (new, no Blender): light designs (Product, White, Dark studio; CIE overcast sky),
  the five one-click looks, light in plain words, blur f-stop (thin lens), turntable timing.
- `world.py`: new Light choices Product/White/Dark studio (stored numbers 3–5; Studio 0, 360° photo 1,
  Sky 2 unchanged, Studio now labelled "Soft studio", its picture untouched), packed light pictures,
  `sky_weather` Sun/Overcast wherever the sky lights (also sea/deck/quay). `states.WORLD_KEYS` and
  templates keep the weather; scenes/templates from before have no weather → sunny.
- `cameras.py`: views Isometric (orthographic), Front, Side, Top, 3/4 hero low/high (+ older ones under
  More), framing whole model or selection with Tight/Normal/Roomy space; blur None/A little/Strong per
  camera (`fr_blur`), f-stop worked out from lens, sensor and sharp distance so the look is the same at
  any machine size; sharp spot = empty with Child Of on the clicked part as the focus object;
  turntable camera aimed at the Orbit axis. Fixed on the way: orthographic camera in a portrait picture
  cut the sides off; a new camera on the sea did not see to the horizon until the next rebuild.
- `turntable.py` + `ops_scene.py`: Make turntable video = camera, tagged saved scene and animation
  "Turntable" (one linear Orbit step of 360·(N−1)/N° over N frames: loops without a jump), job in the
  queue, queue started. `animation.py`, `ui_motion.py` untouched. Hall note + Use Simple.
- Panel 5: Light look buttons at the top, light words line, Camera and Turntable video sub-panels;
  tooltips on everything new (`tooltip_report.py`: no panel 5 findings; no Scene & Render rows were left
  in TOOLTIPS-TODO, 0016 did them). `render.pictures_dir` cached (lru_cache, restype set).
- Guide chapter 5 (Light look with a picture of the five looks, Light, Camera, Turntable video),
  pictures `panel_5_scene/surroundings/camera/turntable.png`, `looks.jpg`; `tools/guide_screens.py`
  mode `looks`; `docs/DEVELOPMENT.md` section; real-app test `tools/ui_test_studio.py` in
  `ci_real_app.py` (MIN_CHECKS 21).

**Tested and measured** (2-core Linux test machine, no graphics card, generic test models only):
- `tests/test_studio_cameras.py`: 115 tests (every look and every Light × weather renders a CPU frame;
  every view, landscape and portrait, has all model corners inside the picture and fills ≥ 85 %;
  selection framing; space; focus distance from a ray-cast click = projected distance; spot follows
  its part; blur numbers; old cameras keep their f-stop; turntable: camera on the axis, whole crane in
  the picture at 6 moments, 360/N per frame, loop closes; queue: the button queues and starts it, then
  a time test of the real turntable renders in the background queue). Full suite on GitHub.
- Real app (Blender 5.2.3, xvfb): `ui_test_studio.py` 21/21 twice (looks, live preview, views,
  click-to-select + Frame: Selection, Ctrl+Z/Ctrl+Shift+Z, eyedropper click on the boom, lens,
  render with blur, hall note, turntable button → first frame rendered by the queue in 63 s, Stop now,
  save + reopen). Panel 5 screenshots at the default width checked: three cut-off labels fixed
  ("Whole m…", "Where I look n…", "Background bl…").
- Old project made with main's 0.2.13 code: opens with the same Light, saved scenes keep Studio /
  360° photo / Sky, a camera with the old Blur keeps f/3.2 and its focus.
- Render time, crane, 480×270, Preview, CPU: old Soft studio 16.1 s; Product 18.0, White 16.2, Dark
  16.3, Outdoor sun 12.5, Overcast 15.1 s; Product + blur 18.7–19.2 s. Synthetic 2,812-part scene:
  add view 0.24 s, Fit 0.05 s, blur 0.05 s, turntable make 0.52 s, view on 600 selected parts 0.38 s.
- Independent review (Windows-only `pictures_dir` + the whole change): no blocker; 4 should-fix
  (old scenes/templates took today's weather; a stopped/failed turntable job rendered again next to the
  new one; a camera copied with Shift+D shared and could delete the other's sharp spot; texts claimed
  the spot follows its part in animations) and minors (user's own scene "Turntable" overwritten, failed
  queue start left a job blocking the button) – all fixed, with tests.

**Open points / follow-up tasks:**
- Owner: try the looks, blur and a turntable on the RTX 3090 (render time per frame of a 10 s turntable).
- Motion lane (next task there): the animation camera copies only the focus distance, not the sharp
  spot (`animation._anim_camera`); copying `dof.focus_object` would let the spot follow its part in
  videos. Queue: a queue restarted within the same second as a stop reuses the stopped folder and stops
  at once (its stop file is still there) – seen in a test, rare by hand.
- `render.pictures_dir` caches the fallback ~/Pictures if the Windows lookup fails once (same as
  `documents_dir`); no self-test line added for it.
- Changing size, shape or frame rate of "Turntable" in 6 Animation needs Make turntable video again
  (said in the panel and guide).
- Branch `task/0017-studio-cameras` can be deleted on github.com.
