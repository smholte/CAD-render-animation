# 0084 – Demo model: deck re-layout as the owner works (oval route through both tensioners, quadrant on rails)

**Who:** worker · **Status:** open – can start (Wed 11 Nov night) · **Branch:** `task/0084-demo-deck-relayout`
**Started by:** lead chat, 11 Nov 2026 (after 0076 and the reference study 0083)
**Lane:** **Demo models** – `tools/make_demo_cable_lay.py`, `tools/demo_cable_lay/`, `tests/test_demo_cable_lay.py`,
`tasks/img/0084-*.png`. No app code (`fresing_render/`), no version, no release.
**Model:** **Opus · effort High** (layout, route geometry and new mechanisms) · **Place:** Claude Code on the web,
environment "CAD-render-animation"

Runs next to 0058 and 0061 (Thursday, Fable day): touches none of their files. **Merge to `main` before Thu 12 Nov
08:00**; if not ready then, merge only after 0058 and 0061 are merged (one more run is fine).

## Goal

0076 made the invented cable-lay spread, but its deck is one straight line (tensioners in a row, one chute in the
middle, a quarter-circle quadrant hinged at the transom). The owner's answers in 0083 show how such a spread really works.
Re-lay the demo model so the demo project (0077) and the motion tasks (0078–0082) show **his** way of working – still
invented, generic shapes and sizes, nothing copied one-to-one from his reference pictures.

## Read first

`tasks/0083-cable-lay-reference-study.md`: **"The owner's answers and step pictures"** (deck layout, cable route during
lay, coil, CPS run, quadrant sequence, cable look) and **"Check against 0076"** (16 rows). `tasks/0076-…` report for
how the code is built.

## Scope – the lead's decisions on 0083's check table

- **Row 1 – deck lanes and the oval route:** two side lanes of raised roller highways (V roller cradles on trestles, a
  grating walkway beside each), the quadrant's middle lane between them with **rails**, a **lower path 1–1.5 m below**
  side A. Route: coil → arch → down the tower → lower path aft on side A → **stern-corner radius controller** (180°) →
  forward on side B **through tensioner 1** → round the **quadrant at its stationary position** (180°, forward end of the
  middle lane) → aft on side A's highway **through tensioner 2** → down **side A's overboarding chute** ("horn") into the
  sea. All bends ≥ MBR (keep 1.15 × MBR). Route JSON = this oval route.
- **Row 2 – tensioners:** one in each side lane; the top-track carriage **lifts** (squeeze cylinders, stroke covering
  Ø 50–500 + clearance) **and tilts back** about a hinge at its aft end. Both in the joint sheet.
- **Rows 3–4:** gripping run **14 links** (4.2 m at 300 mm pitch); pads **150–160° V**, dark matte rubber on a steel back
  plate; squeeze stroke covers the Ø range.
- **Row 5 – Lebus:** two crossovers per turn of **~35°** each, 180° apart, plus riser/filler wedges at the flanges.
- **Row 7 – quadrant system rebuilt:** a **D-shaped quadrant** (semicircle radius ≥ MBR with spokes, a straight bar,
  cable gutter round the curve, hang-off point) on **rail bogies** in the middle lane; a separate **quadrant handler**
  (frame hinged at the transom, tilted 0→~100° by hydraulic cylinders, a **top-centre pulley**); the **quadrant handling
  winch in front of the carousel**, its wire aft over the handler's pulley to the quadrant; **two tipping winches on the
  stern, port and starboard**, wires over **swivelling sheaves** to the two ends of the D's bar. Joints: quadrant slide
  along the rails, handler tilt 0–100°, quadrant hang/tip about its wire point, sheave swivels, winch drums.
- **Row 8:** route rollers about **1.5 m apart** on the straights (instanced copies of one part).
- **Row 9:** one **linear cable engine** (wheel pairs) on side B between the stern corner and tensioner 1 – its wheels
  turn with the cable (a test for 0078).
- **Row 10:** a bellmouth / roller cage where the cable lifts off the coil.
- **Row 13 – loading tower:** an **overhead arch** (~180° radius controller, rollers along its inside) that **only
  slews** about the tower's axis; a hanging guide frame drops the cable into the coil (no trolley in/out). Joint: slew.
- **Row 14:** a hole at the foot of the core with a clamp inside; the coil as flat layers (layer 1 outwards, layer 2
  inwards); the cable end through the hole.
- **Rows 11 + 15 – CPS store:** a rack along one side with 4–6 CPS sets, an **orange twisted ramp** and a curved slide
  to the route at the quadrant's stationary position. CPS look as 0083 describes (pull head, grey tube, yellow
  segments, vertebrae, bend restrictors), ~15–25 m long.
- **Row 16:** chutes are the curved overboarding **horns** at the stern ends of the side lanes (side A used; a horn on
  side B too), the middle lane's stern end is the handler.
- **Quay loading (for 0077):** an extra file `demo_quay_loading.step`: a quay with the standalone storage carousel and a
  route from it to the vessel's stern corner, placed for the vessel moored alongside (0077 shows loading from the quay).
- Rows 6, 12: keep. Optional only if cheap: lightening holes in the rim plates.

Keep: one parameter set, files made at run time (none committed), triangle budget (whole assembly at Normal ≤ ~3 M
placed), every sheave groove a torus at the rope/cable centre radius, `demo_joints.json` with uids that exist.

## Done when

- [ ] All files written by `tools/make_demo_cable_lay.py`, with the layout above; route JSON = the oval route through
      both tensioners and round the quadrant; joint sheet updated (tensioner lift + tilt, quadrant rails, handler tilt,
      quadrant tip, sheave swivels, arch slew, cable engine wheels, rollers).
- [ ] `tests/test_demo_cable_lay.py` updated: MBR on the oval for Ø 50–500, route passes through both tensioners' grip
      lines and round the quadrant curve, rollers ≤ 1.6 m apart on straights, pad count/pitch, Lebus crossovers ~35°,
      every joint uid exists, triangle budget, quay file imports.
- [ ] 4–6 small Cycles pictures (overview from above, the stern with handler/quadrant/horns, the tensioners, the
      arch over the carousel, the CPS rack + ramp, the quay) in `tasks/img/0084-*.png`.
- [ ] GitHub green; merged to `main` (no version, no release).
- [ ] Report filled in (what changed per row, triangles before/after, open points); `TASKS.md`: 0084 done, 0077 open.

## Not in this task

App code, joints in a project, animation (0077); the moving cable, tracks, spooling, catenary, quadrant motion
(0078–0082); 0058 / 0061 files.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
