# 0328 – Bug and friction hunt round 8 (findings only): 0.2.160 to the newest, used as three kinds of user

**Who:** worker · **Status:** open · **Branch:** none (report on `main`, touching only `tasks/` and `TASKS.md`)
**Started by:** lead, 25 Nov 2026 (owner 01:06: "Are there more tasks I can run overnight? I mostly want tasks to make
the app more user friendly right now.") · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment
"CAD-render-animation". Findings only: no app code, no version, no test run of its own – it does not count towards the
code tasks.

## Goal

A ranked list of what breaks and of what makes the app **hard to use**, from 0.2.160 (the last hunt, 0209, ended at
0.2.159) to the newest, found by using it the way the owner's three kinds of user would. Grouped into fix tasks by lane,
so the lead can brief them tomorrow. The owner's aim: as simple as possible, **looks very good with no set-up**, every
function suited to all three levels.

## Who you are (three passes, one per user)

1. **Sales person, not technical** – Client view and the Sales workspace: open a project someone sent, look round,
   move the lead motions and joints (Sales may move joints since 0321 if merged), render a picture, make a short video,
   export the 3D page. Never opens Blender's own tools.
2. **CAD engineer new to rendering** – Essentials / Machine builder: first start (0276 set-up), import the test crane
   and the stress model's small size (`FRESING_PCCHECK_STRESS_SMALL=1`), sort into groups, pick materials (the picker
   if 0273 is merged), finishes, welds, joints, a lead motion, measure (0322 if merged), copy / place / remove,
   render, model update to a revision, backups, Settings window.
3. **Skilled animator** – Video producer / Full access: the animation panel, cameras, looks, render queue, Blender's
   own tools opened from the app and back (Fresing > Show all of Blender / Back), keys.

## What to look at

- Everything in `CHANGELOG.md` from 0.2.160 to the newest (read the headings first, then only what each pass needs).
- **Friction, not only bugs:** a step you could not find within ~30 s, a button whose words or tooltip did not tell
  you what happens, more clicks than needed, a panel that jumps (CLAUDE.md section 6 "The panel stays still"), a
  window that opens in a bad place or size, a question asked again and again, a default that looks poor without
  set-up, a text that assumes Blender knowledge, something that differs between workspaces for no reason, the
  Learning hub not leading to the function you need. Name the place exactly (`core/places.py` `where()`).
- **Looks with no set-up:** import the test crane, the test mill and the weldment with defaults, render a still at
  Draft and Normal: note every part that looks wrong or bare (2–3 small pictures at most, `tasks/img/0328_*`, test
  models only).
- 0209's rows: re-check that each fix holds (0213–0216, 0236–0239). The open points the lead keeps (progress note
  list, e.g. 0213 Set-up window Back / Next in the Client view, 0221 new window not tidied until the next load, 0241
  welcome box above the splash picture, 0271 keyboard-only work not seen as presence, 0179 the 3D page's settings menu
  covers the play bar): say for each whether it still stands and how much it hurts a user.
- Old projects saved by 0.2.159, 0.2.200 and 0.2.230 opened in the newest version: layout, workspace, everything
  builds the same.
- Tasks still running when you start (see `TASKS.md`): look at their area only once merged; note what you skipped.

## Rules

Public repository (CLAUDE.md section 6). Each row: who (sales / engineer / animator), what you did, what happened, what
should happen, how often, the smallest repeat case, kind (crash / lost work / wrong result / **friction** / looks /
small), how much it hurts (1–3), the lane, and a proposed fix in one line. Then a grouping into fix tasks by lane (two
fix tasks never share a file) – friction fixes that are small can be bundled per lane. Helper agents: at most 3, one per
pass is a good split; say which did what. Push only `tasks/0328-bug-and-friction-hunt-8.md` (+ small pictures) and
`TASKS.md`.

## Done when

- [ ] Report: "In short (for the owner)" (≤ 8 lines: the 5 things that hurt users most), the rows, the grouping into
      fix tasks for the lead
- [ ] Pushed to `main` touching only `tasks/` and `TASKS.md`; then check that main really contains your commit

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**In short (for the owner):**

**Rows:**

**Grouping into fix tasks (for the lead):**
