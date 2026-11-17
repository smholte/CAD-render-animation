# 0199 – Start here: a "Fresing" menu in the top bar, a welcome that suggests the test tour, and What's new after an update (new and changed test models)

**Who:** worker · **Status:** open – **after 0198** (uses its `fresing.show_panel`; both touch the app template) ·
**Branch:** `task/0199-start-here-whats-new`
**Started by:** lead chat, 17 Nov 2026 22:30 (owner's wishes) · **Lane:** Start & learn (new)
**Area:** new `blender/welcome.py` + `blender/ui_topbar.py`; `blender/tour.py` (additive: version fields on sets and
stops, a "new and changed only" build), `blender/ops_tour.py`, `blender/updates.py` (the start-up check hands over
"first start of this version"), `core/functions.py` (additive field), `tools/ci_precheck.py` + a new
`tools/tour_versions.py` and `tests/data/tour_versions.json`; additive: preferences in `props.py`, guide, PC check
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

The owner (17 Nov, his words): *"I want some of the functions to be easier to find, like the test tour. For new users
it should suggest to start the test tour. When a new version of the app is updated and the test tour is updated, I
want it to show the new test models – the ones that are new and also the ones that were updated/changed. This allows
an existing user to easily learn new functions when they are added. So the existing user after an update gets a popup
at start to check out the new test models and possibly a short list of new functions."*

Today the tour, the demo and the PC check sit at the top of Blender's **Help** menu (owner's screenshot 17 Nov:
"Fresing Render user guide, Check for Fresing Render updates, PC check…, Make / Open test tour project, Make / Open
demo project", then Blender's own Manual, Support …). A new user does not look there.

## What to build

1. **A "Fresing" menu in Blender's top bar** (beside File, Edit, Render, Window, Help – always visible, so it is the
   one place to find the app's own things). Entries, in this order, each with an icon and a tooltip:
   *Take the test tour* (opens the tour of this version; makes it first when there is none, with the usual progress
   and Cancel) · *What's new in 0.2.NNN* · *Show the Fresing panel* (0198's `fresing.show_panel`) · separator ·
   *Demo project* (make / open) · *User guide* · *PC check…* · *Check for updates* · separator · *Welcome screen…*.
   The Help menu keeps its Fresing lines (the owner knows them there) – no second copy of any operator, only menu
   lines.
2. **Welcome for a new user:** the first start in a settings folder (no "last version run" stored) shows a small
   window: one line on what the app is, one on the test tour ("every function on small test models; making it takes
   about N minutes on a PC like yours" – N from 0059's measured build time, said as an expectation), buttons **Take the
   test tour** / **Later** / **Don't show this again**. *Later* asks again at the next start, at most three starts.
   Never in background, the PC check, the self-test, the render kit or the tests (an environment flag the tests and
   the kit already set, or a new one); never on top of a double-clicked project file before it is open – show it
   after.
3. **What's new after an update:** the first start of a newer version than the last one run shows **one** popup:
   - title "What's new in 0.2.NNN" (when several versions were skipped: "since 0.2.MMM");
   - **a short list of new functions** (at most ~8 lines, newest first, each with *Show in guide*), from a new
     `added="0.2.NNN"` field on each function entry in `core/functions.py`; a line for a function marked
     `changed="0.2.NNN"` says "improved"; a link to the full release notes (`changelog.json`, already published with
     every release) for the rest;
   - **the test models:** "3 new test models, 2 changed" with their names, and **Open the tour of the new and changed
     models** (builds only those sets – much faster than the whole tour), **Whole tour**, **Later**. *Later* keeps
     What's new in the Fresing menu until opened once.
   - The tour itself marks sets and stops **New** / **Changed in 0.2.NNN** (in the Test tour panel's list and on the
     hub), so the user sees what to look at.
   - Only shown after a real update (the version went up), never after a downgrade or re-install of the same version.
4. **Version fields that cannot be forgotten:** each `@tour_set(...)` and each `stop(...)` gets `added=` and
   `changed=` versions. Backfill the existing 45 sets and their stops from git history / CHANGELOG (`git log` on
   `tour.py` and the test-model makers; best effort, say in the report how sure each is – at least the last ~15
   versions right). Then make it automatic for later tasks: `tools/tour_versions.py` records a fingerprint per set
   (its build function's source, its stops' source, its models' file hashes) in `tests/data/tour_versions.json`;
   **the precheck fails** when a fingerprint changed but `changed=` was not raised to the branch's new version, with
   the line to write in its message (and the command that re-records the file). The same check for `core/functions.py`
   entries: a new entry without `added=` fails. Add the rule in one line to CLAUDE.md (tour section) and to
   `tasks/TEMPLATE.md`'s "Done when".
5. **The usual parts of a visible change:** tooltips; guide chapter "Start here" (the Fresing menu, welcome, What's
   new); function entries (`help.start_here`, `help.whats_new`); a test-tour stop; a PC-check line if Windows can
   break it (the popup at start).

## Done when

- [ ] Real-app test: a fresh settings folder shows the welcome once; *Later* three times then never; *Don't show
      again* never; *Take the test tour* starts the tour build.
- [ ] Real-app test: a settings folder that last ran an older version (written by the test) shows What's new with the
      right functions and sets; *Open the tour of the new and changed models* builds only those sets (count and time
      in the report); a second start shows nothing; the same version again shows nothing.
- [ ] The Fresing top-bar menu with every entry working; Help menu unchanged.
- [ ] Precheck test: a changed tour set without a raised `changed=` fails with a clear message; a new function entry
      without `added=` fails; re-recording fixes it.
- [ ] Backfilled versions for all sets, stops and function entries (how sure: in the report).
- [ ] Tooltips, guide chapter, function entries, tour stop, PC-check line (or why none); screenshots of the menu and
      both popups looked at (Windows display scaling: no cut-off text at 100–200 %, as 0177 checked for the kit).
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Lessons (Show me / Build it yourself), the guide inside the app, workspaces (0062, Learning lane). The usage tracker
(0181). Any change to what the tour's stops show.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
