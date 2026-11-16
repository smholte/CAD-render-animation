# 0153 – Demo vessel: a detailed hull, superstructure, propulsion and its looks

**Who:** worker · **Status:** running (16 Nov) · **Branch:** `ccr-82ef1269-tt9p0w` (the web session's branch)
**Started by:** lead chat, 16 Nov 2026 (owner: "more details to the ship itself") · **Model:** Opus · effort Medium ·
**Place:** Claude Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Demo models lane: `fresing_render/demo_model/` (params, geom, the hull and new parts), `demo.py` (looks, joints of the new parts, the stage list only where needed), `blender/marine_looks.py` (use, add only if needed), the demo's tests (as 0145 split them).
**Do not edit:** the sea / surroundings code (`surroundings.py`, `core/sea.py` – 0148, then 0154), the Web 3D lane (0142/0143), `paths*` / cable code, milling (0146).

## Goal

The demo's vessel looks like a real offshore cable-lay vessel close up, not a box with a deck: shaped hull, a proper superstructure, propulsion you can see turning, and believable paint, wear and growth.

## What to build

1. **Hull:** a shaped bow (flare, optional bulbous bow), a stern with a skeg / transom, bilge keels, a slight sheer;
   still a ruled loft (0074: smooth lofts mesh 5× heavier). Moon pool optional.
2. **Superstructure and deck outfitting:** accommodation block with window rows, bridge with wings and bridge windows,
   mast with radar / antennas / lights, funnel(s), lifeboats or rescue boat in davits, railings along the deck edge,
   a helideck optional, a deck crane (its own joints, parked), bollards, fairleads, hatches. Keep the cable-lay
   spread and its clearances as they are (the stages and the clash test must not change).
3. **Propulsion:** two azimuth thrusters (or shaft propellers + rudders) at the stern, one or two **tunnel bow
   thrusters** (openings in the hull, propellers inside), a retractable azimuth optional. Each propeller and azimuth
   gets a joint (turn / steer) so the animation and 0154's water effects can drive them.
4. **Looks:** hull paint above the waterline, boot-top stripe, red antifouling below, draft marks and a name plate
   (invented name, decals of 0024), non-slip deck paint, steel and galvanised outfitting, glass; wear: rust streaks
   from scuppers and hawse pipes, scratches on the side where fenders touch, **marine growth below the waterline**
   (0116's `paint_marine_growth`, banded by `fr_waterline_z`).
5. The demo's shots and cameras still frame well; one new camera for the stern / thrusters and one along the hull side.

## Rules

The vessel is **invented** (CLAUDE.md section 6): no real vessel's or the owner's employer's design, names or
pictures; generic features every offshore construction / cable-lay vessel has. Test models one solid per part
(`geom.write_step`). Every tour animation keeps 0 clashes; the demo's clash test stays green.

## Done when

- [ ] Model maker tests (sizes, one solid per part, joint count), the demo builds and its tests pass; the clash test 0
      rows; triangles and Make demo time before/after (aim: Make demo ≤ +20 %).
- [ ] Tooltips, guide, PC-check line / tour stop, function list for anything new the owner sees; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures (invented demo only) in
      `tasks/img/0153_*` and the cost (import time, triangles, frame time) before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
