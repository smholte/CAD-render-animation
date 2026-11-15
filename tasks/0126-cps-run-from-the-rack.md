# 0126 – Demo: the CPS run from the rack to the cable end

**Who:** worker · **Status:** open – **starts after 0125 is done** (same demo stages) · **Branch:** `task/0126-cps-run`
**Started by:** lead chat, 15 Nov 2026 (owner: "all 5 suggested tasks") · **Model:** Opus · effort High
**Area (Demo models lane):** `fresing_render/demo_model/` (rack, ramp, curved slide, the CPS set's parts if they need
splitting), `blender/demo.py` (a new stage before the quadrant stages; shots renumbered only if needed), app code in the
Flex parts lane (`paths*.py`, `core/paths.py`) only where the CPS must ride a path the app cannot yet give, their
tests. **Do not edit:** `sequence.py`, `ui_motion.py` beyond the cable boxes (task 0129); `tools/site_projects/`,
`site/` (task 0128).

## Goal

The demo shows the owner's CPS steps 1–5: one CPS set slides from the rack down the orange ramp and the curved slide
onto the cable highway, travels along the route round the quadrant and down one lane, stops, runs back the other way
to its place in front of the cable, the cable end is connected to its rear end, and then the CPS goes on nose first
into 0082's quadrant sequence.

## Background

- **Owner's description:** `tasks/0083-cable-lay-reference-study.md`, "CPS store" (about line 292) and "CPS on the
  cable end (owner's CPS steps 1–5)" (about line 313), plus his route steps 1–4 just above it. A CPS set is ~15–25 m
  long, ~2× the cable Ø; from the nose: pointed pull head, grey tube, segmented yellow, brown vertebrae, grey, yellow
  bend-restrictor segments next to the cable. These are generic words for the owner's work – the demo stays invented
  (CLAUDE.md section 6: nothing of his employer's design).
- The demo already has a CPS rack + ramp (0084) and a CPS / pull head on the cable that rides over the horn and down
  (0081: "things on the cable (CPS set) ride over the horn and down"); 0082 starts with the CPS on the cable end.
- A CPS is not a straight rigid body on a curved route: its segments must follow the path (like 0081's riders, or
  0079's links one pitch apart). Use what exists before writing a new solver.
- Read the report of 0125 first (it changes the sea stage and maybe the paths code).

## Done when

- [ ] A new demo stage (e.g. `cps`) plays steps 1–5: down the ramp, onto the highway, along the route round the
      quadrant, down one lane, stop, back, connect to the cable end, then into the existing quadrant shots.
- [ ] The CPS's segments stay on the route's middle line within 2 cm on every frame (measured), no segment through a
      roller, cradle or rail: 0 clash rows in the demo (`tests/test_demo_clash.py`).
- [ ] A shot (camera) that shows the run; captions as the other demo shots; "What it can do today" still builds.
- [ ] Make demo time and per-frame cost before/after in the report.
- [ ] If an app ability was added (something on a path that is not a cable): tooltip, guide + anchor, function-list
      entry, tour stop, PC-check line (CLAUDE.md section 6). A demo-only stage needs none of these.
- [ ] Tests; full GitHub run green; report with the owner's check (the new shot on the RTX 3090).

## Not in this task

The quadrant sequence itself (0082, 0125). The site. Glow markers, sediment.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
