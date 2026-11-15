# 0143 – Web 3D model: under the sea – seabed, the cable in the water, the sea cut-away, the camera under water

**Who:** worker · **Status:** waiting – starts **after 0142 is merged** (same files) · **Branch:**
`task/0143-web-sea-cutaway`
**Started by:** lead chat, 15 Nov 2026 (owner: "cutout is not visible in web 3D model") · **Model:** Opus · effort
Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Web 3D lane):** `core/web3d_env.py`, `blender/web3d.py`, `fr_page.js` / the player, their tests; reads the app's
sea code (`surroundings.py`, `paths_sea.py`, the seabed and cut-away of 0081) – never edits it.
**Do not edit:** the app's sea and cable code (0137, 0138).

## Goal

On the page you can see what happens under the water as in the app: the seabed, the cable going down to its
touch-down, and the app's **sea cut-away** box (the see-through window in the sea with the clarity setting).

## Background

- The owner's demo (0.2.105) in the app shows the sea cut-away: a clear box behind the stern, the seabed with its
  ripples, the power cable and the A&R wire going down to the touch-down. On the page the sea is one opaque surface:
  nothing under it, no cut-away (the panel says "Not in the web model: … the cutaway").
- 0142 makes the cables move on the page; this task makes the water let you see them.

## What to build

1. Export the seabed (depth, its look, the app's sand ripples as a small tile) when the project has one.
2. The sea cut-away: the box's place and size (moving with the vessel as in the app), the water inside drawn see-through
   with the app's clarity (fog colour and distance), its edges as in the app.
3. A switch in 0134's settings menu: "Under the sea" on/off (only when the export holds it); Auto quality may turn
   it off on Phone.
4. Without a cut-away in the project: the sea stays as today.
5. **The camera may go under the sea** (owner, 15 Nov 23:44): today the page stops the camera at the horizon
   (`controls.maxPolarAngle = 0.497π` with a sea, `fr_page.js`). Let it dive: under water the view gets the water's
   colour and fog by the project's clarity, the surface seen from below, the seabed as the floor (the camera stops
   just above it). Smooth at the surface (no flicker when the camera crosses it). A menu switch "Camera under water"
   (on by default when the export holds the seabed).

## Done when

- [ ] The demo's page shows the cut-away, seabed and the cable to its touch-down; headless pictures vs the app at 2
      moments in `tasks/img/0143_*`.
- [ ] Tests (box place and clarity read from the project; the switch; no seabed when the project has none); page cost on
      Phone / Balanced in the report.
- [ ] Guide, tooltips, function list, PC-check line; GitHub run green; merged; version; short list for the owner.

## Not in this task

Moving cables (0142); the model's own cutaway / section slider (0135).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
