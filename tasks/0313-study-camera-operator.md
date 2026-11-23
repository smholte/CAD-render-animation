# 0313 – Study + prototype (findings only): a camera operator – ready-made camera moves with a few options each, paths to edit, quick to use

**Who:** worker · **Status:** running · **Branch:** `task/0313-study-camera-operator` (branch only, never
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

- [ ] Report + page on the branch → the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
