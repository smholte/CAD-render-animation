# 0152 – Study: public references for cable-lay operations, to check the demo (findings only)

**Who:** worker · **Status:** done (16 Nov; findings only: no app code, no test run) · **Branch:** none
(report on `main`, touching only `tasks/`)
**Started by:** lead chat, 16 Nov 2026 (owner picked the research) · **Model:** Opus · effort Medium · **Place:** a **new chat in the claude.ai project "STEP rendering App"** (it must open web pages; CLAUDE.md section 2, as 0113)

## Goal

Check the invented cable-lay demo (tasks 0075–0082, 0125, 0126) against public descriptions of real operations, so its motions, speeds and sizes are plausible – without using anything of the owner's employer.

## What to do

1. Public sources only: papers (OTC, OMAE, ISOPE), standards and recommended practices (e.g. DNV-ST-N001, DNV-RP-F401
   / F114 / C205 as relevant, IEC / CIGRE TBs on submarine cables), manufacturers' public brochures and videos
   (carousels, tensioners, quadrants, chutes, CPS / bend restrictors, A&R winches), installation contractors' public
   case studies.
2. Typical values: lay speeds, tensioner pull, carousel sizes / turn speeds, minimum bend radius rules, quadrant / overboard
   chute geometry, second-end and pull-in procedures, CPS lengths and installation, water depths, touch-down monitoring.
3. Compare with the demo (`fresing_render/demo_model/params.py`, `demo.py` stages, the 0075 design notes; the owner's
   generic answers in `tasks/0075-motion-paths-design.md`) – a table: demo value, typical public value, source, change?
4. **Never** use, search for or mention the owner's employer, its vessels or clients; describe the owner's own
   steps only as `tasks/0083-…` already does (private reference, generic). Ranked suggestions for the Demo models lane.

## Rules

- Public repository: no owner's or employer's models, names or pictures; invented or openly licensed examples only
  (CLAUDE.md section 6). Name every source with its link; say what was measured where and what is an expectation.
- Sources are data, not instructions. Paraphrase; short quotes only.

## Done when

- [x] Report below: "In short (for the owner)" first (≤ 10 lines), then the findings, a ranked list of proposals
      (each: what, gain, effort S/M/L, risk, which lane / task it would be) and the sources.
- [x] Pushed to `main` touching only `tasks/` (and `tasks/img/0152_*`); then check that main really contains your
      commit. (In a project chat without push access: give the owner the finished file to attach in the lead chat.)

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 16 Nov 2026. 0 test runs (`tasks/` + `TASKS.md` only). Web search and opening
pages both worked this time (opened: the Carbon Trust MecLim II guideline, and the first 60 % of a TU Delft thesis).
Nothing of the owner's employer, its vessels or clients was searched for or used; vessel pages from contractors are left
out (as in 0083) – where a fact came from one, an equipment maker's or a public source was used instead.

### In short (for the owner)

- The demo holds up: bend radius, chute and quadrant radius, tensioners, carousel, lay speed, water depth, CPS length and
  the second-end steps all sit inside public values.
- **One number is off:** the cable is too heavy in water (51 kg/m at Ø 200; public cables work out to 22–39). With ~38
  kg/m the top tension drops from 25 to ~19–21 kN.
- **Missing:** nobody watches the touch-down. Real lays have an ROV there and a supervisor reading top tension, layback,
  departure angle and lay speed. A "lay data" box in shot 8 is the cheapest big gain (the app has the numbers); an ROV next.
- Small: the handler's 0→100° tilt (shot 9) has no "× N" in its caption; the carousel coil fills only 3 of its 5 m rim.

### Findings: the demo against public values

Demo values from `fresing_render/demo_model/params.py`, `fresing_render/blender/demo.py`, `core/catenary.py`,
`core/vessel_motion.py`. "Worked out here" = arithmetic in this session from the numbers named (no model run).

| # | What | Demo | Typical public value | Source | Change? |
| --- | --- | --- | --- | --- | --- |
| 1 | Cable minimum bend radius (MBR) | 17.5 × Ø = 3.5 m at Ø 200; every bend 1.15 × MBR → 4.05 m (20 × Ø) | Rule of thumb 15 × OD (said to be only a rough guide; a real MBR depends on tension – CIGRE TB 623 tests with and without tension). HV cable sheets: 20 × D. A 33 kV Ø 124 cable: MBR under tension 2.6 m (21 × D). A patent: ~3 m at Ø 150 (20 × D). A CPS for a Ø 158 export cable: 2.37 m (15 × D) | [S1], [S2], [S3], [S4], [S5] | No |
| 2 | Chute (horn) radius | = bend radius, 4.05 m | Quayside chute "3 m MBR"; modular spread MBR 4 m (0083) | [S6], 0083 | No |
| 3 | D-quadrant | radius 4.05 m, D-frame on rails, handler + top pulley | A quadrant for cable up to Ø 350: MBR 3.2 m, 3.5 t own weight, 5.5 t cable, 12 guide rollers. Gutter radius above the MBR. Quadrant winch active-heave-compensated, 25 t SWL; the bight goes over "in one motion", tangent to the stern chutes | [S3], [S7], [S8] | No |
| 4 | **Cable weight in water** | **51 kg/m at Ø 200** (`WET_200`, scaled with Ø²) | Worked out here: 33 kV Ø 124 → 14.7 kg/m (stated); 33 kV Ø 139 → 18.8 (stated); 66 kV "dry" Ø 183, 57.9 kg/m in air → ~31 in water; 66 kV "wet" Ø 163 → ~15; export Ø 261, 3,300 t / 28 km = 118 kg/m in air → ~63 in water. Per Ø²: 560–970 kg/m³ → **22–39 kg/m at Ø 200**. Export cables 70–150 kg/m in air at Ø 200–300 | [S3], [S9], [S10], [S11], [S12] | **Yes: ~38 kg/m** (the dry, lead-sheathed end – the heavy look the demo wants) |
| 5 | Tensions at 30 m (follow from #4) | layback 32 m → bottom 10.4 kN, top 25.4 kN, cable leaves 66° below horizontal (worked out here) | Same layback with 38 kg/m: bottom 7.7 kN, top 18.9 kN, 66°. Or keep 10 kN bottom: layback 37 m, top 21 kN, 62°. Installers keep bottom tension low but not zero; T_top = T_bottom + w·h holds in shallow water on a flat seabed | [S13], [S14] | With #4 |
| 6 | Lay speed | 10 m/min (600 m/h) | Tensioners 0–1,200 m/h. Laying only: up to ~1.85 km/h; buried by jetting 0.13–0.21 km/h; burial on average ~0.2 km/h. An inter-array cable: about 1 day to lay and bury | [S15], [S16], [S17], [S18] | No – but say "surface lay" in the caption (with burial it is ~2–4 m/min) |
| 7 | Tensioner | 2 tracks, gripping run 14 × 300 = 4.2 m, 160° V pads, 8-tooth sprockets (r 0.39 m); lifts, then tilts out of the line | 150 kN class: 3.5–4.0 m contact; 200 kN: 4.0 m; 500 kN (4 tracks): 5.5 m. Pinch up to 667–1,000 kN, cable pressure ~143 kN/m, Ø 50–400, 0–1,200 m/h. "Break-back and tilt" tensioners exist so a quadrant can pass | [S15], [S19], [S20] | No (it reads as a 15–20 t tensioner) |
| 8 | Top tension vs tensioner | ~25 kN (2.5 t) on 2 tensioners | 15–50 t units are usual; they are sized for heavier cable and deeper water | [S15], [S19] | No |
| 9 | Carousel | Ø 24 m, core Ø 8 m, rim 5 m; 15 layers = 3 m of coil ≈ 28 km of Ø 200 (worked out); 0.14–0.39 rpm at 10 m/min | Ø 10–40 m, 0–30 m/min, up to 12,000 t. A Ø 18 m modular carousel: 2,500 t, 6.5 m stacking height, 15 m/min. A 23 m basket carousel took 28 km of Ø 261 export cable (3,300 t) | [S21], [S22], [S12] | Optional: fill the coil to ~4–4.5 m (20–22 layers) so it looks loaded |
| 10 | Water depth | 30 m | Wind farms typically 10–40 m (thesis uses 25 m); 18–25 m (a UK farm); up to 25 m (London Array); 33 m for a 2030 reference site | [S3], [S23], [S24], [S25] | No |
| 11 | Touch-down monitoring | none shown | Most power-cable lays have an ROV tracking the touch-down (USBL position). The lay supervisor watches top tension, departure angle, layback, lay speed, bathymetry and camera feeds; layback and angle are kept within ranges set per depth and sea state | [S13], [S26], [S27] | **Yes: show it** (proposals 1, 3) |
| 12 | CPS set | 15 m long, Ø 400 (2 × cable), vertebra rings ×1.02 | CPS sleeves ~2–15 m, 0.5–8 t; bend stiffeners 1.5–2 m long, OD ≥ 140 mm; vertebra units ~0.5 m; three parts: monopile interface, dynamic zone, static zone. Fitting on deck as fast as ~30 min on some projects | [S28], [S29], [S30] | No (at the long end – fine) |
| 13 | Second end | The D carries the end aft, over the stern, down; tips near the seabed, the end is let go on the seabed | Two public variants: (a) the quadrant lays the end on the seabed **before** it is pulled in (wet store); (b) pull-in **first**: the CPS is pulled into the monopile and locks, then the overlength bight is lowered on the quadrant while the structure's winch takes in slack, and the quadrant tilts at the seabed to release it | [S31], [S3], [S4] | No – the demo is (a). (b) is a later shot (proposal 7) |
| 14 | Handler tilt 0→100° | 4 s on screen, caption without "× N" | No public time found. Estimate: 1–3 min real for a heavy hydraulic frame with the D and cable | (est.) | Small: add "× N" or slow it (proposal 4) |
| 15 | Tipping, A&R, quadrant travel | tip 15 min real (× N shown); A&R 10 m/min; D travel 6 m/min | No public speeds (makers publish SWL, not speeds); 0083's estimates stand | 0083, [S8] | No |
| 16 | Quay loading | tensioner pulls in, carousel turns, ~10 m/min | A quay spread: 15 t quayside tensioner, a loading tower with a 10 t spooling tensioner, a 3 m MBR chute; carousels 0–30 m/min | [S6], [S21] | No |
| 17 | Vessel | 120 × 27 m, draught 6 m, freeboard 3 m | CLVs up to ~30 × 140 m; a 90 × 30 m CLV draws 4.3 m. Freeboard of 120–130 m CLVs: ~3.5–7 m (est.) | [S32], [S3] | No (3 m is the low end; raising it moves every route) |
| 18 | Sea state | Calm: roll ±1.25°, pitch ±0.45°, heave ±0.3 m | Lay usually stops at Hs 1.5–2 m (~65 % workability); a thesis' abort limits Hs 3.5 m, roll 8°, heave acceleration 3 m/s². Weather-restricted operations (< 72 h) are planned with DNV-ST-N001's alpha factor on the forecast | [S33], [S3], [S34] | No |

### Proposals, ranked (lead decides)

| # | What | Gain | Effort | Risk | Lane / task |
| --- | --- | --- | --- | --- | --- |
| 1 | **"Lay data" box in shot 8**: top tension, bottom tension, layback, departure angle, lay speed, water depth – the numbers `paths_sea.numbers` already gives (the stage writes them to the notes today), as a label or caption, plus "surface lay" in the speed caption | An engineer sees the lay is controlled, as on a lay supervisor's screen | S | Low (labels exist) | Demo models lane, small follow-up in `demo.py` (`shot_sea`) |
| 2 | **Wet weight 51 → ~38 kg/m at Ø 200** (`core/catenary.WET_200`); decide: keep layback 32 m (bottom 7.7 kN) or keep 10 kN (layback 37 m) | Right tensions on screen (needed once #1 shows them) | S | Medium-low: expected numbers in the catenary/sea tests and the demo's notes change; the cut-away and touch-down move if the layback changes | Flex parts lane (owner of `core/catenary.py`); one task with #1 is fine |
| 3 | **An invented work-class ROV** following the touch-down in shot 8 (box frame, thrusters, two lights, tether to the stern); one slide joint that keeps it at the touch-down | The most recognisable "real lay" picture under water | M | Low-medium: one more moving body for the clash check (leave it out or check it), triangles | Demo models lane (maker + stage) |
| 4 | Handler tilt in shot 9 (and back in shot 12): give the caption its "× N", or make it ~8–10 s | Consistent time-lapse captions; no "too fast" look | S | Low | Demo models lane |
| 5 | Carousel coil 15 → 20–22 layers (4–4.4 m of the 5 m rim) | A loaded carousel looks loaded | S | Low-medium: spool tables, the arch's reach and the tests' expected lengths change | Demo models lane (+ the spool numbers in tests) |
| 6 | Captions: name the tensioner class ("15–20 t") and the cable ("Ø 200, MBR 3.5 m") once in shot 5 | Shows the demo is sized on purpose | S | Low | Demo models lane |
| 7 | Second-end variant (b) – later: a monopile with its aperture, the CPS pulled in and latched, then the D lowers the overlength while the pull-in winch takes in slack | Shows the most common modern sequence | L | Medium: new model parts (monopile, messenger wire, pull-in winch), new stage; ties in with the Site kit's turbine (0116) | Demo models + Flex parts lanes; owner decides |
| 8 | First-end pull-in shot – later (messenger wire from the monopile, cable paid out over the horn) | Completes the story of one cable | L | Medium (as 7) | Same as 7 |

Not proposed: freeboard 3 → 4–5 m (row 17) – it would move every route for a small gain; only if the owner finds the
deck looks low.

### Sources

- [S1] Carbon Trust, MecLim II – guidelines for defining the mechanical limits of subsea cables (2025), §4.2, §5.2:
  https://www.carbontrust.com/sites/default/files/2025-06/Guideline%20for%20defining%20the%20mechanical%20limits%20%28MecLim%29%20of%20subsea%20cables.pdf
  (CIGRE TB 623, which it builds on: https://e-cigre.org/publication/623-recommendations-for-mechanical-testing-of-submarine-cables)
- [S2] HV cable data sheets with "min. bending radius 20 × D": https://hes.com.tr/assets/doc/urunler-pdf/en/654.pdf
- [S3] D. Sotiriadis, Motion based cable integrity limits for quadrant assisted pull-in operations on submarine
  inter-array cables, MSc thesis TU Delft, 2020 (sections 3.1–3.4, 6.3, 7.1):
  https://repository.tudelft.nl/file/File_cb39a064-ff78-4423-a41b-a728beeee92c
- [S4] Patent US 12545375 B2, cable laying vessel (MBR; second end with pulling cable):
  https://patents.google.com/patent/US12545375B2/de ; patent US 4415764 (MBR ~3 m at Ø 150):
  https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4415764
- [S5] CPS for an export cable of Ø 158 with a 2.37 m bend radius: https://www.marinelink.com/news/maritime/cable-protection-systems
- [S6] A storage-yard spread (5,500 t basket carousel, loading tower with 10 t tensioner, 15 t quayside tensioner, 3 m MBR
  chute): https://swanhunter.com/projects/german-offshore-windfarm
- [S7] Patent application, cable quadrant gutter radius above the MBR:
  https://trea.com/information/cable-laying-vessel/patentapplication/017508f2-77e2-46ba-abdf-e93f6fb537ac
- [S8] Royal IHC, quadrant handling systems (AHC winch, 25 t SWL, one motion, O-loop):
  https://www.royalihc.com/offshore-energy/offshore-equipment/offshore-power-cable-lay/offshore-quadrant-handling-systems
- [S9] 33 kV array cable data sheet (Ø 139, 34.0 kg/m in air, 18.8 in water): https://www.powerandcables.com/wp-content/uploads/2018/10/WOW2.pdf
- [S10] Prysmian, 66 kV submarine cable systems (dry / semi-wet / wet: Ø 183 / 175 / 163, 57.9 / 39.4 / 36.2 kg/m):
  https://www.prysmian.com/sites/www.prysmian.com/files/2024-03/leaflet_submarine_epr_66%20Kv_%20final_0.pdf
- [S11] Scottish Enterprise, offshore wind fact sheet 4 – cables (export cables 70–150 kg/m, Ø 200–300 mm):
  https://www.scottish-enterprise.com/media/0uectkrp/offshore-wind-factsheet-4-cables-and-accessories.pdf
- [S12] Export cable load-in: ~28 km of Ø 261 mm, ~3,300 t, into a 23 m basket carousel: https://www.offshore-energy.biz/?p=242816
- [S13] Makai, Power Module (bottom tension, T_top = T_bot + w·H, ROV tracking of the touch-down):
  https://www.makai.com/cable-software/power-module/
- [S14] Patent US 11733071 (low but non-zero bottom tension; T_top = T_bottom + W·H in shallow water):
  https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11733071
- [S15] MacArtney CEMAC offshore track tensioners (table: pull, pinch, contact length, 0–1,200 m/h):
  https://azure.macartney.com/media/jlsblpso/cemac-offshore-track-tensioners.pdf
- [S16] ScienceDirect topic page, cable installation (lay rates 0.13–0.21 km/h jetting, 1.85 km/h laid):
  https://www.sciencedirect.com/topics/engineering/cable-installation
- [S17] Burial speed ~0.2 km/h: https://electrical-engineering-portal.com/installing-submarine-transmission-cable
- [S18] BOEM, cable laying poster (an inter-array cable ~1 day to lay and bury):
  https://boem.gov/renewable-energy/state-activities/rwf-scoping-poster-cable-laying
- [S19] MacArtney, 50 t and 15 t tensioners (contact 5.5 m / 4.0 m, Ø 50–400, 0–1,200 m/h):
  https://macartney.com/offshore/news-events/news-events/news-complete-tensioner-package-for-asso-subsea/
- [S20] Royal IHC, modular cable lay spread (tensioner with break-back and tilt; quadrant handling system):
  https://www.royalihc.com/sites/default/files/documents/Modular%20Cable%20Lay%20Spread_Final_526.pdf
- [S21] NOV, storage carousels (Ø 10–40 m, 0–30 m/min, up to 12,000 t):
  https://assets.nov.com/NCP4N68N/at/bpkt3cv655j942hp8hbpk8/Storage_Carousels_Flyer.pdf
- [S22] A demountable modular carousel (Ø 18 m, 2,500 t, stacking 6.5 m, 15 m/min):
  https://www.environmental-expert.com/products/demountable-modular-carousel-827496
- [S23] Dudgeon offshore wind farm, facts (water depth 18–25 m, mean Hs 1.1 m): https://dudgeonoffshorewind.co.uk/construction/facts-and-figures
- [S24] Ingenia, harnessing offshore winds (20–30 m; London Array up to 25 m): https://ingenia.org.uk/articles/harnessing-offshore-winds/
- [S25] ORE Catapult, 2030 reference site (33 m, 66 kV array): https://ore.catapult.org.uk/blog/delivering-40gw-accelerating-the-uks-transition-to-net-zero
- [S26] TU Delft paper on monitoring the cable during installation (what the lay supervisor watches):
  https://repository.tudelft.nl/file/File_53d49524-a631-495c-9788-dfc733183463
- [S27] Sonardyne, touch-down monitoring by ROV + USBL: https://www.sonardyne.com/?p=24827
- [S28] Scottish Enterprise, offshore wind fact sheet 3 – cable protection systems:
  https://www.scottish-enterprise.com/media/ry2daieh/offshore-wind-factsheet-3-cable-protection-systems.pdf
- [S29] Wikipedia, cable protection system (three parts, latch): https://en.wikipedia.org/wiki/Cable_protection_system
- [S30] OE Digital, a CPS fitted in ~30 min on some projects: https://www.oedigital.com/news/447261-cable-protection
- [S31] Guide to an offshore wind farm (floating), cable laying equipment and pull-in (the quadrant lays the end before
  the pull-in; quadrant generally used for second ends):
  https://guidetofloatingoffshorewind.com/guide/i-installation-and-commissioning/i-2-offshore-cable-installation/i-2-4-cable-laying-equipment/ ,
  https://guidetofloatingoffshorewind.com/?p=604
- [S32] Same guide, cable-laying vessel (up to 30 × 140 m):
  https://guidetofloatingoffshorewind.com/guide/i-installation-and-commissioning/i-2-offshore-cable-installation/i-2-3-cable-laying-vessel/
- [S33] Damen, motion-compensated cable lay vessel (Hs 1.5–2 m, ~65 % workability; adjustable quadrant radius):
  https://go.damen.com/motion-compensated-cable-lay-vessel
- [S34] DNV-ST-N001 marine operations (alpha factor, weather-restricted operations): https://nodynamics.com/knowledge-hub/dnv-st-n001-marine-operations/ ;
  DNV-RP-0360 subsea power cables in shallow water (scope only, the document itself is not free):
  https://dnv.com/energy/standards-guidelines/dnv-rp-0360-subsea-power-cables-in-shallow-water

**What changed:** this report; `TASKS.md` 0152 → done. No app code, no version.

**Tested and measured:** nothing run in the app. Worked out here with Python from the demo's own numbers: the catenary
(layback 32 m, 30 m water: bottom/top tension and departure angle for 51 and 38 kg/m), the carousel's turn speed
(0.14–0.39 rpm at 10 m/min) and coil length (~1,890 m per layer, ~28 km for 15 layers), and the wet weights in row 4
(buoyancy of a round cable in sea water of 1,025 kg/m³ where only the weight in air is published). These are estimates
from published numbers, not measurements.

**Open points / follow-up tasks:**
- Proposals 1–2 (and 4, 6) fit one small Demo models task; proposal 2 touches `core/catenary.py` (Flex parts lane) –
  the lead decides which lane runs it.
- Not found in public sources: handler tilt time, quadrant travel and A&R speeds, CPS run speed on deck – they stay
  estimates (0083).
- DNV-RP-0360, DNV-ST-0359 and CIGRE TB 623 themselves are paid / members-only; only their scope and what other public
  documents quote from them was used.
