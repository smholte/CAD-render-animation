# 0062 – A cleaner side panel: show only the functions a project needs, clearer separation, tidy start-up

**Who:** worker · **Status:** later – owner's wish 10 Nov 2026: **after more of the big features are in** (owner's
order in `TASKS.md`); the lead re-reads this brief and the panels as they are then, before it starts
· **Branch:** `task/0062-ui-clean-up`
**Started by:** lead chat, 10 Nov 2026 (owner's wish)
**Lane:** touches every panel file (`blender/ui*.py`), `app_template/fresing_render/__init__.py`, `blender/props.py`
(additive), guide pictures – so it runs **alone** (no other task with UI changes at the same time)
**Model:** Fable · effort High (owner agreed 17 Nov: it runs alone and touches every panel; fallback Opus · High) ·
**Place:** Claude Code on the web, environment
"CAD-render-animation"

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

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
