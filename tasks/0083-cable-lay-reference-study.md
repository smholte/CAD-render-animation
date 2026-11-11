# 0083 – Reference study: how a cable-lay spread really looks and moves

**Who:** worker · **Status:** done (11 Nov) · **Branch:**
`task/0083-cable-lay-reference`
**Started by:** lead chat, 11 Nov 2026
**Area:** findings only – this task file and, at most, small notes in `tasks/0076-demo-cable-lay-model.md` (a "Notes
from 0083" section). No code, no version, no release (a `tasks/`-only push starts no test run).
**Model:** **Opus · effort Medium** · **Place:** Claude Code on the web, environment "CAD-render-animation" (web search and
web pages through the session's own search/fetch tools; the shell cannot reach most websites)

## Goal

The demo model (0076), the demo project (0077) and the motion-paths tasks (0078–0082) must look and move like the real
thing to an engineer who designs these machines (the owner). This study collects, from public sources, **what the
equipment looks like, its typical sizes, and how and how fast each part moves**, so the briefs and the reviews have
facts instead of guesses. It also proposes a **shot list** for the demo video.

## Background

Owner's answers (end of `tasks/0075-motion-paths-design.md`): carousel usually (also standalone storage carousels),
chute or quadrant at the stern, cable Ø 50–500 mm, lay speed ~10 m/min, two track tensioners with pad chains that
squeeze, quadrant + quadrant handling winch + tipping winches, handling winches helping the tensioners, spiral-groove and
Lebus drums, CPS, power cable black with yellow angled stripes, steel wire rope on winches. Read 0076's brief: it is
being built at the same time from general knowledge.

The owner may paste **screenshots** of reference videos (his own collection) into the session: use them as private
reference only – **never commit them or describe a client's design in the public repository**; write generic findings.

## Questions to answer (numbers with a source; say plainly what is an estimate)

1. **Track tensioners:** 2-track vs 4-track; track length, pad size and shape (V or flat, rubber), chain pitch, pads per
   track; how the top track squeezes (cylinders, stroke, opening for Ø range); line pull and speed ranges; what visibly
   moves (tracks, sprockets, cylinders) and in which direction; how two tensioners in a row share the load.
2. **Carousels:** outer/inner diameters and rim heights for 1,000–10,000 t; turning speed at 10 m/min lay speed
   (rpm vs coil radius); how the cable lies in the carousel (flat spiral layers, from outside in or inside out, the
   crossover to the next layer); the **loading arm / radius controller** (how it follows the layer, its motion range).
   Standalone storage carousels on a quay or barge: what differs.
3. **Cable route on deck:** roller conveyors, cable gutters, guide wheels / radius controllers at bends, straighteners,
   cable engines; typical spacing of rollers; heights above deck.
4. **Stern:** overboarding chute (radius, rollers, width) vs overboarding sheave; the **quadrant** – shape, radius,
   how the cable end is fixed (hang-off, pulling head), the **first-end and second-end** procedures step by step, what the
   quadrant handling winch and the **tipping winches** do and in which order, typical durations.
5. **Handling winches helping the tensioners:** how a winch wire is joined to the cable (pulling grip, stopper,
   Chinese finger) and when; A&R winch.
6. **Winch drums:** spiral groove vs **Lebus** grooving (parallel sections + crossover zones per turn, risers/fillers at
   the flanges, layer change); what to show in close-ups; fleet angle limits.
7. **Cable into the sea:** lay catenary, touch-down point distance for typical depths, tension; lay speed in practice;
   what an underwater shot usually shows; **CPS** types (bend restrictor, polymer sleeves, centraliser, latch for
   monopile/J-tube) and how they look on the cable.
8. **Looks:** export / inter-array power cables (outer serving, colour, **yellow stripe** pitch and angle, length marks),
   steel wire rope (strands, lay, compacted vs regular, sheen), typical deck/machine paint (RAL), wear, wet decks.
9. **Vessel motion** that looks right in a video (roll/pitch amplitudes and periods in a calm working sea state).
10. **Shot list:** 8–12 camera shots for a 1–2 minute demo video of the spread (like a manufacturer's promo): what each
    shows, camera place and move, duration, which app feature it needs (existing or task 0077–0082).

## Done when

- [x] Each question answered briefly with numbers and **source links** (manufacturer pages, papers, class/industry
      guidance); estimates marked as such; no long quotes, no pictures from the web committed.
- [x] A short list **"check against 0076"**: where 0076's brief assumes something different (sizes, shapes, missing
      parts), each with the suggested change – the lead decides.
- [x] Per motion-paths task 0077–0082: the facts its brief needs (one short block each).
- [x] The shot list.
- [x] Report pushed to `main` (tasks/ only, no test run); `TASKS.md`: 0083 done.

## Not in this task

Code, models, pictures from the web, anything of the owner's employer or its clients.

---

## Report (filled in by the chat that did the task)

**Chat / date:** Claude Code on the web, 11 Nov 2026. 0 test runs (tasks/ only).

**How the facts were found.** Web search worked; opening pages and PDFs did **not** (every manufacturer host was
refused by the session's network: macartney.com, royalihc.com, briggsmarine.com, jandenul.com, swanhunter.com). So the
numbers below come from the search engine's extracts of the linked pages. Each one has its link; anything without a
link is marked **(est.)** = engineering estimate / general knowledge, or **(owner's ref.)** = seen in the owner's private
reference screenshots (a promo animation and photos of modern cable-lay vessels; not committed, no names, no layout
copied – generic observations only). A follow-up that needs the full datasheets should allow those hosts first.

### Findings

**1. Track tensioners**
- Cable lay mostly uses **2-track** units (some 3-track); 4-track is mainly for flexible/reeled pipe
  ([Royal IHC pipelay tensioners](https://www.royalihc.com/offshore-energy/offshore-equipment/tensioners-and-winches/pipelay-tensioners)).
  A 4-track unit rated 51 t pulls 25.5 t in 2-track mode at μ 0.09 ([OE Digital](https://www.oedigital.com/news/461464-maintaining-tension-in-subsea-cable-laying)).
- **15 t class:** track contact length **3.0–3.2 m**, squeeze 0–60 t total, i.e. ~13.5–16 t/m (≈160 kN/m)
  ([Royal IHC 15Te factsheet](https://royalihc.com/sites/default/files/documents/RIHC%20factsheet%20OE%2015Te%20breakback%20tracked%20engine.pdf),
  [Royal IHC rental tensioners](https://www.royalihc.com/sites/default/files/documents/Royal%20IHC_Rental%20Tracked%20Tensioners.pdf),
  [Briggs 15te sheet](https://www.briggsmarine.com/wp-content/uploads/2022/10/15te-Tracked-Tensioner-Specification-Sheet.pdf)).
  One range lists contact lengths **1.75–5.5 m**, μ 0.1–0.2, cable **Ø 50–400 mm**, 2/3/4 tracks
  ([MacArtney CEMAC tensioners](https://macartney.com/offshore/cable-pipe-handling/cemac-offshore-track-tensioners/)).
- **Pads:** natural rubber, 70 Shore A, **160° V** (a shallow V) ([Royal IHC rental](https://www.royalihc.com/sites/default/files/documents/Royal%20IHC_Rental%20Tracked%20Tensioners.pdf)).
  Pad pitch is not published; the chain pitch is ~150–300 mm, and each pad is about as long as the pitch **(est.)**.
- **Speed and pull:** 0–1,200 m/h (= **0–20 m/min**) at 5–50 t pull ([CEMAC datasheet](https://azure.macartney.com/media/jlsblpso/cemac-offshore-track-tensioners.pdf)),
  0.5–15 m/min at the full 15 t, 20 m/min at reduced pull ([Royal IHC 15Te](https://royalihc.com/sites/default/files/documents/RIHC%20factsheet%20OE%2015Te%20breakback%20tracked%20engine.pdf)),
  25 t at 0–10 m/min, Ø 60–300 ([Jantle](https://ahjantlemarine.en.made-in-china.com/product/AagRvJSGvtWZ/China-Tensioner-for-Cable-Laying-Vessels.html)).
  Pull ≈ 2 · μ · squeeze. At μ 0.15, 15 t of pull needs ~50 t of squeeze, which agrees with the 0–60 t above (est.).
- **Squeeze:** fail-safe hydraulic cylinders press the top track (or both tracks) onto the cable
  ([OE Digital](https://www.oedigital.com/news/461464-maintaining-tension-in-subsea-cable-laying)). The stroke must
  cover the Ø range plus clearance, so ~Ø_max − Ø_min + 100–200 mm, about 0.4–0.5 m for Ø 50–400 **(est.)**. The top
  track moves straight down and stays parallel to the bottom one.
- **What moves:** the pad chains run round the sprockets at cable speed (with no slip on the cable, a pad moves with
  the cable on the gripping run). The drive sprockets sit at one end with hydraulic motors and gearboxes, and the
  idlers turn freely. The cylinders move only when the tensioner opens or closes. **(owner's ref.)** The whole
  tensioner **lifts up and tilts back** on its frame, out of the cable line (to let the cable end, CPS or a joint
  pass, or to free the lane).
- **Two in a row:** they share the line tension through their controls (load sharing). At a cable end or a joint, one
  opens while the other holds **(est.)**. **(owner's ref.)** On the vessel in his screenshots, the two tensioners
  stand **one on each side of the deck** (port and starboard lanes), not one behind the other. See the 0076 check
  below.

**2. Carousels**
- Sizes: outer Ø **10–40 m** and up to 12,000 t ([NOV storage carousels](https://assets.nov.com/NCP4N68N/at/bpkt3cv655j942hp8hbpk8/Storage_Carousels_Flyer.pdf)).
  Basket carousels for 2,000–7,000 t have outer Ø 12.2, 12.8, 14, 15, 18, 23 and 28 m ([Swan Hunter](https://swanhunter.com/basket-carousels)).
  A 7,000 t reel carousel has a core Ø of **4.5–8 m** and a core height of 6 m ([Swan Hunter](https://swanhunter.com/reel-carousels-loading-towers/)).
  A 4,000 t carousel has a core Ø of 3.6 m and a basket height of 5 m ([Jan De Nul](https://jandenul.com/sites/default/files/public/Cable%20carousel.pdf)).
  So a **7,000 t carousel is about Ø 24–28 m, rim 5–6 m high, with a core of Ø 4–8 m** (est. from these).
- **Turning speed** at 10 m/min of cable: rpm = v / (2π r). That gives **0.40 rpm** at r 4 m, 0.20 at 8 m and 0.14 at
  11.7 m. One flat layer of a Ø 200 cable between r 4 and 11.7 m holds ~1,900 m, i.e. **~3.2 h per layer** (worked
  out here). On screen the carousel hardly moves: the demo needs time-lapse or "faster than real" with a caption.
- **How the cable lies (est., common practice):** the cable is coiled in flat layers, each layer a spiral across the
  basket's width. The next layer spirals back the other way, with a crossover (the cable climbs onto the new layer)
  at the core or at the rim. Unloading goes in the reverse order.
- **Loading arm / spooling arm:** a slewing boom from the centre pillar, with a controllable guide (articulated boom),
  operated hydraulically from a control cabin that also sets the carousel speed
  ([spooling arm description](https://onboardsystems.com/product/210-275-00) – adjacent industry, treat with care).
  A loading arm sheet gives 11.4 m long, 5.9 m high, outer ring radius up to 8.25 m
  ([Briggs loading arm](https://www.briggsmarine.com/wp-content/uploads/2022/10/Cable-Loading-Arm-Specification-Sheet.pdf)).
  Its guide moves in or out by **one cable Ø per carousel turn** (0.2 m every 2.5–7.5 min at 10 m/min) and is reversed
  at each layer change. Its height follows the layer (est.).
- **(owner's ref.)** Typical looks: a tall rim made of plated sections with **round lightening holes**, a fence and
  walkway on the rim top, a light-coloured perforated floor, and a tall core tube with a fence round its top. A walkway
  bridge from the loading tower over the carousel to the core. Loaded with striped cable, the coil reads yellow-green
  from a distance.
- **Standalone storage carousels** (quay or barge) are the same in principle: no well, a base frame or a foundation
  ring, often bigger and slower, and loaded from the factory over a quay gantry or a loading tower (est.; Swan Hunter
  "reel carousels / loading towers" link above).

**3. Cable route on deck**
- The route is made of **roller highways** (the cable runs in a gutter over rollers on stands), **radius controllers**
  at the bends (a curved row of rollers with radius ≥ MBR), **linear cable engines** (pairs of wheels) to move the
  cable on deck, and an overboarding chute or sheave. A modular spread has a 22 m roller highway and MBR 4 m
  ([Royal IHC modular spread](https://www.royalihc.com/offshore-energy/offshore-equipment/power-cable-lay/modular-cable-lay-spread)).
  The Osbit spread lists cable highways, quadrant trackways, a chute and a quadrant handling winch
  ([offshorewind.biz](https://offshorewind.biz/2014/07/03/osbit-equips-technip-with-bespoke-cable-handling-system)).
- **Rollers:** ~1.0–2.0 m apart on the straight runs, closer on the bends. The cable centre is 0.8–1.8 m above the
  deck, and the rollers are V-shaped or a pair of angled rollers **(est.; owner's ref.: a long raised highway on
  regular trestles, red-and-white roller cradles, a green grating walkway beside it; from the carousel top down to
  deck level a tall tower with a stacked radius controller)**.
- A roller with a radius smaller than the MBR is fine only if the cable is not bent round it, i.e. on the straight
  parts ([patent US12545375](https://patents.google.com/patent/US12545375B2/de)).

**4. Stern: chute and quadrant**
- **Chute:** a curved roller track with radius ≥ MBR, often flared at the sides so the cable keeps its MBR when the
  vessel rolls or yaws ([patent US12545375](https://patents.google.com/patent/US12545375B2/de)). Width ~1–2 m
  **(est.)**.
- **Quadrant:** a semicircular / quarter-circle frame with a radius above the cable's MBR
  ([GB2561001A](https://patents.google.com/patent/GB2561001A/en)). It is used for the **second end** (and repairs): the
  cable end is laid on the seabed with it before the pull-in
  ([guide to floating offshore wind](https://guidetofloatingoffshorewind.com/guide/i-installation-and-commissioning/i-2-offshore-cable-installation/i-2-2-array-cable-installation/)).
  The quadrant handling winch is active-heave-compensated, SWL **25 t**. The quadrant interlocks during overboarding,
  and the last bight is laid "in one motion" without a crane
  ([Royal IHC quadrant handling](https://www.royalihc.com/offshore-energy/offshore-equipment/offshore-power-cable-lay/offshore-quadrant-handling-systems)).
  **(owner's ref.)** The quadrant is a **yellow frame lying flat on the deck** in a lane beside the cable route, and it
  is lifted and tipped over the stern from there.
- **Second end, step by step (est., general practice; the order fits the sources above):**
  1. Lay slows down; the cable end (pull head, CPS fitted or fitted now) comes off the carousel through the
     tensioners. 2. The cable is held by a stopper or hang-off clamp; the end is placed in the quadrant's gutter and the
     pull head is shackled to the quadrant's hang-off point. 3. The quadrant handling winch wire is connected.
  4. The **tipping winches** pull the quadrant aft about its hinge at the stern while the tensioners pay out; the cable
     bends round the quadrant at ≥ MBR. 5. At about 90° the **quadrant handling winch** takes the load, and the
     tensioners open. 6. The handling winch lowers the quadrant and the cable bight to the seabed (heave-compensated)
     while the vessel creeps along the route. 7. An ROV releases the cable; the winch recovers the quadrant, and the
     tipping winches bring it back on deck.
  Durations **(est.)**: preparation 2–4 h, tipping 10–20 min, lowering at 5–15 m/min (30 m water: a few minutes),
  ROV release 0.5–1 h.
- **First end (est.):** a messenger wire from the J-tube or monopile (placed earlier) is brought to the vessel and
  joined to the pull head ([guide to floating offshore wind](https://guidetofloatingoffshorewind.com/guide/i-installation-and-commissioning/i-2-offshore-cable-installation/i-2-2-array-cable-installation/)).
  The structure's winch pulls the cable in while the tensioners pay out over the chute
  ([Block Island example](https://oceannews.com/featured-stories/subsea-cable-installation-for-the-block-island-wind-farm/)).
  The CPS goes into the monopile hole and latches. Then the main lay starts. Usually 4–8 h (est.).

**5. Handling winches helping the tensioners**
- The winch wire is joined to the cable with a **cable grip / stocking ("Chinese finger")**, which tightens round the
  cable as it is pulled, or to the **pull head** at the cable end
  ([towing sock](https://en.wikipedia.org/wiki/Towing_sock), [Chinese finger](https://trenchlesspedia.com/definition/4115/chinese-finger)).
  It is used when extra pull is needed beyond the tensioners, when the end, CPS or a joint cannot pass through the
  tracks, or when cable is pulled back on board (est.). Wire Ø 40–60 mm for 25–50 t (est.). The **A&R winch**
  (abandon and recovery) lowers a cable end to the seabed on its wire and picks it up again; its wire goes over the
  chute or an A-frame (est.).

**6. Winch drums**
- **Lebus:** the grooves run **parallel to the flange** with **two crossovers per turn**, each shifting the rope half
  a pitch. About 80 % of the circumference is parallel and ~20 % crosses
  ([mining-technology / Lebus](https://www.mining-technology.com/contractors/winding/lebusspooling/),
  [Wikipedia: wire rope spooling](https://en.wikipedia.org/wiki/Wire_rope_spooling_technology)).
  On the next layers the rope lies in the gap between two wraps below. At the flanges, **riser / filler rings**
  (wedges) lift the rope to the next layer smoothly (est.; not in the extracts).
- **Spiral groove:** one helical groove with a pitch of ~1.03–1.06 × rope Ø (est.). Fleet angle **0.5–1.5° for plain
  drums and up to ~2–2.5° for grooved drums**; below 0.5° the rope piles up at the flange
  ([Wikipedia](https://en.wikipedia.org/wiki/Wire_rope_spooling_technology),
  [Hercules fleet angle](https://www.herculeslifting.com/blogs/news/fleet-angle-analysis-winching-wire-rope-spooling)).
- **Close-ups to show:** the first layer in the grooves; on Lebus, the rope stepping sideways at the two crossovers
  (180° apart) and climbing at the riser by the flange; the second layer crossing the first.

**7. Cable into the sea**
- The cable hangs in a **catenary** from the chute or quadrant to the touchdown point. Its shape depends on the
  departure angle, wet weight, depth and layback. **T_top = T_bottom + w·h**
  ([cabledatasheet](https://cabledatasheet.com/general-cable-information/the-catenary-line-installation-and-protection-of-submarine-power-cables)).
  Installers keep the bottom tension low but not zero, to avoid free spans
  ([Makai](https://www.makai.com/cable-software/power-module/)).
- Worked example (here; w = 500 N/m wet ≈ a Ø 200 cable (est.), bottom tension 10 kN): at **20 / 30 / 50 m depth** the
  layback is **26 / 31 / 39 m**, the top tension 20 / 25 / 35 kN, and the cable leaves the chute **60–73° below
  horizontal**.
- **Lay speed:** tensioners allow 0–20 m/min (item 1); the owner says ~10 m/min. Lay stops at ends and joints.
- **Underwater shot (est.):** the cable coming off the chute, the catenary fading into blue-green water, the
  touchdown with a little sediment, sometimes an ROV following the touchdown.
- **CPS:** a CPS has three parts: a **centraliser / monopile interface**, a **dynamic-zone protection** and a
  **static-zone protection** ([Wikipedia: cable protection system](https://en.wikipedia.org/wiki/Cable_protection_system)).
  Bend restrictors are polymer **vertebrae** (a few degrees per segment, a bigger Ø) or cast-iron half shells inside a
  PU shell. Bend stiffeners are conical PU mouldings. A **latch** goes through an angled hole in the monopile wall
  (J-tubeless). The Balmoral CPS adds a detachable **pull head**
  ([Wikipedia](https://en.wikipedia.org/wiki/Cable_protection_system),
  [WindTech: Balmoral](https://www.windtech-international.com/product-news/balmoral-develops-integrated-cable-protection-solution-for-offshore-wind),
  [OWC white paper](https://abl-group.com/wp-content/uploads/2022/10/OWC-White-Paper-Cable-Protection-Systems.pdf)).
  Sizes **(est.)**: a CPS is 10–25 m long, with an outer Ø 2–3 × the cable Ø; the vertebrae are 0.3–0.6 m long; the
  centraliser is a 1–2 m tapered tube; the latch is a collar with spring dogs.
  **(owner's ref.)** On deck, CPS sets and bend restrictors lie in racks, coloured yellow and brown/orange.

**8. Looks**
- **Power cable:** the outer serving is **polypropylene yarn over the armour, black with yellow**, so the cable is
  visible during laying; dynamic cables have a PE sheath instead
  ([guide to floating offshore wind](https://guidetofloatingoffshorewind.com/guide/b-balance-of-plant/b-1-cables/b-1-2-export-cable/b-1-2-2-export-cable-outer/),
  [cable spec](https://media.salvex.com/auction/d/1830134/183013309_820272.pdf)). Stripe geometry is **not
  published**. Estimate: helical yellow bands at 30–60° to the cable axis, 2–4 bands per lay length of ~8–15 × Ø,
  each band 0.2–0.4 × Ø wide, matte. Length marks (white or yellow numbers) every 10–100 m (est.; owner to confirm
  from his own cables).
- **Steel wire rope:** right regular lay is standard; in regular lay the wires look **parallel to the rope axis**
  (Lang lay looks diagonal). Compacted strands are smoother and denser
  ([TM 5-3810-305](https://constructioncranes.tpub.com/TM-5-3810-305-10/css/TM-5-3810-305-10_91.htm),
  [CERTEX](https://www.certex.dk/en/knowhow/articles-about-steel-wire-rope/technical-description-steel-wire-rope),
  [Lexco](https://www.lexcocable.com/resources/downloads/wire-rope-products)). Look (est.): 6–8 outer strands, lay
  length ~6–7 × Ø, galvanised grey with dark grease in the valleys, an anisotropic sheen along the wires.
- **Paint (owner's ref. + est.):** machinery in a deep blue (RAL 5002/5010 kind) and bright orange (RAL 2004/2008 kind);
  the carousel rim in orange; stairs, railings, quadrant and walkway structure in yellow (RAL 1003/1023) or white; a
  grey deck with green or grey grating walkways; a white deckhouse. Wear (est.): the deck dirty and wet near the
  stern, darker streaks and rust at the bulwark, and polished steel where the cable touches the rollers.

**9. Vessel motion (calm working sea)**
- Cable lay usually stops at **Hs 1.5–2 m** (~65 % workability); a motion-compensated design aims for Hs 3.5 m
  ([Damen](https://go.damen.com/motion-compensated-cable-lay-vessel)). Lay itself is limited by the chute's vertical
  speed, MBR and bottom tension, not by angles
  ([TU Delft](https://repository.tudelft.nl/record/uuid:185da4cd-e0bf-4d57-b9c8-6034868db8ae)). Old pipelay criterion:
  roll ≤ **2° single amplitude** ([TU Delft](https://repository.tudelft.nl/record/uuid:d30fe3ba-8b5b-435d-9b5b-ffc41b08b5d4)).
  Natural roll period ≥ **10 s** ([patent US4345855](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/4345855)).
- **For the video (est.):** roll ±1–1.5° at 10–12 s, pitch ±0.3–0.6° at 6–8 s, heave ±0.2–0.4 m at 7–9 s. Use
  mixed, non-repeating sines, and mind the phase: the stern moves the most. More looks fake.

### The owner's answers and step pictures (11 Nov, evening) – the spread as he works with it

The owner answered the questions and sent a set of step pictures and notes (a promo animation of a modern cable-lay
vessel). They are private reference only and are **not in the repository** (the zip lies in a draft release only he
sees). Below is a **generic** description: which machines there are, in which order and how they move. The demo model
keeps its own sizes and shapes and must not copy that vessel's layout one-to-one.

**Deck layout (aft half of the vessel, from the carousel to the stern):**
- **Carousel** amidships. A **loading tower** beside it carries an **overhead arch**: a ~180° radius controller (rollers
  along the inside of a big inverted U) over which the cable goes from deck level up and down into the carousel. The
  arch **only slews** about the tower's upright axis to reach every coil radius from the core to the rim. It does not go
  up or down: a hanging guide frame with a platform at its end drops the cable into the coil.
- **Two side lanes** of raised roller highways (V roller cradles on trestles, a grating walkway beside each), one on
  each side, and a **lower path ~1–1.5 m below** one of them. Between them lies the **middle lane**, with the
  **rails** for the quadrant (no cable on it during lay).
- **Two track tensioners**, one in each side lane near the stern. **The cable passes through both, one after the
  other** (forward through the first one, aft through the second one; owner, 11 Nov). To let the cable out, each
  tensioner's **top track lifts up and tilts back**.
- **Stern:** a curved **radius controller** in each stern corner turns the cable 180° from one lane into the next. The
  **quadrant handler**, a big frame lying flat in the middle lane at the stern, is hinged at the transom and tilted by
  hydraulic cylinders from 0° to **about 100°**, hanging over the sea. It has a **pulley at its top centre** for the
  quadrant handling wire. Big curved **overboarding chutes** (fair "horns") sit at the stern ends of the side lanes,
  one on each side of the handler: the cable goes overboard down the chute behind the second tensioner.
- **Quadrant:** a **D-shaped frame** (a semicircle with a straight bar across, spokes inside, a cable gutter round the
  curve). Its **stationary position** is lying flat at the **forward end of the middle lane**, where it serves as the
  180° turn of the cable route. It **travels on the rails** along the middle lane.
- **Quadrant handling winch:** in front of the carousel. Its wire runs aft along the deck, over the handler's top
  pulley, to the quadrant.
- **Two tipping winches** on the stern, port and starboard. Their wires run over **sheaves that swivel** to follow the
  quadrant as it tips, to the two ends of the quadrant's straight bar.
- **CPS store:** long racks along one side, several rows high, holding complete CPS sets lying lengthwise. An **orange
  curved ramp** (a twisted slide) brings one CPS down from the racks onto a curved slide that joins the cable route at
  the quadrant's forward position.

**Cable route during lay** (owner's steps 0,1–0,6; loading from the quay is the same route backwards, with the
tensioner pulling the cable in and the carousel turning in step, ~10 m/min):
1. From the carousel coil up into the arch's hanging guide, over the arch, down the tower to deck level.
2. On the **lower path, ~1–1.5 m below** the highway, aft along side A (under the run that comes back aft on top).
3. At the stern, round side A's corner radius controller across to side B (180°), then forward **through tensioner 1**
   in side B's lane.
4. Straight forward along side B to the quadrant at its stationary position, round the quadrant's curve (180°) to
   side A.
5. Straight aft along side A's highway (over the lower path), **through tensioner 2**, and down **side A's stern
   chute** into the sea.
So the cable makes a closed oval on deck (an "O-loop": the tensioners sit between the carousel and the sea, and the
quadrant is one of its turns).

**Coil in the carousel:** the cable end goes through a **hole at the foot of the core** and is fastened inside it. The
first turn lies along the core. The first layer fills **from the core outwards**, the second **from the rim inwards**,
and so on.

**CPS on the cable end** (owner's CPS steps 1–5): one CPS slides from the rack down the orange ramp and the curved
slide onto the highway. It travels along the route round the quadrant and down one lane, stops, and then **runs back
the other way** to its place in front of the cable. The cable comes along steps 1–4 above and is **connected to the
CPS's rear end**. Then the CPS, nose (pull head) first, goes on with step 5 and the quadrant sequence. A CPS set (est.
from the pictures) is ~15–25 m long and ~2× the cable Ø thick. From the nose: a pointed pull head, a grey tube, a
segmented yellow section, brown vertebrae, grey, and yellow bend-restrictor segments next to the cable.

**Quadrant sequence** (owner's steps 1–16):
1. The quadrant sits at its stationary position (it is the route's 180° turn).
2. When the cable hangs just over the edge of the chute, the quadrant **travels aft** on its rails with the cable on it.
3. It stops in front of the tensioners.
4. The tensioners **lift their top track and tilt it back**, letting the cable go.
5. The quadrant travels on, **over the quadrant handler** lying flat at the stern. The **tipping winch wires** are
   connected to both sides of the quadrant.
6. The **handler tilts up**. The quadrant rides on top of it, and the handling wire runs over the pulley at the
   handler's top. The quadrant itself does not turn on the handler: it follows the handler's tilt, and the handling
   winch pays out to keep it in place.
7. At about 100° the handler holds the quadrant **over the stern**, hanging below the top pulley with the curve down.
   The cable bight goes round its curve, both legs down into the water.
8–10. The **handling winch lowers** the quadrant into the water and down. The **tipping winches pay out in step**.
11. Near the seabed the handling winch **holds**, and the tipping winches **pay out more**. The quadrant **tips** (turns
    about its handling-wire point) towards lying flat.
12. It tips further.
13. Tipping done: the cable **slides off** the quadrant onto the seabed.
14. The handling winch **pulls the quadrant back up**.
15. The handler **tilts back down** (the tensioners still have their top tracks tilted up). The quadrant is pulled back
    along the rails to its stationary position.
(Underwater the reference shows clear blue water with sun rays, a monopile, sediment specks, and small glowing markers
on the quadrant's hang-off point.)

**Cable look** (owner's example: a stock render of a Ø 300 mm offshore power cable): black serving with a fine
diagonal yarn texture. The yellow is **pairs of narrow bands**, not single wide stripes. Measured on the picture: each
band ~0.10 × Ø wide, ~0.07 × Ø black between the two bands of a pair, one pair every ~1.3 × Ø along the cable. The bands
run **almost round the cable, ~15–20° off square to the axis** (a slow helix). The serving is matte, with a slight
sheen where it is wet. No length marks are visible.

**Public numbers of comparable spreads** (owner, 11 Nov: his references are recent cable-lay vessels with this layout and a
modular cable-lay system of the same kind he is working on). From public trade-press pages; the names and links are
**left out on purpose** (the owner's work and his clients' equipment do not belong in this public repository; the owner
has them in the 0083 session):
- A ~123 m × 28 m DP2 cable-lay vessel: carousel **Ø 26 m outer, > 5,000 t**, **2 × 20 t** tensioners (listed as
  vertical), a 170 t knuckle-boom crane.
- A ~130 m × 28 m vessel of the same family: **two carousels (on and below deck), 8,000 t together**, can lay two
  cables at once; inter-array cables of **1–1.5 km**, about **3 cables per 24 h**; at the tower end the cable end is
  lowered with the **quadrant** and pulled into the tower.
- A **modular 30 t cable-lay system**: **2 × 15 t tensioners**, **MBR 5 m**, a **50 t A&R winch**, cable **Ø 50–500 mm**,
  a quadrant handling system that overboards the quadrant without a crane (it doubles as a joint-handling arm in
  repairs). A motion-compensated version of such a system: line pull 35 t including dynamics, Ø 50–500 mm.
So the demo model's sizes (Ø 24 m carousel, 2 tensioners, MBR 3.5 m at Ø 200, vessel ~124 m × 27 m) sit right in this
range; for a "Ø 500 mm" demo the MBR of 5 m+ and 15–20 t tensioners are the numbers to use.

### Check against 0076 (0076 was finished on its branch while this ran; compared with its `params.py` and report)

| # | 0076 has | Reference says | Suggested change (lead decides) |
| --- | --- | --- | --- |
| 1 | Two tensioners **in a row** on one centre line; cable carousel → arm → deck line → tensioners → chute in one straight line | **Owner (11 Nov): one tensioner in each side lane**, and the route as in "Cable route during lay" above: an oval through **both** tensioners: lower path aft on side A, 180° at the stern, forward through tensioner 1 on side B, 180° round the quadrant, aft through tensioner 2 on side A, down side A's chute | **Re-lay the deck:** two side lanes (a tensioner in each) + the quadrant's middle lane, a lower path 1–1.5 m under side A, a stern-corner radius controller, the chute at side A's stern. Route JSON: this one oval route, through both tensioners. |
| 2 | Tensioner fixed in the line | Owner: the **top track lifts up and tilts back** to let the cable out (step 4) | Give the top-track carriage a lift (squeeze cylinders, longer stroke) plus a tilt hinge at its aft end, and add both to the joint sheet. |
| 3 | Track gripping run 20 × 300 = **6 m** | 15 t class: 3–3.2 m; range 1.75–5.5 m | 6 m is long but possible for ~25–30 t. For a "15–25 t" look, use **12–14 links (3.6–4.2 m)**, which also saves triangles. |
| 4 | Pads with a **120° V** | 160° V, rubber, 70 Shore A | Keep it if the 120° V is needed for Ø 50–500 on one pad, or make it **150–160°** and let the squeeze stroke cover the range. Make the pads look rubber (dark, matte) on a steel back plate. |
| 5 | Lebus: **two 18° crossovers** per turn | ~20 % of the circumference crosses (≈ 2 × 36°) | Widen each crossover to **~30–40°**, and keep the two 180° apart. Add **riser / filler wedges** at the flanges if they are missing. |
| 6 | Carousel Ø 24 m, rim 5 m, core Ø 8 m | 7,000 t class: Ø 23–28 m, rim/core 5–6 m, core Ø 4–8 m | OK. Optional: lightening holes in the rim plates (owner's ref.); a walkway bridge from the tower to the core. |
| 7 | Quadrant (quarter circle) hinged at the transom, tips 0–100°; handling winch with a lead sheave; two tipping winches on a stern frame | Owner: a **D-shaped quadrant** lying flat at the forward end of the middle lane (the route's 180° turn), **travelling on rails** aft over a **quadrant handler** (a frame hinged at the transom, 0→~100° by cylinders, a top pulley). Handling winch in front of the carousel, its wire over the handler's pulley. **Tipping winches port and starboard on the stern, swivelling sheaves**, wires to the two ends of the D's bar. Quadrant tips near the seabed to release the cable | **Rebuild the quadrant system:** D-frame (radius ≥ MBR, gutter, hang-off) on rail bogies, rails along the middle lane, a separate handler frame with tilt cylinders and a top pulley, the handling winch moved forward, two stern tipping winches with swivel sheaves. Joints: quadrant slide (rails), handler tilt 0–100°, quadrant hang + tip about its wire point (for 0082), sheave swivels. |
| 8 | Route rollers: 14 on stands at 1.8 m | Rollers ~1–2 m apart, 0.8–1.8 m high | 14 rollers over ~40 m of deck line is sparse. Put **~1.5 m between rollers** on the straights (cheap parts, instanced). |
| 9 | No cable straightener and no linear cable engine | Linear cable engines (wheel pairs) are common on deck routes | Optional: one cable engine between the tower and tensioner 1 (wheels turn with the cable: a good test for 0078). |
| 10 | Lift-off from the coil is a free span | The spooling arm guides the cable from the coil (bellmouth / guide rollers) | As 0076 noted: a bellmouth or roller cage at the arm's end. |
| 11 | Static CPS on the cable end at the quadrant | CPS = centraliser + dynamic + static sections; racks of CPS on deck | OK. Optional: a CPS rack on deck as set dressing. |
| 12 | Handling wire Ø 48, quadrant wire 56, tipping wire 36 | Est. Ø 40–60 for 25–50 t | OK. |
| 13 | Loading tower + slewing arm with a trolley that moves in/out | Owner: an **overhead arch** (~180° radius controller) that **only slews**; a hanging guide frame drops the cable into the coil | Replace the trolley's in/out by slewing alone (the guide's radius follows from the slew angle). The arch's rollers along its inside are the cable's bend. |
| 14 | Cable end at the core: not modelled | Owner: the cable end goes through a **hole at the foot of the core** and is fastened inside; first turn along the core; layer 1 outwards, layer 2 inwards | Add the core hole (and a simple clamp inside). The coil solid: flat layers. |
| 15 | No CPS store | Owner: CPS racks along one side, an orange twisted **ramp** and a curved slide to the route at the quadrant | Add a rack with 4–6 CPS sets, the ramp and the slide (set dressing, and a path for 0082's CPS run). |
| 16 | One stern chute in the middle | Owner: the chutes are the curved overboarding "horns" at the stern ends of the side lanes, on both sides of the handler; a 180° radius controller across the stern | Move the chute to side A's stern (a horn on side B for the mirrored set-up), add the stern radius controller; the middle lane's stern end is the handler. |

### Facts per task 0077–0082

- **0077 demo project:** real speeds are slow, so animate at real speed with a time-lapse factor in a caption
  ("× 10"). Carousel 0.14–0.40 rpm at 10 m/min. Loading arm: in or out 1 Ø per turn. Tensioner squeeze: cylinders
  stroke ~0.1–0.3 m in 5–10 s. Quadrant tip 0→90° in 10–20 min real (show in 10–20 s). Vessel motion as in item 9.
  Paint and looks as in item 8. Owner's ref. effects worth copying: an **X-ray / outline highlight** of one machine
  (exists: X-ray look + Fade steps, 0073) and **arrow chevrons** showing the cable's direction (decal arrows / labels).
- **0078 cable paths + looks:** one cable speed of 0–20 m/min (default 10). Stripe: **pairs of narrow yellow bands** (each
  0.10 × Ø, 0.07 × Ø apart, a pair every 1.3 × Ø, 15–20° off square), fine diagonal yarn texture, matte; it must move
  with the cable. Steel wire: regular lay, 6–8 strands, lay ~6.5 × Ø, galvanised + grease.
  Rollers turn at v / r_roller (a 0.3 m roller at 10 m/min = 10.6 rpm: visible). Sheave grooves: radius = rope centre.
- **0079 tensioner tracks:** 2 tracks; pads at the chain pitch (0.3 m), rubber, V 120–160°. The gripping run moves
  **with** the cable (no slip). Sprocket rpm = v / (2π r_sprocket); 8 teeth × 300 mm gives r 0.39 m, i.e. 4.1 rpm at
  10 m/min. Squeeze: the top track goes down parallel by the cylinders, stroke ≈ Ø range + 0.1–0.2 m, 0–60 t total.
  Both tensioners share the line tension; one opens at an end or joint. Lift + tilt out of the line (owner's ref.).
- **0080 spooling:** flat spiral layers that alternate direction, crossover at the core or rim; ~1,900 m and ~3.2 h per
  layer (Ø 24 m carousel, Ø 200 cable). The arm's guide moves radially 1 Ø per turn. Storage carousel: same, on a base
  frame. Drums: spiral groove at pitch 1.03–1.06 × rope Ø; Lebus 2 crossovers per turn (~20 % of the circumference)
  + flange risers; fleet angle 0.5–2°.
- **0081 cable into the sea:** catenary with T_top = T_bot + w·h. Layback 26–39 m for 20–50 m depth (the example
  above); departure angle 60–75° below horizontal. Touchdown with a little sediment; water clarity slider. CPS parts
  as in item 7. Vessel motion: stern heave ±0.2–0.4 m moves the chute exit, and the catenary follows.
- **Owner's sequence (11 Nov) replaces the estimates where they differ:** route, quadrant steps 1–15, CPS run and
  cable look are in "The owner's answers and step pictures" above. Demo (0077): **loading from the quay** (quay
  surroundings, cable from a quay storage carousel through the stern-corner radius controller and the tensioner into
  the carousel) **and** laying.
- **0082 quadrant operations:** the 7-step second-end sequence (item 4) and the first-end pull-in. Tipping winches
  pull the quadrant over (hinge at the stern); the quadrant handling winch (heave-compensated, ~25 t) lowers it;
  tensioners pay out and then open; ROV release. Handling winches join the cable by a grip / Chinese finger or the
  pull head, for extra pull or to pass the CPS.

### Shot list (1 min 45 s; ~25 fps; time-lapse factor shown where used)

| # | Shot | Camera | s | Needs |
| --- | --- | --- | --- | --- |
| 1 | Establishing: the vessel on a calm sea, gentle roll | Drone, high and far, slow push-in from the bow quarter | 10 | Open sea + waves, vessel motion (study #4 / 0081), camera path (idea #7) |
| 2 | The deck from above: carousel, route, tensioners, stern | Top-down orbit, slow turn | 10 | Turntable / camera views (exists) |
| 2b | Loading at the quay: cable from a quay storage carousel over the stern, round the corner radius controller, through the tensioner, over the arch into the carousel | Drone along the route, then down into the carousel | 12 (× 10) | Quay surroundings (exist), 0078 + 0080 |
| 3 | Carousel turning, the loading arm following the layer, striped cable coming off | Low on the rim walkway, looking across the coil | 10 (× 10 time-lapse) | 0080 spooling + 0078 looks |
| 4 | Cable down the tower's radius controller onto the roller highway, rollers turning | Tracking along the highway at cable speed, low | 10 | 0078 cable paths, rollers turn |
| 5 | Tensioner squeeze: top track lowers onto the cable, then the tracks run | Close-up side view, slight dolly | 10 | 0079 tracks + squeeze (cylinders exist as joints) |
| 6 | X-ray highlight of the tensioner, labels on its parts | Same spot, cut to a wider frame | 8 | Labels and X-ray look / Fade (exist, 0073) |
| 7 | Handling winch: wire spooling on the spiral-groove drum; a Lebus close-up | Macro on the drum, rack focus | 8 | 0080 drums, 0078 wire look, depth of field (exists) |
| 8 | Cable over the stern chute into the water | From behind the stern, low over the water | 10 | 0078 + 0081 |
| 9 | Underwater: catenary to touchdown, clear water, cut-away hull | Underwater, sliding along the cable | 12 | 0081 (water clarity slider, cut-away) |
| 10 | Quadrant: it travels aft on its rails, the tensioners' top tracks tilt up, the handler tilts over the stern, the quadrant is lowered and tips near the seabed (underwater cut) | Side view of the stern, slow crane-up; then underwater | 15 (× 20 time-lapse) | 0082 quadrant operations |
| 11 | End card: the vessel sailing on, logo | Drone pull-back | 5 | Brand kit / end card (exists) |

**Open points:**
- Answered by the owner (11 Nov): one tensioner per side, the route, the quadrant sequence, the CPS run, the cable look,
  loading from the quay in the demo; the cable goes through **both** tensioners; the quadrant sequence is how the
  cable is **put into the sea** (its end lowered to the seabed), and the same steps backwards **pull it up again**.
  Datasheets: web search works from a web session, opening pages does not; a later task that needs a full datasheet asks
  for its host when it needs it (the owner approves the network change then): royalihc.com, macartney.com,
  azure.macartney.com, briggsmarine.com, swanhunter.com, jandenul.com.
- The check against 0076 now has 16 rows. Rows 1, 2, 7 and 13–16 change the layout a lot: a follow-up task on the Demo
  models lane ("0076 b: deck re-layout") before 0077 is worth it (lead decides).
- Not answered by public sources (estimates only): pad pitch, squeeze stroke, roller spacing, CPS dimensions, stripe
  geometry, procedure durations, roll/pitch numbers.
- 0076 notes were **not** written into `tasks/0076-demo-cable-lay-model.md`: 0076's finished report lives on its
  branch (`claude/sleepy-darwin-bzhvdy`), and editing the file on `main` would clash with its merge. The table above
  is the note.
- The owner's screenshots were used as private reference only; nothing of them is committed.
