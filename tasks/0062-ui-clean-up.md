# 0062 – A cleaner side panel: show only the functions a project needs, clearer separation, tidy start-up

**Who:** worker · **Status:** running (18 Nov, owner's overnight run; 0198 on `main` first for the app template,
see the lead note of 18 Nov)
· **Branch:** `claude/youthful-goldberg-52dvm2` (the web session's own)
**Started by:** lead chat, 10 Nov 2026 (owner's wish)
**Lane:** touches every panel file (`blender/ui*.py`), `app_template/fresing_render/__init__.py`, `blender/props.py`
(additive), guide pictures – so it runs **alone** (no other task with UI changes at the same time)
**Model:** Fable · effort High (owner agreed 17 Nov: it runs alone and touches every panel; fallback Opus · High) ·
**Place:** Claude Code on the web, environment
"CAD-render-animation"

**Lead note 18 Nov 2026 00:05 – the owner's picks (final; build them without stopping):**
- **0197** (`tasks/0197-*.md` report, page `tasks/0197_page/`): `0197 picks: 1, 2, 3, 4, 6, 7, 8, 9, 10, 14 · lock b ·
  word: Workspace + hide tabs`. So: (1) separation rule + `gap()` helper, boxed sub-panel headers, grey hints;
  (2) numbered how-to boxes in a fold "How it works" – open on a new project, closed once the function was used,
  Preferences switch keeps them open; (3) 5 Scene & Render in work order (surroundings → light → camera → saved
  scenes → image size & render → turntable → web 3D); (4) Brand kit & logo, Labels, Watermark move to 6 Animation
  next to Finishing / Pictures / Music, the "(6 Animation > …)" cross-references built from one table; (6) one word
  per action (Remove / Clear / Delete, Show in folder, Add / Use as, Back to …, Find, Set-up) – tooltips and guide
  follow; (7) no labels cut with "…" at the default width; (8) one blue `primary()` button per section; (9) one line +
  button (or hidden) when the sea / vessel / way cover / drum / track is not there; (10) a "What's next" card above
  1 Import (× hides it, remembered per project, gone after the first render); (14) a state in every sub-panel header.
  **Not picked:** 5 (no section split, no renumbering), 11, 12, 13. **Client view lock: (b)** – editing operators
  refused, panels hidden, parts `hide_select` + locked, Delete / Edit Mode / Outliner / Blender's Import & Save-as off;
  Full access undoes all of it; no password. **The word:** keep "Workspace" and **hide Blender's 11 workspace tabs** in
  every workspace except Full access (they come back there).
- **0200** (report `tasks/0200-less-scrolling-study.md`, prototype on branch `claude/busy-newton-24qrjk` –
  `tasks/0200_proto/`, take from it, do not merge it): `0200 pick: render A+B · float 2 · scroll 1+2+4`. So: **A** a
  "Make" panel above 1 Import (Picture, Product video, Turntable, 3D page, Animation, Queue; each opens the app's own
  settings panel as a popover with its Make button; `bl_ui_units_x` before registration; `ui.wrap()` takes the
  popover's width) and **B** the same list as a "Make" popover in the 3D view header; no section renumbered.
  **float 2:** the "Set-up window" – a second OS window showing a "Set-up" sidebar tab with the steps one at a time
  (CNC mill, mechanism; later cylinders, cables), Back / Next, opened from each set-up sub-panel and from the Make list;
  the step number in scene properties (saved). **Owner checked on his PC (17 Nov 23:50): the window stays in front of
  the main window, and comes back on the second monitor after Ctrl+S and reopening.** **scroll 1:** a grey hint +
  guide + tour text for Ctrl+click on a section title; **2:** section tabs All · 1 … 7 (a `poll` in each section class,
  1 Import gets one); **4:** rarely used settings in "More" folds, how-to boxes folded once learnt (= 0197 item 2).
  Not picked: render C (a top-bar Make menu – 0199 may add it to its Fresing menu later), scroll 3.
- Also fix 0200's find: "7 subassemblys" – `core/words.plural("subassembly")` must give "subassemblies" (+ test).
- **Order changed (owner 18 Nov):** 0198 → **0062** → 0199 (0199 waits; it builds its menu on 0062's layout).
  **0198 is not on `main` yet** at 00:05 (code pushed on `task/0198-layout-kept-on-open`, renumbering after 0192 took
  0.2.149). Start by reading and the design (subagent split, below "Design"); **do not edit `app_template/`,
  `ui_header.py`, `ops_tour.py` or `ops_demo.py` before 0198's "done" commit is on `main`** – check with
  `git fetch origin main && git log origin/main --oneline -20 | grep 0198`, every ~20 min while designing; then merge
  `main` into your branch. If 0198 is still not on `main` after 3 hours, build everything else and leave those files
  to the end. Lifting L3 (0191) may merge meanwhile (new files + `functions.py` entries): take its family in the
  workspace map. Running beside you: 0191, 0195 (study) – neither changes `ui*.py`.

**Lead note 17 Nov 2026 – order and pre-study (owner agreed 22:00):** 0062 runs **before Lifting L4** (the Lifting
panels are then built once in the new layout). Its one stop (point 5, and the Client view lock level) moves to the
findings-only study **0197**: the owner picks from 0197's page before 0062 starts and the lead writes the picks here –
0062 then runs **without stopping**. 0197's panel inventory and workspace map are 0062's starting point.

**Lead note 17 Nov 2026 22:30 – owner's new wishes (Start & learn lane):** point 3's "every project opens in the
app's layout" and a way back to a hidden Fresing panel move to **0198** (done before 0062; 0062 keeps "sections 1–7
start folded"). A top-bar "Fresing" menu, the welcome and What's new go to **0199** (before 0062; 0062 keeps its menu
as it is). New for 0062, from the owner: **all ways to render side by side** (3D page, turntable, current view and the
others), **less scrolling**, and **a floating, draggable set-up window** (e.g. setting up a CNC mill or a mechanism)
– study **0200** measures what Blender allows and puts options on a page; the owner picks there and the lead writes
the picks here with 0197's. Order: 0198 → 0199 → 0062; 0200 beside them; 0062 starts only when both pages are picked.

**Lead note 14 Nov 2026 – interactive learning (study 0123):** the owner wants this overhaul and the learning modes (Show me / Build it yourself on the test models, the guide inside the app) to work as one. Before this task starts the lead adds 0123's results here: the families come from the one function list (registry), and the shared panel helpers get the hook that lets a lesson highlight a button and open its folds. The modes themselves are built after this task.

**Lead note 17 Nov 2026 – highlight looks (owner's pick from 0168):** `button C + D, section 5 + 4, part 3 + 1,
colour Fresing Green`. The hook builds **both looks of each pair** behind one setting (Preferences, "Lesson highlight"),
the first named as default; the owner settles each pair on his RTX 3090 and the lesson build tasks drop the other.
Take the code from branch `claude/practical-heisenberg-jm99vr` (`fresing_render/blender/lesson.py`, on top of 0133's) –
**only these six looks**, not the other 23.
- **Button C** (spotlight: rest of the side panel dimmed, the button clear with a thin outline) – default. As clipped,
  C also dims the Lesson panel and greys its *Do it for me*: build it with the **Lesson panel left clear** (look M's
  two markers already do this). **Owner's 0185 pick (17 Nov 21:52): C bright** – the Lesson panel keeps full
  brightness (instruction, Back, Do it for me, Stop lesson), the rest of the side panel dimmed; see 0185's page,
  `step4_C_bright` on branch `task/0185-look-c-wide`. No dark variant.
- **Button D** (bar on the button's left edge, button tinted, breathing) – check the white label on the tint stays
  readable at Windows display scaling 100–200 %.
- **Section 5** (header label in the colour, fold arrow nods slowly) – default · **Section 4** (bar on the header's
  left edge).
- **Part 3** (rest faded, the part clear in its own colour) – default · **Part 1** (see-through glow).
- **Colour** stays one setting (`lesson.set_colour`), default Fresing Green `#479B29`; the text card's accent follows
  it. Breaths at 1.5 s as in 0168 (loops join at 3 s), never faster than 1 per second.
- On one button of a joined pair (0133's fix); costs on the crane were 0.05–1.25 ms per redraw – measure part 3 and 1
  once on the demo (1,250 parts).

**Lead note 17 Nov 2026 – workspaces (owner's document "UI workspace presets & adaptive usage tracker"):** the
built-in sets of point 1 become **workspaces** for target groups (the owner's word; the panel says "Workspace"), with
one switcher at the top of the Fresing tab, remembered per project, and a user default for new projects. Each
function entry in `core/functions.py` gets a field naming the workspaces that show it, so a feature built later adds
itself (the Lifting lane does this; 0062 does not wait for it). The family ticks stay under the switcher. Built-in
workspaces (each hides what its users never need; every hide keeps the work, point 1):
- **CNC & machining** – G-code player, toolpaths, axis set-up, tool library, workshop surroundings, clash check.
  Hides: sea, vessel motion, studio rigs, exploded views.
- **Offshore & cable laying** – sea and seabed, vessel motion, cables / winches / spools, cranes and A-frames, outdoor
  marine skies. Hides: G-code, toolpaths, studio set-ups.
- **Product design & R&D** – studio lights, materials and paint, exploded views (assembly sequence), cutaway,
  turntable. Hides: G-code, cables and rigging, sea and workshop surroundings.
- **Client view (sales)** – import, surroundings picker, saved views, turntable, Render. Hides everything else **and
  locks the model** against accidental edits (parts cannot be moved, deleted or re-meshed; the worker proposes how
  strict, the owner picks with point 5).
- **Education & training** – the test tour (later the lessons of study 0123), the animation timeline, simplified
  camera controls. Hides: render engine settings, shader editing, batch export.
- **Full access** – every family plus Blender's own toolbar and editors.
- **Lifting plans** – comes with the Lifting lane (study 0180); the owner merged his "Heavy lifting, cranes & rigging"
  group into it.
- **Robotics & factory automation** – left out until robotics functions exist (6-axis arm, grippers, conveyors,
  safety zones are not in the app).
Own workspaces are 0062's own sets: one `.json` file each in the library (folder "Workspaces"). Blender has its own
"workspaces" (the tabs at the top): the worker checks the app hides them or the word does not confuse, and says so in
the point-5 list. The usage tracker, favourites bar and declutter prompts of the same document are **0181**, after
this task.

## Goal

The Fresing side panel has grown to 7 sections and ~35 sub-panels. Many projects (an offshore crane, a cable-laying
machine) never use the CNC functions, yet milling, chips, coolant, tool changes and way covers are always there. The
owner wants a calm, clean panel: only what the project needs, clear separation between sections and buttons, and a
tidy start every time the app opens.

## The owner's points (10 Nov 2026)

1. **CNC milling functions are often not needed: a way to separate them.** Suggestion to work out: a choice at the
   top of the panel or in 1 Import, e.g. **"Functions in this project"** with ticks per family – *CNC machine &
   milling* (CNC machine, Tools, Tool changes, Milling, Chips, Air blast, Coolant, Way covers, tool marks), *Mechanisms
   & cylinders*, *Hoses & drag chains* (0058), *Video finishing* (brand kit, labels, pictures, music) – or a few ready
   profiles ("Machine stills", "Machine animation", "CNC demo", "Everything"). Hidden families keep their settings;
   a project that already uses a family shows it when it opens (the user may hide it afterwards, with the warning
   below); one click shows everything.
   Saved with the project and in templates.
   **Owner's choice 10 Nov: both** – ticks per family *and* ready-made sets – **plus the user's own sets**: a set he
   makes ("Offshore cranes", "Mill demos") is saved as **one file in the app's library folder** (the same shared
   library as rule sets (0015) and brand kits (0018), e.g. a folder "Panel sets"), so a colleague gets it by copying
   that file into his own library folder. Ready-made sets are built in and cannot be overwritten; an own set with the
   same name wins and says so. A set file from a newer version opens in an older one without errors (unknown families
   ignored).
   **Owner's choice 10 Nov (2): switch on and off at any time.** A family can be turned on or off in the middle of a
   project, as often as the user likes, so everyone can shape his own workflow. Turning off a **main function** (a
   family the project uses: set-up, steps or keys in it) shows a **warning popup** that names what is set up ("This
   project has a CNC machine, 3 tools and a G-code step. They stay in the project and keep working in renders; only
   the panels are hidden.") with **Hide anyway** and **Cancel** – it is allowed, never blocked. Turning it on again
   shows everything as it was. Hiding a family never deletes or switches off its work.
2. **More visual separation between the buttons and sections.** Clear headers per section, spacing between groups,
   boxes or lines between a section's steps, the main button of each section stands out (`primary()`), consistent
   icons; the layout rules at the top of `blender/ui.py` stay and get a "separation" rule.
3. **On start-up the Fresing panel always shows and Blender's own toolbar (the tool shelf on the left) is folded
   away.** Also when opening an existing project, a test-tour project, a project saved by an older version, after
   Update now, and with the Blender splash. The app template does part of this today (`show_region_ui`,
   `show_region_toolbar = False`, Fresing tab) – find where it does not hold (projects saved with their own window
   layout, "Load UI") and make it hold.
4. **In the Fresing panel, sections 1 to 7 start folded** for a clean look when the app starts (each header still
   shows its state, as the layout rules say). **Owner's choice 10 Nov: always start folded**, with a user setting
   (Blender Preferences of the extension, or a small "Panel" fold in Help) to keep them as they were left.
5. **"And more improvements"** – the worker first makes a short list from the panels as they are then (screenshots
   with `tools/ui_screens.py`), e.g.: long sections split or moved into folds, the same words for the same things
   everywhere, rarely used settings in "More", sub-panels in a sensible order, a short "what's next" hint at the top
   of a new project. **The owner picks from that list before the build** – done in study **0197** (17 Nov): the picks are
   written in this brief before the task starts; no stop in this task.

## Done when

- [ ] The owner's picks from 0197 (point 5, lock level, the word) built; any pick left out is named in the report.
- [ ] Ticks per family, built-in sets and own sets (save, rename, delete; one file each in the library folder; a
      copied file shows up after Refresh / restart – tested with a second settings folder).
- [ ] Function families can be switched on and off at any time in a project; hiding one that is in use shows the
      warning popup (Hide anyway / Cancel) and keeps all its work (renders, queue, model update unchanged – test); templates and
      old projects open with everything they use visible.
- [ ] Start-up: Fresing tab open, Blender's toolbar folded, sections 1–7 folded (user setting to keep them as left) – checked for a new project, an old
      project, a tour project and after Update now (real-app test).
- [ ] Separation and the other picked improvements done in every panel; screenshots of every panel looked at.
- [ ] Real-app tests and `tools/guide_screens.py` adjusted (they click fixed spots: folded sections change those);
      every guide picture of a changed panel re-made; guide chapter "The side panel" on families and start-up.
- [ ] Tooltips on all new settings; test-tour stop "Functions in this project"; PC-check line if something visible
      can break on Windows.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

New functions. Changes to what a button does (only where it sits and how it looks). Blender's other editors.

## Design (worker, 18 Nov 2026 – the split and the interfaces; the subagents' brief)

Tried in the real app first (Blender 5.2.3 under xvfb, web machine; probes in the session's scratchpad):
a panel without Blender's header (`HIDE_HEADER`) can have sub-panels, three levels deep; a header row drawn by the app
(an operator without frame: fold arrow + title, state on the right) looks like Blender's and sees Ctrl in `invoke`;
Blender's 11 workspace tabs go away by replacing `TOPBAR_HT_upper_bar.draw_left` (nothing is deleted); a key in an
add-on keymap whose operator's `poll` is False passes on to Blender's own key (Delete, Ctrl+Shift+S), so a lock can
swallow keys only while it is on. Blender keeps a panel's open / closed state per panel name and gives an add-on no
way to set it – so "always start folded", "tab 3 opens section 3" and "a lesson opens the fold" need the app's own
headers.

### Decisions (the owner is asleep; each is in the report)

1. **Every Fresing side-panel panel draws its own header** (`blender/panels.py`, put on the classes when they are
   registered – no panel file changes for it): sections get a boxed, taller title row, sub-panels a boxed row; fold
   arrow + icon + title on the left, the state on the right; click = open / fold, **Ctrl+click = only this one stays
   open**. The open set is the app's (`panels.is_open / set_open`), not Blender's: sections 1–7 start folded at every
   start and every load; Preferences > "Keep sections as I left them" stores the set in the project at save.
   Sub-panels keep their old default (those without `DEFAULT_CLOSED` start open).
2. **Workspaces** = which functions show. Built in: **All functions** (default for new projects: everything, Blender's
   tabs hidden), CNC & machining, Offshore & cable laying, Product design & R&D, Client view, Education & training,
   **Full access** (everything + Blender's tabs, toolbar, menus). "All functions" is new (the owner's first list had
   "Everything"): without it the calm default would be missing – Full access brings Blender's own UI back.
   Lifting plans: the Lifting lane adds the key to its functions (`workspaces=`); Robotics: later.
3. **Families** are the ticks under the switcher: `functions.FAMILIES` + a new family `video` (brand kit, labels,
   watermark, finishing, pictures, music). Always on (no tick): import, looks, scene, help.
4. A function shows when its family is ticked and the workspace does not hide it (`Function.workspaces`, default by
   family from `workspaces.FAMILY_DEFAULT`). A panel shows when one of its functions shows; a panel no function names
   always shows. A project stores the workspace's name, its definition (own workspaces: so it opens the same on a PC
   without the file) and the user's ticks.
5. **Old projects and templates:** a project without a stored workspace opens in the user's default workspace with
   every family it uses ticked. A family the user hid with "Hide anyway" stays hidden at the next open (it is his
   choice; the panel says "N in use hidden" with Show).
6. **Client view lock (b):** every `fresing.*` operator except a short allow-list is refused (`poll`, with a reason),
   all objects `hide_select` + locked (what was changed is remembered per object and put back), active object cleared,
   Delete / X / Tab / Ctrl+Shift+S swallowed by an add-on keymap, the Outliner areas show the Info editor (put back),
   File menu reduced (no Save As, Import, Export, Link, Append). Full access – or any workspace without the lock –
   undoes all of it. No password.
7. **Blender's tabs:** hidden by drawing the top bar without them; back in Full access. No workspace is deleted.
8. **Section tabs** All · 1 … 7 under the workspace row (session state, starts at All); a tab shows only its section,
   opened. The Ctrl+click hint is a grey line under the tabs until the user has done it once (stored in Preferences).
9. **Make** (render A + B): a panel "Make" above 1 Import, folded like a section, six buttons that open the app's own
   settings panels as popovers; the same list as a popover "Make" in the 3D view's header. Section numbers stay.
10. **Set-up window** (float 2): `fresing.setup_window`, a tab "Set-up" in a second window; kinds CNC mill and
    mechanism; step number in the scene (`setup_kind`, `setup_step`).
11. **Moves (pick 3 + 4):** 5 Scene & Render in the order surroundings (Weather & time, Vessel motion, Vessel at work,
    Props, House) → Camera → Saved scenes → Image size & render → Turntable video → Web 3D model; Brand kit & logo,
    Labels, Watermark go to 6 Animation after Finishing. Text that names a place is built by `places.where()`.
12. **One blue button per section** (pick 8): Import STEP…, Sort parts into groups, Render image, Build & play, Start
    queue (2 Structure and 4 Motion have none: no single main step); the Make popovers and the Set-up window's Next
    are blue too. Every other former `primary()` is `big()` (big, grey).
13. **Words (pick 6):** *Remove* = takes a thing out of the project · *Clear* = empties a list, a cache or a result ·
    *Delete* = only files in the library · *Show in folder* · *Add* = a new thing; *Use as* = picks the clicked part ·
    *Back to …* always names where to (Back to CAD position, Back to the rules, Back to the defaults) · *Find* (not
    Search) · *Set-up* (noun) / *Set up* (verb). Button texts, tooltips and the guide follow; operator ids do not change.

### Shared code (the worker's; committed before any subagent starts)

`fresing_render/blender/ui.py` helpers every panel file uses:

| Helper | What it draws |
| --- | --- |
| `gap(layout, line=False)` | the space between two steps of a panel (separation rule); `line=True` adds a thin line |
| `primary(layout, idname, text, icon, scale=BIG)` | the ONE blue main button of a section |
| `big(layout, idname, text, icon, scale=MEDIUM)` | a sub-panel's main button: big, grey; returns the operator |
| `hint(layout, context, text, inset=0)` | a grey hint without icon; `wrap(..., icon="INFO")` is grey too |
| `steps(layout, context, lines, key="", used=False)` | the numbered how-to in a fold "How it works" (`key` = the fold's id, e.g. `"fr_how_cutaway"`): open while `used` is False, closed once it is True; Preferences "Keep How it works open" |
| `missing(layout, context, text, op="", op_text="", icon="INFO")` | pick 9: ONE line (+ one button) when the thing a panel needs is not there; returns the operator or None |
| `header_status(layout, text, icon, alert, limit)` | unchanged: the state on the right of a header |
| `where(panel, fold="")` | "6 Animation > Labels" from `core/places.py` |

`fresing_render/core/places.py`: `SECTION` / `PLACES` (panel class name → section number, title, parent) and
`where()`; a test compares it with the registered panels. `core/workspaces.py`: the built-in workspaces, own-workspace
files, what shows. `blender/workspaces.py`: the project's state, in use, lock, Blender's tabs. `blender/panels.py`:
headers, open set, tabs, the `poll` put on every panel and operator. `blender/ui_top.py` + `ops_workspace.py`:
Workspace switcher, What's next card, tabs, Make.

### The panels pass (rules for every panel file; one owner per file)

For each panel in your files, without changing what any button does:
1. **Steps apart:** a `gap(layout)` between the groups of a panel (how-to · choices · main button · list · details ·
   more). No two buttons of different steps touch.
2. **How-to boxes:** every `steps(...)` call gets `key="fr_how_<panel>"` and `used=<the project has one>` (a cut, a
   decal, a cylinder …).
3. **One blue:** `primary(` → `big(` except the five named in decision 12.
4. **A state in every sub-panel header:** `draw_header_preset` with `header_status(...)`: a count (`plural`), on / off,
   or the chosen thing; at most 14 characters; an alert colour only for a problem.
5. **Nothing cut off** at the default width (side panel 292 px at scale 1.0 – about 38 characters per line, a button
   pair about 16 each): shorter text or two lines (`wrap`).
6. **Words** of decision 13 in button texts and tooltips (`bl_label`, docstrings, `description=`); operator ids and
   property names stay. A changed text that `core/functions.py` (`text=`), a test or `tools/` names: list it in your
   report – the worker changes those.
7. **Not there** (pick 9): when the thing a sub-panel needs is missing (no sea, no vessel, no axis joint …) the whole
   body is one `missing(...)` line with the button that gets it, nothing else.
8. Tooltips on anything new. No new functions. `tools/tooltip_report.py` stays clean for your files.

### Subagents (at most 3 at a time; each in its own worktree; none pushes, merges, bumps the version or edits
`TASKS.md`, `props.py`, `ui.py`, `__init__.py`, `handlers.py`, `tour.py`, `pccheck/`, the guide, `core/functions.py`)

| # | Job | Files it owns |
| --- | --- | --- |
| S1 | Set-up window from 0200's prototype (`tasks/0200_proto/setup_window.py` on `claude/busy-newton-24qrjk`) | new `blender/ui_setup.py`, `blender/ops_setup.py`, `tools/ui_test_setup.py`, `tests/test_setup_window.py` |
| S2 | Lesson highlight hook: the six looks (button C + D, section 5 + 4, part 3 + 1) from `lesson.py` on `claude/practical-heisenberg-jm99vr` | new `blender/highlight.py`, `tools/ui_test_highlight.py`, `tests/test_highlight.py` |
| S3 | Panels pass: 4 Motion, 6 Animation, 7 Render queue, Saved scenes | `blender/ui_motion.py` |
| S4 | Panels pass: the machine sub-panels of 4 Motion | `ui_gcode.py`, `ui_machining.py`, `ui_coolant.py`, `ui_waycover.py`, `ui_flex.py`, `ui_paths.py`, `ui_spool.py`, `ui_tracks.py` |
| S5 | Panels pass: the other sub-panels | `ui_callouts.py`, `ui_clash.py`, `ui_decals.py`, `ui_fade.py`, `ui_house.py`, `ui_people.py`, `ui_section.py`, `ui_vessel_motion.py`, `ui_video.py`, `ui_weather.py`, `ui_web3d.py` |
| S6 | Independent tests of workspaces, families, own-workspace files and the lock, written from this brief by an agent that wrote none of it; its findings go back to the worker | new `tests/test_workspaces_independent.py` |
| S7 | Guide chapter + pictures, at the end | `docs/USER-GUIDE.md`, `docs/img/` (the worker merges) |

The worker keeps: `ui.py` (helpers + its panels' pass), `panels.py`, `workspaces.py`, `ui_top.py`, `ops_workspace.py`,
`core/`, `props.py`, `prefs.py`, `__init__.py`, `handlers.py`, `tour.py`, `pccheck/`, `core/functions.py`, the real-app
tests and tools, version, CHANGELOG, `TASKS.md`; after 0198 is on `main`: `app_template/`, `ui_header.py`.

**Interfaces the subagents build against**
- S1: `scene.fresing.setup_kind` (enum `CNC` / `MECH`), `scene.fresing.setup_step` (int ≥ 0) exist in `props.py`.
  `ui_setup.SETUPS = {kind: (title, [(step title, draw(layout, context)), …])}`, `ui_setup.draw_setup(layout, context)`,
  panel `FRESING_PT_setup` (tab "Set-up"), operators `fresing.setup_window` (prop `kind`), `fresing.setup_go` (prop
  `step`); `CLASSES` tuples in both files. The worker adds the "Set-up window" buttons to the panels and the Make list.
- S2: `highlight.point(panel="FRESING_PT_x", button="fresing.op", text="", prop="", fold="", parts=())`,
  `highlight.clear()`, `highlight.active()`, `highlight.set_look(kind, key)` (kind `button` C / D, `section` 5 / 4,
  `part` 3 / 1), `highlight.set_colour("#479B29")`, `highlight.mark_header(layout, panel_name)` (the worker's header
  code calls it), `highlight.fold_open(idname) -> bool` (`ui.fold` asks it), `highlight.register()/unregister()`.
  Nothing runs while nothing is pointed at. Preferences (the worker adds them): `lesson_button` (C / D),
  `lesson_section` (5 / 4), `lesson_part` (3 / 1), `lesson_colour`.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web (Fable · High), 17–18 Nov 2026, the owner's overnight run. Branch
`claude/youthful-goldberg-52dvm2` (the web session's own). **State while it runs** (so a new session can continue
with "… and continue task 0062 from its branch"): see "Progress" at the end of this report.

**What changed:** (filled in at the end)

**Tested and measured** (name the machine and the model): (filled in at the end)

**Open points / follow-up tasks:** (filled in at the end)

**Progress (worker's notes, 18 Nov):**
- Done on the branch: `core/workspaces.py`, `core/places.py`, `blender/panels.py` (own title rows, open set, tabs,
  polls), `blender/workspaces.py`, `blender/lock.py`, `blender/ui_top.py`, `blender/ops_workspace.py`, the helpers in
  `ui.py`, the panel pass over `ui.py` (worker) and `ui_motion.py` (S3, merged), words in operators, the moves
  (Brand kit / Labels / Watermark → 6 Animation, 5 in work order), function-list entries, guide sections (text;
  pictures are placeholders), tour stops `workspace` + `make`, PC-check line `panel.workspaces`, tests
  (`tests/test_workspaces.py`, `tests/test_places.py`, `tools/ui_test_panel.py` 37 checks), screenshot tools adapted.
- Merged since: `main` with 0198 (0.2.150); S1 the Set-up window (`ui_setup.py`, `ops_setup.py`, 46-check real-app
  test) with its buttons, tour stop `setup`, function entry and guide section; S2 the lesson highlight
  (`highlight.py`, 74-check real-app test); the panel pass over the video finishing panels (worker); counts raised;
  `ui_test_panel`, `ui_test_setup`, `ui_test_highlight` in `tools/ci_real_app.py`; CHANGELOG text (0.2.151).
- Running as subagents: S4 panel pass over the machine sub-panels, S5 panel pass over the other sub-panels, S6
  independent tests (`tests/test_workspaces_independent.py`, findings as strict xfail tests).
- Still to do: merge S4 / S5 / S6 and fix S6's findings; S7 guide chapters + every panel picture; version 0.2.151
  in the two version files (the `since=` fields already say 0.2.151 – renumber all if another task takes it);
  full run green; fast-forward `main`; release check; report; `TASKS.md` (0062 done, 0199 "open – can start").
