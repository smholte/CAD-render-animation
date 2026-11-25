# 0321 – Workspaces round 3: Welding, Machine builder, Video producer, Houses; Sales may move joints

**Who:** worker · **Status:** running · **Branch:** `claude/cad-render-animation-0321-yl8i1m`
**Started by:** lead, 24 Nov 2026 (owner 11:44: "make a separate welding workspace. This will only be the rendering
options and weld placement, weld symbols and later the 2D drawings. Optionally other functions if advised." – "I agree
with the 3 additional workspaces you suggested" – "Sales workspace is allowed to move joints.") ·
**Model:** Opus · effort Medium
**Area:** Start & learn lane (workspaces part) – `core/workspaces.py` (`BUILTIN`), `blender/workspaces.py`,
`core/functions.py` (`workspaces=`, `FAMILY_WORKSPACES`), the Workspace drop-down; tests, guide, tour stop, PC check,
CHANGELOG. **Not:** `welcome.py` / the first-start set-up (0276 runs beside this – see 4), `lock.py`.

## Goal

Four more ready workspaces, each showing only what that job needs, and Sales can pose the machine for a client.

## Background

- 0294 (0.2.226) built Essentials, Sales, Quick render, Animator, Reviewer, favourites on top; its report proposed
  **Machine builder** (import, structure, place, joints, cylinders, mechanisms, way covers, hoses and drag chains,
  tracks, Set-up window, clash check), **Video producer** (animation steps, camera paths, labels, picture cards, music,
  brand kit, watermark, captions, queue) and **Houses** (House from House Planner, surroundings, weather and time,
  light, camera, picture, turntable, 3D page). The owner agreed to all three.
- 0294's open point: **Sales hides, it does not lock**. The owner: Sales **may move joints** – no lock wanted.
- Welds: 0319 (0.2.231) placement + looks; 0320 (may run beside this) adds weld symbols + a weld list; 2D drawings later.

## What to do

1. **Welding** workspace: import, the render options (Looks for the parts, scene, light, camera, Picture / Render this
   view), **3 Looks > Welds** (placement, types, looks, finish, rust), weld symbols + weld list (if 0320 is merged; if
   not, 0320 adds them – say so), and a greyed "2D drawings – coming later" line only if the app already shows such
   placeholders (otherwise leave it out). Propose (do not add) other functions that would help a welding engineer –
   e.g. measuring (0322), cutaway section, exploded view – in the report; add one only if it is clearly needed to place
   welds (say why).
2. **Machine builder**, **Video producer**, **Houses** as 0294 proposed them (adjust where a function name has changed).
3. **Sales**: show joint moving – the joint sliders / poses of 4 Motion (and the Lead motions drop-down when 0309 is
   merged) – structure editing stays hidden. No lock.
4. Each new workspace: an icon, a one-line tooltip, a star for favourites, a guide section, the Learning hub's
   chapter list if 0304's chapters exist (they do not yet – leave a note). If **0276** is merged before you, map its
   set-up ticks to the new workspaces where they fit (e.g. a fabrication / welding tick if it has one); if not, say in
   the report what 0276's mapping should add.
5. Tests (each workspace shows exactly its functions), one tour stop (switching to Welding), a Full PC-check line.

## Done when

- [ ] Welding, Machine builder, Video producer, Houses in the drop-down, each with its functions (tests)
- [ ] Sales shows joint moving; structure editing still hidden
- [ ] Guide + tour + PC check; tests added/updated; full suite passes; screenshots checked; version fields; owner's
      test steps; merged, release

## Not in this task

The first-start set-up (0276), weld symbols / list (0320), measuring (0322), 2D drawings, locks (`lock.py`).

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 24 Nov 2026 · branch `claude/cad-render-animation-0321-yl8i1m` · 0.2.240

**What changed:**
- **Four workspaces** (`core/workspaces.BUILTIN`, lists in `core/functions.TASK_WORKSPACES`, keys `welding`, `builder`,
  `video`, `houses`): Welding 69 functions, Machine builder 91, Video producer 78, Houses 69 (counts with the common
  part: panel, learning, help, settings). Each has a tooltip (its note), a star (the 0294 drop-down), and an **icon**:
  every workspace now has one (`W.ICONS`; own workspaces `USER`; the one in use keeps the tick).
- **Welding:** import (+ update, up axis), the tree (to pick the two parts of a weld and hide what is in the way – the one
  addition beyond the brief, needed to place welds), materials, find, rules, rule sets, finishes, rust, paint faces,
  **Welds**, light look, surroundings, light, camera, blur, picture, Render this view, image shapes, saved scenes.
  Weld symbols + list: **0320 is not merged** – it should add `workspaces=("welding",)` to its function entries (one
  word each). No "2D drawings – coming later" line: the app shows no such placeholders (none found), so left out.
- **Machine builder / Video producer / Houses** as 0294 proposed (function names as they are now; Machine builder also
  has hoses' draw / route / avoid / kinds, Video producer the weather step and people, Houses night, props, the queue's
  picture and the 3D page's tools).
- **Sales moves joints** (owner 24 Nov): a new function `joints.move` (the slider, CAD (0) / Min / Max). 4 Motion >
  Joints in a workspace that shows moving but not adding (`ui_motion.can_edit_joints`) draws only the list, the picked
  joint's slider and CAD (0) / Min / Max – no Add, −, Set-up, limits, couplings; a follower says which joint to move.
  Sales also got Poses and Everything back to CAD position. No lock. The Lead motions drop-down (0309) was already in
  every workspace.
- **0276's set-up** (merged before this): four more work ticks (Welding and fabrication, Making machines move, Videos
  of machines, Houses from House Planner) → their workspaces and hub chapters (Look, Motion, Output, Output); the ticks
  now in two columns (13).
- Guide: the workspace table, section `more-workspaces`, `move-joints` (Sales), the set-up's tick list, picture
  `workspace_stars.png` (from the real-app run, with the icons). Tour stop **workspace_welding** (welds set), the
  workspace stop's Sales check updated; PC-check line **workspace.round3** (+ workspace.essentials' Sales check);
  real-app `ui_test_workspaces2.py` Sales check updated.

**Tested and measured** (4-core web machine, test crane / weldment): `tests/test_workspaces_round3.py` (15, new: each
workspace exactly its functions and panels, Sales draws sliders without add/remove/set-up and the joint moves, the
drop-down's icons, the set-up ticks), `test_workspaces_essentials.py`, `test_functions.py`, `test_first_setup.py`,
`test_user_guide.py`; tour stops welds + workspace_welding + workspace (Go + check); PC-check lines workspace.round3 +
workspace.essentials OK (Sales: the boom's tip moved 2,605 mm at 20°); real-app workspaces2 19/19; a real-app
screenshot of 4 Motion > Joints in Sales looked at (list, slider, CAD (0) / Min / Max, Poses below).

**Open points / follow-up tasks:**
- **0320:** add `workspaces=("welding",)` to the weld-symbol and weld-list entries.
- **0304** (Learning hub chapters per workspace): chapters do not exist yet – Welding, Machine builder, Video producer
  and Houses need one each there.
- Proposed for Welding, **not added** (owner decides): **Measure** (0322 – weld lengths, gaps), **Slice** (a weld
  inside a box section), **X-ray** (welds behind parts), **Exploded view** (welds of a sub-assembly shown apart),
  **Turntable** and **Render queue** (several weld pictures in one go).
- Sales' icon is Blender's "FUND" (a heart); easy to change in `W.ICONS`.
