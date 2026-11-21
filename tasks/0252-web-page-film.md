# 0252 – Web 3D page: "Film" – play the motion through the video's camera, with the page's baked light

**Who:** worker · **Status:** running · **Branch:** `claude/sleepy-fermat-52ww3l` (the web session's branch)
**Started by:** lead, 21 Nov 2026 13:50 (owner 13:30: "now we have the 3D viewer and the camera positions, could we
also have a button to follow the cameras through the animation – like the real rendered animation, but with the baked
light in the 3D web viewer"; his picks 13:45, see Background) · **Model:** Opus · effort High
**Area:** Web 3D lane –
- `blender/web3d.py`, `core/web3d.py` (the film's data in the export), `ops_web3d.py` / `ui_web3d.py` (three tick
  boxes; additive), the Web 3D settings on the scene (additive properties, wherever the lane keeps them today);
- `web/fr_page.js` (the camera follows the film), `web/fr_player.js` (the Film button, the overlays);
- read only: `blender/animation.py` (the Animation camera, `fr_anim_camera`), `blender/camera_path.py`,
  `core/callouts.py`, `core/brand.py`, `blender/video.py` (what the video shows and when);
- tour stop `web3d` only (`changed=`), PC check `web3d.film` (new line), `core/functions.py` (one new entry), the
  guide's "Web 3D model" section, CHANGELOG, CLAUDE.md section 3's web lines.

**Not:** the Animation tab, Camera steps, `animation.py` / `camera_path.py` / `video.py` themselves (read only), the
render, other tour stops, `site/` (the landing page's own models get Film only when the site is rebuilt – say in the
report whether one of them should).

## Goal

A page made with Make > Web 3D model (any project whose animation has a built Animation camera) gets a **Film**
button in its play bar. Film plays the motion **seen through the video's camera** – the same shots, camera moves,
cuts and field of view as the rendered video – with the page's own (baked) light. The visitor can leave it at any
moment by dragging and go back with one press.

## Background

- **Owner's picks (21 Nov 13:45):**
  1. The page opens **as today (free view)**; a **Film** button in the play bar starts the film.
  2. A drag or zoom during the film **leaves the film, the motion keeps playing**; the Film button lights up, and one
     press goes back into the video's camera (at the moment that is playing).
  3. By default **camera + motion only**. **Captions, labels and the title / end card** each get a **tick box in the
     export** (lead: all three off by default – the owner's recommended pick was "camera + motion only").
  4. **Only the Animation camera** (the Camera steps of the Animation tab). The turntable's and the product video's
     cameras = later (TASKS.md "Later" list) – keep the data shape open for more than one film, but build one.
- **What exists:** the page plays the motion (0134: Space, time slider, ½× 1× 2×, ← →; 0142 moving cables etc.), shows
  the project's saved cameras as fixed views with a glide between them (0134, 0179: one views control, the render's
  frame fitted into the free area – `hfov` / `vfov`), puts view + moment in the address (0134). The Animation camera is
  keyed on every frame at Build (`animation.py` `_anim_camera`, `camera_path.py`: ride along, fly a path, watch part,
  glide-ins `cam_blend`); hard cuts are where the video cuts. Neither is in the page today.
- The owner's aim: as simple as possible. One button; no film settings on the page beyond it.

## What to build

**A. The film's data (export).** Read the Animation camera over the page's frame range (the same frames and frame
rate as the page's motion): place, turn and field of view per frame, in the page's coordinates (as the saved views
are converted today). Store only what is needed – e.g. keys where the move is not straight, or quantised per frame –
and mark the **cuts** (a jump between two frames is a cut, never smoothed). Aim: ≤ ~200 KB for the full demo kit's
4,481 frames, ≤ 1 % of a normal page; say the size in the report. No Film data when there is no built Animation
camera or the export has no motion (then no button). Depth of field and motion blur are not on the page (say so in
the guide in one line).

**B. Film on the page (`fr_page.js`, `fr_player.js`).** A **Film** button in the play bar (tooltip "Play the video's
camera moves"), also on a phone (0179's compact layout, no overlaps). Pressed: the camera takes the film's place, turn
and field of view **on every drawn frame, from the motion's own time** – so the time slider, ← →, speed and pause all
move the film camera with it; the render's frame is fitted into the free area like a saved view. A drag, a zoom, a
saved view or a part tool that moves the camera **leaves the film; the motion goes on**; the button shows it can take
you back; pressing it glides back (short, like a saved view) into the film at the current moment. At a cut the camera
jumps. The address holds `film=1` (0134's link). Under water, Slice, measuring keep working as on a saved view.

**C. Export tick boxes (`ui_web3d.py`).** Under the Web 3D export, only when the project has an Animation camera:
**Film: captions**, **Film: labels**, **Film: title and end card** – all off by default, each with a tooltip.
- *Captions:* the video's captions as text over the film at their times (what `video.py` / `core/brand.py` show –
  same words, same times); only while Film is on.
- *Labels:* the video's part labels with their lines, the box placed by the same rule as the video where cheap, the
  line's end on the part as it moves; only while Film is on and only when they are shown in the video.
- *Title and end card:* the video's title card before the film's first frame and the end card (logo) after its last,
  for their seconds; Film from the start shows them, scrubbing past them hides them.
Anything of these that the video draws with Blender's sequencer and the page cannot do the same way: do the plain
version and list the difference in the report.

**D. Everything that names it.** Guide "Web 3D model" (Film button, the three tick boxes, what the film does not
show), function-list entry + guide anchor (`since=`), tour stop `web3d` text (`changed=`, re-record), PC check
`web3d.film` (export a small moving test model with a Camera step, the page in film mode at two moments: the camera
within ~1 mm / 0.05° of Blender's Animation camera, a cut jumps), CHANGELOG, CLAUDE.md section 3.

## Done when

- [ ] A page from a project with a built Animation camera has Film; one without has no button
- [ ] In film the page's camera matches Blender's Animation camera at any frame (tests: several frames incl. a ride
      along, a fly a path, a watch part, a glide-in and a cut: place ≤ ~1 mm × model size / 1 m, angle ≤ 0.05°, fov
      ≤ 0.05°); a cut jumps, never glides
- [ ] Slider, ← →, speed, pause move the film camera with the motion; drag / zoom / saved view leaves film while the
      motion plays on; Film glides back at the current moment; `film=1` in the link opens in film
- [ ] The three tick boxes: off by default; on, each shows on the page as in the video (captions' words and times,
      labels on the moving parts, the cards' seconds); off, nothing of them is in the file
- [ ] Phone layout (0179's checks) with the Film button: no overlaps
- [ ] Film data size reported (small test model, the public demo "Vessel in a wind park"); page frame time not worse
      than without Film on the web machine (numbers)
- [ ] Guide, function list, tour stop `web3d`, PC check `web3d.film`, CHANGELOG, CLAUDE.md; full suite + GitHub green

## Not in this task

- The turntable's and the product video's cameras as films (later – TASKS.md "Later").
- Depth of field, motion blur, the video's music, watermark, picture cards on the page.
- The landing page's models (`site/`) – say in the report which one would gain from Film.
- Any change to how the video itself is rendered.

---

## Design (worker, 21 Nov 2026)

- **Data in the page's settings, not in the glTF:** `ST.films = [ {name, kind "ANIMATION", fps, n, aspect, ps, k, p, q,
  v, cut, captions?, labels?, cards?} ]` – a list, so the turntable's / product video's cameras can follow. In three's
  world (Blender (x, y, z) -> (x, z, -y)), because the glTF's root rides in the page's vessel group while the video's
  camera lives in the world.
- **Read in `Job._motion`'s own pass** (same frames, same fps): `blender/web3d_film.Film.read` – `matrix_world` and
  the vertical fov from `calc_matrix_camera` (exact for every sensor fit; an ortho camera as the angle at the model).
- **`core/web3d_film.encode`:** runs split at the cuts (the Cut steps' frames + big single-frame jumps found in the
  numbers); per run only the frames a straight blend (place, fov) / `slerpFlat` (turn) cannot give, checked with the
  stored numbers at every frame: 0.25 mm per metre of the model (min 0.25 mm), 0.02°, fov 0.02°; whole numbers as
  steps from the kept frame before. `sample` = what `fr_page.js` `filmAt` plays (a cut holds the shot before).
- **Page:** Film = the camera set in `draw()` from the motion's own time (after OrbitControls' update), like a saved
  view for the under-water / floor clamps; the controls' `start` (drag, zoom), a saved view, Reset and `setCamera`
  leave it; `setFilm(true, glide)` glides 0.6 s back. Cards: the motion's clock (`advance`) waits while a card shows;
  at the Film's end the end card, then the title card, then from the start; `setTime` skips a card.
- **Overlays (`fr_player.js`):** captions (DOM, the video's place 0.09 / size 0.05 of the render's frame), cards (DOM,
  the video's lines), labels on a 2D canvas after each picture (`page.afterDraw`): the label's point in its part's glTF
  node (`gltf.parser.associations`), the boxes by a port of `core/callouts.place_labels` with the model's box as the
  outline.

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 21 Nov 2026 (branch `claude/sleepy-fermat-52ww3l`, the session's own branch).

**What changed:**
- New `core/web3d_film.py` (no Blender): the camera's place / turn in the page's world, cuts, thinning between cuts
  (0.25 mm per metre of the model, 0.02°, fov 0.02°, checked at every frame with the stored numbers), delta-int JSON,
  `decode` / `sample` (what the page plays), the captions as seconds (`brand.caption_list`).
- New `blender/web3d_film.py`: `Film` reads the built Animation camera in `Job._motion`'s pass (fov from
  `calc_matrix_camera`), cuts from the Cut steps + jumps found in the numbers; captions (`video.captions_of`), labels
  (point in its part's glTF node, live words per frame, window), title / end card (brand kit colours, logo ≤ 640 px).
  `set_up_test`: the crane – ride on the boom, path watching the trolley with a glide-in, cut, keep the trolley in the
  middle; label, captions, cards. A camera-only film (nothing else moves) plays too.
- `web3d.py`: the hook in `_motion` / `finish` (`st["films"]`, the result line "Film: the video's camera, N KB").
  `props.py` three tick boxes `film_captions`, `film_labels`, `film_cards` (off); `ops_web3d.py` passes them;
  `ui_web3d.py` shows them under Include animation only with a built Animation camera, + a line in "On the page".
- `fr_page.js`: the Film (camera from the motion's own time after OrbitControls, glide back 0.6 s, leaves on drag /
  zoom / saved view / Reset / setCamera, `film=1` in the link and at the start, the cards' clock, `afterDraw`,
  `page.nodes`, `filmState` in the PC check's state). `fr_player.js`: Film button (orange ring when left; on a phone
  under 330 px the time text hides), captions / cards (DOM), labels (2D canvas, port of `place_labels`).
- PC check `web3d.film` (Full; MIN_LINES_FULL 116), tour stop `web3d` (builds "Camera rides and flies", exports with
  animation: the page has the Film; crane set changed 0.2.194, recorded), function `web.film`, guide "Film" section
  (`#web3d-film`) + Playback line, CHANGELOG 0.2.194, CLAUDE.md section 3.

**Tested and measured** (web machine, 4 cores, software GL):
- `tests/test_web3d_film.py` (14: data + page in headless Chromium), `tests/test_web3d_film_blender.py` (7: real
  export of the crane against Blender's Animation camera at every frame, the cut, each camera mode, tick boxes, label
  point, no film without camera / animation, the page's camera at three moments). Player, tools, web3d, functions,
  guide, places, PC check tests pass; `test_tour.py -k web3d` passes; PC check line `web3d.film` OK (8.2 s).
- **Accuracy:** crane (1.8 m): worst 0.44 mm, 0.015°, fov 0.0002° (limits 1.8 mm, 0.05°). Public demo "Vessel in a
  wind park" (small form, 132 m): worst 33 mm (limit 132 mm), 0.020°, fov 0.0004°; 7 cuts found.
- **Size:** crane 126 frames -> 98 kept, **4.0 KB**; public demo 1,489 frames -> 309 kept, **9.4 KB** (page ~40 MB:
  0.02 %); a worst case of 4,481 frames that all must be kept (a camera turning all the time): < 200 KB (test).
  The full demo kit was not measured (private repository, not this task's).
- **Frame time:** the Film's own work per picture: 0.7 µs (camera) + 36 µs (one label, 1280 × 720 canvas) – under
  0.3 % of a 60 fps picture. Pictures in 3 s on the synthetic page (capped at 60/s): 181 off, 180 on, 180 off.
  On the crane at Best, 1280 × 720, software GL the numbers jump (13–21 pictures in 4 s, the Film's view fills more
  of the screen); not a cost of the Film.
- **Independent tester** (a subagent that did not write the code, 26 probe runs): 0 differences between the page and
  `core.web3d_film.sample` over 58 times (cuts, sign flips, t = D, beyond); encode edge cases fine. Found 4 faults;
  fixed 3 with tests: the Film button pushed the play bar off a 280 px phone (and `layoutCheck` missed it); a Film
  shot further than the orbit limit was pulled in at every picture (drew all the time while paused, a 2 px drag
  snapped 379 m in); leaving during the end card and pressing Film showed the end card again.
- GitHub runs: listed below.

**Owner steps** (after the update):
1. Open a project whose animation has Camera steps (or Help > test tour, crane set, stop "Web 3D model").
2. 6 Animation: **Build & play** the animation.
3. 5 Scene & Render > Web 3D model: tick **Include animation**; under it, tick **Film: captions**, **Film: labels**,
   **Film: title and end card** if wanted. Press **Export…**, then **Open page**.
4. In the browser: press the **film-camera button** at the right end of the play bar. You should see the motion
   through the video's camera (same shots and cuts as the video). Drag: you leave the Film, the motion goes on, the
   button gets an orange ring; press it: the view glides back. Please check on your RTX 3090 that it stays smooth.

**Open points / follow-up tasks:**
- The time line's very end (t = length) shows the first frame, as the motion already does (the page loops): with a cut
  near the end, the slider's last position shows the first shot. Not changed (would differ from the parts).
- Not on the page (guide says so): depth of field, motion blur, music, watermark, picture cards, the brand kit's font.
  The cards' clock runs at the play speed (2×: half their seconds). Captions / labels stay in the clean look (H) and
  are not in Screenshot (S).
- With vessel motion on the page, the parts move by the page's own sea motion while the Film's camera is the video's
  keyed world camera: a camera riding on a moving vessel may sway slightly differently from the vessel on the page.
- Labels' box placement uses the model's whole box as the outline (the video uses the shown parts' boxes).
- Landing page: the Thor arm and the CEB press would gain most from a Film (their render-kit animations have camera
  moves); needs the site's models exported again with Include animation (site lane).
- The full demo kit's size (private) and the turntable / product video films (TASKS.md "Later").
