# 0158 – Cable look: yarn-served power cable with fibre texture and double marker bands

**Who:** worker · **Status:** done (16 Nov, 0.2.116) · **Branch:** `ccr-4f850d4d-er64e3`
**Started by:** lead chat, 16 Nov 2026 (owner, with photos of a real cable – described below in words; the photos are
**not** committed: CLAUDE.md section 6) · **Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment
"CAD-render-animation". Subagents allowed (CLAUDE.md section 2).
**Area:** Cable looks: `blender/cable_looks.py` (a new kind or a variant of POWER, the shader nodes + `pattern` in plain Python), the web page's cable look as 0142 left it (`fr_page.js` / its cable shader), `ui_paths.py` (the look's choice + settings), their tests.
**Do not edit:** the cable path solver (`paths*.py`, 0159), the demo model maker (0153), the sea (0148/0154).

## Goal

Large export / array cables look like the real thing close up: a black polypropylene-yarn serving with visible fibres, and the double yellow marker bands – in renders, the live view and the web page.

## Background

What the owner's photos show (a large submarine power cable, ~0.3 m Ø, in a workshop): the outer layer is **black
polypropylene yarn served helically** round the cable – many fine strands (~2–3 mm) at a steep lay angle, almost
square to the cable, so the surface reads as fine parallel grooves running round it; matte, with a slight sheen along
the strands, some loose / fuzzy fibres and light dust and lint caught in it, darker and lighter strands mixed. Every
~1–1.5 m there are **two yellow painted bands** (each ~3–4 cm wide, ~3 cm apart) running round the cable – painted onto
the yarn, so the paint follows the grooves, edges ragged, partly worn / smudged black. Today's `cable_power` look draws
helical stripes instead.

## What to build

1. A look **Served cable (yarn)** – a choice next to the existing *Power cable* and *Wire rope*: yarn grooves along
   the lay angle (bump/normal from the formula, no image needed, or a small seamless tile), strand colour variation,
   fuzz (a faint sheen layer and/or fine hair-like noise), dirt; settings: yarn pitch, lay angle, colour, wear.
2. **Marker bands:** pairs (or singles) of rings every N m with width, gap, colour (default yellow), wear (paint
   following the grooves, ragged edges, smudges); they travel with the paid-out length like today's stripes.
3. Same in the coil on the carousel/drum, in the live view, Cycles and EEVEE, and on the web page (0142's way of
   drawing cable looks).
4. The demo's power cable uses the new look by default (the owner's choice can switch back).

## Done when

- [x] `pattern` tests (band spacing / width / travel with payout, groove pitch); small close-up renders (Cycles) of the
      test cable and the demo's cable in `tasks/img/0158_*`; render time per frame before/after (close-up, demo).
- [x] Tooltips, guide (pictures of the cable looks from the test model / the invented demo only), PC-check line / tour
      stop, function list for anything the owner sees; GitHub run green; merged; version (CLAUDE.md section 7); report.

## Design (worker, 16 Nov 2026)

A third cable look **SERVED** (kind number 3, material `cable_served`, group "Served cables"), next to POWER and ROPE.
Shader nodes only (no picture), as the other two: works with scripts off, Cycles, EEVEE, the queue.

Data on the cable object (the tube part, and copied to the spool's rope object):
- `fr_cable_look` = `[band distance m, 0, band width m, 3]` (the same 4-number property as the other looks)
- `fr_cable_yarn` = `[yarn pitch m (axial, strand to strand), yarn starts (signed whole number: strands per lay; from
  the lay angle as the power cable's stripes), cable diameter m, wear 0 … 1]`
- `fr_cable_band` = `[bands per group 1 | 2, gap m, paint wear 0 … 1, 0]`
- `fr_cable_yarn_rgb`, `fr_cable_band_rgb` = colours (3 floats, scene linear)
- missing properties (a part given the material by hand): the library entry's defaults.

Formula (plain Python in `cable_looks`, the nodes and the page's shader draw the same):
- yarn phase `g = (s − paid out) / yarn pitch + starts · φ / 2π`; strand height `sqrt(1 − (2 fract g − 1)²)`;
  strand colour from a white noise of `floor(g)`; fibres = noise stretched along the strand; dust in the grooves.
- band: `x = (s − paid out) mod distance`; band 1 = `[0, w)`, band 2 = `[w + gap, 2w + gap)`; ragged edges (noise,
  ±a few mm, more with wear), paint thinner in the grooves and smudged black by wear. `bands()` gives the clean mask.

Code: `blender/cable_looks.py` (formula, nodes, `served_props`), `core/materials_lib.py` (entry 56), `props.py`
(FRCable settings), `ui_paths.py` (the look's settings), `paths.py` only where the look is written (*(picture removed – private, task 0226)*,
*(picture removed – private, task 0226)*, `GROUPS`), `spool.py` (copies all look properties), `web3d_drawn.py` +
`core/web3d_tubes.py` + `web/fr_page.js` (the page), `demo.py` (the power cables get SERVED), tour set "served",
PC-check line `looks.served_cable`, function `cables.served_look`, guide.

---

## Report (filled in by the chat that did the task)

**Chat / date:** worker, Claude Code on the web, 16 Nov 2026 (branch `ccr-4f850d4d-er64e3`), version 0.2.116.

**What changed:**
- New look **SERVED** "Served cable (yarn)" (`blender/cable_looks.py`, material `cable_served`, uid 56, group
  "Served cables"): yarn grooves at the lay angle (bump from the formula, no picture), each strand darker/lighter
  (counted round the n strands: no seam where the angle jumps), fibres (noise along the strand), dust in the grooves
  with wear, sheen from the material; marker bands single or pairs every N m, width, gap, colour, paint wear (ragged
  edges with a step per strand, paint thinner in the grooves, smudges). Formula in plain Python: `served_props`,
  `yarn_phase`, `yarn`, `bands`. Data on the cable object: `fr_cable_look` + `fr_cable_yarn`, `fr_cable_band`,
  `fr_cable_yarn_rgb`, `fr_cable_band_rgb` (Design above); missing ones = the library's.
- Settings on the cable (`props.py` FRCable: band count/width/gap/colour/paint wear; yarn pitch, lay angle, yarn
  colour, wear; Pitch = band distance), panel `ui_paths.py` (fold "Yarn").
- `paths.py` only where the look is written (`look_props`, *(picture removed – private, task 0226)*, `GROUPS`); no
  solver code touched. `spool.py`: the coil copies every look property, and **`follow_look`** (a fix that also
  helps the old looks: switching a cable's look left its drum/carousel coil in the old look until rebuilt).
- Web page: `look_for_page` / `web3d_drawn.look_of` send the served numbers; `fr_page.js` draws yarn, fibres, dust
  and bands (own value noise – the same kind of look, not Blender's numbers; band places and groove phase identical).
- Demo: the lay cable and the second end get SERVED (`demo.py`), the demo test checks the look and the coil.
- Tour set/stop "served" (test_spool.step), PC-check line `looks.served_cable`, function `offshore.served_cable`,
  guide section "Served cable (yarn)" (anchor `served-cable`, picture `view_cables_served.jpg` from the invented
  demo), CHANGELOG. MIN_LINES_FULL 84, MIN_LINES_TOUR 65, MIN_CHECKS tour 65.

**Tested and measured** (4-core web machine, Blender 5.2.3 as module, Cycles CPU):
- `tests/test_cable_looks.py` (6 new served tests: library, `served_props`, band spacing/width/travel with payout,
  groove pitch and lay, nodes = formula by probe renders from two sides, real material yellow/black + travel + wear +
  library fall-back; EEVEE child renders the served look too: bands error 0.0), `tests/test_paths.py`
  (`test_the_served_look`), `tests/test_web3d_moving.py` (`test_served_cable_look_on_the_page`: numbers + headless
  page "ready" – it caught a GLSL reserved word), `test_demo_project_cable.py` (4 passed on the made demo),
  `test_tour.py` (75 passed), `test_tour_clash.py -k served`, PC-check line OK (render 2.7 s at 320x180), precheck,
  tooltip report (751 ok).
- **Independent tester** (subagent, Sonnet, did not write the code): `tests/test_served_cable_independent.py`, 17
  tests; it found 3 faults, all fixed: missing colour properties rendered the bands black (now the library's colours,
  nodes and page alike), lay angle 0 gave rings instead of strands along the cable, the first band's left edge was
  not paint.
- Close-ups (960x540, Draft = 48 samples, CPU): test carousel power cable 11.6 s with Power cable → 12.9 / 13.1 s with
  Served (+12 %); demo coil 9.8 → 13.4 s (+37 %, the coil fills the picture), demo chute 9.7 → 10.4 s (+7 %).
  Pictures: `tasks/img/0158_test_power.jpg`, `0158_test_served.jpg`, *(picture removed – private, task 0226)*,
  *(picture removed – private, task 0226)*.

**GitHub runs:** 2 full runs. The first was red in one test: my new page test had no fall-back for GitHub's headless browser, which cannot start there; it now falls back as the older page test does. Then 0148 took 0.2.115, so I renumbered to 0.2.116 and the second run was green (20 min). Subagent: one independent tester (Sonnet) wrote `tests/test_served_cable_independent.py` and found 3 faults, which I fixed myself (listed above).

**Open points / follow-up tasks:**
- The page's yarn and dust noise is its own (value noise), not Blender's numbers: same look, other blotches.
- A colour set to pure black (0, 0, 0) counts as "not given" and takes the library's colour (for a black yarn the
  same; a black band would become yellow).
- `panel_cables.png` not re-shot: the guide's panel picture shows the rope test model, whose Look row is unchanged.
- No GPU measurement here; the owner's RTX 3090 render time with the served look is still to be seen (PC check
  line `looks.served_cable` measures the CPU close-up).
