# 0155 – Props for scale and the human figure: detailed and realistic

**Who:** worker · **Status:** waiting – starts after 0148 is merged (same surroundings code) · **Branch:** `task/0155-props-and-people`
**Started by:** lead chat, 16 Nov 2026 (owner: props, hand and human more detailed and realistic; a full human doing a
manual tool change) · **Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation".
Subagents allowed (CLAUDE.md section 2).
**Area:** Surroundings lane: `core/surroundings.py` (`PROPS`, `person()`, `prop_shapes`, sizes), `blender/surroundings.py` (props' meshes and materials), `ops_surroundings.py`, a small assets folder if a CC0 base is used, their tests.
**Do not edit:** the sea (`core/sea.py`) except where props sit on it; the demo model maker (0153); the Web 3D lane (0142/0143); `toolchange.py` (0156); milling (0146).

## Goal

The props that give a machine its scale – the person, pallet, forklift, car, container, etc. – look real in a close render instead of blocky stand-ins, and the person can be posed.

## What to build

1. **Person:** a realistic human figure (proportions, face without a real likeness, hands, work clothes: overalls or
   hi-vis vest, safety shoes, helmet optional, gloves optional), a few heights (1.65 / 1.75 / 1.85 m), a simple rig
   with **poses**: standing, walking, pointing, hands on a control panel, kneeling, operator at a machine; skin and
   cloth looks with subtle variation; 2–3 outfits (workshop, offshore orange, office).
2. **Every other prop** in `PROPS` gets the same care (bevels, real dimensions, decals without brands, wear): check the
   list and say which ones changed; add 2–3 useful ones for offshore and workshop scenes (e.g. a pallet with crates,
   a gas bottle rack, an IBC tank, a toolbox trolley) if missing.
3. Levels of detail: a light version for far away / many copies and the detailed one for close shots, chosen by
   distance to the camera at render (or a setting).
4. Old projects: their props update to the new look on load (or a "Refresh props" button) without moving.

## Rules

- **Licences:** only models you make in code, or openly licensed bases that allow redistribution in a GPL app and a
  public repository – e.g. Blender Studio's *Human Base Meshes* bundle (CC0) or MakeHuman exports (CC0); check and
  name the licence in `site/CREDITS.md` / the extension's credits. No real person's likeness, no branded clothing or
  tools (no logos), no downloaded manufacturer models (CLAUDE.md section 6).
- Keep the shipped size small: measure what the extension zip grows by (aim ≤ +5 MB); light meshes (props are seen
  from afar; the hand / human close up only in tool changes).

## Done when

- [ ] Tests (sizes, poses keep feet on the floor, prop count and names unchanged for old projects, LOD switch); render
      sheet of all props and poses at the same scale.
- [ ] Tooltips, guide (with new pictures of its section), PC-check line / tour stop, function list; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures in `tasks/img/0155_*`, triangles
      and zip size before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
