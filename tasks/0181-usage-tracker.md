# 0181 – Usage tracker on the PC: favourites bar, declutter prompts, time saved, where the time goes

**Who:** worker · **Status:** running (18 Nov) (0199 is done, 0.2.155; it was "after 0199" because both add to `core/functions.py`, the Help menu and the tour; 0199's precheck rules
for `since=` / `changed=` apply to this task's entries). 0062 is done: see its report's pointers for 0181
(`panels.OPEN` / `fresing.panel_toggle` = where opening a panel can be counted; `workspaces.used_functions(scene)` = what
a project has) ·
**Branch:** `task/0181-usage-tracker`
**Started by:** lead chat, 17 Nov 2026 (owner's document "UI workspace presets & adaptive usage tracker", part 2) ·
**Lane:** new **Usage lane**: new files `core/usage.py`, `blender/usage.py`, `blender/ops_usage.py`, `blender/ui_usage.py`
and their tests; additive: `props.py`, `core/functions.py` (a field), the operator registration (one counting hook),
the Help menu, the tour, the PC check, the guide.
**Model:** Opus · effort Medium (lead confirms when it starts) · **Place:** Claude Code on the web, environment
"CAD-render-animation".

## Goal

The app learns which functions each user really uses – **on his own PC only, nothing is ever sent** – and uses that
to keep his panel short: a favourites bar with his most-used buttons, a quiet offer to hide what he never uses, and a
small "My usage" window (time saved, where the time goes).

## The owner's wishes (document of 17 Nov 2026, lead's notes in brackets)

**Tracking (local, per Windows user):**
- **Click and frequency counter:** how often each function, panel and button is used, across sessions. (Count per
  function id of `core/functions.py`, so counts survive renamed buttons; a session = one app start.)
- **Time-saved calculator:** automated actions (auto bolt grouping, auto material assignment …) and the estimated
  manual clicks / hours they saved. (**Always labelled as an estimate**, with how it is worked out: each automated
  function gets a `manual_estimate` in its function-list entry – steps and seconds per part or per use – written by
  the worker, listed in the report for the owner to adjust. CLAUDE.md section 1: never a guess shown as a measurement.)
- **Session heatmap:** which stage takes the user the most time – Import → Rigging → Environment → Render. (Stages from
  the families: Import & structure, Looks, Motion & rigging, Scene & surroundings, Animation, Render & export; time
  counted to the stage of the last used function; idle time – no input for 2 min – not counted. Shown as simple bars.)

**Panel help:**
- **Favourites bar:** the user's top 5–8 functions pinned to a quick-access bar (top of the Fresing tab; the 3D view's
  header if it fits – worker proposes). (**Re-sorted only at app start, never during a session** – buttons that move
  while you work are worse than no bar. The user can pin an item so it stays, unpin, and switch the bar off.)
- **Declutter prompts:** a tool or panel with 0 uses after a threshold (default 10 sessions, a setting) gets a quiet
  prompt: "You haven't used [Tool] recently. Hide it to clean up your workspace?" (**Never for a function the open
  project uses** – 0062's rule; at most one prompt per session; each tool asked once; buttons Hide / Not now / Don't
  ask again; hiding goes through 0062's workspace mechanism – a personal layer on top of the workspace, so the built-in
  workspace itself is never changed.)
- **One-click reset / restore:** "Show all" (0062 has it) and "Back to the workspace as it came" (drops the personal
  hides and pins).
- **Exportable .json profiles:** a user or a team saves and loads its own workspace with the favourites bar and the
  hidden items as one file in the library (0062's own-workspace file, extended). (Usage counts are **not** in it
  unless the user ticks "include my usage counts".)

**Privacy and control (lead):** one file in the user's own settings folder; no network code in the module (a test
checks it imports no network library); a switch "Track my usage" (on by default – owner may change), "Clear my usage
data", and the guide says what is stored and where.

## Done when

- [ ] Counting per function id for every Fresing button and panel opening, sessions counted, idle time left out;
      counts kept across updates; a broken or newer usage file never stops the app (starts empty, keeps a copy).
- [ ] Favourites bar (top 5–8, sorted at start only, pin / unpin / off); declutter prompts with the rules above;
      reset; profile export / import with and without counts.
- [ ] Help > My usage: counts, time per stage as bars, time saved marked "estimate" with its basis; Clear my usage data.
- [ ] No measurable cost per click (measured on the web machine: the counting hook, before / after, in the report).
- [ ] Tests (the counting, the threshold, the prompt rules, the file round trip, no network imports); real-app test of
      the bar and a prompt; screenshots checked with `tools/ui_screens.py`.
- [ ] Tooltips; function-list entries + guide anchors; guide chapter "Your usage and the favourites bar"; test-tour
      stop; PC-check line.
- [ ] GitHub green incl. Windows; merged to `main`, next free version, released; report filled in; `TASKS.md`.

## Not in this task

Sending anything off the PC (never). Team-wide usage statistics. The workspaces themselves (0062). Changing what a
button does.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
