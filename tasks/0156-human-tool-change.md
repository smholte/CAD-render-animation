# 0156 – Manual tool change: a realistic hand, and a full human doing the change

**Who:** worker · **Status:** waiting – starts after 0155 is merged (uses its human figure) · **Branch:** `task/0156-human-tool-change`
**Started by:** lead chat, 16 Nov 2026 (owner: props, hand and human more detailed and realistic; a full human doing a
manual tool change) · **Model:** Opus · effort High · **Place:** Claude Code on the web, environment "CAD-render-animation".
Subagents allowed (CLAUDE.md section 2).
**Area:** Tool-change lane: `blender/toolchange.py` (the hand "FR hand", manual changes), `core/toolchange.py` (the timed phases), the operator's figure from 0155, `ui_gcode.py` (its settings), their tests, the guide's tool-change section.
**Do not edit:** milling / material removal (`machining.py`, 0146), the ATC code paths unless shared helpers need a parameter, the surroundings (0155 done before), the Web 3D lane.

## Goal

A manual tool change looks like a real operator doing it: a detailed gloved hand (as today, but realistic), or – a new choice – a whole person who steps to the machine, opens the door, holds the tool holder, releases it with the drawbar button, puts the new tool in, closes the door and steps back.

## What to build

1. **Hand:** the app-made gloved hand (`HAND_NAME = "FR hand"`, `GRIP_BELOW_GAUGE`, `PULL`) made realistic: glove
   shape and material, fingers that close round the holder, the other hand at the drawbar button optional.
2. **Full human** (new choice next to *Hand* / *None*): the 0155 figure with an animation built from the change's
   timed phases (`core/toolchange.py`): walk in from a set spot, open the machine's door if it has one (a joint the
   owner picks, else skip), reach, grip, press the release, pull the tool down, put it in the rack / on a table, take
   the new one, insert, release, close, step back. Inverse kinematics for the arms on the holder's place (Blender IK
   constraints, baked to keys at Build, works with scripts off). The pause length (manual-change pause, 0–5 s) grows
   automatically to what the person needs, and the report says the time per change.
3. The person never walks through the machine or the table: a clear path to a stand spot in front of the spindle
   (the owner can move the spot); the clash check knows the person (0 clashes on the tour's tool-change set).
4. Works with the queue, saved scenes, the product video; the person can be hidden for a shot.

## Rules

- **Licences:** only models you make in code, or openly licensed bases that allow redistribution in a GPL app and a
  public repository – e.g. Blender Studio's *Human Base Meshes* bundle (CC0) or MakeHuman exports (CC0); check and
  name the licence in `site/CREDITS.md` / the extension's credits. No real person's likeness, no branded clothing or
  tools (no logos), no downloaded manufacturer models (CLAUDE.md section 6).
- Keep the shipped size small: measure what the extension zip grows by (aim ≤ +5 MB); light meshes (props are seen
  from afar; the hand / human close up only in tool changes).

## Done when

- [ ] Tests (hand grip place on the holder, phases in order, IK reaches within a few mm, walking path clear, 0 clashes,
      the pause grows); a short clip of one change with the full human (test mill), cropped small.
- [ ] Tooltips, guide (with new pictures of its section), PC-check line / tour stop, function list; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures in `tasks/img/0156_*`, triangles
      and zip size before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
