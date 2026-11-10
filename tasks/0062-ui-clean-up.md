# 0062 – A cleaner side panel: show only the functions a project needs, clearer separation, tidy start-up

**Who:** worker · **Status:** later – owner's wish 10 Nov 2026: **after more of the big features are in** (owner's
order in `TASKS.md`); the lead re-reads this brief and the panels as they are then, before it starts
· **Branch:** `task/0062-ui-clean-up`
**Started by:** lead chat, 10 Nov 2026 (owner's wish)
**Lane:** touches every panel file (`blender/ui*.py`), `app_template/fresing_render/__init__.py`, `blender/props.py`
(additive), guide pictures – so it runs **alone** (no other task with UI changes at the same time)
**Model:** Opus · effort Medium (lead to confirm when it starts) · **Place:** Claude Code on the web, environment
"CAD-render-animation"

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
   of a new project. **The owner picks from that list before the build** (the worker shows it in one message with
   small screenshots and waits; this is the one stop in the task).

## Done when

- [ ] The owner's choice from point 5 is in the report.
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
