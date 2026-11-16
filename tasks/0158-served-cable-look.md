# 0158 – Cable look: yarn-served power cable with fibre texture and double marker bands

**Who:** worker · **Status:** running (16 Nov) · **Branch:** `ccr-4f850d4d-er64e3`
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

- [ ] `pattern` tests (band spacing / width / travel with payout, groove pitch); small close-up renders (Cycles) of the
      test cable and the demo's cable in `tasks/img/0158_*`; render time per frame before/after (close-up, demo).
- [ ] Tooltips, guide (pictures of the cable looks from the test model / the invented demo only), PC-check line / tour
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
(FRCable settings), `ui_paths.py` (the look's settings), `paths.py` only where the look is written (`_apply_look`,
`_strip`, `_default_pitch`, `GROUPS`), `spool.py` (copies all look properties), `web3d_drawn.py` +
`core/web3d_tubes.py` + `web/fr_page.js` (the page), `demo.py` (the power cables get SERVED), tour set "served",
PC-check line `looks.served_cable`, function `cables.served_look`, guide.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured** (name the machine and the model):

**Open points / follow-up tasks:**
