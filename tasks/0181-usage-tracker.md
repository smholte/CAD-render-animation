# 0181 – Usage tracker on the PC: favourites bar, declutter prompts, time saved, where the time goes

**Who:** worker · **Status:** done (0.2.158, 18 Nov) (0199 is done, 0.2.155; it was "after 0199" because both add to `core/functions.py`, the Help menu and the tour; 0199's precheck rules
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

## Design (worker, 18 Nov 2026)

- **Counting:** `panels.install` wraps every `fresing.*` operator (`usage.wrap`: its `invoke`, else its `execute`); a
  button inside a button counts once; a click counts for ONE function id – by the button's kind (`BY_PROP`:
  `block_add`, `queue_add`), else the panel it was clicked in (`panels` puts `fr_panel` on each panel's layout with
  `context_string_set`), else the first entry naming the button; `ALSO` adds buttons no entry names
  (`apply_rules` → `looks.materials`). Opening a panel counts for the panel. Not counted: background runs,
  `FRESING_NO_USAGE`, simulated events unless `FRESING_USAGE_TEST`.
- **File:** `<config>/fresing_usage.json` (next to 0199's start file); broken → `.broken` copy, newer → `.newer` copy,
  fresh state. Written every 30 s when changed, at a project save, at exit.
- **Session** = one app start (`usage.start`, a timer 1 s after start): sessions + 1, the bar sorted (only then).
- **Bar:** `FRESING_PT_favourites` under the Workspace row (proposal: not in the 3D view's header – Make sits there
  already). Pins first, then the most used (≥ 2 uses), 6 by default (5–8). Side-panel favourite = go there (its
  section tab, opened to its panel, the lesson highlight points at the button for 6 s); a menu favourite runs.
- **Declutter:** panels of `places.PLACES` only (never a section, a menu, the import / help / panel families); after
  `threshold` (10) sessions without a use of the panel, its functions or a panel under it; all its functions shown,
  none used by the project; one per session, each panel once. Hide → `state["hidden"]`; `workspaces.PERSONAL["hide"]`
  = hides minus what the project uses; applied in `_hidden` on top of every workspace except Full access.
- **Stages:** families → Import & structure, Looks, Motion & rigging (motion, machines, cnc, milling, offshore,
  lifting), Scene & surroundings (scene, house), Animation (animation, video), Render & export (queue, web); idle > 2 min
  not counted.
- **Time saved:** `Function.manual_estimate = ("use" | "part", seconds, "what by hand")`, checked by `problems()`.
- **Profiles:** `Workspace.extra` = `favourites` (+ `usage` when ticked) in the own-workspace file; `to_json()` (what a
  project keeps) never holds `usage`; an import's library copy drops it too.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 18 Nov 2026 · released as **0.2.158** (0201 and 0202 took 0.2.156 / 0.2.157
meanwhile).

**What changed:** see Design above. New files `core/usage.py`, `blender/usage.py`, `ops_usage.py`, `ui_usage.py`,
`tests/test_usage.py` (30), `tests/test_usage_blender.py` (12), `tools/ui_test_usage.py` (real app, 24 checks, group
scenes). Additive: `panels.install` wraps the operators and sets `fr_panel`; the panel-toggle counts an opening;
`workspaces.PERSONAL` in `_hidden`; `Workspace.extra` (profile parts) in `core/workspaces.py`; `Function.manual_estimate`
(+ a precheck rule); 4 function entries (`usage.favourites`, `usage.declutter`, `usage.my_usage`, `usage.profiles`);
My usage in the Fresing menu and at the end of Help; "Back as it came" in the Workspace panel when the user hid
something; the PC check's two operators are wrapped too; `lock.ALLOWED_PREFIXES` + `fresing.usage_`; tour stop
`usage` (crane set changed); PC-check line `app.usage`; guide chapter "Your usage and the favourites bar" with two
pictures; CLAUDE.md (layout + one lesson learned).

**Proposals the owner can change:**
- The bar sits in the side panel under the Workspace row, not in the 3D view's header (Make is there already).
- A favourite in the side panel *goes there* (its section tab, opened, its button pointed at for 6 s) rather than
  pressing the button: most buttons need a selected row or settings above them. A menu favourite (PC check, updates)
  runs.
- Personal hides apply in every workspace except Full access (also in All functions, the default).
- "Not now" = not asked about that panel again; "Don't ask again" = no more questions (switch back in My usage).
- Settings-only functions (no button) are never on the bar; their use is seen through opening their panel.
- **Time-saved guesses for the owner to adjust** (`manual_estimate` in `core/functions.py`): Material groups / Sort
  parts into groups 5 s per part · Exploded view 20 s per part · Assembly sequence 30 s per part · Model update 30 min ·
  Cylinder 10 min · Way cover 15 min · Hose 20 min · Cable 30 min · Turntable 15 min · Product video 60 min · Clash check
  20 min · Web 3D model 2 h · Every paint scheme 10 min · Make a toolpath 60 min (per use). Per part = the mesh objects
  in the project at the click.

**Tested and measured:**
- Cost per click, web machine (4 cores, Blender as a module): one button 0.013 ms without counting, 0.024 ms with;
  `record()` alone 0.008–0.014 ms; the PC-check line measured 0.009 ms. No measurable cost.
- Real app (xvfb, test crane): bar sorted at a start, a real click on a favourite opens tab 3 + Logos & stickers, a
  real click on Sort parts into groups counts for Material groups with its panel known (`fr_panel` reaches the
  operator) and ~10 min saved for 106 parts, Hide hides the asked panel, My usage opens, Back as it came: 24/24.
- GitHub: 3 full runs. Run 1 red: a test counts the Help menu's `_draw_help` functions and mine had the same name
  (renamed). Run 2 green; 0202 took 0.2.157 meanwhile → merge + 0.2.158, run 3 green (44306659788).
- No independent tester agent (not Windows code; the wrap of every operator is covered by a test that checks every
  `fresing.*` operator and by the full real-app suite, which clicks hundreds of them).

**Open points / follow-up tasks:**
- On the owner's PC: after a few starts the bar should appear; after 10 starts the first question.
- Counting a *setting* change (not a button) is not done; a panel opening stands in for it.
- 0208 (learn as you go) can start: it extends the declutter question (`usage.answer`, `ui_usage.py`).
