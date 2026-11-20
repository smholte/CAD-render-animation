# 0236 – Fixes from bug hunt 0209, group F: usage tracker and start (declutter, profiles, damaged start file, What's new, favourites)

**Who:** worker · **Status:** done (0.2.181) · **Branch:** `task/0236-usage-start-fixes`
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

**Chat / date:** Claude Code on the web (Sonnet), 20 Nov 2026

**What changed:** Row 13: `declutter.new` {function: session first offered}, `usage.note_new` at each start from the start file's What's new range; a panel with such a function is not asked about for `threshold` sessions. Row 19: a profile keeps the personal hides in its own `hidden` {ids} (new profile key), not in the workspace's `hide`; the importer adds them to the user's hides, so reset undoes them. Row 22: `usage.refresh_personal` from the depsgraph handler, at most every 2 s and only when something is hidden. Row 25: `core/start.load` cleans every field (junk version = none), `new_functions` gives nothing for a junk `since`. Row 26: `headline=True` (workspaces, Client view, folded sections, Fresing menu, What's new, Blender editors) listed first; `changed=` on milling.fast_map, web.moving, offshore.sea_cable and the three usage functions; What's new says "N new, M better" with a second list "Better since …" (`better_functions`). Row 34: `short=` (at most 16 characters, precheck-checked) on 48 functions; the question has two gaps above it. Guide and CHANGELOG updated.

**Tested and measured** (4-core web machine, Blender module): new tests in test_start, test_usage, test_usage_blender (rows 13, 19, 22, 25, 26, 34 incl. the real function list from 0.2.141); real-app `usage` test 31/31; screenshot of the bar and question at the default width looked at (labels whole). GitHub: full run 44806756204 green on the merged commit; main run 44810536040: release 0.2.181 published, Windows self-update and "Offer the release" green.

**Runs:** 3 full runs. (1) 44769321642 (0.2.176): everything green except the Windows PC-check line `web3d.small` ("page gave no places of its parts, ready PHONE frames 0"), failed again on re-run; known flake, fixed by task 0242. (2) a version clash with main (0.2.180) – merged and renumbered to 0.2.181; (3) 44806756204 green. Also: a new function from main (paths.draw_cable, help.blender_editors) had a long label – got `short=`.

**Open points / follow-up tasks:** The landing-page deploy after the release failed ("No artifacts named github-pages were found", run 44810536040) – not caused by this change; needs a Pages re-run. No subagents ran; the independent review was skipped (no Windows-only code). The profile's `hidden` key is new: an older app opens such a profile as a plain workspace. A profile exported before this change still has its hides inside the workspace's `hide`.
