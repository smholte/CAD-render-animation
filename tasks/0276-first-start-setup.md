# 0276 – First-start set-up: one window that walks a new user through the app's set-up (replaces Blender's own)

**Who:** worker · **Status:** open – waits for 0272 (it uses the Settings pages and the locations) and 0275 (the
progress window) · **Branch:** `task/0276-first-start-setup`
**Started by:** lead, 21 Nov 2026 (owner 17:45: "maybe there should be a set-up menu when a user opens the app for the
first time?"; owner's picks 17:50: **full set-up** – **replace Blender's own first-start window**) ·
**Model:** Opus · effort Medium
**Area:** Start & learn lane – `blender/welcome.py` (the welcome becomes step 1 of the set-up; `_quick_setup_open`,
`_draw_quick_setup`), `core/start.py` (the start file: set-up done / skipped / version), a **new**
`blender/first_setup.py` (the window and its steps), `app_template/` (Blender's quick set-up skipped – see 1),
reads 0271's Settings pages and 0272's `core/locations.py`, starts 0275's progress window and the PC check's Quick
mode (`pccheck/`, read only); their tests, a real-app test, guide, `docs/COMPANY-USE.md` (what IT can pre-set), CHANGELOG.
**Not:** new settings – every choice here is one that already exists in the Settings window (0271 / 0272), the set-up
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
3. **Your PC** – runs the PC check's **Quick** mode in the background (~20 s on the owner's PC) and shows in plain words:
   graphics card found / not, the render device chosen, a suggested Live preview and render quality; one line when the
   PC is slow ("Big models will be slow on this PC: …").
4. **Your company and your folders** – "Does your company or department have a Fresing set-up file?" – found by
   itself (0272: next to the approved-version folder) and shown, or **Browse…** (network or local), or **No**; then
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
3. **IT pre-sets:** a company that put a set-up file (0272) gets steps 4 and (if the file says so) 2 pre-filled; a
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
