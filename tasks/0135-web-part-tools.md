# 0135 – Web 3D player: part tools – click a part, measure, cutaway, fade the rest

**Who:** worker · **Status:** done 16 Nov 2026 (0.2.131) · **Branch:**
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

**Chat / date:** Claude Code on the web, 16 Nov 2026 (branch `claude/vibrant-hawking-m0vw5o`).

**What changed:**
- **Export – face data** (`core/web3d_faces.py`, new; `blender/web3d.py` `face_data`): every CAD mesh's flat faces
  (plane: normal + offset) and round faces (axis point + direction + **the face's own radius**, worked out from its
  points – the importer keeps one axis per line with the largest radius, 0122) go into the `.glb` as two accessors per
  mesh (runs: first triangle → row; rows: 8 floats), named in the file's `extras.fr_faces`; cones / tori / fillets get
  an axis but no diameter (`AXIS`). Rows are in the mesh's written 16-bit coordinates, so the page's matrix of the
  hit mesh brings them to the world (moving, scaled, mirrored parts). A baked-light copy shares its mesh's data.
  New setting **Faces for measuring** (on; props, panel, operator, tooltip). Milled parts, drawn tubes and mesh models
  have no CAD faces: points only.
- **Export – cards**: node `extras.fr_card` = the part's label text (task 0025), else its name; with Hide part names
  its material group – never a part name (test).
- **Page** – `fr_measure.js` (new, the maths, node-testable) and `fr_tools.js` (new, the UI): the left column Part info
  (I), Measure (D: Faces / Points, X/Y/Z arrows with X), Cutaway (C: X/Y/Z, Flip, slider; cap colour by a
  `clipping_planes_fragment` addition for back faces, only on the model's materials, the plane in the vessel's frame),
  Fade the rest (T: see-through copies of the other parts' materials). Click = press + release without a drag; tap on
  phones; long press = the card; mouse hover lights the part / face (one ray a frame, off when a ray costs > 40 ms).
  Clicked points are kept in their mesh's coordinates: a measurement follows the animation. Keys in the keys help;
  `frPage.partTools` for tests; `?selftest=1` writes `data-fr-tools` (PC check).
- `fr_page.js`: `page.three`, `page.gltf`, `page.beforeDraw`, part nodes tagged; **0147 row 16** (remembered fields
  type-checked, bad ones dropped); **21d** (the link and the remembered settings hold only what the visitor switched,
  not the page's own "no shadows without a graphics card" / Auto's Under the sea). `fr_player.js`: **21e** (help as a
  bottom sheet on phones and low windows, tool buttons smaller so they stay one column at 844 × 390, the menu higher
  and longer there, touch wording in the hint and help, "1" with one saved view), **21f** (screenshot name folded to
  plain letters: "Plåt – test" → "Plat - test.png").
- Guide section "On the page: part info, measure, cutaway, fade the rest" (`web3d-tools`), the export step, the panel
  picture; function `web.tools`; tour stop "web3d" text + check (faces in the file, tools in the page); PC check
  `web3d.export` now also reads the part tools' self-test on the mill's page.

**Tested and measured** (4-core web machine, no graphics card):
- `tests/test_web_tools.py` (14): face data, maths by node (planes 50.0 mm, angle 90°, Ø40, centre to centre 200 mm,
  skew axes, face to centre both ways, X/Y/Z parts, number format, a stretched/moved part's row), and in headless
  Chromium on a made-up model of known sizes: every measurement by a click at the computed pixel, a real mouse click,
  a drag that does not pick, info card, fade (2 parts faded, back on empty click), cut (the shaft cut away, Flip keeps
  it), hide names + long press (card = group), hover lights a face, a page without face data (points, says so),
  self-test + keys help, phone portrait/landscape layout, junk in the remembered settings, the link without
  `off=shadows`. `tests/test_web3d_faces_blender.py` (2): the test crane's export – Ø13, 20, 22, 40, 40.4, 50 found;
  the Ø40.4 bore keeps its radius beside the Ø100 lug on one axis line; cards; labels; faces off.
- **File-size cost of the face data** (texture 256, draft import): test crane 164,264 → 181,456 bytes (+17 KB,
  +10 %; 349 faces); demo vessel (`demo_cable_lay.step`, 879,000 triangles, 264 meshes, 7,367 faces) 4,356,288 →
  4,712,836 bytes (+356 KB, +8 %), export 2.8 → 4.4 s. Kept on by default, with the tick to leave it out.
- A click on the demo vessel's page: 1–20 ms per ray (5 clicks across the view).
- **Independent tester** (a subagent that did not write the code, run from the brief): 9 faults, all fixed and each
  with a test in `test_web_tools.py` (3 tests added): (1) cables/ropes the page draws (0142) could not be clicked – a
  click went to the part behind – and Fade made them vanish (the see-through copy lost the material's shader code);
  now the ray is tested against their centre lines, the copy keeps the code; (2) cut first, then fade: the faded parts
  kept a copy of the cut plane where the slider was; (3) a click on the red cut face measured on a hidden back face –
  now on the cut plane ("Cut face"); (4) stickers (decals) counted as parts – the export marks them (`fr_decal`), the
  tools look through them; (5) phone: the Measure panel covered the play bar and the Clean look button – it sits
  above the bottom row, left of the right column; (6) a slow mouse click opened a card (the long press is for touch
  only now) and one Esc closed the help and the measurement; (7) shallow cones (Ø2000 → Ø1996.8) and R0.35 fillets
  read as cylinders – the round test is now 0.002 mm + 32-bit rounding; (8) any saved choice wrote `off: []`, which
  stopped Auto's Under the sea and no-graphics-card fallbacks – they now look at what the visitor switched; (9) the
  screenshot name dropped ø, æ, ß – spelt out now (o, ae, ss). What it found right: tilted / scaled / mirrored parts,
  several materials per part, compressed files, real exports of the crane, test_atc and test_faces_a (every pixel
  of 3 views: flat faces within 0.02 mm, round within the facet depth), vessel motion, touch, glass.
- Existing tests run locally: test_web_player, test_web3d, test_web3d_core, test_web3d_env, test_web3d_under,
  test_web3d_light_page, test_site, test_functions, test_user_guide; tooltip report 820/820; precheck.

**Open points / follow-up tasks:**
- The measurement's numbers and the card are page elements: a Screenshot (S) shows the lines, not the numbers.
- The link to a view (L) does not carry the tools' state (cut, measurement).
- Parts the vessel motion keeps Still or Level are measured in the vessel's frame (off by the motion while it rolls).
- Pages exported before 0.2.130 have no face data: they measure between points.
