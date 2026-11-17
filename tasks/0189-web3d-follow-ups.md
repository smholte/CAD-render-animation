# 0189 – Fix: web 3D export of the demo too slow + small page faults (bug hunt 6, rows 9, 6, 12, 13, 17)

**Who:** worker · **Status:** running · **Branch:** `task/0189-web3d-follow-ups`
**Started by:** lead chat, 17 Nov 2026 (from bug hunt 6, task 0183) · **Model:** Opus · effort Medium · **Place:** Claude Code on the
web, environment "CAD-render-animation"
**Area:** Web 3D lane (`blender/web3d.py`, `core/web3d.py`, `ui_web3d.py`, the page's `fr_*.js`, their tests)

## Goal

Exporting the demo as a web page takes minutes again (not ~36 min), the panel's time estimate is honest, and the page
has no floating sea cable or covered buttons.

## Background

- **Row 9 (main):** the demo's export takes 2,174 s instead of 96 s – 264 parts get their own marine bake (~7 s each),
  mostly wind-park parts baked again per turbine (CLAMP J-TUBE ×36, TP SLEEVE ×9 …); the panel says "about 34 s".
  Suggested: copies with the same mesh, looks and world height / turn share one bake; the estimate counts the per-part
  bakes (or warns above N parts). 0175 (0.2.143) changed the file sizes since – measure again on main first.
- **Row 6:** vessel motion off (at export, or the visitor's switch) → the laid sea cable dips 0.78 m into the seabed or
  floats 0.85 m above it.
- **Row 12:** phone sideways: the part tools' panel covers the saved-views row (`placePanel` only ≤ 600 px; `layoutCheck`
  leaves out `#fr-tpanel`).
- **Row 13:** an animated page shows a label's live fields at the exported frame ("Lay speed 0.0 m/min").
- **Row 17:** one draw of the Web 3D panel costs ~45–60 ms on the small demo (estimates walk every part).

## Rules for this task

- Each row's proof, numbers and suggested fix are in `tasks/0183-bug-hunt-6.md` (Findings table): read only those rows.
- Every fix gets a test that **failed before** (CLAUDE.md section 6); nothing loosened.
- Normal finish (CLAUDE.md sections 2 and 7): own branch, area tests locally, version raised last, CHANGELOG in plain
  words, green GitHub run, merge, release. Other fix tasks of bug hunt 6 run at the same time: take the next free
  version when you merge.
- A row you cannot reproduce or fix: say so in the report with what you saw; do not guess.

## Done when

- [x] Row 9: the small demo's static export at least 5× faster than the row's 2,174 s on the same machine (say the
      load), same look where copies share a bake (compare pictures); the estimate within ~2× of the measured time.
- [x] Rows 6, 12, 13, 17 each fixed with a test (row 12 in the phone-size layout check).
- [x] The site's models still build (`build_site.py --web-model` keeps the IEA entries in media.json – 0179's note).
- [x] Report below filled in; TASKS.md row moved to Done with the version.

## Not in this task

Spool solids after a scripted export (row 11 is in 0187); the Flex lane's files.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 17 Nov 2026. Branch `task/0189-web3d-follow-ups`, version 0.2.147.

**What changed:**
- **Row 9 – export speed.** Two causes, both fixed in `blender/web3d.py`:
  1. Copies share a marine bake: `own_share_key` (mesh, materials, the object properties those materials read, scale,
     the third row of the world matrix = tilt) + `own_groups` (height within `SHARE_DZ` = 5 mm – the wind park's
     copies differ by 0.1–0.5 mm in height, float32 places km apart). A turn about the vertical and a move across are
     free (the looks read world height, world up in the part's axes, and object coordinates). Shared copies reuse the
     first one's pictures, UVs, looks and glTF mesh. Demo: 69 bakes for 264 parts.
  2. **The bake scene dragged the whole project into every bake** (`_bare`): the copy of the project scene kept the
     compositor's tree (its Render Layers node reads the project scene) and `scene.fresing` (pointers to parts) – each
     `bpy.ops.object.bake` built the depsgraph of all 3,271 objects: 0.6 s per bake op on the small demo, 0.07 s
     without. This also speeds up the tile bakes and the baked light (`lightbake` uses `web3d.Baker`).
  - Estimate: `core.own_estimate(..., bakes=, unique_area=)` adds `OWN_SECONDS_PER_BAKE` (2.0 s) per bake and counts
    only the shared pictures; the panel says "N parts baked (copies share one), bake about … (estimate)". The export
    line says "copies share: N bakes".
- **Row 6 – sea cable without vessel motion.** `web3d.SeaRest` + `web3d_drawn.Drawn.fix`: with the parts read at rest
  and no vessel motion on the page, each point of a SEA cable's tube is blended between its place on the vessel at
  rest (at and above the water) and its world place with the vessel moving (on the seabed), by its height between
  seabed and water – every frame read, and the drawn copy. With vessel motion on the page, the page's settings carry
  `vessel.keep` and `fr_page.js` leaves out the "Vessel motion" switch (the suggested alternative: the cable cannot be
  right for a still vessel when it was solved for a moving one).
- **Row 12 – phone sideways.** `fr_tools.js`: on a short screen the panel's max-height leaves the bottom stack free
  (`--fr-stack`, as the default already did); opening a tool hides the first-visit bubble; `fr_player.js` `layoutCheck`
  lists "part tool panel".
- **Row 13 – live label fields.** `web3d.part_labels(scene, animated=)`: on an animated page the lines with a live
  field are left out (only fields: the card shows the name).
- **Row 17 – panel cost.** `web3d._kept`: the marine and light estimates are kept until a change counter moves
  (depsgraph update, undo, redo, load; persistent handlers, `web3d.register()` in `__init__.py`). `can_export` stays
  exact (the export button uses it; it is not drawn in the panel).
- **Site (0179's note).** `tools/build_site.py` `_tidy(drop=)`: adding or removing a web model removes only the removed
  model's credit when nothing uses it; the IEA 15 MW entries stay.

**Tested and measured** (4-core web machine, small demo `tests/demo_made.py`, static export, Surroundings Project,
Light Live, Marine detail Normal, texture 1024):
- Row 9: main 1,754.5 s (marine bakes 1,515 s, 264 bakes, 802 textures, 16.0 MB; load ~1.8, the export alone) →
  branch **214.5 s** (marine 142 s, 69 bakes, 233 textures, 11.2 MB; load ~1.8): **8.2×**. The row's 2,174 s was on a
  machine under load 8–12. Estimate before: "34 s"; now 164 s for the marine bakes against 142 s measured. Animated
  export with the branch: 701 s (marine 201 s), measured while the area tests ran (load 4–5); main not measured
  animated (the row: +~1,900 s).
- Same look: `test_copies_share_one_marine_bake` – a copy turned and moved, baked alone, has the same colours per 0.5 m
  height band as when it shares the first one's bake (< 0.03); a copy 1 m higher gets its own. No page screenshots of
  the demo were compared.
- Row 17: marine + light estimate + view names per draw on the small demo: 26–46 ms → 0.2–0.3 ms.
- Row 6: test_sea, Rough, built: on the seabed the page's points are within 2 cm of the app's (static) and 6 cm
  (animated, the page's thinning); above the water within 2 cm of the vessel at rest.
- New tests, each failing before: `test_web3d_own_bake.py` (copies share; estimates kept; the bake scene does not
  pull in the project), `test_web3d_sea_vessel_blender.py` (3), `test_web_player.py`
  `test_part_tool_panel_leaves_the_bottom_stack_free` (844×390, 667×375, upright, laptop; Measure and Cutaway),
  `test_web3d_faces_blender.py` `test_live_label_fields_are_left_out_of_an_animated_page`, `test_site.py` (credits
  kept). Locally: all `test_web3d*.py`, `test_web_player.py`, `test_web_tools.py`, `test_site.py`, `test_lightbake*.py`,
  `test_user_guide.py`, `test_updates.py`, `tooltip_report.py --strict` – pass (headless Chromium ran here).
- `make_site_web_models.py` itself was not run (it needs the sources cloned); `build_site.py --web-model` is covered by
  `test_site.py`.
- GitHub: 3 full runs. Run 44153555675 red twice (the rerun of its failed jobs too): Windows part A, PC-check line `web3d.small` – "the page gave no places of its parts (loading)": Edge's virtual-time budget ran out before the packed model was loaded. The `.glb` is byte-identical to main's and the page differs only in four JS lines the `web3d.export` line ran fine in the same Edge; Linux (headless shell and full Chromium, also after `web3d.export` in one real Blender) passes. Task 0187 hit the same failure twice that afternoon. Then 0187 took 0.2.146: merged, renumbered to 0.2.147, run 44164564374 green (Windows included); main fast-forwarded to it.

**Open points / follow-up tasks:**
- The Windows PC-check line `web3d.small` reads the page with Edge's `--virtual-time-budget`; it sometimes dumps the page before the packed model is loaded ("loading"; 0187 and 0189 each twice on 17 Nov). A retry on "loading" or waiting for the state in `read_page` would end the flake (Quality & delivery lane).
- The visitor's Vessel motion switch is left out when a sea cable hangs from the vessel; making the page blend the
  cable itself (the same `SeaRest` rule in `fr_tubes.js`) would let it stay – not done.
- The thrusters, bilge keels, name boards … port/starboard are mirror images: still two bakes each (73 → 69 bakes).
- The demo's three biggest marine parts take 15–26 s each (2048 px pictures); they are most of the 142 s now.
