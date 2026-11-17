# 0197 – Study: the side panel as it is now – improvement list, workspace map, model-lock levels (pre-study for 0062)

**Who:** worker · **Status:** done 17 Nov 2026 · **Branch:** `task/0197-panel-survey` (or the web session's own name)
**Started by:** lead chat, 17 Nov 2026 (owner agreed 22:00: take 0062's one mid-task stop out of 0062, so it runs
straight through) · **Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment
"CAD-render-animation"
**Area:** findings only: a report, a picture page and small screenshots under `tasks/`. **No change to the app**, no
version, no test run. Does not count as a code task (it may run beside the four code tasks).

## Goal

The owner picks the side-panel improvements of 0062 (point 5) and the strictness of the Client view lock **before**
0062 starts, from one clear page with readable screenshots. 0062 (Fable · High) then builds without stopping.

## Background

- Read `tasks/0062-ui-clean-up.md` whole (owner's points 1–5, the workspaces note, the highlight note) – that is what
  this study prepares. Do not build any of it.
- The panels: `fresing_render/blender/ui*.py` (layout rules at the top of `ui.py`), the function list
  `fresing_render/core/functions.py` (family / panel / fold per function, task 0124).
- Screenshots: `tools/ui_screens.py` (docstring), `tools/guide_screens.py` for whole-window shots; settings folder via
  `tools/web_install_app.py` (CLAUDE.md section 4). Use the test crane and other test models in
  `fresing_render/data/`; the cable-lay demo only where a panel needs it (sea, cables, spools, people). **Never the
  Fresing 400** (CLAUDE.md section 6).
- **Readable pictures (owner 17 Nov):** the 0185 page shot the whole window at UI scale 0.7 and the owner could not
  read it. Shoot at **Resolution Scale 1.0 or more**, crop **per panel**, and show them at their own size (no
  shrinking); a whole-window shot only to show where things are.
- **Panel draw cost: not here** – study 0195 (running) measures it.

## What to deliver (report + page)

1. **Panel inventory** – every section and sub-panel (and its folds) as on `main` now: name, where, family and
   function ids from `functions.py`, how often a typical project uses it (CNC / offshore / product shot), and any
   function on screen that `functions.py` does not name.
2. **Workspace map (draft)** – a table: each function family × the owner's workspaces (CNC & machining, Offshore &
   cable laying, Product design & R&D, Client view, Education & training, Full access; Lifting plans as "comes with
   the Lifting lane"). Mark the doubtful cells and say why. 0062 takes it as its starting point.
3. **The point-5 improvement list** – numbered, each with: the panel, what changes, why (what is unclear or crowded
   now), a small before screenshot, effort S / M / L, risk (what could break: real-app tests clicking fixed spots, guide
   pictures). Cover at least: long sections split or moved into folds, the same words for the same things everywhere
   (list the pairs found), rarely used settings in "More", sub-panel order, the main button per section (`primary()`),
   separation between sections and steps (a proposed "separation" rule for `ui.py`), icons, a short "what's next" hint
   at the top of a new project. Mark your **recommended** picks (★) and keep the list to what is worth doing –
   about 10–20 items.
4. **Client view lock – 2 or 3 levels**, e.g. (a) view only: no move / delete / re-mesh, every Fresing editing panel
   hidden; (b) also Blender's own edits blocked (transform tools, Delete, Edit Mode); (c) also a password or a file
   flag to unlock. Per level: what it blocks, how (operator polls, `lock_location`…, a load handler, keymap), what
   still gets through, cost. Recommend one.
5. **Blender's own "workspaces" tabs** (top bar) vs the app's word "Workspace": what the app template shows today, and
   2–3 options (hide the tabs, rename ours to e.g. "Work set", keep both). Recommend one.
6. **Anything else 0062 must know**: panels that already break the layout rules, labels cut off at the default
   width, real-app tests and guide pictures that depend on today's layout (list the files).

Put items 2–5 also on one **picture page** `tasks/0197_page/index.html` (plain HTML, no external links; screenshots
next to each item, a tick box per item and a **Copy** button that copies one line like
`0197 picks: 1, 3, 4, 7 · lock b · word: Work set` for the owner to paste to the lead). The lead publishes the page as
a private artifact.

## Done when

- [ ] Report below filled in with items 1–6; page `tasks/0197_page/` with readable per-panel screenshots.
- [ ] Pictures only of test models / the invented demo; nothing of the owner's.
- [ ] Report, page and pictures pushed to `main` (only `tasks/` files: no test run starts) and `TASKS.md` row set to
      done; tell the owner in one line that the lead publishes the page.

## Not in this task

Any change to the app or its tests; panel draw cost (0195); the highlight looks (settled in 0062's brief); the usage
tracker (0181).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Sonnet), 17 Nov 2026. Branch: the session's own (`claude/nice-heisenberg-tjogio`), merged to `main` with `tasks/` files only.

**What changed:** only this file, `tasks/0197_page/` (`index.html` + 12 screenshots in `img/`) and the `TASKS.md` row. No app code, no version, no test run. The lead publishes `tasks/0197_page/index.html` as a private artifact (it needs its `img/` folder next to it; no external links).

### 1 · Panel inventory (main, version 0.2.147)

Usage: **C** = CNC project, **O** = offshore / cable laying, **P** = product shot. ●●● = every project, ● = often, ○ = rarely, – = never (my judgement from the demo and test models, not measured). Function ids from `core/functions.py`.

| Section / sub-panel (folds) | Family · function ids | C | O | P |
|---|---|---|---|---|
| **Test tour** (only in a tour project) | help · help.tour | – | – | – |
| **1 Import** (fold More: cache) | import · import.step, .mesh, .update, .two_copies | ●●● | ●●● | ●●● |
| **2 Structure** | import · structure.tree | ●● | ●● | ●● |
| – Clean-up | import · structure.cleanup | ● | ● | ● |
| – Visibility sets | import · structure.visibility | ○ | ○ | ● |
| **3 Looks** (fold Manage rule sets) | looks · looks.materials, .marine, .rule_sets | ●●● | ●●● | ●●● |
| – Paint faces | looks.faces | ○ | ○ | ● |
| – Find & sort parts | looks.find | ● | ● | ● |
| – Sorting rules | looks.rules | ○ | ○ | ○ |
| – Paint schemes & templates | looks.schemes | ○ | ○ | ● |
| – Cutaway (ui_section.py) | looks.cutaway | ● | ○ | ● |
| – Logos & stickers (fold Library) | looks.decals | ○ | ○ | ● |
| – X-ray look (ui_fade.py) | looks.xray | ○ | ○ | ● |
| **4 Motion** | motion · joints.rotate, .stack, .hover, .couplings | ●●● | ●●● | ● |
| – Cylinders | machines.cylinder | ○ | ● | ○ |
| – Mechanisms | machines.mechanism | ○ | ○ | ○ |
| – Poses & exploded views | motion · poses.pose, .explode | ○ | ○ | ●● |
| – Hoses and drag chains | machines.hoses, .chains | ○ | ● | ○ |
| – Cables and paths (fold sea) | offshore.cables, .served_cable, .moving_cable, .swivel, .sea_cable, .settle | – | ●●● | – |
| – Drums and carousels | offshore.spool | – | ● | – |
| – Tracks and belts | machines.tracks | – | ○ | ○ |
| – Way covers | machines.waycover, .waycover_two | ● | – | – |
| – CNC machine (folds Machine, Air blast) | cnc.machine, .acceleration, .air | ●●● | – | – |
| – – Rotary axes · Tools · Tool changes (fold Operator) · Coolant | cnc.rotary4/5, .tools, .toolchange_*, .atc, .doublearm, .coolant | ● | – | – |
| – Milling | milling.cut, .cut_look, .marks, .fast_map | ●● | – | – |
| – – Chips · Make a toolpath | milling.chips, .toolpath | ● | – | – |
| **5 Scene & Render** | scene · looks.light_look, scene.surroundings, .light, .sea_ground | ●●● | ●●● | ●●● |
| – Camera | scene.camera, .blur | ●●● | ●●● | ●●● |
| – Image size & render (fold Files & graphics card) | scene.still, .shapes | ●●● | ●●● | ●●● |
| – Saved scenes (defined in ui_motion.py) | scene.save | ● | ● | ●● |
| – Brand kit & logo | animation.brand | ○ | ○ | ● |
| – Labels (ui_callouts.py) | animation.labels | ● | ● | ● |
| – Props for scale | scene.props, .props_detail | ○ | ● | ● |
| – Turntable video | scene.turntable | ○ | ○ | ●● |
| – Vessel motion · Vessel at work (fold Thrusters) | offshore.vessel_motion, .vessel_work, .thrusters | – | ●● | – |
| – Watermark | animation.watermark | ○ | ○ | ● |
| – Weather & time (fold Work lights) | scene.weather, .start_scene_save, .night | ○ | ●● | ○ |
| – Web 3D model (folds Surroundings, Light, On the page) | web.* (10) | ○ | ○ | ● |
| – House from House Planner (only with a house) | house.import | – | – | – |
| **6 Animation** (fold Make a product video) | animation.add, .joint_step, .build, .motor, .camera_path, .fade, .sequence, .back_to_cad, .weather_step, .vessel_step, cnc.gcode, animation.product_video | ●●● | ●●● | ●● |
| – Pictures · Music (ui_callouts.py) | animation.cards, .music | ○ | ○ | ● |
| – Clash check | animation.clash | ● | ●● | ○ |
| – Finishing | animation.finishing | ○ | ○ | ● |
| – People | animation.people | ○ | ● | ○ |
| – Trail lines | animation.trails | ○ | ● | ○ |
| **7 Render queue** (fold Every paint scheme) | queue.still, .video, .time_test, .start_later, .schemes | ●● | ●● | ●● |
| Help menu / File > Import (not in the panel) | help.updates, .pc_check, .tour, .demo | – | – | – |

About 36 sub-panels and 13 folds under 7 sections; 113 functions in `functions.py`. **On screen but not named in `functions.py` (all 54 panels are named, but these functions are not separate entries):** Looks > Manage rule sets management (Copy / New / Rename / Delete inside `looks.rule_sets`, one entry for five buttons); Import > Clear import cache; Structure's lock / zoom-to buttons and the per-part 'Locked in place' toggle (`structure.tree` only); Motion > 'Everything back to CAD position' and 'Show joint arrows'; Vessel at work's thrusters share one entry; Web 3D's 'Export…' is one of ten. None of this blocks 0062: the families work; per-function workspace fields should be added where a panel mixes audiences (see map notes).

### 2 · Workspace map (draft)

On the page (`tasks/0197_page/index.html`, section 2) with the doubtful cells marked. Main findings: (a) the **13 families are too coarse** – section 5 mixes the sea ground (Offshore), studio light (Product) and workshop surroundings (CNC), and section 6 mixes sequence / explode (Product) with video finishing (all) – so the workspace field must be **per function**, as the brief already says, plus a few new function entries (sea ground, studio light, workshop surroundings are one entry `scene.surroundings` today); (b) **Client view** needs a function-level pick, not a family one (saved views, turntable, render, web 3D model; no rules, no paint faces); (c) doubtful: hoses and tracks in Product design, way covers in Offshore, the web 3D model in Client view, Clash check in Product design, Education's use of joints and CNC.

### 3 · Point-5 list

14 items with before pictures, effort and risk are on the page (section 1); ★ = recommended: **1, 2, 3, 4, 6, 7, 8, 9, 10, 14**. Not recommended: 5 (split section 5: ~230 text references to section numbers change), 11, 12, 13 (small, can wait). Word pairs found (item 6): Remove / Delete / Clear (6 + 3 + 2 buttons); Show in folder (3) / Show the folder / Open the logos folder; Add (21) / Make (4) / Use as (3); Build animation / Build & play; Back to CAD / Back to normal / Back to the rules / Defaults; Find (3) / Search; Set-up / Set up. Icons: the info icon is drawn 100 times and the error icon 78 times in `ui*.py`.

### 4 · Client view lock

Three levels on the page (section 3). **Recommended: (b)** – Fresing editing operators refused by one wrapper round the ~320 `fresing.*` operators, parts `hide_select` + `lock_*` (both already used by the app), Delete / Edit Mode / Outliner blocked, undone by switching to Full access. Facts found: the app already locks each part's location / rotation / scale at import (`logic.set_locked`, 'Locked in place'), so (a) alone stops nothing in Blender's own tools; `hide_select` is used for excluded parts (`logic.py`). A password (c) is only an accident guard: Blender is open source.

### 5 · Blender's 'workspaces' tabs

Measured in the real app on the web machine (Blender 5.2.3, template "Fresing Render"): **11 Blender tabs are present** (Animation, Compositing, Geometry Nodes, Layout, Modeling, Rendering, Scripting, Sculpting, Shading, Texture Paint, UV Editing), the first window has Properties, Outliner, Dope Sheet and 3D view; no Fresing code touches workspaces (`grep` finds none). Options on the page (section 4); **recommended: keep 'Workspace' and hide Blender's tabs in every workspace except Full access** (a load handler removes the unused ones; Full access brings them back).

### 6 · Other things 0062 must know

- **Labels cut off at the default width** (side panel 292 px at scale 1.0, 436 px at 1.5): see item 7.
- **Layout-rule breakers:** a state in every sub-panel header is only met by 7 sub-panels (item 14); the 'one blue button' idea (item 8); many hints look like alerts (item 13). 'More' folds are used well in Import, Image size & render and CNC.
- **Folds in screenshots:** `tools/ui_screens.py` opens every fold (it re-registers panels without `DEFAULT_CLOSED`); in the real app all sub-panels start closed, so a screenshot is the worst case for height. The all-open sidebar is ~11,000 px tall at scale 1.5 (the tool cuts it at the window height: section 5 on needed a copy of the tool that hides sections 1–4 – kept in the session's scratchpad, not committed; idea for 0062: an env variable `UISHOT_HIDE` in `ui_screens.py`).
- **Cross-references:** section numbers are written in text ~230 times (`props.py` 49, `tour.py` 73, `ui_gcode.py` 12, `ui_motion.py` 10 …); moving a sub-panel (items 3, 4) needs them all checked – a table-driven helper would stop this.
- **Depends on today's layout:** real-app tests `tools/ui_test_*.py` (19 files: app, callouts, clash, cylinder, decals, doublearm, faces, flex, gcode, linkage, milling, paths, spool, studio, surroundings, tour, vessel, video, waycover) click fixed spots; `tools/guide_screens.py` (71 panel references) and `tools/ui_screens.py`; 75 `docs/img/panel_*.png` guide pictures; `tests/test_panels.py`, `test_functions.py`, `test_tour.py` and about 30 more `tests/*.py` that name `FRESING_PT_*` panels; `functions.py` panel / fold fields; `app_template/fresing_render/__init__.py` (`_tidy_screens`).

**Tested and measured:** screenshots of the real app (Blender 5.2.3 under xvfb, web machine with 4 cores, test crane `test_crane_a.step`, UI scale 1.5, nothing of the owner's). The workspaces count was read from the running app. Usage columns are my judgement, not measured.

**Open points / follow-up tasks:** the owner picks on the page; the lead writes the picks into 0062's brief. Panel draw cost is study 0195. Not covered by pictures: the Test tour panel and the House panel (they only show in a tour / house project), the Lifting panels (not built).
