# 0143 – Web 3D model: under the sea – seabed, the cable in the water, the sea cut-away, the camera under water

**Who:** worker · **Status:** done (0.2.128) · **Branch:**
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

- **Bug hunt 0147 row 11 (added by the lead, 16 Nov):** a saved view below the water (sea page) or below the floor
  (plain page) is pushed up by the `lowest` clamp in `fr_page.js` (~line 1095), so 0128's "Seabed" camera can never be
  shown. With the dive under water this task builds: no clamp while the camera is on a saved view (until the visitor
  drags), and the Seabed view of the offshore turbine page shows the seabed and 0148's cut. Test as the row's proof.
- **0148 (seabed cut) and 0161 (web export fixes) are merged before this starts:** show 0148's soil section and the
  monopile to its toe on the page too (read 0148's report and the sea section of the guide).

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

- [x] The demo's page shows the cut-away, seabed and the cable to its touch-down; headless pictures vs the app at 2
      moments in `tasks/img/0143_*`.
- [x] Tests (box place and clarity read from the project; the switch; no seabed when the project has none); page cost on
      Phone / Balanced in the report.
- [x] Guide, tooltips, function list, PC-check line; GitHub run green; merged; version; short list for the owner.

## Not in this task

Moving cables (0142); the model's own cutaway / section slider (0135).

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 16 Nov 2026.

**What changed:**
- **Export** (`blender/web3d_env.py` `under_block`, `core/web3d_env.py` `under_settings`): on the **Open sea** the page's
  settings get `under` – the seabed's height and depth, the water's clarity (sigma = 3 / clarity) and light, the
  app's water colour, sand colours and ripple numbers, the cut-away box **as the app built it** (the sea object's
  `fr_seacut_*`: placed by the cable or by the panel's numbers), the soil section's depth (0148's `fr_soil_depth`)
  and the seabed's drift aft while a cable pays out (read per frame in `Job._motion`, thinned to the moments a
  straight blend cannot give: `under_motion`). Nothing on the Vessel deck, the Quayside or Surroundings None (old
  pages unchanged). `water_length` / `bed_offset` = the page's formulas in plain Python for the tests.
- **Page** (`fr_page.js`): the seabed (the app's sand, patches and `core.sea.seabed_ripples` drawn as light and shade
  from its exact slope, drifting with the cable), drawn only where it can be seen (round the box, round the camera
  under water; beyond 6 x the clarity nothing is left of it); the sea open inside the box; the box's walls (the bright
  line along their top, following the waves; darker with depth); the soil section (0148: layers sand to clay, wobbling);
  every material fades by the metres of water between it and the camera outside the box – the app's
  `seen = behind x T + colour x (1 - T)` – through three's fog chunks, so no new program when switched; the water's
  colour where nothing is (below the horizon through the walls, all round under water).
- **Camera under water:** the horizon limit goes; under the water the view gets the water's colour and the fade, the
  surface seen from below, the seabed (in the pit: its floor) as the floor 0.4 m under the camera; the switch above /
  below follows the wave at the camera with 4 cm either way (no flicker – tested in 1.5 cm steps).
- **Menu:** "Under the sea" and "Camera under water" (both on). Under the sea off removes the water code from every
  program. **Auto quality** switches Under the sea off once at Phone when the page still cannot keep 27 pictures a
  second (a note says so; not when the visitor chose the items).
- **0147 row 11:** a saved view below the water or the floor is shown where it was saved (no clamp, no horizon limit)
  until the visitor drags; then the limit follows the camera up without a jump. The "At the seabed" view of the demo
  shows the seabed (`tasks/img/0143_demo_at_the_seabed_page.jpg`). The offshore turbine's "Seabed" view of the site is
  the owner's kit page: not re-made here (same code path).
- PC check line `web3d.under`, function entry `web.under`, guide section "Under the sea on the page", the panel's note
  ("the cutaway of parts"). `tools/web3d_env_shot.js` takes `--eval=` and prints the camera and under-the-sea state.

**Tested and measured** (4-core web machine, no graphics card, headless Chromium with SwiftShader):
- `tests/test_web3d_under.py` (12: the block, the water's stretch = `core.sea.seen_through`, drift, items text; in the
  browser: box open from above / closed by the switch (pixel colours), dive + floor stop + no dive, surface crossing
  without flicker, saved views below water and floor (row 11), a sea without seabed as before, the soil pit, Auto at
  Phone); `tests/test_web3d_under_blender.py` (3: box, clarity, seabed and drift equal to the app's on the sea cable
  model; ground; none on the deck / without surroundings).
- **Demo** (invented cable-lay vessel, scaled-down build): export with animation 464 s (3,831 frames), page 44 MB, the
  under block ~1 kB, drift in 9 moments. Pictures app (Cycles 16 samples) vs page at 58 s and 64 s of "Into the sea":
  `tasks/img/0143_demo_into_the_sea_t58.jpg`, `_t64.jpg` – the box, the walls' line, the cable to its touch-down and the
  fade through the walls match; **the page's sand is greyer and darker** (mean RGB at the box's far end: app 105/96/79,
  page 70/77/76; not the shadow). Under water and the soil pit: `tasks/img/0143_page_under_water_and_soil.jpg`.
- **Page cost** (sea cable test page, 480 x 320, pictures a second, 3 runs each in one browser): Phone 3.8 (Under the sea
  on) against 9.6 (a page without it), Balanced 1.5 against 7 looking into the box; looking at the vessel 3.6 / 8 and
  1.9 / 6.6. With Under the sea off the page is as fast as without it. Software drawing only; on a graphics card not
  measured (expected small: a few dozen operations per pixel).
- Local: the files above plus test_web_player, test_web3d_env(_blender), test_web3d_light_page, test_functions; the PC
  check line on the bpy module.

**Open points / follow-up tasks:**
- Sand colour on the page vs the app (above): the page's light makes dark warm colours greyer; worth a look with the
  owner's eyes on a real screen.
- No stones on the page's seabed (the app's Detailed has 420); the ripples are shading, not shape.
- Software drawing: Under the sea halves the pictures a second or worse; the bisection (dome, walls, seabed, fade, the
  sea's underside each alone) found no single cause. Measure on the owner's PC (gear menu shows pictures a second).
- The water's light follows the export, not the page's Sun / time of day slider.
- No test-tour stop (the page is not in the app; as `web.moving`); the PC check line covers it.
