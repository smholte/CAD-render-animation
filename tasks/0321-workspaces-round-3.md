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

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
