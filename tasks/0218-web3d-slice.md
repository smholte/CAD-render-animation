# 0218 – Web 3D page: Slice instead of Cutaway – any face, several slices, edit and delete

**Who:** worker · **Status:** done 18 Nov 2026 (0.2.169) · **Branch:** `task/0218-web3d-slice`
**Started by:** lead, 18 Nov 2026 (owner's request of 18 Nov 22:13, through the ToolBox lead's lead-post message
`1118-toolbox-to-fresing-render-viewer-and-slice.md`) · **Model:** Opus · effort Medium
**Area:** Web 3D lane – `fresing_render/web/fr_tools.js` (the part tools), `fr_page.js` (only where the clipping planes
reach the materials), `fresing_render/web/README.txt`, `tests/test_web_tools.py` and the web page's checks,
`docs/USER-GUIDE.md` (the web page's chapter), function list / tour / PC-check entries of the page's cutaway. Not
`core/web3d_faces.py` (0219 may change it next).

## Goal

The web 3D page's **Cutaway** becomes **Slice** and works like slicing in House Planner: the owner picks a face of the
model and slices along it (or along X / Y / Z as today), keeps **several slices on at once**, and can **edit** (move,
turn) and **delete** each one. The page is meant to grow into the owner's STEP viewer (ToolBox plan), so it should
feel like a real viewer's tool.

## Background

- Today (task 0135, `fr_tools.js` header): "Cutaway (C) – one plane across X, Y or Z, moved by a slider, Flip keeps
  the other side; the cut faces show the app's cap colour. Only the model is cut (not the sea, the sky or the seabed)".
  State `st.cut = {on, axis, flip, at}`; three.js clipping planes with a cap colour drawn in
  `clipping_planes_fragment` (`CAP`).
- **House Planner's slice is the reference for the behaviour** – the public repository `smholte/house-planner`,
  `src/view3d.js`, section "slice" (anonymous clone; **never attach `smholte/house-planner-dev`**): the user picks a
  surface, gets a plane with handles (move, turn, size), slices are numbered ("Edit slice 2"), stay on while he works
  with other tools, and are listed with edit and delete. Read it for the behaviour and the words; copying code is fine
  only if its licence allows it in a GPL page (check its LICENSE; else write our own).
- A picked face already gives an exact plane (`extras.fr_faces`, `core/web3d_faces.py`: a flat face's plane, a round
  face's axis) – a slice on a flat face lies in it, a slice on a round face goes through its axis (owner's choice of
  turn with the handle).

## What to do

1. **Name:** "Slice" everywhere on the page – button, key hint (keep the key **S** if free, else keep C and say so),
   panel, tooltips, README, the guide. Old exported pages are not changed.
2. **Making a slice:** "Add slice", then either click a face (flat: its plane; round: through its axis, square to the
   view) or choose X / Y / Z (as today). The kept side: the side away from the camera is cut away; **Flip** swaps it.
3. **Several slices at once** (at least 6), each numbered ("Slice 1", "Slice 2" …), listed in the panel with **Edit**,
   **Hide / Show** and **Delete**. All slices cut together (the model shows what is on the kept side of every plane).
   The cap colour stays right where two cuts meet.
4. **Editing:** the selected slice shows a plane with handles – move along its normal (drag, or a number in mm), turn
   about two axes in its plane (drag, or degrees), size of the drawn plane only. Esc / Done ends editing; the slices
   stay on while measuring, picking a part or fading the rest – all of those must click "through" a slice to the
   visible (kept) geometry, never onto the cut-away part.
5. **Kept in the page's state:** slices survive switching tools and a saved view, if saved views keep tool state today
   (follow what 0135 / 0179 do; no new storage).
6. **Phone** (0179's layout): one slice at a time is fine on a phone, the list scrolls; no overlap with the player's
   controls.
7. **Cost:** several clipping planes on large models – measure the frame time on the made demo's page (4-core web
   machine, software GL) with 0, 1 and 6 slices, and say it in the report.

## Done when

- [x] Slice by face (flat and round) and by X / Y / Z; up to 6 at once; edit (move, turn) and delete each; Flip
- [x] Measuring, part click and fade work through slices onto the kept geometry (tests)
- [x] `tests/test_web_tools.py` (node) covers the slice maths (plane from a pick, kept side, several planes); the page's
      self-test / web checks still pass; a picture of two slices on the test crane's page looked at
- [x] Guide, README.txt, tooltips; function-list entry `changed=`, tour stop and PC-check line updated to Slice
      (`changed=`), version fields as the precheck asks
- [x] Frame-time numbers with 0 / 1 / 6 slices in the report
- [x] Report filled in

## Not in this task

Measuring changes (labels apart, edges – task **0219**, next in this lane); a page that opens on its own by a link or
reads STEP in the browser (ToolBox plan, later); the app's own 3 Looks > Cutaway panel (renamed to Slice by **0220**, owner 18 Nov 23:06 –
use the same words: "Slice", "Add slice", "Slice 1"); `house-planner-dev`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026 (one session, no subagents – a one-file feature with its tests;
independent tester skipped: no Windows-only code).

**What changed:**
- `fr_tools.js`: Cutaway → **Slice** (button, panel, keys help). Add slice, then a click on a face (flat: in its plane;
  round / cone: through its axis, square to the view; a page without face data: the triangle's normal) or X / Y / Z
  through the model's middle. Up to **8** slices, numbered, listed with Edit / Hide·Show / Delete (×), Delete all.
  All slices are clipping planes on every material (the live `Plane` objects); the cap colour works per plane, so
  where two cuts meet it stays right. Editing shows a blue plane with a white arrow (move) and two yellow knobs (turn
  about the first in-plane axis and about the turned second); drags are capture-phase listeners, the view does not
  turn; or type Move (mm) and two Turn angles (°); a size slider for the drawn plane only. Esc order: end a drag →
  end editing → stop adding → (measure / card / fade / tool as before) → close the list (slices stay on).
- **Kept side:** the side **away** from the camera stays (the near side is cut away), as in House Planner – the brief's
  sentence "the side away from the camera is cut away" reads the other way round; keeping the near side would show
  the outside of the near half with its cut face turned away, so I followed House Planner. Flip swaps it. Lead: say
  if the owner wants it the other way (one line in `M.slice.fromPick` / `across`).
- **Key** stays **C**: S is the player's screenshot.
- Clicks of Part info, Measure and Fade go through every slice onto kept geometry; a hit on a part's inside is the
  cut face where the ray **enters** what all planes keep (`M.slice.capAt`) and measures as a flat face of that slice.
- Saved views keep only the camera (0179); the slices are page state and stay on through view switches and tools.
  No new storage.
- `fr_measure.js`: `FRMeasure.slice` – frame, fromPick, across, plane (two turns + move + flip), kept, capAt,
  moveRange (pure maths, node-tested).
- House Planner's slice (public repo, `src/view3d.js`) was read for behaviour and words only: it has no licence file,
  so no code was copied.
- Guide (web page chapter), `web/README.txt`, function `web.tools` (`changed=0.2.169`), tour stop `web3d` text
  (`changed`, crane set `changed`, `tour_versions.json` recorded), PC-check line `web3d.export` text and result
  (the page's self-test now adds 6 slices, checks every material carries all 6, deletes them).

**Tested and measured** (4-core web machine, headless Chromium, SwiftShader):
- `tests/test_web_tools.py` 20 passed: new `test_slice_maths` (node), `test_several_slices_clicks_go_through_and_handles`
  (face slice + axis slice, shaft top cut away never picked, cap pick, measure through slices, knob turn, arrow move,
  camera unchanged, hide, delete, Esc), `test_six_slices_and_the_panel` (C → adding, empty click waits, X button,
  8 slices, 9th refused, list rows, Esc twice); the 0135 tests moved to the slice API.
- Picture: two slices (across Y, across Z turned 20°) on the test crane's exported page – looked at; the cut half and
  the handles show as intended.
- **Frame time**, demo vessel `demo_cable_lay.step` exported as a page (2.12 M triangles, 10.9 MB; the vessel model,
  not the full made demo project with animation), 1280 x 720, software GL, `renderer.render` + 1-pixel read, median of
  4: **0 slices 8.0 s, 1 slice 6.8 s, 6 slices 7.2 s, 0 again 7.7 s** – no measurable cost from the planes on this
  machine (a cut hides pixels, which saves about as much as the planes cost). On the owner's graphics card: expected
  the same, not measured.

**Runs:** 2 – run 44413437042 full: all green but Windows part A (the shortcut check "a second refresh writes nothing": the app's Fresing Render.exe not yet usable at the first refresh – runner timing, 0212's check, not this change); its failed jobs re-run green. Then a docs run for merge main + report.

**Open points / follow-up tasks:**
- The panel (300 px, top left) can cover the slice's handles on a small window; the user turns the view. A later
  polish could move the panel when the handles are under it.
- The app's 3 Looks > Cutaway stays as it is (task 0220 renames it).
