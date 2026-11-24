# 0294 – Workspaces round 2: Essentials as the start, task workspaces (Sales, Quick render, Animator, Reviewer), favourites on top

**Who:** worker · **Status:** done (0.2.224) · **Branch:**
`task/0294-workspaces-round-2`
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "More Workspaces for the functions. And some very
specified simple workspaces, where a user has to only do very specific task, like a sales person." – "Favorite
workspace on top of the list when you click on the drop down menu to select your workspace." – "On startup if a user
hasn't set their own chosen workspace, there should be one essentials workspace where users first come in to."; owner's
click box 23 Nov: all four task workspaces – Sales, Quick render, Animator, Reviewer) · **Model:** Opus · effort Medium
**Area:** Start & learn lane – `core/workspaces.py` (`BUILTIN`), `blender/workspaces.py`, `blender/ops_workspace.py`, the
Workspace part of the left panel (`ui_left.py`), `core/functions.py` (`workspaces=`, `FAMILY_WORKSPACES`), the settings
file (0283) + Settings > General (`ui_settings.py`), guide, tour stop, PC check, CHANGELOG.
**Not:** `welcome.py` and the first-start set-up (0276 comes after this and uses it), `lock.py`'s Client view rules.

## Background

0062 made the built-in list (All functions, CNC & machining, Offshore & cable laying, Product design & R&D, Client
view, Education & training, Lifting plans, Full access) and own workspaces as files. 0062's lead decision "default
workspace All functions" is changed by the owner: new users start in **Essentials**.

## What to do

1. **Essentials** (new built-in, first in the list): only what a new user needs for a first good picture and a simple
   motion – import, sort into groups + materials, surroundings + light look, camera views, a joint + a pose, Build &
   play, render image / turntable, save. Propose the exact function list in the report (from `functions.py`) and build
   it. It is the workspace of anyone who **has not chosen one** (state how "not chosen" is known – a user who already
   works in another workspace keeps it), and the default for new projects until the user picks another (Settings >
   General: "Workspace for new projects").
2. **Task workspaces** (owner's picks): **Sales** – take a finished project and make outputs: saved scenes, looks /
   paint schemes, surroundings, render picture, turntable, product video, 3D page; the model's structure and motion
   locked (say how it differs from the Client view); **Quick render** – import a STEP, sort + looks, surroundings,
   light, one picture / turntable; **Animator** – joints, cylinders, mechanisms, poses, animation steps, cameras and
   camera paths, labels, render queue, video; **Reviewer** – look at a finished model: saved scenes, slice / cutaway,
   exploded views, labels / notes, measuring (if the app has no measuring in the 3D view, say so as an open point).
   Each with a tooltip saying what it is for.
3. **More workspaces for the functions:** propose 2–3 more from the function families in the report (do not build
   them) – the owner decides.
4. **Favourites on top:** a star on each workspace in the drop-down; starred ones (and the user's "for new projects"
   choice) at the top above a line; kept per user in the settings file.
5. Note for 0276 (first-start set-up, next in the lane): its "Your work" step maps ticks to these; no tick → Essentials
   – write that line into `tasks/0276-first-start-setup.md` under step 2.

## Done when

- [x] Tests: Essentials / the four task workspaces show exactly their functions; a new user lands in Essentials, an
      existing user keeps his; star order kept over a restart; own workspaces still load
- [x] Real-app test of the drop-down with a star; guide (Workspaces) + pictures; tour stop `changed=`; PC check line
      `workspace.essentials`; function entries; full suite + GitHub run green; report; merged, version, release

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 (one session, no subagents).

**What changed:**
- **Essentials** – a new built-in, first in the list. Its functions (63, from `core/functions.py` `TASK_WORKSPACES`):
  the side panel itself, learning, help and settings (`_COMMON`, 43 entries every task workspace keeps), plus
  `import.step`, `import.mesh`, `import.drop`, `import.again`, `structure.tree`, `looks.materials`, `looks.light_look`,
  `scene.surroundings`, `scene.light`, `scene.camera`, `joints.rotate`, `joints.slide`, `joints.hover`, `poses.pose`,
  `animation.add`, `animation.joint_step`, `animation.build`, `scene.still`, `scene.turntable`, `scene.save`.
  "Save" = saved scenes; saving the project is File > Save, always there, and backups (`help.backups`) are in `_COMMON`.
- **How "not chosen" is known:** `prefs.default_workspace` (kept by the settings file, 0283) now defaults to `''` =
  not chosen → new projects start in Essentials (`workspaces.default_name()`). An **existing user** keeps All
  functions: at the start (`workspaces.keep_for_existing_user`, called right after the settings file is read, before
  What's new writes this version into `fresing_start.json`), a user whose `last_run` is older than
  `W.START_SINCE` (0.2.224) and who has nothing chosen gets "All functions" written down – once; a choice is never
  changed. A user of a version before 0.2.155 (no start file) counts as new. Projects keep their own workspace.
  Settings > General shows "Essentials (not chosen yet)".
- **Task workspaces** as lists of functions (`TASK_WORKSPACES`; a function built later adds itself with
  `workspaces=("sales", …)`), each with a tooltip: **Sales** (73) – saved scenes, looks, paint schemes, logos,
  surroundings, weather, props, camera, blur, picture, shapes, turntable, product video, Build & play, video finishing,
  queue (incl. every paint scheme), 3D page. **How Sales differs from the Client view:** Sales is **not locked** – looks,
  scenes and outputs can still be changed; import, structure and motion are only *hidden* (another workspace shows them
  again). The Client view locks the whole model and refuses every editing button. **Quick render** (59), **Animator**
  (83), **Reviewer** (55: saved scenes, slice, X-ray, poses + exploded view, labels, visibility sets, Build & play, clash
  check, camera, picture).
- **Favourites on top:** the Workspace row opens `FRESING_MT_workspaces` (instead of the plain enum menu): the workspace
  for new projects ("· new projects") and the starred ones (in the order starred) on top, a line, then the rest; a star
  (`fresing.workspace_star`) on every row. Kept in the settings file (`prefs.workspace_stars`, a JSON list). A renamed
  own workspace keeps its star and its "for new projects" place.
- 0276's brief has the line for its "Your work" step (no tick → Essentials).
- Function entries `panel.essentials`, `panel.task_workspaces`, `panel.workspace_stars` (+ guide anchors), PC check line
  `workspace.essentials`, tour stop `workspace` + crane set `changed=0.2.224`, guide (Workspaces table, Essentials, the
  four task workspaces, the stars, picture `docs/img/workspace_stars.png`), CHANGELOG.
- **Tests keep All functions:** `tests/conftest.py`, `tools/ci_real_app.py`, `tools/ui_screens.py` and
  `tools/guide_screens.py` set `FRESING_WORKSPACE_START=All functions` (the start of a user who has not chosen), so the
  existing tests and pictures start where they always did; `ui_test_workspaces2.py` and `test_workspaces_essentials.py`
  test the real start (Essentials). Blender as a Python module without the app's preferences also starts in All
  functions (no user).

**Tested and measured** (4-core web machine):
- `tests/test_workspaces_essentials.py` (new, 20): each task workspace shows exactly its list, Essentials' and Sales'
  panels, a broken list refused by the precheck, star order + damage, menu order, start choice; in Blender: a new user's
  project in Essentials, a chosen one kept, an existing user moved to All functions once (written to the file), stars
  over a restart (settings file read again) and after an own workspace's rename, the drop-down draws a star per row.
- Real app `ui_test_workspaces2.py` (new, group tour-b): 19/19 in 23 s – a new user in Essentials, the real drop-down
  drawn (Essentials on top, then the stars Reviewer, Sales, a line, the rest), Sales, Use for new projects, the next new
  project in Sales, and **a real restart** (a second app in the same settings folder: stars, choice, list top and the
  first project all kept); everything put back. The star is pressed through its operator as a button would, not by a
  simulated click on its pixel.
- PC check `workspace.essentials` (bpy module): OK, "Essentials 63, Sales 73, Quick render 59, Animator 83, Reviewer 55
  functions"; the user's own choice and stars are put back (checked).
- `test_workspaces.py`, `test_workspaces_independent.py`, `test_functions.py`, `test_settings_store.py`,
  `test_settings_blender.py`, `test_quiet.py`: green after updating the list of built-ins, the allow-list count (+1:
  the star), the 0.2.198 default of `default_workspace` and the Make test for list workspaces. Tooltip check strict: OK.
- GitHub: see the runs below.

**Open points / follow-up tasks:**
- **Measuring in the 3D view:** the app has none (only the 3D page's measure tool, `web.tools`): Reviewer has no
  measuring. A follow-up if the owner wants it.
- **Sales hides, it does not lock** structure and motion: G / R on a part still move it (as in every workspace outside
  the Client view). A real "looks yes, model no" lock needs `lock.py` (not this task's area).
- Panels show whole: Sales shows 6 Animation for its product video (the panel holds all steps), Reviewer shows 4 Motion >
  Poses for the exploded view.
- **Proposed, not built** (owner decides): **Machine builder** (import, structure, place, joints, cylinders, mechanisms,
  way covers, hoses and drag chains, tracks, Set-up window, clash check); **Video producer** (animation steps, camera
  paths, labels, picture cards, music, brand kit, watermark, captions, queue); **Houses** (House from House Planner,
  surroundings, weather and time, light, camera, picture, turntable, 3D page).
- Guide pictures of the side panel were not made again (they show All functions, as before); the new picture is the
  drop-down from the real-app test.

**Owner's check on your PC:**
1. Update to 0.2.224, open the app. The Workspace row (left panel) still says what you had – All functions, unless you
   had chosen another.
2. Click the Workspace row: Essentials is first; every row has a star on the right. Click the star of **Sales**: it
   jumps to the top, above a line. Close and start the app again: Sales is still on top.
3. Pick **Essentials**: the side panel shows only import, looks, scene, camera, motion basics, animation and render.
