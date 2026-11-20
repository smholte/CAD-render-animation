# 0236 – Fixes from bug hunt 0209, group F: usage tracker and start (declutter, profiles, damaged start file, What's new, favourites)

**Who:** worker · **Status:** open · **Branch:** `task/0236-usage-start-fixes`
**Started by:** lead, 20 Nov 2026 (bug hunt 0209 rows 13, 19, 22, 25, 26, 34) · **Model:** Sonnet · effort Medium
**Area:** Usage lane – `core/usage.py`, `blender/usage.py`, `blender/ops_usage.py`, `blender/ui_usage.py`; `core/start.py`
(the start file's `load`, `new_functions`); `core/functions.py` (new optional fields + `changed=` values, no entry
removed); `blender/welcome.py` **only** if What's new's list needs one more argument (0222 package A will edit its splash
part later – keep any change there to the What's new call). Tests for every row.

## Goal

Six small faults of the usage tracker and the start window go away: the app never asks to hide a panel What's new is
advertising, a profile's hides can be undone, a hidden panel shows when the project starts using it, a damaged start
file is repaired instead of failing at every start, What's new leads with what a user sees first and names what got
better, and the favourites bar shows whole labels.

## Background

Bug hunt 0209 (`tasks/0209-bug-hunt-7.md`, table rows; proof scripts are gone – each row gives its numbers):

- **Row 13** – `core/usage.py` `declutter_candidate` (~360): a function never used counts as unused from session 0, so
  the first start after an update (0.2.150 → 0.2.159) says "What's new – 24 new functions" and asks "You haven't used
  Equipment recently. Hide it…?" (Equipment came with 0.2.156). Fix: count "not used" from the session a function was
  first offered – skip functions newer than `whats_new.from` until `threshold` sessions have passed.
- **Row 19** – `ops_usage.export_profile` (~217) puts the personal hides into the workspace's `hide` and switches to it;
  `usage.reset` clears only `state["hidden"]`: after Export profile, "Back to the workspace as it came" says "Your hidden
  panels show again" but they stay hidden; a colleague importing the profile gets hides his reset cannot undo. Fix: keep
  a profile's hides apart (a personal-hide key the importer adds to the user's own hides), so reset undoes them.
- **Row 22** – `usage.apply_personal` (~322) runs only on load, Hide and reset: a personally hidden panel stays hidden
  when the project starts using it in the same session; the Workspace row then says the family is hidden though the
  workspace shows it. Fix: run it when `used_functions` changes (after Build / undo / model update) – cheap, never in a
  draw that runs every redraw unless cached.
- **Row 25** – `core/start.py` ~77 / ~93 `int(w.get("later", 0))`, `load()` (~59) keeps any type: a damaged start file
  (`"later": "two"`, null, 1e400) gives a traceback at every start, welcome and What's new never show; a junk `last_run`
  ("0.2.x") makes What's new list all 137 functions. Fix: clean the types in `load` as `core/usage.clean` does; a junk
  version = no What's new (or "since the first version" with a cap) – never a traceback.
- **Row 26** – `core/start.py` `new_functions` gives the newest by `since`; only 1 entry has `changed=`. After 0.2.141 →
  0.2.159 What's new lists Make a crane, chart entry, four usage lines … while **workspaces, Client view, folded
  sections and the Fresing menu** sit in "… and 17 more". **Lead's decision:** (a) a new optional field
  `headline=True` on functions a user meets first (today: workspaces, Client view, the folded side panel, the Fresing
  menu, What's new, 0221's Show / Hide Blender's editors); What's new lists headline entries first, then the newest;
  (b) set `changed="<version>"` on functions a release made **visibly** better (from CHANGELOG: e.g. Fast 3-axis hole
  0.2.145, web export of the demo ~8× faster, the sea change ~3×, the Client view lock fixes …) and What's new shows them
  in a second short list "Better since …"; the count line says "N new, M better". The precheck's function check accepts
  the new field.
- **Row 34** – `usage.label` (~253): at the default side-panel width the favourites bar cuts labels ("Update to new
  revi…", "The same STEP twi…"); a favourite "Hide" sits right above the declutter question's own "Hide". Fix: an
  optional `short=` label per function (≤ about 16 characters; the precheck checks the length) used where room is tight,
  else the title; keep the declutter question visually apart (a gap / its own box).

## What to do

One fix per row as above, each with a test that failed before (rows 13, 19, 22, 25 and 26 are deterministic; row 34 a
screenshot at the default width via `tools/ui_screens.py`). Guide lines where the behaviour is described (usage, What's
new). Function-list entries keep their ids; `changed=` on the usage functions you made visibly different.

## Done when

- [ ] Rows 13, 19, 22, 25, 26, 34 fixed, each with its test; screenshots of the favourites bar and What's new checked
- [ ] What's new after 0.2.141 → newest shows the headline entries and a "Better since" list (test with the real list)
- [ ] Precheck green (new fields), full suite green; report filled in, merged, released

## Not in this task

The splash and Blender's own parts (0222 packages, Start & learn lane); lessons (0230); other 0209 rows.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
