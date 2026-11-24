# 0276 – First-start set-up: one window that walks a new user through the app's set-up (replaces Blender's own)

**Who:** worker · **Status:** running · **Branch:** `claude/cad-render-animation-0276-loioex` (the web session's branch)
progress window) · **Branch:** `task/0276-first-start-setup`
**Started by:** lead, 21 Nov 2026 (owner 17:45: "maybe there should be a set-up menu when a user opens the app for the
first time?"; owner's picks 17:50: **full set-up** – **replace Blender's own first-start window**) ·
**Model:** Opus · effort Medium
**Area:** Start & learn lane – `blender/welcome.py` (the welcome becomes step 1 of the set-up; `_quick_setup_open`,
`_draw_quick_setup`), `core/start.py` (the start file: set-up done / skipped / version), a **new**
`blender/first_setup.py` (the window and its steps), `app_template/` (Blender's quick set-up skipped – see 1),
reads 0271's Settings pages and 0272's `core/locations.py`, starts 0275's progress window and the PC check's Quick
mode (`pccheck/`, read only); their tests, a real-app test, guide, `docs/COMPANY-USE.md` (what IT can pre-set), CHANGELOG.
**Also (owner 17:53):** step 6 offers **Save my set-up as a file…** (0272) for a user who wants to copy it to a
colleague. **Not:** new settings – every choice here is one that already exists in the Settings window (0271 / 0272), the set-up
only asks them in order.

## Goal

The first time someone starts Fresing Render, **one window** walks them through what matters, in a few clicks, and
ends with them doing something real: importing their first STEP or opening the Learning hub. Blender's own first-start
window (language, keys, theme) no longer comes first.

## Steps (owner's pick: the full set-up; every step has Back / Next, a step bar on top, **Skip set-up** always there)

1. **Welcome** – what the app is (today's welcome text; 0266's "who it is for" in one line), the language choice that
   Blender's window had (only the languages Fresing's texts make sense in – say which; English default).
2. **Your work** – tick what you do (CNC & machining · Offshore & cable laying · Product design & R&D · Lifting plans ·
   Education & training · Sales / presentations · Animation): sets the **workspace for new projects** (0062;
   several ticks → the nearest workspace or All functions – say the rule) and what the Learning hub suggests first.
   **From task 0294 (0.2.226):** the ticks map to the built-in workspaces – Sales / presentations → **Sales**,
   Animation → **Animator**, the others to their area workspace (a "just a picture" tick may map to **Quick render**,
   "looking at models" to **Reviewer**); **no tick → Essentials** (leave "Workspace for new projects" empty: '' is
   "not chosen" = Essentials, `workspaces.chosen()` / `default_name()`). Set the choice with
   `prefs.default_workspace` (kept by the settings file).
3. **Your PC** – runs the PC check's **Quick** mode in the background (~20 s on the owner's PC) and shows in plain words:
   graphics card found / not, the render device chosen, a suggested Live preview and render quality; one line when the
   PC is slow ("Big models will be slow on this PC: …").
4. **Your company and your folders** – "Do you have a Fresing set-up file (`.frsetup`) from your company, department or
   a colleague?" – found by itself (0272: next to the approved-version folder) and shown, **Open set-up file…** / drop
   it on the window (one file, network or local – owner 17:53), or **No**. With a set-up file: a short **"Different
   from standard"** list of what it sets (0272), and the steps it fills (2, 4, defaults) shown pre-filled; then
   the user's own STEP models folder and where renders go (default **Renders next to the project**, owner 17:39).
5. **The Learning hub** – make it now (0275's progress window; the user can go on to step 6 while it is made) or later.
6. **Done** – **Import your first STEP…** · **Open the Learning hub** (greyed with the progress while it is made) ·
   **Open the demo project**; one line: "Change any of this in Fresing > Settings…; Fresing > Set up again… runs this
   again".

## What to do besides the steps

1. **Blender's own first-start window** ("quick set-up": language, keys, theme; today the app waits for its Continue,
   `welcome._quick_setup_open`) **does not show**: the app writes Blender's choices itself on the first start (Blender
   keys – the app's key rules of 0253 sit on top –, the app's theme, the language from step 1) and saves the
   preferences, so the window never comes. Prove it on a fresh settings folder (no `userpref.blend`), on Linux and on
   GitHub's Windows job (part A installs fresh).
2. **Who sees it:** a new install (no start file); an update from a version before this task: **not** the set-up, only
   What's new (they are set up already) – with one line in What's new "New: a set-up for new users – Fresing > Set up
   again…". Never in background runs, the queue, the PC check, the kit, with `FRESING_NO_WELCOME` or simulated events
   (today's rules).
3. **IT pre-sets:** a company that put a `.frsetup` file (0272) gets steps 4 and (if the file says so) 2 pre-filled; a
   set-up file may say `"first_setup": "skip"` so managed PCs start straight in. `COMPANY-USE.md` says so.
4. **Client view:** the set-up never opens in it.

## Done when

- [ ] Fresh settings folder: no Blender quick-set-up window, the Fresing set-up opens, every step works, Skip works at
      every step; real-app test clicks the whole way (Quick PC check shortened in the test) and once with Skip
- [ ] An update from 0.2.19x shows What's new, not the set-up; a set-up file with `skip` starts straight in
- [ ] Windows job part A: the fresh install starts without Blender's quick set-up (screenshot or a check line)
- [ ] Guide chapter "First start" with pictures; function list, PC-check line, CHANGELOG; report with the owner's check
      steps (how to see it again on his PC without losing his settings); merged, released

## Not in this task

New settings; online accounts or sign-in; collecting anything about the user (nothing leaves the PC – the ticks in step
2 stay in the app's settings).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (worker), 24 Nov 2026. Released as **0.2.233**.

**What changed:**
- **New `blender/first_setup.py`** – the set-up window (made like Fresing Settings: screen mark `fr_first_setup`, its
  page in the toolbar region, in `PAGE_MARKS` and `panels.SIDE_MARKS`, place kept as `first_setup`). Six steps
  (`core/first_setup.STEPS`), step bar, Back / Next, **Skip set-up** top right on every step. Step 1 language of
  Blender's menus (English / Nederlands / Deutsch – the app's texts stay English); step 2 nine work ticks →
  `prefs.default_workspace` (no tick '' = Essentials, one = its workspace, two+ = All functions; only a click writes,
  opening never overwrites a user's own choice) + the hub's first chapter (`ui_tour` opens it when nothing is picked);
  step 3 runs the PC check's Quick lines `app.start, gpu.device, pc.gpu, import.crane, render.gpu` in a background
  Blender (`first_setup_probe.py`, own history folder, no report, no browser; CREATE_NO_WINDOW on Windows), says it
  in plain words (`core.pc_summary`) and sets Live preview's remembered choice; step 4 the set-up file in use with
  "Different from standard" (what the set-up files set), Open set-up file… (drop works: the 3D view's file handler),
  Add my STEP models folder…, where renders go; step 5 Make it now (`tour_make` in the main window → 0275's card);
  step 6 Import your first STEP… / Open the Learning hub (greyed while made) / Open (or Make) the demo project / Save
  my set-up as a file… / Close.
- **Blender's quick set-up never shows:** the app template's load_post calls `first_setup.at_load` before Blender makes
  its splash – Blender's keys (Blender), theme (default) saved with `save_userpref` when there is no `userpref.blend`;
  on the start that shows the set-up the splash is off for that start only. Measured on the web machine with a
  settings folder without `userpref.blend`: old template → Blender's "Quick Setup" (language/theme/keymap/Continue);
  new → the set-up window only.
- **Start file** (`core/start.py`): a new user's start shows `"setup"` (was `"welcome"`), at most 3 starts; a part
  `setup` = state ''/done/skipped, step, work ticks, version, by "it". An existing user (last_run set) gets What's new.
  The welcome stays as Fresing > Welcome screen…. `.frsetup`: `"first_setup": "skip"` (top level or in
  `first_start`) → skipped by IT; `first_start.workspace / work / language` pre-fill.
- **Fresing > Set up again…** (greyed in the Client view with the reason; the set-up never opens there).
- Small fix: Settings > Locations' "Different from standard" no longer lists `window_places`.
- Guide chapter **First start: the set-up** (`#first-start`, 6 pictures from the real-app test), the welcome section
  rewritten, the Fresing menu list; `COMPANY-USE.md` (what IT can pre-set / skip); function `help.first_setup`
  (tour stop `start_here`), PC-check line `app.first_setup` (MIN_LINES_FULL 146), `app.start_here` expects the set-up;
  Windows install part A checks the installed template hands the first start to the set-up (and "Preferences saved").

**Tested and measured** (4-core web machine, no graphics card, real Blender 5.2.3 under xvfb):
- `tests/test_first_setup.py` 35 tests; `test_start.py`, functions, places, form windows, locations, apptools,
  editors, ci tools, workspaces essentials, tour versions, user guide: all pass. `tooltip_report.py --strict` OK.
- Real app `ui_test_first_setup.py` (new group member of paths-heavy, ~1 min): **42/42** – prefs saved by the app,
  splash left out, the window shows only its page, Next clicked through all six steps (real clicks found by the
  button's blue), ticks → workspaces, the PC lines (shortened to 2 lines in the test), a company set-up file, the hub
  started and cancelled, Close → "done", Set up again…, a click on Skip → "skipped", IT skip, update from 0.2.195 →
  What's new, Client view refused. `ui_test_start.py` **75/75** (a new user now gets the set-up).
- PC-check lines `app.first_setup` and `app.start_here`: OK (bpy module).
- The probe's real time with all five lines (import + HD render on a card) was not measured here (no graphics card);
  the brief's "~20 s on the owner's PC" is an expectation.
- GitHub runs: see below.

**Owner's check (on your PC, without losing your settings):**
1. Close Fresing Render. Open the app folder (Fresing > Tools and checks > Open the app folder), go to
   `…\portable\config\` and **rename** `fresing_start.json` to `fresing_start.json.keep` (your settings are in other
   files and stay).
2. Start Fresing Render. You should see the window **Set up Fresing Render** and no start-up screen. Click through
   with **Next**; on **Your PC** it looks at your RTX 3090 (about 20 s to a minute) and should say "Graphics card
   found", "Renders on: the graphics card" and how long one HD picture took.
3. Anything you change there is a real setting (workspace for new projects, Live preview, folders). On **Done** press
   **Close**.
4. To get back to exactly where you were: close the app, delete the new `fresing_start.json` and rename
   `fresing_start.json.keep` back. (Or simply use Fresing > Set up again… any time – no file needed.)

**Open points / follow-up tasks:**
- No independent review helper ran: the only Windows-only line is the `CREATE_NO_WINDOW` flag of the probe (the same
  pattern as the Learning hub's build); the owner's check step 2 confirms it on Windows.
- The Windows installer already saved Blender's preferences before this task, so a fresh Windows install never showed
  Blender's quick set-up; the app's own save covers a settings folder without them (dev machines, a deleted folder).
- Languages: only English, Dutch, German are offered (Blender's menus); Fresing's own texts are English only.
