# 0131 – Bug hunt, round 4: everything built since 0118 (findings only, no code changes)

**Who:** worker · **Status:** done – report on its branch · **Branch:** `task/0131-bug-hunt-4` (the report only – **do not push to
`main`**, see step 5)
**Started by:** lead chat, 15 Nov 2026 (owner: "all tasks") · **Lane:** none – reads everything, **changes no app code,
tests or tools**, so it runs next to every lane and starts **no** test run on GitHub
**Model:** **Opus · effort High** · **Place:** Claude Code on the web, environment "CAD-render-animation" (real Blender
at start, CLAUDE.md section 4)

## Goal

A ranked list of real problems in what was built since the third bug hunt (0118, 14 Nov, 0.2.92) – crashes, lost
work, old projects that no longer open, wrong output, slow spots, functions that fight each other – each with proof
and a suggested fix, so the lead can turn them into tasks **before** the owner hits them on his PC.

## Background

- Since 0118: **0.2.93 → 0.2.103** – "Turn it yourself" picker (0111), IEA 15 MW turbine + looks concrete / marine
  growth / run-down streaks (0116), quadrant operations + A&R / tipping wires as app cables + shots 9–12 (0082),
  bug-hunt fixes A/B/C (0119, 0120, 0121 = 0118's rows), mesh import glTF/OBJ/FBX (0117), function list + guide
  anchors (0124), nicer test models (0122), motion extras: blocked ways, riders, stacking, Back to CAD, product-video
  close-ups (0129), quadrant and sea follow-ups: settling, seabed set-down, swivels, free bend (0125), random test
  failures (0127). Each task file has its report and open points: read them first, do not re-report a known open
  point (mention it only if it is worse than the report says).
- Check that **0118's rows really are fixed** (0119–0121, 0117 row 14): one quick repeat of each row's proof.
- Read CLAUDE.md section 8 (Blender's traps found so far) and look for the same kinds of mistakes in the new code.
- **Running at the same time** (their files change tonight – look at them lightly and check each finding there against
  the newest `main` before writing it): **0128** turbine extras + ATC web model (`tools/site_projects/`,
  `site/render_kit/`, `marine_looks.py`, `site/media/`), **0126** CPS run (`demo_model/`, `demo.py`, maybe
  `paths*.py`), **0130** House format 1.0.1 (`house_*`), **0132** Motion follow-ups (`ui_motion.py` joint box,
  `sequence.py`, maybe `clash.py`).

## What to do

1. **Functions together** (the main point), on the generic test models (0122's new ones) and the demo project:
   - **Demo project** with shots 9–12: the quadrant lowered, tipped, let go on the seabed with vessel motion on, a
     weather preset, the cut-away under water, a product video, a web 3D export; save, reopen, Build again – does the
     cable, the D, the swivels, the settled sea cable or the CPS move, double or vanish?
   - **Assembly sequence + riders + Back to CAD** (0129) with a model update, a clash check, the render queue and a
     product video in the same project.
   - **Mesh import** (0117): made-up glTF/OBJ/FBX files only (made in Blender in the scratch folder – never downloaded
     manufacturer models): joints on facetted cylinders, decals, a model update from a changed file, the look "From
     file", web 3D export of a mesh project, a mix of STEP and mesh models in one project.
   - **Turbine** (0116): the stand-in conversion with weather, vessel motion off, clash check, web 3D export.
   - **Scripts off** (as 0118 did): every driver of the new data (A&R/tipping wires, swivels, riders, sequence steps,
     Back to CAD) still moves with "Auto Run Python Scripts" off.
   - **Undo / Ctrl+Z** after the new buttons (mesh import, Back to CAD step, swivel, let go, sequence preview).
   - **Function list** (0124): every entry's button, guide anchor, tour stop and PC-check line really exist and fit.
2. **Old projects:** make projects with **0.2.92, 0.2.95 and 0.2.101** (their tags; joints, a look, a decal, a
   G-code step, a cable with a sea end, a sequence step, a queued job) and open them in the newest `main`: everything
   there, nothing doubled, the queue job still renders.
3. **Slow:** ms per frame change and per redraw on the demo project (shots 9–12 with the sea end and swivels) and on
   the Heavy machine, each new per-frame feature switched on one by one; Make demo's time; the preview plan on a big
   subassembly.
4. **Prove** each finding: a short script or click test (scratch folder **outside** the repository; the few lines
   needed to repeat it go into the report). A finding that cannot be shown is *suspected*, never confirmed.
   Windows-only code: review by reading. Helper agents may read areas in parallel (at most 3, one area each, findings
   only); the main session checks every finding itself.
5. **Report** in this file, one table row per finding, worst first:
   `# · severity (crash / lost work / old project / wrong output / slow / small) · where (file:function) · what
   happens and when · proof (confirmed + how / suspected) · suggested fix in one sentence · lane · model · effort`.
   Then a short list of areas that looked sound. Group small findings (texts, tooltips) in one row.
   **Push the report to the branch `task/0131-bug-hunt-4` only.** The lead brings it to `main` and turns rows into
   tasks. Set the task to "running" in `TASKS.md` on `main` at the start (a TASKS.md-only push starts no run).

## Done when

- [x] Step 1 combinations tried (say which were not and why); 0118's rows re-checked; old projects from 0.2.92,
      0.2.95, 0.2.101 opened; speed measured
- [x] Findings table filled in, worst first, each confirmed with proof or marked suspected; sound areas listed
- [x] No change to app code, tests or tools; the report pushed to `task/0131-bug-hunt-4`

## Not in this task

Fixing anything – even one-line fixes go into the report as a suggested fix. New features, the look of the UI (0062),
render quality judgements. The owner's own files (the repository is public – generic test models only). The Fresing
400 (CLAUDE.md section 6). Nothing from `smholte/house-planner-dev`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Opus, effort High), 15 Nov 2026. Hunted on `main` = d407eed (0.2.103); every
finding was checked again on **0.2.104** (task 0132 merged while this ran): one row (Back to CAD after a hidden Take
apart) was fixed by 0132 and is left out, the rest are still there. **No app code, test or tool changed.** Three helper
agents read one area each (A mesh import, B assembly sequence / Back to CAD / product video, C sea cables / quadrant);
**every row below was run again in the main session** (their scripts, and for C row 3 a real model update instead of
the simulated one). Scratch scripts were outside the repository; the lines that repeat each finding are in the table.

**What was tried**
- **Demo project, full form** (Make demo 530 s with the helpers running at the same time; Build 83–144 s): Build at
  frame 1, at 1803 and at 3206; vessel motion off/on; Grey North Sea and Storm; sea cut-away; product video; web 3D
  export (built: 13 s, 9.4 MB); save, reopen, Build again; Build twice → **rows 1 and 6**. Built at frame 1 the rebuild,
  save/reopen and a second Build are identical (0 differences at 31 frames, all 2,525 objects + every node mesh).
- **Old projects:** the whole test tour (34 / 34 / 36 sets) made with **0.2.92, 0.2.95 and 0.2.101** (their tags,
  Blender as a module), each set opened in 0.2.103, every animation built again, every object's place, hiding and node
  mesh compared at 5 frames: **nothing missing, doubled or erroring**; collections the same length. Only difference: the
  let-go sea cable of "A cable on a moving part" (0.2.95, 0.2.101) – finer drawing (0125's free bend, intended) and
  **row 14**. The 0.2.101 hub's queued still and video **rendered** in 0.2.103 (draft, background queue, both DONE).
- **Assembly sequence + riders + Back to CAD** with a model update (same STEP; crane A → B), clash check, queue set-up,
  product video, save/reopen: rows 8–11, 16(f, g); the rest sound (below).
- **Mesh import:** joints on facetted cylinders, decals, looks, "From file", model updates (renamed / removed / added /
  moved parts, m → mm), a STEP and a mesh model in one project, two copies of one file, web 3D export of STEP + glTF +
  OBJ, odd files (made up with `tools/make_test_mesh.py`'s writer): rows 3, 4, 12, 13, 16(b–e).
- **Turbine** (0116's stand-in, the app project of `test_site_turbine_standin.py`): weather presets, Build, clash check
  **0 rows** (41 s), web 3D export still and animated (32 s, 3.2 MB) – sound. (Its project has no sea: the kit sets it.)
- **Scripts off:** sea project (39 drivers), swivel project (12), sequence + riders + Back to CAD project, the queue copy
  and the product video: no Python driver; real Blender 5.2.3 `-b -Y` against scripts on: identical places and node
  meshes (sequence project all 216 frames; sea / swivel projects). The full demo was not run with `-Y` here (0118 did,
  and the new demo drivers are the swivels' keys and the same kinds of couplings).
- **Undo:** real app (xvfb) for the sequence preview (50 → 80 → undo → redo), Build, Back to CAD step, product video
  (no crash; row 10 shows there too) and for Import mesh model / its model update (clean). Let go and Swivel: `UNDO` on
  the operators, no Python caches in `paths_swivel` / `paths_rollers` (reading; not clicked in the real app).
- **Function list (0124):** `problems()` empty on 0.2.103; every one of the 96 entries' guide anchors lands on the
  section of that function (checked one by one); buttons exist from the version the entry says (only `cnc.tools`
  says 0.2.36 while its button is in 0.2.30 – not worth a row).
- **0118's rows re-checked:** `test_fixes_0120.py`, `test_model_update_cables.py`, `test_motion_fixes.py` (the tests
  written from rows 1–13, 16–18, failing on the old code) – 35 passed; row 4 repeated by hand with riders (0 free moves);
  row 14 (two imports of one file at once) is covered by 0117's own tests. **All fixed.**
- **Speed** (4-core web machine, Blender as a module, no graphics card): demo, built, quiet machine: **42.5 ms per frame
  change** (shots 9–12: 40.7 ms); the app's Python handlers ≈ 0 ms of it (profiled) – the rest is Blender's own
  evaluation (0118 measured 26–34 ms in another session: not proven to be a regression, no row). With the helpers
  running: 52–96 ms; Storm +13–20 ms; sea cut-away no extra. Sea test model built: 3.4–6 ms per frame; not built with
  vessel motion on: 93 ms (the sea cable is solved every frame, as designed). **Heavy machine** (3,000 parts, Draft):
  Assembly sequence on a 272-part module – first preview touch 0.9–1.4 s, then 90–250 ms per slider step, Build 2.7 s,
  frame change 17.7 ms afterwards. Helper B, 600-part machine: whole model 0.7–1.0 s plan, 53–93 ms per step, Build 5 s.

**Findings** (worst first)

| # | Severity | Where | What happens and when | Proof | Suggested fix | Lane | Model | Effort |
|---|---|---|---|---|---|---|---|---|
| 1 | **crash** | `web3d.Baker.__init__` (398: `src.copy()` copies the scene **with its `scene.fresing`**) + `paths._follow` / `_on_depsgraph` (3538–3563) | **Export web 3D model crashes Blender (segfault, unsaved work lost) whenever the project has a moving cable and no built animation** – after Clear keys, after Make a product video (it clears keys), a sequence preview, or before the first Build. The bake scene is a copy whose cable list still points at the real parts; the cables' depsgraph handler runs `_live` for that copy during `bpy.ops.object.bake` ("Object 'FR seabed motion' already in collection" in older versions) and Cycles crashes. Since 0.2.95 (moving cables, 0082). | confirmed: **real app 5.2.3 under xvfb** (`fresing.web3d_export`, EXEC) and as a module: `test_moving.step`, `paths.set_up_moving_model(sc)`, no Build, `web3d.export(sc, path)` → `Segmentation fault` at `web3d.py:423` (`_run`); same on the demo after `animation.clear_keys`; 0.2.95, 0.2.101, 0.2.103, 0.2.104 all crash; with the paths handler removed it exports (13 s) | Every live handler (paths first; flex, vessel, spool, tracks, linkages, section to be safe) skips scenes that are not a real project scene – e.g. a tag on the bake copy (`sc["fr_bake"] = True`) checked in `_follow` – or the Baker empties the copy's `fresing` lists; test: moving cable, not built, export. | web 3D / cable paths | Sonnet | Medium |
| 2 | lost work | `paths.py`: `_CONTACT_FIELDS` (987, no `swivel`), `_write_contact` (1030), `_row_of` (1052), `_merge` (1064); used by `read_cad` (1154) and Add contact's `change()` (2866–2872), `_restore` | A contact's **Swivel** (0125) and its **Let go frame** (0082) are dropped whenever the contact list is rewritten: **model update**, From CAD cable again (also a contact marked user), any Add contact (all *other* contacts lose both), and a *refused* flip/end change (its restore drops every Swivel). The demo's tipping-wire heads would stop following their wires after an update; a let-go sheave holds on again and Build warns. | confirmed: `test_moving.step` + `paths.set_up_moving_model`, Build, then a **real** update to the same file (`import_step(..., update_root=root.name)`, "34 kept") → SHEAVE `let_go_frame` 231 → −1; Build warns "0.47 m too short…", "lifts its end off the seabed", "bends over the end of 'SHEAVE'". Swivel: set `contact.swivel = 'Swivel'`, From CAD cable → `''`; Add contact → SHEAVE 2 `('Luff', 40)` → `('', -1)` | Carry `swivel` and `let_go_frame` in `_row_of` / `_write_contact` / `_merge` and add `swivel` to `_CONTACT_FIELDS`; tests for update, re-read, add, refused flip. | cable paths | Sonnet | Medium |
| 3 | lost work | `reimport.py:match` rule 2 (146: 1:1 name match without a place check); names from `mesh_reader.read_mesh` (1097: `"<name> <k+1>"` for split pieces; 450: `"Node <k+1>"`) | **Mesh model update moves work onto the wrong piece** when a split mesh's generated piece numbers shift (a piece removed, or one added earlier in the file): names match the wrong shapes before rule 4 (same shape, same place) gets its turn. A piece removed → the decal and group look of a *kept* block are dropped and the report names the wrong part missing; a piece added first → the joint "Shaft turn" now moves the plate (12 polys) instead of the shaft, the look lands on another block, "1 new, 0 missing". | confirmed: a glTF of one mesh split into 5 loose pieces ("WELDMENT 1–5"), joint on the shaft, decal + group look on the block at x 0.1; update with block 1 removed → "missing ['WELDMENT 5']", decal gone; update with a small piece first → joint moves 12 polys | Mark reader-made names (piece numbers, "Node k") on the node and match those by shape and place (rule 4) before names; at least require the place to agree for a generated name. | import | Opus | Medium |
| 4 | lost work | `mesh_import._make_material` (89: no `use_fake_user`; the part refers to it only by name `fr_file_material`) | A mesh model's **own material is lost at save** when no part shows it: a group switched away from "From file", or a mesh part that joined a group an earlier STEP model made. After reopening, "From file" does nothing (the parts keep the group colour); the file's colours and pictures are gone for good (also for paint schemes and the queue's every-scheme jobs). | confirmed: mesh crane, group look → Yellow paint ("FR file Yellow paint users 0"), save, reopen → 3 of 5 file materials left, back to "From file" → still "FR Yellow paint" | `use_fake_user = True` on file materials (taken off when the model is removed or updated away), or keep a real ID reference. | import | Sonnet | Low |
| 5 | lost work | `joints.rename` (1596) vs `FRCableContact.swivel`, `paths_swivel.after_clear` / `paths_rollers.after_clear` (`fr_swivel_was` / `fr_roller_was` JSON) | Renaming a joint is not carried into the new cable data: (a) the swivel's **leader renamed while built** → at Clear keys the coupling is not put back (follows `''`); (b) the **swivel joint renamed** → `contact.swivel` points at the old name and the head stops following its wire without a word. The older `contact.joint` / `item.joint` fields look the same (reading). | confirmed: swivel set-up of `test_paths_swivel.py`, built, `joints.rename` of the leader, Clear keys → follows `''` (was 'Lead'); rename of the swivel → pad moved 2 m: swivel value 0.0, sheave tilted 26.1° off its wire | `joints.rename` also updates `contact.swivel`, `contact.joint`, `item.joint` and the two `…_was` JSONs (or clears keys first when built). | cable paths | Sonnet | Medium |
| 6 | wrong output | demo: the second end and its CPS (`paths` sea end / riders / let go read at Build) | **The demo's Build depends on the frame shown when Build is pressed.** At frame 1 it gives exactly what Make demo saved; at frame 1803 24 objects differ; at the last frame (3206) the second end and its CPS / bend restrictors lie **up to 73 m** away from where Make demo put them (on the seabed 60–70 m aft from shot 9 on) and Build warns "**98 m** more cable than the water is deep… at frame 1651" (made: 0.13 m at frame 1810). The owner scrubs and presses Build → shots 9–12 are wrong until he Builds at frame 1. Also with vessel motion off; **not** on the small `test_moving` model (frame 1 / 240 / 289: identical), so it is in what the demo's second end adds (excluded parts until shot 9, CPS rider, quadrant, let go). | confirmed: Make demo (full), open, `sc.frame_set(f)`, `animation.bake(sc, s.animations[s.anim_baked])`, compare node meshes of `CABLE END.001`, `CPS …`, `PULL HEAD.005`: f = 1 → 0 differences; f = 3206 → 72–120 rows, 60–73 m | Build reads everything at the animation's first frame (or inside a fixed start pose), never at the frame shown; find what the second end / CPS reads in the pose shown; test: Build at first and last frame identical on the demo. | cable paths / demo | Opus | High |
| 7 | wrong output | `vessel_motion.hoses_follow` (542: "Cables … need nothing"), `flex.motion_changed` (1714: returns without hoses), `paths_sea.weather_changed` (789), `paths._rebuild` (1851) | A **built sea cable is not worked out again when vessel motion or the vessel speed changes after Build** (sea state, vessel panel, Weather & time speed / preset): the seabed moves the new way at once, the cable keeps the old shapes; the animation still counts as built, nothing says "Build again". ROUGH → CALM after Build: the cable end 1.40 m above to 1.03 m under the seabed (+0.024 m before). Vessel speed 3 → 6 kn: the end that should lie still slides 17.8 m along the seabed. (0121 row 5 fixed this for hoses only; hoses also miss the Sea state / Bow / preset routes, which reach `vessel_motion.sync` through `world.apply` without `hoses_follow` – reading.) | confirmed: `test_moving.step` sea set-up, built, Weather & time vessel speed 3 → 6 kn → end in seabed coordinates at f1/100/200/end −61.29 → −61.29/−55.18/−49.0/−43.51 | After such a change, bake the sea cables again (as `flex.motion_changed` does) or take the Build off with a note; route every vessel/sea change through one function. | cable paths / vessel motion | Opus | Medium |
| 8 | wrong output | `blender/sequence.py:bake_step` (`k.home.setdefault` keeps the **first** Take apart's start) | **Nested sequences jump:** Take apart SLIDE.UNIT, Take apart the whole model, Put together the whole model, Put together SLIDE.UNIT → at the 3rd step's first frame parts jump 8–233 mm in one frame, at the 4th every SLIDE.UNIT part jumps 120 mm out again; in between they fly through the portal frame (clash rows PORTAL FRAME × CARRIAGE 16.2 mm, × GRIPPER BLOCK 10.8 mm on 0.2.104 – 0132 now leaves the jumps themselves out of the clash check, so only these real ones show). No Build warning. | confirmed on 0.2.104: `test_sequence_frame.step`, the four steps above → "frame 106 moved > 5 mm in one frame: CARRIAGE 233…", "frame 163 … 120 each", 3 clash rows | Keep a stack of homes per part (push at Take apart, pop at Put together) and plan a Put together from where the parts are when it starts. | assembly sequence | Opus | Medium |
| 9 | wrong output | `core/sequence.py:order` (`out_key` 148–156: sort by `-key`, no tolerance) | Two parts whose near ends are flush **swap places in the order by float32 noise**: the first Build ranks them one way, a second Build, a Build after reopening and the **queue's own Build** the other way – the queued video differs by 80 mm from what the owner checked (also the preview after an undo). | confirmed on 0.2.104: `test_sequence_frame.step`, Take apart; COVER and CARRIAGE near ends −0.0500000007 / −0.0500000045 m → ranks 4/5, then 5/4 | Round `out_key` to 1e-6 m (as `_plan_key` compares places) so ties fall to the tree order. | assembly sequence | Sonnet | Low |
| 10 | wrong output | `product_video.make` (428–429 end the preview only when keys exist; `save_shot` 463) | **Make a product video while a sequence Preview is above 0 %** stores the preview's places in the video's start scene: every Build of the video starts with parts half out (5 parts, 41–120 mm) until it is made again; the preview stays on. Save pose / Save scene the same (5 free moves). | confirmed on 0.2.104: `test_sequence_frame.step`, preview 60 %, `product_video.make` → start shot "free moves stored 5", frame 1: GRIPPER BLOCK 117.1, SPLIT PIN 120.0 mm | `sequence.end_preview(scene)` at the top of `make` (and before saving a pose or scene). | assembly sequence | Sonnet | Low |
| 11 | wrong output | `blender/sequence.py:movers` (90–97: no visibility check), `_visibility` (410–416) | A part **hidden with the eye in 2 Structure still takes part** in a sequence (counted, its own time slot, blocks others); with **Put together + At the end Hide or Fade it becomes visible** from its come-in frame to the end (since 0100). | confirmed on 0.2.104: SPINDLE.UNIT, COVER hidden, Put together + HIDE/FADE → it renders on 101 of 163 frames, count 12 incl. it | Leave parts hidden in Structure out of the movers (or never key them visible). | assembly sequence | Sonnet | Low |
| 12 | wrong output | `marine_looks.sync` is called only from `materials.build_nodes` (`surroundings.ensure` / `_build_sea` never call it) | The **marine growth band does not follow the sea**: pick the growth look, then add the sea, change Water level or switch to Vessel deck → the waterline stays where it was when the look was built (no sea: 0). Water level 3 m → growth drawn 3 m under the water; Deck (sea at −3 m) → growth at deck height. Stays wrong in renders and the queue (the material is not built again). | confirmed: crane, background SEA, `materials.ensure_material("Hull", "paint_marine_growth", "RAL 1023")`, `s.water_level = 3.0` → `sea_z` 3.0, `waterline` 0.0; DECK → sea −3.0, waterline 0.0 | Call `marine_looks.sync(scene)` at the end of `surroundings.ensure` (and wherever the sea is built or moved). | looks | Sonnet | Low |
| 13 | wrong output | `importer/runner.cache_key` | The mesh cache key covers only the main file: after a change to the **MTL** (colour), a texture or a .gltf's external .bin, both a re-import and **Update to new revision** use the old cache ("from cache: file unchanged", "4 kept, 0 new"): the change never arrives. | confirmed: `test_mesh_parts.obj`, MTL Kd → 1 0 0, re-import and update → still (0.05, 0.2, 0.6) | Add size + mtime of the side files the reader used (mtllib, image and buffer URIs, listed in tree.json) to the validity check. | import | Sonnet | Low |
| 14 | old project | `props.FRCable.sea_settle` (default 4.0, no versioning) | **Let-go sea cables of 0.2.95–0.2.102 projects now sink onto the seabed over 4 s** at the next Build (the new default applies to old data), where they stayed put before; CHANGELOG 0.2.103 says "0 = as before" but not that old projects change. | confirmed: tour set "A cable on a moving part" made with 0.2.95 and 0.2.101, opened in 0.2.103: `sea_settle` 4.0, after Build at frame 289 the cable's highest point −2.11 m → −9.85 m (settled) | A `load_post` versioning step: cables saved before 0.2.103 with a let go get `sea_settle = 0` (or say it in the changelog). | cable paths | Sonnet | Low |
| 15 | slow | `reimport._carry_over` (489: `bpy.data.meshes.remove(me)` in a loop; 486 `batch_remove`) | A **mesh model update is quadratic** in its unique meshes (mesh files rarely share them): same file, new date: 750 parts 4.5 s, 1,500 parts 12.1 s (helper: 3,000 parts 60 s; renamed 79 s; the import itself 12 s). | confirmed: glTF of N boxes, `import_mesh(..., update_root=…)` with a new mtime: 750 → 4.5 s, 1,500 → 12.1 s | Remove the old meshes in one `bpy.data.batch_remove([...])`; measure the objects' `batch_remove` again at 3,000. | import | Sonnet | Low |
| 16 | small | several | (a) `paths.ramp_steps` (2385) reads the slope after a change as `v[k+1]−v[k]`: changes 1–2 frames apart over-estimate the step (numeric case: 0.475 m off the tight payout). (b) `joints.axis_from_hit` (1647) scales the radius by the object's local X: a cylinder whose axis is its own X and is stretched along it shows **Ø300 for a Ø100 rod** (axis right). (c) `hover._MESH` / `_FACE` keyed by mesh **name** + counts: after two updates a mesh gets its old name back and the hover draws the old points (m → mm: 1000× too big; STEP too). (d) `mesh_reader._text_lines` (570) decodes UTF-8 with "replace": a cp1252 OBJ/MTL shows "Pl�t" and reports `stål.png` missing. (e) `mesh_reader._read_gltf` (432) takes scene 0 when `"scene"` is missing: an empty scene 0 → "no faces to show". (f) A sequence step's **trail line of a part removed by an update** warns at every Build "its part is gone (pick it again…)" – advice that does not apply (`trails.py` 186, `sequence.tidy_trails`). (g) `sequence._plan_key` (782–790) keys on `b.as_pointer()` (CLAUDE.md section 8) and leaves out the parts outside the subassembly: hiding the portal frame between two slider steps keeps the old plan (preview sideways, Build up). | (a) plain-Python numbers; (b)–(g) confirmed by scripts (b: stretched rod in a glTF; c: OBJ m then mm twice; d: latin-1 OBJ; e: two scenes, no `"scene"`; f: crane A → B with a sequence + trails; g: `test_sequence_frame.step`, frame hidden at 100 % preview → "preview == build: False") | (a) merge changes closer than the ramp; (b) scale by `mw.to_3x3() @ u` with `u` across the axis; (c) `hover.clear()` after a build/update or key on content; (d) fall back to cp1252; (e) first scene with nodes; (f) `tidy_trails` drops step-owned trails whose part is gone, silently; (g) key on `seq_id` + obstacles' names, visibility, places | cable paths / import / motion | Sonnet | Low |

**Areas that looked sound**
- Old projects of 0.2.92 / 0.2.95 / 0.2.101: every tour set opens, builds and keeps joints, looks, decals, G-code steps,
  cables with a sea end, sequence steps, weather, vessel motion, queue jobs (row 14 the only change); old queue jobs
  render.
- Demo built at frame 1: rebuild, save / reopen / Build and a second Build identical; web 3D export of the built demo;
  weather presets and the cut-away on it; product video made on it.
- Sea cables: let go + Settles in + rollers the cable leaves + swivel + vessel motion + weather, Build, save, reopen,
  Build again identical (≤ 4e-6 m); Clear keys puts every roller and swivel coupling back; two Builds in a row harmless;
  a model update while built brings put-aside couplings back; Settles in longer than the animation, let go at the last
  frame / after the end, a cable hidden all the time: clean.
- Assembly sequence: model update (same STEP and crane A → B: Back to CAD ends on the new CAD place, the new part joins
  the step, free moves carried), save / reopen identical before building, the product video after an update, the queue
  copy, Back to CAD first / twice / of a subassembly, a rider whose carrier a Hide step hides, preview 100 % then Build;
  real-app undo / redo of preview, Build, Back to CAD and product video (no crash).
- Mesh import: joints on facetted rings / pins / mirrored wheels, decals, a full A → C update (renamed, removed, added,
  moved – report right), STEP + mesh in one project with each updated in turn, two copies of one file, undo / redo of
  import and update in real Blender, web 3D export of STEP + glTF + OBJ, odd OBJ/glTF files (partial vt/vn, NaN corners,
  1e30, KHR_materials_*, URIs with spaces and accents, mirrored roots), units Auto at 499 / 500; import speed linear
  (3,000 meshes 12.4 s, 3,000 instances 2.7 s).
- Turbine stand-in: weather, clash check 0 rows, web 3D export still and animated.
- Scripts off and 0118's rows: above. Python handlers per frame on the built demo ≈ 0 ms.

**Not tried:** the full demo's clash check (`test_demo_clash.py` runs it at every push), the demo with `-Y`, a real queue
render of the demo, Let go / Swivel clicked in the real app (operators read), Thor's block (needs the kit's sources),
FBX beyond 0117's own tests.

**Open points / follow-up tasks:** the rows above. Row 1 first (a crash with lost work, one handler guard); rows 2–5
lose the owner's work; row 6 makes the demo's shots 9–12 wrong after an ordinary Build (cause not yet pinned down –
Opus High). Leftover: none in the repository; scratch worktrees of the three old tags and of 0.2.104 removed.
