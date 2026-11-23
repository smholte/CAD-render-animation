# 0313 – Study + prototype (findings only): a camera operator – ready-made camera moves with a few options each, paths to edit, quick to use

**Who:** worker · **Status:** done 23 Nov – findings only · **Branch:** `task/0313-study-camera-operator` (branch only, never
merged; every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner 21:14: "a camera operator, a few preset camera movements, each having a few
options to adjust and paths to be edited … keep it easy to use and fast." Example: https://superhivemarket.com/products/cinemaoperator)
· **Model:** Opus · effort High
**Area:** findings + design only; prototype in **new files** on the branch (e.g. `tools/camera_operator_proto/`). Reads
the Scene & Render lane: `blender/cameras.py` (views, blur, sharp spot, turntable camera), `core/camera_path.py` +
`blender/camera_path.py` (0087: Ride along, Fly a path, Watch part, glide-in), the camera part of `animation.py`,
`product_video.py` (0101 spots), study **0305**'s report (branch `task/0305-study-animation-exploded`: steps as bars on
the time line – its build task D). The page in `tasks/0313_page/`. Not a code slot.

## The example (lead's notes from its page, 23 Nov – look yourself too; if refused from the web machine, use these)

CinemaOperator (GPL, ~$50): moves built with on-screen pads – slide & crane, orbit, push / pull, roll, pan & tilt;
aim modes (follow a target, look along the path, turn smoothly between saved directions, hold a direction); a target
marker for aim and focus; framing guides (centre, thirds, diagonals) that never render; "CAM cards" on a time line –
curves between them made automatically, drag to retime, fit to a duration or space evenly; edit the path in a 3-view
layout or draw it with a pen; handheld / walk / vehicle shake with strength and seed, continuous roll; lens presets,
f-stop and depth of field; aspect presets; two tracks A / B with cuts; bake to plain camera keys. **Ideas only – no
outside code.** Its weak side for our users: many controls, a console look – ours must be a short list.

## What to find out

A. **The short list of moves** a machine film needs (rank them): orbit (whole model / a part; height, direction,
   how far round), push in / pull out (reveal), crane up / down, slide past, fly-over, top-down to side, follow a
   moving part (today's Ride along), low "hero" arc, focus pull from one part to another, a fly-through along a drawn
   path, handheld / walk / vehicle shake on any move. Each with **2–4 options** in plain words (speed, distance,
   start / end angle, easing) and a picture or a moving thumbnail.
B. **How a user does it fast**: pick a move → it is placed round the model / picked part at once and plays in the view;
   options as sliders; the path shown in the view with points to drag, add or remove; aim at the model, a part, along
   the path, or held; framing guides on / off; lens presets and focus on a picked part. One move = one Camera step
   (Build bakes keys as today, scripts-off safe). Chaining moves: glide, cut, or one long path.
C. **Who uses what**: a sales person picks "Orbit" and renders; an engineer adjusts; an animator gets plain keys and
   Blender's graph editor. Where it lives (5 Scene & Render, 6 Animation, the Make windows of 0308, 0305's time line).
D. **Speed**: placing and previewing a move must be instant on big models – measure on the test crane and the PC-check
   Heavy model (web machine).
E. **Prototype** on the branch: 6–8 moves on the test crane and the test mill as short clips, the options of two of
   them changed side by side, a drawn path edited; then phases and build tasks (Scene & Render lane – it also has
   0299 weather open: no shared file, or after it), models / efforts; the page with pick ticks and a Copy line
   (`0313 pick: …`).

## Done when

- [x] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 23 Nov 2026. Branch `task/0313-study-camera-operator`
(`[skip ci]`, never merged).

**What changed:** no app code. On the branch: the page `tasks/0313_page/` (`index.html`, 19 clips as MP4 + poster and 2 path pictures
in `clips/`, `timings.json`, `speed.json`; 0.9 MB, no external links) – **the lead publishes it for the owner's picks** (Copy line
`0313 pick: <tasks> · moves: <moves>`, default `A B C D E G · moves: orbit push crane hero slide topdown follow focus shake`).
Prototype in `tasks/0313_proto/`: `moves.py` (the moves, no Blender: every move = handles the camera flies through + aim + lens, fitted
with the projection rule of `cameras.fit`, flown on `core/camera_path.Path`; shake; move / add a handle), `clips.py` (the clips, bpy
module, Workbench; the focus pull in Cycles), `speed.py` (point D). Run lines in their docstrings.

Main finding (design): a ready-made move only **places** the points of today's Fly a path plus an aim and a lens – so one path editor
serves every move, dragging a point turns a move into a free path ("Orbit (edited)", Back to Orbit), and Build keeps baking plain keys
through `camera_path.plan` (scripts off, queue, saved projects unchanged).

The short list (ranked; 2–4 options each, on the page): 1 Orbit (how far, height, way, distance; round the model or a part) · 2 Push in /
Pull out to a clicked part (how close) · 3 Crane up / down · 4 Hero arc (low, wide lens) · 5 Slide past · 6 Top-down to side · 7 Follow a
moving part (chase, level, lag) · 8 Focus pull (part to part) · 9 Fly-over · 10 Fly-through a clicked path · 11 Shake on any move
(Handheld / Walk / Vehicle, strength, seed). Left out: roll, dolly zoom, A/B tracks (Cut to does it).

**Tested and measured** (web machine, 4 cores, no graphics card; Blender 5.2.3 as a Python module; draft import):

| Model | Parts | Triangles | Corner points | Place a move (6) | Key 125 frames | Frame step, camera only | Build, one Fly a path step |
|---|---|---|---|---|---|---|---|
| test_crane_a | 20 | 7,046 | 0.2 ms | 1.3–2.9 ms | 5.3 ms | 0.03 ms | 0.01 s |
| test_mill | 44 | 7,753 | 0.4 ms | 1.2–2.5 ms | 4.9 ms | 0.04 ms | 0.01 s |
| PC check Heavy (invented) | 2,992 | 3,782,496 | 40 ms | 1.3–5.5 ms | 5.5 ms | 4.4 ms | 0.52 s |

So placing + previewing a move is instant on all three, if the corner points are read once per step opening (40 ms on 2,992 parts in
Python), not at every slider move. Viewport frame rate not measured (no graphics card). Clips: Workbench 480 × 270 ~0.25–0.3 s a
frame; the focus pull in Cycles 4.9 s a frame.

Found on the way: (1) the smooth curve through an orbit's points strays from the circle at its ends – 2.1 % of the radius with 12 points
per turn (0.17 % in between), 4.9 % with 8 – because `Path` guesses its end directions by mirroring: an untouched orbit should stay an
exact arc and a path's ends should take the move's own direction (task A). (2) A focus pull framed on both parts was hard to see (near and
far at nearly one distance): it must frame the near part close (fixed in the prototype). (3) The hero arc ends with the long boom pointing
at the camera and leaving the picture: fit each point of an arc, not the arc once. (4) A steady orbit (one distance) leaves a long model
small when seen end-on – a "keep it filling the picture" switch is offered.

**Build tasks (ranked; page section 8):** A Camera move step with the first six moves, `core/camera_moves.py`, exact arcs (L, Opus High,
after 0299) · B instant preview (key only the step's camera, play through it) + Blender's camera composition guides (M, Opus Medium, with
or right after A) · C drag the path in the view: drag / + add / right-click remove, "(edited)", Back to the move, also for Fly a path (L,
Opus High, after A) · D Follow, Focus pull, Shake (M, Opus Medium, after A) · E lens presets 24/50/85/135 + zoom (S, Sonnet Medium, with D) ·
F chain moves on 0305's time line (M, after 0305 task D) · G one-move video from Make (0308) + product video and Turntable use the moves
(S–M, Sonnet Medium, after A and 0308) · H hand over as keys for animators (S, Sonnet Medium) · I Fly-over + path clicked on the model
(M, Opus Medium, after C). All Scene & Render lane plus the Camera step's box in `ui_motion.py` and `props.py` (shared files): after 0299,
one at a time.

**Open points / follow-up tasks:**
- The example page (superhivemarket.com) is refused from the web machine; its features come from the lead's notes in the brief.
- Not tried in the real app: the panel is an HTML mock-up; dragging handles (a modal + draw handler) and the preview's frame rate on the
  owner's RTX 3090 are expectations. Workbench clips stand for the view's look, not a final render.
- The moves were judged by eye on two small test models and timed on the Heavy layout (flat, 39 × 55 × 0.5 m); a tall or very long model
  may need other defaults (the hero arc above).
- Subagents: one (Sonnet) tried to read the example page (refused). No independent review (findings only). GitHub runs: none (`[skip ci]`).
