# 0164 – Served cable: the yellow marker lines are two continuous spirals (1 m pitch), not rings

**Who:** worker · **Status:** open – can start when a code slot is free · **Branch:** `task/0164-served-spiral-bands`
**Started by:** lead chat, 16 Nov 2026 (owner's correction of 0158, with two photos) ·
**Model:** Sonnet · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation".
**Area (cable looks):** `blender/cable_looks.py` (the SERVED band part only: defaults, `served_props`, `bands`,
`pattern`, the band nodes), `web/fr_page.js` (the served band lines of the cable shader only), the served-look settings
in `props.py` (FRCable, additive) and `ui_paths.py` (the served band rows only), `web3d_drawn.py` / `core/web3d_tubes.py` only if the page
needs the new number; their tests (`tests/test_cable_looks.py`, `tests/test_served_cable_independent.py`,
`tests/test_web3d_moving.py`, `tests/test_paths.py`); the guide's served-cable section, its picture.
**Do not edit:** `demo_model/`, `demo.py` (0153 runs there – the demo gets the spiral through the library's default;
if `demo.py` passes its own band values, write it in the report for a later task), `paths.py`, `paths_sea.py`, `spool.py`, `flex.py` and the cable panels' notes (0160 runs there at the same time –
the new number is written by `served_props` / the look's own code), the rest of the Web 3D lane (0161, 0143), `sequence.py` /
`reimport.py` (0162). If 0160 merges first and `ui_paths.py` or `props.py` clash, merge `main` and keep both.

## Goal

The served cable's yellow marker lines look like the real cable: **two parallel yellow lines that run as one
continuous spiral round the cable over its whole length, one full turn per metre** – not pairs of separate rings
every metre and a bit (what 0158 drew).

## Background

0158 (0.2.116) made the look *Served cable (yarn)* with "marker bands": pairs of **rings** every 1.25 m
(`x = (s − paid out) mod distance`). The owner (16 Nov, 12:15, two photos of a real served export cable in a
workshop – described here, not committed) says this is wrong:

- The two yellow lines are **continuous helical stripes** along the entire length of the cable, side by side (each
  ~3–4 cm wide, ~3 cm of black between them – 0158's width 0.035 m and gap 0.03 m fit).
- **Pitch 1 m:** the pair goes once round the cable per metre of cable. On a ~0.3 m cable that gives stripes at a
  clear slant (seen from the side, a stripe on the near face crosses the cable over about half a metre).
- **Hand:** in both photos the stripes on the near face lean like the middle stroke of a **Z** when the cable is held
  upright – a **right-hand** helix (like a normal screw thread). The lead read this from the photos; make it the
  default and a setting, and say in the report which sign of `starts` it is (module docstring: with φ turning
  right-handed about growing s, a positive `starts` is a left-hand helix).
- Paint as 0158 drew it (ragged edges, thinner in the grooves, smudged with wear) – unchanged.
- "Similar like before": the older *Power cable* look already draws helical stripes with `phase = u + starts · θ`;
  the bands should follow the same idea.

The served look already carries a stripe count: `fr_cable_look = [band distance m, 0, band width m, 3]` – the second
number (starts) is always 0 today. Suggested (the worker may choose better, write it under Design):
- band phase `x = fract((s − paid out) / pitch + band starts · θ) · pitch`, the bands as today on `x`;
  `band starts` = ±1 (one spiral pair, the sign is the hand), 0 = rings (what 0158 drew);
- `pitch` = distance along the cable for one full turn (1.0 m by default; for rings it stays the distance between
  groups – the same number along any straight line on the cable);
- **old projects keep what they have**: a served cable saved with 0.2.116 (starts 0) still draws rings; the library
  default, new served cables and the demo (through the default) get the spiral.

## What to build

1. Served cable look: **Bands: Spiral / Rings** (default Spiral), **Pitch (one turn) 1.0 m**, **Hand: Right / Left**
   (default Right); width, gap, count (1 or 2 lines), colour, paint wear as now. Tooltips say what pitch means for each.
2. The same pattern everywhere 0158 drew the bands: Cycles, EEVEE, live view, the coil on the carousel/drum (the
   spool's rope object), the web page's shader (same band places as the app, as 0158 checked for the rings).
3. The stripes travel with the paid-out length like today (a mark on the cable moves with the cable, it does not
   turn round it).

## Done when

- [ ] `bands` / `pattern` tests for the spiral: one full turn per pitch along a line on the cable, the two lines
      parallel at width + gap, right / left hand as set, travel with payout without turning, rings unchanged for
      starts 0 (0.2.116 data); nodes = formula by probe renders (as 0158's test); the page's numbers and headless
      page "ready" (with GitHub's fall-back); the independent tests of 0158 updated where they assumed rings.
- [ ] An old project's served cable (rings, 0.2.116) opens unchanged; a new one and the made demo show the spiral.
- [ ] Small close-up renders (Cycles) of the test cable and the demo's cable in `tasks/img/0164_*` (invented models
      only); render time per frame before/after on the same close-up (expect no change).
- [ ] Tooltips, guide section "Served cable (yarn)" + its picture, tour stop "served" still passes, PC-check line
      `looks.served_cable` still OK, function list entry text if it says "rings"; GitHub run green; merged; version
      (CLAUDE.md section 7); report.

## Not in this task

The yarn itself (0158's grooves, fibres, dust – the owner did not ask for a change), the power cable and wire rope
looks, cable speed and the carousel (0159), cable/sea fixes (0160), the web export fixes (0161), the sea under water on
the page (0143 – it waits for this task because both edit `fr_page.js`). The owner's photos are never committed
(CLAUDE.md section 6).

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
