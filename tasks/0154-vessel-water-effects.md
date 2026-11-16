# 0154 – Water effects of a working vessel: wake, bow wave, propeller wash, thruster jets

**Who:** worker · **Status:** running · **Branch:** `claude/nifty-mendel-78lbia`
**Started by:** lead chat, 16 Nov 2026 (owner: "more details to the ship itself") · **Model:** Opus · effort High ·
**Place:** Claude Code on the web, environment "CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Sea lane: `core/sea.py`, `blender/surroundings.py` (the sea, its foam/white caps), `blender/vessel_motion.py` (speed, heading, a manoeuvre setting), the propeller / thruster joints' drive from that setting, their tests, the guide's sea and vessel sections.
**Do not edit:** the demo model maker (`demo_model/`, done by 0153), the Web 3D lane (0142/0143 – the page's version of these effects is a later task), cable code, milling.

## Goal

When the vessel sails ahead or holds position with its thrusters, the water shows it: a wake and foam trail behind the propellers, a bow wave, hull wash along the sides, and white jets / boiling water at a tunnel thruster when it runs – and the propellers turn with it.

## What to build

1. **What the vessel does:** a setting per saved scene / animation step: *still*, *ahead at N knots* (the existing vessel
   speed), *sideways / DP* (bow and stern thrusters pushing, azimuths steered), *turning*; it drives the propeller and
   thruster joints (rpm, steer angle) and the effects below.
2. **Ahead:** Kelvin-wake pattern (the ~19.5° wedge) and a turbulent foam trail behind the propellers that fades with
   distance; a bow wave and hull-side wash in proportion to speed; as displacement + foam in the sea shader (EEVEE and
   Cycles) or a light particle/mesh layer – measure frame time on the demo.
3. **Thrusters:** at a running tunnel thruster a jet of white/boiling water on the side it pushes to, at a running
   azimuth a boil and wash in its direction; spray optional; strength by rpm.
4. Works with vessel motion (0085), sea states, weather (0109), the sea cut-away (0081/0148: under water a faint
   bubble plume optional).
5. The demo: one short stage or the existing transit shot uses *ahead*, one uses *sideways / DP*.

## Rules

The vessel is **invented** (CLAUDE.md section 6): no real vessel's or the owner's employer's design, names or
pictures; generic features every offshore construction / cable-lay vessel has. Test models one solid per part
(`geom.write_step`). Every tour animation keeps 0 clashes; the demo's clash test stays green.

## Done when

- [ ] Tests (pattern angle and fade from the formula in plain Python; joints driven by the setting; effects off when
      still); pictures ahead / DP / still; frame time before/after on the demo (EEVEE and Cycles preview).
- [ ] Tooltips, guide, PC-check line / tour stop, function list for anything new the owner sees; GitHub run green;
      merged; version (CLAUDE.md section 7); report with small before/after pictures (invented demo only) in
      `tasks/img/0154_*` and the cost (import time, triangles, frame time) before/after.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
