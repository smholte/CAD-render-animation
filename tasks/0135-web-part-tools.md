# 0135 – Web 3D player: part tools – click a part, measure, cutaway, fade the rest

**Who:** worker · **Status:** waiting – starts **after 0134 is merged** (same files) · **Branch:**
`task/0135-web-part-tools`
**Started by:** lead chat, 15 Nov 2026 (owner's wishes) · **Model:** Opus · effort High ·
**Place:** Claude Code on the web, environment "CAD-render-animation"
**Area (Web 3D lane):** `fresing_render/web/fr_page.js` / the player as 0134 left it, `core/web3d.py` (what the file
carries per part), `blender/web3d.py`, `ui_web3d.py`, their tests, the guide section.

## Goal

In the web 3D player the visitor can click a part to see what it is, measure distances, cut the model open, and fade
everything but one part – like the app's own tools, on PC and phone.

## What to build

1. **Click a part → name / label.** A small card at the part: the app's label text for that part if it has one
   (task 0025's labels), else its name – **only when the export keeps names**; with "hide names" (default, public
   pages) the card shows the group/look name or nothing, never a part name. Hover highlight on PC.
2. **Measure.** (a) Point to point: two clicks on surfaces → distance in mm (and the X/Y/Z parts of it), a line with
   the number. (b) **Between planes** (owner's wish): click a flat face, then another; parallel (within ~1°) → the
   distance between the planes; not parallel → the angle between them, and the point-to-point distance. Snaps to a
   round face's axis (hole centre to hole centre) as a stretch goal – say in the report if done. Needs face data in
   the export: decide the lightest way (a per-triangle face id or normal groups in the .glb, as the app's
   `fr_face_starts`), measure the file-size cost and keep it optional per export if it is large.
3. **Cutaway slider.** One plane (X / Y / Z, flip) moved by a slider; cut faces closed or a clear cap colour, like the
   app's cut-away (0086) – mind the sea and the vessel motion.
4. **Fade the rest on click.** The clicked part stays solid, the others go see-through (as the app's X-ray / Fade);
   click empty space or Esc to undo.
5. Each tool in the settings menu / a small tool row, in the keyboard help (0134), working on phone (tap, long-press).
6. Guide section, tooltips of the export settings, function list entry, PC-check / headless tests.

## Done when

- [ ] 1–5 in the player; headless tests (a click at a known pixel gives the expected part / distance / plane distance
      on a test model with known sizes, e.g. the test crane or `test_atc.step`); no part name in a page exported with
      hide names (test).
- [ ] File-size cost of the face data measured (test crane, demo vessel) and reported.
- [ ] Tooltips, guide, function list, tests; GitHub run green; merged; version; report with a short list for the owner.

## Not in this task

Everything 0134 does; weather on the page (0115).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
