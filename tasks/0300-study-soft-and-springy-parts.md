# 0300 – Study + prototype (findings only): soft and springy parts – rubber that squeezes, springs that compress – set up in a few clicks

**Who:** worker · **Status:** done 23 Nov (findings, report and page on the branch, not merged) · **Branch:** `task/0300-study-soft-parts` (branch only, never merged;
every push `[skip ci]`)
**Started by:** lead, 23 Nov 2026 (owner's list, 23 Nov 19:39: "Simulated materials like rubber getting squished, spring
and such. And again, a way to add it with a few clicks or possibly a popup window with a few steps.") · **Model:** Opus ·
effort High
**Area:** findings only; prototype code in new files on the branch (e.g. `tools/soft_proto/`); reads `cylinders.py`,
`joints.py`, `flex.py`, `core/part_types_data.py` ("Springs", "Gas springs & shock absorbers"), 0282's `form_window.py`.
Clips and the page in `tasks/0300_page/`. Not a code slot.

## What to find out

A. **Kinds and how each moves:** coil springs (compression, extension, torsion – pitch changes, wire Ø and coil count
   kept; ground or closed ends), read from the CAD spring (outer Ø, wire Ø, turns, free length from its mesh) or typed;
   gas springs / dampers (two rigid parts like a cylinder?); rubber – bushings, buffers / bump stops, seals, mounts,
   bellows / gaiters (folding), tyres on the ground – squeezed with the volume kept (bulging) when two parts come closer.
B. **How in Blender** and the cost per frame on the 4-core machine, scripts off (CLAUDE.md 8: simple-expression
   drivers): a Geometry Nodes helix driven by the distance between the two seats, shape keys made at set-up, a GN
   squash with bulge, lattice / Simple Deform; what the clash check, the web 3D export, a model update and the render
   queue do with each.
C. **Set-up in a few clicks:** a function window with steps (0282) – pick the spring / rubber part → the two parts it
   sits between → Check → Done; found by itself from the part kind or name where possible.
D. **Prototype** on a small invented test model: a spring between two plates moved by a slide joint, a rubber buffer
   hit by a stop, a bellows on a cylinder rod – clips.
E. **Page:** a clip per kind, the cost, the set-up flow as a mock-up, ranked build tasks; pick ticks + Copy line.

## Done when

- [ ] Report + page on the branch; the lead publishes the page for the owner's picks → build tasks

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
