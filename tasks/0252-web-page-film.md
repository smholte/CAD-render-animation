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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Owner steps** (after the update):

**Open points / follow-up tasks:**
