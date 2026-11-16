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
   distance between the planes; not parallel → the angle between them, and the point-to-point distance.
   (c) **Diameter** (owner, 15 Nov 22:18): click a round face (hole, shaft, bore) → its diameter (Ø … mm).
   (d) **Centre to centre:** two round faces → distance between their axes (parallel axes; otherwise the shortest
   distance between the axis lines and the angle). (e) **Face to centre:** a flat face and a round face → distance
   from the plane to the axis. (f) **X/Y/Z switch:** when on, every measurement also shows its X, Y and Z parts as
   arrows in the axis colours (X red, Y green, Z blue, as Blender), each with its own number. Round faces: read their
   axis and radius from the export (the app already finds them, `fr_face_starts` / `joints.axis_from_hit`; 0122 note:
   faces on one axis line get ONE axis with the largest radius – keep the clicked face's own radius). Needs face data in
   the export: decide the lightest way (a per-triangle face id or normal groups in the .glb, as the app's
   `fr_face_starts`), measure the file-size cost and keep it optional per export if it is large.
3. **Cutaway slider.** One plane (X / Y / Z, flip) moved by a slider; cut faces closed or a clear cap colour, like the
   app's cut-away (0086) – mind the sea and the vessel motion.
4. **Fade the rest on click.** The clicked part stays solid, the others go see-through (as the app's X-ray / Fade);
   click empty space or Esc to undo.
5. Each tool in the settings menu / a small tool row, in the keyboard help (0134), working on phone (tap, long-press).
6. Guide section, tooltips of the export settings, function list entry, PC-check / headless tests.

- **Bug hunt 0147 rows 16 and 21d–f (added by the lead, 16 Nov; the player's settings and phone layout):** (16) a
  remembered setting of the wrong type (e.g. `off` not a list under `fresing-player:<path>`) stops the page for good –
  type-check every remembered field and drop bad ones; (21d) a software-rendering browser writes `off=shadows` into the
  link – write only items the visitor switched; (21e) phone: portrait help covers the tool column, landscape 844×390
  menu covers the 2nd tool column and help overlaps the title, help says "1 … 1" with one view, touch hint says
  "right-drag … ? for keys" – a narrow-height layout, help as a bottom sheet, touch wording (this task adds tools, so
  lay them out for phones from the start); (21f) a screenshot of a page with a non-ASCII title saves as "download"
  without `.png` – fold the file name to ASCII. Proofs and numbers in `tasks/0147-bug-hunt-5.md`.

## Done when

- [ ] 1–5 in the player; headless tests (a click at a known pixel gives the expected part / distance / plane distance /
      diameter / centre-to-centre / face-to-centre, and the X/Y/Z parts
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
