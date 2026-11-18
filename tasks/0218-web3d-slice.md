# 0218 – Web 3D page: Slice instead of Cutaway – any face, several slices, edit and delete

**Who:** worker · **Status:** open – can start (Web 3D lane) · **Branch:** `task/0218-web3d-slice`
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

- [ ] Slice by face (flat and round) and by X / Y / Z; up to 6 at once; edit (move, turn) and delete each; Flip
- [ ] Measuring, part click and fade work through slices onto the kept geometry (tests)
- [ ] `tests/test_web_tools.py` (node) covers the slice maths (plane from a pick, kept side, several planes); the page's
      self-test / web checks still pass; a picture of two slices on the test crane's page looked at
- [ ] Guide, README.txt, tooltips; function-list entry `changed=`, tour stop and PC-check line updated to Slice
      (`changed=`), version fields as the precheck asks
- [ ] Frame-time numbers with 0 / 1 / 6 slices in the report
- [ ] Report filled in

## Not in this task

Measuring changes (labels apart, edges – task **0219**, next in this lane); a page that opens on its own by a link or
reads STEP in the browser (ToolBox plan, later); the app's own 3 Looks > Cutaway panel (owner decides whether it is
renamed too); `house-planner-dev`.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
