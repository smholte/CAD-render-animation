# 0333 – Workspaces match their job (0328 F4)

**Who:** worker · **Status:** done (0.2.259) ·
**Branch:** `task/0333-workspaces-match-their-job`
**Started by:** lead, 25 Nov 2026 (from 0328's report; owner's answers 25 Nov 10:5x below) · **Model:** Sonnet · effort Medium
**Area:** Workspaces – `core/functions.py`, `core/workspaces.py`, `blender/workspaces.py`, `blender/context_menu.py`,
`blender/ui_left.py`, `blender/ui_motion.py` (row 26 only), `blender/ui_lead_motions.py` (row 33 only), `blender/ui_topbar.py`
(Make's list), the Settings > General row and its stored value (`ui_settings.py`, `settings_store.py` – additively), their
tests, guide, tour stops of the workspaces, CHANGELOG.
**Not:** `lead_motions.py` / `animation.py` logic (0330), `lock.py` / `quiet.py` (0332), the Keys tab (0295).

## Goal

Each workspace holds what its user needs and nothing it hides shows up anyway: the right-click menu, the Make list and
the panels follow the workspace; a colleague's project opens in your own workspace and tells you so once.

## What to do

Fix 0328's rows **9, 10, 11, 16, 26, 33** (`tasks/0328-bug-and-friction-hunt-8.md`, table "Rows") + row 32's words in
these files. **The owner's answers (25 Nov):**

1. **Video producer** gets Weather & time (and 0299's two-click change), Turntable, Render this view, the joint sliders
   and Save start scene. **Animator** gets Light, Saved scenes, Weather and Turntable.
2. **Sales**: Make gets **Render animation** (the Product video's "then Render animation" then points there; fix its
   "the list below" words).
3. **A colleague's project opens in the user's own workspace.** On opening a project last saved by another person in
   another workspace, a popup says so (who / which workspace, in plain words; "Switch to theirs" and "OK"), with
   "Don't show this again". Settings > General: a switch for that popup (on by default). "Who" = the name the project
   already stores (0291 / backups); no name → "another person".
4. Row 10's other points (Essentials / Builder lists vs panels, Client view) as the row proposes; row 11's red alarm →
   a grey one-line hint, shorter text.

## Watch

- Read each row's repeat case and proposed fix first; a better fix is fine, say why.
- Workspace lists change the first-start set-up's ticks, the Learning hub's chapters and Favourites: check them.
- Every visible change: tooltip, guide, PC-check line, tour stop / function-list entry with `since=` / `changed=`.
- Two tasks never share a file: stay inside **Area**.

## Done when

- [ ] Each row's repeat case now gives "what should happen" (a test per row; real-app check where it was seen there)
- [ ] The owner's four answers above work in the real app
- [ ] Tests added/updated; full suite passes; GitHub run green
- [ ] (UI) screenshots checked with tools/ui_screens.py
- [ ] Report below filled in, merged, released

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 25 Nov 2026.

**What changed:** 0328 rows 9 (right-click menu draws an entry only when `workspaces.shows` its function), 10 (Video
producer: weather + presets + change, start scene, turntable, Render this view, joint sliders; Animator: light, saved
scenes, weather, turntable; `looks.picker` beside `looks.materials`; finishes + update in Essentials / Machine builder;
the Client view's `import.*` functions hidden by `NO_CLIENT`; Make's Animation output also where `queue.video` shows – Sales;
the Product video note), 11 (grey one-line "N hidden, in use"), 16 (Play beside Build & play in the Client view when built),
26 (the "animation is built" box moved under Back to CAD), 33 (no greyed Lead motions buttons when locked). Owner's answer 3:
`workspaces.take_in` opens a project saved by another person (new hidden project field `saved_by`, written at every save) in
the user's workspace; popup `fresing.colleague_workspace` with Switch to theirs / OK / Don't show again;
Settings > General switch `ask_colleague_workspace` (on by default). Function `panel.colleague_workspace`, guide section,
PC-check addition to `workspace.round3`, tests `tests/test_workspaces_match_job.py` (+ right-click test, 5 old tests updated).

**Tested and measured** (4-core web machine, no graphics card): the touched tests locally (workspaces, functions, form
window, guide, lead motions, tour, PC check: 415 passed; `test_zz_switching_the_extension_off…` fails alone on `main` too);
`ui_test_place.py` 22/22 locally. GitHub: 4 runs – popup not named in `form_window.POPUPS` (fixed); version clash with 0332
(renumbered 0.2.259); `ui_test_place.py`'s first click failed once on a slow runner, passed locally and on a re-run of that
job; final run green. Not done: screenshots with `tools/ui_screens.py` were not looked at; no real-app test of the popup.

**Open points / follow-up tasks:** Old projects have no `saved_by`, so they open as they were (no popup). "Who" is the PC
user name, not a person's name. Row 32's other words (status bar, cut texts) are untouched. 0295's Keys tab untouched.
