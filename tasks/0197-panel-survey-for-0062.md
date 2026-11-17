# 0197 – Study: the side panel as it is now – improvement list, workspace map, model-lock levels (pre-study for 0062)

**Who:** worker · **Status:** open – can start · **Branch:** `task/0197-panel-survey` (or the web session's own name)
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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
