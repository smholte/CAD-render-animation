# 0157 – People in the scene: walk paths, carry items, actions and meetings

**Who:** worker · **Status:** waiting – starts after 0155 is merged (uses its human figure and rig); may run beside 0156
if their files stay apart (say so in TASKS.md when starting) · **Branch:** `task/0157-people-paths-actions`
**Started by:** lead chat, 16 Nov 2026 (owner) · **Model:** Opus · effort High · **Place:** Claude Code on the web,
environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2): interfaces first, an independent tester.
**Area (new People lane):** new `core/people.py` (paths, timing, gait, action list – no Blender), new
`blender/people.py`, `ops_people.py`, `ui_people.py` (a sub-panel, e.g. 5 Scene & Render > People or 6 Animation >
People – follow `blender/ui.py`'s layout rules), additive lines in `props.py`, `animation.py` (Build bakes the people),
their tests, the guide, tour stop, PC-check line, function list.
**Do not edit:** `toolchange.py` (0156), `core/surroundings.py` / props' meshes (0155 owns the figure: import and use
it, ask the figure's API only), the Web 3D lane (0142/0143), sea / demo code.

## Goal

The owner places people in a scene and tells them what to do along a path – walk, stop, carry, put down, greet, talk –
and Build turns it into a believable animation, e.g.: *a person walks in carrying a small toolbox, stops next to
another person, puts the box down, greets them (handshake or wave) and starts talking.*

## What to build

1. **People:** add a person (0155's figure: outfit, height, a name the owner gives), as many as wanted; place by
   clicking on the floor / deck (snaps to the surface below, rides on a moving deck with vessel motion – 0085).
2. **Path:** click points on the floor (a curve shown in the view, editable afterwards: move / insert / delete points),
   smooth corners; the person keeps feet on the surface (ray down per step, stairs not needed now – say if a slope
   is too steep).
3. **Actions along the path** – a list per person, in order, each with a place on the path (at a point / at the end) and
   a duration where it applies: *walk* (gaits: **stroll, walk, brisk, carry-walk, run**, each with its speed and
   stride; the stride matches the speed so feet do not slide), *stop*, *turn to face* (a point, another person, a
   part), *pick up* / *put down* (an item), *wave*, *greet* (handshake with another person: both arrive, both reach,
   hands meet – timing worked out together), *talk* (idle gestures, head turns, a slight sway; two people talking face
   each other and take turns), *point at* (a part), *look at*, *idle*, *operate* (hands on a panel / part – reuse
   0156's arm reach if merged, else hands to a point with IK).
4. **Carried items:** a menu of items (from 0155's props + small ones: toolbox, clipboard, tablet, hard hat, cable
   drum, crate, spanner, hose) – carried in one or both hands with the right grip and arm pose, put down where the
   action says (on the floor / a table / a part's top), picked up again later.
5. **Waiting for each other:** an action can wait for another person's action ("greet when Anna arrives") so meetings
   line up whatever the walking times.
6. **Build:** everything baked to keys (works with scripts off, in the queue, saved scenes, product video, test tour);
   the people's paths avoid the machine: a warning when a path runs through a part (the clash check knows people,
   0 clashes on the tour set); a Preview slider like the assembly sequence's.
7. **Speed:** the rig and keys stay light – measure frame time with 1, 5 and 20 people on the demo deck.

## Done when

- [ ] The owner's example works as a test-tour stop (two people, toolbox, stop, put down, greet, talk) and as a test
      that checks the order, the meeting time, feet on the floor (no sliding above a few mm per step), the box on the
      floor after "put down", 0 clashes.
- [ ] Tests for paths (length, smoothing, surface following), gaits (speed ↔ stride), waits between people, carry
      grips, old projects without people unchanged.
- [ ] A short clip of the example (test model or the demo deck) in `tasks/img/0157_*`; frame time with 1 / 5 / 20
      people.
- [ ] Tooltips, guide, PC-check line, function list; GitHub run green; merged; version (CLAUDE.md section 7).

## Not in this task

Crowds / random people, stairs and ladders, sitting, people on the web page (a later Web 3D task), lip-sync / voices.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
